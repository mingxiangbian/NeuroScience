#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import resource
import stat
import sys
import time
from typing import Any

import numpy as np


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
DEFAULT_CONFIG = MODULE_DIR / "configs" / "exp-069-base-smoke-attempt-2.json"
EXPERIMENT_ID = "EXP-069"
ATTEMPT_ID = "attempt-2-base-smoke"
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
    "text",
    "texts",
    "sample_id",
    "sample_ids",
    "component_id",
    "component_ids",
    "ordinal",
    "ordinals",
    "token_ids",
    "hidden_states",
    "representations",
    "logits",
    "gold",
    "labels",
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


def create_json_once(path: Path, value: Any, *, private: bool = False) -> None:
    if os.path.lexists(path):
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    if private:
        os.chmod(path.parent, 0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600 if private else 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.chmod(path, 0o600 if private else 0o644)


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
        "attempt_id",
        "rq_id",
        "tier",
        "registered_at",
        "authorization",
        "parent_static",
        "source_runner",
        "implementation",
        "environment",
        "smoke",
        "resources",
        "outputs",
        "claim_boundary",
    }
    if set(config) != expected:
        raise ValueError("Base-smoke config schema drift")
    if (
        config["schema_version"] != "exp-069-base-smoke-attempt-2-v1"
        or config["experiment_id"] != EXPERIMENT_ID
        or config["attempt_id"] != ATTEMPT_ID
        or config["rq_id"] != "RQ-S4"
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
        raise ValueError("Base-smoke authorization drift")
    if config["smoke"] != {
        "points": list(POINTS),
        "rows": 32,
        "hidden_size": 2560,
        "comparison_dtype": "float32",
        "rtol": 0.0,
        "m2_hf_atol": 1e-5,
        "standard_hf_atol": 1e-5,
    }:
        raise ValueError("Base-smoke numeric contract drift")
    for key in ("public_root", "private_root"):
        resolve_project(config["outputs"][key], must_exist=False)


def load_config(path: Path) -> dict[str, Any]:
    if path.resolve() != DEFAULT_CONFIG.resolve():
        raise PermissionError("Base-smoke consumer requires the frozen config")
    config = strict_json(path)
    validate_config(config)
    return config


def load_source_runner(config: dict[str, Any]) -> Any:
    source_path = require_record(config["source_runner"])
    spec = importlib.util.spec_from_file_location("exp069_attempt1_frozen_runner", source_path)
    if spec is None or spec.loader is None:
        raise ImportError(source_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def public_root(config: dict[str, Any]) -> Path:
    return resolve_project(config["outputs"]["public_root"], must_exist=False)


def private_root(config: dict[str, Any]) -> Path:
    return resolve_project(config["outputs"]["private_root"], must_exist=False)


def inventory(root: Path) -> set[str]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Invalid parent output root")
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


def qwen_tree(parent_config: dict[str, Any], source: Any) -> list[dict[str, Any]]:
    manifest = source.strict_json(source.require_record(parent_config["model"]["qwen_manifest"]))
    base_root = source.resolve_project(parent_config["model"]["base_path"], must_exist=False)
    expected = manifest["mlx_bf16"]["files"]
    if {item["path"] for item in expected} != {
        path.relative_to(base_root).as_posix() for path in base_root.iterdir() if path.is_file()
    }:
        raise ValueError("Frozen Qwen file inventory drift")
    records: list[dict[str, Any]] = []
    for item in expected:
        path = base_root / item["path"]
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError("Unsafe Frozen Qwen asset")
        observed = observed_artifact(path)
        if observed["bytes"] != item["bytes"] or observed["sha256"] != item["sha256"]:
            raise ValueError(f"Frozen Qwen asset drift: {item['path']}")
        records.append(observed)
    return records


def require_parent(config: dict[str, Any], source: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    parent = config["parent_static"]
    parent_config_path = require_record(parent["config"])
    require_record(parent["static_run"])
    static_verification_path = require_record(parent["static_verification"])
    input_manifest_path = require_record(parent["input_manifest"])
    static_verification = strict_json(static_verification_path)
    if (
        static_verification.get("status") != "Passed"
        or static_verification.get("passed_count") != 14
        or static_verification.get("failed_count") != 0
    ):
        raise ValueError("Parent static verification drift")
    if inventory(static_verification_path.parent) != {"static.json", "static-verification.json"}:
        raise ValueError("Parent static public inventory drift")
    if inventory(input_manifest_path.parent) != {"input-manifest.json"}:
        raise ValueError("Parent static private inventory drift")
    parent_config = source.load_config(parent_config_path)
    source.require_static_pass(parent_config_path, parent_config)
    manifest = strict_json(input_manifest_path)
    if manifest.get("config") != parent["config"]:
        raise ValueError("Parent input-manifest config binding drift")
    return parent_config, manifest


def require_implementation(config: dict[str, Any]) -> None:
    for record in config["implementation"].values():
        require_record(record)


def peak_rss_gb() -> float:
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1e9


def execute(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    require_implementation(config)
    source = load_source_runner(config)
    parent_config, manifest = require_parent(config, source)
    source.require_environment(parent_config)
    if source.environment_identity() != config["environment"]:
        raise PermissionError("Base-smoke environment drift")
    root_public = public_root(config)
    root_private = private_root(config)
    if os.path.lexists(root_public) or os.path.lexists(root_private):
        raise FileExistsError("Base-smoke output root exists")
    root_public.mkdir(parents=True, mode=0o755)
    root_private.mkdir(parents=True, mode=0o700)
    os.chmod(root_private, 0o700)
    claim = {
        "schema_version": "exp-069-base-smoke-claim-v1",
        "experiment_id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "Claimed",
        "config": observed_artifact(config_path),
        "parent_static_verification": config["parent_static"]["static_verification"],
        "authorized_stage": "base-smoke",
        "fold_smoke_authorized": False,
        "assemble_authorized": False,
        "claim_boundary": config["claim_boundary"],
    }
    create_json_once(root_public / "run-claim.json", claim)
    rows = source.load_selected_train_rows(parent_config, manifest)
    prompt = source.strict_json(source.require_record(parent_config["model"]["prompt"]))
    source.require_record(parent_config["model"]["shared_config"])
    source.require_record(parent_config["model"]["qwen_manifest"])
    source.require_record(parent_config["data"]["train"])
    source.require_record(parent_config["m2_cache"]["gate_verification"])
    qwen_before = qwen_tree(parent_config, source)
    cache_path = source.require_record(parent_config["m2_cache"]["features"])
    cache_before = observed_artifact(cache_path)
    cache = np.load(
        cache_path,
        mmap_mode="r",
        allow_pickle=False,
    )
    if cache.flags.writeable or cache.shape != (3360, 2560) or cache.dtype.str != "<f4":
        raise ValueError("M2 cache read-only schema drift")
    started = time.perf_counter()
    with source.heavy_mutex(parent_config):
        import mlx.core as mx
        from mlx_lm import load
        from mlx_lm.models.base import create_attention_mask

        mx.reset_peak_memory()
        model, tokenizer = load(str(source.resolve_project(parent_config["model"]["base_path"])), lazy=False)
        model.freeze()
        model.eval()
        arrays: dict[str, list[np.ndarray]] = {POINT_KEYS[name]: [] for name in POINTS}
        standard_values: list[np.ndarray] = []
        tokens: list[tuple[int, list[int]]] = []
        token_lengths: list[int] = []
        standard_error = 0.0
        for row in rows:
            ids, _, _ = source.qwen_prompt_ids(tokenizer, prompt, row["text"], 384)
            points, standard = source.manual_residual_points(
                model, mx.array([ids], dtype=mx.int32), create_attention_mask
            )
            mx.eval(*points.values(), standard)
            converted = {
                name: np.asarray(value.astype(mx.float32), dtype=np.float32)
                for name, value in points.items()
            }
            standard_array = np.asarray(standard.astype(mx.float32), dtype=np.float32)
            standard_error = max(standard_error, source.max_abs(converted["HF"], standard_array))
            for name in POINTS:
                arrays[POINT_KEYS[name]].append(converted[name][0])
            standard_values.append(standard_array[0])
            tokens.append((int(row["ordinal"]), ids))
            token_lengths.append(len(ids))
            if time.perf_counter() - started > float(config["resources"]["wall_minutes"]) * 60:
                raise TimeoutError("Base smoke exceeded wall-time budget")
            if float(mx.get_peak_memory()) / 1e9 > float(config["resources"]["peak_mlx_gb"]):
                raise MemoryError("Base smoke exceeded MLX memory budget")
        stacked = {key: np.asarray(values, dtype=np.float32) for key, values in arrays.items()}
        standard_hf = np.asarray(standard_values, dtype=np.float32)
        ordinals = np.asarray([row["ordinal"] for row in rows], dtype=np.int32)
        fold_ids = np.asarray([row["fold_id"] for row in rows], dtype=np.int8)
        m2_error = source.max_abs(stacked["hf"], np.asarray(cache[ordinals], dtype=np.float32))
        if standard_error > config["smoke"]["standard_hf_atol"] or m2_error > config["smoke"]["m2_hf_atol"]:
            raise ValueError("Base smoke numeric gate failed")
        output_path = root_private / "base.npz"
        source.save_npz_once(
            output_path,
            ordinal=ordinals,
            fold_id=fold_ids,
            token_length=np.asarray(token_lengths, dtype=np.int16),
            standard_hf=standard_hf,
            **stacked,
        )
        resources = {
            "elapsed_seconds": time.perf_counter() - started,
            "mlx_peak_bytes": int(mx.get_peak_memory()),
            "ru_maxrss_gb": peak_rss_gb(),
        }
        del model, tokenizer
        mx.clear_cache()
    cache_after = observed_artifact(cache_path)
    if cache_before != cache_after:
        raise ValueError("M2 cache identity changed during base smoke")
    qwen_after = qwen_tree(parent_config, source)
    if qwen_before != qwen_after:
        raise ValueError("Frozen Qwen identity changed during base smoke")
    worker = {
        "schema_version": "exp-069-base-smoke-worker-v2",
        "experiment_id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "Completed",
        "rows": 32,
        "token_stream_sha256": source.token_stream_digest(tokens),
        "fold_token_stream_sha256": {
            str(fold): source.token_stream_digest(
                [token_row for token_row, row in zip(tokens, rows) if int(row["fold_id"]) == fold]
            )
            for fold in source.FOLDS
        },
        "max_errors": {"m2_hf": m2_error, "standard_hf": standard_error},
        "m2_cache_before": cache_before,
        "m2_cache_after": cache_after,
        "qwen_tree_before": qwen_before,
        "qwen_tree_after": qwen_after,
        "output": observed_artifact(output_path, logical_name="base.npz"),
        "resources": resources,
        "access": {
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
        },
    }
    worker_path = root_private / "base-worker.json"
    create_json_once(worker_path, worker, private=True)
    run = {
        "schema_version": "exp-069-base-smoke-run-v2",
        "experiment_id": EXPERIMENT_ID,
        "attempt_id": ATTEMPT_ID,
        "stage": "base-smoke",
        "status": "CompletedAwaitingVerification",
        "rows": 32,
        "points": list(POINTS),
        "max_errors": worker["max_errors"],
        "resources": resources,
        "private_worker": observed_artifact(worker_path, logical_name="base-worker.json"),
        "private_output": observed_artifact(output_path, logical_name="base.npz"),
        "access": worker["access"],
        "fold_smoke_authorized": False,
        "assemble_authorized": False,
        "base_smoke_complete": True,
        "exp069_complete": False,
        "claim_boundary": config["claim_boundary"],
    }
    if public_sensitive_paths(run):
        raise ValueError("Base-smoke public privacy scan failed")
    create_json_once(root_public / "run.json", run)
    return run


def record_failure(config: dict[str, Any], error: BaseException) -> None:
    try:
        root = public_root(config)
        root.mkdir(parents=True, exist_ok=True, mode=0o755)
        target = root / "run.json"
        if os.path.lexists(target):
            return
        create_json_once(
            target,
            {
                "schema_version": "exp-069-base-smoke-failure-v1",
                "experiment_id": EXPERIMENT_ID,
                "attempt_id": ATTEMPT_ID,
                "stage": "base-smoke",
                "status": "Failed",
                "error_type": type(error).__name__,
                "claim_boundary": config.get("claim_boundary"),
            },
        )
    except Exception:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the append-only EXP-069 base smoke")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--stage", choices=("base-smoke",), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config: dict[str, Any] = {}
    try:
        config = load_config(args.config)
        result = execute(args.config, config)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        if config:
            record_failure(config, error)
        raise


if __name__ == "__main__":
    main()
