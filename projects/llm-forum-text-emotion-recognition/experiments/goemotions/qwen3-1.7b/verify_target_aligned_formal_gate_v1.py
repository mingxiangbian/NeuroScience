#!/usr/bin/env python3
"""Independently verify the EXP-033 seed-42 formal execution gate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any


EXPERIMENT_ID = "EXP-033"
GATE_ID = "EXP-033-FORMAL-GATE-V1"
VERIFICATION_ID = "EXP-033-FORMAL-GATE-VERIFY-V1"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
CONTRACT_PATH = SCRIPT_DIR / "preflight" / "exp-033-formal-gate-contract-v1.json"


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


def verify_spec(spec: dict[str, Any]) -> dict[str, Any]:
    path = resolve_project_path(spec["path"])
    observed = artifact(path)
    if observed["sha256"] != spec["sha256"]:
        raise ValueError(f"Frozen artifact hash drift: {path}")
    if "bytes" in spec and observed["bytes"] != int(spec["bytes"]):
        raise ValueError(f"Frozen artifact size drift: {path}")
    return observed


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
            f"Frozen verifier failed during gate recomputation: {path}\n"
            + checked.stdout
            + checked.stderr
        )


def load_contract() -> dict[str, Any]:
    contract = load_json(CONTRACT_PATH)
    if (
        contract.get("contract_id") != GATE_ID
        or contract.get("experiment_id") != EXPERIMENT_ID
        or contract.get("stage") != "formal-seed-42"
        or contract.get("formal_training_enabled") is not True
        or contract.get("seed") != 42
    ):
        raise ValueError("Unexpected EXP-033 formal gate identity")
    implementation = contract["implementation"]
    verifier = resolve_project_path(implementation["gate_verifier"]["path"])
    if verifier != Path(__file__).resolve():
        raise ValueError("Formal gate verifier path drift")
    for spec in implementation.values():
        verify_spec(spec)
    for spec in contract["frozen_artifacts"].values():
        verify_spec(spec)
    return contract


def recompute(contract: dict[str, Any]) -> dict[str, Any]:
    python = Path(contract["runtime"]["python_executable"])
    if not python.is_file() or not Path(os.sys.executable).samefile(python):
        raise ValueError("Gate verifier is not running in the frozen Python environment")
    cli = Path(contract["runtime"]["mlx_lora_cli"]["path"])
    if (
        not cli.is_file()
        or not os.access(cli, os.X_OK)
        or sha256_file(cli) != contract["runtime"]["mlx_lora_cli"]["sha256"]
    ):
        raise ValueError("Frozen MLX-LM CLI drift")
    run_verifier(
        resolve_project_path(contract["frozen_artifacts"]["smoke_verifier"]["path"]),
        python,
    )

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
        raise ValueError("Superseded V3 runner contract is not frozen formal-disabled")
    runtime_path = resolve_project_path(
        contract["frozen_artifacts"]["formal_runtime"]["path"]
    )
    runtime = load_json(runtime_path)
    canonical_path = resolve_project_path(
        contract["frozen_artifacts"]["canonical_runtime_contract"]["path"]
    )
    canonical = load_json(canonical_path)
    if runtime != canonical["effective_configs"]["formal_seed_42"]:
        raise ValueError("Formal runtime differs from the canonical runtime contract")
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
    if observed != contract["formal_runtime_assertions"]:
        raise ValueError("Formal runtime assertion drift")
    adapter_dir = resolve_project_path(contract["outputs"]["adapter_dir"])
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
        raise ValueError("Formal train JSONL hash drift")
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
        raise ValueError("Smoke verification transition fields are invalid")
    run_dir = resolve_project_path(contract["outputs"]["run_dir"])
    present = [display_path(path) for path in (adapter_dir, run_dir) if path.exists()]
    if present:
        raise FileExistsError(f"Formal outputs already exist before authorization: {present}")
    return {
        "config": artifact(config_path),
        "formal_runtime": artifact(runtime_path),
        "mlx_lora_cli": artifact(cli),
        "smoke_verification": artifact(smoke_path),
        "test_split_absent": True,
        "train_data": artifact(train_path),
    }


def build_verification(contract: dict[str, Any]) -> dict[str, Any]:
    dry_path = resolve_project_path(contract["outputs"]["gate_dry_run"])
    dry = load_json(dry_path)
    recalculated = recompute(contract)
    expected_implementation = {
        name: verify_spec(spec) for name, spec in contract["implementation"].items()
    }
    if (
        dry.get("experiment_id") != EXPERIMENT_ID
        or dry.get("gate_id") != GATE_ID
        or dry.get("stage") != "formal-gate-dry-run"
        or dry.get("status") != "Passed"
        or dry.get("accessed_splits") != ["train"]
        or dry.get("formal_training_authorized") is not False
        or dry.get("model_forward_or_backward_executed") is not False
        or dry.get("validation_split_accessed") is not False
        or dry.get("test_split_accessed") is not False
        or dry.get("contract") != artifact(CONTRACT_PATH)
        or dry.get("implementation") != expected_implementation
        or dry.get("recalculated") != recalculated
    ):
        raise ValueError("Stored formal gate dry-run differs from independent recomputation")
    return {
        "accessed_splits": ["train"],
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract": artifact(CONTRACT_PATH),
        "dry_run": artifact(dry_path),
        "experiment_id": EXPERIMENT_ID,
        "formal_training_authorized": False,
        "gate_id": GATE_ID,
        "implementation": {
            "imports_runner": False,
            "verifier": artifact(Path(__file__).resolve()),
        },
        "model_forward_or_backward_executed": False,
        "next_required_step": (
            "Create a separately hash-bound formal-seed-42 authorization, then execute "
            "the frozen train-only runtime once."
        ),
        "recalculated": recalculated,
        "status": "Passed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
        "verification_id": VERIFICATION_ID,
    }


def check_existing(expected: dict[str, Any], path: Path) -> None:
    existing = load_json(path)
    expected["completed_at_utc"] = existing.get("completed_at_utc")
    if existing != expected:
        raise ValueError("Stored formal gate verification differs from recomputation")


def main() -> None:
    args = parse_args()
    contract = load_contract()
    verification_path = resolve_project_path(contract["outputs"]["gate_verification"])
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
