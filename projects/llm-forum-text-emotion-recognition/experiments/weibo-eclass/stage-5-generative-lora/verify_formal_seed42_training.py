#!/usr/bin/env python3
"""Independently verify the completed EXP-047 seed-42 train-only run."""

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
import stat
import statistics
import subprocess
import sys
from typing import Any

import numpy as np
from safetensors import safe_open


os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["PYTHONNOUSERSITE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

EXPERIMENT_ID = "EXP-047"
CONTRACT_ID = "EXP-047-FORMAL-SEED-42-V1"
VERIFICATION_ID = "EXP-047-FORMAL-SEED-42-TRAIN-VERIFY-V1"
STAGE = "formal-seed-42-train-only"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
CONTRACT_PATH = SCRIPT_DIR / "preflight" / "exp-047-formal-seed-42-contract-v1.json"
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
    return {"bytes": path.stat().st_size, "path": display_path(path), "sha256": sha256_file(path)}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_equal(observed: Any, expected: Any, message: str) -> None:
    if observed != expected:
        raise ValueError(f"{message}: observed={observed!r}, expected={expected!r}")


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
        contract.get("contract_id") != CONTRACT_ID
        or contract.get("experiment_id") != EXPERIMENT_ID
        or contract.get("stage") != STAGE
        or contract.get("formal_training_enabled") is not True
        or contract.get("seed") != 42
    ):
        raise ValueError("Unexpected EXP-047 formal contract identity")
    verifier = resolve_project_path(contract["implementation"]["training_verifier"]["path"])
    require_equal(verifier, Path(__file__).resolve(), "Formal training verifier path drift")
    for spec in contract["implementation"].values():
        verify_spec(spec)
    for spec in contract["frozen_artifacts"].values():
        verify_spec(spec)
    python = Path(contract["runtime"]["python_executable"])
    if not python.is_file() or not Path(sys.executable).samefile(python):
        raise ValueError("Training verifier is not running in the frozen environment")
    return contract


