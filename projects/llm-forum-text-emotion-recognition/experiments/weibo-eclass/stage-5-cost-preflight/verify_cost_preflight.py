#!/usr/bin/env python3
"""Independently verify EXP-044 without importing its runner."""

from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
from typing import Any


EXPERIMENT_ID = "EXP-044"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
CONFIG_PATH = SCRIPT_DIR / "config.json"
TRAIN_LOG_PATTERN = re.compile(
    r"Iter (?P<iteration>\d+): Train loss (?P<loss>[^,]+), "
    r"Learning Rate (?P<learning_rate>[^,]+), It/sec (?P<iterations_per_second>[^,]+), "
    r"Tokens/sec (?P<tokens_per_second>[^,]+), Trained Tokens (?P<trained_tokens>\d+), "
    r"Peak mem (?P<peak_memory_gb>[^ ]+) GB"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Project path escapes root: {value}")
    return path


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def quantile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return values[lower]
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def allocate_quotas(counts: dict[str, int], total: int, labels: list[str]) -> dict[str, int]:
    population = sum(counts.values())
    raw = {label: total * counts[label] / population for label in labels}
    quotas = {label: max(1, math.floor(raw[label])) for label in labels}
    while sum(quotas.values()) > total:
        choices = [label for label in labels if quotas[label] > 1]
        label = min(choices, key=lambda item: (raw[item] - quotas[item], labels.index(item)))
        quotas[label] -= 1
    while sum(quotas.values()) < total:
        label = max(labels, key=lambda item: (raw[item] - quotas[item], -labels.index(item)))
        quotas[label] += 1
    return quotas


def render_messages(config: dict[str, Any], prompt: dict[str, Any], row: dict[str, Any]) -> list[dict[str, str]]:
    definitions = "\n".join(
        f"- {label}: {prompt['label_definitions'][label]}" for label in config["data"]["labels"]
    )
    return [
        {
            "role": "system",
            "content": prompt["system_template"].format(
                label_definitions=definitions,
                output_schema=prompt["output_schema"],
            ),
        },
        {
            "role": "user",
            "content": prompt["target_only_template"].format(
                target=row["views"]["target_only"]["target"]
            ),
        },
        {
            "role": "assistant",
            "content": prompt["assistant_target_template"].replace("{label}", row["label"]),
        },
    ]


def expected_selection(config: dict[str, Any], rows: list[dict[str, Any]], tokenizer: Any, prompt: dict[str, Any]) -> list[dict[str, Any]]:
    measured = []
    for row in rows:
        messages = render_messages(config, prompt, row)
        tokens = tokenizer.apply_chat_template(messages, return_dict=False)
        prefix = tokenizer.apply_chat_template(messages[:-1], add_generation_prompt=True, return_dict=False)
        supervised = tokenizer.decode(tokens[len(prefix) :])
        expected = "<think>\n\n</think>\n\n" + messages[-1]["content"] + "<|im_end|>\n"
        if supervised != expected:
            raise ValueError("Independent supervision-boundary check failed")
        measured.append(
            {
                "label": row["label"],
                "messages": messages,
                "sample_id": row["sample_id"],
                "supervised_tokens": len(tokens) - len(prefix),
                "token_length": len(tokens),
            }
        )
    counts = Counter(row["label"] for row in measured)
    quotas = allocate_quotas(dict(counts), config["sampling"]["rows"], config["data"]["labels"])
    selected = []
    namespace = config["sampling"]["seed_namespace"]
    for label in config["data"]["labels"]:
        values = [row for row in measured if row["label"] == label]
        values.sort(key=lambda row: (row["token_length"], sha256_text(f"{namespace}:{row['sample_id']}")))
        quota = quotas[label]
        indices = [min(len(values) - 1, ((2 * rank + 1) * len(values)) // (2 * quota)) for rank in range(quota)]
        selected.extend(values[index] for index in indices)
    return selected


def parse_private_history(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = TRAIN_LOG_PATTERN.search(line)
        if match:
            rows.append(
                {
                    "iteration": int(match.group("iteration")),
                    "train_loss": float(match.group("loss")),
                    "learning_rate": float(match.group("learning_rate")),
                    "iterations_per_second": float(match.group("iterations_per_second")),
                    "tokens_per_second": float(match.group("tokens_per_second")),
                    "trained_tokens": int(match.group("trained_tokens")),
                    "peak_memory_gb": float(match.group("peak_memory_gb")),
                }
            )
    return rows


def load_csv_history(path: Path) -> list[dict[str, Any]]:
    converters = {
        "iteration": int,
        "train_loss": float,
        "learning_rate": float,
        "iterations_per_second": float,
        "tokens_per_second": float,
        "trained_tokens": int,
        "peak_memory_gb": float,
    }
    with path.open(encoding="utf-8", newline="") as source:
        return [
            {key: converters[key](value) for key, value in row.items()}
            for row in csv.DictReader(source)
        ]


def adapter_summary(path: Path) -> dict[str, Any]:
    import numpy as np
    from safetensors import safe_open

    result = Counter()
    finite = True
    with safe_open(path, framework="numpy") as source:
        for name in source.keys():
            tensor = source.get_tensor(name)
            result["tensor_count"] += 1
            result["trainable_parameter_count"] += int(tensor.size)
            finite = finite and bool(np.all(np.isfinite(tensor)))
            if name.endswith("lora_b"):
                result["lora_b_tensor_count"] += 1
                result["lora_b_nonzero_tensors"] += int(bool(np.any(tensor != 0)))
    return {**dict(result), "all_finite": finite}


def main() -> None:
    config = load_json(CONFIG_PATH)
    run_dir = resolve(config["run_dir"])
    private_root = resolve(config["private_root"])
    output = run_dir / "verification.json"
    if output.exists():
        raise FileExistsError("EXP-044 verification is append-only")
    run = load_json(run_dir / "run.json")
    sample_summary = load_json(run_dir / "sample_summary.json")
    projection = load_json(run_dir / "cost_projection.json")
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: Any) -> None:
        checks.append({"check": name, "detail": detail, "status": "Passed" if passed else "Failed"})

    check(
        "run-boundary",
        run.get("experiment_id") == EXPERIMENT_ID
        and run.get("tier") == "Minor"
        and run.get("status") == "Awaiting Independent Verification"
        and run.get("accessed_splits") == ["train"]
        and run.get("validation_split_accessed") is False
        and run.get("test_split_accessed") is False,
        {"status": run.get("status"), "accessed_splits": run.get("accessed_splits")},
    )
    train_path = resolve(config["data"]["train_path"])
    prompt_path = resolve(config["prompt"]["path"])
    manifest_path = resolve(config["model"]["manifest_path"])
    check(
        "frozen-input-hashes",
        sha256_file(train_path) == config["data"]["train_sha256"]
        and sha256_file(prompt_path) == config["prompt"]["sha256"]
        and sha256_file(manifest_path) == config["model"]["manifest_sha256"],
        {"train_rows_expected": config["data"]["train_rows"]},
    )

    rows = [json.loads(line) for line in train_path.open(encoding="utf-8")]
    check(
        "train-schema-and-count",
        len(rows) == config["data"]["train_rows"]
        and len({row["sample_id"] for row in rows}) == len(rows)
        and all(row["protocol_id"] == config["data"]["protocol_id"] for row in rows),
        {"rows": len(rows)},
    )
    os.environ.update(
        {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    )
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(resolve(config["model"]["local_path"]), local_files_only=True)
    prompt = load_json(prompt_path)
    selected = expected_selection(config, rows, tokenizer, prompt)
    private_manifest = [
        json.loads(line) for line in (private_root / "selection-manifest.jsonl").open(encoding="utf-8")
    ]
    expected_ids = [row["sample_id"] for row in selected]
    actual_ids = [row["sample_id"] for row in private_manifest]
    check(
        "deterministic-representative-sample",
        actual_ids == expected_ids and len(actual_ids) == config["sampling"]["rows"],
        {"rows": len(actual_ids), "labels": dict(Counter(row["label"] for row in private_manifest))},
    )
    selection_material = "\n".join(
        sha256_text(f"{config['sampling']['seed_namespace']}:{sample_id}") for sample_id in actual_ids
    )
    check(
        "public-sample-summary",
        sample_summary["selection_digest_sha256"] == sha256_text(selection_material)
        and sample_summary["sample_rows"] == len(actual_ids)
        and sample_summary["raw_ids_stored_publicly"] is False
        and sample_summary["raw_text_stored_publicly"] is False,
        {"selection_digest_sha256": sample_summary["selection_digest_sha256"]},
    )
    lora_train = private_root / "lora-data" / "train.jsonl"
    lora_rows = [json.loads(line) for line in lora_train.open(encoding="utf-8")]
    check(
        "private-training-contract",
        len(lora_rows) == len(selected)
        and all(row == {"messages": expected["messages"]} for row, expected in zip(lora_rows, selected))
        and not (private_root / "lora-data" / "valid.jsonl").exists()
        and not (private_root / "lora-data" / "test.jsonl").exists(),
        {"train_rows": len(lora_rows), "validation_file": False, "test_file": False},
    )
    runtime = load_json(private_root / "lora-runtime.json")
    training = config["training"]
    runtime_ok = (
        runtime["iters"] == training["iterations"]
        and runtime["seed"] == training["seed"]
        and runtime["num_layers"] == training["num_layers"]
        and runtime["mask_prompt"] is True
        and runtime["test"] is False
        and runtime["test_batches"] == 0
        and runtime["val_batches"] == 0
        and runtime["lora_parameters"]["keys"] == training["target_modules"]
    )
    check("runtime-config", runtime_ok, {"iterations": runtime["iters"], "seed": runtime["seed"]})

    private_history = parse_private_history(private_root / "stdout.log")
    public_history = load_csv_history(run_dir / "history.csv")
    history_ok = (
        private_history == public_history
        and bool(public_history)
        and public_history[-1]["iteration"] == training["iterations"]
        and all(
            math.isfinite(value)
            for row in public_history
            for value in row.values()
            if isinstance(value, float)
        )
    )
    check(
        "training-history",
        history_ok,
        {"report_rows": len(public_history), "last_iteration": public_history[-1]["iteration"]},
    )
    adapter_path = private_root / "adapter" / "adapters.safetensors"
    adapter = adapter_summary(adapter_path)
    expected_b = len(training["adapted_block_indices"]) * len(training["target_modules"])
    check(
        "adapter-tensors",
        adapter.get("tensor_count") == expected_b * 2
        and adapter.get("lora_b_tensor_count") == expected_b
        and adapter.get("lora_b_nonzero_tensors") == expected_b
        and adapter.get("all_finite") is True
        and adapter.get("trainable_parameter_count") == run["result"]["trainable_parameter_count"],
        adapter,
    )
    peak_memory = max(row["peak_memory_gb"] for row in public_history)
    check(
        "memory-gate",
        peak_memory == run["result"]["peak_memory_gb"]
        and peak_memory == projection["observed_peak_memory_gb"]
        and peak_memory <= config["resource_budget"]["peak_memory_gb_max"],
        {"peak_memory_gb": peak_memory, "limit_gb": config["resource_budget"]["peak_memory_gb_max"]},
    )
    steady = [
        row["iterations_per_second"]
        for row in public_history
        if row["iteration"] > training["steady_state_after_iteration"]
    ]
    median_rate = statistics.median(steady)
    expected_projections = []
    for epochs in training["epochs_for_projection"]:
        raw = config["data"]["train_rows"] * epochs / median_rate / 3600
        expected_projections.append(
            {
                "epochs": epochs,
                "one_seed_hours_raw": raw,
                "one_seed_hours_with_safety": raw * config["resource_budget"]["safety_multiplier"],
                "three_seeds_hours_sequential_with_safety": raw
                * config["resource_budget"]["safety_multiplier"]
                * 3,
            }
        )
    projection_ok = (
        abs(projection["median_iterations_per_second"] - median_rate) < 1e-12
        and abs(projection["p25_iterations_per_second"] - quantile(steady, 0.25)) < 1e-12
        and projection["projections"] == expected_projections
        and projection["validation_and_inference_time_included"] is False
    )
    check("cost-projection", projection_ok, {"median_iterations_per_second": median_rate})

    public_paths = [
        path for path in run_dir.iterdir() if path.is_file() and path.name != "verification.json"
    ]
    public_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in public_paths)
    leaked_ids = sum(sample_id in public_text for sample_id in (row["sample_id"] for row in rows))
    long_targets = {
        row["views"]["target_only"]["target"]
        for row in rows
        if len(row["views"]["target_only"]["target"]) >= 16
    }
    leaked_targets = sum(target in public_text for target in long_targets)
    check(
        "public-privacy-boundary",
        leaked_ids == 0 and leaked_targets == 0,
        {"raw_id_matches": leaked_ids, "long_raw_text_matches": leaked_targets},
    )
    check(
        "no-performance-claim",
        all(key not in public_text.lower() for key in ('"macro_f1"', '"accuracy"', '"weighted_f1"')),
        {"classification_metrics_present": False},
    )

    failed = [item["check"] for item in checks if item["status"] != "Passed"]
    report = {
        "accessed_splits": ["train"],
        "check_count": len(checks),
        "checks": checks,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": EXPERIMENT_ID,
        "failed_checks": failed,
        "status": "Passed" if not failed else "Failed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
        "verifier_imported_runner": False,
    }
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not failed:
        run["status"] = "Verified"
        run["verified_at_utc"] = report["completed_at_utc"]
        run["verification"] = {
            "path": str(output.relative_to(PROJECT_ROOT)),
            "sha256": sha256_file(output),
        }
        (run_dir / "run.json").write_text(
            json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps({"check_count": len(checks), "failed_checks": failed, "status": report["status"]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
