#!/usr/bin/env python3
"""Run the staged fold-0 EXP-058 M1/M3 two-step OOF consumer dry-run."""

from __future__ import annotations

import argparse
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
from typing import Any, Iterable


EXPERIMENT_ID = "EXP-058"
STAGE = "fold-0-m1-m3-two-step-dry-run"
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
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-058-oof-consumer-dry-run-fold-0.json"


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


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID or config.get("stage") != STAGE:
        raise ValueError("Unexpected EXP-058 dry-run identity")
    auth = config["authorization"]
    expected_true = ("model_loading", "two_step_training", "heldout_forward")
    expected_false = (
        "calibration",
        "full_oof_training",
        "metrics",
        "oracle_analysis",
        "router_training",
        "test_access",
        "validation_access",
    )
    if auth.get("fold_id") != 0 or auth.get("model_seed") != 42:
        raise PermissionError("Dry-run is restricted to fold 0 and seed 42")
    if any(auth.get(key) is not True for key in expected_true):
        raise PermissionError("Required dry-run action is not authorized")
    if any(auth.get(key) is not False for key in expected_false):
        raise PermissionError("Dry-run authorization exceeds the registered scope")
    execution = config["execution"]
    if execution.get("optimizer_steps_per_model") != 2:
        raise PermissionError("Exactly two optimizer steps per model are authorized")
    if execution.get("heldout_forward_rows_per_model") != 2:
        raise PermissionError("Exactly two held-out rows per model are authorized")
    for record in config["implementation"].values():
        require_record(record)
    for record in config["prerequisites"].values():
        require_record(record)
    return config


def verify_prerequisites(config: dict[str, Any]) -> dict[str, Any]:
    verification = load_json_record(config["prerequisites"]["fold_verification"])
    if (
        verification.get("status") != "Passed"
        or verification.get("check_count") != 131
        or verification.get("passed_count") != 131
        or verification.get("failed_count") != 0
    ):
        raise RuntimeError("Fold-manifest prerequisite is not independently verified")
    contract = load_json_record(config["prerequisites"]["consumer_contract"])
    if contract.get("training_authorized_by_contract") is not False:
        raise ValueError("Completed fold contract must remain sealed for full OOF")
    if contract.get("forbidden_splits") != ["validation", "test"]:
        raise ValueError("Fold consumer split boundary drift")
    manifest_path = require_record(config["prerequisites"]["fold_manifest"])
    manifest_hash = sha256(manifest_path)
    if contract.get("fold_manifest_sha256") != manifest_hash:
        raise ValueError("Consumer contract and manifest hash disagree")

    m1_run = load_json_record(config["prerequisites"]["m1_seed_42_run"])
    m1_verify = load_json_record(config["prerequisites"]["m1_seed_42_verification"])
    m3_run = load_json_record(config["prerequisites"]["m3_seed_42_run"])
    m3_verify = load_json_record(config["prerequisites"]["m3_seed_42_verification"])
    if m1_run.get("status") != "Completed" or m1_verify.get("status") != "Passed":
        raise RuntimeError("Verified M1 seed-42 metadata is unavailable")
    if (
        m3_run.get("status") != "Completed"
        or m3_verify.get("status") != "Passed"
        or m3_verify.get("checks_passed") != 148
        or m3_verify.get("checks_total") != 148
        or m3_verify.get("failed_checks") != []
    ):
        raise RuntimeError("Verified M3 seed-42 metadata is unavailable")
    if m1_run["selection"]["selected_epoch"] != 4 or m3_run["selection"]["selected_epoch"] != 2:
        raise ValueError("Selected epoch metadata drift")
    if m1_run.get("test_split_accessed") or m3_run.get("test_split_accessed"):
        raise PermissionError("Prerequisite test boundary drift")
    shared = load_json_record(config["prerequisites"]["shared_config"])
    if shared["data"]["test_status"] != "sealed_not_authorized_for_model_access":
        raise PermissionError("Shared test contract is not sealed")
    return {"shared": shared, "m1_run": m1_run, "m3_run": m3_run}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def load_partition(config: dict[str, Any]) -> dict[str, Any]:
    train_path = require_record(config["data"]["train"])
    manifest_path = require_record(config["prerequisites"]["fold_manifest"])
    manifest_before = sha256(manifest_path)
    train_rows = read_jsonl(train_path)
    manifest_rows = read_jsonl(manifest_path)
    if len(train_rows) != 3360 or len(manifest_rows) != 3360:
        raise ValueError("EXP-058 train/manifest row count drift")
    train_ids: set[str] = set()
    for row in train_rows:
        if set(row) != TRAIN_FIELDS or row.get("protocol_id") != "DATA-SO-TASK-V1":
            raise ValueError("Train schema or protocol drift")
        if row["sample_id"] in train_ids:
            raise ValueError("Duplicate train sample ID")
        train_ids.add(row["sample_id"])
        if len(row["labels"]) != len(LABELS) or any(value not in (0, 1) for value in row["labels"]):
            raise ValueError("Invalid train label vector")
        cardinality = sum(row["labels"])
        if row["label_cardinality"] != cardinality or row["neutral"] != (cardinality == 0):
            raise ValueError("Train derived-field drift")
    assignments: dict[str, dict[str, Any]] = {}
    for row in manifest_rows:
        if set(row) != MANIFEST_FIELDS or row.get("experiment_id") != EXPERIMENT_ID:
            raise ValueError("Fold manifest schema drift")
        if row["sample_id"] in assignments or row["fold_id"] not in range(5):
            raise ValueError("Invalid fold assignment")
        assignments[row["sample_id"]] = row
    if set(assignments) != train_ids:
        raise ValueError("Fold manifest does not cover train exactly")
    for row in train_rows:
        if assignments[row["sample_id"]]["component_id"] != row["component_id"]:
            raise ValueError("Manifest component identity drift")

    fold_id = int(config["authorization"]["fold_id"])
    heldout = [row for row in train_rows if assignments[row["sample_id"]]["fold_id"] == fold_id]
    training = [row for row in train_rows if assignments[row["sample_id"]]["fold_id"] != fold_id]
    if len(training) != 2688 or len(heldout) != 672:
        raise ValueError("Fold-0 partition size drift")
    train_sample_ids = {row["sample_id"] for row in training}
    heldout_sample_ids = {row["sample_id"] for row in heldout}
    train_components = {row["component_id"] for row in training}
    heldout_components = {row["component_id"] for row in heldout}
    if train_sample_ids & heldout_sample_ids or train_components & heldout_components:
        raise ValueError("OOF sample/component leakage")
    return {
        "all": train_rows,
        "training": training,
        "heldout": heldout,
        "manifest_path": manifest_path,
        "manifest_before": manifest_before,
        "training_order_sha256": canonical_digest([row["sample_id"] for row in training]),
        "heldout_order_sha256": canonical_digest([row["sample_id"] for row in heldout]),
    }


