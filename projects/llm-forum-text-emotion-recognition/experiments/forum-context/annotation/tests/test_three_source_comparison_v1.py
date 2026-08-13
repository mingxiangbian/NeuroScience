#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ANNOTATION_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANNOTATION_DIR))

import compare_three_sources_v1 as comparison  # noqa: E402


def decision(label: str, *, confidence: str = "high") -> dict[str, object]:
    if label in {"unclear", "unusable"}:
        return {
            "status": label,
            "primary_emotion": None,
            "other_emotion_text": None,
            "confidence": confidence,
        }
    return {
        "status": "labeled",
        "primary_emotion": label,
        "other_emotion_text": None,
        "confidence": confidence,
    }


def row(human: str, model_01: str, model_02: str) -> dict[str, object]:
    return {
        "decisions": {
            "human": decision(human),
            "model_01": decision(model_01),
            "model_02": decision(model_02),
        }
    }


class DecisionTests(unittest.TestCase):
    def test_other_emotion_exact_key_normalizes_but_public_key_hides_proposal(self) -> None:
        value = {
            "status": "labeled",
            "primary_emotion": "other_emotion",
            "other_emotion_text": "  Moral   Outrage ",
            "confidence": "medium",
        }
        self.assertEqual(comparison.exact_key(value), "other_emotion:moral outrage")
        self.assertEqual(comparison.public_key(value), "other_emotion")

    def test_invalid_unlabeled_emotion_is_rejected(self) -> None:
        value = decision("unclear")
        value["primary_emotion"] = "anger"
        with self.assertRaises(ValueError):
            comparison.validate_decision(value, contextual=False)


class AgreementTests(unittest.TestCase):
    def test_three_way_patterns_are_exclusive(self) -> None:
        rows = [
            row("anger", "anger", "anger"),
            row("anger", "neutral", "neutral"),
            row("anger", "anger", "neutral"),
            row("anger", "neutral", "anger"),
            row("anger", "neutral", "unclear"),
        ]
        metrics = comparison.three_way_metrics(rows)
        self.assertEqual(metrics["all_three_equal"], 1)
        self.assertEqual(metrics["models_equal_human_differs"], 1)
        self.assertEqual(metrics["human_model_01_equal_model_02_differs"], 1)
        self.assertEqual(metrics["human_model_02_equal_model_01_differs"], 1)
        self.assertEqual(metrics["all_three_different"], 1)

    def test_pair_metrics_count_focal_boundaries(self) -> None:
        rows = [
            row("neutral", "unclear", "anger"),
            row("anger", "frustration", "anger"),
        ]
        metrics = comparison.pair_metrics(rows, "human", "model_01")
        self.assertEqual(metrics["agree"], 0)
        self.assertEqual(metrics["focal_disagreements"]["neutral_vs_unclear"], 1)
        self.assertEqual(metrics["focal_disagreements"]["anger_vs_frustration"], 1)

    def test_transition_categories_are_exclusive(self) -> None:
        rows = [
            {"stage_a": {"human": decision("anger")}, "stage_b": {"human": decision("anger")}},
            {"stage_a": {"human": decision("unclear")}, "stage_b": {"human": decision("anger")}},
            {"stage_a": {"human": decision("anger")}, "stage_b": {"human": decision("unclear")}},
            {"stage_a": {"human": decision("anger")}, "stage_b": {"human": decision("frustration")}},
        ]
        metrics = comparison.transition_metrics(rows, "human")
        self.assertEqual(metrics["unchanged"], 1)
        self.assertEqual(metrics["resolved_from_unclear"], 1)
        self.assertEqual(metrics["became_unclear"], 1)
        self.assertEqual(metrics["label_changed"], 1)
        self.assertEqual(metrics["changed_total"], 3)

    def test_group_metrics_projects_the_requested_stage(self) -> None:
        rows = [
            {
                "stage_a": {
                    "human": decision("anger"),
                    "model_01": decision("anger"),
                    "model_02": decision("anger"),
                },
                "stage_b": {
                    "human": decision("neutral"),
                    "model_01": decision("anger"),
                    "model_02": decision("anger"),
                },
            }
        ]
        stage_a = comparison.group_metrics(rows, "stage_a")
        stage_b = comparison.group_metrics(rows, "stage_b")
        self.assertEqual(stage_a["three_way"]["all_three_equal"], 1)
        self.assertEqual(stage_b["three_way"]["models_equal_human_differs"], 1)

    def test_diagnostic_agreement_accepts_projected_stage_rows(self) -> None:
        base = decision("anger")
        contextual = {
            **base,
            "sarcasm": "absent",
            "mixed_emotion": False,
            "context_sufficiency": "sufficient",
        }
        rows = [
            {
                "decisions": {
                    "human": contextual,
                    "model_01": contextual,
                    "model_02": contextual,
                }
            }
        ]
        metrics = comparison.diagnostic_agreement(rows, "sarcasm")
        self.assertEqual(metrics["three_way_exact"], 1)


class PrivacyTests(unittest.TestCase):
    def test_public_report_rejects_private_fields_and_hmac_ids(self) -> None:
        value = {
            "sample_uid": "smp_" + "a" * 64,
            "nested": {"text": "private"},
        }
        violations = comparison.public_violations(value)
        self.assertTrue(any("sample_uid" in item for item in violations))
        self.assertTrue(any("HMAC" in item for item in violations))
        self.assertTrue(any("text" in item for item in violations))

    def test_aggregate_shape_passes_privacy_scan(self) -> None:
        value = {
            "rows": 120,
            "decision_distribution": {"human": {"anger": 10}},
            "privacy": {"forum_text_emitted": False},
        }
        self.assertEqual(comparison.public_violations(value), [])


if __name__ == "__main__":
    unittest.main()
