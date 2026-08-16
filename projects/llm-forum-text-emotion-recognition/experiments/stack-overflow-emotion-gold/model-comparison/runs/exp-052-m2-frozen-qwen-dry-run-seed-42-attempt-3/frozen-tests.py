from __future__ import annotations

import importlib.util
import json
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


runner = load_module("so_exp052_runner", "run_exp052_m2.py")
verifier = load_module("so_exp052_verifier", "verify_exp052_m2.py")


class MetricTests(unittest.TestCase):
    def test_runner_and_verifier_metrics_match_known_multilabel_counts(self):
        gold = np.asarray(
            [
                [1, 0, 0, 0, 0, 0],
                [1, 1, 0, 0, 0, 0],
                [0, 1, 1, 0, 0, 0],
                [0, 0, 0, 0, 0, 0],
            ],
            dtype=np.uint8,
        )
        predicted = np.asarray(
            [
                [1, 0, 0, 0, 0, 0],
                [0, 1, 0, 0, 0, 0],
                [0, 1, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0],
            ],
            dtype=np.uint8,
        )
        observed = runner.metric_bundle(gold, predicted)
        self.assertEqual(observed, verifier.metric_bundle(gold, predicted))
        self.assertAlmostEqual(observed["subset_accuracy"], 0.5)
        self.assertAlmostEqual(observed["per_label"]["love"]["f1"], 2 / 3)
        self.assertAlmostEqual(observed["per_label"]["joy"]["f1"], 1.0)
        self.assertEqual(observed["per_label"]["surprise"]["f1"], 0.0)

    def test_checkpoint_tie_rule_is_strict_and_earliest(self):
        history = [
            {"epoch": 1, "fixed_macro_f1": 0.6001},
            {"epoch": 2, "fixed_macro_f1": 0.6050},
        ]
        expected = runner.select_checkpoint(history, 0.005)
        independent = verifier.independently_select_checkpoint([0.6001, 0.6050], 0.005)
        self.assertEqual(expected, independent)
        self.assertEqual(expected["selected_epoch"], 1)
        boundary = runner.select_checkpoint(
            [{"epoch": 1, "fixed_macro_f1": 0.6000}, {"epoch": 2, "fixed_macro_f1": 0.6050}],
            0.005,
        )
        self.assertEqual(boundary["selected_epoch"], 2)

    def test_threshold_tie_prefers_closest_to_point_five_then_lower(self):
        gold = np.asarray([[1, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]], dtype=np.uint8)
        probabilities = np.asarray(
            [[0.9, 0.1, 0.1, 0.1, 0.1, 0.1], [0.1, 0.1, 0.1, 0.1, 0.1, 0.1]],
            dtype=np.float32,
        )
        selected, rows = runner.select_threshold(gold, probabilities, [0.4, 0.5, 0.6])
        independent, independent_rows = verifier.independently_select_threshold(
            gold, probabilities, [0.4, 0.5, 0.6]
        )
        self.assertEqual(selected, 0.5)
        self.assertEqual((selected, rows), (independent, independent_rows))

    def test_sigmoid_is_stable_for_large_logits(self):
        values = runner.sigmoid(np.asarray([[-1000.0, 0.0, 1000.0]], dtype=np.float32))
        self.assertTrue(np.isfinite(values).all())
        self.assertEqual(float(values[0, 0]), 0.0)
        self.assertEqual(float(values[0, 1]), 0.5)
        self.assertEqual(float(values[0, 2]), 1.0)


class ContractTests(unittest.TestCase):
    @staticmethod
    def rows():
        rows = []
        for label_index in range(6):
            for copy in range(3):
                labels = [0] * 6
                labels[label_index] = 1
                rows.append(
                    {
                        "sample_id": f"p-{label_index}-{copy}",
                        "component_id": f"c-{label_index}-{copy}",
                        "labels": labels,
                    }
                )
        for index in range(20):
            rows.append(
                {
                    "sample_id": f"n-{index}",
                    "component_id": f"nc-{index}",
                    "labels": [0] * 6,
                }
            )
        return rows

    def test_dry_selection_is_deterministic_and_independent(self):
        first = runner.select_dry_rows(self.rows(), 24, "unit-exp052")
        second = runner.select_dry_rows(list(reversed(self.rows())), 24, "unit-exp052")
        independent = verifier.independently_select_dry_rows(self.rows(), 24, "unit-exp052")
        ids = [row["sample_id"] for row in first]
        self.assertEqual(ids, [row["sample_id"] for row in second])
        self.assertEqual(ids, [row["sample_id"] for row in independent])
        for index in range(6):
            self.assertGreaterEqual(sum(row["labels"][index] for row in first), 2)

    def test_runner_source_keeps_test_sealed_and_updates_only_head(self):
        audit = verifier.source_access_audit(MODULE_DIR / "run_exp052_m2.py")
        self.assertTrue(all(audit.values()), audit)

    def test_authorization_excludes_later_work(self):
        protocol = (
            MODULE_DIR.parent / "protocols" / "exp-052-seed-42-authorization.md"
        ).read_text(encoding="utf-8")
        self.assertIn("does not authorize Stack Overflow test access", protocol)
        self.assertIn("seeds 43 or 44", protocol)
        self.assertIn("EXP-053/M3", protocol)

    def test_dry_run_contract_authorizes_train_only_when_present(self):
        path = MODULE_DIR / "configs" / "exp-052-m2-seed-42-dry-run.json"
        if not path.exists():
            self.skipTest("Dry-run contract is frozen after source hashes are available")
        config = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(config["experiment_id"], "EXP-052")
        self.assertEqual(config["stage"], "train-only-dry-run")
        self.assertEqual(config["authorization"]["seeds"], [42])
        self.assertEqual(config["authorization"]["splits"], ["train"])
        self.assertFalse(config["authorization"]["test_access"])
        self.assertFalse(config["authorization"]["seeds_43_44_authorized"])
        self.assertFalse(config["authorization"]["exp_053_054_authorized"])


if __name__ == "__main__":
    unittest.main()
