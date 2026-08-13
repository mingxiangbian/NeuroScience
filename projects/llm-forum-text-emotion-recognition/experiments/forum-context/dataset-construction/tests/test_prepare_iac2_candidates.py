#!/usr/bin/env python3

from __future__ import annotations

import gzip
import importlib.util
import json
import sqlite3
import stat
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


prepare = load_module("prepare_iac2_candidates", ROOT / "prepare_iac2_candidates.py")
verify = load_module("verify_cleaning_output", ROOT / "verify_cleaning_output.py")


def mysql_value(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, int):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
    escaped = escaped.replace("\n", "\\n").replace("\r", "\\r")
    return f"'{escaped}'"


def insert_line(table: str, rows: list[tuple[object, ...]]) -> str:
    encoded_rows = [
        "(" + ",".join(mysql_value(value) for value in row) + ")" for row in rows
    ]
    return f"INSERT INTO `{table}` VALUES " + ",".join(encoded_rows) + ";\n"


class TextRuleTests(unittest.TestCase):
    def test_minimal_normalization_masks_identifiers_but_keeps_style(self) -> None:
        value = (
            "<p>HELLOOO!!! &amp; fine</p> test@example.com "
            "https://example.com @someone 192.168.1.5"
        )
        normalized = prepare.normalize_model_text(value)
        self.assertIn("HELLOOO!!!", normalized)
        self.assertIn("[[EMAIL]]", normalized)
        self.assertIn("[[URL]]", normalized)
        self.assertIn("[[MENTION]]", normalized)
        self.assertIn("[[IP]]", normalized)
        self.assertNotIn("<p>", normalized)

    def test_quote_text_is_inserted_at_schema_offset(self) -> None:
        raw = "Thanks!!!"
        quote = prepare.QuoteRecord(0, None, 0, b"Old words")
        views = prepare.derive_quote_views(raw, [quote])
        self.assertIn("Old words", views.model_full_source)
        self.assertNotIn("Old words", views.model_body_source)
        self.assertIn("[[QUOTE]]", views.model_body_source)
        self.assertEqual(views.offset_status_counts["valid_top_level"], 1)

        invalid = prepare.QuoteRecord(0, None, 99, b"Old words")
        invalid_views = prepare.derive_quote_views(raw, [invalid])
        self.assertEqual(invalid_views.model_body_source, raw)
        self.assertEqual(invalid_views.offset_status_counts["out_of_bounds"], 1)

    def test_nested_quote_offset_is_relative_to_parent_quote(self) -> None:
        quotes = [
            prepare.QuoteRecord(0, None, 0, b"Outer text"),
            prepare.QuoteRecord(1, 0, 5, b"Inner text"),
        ]
        views = prepare.derive_quote_views("Reply", quotes)
        self.assertIn("Outer", views.model_full_source)
        self.assertIn("Inner", views.model_full_source)
        self.assertNotIn("Outer", views.model_body_source)
        self.assertNotIn("Inner", views.model_body_source)
        self.assertEqual(views.offset_status_counts["valid_nested"], 1)
        self.assertEqual(views.inserted_top_level_count, 1)
        self.assertEqual(views.inserted_nested_count, 1)

    def test_hard_filters_remain_conservative(self) -> None:
        short = prepare.evaluate_post(b"No.", [])
        self.assertIsNone(short.hard_reason)
        self.assertIn("short", short.soft_flags)

        url_only = prepare.evaluate_post(b"https://example.com", [])
        self.assertIsNone(url_only.hard_reason)
        self.assertIn("url_only", url_only.soft_flags)

        placeholder = prepare.evaluate_post(b"[deleted]", [])
        self.assertEqual(placeholder.hard_reason, "placeholder")

        quote = prepare.QuoteRecord(0, None, 0, b"Old words")
        quote_only = prepare.evaluate_post(b"", [quote])
        self.assertEqual(quote_only.hard_reason, "quote_only")

    def test_hmac_ids_are_stable_and_domain_separated(self) -> None:
        key = bytes(range(32))
        self.assertEqual(
            prepare.make_uid(key, "post", 1, 2),
            prepare.make_uid(key, "post", 1, 2),
        )
        self.assertNotEqual(
            prepare.make_uid(key, "post", 1, 2),
            prepare.make_uid(key, "sample", 1, 2),
        )


