import importlib.util
from pathlib import Path
import unittest

import numpy as np

MODULE = Path(__file__).resolve().parents[1] / 'score_exp072_ablation.py'
SPEC = importlib.util.spec_from_file_location('score_exp072_test', MODULE)
SCORE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCORE)


class ScoringTests(unittest.TestCase):
    def test_perfect_binary_metrics(self):
        gold = np.eye(6, dtype=np.uint8)
        result = SCORE.classification(gold, gold)
        self.assertEqual(result['six_label_macro_f1'], 1.0)
        self.assertEqual(result['five_label_macro_f1'], 1.0)
        self.assertEqual(result['micro_f1'], 1.0)
        self.assertEqual(result['weighted_f1'], 1.0)
        self.assertEqual(result['hamming_loss'], 0.0)
        self.assertEqual(result['subset_accuracy'], 1.0)

    def test_zero_support_and_prediction(self):
        gold = np.zeros((4, 6), dtype=np.uint8)
        result = SCORE.classification(gold, gold)
        self.assertEqual(result['six_label_macro_f1'], 0.0)
        self.assertEqual(result['micro_f1'], 0.0)
        self.assertEqual(result['weighted_f1'], 0.0)
        self.assertEqual(result['subset_accuracy'], 1.0)

    def test_five_label_excludes_only_surprise(self):
        gold = np.eye(6, dtype=np.uint8)
        prediction = gold.copy()
        prediction[:, 2] = 0
        result = SCORE.classification(gold, prediction)
        self.assertAlmostEqual(result['six_label_macro_f1'], 5 / 6)
        self.assertEqual(result['five_label_macro_f1'], 1.0)

    def test_metrics_use_pooled_counts(self):
        gold = np.zeros((5, 6), dtype=np.uint8)
        gold[:, 0] = 1
        prediction = gold.copy()
        prediction[1:, 0] = 0
        result = SCORE.classification(gold, prediction)
        self.assertAlmostEqual(result['per_label']['love']['f1'], 1 / 3)
        self.assertAlmostEqual(result['micro_f1'], 1 / 3)

    def test_stable_sigmoid_and_nonfinite_rejection(self):
        value = SCORE.sigmoid(np.array([-1000., 0., 1000.]))
        np.testing.assert_array_equal(value, [0., .5, 1.])
        with self.assertRaises(ValueError):
            SCORE.sigmoid(np.array([np.nan]))

    def test_binary_validation(self):
        with self.assertRaises(ValueError):
            SCORE.classification(np.full((4, 6), 2), np.ones((4, 6)))

    def test_full_ablation_direction_and_flip(self):
        gold = np.zeros((3360, 6), dtype=np.uint8)
        gold[:, 0] = 1
        logits = {}
        for seed, condition in SCORE.CONDITIONS:
            value = np.full((3360, 6), -2., dtype=np.float32)
            value[:, 0] = 2. if condition == 'A0' else -2.
            logits[f's{seed}:{condition}'] = value
        thresholds = {seed: np.full(3360, .5) for seed in (42, 43, 44)}
        report, predictions = SCORE.score_arrays(gold, logits, thresholds)
        self.assertEqual(len(report['conditions']), 14)
        self.assertEqual(len(predictions), 14)
        condition = report['conditions']['s43:A2']
        self.assertAlmostEqual(condition['delta_from_full']['five_label_macro_f1'], -.2)
        self.assertEqual(condition['prediction_vector_flip_rate'], 1.)
        self.assertAlmostEqual(condition['mean_absolute_logit_change'], 4 / 6)
        self.assertEqual(report['conditions']['s43:A0']['prediction_vector_flip_rate'], 0.)

    def test_threshold_equality_is_positive(self):
        gold = np.zeros((3360, 6), dtype=np.uint8)
        logits = {f's{s}:{c}': np.zeros((3360, 6), dtype=np.float32) for s, c in SCORE.CONDITIONS}
        thresholds = {s: np.full(3360, .5) for s in (42, 43, 44)}
        _, predictions = SCORE.score_arrays(gold, logits, thresholds)
        self.assertTrue(np.all(predictions['s42:A0'] == 1))

    def test_threshold_invalid(self):
        gold = np.zeros((3360, 6), dtype=np.uint8)
        logits = {f's{s}:{c}': np.zeros((3360, 6), dtype=np.float32) for s, c in SCORE.CONDITIONS}
        with self.assertRaises(ValueError):
            SCORE.score_arrays(gold, logits, {s: np.full(3360, np.nan) for s in (42, 43, 44)})


if __name__ == '__main__':
    unittest.main()