def m1_schedule(config: dict[str, Any], training_rows: int) -> dict[str, int]:
    batch_size = int(config["m1"]["batch_size"])
    steps_per_epoch = math.ceil(training_rows / batch_size)
    planned_epochs = int(config["m1"]["planned_scheduler_epochs"])
    stop_epoch = int(config["m1"]["selected_stop_epoch"])
    horizon = steps_per_epoch * planned_epochs
    warmup_exact = horizon * float(config["m1"]["warmup_ratio"])
    if not warmup_exact.is_integer():
        raise ValueError("Corrected M1 warmup is not integral")
    return {
        "steps_per_epoch": steps_per_epoch,
        "planned_scheduler_epochs": planned_epochs,
        "scheduler_horizon_steps": horizon,
        "warmup_steps": int(warmup_exact),
        "selected_stop_epoch": stop_epoch,
        "selected_stop_steps": steps_per_epoch * stop_epoch,
    }


def verify_model_files(shared: dict[str, Any], family: str) -> dict[str, Any]:
    if family == "m1":
        spec = shared["models"]["m1"]
        manifest = require_record(
            {
                "path": spec["manifest_path"],
                "bytes": resolve_project(spec["manifest_path"]).stat().st_size,
                "sha256": spec["manifest_sha256"],
            }
        )
        content = json.loads(manifest.read_text(encoding="utf-8"))
        root = resolve_project(spec["local_path"])
        files = content["files"]
    elif family == "m3":
        spec = shared["models"]["qwen_shared"]
        manifest = require_record(
            {
                "path": spec["manifest_path"],
                "bytes": resolve_project(spec["manifest_path"]).stat().st_size,
                "sha256": spec["manifest_sha256"],
            }
        )
        content = json.loads(manifest.read_text(encoding="utf-8"))
        root = resolve_project(spec["local_path"])
        files = content["mlx_bf16"]["files"]
    else:
        raise ValueError(f"Unknown model family: {family}")
    for record in files:
        path = root / record["path"]
        if path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
            raise ValueError(f"Model asset drift: {path}")
    return {"manifest": artifact(manifest), "file_count": len(files)}


