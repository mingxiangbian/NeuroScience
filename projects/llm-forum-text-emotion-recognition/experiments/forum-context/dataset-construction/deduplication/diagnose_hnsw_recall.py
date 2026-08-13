#!/usr/bin/env python3
"""Evaluate HNSW search-time recall without reading or emitting forum text."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import faiss
import numpy as np


EMBEDDING_DIM = 384
PAIR_DIM = 768
AUDIT_SIZE = 128
K = 64


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-db", type=Path, required=True)
    parser.add_argument("--dedup-db", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--ef-search", type=int, nargs="+", default=[256, 384, 512, 768])
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def pair_vectors(
    parent_rows: np.ndarray,
    target_rows: np.ndarray,
    embeddings: np.ndarray,
    indices: Sequence[int],
) -> np.ndarray:
    selected = np.asarray(indices, dtype=np.int64)
    parent = np.asarray(embeddings[parent_rows[selected]], dtype=np.float32)
    target = np.asarray(embeddings[target_rows[selected]], dtype=np.float32)
    return np.concatenate((parent, target), axis=1) / math.sqrt(2.0)


def diagnose(args: argparse.Namespace) -> dict[str, object]:
    for path in (args.input_db, args.dedup_db, args.embeddings, args.index):
        if not path.is_file():
            raise FileNotFoundError(path)
    if args.output.exists() and not args.replace:
        raise FileExistsError(f"refusing to overwrite without --replace: {args.output}")

    source = sqlite3.connect(f"file:{args.input_db}?mode=ro", uri=True)
    dedup = sqlite3.connect(f"file:{args.dedup_db}?mode=ro", uri=True)
    try:
        post_rows = list(
            dedup.execute(
                "SELECT post_uid, embedding_row FROM post_embedding_rows ORDER BY embedding_row"
            )
        )
        post_to_row = {str(post_uid): int(row) for post_uid, row in post_rows}
        candidates = list(
            source.execute(
                """
                SELECT sample_uid, parent_post_uid, target_post_uid, pair_sha256
                FROM candidate_pairs
                WHERE eligible = 1
                ORDER BY sample_uid
                """
            )
        )
        qualities = list(
            dedup.execute(
                """
                SELECT severe_flag_count, total_flag_count, combined_word_count_capped
                FROM candidate_decisions
                ORDER BY candidate_index
                """
            )
        )
        if len(candidates) != len(qualities):
            raise AssertionError("candidate alignment changed")
        parent_rows = np.fromiter(
            (post_to_row[str(row[1])] for row in candidates),
            dtype=np.int32,
            count=len(candidates),
        )
        target_rows = np.fromiter(
            (post_to_row[str(row[2])] for row in candidates),
            dtype=np.int32,
            count=len(candidates),
        )
        representatives: dict[str, int] = {}
        for index, row in enumerate(candidates):
            pair_hash = str(row[3])
            current = representatives.get(pair_hash)
            rank = (
                int(qualities[index][0]),
                int(qualities[index][1]),
                -int(qualities[index][2]),
                str(row[0]),
            )
            if current is None:
                representatives[pair_hash] = index
                continue
            current_rank = (
                int(qualities[current][0]),
                int(qualities[current][1]),
                -int(qualities[current][2]),
                str(candidates[current][0]),
            )
            if rank < current_rank:
                representatives[pair_hash] = index
        representative_indices = sorted(
            representatives.values(),
            key=lambda index: str(candidates[index][0]),
        )
        audit_indices = heapq.nsmallest(
            min(AUDIT_SIZE, len(representative_indices)),
            representative_indices,
            key=lambda index: hashlib.sha256(
                str(candidates[index][0]).encode("ascii")
            ).digest(),
        )
        embeddings = np.memmap(
            args.embeddings,
            dtype=np.float32,
            mode="r",
            shape=(len(post_rows), EMBEDDING_DIM),
        )
        queries = pair_vectors(parent_rows, target_rows, embeddings, audit_indices)
        faiss.omp_set_num_threads(args.threads)
        flat = faiss.IndexFlatIP(PAIR_DIM)
        for start in range(0, len(representative_indices), 10000):
            stop = min(start + 10000, len(representative_indices))
            flat.add(
                pair_vectors(
                    parent_rows,
                    target_rows,
                    embeddings,
                    representative_indices[start:stop],
                )
            )
        _, exact_neighbors = flat.search(queries, K)
        index = faiss.read_index(str(args.index))
        results: list[dict[str, object]] = []
        for ef_search in args.ef_search:
            index.hnsw.efSearch = int(ef_search)
            _, approximate_neighbors = index.search(queries, K)
            recalls = []
            for exact, approximate in zip(exact_neighbors, approximate_neighbors):
                exact_set = {int(value) for value in exact}
                approximate_set = {int(value) for value in approximate}
                recalls.append(len(exact_set & approximate_set) / len(exact_set))
            results.append(
                {
                    "ef_search": int(ef_search),
                    "mean_recall_at_64": float(np.mean(recalls)),
                    "min_recall_at_64": float(np.min(recalls)),
                    "passes_mean_recall_0_98": float(np.mean(recalls)) >= 0.98,
                }
            )
        payload: dict[str, object] = {
            "schema_version": "1",
            "pipeline_id": "DATA-FCTX-DEDUP-V1-RECALL-DIAGNOSTIC",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
            "candidate_rows": len(candidates),
            "exact_representative_rows": len(representative_indices),
            "audit_queries": len(audit_indices),
            "k": K,
            "results": results,
            "contains_public_forum_text": False,
            "contains_public_source_or_sample_ids": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_name(f".{args.output.name}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, args.output)
        return payload
    finally:
        source.close()
        dedup.close()


def main() -> None:
    payload = diagnose(parse_args())
    print(json.dumps({"status": payload["status"], "results": payload["results"]}))


if __name__ == "__main__":
    main()
