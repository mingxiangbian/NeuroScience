from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp058_oof_production.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp058_oof_production.py"
CONFIG_PATH = MODULE_DIR / "configs" / "exp-058-oof-production.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_module("exp058_oof_production_under_test", RUNNER_PATH)


class OOFProductionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = runner.load_config(CONFIG_PATH)

    def test_authorization_is_full_five_fold_but_train_only(self) -> None:
        authorization = self.config["authorization"]
        self.assertEqual(authorization["fold_ids"], [0, 1, 2, 3, 4])
        self.assertEqual(authorization["model_seed"], 42)
        for key in ("assembly", "full_oof_training", "heldout_forward", "model_loading"):
            self.assertTrue(authorization[key])
        for key in (
            "calibration",
            "metrics",
            "oracle_analysis",
            "router_training",
            "test_access",
            "validation_access",
        ):
            self.assertFalse(authorization[key])

    def test_all_partitions_preserve_source_order_and_components(self) -> None:
        state = runner.load_partitions(self.config)
        self.assertEqual(len(state["all"]), 3360)
        for fold_id, partition in state["partitions"].items():
            self.assertEqual(len(partition["training"]), 2688, fold_id)
            self.assertEqual(len(partition["heldout"]), 672, fold_id)
            self.assertFalse(
                {row["component_id"] for row in partition["training"]}
                & {row["component_id"] for row in partition["heldout"]}
            )

    def test_m1_scheduler_preserves_five_epoch_horizon_and_four_epoch_stop(self) -> None:
        self.assertEqual(
            runner.m1_schedule(self.config, 2688),
            {
                "steps_per_epoch": 168,
                "planned_scheduler_epochs": 5,
                "scheduler_horizon_steps": 840,
                "warmup_steps": 84,
                "selected_stop_epoch": 4,
                "selected_stop_steps": 672,
            },
        )

    def test_m3_step_count_is_two_complete_epochs_per_fold(self) -> None:
        self.assertEqual(self.config["execution"]["m3_epochs"], 2)
        self.assertEqual(2688 * self.config["execution"]["m3_epochs"], 5376)
        self.assertEqual(self.config["m3"]["expected_insertion_points"], 112)
        self.assertEqual(self.config["m3"]["expected_total_trainable_parameters"], 7_355_398)

    def test_verified_dry_run_is_a_hard_prerequisite(self) -> None:
        prerequisites = runner.verify_prerequisites(self.config)
        self.assertEqual(prerequisites["m1_run"]["selection"]["selected_epoch"], 4)
        self.assertEqual(prerequisites["m3_run"]["selection"]["selected_epoch"], 2)
        verification = runner.load_json_record(self.config["prerequisites"]["dry_run_verification"])
        self.assertEqual(verification["status"], "Passed")
        self.assertEqual(verification["passed_count"], 114)

    def test_public_privacy_scanner_rejects_row_level_fields(self) -> None:
        self.assertEqual(runner.public_sensitive_paths({"label_order": ["love"]}), [])
        self.assertEqual(
            runner.public_sensitive_paths({"safe": {"sample_ids": ["x"], "logits": [[0.1]]}}),
            ["$.safe.sample_ids", "$.safe.logits"],
        )

    def test_runner_has_no_top_level_model_library_imports(self) -> None:
        tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
        imports = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[0])
        self.assertFalse({"mlx", "mlx_lm", "numpy", "torch", "transformers"} & set(imports))

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
        self.assertNotIn("run_exp058_oof_production", source)


if __name__ == "__main__":
    unittest.main()
