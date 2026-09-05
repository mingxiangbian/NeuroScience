#!/usr/bin/env python3

from __future__ import annotations

import ast
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "sqma-004-agent-tune-input.json"
RUNNER_PATH = PROJECT_ROOT / "scripts" / "run_sqma004_agent_tune_input.py"
VERIFIER_PATH = PROJECT_ROOT / "scripts" / "verify_sqma004_agent_tune_input.py"
CONTRACT_PATH = PROJECT_ROOT / "scripts" / "scoped_input_contract.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load_module("sqma004_runner_for_tests", RUNNER_PATH)
VERIFIER = load_module("sqma004_verifier_for_tests", VERIFIER_PATH)
CONTRACT = load_module("sqma004_contract_for_tests", CONTRACT_PATH)
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def source_rows(fold: int = 3):
    labels = [0, 1, 0, 0, 0, 0]
    public = {
        "schema_version": "exp-058-fold-row-v1", "protocol_id": "DATA-SO-TASK-V1",
        "experiment_id": "EXP-058", "sample_id": "sample-x", "component_id": "component-x",
        "fold_id": fold,
    }
    train = {
        "schema_version": "so-emotion-c0-v1", "protocol_id": "DATA-SO-TASK-V1",
        "sample_id": "sample-x", "component_id": "component-x", "text": "It finally works!",
        "labels": labels, "neutral": False, "label_cardinality": 1,
    }
    private = {**public, "labels": labels, "neutral": False, "label_cardinality": 1}
    return public, train, private


def imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


