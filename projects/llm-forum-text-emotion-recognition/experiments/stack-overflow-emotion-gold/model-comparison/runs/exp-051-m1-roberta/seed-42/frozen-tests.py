from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, MODULE_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = load_module("so_exp051_runner", "run_exp051_m1.py")
verifier = load_module("so_exp051_verifier", "verify_exp051_m1.py")


class SelectionTests(unittest.TestCase):
    def test_checkpoint_uses_strict_practical_tie_and_earliest_epoch(self):
        values = [0.60, 0.6049, 0.6051, 0.61, 0.609]
        history = [
            {"epoch": index + 1, "fixed_macro_f1": value}
            for index, value in enumerate(values)
        ]
        observed = runner.select_checkpoint(history, 0.005)
        independent = verifier.select_checkpoint(values, 0.005)
        self.assertEqual(observed, independent)
        self.assertEqual(observed["selected_epoch"], 3)
        self.assertEqual(observed["eligible_epochs"], [3, 4, 5])

    def test_threshold_ties_prefer_closest_to_half_then_lower(self):
        gold = np.asarray([[1, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]], dtype=np.uint8)
        probabilities = np.asarray(
            [[0.9, 0.1, 0.1, 0.1, 0.1, 0.1], [0.1, 0.1, 0.1, 0.1, 0.1, 0.1]],
            dtype=np.float32,
        )
        grid = [0.4, 0.5, 0.6]
        observed, rows = runner.select_threshold(gold, probabilities, grid)
        independent, independent_rows = verifier.select_threshold(gold, probabilities, grid)
        self.assertEqual(observed, 0.5)
        self.assertEqual(observed, independent)
        self.assertEqual(rows, independent_rows)


class MetricTests(unittest.TestCase):
    def test_metric_implementations_match(self):
        gold = np.asarray(
            [[1, 0, 0, 1, 0, 0], [0, 1, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]],
            dtype=np.uint8,
        )
        predicted = np.asarray(
            [[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]],
            dtype=np.uint8,
        )
        self.assertEqual(runner.metric_bundle(gold, predicted), verifier.metric_bundle(gold, predicted))

    def test_component_bootstrap_is_reproducible_and_independent(self):
        gold = np.asarray(
            [[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0], [0, 0, 0, 1, 0, 0]],
            dtype=np.uint8,
        )
        predicted = gold.copy()
        components = ["a", "a", "b"]
        first = runner.bootstrap_summary(gold, predicted, components, 42, 25, "unit", "fixed-0.5")
        second = verifier.bootstrap_summary(gold, predicted, components, 42, 25, "unit", "fixed-0.5")
        self.assertEqual(first, second)
        self.assertEqual(first["component_count"], 2)


class ContractTests(unittest.TestCase):
    def test_seed_42_only_and_test_denied(self):
        run_config, shared = runner.load_config(
            MODULE_DIR / "configs" / "exp-051-m1-roberta-seed-42.json", 42
        )
        self.assertEqual(run_config["authorization"]["seeds"], [42])
        self.assertFalse(run_config["authorization"]["test_access"])
        self.assertEqual(shared["data"]["model_access_whitelist"], ["train", "validation"])
        with self.assertRaises(PermissionError):
            runner.load_config(
                MODULE_DIR / "configs" / "exp-051-m1-roberta-seed-42.json", 43
            )

    def test_runner_source_has_explicit_split_boundary(self):
        audit = verifier.source_access_audit(MODULE_DIR / "run_exp051_m1.py")
        self.assertTrue(all(audit.values()), audit)


if __name__ == "__main__":
    unittest.main()
