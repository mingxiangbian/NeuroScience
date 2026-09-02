#!/usr/bin/env python3
"""Run the one-shot EXP-066 32-row headless runtime parity gate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.metadata
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import resource
import stat
import sys
import time
from typing import Any
import zipfile

import numpy as np

import runtime_exp066 as runtime_core


EXPERIMENT_ID = "EXP-066"
RUN_ID = "exp-066-headless-runtime-parity"
CONFIG_SCHEMA = "exp-066-runtime-parity-config-v1"
PRIVATE_SCHEMA = "exp-066-runtime-parity-private-v1"
LABEL_ORDER = runtime_core.LABEL_ORDER
FEATURE_NAMES = runtime_core.FEATURE_NAMES
PARITY_SCHEMA = {
    "ordinal": {"shape": [32], "dtype": "int16", "fortran_order": False},
    "m1_probabilities": {"shape": [32, 6], "dtype": "float32", "fortran_order": False},
    "m3_probabilities": {"shape": [32, 6], "dtype": "float32", "fortran_order": False},
    "features": {"shape": [32, 14], "dtype": "float64", "fortran_order": False},
    "standardized_features": {"shape": [32, 14], "dtype": "float64", "fortran_order": False},
    "route_score": {"shape": [32], "dtype": "float64", "fortran_order": False},
    "route_mask": {"shape": [32], "dtype": "uint8", "fortran_order": False},
    "m1_prediction": {"shape": [32, 6], "dtype": "uint8", "fortran_order": False},
    "m3_prediction": {"shape": [32, 6], "dtype": "uint8", "fortran_order": False},
    "final_prediction": {"shape": [32, 6], "dtype": "uint8", "fortran_order": False},
    "selected_path": {"shape": [32], "dtype": "uint8", "fortran_order": False},
    "neutral": {"shape": [32], "dtype": "uint8", "fortran_order": False},
    "character_length": {"shape": [32], "dtype": "int32", "fortran_order": False},
    "m1_token_length": {"shape": [32], "dtype": "int32", "fortran_order": False},
}
PUBLIC_SENSITIVE_KEYS = {
    "text", "raw_text", "ordinal", "ordinals", "sample_id", "sample_ids",
    "component_id", "component_ids", "probabilities", "m1_probabilities",
    "m3_probabilities", "features", "standardized_features", "route_score",
    "route_mask", "prediction", "predictions", "m1_prediction", "m3_prediction",
    "final_prediction", "selected_path", "neutral", "active_labels", "token_ids",
}
CLAIM_BOUNDARY = (
    "A verified 32-row checkpoint-to-headless-runtime parity result for the frozen seed-42 "
    "local development stack only; no classification performance, independent-test, latency, "
    "production, forum-generalization, or emotion-mechanism claim."
)


def _project_root(source: Path) -> Path:
    for candidate in (source, *source.parents):
        if candidate.name == "llm-forum-text-emotion-recognition":
            return candidate
    raise RuntimeError("Could not locate project root")


PROJECT_ROOT = _project_root(Path(__file__).resolve())
BASE = Path("experiments/stack-overflow-emotion-gold/oof-router")
DEFAULT_CONFIG = PROJECT_ROOT / BASE / "configs/exp-066-headless-runtime-parity.json"
PUBLIC_REL = BASE / "runs" / RUN_ID
PRIVATE_REL = BASE / "private" / RUN_ID


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def _resolve(value: str | Path) -> Path:
    relative = Path(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"Unsafe project-relative path: {value}")
    cursor = PROJECT_ROOT
    for part in relative.parts:
        cursor = cursor / part
        if os.path.lexists(cursor) and stat.S_ISLNK(os.lstat(cursor).st_mode):
            raise ValueError(f"Path traverses symlink: {value}")
    path = (PROJECT_ROOT / relative).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def artifact(path: Path, include_path: bool = True) -> dict[str, Any]:
    metadata = os.lstat(path)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ValueError(f"Artifact is not one regular file: {path}")
    value: dict[str, Any] = {
        "bytes": metadata.st_size,
        "sha256": sha256_file(path),
        "mode": f"{stat.S_IMODE(metadata.st_mode):04o}",
    }
    if include_path:
        value["path"] = str(path.relative_to(PROJECT_ROOT))
    return value


def require_record(value: dict[str, Any], mode: int) -> Path:
    if set(value) != {"path", "bytes", "sha256", "mode"}:
        raise ValueError("EXP-066 artifact record schema drift")
    path = _resolve(value["path"])
    metadata = os.lstat(path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != mode
        or metadata.st_size != value["bytes"]
        or value["mode"] != f"{mode:04o}"
        or sha256_file(path) != value["sha256"]
    ):
        raise ValueError(f"EXP-066 artifact identity drift: {value['path']}")
    return path


def require_inventory(root_value: str, records: list[dict[str, Any]], root_mode: int) -> Path:
    root = _resolve(root_value)
    metadata = os.lstat(root)
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != root_mode:
        raise ValueError(f"EXP-066 asset root mode/type drift: {root_value}")
    expected_names = {record["name"] for record in records}
    observed_names = {path.name for path in root.iterdir() if path.is_file()}
    if observed_names != expected_names:
        raise ValueError(f"EXP-066 asset inventory name drift: {root_value}")
    for record in records:
        path = root / record["name"]
        require_record(
            {
                "path": str(path.relative_to(PROJECT_ROOT)),
                "bytes": record["bytes"],
                "sha256": record["sha256"],
                "mode": record["mode"],
            },
            int(record["mode"], 8),
        )
    return root


def npz_schema(path: Path) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        if len(members) != len(set(members)):
            raise ValueError("NPZ duplicate members")
        if any(not member.endswith(".npy") or "/" in member for member in members):
            raise ValueError("NPZ member layout drift")
        for member in sorted(members):
            with archive.open(member) as source:
                version = np.lib.format.read_magic(source)
                if version == (1, 0):
                    shape, fortran, dtype = np.lib.format.read_array_header_1_0(source)
                elif version == (2, 0):
                    shape, fortran, dtype = np.lib.format.read_array_header_2_0(source)
                else:
                    shape, fortran, dtype = np.lib.format._read_array_header(source, version)
            output[Path(member).stem] = {
                "shape": list(shape), "dtype": str(dtype), "fortran_order": bool(fortran)
            }
    return output


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def environment_identity() -> dict[str, Any]:
    packages = {
        name: importlib.metadata.version(distribution)
        for name, distribution in {
            "numpy": "numpy",
            "scikit_learn": "scikit-learn",
            "torch": "torch",
            "transformers": "transformers",
            "tokenizers": "tokenizers",
            "mlx": "mlx",
            "mlx_lm": "mlx-lm",
            "safetensors": "safetensors",
        }.items()
    }
    return {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "packages": packages,
        "offline_environment": {
            "PYTHONNOUSERSITE": os.environ.get("PYTHONNOUSERSITE"),
            "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE"),
            "TRANSFORMERS_OFFLINE": os.environ.get("TRANSFORMERS_OFFLINE"),
            "TOKENIZERS_PARALLELISM": os.environ.get("TOKENIZERS_PARALLELISM"),
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
            "VECLIB_MAXIMUM_THREADS": os.environ.get("VECLIB_MAXIMUM_THREADS"),
        },
    }


def load_config(config_path: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    config_path = config_path.resolve()
    if config_path != DEFAULT_CONFIG.resolve():
        raise ValueError("EXP-066 requires the frozen config path")
    if artifact(config_path)["mode"] != "0644":
        raise ValueError("EXP-066 config mode drift")
    config = load_json(config_path)
    if (
        config.get("schema_version") != CONFIG_SCHEMA
        or config.get("experiment_id") != EXPERIMENT_ID
        or config.get("run_id") != RUN_ID
        or config.get("rq_id") != "RQ-S3"
        or config.get("tier") != "Major"
        or config.get("model_seed") != 42
        or config.get("labels") != list(LABEL_ORDER)
        or config.get("features") != list(FEATURE_NAMES)
        or config.get("claim_boundary") != CLAIM_BOUNDARY
    ):
        raise ValueError("EXP-066 config identity drift")
    if config.get("outputs") != {
        "public_dir": str(PUBLIC_REL), "private_dir": str(PRIVATE_REL)
    }:
        raise ValueError("EXP-066 output contract drift")
    if config.get("parity") != {
        "rows": 32,
        "m1_probability_atol": 1e-5,
        "m3_probability_atol": 1e-5,
        "feature_atol": 1e-8,
        "standardized_feature_atol": 1e-8,
        "route_score_atol": 1e-8,
        "discrete_exact": True,
        "fallback_allowed": False,
        "output_schema": PARITY_SCHEMA,
    }:
        raise ValueError("EXP-066 parity contract drift")
    expected_access = {
        "exp064_bundle_access": True,
        "exp065_projection_replay_access": True,
        "m1_checkpoint_access": True,
        "m3_base_adapter_head_access": True,
        "original_validation_access": False,
        "historical_validation_npz_access": False,
        "test_access": False,
        "network_access": False,
        "fallback": False,
    }
    if config.get("access") != expected_access:
        raise ValueError("EXP-066 access contract drift")
    if config.get("environment") != environment_identity():
        raise ValueError("EXP-066 unified runtime environment drift")
    sources: dict[str, Path] = {"config": config_path}
    for section in ("prerequisite", "implementation"):
        for name, record in config.get(section, {}).items():
            sources[name] = require_record(record, 0o644)
    if load_json(sources["exp064_completion"]).get("status") != "Complete":
        raise ValueError("EXP-066 EXP-064 prerequisite drift")
    if load_json(sources["exp064_verification"]).get("status") != "Passed":
        raise ValueError("EXP-066 EXP-064 verification drift")
    if load_json(sources["exp065_completion"]).get("status") != "Complete":
        raise ValueError("EXP-066 EXP-065 prerequisite drift")
    if load_json(sources["exp065_verification"]).get("status") != "Passed":
        raise ValueError("EXP-066 EXP-065 verification drift")
    assets = config["runtime_assets"]
    for name, mode in (
        ("bundle_manifest", 0o600),
        ("bundle_parameters", 0o600),
        ("projection", 0o600),
        ("replay", 0o600),
        ("projection_manifest", 0o600),
        ("m3_adapter", 0o600),
        ("m3_head", 0o600),
        ("m3_prompt", 0o644),
        ("m3_base_manifest", 0o644),
    ):
        sources[name] = require_record(assets[name], mode)
    sources["m1_checkpoint_root"] = require_inventory(
        assets["m1_checkpoint_root"], assets["m1_checkpoint_files"], 0o755
    )
    sources["m3_base_root"] = require_inventory(
        assets["m3_base_root"], assets["m3_base_files"], 0o755
    )
    if load_json(sources["projection_manifest"]).get("status") != "MaterializedAwaitingVerification":
        raise ValueError("EXP-066 projection manifest state drift")
    return config, sources


def load_parity_inputs(config: dict[str, Any], sources: dict[str, Path]) -> tuple[list[str], dict[str, np.ndarray]]:
    replay_path = sources["replay"]
    with np.load(replay_path, allow_pickle=False) as archive:
        if set(archive.files) != {"ordinal", "m1_probabilities", "m3_probabilities"}:
            raise ValueError("EXP-066 replay key drift")
        replay = {name: np.asarray(archive[name]) for name in archive.files}
    if (
        replay["ordinal"].shape != (32,)
        or replay["ordinal"].dtype != np.int16
        or replay["m1_probabilities"].shape != (32, 6)
        or replay["m3_probabilities"].shape != (32, 6)
        or replay["m1_probabilities"].dtype != np.float32
        or replay["m3_probabilities"].dtype != np.float32
    ):
        raise ValueError("EXP-066 replay array contract drift")
    requested = replay["ordinal"].astype(int).tolist()
    requested_set = set(requested)
    texts: dict[int, str] = {}
    with sources["projection"].open("r", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != {
                "ordinal", "opaque_component_group", "text"
            }:
                raise ValueError("EXP-066 projection row schema drift")
            ordinal = row["ordinal"]
            if ordinal in requested_set:
                if ordinal in texts or type(row["text"]) is not str:
                    raise ValueError("EXP-066 projection selected row drift")
                texts[ordinal] = row["text"]
    if set(texts) != requested_set:
        raise ValueError("EXP-066 projection/replay ordinal alignment drift")
    return [texts[value] for value in requested], replay


def build_output_arrays(
    runtime: runtime_core.PhaseARuntime,
    texts: list[str],
    replay: dict[str, np.ndarray],
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    rows = len(texts)
    arrays = {
        "ordinal": np.ascontiguousarray(replay["ordinal"], dtype="<i2"),
        "m1_probabilities": np.empty((rows, 6), dtype="<f4"),
        "m3_probabilities": np.empty((rows, 6), dtype="<f4"),
        "features": np.empty((rows, 14), dtype="<f8"),
        "standardized_features": np.empty((rows, 14), dtype="<f8"),
        "route_score": np.empty(rows, dtype="<f8"),
        "route_mask": np.empty(rows, dtype=np.uint8),
        "m1_prediction": np.empty((rows, 6), dtype=np.uint8),
        "m3_prediction": np.empty((rows, 6), dtype=np.uint8),
        "final_prediction": np.empty((rows, 6), dtype=np.uint8),
        "selected_path": np.empty(rows, dtype=np.uint8),
        "neutral": np.empty(rows, dtype=np.uint8),
        "character_length": np.empty(rows, dtype="<i4"),
        "m1_token_length": np.empty(rows, dtype="<i4"),
    }
    for index, text in enumerate(texts):
        record = runtime.parity_record(text)
        arrays["m1_probabilities"][index] = record["m1_probabilities"]
        arrays["m3_probabilities"][index] = record["m3_probabilities"]
        arrays["features"][index] = record["features"]
        arrays["standardized_features"][index] = record["standardized_features"]
        arrays["route_score"][index] = record["route_score"]
        arrays["route_mask"][index] = int(record["route_eligible"])
        arrays["m1_prediction"][index] = (
            record["m1_probabilities"] >= runtime.bundle.m1_threshold
        ).astype(np.uint8)
        arrays["m3_prediction"][index] = (
            record["m3_probabilities"] >= runtime.bundle.m3_threshold
        ).astype(np.uint8)
        arrays["final_prediction"][index] = record["final_prediction"]
        arrays["selected_path"][index] = record["selected_path"]
        arrays["neutral"][index] = int(record["neutral"])
        arrays["character_length"][index] = record["character_length"]
        arrays["m1_token_length"][index] = record["m1_token_length"]
    errors = {
        "m1_replay_max_abs_error": float(
            np.max(np.abs(arrays["m1_probabilities"] - replay["m1_probabilities"]))
        ),
        "m3_replay_max_abs_error": float(
            np.max(np.abs(arrays["m3_probabilities"] - replay["m3_probabilities"]))
        ),
    }
    return arrays, errors


def npz_bytes(arrays: dict[str, np.ndarray]) -> bytes:
    buffer = BytesIO()
    np.savez(buffer, **arrays)
    return buffer.getvalue()


def _create(path: Path, payload: bytes, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, mode)
    with os.fdopen(descriptor, "wb") as target:
        target.write(payload)
        target.flush()
        os.fsync(target.fileno())
    os.chmod(path, mode)


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    output: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in PUBLIC_SENSITIVE_KEYS:
                output.append(path)
            output.extend(public_sensitive_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            output.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    return output


def _freeze(public_dir: Path, sources: dict[str, Path]) -> dict[str, Any]:
    frozen = public_dir / "frozen-sources"
    frozen.mkdir(mode=0o755)
    result: dict[str, Any] = {}
    for name in ("config", "protocol", "runtime", "runner", "verifier", "tests", "finalizer"):
        source = sources[name]
        target = frozen / ("config.json" if name == "config" else source.name)
        _create(target, source.read_bytes(), 0o644)
        result[name] = artifact(target)
    return result


def _assert_outputs_absent(public_dir: Path, private_dir: Path) -> None:
    for path in (public_dir, private_dir):
        if os.path.lexists(path):
            raise FileExistsError(f"EXP-066 output already exists: {path.relative_to(PROJECT_ROOT)}")
        _resolve(path.relative_to(PROJECT_ROOT))


def acquire_lock(config: dict[str, Any]):
    lock_path = _resolve(config["heavy_workload_lock"])
    descriptor = lock_path.open("r+")
    try:
        fcntl.flock(descriptor.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        descriptor.close()
        raise RuntimeError("EXP-066 heavy workload lock is busy")
    return descriptor


def preflight(config_path: Path) -> dict[str, Any]:
    config, sources = load_config(config_path)
    public_dir = _resolve(config["outputs"]["public_dir"])
    private_dir = _resolve(config["outputs"]["private_dir"])
    _assert_outputs_absent(public_dir, private_dir)
    texts, replay = load_parity_inputs(config, sources)
    del texts, replay
    lock = acquire_lock(config)
    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    lock.close()
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": "Ready",
        "rows": 32,
        "unified_environment": True,
        "public_output_absent": True,
        "private_output_absent": True,
        "original_validation_access": False,
        "test_access": False,
        "model_loaded": False,
    }


def execute(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    started_at = utc_now()
    started = time.perf_counter()
    config, sources = load_config(config_path)
    public_dir = _resolve(config["outputs"]["public_dir"])
    private_dir = _resolve(config["outputs"]["private_dir"])
    _assert_outputs_absent(public_dir, private_dir)
    texts, replay = load_parity_inputs(config, sources)
    lock = acquire_lock(config)
    public_dir.mkdir(mode=0o755)
    os.chmod(public_dir, 0o755)
    private_dir.mkdir(mode=0o700)
    os.chmod(private_dir, 0o700)
    implementation = _freeze(public_dir, sources)
    claim = {
        "schema_version": "exp-066-run-claim-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "status": "Claimed",
        "claimed_at_utc": started_at,
        "config": artifact(config_path),
        "one_shot": True,
        "cli_gate": "closed_pending_independent_parity",
    }
    _create(public_dir / "run-claim.json", canonical_json_bytes(claim), 0o644)
    try:
        import mlx.core as mx

        mx.reset_peak_memory()
        load_started = time.perf_counter()
        runtime = runtime_core.build_real_runtime(config, PROJECT_ROOT)
        load_seconds = time.perf_counter() - load_started
        arrays, errors = build_output_arrays(runtime, texts, replay)
        if errors["m1_replay_max_abs_error"] > config["parity"]["m1_probability_atol"]:
            raise RuntimeError("EXP-066 M1 runtime probability replay failed")
        if errors["m3_replay_max_abs_error"] > config["parity"]["m3_probability_atol"]:
            raise RuntimeError("EXP-066 M3 runtime probability replay failed")
        parity_path = private_dir / "parity-output.npz"
        _create(parity_path, npz_bytes(arrays), 0o600)
        if npz_schema(parity_path) != PARITY_SCHEMA:
            raise RuntimeError("EXP-066 written parity NPZ schema drift")
        runtime_manifest = {
            "schema_version": PRIVATE_SCHEMA,
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "status": "CompletedAwaitingVerification",
            "environment": config["environment"],
            "runtime_assets": config["runtime_assets"],
            "prerequisite": config["prerequisite"],
            "implementation": config["implementation"],
            "parity_contract": config["parity"],
            "aggregate_replay_errors": errors,
            "route_count": int(np.sum(arrays["route_mask"])),
            "fallback_count": 0,
            "output": {
                "logical_name": parity_path.name,
                **artifact(parity_path, include_path=False),
                "schema": PARITY_SCHEMA,
            },
            "access_attestation": config["access"],
            "no_classification_metrics_computed": True,
            "claim_boundary": CLAIM_BOUNDARY,
        }
        manifest_path = private_dir / "runtime-manifest.json"
        _create(manifest_path, canonical_json_bytes(runtime_manifest), 0o600)
        private_outputs = {
            "parity_output": {
                "logical_name": parity_path.name,
                **artifact(parity_path, include_path=False),
                "schema_sha256": canonical_digest(PARITY_SCHEMA),
            },
            "runtime_manifest": {
                "logical_name": manifest_path.name,
                **artifact(manifest_path, include_path=False),
            },
        }
        access = {
            "exp064_bundle_accessed": True,
            "exp065_projection_replay_accessed": True,
            "m1_checkpoint_accessed": True,
            "m3_base_adapter_head_accessed": True,
            "original_validation_accessed": False,
            "historical_validation_npz_accessed": False,
            "test_accessed": False,
            "network_accessed": False,
            "fallback_count": 0,
        }
        resource_record = {
            "model_load_seconds": load_seconds,
            "elapsed_seconds": time.perf_counter() - started,
            "ru_maxrss_raw": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
            "mlx_active_bytes": int(mx.get_active_memory()),
            "mlx_cache_bytes": int(mx.get_cache_memory()),
            "mlx_peak_bytes": int(mx.get_peak_memory()),
        }
        run = {
            "schema_version": "exp-066-run-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "tier": "Major",
            "rq_id": "RQ-S3",
            "stage": "headless-runtime-32-row-parity",
            "status": "CompletedAwaitingVerification",
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
            "command": f"{sys.executable} {Path(__file__).relative_to(PROJECT_ROOT)} --config {config_path.relative_to(PROJECT_ROOT)}",
            "working_directory": str(PROJECT_ROOT),
            "environment": config["environment"],
            "implementation": implementation,
            "prerequisite": config["prerequisite"],
            "contract": {
                "rows": 32,
                "label_count": 6,
                "feature_count": 14,
                "m1_probability_atol": 1e-5,
                "m3_probability_atol": 1e-5,
                "fallback_allowed": False,
                "no_classification_metrics": True,
            },
            "aggregate_parity": {
                **errors,
                "route_count": int(np.sum(arrays["route_mask"])),
                "fallback_count": 0,
            },
            "private_outputs": private_outputs,
            "access_attestation": access,
            "resources": resource_record,
            "privacy": {"row_level_public": False, "public_scan_passed": True},
            "cli_gate": "closed_pending_independent_parity",
            "claim_boundary": CLAIM_BOUNDARY,
            "warnings": [],
        }
        violations = public_sensitive_paths(run)
        if violations:
            raise RuntimeError(f"EXP-066 public privacy schema violation: {violations}")
        _create(
            public_dir / "stdout.log",
            (
                f"{EXPERIMENT_ID} {RUN_ID}\nstatus=CompletedAwaitingVerification\n"
                "rows=32\nfallback_count=0\noriginal_validation_access=false\n"
                "test_access=false\ncli_gate=closed_pending_independent_parity\n"
            ).encode("utf-8"),
            0o644,
        )
        _create(public_dir / "run.json", canonical_json_bytes(run), 0o644)
        return run
    except Exception as error:
        private_failure = {
            "schema_version": "exp-066-private-failure-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "status": "Failed",
            "failed_at_utc": utc_now(),
            "error_type": type(error).__name__,
            "error": str(error),
        }
        if not os.path.lexists(private_dir / "failure.json"):
            _create(private_dir / "failure.json", canonical_json_bytes(private_failure), 0o600)
        public_failure = {
            "schema_version": "exp-066-run-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "status": "Failed",
            "failed_at_utc": utc_now(),
            "error_type": type(error).__name__,
            "fallback_count": 0,
            "original_validation_accessed": False,
            "test_accessed": False,
            "cli_gate": "closed",
            "claim_boundary": CLAIM_BOUNDARY,
        }
        if not os.path.lexists(public_dir / "run.json"):
            _create(public_dir / "run.json", canonical_json_bytes(public_failure), 0o644)
        raise
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = preflight(args.config) if args.check else execute(args.config)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
