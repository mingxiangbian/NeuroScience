#!/usr/bin/env python3
"""Incident 003 recovery verifier for seed-44 EXP-060 router preflight.

This program never runs the preflight runner and never writes the canonical
Attempt-1 verifier sidecars.  It virtualizes those sidecars in memory and
publishes one append-only recovery envelope in a separate namespace.
"""

from __future__ import annotations

import argparse
import ast
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import resource
import stat
import struct
import sys
import time
from types import ModuleType
from typing import Any
import zipfile


SCHEMA_CONFIG = "exp-router-preflight-verification-incident-003-attempt-2-config-v1"
SCHEMA_CLAIM = "exp-router-preflight-verification-incident-003-attempt-2-claim-v1"
SCHEMA_ATTEMPT1_FAILURE = (
    "exp-router-preflight-verification-incident-003-attempt-1-failure-v1"
)
SCHEMA_PASSED = "exp-router-preflight-verification-incident-003-attempt-2-v1"
SCHEMA_FAILED = "exp-router-preflight-verification-incident-003-attempt-2-failure-v1"
SCHEMA_TERMINAL = "exp-router-preflight-verification-incident-003-attempt-2-terminal-v1"

INCIDENT_ID = "003"
EXPERIMENT_ID = "EXP-060"
PARENT_EXPERIMENT_ID = "EXP-062"
RUN_ID = "exp-062-seed-44-router-replication"
ATTEMPT_ID = "attempt-1"
MODEL_SEED = 44
RQ_ID = "RQ-S3"
VERIFICATION_ATTEMPT = 2
SCOPE = "preflight-recovery"

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
CONFIGS_DIR = SCRIPT_DIR / "configs"
CONFIG_NAME = (
    "exp-062-seed-44-router-replication-router-preflight-verification-"
    "attempt-2-incident-003.json"
)
DEFAULT_CONFIG = CONFIGS_DIR / CONFIG_NAME
PROTOCOL_PATH = (
    PROJECT_ROOT
    / "experiments/stack-overflow-emotion-gold/protocols/"
    "exp-062-exp060-router-preflight-verification-attempt-2-incident-003.md"
)
RECOVERY_TESTS_PATH = SCRIPT_DIR / "tests/test_exp060_router_preflight_attempt2.py"
ORIGINAL_LIVE_VERIFIER = SCRIPT_DIR / "verify_exp060_router_preflight.py"

ATTEMPT_PUBLIC = SCRIPT_DIR / "runs" / RUN_ID / ATTEMPT_ID
ATTEMPT_PRIVATE = SCRIPT_DIR / "private" / RUN_ID / ATTEMPT_ID
ATTEMPT1_ROOT = ATTEMPT_PUBLIC / "router-preflight"
ATTEMPT2_ROOT = ATTEMPT_PUBLIC / "router-preflight-verification-attempt-2"
ORIGINAL_CONFIG = CONFIGS_DIR / (
    "exp-062-seed-44-router-replication-router-preflight-attempt-1.json"
)
ORIGINAL_RUN = ATTEMPT1_ROOT / "run.json"
ORIGINAL_CONTRACT = ATTEMPT1_ROOT / "preflight-contract.json"
ORIGINAL_FROZEN_VERIFIER = (
    ATTEMPT1_ROOT / "frozen-sources/verify_exp060_router_preflight.py"
)
CANONICAL_VERIFICATION = ATTEMPT1_ROOT / "verification.json"
CANONICAL_SUMMARY = ATTEMPT1_ROOT / "VERIFICATION-SUMMARY.md"
FORMAL_CONFIG = CONFIGS_DIR / (
    "exp-062-seed-44-router-replication-router-formal-attempt-1.json"
)
FORMAL_PUBLIC = ATTEMPT_PUBLIC / "router"
FORMAL_PRIVATE = ATTEMPT_PRIVATE / "router"
SELECTION = SCRIPT_DIR / "runs" / RUN_ID / "selected-attempt.json"

ORIGINAL_VERIFIER_BYTES = 84331
ORIGINAL_VERIFIER_SHA256 = (
    "31d985d37940994f8caabcb065a426d92afe710d6ecaed8a22a33511f8ef870c"
)
ORIGINAL_CONFIG_SHA256 = (
    "2765265f4c6a62349fc2645a466f116b4c1ca5e675932c21ca510360b991b823"
)
ORIGINAL_RUN_SHA256 = (
    "0a230f297fa16c670359c9ad00580add30a556e11dcfa59ce7c3702804960347"
)
ORIGINAL_CONTRACT_SHA256 = (
    "2229566b2f718a601caa8146880ee0257a567ac1c68e6e8a8eec831318890369"
)

SEED_CONTRACT = {
    "model_seed": 44,
    "python_seed": 44,
    "numpy_seed": 44,
    "torch_seed": 44,
    "m1_batch_seed": 44,
    "m3_head_seed": 44,
    "m3_batch_seed": 44,
    "m3_lora_seed": 100044,
}

ORIGINAL_CHECK_NAMES = (
    "verification.config",
    "verification.run_schema",
    "verification.contract_schema",
    "verification.runner_checks",
    "verification.upstream_chain",
    "verification.input_header_only",
    "verification.router_identity_calibration",
    "verification.policies_5",
    "verification.deployable_policy_order_3",
    "verification.formal_source_contract",
    "verification.frozen_sources",
    "verification.public_modes",
    "verification.public_privacy",
    "verification.formal_public_absent",
    "verification.formal_private_absent",
    "verification.completion_absent",
    "verification.selection_absent",
    "verification.resources.wall_seconds",
    "verification.resources.peak_memory_gb",
    "verification.resources.zero_cost_forward",
)

RUN_CHECK_NAMES = (
    "config.exact_schema",
    "config.identity",
    "config.authorization_no_result_only",
    "config.upstream_chain",
    "input.header_schema_only",
    "input.mode_0600_nlink1",
    "input.parent_mode_0700",
    "exp059.diagnostic_calibrators_allowed",
    "exp059.router_replication_identity",
    "router.policies_5",
    "router.deployable_policy_order_3",
    "router.formal_source_contract",
    "features.exact_14",
    "cross_fitting.inner3_outer4",
    "outputs.preflight_absent",
    "outputs.formal_public_absent",
    "outputs.formal_private_absent",
    "outputs.completion_absent",
    "outputs.selection_absent",
    "runtime.numpy_available",
    "runtime.scikit_learn_available",
    "tests.preflight",
    "tests.formal",
    "tests.launchers",
    "resources.wall_seconds",
    "resources.peak_memory_gb",
    "resources.api_gpu_forward_zero",
)

RECOVERY_CHECK_NAMES = (
    "recovery.incident_config",
    "recovery.attempt1_failure",
    "recovery.canonical_absence",
    "recovery.runner_seal",
    "recovery.contract",
    "recovery.frozen_inventory",
    "recovery.original_verifier_bytes",
    "recovery.repo_root_injection",
    "recovery.writer_capture",
    "recovery.virtual_tree_audit",
    "recovery.original_return",
    "recovery.original_checks_20",
    "recovery.no_result_claims",
    "recovery.resources_privacy",
    "recovery.physical_invariants",
    "recovery.downstream_absence",
)

ORIGINAL_VERIFICATION_KEYS = {
    "schema_version",
    "experiment_id",
    "replication_parent_experiment_id",
    "run_id",
    "attempt_id",
    "model_seed",
    "seed_contract",
    "rq_id",
    "scope",
    "verified_at_utc",
    "status",
    "passed_count",
    "failed_count",
    "checks",
    "independent",
    "runner_imported",
    "execution_claims",
    "verified_artifacts",
    "resources",
    "claim_boundary",
}

SOURCE_ARTIFACT_KEYS = {
    "config",
    "protocol",
    "preflight_runner",
    "preflight_verifier",
    "preflight_tests",
    "runner",
    "verifier",
    "tests",
    "runner_launcher",
    "verifier_launcher",
    "launcher_tests",
}

EXECUTION_CLAIM_KEYS = {
    "array_values_loaded",
    "real_features_constructed",
    "real_router_targets_constructed",
    "scaler_or_router_fitted",
    "router_metrics_computed",
    "bootstrap_computed",
    "validation_accessed",
    "test_accessed",
    "raw_text_accessed",
    "model_loaded_or_forward_run",
    "formal_router_training",
    "formal_result_computation",
}

FAILURE_STAGES = {
    "claim",
    "original_verifier",
    "candidate_validation",
    "passed_publish",
    "passed_summary",
    "passed_postcheck",
    "final_state_audit",
    "final_resource_audit",
    "terminal_seal",
    "terminal_postcheck",
}

