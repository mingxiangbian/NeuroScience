from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, MODULE_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = load_module("so_exp052_cache_runner", "run_exp052_cache_reuse_gate.py")
verifier = load_module("so_exp052_cache_verifier", "verify_exp052_cache_reuse_gate.py")


class CacheContractTests(unittest.TestCase):
    def test_cache_is_loaded_as_read_only_float32_mmap(self):
        with tempfile.TemporaryDirectory(dir=MODULE_DIR) as temporary:
            path = Path(temporary) / "features.npy"
            values = np.arange(24, dtype=np.float32).reshape(4, 6)
            np.save(path, values, allow_pickle=False)
            record = runner.artifact(path)
            observed, metadata = runner.validate_cache_array(
                record, expected_shape=(4, 6)
            )
            self.assertIsInstance(observed, np.memmap)
            self.assertFalse(observed.flags.writeable)
            self.assertEqual(observed.dtype, np.float32)
            self.assertEqual(metadata["mmap_mode"], "r")
            self.assertFalse(metadata["writeable"])

    def test_cache_hash_drift_is_rejected_before_use(self):
        with tempfile.TemporaryDirectory(dir=MODULE_DIR) as temporary:
            path = Path(temporary) / "features.npy"
            np.save(path, np.ones((2, 3), dtype=np.float32), allow_pickle=False)
            record = runner.artifact(path)
            np.save(path, np.zeros((2, 3), dtype=np.float32), allow_pickle=False)
            with self.assertRaises(ValueError):
                runner.validate_cache_array(record, expected_shape=(2, 3))

    def test_gate_loaders_reject_test_split(self):
        with self.assertRaises(PermissionError):
            runner.load_split_rows({}, "test")
        with self.assertRaises(PermissionError):
            verifier.load_split_rows({}, "test")

    def test_gate_sources_have_static_train_validation_only_boundary(self):
        for filename in (
            "run_exp052_cache_reuse_gate.py",
            "verify_exp052_cache_reuse_gate.py",
        ):
            audit = verifier.source_access_audit(MODULE_DIR / filename)
            self.assertTrue(all(audit.values()), {filename: audit})

    def test_protocol_forbids_cross_model_reuse_and_new_training(self):
        protocol = (
            MODULE_DIR.parent
            / "protocols"
            / "exp-052-feature-cache-reuse-gate.md"
        ).read_text(encoding="utf-8")
        self.assertIn("不得用于 EXP-053/M3、EXP-054/M4", protocol)
        self.assertIn("只读 mmap", protocol)
        self.assertIn("不授权 seeds 43/44", protocol)

    def test_machine_contract_binds_verified_seed_42_without_authorizing_consumers(self):
        config = json.loads(
            (
                MODULE_DIR
                / "configs"
                / "exp-052-m2-feature-cache-reuse-gate.json"
            ).read_text(encoding="utf-8")
        )
        authorization = config["authorization"]
        self.assertEqual(config["stage"], "feature-cache-reuse-integrity-gate")
        self.assertEqual(authorization["source_seed"], 42)
        self.assertEqual(authorization["candidate_consumers"], [43, 44])
        self.assertFalse(authorization["consumer_seeds_authorized"])
        self.assertFalse(authorization["training_authorized"])
        self.assertFalse(authorization["performance_metrics_authorized"])
        self.assertFalse(authorization["test_access"])
        source_verification = json.loads(
            runner.resolve_project(config["source_seed_42"]["verification"]["path"])
            .read_text(encoding="utf-8")
        )
        self.assertEqual(source_verification["status"], "Passed")
        self.assertEqual(source_verification["check_count"], 70)
        self.assertFalse(source_verification["test_split_accessed"])

    def test_machine_contract_cache_records_match_source_run(self):
        config = json.loads(
            (
                MODULE_DIR
                / "configs"
                / "exp-052-m2-feature-cache-reuse-gate.json"
            ).read_text(encoding="utf-8")
        )
        source_run = json.loads(
            runner.resolve_project(config["source_seed_42"]["run"]["path"])
            .read_text(encoding="utf-8")
        )
        for split in runner.ALLOWED_SPLITS:
            expected = config["feature_cache"][split]
            self.assertEqual(
                expected["artifact"],
                source_run["artifacts"][f"{split}_features_private"],
            )
            self.assertEqual(
                expected["sample_order_sha256"],
                source_run["feature_cache"][split]["sample_order_sha256"],
            )
            self.assertEqual(
                expected["token_id_stream_sha256"],
                source_run["feature_cache"][split]["token_id_stream_sha256"],
            )


if __name__ == "__main__":
    unittest.main()
