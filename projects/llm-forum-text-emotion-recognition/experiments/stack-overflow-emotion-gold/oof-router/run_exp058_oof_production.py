#!/usr/bin/env python3
"""Run authorized five-fold M1/M3 EXP-058 OOF production."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import gc
import fcntl
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import re
import resource
import shutil
import stat
import subprocess
import sys
import time
from typing import Any, Iterable, Iterator, Sequence


LEGACY_EXPERIMENT_ID = "EXP-058"
LEGACY_STAGE = "paired-m1-m3-oof-production"
LEGACY_CONFIG_SCHEMA = "exp-058-oof-production-config-v1"
CONFIG_V2_SCHEMA = "exp-oof-production-config-v2"
ATTEMPT_RE = re.compile(r"attempt-[1-9][0-9]*\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
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
LIVE_RUNNER_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
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
    "schema_version",
    "experiment_id",
    "rq_id",
    "tier",
    "stage",
    "run_id",
    "attempt_id",
    "authorization",
    "execution",
    "seed_contract",
    "data",
    "implementation",
    "prerequisites",
    "outputs",
    "initialization",
    "m1",
    "m3",
    "resources",
}
V2_AUTHORIZATION_KEYS = {
    "authorized_at",
    "basis",
    "fold_ids",
    "model_seed",
    "assembly",
    "full_oof_training",
    "heldout_forward",
    "model_loading",
    "calibration",
    "metrics",
    "oracle_analysis",
    "router_training",
    "test_access",
    "validation_access",
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
    if is_v2(config):
        return str(config["run_id"])
    return "exp-058-paired-oof-production"


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
    if not isinstance(expected, dict):
        raise ValueError(f"Missing initialization expectations for fold {fold_id}")
    required = {"model_seed", *INIT_HASH_FIELDS}
    if set(expected) != required:
        raise ValueError(f"Initialization expectation schema drift for fold {fold_id}")
    if int(expected["model_seed"]) != model_seed(config):
        raise ValueError(f"Initialization seed drift for fold {fold_id}")
    for field in INIT_HASH_FIELDS:
        require_digest(expected[field], f"initialization.expected_by_fold.{fold_id}.{field}")
    return expected


def initialization_state_sha256(family: str, observed: dict[str, Any]) -> str:
    allowed = {
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
    if family not in allowed:
        raise ValueError(f"Unknown initialization family: {family}")
    return canonical_digest({key: observed[key] for key in allowed[family]})


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


def require_regular_path(path: Path, field: str) -> Path:
    if not lexists(path):
        raise FileNotFoundError(path)
    observed = os.lstat(path)
    if stat.S_ISLNK(observed.st_mode) or not stat.S_ISREG(observed.st_mode):
        raise ValueError(f"{field} must be a regular non-symlink file: {path}")
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
    if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
        raise ValueError("Artifact record must have exact path/bytes/sha256 fields")
    require_digest(record["sha256"], "artifact.sha256")
    path = resolve_project(str(record["path"]))
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Frozen artifact drift: {path}")
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


def shared_scientific_contract(config: dict[str, Any]) -> dict[str, Any]:
    """Return the seed-independent contract that must match across EXP-061/062."""
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
        "run.json",
        "stdout.log",
        "paired-oof-summary.json",
        "verification.json",
        "VERIFICATION-SUMMARY.md",
        "oof-complete.json",
        "initialization-failure.json",
        "assembly-failure.json",
        "frozen-sources/config.json",
        "frozen-sources/protocol.md",
        "frozen-sources/runner.py",
        "frozen-sources/verifier.py",
        "frozen-sources/tests.py",
        "frozen-sources/m1_runner_reference.py",
        "frozen-sources/qwen_primitives.py",
        "frozen-sources/m3_preflight_reference.py",
    }
    for fold_id in range(5):
        for family in ("m1", "m3"):
            prefix = f"fold-{fold_id}/{family}"
            allowed.update(
                {
                    f"{prefix}/run.json",
                    f"{prefix}/stdout.log",
                    f"{prefix}/history.csv",
                    f"{prefix}/verification.json",
                    f"{prefix}/VERIFICATION-SUMMARY.md",
                    f"{prefix}/failure.json",
                }
            )
    return allowed


def expected_public_json_schema(relative: str) -> str | None:
    if relative == "run.json":
        return "exp-oof-production-run-v2"
    if relative == "paired-oof-summary.json":
        return "exp-paired-oof-summary-v2"
    if relative == "verification.json":
        return "exp-oof-final-verification-v2"
    if relative == "oof-complete.json":
        return "exp-oof-completion-v2"
    if relative == "initialization-failure.json":
        return "exp-oof-initialization-failure-v2"
    if relative == "assembly-failure.json":
        return "exp-oof-assembly-failure-v2"
    if relative == "frozen-sources/config.json":
        return CONFIG_V2_SCHEMA
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
        expected_schema = expected_public_json_schema(relative)
        if path.suffix == ".json":
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
            sensitive = public_sensitive_paths(value)
            if sensitive:
                violations.append(f"sensitive:{relative}:{sensitive}")
    return violations


def assert_public_artifact_allowlist(config: dict[str, Any]) -> None:
    violations = public_artifact_violations(config)
    if violations:
        raise ValueError(f"Public artifact allowlist/schema violation: {violations}")


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
        or run.get("status") != "CompletedAwaitingVerification"
        or verification.get("status") != "Passed"
        or verification.get("failed_count") != 0
    ):
        raise PermissionError("Legacy source fallback requires the verified sealed EXP-058 run")
    frozen = run.get("frozen_sources")
    if not isinstance(frozen, dict) or set(frozen) != {"config", *config["implementation"]}:
        raise ValueError("Legacy frozen-source inventory drift")
    config_record = frozen["config"]
    frozen_config = require_record(config_record)
    if (
        frozen_config.parent.resolve() != (LEGACY_PUBLIC_RUN / "frozen-sources").resolve()
        or sha256(config_path) != sha256(frozen_config)
    ):
        raise ValueError("Legacy frozen config does not match the archived run")
    for name, expected in config["implementation"].items():
        observed_path = require_record(frozen[name])
        if observed_path.parent.resolve() != (LEGACY_PUBLIC_RUN / "frozen-sources").resolve():
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
    expected_execution = {"model_seed": expected_seed, **V2_EXECUTION}
    if config.get("execution") != expected_execution:
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
    expected_by_fold = initialization.get("expected_by_fold")
    if not isinstance(expected_by_fold, dict) or set(expected_by_fold) != {str(i) for i in range(5)}:
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


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    schema = config.get("schema_version")
    if schema not in (LEGACY_CONFIG_SCHEMA, CONFIG_V2_SCHEMA):
        raise ValueError("Unexpected OOF production config schema")
    if schema == LEGACY_CONFIG_SCHEMA and (
        config.get("experiment_id") != LEGACY_EXPERIMENT_ID or config.get("stage") != LEGACY_STAGE
    ):
        raise ValueError("Unexpected sealed EXP-058 production identity")
    if schema == CONFIG_V2_SCHEMA:
        validate_v2_identity(config)
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
    if auth.get("fold_ids") != [0, 1, 2, 3, 4] or auth.get("model_seed") != model_seed(config):
        raise PermissionError("Full OOF authorization fold/seed drift")
    execution = config["execution"]
    if execution.get("fold_ids") != [0, 1, 2, 3, 4] or int(execution.get("model_seed", model_seed(config))) != model_seed(config):
        raise ValueError("Execution fold list drift")
    if execution.get("m1_epochs") != 4 or execution.get("m3_epochs") != 2:
        raise ValueError("Frozen OOF epoch contract drift")
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
        live_runner = require_record(config["implementation"]["runner"])
        if live_runner != LIVE_RUNNER_PATH.resolve():
            raise ValueError("Config-v2 runner record is not bound to the live runner artifact")
    if schema == LEGACY_CONFIG_SCHEMA:
        config["_archive_only"] = True
    for record in config["prerequisites"].values():
        require_record(record)
    require_record(config["data"]["train"])
    if schema == CONFIG_V2_SCHEMA:
        verify_v2_frozen_data_identity(config)
    config["_config_path"] = str(path.resolve())
    config["_config_sha256"] = sha256(path)
    return config


def expected_cli_identity(config: dict[str, Any]) -> dict[str, Any]:
    """Return the non-overridable command identity for a config-v2 attempt."""
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
    """Require config-v2 identity flags and prove that none override the config."""
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


@contextmanager
def heavy_research_workload_mutex(config: dict[str, Any], fold_id: int) -> Iterator[dict[str, Any]]:
    """Acquire the shared heavy-workload mutex without waiting or mutating an attempt."""
    if not is_v2(config):
        raise PermissionError("The shared workload mutex is only for registered config-v2 runs")
    lock_path = resolve_output(HEAVY_WORKLOAD_LOCK_PATH)
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(lock_path.parent, 0o700)
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        os.chmod(lock_path, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Shared heavy-research workload mutex is already owned") from error
        metadata = {
            "schema_version": "exp-heavy-workload-lock-owner-v1",
            "path": HEAVY_WORKLOAD_LOCK_PATH,
            "mode": "nonblocking-advisory-exclusive",
            "owner": {
                "experiment_id": experiment_id(config),
                "run_id": run_id(config),
                "attempt_id": attempt_id(config),
                "model_seed": model_seed(config),
                "scope": "m3",
                "fold_id": fold_id,
                "pid": os.getpid(),
            },
            "acquired_at_utc": utc_now(),
        }
        payload = (json.dumps(metadata, sort_keys=True) + "\n").encode()
        os.ftruncate(descriptor, 0)
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.write(descriptor, payload)
        os.fsync(descriptor)
        yield metadata
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def verify_prerequisites(config: dict[str, Any]) -> dict[str, Any]:
    fold_verification = load_json_record(config["prerequisites"]["fold_verification"])
    if (
        fold_verification.get("status") != "Passed"
        or fold_verification.get("check_count") != 131
        or fold_verification.get("passed_count") != 131
        or fold_verification.get("failed_count") != 0
    ):
        raise RuntimeError("Fold manifest is not independently verified")
    if not is_v2(config):
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

    if is_v2(config):
        manifest = load_json_record(config["prerequisites"]["initialization_manifest"])
        verification = load_json_record(config["prerequisites"]["initialization_verification"])
        manifest_keys = {
            "schema_version", "experiment_id", "run_id", "attempt_id", "model_seed",
            "seed_contract", "base_asset_manifest_sha256", "fold_manifest_sha256",
            "shared_scientific_contract_sha256", "cross_seed_gate", "folds",
        }
        identity_ok = (
            set(manifest) == manifest_keys
            and manifest.get("schema_version") == "exp-oof-initialization-manifest-v1"
            and manifest.get("experiment_id") == experiment_id(config)
            and manifest.get("run_id") == run_id(config)
            and manifest.get("attempt_id") == attempt_id(config)
            and manifest.get("model_seed") == model_seed(config)
            and manifest.get("seed_contract") == seed_contract(config)
            and manifest.get("shared_scientific_contract_sha256")
            == shared_scientific_contract_sha256(config)
            and manifest.get("cross_seed_gate") == {
                "required_before_formal_training": True,
                "status": "Pending",
                "verification_schema": "exp-oof-cross-seed-initialization-verification-v1",
            }
        )
        if not identity_ok:
            raise ValueError("Initialization manifest identity drift")
        if (
            manifest.get("base_asset_manifest_sha256")
            != config["initialization"]["base_asset_manifest_sha256"]
            or manifest.get("fold_manifest_sha256") != sha256(manifest_path)
        ):
            raise ValueError("Initialization manifest source identity drift")
        folds = manifest.get("folds")
        if not isinstance(folds, dict) or set(folds) != {str(i) for i in range(5)}:
            raise ValueError("Initialization manifest does not cover five folds")
        for fold_id in range(5):
            expected = expected_initialization(config, fold_id)
            observed = folds[str(fold_id)]
            if not isinstance(observed, dict):
                raise ValueError(f"Initialization manifest fold {fold_id} is invalid")
            for key, value in expected.items():
                if observed.get(key) != value:
                    raise ValueError(f"Initialization manifest fold {fold_id} drift: {key}")
            if observed.get("m3_lora_b_zero_initialized") is not True:
                raise ValueError("LoRA-B equality is allowed only with verified zero initialization")
        manifest_record = config["prerequisites"]["initialization_manifest"]
        verified_manifest = verification.get("verified_artifacts", {}).get("initialization_manifest")
        if (
            verification.get("status") != "Passed"
            or verification.get("failed_count") != 0
            or verification.get("experiment_id") != experiment_id(config)
            or verification.get("run_id") != run_id(config)
            or verification.get("attempt_id") != attempt_id(config)
            or verified_manifest != manifest_record
        ):
            raise RuntimeError("Initialization manifest is not independently verified")
        cross_record = config["prerequisites"]["cross_seed_initialization_verification"]
        cross_seed = load_json_record(cross_record)
        member = cross_seed.get("members", {}).get(experiment_id(config), {})
        if (
            cross_seed.get("schema_version")
            != "exp-oof-cross-seed-initialization-verification-v1"
            or cross_seed.get("status") != "Passed"
            or cross_seed.get("failed_count") != 0
            or cross_seed.get("shared_scientific_contract_sha256")
            != shared_scientific_contract_sha256(config)
            or cross_seed.get("base_asset_manifest_sha256")
            != manifest.get("base_asset_manifest_sha256")
            or cross_seed.get("fold_manifest_sha256") != manifest.get("fold_manifest_sha256")
            or member.get("model_seed") != model_seed(config)
            or member.get("formal_run_id") != run_id(config)
            or member.get("formal_attempt_id") != attempt_id(config)
            or member.get("initialization_manifest") != manifest_record
            or member.get("initialization_verification")
            != config["prerequisites"]["initialization_verification"]
            or config["authorization"]["cross_seed_initialization_verification_sha256"]
            != cross_record["sha256"]
        ):
            raise RuntimeError("Cross-seed initialization gate is not bound to this formal attempt")
        shared = load_json_record(config["prerequisites"]["shared_config"])
        if shared["data"]["test_status"] != "sealed_not_authorized_for_model_access":
            raise PermissionError("Shared test contract drift")
        observed_assets = base_asset_manifest_sha256(shared)
        if observed_assets != config["initialization"]["base_asset_manifest_sha256"]:
            raise ValueError("Base asset manifest identity drift")
        return {
            "shared": shared,
            "initialization_manifest": manifest,
            "initialization_verification": verification,
            "cross_seed_initialization_verification": cross_seed,
        }

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
        if set(row) != MANIFEST_FIELDS or row.get("experiment_id") != LEGACY_EXPERIMENT_ID:
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
    key = "public_attempt_dir" if is_v2(config) else "public_run_dir"
    resolver = resolve_output if is_v2(config) else resolve_project
    return resolver(config["outputs"][key])


def private_run_dir(config: dict[str, Any]) -> Path:
    key = "private_attempt_dir" if is_v2(config) else "private_run_dir"
    resolver = resolve_output if is_v2(config) else resolve_project
    return resolver(config["outputs"][key])


def public_namespace(config: dict[str, Any]) -> Path:
    return (
        resolve_output(config["outputs"]["public_namespace"])
        if is_v2(config)
        else public_run_dir(config)
    )


def private_namespace(config: dict[str, Any]) -> Path:
    return (
        resolve_output(config["outputs"]["private_namespace"])
        if is_v2(config)
        else private_run_dir(config)
    )


def selection_record_path(config: dict[str, Any]) -> Path:
    if not is_v2(config):
        raise PermissionError("Legacy EXP-058 has no mutable attempt selection stage")
    return resolve_output(config["outputs"]["selection_record"])


def config_provenance(config: dict[str, Any]) -> dict[str, Any]:
    path = Path(config["_config_path"])
    if sha256(path) != config["_config_sha256"]:
        raise ValueError("Config changed after it was loaded")
    return artifact(path)


def identity_provenance(config: dict[str, Any]) -> dict[str, Any]:
    provenance = {
        "experiment_id": experiment_id(config),
        "stage": stage_name(config),
        "run_id": run_id(config),
        "attempt_id": attempt_id(config),
        "model_seed": model_seed(config),
        "seed_contract": seed_contract(config),
        "seed_contract_sha256": canonical_digest(seed_contract(config)),
        "config": config_provenance(config),
    }
    if is_v2(config):
        if config.get("_cli_identity") != expected_cli_identity(config):
            raise PermissionError("Config-v2 CLI identity was not bound before execution")
        provenance["cli_identity"] = config["_cli_identity"]
    return provenance


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


def guard_initialize_invocation(config: dict[str, Any]) -> None:
    if is_v2(config) and lexists(selection_record_path(config)):
        raise FileExistsError("A selected attempt already blocks initialization")
    existing = [
        display_path(path)
        for path in (public_run_dir(config), private_run_dir(config))
        if lexists(path)
    ]
    if existing:
        raise FileExistsError(f"Append-only attempt paths already exist: {existing}")


def guard_fold_invocation(config: dict[str, Any], family: str, fold_id: int) -> None:
    top = load_top_run(config)
    public_fold, private_fold = fold_dirs(config, family, fold_id)
    if (
        top.get("status") != "InProgress"
        or top.get("stages", {}).get(family, {}).get("folds", {}).get(str(fold_id), {}).get("status")
        != "Pending"
        or lexists(public_fold)
        or lexists(private_fold)
        or lexists(public_run_dir(config) / "verification.json")
        or lexists(public_run_dir(config) / "oof-complete.json")
    ):
        raise RuntimeError(f"{family} fold {fold_id} is not a fresh Pending append-only stage")


def guard_assembly_invocation(config: dict[str, Any]) -> None:
    top = load_top_run(config)
    if (
        top.get("status") != "InProgress"
        or top.get("stages", {}).get("assembly", {}).get("status") != "Pending"
        or lexists(public_run_dir(config) / "paired-oof-summary.json")
        or lexists(private_run_dir(config) / "paired-oof.npz")
        or lexists(public_run_dir(config) / "verification.json")
        or lexists(public_run_dir(config) / "oof-complete.json")
    ):
        raise RuntimeError("Assembly is not a fresh Pending append-only stage")


def initialize(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    if config.get("_archive_only"):
        raise PermissionError("Sealed EXP-058 is archive-only and can never be rerun")
    prerequisites = verify_prerequisites(config)
    partitions = load_partitions(config)
    run_dir = public_run_dir(config)
    private_dir = private_run_dir(config)
    guard_initialize_invocation(config)
    free_gb = shutil.disk_usage(PROJECT_ROOT).free / 1e9
    if free_gb < float(config["resources"]["minimum_free_disk_gb"]):
        raise OSError("Insufficient free disk for checkpointed OOF production")
    if is_v2(config):
        public_namespace(config).mkdir(parents=True, exist_ok=True)
        private_namespace(config).mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(private_namespace(config), 0o700)
        run_dir.mkdir()
        config["_initialization_claimed"] = True
        private_dir.mkdir(mode=0o700)
    else:
        run_dir.mkdir(parents=True)
        private_dir.mkdir(parents=True, mode=0o700)
    os.chmod(private_dir, 0o700)
    frozen_sources = freeze_sources(run_dir, config_path, config)
    partition_contract_path = private_dir / "partition-contract.json"
    atomic_json(
        partition_contract_path,
        {
            "schema_version": "exp-oof-partition-contract-v2" if is_v2(config) else "exp-058-oof-partition-contract-v1",
            **identity_provenance(config),
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
        "schema_version": "exp-oof-production-run-v2" if is_v2(config) else "exp-058-oof-production-run-v1",
        **identity_provenance(config),
        "rq_id": config.get("rq_id", "RQ-S3"),
        "tier": "Major",
        "status": "InProgress",
        "started_at_utc": now,
        "working_directory": str(PROJECT_ROOT),
        "git": git_metadata(),
        "authorization": config["authorization"],
        "initialization": {
            "base_asset_manifest_sha256": (
                config["initialization"]["base_asset_manifest_sha256"]
                if is_v2(config)
                else base_asset_manifest_sha256(prerequisites["shared"])
            ),
            "manifest": (
                config["prerequisites"].get("initialization_manifest") if is_v2(config) else None
            ),
            "verification": (
                config["prerequisites"].get("initialization_verification") if is_v2(config) else None
            ),
        },
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
    assert_public_artifact_allowlist(config)
    return run


def record_initialization_failure(config: dict[str, Any], error: Exception) -> None:
    run_dir = public_run_dir(config)
    if (
        is_v2(config)
        and config.get("_initialization_claimed") is not True
    ) or not run_dir.is_dir() or lexists(run_dir / "verification.json") or lexists(run_dir / "oof-complete.json"):
        return
    failure_path = run_dir / "initialization-failure.json"
    if lexists(failure_path):
        return
    run_path = run_dir / "run.json"
    if run_path.is_file():
        current = json.loads(run_path.read_text(encoding="utf-8"))
        if (
            current.get("status") != "InProgress"
            or current.get("stages", {}).get("initialize", {}).get("status") == "Passed"
        ):
            return
    atomic_json(
        failure_path,
        {
            "schema_version": "exp-oof-initialization-failure-v2",
            **identity_provenance(config),
            "status": "Failed",
            "failed_at_utc": utc_now(),
            "error_type": type(error).__name__,
            "error": str(error),
            "validation_accessed": False,
            "test_accessed": False,
        },
    )
    if run_path.is_file():
        run = json.loads(run_path.read_text(encoding="utf-8"))
        run["status"] = "BlockedByFailure"
        run["initialization_failure"] = artifact(failure_path)
        atomic_json(run_path, run)


def load_top_run(config: dict[str, Any]) -> dict[str, Any]:
    path = public_run_dir(config) / "run.json"
    require_regular_path(path, "Top-level production run")
    run = json.loads(path.read_text(encoding="utf-8"))
    if (
        run.get("experiment_id") != experiment_id(config)
        or run.get("stage") != stage_name(config)
        or (is_v2(config) and (
            run.get("run_id") != run_id(config)
            or run.get("attempt_id") != attempt_id(config)
            or run.get("model_seed") != model_seed(config)
            or run.get("seed_contract") != seed_contract(config)
            or run.get("config") != config_provenance(config)
            or run.get("cli_identity") != config.get("_cli_identity")
        ))
    ):
        raise ValueError("Production run identity drift")
    return run


def verification_path(config: dict[str, Any], family: str, fold_id: int) -> Path:
    return fold_dirs(config, family, fold_id)[0] / "verification.json"


def require_passed_fold(config: dict[str, Any], family: str, fold_id: int) -> dict[str, Any]:
    path = verification_path(config, family, fold_id)
    try:
        require_regular_path(path, f"{family} fold {fold_id} verification")
    except (FileNotFoundError, ValueError) as error:
        raise RuntimeError(f"{family} fold {fold_id} has not been independently verified") from error
    value = json.loads(path.read_text(encoding="utf-8"))
    run_path = fold_dirs(config, family, fold_id)[0] / "run.json"
    require_regular_path(run_path, f"{family} fold {fold_id} run")
    if (
        value.get("status") != "Passed"
        or value.get("failed_count") != 0
        or value.get("experiment_id") != experiment_id(config)
        or value.get("stage") != stage_name(config)
        or (is_v2(config) and (
            value.get("run_id") != run_id(config)
            or value.get("attempt_id") != attempt_id(config)
            or value.get("model_seed") != model_seed(config)
            or value.get("seed_contract") != seed_contract(config)
            or value.get("cli_identity") != config.get("_cli_identity")
            or value.get("scope") != "fold"
            or value.get("family") != family
            or value.get("fold_id") != fold_id
            or value.get("config") != config_provenance(config)
            or value.get("verified_artifacts", {}).get("run") != artifact(run_path)
        ))
    ):
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
    allowed_statuses = ("InProgress",) if is_v2(config) else ("InProgress", "BlockedByFailure")
    if top.get("status") not in allowed_statuses:
        raise RuntimeError("Production run is not open for fold execution")
    if is_v2(config) and lexists(selection_record_path(config)):
        raise FileExistsError("A selected attempt blocks later fold execution")
    if top["stages"][family]["folds"][str(fold_id)]["status"] != "Pending":
        raise RuntimeError(f"{family} fold {fold_id} is not pending")
    if fold_id > 0:
        require_passed_fold(config, family, fold_id - 1)
    if family == "m3":
        for prior_fold in range(5):
            require_passed_fold(config, "m1", prior_fold)
    public_fold, private_fold = fold_dirs(config, family, fold_id)
    if lexists(public_fold) or lexists(private_fold):
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
        "schema_version": "exp-oof-fold-run-v2" if is_v2(config) else "exp-058-oof-fold-run-v1",
        **identity_provenance(config),
        "rq_id": config.get("rq_id", "RQ-S3"),
        "tier": "Major",
        "family": family,
        "fold_id": fold_id,
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
    current_path = public_fold / "run.json"
    current = json.loads(current_path.read_text(encoding="utf-8"))
    top_before = load_top_run(config)
    if (
        current.get("status") != "InProgress"
        or lexists(public_fold / "verification.json")
        or top_before.get("status") != "InProgress"
        or top_before["stages"][family]["folds"][str(fold_id)].get("status") != "InProgress"
    ):
        raise RuntimeError("Refusing to overwrite a completed or verified fold")
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
    assert_public_artifact_allowlist(config)
    return fold_run


def record_failure(config: dict[str, Any], family: str, fold_id: int, error: Exception) -> None:
    public_fold, _ = fold_dirs(config, family, fold_id)
    if not public_fold.is_dir() or lexists(public_fold / "verification.json"):
        return
    failure_path = public_fold / "failure.json"
    if is_v2(config) and lexists(failure_path):
        return
    run_path = public_fold / "run.json"
    if not run_path.is_file():
        return
    fold_run = json.loads(run_path.read_text(encoding="utf-8"))
    top = load_top_run(config)
    if (
        fold_run.get("status") != "InProgress"
        or top.get("status") != "InProgress"
        or top["stages"][family]["folds"][str(fold_id)].get("status") != "InProgress"
        or lexists(public_run_dir(config) / "verification.json")
        or lexists(public_run_dir(config) / "oof-complete.json")
    ):
        return
    failure = {
        "schema_version": "exp-oof-fold-failure-v2" if is_v2(config) else "exp-058-oof-fold-failure-v1",
        **identity_provenance(config),
        "family": family,
        "fold_id": fold_id,
        "status": "Failed",
        "failed_at_utc": utc_now(),
        "error_type": type(error).__name__,
        "error": str(error),
        "validation_accessed": False,
        "test_accessed": False,
    }
    atomic_json(failure_path, failure)
    fold_run["status"] = "Failed"
    fold_run["failed_at_utc"] = failure["failed_at_utc"]
    fold_run["failure"] = artifact(failure_path)
    atomic_json(run_path, fold_run)
    top["status"] = "BlockedByFailure"
    top["stages"][family]["folds"][str(fold_id)] = {
        "status": "Failed",
        "failure": artifact(failure_path),
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

    seed = model_seed(config)
    expected_init = expected_initialization(config, fold_id)
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
    if initial_classifier != expected_init["m1_classifier_init_sha256"]:
        raise ValueError("M1 fresh classifier initialization drift")
    rng_digest = m1_rng_state_digest(config)
    initialization_state = initialization_state_sha256(
        "m1",
        {
            "m1_classifier_init_sha256": initial_classifier,
            "m1_rng_state_digest": rng_digest,
        },
    )
    if is_v2(config) and (
        rng_digest != expected_init["m1_rng_state_digest"]
        or initialization_state != expected_init["m1_initialization_state_sha256"]
    ):
        raise ValueError("M1 initialization-state contract drift")
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
    generator = torch.Generator().manual_seed(seed_contract(config)["m1_batch_seed"])
    batch_orders = [
        torch.randperm(len(train_dataset), generator=generator).tolist()
        for _ in range(int(config["execution"]["m1_epochs"]))
    ]
    batch_order_digests = [
        canonical_digest([partition["training"][index]["sample_id"] for index in order])
        for order in batch_orders
    ]
    batch_order_digest = canonical_digest(batch_order_digests)
    if is_v2(config) and batch_order_digest != expected_init["m1_batch_order_sha256"]:
        raise ValueError("M1 batch-order contract drift")
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
                "batch_order_sha256": batch_order_digests[epoch - 1],
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
    checkpoint_provenance_path = private_fold / "checkpoint-provenance.json"
    atomic_json(
        checkpoint_provenance_path,
        {
            "schema_version": "exp-oof-checkpoint-provenance-v2",
            **identity_provenance(config),
            "family": "m1",
            "fold_id": fold_id,
            "base_asset_manifest_sha256": (
                config["initialization"]["base_asset_manifest_sha256"]
                if is_v2(config)
                else base_asset_manifest_sha256(prerequisites["shared"])
            ),
            "fold_manifest_sha256": partition_bundle["manifest_before"],
            "initialization": {
                "m1_classifier_init_sha256": initial_classifier,
                "m1_rng_state_digest": rng_digest,
                "m1_initialization_state_sha256": initialization_state,
                "m1_batch_order_sha256": batch_order_digest,
            },
            "checkpoint": checkpoint,
        },
        private=True,
    )
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
            "schema_version": "exp-oof-m1-fold-evidence-v2" if is_v2(config) else "exp-058-m1-oof-fold-evidence-v1",
            **identity_provenance(config),
            "fold_id": fold_id,
            "training_order_sha256": partition["training_order_sha256"],
            "heldout_order_sha256": partition["heldout_order_sha256"],
            "training_rows": len(partition["training"]),
            "heldout_rows": len(partition["heldout"]),
            "batch_order_sha256": [row["batch_order_sha256"] for row in history],
            "batch_order_combined_sha256": batch_order_digest,
            "scheduler": schedule,
            "classifier_initial_sha256": initial_classifier,
            "rng_state_digest": rng_digest,
            "initialization_state_sha256": initialization_state,
            "classifier_final_sha256": final_classifier,
            "base_asset_manifest_sha256": (
                config["initialization"]["base_asset_manifest_sha256"]
                if is_v2(config)
                else base_asset_manifest_sha256(prerequisites["shared"])
            ),
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
        "schema_version": "exp-oof-fold-run-v2" if is_v2(config) else "exp-058-oof-fold-run-v1",
        **identity_provenance(config),
        "rq_id": config.get("rq_id", "RQ-S3"),
        "tier": "Major",
        "family": "m1",
        "fold_id": fold_id,
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
            "rng_state_digest": rng_digest,
            "initialization_state_sha256": initialization_state,
            "batch_order_sha256": batch_order_digest,
            "classifier_final_sha256": final_classifier,
            "model_asset_files_verified": model_assets["file_count"],
            "base_asset_manifest_sha256": (
                config["initialization"]["base_asset_manifest_sha256"]
                if is_v2(config)
                else base_asset_manifest_sha256(prerequisites["shared"])
            ),
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
            "checkpoint_provenance_private": artifact(checkpoint_provenance_path),
        },
        "claim_boundary": "One train-only M1 OOF fold; no thresholds, predictions, or metrics.",
    }
    log_line(public_fold, "m1", f"fold {fold_id} completed in {wall_seconds / 3600:.3f} h")
    del model, tokenizer, optimizer, scheduler, train_dataset
    gc.collect()
    return finish_fold(config, "m1", fold_id, fold_run)


def run_m3_fold(
    config: dict[str, Any], fold_id: int, lock_metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    if is_v2(config) and not valid_m3_lock_metadata(lock_metadata, config, fold_id):
        raise PermissionError("Config-v2 M3 execution requires the canonical shared workload mutex")
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
    seed = model_seed(config)
    expected_init = expected_initialization(config, fold_id)
    contract = seed_contract(config)
    head = primitives.build_qwen_head(contract["m3_head_seed"], int(spec["hidden_size"]))
    head_initial = primitives.mlx_tensor_digest(primitives.mlx_trainable(head))
    if head_initial != expected_init["m3_classifier_head_init_sha256"]:
        raise ValueError("M3 fresh head initialization drift")
    wrapper = primitives.make_classification_wrapper(model, head)

    first_ids = mx.array([train_ids[0]], dtype=mx.int32)
    base_logits = wrapper(first_ids)
    mx.eval(base_logits)
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
    observed = primitives.insertion_contract(model, shared)
    converted_logits = wrapper(first_ids)
    mx.eval(converted_logits)
    zero_delta = float(mx.max(mx.abs(base_logits - converted_logits)).item())
    lora_initial_items = primitives.mlx_trainable(model)
    lora_initial = primitives.mlx_tensor_digest(lora_initial_items)
    lora_a_initial_items = [(name, tensor) for name, tensor in lora_initial_items if name.endswith("lora_a")]
    lora_b_initial_items = [(name, tensor) for name, tensor in lora_initial_items if name.endswith("lora_b")]
    if not lora_a_initial_items or len(lora_a_initial_items) != len(lora_b_initial_items):
        raise ValueError("M3 LoRA A/B initialization inventory drift")
    lora_a_initial = primitives.mlx_tensor_digest(lora_a_initial_items)
    lora_b_initial = primitives.mlx_tensor_digest(lora_b_initial_items)
    lora_b_zero_initialized = all(not bool(mx.any(tensor != 0).item()) for _, tensor in lora_b_initial_items)
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
    if lora_initial != expected_init["m3_lora_combined_init_sha256"]:
        raise ValueError("M3 fresh LoRA initialization drift")
    base_before = helpers.frozen_parameter_sentinel(model)
    if base_before["sha256"] != expected_init["m3_base_sentinel_sha256"]:
        raise ValueError("M3 base sentinel drift before training")
    rng_digest = m3_rng_state_digest(config)
    initialization_state = initialization_state_sha256(
        "m3",
        {
            "m3_lora_a_init_sha256": lora_a_initial,
            "m3_lora_b_init_sha256": lora_b_initial,
            "m3_lora_combined_init_sha256": lora_initial,
            "m3_classifier_head_init_sha256": head_initial,
            "m3_base_sentinel_sha256": base_before["sha256"],
            "m3_rng_state_digest": rng_digest,
        },
    )
    if is_v2(config) and (
        lora_a_initial != expected_init["m3_lora_a_init_sha256"]
        or lora_b_initial != expected_init["m3_lora_b_init_sha256"]
        or not lora_b_zero_initialized
        or rng_digest != expected_init["m3_rng_state_digest"]
        or initialization_state != expected_init["m3_initialization_state_sha256"]
    ):
        raise ValueError("M3 initialization-state contract drift")

    rng = np.random.default_rng(contract["m3_batch_seed"])
    batch_orders = np.stack(
        [rng.permutation(len(partition["training"])) for _ in range(int(config["execution"]["m3_epochs"]))]
    ).astype(np.int32)
    batch_order_digests = [
        canonical_digest([partition["training"][int(index)]["sample_id"] for index in order])
        for order in batch_orders
    ]
    batch_order_digest = canonical_digest(batch_order_digests)
    if is_v2(config) and batch_order_digest != expected_init["m3_batch_order_sha256"]:
        raise ValueError("M3 batch-order contract drift")
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
                "batch_order_sha256": batch_order_digests[epoch - 1],
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
    checkpoint_provenance_path = private_fold / "checkpoint-provenance.json"
    atomic_json(
        checkpoint_provenance_path,
        {
            "schema_version": "exp-oof-checkpoint-provenance-v2",
            **identity_provenance(config),
            "family": "m3",
            "fold_id": fold_id,
            "base_asset_manifest_sha256": (
                config["initialization"]["base_asset_manifest_sha256"]
                if is_v2(config)
                else base_asset_manifest_sha256(prerequisites["shared"])
            ),
            "fold_manifest_sha256": partition_bundle["manifest_before"],
            "initialization": {
                "m3_lora_a_init_sha256": lora_a_initial,
                "m3_lora_b_init_sha256": lora_b_initial,
                "m3_lora_combined_init_sha256": lora_initial,
                "m3_classifier_head_init_sha256": head_initial,
                "m3_base_sentinel_sha256": base_before["sha256"],
                "m3_rng_state_digest": rng_digest,
                "m3_initialization_state_sha256": initialization_state,
                "m3_batch_order_sha256": batch_order_digest,
                "m3_lora_b_zero_initialized": lora_b_zero_initialized,
            },
            "checkpoint": {
                "adapter": artifact(adapter_path),
                "head": artifact(head_path),
            },
        },
        private=True,
    )
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
            "schema_version": "exp-oof-m3-fold-evidence-v2" if is_v2(config) else "exp-058-m3-oof-fold-evidence-v1",
            **identity_provenance(config),
            "fold_id": fold_id,
            "training_order_sha256": partition["training_order_sha256"],
            "heldout_order_sha256": partition["heldout_order_sha256"],
            "training_rows": len(partition["training"]),
            "heldout_rows": len(partition["heldout"]),
            "batch_order_sha256": [row["batch_order_sha256"] for row in history],
            "batch_order_combined_sha256": batch_order_digest,
            "head_initial_sha256": head_initial,
            "lora_a_initial_sha256": lora_a_initial,
            "lora_b_initial_sha256": lora_b_initial,
            "lora_b_zero_initialized": lora_b_zero_initialized,
            "head_final_sha256": head_final,
            "lora_initial_sha256": lora_initial,
            "rng_state_digest": rng_digest,
            "initialization_state_sha256": initialization_state,
            "lora_final_sha256": lora_final,
            "base_asset_manifest_sha256": (
                config["initialization"]["base_asset_manifest_sha256"]
                if is_v2(config)
                else base_asset_manifest_sha256(prerequisites["shared"])
            ),
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
        "schema_version": "exp-oof-fold-run-v2" if is_v2(config) else "exp-058-oof-fold-run-v1",
        **identity_provenance(config),
        "rq_id": config.get("rq_id", "RQ-S3"),
        "tier": "Major",
        "family": "m3",
        "fold_id": fold_id,
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
            "lora_a_initial_sha256": lora_a_initial,
            "lora_b_initial_sha256": lora_b_initial,
            "lora_b_zero_initialized": lora_b_zero_initialized,
            "head_final_sha256": head_final,
            "lora_initial_sha256": lora_initial,
            "rng_state_digest": rng_digest,
            "initialization_state_sha256": initialization_state,
            "batch_order_sha256": batch_order_digest,
            "lora_final_sha256": lora_final,
            "zero_step_max_abs_logit_difference": zero_delta,
            "insertion_count": len(observed),
            "lora_parameter_count": lora_count,
            "total_trainable_parameter_count": total_count,
            "nonzero_lora_b_tensors": nonzero_lora_b,
            "base_sentinel_unchanged": base_after == base_before,
            "trainable_whitelist_passed": not unexpected,
            "model_asset_files_verified": model_assets["file_count"],
            "base_asset_manifest_sha256": (
                config["initialization"]["base_asset_manifest_sha256"]
                if is_v2(config)
                else base_asset_manifest_sha256(prerequisites["shared"])
            ),
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
        **({"execution_lock": lock_metadata} if is_v2(config) else {}),
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
            "checkpoint_provenance_private": artifact(checkpoint_provenance_path),
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

    guard_assembly_invocation(config)
    top = load_top_run(config)
    if top.get("status") != "InProgress" or top["stages"]["assembly"]["status"] != "Pending":
        raise RuntimeError("OOF production is not ready for assembly")
    for family in ("m1", "m3"):
        for fold_id in range(5):
            require_passed_fold(config, family, fold_id)
    top["stages"]["assembly"] = {"status": "InProgress", "started_at_utc": utc_now()}
    atomic_json(public_run_dir(config) / "run.json", top)
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
            predictions_path = require_record_within(
                fold_run["artifacts"]["heldout_logit_table_private"],
                private_run_dir(config),
                exact_relative=f"fold-{fold_id}/{family}/heldout-logits.npz",
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
    if lexists(paired_path):
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
        "schema_version": "exp-paired-oof-summary-v2" if is_v2(config) else "exp-058-paired-oof-summary-v1",
        **identity_provenance(config),
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
    assert_public_artifact_allowlist(config)
    return top


def record_assembly_failure(config: dict[str, Any], error: Exception) -> None:
    run_dir = public_run_dir(config)
    if (
        not run_dir.is_dir()
        or lexists(run_dir / "verification.json")
        or lexists(run_dir / "oof-complete.json")
    ):
        return
    failure_path = run_dir / "assembly-failure.json"
    if is_v2(config) and lexists(failure_path):
        return
    top = load_top_run(config)
    if (
        top.get("status") != "InProgress"
        or top.get("stages", {}).get("assembly", {}).get("status") != "InProgress"
    ):
        return
    atomic_json(
        failure_path,
        {
            "schema_version": "exp-oof-assembly-failure-v2" if is_v2(config) else "exp-058-oof-assembly-failure-v1",
            **identity_provenance(config),
            "status": "Failed",
            "failed_at_utc": utc_now(),
            "error_type": type(error).__name__,
            "error": str(error),
            "validation_accessed": False,
            "test_accessed": False,
        },
    )
    top["status"] = "BlockedByFailure"
    top["stages"]["assembly"] = {"status": "Failed", "failure": artifact(failure_path)}
    atomic_json(run_dir / "run.json", top)


def create_json_once(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
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


def complete_oof_attempt(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    if not is_v2(config):
        raise PermissionError("OOF completion is available only for config-v2 attempts")
    completion_path = public_run_dir(config) / "oof-complete.json"
    if lexists(completion_path):
        raise FileExistsError("OOF completion record is immutable and already exists")
    if lexists(selection_record_path(config)):
        raise FileExistsError("A final pipeline selection already exists")
    run_dir = public_run_dir(config)
    run_path = run_dir / "run.json"
    verification_path = run_dir / "verification.json"
    summary_path = run_dir / "paired-oof-summary.json"
    for required_path, field in (
        (run_path, "Top-level OOF run"),
        (verification_path, "Final OOF verification"),
        (summary_path, "Paired OOF summary"),
    ):
        require_regular_path(required_path, field)
    run = json.loads(run_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    expected_identity = (
        verification.get("experiment_id") == experiment_id(config)
        and verification.get("stage") == stage_name(config)
        and verification.get("run_id") == run_id(config)
        and verification.get("attempt_id") == attempt_id(config)
        and verification.get("model_seed") == model_seed(config)
        and verification.get("seed_contract") == seed_contract(config)
        and verification.get("config") == config_provenance(config)
    )
    verified = verification.get("verified_artifacts", {})
    if (
        run.get("status") != "CompletedAwaitingVerification"
        or verification.get("status") != "Passed"
        or verification.get("failed_count") != 0
        or not expected_identity
        or verified.get("config") != config_provenance(config)
        or verified.get("run", {}).get("sha256") != sha256(run_path)
        or verified.get("summary") != artifact(summary_path)
    ):
        raise RuntimeError("Only a Passed final OOF verification can complete the OOF stage")
    paired_record = run.get("artifacts", {}).get("paired_oof_private")
    if not isinstance(paired_record, dict):
        raise ValueError("Completed OOF attempt is missing paired OOF provenance")
    require_record_within(
        paired_record, private_run_dir(config), exact_relative="paired-oof.npz"
    )
    if verified.get("paired_oof_private") != paired_record:
        raise RuntimeError("Final verifier is not bound to the current paired OOF artifact")
    completion = {
        "schema_version": "exp-oof-completion-v2",
        **identity_provenance(config),
        "status": "Complete",
        "completed_at_utc": utc_now(),
        "config": config_provenance(config),
        "artifacts": {
            "run": artifact(run_path),
            "summary": artifact(summary_path),
            "final_verification": artifact(verification_path),
            "paired_oof_private": paired_record,
        },
        "next_gate": "Seed-specific EXP-059 and identity-nested EXP-060 must pass before namespace selection.",
        "claim_boundary": "Completes one verified train-only paired OOF stage; this is not final pipeline selection.",
    }
    if public_sensitive_paths(completion):
        raise ValueError("OOF completion record contains row-level fields")
    create_json_once(completion_path, completion)
    assert_public_artifact_allowlist(config)
    return completion


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--stage", choices=("initialize", "m1", "m3", "assemble", "complete"), required=True)
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
    if config.get("_archive_only"):
        raise PermissionError("Sealed EXP-058 is archive-only; use its frozen sources for audit")
    if is_v2(config) and lexists(selection_record_path(config)):
        raise FileExistsError("A selected attempt blocks all later runner stages")
    if args.stage == "initialize":
        if args.fold is not None:
            raise ValueError("Initialize does not accept --fold")
        guard_initialize_invocation(config)
        try:
            result = initialize(config_path, config)
        except Exception as error:
            record_initialization_failure(config, error)
            raise
    elif args.stage == "complete":
        if args.fold is not None:
            raise ValueError("Complete does not accept --fold")
        result = complete_oof_attempt(config_path, config)
    elif args.stage == "assemble":
        if args.fold is not None:
            raise ValueError("Assemble does not accept --fold")
        guard_assembly_invocation(config)
        try:
            result = assemble(config)
        except Exception as error:
            record_assembly_failure(config, error)
            raise
    else:
        if args.fold not in range(5):
            raise ValueError("Model stages require --fold 0..4")
        guard_fold_invocation(config, args.stage, args.fold)
        if args.stage == "m3":
            with heavy_research_workload_mutex(config, args.fold) as lock_metadata:
                try:
                    result = run_m3_fold(config, args.fold, lock_metadata)
                except Exception as error:
                    record_failure(config, args.stage, args.fold, error)
                    raise
        else:
            try:
                result = run_m1_fold(config, args.fold)
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
