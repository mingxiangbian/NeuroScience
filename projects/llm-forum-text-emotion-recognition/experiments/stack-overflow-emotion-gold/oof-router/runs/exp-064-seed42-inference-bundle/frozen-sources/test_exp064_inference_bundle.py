from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp064_inference_bundle.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp064_inference_bundle.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load("exp064_runner_tests", RUNNER_PATH)
VERIFIER = load("exp064_verifier_tests", VERIFIER_PATH)


class Exp064InferenceBundleTests(unittest.TestCase):
    def test_frozen_orders_and_schemas(self) -> None:
        self.assertEqual(RUNNER.LABEL_ORDER, VERIFIER.LABEL_ORDER)
        self.assertEqual(RUNNER.FEATURE_NAMES, VERIFIER.FEATURE_NAMES)
        self.assertEqual(len(RUNNER.LABEL_ORDER), 6)
        self.assertEqual(len(RUNNER.FEATURE_NAMES), 14)
        self.assertEqual(RUNNER.EXPECTED_INPUT_SCHEMA, VERIFIER.INPUT_SCHEMA)
        self.assertEqual(RUNNER.EXPECTED_BUNDLE_SCHEMA, VERIFIER.PARAMETER_SCHEMA)

    def test_stable_sigmoid_extremes_and_independent_agreement(self) -> None:
        values = np.asarray([-1000.0, -1.0, 0.0, 1.0, 1000.0])
        observed = RUNNER.stable_sigmoid(values)
        expected = VERIFIER.stable_sigmoid(values)
        self.assertTrue(np.array_equal(observed, expected))
        self.assertTrue(np.all(np.isfinite(observed)))
        self.assertEqual(observed[0], 0.0)
        self.assertEqual(observed[2], 0.5)
        self.assertEqual(observed[-1], 1.0)

    def test_threshold_ties_choose_closest_then_lower(self) -> None:
        probabilities = np.full((4, 6), 0.5, dtype=np.float64)
        all_zero = np.zeros((4, 6), dtype=np.uint8)
        grid = [value / 100.0 for value in range(5, 96)]
        self.assertEqual(RUNNER.select_threshold(probabilities, all_zero, grid), 0.51)
        self.assertEqual(VERIFIER.choose_threshold(probabilities, all_zero), 0.51)
        all_one = np.ones((4, 6), dtype=np.uint8)
        self.assertEqual(RUNNER.select_threshold(probabilities, all_one, grid), 0.5)
        self.assertEqual(VERIFIER.choose_threshold(probabilities, all_one), 0.5)

    def test_target_is_strict_m3_win_and_tie_to_m1(self) -> None:
        gold = np.asarray([[1, 0, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0]], dtype=np.uint8)
        m1 = np.asarray([[0, 0, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0]], dtype=np.uint8)
        m3 = np.asarray([[1, 0, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0]], dtype=np.uint8)
        expected = np.asarray([1, 0], dtype=np.uint8)
        self.assertTrue(np.array_equal(RUNNER.build_target(m1, m3, gold), expected))
        self.assertTrue(np.array_equal(VERIFIER.target(m1, m3, gold), expected))

    def test_feature_contract_entropy_margin_and_cardinality(self) -> None:
        probabilities = np.asarray(
            [[0.0, 1.0, 0.5, 0.49, 0.51, 0.2], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]],
            dtype=np.float64,
        )
        characters = np.asarray([12, 24], dtype=np.int32)
        tokens = np.asarray([4, 8], dtype=np.int32)
        left = RUNNER.build_features(probabilities, 0.5, characters, tokens)
        right = VERIFIER.features(probabilities, 0.5, characters, tokens)
        self.assertEqual(left.shape, (2, 14))
        self.assertTrue(np.all(np.isfinite(left)))
        self.assertTrue(np.allclose(left, right, rtol=0.0, atol=0.0))
        self.assertEqual(left[0, 8], 0.0)
        self.assertEqual(left[0, 9], 3.0)
        self.assertEqual(left[0, 12], 12.0)
        self.assertEqual(left[0, 13], 4.0)

    def test_cutoff_routes_all_ties(self) -> None:
        scores = np.asarray([0.9, 0.8, 0.8, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        cut = RUNNER.cutoff_for_rate(scores, 0.15)
        self.assertEqual(cut, 0.8)
        self.assertEqual(int(np.sum(scores >= cut)), 3)
        self.assertEqual(VERIFIER.cutoff(scores), 0.8)

    def test_canonical_json_rejects_nan(self) -> None:
        with self.assertRaises(ValueError):
            RUNNER.canonical_json_bytes({"value": float("nan")})
        value = {"z": 1, "a": True}
        payload = RUNNER.canonical_json_bytes(value)
        self.assertEqual(payload, b'{"a":true,"z":1}\n')
        self.assertEqual(payload, VERIFIER.canonical_json_bytes(value))

    def test_create_once_refuses_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.json"
            RUNNER._create_bytes_once(path, b"first", 0o600)
            with self.assertRaises(FileExistsError):
                RUNNER._create_bytes_once(path, b"second", 0o600)
            self.assertEqual(path.read_bytes(), b"first")
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_public_privacy_scanner(self) -> None:
        self.assertEqual(RUNNER.public_sensitive_paths({"status": "ok"}), [])
        self.assertTrue(RUNNER.public_sensitive_paths({"gold": [1, 0]}))
        self.assertTrue(VERIFIER.public_sensitive_paths({"route_scores": [0.5]}))

    def test_verifier_is_independent_and_pickle_free(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        forbidden = (
            "import run_exp064",
            "from run_exp064",
            "import run_exp060",
            "from run_exp060",
            "joblib",
            "pickle.load",
            "pickle.loads",
        )
        for value in forbidden:
            self.assertNotIn(value, source)

    def test_frozen_config_and_input_contract_load(self) -> None:
        config, sources = RUNNER.load_and_validate_config(RUNNER.DEFAULT_CONFIG)
        self.assertEqual(config["experiment_id"], "EXP-064")
        self.assertEqual(config["model_seed"], 42)
        self.assertEqual(config["outputs"]["public_dir"], str(RUNNER.PUBLIC_REL))
        self.assertEqual(config["outputs"]["private_dir"], str(RUNNER.PRIVATE_REL))
        self.assertEqual(RUNNER.npz_header_schema(sources["input"]), RUNNER.EXPECTED_INPUT_SCHEMA)

    def test_relative_frozen_config_path_is_normalized(self) -> None:
        relative = RUNNER.DEFAULT_CONFIG.relative_to(RUNNER.PROJECT_ROOT.parent.parent)
        previous = Path.cwd()
        try:
            os.chdir(RUNNER.PROJECT_ROOT.parent.parent)
            config, _ = RUNNER.load_and_validate_config(relative)
        finally:
            os.chdir(previous)
        self.assertEqual(config["experiment_id"], "EXP-064")


if __name__ == "__main__":
    unittest.main()
