from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, MODULE_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = load_module("so_exp051_runner", "run_exp051_m1.py")
verifier = load_module("so_exp051_verifier", "verify_exp051_m1.py")


class SelectionTests(unittest.TestCase):
    def test_checkpoint_uses_strict_practical_tie_and_earliest_epoch(self):
        values = [0.60, 0.6049, 0.6051, 0.61, 0.609]
        history = [
            {"epoch": index + 1, "fixed_macro_f1": value}
            for index, value in enumerate(values)
        ]
        observed = runner.select_checkpoint(history, 0.005)
        independent = verifier.select_checkpoint(values, 0.005)
        self.assertEqual(observed, independent)
        self.assertEqual(observed["selected_epoch"], 3)
        self.assertEqual(observed["eligible_epochs"], [3, 4, 5])

    def test_threshold_ties_prefer_closest_to_half_then_lower(self):
        gold = np.asarray([[1, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]], dtype=np.uint8)
        probabilities = np.asarray(
            [[0.9, 0.1, 0.1, 0.1, 0.1, 0.1], [0.1, 0.1, 0.1, 0.1, 0.1, 0.1]],
            dtype=np.float32,
        )
        grid = [0.4, 0.5, 0.6]
        observed, rows = runner.select_threshold(gold, probabilities, grid)
        independent, independent_rows = verifier.select_threshold(gold, probabilities, grid)
        self.assertEqual(observed, 0.5)
        self.assertEqual(observed, independent)
        self.assertEqual(rows, independent_rows)


class MetricTests(unittest.TestCase):
    def test_metric_implementations_match(self):
        gold = np.asarray(
            [[1, 0, 0, 1, 0, 0], [0, 1, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]],
            dtype=np.uint8,
        )
        predicted = np.asarray(
            [[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]],
            dtype=np.uint8,
        )
        self.assertEqual(runner.metric_bundle(gold, predicted), verifier.metric_bundle(gold, predicted))

    def test_component_bootstrap_is_reproducible_and_independent(self):
        gold = np.asarray(
            [[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0], [0, 0, 0, 1, 0, 0]],
            dtype=np.uint8,
        )
        predicted = gold.copy()
        components = ["a", "a", "b"]
        first = runner.bootstrap_summary(gold, predicted, components, 42, 25, "unit", "fixed-0.5")
        second = verifier.bootstrap_summary(gold, predicted, components, 42, 25, "unit", "fixed-0.5")
        self.assertEqual(first, second)
        self.assertEqual(first["component_count"], 2)


