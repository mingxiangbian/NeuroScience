#!/usr/bin/env python3
"""Independently verify DATA-FCTX-CLEAN-V2 without emitting private text."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import re
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


PIPELINE_ID = "DATA-FCTX-CLEAN-V2"
REQUIRED_TABLES = {
    "metadata",
    "discussions",
    "source_posts",
    "source_quotes",
    "post_texts",
    "quote_texts",
    "cleaned_posts",
    "post_soft_flags",
    "quote_reconstruction_stats",
    "candidate_pairs",
    "candidate_hard_reasons",
    "candidate_soft_flags",
    "exact_duplicate_clusters",
}
FORBIDDEN_PUBLIC_KEYS = {
    "source_discussion_id",
    "source_post_id",
    "target_source_post_id",
    "parent_source_post_id",
    "thread_uid",
    "post_uid",
    "sample_uid",
    "raw_text",
    "raw_bytes",
    "model_full",
    "model_body",
    "dedup_body",
    "body_sha256",
    "pair_sha256",
    "title",
    "discussion_url",
    "author_id",
    "username",
}
ABSOLUTE_PATH_RE = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--id-key", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_uid(key: bytes, kind: str, *parts: int) -> str:
    payload = ":".join([kind, *(str(part) for part in parts)]).encode("ascii")
    digest = hmac.new(key, payload, hashlib.sha256).hexdigest()
    prefixes = {"thread": "thr", "post": "pst", "sample": "smp"}
    return f"{prefixes[kind]}_{digest}"


def nearest_rank_quantiles(values: Iterable[int]) -> dict[str, int | None]:
    ordered = sorted(values)
    if not ordered:
        return {key: None for key in ("min", "p25", "p50", "p75", "p95", "p99", "max")}

    def at(probability: float) -> int:
        index = max(0, math.ceil(probability * len(ordered)) - 1)
        return ordered[min(index, len(ordered) - 1)]

    return {
        "min": ordered[0],
        "p25": at(0.25),
        "p50": at(0.50),
        "p75": at(0.75),
        "p95": at(0.95),
        "p99": at(0.99),
        "max": ordered[-1],
    }


def count_map(connection: sqlite3.Connection, table: str, column: str) -> dict[str, int]:
    query = f"SELECT {column}, COUNT(*) FROM {table} GROUP BY {column} ORDER BY {column}"
    return {str(key): int(value) for key, value in connection.execute(query)}


def duplicate_summary_from_candidates(
    connection: sqlite3.Connection, column: str
) -> dict[str, int]:
    rows = list(
        connection.execute(
            f"""
            SELECT COUNT(*)
            FROM candidate_pairs
            WHERE eligible = 1 AND {column} IS NOT NULL
            GROUP BY {column}
            HAVING COUNT(*) > 1
            """
        )
    )
    sizes = [int(row[0]) for row in rows]
    return {
        "clusters_with_multiple_rows": len(sizes),
        "rows_in_duplicate_clusters": sum(sizes),
        "max_cluster_size": max(sizes, default=1),
    }


def public_payload_violations(payload: object, location: str = "root") -> list[str]:
    violations: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            child = f"{location}.{key}"
            if key in FORBIDDEN_PUBLIC_KEYS:
                violations.append(f"forbidden public key: {child}")
            violations.extend(public_payload_violations(value, child))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            violations.extend(public_payload_violations(value, f"{location}[{index}]"))
    elif isinstance(payload, str) and ABSOLUTE_PATH_RE.search(payload):
        violations.append(f"absolute path in public payload: {location}")
    return violations


def git_ignored(repo_root: Path, path: Path) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "check-ignore", "-q", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def uid_mismatch_counts(connection: sqlite3.Connection, key: bytes) -> dict[str, int]:
    counts = {"thread": 0, "post": 0, "sample": 0}
    for discussion_id, uid in connection.execute(
        "SELECT source_discussion_id, thread_uid FROM discussions"
    ):
        if uid != make_uid(key, "thread", discussion_id):
            counts["thread"] += 1
    for discussion_id, post_id, uid in connection.execute(
        "SELECT source_discussion_id, source_post_id, post_uid FROM source_posts"
    ):
        if uid != make_uid(key, "post", discussion_id, post_id):
            counts["post"] += 1
    for discussion_id, target_id, parent_id, uid in connection.execute(
        """
        SELECT source_discussion_id,
               target_source_post_id,
               parent_source_post_id,
               sample_uid
        FROM candidate_pairs
        """
    ):
        if uid != make_uid(key, "sample", discussion_id, target_id, parent_id):
            counts["sample"] += 1
    return counts


def verify(args: argparse.Namespace) -> dict[str, object]:
    required_paths = (
        args.source,
        args.db,
        args.id_key,
        args.script,
        args.protocol,
        args.report,
        args.manifest,
    )
    for path in required_paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    if args.output.exists() and not args.replace:
        raise FileExistsError(f"refusing to overwrite without --replace: {args.output}")

    report = json.loads(args.report.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    key = args.id_key.read_bytes()
    mismatches: list[str] = []
    checks: list[dict[str, object]] = []

    def check(name: str, condition: bool, detail: str) -> None:
        checks.append({"name": name, "status": "passed" if condition else "failed", "detail": detail})
        if not condition:
            mismatches.append(name)

    source_sha = sha256_file(args.source)
    db_sha = sha256_file(args.db)
    script_sha = sha256_file(args.script)
    protocol_sha = sha256_file(args.protocol)
    report_sha = sha256_file(args.report)

    check("source hash matches report", report["source_artifact"]["sha256"] == source_sha, "SHA-256")
    check("source hash matches manifest", manifest["source"]["sha256"] == source_sha, "SHA-256")
    check("database hash matches report", report["private_artifact"]["sha256"] == db_sha, "SHA-256")
    check("database hash matches manifest", manifest["private_artifact"]["sha256"] == db_sha, "SHA-256")
    check("script hash matches report", report["implementation"]["script_sha256"] == script_sha, "SHA-256")
    check("protocol hash matches report", report["implementation"]["protocol_sha256"] == protocol_sha, "SHA-256")
    check("report hash matches manifest", manifest["aggregate_report"]["sha256"] == report_sha, "SHA-256")
    check("ID key length", len(key) == 32, "exactly 32 bytes")
    check("ID key file mode", not (args.id_key.stat().st_mode & 0o077), "owner-only permissions")

    public_violations = public_payload_violations(report, "report")
    public_violations.extend(public_payload_violations(manifest, "manifest"))
    check("public payload privacy keys", not public_violations, f"violations={len(public_violations)}")

    if args.repo_root is not None:
        ignored = git_ignored(args.repo_root, args.db) and git_ignored(args.repo_root, args.id_key)
        check("private artifacts are gitignored", ignored, "database and HMAC key")

    connection = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        check("SQLite integrity", integrity == "ok", str(integrity))
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        check("required tables", REQUIRED_TABLES <= tables, f"present={len(tables)}")
        check("author table absent", "author" not in tables, "author table must not be retained")

        forbidden_columns: list[str] = []
        for table in tables:
            for row in connection.execute(f"PRAGMA table_info({table})"):
                column = str(row[1]).casefold()
                if "author" in column or column in {"url", "discussion_url"}:
                    forbidden_columns.append(f"{table}.{column}")
        check("author and URL columns absent", not forbidden_columns, f"violations={len(forbidden_columns)}")

        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        check("database pipeline ID", metadata.get("pipeline_id") == PIPELINE_ID, PIPELINE_ID)
        check("database source hash", metadata.get("source_sha256") == source_sha, "SHA-256")
        check("database script hash", metadata.get("script_sha256") == script_sha, "SHA-256")
        check("database protocol hash", metadata.get("protocol_sha256") == protocol_sha, "SHA-256")

        posts = connection.execute("SELECT COUNT(*) FROM source_posts").fetchone()[0]
        roots = connection.execute(
            "SELECT COUNT(*) FROM source_posts WHERE parent_post_id IS NULL"
        ).fetchone()[0]
        candidates = connection.execute("SELECT COUNT(*) FROM candidate_pairs").fetchone()[0]
        eligible = connection.execute(
            "SELECT COUNT(*) FROM candidate_pairs WHERE eligible = 1"
        ).fetchone()[0]
        cleaned = connection.execute("SELECT COUNT(*) FROM cleaned_posts").fetchone()[0]
        check("post accounting", posts == roots + candidates, "posts = roots + candidates")
        check("cleaned post coverage", cleaned == posts, "one cleaned row per post")
        check(
            "candidate report counts",
            report["counts"]["posts"] == posts
            and report["counts"]["root_posts_not_candidates"] == roots
            and report["counts"]["declared_parent_candidates"] == candidates
            and report["counts"]["eligible_candidates"] == eligible
            and report["counts"]["excluded_candidates"] == candidates - eligible,
            "aggregate equality",
        )

        eligibility_errors = connection.execute(
            """
            SELECT COUNT(*)
            FROM candidate_pairs AS c
            WHERE (c.eligible = 1 AND EXISTS (
                       SELECT 1 FROM candidate_hard_reasons AS h
                       WHERE h.sample_uid = c.sample_uid
                   ))
               OR (c.eligible = 0 AND NOT EXISTS (
                       SELECT 1 FROM candidate_hard_reasons AS h
                       WHERE h.sample_uid = c.sample_uid
                   ))
            """
        ).fetchone()[0]
        check("eligibility reason invariant", eligibility_errors == 0, f"mismatches={eligibility_errors}")
        json_reason_errors = connection.execute(
            """
            SELECT COUNT(*)
            FROM candidate_pairs AS c
            WHERE json_array_length(c.hard_reasons_json) != (
                SELECT COUNT(*) FROM candidate_hard_reasons AS h
                WHERE h.sample_uid = c.sample_uid
            )
            """
        ).fetchone()[0]
        json_flag_errors = connection.execute(
            """
            SELECT COUNT(*)
            FROM candidate_pairs AS c
            WHERE json_array_length(c.soft_flags_json) != (
                SELECT COUNT(*) FROM candidate_soft_flags AS f
                WHERE f.sample_uid = c.sample_uid
            )
            """
        ).fetchone()[0]
        check("candidate JSON reason counts", json_reason_errors == 0, f"mismatches={json_reason_errors}")
        check("candidate JSON flag counts", json_flag_errors == 0, f"mismatches={json_flag_errors}")

        hard_counts = count_map(connection, "candidate_hard_reasons", "reason")
        soft_counts = count_map(connection, "candidate_soft_flags", "flag")
        check(
            "hard reason report",
            report["counts"]["hard_reason_occurrences"] == hard_counts,
            f"categories={len(hard_counts)}",
        )
        check(
            "soft flag report",
            report["counts"]["soft_flag_occurrences"] == soft_counts,
            f"categories={len(soft_counts)}",
        )

        quote_offset_row = connection.execute(
            """
            SELECT COALESCE(SUM(valid_top_level_count), 0),
                   COALESCE(SUM(valid_nested_count), 0),
                   COALESCE(SUM(missing_offset_count), 0),
                   COALESCE(SUM(missing_parent_count), 0),
                   COALESCE(SUM(out_of_bounds_count), 0),
                   COALESCE(SUM(cycle_count), 0)
            FROM quote_reconstruction_stats
            """
        ).fetchone()
        quote_text_row = connection.execute(
            """
            SELECT COALESCE(SUM(quote_text_present_count), 0),
                   COALESCE(SUM(quote_text_empty_count), 0),
                   COALESCE(SUM(quote_text_missing_count), 0),
                   COALESCE(SUM(quote_decode_replacement_count), 0),
                   COALESCE(SUM(quote_text_char_count), 0),
                   COALESCE(SUM(inserted_top_level_count), 0),
                   COALESCE(SUM(inserted_nested_count), 0)
            FROM quote_reconstruction_stats
            """
        ).fetchone()
        quote_offset_counts = {
            "valid_top_level": int(quote_offset_row[0]),
            "valid_nested": int(quote_offset_row[1]),
            "missing_offset": int(quote_offset_row[2]),
            "missing_parent": int(quote_offset_row[3]),
            "out_of_bounds": int(quote_offset_row[4]),
            "cycle": int(quote_offset_row[5]),
        }
        quote_text_counts = {
            "present": int(quote_text_row[0]),
            "empty": int(quote_text_row[1]),
            "missing": int(quote_text_row[2]),
            "decode_replacement": int(quote_text_row[3]),
        }
        source_quote_count = connection.execute("SELECT COUNT(*) FROM source_quotes").fetchone()[0]
        check(
            "quote offset accounting",
            sum(quote_offset_counts.values()) == source_quote_count,
            "one offset status per quote row",
        )
        check(
            "quote text accounting",
            quote_text_counts["present"]
            + quote_text_counts["empty"]
            + quote_text_counts["missing"]
            == source_quote_count,
            "one text availability status per quote row",
        )
        check(
            "quote offset report",
            report["quote_reconstruction"]["offset_status_occurrences"]
            == quote_offset_counts,
            f"rows={source_quote_count}",
        )
        check(
            "quote text report",
            report["quote_reconstruction"]["text_status_occurrences"]
            == quote_text_counts,
            f"rows={source_quote_count}",
        )
        inserted = {
            "top_level": int(quote_text_row[5]),
            "nested": int(quote_text_row[6]),
            "quote_text_characters": int(quote_text_row[4]),
        }
        check(
            "quote insertion report",
            report["quote_reconstruction"]["inserted"] == inserted,
            "reconstructed marker and text counts",
        )
        posts_with_quotes = connection.execute(
            """
            SELECT COUNT(*) FROM quote_reconstruction_stats
            WHERE valid_top_level_count + valid_nested_count + missing_offset_count
                + missing_parent_count + out_of_bounds_count + cycle_count > 0
            """
        ).fetchone()[0]
        check(
            "posts with quote metadata",
            report["quote_reconstruction"]["posts_with_quote_metadata"]
            == posts_with_quotes,
            f"posts={posts_with_quotes}",
        )
        source_flags = connection.execute(
            """
            SELECT SUM(CASE WHEN truncated = 1 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN altered = 1 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN quote_source_discussion_id IS NULL
                              OR quote_source_post_id IS NULL THEN 1 ELSE 0 END)
            FROM source_quotes
            """
        ).fetchone()
        expected_source_flags = {
            "truncated": int(source_flags[0]),
            "altered": int(source_flags[1]),
            "source_unresolved": int(source_flags[2]),
        }
        check(
            "quote source attribute report",
            report["quote_reconstruction"]["source_attributes"]
            == expected_source_flags,
            "aggregate source alignment attributes",
        )

        target_lengths = nearest_rank_quantiles(
            row[0]
            for row in connection.execute(
                """
                SELECT c.word_count
                FROM candidate_pairs AS p
                JOIN cleaned_posts AS c
                  ON c.source_discussion_id = p.source_discussion_id
                 AND c.source_post_id = p.target_source_post_id
                WHERE p.eligible = 1
                """
            )
        )
        parent_lengths = nearest_rank_quantiles(
            row[0]
            for row in connection.execute(
                """
                SELECT c.word_count
                FROM candidate_pairs AS p
                JOIN cleaned_posts AS c
                  ON c.source_discussion_id = p.source_discussion_id
                 AND c.source_post_id = p.parent_source_post_id
                WHERE p.eligible = 1
                """
            )
        )
        check(
            "word-count quantiles",
            report["eligible_word_count_nearest_rank"]
            == {"target": target_lengths, "parent": parent_lengths},
            "nearest-rank recomputation",
        )

        target_duplicates = duplicate_summary_from_candidates(connection, "target_body_sha256")
        pair_duplicates = duplicate_summary_from_candidates(connection, "pair_sha256")
        check(
            "target duplicate report",
            report["exact_duplication"]["target"] == target_duplicates,
            f"clusters={target_duplicates['clusters_with_multiple_rows']}",
        )
        check(
            "pair duplicate report",
            report["exact_duplication"]["pair"] == pair_duplicates,
            f"clusters={pair_duplicates['clusters_with_multiple_rows']}",
        )
        context_rows = connection.execute(
            "SELECT COUNT(*) FROM candidate_pairs WHERE eligible = 1 AND context_variant = 1"
        ).fetchone()[0]
        context_targets = connection.execute(
            """
            SELECT COUNT(DISTINCT target_body_sha256)
            FROM candidate_pairs
            WHERE eligible = 1 AND context_variant = 1
            """
        ).fetchone()[0]
        check(
            "context variant report",
            report["exact_duplication"]["context_variant_rows"] == context_rows
            and report["exact_duplication"]["distinct_context_variant_targets"]
            == context_targets,
            "target text under multiple parent contexts",
        )

        eligible_hash_errors = connection.execute(
            """
            SELECT COUNT(*) FROM candidate_pairs
            WHERE eligible = 1
              AND (target_body_sha256 IS NULL OR parent_body_sha256 IS NULL OR pair_sha256 IS NULL)
            """
        ).fetchone()[0]
        check("eligible duplicate keys", eligible_hash_errors == 0, f"missing={eligible_hash_errors}")
        uid_errors = uid_mismatch_counts(connection, key)
        check("HMAC identifiers", not any(uid_errors.values()), f"mismatches={sum(uid_errors.values())}")
    finally:
        connection.close()

    status = "passed" if not mismatches else "failed"
    payload: dict[str, object] = {
        "schema_version": "2",
        "pipeline_id": PIPELINE_ID,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "inputs": {
            "source_filename": args.source.name,
            "source_sha256": source_sha,
            "database_filename": args.db.name,
            "database_sha256": db_sha,
            "aggregate_report_filename": args.report.name,
            "aggregate_report_sha256": report_sha,
            "verification_script_sha256": sha256_file(Path(__file__).resolve()),
        },
        "checks": checks,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "public_payload_violations": public_violations,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, args.output)
    print(json.dumps({"status": status, "checks": len(checks), "mismatches": len(mismatches)}))
    return payload


def main() -> None:
    payload = verify(parse_args())
    if payload["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
