from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import strict_base_contract as contract  # noqa: E402


PUBLIC_MANIFEST = (
    REPO_ROOT
    / "projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold"
    / "oof-router/runs/exp-058-fold-manifest-preflight-attempt-2"
    / "fold-manifest.public.jsonl"
)


class StrictBaseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = contract.load_public_fold_manifest(PUBLIC_MANIFEST)

    def test_happy_path_freezes_seven_fits_and_three_active_dev_fits(self) -> None:
        plan = contract.validate_full_plan(contract.FULL_FIT_PLAN)
        self.assertEqual(len(plan), 7)
        self.assertEqual(tuple(fit.fit_id for fit in contract.active_dev_plan()), contract.ACTIVE_DEV_FIT_IDS)
        self.assertEqual(
            tuple(item["fit_id"] for item in contract.summarize_active_dev(self.rows)),
            contract.ACTIVE_DEV_FIT_IDS,
        )
        self.assertEqual(contract.m3_steps(1344), 2688)
        self.assertIn("heldout-logits", contract.SNAPSHOT_CONTRACT)
        self.assertEqual(contract.VIEW_FIT_IDS["final-development"][-1], "tune-h3")
        value = contract.strict_base_public_contract(PUBLIC_MANIFEST)
        self.assertEqual(value["fit_count_per_family"], 7)
        self.assertEqual(value["manifest"]["sha256"], contract.EXPECTED_PUBLIC_MANIFEST_SHA256)
        self.assertEqual(
            value["manifest"]["membership_sha256"],
            contract.EXPECTED_PUBLIC_MEMBERSHIP_SHA256,
        )
        self.assertFalse(contract.public_sensitive_paths(value))

    def test_fold4_injection_is_rejected(self) -> None:
        changed = list(contract.FULL_FIT_PLAN)
        changed[0] = replace(changed[0], train_folds=(1, 2, 4))
        with self.assertRaisesRegex(contract.ContractError, "forbidden fold 4"):
            contract.validate_fit_plan(changed)

    def test_train_and_heldout_overlap_is_rejected(self) -> None:
        changed = list(contract.FULL_FIT_PLAN)
        changed[0] = replace(changed[0], train_folds=(0, 1, 2))
        with self.assertRaisesRegex(contract.ContractError, "overlap"):
            contract.validate_fit_plan(changed)

    def test_missing_and_duplicate_fit_are_rejected(self) -> None:
        with self.assertRaisesRegex(contract.ContractError, "incomplete"):
            contract.validate_fit_plan(contract.FULL_FIT_PLAN[:-1])
        duplicated = contract.FULL_FIT_PLAN + (contract.FULL_FIT_PLAN[0],)
        with self.assertRaisesRegex(contract.ContractError, "duplicate"):
            contract.validate_fit_plan(duplicated)

    def test_actual_public_manifest_dev_counts_membership_and_schedules(self) -> None:
        aggregate = contract.validate_exp058_public_manifest(self.rows)
        self.assertEqual((aggregate["rows"], aggregate["components"]), (3360, 3277))
        self.assertEqual(
            [(aggregate["folds"][str(fold)]["rows"], aggregate["folds"][str(fold)]["components"]) for fold in range(3)],
            [(672, 658), (672, 654), (672, 651)],
        )
        expected = {
            "dev-h0": (1344, 1305),
            "dev-h1": (1344, 1309),
            "dev-h2": (1344, 1312),
        }
        for fit in contract.active_dev_plan():
            summary = contract.summarize_fit(self.rows, fit)
            self.assertEqual(
                (summary["training"]["rows"], summary["training"]["components"]),
                expected[fit.fit_id],
            )
            self.assertEqual(summary["heldout"]["rows"], 672)
            self.assertEqual(summary["m1_schedule"]["steps_per_epoch"], 84)
            self.assertEqual(summary["m1_schedule"]["warmup_steps"], 42)
            self.assertEqual(summary["m1_schedule"]["selected_stop_steps"], 336)
            self.assertEqual(summary["m3_schedule"]["optimizer_steps"], 2688)

        tune = contract.summarize_fit(
            self.rows, next(fit for fit in contract.FULL_FIT_PLAN if fit.fit_id == "tune-h3")
        )
        self.assertEqual((tune["training"]["rows"], tune["training"]["components"]), (2016, 1963))
        self.assertEqual(tune["m1_schedule"]["steps_per_epoch"], 126)
        self.assertEqual(tune["m1_schedule"]["warmup_steps"], 63)
        self.assertEqual(tune["m1_schedule"]["selected_stop_steps"], 504)
        self.assertEqual(tune["m3_schedule"]["optimizer_steps"], 4032)

    def test_heldout_logits_schema_is_gold_free(self) -> None:
        schema = contract.validate_snapshot_schema(
            "heldout-logits", contract.HELDOUT_LOGITS_SCHEMA.fields
        )
        self.assertFalse(schema.contains_gold)
        self.assertNotIn("gold", schema.fields)
        with self.assertRaisesRegex(contract.ContractError, "schema drift"):
            contract.validate_snapshot_schema(
                "heldout-logits", (*contract.HELDOUT_LOGITS_SCHEMA.fields, "gold")
            )

    def test_public_sensitive_check_rejects_ids_gold_and_logits(self) -> None:
        with self.assertRaises(contract.ContractError):
            contract.assert_public_safe({"sample_ids": ["sample-secret"]})
        with self.assertRaises(contract.ContractError):
            contract.assert_public_safe({"nested": {"gold": [[1, 0, 0, 0, 0, 0]]}})
        with self.assertRaises(contract.ContractError):
            contract.assert_public_safe({"nested": {"logits": [0.0]}})


if __name__ == "__main__":
    unittest.main()
