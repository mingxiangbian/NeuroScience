#!/usr/bin/env python3
"""Unit tests for EXP-043 pure helper behavior."""

from __future__ import annotations

import unittest

from label_parser import parse_final_label
import run_stage4


class Stage4HelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "data": {"labels": [
                "anger", "joy", "negative", "neutral", "no_emotion", "positive", "sadness"
            ]}
        }
        self.prompt = {
            "label_definitions": {label: label for label in self.config["data"]["labels"]},
            "output_schema": "{\"label\":\"<allowed_label>\"}",
            "system_template": "{label_definitions}\n{output_schema}",
            "target_only_template": "[T]\n{target}",
            "previous_context_template": "[P]\n{previous}\n[T]\n{target}",
        }

    @staticmethod
    def row(previous: str = "prior") -> dict:
        return {
            "context_available": bool(previous),
            "views": {
                "target_only": {"target": "current"},
                "previous_context": {"previous": previous, "target": "current"},
            },
        }

    def test_missing_context_renders_identical_messages(self) -> None:
        row = self.row("")
        self.assertEqual(
            run_stage4.prompt_messages(self.config, self.prompt, row, "target_only"),
            run_stage4.prompt_messages(self.config, self.prompt, row, "previous_context"),
        )

    def test_context_rendering_only_changes_user_content(self) -> None:
        target = run_stage4.prompt_messages(self.config, self.prompt, self.row(), "target_only")
        context = run_stage4.prompt_messages(self.config, self.prompt, self.row(), "previous_context")
        self.assertEqual(target[0], context[0])
        self.assertNotEqual(target[1], context[1])
        self.assertIn("prior", context[1]["content"])

    def test_strict_parser_accepts_both_modes(self) -> None:
        labels = self.config["data"]["labels"]
        direct = parse_final_label('{"label":"joy"}', thinking=False, labels=labels)
        reasoned = parse_final_label('<think>brief</think>\n{"label":"joy"}', thinking=True, labels=labels)
        self.assertTrue(direct.valid)
        self.assertTrue(reasoned.valid)
        self.assertEqual(reasoned.label, "joy")

    def test_invalid_prediction_stays_in_denominator(self) -> None:
        labels = ["a", "b"]
        result = run_stage4.classification_metrics(
            ["a", "b"],
            ["a", run_stage4.INVALID_LABEL],
            labels,
        )
        self.assertEqual(result["accuracy"], 0.5)
        self.assertEqual(result["per_class"]["b"]["recall"], 0.0)
        self.assertEqual(result["confusion_matrix"], [[1, 0, 0], [0, 0, 1]])

    def test_factorial_effects(self) -> None:
        effects = run_stage4.factorial_effects({"A": 0.4, "B": 0.5, "C": 0.45, "D": 0.6})
        self.assertAlmostEqual(effects["context_reasoning_off_B_minus_A"], 0.1)
        self.assertAlmostEqual(effects["context_reasoning_on_D_minus_C"], 0.15)
        self.assertAlmostEqual(effects["interaction_D_minus_C_minus_B_minus_A"], 0.05)

    def test_selection_prefers_reasoning_off_then_target_only(self) -> None:
        conditions = {
            "A": {"reasoning": False, "view": "target_only"},
            "B": {"reasoning": False, "view": "previous_context"},
            "C": {"reasoning": True, "view": "target_only"},
            "D": {"reasoning": True, "view": "previous_context"},
        }
        result = run_stage4.choose_condition(
            {"A": 0.598, "B": 0.600, "C": 0.601, "D": 0.599},
            conditions,
            {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0},
            0.005,
        )
        self.assertEqual(result["selected_condition"], "A")


if __name__ == "__main__":
    unittest.main()
