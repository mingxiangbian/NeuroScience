from __future__ import annotations

import sys
from pathlib import Path
import unittest

import numpy as np


TEST_GATE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TEST_GATE_DIR))

from test_gate_common import compute_metrics


class ComputeMetricsTest(unittest.TestCase):
    def test_multilabel_metrics_and_confusion_orientation(self) -> None:
        labels = ("first", "second")
        gold = np.asarray([[1, 0], [0, 1], [1, 1]], dtype=np.uint8)
        predicted = np.asarray([[1, 0], [1, 0], [1, 1]], dtype=np.uint8)

        metrics, confusion = compute_metrics(gold, predicted, labels)

        self.assertAlmostEqual(metrics["macro"]["f1"], (0.8 + 2 / 3) / 2)
        self.assertAlmostEqual(metrics["micro"]["f1"], 0.75)
        self.assertAlmostEqual(metrics["subset_accuracy"], 2 / 3)
        np.testing.assert_array_equal(
            confusion,
            np.asarray(
                [
                    [[0, 1], [0, 2]],
                    [[1, 0], [1, 1]],
                ],
                dtype=np.int64,
            ),
        )


if __name__ == "__main__":
    unittest.main()
