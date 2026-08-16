from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MODULE_DIR.parents[2]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, MODULE_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = load_module("so_exp053_preflight_runner", "run_exp053_m3_preflight.py")
verifier = load_module("so_exp053_preflight_verifier", "verify_exp053_m3_preflight.py")


class SelectionTests(unittest.TestCase):
    @staticmethod
    def rows():
        rows = []
        for index in range(96):
            labels = [0] * 6
            labels[index % 6] = 1
            rows.append(
                {
                    "sample_id": f"single-{index:03d}",
                    "component_id": f"component-single-{index:03d}",
                    "labels": labels,
                    "label_cardinality": 1,
                    "neutral": False,
                }
            )
        for index in range(12):
            rows.append(
                {
                    "sample_id": f"neutral-{index:03d}",
                    "component_id": f"component-neutral-{index:03d}",
                    "labels": [0] * 6,
                    "label_cardinality": 0,
                    "neutral": True,
                }
            )
        for index in range(12):
            labels = [0] * 6
            labels[index % 6] = 1
            labels[(index + 1) % 6] = 1
            rows.append(
                {
                    "sample_id": f"multi-{index:03d}",
                    "component_id": f"component-multi-{index:03d}",
                    "labels": labels,
                    "label_cardinality": 2,
                    "neutral": False,
                }
            )
        return rows

    def test_selection_is_deterministic_covered_and_independently_reproduced(self):
        rows = self.rows()
        token_counts = {row["sample_id"]: index + 10 for index, row in enumerate(rows)}
        labels = ["love", "joy", "surprise", "anger", "sadness", "fear"]
        arguments = (token_counts, labels, "unit-exp053-v1", 32)
        first = runner.select_length_aware_rows(rows, *arguments)
        reversed_result = runner.select_length_aware_rows(list(reversed(rows)), *arguments)
        independent = verifier.select_length_aware_rows(rows, *arguments)

        expected_ids = [row["sample_id"] for row in first]
        self.assertEqual(expected_ids, [row["sample_id"] for row in reversed_result])
        self.assertEqual(expected_ids, [row["sample_id"] for row in independent])
        self.assertEqual(len(first), 32)
        self.assertGreaterEqual(sum(row["neutral"] for row in first), 4)
        self.assertGreaterEqual(sum(row["label_cardinality"] == 2 for row in first), 4)
        for index in range(6):
            self.assertGreaterEqual(sum(row["labels"][index] for row in first), 1)

        selected_lengths = [token_counts[row["sample_id"]] for row in first]
        full_lengths = sorted(token_counts.values())
        self.assertLessEqual(min(selected_lengths), full_lengths[len(full_lengths) // 10])
        self.assertGreaterEqual(max(selected_lengths), full_lengths[len(full_lengths) * 9 // 10])

    def test_selection_rejects_an_undersized_contract(self):
        rows = self.rows()
        token_counts = {row["sample_id"]: index + 10 for index, row in enumerate(rows)}
        labels = ["love", "joy", "surprise", "anger", "sadness", "fear"]
        with self.assertRaises(ValueError):
            runner.select_length_aware_rows(rows, token_counts, labels, "unit-exp053-v1", 12)


class ContractTests(unittest.TestCase):
    def test_runtime_projection_uses_validation_count_only_as_cost_metadata(self):
        observed = runner.project_runtime(
            model_load_seconds=10.0,
            tokenization_seconds=20.0,
            train_step_seconds=[5.0, 5.0, 2.0, 2.0, 2.0, 2.0],
            forward_seconds=[1.0, 1.0],
            checkpoint_write_seconds=10.0,
            train_rows=100,
            validation_rows=20,
            formal_steps=100,
            safety_factor=1.5,
            warmup_steps=2,
        )
        self.assertEqual(observed["raw_per_seed_seconds"], 264.0)
        self.assertEqual(observed["projected_per_seed_seconds_with_safety"], 396.0)
        self.assertAlmostEqual(observed["projected_per_seed_hours_with_safety"], 0.11)
        self.assertAlmostEqual(observed["projected_three_seed_hours_with_safety"], 0.33)

    def test_trainable_whitelist_excludes_frozen_base_parameters(self):
        self.assertTrue(runner.trainable_name_allowed("head.weight"))
        self.assertTrue(runner.trainable_name_allowed("head.bias"))
        self.assertTrue(
            runner.trainable_name_allowed(
                "backbone.model.layers.20.self_attn.q_proj.lora_a"
            )
        )
        self.assertFalse(
            runner.trainable_name_allowed("backbone.model.layers.20.self_attn.q_proj.weight")
        )
        self.assertFalse(runner.trainable_name_allowed("backbone.lm_head.weight"))

    def test_authorization_is_train_only_and_non_performance(self):
        protocol = (
            PROJECT_ROOT
            / "experiments/stack-overflow-emotion-gold/protocols/exp-053-m3-resource-preflight-authorization.md"
        ).read_text(encoding="utf-8")
        self.assertIn("read the frozen `DATA-SO-TASK-V1` train split only", protocol)
        self.assertIn("It may not:", protocol)
        self.assertIn("read validation or test rows", protocol)
        self.assertIn("does not authorize formal training", protocol)

    def test_config_freezes_resource_gate_without_formal_authorization(self):
        config_path = (
            MODULE_DIR / "configs/exp-053-m3-resource-preflight-seed-42-attempt-2.json"
        )
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["experiment_id"], "EXP-053")
        self.assertEqual(config["stage"], "train-only-resource-preflight")
        self.assertEqual(config["authorization"]["seeds"], [42])
        self.assertEqual(config["authorization"]["splits"], ["train"])
        self.assertFalse(config["authorization"]["validation_access"])
        self.assertFalse(config["authorization"]["test_access"])
        self.assertFalse(config["authorization"]["formal_training"])
        self.assertFalse(config["formal_execution_authorized"])
        self.assertEqual(config["sampling"]["sample_rows"], 32)
        self.assertEqual(config["execution"]["projection_safety_factor"], 1.5)
        self.assertEqual(config["execution"]["maximum_peak_memory_gb"], 13.0)
        self.assertEqual(config["execution"]["maximum_projected_hours_per_seed"], 8.0)
        self.assertEqual(
            config["execution"]["maximum_projected_hours_three_seeds"], 24.0
        )

    def test_config_binds_verified_exp050_and_exp052_evidence(self):
        config_path = (
            MODULE_DIR / "configs/exp-053-m3-resource-preflight-seed-42-attempt-2.json"
        )
        config = json.loads(config_path.read_text(encoding="utf-8"))
        prerequisites = config["prerequisites"]
        self.assertIn("m3", prerequisites["exp050"])
        self.assertIn("run", prerequisites["m2_seed_42"])
        self.assertIn("verification", prerequisites["m2_seed_42"])
        self.assertIn("aggregate", prerequisites["m2_aggregate"])
        self.assertIn("verification", prerequisites["m2_aggregate"])

    def test_frozen_config_and_prerequisite_schemas_are_accepted(self):
        config_path = (
            MODULE_DIR / "configs/exp-053-m3-resource-preflight-seed-42-attempt-2.json"
        )
        config = runner.load_config(config_path)
        shared, m2_run = runner.validate_prerequisites(config)
        self.assertEqual(shared["data"]["protocol_id"], "DATA-SO-TASK-V1")
        self.assertEqual(
            m2_run["model_runtime"]["head_initial_sha256"],
            config["execution"]["expected_head_initial_sha256"],
        )

    def test_attempt_two_releases_training_references_before_checkpoint_replay(self):
        source = (MODULE_DIR / "run_exp053_m3_preflight.py").read_text(encoding="utf-8")
        cleanup_position = source.index("del (\n        wrapper,")
        reset_position = source.index("mx.reset_peak_memory()", cleanup_position)
        reload_position = source.index("reloaded_model, reloaded_tokenizer = load", reset_position)
        self.assertLess(cleanup_position, reset_position)
        self.assertLess(reset_position, reload_position)
        self.assertIn("training_phase_peak_memory_gb", source)
        self.assertIn("replay_phase_peak_memory_gb", source)

    def test_runner_does_not_load_validation_or_test_artifacts(self):
        source = (MODULE_DIR / "run_exp053_m3_preflight.py").read_text(encoding="utf-8")
        self.assertNotIn('shared["data"]["validation_path"]', source)
        self.assertNotIn('shared["data"]["test_path"]', source)
        self.assertNotIn("load_validation(", source)
        self.assertNotIn("load_test(", source)
        self.assertIn('"accessed_splits": ["train"]', source)
        self.assertIn('"performance_metrics_computed": False', source)

    def test_verifier_is_independent_of_runner(self):
        source = (MODULE_DIR / "verify_exp053_m3_preflight.py").read_text(encoding="utf-8")
        self.assertNotIn("import run_exp053_m3_preflight", source)
        self.assertNotIn("from run_exp053_m3_preflight", source)
        self.assertIn("def select_length_aware_rows(", source)
        self.assertIn("def projected_runtime(", source)

    def test_private_artifacts_are_gitignored(self):
        ignore = (MODULE_DIR / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("private/", ignore)
        self.assertIn("runs/**/*.safetensors", ignore)


if __name__ == "__main__":
    unittest.main()
