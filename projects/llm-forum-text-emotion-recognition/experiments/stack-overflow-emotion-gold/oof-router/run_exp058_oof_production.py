#!/usr/bin/env python3
"""Run authorized five-fold M1/M3 EXP-058 OOF production."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time
from typing import Any, Iterable, Sequence


EXPERIMENT_ID = "EXP-058"
STAGE = "paired-m1-m3-oof-production"
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
TRAIN_FIELDS = {
    "component_id",
    "label_cardinality",
    "labels",
    "neutral",
    "protocol_id",
    "sample_id",
    "schema_version",
    "text",
}
MANIFEST_FIELDS = {
    "component_id",
    "experiment_id",
    "fold_id",
    "protocol_id",
    "sample_id",
    "schema_version",
}
PUBLIC_SENSITIVE_KEYS = {
    "component_id",
    "component_ids",
    "gold",
    "labels",
    "logits",
    "prediction",
    "predictions",
    "probabilities",
    "sample_id",
    "sample_ids",
    "text",
}

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-058-oof-production.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def resolve_project(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Project-relative path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(resolved)


def atomic_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if private:
        os.chmod(temporary, 0o600)
    temporary.replace(path)
    if private:
        os.chmod(path, 0o600)


def artifact(path: Path) -> dict[str, Any]:
    return {"path": display_path(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def tree_artifact(path: Path) -> dict[str, Any]:
    files = []
    total = 0
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        relative = str(child.relative_to(path))
        size = child.stat().st_size
        total += size
        files.append({"path": relative, "bytes": size, "sha256": sha256(child)})
    return {
        "path": display_path(path),
        "file_count": len(files),
        "bytes": total,
        "sha256": canonical_digest(files),
        "files": files,
    }


def require_record(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Frozen artifact drift: {path}")
    return path


def load_json_record(record: dict[str, Any]) -> dict[str, Any]:
    return json.loads(require_record(record).read_text(encoding="utf-8"))


def dynamic_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    return {"commit": commit, "dirty": bool(status), "dirty_path_count": len(status)}


def package_versions(names: Iterable[str]) -> dict[str, str]:
    result = {"python": platform.python_version()}
    for name in names:
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = "not-installed"
    return result


def peak_rss_gb() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / 1e9 if platform.system() == "Darwin" else value * 1024 / 1e9


def private_tree_permissions(path: Path) -> None:
    for directory in [path, *(item for item in path.rglob("*") if item.is_dir())]:
        os.chmod(directory, 0o700)
    for child in (item for item in path.rglob("*") if item.is_file()):
        os.chmod(child, 0o600)


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in PUBLIC_SENSITIVE_KEYS:
                violations.append(path)
            violations.extend(public_sensitive_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    return violations


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID or config.get("stage") != STAGE:
        raise ValueError("Unexpected EXP-058 production identity")
    if config.get("tier") != "Major":
        raise ValueError("Full OOF production must remain Major")
    auth = config["authorization"]
    true_keys = ("assembly", "full_oof_training", "heldout_forward", "model_loading")
    false_keys = (
        "calibration",
        "metrics",
        "oracle_analysis",
        "router_training",
        "test_access",
        "validation_access",
    )
    if any(auth.get(key) is not True for key in true_keys):
        raise PermissionError("Required full-OOF action is not authorized")
    if any(auth.get(key) is not False for key in false_keys):
        raise PermissionError("Full-OOF authorization exceeds the registered scope")
    if auth.get("fold_ids") != [0, 1, 2, 3, 4] or auth.get("model_seed") != 42:
        raise PermissionError("Full OOF is restricted to folds 0-4 and seed 42")
    execution = config["execution"]
    if execution.get("fold_ids") != [0, 1, 2, 3, 4]:
        raise ValueError("Execution fold list drift")
    if execution.get("m1_epochs") != 4 or execution.get("m3_epochs") != 2:
        raise ValueError("Frozen OOF epoch contract drift")
    for record in config["implementation"].values():
        require_record(record)
    for record in config["prerequisites"].values():
        require_record(record)
    require_record(config["data"]["train"])
    return config


def verify_prerequisites(config: dict[str, Any]) -> dict[str, Any]:
    fold_verification = load_json_record(config["prerequisites"]["fold_verification"])
    if (
        fold_verification.get("status") != "Passed"
        or fold_verification.get("check_count") != 131
        or fold_verification.get("passed_count") != 131
        or fold_verification.get("failed_count") != 0
    ):
        raise RuntimeError("Fold manifest is not independently verified")
    dry_run = load_json_record(config["prerequisites"]["dry_run"])
    dry_verification = load_json_record(config["prerequisites"]["dry_run_verification"])
    if (
        dry_run.get("status") != "CompletedAwaitingVerification"
        or dry_run.get("stages", {}).get("m1", {}).get("status") != "Passed"
        or dry_run.get("stages", {}).get("m3", {}).get("status") != "Passed"
        or dry_verification.get("status") != "Passed"
        or dry_verification.get("check_count") != 114
        or dry_verification.get("passed_count") != 114
        or dry_verification.get("failed_count") != 0
    ):
        raise RuntimeError("Fold-0 consumer dry-run gate is not verified")
    contract = load_json_record(config["prerequisites"]["consumer_contract"])
    manifest_path = require_record(config["prerequisites"]["fold_manifest"])
    if contract.get("fold_manifest_sha256") != sha256(manifest_path):
        raise ValueError("Consumer contract and fold manifest disagree")
    if contract.get("forbidden_splits") != ["validation", "test"]:
        raise ValueError("Consumer split boundary drift")

    m1_run = load_json_record(config["prerequisites"]["m1_seed_42_run"])
    m1_verification = load_json_record(config["prerequisites"]["m1_seed_42_verification"])
    m3_run = load_json_record(config["prerequisites"]["m3_seed_42_run"])
    m3_verification = load_json_record(config["prerequisites"]["m3_seed_42_verification"])
    if m1_run.get("status") != "Completed" or m1_verification.get("status") != "Passed":
        raise RuntimeError("Verified M1 seed-42 metadata is unavailable")
    if (
        m3_run.get("status") != "Completed"
        or m3_verification.get("status") != "Passed"
        or m3_verification.get("checks_passed") != 148
        or m3_verification.get("checks_total") != 148
        or m3_verification.get("failed_checks") != []
    ):
        raise RuntimeError("Verified M3 seed-42 metadata is unavailable")
    if m1_run["selection"]["selected_epoch"] != 4 or m3_run["selection"]["selected_epoch"] != 2:
        raise ValueError("Selected epoch metadata drift")
    if m1_run.get("test_split_accessed") or m3_run.get("test_split_accessed"):
        raise PermissionError("Prerequisite test boundary drift")
    shared = load_json_record(config["prerequisites"]["shared_config"])
    if shared["data"]["test_status"] != "sealed_not_authorized_for_model_access":
        raise PermissionError("Shared test contract drift")
    return {"shared": shared, "m1_run": m1_run, "m3_run": m3_run}


def load_partitions(config: dict[str, Any]) -> dict[str, Any]:
    train_path = require_record(config["data"]["train"])
    manifest_path = require_record(config["prerequisites"]["fold_manifest"])
    manifest_before = sha256(manifest_path)
    train_rows = read_jsonl(train_path)
    manifest_rows = read_jsonl(manifest_path)
    if len(train_rows) != 3360 or len(manifest_rows) != 3360:
        raise ValueError("EXP-058 train/manifest row count drift")
    train_by_id: dict[str, dict[str, Any]] = {}
    for row in train_rows:
        if set(row) != TRAIN_FIELDS or row.get("protocol_id") != "DATA-SO-TASK-V1":
            raise ValueError("Train schema or protocol drift")
        if row["sample_id"] in train_by_id:
            raise ValueError("Duplicate train sample ID")
        if len(row["labels"]) != len(LABELS) or any(value not in (0, 1) for value in row["labels"]):
            raise ValueError("Invalid train label vector")
        cardinality = sum(row["labels"])
        if row["label_cardinality"] != cardinality or row["neutral"] != (cardinality == 0):
            raise ValueError("Train derived-field drift")
        train_by_id[row["sample_id"]] = row
    assignments: dict[str, dict[str, Any]] = {}
    for row in manifest_rows:
        if set(row) != MANIFEST_FIELDS or row.get("experiment_id") != EXPERIMENT_ID:
            raise ValueError("Fold manifest schema drift")
        if row["sample_id"] in assignments or row["fold_id"] not in range(5):
            raise ValueError("Invalid fold assignment")
        assignments[row["sample_id"]] = row
    if set(assignments) != set(train_by_id):
        raise ValueError("Fold manifest does not cover train exactly")
    for sample_id, row in train_by_id.items():
        if assignments[sample_id]["component_id"] != row["component_id"]:
            raise ValueError("Manifest component identity drift")

    partitions: dict[int, dict[str, Any]] = {}
    for fold_id in range(5):
        heldout = [row for row in train_rows if assignments[row["sample_id"]]["fold_id"] == fold_id]
        training = [row for row in train_rows if assignments[row["sample_id"]]["fold_id"] != fold_id]
        if len(training) != 2688 or len(heldout) != 672:
            raise ValueError(f"Fold {fold_id} partition size drift")
        training_components = {row["component_id"] for row in training}
        heldout_components = {row["component_id"] for row in heldout}
        if training_components & heldout_components:
            raise ValueError(f"Fold {fold_id} duplicate-component leakage")
        partitions[fold_id] = {
            "training": training,
            "heldout": heldout,
            "training_order_sha256": canonical_digest([row["sample_id"] for row in training]),
            "heldout_order_sha256": canonical_digest([row["sample_id"] for row in heldout]),
        }
    return {
        "all": train_rows,
        "assignments": assignments,
        "partitions": partitions,
        "manifest_path": manifest_path,
        "manifest_before": manifest_before,
    }


def m1_schedule(config: dict[str, Any], training_rows: int) -> dict[str, int]:
    batch_size = int(config["m1"]["batch_size"])
    steps_per_epoch = math.ceil(training_rows / batch_size)
    planned_epochs = int(config["m1"]["planned_scheduler_epochs"])
    stop_epoch = int(config["execution"]["m1_epochs"])
    horizon = steps_per_epoch * planned_epochs
    warmup_exact = horizon * float(config["m1"]["warmup_ratio"])
    if not warmup_exact.is_integer():
        raise ValueError("M1 warmup is not integral")
    schedule = {
        "steps_per_epoch": steps_per_epoch,
        "planned_scheduler_epochs": planned_epochs,
        "scheduler_horizon_steps": horizon,
        "warmup_steps": int(warmup_exact),
        "selected_stop_epoch": stop_epoch,
        "selected_stop_steps": steps_per_epoch * stop_epoch,
    }
    if schedule != config["m1"]["expected_schedule"]:
        raise ValueError("M1 production schedule drift")
    return schedule


def verify_model_files(shared: dict[str, Any], family: str) -> dict[str, Any]:
    if family == "m1":
        spec = shared["models"]["m1"]
        manifest_path = resolve_project(spec["manifest_path"])
        root = resolve_project(spec["local_path"])
        manifest_key = "files"
    elif family == "m3":
        spec = shared["models"]["qwen_shared"]
        manifest_path = resolve_project(spec["manifest_path"])
        root = resolve_project(spec["local_path"])
        manifest_key = "mlx_bf16"
    else:
        raise ValueError(f"Unknown model family: {family}")
    if sha256(manifest_path) != spec["manifest_sha256"]:
        raise ValueError(f"{family} model manifest drift")
    content = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = content["files"] if manifest_key == "files" else content[manifest_key]["files"]
    for record in files:
        path = root / record["path"]
        if path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
            raise ValueError(f"Model asset drift: {path}")
    return {"manifest": artifact(manifest_path), "file_count": len(files)}


def public_run_dir(config: dict[str, Any]) -> Path:
    return resolve_project(config["outputs"]["public_run_dir"])


def private_run_dir(config: dict[str, Any]) -> Path:
    return resolve_project(config["outputs"]["private_run_dir"])


def fold_dirs(config: dict[str, Any], family: str, fold_id: int) -> tuple[Path, Path]:
    return (
        public_run_dir(config) / f"fold-{fold_id}" / family,
        private_run_dir(config) / f"fold-{fold_id}" / family,
    )


def log_line(run_dir: Path, stage: str, message: str) -> None:
    line = f"[{utc_now()}] [{stage}] {message}"
    print(line, flush=True)
    with (run_dir / "stdout.log").open("a", encoding="utf-8") as target:
        target.write(line + "\n")


def freeze_sources(run_dir: Path, config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    frozen = run_dir / "frozen-sources"
    frozen.mkdir(parents=True)
    records: dict[str, Any] = {}
    config_target = frozen / "config.json"
    shutil.copy2(config_path, config_target)
    records["config"] = artifact(config_target)
    for name, record in config["implementation"].items():
        source = require_record(record)
        suffix = source.suffix or ".txt"
        target = frozen / f"{name}{suffix}"
        shutil.copy2(source, target)
        records[name] = artifact(target)
    return records


def initialize(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    prerequisites = verify_prerequisites(config)
    partitions = load_partitions(config)
    run_dir = public_run_dir(config)
    private_dir = private_run_dir(config)
    if run_dir.exists() or private_dir.exists():
        raise FileExistsError("Refusing to overwrite append-only OOF production output")
    free_gb = shutil.disk_usage(PROJECT_ROOT).free / 1e9
    if free_gb < float(config["resources"]["minimum_free_disk_gb"]):
        raise OSError("Insufficient free disk for checkpointed OOF production")
    run_dir.mkdir(parents=True)
    private_dir.mkdir(parents=True, mode=0o700)
    os.chmod(private_dir, 0o700)
    frozen_sources = freeze_sources(run_dir, config_path, config)
    partition_contract_path = private_dir / "partition-contract.json"
    atomic_json(
        partition_contract_path,
        {
            "schema_version": "exp-058-oof-partition-contract-v1",
            "manifest_sha256": partitions["manifest_before"],
            "folds": {
                str(fold_id): {
                    "training_sample_ids": [
                        row["sample_id"] for row in partitions["partitions"][fold_id]["training"]
                    ],
                    "heldout_sample_ids": [
                        row["sample_id"] for row in partitions["partitions"][fold_id]["heldout"]
                    ],
                }
                for fold_id in range(5)
            },
        },
        private=True,
    )
    now = utc_now()
    run = {
        "schema_version": "exp-058-oof-production-run-v1",
        "experiment_id": EXPERIMENT_ID,
        "rq_id": "RQ-S3",
        "tier": "Major",
        "stage": STAGE,
        "status": "InProgress",
        "started_at_utc": now,
        "working_directory": str(PROJECT_ROOT),
        "git": git_metadata(),
        "authorization": config["authorization"],
        "data": {
            "protocol_id": config["data"]["protocol_id"],
            "train_rows": 3360,
            "duplicate_components": 3277,
            "fold_count": 5,
            "rows_per_fold": 672,
            "training_rows_per_fold": 2688,
            "label_order": list(LABELS),
            "train_sha256": config["data"]["train"]["sha256"],
            "fold_manifest_sha256": partitions["manifest_before"],
        },
        "split_access": {
            "accessed_splits": ["train"],
            "validation_accessed": False,
            "test_inputs_accessed": False,
            "test_labels_accessed": False,
        },
        "model_execution": {
            "performance_metrics_computed": False,
            "calibration_performed": False,
            "oracle_analysis_performed": False,
            "router_training_performed": False,
        },
        "stages": {
            "initialize": {"status": "Passed", "completed_at_utc": now},
            "m1": {"folds": {str(fold): {"status": "Pending"} for fold in range(5)}},
            "m3": {"folds": {str(fold): {"status": "Pending"} for fold in range(5)}},
            "assembly": {"status": "Pending"},
        },
        "resources": {
            "minimum_free_disk_gb": config["resources"]["minimum_free_disk_gb"],
            "free_disk_gb_at_start": free_gb,
            "api_cost_usd": 0,
        },
        "frozen_sources": frozen_sources,
        "artifacts": {"partition_contract_private": artifact(partition_contract_path)},
        "claim_boundary": "Train-only OOF-logit production; no performance evidence.",
    }
    violations = public_sensitive_paths(run)
    if violations:
        raise ValueError(f"Public initialization contains row-level fields: {violations}")
    atomic_json(run_dir / "run.json", run)
    log_line(run_dir, "initialize", "verified five partitions and froze production sources")
    return run


def load_top_run(config: dict[str, Any]) -> dict[str, Any]:
    path = public_run_dir(config) / "run.json"
    if not path.is_file():
        raise FileNotFoundError("Production initialization has not completed")
    run = json.loads(path.read_text(encoding="utf-8"))
    if run.get("experiment_id") != EXPERIMENT_ID or run.get("stage") != STAGE:
        raise ValueError("Production run identity drift")
    return run


def verification_path(config: dict[str, Any], family: str, fold_id: int) -> Path:
    return fold_dirs(config, family, fold_id)[0] / "verification.json"


def require_passed_fold(config: dict[str, Any], family: str, fold_id: int) -> dict[str, Any]:
    path = verification_path(config, family, fold_id)
    if not path.is_file():
        raise RuntimeError(f"{family} fold {fold_id} has not been independently verified")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("status") != "Passed" or value.get("failed_count") != 0:
        raise RuntimeError(f"{family} fold {fold_id} verification did not pass")
    return value


def completed_family_seconds(config: dict[str, Any], family: str) -> float:
    total = 0.0
    for fold_id in range(5):
        path = fold_dirs(config, family, fold_id)[0] / "run.json"
        if not path.is_file():
            continue
        run = json.loads(path.read_text(encoding="utf-8"))
        if run.get("status") == "CompletedAwaitingVerification":
            total += float(run["resources"]["wall_seconds"])
    return total


def begin_fold(config: dict[str, Any], family: str, fold_id: int) -> tuple[Path, Path, float]:
    if family not in ("m1", "m3") or fold_id not in range(5):
        raise ValueError("Invalid OOF family/fold")
    top = load_top_run(config)
    if top.get("status") not in ("InProgress", "BlockedByFailure"):
        raise RuntimeError("Production run is not open for fold execution")
    if top["stages"][family]["folds"][str(fold_id)]["status"] != "Pending":
        raise RuntimeError(f"{family} fold {fold_id} is not pending")
    if fold_id > 0:
        require_passed_fold(config, family, fold_id - 1)
    if family == "m3":
        for prior_fold in range(5):
            require_passed_fold(config, "m1", prior_fold)
    public_fold, private_fold = fold_dirs(config, family, fold_id)
    if public_fold.exists() or private_fold.exists():
        raise FileExistsError(f"Refusing to overwrite {family} fold {fold_id}")
    public_fold.mkdir(parents=True)
    private_fold.mkdir(parents=True, mode=0o700)
    os.chmod(private_fold, 0o700)
    top["status"] = "InProgress"
    top["stages"][family]["folds"][str(fold_id)] = {
        "status": "InProgress",
        "started_at_utc": utc_now(),
    }
    atomic_json(public_run_dir(config) / "run.json", top)
    initial = {
        "schema_version": "exp-058-oof-fold-run-v1",
        "experiment_id": EXPERIMENT_ID,
        "rq_id": "RQ-S3",
        "tier": "Major",
        "stage": STAGE,
        "family": family,
        "fold_id": fold_id,
        "model_seed": 42,
        "status": "InProgress",
        "started_at_utc": utc_now(),
        "split_access": {
            "accessed_splits": ["train"],
            "validation_accessed": False,
            "test_inputs_accessed": False,
            "test_labels_accessed": False,
        },
        "performance_metrics_computed": False,
    }
    atomic_json(public_fold / "run.json", initial)
    return public_fold, private_fold, completed_family_seconds(config, family)


def finish_fold(
    config: dict[str, Any], family: str, fold_id: int, fold_run: dict[str, Any]
) -> dict[str, Any]:
    public_fold, _ = fold_dirs(config, family, fold_id)
    if public_sensitive_paths(fold_run):
        raise ValueError("Public fold run contains row-level fields")
    atomic_json(public_fold / "run.json", fold_run)
    top = load_top_run(config)
    top["stages"][family]["folds"][str(fold_id)] = {
        "status": "CompletedAwaitingVerification",
        "completed_at_utc": fold_run["completed_at_utc"],
        "run": artifact(public_fold / "run.json"),
    }
    atomic_json(public_run_dir(config) / "run.json", top)
    return fold_run


def record_failure(config: dict[str, Any], family: str, fold_id: int, error: Exception) -> None:
    public_fold, _ = fold_dirs(config, family, fold_id)
    if not public_fold.is_dir():
        return
    failure = {
        "schema_version": "exp-058-oof-fold-failure-v1",
        "experiment_id": EXPERIMENT_ID,
        "family": family,
        "fold_id": fold_id,
        "status": "Failed",
        "failed_at_utc": utc_now(),
        "error_type": type(error).__name__,
        "error": str(error),
        "validation_accessed": False,
        "test_accessed": False,
    }
    atomic_json(public_fold / "failure.json", failure)
    run_path = public_fold / "run.json"
    if run_path.is_file():
        fold_run = json.loads(run_path.read_text(encoding="utf-8"))
        fold_run["status"] = "Failed"
        fold_run["failed_at_utc"] = failure["failed_at_utc"]
        fold_run["failure"] = artifact(public_fold / "failure.json")
        atomic_json(run_path, fold_run)
    top = load_top_run(config)
    top["status"] = "BlockedByFailure"
    top["stages"][family]["folds"][str(fold_id)] = {
        "status": "Failed",
        "failure": artifact(public_fold / "failure.json"),
    }
    atomic_json(public_run_dir(config) / "run.json", top)


def write_history(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("Cannot write empty training history")
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save_npy_private(path: Path, value: Any, np: Any) -> None:
    temporary = path.with_name(path.name + ".tmp.npy")
    np.save(temporary, value, allow_pickle=False)
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)


def save_npz_private(path: Path, np: Any, **arrays: Any) -> None:
    temporary = path.with_name(path.name + ".tmp.npz")
    np.savez_compressed(temporary, **arrays)
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)


def run_m1_fold(config: dict[str, Any], fold_id: int) -> dict[str, Any]:
    public_fold, private_fold, prior_family_seconds = begin_fold(config, "m1", fold_id)
    started_at = utc_now()
    started = time.perf_counter()
    prerequisites = verify_prerequisites(config)
    shared = prerequisites["shared"]
    partition_bundle = load_partitions(config)
    partition = partition_bundle["partitions"][fold_id]
    model_assets = verify_model_files(shared, "m1")
    reference = dynamic_module(
        f"exp058_m1_reference_fold_{fold_id}",
        require_record(config["implementation"]["m1_runner_reference"]),
    )
    np = reference.np
    torch = reference.torch
    spec = shared["models"]["m1"]
    model_path = resolve_project(spec["local_path"])
    log_line(public_fold, "m1", "verified model assets and train-only fold partition")

    tokenizer = reference.AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    train_encodings, train_token_summary = reference.encode_rows(
        tokenizer, partition["training"], int(spec["max_sequence_length"])
    )
    heldout_encodings, heldout_token_summary = reference.encode_rows(
        tokenizer, partition["heldout"], int(spec["max_sequence_length"])
    )
    train_gold = np.asarray([row["labels"] for row in partition["training"]], dtype=np.uint8)
    train_dataset = reference.EncodedDataset(train_encodings, train_gold)
    collator = reference.make_collator(tokenizer)

    seed = int(config["authorization"]["model_seed"])
    reference.seed_everything(seed, "cpu")
    model = reference.AutoModelForSequenceClassification.from_pretrained(
        model_path,
        local_files_only=True,
        num_labels=len(LABELS),
        id2label={index: label for index, label in enumerate(LABELS)},
        label2id={label: index for index, label in enumerate(LABELS)},
        problem_type="multi_label_classification",
        ignore_mismatched_sizes=True,
    )
    if type(model.classifier).__name__ != "RobertaClassificationHead":
        raise ValueError("M1 classification head contract drift")
    initial_classifier = reference.tensor_digest(
        {name: value for name, value in model.named_parameters() if name.startswith("classifier.")}
    )
    if initial_classifier != config["m1"]["expected_classifier_initial_sha256"]:
        raise ValueError("M1 fresh classifier initialization drift")
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    trainable_count = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    if parameter_count != trainable_count:
        raise ValueError("M1 OOF must preserve full fine-tuning")

    schedule = m1_schedule(config, len(partition["training"]))
    optimizer = torch.optim.AdamW(
        reference.optimizer_groups(
            model, float(spec["weight_decay"]), config["m1"]["weight_decay_exclusions"]
        ),
        lr=float(spec["learning_rate"]),
        betas=(0.9, 0.999),
        eps=1e-8,
    )
    scheduler = reference.LambdaLR(
        optimizer,
        lambda step: reference.linear_schedule(
            step, schedule["warmup_steps"], schedule["scheduler_horizon_steps"]
        ),
    )
    generator = torch.Generator().manual_seed(seed)
    batch_orders = [
        torch.randperm(len(train_dataset), generator=generator).tolist()
        for _ in range(int(config["execution"]["m1_epochs"]))
    ]
    batch_orders_path = private_fold / "batch-orders.npy"
    save_npy_private(batch_orders_path, np.asarray(batch_orders, dtype=np.int32), np)
    history: list[dict[str, Any]] = []
    global_step = 0
    model.train()
    for epoch, order in enumerate(batch_orders, start=1):
        epoch_started = time.perf_counter()
        loader = reference.DataLoader(
            reference.Subset(train_dataset, order),
            batch_size=int(spec["batch_size"]),
            shuffle=False,
            drop_last=False,
            num_workers=0,
            collate_fn=collator,
        )
        loss_sum = 0.0
        examples = 0
        for batch_index, batch in enumerate(loader, start=1):
            labels = batch.pop("labels")
            optimizer.zero_grad(set_to_none=True)
            logits = model(**batch).logits
            if tuple(logits.shape) != (labels.shape[0], len(LABELS)):
                raise ValueError("M1 logit shape drift")
            loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels)
            if not torch.isfinite(loss):
                raise ValueError(f"Non-finite M1 loss at epoch {epoch}, batch {batch_index}")
            loss.backward()
            gradient_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            if not torch.isfinite(gradient_norm):
                raise ValueError("Non-finite M1 gradient norm")
            optimizer.step()
            scheduler.step()
            batch_rows = int(labels.shape[0])
            loss_sum += float(loss.detach()) * batch_rows
            examples += batch_rows
            global_step += 1
            elapsed = time.perf_counter() - started
            if prior_family_seconds + elapsed > float(config["resources"]["m1_total_wall_hours"]) * 3600:
                raise TimeoutError("M1 family exceeded its frozen total wall-time budget")
            if batch_index % 50 == 0 or batch_index == schedule["steps_per_epoch"]:
                log_line(
                    public_fold,
                    "m1",
                    f"epoch {epoch} step {batch_index}/{schedule['steps_per_epoch']} "
                    f"mean_loss={loss_sum / examples:.6f}",
                )
        history.append(
            {
                "epoch": epoch,
                "optimizer_steps": global_step,
                "train_loss": loss_sum / examples,
                "learning_rate_end": float(optimizer.param_groups[0]["lr"]),
                "batch_order_sha256": canonical_digest(
                    [partition["training"][index]["sample_id"] for index in order]
                ),
                "epoch_seconds": time.perf_counter() - epoch_started,
            }
        )
    if global_step != schedule["selected_stop_steps"] or len(history) != 4:
        raise ValueError("M1 OOF completion-count drift")

    final_classifier = reference.tensor_digest(
        {name: value for name, value in model.named_parameters() if name.startswith("classifier.")}
    )
    if final_classifier == initial_classifier:
        raise ValueError("M1 classifier did not update")
    model.eval()
    heldout_logits: list[Any] = []
    eval_batch_size = int(config["m1"]["heldout_batch_size"])
    with torch.no_grad():
        for start in range(0, len(partition["heldout"]), eval_batch_size):
            stop = min(start + eval_batch_size, len(partition["heldout"]))
            features = [
                {key: values[index] for key, values in heldout_encodings.items()}
                for index in range(start, stop)
            ]
            batch = tokenizer.pad(features, padding=True, return_tensors="pt")
            values = model(**batch).logits.float().cpu()
            if not torch.isfinite(values).all():
                raise ValueError("M1 held-out logits are non-finite")
            heldout_logits.append(values.numpy())
            if stop % 160 == 0 or stop == len(partition["heldout"]):
                log_line(public_fold, "m1", f"held-out forward {stop}/{len(partition['heldout'])}")
    heldout_logits_array = np.concatenate(heldout_logits, axis=0).astype(np.float32, copy=False)
    if heldout_logits_array.shape != (672, len(LABELS)):
        raise ValueError("M1 held-out logit matrix shape drift")

    checkpoint_dir = private_fold / "final-model"
    model.save_pretrained(checkpoint_dir, safe_serialization=True)
    private_tree_permissions(checkpoint_dir)
    checkpoint = tree_artifact(checkpoint_dir)
    predictions_path = private_fold / "heldout-logits.npz"
    save_npz_private(
        predictions_path,
        np,
        sample_ids=np.asarray([row["sample_id"] for row in partition["heldout"]]),
        component_ids=np.asarray([row["component_id"] for row in partition["heldout"]]),
        fold_ids=np.full(len(partition["heldout"]), fold_id, dtype=np.int8),
        gold=np.asarray([row["labels"] for row in partition["heldout"]], dtype=np.uint8),
        logits=heldout_logits_array,
        character_lengths=np.asarray([len(row["text"]) for row in partition["heldout"]], dtype=np.int32),
        token_lengths=np.asarray([len(ids) for ids in heldout_encodings["input_ids"]], dtype=np.int32),
    )
    evidence_path = private_fold / "evidence.json"
    manifest_after = sha256(partition_bundle["manifest_path"])
    if manifest_after != partition_bundle["manifest_before"]:
        raise ValueError("Fold manifest changed during M1 production")
    atomic_json(
        evidence_path,
        {
            "schema_version": "exp-058-m1-oof-fold-evidence-v1",
            "fold_id": fold_id,
            "model_seed": seed,
            "training_order_sha256": partition["training_order_sha256"],
            "heldout_order_sha256": partition["heldout_order_sha256"],
            "training_rows": len(partition["training"]),
            "heldout_rows": len(partition["heldout"]),
            "batch_order_sha256": [row["batch_order_sha256"] for row in history],
            "scheduler": schedule,
            "classifier_initial_sha256": initial_classifier,
            "classifier_final_sha256": final_classifier,
            "train_token_summary": train_token_summary,
            "heldout_token_summary": heldout_token_summary,
            "manifest_sha256_before": partition_bundle["manifest_before"],
            "manifest_sha256_after": manifest_after,
            "heldout_labels_used_for_forward": False,
        },
        private=True,
    )
    history_path = public_fold / "history.csv"
    write_history(history_path, history)
    wall_seconds = time.perf_counter() - started
    if prior_family_seconds + wall_seconds > float(config["resources"]["m1_total_wall_hours"]) * 3600:
        raise TimeoutError("M1 family exceeded its frozen total wall-time budget")
    peak_memory = peak_rss_gb()
    if peak_memory > float(config["resources"]["m1_peak_process_memory_gb"]):
        raise MemoryError("M1 fold exceeded its memory budget")
    completed_at = utc_now()
    fold_run = {
        "schema_version": "exp-058-oof-fold-run-v1",
        "experiment_id": EXPERIMENT_ID,
        "rq_id": "RQ-S3",
        "tier": "Major",
        "stage": STAGE,
        "family": "m1",
        "fold_id": fold_id,
        "model_seed": seed,
        "status": "CompletedAwaitingVerification",
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "invocation": " ".join(sys.argv),
        "working_directory": str(PROJECT_ROOT),
        "git": git_metadata(),
        "environment": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "executable": sys.executable,
            "packages": package_versions(("numpy", "torch", "transformers")),
        },
        "data": {
            "protocol_id": config["data"]["protocol_id"],
            "training_rows": 2688,
            "heldout_rows": 672,
            "training_order_sha256": partition["training_order_sha256"],
            "heldout_order_sha256": partition["heldout_order_sha256"],
            "fold_manifest_sha256": manifest_after,
            "sample_overlap": 0,
            "component_overlap": 0,
            "label_order": list(LABELS),
        },
        "model": {
            "repo_id": spec["repo_id"],
            "revision": spec["revision"],
            "precision": spec["precision"],
            "parameter_count": parameter_count,
            "trainable_parameter_count": trainable_count,
            "classifier_initial_sha256": initial_classifier,
            "classifier_final_sha256": final_classifier,
            "model_asset_files_verified": model_assets["file_count"],
        },
        "training": {
            "epochs": 4,
            "batch_size": int(spec["batch_size"]),
            "optimizer_steps": global_step,
            "loss": "unweighted_binary_cross_entropy_with_logits",
            "optimizer": "AdamW",
            "learning_rate": float(spec["learning_rate"]),
            "weight_decay": float(spec["weight_decay"]),
            "scheduler": schedule,
            "history": history,
        },
        "heldout_forward": {"rows": 672, "finite_logit_values": int(heldout_logits_array.size)},
        "split_access": {
            "accessed_splits": ["train"],
            "validation_accessed": False,
            "test_inputs_accessed": False,
            "test_labels_accessed": False,
        },
        "performance_metrics_computed": False,
        "resources": {
            "wall_seconds": wall_seconds,
            "prior_family_wall_seconds": prior_family_seconds,
            "cumulative_family_wall_seconds": prior_family_seconds + wall_seconds,
            "peak_process_rss_gb": peak_memory,
            "api_cost_usd": 0,
        },
        "privacy": {
            "public_raw_text": False,
            "public_row_identifiers": False,
            "private_artifacts_gitignored": True,
        },
        "artifacts": {
            "history": artifact(history_path),
            "batch_orders_private": artifact(batch_orders_path),
            "heldout_logit_table_private": artifact(predictions_path),
            "evidence_private": artifact(evidence_path),
            "final_checkpoint_private": checkpoint,
        },
        "claim_boundary": "One train-only M1 OOF fold; no thresholds, predictions, or metrics.",
    }
    log_line(public_fold, "m1", f"fold {fold_id} completed in {wall_seconds / 3600:.3f} h")
    del model, tokenizer, optimizer, scheduler, train_dataset
    gc.collect()
    return finish_fold(config, "m1", fold_id, fold_run)


def run_m3_fold(config: dict[str, Any], fold_id: int) -> dict[str, Any]:
    public_fold, private_fold, prior_family_seconds = begin_fold(config, "m3", fold_id)
    started_at = utc_now()
    started = time.perf_counter()
    prerequisites = verify_prerequisites(config)
    shared = prerequisites["shared"]
    partition_bundle = load_partitions(config)
    partition = partition_bundle["partitions"][fold_id]
    model_assets = verify_model_files(shared, "m3")
    primitives = dynamic_module(
        f"exp058_qwen_primitives_fold_{fold_id}",
        require_record(config["implementation"]["qwen_primitives"]),
    )
    helpers = dynamic_module(
        f"exp058_m3_helpers_fold_{fold_id}",
        require_record(config["implementation"]["m3_preflight_reference"]),
    )

    import numpy as np
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx_lm import load
    from mlx_lm.tuner import linear_to_lora_layers
    from mlx_lm.tuner.trainer import grad_checkpoint

    os.environ.update(
        {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    )
    mx.reset_peak_memory()
    spec = shared["models"]["qwen_shared"]
    lora = shared["models"]["lora_shared"]
    model_path = resolve_project(spec["local_path"])
    log_line(public_fold, "m3", "verified model assets and train-only fold partition")
    model_load_started = time.perf_counter()
    model, tokenizer = load(str(model_path), lazy=False)
    model_load_seconds = time.perf_counter() - model_load_started
    model.freeze()
    model.eval()
    prompt = primitives.load_prompt(shared)
    tokenization_started = time.perf_counter()
    train_ids = [
        primitives.qwen_prompt_ids(
            tokenizer, prompt, row["text"], shared["prompt"]["max_sequence_length"]
        )
        for row in partition["training"]
    ]
    heldout_ids = [
        primitives.qwen_prompt_ids(
            tokenizer, prompt, row["text"], shared["prompt"]["max_sequence_length"]
        )
        for row in partition["heldout"]
    ]
    tokenization_seconds = time.perf_counter() - tokenization_started
    seed = int(config["authorization"]["model_seed"])
    head = primitives.build_qwen_head(seed, int(spec["hidden_size"]))
    head_initial = primitives.mlx_tensor_digest(primitives.mlx_trainable(head))
    if head_initial != config["m3"]["expected_head_initial_sha256"]:
        raise ValueError("M3 fresh head initialization drift")
    wrapper = primitives.make_classification_wrapper(model, head)

    first_ids = mx.array([train_ids[0]], dtype=mx.int32)
    base_logits = wrapper(first_ids)
    mx.eval(base_logits)
    mx.random.seed(seed + 100000)
    linear_to_lora_layers(
        model,
        int(lora["num_layers"]),
        {
            "rank": int(lora["rank"]),
            "scale": float(lora["scale"]),
            "dropout": float(lora["dropout"]),
            "keys": lora["target_modules"],
        },
    )
    observed = primitives.insertion_contract(model, shared)
    converted_logits = wrapper(first_ids)
    mx.eval(converted_logits)
    zero_delta = float(mx.max(mx.abs(base_logits - converted_logits)).item())
    lora_initial_items = primitives.mlx_trainable(model)
    lora_initial = primitives.mlx_tensor_digest(lora_initial_items)
    trainable_items = primitives.mlx_trainable(wrapper)
    unexpected = [name for name, _ in trainable_items if not helpers.trainable_name_allowed(name)]
    lora_count = sum(int(tensor.size) for _, tensor in lora_initial_items)
    total_count = sum(int(tensor.size) for _, tensor in trainable_items)
    if (
        zero_delta != 0.0
        or len(observed) != 112
        or lora_count != 7_340_032
        or total_count != 7_355_398
        or unexpected
    ):
        raise ValueError("M3 zero-step or trainable whitelist contract failed")
    if lora_initial != config["m3"]["expected_lora_initial_sha256"]:
        raise ValueError("M3 fresh LoRA initialization drift")
    base_before = helpers.frozen_parameter_sentinel(model)
    if base_before["sha256"] != config["m3"]["expected_base_sentinel_sha256"]:
        raise ValueError("M3 base sentinel drift before training")

    rng = np.random.default_rng(seed)
    batch_orders = np.stack(
        [rng.permutation(len(partition["training"])) for _ in range(int(config["execution"]["m3_epochs"]))]
    ).astype(np.int32)
    batch_orders_path = private_fold / "batch-orders.npy"
    save_npy_private(batch_orders_path, batch_orders, np)
    grad_checkpoint(model.layers[0])
    model.train()
    head_optimizer = optim.AdamW(
        learning_rate=float(spec["head_learning_rate"]),
        weight_decay=float(spec["head_weight_decay"]),
    )
    lora_optimizer = optim.AdamW(
        learning_rate=float(lora["learning_rate"]), weight_decay=float(lora["weight_decay"])
    )
    loss_and_grad = nn.value_and_grad(wrapper, primitives.classification_loss)
    history: list[dict[str, Any]] = []
    global_step = 0
    for epoch, order in enumerate(batch_orders, start=1):
        epoch_started = time.perf_counter()
        loss_sum = 0.0
        for position, row_index in enumerate(order, start=1):
            index = int(row_index)
            ids = mx.array([train_ids[index]], dtype=mx.int32)
            targets = mx.array([partition["training"][index]["labels"]], dtype=mx.float32)
            loss, gradients = loss_and_grad(wrapper, ids, targets)
            lora_optimizer.update(wrapper.backbone, gradients["backbone"])
            head_optimizer.update(wrapper.head, gradients["head"])
            mx.eval(loss, wrapper.trainable_parameters(), lora_optimizer.state, head_optimizer.state)
            value = float(loss.item())
            if not math.isfinite(value):
                raise ValueError(f"Non-finite M3 loss at epoch {epoch}, position {position}")
            loss_sum += value
            global_step += 1
            elapsed = time.perf_counter() - started
            peak_memory = float(mx.get_peak_memory()) / 1e9
            if peak_memory > float(config["resources"]["m3_peak_mlx_memory_gb"]):
                raise MemoryError("M3 fold exceeded its memory budget")
            if elapsed > float(config["resources"]["m3_per_fold_wall_hours"]) * 3600:
                raise TimeoutError("M3 fold exceeded its wall-time budget")
            if prior_family_seconds + elapsed > float(config["resources"]["m3_total_wall_hours"]) * 3600:
                raise TimeoutError("M3 family exceeded its total wall-time budget")
            if position % int(config["m3"]["log_every_steps"]) == 0 or position == len(order):
                log_line(
                    public_fold,
                    "m3",
                    f"epoch {epoch} step {position}/{len(order)} mean_loss={loss_sum / position:.6f} "
                    f"peak={peak_memory:.3f}GB",
                )
            if position % 250 == 0:
                mx.clear_cache()
        history.append(
            {
                "epoch": epoch,
                "optimizer_steps": global_step,
                "train_loss": loss_sum / len(order),
                "batch_order_sha256": canonical_digest(
                    [partition["training"][int(index)]["sample_id"] for index in order]
                ),
                "epoch_seconds": time.perf_counter() - epoch_started,
            }
        )
    expected_steps = len(partition["training"]) * int(config["execution"]["m3_epochs"])
    if global_step != expected_steps or len(history) != 2:
        raise ValueError("M3 OOF completion-count drift")

    head_final_items = primitives.mlx_trainable(head)
    head_final = primitives.mlx_tensor_digest(head_final_items)
    lora_final_items = primitives.mlx_trainable(model)
    lora_final = primitives.mlx_tensor_digest(lora_final_items)
    nonzero_lora_b = sum(
        bool(mx.any(tensor != 0).item())
        for name, tensor in lora_final_items
        if name.endswith("lora_b")
    )
    base_after = helpers.frozen_parameter_sentinel(model)
    if head_final == head_initial or lora_final == lora_initial:
        raise ValueError("M3 head or LoRA tensors did not update")
    if nonzero_lora_b != 112 or base_after != base_before:
        raise ValueError("M3 LoRA update or frozen-base sentinel failed")

    model.eval()
    heldout_logits: list[list[float]] = []
    for index, ids_value in enumerate(heldout_ids, start=1):
        values = wrapper(mx.array([ids_value], dtype=mx.int32)).astype(mx.float32)
        mx.eval(values)
        row = np.asarray(values)[0]
        if row.shape != (len(LABELS),) or not np.isfinite(row).all():
            raise ValueError("M3 held-out logits are invalid")
        heldout_logits.append([float(value) for value in row])
        if index % int(config["m3"]["heldout_log_every_rows"]) == 0 or index == len(heldout_ids):
            log_line(public_fold, "m3", f"held-out forward {index}/{len(heldout_ids)}")
    heldout_logits_array = np.asarray(heldout_logits, dtype=np.float32)
    if heldout_logits_array.shape != (672, len(LABELS)):
        raise ValueError("M3 held-out logit matrix shape drift")

    adapter_path = private_fold / "adapters.safetensors"
    head_path = private_fold / "head.safetensors"
    mx.save_safetensors(str(adapter_path), dict(lora_final_items))
    mx.save_safetensors(str(head_path), dict(head_final_items))
    os.chmod(adapter_path, 0o600)
    os.chmod(head_path, 0o600)
    predictions_path = private_fold / "heldout-logits.npz"
    save_npz_private(
        predictions_path,
        np,
        sample_ids=np.asarray([row["sample_id"] for row in partition["heldout"]]),
        component_ids=np.asarray([row["component_id"] for row in partition["heldout"]]),
        fold_ids=np.full(len(partition["heldout"]), fold_id, dtype=np.int8),
        gold=np.asarray([row["labels"] for row in partition["heldout"]], dtype=np.uint8),
        logits=heldout_logits_array,
        character_lengths=np.asarray([len(row["text"]) for row in partition["heldout"]], dtype=np.int32),
        token_lengths=np.asarray([len(ids) for ids in heldout_ids], dtype=np.int32),
    )
    manifest_after = sha256(partition_bundle["manifest_path"])
    if manifest_after != partition_bundle["manifest_before"]:
        raise ValueError("Fold manifest changed during M3 production")
    evidence_path = private_fold / "evidence.json"
    atomic_json(
        evidence_path,
        {
            "schema_version": "exp-058-m3-oof-fold-evidence-v1",
            "fold_id": fold_id,
            "model_seed": seed,
            "training_order_sha256": partition["training_order_sha256"],
            "heldout_order_sha256": partition["heldout_order_sha256"],
            "training_rows": len(partition["training"]),
            "heldout_rows": len(partition["heldout"]),
            "batch_order_sha256": [row["batch_order_sha256"] for row in history],
            "head_initial_sha256": head_initial,
            "head_final_sha256": head_final,
            "lora_initial_sha256": lora_initial,
            "lora_final_sha256": lora_final,
            "zero_step_max_abs_logit_difference": zero_delta,
            "insertion_count": len(observed),
            "lora_parameter_count": lora_count,
            "total_trainable_parameter_count": total_count,
            "nonzero_lora_b_tensors": nonzero_lora_b,
            "base_sentinel_before": base_before,
            "base_sentinel_after": base_after,
            "train_token_summary": {
                "rows": len(train_ids),
                "minimum": min(map(len, train_ids)),
                "maximum": max(map(len, train_ids)),
            },
            "heldout_token_summary": {
                "rows": len(heldout_ids),
                "minimum": min(map(len, heldout_ids)),
                "maximum": max(map(len, heldout_ids)),
            },
            "manifest_sha256_before": partition_bundle["manifest_before"],
            "manifest_sha256_after": manifest_after,
            "heldout_labels_used_for_forward": False,
        },
        private=True,
    )
    history_path = public_fold / "history.csv"
    write_history(history_path, history)
    wall_seconds = time.perf_counter() - started
    peak_memory = float(mx.get_peak_memory()) / 1e9
    if peak_memory > float(config["resources"]["m3_peak_mlx_memory_gb"]):
        raise MemoryError("M3 fold exceeded its memory budget")
    if wall_seconds > float(config["resources"]["m3_per_fold_wall_hours"]) * 3600:
        raise TimeoutError("M3 fold exceeded its wall-time budget")
    if prior_family_seconds + wall_seconds > float(config["resources"]["m3_total_wall_hours"]) * 3600:
        raise TimeoutError("M3 family exceeded its total wall-time budget")
    completed_at = utc_now()
    fold_run = {
        "schema_version": "exp-058-oof-fold-run-v1",
        "experiment_id": EXPERIMENT_ID,
        "rq_id": "RQ-S3",
        "tier": "Major",
        "stage": STAGE,
        "family": "m3",
        "fold_id": fold_id,
        "model_seed": seed,
        "status": "CompletedAwaitingVerification",
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "invocation": " ".join(sys.argv),
        "working_directory": str(PROJECT_ROOT),
        "git": git_metadata(),
        "environment": {
            "machine": platform.machine(),
            "platform": platform.platform(),
            "executable": sys.executable,
            "packages": package_versions(("mlx", "mlx-lm", "numpy", "safetensors")),
        },
        "data": {
            "protocol_id": config["data"]["protocol_id"],
            "training_rows": 2688,
            "heldout_rows": 672,
            "training_order_sha256": partition["training_order_sha256"],
            "heldout_order_sha256": partition["heldout_order_sha256"],
            "fold_manifest_sha256": manifest_after,
            "sample_overlap": 0,
            "component_overlap": 0,
            "label_order": list(LABELS),
        },
        "model": {
            "repo_id": spec["repo_id"],
            "revision": spec["revision"],
            "precision": spec["precision"],
            "pooling": shared["prompt"]["pooling"],
            "head_initial_sha256": head_initial,
            "head_final_sha256": head_final,
            "lora_initial_sha256": lora_initial,
            "lora_final_sha256": lora_final,
            "zero_step_max_abs_logit_difference": zero_delta,
            "insertion_count": len(observed),
            "lora_parameter_count": lora_count,
            "total_trainable_parameter_count": total_count,
            "nonzero_lora_b_tensors": nonzero_lora_b,
            "base_sentinel_unchanged": base_after == base_before,
            "trainable_whitelist_passed": not unexpected,
            "model_asset_files_verified": model_assets["file_count"],
        },
        "training": {
            "epochs": 2,
            "batch_size": 1,
            "optimizer_steps": global_step,
            "loss": "unweighted_binary_cross_entropy_with_logits",
            "head_optimizer": {
                "name": "AdamW",
                "learning_rate": float(spec["head_learning_rate"]),
                "weight_decay": float(spec["head_weight_decay"]),
            },
            "lora_optimizer": {
                "name": "AdamW",
                "learning_rate": float(lora["learning_rate"]),
                "weight_decay": float(lora["weight_decay"]),
            },
            "gradient_checkpointing": True,
            "history": history,
        },
        "heldout_forward": {"rows": 672, "finite_logit_values": int(heldout_logits_array.size)},
        "split_access": {
            "accessed_splits": ["train"],
            "validation_accessed": False,
            "test_inputs_accessed": False,
            "test_labels_accessed": False,
        },
        "performance_metrics_computed": False,
        "resources": {
            "wall_seconds": wall_seconds,
            "prior_family_wall_seconds": prior_family_seconds,
            "cumulative_family_wall_seconds": prior_family_seconds + wall_seconds,
            "model_load_seconds": model_load_seconds,
            "tokenization_seconds": tokenization_seconds,
            "peak_mlx_memory_gb": peak_memory,
            "peak_process_rss_gb": peak_rss_gb(),
            "api_cost_usd": 0,
        },
        "privacy": {
            "public_raw_text": False,
            "public_row_identifiers": False,
            "private_artifacts_gitignored": True,
        },
        "artifacts": {
            "history": artifact(history_path),
            "batch_orders_private": artifact(batch_orders_path),
            "heldout_logit_table_private": artifact(predictions_path),
            "evidence_private": artifact(evidence_path),
            "adapter_private": artifact(adapter_path),
            "head_private": artifact(head_path),
        },
        "claim_boundary": "One train-only M3 OOF fold; no thresholds, predictions, or metrics.",
    }
    log_line(public_fold, "m3", f"fold {fold_id} completed in {wall_seconds / 3600:.3f} h")
    del model, tokenizer, head, wrapper, head_optimizer, lora_optimizer, loss_and_grad
    gc.collect()
    mx.clear_cache()
    return finish_fold(config, "m3", fold_id, fold_run)


def assemble(config: dict[str, Any]) -> dict[str, Any]:
    import numpy as np

    top = load_top_run(config)
    if top.get("status") != "InProgress" or top["stages"]["assembly"]["status"] != "Pending":
        raise RuntimeError("OOF production is not ready for assembly")
    for family in ("m1", "m3"):
        for fold_id in range(5):
            require_passed_fold(config, family, fold_id)
    partition_bundle = load_partitions(config)
    expected_rows = partition_bundle["all"]
    by_family: dict[str, dict[str, dict[str, Any]]] = {"m1": {}, "m3": {}}
    run_hashes: dict[str, dict[int, str]] = {"m1": {}, "m3": {}}
    resource_totals = {"m1_wall_seconds": 0.0, "m3_wall_seconds": 0.0}

    for family in ("m1", "m3"):
        for fold_id in range(5):
            public_fold, _ = fold_dirs(config, family, fold_id)
            run_path = public_fold / "run.json"
            fold_run = json.loads(run_path.read_text(encoding="utf-8"))
            run_hashes[family][fold_id] = sha256(run_path)
            resource_totals[f"{family}_wall_seconds"] += float(fold_run["resources"]["wall_seconds"])
            predictions_path = require_record(fold_run["artifacts"]["heldout_logit_table_private"])
            with np.load(predictions_path, allow_pickle=False) as table:
                required = {
                    "sample_ids",
                    "component_ids",
                    "fold_ids",
                    "gold",
                    "logits",
                    "character_lengths",
                    "token_lengths",
                }
                if set(table.files) != required:
                    raise ValueError(f"{family} fold {fold_id} private table schema drift")
                for index, sample_id_value in enumerate(table["sample_ids"].tolist()):
                    sample_id = str(sample_id_value)
                    if sample_id in by_family[family]:
                        raise ValueError(f"Duplicate {family} OOF row: {sample_id}")
                    by_family[family][sample_id] = {
                        "component_id": str(table["component_ids"][index]),
                        "fold_id": int(table["fold_ids"][index]),
                        "gold": np.asarray(table["gold"][index], dtype=np.uint8),
                        "logits": np.asarray(table["logits"][index], dtype=np.float32),
                        "character_length": int(table["character_lengths"][index]),
                        "token_length": int(table["token_lengths"][index]),
                    }
    expected_ids = [row["sample_id"] for row in expected_rows]
    if set(by_family["m1"]) != set(expected_ids) or set(by_family["m3"]) != set(expected_ids):
        raise ValueError("Paired OOF family coverage drift")

    sample_ids: list[str] = []
    component_ids: list[str] = []
    fold_ids: list[int] = []
    gold_rows: list[Any] = []
    m1_logits: list[Any] = []
    m3_logits: list[Any] = []
    character_lengths: list[int] = []
    m1_token_lengths: list[int] = []
    m3_token_lengths: list[int] = []
    m1_run_sha256: list[str] = []
    m3_run_sha256: list[str] = []
    for row in expected_rows:
        sample_id = row["sample_id"]
        m1 = by_family["m1"][sample_id]
        m3 = by_family["m3"][sample_id]
        expected_fold = int(partition_bundle["assignments"][sample_id]["fold_id"])
        if m1["component_id"] != row["component_id"] or m3["component_id"] != row["component_id"]:
            raise ValueError("Paired OOF component identity drift")
        if m1["fold_id"] != expected_fold or m3["fold_id"] != expected_fold:
            raise ValueError("Paired OOF fold identity drift")
        expected_gold = np.asarray(row["labels"], dtype=np.uint8)
        if not np.array_equal(m1["gold"], expected_gold) or not np.array_equal(m3["gold"], expected_gold):
            raise ValueError("Paired OOF gold drift")
        if m1["logits"].shape != (6,) or m3["logits"].shape != (6,):
            raise ValueError("Paired OOF logit width drift")
        if not np.isfinite(m1["logits"]).all() or not np.isfinite(m3["logits"]).all():
            raise ValueError("Paired OOF contains non-finite logits")
        if m1["character_length"] != len(row["text"]) or m3["character_length"] != len(row["text"]):
            raise ValueError("Paired OOF character length drift")
        sample_ids.append(sample_id)
        component_ids.append(row["component_id"])
        fold_ids.append(expected_fold)
        gold_rows.append(expected_gold)
        m1_logits.append(m1["logits"])
        m3_logits.append(m3["logits"])
        character_lengths.append(len(row["text"]))
        m1_token_lengths.append(m1["token_length"])
        m3_token_lengths.append(m3["token_length"])
        m1_run_sha256.append(run_hashes["m1"][expected_fold])
        m3_run_sha256.append(run_hashes["m3"][expected_fold])

    private_dir = private_run_dir(config)
    paired_path = private_dir / "paired-oof.npz"
    if paired_path.exists():
        raise FileExistsError("Refusing to overwrite paired OOF table")
    save_npz_private(
        paired_path,
        np,
        sample_ids=np.asarray(sample_ids),
        component_ids=np.asarray(component_ids),
        fold_ids=np.asarray(fold_ids, dtype=np.int8),
        gold=np.asarray(gold_rows, dtype=np.uint8),
        m1_logits=np.asarray(m1_logits, dtype=np.float32),
        m3_logits=np.asarray(m3_logits, dtype=np.float32),
        character_lengths=np.asarray(character_lengths, dtype=np.int32),
        m1_token_lengths=np.asarray(m1_token_lengths, dtype=np.int32),
        m3_token_lengths=np.asarray(m3_token_lengths, dtype=np.int32),
        m1_fold_run_sha256=np.asarray(m1_run_sha256),
        m3_fold_run_sha256=np.asarray(m3_run_sha256),
    )
    paired_artifact = artifact(paired_path)
    summary = {
        "schema_version": "exp-058-paired-oof-summary-v1",
        "experiment_id": EXPERIMENT_ID,
        "status": "CompletedAwaitingVerification",
        "rows": 3360,
        "folds": 5,
        "rows_per_fold": {str(fold): fold_ids.count(fold) for fold in range(5)},
        "m1_finite_logit_values": int(np.asarray(m1_logits).size),
        "m3_finite_logit_values": int(np.asarray(m3_logits).size),
        "source_order_sha256": canonical_digest(sample_ids),
        "paired_table_private": paired_artifact,
        "resource_totals": resource_totals,
        "performance_metrics_computed": False,
        "calibration_performed": False,
        "oracle_analysis_performed": False,
        "router_training_performed": False,
        "validation_accessed": False,
        "test_accessed": False,
        "claim_boundary": "Paired raw train-OOF logits only; no performance or routing claim.",
    }
    if public_sensitive_paths(summary):
        raise ValueError("Public OOF summary contains row-level fields")
    summary_path = public_run_dir(config) / "paired-oof-summary.json"
    atomic_json(summary_path, summary)
    top = load_top_run(config)
    for family in ("m1", "m3"):
        for fold_id in range(5):
            top["stages"][family]["folds"][str(fold_id)]["status"] = "Verified"
            top["stages"][family]["folds"][str(fold_id)]["verification"] = artifact(
                verification_path(config, family, fold_id)
            )
    top["stages"]["assembly"] = {"status": "Completed", "completed_at_utc": utc_now()}
    top["status"] = "CompletedAwaitingVerification"
    top["completed_at_utc"] = utc_now()
    top["resources"].update(resource_totals)
    top["artifacts"]["paired_oof_private"] = paired_artifact
    top["artifacts"]["paired_oof_summary"] = artifact(summary_path)
    if public_sensitive_paths(top):
        raise ValueError("Public top-level run contains row-level fields")
    atomic_json(public_run_dir(config) / "run.json", top)
    log_line(public_run_dir(config), "assembly", "paired all 3,360 train rows in frozen source order")
    return top


def record_assembly_failure(config: dict[str, Any], error: Exception) -> None:
    run_dir = public_run_dir(config)
    if not run_dir.is_dir():
        return
    failure_path = run_dir / "assembly-failure.json"
    atomic_json(
        failure_path,
        {
            "schema_version": "exp-058-oof-assembly-failure-v1",
            "experiment_id": EXPERIMENT_ID,
            "status": "Failed",
            "failed_at_utc": utc_now(),
            "error_type": type(error).__name__,
            "error": str(error),
            "validation_accessed": False,
            "test_accessed": False,
        },
    )
    top = load_top_run(config)
    top["status"] = "BlockedByFailure"
    top["stages"]["assembly"] = {"status": "Failed", "failure": artifact(failure_path)}
    atomic_json(run_dir / "run.json", top)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--stage", choices=("initialize", "m1", "m3", "assemble"), required=True)
    parser.add_argument("--fold", type=int)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = load_config(config_path)
    if args.stage == "initialize":
        if args.fold is not None:
            raise ValueError("Initialize does not accept --fold")
        result = initialize(config_path, config)
    elif args.stage == "assemble":
        if args.fold is not None:
            raise ValueError("Assemble does not accept --fold")
        try:
            result = assemble(config)
        except Exception as error:
            record_assembly_failure(config, error)
            raise
    else:
        if args.fold not in range(5):
            raise ValueError("Model stages require --fold 0..4")
        try:
            result = (
                run_m1_fold(config, args.fold)
                if args.stage == "m1"
                else run_m3_fold(config, args.fold)
            )
        except Exception as error:
            record_failure(config, args.stage, args.fold, error)
            raise
    print(
        json.dumps(
            {
                "stage": args.stage,
                "fold": args.fold,
                "status": result["status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
