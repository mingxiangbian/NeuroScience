#!/usr/bin/env python3
"""Unit tests for EXP-044 deterministic sampling and cost helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


RUNNER_PATH = Path(__file__).with_name("run_cost_preflight.py")
SPEC = importlib.util.spec_from_file_location("exp044_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class CostPreflightTests(unittest.TestCase):
    def test_allocate_quotas_is_proportional_and_exact(self) -> None:
        labels = ["a", "b", "c"]
        quotas = RUNNER.allocate_quotas({"a": 70, "b": 20, "c": 10}, 20, labels)
        self.assertEqual(quotas, {"a": 14, "b": 4, "c": 2})
        self.assertEqual(sum(quotas.values()), 20)

    def test_length_quantile_selection_is_deterministic(self) -> None:
        measured = [
            {"label": label, "sample_id": f"{label}-{index}", "token_length": index}
            for label in ("a", "b")
            for index in range(1, 11)
        ]
        first = RUNNER.select_length_quantiles(measured, {"a": 3, "b": 2}, ["a", "b"], "seed")
        second = RUNNER.select_length_quantiles(measured, {"a": 3, "b": 2}, ["a", "b"], "seed")
        self.assertEqual(first, second)
        self.assertEqual(len({row["sample_id"] for row in first}), 5)
        self.assertEqual([row["token_length"] for row in first[:3]], [2, 6, 9])

    def test_cost_projection_uses_only_post_warmup_rates(self) -> None:
        config = {
            "data": {"train_rows": 1000},
            "training": {"steady_state_after_iteration": 20, "epochs_for_projection": [2]},
            "resource_budget": {"safety_multiplier": 1.25},
        }
        history = [
            {"iteration": 10, "iterations_per_second": 0.1},
            {"iteration": 30, "iterations_per_second": 1.0},
            {"iteration": 40, "iterations_per_second": 2.0},
            {"iteration": 50, "iterations_per_second": 3.0},
            {"iteration": 60, "iterations_per_second": 4.0},
            {"iteration": 70, "iterations_per_second": 5.0},
        ]
        projection = RUNNER.cost_projection(config, history)
        self.assertEqual(projection["median_iterations_per_second"], 3.0)
        expected = 1000 * 2 / 3.0 / 3600 * 1.25
        self.assertAlmostEqual(projection["projections"][0]["one_seed_hours_with_safety"], expected)


if __name__ == "__main__":
    unittest.main()
