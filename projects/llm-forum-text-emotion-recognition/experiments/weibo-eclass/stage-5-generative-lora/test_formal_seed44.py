#!/usr/bin/env python3
"""Static and pure-function tests for the EXP-047 seed-44 formal runner."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER_PATH = SCRIPT_DIR / "run_formal_seed44.py"
SPEC = importlib.util.spec_from_file_location("exp047_formal_runner", RUNNER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load the formal runner module")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class FormalSeed44Tests(unittest.TestCase):
    def test_log_parser_extracts_expected_fields(self) -> None:
        contents = "\n".join(
            [
                "Trainable parameters: 0.182% (7.340M/4022.468M)",
                "Iter 10: Train loss 0.321, Learning Rate 1.000e-05, It/sec 0.575, "
                "Tokens/sec 120.5, Trained Tokens 2096, Peak mem 8.679 GB",
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stdout.log"
            path.write_text(contents + "\n", encoding="utf-8")
            history, trainable = RUNNER.parse_training_log(path)
        self.assertEqual(history[0]["iteration"], 10)
        self.assertEqual(history[0]["trained_tokens"], 2096)
        self.assertEqual(history[0]["learning_rate"], 1e-5)
        self.assertEqual(trainable["trainable_millions"], 7.34)

    def test_log_parser_rejects_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stdout.log"
            path.write_text("Traceback (most recent call last):\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                RUNNER.parse_training_log(path)

    def test_expected_adapter_key_contract(self) -> None:
        runtime = {
            "num_layers": 16,
            "lora_parameters": {
                "keys": [
                    "self_attn.q_proj",
                    "self_attn.k_proj",
                    "self_attn.v_proj",
                    "self_attn.o_proj",
                    "mlp.gate_proj",
                    "mlp.up_proj",
                    "mlp.down_proj",
                ]
            },
        }
        keys = RUNNER.expected_adapter_keys(runtime, 36)
        self.assertEqual(len(keys), 224)
        self.assertIn("model.layers.20.self_attn.q_proj.lora_a", keys)
        self.assertIn("model.layers.35.mlp.down_proj.lora_b", keys)
        self.assertFalse(any("model.layers.19." in key for key in keys))

    def test_runner_exposes_train_only_command(self) -> None:
        tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
        subcommands = {
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_parser"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        }
        self.assertEqual(subcommands, {"train"})

    def test_project_path_rejects_escape(self) -> None:
        with self.assertRaises(ValueError):
            RUNNER.resolve_project_path("../../../../outside")


if __name__ == "__main__":
    unittest.main(verbosity=2)