class SyntheticPipelineTest(unittest.TestCase):
    def test_end_to_end_private_database_and_public_aggregates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "synthetic.sql.gz"
            protocol = root / "protocol.md"
            database = root / "private" / "cleaning.sqlite"
            key = root / "private" / "id-key.bin"
            report = root / "report.json"
            manifest = root / "manifest.json"
            verification = root / "verification.json"

            discussion_rows = [(1, "https://not-retained.example", "Synthetic title", 10)]
            post_rows = [
                (1, 1, 10, "2020-01-01 00:00:00", None, 0, 101, 0, 0, None),
                (1, 2, 11, "2020-01-01 00:01:00", 1, 0, 102, 0, 0, None),
                (1, 3, 12, "2020-01-01 00:02:00", 1, 0, 103, 0, 0, None),
                (1, 4, 13, "2020-01-01 00:03:00", 99, 1, 104, 0, 0, None),
                (1, 5, 14, "2020-01-01 00:04:00", 1, 0, 105, 0, 0, None),
                (1, 6, 15, "2020-01-01 00:05:00", 1, 0, 106, 0, 0, None),
            ]
            quote_rows = [
                (1, 2, 0, None, 0, 201, 1, 1, 0, 9, 0, 0),
                (1, 5, 0, None, 0, 201, 1, 1, 0, 9, 0, 0),
                (1, 6, 0, None, 99, 201, 1, 1, 0, 9, 0, 0),
            ]
            text_rows = [
                (101, "Parent text test@example.com"),
                (102, "Thanks!!!"),
                (103, "[deleted]"),
                (104, "An unresolved reply"),
                (105, ""),
                (106, "Different body"),
                (201, "Old words"),
            ]
            dump = "".join(
                (
                    insert_line("discussion", discussion_rows),
                    insert_line("post", post_rows),
                    insert_line("quote", quote_rows),
                    insert_line("text", text_rows),
                )
            )
            with gzip.open(source, "wb") as handle:
                handle.write(dump.encode("utf-8"))
            protocol.write_text("synthetic protocol\n", encoding="utf-8")

            result = prepare.prepare_dataset(
                Namespace(
                    source=source,
                    output_db=database,
                    id_key=key,
                    protocol=protocol,
                    report=report,
                    manifest=manifest,
                    replace=False,
                )
            )
            self.assertEqual(result["counts"]["declared_parent_candidates"], 5)
            self.assertEqual(result["counts"]["eligible_candidates"], 2)
            self.assertEqual(stat.S_IMODE(key.stat().st_mode), 0o600)

            connection = sqlite3.connect(database)
            try:
                target_two = connection.execute(
                    """
                    SELECT model_body, model_full FROM cleaned_posts
                    WHERE source_discussion_id = 1 AND source_post_id = 2
                    """
                ).fetchone()
                target_six_flags = {
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT flag FROM post_soft_flags
                        WHERE source_discussion_id = 1 AND source_post_id = 6
                        """
                    )
                }
            finally:
                connection.close()
            self.assertEqual(target_two[0], "[[QUOTE]]\nThanks!!!")
            self.assertIn("Old words", target_two[1])
            self.assertIn("quote_structure_unverified", target_six_flags)

            public_text = report.read_text(encoding="utf-8") + manifest.read_text(encoding="utf-8")
            self.assertNotIn("Thanks!!!", public_text)
            self.assertNotIn("Old words", public_text)
            self.assertNotIn("https://not-retained.example", public_text)

            verification_result = verify.verify(
                Namespace(
                    source=source,
                    db=database,
                    id_key=key,
                    script=ROOT / "prepare_iac2_candidates.py",
                    protocol=protocol,
                    report=report,
                    manifest=manifest,
                    output=verification,
                    repo_root=None,
                    replace=False,
                )
            )
            self.assertEqual(verification_result["status"], "passed")
            self.assertEqual(json.loads(verification.read_text())["mismatch_count"], 0)


if __name__ == "__main__":
    unittest.main()
