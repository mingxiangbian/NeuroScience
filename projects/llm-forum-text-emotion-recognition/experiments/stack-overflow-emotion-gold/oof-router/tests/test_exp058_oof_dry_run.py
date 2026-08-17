from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp058_oof_dry_run.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp058_oof_dry_run.py"
CONFIG_PATH = MODULE_DIR / "configs" / "exp-058-oof-consumer-dry-run-fold-0.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_module("exp058_oof_dry_run_under_test", RUNNER_PATH)


class DryRunContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def test_authorization_is_exactly_fold_zero_two_steps(self) -> None:
        config = runner.load_config(CONFIG_PATH)
        authorization = config["authorization"]
        self.assertEqual(authorization["fold_id"], 0)
        self.assertEqual(authorization["model_seed"], 42)
        self.assertTrue(authorization["model_loading"])
        self.assertTrue(authorization["two_step_training"])
        self.assertTrue(authorization["heldout_forward"])
        for key in (
            "calibration",
            "full_oof_training",
            "metrics",
            "oracle_analysis",
            "router_training",
            "test_access",
            "validation_access",
        ):
            self.assertFalse(authorization[key])
        self.assertEqual(config["execution"]["optimizer_steps_per_model"], 2)
        self.assertEqual(config["execution"]["heldout_forward_rows_per_model"], 2)

    def test_partition_preserves_source_order_and_component_isolation(self) -> None:
        partition = runner.load_partition(self.config)
        self.assertEqual(len(partition["training"]), 2688)
        self.assertEqual(len(partition["heldout"]), 672)
        self.assertFalse(
            {row["sample_id"] for row in partition["training"]}
            & {row["sample_id"] for row in partition["heldout"]}
        )
        self.assertFalse(
            {row["component_id"] for row in partition["training"]}
            & {row["component_id"] for row in partition["heldout"]}
        )
        reconstructed = []
        train_ids = {row["sample_id"] for row in partition["training"]}
        heldout_ids = {row["sample_id"] for row in partition["heldout"]}
        for row in partition["all"]:
            reconstructed.append("training" if row["sample_id"] in train_ids else "heldout")
            self.assertIn(row["sample_id"], train_ids | heldout_ids)
        self.assertEqual(reconstructed.count("training"), 2688)
        self.assertEqual(reconstructed.count("heldout"), 672)

    def test_m1_scheduler_preserves_five_epoch_horizon(self) -> None:
        schedule = runner.m1_schedule(self.config, 2688)
        self.assertEqual(
            schedule,
            {
                "steps_per_epoch": 168,
                "planned_scheduler_epochs": 5,
                "scheduler_horizon_steps": 840,
                "warmup_steps": 84,
                "selected_stop_epoch": 4,
                "selected_stop_steps": 672,
            },
        )
        self.assertNotEqual(168 * 4 * 0.1, int(168 * 4 * 0.1))

    def test_public_privacy_scanner_rejects_row_level_fields(self) -> None:
        self.assertEqual(runner.public_sensitive_paths({"label_order": ["love"]}), [])
        violations = runner.public_sensitive_paths(
            {"safe": {"sample_ids": ["sample-x"], "logits": [[0.1]]}}
        )
        self.assertEqual(violations, ["$.safe.sample_ids", "$.safe.logits"])

    def test_full_oof_consumer_contract_remains_sealed(self) -> None:
        contract = runner.load_json_record(self.config["prerequisites"]["consumer_contract"])
        self.assertFalse(contract["training_authorized_by_contract"])
        self.assertFalse(contract["consumers"]["M1"]["authorized"])
        self.assertFalse(contract["consumers"]["M3"]["authorized"])

    def test_m3_prerequisite_is_successful_attempt_two(self) -> None:
        record = self.config["prerequisites"]["m3_seed_42_verification"]
        self.assertTrue(record["path"].endswith("verification-attempt-2.json"))
        verification = runner.load_json_record(record)
        self.assertEqual(verification["status"], "Passed")
        self.assertEqual(verification["checks_passed"], 148)
        self.assertEqual(verification["checks_total"], 148)
        self.assertEqual(verification["failed_checks"], [])

    def test_runner_has_no_top_level_model_library_imports(self) -> None:
        tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
        imports = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[0])
        self.assertFalse({"mlx", "mlx_lm", "torch", "transformers"} & set(imports))

    def test_verifier_imports_no_model_libraries_or_runner(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[0])
        self.assertFalse({"mlx", "mlx_lm", "torch", "transformers"} & set(imports))
        self.assertNotIn("run_exp058_oof_dry_run", source)


if __name__ == "__main__":
    unittest.main()
