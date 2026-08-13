#!/usr/bin/env python3
"""Run EXP-043 frozen Qwen context x reasoning validation inference."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import sys
import time
from typing import Any, Iterable, Sequence

from label_parser import parse_final_label


MODULE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = MODULE_ROOT / "config.json"
INVALID_LABEL = "__invalid__"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("initialize")
    subparsers.add_parser("smoke")
    infer = subparsers.add_parser("infer")
    infer.add_argument("--condition", choices=("A", "B", "C", "D"), required=True)
    subparsers.add_parser("aggregate")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if PROJECT_ROOT not in path.parents and path != PROJECT_ROOT:
        raise ValueError(f"Path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def atomic_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if private:
        os.chmod(temporary, 0o600)
    temporary.replace(path)
    if private:
        os.chmod(path, 0o600)


def append_private_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch(mode=0o600)
    with path.open("a", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        target.flush()
        os.fsync(target.fileno())
    os.chmod(path, 0o600)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as source:
        return [json.loads(line) for line in source if line.strip()]


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": display_path(path),
        "sha256": sha256_file(path),
    }


def quantile(values: Sequence[float | int], fraction: float) -> float:
    if not values:
        raise ValueError("Cannot summarize empty values")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def numeric_summary(values: Sequence[float | int]) -> dict[str, float | int]:
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "min": min(values),
        "p50": quantile(values, 0.50),
        "p95": quantile(values, 0.95),
        "p99": quantile(values, 0.99),
    }


def implementation_files(config: dict[str, Any]) -> dict[str, Path]:
    fields = {
        "runner": "runner_path",
        "verifier": "verifier_path",
        "test": "test_path",
        "parser": "parser_path",
        "prompt": "prompt_path",
        "requirements": "requirements_path",
    }
    return {
        name: resolve_project_path(config["implementation"][path_field])
        for name, path_field in fields.items()
    }


def load_config(*, verify_sources: bool = True) -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config["experiment_id"] != "EXP-043" or config["tier"] != "Major":
        raise ValueError("EXP-043 identity drift")
    if config["data"]["test_access"] is not False:
        raise ValueError("Test access must remain false")
    if tuple(config["conditions"]) != ("A", "B", "C", "D"):
        raise ValueError("Condition order drift")
    if config["generation"]["deterministic"] is not True or config["generation"]["temperature"] != 0.0:
        raise ValueError("Formal inference must remain deterministic greedy")
    if verify_sources:
        for name, path in implementation_files(config).items():
            expected = config["implementation"][f"{name}_sha256"]
            if expected == "TO_BE_FROZEN" or sha256_file(path) != expected:
                raise ValueError(f"Frozen {name} hash drift")
        reference = resolve_project_path(config["stage3_reference"]["aggregate_path"])
        if sha256_file(reference) != config["stage3_reference"]["aggregate_sha256"]:
            raise ValueError("EXP-042 aggregate hash drift")
    return config


def run_dir(config: dict[str, Any]) -> Path:
    return resolve_project_path(config["run_dir"])


def private_root(config: dict[str, Any]) -> Path:
    return resolve_project_path(config["private_root"])


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return {"commit": commit, "dirty": dirty}


def package_versions() -> dict[str, str]:
    names = ("mlx", "mlx-lm", "numpy", "safetensors", "tokenizers", "transformers")
    return {name: importlib.metadata.version(name) for name in names}


def log_event(config: dict[str, Any], event: dict[str, Any]) -> None:
    record = {"at_utc": utc_now(), **event}
    path = run_dir(config) / "stdout.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as target:
        target.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
    print(json.dumps(event, ensure_ascii=True, sort_keys=True), flush=True)


def load_run(config: dict[str, Any]) -> dict[str, Any]:
    path = run_dir(config) / "run.json"
    if not path.is_file():
        raise FileNotFoundError("Run is not initialized")
    return json.loads(path.read_text(encoding="utf-8"))


def save_run(config: dict[str, Any], run: dict[str, Any]) -> None:
    atomic_json(run_dir(config) / "run.json", run)


def record_command(config: dict[str, Any], run: dict[str, Any]) -> None:
    command = f"{sys.executable} {display_path(Path(__file__))} " + " ".join(sys.argv[1:])
    if command not in run["command_history"]:
        run["command_history"].append(command)


def update_run_stage(
    config: dict[str, Any],
    stage: str,
    status: str,
    started_at: str,
    elapsed: float,
    output: Path,
    *,
    accessed_split: str | None = None,
) -> None:
    run = load_run(config)
    record_command(config, run)
    run["stages"][stage] = {
        "artifact": artifact(output),
        "completed_at_utc": utc_now(),
        "duration_seconds": elapsed,
        "started_at_utc": started_at,
        "status": status,
    }
    if accessed_split and accessed_split not in run["accessed_splits"]:
        run["accessed_splits"].append(accessed_split)
        run["accessed_splits"].sort()
    run["validation_split_accessed"] = "validation" in run["accessed_splits"]
    run["status"] = status if status == "Failed" else "Running"
    save_run(config, run)


def load_rows(config: dict[str, Any], split: str) -> list[dict[str, Any]]:
    if split not in {"train", "validation"}:
        raise ValueError(split)
    data = config["data"]
    path = resolve_project_path(data[f"{split}_path"])
    if sha256_file(path) != data[f"{split}_sha256"]:
        raise ValueError(f"{split} hash drift")
    rows = read_jsonl(path)
    if len(rows) != data[f"{split}_rows"]:
        raise ValueError(f"{split} row-count drift")
    labels = set(data["labels"])
    sample_ids: set[str] = set()
    for row in rows:
        if row.get("protocol_id") != data["protocol_id"] or row.get("label") not in labels:
            raise ValueError(f"{split} schema or label drift")
        if row["sample_id"] in sample_ids:
            raise ValueError(f"Duplicate {split} sample_id")
        sample_ids.add(row["sample_id"])
        if row["views"]["target_only"]["target"] != row["views"]["previous_context"]["target"]:
            raise ValueError("Paired target drift")
        previous = row["views"]["previous_context"]["previous"]
        if bool(previous) != bool(row["context_available"]):
            raise ValueError("context_available drift")
    return rows


def load_prompt(config: dict[str, Any]) -> dict[str, Any]:
    prompt = json.loads(resolve_project_path(config["implementation"]["prompt_path"]).read_text(encoding="utf-8"))
    if tuple(prompt["label_definitions"]) != tuple(config["data"]["labels"]):
        raise ValueError("Prompt ontology order drift")
    return prompt


def prompt_messages(
    config: dict[str, Any],
    prompt: dict[str, Any],
    row: dict[str, Any],
    view: str,
) -> list[dict[str, str]]:
    definitions = "\n".join(
        f"- {label}: {prompt['label_definitions'][label]}" for label in config["data"]["labels"]
    )
    system = prompt["system_template"].format(
        label_definitions=definitions,
        output_schema=prompt["output_schema"],
    )
    target = row["views"]["target_only"]["target"]
    if view == "target_only":
        user = prompt["target_only_template"].format(target=target)
    elif view == "previous_context":
        previous = row["views"]["previous_context"]["previous"]
        user = (
            prompt["previous_context_template"].format(previous=previous, target=target)
            if previous
            else prompt["target_only_template"].format(target=target)
        )
    else:
        raise ValueError(view)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def messages_sha256(messages: list[dict[str, str]]) -> str:
    return sha256_text(json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def verify_model_manifest(config: dict[str, Any]) -> dict[str, Any]:
    manifest_path = resolve_project_path(config["model"]["manifest_path"])
    if sha256_file(manifest_path) != config["model"]["manifest_sha256"]:
        raise ValueError("Model manifest hash drift")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["repo_id"] != config["model"]["repo_id"] or manifest["revision"] != config["model"]["revision"]:
        raise ValueError("Model identity drift")
    model_root = resolve_project_path(config["model"]["local_path"])
    checked = []
    for expected in manifest["mlx_bf16"]["files"]:
        path = model_root / expected["path"]
        if path.stat().st_size != expected["bytes"] or sha256_file(path) != expected["sha256"]:
            raise ValueError(f"Model file drift: {expected['path']}")
        checked.append({"bytes": expected["bytes"], "path": expected["path"], "sha256": expected["sha256"]})
    return {"file_count": len(checked), "files": checked, "total_bytes": sum(row["bytes"] for row in checked)}


def classification_metrics(
    gold: Sequence[str],
    predictions: Sequence[str],
    labels: Sequence[str],
    invalid_label: str = INVALID_LABEL,
) -> dict[str, Any]:
    if len(gold) != len(predictions) or not gold:
        raise ValueError("Metrics require equal non-empty vectors")
    allowed_predictions = set(labels) | {invalid_label}
    if any(value not in labels for value in gold) or any(value not in allowed_predictions for value in predictions):
        raise ValueError("Metric label outside frozen ontology")
    per_class: dict[str, Any] = {}
    f1_values: list[float] = []
    precision_values: list[float] = []
    recall_values: list[float] = []
    weighted_sum = 0.0
    for label in labels:
        tp = sum(g == label and p == label for g, p in zip(gold, predictions))
        fp = sum(g != label and p == label for g, p in zip(gold, predictions))
        fn = sum(g == label and p != label for g, p in zip(gold, predictions))
        support = sum(g == label for g in gold)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"f1": f1, "precision": precision, "recall": recall, "support": support}
        precision_values.append(precision)
        recall_values.append(recall)
        f1_values.append(f1)
        weighted_sum += f1 * support
    columns = list(labels) + [invalid_label]
    confusion = [
        [sum(g == gold_label and p == predicted_label for g, p in zip(gold, predictions)) for predicted_label in columns]
        for gold_label in labels
    ]
    return {
        "accuracy": sum(g == p for g, p in zip(gold, predictions)) / len(gold),
        "confusion_columns": columns,
        "confusion_matrix": confusion,
        "macro_f1": statistics.fmean(f1_values),
        "macro_precision": statistics.fmean(precision_values),
        "macro_recall": statistics.fmean(recall_values),
        "per_class": per_class,
        "rows": len(gold),
        "weighted_f1": weighted_sum / len(gold),
    }


def metrics_by_slice(records: Sequence[dict[str, Any]], labels: Sequence[str]) -> dict[str, Any]:
    slices = {
        "all": list(records),
        "context_available": [row for row in records if row["context_available"]],
        "first_clause": [row for row in records if not row["context_available"]],
    }
    return {
        name: classification_metrics(
            [row["gold_label"] for row in values],
            [row["prediction"] for row in values],
            labels,
        )
        for name, values in slices.items()
    }


def macro_f1(gold: Sequence[str], predictions: Sequence[str], labels: Sequence[str]) -> float:
    return classification_metrics(gold, predictions, labels)["macro_f1"]


def factorial_effects(scores: dict[str, float]) -> dict[str, float]:
    return {
        "context_reasoning_off_B_minus_A": scores["B"] - scores["A"],
        "context_reasoning_on_D_minus_C": scores["D"] - scores["C"],
        "reasoning_target_only_C_minus_A": scores["C"] - scores["A"],
        "reasoning_context_D_minus_B": scores["D"] - scores["B"],
        "interaction_D_minus_C_minus_B_minus_A": (scores["D"] - scores["C"]) - (scores["B"] - scores["A"]),
        "average_context_effect": ((scores["B"] - scores["A"]) + (scores["D"] - scores["C"])) / 2,
        "average_reasoning_effect": ((scores["C"] - scores["A"]) + (scores["D"] - scores["B"])) / 2,
    }


def choose_condition(
    scores: dict[str, float],
    conditions: dict[str, dict[str, Any]],
    durations: dict[str, float],
    tie: float,
) -> dict[str, Any]:
    best = max(scores.values())
    candidates = [name for name, score in scores.items() if best - score < tie]
    selected = min(
        candidates,
        key=lambda name: (
            bool(conditions[name]["reasoning"]),
            conditions[name]["view"] != "target_only",
            durations[name],
            name,
        ),
    )
    return {
        "best_macro_f1": best,
        "candidate_conditions": candidates,
        "practical_tie_threshold": tie,
        "reason": "within tie threshold; prefer reasoning off, target only, then lower batch time",
        "selected_condition": selected,
        "selected_macro_f1": scores[selected],
    }


def initialize(config: dict[str, Any]) -> None:
    public = run_dir(config)
    private = private_root(config)
    if public.exists() or private.exists():
        raise FileExistsError("EXP-043 output directory already exists")
    started_at, started = utc_now(), time.perf_counter()
    train_rows = load_rows(config, "train")
    validation_path = resolve_project_path(config["data"]["validation_path"])
    if not validation_path.is_file():
        raise FileNotFoundError("Frozen validation file is unavailable")
    model_inventory = verify_model_manifest(config)
    public.mkdir(parents=True)
    private.mkdir(parents=True, mode=0o700)
    os.chmod(private, 0o700)
    frozen_names = {
        "runner": "frozen-runner.py",
        "verifier": "frozen-verifier.py",
        "test": "frozen-test.py",
        "parser": "frozen-label-parser.py",
        "prompt": "frozen-prompt-v1.json",
        "requirements": "frozen-requirements-lock.txt",
    }
    frozen_artifacts = {}
    for name, source in implementation_files(config).items():
        destination = public / frozen_names[name]
        shutil.copy2(source, destination)
        frozen_artifacts[name] = artifact(destination)
    protocol = resolve_project_path(config["protocol_path"])
    shutil.copy2(protocol, public / "frozen-protocol.md")
    shutil.copy2(CONFIG_PATH, public / "frozen-config.json")
    run = {
        "accessed_splits": [],
        "command_history": [],
        "config": artifact(public / "frozen-config.json"),
        "environment": {
            "architecture": platform.machine(),
            "executable": sys.executable,
            "packages": package_versions(),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "experiment_id": config["experiment_id"],
        "frozen_artifacts": frozen_artifacts,
        "git": git_metadata(),
        "model": {
            "adapter_loaded": False,
            "inventory": model_inventory,
            "manifest": artifact(resolve_project_path(config["model"]["manifest_path"])),
            "precision": config["model"]["precision"],
            "quantized": config["model"]["quantized"],
            "repo_id": config["model"]["repo_id"],
            "revision": config["model"]["revision"],
        },
        "rq_ids": config["rq_ids"],
        "stage": "stage-4-frozen-qwen-context-reasoning-2x2",
        "stages": {},
        "started_at_utc": started_at,
        "status": "Initialized",
        "test_split_accessed": False,
        "tier": config["tier"],
        "validation_split_accessed": False,
    }
    record_command(config, run)
    save_run(config, run)
    init_report = {
        "completed_at_utc": utc_now(),
        "experiment_id": config["experiment_id"],
        "model_files_verified": model_inventory["file_count"],
        "model_total_bytes": model_inventory["total_bytes"],
        "status": "Passed",
        "test_split_accessed": False,
        "train_rows_verified": len(train_rows),
        "validation_identity_check": "deferred until formal inference after train-only smoke",
        "validation_split_accessed_for_results": False,
    }
    output = public / "initialize.json"
    atomic_json(output, init_report)
    update_run_stage(config, "initialize", "Passed", started_at, time.perf_counter() - started, output)
    log_event(config, {"stage": "initialize", "status": "Passed"})


def load_model_runtime(config: dict[str, Any]):
    os.environ.update(
        {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    )
    from mlx_lm import batch_generate, load
    from mlx_lm.sample_utils import make_sampler

    model, tokenizer = load(str(resolve_project_path(config["model"]["local_path"])))
    sampler = make_sampler(temp=config["generation"]["temperature"])
    return model, tokenizer, batch_generate, sampler


def generate_one_batch(
    config: dict[str, Any],
    model: Any,
    tokenizer: Any,
    batch_generate: Any,
    sampler: Any,
    messages: list[list[dict[str, str]]],
    reasoning: bool,
) -> tuple[list[str], list[list[int]], dict[str, Any]]:
    prompts = [
        list(
            tokenizer.apply_chat_template(
                value,
                add_generation_prompt=True,
                enable_thinking=reasoning,
                tokenize=True,
            )
        )
        for value in messages
    ]
    started = time.perf_counter()
    response = batch_generate(
        model,
        tokenizer,
        prompts,
        max_tokens=config["generation"]["max_new_tokens"],
        sampler=sampler,
        completion_batch_size=config["generation"]["completion_batch_size"],
        prefill_batch_size=config["generation"]["prefill_batch_size"],
        prefill_step_size=config["generation"]["prefill_step_size"],
        verbose=False,
    )
    elapsed = time.perf_counter() - started
    stats = asdict(response.stats)
    stats["batch_elapsed_seconds"] = elapsed
    if not math.isfinite(elapsed) or elapsed <= 0:
        raise RuntimeError("Nonfinite batch timing")
    return list(response.texts), prompts, stats


def smoke(config: dict[str, Any]) -> None:
    started_at, started = utc_now(), time.perf_counter()
    run = load_run(config)
    if run["stages"].get("initialize", {}).get("status") != "Passed":
        raise RuntimeError("Initialize must pass before smoke")
    output = run_dir(config) / "smoke.json"
    if output.exists():
        raise FileExistsError(output)
    rows = load_rows(config, "train")[: config["resource_budget"]["smoke_rows"]]
    prompt = load_prompt(config)
    model, tokenizer, batch_generate, sampler = load_model_runtime(config)
    private_rows: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    for reasoning in (False, True):
        messages = [prompt_messages(config, prompt, row, "target_only") for row in rows]
        texts, prompts, stats = generate_one_batch(
            config, model, tokenizer, batch_generate, sampler, messages, reasoning
        )
        parsed = [parse_final_label(text, thinking=reasoning, labels=config["data"]["labels"]) for text in texts]
        mode = "reasoning_on" if reasoning else "reasoning_off"
        for index, (row, text, prompt_ids, result) in enumerate(zip(rows, texts, prompts, parsed)):
            private_rows.append(
                {
                    "generated_tokens": len(tokenizer.encode(text, add_special_tokens=False)),
                    "message_sha256": messages_sha256(messages[index]),
                    "mode": mode,
                    "parse": result.to_dict(),
                    "prompt_tokens": len(prompt_ids),
                    "raw_output": text,
                    "sample_id": row["sample_id"],
                }
            )
        summaries[mode] = {
            "batch": stats,
            "parser_valid_count": sum(result.valid for result in parsed),
            "parser_valid_rate": sum(result.valid for result in parsed) / len(parsed),
            "rows": len(parsed),
        }
    batches_per_condition = math.ceil(config["data"]["validation_rows"] / config["generation"]["batch_size"])
    projected = (
        config["resource_budget"]["projection_safety_multiplier"]
        * batches_per_condition
        * 2
        * (
            summaries["reasoning_off"]["batch"]["batch_elapsed_seconds"]
            + summaries["reasoning_on"]["batch"]["batch_elapsed_seconds"]
        )
    )
    peak = max(summary["batch"]["peak_memory"] for summary in summaries.values())
    passed = (
        projected <= config["resource_budget"]["formal_wall_time_seconds_max"]
        and peak <= config["resource_budget"]["peak_memory_gb_max"]
        and all(summary["parser_valid_count"] >= 1 for summary in summaries.values())
    )
    private_path = private_root(config) / "smoke-outputs.jsonl"
    append_private_jsonl(private_path, private_rows)
    report = {
        "accessed_splits": ["train"],
        "completed_at_utc": utc_now(),
        "experiment_id": config["experiment_id"],
        "full_2x2_projected_seconds_with_safety_multiplier": projected,
        "performance_metrics_computed": False,
        "private_output_sha256": sha256_file(private_path),
        "status": "Passed" if passed else "Failed",
        "summaries": summaries,
        "test_split_accessed": False,
        "validation_split_accessed": False,
    }
    atomic_json(output, report)
    update_run_stage(
        config,
        "smoke",
        report["status"],
        started_at,
        time.perf_counter() - started,
        output,
        accessed_split="train",
    )
    log_event(config, {"projected_seconds": projected, "stage": "smoke", "status": report["status"]})
    if not passed:
        raise RuntimeError("Train-only batch/runtime smoke failed")


def validate_resume_prefix(
    existing: Sequence[dict[str, Any]],
    rows: Sequence[dict[str, Any]],
    condition: str,
) -> None:
    if len(existing) > len(rows):
        raise ValueError("Private prediction file exceeds validation length")
    for index, record in enumerate(existing):
        if (
            record.get("condition") != condition
            or record.get("row_index") != index
            or record.get("sample_id") != rows[index]["sample_id"]
        ):
            raise ValueError("Existing private rows are not an exact resumable prefix")


def public_condition_summary(
    config: dict[str, Any],
    condition: str,
    records: Sequence[dict[str, Any]],
    private_path: Path,
    elapsed: float,
) -> dict[str, Any]:
    labels = config["data"]["labels"]
    batch_records: dict[int, dict[str, Any]] = {}
    for record in records:
        batch_records.setdefault(record["batch_index"], record["batch_stats"])
    batches = list(batch_records.values())
    total_batch_elapsed = sum(row["batch_elapsed_seconds"] for row in batches)
    valid = sum(record["parse"]["valid"] for record in records)
    return {
        "accessed_splits": ["validation"],
        "completed_at_utc": utc_now(),
        "condition": condition,
        "experiment_id": config["experiment_id"],
        "generation": {
            "batch_elapsed_seconds": numeric_summary([row["batch_elapsed_seconds"] for row in batches]),
            "batch_size": config["generation"]["batch_size"],
            "batches": len(batches),
            "generated_tokens": numeric_summary([record["generated_tokens"] for record in records]),
            "peak_memory_gb_max": max(row["peak_memory"] for row in batches),
            "prompt_tokens": numeric_summary([record["prompt_tokens"] for record in records]),
            "command_elapsed_seconds": elapsed,
            "total_batch_elapsed_seconds": total_batch_elapsed,
            "total_generation_tokens": sum(row["generation_tokens"] for row in batches),
            "total_prompt_tokens": sum(row["prompt_tokens"] for row in batches),
        },
        "metrics": metrics_by_slice(records, labels),
        "parser": {
            "error_counts": dict(sorted(Counter(record["parse"]["error"] for record in records if record["parse"]["error"]).items())),
            "likely_truncated_count": sum(record["likely_truncated"] for record in records),
            "valid_count": valid,
            "valid_rate": valid / len(records),
        },
        "private_predictions_sha256": sha256_file(private_path),
        "reasoning": config["conditions"][condition]["reasoning"],
        "rows": len(records),
        "status": "Passed",
        "test_split_accessed": False,
        "validation_split_accessed": True,
        "view": config["conditions"][condition]["view"],
    }


def infer(config: dict[str, Any], condition: str) -> None:
    started_at, started = utc_now(), time.perf_counter()
    run = load_run(config)
    if run["stages"].get("smoke", {}).get("status") != "Passed":
        raise RuntimeError("Smoke must pass before formal validation")
    output = run_dir(config) / f"condition-{condition}.json"
    if output.exists():
        raise FileExistsError(output)
    rows = load_rows(config, "validation")
    spec = config["conditions"][condition]
    prompt = load_prompt(config)
    private_path = private_root(config) / f"condition-{condition}-predictions.jsonl"
    existing = read_jsonl(private_path) if private_path.exists() else []
    validate_resume_prefix(existing, rows, condition)
    model, tokenizer, batch_generate, sampler = load_model_runtime(config)
    batch_size = config["generation"]["batch_size"]
    for start_index in range(len(existing), len(rows), batch_size):
        batch_rows = rows[start_index : start_index + batch_size]
        messages = [prompt_messages(config, prompt, row, spec["view"]) for row in batch_rows]
        texts, prompts, batch_stats = generate_one_batch(
            config,
            model,
            tokenizer,
            batch_generate,
            sampler,
            messages,
            spec["reasoning"],
        )
        batch_index = start_index // batch_size
        private_records = []
        for offset, (row, text, prompt_ids) in enumerate(zip(batch_rows, texts, prompts)):
            parsed = parse_final_label(text, thinking=spec["reasoning"], labels=config["data"]["labels"])
            generated_tokens = len(tokenizer.encode(text, add_special_tokens=False))
            private_records.append(
                {
                    "batch_index": batch_index,
                    "batch_stats": batch_stats,
                    "condition": condition,
                    "context_available": bool(row["context_available"]),
                    "generated_tokens": generated_tokens,
                    "gold_label": row["label"],
                    "likely_truncated": generated_tokens >= config["generation"]["max_new_tokens"] - 2,
                    "message_sha256": messages_sha256(messages[offset]),
                    "parse": parsed.to_dict(),
                    "prediction": parsed.label if parsed.valid else config["evaluation"]["invalid_label"],
                    "prompt_tokens": len(prompt_ids),
                    "raw_output": text,
                    "reasoning": spec["reasoning"],
                    "row_index": start_index + offset,
                    "sample_id": row["sample_id"],
                    "view": spec["view"],
                }
            )
        append_private_jsonl(private_path, private_records)
        completed = start_index + len(private_records)
        log_event(
            config,
            {
                "batch": batch_index + 1,
                "completed": completed,
                "condition": condition,
                "stage": "infer",
                "total": len(rows),
            },
        )
    records = read_jsonl(private_path)
    validate_resume_prefix(records, rows, condition)
    if len(records) != len(rows):
        raise RuntimeError("Formal condition did not complete all validation rows")
    elapsed = time.perf_counter() - started
    summary = public_condition_summary(config, condition, records, private_path, elapsed)
    atomic_json(output, summary)
    update_run_stage(
        config,
        f"condition_{condition}",
        "Passed",
        started_at,
        elapsed,
        output,
        accessed_split="validation",
    )
    log_event(
        config,
        {
            "condition": condition,
            "macro_f1": summary["metrics"]["all"]["macro_f1"],
            "parser_valid_rate": summary["parser"]["valid_rate"],
            "stage": "infer",
            "status": "Passed",
        },
    )


def bootstrap_factorial(
    records: dict[str, Sequence[dict[str, Any]]],
    labels: Sequence[str],
    repeats: int,
    seed_namespace: str,
) -> dict[str, Any]:
    gold = [row["gold_label"] for row in records["A"]]
    predictions = {condition: [row["prediction"] for row in values] for condition, values in records.items()}
    observed_scores = {condition: macro_f1(gold, values, labels) for condition, values in predictions.items()}
    observed_effects = factorial_effects(observed_scores)
    randomizer = random.Random(int(sha256_text(seed_namespace)[:16], 16))
    distributions = {name: [] for name in observed_effects}
    for _ in range(repeats):
        indices = [randomizer.randrange(len(gold)) for _ in gold]
        sampled_gold = [gold[index] for index in indices]
        sampled_scores = {
            condition: macro_f1(sampled_gold, [values[index] for index in indices], labels)
            for condition, values in predictions.items()
        }
        for name, value in factorial_effects(sampled_scores).items():
            distributions[name].append(value)
    return {
        name: {
            "ci95_percentile": [quantile(distributions[name], 0.025), quantile(distributions[name], 0.975)],
            "observed": observed,
        }
        for name, observed in observed_effects.items()
    }


def aggregate(config: dict[str, Any]) -> None:
    started_at, started = utc_now(), time.perf_counter()
    run = load_run(config)
    required = {f"condition_{name}" for name in config["conditions"]}
    if any(run["stages"].get(name, {}).get("status") != "Passed" for name in required):
        raise RuntimeError("All four formal conditions must pass before aggregate")
    output = run_dir(config) / "aggregate_metrics.json"
    if output.exists():
        raise FileExistsError(output)
    rows = load_rows(config, "validation")
    records: dict[str, list[dict[str, Any]]] = {}
    summaries: dict[str, dict[str, Any]] = {}
    for condition in config["conditions"]:
        private_path = private_root(config) / f"condition-{condition}-predictions.jsonl"
        records[condition] = read_jsonl(private_path)
        validate_resume_prefix(records[condition], rows, condition)
        if len(records[condition]) != len(rows):
            raise ValueError(f"Condition {condition} row count drift")
        summaries[condition] = json.loads((run_dir(config) / f"condition-{condition}.json").read_text(encoding="utf-8"))
    first_clause_indices = [index for index, row in enumerate(rows) if not row["context_available"]]
    prompt_match = {
        "reasoning_off_A_equals_B": all(
            records["A"][index]["message_sha256"] == records["B"][index]["message_sha256"]
            for index in first_clause_indices
        ),
        "reasoning_on_C_equals_D": all(
            records["C"][index]["message_sha256"] == records["D"][index]["message_sha256"]
            for index in first_clause_indices
        ),
    }
    if not all(prompt_match.values()):
        raise RuntimeError("First-clause paired prompts are not identical")
    off_raw_equal = sum(
        records["A"][index]["raw_output"] == records["B"][index]["raw_output"]
        for index in first_clause_indices
    )
    on_raw_equal = sum(
        records["C"][index]["raw_output"] == records["D"][index]["raw_output"]
        for index in first_clause_indices
    )
    first_clause_exact = {
        "prediction_equal_count_reasoning_off": sum(
            records["A"][index]["prediction"] == records["B"][index]["prediction"]
            for index in first_clause_indices
        ),
        "prediction_equal_count_reasoning_on": sum(
            records["C"][index]["prediction"] == records["D"][index]["prediction"]
            for index in first_clause_indices
        ),
        "prompt_hash_match": prompt_match,
        "raw_output_equal_count_reasoning_off": off_raw_equal,
        "raw_output_equal_count_reasoning_on": on_raw_equal,
        "raw_output_equal_rate_reasoning_off": off_raw_equal / len(first_clause_indices),
        "raw_output_equal_rate_reasoning_on": on_raw_equal / len(first_clause_indices),
        "rows": len(first_clause_indices),
    }
    scores = {condition: summaries[condition]["metrics"]["all"]["macro_f1"] for condition in config["conditions"]}
    durations = {
        condition: summaries[condition]["generation"]["total_batch_elapsed_seconds"]
        for condition in config["conditions"]
    }
    formal_elapsed = sum(durations.values())
    if formal_elapsed > config["resource_budget"]["formal_wall_time_seconds_max"]:
        raise RuntimeError("Formal wall-time budget exceeded")
    selection = choose_condition(
        scores,
        config["conditions"],
        durations,
        config["evaluation"]["practical_tie_macro_f1"],
    )
    reference = json.loads(resolve_project_path(config["stage3_reference"]["aggregate_path"]).read_text(encoding="utf-8"))
    reference_value = reference["m2_primary_view_selection"]["target_mean_macro_f1"]
    if not math.isclose(reference_value, config["stage3_reference"]["target_only_macro_f1_mean"], abs_tol=1e-15):
        raise ValueError("EXP-042 reference value drift")
    bootstrap = bootstrap_factorial(
        records,
        config["data"]["labels"],
        config["evaluation"]["bootstrap_repeats"],
        config["evaluation"]["bootstrap_seed_namespace"],
    )
    aggregate_report = {
        "completed_at_utc": utc_now(),
        "condition_metrics": {condition: summaries[condition]["metrics"] for condition in config["conditions"]},
        "conditions": config["conditions"],
        "experiment_id": config["experiment_id"],
        "factorial_effects": bootstrap,
        "first_clause_determinism": first_clause_exact,
        "generation_and_parser": {
            condition: {"generation": summaries[condition]["generation"], "parser": summaries[condition]["parser"]}
            for condition in config["conditions"]
        },
        "qwen_vs_exp042_m2_target": {
            "delta_macro_f1": selection["selected_macro_f1"] - reference_value,
            "exp042_macro_f1_mean": reference_value,
            "qwen_condition": selection["selected_condition"],
            "qwen_macro_f1": selection["selected_macro_f1"],
            "scope": "descriptive validation comparison; no cross-model significance claim",
        },
        "resource_usage": {
            "api_cost_usd": 0,
            "formal_elapsed_seconds": formal_elapsed,
            "formal_generations": sum(summary["rows"] for summary in summaries.values()),
            "peak_memory_gb_max": max(summary["generation"]["peak_memory_gb_max"] for summary in summaries.values()),
        },
        "selection": selection,
        "status": "AwaitingIndependentVerification",
        "test_split_accessed": False,
        "validation_split_accessed": True,
    }
    atomic_json(output, aggregate_report)
    report_lines = [
        "# EXP-043 Frozen Qwen 2x2 Results",
        "",
        "Status: Awaiting independent verification.",
        "",
        "| Condition | View | Reasoning | Macro-F1 | Accuracy | Parser valid |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for condition, spec in config["conditions"].items():
        summary = summaries[condition]
        report_lines.append(
            f"| {condition} | {spec['view']} | {str(spec['reasoning']).lower()} | "
            f"{summary['metrics']['all']['macro_f1']:.6f} | {summary['metrics']['all']['accuracy']:.6f} | "
            f"{summary['parser']['valid_rate']:.6f} |"
        )
    report_lines.extend(
        [
            "",
            f"Frozen Qwen condition: `{selection['selected_condition']}`.",
            f"Selected Qwen minus EXP-042 M2 target-only Macro-F1: "
            f"`{selection['selected_macro_f1'] - reference_value:+.6f}`.",
            "",
            "These are validation results. The sealed test split was not accessed.",
            "",
        ]
    )
    (run_dir(config) / "REPORT.md").write_text("\n".join(report_lines), encoding="utf-8")
    elapsed = time.perf_counter() - started
    update_run_stage(config, "aggregate", "Passed", started_at, elapsed, output, accessed_split="validation")
    run = load_run(config)
    run["status"] = "AwaitingIndependentVerification"
    run["test_split_accessed"] = False
    save_run(config, run)
    log_event(
        config,
        {
            "selected_condition": selection["selected_condition"],
            "stage": "aggregate",
            "status": "AwaitingIndependentVerification",
        },
    )


def mark_failed(config: dict[str, Any], error: Exception) -> None:
    path = run_dir(config) / "run.json"
    if not path.exists():
        return
    run = json.loads(path.read_text(encoding="utf-8"))
    run["failure"] = {"at_utc": utc_now(), "message": str(error), "type": type(error).__name__}
    run["status"] = "Failed"
    atomic_json(path, run)


def main() -> None:
    args = parse_args()
    config = load_config()
    try:
        if args.command == "initialize":
            initialize(config)
        elif args.command == "smoke":
            smoke(config)
        elif args.command == "infer":
            infer(config, args.condition)
        elif args.command == "aggregate":
            aggregate(config)
        else:
            raise ValueError(args.command)
    except Exception as error:
        mark_failed(config, error)
        raise


if __name__ == "__main__":
    main()
