#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from typing import Any
import zipfile

import numpy as np


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
DEFAULT_CONFIG = MODULE_DIR / "configs" / "exp-069-base-smoke-attempt-2.json"
EXPERIMENT_ID = "EXP-069"
ATTEMPT_ID = "attempt-2-base-smoke"
ORDINALS = (
    0, 108, 217, 325, 433, 542, 650, 758,
    867, 975, 1084, 1192, 1300, 1409, 1517, 1625,
    1734, 1842, 1950, 2059, 2167, 2275, 2384, 2492,
    2601, 2709, 2817, 2926, 3034, 3142, 3251, 3359,
)
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
PUBLIC_FORBIDDEN_KEYS = {
    "text", "texts", "sample_id", "sample_ids", "component_id", "component_ids",
    "ordinal", "ordinals", "token_ids", "hidden_states", "representations", "logits",
    "gold", "labels",
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


def strict_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_no_constant,
    )


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
    pure = PurePosixPath(relative)
    if type(relative) is not str or not relative or pure.is_absolute() or pure.as_posix() != relative:
        raise ValueError("Unsafe project path")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("Unsafe project path")
    candidate = PROJECT_ROOT.joinpath(*pure.parts)
    current = PROJECT_ROOT
    for part in pure.parts:
        current = current / part
        if os.path.lexists(current) and current.is_symlink():
            raise ValueError("Symlink path rejected")
    if must_exist:
        if not candidate.is_file() or candidate.stat().st_nlink != 1:
            raise ValueError("Unsafe or missing input")
    return candidate


def observed_artifact(path: Path, *, logical_name: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "bytes": path.stat().st_size,
        "mode": file_mode(path),
        "sha256": sha256(path),
    }
    if logical_name is None:
        value["path"] = path.relative_to(PROJECT_ROOT).as_posix()
    else:
        value["logical_name"] = logical_name
    return value


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
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
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


def load_config(path: Path) -> dict[str, Any]:
    if path.resolve() != DEFAULT_CONFIG.resolve():
        raise PermissionError("Base-smoke verifier requires the frozen config")
    config = strict_json(path)
    if (
        config.get("schema_version") != "exp-069-base-smoke-attempt-2-v1"
        or config.get("experiment_id") != EXPERIMENT_ID
        or config.get("attempt_id") != ATTEMPT_ID
    ):
        raise ValueError("Base-smoke config identity drift")
    if config["authorization"] != {
        "base_smoke_authorized": True,
        "model_loading_authorized": True,
        "forward_authorized": True,
        "fold_smoke_authorized": False,
        "assemble_authorized": False,
        "training_authorized": False,
        "performance_metrics_authorized": False,
        "validation_access": False,
        "test_access": False,
    }:
        raise ValueError("Base-smoke verifier authorization drift")
    require_record(config["source_runner"])
    for record in config["parent_static"].values():
        require_record(record)
    for record in config["implementation"].values():
        require_record(record)
    return config


def public_root(config: dict[str, Any]) -> Path:
    return resolve_project(config["outputs"]["public_root"], must_exist=False)


def private_root(config: dict[str, Any]) -> Path:
    return resolve_project(config["outputs"]["private_root"], must_exist=False)


def inventory(root: Path) -> set[str]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Invalid output root")
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


def qwen_tree(parent_config: dict[str, Any]) -> list[dict[str, Any]]:
    manifest = strict_json(require_record(parent_config["model"]["qwen_manifest"]))
    base_root = resolve_project(parent_config["model"]["base_path"], must_exist=False)
    expected = manifest["mlx_bf16"]["files"]
    if {item["path"] for item in expected} != {
        path.relative_to(base_root).as_posix() for path in base_root.iterdir() if path.is_file()
    }:
        raise ValueError("Frozen Qwen inventory drift")
    records: list[dict[str, Any]] = []
    for item in expected:
        path = base_root / item["path"]
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError("Unsafe Frozen Qwen asset")
        observed = observed_artifact(path)
        if observed["bytes"] != item["bytes"] or observed["sha256"] != item["sha256"]:
            raise ValueError("Frozen Qwen asset drift")
        records.append(observed)
    return records


