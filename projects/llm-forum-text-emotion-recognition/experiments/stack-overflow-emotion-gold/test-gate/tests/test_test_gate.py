#!/usr/bin/env python3
"""Synthetic tests for EXP-056. These tests never open real test data."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np


TEST_GATE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TEST_GATE_DIR))

from test_gate_common import (  # noqa: E402
    aggregate_values,
    load_prediction_npz,
    load_test_labels_after_prediction_seal,
    metric_bundle,
    save_prediction_npz,
    sha256_file,
    verify_authorization,
)


CONTRACT_PATH = TEST_GATE_DIR / "configs" / "exp-056-test-ready.json"


class TestMetricContract(unittest.TestCase):
    def test_multilabel_metrics_include_strict_accuracy(self) -> None:
        gold = np.asarray([[1, 0, 0, 0, 0, 0], [0, 1, 0, 1, 0, 0]], dtype=np.uint8)
        predicted = np.asarray([[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0]], dtype=np.uint8)
        metrics = metric_bundle(gold, predicted)
        self.assertEqual(metrics["accuracy_definition"], "strict subset/exact-match accuracy")
        self.assertEqual(metrics["subset_accuracy"], 0.5)
        self.assertEqual(metrics["per_label"]["anger"]["fn"], 1)

    def test_three_seed_aggregation_uses_sample_standard_deviation(self) -> None:
        summary = aggregate_values([1.0, 2.0, 3.0])
        self.assertEqual(summary["mean"], 2.0)
        self.assertEqual(summary["sample_std"], 1.0)
        self.assertEqual(summary["n"], 3)


class TestPrivatePredictionContract(unittest.TestCase):
    def test_prediction_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "predictions.npz"
            probabilities = np.full((2, 6), 0.25, dtype=np.float32)
            predicted = (probabilities >= 0.2).astype(np.uint8)
            save_prediction_npz(path, ["a", "b"], ["x", "y"], probabilities, predicted)
            loaded = load_prediction_npz(path, 2)
            np.testing.assert_array_equal(loaded["predicted"], predicted)
            self.assertEqual(loaded["sample_ids"].tolist(), ["a", "b"])


class TestAuthorizationGate(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_missing_authorization_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(PermissionError):
                verify_authorization(self.contract, Path(directory) / "missing.json")

    def test_labels_rejected_before_prediction_seal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            authorization_path = Path(directory) / "authorization.json"
            authorization_path.write_text(json.dumps({
                "schema_version": "exp-056-test-authorization-v1",
                "experiment_id": "EXP-056",
                "authorized": True,
                "contract_sha256": sha256_file(CONTRACT_PATH),
                "scope": "one_time_stack_overflow_test_execution_for_all_12_frozen_units",
                "authorized_at_utc": "2026-08-15T00:00:00+00:00",
                "user_instruction": "synthetic test only",
            }), encoding="utf-8")
            with self.assertRaises(PermissionError):
                load_test_labels_after_prediction_seal(
                    self.contract, authorization_path, {"status": "not sealed"}
                )


class TestFrozenContract(unittest.TestCase):
    def test_exact_formal_scope(self) -> None:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        expected = [f"m{family}-seed-{seed}" for family in range(1, 5) for seed in (42, 43, 44)]
        self.assertEqual(contract["unit_order"], expected)
        self.assertEqual(len(contract["units"]), 12)
        self.assertFalse(contract["data"]["test_inputs_opened_during_freeze"])
        self.assertFalse(contract["data"]["test_labels_opened_during_freeze"])


if __name__ == "__main__":
    unittest.main()
