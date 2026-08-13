#!/usr/bin/env python3
"""Unit tests for the EXP-045 sampling, comparison, and decision helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


RUNNER_PATH = Path(__file__).with_name("run_batch_equivalence.py")
SPEC = importlib.util.spec_from_file_location("exp045_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def decision_config() -> dict[str, object]:
    return {
        "decision": {
            "batch_composition_label_agreement_min": 1.0,
            "batch_replay_label_agreement_min": 1.0,
            "fallback_if_no_stable_reasoning_on_mode": "blocked",
            "singleton_replay_label_agreement_min": 1.0,
        }
    }


def comparison(rate: float) -> dict[str, float]:
    return {"final_label_equal_rate": rate}


class BatchEquivalenceTests(unittest.TestCase):
    def test_allocate_quotas_is_proportional_and_exact(self) -> None:
        labels = ["a", "b", "c"]
        quotas = RUNNER.allocate_quotas({"a": 70, "b": 20, "c": 10}, 20, labels)
        self.assertEqual(quotas, {"a": 14, "b": 4, "c": 2})
        self.assertEqual(sum(quotas.values()), 20)

    def test_representative_selection_is_deterministic(self) -> None:
        measured = [
            {
                "label": label,
                "prompt_tokens": index,
                "sample_id": f"{label}-{index}",
            }
            for label in ("a", "b")
            for index in range(1, 11)
        ]
        first = RUNNER.select_representative_rows(
            [dict(row) for row in measured], {"a": 3, "b": 2}, ["a", "b"], "seed"
        )
        second = RUNNER.select_representative_rows(
            [dict(row) for row in measured], {"a": 3, "b": 2}, ["a", "b"], "seed"
        )
        self.assertEqual(first, second)
        self.assertEqual(len({row["sample_id"] for row in first}), 5)
        by_label = {
            label: sorted(row["prompt_tokens"] for row in first if row["label"] == label)
            for label in ("a", "b")
        }
        self.assertEqual(by_label, {"a": [2, 6, 9], "b": [3, 8]})

    def test_compare_records_checks_all_three_surfaces(self) -> None:
        left = [
            {
                "selection_index": 0,
                "raw_output_sha256": "a",
                "prediction": "joy",
                "parse": {"valid": True},
            },
            {
                "selection_index": 1,
                "raw_output_sha256": "b",
                "prediction": "sadness",
                "parse": {"valid": True},
            },
        ]
        right = [
            {
                "selection_index": 1,
                "raw_output_sha256": "c",
                "prediction": "sadness",
                "parse": {"valid": False},
            },
            {
                "selection_index": 0,
                "raw_output_sha256": "a",
                "prediction": "joy",
                "parse": {"valid": True},
            },
        ]
        result = RUNNER.compare_records(left, right)
        self.assertEqual(result["raw_output_equal_rate"], 0.5)
        self.assertEqual(result["parser_state_equal_rate"], 0.5)
        self.assertEqual(result["final_label_equal_rate"], 1.0)

    def test_decision_prefers_stable_batch8(self) -> None:
        comparisons = {
            "batch8_replay": comparison(1.0),
            "batch8_composition": comparison(1.0),
            "singleton_replay": comparison(1.0),
        }
        result = RUNNER.choose_execution_protocol(decision_config(), comparisons)
        self.assertEqual(result["gate_status"], "Passed")
        self.assertEqual(result["recommended_execution_protocol"], "batch8_fixed_order")

    def test_decision_falls_back_to_stable_singleton(self) -> None:
        comparisons = {
            "batch8_replay": comparison(1.0),
            "batch8_composition": comparison(0.9),
            "singleton_replay": comparison(1.0),
        }
        result = RUNNER.choose_execution_protocol(decision_config(), comparisons)
        self.assertEqual(result["gate_status"], "Passed")
        self.assertEqual(result["recommended_execution_protocol"], "singleton")

    def test_decision_blocks_unstable_reasoning_on(self) -> None:
        comparisons = {
            "batch8_replay": comparison(0.9),
            "batch8_composition": comparison(0.9),
            "singleton_replay": comparison(0.9),
        }
        result = RUNNER.choose_execution_protocol(decision_config(), comparisons)
        self.assertEqual(result["gate_status"], "Blocked")
        self.assertEqual(result["recommended_execution_protocol"], "blocked")


if __name__ == "__main__":
    unittest.main()
