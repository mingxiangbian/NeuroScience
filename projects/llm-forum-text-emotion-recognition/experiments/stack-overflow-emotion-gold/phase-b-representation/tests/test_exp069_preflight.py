from __future__ import annotations

import ast
import importlib.util
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
import warnings
import zipfile

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp069_preflight.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp069_preflight.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load("exp069_runner_tests", RUNNER_PATH)
VERIFIER = load("exp069_verifier_tests", VERIFIER_PATH)


class FakeLayer:
    def __init__(self, value: float) -> None:
        self.value = value

    def __call__(self, hidden, mask, cache):
        return hidden + self.value


class FakeCore:
    def __init__(self) -> None:
        self.layers = [FakeLayer(float(index + 1)) for index in range(36)]

    def embed_tokens(self, input_ids):
        return np.asarray(input_ids, dtype=np.float32)[..., None] * np.ones((1, 1, 2), dtype=np.float32)

    def norm(self, hidden):
        return hidden * 2.0

    def __call__(self, input_ids):
        hidden = self.embed_tokens(input_ids)
        for layer in self.layers:
            hidden = layer(hidden, None, None)
        return self.norm(hidden)


class FakeBackbone:
    def __init__(self) -> None:
        self.model = FakeCore()


class Exp069ContractTests(unittest.TestCase):
    def test_smoke_ordinals_are_exact(self) -> None:
        expected = [
            0, 108, 217, 325, 433, 542, 650, 758,
            867, 975, 1084, 1192, 1300, 1409, 1517, 1625,
            1734, 1842, 1950, 2059, 2167, 2275, 2384, 2492,
            2601, 2709, 2817, 2926, 3034, 3142, 3251, 3359,
        ]
        self.assertEqual(RUNNER.smoke_ordinals(), expected)
        self.assertEqual(tuple(expected), VERIFIER.ORDINALS)

    def test_default_config_is_static_only(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        self.assertTrue(config["authorization"]["design_authorized"])
        self.assertTrue(config["authorization"]["static_execution_authorized"])
        self.assertFalse(config["authorization"]["smoke_execution_authorized"])
        RUNNER.require_stage_authorized(config, "static")
        with self.assertRaises(PermissionError):
            RUNNER.require_stage_authorized(config, "base-smoke")

    def test_verifier_is_independent_and_model_free(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse({"mlx", "mlx_lm", "torch", "transformers", "safetensors"} & imported)
        self.assertNotIn("run_exp069", source)

    def test_runner_has_no_top_level_model_import(self) -> None:
        tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
        top_level = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                top_level.update(alias.name.split(".")[0] for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                top_level.add(node.module.split(".")[0])
        self.assertFalse({"mlx", "mlx_lm", "torch", "transformers", "safetensors"} & top_level)

    def test_strict_json_rejects_duplicate_and_nonfinite(self) -> None:
        with self.assertRaises(ValueError):
            RUNNER.strict_json_bytes(b'{"a":1,"a":2}')
        with self.assertRaises(ValueError):
            VERIFIER.strict_json_bytes(b'{"a":NaN}')

    def test_public_privacy_scanner(self) -> None:
        self.assertEqual(RUNNER.public_sensitive_paths({"status": "Passed"}), [])
        self.assertTrue(RUNNER.public_sensitive_paths({"rows": [{"ordinal": 1}]}))
        self.assertTrue(VERIFIER.public_sensitive_paths({"logits": []}))

    def test_config_binding_rejects_post_static_drift(self) -> None:
        record = RUNNER.artifact(RUNNER.DEFAULT_CONFIG)
        RUNNER.require_config_binding(RUNNER.DEFAULT_CONFIG, record)
        VERIFIER.require_config_binding(VERIFIER.DEFAULT_CONFIG, record)
        changed = dict(record)
        changed["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            RUNNER.require_config_binding(RUNNER.DEFAULT_CONFIG, changed)
        with self.assertRaises(ValueError):
            VERIFIER.require_config_binding(VERIFIER.DEFAULT_CONFIG, changed)

    def test_access_attestation_rejects_forbidden_flip(self) -> None:
        expected = {
            "validation_accessed": False,
            "test_accessed": False,
            "performance_metrics_computed": False,
        }
        VERIFIER.require_exact_access(dict(expected), expected, "Synthetic")
        changed = dict(expected)
        changed["test_accessed"] = True
        with self.assertRaises(ValueError):
            VERIFIER.require_exact_access(changed, expected, "Synthetic")

    def test_manual_residual_points_preserve_raw_points(self) -> None:
        backbone = FakeBackbone()
        points, standard = RUNNER.manual_residual_points(
            backbone, np.asarray([[3]], dtype=np.int32), lambda hidden, cache: None
        )
        self.assertEqual(tuple(points), RUNNER.POINTS)
        self.assertTrue(np.array_equal(points["H-1"], np.asarray([[3.0, 3.0]])))
        self.assertTrue(np.array_equal(points["H7"], np.asarray([[39.0, 39.0]])))
        self.assertTrue(np.array_equal(points["H35"], np.asarray([[669.0, 669.0]])))
        self.assertTrue(np.array_equal(points["HF"], np.asarray([[1338.0, 1338.0]])))
        self.assertTrue(np.array_equal(points["HF"], standard))
        self.assertFalse(np.array_equal(points["H35"], points["HF"]))

    def test_max_abs_boundary_and_shape(self) -> None:
        left = np.asarray([0.0, 1.0], dtype=np.float32)
        right = np.asarray([0.0, 1.0 + 1e-6], dtype=np.float32)
        self.assertLessEqual(RUNNER.max_abs(left, right), 1e-5)
        with self.assertRaises(ValueError):
            VERIFIER.max_abs(left, right.reshape(1, 2))

    def test_safe_path_rejects_parent_and_symlink(self) -> None:
        original_runner_root = RUNNER.PROJECT_ROOT
        original_verifier_root = VERIFIER.PROJECT_ROOT
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "value.json"
            target.write_text("{}", encoding="utf-8")
            linked = root / "linked.json"
            linked.symlink_to(target)
            RUNNER.PROJECT_ROOT = root
            VERIFIER.PROJECT_ROOT = root
            try:
                with self.assertRaises(ValueError):
                    RUNNER.resolve_project("../value.json")
                with self.assertRaises(ValueError):
                    VERIFIER.resolve_project("linked.json")
            finally:
                RUNNER.PROJECT_ROOT = original_runner_root
                VERIFIER.PROJECT_ROOT = original_verifier_root

    def test_private_npz_exact_schema_and_object_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "value.npz"
            np.savez(path, value=np.asarray([1], dtype=np.int32))
            os.chmod(path, 0o600)
            observed = VERIFIER.load_private_npz(path, {"value"})
            self.assertEqual(observed["value"].tolist(), [1])
            with self.assertRaises(ValueError):
                VERIFIER.load_private_npz(path, {"different"})
            object_path = Path(directory) / "object.npz"
            np.savez(object_path, value=np.asarray([{"a": 1}], dtype=object))
            os.chmod(object_path, 0o600)
            with self.assertRaises(ValueError):
                VERIFIER.load_private_npz(object_path, {"value"})

    def test_duplicate_npz_member_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.npz"
            payload = b"not-a-valid-npy"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr("value.npy", payload)
                    archive.writestr("value.npy", payload)
            os.chmod(path, 0o600)
            with self.assertRaises(ValueError):
                VERIFIER.load_private_npz(path, {"value"})

    def test_historical_loader_does_not_access_gold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "historical.npz"
            np.savez(
                path,
                sample_ids=np.asarray(["sample"], dtype="<U8"),
                fold_ids=np.asarray([0], dtype=np.int8),
                logits=np.zeros((1, 6), dtype=np.float32),
                gold=np.asarray([{"poison": True}], dtype=object),
            )
            observed = VERIFIER.load_historical_members(path)
            self.assertEqual(set(observed), {"sample_ids", "fold_ids", "logits"})

    def test_safetensors_f32_reader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "head.safetensors"
            weight = np.arange(12, dtype=np.float32).reshape(3, 4)
            bias = np.arange(3, dtype=np.float32)
            weight_bytes = weight.astype("<f4").tobytes()
            bias_bytes = bias.astype("<f4").tobytes()
            header = {
                "weight": {"dtype": "F32", "shape": [3, 4], "data_offsets": [0, len(weight_bytes)]},
                "bias": {
                    "dtype": "F32",
                    "shape": [3],
                    "data_offsets": [len(weight_bytes), len(weight_bytes) + len(bias_bytes)],
                },
            }
            header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
            path.write_bytes(struct.pack("<Q", len(header_bytes)) + header_bytes + weight_bytes + bias_bytes)
            observed = VERIFIER.read_safetensors_f32(path, {"weight", "bias"})
            self.assertTrue(np.array_equal(observed["weight"], weight))
            self.assertTrue(np.array_equal(observed["bias"], bias))


if __name__ == "__main__":
    unittest.main()
