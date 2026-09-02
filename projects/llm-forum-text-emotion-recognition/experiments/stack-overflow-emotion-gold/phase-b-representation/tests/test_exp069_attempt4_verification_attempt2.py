from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import unittest

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]
VERIFIER_PATH = MODULE_DIR / "verify_exp069_attempt4_verification_attempt2.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFIER = load("exp069_verification_attempt2_tests", VERIFIER_PATH)


class Exp069VerificationAttempt2Tests(unittest.TestCase):
    def test_scope_is_model_free_recovery_only(self) -> None:
        config = VERIFIER.load_config(VERIFIER.DEFAULT_CONFIG)
        self.assertEqual(
            config["scope"],
            {
                "verification_only": True,
                "model_rerun": False,
                "assemble_rerun": False,
                "source_mutation": False,
                "exp070": False,
            },
        )
        self.assertFalse(config["authorization"]["model_loading_authorized"])
        self.assertFalse(config["authorization"]["forward_authorized"])
        self.assertFalse(config["authorization"]["validation_access"])
        self.assertFalse(config["authorization"]["test_access"])

    def test_all_frozen_records_match(self) -> None:
        config = VERIFIER.load_config(VERIFIER.DEFAULT_CONFIG)
        VERIFIER.require_config_records(config)

    def test_source_failure_and_snapshot_are_bound(self) -> None:
        config = VERIFIER.load_config(VERIFIER.DEFAULT_CONFIG)
        _, _, run, failure = VERIFIER.validate_source_snapshot(config)
        self.assertEqual(run["status"], "CompletedAwaitingVerification")
        self.assertEqual(run["max_errors"]["manual_logit"], 0.0)
        self.assertEqual(failure["status"], "Failed")
        self.assertEqual(failure["error_type"], "ValueError")

    def test_metric_names_and_tolerances_are_separate(self) -> None:
        config = VERIFIER.load_config(VERIFIER.DEFAULT_CONFIG)
        self.assertEqual(config["metrics"]["aggregate_equality_atol"], 1e-12)
        self.assertEqual(config["metrics"]["manual_logit_atol"], 1e-5)
        self.assertNotEqual(
            config["metrics"]["runner_metric"],
            config["metrics"]["independent_metric"],
        )

    def test_synthetic_metrics_do_not_collide(self) -> None:
        manual = np.asarray([[1.0]], dtype=np.float32)
        standard = manual.copy()
        replay = np.asarray([[1.0 + 5e-6]], dtype=np.float32)
        runner_metric = float(np.max(np.abs(manual - standard)))
        independent_metric = float(np.max(np.abs(replay - manual)))
        self.assertEqual(runner_metric, 0.0)
        self.assertGreater(independent_metric, 0.0)
        self.assertLessEqual(independent_metric, 1e-5)

    def test_frozen_transform_keeps_strict_aggregate_equality(self) -> None:
        config = VERIFIER.load_config(VERIFIER.DEFAULT_CONFIG)
        source_path = VERIFIER.require_record(config["frozen_verifiers"]["source_verifier"])
        transformed, digest = VERIFIER.transform_source_verifier(source_path)
        self.assertEqual(len(digest), 64)
        self.assertFalse(transformed.math_isclose(0.0, 1e-11))

    def test_recovery_verifier_has_no_model_or_runner_import(self) -> None:
        tree = ast.parse(VERIFIER_PATH.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertFalse({"mlx", "mlx_lm", "torch", "transformers"} & imports)
        self.assertNotIn("run_exp069_fold_smoke_attempt4", VERIFIER_PATH.read_text())

    def test_recovery_output_namespace_is_fresh_and_separate(self) -> None:
        config = VERIFIER.load_config(VERIFIER.DEFAULT_CONFIG)
        self.assertEqual(config["outputs"]["recovery_public_root"], VERIFIER.RECOVERY_PUBLIC_ROOT)
        self.assertNotEqual(
            config["outputs"]["recovery_public_root"],
            config["outputs"]["source_public_root"],
        )


if __name__ == "__main__":
    unittest.main()
