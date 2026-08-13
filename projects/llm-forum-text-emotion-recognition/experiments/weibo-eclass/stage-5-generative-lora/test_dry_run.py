#!/usr/bin/env python3
"""Unit tests for the EXP-047 no-model dry-run and verifier helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load_module("exp047_runner", SCRIPT_DIR / "run_dry_run.py")
VERIFIER = load_module("exp047_verifier", SCRIPT_DIR / "verify_dry_run.py")


class DryRunTests(unittest.TestCase):
    def test_numeric_summary_uses_interpolated_percentiles(self) -> None:
        values = list(range(1, 101))
        self.assertEqual(RUNNER.numeric_summary(values)["p50"], 50.5)
        self.assertEqual(RUNNER.numeric_summary(values)["p95"], 95.05)
        self.assertEqual(RUNNER.numeric_summary(values), VERIFIER.numeric_summary(values))

    def test_normalize_token_ids_rejects_batch_encoding_and_booleans(self) -> None:
        self.assertEqual(RUNNER.normalize_token_ids([1, 2, 3]), [1, 2, 3])
        with self.assertRaises(TypeError):
            RUNNER.normalize_token_ids({"input_ids": [1, 2, 3]})
        with self.assertRaises(TypeError):
            RUNNER.normalize_token_ids([1, True, 3])

    def test_render_messages_has_strict_label_only_target(self) -> None:
        config = {"data": {"labels": ["anger", "joy"]}}
        prompt = {
            "assistant_target_template": '{"label":"{label}"}',
            "label_definitions": {"anger": "a", "joy": "b"},
            "output_schema": '{"label":"<label>"}',
            "system_template": "{label_definitions}\n{output_schema}",
            "target_only_template": "Target: {target}",
        }
        row = {"label": "joy", "views": {"target_only": {"target": "example"}}}
        expected = RUNNER.render_messages(config, prompt, row)
        self.assertEqual(expected[-1], {"role": "assistant", "content": '{"label":"joy"}'})
        self.assertEqual(expected, VERIFIER.render_messages(config, prompt, row))

    def test_runtime_config_is_exactly_train_only_for_all_seeds(self) -> None:
        config = {
            "model": {"local_path": "models/qwen3-4b/mlx-bf16"},
            "paths": {"private_root": "data/private/exp-047"},
            "training": {
                "batch_size": 1,
                "dropout": 0.0,
                "grad_accumulation_steps": 1,
                "grad_checkpoint": True,
                "iterations_per_epoch": 5995,
                "learning_rate": 0.00001,
                "lr_schedule": None,
                "mask_prompt": True,
                "max_sequence_length": 512,
                "num_layers": 16,
                "optimizer": "adamw",
                "optimizer_config": {"adamw": {}},
                "rank": 8,
                "scale": 20.0,
                "seeds": [42, 43, 44],
                "target_modules": ["self_attn.q_proj"],
                "total_iterations_per_seed": 11990,
            },
        }
        for seed in config["training"]["seeds"]:
            runtime = RUNNER.build_runtime_config(config, seed)
            RUNNER.validate_runtime(config, runtime, seed)
            self.assertEqual(runtime, VERIFIER.expected_runtime_config(config, seed))
            self.assertTrue(runtime["train"])
            self.assertFalse(runtime["test"])
            self.assertEqual(runtime["val_batches"], 0)

    def test_runner_source_exposes_no_model_execution_route(self) -> None:
        audit = VERIFIER.inspect_runner_source(SCRIPT_DIR / "run_dry_run.py")
        self.assertTrue(audit["passed"], audit)
        self.assertEqual(audit["command_choices"], ["dry-run"])
        self.assertEqual(audit["from_pretrained_calls"], ["AutoTokenizer.from_pretrained"])


if __name__ == "__main__":
    unittest.main()
