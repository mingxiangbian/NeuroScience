#!/usr/bin/env python3
"""Frozen EXP-070 formal linear-probe consumer.

The runner has four deliberately separate stages:

``static``
    A no-result source and implementation gate.  It does not import NumPy or
    scikit-learn, parse labels, or load NPY array values.
``initialize``
    Creates a fresh append-only formal namespace after a completed static gate.
``fit-fold``
    Fits exactly one next outer fold.  Only labels from that fold's outer-train
    partition are decoded.  A private NPZ is followed by an external JSON seal.
``assemble``
    Runs only after all five fold seals exist.  It is the first stage that
    decodes outer-heldout labels, and it computes aggregate metrics, the shared
    bootstrap, votes, and the label-shuffle validity control.

No stage loads a model, runs a forward pass, or accesses validation/test data.
"""

from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import resource
import shutil
import stat
import struct
import sys
import time
from typing import Any, Iterator, Mapping, Sequence
import warnings


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
DEFAULT_STATIC_CONFIG = MODULE_DIR / "configs" / "exp-070-formal-probe-preflight.json"
DEFAULT_FORMAL_CONFIG = MODULE_DIR / "configs" / "exp-070-formal-probe.json"

EXPERIMENT_ID = "EXP-070"
ROWS = 3360
FOLDS = (0, 1, 2, 3, 4)
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
PRIMARY_COLUMNS = (0, 1, 3, 4, 5)
ALL_POINTS = ("H-1", "H7", "H15", "H19", "H20", "H27", "H31", "H35", "HF")
CONFIRMATION_POINTS = ("H19", "H27", "HF")
VOTING_POINTS = ("H27", "HF")
PRE_LORA_POINTS = ("H-1", "H7", "H15", "H19")
SHUFFLE_SEEDS = (2026082711, 2026082712, 2026082713)
BOOTSTRAP_SEED = 2026082701
BOOTSTRAP_REPLICATES = 2000
THRESHOLD_INDICES = tuple(range(5, 96))
COMPARISON_TOLERANCE = 1e-12

MAIN_KEYS = tuple(
    [f"frozen:{point}" for point in ALL_POINTS]
    + [f"m3-s42:{point}" for point in ALL_POINTS]
    + [f"m3-s43:{point}" for point in CONFIRMATION_POINTS]
    + [f"m3-s44:{point}" for point in CONFIRMATION_POINTS]
)
SHUFFLE_CONDITIONS = tuple(
    [f"frozen:{point}" for point in VOTING_POINTS]
    + [f"m3-s42:{point}" for point in VOTING_POINTS]
    + [f"m3-s43:{point}" for point in VOTING_POINTS]
    + [f"m3-s44:{point}" for point in VOTING_POINTS]
)
SHUFFLE_KEYS = tuple(
    f"shuffle-{shuffle_seed}|{condition}"
    for shuffle_seed in SHUFFLE_SEEDS
    for condition in SHUFFLE_CONDITIONS
)
WORKER_IDS = tuple(
    ["base"]
    + [f"m3-s42-f{fold}" for fold in FOLDS]
    + [f"m3-s43-f{fold}" for fold in FOLDS]
    + [f"m3-s44-f{fold}" for fold in FOLDS]
)

MAIN_FITS_PER_FOLD = 24 * 5 * 6
SHUFFLE_FITS_PER_FOLD = 24 * 6
TOTAL_MAIN_FITS = MAIN_FITS_PER_FOLD * 5
TOTAL_SHUFFLE_FITS = SHUFFLE_FITS_PER_FOLD * 5
TOTAL_BINARY_FITS = TOTAL_MAIN_FITS + TOTAL_SHUFFLE_FITS

PROBE_ENVIRONMENT = {
    "python_executable": "/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python",
    "python_version": "3.10.20",
    "architecture": "arm64",
    "packages": {
        "numpy": "2.2.6",
        "scikit-learn": "1.7.2",
        "scipy": "1.15.3",
        "joblib": "1.5.3",
    },
    "thread_environment": {
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    },
}

EXPECTED_CONFIG_METHOD_NORMALIZED_SHA256 = (
    "5ec0e5d050d08b70fdc86badf77e0f5dae72282bf060e173135a37af8e910e3f"
)
STATIC_CHECKS = [
    "config_identity",
    "method_identity",
    "implementation_identity",
    "implementation_import_boundary",
    "synthetic_test_suite_34_of_34",
    "environment_identity",
    "authorization_boundary",
    "access_boundary",
    "source_recovery_completion",
    "source_snapshot_identity",
    "sixteen_matrix_identities",
    "sixteen_matrix_headers",
    "label_source_identity_only",
    "static_public_inventory_modes_links",
    "static_private_inventory_modes_links",
    "static_runner_payload",
    "static_private_contract",
    "formal_roots_absent",
    "consumer_private_budget",
    "public_privacy",
    "source_unchanged",
    "no_numpy_or_sklearn_import",
    "no_model_or_runner_import",
    "no_array_or_label_value_read",
    "no_probe_threshold_shuffle_bootstrap_metric",
]

EXPECTED_SOURCE = {
    "extraction_complete": {
        "path": (
            "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
            "exp-070-layerwise-probes/formal-extraction-verification-attempt-2/"
            "extraction-complete.json"
        ),
        "bytes": 2302,
        "mode": "0644",
        "sha256": "02755a7985e83e988fa5f0e3e2fbfaa22c7255ca1cfa7a8f2191ea5f222cb5cb",
    },
    "extraction_verification": {
        "path": (
            "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
            "exp-070-layerwise-probes/formal-extraction-verification-attempt-2/verification.json"
        ),
        "bytes": 7097,
        "mode": "0644",
        "sha256": "21e41625527702a4d8534225692a5d06fbf672add51eb67395af2a6e8803e5f5",
    },
    "source_snapshot_claim": {
        "path": (
            "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
            "exp-070-layerwise-probes/formal-extraction-verification-attempt-2/"
            "source-snapshot-claim.json"
        ),
        "bytes": 1544,
        "mode": "0644",
        "sha256": "a2126108644b8221d2ae339f27c9c586aabe528f71d0dd8a95d15fd096977b2e",
    },
    "extraction_run": {
        "path": (
            "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
            "exp-070-layerwise-probes/formal-extraction-attempt-1/extraction.json"
        ),
        "bytes": 1596,
        "mode": "0644",
        "sha256": "1ad33d4197517993a07e2af7f9fea14d7185e537a52376c1a400c91237793cfe",
    },
    "extraction_manifest": {
        "path": (
            "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
            "exp-070-layerwise-probes/formal-extraction-attempt-1/extraction-manifest.json"
        ),
        "bytes": 10612,
        "mode": "0600",
        "sha256": "ef8092d7c8704199d7f5d8dce0c240418fde62a0b71ff4ba07a9da45c151d347",
    },
    "row_contract": {
        "path": (
            "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
            "exp-070-layerwise-probes/formal-extraction-attempt-1/row-contract.npz"
        ),
        "bytes": 31014,
        "mode": "0600",
        "sha256": "f85a250cb2809f1cf5f33f6faf21dccc1eacccae3cbdc8adb839d4ae97f22308",
    },
    "fold_manifest_public": {
        "path": (
            "experiments/stack-overflow-emotion-gold/oof-router/runs/"
            "exp-058-fold-manifest-preflight-attempt-2/fold-manifest.public.jsonl"
        ),
        "bytes": 739200,
        "mode": "0644",
        "sha256": "82929b1d837ceb9825c5bc39a8fea18f6d0736fca42aad630f3788b1ff8139d8",
    },
    "fold_manifest_private": {
        "path": (
            "experiments/stack-overflow-emotion-gold/oof-router/private/"
            "exp-058-fold-manifest-preflight-attempt-2/fold-manifest.private.jsonl"
        ),
        "bytes": 979748,
        "mode": "0600",
        "sha256": "d518e97c3332f2d59ea3556aecbb3a8cf9253438aee5ba02cd2ab105663862af",
    },
}

EXTRACTION_PRIVATE_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
    "exp-070-layerwise-probes/formal-extraction-attempt-1"
)


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


def require_canonical_json(path: Path) -> Any:
    value = strict_json(path)
    if path.read_bytes() != canonical_json_bytes(value):
        raise ValueError(f"Non-canonical JSON artifact: {path}")
    return value


def strict_json_bytes(payload: bytes) -> Any:
    return json.loads(
        payload,
        object_pairs_hook=_unique_object,
        parse_constant=_no_constant,
    )


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bytes_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def resolve_project(relative: str) -> Path:
    pure = PurePosixPath(relative)
    if type(relative) is not str or not relative or pure.is_absolute() or pure.as_posix() != relative:
        raise ValueError("Unsafe project path")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("Unsafe project path")
    path = PROJECT_ROOT.joinpath(*pure.parts)
    current = PROJECT_ROOT
    for part in pure.parts:
        current = current / part
        if os.path.lexists(current) and current.is_symlink():
            raise ValueError(f"Symlink path rejected: {relative}")
    return path


def artifact(path: Path, *, logical_name: str | None = None) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError(f"Unsafe or missing artifact: {path}")
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


def require_record(record: Mapping[str, Any]) -> Path:
    if set(record) != {"path", "bytes", "mode", "sha256"}:
        raise ValueError("Artifact record schema drift")
    path = resolve_project(str(record["path"]))
    if artifact(path) != dict(record):
        raise ValueError(f"Artifact identity drift: {record['path']}")
    return path


