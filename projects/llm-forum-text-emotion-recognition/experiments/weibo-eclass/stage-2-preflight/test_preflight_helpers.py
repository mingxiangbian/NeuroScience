#!/usr/bin/env python3
"""Train-only contract tests for EXP-041 helpers."""

from __future__ import annotations

from collections import Counter
import json
import unittest

import run_preflight as runner


class PreflightHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(runner.CONFIG_PATH.read_text(encoding="utf-8"))
        cls.rows = runner.load_train(cls.config)
        cls.selected = runner.select_rows(cls.config, cls.rows)
        cls.prompt = runner.load_prompt(cls.config)

    def test_train_only_selection_covers_all_strata(self) -> None:
        counts = Counter(
            (row["label"], bool(row["context_available"])) for row in self.selected
        )
        self.assertEqual(len(self.rows), 5995)
        self.assertEqual(len(self.selected), 56)
        self.assertEqual(set(counts.values()), {4})
        self.assertEqual(len(counts), 14)

    def test_prompt_pair_changes_only_user_input(self) -> None:
        available = next(row for row in self.selected if row["context_available"])
        target = runner.prompt_messages(
            self.config, self.prompt, available, "target_only"
        )
        context = runner.prompt_messages(
            self.config, self.prompt, available, "previous_context"
        )
        self.assertEqual(target[0], context[0])
        self.assertNotEqual(target[1], context[1])
        self.assertIn(available["views"]["target_only"]["target"], context[1]["content"])

    def test_missing_context_pair_is_identical(self) -> None:
        missing = next(row for row in self.selected if not row["context_available"])
        self.assertEqual(
            runner.prompt_messages(self.config, self.prompt, missing, "target_only"),
            runner.prompt_messages(self.config, self.prompt, missing, "previous_context"),
        )

    def test_assistant_training_target_is_valid_json(self) -> None:
        row = self.selected[0]
        messages = runner.prompt_messages(
            self.config,
            self.prompt,
            row,
            "target_only",
            include_target=True,
        )
        self.assertEqual(json.loads(messages[-1]["content"]), {"label": row["label"]})

    def test_qwen_generation_budget_has_six_conditions(self) -> None:
        cases = runner.qwen_cases(self.config, self.selected)
        counts = Counter(condition for _, _, _, condition in cases)
        self.assertEqual(len(cases), 42)
        self.assertEqual(len(counts), 6)
        self.assertEqual(set(counts.values()), {7})

    def test_qwen_budget_correction_keeps_exp_040_seeds(self) -> None:
        inference = self.config["qwen"]["inference"]
        self.assertEqual(inference["generation_seed_namespace"], "EXP-040")
        self.assertEqual(inference["max_new_tokens"], 1024)

    def test_lora_runtime_is_train_only(self) -> None:
        runtime = runner.lora_runtime_config(self.config)
        self.assertTrue(runtime["train"])
        self.assertFalse(runtime["test"])
        self.assertEqual(runtime["val_batches"], 0)
        self.assertEqual(runtime["iters"], 2)
        self.assertEqual(
            runtime["lora_parameters"]["keys"],
            self.config["qwen"]["lora"]["target_modules"],
        )


if __name__ == "__main__":
    unittest.main()