def max_abs(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape or not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("Invalid numeric comparison")
    return float(np.max(np.abs(left.astype(np.float64) - right.astype(np.float64)), initial=0.0))


def load_base_npz(path: Path) -> dict[str, np.ndarray]:
    if file_mode(path) != "0600" or path.is_symlink() or path.stat().st_nlink != 1:
        raise PermissionError("Unsafe private base artifact")
    keys = {"ordinal", "fold_id", "token_length", "standard_hf", *(POINT_KEYS[name] for name in POINTS)}
    with zipfile.ZipFile(path) as archive:
        names = [item.filename for item in archive.infolist()]
        if len(names) != len(set(names)) or set(names) != {f"{key}.npy" for key in keys}:
            raise ValueError("Base NPZ inventory drift")
        if any(".." in PurePosixPath(name).parts for name in names):
            raise ValueError("Unsafe NPZ member")
    with np.load(path, allow_pickle=False) as table:
        values = {key: table[key] for key in keys}
    if any(value.dtype.hasobject for value in values.values()):
        raise ValueError("Object dtype forbidden")
    return values


def validate_resources(resources: Any, config: dict[str, Any]) -> None:
    if set(resources) != {"elapsed_seconds", "mlx_peak_bytes", "ru_maxrss_gb"}:
        raise ValueError("Base-smoke resource schema drift")
    elapsed = float(resources["elapsed_seconds"])
    mlx_peak = int(resources["mlx_peak_bytes"])
    rss = float(resources["ru_maxrss_gb"])
    if not math.isfinite(elapsed) or not math.isfinite(rss) or elapsed < 0 or rss < 0 or mlx_peak < 0:
        raise ValueError("Base-smoke resource value drift")
    if elapsed > float(config["resources"]["wall_minutes"]) * 60:
        raise ValueError("Base-smoke wall-time gate failed")
    if mlx_peak > float(config["resources"]["peak_mlx_gb"]) * 1_000_000_000:
        raise ValueError("Base-smoke MLX-memory gate failed")


def validate_base_metadata(
    base: dict[str, np.ndarray], input_manifest: dict[str, Any], worker: dict[str, Any]
) -> None:
    if base["fold_id"].shape != (32,) or base["token_length"].shape != (32,):
        raise ValueError("Base metadata shape drift")
    row_by_ordinal = {int(row["ordinal"]): row for row in input_manifest["rows"]}
    expected_folds = [int(row_by_ordinal[ordinal]["fold_id"]) for ordinal in ORDINALS]
    if base["fold_id"].tolist() != expected_folds:
        raise ValueError("Base fold mapping drift")
    if np.any(base["token_length"] < 1) or np.any(base["token_length"] > 384):
        raise ValueError("Base token-length drift")
    digest = worker.get("token_stream_sha256")
    fold_digests = worker.get("fold_token_stream_sha256")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("Base token-stream digest drift")
    if not isinstance(fold_digests, dict) or set(fold_digests) != {"0", "1", "2", "3", "4"}:
        raise ValueError("Base fold-token digest schema drift")
    if any(
        not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
        for value in fold_digests.values()
    ):
        raise ValueError("Base fold-token digest value drift")


def validate_claim(claim: dict[str, Any], config: dict[str, Any], current_config: dict[str, Any]) -> None:
    expected_keys = {
        "schema_version",
        "experiment_id",
        "attempt_id",
        "status",
        "config",
        "parent_static_verification",
        "authorized_stage",
        "fold_smoke_authorized",
        "assemble_authorized",
        "claim_boundary",
    }
    if set(claim) != expected_keys:
        raise ValueError("Base-smoke claim schema drift")
    if (
        claim["schema_version"] != "exp-069-base-smoke-claim-v1"
        or claim["experiment_id"] != EXPERIMENT_ID
        or claim["attempt_id"] != ATTEMPT_ID
        or claim["status"] != "Claimed"
        or claim["authorized_stage"] != "base-smoke"
        or claim["fold_smoke_authorized"] is not False
        or claim["assemble_authorized"] is not False
        or claim["config"] != current_config
        or claim["parent_static_verification"] != config["parent_static"]["static_verification"]
        or claim["claim_boundary"] != config["claim_boundary"]
    ):
        raise ValueError("Base-smoke claim value drift")


def verify(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    root_public = public_root(config)
    root_private = private_root(config)
    if inventory(root_public) != {"run-claim.json", "run.json"}:
        raise ValueError("Base-smoke public inventory drift")
    if inventory(root_private) != {"base.npz", "base-worker.json"}:
        raise ValueError("Base-smoke private inventory drift")
    if file_mode(root_public) != "0755" or file_mode(root_private) != "0700":
        raise PermissionError("Base-smoke root mode drift")
    for path in (root_public / "run-claim.json", root_public / "run.json"):
        if path.is_symlink() or path.stat().st_nlink != 1 or file_mode(path) != "0644":
            raise PermissionError("Base-smoke public file mode/link drift")
    for path in (root_private / "base.npz", root_private / "base-worker.json"):
        if path.is_symlink() or path.stat().st_nlink != 1 or file_mode(path) != "0600":
            raise PermissionError("Base-smoke private file mode/link drift")
    claim = strict_json(root_public / "run-claim.json")
    run = strict_json(root_public / "run.json")
    worker = strict_json(root_private / "base-worker.json")
    current_config = observed_artifact(config_path)
    validate_claim(claim, config, current_config)
    if run.get("status") != "CompletedAwaitingVerification" or worker.get("status") != "Completed":
        raise ValueError("Base-smoke terminal state drift")
    base_path = root_private / "base.npz"
    if run.get("private_output") != observed_artifact(base_path, logical_name="base.npz"):
        raise ValueError("Base-smoke private output drift")
    if run.get("private_worker") != observed_artifact(
        root_private / "base-worker.json", logical_name="base-worker.json"
    ):
        raise ValueError("Base-smoke worker identity drift")
    if worker.get("output") != run.get("private_output"):
        raise ValueError("Base-smoke worker/run binding drift")
    base = load_base_npz(base_path)
    if (
        base["ordinal"].shape != (32,)
        or base["ordinal"].dtype.str != "<i4"
        or tuple(int(value) for value in base["ordinal"]) != ORDINALS
    ):
        raise ValueError("Base ordinal drift")
    if (
        base["fold_id"].shape != (32,)
        or base["fold_id"].dtype.str != "|i1"
        or base["token_length"].shape != (32,)
        or base["token_length"].dtype.str != "<i2"
    ):
        raise ValueError("Base index dtype drift")
    for point in POINTS:
        value = base[POINT_KEYS[point]]
        if value.shape != (32, 2560) or value.dtype.str != "<f4" or not np.isfinite(value).all():
            raise ValueError("Base representation schema drift")
    if base["standard_hf"].shape != (32, 2560) or base["standard_hf"].dtype.str != "<f4":
        raise ValueError("Base standard HF schema drift")
    parent_config = strict_json(require_record(config["parent_static"]["config"]))
    static_run_path = require_record(config["parent_static"]["static_run"])
    static_verification_path = require_record(config["parent_static"]["static_verification"])
    input_manifest_path = require_record(config["parent_static"]["input_manifest"])
    input_manifest = strict_json(input_manifest_path)
    if inventory(static_run_path.parent) != {"static.json", "static-verification.json"}:
        raise ValueError("Parent static public inventory drift")
    if inventory(input_manifest_path.parent) != {"input-manifest.json"}:
        raise ValueError("Parent static private inventory drift")
    validate_base_metadata(base, input_manifest, worker)
    cache_record = parent_config["m2_cache"]["features"]
    cache_path = require_record(cache_record)
    cache_current = observed_artifact(cache_path)
    if worker.get("m2_cache_before") != cache_current or worker.get("m2_cache_after") != cache_current:
        raise ValueError("M2 cache before/after identity drift")
    current_qwen_tree = qwen_tree(parent_config)
    if worker.get("qwen_tree_before") != current_qwen_tree or worker.get("qwen_tree_after") != current_qwen_tree:
        raise ValueError("Frozen Qwen before/after identity drift")
    cache = np.load(cache_path, mmap_mode="r", allow_pickle=False)
    if cache.flags.writeable or cache.shape != (3360, 2560) or cache.dtype.str != "<f4":
        raise ValueError("M2 cache read-only schema drift")
    errors = {
        "m2_hf": max_abs(base["hf"], np.asarray(cache[base["ordinal"]], dtype=np.float32)),
        "standard_hf": max_abs(base["hf"], base["standard_hf"]),
    }
    if errors["m2_hf"] > config["smoke"]["m2_hf_atol"] or errors["standard_hf"] > config["smoke"]["standard_hf_atol"]:
        raise ValueError("Independent base-smoke numeric gate failed")
    if any(abs(float(worker["max_errors"][key]) - value) > 1e-12 for key, value in errors.items()):
        raise ValueError("Base worker aggregate drift")
    if run.get("max_errors") != worker.get("max_errors") or run.get("resources") != worker.get("resources"):
        raise ValueError("Base public aggregate drift")
    validate_resources(worker.get("resources"), config)
    expected_access = {
        "train_label_bearing_container_accessed": True,
        "train_text_accessed": True,
        "train_label_values_used": False,
        "train_label_values_persisted": False,
        "m2_feature_rows_read": 32,
        "m3_artifacts_accessed": False,
        "model_loaded": True,
        "forward_executed": True,
        "validation_accessed": False,
        "test_accessed": False,
        "performance_metrics_computed": False,
    }
    if worker.get("access") != expected_access or run.get("access") != expected_access:
        raise ValueError("Base-smoke access boundary drift")
    if run.get("fold_smoke_authorized") is not False or run.get("assemble_authorized") is not False:
        raise ValueError("Base-smoke scope drift")
    if run.get("base_smoke_complete") is not True or run.get("exp069_complete") is not False:
        raise ValueError("Base-smoke completion scope drift")
    if public_sensitive_paths(claim) or public_sensitive_paths(run):
        raise ValueError("Base-smoke public privacy drift")
    parent_verification = strict_json(static_verification_path)
    if parent_verification.get("status") != "Passed" or parent_verification.get("passed_count") != 14:
        raise ValueError("Parent static verification drift")
    checks = [
        "config_identity",
        "implementation_identity",
        "parent_static_bindings",
        "public_inventory",
        "private_inventory",
        "private_modes",
        "resource_gates",
        "claim_state",
        "run_state",
        "artifact_bindings",
        "base_npz_schema",
        "smoke_ordinals",
        "fold_mapping",
        "token_contract",
        "m2_cache_replay",
        "standard_hf_replay",
        "numeric_gates",
        "aggregate_replay",
        "access_boundary",
        "scope_boundary",
        "public_privacy",
        "no_metrics",
        "no_validation_test",
    ]
    verification = {
        "schema_version": "exp-069-base-smoke-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "Passed",
        "passed_count": len(checks),
        "failed_count": 0,
        "checks": checks,
        "max_errors": errors,
        "rows": 32,
        "runner_imported": False,
        "model_libraries_imported": False,
        "fold_smoke_authorized": False,
        "base_smoke_complete": True,
        "exp069_complete": False,
        "assemble_authorized": False,
        "claim_boundary": config["claim_boundary"],
    }
    if public_sensitive_paths(verification):
        raise ValueError("Base verification public privacy drift")
    verification_path = root_public / "verification.json"
    create_json_once(verification_path, verification)
    completion = {
        "schema_version": "exp-069-base-smoke-complete-v1",
        "experiment_id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "Complete",
        "run": observed_artifact(root_public / "run.json"),
        "verification": observed_artifact(verification_path),
        "private_output": observed_artifact(base_path, logical_name="base.npz"),
        "base_smoke_complete": True,
        "exp069_complete": False,
        "fold_smoke_authorized": False,
        "next_gate": "EXP-069 fold smoke remains separately unauthorized",
        "claim_boundary": config["claim_boundary"],
    }
    create_json_once(root_public / "base-complete.json", completion)
    return verification


def record_failure(config: dict[str, Any], error: BaseException) -> None:
    try:
        root = public_root(config)
        target = root / "verification.json"
        if os.path.lexists(target):
            return
        create_json_once(
            target,
            {
                "schema_version": "exp-069-base-smoke-verification-failure-v1",
                "experiment_id": EXPERIMENT_ID,
                "attempt_id": ATTEMPT_ID,
                "status": "Failed",
                "error_type": type(error).__name__,
                "claim_boundary": config.get("claim_boundary"),
            },
        )
    except Exception:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Independently verify EXP-069 base smoke")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config: dict[str, Any] = {}
    try:
        config = load_config(args.config)
        result = verify(args.config, config)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        if config:
            record_failure(config, error)
        raise


if __name__ == "__main__":
    main()
