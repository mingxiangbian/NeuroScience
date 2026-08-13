#!/usr/bin/env python3
"""Pure-function tests for the EXP-047 seed-42 replay gate."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER_PATH = SCRIPT_DIR / "run_seed42_replay.py"
SPEC = importlib.util.spec_from_file_location("exp047_seed42_replay", RUNNER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load replay runner")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
VERIFIER_PATH = SCRIPT_DIR / "verify_seed42_replay.py"
VERIFIER_SPEC = importlib.util.spec_from_file_location("exp047_seed42_replay_verifier", VERIFIER_PATH)
if VERIFIER_SPEC is None or VERIFIER_SPEC.loader is None:
    raise RuntimeError("Unable to load replay verifier")
VERIFIER = importlib.util.module_from_spec(VERIFIER_SPEC)
VERIFIER_SPEC.loader.exec_module(VERIFIER)


class Seed42ReplayTests(unittest.TestCase):
    def test_generated_token_count_retokenizes_output(self) -> None:
        class Tokenizer:
            def encode(self, value: str, *, add_special_tokens: bool) -> list[int]:
                self.call = (value, add_special_tokens)
                return [3, 5, 8]

        tokenizer = Tokenizer()
        self.assertEqual(VERIFIER.generated_token_count(tokenizer, "answer"), 3)
        self.assertEqual(tokenizer.call, ("answer", False))

    def test_selection_digest_is_order_sensitive(self) -> None:
        rows = [{"selector_sha256": "a"}, {"selector_sha256": "b"}]
        self.assertNotEqual(RUNNER.selection_digest(rows), RUNNER.selection_digest(list(reversed(rows))))

    def test_compare_records_counts_all_three_states(self) -> None:
        left = [
            {
                "selection_index": 0,
                "prediction": "anger",
                "parse": {"valid": True, "label": "anger"},
                "raw_output_sha256": "a",
            },
            {
                "selection_index": 1,
                "prediction": "joy",
                "parse": {"valid": True, "label": "joy"},
                "raw_output_sha256": "b",
            },
        ]
        right = [
            dict(left[0]),
            {
                "selection_index": 1,
                "prediction": "joy",
                "parse": {"valid": True, "label": "joy"},
                "raw_output_sha256": "different",
            },
        ]
        comparison = RUNNER.compare_records(left, right)
        self.assertEqual(comparison["final_label_equal_count"], 2)
        self.assertEqual(comparison["parser_state_equal_count"], 2)
        self.assertEqual(comparison["raw_output_equal_count"], 1)

    def test_compare_records_rejects_row_set_drift(self) -> None:
        left = [{"selection_index": 0}]
        right = [{"selection_index": 1}]
        with self.assertRaises(ValueError):
            RUNNER.compare_records(left, right)

    def test_token_ids_reject_boolean(self) -> None:
        with self.assertRaises(TypeError):
            RUNNER.require_token_ids([1, True, 2])


if __name__ == "__main__":
    unittest.main(verbosity=2)