def log_line(run_dir: Path, stage: str, message: str) -> None:
    line = f"[{utc_now()}] [{stage}] {message}"
    print(line, flush=True)
    with (run_dir / "stdout.log").open("a", encoding="utf-8") as target:
        target.write(line + "\n")


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


def initialize_static(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    prerequisites = verify_prerequisites(config)
    partition = load_partition(config)
    run_dir = resolve_project(config["outputs"]["public_run_dir"])
    private_dir = resolve_project(config["outputs"]["private_run_dir"])
    if run_dir.exists() or private_dir.exists():
        raise FileExistsError("Refusing to overwrite append-only dry-run output")
    run_dir.mkdir(parents=True)
    private_dir.mkdir(parents=True, mode=0o700)
    os.chmod(private_dir, 0o700)

    frozen_dir = run_dir / "frozen-sources"
    frozen_dir.mkdir()
    frozen_sources: dict[str, Any] = {}
    source_records = {"config": artifact(config_path), **config["implementation"]}
    for name, record in source_records.items():
        source = require_record(record)
        destination = frozen_dir / f"{name}{source.suffix}"
        shutil.copy2(source, destination)
        frozen_sources[name] = artifact(destination)

    private_partition = private_dir / "partition.json"
    atomic_json(
        private_partition,
        {
            "schema_version": "exp-058-oof-dry-run-partition-v1",
            "fold_id": 0,
            "training": [
                {"sample_id": row["sample_id"], "component_id": row["component_id"]}
                for row in partition["training"]
            ],
            "heldout": [
                {"sample_id": row["sample_id"], "component_id": row["component_id"]}
                for row in partition["heldout"]
            ],
        },
        private=True,
    )
    schedule = m1_schedule(config, len(partition["training"]))
    if schedule != config["m1"]["expected_schedule"]:
        raise ValueError("M1 scheduler correction does not match frozen expected values")

    run = {
        "schema_version": "exp-058-oof-consumer-dry-run-v1",
        "experiment_id": EXPERIMENT_ID,
        "rq_id": "RQ-S3",
        "tier": "Minor",
        "stage": STAGE,
        "status": "InProgress",
        "started_at_utc": utc_now(),
        "working_directory": str(PROJECT_ROOT),
        "git": git_metadata(),
        "authorization": config["authorization"],
        "split_access": {
            "accessed_splits": ["train"],
            "validation_accessed": False,
            "test_inputs_accessed": False,
            "test_labels_accessed": False,
        },
        "data": {
            "protocol_id": "DATA-SO-TASK-V1",
            "label_order": list(LABELS),
            "fold_id": 0,
            "training_rows": len(partition["training"]),
            "heldout_rows": len(partition["heldout"]),
            "training_order_sha256": partition["training_order_sha256"],
            "heldout_order_sha256": partition["heldout_order_sha256"],
            "component_overlap": 0,
            "sample_overlap": 0,
            "manifest_sha256": partition["manifest_before"],
        },
        "m1_schedule": schedule,
        "model_execution": {
            "m1_optimizer_steps": 0,
            "m3_optimizer_steps": 0,
            "performance_metrics_computed": False,
            "full_oof_training_performed": False,
        },
        "stages": {
            "static": {"status": "Passed", "completed_at_utc": utc_now()},
            "m1": {"status": "Pending"},
            "m3": {"status": "Pending"},
        },
        "artifacts": {
            "frozen_sources": frozen_sources,
            "private_partition": artifact(private_partition),
        },
        "prerequisite_summary": {
            "fold_manifest_verification": "Passed_131_of_131",
            "m1_selected_epoch": prerequisites["m1_run"]["selection"]["selected_epoch"],
            "m3_selected_epoch": prerequisites["m3_run"]["selection"]["selected_epoch"],
            "full_oof_consumer_contract_authorized": False,
        },
        "claim_boundary": "Implementation-only fold-0 two-step dry-run; no performance evidence.",
    }
    violations = public_sensitive_paths(run)
    if violations:
        raise ValueError(f"Public run contains sensitive keys: {violations}")
    atomic_json(run_dir / "run.json", run)
    log_line(run_dir, "static", "train-only fold partition and scheduler contract passed")
    return run


def require_stage(config: dict[str, Any], stage: str) -> tuple[Path, Path, dict[str, Any]]:
    run_dir = resolve_project(config["outputs"]["public_run_dir"])
    private_dir = resolve_project(config["outputs"]["private_run_dir"])
    run_path = run_dir / "run.json"
    if not run_path.is_file() or not private_dir.is_dir():
        raise FileNotFoundError("Static stage has not completed")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    if run["stages"]["static"]["status"] != "Passed":
        raise RuntimeError("Static stage did not pass")
    if run["stages"][stage]["status"] != "Pending":
        raise RuntimeError(f"Stage {stage} is not pending")
    if stage == "m3" and run["stages"]["m1"]["status"] != "Passed":
        raise RuntimeError("M1 must pass before M3 starts")
    return run_dir, private_dir, run


def complete_model_stage(
    config: dict[str, Any], stage: str, summary: dict[str, Any], private_artifact: dict[str, Any]
) -> dict[str, Any]:
    run_dir = resolve_project(config["outputs"]["public_run_dir"])
    run_path = run_dir / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["stages"][stage] = {"status": "Passed", "completed_at_utc": utc_now(), **summary}
    run["model_execution"][f"{stage}_optimizer_steps"] = 2
    run["artifacts"][f"{stage}_private_evidence"] = private_artifact
    if run["stages"]["m1"]["status"] == "Passed" and run["stages"]["m3"]["status"] == "Passed":
        run["status"] = "CompletedAwaitingVerification"
        run["completed_at_utc"] = utc_now()
    violations = public_sensitive_paths(run)
    if violations:
        raise ValueError(f"Public run contains sensitive keys: {violations}")
    atomic_json(run_path, run)
    return run


def record_failure(config: dict[str, Any], stage: str, error: Exception) -> None:
    run_dir = resolve_project(config["outputs"]["public_run_dir"])
    if not run_dir.is_dir():
        return
    failure = {
        "schema_version": "exp-058-oof-consumer-dry-run-failure-v1",
        "experiment_id": EXPERIMENT_ID,
        "stage": stage,
        "status": "Failed",
        "failed_at_utc": utc_now(),
        "exception_type": type(error).__name__,
        "error": str(error),
        "validation_accessed": False,
        "test_accessed": False,
        "performance_metrics_computed": False,
    }
    atomic_json(run_dir / f"{stage}-failure.json", failure)
    run_path = run_dir / "run.json"
    if run_path.is_file():
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run["status"] = "Failed"
        run["stages"][stage] = {"status": "Failed", "failed_at_utc": utc_now()}
        atomic_json(run_path, run)


def run_m1(config: dict[str, Any]) -> dict[str, Any]:
    run_dir, private_dir, _ = require_stage(config, "m1")
    started = time.perf_counter()
    prerequisites = verify_prerequisites(config)
    shared = prerequisites["shared"]
    partition = load_partition(config)
    model_assets = verify_model_files(shared, "m1")
    reference = dynamic_module(
        "exp058_m1_reference", require_record(config["implementation"]["m1_runner_reference"])
    )
    np = reference.np
    torch = reference.torch
    log_line(run_dir, "m1", "verified model assets and train-only fold partition")

    spec = shared["models"]["m1"]
    model_path = resolve_project(spec["local_path"])
    tokenizer = reference.AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    train_encodings, train_lengths = reference.encode_rows(
        tokenizer, partition["training"], int(spec["max_sequence_length"])
    )
    heldout_encodings, heldout_lengths = reference.encode_rows(
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
        raise ValueError("M1 dry-run must preserve full fine-tuning")

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
    epoch_order = torch.randperm(len(train_dataset), generator=generator).tolist()
    epoch_order_digest = canonical_digest(
        [partition["training"][index]["sample_id"] for index in epoch_order]
    )
    if epoch_order_digest != config["m1"]["expected_epoch_1_order_sha256"]:
        raise ValueError("M1 seed-42 epoch-1 order drift")
    selected_indices = epoch_order[: int(config["execution"]["optimizer_steps_per_model"]) * int(spec["batch_size"])]
    selected_rows = [partition["training"][index] for index in selected_indices]
    if canonical_digest([row["sample_id"] for row in selected_rows]) != config["m1"]["expected_dry_run_training_ids_sha256"]:
        raise ValueError("M1 dry-run training rows drift")
    train_loader = reference.DataLoader(
        reference.Subset(train_dataset, selected_indices),
        batch_size=int(spec["batch_size"]),
        shuffle=False,
        drop_last=False,
        num_workers=0,
        collate_fn=collator,
    )

    model.train()
    losses: list[float] = []
    gradient_norms: list[float] = []
    learning_rates: list[float] = []
    for step, batch in enumerate(train_loader, start=1):
        labels = batch.pop("labels")
        optimizer.zero_grad(set_to_none=True)
        logits = model(**batch).logits
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels)
        if not torch.isfinite(loss):
            raise ValueError(f"Non-finite M1 loss at step {step}")
        loss.backward()
        gradient_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        if not torch.isfinite(gradient_norm):
            raise ValueError(f"Non-finite M1 gradient norm at step {step}")
        optimizer.step()
        scheduler.step()
        losses.append(float(loss.detach()))
        gradient_norms.append(float(gradient_norm.detach()))
        learning_rates.append(float(optimizer.param_groups[0]["lr"]))
    if len(losses) != 2:
        raise ValueError("M1 dry-run did not execute exactly two optimizer steps")

    final_classifier = reference.tensor_digest(
        {name: value for name, value in model.named_parameters() if name.startswith("classifier.")}
    )
    if final_classifier == initial_classifier:
        raise ValueError("M1 classifier did not update")
    heldout_rows = partition["heldout"][:2]
    if canonical_digest([row["sample_id"] for row in heldout_rows]) != config["expected_heldout_forward_ids_sha256"]:
        raise ValueError("Held-out forward rows drift")
    held_features = [
        {key: value[index] for key, value in heldout_encodings.items()}
        for index in range(len(heldout_rows))
    ]
    held_batch = tokenizer.pad(held_features, padding=True, return_tensors="pt")
    model.eval()
    with torch.no_grad():
        held_logits_tensor = model(**held_batch).logits.float().cpu()
    if tuple(held_logits_tensor.shape) != (2, len(LABELS)) or not torch.isfinite(held_logits_tensor).all():
        raise ValueError("M1 held-out logits are invalid")
    held_logits = held_logits_tensor.numpy().tolist()
    manifest_after = sha256(partition["manifest_path"])
    if manifest_after != partition["manifest_before"]:
        raise ValueError("Fold manifest changed during M1 stage")

    evidence_path = private_dir / "m1-evidence.json"
    atomic_json(
        evidence_path,
        {
            "schema_version": "exp-058-oof-dry-run-m1-evidence-v1",
            "fold_id": 0,
            "model_seed": seed,
            "training_source_order_sha256": partition["training_order_sha256"],
            "heldout_source_order_sha256": partition["heldout_order_sha256"],
            "epoch_1_order_sha256": epoch_order_digest,
            "training_sample_ids": [row["sample_id"] for row in selected_rows],
            "training_component_ids": [row["component_id"] for row in selected_rows],
            "heldout_sample_ids": [row["sample_id"] for row in heldout_rows],
            "heldout_component_ids": [row["component_id"] for row in heldout_rows],
            "optimizer_steps": len(losses),
            "batch_size": int(spec["batch_size"]),
            "losses": losses,
            "gradient_norms": gradient_norms,
            "learning_rates_after_step": learning_rates,
            "scheduler": schedule,
            "classifier_initial_sha256": initial_classifier,
            "classifier_final_sha256": final_classifier,
            "heldout_logits": held_logits,
            "label_order": list(LABELS),
            "manifest_sha256_before": partition["manifest_before"],
            "manifest_sha256_after": manifest_after,
            "train_token_lengths": train_lengths,
            "heldout_token_lengths": heldout_lengths,
            "heldout_labels_used_for_forward": False,
        },
        private=True,
    )
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9
    elapsed = time.perf_counter() - started
    if peak_rss > float(config["resources"]["m1_peak_process_memory_gb"]):
        raise MemoryError("M1 dry-run exceeded its memory budget")
    summary = {
        "optimizer_steps": 2,
        "heldout_forward_rows": 2,
        "finite_losses": 2,
        "finite_logit_values": 12,
        "fresh_classifier_hash_matched": True,
        "classifier_updated": True,
        "model_asset_files_verified": model_assets["file_count"],
        "peak_process_rss_gb": peak_rss,
        "wall_seconds": elapsed,
    }
    log_line(run_dir, "m1", f"passed two updates and held-out forward in {elapsed:.2f}s")
    del model, tokenizer, optimizer, scheduler, train_dataset, train_loader, held_batch
    gc.collect()
    return complete_model_stage(config, "m1", summary, artifact(evidence_path))


def run_m3(config: dict[str, Any]) -> dict[str, Any]:
    run_dir, private_dir, _ = require_stage(config, "m3")
    started = time.perf_counter()
    prerequisites = verify_prerequisites(config)
    shared = prerequisites["shared"]
    partition = load_partition(config)
    model_assets = verify_model_files(shared, "m3")
    primitives = dynamic_module(
        "exp058_qwen_primitives", require_record(config["implementation"]["qwen_primitives"])
    )
    helpers = dynamic_module(
        "exp058_m3_helpers", require_record(config["implementation"]["m3_preflight_reference"])
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
    model, tokenizer = load(str(model_path), lazy=False)
    model.freeze()
    model.eval()
    prompt = primitives.load_prompt(shared)
    train_ids = [
        primitives.qwen_prompt_ids(tokenizer, prompt, row["text"], shared["prompt"]["max_sequence_length"])
        for row in partition["training"]
    ]
    heldout_ids = [
        primitives.qwen_prompt_ids(tokenizer, prompt, row["text"], shared["prompt"]["max_sequence_length"])
        for row in partition["heldout"]
    ]
    seed = int(config["authorization"]["model_seed"])
    head = primitives.build_qwen_head(seed, int(spec["hidden_size"]))
    head_initial = primitives.mlx_tensor_digest(primitives.mlx_trainable(head))
    if head_initial != config["m3"]["expected_head_initial_sha256"]:
        raise ValueError("M3 fresh head initialization drift")
    wrapper = primitives.make_classification_wrapper(model, head)

    rng = np.random.default_rng(seed)
    epoch_order = rng.permutation(len(partition["training"])).astype(np.int32)
    epoch_order_digest = canonical_digest(
        [partition["training"][int(index)]["sample_id"] for index in epoch_order]
    )
    if epoch_order_digest != config["m3"]["expected_epoch_1_order_sha256"]:
        raise ValueError("M3 seed-42 epoch-1 order drift")
    selected_indices = epoch_order[:2]
    selected_rows = [partition["training"][int(index)] for index in selected_indices]
    if canonical_digest([row["sample_id"] for row in selected_rows]) != config["m3"]["expected_dry_run_training_ids_sha256"]:
        raise ValueError("M3 dry-run training rows drift")

    first_ids = mx.array([train_ids[int(selected_indices[0])]], dtype=mx.int32)
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

    grad_checkpoint(model.layers[0])
    model.train()
    head_optimizer = optim.AdamW(
        learning_rate=float(spec["head_learning_rate"]), weight_decay=float(spec["head_weight_decay"])
    )
    lora_optimizer = optim.AdamW(
        learning_rate=float(lora["learning_rate"]), weight_decay=float(lora["weight_decay"])
    )
    loss_and_grad = nn.value_and_grad(wrapper, primitives.classification_loss)
    losses: list[float] = []
    for row_index in selected_indices:
        index = int(row_index)
        ids = mx.array([train_ids[index]], dtype=mx.int32)
        targets = mx.array([partition["training"][index]["labels"]], dtype=mx.float32)
        loss, gradients = loss_and_grad(wrapper, ids, targets)
        lora_optimizer.update(wrapper.backbone, gradients["backbone"])
        head_optimizer.update(wrapper.head, gradients["head"])
        mx.eval(loss, wrapper.trainable_parameters(), lora_optimizer.state, head_optimizer.state)
        value = float(loss.item())
        if not math.isfinite(value):
            raise ValueError("Non-finite M3 dry-run loss")
        losses.append(value)
    if len(losses) != 2:
        raise ValueError("M3 dry-run did not execute exactly two optimizer steps")

    head_final = primitives.mlx_tensor_digest(primitives.mlx_trainable(head))
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

    heldout_rows = partition["heldout"][:2]
    if canonical_digest([row["sample_id"] for row in heldout_rows]) != config["expected_heldout_forward_ids_sha256"]:
        raise ValueError("Held-out forward rows drift")
    model.eval()
    held_logits: list[list[float]] = []
    for ids_value in heldout_ids[:2]:
        logits = wrapper(mx.array([ids_value], dtype=mx.int32)).astype(mx.float32)
        mx.eval(logits)
        values = np.asarray(logits)[0].tolist()
        if len(values) != len(LABELS) or any(not math.isfinite(float(value)) for value in values):
            raise ValueError("M3 held-out logits are invalid")
        held_logits.append([float(value) for value in values])
    manifest_after = sha256(partition["manifest_path"])
    if manifest_after != partition["manifest_before"]:
        raise ValueError("Fold manifest changed during M3 stage")

    evidence_path = private_dir / "m3-evidence.json"
    atomic_json(
        evidence_path,
        {
            "schema_version": "exp-058-oof-dry-run-m3-evidence-v1",
            "fold_id": 0,
            "model_seed": seed,
            "training_source_order_sha256": partition["training_order_sha256"],
            "heldout_source_order_sha256": partition["heldout_order_sha256"],
            "epoch_1_order_sha256": epoch_order_digest,
            "training_sample_ids": [row["sample_id"] for row in selected_rows],
            "training_component_ids": [row["component_id"] for row in selected_rows],
            "heldout_sample_ids": [row["sample_id"] for row in heldout_rows],
            "heldout_component_ids": [row["component_id"] for row in heldout_rows],
            "optimizer_steps": len(losses),
            "batch_size": 1,
            "losses": losses,
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
            "heldout_logits": held_logits,
            "label_order": list(LABELS),
            "manifest_sha256_before": partition["manifest_before"],
            "manifest_sha256_after": manifest_after,
            "train_token_lengths": {
                "minimum": min(map(len, train_ids)),
                "maximum": max(map(len, train_ids)),
                "rows": len(train_ids),
            },
            "heldout_token_lengths": {
                "minimum": min(map(len, heldout_ids)),
                "maximum": max(map(len, heldout_ids)),
                "rows": len(heldout_ids),
            },
            "heldout_labels_used_for_forward": False,
        },
        private=True,
    )
    peak_memory = float(mx.get_peak_memory()) / 1e9
    elapsed = time.perf_counter() - started
    if peak_memory > float(config["resources"]["m3_peak_mlx_memory_gb"]):
        raise MemoryError("M3 dry-run exceeded its memory budget")
    summary = {
        "optimizer_steps": 2,
        "heldout_forward_rows": 2,
        "finite_losses": 2,
        "finite_logit_values": 12,
        "fresh_head_hash_matched": True,
        "fresh_lora_hash_matched": True,
        "zero_step_lora_delta": True,
        "insertion_points": len(observed),
        "trainable_whitelist_passed": True,
        "head_updated": True,
        "lora_updated": True,
        "base_sentinel_unchanged": True,
        "model_asset_files_verified": model_assets["file_count"],
        "peak_mlx_memory_gb": peak_memory,
        "wall_seconds": elapsed,
    }
    log_line(run_dir, "m3", f"passed two updates and held-out forward in {elapsed:.2f}s")
    del model, tokenizer, head, wrapper, head_optimizer, lora_optimizer, loss_and_grad
    gc.collect()
    mx.clear_cache()
    return complete_model_stage(config, "m3", summary, artifact(evidence_path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--stage", choices=("static", "m1", "m3"), required=True)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config: dict[str, Any] | None = None
    try:
        config = load_config(config_path)
        if args.stage == "static":
            result = initialize_static(config_path, config)
        elif args.stage == "m1":
            result = run_m1(config)
        else:
            result = run_m3(config)
    except Exception as error:
        if config is not None and args.stage != "static":
            record_failure(config, args.stage, error)
        raise
    print(json.dumps({"status": result["status"], "stage": args.stage}, sort_keys=True))


if __name__ == "__main__":
    main()
