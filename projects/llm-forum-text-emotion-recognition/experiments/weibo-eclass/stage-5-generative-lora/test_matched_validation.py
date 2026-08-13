#!/usr/bin/env python3
"""Focused tests for the EXP-047 matched-validation runner."""

from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import run_matched_validation as runner  # noqa: E402


class FakeTokenizer:
    def encode(self, value: str, *, add_special_tokens: bool) -> list[int]:
        if add_special_tokens:
            raise AssertionError("Tests require raw token counts")
        return list(range(len(value.split())))


class MatchedValidationTests(unittest.TestCase):
    def test_require_token_ids_rejects_empty_bool_and_non_integer(self) -> None:
        self.assertEqual(runner.require_token_ids([1, 2, 3]), [1, 2, 3])
        for invalid in ([], [True], [1, "2"]):
            with self.subTest(invalid=invalid), self.assertRaises(TypeError):
                runner.require_token_ids(invalid)

    def test_output_token_counts_partitions_at_first_boundary(self) -> None:
        tokenizer = FakeTokenizer()
        self.assertEqual(
            runner.output_token_counts(tokenizer, "one two</think>three four five", 6),
            {"final_tokens": 3, "thinking_tokens": 2},
        )
        self.assertEqual(
            runner.output_token_counts(tokenizer, "unfinished thought", 2),
            {"final_tokens": 0, "thinking_tokens": 2},
        )

    def test_invalid_predictions_remain_in_metric_denominator(self) -> None:
        result = runner.classification_metrics(
            ["a", "a", "b"], ["a", runner.INVALID_LABEL, "a"], ["a", "b"]
        )
        self.assertAlmostEqual(result["accuracy"], 1 / 3)
        self.assertEqual(result["rows"], 3)
        self.assertEqual(result["confusion_columns"], ["a", "b", runner.INVALID_LABEL])
        self.assertEqual(result["confusion_matrix"], [[1, 0, 1], [1, 0, 0]])

    def test_slice_metrics_preserve_all_rows(self) -> None:
        records = [
            {"context_available": True, "gold_label": "a", "prediction": "a"},
            {"context_available": False, "gold_label": "b", "prediction": "b"},
            {"context_available": False, "gold_label": "a", "prediction": "b"},
        ]
        result = runner.metrics_by_slice(records, ["a", "b"])
        self.assertEqual(result["all"]["rows"], 3)
        self.assertEqual(result["context_available"]["rows"], 1)
        self.assertEqual(result["first_clause"]["rows"], 2)

    def test_resume_requires_exact_unique_ordered_prefix(self) -> None:
        rows = [
            {"sample_id": "s0", "group_id": "g0"},
            {"sample_id": "s1", "group_id": "g1"},
        ]
        prefix = [
            {"condition": "reference", "row_index": 0, "sample_id": "s0", "group_id": "g0"}
        ]
        runner.validate_resume_prefix(prefix, rows, "reference")
        drifted = copy.deepcopy(prefix)
        drifted[0]["sample_id"] = "s1"
        with self.assertRaises(ValueError):
            runner.validate_resume_prefix(drifted, rows, "reference")

    def test_group_bootstrap_is_deterministic_and_aligned(self) -> None:
        reference = [
            {"sample_id": "s0", "group_id": "g0", "gold_label": "a", "prediction": "a"},
            {"sample_id": "s1", "group_id": "g0", "gold_label": "b", "prediction": "a"},
            {"sample_id": "s2", "group_id": "g1", "gold_label": "a", "prediction": "b"},
            {"sample_id": "s3", "group_id": "g1", "gold_label": "b", "prediction": "b"},
        ]
        candidate = copy.deepcopy(reference)
        candidate[1]["prediction"] = "b"
        first = runner.bootstrap_pairwise(reference, candidate, ["a", "b"], 50, "fixed")
        second = runner.bootstrap_pairwise(reference, candidate, ["a", "b"], 50, "fixed")
        self.assertEqual(first, second)
        self.assertEqual(first["groups"], 2)
        misaligned = copy.deepcopy(candidate)
        misaligned[0]["sample_id"] = "other"
        with self.assertRaises(ValueError):
            runner.bootstrap_pairwise(reference, misaligned, ["a", "b"], 50, "fixed")

    def test_frozen_primary_decision_threshold(self) -> None:
        self.assertEqual(runner.primary_decision(0.005, 0.005), "material_improvement")
        self.assertEqual(runner.primary_decision(-0.005, 0.005), "material_degradation")
        self.assertEqual(runner.primary_decision(0.004999, 0.005), "practical_tie")


if __name__ == "__main__":
    unittest.main()
