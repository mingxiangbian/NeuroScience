#!/usr/bin/env python3
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import gc
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import resource
import stat
import sys
import time
from typing import Any, Iterator, Sequence

import numpy as np


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
DEFAULT_CONFIG = MODULE_DIR / "configs" / "exp-069-representation-extraction-preflight.json"
QWEN3_SOURCE = Path(
    "/Users/phoenix/miniconda3/envs/phase-a-runtime/lib/python3.11/site-packages/mlx_lm/models/qwen3.py"
)
SCHEMA_VERSION = "exp-069-preflight-config-v1"
EXPERIMENT_ID = "EXP-069"
RUN_ID = "exp-069-representation-extraction-preflight"
SEEDS = (42, 43, 44)
FOLDS = (0, 1, 2, 3, 4)
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
POINTS = ("H-1", "H7", "H15", "H19", "H20", "H27", "H31", "H35", "HF")
POINT_KEYS = {
    "H-1": "h_minus_1",
    "H7": "h7",
    "H15": "h15",
    "H19": "h19",
    "H20": "h20",
    "H27": "h27",
    "H31": "h31",
    "H35": "h35",
    "HF": "hf",
}
PRE_LORA_POINTS = ("H-1", "H7", "H15", "H19")
EXPECTED_FOLD_COUNTS = {0: 8, 1: 6, 2: 5, 3: 7, 4: 6}
TARGET_MODULES = (
    "self_attn.q_proj",
    "self_attn.k_proj",
    "self_attn.v_proj",
    "self_attn.o_proj",
    "mlp.gate_proj",
    "mlp.up_proj",
    "mlp.down_proj",
)
PUBLIC_ALLOWLIST = {
    "static.json",
    "static-verification.json",
    "run-claim.json",
    "run.json",
    "verification.json",
    "preflight-complete.json",
}
PUBLIC_FORBIDDEN_KEYS = {
    "text",
    "texts",
    "sample_id",
    "sample_ids",
    "component_id",
    "component_ids",
    "ordinal",
    "ordinals",
    "gold",
    "labels",
    "logits",
    "token_ids",
    "hidden_states",
    "representations",
}


def _no_constant(value: str) -> Any:
    raise ValueError(f"Non-finite JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json_bytes(payload: bytes) -> Any:
    return json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_no_constant,
    )


def strict_json(path: Path) -> Any:
    return strict_json_bytes(path.read_bytes())


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def artifact(path: Path, *, logical_name: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "bytes": path.stat().st_size,
        "mode": file_mode(path),
        "sha256": sha256(path),
    }
    if logical_name is None:
        result["path"] = path.relative_to(PROJECT_ROOT).as_posix()
    else:
        result["logical_name"] = logical_name
    return result


def resolve_project(relative: str, *, must_exist: bool = True) -> Path:
    if type(relative) is not str or not relative:
        raise TypeError("Project path must be a non-empty string")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or pure.as_posix() != relative or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError(f"Unsafe project path: {relative}")
    candidate = PROJECT_ROOT.joinpath(*pure.parts)
    current = PROJECT_ROOT
    for part in pure.parts:
        current = current / part
        if os.path.lexists(current) and current.is_symlink():
            raise ValueError(f"Symlink path rejected: {relative}")
    if must_exist:
        if not candidate.is_file():
            raise FileNotFoundError(candidate)
        if candidate.stat().st_nlink != 1:
            raise ValueError(f"Hardlinked input rejected: {relative}")
    return candidate


def require_record(record: dict[str, Any]) -> Path:
    if set(record) != {"path", "bytes", "mode", "sha256"}:
        raise ValueError("Artifact record schema drift")
    path = resolve_project(record["path"])
    observed = artifact(path)
    if observed != record:
        raise ValueError(f"Artifact identity drift: {record['path']}")
    return path


def require_derived(record: dict[str, Any], *, expected_mode: str = "0600") -> Path:
    if set(record) != {"path", "bytes", "sha256"}:
        raise ValueError("Parent artifact record schema drift")
    path = resolve_project(record["path"])
    if path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
        raise ValueError(f"Parent artifact identity drift: {record['path']}")
    if file_mode(path) != expected_mode:
        raise PermissionError(f"Parent artifact mode drift: {record['path']}")
    return path


