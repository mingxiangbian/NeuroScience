#!/usr/bin/env python3
"""Unit tests for the frozen single-label output contract."""

from __future__ import annotations

import unittest

from label_parser import parse_final_label


class LabelParserTests(unittest.TestCase):
    def test_nonthinking_exact_json(self) -> None:
        result = parse_final_label('{"label":"joy"}', thinking=False)
        self.assertTrue(result.valid)
        self.assertEqual(result.label, "joy")
        self.assertEqual(result.canonical_output, '{"label":"joy"}')

    def test_nonthinking_allows_outer_whitespace(self) -> None:
        self.assertTrue(parse_final_label(' \n {"label": "anger"}\n', thinking=False).valid)

    def test_nonthinking_rejects_markdown(self) -> None:
        result = parse_final_label('```json\n{"label":"joy"}\n```', thinking=False)
        self.assertEqual(result.error, "invalid_json")

    def test_nonthinking_rejects_thinking_markers(self) -> None:
        result = parse_final_label('</think>{"label":"joy"}', thinking=False)
        self.assertEqual(result.error, "thinking_marker_in_nonthinking_output")

    def test_thinking_accepts_generated_opening_marker(self) -> None:
        output = '<think>理由</think>\n{"label":"negative"}'
        result = parse_final_label(output, thinking=True)
        self.assertTrue(result.valid)
        self.assertTrue(result.opening_marker_found)

    def test_thinking_accepts_template_prefilled_opening_marker(self) -> None:
        output = '理由文本\n</think>\n{"label":"sadness"}'
        result = parse_final_label(output, thinking=True)
        self.assertTrue(result.valid)
        self.assertFalse(result.opening_marker_found)

    def test_thinking_requires_one_close_boundary(self) -> None:
        self.assertEqual(
            parse_final_label('{"label":"joy"}', thinking=True).error,
            "missing_thinking_boundary",
        )
        self.assertEqual(
            parse_final_label('</think></think>{"label":"joy"}', thinking=True).error,
            "multiple_thinking_boundaries",
        )

    def test_rejects_extra_key(self) -> None:
        result = parse_final_label('{"label":"joy","reason":"x"}', thinking=False)
        self.assertEqual(result.error, "schema_keys_mismatch")

    def test_rejects_unknown_or_multiple_labels(self) -> None:
        self.assertEqual(
            parse_final_label('{"label":"fear"}', thinking=False).error,
            "unknown_label",
        )
        self.assertEqual(
            parse_final_label('{"label":["joy","positive"]}', thinking=False).error,
            "label_not_string",
        )

    def test_rejects_trailing_text(self) -> None:
        result = parse_final_label('{"label":"neutral"}\nDone', thinking=False)
        self.assertEqual(result.error, "invalid_json")


if __name__ == "__main__":
    unittest.main()
