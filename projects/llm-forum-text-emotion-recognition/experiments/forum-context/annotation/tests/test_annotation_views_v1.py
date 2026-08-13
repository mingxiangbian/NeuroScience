#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ANNOTATION_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANNOTATION_DIR))

import export_annotation_views_v1 as exporter  # noqa: E402
import verify_annotation_views_v1 as verifier  # noqa: E402


def synthetic_view() -> dict[str, object]:
    return {
        "schema_version": "annotation-view-v1",
        "protocol_id": "DATA-FCTX-LABEL-V1",
        "dataset": {
            "name": "IAC 2.0",
            "subset": "4forums",
            "cleaning_pipeline_id": "DATA-FCTX-CLEAN-V2",
            "dedup_pipeline_id": "DATA-FCTX-DEDUP-V2",
        },
        "ids": {
            "sample_uid": "smp_" + "1" * 64,
            "thread_uid": "thr_" + "2" * 64,
            "parent_uid": "pst_" + "3" * 64,
            "target_uid": "pst_" + "4" * 64,
        },
        "context": {
            "discussion_title": "Synthetic discussion",
            "direct_parent_body": "Synthetic parent",
            "target_quotes": [
                {
                    "quote_index": 0,
                    "text": "Synthetic quote",
                    "source_relation": "direct_parent",
                    "truncated": False,
                    "altered": None,
                }
            ],
        },
        "target": {
            "body": "Synthetic target [[QUOTE]]",
            "full_with_quotes": (
                "Synthetic target [[QUOTE]] Synthetic quote [[/QUOTE]]"
            ),
        },
        "display_contract": {
            "stage_a": "target.body",
            "stage_b": "context+target",
            "stage_a_locked_before_stage_b": True,
            "future_replies_included": False,
            "ancestor_chain_included": False,
        },
    }


class QuoteExtractionTests(unittest.TestCase):
    def test_exporter_extracts_top_level_and_preserves_nested_marker(self) -> None:
        value = (
            "Before [[QUOTE]] outer [[QUOTE]] inner [[/QUOTE]] tail "
            "[[/QUOTE]] after [[QUOTE]] second [[/QUOTE]]"
        )
        self.assertEqual(
            exporter.extract_top_level_quote_blocks(value),
            ["outer [[QUOTE]] inner [[/QUOTE]] tail", "second"],
        )

    def test_independent_parser_matches_expected_blocks(self) -> None:
        value = "A [[QUOTE]] one [[/QUOTE]] B [[QUOTE]] two [[/QUOTE]]"
        self.assertEqual(verifier.extract_outer_quotes(value), ["one", "two"])

    def test_unbalanced_markers_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            exporter.extract_top_level_quote_blocks("[[QUOTE]] missing close")
        with self.assertRaises(ValueError):
            verifier.extract_outer_quotes("[[/QUOTE]] missing open")


class RelationTests(unittest.TestCase):
    def test_source_relations_are_distinct(self) -> None:
        self.assertEqual(
            exporter.source_relation(
                discussion_id=1,
                parent_post_id=2,
                quote_discussion_id=1,
                quote_post_id=2,
            ),
            "direct_parent",
        )
        self.assertEqual(
            exporter.source_relation(
                discussion_id=1,
                parent_post_id=2,
                quote_discussion_id=1,
                quote_post_id=9,
            ),
            "same_thread_other",
        )
        self.assertEqual(
            exporter.source_relation(
                discussion_id=1,
                parent_post_id=2,
                quote_discussion_id=None,
                quote_post_id=None,
            ),
            "external_or_unknown",
        )


class ContractTests(unittest.TestCase):
    def test_synthetic_view_passes_both_contract_checks(self) -> None:
        view = synthetic_view()
        exporter.validate_view_contract(view)
        self.assertEqual(verifier.validate_schema_contract(view), [])

    def test_sampling_metadata_is_rejected_from_view(self) -> None:
        view = synthetic_view()
        view["lane"] = "representative"
        self.assertIn("$.lane", verifier.collect_forbidden_keys(
            view, verifier.FORBIDDEN_VIEW_KEYS
        ))

    def test_public_report_scan_rejects_private_ids_and_text_fields(self) -> None:
        value = {
            "sample_uid": "smp_" + "a" * 64,
            "context": {"text": "private"},
        }
        violations = verifier.public_violations(value)
        self.assertTrue(any("sample_uid" in item for item in violations))
        self.assertTrue(any("HMAC" in item for item in violations))
        self.assertTrue(any("context" in item for item in violations))

    def test_public_aggregate_shape_passes_privacy_scan(self) -> None:
        value = {
            "view_rows": 120,
            "target_quote_blocks": 75,
            "combined_sha256": "a" * 64,
            "privacy": {"forum_text_emitted": False},
        }
        self.assertEqual(verifier.public_violations(value), [])

    def test_canonical_hash_implementations_match(self) -> None:
        view = synthetic_view()
        self.assertEqual(
            exporter.canonical_json_sha256(view),
            verifier.canonical_json_sha256(view),
        )


if __name__ == "__main__":
    unittest.main()