PASSED_KEYS = {
    "schema_version",
    "incident_id",
    "verification_attempt",
    "experiment_id",
    "replication_parent_experiment_id",
    "run_id",
    "attempt_id",
    "model_seed",
    "seed_contract",
    "rq_id",
    "scope",
    "status",
    "verified_at_utc",
    "patch_ledger",
    "original_artifacts",
    "physical_invariants",
    "virtual_namespace",
    "captured_candidate",
    "checks",
    "passed_count",
    "failed_count",
    "resources",
    "formal_gate_authorized",
    "claim_boundary",
}

FAILED_KEYS = {
    "schema_version",
    "incident_id",
    "verification_attempt",
    "experiment_id",
    "replication_parent_experiment_id",
    "run_id",
    "attempt_id",
    "model_seed",
    "seed_contract",
    "rq_id",
    "scope",
    "status",
    "failed_at_utc",
    "failure_stage",
    "failure_code",
    "exception_type",
    "completed_checks",
    "original_artifacts",
    "resources",
    "formal_gate_authorized",
    "claim_boundary",
}

PUBLIC_SENSITIVE_KEYS = {
    "sample_id",
    "sample_ids",
    "component_id",
    "component_ids",
    "fold_id",
    "fold_ids",
    "gold",
    "logit",
    "logits",
    "probability",
    "probabilities",
    "feature",
    "features",
    "feature_matrix",
    "target",
    "targets",
    "router_targets",
    "route_score",
    "route_scores",
    "route_mask",
    "route_masks",
    "prediction",
    "predictions",
    "raw_text",
    "text",
}

EXPECTED_HEADER = {
    "sample_ids": {"shape": [3360], "dtype": "<U31", "fortran_order": False},
    "component_ids": {"shape": [3360], "dtype": "<U34", "fortran_order": False},
    "fold_ids": {"shape": [3360], "dtype": "int8", "fortran_order": False},
    "gold": {"shape": [3360, 6], "dtype": "uint8", "fortran_order": False},
    "m1_logits": {"shape": [3360, 6], "dtype": "float32", "fortran_order": False},
    "m3_logits": {"shape": [3360, 6], "dtype": "float32", "fortran_order": False},
    "character_lengths": {"shape": [3360], "dtype": "int32", "fortran_order": False},
    "m1_token_lengths": {"shape": [3360], "dtype": "int32", "fortran_order": False},
    "m3_token_lengths": {"shape": [3360], "dtype": "int32", "fortran_order": False},
    "m1_fold_run_sha256": {"shape": [3360], "dtype": "<U64", "fortran_order": False},
    "m3_fold_run_sha256": {"shape": [3360], "dtype": "<U64", "fortran_order": False},
}

CONFIG_KEYS = {
    "schema_version",
    "incident_id",
    "experiment_id",
    "replication_parent_experiment_id",
    "run_id",
    "attempt_id",
    "model_seed",
    "seed_contract",
    "rq_id",
    "registered_at",
    "authorization",
    "predecessor",
    "implementation",
    "outputs",
    "resources",
    "privacy",
    "claim_boundary",
    "commands",
}

CLAIM_KEYS = {
    "schema_version",
    "incident_id",
    "verification_attempt",
    "experiment_id",
    "replication_parent_experiment_id",
    "run_id",
    "attempt_id",
    "model_seed",
    "seed_contract",
    "rq_id",
    "scope",
    "claimed_at_utc",
    "incident_config",
    "expected_frozen_sources",
    "formal_gate_authorized",
    "claim_boundary",
}

ATTEMPT1_FAILURE_KEYS = {
    "schema_version",
    "incident_id",
    "verification_attempt",
    "experiment_id",
    "replication_parent_experiment_id",
    "run_id",
    "attempt_id",
    "model_seed",
    "seed_contract",
    "status",
    "failure_stage",
    "failure_code",
    "exception_type",
    "exit_code",
    "canonical_verification_absent",
    "canonical_summary_absent",
    "original_artifacts",
    "formal_gate_authorized",
    "claim_boundary",
}

TERMINAL_KEYS = {
    "schema_version",
    "incident_id",
    "verification_attempt",
    "experiment_id",
    "replication_parent_experiment_id",
    "run_id",
    "attempt_id",
    "model_seed",
    "seed_contract",
    "rq_id",
    "scope",
    "status",
    "completed_at_utc",
    "verification",
    "summary",
    "terminal_resources",
    "terminal_state_sha256",
    "formal_gate_authorized",
    "claim_boundary",
}

AUTHORIZATION = {
    "verification_attempt_2": True,
    "runner_rerun": False,
    "formal_execution": False,
    "primary_gate": False,
    "selection": False,
    "private_values": False,
    "validation_access": False,
    "test_access": False,
    "model_loading_or_forward": False,
    "raw_text_access": False,
}

AUTHORIZATION_BASIS = (
    "Current user authorization covers exactly one Incident 003 preflight verification attempt 2; "
    "runner rerun and formal execution remain prohibited."
)

RESOURCE_CONTRACT = {
    "wall_seconds": 300,
    "peak_memory_gb": 2.0,
    "api_cost_usd": 0,
    "gpu_cost_usd": 0,
    "model_forward_runs": 0,
}

CLAIM_BOUNDARY = (
    "Incident-003 preflight verifier recovery only; namespace-virtualized output is "
    "not canonical Attempt-1 verification and does not authorize formal execution."
)


class Attempt2TerminalFailure(Exception):
    """Safe marker for a terminal Incident 003 failure."""

    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__("Incident 003 attempt-2 terminal failure")
        self.payload = payload


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _typed_int(value: Any) -> bool:
    return type(value) is int


def _typed_number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(float(value))


def _typed_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            _typed_equal(actual[key], child) for key, child in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _typed_equal(left, right) for left, right in zip(actual, expected)
        )
    if isinstance(expected, float):
        return math.isfinite(actual) and actual == expected
    return actual == expected


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    return _sha256(encoded)


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _stat_signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _assert_no_symlink_components(path: Path) -> None:
    absolute = Path(os.path.abspath(os.fspath(path)))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        metadata = os.lstat(current)
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"Path traverses a symbolic link: {path}")


