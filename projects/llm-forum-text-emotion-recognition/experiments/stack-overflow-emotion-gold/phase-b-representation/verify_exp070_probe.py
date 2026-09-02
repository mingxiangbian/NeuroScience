#!/usr/bin/env python3
"""Independently verify the EXP-070 formal probe consumer.

Static verification reads artifact identities and NPY headers, then runs the
frozen synthetic suite in an isolated child process. Formal verification reads
the sealed probability bundles and the private fold-label manifest, then
recomputes thresholds, metrics, bootstrap intervals, votes, and the
negative-control override. Separate completion invocations rerun the full
read-only verification and accept only an exact Passed prefix. This module
never imports the producer and never refits a probe.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import resource
import shutil
import stat
import struct
import subprocess
import sys
import time
from typing import Any, Iterator, Mapping, Sequence
import zipfile


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
SOURCE_SNAPSHOT_SHA256 = "cdcde7fd617aee9d6189d6a7e87778a6617cdf0a6db658a397928b7e20910bad"
EXPECTED_METHOD_SHA256 = "5ec0e5d050d08b70fdc86badf77e0f5dae72282bf060e173135a37af8e910e3f"
EXTRACTION_PUBLIC_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
    "exp-070-layerwise-probes/formal-extraction-attempt-1"
)
EXTRACTION_PRIVATE_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
    "exp-070-layerwise-probes/formal-extraction-attempt-1"
)

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

FORMAL_CHECKS = [
    "config_identity",
    "method_identity",
    "implementation_identity",
    "static_completion_binding",
    "source_recovery_completion",
    "source_snapshot_identity",
    "formal_public_inventory_modes_links",
    "formal_private_inventory_modes_links",
    "run_claim_binding",
    "input_manifest_binding",
    "five_fold_seal_schema",
    "five_fold_npz_schema",
    "fold_ordinal_partition",
    "condition_orders",
    "fit_inventory_4320",
    "solver_iteration_gates",
    "source_before_after_seals",
    "shuffle_permutation_digests",
    "independent_threshold_selection",
    "probability_range_and_finite",
    "label_source_alignment",
    "component_disjointness",
    "single_pcg64_bootstrap_plan",
    "bootstrap_plan_digest",
    "bootstrap_label_validity",
    "independent_metrics",
    "independent_metric_deltas",
    "independent_bootstrap_intervals",
    "independent_seed_votes",
    "independent_negative_control_override",
    "probe_manifest_binding",
    "probe_run_exact_results",
    "resource_ceilings",
    "consumer_private_budget",
    "access_boundary",
    "public_privacy",
    "probability_only_no_refit",
    "no_model_forward_validation_test",
    "source_unchanged",
]

FORBIDDEN_MODEL_MODULES = {"mlx", "mlx_lm", "torch", "transformers"}
STATIC_VALUE_MODULES = {"numpy", "sklearn", "scipy"}


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
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def require_canonical_json(path: Path) -> Any:
    value = strict_json(path)
    if path.read_bytes() != canonical_json_bytes(value):
        raise ValueError(f"Non-canonical JSON artifact: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bytes_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def resolve_project(relative: str, *, must_exist: bool = True) -> Path:
    if type(relative) is not str:
        raise TypeError("Project path must be a string")
    pure = PurePosixPath(relative)
    if not relative or pure.is_absolute() or pure.as_posix() != relative:
        raise ValueError("Unsafe project path")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("Unsafe project path")
    path = PROJECT_ROOT.joinpath(*pure.parts)
    current = PROJECT_ROOT
    for part in pure.parts:
        current = current / part
        if os.path.lexists(current) and current.is_symlink():
            raise ValueError(f"Symlink path rejected: {relative}")
    if must_exist and not os.path.lexists(path):
        raise FileNotFoundError(path)
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


def create_json_once(path: Path, value: Any) -> dict[str, Any]:
    if os.path.lexists(path):
        raise FileExistsError(path)
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise ValueError("Unsafe verifier output directory")
    payload = canonical_json_bytes(value)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    if os.path.lexists(temporary):
        raise FileExistsError(temporary)
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(descriptor)
        os.chmod(temporary, 0o644)
        os.link(temporary, path)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)
    return artifact(path)


def require_safe_root(root: Path, *, private: bool) -> set[str]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"Unsafe artifact root: {root}")
    expected_mode = "0700" if private else "0755"
    if file_mode(root) != expected_mode:
        raise PermissionError(f"Root mode drift: {root}")
    entries = list(root.rglob("*"))
    if any(item.is_symlink() for item in entries):
        raise PermissionError(f"Nested symlink rejected: {root}")
    if any(not item.is_file() and not item.is_dir() for item in entries):
        raise PermissionError(f"Special filesystem entry rejected: {root}")
    return {item.relative_to(root).as_posix() for item in entries if item.is_file()}


def require_file_modes(root: Path, names: Sequence[str], *, private: bool) -> None:
    expected = "0600" if private else "0644"
    for name in names:
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError(f"Unsafe artifact: {path}")
        if file_mode(path) != expected:
            raise PermissionError(f"Artifact mode drift: {path}")


def _read_exact(handle: Any, size: int) -> bytes:
    value = handle.read(size)
    if len(value) != size:
        raise ValueError("Truncated NPY header")
    return value


def read_npy_header(path: Path) -> dict[str, Any]:
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
    if schema == "exp-070-formal-probe-preflight-config-v1":
        return "static"
    if schema == "exp-070-formal-probe-config-v1":
        return "formal"
    raise ValueError("Unrecognized EXP-070 probe config")


def _normalize_json_numbers(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_json_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_json_numbers(item) for item in value]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return value


def method_sha256(config: Mapping[str, Any]) -> str:
    if set(config.get("method", {})) != {
        "labels", "points", "outer_cv", "probe", "threshold", "metrics",
        "seed_roles", "label_shuffle", "bootstrap", "fit_inventory",
    }:
        raise ValueError("EXP-070 method object schema drift")
    return bytes_sha256(canonical_json_bytes(_normalize_json_numbers(config["method"])))


def validate_probability_contract(config: Mapping[str, Any]) -> None:
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
    value = config.get("private_probability_artifact")
    if not isinstance(value, Mapping) or value.get("arrays") != expected_arrays:
        raise ValueError("EXP-070 private probability schema drift")
    if (
        value.get("writer") != "numpy.savez"
        or value.get("compressed") is not False
        or value.get("directory_mode") != "0700"
        or value.get("file_mode") != "0600"
        or value.get("layout") != "C"
        or value.get("seal_written_last") is not True
        or value.get("npz_without_seal") != "terminal_orphan_no_same_attempt_resume"
        or value.get("final_verifier") != "probability_only_no_refit"
    ):
        raise ValueError("EXP-070 private probability contract drift")
    forbidden = {
        "labels", "predictions", "sample_ids", "component_ids", "coefficients",
        "scalers", "representations", "text",
    }
    if set(value.get("forbidden_members", [])) != forbidden:
        raise ValueError("EXP-070 forbidden private member drift")


def validate_resources(config: Mapping[str, Any]) -> Mapping[str, Any]:
    expected = {
        "maximum_concurrent_probe_workers": 1,
        "maximum_binary_probe_fits": TOTAL_BINARY_FITS,
        "formal_wall_seconds": 43200,
        "probe_peak_rss_bytes": 8589934592,
        "consumer_private_budget_bytes": 536870912,
        "threads_per_library": 1,
        "api_cost_usd": 0,
    }
    value = config.get("resources")
    if (
        not isinstance(value, Mapping)
        or set(value) != set(expected)
        or any(value.get(key) != item for key, item in expected.items())
    ):
        raise ValueError("EXP-070 resource contract drift")
    return value


def validate_outputs(config: Mapping[str, Any]) -> None:
    outputs = config.get("outputs")
    if not isinstance(outputs, Mapping):
        raise ValueError("EXP-070 output contract missing")
    expected_keys = {
        "preflight_public_root", "preflight_private_root", "formal_public_root",
        "formal_private_root", "preflight_public_success_allowlist",
        "preflight_public_runner_failure_allowlist",
        "preflight_public_verifier_failure_allowlist", "preflight_private_allowlist",
        "formal_public_claim_allowlist", "formal_public_awaiting_verification_allowlist",
        "formal_public_verified_allowlist", "formal_public_success_allowlist",
        "formal_public_runner_failure_allowlist", "formal_private_top_level_allowlist",
        "formal_private_fold_allowlist", "formal_private_success_allowlist",
    }
    if set(outputs) != expected_keys:
        raise ValueError("EXP-070 output key inventory drift")
    expected_roots = {
        "preflight_public_root": (
            "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
            "exp-070-layerwise-probes/formal-probe-preflight-attempt-1"
        ),
        "preflight_private_root": (
            "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
            "exp-070-layerwise-probes/formal-probe-preflight-attempt-1"
        ),
        "formal_public_root": (
            "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
            "exp-070-layerwise-probes/formal-probe-attempt-1"
        ),
        "formal_private_root": (
            "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
            "exp-070-layerwise-probes/formal-probe-attempt-1"
        ),
    }
    if any(outputs.get(key) != value for key, value in expected_roots.items()):
        raise ValueError("EXP-070 output root drift")
    fold_names = [name for fold in FOLDS for name in (f"f{fold}.npz", f"f{fold}.json")]
    if outputs.get("preflight_public_success_allowlist") != [
        "static.json", "static-verification.json", "no-result-complete.json"
    ]:
        raise ValueError("EXP-070 static public allowlist drift")
    if outputs.get("preflight_private_allowlist") != ["input-contract-manifest.json"]:
        raise ValueError("EXP-070 static private allowlist drift")
    if outputs.get("preflight_public_runner_failure_allowlist") != ["static.json"]:
        raise ValueError("EXP-070 static runner-failure allowlist drift")
    if outputs.get("preflight_public_verifier_failure_allowlist") != ["static.json", "static-verification.json"]:
        raise ValueError("EXP-070 static verifier-failure allowlist drift")
    if outputs.get("formal_public_claim_allowlist") != ["run-claim.json"]:
        raise ValueError("EXP-070 formal claim allowlist drift")
    if outputs.get("formal_public_awaiting_verification_allowlist") != ["run-claim.json", "probe.json"]:
        raise ValueError("EXP-070 formal public allowlist drift")
    if outputs.get("formal_public_verified_allowlist") != ["run-claim.json", "probe.json", "verification.json"]:
        raise ValueError("EXP-070 formal verified allowlist drift")
    if outputs.get("formal_public_success_allowlist") != [
        "run-claim.json", "probe.json", "verification.json", "probe-complete.json"
    ]:
        raise ValueError("EXP-070 formal success allowlist drift")
    if outputs.get("formal_public_runner_failure_allowlist") != ["run-claim.json", "failure.json"]:
        raise ValueError("EXP-070 formal runner-failure allowlist drift")
    if outputs.get("formal_private_top_level_allowlist") != ["input-manifest.json", "folds", "probe-manifest.json"]:
        raise ValueError("EXP-070 formal private top-level allowlist drift")
    if outputs.get("formal_private_fold_allowlist") != fold_names:
        raise ValueError("EXP-070 formal fold allowlist drift")
    if outputs.get("formal_private_success_allowlist") != [
        "input-manifest.json", *[f"folds/{name}" for name in fold_names], "probe-manifest.json"
    ]:
        raise ValueError("EXP-070 formal private allowlist drift")


def validate_authorization(config: Mapping[str, Any], *, formal: bool) -> None:
    value = config.get("authorization")
    if not isinstance(value, Mapping):
        raise PermissionError("Missing EXP-070 authorization")
    expected_keys = {
        "static_preflight", "initialize", "fit_folds", "assemble", "source_file_identity",
        "npy_headers", "representation_values", "label_source_rows", "label_values",
        "outer_train_label_use", "outer_heldout_label_use_after_fold_seals", "probe_fitting",
        "threshold_selection", "label_shuffle", "bootstrap", "performance_metrics",
        "final_verification", "formal_completion", "model_loading", "forward",
        "source_mutation", "validation", "test", "exp071",
    }
    if set(value) != expected_keys or value.get("source_file_identity") is not True or value.get("npy_headers") is not True:
        raise PermissionError("EXP-070 authorization key inventory drift")
    for key in ("model_loading", "forward", "source_mutation", "validation", "test", "exp071"):
        if value.get(key) is not False:
            raise PermissionError(f"Forbidden authorization enabled: {key}")
    formal_keys = (
        "initialize", "fit_folds", "assemble", "representation_values", "label_source_rows",
        "label_values", "outer_train_label_use", "outer_heldout_label_use_after_fold_seals",
        "probe_fitting", "threshold_selection", "label_shuffle", "bootstrap",
        "performance_metrics", "final_verification", "formal_completion",
    )
    if formal:
        if value.get("static_preflight") is not False:
            raise PermissionError("Formal config authorizes static work")
        if any(value.get(key) is not True for key in formal_keys):
            raise PermissionError("Formal authorization is incomplete")
    else:
        if value.get("static_preflight") is not True:
            raise PermissionError("Static authorization missing")
        if any(value.get(key) is not False for key in formal_keys):
            raise PermissionError("Static config over-authorizes formal work")


def validate_access(config: Mapping[str, Any], *, formal: bool) -> None:
    value = config.get("access")
    if not isinstance(value, Mapping):
        raise PermissionError("Missing EXP-070 access contract")
    static_keys = {
        "public_parent_json", "private_parent_metadata", "source_file_bytes_hashed",
        "npy_headers_read", "representation_array_values_read",
        "label_source_file_bytes_hashed", "label_source_rows_parsed", "label_values_read",
        "train_jsonl_accessed", "train_text_read", "model_loaded", "forward_executed",
        "real_probe_fitted", "threshold_selected", "shuffle_executed",
        "bootstrap_executed", "performance_metrics_computed", "validation_accessed",
        "test_accessed",
    }
    formal_keys = static_keys | {"representation_mmap_mode", "label_access_staging"}
    if set(value) != (formal_keys if formal else static_keys):
        raise PermissionError("EXP-070 access key inventory drift")
    for key in ("public_parent_json", "private_parent_metadata", "source_file_bytes_hashed", "npy_headers_read", "label_source_file_bytes_hashed"):
        if value.get(key) is not True:
            raise PermissionError(f"Required EXP-070 access missing: {key}")
    for key in (
        "train_jsonl_accessed", "train_text_read", "model_loaded", "forward_executed",
        "validation_accessed", "test_accessed",
    ):
        if value.get(key) is not False:
            raise PermissionError(f"Forbidden access enabled: {key}")
    value_keys = (
        "representation_array_values_read", "label_source_rows_parsed", "label_values_read",
        "real_probe_fitted", "threshold_selected", "shuffle_executed", "bootstrap_executed",
        "performance_metrics_computed",
    )
    expected = formal
    if any(value.get(key) is not expected for key in value_keys):
        raise PermissionError("EXP-070 value-access contract drift")
    if formal and value.get("representation_mmap_mode") != "r":
        raise PermissionError("EXP-070 representation mmap contract drift")
    if formal and value.get("label_access_staging") != (
        "outer_train_only_during_fit_fold_then_all_labels_during_assemble_after_five_fold_seals"
    ):
        raise PermissionError("EXP-070 label staging contract drift")


def validate_environment_config(config: Mapping[str, Any]) -> None:
    if config.get("environment") != PROBE_ENVIRONMENT:
        raise ValueError("EXP-070 environment config drift")


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
            for key in PROBE_ENVIRONMENT["thread_environment"]
        },
    }


def require_environment(config: Mapping[str, Any]) -> dict[str, Any]:
    validate_environment_config(config)
    observed = observed_environment()
    if observed != PROBE_ENVIRONMENT:
        raise EnvironmentError("EXP-070 verifier environment drift")
    if os.environ.get("PYTHONNOUSERSITE") != "1":
        raise EnvironmentError("PYTHONNOUSERSITE must equal 1")
    return observed


def validate_config(config: Mapping[str, Any], *, kind: str) -> None:
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
    if _config_kind(config) != kind:
        raise ValueError("EXP-070 config kind drift")
    base_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "rq_id", "tier",
        "registered_at", "stage", "parent_method", "source", "environment", "method",
        "private_probability_artifact", "resources", "authorization", "access", "outputs",
        "implementation", "claim_boundary",
    }
    expected_keys = base_keys | ({"preflight"} if kind == "formal" else set())
    if set(config) != expected_keys:
        raise ValueError("EXP-070 config top-level schema drift")
    if (
        config.get("experiment_id") != EXPERIMENT_ID
        or config.get("schema_version") != expected[0]
        or config.get("run_id") != expected[1]
        or config.get("attempt_id") != expected[2]
        or config.get("stage") != expected[3]
        or config.get("rq_id") != "RQ-S4.1"
    ):
        raise ValueError("EXP-070 config identity drift")
    if method_sha256(config) != EXPECTED_METHOD_SHA256:
        raise ValueError("EXP-070 method identity drift")
    validate_probability_contract(config)
    validate_resources(config)
    validate_outputs(config)
    validate_authorization(config, formal=kind == "formal")
    validate_access(config, formal=kind == "formal")
    validate_environment_config(config)


def load_config(path: Path, *, kind: str) -> dict[str, Any]:
    expected = DEFAULT_STATIC_CONFIG if kind == "static" else DEFAULT_FORMAL_CONFIG
    if path.resolve() != expected.resolve():
        raise ValueError("Only the frozen EXP-070 probe config is accepted")
    value = strict_json(path)
    if not isinstance(value, dict):
        raise ValueError("Config root must be an object")
    validate_config(value, kind=kind)
    return value


def require_implementation(config: Mapping[str, Any]) -> dict[str, Path]:
    value = config.get("implementation")
    if not isinstance(value, Mapping) or set(value) != {"protocol", "runner", "verifier", "tests"}:
        raise ValueError("EXP-070 implementation inventory drift")
    paths: dict[str, Path] = {}
    for name, record in value.items():
        if not isinstance(record, Mapping) or record.get("sha256") == "TBD" or record.get("bytes") == 0:
            raise ValueError("EXP-070 implementation is not frozen")
        paths[name] = require_record(record)
    if paths["verifier"].resolve() != Path(__file__).resolve():
        raise ValueError("EXP-070 verifier self identity drift")
    return paths


def _imports(path: Path) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    all_imports: set[str] = set()
    top_level: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            all_imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            all_imports.add(node.module.split(".")[0])
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_level.add(node.module.split(".")[0])
    return all_imports, top_level


def require_import_boundaries(paths: Mapping[str, Path], *, static: bool) -> None:
    for name in ("runner", "verifier"):
        all_imports, top_level = _imports(paths[name])
        if all_imports & FORBIDDEN_MODEL_MODULES:
            raise RuntimeError(f"Forbidden model import in {name}")
        if top_level & STATIC_VALUE_MODULES:
            raise RuntimeError(f"Value library imported at module scope in {name}")
    verifier_imports, _ = _imports(paths["verifier"])
    if "run_exp070_probe" in verifier_imports:
        raise RuntimeError("Verifier imports the producer")
    if {name.split(".")[0] for name in sys.modules} & FORBIDDEN_MODEL_MODULES:
        raise RuntimeError("Verifier process contains a forbidden model module")
    if static and ({name.split(".")[0] for name in sys.modules} & STATIC_VALUE_MODULES):
        raise RuntimeError("Static verifier imported a value library")


def _synthetic_test_summary(config: Mapping[str, Any], test_path: Path) -> dict[str, Any]:
    if test_path.resolve() != (MODULE_DIR / "tests" / "test_exp070_probe.py").resolve():
        raise ValueError("EXP-070 synthetic test path drift")
    claim_environment = {
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "TOKENIZERS_PARALLELISM": "false",
        "LC_ALL": "C",
        "LANG": "C",
        **PROBE_ENVIRONMENT["thread_environment"],
    }
    command_claim = {
        "python_executable": PROBE_ENVIRONMENT["python_executable"],
        "python_version": PROBE_ENVIRONMENT["python_version"],
        "arguments": ["-B", "-m", "unittest", "discover", "-s", "tests", "-p", test_path.name],
        "working_directory": "phase-b-representation",
        "environment": {
            key: claim_environment[key]
            for key in (
                "PYTHONNOUSERSITE", "PYTHONDONTWRITEBYTECODE", "HF_HUB_OFFLINE",
                "TRANSFORMERS_OFFLINE", "TOKENIZERS_PARALLELISM", "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
                "NUMEXPR_NUM_THREADS", "LC_ALL", "LANG",
            )
        },
        "timeout_seconds": 600,
    }
    return {
        "test_artifact": dict(config["implementation"]["tests"]),
        "tests_run": 34,
        "status": "Passed",
        "command_sha256": bytes_sha256(canonical_json_bytes(command_claim)),
    }


def run_synthetic_tests(config: Mapping[str, Any], test_path: Path) -> dict[str, Any]:
    expected = _synthetic_test_summary(config, test_path)
    command = [
        PROBE_ENVIRONMENT["python_executable"],
        "-B",
        "-m",
        "unittest",
        "discover",
        "-s",
        str(test_path.parent),
        "-p",
        test_path.name,
    ]
    frozen_environment = {
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "TOKENIZERS_PARALLELISM": "false",
        "LC_ALL": "C",
        "LANG": "C",
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        **PROBE_ENVIRONMENT["thread_environment"],
    }
    if os.environ.get("TMPDIR"):
        frozen_environment["TMPDIR"] = str(os.environ["TMPDIR"])
    completed = subprocess.run(
        command,
        cwd=MODULE_DIR,
        env=frozen_environment,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    combined = "\n".join((completed.stdout, completed.stderr))
    match = re.search(r"(?:^|\n)Ran ([0-9]+) tests? in [^\n]+", combined)
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    if completed.returncode != 0 or match is None or int(match.group(1)) != 34 or not lines or lines[-1] != "OK":
        raise RuntimeError("EXP-070 frozen synthetic suite failed")
    if {name.split(".")[0] for name in sys.modules} & STATIC_VALUE_MODULES:
        raise RuntimeError("Synthetic child polluted the static verifier process")
    return expected


def source_identity_snapshot(config: Mapping[str, Any]) -> dict[str, Any]:
    records: dict[str, dict[str, Any]] = {}
    for container in (config.get("source"), config.get("parent_method")):
        for record in iter_artifact_records(container):
            current = artifact(resolve_project(str(record["path"])))
            records[current["path"]] = current
    ordered = {key: records[key] for key in sorted(records)}
    return {"sha256": bytes_sha256(canonical_json_bytes(ordered)), "inventory": ordered}


def recovery_snapshot_digest() -> str:
    records: dict[str, dict[str, Any]] = {}
    for prefix, relative, private in (
        ("public", EXTRACTION_PUBLIC_ROOT, False),
        ("private", EXTRACTION_PRIVATE_ROOT, True),
    ):
        root = resolve_project(relative)
        if root.is_symlink() or not root.is_dir():
            raise ValueError("EXP-070 extraction source root drift")
        if file_mode(root) != ("0700" if private else "0755"):
            raise PermissionError("EXP-070 extraction source root mode drift")
        entries = list(root.rglob("*"))
        if any(item.is_symlink() for item in entries):
            raise PermissionError("EXP-070 extraction source symlink drift")
        if any(not item.is_file() and not item.is_dir() for item in entries):
            raise PermissionError("EXP-070 extraction source special-entry drift")
        for directory in (item for item in entries if item.is_dir()):
            if file_mode(directory) != ("0700" if private else "0755"):
                raise PermissionError("EXP-070 extraction source directory mode drift")
        for path in sorted(item for item in entries if item.is_file()):
            if path.stat().st_nlink != 1:
                raise PermissionError("EXP-070 extraction source hard-link drift")
            records[f"{prefix}/{path.relative_to(root).as_posix()}"] = {
                "bytes": path.stat().st_size,
                "mode": file_mode(path),
                "sha256": sha256(path),
            }
    return bytes_sha256(canonical_json_bytes(records))


def require_frozen_sources(config: Mapping[str, Any]) -> dict[str, Any]:
    source = config.get("source")
    if not isinstance(source, Mapping) or source.get("snapshot_sha256") != SOURCE_SNAPSHOT_SHA256:
        raise ValueError("EXP-070 source contract drift")
    for container in (source, config.get("parent_method")):
        for record in iter_artifact_records(container):
            require_record(record)
    completion_path = require_record(source["recovery_completion"])
    completion = strict_json(completion_path)
    if (
        completion.get("status") != "Complete"
        or completion.get("formal_extraction_complete") is not True
        or completion.get("probe_fitting_authorized") is not False
        or completion.get("exp070_complete") is not False
        or completion.get("source_mutated") is not False
    ):
        raise ValueError("EXP-070 extraction completion drift")
    verification = strict_json(require_record(source["recovery_verification"]))
    if verification.get("status") != "Passed" or verification.get("failed_count") != 0:
        raise ValueError("EXP-070 extraction verification drift")
    claim = strict_json(require_record(source["recovery_snapshot_claim"]))
    if claim.get("source_snapshot_sha256") != SOURCE_SNAPSHOT_SHA256:
        raise ValueError("EXP-070 source snapshot claim drift")
    if recovery_snapshot_digest() != SOURCE_SNAPSHOT_SHA256:
        raise ValueError("EXP-070 full extraction source snapshot drift")
    matrices = source.get("matrices")
    if not isinstance(matrices, list) or [item.get("worker_id") for item in matrices] != list(WORKER_IDS):
        raise ValueError("EXP-070 matrix inventory drift")
    workers = strict_json(require_record(source["private_extraction_manifest"])).get("workers")
    if not isinstance(workers, list) or [item.get("worker_id") for item in workers] != list(WORKER_IDS):
        raise ValueError("EXP-070 extraction worker inventory drift")
    observed_workers: list[dict[str, Any]] = []
    for configured, worker in zip(matrices, workers, strict=True):
        worker_id = configured["worker_id"]
        if worker_id == "base":
            expected_seed, expected_fold, expected_kind = None, None, "frozen"
            expected_points_list = list(ALL_POINTS)
        else:
            model, fold_text = worker_id.rsplit("-f", 1)
            expected_seed = int(model.removeprefix("m3-s"))
            expected_fold = int(fold_text)
            expected_kind = "m3"
            expected_points_list = list(ALL_POINTS if expected_seed == 42 else CONFIRMATION_POINTS)
        if (
            configured.get("kind") != expected_kind
            or configured.get("seed") != expected_seed
            or configured.get("fold") != expected_fold
            or configured.get("shape") != [ROWS, len(expected_points_list), 2560]
            or configured.get("points") != expected_points_list
        ):
            raise ValueError(f"EXP-070 configured matrix contract drift: {worker_id}")
        matrix_path = require_record(configured["artifact"])
        expected_points = 9 if configured["worker_id"] == "base" or configured["seed"] == 42 else 3
        header = read_npy_header(matrix_path)
        expected_header = {"dtype": "<f4", "fortran_order": False, "shape": [ROWS, expected_points, 2560]}
        if header != expected_header:
            raise ValueError(f"EXP-070 matrix header drift: {configured['worker_id']}")
        if worker.get("output", {}).get("sha256") != configured["artifact"]["sha256"]:
            raise ValueError("EXP-070 matrix-to-manifest binding drift")
        observed_workers.append(
            {"worker_id": configured["worker_id"], "output": worker["output"], "header": header}
        )
    return {
        "completion": source["recovery_completion"],
        "verification": source["recovery_verification"],
        "snapshot_claim": source["recovery_snapshot_claim"],
        "extraction_manifest": source["private_extraction_manifest"],
        "row_contract": source["private_row_contract"],
        "fold_manifest_public": source["label_source"]["public_fold_manifest"],
        "fold_manifest_private": source["label_source"]["private_fold_manifest"],
        "source_snapshot_sha256": SOURCE_SNAPSHOT_SHA256,
        "workers": observed_workers,
    }


def _root(config: Mapping[str, Any], *, private: bool) -> Path:
    outputs = config["outputs"]
    kind = _config_kind(config)
    key = (
        "preflight_private_root" if private else "preflight_public_root"
    ) if kind == "static" else (
        "formal_private_root" if private else "formal_public_root"
    )
    return resolve_project(str(outputs[key]), must_exist=False)


def _directory_bytes(root: Path) -> int:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Unsafe private-budget root")
    total = 0
    for item in root.rglob("*"):
        if item.is_symlink():
            raise PermissionError("Symlink during private-budget audit")
        if item.is_file():
            total += item.stat().st_size
        elif not item.is_dir():
            raise PermissionError("Special entry during private-budget audit")
    return total


def require_private_ignore() -> None:
    path = MODULE_DIR / ".gitignore"
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1 or file_mode(path) != "0644":
        raise PermissionError("EXP-070 privacy ignore file drift")
    rules = {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
    if "private/" not in rules:
        raise PermissionError("EXP-070 private output is not ignored")


def _public_sensitive(value: Any) -> bool:
    forbidden_keys = {
        "labels", "probabilities", "predictions", "sample_ids", "component_ids",
        "fold_ids", "row_identity", "permutation_sha256",
    }
    if isinstance(value, Mapping):
        if set(value) & forbidden_keys:
            return True
        return any(_public_sensitive(item) for item in value.values())
    if isinstance(value, list):
        if len(value) >= 672:
            return True
        return any(_public_sensitive(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return any(
            marker in lowered
            for marker in ("/users/", "phase-b-representation/private/", "sample-", "component-")
        )
    return False


def _validate_static_payloads(
    config_path: Path,
    config: Mapping[str, Any],
    sources: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    environment: Mapping[str, Any],
    *,
    require_formal_roots_absent: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    pub = _root(config, private=False)
    priv = _root(config, private=True)
    observed_public = require_safe_root(pub, private=False)
    if observed_public not in (
        {"static.json"},
        {"static.json", "static-verification.json"},
        {"static.json", "static-verification.json", "no-result-complete.json"},
    ):
        raise ValueError("EXP-070 static public prefix drift")
    require_file_modes(pub, sorted(observed_public), private=False)
    if require_safe_root(priv, private=True) != {"input-contract-manifest.json"}:
        raise ValueError("EXP-070 static private inventory drift")
    require_file_modes(pub, ["static.json"], private=False)
    require_file_modes(priv, ["input-contract-manifest.json"], private=True)
    if any(item.is_dir() for item in pub.rglob("*")) or any(item.is_dir() for item in priv.rglob("*")):
        raise ValueError("EXP-070 static nested-directory drift")
    run_path = pub / "static.json"
    input_path = priv / "input-contract-manifest.json"
    run = require_canonical_json(run_path)
    private = require_canonical_json(input_path)
    expected_access = {
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
    if set(private) != {
        "schema_version", "experiment_id", "run_id", "attempt_id", "config",
        "method_sha256", "sources", "source_identity_snapshot", "environment",
        "access", "status",
    }:
        raise ValueError("EXP-070 static input schema drift")
    if (
        private.get("schema_version") != "exp-070-probe-static-input-v1"
        or private.get("experiment_id") != EXPERIMENT_ID
        or private.get("run_id") != config["run_id"]
        or private.get("attempt_id") != config["attempt_id"]
        or private.get("config") != artifact(config_path)
        or private.get("method_sha256") != EXPECTED_METHOD_SHA256
        or private.get("sources") != sources
        or private.get("source_identity_snapshot") != snapshot
        or private.get("environment") != environment
        or private.get("access") != expected_access
        or private.get("status") != "Sealed"
    ):
        raise ValueError("EXP-070 static input binding drift")
    if set(run) != {
        "schema_version", "experiment_id", "run_id", "attempt_id", "stage", "status",
        "config", "input_manifest", "counts", "method_sha256", "source_snapshot_sha256",
        "resources", "access", "claim_boundary",
    }:
        raise ValueError("EXP-070 static run schema drift")
    if (
        run.get("schema_version") != "exp-070-probe-static-run-v1"
        or run.get("experiment_id") != EXPERIMENT_ID
        or run.get("run_id") != config["run_id"]
        or run.get("attempt_id") != config["attempt_id"]
        or run.get("stage") != "static"
        or run.get("status") != "CompletedAwaitingVerification"
        or run.get("config") != artifact(config_path)
        or run.get("input_manifest") != artifact(input_path, logical_name="input-contract-manifest.json")
        or run.get("counts") != {
            "rows": ROWS, "workers": 16, "matrices": 16,
            "main_conditions": 24, "shuffle_conditions_per_fold": 24,
        }
        or run.get("method_sha256") != EXPECTED_METHOD_SHA256
        or run.get("source_snapshot_sha256") != SOURCE_SNAPSHOT_SHA256
        or run.get("access") != expected_access
        or run.get("claim_boundary") != config["claim_boundary"]
    ):
        raise ValueError("EXP-070 static run binding drift")
    resources = run.get("resources")
    if not isinstance(resources, Mapping) or set(resources) != {
        "elapsed_seconds", "peak_rss_bytes", "free_disk_bytes"
    }:
        raise ValueError("EXP-070 static resource schema drift")
    if (
        not 0.0 <= float(resources["elapsed_seconds"]) <= 43200.0
        or not 0 < int(resources["peak_rss_bytes"]) <= 8589934592
        or int(resources["free_disk_bytes"]) < 536870912
    ):
        raise ValueError("EXP-070 static resource gate drift")
    if _public_sensitive(run):
        raise ValueError("EXP-070 static public privacy drift")
    if require_formal_roots_absent:
        for key in ("formal_public_root", "formal_private_root"):
            candidate = resolve_project(str(config["outputs"][key]), must_exist=False)
            if os.path.lexists(candidate):
                raise FileExistsError("EXP-070 formal root exists during static verification")
    return run, private, run_path, input_path


def _static_verification(
    config_path: Path,
    config: Mapping[str, Any],
    run_path: Path,
    input_path: Path,
    snapshot: Mapping[str, Any],
    synthetic_tests: Mapping[str, Any],
) -> dict[str, Any]:
    value = {
        "schema_version": "exp-070-probe-static-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "stage": "static",
        "status": "Passed",
        "passed_count": len(STATIC_CHECKS),
        "failed_count": 0,
        "checks": STATIC_CHECKS,
        "config": artifact(config_path),
        "run": artifact(run_path),
        "input_manifest": artifact(input_path, logical_name="input-contract-manifest.json"),
        "method_sha256": EXPECTED_METHOD_SHA256,
        "source_snapshot_sha256": SOURCE_SNAPSHOT_SHA256,
        "source_identity_snapshot_sha256": snapshot["sha256"],
        "synthetic_tests": dict(synthetic_tests),
        "formal_probe_authorized": True,
        "runner_imported": False,
        "model_libraries_imported": False,
        "access": {
            "npy_headers_read": True,
            "npy_array_values_read": False,
            "fold_manifest_values_read": False,
            "labels_read": False,
            "probe_fitted": False,
            "metrics_computed": False,
            "validation_accessed": False,
            "test_accessed": False,
        },
        "claim_boundary": config["claim_boundary"],
    }
    if _public_sensitive(value):
        raise ValueError("EXP-070 static verification public privacy drift")
    return value


def _static_completion(
    config: Mapping[str, Any],
    run_path: Path,
    input_path: Path,
    verification_path: Path,
    synthetic_tests: Mapping[str, Any],
) -> dict[str, Any]:
    value = {
        "schema_version": "exp-070-probe-static-complete-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "status": "Complete",
        "formal_probe_authorized": True,
        "formal_probe_executed": False,
        "performance_metrics_computed": False,
        "exp070_complete": False,
        "exp071_authorized": False,
        "run": artifact(run_path),
        "verification": artifact(verification_path),
        "input_manifest": artifact(input_path, logical_name="input-contract-manifest.json"),
        "method_sha256": EXPECTED_METHOD_SHA256,
        "source_snapshot_sha256": SOURCE_SNAPSHOT_SHA256,
        "synthetic_tests": dict(synthetic_tests),
        "claim_boundary": config["claim_boundary"],
        "next_gate": "EXP-070 formal probe initialize",
    }
    if _public_sensitive(value):
        raise ValueError("EXP-070 static completion public privacy drift")
    return value


def verify_static(config_path: Path, *, complete: bool) -> dict[str, Any]:
    config = load_config(config_path, kind="static")
    paths = require_implementation(config)
    require_import_boundaries(paths, static=True)
    synthetic_tests = run_synthetic_tests(config, paths["tests"])
    require_import_boundaries(paths, static=True)
    environment = require_environment(config)
    require_private_ignore()
    if shutil.disk_usage(PROJECT_ROOT).free < 536870912:
        raise OSError("EXP-070 static free-disk gate failed")
    before = source_identity_snapshot(config)
    sources = require_frozen_sources(config)
    after_sources = source_identity_snapshot(config)
    if before != after_sources:
        raise ValueError("EXP-070 source changed during static source checks")
    run, _private, run_path, input_path = _validate_static_payloads(
        config_path, config, sources, before, environment
    )
    del run
    public = _root(config, private=False)
    verification_path = public / "static-verification.json"
    completion_path = public / "no-result-complete.json"
    expected_verification = _static_verification(
        config_path, config, run_path, input_path, before, synthetic_tests
    )
    if os.path.lexists(verification_path):
        observed = require_canonical_json(verification_path)
        if observed != expected_verification or observed.get("status") != "Passed":
            raise RuntimeError("Only an exact Passed static verification prefix can resume")
    elif complete:
        raise RuntimeError("Static completion requires an existing Passed verification")
    else:
        if require_safe_root(public, private=False) != {"static.json"}:
            raise ValueError("EXP-070 static preverification inventory drift")
        create_json_once(verification_path, expected_verification)
    if require_safe_root(public, private=False) not in (
        {"static.json", "static-verification.json"},
        {"static.json", "static-verification.json", "no-result-complete.json"},
    ):
        raise ValueError("EXP-070 static Passed-prefix inventory drift")
    if complete:
        expected_completion = _static_completion(
            config, run_path, input_path, verification_path, synthetic_tests
        )
        if os.path.lexists(completion_path):
            if require_canonical_json(completion_path) != expected_completion:
                raise ValueError("EXP-070 static completion drift")
        else:
            create_json_once(completion_path, expected_completion)
        if require_safe_root(public, private=False) != set(
            config["outputs"]["preflight_public_success_allowlist"]
        ):
            raise ValueError("EXP-070 static terminal inventory drift")
        require_file_modes(
            public, config["outputs"]["preflight_public_success_allowlist"], private=False
        )
    elif os.path.lexists(completion_path):
        raise RuntimeError("Static verify cannot create or consume completion")
    elif require_safe_root(public, private=False) != {
        "static.json", "static-verification.json"
    }:
        raise ValueError("EXP-070 static verified inventory drift")
    final_source = source_identity_snapshot(config)
    if final_source != before or recovery_snapshot_digest() != SOURCE_SNAPSHOT_SHA256:
        raise ValueError("EXP-070 source changed during static verification")
    return expected_verification


def _public_fold_rows(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    source = config["source"]["label_source"]
    path = require_record(source["public_fold_manifest"])
    expected_keys = {
        "schema_version", "protocol_id", "experiment_id", "sample_id", "component_id", "fold_id"
    }
    rows: list[dict[str, Any]] = []
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
                raise ValueError(f"EXP-070 public fold row drift: {ordinal}")
            rows.append(value)
    if len(rows) != ROWS:
        raise ValueError("EXP-070 public fold row-count drift")
    if [sum(row["fold_id"] == fold for row in rows) for fold in FOLDS] != [672] * 5:
        raise ValueError("EXP-070 public fold-size drift")
    if len({row["sample_id"] for row in rows}) != ROWS:
        raise ValueError("EXP-070 duplicate sample identity")
    component_owner: dict[str, int] = {}
    for row in rows:
        owner = component_owner.setdefault(row["component_id"], row["fold_id"])
        if owner != row["fold_id"]:
            raise ValueError("EXP-070 component leakage")
    if len(component_owner) != 3277:
        raise ValueError("EXP-070 component-count drift")
    return rows


def _private_label(value: Any, public: Mapping[str, Any], ordinal: int) -> list[int]:
    expected_keys = {
        "schema_version", "protocol_id", "experiment_id", "sample_id", "component_id", "fold_id",
        "labels", "neutral", "label_cardinality",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise ValueError(f"EXP-070 private label row schema drift: {ordinal}")
    for key in ("schema_version", "protocol_id", "experiment_id", "sample_id", "component_id", "fold_id"):
        if value.get(key) != public.get(key):
            raise ValueError(f"EXP-070 public/private label alignment drift: {ordinal}")
    labels = value.get("labels")
    if (
        not isinstance(labels, list)
        or len(labels) != 6
        or any(type(item) not in (int, bool) or int(item) not in (0, 1) for item in labels)
    ):
        raise ValueError(f"EXP-070 label schema drift: {ordinal}")
    normalized = [int(item) for item in labels]
    cardinality = sum(normalized)
    if value.get("label_cardinality") != cardinality or value.get("neutral") is not (cardinality == 0):
        raise ValueError(f"EXP-070 derived label field drift: {ordinal}")
    return normalized


def load_labels(config: Mapping[str, Any], public_rows: Sequence[Mapping[str, Any]]) -> Any:
    import numpy as np

    path = require_record(config["source"]["label_source"]["private_fold_manifest"])
    labels: list[list[int]] = []
    with path.open("rb") as handle:
        for ordinal, line in enumerate(handle):
            if ordinal >= ROWS:
                raise ValueError("EXP-070 private label source has extra rows")
            labels.append(_private_label(strict_json_bytes(line), public_rows[ordinal], ordinal))
    if len(labels) != ROWS:
        raise ValueError("EXP-070 private label row-count drift")
    result = np.asarray(labels, dtype=np.uint8)
    if result.shape != (ROWS, 6):
        raise ValueError("EXP-070 label matrix shape drift")
    return result


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


def _binary_f1_columns(labels: Any, predicted: Any) -> Any:
    import numpy as np

    truth = np.asarray(labels, dtype=np.uint8)
    guess = np.asarray(predicted, dtype=np.uint8)
    if truth.shape != guess.shape or truth.ndim != 2 or truth.shape[1] != 6:
        raise ValueError("EXP-070 F1 input drift")
    values = np.zeros(6, dtype=np.float64)
    for column in range(6):
        tp = int(np.sum((truth[:, column] == 1) & (guess[:, column] == 1)))
        fp = int(np.sum((truth[:, column] == 0) & (guess[:, column] == 1)))
        fn = int(np.sum((truth[:, column] == 1) & (guess[:, column] == 0)))
        denominator = 2 * tp + fp + fn
        values[column] = 0.0 if denominator == 0 else (2.0 * tp) / denominator
    return values


def threshold_objectives(labels: Any, probabilities: Any, threshold_index: int) -> tuple[float, float]:
    import numpy as np

    truth = np.asarray(labels, dtype=np.uint8)
    values = np.asarray(probabilities, dtype=np.float64)
    if truth.shape != values.shape or truth.ndim != 2 or truth.shape[1] != 6:
        raise ValueError("EXP-070 threshold input drift")
    if threshold_index not in THRESHOLD_INDICES or not np.all(np.isfinite(values)):
        raise ValueError("EXP-070 threshold value drift")
    prediction = (values >= threshold_index / 100.0).astype(np.uint8)
    f1 = _binary_f1_columns(truth, prediction)
    return float(np.mean(f1[list(PRIMARY_COLUMNS)])), float(np.mean(truth != prediction))


def select_threshold_index(labels: Any, probabilities: Any) -> int:
    scores = [
        (index, *threshold_objectives(labels, probabilities, index))
        for index in THRESHOLD_INDICES
    ]
    best_f1 = max(item[1] for item in scores)
    candidates = [item for item in scores if best_f1 - item[1] <= COMPARISON_TOLERANCE]
    best_hamming = min(item[2] for item in candidates)
    candidates = [item for item in candidates if item[2] - best_hamming <= COMPARISON_TOLERANCE]
    distance = min(abs(item[0] - 50) for item in candidates)
    candidates = [item for item in candidates if abs(item[0] - 50) == distance]
    return min(item[0] for item in candidates)


def shuffle_permutation(outer_fold: int, shuffle_seed: int) -> Any:
    import numpy as np

    if outer_fold not in FOLDS or shuffle_seed not in SHUFFLE_SEEDS:
        raise ValueError("EXP-070 shuffle request drift")
    rng = np.random.Generator(
        np.random.PCG64(np.random.SeedSequence([shuffle_seed, outer_fold]))
    )
    result = np.asarray(rng.permutation(2688), dtype=np.int64)
    if not np.array_equal(np.sort(result), np.arange(2688)):
        raise ValueError("EXP-070 shuffle permutation drift")
    return result


def _npz_record(path: Path) -> dict[str, Any]:
    return artifact(path, logical_name=f"folds/{path.name}")


def _expected_npz_members() -> set[str]:
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


def _validate_npz_container(path: Path) -> None:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1 or file_mode(path) != "0600":
        raise ValueError(f"Unsafe EXP-070 fold NPZ: {path}")
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        if len(infos) != 8 or len({item.filename for item in infos}) != 8:
            raise ValueError("EXP-070 NPZ member-count drift")
        names: set[str] = set()
        for info in infos:
            if (
                info.is_dir()
                or info.flag_bits & 1
                or info.compress_type != zipfile.ZIP_STORED
                or not info.filename.endswith(".npy")
                or "/" in info.filename
                or "\\" in info.filename
            ):
                raise ValueError("EXP-070 unsafe or compressed NPZ member")
            names.add(info.filename[:-4])
        if names != _expected_npz_members():
            raise ValueError("EXP-070 NPZ member inventory drift")


def _load_fold(
    config: Mapping[str, Any],
    outer_fold: int,
    fold_ids: Any | None,
    labels: Any | None,
    source_snapshot: Mapping[str, Any],
    *,
    structural_only: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    import numpy as np

    root = _root(config, private=True) / "folds"
    npz_path = root / f"f{outer_fold}.npz"
    seal_path = root / f"f{outer_fold}.json"
    if file_mode(seal_path) != "0600" or seal_path.stat().st_nlink != 1 or seal_path.is_symlink():
        raise ValueError("EXP-070 fold seal mode/link drift")
    seal = require_canonical_json(seal_path)
    expected_seal_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "outer_fold", "status",
        "npz", "main_condition_order", "shuffle_condition_order", "inner_fold_order",
        "source_before", "source_after", "permutation_sha256", "fit_counts",
        "convergence", "resources", "access",
    }
    if set(seal) != expected_seal_keys:
        raise ValueError(f"EXP-070 fold seal schema drift: {outer_fold}")
    expected_access = {
        "fold_manifest_container_bytes_read": True,
        "outer_train_label_values_read": True,
        "outer_heldout_label_values_decoded": False,
        "representation_values_read": True,
        "model_loaded": False,
        "forward_executed": False,
        "validation_accessed": False,
        "test_accessed": False,
    }
    expected_counts = {
        "main_binary_fits": MAIN_FITS_PER_FOLD,
        "shuffle_binary_fits": SHUFFLE_FITS_PER_FOLD,
        "total_binary_fits": MAIN_FITS_PER_FOLD + SHUFFLE_FITS_PER_FOLD,
    }
    if (
        seal.get("schema_version") != "exp-070-probe-fold-seal-v1"
        or seal.get("experiment_id") != EXPERIMENT_ID
        or seal.get("run_id") != config["run_id"]
        or seal.get("attempt_id") != config["attempt_id"]
        or seal.get("outer_fold") != outer_fold
        or seal.get("status") != "Sealed"
        or seal.get("npz") != _npz_record(npz_path)
        or seal.get("main_condition_order") != list(MAIN_KEYS)
        or seal.get("shuffle_condition_order") != list(SHUFFLE_CONDITIONS)
        or seal.get("inner_fold_order") != [fold for fold in FOLDS if fold != outer_fold]
        or seal.get("source_before") != source_snapshot
        or seal.get("source_after") != source_snapshot
        or seal.get("fit_counts") != expected_counts
        or seal.get("access") != expected_access
    ):
        raise ValueError(f"EXP-070 fold seal binding drift: {outer_fold}")
    permutation_digests = {
        str(seed): _array_digest(shuffle_permutation(outer_fold, seed))
        for seed in SHUFFLE_SEEDS
    }
    if seal.get("permutation_sha256") != permutation_digests:
        raise ValueError(f"EXP-070 shuffle permutation digest drift: {outer_fold}")
    resources = seal.get("resources")
    if not isinstance(resources, Mapping) or set(resources) != {
        "elapsed_seconds", "peak_rss_bytes", "private_exp070_bytes"
    }:
        raise ValueError("EXP-070 fold resource schema drift")
    if (
        not 0.0 < float(resources["elapsed_seconds"]) <= 43200.0
        or not 0 < int(resources["peak_rss_bytes"]) <= 8589934592
        or not 0 < int(resources["private_exp070_bytes"]) <= 536870912
    ):
        raise ValueError("EXP-070 fold resource gate drift")
    _validate_npz_container(npz_path)
    with np.load(npz_path, allow_pickle=False) as bundle:
        if set(bundle.files) != _expected_npz_members():
            raise ValueError("EXP-070 fold member drift")
        arrays = {
            "outer_train_ordinals": np.ascontiguousarray(bundle["outer_train_ordinals"], dtype=np.int32),
            "outer_heldout_ordinals": np.ascontiguousarray(bundle["outer_heldout_ordinals"], dtype=np.int32),
            "main_inner_oof_probability": np.ascontiguousarray(bundle["main_inner_oof_probability"], dtype=np.float64),
            "main_outer_heldout_probability": np.ascontiguousarray(bundle["main_outer_heldout_probability"], dtype=np.float64),
            "main_threshold_index": np.ascontiguousarray(bundle["main_threshold_index"], dtype=np.int16),
            "main_n_iter": np.ascontiguousarray(bundle["main_n_iter"], dtype=np.int32),
            "shuffle_outer_heldout_probability": np.ascontiguousarray(bundle["shuffle_outer_heldout_probability"], dtype=np.float64),
            "shuffle_n_iter": np.ascontiguousarray(bundle["shuffle_n_iter"], dtype=np.int32),
        }
        expected_dtypes = {
            "outer_train_ordinals": np.dtype(np.int32),
            "outer_heldout_ordinals": np.dtype(np.int32),
            "main_inner_oof_probability": np.dtype(np.float64),
            "main_outer_heldout_probability": np.dtype(np.float64),
            "main_threshold_index": np.dtype(np.int16),
            "main_n_iter": np.dtype(np.int32),
            "shuffle_outer_heldout_probability": np.dtype(np.float64),
            "shuffle_n_iter": np.dtype(np.int32),
        }
        for name in bundle.files:
            if bundle[name].dtype != expected_dtypes[name] or not bundle[name].flags.c_contiguous:
                raise ValueError(f"EXP-070 fold dtype/layout drift: {name}")
    expected_shapes = {
        "outer_train_ordinals": (2688,),
        "outer_heldout_ordinals": (672,),
        "main_inner_oof_probability": (24, 2688, 6),
        "main_outer_heldout_probability": (24, 672, 6),
        "main_threshold_index": (24,),
        "main_n_iter": (24, 5, 6),
        "shuffle_outer_heldout_probability": (3, 8, 672, 6),
        "shuffle_n_iter": (3, 8, 6),
    }
    if any(arrays[name].shape != shape for name, shape in expected_shapes.items()):
        raise ValueError(f"EXP-070 fold shape drift: {outer_fold}")
    inner_ordinals = arrays["outer_train_ordinals"]
    outer_ordinals = arrays["outer_heldout_ordinals"]
    if (
        not np.array_equal(inner_ordinals, np.sort(inner_ordinals))
        or not np.array_equal(outer_ordinals, np.sort(outer_ordinals))
        or not np.array_equal(
            np.sort(np.concatenate((inner_ordinals, outer_ordinals))),
            np.arange(ROWS, dtype=np.int32),
        )
    ):
        raise ValueError(f"EXP-070 structural ordinal partition drift: {outer_fold}")
    probability_names = (
        "main_inner_oof_probability", "main_outer_heldout_probability",
        "shuffle_outer_heldout_probability",
    )
    for name in probability_names:
        value = arrays[name]
        if not np.all(np.isfinite(value)) or np.any(value < 0.0) or np.any(value > 1.0):
            raise ValueError(f"EXP-070 probability gate drift: {outer_fold}/{name}")
    thresholds = arrays["main_threshold_index"]
    if not np.all(np.isin(thresholds, THRESHOLD_INDICES)):
        raise ValueError("EXP-070 threshold index range drift")
    for name in ("main_n_iter", "shuffle_n_iter"):
        if np.any(arrays[name] <= 0) or np.any(arrays[name] > 2000):
            raise ValueError("EXP-070 solver iteration gate drift")
    convergence = seal.get("convergence")
    if convergence != {
        "main_n_iter_max": int(np.max(arrays["main_n_iter"])),
        "shuffle_n_iter_max": int(np.max(arrays["shuffle_n_iter"])),
        "all_within_max_iter": True,
    }:
        raise ValueError(f"EXP-070 convergence record drift: {outer_fold}")
    if structural_only:
        if fold_ids is None or labels is not None:
            raise ValueError("EXP-070 structural fold validation contract drift")
        expected_inner = np.flatnonzero(fold_ids != outer_fold).astype(np.int32)
        expected_outer = np.flatnonzero(fold_ids == outer_fold).astype(np.int32)
        if (
            not np.array_equal(inner_ordinals, expected_inner)
            or not np.array_equal(outer_ordinals, expected_outer)
        ):
            raise ValueError(f"EXP-070 structural fold membership drift: {outer_fold}")
        return seal, arrays
    if fold_ids is None or labels is None:
        raise ValueError("EXP-070 semantic fold validation lacks labels")
    expected_inner = np.flatnonzero(fold_ids != outer_fold).astype(np.int32)
    expected_outer = np.flatnonzero(fold_ids == outer_fold).astype(np.int32)
    if (
        not np.array_equal(inner_ordinals, expected_inner)
        or not np.array_equal(outer_ordinals, expected_outer)
    ):
        raise ValueError(f"EXP-070 fold ordinal drift: {outer_fold}")
    for position in range(24):
        selected = select_threshold_index(
            labels[expected_inner], arrays["main_inner_oof_probability"][position]
        )
        if selected != int(thresholds[position]):
            raise ValueError(f"EXP-070 independent threshold mismatch: {outer_fold}/{MAIN_KEYS[position]}")
    return seal, arrays


def prevalidate_fold_structures(
    config: Mapping[str, Any],
    source_snapshot: Mapping[str, Any],
    public_rows: Sequence[Mapping[str, Any]],
) -> None:
    import numpy as np

    fold_ids = np.asarray([row["fold_id"] for row in public_rows], dtype=np.int8)
    if fold_ids.shape != (ROWS,):
        raise ValueError("EXP-070 structural fold-id shape drift")
    for outer_fold in FOLDS:
        _seal, arrays = _load_fold(
            config,
            outer_fold,
            fold_ids,
            None,
            source_snapshot,
            structural_only=True,
        )
        del arrays


def build_bootstrap_plan(fold_ids: Any, component_ids: Sequence[str], labels: Any) -> tuple[list[Any], str]:
    import numpy as np

    fold_array = np.asarray(fold_ids, dtype=np.int8)
    truth = np.asarray(labels, dtype=np.uint8)
    if fold_array.shape != (ROWS,) or truth.shape != (ROWS, 6) or len(component_ids) != ROWS:
        raise ValueError("EXP-070 bootstrap input drift")
    component_rows: dict[int, list[tuple[str, Any]]] = {}
    owners: dict[str, int] = {}
    for fold in FOLDS:
        members: dict[str, list[int]] = {}
        for ordinal in np.flatnonzero(fold_array == fold).tolist():
            component = component_ids[ordinal]
            owner = owners.setdefault(component, fold)
            if owner != fold:
                raise ValueError("EXP-070 bootstrap component leakage")
            members.setdefault(component, []).append(ordinal)
        order = sorted(members, key=lambda value: value.encode("utf-8"))
        if not order:
            raise ValueError("EXP-070 bootstrap empty fold")
        component_rows[fold] = [
            (component, np.asarray(sorted(members[component]), dtype=np.int32))
            for component in order
        ]
    rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    digest = hashlib.sha256()
    plan: list[Any] = []
    for replicate in range(BOOTSTRAP_REPLICATES):
        blocks = []
        digest.update(replicate.to_bytes(4, "little", signed=False))
        for fold in FOLDS:
            universe = component_rows[fold]
            draws = np.asarray(
                rng.integers(
                    0, len(universe), size=len(universe), dtype=np.int64, endpoint=False
                ),
                dtype=np.int64,
            )
            digest.update(fold.to_bytes(1, "little", signed=False))
            digest.update(len(universe).to_bytes(4, "little", signed=False))
            digest.update(draws.tobytes(order="C"))
            blocks.extend(universe[index][1] for index in draws.tolist())
        rows = np.ascontiguousarray(np.concatenate(blocks), dtype=np.int32)
        sampled = truth[rows]
        for column in range(6):
            if not np.array_equal(
                np.unique(sampled[:, column]), np.asarray([0, 1], dtype=np.uint8)
            ):
                raise ValueError(
                    f"EXP-070 invalid bootstrap replicate {replicate}: {LABELS[column]}"
                )
        digest.update(rows.shape[0].to_bytes(4, "little", signed=False))
        digest.update(rows.tobytes(order="C"))
        plan.append(rows)
    return plan, digest.hexdigest()


def metric_bundle(labels: Any, probabilities: Any, predicted: Any) -> dict[str, Any]:
    import numpy as np
    from sklearn.metrics import accuracy_score, average_precision_score, f1_score, hamming_loss

    truth = np.asarray(labels, dtype=np.uint8)
    values = np.asarray(probabilities, dtype=np.float64)
    guess = np.asarray(predicted, dtype=np.uint8)
    if truth.shape != values.shape or truth.shape != guess.shape or truth.ndim != 2 or truth.shape[1] != 6:
        raise ValueError("EXP-070 metric shape drift")
    if not np.all(np.isfinite(values)) or np.any(values < 0.0) or np.any(values > 1.0):
        raise ValueError("EXP-070 metric probability drift")
    if not np.all(np.isin(truth, [0, 1])) or not np.all(np.isin(guess, [0, 1])):
        raise ValueError("EXP-070 metric binary input drift")
    for column in range(6):
        if not np.array_equal(np.unique(truth[:, column]), np.asarray([0, 1], dtype=np.uint8)):
            raise ValueError(f"EXP-070 metric label support drift: {LABELS[column]}")
    per_label_ap = np.asarray(
        [average_precision_score(truth[:, column], values[:, column]) for column in range(6)],
        dtype=np.float64,
    )
    per_label_f1 = _binary_f1_columns(truth, guess)
    return {
        "five_label_macro_ap": float(np.mean(per_label_ap[list(PRIMARY_COLUMNS)])),
        "six_label_macro_ap": float(np.mean(per_label_ap)),
        "six_label_macro_f1": float(np.mean(per_label_f1)),
        "five_label_macro_f1": float(np.mean(per_label_f1[list(PRIMARY_COLUMNS)])),
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
    if truth.shape != values.shape or truth.ndim != 2 or truth.shape[1] != 6:
        raise ValueError("EXP-070 AP shape drift")
    if not np.all(np.isfinite(values)) or np.any(values < 0.0) or np.any(values > 1.0):
        raise ValueError("EXP-070 AP probability drift")
    for column in range(6):
        if not np.array_equal(np.unique(truth[:, column]), np.asarray([0, 1], dtype=np.uint8)):
            raise ValueError(f"EXP-070 AP label support drift: {LABELS[column]}")
    per_label = np.asarray(
        [average_precision_score(truth[:, column], values[:, column]) for column in range(6)],
        dtype=np.float64,
    )
    return {
        "five_label_macro_ap": float(np.mean(per_label[list(PRIMARY_COLUMNS)])),
        "six_label_macro_ap": float(np.mean(per_label)),
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
            raise ValueError(f"EXP-070 non-numeric metric leaf: {name}")
    return result


def _unflatten_numeric(value: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for compound, item in value.items():
        cursor = result
        parts = compound.split(".")
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = item
    return result


def metric_delta(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    left_flat = _numeric_leaves(left)
    right_flat = _numeric_leaves(right)
    if set(left_flat) != set(right_flat):
        raise ValueError("EXP-070 metric delta schema drift")
    return _unflatten_numeric({key: left_flat[key] - right_flat[key] for key in left_flat})


def bootstrap_metric_intervals(
    labels: Any,
    left_probability: Any,
    left_prediction: Any,
    right_probability: Any,
    right_prediction: Any,
    plan: Sequence[Any],
) -> dict[str, Any]:
    import numpy as np

    samples: dict[str, list[float]] = {}
    for rows in plan:
        delta = metric_delta(
            metric_bundle(labels[rows], left_probability[rows], left_prediction[rows]),
            metric_bundle(labels[rows], right_probability[rows], right_prediction[rows]),
        )
        for key, value in _numeric_leaves(delta).items():
            samples.setdefault(key, []).append(value)
    return _unflatten_numeric(
        {
            key: [
                float(np.percentile(values, 2.5, method="linear")),
                float(np.percentile(values, 97.5, method="linear")),
            ]
            for key, values in samples.items()
        }
    )


def bootstrap_ap5_interval(
    labels: Any,
    left_probability: Any,
    right_probability: Any,
    plan: Sequence[Any],
) -> list[float]:
    import numpy as np

    values = [
        ap_bundle(labels[rows], left_probability[rows])["five_label_macro_ap"]
        - ap_bundle(labels[rows], right_probability[rows])["five_label_macro_ap"]
        for rows in plan
    ]
    return [
        float(np.percentile(values, 2.5, method="linear")),
        float(np.percentile(values, 97.5, method="linear")),
    ]


def _predictions(probabilities: Any, threshold_by_row: Any) -> Any:
    import numpy as np

    values = np.asarray(probabilities, dtype=np.float64)
    thresholds = np.asarray(threshold_by_row, dtype=np.int16)
    if values.shape != (ROWS, 6) or thresholds.shape != (ROWS,):
        raise ValueError("EXP-070 assembled prediction shape drift")
    return (values >= thresholds[:, None] / 100.0).astype(np.uint8)


def _seed_vote(contrasts: Mapping[str, Any], seed: int) -> tuple[bool, dict[str, Any]]:
    detail: dict[str, Any] = {}
    for point in VOTING_POINTS:
        result = contrasts[f"m3-s{seed}:{point}"]
        delta = float(result["delta"]["five_label_macro_ap"])
        interval = result["bootstrap_delta_intervals"]["five_label_macro_ap"]
        passed = delta > 0.0 and float(interval[0]) > 0.0
        detail[point] = {"delta": delta, "interval": interval, "passed": passed}
    return all(detail[point]["passed"] for point in VOTING_POINTS), detail


def _control_vote(
    contrasts: Mapping[str, Any], shuffle_seed: int, seed: int
) -> tuple[bool, dict[str, Any]]:
    detail: dict[str, Any] = {}
    for point in VOTING_POINTS:
        result = contrasts[f"shuffle-{shuffle_seed}|m3-s{seed}:{point}"]
        delta = float(result["delta_five_label_macro_ap"])
        interval = result["bootstrap_delta_interval"]
        passed = delta > 0.0 and float(interval[0]) > 0.0
        detail[point] = {"delta": delta, "interval": interval, "passed": passed}
    return all(detail[point]["passed"] for point in VOTING_POINTS), detail


def recompute_results(
    config: Mapping[str, Any],
    labels: Any,
    public_rows: Sequence[Mapping[str, Any]],
    source_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    import numpy as np

    fold_ids = np.asarray([row["fold_id"] for row in public_rows], dtype=np.int8)
    component_ids = [str(row["component_id"]) for row in public_rows]
    main_probability = {key: np.empty((ROWS, 6), dtype=np.float64) for key in MAIN_KEYS}
    main_threshold_rows = {key: np.empty(ROWS, dtype=np.int16) for key in MAIN_KEYS}
    thresholds_by_fold = {key: [None] * 5 for key in MAIN_KEYS}
    control_probability = {key: np.empty((ROWS, 6), dtype=np.float64) for key in SHUFFLE_KEYS}
    seals: list[dict[str, Any]] = []
    bundle_records: list[dict[str, Any]] = []

    for outer_fold in FOLDS:
        seal, arrays = _load_fold(config, outer_fold, fold_ids, labels, source_snapshot)
        seals.append(seal)
        npz_path = _root(config, private=True) / "folds" / f"f{outer_fold}.npz"
        bundle_records.append(_npz_record(npz_path))
        outer_ordinals = arrays["outer_heldout_ordinals"]
        outer_probability = arrays["main_outer_heldout_probability"]
        threshold_indices = arrays["main_threshold_index"]
        for position, key in enumerate(MAIN_KEYS):
            main_probability[key][outer_ordinals] = outer_probability[position]
            main_threshold_rows[key][outer_ordinals] = threshold_indices[position]
            thresholds_by_fold[key][outer_fold] = int(threshold_indices[position])
        flattened_shuffle = arrays["shuffle_outer_heldout_probability"].reshape(24, 672, 6)
        for position, key in enumerate(SHUFFLE_KEYS):
            control_probability[key][outer_ordinals] = flattened_shuffle[position]

    if any(value is None for values in thresholds_by_fold.values() for value in values):
        raise ValueError("EXP-070 threshold coverage drift")
    for collection in (main_probability, control_probability):
        for key, value in collection.items():
            if not np.all(np.isfinite(value)) or np.any(value < 0.0) or np.any(value > 1.0):
                raise ValueError(f"EXP-070 OOF probability coverage drift: {key}")

    main_prediction = {
        key: _predictions(main_probability[key], main_threshold_rows[key])
        for key in MAIN_KEYS
    }
    main_metrics = {
        key: metric_bundle(labels, main_probability[key], main_prediction[key])
        for key in MAIN_KEYS
    }
    bootstrap_plan, bootstrap_digest = build_bootstrap_plan(fold_ids, component_ids, labels)
    main_contrasts: dict[str, Any] = {}
    for key in MAIN_KEYS:
        if key.startswith("frozen:"):
            continue
        point = key.split(":", 1)[1]
        baseline = f"frozen:{point}"
        main_contrasts[key] = {
            "baseline": baseline,
            "delta": metric_delta(main_metrics[key], main_metrics[baseline]),
            "bootstrap_delta_intervals": bootstrap_metric_intervals(
                labels,
                main_probability[key],
                main_prediction[key],
                main_probability[baseline],
                main_prediction[baseline],
                bootstrap_plan,
            ),
        }

    seed_votes: dict[str, Any] = {}
    passed_seeds = 0
    for seed in (43, 44):
        passed, detail = _seed_vote(main_contrasts, seed)
        seed_votes[str(seed)] = {"passed": passed, "points": detail}
        passed_seeds += int(passed)

    control_metrics = {
        key: ap_bundle(labels, control_probability[key]) for key in SHUFFLE_KEYS
    }
    control_contrasts: dict[str, Any] = {}
    for key in SHUFFLE_KEYS:
        shuffle_name, condition = key.split("|", 1)
        model, point = condition.split(":", 1)
        if model == "frozen":
            continue
        baseline = f"{shuffle_name}|frozen:{point}"
        control_contrasts[key] = {
            "baseline": baseline,
            "delta_five_label_macro_ap": float(
                control_metrics[key]["five_label_macro_ap"]
                - control_metrics[baseline]["five_label_macro_ap"]
            ),
            "bootstrap_delta_interval": bootstrap_ap5_interval(
                labels,
                control_probability[key],
                control_probability[baseline],
                bootstrap_plan,
            ),
        }

    control_votes: dict[str, Any] = {}
    negative_control_failure = False
    for shuffle_seed in SHUFFLE_SEEDS:
        prospective: dict[str, Any] = {}
        both_pass = True
        for seed in (43, 44):
            passed, detail = _control_vote(control_contrasts, shuffle_seed, seed)
            prospective[str(seed)] = {"passed": passed, "points": detail}
            both_pass = both_pass and passed
        control_votes[str(shuffle_seed)] = {
            "prospective_seeds": prospective,
            "both_prospective_seeds_pass": both_pass,
        }
        negative_control_failure = negative_control_failure or both_pass

    representation_state = None if negative_control_failure else passed_seeds
    representation_state_label = (
        None
        if representation_state is None
        else config["method"]["seed_roles"]["states"][str(representation_state)]
    )
    total_main = sum(int(seal["fit_counts"]["main_binary_fits"]) for seal in seals)
    total_shuffle = sum(int(seal["fit_counts"]["shuffle_binary_fits"]) for seal in seals)
    if total_main != TOTAL_MAIN_FITS or total_shuffle != TOTAL_SHUFFLE_FITS:
        raise ValueError("EXP-070 terminal fit inventory drift")
    results = {
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
    return {
        "results": results,
        "seals": seals,
        "bundle_records": bundle_records,
        "bootstrap_plan_sha256": bootstrap_digest,
        "row_identity": {
            "ordinal_sha256": _array_digest(np.arange(ROWS, dtype=np.int32)),
            "fold_id_sha256": _array_digest(fold_ids),
            "component_id_order_sha256": _string_sequence_digest(component_ids),
            "labels_sha256": _array_digest(labels),
        },
        "fit_counts": {"main": total_main, "shuffle": total_shuffle, "total": total_main + total_shuffle},
    }


def require_static_completion(config: Mapping[str, Any]) -> Path:
    parent = config.get("preflight")
    if not isinstance(parent, Mapping):
        raise ValueError("EXP-070 formal config lacks static binding")
    expected_parent_keys = {
        "config", "static_run", "static_verification", "no_result_completion",
        "required_statuses", "formal_probe_authorized_by_preflight",
    }
    if set(parent) != expected_parent_keys or parent.get("formal_probe_authorized_by_preflight") is not True:
        raise ValueError("EXP-070 formal static binding drift")
    for key in ("config", "static_run", "static_verification", "no_result_completion"):
        value = parent.get(key)
        if not isinstance(value, Mapping) or value.get("sha256") == "TBD" or value.get("bytes") == 0:
            raise ValueError("EXP-070 static parent identity is not frozen")
        require_record(value)
    static_config_path = require_record(parent["config"])
    static_config = strict_json(static_config_path)
    validate_config(static_config, kind="static")
    static_paths = require_implementation(static_config)
    require_import_boundaries(static_paths, static=True)
    if static_config.get("method") != config.get("method"):
        raise ValueError("EXP-070 static/formal method drift")
    environment = require_environment(static_config)
    snapshot = source_identity_snapshot(static_config)
    sources = require_frozen_sources(static_config)
    if source_identity_snapshot(static_config) != snapshot:
        raise ValueError("EXP-070 source changed during static-parent replay")
    run, _input, run_path, input_path = _validate_static_payloads(
        static_config_path,
        static_config,
        sources,
        snapshot,
        environment,
        require_formal_roots_absent=False,
    )
    del run
    synthetic_tests = _synthetic_test_summary(static_config, static_paths["tests"])
    expected_verification = _static_verification(
        static_config_path,
        static_config,
        run_path,
        input_path,
        snapshot,
        synthetic_tests,
    )
    verification_path = require_record(parent["static_verification"])
    verification = require_canonical_json(verification_path)
    completion_path = require_record(parent["no_result_completion"])
    completion = require_canonical_json(completion_path)
    if parent.get("required_statuses") != {
        "static_run": "CompletedAwaitingVerification",
        "static_verification": "Passed",
        "no_result_completion": "Complete",
    }:
        raise ValueError("EXP-070 static status contract drift")
    expected_completion = _static_completion(
        static_config,
        run_path,
        input_path,
        verification_path,
        synthetic_tests,
    )
    if verification != expected_verification or completion != expected_completion:
        raise ValueError("EXP-070 static parent exact payload drift")
    if (
        parent["static_run"] != artifact(run_path)
        or parent["static_verification"] != artifact(verification_path)
        or parent["no_result_completion"] != artifact(completion_path)
        or synthetic_tests.get("status") != "Passed"
        or synthetic_tests.get("tests_run") != 34
        or synthetic_tests.get("test_artifact") != static_config["implementation"]["tests"]
    ):
        raise ValueError("EXP-070 static parent artifact chain drift")
    return completion_path


def _validate_formal_roots(config: Mapping[str, Any]) -> tuple[Path, Path, set[str]]:
    public = _root(config, private=False)
    private = _root(config, private=True)
    public_files = require_safe_root(public, private=False)
    allowed_public = (
        set(config["outputs"]["formal_public_awaiting_verification_allowlist"]),
        set(config["outputs"]["formal_public_verified_allowlist"]),
        set(config["outputs"]["formal_public_success_allowlist"]),
    )
    if public_files not in allowed_public:
        raise ValueError("EXP-070 formal public prefix drift")
    if "failure.json" in public_files:
        raise RuntimeError("EXP-070 runner failure blocks verification")
    require_file_modes(public, sorted(public_files), private=False)
    private_files = require_safe_root(private, private=True)
    expected_private = set(config["outputs"]["formal_private_success_allowlist"])
    if private_files != expected_private:
        raise ValueError("EXP-070 formal private inventory drift")
    require_file_modes(private, sorted(private_files), private=True)
    directories = {
        item.relative_to(private).as_posix() for item in private.rglob("*") if item.is_dir()
    }
    if directories != {"folds"} or file_mode(private / "folds") != "0700":
        raise ValueError("EXP-070 formal private directory drift")
    if any(item.is_dir() for item in public.rglob("*")):
        raise ValueError("EXP-070 public nested directory drift")
    return public, private, public_files


def _validate_claim_and_input(
    config_path: Path,
    config: Mapping[str, Any],
    static_completion: Path,
    sources: Mapping[str, Any],
    source_snapshot: Mapping[str, Any],
    environment: Mapping[str, Any],
    public: Path,
    private: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    claim_path = public / "run-claim.json"
    input_path = private / "input-manifest.json"
    claim = require_canonical_json(claim_path)
    input_manifest = require_canonical_json(input_path)
    if set(claim) != {
        "schema_version", "experiment_id", "run_id", "attempt_id", "stage", "status",
        "config", "static_completion", "source_snapshot_sha256", "lifecycle", "claim_boundary",
    }:
        raise ValueError("EXP-070 run claim schema drift")
    if (
        claim.get("schema_version") != "exp-070-formal-probe-claim-v1"
        or claim.get("experiment_id") != EXPERIMENT_ID
        or claim.get("run_id") != config["run_id"]
        or claim.get("attempt_id") != config["attempt_id"]
        or claim.get("stage") != "formal-probe"
        or claim.get("status") != "Initialized"
        or claim.get("config") != artifact(config_path)
        or claim.get("static_completion") != artifact(static_completion)
        or claim.get("source_snapshot_sha256") != SOURCE_SNAPSHOT_SHA256
        or claim.get("lifecycle") != [
            "initialize", "fit-fold-0", "fit-fold-1", "fit-fold-2", "fit-fold-3", "fit-fold-4", "assemble"
        ]
        or claim.get("claim_boundary") != config["claim_boundary"]
    ):
        raise ValueError("EXP-070 run claim binding drift")
    expected_access = {
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
    }
    if set(input_manifest) != {
        "schema_version", "experiment_id", "run_id", "attempt_id", "config",
        "static_completion", "method_sha256", "sources", "source_identity_snapshot",
        "environment", "resources", "access", "status",
    }:
        raise ValueError("EXP-070 formal input schema drift")
    if (
        input_manifest.get("schema_version") != "exp-070-formal-probe-input-v1"
        or input_manifest.get("experiment_id") != EXPERIMENT_ID
        or input_manifest.get("run_id") != config["run_id"]
        or input_manifest.get("attempt_id") != config["attempt_id"]
        or input_manifest.get("config") != artifact(config_path)
        or input_manifest.get("static_completion") != artifact(static_completion)
        or input_manifest.get("method_sha256") != EXPECTED_METHOD_SHA256
        or input_manifest.get("sources") != sources
        or input_manifest.get("source_identity_snapshot") != source_snapshot
        or input_manifest.get("environment") != environment
        or input_manifest.get("access") != expected_access
        or input_manifest.get("status") != "Initialized"
    ):
        raise ValueError("EXP-070 formal input binding drift")
    resources = input_manifest.get("resources")
    if not isinstance(resources, Mapping) or set(resources) != {
        "elapsed_seconds", "peak_rss_bytes", "free_disk_bytes"
    }:
        raise ValueError("EXP-070 formal input resource schema drift")
    if (
        not 0.0 <= float(resources["elapsed_seconds"]) <= 43200.0
        or not 0 < int(resources["peak_rss_bytes"]) <= 8589934592
        or int(resources["free_disk_bytes"]) < 536870912
    ):
        raise ValueError("EXP-070 formal input resource drift")
    return claim, input_manifest


def _validate_manifests_and_report(
    config_path: Path,
    config: Mapping[str, Any],
    public: Path,
    private: Path,
    source_snapshot: Mapping[str, Any],
    recomputed: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = private / "probe-manifest.json"
    report_path = public / "probe.json"
    manifest = require_canonical_json(manifest_path)
    report = require_canonical_json(report_path)
    expected_access = {
        "outer_train_label_values_read": True,
        "outer_heldout_label_values_read_after_all_fold_seals": True,
        "representation_values_read_by_assemble": False,
        "sealed_probability_values_read": True,
        "model_loaded": False,
        "forward_executed": False,
        "validation_accessed": False,
        "test_accessed": False,
    }
    if set(manifest) != {
        "schema_version", "experiment_id", "run_id", "attempt_id", "status", "config",
        "source_identity_snapshot", "fold_bundles", "row_identity", "bootstrap",
        "fit_counts", "results", "resources", "access", "claim_boundary",
    }:
        raise ValueError("EXP-070 probe manifest schema drift")
    if (
        manifest.get("schema_version") != "exp-070-probe-manifest-v1"
        or manifest.get("experiment_id") != EXPERIMENT_ID
        or manifest.get("run_id") != config["run_id"]
        or manifest.get("attempt_id") != config["attempt_id"]
        or manifest.get("status") != "CompletedAwaitingVerification"
        or manifest.get("config") != artifact(config_path)
        or manifest.get("source_identity_snapshot") != source_snapshot
        or manifest.get("fold_bundles") != recomputed["bundle_records"]
        or manifest.get("row_identity") != recomputed["row_identity"]
        or manifest.get("bootstrap") != {
            "replicates": BOOTSTRAP_REPLICATES,
            "plan_sha256": recomputed["bootstrap_plan_sha256"],
            "percentile_method": "linear",
            "plan_persisted": False,
        }
        or manifest.get("fit_counts") != recomputed["fit_counts"]
        or manifest.get("results") != recomputed["results"]
        or manifest.get("access") != expected_access
        or manifest.get("claim_boundary") != config["claim_boundary"]
    ):
        raise ValueError("EXP-070 probe manifest binding drift")
    manifest_resources = manifest.get("resources")
    if not isinstance(manifest_resources, Mapping) or set(manifest_resources) != {
        "aggregate_elapsed_seconds", "maximum_peak_rss_bytes", "assemble"
    }:
        raise ValueError("EXP-070 manifest resource schema drift")
    assemble = manifest_resources.get("assemble")
    if not isinstance(assemble, Mapping) or set(assemble) != {"elapsed_seconds", "peak_rss_bytes"}:
        raise ValueError("EXP-070 assemble resource schema drift")
    expected_elapsed = sum(
        float(seal["resources"]["elapsed_seconds"]) for seal in recomputed["seals"]
    ) + float(assemble["elapsed_seconds"])
    expected_peak = max(
        [int(seal["resources"]["peak_rss_bytes"]) for seal in recomputed["seals"]]
        + [int(assemble["peak_rss_bytes"])]
    )
    if (
        float(manifest_resources["aggregate_elapsed_seconds"]) != expected_elapsed
        or int(manifest_resources["maximum_peak_rss_bytes"]) != expected_peak
        or expected_elapsed > 43200.0
        or expected_peak > 8589934592
        or not 0.0 < float(assemble["elapsed_seconds"]) <= 43200.0
        or not 0 < int(assemble["peak_rss_bytes"]) <= 8589934592
    ):
        raise ValueError("EXP-070 aggregate resource gate drift")
    if set(report) != {
        "schema_version", "experiment_id", "run_id", "attempt_id", "stage", "status",
        "config", "probe_manifest", "counts", "results", "resources", "access",
        "formal_probe_complete", "exp070_complete", "exp071_authorized", "claim_boundary",
    }:
        raise ValueError("EXP-070 probe report schema drift")
    expected_counts = {
        "rows": ROWS,
        "folds": 5,
        "main_conditions": 24,
        "shuffle_conditions_per_fold": 24,
        "main_binary_fits": TOTAL_MAIN_FITS,
        "shuffle_binary_fits": TOTAL_SHUFFLE_FITS,
        "binary_fits": TOTAL_BINARY_FITS,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
    }
    private_bytes = _directory_bytes(private)
    if private_bytes > int(config["resources"]["consumer_private_budget_bytes"]):
        raise OSError("EXP-070 consumer private budget exceeded")
    expected_report_resources = {
        "aggregate_elapsed_seconds": expected_elapsed,
        "maximum_peak_rss_bytes": expected_peak,
        "private_exp070_bytes": private_bytes,
        "api_cost_usd": 0,
    }
    if (
        report.get("schema_version") != "exp-070-probe-run-v1"
        or report.get("experiment_id") != EXPERIMENT_ID
        or report.get("run_id") != config["run_id"]
        or report.get("attempt_id") != config["attempt_id"]
        or report.get("stage") != "formal-probe"
        or report.get("status") != "CompletedAwaitingVerification"
        or report.get("config") != artifact(config_path)
        or report.get("probe_manifest") != artifact(manifest_path, logical_name="probe-manifest.json")
        or report.get("counts") != expected_counts
        or report.get("results") != recomputed["results"]
        or report.get("resources") != expected_report_resources
        or report.get("access") != expected_access
        or report.get("formal_probe_complete") is not False
        or report.get("exp070_complete") is not False
        or report.get("exp071_authorized") is not False
        or report.get("claim_boundary") != config["claim_boundary"]
    ):
        raise ValueError("EXP-070 probe report binding drift")
    if _public_sensitive(report):
        raise ValueError("EXP-070 probe public privacy drift")
    return manifest, report


def _formal_verification(
    config_path: Path,
    config: Mapping[str, Any],
    public: Path,
    private: Path,
    static_completion: Path,
    source_snapshot: Mapping[str, Any],
    recomputed: Mapping[str, Any],
) -> dict[str, Any]:
    results = recomputed["results"]
    value = {
        "schema_version": "exp-070-probe-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "stage": "formal",
        "status": "Passed",
        "passed_count": len(FORMAL_CHECKS),
        "failed_count": 0,
        "checks": FORMAL_CHECKS,
        "config": artifact(config_path),
        "static_completion": artifact(static_completion),
        "run_claim": artifact(public / "run-claim.json"),
        "run": artifact(public / "probe.json"),
        "probe_manifest": artifact(private / "probe-manifest.json", logical_name="probe-manifest.json"),
        "fold_bundles": recomputed["bundle_records"],
        "method_sha256": EXPECTED_METHOD_SHA256,
        "source_snapshot_sha256": SOURCE_SNAPSHOT_SHA256,
        "source_identity_snapshot_sha256": source_snapshot["sha256"],
        "bootstrap_plan_sha256": recomputed["bootstrap_plan_sha256"],
        "fit_counts": recomputed["fit_counts"],
        "results_sha256": bytes_sha256(canonical_json_bytes(results)),
        "negative_control_failure": results["negative_control_failure"],
        "representation_state": results["representation_state"],
        "representation_state_label": results["representation_state_label"],
        "probability_only_verification": True,
        "probe_refit": False,
        "runner_imported": False,
        "model_libraries_imported": False,
        "source_unchanged": True,
        "access": {
            "sealed_probability_values_read": True,
            "label_values_read": True,
            "representation_values_read": False,
            "probe_refit": False,
            "thresholds_recomputed": True,
            "metrics_recomputed": True,
            "bootstrap_recomputed": True,
            "validation_accessed": False,
            "test_accessed": False,
            "model_loaded": False,
            "forward_executed": False,
        },
        "claim_boundary": config["claim_boundary"],
    }
    if _public_sensitive(value):
        raise ValueError("EXP-070 formal verification public privacy drift")
    return value


def _formal_completion(
    config: Mapping[str, Any],
    public: Path,
    private: Path,
    static_completion: Path,
    verification_path: Path,
    results: Mapping[str, Any],
) -> dict[str, Any]:
    negative_control_failure = bool(results["negative_control_failure"])
    value = {
        "schema_version": "exp-070-probe-complete-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "status": "Complete",
        "formal_probe_complete": True,
        "exp070_complete": True,
        "exp071_authorized": False,
        "performance_metrics_computed": True,
        "negative_control_failure": negative_control_failure,
        "representation_state_assignment_valid": not negative_control_failure,
        "representation_state": results["representation_state"],
        "representation_state_label": results["representation_state_label"],
        "model_loaded": False,
        "forward_executed": False,
        "source_mutated": False,
        "verifier_refit_probe": False,
        "static_completion": artifact(static_completion),
        "run": artifact(public / "probe.json"),
        "verification": artifact(verification_path),
        "probe_manifest": artifact(private / "probe-manifest.json", logical_name="probe-manifest.json"),
        "claim_boundary": config["claim_boundary"],
        "next_gate": (
            "EXP-070 Complete with Negative-control failure; representation-state assignment blocked; EXP-071 unauthorized"
            if negative_control_failure
            else "EXP-070 Complete; EXP-071 unauthorized"
        ),
    }
    if _public_sensitive(value):
        raise ValueError("EXP-070 formal completion public privacy drift")
    return value


def _peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def verify_formal(config_path: Path, *, complete: bool) -> dict[str, Any]:
    started = time.monotonic()
    config = load_config(config_path, kind="formal")
    paths = require_implementation(config)
    require_import_boundaries(paths, static=False)
    static_completion = require_static_completion(config)
    environment = require_environment(config)
    require_private_ignore()
    if shutil.disk_usage(PROJECT_ROOT).free < 536870912:
        raise OSError("EXP-070 formal verifier free-disk gate failed")
    public, private, public_files = _validate_formal_roots(config)
    verification_path = public / "verification.json"
    completion_path = public / "probe-complete.json"
    if "verification.json" in public_files:
        prefix = require_canonical_json(verification_path)
        if prefix.get("status") != "Passed" or prefix.get("failed_count") != 0:
            raise RuntimeError("Only an exact Passed formal verification prefix can resume")
    before = source_identity_snapshot(config)
    sources = require_frozen_sources(config)
    after_sources = source_identity_snapshot(config)
    if before != after_sources:
        raise ValueError("EXP-070 source changed during formal source checks")
    _claim, _input = _validate_claim_and_input(
        config_path,
        config,
        static_completion,
        sources,
        before,
        environment,
        public,
        private,
    )
    public_rows = _public_fold_rows(config)
    prevalidate_fold_structures(config, before, public_rows)
    labels = load_labels(config, public_rows)
    recomputed = recompute_results(config, labels, public_rows, before)
    _manifest, _report = _validate_manifests_and_report(
        config_path, config, public, private, before, recomputed
    )
    final_source = source_identity_snapshot(config)
    if final_source != before or recovery_snapshot_digest() != SOURCE_SNAPSHOT_SHA256:
        raise ValueError("EXP-070 source changed during formal verification")
    if time.monotonic() - started > float(config["resources"]["formal_wall_seconds"]):
        raise TimeoutError("EXP-070 verifier wall-time ceiling exceeded")
    if _peak_rss_bytes() > int(config["resources"]["probe_peak_rss_bytes"]):
        raise MemoryError("EXP-070 verifier peak-RSS ceiling exceeded")
    if {name.split(".")[0] for name in sys.modules} & FORBIDDEN_MODEL_MODULES:
        raise RuntimeError("EXP-070 formal verifier imported a model library")
    if any(name.endswith("run_exp070_probe") for name in sys.modules):
        raise RuntimeError("EXP-070 formal verifier imported the producer")
    expected_verification = _formal_verification(
        config_path, config, public, private, static_completion, before, recomputed
    )
    if os.path.lexists(verification_path):
        if require_canonical_json(verification_path) != expected_verification:
            raise ValueError("EXP-070 Passed verification prefix drift")
    elif complete:
        raise RuntimeError("Formal completion requires an existing Passed verification")
    else:
        if require_safe_root(public, private=False) != set(
            config["outputs"]["formal_public_awaiting_verification_allowlist"]
        ):
            raise ValueError("EXP-070 formal preverification inventory drift")
        create_json_once(verification_path, expected_verification)
    if complete:
        expected_completion = _formal_completion(
            config,
            public,
            private,
            static_completion,
            verification_path,
            recomputed["results"],
        )
        if os.path.lexists(completion_path):
            if require_canonical_json(completion_path) != expected_completion:
                raise ValueError("EXP-070 formal completion drift")
        else:
            create_json_once(completion_path, expected_completion)
        if require_safe_root(public, private=False) != set(
            config["outputs"]["formal_public_success_allowlist"]
        ):
            raise ValueError("EXP-070 formal terminal inventory drift")
        require_file_modes(
            public, config["outputs"]["formal_public_success_allowlist"], private=False
        )
    elif os.path.lexists(completion_path):
        raise RuntimeError("Formal verify cannot create or consume completion")
    elif require_safe_root(public, private=False) != set(
        config["outputs"]["formal_public_verified_allowlist"]
    ):
        raise ValueError("EXP-070 formal verified inventory drift")
    return expected_verification


def _record_failure(stage: str, config_path: Path, error: BaseException) -> None:
    try:
        config = strict_json(config_path)
        if not isinstance(config, Mapping) or _config_kind(config) != stage:
            return
        public = _root(config, private=False)
        if not public.is_dir() or public.is_symlink() or file_mode(public) != "0755":
            return
        if stage == "static":
            target = public / "static-verification.json"
            prerequisite = public / "static.json"
            schema = "exp-070-probe-static-verification-failure-v1"
            run_stage = "static"
        else:
            target = public / "verification.json"
            prerequisite = public / "probe.json"
            schema = "exp-070-probe-verification-failure-v1"
            run_stage = "formal"
            if (public / "failure.json").exists():
                return
        if (
            not prerequisite.is_file()
            or prerequisite.is_symlink()
            or prerequisite.stat().st_nlink != 1
            or file_mode(prerequisite) != "0644"
            or os.path.lexists(target)
        ):
            return
        value = {
            "schema_version": schema,
            "experiment_id": EXPERIMENT_ID,
            "run_id": config.get("run_id"),
            "attempt_id": config.get("attempt_id"),
            "stage": run_stage,
            "status": "Failed",
            "technical_failure": True,
            "error_type": type(error).__name__,
            "formal_probe_authorized": False if stage == "static" else True,
            "exp070_complete": False,
            "exp071_authorized": False,
            "claim_boundary": config.get("claim_boundary"),
        }
        if _public_sensitive(value):
            return
        create_json_once(target, value)
    except Exception:
        return


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        required=True,
        choices=("static-verify", "static-complete", "formal-verify", "formal-complete"),
    )
    parser.add_argument("--config", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    kind, phase = args.stage.split("-", 1)
    config_path = args.config or (
        DEFAULT_STATIC_CONFIG if kind == "static" else DEFAULT_FORMAL_CONFIG
    )
    try:
        result = (
            verify_static(config_path, complete=phase == "complete")
            if kind == "static"
            else verify_formal(config_path, complete=phase == "complete")
        )
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as error:
        if phase == "verify":
            _record_failure(kind, config_path, error)
        print(f"{type(error).__name__}: verification failed", file=sys.stderr)
        return 1
    print(json.dumps({"stage": args.stage, "status": result["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
