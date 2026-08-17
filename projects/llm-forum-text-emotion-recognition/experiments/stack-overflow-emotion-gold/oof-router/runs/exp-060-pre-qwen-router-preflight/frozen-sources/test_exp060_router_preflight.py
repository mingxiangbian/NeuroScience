from __future__ import annotations

import ast
import importlib.util
import inspect
import json
from pathlib import Path
import unittest

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp060_router_preflight.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp060_router_preflight.py"
CONFIG_PATH = MODULE_DIR / "configs" / "exp-060-router-preflight.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_module("exp060_preflight_runner_under_test", RUNNER_PATH)


class Exp060PreflightContractTests(unittest.TestCase):
    def test_feature_builder_has_only_pre_qwen_inputs(self) -> None:
        parameters = tuple(inspect.signature(runner.build_pre_qwen_features).parameters)
        self.assertEqual(
            parameters,
            ("m1_probabilities", "m1_thresholds", "character_lengths", "m1_token_lengths"),
        )

    def test_feature_builder_freezes_shape_order_and_values(self) -> None:
        probabilities = np.asarray(
            [
                [0.9, 0.2, 0.1, 0.4, 0.3, 0.05],
                [0.1, 0.8, 0.2, 0.3, 0.4, 0.6],
            ],
            dtype=np.float64,
        )
        matrix, names = runner.build_pre_qwen_features(
            probabilities,
            np.asarray([0.31, 0.32]),
            np.asarray([120, 240]),
            np.asarray([30, 60]),
        )
        self.assertEqual(matrix.shape, (2, 14))
        self.assertEqual(names, runner.FEATURE_NAMES)
        np.testing.assert_allclose(matrix[:, :6], probabilities)
        np.testing.assert_allclose(matrix[:, 9], [2, 3])
        np.testing.assert_allclose(matrix[:, 10], [0.9, 0.8])
        np.testing.assert_allclose(matrix[:, 11], [0.05, 0.1])
        np.testing.assert_allclose(matrix[:, 12:], [[120, 30], [240, 60]])

    def test_router_target_uses_whole_vector_and_ties_choose_m1(self) -> None:
        gold = np.asarray([[1, 0], [1, 1], [0, 0]], dtype=np.uint8)
        m1 = np.asarray([[1, 0], [1, 0], [0, 1]], dtype=np.uint8)
        m3 = np.asarray([[1, 0], [1, 1], [1, 0]], dtype=np.uint8)
        target = runner.build_router_target(m1, m3, gold)
        np.testing.assert_array_equal(target, [0, 1, 0])

    def test_cutoff_is_fit_only_from_meta_train_scores(self) -> None:
        train = np.asarray([0.1, 0.2, 0.3, 0.4])
        cutoff = runner.score_cutoff(train, 0.25)
        self.assertEqual(cutoff, 0.4)
        heldout_a = runner.apply_score_cutoff(np.asarray([0.39, 0.41]), cutoff)
        heldout_b = runner.apply_score_cutoff(np.asarray([-100.0, 100.0]), cutoff)
        np.testing.assert_array_equal(heldout_a, [0, 1])
        np.testing.assert_array_equal(heldout_b, [0, 1])

    def test_config_freezes_scope_features_and_router(self) -> None:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(tuple(config["feature_contract"]["ordered_features"]), runner.FEATURE_NAMES)
        self.assertFalse(config["router"]["hyperparameter_search"])
        self.assertEqual(config["router"]["logistic_regression"]["C"], 1.0)
        self.assertTrue(config["cross_fitting"]["nested_threshold_recomputation"])
        self.assertEqual(config["cross_fitting"]["outer_fold_ids"], [0, 1, 2, 3, 4])

    def test_config_forbids_results_and_protected_access(self) -> None:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        for key in (
            "formal_router_training",
            "formal_result_computation",
            "validation_access",
            "test_access",
            "model_loading_or_forward",
            "raw_text_access",
        ):
            self.assertFalse(config["authorization"][key], key)

    def test_verifier_does_not_import_runner(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertNotIn("run_exp060_router_preflight", source)
        self.assertFalse(any(name.endswith("run_exp060_router_preflight") for name in imports))


if __name__ == "__main__":
    unittest.main()
