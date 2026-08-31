#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import struct
import sys
from typing import Any
import zipfile

import numpy as np


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
DEFAULT_CONFIG = MODULE_DIR / "configs" / "exp-069-representation-extraction-preflight.json"
EXPERIMENT_ID = "EXP-069"
RUN_ID = "exp-069-representation-extraction-preflight"
SEEDS = (42, 43, 44)
FOLDS = (0, 1, 2, 3, 4)
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
ORDINALS = (
    0,
    108,
    217,
    325,
    433,
    542,
    650,
    758,
    867,
    975,
    1084,
    1192,
    1300,
    1409,
    1517,
    1625,
    1734,
    1842,
    1950,
    2059,
    2167,
    2275,
    2384,
    2492,
    2601,
    2709,
    2817,
    2926,
    3034,
    3142,
    3251,
    3359,
)
FOLD_COUNTS = {0: 8, 1: 6, 2: 5, 3: 7, 4: 6}
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


def resolve_project(relative: str, *, must_exist: bool = True) -> Path:
    if type(relative) is not str or not relative:
        raise TypeError("Project path must be non-empty")
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


def observed_artifact(path: Path, *, logical_name: str | None = None) -> dict[str, Any]:
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


def require_record(record: dict[str, Any]) -> Path:
    if set(record) != {"path", "bytes", "mode", "sha256"}:
        raise ValueError("Artifact record schema drift")
    path = resolve_project(record["path"])
    if observed_artifact(path) != record:
        raise ValueError(f"Artifact identity drift: {record['path']}")
    return path


