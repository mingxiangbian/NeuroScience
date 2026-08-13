#!/usr/bin/env python3
"""Export the private DATA-FCTX-LABEL-V1 annotation views."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


LABEL_PROTOCOL_ID = "DATA-FCTX-LABEL-V1"
SAMPLE_PROTOCOL_ID = "DATA-FCTX-SAMPLE-V1"
VIEW_SCHEMA_VERSION = "annotation-view-v1"
EXPECTED_CLEANING_SHA256 = (
    "b1f3022320980c96c5353be16401764a78e0bc40ebb21d71399fe4efcb05fcc7"
)
EXPECTED_DEDUP_SHA256 = (
    "13a5266a12f9574f073c3c7ce72e785e7d019573961507e1b0631f0a50bd7d4f"
)
EXPECTED_LABEL_PROTOCOL_SHA256 = (
    "0de4bf6243f223ea1a72b3fa48867b59abf6cd19ff95104ff53d00856b0d376a"
)
EXPECTED_VIEW_SCHEMA_SHA256 = (
    "9441981a27f2869d877641809742134de32712392d535355e2b4425ef59e4202"
)
QUOTE_TOKEN_RE = re.compile(r"\[\[(?:/)?QUOTE\]\]")
HMAC_PATTERNS: Mapping[str, re.Pattern[str]] = {
    "sample_uid": re.compile(r"^smp_[0-9a-f]{64}$"),
    "thread_uid": re.compile(r"^thr_[0-9a-f]{64}$"),
    "parent_uid": re.compile(r"^pst_[0-9a-f]{64}$"),
    "target_uid": re.compile(r"^pst_[0-9a-f]{64}$"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleaning-db", type=Path, required=True)
    parser.add_argument("--dedup-db", type=Path, required=True)
    parser.add_argument("--sampling-manifest", type=Path, required=True)
    parser.add_argument("--sampling-report", type=Path, required=True)
    parser.add_argument("--sampling-verification", type=Path, required=True)
    parser.add_argument("--label-protocol", type=Path, required=True)
    parser.add_argument("--view-schema", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path.name}")
    return value


def read_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                raise ValueError(f"blank JSONL row at {path.name}:{line_number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"non-object row at {path.name}:{line_number}")
            records.append(value)
    return records


def is_gitignored(repo_root: Path, path: Path) -> bool:
    return (
        subprocess.run(
            ["git", "check-ignore", "-q", str(path.resolve())],
            cwd=repo_root,
            check=False,
        ).returncode
        == 0
    )


def mode(path: Path) -> str:
    return oct(stat.S_IMODE(path.stat().st_mode))


def extract_top_level_quote_blocks(model_full: str) -> list[str]:
    blocks: list[str] = []
    depth = 0
    block_start: int | None = None
    for token in QUOTE_TOKEN_RE.finditer(model_full):
        if token.group() == "[[QUOTE]]":
            if depth == 0:
                block_start = token.end()
            depth += 1
            continue
        if depth == 0:
            raise ValueError("target model_full contains an unmatched quote close marker")
        depth -= 1
        if depth == 0:
            if block_start is None:
                raise ValueError("target model_full quote start was not recorded")
            text = model_full[block_start : token.start()].strip()
            if not text:
                raise ValueError("target model_full contains an empty top-level quote")
            blocks.append(text)
            block_start = None
    if depth != 0:
        raise ValueError("target model_full contains an unclosed quote marker")
    return blocks


def source_relation(
    *,
    discussion_id: int,
    parent_post_id: int,
    quote_discussion_id: int | None,
    quote_post_id: int | None,
) -> str:
    if (
        quote_discussion_id == discussion_id
        and quote_post_id == parent_post_id
    ):
        return "direct_parent"
    if quote_discussion_id == discussion_id and quote_post_id is not None:
        return "same_thread_other"
    return "external_or_unknown"


def nullable_bool(value: object) -> bool | None:
    if value is None:
        return None
    if value in (0, 1):
        return bool(value)
    raise ValueError(f"expected nullable boolean, got {value!r}")


def validate_manifest(records: Sequence[dict[str, object]]) -> None:
    if len(records) != 120:
        raise ValueError(f"sampling manifest must contain 120 rows, got {len(records)}")
    expected_orders = list(range(1, 121))
    actual_orders = [int(record.get("annotation_order", -1)) for record in records]
    if actual_orders != expected_orders:
        raise ValueError("sampling manifest must be ordered from annotation_order 1 to 120")
    if len({record.get("sample_uid") for record in records}) != 120:
        raise ValueError("sampling manifest sample_uid values are not unique")
    if len({record.get("thread_uid") for record in records}) != 120:
        raise ValueError("sampling manifest thread_uid values are not unique")
    for record in records:
        if record.get("protocol_id") != SAMPLE_PROTOCOL_ID:
            raise ValueError("sampling manifest protocol mismatch")
        if record.get("role") != "primary":
            raise ValueError("sampling manifest contains a non-primary row")
        for key in ("sample_uid", "thread_uid"):
            if not HMAC_PATTERNS[key].fullmatch(str(record.get(key, ""))):
                raise ValueError(f"invalid private {key}")


def validate_view_contract(view: dict[str, object]) -> None:
    if set(view) != {
        "schema_version",
        "protocol_id",
        "dataset",
        "ids",
        "context",
        "target",
        "display_contract",
    }:
        raise ValueError("annotation view has unexpected top-level keys")
    if view["schema_version"] != VIEW_SCHEMA_VERSION:
        raise ValueError("annotation view schema version mismatch")
    if view["protocol_id"] != LABEL_PROTOCOL_ID:
        raise ValueError("annotation view protocol mismatch")
    ids = view["ids"]
    if not isinstance(ids, dict) or set(ids) != set(HMAC_PATTERNS):
        raise ValueError("annotation view IDs do not match the frozen contract")
    for key, pattern in HMAC_PATTERNS.items():
        if not pattern.fullmatch(str(ids[key])):
            raise ValueError(f"invalid annotation view {key}")
    context = view["context"]
    target = view["target"]
    if not isinstance(context, dict) or not isinstance(target, dict):
        raise ValueError("annotation view text sections must be objects")
    for text in (
        context.get("discussion_title"),
        context.get("direct_parent_body"),
        target.get("body"),
        target.get("full_with_quotes"),
    ):
        if not isinstance(text, str) or not text:
            raise ValueError("annotation view contains an empty required text field")
    quotes = context.get("target_quotes")
    if not isinstance(quotes, list):
        raise ValueError("annotation view target_quotes must be a list")
    for quote in quotes:
        if not isinstance(quote, dict) or not isinstance(quote.get("text"), str):
            raise ValueError("annotation view contains an invalid quote block")
        if not quote["text"]:
            raise ValueError("annotation view contains an empty quote block")
    if view["display_contract"] != {
        "stage_a": "target.body",
        "stage_b": "context+target",
        "stage_a_locked_before_stage_b": True,
        "future_replies_included": False,
        "ancestor_chain_included": False,
    }:
        raise ValueError("annotation view display contract mismatch")


def load_selected_rows(
    cleaning_db: Path,
    dedup_db: Path,
    manifest: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    connection = sqlite3.connect(f"file:{cleaning_db.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("ATTACH DATABASE ? AS dedup", (str(dedup_db.resolve()),))
    try:
        selected: list[dict[str, object]] = []
        for manifest_row in manifest:
            sample_uid = str(manifest_row["sample_uid"])
            row = connection.execute(
                """
                SELECT cp.sample_uid,
                       cp.thread_uid,
                       cp.source_discussion_id,
                       cp.target_source_post_id,
                       cp.parent_source_post_id,
                       cp.target_post_uid,
                       cp.parent_post_uid,
                       cp.eligible,
                       discussion.title_model,
                       parent.model_body AS parent_model_body,
                       target.model_body AS target_model_body,
                       target.model_full AS target_model_full,
                       decision.eligible_after_auto_dedup,
                       decision.review_cluster_uid
                FROM candidate_pairs AS cp
                JOIN dedup.candidate_decisions AS decision
                  ON decision.sample_uid = cp.sample_uid
                JOIN discussions AS discussion
                  ON discussion.source_discussion_id = cp.source_discussion_id
                JOIN cleaned_posts AS parent
                  ON parent.source_discussion_id = cp.source_discussion_id
                 AND parent.source_post_id = cp.parent_source_post_id
                JOIN cleaned_posts AS target
                  ON target.source_discussion_id = cp.source_discussion_id
                 AND target.source_post_id = cp.target_source_post_id
                WHERE cp.sample_uid = ?
                """,
                (sample_uid,),
            ).fetchone()
            if row is None:
                raise ValueError("manifest sample is absent from the cleaning database")
            if not row["eligible"] or not row["eligible_after_auto_dedup"]:
                raise ValueError("manifest sample is not eligible after frozen deduplication")
            if row["thread_uid"] != manifest_row["thread_uid"]:
                raise ValueError("manifest thread_uid differs from the cleaning database")
            if row["review_cluster_uid"] != manifest_row["review_cluster_uid"]:
                raise ValueError("manifest review_cluster_uid differs from deduplication")

            quote_rows = connection.execute(
                """
                SELECT quote_index,
                       text_offset,
                       quote_source_discussion_id,
                       quote_source_post_id,
                       truncated,
                       altered
                FROM source_quotes
                WHERE source_discussion_id = ?
                  AND source_post_id = ?
                  AND parent_quote_index IS NULL
                  AND text_offset IS NOT NULL
                ORDER BY text_offset, quote_index
                """,
                (row["source_discussion_id"], row["target_source_post_id"]),
            ).fetchall()
            quote_texts = extract_top_level_quote_blocks(row["target_model_full"])
            if len(quote_rows) != len(quote_texts):
                raise ValueError(
                    "top-level quote metadata does not match reconstructed target text"
                )
            quote_blocks = []
            for quote_row, quote_text in zip(quote_rows, quote_texts, strict=True):
                quote_blocks.append(
                    {
                        "quote_index": int(quote_row["quote_index"]),
                        "text": quote_text,
                        "source_relation": source_relation(
                            discussion_id=int(row["source_discussion_id"]),
                            parent_post_id=int(row["parent_source_post_id"]),
                            quote_discussion_id=quote_row[
                                "quote_source_discussion_id"
                            ],
                            quote_post_id=quote_row["quote_source_post_id"],
                        ),
                        "truncated": nullable_bool(quote_row["truncated"]),
                        "altered": nullable_bool(quote_row["altered"]),
                    }
                )
            selected.append(
                {
                    "annotation_order": int(manifest_row["annotation_order"]),
                    "view": {
                        "schema_version": VIEW_SCHEMA_VERSION,
                        "protocol_id": LABEL_PROTOCOL_ID,
                        "dataset": {
                            "name": "IAC 2.0",
                            "subset": "4forums",
                            "cleaning_pipeline_id": "DATA-FCTX-CLEAN-V2",
                            "dedup_pipeline_id": "DATA-FCTX-DEDUP-V2",
                        },
                        "ids": {
                            "sample_uid": row["sample_uid"],
                            "thread_uid": row["thread_uid"],
                            "parent_uid": row["parent_post_uid"],
                            "target_uid": row["target_post_uid"],
                        },
                        "context": {
                            "discussion_title": row["title_model"],
                            "direct_parent_body": row["parent_model_body"],
                            "target_quotes": quote_blocks,
                        },
                        "target": {
                            "body": row["target_model_body"],
                            "full_with_quotes": row["target_model_full"],
                        },
                        "display_contract": {
                            "stage_a": "target.body",
                            "stage_b": "context+target",
                            "stage_a_locked_before_stage_b": True,
                            "future_replies_included": False,
                            "ancestor_chain_included": False,
                        },
                    },
                }
            )
        return selected
    finally:
        connection.close()


def write_private_view(path: Path, view: dict[str, object]) -> None:
    payload = json.dumps(view, indent=2, ensure_ascii=True) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, payload.encode("utf-8"))
    finally:
        os.close(descriptor)


def write_public_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def combined_view_hash(files: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.name.encode("ascii"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def nearest_rank(values: Sequence[int], fraction: float) -> int:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * fraction + 0.999999) - 1))
    return ordered[index]


def run(args: argparse.Namespace) -> dict[str, object]:
    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir.resolve()
    report_path = args.report.resolve()
    if output_dir.exists():
        raise FileExistsError(f"private views directory already exists: {output_dir}")
    if not is_gitignored(repo_root, output_dir):
        raise ValueError("private views directory is not gitignored")

    input_hashes = {
        "cleaning_database": sha256_file(args.cleaning_db),
        "dedup_database": sha256_file(args.dedup_db),
        "sampling_manifest": sha256_file(args.sampling_manifest),
        "sampling_report": sha256_file(args.sampling_report),
        "sampling_verification": sha256_file(args.sampling_verification),
        "label_protocol": sha256_file(args.label_protocol),
        "view_schema": sha256_file(args.view_schema),
    }
    expected_hashes = {
        "cleaning_database": EXPECTED_CLEANING_SHA256,
        "dedup_database": EXPECTED_DEDUP_SHA256,
        "label_protocol": EXPECTED_LABEL_PROTOCOL_SHA256,
        "view_schema": EXPECTED_VIEW_SCHEMA_SHA256,
    }
    mismatched = [
        name for name, expected in expected_hashes.items()
        if input_hashes[name] != expected
    ]
    if mismatched:
        raise ValueError(f"frozen input hash mismatch: {', '.join(mismatched)}")

    sampling_report = read_json(args.sampling_report)
    sampling_verification = read_json(args.sampling_verification)
    if sampling_report.get("status") != "passed":
        raise ValueError("sampling preflight has not passed")
    if sampling_verification.get("status") != "passed":
        raise ValueError("sampling independent verification has not passed")
    if sampling_verification.get("mismatch_count") != 0:
        raise ValueError("sampling verification contains mismatches")
    expected_manifest_hash = sampling_report["private_artifacts"][
        "sampling_manifest"
    ]["sha256"]
    if input_hashes["sampling_manifest"] != expected_manifest_hash:
        raise ValueError("sampling manifest hash differs from the verified preflight")
    if (
        sampling_verification["inputs"]["sampling_manifest_sha256"]
        != input_hashes["sampling_manifest"]
    ):
        raise ValueError("sampling manifest hash differs from independent verification")
    if (
        sampling_verification["inputs"]["preflight_report_sha256"]
        != input_hashes["sampling_report"]
    ):
        raise ValueError("sampling report hash differs from independent verification")

    manifest = read_jsonl(args.sampling_manifest)
    validate_manifest(manifest)
    selected = load_selected_rows(args.cleaning_db, args.dedup_db, manifest)
    for row in selected:
        validate_view_contract(row["view"])

    temporary_dir = output_dir.with_name(output_dir.name + ".tmp")
    if temporary_dir.exists():
        raise FileExistsError(f"temporary views directory already exists: {temporary_dir}")
    temporary_dir.mkdir(parents=True, mode=0o700)
    os.chmod(temporary_dir, 0o700)
    files: list[Path] = []
    try:
        for row in selected:
            path = temporary_dir / f"{row['annotation_order']:04d}.json"
            write_private_view(path, row["view"])
            files.append(path)
        os.replace(temporary_dir, output_dir)
    except Exception:
        shutil.rmtree(temporary_dir, ignore_errors=True)
        raise

    files = sorted(output_dir.glob("*.json"))
    quote_relations: Counter[str] = Counter()
    quote_counts: list[int] = []
    target_lengths: list[int] = []
    parent_lengths: list[int] = []
    samples_with_quotes = 0
    truncated_true = 0
    altered_true = 0
    for row in selected:
        view = row["view"]
        quotes = view["context"]["target_quotes"]
        quote_counts.append(len(quotes))
        samples_with_quotes += bool(quotes)
        target_lengths.append(len(view["target"]["body"]))
        parent_lengths.append(len(view["context"]["direct_parent_body"]))
        for quote in quotes:
            quote_relations[quote["source_relation"]] += 1
            truncated_true += quote["truncated"] is True
            altered_true += quote["altered"] is True

    report: dict[str, object] = {
        "schema_version": "1",
        "protocol_id": LABEL_PROTOCOL_ID,
        "sampling_protocol_id": SAMPLE_PROTOCOL_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed",
        "inputs": {
            "cleaning_database": {
                "filename": args.cleaning_db.name,
                "sha256": input_hashes["cleaning_database"],
            },
            "dedup_database": {
                "filename": args.dedup_db.name,
                "sha256": input_hashes["dedup_database"],
            },
            "sampling_manifest": {
                "filename": args.sampling_manifest.name,
                "sha256": input_hashes["sampling_manifest"],
                "rows": len(manifest),
            },
            "sampling_report": {
                "filename": args.sampling_report.name,
                "sha256": input_hashes["sampling_report"],
            },
            "sampling_verification": {
                "filename": args.sampling_verification.name,
                "sha256": input_hashes["sampling_verification"],
            },
            "label_protocol": {
                "filename": args.label_protocol.name,
                "sha256": input_hashes["label_protocol"],
            },
            "view_schema": {
                "filename": args.view_schema.name,
                "sha256": input_hashes["view_schema"],
            },
        },
        "implementation": {
            "script": Path(__file__).name,
            "script_sha256": sha256_file(Path(__file__)),
        },
        "aggregate": {
            "view_rows": len(files),
            "annotation_order_min": 1,
            "annotation_order_max": 120,
            "samples_with_target_quotes": samples_with_quotes,
            "target_quote_blocks": sum(quote_counts),
            "quote_source_relations": dict(sorted(quote_relations.items())),
            "truncated_quote_blocks": truncated_true,
            "altered_quote_blocks": altered_true,
            "target_body_chars_nearest_rank": {
                "p50": nearest_rank(target_lengths, 0.50),
                "p90": nearest_rank(target_lengths, 0.90),
                "p95": nearest_rank(target_lengths, 0.95),
            },
            "parent_body_chars_nearest_rank": {
                "p50": nearest_rank(parent_lengths, 0.50),
                "p90": nearest_rank(parent_lengths, 0.90),
                "p95": nearest_rank(parent_lengths, 0.95),
            },
        },
        "private_artifact": {
            "directory_name": output_dir.name,
            "files": len(files),
            "combined_sha256": combined_view_hash(files),
            "directory_mode": mode(output_dir),
            "all_file_modes_0600": all(mode(path) == "0o600" for path in files),
            "gitignored": is_gitignored(repo_root, output_dir),
        },
        "annotation_state": {
            "human_labels_created": False,
            "record_files_created": False,
            "blind_repeats_created": False,
        },
        "privacy": {
            "forum_text_emitted_in_public_report": False,
            "source_ids_emitted": False,
            "hmac_ids_emitted_in_public_report": False,
            "sampling_lanes_emitted_to_views": False,
            "weak_labels_emitted_to_views": False,
            "external_services_used": False,
        },
    }
    write_public_json(report_path, report)
    return report


def main() -> None:
    report = run(parse_args())
    print(
        json.dumps(
            {
                "status": report["status"],
                "view_rows": report["aggregate"]["view_rows"],
                "target_quote_blocks": report["aggregate"]["target_quote_blocks"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
