#!/usr/bin/env python3
"""Execute the frozen EXP-033 seed-42 train-only formal run."""

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
from threading import Thread
import time
import traceback
from typing import Any

import numpy as np
from safetensors import safe_open


EXPERIMENT_ID = "EXP-033"
GATE_ID = "EXP-033-FORMAL-GATE-V1"
STAGE = "formal-seed-42"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
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
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("dry-run")
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
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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
        contract.get("contract_id") != GATE_ID
        or contract.get("experiment_id") != EXPERIMENT_ID
        or contract.get("stage") != STAGE
        or contract.get("formal_training_enabled") is not True
        or contract.get("seed") != 42
    ):
        raise ValueError("Unexpected EXP-033 formal gate identity")
    implementation = contract["implementation"]
    runner = resolve_project_path(implementation["runner"]["path"])
    if runner != Path(__file__).resolve():
        raise ValueError("Formal runner path drift")
    for spec in implementation.values():
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
        timeout=600,
    )
    if checked.returncode != 0:
        raise RuntimeError(
            f"Frozen verifier failed before formal execution: {path}\n"
            + checked.stdout
            + checked.stderr
        )


def verify_runtime_and_boundaries(
    contract: dict[str, Any], *, require_outputs_absent: bool
) -> dict[str, Any]:
    python = Path(contract["runtime"]["python_executable"])
    if not python.is_file() or not Path(os.sys.executable).samefile(python):
        raise ValueError("Formal gate is not running in the frozen Python environment")
    cli = Path(contract["runtime"]["mlx_lora_cli"]["path"])
    if (
        not cli.is_file()
        or not os.access(cli, os.X_OK)
        or sha256_file(cli) != contract["runtime"]["mlx_lora_cli"]["sha256"]
    ):
        raise ValueError("Frozen MLX-LM CLI drift")

    smoke_verifier = resolve_project_path(
        contract["frozen_artifacts"]["smoke_verifier"]["path"]
    )
    run_verifier(smoke_verifier, python)

    dry_path = resolve_project_path(
        contract["frozen_artifacts"]["runner_dry_run_verification"]["path"]
    )
    dry = load_json(dry_path)
    if (
        dry.get("verification_id") != "EXP-033-RUNNER-DRY-RUN-VERIFY-V3"
        or dry.get("status") != "Passed"
        or dry.get("model_forward_or_backward_executed") is not False
        or dry.get("formal_training_authorized") is not False
        or dry.get("validation_split_accessed") is not False
        or dry.get("test_split_accessed") is not False
    ):
        raise ValueError("Frozen V3 dry-run verification is invalid")

    config_path = resolve_project_path(contract["frozen_artifacts"]["config_v3"]["path"])
    config = load_json(config_path)
    if (
        config.get("experiment_id") != EXPERIMENT_ID
        or config["authorization_contract"].get("formal_training_enabled") is not False
    ):
        raise ValueError("The superseded V3 runner contract must remain formal-disabled")
    runtime_path = resolve_project_path(
        contract["frozen_artifacts"]["formal_runtime"]["path"]
    )
    runtime = load_json(runtime_path)
    canonical_path = resolve_project_path(
        contract["frozen_artifacts"]["canonical_runtime_contract"]["path"]
    )
    canonical = load_json(canonical_path)
    if runtime != canonical["effective_configs"]["formal_seed_42"]:
        raise ValueError("Formal runtime differs from the frozen canonical runtime")
    expected = contract["formal_runtime_assertions"]
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
    if observed != expected:
        raise ValueError(f"Formal runtime assertion drift: {observed}")
    outputs = contract["outputs"]
    adapter_dir = resolve_project_path(outputs["adapter_dir"])
    if Path(runtime["adapter_path"]).resolve() != adapter_dir:
        raise ValueError("Formal runtime adapter path differs from the contract output path")
    data_dir = Path(runtime["data"])
    entries = sorted(path.name for path in data_dir.iterdir())
    if entries != contract["training_data"]["directory_entries"]:
        raise ValueError("Formal runtime data-directory inventory drift")
    forbidden = [name for name in ("valid.jsonl", "dev.jsonl", "test.jsonl") if (data_dir / name).exists()]
    if forbidden:
        raise ValueError(f"Formal runtime data directory contains forbidden splits: {forbidden}")
    train_path = data_dir / "train.jsonl"
    if sha256_file(train_path) != contract["training_data"]["sha256"]:
        raise ValueError("Formal training JSONL hash drift")
    test_spec = contract["test_gate"]
    if test_spec != config["data"]["test"]:
        raise ValueError("Formal test gate differs from the frozen V3 data contract")
    test_path = resolve_project_path(test_spec["path"])
    if test_spec.get("must_be_absent") is not True or test_path.exists():
        raise ValueError("Test-absence gate failed")

    smoke_path = resolve_project_path(
        contract["frozen_artifacts"]["smoke_verification"]["path"]
    )
    smoke = load_json(smoke_path)
    if (
        smoke.get("verification_id") != "EXP-033-SMOKE-VERIFY-V1"
        or smoke.get("status") != "Passed"
        or smoke.get("formal_training_authorized") is not False
        or smoke.get("validation_split_accessed") is not False
        or smoke.get("test_split_accessed") is not False
    ):
        raise ValueError("Smoke verification does not satisfy the formal transition gate")

    run_dir = resolve_project_path(outputs["run_dir"])
    if require_outputs_absent:
        present = [display_path(path) for path in (adapter_dir, run_dir) if path.exists()]
        if present:
            raise FileExistsError(f"Append-only formal output already exists: {present}")
    return {
        "config": artifact(config_path),
        "formal_runtime": artifact(runtime_path),
        "mlx_lora_cli": artifact(cli),
        "smoke_verification": artifact(smoke_path),
        "test_split_absent": True,
        "train_data": artifact(train_path),
    }


