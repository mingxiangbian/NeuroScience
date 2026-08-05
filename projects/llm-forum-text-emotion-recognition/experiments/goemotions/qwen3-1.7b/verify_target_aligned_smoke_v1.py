#!/usr/bin/env python3
"""Independently verify the EXP-033 target-aligned LoRA train-only smoke."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
from typing import Any

import numpy as np
from safetensors import safe_open


EXPERIMENT_ID = "EXP-033"
VERIFICATION_ID = "EXP-033-SMOKE-VERIFY-V1"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
CONFIG_PATH = SCRIPT_DIR / "configs" / "exp-033-target-aligned-lora-v3.json"
TRAIN_LOG_PATTERN = re.compile(
    r"Iter (?P<iteration>\d+): Train loss (?P<loss>[^,]+), "
    r"Learning Rate (?P<learning_rate>[^,]+), It/sec (?P<iterations_per_second>[^,]+), "
    r"Tokens/sec (?P<tokens_per_second>[^,]+), Trained Tokens (?P<trained_tokens>\d+), "
    r"Peak mem (?P<peak_memory_gb>[^ ]+) GB"
)
TRAINABLE_PATTERN = re.compile(
    r"Trainable parameters: (?P<percent>[^%]+)% "
    r"\((?P<trainable>[^M]+)M/(?P<total>[^M]+)M\)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "bytes": path.stat().st_size,
        "path": display_path(path),
        "sha256": sha256_file(path),
    }


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def require_equal(observed: Any, expected: Any, message: str) -> None:
    if observed != expected:
        raise ValueError(f"{message}: observed={observed!r}, expected={expected!r}")


def require_close(observed: float, expected: float, message: str) -> None:
    if not math.isclose(observed, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"{message}: observed={observed}, expected={expected}")


def load_config() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    if (
        config.get("experiment_id") != EXPERIMENT_ID
        or config.get("status") != "Registered"
        or config.get("tier") != "Major"
        or config["authorization_contract"].get("formal_training_enabled") is not False
    ):
        raise ValueError("Unexpected EXP-033 V3 registration identity")
    runner_path = resolve_project_path(config["implementation"]["runner_path"])
    verifier_path = resolve_project_path(config["implementation"]["verifier_path"])
    require_equal(
        sha256_file(runner_path),
        config["implementation"]["runner_sha256"],
        "Runner hash drift",
    )
    require_equal(
        sha256_file(verifier_path),
        config["implementation"]["verifier_sha256"],
        "Dry-run verifier hash drift",
    )
    protocol = config["artifacts"]["protocol"]
    require_equal(
        sha256_file(resolve_project_path(protocol["path"])),
        protocol["sha256"],
        "Protocol hash drift",
    )
    return config


def verify_authorization(
    config: dict[str, Any], report: dict[str, Any], runtime_path: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    authorization_path = resolve_project_path(report["authorization"]["path"])
    require_equal(report["authorization"], artifact(authorization_path), "Authorization artifact drift")
    authorization = load_json(authorization_path)
    dry_path = resolve_project_path(authorization["dry_run_verification_path"])
    dry_artifact = artifact(dry_path)
    dry_report = load_json(dry_path)
    expected = {
        "authorized": True,
        "config_sha256": sha256_file(CONFIG_PATH),
        "dry_run_verification_id": "EXP-033-RUNNER-DRY-RUN-VERIFY-V3",
        "dry_run_verification_path": display_path(dry_path),
        "dry_run_verification_sha256": dry_artifact["sha256"],
        "experiment_id": EXPERIMENT_ID,
        "runtime_config_path": display_path(runtime_path),
        "runtime_config_sha256": sha256_file(runtime_path),
        "stage": "train-only-smoke",
    }
    for key, value in expected.items():
        require_equal(authorization.get(key), value, f"Authorization binding drift: {key}")
    require_equal(
        authorization.get("scope"),
        {"formal_training": False, "test_split": False, "validation_split": False},
        "Authorization scope drift",
    )
    if (
        dry_report.get("status") != "Passed"
        or dry_report.get("formal_training_authorized") is not False
        or dry_report.get("smoke_training_authorized") is not False
        or dry_report.get("model_forward_or_backward_executed") is not False
        or dry_report.get("validation_split_accessed") is not False
        or dry_report.get("test_split_accessed") is not False
    ):
        raise ValueError("Bound dry-run verification no longer satisfies its execution boundary")
    return authorization, dry_artifact


def verify_runtime(
    config: dict[str, Any], report: dict[str, Any]
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    runtime_path = resolve_project_path(config["artifacts"]["smoke_runtime_config"])
    require_equal(report["runtime_config"], artifact(runtime_path), "Runtime artifact drift")
    runtime = load_json(runtime_path)
    contract_spec = config["runtime"]["canonical_contract"]
    contract_path = resolve_project_path(contract_spec["path"])
    require_equal(sha256_file(contract_path), contract_spec["sha256"], "Runtime contract drift")
    contract = load_json(contract_path)
    require_equal(runtime, contract["effective_configs"]["smoke"], "Smoke runtime contract drift")
    if (
        runtime.get("train") is not True
        or runtime.get("test") is not False
        or runtime.get("val_batches") != 0
        or runtime.get("test_batches") != 0
        or runtime.get("iters") != config["preflight"]["smoke_iterations"]
        or runtime.get("seed") != 42
    ):
        raise ValueError("Smoke runtime is not the frozen train-only seed-42 condition")
    data_dir = Path(runtime["data"])
    require_equal(
        sorted(path.name for path in data_dir.iterdir()),
        ["train.jsonl"],
        "Smoke runtime directory is not train-only",
    )
    adapter_config_path = resolve_project_path(report["adapter"]["config"]["path"])
    require_equal(
        report["adapter"]["config"],
        artifact(adapter_config_path),
        "Adapter config artifact drift",
    )
    adapter_config = load_json(adapter_config_path)
    expected_adapter_config = {**runtime, "config": str(runtime_path)}
    require_equal(adapter_config, expected_adapter_config, "Saved adapter config drift")
    return runtime_path, runtime, artifact(contract_path)


def verify_smoke_data(config: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    label_spec = config["data"]["labels"]
    label_path = resolve_project_path(label_spec["path"])
    require_equal(sha256_file(label_path), label_spec["sha256"], "Label ontology hash drift")
    labels = tuple(line.strip() for line in label_path.read_text(encoding="utf-8").splitlines())
    require_equal(len(labels), label_spec["count"], "Label count drift")
    if len(labels) != len(set(labels)):
        raise ValueError("Label ontology contains duplicates")
    label_ids = {label: index for index, label in enumerate(labels)}

    spec = config["data"]["smoke_train"]
    path = resolve_project_path(spec["path"])
    require_equal(sha256_file(path), spec["sha256"], "Smoke data hash drift")
    cardinality: Counter[int] = Counter()
    support: Counter[str] = Counter()
    target_stream = hashlib.sha256()
    neutral_cooccurrence = 0
    rows = 0
    with path.open("r", encoding="utf-8") as source:
        for row_number, line in enumerate(source, start=1):
            rows = row_number
            record = json.loads(line)
            require_equal(set(record), {"messages"}, f"Smoke row {row_number} keys drift")
            messages = record["messages"]
            if (
                not isinstance(messages, list)
                or len(messages) != 3
                or [message.get("role") for message in messages]
                != ["system", "user", "assistant"]
            ):
                raise ValueError(f"Smoke row {row_number} message schema drift")
            target = messages[-1]["content"]
            parsed = json.loads(target)
            if set(parsed) != {"labels"} or not isinstance(parsed["labels"], list):
                raise ValueError(f"Smoke row {row_number} target schema drift")
            target_labels = parsed["labels"]
            if (
                not target_labels
                or len(target_labels) != len(set(target_labels))
                or any(label not in label_ids for label in target_labels)
            ):
                raise ValueError(f"Smoke row {row_number} target labels drift")
            ids = [label_ids[label] for label in target_labels]
            require_equal(ids, sorted(ids), f"Smoke row {row_number} target order drift")
            canonical = json.dumps(
                {"labels": target_labels}, separators=(",", ":"), ensure_ascii=True
            )
            require_equal(target, canonical, f"Smoke row {row_number} target serialization drift")
            cardinality[len(target_labels)] += 1
            support.update(target_labels)
            neutral_cooccurrence += int("neutral" in target_labels and len(target_labels) > 1)
            target_stream.update(
                f"{row_number}\t{','.join(map(str, ids))}\t{target}\n".encode("utf-8")
            )

    observed = {
        "cardinality_support": {str(key): cardinality[key] for key in sorted(cardinality)},
        "covers_all_labels": set(support) == set(labels),
        "label_support": dict(sorted(support.items())),
        "max_target_cardinality": max(cardinality),
        "neutral_cooccurrence_rows": neutral_cooccurrence,
        "path": display_path(path),
        "rows": rows,
        "sha256": spec["sha256"],
        "target_stream_sha256": target_stream.hexdigest(),
    }
    require_equal(rows, spec["rows"], "Smoke row count drift")
    require_equal(
        neutral_cooccurrence,
        spec["neutral_cooccurrence_rows"],
        "Smoke neutral co-occurrence drift",
    )
    require_equal(
        observed["max_target_cardinality"],
        spec["max_target_cardinality"],
        "Smoke cardinality boundary drift",
    )
    require_equal(observed["covers_all_labels"], True, "Smoke label coverage drift")
    require_equal(report["data"], observed, "Smoke data report drift")

    test_spec = config["data"]["test"]
    test_path = resolve_project_path(test_spec["path"])
    if test_spec.get("must_be_absent") is not True or test_path.exists():
        raise ValueError("Test-absence gate failed during smoke verification")
    return observed


def parse_log(path: Path) -> tuple[list[dict[str, Any]], dict[str, float]]:
    history: list[dict[str, Any]] = []
    trainable: dict[str, float] | None = None
    text = path.read_text(encoding="utf-8")
    if "Traceback" in text or "out of memory" in text.lower():
        raise ValueError("Training stdout contains an exception or OOM marker")
    for line in text.splitlines():
        match = TRAIN_LOG_PATTERN.search(line)
        if match:
            row: dict[str, Any] = {
                "iteration": int(match.group("iteration")),
                "train_loss": float(match.group("loss")),
                "learning_rate": float(match.group("learning_rate")),
                "iterations_per_second": float(match.group("iterations_per_second")),
                "tokens_per_second": float(match.group("tokens_per_second")),
                "trained_tokens": int(match.group("trained_tokens")),
                "peak_memory_gb": float(match.group("peak_memory_gb")),
            }
            history.append(row)
        trainable_match = TRAINABLE_PATTERN.search(line)
        if trainable_match:
            trainable = {
                "percent": float(trainable_match.group("percent")),
                "total_millions": float(trainable_match.group("total")),
                "trainable_millions": float(trainable_match.group("trainable")),
            }
    if not history or trainable is None:
        raise ValueError("Training stdout is missing history or trainable-parameter output")
    return history, trainable


def verify_history(
    config: dict[str, Any], report: dict[str, Any], runtime: dict[str, Any]
) -> dict[str, Any]:
    stdout_path = resolve_project_path(config["artifacts"]["smoke_stdout"])
    history_path = resolve_project_path(config["artifacts"]["smoke_history"])
    require_equal(report["stdout"], artifact(stdout_path), "Smoke stdout artifact drift")
    require_equal(report["history"], artifact(history_path), "Smoke history artifact drift")
    stdout_history, trainable = parse_log(stdout_path)
    with history_path.open("r", encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    typed_history: list[dict[str, Any]] = []
    for row in rows:
        typed = {
            "iteration": int(row["iteration"]),
            "train_loss": float(row["train_loss"]),
            "learning_rate": float(row["learning_rate"]),
            "iterations_per_second": float(row["iterations_per_second"]),
            "tokens_per_second": float(row["tokens_per_second"]),
            "trained_tokens": int(row["trained_tokens"]),
            "peak_memory_gb": float(row["peak_memory_gb"]),
        }
        numeric = [value for key, value in typed.items() if key not in {"iteration", "trained_tokens"}]
        if not all(math.isfinite(float(value)) for value in numeric):
            raise ValueError("Smoke history contains a non-finite value")
        typed_history.append(typed)
    require_equal(typed_history, stdout_history, "CSV and stdout history differ")
    report_every = int(runtime["steps_per_report"])
    expected_iterations = list(range(report_every, int(runtime["iters"]) + 1, report_every))
    require_equal(
        [row["iteration"] for row in typed_history],
        expected_iterations,
        "Smoke reporting iterations drift",
    )
    if any(row["iterations_per_second"] <= 0 or row["tokens_per_second"] <= 0 for row in typed_history):
        raise ValueError("Smoke throughput is non-positive")
    if any(
        later["trained_tokens"] <= earlier["trained_tokens"]
        for earlier, later in zip(typed_history, typed_history[1:])
    ):
        raise ValueError("Smoke trained-token count is not strictly increasing")
    if any(row["learning_rate"] != float(runtime["learning_rate"]) for row in typed_history):
        raise ValueError("Smoke learning rate differs from the frozen runtime")

    initial_window = statistics.mean(row["train_loss"] for row in typed_history[:2])
    final_window = statistics.mean(row["train_loss"] for row in typed_history[-2:])
    median_rate = statistics.median(row["iterations_per_second"] for row in typed_history)
    projected_hours = int(config["training"]["iterations"]) / median_rate / 3600
    peak_memory = max(row["peak_memory_gb"] for row in typed_history)
    require_close(float(report["initial_loss_window"]), initial_window, "Initial loss window drift")
    require_close(float(report["final_loss_window"]), final_window, "Final loss window drift")
    require_close(
        float(report["median_iterations_per_second"]),
        median_rate,
        "Median throughput drift",
    )
    require_close(
        float(report["projected_formal_training_hours"]),
        projected_hours,
        "Projected formal runtime drift",
    )
    require_close(float(report["peak_mlx_memory_gb"]), peak_memory, "Peak memory drift")
    require_equal(report["trainable_parameters_reported"], trainable, "Trainable report drift")
    if final_window > initial_window * 1.25:
        raise ValueError("Smoke loss gate failed")
    if projected_hours > float(config["resource_budget"]["training_wall_time_hours_max_per_seed"]):
        raise ValueError("Projected formal runtime exceeds the registered budget")
    if peak_memory > float(config["resource_budget"]["peak_mlx_memory_gb_max"]):
        raise ValueError("Smoke peak memory exceeds the registered budget")
    duration_seconds = float(report["duration_seconds"])
    if (
        not math.isfinite(duration_seconds)
        or duration_seconds <= 0
        or duration_seconds > float(config["preflight"]["smoke_wall_time_minutes_max"]) * 60
    ):
        raise ValueError("Smoke duration exceeds the registered wall-time budget")
    return {
        "duration_seconds": duration_seconds,
        "final_loss_window": final_window,
        "initial_loss_window": initial_window,
        "median_iterations_per_second": median_rate,
        "micro_iterations": int(runtime["iters"]),
        "optimizer_updates": int(runtime["iters"]) // int(runtime["grad_accumulation_steps"]),
        "peak_mlx_memory_gb": peak_memory,
        "projected_formal_training_hours": projected_hours,
        "reporting_rows": len(typed_history),
        "trainable_parameters_reported": trainable,
    }


def verify_adapter(config: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    weights_path = resolve_project_path(report["adapter"]["weights"]["path"])
    require_equal(report["adapter"]["weights"], artifact(weights_path), "Adapter weights drift")
    expected_layers = set(config["training"]["lora"]["adapted_block_indices"])
    expected_modules = set(config["training"]["lora"]["target_modules"])
    expected_keys = {
        f"model.layers.{layer}.{module}.lora_{suffix}"
        for layer in expected_layers
        for module in expected_modules
        for suffix in ("a", "b")
    }
    tensor_count = 0
    trainable_parameters = 0
    b_tensor_count = 0
    b_nonzero_count = 0
    with safe_open(weights_path, framework="numpy") as handle:
        keys = set(handle.keys())
        require_equal(keys, expected_keys, "Adapter tensor key set drift")
        for key in sorted(keys):
            tensor = handle.get_tensor(key)
            tensor_count += 1
            trainable_parameters += int(tensor.size)
            if not np.isfinite(tensor).all():
                raise ValueError(f"Adapter tensor is non-finite: {key}")
            if key.endswith("lora_b"):
                b_tensor_count += 1
                b_nonzero_count += int(np.any(tensor != 0))
    observed = {
        "lora_b_nonzero_tensors": b_nonzero_count,
        "lora_b_tensor_count": b_tensor_count,
        "tensor_count": tensor_count,
        "trainable_parameter_count": trainable_parameters,
    }
    expected = {
        key: report["adapter"][key]
        for key in (
            "lora_b_nonzero_tensors",
            "lora_b_tensor_count",
            "tensor_count",
            "trainable_parameter_count",
        )
    }
    require_equal(observed, expected, "Adapter summary drift")
    require_equal(
        trainable_parameters,
        config["preflight"]["expected_trainable_parameters"],
        "Adapter trainable-parameter count drift",
    )
    require_equal(b_nonzero_count, b_tensor_count, "At least one LoRA B tensor remained zero")
    return {**observed, "weights": artifact(weights_path)}


def build_verification(config: dict[str, Any]) -> dict[str, Any]:
    report_path = resolve_project_path(config["artifacts"]["smoke_report"])
    report = load_json(report_path)
    if (
        report.get("experiment_id") != EXPERIMENT_ID
        or report.get("stage") != "train-only-smoke"
        or report.get("status") != "Passed"
        or report.get("tier") != "Minor preflight"
        or report.get("seed") != 42
        or report.get("accessed_splits") != ["train"]
        or report.get("validation_split_accessed") is not False
        or report.get("test_split_accessed") is not False
    ):
        raise ValueError("Smoke report execution-boundary fields are invalid")
    require_equal(report["config"], artifact(CONFIG_PATH), "Smoke config artifact drift")
    runtime_path, runtime, runtime_contract = verify_runtime(config, report)
    _, dry_verification = verify_authorization(config, report, runtime_path)
    data = verify_smoke_data(config, report)
    history = verify_history(config, report, runtime)
    adapter = verify_adapter(config, report)
    return {
        "accessed_splits": ["train"],
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": EXPERIMENT_ID,
        "formal_training_authorized": False,
        "implementation": {
            "imports_runner": False,
            "verifier": artifact(Path(__file__).resolve()),
        },
        "next_required_step": (
            "Freeze this smoke verification into a new formal-execution runner contract, "
            "then obtain separate authorization before seed-42 formal training."
        ),
        "recalculated": {
            "adapter": adapter,
            "authorization": report["authorization"],
            "data": data,
            "dry_run_verification": dry_verification,
            "history": history,
            "runtime_config": artifact(runtime_path),
            "runtime_contract": runtime_contract,
            "smoke_report": artifact(report_path),
        },
        "smoke_training_authorized": True,
        "status": "Passed",
        "test_split_absent": True,
        "test_split_accessed": False,
        "validation_split_accessed": False,
        "verification_id": VERIFICATION_ID,
    }


def check_existing(expected: dict[str, Any], path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    existing = load_json(path)
    expected["completed_at_utc"] = existing.get("completed_at_utc")
    require_equal(existing, expected, "Stored smoke verification differs from recomputation")


def main() -> None:
    args = parse_args()
    config = load_config()
    verification_path = resolve_project_path(config["artifacts"]["smoke_verification"])
    verification = build_verification(config)
    if args.check:
        check_existing(verification, verification_path)
        print(json.dumps({"path": display_path(verification_path), "status": "Passed"}, indent=2))
        return
    if verification_path.exists():
        raise FileExistsError(verification_path)
    write_json(verification_path, verification)
    print(json.dumps(verification, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
