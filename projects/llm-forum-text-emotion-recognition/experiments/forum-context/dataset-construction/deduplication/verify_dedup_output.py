#!/usr/bin/env python3
"""Independently verify DATA-FCTX-DEDUP-V1 without emitting private text."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence

import numpy as np


PIPELINE_ID = "DATA-FCTX-DEDUP-V1"
MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
MODEL_FILES = (
    "model.safetensors",
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "1_Pooling/config.json",
)
EMBEDDING_DIM = 384
PAIR_DIM = 768
MAX_TOKENS = 256
INITIAL_K = 64
MAX_K = 512
RETRIEVAL_FLOOR = 0.88
LEXICAL_JACCARD = 0.85
LEXICAL_LENGTH_RATIO = 0.85
SEMANTIC_PAIR = 0.92
SEMANTIC_COMPONENT = 0.85
SEMANTIC_STRONG_PAIR = 0.96
SEMANTIC_STRONG_COMPONENT = 0.94
RECALL_AUDIT_SIZE = 128
RECALL_REQUIRED = 0.98
TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*")
ABSOLUTE_PATH_RE = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\)")
NEGATION_CANONICAL = {
    "no": "no",
    "not": "not",
    "never": "never",
    "neither": "neither",
    "nor": "nor",
    "nobody": "nobody",
    "nothing": "nothing",
    "nowhere": "nowhere",
    "cannot": "not",
    "can't": "not",
    "cant": "not",
    "won't": "not",
    "wont": "not",
    "don't": "not",
    "dont": "not",
    "isn't": "not",
    "isnt": "not",
    "aren't": "not",
    "arent": "not",
    "wasn't": "not",
    "wasnt": "not",
    "weren't": "not",
    "werent": "not",
    "didn't": "not",
    "didnt": "not",
    "doesn't": "not",
    "doesnt": "not",
    "haven't": "not",
    "havent": "not",
    "hasn't": "not",
    "hasnt": "not",
    "hadn't": "not",
    "hadnt": "not",
    "wouldn't": "not",
    "wouldnt": "not",
    "shouldn't": "not",
    "shouldnt": "not",
    "couldn't": "not",
    "couldnt": "not",
}
FORBIDDEN_PUBLIC_KEYS = {
    "sample_uid",
    "post_uid",
    "thread_uid",
    "source_post_id",
    "source_discussion_id",
    "model_body",
    "dedup_body",
    "pair_sha256",
    "body_sha256",
}
REQUIRED_TABLES = {
    "metadata",
    "post_embedding_rows",
    "candidate_decisions",
    "duplicate_edges",
    "retrieval_audit",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-db", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_faiss():
    """Delay FAISS/OpenMP loading until PyTorch replay has finished."""
    import faiss

    return faiss


def sha256_model(model_dir: Path) -> str:
    digest = hashlib.sha256()
    for relative in MODEL_FILES:
        path = model_dir / relative
        file_hash = sha256_file(path)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def public_payload_violations(payload: object, location: str = "root") -> list[str]:
    violations: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            child = f"{location}.{key}"
            if key in FORBIDDEN_PUBLIC_KEYS:
                violations.append(child)
            violations.extend(public_payload_violations(value, child))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            violations.extend(public_payload_violations(value, f"{location}[{index}]"))
    elif isinstance(payload, str) and ABSOLUTE_PATH_RE.search(payload):
        violations.append(location)
    return violations


def git_ignored(repo_root: Path, path: Path) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "check-ignore", "-q", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def open_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def tokens(value: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in TOKEN_RE.findall(value))


def negation_signature(token_values: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        NEGATION_CANONICAL[token]
        for token in token_values
        if token in NEGATION_CANONICAL
    )


def numeric_signature(token_values: Sequence[str]) -> tuple[str, ...]:
    return tuple(token for token in token_values if any(char.isdigit() for char in token))


def char_ngrams(value: str, size: int = 5) -> set[str]:
    if not value:
        return set()
    if len(value) < size:
        return {value}
    return {value[index : index + size] for index in range(len(value) - size + 1)}


def set_jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def compare_text(left: str, right: str) -> dict[str, object]:
    left_tokens = tokens(left)
    right_tokens = tokens(right)
    longest = max(len(left), len(right))
    return {
        "char_jaccard": set_jaccard(char_ngrams(left), char_ngrams(right)),
        "length_ratio": min(len(left), len(right)) / longest if longest else 1.0,
        "token_equal": left_tokens == right_tokens,
        "negation_equal": negation_signature(left_tokens) == negation_signature(right_tokens),
        "numeric_equal": numeric_signature(left_tokens) == numeric_signature(right_tokens),
    }


def pair_vectors(
    parent_rows: np.ndarray,
    target_rows: np.ndarray,
    embeddings: np.ndarray,
    indices: Sequence[int] | np.ndarray,
) -> np.ndarray:
    selected = np.asarray(indices, dtype=np.int64)
    parent = np.asarray(embeddings[parent_rows[selected]], dtype=np.float32)
    target = np.asarray(embeddings[target_rows[selected]], dtype=np.float32)
    return np.concatenate((parent, target), axis=1) / math.sqrt(2.0)


def chunks(values: Sequence[int], size: int) -> Iterator[Sequence[int]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def fetch_post_text(
    connection: sqlite3.Connection,
    post_uid: str,
    column: str,
    cache: dict[str, str],
) -> str:
    key = f"{column}:{post_uid}"
    if key not in cache:
        row = connection.execute(
            f"SELECT {column} FROM cleaned_posts WHERE post_uid = ?",
            (post_uid,),
        ).fetchone()
        if row is None:
            raise KeyError("candidate post is absent from cleaned_posts")
        cache[key] = row[0] or ""
    return cache[key]


def run_embedding_replay_worker(
    worker: Path,
    input_db: Path,
    dedup_db: Path,
    embeddings: Path,
    model_dir: Path,
    threads: int,
    batch_size: int,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as temporary_directory:
        output = Path(temporary_directory) / "embedding-replay.json"
        subprocess.run(
            [
                sys.executable,
                str(worker),
                "--input-db",
                str(input_db),
                "--dedup-db",
                str(dedup_db),
                "--embeddings",
                str(embeddings),
                "--model-dir",
                str(model_dir),
                "--output",
                str(output),
                "--threads",
                str(threads),
                "--batch-size",
                str(batch_size),
            ],
            check=True,
        )
        return json.loads(output.read_text(encoding="utf-8"))


def verify(args: argparse.Namespace) -> dict[str, object]:
    embedding_worker = Path(args.script).with_name("embed_iac2_posts.py")
    replay_worker = Path(__file__).with_name("replay_iac2_embeddings.py")
    required = (
        args.input_db,
        args.db,
        args.embeddings,
        args.index,
        args.model_dir,
        args.script,
        args.protocol,
        args.report,
        args.manifest,
        embedding_worker,
        replay_worker,
    )
    for path in required:
        if not path.exists():
            raise FileNotFoundError(path)
    if args.output.exists() and not args.replace:
        raise FileExistsError(f"refusing to overwrite without --replace: {args.output}")
    if args.model_dir.name != MODEL_REVISION:
        raise ValueError("model directory is not the frozen revision")

    report = json.loads(args.report.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    checks: list[dict[str, object]] = []
    mismatches: list[str] = []

    def check(name: str, condition: bool, detail: str) -> None:
        checks.append(
            {"name": name, "status": "passed" if condition else "failed", "detail": detail}
        )
        if not condition:
            mismatches.append(name)

    input_sha = sha256_file(args.input_db)
    db_sha = sha256_file(args.db)
    embeddings_sha = sha256_file(args.embeddings)
    index_sha = sha256_file(args.index)
    script_sha = sha256_file(args.script)
    protocol_sha = sha256_file(args.protocol)
    report_sha = sha256_file(args.report)
    model_sha = sha256_model(args.model_dir)
    embedding_worker_sha = sha256_file(embedding_worker)
    replay_worker_sha = sha256_file(replay_worker)

    check("pipeline status", report.get("status") == "completed_pending_independent_verification", "pre-verification run completed")
    check("input hash in report", report["input"]["database_sha256"] == input_sha, "SHA-256")
    check("input hash in manifest", manifest["input"]["database_sha256"] == input_sha, "SHA-256")
    check("database hash in report", report["private_artifacts"]["database"]["sha256"] == db_sha, "SHA-256")
    check("database hash in manifest", manifest["private_artifacts"]["database"]["sha256"] == db_sha, "SHA-256")
    check("embedding hash in report", report["private_artifacts"]["embeddings"]["sha256"] == embeddings_sha, "SHA-256")
    check("embedding hash in manifest", manifest["private_artifacts"]["embeddings"]["sha256"] == embeddings_sha, "SHA-256")
    check("index hash in report", report["private_artifacts"]["index"]["sha256"] == index_sha, "SHA-256")
    check("index hash in manifest", manifest["private_artifacts"]["index"]["sha256"] == index_sha, "SHA-256")
    check("script hash", report["implementation"]["script_sha256"] == script_sha, "SHA-256")
    check("embedding worker hash", report["implementation"]["embedding_worker_sha256"] == embedding_worker_sha, "SHA-256")
    check("protocol hash", report["implementation"]["protocol_sha256"] == protocol_sha, "SHA-256")
    check("protocol hash in manifest", manifest["protocol"]["sha256"] == protocol_sha, "SHA-256")
    check("report hash in manifest", manifest["aggregate_report"]["sha256"] == report_sha, "SHA-256")
    check("model identity", report["model"]["model_id"] == MODEL_ID and report["model"]["revision"] == MODEL_REVISION, "frozen model and revision")
    check("model file hash", report["model"]["selected_files_sha256"] == model_sha, "selected model files")

    public_violations = public_payload_violations(report, "report")
    public_violations.extend(public_payload_violations(manifest, "manifest"))
    check("public payload privacy", not public_violations, f"violations={len(public_violations)}")
    owner_only = all(not (path.stat().st_mode & 0o077) for path in (args.db, args.embeddings, args.index))
    check("private artifact modes", owner_only, "owner-only permissions")
    if args.repo_root is not None:
        ignored = all(
            git_ignored(args.repo_root, path)
            for path in (args.db, args.embeddings, args.index)
        )
        check("private artifacts are gitignored", ignored, "database, embeddings and index")

    input_connection = open_readonly(args.input_db)
    output_connection = open_readonly(args.db)
    try:
        integrity = output_connection.execute("PRAGMA integrity_check").fetchone()[0]
        check("SQLite integrity", integrity == "ok", str(integrity))
        tables = {
            row[0]
            for row in output_connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        check("required tables", REQUIRED_TABLES <= tables, f"present={len(tables)}")
        metadata = dict(output_connection.execute("SELECT key, value FROM metadata"))
        check("database pipeline ID", metadata.get("pipeline_id") == PIPELINE_ID, PIPELINE_ID)
        check("database input hash", metadata.get("input_db_sha256") == input_sha, "SHA-256")
        check("database script hash", metadata.get("script_sha256") == script_sha, "SHA-256")
        check("database protocol hash", metadata.get("protocol_sha256") == protocol_sha, "SHA-256")
        check("database model hash", metadata.get("model_sha256") == model_sha, "SHA-256")

        post_rows = list(
            output_connection.execute(
                "SELECT post_uid, embedding_row, token_count_capped, possible_truncation FROM post_embedding_rows ORDER BY embedding_row"
            )
        )
        post_count = len(post_rows)
        embedding_row_by_uid = {str(row[0]): int(row[1]) for row in post_rows}
        token_counts = np.fromiter((int(row[2]) for row in post_rows), dtype=np.uint16, count=post_count)
        check("embedding row continuity", all(int(row[1]) == index for index, row in enumerate(post_rows)), "zero-based contiguous rows")
        check("truncation flags", all(int(row[3]) == int(int(row[2]) >= MAX_TOKENS) for row in post_rows), "token-count gate")
        expected_embedding_size = post_count * EMBEDDING_DIM * np.dtype(np.float32).itemsize
        check("embedding file size", args.embeddings.stat().st_size == expected_embedding_size, f"rows={post_count}, dimension={EMBEDDING_DIM}")
        check("embedding report shape", report["private_artifacts"]["embeddings"]["shape"] == [post_count, EMBEDDING_DIM], "aggregate shape")
        embeddings = np.memmap(args.embeddings, dtype=np.float32, mode="r", shape=(post_count, EMBEDDING_DIM))
        norm_min = float("inf")
        norm_max = 0.0
        finite = True
        for start in range(0, post_count, 25000):
            block = np.asarray(embeddings[start : start + 25000], dtype=np.float32)
            finite = finite and bool(np.isfinite(block).all())
            norms = np.linalg.norm(block, axis=1)
            norm_min = min(norm_min, float(norms.min()))
            norm_max = max(norm_max, float(norms.max()))
        check("embedding values finite", finite, "all rows")
        check("embedding L2 normalization", abs(norm_min - 1.0) <= 2e-5 and abs(norm_max - 1.0) <= 2e-5, "unit norm")

        input_rows = list(
            input_connection.execute(
                """
                SELECT sample_uid, parent_post_uid, target_post_uid, pair_sha256
                FROM candidate_pairs
                WHERE eligible = 1
                ORDER BY sample_uid
                """
            )
        )
        decisions = list(
            output_connection.execute(
                """
                SELECT candidate_index, sample_uid, canonical_sample_uid,
                       auto_decision, eligible_after_auto_dedup,
                       severe_flag_count, total_flag_count,
                       combined_word_count_capped, review_status,
                       review_cluster_uid
                FROM candidate_decisions
                ORDER BY candidate_index
                """
            )
        )
        candidate_count = len(input_rows)
        check("candidate count", len(decisions) == candidate_count == report["input"]["eligible_candidates"], f"rows={candidate_count}")
        sample_uids = [str(row[0]) for row in input_rows]
        sample_to_index = {sample_uid: index for index, sample_uid in enumerate(sample_uids)}
        parent_uids = [str(row[1]) for row in input_rows]
        target_uids = [str(row[2]) for row in input_rows]
        pair_hashes = [str(row[3]) for row in input_rows]
        parent_rows = np.fromiter((embedding_row_by_uid[value] for value in parent_uids), dtype=np.int32, count=candidate_count)
        target_rows = np.fromiter((embedding_row_by_uid[value] for value in target_uids), dtype=np.int32, count=candidate_count)
        ordered = all(int(row[0]) == index and str(row[1]) == sample_uids[index] for index, row in enumerate(decisions))
        check("candidate index alignment", ordered, "input and output stable order")

        decision_counts: Counter[str] = Counter()
        canonical_indices = np.empty(candidate_count, dtype=np.int32)
        decision_invariant_errors = 0
        for index, row in enumerate(decisions):
            canonical_uid = str(row[2])
            decision = str(row[3])
            eligible = int(row[4])
            canonical_index = sample_to_index.get(canonical_uid, -1)
            canonical_indices[index] = canonical_index
            decision_counts[decision] += 1
            if canonical_index < 0 or decision not in {"keep", "drop_exact", "drop_format_only"}:
                decision_invariant_errors += 1
                continue
            canonical_decision = str(decisions[canonical_index][3])
            if canonical_decision != "keep" or int(eligible) != int(decision == "keep"):
                decision_invariant_errors += 1
            if decision == "keep" and canonical_index != index:
                decision_invariant_errors += 1
            if decision == "drop_exact" and pair_hashes[index] != pair_hashes[canonical_index]:
                decision_invariant_errors += 1
            if decision == "drop_format_only" and pair_hashes[index] == pair_hashes[canonical_index]:
                decision_invariant_errors += 1
            if decision != "keep" and (str(row[8]) != "none" or row[9] is not None):
                decision_invariant_errors += 1
        check("decision invariants", decision_invariant_errors == 0, f"mismatches={decision_invariant_errors}")
        check("decision report counts", all(report["decisions"].get(key, 0) == value for key, value in decision_counts.items()), f"categories={len(decision_counts)}")
        check("eligible-after-dedup accounting", report["decisions"]["eligible_after_auto_dedup"] == decision_counts["keep"], "kept rows")

        duplicate_sizes = [
            int(row[0])
            for row in input_connection.execute(
                """
                SELECT COUNT(*) FROM candidate_pairs
                WHERE eligible = 1
                GROUP BY pair_sha256
                HAVING COUNT(*) > 1
                """
            )
        ]
        exact_report = report["exact_duplicates"]
        check("exact duplicate accounting", exact_report == {"clusters": len(duplicate_sizes), "members": sum(duplicate_sizes), "max_cluster_size": max(duplicate_sizes, default=1)}, f"clusters={len(duplicate_sizes)}")
        check("exact drop accounting", decision_counts["drop_exact"] == sum(size - 1 for size in duplicate_sizes), "one representative per exact cluster")

        direct_edges = {
            (int(left), int(right), str(edge_type))
            for left, right, edge_type in output_connection.execute(
                "SELECT sample_index_a, sample_index_b, edge_type FROM duplicate_edges WHERE edge_type IN ('exact', 'format_only')"
            )
        }
        missing_direct_edges = 0
        format_rule_errors = 0
        text_cache: dict[str, str] = {}
        for index, row in enumerate(decisions):
            decision = str(row[3])
            if decision == "keep":
                continue
            canonical = int(canonical_indices[index])
            edge_type = "exact" if decision == "drop_exact" else "format_only"
            if (min(index, canonical), max(index, canonical), edge_type) not in direct_edges:
                missing_direct_edges += 1
            if decision == "drop_format_only":
                parent = compare_text(
                    fetch_post_text(input_connection, parent_uids[index], "dedup_body", text_cache),
                    fetch_post_text(input_connection, parent_uids[canonical], "dedup_body", text_cache),
                )
                target = compare_text(
                    fetch_post_text(input_connection, target_uids[index], "dedup_body", text_cache),
                    fetch_post_text(input_connection, target_uids[canonical], "dedup_body", text_cache),
                )
                valid = all(
                    (
                        parent["char_jaccard"] >= LEXICAL_JACCARD,
                        target["char_jaccard"] >= LEXICAL_JACCARD,
                        parent["length_ratio"] >= LEXICAL_LENGTH_RATIO,
                        target["length_ratio"] >= LEXICAL_LENGTH_RATIO,
                        parent["token_equal"],
                        target["token_equal"],
                        parent["negation_equal"],
                        target["negation_equal"],
                        parent["numeric_equal"],
                        target["numeric_equal"],
                    )
                )
                if not valid:
                    format_rule_errors += 1
        check("direct evidence for every auto-drop", missing_direct_edges == 0, f"missing={missing_direct_edges}")
        check("format-only drop rules", format_rule_errors == 0, f"mismatches={format_rule_errors}")

        edge_type_counts: Counter[str] = Counter()
        edge_score_errors = 0
        edge_rule_errors = 0
        lexical_text_errors = 0
        edge_rows = output_connection.execute(
            """
            SELECT sample_index_a, sample_index_b, edge_type,
                   format_auto, lexical_review, semantic_review, semantic_strong,
                   parent_cosine, target_cosine, pair_cosine,
                   parent_char_jaccard, target_char_jaccard,
                   parent_length_ratio, target_length_ratio,
                   parent_token_sequence_equal, target_token_sequence_equal,
                   parent_negation_equal, target_negation_equal,
                   parent_numeric_equal, target_numeric_equal,
                   guard_flags_json
            FROM duplicate_edges
            """
        )
        for row in edge_rows:
            left, right = int(row[0]), int(row[1])
            edge_type = str(row[2])
            edge_type_counts[edge_type] += 1
            if not (0 <= left < right < candidate_count):
                edge_rule_errors += 1
                continue
            if edge_type == "exact":
                if pair_hashes[left] != pair_hashes[right] or any(int(row[index]) for index in range(3, 7)):
                    edge_rule_errors += 1
                continue
            parent_cosine = float(
                np.asarray(embeddings[parent_rows[left]], dtype=np.float32)
                @ np.asarray(embeddings[parent_rows[right]], dtype=np.float32)
            )
            target_cosine = float(
                np.asarray(embeddings[target_rows[left]], dtype=np.float32)
                @ np.asarray(embeddings[target_rows[right]], dtype=np.float32)
            )
            pair_cosine = (parent_cosine + target_cosine) / 2.0
            if max(abs(parent_cosine - float(row[7])), abs(target_cosine - float(row[8])), abs(pair_cosine - float(row[9]))) > 2e-5:
                edge_score_errors += 1
            lexical = bool(row[4])
            semantic = bool(row[5])
            strong = bool(row[6])
            if semantic != (pair_cosine >= SEMANTIC_PAIR and parent_cosine >= SEMANTIC_COMPONENT and target_cosine >= SEMANTIC_COMPONENT):
                edge_rule_errors += 1
            if strong != (semantic and pair_cosine >= SEMANTIC_STRONG_PAIR and parent_cosine >= SEMANTIC_STRONG_COMPONENT and target_cosine >= SEMANTIC_STRONG_COMPONENT):
                edge_rule_errors += 1
            if bool(row[3]) and (edge_type != "format_only" or not lexical):
                edge_rule_errors += 1
            parent = compare_text(
                fetch_post_text(input_connection, parent_uids[left], "dedup_body", text_cache),
                fetch_post_text(input_connection, parent_uids[right], "dedup_body", text_cache),
            )
            target = compare_text(
                fetch_post_text(input_connection, target_uids[left], "dedup_body", text_cache),
                fetch_post_text(input_connection, target_uids[right], "dedup_body", text_cache),
            )
            recorded = (
                float(row[10]), float(row[11]), float(row[12]), float(row[13]),
                bool(row[14]), bool(row[15]), bool(row[16]), bool(row[17]), bool(row[18]), bool(row[19]),
            )
            expected = (
                parent["char_jaccard"], target["char_jaccard"], parent["length_ratio"], target["length_ratio"],
                parent["token_equal"], target["token_equal"], parent["negation_equal"], target["negation_equal"], parent["numeric_equal"], target["numeric_equal"],
            )
            numeric_match = all(
                abs(float(recorded[index]) - float(expected[index])) <= 2e-6
                for index in range(4)
            )
            boolean_match = recorded[4:] == expected[4:]
            if not (numeric_match and boolean_match):
                lexical_text_errors += 1
            threshold_match = all(
                (
                    parent["char_jaccard"] >= LEXICAL_JACCARD,
                    target["char_jaccard"] >= LEXICAL_JACCARD,
                    parent["length_ratio"] >= LEXICAL_LENGTH_RATIO,
                    target["length_ratio"] >= LEXICAL_LENGTH_RATIO,
                    parent["negation_equal"], target["negation_equal"],
                    parent["numeric_equal"], target["numeric_equal"],
                )
            )
            if lexical != threshold_match:
                lexical_text_errors += 1
            if bool(row[3]) and not (parent["token_equal"] and target["token_equal"]):
                lexical_text_errors += 1
            expected_guards: list[str] = []
            if not parent["negation_equal"]:
                expected_guards.append("parent_negation_mismatch")
            if not target["negation_equal"]:
                expected_guards.append("target_negation_mismatch")
            if not parent["numeric_equal"]:
                expected_guards.append("parent_numeric_mismatch")
            if not target["numeric_equal"]:
                expected_guards.append("target_numeric_mismatch")
            if token_counts[parent_rows[left]] >= MAX_TOKENS or token_counts[parent_rows[right]] >= MAX_TOKENS:
                expected_guards.append("parent_possible_truncation")
            if token_counts[target_rows[left]] >= MAX_TOKENS or token_counts[target_rows[right]] >= MAX_TOKENS:
                expected_guards.append("target_possible_truncation")
            if tuple(json.loads(str(row[20]))) != tuple(sorted(expected_guards)):
                edge_rule_errors += 1
            if not lexical and not semantic:
                edge_rule_errors += 1
        check("edge cosine recomputation", edge_score_errors == 0, f"mismatches={edge_score_errors}")
        check("edge threshold rules", edge_rule_errors == 0, f"mismatches={edge_rule_errors}")
        check("lexical edge text recomputation", lexical_text_errors == 0, f"mismatches={lexical_text_errors}")
        semantic_only_auto = output_connection.execute(
            """
            SELECT COUNT(*)
            FROM candidate_decisions AS d
            WHERE d.auto_decision != 'keep'
              AND NOT EXISTS (
                  SELECT 1 FROM duplicate_edges AS e
                  WHERE e.sample_index_a = MIN(d.candidate_index, (
                            SELECT c.candidate_index FROM candidate_decisions AS c
                            WHERE c.sample_uid = d.canonical_sample_uid
                        ))
                    AND e.sample_index_b = MAX(d.candidate_index, (
                            SELECT c.candidate_index FROM candidate_decisions AS c
                            WHERE c.sample_uid = d.canonical_sample_uid
                        ))
                    AND e.edge_type IN ('exact', 'format_only')
              )
            """
        ).fetchone()[0]
        check("no semantic-only auto-drop", int(semantic_only_auto) == 0, f"violations={semantic_only_auto}")

        review_clusters = output_connection.execute(
            "SELECT COUNT(DISTINCT review_cluster_uid) FROM candidate_decisions WHERE review_cluster_uid IS NOT NULL"
        ).fetchone()[0]
        review_members = output_connection.execute(
            "SELECT COUNT(*) FROM candidate_decisions WHERE review_cluster_uid IS NOT NULL"
        ).fetchone()[0]
        max_review_cluster = output_connection.execute(
            "SELECT COALESCE(MAX(n), 1) FROM (SELECT COUNT(*) AS n FROM candidate_decisions WHERE review_cluster_uid IS NOT NULL GROUP BY review_cluster_uid)"
        ).fetchone()[0]
        check("review cluster report", report["reviews"]["review_clusters"] == review_clusters and report["reviews"]["review_cluster_members"] == review_members and report["reviews"]["max_review_cluster_size"] == max_review_cluster, f"clusters={review_clusters}")

        replay_stats = run_embedding_replay_worker(
            replay_worker,
            args.input_db,
            args.db,
            args.embeddings,
            args.model_dir,
            args.threads,
            args.batch_size,
        )
        check(
            "embedding model replay",
            bool(replay_stats["passed"]),
            f"sampled_rows={replay_stats['sampled_rows']}",
        )
        check(
            "token count replay",
            int(replay_stats["token_count_errors"]) == 0,
            f"mismatches={replay_stats['token_count_errors']}",
        )

        faiss = load_faiss()
        faiss.omp_set_num_threads(args.threads)
        hnsw = faiss.read_index(str(args.index))
        exact_representative: dict[str, int] = {}
        for index, pair_hash in enumerate(pair_hashes):
            current = exact_representative.get(pair_hash)
            rank = (int(decisions[index][5]), int(decisions[index][6]), -int(decisions[index][7]), sample_uids[index])
            if current is None:
                exact_representative[pair_hash] = index
            else:
                current_rank = (int(decisions[current][5]), int(decisions[current][6]), -int(decisions[current][7]), sample_uids[current])
                if rank < current_rank:
                    exact_representative[pair_hash] = index
        representative_indices = sorted(exact_representative.values(), key=lambda index: sample_uids[index])
        check("HNSW dimensions", hnsw.d == PAIR_DIM and hnsw.ntotal == len(representative_indices), f"rows={hnsw.ntotal}, dimension={hnsw.d}")
        check("HNSW report rows", report["retrieval"]["rows"] == len(representative_indices), "exact representatives")

        audit_indices = heapq.nsmallest(
            min(RECALL_AUDIT_SIZE, len(representative_indices)),
            representative_indices,
            key=lambda index: hashlib.sha256(sample_uids[index].encode("ascii")).digest(),
        )
        queries = pair_vectors(parent_rows, target_rows, embeddings, audit_indices)
        flat = faiss.IndexFlatIP(PAIR_DIM)
        for block in chunks(representative_indices, 10000):
            flat.add(pair_vectors(parent_rows, target_rows, embeddings, block))
        _, exact_neighbors = flat.search(queries, INITIAL_K)
        _, approximate_neighbors = hnsw.search(queries, INITIAL_K)
        recalls = []
        for exact, approximate in zip(exact_neighbors, approximate_neighbors):
            exact_set = {int(value) for value in exact}
            approximate_set = {int(value) for value in approximate}
            recalls.append(len(exact_set & approximate_set) / len(exact_set))
        mean_recall = float(np.mean(recalls)) if recalls else 1.0
        min_recall = float(np.min(recalls)) if recalls else 1.0
        check("HNSW exact recall gate", mean_recall >= RECALL_REQUIRED, f"queries={len(recalls)}, k={INITIAL_K}")
        check("HNSW recall report", abs(mean_recall - float(report["retrieval"]["mean_recall_at_k"])) <= 1e-12 and abs(min_recall - float(report["retrieval"]["min_recall_at_k"])) <= 1e-12, "independent FlatIP audit")
        del flat

        adaptive_queries = 0
        saturated_queries = 0
        for block in chunks(representative_indices, 1000):
            vectors = pair_vectors(parent_rows, target_rows, embeddings, block)
            scores, _ = hnsw.search(vectors, INITIAL_K)
            adaptive_offsets = np.flatnonzero(scores[:, -1] >= RETRIEVAL_FLOOR)
            adaptive_queries += int(len(adaptive_offsets))
            if len(adaptive_offsets):
                expanded_scores, _ = hnsw.search(vectors[adaptive_offsets], MAX_K)
                saturated_queries += int(np.count_nonzero(expanded_scores[:, -1] >= SEMANTIC_PAIR))
        check("adaptive retrieval report", adaptive_queries == report["retrieval"]["adaptive_queries"], f"queries={adaptive_queries}")
        check("retrieval saturation gate", saturated_queries == 0, f"saturated={saturated_queries}")
        check("retrieval saturation report", saturated_queries == report["retrieval"]["saturated_queries_at_max_k"], "independent HNSW search")

    finally:
        input_connection.close()
        output_connection.close()

    status = "passed" if not mismatches else "failed"
    payload: dict[str, object] = {
        "schema_version": "1",
        "pipeline_id": PIPELINE_ID,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "inputs": {
            "input_database_filename": args.input_db.name,
            "input_database_sha256": input_sha,
            "dedup_database_filename": args.db.name,
            "dedup_database_sha256": db_sha,
            "embeddings_filename": args.embeddings.name,
            "embeddings_sha256": embeddings_sha,
            "index_filename": args.index.name,
            "index_sha256": index_sha,
            "aggregate_report_filename": args.report.name,
            "aggregate_report_sha256": report_sha,
            "verification_script_sha256": sha256_file(Path(__file__).resolve()),
            "embedding_worker_sha256": embedding_worker_sha,
            "embedding_replay_worker_sha256": replay_worker_sha,
        },
        "aggregate": {
            "candidate_rows": int(report["input"]["eligible_candidates"]),
            "kept_rows": int(report["decisions"]["eligible_after_auto_dedup"]),
            "auto_dropped_rows": int(report["decisions"]["auto_dropped"]),
            "edge_type_counts": dict(sorted(edge_type_counts.items())),
            "mean_recall_at_64": mean_recall,
            "min_recall_at_64": min_recall,
            "adaptive_queries": adaptive_queries,
            "saturated_queries_at_max_k": saturated_queries,
        },
        "checks": checks,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "public_payload_violations": public_violations,
    }
    output_violations = public_payload_violations(payload, "verification")
    if output_violations:
        raise ValueError(f"verification payload privacy violations: {output_violations}")
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
