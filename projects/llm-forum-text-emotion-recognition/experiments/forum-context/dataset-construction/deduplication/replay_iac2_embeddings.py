#!/usr/bin/env python3
"""Replay a deterministic private embedding sample without loading FAISS."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import os
import sqlite3
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
    parser.add_argument("--dedup-db", type=Path, required=True)
    parser.add_argument("--embeddings", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    return parser.parse_args()


def mean_pool(hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    mask = attention_mask.unsqueeze(-1).to(hidden_state.dtype)
    pooled = (hidden_state * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
    return torch.nn.functional.normalize(pooled, p=2, dim=1)


def replay(args: argparse.Namespace) -> dict[str, object]:
    if args.model_dir.name != MODEL_REVISION:
        raise ValueError("model directory is not the frozen revision")
    input_connection = sqlite3.connect(f"file:{args.input_db}?mode=ro", uri=True)
    dedup_connection = sqlite3.connect(f"file:{args.dedup_db}?mode=ro", uri=True)
    try:
        post_rows = list(
            dedup_connection.execute(
                """
                SELECT post_uid, embedding_row, token_count_capped
                FROM post_embedding_rows
                ORDER BY embedding_row
                """
            )
        )
        sample_rows = heapq.nsmallest(
            min(32, len(post_rows)),
            range(len(post_rows)),
            key=lambda index: hashlib.sha256(str(post_rows[index][0]).encode("ascii")).digest(),
        )
        texts: list[str] = []
        stored_token_counts: list[int] = []
        for row_index in sample_rows:
            post_uid, _, token_count = post_rows[row_index]
            row = input_connection.execute(
                "SELECT model_body FROM cleaned_posts WHERE post_uid = ?",
                (post_uid,),
            ).fetchone()
            if row is None:
                raise KeyError("sampled post is absent from cleaning database")
            texts.append(row[0] or "")
            stored_token_counts.append(int(token_count))

        embeddings = np.memmap(
            args.embeddings,
            dtype=np.float32,
            mode="r",
            shape=(len(post_rows), EMBEDDING_DIM),
        )
        torch.set_num_threads(args.threads)
        tokenizer = AutoTokenizer.from_pretrained(args.model_dir, local_files_only=True)
        model = AutoModel.from_pretrained(args.model_dir, local_files_only=True)
        model.eval()
        max_abs_error = 0.0
        token_count_errors = 0
        with torch.inference_mode():
            for start in range(0, len(texts), args.batch_size):
                stop = min(start + args.batch_size, len(texts))
                encoded = tokenizer(
                    texts[start:stop],
                    padding=True,
                    truncation=True,
                    max_length=MAX_TOKENS,
                    return_length=True,
                    return_tensors="pt",
                )
                lengths = np.asarray(encoded.pop("length"), dtype=np.uint16)
                recomputed = mean_pool(
                    model(**encoded).last_hidden_state,
                    encoded["attention_mask"],
                ).cpu().numpy().astype(np.float32)
                selected = sample_rows[start:stop]
                stored = np.asarray(embeddings[selected], dtype=np.float32)
                max_abs_error = max(
                    max_abs_error,
                    float(np.max(np.abs(recomputed - stored))),
                )
                expected_lengths = np.asarray(
                    stored_token_counts[start:stop],
                    dtype=np.uint16,
                )
                token_count_errors += int(np.count_nonzero(lengths != expected_lengths))
        payload: dict[str, object] = {
            "sampled_rows": len(sample_rows),
            "max_abs_error": max_abs_error,
            "token_count_errors": token_count_errors,
            "passed": max_abs_error <= 2e-5 and token_count_errors == 0,
            "torch": torch.__version__,
            "transformers": __import__("transformers").__version__,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_name(f".{args.output.name}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.chmod(temporary, 0o600)
        os.replace(temporary, args.output)
        return payload
    finally:
        input_connection.close()
        dedup_connection.close()


def main() -> None:
    payload = replay(parse_args())
    print(
        json.dumps(
            {"status": "passed" if payload["passed"] else "failed"},
            ensure_ascii=True,
        ),
        flush=True,
    )
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
