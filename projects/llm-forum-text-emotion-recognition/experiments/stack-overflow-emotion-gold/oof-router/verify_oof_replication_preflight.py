#!/usr/bin/env python3
"""Independently recompute and verify the EXP-061/062 initialization preflight."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import random
import re
import stat
from typing import Any, Iterable, Sequence


CONFIG_SCHEMA = "exp-oof-initialization-preflight-config-v1"
STAGE = "oof-initialization-preflight"
RQ_ID = "RQ-S3"
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
SCOPES = ("static", "m1-init", "m3-init", "finalize", "cross-seed")
ATTEMPT_RE = re.compile(r"attempt-[1-9][0-9]*\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

SCRIPT_DIR = Path(__file__).resolve().parent
LIVE_PREFLIGHT_VERIFIER_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_DIR.parents[2]
PUBLIC_RUNS_ROOT = SCRIPT_DIR / "runs"
PRIVATE_RUNS_ROOT = SCRIPT_DIR / "private"

IDENTITIES = {
    "EXP-061": {
        "seed": 43,
        "formal_run_id": "exp-061-seed-43-router-replication",
        "preflight_run_id": "exp-061-seed-43-router-replication-preflight",
    },
    "EXP-062": {
        "seed": 44,
        "formal_run_id": "exp-062-seed-44-router-replication",
        "preflight_run_id": "exp-062-seed-44-router-replication-preflight",
    },
}
CONFIG_KEYS = {
    "schema_version",
    "experiment_id",
    "rq_id",
    "tier",
    "stage",
    "run_id",
    "formal_run_id",
    "attempt_id",
    "formal_attempt_id",
    "authorization",
    "execution",
    "seed_contract",
    "data",
    "implementation",
    "preflight_implementation",
    "prerequisites",
    "outputs",
    "formal_outputs",
    "m1",
    "m3",
    "resources",
}
FORMAL_IMPLEMENTATION_KEYS = {
    "protocol",
    "runner",
    "verifier",
    "tests",
    "m1_runner_reference",
    "qwen_primitives",
    "m3_preflight_reference",
}
PREFLIGHT_IMPLEMENTATION_KEYS = {"runner", "verifier", "tests"}
FORMAL_PROTOCOL_PATHS = {
    "EXP-061": "experiments/stack-overflow-emotion-gold/protocols/exp-061-seed-43-router-replication.md",
    "EXP-062": "experiments/stack-overflow-emotion-gold/protocols/exp-062-seed-44-router-replication.md",
}
FORMAL_IMPLEMENTATION_PATHS = {
    "runner": "experiments/stack-overflow-emotion-gold/oof-router/run_exp058_oof_production.py",
    "verifier": "experiments/stack-overflow-emotion-gold/oof-router/verify_exp058_oof_production.py",
    "tests": "experiments/stack-overflow-emotion-gold/oof-router/tests/test_exp058_oof_production.py",
    "m1_runner_reference": "experiments/stack-overflow-emotion-gold/model-comparison/run_exp051_m1.py",
    "qwen_primitives": "experiments/stack-overflow-emotion-gold/model-comparison/run_preflight.py",
    "m3_preflight_reference": "experiments/stack-overflow-emotion-gold/model-comparison/run_exp053_m3_preflight.py",
}
PREFLIGHT_IMPLEMENTATION_PATHS = {
    "runner": "experiments/stack-overflow-emotion-gold/oof-router/run_oof_replication_preflight.py",
    "verifier": "experiments/stack-overflow-emotion-gold/oof-router/verify_oof_replication_preflight.py",
    "tests": "experiments/stack-overflow-emotion-gold/oof-router/tests/test_oof_replication_preflight.py",
}
PREREQUISITE_KEYS = {
    "shared_config",
    "fold_manifest",
    "consumer_contract",
    "fold_verification",
}
OUTPUT_KEYS = {
    "public_namespace",
    "public_attempt_dir",
    "private_namespace",
    "private_attempt_dir",
    "selection_record",
}
AUTHORIZATION_TEMPLATE = {
    "model_loading": True,
    "initialization_only": True,
    "training": False,
    "heldout_forward": False,
    "metrics": False,
    "calibration": False,
    "router_training": False,
    "validation_access": False,
    "test_access": False,
}
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
INIT_HASH_FIELDS = (
    "base_asset_manifest_sha256",
    "fold_manifest_sha256",
    "m1_classifier_init_sha256",
    "m1_rng_state_digest",
    "m1_initialization_state_sha256",
    "m1_batch_order_sha256",
    "m3_lora_a_init_sha256",
    "m3_lora_b_init_sha256",
    "m3_lora_combined_init_sha256",
    "m3_classifier_head_init_sha256",
    "m3_base_sentinel_sha256",
    "m3_rng_state_digest",
    "m3_initialization_state_sha256",
    "m3_batch_order_sha256",
)
EXPECTED_FOLD_KEYS = {"model_seed", *INIT_HASH_FIELDS}
V2_EXECUTION = {
    "fold_ids": [0, 1, 2, 3, 4],
    "canonical_prefilter_order": "frozen_train_source_file_order",
    "m1_epochs": 4,
    "m3_epochs": 2,
    "m1_device": "cpu",
    "m3_device": "Apple_Metal",
    "family_order": ["m1", "m3"],
    "performance_metrics_allowed": False,
}
V2_M1 = {
    "batch_size": 16,
    "heldout_batch_size": 32,
    "planned_scheduler_epochs": 5,
    "warmup_ratio": 0.1,
    "weight_decay_exclusions": ["bias", "LayerNorm.weight"],
    "expected_schedule": {
        "steps_per_epoch": 168,
        "planned_scheduler_epochs": 5,
        "scheduler_horizon_steps": 840,
        "warmup_steps": 84,
        "selected_stop_epoch": 4,
        "selected_stop_steps": 672,
    },
}
V2_M3 = {
    "log_every_steps": 250,
    "heldout_log_every_rows": 100,
    "expected_insertion_points": 112,
    "expected_lora_parameters": 7_340_032,
    "expected_total_trainable_parameters": 7_355_398,
    "expected_optimizer_steps_per_fold": 5_376,
}
V2_RESOURCES = {
    "api_cost_usd": 0,
    "minimum_free_disk_gb": 8.0,
    "m1_peak_process_memory_gb": 8.0,
    "m1_total_wall_hours": 4.0,
    "m3_peak_mlx_memory_gb": 13.0,
    "m3_per_fold_wall_hours": 4.5,
    "m3_total_wall_hours": 22.5,
    "maximum_m1_fold_runs": 5,
    "maximum_m3_fold_runs": 5,
}
FROZEN_TRAIN_PATH = "data/stack-overflow-emotion-gold/derived-private/task-v1/train.jsonl"
FROZEN_TRAIN_SHA256 = "fc2f853b5b8afb78253ca3a96b5093d2fd12ea7063801f57bf138c9d5cf528fc"
FROZEN_FOLD_MANIFEST_PATH = (
    "experiments/stack-overflow-emotion-gold/oof-router/runs/"
    "exp-058-fold-manifest-preflight-attempt-2/fold-manifest.public.jsonl"
)
FROZEN_FOLD_MANIFEST_SHA256 = "82929b1d837ceb9825c5bc39a8fea18f6d0736fca42aad630f3788b1ff8139d8"
FROZEN_SHARED_CONFIG_PATH = "experiments/stack-overflow-emotion-gold/model-comparison/config.json"
FROZEN_SHARED_CONFIG_BYTES = 6720
FROZEN_SHARED_CONFIG_SHA256 = "d97b7c837b5de4ef014a553fa255ebea4ecdffa848d19715d084bf7ed46177d6"


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


def require_digest(value: Any, field: str) -> str:
    digest = str(value)
    if not SHA256_RE.fullmatch(digest) or digest == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256")
    return digest


def lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def reject_symlink_ancestors(relative: Path, field: str) -> None:
    cursor = PROJECT_ROOT
    for part in relative.parts:
        cursor /= part
        if lexists(cursor) and stat.S_ISLNK(os.lstat(cursor).st_mode):
            raise ValueError(f"{field} contains a symlink or broken symlink: {cursor}")


def resolve_project(value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        raise ValueError(f"Project-relative path is not normalized: {value}")
    reject_symlink_ancestors(relative, "Input record path")
    path = (PROJECT_ROOT / relative).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Project-relative path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))


def resolve_output(value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        raise ValueError(f"Output path is not normalized project-relative data: {value}")
    reject_symlink_ancestors(relative, "Output path")
    resolved = (PROJECT_ROOT / relative).resolve()
    if not resolved.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Output path escapes project root: {value}")
    return resolved


def artifact(path: Path) -> dict[str, Any]:
    return {"path": display_path(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def create_json_once(path: Path, value: Any) -> None:
    if lexists(path):
        raise FileExistsError(f"Refusing to overwrite append-only verification: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
        os.link(temporary, path)
    finally:
        if lexists(temporary):
            temporary.unlink()


def require_record(record: Any, field: str) -> Path:
    if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
        raise ValueError(f"{field} must be an exact path/bytes/sha256 artifact record")
    require_digest(record["sha256"], f"{field}.sha256")
    path = resolve_project(str(record["path"]))
    if not lexists(path) or stat.S_ISLNK(os.lstat(path).st_mode) or not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Frozen artifact drift: {field}")
    return path


def load_json_record(record: dict[str, Any], field: str) -> dict[str, Any]:
    return json.loads(require_record(record, field).read_text(encoding="utf-8"))


def expected_seed_contract(seed: int) -> dict[str, int]:
    return {
        "model_seed": seed,
        "python_seed": seed,
        "numpy_seed": seed,
        "torch_seed": seed,
        "m1_batch_seed": seed,
        "m3_head_seed": seed,
        "m3_batch_seed": seed,
        "m3_lora_seed": seed + 100000,
    }


def expected_outputs(run_id: str, attempt_id: str) -> dict[str, str]:
    public_namespace = PUBLIC_RUNS_ROOT / run_id
    private_namespace = PRIVATE_RUNS_ROOT / run_id
    return {
        "public_namespace": display_path(public_namespace),
        "public_attempt_dir": display_path(public_namespace / attempt_id),
        "private_namespace": display_path(private_namespace),
        "private_attempt_dir": display_path(private_namespace / attempt_id),
        "selection_record": display_path(public_namespace / "selected-attempt.json"),
    }


def shared_scientific_contract(config: dict[str, Any]) -> dict[str, Any]:
    execution = {key: value for key, value in config["execution"].items() if key != "model_seed"}
    implementation = {
        key: value for key, value in config["implementation"].items() if key != "protocol"
    }
    return {
        "data": config["data"],
        "fold_manifest": config["prerequisites"]["fold_manifest"],
        "consumer_contract": config["prerequisites"]["consumer_contract"],
        "fold_verification": config["prerequisites"]["fold_verification"],
        "shared_config": config["prerequisites"]["shared_config"],
        "implementation": implementation,
        "execution": execution,
        "m1": config["m1"],
        "m3": config["m3"],
        "resources": config["resources"],
    }


def shared_scientific_contract_sha256(config: dict[str, Any]) -> str:
    return canonical_digest(shared_scientific_contract(config))


def validate_identity(config: dict[str, Any]) -> dict[str, Any]:
    if set(config) != CONFIG_KEYS or config.get("schema_version") != CONFIG_SCHEMA:
        raise ValueError("Initialization preflight config schema drift")
    identity = IDENTITIES.get(str(config.get("experiment_id")))
    if identity is None:
        raise ValueError("Initialization preflight is restricted to EXP-061/EXP-062")
    seed = int(identity["seed"])
    if (
        config.get("rq_id") != RQ_ID
        or config.get("tier") != "Major"
        or config.get("stage") != STAGE
        or config.get("run_id") != identity["preflight_run_id"]
        or config.get("formal_run_id") != identity["formal_run_id"]
    ):
        raise ValueError("Initialization preflight identity drift")
    for key in ("attempt_id", "formal_attempt_id"):
        if not ATTEMPT_RE.fullmatch(str(config.get(key, ""))):
            raise ValueError(f"{key} must match attempt-[1-9][0-9]*")
    if config.get("seed_contract") != expected_seed_contract(seed):
        raise ValueError("Exact initialization RNG seed contract drift")
    if config.get("authorization") != {"model_seed": seed, **AUTHORIZATION_TEMPLATE}:
        raise PermissionError("No-result initialization authorization drift")
    if config.get("execution") != {"model_seed": seed, **V2_EXECUTION}:
        raise ValueError("Initialization execution contract drift")
    if config.get("m1") != V2_M1 or config.get("m3") != V2_M3:
        raise ValueError("Initialization M1/M3 scientific contract drift")
    if config.get("resources") != V2_RESOURCES:
        raise ValueError("Initialization resource contract drift")
    if config.get("outputs") != expected_outputs(config["run_id"], config["attempt_id"]):
        raise ValueError("Preflight outputs are not canonical derived paths")
    if config.get("formal_outputs") != expected_outputs(
        config["formal_run_id"], config["formal_attempt_id"]
    ):
        raise ValueError("Formal outputs are not canonical derived paths")
    for section in ("outputs", "formal_outputs"):
        if set(config[section]) != OUTPUT_KEYS:
            raise ValueError(f"{section} schema drift")
        for value in config[section].values():
            resolve_output(value)
    if set(config.get("implementation", {})) != FORMAL_IMPLEMENTATION_KEYS:
        raise ValueError("Formal implementation source inventory drift")
    if set(config.get("preflight_implementation", {})) != PREFLIGHT_IMPLEMENTATION_KEYS:
        raise ValueError("Preflight implementation source inventory drift")
    expected_formal_paths = {
        "protocol": FORMAL_PROTOCOL_PATHS[config["experiment_id"]],
        **FORMAL_IMPLEMENTATION_PATHS,
    }
    for section, expected_paths in (
        ("implementation", expected_formal_paths),
        ("preflight_implementation", PREFLIGHT_IMPLEMENTATION_PATHS),
    ):
        for name, expected_path in expected_paths.items():
            record = config[section][name]
            if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
                raise ValueError(f"{section}.{name} artifact schema drift")
            if record.get("path") != expected_path:
                raise ValueError(f"{section}.{name} canonical path drift")
            require_digest(record.get("sha256"), f"{section}.{name}.sha256")
    if set(config.get("prerequisites", {})) != PREREQUISITE_KEYS:
        raise ValueError("Preflight prerequisite inventory drift")
    data = config.get("data")
    if not isinstance(data, dict) or set(data) != {"train", "protocol_id", "label_order"}:
        raise ValueError("Preflight data schema drift")
    if data["protocol_id"] != "DATA-SO-TASK-V1" or tuple(data["label_order"]) != LABELS:
        raise ValueError("Frozen train protocol or label order drift")
    train = data["train"]
    fold = config["prerequisites"]["fold_manifest"]
    shared = config["prerequisites"]["shared_config"]
    if (
        not isinstance(train, dict)
        or train.get("path") != FROZEN_TRAIN_PATH
        or train.get("sha256") != FROZEN_TRAIN_SHA256
        or not isinstance(fold, dict)
        or fold.get("path") != FROZEN_FOLD_MANIFEST_PATH
        or fold.get("sha256") != FROZEN_FOLD_MANIFEST_SHA256
        or not isinstance(shared, dict)
        or shared.get("path") != FROZEN_SHARED_CONFIG_PATH
        or shared.get("bytes") != FROZEN_SHARED_CONFIG_BYTES
        or shared.get("sha256") != FROZEN_SHARED_CONFIG_SHA256
    ):
        raise PermissionError("Preflight must bind the frozen EXP-058 train/fold/shared identity")
    for section in ("implementation", "preflight_implementation", "prerequisites"):
        for name, record in config[section].items():
            if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
                raise ValueError(f"{section}.{name} artifact schema drift")
            require_digest(record["sha256"], f"{section}.{name}.sha256")
    return identity


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    validate_identity(config)
    require_record(config["data"]["train"], "data.train")
    for section in ("implementation", "preflight_implementation", "prerequisites"):
        for name, record in config[section].items():
            require_record(record, f"{section}.{name}")
    live_verifier = require_record(
        config["preflight_implementation"]["verifier"], "preflight_implementation.verifier"
    )
    if live_verifier != LIVE_PREFLIGHT_VERIFIER_PATH.resolve():
        raise ValueError("Preflight verifier record is not bound to the live verifier artifact")
    config["_config_path"] = str(path.resolve())
    config["_config_sha256"] = sha256(path)
    return config


def preflight_run_dir(config: dict[str, Any]) -> Path:
    return resolve_output(config["outputs"]["public_attempt_dir"])


def preflight_private_dir(config: dict[str, Any]) -> Path:
    return resolve_output(config["outputs"]["private_attempt_dir"])


def assert_output_boundaries(config: dict[str, Any]) -> None:
    run_dir = preflight_run_dir(config)
    private_dir = preflight_private_dir(config)
    if (
        not lexists(run_dir)
        or not lexists(private_dir)
        or stat.S_ISLNK(os.lstat(run_dir).st_mode)
        or stat.S_ISLNK(os.lstat(private_dir).st_mode)
        or not run_dir.is_dir()
        or not private_dir.is_dir()
    ):
        raise FileNotFoundError("Preflight attempt directories are incomplete")
    if (private_dir.stat().st_mode & 0o777) != 0o700:
        raise PermissionError("Private preflight attempt must be mode 0700")
    if any(private_dir.rglob("*")):
        raise ValueError("No-result preflight private attempt must remain empty")
    forbidden = (
        resolve_output(config["formal_outputs"]["public_attempt_dir"]),
        resolve_output(config["formal_outputs"]["private_attempt_dir"]),
        resolve_output(config["formal_outputs"]["selection_record"]),
        resolve_output(config["outputs"]["selection_record"]),
    )
    existing = [display_path(path) for path in forbidden if lexists(path)]
    if existing:
        raise FileExistsError(f"Formal/preflight selection boundary drift: {existing}")
    if lexists(run_dir / "failure.json"):
        raise RuntimeError("Preflight attempt is sealed by an initialization failure")


def base_asset_manifest_sha256(shared: dict[str, Any]) -> str:
    return canonical_digest(
        {
            "m1": shared["models"]["m1"]["manifest_sha256"],
            "m3": shared["models"]["qwen_shared"]["manifest_sha256"],
        }
    )


def verify_model_files(shared: dict[str, Any], family: str) -> dict[str, Any]:
    if family == "m1":
        spec, manifest_key = shared["models"]["m1"], "files"
    elif family == "m3":
        spec, manifest_key = shared["models"]["qwen_shared"], "mlx_bf16"
    else:
        raise ValueError(f"Unknown model family: {family}")
    manifest_path = resolve_project(spec["manifest_path"])
    root = resolve_project(spec["local_path"])
    require_digest(spec["manifest_sha256"], f"shared.models.{family}.manifest_sha256")
    if sha256(manifest_path) != spec["manifest_sha256"]:
        raise ValueError(f"{family} model manifest drift")
    content = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = content["files"] if manifest_key == "files" else content[manifest_key]["files"]
    for index, record in enumerate(files):
        lexical_path = root / record["path"]
        reject_symlink_ancestors(
            lexical_path.relative_to(PROJECT_ROOT.resolve()), "Model asset path"
        )
        path = lexical_path.resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError(f"Model asset escapes local root: {record['path']}")
        if (
            not path.is_file()
            or path.stat().st_size != int(record["bytes"])
            or sha256(path) != record["sha256"]
        ):
            raise ValueError(f"Model asset drift: {family}[{index}]")
    return {"manifest": artifact(manifest_path), "file_count": len(files)}


def load_shared(config: dict[str, Any]) -> dict[str, Any]:
    shared = load_json_record(config["prerequisites"]["shared_config"], "prerequisites.shared_config")
    if shared["data"]["test_status"] != "sealed_not_authorized_for_model_access":
        raise PermissionError("Shared config no longer seals test")
    if shared["data"]["protocol_id"] != config["data"]["protocol_id"]:
        raise ValueError("Shared/train protocol drift")
    if tuple(shared["data"]["labels"]) != LABELS:
        raise ValueError("Shared label order drift")
    if shared["data"]["train_sha256"] != config["data"]["train"]["sha256"]:
        raise ValueError("Shared/train SHA-256 drift")
    return shared


def read_partition_ids(config: dict[str, Any]) -> dict[str, Any]:
    train_path = require_record(config["data"]["train"], "data.train")
    manifest_path = require_record(
        config["prerequisites"]["fold_manifest"], "prerequisites.fold_manifest"
    )
    train_ids: list[str] = []
    components: dict[str, str] = {}
    with train_path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            row = json.loads(line)
            if set(row) != TRAIN_FIELDS or row.get("protocol_id") != "DATA-SO-TASK-V1":
                raise ValueError(f"Train schema drift at row {line_number}")
            sample_id = str(row["sample_id"])
            if sample_id in components:
                raise ValueError("Duplicate train sample ID")
            labels = row["labels"]
            if len(labels) != len(LABELS) or any(value not in (0, 1) for value in labels):
                raise ValueError("Invalid train label vector")
            cardinality = sum(labels)
            if row["label_cardinality"] != cardinality or row["neutral"] != (cardinality == 0):
                raise ValueError("Train derived-field drift")
            train_ids.append(sample_id)
            components[sample_id] = str(row["component_id"])
    assignments: dict[str, tuple[int, str]] = {}
    with manifest_path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            row = json.loads(line)
            sample_id = str(row.get("sample_id"))
            if (
                set(row) != MANIFEST_FIELDS
                or row.get("experiment_id") != "EXP-058"
                or row.get("protocol_id") != "DATA-SO-TASK-V1"
                or row.get("fold_id") not in range(5)
                or sample_id in assignments
            ):
                raise ValueError(f"Fold manifest schema drift at row {line_number}")
            assignments[sample_id] = (int(row["fold_id"]), str(row["component_id"]))
    if len(train_ids) != 3360 or len(set(components.values())) != 3277:
        raise ValueError("Frozen train row/component count drift")
    if set(train_ids) != set(assignments):
        raise ValueError("Fold manifest does not cover train exactly")
    for sample_id in train_ids:
        if assignments[sample_id][1] != components[sample_id]:
            raise ValueError("Train/fold component identity drift")
    training_ids: dict[int, list[str]] = {}
    fold_summary: dict[str, dict[str, Any]] = {}
    for fold_id in range(5):
        training = [sample_id for sample_id in train_ids if assignments[sample_id][0] != fold_id]
        heldout = [sample_id for sample_id in train_ids if assignments[sample_id][0] == fold_id]
        train_components = {components[sample_id] for sample_id in training}
        heldout_components = {components[sample_id] for sample_id in heldout}
        if len(training) != 2688 or len(heldout) != 672 or train_components & heldout_components:
            raise ValueError(f"Fold {fold_id} partition/leakage contract drift")
        training_ids[fold_id] = training
        fold_summary[str(fold_id)] = {
            "training_rows": len(training),
            "heldout_rows": len(heldout),
            "training_order_sha256": canonical_digest(training),
        }
    return {
        "train_rows": len(train_ids),
        "duplicate_components": len(set(components.values())),
        "fold_manifest_sha256": sha256(manifest_path),
        "training_ids": training_ids,
        "folds": fold_summary,
    }


def validate_fold_prerequisites(config: dict[str, Any], fold_sha256: str) -> None:
    contract = load_json_record(
        config["prerequisites"]["consumer_contract"], "prerequisites.consumer_contract"
    )
    verification = load_json_record(
        config["prerequisites"]["fold_verification"], "prerequisites.fold_verification"
    )
    if contract.get("fold_manifest_sha256") != fold_sha256:
        raise ValueError("Consumer contract/fold manifest SHA-256 drift")
    if contract.get("forbidden_splits") != ["validation", "test"]:
        raise PermissionError("Consumer contract no longer forbids validation/test")
    if verification.get("status") != "Passed" or int(verification.get("failed_count", -1)) != 0:
        raise RuntimeError("Fold manifest does not have a clean independent verification")


def source_artifacts(config: dict[str, Any]) -> dict[str, Any]:
    return {
        section: {
            name: artifact(require_record(record, f"{section}.{name}"))
            for name, record in sorted(config[section].items())
        }
        for section in ("implementation", "preflight_implementation", "prerequisites")
    }


def static_observation(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    shared = load_shared(config)
    partitions = read_partition_ids(config)
    validate_fold_prerequisites(config, partitions["fold_manifest_sha256"])
    models = {family: verify_model_files(shared, family) for family in ("m1", "m3")}
    base_digest = base_asset_manifest_sha256(shared)
    require_digest(base_digest, "base_asset_manifest_sha256")
    return {
        "config": artifact(config_path),
        "shared_scientific_contract_sha256": shared_scientific_contract_sha256(config),
        "sources": source_artifacts(config),
        "train": artifact(require_record(config["data"]["train"], "data.train")),
        "base_assets": {
            "base_asset_manifest_sha256": base_digest,
            "families": models,
        },
        "fold_manifest_sha256": partitions["fold_manifest_sha256"],
        "partition_contract": {
            "train_rows": partitions["train_rows"],
            "duplicate_components": partitions["duplicate_components"],
            "folds": partitions["folds"],
        },
    }


def require_passed_json(path: Path, schema_version: str) -> dict[str, Any]:
    if not lexists(path) or stat.S_ISLNK(os.lstat(path).st_mode) or not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != schema_version or value.get("status") != "Passed":
        raise RuntimeError(f"Required stage has not passed: {path}")
    return value


def verification_stage_path(config: dict[str, Any], family: str, fold_id: int) -> Path:
    return (
        preflight_run_dir(config)
        / "verification-stages"
        / f"fold-{fold_id}"
        / f"{family}-init.json"
    )


def model_stage_path(config: dict[str, Any], family: str, fold_id: int) -> Path:
    return preflight_run_dir(config) / f"fold-{fold_id}" / f"{family}-init.json"


def sample_order_digest(training_ids: Sequence[str], orders: Iterable[Sequence[int]]) -> str:
    epoch_digests: list[str] = []
    expected = list(range(len(training_ids)))
    for order in orders:
        indices = [int(index) for index in order]
        if sorted(indices) != expected:
            raise ValueError("Batch sample order is not a complete permutation")
        epoch_digests.append(canonical_digest([training_ids[index] for index in indices]))
    if not epoch_digests:
        raise ValueError("At least one epoch order is required")
    return canonical_digest(epoch_digests)


def expected_public_files() -> set[str]:
    allowed = {"static.json", "failure.json", "initialization-manifest.json", "verification.json",
               "verification-stages/static.json"}
    for fold_id in range(5):
        for family in ("m1", "m3"):
            allowed.add(f"fold-{fold_id}/{family}-init.json")
            allowed.add(f"verification-stages/fold-{fold_id}/{family}-init.json")
    return allowed


def expected_public_schema(relative: str) -> str | None:
    exact = {
        "static.json": "exp-oof-initialization-static-v1",
        "failure.json": "exp-oof-initialization-preflight-failure-v1",
        "initialization-manifest.json": "exp-oof-initialization-manifest-v1",
        "verification.json": "exp-oof-initialization-preflight-verification-v1",
        "verification-stages/static.json": "exp-oof-initialization-static-verification-v1",
    }
    if relative in exact:
        return exact[relative]
    match = re.fullmatch(r"(?:verification-stages/)?fold-[0-4]/(m1|m3)-init\.json", relative)
    if match:
        verified = relative.startswith("verification-stages/")
        return f"exp-oof-{match.group(1)}-initialization{'-verification' if verified else ''}-v1"
    return None


def public_artifact_violations(config: dict[str, Any]) -> list[str]:
    root = preflight_run_dir(config)
    if not root.is_dir():
        return []
    allowed = expected_public_files()
    allowed_directories = {
        str(parent) for relative in allowed for parent in Path(relative).parents if str(parent) != "."
    }
    violations: list[str] = []
    for path in sorted(root.rglob("*")):
        relative = str(path.relative_to(root))
        if stat.S_ISLNK(os.lstat(path).st_mode):
            violations.append(f"symlink:{relative}")
        elif path.is_dir():
            if relative not in allowed_directories:
                violations.append(f"unexpected-directory:{relative}")
        elif relative not in allowed:
            violations.append(f"unexpected:{relative}")
        else:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                violations.append(f"invalid-json:{relative}")
                continue
            if value.get("schema_version") != expected_public_schema(relative):
                violations.append(f"schema:{relative}")
            if public_sensitive_paths(value):
                violations.append(f"sensitive:{relative}")
    return violations


def assert_public_artifact_allowlist(config: dict[str, Any]) -> None:
    violations = public_artifact_violations(config)
    if violations:
        raise ValueError(f"Preflight public artifact allowlist/schema violation: {violations}")


def m1_rng_state_digest(seed_contract: dict[str, int]) -> str:
    return canonical_digest(
        {
            key: seed_contract[key]
            for key in ("python_seed", "numpy_seed", "torch_seed", "m1_batch_seed")
        }
    )


def m3_rng_state_digest(seed_contract: dict[str, int]) -> str:
    return canonical_digest(
        {
            key: seed_contract[key]
            for key in ("m3_head_seed", "m3_batch_seed", "m3_lora_seed")
        }
    )


def initialization_state_sha256(family: str, observed: dict[str, Any]) -> str:
    fields = {
        "m1": ("m1_classifier_init_sha256", "m1_rng_state_digest"),
        "m3": (
            "m3_lora_a_init_sha256",
            "m3_lora_b_init_sha256",
            "m3_lora_combined_init_sha256",
            "m3_classifier_head_init_sha256",
            "m3_base_sentinel_sha256",
            "m3_rng_state_digest",
        ),
    }
    return canonical_digest({key: observed[key] for key in fields[family]})


def common_fold_identity(config: dict[str, Any], static: dict[str, Any]) -> dict[str, Any]:
    return {
        "model_seed": config["seed_contract"]["model_seed"],
        "base_asset_manifest_sha256": static["observed"]["base_assets"][
            "base_asset_manifest_sha256"
        ],
        "fold_manifest_sha256": static["observed"]["fold_manifest_sha256"],
    }


def torch_tensor_digest(parameters: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(parameters.items()):
        array = tensor.detach().cpu().float().contiguous().numpy()
        digest.update(name.encode())
        digest.update(str(tuple(array.shape)).encode())
        digest.update(array.tobytes())
    return digest.hexdigest()


def mlx_trainable(module: Any) -> list[tuple[str, Any]]:
    from mlx.utils import tree_flatten

    return list(tree_flatten(module.trainable_parameters()))


def mlx_tensor_digest(items: list[tuple[str, Any]]) -> str:
    import numpy as np
    import mlx.core as mx

    digest = hashlib.sha256()
    for name, tensor in sorted(items):
        array = np.asarray(tensor.astype(mx.float32))
        digest.update(name.encode())
        digest.update(str(tuple(array.shape)).encode())
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def independent_insertion_contract(model: Any, shared: dict[str, Any]) -> list[tuple[int, str]]:
    observed: list[tuple[int, str]] = []
    for name, module in model.named_modules():
        if type(module).__name__ != "LoRALinear":
            continue
        match = re.search(r"(?:^|\.)layers\.(\d+)\.(.+)$", name)
        if not match:
            raise ValueError(f"Unexpected LoRA path: {name}")
        observed.append((int(match.group(1)), match.group(2)))
    lora = shared["models"]["lora_shared"]
    expected = [
        (block, target)
        for block in lora["adapted_block_indices"]
        for target in lora["target_modules"]
    ]
    if sorted(observed) != sorted(expected):
        raise ValueError("LoRA insertion set drift")
    return observed


def independent_base_sentinel(model: Any) -> str:
    import numpy as np
    import mlx.core as mx
    from mlx.utils import tree_flatten

    base_items = [
        (name, tensor)
        for name, tensor in tree_flatten(model.parameters())
        if not name.endswith((".lora_a", ".lora_b"))
    ]
    base_items.sort(key=lambda item: item[0])
    positions = sorted({round(index * (len(base_items) - 1) / 15) for index in range(16)})
    digest = hashlib.sha256()
    for position in positions:
        name, tensor = base_items[position]
        size = int(tensor.size)
        indices = sorted({0, size // 3, (2 * size) // 3, size - 1})
        sample = np.asarray(tensor.reshape(-1)[mx.array(indices)].astype(mx.float32))
        digest.update(name.encode())
        digest.update(str(tuple(tensor.shape)).encode())
        digest.update(sample.tobytes(order="C"))
    return digest.hexdigest()


def require_static_verification(config: dict[str, Any]) -> dict[str, Any]:
    return require_passed_json(
        preflight_run_dir(config) / "verification-stages" / "static.json",
        "exp-oof-initialization-static-verification-v1",
    )


def observe_m1_initialization(config: dict[str, Any], fold_id: int) -> dict[str, Any]:
    static = require_passed_json(
        preflight_run_dir(config) / "static.json", "exp-oof-initialization-static-v1"
    )
    require_static_verification(config)
    shared = load_shared(config)
    verify_model_files(shared, "m1")
    training_ids = read_partition_ids(config)["training_ids"][fold_id]
    import numpy as np
    import torch
    from transformers import AutoModelForSequenceClassification

    os.environ.update(
        {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    )
    contract = config["seed_contract"]
    random.seed(contract["python_seed"])
    np.random.seed(contract["numpy_seed"])
    torch.manual_seed(contract["torch_seed"])
    torch.use_deterministic_algorithms(True, warn_only=True)
    model_spec = shared["models"]["m1"]
    model = AutoModelForSequenceClassification.from_pretrained(
        resolve_project(model_spec["local_path"]),
        local_files_only=True,
        num_labels=len(LABELS),
        id2label={index: label for index, label in enumerate(LABELS)},
        label2id={label: index for index, label in enumerate(LABELS)},
        problem_type="multi_label_classification",
        ignore_mismatched_sizes=True,
    )
    if type(model.classifier).__name__ != "RobertaClassificationHead":
        raise ValueError("M1 fresh classification head contract drift")
    classifier = torch_tensor_digest(
        {name: value for name, value in model.named_parameters() if name.startswith("classifier.")}
    )
    rng_digest = m1_rng_state_digest(contract)
    state_digest = initialization_state_sha256(
        "m1", {"m1_classifier_init_sha256": classifier, "m1_rng_state_digest": rng_digest}
    )
    generator = torch.Generator().manual_seed(contract["m1_batch_seed"])
    orders = [
        torch.randperm(len(training_ids), generator=generator).tolist()
        for _ in range(config["execution"]["m1_epochs"])
    ]
    batch_digest = sample_order_digest(training_ids, orders)
    del model
    gc.collect()
    return {
        **common_fold_identity(config, static),
        "m1_classifier_init_sha256": classifier,
        "m1_rng_state_digest": rng_digest,
        "m1_initialization_state_sha256": state_digest,
        "m1_batch_order_sha256": batch_digest,
    }


def observe_m3_initialization(config: dict[str, Any], fold_id: int) -> dict[str, Any]:
    static = require_passed_json(
        preflight_run_dir(config) / "static.json", "exp-oof-initialization-static-v1"
    )
    require_static_verification(config)
    shared = load_shared(config)
    verify_model_files(shared, "m3")
    training_ids = read_partition_ids(config)["training_ids"][fold_id]
    import numpy as np
    import mlx.core as mx
    import mlx.nn as nn
    from mlx_lm import load
    from mlx_lm.tuner import linear_to_lora_layers

    os.environ.update(
        {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    )
    spec = shared["models"]["qwen_shared"]
    lora = shared["models"]["lora_shared"]
    model, _tokenizer = load(str(resolve_project(spec["local_path"])), lazy=False)
    model.freeze()
    model.eval()
    contract = config["seed_contract"]
    mx.random.seed(contract["m3_head_seed"])
    head = nn.Linear(int(spec["hidden_size"]), len(LABELS), bias=True)
    head_items = mlx_trainable(head)
    head_digest = mlx_tensor_digest(head_items)
    mx.random.seed(contract["m3_lora_seed"])
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
    insertions = independent_insertion_contract(model, shared)
    lora_items = mlx_trainable(model)
    lora_a_items = [(name, tensor) for name, tensor in lora_items if name.endswith("lora_a")]
    lora_b_items = [(name, tensor) for name, tensor in lora_items if name.endswith("lora_b")]
    if not lora_a_items or len(lora_a_items) != len(lora_b_items):
        raise ValueError("M3 LoRA A/B initialization inventory drift")
    lora_a_digest = mlx_tensor_digest(lora_a_items)
    lora_b_digest = mlx_tensor_digest(lora_b_items)
    lora_digest = mlx_tensor_digest(lora_items)
    b_zero = all(not bool(mx.any(tensor != 0).item()) for _, tensor in lora_b_items)
    lora_count = sum(int(tensor.size) for _, tensor in lora_items)
    head_count = sum(int(tensor.size) for _, tensor in head_items)
    if (
        len(insertions) != 112
        or lora_count != int(lora["trainable_parameters"])
        or lora_count + head_count != int(lora["classification_total_trainable_parameters"])
        or not b_zero
    ):
        raise ValueError("M3 fresh-head/LoRA initialization contract drift")
    base_digest = independent_base_sentinel(model)
    rng_digest = m3_rng_state_digest(contract)
    state_digest = initialization_state_sha256(
        "m3",
        {
            "m3_lora_a_init_sha256": lora_a_digest,
            "m3_lora_b_init_sha256": lora_b_digest,
            "m3_lora_combined_init_sha256": lora_digest,
            "m3_classifier_head_init_sha256": head_digest,
            "m3_base_sentinel_sha256": base_digest,
            "m3_rng_state_digest": rng_digest,
        },
    )
    rng = np.random.default_rng(contract["m3_batch_seed"])
    orders = [
        rng.permutation(len(training_ids)).tolist()
        for _ in range(config["execution"]["m3_epochs"])
    ]
    batch_digest = sample_order_digest(training_ids, orders)
    del head, model, _tokenizer
    gc.collect()
    mx.clear_cache()
    return {
        **common_fold_identity(config, static),
        "m3_lora_a_init_sha256": lora_a_digest,
        "m3_lora_b_init_sha256": lora_b_digest,
        "m3_lora_combined_init_sha256": lora_digest,
        "m3_classifier_head_init_sha256": head_digest,
        "m3_base_sentinel_sha256": base_digest,
        "m3_rng_state_digest": rng_digest,
        "m3_initialization_state_sha256": state_digest,
        "m3_batch_order_sha256": batch_digest,
        "m3_lora_b_zero_initialized": b_zero,
    }


def verification_report(
    config: dict[str, Any], schema_version: str, observed: dict[str, Any], matched: bool, **extra: Any
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "experiment_id": config["experiment_id"],
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "model_seed": config["seed_contract"]["model_seed"],
        **extra,
        "status": "Passed" if matched else "Failed",
        "verified_at_utc": utc_now(),
        "independent": True,
        "preflight_runner_imported": False,
        "formal_runner_imported": False,
        "observed": observed,
        "matched_runner_observation": matched,
        "execution_claims": {
            "optimizer_created": False,
            "training_performed": False,
            "heldout_forward_performed": False,
            "metric_computed": False,
            "validation_accessed": False,
            "test_accessed": False,
        },
    }


def verify_static(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    assert_output_boundaries(config)
    output = preflight_run_dir(config) / "verification-stages" / "static.json"
    if lexists(output):
        raise FileExistsError("Static verification stage is append-only")
    assert_public_artifact_allowlist(config)
    runner_path = preflight_run_dir(config) / "static.json"
    runner = require_passed_json(runner_path, "exp-oof-initialization-static-v1")
    observed = static_observation(config_path, config)
    matched = runner.get("observed") == observed
    report = verification_report(
        config,
        "exp-oof-initialization-static-verification-v1",
        observed,
        matched,
        verified_artifacts={"runner_static": artifact(runner_path)},
    )
    create_json_once(output, report)
    assert_public_artifact_allowlist(config)
    return report


def require_all_m1_verified(config: dict[str, Any]) -> None:
    for fold_id in range(5):
        require_passed_json(
            verification_stage_path(config, "m1", fold_id),
            "exp-oof-m1-initialization-verification-v1",
        )


def verify_model_initialization(
    config: dict[str, Any], family: str, fold_id: int
) -> dict[str, Any]:
    assert_output_boundaries(config)
    output = verification_stage_path(config, family, fold_id)
    if lexists(output):
        raise FileExistsError(f"{family} fold {fold_id} verification stage is append-only")
    assert_public_artifact_allowlist(config)
    require_static_verification(config)
    if family == "m3":
        require_all_m1_verified(config)
    runner_path = model_stage_path(config, family, fold_id)
    runner = require_passed_json(runner_path, f"exp-oof-{family}-initialization-v1")
    observed = (
        observe_m1_initialization(config, fold_id)
        if family == "m1"
        else observe_m3_initialization(config, fold_id)
    )
    matched = runner.get("observed") == observed
    report = verification_report(
        config,
        f"exp-oof-{family}-initialization-verification-v1",
        observed,
        matched,
        fold_id=fold_id,
        verified_artifacts={f"runner_{family}_initialization": artifact(runner_path)},
    )
    create_json_once(output, report)
    assert_public_artifact_allowlist(config)
    return report


def assemble_fold(m1: dict[str, Any], m3: dict[str, Any]) -> dict[str, Any]:
    common = {"model_seed", "base_asset_manifest_sha256", "fold_manifest_sha256"}
    if any(m1.get(key) != m3.get(key) for key in common):
        raise ValueError("M1/M3 fold identity drift")
    combined = {**m1, **m3}
    expected_keys = {"model_seed", *INIT_HASH_FIELDS, "m3_lora_b_zero_initialized"}
    if set(combined) != expected_keys:
        raise ValueError("Combined initialization fold schema drift")
    for field in INIT_HASH_FIELDS:
        require_digest(combined[field], f"fold.{field}")
    if combined["m3_lora_b_zero_initialized"] is not True:
        raise ValueError("LoRA-B equality requires verified zero initialization")
    return combined


def assemble_manifest(config: dict[str, Any], folds: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if set(folds) != {str(index) for index in range(5)}:
        raise ValueError("Initialization manifest must contain exactly five folds")
    base_values = {fold["base_asset_manifest_sha256"] for fold in folds.values()}
    manifest_values = {fold["fold_manifest_sha256"] for fold in folds.values()}
    if len(base_values) != 1 or len(manifest_values) != 1:
        raise ValueError("Cross-fold base/fold source identity drift")
    return {
        "schema_version": "exp-oof-initialization-manifest-v1",
        "experiment_id": config["experiment_id"],
        "run_id": config["formal_run_id"],
        "attempt_id": config["formal_attempt_id"],
        "model_seed": config["seed_contract"]["model_seed"],
        "seed_contract": config["seed_contract"],
        "base_asset_manifest_sha256": next(iter(base_values)),
        "fold_manifest_sha256": next(iter(manifest_values)),
        "shared_scientific_contract_sha256": shared_scientific_contract_sha256(config),
        "cross_seed_gate": {
            "required_before_formal_training": True,
            "status": "Pending",
            "verification_schema": "exp-oof-cross-seed-initialization-verification-v1",
        },
        "folds": folds,
    }


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    forbidden = {
        "sample_id",
        "sample_ids",
        "component_id",
        "component_ids",
        "text",
        "labels",
        "gold",
        "logits",
        "probabilities",
        "predictions",
        "features",
        "targets",
        "masks",
    }
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            if key in forbidden:
                violations.append(child_path)
            violations.extend(public_sensitive_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    return violations


def verify_finalize(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    assert_output_boundaries(config)
    output = preflight_run_dir(config) / "verification.json"
    if lexists(output):
        raise FileExistsError("Final preflight verification is append-only")
    assert_public_artifact_allowlist(config)
    require_static_verification(config)
    run_dir = preflight_run_dir(config)
    manifest_path = run_dir / "initialization-manifest.json"
    if not lexists(manifest_path) or stat.S_ISLNK(os.lstat(manifest_path).st_mode) or not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    folds: dict[str, dict[str, Any]] = {}
    stage_artifacts: dict[str, Any] = {}
    for fold_id in range(5):
        m1_path = verification_stage_path(config, "m1", fold_id)
        m3_path = verification_stage_path(config, "m3", fold_id)
        m1 = require_passed_json(m1_path, "exp-oof-m1-initialization-verification-v1")
        m3 = require_passed_json(m3_path, "exp-oof-m3-initialization-verification-v1")
        folds[str(fold_id)] = assemble_fold(m1["observed"], m3["observed"])
        stage_artifacts[str(fold_id)] = {"m1": artifact(m1_path), "m3": artifact(m3_path)}
    expected = assemble_manifest(config, folds)
    source_recomputed = static_observation(config_path, config)
    static_verified = require_static_verification(config)
    checks = {
        "manifest_exact": manifest == expected,
        "static_sources_unchanged": static_verified.get("observed") == source_recomputed,
        "formal_outputs_absent": True,
        "preflight_selection_absent": True,
        "private_attempt_empty": not any(preflight_private_dir(config).rglob("*")),
        "public_manifest_has_no_row_level_fields": not public_sensitive_paths(manifest),
    }
    failed = [name for name, passed in checks.items() if not passed]
    report = {
        "schema_version": "exp-oof-initialization-preflight-verification-v1",
        "experiment_id": config["experiment_id"],
        "run_id": config["formal_run_id"],
        "attempt_id": config["formal_attempt_id"],
        "model_seed": config["seed_contract"]["model_seed"],
        "seed_contract": config["seed_contract"],
        "shared_scientific_contract_sha256": shared_scientific_contract_sha256(config),
        "status": "Failed" if failed else "Passed",
        "verified_at_utc": utc_now(),
        "independent": True,
        "preflight_runner_imported": False,
        "formal_runner_imported": False,
        "failed_count": len(failed),
        "checks": checks,
        "failed_checks": failed,
        "verified_artifacts": {
            "config": artifact(config_path),
            "initialization_manifest": artifact(manifest_path),
            "stage_verifications": stage_artifacts,
        },
        "formal_config_contract": {
            "initialization_exact_keys": ["base_asset_manifest_sha256", "expected_by_fold"],
            "expected_by_fold_exact_keys": ["model_seed", *INIT_HASH_FIELDS],
            "copy_rule": (
                "formal initialization.expected_by_fold copies manifest.folds after removing only "
                "m3_lora_b_zero_initialized"
            ),
            "prerequisite_records_required": [
                "prerequisites.initialization_manifest",
                "prerequisites.initialization_verification",
                "prerequisites.cross_seed_initialization_verification",
            ],
            "cross_seed_gate_required": True,
        },
        "execution_claims": {
            "models_initialized": True,
            "optimizer_created": False,
            "training_performed": False,
            "heldout_forward_performed": False,
            "metric_computed": False,
            "validation_accessed": False,
            "test_accessed": False,
        },
        "claim_boundary": "Verified fresh initialization and batch-order identity only; formal training remains separate.",
    }
    create_json_once(output, report)
    assert_public_artifact_allowlist(config)
    return report


def initialization_bundle(config: dict[str, Any]) -> dict[str, Any]:
    """Load only already-Passed aggregate initialization artifacts."""
    assert_output_boundaries(config)
    assert_public_artifact_allowlist(config)
    run_dir = preflight_run_dir(config)
    manifest_path = run_dir / "initialization-manifest.json"
    verification_path = run_dir / "verification.json"
    # The manifest intentionally has no status field, so validate it independently.
    if not lexists(manifest_path) or stat.S_ISLNK(os.lstat(manifest_path).st_mode):
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verification = require_passed_json(
        verification_path, "exp-oof-initialization-preflight-verification-v1"
    )
    expected_manifest_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "model_seed",
        "seed_contract", "base_asset_manifest_sha256", "fold_manifest_sha256",
        "shared_scientific_contract_sha256", "cross_seed_gate", "folds",
    }
    if set(manifest) != expected_manifest_keys:
        raise ValueError("Initialization manifest exact schema drift")
    if (
        manifest.get("schema_version") != "exp-oof-initialization-manifest-v1"
        or manifest.get("experiment_id") != config["experiment_id"]
        or manifest.get("run_id") != config["formal_run_id"]
        or manifest.get("attempt_id") != config["formal_attempt_id"]
        or manifest.get("model_seed") != config["seed_contract"]["model_seed"]
        or manifest.get("seed_contract") != config["seed_contract"]
        or manifest.get("shared_scientific_contract_sha256")
        != shared_scientific_contract_sha256(config)
        or manifest.get("cross_seed_gate")
        != {
            "required_before_formal_training": True,
            "status": "Pending",
            "verification_schema": "exp-oof-cross-seed-initialization-verification-v1",
        }
    ):
        raise ValueError("Initialization manifest identity/cross-seed declaration drift")
    folds = manifest.get("folds")
    if not isinstance(folds, dict) or set(folds) != {str(index) for index in range(5)}:
        raise ValueError("Initialization manifest fold coverage drift")
    for fold_id, fold in folds.items():
        if not isinstance(fold, dict) or set(fold) != {
            *EXPECTED_FOLD_KEYS, "m3_lora_b_zero_initialized"
        }:
            raise ValueError(f"Initialization manifest fold {fold_id} schema drift")
        if fold["model_seed"] != config["seed_contract"]["model_seed"]:
            raise ValueError(f"Initialization manifest fold {fold_id} seed drift")
        for field in INIT_HASH_FIELDS:
            require_digest(fold[field], f"manifest.folds.{fold_id}.{field}")
        if fold["m3_lora_b_zero_initialized"] is not True:
            raise ValueError("LoRA-B equality requires verified zero initialization")
    manifest_record = artifact(manifest_path)
    if (
        verification.get("experiment_id") != config["experiment_id"]
        or verification.get("run_id") != config["formal_run_id"]
        or verification.get("attempt_id") != config["formal_attempt_id"]
        or verification.get("model_seed") != config["seed_contract"]["model_seed"]
        or verification.get("seed_contract") != config["seed_contract"]
        or verification.get("failed_count") != 0
        or verification.get("verified_artifacts", {}).get("initialization_manifest")
        != manifest_record
    ):
        raise RuntimeError("Initialization manifest does not have a bound Passed verification")
    return {
        "manifest": manifest,
        "verification": verification,
        "manifest_record": manifest_record,
        "verification_record": artifact(verification_path),
    }


def build_cross_seed_report(
    configs: dict[str, dict[str, Any]], bundles: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    if set(configs) != {"EXP-061", "EXP-062"} or set(bundles) != set(configs):
        raise ValueError("Cross-seed gate requires exactly EXP-061 and EXP-062")
    left, right = configs["EXP-061"], configs["EXP-062"]
    left_manifest = bundles["EXP-061"]["manifest"]
    right_manifest = bundles["EXP-062"]["manifest"]
    shared_digest = shared_scientific_contract_sha256(left)
    checks: dict[str, bool] = {
        "registered_seeds_43_44": (
            left["seed_contract"]["model_seed"], right["seed_contract"]["model_seed"]
        ) == (43, 44),
        "shared_scientific_contract_identical": (
            shared_digest
            == shared_scientific_contract_sha256(right)
            == left_manifest["shared_scientific_contract_sha256"]
            == right_manifest["shared_scientific_contract_sha256"]
        ),
        "base_asset_identity_identical": (
            left_manifest["base_asset_manifest_sha256"]
            == right_manifest["base_asset_manifest_sha256"]
        ),
        "fold_manifest_identity_identical": (
            left_manifest["fold_manifest_sha256"] == right_manifest["fold_manifest_sha256"]
        ),
    }
    per_fold: dict[str, dict[str, bool]] = {}
    for fold_id in range(5):
        fold_43 = left_manifest["folds"][str(fold_id)]
        fold_44 = right_manifest["folds"][str(fold_id)]
        fold_checks = {
            "m1_classifier_differs": (
                fold_43["m1_classifier_init_sha256"] != fold_44["m1_classifier_init_sha256"]
            ),
            "m3_lora_a_differs": (
                fold_43["m3_lora_a_init_sha256"] != fold_44["m3_lora_a_init_sha256"]
            ),
            "m3_classifier_head_differs": (
                fold_43["m3_classifier_head_init_sha256"]
                != fold_44["m3_classifier_head_init_sha256"]
            ),
            "m3_lora_b_equality_allowed_only_when_zero": (
                fold_43["m3_lora_b_init_sha256"] != fold_44["m3_lora_b_init_sha256"]
                or (
                    fold_43["m3_lora_b_zero_initialized"] is True
                    and fold_44["m3_lora_b_zero_initialized"] is True
                )
            ),
        }
        per_fold[str(fold_id)] = fold_checks
        checks[f"fold_{fold_id}_seed_sensitive_initialization"] = all(fold_checks.values())
    failed = [name for name, passed in checks.items() if not passed]
    members = {}
    for experiment_id in ("EXP-061", "EXP-062"):
        config = configs[experiment_id]
        bundle = bundles[experiment_id]
        members[experiment_id] = {
            "model_seed": config["seed_contract"]["model_seed"],
            "preflight_run_id": config["run_id"],
            "preflight_attempt_id": config["attempt_id"],
            "formal_run_id": config["formal_run_id"],
            "formal_attempt_id": config["formal_attempt_id"],
            "initialization_manifest": bundle["manifest_record"],
            "initialization_verification": bundle["verification_record"],
        }
    return {
        "schema_version": "exp-oof-cross-seed-initialization-verification-v1",
        "status": "Failed" if failed else "Passed",
        "verified_at_utc": utc_now(),
        "failed_count": len(failed),
        "failed_checks": failed,
        "shared_scientific_contract_sha256": shared_digest,
        "base_asset_manifest_sha256": left_manifest["base_asset_manifest_sha256"],
        "fold_manifest_sha256": left_manifest["fold_manifest_sha256"],
        "members": members,
        "checks": checks,
        "per_fold_checks": per_fold,
        "execution_claims": {
            "aggregate_only": True,
            "model_loaded": False,
            "training_performed": False,
            "heldout_forward_performed": False,
            "metric_computed": False,
            "validation_accessed": False,
            "test_accessed": False,
        },
        "claim_boundary": "Cross-seed initialization identity only; no model result or performance claim.",
    }


def cross_seed_output_path(configs: dict[str, dict[str, Any]]) -> Path:
    left, right = configs["EXP-061"], configs["EXP-062"]
    name = (
        f"{left['attempt_id']}--{left['formal_attempt_id']}--"
        f"{right['attempt_id']}--{right['formal_attempt_id']}.json"
    )
    relative_base = display_path(SCRIPT_DIR)
    return resolve_output(
        f"{relative_base}/runs/exp-061-exp-062-initialization-cross-seed/{name}"
    )


def assert_cross_seed_namespace_clean(output: Path) -> None:
    namespace = output.parent
    if not lexists(namespace):
        return
    if stat.S_ISLNK(os.lstat(namespace).st_mode) or not namespace.is_dir():
        raise ValueError("Cross-seed aggregate namespace must be a real directory")
    for child in namespace.iterdir():
        if stat.S_ISLNK(os.lstat(child).st_mode) or not child.is_file() or child.suffix != ".json":
            raise ValueError(f"Unexpected cross-seed aggregate artifact: {child}")
        value = json.loads(child.read_text(encoding="utf-8"))
        if value.get("schema_version") != "exp-oof-cross-seed-initialization-verification-v1":
            raise ValueError(f"Cross-seed aggregate schema drift: {child}")


def verify_cross_seed(
    config: dict[str, Any], peer_config: dict[str, Any]
) -> dict[str, Any]:
    configs = {config["experiment_id"]: config, peer_config["experiment_id"]: peer_config}
    if set(configs) != {"EXP-061", "EXP-062"}:
        raise ValueError("--config and --peer-config must be opposite registered seeds")
    bundles = {experiment_id: initialization_bundle(value) for experiment_id, value in configs.items()}
    report = build_cross_seed_report(configs, bundles)
    output = cross_seed_output_path(configs)
    assert_cross_seed_namespace_clean(output)
    create_json_once(output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--scope", choices=SCOPES, required=True)
    parser.add_argument("--fold", type=int)
    parser.add_argument("--peer-config", type=Path)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = load_config(config_path)
    if args.scope == "cross-seed":
        if args.fold is not None or args.peer_config is None:
            raise ValueError("cross-seed requires --peer-config and does not accept --fold")
        peer_config = load_config(args.peer_config.resolve())
        report = verify_cross_seed(config, peer_config)
    elif args.scope in ("static", "finalize"):
        if args.peer_config is not None:
            raise ValueError(f"{args.scope} does not accept --peer-config")
        if args.fold is not None:
            raise ValueError(f"{args.scope} does not accept --fold")
        report = verify_static(config_path, config) if args.scope == "static" else verify_finalize(config_path, config)
    else:
        if args.fold not in range(5) or args.peer_config is not None:
            raise ValueError("Model initialization scopes require --fold 0..4")
        family = "m1" if args.scope == "m1-init" else "m3"
        report = verify_model_initialization(config, family, args.fold)
    print(json.dumps({"scope": args.scope, "fold": args.fold, "status": report["status"]}, sort_keys=True))
    if report["status"] != "Passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
