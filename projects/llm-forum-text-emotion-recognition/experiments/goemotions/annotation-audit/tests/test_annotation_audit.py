#!/usr/bin/env python3
"""Local synthetic preflight for EXP-035 before the official archive pass."""

from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = load_module("exp035_runner", "run_annotation_audit.py")
finalizer = load_module("exp035_finalizer", "finalize_annotation_audit.py")
verifier = load_module("exp035_verifier", "verify_annotation_audit.py")


LABELS = [
    "admiration", "amusement", "anger", "annoyance", "approval", "caring",
    "confusion", "curiosity", "desire", "disappointment", "disapproval",
    "disgust", "embarrassment", "excitement", "fear", "gratitude", "grief",
    "joy", "love", "nervousness", "optimism", "pride", "realization",
    "relief", "remorse", "sadness", "surprise", "neutral",
]


def label_vector(*indices: int) -> list[int]:
    values = [0] * len(LABELS)
    for index in indices:
        values[index] = 1
    return values


class FakeResponse(io.BytesIO):
    def __init__(self, payload: bytes, etag: str) -> None:
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload)), "ETag": f'"{etag}"'}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


class AnnotationAuditPreflight(unittest.TestCase):
    def test_stream_source_hashes_and_retains_only_allowlisted_row(self) -> None:
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(runner.expected_header(LABELS))
        common = ["author", "sub", "link", "parent", "0"]
        writer.writerow(["kept text", "keep", *common, "rater-1", "false", *label_vector(2)])
        writer.writerow(["dropped text", "drop", *common, "rater-2", "false", *label_vector(27)])
        payload = output.getvalue().encode("utf-8")
        etag = hashlib.md5(payload).hexdigest()  # noqa: S324 - synthetic identity.
        source = {
            "content_length": len(payload),
            "etag": etag,
            "last_modified": "synthetic",
            "md5_base64": base64.b64encode(hashlib.md5(payload).digest()).decode("ascii"),
            "name": "synthetic.csv",
            "url": "https://invalid.local/synthetic.csv",
        }
        target = {
            "comment_id": "keep",
            "example_hash": runner.sha256_text("keep"),
            "source_train_row": 1,
            "text": "kept text",
            "text_sha256": runner.sha256_text("kept text"),
        }
        with mock.patch.object(
            runner.urllib.request,
            "urlopen",
            return_value=FakeResponse(payload, etag),
        ):
            records, manifest = runner.stream_source(
                source, LABELS, {"keep": target}
            )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["comment_id"], "keep")
        self.assertEqual(manifest["raw_annotation_rows"], 2)
        self.assertEqual(manifest["matched_annotation_rows"], 1)
        self.assertEqual(manifest["sha256"], hashlib.sha256(payload).hexdigest())

    def test_runner_and_verifier_recompute_same_aggregation_and_sample(self) -> None:
        selected = [
            {
                "comment_id": "a",
                "example_hash": runner.sha256_text("a"),
                "gold_label_ids": [2, 27],
                "gold_labels": ["anger", "neutral"],
                "source_train_row": 10,
            },
            {
                "comment_id": "b",
                "example_hash": runner.sha256_text("b"),
                "gold_label_ids": [17, 27],
                "gold_labels": ["joy", "neutral"],
                "source_train_row": 20,
            },
        ]
        records = []
        for rater, labels in enumerate(
            [label_vector(2), label_vector(2), label_vector(27), label_vector(27)],
            start=1,
        ):
            records.append(
                {"comment_id": "a", "labels": labels, "rater_hash": str(rater), "unclear": False}
            )
        for rater in range(2):
            records.append(
                {
                    "comment_id": "b",
                    "labels": label_vector(17, 27),
                    "rater_hash": f"b{rater}",
                    "unclear": False,
                }
            )

        run_rows, run_summary, run_emotions, run_patterns = runner.aggregate_rows(
            selected, records, LABELS
        )
        verify_rows, verify_summary, verify_emotions, verify_patterns = (
            verifier.recompute_quantitative(selected, records, LABELS)
        )
        self.assertEqual(run_rows, verify_rows)
        self.assertEqual(
            {**run_summary, **{
                "rater_count_distribution": {str(k): v for k, v in run_summary["rater_count_distribution"].items()},
                "unclear_count_distribution": {str(k): v for k, v in run_summary["unclear_count_distribution"].items()},
                "neutral_vote_distribution": {str(k): v for k, v in run_summary["neutral_vote_distribution"].items()},
                "same_rater_coselection_count_distribution": {
                    str(k): v for k, v in run_summary["same_rater_coselection_count_distribution"].items()
                },
            }},
            verify_summary,
        )
        self.assertEqual(run_emotions, verify_emotions)
        self.assertEqual(run_patterns, verify_patterns)

        config = {
            "qualitative_sample": {
                "maximum_rows": 2,
                "ranking_salt": "synthetic",
                "roles": [
                    {"name": "aggregation_only", "limit": 1},
                    {"name": "same_rater_coselection", "limit": 1},
                ],
            }
        }
        self.assertEqual(
            runner.select_sample(run_rows, config),
            verifier.recompute_sample(verify_rows, config),
        )

    def test_finalizer_and_verifier_render_same_report(self) -> None:
        aggregate = {
            "aggregation_only_rows": 7,
            "any_unclear_rows": 2,
            "decision": "annotation_aggregation_is_primary_for_target_structure",
            "official_threshold_reproduction_mismatches": 0,
            "rows": 10,
            "same_rater_coselection_rows": 3,
        }
        qualitative = {"annotation_rows": 4, "context_likely_needed_rows": 1}
        self.assertEqual(
            finalizer.render_report(aggregate, qualitative),
            verifier.render_report(aggregate, qualitative),
        )


if __name__ == "__main__":
    unittest.main()