def create_json_once(path: Path, value: Any) -> None:
    if os.path.lexists(path):
        raise FileExistsError(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.chmod(path, 0o644)


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in PUBLIC_FORBIDDEN_KEYS:
                found.append(f"{prefix}.{key}")
            found.extend(public_sensitive_paths(child, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    return found


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
        raise ValueError("EXP-069 verifier config schema drift")
    if (
        config["schema_version"] != "exp-069-preflight-config-v1"
        or config["experiment_id"] != EXPERIMENT_ID
        or config["run_id"] != RUN_ID
        or config["attempt_id"] != "attempt-1"
        or config["rq_id"] != "RQ-S4"
    ):
        raise ValueError("EXP-069 verifier config identity drift")
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
        raise ValueError("EXP-069 verifier authorization schema drift")
    static_execution = authorization["static_execution_authorized"]
    smoke_execution = authorization["smoke_execution_authorized"]
    if (
        type(static_execution) is not bool
        or type(smoke_execution) is not bool
        or authorization["design_authorized"] is not True
    ):
        raise ValueError("EXP-069 verifier authorization identity drift")
    if (
        authorization["model_loading_authorized"] is not smoke_execution
        or authorization["forward_authorized"] is not smoke_execution
    ):
        raise ValueError("EXP-069 verifier smoke authorization mismatch")
    if any(
        authorization[key] is not False
        for key in (
            "training_authorized",
            "performance_metrics_authorized",
            "validation_access",
            "test_access",
        )
    ):
        raise ValueError("EXP-069 verifier forbidden authorization drift")
    smoke = config["smoke"]
    if smoke["ordinals"] != list(ORDINALS) or smoke["points"] != list(POINTS):
        raise ValueError("EXP-069 verifier smoke identity drift")
    if smoke["fold_counts"] != [FOLD_COUNTS[index] for index in FOLDS]:
        raise ValueError("EXP-069 verifier fold-count drift")
    tolerances = smoke["tolerances"]
    if set(tolerances) != {
        "rtol",
        "m2_hf_atol",
        "standard_hf_atol",
        "manual_logit_atol",
        "m3_logit_atol",
        "pre_lora_atol",
    }:
        raise ValueError("EXP-069 verifier tolerance schema drift")
    if float(tolerances["rtol"]) != 0.0 or any(
        float(tolerances[key]) != 1e-5 for key in tolerances if key != "rtol"
    ):
        raise ValueError("EXP-069 verifier tolerance value drift")
    if [item["seed"] for item in config["m3_lineage"]] != list(SEEDS):
        raise ValueError("EXP-069 verifier seed lineage drift")
    expected_public = {
        "static.json",
        "static-verification.json",
        "run-claim.json",
        "run.json",
        "verification.json",
        "preflight-complete.json",
    }
    if set(config["outputs"]["public_allowlist"]) != expected_public:
        raise ValueError("EXP-069 verifier public allowlist drift")
    for key in ("public_root", "private_root", "heavy_lock"):
        resolve_project(config["outputs"][key], must_exist=False)
    if config["access"] != {
        "allowed_split": "train",
        "train_container_label_values_used": False,
        "train_container_label_values_persisted": False,
        "historical_npz_members": ["sample_ids", "fold_ids", "logits"],
        "heldout_gold_access": False,
        "validation_access": False,
        "test_access": False,
        "performance_metrics": False,
    }:
        raise ValueError("EXP-069 verifier access contract drift")


def require_config_binding(config_path: Path, *records: dict[str, Any]) -> None:
    current = observed_artifact(config_path)
    for record in records:
        if record != current:
            raise ValueError("EXP-069 config changed after static registration")


def require_exact_access(observed: Any, expected: dict[str, Any], label: str) -> None:
    if observed != expected:
        raise ValueError(f"{label} access boundary drift")


def load_config(path: Path) -> dict[str, Any]:
    if path.resolve() != DEFAULT_CONFIG.resolve():
        raise PermissionError("EXP-069 verifier requires the frozen config")
    config = strict_json(path)
    validate_config(config)
    require_record(config["decision"])
    for record in config["implementation"].values():
        require_record(record)
    return config


def public_root(config: dict[str, Any]) -> Path:
    return resolve_project(config["outputs"]["public_root"], must_exist=False)


def private_root(config: dict[str, Any]) -> Path:
    return resolve_project(config["outputs"]["private_root"], must_exist=False)


def inventory(root: Path) -> set[str]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"Invalid output root: {root}")
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def max_abs(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape:
        raise ValueError("Comparison shape drift")
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("Non-finite comparison")
    return float(np.max(np.abs(left.astype(np.float64) - right.astype(np.float64)), initial=0.0))


def load_private_npz(path: Path, expected_keys: set[str]) -> dict[str, np.ndarray]:
    if path.is_symlink() or path.stat().st_nlink != 1 or file_mode(path) != "0600":
        raise PermissionError(f"Unsafe private NPZ: {path}")
    with zipfile.ZipFile(path) as archive:
        names = [item.filename for item in archive.infolist()]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate NPZ member")
        if any(PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts for name in names):
            raise ValueError("Unsafe NPZ member path")
        expected_members = {f"{key}.npy" for key in expected_keys}
        if set(names) != expected_members:
            raise ValueError("Private NPZ keyset drift")
    with np.load(path, allow_pickle=False) as table:
        result = {key: table[key] for key in expected_keys}
    if any(value.dtype.hasobject for value in result.values()):
        raise ValueError("Object dtype forbidden")
    return result


def load_historical_members(path: Path) -> dict[str, np.ndarray]:
    with zipfile.ZipFile(path) as archive:
        names = [item.filename for item in archive.infolist()]
        if len(names) != len(set(names)) or any(".." in PurePosixPath(name).parts for name in names):
            raise ValueError("Unsafe historical NPZ")
    with np.load(path, allow_pickle=False) as table:
        result = {
            "sample_ids": table["sample_ids"],
            "fold_ids": table["fold_ids"],
            "logits": table["logits"],
        }
    return result


def read_safetensors_f32(path: Path, names: set[str]) -> dict[str, np.ndarray]:
    with path.open("rb") as handle:
        header_length = struct.unpack("<Q", handle.read(8))[0]
        header = strict_json_bytes(handle.read(header_length))
        if set(header) - {"__metadata__"} != names:
            raise ValueError("Safetensors keyset drift")
        data_start = 8 + header_length
        output: dict[str, np.ndarray] = {}
        for name in names:
            item = header[name]
            if item["dtype"] != "F32":
                raise ValueError("Verifier supports F32 head tensors only")
            start, end = item["data_offsets"]
            shape = tuple(int(value) for value in item["shape"])
            handle.seek(data_start + int(start))
            payload = handle.read(int(end) - int(start))
            value = np.frombuffer(payload, dtype="<f4").reshape(shape).copy()
            output[name] = value
    return output


def check_static(config: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    checks: list[str] = []
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
    for lineage in config["m3_lineage"]:
        for record in lineage["aggregate_records"]:
            require_record(record)
    root_public = public_root(config)
    root_private = private_root(config)
    if inventory(root_public) != {"static.json"}:
        raise ValueError("Static public inventory drift")
    if inventory(root_private) != {"input-manifest.json"}:
        raise ValueError("Static private inventory drift")
    static = strict_json(root_public / "static.json")
    manifest_path = root_private / "input-manifest.json"
    manifest = strict_json(manifest_path)
    require_config_binding(DEFAULT_CONFIG, manifest["config"])
    if static.get("status") != "CompletedAwaitingVerification" or static.get("stage") != "static":
        raise ValueError("Static run state drift")
    if static["input_manifest"] != observed_artifact(manifest_path, logical_name="input-manifest.json"):
        raise ValueError("Static input-manifest identity drift")
    if file_mode(manifest_path) != "0600" or file_mode(root_private) != "0700":
        raise PermissionError("Static private mode drift")
    if [row["ordinal"] for row in manifest["rows"]] != list(ORDINALS):
        raise ValueError("Static ordinal drift")
    observed_counts = {fold: 0 for fold in FOLDS}
    for row in manifest["rows"]:
        observed_counts[int(row["fold_id"])] += 1
    if observed_counts != FOLD_COUNTS:
        raise ValueError("Static fold coverage drift")
    pairs = [(item["seed"], item["fold"]) for item in manifest["m3_sources"]]
    if pairs != [(seed, fold) for seed in SEEDS for fold in FOLDS]:
        raise ValueError("Static M3 source coverage drift")
    for source in manifest["m3_sources"]:
        for key in ("run", "verification", "adapter", "head", "heldout_logits", "evidence"):
            require_record(source[key])
        if source["seed"] == 42 and source["checkpoint_provenance"] is not None:
            raise ValueError("Seed-42 provenance drift")
        if source["seed"] in (43, 44):
            require_record(source["checkpoint_provenance"])
        verification = strict_json(resolve_project(source["verification"]["path"]))
        if verification.get("status") != "Passed" or verification.get("failed_count", 0) != 0:
            raise ValueError("Parent fold verification drift")
    if manifest["access"] != static["access"]:
        raise ValueError("Static access attestation drift")
    expected_static_access = {
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
    }
    require_exact_access(manifest["access"], expected_static_access, "Static")
    if public_sensitive_paths(static):
        raise ValueError("Static public privacy drift")
    checks.extend(
        [
            "config_identity",
            "implementation_identity",
            "static_public_inventory",
            "static_private_inventory",
            "static_run_state",
            "input_manifest_identity",
            "private_modes",
            "smoke_ordinals",
            "fold_coverage",
            "m3_source_coverage",
            "parent_fold_verifications",
            "access_attestation",
            "public_privacy",
            "future_outputs_absent",
        ]
    )
    return checks, manifest


def verify_static(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    checks, manifest = check_static(config)
    output = {
        "schema_version": "exp-069-static-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": config["attempt_id"],
        "stage": "static",
        "status": "Passed",
        "passed_count": len(checks),
        "failed_count": 0,
        "checks": checks,
        "config": observed_artifact(config_path),
        "input_manifest": observed_artifact(
            private_root(config) / "input-manifest.json", logical_name="input-manifest.json"
        ),
        "counts": {"rows": len(manifest["rows"]), "checkpoints": len(manifest["m3_sources"])},
        "runner_imported": False,
        "model_libraries_imported": False,
        "claim_boundary": config["claim_boundary"],
    }
    if public_sensitive_paths(output):
        raise ValueError("Static verification public privacy drift")
    create_json_once(public_root(config) / "static-verification.json", output)
    return output


def expected_worker_keys() -> set[str]:
    return {
        "ordinal",
        "fold_id",
        "token_length",
        "standard_hf",
        "manual_logits",
        "standard_logits",
        "reference_logits",
        *(POINT_KEYS[name] for name in POINTS),
    }


def expected_base_keys() -> set[str]:
    return {"ordinal", "fold_id", "token_length", "standard_hf", *(POINT_KEYS[name] for name in POINTS)}


def verify_smoke(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    root_public = public_root(config)
    root_private = private_root(config)
    if inventory(root_public) != {"static.json", "static-verification.json", "run-claim.json", "run.json"}:
        raise ValueError("Smoke public inventory drift")
    static_verification = strict_json(root_public / "static-verification.json")
    if static_verification.get("status") != "Passed":
        raise ValueError("Static verification prerequisite drift")
    claim = strict_json(root_public / "run-claim.json")
    if (
        claim.get("status") != "Claimed"
        or claim.get("smoke_execution_authorized") is not True
        or claim.get("model_loading_authorized") is not True
    ):
        raise ValueError("Smoke run claim drift")
    run = strict_json(root_public / "run.json")
    if run.get("status") != "CompletedAwaitingVerification":
        raise ValueError("Smoke run state drift")
    manifest = strict_json(root_private / "input-manifest.json")
    smoke_manifest_path = root_private / "smoke-manifest.json"
    smoke_manifest = strict_json(smoke_manifest_path)
    require_config_binding(
        config_path,
        manifest["config"],
        static_verification["config"],
        claim["config"],
        smoke_manifest["config"],
    )
    if run["private_manifest"] != observed_artifact(smoke_manifest_path, logical_name="smoke-manifest.json"):
        raise ValueError("Smoke private-manifest identity drift")
    if smoke_manifest.get("input_manifest") != observed_artifact(
        root_private / "input-manifest.json", logical_name="input-manifest.json"
    ):
        raise ValueError("Smoke input-manifest identity drift")
    base_path = root_private / "base.npz"
    base_worker_record = strict_json(root_private / "base-worker.json")
    if (
        base_worker_record.get("status") != "Completed"
        or base_worker_record.get("output") != observed_artifact(base_path, logical_name="base.npz")
    ):
        raise ValueError("Base worker manifest drift")
    expected_base_access = {
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
    }
    require_exact_access(base_worker_record.get("access"), expected_base_access, "Base worker")
    base = load_private_npz(base_path, expected_base_keys())
    if base["ordinal"].dtype.str != "<i4" or base["ordinal"].tolist() != list(ORDINALS):
        raise ValueError("Base ordinal drift")
    if base["fold_id"].dtype.str != "|i1" or base["token_length"].dtype.str != "<i2":
        raise ValueError("Base index dtype drift")
    for key in (POINT_KEYS[name] for name in POINTS):
        if base[key].shape != (32, 2560) or base[key].dtype.str != "<f4":
            raise ValueError("Base representation schema drift")
    if base["standard_hf"].shape != (32, 2560) or base["standard_hf"].dtype.str != "<f4":
        raise ValueError("Base standard HF schema drift")
    cache_path = require_record(config["m2_cache"]["features"])
    cache = np.load(cache_path, mmap_mode="r", allow_pickle=False)
    errors = {
        "m2_hf": max_abs(base["hf"], np.asarray(cache[base["ordinal"]], dtype=np.float32)),
        "standard_hf": max_abs(base["hf"], base["standard_hf"]),
        "manual_logit": 0.0,
        "m3_logit": 0.0,
        "pre_lora": 0.0,
    }
    base_position = {int(value): index for index, value in enumerate(base["ordinal"])}
    row_by_ordinal = {int(row["ordinal"]): row for row in manifest["rows"]}
    source_by_pair = {(item["seed"], item["fold"]): item for item in manifest["m3_sources"]}
    coverage: dict[int, list[int]] = {seed: [] for seed in SEEDS}
    actual_worker_records: list[dict[str, Any]] = []
    expected_private = {"input-manifest.json", "base.npz", "base-worker.json", "smoke-manifest.json"}
    for seed in SEEDS:
        for fold in FOLDS:
            expected_private.add(f"seed-{seed}/fold-{fold}.npz")
            expected_private.add(f"seed-{seed}/fold-{fold}.json")
            worker_path = root_private / f"seed-{seed}" / f"fold-{fold}.npz"
            worker_json_path = root_private / f"seed-{seed}" / f"fold-{fold}.json"
            worker = load_private_npz(worker_path, expected_worker_keys())
            worker_record = strict_json(worker_json_path)
            if (
                worker_record.get("status") != "Completed"
                or worker_record.get("seed") != seed
                or worker_record.get("fold") != fold
                or worker_record.get("output")
                != observed_artifact(worker_path, logical_name=f"seed-{seed}/fold-{fold}.npz")
            ):
                raise ValueError("Fold worker manifest drift")
            if worker_record.get("token_stream_sha256") != base_worker_record[
                "fold_token_stream_sha256"
            ][str(fold)]:
                raise ValueError("Verifier observed base/M3 token stream drift")
            if worker_record.get("source_before") != worker_record.get("source_after"):
                raise ValueError("Fold checkpoint changed during runner smoke")
            actual_worker_records.append(worker_record)
            expected_fold_access = {
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
            }
            require_exact_access(worker_record.get("access"), expected_fold_access, "Fold worker")
            expected_ordinals = [
                ordinal for ordinal in ORDINALS if int(row_by_ordinal[ordinal]["fold_id"]) == fold
            ]
            if worker["ordinal"].tolist() != expected_ordinals:
                raise ValueError("Fold worker ordinal drift")
            if worker["fold_id"].tolist() != [fold] * len(expected_ordinals):
                raise ValueError("Fold worker fold drift")
            rows = len(expected_ordinals)
            for key in (POINT_KEYS[name] for name in POINTS):
                if worker[key].shape != (rows, 2560) or worker[key].dtype.str != "<f4":
                    raise ValueError("Fold representation schema drift")
            for key in ("standard_hf",):
                if worker[key].shape != (rows, 2560) or worker[key].dtype.str != "<f4":
                    raise ValueError("Fold HF schema drift")
            for key in ("manual_logits", "standard_logits", "reference_logits"):
                if worker[key].shape != (rows, 6) or worker[key].dtype.str != "<f4":
                    raise ValueError("Fold logit schema drift")
            source = source_by_pair[(seed, fold)]
            current_source = {
                "adapter": observed_artifact(require_record(source["adapter"])),
                "head": observed_artifact(require_record(source["head"])),
                "heldout": observed_artifact(require_record(source["heldout_logits"])),
            }
            if worker_record.get("source_before") != current_source:
                raise ValueError("Fold source identity drift after runner smoke")
            head = read_safetensors_f32(require_record(source["head"]), {"weight", "bias"})
            recomputed = worker["hf"] @ head["weight"].T + head["bias"]
            errors["manual_logit"] = max(
                errors["manual_logit"],
                max_abs(recomputed.astype(np.float32), worker["manual_logits"]),
                max_abs(worker["manual_logits"], worker["standard_logits"]),
            )
            errors["standard_hf"] = max(errors["standard_hf"], max_abs(worker["hf"], worker["standard_hf"]))
            historical = load_historical_members(require_record(source["heldout_logits"]))
            index = {str(value): position for position, value in enumerate(historical["sample_ids"])}
            if set(int(value) for value in np.unique(historical["fold_ids"])) != {fold}:
                raise ValueError("Historical heldout fold drift")
            reference = np.asarray(
                [historical["logits"][index[row_by_ordinal[ordinal]["sample_id"]]] for ordinal in expected_ordinals],
                dtype=np.float32,
            )
            errors["m3_logit"] = max(
                errors["m3_logit"],
                max_abs(worker["reference_logits"], reference),
                max_abs(worker["standard_logits"], reference),
            )
            for point in PRE_LORA_POINTS:
                base_rows = np.asarray(
                    [base[POINT_KEYS[point]][base_position[ordinal]] for ordinal in expected_ordinals],
                    dtype=np.float32,
                )
                errors["pre_lora"] = max(
                    errors["pre_lora"], max_abs(worker[POINT_KEYS[point]], base_rows)
                )
            coverage[seed].extend(expected_ordinals)
    if inventory(root_private) != expected_private:
        raise ValueError("Smoke private inventory drift")
    for relative in expected_private:
        if file_mode(root_private / relative) != "0600":
            raise PermissionError(f"Smoke private mode drift: {relative}")
    if any(sorted(values) != list(ORDINALS) for values in coverage.values()):
        raise ValueError("Smoke per-seed coverage drift")
    if smoke_manifest.get("base_worker") != base_worker_record or smoke_manifest.get(
        "fold_workers"
    ) != actual_worker_records:
        raise ValueError("Smoke worker-manifest aggregation drift")
    expected_coverage = {"base_rows": 32, "seed_fold_rows": 96, "seeds": 3, "folds": 5}
    if smoke_manifest.get("coverage") != expected_coverage:
        raise ValueError("Smoke coverage aggregate drift")
    expected_counts = {"smoke_rows": 32, "seeds": 3, "folds": 5, "model_workers": 16}
    if run.get("counts") != expected_counts:
        raise ValueError("Public count aggregate drift")
    expected_resources = {
        "total_elapsed_seconds": float(base_worker_record["resources"]["elapsed_seconds"])
        + sum(float(worker["resources"]["elapsed_seconds"]) for worker in actual_worker_records),
        "maximum_mlx_peak_bytes": max(
            [int(base_worker_record["resources"]["mlx_peak_bytes"])]
            + [int(worker["resources"]["mlx_peak_bytes"]) for worker in actual_worker_records]
        ),
    }
    if (
        not math_isclose(
            float(run["resources"]["total_elapsed_seconds"]),
            expected_resources["total_elapsed_seconds"],
        )
        or int(run["resources"]["maximum_mlx_peak_bytes"])
        != expected_resources["maximum_mlx_peak_bytes"]
    ):
        raise ValueError("Public resource aggregate drift")
    expected_aggregate_access = {
        "train_only": True,
        "validation_accessed": False,
        "test_accessed": False,
        "performance_metrics_computed": False,
    }
    require_exact_access(run.get("access"), expected_aggregate_access, "Smoke run")
    require_exact_access(smoke_manifest.get("access"), expected_aggregate_access, "Smoke manifest")
    limits = config["smoke"]["tolerances"]
    gate_map = {
        "m2_hf": "m2_hf_atol",
        "standard_hf": "standard_hf_atol",
        "manual_logit": "manual_logit_atol",
        "m3_logit": "m3_logit_atol",
        "pre_lora": "pre_lora_atol",
    }
    for gate, limit_key in gate_map.items():
        if errors[gate] > float(limits[limit_key]):
            raise ValueError(f"EXP-069 numeric gate failed: {gate}")
    for gate, value in errors.items():
        if not math_isclose(value, float(run["max_errors"][gate])):
            raise ValueError(f"Public aggregate drift: {gate}")
        if not math_isclose(value, float(smoke_manifest["max_errors"][gate])):
            raise ValueError(f"Private aggregate drift: {gate}")
    if public_sensitive_paths(run):
        raise ValueError("Smoke public privacy drift")
    checks = [
        "config_identity",
        "implementation_identity",
        "static_verification",
        "public_inventory",
        "private_inventory",
        "private_modes",
        "smoke_manifest_identity",
        "base_schema",
        "base_cache_replay",
        "standard_hf_replay",
        "fold_schemas",
        "head_logit_replay",
        "heldout_logit_replay",
        "token_stream_identity",
        "pre_lora_equivalence",
        "per_seed_coverage",
        "numeric_gates",
        "aggregate_replay",
        "resource_replay",
        "public_privacy",
        "access_boundary",
        "no_metrics",
    ]
    verification = {
        "schema_version": "exp-069-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": config["attempt_id"],
        "status": "Passed",
        "passed_count": len(checks),
        "failed_count": 0,
        "checks": checks,
        "max_errors": errors,
        "counts": {"smoke_rows": 32, "seeds": 3, "folds": 5, "worker_npz": 16},
        "runner_imported": False,
        "model_libraries_imported": False,
        "access": {"validation_accessed": False, "test_accessed": False, "gold_read": False},
        "claim_boundary": config["claim_boundary"],
    }
    create_json_once(root_public / "verification.json", verification)
    completion = {
        "schema_version": "exp-069-complete-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": config["attempt_id"],
        "status": "Complete",
        "run": observed_artifact(root_public / "run.json"),
        "verification": observed_artifact(root_public / "verification.json"),
        "claim_boundary": config["claim_boundary"],
        "next_gate": "EXP-070 remains separately registered and unexecuted",
    }
    create_json_once(root_public / "preflight-complete.json", completion)
    return verification


def math_isclose(left: float, right: float) -> bool:
    return abs(left - right) <= 1e-12


def record_failed_verification(config: dict[str, Any], stage: str, error: BaseException) -> None:
    try:
        root = public_root(config)
        name = "static-verification.json" if stage == "static" else "verification.json"
        target = root / name
        if os.path.lexists(target):
            return
        value = {
            "schema_version": "exp-069-verification-failure-v1",
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
    parser = argparse.ArgumentParser(description="Independently verify EXP-069 preflight evidence")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--stage", choices=("static", "smoke"), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config: dict[str, Any] = {}
    try:
        config = load_config(args.config)
        authorization_key = (
            "static_execution_authorized" if args.stage == "static" else "smoke_execution_authorized"
        )
        if config["authorization"][authorization_key] is not True:
            raise PermissionError(f"EXP-069 {args.stage} is not authorized by the frozen config")
        result = verify_static(args.config, config) if args.stage == "static" else verify_smoke(
            args.config, config
        )
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
            record_failed_verification(config, args.stage, error)
        raise


if __name__ == "__main__":
    main()