class Sqma004AgentTuneInputTests(unittest.TestCase):
    def test_design_is_fold3_only_and_non_executable(self) -> None:
        self.assertFalse(CONFIG["authorization"]["execution_authorized"])
        self.assertEqual(CONFIG["planned_access"]["decode_private_rows_for_folds"], [3])
        self.assertFalse(CONFIG["planned_access"]["decode_private_rows_for_folds_0_2"])
        self.assertFalse(CONFIG["planned_access"]["decode_private_rows_for_fold4"])
        self.assertEqual(CONFIG["snapshot_contract"]["scopes"], ["gold-free-inference", "consumer-gold"])
        self.assertFalse(CONFIG["snapshot_contract"]["train_capable_created"])
        self.assertEqual(
            CONFIG["sqma003_completion_contract"]["accuracy_scored"], False
        )

    def test_sqma003_completion_uses_actual_accuracy_scored_field(self) -> None:
        completion = {
            "schema_version": "sqma-003-complete-v1",
            "experiment_id": "SQMA-003",
            "status": "Complete",
            "sqma003_complete": True,
            "agent_preflight_verified": True,
            "preflight_gate": "Passed",
            "accuracy_scored": False,
            "gold_accessed": False,
            "model_training_executed": False,
        }
        expected = CONFIG["sqma003_completion_contract"]
        RUNNER.validate_sqma003_completion(completion, expected)
        VERIFIER.validate_sqma003_completion(completion, expected)

        wrong = dict(completion)
        wrong.pop("accuracy_scored")
        wrong["accuracy_evidence"] = False
        with self.assertRaisesRegex(RUNNER.TuneInputError, "accuracy boundary"):
            RUNNER.validate_sqma003_completion(wrong, expected)
        with self.assertRaisesRegex(VERIFIER.VerificationError, "accuracy boundary"):
            VERIFIER.validate_sqma003_completion(wrong, expected)

    def test_runner_and_verifier_agree_on_fold3_materialization(self) -> None:
        public, train, private = source_rows()
        runner_value = RUNNER.materialize_fold3_row(public, train, private, 17, CONTRACT)
        verifier_value = VERIFIER.materialize_expected_row(public, train, private, 17, CONTRACT)
        self.assertEqual(runner_value, verifier_value)
        inference, gold = verifier_value
        self.assertEqual(set(inference), VERIFIER.GOLD_FREE_FIELDS)
        self.assertNotIn("gold", inference)
        self.assertEqual(gold["gold"], [0, 1, 0, 0, 0, 0])

    def test_private_decode_gate_rejects_every_non_fold3_fold(self) -> None:
        self.assertTrue(VERIFIER.decode_private_fold(3))
        for fold in (0, 1, 2, 4):
            with self.subTest(fold=fold):
                self.assertFalse(VERIFIER.decode_private_fold(fold))
        public, train, private = source_rows(4)
        with self.assertRaisesRegex(VERIFIER.VerificationError, "non-fold3"):
            VERIFIER.materialize_expected_row(public, train, private, 1, CONTRACT)

    def test_gold_free_schema_is_exact_and_rejects_derived_fields(self) -> None:
        inference, _ = VERIFIER.materialize_expected_row(*source_rows(), 0, CONTRACT)
        VERIFIER.validate_gold_free_row(inference, CONTRACT)
        for field, value in (("gold", [0] * 6), ("labels", [0] * 6), ("neutral", True), ("label_cardinality", 0)):
            changed = dict(inference)
            changed[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(VERIFIER.VerificationError, "schema"):
                VERIFIER.validate_gold_free_row(changed, CONTRACT)

    def test_source_identity_and_order_drift_fail(self) -> None:
        public, train, private = source_rows()
        private["component_id"] = "component-other"
        with self.assertRaisesRegex(VERIFIER.VerificationError, "join"):
            VERIFIER.materialize_expected_row(public, train, private, 0, CONTRACT)
        public, train, private = source_rows()
        private["labels"] = [1, 0, 0, 0, 0, 0]
        private["label_cardinality"] = 1
        with self.assertRaisesRegex(VERIFIER.VerificationError, "gold"):
            VERIFIER.materialize_expected_row(public, train, private, 0, CONTRACT)

    def test_fold3_identity_and_output_inventory_are_frozen(self) -> None:
        self.assertEqual(VERIFIER.FOLD3_IDENTITY["rows"], 672)
        self.assertEqual(VERIFIER.FOLD3_IDENTITY["components"], 657)
        self.assertEqual(len(VERIFIER.FOLD3_IDENTITY["source_ordinal_sha256"]), 64)
        self.assertEqual(
            CONFIG["outputs"]["private_allowed_files"],
            ["fold-3/gold-free-inference.jsonl", "fold-3/consumer-gold.npz", "private-manifest.json"],
        )

    def test_public_privacy_rejects_row_values(self) -> None:
        self.assertFalse(VERIFIER.public_sensitive_paths({"rows": 672, "sha256": "a" * 64}))
        for payload in (
            {"sample_id": "sample-x"}, {"nested": {"text": "secret"}},
            {"nested": ["component-x"]}, {"gold": [[0, 1, 0, 0, 0, 0]]},
        ):
            with self.subTest(payload=payload):
                self.assertTrue(VERIFIER.public_sensitive_paths(payload))

    def test_verifier_is_independent_and_model_free(self) -> None:
        roots = imported_roots(VERIFIER_PATH)
        self.assertNotIn("run_sqma004_agent_tune_input", roots)
        self.assertFalse(roots & {"mlx", "mlx_lm", "torch", "transformers"})
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import run_sqma004_agent_tune_input", source)

    def test_completion_contract_has_no_automatic_comparison(self) -> None:
        protocol = (PROJECT_ROOT / "protocols/sqma-004-agent-tune-input.md").read_text(encoding="utf-8")
        self.assertIn("agent_tune_comparison_authorized=false", protocol)
        self.assertIn("next_gate=register_full_672_row_agent_tune_matched_comparison", protocol)
        self.assertIn("accuracy_scored=false", protocol)
        self.assertFalse(CONFIG["authorization"]["automatic_next_stage"])


if __name__ == "__main__":
    unittest.main()