def dry_run(contract: dict[str, Any]) -> None:
    report_path = resolve_project_path(contract["outputs"]["gate_dry_run"])
    verification_path = resolve_project_path(contract["outputs"]["gate_verification"])
    if report_path.exists() or verification_path.exists():
        raise FileExistsError("Formal gate dry-run or verification already exists")
    checked = verify_runtime_and_boundaries(contract, require_outputs_absent=True)
    report = {
        "accessed_splits": ["train"],
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract": artifact(CONTRACT_PATH),
        "experiment_id": EXPERIMENT_ID,
        "formal_training_authorized": False,
        "gate_id": GATE_ID,
        "implementation": {
            name: verify_spec(spec) for name, spec in contract["implementation"].items()
        },
        "model_forward_or_backward_executed": False,
        "next_required_step": (
            "Independently verify this gate, then bind a separate formal-seed-42 "
            "authorization before training."
        ),
        "recalculated": checked,
        "stage": "formal-gate-dry-run",
        "status": "Passed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
    }
    write_json(report_path, report)
    print(json.dumps(report, indent=2, sort_keys=True))


def verify_authorization(
    contract: dict[str, Any], authorization_path: Path
) -> dict[str, Any]:
    gate_verifier = resolve_project_path(contract["implementation"]["gate_verifier"]["path"])
    python = Path(contract["runtime"]["python_executable"])
    run_verifier(gate_verifier, python)
    gate_path = resolve_project_path(contract["outputs"]["gate_verification"])
    smoke_path = resolve_project_path(
        contract["frozen_artifacts"]["smoke_verification"]["path"]
    )
    runtime_path = resolve_project_path(
        contract["frozen_artifacts"]["formal_runtime"]["path"]
    )
    config_path = resolve_project_path(contract["frozen_artifacts"]["config_v3"]["path"])
    authorization_path = authorization_path.expanduser().resolve()
    if not authorization_path.is_file():
        raise FileNotFoundError(authorization_path)
    if not authorization_path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError("Formal authorization must be stored inside the project")
    authorization = load_json(authorization_path)
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
        if authorization.get(key) != value:
            raise ValueError(f"Formal authorization binding mismatch: {key}")
    if authorization.get("scope") != {
        "seeds": [42],
        "test_split": False,
        "train": True,
        "validation_split": False,
    }:
        raise ValueError("Formal authorization scope drift")
    return artifact(authorization_path)


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
            numeric = [
                value
                for key, value in row.items()
                if key not in {"iteration", "trained_tokens"}
            ]
            if not all(math.isfinite(float(value)) for value in numeric):
                raise ValueError("Formal training log contains a non-finite value")
            history.append(row)
        trainable_match = TRAINABLE_PATTERN.search(line)
        if trainable_match:
            trainable = {
                "percent": float(trainable_match.group("percent")),
                "total_millions": float(trainable_match.group("total")),
                "trainable_millions": float(trainable_match.group("trainable")),
            }
    if not history or trainable is None:
        raise ValueError("Formal training log is missing history or parameter output")
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


