#!/usr/bin/env python3
"""No-test unit checks for EXP-049 helpers."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import unittest

from test_gate_common import (
    INVALID_LABEL,
    bootstrap_family_contrast,
    classification_metrics,
    metrics_by_slice,
    primary_decision,
)
from verify_frozen_test import (
    bootstrap_contrast as independent_bootstrap_contrast,
    independent_parse,
    metrics as independent_metrics,
    slice_metrics as independent_slice_metrics,
)


class TestMetrics(unittest.TestCase):
    def test_independent_parser_matches_frozen_parser(self) -> None:
        parser_path = (
            Path(__file__).resolve().parent.parent
            / "stage-4-qwen-2x2"
            / "label_parser.py"
        )
        spec = importlib.util.spec_from_file_location("exp049_test_frozen_parser", parser_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        labels = ["anger", "joy"]
        outputs = [
            "",
            "   ",
            '{"label":"anger"}',
            '<think>reason</think>{"label":"anger"}',
            '<think>reason</think>{"label":"unknown"}',
            '<think>reason</think>{"label":"anger","extra":1}',
            '<think>reason</think>not-json',
            '<think>reason</think><think>{"label":"joy"}',
            '<think>reason</think></think>{"label":"joy"}',
        ]
        for output in outputs:
            expected = module.parse_final_label(output, thinking=True, labels=labels).to_dict()
            self.assertEqual(independent_parse(output, labels), expected)

    def test_independent_metrics_match_runner_helpers(self) -> None:
        labels = ["anger", "joy", "no_emotion"]
        gold = ["anger", "joy", "no_emotion", "anger"]
        predicted = ["anger", INVALID_LABEL, "joy", "no_emotion"]
        self.assertEqual(
            independent_metrics(gold, predicted, labels),
            classification_metrics(gold, predicted, labels),
        )
        rows = [
            {"context_available": True, "ambiguous_target": False, "group_id": "g1"},
            {"context_available": False, "ambiguous_target": True, "group_id": "g2"},
            {"context_available": True, "ambiguous_target": False, "group_id": "g2"},
            {"context_available": False, "ambiguous_target": False, "group_id": "g3"},
        ]
        contract = {
            "labels": labels,
            "evaluation": {
                "long_tail_labels": ["anger", "joy"],
                "slices": [
                    "all",
                    "context_available",
                    "first_clause",
                    "ambiguous_target",
                    "unambiguous_target",
                    "no_emotion",
                    "emotion_label",
                    "long_tail_label",
                ],
            },
        }
        self.assertEqual(
            independent_slice_metrics(rows, gold, predicted, contract),
            metrics_by_slice(rows, gold, predicted, contract),
        )

    def test_invalid_prediction_counts_as_error_without_expanding_macro_labels(self) -> None:
        metrics = classification_metrics(
            ["anger", "joy", "joy"],
            ["anger", INVALID_LABEL, "anger"],
            ["anger", "joy"],
        )
        self.assertTrue(math.isclose(metrics["accuracy"], 1 / 3))
        self.assertTrue(math.isclose(metrics["macro_f1"], 1 / 3))
        self.assertEqual(metrics["confusion_columns"], ["anger", "joy", INVALID_LABEL])
        self.assertEqual(metrics["confusion_matrix"], [[1, 0, 0], [1, 0, 1]])

    def test_slices_use_frozen_metadata_and_gold_groups(self) -> None:
        rows = [
            {"context_available": True, "ambiguous_target": False, "group_id": "g1"},
            {"context_available": False, "ambiguous_target": True, "group_id": "g2"},
            {"context_available": True, "ambiguous_target": False, "group_id": "g2"},
        ]
        contract = {
            "labels": ["anger", "no_emotion"],
            "evaluation": {
                "long_tail_labels": ["anger"],
                "slices": [
                    "all",
                    "context_available",
                    "first_clause",
                    "ambiguous_target",
                    "unambiguous_target",
                    "no_emotion",
                    "emotion_label",
                    "long_tail_label",
                ],
            },
        }
        metrics = metrics_by_slice(
            rows,
            ["anger", "no_emotion", "anger"],
            ["anger", "no_emotion", "no_emotion"],
            contract,
        )
        self.assertEqual(metrics["all"]["rows"], 3)
        self.assertEqual(metrics["context_available"]["rows"], 2)
        self.assertEqual(metrics["ambiguous_target"]["rows"], 1)
        self.assertEqual(metrics["long_tail_label"]["rows"], 2)

    def test_group_bootstrap_is_deterministic(self) -> None:
        rows = [{"group_id": "g1"}, {"group_id": "g1"}, {"group_id": "g2"}]
        gold = ["a", "b", "a"]
        predictions = {
            "candidate": ["a", "b", "a"],
            "reference": ["b", "b", "b"],
        }
        first = bootstrap_family_contrast(
            rows, gold, predictions, ["candidate"], ["reference"], ["a", "b"], 50, "x"
        )
        second = bootstrap_family_contrast(
            rows, gold, predictions, ["candidate"], ["reference"], ["a", "b"], 50, "x"
        )
        self.assertEqual(first, second)
        self.assertEqual(
            first,
            independent_bootstrap_contrast(
                rows,
                gold,
                predictions,
                ["candidate"],
                ["reference"],
                ["a", "b"],
                50,
                "x",
            ),
        )
        self.assertGreater(first["observed_delta"], 0)

    def test_practical_decision_boundaries(self) -> None:
        self.assertEqual(primary_decision(0.005, 0.005), "material_improvement")
        self.assertEqual(primary_decision(-0.005, 0.005), "material_degradation")
        self.assertEqual(primary_decision(0.0049, 0.005), "practical_tie")


if __name__ == "__main__":
    unittest.main()
