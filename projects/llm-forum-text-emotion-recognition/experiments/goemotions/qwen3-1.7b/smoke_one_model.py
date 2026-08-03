#!/usr/bin/env python3
"""Run one synthetic MLX generation without reading project data."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

from mlx_lm import generate, load
from mlx_lm.sample_utils import make_sampler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--condition",
        choices=("base", "post-trained"),
        required=True,
    )
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_dir = args.model_dir.resolve()
    if not model_dir.is_dir():
        raise FileNotFoundError(f"Missing local MLX model: {model_dir}")
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite: {args.output}")

    started_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    model, tokenizer = load(str(model_dir))

    if args.condition == "post-trained":
        messages = [
            {
                "role": "user",
                "content": "Reply with one English word meaning happy.",
            }
        ]
        prompt = tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            enable_thinking=False,
            tokenize=False,
        )
        input_mode = "official chat template with thinking disabled"
    else:
        prompt = "Complete this sentence in English: The weather today is"
        input_mode = "plain completion"

    prompt_tokens = tokenizer.encode(prompt)
    generated = generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=8,
        sampler=make_sampler(temp=0.0),
        verbose=False,
    )
    elapsed = time.perf_counter() - started
    generated_tokens = tokenizer.encode(generated)
    if not generated.strip():
        raise ValueError(f"{args.condition} generated an empty response")

    report = {
        "accessed_splits": [],
        "condition": args.condition,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "generated_character_count": len(generated),
        "generated_nonempty": True,
        "generated_token_count": len(generated_tokens),
        "generation_text_stored": False,
        "input_mode": input_mode,
        "max_tokens": 8,
        "model_dir": str(model_dir),
        "packages": {
            "mlx": importlib.metadata.version("mlx"),
            "mlx-lm": importlib.metadata.version("mlx-lm"),
            "transformers": importlib.metadata.version("transformers"),
        },
        "platform": platform.platform(),
        "prompt_token_count": len(prompt_tokens),
        "python": platform.python_version(),
        "sampler": "greedy",
        "started_at_utc": started_at.isoformat(),
        "test_split_accessed": False,
        "total_seconds": elapsed,
        "validation_split_accessed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "condition": args.condition,
                "generated_nonempty": True,
                "generated_token_count": len(generated_tokens),
                "total_seconds": elapsed,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

