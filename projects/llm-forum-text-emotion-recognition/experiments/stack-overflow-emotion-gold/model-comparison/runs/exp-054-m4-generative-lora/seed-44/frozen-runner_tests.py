#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = load("exp054_runner_tests", ROOT / "run_exp054_m4.py")
strict_parser = load("exp054_parser_tests", ROOT / "strict_multilabel_parser.py")


class FakeTokenizer:
    def apply_chat_template(self, messages, **kwargs):
        text = messages[1]["content"]
        prefix = [10, 11] + [20] * max(1, len(text) // 20) + [30, 31]
        if messages[-1]["role"] == "assistant":
            return prefix + [40] * max(2, len(messages[-1]["content"]) // 4) + [50]
        return prefix

    def decode(self, ids, **kwargs):
        return "<think>\n\n</think>\n\n"

    def encode(self, text, **kwargs):
        return [1] * len(text)


class Exp054RunnerTests(unittest.TestCase):
    def test_assistant_only_mask_excludes_prompt(self):
        row = {"text": "example", "labels": [1, 0, 0, 1, 0, 0]}
        prompt = {"system": "system", "user_prefix": "text: ", "user_suffix": ""}
        inputs, targets, weights, summary = runner.m4_sequence(
            FakeTokenizer(), prompt, row, 384, strict_parser
        )
        self.assertEqual(len(inputs), len(targets))
        self.assertEqual(len(weights), len(targets))
        self.assertTrue(all(value == 0 for value in weights[:summary["prompt_tokens"] - 1]))
        self.assertTrue(all(value == 1 for value in weights[summary["prompt_tokens"] - 1:]))
        self.assertEqual(summary["canonical_target"], '{"emotions":["love","anger"]}')

    def test_selection_uses_earlier_practical_tie(self):
        selected = runner.select_checkpoint(
            [{"epoch": 1, "macro_f1": 0.601}, {"epoch": 2, "macro_f1": 0.605}], 0.005
        )
        self.assertEqual(selected["selected_epoch"], 1)

    def test_selection_uses_later_material_improvement(self):
        selected = runner.select_checkpoint(
            [{"epoch": 1, "macro_f1": 0.599}, {"epoch": 2, "macro_f1": 0.605}], 0.005
        )
        self.assertEqual(selected["selected_epoch"], 2)

    def test_perfect_metrics(self):
        gold = np.asarray([[1, 0, 0, 0, 0, 0], [0, 0, 0, 1, 0, 0]], dtype=np.uint8)
        metrics = runner.metric_bundle(gold, gold.copy())
        self.assertEqual(metrics["macro"]["f1"], 1 / 3)
        self.assertEqual(metrics["subset_accuracy"], 1.0)
        self.assertEqual(metrics["hamming_loss"], 0.0)

    def test_replay_subset_is_order_independent(self):
        rows = [{"sample_id": value} for value in ("c", "a", "b", "d")]
        first = runner.replay_subset(rows, 3, "namespace")
        second = runner.replay_subset(list(reversed(rows)), 3, "namespace")
        self.assertEqual([row["sample_id"] for row in first], [row["sample_id"] for row in second])

    def test_invalid_parser_output_is_all_zero(self):
        parsed = strict_parser.parse_output('{"emotions":["anger","love"]}')
        self.assertFalse(parsed["valid"])
        self.assertEqual(parsed["error"], "noncanonical_order")
        self.assertEqual(parsed["vector"], [0] * 6)

    def test_source_does_not_resolve_test_split(self):
        source = (ROOT / "run_exp054_m4.py").read_text(encoding="utf-8")
        self.assertNotIn('load_split(shared, "test")', source)
        self.assertNotIn("test_path", source)


if __name__ == "__main__":
    unittest.main()
