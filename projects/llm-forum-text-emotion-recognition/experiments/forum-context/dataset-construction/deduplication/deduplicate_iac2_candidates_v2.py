#!/usr/bin/env python3
"""Build private exact, lexical-near, and semantic-near deduplication evidence."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import numpy as np


SCHEMA_VERSION = "1"
PIPELINE_ID = "DATA-FCTX-DEDUP-V2"
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
PAIR_DIM = EMBEDDING_DIM * 2
MAX_TOKENS = 256
HNSW_M = 32
HNSW_EF_CONSTRUCTION = 200
HNSW_EF_SEARCH = 768
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
SEVERE_FLAG_SUFFIXES = {
    "decode_replacement",
    "quote_structure_unverified",
    "quote_text_missing",
    "html_quote_unstructured",
    "no_lexical_tokens",
    "url_only",
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


@dataclass(frozen=True)
class Candidate:
    index: int
    sample_uid: str
    parent_row: int
    target_row: int
    pair_sha256: str
    severe_flag_count: int
    total_flag_count: int
    combined_word_count_capped: int

    @property
    def rank(self) -> tuple[int, int, int, str]:
        return (
            self.severe_flag_count,
            self.total_flag_count,
            -self.combined_word_count_capped,
            self.sample_uid,
        )


@dataclass(frozen=True)
class TextMetrics:
    char_jaccard: float
    length_ratio: float
    token_sequence_equal: bool
    negation_equal: bool
    numeric_equal: bool


@dataclass(frozen=True)
class ClassifiedEdge:
    index_a: int
    index_b: int
    edge_type: str
    format_auto: bool
    lexical_review: bool
    semantic_review: bool
    semantic_strong: bool
    parent_cosine: float
    target_cosine: float
    pair_cosine: float
    parent_metrics: TextMetrics
    target_metrics: TextMetrics
    guard_flags: tuple[str, ...]


class UnionFind:
    def __init__(self, values: Iterable[int]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: int) -> int:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: int, right: int) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left != root_right:
            self.parent[max(root_left, root_right)] = min(root_left, root_right)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-db", type=Path, required=True)
    parser.add_argument("--cleaning-manifest", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output-db", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--expected-candidates", type=int, default=403336)
    parser.add_argument("--reuse-embeddings-from", type=Path)
    parser.add_argument("--reuse-index-from", type=Path)
    parser.add_argument("--reuse-manifest", type=Path)
    parser.add_argument("--reuse-report", type=Path)
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_faiss():
    """Delay FAISS/OpenMP loading until PyTorch embedding has finished."""
    import faiss

    return faiss


def sha256_model(model_dir: Path) -> tuple[str, dict[str, str]]:
    digest = hashlib.sha256()
    file_hashes: dict[str, str] = {}
    for relative in MODEL_FILES:
        path = model_dir / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        file_hash = sha256_file(path)
        file_hashes[relative] = file_hash
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest(), file_hashes


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


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
    if not union:
        return 1.0
    return len(left & right) / len(union)


def length_ratio(left: str, right: str) -> float:
    longest = max(len(left), len(right))
    if not longest:
        return 1.0
    return min(len(left), len(right)) / longest


def compare_text(left: str, right: str) -> TextMetrics:
    left_tokens = tokens(left)
    right_tokens = tokens(right)
    return TextMetrics(
        char_jaccard=set_jaccard(char_ngrams(left), char_ngrams(right)),
        length_ratio=length_ratio(left, right),
        token_sequence_equal=left_tokens == right_tokens,
        negation_equal=negation_signature(left_tokens)
        == negation_signature(right_tokens),
        numeric_equal=numeric_signature(left_tokens) == numeric_signature(right_tokens),
    )


def classify_edge(
    index_a: int,
    index_b: int,
    parent_a: str,
    target_a: str,
    parent_b: str,
    target_b: str,
    parent_cosine: float,
    target_cosine: float,
    parent_truncated: bool,
    target_truncated: bool,
) -> ClassifiedEdge | None:
    pair_cosine = (parent_cosine + target_cosine) / 2.0
    if pair_cosine < RETRIEVAL_FLOOR:
        return None

    parent_metrics = compare_text(parent_a, parent_b)
    target_metrics = compare_text(target_a, target_b)
    guards_match = (
        parent_metrics.negation_equal
        and parent_metrics.numeric_equal
        and target_metrics.negation_equal
        and target_metrics.numeric_equal
    )
    lexical_review = (
        guards_match
        and parent_metrics.char_jaccard >= LEXICAL_JACCARD
        and target_metrics.char_jaccard >= LEXICAL_JACCARD
        and parent_metrics.length_ratio >= LEXICAL_LENGTH_RATIO
        and target_metrics.length_ratio >= LEXICAL_LENGTH_RATIO
    )
    format_auto = (
        lexical_review
        and parent_metrics.token_sequence_equal
        and target_metrics.token_sequence_equal
    )
    semantic_review = (
        pair_cosine >= SEMANTIC_PAIR
        and parent_cosine >= SEMANTIC_COMPONENT
        and target_cosine >= SEMANTIC_COMPONENT
    )
    semantic_strong = (
        semantic_review
        and pair_cosine >= SEMANTIC_STRONG_PAIR
        and parent_cosine >= SEMANTIC_STRONG_COMPONENT
        and target_cosine >= SEMANTIC_STRONG_COMPONENT
    )
    if not lexical_review and not semantic_review:
        return None

    guard_flags: list[str] = []
    if not parent_metrics.negation_equal:
        guard_flags.append("parent_negation_mismatch")
    if not target_metrics.negation_equal:
        guard_flags.append("target_negation_mismatch")
    if not parent_metrics.numeric_equal:
        guard_flags.append("parent_numeric_mismatch")
    if not target_metrics.numeric_equal:
        guard_flags.append("target_numeric_mismatch")
    if parent_truncated:
        guard_flags.append("parent_possible_truncation")
    if target_truncated:
        guard_flags.append("target_possible_truncation")

    if format_auto:
        edge_type = "format_only"
    elif lexical_review and semantic_review:
        edge_type = "lexical_semantic_review"
    elif lexical_review:
        edge_type = "lexical_review"
    else:
        edge_type = "semantic_review"

    return ClassifiedEdge(
        index_a=min(index_a, index_b),
        index_b=max(index_a, index_b),
        edge_type=edge_type,
        format_auto=format_auto,
        lexical_review=lexical_review,
        semantic_review=semantic_review,
        semantic_strong=semantic_strong,
        parent_cosine=parent_cosine,
        target_cosine=target_cosine,
        pair_cosine=pair_cosine,
        parent_metrics=parent_metrics,
        target_metrics=target_metrics,
        guard_flags=tuple(sorted(guard_flags)),
    )


def severe_flag_count(flags: Sequence[str]) -> int:
    return sum(
        any(flag == suffix or flag.endswith(f"_{suffix}") for suffix in SEVERE_FLAG_SUFFIXES)
        for flag in flags
    )


def choose_exact_representatives(
    candidates: Sequence[Candidate],
) -> tuple[dict[int, int], dict[str, list[int]]]:
    groups: dict[str, list[int]] = defaultdict(list)
    for candidate in candidates:
        groups[candidate.pair_sha256].append(candidate.index)
    representatives: dict[int, int] = {}
    for members in groups.values():
        representative = min(members, key=lambda index: candidates[index].rank)
        for member in members:
            representatives[member] = representative
    return representatives, groups


def assign_direct_representatives(
    candidates: Sequence[Candidate],
    exact_representative: dict[int, int],
    exact_groups: dict[str, list[int]],
    format_edges: Iterable[tuple[int, int]],
) -> tuple[dict[int, int], dict[int, str]]:
    reps = sorted(set(exact_representative.values()), key=lambda index: candidates[index].rank)
    adjacency: dict[int, set[int]] = defaultdict(set)
    for left, right in format_edges:
        left_rep = exact_representative[left]
        right_rep = exact_representative[right]
        if left_rep == right_rep:
            continue
        adjacency[left_rep].add(right_rep)
        adjacency[right_rep].add(left_rep)

    rep_to_final: dict[int, int] = {}
    for representative in reps:
        if representative in rep_to_final:
            continue
        rep_to_final[representative] = representative
        for neighbor in sorted(
            adjacency.get(representative, set()),
            key=lambda index: candidates[index].rank,
        ):
            if neighbor not in rep_to_final:
                rep_to_final[neighbor] = representative

    final_representative: dict[int, int] = {}
    decisions: dict[int, str] = {}
    for pair_hash, members in exact_groups.items():
        del pair_hash
        group_rep = exact_representative[members[0]]
        final = rep_to_final[group_rep]
        for member in members:
            final_representative[member] = final
            if member == final:
                decisions[member] = "keep"
            elif candidates[member].pair_sha256 == candidates[final].pair_sha256:
                decisions[member] = "drop_exact"
            else:
                decisions[member] = "drop_format_only"
    return final_representative, decisions


def direct_decision_edges(
    candidates: Sequence[Candidate],
    final_representative: dict[int, int],
    decisions: dict[int, str],
    embeddings: np.ndarray,
    dedup_texts: Sequence[str],
    token_counts: np.ndarray,
) -> list[tuple[object, ...]]:
    """Create one auditable edge from every auto-drop to its kept representative."""
    rows: list[tuple[object, ...]] = []
    for index, decision in decisions.items():
        if decision == "keep":
            continue
        canonical_index = final_representative[index]
        if decisions[canonical_index] != "keep":
            raise AssertionError("auto-drop canonical is not kept")
        candidate = candidates[index]
        canonical = candidates[canonical_index]
        left = min(index, canonical_index)
        right = max(index, canonical_index)
        if decision == "drop_exact":
            if candidate.pair_sha256 != canonical.pair_sha256:
                raise AssertionError("exact drop does not share the canonical pair hash")
            rows.append(
                (
                    left,
                    right,
                    "exact",
                    0,
                    0,
                    0,
                    0,
                    None,
                    None,
                    None,
                    1.0,
                    1.0,
                    1.0,
                    1.0,
                    1,
                    1,
                    1,
                    1,
                    1,
                    1,
                    "[]",
                )
            )
            continue
        if decision != "drop_format_only":
            raise AssertionError(f"unexpected auto decision: {decision}")

        parent_metrics = compare_text(
            dedup_texts[candidate.parent_row],
            dedup_texts[canonical.parent_row],
        )
        target_metrics = compare_text(
            dedup_texts[candidate.target_row],
            dedup_texts[canonical.target_row],
        )
        lexical_match = (
            parent_metrics.char_jaccard >= LEXICAL_JACCARD
            and target_metrics.char_jaccard >= LEXICAL_JACCARD
            and parent_metrics.length_ratio >= LEXICAL_LENGTH_RATIO
            and target_metrics.length_ratio >= LEXICAL_LENGTH_RATIO
            and parent_metrics.negation_equal
            and target_metrics.negation_equal
            and parent_metrics.numeric_equal
            and target_metrics.numeric_equal
            and parent_metrics.token_sequence_equal
            and target_metrics.token_sequence_equal
        )
        if not lexical_match:
            raise AssertionError("format-only drop lacks a direct qualifying edge")
        parent_cosine = float(
            np.asarray(embeddings[candidate.parent_row], dtype=np.float32)
            @ np.asarray(embeddings[canonical.parent_row], dtype=np.float32)
        )
        target_cosine = float(
            np.asarray(embeddings[candidate.target_row], dtype=np.float32)
            @ np.asarray(embeddings[canonical.target_row], dtype=np.float32)
        )
        pair_cosine = (parent_cosine + target_cosine) / 2.0
        semantic_review = (
            pair_cosine >= SEMANTIC_PAIR
            and parent_cosine >= SEMANTIC_COMPONENT
            and target_cosine >= SEMANTIC_COMPONENT
        )
        semantic_strong = (
            semantic_review
            and pair_cosine >= SEMANTIC_STRONG_PAIR
            and parent_cosine >= SEMANTIC_STRONG_COMPONENT
            and target_cosine >= SEMANTIC_STRONG_COMPONENT
        )
        guard_flags: list[str] = []
        if (
            token_counts[candidate.parent_row] >= MAX_TOKENS
            or token_counts[canonical.parent_row] >= MAX_TOKENS
        ):
            guard_flags.append("parent_possible_truncation")
        if (
            token_counts[candidate.target_row] >= MAX_TOKENS
            or token_counts[canonical.target_row] >= MAX_TOKENS
        ):
            guard_flags.append("target_possible_truncation")
        rows.append(
            edge_row(
                ClassifiedEdge(
                    index_a=left,
                    index_b=right,
                    edge_type="format_only",
                    format_auto=True,
                    lexical_review=True,
                    semantic_review=semantic_review,
                    semantic_strong=semantic_strong,
                    parent_cosine=parent_cosine,
                    target_cosine=target_cosine,
                    pair_cosine=pair_cosine,
                    parent_metrics=parent_metrics,
                    target_metrics=target_metrics,
                    guard_flags=tuple(guard_flags),
                )
            )
        )
    return rows


def pair_vectors(
    candidates: Sequence[Candidate],
    embeddings: np.ndarray,
    indices: Sequence[int],
) -> np.ndarray:
    parent_rows = np.fromiter(
        (candidates[index].parent_row for index in indices),
        dtype=np.int64,
        count=len(indices),
    )
    target_rows = np.fromiter(
        (candidates[index].target_row for index in indices),
        dtype=np.int64,
        count=len(indices),
    )
    parent = np.asarray(embeddings[parent_rows], dtype=np.float32)
    target = np.asarray(embeddings[target_rows], dtype=np.float32)
    return np.concatenate((parent, target), axis=1) / math.sqrt(2.0)


def deterministic_audit_indices(candidates: Sequence[Candidate], size: int) -> list[int]:
    ranked = sorted(
        range(len(candidates)),
        key=lambda index: hashlib.sha256(
            candidates[index].sample_uid.encode("ascii")
        ).digest(),
    )
    return ranked[: min(size, len(ranked))]


def open_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def load_posts(
    connection: sqlite3.Connection,
) -> tuple[list[str], list[str], list[int]]:
    query = """
        WITH used(post_uid) AS (
            SELECT target_post_uid
            FROM candidate_pairs
            WHERE eligible = 1
            UNION
            SELECT parent_post_uid
            FROM candidate_pairs
            WHERE eligible = 1
        )
        SELECT p.post_uid,
               p.dedup_body,
               p.word_count
        FROM used
        JOIN cleaned_posts AS p ON p.post_uid = used.post_uid
        ORDER BY p.post_uid
    """
    post_uids: list[str] = []
    dedup_texts: list[str] = []
    word_counts: list[int] = []
    for post_uid, dedup_body, word_count in connection.execute(query):
        post_uids.append(post_uid)
        dedup_texts.append(dedup_body or "")
        word_counts.append(int(word_count))
    return post_uids, dedup_texts, word_counts


def load_candidates(
    connection: sqlite3.Connection,
    post_row: dict[str, int],
    word_counts: Sequence[int],
) -> list[Candidate]:
    query = """
        SELECT sample_uid,
               parent_post_uid,
               target_post_uid,
               pair_sha256,
               soft_flags_json
        FROM candidate_pairs
        WHERE eligible = 1
        ORDER BY sample_uid
    """
    candidates: list[Candidate] = []
    for index, row in enumerate(connection.execute(query)):
        sample_uid, parent_uid, target_uid, pair_hash, flags_json = row
        parent_index = post_row[parent_uid]
        target_index = post_row[target_uid]
        flags = tuple(json.loads(flags_json))
        candidates.append(
            Candidate(
                index=index,
                sample_uid=sample_uid,
                parent_row=parent_index,
                target_row=target_index,
                pair_sha256=pair_hash,
                severe_flag_count=severe_flag_count(flags),
                total_flag_count=len(flags),
                combined_word_count_capped=min(
                    int(word_counts[parent_index]) + int(word_counts[target_index]),
                    2048,
                ),
            )
        )
    return candidates


def run_embedding_worker(
    worker: Path,
    input_db: Path,
    model_dir: Path,
    embeddings: Path,
    token_counts: Path,
    stats: Path,
    batch_size: int,
    threads: int,
) -> dict[str, object]:
    subprocess.run(
        [
            sys.executable,
            str(worker),
            "--input-db",
            str(input_db),
            "--model-dir",
            str(model_dir),
            "--embeddings",
            str(embeddings),
            "--token-counts",
            str(token_counts),
            "--stats",
            str(stats),
            "--batch-size",
            str(batch_size),
            "--threads",
            str(threads),
        ],
        check=True,
    )
    payload = json.loads(stats.read_text(encoding="utf-8"))
    if payload.get("dimension") != EMBEDDING_DIM or payload.get("dtype") != "float32":
        raise ValueError("embedding worker returned an unexpected format")
    if payload.get("mode") != "embeddings_and_token_counts":
        raise ValueError("embedding worker returned an unexpected mode")
    if payload.get("preflight_limit") is not None:
        raise ValueError("official embedding worker unexpectedly used a row limit")
    return payload


def run_token_count_worker(
    worker: Path,
    input_db: Path,
    model_dir: Path,
    token_counts: Path,
    stats: Path,
    batch_size: int,
    threads: int,
) -> dict[str, object]:
    subprocess.run(
        [
            sys.executable,
            str(worker),
            "--input-db",
            str(input_db),
            "--model-dir",
            str(model_dir),
            "--token-counts",
            str(token_counts),
            "--stats",
            str(stats),
            "--batch-size",
            str(batch_size),
            "--threads",
            str(threads),
            "--token-counts-only",
        ],
        check=True,
    )
    payload = json.loads(stats.read_text(encoding="utf-8"))
    if payload.get("mode") != "token_counts_only":
        raise ValueError("token-count worker returned an unexpected mode")
    if payload.get("preflight_limit") is not None:
        raise ValueError("official token-count worker unexpectedly used a row limit")
    return payload


def validate_reuse_inputs(
    args: argparse.Namespace,
    input_db_sha: str,
    model_sha: str,
) -> dict[str, object] | None:
    values = (
        args.reuse_embeddings_from,
        args.reuse_index_from,
        args.reuse_manifest,
        args.reuse_report,
    )
    if not any(values):
        return None
    if not all(values):
        raise ValueError("all four reuse inputs must be provided together")
    assert args.reuse_embeddings_from is not None
    assert args.reuse_index_from is not None
    assert args.reuse_manifest is not None
    assert args.reuse_report is not None
    for path in values:
        assert path is not None
        if not path.is_file():
            raise FileNotFoundError(path)
    manifest = json.loads(args.reuse_manifest.read_text(encoding="utf-8"))
    report = json.loads(args.reuse_report.read_text(encoding="utf-8"))
    if manifest.get("pipeline_id") != "DATA-FCTX-DEDUP-V1":
        raise ValueError("reuse manifest is not DATA-FCTX-DEDUP-V1")
    if manifest.get("artifact_status") != "failed_retrieval_quality_gate":
        raise ValueError("reuse source is not the frozen failed V1 run")
    if report.get("status") != "failed_retrieval_quality_gate":
        raise ValueError("reuse report status does not match the V1 manifest")
    if report.get("pipeline_id") != "DATA-FCTX-DEDUP-V1":
        raise ValueError("reuse report is not DATA-FCTX-DEDUP-V1")
    if manifest["input"]["database_sha256"] != input_db_sha:
        raise ValueError("reuse source used a different cleaning database")
    if report["input"]["database_sha256"] != input_db_sha:
        raise ValueError("reuse report used a different cleaning database")
    if report["model"]["model_id"] != MODEL_ID:
        raise ValueError("reuse source used a different embedding model")
    if report["model"]["selected_files_sha256"] != model_sha:
        raise ValueError("reuse source used different embedding model files")
    if report["model"]["revision"] != MODEL_REVISION:
        raise ValueError("reuse source used a different model revision")
    if report["input"]["eligible_candidates"] != args.expected_candidates:
        raise ValueError("reuse source has a different eligible-candidate count")
    exact = report["exact_duplicates"]
    expected_unique_pairs = args.expected_candidates - (
        int(exact["members"]) - int(exact["clusters"])
    )
    expected_retrieval = {
        "rows": expected_unique_pairs,
        "dimension": PAIR_DIM,
        "M": HNSW_M,
        "ef_construction": HNSW_EF_CONSTRUCTION,
    }
    for key, expected in expected_retrieval.items():
        if report["retrieval"].get(key) != expected:
            raise ValueError(f"reuse source has unexpected retrieval setting: {key}")
    if sha256_file(args.reuse_report) != manifest["aggregate_report"]["sha256"]:
        raise ValueError("reuse report hash does not match its manifest")
    embedding_sha = sha256_file(args.reuse_embeddings_from)
    index_sha = sha256_file(args.reuse_index_from)
    if embedding_sha != manifest["private_artifacts"]["embeddings"]["sha256"]:
        raise ValueError("reuse embedding hash does not match its manifest")
    if index_sha != manifest["private_artifacts"]["index"]["sha256"]:
        raise ValueError("reuse index hash does not match its manifest")
    if manifest["private_artifacts"]["embeddings"]["shape"][1] != EMBEDDING_DIM:
        raise ValueError("reuse embeddings have the wrong dimension")
    return {
        "source_pipeline_id": manifest["pipeline_id"],
        "source_artifact_status": manifest["artifact_status"],
        "source_manifest_filename": args.reuse_manifest.name,
        "source_manifest_sha256": sha256_file(args.reuse_manifest),
        "source_report_filename": args.reuse_report.name,
        "source_report_sha256": sha256_file(args.reuse_report),
        "embedding_filename": args.reuse_embeddings_from.name,
        "embedding_sha256": embedding_sha,
        "index_filename": args.reuse_index_from.name,
        "index_sha256": index_sha,
        "reused_components": ["post_embeddings", "HNSW_graph"],
        "reused_decisions_or_edges": False,
    }


def initialize_output_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute("PRAGMA temp_store=FILE")
    connection.executescript(
        """
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE post_embedding_rows (
            post_uid TEXT PRIMARY KEY,
            embedding_row INTEGER NOT NULL UNIQUE,
            token_count_capped INTEGER NOT NULL,
            possible_truncation INTEGER NOT NULL
        );

        CREATE TABLE candidate_decisions (
            candidate_index INTEGER PRIMARY KEY,
            sample_uid TEXT NOT NULL UNIQUE,
            canonical_sample_uid TEXT NOT NULL,
            auto_decision TEXT NOT NULL,
            eligible_after_auto_dedup INTEGER NOT NULL,
            severe_flag_count INTEGER NOT NULL,
            total_flag_count INTEGER NOT NULL,
            combined_word_count_capped INTEGER NOT NULL,
            review_status TEXT NOT NULL,
            review_cluster_uid TEXT
        );

        CREATE TABLE duplicate_edges (
            sample_index_a INTEGER NOT NULL,
            sample_index_b INTEGER NOT NULL,
            edge_type TEXT NOT NULL,
            format_auto INTEGER NOT NULL,
            lexical_review INTEGER NOT NULL,
            semantic_review INTEGER NOT NULL,
            semantic_strong INTEGER NOT NULL,
            parent_cosine REAL,
            target_cosine REAL,
            pair_cosine REAL,
            parent_char_jaccard REAL,
            target_char_jaccard REAL,
            parent_length_ratio REAL,
            target_length_ratio REAL,
            parent_token_sequence_equal INTEGER,
            target_token_sequence_equal INTEGER,
            parent_negation_equal INTEGER,
            target_negation_equal INTEGER,
            parent_numeric_equal INTEGER,
            target_numeric_equal INTEGER,
            guard_flags_json TEXT NOT NULL,
            PRIMARY KEY (sample_index_a, sample_index_b, edge_type)
        );

        CREATE TABLE retrieval_audit (
            name TEXT PRIMARY KEY,
            value REAL NOT NULL
        );
        """
    )
    return connection


def edge_row(edge: ClassifiedEdge) -> tuple[object, ...]:
    return (
        edge.index_a,
        edge.index_b,
        edge.edge_type,
        int(edge.format_auto),
        int(edge.lexical_review),
        int(edge.semantic_review),
        int(edge.semantic_strong),
        edge.parent_cosine,
        edge.target_cosine,
        edge.pair_cosine,
        edge.parent_metrics.char_jaccard,
        edge.target_metrics.char_jaccard,
        edge.parent_metrics.length_ratio,
        edge.target_metrics.length_ratio,
        int(edge.parent_metrics.token_sequence_equal),
        int(edge.target_metrics.token_sequence_equal),
        int(edge.parent_metrics.negation_equal),
        int(edge.target_metrics.negation_equal),
        int(edge.parent_metrics.numeric_equal),
        int(edge.target_metrics.numeric_equal),
        json.dumps(edge.guard_flags, ensure_ascii=True),
    )


def insert_edges(
    connection: sqlite3.Connection,
    rows: Sequence[tuple[object, ...]],
) -> None:
    if not rows:
        return
    connection.executemany(
        """
        INSERT OR IGNORE INTO duplicate_edges
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def build_hnsw(
    candidates: Sequence[Candidate],
    representative_indices: Sequence[int],
    embeddings: np.ndarray,
    output_path: Path,
    threads: int,
) -> tuple[object, dict[str, object]]:
    faiss = load_faiss()
    faiss.omp_set_num_threads(threads)
    index = faiss.IndexHNSWFlat(PAIR_DIM, HNSW_M, faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efConstruction = HNSW_EF_CONSTRUCTION
    index.hnsw.efSearch = HNSW_EF_SEARCH
    started = time.monotonic()
    for start in range(0, len(representative_indices), 5000):
        stop = min(start + 5000, len(representative_indices))
        vectors = pair_vectors(
            candidates,
            embeddings,
            representative_indices[start:stop],
        )
        index.add(vectors)
        if stop % 50000 == 0 or stop == len(representative_indices):
            print(f"indexed pairs: {stop:,}/{len(representative_indices):,}", flush=True)
    faiss.write_index(index, str(output_path))
    elapsed = time.monotonic() - started
    return index, {
        "rows": len(representative_indices),
        "dimension": PAIR_DIM,
        "M": HNSW_M,
        "ef_construction": HNSW_EF_CONSTRUCTION,
        "ef_search": HNSW_EF_SEARCH,
        "elapsed_seconds": round(elapsed, 3),
    }


def recall_audit(
    index: object,
    candidates: Sequence[Candidate],
    representative_indices: Sequence[int],
    embeddings: np.ndarray,
) -> dict[str, object]:
    faiss = load_faiss()
    local_candidates = [candidates[index] for index in representative_indices]
    audit_local = deterministic_audit_indices(local_candidates, RECALL_AUDIT_SIZE)
    query_global = [representative_indices[index] for index in audit_local]
    queries = pair_vectors(candidates, embeddings, query_global)

    flat = faiss.IndexFlatIP(PAIR_DIM)
    for start in range(0, len(representative_indices), 10000):
        stop = min(start + 10000, len(representative_indices))
        flat.add(
            pair_vectors(
                candidates,
                embeddings,
                representative_indices[start:stop],
            )
        )
    _, exact_neighbors = flat.search(queries, INITIAL_K)
    _, approximate_neighbors = index.search(queries, INITIAL_K)
    recalls = []
    for exact, approximate in zip(exact_neighbors, approximate_neighbors):
        exact_set = {int(value) for value in exact}
        approximate_set = {int(value) for value in approximate}
        recalls.append(len(exact_set & approximate_set) / len(exact_set))
    del flat
    gc.collect()
    return {
        "queries": len(audit_local),
        "k": INITIAL_K,
        "mean_recall_at_k": float(np.mean(recalls)) if recalls else 1.0,
        "min_recall_at_k": float(np.min(recalls)) if recalls else 1.0,
        "required_mean_recall": RECALL_REQUIRED,
    }


def search_and_classify(
    connection: sqlite3.Connection,
    index: object,
    candidates: Sequence[Candidate],
    representative_indices: Sequence[int],
    embeddings: np.ndarray,
    dedup_texts: Sequence[str],
    token_counts: np.ndarray,
) -> tuple[set[tuple[int, int]], dict[str, object]]:
    faiss = load_faiss()
    local_to_global = np.asarray(representative_indices, dtype=np.int64)
    seen: set[tuple[int, int, str]] = set()
    format_edges: set[tuple[int, int]] = set()
    edge_counts: Counter[str] = Counter()
    guard_counts: Counter[str] = Counter()
    adaptive_queries = 0
    saturated_queries = 0
    processed = 0
    started = time.monotonic()
    rows_to_insert: list[tuple[object, ...]] = []

    for start in range(0, len(representative_indices), 1000):
        stop = min(start + 1000, len(representative_indices))
        query_globals = representative_indices[start:stop]
        vectors = pair_vectors(candidates, embeddings, query_globals)
        scores, neighbors = index.search(vectors, INITIAL_K)
        for offset, global_index in enumerate(query_globals):
            row_scores = scores[offset]
            row_neighbors = neighbors[offset]
            if row_scores[-1] >= RETRIEVAL_FLOOR:
                adaptive_queries += 1
                expanded_scores, expanded_neighbors = index.search(
                    vectors[offset : offset + 1],
                    MAX_K,
                )
                row_scores = expanded_scores[0]
                row_neighbors = expanded_neighbors[0]
                if row_scores[-1] >= SEMANTIC_PAIR:
                    saturated_queries += 1

            candidate_a = candidates[global_index]
            parent_a_text = dedup_texts[candidate_a.parent_row]
            target_a_text = dedup_texts[candidate_a.target_row]
            parent_a_embedding = np.asarray(
                embeddings[candidate_a.parent_row],
                dtype=np.float32,
            )
            target_a_embedding = np.asarray(
                embeddings[candidate_a.target_row],
                dtype=np.float32,
            )
            for score, local_neighbor in zip(row_scores, row_neighbors):
                if local_neighbor < 0 or score < RETRIEVAL_FLOOR:
                    break
                neighbor_global = int(local_to_global[int(local_neighbor)])
                if neighbor_global == global_index:
                    continue
                left = min(global_index, neighbor_global)
                right = max(global_index, neighbor_global)
                candidate_b = candidates[neighbor_global]
                if candidate_a.pair_sha256 == candidate_b.pair_sha256:
                    continue

                parent_cosine = float(
                    parent_a_embedding
                    @ np.asarray(embeddings[candidate_b.parent_row], dtype=np.float32)
                )
                target_cosine = float(
                    target_a_embedding
                    @ np.asarray(embeddings[candidate_b.target_row], dtype=np.float32)
                )
                edge = classify_edge(
                    left,
                    right,
                    parent_a_text,
                    target_a_text,
                    dedup_texts[candidate_b.parent_row],
                    dedup_texts[candidate_b.target_row],
                    parent_cosine,
                    target_cosine,
                    bool(
                        token_counts[candidate_a.parent_row] >= MAX_TOKENS
                        or token_counts[candidate_b.parent_row] >= MAX_TOKENS
                    ),
                    bool(
                        token_counts[candidate_a.target_row] >= MAX_TOKENS
                        or token_counts[candidate_b.target_row] >= MAX_TOKENS
                    ),
                )
                if edge is None:
                    continue
                edge_key = (edge.index_a, edge.index_b, edge.edge_type)
                if edge_key in seen:
                    continue
                seen.add(edge_key)
                rows_to_insert.append(edge_row(edge))
                edge_counts[edge.edge_type] += 1
                guard_counts.update(edge.guard_flags)
                if edge.format_auto:
                    format_edges.add((edge.index_a, edge.index_b))
                if len(rows_to_insert) >= 2000:
                    insert_edges(connection, rows_to_insert)
                    rows_to_insert.clear()

        processed += stop - start
        if processed % 25000 == 0 or processed == len(representative_indices):
            elapsed = max(time.monotonic() - started, 1e-9)
            print(
                f"searched pairs: {processed:,}/{len(representative_indices):,} "
                f"({processed / elapsed:.2f} rows/s)",
                flush=True,
            )
    insert_edges(connection, rows_to_insert)
    connection.commit()
    return format_edges, {
        "edge_type_counts": dict(sorted(edge_counts.items())),
        "guard_flag_counts": dict(sorted(guard_counts.items())),
        "adaptive_queries": adaptive_queries,
        "saturated_queries_at_max_k": saturated_queries,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def review_assignments(
    connection: sqlite3.Connection,
    final_representative: dict[int, int],
    decisions: dict[int, str],
    candidates: Sequence[Candidate],
) -> tuple[dict[int, str], dict[int, str | None], dict[str, object]]:
    kept = {index for index, decision in decisions.items() if decision == "keep"}
    union_find = UnionFind(kept)
    review_types: dict[int, set[str]] = defaultdict(set)
    review_edges = 0
    for left, right, lexical, semantic in connection.execute(
        """
        SELECT sample_index_a, sample_index_b, lexical_review, semantic_review
        FROM duplicate_edges
        WHERE lexical_review = 1 OR semantic_review = 1
        """
    ):
        left_final = final_representative[int(left)]
        right_final = final_representative[int(right)]
        if left_final == right_final:
            continue
        if left_final not in kept or right_final not in kept:
            raise AssertionError("review edge did not resolve to kept representatives")
        union_find.union(left_final, right_final)
        review_edges += 1
        if lexical:
            review_types[left_final].add("lexical")
            review_types[right_final].add("lexical")
        if semantic:
            review_types[left_final].add("semantic")
            review_types[right_final].add("semantic")

    components: dict[int, list[int]] = defaultdict(list)
    for index in kept:
        components[union_find.find(index)].append(index)
    review_components = [members for members in components.values() if len(members) > 1]
    cluster_uids: dict[int, str | None] = {index: None for index in range(len(candidates))}
    for members in review_components:
        digest = hashlib.sha256()
        for sample_uid in sorted(candidates[index].sample_uid for index in members):
            digest.update(sample_uid.encode("ascii"))
            digest.update(b"\n")
        cluster_uid = f"rev_{digest.hexdigest()}"
        for index in members:
            cluster_uids[index] = cluster_uid

    statuses: dict[int, str] = {}
    for index in range(len(candidates)):
        if decisions[index] != "keep":
            statuses[index] = "none"
            cluster_uids[index] = None
            continue
        types = review_types.get(index, set())
        if types == {"lexical", "semantic"}:
            statuses[index] = "lexical_and_semantic"
        elif types == {"lexical"}:
            statuses[index] = "lexical"
        elif types == {"semantic"}:
            statuses[index] = "semantic"
        else:
            statuses[index] = "none"
    return statuses, cluster_uids, {
        "review_edges_between_kept_representatives": review_edges,
        "review_clusters": len(review_components),
        "review_cluster_members": sum(len(members) for members in review_components),
        "max_review_cluster_size": max(
            (len(members) for members in review_components),
            default=1,
        ),
    }


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
    elif isinstance(payload, str) and (
        payload.startswith("/Users/")
        or payload.startswith("/home/")
        or re.match(r"^[A-Za-z]:\\", payload)
    ):
        violations.append(location)
    return violations


def build_dataset(args: argparse.Namespace) -> dict[str, object]:
    for path in (
        args.input_db,
        args.cleaning_manifest,
        args.model_dir,
        args.protocol,
    ):
        if not path.exists():
            raise FileNotFoundError(path)
    for path in (
        args.output_db,
        args.embeddings,
        args.index,
        args.report,
        args.manifest,
    ):
        if path.exists() and not args.replace:
            raise FileExistsError(f"refusing to overwrite without --replace: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    if args.expected_candidates <= 0:
        raise ValueError("expected candidate count must be positive")
    if args.model_dir.name != MODEL_REVISION:
        raise ValueError(
            f"model directory must be the frozen revision {MODEL_REVISION}"
        )

    cleaning_manifest = json.loads(args.cleaning_manifest.read_text(encoding="utf-8"))
    input_db_sha = sha256_file(args.input_db)
    expected_input_sha = cleaning_manifest["private_artifact"]["sha256"]
    if input_db_sha != expected_input_sha:
        raise ValueError("cleaning database hash does not match cleaning-v2 manifest")
    model_sha, model_file_hashes = sha256_model(args.model_dir)
    reuse_provenance = validate_reuse_inputs(args, input_db_sha, model_sha)
    protocol_sha = sha256_file(args.protocol)
    script_sha = sha256_file(Path(__file__).resolve())
    embedding_worker = Path(__file__).with_name("embed_iac2_posts_v2.py")
    if not embedding_worker.is_file():
        raise FileNotFoundError(embedding_worker)
    embedding_worker_sha = sha256_file(embedding_worker)

    temporary_db = args.output_db.with_name(f".{args.output_db.name}.tmp")
    temporary_embeddings = args.embeddings.with_name(f".{args.embeddings.name}.tmp")
    temporary_index = args.index.with_name(f".{args.index.name}.tmp")
    temporary_token_counts = args.embeddings.with_name(
        f".{args.embeddings.name}.token-counts.tmp"
    )
    temporary_embedding_stats = args.embeddings.with_name(
        f".{args.embeddings.name}.stats.tmp"
    )
    temporary_report = args.report.with_name(f".{args.report.name}.tmp")
    temporary_manifest = args.manifest.with_name(f".{args.manifest.name}.tmp")
    temporary_paths = (
        temporary_db,
        temporary_embeddings,
        temporary_index,
        temporary_token_counts,
        temporary_embedding_stats,
        temporary_report,
        temporary_manifest,
    )
    for path in temporary_paths:
        if path.exists():
            if not args.replace:
                raise FileExistsError(f"stale temporary output exists: {path}")
            path.unlink()

    started = time.monotonic()
    input_connection = open_readonly(args.input_db)
    output_connection: sqlite3.Connection | None = None
    try:
        if reuse_provenance is None:
            embedding_stats = run_embedding_worker(
                embedding_worker,
                args.input_db,
                args.model_dir,
                temporary_embeddings,
                temporary_token_counts,
                temporary_embedding_stats,
                args.batch_size,
                args.threads,
            )
        else:
            assert args.reuse_embeddings_from is not None
            shutil.copyfile(args.reuse_embeddings_from, temporary_embeddings)
            token_stats = run_token_count_worker(
                embedding_worker,
                args.input_db,
                args.model_dir,
                temporary_token_counts,
                temporary_embedding_stats,
                args.batch_size,
                args.threads,
            )
            embedding_stats = {
                "rows": token_stats["rows"],
                "dimension": EMBEDDING_DIM,
                "dtype": "float32",
                "possible_truncation_rows": token_stats[
                    "possible_truncation_rows"
                ],
                "elapsed_seconds": token_stats["elapsed_seconds"],
                "rows_per_second": token_stats["rows_per_second"],
                "preflight_limit": None,
                "mode": "reused_embeddings_with_corrected_token_counts",
                "python": token_stats["python"],
                "torch": token_stats["torch"],
                "transformers": token_stats["transformers"],
            }
        worker_runtime = {
            key: embedding_stats.pop(key)
            for key in ("python", "torch", "transformers")
        }
        post_uids, dedup_texts, word_counts = load_posts(input_connection)
        if int(embedding_stats["rows"]) != len(post_uids):
            raise ValueError("embedding worker row count does not match used posts")
        post_row = {post_uid: index for index, post_uid in enumerate(post_uids)}
        candidates = load_candidates(input_connection, post_row, word_counts)
        if len(candidates) != args.expected_candidates:
            raise ValueError(f"unexpected eligible candidate count: {len(candidates)}")
        embeddings = np.memmap(
            temporary_embeddings,
            dtype=np.float32,
            mode="r+",
            shape=(len(post_uids), EMBEDDING_DIM),
        )
        token_counts = np.memmap(
            temporary_token_counts,
            dtype=np.uint16,
            mode="r",
            shape=(len(post_uids),),
        )

        exact_representative, exact_groups = choose_exact_representatives(candidates)
        representative_indices = sorted(
            set(exact_representative.values()),
            key=lambda index: candidates[index].sample_uid,
        )

        output_connection = initialize_output_database(temporary_db)
        output_connection.executemany(
            "INSERT INTO metadata VALUES (?, ?)",
            (
                ("schema_version", SCHEMA_VERSION),
                ("pipeline_id", PIPELINE_ID),
                ("input_db_sha256", input_db_sha),
                ("model_sha256", model_sha),
                ("protocol_sha256", protocol_sha),
                ("script_sha256", script_sha),
                ("embedding_worker_sha256", embedding_worker_sha),
            ),
        )
        output_connection.executemany(
            "INSERT INTO post_embedding_rows VALUES (?, ?, ?, ?)",
            (
                (
                    post_uid,
                    index,
                    int(token_counts[index]),
                    int(token_counts[index] >= MAX_TOKENS),
                )
                for index, post_uid in enumerate(post_uids)
            ),
        )
        output_connection.commit()

        if reuse_provenance is None:
            index, index_stats = build_hnsw(
                candidates,
                representative_indices,
                embeddings,
                temporary_index,
                args.threads,
            )
        else:
            assert args.reuse_index_from is not None
            reuse_started = time.monotonic()
            shutil.copyfile(args.reuse_index_from, temporary_index)
            index = load_faiss().read_index(str(temporary_index))
            if index.d != PAIR_DIM or index.ntotal != len(representative_indices):
                raise ValueError("reuse HNSW graph does not match V2 representatives")
            index.hnsw.efSearch = HNSW_EF_SEARCH
            load_faiss().write_index(index, str(temporary_index))
            index_stats = {
                "rows": len(representative_indices),
                "dimension": PAIR_DIM,
                "M": HNSW_M,
                "ef_construction": HNSW_EF_CONSTRUCTION,
                "ef_search": HNSW_EF_SEARCH,
                "elapsed_seconds": round(time.monotonic() - reuse_started, 3),
                "reused_graph": True,
            }
        recall_stats = recall_audit(
            index,
            candidates,
            representative_indices,
            embeddings,
        )
        format_edges, search_stats = search_and_classify(
            output_connection,
            index,
            candidates,
            representative_indices,
            embeddings,
            dedup_texts,
            token_counts,
        )
        final_representative, decisions = assign_direct_representatives(
            candidates,
            exact_representative,
            exact_groups,
            format_edges,
        )
        insert_edges(
            output_connection,
            direct_decision_edges(
                candidates,
                final_representative,
                decisions,
                embeddings,
                dedup_texts,
                token_counts,
            ),
        )
        output_connection.commit()

        statuses, review_cluster_uids, review_stats = review_assignments(
            output_connection,
            final_representative,
            decisions,
            candidates,
        )
        output_connection.executemany(
            """
            INSERT INTO candidate_decisions
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    candidate.index,
                    candidate.sample_uid,
                    candidates[final_representative[candidate.index]].sample_uid,
                    decisions[candidate.index],
                    int(decisions[candidate.index] == "keep"),
                    candidate.severe_flag_count,
                    candidate.total_flag_count,
                    candidate.combined_word_count_capped,
                    statuses[candidate.index],
                    review_cluster_uids[candidate.index],
                )
                for candidate in candidates
            ),
        )
        output_connection.executemany(
            "INSERT INTO retrieval_audit VALUES (?, ?)",
            (
                ("mean_recall_at_64", recall_stats["mean_recall_at_k"]),
                ("min_recall_at_64", recall_stats["min_recall_at_k"]),
                (
                    "saturated_queries_at_max_k",
                    search_stats["saturated_queries_at_max_k"],
                ),
            ),
        )
        output_connection.execute(
            "CREATE INDEX candidate_decision_idx ON candidate_decisions(auto_decision)"
        )
        output_connection.execute(
            "CREATE INDEX candidate_review_idx ON candidate_decisions(review_status)"
        )
        output_connection.execute(
            "CREATE INDEX edge_type_idx ON duplicate_edges(edge_type)"
        )
        output_connection.commit()
        integrity = output_connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"output SQLite integrity check failed: {integrity}")
        output_connection.close()
        output_connection = None
        input_connection.close()

        embeddings.flush()
        del embeddings
        del token_counts
        del index
        gc.collect()
        temporary_token_counts.unlink()
        temporary_embedding_stats.unlink()
        os.chmod(temporary_db, 0o600)
        os.chmod(temporary_embeddings, 0o600)
        os.chmod(temporary_index, 0o600)

        output_db_sha = sha256_file(temporary_db)
        embeddings_sha = sha256_file(temporary_embeddings)
        index_sha = sha256_file(temporary_index)
        decision_counts = Counter(decisions.values())
        exact_cluster_sizes = [len(members) for members in exact_groups.values() if len(members) > 1]
        passed = (
            recall_stats["mean_recall_at_k"] >= RECALL_REQUIRED
            and search_stats["saturated_queries_at_max_k"] == 0
        )
        report: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "pipeline_id": PIPELINE_ID,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": (
                "completed_pending_independent_verification"
                if passed
                else "failed_retrieval_quality_gate"
            ),
            "scope": {
                "dataset": "Internet Argument Corpus 2.0",
                "subset": "4forums",
                "unit": "eligible parent-target pair",
                "labels_assigned": False,
                "splits_assigned": False,
                "external_services_used": False,
                "semantic_only_auto_drop": False,
                "reused_failed_run_decisions_or_edges": False,
            },
            "input": {
                "database_filename": args.input_db.name,
                "database_sha256": input_db_sha,
                "eligible_candidates": len(candidates),
                "used_posts": len(post_uids),
            },
            "implementation": {
                "script_sha256": script_sha,
                "embedding_worker_sha256": embedding_worker_sha,
                "protocol_sha256": protocol_sha,
                "python": worker_runtime["python"],
                "torch": worker_runtime["torch"],
                "transformers": worker_runtime["transformers"],
                "faiss": load_faiss().__version__,
                "process_isolation": "PyTorch embedding worker then FAISS parent",
                "threads": args.threads,
                "batch_size": args.batch_size,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            "model": {
                "model_id": MODEL_ID,
                "revision": MODEL_REVISION,
                "selected_files_sha256": model_sha,
                "selected_file_hashes": model_file_hashes,
                "pooling": "attention-mask mean pooling",
                "normalized": True,
                "max_tokens": MAX_TOKENS,
            },
            "embedding": embedding_stats,
            "reuse_provenance": reuse_provenance,
            "retrieval": {
                **index_stats,
                "initial_k": INITIAL_K,
                "max_k": MAX_K,
                "retrieval_floor": RETRIEVAL_FLOOR,
                **recall_stats,
                **search_stats,
            },
            "thresholds": {
                "lexical_char_5gram_jaccard_gte": LEXICAL_JACCARD,
                "lexical_length_ratio_gte": LEXICAL_LENGTH_RATIO,
                "semantic_pair_cosine_gte": SEMANTIC_PAIR,
                "semantic_component_cosine_gte": SEMANTIC_COMPONENT,
                "semantic_strong_pair_cosine_gte": SEMANTIC_STRONG_PAIR,
                "semantic_strong_component_cosine_gte": SEMANTIC_STRONG_COMPONENT,
            },
            "exact_duplicates": {
                "clusters": len(exact_cluster_sizes),
                "members": sum(exact_cluster_sizes),
                "max_cluster_size": max(exact_cluster_sizes, default=1),
            },
            "decisions": {
                **dict(sorted(decision_counts.items())),
                "eligible_after_auto_dedup": decision_counts["keep"],
                "auto_dropped": len(candidates) - decision_counts["keep"],
            },
            "reviews": review_stats,
            "privacy": {
                "public_text": False,
                "public_source_or_hmac_ids": False,
                "public_embeddings_or_index": False,
                "private_artifacts_git_tracking": "forbidden",
            },
            "private_artifacts": {
                "database": {
                    "filename": args.output_db.name,
                    "size_bytes": temporary_db.stat().st_size,
                    "sha256": output_db_sha,
                },
                "embeddings": {
                    "filename": args.embeddings.name,
                    "size_bytes": temporary_embeddings.stat().st_size,
                    "sha256": embeddings_sha,
                    "shape": [len(post_uids), EMBEDDING_DIM],
                    "dtype": "float32",
                },
                "index": {
                    "filename": args.index.name,
                    "size_bytes": temporary_index.stat().st_size,
                    "sha256": index_sha,
                },
            },
        }
        violations = public_payload_violations(report)
        if violations:
            raise ValueError(f"public report privacy violations: {violations}")
        atomic_write_json(temporary_report, report)

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "pipeline_id": PIPELINE_ID,
            "generated_at": report["generated_at"],
            "artifact_status": (
                "generated_pending_independent_verification"
                if passed
                else "failed_retrieval_quality_gate"
            ),
            "input": {
                "manifest": args.cleaning_manifest.name,
                "database_filename": args.input_db.name,
                "database_sha256": input_db_sha,
            },
            "protocol": {
                "filename": args.protocol.name,
                "sha256": protocol_sha,
            },
            "aggregate_report": {
                "filename": args.report.name,
                "sha256": sha256_file(temporary_report),
            },
            "private_artifacts": report["private_artifacts"],
            "reuse_provenance": reuse_provenance,
            "contains_public_forum_text": False,
            "contains_public_source_or_sample_ids": False,
            "contains_public_embeddings": False,
        }
        violations = public_payload_violations(manifest)
        if violations:
            raise ValueError(f"public manifest privacy violations: {violations}")
        atomic_write_json(temporary_manifest, manifest)

        for temporary, final in (
            (temporary_db, args.output_db),
            (temporary_embeddings, args.embeddings),
            (temporary_index, args.index),
            (temporary_report, args.report),
            (temporary_manifest, args.manifest),
        ):
            os.replace(temporary, final)
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "input_candidates": len(candidates),
                    "kept": decision_counts["keep"],
                    "auto_dropped": len(candidates) - decision_counts["keep"],
                    "review_clusters": review_stats["review_clusters"],
                },
                ensure_ascii=True,
            ),
            flush=True,
        )
        return report
    except Exception:
        input_connection.close()
        if output_connection is not None:
            output_connection.close()
        for path in temporary_paths:
            if path.exists():
                path.unlink()
        raise


def main() -> None:
    report = build_dataset(parse_args())
    if report["status"].startswith("failed"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
