#!/usr/bin/env python3
"""Independent Incident-003-aware consumer for the frozen EXP-060 v3 verifier."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import shlex
import stat
import time
from types import ModuleType
from typing import Any


V4_CONFIG_SCHEMA = "exp-router-replication-config-v4-incident-003"
V3_CONFIG_SCHEMA = "exp-router-replication-config-v3"
FORMAL_CONFIG_NAME = (
    "exp-062-seed-44-router-replication-router-formal-attempt-1-incident-003.json"
)
INCIDENT_ID = "003"
RUN_ID = "exp-062-seed-44-router-replication"
ATTEMPT_ID = "attempt-1"
MODEL_SEED = 44
RQ_ID = "RQ-S3"

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
CONFIGS_DIR = SCRIPT_DIR / "configs"
PROTOCOL_PATH = (
    PROJECT_ROOT
    / "experiments/stack-overflow-emotion-gold/protocols/exp-060-pre-qwen-deployable-router.md"
)
INCIDENT_PROTOCOL_PATH = (
    PROJECT_ROOT
    / "experiments/stack-overflow-emotion-gold/protocols/"
    "exp-062-exp060-router-formal-consumer-incident-003.md"
)
BASE_RUNNER_PATH = SCRIPT_DIR / "run_exp060_router.py"
BASE_VERIFIER_PATH = SCRIPT_DIR / "verify_exp060_router.py"
BASE_TESTS_PATH = SCRIPT_DIR / "tests/test_exp060_router.py"
V3_RUNNER_PATH = SCRIPT_DIR / "run_exp060_router_v3.py"
V3_LIVE_PATH = SCRIPT_DIR / "verify_exp060_router_v3.py"
V3_TESTS_PATH = SCRIPT_DIR / "tests/test_exp060_router_v3.py"
V4_RUNNER_PATH = SCRIPT_DIR / "run_exp060_router_v4_incident003.py"
V4_VERIFIER_PATH = Path(__file__).resolve()
V4_TESTS_PATH = SCRIPT_DIR / "tests/test_exp060_router_v4_incident003.py"

PUBLIC_ATTEMPT = SCRIPT_DIR / "runs" / RUN_ID / ATTEMPT_ID
PRIVATE_ATTEMPT = SCRIPT_DIR / "private" / RUN_ID / ATTEMPT_ID
ATTEMPT1_ROOT = PUBLIC_ATTEMPT / "router-preflight"
ATTEMPT1_FROZEN = ATTEMPT1_ROOT / "frozen-sources"
ATTEMPT2_ROOT = PUBLIC_ATTEMPT / "router-preflight-verification-attempt-2"
ATTEMPT2_FROZEN = ATTEMPT2_ROOT / "frozen-sources"
V3_FROZEN_PATH = ATTEMPT1_FROZEN / "verify_exp060_router_v3.py"
CANONICAL_ATTEMPT1_VERIFICATION = ATTEMPT1_ROOT / "verification.json"
CANONICAL_ATTEMPT1_SUMMARY = ATTEMPT1_ROOT / "VERIFICATION-SUMMARY.md"
OLD_FORMAL_CONFIG = CONFIGS_DIR / (
    "exp-062-seed-44-router-replication-router-formal-attempt-1.json"
)
SELECTION_PATH = SCRIPT_DIR / "runs" / RUN_ID / "selected-attempt.json"
GOVERNANCE_DIR = PUBLIC_ATTEMPT / "router-formal-consumer-v4"

RECOVERY_CONFIG_PATH = CONFIGS_DIR / (
    "exp-062-seed-44-router-replication-router-preflight-verification-"
    "attempt-2-incident-003.json"
)
RECOVERY_PROTOCOL_PATH = (
    PROJECT_ROOT
    / "experiments/stack-overflow-emotion-gold/protocols/"
    "exp-062-exp060-router-preflight-verification-attempt-2-incident-003.md"
)
RECOVERY_VERIFIER_PATH = SCRIPT_DIR / "verify_exp060_router_preflight_attempt2.py"
RECOVERY_TESTS_PATH = SCRIPT_DIR / "tests/test_exp060_router_preflight_attempt2.py"

V3_BYTES = 68530
V3_SHA256 = "38da93d352de49121d5035d11fa73fe4f7b349206227adc46db5be814db97651"
V3_RUNNER_SHA256 = "a443c6a7ec7c35fc91ec4acf879f5ac7abb0d654e37fd72f43add9bdfba1a4bd"
V3_TESTS_SHA256 = "5a5756f99ef6e254a4bd8535a7fa2076b40fbfdcd5a95c185f8ea67a322dac5e"
TERMINAL_STATE_SHA256 = "0d2d1ad3e46246613853edc0ec2aabedf695e8f0622194016c20bfa281f778dd"
RECOVERY_CLAIM_BOUNDARY = (
    "Incident-003 preflight verifier recovery only; namespace-virtualized output is "
    "not canonical Attempt-1 verification and does not authorize formal execution."
)
FORMAL_AUTHORIZATION_BASIS = (
    "Explicit user authorization: seed44 EXP-060 Incident 003 recovery-aware "
    "formal analysis and primary gate; selection is not authorized."
)
STAGE_ORDER = ("run", "final", "complete", "completion")
STAGE_CLAIM_KEYS = {
    "schema_version", "incident_id", "run_id", "attempt_id", "scope", "status",
    "claimed_at_utc", "config", "v3_launcher", "formal_scope_authorized",
    "selection_authorized", "claim_boundary",
}
STAGE_TERMINAL_KEYS = {
    "schema_version", "incident_id", "run_id", "attempt_id", "scope", "status",
    "completed_at_utc", "claim", "config", "v3_launcher", "result_status",
    "immutable_before_sha256", "immutable_after_sha256", "terminal_resources",
    "formal_scope_authorized", "selection_written", "claim_boundary",
}
STAGE_FAILURE_KEYS = {
    "schema_version", "incident_id", "run_id", "attempt_id", "scope", "status",
    "failed_at_utc", "claim", "failure_code", "exception_type", "resources",
    "formal_scope_authorized", "selection_written", "claim_boundary",
}

FIXED_ARTIFACTS = {
    "attempt1_config": (
        CONFIGS_DIR / "exp-062-seed-44-router-replication-router-preflight-attempt-1.json",
        13602, "2765265f4c6a62349fc2645a466f116b4c1ca5e675932c21ca510360b991b823",
    ),
    "attempt1_run": (
        ATTEMPT1_ROOT / "run.json", 12472,
        "0a230f297fa16c670359c9ad00580add30a556e11dcfa59ce7c3702804960347",
    ),
    "attempt1_contract": (
        ATTEMPT1_ROOT / "preflight-contract.json", 3957,
        "2229566b2f718a601caa8146880ee0257a567ac1c68e6e8a8eec831318890369",
    ),
    "attempt1_frozen_verifier": (
        ATTEMPT1_FROZEN / "verify_exp060_router_preflight.py", 84331,
        "31d985d37940994f8caabcb065a426d92afe710d6ecaed8a22a33511f8ef870c",
    ),
    "incident_config": (
        RECOVERY_CONFIG_PATH, 12000,
        "f2944fbf9b13d7d41b083425acdf9a9906c9ae392a0b4b970b7e4dde5016043f",
    ),
    "claim": (
        ATTEMPT2_ROOT / "verification-attempt-2-claim.json", 2568,
        "29395cd61d49693d1c6a7c66ef3e178aa0dc1174de79e5f0a11e75a2dfc86f82",
    ),
    "attempt1_failure": (
        ATTEMPT2_ROOT / "attempt-1-failure-seal.json", 2167,
        "52034bad26db2f5e7c7094a20115d0073001c0155106814f0aa1961ab0fd9897",
    ),
    "attempt2_verification": (
        ATTEMPT2_ROOT / "verification.json", 26523,
        "982dfed3e3f617b947c2bca23086ad38f819e95b80ae5368c2a4e3faf57afcb7",
    ),
    "attempt2_summary": (
        ATTEMPT2_ROOT / "VERIFICATION-SUMMARY.md", 371,
        "0ddb62c223747e143a50e0d92a498ca7ff8198db9f3eac7e8939275351cfc93a",
    ),
    "attempt2_terminal": (
        ATTEMPT2_ROOT / "verification-attempt-2-terminal.json", 1769,
        "fdced6d9b568556f4ac88ddd85eb2597bd9738104a87aa63cd3a27f9a2c7e148",
    ),
}
RECOVERY_FROZEN_EXPECTED = {
    "config": ("config.json", 12000, "f2944fbf9b13d7d41b083425acdf9a9906c9ae392a0b4b970b7e4dde5016043f"),
    "protocol": (
        "exp-062-exp060-router-preflight-verification-attempt-2-incident-003.md",
        11129, "b56001a7680a0ebca8dac27f3f2ea7a5cdbbc126a7526f40d1a3821591e984f3",
    ),
    "verifier": (
        "verify_exp060_router_preflight_attempt2.py", 72377,
        "b0858368ab2eb5c4c1428c497f36a98735fb59f94c286f090ae82bb55baa3528",
    ),
    "tests": (
        "test_exp060_router_preflight_attempt2.py", 43509,
        "5ccba4bf2eab89e2754cf7b334e1760c9083f38d3c2cc66094745619cf840c7f",
    ),
}

IMPLEMENTATION_KEYS = {
    "protocol", "runner", "verifier", "tests", "runner_launcher",
    "verifier_launcher", "launcher_tests", "incident_protocol",
    "incident_runner_launcher", "incident_verifier_launcher",
    "incident_launcher_tests",
}
PREREQUISITE_KEYS = {
    "oof_verification", "exp059_run", "exp059_verification",
    "exp059_calibration_parameters", "exp060_preflight_verification",
}
RECOVERY_KEYS = {
    "incident_id", "attempt_1", "attempt_2",
    "canonical_attempt_1_sidecars_absent", "formal_gate_authorized",
}
ATTEMPT1_KEYS = {"config", "run", "contract", "frozen_verifier", "failure_seal"}
ATTEMPT2_KEYS = {
    "incident_config", "claim", "verification", "summary", "terminal", "frozen_sources",
}
CLAIM_KEYS = {
    "schema_version", "incident_id", "verification_attempt", "experiment_id",
    "replication_parent_experiment_id", "run_id", "attempt_id", "model_seed",
    "seed_contract", "rq_id", "scope", "claimed_at_utc", "incident_config",
    "expected_frozen_sources", "formal_gate_authorized", "claim_boundary",
}
FAILURE_KEYS = {
    "schema_version", "incident_id", "verification_attempt", "experiment_id",
    "replication_parent_experiment_id", "run_id", "attempt_id", "model_seed",
    "seed_contract", "status", "failure_stage", "failure_code", "exception_type",
    "exit_code", "canonical_verification_absent", "canonical_summary_absent",
    "original_artifacts", "formal_gate_authorized", "claim_boundary",
}
PASSED_KEYS = {
    "schema_version", "incident_id", "verification_attempt", "experiment_id",
    "replication_parent_experiment_id", "run_id", "attempt_id", "model_seed",
    "seed_contract", "rq_id", "scope", "status", "verified_at_utc", "patch_ledger",
    "original_artifacts", "physical_invariants", "virtual_namespace",
    "captured_candidate", "checks", "passed_count", "failed_count", "resources",
    "formal_gate_authorized", "claim_boundary",
}
TERMINAL_KEYS = {
    "schema_version", "incident_id", "verification_attempt", "experiment_id",
    "replication_parent_experiment_id", "run_id", "attempt_id", "model_seed",
    "seed_contract", "rq_id", "scope", "status", "completed_at_utc",
    "verification", "summary", "terminal_resources", "terminal_state_sha256",
    "formal_gate_authorized", "claim_boundary",
}
ORIGINAL_KEYS = {
    "schema_version", "experiment_id", "replication_parent_experiment_id", "run_id",
    "attempt_id", "model_seed", "seed_contract", "rq_id", "scope", "verified_at_utc",
    "status", "passed_count", "failed_count", "checks", "independent",
    "runner_imported", "execution_claims", "verified_artifacts", "resources",
    "claim_boundary",
}
RECOVERY_CHECK_NAMES = (
    "recovery.incident_config", "recovery.attempt1_failure",
    "recovery.canonical_absence", "recovery.runner_seal", "recovery.contract",
    "recovery.frozen_inventory", "recovery.original_verifier_bytes",
    "recovery.repo_root_injection", "recovery.writer_capture",
    "recovery.virtual_tree_audit", "recovery.original_return",
    "recovery.original_checks_20", "recovery.no_result_claims",
    "recovery.resources_privacy", "recovery.physical_invariants",
    "recovery.downstream_absence",
)
ORIGINAL_CHECK_NAMES = (
    "verification.config", "verification.run_schema", "verification.contract_schema",
    "verification.runner_checks", "verification.upstream_chain",
    "verification.input_header_only", "verification.router_identity_calibration",
    "verification.policies_5", "verification.deployable_policy_order_3",
    "verification.formal_source_contract", "verification.frozen_sources",
    "verification.public_modes", "verification.public_privacy",
    "verification.formal_public_absent", "verification.formal_private_absent",
    "verification.completion_absent", "verification.selection_absent",
    "verification.resources.wall_seconds", "verification.resources.peak_memory_gb",
    "verification.resources.zero_cost_forward",
)
EXECUTION_CLAIMS = {
    "array_values_loaded", "real_features_constructed", "real_router_targets_constructed",
    "scaler_or_router_fitted", "router_metrics_computed", "bootstrap_computed",
    "validation_accessed", "test_accessed", "raw_text_accessed",
    "model_loaded_or_forward_run", "formal_router_training", "formal_result_computation",
}
PUBLIC_SENSITIVE_KEYS = {
    "sample_id", "sample_ids", "component_id", "component_ids", "fold_id",
    "fold_ids", "gold", "logit", "logits", "probability", "probabilities",
    "feature", "features", "feature_matrix", "target", "targets",
    "router_targets", "route_score", "route_scores", "route_mask", "route_masks",
    "prediction", "predictions", "raw_text", "text",
}


def _typed_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


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


def _stat_signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev, value.st_ino, value.st_mode, value.st_nlink, value.st_size,
        value.st_mtime_ns, value.st_ctime_ns,
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
        raise PermissionError(f"Governed file mode/type/link drift: {lexical}")
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("O_NOFOLLOW is required")
    descriptor = os.open(lexical, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(descriptor)
        if _stat_signature(opened) != _stat_signature(before):
            raise ValueError(f"File identity changed before open: {lexical}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        payload = b"".join(chunks)
        if len(payload) != opened.st_size:
            raise ValueError(f"Short governed read: {lexical}")
        after_fd = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    after = os.lstat(lexical)
    if _stat_signature(after_fd) != _stat_signature(opened) or _stat_signature(after) != _stat_signature(opened):
        raise ValueError(f"File changed during governed read: {lexical}")
    return payload, opened


def _read_descriptor(descriptor: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def _held_v3_bytes(live_path: Path, frozen_path: Path) -> bytes:
    paths = (live_path, frozen_path)
    before: list[os.stat_result] = []
    descriptors: list[int] = []
    try:
        for path in paths:
            _assert_no_symlink_components(path)
            metadata = os.lstat(path)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
                or stat.S_IMODE(metadata.st_mode) != 0o644
            ):
                raise PermissionError(f"Frozen/live v3 mode/type/link drift: {path}")
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            opened = os.fstat(descriptor)
            if _stat_signature(opened) != _stat_signature(metadata):
                os.close(descriptor)
                raise ValueError(f"Frozen/live v3 path changed before open: {path}")
            before.append(metadata)
            descriptors.append(descriptor)
        payloads = [_read_descriptor(descriptor) for descriptor in descriptors]
        for path, descriptor, expected, payload in zip(
            paths, descriptors, before, payloads
        ):
            after_fd = os.fstat(descriptor)
            after_path = os.lstat(path)
            if (
                _stat_signature(after_fd) != _stat_signature(expected)
                or _stat_signature(after_path) != _stat_signature(expected)
                or len(payload) != expected.st_size
            ):
                raise ValueError(f"Frozen/live v3 path changed while held: {path}")
        if (
            any(metadata.st_size != V3_BYTES for metadata in before)
            or any(_sha256(payload) != V3_SHA256 for payload in payloads)
            or payloads[0] != payloads[1]
        ):
            raise ValueError("Frozen/live v3 verifier bytes drift")
        return payloads[1]
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _display(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))


def _record(path: Path, mode: int = 0o644) -> dict[str, Any]:
    payload, metadata = _secure_read(path, mode)
    return {"path": _display(path), "bytes": metadata.st_size, "sha256": _sha256(payload)}


def _require_record(record: Any, mode: int) -> tuple[Path, bytes]:
    if (
        not isinstance(record, dict)
        or set(record) != {"path", "bytes", "sha256"}
        or not isinstance(record.get("path"), str)
        or not _typed_int(record.get("bytes"))
        or record["bytes"] < 0
        or not isinstance(record.get("sha256"), str)
        or len(record["sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in record["sha256"])
    ):
        raise ValueError("Artifact record schema/type drift")
    relative = Path(record["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Artifact record path drift")
    path = PROJECT_ROOT / relative
    payload, metadata = _secure_read(path, mode)
    if metadata.st_size != record["bytes"] or _sha256(payload) != record["sha256"]:
        raise ValueError(f"Artifact record content drift: {relative}")
    return path.resolve(), payload


def _fixed(name: str) -> tuple[dict[str, Any], bytes]:
    path, expected_bytes, expected_sha = FIXED_ARTIFACTS[name]
    payload, metadata = _secure_read(path, 0o644)
    if metadata.st_size != expected_bytes or _sha256(payload) != expected_sha:
        raise ValueError(f"Frozen Incident 003 artifact drift: {name}")
    return {"path": _display(path), "bytes": expected_bytes, "sha256": expected_sha}, payload


def _directory(path: Path, names: set[str]) -> None:
    metadata = os.lstat(path)
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o755
        or {entry.name for entry in os.scandir(path)} != names
    ):
        raise PermissionError(f"Governed directory inventory/mode drift: {path}")


def _snapshot_directory(path: Path, names: set[str]) -> dict[str, Any]:
    _directory(path, names)
    result: dict[str, Any] = {".": _stat_signature(os.lstat(path))}
    for entry in os.scandir(path):
        child = Path(entry.path)
        metadata = os.lstat(child)
        if stat.S_ISDIR(metadata.st_mode):
            result[entry.name] = ("dir", _stat_signature(metadata))
        else:
            payload, observed = _secure_read(child, 0o644)
            result[entry.name] = ("file", _stat_signature(observed), _sha256(payload))
    return result


def _recovery_terminal_state_snapshot(incident_config: dict[str, Any]) -> dict[str, Any]:
    _, run_payload = _fixed("attempt1_run")
    _, config_payload = _fixed("attempt1_config")
    run = json.loads(run_payload.decode())
    original_config = json.loads(config_payload.decode())
    source_artifacts = run.get("source_artifacts")
    live_implementation = original_config.get("implementation")
    if (
        not isinstance(source_artifacts, dict)
        or len(source_artifacts) != 11
        or not isinstance(live_implementation, dict)
        or len(live_implementation) != 10
    ):
        raise ValueError("Attempt-1 terminal-state inventory drift")
    frozen_names = {Path(record["path"]).name for record in source_artifacts.values()}
    input_record = incident_config["predecessor"]["input"]
    input_path, _ = _require_record(input_record, 0o600)
    return {
        "attempt1_root": _snapshot_directory(
            ATTEMPT1_ROOT, {"run.json", "preflight-contract.json", "frozen-sources"}
        ),
        "frozen_sources": _snapshot_directory(ATTEMPT1_FROZEN, frozen_names),
        "config": _record(FIXED_ARTIFACTS["attempt1_config"][0]),
        "run": _record(FIXED_ARTIFACTS["attempt1_run"][0]),
        "contract": _record(FIXED_ARTIFACTS["attempt1_contract"][0]),
        "upstreams": {
            name: _record(PROJECT_ROOT / record["path"])
            for name, record in incident_config["predecessor"]["upstreams"].items()
        },
        "live_implementation": {
            name: _record(PROJECT_ROOT / record["path"])
            for name, record in live_implementation.items()
        },
        "input": _record(input_path, 0o600),
        "input_parent": _stat_signature(os.lstat(input_path.parent)),
        "pyc": _pyc_snapshot(),
        "canonical_absent": [
            not os.path.lexists(CANONICAL_ATTEMPT1_VERIFICATION),
            not os.path.lexists(CANONICAL_ATTEMPT1_SUMMARY),
        ],
        "downstream_absent": [True, True, True, True],
    }


def _validate_recovery_transition_claim(config: dict[str, Any]) -> None:
    claim_path = GOVERNANCE_DIR / "run-claim.json"
    claim = json.loads(_secure_read(claim_path, 0o644)[0].decode())
    if (
        not isinstance(claim, dict)
        or set(claim) != STAGE_CLAIM_KEYS
        or claim.get("schema_version") != "exp-router-formal-consumer-v4-stage-claim-v1"
        or claim.get("incident_id") != INCIDENT_ID
        or claim.get("run_id") != RUN_ID
        or claim.get("attempt_id") != ATTEMPT_ID
        or claim.get("scope") != "run"
        or claim.get("status") != "Claimed"
        or claim.get("config") != _record(CONFIGS_DIR / FORMAL_CONFIG_NAME)
        or claim.get("v3_launcher") != _record(V3_RUNNER_PATH)
        or claim.get("formal_scope_authorized") is not True
        or claim.get("selection_authorized") is not False
        or claim.get("claim_boundary") != config["claim_boundary"]
        or _privacy(claim)
    ):
        raise ValueError("v4 run transition claim drift")
    _canonical_utc(claim.get("claimed_at_utc"))


def _validate_recovery_terminal_phase(
    config: dict[str, Any], incident_config: dict[str, Any]
) -> None:
    public_router = PUBLIC_ATTEMPT / "router"
    private_router = PRIVATE_ATTEMPT / "router"
    presence = (os.path.lexists(public_router), os.path.lexists(private_router))
    if presence == (False, False):
        if _canonical_digest(_recovery_terminal_state_snapshot(incident_config)) != TERMINAL_STATE_SHA256:
            raise ValueError("Incident 003 terminal state no longer reproduces")
        if os.path.lexists(GOVERNANCE_DIR):
            _validate_recovery_transition_claim(config)
        return
    if presence == (True, True):
        _validate_recovery_transition_claim(config)
        return
    raise ValueError("Formal public/private router transition is asymmetric")


def _canonical_utc(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("+00:00"):
        raise ValueError("Timestamp is not canonical UTC")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo != timezone.utc or parsed.isoformat() != value:
        raise ValueError("Timestamp is not canonical UTC")
    return parsed


def _resources(value: Any, wall: float, memory: float) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {
            "wall_seconds", "peak_process_rss_gb", "api_cost_usd", "gpu_cost_usd",
            "model_forward_runs",
        }
        and _typed_number(value["wall_seconds"])
        and 0 <= float(value["wall_seconds"]) <= wall
        and _typed_number(value["peak_process_rss_gb"])
        and 0 <= float(value["peak_process_rss_gb"]) <= memory
        and type(value["api_cost_usd"]) is int
        and value["api_cost_usd"] == 0
        and type(value["gpu_cost_usd"]) is int
        and value["gpu_cost_usd"] == 0
        and type(value["model_forward_runs"]) is int
        and value["model_forward_runs"] == 0
    )


def _privacy(value: Any, prefix: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            if key in PUBLIC_SENSITIVE_KEYS:
                violations.append(child_path)
            violations.extend(_privacy(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(_privacy(child, f"{prefix}[{index}]"))
    return violations


def _identity(value: dict[str, Any], attempt: int = 2) -> bool:
    return (
        value.get("incident_id") == INCIDENT_ID
        and type(value.get("verification_attempt")) is int
        and value.get("verification_attempt") == attempt
        and value.get("experiment_id") == "EXP-060"
        and value.get("replication_parent_experiment_id") == "EXP-062"
        and value.get("run_id") == RUN_ID
        and value.get("attempt_id") == ATTEMPT_ID
        and type(value.get("model_seed")) is int
        and value.get("model_seed") == MODEL_SEED
    )


def _checks(
    value: dict[str, Any], names: tuple[str, ...], *, null_details: bool = True
) -> None:
    rows = value.get("checks")
    if (
        not isinstance(rows, list)
        or [row.get("name") for row in rows] != list(names)
        or any(
            not isinstance(row, dict)
            or set(row) != {"name", "passed", "detail"}
            or row.get("passed") is not True
            or (null_details and row.get("detail") is not None)
            for row in rows
        )
        or not _typed_int(value.get("passed_count"))
        or value["passed_count"] != len(names)
        or not _typed_int(value.get("failed_count"))
        or value["failed_count"] != 0
    ):
        raise ValueError("Verification check inventory/count drift")


def _summary(value: dict[str, Any]) -> bytes:
    return (
        "# Incident 003 Preflight Verification Attempt 2\n\n"
        "- Status: `Passed`\n"
        f"- Recovery checks: `{value['passed_count']}/{value['passed_count']}`\n"
        "- Namespace virtualized: `true`\n"
        "- Canonical Attempt-1 verification written: `false`\n"
        "- Formal gate authorized: `false`\n\n"
        f"{value['claim_boundary']}\n"
    ).encode("utf-8")


def _original_summary(candidate: dict[str, Any]) -> bytes:
    return (
        "# Seed-44 EXP-060 No-Result Preflight Verification\n\n"
        "- Status: `Passed`\n"
        f"- Checks: `{len(candidate['checks'])}/{len(candidate['checks'])}`\n"
        "- Independent verifier imported the runner: `false`\n"
        "- Feature/target/router/metric/bootstrap computation: `false`\n"
        "- Formal router execution remains separately authorized.\n"
    ).encode("utf-8")


def _validate_recovery(config: dict[str, Any], v3: ModuleType) -> None:
    recovery = config.get("preflight_recovery")
    if (
        not isinstance(recovery, dict)
        or set(recovery) != RECOVERY_KEYS
        or recovery.get("incident_id") != INCIDENT_ID
        or recovery.get("canonical_attempt_1_sidecars_absent") is not True
        or recovery.get("formal_gate_authorized") is not False
    ):
        raise ValueError("Incident 003 recovery boundary drift")
    attempt1 = recovery.get("attempt_1")
    attempt2 = recovery.get("attempt_2")
    if not isinstance(attempt1, dict) or set(attempt1) != ATTEMPT1_KEYS:
        raise ValueError("Attempt-1 recovery inventory drift")
    if not isinstance(attempt2, dict) or set(attempt2) != ATTEMPT2_KEYS:
        raise ValueError("Attempt-2 recovery inventory drift")
    fixed = {name: _fixed(name) for name in FIXED_ARTIFACTS}
    expected_attempt1 = {
        "config": fixed["attempt1_config"][0], "run": fixed["attempt1_run"][0],
        "contract": fixed["attempt1_contract"][0],
        "frozen_verifier": fixed["attempt1_frozen_verifier"][0],
        "failure_seal": fixed["attempt1_failure"][0],
    }
    if not _typed_equal(attempt1, expected_attempt1):
        raise ValueError("Attempt-1 direct lineage drift")
    frozen_records: dict[str, dict[str, Any]] = {}
    _directory(ATTEMPT2_FROZEN, {row[0] for row in RECOVERY_FROZEN_EXPECTED.values()})
    for name, (basename, size, digest) in RECOVERY_FROZEN_EXPECTED.items():
        path = ATTEMPT2_FROZEN / basename
        payload, metadata = _secure_read(path, 0o644)
        if metadata.st_size != size or _sha256(payload) != digest:
            raise ValueError(f"Attempt-2 frozen source drift: {name}")
        frozen_records[name] = {"path": _display(path), "bytes": size, "sha256": digest}
    expected_attempt2 = {
        "incident_config": fixed["incident_config"][0], "claim": fixed["claim"][0],
        "verification": fixed["attempt2_verification"][0],
        "summary": fixed["attempt2_summary"][0],
        "terminal": fixed["attempt2_terminal"][0], "frozen_sources": frozen_records,
    }
    if not _typed_equal(attempt2, expected_attempt2):
        raise ValueError("Attempt-2 direct lineage drift")
    _directory(
        ATTEMPT2_ROOT,
        {
            "verification-attempt-2-claim.json", "attempt-1-failure-seal.json",
            "verification.json", "VERIFICATION-SUMMARY.md",
            "verification-attempt-2-terminal.json", "frozen-sources",
        },
    )
    for forbidden in (
        ATTEMPT2_ROOT / "attempt-2-failure.json", ATTEMPT2_ROOT / "FAILURE-SUMMARY.md",
        CANONICAL_ATTEMPT1_VERIFICATION, CANONICAL_ATTEMPT1_SUMMARY,
        OLD_FORMAL_CONFIG, SELECTION_PATH,
    ):
        if os.path.lexists(forbidden):
            raise FileExistsError(f"Forbidden recovery/formal artifact exists: {forbidden}")

    incident_config = json.loads(fixed["incident_config"][1].decode())
    claim = json.loads(fixed["claim"][1].decode())
    failure = json.loads(fixed["attempt1_failure"][1].decode())
    passed = json.loads(fixed["attempt2_verification"][1].decode())
    terminal = json.loads(fixed["attempt2_terminal"][1].decode())
    live_recovery = {
        "protocol": RECOVERY_PROTOCOL_PATH,
        "verifier": RECOVERY_VERIFIER_PATH,
        "tests": RECOVERY_TESTS_PATH,
    }
    if set(incident_config.get("implementation", {})) != set(live_recovery):
        raise ValueError("Incident 003 live implementation inventory drift")
    for name, live_path in live_recovery.items():
        live_record = _record(live_path)
        if (
            incident_config["implementation"][name] != live_record
            or live_record["bytes"] != frozen_records[name]["bytes"]
            or live_record["sha256"] != frozen_records[name]["sha256"]
        ):
            raise ValueError(f"Incident 003 frozen/live implementation drift: {name}")
    if (
        fixed["incident_config"][0]["bytes"] != frozen_records["config"]["bytes"]
        or fixed["incident_config"][0]["sha256"] != frozen_records["config"]["sha256"]
    ):
        raise ValueError("Incident 003 frozen/live config drift")
    for value in (claim, failure, passed, terminal):
        if (
            not _typed_equal(value.get("seed_contract"), v3.SEED_CONTRACT)
            or value.get("claim_boundary") != RECOVERY_CLAIM_BOUNDARY
        ):
            raise ValueError("Incident 003 seed/claim-boundary drift")
    if (
        set(claim) != CLAIM_KEYS
        or not _identity(claim)
        or claim.get("schema_version")
        != "exp-router-preflight-verification-incident-003-attempt-2-claim-v1"
        or claim.get("rq_id") != RQ_ID
        or claim.get("scope") != "preflight-recovery"
        or claim.get("incident_config") != fixed["incident_config"][0]
        or not _typed_equal(claim.get("expected_frozen_sources"), frozen_records)
        or claim.get("formal_gate_authorized") is not False
    ):
        raise ValueError("Incident claim drift")
    claimed_at = _canonical_utc(claim.get("claimed_at_utc"))
    if (
        set(failure) != FAILURE_KEYS
        or not _identity(failure, 1)
        or failure.get("schema_version")
        != "exp-router-preflight-verification-incident-003-attempt-1-failure-v1"
        or failure.get("status") != "Failed"
        or failure.get("failure_stage") != "child_test_preflight"
        or failure.get("failure_code") != "missing_repo_root"
        or failure.get("exception_type") != "NameError"
        or type(failure.get("exit_code")) is not int
        or failure.get("exit_code") != 1
        or failure.get("canonical_verification_absent") is not True
        or failure.get("canonical_summary_absent") is not True
        or failure.get("formal_gate_authorized") is not False
        or failure.get("original_artifacts")
        != {key: expected_attempt1[key] for key in ("config", "run", "contract", "frozen_verifier")}
    ):
        raise ValueError("Attempt-1 failure seal drift")
    if (
        set(passed) != PASSED_KEYS
        or not _identity(passed)
        or passed.get("schema_version")
        != "exp-router-preflight-verification-incident-003-attempt-2-v1"
        or passed.get("status") != "Passed"
        or passed.get("rq_id") != RQ_ID
        or passed.get("scope") != "preflight-recovery"
        or passed.get("formal_gate_authorized") is not False
    ):
        raise ValueError("Attempt-2 Passed envelope drift")
    _checks(passed, RECOVERY_CHECK_NAMES)
    verified_at = _canonical_utc(passed.get("verified_at_utc"))
    if verified_at < claimed_at:
        raise ValueError("Attempt-2 chronology drift")
    if not _typed_equal(passed.get("patch_ledger"), {
        "patch_surface": ["REPO_ROOT", "_create_bytes_once", "_assert_replication_preflight_tree"],
        "patches_restored": True, "repo_root_injected": True,
    }):
        raise ValueError("Attempt-2 patch ledger drift")
    if not _typed_equal(passed.get("virtual_namespace"), {
        "canonical_verification_written": False, "namespace_virtualized": True,
        "original_postwrite_audit": "equivalent_virtual_overlay",
        "unverified_tree_calls": 1, "verified_tree_calls": 1, "writer_calls": 2,
    }):
        raise ValueError("Attempt-2 virtual audit drift")
    if not _typed_equal(passed.get("physical_invariants"), {
        "after_sha256": TERMINAL_STATE_SHA256, "before_sha256": TERMINAL_STATE_SHA256,
        "canonical_sidecars_absent": True, "downstream_absent": True, "unchanged": True,
    }):
        raise ValueError("Attempt-2 physical invariant drift")
    _validate_recovery_terminal_phase(config, incident_config)
    if not _resources(passed.get("resources"), 300, 2.0):
        raise ValueError("Attempt-2 resources drift")

    original = passed.get("original_artifacts")
    if (
        not isinstance(original, dict)
        or set(original) != {
            "config", "run", "contract", "frozen_verifier", "source_artifacts",
            "upstreams", "input",
        }
        or original.get("config") != expected_attempt1["config"]
        or original.get("run") != expected_attempt1["run"]
        or original.get("contract") != expected_attempt1["contract"]
        or original.get("frozen_verifier") != expected_attempt1["frozen_verifier"]
        or original.get("input") != config.get("input", {}).get("paired_oof")
        or incident_config.get("predecessor", {}).get("source_artifacts")
        != original.get("source_artifacts")
        or incident_config.get("predecessor", {}).get("upstreams") != original.get("upstreams")
        or incident_config.get("predecessor", {}).get("input") != original.get("input")
    ):
        raise ValueError("Attempt-2 original lineage drift")
    expected_source_keys = {
        "config", "protocol", "preflight_runner", "preflight_verifier",
        "preflight_tests", "runner", "verifier", "tests", "runner_launcher",
        "verifier_launcher", "launcher_tests",
    }
    if set(original.get("source_artifacts", {})) != expected_source_keys:
        raise ValueError("Attempt-1 frozen-source inventory drift")
    frozen_names: set[str] = set()
    for record in original["source_artifacts"].values():
        frozen_path, _ = _require_record(record, 0o644)
        if frozen_path.parent != ATTEMPT1_FROZEN.resolve():
            raise ValueError("Attempt-1 frozen-source path drift")
        frozen_names.add(frozen_path.name)
    _directory(
        ATTEMPT1_ROOT,
        {"run.json", "preflight-contract.json", "frozen-sources"},
    )
    _directory(ATTEMPT1_FROZEN, frozen_names)
    for record in original["upstreams"].values():
        _require_record(record, 0o644)
    captured = passed.get("captured_candidate")
    if not isinstance(captured, dict) or set(captured) != {
        "verification", "verification_bytes", "verification_sha256",
        "verification_canonical_sha256", "summary_bytes", "summary_sha256",
    }:
        raise ValueError("Captured candidate inventory drift")
    candidate = captured.get("verification")
    if (
        not isinstance(candidate, dict)
        or set(candidate) != ORIGINAL_KEYS
        or candidate.get("schema_version") != "exp-router-replication-preflight-verification-v1"
        or candidate.get("experiment_id") != "EXP-060"
        or candidate.get("replication_parent_experiment_id") != "EXP-062"
        or candidate.get("run_id") != RUN_ID
        or candidate.get("attempt_id") != ATTEMPT_ID
        or type(candidate.get("model_seed")) is not int
        or candidate.get("model_seed") != MODEL_SEED
        or not _typed_equal(candidate.get("seed_contract"), v3.SEED_CONTRACT)
        or candidate.get("rq_id") != RQ_ID
        or candidate.get("status") != "Passed"
        or candidate.get("scope") != "preflight"
        or candidate.get("independent") is not True
        or candidate.get("runner_imported") is not False
    ):
        raise ValueError("Captured original verification drift")
    _checks(candidate, ORIGINAL_CHECK_NAMES, null_details=False)
    claims = candidate.get("execution_claims")
    if (
        not isinstance(claims, dict)
        or set(claims) != EXECUTION_CLAIMS
        or any(value is not False for value in claims.values())
        or not _resources(candidate.get("resources"), 300, 2.0)
    ):
        raise ValueError("Captured original claims/resources drift")
    expected_verified = {
        "config": original["config"], "run": original["run"],
        "contract": original["contract"], "input": original["input"],
        "upstreams": original["upstreams"], "frozen_sources": original["source_artifacts"],
        "formal_sources": {
            name: original["source_artifacts"][name]
            for name in (
                "protocol", "runner", "verifier", "tests", "runner_launcher",
                "verifier_launcher", "launcher_tests",
            )
        },
    }
    if not _typed_equal(candidate.get("verified_artifacts"), expected_verified):
        raise ValueError("Captured original verified-artifact drift")
    candidate_bytes = (json.dumps(candidate, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()
    original_summary = _original_summary(candidate)
    if (
        not _typed_int(captured.get("verification_bytes"))
        or captured.get("verification_bytes") != len(candidate_bytes)
        or captured.get("verification_sha256") != _sha256(candidate_bytes)
        or captured.get("verification_canonical_sha256")
        != hashlib.sha256(json.dumps(candidate, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        or not _typed_int(captured.get("summary_bytes"))
        or captured.get("summary_bytes") != len(original_summary)
        or captured.get("summary_sha256") != _sha256(original_summary)
    ):
        raise ValueError("Captured original byte/digest drift")
    if fixed["attempt2_summary"][1] != _summary(passed):
        raise ValueError("Attempt-2 deterministic summary drift")
    if (
        set(terminal) != TERMINAL_KEYS
        or not _identity(terminal)
        or terminal.get("schema_version")
        != "exp-router-preflight-verification-incident-003-attempt-2-terminal-v1"
        or terminal.get("status") != "Complete"
        or terminal.get("scope") != "preflight-recovery"
        or terminal.get("rq_id") != RQ_ID
        or terminal.get("verification") != fixed["attempt2_verification"][0]
        or terminal.get("summary") != fixed["attempt2_summary"][0]
        or terminal.get("terminal_state_sha256") != TERMINAL_STATE_SHA256
        or terminal.get("formal_gate_authorized") is not False
        or not _resources(terminal.get("terminal_resources"), 300, 2.0)
        or float(terminal["terminal_resources"]["wall_seconds"])
        < float(passed["resources"]["wall_seconds"])
        or float(terminal["terminal_resources"]["peak_process_rss_gb"])
        < float(passed["resources"]["peak_process_rss_gb"])
        or _canonical_utc(terminal.get("completed_at_utc")) < verified_at
    ):
        raise ValueError("Attempt-2 terminal seal drift")
    if any(v3._public_sensitive_paths(value) for value in (claim, failure, passed, terminal)):
        raise ValueError("Attempt-2 public privacy drift")
    if config["prerequisites"]["exp060_preflight_verification"] != fixed["attempt2_verification"][0]:
        raise ValueError("Formal prerequisite is not Attempt-2 Passed verification")
    for name in ("oof_verification", "exp059_run", "exp059_verification", "exp059_calibration_parameters"):
        if config["prerequisites"][name] != original["upstreams"][name]:
            raise ValueError(f"Formal/recovery upstream drift: {name}")
    for name in (
        "protocol", "runner", "verifier", "tests", "runner_launcher",
        "verifier_launcher", "launcher_tests",
    ):
        live = config["implementation"][name]
        frozen = candidate["verified_artifacts"]["formal_sources"][name]
        if live["bytes"] != frozen["bytes"] or live["sha256"] != frozen["sha256"]:
            raise ValueError(f"Old-seven formal lineage drift: {name}")


def _config_path(path: Path) -> tuple[Path, bytes]:
    lexical = Path(os.path.abspath(os.fspath(path)))
    if lexical.parent != CONFIGS_DIR.resolve() or lexical.name != FORMAL_CONFIG_NAME:
        raise ValueError("Incident 003 formal config path is not canonical")
    return lexical, _secure_read(lexical, 0o644)[0]


def _expected_commands(path: Path, python: str) -> dict[str, list[str]]:
    config_arg = str(path.relative_to(REPO_ROOT.resolve()))
    runner_arg = str(V4_RUNNER_PATH.relative_to(REPO_ROOT.resolve()))
    verifier_arg = str(V4_VERIFIER_PATH.relative_to(REPO_ROOT.resolve()))
    return {
        "run": [python, runner_arg, "--config", config_arg, "--stage", "run"],
        "verify_final": [python, verifier_arg, "--config", config_arg, "--scope", "final"],
        "complete": [python, runner_arg, "--config", config_arg, "--stage", "complete"],
        "verify_completion": [python, verifier_arg, "--config", config_arg, "--scope", "completion"],
    }


def validate_launch_contract(config_path: Path, v3: ModuleType) -> tuple[Path, dict[str, Any]]:
    path, payload = _config_path(config_path)
    config = json.loads(payload.decode())
    if not isinstance(config, dict) or set(config) != set(v3.FORMAL_TOP_KEYS) | {"preflight_recovery"}:
        raise ValueError("Formal v4 top-level schema drift")
    if v3._public_sensitive_paths(config):
        raise ValueError("Formal v4 public privacy drift")
    if (
        config.get("schema_version") != V4_CONFIG_SCHEMA
        or config.get("experiment_id") != v3.FORMAL_EXPERIMENT_ID
        or config.get("run_id") != RUN_ID
        or config.get("attempt_id") != ATTEMPT_ID
        or not _typed_equal(config.get("seed_contract"), v3.SEED_CONTRACT)
        or config.get("rq_id") != RQ_ID
        or config.get("tier") != "Major system experiment"
        or config.get("stage") != v3.FORMAL_STAGE
        or config.get("registered_at") != "2026-08-24"
        or not _typed_equal(config.get("outputs"), v3._expected_outputs())
        or config.get("claim_boundary") != v3.FORMAL_CLAIM_BOUNDARY
        or not _typed_equal(config.get("resources"), v3.FORMAL_RESOURCE_CONTRACT)
    ):
        raise ValueError("Formal v4 identity/resource/path drift")
    if os.path.lexists(SELECTION_PATH):
        raise FileExistsError("Final selection already exists")
    authorization = config.get("authorization")
    if not isinstance(authorization, dict) or set(authorization) != {
        "basis", "model_seed", "formal_router_training", "formal_result_computation",
        "validation_access", "test_access", "model_loading_or_forward", "raw_text_access",
    }:
        raise ValueError("Formal v4 authorization inventory drift")
    if (
        authorization.get("basis") != FORMAL_AUTHORIZATION_BASIS
        or type(authorization.get("model_seed")) is not int
        or authorization["model_seed"] != MODEL_SEED
        or authorization["formal_router_training"] is not True
        or authorization["formal_result_computation"] is not True
        or any(
            authorization[name] is not False
            for name in ("validation_access", "test_access", "model_loading_or_forward", "raw_text_access")
        )
    ):
        raise PermissionError("Formal v4 authorization drift")
    python = config.get("runtime", {}).get("python_executable")
    expected_commands = _expected_commands(path, python) if isinstance(python, str) and Path(python).is_absolute() else None
    if (
        expected_commands is None
        or not isinstance(config.get("commands"), dict)
        or set(config["commands"]) != set(expected_commands)
        or any(shlex.split(str(config["commands"][name])) != expected for name, expected in expected_commands.items())
    ):
        raise ValueError("Formal v4 command contract drift")
    implementation = config.get("implementation")
    if not isinstance(implementation, dict) or set(implementation) != IMPLEMENTATION_KEYS:
        raise ValueError("Formal v4 implementation inventory is not exact11")
    paths = {
        "protocol": PROTOCOL_PATH, "runner": BASE_RUNNER_PATH,
        "verifier": BASE_VERIFIER_PATH, "tests": BASE_TESTS_PATH,
        "runner_launcher": V3_RUNNER_PATH, "verifier_launcher": V3_LIVE_PATH,
        "launcher_tests": V3_TESTS_PATH, "incident_protocol": INCIDENT_PROTOCOL_PATH,
        "incident_runner_launcher": V4_RUNNER_PATH,
        "incident_verifier_launcher": V4_VERIFIER_PATH,
        "incident_launcher_tests": V4_TESTS_PATH,
    }
    basenames: set[str] = set()
    for name, expected in paths.items():
        observed, _ = _require_record(implementation[name], 0o644)
        if observed != expected.resolve():
            raise ValueError(f"Formal v4 implementation path drift: {name}")
        basenames.add(observed.name)
    if len(basenames) != 11:
        raise ValueError("Formal v4 implementation basenames are not unique")
    expected_hashes = {
        "runner": v3.BASE_RUNNER_SHA256, "verifier": v3.BASE_VERIFIER_SHA256,
        "tests": v3.BASE_TESTS_SHA256, "runner_launcher": V3_RUNNER_SHA256,
        "verifier_launcher": V3_SHA256, "launcher_tests": V3_TESTS_SHA256,
    }
    for name, digest in expected_hashes.items():
        if implementation[name]["sha256"] != digest:
            raise ValueError(f"Frozen base/v3 hash drift: {name}")
    prerequisites = config.get("prerequisites")
    if not isinstance(prerequisites, dict) or set(prerequisites) != PREREQUISITE_KEYS:
        raise ValueError("Formal v4 prerequisite inventory is not exact5")
    prerequisite_paths = {
        "oof_verification": PUBLIC_ATTEMPT / "verification.json",
        "exp059_run": PUBLIC_ATTEMPT / "calibration/run.json",
        "exp059_verification": PUBLIC_ATTEMPT / "calibration/verification.json",
        "exp059_calibration_parameters": PUBLIC_ATTEMPT / "calibration/calibration-parameters.json",
        "exp060_preflight_verification": ATTEMPT2_ROOT / "verification.json",
    }
    for name, expected in prerequisite_paths.items():
        observed, _ = _require_record(prerequisites[name], 0o644)
        if observed != expected.resolve():
            raise ValueError(f"Formal v4 prerequisite path drift: {name}")
    if set(config.get("input", {})) != {"paired_oof"}:
        raise ValueError("Formal v4 input inventory drift")
    paired, _ = _require_record(config["input"]["paired_oof"], 0o600)
    if paired != (PRIVATE_ATTEMPT / "paired-oof.npz").resolve():
        raise ValueError("Formal v4 paired OOF path drift")
    paired_parent = os.lstat(paired.parent)
    if (
        stat.S_ISLNK(paired_parent.st_mode)
        or not stat.S_ISDIR(paired_parent.st_mode)
        or stat.S_IMODE(paired_parent.st_mode) != 0o700
    ):
        raise PermissionError("Formal paired OOF parent mode/type drift")
    sections = {
        "provenance": v3.EXPECTED_PROVENANCE, "path_bases": v3.EXPECTED_PATH_BASES,
        "artifact_contract": v3.FORMAL_ARTIFACT_CONTRACT, "runtime": v3.EXPECTED_RUNTIME,
        "data": v3.EXPECTED_DATA, "cross_fitting": v3.EXPECTED_CROSS_FITTING,
        "thresholds": v3.EXPECTED_THRESHOLDS, "target_contract": v3.EXPECTED_TARGET_CONTRACT,
        "feature_contract": v3.EXPECTED_FEATURE_CONTRACT, "router": v3.EXPECTED_ROUTER,
        "call_rates": v3.EXPECTED_CALL_RATES, "gate": v3.EXPECTED_GATE,
        "risk_coverage": v3.EXPECTED_RISK_COVERAGE, "bootstrap": v3.EXPECTED_BOOTSTRAP,
    }
    for name, expected in sections.items():
        if not _typed_equal(config.get(name), expected):
            raise ValueError(f"Formal v4 governance/science drift: {name}")
    if (
        tuple(config["router"]["policies"]) != tuple(v3.POLICIES)
        or tuple(config["router"]["deployable_policy_order"]) != tuple(v3.DEPLOYABLE_POLICIES)
    ):
        raise ValueError("Formal v4 policy inventory/order drift")
    _validate_recovery(config, v3)
    return path, config


def _load_verified_v3() -> ModuleType:
    frozen = _held_v3_bytes(V3_LIVE_PATH, V3_FROZEN_PATH)
    module = ModuleType("_exp060_router_v4_incident003_frozen_v3_verifier")
    module.__file__ = str(V3_LIVE_PATH)
    module.__package__ = ""
    exec(compile(frozen.decode(), str(V3_LIVE_PATH), "exec", dont_inherit=True), module.__dict__)
    if module.FORMAL_CONFIG_SCHEMA != V3_CONFIG_SCHEMA or not callable(module.validate_launch_contract):
        raise ValueError("Frozen v3 verifier interface drift")
    return module


def _pyc_snapshot() -> dict[str, tuple[int, ...]]:
    result: dict[str, tuple[int, ...]] = {}
    for directory in (SCRIPT_DIR / "__pycache__", SCRIPT_DIR / "tests/__pycache__"):
        if not os.path.lexists(directory):
            continue
        metadata = os.lstat(directory)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("Python cache directory type drift")
        for entry in os.scandir(directory):
            child = Path(entry.path)
            child_metadata = os.lstat(child)
            if stat.S_ISREG(child_metadata.st_mode):
                result[_display(child)] = _stat_signature(child_metadata)
    return result


def _immutable_snapshot(path: Path, config: dict[str, Any]) -> dict[str, Any]:
    config_payload, config_metadata = _secure_read(path, 0o644)
    rows: list[tuple[str, dict[str, Any], int]] = []
    rows.extend((f"implementation.{name}", record, 0o644) for name, record in config["implementation"].items())
    rows.extend((f"prerequisites.{name}", record, 0o644) for name, record in config["prerequisites"].items())
    rows.append(("input", config["input"]["paired_oof"], 0o600))
    rows.extend((f"attempt1.{name}", record, 0o644) for name, record in config["preflight_recovery"]["attempt_1"].items())
    for name, record in config["preflight_recovery"]["attempt_2"].items():
        if name == "frozen_sources":
            rows.extend((f"frozen.{child}", child_record, 0o644) for child, child_record in record.items())
        else:
            rows.append((f"attempt2.{name}", record, 0o644))
    observed: dict[str, Any] = {
        "config": (_stat_signature(config_metadata), _sha256(config_payload))
    }
    for name, record, mode in rows:
        artifact_path, payload = _require_record(record, mode)
        observed[name] = (record, _stat_signature(os.lstat(artifact_path)), _sha256(payload))
    observed["pyc"] = _pyc_snapshot()
    observed["absent"] = (
        not os.path.lexists(CANONICAL_ATTEMPT1_VERIFICATION),
        not os.path.lexists(CANONICAL_ATTEMPT1_SUMMARY),
        not os.path.lexists(OLD_FORMAL_CONFIG),
        not os.path.lexists(SELECTION_PATH),
    )
    return observed


def _stage_state(scope: str, before: bool) -> tuple[bool, ...]:
    public_router = PUBLIC_ATTEMPT / "router"
    private_router = PRIVATE_ATTEMPT / "router"
    verification = public_router / "verification.json"
    summary = public_router / "VERIFICATION-SUMMARY.md"
    completion = public_router / "router-complete.json"
    observed = tuple(os.path.lexists(path) for path in (public_router, private_router, verification, summary, completion, SELECTION_PATH))
    expected = {
        ("final", True): (True, True, False, False, False, False),
        ("final", False): (True, True, True, True, False, False),
        ("completion", True): (True, True, True, True, True, False),
        ("completion", False): (True, True, True, True, True, False),
    }[(scope, before)]
    if observed != expected:
        raise ValueError(f"Formal v4 verifier stage-state drift for {scope}: {observed}")
    return observed


def _peak_rss_gb() -> float:
    divisor = 1e9 if platform.system() == "Darwin" else 1e9 / 1024
    return max(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / divisor,
        resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / divisor,
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False
        )
        + "\n"
    ).encode()


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _create_directory_once(path: Path) -> None:
    if os.path.lexists(path):
        raise FileExistsError(f"Governance directory is append-only: {path}")
    _assert_no_symlink_components(path.parent)
    parent = os.lstat(path.parent)
    if (
        stat.S_ISLNK(parent.st_mode)
        or not stat.S_ISDIR(parent.st_mode)
        or stat.S_IMODE(parent.st_mode) != 0o755
    ):
        raise PermissionError("Governance namespace parent mode/type drift")
    os.mkdir(path, 0o755)
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fchmod(descriptor, 0o755)
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o755:
            raise PermissionError("Governance directory mode/type drift after creation")
    finally:
        os.close(descriptor)


def _create_json_once(path: Path, value: dict[str, Any]) -> None:
    if os.path.lexists(path):
        raise FileExistsError(f"Governance sidecar is append-only: {path}")
    parent = os.lstat(path.parent)
    if (
        stat.S_ISLNK(parent.st_mode)
        or not stat.S_ISDIR(parent.st_mode)
        or stat.S_IMODE(parent.st_mode) != 0o755
    ):
        raise PermissionError("Governance parent mode/type drift")
    payload = _json_bytes(value)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o644,
    )
    try:
        os.fchmod(descriptor, 0o644)
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise OSError("Short governance write")
            offset += written
        os.fsync(descriptor)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) != 0o644
            or opened.st_size != len(payload)
        ):
            raise PermissionError("Governance sidecar post-write mode/type/link drift")
    finally:
        os.close(descriptor)
    persisted, metadata = _secure_read(path, 0o644)
    if persisted != payload or metadata.st_size != len(payload):
        raise ValueError("Governance sidecar persistence drift")


def _stage_path(scope: str, kind: str) -> Path:
    if scope not in STAGE_ORDER or kind not in {"claim", "terminal", "failure"}:
        raise ValueError("Unexpected governance scope/kind")
    return GOVERNANCE_DIR / f"{scope}-{kind}.json"


def _stage_v3_path(scope: str) -> Path:
    return V3_RUNNER_PATH if scope in {"run", "complete"} else V3_LIVE_PATH


def _expected_result_status(scope: str) -> str:
    return {
        "run": "CompletedAwaitingVerification",
        "final": "Passed",
        "complete": "Complete",
        "completion": "Passed",
    }[scope]


def _resource_value(started: float) -> dict[str, Any]:
    return {
        "wall_seconds": time.monotonic() - started,
        "peak_process_rss_gb": _peak_rss_gb(),
        "api_cost_usd": 0,
        "gpu_cost_usd": 0,
        "model_forward_runs": 0,
    }


def _validate_scope_result(scope: str, result: Any) -> None:
    if not isinstance(result, dict) or result.get("status") != _expected_result_status(scope):
        raise RuntimeError(f"v4 {scope} returned a non-success status")
    if scope in {"final", "completion"}:
        rows = result.get("checks")
        if (
            not _typed_int(result.get("passed_count"))
            or result["passed_count"] <= 0
            or not _typed_int(result.get("failed_count"))
            or result["failed_count"] != 0
            or not isinstance(rows, list)
            or len(rows) != result["passed_count"]
            or any(
                not isinstance(row, dict)
                or set(row) != {"name", "passed", "detail"}
                or not isinstance(row["name"], str)
                or row["passed"] is not True
                for row in rows
            )
        ):
            raise RuntimeError(f"v4 {scope} verification result is not fully Passed")


def _validate_completed_stage(scope: str, config_path: Path, config: dict[str, Any]) -> None:
    claim_path = _stage_path(scope, "claim")
    terminal_path = _stage_path(scope, "terminal")
    claim = json.loads(_secure_read(claim_path, 0o644)[0].decode())
    terminal = json.loads(_secure_read(terminal_path, 0o644)[0].decode())
    expected_config = _record(config_path)
    expected_v3 = _record(_stage_v3_path(scope))
    current_immutable_digest = _canonical_digest(_immutable_snapshot(config_path, config))
    if (
        not isinstance(claim, dict)
        or set(claim) != STAGE_CLAIM_KEYS
        or claim.get("schema_version") != "exp-router-formal-consumer-v4-stage-claim-v1"
        or claim.get("incident_id") != INCIDENT_ID
        or claim.get("run_id") != RUN_ID
        or claim.get("attempt_id") != ATTEMPT_ID
        or claim.get("scope") != scope
        or claim.get("status") != "Claimed"
        or claim.get("config") != expected_config
        or claim.get("v3_launcher") != expected_v3
        or claim.get("formal_scope_authorized") is not True
        or claim.get("selection_authorized") is not False
        or claim.get("claim_boundary") != config["claim_boundary"]
    ):
        raise ValueError(f"v4 {scope} claim seal drift")
    claimed_at = _canonical_utc(claim.get("claimed_at_utc"))
    if (
        not isinstance(terminal, dict)
        or set(terminal) != STAGE_TERMINAL_KEYS
        or terminal.get("schema_version") != "exp-router-formal-consumer-v4-stage-terminal-v1"
        or terminal.get("incident_id") != INCIDENT_ID
        or terminal.get("run_id") != RUN_ID
        or terminal.get("attempt_id") != ATTEMPT_ID
        or terminal.get("scope") != scope
        or terminal.get("status") != "Complete"
        or terminal.get("claim") != _record(claim_path)
        or terminal.get("config") != expected_config
        or terminal.get("v3_launcher") != expected_v3
        or terminal.get("result_status") != _expected_result_status(scope)
        or terminal.get("immutable_before_sha256")
        != terminal.get("immutable_after_sha256")
        or not isinstance(terminal.get("immutable_before_sha256"), str)
        or len(terminal["immutable_before_sha256"]) != 64
        or any(
            character not in "0123456789abcdef"
            for character in terminal["immutable_before_sha256"]
        )
        or terminal.get("immutable_before_sha256") != current_immutable_digest
        or not _resources(terminal.get("terminal_resources"), 1800, 4.0)
        or terminal.get("formal_scope_authorized") is not True
        or terminal.get("selection_written") is not False
        or terminal.get("claim_boundary") != config["claim_boundary"]
    ):
        raise ValueError(f"v4 {scope} terminal seal drift")
    if _canonical_utc(terminal.get("completed_at_utc")) < claimed_at:
        raise ValueError(f"v4 {scope} stage chronology drift")
    if _privacy(claim) or _privacy(terminal):
        raise ValueError(f"v4 {scope} governance privacy drift")


def _governance_precheck(scope: str, config_path: Path, config: dict[str, Any]) -> None:
    index = STAGE_ORDER.index(scope)
    if index == 0:
        if os.path.lexists(GOVERNANCE_DIR):
            raise FileExistsError("v4 formal governance namespace is already claimed")
        return
    expected: set[str] = set()
    for previous in STAGE_ORDER[:index]:
        expected.update({f"{previous}-claim.json", f"{previous}-terminal.json"})
    _directory(GOVERNANCE_DIR, expected)
    for previous in STAGE_ORDER[:index]:
        _validate_completed_stage(previous, config_path, config)
    for kind in ("claim", "terminal", "failure"):
        if os.path.lexists(_stage_path(scope, kind)):
            raise FileExistsError(f"v4 {scope} scope is already terminal or claimed")


def _governance_manifest_through(scope: str) -> None:
    expected: set[str] = set()
    for stage in STAGE_ORDER[: STAGE_ORDER.index(scope) + 1]:
        expected.update({f"{stage}-claim.json", f"{stage}-terminal.json"})
    _directory(GOVERNANCE_DIR, expected)


def _claim_scope(scope: str, config_path: Path, config: dict[str, Any]) -> Path:
    if scope == "run":
        _create_directory_once(GOVERNANCE_DIR)
    claim_path = _stage_path(scope, "claim")
    claim = {
        "schema_version": "exp-router-formal-consumer-v4-stage-claim-v1",
        "incident_id": INCIDENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "scope": scope,
        "status": "Claimed",
        "claimed_at_utc": _utc_now(),
        "config": _record(config_path),
        "v3_launcher": _record(_stage_v3_path(scope)),
        "formal_scope_authorized": True,
        "selection_authorized": False,
        "claim_boundary": config["claim_boundary"],
    }
    if set(claim) != STAGE_CLAIM_KEYS or _privacy(claim):
        raise RuntimeError("v4 stage claim construction drift")
    _create_json_once(claim_path, claim)
    return claim_path


def _seal_scope_success(
    scope: str,
    config_path: Path,
    config: dict[str, Any],
    claim_path: Path,
    before: dict[str, Any],
    after: dict[str, Any],
    resources: dict[str, Any],
) -> None:
    value = {
        "schema_version": "exp-router-formal-consumer-v4-stage-terminal-v1",
        "incident_id": INCIDENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "scope": scope,
        "status": "Complete",
        "completed_at_utc": _utc_now(),
        "claim": _record(claim_path),
        "config": _record(config_path),
        "v3_launcher": _record(_stage_v3_path(scope)),
        "result_status": _expected_result_status(scope),
        "immutable_before_sha256": _canonical_digest(before),
        "immutable_after_sha256": _canonical_digest(after),
        "terminal_resources": resources,
        "formal_scope_authorized": True,
        "selection_written": False,
        "claim_boundary": config["claim_boundary"],
    }
    if (
        set(value) != STAGE_TERMINAL_KEYS
        or value["immutable_before_sha256"] != value["immutable_after_sha256"]
        or not _resources(resources, 1800, 4.0)
        or _privacy(value)
    ):
        raise RuntimeError("v4 stage terminal construction drift")
    _create_json_once(_stage_path(scope, "terminal"), value)


def _seal_scope_failure(scope: str, claim_path: Path, error: Exception, started: float) -> None:
    exception_type = type(error).__name__
    if exception_type not in {"ValueError", "PermissionError", "FileExistsError", "RuntimeError"}:
        exception_type = "Exception"
    value = {
        "schema_version": "exp-router-formal-consumer-v4-stage-failure-v1",
        "incident_id": INCIDENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "scope": scope,
        "status": "Failed",
        "failed_at_utc": _utc_now(),
        "claim": _record(claim_path),
        "failure_code": "governed_scope_failure",
        "exception_type": exception_type,
        "resources": _resource_value(started),
        "formal_scope_authorized": True,
        "selection_written": False,
        "claim_boundary": "Formal scope failed or remained incomplete; retry and next scope are forbidden.",
    }
    if set(value) != STAGE_FAILURE_KEYS or _privacy(value):
        raise RuntimeError("v4 stage failure construction drift")
    _create_json_once(_stage_path(scope, "failure"), value)


def execute(config_path: Path, scope: str) -> dict[str, Any]:
    if scope not in {"final", "completion"}:
        raise ValueError("Unexpected v4 verifier scope")
    started = time.monotonic()
    v3 = _load_verified_v3()
    canonical, config = validate_launch_contract(config_path, v3)
    before_snapshot = _immutable_snapshot(canonical, config)
    _stage_state(scope, True)
    _governance_precheck(scope, canonical, config)
    claim_path = _claim_scope(scope, canonical, config)
    original_schema = v3.FORMAL_CONFIG_SCHEMA
    original_validator = v3.validate_launch_contract
    adapter_calls = 0
    execute_calls = 0

    def adapter(path: Path) -> tuple[Path, dict[str, Any]]:
        nonlocal adapter_calls
        adapter_calls += 1
        return validate_launch_contract(path, v3)

    try:
        try:
            v3.FORMAL_CONFIG_SCHEMA = V4_CONFIG_SCHEMA
            v3.validate_launch_contract = adapter
            execute_calls += 1
            result = v3.execute(canonical, scope)
        finally:
            v3.FORMAL_CONFIG_SCHEMA = original_schema
            v3.validate_launch_contract = original_validator
        if (
            execute_calls != 1
            or adapter_calls != 2
            or v3.FORMAL_CONFIG_SCHEMA != original_schema
            or v3.validate_launch_contract is not original_validator
        ):
            raise RuntimeError("v4 verifier exact-two patch/call/restore drift")
        _validate_scope_result(scope, result)
        after_snapshot = _immutable_snapshot(canonical, config)
        if after_snapshot != before_snapshot:
            raise RuntimeError("Immutable Incident/upstream/private state changed during verification")
        _stage_state(scope, False)
        resources = _resource_value(started)
        if not _resources(resources, 1800, 4.0):
            raise RuntimeError(
                f"v4 outer verifier budget exceeded: wall={resources['wall_seconds']}, "
                f"rss={resources['peak_process_rss_gb']}"
            )
        _seal_scope_success(
            scope, canonical, config, claim_path, before_snapshot, after_snapshot, resources
        )
        _governance_manifest_through(scope)
        _validate_completed_stage(scope, canonical, config)
        terminal_resources = _resource_value(started)
        if not _resources(terminal_resources, 1800, 4.0):
            raise RuntimeError("v4 verifier terminal publication exceeded its outer budget")
        return result
    except Exception as error:
        try:
            _seal_scope_failure(scope, claim_path, error, started)
        except Exception as seal_error:
            raise RuntimeError("v4 verifier failed and its failure seal could not be written") from seal_error
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--scope", choices=("final", "completion"), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = execute(args.config, args.scope)
    if result.get("status") != "Passed":
        raise SystemExit(1)
    print(json.dumps({"status": result.get("status"), "scope": args.scope}, sort_keys=True))


if __name__ == "__main__":
    main()