def create_json_once(path: Path, value: Any, *, private: bool = False) -> None:
    if os.path.lexists(path):
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    if private:
        os.chmod(path.parent, 0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600 if private else 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if private:
            os.chmod(path, 0o600)
        else:
            os.chmod(path, 0o644)


def save_npz_once(path: Path, **arrays: np.ndarray) -> None:
    if os.path.lexists(path):
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp.npz")
    if os.path.lexists(temporary):
        raise FileExistsError(temporary)
    try:
        np.savez(temporary, **arrays)
        os.chmod(temporary, 0o600)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.lexists(temporary):
            temporary.unlink()


def smoke_ordinals(rows: int = 3360, count: int = 32) -> list[int]:
    if rows != 3360 or count != 32:
        raise ValueError("EXP-069 smoke size is frozen")
    return [math.floor(index * (rows - 1) / (count - 1) + 0.5) for index in range(count)]


def validate_config(config: dict[str, Any]) -> None:
    expected = {
        "schema_version",
        "experiment_id",
        "run_id",
        "attempt_id",
        "rq_id",
        "tier",
        "registered_at",
        "authorization",
        "decision",
        "implementation",
        "environment",
        "data",
        "model",
        "m2_cache",
        "m3_lineage",
        "smoke",
        "access",
        "resources",
        "outputs",
        "claim_boundary",
    }
    if set(config) != expected:
        raise ValueError("EXP-069 config top-level schema drift")
    if config["schema_version"] != SCHEMA_VERSION or config["experiment_id"] != EXPERIMENT_ID:
        raise ValueError("EXP-069 config identity drift")
    if config["run_id"] != RUN_ID or config["attempt_id"] != "attempt-1" or config["rq_id"] != "RQ-S4":
        raise ValueError("EXP-069 run identity drift")
    authorization = config["authorization"]
    if set(authorization) != {
        "design_authorized",
        "static_execution_authorized",
        "smoke_execution_authorized",
        "model_loading_authorized",
        "forward_authorized",
        "training_authorized",
        "performance_metrics_authorized",
        "validation_access",
        "test_access",
    }:
        raise ValueError("EXP-069 authorization drift")
    if authorization["design_authorized"] is not True:
        raise ValueError("EXP-069 design authorization missing")
    if any(
        authorization[key] is not False
        for key in (
            "training_authorized",
            "performance_metrics_authorized",
            "validation_access",
            "test_access",
        )
    ):
        raise ValueError("EXP-069 forbidden authorization drift")
    static_execution = authorization["static_execution_authorized"]
    smoke_execution = authorization["smoke_execution_authorized"]
    if type(static_execution) is not bool or type(smoke_execution) is not bool:
        raise TypeError("EXP-069 stage authorizations must be boolean")
    if (
        authorization["model_loading_authorized"] is not smoke_execution
        or authorization["forward_authorized"] is not smoke_execution
    ):
        raise ValueError("EXP-069 smoke/model/forward authorization mismatch")
    smoke = config["smoke"]
    if smoke["ordinals"] != smoke_ordinals() or smoke["points"] != list(POINTS):
        raise ValueError("EXP-069 smoke identity drift")
    if smoke["fold_counts"] != [EXPECTED_FOLD_COUNTS[index] for index in FOLDS]:
        raise ValueError("EXP-069 fold-count drift")
    if smoke["label_order"] != list(LABEL_ORDER) or smoke["hidden_size"] != 2560:
        raise ValueError("EXP-069 label or hidden-size drift")
    tolerances = smoke["tolerances"]
    if set(tolerances) != {
        "rtol",
        "m2_hf_atol",
        "standard_hf_atol",
        "manual_logit_atol",
        "m3_logit_atol",
        "pre_lora_atol",
    } or any(float(value) < 0 for value in tolerances.values()):
        raise ValueError("EXP-069 tolerance schema drift")
    if float(tolerances["rtol"]) != 0.0 or any(
        float(tolerances[key]) != 1e-5 for key in tolerances if key != "rtol"
    ):
        raise ValueError("EXP-069 tolerance value drift")
    lineage = config["m3_lineage"]
    if [item["seed"] for item in lineage] != list(SEEDS):
        raise ValueError("EXP-069 seed lineage drift")
    outputs = config["outputs"]
    if set(outputs["public_allowlist"]) != PUBLIC_ALLOWLIST:
        raise ValueError("EXP-069 public allowlist drift")
    for key in ("public_root", "private_root", "heavy_lock"):
        resolve_project(outputs[key], must_exist=False)
    if config["access"]["historical_npz_members"] != ["sample_ids", "fold_ids", "logits"]:
        raise ValueError("EXP-069 historical NPZ allowlist drift")


def load_config(path: Path) -> dict[str, Any]:
    if path.resolve() != DEFAULT_CONFIG.resolve():
        raise PermissionError("EXP-069 requires the frozen default config")
    config = strict_json(path)
    if not isinstance(config, dict):
        raise TypeError("EXP-069 config must be an object")
    validate_config(config)
    return config


def public_root(config: dict[str, Any]) -> Path:
    return resolve_project(config["outputs"]["public_root"], must_exist=False)


def private_root(config: dict[str, Any]) -> Path:
    return resolve_project(config["outputs"]["private_root"], must_exist=False)


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in PUBLIC_FORBIDDEN_KEYS:
                found.append(f"{prefix}.{key}")
            found.extend(public_sensitive_paths(child, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    return found


def environment_identity() -> dict[str, Any]:
    packages = {}
    for name in ("numpy", "mlx", "mlx-lm", "safetensors", "tokenizers", "transformers"):
        packages[name.replace("-", "_")] = importlib.metadata.version(name)
    return {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "packages": packages,
        "qwen3_source": {
            "path": str(QWEN3_SOURCE),
            "bytes": QWEN3_SOURCE.stat().st_size,
            "mode": file_mode(QWEN3_SOURCE),
            "sha256": sha256(QWEN3_SOURCE),
        },
        "offline_environment": {
            key: os.environ.get(key)
            for key in (
                "PYTHONNOUSERSITE",
                "HF_HUB_OFFLINE",
                "TRANSFORMERS_OFFLINE",
                "TOKENIZERS_PARALLELISM",
                "OMP_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS",
            )
        },
    }


def require_environment(config: dict[str, Any]) -> None:
    if environment_identity() != config["environment"]:
        raise PermissionError("EXP-069 environment identity drift")


def require_implementation(config: dict[str, Any], config_path: Path) -> None:
    require_record(config["decision"])
    for record in config["implementation"].values():
        require_record(record)
    if config_path.resolve() != DEFAULT_CONFIG.resolve():
        raise PermissionError("EXP-069 config path drift")


def require_stage_authorized(config: dict[str, Any], stage: str) -> None:
    key = "static_execution_authorized" if stage == "static" else "smoke_execution_authorized"
    if config["authorization"][key] is not True:
        raise PermissionError(f"EXP-069 {stage} is not authorized by the frozen config")


def require_config_binding(config_path: Path, *records: dict[str, Any]) -> None:
    current = artifact(config_path)
    for record in records:
        if record != current:
            raise ValueError("EXP-069 config changed after static registration")


def load_fold_rows(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[int, int]]:
    manifest_path = require_record(config["data"]["fold_manifest_public"])
    ordinals = set(config["smoke"]["ordinals"])
    selected: list[dict[str, Any]] = []
    counts = {fold: 0 for fold in FOLDS}
    with manifest_path.open("r", encoding="utf-8") as handle:
        for ordinal, line in enumerate(handle):
            row = strict_json_bytes(line.encode("utf-8"))
            if ordinal not in ordinals:
                continue
            allowed = {"sample_id", "component_id", "fold_id"}
            if not allowed.issubset(row):
                raise ValueError("Fold manifest smoke schema drift")
            fold = int(row["fold_id"])
            if fold not in FOLDS:
                raise ValueError("Fold ID drift")
            selected.append(
                {
                    "ordinal": ordinal,
                    "sample_id": row["sample_id"],
                    "component_id": row["component_id"],
                    "fold_id": fold,
                }
            )
            counts[fold] += 1
    if [row["ordinal"] for row in selected] != config["smoke"]["ordinals"]:
        raise ValueError("Smoke ordinal alignment drift")
    if counts != EXPECTED_FOLD_COUNTS:
        raise ValueError("Smoke fold coverage drift")
    if len({row["sample_id"] for row in selected}) != 32:
        raise ValueError("Smoke sample identity collision")
    return selected, counts


def require_parent_verification(path: Path, *, expected_checks: int) -> dict[str, Any]:
    value = strict_json(path)
    if value.get("status") != "Passed" or value.get("failed_count", 0) != 0:
        raise ValueError(f"Parent verification is not Passed: {path}")
    if value.get("check_count") != expected_checks:
        raise ValueError(f"Parent verification count drift: {path}")
    return value


def adapter_inventory(path: Path) -> dict[str, Any]:
    from safetensors import safe_open

    names: list[str] = []
    parameters = 0
    layers: set[int] = set()
    modules: set[str] = set()
    with safe_open(path, framework="numpy") as handle:
        for name in handle.keys():
            tensor = handle.get_tensor(name)
            names.append(name)
            parameters += int(tensor.size)
            match = re.fullmatch(r"model\.layers\.(\d+)\.(.+)\.lora_([ab])", name)
            if not match:
                raise ValueError(f"Unexpected adapter tensor: {name}")
            layers.add(int(match.group(1)))
            modules.add(match.group(2))
            if match.group(3) == "a" and tensor.shape[-1] != 8:
                raise ValueError("LoRA-A rank drift")
            if match.group(3) == "b" and tensor.shape[0] != 8:
                raise ValueError("LoRA-B rank drift")
    if len(names) != 224 or parameters != 7_340_032:
        raise ValueError("Adapter tensor inventory drift")
    if layers != set(range(20, 36)) or modules != set(TARGET_MODULES):
        raise ValueError("Adapter layer/module inventory drift")
    return {"tensor_count": len(names), "parameter_count": parameters}


def head_inventory(path: Path) -> dict[str, Any]:
    from safetensors.numpy import load_file

    values = load_file(str(path))
    if set(values) != {"weight", "bias"}:
        raise ValueError("M3 head tensor keys drift")
    if values["weight"].shape != (6, 2560) or values["bias"].shape != (6,):
        raise ValueError("M3 head tensor shape drift")
    return {"keys": ["bias", "weight"], "weight_shape": [6, 2560], "bias_shape": [6]}


def heldout_inventory(path: Path, fold: int) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as archive:
        required = {"sample_ids", "fold_ids", "logits"}
        if not required.issubset(archive.files):
            raise ValueError("Heldout logit member drift")
        sample_ids = archive["sample_ids"]
        fold_ids = archive["fold_ids"]
        logits = archive["logits"]
        if sample_ids.shape != (672,) or fold_ids.shape != (672,) or logits.shape != (672, 6):
            raise ValueError("Heldout logit shape drift")
        if logits.dtype.str != "<f4" or not np.isfinite(logits).all():
            raise ValueError("Heldout logit dtype/value drift")
        if set(int(value) for value in np.unique(fold_ids)) != {fold}:
            raise ValueError("Heldout logit fold drift")
    return {"rows": 672, "members_read": ["sample_ids", "fold_ids", "logits"]}


def fold_source_manifest(config: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for lineage in config["m3_lineage"]:
        seed = int(lineage["seed"])
        for record in lineage["aggregate_records"]:
            require_record(record)
        for fold in FOLDS:
            run_path = resolve_project(lineage["run_template"].format(fold=fold))
            verification_path = resolve_project(lineage["verification_template"].format(fold=fold))
            run = strict_json(run_path)
            if run.get("family") != "m3" or run.get("fold_id") != fold:
                raise ValueError("M3 fold run identity drift")
            if run.get("status") != "CompletedAwaitingVerification":
                raise ValueError("M3 fold run status drift")
            observed_seed = run.get("model_seed")
            if seed == 42:
                if observed_seed not in (None, 42):
                    raise ValueError("Seed-42 fold identity drift")
            elif observed_seed != seed:
                raise ValueError("M3 fold seed drift")
            require_parent_verification(
                verification_path, expected_checks=int(lineage["fold_verification_checks"])
            )
            artifacts = run.get("artifacts", {})
            adapter_path = require_derived(artifacts["adapter_private"])
            head_path = require_derived(artifacts["head_private"])
            logits_path = require_derived(artifacts["heldout_logit_table_private"])
            evidence_path = require_derived(artifacts["evidence_private"])
            provenance_record = artifacts.get("checkpoint_provenance_private")
            provenance = require_derived(provenance_record) if provenance_record is not None else None
            if seed == 42 and provenance is not None:
                raise ValueError("Seed-42 must not manufacture checkpoint provenance")
            if seed in (43, 44) and provenance is None:
                raise ValueError("Prospective seed checkpoint provenance missing")
            entries.append(
                {
                    "seed": seed,
                    "fold": fold,
                    "run": artifact(run_path),
                    "verification": artifact(verification_path),
                    "adapter": artifact(adapter_path),
                    "head": artifact(head_path),
                    "heldout_logits": artifact(logits_path),
                    "evidence": artifact(evidence_path),
                    "checkpoint_provenance": artifact(provenance) if provenance is not None else None,
                    "adapter_inventory": adapter_inventory(adapter_path),
                    "head_inventory": head_inventory(head_path),
                    "heldout_inventory": heldout_inventory(logits_path, fold),
                }
            )
    if [(item["seed"], item["fold"]) for item in entries] != [
        (seed, fold) for seed in SEEDS for fold in FOLDS
    ]:
        raise ValueError("M3 source coverage drift")
    return entries


def static_stage(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    require_environment(config)
    require_implementation(config, config_path)
    root_public = public_root(config)
    root_private = private_root(config)
    if os.path.lexists(root_public) or os.path.lexists(root_private):
        raise FileExistsError("EXP-069 output root already exists")
    for record in (
        config["data"]["task_manifest"],
        config["data"]["train"],
        config["data"]["fold_manifest_public"],
        config["data"]["fold_manifest_private"],
        config["data"]["fold_verification"],
        config["model"]["shared_config"],
        config["model"]["qwen_manifest"],
        config["model"]["prompt"],
        config["m2_cache"]["gate_config"],
        config["m2_cache"]["gate_run"],
        config["m2_cache"]["gate_verification"],
        config["m2_cache"]["metadata"],
        config["m2_cache"]["features"],
    ):
        require_record(record)
    fold_verification = strict_json(require_record(config["data"]["fold_verification"]))
    if fold_verification.get("status") != "Passed" or fold_verification.get("failed_count", 0) != 0:
        raise ValueError("Fold manifest verification is not Passed")
    cache_verification = strict_json(require_record(config["m2_cache"]["gate_verification"]))
    if cache_verification.get("status") != "Passed" or cache_verification.get("check_count") != 74:
        raise ValueError("M2 cache gate verification drift")
    cache_path = require_record(config["m2_cache"]["features"])
    cache = np.load(cache_path, mmap_mode="r", allow_pickle=False)
    if list(cache.shape) != config["m2_cache"]["shape"] or cache.dtype.str != "<f4":
        raise ValueError("M2 train cache shape/dtype drift")
    selected, fold_counts = load_fold_rows(config)
    m3_sources = fold_source_manifest(config)
    root_private.mkdir(parents=True, mode=0o700)
    os.chmod(root_private, 0o700)
    root_public.mkdir(parents=True, mode=0o755)
    input_manifest = {
        "schema_version": "exp-069-input-manifest-v1",
        "experiment_id": EXPERIMENT_ID,
        "attempt_id": config["attempt_id"],
        "config": artifact(config_path),
        "rows": selected,
        "fold_counts": {str(key): value for key, value in fold_counts.items()},
        "m3_sources": m3_sources,
        "access": {
            "fold_manifest_public_accessed": True,
            "fold_manifest_private_parsed": False,
            "fold_manifest_label_values_read": False,
            "train_text_accessed": False,
            "m2_feature_values_read": False,
            "heldout_members_read": ["sample_ids", "fold_ids", "logits"],
            "heldout_gold_read": False,
            "validation_accessed": False,
            "test_accessed": False,
            "model_loaded": False,
            "forward_executed": False,
        },
    }
    manifest_path = root_private / "input-manifest.json"
    create_json_once(manifest_path, input_manifest, private=True)
    report = {
        "schema_version": "exp-069-static-run-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": config["attempt_id"],
        "stage": "static",
        "status": "CompletedAwaitingVerification",
        "counts": {"rows": 32, "seeds": 3, "folds_per_seed": 5, "checkpoints": 15},
        "points": list(POINTS),
        "input_manifest": artifact(manifest_path, logical_name="input-manifest.json"),
        "access": input_manifest["access"],
        "claim_boundary": config["claim_boundary"],
    }
    if public_sensitive_paths(report):
        raise ValueError("Static public privacy scan failed")
    create_json_once(root_public / "static.json", report)
    return report


def require_static_pass(
    config_path: Path, config: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    require_environment(config)
    require_implementation(config, config_path)
    root_public = public_root(config)
    root_private = private_root(config)
    static = strict_json(root_public / "static.json")
    verification = strict_json(root_public / "static-verification.json")
    if static.get("status") != "CompletedAwaitingVerification":
        raise ValueError("Static run state drift")
    if verification.get("status") != "Passed" or verification.get("failed_count") != 0:
        raise ValueError("Static verification is not Passed")
    manifest = strict_json(root_private / "input-manifest.json")
    require_config_binding(config_path, manifest["config"], verification["config"])
    if artifact(root_private / "input-manifest.json", logical_name="input-manifest.json") != static["input_manifest"]:
        raise ValueError("Static input-manifest identity drift")
    return static, manifest


def load_selected_train_rows(config: dict[str, Any], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    train_path = require_record(config["data"]["train"])
    wanted = {int(row["ordinal"]): row for row in manifest["rows"]}
    selected: list[dict[str, Any]] = []
    with train_path.open("r", encoding="utf-8") as handle:
        for ordinal, line in enumerate(handle):
            if ordinal not in wanted:
                continue
            row = strict_json_bytes(line.encode("utf-8"))
            expected = wanted[ordinal]
            if row.get("sample_id") != expected["sample_id"] or row.get("component_id") != expected["component_id"]:
                raise ValueError("Train/fold-manifest identity drift")
            selected.append(
                {
                    "ordinal": ordinal,
                    "sample_id": row["sample_id"],
                    "component_id": row["component_id"],
                    "fold_id": int(expected["fold_id"]),
                    "text": row["text"],
                }
            )
    if [row["ordinal"] for row in selected] != config["smoke"]["ordinals"]:
        raise ValueError("Train smoke order drift")
    return selected


def qwen_prompt_ids(tokenizer: Any, prompt: dict[str, Any], text: str, limit: int) -> tuple[list[int], int, bool]:
    def apply(value: str) -> list[int]:
        output = tokenizer.apply_chat_template(
            [
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user_prefix"] + value + prompt["user_suffix"]},
            ],
            tokenize=True,
            return_dict=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        if not isinstance(output, list) or any(type(token) is not int for token in output):
            raise TypeError("Tokenizer must return plain integer IDs")
        return output

    full = apply(text)
    raw_length = len(full)
    if raw_length <= limit:
        selected, truncated = full, False
    else:
        target_ids = tokenizer.encode(text, add_special_tokens=False)
        low, high, selected = 0, len(target_ids), apply("")
        while low <= high:
            middle = (low + high) // 2
            candidate = apply(tokenizer.decode(target_ids[:middle], skip_special_tokens=False))
            if len(candidate) <= limit:
                selected, low = candidate, middle + 1
            else:
                high = middle - 1
        truncated = True
    if not selected or len(selected) > limit:
        raise ValueError("Frozen Qwen length contract failed")
    if not tokenizer.decode(selected).endswith("<think>\n\n</think>\n\n"):
        raise ValueError("Qwen empty-think suffix drift")
    return selected, raw_length, truncated


def manual_residual_points(backbone: Any, input_ids: Any, create_attention_mask: Any) -> tuple[dict[str, Any], Any]:
    core = backbone.model
    if len(core.layers) != 36:
        raise ValueError("Qwen block-count drift")
    hidden = core.embed_tokens(input_ids)
    mask = create_attention_mask(hidden, None)
    points: dict[str, Any] = {"H-1": hidden[:, -1, :]}
    wanted = {7, 15, 19, 20, 27, 31, 35}
    for index, block in enumerate(core.layers):
        hidden = block(hidden, mask, None)
        if index in wanted:
            points[f"H{index}"] = hidden[:, -1, :]
    normalized = core.norm(hidden)
    points["HF"] = normalized[:, -1, :]
    standard_hf = core(input_ids)[:, -1, :]
    if tuple(points) != POINTS:
        raise ValueError("Representation point order drift")
    return points, standard_hf


def max_abs(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape:
        raise ValueError("Comparison shape drift")
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("Non-finite comparison")
    return float(np.max(np.abs(left.astype(np.float64) - right.astype(np.float64)), initial=0.0))


def token_stream_digest(rows: Sequence[tuple[int, Sequence[int]]]) -> str:
    digest = hashlib.sha256()
    for ordinal, ids in rows:
        values = np.asarray(ids, dtype="<i4")
        digest.update(int(ordinal).to_bytes(8, "little", signed=False))
        digest.update(len(ids).to_bytes(4, "little", signed=False))
        digest.update(values.tobytes(order="C"))
    return digest.hexdigest()


def peak_memory_gb() -> float:
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1e9


@contextmanager
def heavy_mutex(config: dict[str, Any]) -> Iterator[None]:
    path = resolve_project(config["outputs"]["heavy_lock"], must_exist=False)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Another heavy research workload is active") from error
        os.fchmod(descriptor, 0o600)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def create_claim(config_path: Path, config: dict[str, Any]) -> None:
    path = public_root(config) / "run-claim.json"
    if path.exists():
        return
    claim = {
        "schema_version": "exp-069-run-claim-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": config["attempt_id"],
        "status": "Claimed",
        "config": artifact(config_path),
        "workers": 16,
        "model_loading_authorized": config["authorization"]["model_loading_authorized"],
        "smoke_execution_authorized": config["authorization"]["smoke_execution_authorized"],
        "claim_boundary": config["claim_boundary"],
    }
    create_json_once(path, claim)


def base_stage(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    require_environment(config)
    _, manifest = require_static_pass(config_path, config)
    create_claim(config_path, config)
    root = private_root(config)
    output = root / "base.npz"
    worker_path = root / "base-worker.json"
    if os.path.lexists(output) or os.path.lexists(worker_path):
        raise FileExistsError("Base worker output exists")
    rows = load_selected_train_rows(config, manifest)
    prompt = strict_json(require_record(config["model"]["prompt"]))
    cache = np.load(require_record(config["m2_cache"]["features"]), mmap_mode="r", allow_pickle=False)
    started = time.perf_counter()
    with heavy_mutex(config):
        import mlx.core as mx
        from mlx_lm import load
        from mlx_lm.models.base import create_attention_mask

        mx.reset_peak_memory()
        model, tokenizer = load(str(resolve_project(config["model"]["base_path"])), lazy=False)
        model.freeze()
        model.eval()
        arrays: dict[str, list[np.ndarray]] = {POINT_KEYS[name]: [] for name in POINTS}
        standard_values: list[np.ndarray] = []
        tokens: list[tuple[int, list[int]]] = []
        standard_error = 0.0
        lengths: list[int] = []
        for row in rows:
            ids, _, _ = qwen_prompt_ids(tokenizer, prompt, row["text"], 384)
            values, standard = manual_residual_points(model, mx.array([ids], dtype=mx.int32), create_attention_mask)
            mx.eval(*values.values(), standard)
            converted = {name: np.asarray(value.astype(mx.float32), dtype=np.float32) for name, value in values.items()}
            standard_array = np.asarray(standard.astype(mx.float32), dtype=np.float32)
            standard_error = max(standard_error, max_abs(converted["HF"], standard_array))
            for name in POINTS:
                arrays[POINT_KEYS[name]].append(converted[name][0])
            standard_values.append(standard_array[0])
            tokens.append((row["ordinal"], ids))
            lengths.append(len(ids))
            if time.perf_counter() - started > float(config["resources"]["worker_wall_minutes"]) * 60:
                raise TimeoutError("Base worker exceeded wall-time budget")
            if float(mx.get_peak_memory()) / 1e9 > float(config["resources"]["worker_peak_mlx_gb"]):
                raise MemoryError("Base worker exceeded MLX memory budget")
        stacked = {key: np.asarray(value, dtype=np.float32) for key, value in arrays.items()}
        standard_hf = np.asarray(standard_values, dtype=np.float32)
        ordinals = np.asarray([row["ordinal"] for row in rows], dtype=np.int32)
        fold_ids = np.asarray([row["fold_id"] for row in rows], dtype=np.int8)
        token_lengths = np.asarray(lengths, dtype=np.int16)
        cache_error = max_abs(stacked["hf"], np.asarray(cache[ordinals], dtype=np.float32))
        tolerances = config["smoke"]["tolerances"]
        if standard_error > tolerances["standard_hf_atol"] or cache_error > tolerances["m2_hf_atol"]:
            raise ValueError("Base representation parity gate failed")
        save_npz_once(
            output,
            ordinal=ordinals,
            fold_id=fold_ids,
            token_length=token_lengths,
            standard_hf=standard_hf,
            **stacked,
        )
        resources = {
            "elapsed_seconds": time.perf_counter() - started,
            "mlx_peak_bytes": int(mx.get_peak_memory()),
            "ru_maxrss_gb": peak_memory_gb(),
        }
        del model, tokenizer
        mx.clear_cache()
    worker = {
        "schema_version": "exp-069-base-worker-v1",
        "experiment_id": EXPERIMENT_ID,
        "stage": "base-smoke",
        "status": "Completed",
        "rows": 32,
        "token_stream_sha256": token_stream_digest(tokens),
        "fold_token_stream_sha256": {
            str(fold): token_stream_digest(
                [
                    token_row
                    for token_row, source_row in zip(tokens, rows)
                    if int(source_row["fold_id"]) == fold
                ]
            )
            for fold in FOLDS
        },
        "max_errors": {"m2_hf": cache_error, "standard_hf": standard_error},
        "output": artifact(output, logical_name="base.npz"),
        "resources": resources,
        "access": {
            "train_label_bearing_container_accessed": True,
            "train_text_accessed": True,
            "train_label_values_used": False,
            "train_label_values_persisted": False,
            "m2_feature_rows_read": 32,
            "validation_accessed": False,
            "test_accessed": False,
            "model_loaded": True,
            "forward_executed": True,
            "performance_metrics_computed": False,
        },
    }
    create_json_once(worker_path, worker, private=True)
    return worker


def source_for(manifest: dict[str, Any], seed: int, fold: int) -> dict[str, Any]:
    matches = [item for item in manifest["m3_sources"] if item["seed"] == seed and item["fold"] == fold]
    if len(matches) != 1:
        raise ValueError("M3 source lookup drift")
    return matches[0]


def lora_identity(model: Any) -> list[tuple[int, str]]:
    observed: list[tuple[int, str]] = []
    for name, module in model.named_modules():
        if type(module).__name__ != "LoRALinear":
            continue
        match = re.search(r"(?:^|\.)layers\.(\d+)\.(.+)$", name)
        if not match:
            raise ValueError("Unexpected runtime LoRA path")
        if float(module.scale) != 20.0 or float(module.dropout._p_1) != 1.0:
            raise ValueError("Runtime LoRA scale/dropout drift")
        if int(module.lora_a.shape[-1]) != 8 or int(module.lora_b.shape[0]) != 8:
            raise ValueError("Runtime LoRA rank drift")
        observed.append((int(match.group(1)), match.group(2)))
    expected = [(block, module) for block in range(20, 36) for module in TARGET_MODULES]
    if sorted(observed) != sorted(expected):
        raise ValueError("Runtime LoRA insertion drift")
    return observed


def fold_stage(config_path: Path, config: dict[str, Any], seed: int, fold: int) -> dict[str, Any]:
    if seed not in SEEDS or fold not in FOLDS:
        raise ValueError("Invalid EXP-069 seed/fold")
    require_environment(config)
    _, manifest = require_static_pass(config_path, config)
    create_claim(config_path, config)
    base_worker_path = private_root(config) / "base-worker.json"
    base_output_path = private_root(config) / "base.npz"
    base_worker = strict_json(base_worker_path)
    if base_worker.get("status") != "Completed" or base_worker["output"] != artifact(
        base_output_path, logical_name="base.npz"
    ):
        raise ValueError("Base worker prerequisite drift")
    output_dir = private_root(config) / f"seed-{seed}"
    output_path = output_dir / f"fold-{fold}.npz"
    worker_path = output_dir / f"fold-{fold}.json"
    if os.path.lexists(output_path) or os.path.lexists(worker_path):
        raise FileExistsError("Fold worker output exists")
    rows = [row for row in load_selected_train_rows(config, manifest) if row["fold_id"] == fold]
    if len(rows) != EXPECTED_FOLD_COUNTS[fold]:
        raise ValueError("Fold worker row count drift")
    source = source_for(manifest, seed, fold)
    adapter_path = resolve_project(source["adapter"]["path"])
    head_path = resolve_project(source["head"]["path"])
    heldout_path = resolve_project(source["heldout_logits"]["path"])
    before = {name: artifact(path) for name, path in {"adapter": adapter_path, "head": head_path, "heldout": heldout_path}.items()}
    with np.load(base_output_path, allow_pickle=False) as base_archive:
        base_ordinals = base_archive["ordinal"]
        base_points = {name: base_archive[POINT_KEYS[name]] for name in PRE_LORA_POINTS}
    base_index = {int(value): index for index, value in enumerate(base_ordinals)}
    with np.load(heldout_path, allow_pickle=False) as archive:
        historical_ids = archive["sample_ids"]
        historical_folds = archive["fold_ids"]
        historical_logits = archive["logits"]
    historical_index = {str(value): index for index, value in enumerate(historical_ids)}
    prompt = strict_json(require_record(config["model"]["prompt"]))
    started = time.perf_counter()
    with heavy_mutex(config):
        import mlx.core as mx
        import mlx.nn as nn
        from mlx_lm import load
        from mlx_lm.models.base import create_attention_mask
        from mlx_lm.tuner import linear_to_lora_layers
        from mlx.utils import tree_flatten
        from safetensors.numpy import load_file as load_safetensors

        mx.reset_peak_memory()
        model, tokenizer = load(str(resolve_project(config["model"]["base_path"])), lazy=False)
        model.freeze()
        model.eval()
        mx.random.seed(seed)
        head = nn.Linear(2560, 6, bias=True)
        mx.random.seed(seed + 100000)
        linear_to_lora_layers(
            model,
            16,
            {"rank": 8, "scale": 20.0, "dropout": 0.0, "keys": list(TARGET_MODULES)},
        )
        lora_identity(model)
        adapter_arrays = load_safetensors(str(adapter_path))
        head_arrays = load_safetensors(str(head_path))
        if set(head_arrays) != {"weight", "bias"}:
            raise ValueError("Fold head key drift")
        if head_arrays["weight"].shape != (6, 2560) or head_arrays["bias"].shape != (6,):
            raise ValueError("Fold head shape drift")
        model.load_weights(str(adapter_path), strict=False)
        head.load_weights(str(head_path), strict=True)
        model.eval()
        runtime_arrays = dict(tree_flatten(model.trainable_parameters()))
        if set(runtime_arrays) != set(adapter_arrays):
            raise ValueError("Runtime adapter key coverage drift")
        adapter_load_error = 0.0
        for name, expected in adapter_arrays.items():
            observed = np.asarray(runtime_arrays[name].astype(mx.float32), dtype=np.float32)
            adapter_load_error = max(adapter_load_error, max_abs(observed, expected.astype(np.float32)))
        if adapter_load_error != 0.0:
            raise ValueError("Runtime adapter tensor load drift")
        head_values = [value for _, value in tree_flatten(head.trainable_parameters())]
        mx.eval(*runtime_arrays.values(), *head_values)
        arrays: dict[str, list[np.ndarray]] = {POINT_KEYS[name]: [] for name in POINTS}
        standard_hf_values: list[np.ndarray] = []
        manual_logits_values: list[np.ndarray] = []
        standard_logits_values: list[np.ndarray] = []
        reference_logits_values: list[np.ndarray] = []
        tokens: list[tuple[int, list[int]]] = []
        lengths: list[int] = []
        errors = {"standard_hf": 0.0, "manual_logit": 0.0, "m3_logit": 0.0, "pre_lora": 0.0}
        for row in rows:
            ids, _, _ = qwen_prompt_ids(tokenizer, prompt, row["text"], 384)
            input_ids = mx.array([ids], dtype=mx.int32)
            points, standard_hf = manual_residual_points(model, input_ids, create_attention_mask)
            manual_logits = head(points["HF"].astype(head.weight.dtype)).astype(mx.float32)
            standard_hidden = model.model(input_ids)
            standard_logits = head(standard_hidden[:, -1, :].astype(head.weight.dtype)).astype(mx.float32)
            mx.eval(*points.values(), standard_hf, manual_logits, standard_logits)
            converted = {name: np.asarray(value.astype(mx.float32), dtype=np.float32) for name, value in points.items()}
            standard_hf_array = np.asarray(standard_hf.astype(mx.float32), dtype=np.float32)
            manual_logits_array = np.asarray(manual_logits, dtype=np.float32)
            standard_logits_array = np.asarray(standard_logits, dtype=np.float32)
            reference_index = historical_index.get(row["sample_id"])
            if reference_index is None or int(historical_folds[reference_index]) != fold:
                raise ValueError("Historical heldout row alignment drift")
            reference_logits_array = np.asarray(historical_logits[reference_index : reference_index + 1], dtype=np.float32)
            errors["standard_hf"] = max(errors["standard_hf"], max_abs(converted["HF"], standard_hf_array))
            errors["manual_logit"] = max(errors["manual_logit"], max_abs(manual_logits_array, standard_logits_array))
            errors["m3_logit"] = max(errors["m3_logit"], max_abs(standard_logits_array, reference_logits_array))
            base_position = base_index[row["ordinal"]]
            for point in PRE_LORA_POINTS:
                errors["pre_lora"] = max(
                    errors["pre_lora"], max_abs(converted[point][0], base_points[point][base_position])
                )
            for name in POINTS:
                arrays[POINT_KEYS[name]].append(converted[name][0])
            standard_hf_values.append(standard_hf_array[0])
            manual_logits_values.append(manual_logits_array[0])
            standard_logits_values.append(standard_logits_array[0])
            reference_logits_values.append(reference_logits_array[0])
            tokens.append((row["ordinal"], ids))
            lengths.append(len(ids))
            if time.perf_counter() - started > float(config["resources"]["worker_wall_minutes"]) * 60:
                raise TimeoutError("Fold worker exceeded wall-time budget")
            if float(mx.get_peak_memory()) / 1e9 > float(config["resources"]["worker_peak_mlx_gb"]):
                raise MemoryError("Fold worker exceeded MLX memory budget")
        limits = config["smoke"]["tolerances"]
        if (
            errors["standard_hf"] > limits["standard_hf_atol"]
            or errors["manual_logit"] > limits["manual_logit_atol"]
            or errors["m3_logit"] > limits["m3_logit_atol"]
            or errors["pre_lora"] > limits["pre_lora_atol"]
        ):
            raise ValueError("Fold parity gate failed")
        save_npz_once(
            output_path,
            ordinal=np.asarray([row["ordinal"] for row in rows], dtype=np.int32),
            fold_id=np.full(len(rows), fold, dtype=np.int8),
            token_length=np.asarray(lengths, dtype=np.int16),
            standard_hf=np.asarray(standard_hf_values, dtype=np.float32),
            manual_logits=np.asarray(manual_logits_values, dtype=np.float32),
            standard_logits=np.asarray(standard_logits_values, dtype=np.float32),
            reference_logits=np.asarray(reference_logits_values, dtype=np.float32),
            **{key: np.asarray(value, dtype=np.float32) for key, value in arrays.items()},
        )
        resources = {
            "elapsed_seconds": time.perf_counter() - started,
            "mlx_peak_bytes": int(mx.get_peak_memory()),
            "ru_maxrss_gb": peak_memory_gb(),
        }
        del model, tokenizer, head
        mx.clear_cache()
    after = {name: artifact(path) for name, path in {"adapter": adapter_path, "head": head_path, "heldout": heldout_path}.items()}
    if before != after:
        raise ValueError("Checkpoint identity changed during fold smoke")
    worker = {
        "schema_version": "exp-069-fold-worker-v1",
        "experiment_id": EXPERIMENT_ID,
        "stage": "fold-smoke",
        "status": "Completed",
        "seed": seed,
        "fold": fold,
        "rows": len(rows),
        "token_stream_sha256": token_stream_digest(tokens),
        "adapter_load_max_abs_error": adapter_load_error,
        "max_errors": errors,
        "output": artifact(output_path, logical_name=f"seed-{seed}/fold-{fold}.npz"),
        "source_before": before,
        "source_after": after,
        "resources": resources,
        "access": {
            "train_label_bearing_container_accessed": True,
            "train_text_accessed": True,
            "train_label_values_used": False,
            "train_label_values_persisted": False,
            "heldout_members_read": ["sample_ids", "fold_ids", "logits"],
            "heldout_gold_read": False,
            "validation_accessed": False,
            "test_accessed": False,
            "model_loaded": True,
            "forward_executed": True,
            "performance_metrics_computed": False,
        },
    }
    if worker["token_stream_sha256"] != base_worker["fold_token_stream_sha256"][str(fold)]:
        raise ValueError("Base/M3 token stream drift")
    create_json_once(worker_path, worker, private=True)
    return worker


def assemble_stage(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    require_environment(config)
    _, manifest = require_static_pass(config_path, config)
    create_claim(config_path, config)
    root = private_root(config)
    base_worker = strict_json(root / "base-worker.json")
    workers: list[dict[str, Any]] = []
    for seed in SEEDS:
        for fold in FOLDS:
            worker = strict_json(root / f"seed-{seed}" / f"fold-{fold}.json")
            if worker.get("status") != "Completed" or worker.get("seed") != seed or worker.get("fold") != fold:
                raise ValueError("Fold worker terminal drift")
            output_path = root / f"seed-{seed}" / f"fold-{fold}.npz"
            if worker["output"] != artifact(output_path, logical_name=f"seed-{seed}/fold-{fold}.npz"):
                raise ValueError("Fold worker artifact drift")
            workers.append(worker)
    if sum(worker["rows"] for worker in workers) != 96:
        raise ValueError("EXP-069 fold-worker coverage drift")
    max_errors = {
        "m2_hf": float(base_worker["max_errors"]["m2_hf"]),
        "standard_hf": max(
            [float(base_worker["max_errors"]["standard_hf"])]
            + [float(worker["max_errors"]["standard_hf"]) for worker in workers]
        ),
        "manual_logit": max(float(worker["max_errors"]["manual_logit"]) for worker in workers),
        "m3_logit": max(float(worker["max_errors"]["m3_logit"]) for worker in workers),
        "pre_lora": max(float(worker["max_errors"]["pre_lora"]) for worker in workers),
    }
    private_manifest = {
        "schema_version": "exp-069-smoke-manifest-v1",
        "experiment_id": EXPERIMENT_ID,
        "attempt_id": config["attempt_id"],
        "config": artifact(config_path),
        "input_manifest": artifact(root / "input-manifest.json", logical_name="input-manifest.json"),
        "base_worker": base_worker,
        "fold_workers": workers,
        "coverage": {"base_rows": 32, "seed_fold_rows": 96, "seeds": 3, "folds": 5},
        "max_errors": max_errors,
        "access": {
            "train_only": True,
            "validation_accessed": False,
            "test_accessed": False,
            "performance_metrics_computed": False,
        },
    }
    private_manifest_path = root / "smoke-manifest.json"
    create_json_once(private_manifest_path, private_manifest, private=True)
    run = {
        "schema_version": "exp-069-run-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": config["attempt_id"],
        "stage": "representation-extraction-preflight",
        "status": "CompletedAwaitingVerification",
        "counts": {"smoke_rows": 32, "seeds": 3, "folds": 5, "model_workers": 16},
        "points": list(POINTS),
        "max_errors": max_errors,
        "resources": {
            "total_elapsed_seconds": float(base_worker["resources"]["elapsed_seconds"])
            + sum(float(worker["resources"]["elapsed_seconds"]) for worker in workers),
            "maximum_mlx_peak_bytes": max(
                [int(base_worker["resources"]["mlx_peak_bytes"])]
                + [int(worker["resources"]["mlx_peak_bytes"]) for worker in workers]
            ),
        },
        "private_manifest": artifact(private_manifest_path, logical_name="smoke-manifest.json"),
        "access": private_manifest["access"],
        "claim_boundary": config["claim_boundary"],
    }
    if public_sensitive_paths(run):
        raise ValueError("EXP-069 public privacy scan failed")
    create_json_once(public_root(config) / "run.json", run)
    return run


def record_failure(config: dict[str, Any], stage: str, error: BaseException) -> None:
    try:
        root = public_root(config)
        root.mkdir(parents=True, exist_ok=True, mode=0o755)
        target = root / ("static.json" if stage == "static" else "run.json")
        if os.path.lexists(target):
            return
        value = {
            "schema_version": "exp-069-failure-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "attempt_id": config.get("attempt_id"),
            "stage": stage,
            "status": "Failed",
            "error_type": type(error).__name__,
            "claim_boundary": config.get("claim_boundary"),
        }
        create_json_once(target, value)
    except Exception:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the frozen EXP-069 preflight stages")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--stage", required=True, choices=("static", "base-smoke", "fold-smoke", "assemble"))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--fold", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config: dict[str, Any] = {}
    try:
        config = load_config(args.config)
        require_stage_authorized(config, args.stage)
        if args.stage == "static":
            result = static_stage(args.config, config)
        elif args.stage == "base-smoke":
            if args.seed is not None or args.fold is not None:
                raise ValueError("Base smoke does not take seed/fold")
            result = base_stage(args.config, config)
        elif args.stage == "fold-smoke":
            if args.seed is None or args.fold is None:
                raise ValueError("Fold smoke requires seed and fold")
            result = fold_stage(args.config, config, args.seed, args.fold)
        else:
            if args.seed is not None or args.fold is not None:
                raise ValueError("Assemble does not take seed/fold")
            result = assemble_stage(args.config, config)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except BaseException as error:
        authorization_key = (
            "static_execution_authorized" if args.stage == "static" else "smoke_execution_authorized"
        )
        unauthorized = (
            isinstance(config, dict)
            and bool(config)
            and config.get("authorization", {}).get(authorization_key) is not True
        )
        if isinstance(config, dict) and config and not unauthorized:
            record_failure(config, args.stage, error)
        raise


if __name__ == "__main__":
    main()