def iter_artifact_records(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, Mapping):
        if set(value) == {"path", "bytes", "mode", "sha256"}:
            yield dict(value)
            return
        for item in value.values():
            yield from iter_artifact_records(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_artifact_records(item)


def create_json_once(path: Path, value: Any, *, private: bool) -> dict[str, Any]:
    if os.path.lexists(path):
        raise FileExistsError(f"Refusing to overwrite {path}")
    payload = canonical_json_bytes(value)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600 if private else 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    os.chmod(path, 0o600 if private else 0o644)
    return artifact(path, logical_name=path.name) if private else artifact(path)


def ensure_new_directory(path: Path, *, private: bool) -> None:
    if os.path.lexists(path):
        raise FileExistsError(f"Output root already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir(mode=0o700 if private else 0o755)
    os.chmod(path, 0o700 if private else 0o755)


def require_safe_directory(path: Path, *, private: bool) -> None:
    if path.is_symlink() or not path.is_dir() or path.stat().st_nlink < 1:
        raise ValueError(f"Unsafe directory: {path}")
    expected = "0700" if private else "0755"
    if file_mode(path) != expected:
        raise PermissionError(f"Directory mode drift: {path}")
    entries = list(path.rglob("*"))
    if any(item.is_symlink() for item in entries):
        raise PermissionError(f"Nested symlink rejected: {path}")
    if any(not item.is_file() and not item.is_dir() for item in entries):
        raise PermissionError(f"Special filesystem entry rejected: {path}")


def _read_exact(handle: Any, size: int) -> bytes:
    value = handle.read(size)
    if len(value) != size:
        raise ValueError("Truncated NPY header")
    return value


def read_npy_header(path: Path) -> dict[str, Any]:
    """Read only the NPY header; this function never imports NumPy."""
    with path.open("rb") as handle:
        if _read_exact(handle, 6) != b"\x93NUMPY":
            raise ValueError(f"Invalid NPY magic: {path}")
        major, minor = _read_exact(handle, 2)
        if (major, minor) == (1, 0):
            header_size = struct.unpack("<H", _read_exact(handle, 2))[0]
        elif major in (2, 3) and minor == 0:
            header_size = struct.unpack("<I", _read_exact(handle, 4))[0]
        else:
            raise ValueError("Unsupported NPY version")
        if not 0 < header_size <= 65536:
            raise ValueError("Unsafe NPY header size")
        header = ast.literal_eval(_read_exact(handle, header_size).decode("latin1").strip())
    if set(header) != {"descr", "fortran_order", "shape"}:
        raise ValueError("NPY header schema drift")
    return {
        "dtype": header["descr"],
        "fortran_order": header["fortran_order"],
        "shape": list(header["shape"]),
    }


def _config_kind(config: Mapping[str, Any]) -> str:
    schema = str(config.get("schema_version", ""))
    if "preflight" in schema:
        return "static"
    if "formal-probe" in schema or "formal_probe" in schema:
        return "formal"
    raise ValueError("Unrecognized EXP-070 probe config schema")


def _method_from_config(config: Mapping[str, Any]) -> Any:
    for key in ("method", "frozen_method", "probe_method"):
        if key in config:
            return config[key]
    raise ValueError("Config lacks exact frozen method object")


def _normalize_json_numbers(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_json_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_json_numbers(item) for item in value]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return value


def config_method_sha256(config: Mapping[str, Any]) -> str:
    return bytes_sha256(
        canonical_json_bytes(_normalize_json_numbers(_method_from_config(config)))
    )


def validate_method_contract(config: Mapping[str, Any]) -> None:
    if config_method_sha256(config) != EXPECTED_CONFIG_METHOD_NORMALIZED_SHA256:
        raise ValueError("EXP-070 frozen probe method drift")


def validate_environment_config(config: Mapping[str, Any]) -> None:
    value = config.get("environment") or config.get("environments", {}).get("probe")
    if value != PROBE_ENVIRONMENT:
        raise ValueError("EXP-070 probe environment contract drift")


def validate_probability_artifact_contract(config: Mapping[str, Any]) -> None:
    value = config.get("private_probability_artifact")
    if not isinstance(value, Mapping):
        raise ValueError("Missing EXP-070 private probability artifact contract")
    expected_arrays = {
        "outer_train_ordinals": {"shape": [2688], "dtype": "<i4"},
        "outer_heldout_ordinals": {"shape": [672], "dtype": "<i4"},
        "main_inner_oof_probability": {"shape": [24, 2688, 6], "dtype": "<f8"},
        "main_outer_heldout_probability": {"shape": [24, 672, 6], "dtype": "<f8"},
        "main_threshold_index": {"shape": [24], "dtype": "<i2"},
        "main_n_iter": {"shape": [24, 5, 6], "dtype": "<i4"},
        "shuffle_outer_heldout_probability": {"shape": [3, 8, 672, 6], "dtype": "<f8"},
        "shuffle_n_iter": {"shape": [3, 8, 6], "dtype": "<i4"},
    }
    if (
        value.get("writer") != "numpy.savez"
        or value.get("compressed") is not False
        or value.get("directory_mode") != "0700"
        or value.get("file_mode") != "0600"
        or value.get("layout") != "C"
        or value.get("seal_written_last") is not True
        or value.get("npz_without_seal") != "terminal_orphan_no_same_attempt_resume"
        or value.get("arrays") != expected_arrays
        or value.get("final_verifier") != "probability_only_no_refit"
    ):
        raise ValueError("EXP-070 private probability artifact contract drift")
    forbidden = {
        "labels", "predictions", "sample_ids", "component_ids", "coefficients",
        "scalers", "representations", "text",
    }
    if set(value.get("forbidden_members", [])) != forbidden:
        raise ValueError("EXP-070 forbidden private member contract drift")


def require_implementation_records(config: Mapping[str, Any]) -> None:
    implementation = config.get("implementation")
    if not isinstance(implementation, Mapping) or set(implementation) != {"protocol", "runner", "verifier", "tests"}:
        raise ValueError("EXP-070 implementation inventory drift")
    for record in implementation.values():
        if not isinstance(record, Mapping) or record.get("sha256") == "TBD" or record.get("bytes") == 0:
            raise ValueError("EXP-070 implementation identity is not frozen")
        require_record(record)


def validate_output_contract(config: Mapping[str, Any]) -> None:
    outputs = config.get("outputs")
    if not isinstance(outputs, Mapping):
        raise ValueError("Missing EXP-070 output contract")
    if outputs.get("preflight_public_success_allowlist") != [
        "static.json", "static-verification.json", "no-result-complete.json"
    ]:
        raise ValueError("EXP-070 preflight public allowlist drift")
    if outputs.get("preflight_private_allowlist") != ["input-contract-manifest.json"]:
        raise ValueError("EXP-070 preflight private allowlist drift")
    if outputs.get("formal_public_awaiting_verification_allowlist") != ["run-claim.json", "probe.json"]:
        raise ValueError("EXP-070 formal public allowlist drift")
    expected_fold_files = [name for fold in FOLDS for name in (f"f{fold}.npz", f"f{fold}.json")]
    if outputs.get("formal_private_fold_allowlist") != expected_fold_files:
        raise ValueError("EXP-070 formal fold allowlist drift")
    if outputs.get("formal_private_success_allowlist") != [
        "input-manifest.json", *[f"folds/{name}" for name in expected_fold_files], "probe-manifest.json"
    ]:
        raise ValueError("EXP-070 formal private allowlist drift")
    roots = [
        resolve_project(str(outputs[key]))
        for key in (
            "preflight_public_root",
            "preflight_private_root",
            "formal_public_root",
            "formal_private_root",
        )
    ]
    if len({path.resolve() for path in roots}) != 4:
        raise ValueError("EXP-070 output roots must be distinct")
    extraction_root = resolve_project(EXTRACTION_PRIVATE_ROOT).resolve()
    if any(path.resolve() == extraction_root or extraction_root in path.resolve().parents for path in roots):
        raise ValueError("EXP-070 output root overlaps immutable extraction source")


def observed_environment() -> dict[str, Any]:
    return {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "scikit-learn", "scipy", "joblib")
        },
        "thread_environment": {
            key: os.environ.get(key)
            for key in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
    }


def require_environment(config: Mapping[str, Any]) -> dict[str, Any]:
    validate_environment_config(config)
    observed = observed_environment()
    if observed != PROBE_ENVIRONMENT:
        raise EnvironmentError("EXP-070 probe runtime identity drift")
    if os.environ.get("PYTHONNOUSERSITE") != "1":
        raise EnvironmentError("Required environment variable drift: PYTHONNOUSERSITE")
    for key, expected in PROBE_ENVIRONMENT["thread_environment"].items():
        if os.environ.get(key) != expected:
            raise EnvironmentError(f"Required environment variable drift: {key}")
    return observed


def _output_path(config: Mapping[str, Any], key: str) -> Path:
    outputs = config.get("outputs")
    if not isinstance(outputs, Mapping):
        raise ValueError(f"Missing output key: {key}")
    kind = _config_kind(config)
    translated = {
        ("static", "public_root"): "preflight_public_root",
        ("static", "private_root"): "preflight_private_root",
        ("formal", "public_root"): "formal_public_root",
        ("formal", "private_root"): "formal_private_root",
    }.get((kind, key), key)
    if translated not in outputs:
        raise ValueError(f"Missing output key: {key}")
    return resolve_project(str(outputs[translated]))


def public_root(config: Mapping[str, Any]) -> Path:
    return _output_path(config, "public_root")


def private_root(config: Mapping[str, Any]) -> Path:
    return _output_path(config, "private_root")


def _validate_identity(config: Mapping[str, Any], *, kind: str) -> None:
    if config.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("EXP-070 config experiment identity drift")
    if type(config.get("run_id")) is not str or type(config.get("attempt_id")) is not str:
        raise ValueError("EXP-070 config run identity drift")
    if _config_kind(config) != kind:
        raise ValueError(f"Expected {kind} config")
    expected = {
        "static": (
            "exp-070-formal-probe-preflight-config-v1",
            "exp-070-layerwise-probe-formal-probe-preflight",
            "formal-probe-preflight-attempt-1",
            "formal-probe-consumer-preflight",
        ),
        "formal": (
            "exp-070-formal-probe-config-v1",
            "exp-070-layerwise-probe-formal-probe",
            "formal-probe-attempt-1",
            "formal-probe",
        ),
    }[kind]
    if (
        config.get("schema_version") != expected[0]
        or config.get("run_id") != expected[1]
        or config.get("attempt_id") != expected[2]
        or config.get("stage") != expected[3]
        or config.get("rq_id") != "RQ-S4.1"
    ):
        raise ValueError("EXP-070 probe config identity drift")
    validate_method_contract(config)
    validate_environment_config(config)
    validate_probability_artifact_contract(config)
    validate_output_contract(config)
    _resource_contract(config)


def load_config(path: Path, *, expected_kind: str) -> dict[str, Any]:
    expected_default = DEFAULT_STATIC_CONFIG if expected_kind == "static" else DEFAULT_FORMAL_CONFIG
    if path.resolve() != expected_default.resolve():
        raise ValueError(f"Only frozen {expected_kind} config is accepted")
    config = strict_json(path)
    if not isinstance(config, dict):
        raise ValueError("Config root must be an object")
    _validate_identity(config, kind=expected_kind)
    return config


def require_frozen_sources(config: Mapping[str, Any], *, headers_only: bool) -> dict[str, Any]:
    """Validate the attempt-2 chain and all sixteen cache artifacts.

    ``headers_only`` is documented at the call site for the static stage.  This
    function never loads array values in either mode.
    """
    del headers_only
    source_config = config.get("source")
    if not isinstance(source_config, Mapping):
        raise ValueError("EXP-070 config lacks source binding")
    if set(source_config) != {
        "snapshot_sha256", "formal_extraction_protocol", "formal_extraction_config",
        "formal_extraction_claim", "formal_extraction_run", "recovery_protocol",
        "recovery_config", "recovery_snapshot_claim", "recovery_verification",
        "recovery_completion", "private_input_manifest", "private_row_contract",
        "private_extraction_manifest", "row_identity", "label_source", "matrix_root",
        "matrices",
    }:
        raise ValueError("EXP-070 source binding schema drift")
    if source_config.get("snapshot_sha256") != "cdcde7fd617aee9d6189d6a7e87778a6617cdf0a6db658a397928b7e20910bad":
        raise ValueError("EXP-070 config source snapshot drift")
    if source_config.get("matrix_root") != f"{EXTRACTION_PRIVATE_ROOT}/extraction":
        raise ValueError("EXP-070 matrix-root drift")
    if (
        source_config.get("recovery_completion") != EXPECTED_SOURCE["extraction_complete"]
        or source_config.get("recovery_verification") != EXPECTED_SOURCE["extraction_verification"]
        or source_config.get("recovery_snapshot_claim") != EXPECTED_SOURCE["source_snapshot_claim"]
        or source_config.get("formal_extraction_run") != EXPECTED_SOURCE["extraction_run"]
        or source_config.get("private_extraction_manifest") != EXPECTED_SOURCE["extraction_manifest"]
        or source_config.get("private_row_contract") != EXPECTED_SOURCE["row_contract"]
    ):
        raise ValueError("EXP-070 extraction source record drift")
    label_source = source_config.get("label_source")
    if (
        not isinstance(label_source, Mapping)
        or label_source.get("private_fold_manifest") != EXPECTED_SOURCE["fold_manifest_private"]
        or label_source.get("public_fold_manifest") != EXPECTED_SOURCE["fold_manifest_public"]
        or label_source.get("train_jsonl_access") is not False
        or label_source.get("row_order") != "file_order_must_match_extraction_row_identity"
    ):
        raise ValueError("EXP-070 label source binding drift")
    for record in iter_artifact_records(source_config):
        require_record(record)
    for record in iter_artifact_records(config.get("parent_method")):
        require_record(record)
    for expected in EXPECTED_SOURCE.values():
        require_record(expected)

    completion = strict_json(resolve_project(EXPECTED_SOURCE["extraction_complete"]["path"]))
    if (
        completion.get("status") != "Complete"
        or completion.get("formal_extraction_complete") is not True
        or completion.get("probe_fitting_authorized") is not False
        or completion.get("exp070_complete") is not False
        or completion.get("source_mutated") is not False
    ):
        raise ValueError("EXP-070 extraction completion gate drift")
    claim = strict_json(resolve_project(EXPECTED_SOURCE["source_snapshot_claim"]["path"]))
    if claim.get("source_snapshot_sha256") != "cdcde7fd617aee9d6189d6a7e87778a6617cdf0a6db658a397928b7e20910bad":
        raise ValueError("EXP-070 extraction snapshot identity drift")
    verification = strict_json(resolve_project(EXPECTED_SOURCE["extraction_verification"]["path"]))
    if verification.get("status") != "Passed" or verification.get("failed_count") != 0:
        raise ValueError("EXP-070 extraction verification gate drift")

    manifest_path = resolve_project(EXPECTED_SOURCE["extraction_manifest"]["path"])
    manifest = strict_json(manifest_path)
    workers = manifest.get("workers")
    if not isinstance(workers, list) or [item.get("worker_id") for item in workers] != list(WORKER_IDS):
        raise ValueError("EXP-070 worker inventory/order drift")
    extraction_root = resolve_project(EXTRACTION_PRIVATE_ROOT)
    configured_matrices = source_config.get("matrices")
    if not isinstance(configured_matrices, list) or [item.get("worker_id") for item in configured_matrices] != list(WORKER_IDS):
        raise ValueError("EXP-070 configured matrix inventory/order drift")
    observed_workers: list[dict[str, Any]] = []
    for item, configured in zip(workers, configured_matrices, strict=True):
        worker_id = item["worker_id"]
        worker_dir = extraction_root / "extraction" / worker_id
        matrix = worker_dir / "representations.npy"
        worker_json = worker_dir / "worker.json"
        if item.get("output") != artifact(matrix, logical_name=f"{worker_id}/representations.npy"):
            raise ValueError(f"EXP-070 matrix identity drift: {worker_id}")
        if configured.get("artifact") != artifact(matrix):
            raise ValueError(f"EXP-070 configured matrix identity drift: {worker_id}")
        if item.get("manifest") != artifact(worker_json, logical_name=f"{worker_id}/worker.json"):
            raise ValueError(f"EXP-070 worker-manifest identity drift: {worker_id}")
        header = read_npy_header(matrix)
        points = 9 if worker_id == "base" or worker_id.startswith("m3-s42-") else 3
        expected_points = list(ALL_POINTS if points == 9 else CONFIRMATION_POINTS)
        expected_kind = "frozen" if worker_id == "base" else "m3"
        expected_seed = None if worker_id == "base" else int(worker_id.split("-")[1][1:])
        expected_fold = None if worker_id == "base" else int(worker_id.rsplit("f", 1)[1])
        if (
            configured.get("kind") != expected_kind
            or configured.get("seed") != expected_seed
            or configured.get("fold") != expected_fold
            or configured.get("shape") != [ROWS, points, 2560]
            or configured.get("points") != expected_points
        ):
            raise ValueError(f"EXP-070 configured matrix semantics drift: {worker_id}")
        if header != {"dtype": "<f4", "fortran_order": False, "shape": [ROWS, points, 2560]}:
            raise ValueError(f"EXP-070 matrix header drift: {worker_id}")
        observed_workers.append({"worker_id": worker_id, "output": item["output"], "header": header})

    return {
        "completion": EXPECTED_SOURCE["extraction_complete"],
        "verification": EXPECTED_SOURCE["extraction_verification"],
        "snapshot_claim": EXPECTED_SOURCE["source_snapshot_claim"],
        "extraction_manifest": EXPECTED_SOURCE["extraction_manifest"],
        "row_contract": EXPECTED_SOURCE["row_contract"],
        "fold_manifest_public": EXPECTED_SOURCE["fold_manifest_public"],
        "fold_manifest_private": EXPECTED_SOURCE["fold_manifest_private"],
        "source_snapshot_sha256": claim["source_snapshot_sha256"],
        "workers": observed_workers,
    }


def source_identity_snapshot(config: Mapping[str, Any]) -> dict[str, Any]:
    records: dict[str, dict[str, Any]] = {}
    for record in iter_artifact_records(config.get("source")):
        current = artifact(resolve_project(record["path"]))
        records[current["path"]] = current
    for record in iter_artifact_records(config.get("parent_method")):
        current = artifact(resolve_project(record["path"]))
        records[current["path"]] = current
    value = {key: records[key] for key in sorted(records)}
    return {"sha256": bytes_sha256(canonical_json_bytes(value)), "inventory": value}


def _resource_contract(config: Mapping[str, Any]) -> Mapping[str, Any]:
    resources = config.get("resources")
    if not isinstance(resources, Mapping):
        raise ValueError("Missing resource contract")
    required = {
        "maximum_concurrent_probe_workers": 1,
        "maximum_binary_probe_fits": TOTAL_BINARY_FITS,
        "formal_wall_seconds": 43200,
        "probe_peak_rss_bytes": 8589934592,
        "consumer_private_budget_bytes": 536870912,
        "threads_per_library": 1,
        "api_cost_usd": 0,
    }
    for key, expected in required.items():
        if resources.get(key) != expected:
            raise ValueError(f"Resource contract drift: {key}")
    return resources


def _free_disk_gate(config: Mapping[str, Any]) -> int:
    resources = _resource_contract(config)
    minimum = int(resources["consumer_private_budget_bytes"])
    free = shutil.disk_usage(PROJECT_ROOT).free
    if minimum <= 0 or free < minimum:
        raise OSError("EXP-070 probe free-disk gate failed")
    return free


def _peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def _assert_resource_use(config: Mapping[str, Any], *, started: float) -> dict[str, Any]:
    resources = _resource_contract(config)
    elapsed = time.monotonic() - started
    peak = _peak_rss_bytes()
    if elapsed > float(resources["formal_wall_seconds"]):
        raise TimeoutError("EXP-070 probe wall-time ceiling exceeded")
    if peak > int(resources["probe_peak_rss_bytes"]):
        raise MemoryError("EXP-070 probe peak-RSS ceiling exceeded")
    return {"elapsed_seconds": elapsed, "peak_rss_bytes": peak}


def _authorization(config: Mapping[str, Any], *, formal: bool) -> None:
    value = config.get("authorization")
    if not isinstance(value, Mapping):
        raise PermissionError("Missing EXP-070 probe authorization")
    always_false = ("model_loading", "forward", "source_mutation", "validation", "test", "exp071")
    if any(value.get(key) is not False for key in always_false):
        raise PermissionError("EXP-070 forbidden authorization enabled")
    if formal:
        for key in (
            "initialize", "fit_folds", "assemble", "representation_values", "label_source_rows",
            "label_values", "outer_train_label_use", "outer_heldout_label_use_after_fold_seals",
            "probe_fitting", "threshold_selection", "label_shuffle", "bootstrap", "performance_metrics",
            "final_verification", "formal_completion",
        ):
            if value.get(key) is not True:
                raise PermissionError(f"EXP-070 formal authorization missing: {key}")
        if value.get("static_preflight") is not False:
            raise PermissionError("Formal config cannot authorize static stage")
    else:
        if value.get("static_preflight") is not True:
            raise PermissionError("Static config does not authorize no-result gate")
        for key in (
            "initialize", "fit_folds", "assemble", "representation_values", "label_source_rows",
            "label_values", "outer_train_label_use", "outer_heldout_label_use_after_fold_seals",
            "probe_fitting", "threshold_selection", "label_shuffle", "bootstrap", "performance_metrics",
            "final_verification", "formal_completion",
        ):
            if value.get(key) is not False:
                raise PermissionError(f"Static config over-authorizes {key}")


def _access_contract(config: Mapping[str, Any], *, formal: bool) -> None:
    value = config.get("access")
    if not isinstance(value, Mapping):
        raise PermissionError("Missing EXP-070 access contract")
    for key in ("train_jsonl_accessed", "train_text_read", "model_loaded", "forward_executed", "validation_accessed", "test_accessed"):
        if value.get(key) is not False:
            raise PermissionError(f"Forbidden EXP-070 access enabled: {key}")
    if formal:
        for key in (
            "representation_array_values_read", "label_source_rows_parsed", "label_values_read",
            "real_probe_fitted", "threshold_selected", "shuffle_executed", "bootstrap_executed",
            "performance_metrics_computed",
        ):
            if value.get(key) is not True:
                raise PermissionError(f"Formal access missing: {key}")
    else:
        for key in (
            "representation_array_values_read", "label_source_rows_parsed", "label_values_read",
            "real_probe_fitted", "threshold_selected", "shuffle_executed", "bootstrap_executed",
            "performance_metrics_computed",
        ):
            if value.get(key) is not False:
                raise PermissionError(f"Static access over-authorizes {key}")


def _config_record(path: Path) -> dict[str, Any]:
    return artifact(path)


def static_stage(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path, expected_kind="static")
    _authorization(config, formal=False)
    _access_contract(config, formal=False)
    started = time.monotonic()
    observed_environment_value = require_environment(config)
    free = _free_disk_gate(config)
    pub = public_root(config)
    priv = private_root(config)
    if os.path.lexists(pub) or os.path.lexists(priv):
        raise FileExistsError("EXP-070 probe static output root already exists")
    configured_outputs = config.get("outputs")
    if isinstance(configured_outputs, Mapping):
        formal_pub = resolve_project(str(configured_outputs["formal_public_root"]))
        formal_priv = resolve_project(str(configured_outputs["formal_private_root"]))
        if os.path.lexists(formal_pub) or os.path.lexists(formal_priv):
            raise FileExistsError("EXP-070 probe static output root already exists")

    before = source_identity_snapshot(config)
    sources = require_frozen_sources(config, headers_only=True)
    after = source_identity_snapshot(config)
    if before != after:
        raise ValueError("EXP-070 source snapshot changed during static gate")
    require_implementation_records(config)
    resources = _assert_resource_use(config, started=started)

    ensure_new_directory(pub, private=False)
    ensure_new_directory(priv, private=True)
    input_manifest = {
        "schema_version": "exp-070-probe-static-input-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "config": _config_record(config_path),
        "method_sha256": EXPECTED_CONFIG_METHOD_NORMALIZED_SHA256,
        "sources": sources,
        "source_identity_snapshot": before,
        "environment": observed_environment_value,
        "access": {
            "npy_headers_read": True,
            "npy_array_values_read": False,
            "fold_manifest_values_read": False,
            "labels_read": False,
            "representation_values_read": False,
            "probe_fitted": False,
            "metrics_computed": False,
            "validation_accessed": False,
            "test_accessed": False,
        },
        "status": "Sealed",
    }
    input_record = create_json_once(priv / "input-contract-manifest.json", input_manifest, private=True)
    report = {
        "schema_version": "exp-070-probe-static-run-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "stage": "static",
        "status": "CompletedAwaitingVerification",
        "config": _config_record(config_path),
        "input_manifest": input_record,
        "counts": {"rows": ROWS, "workers": 16, "matrices": 16, "main_conditions": 24, "shuffle_conditions_per_fold": 24},
        "method_sha256": EXPECTED_CONFIG_METHOD_NORMALIZED_SHA256,
        "source_snapshot_sha256": sources["source_snapshot_sha256"],
        "resources": {**resources, "free_disk_bytes": free},
        "access": input_manifest["access"],
        "claim_boundary": config["claim_boundary"],
    }
    create_json_once(pub / "static.json", report, private=False)
    return report


def _formal_static_completion(config: Mapping[str, Any]) -> Path:
    parent = config.get("preflight")
    expected_parent_keys = {
        "config",
        "static_run",
        "static_verification",
        "no_result_completion",
        "required_statuses",
        "formal_probe_authorized_by_preflight",
    }
    if (
        not isinstance(parent, Mapping)
        or set(parent) != expected_parent_keys
        or parent.get("formal_probe_authorized_by_preflight") is not True
        or parent.get("required_statuses")
        != {
            "static_run": "CompletedAwaitingVerification",
            "static_verification": "Passed",
            "no_result_completion": "Complete",
        }
    ):
        raise ValueError("EXP-070 formal static binding drift")
    for key in ("config", "static_run", "static_verification", "no_result_completion"):
        record = parent[key]
        if (
            not isinstance(record, Mapping)
            or record.get("bytes") == 0
            or record.get("sha256") == "TBD"
        ):
            raise ValueError("EXP-070 static parent identity is not frozen")
        require_record(record)

    static_config_path = require_record(parent["config"])
    static_config = load_config(static_config_path, expected_kind="static")
    require_implementation_records(static_config)
    if _method_from_config(static_config) != _method_from_config(config):
        raise ValueError("EXP-070 static/formal method drift")
    static_public = public_root(static_config)
    static_private = private_root(static_config)
    require_safe_directory(static_public, private=False)
    require_safe_directory(static_private, private=True)
    public_files = {
        path.relative_to(static_public).as_posix()
        for path in static_public.rglob("*")
        if path.is_file()
    }
    private_files = {
        path.relative_to(static_private).as_posix()
        for path in static_private.rglob("*")
        if path.is_file()
    }
    if public_files != set(static_config["outputs"]["preflight_public_success_allowlist"]):
        raise ValueError("EXP-070 static parent public inventory drift")
    if private_files != {"input-contract-manifest.json"}:
        raise ValueError("EXP-070 static parent private inventory drift")
    if any(path.is_dir() for path in static_public.rglob("*")) or any(
        path.is_dir() for path in static_private.rglob("*")
    ):
        raise ValueError("EXP-070 static parent nested-directory drift")

    run_path = require_record(parent["static_run"])
    verification_path = require_record(parent["static_verification"])
    completion_path = require_record(parent["no_result_completion"])
    input_path = static_private / "input-contract-manifest.json"
    if file_mode(input_path) != "0600" or input_path.stat().st_nlink != 1:
        raise ValueError("EXP-070 static parent private artifact drift")
    run = require_canonical_json(run_path)
    verification = require_canonical_json(verification_path)
    completion = require_canonical_json(completion_path)
    input_manifest = require_canonical_json(input_path)
    sources = require_frozen_sources(static_config, headers_only=True)
    source_snapshot = source_identity_snapshot(static_config)
    static_access = {
        "npy_headers_read": True,
        "npy_array_values_read": False,
        "fold_manifest_values_read": False,
        "labels_read": False,
        "representation_values_read": False,
        "probe_fitted": False,
        "metrics_computed": False,
        "validation_accessed": False,
        "test_accessed": False,
    }
    verification_access = {
        "npy_headers_read": True,
        "npy_array_values_read": False,
        "fold_manifest_values_read": False,
        "labels_read": False,
        "probe_fitted": False,
        "metrics_computed": False,
        "validation_accessed": False,
        "test_accessed": False,
    }
    static_config_record = artifact(static_config_path)
    input_record = artifact(input_path, logical_name="input-contract-manifest.json")
    run_record = artifact(run_path)
    verification_record = artifact(verification_path)
    synthetic_tests = verification.get("synthetic_tests")
    if (
        not isinstance(synthetic_tests, Mapping)
        or set(synthetic_tests) != {"test_artifact", "tests_run", "status", "command_sha256"}
        or synthetic_tests.get("test_artifact") != static_config["implementation"]["tests"]
        or type(synthetic_tests.get("tests_run")) is not int
        or int(synthetic_tests["tests_run"]) <= 0
        or synthetic_tests.get("status") != "Passed"
        or type(synthetic_tests.get("command_sha256")) is not str
        or len(synthetic_tests["command_sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in synthetic_tests["command_sha256"])
    ):
        raise ValueError("EXP-070 static synthetic-test binding drift")

    if set(input_manifest) != {
        "schema_version", "experiment_id", "run_id", "attempt_id", "config",
        "method_sha256", "sources", "source_identity_snapshot", "environment",
        "access", "status",
    } or (
        input_manifest.get("schema_version") != "exp-070-probe-static-input-v1"
        or input_manifest.get("experiment_id") != EXPERIMENT_ID
        or input_manifest.get("run_id") != static_config["run_id"]
        or input_manifest.get("attempt_id") != static_config["attempt_id"]
        or input_manifest.get("config") != static_config_record
        or input_manifest.get("method_sha256") != EXPECTED_CONFIG_METHOD_NORMALIZED_SHA256
        or input_manifest.get("sources") != sources
        or input_manifest.get("source_identity_snapshot") != source_snapshot
        or input_manifest.get("environment") != PROBE_ENVIRONMENT
        or input_manifest.get("access") != static_access
        or input_manifest.get("status") != "Sealed"
    ):
        raise ValueError("EXP-070 static input binding drift")

    if set(run) != {
        "schema_version", "experiment_id", "run_id", "attempt_id", "stage", "status",
        "config", "input_manifest", "counts", "method_sha256", "source_snapshot_sha256",
        "resources", "access", "claim_boundary",
    } or (
        run.get("schema_version") != "exp-070-probe-static-run-v1"
        or run.get("experiment_id") != EXPERIMENT_ID
        or run.get("run_id") != static_config["run_id"]
        or run.get("attempt_id") != static_config["attempt_id"]
        or run.get("stage") != "static"
        or run.get("status") != "CompletedAwaitingVerification"
        or run.get("config") != static_config_record
        or run.get("input_manifest") != input_record
        or run.get("counts")
        != {
            "rows": ROWS,
            "workers": 16,
            "matrices": 16,
            "main_conditions": 24,
            "shuffle_conditions_per_fold": 24,
        }
        or run.get("method_sha256") != EXPECTED_CONFIG_METHOD_NORMALIZED_SHA256
        or run.get("source_snapshot_sha256")
        != "cdcde7fd617aee9d6189d6a7e87778a6617cdf0a6db658a397928b7e20910bad"
        or run.get("access") != static_access
        or run.get("claim_boundary") != static_config["claim_boundary"]
    ):
        raise ValueError("EXP-070 static run binding drift")
    run_resources = run.get("resources")
    if (
        not isinstance(run_resources, Mapping)
        or set(run_resources) != {"elapsed_seconds", "peak_rss_bytes", "free_disk_bytes"}
        or not 0.0 <= float(run_resources["elapsed_seconds"]) <= 43200.0
        or not 0 < int(run_resources["peak_rss_bytes"]) <= 8589934592
        or int(run_resources["free_disk_bytes"]) < 536870912
    ):
        raise ValueError("EXP-070 static run resource drift")

    if set(verification) != {
        "schema_version", "experiment_id", "run_id", "attempt_id", "stage", "status",
        "passed_count", "failed_count", "checks", "config", "run", "input_manifest",
        "method_sha256", "source_snapshot_sha256", "source_identity_snapshot_sha256",
        "synthetic_tests", "formal_probe_authorized", "runner_imported", "model_libraries_imported",
        "access", "claim_boundary",
    } or (
        verification.get("schema_version") != "exp-070-probe-static-verification-v1"
        or verification.get("experiment_id") != EXPERIMENT_ID
        or verification.get("run_id") != static_config["run_id"]
        or verification.get("attempt_id") != static_config["attempt_id"]
        or verification.get("stage") != "static"
        or verification.get("status") != "Passed"
        or verification.get("passed_count") != len(STATIC_CHECKS)
        or verification.get("failed_count") != 0
        or verification.get("checks") != STATIC_CHECKS
        or verification.get("config") != static_config_record
        or verification.get("run") != run_record
        or verification.get("input_manifest") != input_record
        or verification.get("method_sha256") != EXPECTED_CONFIG_METHOD_NORMALIZED_SHA256
        or verification.get("source_snapshot_sha256")
        != "cdcde7fd617aee9d6189d6a7e87778a6617cdf0a6db658a397928b7e20910bad"
        or verification.get("source_identity_snapshot_sha256") != source_snapshot["sha256"]
        or verification.get("synthetic_tests") != synthetic_tests
        or verification.get("formal_probe_authorized") is not True
        or verification.get("runner_imported") is not False
        or verification.get("model_libraries_imported") is not False
        or verification.get("access") != verification_access
        or verification.get("claim_boundary") != static_config["claim_boundary"]
    ):
        raise ValueError("EXP-070 static verification binding drift")

    if set(completion) != {
        "schema_version", "experiment_id", "run_id", "attempt_id", "status",
        "formal_probe_authorized", "formal_probe_executed", "performance_metrics_computed",
        "exp070_complete", "exp071_authorized", "run", "verification", "input_manifest",
        "method_sha256", "source_snapshot_sha256", "synthetic_tests", "claim_boundary", "next_gate",
    } or (
        completion.get("schema_version") != "exp-070-probe-static-complete-v1"
        or completion.get("experiment_id") != EXPERIMENT_ID
        or completion.get("run_id") != static_config["run_id"]
        or completion.get("attempt_id") != static_config["attempt_id"]
        or completion.get("status") != "Complete"
        or completion.get("formal_probe_authorized") is not True
        or completion.get("formal_probe_executed") is not False
        or completion.get("performance_metrics_computed") is not False
        or completion.get("exp070_complete") is not False
        or completion.get("exp071_authorized") is not False
        or completion.get("run") != run_record
        or completion.get("verification") != verification_record
        or completion.get("input_manifest") != input_record
        or completion.get("method_sha256") != EXPECTED_CONFIG_METHOD_NORMALIZED_SHA256
        or completion.get("source_snapshot_sha256")
        != "cdcde7fd617aee9d6189d6a7e87778a6617cdf0a6db658a397928b7e20910bad"
        or completion.get("synthetic_tests") != synthetic_tests
        or completion.get("claim_boundary") != static_config["claim_boundary"]
        or completion.get("next_gate") != "EXP-070 formal probe initialize"
    ):
        raise ValueError("EXP-070 static completion binding drift")
    return completion_path


def initialize_stage(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path, expected_kind="formal")
    require_implementation_records(config)
    _authorization(config, formal=True)
    _access_contract(config, formal=True)
    started = time.monotonic()
    static_completion = _formal_static_completion(config)
    observed_environment_value = require_environment(config)
    free = _free_disk_gate(config)
    sources = require_frozen_sources(config, headers_only=True)
    before = source_identity_snapshot(config)

    pub = public_root(config)
    priv = private_root(config)
    if os.path.lexists(pub) or os.path.lexists(priv):
        raise FileExistsError("EXP-070 formal probe output root already exists")
    ensure_new_directory(pub, private=False)
    ensure_new_directory(priv, private=True)
    folds_dir = priv / "folds"
    folds_dir.mkdir(mode=0o700)
    os.chmod(folds_dir, 0o700)

    claim = {
        "schema_version": "exp-070-formal-probe-claim-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "stage": "formal-probe",
        "status": "Initialized",
        "config": _config_record(config_path),
        "static_completion": artifact(static_completion),
        "source_snapshot_sha256": sources["source_snapshot_sha256"],
        "lifecycle": ["initialize", "fit-fold-0", "fit-fold-1", "fit-fold-2", "fit-fold-3", "fit-fold-4", "assemble"],
        "claim_boundary": config["claim_boundary"],
    }
    create_json_once(pub / "run-claim.json", claim, private=False)
    after = source_identity_snapshot(config)
    if before != after:
        raise ValueError("EXP-070 source snapshot changed during initialization")
    resources = _assert_resource_use(config, started=started)
    input_manifest = {
        "schema_version": "exp-070-formal-probe-input-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "config": _config_record(config_path),
        "static_completion": artifact(static_completion),
        "method_sha256": EXPECTED_CONFIG_METHOD_NORMALIZED_SHA256,
        "sources": sources,
        "source_identity_snapshot": before,
        "environment": observed_environment_value,
        "resources": {**resources, "free_disk_bytes": free},
        "access": {
            "fold_manifest_values_read": False,
            "outer_train_labels_read": False,
            "outer_heldout_labels_read": False,
            "representation_values_read": False,
            "probe_fitted": False,
            "metrics_computed": False,
            "model_loaded": False,
            "forward_executed": False,
            "validation_accessed": False,
            "test_accessed": False,
        },
        "status": "Initialized",
    }
    create_json_once(priv / "input-manifest.json", input_manifest, private=True)
    return claim


def _public_fold_rows() -> list[dict[str, Any]]:
    import numpy as np

    path = require_record(EXPECTED_SOURCE["fold_manifest_public"])
    rows: list[dict[str, Any]] = []
    expected_keys = {"schema_version", "protocol_id", "experiment_id", "sample_id", "component_id", "fold_id"}
    with path.open("rb") as handle:
        for ordinal, line in enumerate(handle):
            value = strict_json_bytes(line)
            if (
                not isinstance(value, dict)
                or set(value) != expected_keys
                or value.get("schema_version") != "exp-058-fold-row-v1"
                or value.get("protocol_id") != "DATA-SO-TASK-V1"
                or value.get("experiment_id") != "EXP-058"
                or type(value.get("sample_id")) is not str
                or type(value.get("component_id")) is not str
                or value.get("fold_id") not in FOLDS
            ):
                raise ValueError(f"EXP-070 public fold row schema drift at ordinal {ordinal}")
            rows.append(value)
    if len(rows) != ROWS or [sum(row["fold_id"] == fold for row in rows) for fold in FOLDS] != [672] * 5:
        raise ValueError("EXP-070 public fold row-count drift")
    if len({row["sample_id"] for row in rows}) != ROWS:
        raise ValueError("EXP-070 duplicate sample identity")
    component_fold: dict[str, int] = {}
    for row in rows:
        previous = component_fold.setdefault(row["component_id"], row["fold_id"])
        if previous != row["fold_id"]:
            raise ValueError("EXP-070 component leakage across folds")
    if len(component_fold) != 3277:
        raise ValueError("EXP-070 component-count drift")
    if (
        _string_sequence_digest([row["sample_id"] for row in rows])
        != "bba5ac048be9cbe407f039b228f3ed9ef84a00d3d5cacf81d2caf0454ef4c7b0"
        or _string_sequence_digest([row["component_id"] for row in rows])
        != "86c57712a9c03e1b6fbf11c08f7f56e933cee5ff6c4100e46e0b09b3b95a8037"
        or _array_digest(np.asarray([row["fold_id"] for row in rows], dtype=np.int8))
        != "561a902dc639dd9b720fef68b335d608cf512cc8eaa98ac779350919a9e724cc"
    ):
        raise ValueError("EXP-070 fold-manifest row identity drift")
    return rows


def _validate_private_label_row(value: Any, public: Mapping[str, Any], ordinal: int) -> list[int]:
    expected_keys = {
        "schema_version", "protocol_id", "experiment_id", "sample_id", "component_id", "fold_id",
        "labels", "neutral", "label_cardinality",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise ValueError(f"EXP-070 private fold row schema drift at ordinal {ordinal}")
    for key in ("schema_version", "protocol_id", "experiment_id", "sample_id", "component_id", "fold_id"):
        if value.get(key) != public.get(key):
            raise ValueError(f"EXP-070 public/private fold alignment drift at ordinal {ordinal}")
    labels = value.get("labels")
    if (
        not isinstance(labels, list)
        or len(labels) != 6
        or any(type(item) not in (int, bool) or int(item) not in (0, 1) for item in labels)
    ):
        raise ValueError(f"EXP-070 label schema drift at ordinal {ordinal}")
    normalized = [int(item) for item in labels]
    if value.get("label_cardinality") != sum(normalized) or value.get("neutral") is not (sum(normalized) == 0):
        raise ValueError(f"EXP-070 label-derived field drift at ordinal {ordinal}")
    return normalized


def load_outer_train_labels(outer_fold: int, public_rows: Sequence[Mapping[str, Any]]) -> tuple[Any, Any]:
    """Decode only labels outside ``outer_fold``; heldout lines remain opaque bytes."""
    import numpy as np

    path = require_record(EXPECTED_SOURCE["fold_manifest_private"])
    ordinals: list[int] = []
    labels: list[list[int]] = []
    line_count = 0
    with path.open("rb") as handle:
        for ordinal, line in enumerate(handle):
            line_count += 1
            public = public_rows[ordinal] if ordinal < len(public_rows) else None
            if public is None:
                raise ValueError("Private fold manifest has extra rows")
            if public["fold_id"] == outer_fold:
                continue
            value = strict_json_bytes(line)
            labels.append(_validate_private_label_row(value, public, ordinal))
            ordinals.append(ordinal)
    if line_count != ROWS or len(ordinals) != 2688:
        raise ValueError("EXP-070 outer-train label row-count drift")
    return np.asarray(ordinals, dtype=np.int32), np.asarray(labels, dtype=np.uint8)


def load_all_labels(public_rows: Sequence[Mapping[str, Any]]) -> Any:
    import numpy as np

    path = require_record(EXPECTED_SOURCE["fold_manifest_private"])
    labels: list[list[int]] = []
    with path.open("rb") as handle:
        for ordinal, line in enumerate(handle):
            if ordinal >= ROWS:
                raise ValueError("Private fold manifest has extra rows")
            labels.append(_validate_private_label_row(strict_json_bytes(line), public_rows[ordinal], ordinal))
    if len(labels) != ROWS:
        raise ValueError("EXP-070 full-label row-count drift")
    return np.asarray(labels, dtype=np.uint8)


def _binary_f1_columns(labels: Any, predicted: Any) -> Any:
    import numpy as np
    from sklearn.metrics import f1_score

    truth = np.asarray(labels, dtype=np.uint8)
    guess = np.asarray(predicted, dtype=np.uint8)
    if truth.shape != guess.shape or truth.ndim != 2 or truth.shape[1] != 6:
        raise ValueError("EXP-070 F1 input shape drift")
    return np.asarray(
        f1_score(truth, guess, average=None, zero_division=0), dtype=np.float64
    )


def threshold_objectives(labels: Any, probabilities: Any, threshold_index: int) -> tuple[float, float]:
    import numpy as np

    truth = np.asarray(labels, dtype=np.uint8)
    values = np.asarray(probabilities, dtype=np.float64)
    if truth.shape != values.shape or truth.ndim != 2 or truth.shape[1] != 6:
        raise ValueError("EXP-070 threshold input shape drift")
    if threshold_index not in THRESHOLD_INDICES or not np.all(np.isfinite(values)):
        raise ValueError("EXP-070 threshold value drift")
    predicted = (values >= threshold_index / 100.0).astype(np.uint8)
    f1 = _binary_f1_columns(truth, predicted)
    return float(np.mean(f1[list(PRIMARY_COLUMNS)])), float(np.mean(truth != predicted))


def select_threshold_index(labels: Any, probabilities: Any) -> int:
    scores = [
        (index, *threshold_objectives(labels, probabilities, index))
        for index in THRESHOLD_INDICES
    ]
    best_f1 = max(value[1] for value in scores)
    candidates = [value for value in scores if best_f1 - value[1] <= COMPARISON_TOLERANCE]
    best_hamming = min(value[2] for value in candidates)
    candidates = [value for value in candidates if value[2] - best_hamming <= COMPARISON_TOLERANCE]
    closest = min(abs(value[0] - 50) for value in candidates)
    candidates = [value for value in candidates if abs(value[0] - 50) == closest]
    return min(value[0] for value in candidates)


def build_shuffle_permutation(row_count: int, shuffle_seed: int, outer_fold: int) -> Any:
    import numpy as np

    if row_count != 2688 or shuffle_seed not in SHUFFLE_SEEDS or outer_fold not in FOLDS:
        raise ValueError("EXP-070 shuffle request drift")
    rng = np.random.Generator(
        np.random.PCG64(np.random.SeedSequence([shuffle_seed, outer_fold]))
    )
    value = np.asarray(rng.permutation(row_count), dtype=np.int64)
    if value.shape != (row_count,) or not np.array_equal(np.sort(value), np.arange(row_count)):
        raise ValueError("EXP-070 shuffle permutation drift")
    return value


def _fit_six_binary(train_x: Any, train_y: Any, predict_x: Any) -> tuple[Any, Any]:
    import numpy as np
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    x_fit = np.asarray(train_x, dtype=np.float64)
    y_fit = np.asarray(train_y, dtype=np.uint8)
    x_predict = np.asarray(predict_x, dtype=np.float64)
    if (
        x_fit.ndim != 2
        or x_predict.ndim != 2
        or x_fit.shape[1] != 2560
        or x_predict.shape[1] != 2560
        or y_fit.shape != (x_fit.shape[0], 6)
        or not np.all(np.isfinite(x_fit))
        or not np.all(np.isfinite(x_predict))
    ):
        raise ValueError("EXP-070 probe fit input drift")
    for column in range(6):
        if not np.array_equal(np.unique(y_fit[:, column]), np.asarray([0, 1], dtype=np.uint8)):
            raise ValueError(f"EXP-070 single-class fit partition for label {LABELS[column]}")

    scaler = StandardScaler(with_mean=True, with_std=True)
    scaled_fit = scaler.fit_transform(x_fit)
    scaled_predict = scaler.transform(x_predict)
    for value in (scaler.mean_, scaler.var_, scaler.scale_, scaled_fit, scaled_predict):
        if not np.all(np.isfinite(value)):
            raise ValueError("EXP-070 non-finite scaler output")

    outputs = []
    iterations = []
    for column in range(6):
        model = LogisticRegression(
            penalty="l2",
            dual=False,
            C=1.0,
            solver="liblinear",
            class_weight=None,
            fit_intercept=True,
            intercept_scaling=1.0,
            tol=1e-4,
            max_iter=2000,
            random_state=42,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error", ConvergenceWarning)
            model.fit(scaled_fit, y_fit[:, column])
        if not np.array_equal(model.classes_, np.asarray([0, 1])):
            raise ValueError("EXP-070 positive-class identity drift")
        if model.n_iter_.shape != (1,) or int(model.n_iter_[0]) <= 0 or int(model.n_iter_[0]) > 2000:
            raise ValueError("EXP-070 solver iteration record drift")
        iterations.append(int(model.n_iter_[0]))
        for value in (model.coef_, model.intercept_):
            if not np.all(np.isfinite(value)):
                raise ValueError("EXP-070 non-finite probe parameter")
        output = model.predict_proba(scaled_predict)[:, 1]
        if output.shape != (x_predict.shape[0],) or not np.all(np.isfinite(output)):
            raise ValueError("EXP-070 non-finite probe probability")
        if np.any(output < 0.0) or np.any(output > 1.0):
            raise ValueError("EXP-070 probability range drift")
        outputs.append(output)
    return (
        np.ascontiguousarray(np.column_stack(outputs), dtype=np.float64),
        np.asarray(iterations, dtype=np.int32),
    )


def _fit_main_condition(
    representation: Any,
    fold_ids: Any,
    outer_fold: int,
    outer_train_ordinals: Any,
    outer_train_labels: Any,
) -> tuple[Any, Any, int, Any, int]:
    import numpy as np

    x = np.asarray(representation, dtype=np.float64)
    fold_array = np.asarray(fold_ids, dtype=np.int8)
    train_ordinals = np.asarray(outer_train_ordinals, dtype=np.int32)
    train_labels = np.asarray(outer_train_labels, dtype=np.uint8)
    expected_train = np.flatnonzero(fold_array != outer_fold).astype(np.int32)
    outer_ordinals = np.flatnonzero(fold_array == outer_fold).astype(np.int32)
    if (
        x.shape != (ROWS, 2560)
        or not np.array_equal(train_ordinals, expected_train)
        or train_labels.shape != (2688, 6)
        or outer_ordinals.shape != (672,)
    ):
        raise ValueError("EXP-070 main-condition split drift")

    inner_probabilities = np.empty((2688, 6), dtype=np.float64)
    n_iter = np.empty((5, 6), dtype=np.int32)
    fit_count = 0
    fit_index = 0
    outer_train_fold_ids = fold_array[train_ordinals]
    for inner_fold in FOLDS:
        if inner_fold == outer_fold:
            continue
        inner_fit_mask = outer_train_fold_ids != inner_fold
        inner_predict_mask = outer_train_fold_ids == inner_fold
        if int(np.sum(inner_fit_mask)) != 2016 or int(np.sum(inner_predict_mask)) != 672:
            raise ValueError("EXP-070 inner-fold size drift")
        probability, iteration = _fit_six_binary(
            x[train_ordinals[inner_fit_mask]],
            train_labels[inner_fit_mask],
            x[train_ordinals[inner_predict_mask]],
        )
        inner_probabilities[inner_predict_mask] = probability
        n_iter[fit_index] = iteration
        fit_index += 1
        fit_count += 6
    threshold_index = select_threshold_index(train_labels, inner_probabilities)
    outer_probabilities, iteration = _fit_six_binary(
        x[train_ordinals], train_labels, x[outer_ordinals]
    )
    n_iter[fit_index] = iteration
    fit_index += 1
    fit_count += 6
    if fit_count != 30 or fit_index != 5:
        raise ValueError("EXP-070 main fit-count drift")
    return inner_probabilities, outer_probabilities, threshold_index, n_iter, fit_count


def _fit_shuffle_condition(
    representation: Any,
    fold_ids: Any,
    outer_fold: int,
    outer_train_ordinals: Any,
    shuffled_outer_train_labels: Any,
) -> tuple[Any, Any, int]:
    import numpy as np

    x = np.asarray(representation, dtype=np.float64)
    fold_array = np.asarray(fold_ids, dtype=np.int8)
    train_ordinals = np.asarray(outer_train_ordinals, dtype=np.int32)
    outer_ordinals = np.flatnonzero(fold_array == outer_fold).astype(np.int32)
    if x.shape != (ROWS, 2560) or train_ordinals.shape != (2688,) or outer_ordinals.shape != (672,):
        raise ValueError("EXP-070 shuffle-condition split drift")
    probability, n_iter = _fit_six_binary(
        x[train_ordinals], shuffled_outer_train_labels, x[outer_ordinals]
    )
    return probability, n_iter, 6


def _worker_points(worker_id: str) -> tuple[str, ...]:
    return ALL_POINTS if worker_id == "base" or worker_id.startswith("m3-s42-") else CONFIRMATION_POINTS


def _worker_matrix_path(worker_id: str) -> Path:
    if worker_id not in WORKER_IDS:
        raise ValueError(f"Unknown EXP-070 worker: {worker_id}")
    return resolve_project(EXTRACTION_PRIVATE_ROOT) / "extraction" / worker_id / "representations.npy"


def _load_worker_matrix(worker_id: str) -> Any:
    import numpy as np

    path = _worker_matrix_path(worker_id)
    value = np.load(path, mmap_mode="r", allow_pickle=False)
    expected = (ROWS, len(_worker_points(worker_id)), 2560)
    if value.shape != expected or value.dtype != np.dtype("float32") or value.flags.f_contiguous:
        raise ValueError(f"EXP-070 representation schema drift: {worker_id}")
    if not isinstance(value, np.memmap) or value.mode != "r":
        raise PermissionError("EXP-070 representation must be read-only mmap")
    return value


def _condition_worker_and_point(key: str, outer_fold: int) -> tuple[str, str]:
    model, point = key.split(":", 1)
    worker = "base" if model == "frozen" else f"{model}-f{outer_fold}"
    if point not in _worker_points(worker):
        raise ValueError(f"EXP-070 condition-point drift: {key}")
    return worker, point


def _point_slice(matrices: Mapping[str, Any], worker: str, point: str) -> Any:
    import numpy as np

    index = _worker_points(worker).index(point)
    return np.asarray(matrices[worker][:, index, :], dtype=np.float64)


def _npz_artifact(path: Path) -> dict[str, Any]:
    return artifact(path, logical_name=f"folds/{path.name}")


def _write_npz_once(path: Path, arrays: Mapping[str, Any]) -> dict[str, Any]:
    import numpy as np

    if os.path.lexists(path):
        raise FileExistsError(f"Refusing to overwrite {path}")
    part = path.with_name(path.name + ".part")
    if os.path.lexists(part):
        raise FileExistsError(f"Technical NPZ already exists: {part}")
    descriptor = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            np.savez(handle, **arrays)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    os.chmod(part, 0o600)
    if os.path.lexists(path):
        raise FileExistsError(f"NPZ destination appeared during write: {path}")
    os.link(part, path)
    os.unlink(part)
    os.chmod(path, 0o600)
    return _npz_artifact(path)


def _bundle_expected_arrays() -> set[str]:
    return {
        "outer_train_ordinals",
        "outer_heldout_ordinals",
        "main_inner_oof_probability",
        "main_outer_heldout_probability",
        "main_threshold_index",
        "main_n_iter",
        "shuffle_outer_heldout_probability",
        "shuffle_n_iter",
    }


def validate_fold_bundle(path: Path, outer_fold: int) -> None:
    import numpy as np

    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1 or file_mode(path) != "0600":
        raise ValueError(f"Unsafe fold bundle: {path}")
    with np.load(path, allow_pickle=False) as bundle:
        if set(bundle.files) != _bundle_expected_arrays():
            raise ValueError("EXP-070 fold bundle member drift")
        if bundle["outer_train_ordinals"].shape != (2688,) or bundle["outer_train_ordinals"].dtype != np.int32:
            raise ValueError("EXP-070 inner ordinal schema drift")
        if bundle["outer_heldout_ordinals"].shape != (672,) or bundle["outer_heldout_ordinals"].dtype != np.int32:
            raise ValueError("EXP-070 outer ordinal schema drift")
        if bundle["main_inner_oof_probability"].shape != (24, 2688, 6) or bundle["main_inner_oof_probability"].dtype != np.float64:
            raise ValueError("EXP-070 main inner probability schema drift")
        if bundle["main_outer_heldout_probability"].shape != (24, 672, 6) or bundle["main_outer_heldout_probability"].dtype != np.float64:
            raise ValueError("EXP-070 main outer probability schema drift")
        if bundle["main_threshold_index"].shape != (24,) or bundle["main_threshold_index"].dtype != np.int16:
            raise ValueError("EXP-070 threshold schema drift")
        if bundle["main_n_iter"].shape != (24, 5, 6) or bundle["main_n_iter"].dtype != np.int32:
            raise ValueError("EXP-070 main n_iter schema drift")
        if bundle["shuffle_outer_heldout_probability"].shape != (3, 8, 672, 6) or bundle["shuffle_outer_heldout_probability"].dtype != np.float64:
            raise ValueError("EXP-070 shuffle probability schema drift")
        if bundle["shuffle_n_iter"].shape != (3, 8, 6) or bundle["shuffle_n_iter"].dtype != np.int32:
            raise ValueError("EXP-070 shuffle n_iter schema drift")
        if not np.all(np.isfinite(bundle["main_inner_oof_probability"])) or not np.all(np.isfinite(bundle["main_outer_heldout_probability"])):
            raise ValueError("EXP-070 non-finite main probability")
        if not np.all(np.isfinite(bundle["shuffle_outer_heldout_probability"])):
            raise ValueError("EXP-070 non-finite shuffle probability")
        for name in ("main_inner_oof_probability", "main_outer_heldout_probability", "shuffle_outer_heldout_probability"):
            if np.any(bundle[name] < 0.0) or np.any(bundle[name] > 1.0):
                raise ValueError("EXP-070 probability range drift")
        if not np.all(np.isin(bundle["main_threshold_index"], THRESHOLD_INDICES)):
            raise ValueError("EXP-070 threshold index drift")
        for name in ("main_n_iter", "shuffle_n_iter"):
            if np.any(bundle[name] <= 0) or np.any(bundle[name] > 2000):
                raise ValueError("EXP-070 solver iteration range drift")


def validate_fold_prefix(config: Mapping[str, Any], expected_count: int) -> list[dict[str, Any]]:
    if not 0 <= expected_count <= 5:
        raise ValueError("Invalid EXP-070 prefix length")
    pub = public_root(config)
    priv = private_root(config)
    require_safe_directory(pub, private=False)
    require_safe_directory(priv, private=True)
    if (pub / "failure.json").exists():
        raise RuntimeError("EXP-070 formal attempt is terminally failed")
    if not (pub / "run-claim.json").is_file() or not (priv / "input-manifest.json").is_file():
        raise ValueError("EXP-070 initialization artifacts missing")
    folds_dir = priv / "folds"
    require_safe_directory(folds_dir, private=True)
    expected_names = {name for fold in range(expected_count) for name in (f"f{fold}.npz", f"f{fold}.json")}
    observed_names = {path.name for path in folds_dir.iterdir()}
    if observed_names != expected_names:
        raise ValueError("EXP-070 fold prefix/inventory drift")
    seals = []
    for fold in range(expected_count):
        npz_path = folds_dir / f"f{fold}.npz"
        seal_path = folds_dir / f"f{fold}.json"
        if file_mode(seal_path) != "0600" or seal_path.stat().st_nlink != 1:
            raise ValueError("EXP-070 fold seal mode/link drift")
        seal = strict_json(seal_path)
        if (
            seal.get("schema_version") != "exp-070-probe-fold-seal-v1"
            or seal.get("status") != "Sealed"
            or seal.get("outer_fold") != fold
            or seal.get("npz") != _npz_artifact(npz_path)
            or seal.get("main_condition_order") != list(MAIN_KEYS)
            or seal.get("shuffle_condition_order") != list(SHUFFLE_CONDITIONS)
            or seal.get("fit_counts")
            != {
                "main_binary_fits": MAIN_FITS_PER_FOLD,
                "shuffle_binary_fits": SHUFFLE_FITS_PER_FOLD,
                "total_binary_fits": MAIN_FITS_PER_FOLD + SHUFFLE_FITS_PER_FOLD,
            }
            or seal.get("source_before") != seal.get("source_after")
        ):
            raise ValueError(f"EXP-070 fold seal drift: {fold}")
        validate_fold_bundle(npz_path, fold)
        seals.append(seal)
    return seals


def _directory_bytes(path: Path) -> int:
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"Unsafe disk-budget root: {path}")
    total = 0
    for item in path.rglob("*"):
        if item.is_symlink():
            raise ValueError("Symlink rejected during disk-budget audit")
        if item.is_file():
            total += item.stat().st_size
        elif not item.is_dir():
            raise ValueError("Special entry rejected during disk-budget audit")
    return total


def _private_disk_gate(config: Mapping[str, Any]) -> int:
    resources = _resource_contract(config)
    budget = int(resources["consumer_private_budget_bytes"])
    if budget <= 0:
        raise ValueError("Missing EXP-070 private disk budget")
    total = _directory_bytes(private_root(config)) if private_root(config).exists() else 0
    if total > budget:
        raise OSError("EXP-070 private disk budget exceeded")
    return total


def fit_fold_stage(config_path: Path, outer_fold: int) -> dict[str, Any]:
    import numpy as np

    if outer_fold not in FOLDS:
        raise ValueError("EXP-070 fit-fold requires fold 0..4")
    config = load_config(config_path, expected_kind="formal")
    require_implementation_records(config)
    _authorization(config, formal=True)
    _access_contract(config, formal=True)
    _formal_static_completion(config)
    started = time.monotonic()
    require_environment(config)
    _free_disk_gate(config)
    require_frozen_sources(config, headers_only=False)
    validate_fold_prefix(config, outer_fold)
    before = source_identity_snapshot(config)

    public_rows = _public_fold_rows()
    fold_ids = np.asarray([row["fold_id"] for row in public_rows], dtype=np.int8)
    inner_ordinals, outer_train_labels = load_outer_train_labels(outer_fold, public_rows)
    expected_inner = np.flatnonzero(fold_ids != outer_fold).astype(np.int32)
    outer_ordinals = np.flatnonzero(fold_ids == outer_fold).astype(np.int32)
    if not np.array_equal(inner_ordinals, expected_inner) or outer_ordinals.shape != (672,):
        raise ValueError("EXP-070 outer fold ordinal drift")

    worker_ids = ("base", f"m3-s42-f{outer_fold}", f"m3-s43-f{outer_fold}", f"m3-s44-f{outer_fold}")
    matrices = {worker_id: _load_worker_matrix(worker_id) for worker_id in worker_ids}

    main_inner_values = []
    main_outer_values = []
    threshold_values = []
    main_n_iter_values = []
    main_fit_count = 0
    for key in MAIN_KEYS:
        worker, point = _condition_worker_and_point(key, outer_fold)
        representation = _point_slice(matrices, worker, point)
        inner, outer, threshold_index, n_iter, fits = _fit_main_condition(
            representation,
            fold_ids,
            outer_fold,
            inner_ordinals,
            outer_train_labels,
        )
        main_inner_values.append(inner)
        main_outer_values.append(outer)
        threshold_values.append(threshold_index)
        main_n_iter_values.append(n_iter)
        main_fit_count += fits
        del representation
    main_inner = np.ascontiguousarray(np.stack(main_inner_values), dtype=np.float64)
    main_outer = np.ascontiguousarray(np.stack(main_outer_values), dtype=np.float64)
    thresholds = np.asarray(threshold_values, dtype=np.int16)
    main_n_iter = np.ascontiguousarray(np.stack(main_n_iter_values), dtype=np.int32)
    if main_fit_count != MAIN_FITS_PER_FOLD:
        raise ValueError("EXP-070 per-fold main fit inventory drift")

    permutations = {
        shuffle_seed: build_shuffle_permutation(2688, shuffle_seed, outer_fold)
        for shuffle_seed in SHUFFLE_SEEDS
    }
    permutation_digests = [
        bytes_sha256(np.ascontiguousarray(permutations[seed], dtype=np.int64).tobytes(order="C"))
        for seed in SHUFFLE_SEEDS
    ]
    shuffle_outer_values = []
    shuffle_n_iter_values = []
    shuffle_fit_count = 0
    for key in SHUFFLE_KEYS:
        shuffle_name, condition = key.split("|", 1)
        model, point = condition.split(":", 1)
        shuffle_seed = int(shuffle_name.removeprefix("shuffle-"))
        worker = "base" if model == "frozen" else f"{model}-f{outer_fold}"
        shuffled_labels = outer_train_labels[permutations[shuffle_seed]]
        representation = _point_slice(matrices, worker, point)
        probability, n_iter, fits = _fit_shuffle_condition(
            representation,
            fold_ids,
            outer_fold,
            inner_ordinals,
            shuffled_labels,
        )
        shuffle_outer_values.append(probability)
        shuffle_n_iter_values.append(n_iter)
        shuffle_fit_count += fits
        del representation
    shuffle_outer = np.ascontiguousarray(np.stack(shuffle_outer_values), dtype=np.float64)
    shuffle_n_iter = np.ascontiguousarray(
        np.stack(shuffle_n_iter_values).reshape(3, 8, 6), dtype=np.int32
    )
    if shuffle_fit_count != SHUFFLE_FITS_PER_FOLD:
        raise ValueError("EXP-070 per-fold shuffle fit inventory drift")

    for matrix in matrices.values():
        del matrix
    matrices.clear()
    after = source_identity_snapshot(config)
    if before != after:
        raise ValueError("EXP-070 source snapshot changed during fit-fold")

    folds_dir = private_root(config) / "folds"
    bundle_path = folds_dir / f"f{outer_fold}.npz"
    arrays = {
        "outer_train_ordinals": np.ascontiguousarray(inner_ordinals, dtype=np.int32),
        "outer_heldout_ordinals": np.ascontiguousarray(outer_ordinals, dtype=np.int32),
        "main_inner_oof_probability": main_inner,
        "main_outer_heldout_probability": main_outer,
        "main_threshold_index": thresholds,
        "main_n_iter": main_n_iter,
        "shuffle_outer_heldout_probability": shuffle_outer.reshape(3, 8, 672, 6),
        "shuffle_n_iter": shuffle_n_iter,
    }
    bundle_record = _write_npz_once(bundle_path, arrays)
    validate_fold_bundle(bundle_path, outer_fold)
    resources = _assert_resource_use(config, started=started)
    private_bytes = _private_disk_gate(config)
    seal = {
        "schema_version": "exp-070-probe-fold-seal-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "outer_fold": outer_fold,
        "status": "Sealed",
        "npz": bundle_record,
        "main_condition_order": list(MAIN_KEYS),
        "shuffle_condition_order": list(SHUFFLE_CONDITIONS),
        "inner_fold_order": [fold for fold in FOLDS if fold != outer_fold],
        "source_before": before,
        "source_after": after,
        "permutation_sha256": dict(zip(map(str, SHUFFLE_SEEDS), permutation_digests, strict=True)),
        "fit_counts": {
            "main_binary_fits": main_fit_count,
            "shuffle_binary_fits": shuffle_fit_count,
            "total_binary_fits": main_fit_count + shuffle_fit_count,
        },
        "convergence": {
            "main_n_iter_max": int(np.max(main_n_iter)),
            "shuffle_n_iter_max": int(np.max(shuffle_n_iter)),
            "all_within_max_iter": True,
        },
        "resources": {**resources, "private_exp070_bytes": private_bytes},
        "access": {
            "fold_manifest_container_bytes_read": True,
            "outer_train_label_values_read": True,
            "outer_heldout_label_values_decoded": False,
            "representation_values_read": True,
            "model_loaded": False,
            "forward_executed": False,
            "validation_accessed": False,
            "test_accessed": False,
        },
    }
    create_json_once(folds_dir / f"f{outer_fold}.json", seal, private=True)
    return seal


def build_bootstrap_plan(
    fold_ids: Any,
    component_ids: Sequence[str],
    labels: Any,
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[list[Any], str]:
    """Build the one shared duplicate-component bootstrap plan.

    RNG consumption is replicate-major and fold-minor.  Component universes
    are sorted by UTF-8 bytes, and rows within a selected component remain in
    ascending source ordinal order.
    """
    import numpy as np

    fold_array = np.asarray(fold_ids, dtype=np.int8)
    truth = np.asarray(labels, dtype=np.uint8)
    if (
        fold_array.ndim != 1
        or truth.shape != (fold_array.shape[0], 6)
        or len(component_ids) != fold_array.shape[0]
        or replicates <= 0
        or seed != BOOTSTRAP_SEED
    ):
        raise ValueError("EXP-070 bootstrap input drift")
    if any(type(value) is not str or not value for value in component_ids):
        raise ValueError("EXP-070 component identity drift")

    component_rows_by_fold: dict[int, list[tuple[str, Any]]] = {}
    component_owner: dict[str, int] = {}
    for fold in FOLDS:
        members: dict[str, list[int]] = {}
        for ordinal in np.flatnonzero(fold_array == fold).tolist():
            component = component_ids[ordinal]
            previous = component_owner.setdefault(component, fold)
            if previous != fold:
                raise ValueError("EXP-070 bootstrap component leakage")
            members.setdefault(component, []).append(ordinal)
        ordered = sorted(members, key=lambda value: value.encode("utf-8"))
        if not ordered:
            raise ValueError("EXP-070 bootstrap empty fold")
        component_rows_by_fold[fold] = [
            (component, np.asarray(sorted(members[component]), dtype=np.int32))
            for component in ordered
        ]

    rng = np.random.Generator(np.random.PCG64(seed))
    digest = hashlib.sha256()
    plan: list[Any] = []
    for replicate in range(replicates):
        blocks = []
        digest.update(replicate.to_bytes(4, "little", signed=False))
        for fold in FOLDS:
            universe = component_rows_by_fold[fold]
            draw_indices = np.asarray(
                rng.integers(
                    0,
                    len(universe),
                    size=len(universe),
                    dtype=np.int64,
                    endpoint=False,
                ),
                dtype=np.int64,
            )
            digest.update(fold.to_bytes(1, "little", signed=False))
            digest.update(len(universe).to_bytes(4, "little", signed=False))
            digest.update(draw_indices.tobytes(order="C"))
            blocks.extend(universe[index][1] for index in draw_indices.tolist())
        rows = np.ascontiguousarray(np.concatenate(blocks), dtype=np.int32)
        sampled = truth[rows]
        for column in range(6):
            if not np.array_equal(np.unique(sampled[:, column]), np.asarray([0, 1], dtype=np.uint8)):
                raise ValueError(
                    f"EXP-070 invalid bootstrap replicate {replicate} for label {LABELS[column]}"
                )
        digest.update(rows.shape[0].to_bytes(4, "little", signed=False))
        digest.update(rows.tobytes(order="C"))
        plan.append(rows)
    return plan, digest.hexdigest()


def metric_bundle(labels: Any, probabilities: Any, predicted: Any) -> dict[str, Any]:
    import numpy as np
    from sklearn.metrics import average_precision_score, f1_score, hamming_loss, accuracy_score

    truth = np.asarray(labels, dtype=np.uint8)
    values = np.asarray(probabilities, dtype=np.float64)
    guess = np.asarray(predicted, dtype=np.uint8)
    if truth.shape != values.shape or truth.shape != guess.shape or truth.ndim != 2 or truth.shape[1] != 6:
        raise ValueError("EXP-070 metric input shape drift")
    if not np.all(np.isfinite(values)) or np.any(values < 0.0) or np.any(values > 1.0):
        raise ValueError("EXP-070 metric probability drift")
    if not np.all(np.isin(truth, [0, 1])) or not np.all(np.isin(guess, [0, 1])):
        raise ValueError("EXP-070 metric binary input drift")
    for column in range(6):
        if not np.array_equal(np.unique(truth[:, column]), np.asarray([0, 1], dtype=np.uint8)):
            raise ValueError(f"EXP-070 metric label support drift: {LABELS[column]}")

    per_label_ap = np.asarray(
        average_precision_score(truth, values, average=None), dtype=np.float64
    )
    per_label_f1 = np.asarray(
        f1_score(truth, guess, average=None, zero_division=0), dtype=np.float64
    )
    return {
        "five_label_macro_ap": float(
            average_precision_score(
                truth[:, list(PRIMARY_COLUMNS)], values[:, list(PRIMARY_COLUMNS)], average="macro"
            )
        ),
        "six_label_macro_ap": float(average_precision_score(truth, values, average="macro")),
        "six_label_macro_f1": float(f1_score(truth, guess, average="macro", zero_division=0)),
        "five_label_macro_f1": float(
            f1_score(
                truth[:, list(PRIMARY_COLUMNS)],
                guess[:, list(PRIMARY_COLUMNS)],
                average="macro",
                zero_division=0,
            )
        ),
        "micro_ap": float(average_precision_score(truth, values, average="micro")),
        "micro_f1": float(f1_score(truth, guess, average="micro", zero_division=0)),
        "hamming_loss": float(hamming_loss(truth, guess)),
        "subset_accuracy": float(accuracy_score(truth, guess)),
        "per_label_ap": dict(zip(LABELS, map(float, per_label_ap), strict=True)),
        "per_label_f1": dict(zip(LABELS, map(float, per_label_f1), strict=True)),
    }


def ap_bundle(labels: Any, probabilities: Any) -> dict[str, Any]:
    import numpy as np
    from sklearn.metrics import average_precision_score

    truth = np.asarray(labels, dtype=np.uint8)
    values = np.asarray(probabilities, dtype=np.float64)
    if truth.shape != values.shape or truth.ndim != 2 or truth.shape[1] != 6 or not np.all(np.isfinite(values)):
        raise ValueError("EXP-070 AP input drift")
    for column in range(6):
        if not np.array_equal(np.unique(truth[:, column]), np.asarray([0, 1], dtype=np.uint8)):
            raise ValueError(f"EXP-070 AP label support drift: {LABELS[column]}")
    per_label = np.asarray(
        average_precision_score(truth, values, average=None), dtype=np.float64
    )
    return {
        "five_label_macro_ap": float(
            average_precision_score(
                truth[:, list(PRIMARY_COLUMNS)], values[:, list(PRIMARY_COLUMNS)], average="macro"
            )
        ),
        "six_label_macro_ap": float(average_precision_score(truth, values, average="macro")),
        "per_label_ap": dict(zip(LABELS, map(float, per_label), strict=True)),
    }


def _numeric_leaves(value: Mapping[str, Any], prefix: str = "") -> dict[str, float]:
    result: dict[str, float] = {}
    for key, item in value.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(item, Mapping):
            result.update(_numeric_leaves(item, name))
        elif type(item) in (int, float):
            result[name] = float(item)
        else:
            raise ValueError(f"Non-numeric metric leaf: {name}")
    return result


def _unflatten_numeric(value: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for compound, item in value.items():
        current = result
        parts = compound.split(".")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = item
    return result


def metric_delta(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    left_flat = _numeric_leaves(left)
    right_flat = _numeric_leaves(right)
    if set(left_flat) != set(right_flat):
        raise ValueError("EXP-070 metric delta schema drift")
    return _unflatten_numeric({key: left_flat[key] - right_flat[key] for key in left_flat})


def bootstrap_metric_delta_intervals(
    labels: Any,
    left_probabilities: Any,
    left_predictions: Any,
    right_probabilities: Any,
    right_predictions: Any,
    plan: Sequence[Any],
) -> dict[str, Any]:
    import numpy as np

    samples: dict[str, list[float]] = {}
    for rows in plan:
        delta = metric_delta(
            metric_bundle(labels[rows], left_probabilities[rows], left_predictions[rows]),
            metric_bundle(labels[rows], right_probabilities[rows], right_predictions[rows]),
        )
        for key, value in _numeric_leaves(delta).items():
            samples.setdefault(key, []).append(value)
    intervals = {
        key: [
            float(item)
            for item in np.percentile(values, [2.5, 97.5], method="linear")
        ]
        for key, values in samples.items()
    }
    return _unflatten_numeric(intervals)


def bootstrap_ap5_delta_interval(
    labels: Any,
    left_probabilities: Any,
    right_probabilities: Any,
    plan: Sequence[Any],
) -> list[float]:
    import numpy as np

    values = [
        ap_bundle(labels[rows], left_probabilities[rows])["five_label_macro_ap"]
        - ap_bundle(labels[rows], right_probabilities[rows])["five_label_macro_ap"]
        for rows in plan
    ]
    return [
        float(item)
        for item in np.percentile(values, [2.5, 97.5], method="linear")
    ]


def _array_digest(value: Any) -> str:
    import numpy as np

    return bytes_sha256(np.ascontiguousarray(value).tobytes(order="C"))


def _string_sequence_digest(values: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for value in values:
        payload = value.encode("utf-8")
        digest.update(len(payload).to_bytes(4, "little", signed=False))
        digest.update(payload)
    return digest.hexdigest()


def _main_predictions(probabilities: Any, threshold_by_row: Any) -> Any:
    import numpy as np

    values = np.asarray(probabilities, dtype=np.float64)
    thresholds = np.asarray(threshold_by_row, dtype=np.int16)
    if values.shape != (ROWS, 6) or thresholds.shape != (ROWS,):
        raise ValueError("EXP-070 prediction assembly shape drift")
    return (values >= thresholds[:, None] / 100.0).astype(np.uint8)


def _seed_pass(contrasts: Mapping[str, Any], seed: int) -> tuple[bool, dict[str, Any]]:
    detail: dict[str, Any] = {}
    for point in VOTING_POINTS:
        key = f"m3-s{seed}:{point}"
        result = contrasts[key]
        delta = float(result["delta"]["five_label_macro_ap"])
        interval = result["bootstrap_delta_intervals"]["five_label_macro_ap"]
        passed = delta > 0.0 and float(interval[0]) > 0.0
        detail[point] = {"delta": delta, "interval": interval, "passed": passed}
    return all(detail[point]["passed"] for point in VOTING_POINTS), detail


def _control_seed_pass(
    control_contrasts: Mapping[str, Any], shuffle_seed: int, seed: int
) -> tuple[bool, dict[str, Any]]:
    detail: dict[str, Any] = {}
    for point in VOTING_POINTS:
        key = f"shuffle-{shuffle_seed}|m3-s{seed}:{point}"
        result = control_contrasts[key]
        delta = float(result["delta_five_label_macro_ap"])
        interval = result["bootstrap_delta_interval"]
        passed = delta > 0.0 and float(interval[0]) > 0.0
        detail[point] = {"delta": delta, "interval": interval, "passed": passed}
    return all(detail[point]["passed"] for point in VOTING_POINTS), detail


def assemble_stage(config_path: Path) -> dict[str, Any]:
    import numpy as np

    config = load_config(config_path, expected_kind="formal")
    require_implementation_records(config)
    _authorization(config, formal=True)
    _access_contract(config, formal=True)
    _formal_static_completion(config)
    started = time.monotonic()
    require_environment(config)
    _free_disk_gate(config)
    require_frozen_sources(config, headers_only=False)
    seals = validate_fold_prefix(config, 5)
    before = source_identity_snapshot(config)

    # This is intentionally after all five external seals have passed.
    public_rows = _public_fold_rows()
    labels = load_all_labels(public_rows)
    fold_ids = np.asarray([row["fold_id"] for row in public_rows], dtype=np.int8)
    component_ids = [row["component_id"] for row in public_rows]

    main_probabilities = {key: np.empty((ROWS, 6), dtype=np.float64) for key in MAIN_KEYS}
    main_threshold_rows = {key: np.empty(ROWS, dtype=np.int16) for key in MAIN_KEYS}
    thresholds_by_fold = {key: [None] * 5 for key in MAIN_KEYS}
    control_probabilities = {key: np.empty((ROWS, 6), dtype=np.float64) for key in SHUFFLE_KEYS}
    bundle_records = []

    for outer_fold in FOLDS:
        path = private_root(config) / "folds" / f"f{outer_fold}.npz"
        bundle_records.append(_npz_artifact(path))
        with np.load(path, allow_pickle=False) as bundle:
            inner_ordinals = np.asarray(bundle["outer_train_ordinals"], dtype=np.int32)
            outer_ordinals = np.asarray(bundle["outer_heldout_ordinals"], dtype=np.int32)
            expected_inner = np.flatnonzero(fold_ids != outer_fold).astype(np.int32)
            expected_outer = np.flatnonzero(fold_ids == outer_fold).astype(np.int32)
            if not np.array_equal(inner_ordinals, expected_inner) or not np.array_equal(outer_ordinals, expected_outer):
                raise ValueError(f"EXP-070 bundle ordinal drift: fold {outer_fold}")

            inner_probabilities = np.asarray(bundle["main_inner_oof_probability"], dtype=np.float64)
            outer_probabilities = np.asarray(bundle["main_outer_heldout_probability"], dtype=np.float64)
            saved_thresholds = np.asarray(bundle["main_threshold_index"], dtype=np.int16)
            for position, key in enumerate(MAIN_KEYS):
                independently_selected = select_threshold_index(
                    labels[inner_ordinals], inner_probabilities[position]
                )
                if independently_selected != int(saved_thresholds[position]):
                    raise ValueError(f"EXP-070 sealed threshold mismatch: fold {outer_fold}, {key}")
                main_probabilities[key][outer_ordinals] = outer_probabilities[position]
                main_threshold_rows[key][outer_ordinals] = independently_selected
                thresholds_by_fold[key][outer_fold] = independently_selected

            saved_shuffle_digests = [
                seals[outer_fold]["permutation_sha256"][str(seed)]
                for seed in SHUFFLE_SEEDS
            ]
            expected_shuffle_digests = [
                _array_digest(build_shuffle_permutation(2688, seed, outer_fold))
                for seed in SHUFFLE_SEEDS
            ]
            if saved_shuffle_digests != expected_shuffle_digests:
                raise ValueError(f"EXP-070 shuffle digest mismatch: fold {outer_fold}")
            shuffle_probabilities = np.asarray(
                bundle["shuffle_outer_heldout_probability"], dtype=np.float64
            ).reshape(24, 672, 6)
            for position, key in enumerate(SHUFFLE_KEYS):
                control_probabilities[key][outer_ordinals] = shuffle_probabilities[position]

    if any(value is None for values in thresholds_by_fold.values() for value in values):
        raise ValueError("EXP-070 threshold fold coverage drift")
    for collection in (main_probabilities, control_probabilities):
        for key, values in collection.items():
            if not np.all(np.isfinite(values)) or np.any(values < 0.0) or np.any(values > 1.0):
                raise ValueError(f"EXP-070 OOF probability coverage drift: {key}")

    main_predictions = {
        key: _main_predictions(main_probabilities[key], main_threshold_rows[key])
        for key in MAIN_KEYS
    }
    main_metrics = {
        key: metric_bundle(labels, main_probabilities[key], main_predictions[key])
        for key in MAIN_KEYS
    }
    bootstrap_plan, bootstrap_plan_sha256 = build_bootstrap_plan(
        fold_ids, component_ids, labels
    )

    main_contrasts: dict[str, Any] = {}
    for key in MAIN_KEYS:
        if key.startswith("frozen:"):
            continue
        point = key.split(":", 1)[1]
        base_key = f"frozen:{point}"
        main_contrasts[key] = {
            "baseline": base_key,
            "delta": metric_delta(main_metrics[key], main_metrics[base_key]),
            "bootstrap_delta_intervals": bootstrap_metric_delta_intervals(
                labels,
                main_probabilities[key],
                main_predictions[key],
                main_probabilities[base_key],
                main_predictions[base_key],
                bootstrap_plan,
            ),
        }

    seed_votes: dict[str, Any] = {}
    passed_seeds = 0
    for seed in (43, 44):
        passed, detail = _seed_pass(main_contrasts, seed)
        seed_votes[str(seed)] = {"passed": passed, "points": detail}
        passed_seeds += int(passed)

    control_metrics = {
        key: ap_bundle(labels, control_probabilities[key]) for key in SHUFFLE_KEYS
    }
    control_contrasts: dict[str, Any] = {}
    for key in SHUFFLE_KEYS:
        shuffle_name, condition = key.split("|", 1)
        model, point = condition.split(":", 1)
        if model == "frozen":
            continue
        base_key = f"{shuffle_name}|frozen:{point}"
        delta = (
            control_metrics[key]["five_label_macro_ap"]
            - control_metrics[base_key]["five_label_macro_ap"]
        )
        control_contrasts[key] = {
            "baseline": base_key,
            "delta_five_label_macro_ap": float(delta),
            "bootstrap_delta_interval": bootstrap_ap5_delta_interval(
                labels,
                control_probabilities[key],
                control_probabilities[base_key],
                bootstrap_plan,
            ),
        }

    control_votes: dict[str, Any] = {}
    negative_control_failure = False
    for shuffle_seed in SHUFFLE_SEEDS:
        per_seed: dict[str, Any] = {}
        both_prospective_pass = True
        for seed in (43, 44):
            passed, detail = _control_seed_pass(control_contrasts, shuffle_seed, seed)
            per_seed[str(seed)] = {"passed": passed, "points": detail}
            both_prospective_pass = both_prospective_pass and passed
        control_votes[str(shuffle_seed)] = {
            "prospective_seeds": per_seed,
            "both_prospective_seeds_pass": both_prospective_pass,
        }
        negative_control_failure = negative_control_failure or both_prospective_pass

    representation_state = None if negative_control_failure else passed_seeds
    representation_state_label = (
        None
        if representation_state is None
        else _method_from_config(config)["seed_roles"]["states"][str(representation_state)]
    )
    total_main_fits = sum(int(seal["fit_counts"]["main_binary_fits"]) for seal in seals)
    total_shuffle_fits = sum(int(seal["fit_counts"]["shuffle_binary_fits"]) for seal in seals)
    if total_main_fits != TOTAL_MAIN_FITS or total_shuffle_fits != TOTAL_SHUFFLE_FITS:
        raise ValueError("EXP-070 aggregate fit inventory drift")

    assemble_resources = _assert_resource_use(config, started=started)
    aggregate_elapsed = sum(float(seal["resources"]["elapsed_seconds"]) for seal in seals) + assemble_resources["elapsed_seconds"]
    aggregate_peak = max(
        [int(seal["resources"]["peak_rss_bytes"]) for seal in seals]
        + [assemble_resources["peak_rss_bytes"]]
    )
    resources_contract = _resource_contract(config)
    if aggregate_elapsed > float(resources_contract["formal_wall_seconds"]):
        raise TimeoutError("EXP-070 aggregate probe wall-time ceiling exceeded")
    if aggregate_peak > int(resources_contract["probe_peak_rss_bytes"]):
        raise MemoryError("EXP-070 aggregate probe peak-RSS ceiling exceeded")
    after = source_identity_snapshot(config)
    if before != after:
        raise ValueError("EXP-070 source snapshot changed during assemble")

    aggregate_results = {
        "threshold_indices_by_outer_fold": thresholds_by_fold,
        "main_metrics": main_metrics,
        "main_contrasts": main_contrasts,
        "seed_votes": seed_votes,
        "control_metrics": control_metrics,
        "control_contrasts": control_contrasts,
        "control_votes": control_votes,
        "negative_control_failure": negative_control_failure,
        "representation_state": representation_state,
        "representation_state_label": representation_state_label,
    }
    private_manifest = {
        "schema_version": "exp-070-probe-manifest-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "status": "CompletedAwaitingVerification",
        "config": _config_record(config_path),
        "source_identity_snapshot": before,
        "fold_bundles": bundle_records,
        "row_identity": {
            "ordinal_sha256": _array_digest(np.arange(ROWS, dtype=np.int32)),
            "fold_id_sha256": _array_digest(fold_ids),
            "component_id_order_sha256": _string_sequence_digest(component_ids),
            "labels_sha256": _array_digest(labels),
        },
        "bootstrap": {
            "replicates": BOOTSTRAP_REPLICATES,
            "plan_sha256": bootstrap_plan_sha256,
            "percentile_method": "linear",
            "plan_persisted": False,
        },
        "fit_counts": {
            "main": total_main_fits,
            "shuffle": total_shuffle_fits,
            "total": total_main_fits + total_shuffle_fits,
        },
        "results": aggregate_results,
        "resources": {
            "aggregate_elapsed_seconds": aggregate_elapsed,
            "maximum_peak_rss_bytes": aggregate_peak,
            "assemble": assemble_resources,
        },
        "access": {
            "outer_train_label_values_read": True,
            "outer_heldout_label_values_read_after_all_fold_seals": True,
            "representation_values_read_by_assemble": False,
            "sealed_probability_values_read": True,
            "model_loaded": False,
            "forward_executed": False,
            "validation_accessed": False,
            "test_accessed": False,
        },
        "claim_boundary": config["claim_boundary"],
    }
    private_manifest_record = create_json_once(
        private_root(config) / "probe-manifest.json", private_manifest, private=True
    )
    private_bytes = _private_disk_gate(config)
    report = {
        "schema_version": "exp-070-probe-run-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "stage": "formal-probe",
        "status": "CompletedAwaitingVerification",
        "config": _config_record(config_path),
        "probe_manifest": private_manifest_record,
        "counts": {
            "rows": ROWS,
            "folds": 5,
            "main_conditions": 24,
            "shuffle_conditions_per_fold": 24,
            "main_binary_fits": total_main_fits,
            "shuffle_binary_fits": total_shuffle_fits,
            "binary_fits": total_main_fits + total_shuffle_fits,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        },
        "results": aggregate_results,
        "resources": {
            "aggregate_elapsed_seconds": aggregate_elapsed,
            "maximum_peak_rss_bytes": aggregate_peak,
            "private_exp070_bytes": private_bytes,
            "api_cost_usd": 0,
        },
        "access": private_manifest["access"],
        "formal_probe_complete": False,
        "exp070_complete": False,
        "exp071_authorized": False,
        "claim_boundary": config["claim_boundary"],
    }
    create_json_once(public_root(config) / "probe.json", report, private=False)
    return report


@contextmanager
def exclusive_probe_lock() -> Iterator[None]:
    lock_path = resolve_project(
        "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
        "locks/exp070-formal-probe.lock"
    )
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if lock_path.parent.is_symlink() or not lock_path.parent.is_dir():
        raise PermissionError("Unsafe EXP-070 probe lock directory")
    os.chmod(lock_path.parent, 0o700)
    try:
        descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise ProbeLockBusy("EXP-070 formal probe worker is already active") from error
    identity = os.fstat(descriptor)
    try:
        os.write(descriptor, canonical_json_bytes({"pid": os.getpid()}))
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        yield
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if os.path.lexists(lock_path):
            current = os.lstat(lock_path)
            if current.st_dev != identity.st_dev or current.st_ino != identity.st_ino:
                raise RuntimeError("EXP-070 probe lock identity changed")
            os.unlink(lock_path)


class ProbeLockBusy(RuntimeError):
    """A no-state refusal because another formal probe process owns the lock."""


def _write_terminal_failure(
    config_path: Path, stage: str, outer_fold: int | None, error: BaseException
) -> None:
    try:
        config = strict_json(config_path)
        if not isinstance(config, Mapping) or _config_kind(config) != "formal":
            return
        pub = public_root(config)
        if (
            not pub.is_dir()
            or not (pub / "run-claim.json").is_file()
            or (pub / "probe.json").exists()
            or (pub / "failure.json").exists()
        ):
            return
        value = {
            "schema_version": "exp-070-formal-probe-failure-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": config.get("run_id"),
            "attempt_id": config.get("attempt_id"),
            "stage": stage,
            "outer_fold": outer_fold,
            "status": "Failed",
            "error_type": type(error).__name__,
            "error_detail_public": False,
            "same_attempt_resume": False,
            "model_loaded": False,
            "forward_executed": False,
            "validation_accessed": False,
            "test_accessed": False,
        }
        create_json_once(pub / "failure.json", value, private=False)
    except Exception:
        return


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("static", "initialize", "fit-fold", "assemble"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--fold", type=int)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.stage == "static":
        if args.fold is not None:
            raise ValueError("Static stage does not accept --fold")
        config_path = args.config or DEFAULT_STATIC_CONFIG
        result = static_stage(config_path)
        print(json.dumps({"stage": "static", "status": result["status"]}, sort_keys=True))
        return 0

    config_path = args.config or DEFAULT_FORMAL_CONFIG
    if args.stage == "fit-fold" and args.fold not in FOLDS:
        raise ValueError("fit-fold requires --fold 0..4")
    if args.stage != "fit-fold" and args.fold is not None:
        raise ValueError(f"{args.stage} does not accept --fold")
    try:
        with exclusive_probe_lock():
            if args.stage == "initialize":
                result = initialize_stage(config_path)
            elif args.stage == "fit-fold":
                result = fit_fold_stage(config_path, int(args.fold))
            else:
                result = assemble_stage(config_path)
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
        return 0
    except ProbeLockBusy as error:
        print(f"ProbeLockBusy: {error}", file=sys.stderr)
        return 2
    except BaseException as error:
        _write_terminal_failure(config_path, args.stage, args.fold, error)
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
