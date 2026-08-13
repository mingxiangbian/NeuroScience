#!/usr/bin/env python3
"""Stream private IAC posts into corrected token counts and MiniLM embeddings."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer


EMBEDDING_DIM = 384
MAX_TOKENS = 256
MODEL_REVISION = "c9745ed1d9f207416be6d2e6f8de32d1f16199bf"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-db", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path)
    parser.add_argument("--token-counts", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--token-counts-only", action="store_true")
    return parser.parse_args()


def mean_pool(hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    mask = attention_mask.unsqueeze(-1).to(hidden_state.dtype)
    pooled = (hidden_state * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
    return torch.nn.functional.normalize(pooled, p=2, dim=1)


def capped_token_lengths(attention_mask: torch.Tensor) -> torch.Tensor:
    """Count non-padding tokens after truncation."""
    if attention_mask.ndim != 2:
        raise ValueError("attention mask must have shape [batch, tokens]")
    return attention_mask.sum(dim=1, dtype=torch.int64)


def stream_query(limit: int | None = None) -> str:
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
        SELECT p.model_body
        FROM used
        JOIN cleaned_posts AS p ON p.post_uid = used.post_uid
        ORDER BY p.post_uid
    """
    if limit is not None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        query += f" LIMIT {limit}"
    return query


def encode(args: argparse.Namespace) -> dict[str, object]:
    if args.model_dir.name != MODEL_REVISION:
        raise ValueError("model directory is not the frozen revision")
    for path in (args.input_db, args.model_dir):
        if not path.exists():
            raise FileNotFoundError(path)
    if not args.token_counts_only and args.embeddings is None:
        raise ValueError("embeddings output is required outside token-counts-only mode")
    output_paths = [args.token_counts, args.stats]
    if args.embeddings is not None and not args.token_counts_only:
        output_paths.append(args.embeddings)
    for path in output_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.unlink()

    connection = sqlite3.connect(f"file:{args.input_db}?mode=ro", uri=True)
    try:
        post_count = int(
            connection.execute(
                f"SELECT COUNT(*) FROM ({stream_query(args.limit)})"
            ).fetchone()[0]
        )
        embeddings = None
        if not args.token_counts_only:
            assert args.embeddings is not None
            embeddings = np.memmap(
                args.embeddings,
                dtype=np.float32,
                mode="w+",
                shape=(post_count, EMBEDDING_DIM),
            )
        token_counts = np.memmap(
            args.token_counts,
            dtype=np.uint16,
            mode="w+",
            shape=(post_count,),
        )
        torch.set_num_threads(args.threads)
        tokenizer = AutoTokenizer.from_pretrained(args.model_dir, local_files_only=True)
        model = None
        if not args.token_counts_only:
            model = AutoModel.from_pretrained(args.model_dir, local_files_only=True)
            if int(model.config.hidden_size) != EMBEDDING_DIM:
                raise ValueError(f"unexpected embedding dimension: {model.config.hidden_size}")
            model.eval()

        cursor = connection.execute(stream_query(args.limit))
        written = 0
        started = time.monotonic()
        with torch.inference_mode():
            while True:
                rows = cursor.fetchmany(args.batch_size)
                if not rows:
                    break
                texts = [row[0] or "" for row in rows]
                encoded = tokenizer(
                    texts,
                    padding=True,
                    truncation=True,
                    max_length=MAX_TOKENS,
                    return_tensors="pt",
                )
                lengths = capped_token_lengths(encoded["attention_mask"])
                stop = written + len(rows)
                if model is not None:
                    output = model(**encoded).last_hidden_state
                    pooled = mean_pool(output, encoded["attention_mask"])
                    array = pooled.detach().cpu().numpy().astype(np.float32, copy=False)
                    if not np.isfinite(array).all():
                        raise FloatingPointError("non-finite post embedding")
                    assert embeddings is not None
                    embeddings[written:stop] = array
                token_counts[written:stop] = np.asarray(lengths, dtype=np.uint16)
                written = stop
                if written // 10000 != (written - len(rows)) // 10000 or written == post_count:
                    elapsed = max(time.monotonic() - started, 1e-9)
                    print(
                        f"{'tokenized' if model is None else 'embedded'} posts: "
                        f"{written:,}/{post_count:,} "
                        f"({written / elapsed:.2f} rows/s)",
                        flush=True,
                    )
        if written != post_count:
            raise AssertionError(f"post stream count changed: {written} != {post_count}")
        if embeddings is not None:
            embeddings.flush()
        token_counts.flush()
        elapsed = time.monotonic() - started
        payload: dict[str, object] = {
            "rows": post_count,
            "dimension": EMBEDDING_DIM,
            "dtype": "float32",
            "possible_truncation_rows": int(
                np.count_nonzero(np.asarray(token_counts) >= MAX_TOKENS)
            ),
            "elapsed_seconds": round(elapsed, 3),
            "rows_per_second": round(post_count / max(elapsed, 1e-9), 3),
            "python": os.sys.version.split()[0],
            "torch": torch.__version__,
            "transformers": __import__("transformers").__version__,
            "preflight_limit": args.limit,
            "mode": "token_counts_only" if args.token_counts_only else "embeddings_and_token_counts",
        }
        args.stats.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        for path in output_paths:
            os.chmod(path, 0o600)
        return payload
    finally:
        connection.close()


def main() -> None:
    payload = encode(parse_args())
    print(
        json.dumps(
            {"status": "completed", "rows": payload["rows"]},
            ensure_ascii=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
