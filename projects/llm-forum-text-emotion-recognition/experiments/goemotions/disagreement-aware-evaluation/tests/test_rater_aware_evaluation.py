from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "run_rater_aware_evaluation.py"
SPEC = importlib.util.spec_from_file_location("run_rater_aware_evaluation", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class MetricTests(unittest.TestCase):
    def test_set_metrics_handle_overlap_and_empty_sets(self) -> None:
        self.assertEqual(MODULE.set_f1(set(), set()), 1.0)
        self.assertEqual(MODULE.jaccard(set(), set()), 1.0)
        self.assertEqual(MODULE.exact(set(), set()), 1.0)
        self.assertAlmostEqual(MODULE.set_f1({4}, {4, 27}), 2 / 3)
        self.assertAlmostEqual(MODULE.jaccard({4}, {4, 27}), 1 / 2)
        self.assertEqual(MODULE.exact({4}, {4, 27}), 0.0)

    def test_rater_view_separates_aggregation_from_same_rater_coselection(self) -> None:
        selected = [
            {
                "example_hash": "a" * 64,
                "gold_label_ids": [4, 27],
                "source_dev_row": 1,
            },
            {
                "example_hash": "b" * 64,
                "gold_label_ids": [2, 27],
                "source_dev_row": 2,
            },
        ]
        records = [
            self.record("a", "1", 1, [4]),
            self.record("a", "2", 1, [4]),
            self.record("a", "3", 1, [27]),
            self.record("a", "4", 1, [27]),
            self.record("b", "1", 2, [2, 27]),
            self.record("b", "2", 2, [2, 27]),
        ]
        structures, view, summary = MODULE.build_rater_view(selected, records, 28)
        self.assertTrue(structures[0]["aggregation_only"])
        self.assertFalse(structures[1]["aggregation_only"])
        self.assertEqual(summary["aggregation_only_rows"], 1)
        self.assertEqual(summary["official_threshold_reproduction_mismatches"], 0)
        self.assertEqual(view[1]["clear_sets"], [{4}, {4}, {27}, {27}])

    def test_clear_empty_annotation_stops_scoring(self) -> None:
        selected = [
            {
                "example_hash": "a" * 64,
                "gold_label_ids": [4, 27],
                "source_dev_row": 1,
            }
        ]
        records = [
            self.record("a", "1", 1, [4]),
            self.record("a", "2", 1, [4]),
            self.record("a", "3", 1, [27]),
            self.record("a", "4", 1, []),
        ]
        with self.assertRaisesRegex(RuntimeError, "Empty clear-rater label set"):
            MODULE.build_rater_view(selected, records, 28)

    def test_example_weighting_does_not_weight_rows_by_rater_count(self) -> None:
        selected = [
            {"example_hash": "a" * 64, "gold_label_ids": [4, 27], "source_dev_row": 1},
            {"example_hash": "b" * 64, "gold_label_ids": [2, 27], "source_dev_row": 2},
        ]
        view = {
            1: {"gold": {4, 27}, "clear_sets": [{4}, {4}, {27}, {27}], "all_labeled_sets": [{4}, {4}, {27}, {27}]},
            2: {"gold": {2, 27}, "clear_sets": [{2, 27}, {2, 27}], "all_labeled_sets": [{2, 27}, {2, 27}]},
        }
        config = {
            "predictions": [
                {"condition": "candidate", "run_id": "candidate-42", "seed": 42}
            ]
        }
        predictions = {"candidate-42": {1: {4}, 2: {2, 27}}}
        _, run_metrics, _ = MODULE.score_runs(config, selected, view, predictions)
        expected_row_one = (1.0 + 1.0 + 0.0 + 0.0) / 4
        self.assertAlmostEqual(
            run_metrics[0]["clear_rater_expected_set_f1"],
            (expected_row_one + 1.0) / 2,
        )

    @staticmethod
    def record(prefix: str, rater: str, row_number: int, label_ids: list[int]) -> dict[str, object]:
        return {
            "example_hash": prefix * 64,
            "label_ids": label_ids,
            "rater_hash": rater * 64,
            "source_dev_row": row_number,
            "source_file": "synthetic.csv",
            "source_line": row_number,
            "text_sha256": "t" * 64,
            "unclear": False,
        }


if __name__ == "__main__":
    unittest.main()

