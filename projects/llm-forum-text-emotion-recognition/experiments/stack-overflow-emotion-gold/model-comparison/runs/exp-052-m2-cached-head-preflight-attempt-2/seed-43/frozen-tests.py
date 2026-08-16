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


runner = load_module("so_exp052_cached_runner", "run_exp052_m2_cached_head.py")
verifier = load_module("so_exp052_cached_verifier", "verify_exp052_m2_cached_head.py")


class CachedHeadContractTests(unittest.TestCase):
    def test_cache_loader_is_read_only_and_rejects_hash_drift(self):
        with tempfile.TemporaryDirectory(dir=MODULE_DIR) as temporary:
            path = Path(temporary) / "features.npy"
            np.save(path, np.arange(12, dtype=np.float32).reshape(2, 6), allow_pickle=False)
            record = runner.artifact(path)
            values, metadata = runner.load_cache(
                record, {"shape": [2, 6]}
            )
            self.assertIsInstance(values, np.memmap)
            self.assertFalse(values.flags.writeable)
            self.assertEqual(metadata["mmap_mode"], "r")
            np.save(path, np.zeros((2, 6), dtype=np.float32), allow_pickle=False)
            with self.assertRaises(ValueError):
                runner.load_cache(record, {"shape": [2, 6]})

    def test_split_loaders_reject_unlisted_split(self):
        with self.assertRaises(PermissionError):
            runner.load_split_rows({}, "test")
        with self.assertRaises(PermissionError):
            verifier.load_split_rows({}, "test")

    def test_gate_flattened_cache_record_is_normalized(self):
        flattened = {
            "path": "private/features.npy",
            "bytes": 128,
            "sha256": "abc",
            "shape": [2, 6],
            "dtype": "float32",
        }
        self.assertEqual(
            runner.compact_artifact(flattened),
            {"path": "private/features.npy", "bytes": 128, "sha256": "abc"},
        )

    def test_cached_runner_has_no_qwen_load_path(self):
        audit = verifier.source_access_audit(MODULE_DIR / "run_exp052_m2_cached_head.py")
        self.assertTrue(all(audit.values()), audit)

    def test_batch_orders_are_seeded_deterministic_and_seed_specific(self):
        first = runner.make_batch_orders(43, 20, 2)
        second = runner.make_batch_orders(43, 20, 2)
        seed_42 = runner.make_batch_orders(42, 20, 2)
        self.assertTrue(np.array_equal(first, second))
        self.assertFalse(np.array_equal(first, seed_42))
        for order in first:
            self.assertEqual(sorted(order.tolist()), list(range(20)))

    def test_protocol_authorizes_only_seed_43_cached_head(self):
        protocol = (
            MODULE_DIR.parent
            / "protocols"
            / "exp-052-seed-43-cache-reuse-authorization.md"
        ).read_text(encoding="utf-8")
        self.assertIn("exactly", protocol)
        self.assertIn("seed 44", protocol)
        self.assertIn("does not authorize Stack Overflow test access", protocol)
        self.assertIn("Qwen model is not loaded", protocol)

    def test_config_authorization_when_frozen(self):
        paths = sorted((MODULE_DIR / "configs").glob("exp-052-m2-seed-43-cache-*.json"))
        if not paths:
            self.skipTest("Seed-43 configs are frozen after implementation hashes exist")
        for path in paths:
            config = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(config["experiment_id"], "EXP-052")
            self.assertEqual(config["authorization"]["seeds"], [43])
            self.assertEqual(config["authorization"]["splits"], ["train", "validation"])
            self.assertFalse(config["authorization"]["test_access"])
            self.assertFalse(config["authorization"]["seed_44_authorized"])
            self.assertFalse(config["authorization"]["exp_053_054_authorized"])

    def test_metric_and_selection_logic_remains_matched(self):
        gold = np.asarray([[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0]], dtype=np.uint8)
        probabilities = np.asarray([[0.8, 0.2, 0.1, 0.1, 0.1, 0.1], [0.2, 0.8, 0.1, 0.1, 0.1, 0.1]], dtype=np.float32)
        observed = runner.head_common.metric_bundle(gold, (probabilities >= 0.5).astype(np.uint8))
        independent = verifier.prior_verifier.metric_bundle(gold, (probabilities >= 0.5).astype(np.uint8))
        self.assertEqual(observed, independent)


if __name__ == "__main__":
    unittest.main()
