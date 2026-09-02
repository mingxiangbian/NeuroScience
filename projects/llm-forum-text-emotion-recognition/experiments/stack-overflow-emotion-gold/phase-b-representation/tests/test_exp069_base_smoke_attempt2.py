from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp069_base_smoke_attempt2.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp069_base_smoke_attempt2.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load("exp069_base_runner_tests", RUNNER_PATH)
VERIFIER = load("exp069_base_verifier_tests", VERIFIER_PATH)


class Exp069BaseSmokeAttempt2Tests(unittest.TestCase):
    def test_config_authorizes_base_only(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        authorization = config["authorization"]
        self.assertTrue(authorization["base_smoke_authorized"])
        self.assertTrue(authorization["model_loading_authorized"])
        self.assertTrue(authorization["forward_authorized"])
        self.assertFalse(authorization["fold_smoke_authorized"])
        self.assertFalse(authorization["assemble_authorized"])
        self.assertFalse(authorization["training_authorized"])
        self.assertFalse(authorization["validation_access"])
        self.assertFalse(authorization["test_access"])

    def test_parent_static_records_are_exact(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        for record in config["parent_static"].values():
            RUNNER.require_record(record)
            VERIFIER.require_record(record)
        parent_verification = VERIFIER.strict_json(
            VERIFIER.require_record(config["parent_static"]["static_verification"])
        )
        self.assertEqual(parent_verification["status"], "Passed")
        self.assertEqual(parent_verification["passed_count"], 14)

    def test_verifier_is_independent_and_model_free(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertFalse({"mlx", "mlx_lm", "torch", "transformers", "safetensors"} & imports)
        self.assertNotIn("run_exp069", source)

    def test_runner_model_imports_are_lazy(self) -> None:
        tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
        imports = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertFalse({"mlx", "mlx_lm", "torch", "transformers", "safetensors"} & imports)

    def test_public_privacy(self) -> None:
        self.assertEqual(RUNNER.public_sensitive_paths({"status": "Passed"}), [])
        self.assertTrue(RUNNER.public_sensitive_paths({"ordinal": 1}))
        self.assertTrue(VERIFIER.public_sensitive_paths({"hidden_states": []}))

    def test_numeric_comparison(self) -> None:
        left = np.asarray([0.0, 1.0], dtype=np.float32)
        right = np.asarray([0.0, 1.0 + 1e-6], dtype=np.float32)
        self.assertLessEqual(VERIFIER.max_abs(left, right), 1e-5)
        with self.assertRaises(ValueError):
            VERIFIER.max_abs(left, np.asarray([[0.0, 1.0]], dtype=np.float32))

    def test_base_npz_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "base.npz"
            arrays = {
                "ordinal": np.asarray(VERIFIER.ORDINALS, dtype=np.int32),
                "fold_id": np.zeros(32, dtype=np.int8),
                "token_length": np.ones(32, dtype=np.int16),
                "standard_hf": np.zeros((32, 2560), dtype=np.float32),
            }
            arrays.update(
                {key: np.zeros((32, 2560), dtype=np.float32) for key in VERIFIER.POINT_KEYS.values()}
            )
            np.savez(path, **arrays)
            os.chmod(path, 0o600)
            observed = VERIFIER.load_base_npz(path)
            self.assertEqual(set(observed), set(arrays))
            bad = Path(directory) / "bad.npz"
            np.savez(bad, **{key: value for key, value in arrays.items() if key != "hf"})
            os.chmod(bad, 0o600)
            with self.assertRaises(ValueError):
                VERIFIER.load_base_npz(bad)

    def test_resource_gates(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        good = {"elapsed_seconds": 10.0, "mlx_peak_bytes": 8_000_000_000, "ru_maxrss_gb": 1.0}
        VERIFIER.validate_resources(good, config)
        bad = dict(good)
        bad["mlx_peak_bytes"] = 10_000_000_001
        with self.assertRaises(ValueError):
            VERIFIER.validate_resources(bad, config)

    def test_fold_mapping_token_length_and_digests(self) -> None:
        base = {
            "fold_id": np.zeros(32, dtype=np.int8),
            "token_length": np.ones(32, dtype=np.int16),
        }
        manifest = {
            "rows": [
                {"ordinal": ordinal, "fold_id": 0}
                for ordinal in VERIFIER.ORDINALS
            ]
        }
        worker = {
            "token_stream_sha256": "a" * 64,
            "fold_token_stream_sha256": {str(fold): "b" * 64 for fold in range(5)},
        }
        VERIFIER.validate_base_metadata(base, manifest, worker)
        bad = dict(base)
        bad["token_length"] = np.zeros(32, dtype=np.int16)
        with self.assertRaises(ValueError):
            VERIFIER.validate_base_metadata(bad, manifest, worker)
        wrong_shape = dict(base)
        wrong_shape["token_length"] = np.ones((32, 1), dtype=np.int16)
        with self.assertRaises(ValueError):
            VERIFIER.validate_base_metadata(wrong_shape, manifest, worker)
        wrong_fold = dict(base)
        wrong_fold["fold_id"] = np.ones(32, dtype=np.int8)
        with self.assertRaises(ValueError):
            VERIFIER.validate_base_metadata(wrong_fold, manifest, worker)

    def test_claim_scope_tamper_is_rejected(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        current = RUNNER.observed_artifact(RUNNER.DEFAULT_CONFIG)
        claim = {
            "schema_version": "exp-069-base-smoke-claim-v1",
            "experiment_id": "EXP-069",
            "attempt_id": "attempt-2-base-smoke",
            "status": "Claimed",
            "config": current,
            "parent_static_verification": config["parent_static"]["static_verification"],
            "authorized_stage": "base-smoke",
            "fold_smoke_authorized": False,
            "assemble_authorized": False,
            "claim_boundary": config["claim_boundary"],
        }
        VERIFIER.validate_claim(claim, config, current)
        changed = dict(claim)
        changed["fold_smoke_authorized"] = True
        with self.assertRaises(ValueError):
            VERIFIER.validate_claim(changed, config, current)


if __name__ == "__main__":
    unittest.main()
