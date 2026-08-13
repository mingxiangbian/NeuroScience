#!/usr/bin/env python3
"""Unit tests for EXP-042 pure helper behavior."""

from __future__ import annotations

import unittest

import run_stage3


class Stage3HelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prompt = {
            "target_only_template": "[TARGET]\n{target}",
            "previous_context_template": "[PREVIOUS]\n{previous}\n[TARGET]\n{target}",
        }

    def row(self, previous: str) -> dict:
        return {
            "context_available": bool(previous),
            "label": "joy",
            "views": {
                "target_only": {"target": "current"},
                "previous_context": {"previous": previous, "target": "current"},
            },
        }

    def test_target_only_rendering(self) -> None:
        self.assertEqual(
            run_stage3.render_view(self.prompt, self.row("prior"), "target_only"),
            "[TARGET]\ncurrent",
        )

    def test_context_rendering(self) -> None:
        self.assertEqual(
            run_stage3.render_view(self.prompt, self.row("prior"), "previous_context"),
            "[PREVIOUS]\nprior\n[TARGET]\ncurrent",
        )

    def test_missing_context_collapses_to_target_only(self) -> None:
        row = self.row("")
        self.assertEqual(
            run_stage3.render_view(self.prompt, row, "previous_context"),
            run_stage3.render_view(self.prompt, row, "target_only"),
        )

    def test_metrics_keep_zero_support_labels(self) -> None:
        metrics = run_stage3.classification_metrics(
            ["a", "a", "b"],
            ["a", "b", "b"],
            ["a", "b", "c"],
        )
        self.assertAlmostEqual(metrics["accuracy"], 2 / 3)
        self.assertEqual(metrics["per_class"]["c"]["support"], 0)
        self.assertEqual(metrics["per_class"]["c"]["f1"], 0.0)
        self.assertEqual(metrics["confusion_matrix"], [[1, 1, 0], [0, 1, 0], [0, 0, 0]])

    def test_slice_partition(self) -> None:
        rows = [self.row("prior"), self.row("")]
        rows[1]["label"] = "sadness"
        result = run_stage3.metrics_by_slice(rows, ["joy", "joy"], ["joy", "sadness"])
        self.assertEqual(result["all"]["rows"], 2)
        self.assertEqual(result["context_available"]["rows"], 1)
        self.assertEqual(result["first_clause"]["rows"], 1)


if __name__ == "__main__":
    unittest.main()
