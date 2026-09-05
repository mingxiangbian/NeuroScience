#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = PROJECT_ROOT / "scripts" / "run_sqma005_agent_tune_comparison.py"
SPEC = importlib.util.spec_from_file_location("sqma005_runner_test", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class SQMA005PureContractTests(unittest.TestCase):
    def test_call_plan_is_six_per_row_and_4032_total(self) -> None:
        slots = RUNNER.planned_call_slots()
        self.assertEqual(len(slots), 4032)
        self.assertEqual(
            slots[:6],
            [
                (0, "S3", "evidence_appraisal", 0),
                (0, "S3", "pragmatics_critic", 1),
                (0, "S3", "judge", 2),
                (0, "single_pool", "single_agent", 0),
                (0, "single_pool", "single_agent", 1),
                (0, "single_pool", "single_agent", 2),
            ],
        )
        self.assertEqual(slots[-1], (671, "single_pool", "single_agent", 2))

    def test_seed_schedule_is_deterministic_and_call_specific(self) -> None:
        first = RUNNER.seed_for("namespace", "single_pool", "sample-a", "single_agent", 0)
        self.assertEqual(first, RUNNER.seed_for("namespace", "single_pool", "sample-a", "single_agent", 0))
        self.assertNotEqual(first, RUNNER.seed_for("namespace", "single_pool", "sample-a", "single_agent", 1))
        self.assertGreaterEqual(first, 0)
        self.assertLess(first, 2**32)

    def test_strict_majority_treats_empty_and_even_tie_as_absent(self) -> None:
        self.assertEqual(
            RUNNER.strict_majority(
                [
                    ["joy", "anger"],
                    ["anger"],
                    [],
                ]
            ),
            ["anger"],
        )
        self.assertEqual(RUNNER.strict_majority([["anger"], []]), [])
        self.assertEqual(RUNNER.strict_majority([None, ["fear"], ["fear"]]), ["fear"])

    def test_s2b_uses_largest_whole_prefix_within_tolerance(self) -> None:
        self.assertEqual(RUNNER.choose_s2b_k(300, 100, 0.1), (3, 300, 1.0))
        k, used, utilization = RUNNER.choose_s2b_k(220, 100, 0.1)
        self.assertEqual((k, used), (2, 200))
        self.assertAlmostEqual(utilization, 200 / 220)
        with self.assertRaisesRegex(RUNNER.ProducerError, "no whole-call"):
            RUNNER.choose_s2b_k(260, 100, 0.1)

    def test_any_invalid_s3_role_or_abstention_forces_empty(self) -> None:
        self.assertEqual(RUNNER.effective_s3_labels([True, True, True], ["anger"], False), ["anger"])
        self.assertEqual(RUNNER.effective_s3_labels([True, False, True], ["anger"], False), [])
        self.assertEqual(RUNNER.effective_s3_labels([True, True, True], ["anger"], True), [])

    def test_private_call_text_metadata_is_identical_across_six_row_calls(self) -> None:
        source = "A source sentence."
        token_metadata = {
            "original_tokens": 4,
            "analysis_tokens": 4,
            "was_truncated": False,
        }
        observed = [
            RUNNER.call_text_metadata(source, source, token_metadata)
            for _ in RUNNER.CALL_ORDER
        ]
        self.assertEqual(len(observed), 6)
        self.assertTrue(all(value == observed[0] for value in observed))
        self.assertTrue(observed[0]["model_free_truncation_replay"])
        with self.assertRaisesRegex(RUNNER.ProducerError, "untruncated"):
            RUNNER.call_text_metadata(source, "different", token_metadata)

        truncated = RUNNER.call_text_metadata(
            source,
            "A source",
            {"original_tokens": 4, "analysis_tokens": 2, "was_truncated": True},
        )
        self.assertFalse(truncated["model_free_truncation_replay"])


if __name__ == "__main__":
    unittest.main()
