from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import scoped_input_contract as contract  # noqa: E402


def source_rows(*, fold_id: int = 0, suffix: str = "a", labels: list[int] | None = None):
    labels = labels or [1, 0, 0, 0, 0, 0]
    sample_id = f"sample-{suffix}"
    component_id = f"component-{suffix}"
    public = {
        "schema_version": contract.SOURCE_FOLD_SCHEMA_VERSION,
        "protocol_id": contract.PROTOCOL_ID,
        "experiment_id": contract.SOURCE_FOLD_EXPERIMENT_ID,
        "sample_id": sample_id,
        "component_id": component_id,
        "fold_id": fold_id,
    }
    train = {
        "schema_version": contract.SOURCE_TRAIN_SCHEMA_VERSION,
        "protocol_id": contract.PROTOCOL_ID,
        "sample_id": sample_id,
        "component_id": component_id,
        "text": f"text {suffix}",
        "labels": labels,
        "neutral": sum(labels) == 0,
        "label_cardinality": sum(labels),
    }
    private = {
        **public,
        "labels": labels,
        "neutral": sum(labels) == 0,
        "label_cardinality": sum(labels),
    }
    return public, train, private


class ScopedInputContractTests(unittest.TestCase):
    def test_happy_path_materializes_three_scoped_rows(self) -> None:
        public, train, private = source_rows(fold_id=0)
        outputs = contract.materialize_selected_row(public, train, private, 7)
        self.assertEqual(set(outputs), set(contract.OUTPUT_SCHEMAS))
        self.assertEqual(outputs["train-capable"]["source_ordinal"], 7)
        self.assertEqual(outputs["consumer-gold"]["gold"], train["labels"])
        self.assertNotIn("labels", outputs["gold-free-inference"])
        self.assertNotIn("gold", outputs["gold-free-inference"])
        contract.validate_output_json_row("train-capable", outputs["train-capable"], 0)
        contract.validate_output_json_row(
            "gold-free-inference", outputs["gold-free-inference"], 0
        )

    def test_source_schema_drift_is_rejected(self) -> None:
        public, train, private = source_rows()
        del train["neutral"]
        with self.assertRaisesRegex(contract.ContractError, "schema drift"):
            contract.materialize_selected_row(public, train, private, 0)
        public, train, private = source_rows()
        private["unexpected"] = True
        with self.assertRaisesRegex(contract.ContractError, "schema drift"):
            contract.materialize_selected_row(public, train, private, 0)

    def test_source_join_identity_and_fold_scope_are_enforced(self) -> None:
        public, train, private = source_rows()
        private["sample_id"] = "sample-other"
        with self.assertRaisesRegex(contract.ContractError, "join identity"):
            contract.materialize_selected_row(public, train, private, 0)
        public, train, private = source_rows(fold_id=3)
        with self.assertRaisesRegex(contract.ContractError, "only folds 0-2"):
            contract.materialize_selected_row(public, train, private, 0)

    def test_output_fold_and_source_order_are_enforced(self) -> None:
        rows = []
        for ordinal, suffix in ((2, "a"), (5, "b")):
            public, train, private = source_rows(fold_id=1, suffix=suffix)
            rows.append(
                contract.materialize_selected_row(public, train, private, ordinal)[
                    "gold-free-inference"
                ]
            )
        summary = contract.validate_output_rows(
            "gold-free-inference", rows, 1, require_frozen_identity=False
        )
        self.assertEqual((summary["rows"], summary["components"]), (2, 2))
        with self.assertRaisesRegex(contract.ContractError, "source order"):
            contract.validate_output_rows(
                "gold-free-inference", list(reversed(rows)), 1, require_frozen_identity=False
            )
        with self.assertRaisesRegex(contract.ContractError, "fold drift"):
            contract.validate_output_json_row("gold-free-inference", rows[0], 2)

    def test_gold_free_schema_and_consumer_dtypes_are_frozen(self) -> None:
        self.assertFalse(contract.OUTPUT_SCHEMAS["gold-free-inference"].contains_gold)
        self.assertFalse(
            {"gold", "labels", "neutral", "label_cardinality"}
            & set(contract.OUTPUT_SCHEMAS["gold-free-inference"].fields)
        )
        public, train, private = source_rows()
        inference = contract.materialize_selected_row(public, train, private, 0)[
            "gold-free-inference"
        ]
        inference["labels"] = [1, 0, 0, 0, 0, 0]
        with self.assertRaisesRegex(contract.ContractError, "schema drift"):
            contract.validate_output_json_row("gold-free-inference", inference, 0)

        metadata = {
            name: {"dtype": spec.dtype, "shape": list(spec.shape)}
            for name, spec in contract.CONSUMER_GOLD_ARRAYS.items()
        }
        contract.validate_consumer_gold_arrays(metadata, 0)
        changed = deepcopy(metadata)
        changed["gold"]["dtype"] = "float32"
        with self.assertRaisesRegex(contract.ContractError, "dtype/shape"):
            contract.validate_consumer_gold_arrays(changed, 0)

    def test_expected_fold_counts_and_membership_hashes_are_frozen(self) -> None:
        self.assertEqual(
            [contract.EXPECTED_FOLD_IDENTITY[fold]["components"] for fold in range(3)],
            [658, 654, 651],
        )
        for fold in range(3):
            expected = contract.EXPECTED_FOLD_IDENTITY[fold]
            self.assertEqual(expected["rows"], 672)
            self.assertEqual(len(expected["sample_order_sha256"]), 64)
            self.assertEqual(len(expected["component_membership_sha256"]), 64)
            self.assertEqual(len(expected["row_membership_sha256"]), 64)
            self.assertEqual(len(expected["source_ordinal_sha256"]), 64)

    def test_fit_level_producer_allowlist_is_exact_and_gold_free(self) -> None:
        for fit_id, expected in contract.PRODUCER_ALLOWLIST.items():
            self.assertEqual(contract.validate_producer_request(fit_id, expected), expected)
            self.assertFalse(any(grant.scope == "consumer-gold" for grant in expected))
        with self.assertRaisesRegex(contract.ContractError, "may not request scope"):
            contract.validate_producer_request(
                "dev-h0",
                [
                    ("train-capable", 1),
                    ("train-capable", 2),
                    ("gold-free-inference", 0),
                    ("consumer-gold", 0),
                ],
            )
        with self.assertRaisesRegex(contract.ContractError, "may not request fold"):
            contract.validate_producer_request(
                "dev-h0",
                [("train-capable", 1), ("train-capable", 2), ("gold-free-inference", 4)],
            )

    def test_jsonl_parser_digest_and_public_privacy(self) -> None:
        public, _, _ = source_rows()
        line = contract.canonical_json_line(public)
        parsed = contract.parse_source_json_line("public-fold-manifest", line, 0)
        self.assertEqual(parsed, public)
        self.assertEqual(contract.canonical_digest({"b": 2, "a": 1}), contract.canonical_digest({"a": 1, "b": 2}))
        safe = {"rows": 672, "membership_sha256": "a" * 64}
        contract.assert_public_safe(safe)
        with self.assertRaisesRegex(contract.ContractError, "sensitive"):
            contract.assert_public_safe({"nested": {"sample_ids": ["sample-secret"]}})
        with self.assertRaisesRegex(contract.ContractError, "sensitive"):
            contract.assert_public_safe({"nested": {"text": "private text"}})


if __name__ == "__main__":
    unittest.main()
