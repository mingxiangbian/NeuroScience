#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
from pathlib import Path
import statistics
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("exp054_aggregate_tests", ROOT / "aggregate_exp054_m4.py")
aggregate = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(aggregate)


class Exp054AggregateTests(unittest.TestCase):
    def test_summary_uses_sample_std(self):
        result = aggregate.summarize([1.0, 2.0, 4.0])
        self.assertEqual(result["mean"], 7 / 3)
        self.assertEqual(result["sample_std"], statistics.stdev([1.0, 2.0, 4.0]))

    def test_summary_requires_three_seeds(self):
        with self.assertRaises(ValueError):
            aggregate.summarize([1.0, 2.0])

    def test_seed_order_is_frozen(self):
        result = aggregate.summarize([0.1, 0.2, 0.3])
        self.assertEqual(result["values_by_seed"], {"42": 0.1, "43": 0.2, "44": 0.3})


if __name__ == "__main__":
    unittest.main()
