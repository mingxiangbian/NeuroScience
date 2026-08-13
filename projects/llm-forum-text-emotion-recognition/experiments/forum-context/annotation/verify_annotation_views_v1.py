#!/usr/bin/env python3
"""Independently rebuild and verify the private V1 annotation views."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import stat
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


LABEL_PROTOCOL_ID = "DATA-FCTX-LABEL-V1"
SAMPLE_PROTOCOL_ID = "DATA-FCTX-SAMPLE-V1"
EXPECTED_HASHES = {
    "cleaning_database": "b1f3022320980c96c5353be16401764a78e0bc40ebb21d71399fe4efcb05fcc7",
    "dedup_database": "13a5266a12f9574f073c3c7ce72e785e7d019573961507e1b0631f0a50bd7d4f",
    "label_protocol": "0de4bf6243f223ea1a72b3fa48867b59abf6cd19ff95104ff53d00856b0d376a",
    "view_schema": "9441981a27f2869d877641809742134de32712392d535355e2b4425ef59e4202",
}
ID_PATTERNS: Mapping[str, re.Pattern[str]] = {
    "sample_uid": re.compile(r"^smp_[0-9a-f]{64}$"),
    "thread_uid": re.compile(r"^thr_[0-9a-f]{64}$"),
    "parent_uid": re.compile(r"^pst_[0-9a-f]{64}$"),
    "target_uid": re.compile(r"^pst_[0-9a-f]{64}$"),
}
HMAC_ID_RE = re.compile(r"\b(?:smp|thr|pst|rvc)_[0-9a-f]{64}\b")
FORBIDDEN_VIEW_KEYS = {
    "lane",
    "lane_position",
    "role",
    "selection_rank_sha256",
    "review_cluster_uid",
    "annotation_order",
    "source_discussion_id",
    "source_post_id",
    "target_source_post_id",
    "parent_source_post_id",
    "quote_source_discussion_id",
    "quote_source_post_id",
    "topic_linked",
    "qr_annotated",
    "diag_sarcasm",
    "diag_hostility_affect",
    "presented_quote",
    "presented_response",
    "author",
    "username",
}
FORBIDDEN_PUBLIC_KEYS = {
    "sample_uid",
    "thread_uid",
    "parent_uid",
    "target_uid",
    "review_cluster_uid",
    "source_discussion_id",
    "source_post_id",
    "ids",
    "context",
    "target",
    "discussion_title",
    "direct_parent_body",
    "full_with_quotes",
    "text",
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
    parser.add_argument("--views-dir", type=Path, required=True)
    parser.add_argument("--export-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
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


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {path.name}")
    return value


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            raise ValueError(f"blank JSONL row at {path.name}:{number}")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"non-object JSONL row at {path.name}:{number}")
        rows.append(value)
    return rows


def mode(path: Path) -> str:
    return oct(stat.S_IMODE(path.stat().st_mode))


def is_gitignored(repo_root: Path, path: Path) -> bool:
    return (
        subprocess.run(
            ["git", "check-ignore", "-q", str(path.resolve())],
            cwd=repo_root,
            check=False,
        ).returncode
        == 0
    )


def combined_hash(files: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.name.encode("ascii"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def extract_outer_quotes(value: str) -> list[str]:
    opening = "[[QUOTE]]"
    closing = "[[/QUOTE]]"
    cursor = 0
    stack: list[int] = []
    blocks: list[str] = []
    while cursor < len(value):
        next_open = value.find(opening, cursor)
        next_close = value.find(closing, cursor)
        positions = [position for position in (next_open, next_close) if position >= 0]
        if not positions:
            break
        position = min(positions)
        if position == next_open:
            stack.append(position + len(opening))
            cursor = position + len(opening)
            continue
        if not stack:
            raise ValueError("unmatched quote close marker")
        start = stack.pop()
        if not stack:
            text = value[start:position].strip()
            if not text:
                raise ValueError("empty top-level quote")
            blocks.append(text)
        cursor = position + len(closing)
    if stack:
        raise ValueError("unclosed quote marker")
    return blocks


def relation(
    discussion_id: int,
    parent_post_id: int,
    quote_discussion_id: int | None,
    quote_post_id: int | None,
) -> str:
    if quote_discussion_id == discussion_id and quote_post_id == parent_post_id:
        return "direct_parent"
    if quote_discussion_id == discussion_id and quote_post_id is not None:
        return "same_thread_other"
    return "external_or_unknown"


def nullable_boolean(value: object) -> bool | None:
    if value is None:
        return None
    if value == 0:
        return False
    if value == 1:
        return True
    raise ValueError("database boolean is not 0, 1 or NULL")


def collect_forbidden_keys(
    value: object, forbidden: set[str], path: str = "$"
) -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in forbidden:
                violations.append(child_path)
            violations.extend(collect_forbidden_keys(child, forbidden, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(
                collect_forbidden_keys(child, forbidden, f"{path}[{index}]")
            )
    return violations


def public_violations(value: object, path: str = "$") -> list[str]:
    violations = collect_forbidden_keys(value, FORBIDDEN_PUBLIC_KEYS, path)
    if isinstance(value, dict):
        for key, child in value.items():
            violations.extend(public_violations(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(public_violations(child, f"{path}[{index}]"))
    elif isinstance(value, str) and HMAC_ID_RE.search(value):
        violations.append(f"HMAC identifier at {path}")
    return sorted(set(violations))


def validate_schema_contract(view: dict[str, object]) -> list[str]:
    problems: list[str] = []
    expected_top = {
        "schema_version",
        "protocol_id",
        "dataset",
        "ids",
        "context",
        "target",
        "display_contract",
    }
    if set(view) != expected_top:
        problems.append("top-level keys")
    if view.get("schema_version") != "annotation-view-v1":
        problems.append("schema version")
    if view.get("protocol_id") != LABEL_PROTOCOL_ID:
        problems.append("protocol id")
    if view.get("dataset") != {
        "name": "IAC 2.0",
        "subset": "4forums",
        "cleaning_pipeline_id": "DATA-FCTX-CLEAN-V2",
        "dedup_pipeline_id": "DATA-FCTX-DEDUP-V2",
    }:
        problems.append("dataset contract")
    ids = view.get("ids")
    if not isinstance(ids, dict) or set(ids) != set(ID_PATTERNS):
        problems.append("id keys")
    else:
        for key, pattern in ID_PATTERNS.items():
            if not isinstance(ids[key], str) or not pattern.fullmatch(ids[key]):
                problems.append(f"id format {key}")
    context = view.get("context")
    if not isinstance(context, dict) or set(context) != {
        "discussion_title",
        "direct_parent_body",
        "target_quotes",
    }:
        problems.append("context keys")
    else:
        for key in ("discussion_title", "direct_parent_body"):
            if not isinstance(context[key], str) or not context[key]:
                problems.append(f"context text {key}")
        quotes = context["target_quotes"]
        if not isinstance(quotes, list):
            problems.append("target_quotes type")
        else:
            expected_quote_keys = {
                "quote_index",
                "text",
                "source_relation",
                "truncated",
                "altered",
            }
            for index, quote in enumerate(quotes):
                if not isinstance(quote, dict) or set(quote) != expected_quote_keys:
                    problems.append(f"quote keys {index}")
                    continue
                if not isinstance(quote["quote_index"], int) or quote["quote_index"] < 0:
                    problems.append(f"quote index {index}")
                if not isinstance(quote["text"], str) or not quote["text"]:
                    problems.append(f"quote text {index}")
                if quote["source_relation"] not in {
                    "direct_parent",
                    "same_thread_other",
                    "external_or_unknown",
                }:
                    problems.append(f"quote relation {index}")
                if quote["truncated"] not in (True, False, None):
                    problems.append(f"quote truncated {index}")
                if quote["altered"] not in (True, False, None):
                    problems.append(f"quote altered {index}")
    target = view.get("target")
    if not isinstance(target, dict) or set(target) != {"body", "full_with_quotes"}:
        problems.append("target keys")
    else:
        for key in ("body", "full_with_quotes"):
            if not isinstance(target[key], str) or not target[key]:
                problems.append(f"target text {key}")
    if view.get("display_contract") != {
        "stage_a": "target.body",
        "stage_b": "context+target",
        "stage_a_locked_before_stage_b": True,
        "future_replies_included": False,
        "ancestor_chain_included": False,
    }:
        problems.append("display contract")
    return problems


def expected_views(
    cleaning_db: Path,
    dedup_db: Path,
    manifest: Sequence[dict[str, object]],
) -> list[dict[str, object]]:
    connection = sqlite3.connect(f"file:{cleaning_db.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("ATTACH DATABASE ? AS dedup", (str(dedup_db.resolve()),))
    try:
        expected: list[dict[str, object]] = []
        for manifest_row in manifest:
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
                       parent.model_body AS parent_body,
                       target.model_body AS target_body,
                       target.model_full AS target_full,
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
                (manifest_row["sample_uid"],),
            ).fetchone()
            if row is None:
                raise ValueError("manifest sample missing from cleaning database")
            if not row["eligible"] or not row["eligible_after_auto_dedup"]:
                raise ValueError("manifest sample is not active")
            if row["thread_uid"] != manifest_row["thread_uid"]:
                raise ValueError("manifest thread mismatch")
            if row["review_cluster_uid"] != manifest_row["review_cluster_uid"]:
                raise ValueError("manifest review cluster mismatch")
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
            quote_texts = extract_outer_quotes(row["target_full"])
            if len(quote_rows) != len(quote_texts):
                raise ValueError("quote metadata and text count differ")
            quotes = []
            for quote_row, quote_text in zip(quote_rows, quote_texts, strict=True):
                quotes.append(
                    {
                        "quote_index": int(quote_row["quote_index"]),
                        "text": quote_text,
                        "source_relation": relation(
                            int(row["source_discussion_id"]),
                            int(row["parent_source_post_id"]),
                            quote_row["quote_source_discussion_id"],
                            quote_row["quote_source_post_id"],
                        ),
                        "truncated": nullable_boolean(quote_row["truncated"]),
                        "altered": nullable_boolean(quote_row["altered"]),
                    }
                )
            expected.append(
                {
                    "schema_version": "annotation-view-v1",
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
                        "direct_parent_body": row["parent_body"],
                        "target_quotes": quotes,
                    },
                    "target": {
                        "body": row["target_body"],
                        "full_with_quotes": row["target_full"],
                    },
                    "display_contract": {
                        "stage_a": "target.body",
                        "stage_b": "context+target",
                        "stage_a_locked_before_stage_b": True,
                        "future_replies_included": False,
                        "ancestor_chain_included": False,
                    },
                }
            )
        return expected
    finally:
        connection.close()


def write_public_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def verify(args: argparse.Namespace) -> dict[str, object]:
    repo_root = args.repo_root.resolve()
    views_dir = args.views_dir.resolve()
    manifest = read_jsonl(args.sampling_manifest)
    sampling_report = read_object(args.sampling_report)
    sampling_verification = read_object(args.sampling_verification)
    export_report = read_object(args.export_report)
    files = sorted(views_dir.glob("*.json"))
    actual_views = [read_object(path) for path in files]

    checks: list[dict[str, str]] = []
    mismatches: list[str] = []

    def check(name: str, condition: bool, detail: str) -> None:
        checks.append(
            {"name": name, "status": "passed" if condition else "failed", "detail": detail}
        )
        if not condition:
            mismatches.append(name)

    input_hashes = {
        "cleaning_database": sha256_file(args.cleaning_db),
        "dedup_database": sha256_file(args.dedup_db),
        "sampling_manifest": sha256_file(args.sampling_manifest),
        "sampling_report": sha256_file(args.sampling_report),
        "sampling_verification": sha256_file(args.sampling_verification),
        "label_protocol": sha256_file(args.label_protocol),
        "view_schema": sha256_file(args.view_schema),
        "export_report": sha256_file(args.export_report),
    }
    for name, expected in EXPECTED_HASHES.items():
        check(f"frozen hash {name}", input_hashes[name] == expected, "SHA-256")
    check("sampling report status", sampling_report.get("status") == "passed", "passed")
    check(
        "sampling verification status",
        sampling_verification.get("status") == "passed"
        and sampling_verification.get("mismatch_count") == 0,
        "passed with zero mismatches",
    )
    check("export report status", export_report.get("status") == "passed", "passed")
    check(
        "manifest hash against sampling report",
        input_hashes["sampling_manifest"]
        == sampling_report["private_artifacts"]["sampling_manifest"]["sha256"],
        "SHA-256",
    )
    check(
        "manifest hash against sampling verification",
        input_hashes["sampling_manifest"]
        == sampling_verification["inputs"]["sampling_manifest_sha256"],
        "SHA-256",
    )
    check(
        "export report input hashes",
        all(
            export_report["inputs"][name]["sha256"] == input_hashes[name]
            for name in (
                "cleaning_database",
                "dedup_database",
                "sampling_manifest",
                "sampling_report",
                "sampling_verification",
                "label_protocol",
                "view_schema",
            )
        ),
        "all input hashes",
    )
    check("manifest rows", len(manifest) == 120, f"rows={len(manifest)}")
    orders = [row.get("annotation_order") for row in manifest]
    check("manifest annotation order", orders == list(range(1, 121)), "1..120")
    check(
        "manifest unique samples",
        len({row.get("sample_uid") for row in manifest}) == 120,
        "unique=120",
    )
    check(
        "manifest unique threads",
        len({row.get("thread_uid") for row in manifest}) == 120,
        "unique=120",
    )
    check(
        "view filenames",
        [path.name for path in files] == [f"{index:04d}.json" for index in range(1, 121)],
        f"files={len(files)}",
    )

    expected = expected_views(args.cleaning_db, args.dedup_db, manifest)
    check("expected view rows", len(expected) == 120, f"rows={len(expected)}")
    check(
        "exact database reconstruction",
        actual_views == expected,
        "ordered view objects",
    )
    schema_problems = [
        f"{index:04d}:{problem}"
        for index, view in enumerate(actual_views, 1)
        for problem in validate_schema_contract(view)
    ]
    check(
        "view schema contract",
        not schema_problems,
        f"problems={len(schema_problems)}",
    )
    forbidden_view = [
        f"{index:04d}:{path}"
        for index, view in enumerate(actual_views, 1)
        for path in collect_forbidden_keys(view, FORBIDDEN_VIEW_KEYS)
    ]
    check(
        "hidden sampling and source metadata",
        not forbidden_view,
        f"violations={len(forbidden_view)}",
    )
    check(
        "view sample order",
        [view["ids"]["sample_uid"] for view in actual_views]
        == [row["sample_uid"] for row in manifest],
        "manifest order",
    )
    check(
        "view thread order",
        [view["ids"]["thread_uid"] for view in actual_views]
        == [row["thread_uid"] for row in manifest],
        "manifest order",
    )
    check("views directory mode", mode(views_dir) == "0o700", mode(views_dir))
    check(
        "view file modes",
        len(files) == 120 and all(mode(path) == "0o600" for path in files),
        "all 0600",
    )
    check("views gitignored", is_gitignored(repo_root, views_dir), "git check-ignore")
    check(
        "all view files gitignored",
        len(files) == 120 and all(is_gitignored(repo_root, path) for path in files),
        "120 files",
    )
    view_hash = combined_hash(files)
    check(
        "combined private view hash",
        export_report["private_artifact"]["combined_sha256"] == view_hash,
        "SHA-256",
    )
    check(
        "export aggregate row count",
        export_report["aggregate"]["view_rows"] == len(actual_views) == 120,
        "rows=120",
    )
    quote_relation_counts: Counter[str] = Counter(
        quote["source_relation"]
        for view in actual_views
        for quote in view["context"]["target_quotes"]
    )
    quote_count = sum(quote_relation_counts.values())
    check(
        "export aggregate quote count",
        export_report["aggregate"]["target_quote_blocks"] == quote_count,
        f"blocks={quote_count}",
    )
    check(
        "export aggregate quote relations",
        export_report["aggregate"]["quote_source_relations"]
        == dict(sorted(quote_relation_counts.items())),
        "relation counts",
    )
    report_privacy = public_violations(export_report)
    check(
        "export public report privacy",
        not report_privacy,
        f"violations={len(report_privacy)}",
    )
    check(
        "export privacy claims",
        all(value is False for value in export_report["privacy"].values()),
        "all false",
    )
    check(
        "no human records",
        not (views_dir.parent / "records").exists(),
        "records directory absent",
    )
    check(
        "no blind repeats",
        not (views_dir.parent / "repeat-manifest.jsonl").exists(),
        "repeat manifest absent",
    )
    check(
        "annotation state remains empty",
        export_report.get("annotation_state")
        == {
            "human_labels_created": False,
            "record_files_created": False,
            "blind_repeats_created": False,
        },
        "all false",
    )

    result: dict[str, object] = {
        "schema_version": "1",
        "protocol_id": LABEL_PROTOCOL_ID,
        "sampling_protocol_id": SAMPLE_PROTOCOL_ID,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if not mismatches else "failed",
        "inputs": {
            "cleaning_database_filename": args.cleaning_db.name,
            "cleaning_database_sha256": input_hashes["cleaning_database"],
            "dedup_database_filename": args.dedup_db.name,
            "dedup_database_sha256": input_hashes["dedup_database"],
            "sampling_manifest_filename": args.sampling_manifest.name,
            "sampling_manifest_sha256": input_hashes["sampling_manifest"],
            "sampling_report_filename": args.sampling_report.name,
            "sampling_report_sha256": input_hashes["sampling_report"],
            "sampling_verification_filename": args.sampling_verification.name,
            "sampling_verification_sha256": input_hashes["sampling_verification"],
            "label_protocol_filename": args.label_protocol.name,
            "label_protocol_sha256": input_hashes["label_protocol"],
            "view_schema_filename": args.view_schema.name,
            "view_schema_sha256": input_hashes["view_schema"],
            "export_report_filename": args.export_report.name,
            "export_report_sha256": input_hashes["export_report"],
            "verification_script_sha256": sha256_file(Path(__file__)),
        },
        "aggregate": {
            "view_rows": len(actual_views),
            "target_quote_blocks": quote_count,
            "quote_source_relations": dict(sorted(quote_relation_counts.items())),
        },
        "checks": checks,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "schema_problem_count": len(schema_problems),
        "forbidden_view_key_count": len(forbidden_view),
        "public_payload_violations": report_privacy,
        "annotation_state": {
            "human_labels_created": False,
            "record_files_created": False,
            "blind_repeats_created": False,
        },
        "privacy": {
            "forum_text_emitted": False,
            "source_or_hmac_ids_emitted": False,
            "per_sample_records_emitted": False,
            "external_services_used": False,
        },
    }
    write_public_json(args.output, result)
    return result


def main() -> None:
    result = verify(parse_args())
    print(
        json.dumps(
            {
                "status": result["status"],
                "checks": len(result["checks"]),
                "mismatch_count": result["mismatch_count"],
            },
            sort_keys=True,
        )
    )
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
