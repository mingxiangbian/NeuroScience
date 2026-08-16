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
aggregator = load_module("so_exp051_aggregator", "aggregate_exp051_m1.py")
aggregate_verifier = load_module("so_exp051_aggregate_verifier", "verify_exp051_aggregate.py")


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


class AggregateMethodTests(unittest.TestCase):
    def test_three_seed_summary_uses_sample_standard_deviation(self):
        observed = aggregator.scalar_summary([1.0, 2.0, 3.0])
        independent = aggregate_verifier.independent_summary([1.0, 2.0, 3.0])
        self.assertEqual(observed["mean"], 2.0)
        self.assertEqual(observed["sample_std"], 1.0)
        self.assertTrue(aggregate_verifier.values_match(observed, independent))

    def test_aggregate_sources_are_exactly_the_registered_three_seeds(self):
        self.assertEqual(list(aggregator.SOURCE_PATHS), [42, 43, 44])
        self.assertEqual(aggregator.EXPECTED_CHECK_COUNTS, {42: 67, 43: 72, 44: 72})
        source = (MODULE_DIR / "aggregate_exp051_m1.py").read_text()
        self.assertIn('"test_access": False', source)
        self.assertIn('"exp_052_authorized": False', source)
        self.assertIn('"pool_predictions_across_seeds": False', source)


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

    def test_seed_44_is_separately_authorized_after_verified_seed_43(self):
        config_path = MODULE_DIR / "configs" / "exp-051-m1-roberta-seed-44-cpu.json"
        run_config, shared = runner.load_config(config_path, 44)
        authorization = run_config["authorization"]
        self.assertEqual(authorization["seeds"], [44])
        self.assertFalse(authorization["test_access"])
        self.assertTrue(authorization["three_seed_validation_aggregation_authorized"])
        self.assertFalse(authorization["exp_052_authorized"])
        self.assertEqual(shared["data"]["model_access_whitelist"], ["train", "validation"])
        with self.assertRaises(PermissionError):
            runner.load_config(config_path, 42)
        with self.assertRaises(PermissionError):
            runner.load_config(config_path, 43)
        gate = runner.verify_prior_seed_gate(run_config, 44)
        self.assertEqual(gate["seed"], 43)
        self.assertEqual(gate["status"], "Passed")
        self.assertEqual(gate["verification_check_count"], 72)
        self.assertFalse(gate["test_split_accessed"])

    def test_seed_42_43_44_share_the_scientific_execution_contract(self):
        seed_42 = runner.json.loads(
            (MODULE_DIR / "configs" / "exp-051-m1-roberta-seed-42-cpu-recovery.json").read_text()
        )
        seed_43 = runner.json.loads(
            (MODULE_DIR / "configs" / "exp-051-m1-roberta-seed-43-cpu.json").read_text()
        )
        seed_44 = runner.json.loads(
            (MODULE_DIR / "configs" / "exp-051-m1-roberta-seed-44-cpu.json").read_text()
        )
        excluded = {"public_run_root", "private_run_root"}
        executions = [
            {key: value for key, value in config["execution"].items() if key not in excluded}
            for config in (seed_42, seed_43, seed_44)
        ]
        self.assertEqual(executions[0], executions[1])
        self.assertEqual(executions[1], executions[2])
        self.assertEqual(
            {config["protocol_path"] for config in (seed_42, seed_43, seed_44)},
            {seed_42["protocol_path"]},
        )
        self.assertEqual(seed_42["prerequisite"], seed_43["prerequisite"])
        self.assertEqual(seed_43["prerequisite"], seed_44["prerequisite"])

    def test_seed_44_gate_hashes_match_verified_seed_43_artifacts(self):
        config = runner.json.loads(
            (MODULE_DIR / "configs" / "exp-051-m1-roberta-seed-44-cpu.json").read_text()
        )
        gate = config["prior_seed_gate"]
        self.assertEqual(
            runner.sha256_file(runner.resolve_project(gate["run_path"])),
            gate["run_sha256"],
        )
        self.assertEqual(
            runner.sha256_file(runner.resolve_project(gate["verification_path"])),
            gate["verification_sha256"],
        )

    def test_report_and_verifier_are_not_hardcoded_to_seed_42(self):
        report = runner.render_report(
            {
                "seed": 44,
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
        self.assertIn("Seed 44 Validation", report)
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