def _secure_read(path: Path, mode: int) -> tuple[bytes, os.stat_result]:
    lexical = Path(os.path.abspath(os.fspath(path)))
    _assert_no_symlink_components(lexical)
    before = os.lstat(lexical)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or stat.S_IMODE(before.st_mode) != mode
    ):
        raise PermissionError(f"Secure-read precondition failed: {lexical}")
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("O_NOFOLLOW is required")
    descriptor = os.open(lexical, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(descriptor)
        if _stat_signature(opened) != _stat_signature(before):
            raise ValueError(f"File changed before open: {lexical}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        payload = b"".join(chunks)
        after_fd = os.fstat(descriptor)
        if len(payload) != opened.st_size or _stat_signature(after_fd) != _stat_signature(opened):
            raise ValueError(f"File changed during read: {lexical}")
    finally:
        os.close(descriptor)
    after = os.lstat(lexical)
    if _stat_signature(after) != _stat_signature(after_fd):
        raise ValueError(f"File changed after read: {lexical}")
    return payload, after


def _display(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))


def artifact(path: Path, mode: int = 0o644) -> dict[str, Any]:
    payload, metadata = _secure_read(path, mode)
    return {"path": _display(path), "bytes": metadata.st_size, "sha256": _sha256(payload)}


def _require_record(record: Any, mode: int) -> tuple[Path, bytes]:
    if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
        raise ValueError("Artifact record schema drift")
    if (
        not isinstance(record["path"], str)
        or not _typed_int(record["bytes"])
        or record["bytes"] < 0
        or not isinstance(record["sha256"], str)
        or len(record["sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in record["sha256"])
    ):
        raise ValueError("Artifact record type drift")
    relative = Path(record["path"])
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("Artifact path is not normalized project-relative")
    path = PROJECT_ROOT / relative
    payload, metadata = _secure_read(path, mode)
    if metadata.st_size != record["bytes"] or _sha256(payload) != record["sha256"]:
        raise ValueError(f"Artifact drift: {relative}")
    return path, payload


def _create_directory_once(path: Path) -> None:
    if os.path.lexists(path):
        raise FileExistsError(f"Append-only directory already exists: {path}")
    _assert_no_symlink_components(path.parent)
    os.mkdir(path, 0o755)
    os.chmod(path, 0o755)
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o755:
        raise PermissionError(f"Directory claim invariant failed: {path}")


def _create_bytes_once(path: Path, payload: bytes) -> None:
    _assert_no_symlink_components(path.parent)
    parent = os.lstat(path.parent)
    if stat.S_ISLNK(parent.st_mode) or not stat.S_ISDIR(parent.st_mode) or stat.S_IMODE(parent.st_mode) != 0o755:
        raise PermissionError(f"Output parent invariant failed: {path.parent}")
    if os.path.lexists(path):
        raise FileExistsError(f"Append-only output already exists: {path}")
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o644,
    )
    try:
        os.fchmod(descriptor, 0o644)
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("Short append-only write")
            view = view[written:]
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o644
            or metadata.st_size != len(payload)
        ):
            raise PermissionError(f"Output FD invariant failed: {path}")
    finally:
        os.close(descriptor)
    observed, _ = _secure_read(path, 0o644)
    if observed != payload:
        raise ValueError(f"Output bytes changed after write: {path}")


def _create_json_once(path: Path, value: Any) -> None:
    _create_bytes_once(path, _json_bytes(value))


def _peak_rss_gb() -> float:
    values = [
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    ]
    factor = 1 / 1e9 if platform.system() == "Darwin" else 1024 / 1e9
    return max(float(value) * factor for value in values)


def _privacy_violations(value: Any, prefix: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            if key in PUBLIC_SENSITIVE_KEYS:
                violations.append(child_path)
            violations.extend(_privacy_violations(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(_privacy_violations(child, f"{prefix}[{index}]"))
    return violations


def _npy_header(stream: Any) -> dict[str, Any]:
    if stream.read(6) != b"\x93NUMPY":
        raise ValueError("Invalid NPY magic")
    version = tuple(stream.read(2))
    if version == (1, 0):
        header_size = struct.unpack("<H", stream.read(2))[0]
    elif version in {(2, 0), (3, 0)}:
        header_size = struct.unpack("<I", stream.read(4))[0]
    else:
        raise ValueError("Unsupported NPY header version")
    header = ast.literal_eval(stream.read(header_size).decode("latin1").strip())
    if not isinstance(header, dict) or set(header) != {"descr", "fortran_order", "shape"}:
        raise ValueError("NPY header schema drift")
    dtype = str(header["descr"])
    dtype_names = {
        "|i1": "int8",
        "|u1": "uint8",
        "<i4": "int32",
        "<f4": "float32",
    }
    return {
        "shape": list(header["shape"]),
        "dtype": dtype_names.get(dtype, dtype),
        "fortran_order": header["fortran_order"],
    }


def _npz_header(payload: bytes) -> dict[str, dict[str, Any]]:
    schema: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != {f"{name}.npy" for name in EXPECTED_HEADER}:
            raise ValueError("NPZ member inventory drift")
        for member in names:
            if Path(member).name != member or not member.endswith(".npy"):
                raise ValueError("Nested NPZ member is forbidden")
            with archive.open(member) as stream:
                schema[member[:-4]] = _npy_header(stream)
    if schema != EXPECTED_HEADER:
        raise ValueError("Paired OOF header drift")
    return schema


def _output_paths() -> dict[str, Path]:
    return {
        "root": ATTEMPT2_ROOT,
        "frozen_sources": ATTEMPT2_ROOT / "frozen-sources",
        "claim": ATTEMPT2_ROOT / "verification-attempt-2-claim.json",
        "attempt1_failure": ATTEMPT2_ROOT / "attempt-1-failure-seal.json",
        "passed": ATTEMPT2_ROOT / "verification.json",
        "passed_summary": ATTEMPT2_ROOT / "VERIFICATION-SUMMARY.md",
        "terminal": ATTEMPT2_ROOT / "verification-attempt-2-terminal.json",
        "failed": ATTEMPT2_ROOT / "attempt-2-failure.json",
        "failed_summary": ATTEMPT2_ROOT / "FAILURE-SUMMARY.md",
    }


def _canonical_sidecars() -> tuple[Path, Path]:
    return CANONICAL_VERIFICATION, CANONICAL_SUMMARY


def _runtime_resources(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value)
        == {
            "wall_seconds",
            "peak_process_rss_gb",
            "api_cost_usd",
            "gpu_cost_usd",
            "model_forward_runs",
        }
        and _typed_number(value["wall_seconds"])
        and 0 <= float(value["wall_seconds"]) <= 300
        and _typed_number(value["peak_process_rss_gb"])
        and 0 <= float(value["peak_process_rss_gb"]) <= 2.0
        and type(value["api_cost_usd"]) is int
        and value["api_cost_usd"] == 0
        and type(value["gpu_cost_usd"]) is int
        and value["gpu_cost_usd"] == 0
        and type(value["model_forward_runs"]) is int
        and value["model_forward_runs"] == 0
    )


def _read_json_record(record: Any, mode: int = 0o644) -> tuple[Path, dict[str, Any]]:
    path, payload = _require_record(record, mode)
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return path, value


def _config_path(path: Path) -> Path:
    lexical = Path(os.path.abspath(os.fspath(path)))
    if lexical.parent != CONFIGS_DIR.resolve() or lexical.name != CONFIG_NAME:
        raise ValueError("Incident 003 config path is not canonical")
    _secure_read(lexical, 0o644)
    return lexical


def _validate_predecessor_payloads(
    original_config: dict[str, Any], run: dict[str, Any], contract: dict[str, Any]
) -> None:
    if (
        original_config.get("schema_version")
        != "exp-router-replication-preflight-config-v1"
        or original_config.get("experiment_id") != EXPERIMENT_ID
        or original_config.get("replication_parent_experiment_id") != PARENT_EXPERIMENT_ID
        or original_config.get("run_id") != RUN_ID
        or original_config.get("attempt_id") != ATTEMPT_ID
        or original_config.get("model_seed") != MODEL_SEED
        or not _typed_equal(original_config.get("seed_contract"), SEED_CONTRACT)
        or original_config.get("authorization", {}).get("no_result_preflight") is not True
        or any(
            original_config.get("authorization", {}).get(key) is not False
            for key in (
                "formal_router_training",
                "formal_result_computation",
                "validation_access",
                "test_access",
                "model_loading_or_forward",
                "raw_text_access",
            )
        )
    ):
        raise ValueError("Attempt-1 config no-result identity drift")
    checks = run.get("checks")
    if (
        run.get("schema_version") != "exp-router-replication-preflight-run-v1"
        or run.get("status") != "CompletedAwaitingVerification"
        or run.get("experiment_id") != EXPERIMENT_ID
        or run.get("replication_parent_experiment_id") != PARENT_EXPERIMENT_ID
        or run.get("run_id") != RUN_ID
        or run.get("attempt_id") != ATTEMPT_ID
        or run.get("model_seed") != MODEL_SEED
        or not _typed_equal(run.get("seed_contract"), SEED_CONTRACT)
        or not isinstance(checks, list)
        or [row.get("name") for row in checks] != list(RUN_CHECK_NAMES)
        or any(
            not isinstance(row, dict)
            or set(row) != {"name", "passed", "detail"}
            or row.get("passed") is not True
            for row in checks
        )
        or run.get("check_count") != 27
        or run.get("passed_count") != 27
        or run.get("failed_count") != 0
        or not _runtime_resources(run.get("resources"))
        or not isinstance(run.get("execution_claims"), dict)
        or set(run["execution_claims"]) != EXECUTION_CLAIM_KEYS
        or any(value is not False for value in run["execution_claims"].values())
    ):
        raise ValueError("Attempt-1 runner seal drift")
    expected_header_rows = [
        {"array_name": name, **details}
        for name, details in sorted(EXPECTED_HEADER.items())
    ]
    if (
        contract.get("schema_version")
        != "exp-router-replication-preflight-contract-v1"
        or contract.get("experiment_id") != EXPERIMENT_ID
        or contract.get("replication_parent_experiment_id") != PARENT_EXPERIMENT_ID
        or contract.get("run_id") != RUN_ID
        or contract.get("attempt_id") != ATTEMPT_ID
        or contract.get("result_bearing") is not False
        or contract.get("input_schema") != expected_header_rows
        or contract.get("feature_count") != 14
        or contract.get("nested_cross_fitting_required") is not True
        or contract.get("policies")
        != [
            "m1_only",
            "m3_only",
            "m1_max_entropy",
            "m1_threshold_proximity",
            "logistic_router",
        ]
        or contract.get("deployable_policy_order")
        != ["m1_max_entropy", "m1_threshold_proximity", "logistic_router"]
        or any(
            contract.get(key) is not False
            for key in (
                "formal_router_training_authorized",
                "formal_result_computation_authorized",
                "validation_access",
                "test_access",
                "raw_text_access",
                "model_loading_or_forward",
            )
        )
    ):
        raise ValueError("Attempt-1 no-result contract drift")
    if _privacy_violations(run) or _privacy_violations(contract):
        raise ValueError("Attempt-1 public privacy drift")


def load_config(path: Path) -> dict[str, Any]:
    canonical = _config_path(path)
    config = json.loads(_secure_read(canonical, 0o644)[0].decode("utf-8"))
    if not isinstance(config, dict) or set(config) != CONFIG_KEYS:
        raise ValueError("Incident 003 config top-level schema drift")
    if (
        config.get("schema_version") != SCHEMA_CONFIG
        or config.get("incident_id") != INCIDENT_ID
        or config.get("experiment_id") != EXPERIMENT_ID
        or config.get("replication_parent_experiment_id") != PARENT_EXPERIMENT_ID
        or config.get("run_id") != RUN_ID
        or config.get("attempt_id") != ATTEMPT_ID
        or not _typed_int(config.get("model_seed"))
        or config.get("model_seed") != MODEL_SEED
        or not _typed_equal(config.get("seed_contract"), SEED_CONTRACT)
        or config.get("rq_id") != RQ_ID
        or config.get("registered_at") != "2026-08-24"
        or config.get("claim_boundary") != CLAIM_BOUNDARY
    ):
        raise ValueError("Incident 003 identity drift")
    authorization = config.get("authorization")
    if not isinstance(authorization, dict) or set(authorization) != {"basis", *AUTHORIZATION}:
        raise ValueError("Incident 003 authorization inventory drift")
    if authorization["basis"] != AUTHORIZATION_BASIS:
        raise ValueError("Incident 003 authorization basis drift")
    if not _typed_equal({key: authorization[key] for key in AUTHORIZATION}, AUTHORIZATION):
        raise PermissionError("Incident 003 authorization drift")
    if not _typed_equal(config.get("resources"), RESOURCE_CONTRACT):
        raise ValueError("Incident 003 resource contract drift")
    privacy = config.get("privacy")
    if privacy != {
        "public_sensitive_keys": sorted(PUBLIC_SENSITIVE_KEYS),
        "private_values_loaded": False,
        "np_load_allowed": False,
    }:
        raise ValueError("Incident 003 privacy contract drift")
    outputs = config.get("outputs")
    expected_outputs = {name: _display(value) for name, value in _output_paths().items()}
    if outputs != expected_outputs:
        raise ValueError("Incident 003 output path drift")
    commands = config.get("commands")
    expected_command = (
        f"/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python "
        f"projects/llm-forum-text-emotion-recognition/experiments/"
        f"stack-overflow-emotion-gold/oof-router/{Path(__file__).name} --config "
        f"projects/llm-forum-text-emotion-recognition/experiments/"
        f"stack-overflow-emotion-gold/oof-router/configs/{CONFIG_NAME}"
    )
    if commands != {"verify_attempt_2": expected_command}:
        raise ValueError("Incident 003 command drift")
    implementation = config.get("implementation")
    if not isinstance(implementation, dict) or set(implementation) != {"protocol", "verifier", "tests"}:
        raise ValueError("Incident 003 implementation inventory drift")
    expected_implementation = {
        "protocol": PROTOCOL_PATH,
        "verifier": Path(__file__).resolve(),
        "tests": RECOVERY_TESTS_PATH,
    }
    for name, expected in expected_implementation.items():
        observed, _ = _require_record(implementation[name], 0o644)
        if observed != expected.resolve():
            raise ValueError(f"Incident 003 implementation path drift: {name}")
    predecessor = config.get("predecessor")
    required_predecessor = {
        "failure",
        "config",
        "run",
        "contract",
        "frozen_verifier",
        "source_artifacts",
        "upstreams",
        "input",
    }
    if not isinstance(predecessor, dict) or set(predecessor) != required_predecessor:
        raise ValueError("Incident 003 predecessor inventory drift")
    failure = predecessor["failure"]
    if failure != {
        "verification_attempt": 1,
        "outcome": "TerminalFailureNoSidecars",
        "failure_stage": "child_test_preflight",
        "failure_code": "missing_repo_root",
        "exception_type": "NameError",
        "exit_code": 1,
        "canonical_verification_absent": True,
        "canonical_summary_absent": True,
    }:
        raise ValueError("Attempt-1 failure record drift")
    fixed_records = {
        "config": (ORIGINAL_CONFIG, ORIGINAL_CONFIG_SHA256),
        "run": (ORIGINAL_RUN, ORIGINAL_RUN_SHA256),
        "contract": (ORIGINAL_CONTRACT, ORIGINAL_CONTRACT_SHA256),
        "frozen_verifier": (ORIGINAL_FROZEN_VERIFIER, ORIGINAL_VERIFIER_SHA256),
    }
    for name, (expected_path, expected_hash) in fixed_records.items():
        observed, payload = _require_record(predecessor[name], 0o644)
        if observed != expected_path.resolve() or _sha256(payload) != expected_hash:
            raise ValueError(f"Attempt-1 predecessor drift: {name}")
    original_config = json.loads(_secure_read(ORIGINAL_CONFIG, 0o644)[0].decode("utf-8"))
    run = json.loads(_secure_read(ORIGINAL_RUN, 0o644)[0].decode("utf-8"))
    contract = json.loads(_secure_read(ORIGINAL_CONTRACT, 0o644)[0].decode("utf-8"))
    _validate_predecessor_payloads(original_config, run, contract)
    source_artifacts = run.get("source_artifacts")
    if predecessor["source_artifacts"] != source_artifacts or not isinstance(source_artifacts, dict):
        raise ValueError("Attempt-1 frozen-source lineage drift")
    if set(source_artifacts) != SOURCE_ARTIFACT_KEYS:
        raise ValueError("Attempt-1 source artifact inventory drift")
    if predecessor["frozen_verifier"] != source_artifacts["preflight_verifier"]:
        raise ValueError("Attempt-1 frozen verifier lineage drift")
    live_implementation = original_config.get("implementation")
    if not isinstance(live_implementation, dict) or set(live_implementation) != SOURCE_ARTIFACT_KEYS - {"config"}:
        raise ValueError("Attempt-1 live implementation inventory drift")
    for name, frozen_record in source_artifacts.items():
        _, frozen_payload = _require_record(frozen_record, 0o644)
        if name == "config":
            live_payload = _secure_read(ORIGINAL_CONFIG, 0o644)[0]
        else:
            _, live_payload = _require_record(live_implementation[name], 0o644)
        if frozen_payload != live_payload:
            raise ValueError(f"Attempt-1 frozen/live source drift: {name}")
    if predecessor["upstreams"] != run.get("upstreams") or predecessor["input"] != run.get("input"):
        raise ValueError("Attempt-1 upstream/input lineage drift")
    if not isinstance(predecessor["upstreams"], dict) or len(predecessor["upstreams"]) != 6:
        raise ValueError("Attempt-1 upstream count drift")
    for record in predecessor["upstreams"].values():
        _require_record(record, 0o644)
    _, input_payload = _require_record(predecessor["input"], 0o600)
    _npz_header(input_payload)
    for sidecar in _canonical_sidecars():
        if os.path.lexists(sidecar):
            raise FileExistsError("Canonical Attempt-1 verifier sidecar exists")
    for blocked in (FORMAL_CONFIG, FORMAL_PUBLIC, FORMAL_PRIVATE, SELECTION):
        if os.path.lexists(blocked):
            raise FileExistsError(f"Formal/downstream output already exists: {blocked}")
    if os.path.lexists(ATTEMPT2_ROOT):
        raise FileExistsError("Incident 003 output root is already claimed")
    if _privacy_violations(config):
        raise ValueError("Incident 003 config privacy drift")
    return config


def _snapshot_directory(path: Path, expected: set[str]) -> dict[str, Any]:
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"Expected real directory: {path}")
    entries = {entry.name: Path(entry.path) for entry in os.scandir(path)}
    if set(entries) != expected:
        raise ValueError(f"Directory manifest drift: {path}")
    result: dict[str, Any] = {".": _stat_signature(metadata)}
    for name, child in entries.items():
        child_metadata = os.lstat(child)
        if stat.S_ISDIR(child_metadata.st_mode):
            result[name] = ("dir", _stat_signature(child_metadata))
        else:
            payload, observed = _secure_read(child, 0o644)
            result[name] = ("file", _stat_signature(observed), _sha256(payload))
    return result


def _pyc_snapshot() -> dict[str, tuple[int, ...]]:
    result: dict[str, tuple[int, ...]] = {}
    for directory in (SCRIPT_DIR / "__pycache__", SCRIPT_DIR / "tests/__pycache__"):
        if not os.path.lexists(directory):
            continue
        metadata = os.lstat(directory)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("Python cache path type drift")
        for entry in os.scandir(directory):
            child = Path(entry.path)
            child_metadata = os.lstat(child)
            if stat.S_ISREG(child_metadata.st_mode):
                result[_display(child)] = _stat_signature(child_metadata)
    return result


def _state_snapshot(config: dict[str, Any]) -> dict[str, Any]:
    run = json.loads(_secure_read(ORIGINAL_RUN, 0o644)[0].decode("utf-8"))
    frozen_names = {Path(record["path"]).name for record in run["source_artifacts"].values()}
    original_config = json.loads(_secure_read(ORIGINAL_CONFIG, 0o644)[0].decode("utf-8"))
    live_implementation = original_config.get("implementation")
    if not isinstance(live_implementation, dict) or len(live_implementation) != 10:
        raise ValueError("Attempt-1 live implementation inventory drift")
    return {
        "attempt1_root": _snapshot_directory(
            ATTEMPT1_ROOT, {"run.json", "preflight-contract.json", "frozen-sources"}
        ),
        "frozen_sources": _snapshot_directory(ATTEMPT1_ROOT / "frozen-sources", frozen_names),
        "config": artifact(ORIGINAL_CONFIG),
        "run": artifact(ORIGINAL_RUN),
        "contract": artifact(ORIGINAL_CONTRACT),
        "upstreams": {
            name: artifact(PROJECT_ROOT / record["path"])
            for name, record in config["predecessor"]["upstreams"].items()
        },
        "live_implementation": {
            name: artifact(PROJECT_ROOT / record["path"])
            for name, record in live_implementation.items()
        },
        "input": artifact(PROJECT_ROOT / config["predecessor"]["input"]["path"], 0o600),
        "input_parent": _stat_signature(os.lstat((PROJECT_ROOT / config["predecessor"]["input"]["path"]).parent)),
        "pyc": _pyc_snapshot(),
        "canonical_absent": [not os.path.lexists(path) for path in _canonical_sidecars()],
        "downstream_absent": [
            not os.path.lexists(path)
            for path in (FORMAL_CONFIG, FORMAL_PUBLIC, FORMAL_PRIVATE, SELECTION)
        ],
    }


def _load_original_module(config: dict[str, Any]) -> ModuleType:
    frozen, frozen_payload = _require_record(config["predecessor"]["frozen_verifier"], 0o644)
    live_payload, _ = _secure_read(ORIGINAL_LIVE_VERIFIER, 0o644)
    if (
        frozen != ORIGINAL_FROZEN_VERIFIER.resolve()
        or len(frozen_payload) != ORIGINAL_VERIFIER_BYTES
        or _sha256(frozen_payload) != ORIGINAL_VERIFIER_SHA256
        or live_payload != frozen_payload
    ):
        raise ValueError("Original verifier held-bytes contract drift")
    module = ModuleType("_incident003_original_preflight_verifier")
    module.__file__ = str(ORIGINAL_LIVE_VERIFIER)
    module.__package__ = ""
    code = compile(
        frozen_payload.decode("utf-8"), str(ORIGINAL_LIVE_VERIFIER), "exec", dont_inherit=True
    )
    exec(code, module.__dict__)
    if hasattr(module, "REPO_ROOT"):
        raise ValueError("Original verifier unexpectedly defines REPO_ROOT")
    for name in (
        "_create_bytes_once",
        "_assert_replication_preflight_tree",
        "verify_replication_preflight",
    ):
        if not hasattr(module, name):
            raise ValueError(f"Original verifier API missing: {name}")
    return module


class _Capture:
    def __init__(self, module: ModuleType, config: dict[str, Any]) -> None:
        self.module = module
        self.config = config
        self.writer_calls: list[tuple[Path, bytes, int]] = []
        self.unverified_calls = 0
        self.verified_calls = 0
        self.original_assert = module._assert_replication_preflight_tree

    def writer(self, path: Path, payload: bytes, mode: int = 0o644) -> None:
        expected = [CANONICAL_VERIFICATION, CANONICAL_SUMMARY]
        index = len(self.writer_calls)
        if index >= 2 or Path(path) != expected[index] or mode != 0o644:
            raise ValueError("Original writer capture order/path/mode drift")
        if os.path.lexists(path):
            raise FileExistsError("Canonical sidecar was materialized")
        if not isinstance(payload, bytes) or not payload:
            raise ValueError("Captured writer payload is empty")
        self.writer_calls.append((Path(path), bytes(payload), mode))

    def virtual_assert(
        self, run_dir: Path, config: dict[str, Any], *, verified: bool
    ) -> tuple[Path, Path, Path]:
        if not verified:
            self.unverified_calls += 1
            return self.original_assert(run_dir, config, verified=False)
        self.verified_calls += 1
        physical = self.original_assert(run_dir, config, verified=False)
        if self.verified_calls != 1 or len(self.writer_calls) != 2:
            raise ValueError("Virtual verified-tree call/capture count drift")
        if any(os.path.lexists(path) for path in _canonical_sidecars()):
            raise ValueError("Canonical sidecars appeared during virtual audit")
        physical_names = {entry.name for entry in os.scandir(run_dir)}
        if physical_names != {"run.json", "preflight-contract.json", "frozen-sources"}:
            raise ValueError("Physical unverified manifest drift")
        effective = physical_names | {CANONICAL_VERIFICATION.name, CANONICAL_SUMMARY.name}
        if effective != {
            "run.json",
            "preflight-contract.json",
            "frozen-sources",
            "verification.json",
            "VERIFICATION-SUMMARY.md",
        }:
            raise ValueError("Virtual verified manifest drift")
        return physical


def _original_summary(candidate: dict[str, Any]) -> bytes:
    return (
        "# Seed-44 EXP-060 No-Result Preflight Verification\n\n"
        "- Status: `Passed`\n"
        f"- Checks: `{len(candidate['checks'])}/{len(candidate['checks'])}`\n"
        "- Independent verifier imported the runner: `false`\n"
        "- Feature/target/router/metric/bootstrap computation: `false`\n"
        "- Formal router execution remains separately authorized.\n"
    ).encode("utf-8")


def _validate_candidate(
    candidate_bytes: bytes,
    summary_bytes: bytes,
    stdout_text: str,
    stderr_text: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    candidate = json.loads(candidate_bytes.decode("utf-8"))
    if not isinstance(candidate, dict) or set(candidate) != ORIGINAL_VERIFICATION_KEYS:
        raise ValueError("Captured verification schema drift")
    if (
        candidate.get("schema_version")
        != "exp-router-replication-preflight-verification-v1"
        or candidate.get("experiment_id") != EXPERIMENT_ID
        or candidate.get("replication_parent_experiment_id") != PARENT_EXPERIMENT_ID
        or candidate.get("run_id") != RUN_ID
        or candidate.get("attempt_id") != ATTEMPT_ID
        or candidate.get("model_seed") != MODEL_SEED
        or not _typed_equal(candidate.get("seed_contract"), SEED_CONTRACT)
        or candidate.get("rq_id") != RQ_ID
        or candidate.get("scope") != "preflight"
        or candidate.get("status") != "Passed"
        or candidate.get("independent") is not True
        or candidate.get("runner_imported") is not False
        or candidate.get("claim_boundary")
        != "Verified seed-44 no-result router preflight only; formal routing remains separately authorized."
    ):
        raise ValueError("Captured verification identity/status drift")
    checks = candidate.get("checks")
    if (
        not isinstance(checks, list)
        or [row.get("name") for row in checks] != list(ORIGINAL_CHECK_NAMES)
        or any(
            not isinstance(row, dict)
            or set(row) != {"name", "passed", "detail"}
            or row.get("passed") is not True
            for row in checks
        )
        or not _typed_int(candidate.get("passed_count"))
        or candidate.get("passed_count") != 20
        or not _typed_int(candidate.get("failed_count"))
        or candidate.get("failed_count") != 0
    ):
        raise ValueError("Captured verification check inventory drift")
    claims = candidate.get("execution_claims")
    if (
        not isinstance(claims, dict)
        or set(claims) != EXECUTION_CLAIM_KEYS
        or any(value is not False for value in claims.values())
    ):
        raise ValueError("Captured no-result claim drift")
    if not _runtime_resources(candidate.get("resources")):
        raise ValueError("Captured verification resource drift")
    artifacts = candidate.get("verified_artifacts")
    expected_artifacts = {
        "config": config["predecessor"]["config"],
        "run": config["predecessor"]["run"],
        "contract": config["predecessor"]["contract"],
        "input": config["predecessor"]["input"],
        "upstreams": config["predecessor"]["upstreams"],
        "frozen_sources": config["predecessor"]["source_artifacts"],
        "formal_sources": {
            name: config["predecessor"]["source_artifacts"][name]
            for name in (
                "protocol",
                "runner",
                "verifier",
                "tests",
                "runner_launcher",
                "verifier_launcher",
                "launcher_tests",
            )
        },
    }
    if not _typed_equal(artifacts, expected_artifacts):
        raise ValueError("Captured verification artifact lineage drift")
    if summary_bytes != _original_summary(candidate):
        raise ValueError("Captured verification summary drift")
    if stderr_text != "":
        raise ValueError("Original verifier wrote stderr")
    lines = [line for line in stdout_text.splitlines() if line]
    if len(lines) != 1 or json.loads(lines[0]) != {
        "status": "Passed",
        "passed": 20,
        "failed": 0,
    }:
        raise ValueError("Original verifier terminal stdout drift")
    if _privacy_violations(candidate):
        raise ValueError("Captured verification privacy drift")
    return candidate


def _claim_payload(
    config_record: dict[str, Any],
    config: dict[str, Any],
    frozen: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    value = {
        "schema_version": SCHEMA_CLAIM,
        "incident_id": INCIDENT_ID,
        "verification_attempt": VERIFICATION_ATTEMPT,
        "experiment_id": EXPERIMENT_ID,
        "replication_parent_experiment_id": PARENT_EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "model_seed": MODEL_SEED,
        "seed_contract": SEED_CONTRACT,
        "rq_id": RQ_ID,
        "scope": SCOPE,
        "claimed_at_utc": utc_now(),
        "incident_config": config_record,
        "expected_frozen_sources": frozen,
        "formal_gate_authorized": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    if set(value) != CLAIM_KEYS or _privacy_violations(value):
        raise RuntimeError("Claim schema construction drift")
    return value


def _attempt1_failure_payload(config: dict[str, Any]) -> dict[str, Any]:
    value = {
        "schema_version": SCHEMA_ATTEMPT1_FAILURE,
        "incident_id": INCIDENT_ID,
        "verification_attempt": 1,
        "experiment_id": EXPERIMENT_ID,
        "replication_parent_experiment_id": PARENT_EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "model_seed": MODEL_SEED,
        "seed_contract": SEED_CONTRACT,
        "status": "Failed",
        "failure_stage": "child_test_preflight",
        "failure_code": "missing_repo_root",
        "exception_type": "NameError",
        "exit_code": 1,
        "canonical_verification_absent": True,
        "canonical_summary_absent": True,
        "original_artifacts": {
            name: config["predecessor"][name]
            for name in ("config", "run", "contract", "frozen_verifier")
        },
        "formal_gate_authorized": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    if set(value) != ATTEMPT1_FAILURE_KEYS or _privacy_violations(value):
        raise RuntimeError("Attempt-1 failure-seal construction drift")
    return value


def _passed_summary(value: dict[str, Any]) -> bytes:
    return (
        "# Incident 003 Preflight Verification Attempt 2\n\n"
        "- Status: `Passed`\n"
        f"- Recovery checks: `{value['passed_count']}/{value['passed_count']}`\n"
        "- Namespace virtualized: `true`\n"
        "- Canonical Attempt-1 verification written: `false`\n"
        "- Formal gate authorized: `false`\n\n"
        f"{value['claim_boundary']}\n"
    ).encode("utf-8")


def _failure_summary(value: dict[str, Any]) -> bytes:
    return (
        "# Incident 003 Preflight Verification Attempt 2 Failure\n\n"
        "- Status: `Failed`\n"
        f"- Failure stage: `{value['failure_stage']}`\n"
        f"- Failure code: `{value['failure_code']}`\n"
        "- Formal gate authorized: `false`\n\n"
        f"{value['claim_boundary']}\n"
    ).encode("utf-8")


def _resource_record(started: float) -> dict[str, Any]:
    return {
        "wall_seconds": float(time.monotonic() - started),
        "peak_process_rss_gb": _peak_rss_gb(),
        "api_cost_usd": 0,
        "gpu_cost_usd": 0,
        "model_forward_runs": 0,
    }


def _failure_code(stage: str, error: Exception) -> tuple[str, str]:
    if stage == "original_verifier":
        return "original_verifier_failure", type(error).__name__
    if stage == "candidate_validation":
        return "captured_candidate_invalid", type(error).__name__
    if stage == "passed_summary":
        return "passed_summary_write_failure", type(error).__name__
    if stage == "passed_publish":
        return "passed_publish_failure", type(error).__name__
    if stage == "final_state_audit":
        return "terminal_state_drift", type(error).__name__
    if stage == "final_resource_audit":
        return "terminal_resource_budget_exceeded", type(error).__name__
    if stage == "terminal_seal":
        return "terminal_success_seal_failure", type(error).__name__
    if stage == "terminal_postcheck":
        return "terminal_success_postcheck_failure", type(error).__name__
    return "recovery_contract_failure", type(error).__name__


def _failure_payload(
    config: dict[str, Any], started: float, stage: str, error: Exception, completed: list[str]
) -> dict[str, Any]:
    if stage not in FAILURE_STAGES:
        stage = "original_verifier"
    if tuple(completed) != RECOVERY_CHECK_NAMES[: len(completed)]:
        raise RuntimeError("Failure completed_checks is not an ordered recovery prefix")
    code, exception_type = _failure_code(stage, error)
    value = {
        "schema_version": SCHEMA_FAILED,
        "incident_id": INCIDENT_ID,
        "verification_attempt": VERIFICATION_ATTEMPT,
        "experiment_id": EXPERIMENT_ID,
        "replication_parent_experiment_id": PARENT_EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "model_seed": MODEL_SEED,
        "seed_contract": SEED_CONTRACT,
        "rq_id": RQ_ID,
        "scope": SCOPE,
        "status": "Failed",
        "failed_at_utc": utc_now(),
        "failure_stage": stage,
        "failure_code": code,
        "exception_type": exception_type if exception_type in {
            "ValueError", "RuntimeError", "PermissionError", "FileNotFoundError",
            "FileExistsError", "NameError", "OSError", "JSONDecodeError",
        } else "Exception",
        "completed_checks": list(completed),
        "original_artifacts": {
            name: config["predecessor"][name]
            for name in ("config", "run", "contract", "frozen_verifier")
        },
        "resources": _resource_record(started),
        "formal_gate_authorized": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    if set(value) != FAILED_KEYS or _privacy_violations(value):
        raise RuntimeError("Failure envelope construction drift")
    return value


def _seal_failure(
    config: dict[str, Any], started: float, stage: str, error: Exception, completed: list[str]
) -> dict[str, Any]:
    paths = _output_paths()
    value = _failure_payload(config, started, stage, error, completed)
    if not os.path.lexists(paths["failed"]):
        _create_json_once(paths["failed"], value)
    if not os.path.lexists(paths["failed_summary"]):
        try:
            _create_bytes_once(paths["failed_summary"], _failure_summary(value))
        except Exception:
            pass
    persisted = json.loads(_secure_read(paths["failed"], 0o644)[0].decode("utf-8"))
    if persisted != value or set(persisted) != FAILED_KEYS or _privacy_violations(persisted):
        raise ValueError("Incident 003 failure-seal persistence drift")
    if os.path.lexists(paths["failed_summary"]):
        if _secure_read(paths["failed_summary"], 0o644)[0] != _failure_summary(value):
            raise ValueError("Incident 003 failure summary drift")
    if any(os.path.lexists(path) for path in _canonical_sidecars()):
        raise ValueError("Canonical sidecar appeared during failure sealing")
    if any(
        os.path.lexists(path)
        for path in (FORMAL_CONFIG, FORMAL_PUBLIC, FORMAL_PRIVATE, SELECTION)
    ):
        raise ValueError("Formal/downstream output appeared during failure sealing")
    return value


def _claim(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    paths = _output_paths()
    implementation_payloads = {
        name: _require_record(record, 0o644)[1]
        for name, record in config["implementation"].items()
    }
    config_payload = _secure_read(config_path, 0o644)[0]
    config_record = {
        "path": _display(config_path),
        "bytes": len(config_payload),
        "sha256": _sha256(config_payload),
    }
    target_payloads = {"config": config_payload, **implementation_payloads}
    frozen_records = {
        name: {
            "path": _display(paths["frozen_sources"] / (
                "config.json" if name == "config" else Path(
                    config["implementation"][name]["path"]
                ).name
            )),
            "bytes": len(payload),
            "sha256": _sha256(payload),
        }
        for name, payload in target_payloads.items()
    }
    claim = _claim_payload(config_record, config, frozen_records)
    if (
        claim["incident_config"]["bytes"] != frozen_records["config"]["bytes"]
        or claim["incident_config"]["sha256"] != frozen_records["config"]["sha256"]
    ):
        raise RuntimeError("Incident config claim/frozen binding drift")
    _create_json_once(paths["claim"], claim)
    _create_directory_once(paths["frozen_sources"])
    for name, payload in target_payloads.items():
        target = paths["frozen_sources"] / (
            "config.json"
            if name == "config"
            else Path(config["implementation"][name]["path"]).name
        )
        _create_bytes_once(target, payload)
    _create_json_once(paths["attempt1_failure"], _attempt1_failure_payload(config))
    return claim


def _build_passed(
    config: dict[str, Any], candidate: dict[str, Any], candidate_bytes: bytes,
    summary_bytes: bytes, before: dict[str, Any], after: dict[str, Any],
    capture: _Capture, started: float,
) -> dict[str, Any]:
    resources = _resource_record(started)
    if not _runtime_resources(resources):
        raise RuntimeError("Incident 003 outer resource budget exceeded")
    rows = [{"name": name, "passed": True, "detail": None} for name in RECOVERY_CHECK_NAMES]
    value = {
        "schema_version": SCHEMA_PASSED,
        "incident_id": INCIDENT_ID,
        "verification_attempt": VERIFICATION_ATTEMPT,
        "experiment_id": EXPERIMENT_ID,
        "replication_parent_experiment_id": PARENT_EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "model_seed": MODEL_SEED,
        "seed_contract": SEED_CONTRACT,
        "rq_id": RQ_ID,
        "scope": SCOPE,
        "status": "Passed",
        "verified_at_utc": utc_now(),
        "patch_ledger": {
            "patch_surface": [
                "REPO_ROOT", "_create_bytes_once", "_assert_replication_preflight_tree"
            ],
            "repo_root_injected": True,
            "patches_restored": True,
        },
        "original_artifacts": {
            **{
                name: config["predecessor"][name]
                for name in ("config", "run", "contract", "frozen_verifier")
            },
            "source_artifacts": config["predecessor"]["source_artifacts"],
            "upstreams": config["predecessor"]["upstreams"],
            "input": config["predecessor"]["input"],
        },
        "physical_invariants": {
            "before_sha256": _canonical_digest(before),
            "after_sha256": _canonical_digest(after),
            "unchanged": before == after,
            "canonical_sidecars_absent": all(after["canonical_absent"]),
            "downstream_absent": all(after["downstream_absent"]),
        },
        "virtual_namespace": {
            "namespace_virtualized": True,
            "original_postwrite_audit": "equivalent_virtual_overlay",
            "canonical_verification_written": False,
            "writer_calls": len(capture.writer_calls),
            "unverified_tree_calls": capture.unverified_calls,
            "verified_tree_calls": capture.verified_calls,
        },
        "captured_candidate": {
            "verification": candidate,
            "verification_bytes": len(candidate_bytes),
            "verification_sha256": _sha256(candidate_bytes),
            "verification_canonical_sha256": _canonical_digest(candidate),
            "summary_bytes": len(summary_bytes),
            "summary_sha256": _sha256(summary_bytes),
        },
        "checks": rows,
        "passed_count": len(rows),
        "failed_count": 0,
        "resources": resources,
        "formal_gate_authorized": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    if (
        set(value) != PASSED_KEYS
        or before != after
        or [row["name"] for row in rows] != list(RECOVERY_CHECK_NAMES)
        or _privacy_violations(value)
    ):
        raise RuntimeError("Passed envelope construction drift")
    return value


def _postcheck_passed(value: dict[str, Any]) -> None:
    paths = _output_paths()
    expected_root = {
        "verification-attempt-2-claim.json",
        "attempt-1-failure-seal.json",
        "verification.json",
        "VERIFICATION-SUMMARY.md",
        "frozen-sources",
    }
    if {entry.name for entry in os.scandir(paths["root"])} != expected_root:
        raise ValueError("Incident 003 Passed tree inventory drift")
    if os.path.lexists(paths["failed"]) or os.path.lexists(paths["failed_summary"]):
        raise ValueError("Incident 003 failure artifact coexists with Passed tree")
    for name in ("claim", "attempt1_failure", "passed", "passed_summary"):
        _secure_read(paths[name], 0o644)
    claim = json.loads(_secure_read(paths["claim"], 0o644)[0].decode("utf-8"))
    attempt1_failure = json.loads(
        _secure_read(paths["attempt1_failure"], 0o644)[0].decode("utf-8")
    )
    if (
        set(claim) != CLAIM_KEYS
        or claim.get("formal_gate_authorized") is not False
        or claim.get("incident_config", {}).get("bytes")
        != claim.get("expected_frozen_sources", {}).get("config", {}).get("bytes")
        or claim.get("incident_config", {}).get("sha256")
        != claim.get("expected_frozen_sources", {}).get("config", {}).get("sha256")
        or set(attempt1_failure) != ATTEMPT1_FAILURE_KEYS
        or attempt1_failure.get("status") != "Failed"
        or attempt1_failure.get("failure_code") != "missing_repo_root"
        or attempt1_failure.get("formal_gate_authorized") is not False
        or _privacy_violations(claim)
        or _privacy_violations(attempt1_failure)
    ):
        raise ValueError("Incident 003 claim/failure-seal persistence drift")
    frozen_names = {"config.json", "exp-062-exp060-router-preflight-verification-attempt-2-incident-003.md", Path(__file__).name, RECOVERY_TESTS_PATH.name}
    if {entry.name for entry in os.scandir(paths["frozen_sources"])} != frozen_names:
        raise ValueError("Incident 003 frozen-source inventory drift")
    for entry in os.scandir(paths["frozen_sources"]):
        frozen_payload, _ = _secure_read(Path(entry.path), 0o644)
        name = entry.name
        if name == "config.json":
            live_payload = _secure_read(DEFAULT_CONFIG, 0o644)[0]
        else:
            source_record = next(
                record
                for record in (
                    json.loads(_secure_read(DEFAULT_CONFIG, 0o644)[0].decode("utf-8"))
                    ["implementation"].values()
                )
                if Path(record["path"]).name == name
            )
            live_payload = _require_record(source_record, 0o644)[1]
        if frozen_payload != live_payload:
            raise ValueError(f"Incident 003 frozen/live source drift: {name}")
    persisted = json.loads(_secure_read(paths["passed"], 0o644)[0].decode("utf-8"))
    if persisted != value or _secure_read(paths["passed_summary"], 0o644)[0] != _passed_summary(value):
        raise ValueError("Incident 003 Passed persistence drift")
    if any(os.path.lexists(path) for path in _canonical_sidecars()):
        raise ValueError("Canonical sidecars appeared after recovery publication")
    if any(os.path.lexists(path) for path in (FORMAL_CONFIG, FORMAL_PUBLIC, FORMAL_PRIVATE, SELECTION)):
        raise ValueError("Formal/downstream output appeared after recovery")


def _terminal_payload(
    value: dict[str, Any], terminal_state: dict[str, Any], terminal_resources: dict[str, Any]
) -> dict[str, Any]:
    paths = _output_paths()
    terminal_state_sha256 = _canonical_digest(terminal_state)
    physical = value.get("physical_invariants", {})
    terminal = {
        "schema_version": SCHEMA_TERMINAL,
        "incident_id": INCIDENT_ID,
        "verification_attempt": VERIFICATION_ATTEMPT,
        "experiment_id": EXPERIMENT_ID,
        "replication_parent_experiment_id": PARENT_EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "model_seed": MODEL_SEED,
        "seed_contract": SEED_CONTRACT,
        "rq_id": RQ_ID,
        "scope": SCOPE,
        "status": "Complete",
        "completed_at_utc": utc_now(),
        "verification": artifact(paths["passed"]),
        "summary": artifact(paths["passed_summary"]),
        "terminal_resources": terminal_resources,
        "terminal_state_sha256": terminal_state_sha256,
        "formal_gate_authorized": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    if (
        set(terminal) != TERMINAL_KEYS
        or not _runtime_resources(terminal_resources)
        or terminal_state_sha256 != physical.get("before_sha256")
        or terminal_state_sha256 != physical.get("after_sha256")
        or physical.get("unchanged") is not True
        or float(terminal_resources["wall_seconds"])
        < float(value.get("resources", {}).get("wall_seconds", math.inf))
        or float(terminal_resources["peak_process_rss_gb"])
        < float(value.get("resources", {}).get("peak_process_rss_gb", math.inf))
        or terminal["verification"]["sha256"] != _sha256(_json_bytes(value))
        or terminal["summary"]["sha256"] != _sha256(_passed_summary(value))
        or _privacy_violations(terminal)
    ):
        raise RuntimeError("Incident 003 terminal-success construction drift")
    return terminal


def _postcheck_terminal(value: dict[str, Any], terminal: dict[str, Any]) -> None:
    paths = _output_paths()
    expected_root = {
        "verification-attempt-2-claim.json",
        "attempt-1-failure-seal.json",
        "verification.json",
        "VERIFICATION-SUMMARY.md",
        "verification-attempt-2-terminal.json",
        "frozen-sources",
    }
    if {entry.name for entry in os.scandir(paths["root"])} != expected_root:
        raise ValueError("Incident 003 terminal Passed tree inventory drift")
    persisted = json.loads(_secure_read(paths["terminal"], 0o644)[0].decode("utf-8"))
    if (
        persisted != terminal
        or set(persisted) != TERMINAL_KEYS
        or persisted.get("status") != "Complete"
        or persisted.get("formal_gate_authorized") is not False
        or persisted.get("verification") != artifact(paths["passed"])
        or persisted.get("summary") != artifact(paths["passed_summary"])
        or persisted.get("terminal_state_sha256")
        != value.get("physical_invariants", {}).get("before_sha256")
        or persisted.get("terminal_state_sha256")
        != value.get("physical_invariants", {}).get("after_sha256")
        or float(persisted.get("terminal_resources", {}).get("wall_seconds", -1))
        < float(value.get("resources", {}).get("wall_seconds", math.inf))
        or float(
            persisted.get("terminal_resources", {}).get("peak_process_rss_gb", -1)
        )
        < float(value.get("resources", {}).get("peak_process_rss_gb", math.inf))
        or _secure_read(paths["passed"], 0o644)[0] != _json_bytes(value)
        or _secure_read(paths["passed_summary"], 0o644)[0] != _passed_summary(value)
        or _privacy_violations(persisted)
    ):
        raise ValueError("Incident 003 terminal-success persistence drift")
    if os.path.lexists(paths["failed"]) or os.path.lexists(paths["failed_summary"]):
        raise ValueError("Failure artifact coexists with terminal Passed tree")
    if any(os.path.lexists(path) for path in _canonical_sidecars()):
        raise ValueError("Canonical sidecar appeared before terminal success")
    if any(
        os.path.lexists(path)
        for path in (FORMAL_CONFIG, FORMAL_PUBLIC, FORMAL_PRIVATE, SELECTION)
    ):
        raise ValueError("Formal/downstream output appeared before terminal success")


def run_attempt2(config_path: Path) -> dict[str, Any]:
    started = time.monotonic()
    config_path = _config_path(config_path)
    config = load_config(config_path)
    before = _state_snapshot(config)
    if not all(before["canonical_absent"]) or not all(before["downstream_absent"]):
        raise ValueError("Pre-claim absence contract failed")
    module = _load_original_module(config)
    original_writer = module._create_bytes_once
    original_assert = module._assert_replication_preflight_tree
    capture = _Capture(module, config)
    completed: list[str] = []
    stage = "claim"
    claim_owned = False
    try:
        if os.path.lexists(ATTEMPT2_ROOT):
            raise FileExistsError("Incident 003 output root is already claimed")
        try:
            os.mkdir(ATTEMPT2_ROOT, 0o755)
        except FileExistsError:
            raise
        claim_owned = True
        if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
            raise RuntimeError("O_DIRECTORY and O_NOFOLLOW are required for claim")
        root_descriptor = os.open(
            ATTEMPT2_ROOT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
        try:
            opened_root = os.fstat(root_descriptor)
            if not stat.S_ISDIR(opened_root.st_mode):
                raise ValueError("Incident 003 claimed root is not a directory")
            os.fchmod(root_descriptor, 0o755)
            claimed_root = os.fstat(root_descriptor)
        finally:
            os.close(root_descriptor)
        root_metadata = os.lstat(ATTEMPT2_ROOT)
        if (
            stat.S_ISLNK(root_metadata.st_mode)
            or not stat.S_ISDIR(root_metadata.st_mode)
            or stat.S_IMODE(root_metadata.st_mode) != 0o755
            or stat.S_IMODE(claimed_root.st_mode) != 0o755
            or (claimed_root.st_dev, claimed_root.st_ino)
            != (root_metadata.st_dev, root_metadata.st_ino)
        ):
            raise PermissionError("Incident 003 root claim invariant failed")
        _claim(config_path, config)
        completed = list(RECOVERY_CHECK_NAMES[:6])
        stage = "original_verifier"
        module.REPO_ROOT = module.PROJECT_ROOT.parents[1]
        module._create_bytes_once = capture.writer
        module._assert_replication_preflight_tree = capture.virtual_assert
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                return_code = module.verify_replication_preflight(ORIGINAL_CONFIG)
        finally:
            module._create_bytes_once = original_writer
            module._assert_replication_preflight_tree = original_assert
            if hasattr(module, "REPO_ROOT"):
                delattr(module, "REPO_ROOT")
        completed.extend(RECOVERY_CHECK_NAMES[6:11])
        if (
            return_code != 0
            or len(capture.writer_calls) != 2
            or capture.unverified_calls != 1
            or capture.verified_calls != 1
        ):
            raise RuntimeError("Original verifier did not complete successfully")
        stage = "candidate_validation"
        candidate_bytes = capture.writer_calls[0][1]
        summary_bytes = capture.writer_calls[1][1]
        candidate = _validate_candidate(
            candidate_bytes, summary_bytes, stdout.getvalue(), stderr.getvalue(), config
        )
        after = _state_snapshot(config)
        completed.extend(RECOVERY_CHECK_NAMES[11:16])
        value = _build_passed(
            config, candidate, candidate_bytes, summary_bytes, before, after,
            capture, started,
        )
        stage = "passed_publish"
        _create_json_once(_output_paths()["passed"], value)
        stage = "passed_summary"
        _create_bytes_once(_output_paths()["passed_summary"], _passed_summary(value))
        stage = "passed_postcheck"
        _postcheck_passed(value)
        stage = "final_state_audit"
        terminal_state = _state_snapshot(config)
        if not _typed_equal(terminal_state, before) or not _typed_equal(
            terminal_state, after
        ):
            raise ValueError("Incident 003 terminal state drift")
        stage = "final_resource_audit"
        terminal_resources = _resource_record(started)
        if not _runtime_resources(terminal_resources):
            raise RuntimeError("Incident 003 terminal resource budget exceeded")
        stage = "terminal_seal"
        terminal = _terminal_payload(value, terminal_state, terminal_resources)
        _create_json_once(_output_paths()["terminal"], terminal)
        stage = "terminal_postcheck"
        _postcheck_terminal(value, terminal)
        return value
    except Exception as error:
        if not claim_owned:
            raise
        failure = _seal_failure(config, started, stage, error, completed)
        raise Attempt2TerminalFailure(failure) from None
    finally:
        if hasattr(module, "REPO_ROOT"):
            delattr(module, "REPO_ROOT")
        module._create_bytes_once = original_writer
        module._assert_replication_preflight_tree = original_assert
        module.__dict__.clear()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    if Path.cwd().resolve() != REPO_ROOT.resolve():
        raise RuntimeError(f"Incident 003 must run from repository root: {REPO_ROOT}")
    try:
        value = run_attempt2(parse_args().config)
    except Attempt2TerminalFailure as failure:
        print(
            json.dumps(
                {
                    "status": "Failed",
                    "failure_stage": failure.payload["failure_stage"],
                    "failure_code": failure.payload["failure_code"],
                },
                sort_keys=True,
            )
        )
        raise SystemExit(1)
    print(
        json.dumps(
            {
                "status": value["status"],
                "passed": value["passed_count"],
                "failed": value["failed_count"],
                "formal_gate_authorized": value["formal_gate_authorized"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
