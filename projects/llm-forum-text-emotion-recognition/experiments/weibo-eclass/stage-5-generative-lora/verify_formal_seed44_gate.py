#!/usr/bin/env python3
"""Independently verify the EXP-047 seed-44 formal execution gate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys
from typing import Any


EXPERIMENT_ID = "EXP-047"
CONTRACT_ID = "EXP-047-FORMAL-SEED-44-V1"
VERIFICATION_ID = "EXP-047-FORMAL-SEED-44-GATE-VERIFY-V1"
STAGE = "formal-seed-44-train-only"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
CONTRACT_PATH = SCRIPT_DIR / "preflight" / "exp-047-formal-seed-44-contract-v1.json"


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
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_spec(spec: dict[str, Any]) -> dict[str, Any]:
    path = resolve_project_path(spec["path"])
    observed = artifact(path)
    if observed["sha256"] != spec["sha256"]:
        raise ValueError(f"Frozen artifact hash drift: {path}")
    if "bytes" in spec and observed["bytes"] != int(spec["bytes"]):
        raise ValueError(f"Frozen artifact size drift: {path}")
    return observed


def source_tree_manifest(spec: dict[str, Any]) -> dict[str, Any]:
    root = Path(spec["root"])
    paths = sorted(root.rglob("*.py"), key=lambda item: item.relative_to(root).as_posix())
    aggregate = hashlib.sha256()
    total_bytes = 0
    for path in paths:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        size = path.stat().st_size
        digest = sha256_file(path).encode("ascii")
        aggregate.update(relative + b"\0" + str(size).encode("ascii") + b"\0" + digest + b"\n")
        total_bytes += size
    observed = {
        "file_count": len(paths),
        "manifest_sha256": aggregate.hexdigest(),
        "total_bytes": total_bytes,
    }
    expected = {
        "file_count": int(spec["file_count"]),
        "manifest_sha256": spec["manifest_sha256"],
        "total_bytes": int(spec["total_bytes"]),
    }
    if observed != expected:
        raise ValueError(f"MLX-LM source tree drift: {observed}")
    return observed


def verify_environment(contract: dict[str, Any]) -> dict[str, Any]:
    runtime = contract["runtime"]
    python = Path(runtime["python_executable"])
    if not python.is_file() or not Path(sys.executable).samefile(python):
        raise ValueError(f"Use the frozen Python executable: {python}")
    packages = {
        name: platform.python_version() if name == "python" else importlib.metadata.version(name)
        for name in runtime["packages"]
    }
    if packages != runtime["packages"]:
        raise ValueError(f"Runtime package drift: {packages}")
    cli_spec = runtime["mlx_lora_cli"]
    cli = Path(cli_spec["path"])
    if not cli.is_file() or not os.access(cli, os.X_OK) or sha256_file(cli) != cli_spec["sha256"]:
        raise ValueError("Frozen MLX-LM CLI drift")
    semantics: dict[str, Any] = {}
    for name, spec in runtime["semantics_sources"].items():
        path = Path(spec["path"])
        observed = {"bytes": path.stat().st_size, "path": str(path), "sha256": sha256_file(path)}
        if observed != spec:
            raise ValueError(f"MLX-LM semantics source drift: {name}")
        semantics[name] = observed
    return {
        "mlx_lm_source_tree": source_tree_manifest(runtime["mlx_lm_source_tree"]),
        "mlx_lora_cli": {"bytes": cli.stat().st_size, "path": str(cli), "sha256": sha256_file(cli)},
        "packages": packages,
        "python_executable": str(python),
        "semantics_sources": semantics,
    }


def verify_model(contract: dict[str, Any]) -> dict[str, Any]:
    model = contract["model"]
    manifest_path = resolve_project_path(model["manifest_path"])
    if sha256_file(manifest_path) != model["manifest_sha256"]:
        raise ValueError("Model manifest hash drift")
    manifest = load_json(manifest_path)
    if manifest.get("repo_id") != model["repo_id"] or manifest.get("revision") != model["revision"]:
        raise ValueError("Model identity drift")
    model_root = resolve_project_path(model["local_path"])
    aggregate = hashlib.sha256()
    count = 0
    total = 0
    for expected in manifest["mlx_bf16"]["files"]:
        path = model_root / expected["path"]
        observed = {"bytes": path.stat().st_size, "path": expected["path"], "sha256": sha256_file(path)}
        if observed != expected:
            raise ValueError(f"Model file drift: {path}")
        aggregate.update(
            expected["path"].encode("utf-8")
            + b"\0"
            + str(observed["bytes"]).encode("ascii")
            + b"\0"
            + observed["sha256"].encode("ascii")
            + b"\n"
        )
        count += 1
        total += observed["bytes"]
    if count != 9 or total != 8056445038 or aggregate.hexdigest() != model["files_manifest_sha256"]:
        raise ValueError("Model file manifest aggregate drift")
    return {
        "file_count": count,
        "files_manifest_sha256": aggregate.hexdigest(),
        "manifest": artifact(manifest_path),
        "total_bytes": total,
    }


def run_checked(command: list[str], *, timeout: int = 900) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError("Frozen check failed:\n" + result.stdout + result.stderr)
    return {"command": command, "return_code": result.returncode, "stdout": result.stdout.strip()}


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
    verifier = resolve_project_path(contract["implementation"]["gate_verifier"]["path"])
    if verifier != Path(__file__).resolve():
        raise ValueError("Formal gate verifier path drift")
    for spec in contract["implementation"].values():
        verify_spec(spec)
    for spec in contract["frozen_artifacts"].values():
        verify_spec(spec)
    return contract


def verify_runtime_and_data(contract: dict[str, Any]) -> dict[str, Any]:
    config_path = resolve_project_path(contract["frozen_artifacts"]["config"]["path"])
    config = load_json(config_path)
    if (
        config.get("experiment_id") != EXPERIMENT_ID
        or config.get("status") != "Registered"
        or config["execution"].get("authorized") is not False
        or config["data"].get("test_access") is not False
    ):
        raise ValueError("Frozen EXP-047 config boundary drift")
    runtime_path = resolve_project_path(contract["frozen_artifacts"]["runtime_seed_44"]["path"])
    runtime = load_json(runtime_path)
    observed_runtime = {key: runtime.get(key) for key in contract["formal_runtime_assertions"]}
    if observed_runtime != contract["formal_runtime_assertions"]:
        raise ValueError(f"Formal runtime assertion drift: {observed_runtime}")
    if runtime.get("model") != str(resolve_project_path(contract["model"]["local_path"])):
        raise ValueError("Formal runtime model path drift")
    adapter_dir = resolve_project_path(contract["outputs"]["adapter_dir"])
    if Path(runtime["adapter_path"]).resolve() != adapter_dir:
        raise ValueError("Formal runtime adapter path drift")
    data_dir = Path(runtime["data"])
    if sorted(path.name for path in data_dir.iterdir()) != contract["training_data"]["directory_entries"]:
        raise ValueError("Formal data-directory inventory drift")
    forbidden = [name for name in ("valid.jsonl", "dev.jsonl", "test.jsonl") if (data_dir / name).exists()]
    if forbidden:
        raise ValueError(f"Formal data directory contains forbidden splits: {forbidden}")
    train_path = data_dir / "train.jsonl"
    observed_train = artifact(train_path)
    if (
        observed_train["sha256"] != contract["training_data"]["sha256"]
        or observed_train["bytes"] != int(contract["training_data"]["bytes"])
    ):
        raise ValueError("Formal train JSONL drift")
    with train_path.open("r", encoding="utf-8") as source:
        rows = sum(1 for line in source if line.strip())
    if rows != int(contract["training_data"]["rows"]):
        raise ValueError("Formal train row-count drift")
    if stat.S_IMODE(data_dir.stat().st_mode) != 0o700 or stat.S_IMODE(train_path.stat().st_mode) != 0o600:
        raise PermissionError("Formal private training paths have unsafe permissions")
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(train_path)], cwd=REPO_ROOT
    )
    if ignored.returncode != 0:
        raise ValueError("Formal private training file is not gitignored")
    dry = load_json(resolve_project_path(contract["frozen_artifacts"]["dry_run_verification"]["path"]))
    if (
        dry.get("verification_id") != "EXP-047-RUNNER-DRY-RUN-VERIFY-V1"
        or dry.get("status") != "Passed"
        or dry.get("checks_passed") != 11
        or dry.get("mismatches") != []
        or dry.get("training_executed") is not False
        or dry.get("validation_split_accessed") is not False
        or dry.get("test_split_accessed") is not False
    ):
        raise ValueError("Frozen EXP-047 dry-run verification is invalid")
    for key, experiment in (("exp_044_verification", "EXP-044"), ("exp_046_verification", "EXP-046")):
        parent = load_json(resolve_project_path(contract["frozen_artifacts"][key]["path"]))
        if parent.get("experiment_id") != experiment or parent.get("status") != "Passed":
            raise ValueError(f"Frozen parent verification is invalid: {experiment}")
    return {
        "config": artifact(config_path),
        "formal_runtime": artifact(runtime_path),
        "private_data_gitignored": True,
        "private_directory_mode": "0700",
        "private_train_mode": "0600",
        "train_data": observed_train,
        "train_rows": rows,
    }


def verify_predecessors(contract: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "seed_42_replay_verification": (42, "EXP-047-SEED-42-REPLAY-VERIFY-V2"),
        "seed_42_training_verification": (42, "EXP-047-FORMAL-SEED-42-TRAIN-VERIFY-V2"),
        "seed_43_replay_verification": (43, "EXP-047-SEED-43-REPLAY-VERIFY-V1"),
        "seed_43_training_verification": (43, "EXP-047-FORMAL-SEED-43-ATTEMPT-2-TRAIN-VERIFY-V1"),
    }
    observed: dict[str, Any] = {}
    for key, (seed, verification_id) in expected.items():
        path = resolve_project_path(contract["frozen_artifacts"][key]["path"])
        verification = load_json(path)
        if (
            verification.get("experiment_id") != EXPERIMENT_ID
            or verification.get("seed") != seed
            or verification.get("verification_id") != verification_id
            or verification.get("status") != "Passed"
            or verification.get("validation_split_accessed") is not False
            or verification.get("test_split_accessed") is not False
            or verification.get("remaining_training_seeds_authorized") is not False
        ):
            raise ValueError(f"Invalid predecessor evidence: {key}")
        observed[key] = artifact(path)
    return observed


def recompute(contract: dict[str, Any]) -> dict[str, Any]:
    python = Path(contract["runtime"]["python_executable"])
    test_path = resolve_project_path(contract["implementation"]["test"]["path"])
    checks = {
        "formal_static_tests": run_checked([str(python), str(test_path)]),
    }
    return {
        "environment": verify_environment(contract),
        "model": verify_model(contract),
        "predecessors": verify_predecessors(contract),
        "runtime_and_data": verify_runtime_and_data(contract),
        "subprocess_checks": checks,
    }


def build_verification(contract: dict[str, Any], completed_at_utc: str) -> dict[str, Any]:
    return {
        "accessed_splits": ["train"],
        "completed_at_utc": completed_at_utc,
        "contract": artifact(CONTRACT_PATH),
        "experiment_id": EXPERIMENT_ID,
        "formal_training_authorized": False,
        "implementation": {
            "imports_runner": False,
            "verifier": artifact(Path(__file__).resolve()),
        },
        "model_forward_or_backward_executed": False,
        "next_required_step": "Bind this seed-44-only authorization and execute once; validation/test remain closed.",
        "outputs_absent_at_verification": True,
        "recalculated": recompute(contract),
        "seed": 44,
        "status": "Passed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
        "verification_id": VERIFICATION_ID,
    }


def require_outputs_absent(contract: dict[str, Any]) -> None:
    paths = [resolve_project_path(contract["outputs"][key]) for key in ("adapter_dir", "run_dir")]
    present = [display_path(path) for path in paths if path.exists()]
    if present:
        raise FileExistsError(f"Formal outputs already exist before authorization: {present}")


def main() -> None:
    args = parse_args()
    contract = load_contract()
    verification_path = resolve_project_path(contract["outputs"]["gate_verification"])
    if args.check:
        existing = load_json(verification_path)
        expected = build_verification(contract, str(existing.get("completed_at_utc")))
        if existing != expected:
            raise ValueError("Stored formal gate verification differs from recomputation")
        print(json.dumps({"path": display_path(verification_path), "status": "Passed"}, sort_keys=True))
        return
    require_outputs_absent(contract)
    if verification_path.exists():
        raise FileExistsError(verification_path)
    verification = build_verification(contract, datetime.now(timezone.utc).isoformat())
    write_json(verification_path, verification)
    print(json.dumps({"path": display_path(verification_path), "status": "Passed"}, sort_keys=True))


if __name__ == "__main__":
    main()