def run_gate_check(contract: dict[str, Any]) -> dict[str, Any]:
    python = Path(contract["runtime"]["python_executable"])
    verifier = resolve_project_path(contract["implementation"]["gate_verifier"]["path"])
    result = subprocess.run(
        [str(python), str(verifier), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=900,
    )
    if result.returncode != 0:
        raise RuntimeError("Formal gate no longer reproduces:\n" + result.stdout + result.stderr)
    return {"return_code": result.returncode, "stdout": result.stdout.strip()}


def verify_authorization(contract: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    authorization_path = resolve_project_path(report["authorization"]["path"])
    require_equal(report["authorization"], artifact(authorization_path), "Authorization artifact drift")
    authorization = load_json(authorization_path)
    gate_path = resolve_project_path(contract["outputs"]["gate_verification"])
    runtime_path = resolve_project_path(contract["frozen_artifacts"]["runtime_seed_42"]["path"])
    expected = {
        "authorized": True,
        "contract_id": CONTRACT_ID,
        "contract_path": display_path(CONTRACT_PATH),
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "experiment_id": EXPERIMENT_ID,
        "gate_verification_id": "EXP-047-FORMAL-SEED-42-GATE-VERIFY-V1",
        "gate_verification_path": display_path(gate_path),
        "gate_verification_sha256": sha256_file(gate_path),
        "runtime_config_path": display_path(runtime_path),
        "runtime_config_sha256": sha256_file(runtime_path),
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
        gate.get("verification_id") != "EXP-047-FORMAL-SEED-42-GATE-VERIFY-V1"
        or gate.get("status") != "Passed"
        or gate.get("formal_training_authorized") is not False
        or gate.get("validation_split_accessed") is not False
        or gate.get("test_split_accessed") is not False
    ):
        raise ValueError("Bound formal gate verification is invalid")
    return artifact(authorization_path)


def parse_log(path: Path) -> tuple[list[dict[str, Any]], dict[str, float]]:
    history: list[dict[str, Any]] = []
    trainable: dict[str, float] | None = None
    text = path.read_text(encoding="utf-8")
    if "Traceback" in text or "out of memory" in text.lower():
        raise ValueError("Formal stdout contains an exception or OOM marker")
    for line in text.splitlines():
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
        parameter_match = TRAINABLE_PATTERN.search(line)
        if parameter_match:
            trainable = {
                "percent": float(parameter_match.group("percent")),
                "total_millions": float(parameter_match.group("total")),
                "trainable_millions": float(parameter_match.group("trainable")),
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
    csv_history: list[dict[str, Any]] = []
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
            if not all(
                math.isfinite(float(value))
                for key, value in typed.items()
                if key not in {"iteration", "trained_tokens"}
            ):
                raise ValueError("Formal history contains a non-finite value")
            csv_history.append(typed)
    require_equal(csv_history, stdout_history, "CSV and stdout history differ")
    expected_iterations = list(
        range(int(runtime["steps_per_report"]), int(runtime["iters"]) + 1, int(runtime["steps_per_report"]))
    )
    require_equal([row["iteration"] for row in csv_history], expected_iterations, "Reporting iterations drift")
    if any(row["iterations_per_second"] <= 0 or row["tokens_per_second"] <= 0 for row in csv_history):
        raise ValueError("Formal throughput is non-positive")
    if any(
        later["trained_tokens"] <= earlier["trained_tokens"]
        for earlier, later in zip(csv_history, csv_history[1:])
    ):
        raise ValueError("Formal trained-token count is not strictly increasing")
    if any(row["learning_rate"] != float(runtime["learning_rate"]) for row in csv_history):
        raise ValueError("Formal learning-rate drift")
    require_equal(report["trainable_parameters_reported"], trainable, "Trainable report drift")
    peak = max(row["peak_memory_gb"] for row in csv_history)
    require_equal(float(report["peak_mlx_memory_gb"]), peak, "Peak memory drift")
    if peak > float(contract["resource_budget"]["peak_mlx_memory_gb_max"]):
        raise ValueError("Formal peak memory exceeds the registered budget")
    duration = float(report["duration_seconds"])
    if not math.isfinite(duration) or duration <= 0 or duration > float(contract["resource_budget"]["training_hours_max"]) * 3600:
        raise ValueError("Formal duration exceeds the registered budget")
    return {
        "duration_seconds": duration,
        "final_loss_window": statistics.mean(row["train_loss"] for row in csv_history[-5:]),
        "initial_loss_window": statistics.mean(row["train_loss"] for row in csv_history[:5]),
        "median_iterations_per_second": statistics.median(row["iterations_per_second"] for row in csv_history),
        "micro_iterations": int(runtime["iters"]),
        "peak_mlx_memory_gb": peak,
        "reporting_rows": len(csv_history),
        "trained_tokens": csv_history[-1]["trained_tokens"],
    }


def expected_adapter_keys(runtime: dict[str, Any], hidden_layers: int) -> set[str]:
    return {
        f"model.layers.{layer}.{module}.lora_{suffix}"
        for layer in range(hidden_layers - int(runtime["num_layers"]), hidden_layers)
        for module in runtime["lora_parameters"]["keys"]
        for suffix in ("a", "b")
    }


def verify_adapter(
    contract: dict[str, Any], report: dict[str, Any], runtime: dict[str, Any], adapter_dir: Path
) -> dict[str, Any]:
    expected = contract["expected_adapter"]
    expected_files = {"adapter_config.json", "adapters.safetensors", *expected["checkpoint_names"]}
    require_equal({path.name for path in adapter_dir.iterdir()}, expected_files, "Adapter directory drift")
    if stat.S_IMODE(adapter_dir.stat().st_mode) != 0o700:
        raise PermissionError("Private adapter directory mode drift")
    for path in adapter_dir.iterdir():
        if path.is_file() and stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise PermissionError(f"Private adapter file mode drift: {path.name}")
    weights_path = adapter_dir / "adapters.safetensors"
    require_equal(report["adapter"]["weights"], artifact(weights_path), "Adapter weights drift")
    keys_expected = expected_adapter_keys(runtime, int(contract["model"]["num_hidden_layers"]))
    tensor_count = 0
    parameter_count = 0
    b_count = 0
    b_nonzero = 0
    with safe_open(weights_path, framework="numpy") as handle:
        keys = set(handle.keys())
        require_equal(keys, keys_expected, "Adapter tensor key set drift")
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
    require_equal({key: report["adapter"][key] for key in observed}, observed, "Adapter summary drift")
    require_equal(parameter_count, int(expected["trainable_parameter_count"]), "Adapter parameter count drift")
    require_equal(tensor_count, int(expected["tensor_count"]), "Adapter tensor count drift")
    require_equal(b_count, int(expected["lora_b_tensor_count"]), "LoRA B tensor count drift")
    require_equal(b_nonzero, b_count, "At least one LoRA B tensor remained zero")
    checkpoints = [artifact(adapter_dir / name) for name in expected["checkpoint_names"]]
    require_equal(report["adapter"]["checkpoints"], checkpoints, "Checkpoint artifact drift")
    adapter_config_path = adapter_dir / "adapter_config.json"
    require_equal(report["adapter"]["config"], artifact(adapter_config_path), "Adapter config drift")
    expected_config = {**runtime, "config": str(resolve_project_path(contract["frozen_artifacts"]["runtime_seed_42"]["path"]))}
    require_equal(load_json(adapter_config_path), expected_config, "Saved adapter config drift")
    return {**observed, "checkpoints": checkpoints, "config": artifact(adapter_config_path), "weights": artifact(weights_path)}


def verify_adapter_loadability(runtime: dict[str, Any], adapter_dir: Path) -> dict[str, Any]:
    import mlx.core as mx
    from mlx_lm import load

    mx.reset_peak_memory()
    model, tokenizer = load(str(runtime["model"]), adapter_path=str(adapter_dir), lazy=False)
    token_ids = tokenizer.encode("Synthetic train-only adapter verification input.")
    if not token_ids:
        raise ValueError("Synthetic verification input tokenized to an empty sequence")
    logits = model(mx.array([token_ids]))
    mx.eval(logits)
    if logits.ndim != 3 or logits.shape[0] != 1 or logits.shape[1] != len(token_ids):
        raise ValueError(f"Unexpected synthetic forward shape: {logits.shape}")
    if not bool(mx.all(mx.isfinite(logits)).item()):
        raise ValueError("Synthetic adapter forward produced non-finite logits")
    return {
        "finite_logits": True,
        "input_tokens": len(token_ids),
        "logit_shape": [int(value) for value in logits.shape],
        "model_and_adapter_loaded": True,
        "peak_mlx_memory_gb": float(mx.get_peak_memory()) / 1e9,
    }


def build_verification(contract: dict[str, Any], completed_at_utc: str) -> dict[str, Any]:
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
        raise ValueError("Formal training boundary fields are invalid")
    require_equal(report["contract"], artifact(CONTRACT_PATH), "Formal contract drift")
    gate_check = run_gate_check(contract)
    authorization = verify_authorization(contract, report)
    runtime_path = resolve_project_path(contract["frozen_artifacts"]["runtime_seed_42"]["path"])
    runtime = load_json(runtime_path)
    require_equal(report["runtime_config"], artifact(runtime_path), "Runtime config artifact drift")
    observed_runtime = {key: runtime.get(key) for key in contract["formal_runtime_assertions"]}
    require_equal(observed_runtime, contract["formal_runtime_assertions"], "Runtime assertion drift")
    cli = Path(contract["runtime"]["mlx_lora_cli"]["path"])
    require_equal(report["command"], [str(cli), "-c", str(runtime_path)], "Formal command drift")
    history = verify_history(contract, report, runtime, run_dir)
    adapter = verify_adapter(contract, report, runtime, adapter_dir)
    loadability = verify_adapter_loadability(runtime, adapter_dir)
    if loadability["peak_mlx_memory_gb"] > float(contract["resource_budget"]["peak_mlx_memory_gb_max"]):
        raise ValueError("Synthetic adapter load/forward exceeded the memory budget")
    expected_run_files = {"history.csv", "run.json", "stdout.log"}
    if (run_dir / "verification.json").exists():
        expected_run_files.add("verification.json")
    require_equal({path.name for path in run_dir.iterdir()}, expected_run_files, "Formal run directory drift")
    return {
        "accessed_splits": ["train"],
        "completed_at_utc": completed_at_utc,
        "contract": artifact(CONTRACT_PATH),
        "experiment_id": EXPERIMENT_ID,
        "formal_training_verified": True,
        "implementation": {"imports_runner": False, "verifier": artifact(Path(__file__).resolve())},
        "next_required_step": "Run the frozen two-pass singleton replay for seed 42; validation and seeds 43/44 remain closed.",
        "recalculated": {
            "adapter": adapter,
            "authorization": authorization,
            "gate_check": gate_check,
            "history": history,
            "loadability": loadability,
            "run": artifact(run_path),
            "runtime_config": artifact(runtime_path),
        },
        "remaining_training_seeds_authorized": False,
        "seed": 42,
        "status": "Passed",
        "test_split_accessed": False,
        "validation_evaluation_authorized": False,
        "validation_split_accessed": False,
        "verification_id": VERIFICATION_ID,
    }


def main() -> None:
    args = parse_args()
    contract = load_contract()
    verification_path = resolve_project_path(contract["outputs"]["run_dir"]) / "verification.json"
    if args.check:
        existing = load_json(verification_path)
        expected = build_verification(contract, str(existing.get("completed_at_utc")))
        require_equal(existing, expected, "Stored training verification differs from recomputation")
        print(json.dumps({"path": display_path(verification_path), "status": "Passed"}, sort_keys=True))
        return
    if verification_path.exists():
        raise FileExistsError(verification_path)
    verification = build_verification(contract, datetime.now(timezone.utc).isoformat())
    write_json(verification_path, verification)
    print(json.dumps({"path": display_path(verification_path), "status": "Passed"}, sort_keys=True))


if __name__ == "__main__":
    main()
