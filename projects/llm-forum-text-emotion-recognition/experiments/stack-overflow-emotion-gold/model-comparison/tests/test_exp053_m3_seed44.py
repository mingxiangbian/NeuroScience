#!/usr/bin/env python3
"""Focused tests for the EXP-053 seed-44 runner and verifier."""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_module("exp053_seed44_runner_tests", "run_exp053_m3_seed44.py")
verifier = load_module("exp053_seed44_verifier_tests", "verify_exp053_m3_seed44.py")


class FormalContractTests(unittest.TestCase):
    def test_identity_and_scope_constants(self) -> None:
        self.assertEqual(runner.EXPERIMENT_ID, verifier.EXPERIMENT_ID)
        self.assertEqual(runner.EXPERIMENT_ID, "EXP-053")
        self.assertEqual(runner.SEED, verifier.SEED)
        self.assertEqual(runner.SEED, 44)
        self.assertEqual(runner.STAGE, verifier.STAGE)
        self.assertEqual(runner.STAGE, "seed-44-train-validation")
        self.assertEqual(runner.LABELS, verifier.LABELS)

    def test_prerequisite_verification_uses_actual_schema(self) -> None:
        valid = {
            "status": "Passed",
            "check_count": 2,
            "checks": [{"passed": True}, {"passed": True}],
            "failed_checks": [],
        }
        runner.require_passed_verification(valid, 2, "fixture")
        for key, value in (
            ("status", "Failed"),
            ("check_count", 1),
            ("checks", [{"passed": True}]),
            ("failed_checks", ["failed"]),
        ):
            invalid = dict(valid)
            invalid[key] = value
            with self.assertRaises(RuntimeError):
                runner.require_passed_verification(invalid, 2, "fixture")

    def test_metric_bundle_perfect_prediction(self) -> None:
        gold = np.asarray([[1, 0, 0, 1, 0, 0], [0, 1, 1, 0, 1, 1]], dtype=np.uint8)
        result = runner.metric_bundle(gold, gold.copy())
        self.assertEqual(result["macro"]["f1"], 1.0)
        self.assertEqual(result["micro_f1"], 1.0)
        self.assertEqual(result["subset_accuracy"], 1.0)
        self.assertEqual(result["hamming_loss"], 0.0)

    def test_metric_bundle_zero_division_contract(self) -> None:
        gold = np.zeros((3, 6), dtype=np.uint8)
        predicted = np.zeros_like(gold)
        result = verifier.metric_bundle(gold, predicted)
        self.assertEqual(result["macro"]["f1"], 0.0)
        self.assertEqual(result["weighted_f1"], 0.0)
        self.assertEqual(result["subset_accuracy"], 1.0)
        self.assertEqual(result["prediction_diagnostics"]["empty_prediction_rows"], 3)

    def test_checkpoint_selection_uses_strict_practical_tie_and_earliest(self) -> None:
        history = [
            {"epoch": 1, "fixed_macro_f1": 0.5000},
            {"epoch": 2, "fixed_macro_f1": 0.5049},
        ]
        self.assertEqual(runner.select_checkpoint(history, 0.005)["selected_epoch"], 1)
        history[1]["fixed_macro_f1"] = 0.5050
        self.assertEqual(runner.select_checkpoint(history, 0.005)["selected_epoch"], 2)

    def test_threshold_tie_prefers_closest_to_half(self) -> None:
        gold = np.zeros((2, 6), dtype=np.uint8)
        probabilities = np.zeros((2, 6), dtype=np.float32)
        threshold, _ = runner.select_threshold(gold, probabilities, [0.4, 0.5, 0.6])
        self.assertEqual(threshold, 0.5)

    def test_bootstrap_is_deterministic_and_runner_matches_verifier(self) -> None:
        gold = np.asarray([[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0]], dtype=np.uint8)
        predicted = np.asarray([[1, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]], dtype=np.uint8)
        components = ["a", "b", "c"]
        first = runner.bootstrap_summary(gold, predicted, components, 44, 20, "unit", "fixed-0.5")
        second = verifier.bootstrap(gold, predicted, components, 44, 20, "unit", "fixed-0.5")
        self.assertEqual(first, second)

    def test_paired_bootstrap_zero_delta_for_identical_predictions(self) -> None:
        gold = np.asarray([[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0]], dtype=np.uint8)
        predicted = gold.copy()
        result = runner.paired_bootstrap(gold, predicted, predicted, ["a", "b"], 44, 20, "unit", "fixed-0.5")
        self.assertEqual(result["macro_f1_delta"], {"point": 0.0, "lower": 0.0, "upper": 0.0})

    def test_runner_and_verifier_metric_implementations_match(self) -> None:
        rng = np.random.default_rng(123)
        gold = rng.integers(0, 2, size=(17, 6), dtype=np.uint8)
        predicted = rng.integers(0, 2, size=(17, 6), dtype=np.uint8)
        self.assertEqual(runner.metric_bundle(gold, predicted), verifier.metric_bundle(gold, predicted))

    def test_canonical_batch_order_is_repeatable(self) -> None:
        sample_ids = [f"s-{index}" for index in range(10)]
        first_rng = np.random.default_rng(44)
        second_rng = np.random.default_rng(44)
        first = [runner.canonical_digest([sample_ids[int(index)] for index in first_rng.permutation(10)]) for _ in range(2)]
        second = [verifier.canonical_digest([sample_ids[int(index)] for index in second_rng.permutation(10)]) for _ in range(2)]
        self.assertEqual(first, second)
        self.assertNotEqual(first[0], first[1])

    def test_close_json_accepts_small_float_replay_error(self) -> None:
        self.assertTrue(verifier.close_json({"value": 0.5}, {"value": 0.500000001}, tolerance=1e-8))
        self.assertFalse(verifier.close_json({"value": 0.5}, {"value": 0.5001}, tolerance=1e-8))

    def test_history_parser_preserves_digest_and_numeric_fields(self) -> None:
        fields = [
            "seed", "epoch", "optimizer_steps", "train_loss", "validation_loss",
            "fixed_threshold", "fixed_macro_precision", "fixed_macro_recall", "fixed_macro_f1",
            "fixed_micro_f1", "fixed_weighted_f1", "fixed_subset_accuracy", "fixed_hamming_loss",
            "fixed_five_label_macro_f1_without_surprise", "batch_order_sha256", "epoch_seconds",
            "validation_seconds",
        ]
        row = {key: 1.0 for key in fields}
        row.update({"seed": 44, "epoch": 1, "optimizer_steps": 3360, "batch_order_sha256": "abc"})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.csv"
            with path.open("w", encoding="utf-8", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=fields)
                writer.writeheader()
                writer.writerow(row)
            parsed = verifier.parse_history(path)
        self.assertEqual(parsed[0]["seed"], 44)
        self.assertEqual(parsed[0]["optimizer_steps"], 3360)
        self.assertEqual(parsed[0]["batch_order_sha256"], "abc")

    def test_sigmoid_is_stable_for_large_logits(self) -> None:
        logits = np.asarray([[-1000.0, 1000.0, 0.0]], dtype=np.float32)
        output = runner.sigmoid(logits)
        self.assertTrue(np.isfinite(output).all())
        self.assertEqual(output[0, 0], 0.0)
        self.assertEqual(output[0, 1], 1.0)
        self.assertEqual(output[0, 2], 0.5)

    def test_verifier_does_not_import_runner(self) -> None:
        source = (ROOT / "verify_exp053_m3_seed44.py").read_text(encoding="utf-8")
        self.assertNotIn("import run_exp053_m3_seed44", source)
        self.assertNotIn("from run_exp053_m3_seed44", source)
        self.assertIn("def metric_bundle(", source)
        self.assertIn("def prompt_ids(", source)

    def test_seed44_uses_matched_m2_and_keeps_later_stages_sealed(self) -> None:
        runner_source = (ROOT / "run_exp053_m3_seed44.py").read_text(encoding="utf-8")
        verifier_source = (ROOT / "verify_exp053_m3_seed44.py").read_text(encoding="utf-8")
        for source in (runner_source, verifier_source):
            self.assertIn('m2_seed_44', source)
            self.assertNotIn('m2_seed_43', source)
            self.assertIn('prior_m3_seed_42', source)
            self.assertIn('prior_m3_seed_43', source)
            self.assertIn('seed_44_authorized', source)
            self.assertIn('exp_054_authorized', source)

    def test_private_artifacts_are_gitignored(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("private/", ignore)
        self.assertIn("runs/**/*.safetensors", ignore)
        self.assertIn("runs/**/*.npz", ignore)


if __name__ == "__main__":
    unittest.main()
