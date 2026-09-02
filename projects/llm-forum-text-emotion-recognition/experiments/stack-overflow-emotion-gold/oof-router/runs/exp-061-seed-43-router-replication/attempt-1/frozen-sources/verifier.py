#!/usr/bin/env python3
"""Independently verify EXP-058 fold or final paired OOF production artifacts."""

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
from typing import Any


LEGACY_EXPERIMENT_ID = "EXP-058"
LEGACY_STAGE = "paired-m1-m3-oof-production"
LEGACY_CONFIG_SCHEMA = "exp-058-oof-production-config-v1"
CONFIG_V2_SCHEMA = "exp-oof-production-config-v2"
ATTEMPT_RE = re.compile(r"attempt-[1-9][0-9]*\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
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
LIVE_VERIFIER_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-058-oof-production.json"
PUBLIC_RUNS_ROOT = SCRIPT_DIR / "runs"
PRIVATE_RUNS_ROOT = SCRIPT_DIR / "private"
LEGACY_PUBLIC_RUN = PUBLIC_RUNS_ROOT / "exp-058-paired-oof-production"
LEGACY_PRIVATE_RUN = PRIVATE_RUNS_ROOT / "exp-058-paired-oof-production"

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
V2_IMPLEMENTATION_KEYS = {
    "protocol",
    "runner",
    "verifier",
    "tests",
    "m1_runner_reference",
    "qwen_primitives",
    "m3_preflight_reference",
}
V2_PROTOCOL_PATHS = {
    "EXP-061": "experiments/stack-overflow-emotion-gold/protocols/exp-061-seed-43-router-replication.md",
    "EXP-062": "experiments/stack-overflow-emotion-gold/protocols/exp-062-seed-44-router-replication.md",
}
V2_IMPLEMENTATION_PATHS = {
    "runner": "experiments/stack-overflow-emotion-gold/oof-router/run_exp058_oof_production.py",
    "verifier": "experiments/stack-overflow-emotion-gold/oof-router/verify_exp058_oof_production.py",
    "tests": "experiments/stack-overflow-emotion-gold/oof-router/tests/test_exp058_oof_production.py",
    "m1_runner_reference": "experiments/stack-overflow-emotion-gold/model-comparison/run_exp051_m1.py",
    "qwen_primitives": "experiments/stack-overflow-emotion-gold/model-comparison/run_preflight.py",
    "m3_preflight_reference": "experiments/stack-overflow-emotion-gold/model-comparison/run_exp053_m3_preflight.py",
}
V2_PREREQUISITE_KEYS = {
    "shared_config",
    "fold_manifest",
    "consumer_contract",
    "fold_verification",
    "initialization_manifest",
    "initialization_verification",
    "cross_seed_initialization_verification",
}
V2_DATA_KEYS = {"train", "protocol_id", "label_order"}
V2_CONFIG_KEYS = {
    "schema_version", "experiment_id", "rq_id", "tier", "stage", "run_id", "attempt_id",
    "authorization", "execution", "seed_contract", "data", "implementation", "prerequisites",
    "outputs", "initialization", "m1", "m3", "resources",
}
V2_AUTHORIZATION_KEYS = {
    "authorized_at", "basis", "fold_ids", "model_seed", "assembly", "full_oof_training",
    "heldout_forward", "model_loading", "calibration", "metrics", "oracle_analysis",
    "router_training", "test_access", "validation_access",
    "cross_seed_initialization_verification_sha256",
}
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
        "steps_per_epoch": 168, "planned_scheduler_epochs": 5, "scheduler_horizon_steps": 840,
        "warmup_steps": 84, "selected_stop_epoch": 4, "selected_stop_steps": 672,
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
    "api_cost_usd": 0, "minimum_free_disk_gb": 8.0, "m1_peak_process_memory_gb": 8.0,
    "m1_total_wall_hours": 4.0, "m3_peak_mlx_memory_gb": 13.0,
    "m3_per_fold_wall_hours": 4.5, "m3_total_wall_hours": 22.5,
    "maximum_m1_fold_runs": 5, "maximum_m3_fold_runs": 5,
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
HEAVY_WORKLOAD_LOCK_PATH = (
    "experiments/stack-overflow-emotion-gold/oof-router/private/locks/"
    "heavy-research-workload.lock"
)


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


def is_v2(config: dict[str, Any]) -> bool:
    return config.get("schema_version") == CONFIG_V2_SCHEMA


def experiment_id(config: dict[str, Any]) -> str:
    return str(config["experiment_id"])


def stage_name(config: dict[str, Any]) -> str:
    return str(config["stage"])


def run_id(config: dict[str, Any]) -> str:
    return str(config["run_id"]) if is_v2(config) else "exp-058-paired-oof-production"


def attempt_id(config: dict[str, Any]) -> str | None:
    return str(config["attempt_id"]) if is_v2(config) else None


def model_seed(config: dict[str, Any]) -> int:
    return int(config["execution"]["model_seed"] if is_v2(config) else config["authorization"]["model_seed"])


def seed_contract(config: dict[str, Any]) -> dict[str, int]:
    seed = model_seed(config)
    if not is_v2(config):
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
    return {key: int(value) for key, value in config["seed_contract"].items()}


def m1_rng_state_digest(config: dict[str, Any]) -> str:
    contract = seed_contract(config)
    return canonical_digest(
        {key: contract[key] for key in ("python_seed", "numpy_seed", "torch_seed", "m1_batch_seed")}
    )


def m3_rng_state_digest(config: dict[str, Any]) -> str:
    contract = seed_contract(config)
    return canonical_digest(
        {key: contract[key] for key in ("m3_head_seed", "m3_batch_seed", "m3_lora_seed")}
    )


def require_digest(value: Any, field: str) -> str:
    digest = str(value)
    if not SHA256_RE.fullmatch(digest) or digest == "0" * 64:
        raise ValueError(f"{field} must be a non-placeholder lowercase SHA-256")
    return digest


def base_asset_manifest_sha256(shared: dict[str, Any]) -> str:
    return canonical_digest(
        {
            "m1": shared["models"]["m1"]["manifest_sha256"],
            "m3": shared["models"]["qwen_shared"]["manifest_sha256"],
        }
    )


def expected_initialization(config: dict[str, Any], fold_id: int) -> dict[str, Any]:
    if not is_v2(config):
        return {
            "model_seed": 42,
            "m1_classifier_init_sha256": config["m1"]["expected_classifier_initial_sha256"],
            "m3_classifier_head_init_sha256": config["m3"]["expected_head_initial_sha256"],
            "m3_lora_combined_init_sha256": config["m3"]["expected_lora_initial_sha256"],
            "m3_base_sentinel_sha256": config["m3"]["expected_base_sentinel_sha256"],
        }
    expected = config["initialization"]["expected_by_fold"].get(str(fold_id))
    if not isinstance(expected, dict) or set(expected) != {"model_seed", *INIT_HASH_FIELDS}:
        raise ValueError(f"Initialization expectation schema drift for fold {fold_id}")
    if int(expected["model_seed"]) != model_seed(config):
        raise ValueError(f"Initialization seed drift for fold {fold_id}")
    for field in INIT_HASH_FIELDS:
        require_digest(expected[field], f"initialization.expected_by_fold.{fold_id}.{field}")
    return expected


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
    if family not in fields:
        raise ValueError(f"Unknown initialization family: {family}")
    return canonical_digest({key: observed[key] for key in fields[family]})


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


def resolve_output(value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        raise ValueError(f"Output path is not normalized: {value}")
    reject_symlink_ancestors(relative, "Output path")
    lexical = PROJECT_ROOT / relative
    resolved = lexical.resolve()
    if not resolved.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Output path escapes project root: {value}")
    return resolved


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def artifact(path: Path) -> dict[str, Any]:
    return {"path": display_path(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def require_record(record: dict[str, Any]) -> Path:
    if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
        raise ValueError("Artifact record must have exact path/bytes/sha256 fields")
    require_digest(record["sha256"], "artifact.sha256")
    path = resolve_project(str(record["path"]))
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Artifact drift: {path}")
    return path


def require_record_within(
    record: dict[str, Any], root: Path, *, exact_relative: str | None = None
) -> Path:
    path = require_record(record)
    resolved_root = root.resolve()
    if not path.is_relative_to(resolved_root):
        raise ValueError(f"Artifact escaped its current attempt: {path}")
    if exact_relative is not None and path != (resolved_root / exact_relative).resolve():
        raise ValueError(f"Artifact path drift: expected {exact_relative}, got {path}")
    return path


def tree_artifact(path: Path) -> dict[str, Any]:
    if stat.S_ISLNK(os.lstat(path).st_mode) or not path.is_dir():
        raise ValueError(f"Tree artifact root must be a real directory: {path}")
    symlinks = [child for child in path.rglob("*") if stat.S_ISLNK(os.lstat(child).st_mode)]
    if symlinks:
        raise ValueError(f"Tree artifact contains symlinks: {symlinks}")
    files = []
    total = 0
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        size = child.stat().st_size
        total += size
        files.append(
            {
                "path": str(child.relative_to(path)),
                "bytes": size,
                "sha256": sha256(child),
            }
        )
    return {
        "path": display_path(path),
        "file_count": len(files),
        "bytes": total,
        "sha256": canonical_digest(files),
        "files": files,
    }


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    if lexists(path) or lexists(temporary):
        raise FileExistsError(f"Refusing to overwrite append-only verification artifact: {path}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.link(temporary, path)
    temporary.unlink()


def write_text_once(path: Path, value: str) -> None:
    if lexists(path):
        raise FileExistsError(f"Refusing to overwrite append-only verification summary: {path}")
    with path.open("x", encoding="utf-8") as target:
        target.write(value)


def require_regular_path(path: Path, field: str) -> Path:
    if not lexists(path):
        raise FileNotFoundError(path)
    observed = os.lstat(path)
    if stat.S_ISLNK(observed.st_mode) or not stat.S_ISREG(observed.st_mode):
        raise ValueError(f"{field} must be a regular non-symlink file: {path}")
    return path


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


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


def expected_public_files(config: dict[str, Any]) -> set[str]:
    allowed = {
        "run.json", "stdout.log", "paired-oof-summary.json", "verification.json",
        "VERIFICATION-SUMMARY.md", "oof-complete.json", "initialization-failure.json",
        "assembly-failure.json", "frozen-sources/config.json", "frozen-sources/protocol.md",
        "frozen-sources/runner.py", "frozen-sources/verifier.py", "frozen-sources/tests.py",
        "frozen-sources/m1_runner_reference.py", "frozen-sources/qwen_primitives.py",
        "frozen-sources/m3_preflight_reference.py",
    }
    for fold_id in range(5):
        for family in ("m1", "m3"):
            prefix = f"fold-{fold_id}/{family}"
            allowed.update(
                {f"{prefix}/run.json", f"{prefix}/stdout.log", f"{prefix}/history.csv",
                 f"{prefix}/verification.json", f"{prefix}/VERIFICATION-SUMMARY.md",
                 f"{prefix}/failure.json"}
            )
    return allowed


def expected_public_json_schema(relative: str) -> str | None:
    exact = {
        "run.json": "exp-oof-production-run-v2",
        "paired-oof-summary.json": "exp-paired-oof-summary-v2",
        "verification.json": "exp-oof-final-verification-v2",
        "oof-complete.json": "exp-oof-completion-v2",
        "initialization-failure.json": "exp-oof-initialization-failure-v2",
        "assembly-failure.json": "exp-oof-assembly-failure-v2",
        "frozen-sources/config.json": CONFIG_V2_SCHEMA,
    }
    if relative in exact:
        return exact[relative]
    if re.fullmatch(r"fold-[0-4]/(?:m1|m3)/run\.json", relative):
        return "exp-oof-fold-run-v2"
    if re.fullmatch(r"fold-[0-4]/(?:m1|m3)/verification\.json", relative):
        return "exp-oof-fold-verification-v2"
    if re.fullmatch(r"fold-[0-4]/(?:m1|m3)/failure\.json", relative):
        return "exp-oof-fold-failure-v2"
    return None


def public_artifact_violations(config: dict[str, Any]) -> list[str]:
    if not is_v2(config):
        return []
    root = public_run_dir(config)
    if not root.is_dir():
        return []
    allowed = expected_public_files(config)
    allowed_directories = {
        str(parent)
        for relative in allowed
        for parent in Path(relative).parents
        if str(parent) != "."
    }
    violations: list[str] = []
    for path in sorted(root.rglob("*")):
        relative = str(path.relative_to(root))
        if stat.S_ISLNK(os.lstat(path).st_mode):
            violations.append(f"symlink:{relative}")
            continue
        if path.is_dir():
            if relative not in allowed_directories:
                violations.append(f"unexpected-directory:{relative}")
            continue
        if relative not in allowed:
            violations.append(f"unexpected:{relative}")
            continue
        if path.suffix == ".json":
            expected_schema = expected_public_json_schema(relative)
            if expected_schema is None:
                violations.append(f"unregistered-json:{relative}")
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                violations.append(f"invalid-json:{relative}")
                continue
            if value.get("schema_version") != expected_schema:
                violations.append(f"schema:{relative}")
            if public_sensitive_paths(value):
                violations.append(f"sensitive:{relative}")
    return violations


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def numpy_tensor_digest(items: dict[str, Any]) -> str:
    import numpy as np

    digest = hashlib.sha256()
    for name, tensor in sorted(items.items()):
        array = np.asarray(tensor, dtype=np.float32)
        digest.update(name.encode())
        digest.update(str(tuple(array.shape)).encode())
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


class Checks:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, name: str, passed: bool, detail: Any = None) -> None:
        self.rows.append({"name": name, "passed": bool(passed), "detail": detail})

    @property
    def failed(self) -> list[dict[str, Any]]:
        return [row for row in self.rows if not row["passed"]]


def verify_legacy_frozen_sources(config_path: Path, config: dict[str, Any]) -> None:
    if config.get("outputs") != {
        "public_run_dir": display_path(LEGACY_PUBLIC_RUN),
        "private_run_dir": display_path(LEGACY_PRIVATE_RUN),
    }:
        raise PermissionError("Legacy fallback is restricted to the sealed EXP-058 namespace")
    run_path = LEGACY_PUBLIC_RUN / "run.json"
    verification_path = LEGACY_PUBLIC_RUN / "verification.json"
    if not run_path.is_file() or not verification_path.is_file():
        raise PermissionError("Legacy source fallback requires an existing sealed run")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if (
        run.get("experiment_id") != LEGACY_EXPERIMENT_ID
        or run.get("stage") != LEGACY_STAGE
        or verification.get("status") != "Passed"
        or verification.get("failed_count") != 0
    ):
        raise PermissionError("Legacy source fallback requires the verified sealed EXP-058 run")
    frozen = run.get("frozen_sources")
    if not isinstance(frozen, dict) or set(frozen) != {"config", *config["implementation"]}:
        raise ValueError("Legacy frozen-source inventory drift")
    frozen_config = require_record(frozen["config"])
    if frozen_config.parent.resolve() != (LEGACY_PUBLIC_RUN / "frozen-sources").resolve() or sha256(config_path) != sha256(frozen_config):
        raise ValueError("Legacy frozen config does not match the archived run")
    for name, expected in config["implementation"].items():
        observed = require_record(frozen[name])
        if observed.parent.resolve() != (LEGACY_PUBLIC_RUN / "frozen-sources").resolve():
            raise ValueError(f"Legacy frozen source escaped its archive: {name}")
        if int(frozen[name]["bytes"]) != int(expected["bytes"]) or frozen[name]["sha256"] != expected["sha256"]:
            raise ValueError(f"Legacy frozen source disagrees with config: {name}")


def validate_v2_identity(config: dict[str, Any]) -> None:
    identities = {
        "EXP-061": (43, "exp-061-seed-43-router-replication"),
        "EXP-062": (44, "exp-062-seed-44-router-replication"),
    }
    identity = identities.get(str(config.get("experiment_id")))
    if identity is None:
        raise ValueError("Config-v2 is restricted to registered EXP-061/EXP-062 replications")
    if set(config) != V2_CONFIG_KEYS:
        raise ValueError("Config-v2 exact top-level schema drift")
    expected_seed, expected_run_id = identity
    if (
        config.get("rq_id") != "RQ-S3"
        or config.get("tier") != "Major"
        or config.get("stage") != LEGACY_STAGE
        or config.get("run_id") != expected_run_id
        or model_seed(config) != expected_seed
    ):
        raise ValueError("Experiment, run_id, and model_seed identity drift")
    if not ATTEMPT_RE.fullmatch(str(config.get("attempt_id", ""))):
        raise ValueError("attempt_id must match attempt-[1-9][0-9]*")
    expected_contract = {
        "model_seed": expected_seed,
        "python_seed": expected_seed,
        "numpy_seed": expected_seed,
        "torch_seed": expected_seed,
        "m1_batch_seed": expected_seed,
        "m3_head_seed": expected_seed,
        "m3_batch_seed": expected_seed,
        "m3_lora_seed": expected_seed + 100000,
    }
    if config.get("seed_contract") != expected_contract:
        raise ValueError("Exact RNG seed contract drift")
    authorization = config.get("authorization", {})
    if set(authorization) != V2_AUTHORIZATION_KEYS:
        raise PermissionError("Config-v2 authorization exact schema drift")
    if authorization.get("model_seed") != expected_seed:
        raise PermissionError("Authorization model_seed drift")
    if not isinstance(authorization.get("authorized_at"), str) or not authorization["authorized_at"]:
        raise PermissionError("Formal authorization timestamp is required")
    if not isinstance(authorization.get("basis"), str) or not authorization["basis"]:
        raise PermissionError("Formal authorization basis is required")
    if set(config.get("implementation", {})) != V2_IMPLEMENTATION_KEYS:
        raise ValueError("Config-v2 implementation source inventory drift")
    expected_implementation_paths = {
        "protocol": V2_PROTOCOL_PATHS[config["experiment_id"]],
        **V2_IMPLEMENTATION_PATHS,
    }
    for name, expected_path in expected_implementation_paths.items():
        record = config["implementation"][name]
        if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
            raise ValueError(f"Config-v2 implementation.{name} artifact schema drift")
        if record.get("path") != expected_path:
            raise ValueError(f"Config-v2 implementation.{name} canonical path drift")
        require_digest(record.get("sha256"), f"implementation.{name}.sha256")
    if set(config.get("prerequisites", {})) != V2_PREREQUISITE_KEYS:
        raise ValueError("Config-v2 prerequisite inventory drift")
    if set(config.get("data", {})) != V2_DATA_KEYS:
        raise ValueError("Config-v2 data contract inventory drift")
    if config.get("execution") != {"model_seed": expected_seed, **V2_EXECUTION}:
        raise ValueError("Config-v2 exact execution contract drift")
    if config.get("m1") != V2_M1 or config.get("m3") != V2_M3:
        raise ValueError("Config-v2 M1/M3 scientific contract drift")
    if config.get("resources") != V2_RESOURCES:
        raise ValueError("Config-v2 resource contract drift")
    cross_record = config["prerequisites"].get("cross_seed_initialization_verification")
    if (
        not isinstance(cross_record, dict)
        or authorization.get("cross_seed_initialization_verification_sha256")
        != cross_record.get("sha256")
    ):
        raise PermissionError("Authorization must bind the cross-seed initialization gate")
    relative_base = display_path(SCRIPT_DIR)
    expected_outputs = {
        "public_namespace": f"{relative_base}/runs/{expected_run_id}",
        "public_attempt_dir": f"{relative_base}/runs/{expected_run_id}/{config['attempt_id']}",
        "private_namespace": f"{relative_base}/private/{expected_run_id}",
        "private_attempt_dir": f"{relative_base}/private/{expected_run_id}/{config['attempt_id']}",
        "selection_record": f"{relative_base}/runs/{expected_run_id}/selected-attempt.json",
    }
    if config.get("outputs") != expected_outputs:
        raise ValueError("Config-v2 output paths are not the canonical derived paths")
    for value in expected_outputs.values():
        resolve_output(value)
    initialization = config.get("initialization")
    if not isinstance(initialization, dict) or set(initialization) != {
        "base_asset_manifest_sha256",
        "expected_by_fold",
    }:
        raise ValueError("Config-v2 initialization contract schema drift")
    require_digest(initialization["base_asset_manifest_sha256"], "initialization.base_asset_manifest_sha256")
    if not isinstance(initialization.get("expected_by_fold"), dict) or set(initialization["expected_by_fold"]) != {str(i) for i in range(5)}:
        raise ValueError("Config-v2 must freeze initialization hashes for all five folds")
    for fold_id in range(5):
        expected_initialization(config, fold_id)


def verify_v2_frozen_data_identity(config: dict[str, Any]) -> None:
    train = config["data"]["train"]
    fold_manifest = config["prerequisites"]["fold_manifest"]
    shared_config = config["prerequisites"]["shared_config"]
    if (
        config["data"].get("protocol_id") != "DATA-SO-TASK-V1"
        or config["data"].get("label_order") != list(LABELS)
        or train.get("path") != FROZEN_TRAIN_PATH
        or train.get("sha256") != FROZEN_TRAIN_SHA256
        or fold_manifest.get("path") != FROZEN_FOLD_MANIFEST_PATH
        or fold_manifest.get("sha256") != FROZEN_FOLD_MANIFEST_SHA256
        or shared_config.get("path") != FROZEN_SHARED_CONFIG_PATH
        or shared_config.get("bytes") != FROZEN_SHARED_CONFIG_BYTES
        or shared_config.get("sha256") != FROZEN_SHARED_CONFIG_SHA256
    ):
        raise PermissionError("Config-v2 must use the frozen EXP-058 train/fold/shared identity")
    for fold_id in range(5):
        expected = expected_initialization(config, fold_id)
        if (
            expected["base_asset_manifest_sha256"]
            != config["initialization"]["base_asset_manifest_sha256"]
            or expected["fold_manifest_sha256"] != fold_manifest["sha256"]
        ):
            raise ValueError(f"Fold {fold_id} initialization source identity drift")


def verify_v2_prerequisites(config: dict[str, Any]) -> None:
    manifest_path = require_record(config["prerequisites"]["fold_manifest"])
    fold_verification = json.loads(
        require_record(config["prerequisites"]["fold_verification"]).read_text(encoding="utf-8")
    )
    contract = json.loads(
        require_record(config["prerequisites"]["consumer_contract"]).read_text(encoding="utf-8")
    )
    if (
        fold_verification.get("status") != "Passed"
        or fold_verification.get("failed_count") != 0
        or contract.get("fold_manifest_sha256") != sha256(manifest_path)
        or contract.get("forbidden_splits") != ["validation", "test"]
    ):
        raise RuntimeError("Fold manifest prerequisite drift")
    initialization_record = config["prerequisites"]["initialization_manifest"]
    initialization = json.loads(require_record(initialization_record).read_text(encoding="utf-8"))
    verification = json.loads(
        require_record(config["prerequisites"]["initialization_verification"]).read_text(encoding="utf-8")
    )
    initialization_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "model_seed",
        "seed_contract", "base_asset_manifest_sha256", "fold_manifest_sha256",
        "shared_scientific_contract_sha256", "cross_seed_gate", "folds",
    }
    if (
        set(initialization) != initialization_keys
        or initialization.get("schema_version") != "exp-oof-initialization-manifest-v1"
        or initialization.get("experiment_id") != experiment_id(config)
        or initialization.get("run_id") != run_id(config)
        or initialization.get("attempt_id") != attempt_id(config)
        or initialization.get("model_seed") != model_seed(config)
        or initialization.get("seed_contract") != seed_contract(config)
        or initialization.get("shared_scientific_contract_sha256")
        != shared_scientific_contract_sha256(config)
        or initialization.get("cross_seed_gate") != {
            "required_before_formal_training": True,
            "status": "Pending",
            "verification_schema": "exp-oof-cross-seed-initialization-verification-v1",
        }
        or initialization.get("base_asset_manifest_sha256")
        != config["initialization"]["base_asset_manifest_sha256"]
        or initialization.get("fold_manifest_sha256") != sha256(manifest_path)
    ):
        raise ValueError("Initialization manifest identity drift")
    folds = initialization.get("folds")
    if not isinstance(folds, dict) or set(folds) != {str(i) for i in range(5)}:
        raise ValueError("Initialization manifest fold coverage drift")
    for fold_id in range(5):
        expected = expected_initialization(config, fold_id)
        observed = folds[str(fold_id)]
        if any(observed.get(key) != value for key, value in expected.items()):
            raise ValueError(f"Initialization manifest fold {fold_id} drift")
        if observed.get("m3_lora_b_zero_initialized") is not True:
            raise ValueError("LoRA-B equality is allowed only with verified zero initialization")
    verified_manifest = verification.get("verified_artifacts", {}).get("initialization_manifest")
    if (
        verification.get("status") != "Passed"
        or verification.get("failed_count") != 0
        or verification.get("experiment_id") != experiment_id(config)
        or verification.get("run_id") != run_id(config)
        or verification.get("attempt_id") != attempt_id(config)
        or verified_manifest != initialization_record
    ):
        raise RuntimeError("Initialization manifest is not independently verified")
    cross_record = config["prerequisites"]["cross_seed_initialization_verification"]
    cross_seed = json.loads(require_record(cross_record).read_text(encoding="utf-8"))
    member = cross_seed.get("members", {}).get(experiment_id(config), {})
    if (
        cross_seed.get("schema_version") != "exp-oof-cross-seed-initialization-verification-v1"
        or cross_seed.get("status") != "Passed"
        or cross_seed.get("failed_count") != 0
        or cross_seed.get("shared_scientific_contract_sha256")
        != shared_scientific_contract_sha256(config)
        or cross_seed.get("base_asset_manifest_sha256")
        != initialization.get("base_asset_manifest_sha256")
        or cross_seed.get("fold_manifest_sha256")
        != initialization.get("fold_manifest_sha256")
        or member.get("model_seed") != model_seed(config)
        or member.get("formal_run_id") != run_id(config)
        or member.get("formal_attempt_id") != attempt_id(config)
        or member.get("initialization_manifest") != initialization_record
        or member.get("initialization_verification")
        != config["prerequisites"]["initialization_verification"]
        or config["authorization"]["cross_seed_initialization_verification_sha256"]
        != cross_record["sha256"]
    ):
        raise RuntimeError("Cross-seed initialization gate is not bound to this formal attempt")
    shared = json.loads(require_record(config["prerequisites"]["shared_config"]).read_text(encoding="utf-8"))
    if shared["data"]["test_status"] != "sealed_not_authorized_for_model_access":
        raise PermissionError("Shared test contract drift")
    if base_asset_manifest_sha256(shared) != config["initialization"]["base_asset_manifest_sha256"]:
        raise ValueError("Base asset manifest identity drift")


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    schema = config.get("schema_version")
    if schema not in (LEGACY_CONFIG_SCHEMA, CONFIG_V2_SCHEMA):
        raise ValueError("Unexpected OOF production config schema")
    if schema == LEGACY_CONFIG_SCHEMA and (
        config.get("experiment_id") != LEGACY_EXPERIMENT_ID or config.get("stage") != LEGACY_STAGE
    ):
        raise ValueError("Unexpected sealed EXP-058 production config")
    if schema == CONFIG_V2_SCHEMA:
        validate_v2_identity(config)
    if config.get("tier") != "Major":
        raise ValueError("Full OOF production must remain Major")
    authorization = config["authorization"]
    if authorization.get("fold_ids") != [0, 1, 2, 3, 4] or authorization.get("model_seed") != model_seed(config):
        raise PermissionError("Authorization fold/seed drift")
    for key in ("assembly", "full_oof_training", "heldout_forward", "model_loading"):
        if authorization.get(key) is not True:
            raise PermissionError(f"Missing authorization: {key}")
    for key in ("calibration", "metrics", "oracle_analysis", "router_training", "test_access", "validation_access"):
        if authorization.get(key) is not False:
            raise PermissionError(f"Authorization exceeds OOF scope: {key}")
    execution = config["execution"]
    if (
        execution.get("fold_ids") != [0, 1, 2, 3, 4]
        or int(execution.get("model_seed", model_seed(config))) != model_seed(config)
        or execution.get("m1_epochs") != 4
        or execution.get("m3_epochs") != 2
    ):
        raise ValueError("Execution contract drift")
    implementation_drift = False
    for record in config["implementation"].values():
        try:
            require_record(record)
        except (FileNotFoundError, ValueError):
            implementation_drift = True
    if implementation_drift:
        if schema != LEGACY_CONFIG_SCHEMA:
            raise ValueError("Config-v2 implementation source drift")
        verify_legacy_frozen_sources(path, config)
        config["_legacy_frozen_source_fallback"] = True
    elif schema == LEGACY_CONFIG_SCHEMA:
        verify_legacy_frozen_sources(path, config)
    if schema == CONFIG_V2_SCHEMA:
        live_verifier = require_record(config["implementation"]["verifier"])
        if live_verifier != LIVE_VERIFIER_PATH.resolve():
            raise ValueError("Config-v2 verifier record is not bound to the live verifier artifact")
    for record in config["prerequisites"].values():
        require_record(record)
    require_record(config["data"]["train"])
    if schema == CONFIG_V2_SCHEMA:
        verify_v2_frozen_data_identity(config)
        verify_v2_prerequisites(config)
    config["_config_path"] = str(path.resolve())
    config["_config_sha256"] = sha256(path)
    return config


def expected_cli_identity(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "model_seed": model_seed(config),
        "run_id": run_id(config),
        "output_root": config["outputs"]["public_attempt_dir"],
        "expected_fold_manifest_sha256": config["prerequisites"]["fold_manifest"]["sha256"],
        "expected_data_manifest_sha256": config["data"]["train"]["sha256"],
    }


def bind_cli_identity(
    config: dict[str, Any],
    *,
    cli_model_seed: int | None,
    cli_run_id: str | None,
    cli_output_root: Path | None,
    cli_fold_manifest_sha256: str | None,
    cli_data_manifest_sha256: str | None,
) -> None:
    if not is_v2(config):
        return
    supplied = {
        "model_seed": cli_model_seed,
        "run_id": cli_run_id,
        "output_root": None,
        "expected_fold_manifest_sha256": cli_fold_manifest_sha256,
        "expected_data_manifest_sha256": cli_data_manifest_sha256,
    }
    if cli_output_root is not None:
        supplied["output_root"] = display_path(resolve_output(str(cli_output_root)))
    missing = [key for key, value in supplied.items() if value is None]
    if missing:
        raise PermissionError(f"Config-v2 requires explicit CLI identity flags: {sorted(missing)}")
    expected = expected_cli_identity(config)
    if supplied != expected:
        raise ValueError(f"CLI identity must exactly match config-v2: expected {expected}, got {supplied}")
    config["_cli_identity"] = expected


def valid_m3_lock_metadata(value: Any, config: dict[str, Any], fold_id: int) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"schema_version", "path", "mode", "owner", "acquired_at_utc"}
        and value.get("schema_version") == "exp-heavy-workload-lock-owner-v1"
        and value.get("path") == HEAVY_WORKLOAD_LOCK_PATH
        and value.get("mode") == "nonblocking-advisory-exclusive"
        and isinstance(value.get("acquired_at_utc"), str)
        and bool(value["acquired_at_utc"])
        and isinstance(value.get("owner"), dict)
        and value.get("owner") == {
            "experiment_id": experiment_id(config),
            "run_id": run_id(config),
            "attempt_id": attempt_id(config),
            "model_seed": model_seed(config),
            "scope": "m3",
            "fold_id": fold_id,
            "pid": value.get("owner", {}).get("pid"),
        }
        and isinstance(value.get("owner", {}).get("pid"), int)
        and value["owner"]["pid"] > 0
    )


def verification_identity(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    if not is_v2(config):
        return {}
    if config.get("_cli_identity") != expected_cli_identity(config):
        raise PermissionError("Config-v2 CLI identity was not bound before verification")
    return {
        "run_id": run_id(config),
        "attempt_id": attempt_id(config),
        "model_seed": model_seed(config),
        "seed_contract": seed_contract(config),
        "config": artifact(config_path),
        "cli_identity": config["_cli_identity"],
    }


def source_state(config: dict[str, Any]) -> dict[str, Any]:
    train_path = require_record(config["data"]["train"])
    manifest_path = require_record(config["prerequisites"]["fold_manifest"])
    train_rows = read_jsonl(train_path)
    manifest_rows = read_jsonl(manifest_path)
    if len(train_rows) != 3360 or len(manifest_rows) != 3360:
        raise ValueError("Source row-count drift")
    train_by_id = {row["sample_id"]: row for row in train_rows}
    assignments = {row["sample_id"]: row for row in manifest_rows}
    if len(train_by_id) != 3360 or len(assignments) != 3360 or set(train_by_id) != set(assignments):
        raise ValueError("Source identity coverage drift")
    for sample_id, row in train_by_id.items():
        if assignments[sample_id]["component_id"] != row["component_id"]:
            raise ValueError("Source component identity drift")
    partitions = {}
    for fold_id in range(5):
        heldout = [row for row in train_rows if assignments[row["sample_id"]]["fold_id"] == fold_id]
        training = [row for row in train_rows if assignments[row["sample_id"]]["fold_id"] != fold_id]
        partitions[fold_id] = {"training": training, "heldout": heldout}
    return {
        "train_path": train_path,
        "manifest_path": manifest_path,
        "train_rows": train_rows,
        "train_by_id": train_by_id,
        "assignments": assignments,
        "partitions": partitions,
    }


def public_run_dir(config: dict[str, Any]) -> Path:
    key = "public_attempt_dir" if is_v2(config) else "public_run_dir"
    resolver = resolve_output if is_v2(config) else resolve_project
    return resolver(config["outputs"][key])


def private_run_dir(config: dict[str, Any]) -> Path:
    key = "private_attempt_dir" if is_v2(config) else "private_run_dir"
    resolver = resolve_output if is_v2(config) else resolve_project
    return resolver(config["outputs"][key])


def public_namespace(config: dict[str, Any]) -> Path:
    return resolve_output(config["outputs"]["public_namespace"]) if is_v2(config) else public_run_dir(config)


def selection_record_path(config: dict[str, Any]) -> Path:
    if not is_v2(config):
        raise PermissionError("Legacy EXP-058 has no attempt selection record")
    return resolve_output(config["outputs"]["selection_record"])


def identity_matches(value: dict[str, Any], config: dict[str, Any]) -> bool:
    return (
        value.get("experiment_id") == experiment_id(config)
        and value.get("stage") == stage_name(config)
        and (
            not is_v2(config)
            or (
                value.get("run_id") == run_id(config)
                and value.get("attempt_id") == attempt_id(config)
                and value.get("model_seed") == model_seed(config)
                and value.get("seed_contract") == seed_contract(config)
                and value.get("config") == artifact(Path(config["_config_path"]))
                and value.get("cli_identity") == config.get("_cli_identity") == expected_cli_identity(config)
            )
        )
    )


def fold_dirs(config: dict[str, Any], family: str, fold_id: int) -> tuple[Path, Path]:
    return (
        public_run_dir(config) / f"fold-{fold_id}" / family,
        private_run_dir(config) / f"fold-{fold_id}" / family,
    )


def verify_private_modes(checks: Checks, private_fold: Path, namespace: str) -> None:
    checks.add(f"{namespace}.private_dir_mode", mode(private_fold) == 0o700, oct(mode(private_fold)))
    for child in sorted(private_fold.rglob("*")):
        expected = 0o700 if child.is_dir() else 0o600
        checks.add(
            f"{namespace}.private_mode.{child.relative_to(private_fold)}",
            mode(child) == expected,
            oct(mode(child)),
        )


def verify_fold(config_path: Path, config: dict[str, Any], family: str, fold_id: int) -> dict[str, Any]:
    import numpy as np
    from safetensors.numpy import load_file

    if family not in ("m1", "m3") or fold_id not in range(5):
        raise ValueError("Invalid fold verification target")
    public_fold, private_fold = fold_dirs(config, family, fold_id)
    output_path = public_fold / "verification.json"
    summary_path = public_fold / "VERIFICATION-SUMMARY.md"
    if lexists(output_path) or lexists(summary_path):
        raise FileExistsError("Refusing to overwrite or resume a sealed fold verification")
    run_path = public_fold / "run.json"
    require_regular_path(run_path, "Fold run")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    sources = source_state(config)
    training = sources["partitions"][fold_id]["training"]
    heldout = sources["partitions"][fold_id]["heldout"]
    checks = Checks()
    prefix = f"{family}.fold_{fold_id}"
    expected_init = expected_initialization(config, fold_id)
    public_violations = public_artifact_violations(config)
    checks.add(f"{prefix}.public_allowlist", not public_violations, public_violations)

    checks.add(f"{prefix}.run_status", run.get("status") == "CompletedAwaitingVerification")
    checks.add(
        f"{prefix}.identity",
        identity_matches(run, config) and run.get("family") == family and run.get("fold_id") == fold_id,
    )
    checks.add(f"{prefix}.seed", run.get("model_seed") == model_seed(config))
    checks.add(f"{prefix}.training_rows", run.get("data", {}).get("training_rows") == 2688)
    checks.add(f"{prefix}.heldout_rows", run.get("data", {}).get("heldout_rows") == 672)
    checks.add(
        f"{prefix}.training_order",
        run.get("data", {}).get("training_order_sha256")
        == canonical_digest([row["sample_id"] for row in training]),
    )
    checks.add(
        f"{prefix}.heldout_order",
        run.get("data", {}).get("heldout_order_sha256")
        == canonical_digest([row["sample_id"] for row in heldout]),
    )
    checks.add(
        f"{prefix}.manifest",
        run.get("data", {}).get("fold_manifest_sha256") == sha256(sources["manifest_path"]),
    )
    checks.add(f"{prefix}.sample_overlap", run.get("data", {}).get("sample_overlap") == 0)
    checks.add(f"{prefix}.component_overlap", run.get("data", {}).get("component_overlap") == 0)
    split = run.get("split_access", {})
    checks.add(f"{prefix}.train_only", split.get("accessed_splits") == ["train"])
    checks.add(f"{prefix}.no_validation", split.get("validation_accessed") is False)
    checks.add(f"{prefix}.no_test_inputs", split.get("test_inputs_accessed") is False)
    checks.add(f"{prefix}.no_test_labels", split.get("test_labels_accessed") is False)
    checks.add(f"{prefix}.no_metrics", run.get("performance_metrics_computed") is False)
    checks.add(f"{prefix}.public_privacy", not public_sensitive_paths(run), public_sensitive_paths(run))

    history_path = require_record_within(
        run["artifacts"]["history"], public_fold, exact_relative="history.csv"
    )
    history = list(csv.DictReader(history_path.open(encoding="utf-8")))
    expected_epochs = 4 if family == "m1" else 2
    expected_steps = 672 if family == "m1" else 5376
    checks.add(f"{prefix}.history_epochs", len(history) == expected_epochs, len(history))
    checks.add(
        f"{prefix}.optimizer_steps",
        run.get("training", {}).get("optimizer_steps") == expected_steps,
        run.get("training", {}).get("optimizer_steps"),
    )
    checks.add(
        f"{prefix}.history_final_steps",
        bool(history) and int(history[-1]["optimizer_steps"]) == expected_steps,
    )
    checks.add(
        f"{prefix}.finite_train_losses",
        len(history) == expected_epochs
        and all(math.isfinite(float(row["train_loss"])) for row in history),
    )

    evidence_path = require_record_within(
        run["artifacts"]["evidence_private"], private_fold, exact_relative="evidence.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if is_v2(config):
        checks.add(f"{prefix}.evidence_identity", identity_matches(evidence, config))
        checks.add(
            f"{prefix}.base_asset_provenance",
            run.get("model", {}).get("base_asset_manifest_sha256")
            == evidence.get("base_asset_manifest_sha256")
            == expected_init["base_asset_manifest_sha256"]
            == config["initialization"]["base_asset_manifest_sha256"],
        )
    batch_orders_path = require_record_within(
        run["artifacts"]["batch_orders_private"], private_fold, exact_relative="batch-orders.npy"
    )
    batch_orders = np.load(batch_orders_path, allow_pickle=False)
    checks.add(
        f"{prefix}.batch_order_shape",
        batch_orders.shape == (expected_epochs, 2688),
        list(batch_orders.shape),
    )
    if is_v2(config) and family == "m3":
        independent_rng = np.random.default_rng(seed_contract(config)["m3_batch_seed"])
        independent_orders = np.stack(
            [independent_rng.permutation(2688) for _ in range(expected_epochs)]
        ).astype(np.int32)
        checks.add(
            f"{prefix}.seeded_pcg64_batch_orders",
            np.array_equal(batch_orders, independent_orders),
        )
    expected_indices = np.arange(2688, dtype=np.int32)
    for epoch in range(expected_epochs):
        permutation_ok = np.array_equal(np.sort(batch_orders[epoch]), expected_indices)
        checks.add(f"{prefix}.epoch_{epoch + 1}_permutation", permutation_ok)
        if permutation_ok:
            digest = canonical_digest(
                [training[int(index)]["sample_id"] for index in batch_orders[epoch]]
            )
            checks.add(
                f"{prefix}.epoch_{epoch + 1}_order_digest",
                digest == history[epoch]["batch_order_sha256"]
                and digest == evidence["batch_order_sha256"][epoch],
            )
    batch_order_digest = canonical_digest([row["batch_order_sha256"] for row in history])
    if is_v2(config):
        checks.add(
            f"{prefix}.batch_order_combined",
            batch_order_digest == expected_init[f"{family}_batch_order_sha256"]
            == evidence.get("batch_order_combined_sha256")
            == run.get("model", {}).get("batch_order_sha256"),
        )
    checks.add(f"{prefix}.labels_not_used_for_forward", evidence.get("heldout_labels_used_for_forward") is False)
    checks.add(
        f"{prefix}.manifest_unchanged",
        evidence.get("manifest_sha256_before") == evidence.get("manifest_sha256_after")
        == sha256(sources["manifest_path"]),
    )

    predictions_path = require_record_within(
        run["artifacts"]["heldout_logit_table_private"],
        private_fold,
        exact_relative="heldout-logits.npz",
    )
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
        checks.add(f"{prefix}.private_table_schema", set(table.files) == required, sorted(table.files))
        sample_ids = table["sample_ids"].tolist()
        component_ids = table["component_ids"].tolist()
        fold_ids = np.asarray(table["fold_ids"])
        gold = np.asarray(table["gold"], dtype=np.uint8)
        logits = np.asarray(table["logits"], dtype=np.float32)
        character_lengths = np.asarray(table["character_lengths"], dtype=np.int32)
        token_lengths = np.asarray(table["token_lengths"], dtype=np.int32)
    expected_sample_ids = [row["sample_id"] for row in heldout]
    checks.add(f"{prefix}.heldout_identity", sample_ids == expected_sample_ids)
    checks.add(
        f"{prefix}.heldout_components",
        component_ids == [row["component_id"] for row in heldout],
    )
    checks.add(f"{prefix}.fold_ids", fold_ids.shape == (672,) and np.all(fold_ids == fold_id))
    checks.add(
        f"{prefix}.gold",
        gold.shape == (672, 6)
        and np.array_equal(gold, np.asarray([row["labels"] for row in heldout], dtype=np.uint8)),
    )
    checks.add(
        f"{prefix}.logits",
        logits.shape == (672, 6) and np.isfinite(logits).all(),
        list(logits.shape),
    )
    checks.add(
        f"{prefix}.character_lengths",
        np.array_equal(character_lengths, np.asarray([len(row["text"]) for row in heldout], dtype=np.int32)),
    )
    maximum_length = 256 if family == "m1" else 384
    checks.add(
        f"{prefix}.token_lengths",
        token_lengths.shape == (672,) and np.all(token_lengths > 0) and np.all(token_lengths <= maximum_length),
    )
    checks.add(
        f"{prefix}.heldout_not_training",
        not (set(sample_ids) & {row["sample_id"] for row in training}),
    )

    if family == "m1":
        schedule = run.get("training", {}).get("scheduler", {})
        checks.add(
            f"{prefix}.scheduler",
            schedule
            == {
                "steps_per_epoch": 168,
                "planned_scheduler_epochs": 5,
                "scheduler_horizon_steps": 840,
                "warmup_steps": 84,
                "selected_stop_epoch": 4,
                "selected_stop_steps": 672,
            },
        )
        checkpoint_record = run["artifacts"]["final_checkpoint_private"]
        checkpoint_dir = resolve_project(checkpoint_record["path"])
        checks.add(
            f"{prefix}.checkpoint_current_attempt",
            checkpoint_dir == (private_fold / "final-model").resolve(),
            display_path(checkpoint_dir),
        )
        observed_tree = tree_artifact(checkpoint_dir)
        checks.add(f"{prefix}.checkpoint_tree", observed_tree == checkpoint_record)
        model_path = checkpoint_dir / "model.safetensors"
        checks.add(f"{prefix}.checkpoint_model", model_path.is_file())
        if model_path.is_file():
            tensors = load_file(model_path)
            classifier = {name: value for name, value in tensors.items() if name.startswith("classifier.")}
            classifier_digest = numpy_tensor_digest(classifier)
            checks.add(
                f"{prefix}.classifier_final_digest",
                classifier_digest == run["model"]["classifier_final_sha256"]
                == evidence["classifier_final_sha256"],
            )
        checks.add(
            f"{prefix}.classifier_changed",
            run["model"]["classifier_initial_sha256"]
            == expected_init["m1_classifier_init_sha256"]
            and run["model"]["classifier_final_sha256"]
            != run["model"]["classifier_initial_sha256"],
        )
        if is_v2(config):
            observed_init = {
                "m1_classifier_init_sha256": run["model"]["classifier_initial_sha256"],
                "m1_rng_state_digest": run["model"].get("rng_state_digest"),
            }
            checks.add(
                f"{prefix}.initialization_state",
                evidence.get("classifier_initial_sha256")
                == observed_init["m1_classifier_init_sha256"]
                == expected_init["m1_classifier_init_sha256"]
                and evidence.get("rng_state_digest")
                == observed_init["m1_rng_state_digest"]
                == m1_rng_state_digest(config)
                == expected_init["m1_rng_state_digest"]
                and initialization_state_sha256("m1", observed_init)
                == expected_init["m1_initialization_state_sha256"]
                == run["model"].get("initialization_state_sha256")
                == evidence.get("initialization_state_sha256"),
            )
        checks.add(
            f"{prefix}.memory",
            float(run["resources"]["peak_process_rss_gb"])
            <= float(config["resources"]["m1_peak_process_memory_gb"]),
        )
    else:
        if is_v2(config):
            lock_metadata = run.get("execution_lock")
            lock_path = resolve_output(HEAVY_WORKLOAD_LOCK_PATH)
            try:
                require_regular_path(lock_path, "Shared heavy-workload mutex")
                lock_file_valid = mode(lock_path) == 0o600
            except (FileNotFoundError, ValueError):
                lock_file_valid = False
            checks.add(
                f"{prefix}.shared_workload_mutex",
                valid_m3_lock_metadata(lock_metadata, config, fold_id) and lock_file_valid,
            )
        adapter_path = require_record_within(
            run["artifacts"]["adapter_private"], private_fold, exact_relative="adapters.safetensors"
        )
        head_path = require_record_within(
            run["artifacts"]["head_private"], private_fold, exact_relative="head.safetensors"
        )
        adapter_digest = numpy_tensor_digest(load_file(adapter_path))
        head_digest = numpy_tensor_digest(load_file(head_path))
        checks.add(
            f"{prefix}.adapter_digest",
            adapter_digest == run["model"]["lora_final_sha256"] == evidence["lora_final_sha256"],
        )
        checks.add(
            f"{prefix}.head_digest",
            head_digest == run["model"]["head_final_sha256"] == evidence["head_final_sha256"],
        )
        checks.add(
            f"{prefix}.initialization",
            run["model"]["head_initial_sha256"] == expected_init["m3_classifier_head_init_sha256"]
            and run["model"]["lora_initial_sha256"] == expected_init["m3_lora_combined_init_sha256"]
            and run["model"]["zero_step_max_abs_logit_difference"] == 0.0,
        )
        if is_v2(config):
            observed_init = {
                "m3_lora_a_init_sha256": run["model"].get("lora_a_initial_sha256"),
                "m3_lora_b_init_sha256": run["model"].get("lora_b_initial_sha256"),
                "m3_lora_combined_init_sha256": run["model"].get("lora_initial_sha256"),
                "m3_classifier_head_init_sha256": run["model"].get("head_initial_sha256"),
                "m3_base_sentinel_sha256": expected_init["m3_base_sentinel_sha256"],
                "m3_rng_state_digest": run["model"].get("rng_state_digest"),
            }
            checks.add(
                f"{prefix}.split_initialization",
                evidence.get("head_initial_sha256")
                == observed_init["m3_classifier_head_init_sha256"]
                == expected_init["m3_classifier_head_init_sha256"]
                and evidence.get("lora_initial_sha256")
                == observed_init["m3_lora_combined_init_sha256"]
                == expected_init["m3_lora_combined_init_sha256"]
                and evidence.get("lora_a_initial_sha256")
                == observed_init["m3_lora_a_init_sha256"]
                == expected_init["m3_lora_a_init_sha256"]
                and evidence.get("lora_b_initial_sha256")
                == observed_init["m3_lora_b_init_sha256"]
                == expected_init["m3_lora_b_init_sha256"]
                and run["model"].get("lora_b_zero_initialized") is True
                and evidence.get("lora_b_zero_initialized") is True
                and evidence.get("rng_state_digest")
                == observed_init["m3_rng_state_digest"]
                == m3_rng_state_digest(config)
                == expected_init["m3_rng_state_digest"]
                and initialization_state_sha256("m3", observed_init)
                == expected_init["m3_initialization_state_sha256"]
                == run["model"].get("initialization_state_sha256")
                == evidence.get("initialization_state_sha256"),
            )
            checks.add(
                f"{prefix}.base_initialization",
                evidence.get("base_sentinel_before", {}).get("sha256")
                == expected_init["m3_base_sentinel_sha256"],
            )
        checks.add(
            f"{prefix}.lora_contract",
            run["model"]["insertion_count"] == 112
            and run["model"]["lora_parameter_count"] == 7_340_032
            and run["model"]["total_trainable_parameter_count"] == 7_355_398
            and run["model"]["nonzero_lora_b_tensors"] == 112
            and run["model"]["base_sentinel_unchanged"] is True
            and run["model"]["trainable_whitelist_passed"] is True,
        )
        checks.add(
            f"{prefix}.memory",
            float(run["resources"]["peak_mlx_memory_gb"])
            <= float(config["resources"]["m3_peak_mlx_memory_gb"]),
        )
        checks.add(
            f"{prefix}.fold_wall",
            float(run["resources"]["wall_seconds"])
            <= float(config["resources"]["m3_per_fold_wall_hours"]) * 3600,
        )
    if is_v2(config):
        provenance_path = require_record_within(
            run["artifacts"]["checkpoint_provenance_private"],
            private_fold,
            exact_relative="checkpoint-provenance.json",
        )
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        checks.add(f"{prefix}.checkpoint_provenance_identity", identity_matches(provenance, config))
        checks.add(f"{prefix}.checkpoint_provenance_family", provenance.get("family") == family and provenance.get("fold_id") == fold_id)
        checks.add(
            f"{prefix}.checkpoint_provenance_sources",
            provenance.get("base_asset_manifest_sha256")
            == config["initialization"]["base_asset_manifest_sha256"]
            == expected_init["base_asset_manifest_sha256"]
            and provenance.get("fold_manifest_sha256") == expected_init["fold_manifest_sha256"],
        )
        expected_provenance_init = {
            key: value
            for key, value in expected_init.items()
            if key.startswith(f"{family}_") and key not in {f"{family}_classifier_init_sha256"}
        }
        if family == "m1":
            expected_provenance_init["m1_classifier_init_sha256"] = expected_init["m1_classifier_init_sha256"]
        else:
            expected_provenance_init["m3_lora_b_zero_initialized"] = True
        checks.add(
            f"{prefix}.checkpoint_provenance_initialization",
            provenance.get("initialization") == expected_provenance_init,
        )
        if family == "m1":
            checks.add(
                f"{prefix}.checkpoint_provenance_artifact",
                provenance.get("checkpoint") == run["artifacts"]["final_checkpoint_private"],
            )
        else:
            checks.add(
                f"{prefix}.checkpoint_provenance_artifact",
                provenance.get("checkpoint")
                == {
                    "adapter": run["artifacts"]["adapter_private"],
                    "head": run["artifacts"]["head_private"],
                },
            )
    verify_private_modes(checks, private_fold, prefix)

    result = {
        "schema_version": "exp-oof-fold-verification-v2" if is_v2(config) else "exp-058-oof-fold-verification-v1",
        "experiment_id": experiment_id(config),
        "stage": stage_name(config),
        **verification_identity(config_path, config),
        "scope": "fold",
        "family": family,
        "fold_id": fold_id,
        "verified_at_utc": utc_now(),
        "status": "Passed" if not checks.failed else "Failed",
        "check_count": len(checks.rows),
        "passed_count": len(checks.rows) - len(checks.failed),
        "failed_count": len(checks.failed),
        "checks": checks.rows,
        "independence": {
            "runner_imported": False,
            "model_libraries_imported": False,
            "saved_private_table_recomputed": True,
            "saved_model_state_rehashed": True,
        },
        "verified_artifacts": {
            "config": artifact(config_path),
            "run": artifact(run_path),
            "private_table": artifact(predictions_path),
        },
        "claim_boundary": "Integrity of one train-only OOF fold; no performance claim.",
    }
    atomic_json(output_path, result)
    write_text_once(
        summary_path,
        "\n".join(
            [
                f"# EXP-058 {family.upper()} Fold {fold_id} Verification",
                "",
                f"- Status: `{result['status']}`",
                f"- Checks: `{result['passed_count']}/{result['check_count']}`",
                "- Accessed split: `train` only",
                "- Metrics/calibration/oracle/router: `not computed`",
                "",
                result["claim_boundary"],
                "",
            ]
        ),
    )
    post_write_violations = public_artifact_violations(config)
    if post_write_violations:
        raise RuntimeError(f"Public artifact allowlist failed after fold verification: {post_write_violations}")
    if checks.failed:
        raise RuntimeError(f"Fold verification failed: {len(checks.failed)} checks")
    return result


def verify_final(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    import numpy as np

    run_dir = public_run_dir(config)
    output_path = run_dir / "verification.json"
    summary_output = run_dir / "VERIFICATION-SUMMARY.md"
    if lexists(output_path) or lexists(summary_output):
        raise FileExistsError("Refusing to overwrite or resume a sealed final verification")
    run_path = run_dir / "run.json"
    require_regular_path(run_path, "Top-level OOF run")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    summary_path = run_dir / "paired-oof-summary.json"
    require_regular_path(summary_path, "Paired OOF summary")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    sources = source_state(config)
    checks = Checks()
    public_violations = public_artifact_violations(config)
    checks.add("final.public_allowlist", not public_violations, public_violations)
    checks.add("final.run_status", run.get("status") == "CompletedAwaitingVerification")
    checks.add("final.identity", identity_matches(run, config))
    checks.add("final.summary_identity", identity_matches(summary, config))
    if is_v2(config):
        checks.add("final.selection_absent", not lexists(selection_record_path(config)))
        checks.add(
            "final.summary_record",
            run.get("artifacts", {}).get("paired_oof_summary") == artifact(summary_path),
        )
    checks.add("final.summary_status", summary.get("status") == "CompletedAwaitingVerification")
    checks.add("final.rows", summary.get("rows") == 3360)
    checks.add("final.fold_counts", summary.get("rows_per_fold") == {str(i): 672 for i in range(5)})
    checks.add("final.no_metrics", summary.get("performance_metrics_computed") is False)
    checks.add("final.no_calibration", summary.get("calibration_performed") is False)
    checks.add("final.no_oracle", summary.get("oracle_analysis_performed") is False)
    checks.add("final.no_router", summary.get("router_training_performed") is False)
    checks.add("final.no_validation", summary.get("validation_accessed") is False)
    checks.add("final.no_test", summary.get("test_accessed") is False)
    split = run.get("split_access", {})
    checks.add("final.train_only", split.get("accessed_splits") == ["train"])
    checks.add("final.run_no_validation", split.get("validation_accessed") is False)
    checks.add("final.run_no_test_inputs", split.get("test_inputs_accessed") is False)
    checks.add("final.run_no_test_labels", split.get("test_labels_accessed") is False)

    fold_tables: dict[str, dict[str, Any]] = {"m1": {}, "m3": {}}
    fold_run_hashes: dict[str, dict[int, str]] = {"m1": {}, "m3": {}}
    fold_run_records: dict[str, dict[str, Any]] = {"m1": {}, "m3": {}}
    fold_verification_records: dict[str, dict[str, Any]] = {"m1": {}, "m3": {}}
    family_wall = {"m1": 0.0, "m3": 0.0}
    for family in ("m1", "m3"):
        for fold_id in range(5):
            public_fold, _ = fold_dirs(config, family, fold_id)
            verification_path = public_fold / "verification.json"
            require_regular_path(verification_path, "Fold verification")
            verification = json.loads(verification_path.read_text(encoding="utf-8"))
            fold_verification_records[family][str(fold_id)] = artifact(verification_path)
            fold_run_path = public_fold / "run.json"
            require_regular_path(fold_run_path, "Fold run")
            fold_run_record = artifact(fold_run_path)
            fold_run_records[family][str(fold_id)] = fold_run_record
            checks.add(
                f"final.{family}.fold_{fold_id}.verification",
                verification.get("status") == "Passed"
                and verification.get("failed_count") == 0
                and identity_matches(verification, config)
                and verification.get("scope") == "fold"
                and verification.get("family") == family
                and verification.get("fold_id") == fold_id
                and verification.get("verified_artifacts", {}).get("run") == fold_run_record
                and verification.get("verified_artifacts", {}).get("config") == artifact(config_path),
            )
            fold_run = json.loads(fold_run_path.read_text(encoding="utf-8"))
            checks.add(f"final.{family}.fold_{fold_id}.identity", identity_matches(fold_run, config))
            checks.add(
                f"final.{family}.fold_{fold_id}.top_binding",
                run.get("stages", {}).get(family, {}).get("folds", {}).get(str(fold_id), {}).get("verification")
                == fold_verification_records[family][str(fold_id)],
            )
            fold_run_hashes[family][fold_id] = sha256(fold_run_path)
            family_wall[family] += float(fold_run["resources"]["wall_seconds"])
            table_path = require_record_within(
                fold_run["artifacts"]["heldout_logit_table_private"],
                private_run_dir(config),
                exact_relative=f"fold-{fold_id}/{family}/heldout-logits.npz",
            )
            checks.add(
                f"final.{family}.fold_{fold_id}.verified_table",
                verification.get("verified_artifacts", {}).get("private_table") == artifact(table_path),
            )
            with np.load(table_path, allow_pickle=False) as table:
                for index, sample_id_value in enumerate(table["sample_ids"].tolist()):
                    sample_id = str(sample_id_value)
                    if sample_id in fold_tables[family]:
                        checks.add(f"final.{family}.duplicate_row", False)
                    fold_tables[family][sample_id] = {
                        "component_id": str(table["component_ids"][index]),
                        "fold_id": int(table["fold_ids"][index]),
                        "gold": np.asarray(table["gold"][index], dtype=np.uint8),
                        "logits": np.asarray(table["logits"][index], dtype=np.float32),
                        "character_length": int(table["character_lengths"][index]),
                        "token_length": int(table["token_lengths"][index]),
                    }
    expected_ids = [row["sample_id"] for row in sources["train_rows"]]
    checks.add("final.m1_coverage", set(fold_tables["m1"]) == set(expected_ids))
    checks.add("final.m3_coverage", set(fold_tables["m3"]) == set(expected_ids))

    paired_path = require_record_within(
        run["artifacts"]["paired_oof_private"], private_run_dir(config), exact_relative="paired-oof.npz"
    )
    checks.add("final.summary_paired_record", summary.get("paired_table_private") == artifact(paired_path))
    with np.load(paired_path, allow_pickle=False) as paired:
        required = {
            "sample_ids",
            "component_ids",
            "fold_ids",
            "gold",
            "m1_logits",
            "m3_logits",
            "character_lengths",
            "m1_token_lengths",
            "m3_token_lengths",
            "m1_fold_run_sha256",
            "m3_fold_run_sha256",
        }
        checks.add("final.paired_schema", set(paired.files) == required, sorted(paired.files))
        paired_values = {name: np.asarray(paired[name]) for name in paired.files}
    checks.add("final.paired_source_order", paired_values["sample_ids"].tolist() == expected_ids)
    checks.add("final.paired_shapes", paired_values["gold"].shape == (3360, 6) and paired_values["m1_logits"].shape == (3360, 6) and paired_values["m3_logits"].shape == (3360, 6))
    checks.add("final.paired_finite_m1", np.isfinite(paired_values["m1_logits"]).all())
    checks.add("final.paired_finite_m3", np.isfinite(paired_values["m3_logits"]).all())
    checks.add(
        "final.source_order_digest",
        summary.get("source_order_sha256") == canonical_digest(expected_ids),
    )
    for index, row in enumerate(sources["train_rows"]):
        sample_id = row["sample_id"]
        expected_fold = int(sources["assignments"][sample_id]["fold_id"])
        m1 = fold_tables["m1"][sample_id]
        m3 = fold_tables["m3"][sample_id]
        checks.add(f"final.row_{index}.component", str(paired_values["component_ids"][index]) == row["component_id"] == m1["component_id"] == m3["component_id"])
        checks.add(f"final.row_{index}.fold", int(paired_values["fold_ids"][index]) == expected_fold == m1["fold_id"] == m3["fold_id"])
        expected_gold = np.asarray(row["labels"], dtype=np.uint8)
        checks.add(f"final.row_{index}.gold", np.array_equal(paired_values["gold"][index], expected_gold) and np.array_equal(m1["gold"], expected_gold) and np.array_equal(m3["gold"], expected_gold))
        checks.add(f"final.row_{index}.m1", np.array_equal(paired_values["m1_logits"][index], m1["logits"]))
        checks.add(f"final.row_{index}.m3", np.array_equal(paired_values["m3_logits"][index], m3["logits"]))
        checks.add(f"final.row_{index}.length", int(paired_values["character_lengths"][index]) == len(row["text"]) == m1["character_length"] == m3["character_length"])
        checks.add(f"final.row_{index}.m1_run", str(paired_values["m1_fold_run_sha256"][index]) == fold_run_hashes["m1"][expected_fold])
        checks.add(f"final.row_{index}.m3_run", str(paired_values["m3_fold_run_sha256"][index]) == fold_run_hashes["m3"][expected_fold])
    checks.add(
        "final.m1_wall_budget",
        family_wall["m1"] <= float(config["resources"]["m1_total_wall_hours"]) * 3600,
        family_wall["m1"],
    )
    checks.add(
        "final.m3_wall_budget",
        family_wall["m3"] <= float(config["resources"]["m3_total_wall_hours"]) * 3600,
        family_wall["m3"],
    )
    private_root = private_run_dir(config)
    checks.add("final.private_root_mode", mode(private_root) == 0o700, oct(mode(private_root)))
    for child in sorted(private_root.rglob("*")):
        expected_mode = 0o700 if child.is_dir() else 0o600
        checks.add(
            f"final.private_mode.{child.relative_to(private_root)}",
            mode(child) == expected_mode,
            oct(mode(child)),
        )
    privacy_violations = []
    for json_path in sorted(run_dir.rglob("*.json")):
        if json_path.name == "verification.json" and json_path.parent == run_dir:
            continue
        privacy_violations.extend(
            f"{json_path.relative_to(run_dir)}:{path}"
            for path in public_sensitive_paths(json.loads(json_path.read_text(encoding="utf-8")))
        )
    checks.add("final.public_privacy", not privacy_violations, privacy_violations)

    result = {
        "schema_version": "exp-oof-final-verification-v2" if is_v2(config) else "exp-058-oof-final-verification-v1",
        "experiment_id": experiment_id(config),
        "stage": stage_name(config),
        **verification_identity(config_path, config),
        "scope": "final",
        "verified_at_utc": utc_now(),
        "status": "Passed" if not checks.failed else "Failed",
        "check_count": len(checks.rows),
        "passed_count": len(checks.rows) - len(checks.failed),
        "failed_count": len(checks.failed),
        "checks": checks.rows,
        "independence": {
            "runner_imported": False,
            "model_libraries_imported": False,
            "all_fold_tables_recomputed": True,
            "paired_table_recomputed": True,
        },
        "verified_artifacts": {
            "config": artifact(config_path),
            "run": artifact(run_path),
            "summary": artifact(summary_path),
            "paired_oof_private": artifact(paired_path),
            "fold_runs": fold_run_records,
            "fold_verifications": fold_verification_records,
        },
        "claim_boundary": "Verified paired train OOF logits only; calibration and routing remain separate experiments.",
    }
    atomic_json(output_path, result)
    write_text_once(
        summary_output,
        "\n".join(
            [
                "# EXP-058 Paired OOF Production Verification",
                "",
                f"- Status: `{result['status']}`",
                f"- Checks: `{result['passed_count']}/{result['check_count']}`",
                "- Paired train rows: `3,360`",
                "- M1/M3 fold runs: `5/5` and `5/5`",
                "- Metrics/calibration/oracle/router: `not computed`",
                "- Validation/test access: `false`",
                "",
                result["claim_boundary"],
                "",
            ]
        ),
    )
    post_write_violations = public_artifact_violations(config)
    if post_write_violations:
        raise RuntimeError(f"Public artifact allowlist failed after final verification: {post_write_violations}")
    if checks.failed:
        raise RuntimeError(f"Final OOF verification failed: {len(checks.failed)} checks")
    return result


def verify_completion(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    if not is_v2(config):
        raise PermissionError("OOF completion verification applies only to config-v2")
    path = public_run_dir(config) / "oof-complete.json"
    require_regular_path(path, "OOF completion record")
    completion = json.loads(path.read_text(encoding="utf-8"))
    run_path = public_run_dir(config) / "run.json"
    summary_path = public_run_dir(config) / "paired-oof-summary.json"
    verification_path = public_run_dir(config) / "verification.json"
    for required_path, field in (
        (run_path, "Top-level OOF run"),
        (summary_path, "Paired OOF summary"),
        (verification_path, "Final OOF verification"),
    ):
        require_regular_path(required_path, field)
    run = json.loads(run_path.read_text(encoding="utf-8"))
    final_verification = json.loads(verification_path.read_text(encoding="utf-8"))
    checks = Checks()
    checks.add("completion.canonical_path", path == public_run_dir(config) / "oof-complete.json")
    checks.add("completion.identity", identity_matches(completion, config))
    checks.add("completion.status", completion.get("status") == "Complete")
    checks.add("completion.config", completion.get("config") == artifact(config_path))
    checks.add("completion.public_privacy", not public_sensitive_paths(completion))
    public_violations = public_artifact_violations(config)
    checks.add("completion.public_allowlist", not public_violations, public_violations)
    checks.add(
        "completion.final_passed",
        final_verification.get("status") == "Passed"
        and final_verification.get("failed_count") == 0
        and identity_matches(final_verification, config)
        and final_verification.get("scope") == "final"
        and final_verification.get("verified_artifacts", {}).get("run") == artifact(run_path)
        and final_verification.get("verified_artifacts", {}).get("summary") == artifact(summary_path),
    )
    artifacts = completion.get("artifacts", {})
    checks.add("completion.run", artifacts.get("run") == artifact(run_path))
    checks.add("completion.summary", artifacts.get("summary") == artifact(summary_path))
    checks.add("completion.verification", artifacts.get("final_verification") == artifact(verification_path))
    paired = run.get("artifacts", {}).get("paired_oof_private")
    checks.add("completion.paired_record", isinstance(paired, dict) and artifacts.get("paired_oof_private") == paired)
    if isinstance(paired, dict):
        paired_path = require_record_within(
            paired, private_run_dir(config), exact_relative="paired-oof.npz"
        )
        checks.add("completion.paired_artifact", artifact(paired_path) == paired)
        checks.add(
            "completion.final_paired_binding",
            final_verification.get("verified_artifacts", {}).get("paired_oof_private") == paired,
        )
    result = {
        "schema_version": "exp-oof-completion-verification-v2",
        "experiment_id": experiment_id(config),
        "stage": stage_name(config),
        "run_id": run_id(config),
        "attempt_id": attempt_id(config),
        "model_seed": model_seed(config),
        "seed_contract": seed_contract(config),
        "config": artifact(config_path),
        "cli_identity": config["_cli_identity"],
        "scope": "completion",
        "verified_at_utc": utc_now(),
        "status": "Passed" if not checks.failed else "Failed",
        "check_count": len(checks.rows),
        "passed_count": len(checks.rows) - len(checks.failed),
        "failed_count": len(checks.failed),
        "checks": checks.rows,
        "independence": {"runner_imported": False, "completion_rehashed": True},
    }
    if checks.failed:
        raise RuntimeError(f"OOF completion verification failed: {len(checks.failed)} checks")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--scope", choices=("fold", "final", "completion"), required=True)
    parser.add_argument("--family", choices=("m1", "m3"))
    parser.add_argument("--fold", type=int)
    parser.add_argument("--model-seed", type=int)
    parser.add_argument("--run-id")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--expected-fold-manifest-sha256")
    parser.add_argument("--expected-data-manifest-sha256")
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = load_config(config_path)
    bind_cli_identity(
        config,
        cli_model_seed=args.model_seed,
        cli_run_id=args.run_id,
        cli_output_root=args.output_root,
        cli_fold_manifest_sha256=args.expected_fold_manifest_sha256,
        cli_data_manifest_sha256=args.expected_data_manifest_sha256,
    )
    if args.scope == "fold":
        if args.family is None or args.fold not in range(5):
            raise ValueError("Fold scope requires --family and --fold 0..4")
        result = verify_fold(config_path, config, args.family, args.fold)
    elif args.scope == "final":
        if args.family is not None or args.fold is not None:
            raise ValueError("Final scope does not accept --family/--fold")
        result = verify_final(config_path, config)
    else:
        if args.family is not None or args.fold is not None:
            raise ValueError("Completion scope does not accept --family/--fold")
        result = verify_completion(config_path, config)
    print(json.dumps({"status": result["status"], "checks": result["check_count"]}, sort_keys=True))


if __name__ == "__main__":
    main()
