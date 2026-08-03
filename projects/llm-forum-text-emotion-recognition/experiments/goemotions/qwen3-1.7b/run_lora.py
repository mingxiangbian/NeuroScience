#!/usr/bin/env python3
"""Prepare, train, and evaluate the registered EXP-029 LoRA experiment."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import traceback
from typing import Any, Iterable, Iterator

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["PYTHONNOUSERSITE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

EXPERIMENT_ID = "EXP-029"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
CONFIG_PATH = SCRIPT_DIR / "configs" / "exp-029-instruct-lora.json"
VERIFIER_PATH = SCRIPT_DIR / "verify_lora.py"
METRICS_PATH = SCRIPT_DIR / "llm_full_dev_metrics.py"
CONSTRAINT_PATH = SCRIPT_DIR / "label_json_constraint.py"
DATA_ROOT = PROJECT_ROOT / "data" / "goemotions" / "official"
TRAIN_PATH = DATA_ROOT / "train.tsv"
DEV_PATH = DATA_ROOT / "dev.tsv"
LABELS_PATH = DATA_ROOT / "emotions.txt"
TEST_PATH = DATA_ROOT / "test.tsv"
MODEL_ROOT = PROJECT_ROOT / "models" / "qwen3-1.7b"
MODEL_DIR = MODEL_ROOT / "mlx-bf16"
MODEL_MANIFEST_PATH = MODEL_ROOT / "manifest.json"
PYTHON = Path("/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python")
MLX_LORA = Path("/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/mlx_lm.lora")
CONDITIONS = ("zero-shot", "few-shot-synthetic-3")
TRAIN_LOG_PATTERN = re.compile(
    r"Iter (?P<iteration>\d+): Train loss (?P<loss>[^,]+), "
    r"Learning Rate (?P<learning_rate>[^,]+), It/sec (?P<iterations_per_second>[^,]+), "
    r"Tokens/sec (?P<tokens_per_second>[^,]+), Trained Tokens (?P<trained_tokens>\d+), "
    r"Peak mem (?P<peak_memory_gb>[^ ]+) GB"
)
TRAINABLE_PATTERN = re.compile(
    r"Trainable parameters: (?P<percent>[0-9.]+)% "
    r"\((?P<trainable>[0-9.]+)M/(?P<total>[0-9.]+)M\)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("prepare")
    subparsers.add_parser("preflight")
    subparsers.add_parser("smoke")
    train = subparsers.add_parser("train")
    train.add_argument("--seed", type=int, required=True)
    dev = subparsers.add_parser("dev")
    dev.add_argument("--seed", type=int, required=True)
    dev.add_argument("--resume", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def project_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def resolve_project_path(value: str) -> Path:
    return PROJECT_ROOT / value


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": project_path(path),
        "sha256": sha256_file(path),
    }


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if (
        config["experiment_id"] != EXPERIMENT_ID
        or config["tier"] != "Major"
        or config["status"] != "Registered"
    ):
        raise ValueError("EXP-029 must remain a registered Major configuration")
    if any(value == "PENDING" for value in config["implementation"].values()):
        raise ValueError("Implementation hashes must be frozen before execution")
    return config


def verify_hash(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"Frozen hash mismatch for {path}: {actual} != {expected}")


def verify_static_inputs(
    config: dict[str, Any],
    *,
    include_train: bool = False,
    include_dev: bool = False,
) -> tuple[str, ...]:
    if TEST_PATH.exists():
        raise ValueError(f"Test split must remain absent: {TEST_PATH}")
    if not PYTHON.is_file() or not MLX_LORA.is_file():
        raise FileNotFoundError("The frozen emotion-llm-mlx environment is unavailable")
    checks = [
        (LABELS_PATH, config["data"]["labels_sha256"]),
        (MODEL_MANIFEST_PATH, config["model"]["manifest_sha256"]),
        (resolve_project_path(config["prompt"]["path"]), config["prompt"]["sha256"]),
        (
            resolve_project_path(config["decoding"]["constraint_path"]),
            config["decoding"]["constraint_sha256"],
        ),
        (Path(__file__).resolve(), config["implementation"]["runner_sha256"]),
        (METRICS_PATH, config["implementation"]["metrics_sha256"]),
        (VERIFIER_PATH, config["implementation"]["verifier_sha256"]),
    ]
    if include_train:
        checks.append((TRAIN_PATH, config["data"]["train_sha256"]))
    if include_dev:
        checks.append((DEV_PATH, config["data"]["dev_sha256"]))
    for path, expected in checks:
        verify_hash(path, expected)
    for comparison in config["comparison_inputs"].values():
        for key, value in comparison.items():
            if key.endswith("_path"):
                hash_key = key.removesuffix("_path") + "_sha256"
                if hash_key in comparison:
                    verify_hash(resolve_project_path(value), comparison[hash_key])
        for condition in comparison.get("conditions", {}).values():
            verify_hash(
                resolve_project_path(condition["predictions_path"]),
                condition["predictions_sha256"],
            )
        for seed in comparison.get("seed_predictions", []):
            verify_hash(resolve_project_path(seed["path"]), seed["sha256"])

    labels = tuple(LABELS_PATH.read_text(encoding="utf-8").splitlines())
    if len(labels) != config["data"]["labels"] or len(set(labels)) != len(labels):
        raise ValueError("Frozen label ontology changed")
    manifest = json.loads(MODEL_MANIFEST_PATH.read_text(encoding="utf-8"))
    if (
        manifest["repo_id"] != config["model"]["repo_id"]
        or manifest["revision"] != config["model"]["revision"]
        or manifest["conversion"]["dtype"] != "bfloat16"
        or manifest["conversion"]["quantized"] is not False
    ):
        raise ValueError("Model manifest differs from the registered condition")
    if not MODEL_DIR.is_dir() or not any(MODEL_DIR.glob("*.safetensors")):
        raise FileNotFoundError(f"Missing local MLX model: {MODEL_DIR}")
    return labels


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return {"commit": commit, "dirty": bool(status), "dirty_path_count": len(status)}


def hardware_metadata() -> dict[str, Any]:
    memory = subprocess.run(
        ["sysctl", "-n", "hw.memsize"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    chip = subprocess.run(
        ["sysctl", "-n", "machdep.cpu.brand_string"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {
        "architecture": platform.machine(),
        "chip": chip,
        "memory_bytes": int(memory),
        "platform": platform.platform(),
    }


def package_versions() -> dict[str, str]:
    return {
        name: importlib.metadata.version(name)
        for name in ("huggingface-hub", "mlx", "mlx-lm", "numpy", "transformers")
    }


def prompt_messages(
    prompt_spec: dict[str, Any],
    labels: tuple[str, ...],
    text: str,
    target: str | None = None,
) -> list[dict[str, str]]:
    messages = [
        {
            "role": "system",
            "content": prompt_spec["system_template"].format(
                allowed_labels=", ".join(labels)
            ),
        },
        {
            "role": "user",
            "content": prompt_spec["user_template"].format(text=text),
        },
    ]
    if target is not None:
        messages.append({"role": "assistant", "content": target})
    return messages


def full_chat_tokens(tokenizer: Any, messages: list[dict[str, str]]) -> list[int]:
    return tokenizer.apply_chat_template(messages, return_dict=False)


def truncate_text_to_fit(
    tokenizer: Any,
    prompt_spec: dict[str, Any],
    labels: tuple[str, ...],
    text: str,
    target: str,
    max_tokens: int,
) -> tuple[str, int]:
    text_tokens = tokenizer.encode(text, add_special_tokens=False)
    low, high = 0, len(text_tokens)
    best_text = ""
    best_length = 0
    while low <= high:
        midpoint = (low + high) // 2
        candidate = tokenizer.decode(
            text_tokens[:midpoint],
            skip_special_tokens=False,
            clean_up_tokenization_spaces=False,
        )
        length = len(
            full_chat_tokens(
                tokenizer,
                prompt_messages(prompt_spec, labels, candidate, target),
            )
        )
        if length <= max_tokens:
            best_text, best_length = candidate, length
            low = midpoint + 1
        else:
            high = midpoint - 1
    if not best_text or best_length <= 0:
        raise ValueError("Unable to preserve a non-empty input under the sequence limit")
    return best_text, best_length


def quantile_summary(values: list[int]) -> dict[str, float | int]:
    import numpy as np

    array = np.asarray(values, dtype=np.int64)
    return {
        "max": int(np.max(array)),
        "mean": float(np.mean(array)),
        "min": int(np.min(array)),
        "p50": float(np.quantile(array, 0.50)),
        "p95": float(np.quantile(array, 0.95)),
        "p99": float(np.quantile(array, 0.99)),
    }


def prepare_data(config: dict[str, Any]) -> None:
    labels = verify_static_inputs(config, include_train=True)
    from transformers import AutoTokenizer

    private_root = resolve_project_path(config["artifacts"]["private_data_root"])
    preflight_dir = resolve_project_path(config["artifacts"]["public_preflight_dir"])
    report_path = preflight_dir / "exp-029-data-preparation.json"
    if private_root.exists() or report_path.exists():
        raise FileExistsError("EXP-029 prepared data or public report already exists")
    private_root.parent.mkdir(parents=True, exist_ok=True)
    preflight_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
    prompt_spec = json.loads(
        resolve_project_path(config["prompt"]["path"]).read_text(encoding="utf-8")
    )
    max_tokens = int(config["training"]["max_sequence_length"])
    rows: list[dict[str, Any]] = []
    lengths: list[int] = []
    target_lengths: list[int] = []
    truncations: list[dict[str, int]] = []
    gold_label_support = [0] * len(labels)
    target_label_support = [0] * len(labels)
    neutral_cooccurrence_rows: list[int] = []
    seen_ids: set[str] = set()

    temporary = Path(tempfile.mkdtemp(prefix="exp-029-data-", dir=private_root.parent))
    try:
        train_output = temporary / "train.jsonl"
        with TRAIN_PATH.open("r", encoding="utf-8", newline="") as source, train_output.open(
            "w", encoding="utf-8"
        ) as output:
            reader = csv.reader(source, delimiter="\t")
            for row_index, row in enumerate(reader):
                row_number = row_index + 1
                if len(row) != 3:
                    raise ValueError(f"train.tsv row {row_number} has {len(row)} columns")
                text, encoded_labels, comment_id = row
                if not text or not encoded_labels or not comment_id:
                    raise ValueError(f"train.tsv row {row_number} has an empty field")
                if comment_id in seen_ids:
                    raise ValueError("train.tsv repeats a comment ID")
                seen_ids.add(comment_id)
                try:
                    label_ids = sorted(int(value) for value in encoded_labels.split(","))
                except ValueError as error:
                    raise ValueError(f"Invalid labels at train row {row_number}") from error
                if (
                    not label_ids
                    or len(label_ids) != len(set(label_ids))
                    or any(value < 0 or value >= len(labels) for value in label_ids)
                ):
                    raise ValueError(f"Invalid label set at train row {row_number}")
                for label_id in label_ids:
                    gold_label_support[label_id] += 1
                target_label_ids = list(label_ids)
                neutral_id = labels.index("neutral")
                if neutral_id in target_label_ids and len(target_label_ids) > 1:
                    target_label_ids.remove(neutral_id)
                    neutral_cooccurrence_rows.append(row_number)
                for label_id in target_label_ids:
                    target_label_support[label_id] += 1
                target = json.dumps(
                    {"labels": [labels[value] for value in target_label_ids]},
                    separators=(",", ":"),
                )
                messages = prompt_messages(prompt_spec, labels, text, target)
                tokens = full_chat_tokens(tokenizer, messages)
                original_length = len(tokens)
                original_characters = len(text)
                if original_length > max_tokens:
                    text, final_length = truncate_text_to_fit(
                        tokenizer,
                        prompt_spec,
                        labels,
                        text,
                        target,
                        max_tokens,
                    )
                    messages = prompt_messages(prompt_spec, labels, text, target)
                    tokens = full_chat_tokens(tokenizer, messages)
                    if len(tokens) != final_length:
                        raise ValueError("Truncation length changed after reconstruction")
                    truncations.append(
                        {
                            "final_characters": len(text),
                            "final_tokens": len(tokens),
                            "original_characters": original_characters,
                            "original_tokens": original_length,
                            "row_number": row_number,
                        }
                    )
                prefix_tokens = tokenizer.apply_chat_template(
                    messages[:-1],
                    add_generation_prompt=True,
                    return_dict=False,
                )
                target_length = len(tokens) - len(prefix_tokens)
                if len(tokens) > max_tokens or target_length <= 0:
                    raise ValueError(f"Invalid token boundary at train row {row_number}")
                serialized = json.dumps(
                    {"messages": messages}, separators=(",", ":"), ensure_ascii=True
                )
                output.write(serialized + "\n")
                rows.append(
                    {
                        "label_ids": tuple(target_label_ids),
                        "line": serialized,
                        "row_number": row_number,
                    }
                )
                lengths.append(len(tokens))
                target_lengths.append(target_length)

        expected_rows = int(config["data"]["train_rows"])
        if len(rows) != expected_rows or len(seen_ids) != expected_rows:
            raise ValueError(f"Prepared {len(rows)} rows; expected {expected_rows}")
        if gold_label_support != [
            4130,
            2328,
            1567,
            2470,
            2939,
            1087,
            1368,
            2191,
            641,
            1269,
            2022,
            793,
            303,
            853,
            596,
            2662,
            77,
            1452,
            2086,
            164,
            1581,
            111,
            1110,
            153,
            545,
            1326,
            1060,
            14219,
        ]:
            raise ValueError("Prepared label support differs from DATA-GOE-V1")
        expected_neutral_cooccurrences = int(
            config["data"]["target_mapping"]["neutral_cooccurrence_train_rows"]
        )
        if len(neutral_cooccurrence_rows) != expected_neutral_cooccurrences:
            raise ValueError("Neutral co-occurrence count differs from the correction note")

        selected: set[int] = set()
        for label_id in sorted(
            range(len(labels)), key=lambda value: target_label_support[value]
        ):
            candidates = [
                row
                for row in rows
                if row["row_number"] not in selected and label_id in row["label_ids"]
            ]
            chosen = min(
                candidates,
                key=lambda row: sha256_text(
                    f"EXP-029-smoke-v1:{label_id}:{row['row_number']}"
                ),
            )
            selected.add(chosen["row_number"])
        remaining = sorted(
            (row for row in rows if row["row_number"] not in selected),
            key=lambda row: sha256_text(f"EXP-029-smoke-fill-v1:{row['row_number']}"),
        )
        for row in remaining:
            if len(selected) >= int(config["preflight"]["smoke_rows"]):
                break
            selected.add(row["row_number"])
        smoke_rows = sorted(
            (row for row in rows if row["row_number"] in selected),
            key=lambda row: row["row_number"],
        )
        if len(smoke_rows) != int(config["preflight"]["smoke_rows"]):
            raise ValueError("Smoke selection has the wrong row count")
        smoke_labels = {value for row in smoke_rows for value in row["label_ids"]}
        if smoke_labels != set(range(len(labels))):
            raise ValueError("Smoke selection does not cover every label")
        smoke_dir = temporary / "smoke"
        smoke_dir.mkdir()
        smoke_path = smoke_dir / "train.jsonl"
        smoke_path.write_text(
            "".join(row["line"] + "\n" for row in smoke_rows), encoding="utf-8"
        )
        temporary.rename(private_root)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise

    report = {
        "assistant_target": {
            "canonical_label_order": "ascending frozen numeric label ID",
            "format": "compact exact label-name JSON",
            "prompt_masked_from_loss": True,
            "token_lengths": quantile_summary(target_lengths),
        },
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_protocol": config["data"]["dataset_protocol"],
        "experiment_id": EXPERIMENT_ID,
        "input_artifacts": {
            "labels": artifact(LABELS_PATH),
            "prompt": artifact(resolve_project_path(config["prompt"]["path"])),
            "train": artifact(TRAIN_PATH),
        },
        "privacy": {
            "public_raw_comment_ids": False,
            "public_raw_text": False,
            "private_expanded_chat_data_gitignored": True,
        },
        "prepared_train": {
            **artifact(private_root / "train.jsonl"),
            "rows": len(rows),
            "sequence_token_lengths": quantile_summary(lengths),
        },
        "target_mapping": {
            "dev_gold_unchanged": True,
            "gold_label_support": {
                label: gold_label_support[index] for index, label in enumerate(labels)
            },
            "neutral_cooccurrence_row_count": len(neutral_cooccurrence_rows),
            "neutral_cooccurrence_row_numbers": neutral_cooccurrence_rows,
            "rule": config["data"]["target_mapping"]["rule"],
            "target_label_support": {
                label: target_label_support[index] for index, label in enumerate(labels)
            },
        },
        "smoke": {
            **artifact(private_root / "smoke" / "train.jsonl"),
            "covers_all_labels": True,
            "row_numbers": [row["row_number"] for row in smoke_rows],
            "rows": len(smoke_rows),
            "selection": "rarest-label-first deterministic hash selection, then deterministic hash fill",
        },
        "status": "Passed",
        "test_absent": not TEST_PATH.exists(),
        "truncation": {
            "affected_rows": len(truncations),
            "max_sequence_tokens": max_tokens,
            "records": truncations,
            "target_preserved": True,
        },
    }
    write_json(report_path, report)
    print(json.dumps(report, indent=2, sort_keys=True))


def build_inference_prompt(
    tokenizer: Any,
    prompt_spec: dict[str, Any],
    labels: tuple[str, ...],
    text: str,
    condition: str,
) -> str:
    system = prompt_spec["system_template"].format(allowed_labels=", ".join(labels))
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    if condition == "few-shot-synthetic-3":
        for example in prompt_spec["few_shot_examples"]:
            messages.extend(
                [
                    {"role": "user", "content": example["user"]},
                    {"role": "assistant", "content": example["assistant"]},
                ]
            )
    elif condition != "zero-shot":
        raise ValueError(f"Unknown condition: {condition}")
    messages.append(
        {
            "role": "user",
            "content": prompt_spec["user_template"].format(text=text),
        }
    )
    return tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        enable_thinking=False,
        tokenize=False,
    )


def strict_parse(output: str, labels: tuple[str, ...]) -> dict[str, Any]:
    try:
        decoded = json.loads(output.strip())
    except json.JSONDecodeError:
        return {"canonical_output": None, "error": "invalid-json", "labels": []}
    if not isinstance(decoded, dict) or set(decoded) != {"labels"}:
        return {"canonical_output": None, "error": "wrong-object", "labels": []}
    values = decoded["labels"]
    if not isinstance(values, list) or not values:
        return {"canonical_output": None, "error": "labels-not-nonempty-list", "labels": []}
    if not all(isinstance(value, str) for value in values):
        return {"canonical_output": None, "error": "non-string-label", "labels": []}
    if len(values) != len(set(values)):
        return {"canonical_output": None, "error": "duplicate-label", "labels": []}
    if any(value not in labels for value in values):
        return {"canonical_output": None, "error": "unknown-label", "labels": []}
    if "neutral" in values and len(values) > 1:
        return {"canonical_output": None, "error": "neutral-combined", "labels": []}
    return {
        "canonical_output": json.dumps({"labels": values}, separators=(",", ":")),
        "error": None,
        "labels": values,
    }


def zero_step_preflight(config: dict[str, Any]) -> None:
    labels = verify_static_inputs(config)
    data_report_path = (
        resolve_project_path(config["artifacts"]["public_preflight_dir"])
        / "exp-029-data-preparation.json"
    )
    report_path = data_report_path.with_name("exp-029-zero-step.json")
    adapter_root = resolve_project_path(config["artifacts"]["private_adapter_root"])
    adapter_path = adapter_root / "zero-step"
    run_root = resolve_project_path(config["artifacts"]["run_root"])
    if not data_report_path.is_file():
        raise FileNotFoundError("Data preparation must pass before zero-step preflight")
    if report_path.exists() or adapter_path.exists() or run_root.exists():
        raise FileExistsError("Zero-step output or formal EXP-029 output already exists")
    data_report = json.loads(data_report_path.read_text(encoding="utf-8"))
    if data_report.get("status") != "Passed":
        raise ValueError("Data preparation did not pass")
    for key, relative in (
        ("prepared_train", "train.jsonl"),
        ("smoke", "smoke/train.jsonl"),
    ):
        path = resolve_project_path(config["artifacts"]["private_data_root"]) / relative
        verify_hash(path, data_report[key]["sha256"])

    import mlx.core as mx
    from mlx.utils import tree_flatten
    from mlx_lm import load
    from mlx_lm.tuner.utils import linear_to_lora_layers

    mx.reset_peak_memory()
    model, tokenizer = load(str(MODEL_DIR), lazy=False)
    model.eval()
    prompt_spec = json.loads(
        resolve_project_path(config["prompt"]["path"]).read_text(encoding="utf-8")
    )
    prompt = build_inference_prompt(
        tokenizer,
        prompt_spec,
        labels,
        "I am pleased that the local LoRA preflight is ready.",
        "zero-shot",
    )
    tokens = mx.array([tokenizer.encode(prompt)])
    base_logits = model(tokens)[:, -1, :]
    mx.eval(base_logits)

    model.freeze()
    lora = config["training"]["lora"]
    linear_to_lora_layers(
        model,
        int(lora["num_layers"]),
        {
            "rank": int(lora["rank"]),
            "scale": float(lora["scale"]),
            "dropout": float(lora["dropout"]),
            "keys": list(lora["target_modules"]),
        },
    )
    trainable = dict(tree_flatten(model.trainable_parameters()))
    trainable_parameters = int(sum(value.size for value in trainable.values()))
    expected_parameters = int(config["preflight"]["expected_trainable_parameters"])
    if trainable_parameters != expected_parameters:
        raise ValueError(
            f"Trainable parameter count {trainable_parameters} != {expected_parameters}"
        )
    expected_prefixes = {
        f"model.layers.{block}.{module}"
        for block in lora["adapted_block_indices"]
        for module in lora["target_modules"]
    }
    actual_prefixes = {
        name.rsplit(".", 1)[0]
        for name in trainable
        if name.endswith((".lora_a", ".lora_b"))
    }
    if actual_prefixes != expected_prefixes:
        missing = sorted(expected_prefixes - actual_prefixes)
        extra = sorted(actual_prefixes - expected_prefixes)
        raise ValueError(f"LoRA target mismatch; missing={missing}, extra={extra}")
    converted_logits = model(tokens)[:, -1, :]
    max_difference = float(mx.max(mx.abs(base_logits - converted_logits)).item())
    expected_difference = float(config["preflight"]["zero_step_max_abs_logit_difference"])
    if max_difference != expected_difference:
        raise ValueError(f"Zero-step logits differ by {max_difference}")

    adapter_path.mkdir(parents=True)
    runtime_config = runtime_training_config(
        config,
        seed=int(config["repetition_gate"]["initial_seed"]),
        data_path=resolve_project_path(config["artifacts"]["private_data_root"]),
        adapter_path=adapter_path,
        smoke=False,
    )
    write_json(adapter_path / "adapter_config.json", runtime_config)
    mx.save_safetensors(str(adapter_path / "adapters.safetensors"), trainable)
    del model, converted_logits
    mx.clear_cache()
    reloaded, _ = load(str(MODEL_DIR), adapter_path=str(adapter_path), lazy=False)
    reloaded.eval()
    reloaded_logits = reloaded(tokens)[:, -1, :]
    reload_difference = float(mx.max(mx.abs(base_logits - reloaded_logits)).item())
    if reload_difference != expected_difference:
        raise ValueError(f"Reloaded zero-step logits differ by {reload_difference}")
    peak_memory_gb = float(mx.get_peak_memory() / 1e9)
    if peak_memory_gb > float(config["preflight"]["max_peak_mlx_memory_gb"]):
        raise MemoryError("Zero-step preflight exceeded the memory budget")

    report = {
        "adapter_artifacts": {
            "config": artifact(adapter_path / "adapter_config.json"),
            "weights": artifact(adapter_path / "adapters.safetensors"),
        },
        "adapted_blocks": list(lora["adapted_block_indices"]),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": EXPERIMENT_ID,
        "lora_tensor_count": len(trainable),
        "max_abs_logit_difference_after_conversion": max_difference,
        "max_abs_logit_difference_after_reload": reload_difference,
        "peak_mlx_memory_gb": peak_memory_gb,
        "public_raw_text": False,
        "status": "Passed",
        "target_module_count": len(actual_prefixes),
        "target_modules_per_block": list(lora["target_modules"]),
        "test_absent": not TEST_PATH.exists(),
        "trainable_parameter_count": trainable_parameters,
    }
    write_json(report_path, report)
    print(json.dumps(report, indent=2, sort_keys=True))


def runtime_training_config(
    config: dict[str, Any],
    *,
    seed: int,
    data_path: Path,
    adapter_path: Path,
    smoke: bool,
) -> dict[str, Any]:
    training = config["training"]
    lora = training["lora"]
    return {
        "adapter_path": str(adapter_path),
        "batch_size": int(training["batch_size"]),
        "clear_cache_threshold": 0,
        "data": str(data_path),
        "fine_tune_type": training["fine_tune_type"],
        "grad_accumulation_steps": int(training["grad_accumulation_steps"]),
        "grad_checkpoint": bool(training["grad_checkpoint"]),
        "iters": int(config["preflight"]["smoke_iterations"])
        if smoke
        else int(training["iterations"]),
        "learning_rate": float(training["learning_rate"]),
        "lora_parameters": {
            "dropout": float(lora["dropout"]),
            "keys": list(lora["target_modules"]),
            "rank": int(lora["rank"]),
            "scale": float(lora["scale"]),
        },
        "mask_prompt": bool(training["mask_prompt"]),
        "max_seq_length": int(training["max_sequence_length"]),
        "model": str(MODEL_DIR),
        "num_layers": int(lora["num_layers"]),
        "optimizer": training["optimizer"],
        "save_every": int(config["preflight"]["smoke_iterations"]) + 1
        if smoke
        else int(training["save_every_iterations"]),
        "seed": seed,
        "steps_per_eval": int(training["iterations"]) + 1,
        "steps_per_report": 5 if smoke else int(training["steps_per_report"]),
        "test": False,
        "train": True,
        "val_batches": 0,
    }


def parse_training_log(path: Path) -> tuple[list[dict[str, Any]], dict[str, float]]:
    history: list[dict[str, Any]] = []
    trainable: dict[str, float] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = TRAIN_LOG_PATTERN.search(line)
        if match:
            record = {
                "iteration": int(match.group("iteration")),
                "train_loss": float(match.group("loss")),
                "learning_rate": float(match.group("learning_rate")),
                "iterations_per_second": float(match.group("iterations_per_second")),
                "tokens_per_second": float(match.group("tokens_per_second")),
                "trained_tokens": int(match.group("trained_tokens")),
                "peak_memory_gb": float(match.group("peak_memory_gb")),
            }
            if not all(
                math.isfinite(float(value))
                for key, value in record.items()
                if key not in ("iteration", "trained_tokens")
            ):
                raise ValueError("Training log contains a non-finite value")
            history.append(record)
        trainable_match = TRAINABLE_PATTERN.search(line)
        if trainable_match:
            trainable = {
                "percent": float(trainable_match.group("percent")),
                "total_millions": float(trainable_match.group("total")),
                "trainable_millions": float(trainable_match.group("trainable")),
            }
    if not history or trainable is None:
        raise ValueError("Training log is missing history or trainable parameter output")
    return history, trainable


def write_history(path: Path, history: list[dict[str, Any]]) -> None:
    fields = [
        "iteration",
        "train_loss",
        "learning_rate",
        "iterations_per_second",
        "tokens_per_second",
        "trained_tokens",
        "peak_memory_gb",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in history:
            writer.writerow(row)


def adapter_weight_summary(path: Path) -> dict[str, Any]:
    import mlx.core as mx

    weights = mx.load(str(path))
    b_tensors = {name: value for name, value in weights.items() if name.endswith("lora_b")}
    nonzero_b = sum(bool(mx.any(value != 0).item()) for value in b_tensors.values())
    return {
        "lora_b_nonzero_tensors": nonzero_b,
        "lora_b_tensor_count": len(b_tensors),
        "tensor_count": len(weights),
    }


def stream_subprocess(
    command: list[str],
    log_path: Path,
    timeout_seconds: float,
) -> tuple[int, float]:
    started = time.perf_counter()
    environment = os.environ.copy()
    environment.update(
        {
            "HF_HUB_OFFLINE": "1",
            "PYTHONNOUSERSITE": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "TRANSFORMERS_OFFLINE": "1",
        }
    )
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            log.write(line)
            log.flush()
            print(line, end="", flush=True)
            if time.perf_counter() - started > timeout_seconds:
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                raise TimeoutError("Training exceeded the registered wall-time budget")
        return_code = process.wait()
    return return_code, time.perf_counter() - started


def source_artifacts(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "config": artifact(CONFIG_PATH),
        "constraint": artifact(CONSTRAINT_PATH),
        "labels": artifact(LABELS_PATH),
        "metrics": artifact(METRICS_PATH),
        "model_manifest": artifact(MODEL_MANIFEST_PATH),
        "prompt": artifact(resolve_project_path(config["prompt"]["path"])),
        "runner": artifact(Path(__file__).resolve()),
        "verifier": artifact(VERIFIER_PATH),
    }


def training_paths(
    config: dict[str, Any], seed: int, smoke: bool
) -> tuple[Path, Path, Path, Path]:
    private_adapter_root = resolve_project_path(config["artifacts"]["private_adapter_root"])
    private_data_root = resolve_project_path(config["artifacts"]["private_data_root"])
    if smoke:
        preflight = resolve_project_path(config["artifacts"]["public_preflight_dir"])
        return (
            private_adapter_root / "smoke",
            private_data_root / "smoke",
            preflight / "exp-029-smoke-stdout.log",
            preflight / "exp-029-smoke.json",
        )
    run_dir = resolve_project_path(config["artifacts"]["run_root"]) / f"seed-{seed}"
    return (
        private_adapter_root / f"seed-{seed}",
        private_data_root,
        run_dir / "stdout.log",
        run_dir / "run.json",
    )


def check_seed_gate(config: dict[str, Any], seed: int) -> None:
    allowed = [int(value) for value in config["training"]["seed_schedule"]]
    if seed not in allowed:
        raise ValueError(f"Seed {seed} is outside the registered schedule")
    initial = int(config["repetition_gate"]["initial_seed"])
    if seed == initial:
        return
    verification = (
        resolve_project_path(config["artifacts"]["run_root"])
        / f"seed-{initial}"
        / "verification.json"
    )
    if not verification.is_file():
        raise FileNotFoundError("Seed 42 verification is required before another seed")
    verified = json.loads(verification.read_text(encoding="utf-8"))
    if not verified.get("continue_remaining_seeds"):
        raise ValueError("The registered seed-42 continuation gate is closed")


def run_training(config: dict[str, Any], *, seed: int, smoke: bool) -> None:
    verify_static_inputs(config, include_train=True)
    check_seed_gate(config, seed)
    preflight_dir = resolve_project_path(config["artifacts"]["public_preflight_dir"])
    zero_report_path = preflight_dir / "exp-029-zero-step.json"
    if not zero_report_path.is_file() or json.loads(
        zero_report_path.read_text(encoding="utf-8")
    ).get("status") != "Passed":
        raise ValueError("Zero-step preflight must pass before training")
    if not smoke:
        smoke_report_path = preflight_dir / "exp-029-smoke.json"
        if not smoke_report_path.is_file() or json.loads(
            smoke_report_path.read_text(encoding="utf-8")
        ).get("status") != "Passed":
            raise ValueError("Train-only smoke must pass before formal training")

    adapter_path, data_path, log_path, record_path = training_paths(config, seed, smoke)
    if adapter_path.exists() or log_path.exists() or record_path.exists():
        raise FileExistsError("Append-only training output already exists")
    if not (data_path / "train.jsonl").is_file():
        raise FileNotFoundError(f"Prepared train data is absent: {data_path}")
    if smoke:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        record_path.parent.mkdir(parents=True, exist_ok=False)
    adapter_path.mkdir(parents=True, exist_ok=False)

    runtime = runtime_training_config(
        config,
        seed=seed,
        data_path=data_path,
        adapter_path=adapter_path,
        smoke=smoke,
    )
    runtime_path = adapter_path / "runtime-config.json"
    write_json(runtime_path, runtime)
    command = [str(MLX_LORA), "-c", str(runtime_path)]
    started_at = datetime.now(timezone.utc)
    initial_record: dict[str, Any] = {
        "accessed_splits": ["train"],
        "command": command,
        "experiment_id": EXPERIMENT_ID,
        "seed": seed,
        "smoke": smoke,
        "started_at_utc": started_at.isoformat(),
        "status": "In Progress",
        "test_split_accessed": False,
        "tier": "Minor preflight" if smoke else "Major",
        "validation_split_accessed": False,
    }
    write_json(record_path, initial_record)

    try:
        timeout_minutes = (
            float(config["preflight"]["smoke_wall_time_minutes_max"])
            if smoke
            else float(config["resource_budget"]["training_wall_time_hours_max_per_seed"])
            * 60
        )
        return_code, elapsed = stream_subprocess(
            command, log_path, timeout_seconds=timeout_minutes * 60
        )
        if return_code != 0:
            raise RuntimeError(f"MLX-LM training exited with status {return_code}")
        adapter_file = adapter_path / "adapters.safetensors"
        adapter_config = adapter_path / "adapter_config.json"
        if not adapter_file.is_file() or not adapter_config.is_file():
            raise FileNotFoundError("Training did not save the final adapter")
        history, trainable = parse_training_log(log_path)
        expected_iteration = (
            int(config["preflight"]["smoke_iterations"])
            if smoke
            else int(config["training"]["iterations"])
        )
        if history[-1]["iteration"] != expected_iteration:
            raise ValueError("Training history does not end at the registered iteration")
        max_peak = max(float(row["peak_memory_gb"]) for row in history)
        if max_peak > float(config["resource_budget"]["peak_mlx_memory_gb_max"]):
            raise MemoryError("Training exceeded the registered MLX memory budget")
        weights = adapter_weight_summary(adapter_file)
        if weights["lora_b_nonzero_tensors"] != weights["lora_b_tensor_count"]:
            raise ValueError("At least one trained LoRA B tensor remained entirely zero")

        completed = {
            **initial_record,
            "adapter": {
                "config": artifact(adapter_config),
                "runtime_config": artifact(runtime_path),
                "weights": artifact(adapter_file),
                **weights,
            },
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "data": {
                "expanded_train": artifact(data_path / "train.jsonl"),
                "rows": int(config["preflight"]["smoke_rows"])
                if smoke
                else int(config["data"]["train_rows"]),
                "split": "train",
                "test_rows_accessed": 0,
                "validation_rows_accessed": 0,
            },
            "duration_seconds": elapsed,
            "peak_mlx_memory_gb": max_peak,
            "source_artifacts": source_artifacts(config),
            "status": "Completed" if smoke else "Training Completed",
            "trainable_parameters_reported": trainable,
        }
        if smoke:
            initial_window = statistics.mean(row["train_loss"] for row in history[:2])
            final_window = statistics.mean(row["train_loss"] for row in history[-2:])
            full_reports = [
                row
                for row in history
                if row["iteration"] % int(runtime["steps_per_report"]) == 0
            ]
            median_iterations_per_second = statistics.median(
                row["iterations_per_second"] for row in full_reports
            )
            projected_hours = (
                int(config["training"]["iterations"])
                / median_iterations_per_second
                / 3600
            )
            passed = (
                final_window <= initial_window * 1.25
                and projected_hours
                <= float(config["resource_budget"]["training_wall_time_hours_max_per_seed"])
            )
            completed.update(
                {
                    "final_loss_window": final_window,
                    "initial_loss_window": initial_window,
                    "median_iterations_per_second": median_iterations_per_second,
                    "projected_formal_training_hours": projected_hours,
                    "status": "Passed" if passed else "Failed",
                }
            )
            if not passed:
                write_json(record_path, completed)
                raise RuntimeError("Train-only smoke failed its registered loss or time gate")
        history_path = log_path.with_name(
            "exp-029-smoke-history.csv" if smoke else "history.csv"
        )
        write_history(history_path, history)
        completed["history"] = artifact(history_path)
        completed["stdout"] = artifact(log_path)
        write_json(record_path, completed)
        print(json.dumps(completed, indent=2, sort_keys=True))
    except BaseException as error:
        failed = json.loads(record_path.read_text(encoding="utf-8"))
        if failed.get("status") not in ("Failed", "Passed"):
            failed.update(
                {
                    "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                    "error": {"message": str(error), "traceback": traceback.format_exc()},
                    "status": "Failed",
                }
            )
            write_json(record_path, failed)
        raise


def load_dev(
    expected_rows: int, labels: tuple[str, ...]
) -> tuple[list[str], Any, list[list[int]]]:
    import numpy as np

    texts: list[str] = []
    gold = np.zeros((expected_rows, len(labels)), dtype=np.uint8)
    gold_ids: list[list[int]] = []
    seen_ids: set[str] = set()
    with DEV_PATH.open("r", encoding="utf-8", newline="") as handle:
        for row_index, row in enumerate(csv.reader(handle, delimiter="\t")):
            row_number = row_index + 1
            if row_index >= expected_rows or len(row) != 3:
                raise ValueError(f"Invalid dev row {row_number}")
            text, encoded_labels, comment_id = row
            if comment_id in seen_ids:
                raise ValueError("dev.tsv repeats a comment ID")
            seen_ids.add(comment_id)
            values = [int(value) for value in encoded_labels.split(",")]
            if (
                not values
                or len(values) != len(set(values))
                or any(value < 0 or value >= len(labels) for value in values)
            ):
                raise ValueError(f"Invalid dev labels at row {row_number}")
            texts.append(text)
            gold[row_index, values] = 1
            gold_ids.append(values)
    if len(texts) != expected_rows:
        raise ValueError(f"dev.tsv has {len(texts)} rows; expected {expected_rows}")
    return texts, gold, gold_ids


class TelemetryConstraint:
    def __init__(self, processor: Any, mx: Any):
        self.processor = processor
        self.mx = mx
        self.reset()

    def reset(self) -> None:
        self.processor.reset()
        self.calls = 0
        self.blocked_steps = 0
        self.first_blocked_step: int | None = None
        self.first_blocked_token_id: int | None = None

    def __call__(self, tokens: Any, logits: Any) -> Any:
        raw_argmax = int(self.mx.argmax(logits[0]).item())
        processed = self.processor(tokens, logits)
        blocked = not bool(self.mx.isfinite(processed[0, raw_argmax]).item())
        if blocked:
            self.blocked_steps += 1
            if self.first_blocked_step is None:
                self.first_blocked_step = self.calls
                self.first_blocked_token_id = raw_argmax
        self.calls += 1
        return processed

    def snapshot(self) -> dict[str, Any]:
        return {
            "constraint_intervened": self.blocked_steps > 0,
            "first_blocked_step": self.first_blocked_step,
            "first_blocked_token_id": self.first_blocked_token_id,
            "raw_argmax_blocked_steps": self.blocked_steps,
        }


def eos_token_ids(tokenizer: Any) -> set[int]:
    values = getattr(tokenizer, "eos_token_ids", None)
    if values is None:
        value = getattr(tokenizer, "eos_token_id", None)
        values = [] if value is None else [value]
    return {int(value) for value in values}


def generate_one(
    model: Any,
    tokenizer: Any,
    prompt: str,
    max_tokens: int,
    constraint: TelemetryConstraint,
    mx: Any,
    stream_generate: Any,
    make_sampler: Any,
) -> dict[str, Any]:
    constraint.reset()
    mx.reset_peak_memory()
    started = time.perf_counter()
    output_parts: list[str] = []
    token_logprobs: list[float] = []
    last_response = None
    eos_ids = eos_token_ids(tokenizer)
    for response in stream_generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
        sampler=make_sampler(temp=0.0),
        logits_processors=[constraint],
    ):
        output_parts.append(response.text)
        token_id = int(response.token)
        if token_id not in eos_ids:
            selected_logprob = float(response.logprobs[token_id].item())
            if not math.isfinite(selected_logprob):
                raise ValueError("Generation returned a non-finite selected-token logprob")
            token_logprobs.append(selected_logprob)
        last_response = response
    elapsed = time.perf_counter() - started
    if last_response is None:
        raise RuntimeError("MLX-LM yielded no generation response")
    numeric = (
        last_response.prompt_tps,
        last_response.generation_tps,
        last_response.peak_memory,
        elapsed,
    )
    if not all(math.isfinite(float(value)) for value in numeric):
        raise ValueError("Generation returned a non-finite resource measurement")
    score_sum = float(sum(token_logprobs))
    return {
        "finish_reason": last_response.finish_reason,
        "generated_tokens": int(last_response.generation_tokens),
        "generation_seconds": elapsed,
        "generation_tps": float(last_response.generation_tps),
        "output": "".join(output_parts),
        "peak_memory_gb": float(last_response.peak_memory),
        "prompt_tokens": int(last_response.prompt_tokens),
        "prompt_tps": float(last_response.prompt_tps),
        "sequence_logprob_mean": score_sum / len(token_logprobs)
        if token_logprobs
        else 0.0,
        "sequence_logprob_sum": score_sum,
        **constraint.snapshot(),
    }


def make_record(
    row_number: int,
    condition: str,
    gold_label_ids: list[int],
    labels: tuple[str, ...],
    generated: dict[str, Any],
) -> dict[str, Any]:
    output = generated.pop("output")
    parsed = strict_parse(output, labels)
    parser_error = parsed["error"]
    parser_valid = parser_error is None
    if generated["finish_reason"] != "stop":
        parser_valid = False
        parser_error = "length-terminated"
    predicted_labels = parsed["labels"] if parser_valid else []
    label_to_id = {label: index for index, label in enumerate(labels)}
    return {
        "canonical_output": parsed["canonical_output"] if parser_valid else None,
        "condition": condition,
        "constraint_intervened": generated["constraint_intervened"],
        "finish_reason": generated["finish_reason"],
        "first_blocked_step": generated["first_blocked_step"],
        "first_blocked_token_id": generated["first_blocked_token_id"],
        "generated_tokens": generated["generated_tokens"],
        "generation_seconds": generated["generation_seconds"],
        "generation_tps": generated["generation_tps"],
        "gold_label_ids": gold_label_ids,
        "gold_labels": [labels[value] for value in gold_label_ids],
        "output_character_count": len(output),
        "output_sha256": sha256_text(output),
        "parser_error": parser_error,
        "parser_valid": parser_valid,
        "peak_memory_gb": generated["peak_memory_gb"],
        "predicted_label_ids": [label_to_id[label] for label in predicted_labels],
        "predicted_labels": predicted_labels,
        "prompt_tokens": generated["prompt_tokens"],
        "prompt_tps": generated["prompt_tps"],
        "raw_argmax_blocked_steps": generated["raw_argmax_blocked_steps"],
        "row_number": row_number,
        "sequence_logprob_mean": generated["sequence_logprob_mean"],
        "sequence_logprob_sum": generated["sequence_logprob_sum"],
        "sequence_score_space": "constrained",
    }


def condition_order(row_number: int) -> tuple[str, str]:
    return CONDITIONS if row_number % 2 else tuple(reversed(CONDITIONS))


def expected_pairs(row_count: int) -> Iterator[tuple[int, str]]:
    for row_number in range(1, row_count + 1):
        for condition in condition_order(row_number):
            yield row_number, condition


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def verify_record_prefix(
    records: list[dict[str, Any]], gold_ids: list[list[int]], row_count: int
) -> None:
    pairs = list(expected_pairs(row_count))
    if len(records) > len(pairs):
        raise ValueError("Generation checkpoint has too many rows")
    for index, record in enumerate(records):
        expected_row, expected_condition = pairs[index]
        if (
            record["row_number"] != expected_row
            or record["condition"] != expected_condition
            or record["gold_label_ids"] != gold_ids[expected_row - 1]
        ):
            raise ValueError(f"Generation checkpoint diverges at record {index + 1}")


def metric_tools_module() -> Any:
    sys.path.insert(0, str(SCRIPT_DIR))
    import llm_full_dev_metrics

    return llm_full_dev_metrics


def finalize_dev_outputs(
    config: dict[str, Any],
    run_dir: Path,
    records: list[dict[str, Any]],
    labels: tuple[str, ...],
    gold: Any,
    seed: int,
) -> dict[str, Any]:
    tools = metric_tools_module()
    task_metrics: dict[str, dict[str, Any]] = {}
    generation_metrics: dict[str, dict[str, Any]] = {}
    predictions: dict[str, Any] = {}
    for condition in CONDITIONS:
        condition_records = [row for row in records if row["condition"] == condition]
        if len(condition_records) != int(config["data"]["dev_rows"]):
            raise ValueError(f"{condition} record count is incomplete")
        condition_dir = run_dir / condition
        condition_dir.mkdir(parents=True, exist_ok=False)
        predicted = tools.records_to_prediction_matrix(condition_records, labels)
        metrics, confusion = tools.compute_metrics(gold, predicted, labels)
        generation = tools.summarize_generation(condition_records)
        predictions[condition] = predicted
        task_metrics[condition] = metrics
        generation_metrics[condition] = generation
        tools.write_predictions(condition_dir / "predictions.csv", condition_records)
        tools.write_per_label(condition_dir / "per-label-metrics.csv", metrics, labels)
        tools.write_confusion(
            condition_dir / "multilabel-confusion-matrix.csv", confusion, labels
        )
        tools.write_json(
            condition_dir / "metrics.json",
            {"condition": condition, "generation": generation, "task": metrics},
        )
    tools.write_condition_summary(
        run_dir / "condition-summary.csv",
        CONDITIONS,
        task_metrics,
        generation_metrics,
    )

    named = {
        f"lora-{condition}": predictions[condition] for condition in CONDITIONS
    }
    comparisons = [
        ("lora-zero-minus-lora-few", "lora-zero-shot", "lora-few-shot-synthetic-3")
    ]
    exp025 = config["comparison_inputs"]["EXP-025"]
    for condition in CONDITIONS:
        baseline_gold, baseline_prediction = tools.read_baseline_predictions(
            resolve_project_path(exp025["conditions"][condition]["predictions_path"]),
            labels,
            gold.shape[0],
        )
        if not (baseline_gold == gold).all():
            raise ValueError(f"EXP-025 {condition} gold differs from EXP-029")
        named[f"frozen-{condition}"] = baseline_prediction
        comparisons.append(
            (
                f"lora-minus-frozen-{condition}",
                f"lora-{condition}",
                f"frozen-{condition}",
            )
        )
    selected_frozen = exp025["selected_condition"]
    for condition in CONDITIONS:
        comparisons.append(
            (
                f"lora-{condition}-minus-frozen-selected",
                f"lora-{condition}",
                f"frozen-{selected_frozen}",
            )
        )
    for baseline in config["comparison_inputs"]["EXP-020"]["seed_predictions"]:
        baseline_gold, baseline_prediction = tools.read_baseline_predictions(
            resolve_project_path(baseline["path"]), labels, gold.shape[0]
        )
        if not (baseline_gold == gold).all():
            raise ValueError(f"EXP-020 seed {baseline['seed']} gold differs from EXP-029")
        name = f"bert-seed-{baseline['seed']}"
        named[name] = baseline_prediction
        for condition in CONDITIONS:
            comparisons.append(
                (
                    f"lora-{condition}-minus-{name}",
                    f"lora-{condition}",
                    name,
                )
            )
    bootstrap_config = config["evaluation"]["bootstrap"]
    bootstrap = tools.paired_bootstrap_macro_f1(
        gold,
        named,
        comparisons,
        int(bootstrap_config["replicates"]),
        int(bootstrap_config["seed"]) + seed,
        float(config["evaluation"]["practical_tie_absolute_macro_f1"]),
    )
    tools.write_json(run_dir / "paired-bootstrap.json", bootstrap)

    zero = task_metrics["zero-shot"]["macro"]["f1"]
    few = task_metrics["few-shot-synthetic-3"]["macro"]["f1"]
    threshold = float(config["evaluation"]["practical_tie_absolute_macro_f1"])
    difference = zero - few
    if abs(difference) < threshold:
        selected = "zero-shot"
        reason = "practical tie; zero-shot selected for lower cost and complexity"
    elif difference > 0:
        selected = "zero-shot"
        reason = "zero-shot has higher dev Macro-F1 beyond the practical threshold"
    else:
        selected = "few-shot-synthetic-3"
        reason = "few-shot has higher dev Macro-F1 beyond the practical threshold"
    selected_macro = task_metrics[selected]["macro"]["f1"]
    frozen_selected_macro = float(exp025["selected_dev_macro_f1"])
    aggregate = {
        "baseline_comparisons": {
            condition: {
                "macro_f1": task_metrics[condition]["macro"]["f1"],
                "minus_exp_020_mean": task_metrics[condition]["macro"]["f1"]
                - float(config["comparison_inputs"]["EXP-020"]["dev_macro_f1_mean"]),
                "minus_matched_exp_025": task_metrics[condition]["macro"]["f1"]
                - float(exp025["conditions"][condition]["dev_macro_f1"]),
            }
            for condition in CONDITIONS
        },
        "conditions": {
            condition: {
                "generation": generation_metrics[condition],
                "task": task_metrics[condition],
            }
            for condition in CONDITIONS
        },
        "experiment_id": EXPERIMENT_ID,
        "repetition_gate": {
            "continue_remaining_seeds": selected_macro - frozen_selected_macro >= threshold,
            "frozen_selected_macro_f1": frozen_selected_macro,
            "minimum_improvement": threshold,
            "observed_improvement": selected_macro - frozen_selected_macro,
            "selected_lora_macro_f1": selected_macro,
        },
        "seed": seed,
        "selection": {
            "absolute_difference": abs(difference),
            "difference_zero_minus_few": difference,
            "practical_tie": abs(difference) < threshold,
            "practical_tie_threshold": threshold,
            "reason": reason,
            "selected_condition": selected,
        },
    }
    tools.write_json(run_dir / "aggregate-metrics.json", aggregate)
    return aggregate


def append_log(log_path: Path, message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    line = f"{timestamp} {message}"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(line, flush=True)


def run_dev(config: dict[str, Any], *, seed: int, resume: bool) -> None:
    labels = verify_static_inputs(config, include_dev=True)
    check_seed_gate(config, seed)
    adapter_path, _, log_path, run_path = training_paths(config, seed, smoke=False)
    run_dir = run_path.parent
    if not run_path.is_file() or not adapter_path.is_dir():
        raise FileNotFoundError("Formal training must complete before dev evaluation")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    if run.get("status") not in ("Training Completed", "Failed"):
        raise ValueError(f"Unexpected pre-dev run status: {run.get('status')}")
    adapter_file = adapter_path / "adapters.safetensors"
    verify_hash(adapter_file, run["adapter"]["weights"]["sha256"])
    records_path = run_dir / "generation-records.jsonl"
    if resume:
        if not records_path.is_file():
            raise FileNotFoundError("Resume requested without a generation checkpoint")
    elif records_path.exists() or any((run_dir / condition).exists() for condition in CONDITIONS):
        raise FileExistsError("Append-only dev output already exists; use --resume for a prefix")

    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler

    sys.path.insert(0, str(SCRIPT_DIR))
    from label_json_constraint import LabelJsonLogitsProcessor

    texts, gold, gold_ids = load_dev(int(config["data"]["dev_rows"]), labels)
    run.update(
        {
            "accessed_splits": ["train", "dev"],
            "dev_started_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "Dev In Progress",
            "test_split_accessed": False,
            "validation_split_accessed": True,
        }
    )
    write_json(run_path, run)
    append_log(log_path, f"Starting EXP-029 seed {seed} full-dev evaluation")
    started = time.perf_counter()
    try:
        mx.reset_peak_memory()
        load_started = time.perf_counter()
        model, tokenizer = load(
            str(MODEL_DIR), adapter_path=str(adapter_path), lazy=False
        )
        model_load_seconds = time.perf_counter() - load_started
        constraint = TelemetryConstraint(
            LabelJsonLogitsProcessor(tokenizer, labels, mx), mx
        )
        prompt_spec = json.loads(
            resolve_project_path(config["prompt"]["path"]).read_text(encoding="utf-8")
        )
        for condition in CONDITIONS:
            warmup_prompt = build_inference_prompt(
                tokenizer,
                prompt_spec,
                labels,
                "I am pleased that the trained adapter is ready for validation.",
                condition,
            )
            warmup = generate_one(
                model,
                tokenizer,
                warmup_prompt,
                int(config["decoding"]["max_new_tokens"]),
                constraint,
                mx,
                stream_generate,
                make_sampler,
            )
            parsed = strict_parse(warmup["output"], labels)
            if warmup["finish_reason"] != "stop" or parsed["error"] is not None:
                raise ValueError(f"{condition} trained-adapter warm-up failed")
        append_log(log_path, f"Model loaded in {model_load_seconds:.3f}s; warm-ups passed")

        records = read_records(records_path) if resume else []
        verify_record_prefix(records, gold_ids, len(texts))
        pairs = list(expected_pairs(len(texts)))
        with records_path.open("a" if resume else "w", encoding="utf-8") as output:
            for pair_index, (row_number, condition) in enumerate(
                pairs[len(records) :], start=len(records) + 1
            ):
                elapsed = time.perf_counter() - started
                if elapsed > float(
                    config["resource_budget"]["dev_wall_time_hours_max_per_seed"]
                ) * 3600:
                    raise TimeoutError("Dev generation exceeded the registered budget")
                prompt = build_inference_prompt(
                    tokenizer,
                    prompt_spec,
                    labels,
                    texts[row_number - 1],
                    condition,
                )
                generated = generate_one(
                    model,
                    tokenizer,
                    prompt,
                    int(config["decoding"]["max_new_tokens"]),
                    constraint,
                    mx,
                    stream_generate,
                    make_sampler,
                )
                record = make_record(
                    row_number,
                    condition,
                    gold_ids[row_number - 1],
                    labels,
                    generated,
                )
                output.write(json.dumps(record, sort_keys=True) + "\n")
                output.flush()
                records.append(record)
                if pair_index % 50 == 0:
                    os.fsync(output.fileno())
                if pair_index % 100 == 0 or pair_index == len(pairs):
                    elapsed = time.perf_counter() - started
                    rate = pair_index / elapsed
                    remaining = (len(pairs) - pair_index) / rate
                    run["dev_progress"] = {
                        "completed": pair_index,
                        "estimated_remaining_seconds": remaining,
                        "total": len(pairs),
                    }
                    write_json(run_path, run)
                    append_log(
                        log_path,
                        f"Dev {pair_index}/{len(pairs)}; elapsed {elapsed / 60:.1f} min; ETA {remaining / 60:.1f} min",
                    )
        verify_record_prefix(records, gold_ids, len(texts))
        if len(records) != len(pairs):
            raise ValueError("Dev generation is incomplete")
        aggregate = finalize_dev_outputs(
            config, run_dir, records, labels, gold, seed
        )
        dev_seconds = time.perf_counter() - started
        peak_memory = max(
            aggregate["conditions"][condition]["generation"]["peak_memory_gb_max"]
            for condition in CONDITIONS
        )
        if peak_memory > float(config["resource_budget"]["peak_mlx_memory_gb_max"]):
            raise MemoryError("Dev generation exceeded the registered memory budget")
        run.update(
            {
                "api_cost_usd": 0,
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "data": {
                    **run["data"],
                    "dev_rows": len(texts),
                    "dev_sha256": config["data"]["dev_sha256"],
                    "labels": list(labels),
                    "raw_comment_ids_stored": False,
                    "raw_input_text_stored": False,
                    "test_rows_accessed": 0,
                },
                "dev_duration_seconds": dev_seconds,
                "dev_generation_pairs": len(records),
                "dev_model_load_seconds": model_load_seconds,
                "dev_peak_mlx_memory_gb": peak_memory,
                "status": "Completed",
                "warnings": [
                    "Dev is a model-selection split, not a test or public benchmark result.",
                    "Invalid or length-terminated outputs are empty predictions without retry.",
                    "Constrained sequence log probabilities are not calibrated 28-label probabilities.",
                    "EXP-029 evaluates behavior and does not establish an emotion mechanism.",
                ],
            }
        )
        write_json(run_path, run)
        append_log(
            log_path,
            "Completed dev: "
            + ", ".join(
                f"{condition} Macro-F1={aggregate['conditions'][condition]['task']['macro']['f1']:.6f}"
                for condition in CONDITIONS
            ),
        )
    except BaseException as error:
        run.update(
            {
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "error": {"message": str(error), "traceback": traceback.format_exc()},
                "status": "Failed",
            }
        )
        write_json(run_path, run)
        append_log(log_path, f"FAILED: {error}")
        raise


def main() -> None:
    args = parse_args()
    config = load_config()
    if args.command == "prepare":
        prepare_data(config)
    elif args.command == "preflight":
        zero_step_preflight(config)
    elif args.command == "smoke":
        run_training(
            config,
            seed=int(config["repetition_gate"]["initial_seed"]),
            smoke=True,
        )
    elif args.command == "train":
        run_training(config, seed=args.seed, smoke=False)
    elif args.command == "dev":
        run_dev(config, seed=args.seed, resume=args.resume)
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()
