from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp059_calibration.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp059_calibration.py"
PREFLIGHT_CONFIG = MODULE_DIR / "configs" / "exp-059-preflight.json"
FORMAL_CONFIG = MODULE_DIR / "configs" / "exp-059-calibration-selective-prediction.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_module("exp059_runner_under_test", RUNNER_PATH)


class Exp059ContractTests(unittest.TestCase):
    def test_temperature_fit_improves_a_deterministic_synthetic_case(self) -> None:
        logits = np.asarray([[0.4], [-0.4], [0.6], [-0.6]], dtype=np.float64)
        gold = np.asarray([[1], [0], [1], [0]], dtype=np.uint8)
        fit = runner.fit_temperature(logits, gold, (0.05, 20.0), 1e-12, 1000)
        self.assertTrue(fit["success"])
        self.assertLess(fit["objective_nll"], runner.bce_with_logits(logits, gold))

    def test_threshold_tie_prefers_closest_to_half_then_lower(self) -> None:
        probabilities = np.asarray([[0.0], [0.0]], dtype=np.float64)
        gold = np.asarray([[0], [0]], dtype=np.uint8)

        def one_label_metrics(y, prediction):
            return {
                "macro_f1": 0.0,
                "hamming_loss": float(np.mean(y != prediction)),
            }

        original = runner.classification_metrics
        try:
            runner.classification_metrics = one_label_metrics
            selected = runner.select_threshold(probabilities, gold, [0.4, 0.6])
        finally:
            runner.classification_metrics = original
        self.assertEqual(selected["threshold"], 0.4)

    def test_acceptance_mask_rounds_each_fold_independently(self) -> None:
        scores = np.asarray([0.4, 0.1, 0.3, 0.2, 0.8, 0.5, 0.7, 0.6])
        folds = np.asarray([0, 0, 0, 0, 1, 1, 1, 1], dtype=np.int8)
        sample_ids = np.asarray([f"s{index}" for index in range(8)])
        mask = runner.acceptance_mask(scores, folds, sample_ids, 0.5)
        self.assertEqual(int(np.sum(mask[folds == 0])), 2)
        self.assertEqual(int(np.sum(mask[folds == 1])), 2)
        self.assertEqual(int(np.sum(mask)), 4)

    def test_equal_frequency_bins_cover_every_bit_once(self) -> None:
        probabilities = np.linspace(0.01, 0.99, 30).reshape(10, 3)
        gold = (probabilities >= 0.5).astype(np.uint8)
        _, rows = runner.equal_frequency_bins(probabilities, gold, 7)
        self.assertEqual(len(rows), 7)
        self.assertEqual(sum(row["count"] for row in rows), 30)

    def test_public_scanner_allows_schema_names_but_rejects_row_values(self) -> None:
        schema = runner.public_schema_records(runner.expected_input_schema())
        self.assertEqual(runner.public_sensitive_paths({"input_schema": schema}), [])
        self.assertEqual(
            runner.public_sensitive_paths({"private": {"sample_ids": ["x"], "gold": [[1]]}}),
            ["$.private.sample_ids", "$.private.gold"],
        )

    def test_verifier_does_not_import_runner(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertNotIn("run_exp059_calibration", source)
        self.assertFalse(any(name.endswith("run_exp059_calibration") for name in imports))

    def test_frozen_configs_forbid_validation_and_test(self) -> None:
        self.assertTrue(PREFLIGHT_CONFIG.is_file())
        paths = [PREFLIGHT_CONFIG]
        if FORMAL_CONFIG.is_file():
            paths.append(FORMAL_CONFIG)
        for path in paths:
            config = json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(config["authorization"]["validation_access"], path)
            self.assertFalse(config["authorization"]["test_access"], path)
            self.assertEqual(config["cross_fitting"]["fold_ids"], [0, 1, 2, 3, 4])
            self.assertEqual(config["bootstrap"]["repetitions"], 2000)
            self.assertEqual(config["selective_prediction"]["random_repetitions"], 100)


if __name__ == "__main__":
    unittest.main()