def adapter_summary(path: Path) -> dict[str, Any]:
    tensor_count = 0
    parameter_count = 0
    b_count = 0
    b_nonzero = 0
    with safe_open(path, framework="numpy") as handle:
        for key in handle.keys():
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


def stream_subprocess(
    command: list[str], log_path: Path, timeout_seconds: float
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

        reader = Thread(target=read_output, name="exp-033-formal-stdout", daemon=True)
        reader.start()
        try:
            while True:
                elapsed = time.perf_counter() - started
                if elapsed > timeout_seconds:
                    raise TimeoutError("Formal training exceeded the registered wall-time budget")
                try:
                    line = output_queue.get(timeout=min(1.0, timeout_seconds - elapsed))
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
            try:
                return_code = process.wait(timeout=remaining)
            except subprocess.TimeoutExpired as error:
                raise TimeoutError(
                    "Formal training exceeded the wall-time budget after stdout closed"
                ) from error
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
    checked = verify_runtime_and_boundaries(contract, require_outputs_absent=True)
    outputs = contract["outputs"]
    run_dir = resolve_project_path(outputs["run_dir"])
    adapter_dir = resolve_project_path(outputs["adapter_dir"])
    report_path = run_dir / "run.json"
    log_path = run_dir / "stdout.log"
    history_path = run_dir / "history.csv"
    runtime_path = resolve_project_path(
        contract["frozen_artifacts"]["formal_runtime"]["path"]
    )
    cli = Path(contract["runtime"]["mlx_lora_cli"]["path"])
    command = [str(cli), "-c", str(runtime_path)]
    started_at = datetime.now(timezone.utc)
    record: dict[str, Any] = {
        "accessed_splits": ["train"],
        "authorization": authorization,
        "command": command,
        "contract": artifact(CONTRACT_PATH),
        "experiment_id": EXPERIMENT_ID,
        "git": git_state(),
        "seed": 42,
        "stage": STAGE,
        "started_at_utc": started_at.isoformat(),
        "status": "In Progress",
        "test_split_accessed": False,
        "tier": "Major",
        "validation_split_accessed": False,
    }
    run_dir.mkdir(parents=True, exist_ok=False)
    try:
        write_json(report_path, record)
        adapter_dir.mkdir(parents=True, exist_ok=False)
        timeout_seconds = float(contract["resource_budget"]["training_hours_max"]) * 3600
        return_code, elapsed = stream_subprocess(command, log_path, timeout_seconds)
        if return_code != 0:
            raise RuntimeError(f"MLX-LM formal training exited with status {return_code}")
        runtime = load_json(runtime_path)
        history, trainable = parse_training_log(log_path)
        if history[-1]["iteration"] != int(runtime["iters"]):
            raise ValueError("Formal history does not end at the registered iteration")
        peak_memory = max(float(row["peak_memory_gb"]) for row in history)
        if peak_memory > float(contract["resource_budget"]["peak_mlx_memory_gb_max"]):
            raise MemoryError("Formal training exceeded the MLX memory budget")
        final_adapter = adapter_dir / "adapters.safetensors"
        adapter_config = adapter_dir / "adapter_config.json"
        if not final_adapter.is_file() or not adapter_config.is_file():
            raise FileNotFoundError("Formal training did not save the final adapter")
        summary = adapter_summary(final_adapter)
        if summary["trainable_parameter_count"] != int(
            contract["expected_adapter"]["trainable_parameter_count"]
        ):
            raise ValueError("Formal adapter parameter-count drift")
        if summary["lora_b_nonzero_tensors"] != summary["lora_b_tensor_count"]:
            raise ValueError("At least one formal LoRA B tensor remained zero")
        checkpoints = [
            artifact(path)
            for path in sorted(adapter_dir.glob("*_adapters.safetensors"))
        ]
        if [Path(item["path"]).name for item in checkpoints] != contract["expected_adapter"][
            "checkpoint_names"
        ]:
            raise ValueError("Formal checkpoint set drift")
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
            "preconditions": checked,
            "runtime_config": artifact(runtime_path),
            "status": "Completed; pending independent verification",
            "stdout": artifact(log_path),
            "trainable_parameters_reported": trainable,
        }
        write_json(report_path, completed)
        print(json.dumps(completed, indent=2, sort_keys=True))
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
    if args.command == "dry-run":
        dry_run(contract)
    elif args.command == "train":
        run_formal(contract, args.authorization)
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()
