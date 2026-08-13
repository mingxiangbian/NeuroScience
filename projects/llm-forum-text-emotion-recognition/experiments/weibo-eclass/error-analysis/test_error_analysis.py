#!/usr/bin/env python3
"""Focused standard-library tests for EXP-048 helpers."""

from __future__ import annotations

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_frozen_dev_errors as analysis
import summarize_review as review


class ErrorAnalysisTests(unittest.TestCase):
    def test_multiclass_metrics_include_invalid_as_error(self) -> None:
        metrics = analysis.classification_metrics(
            ["anger", "anger", "joy", "joy"],
            ["anger", analysis.INVALID, "anger", "joy"],
            ["anger", "joy"],
        )
        self.assertAlmostEqual(metrics["accuracy"], 0.5)
        self.assertEqual(metrics["per_class"]["anger"]["tp"], 1)
        self.assertEqual(metrics["per_class"]["anger"]["fp"], 1)
        self.assertEqual(metrics["per_class"]["anger"]["fn"], 1)

    def test_transition_labels(self) -> None:
        self.assertEqual(analysis.transition_name(0, 3, 3, 3), "stable_recovery")
        self.assertEqual(analysis.transition_name(3, 0, 3, 3), "stable_regression")
        self.assertEqual(analysis.transition_name(1, 2, 3, 3), "higher_correct_rate")

    def test_sampling_is_deterministic_and_unique(self) -> None:
        records = []
        for index in range(20):
            records.append(
                {
                    "sample_id": f"sample-{index}",
                    "gold": "anger" if index % 2 else "joy",
                    "conditions": {
                        "reference": {"correct_count": 0, "runs": [{"failed_output": True}]},
                        "lora": {"correct_count": 3 if index < 10 else 1},
                        "encoder": {"correct_count": 0 if index < 10 else 3},
                    },
                }
            )
        sampling = {
            "maximum_unique_rows": 4,
            "seed": "fixed",
            "roles": [{"id": "format_recoveries", "limit": 2}, {"id": "seed_unstable_lora", "limit": 2}],
        }
        first, _ = analysis.select_cases(records, sampling)
        second, _ = analysis.select_cases(records, sampling)
        self.assertEqual(
            [(row["role"], row["record"]["sample_id"]) for row in first],
            [(row["role"], row["record"]["sample_id"]) for row in second],
        )
        self.assertEqual(len({row["record"]["sample_id"] for row in first}), 4)

    def test_none_observed_cannot_mix_with_other_flags(self) -> None:
        config = {
            "annotation": {
                "allowed_evidence_flags": ["none_observed", "negation", "long_tail_class"],
                "allowed_primary_sources": ["uncertain"],
                "confidence_levels": ["low"],
            }
        }
        manifest = [{"sample_rank": "1", "case_id": "case-a", "role": "r", "gold_label": "joy", "long_tail": "false"}]
        annotations = [{"sample_rank": "1", "case_id": "case-a", "role": "r", "gold_label": "joy", "evidence_flags": "none_observed|negation", "primary_possible_source": "uncertain", "reviewer_confidence": "low"}]
        with self.assertRaises(ValueError):
            review.validate_annotations(manifest, annotations, config)


if __name__ == "__main__":
    unittest.main()