class ContractTests(unittest.TestCase):
    def test_seed_42_only_and_test_denied(self):
        run_config, shared = runner.load_config(
            MODULE_DIR / "configs" / "exp-051-m1-roberta-seed-42.json", 42
        )
        self.assertEqual(run_config["authorization"]["seeds"], [42])
        self.assertFalse(run_config["authorization"]["test_access"])
        self.assertEqual(shared["data"]["model_access_whitelist"], ["train", "validation"])
        with self.assertRaises(PermissionError):
            runner.load_config(
                MODULE_DIR / "configs" / "exp-051-m1-roberta-seed-42.json", 43
            )

    def test_cpu_recovery_changes_only_execution_device_and_output_paths(self):
        primary = runner.json.loads(
            (MODULE_DIR / "configs" / "exp-051-m1-roberta-seed-42.json").read_text()
        )
        recovery = runner.json.loads(
            (MODULE_DIR / "configs" / "exp-051-m1-roberta-seed-42-cpu-recovery.json").read_text()
        )
        excluded = {
            "required_device",
            "maximum_wall_minutes",
            "public_run_root",
            "private_run_root",
        }
        primary_execution = {
            key: value for key, value in primary["execution"].items() if key not in excluded
        }
        recovery_execution = {
            key: value for key, value in recovery["execution"].items() if key not in excluded
        }
        self.assertEqual(primary_execution, recovery_execution)
        self.assertEqual(primary["authorization"]["seeds"], recovery["authorization"]["seeds"])
        self.assertEqual(primary["authorization"]["splits"], recovery["authorization"]["splits"])
        self.assertFalse(recovery["authorization"]["test_access"])

    def test_seed_43_is_separately_authorized_after_verified_seed_42(self):
        config_path = MODULE_DIR / "configs" / "exp-051-m1-roberta-seed-43-cpu.json"
        run_config, shared = runner.load_config(config_path, 43)
        self.assertEqual(run_config["authorization"]["seeds"], [43])
        self.assertFalse(run_config["authorization"]["test_access"])
        self.assertFalse(run_config["authorization"]["seed_44_authorized"])
        self.assertEqual(shared["data"]["model_access_whitelist"], ["train", "validation"])
        with self.assertRaises(PermissionError):
            runner.load_config(config_path, 42)
        with self.assertRaises(PermissionError):
            runner.load_config(config_path, 44)
        gate = runner.verify_prior_seed_gate(run_config, 43)
        self.assertEqual(gate["seed"], 42)
        self.assertEqual(gate["status"], "Passed")
        self.assertEqual(gate["verification_check_count"], 67)
        self.assertFalse(gate["test_split_accessed"])

    def test_seed_43_preserves_seed_42_scientific_execution_contract(self):
        seed_42 = runner.json.loads(
            (MODULE_DIR / "configs" / "exp-051-m1-roberta-seed-42-cpu-recovery.json").read_text()
        )
        seed_43 = runner.json.loads(
            (MODULE_DIR / "configs" / "exp-051-m1-roberta-seed-43-cpu.json").read_text()
        )
        excluded = {"public_run_root", "private_run_root"}
        execution_42 = {
            key: value for key, value in seed_42["execution"].items() if key not in excluded
        }
        execution_43 = {
            key: value for key, value in seed_43["execution"].items() if key not in excluded
        }
        self.assertEqual(execution_42, execution_43)
        self.assertEqual(seed_42["protocol_path"], seed_43["protocol_path"])
        self.assertEqual(seed_42["prerequisite"], seed_43["prerequisite"])

    def test_report_and_verifier_are_not_hardcoded_to_seed_42(self):
        report = runner.render_report(
            {
                "seed": 43,
                "status": "Completed",
                "selection": {"selected_epoch": 3},
                "threshold_selection": {"selected_threshold": 0.25},
                "metrics": {
                    "fixed_0.5": {"macro": {"f1": 0.5}},
                    "shared_threshold": {
                        "macro": {"f1": 0.6},
                        "micro_f1": 0.7,
                        "subset_accuracy": 0.8,
                        "per_label": {"surprise": {"f1": 0.0}},
                    },
                },
            }
        )
        self.assertIn("Seed 43 Validation", report)
        self.assertNotIn("Seed 42", report)
        verifier_source = (MODULE_DIR / "verify_exp051_m1.py").read_text()
        self.assertNotIn('config["authorization"]["seeds"] == [42]', verifier_source)

    def test_recovery_requires_train_only_preflight_and_preserves_failed_hashes(self):
        recovery = runner.json.loads(
            (MODULE_DIR / "configs" / "exp-051-m1-roberta-seed-42-cpu-recovery.json").read_text()
        )
        self.assertEqual(recovery["recovery"]["cpu_train_only_preflight_steps"], 10)
        self.assertTrue(recovery["recovery"]["mps_high_watermark_override_forbidden"])
        self.assertEqual(len(recovery["recovery"]["failed_run_sha256"]), 64)
        self.assertEqual(len(recovery["recovery"]["failed_log_sha256"]), 64)

    def test_formal_runner_fails_closed_on_recovery_preflight(self):
        source = (MODULE_DIR / "run_exp051_m1.py").read_text()
        self.assertIn("verify_recovery_preflight(run_config, args.config.resolve())", source)
        self.assertIn('"performance_metrics_computed": False', source)
        self.assertIn('"accessed_splits": ["train"]', source)

    def test_runner_source_has_explicit_split_boundary(self):
        audit = verifier.source_access_audit(MODULE_DIR / "run_exp051_m1.py")
        self.assertTrue(all(audit.values()), audit)


if __name__ == "__main__":
    unittest.main()
