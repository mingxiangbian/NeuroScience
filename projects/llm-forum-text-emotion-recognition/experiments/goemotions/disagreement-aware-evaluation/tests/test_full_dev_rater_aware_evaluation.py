from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, MODULE_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load_module("exp037_runner", "run_full_dev_rater_aware_evaluation.py")
VERIFIER = load_module("exp037_verifier", "verify_full_dev_rater_aware_evaluation.py")


class FullDevRaterAwareEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.selected = [
            {
                "comment_id": "example-1",
                "example_hash": RUNNER.sha256_text("example-1"),
                "gold_label_ids": [0],
                "source_dev_row": 1,
                "text_sha256": RUNNER.sha256_text("text-1"),
            },
            {
                "comment_id": "example-2",
                "example_hash": RUNNER.sha256_text("example-2"),
                "gold_label_ids": [1, 2],
                "source_dev_row": 2,
                "text_sha256": RUNNER.sha256_text("text-2"),
            },
        ]
        label_sets = {
            1: [[0], [0], [1]],
            2: [[1], [1], [2], [2]],
        }
        self.records = []
        for target in self.selected:
            row_number = target["source_dev_row"]
            for index, labels in enumerate(label_sets[row_number]):
                self.records.append(
                    {
                        "example_hash": target["example_hash"],
                        "label_ids": labels,
                        "rater_hash": RUNNER.sha256_text(f"rater-{row_number}-{index}"),
                        "source_dev_row": row_number,
                        "source_file": "fixture.csv",
                        "source_line": index + 2,
                        "text_sha256": target["text_sha256"],
                        "unclear": False,
                    }
                )

    def test_frozen_full_dev_row_hash(self) -> None:
        observed = RUNNER.sha256_text(",".join(map(str, range(1, 5427))))
        self.assertEqual(
            observed,
            "973b9f662bf3fac69c014da03f4741bf312e409bd38ddb1d8e4d8c6c48a3fa98",
        )

    def test_runner_and_verifier_rebuild_same_rater_view(self) -> None:
        runner_structures, runner_view, runner_summary = RUNNER.build_rater_view(
            self.selected, self.records, 3
        )
        verifier_structures, verifier_view, verifier_summary = VERIFIER.rebuild_rater_view(
            self.selected, self.records, 3
        )
        self.assertEqual(runner_structures, verifier_structures)
        self.assertEqual(runner_summary, verifier_summary)
        np.testing.assert_allclose(runner_view[1]["clear_probs"], [2 / 3, 1 / 3, 0])
        np.testing.assert_allclose(runner_view[2]["clear_probs"], [0, 0.5, 0.5])
        np.testing.assert_allclose(
            runner_view[2]["clear_probs"], verifier_view[2]["clear_probs"]
        )
        self.assertEqual(runner_summary["aggregate_target_not_any_clear_rater_rows"], 1)

    def test_soft_label_metric_formula_matches_independent_implementation(self) -> None:
        prediction = np.array([[1.0, 0.0], [0.0, 1.0]])
        target = np.array([[0.5, 0.5], [0.0, 1.0]])
        runner_summary, runner_rows = RUNNER.binary_metric_summary(prediction, target)
        verifier_summary, verifier_rows = VERIFIER.score_binary(prediction, target)
        self.assertAlmostEqual(runner_summary["macro_f1"], (2 / 3 + 0.8) / 2)
        self.assertAlmostEqual(runner_summary["micro_f1"], 0.75)
        self.assertEqual(runner_summary, verifier_summary)
        self.assertEqual(runner_rows, verifier_rows)

    def test_bootstraps_match_independent_implementation(self) -> None:
        official = np.array([-0.2, 0.0, 0.1, 0.3])
        rater = np.array([-0.1, 0.1, 0.2, 0.4])
        runner_sample = RUNNER.bootstrap_sample_metrics(official, rater, 50, 41)
        verifier_sample = VERIFIER.sample_bootstrap(official, rater, 50, 41)
        self.assertEqual(runner_sample, verifier_sample)

        candidate = np.array(
            [
                [[1, 0], [0, 1], [1, 1], [0, 1]],
                [[1, 0], [1, 0], [1, 1], [0, 1]],
            ],
            dtype=float,
        )
        reference = np.array(
            [[[0, 1], [0, 1], [1, 0], [0, 1]]], dtype=float
        )
        gold = np.array([[1, 0], [0, 1], [1, 1], [0, 1]], dtype=float)
        clear = np.array([[0.5, 0.5], [0, 1], [0.5, 1], [0, 1]], dtype=float)
        runner_macro = RUNNER.bootstrap_macro_metrics(
            candidate, reference, gold, clear, 40, 99
        )
        verifier_macro = VERIFIER.bootstrap_macro(
            candidate, reference, gold, clear, 40, 99
        )
        self.assertEqual(runner_macro, verifier_macro)

    def test_full_scoring_and_comparison_match(self) -> None:
        _, runner_view, _ = RUNNER.build_rater_view(self.selected, self.records, 3)
        _, verifier_view, _ = VERIFIER.rebuild_rater_view(self.selected, self.records, 3)
        config = {
            "labels": ["label-0", "label-1", "label-2"],
            "predictions": [
                {"condition": "candidate", "run_id": "candidate-42", "seed": 42},
                {"condition": "reference", "run_id": "reference-42", "seed": 42},
            ],
            "comparisons": [
                {
                    "comparison_id": "candidate-minus-reference",
                    "candidate": {
                        "condition": "candidate",
                        "label": "candidate seed 42",
                        "seeds": [42],
                    },
                    "reference": {
                        "condition": "reference",
                        "label": "reference seed 42",
                        "seeds": [42],
                    },
                }
            ],
            "statistics": {
                "bootstrap_seed": 123,
                "macro_bootstrap_iterations": 20,
                "material_shift_threshold": 0.02,
                "practical_tie_threshold": 0.005,
                "sample_bootstrap_iterations": 20,
            },
        }
        predictions = {
            "candidate-42": [{0}, {1, 2}],
            "reference-42": [{1}, {1}],
        }
        runner_metrics, runner_labels, runner_arrays = RUNNER.score_runs(
            config, self.selected, runner_view, predictions
        )
        verifier_metrics, verifier_labels, verifier_arrays = VERIFIER.independently_score_runs(
            config, self.selected, verifier_view, predictions
        )
        self.assertLessEqual(
            VERIFIER.compare_nested(runner_metrics, verifier_metrics), 1e-12
        )
        self.assertLessEqual(
            VERIFIER.compare_nested(runner_labels, verifier_labels), 1e-12
        )
        runner_comparison = RUNNER.compare_models(config, runner_metrics, runner_arrays)
        verifier_comparison = VERIFIER.independently_compare(
            config, verifier_metrics, verifier_arrays
        )
        self.assertLessEqual(
            VERIFIER.compare_nested(runner_comparison, verifier_comparison), 1e-12
        )


if __name__ == "__main__":
    unittest.main()
