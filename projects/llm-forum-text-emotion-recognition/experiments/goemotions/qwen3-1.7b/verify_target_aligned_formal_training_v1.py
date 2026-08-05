#!/usr/bin/env python3
"""Independently verify the EXP-033 seed-42 train-only formal run."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys
from typing import Any

import numpy as np
from safetensors import safe_open


os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["PYTHONNOUSERSITE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_OFFLINE"] = "1"


EXPERIMENT_ID = "EXP-033"
GATE_ID = "EXP-033-FORMAL-GATE-V1"
VERIFICATION_ID = "EXP-033-FORMAL-TRAIN-VERIFY-V1"
STAGE = "formal-seed-42"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
CONTRACT_PATH = SCRIPT_DIR / "preflight" / "exp-033-formal-gate-contract-v1.json"
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


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def require_equal(observed: Any, expected: Any, message: str) -> None:
    if observed != expected:
        raise ValueError(f"{message}: observed={observed!r}, expected={expected!r}")


def require_close(observed: float, expected: float, message: str) -> None:
    if not math.isclose(observed, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"{message}: observed={observed}, expected={expected}")


def verify_spec(spec: dict[str, Any]) -> dict[str, Any]:
    path = resolve_project_path(spec["path"])
    observed = artifact(path)
    require_equal(observed["sha256"], spec["sha256"], "Frozen artifact hash drift")
    if "bytes" in spec:
        require_equal(observed["bytes"], int(spec["bytes"]), "Frozen artifact size drift")
    return observed


def load_contract() -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    if (
        contract.get("contract_id") != GATE_ID
        or contract.get("experiment_id") != EXPERIMENT_ID
        or contract.get("stage") != STAGE
        or contract.get("formal_training_enabled") is not True
        or contract.get("seed") != 42
    ):
        raise ValueError("Unexpected EXP-033 formal gate identity")
    implementation = contract["implementation"]
    verifier = resolve_project_path(implementation["training_verifier"]["path"])
    require_equal(verifier, Path(__file__).resolve(), "Formal training verifier path drift")
    for spec in implementation.values():
        verify_spec(spec)
    for spec in contract["frozen_artifacts"].values():
        verify_spec(spec)
    python = Path(contract["runtime"]["python_executable"])
    if not python.is_file() or not Path(sys.executable).samefile(python):
        raise ValueError("Formal training verifier is not running in the frozen environment")
    return contract


def verify_authorization(
    contract: dict[str, Any], report: dict[str, Any]
) -> dict[str, Any]:
    authorization_path = resolve_project_path(report["authorization"]["path"])
    require_equal(report["authorization"], artifact(authorization_path), "Authorization artifact drift")
    authorization = load_json(authorization_path)
    gate_path = resolve_project_path(contract["outputs"]["gate_verification"])
    smoke_path = resolve_project_path(
        contract["frozen_artifacts"]["smoke_verification"]["path"]
    )
    runtime_path = resolve_project_path(
        contract["frozen_artifacts"]["formal_runtime"]["path"]
    )
    config_path = resolve_project_path(contract["frozen_artifacts"]["config_v3"]["path"])
    expected = {
        "authorized": True,
        "config_path": display_path(config_path),
        "config_sha256": sha256_file(config_path),
        "contract_id": GATE_ID,
        "contract_path": display_path(CONTRACT_PATH),
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "experiment_id": EXPERIMENT_ID,
        "gate_verification_id": "EXP-033-FORMAL-GATE-VERIFY-V1",
        "gate_verification_path": display_path(gate_path),
        "gate_verification_sha256": sha256_file(gate_path),
        "runtime_config_path": display_path(runtime_path),
        "runtime_config_sha256": sha256_file(runtime_path),
        "smoke_verification_id": "EXP-033-SMOKE-VERIFY-V1",
        "smoke_verification_path": display_path(smoke_path),
        "smoke_verification_sha256": sha256_file(smoke_path),
        "stage": STAGE,
    }
    for key, value in expected.items():
        require_equal(authorization.get(key), value, f"Authorization binding drift: {key}")
    require_equal(
        authorization.get("scope"),
        {"seeds": [42], "test_split": False, "train": True, "validation_split": False},
        "Authorization scope drift",
    )
    gate = load_json(gate_path)
    if (
        gate.get("verification_id") != "EXP-033-FORMAL-GATE-VERIFY-V1"
        or gate.get("status") != "Passed"
        or gate.get("formal_training_authorized") is not False
        or gate.get("validation_split_accessed") is not False
        or gate.get("test_split_accessed") is not False
    ):
        raise ValueError("Bound formal gate verification is invalid")
    smoke = load_json(smoke_path)
    if (
        smoke.get("verification_id") != "EXP-033-SMOKE-VERIFY-V1"
        or smoke.get("status") != "Passed"
        or smoke.get("validation_split_accessed") is not False
        or smoke.get("test_split_accessed") is not False
    ):
        raise ValueError("Bound smoke verification is invalid")
    return artifact(authorization_path)


def verify_runtime(
    contract: dict[str, Any], report: dict[str, Any]
) -> tuple[Path, dict[str, Any]]:
    runtime_path = resolve_project_path(
        contract["frozen_artifacts"]["formal_runtime"]["path"]
    )
    require_equal(report["runtime_config"], artifact(runtime_path), "Runtime artifact drift")
    runtime = load_json(runtime_path)
    canonical_path = resolve_project_path(
        contract["frozen_artifacts"]["canonical_runtime_contract"]["path"]
    )
    canonical = load_json(canonical_path)
    require_equal(runtime, canonical["effective_configs"]["formal_seed_42"], "Runtime contract drift")
    observed = {
        "adapter_path": runtime.get("adapter_path"),
        "batch_size": runtime.get("batch_size"),
        "data": runtime.get("data"),
        "grad_accumulation_steps": runtime.get("grad_accumulation_steps"),
        "iters": runtime.get("iters"),
        "learning_rate": runtime.get("learning_rate"),
        "max_seq_length": runtime.get("max_seq_length"),
        "num_layers": runtime.get("num_layers"),
        "seed": runtime.get("seed"),
        "test": runtime.get("test"),
        "test_batches": runtime.get("test_batches"),
        "train": runtime.get("train"),
        "val_batches": runtime.get("val_batches"),
    }
    require_equal(observed, contract["formal_runtime_assertions"], "Formal runtime assertion drift")
    adapter_dir = resolve_project_path(contract["outputs"]["adapter_dir"])
    require_equal(
        Path(runtime["adapter_path"]).resolve(),
        adapter_dir,
        "Formal runtime adapter path differs from the contract output path",
    )
    data_dir = Path(runtime["data"])
    require_equal(
        sorted(path.name for path in data_dir.iterdir()),
        contract["training_data"]["directory_entries"],
        "Runtime data-directory inventory drift",
    )
    forbidden = [name for name in ("valid.jsonl", "dev.jsonl", "test.jsonl") if (data_dir / name).exists()]
    if forbidden:
        raise ValueError(f"Runtime data directory contains forbidden splits: {forbidden}")
    train_path = data_dir / "train.jsonl"
    require_equal(sha256_file(train_path), contract["training_data"]["sha256"], "Train hash drift")
    with train_path.open("r", encoding="utf-8") as source:
        rows = sum(1 for line in source if line.strip())
    require_equal(rows, int(contract["training_data"]["rows"]), "Train row-count drift")
    config_path = resolve_project_path(contract["frozen_artifacts"]["config_v3"]["path"])
    config = load_json(config_path)
    test_spec = contract["test_gate"]
    require_equal(test_spec, config["data"]["test"], "Formal test gate differs from frozen V3")
    test_path = resolve_project_path(test_spec["path"])
    if test_spec.get("must_be_absent") is not True or test_path.exists():
        raise ValueError("Test-absence gate failed")
    adapter_config_path = resolve_project_path(report["adapter"]["config"]["path"])
    require_equal(report["adapter"]["config"], artifact(adapter_config_path), "Adapter config drift")
    expected_adapter_config = {**runtime, "config": str(runtime_path)}
    require_equal(load_json(adapter_config_path), expected_adapter_config, "Saved adapter config drift")
    smoke_path = resolve_project_path(
        contract["frozen_artifacts"]["smoke_verification"]["path"]
    )
    cli = Path(contract["runtime"]["mlx_lora_cli"]["path"])
    expected_preconditions = {
        "config": artifact(config_path),
        "formal_runtime": artifact(runtime_path),
        "mlx_lora_cli": artifact(cli),
        "smoke_verification": artifact(smoke_path),
        "test_split_absent": True,
        "train_data": artifact(train_path),
    }
    require_equal(report["preconditions"], expected_preconditions, "Formal precondition report drift")
    return runtime_path, runtime


def verify_adapter_loadability(runtime: dict[str, Any], adapter_dir: Path) -> dict[str, Any]:
    import mlx.core as mx
    from mlx_lm import load

    mx.reset_peak_memory()
    model, tokenizer = load(
        str(runtime["model"]),
        adapter_path=str(adapter_dir),
        lazy=False,
    )
    token_ids = tokenizer.encode("Synthetic train-only adapter verification input.")
    if not token_ids:
        raise ValueError("Synthetic adapter verification input tokenized to an empty sequence")
    logits = model(mx.array([token_ids]))
    mx.eval(logits)
    if logits.ndim != 3 or logits.shape[0] != 1 or logits.shape[1] != len(token_ids):
        raise ValueError(f"Unexpected synthetic forward shape: {logits.shape}")
    if not bool(mx.all(mx.isfinite(logits)).item()):
        raise ValueError("Synthetic adapter forward produced non-finite logits")
    peak_memory = float(mx.get_peak_memory()) / 1e9
    return {
        "finite_logits": True,
        "input_tokens": len(token_ids),
        "logit_shape": [int(value) for value in logits.shape],
        "model_and_adapter_loaded": True,
        "peak_mlx_memory_gb": peak_memory,
    }


def parse_log(path: Path) -> tuple[list[dict[str, Any]], dict[str, float]]:
    history: list[dict[str, Any]] = []
    trainable: dict[str, float] | None = None
    contents = path.read_text(encoding="utf-8")
    if "Traceback" in contents or "out of memory" in contents.lower():
        raise ValueError("Formal stdout contains an exception or OOM marker")
    for line in contents.splitlines():
        match = TRAIN_LOG_PATTERN.search(line)
        if match:
            history.append(
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
        trainable_match = TRAINABLE_PATTERN.search(line)
        if trainable_match:
            trainable = {
                "percent": float(trainable_match.group("percent")),
                "total_millions": float(trainable_match.group("total")),
                "trainable_millions": float(trainable_match.group("trainable")),
            }
    if not history or trainable is None:
        raise ValueError("Formal stdout is missing history or trainable-parameter output")
    return history, trainable


def verify_history(
    contract: dict[str, Any], report: dict[str, Any], runtime: dict[str, Any], run_dir: Path
) -> dict[str, Any]:
    stdout_path = run_dir / "stdout.log"
    history_path = run_dir / "history.csv"
    require_equal(report["stdout"], artifact(stdout_path), "Formal stdout artifact drift")
    require_equal(report["history"], artifact(history_path), "Formal history artifact drift")
    stdout_history, trainable = parse_log(stdout_path)
    typed_history: list[dict[str, Any]] = []
    with history_path.open("r", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            typed = {
                "iteration": int(row["iteration"]),
                "train_loss": float(row["train_loss"]),
                "learning_rate": float(row["learning_rate"]),
                "iterations_per_second": float(row["iterations_per_second"]),
                "tokens_per_second": float(row["tokens_per_second"]),
                "trained_tokens": int(row["trained_tokens"]),
                "peak_memory_gb": float(row["peak_memory_gb"]),
            }
            numeric = [
                value for key, value in typed.items() if key not in {"iteration", "trained_tokens"}
            ]
            if not all(math.isfinite(float(value)) for value in numeric):
                raise ValueError("Formal history contains a non-finite value")
            typed_history.append(typed)
    require_equal(typed_history, stdout_history, "CSV and stdout history differ")
    report_every = int(runtime["steps_per_report"])
    final_iteration = int(runtime["iters"])
    expected_iterations = list(range(report_every, final_iteration + 1, report_every))
    if expected_iterations[-1] != final_iteration:
        expected_iterations.append(final_iteration)
    require_equal(
        [row["iteration"] for row in typed_history],
        expected_iterations,
        "Formal reporting iterations drift",
    )
    if any(row["iterations_per_second"] <= 0 or row["tokens_per_second"] <= 0 for row in typed_history):
        raise ValueError("Formal throughput is non-positive")
    if any(
        later["trained_tokens"] <= earlier["trained_tokens"]
        for earlier, later in zip(typed_history, typed_history[1:])
    ):
        raise ValueError("Formal trained-token count is not strictly increasing")
    if any(row["learning_rate"] != float(runtime["learning_rate"]) for row in typed_history):
        raise ValueError("Formal learning rate differs from the frozen runtime")
    require_equal(report["trainable_parameters_reported"], trainable, "Trainable report drift")
    peak_memory = max(row["peak_memory_gb"] for row in typed_history)
    require_close(float(report["peak_mlx_memory_gb"]), peak_memory, "Peak memory drift")
    if peak_memory > float(contract["resource_budget"]["peak_mlx_memory_gb_max"]):
        raise ValueError("Formal peak memory exceeds the registered budget")
    duration_seconds = float(report["duration_seconds"])
    if (
        not math.isfinite(duration_seconds)
        or duration_seconds <= 0
        or duration_seconds > float(contract["resource_budget"]["training_hours_max"]) * 3600
    ):
        raise ValueError("Formal duration exceeds the registered wall-time budget")
    return {
        "duration_seconds": duration_seconds,
        "final_loss_window": statistics.mean(row["train_loss"] for row in typed_history[-5:]),
        "initial_loss_window": statistics.mean(row["train_loss"] for row in typed_history[:5]),
        "median_iterations_per_second": statistics.median(
            row["iterations_per_second"] for row in typed_history
        ),
        "micro_iterations": final_iteration,
        "optimizer_updates": final_iteration // int(runtime["grad_accumulation_steps"]),
        "peak_mlx_memory_gb": peak_memory,
        "reporting_rows": len(typed_history),
        "trainable_parameters_reported": trainable,
        "trained_tokens": typed_history[-1]["trained_tokens"],
    }


def verify_adapter(
    contract: dict[str, Any], report: dict[str, Any], runtime: dict[str, Any], adapter_dir: Path
) -> dict[str, Any]:
    expected_files = {
        "adapter_config.json",
        "adapters.safetensors",
        *contract["expected_adapter"]["checkpoint_names"],
    }
    require_equal(
        {path.name for path in adapter_dir.iterdir()},
        expected_files,
        "Formal adapter directory contents drift",
    )
    weights_path = adapter_dir / "adapters.safetensors"
    require_equal(report["adapter"]["weights"], artifact(weights_path), "Adapter weights drift")
    expected_layers = set(range(28 - int(runtime["num_layers"]), 28))
    expected_modules = set(runtime["lora_parameters"]["keys"])
    expected_keys = {
        f"model.layers.{layer}.{module}.lora_{suffix}"
        for layer in expected_layers
        for module in expected_modules
        for suffix in ("a", "b")
    }
    tensor_count = 0
    parameter_count = 0
    b_count = 0
    b_nonzero = 0
    with safe_open(weights_path, framework="numpy") as handle:
        keys = set(handle.keys())
        require_equal(keys, expected_keys, "Adapter tensor key set drift")
        for key in sorted(keys):
            tensor = handle.get_tensor(key)
            if not np.isfinite(tensor).all():
                raise ValueError(f"Adapter tensor is non-finite: {key}")
            tensor_count += 1
            parameter_count += int(tensor.size)
            if key.endswith("lora_b"):
                b_count += 1
                b_nonzero += int(np.any(tensor != 0))
    observed = {
        "lora_b_nonzero_tensors": b_nonzero,
        "lora_b_tensor_count": b_count,
        "tensor_count": tensor_count,
        "trainable_parameter_count": parameter_count,
    }
    reported = {key: report["adapter"][key] for key in observed}
    require_equal(observed, reported, "Adapter summary drift")
    require_equal(parameter_count, int(contract["expected_adapter"]["trainable_parameter_count"]), "Adapter parameter-count drift")
    require_equal(tensor_count, int(contract["expected_adapter"]["tensor_count"]), "Adapter tensor-count drift")
    require_equal(b_count, int(contract["expected_adapter"]["lora_b_tensor_count"]), "LoRA B count drift")
    require_equal(b_nonzero, b_count, "At least one LoRA B tensor remained zero")

    checkpoint_artifacts = [artifact(adapter_dir / name) for name in contract["expected_adapter"]["checkpoint_names"]]
    require_equal(report["adapter"]["checkpoints"], checkpoint_artifacts, "Checkpoint artifact set drift")
    return {
        **observed,
        "checkpoints": checkpoint_artifacts,
        "config": artifact(adapter_dir / "adapter_config.json"),
        "weights": artifact(weights_path),
    }


def build_verification(contract: dict[str, Any]) -> dict[str, Any]:
    run_dir = resolve_project_path(contract["outputs"]["run_dir"])
    adapter_dir = resolve_project_path(contract["outputs"]["adapter_dir"])
    run_path = run_dir / "run.json"
    report = load_json(run_path)
    if (
        report.get("experiment_id") != EXPERIMENT_ID
        or report.get("stage") != STAGE
        or report.get("status") != "Completed; pending independent verification"
        or report.get("tier") != "Major"
        or report.get("seed") != 42
        or report.get("accessed_splits") != ["train"]
        or report.get("validation_split_accessed") is not False
        or report.get("test_split_accessed") is not False
    ):
        raise ValueError("Formal training execution-boundary fields are invalid")
    require_equal(report["contract"], artifact(CONTRACT_PATH), "Formal contract artifact drift")
    cli = Path(contract["runtime"]["mlx_lora_cli"]["path"])
    runtime_path, runtime = verify_runtime(contract, report)
    require_equal(report["command"], [str(cli), "-c", str(runtime_path)], "Formal command drift")
    authorization = verify_authorization(contract, report)
    history = verify_history(contract, report, runtime, run_dir)
    adapter = verify_adapter(contract, report, runtime, adapter_dir)
    loadability = verify_adapter_loadability(runtime, adapter_dir)
    if loadability["peak_mlx_memory_gb"] > float(
        contract["resource_budget"]["peak_mlx_memory_gb_max"]
    ):
        raise ValueError("Synthetic adapter load/forward exceeded the memory budget")
    expected_run_files = {"history.csv", "run.json", "stdout.log"}
    if (run_dir / "verification.json").exists():
        expected_run_files.add("verification.json")
    require_equal(
        set(path.name for path in run_dir.iterdir()),
        expected_run_files,
        "Formal run directory contains unexpected artifacts",
    )
    return {
        "accessed_splits": ["train"],
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract": artifact(CONTRACT_PATH),
        "experiment_id": EXPERIMENT_ID,
        "formal_training_verified": True,
        "implementation": {
            "imports_runner": False,
            "verifier": artifact(Path(__file__).resolve()),
        },
        "next_required_step": (
            "Freeze and independently audit a validation-only inference contract for the "
            "seed-42 adapter; test and seeds 43/44 remain closed."
        ),
        "recalculated": {
            "adapter": adapter,
            "authorization": authorization,
            "history": history,
            "loadability": loadability,
            "run": artifact(run_path),
            "runtime_config": artifact(runtime_path),
        },
        "remaining_training_seeds_authorized": False,
        "seed": 42,
        "status": "Passed",
        "test_split_absent": True,
        "test_split_accessed": False,
        "validation_evaluation_authorized": True,
        "validation_split_accessed": False,
        "verification_id": VERIFICATION_ID,
    }


def check_existing(expected: dict[str, Any], path: Path) -> None:
    existing = load_json(path)
    expected["completed_at_utc"] = existing.get("completed_at_utc")
    require_equal(existing, expected, "Stored formal training verification differs from recomputation")


def main() -> None:
    args = parse_args()
    contract = load_contract()
    verification_path = resolve_project_path(contract["outputs"]["run_dir"]) / "verification.json"
    verification = build_verification(contract)
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
