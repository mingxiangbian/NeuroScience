#!/usr/bin/env python3
"""Execute the frozen EXP-047 seed-44 train-only LoRA run."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from queue import Empty, Queue
import re
import subprocess
import sys
from threading import Thread
import time
import traceback
from typing import Any

import numpy as np
from safetensors import safe_open


EXPERIMENT_ID = "EXP-047"
CONTRACT_ID = "EXP-047-FORMAL-SEED-44-V1"
STAGE = "formal-seed-44-train-only"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
CONTRACT_PATH = SCRIPT_DIR / "preflight" / "exp-047-formal-seed-44-contract-v1.json"
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
    subparsers = parser.add_subparsers(dest="command", required=True)
    train = subparsers.add_parser("train")
    train.add_argument("--authorization", type=Path, required=True)
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
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_spec(spec: dict[str, Any]) -> dict[str, Any]:
    path = resolve_project_path(spec["path"])
    observed = artifact(path)
    if observed["sha256"] != spec["sha256"]:
        raise ValueError(f"Frozen artifact hash drift: {path}")
    if "bytes" in spec and observed["bytes"] != int(spec["bytes"]):
        raise ValueError(f"Frozen artifact size drift: {path}")
    return observed


def load_contract() -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    if (
        contract.get("contract_id") != CONTRACT_ID
        or contract.get("experiment_id") != EXPERIMENT_ID
        or contract.get("stage") != STAGE
        or contract.get("formal_training_enabled") is not True
        or contract.get("seed") != 44
    ):
        raise ValueError("Unexpected EXP-047 formal contract identity")
    runner = resolve_project_path(contract["implementation"]["runner"]["path"])
    if runner != Path(__file__).resolve():
        raise ValueError("Formal runner path drift")
    for spec in contract["implementation"].values():
        verify_spec(spec)
    for spec in contract["frozen_artifacts"].values():
        verify_spec(spec)
    return contract


def run_verifier(path: Path, python: Path) -> None:
    checked = subprocess.run(
        [str(python), str(path), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=900,
    )
    if checked.returncode != 0:
        raise RuntimeError(
            f"Frozen verifier failed before formal execution: {path}\n"
            + checked.stdout
            + checked.stderr
        )


def verify_authorization(contract: dict[str, Any], path: Path) -> dict[str, Any]:
    python = Path(contract["runtime"]["python_executable"])
    gate_verifier = resolve_project_path(contract["implementation"]["gate_verifier"]["path"])
    run_verifier(gate_verifier, python)

    path = path.expanduser().resolve()
    if not path.is_file() or not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError("Authorization must be an existing project-local file")
    authorization = load_json(path)
    gate_path = resolve_project_path(contract["outputs"]["gate_verification"])
    runtime_path = resolve_project_path(contract["frozen_artifacts"]["runtime_seed_44"]["path"])
    expected = {
        "authorized": True,
        "contract_id": CONTRACT_ID,
        "contract_path": display_path(CONTRACT_PATH),
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "experiment_id": EXPERIMENT_ID,
        "gate_verification_id": "EXP-047-FORMAL-SEED-44-GATE-VERIFY-V1",
        "gate_verification_path": display_path(gate_path),
        "gate_verification_sha256": sha256_file(gate_path),
        "runtime_config_path": display_path(runtime_path),
        "runtime_config_sha256": sha256_file(runtime_path),
        "stage": STAGE,
    }
    for key, value in expected.items():
        if authorization.get(key) != value:
            raise ValueError(f"Formal authorization binding mismatch: {key}")
    if authorization.get("scope") != {
        "seeds": [44],
        "test_split": False,
        "train": True,
        "validation_split": False,
    }:
        raise ValueError("Formal authorization scope drift")
    return artifact(path)


def verify_execution_inputs(contract: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    runtime_path = resolve_project_path(contract["frozen_artifacts"]["runtime_seed_44"]["path"])
    runtime = load_json(runtime_path)
    observed = {key: runtime.get(key) for key in contract["formal_runtime_assertions"]}
    if observed != contract["formal_runtime_assertions"]:
        raise ValueError(f"Formal runtime assertion drift: {observed}")
    data_dir = Path(runtime["data"])
    if sorted(item.name for item in data_dir.iterdir()) != contract["training_data"]["directory_entries"]:
        raise ValueError("Formal training directory inventory drift")
    if any((data_dir / name).exists() for name in ("valid.jsonl", "dev.jsonl", "test.jsonl")):
        raise ValueError("Formal training directory contains a forbidden split")
    train_path = data_dir / "train.jsonl"
    if (
        sha256_file(train_path) != contract["training_data"]["sha256"]
        or train_path.stat().st_size != int(contract["training_data"]["bytes"])
    ):
        raise ValueError("Formal training data drift")
    with train_path.open("r", encoding="utf-8") as source:
        rows = sum(1 for line in source if line.strip())
    if rows != int(contract["training_data"]["rows"]):
        raise ValueError("Formal training row-count drift")
    adapter_dir = resolve_project_path(contract["outputs"]["adapter_dir"])
    if Path(runtime["adapter_path"]).resolve() != adapter_dir:
        raise ValueError("Runtime adapter path differs from the formal contract")
    run_dir = resolve_project_path(contract["outputs"]["run_dir"])
    present = [display_path(path) for path in (adapter_dir, run_dir) if path.exists()]
    if present:
        raise FileExistsError(f"Append-only formal output already exists: {present}")
    return runtime_path, runtime


def parse_training_log(path: Path) -> tuple[list[dict[str, Any]], dict[str, float]]:
    history: list[dict[str, Any]] = []
    trainable: dict[str, float] | None = None
    text = path.read_text(encoding="utf-8")
    if "Traceback" in text or "out of memory" in text.lower():
        raise ValueError("Formal training log contains an exception or OOM marker")
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
            if not all(
                math.isfinite(float(value))
                for key, value in row.items()
                if key not in {"iteration", "trained_tokens"}
            ):
                raise ValueError("Formal training log contains a non-finite value")
            history.append(row)
        parameter_match = TRAINABLE_PATTERN.search(line)
        if parameter_match:
            trainable = {
                "percent": float(parameter_match.group("percent")),
                "total_millions": float(parameter_match.group("total")),
                "trainable_millions": float(parameter_match.group("trainable")),
            }
    if not history or trainable is None:
        raise ValueError("Formal log is missing history or trainable-parameter output")
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
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(history)


def expected_adapter_keys(runtime: dict[str, Any], hidden_layers: int) -> set[str]:
    layers = range(hidden_layers - int(runtime["num_layers"]), hidden_layers)
    modules = runtime["lora_parameters"]["keys"]
    return {
        f"model.layers.{layer}.{module}.lora_{suffix}"
        for layer in layers
        for module in modules
        for suffix in ("a", "b")
    }


def adapter_summary(path: Path, runtime: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    expected_keys = expected_adapter_keys(runtime, int(contract["model"]["num_hidden_layers"]))
    tensor_count = 0
    parameter_count = 0
    b_count = 0
    b_nonzero = 0
    with safe_open(path, framework="numpy") as handle:
        keys = set(handle.keys())
        if keys != expected_keys:
            raise ValueError("Formal adapter tensor key set drift")
        for key in sorted(keys):
            tensor = handle.get_tensor(key)
            if not np.isfinite(tensor).all():
                raise ValueError(f"Non-finite adapter tensor: {key}")
            tensor_count += 1
            parameter_count += int(tensor.size)
            if key.endswith("lora_b"):
                b_count += 1
                b_nonzero += int(np.any(tensor != 0))
    return {
        "lora_b_nonzero_tensors": b_nonzero,
        "lora_b_tensor_count": b_count,
        "tensor_count": tensor_count,
        "trainable_parameter_count": parameter_count,
    }


def stream_subprocess(command: list[str], log_path: Path, timeout_seconds: float) -> tuple[int, float]:
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
    with log_path.open("x", encoding="utf-8") as log:
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
        output_queue: Queue[str | None] = Queue()

        def read_output() -> None:
            try:
                for line in process.stdout:
                    output_queue.put(line)
            finally:
                output_queue.put(None)

        reader = Thread(target=read_output, name="exp-047-seed44-stdout", daemon=True)
        reader.start()
        try:
            while True:
                elapsed = time.perf_counter() - started
                if elapsed > timeout_seconds:
                    raise TimeoutError("Formal training exceeded the registered wall-time budget")
                try:
                    line = output_queue.get(timeout=min(1.0, max(0.1, timeout_seconds - elapsed)))
                except Empty:
                    continue
                if line is None:
                    break
                log.write(line)
                log.flush()
                print(line, end="", flush=True)
            remaining = timeout_seconds - (time.perf_counter() - started)
            if remaining <= 0:
                raise TimeoutError("Formal training exceeded the registered wall-time budget")
            return_code = process.wait(timeout=remaining)
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise
        finally:
            reader.join(timeout=5)
    return return_code, time.perf_counter() - started


def git_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--short"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return {"commit": commit, "dirty": dirty}


def run_formal(contract: dict[str, Any], authorization_path: Path) -> None:
    authorization = verify_authorization(contract, authorization_path)
    runtime_path, runtime = verify_execution_inputs(contract)
    run_dir = resolve_project_path(contract["outputs"]["run_dir"])
    adapter_dir = resolve_project_path(contract["outputs"]["adapter_dir"])
    report_path = run_dir / "run.json"
    log_path = run_dir / "stdout.log"
    history_path = run_dir / "history.csv"
    cli = Path(contract["runtime"]["mlx_lora_cli"]["path"])
    command = [str(cli), "-c", str(runtime_path)]
    record: dict[str, Any] = {
        "accessed_splits": ["train"],
        "authorization": authorization,
        "command": command,
        "contract": artifact(CONTRACT_PATH),
        "experiment_id": EXPERIMENT_ID,
        "git": git_state(),
        "seed": 44,
        "stage": STAGE,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "In Progress",
        "test_split_accessed": False,
        "tier": "Major",
        "validation_split_accessed": False,
    }
    run_dir.mkdir(parents=True, exist_ok=False)
    try:
        write_json(report_path, record)
        adapter_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
        adapter_dir.chmod(0o700)
        timeout_seconds = float(contract["resource_budget"]["training_hours_max"]) * 3600
        return_code, elapsed = stream_subprocess(command, log_path, timeout_seconds)
        if return_code != 0:
            raise RuntimeError(f"MLX-LM formal training exited with status {return_code}")
        history, trainable = parse_training_log(log_path)
        if history[-1]["iteration"] != int(runtime["iters"]):
            raise ValueError("Formal history does not end at the registered iteration")
        expected_iterations = list(
            range(int(runtime["steps_per_report"]), int(runtime["iters"]) + 1, int(runtime["steps_per_report"]))
        )
        if [row["iteration"] for row in history] != expected_iterations:
            raise ValueError("Formal reporting iteration set drift")
        peak_memory = max(float(row["peak_memory_gb"]) for row in history)
        if peak_memory > float(contract["resource_budget"]["peak_mlx_memory_gb_max"]):
            raise MemoryError("Formal training exceeded the MLX memory budget")
        final_adapter = adapter_dir / "adapters.safetensors"
        adapter_config = adapter_dir / "adapter_config.json"
        if not final_adapter.is_file() or not adapter_config.is_file():
            raise FileNotFoundError("Formal training did not save the final adapter")
        summary = adapter_summary(final_adapter, runtime, contract)
        expected_adapter = contract["expected_adapter"]
        if (
            summary["trainable_parameter_count"] != int(expected_adapter["trainable_parameter_count"])
            or summary["tensor_count"] != int(expected_adapter["tensor_count"])
            or summary["lora_b_tensor_count"] != int(expected_adapter["lora_b_tensor_count"])
            or summary["lora_b_nonzero_tensors"] != int(expected_adapter["lora_b_tensor_count"])
        ):
            raise ValueError("Formal adapter integrity summary drift")
        checkpoints = [artifact(adapter_dir / name) for name in expected_adapter["checkpoint_names"]]
        expected_names = {"adapter_config.json", "adapters.safetensors", *expected_adapter["checkpoint_names"]}
        if {path.name for path in adapter_dir.iterdir()} != expected_names:
            raise ValueError("Formal adapter directory contents drift")
        for path in adapter_dir.iterdir():
            if path.is_file():
                path.chmod(0o600)
        write_history(history_path, history)
        completed = {
            **record,
            "adapter": {
                "checkpoints": checkpoints,
                "config": artifact(adapter_config),
                "weights": artifact(final_adapter),
                **summary,
            },
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": elapsed,
            "history": artifact(history_path),
            "peak_mlx_memory_gb": peak_memory,
            "runtime_config": artifact(runtime_path),
            "status": "Completed; pending independent verification",
            "stdout": artifact(log_path),
            "trainable_parameters_reported": trainable,
        }
        write_json(report_path, completed)
        print(json.dumps({"duration_seconds": elapsed, "status": completed["status"]}, sort_keys=True))
    except BaseException as error:
        failed = load_json(report_path) if report_path.is_file() else record
        failed.update(
            {
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "error": {"message": str(error), "traceback": traceback.format_exc()},
                "status": "Failed",
            }
        )
        write_json(report_path, failed)
        raise


def main() -> None:
    args = parse_args()
    contract = load_contract()
    if args.command != "train":
        raise AssertionError(args.command)
    run_formal(contract, args.authorization)


if __name__ == "__main__":
    main()
