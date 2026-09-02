#!/usr/bin/env python3
"""Finalize the completed seed-44 EXP-062 attempt after Incident 004."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
from types import ModuleType
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
BASE = Path("experiments/stack-overflow-emotion-gold/oof-router")
EXPERIMENT_ID = "EXP-062"
RUN_ID = "exp-062-seed-44-router-replication"
ATTEMPT_ID = "attempt-1"
MODEL_SEED = 44
PUBLIC_ATTEMPT_REL = BASE / "runs" / RUN_ID / ATTEMPT_ID
PUBLIC_ATTEMPT = PROJECT_ROOT / PUBLIC_ATTEMPT_REL
SELECTION_REL = BASE / "runs" / RUN_ID / "selected-attempt.json"
SELECTION_PATH = PROJECT_ROOT / SELECTION_REL
CONFIG_REL = BASE / "configs/exp-062-seed-44-router-replication-router-formal-attempt-1-incident-003.json"
OOF_COMPLETION_REL = PUBLIC_ATTEMPT_REL / "oof-complete.json"
CALIBRATION_COMPLETION_REL = PUBLIC_ATTEMPT_REL / "calibration-complete.json"
ROUTER_COMPLETION_REL = PUBLIC_ATTEMPT_REL / "router/router-complete.json"
GOVERNANCE_REL = PUBLIC_ATTEMPT_REL / "router-formal-consumer-v4"
INCIDENT004_PROTOCOL_REL = Path(
    "experiments/stack-overflow-emotion-gold/protocols/"
    "exp-062-exp060-final-verification-recovery-incident-004.md"
)
INCIDENT004_WRAPPER_REL = BASE / "verify_exp060_router_v5_incident004.py"
INCIDENT004_TESTS_REL = BASE / "tests/test_exp060_router_v5_incident004.py"
FINALIZER_REL = BASE / "finalize_router_replication_incident004.py"
FINALIZER_TESTS_REL = BASE / "tests/test_finalize_router_replication_incident004.py"
CLAIM_BOUNDARY = (
    "Selects the fully verified seed-44 same-train attempt after Incident004; "
    "EXP-063 alone may form the prospective cross-seed replication claim."
)


def _canonical_relative(value: Path | str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or not relative.parts or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise ValueError(f"Non-canonical project-relative path: {value}")
    cursor = PROJECT_ROOT
    for part in relative.parts:
        cursor = cursor / part
        if os.path.lexists(cursor) and stat.S_ISLNK(os.lstat(cursor).st_mode):
            raise ValueError(f"Path traverses a symlink: {value}")
    return relative


def resolve(value: Path | str) -> Path:
    relative = _canonical_relative(value)
    path = (PROJECT_ROOT / relative).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def _read_regular(path: Path, expected_mode: int | None = None) -> bytes:
    metadata = os.lstat(path)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ValueError(f"Artifact type/link drift: {path}")
    mode = stat.S_IMODE(metadata.st_mode)
    if expected_mode is not None and mode != expected_mode:
        raise PermissionError(f"Artifact mode drift: {path}")
    if expected_mode is None and mode not in {0o600, 0o644}:
        raise PermissionError(f"Unexpected artifact mode: {path}")
    payload = path.read_bytes()
    after = os.lstat(path)
    if (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise RuntimeError(f"Artifact changed while reading: {path}")
    return payload


def artifact(value: Path | str) -> dict[str, Any]:
    relative = _canonical_relative(value)
    payload = _read_regular(resolve(relative))
    return {
        "path": str(relative),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def require_record(record: Any) -> Path:
    if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
        raise ValueError("Artifact record schema drift")
    path = resolve(record["path"])
    if artifact(Path(record["path"])) != record:
        raise ValueError(f"Artifact record drift: {record.get('path')}")
    return path


def iter_records(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if set(value) == {"path", "bytes", "sha256"}:
            yield value
        else:
            for child in value.values():
                yield from iter_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_records(child)


def load_json(relative: Path, mode: int = 0o644) -> dict[str, Any]:
    value = json.loads(_read_regular(resolve(relative), mode).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {relative}")
    return value


def _identity(value: dict[str, Any], *, experiment_id: str) -> bool:
    return (
        value.get("experiment_id") == experiment_id
        and value.get("run_id") == RUN_ID
        and value.get("attempt_id") == ATTEMPT_ID
        and type(value.get("model_seed")) is int
        and value.get("model_seed") == MODEL_SEED
        and value.get("status") == "Complete"
    )


def validate_prerequisites() -> dict[str, Any]:
    if os.path.lexists(SELECTION_PATH):
        raise FileExistsError("EXP-062 selection already exists")
    oof = load_json(OOF_COMPLETION_REL)
    calibration = load_json(CALIBRATION_COMPLETION_REL)
    router = load_json(ROUTER_COMPLETION_REL)
    if not _identity(oof, experiment_id=EXPERIMENT_ID):
        raise ValueError("OOF completion identity/status drift")
    if not _identity(calibration, experiment_id="EXP-059"):
        raise ValueError("EXP-059 completion identity/status drift")
    if not _identity(router, experiment_id=EXPERIMENT_ID):
        raise ValueError("EXP-060 completion identity/status drift")
    if (
        router.get("decision") != "Pass"
        or router.get("primary_gate_passed") is not True
        or router.get("next_gate")
        != "Finalizer must bind OOF, EXP-059, and router completion records."
    ):
        raise ValueError("EXP-060 completion decision drift")
    for completion in (oof, calibration, router):
        records = list(iter_records(completion.get("artifacts")))
        if not records:
            raise ValueError("Completion has no bound artifacts")
        for record in records:
            require_record(record)

    governance: dict[str, dict[str, Any]] = {}
    for scope, result_status in (
        ("run", "CompletedAwaitingVerification"),
        ("final", "Passed"),
        ("complete", "Complete"),
        ("completion", "Passed"),
    ):
        claim_rel = GOVERNANCE_REL / f"{scope}-claim.json"
        terminal_rel = GOVERNANCE_REL / f"{scope}-terminal.json"
        if os.path.lexists(resolve(GOVERNANCE_REL / f"{scope}-failure.json")):
            raise ValueError(f"Formal scope has a failure seal: {scope}")
        claim = load_json(claim_rel)
        terminal = load_json(terminal_rel)
        if (
            claim.get("scope") != scope
            or claim.get("status") != "Claimed"
            or claim.get("formal_scope_authorized") is not True
            or claim.get("selection_authorized") is not False
            or terminal.get("scope") != scope
            or terminal.get("status") != "Complete"
            or terminal.get("result_status") != result_status
            or terminal.get("formal_scope_authorized") is not True
            or terminal.get("selection_written") is not False
            or terminal.get("immutable_before_sha256")
            != terminal.get("immutable_after_sha256")
        ):
            raise ValueError(f"Formal governance drift: {scope}")
        if terminal.get("claim") != artifact(claim_rel):
            raise ValueError(f"Formal claim binding drift: {scope}")
        governance[scope] = artifact(terminal_rel)

    run = load_json(PUBLIC_ATTEMPT_REL / "router/run.json")
    verification = load_json(PUBLIC_ATTEMPT_REL / "router/verification.json")
    if (
        run.get("decision") != "Pass"
        or run.get("status") != "CompletedAwaitingVerification"
        or verification.get("status") != "Passed"
        or type(verification.get("failed_count")) is not int
        or verification["failed_count"] != 0
        or type(verification.get("passed_count")) is not int
        or verification["passed_count"] <= 0
    ):
        raise ValueError("EXP-060 run/verification drift")
    return {
        "oof": oof,
        "calibration": calibration,
        "router": router,
        "governance": governance,
    }


def _source_records() -> dict[str, Any]:
    return {
        "protocol": artifact(INCIDENT004_PROTOCOL_REL),
        "recovery_wrapper": artifact(INCIDENT004_WRAPPER_REL),
        "recovery_tests": artifact(INCIDENT004_TESTS_REL),
        "finalizer": artifact(FINALIZER_REL),
        "finalizer_tests": artifact(FINALIZER_TESTS_REL),
    }


def build_selection() -> dict[str, Any]:
    state = validate_prerequisites()
    router_run = load_json(PUBLIC_ATTEMPT_REL / "router/run.json")
    selected = {
        "schema_version": "exp-router-replication-selection-incident-004-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "model_seed": MODEL_SEED,
        "seed_contract": router_run["seed_contract"],
        "status": "Selected",
        "selected_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "Pass",
        "primary_gate_passed": True,
        "primary_policy": "logistic_router",
        "primary_nominal_call_rate": 0.15,
        "verification_attempt": 2,
        "completions": {
            "oof": artifact(OOF_COMPLETION_REL),
            "calibration": artifact(CALIBRATION_COMPLETION_REL),
            "router": artifact(ROUTER_COMPLETION_REL),
        },
        "formal_governance": state["governance"],
        "incident_004": _source_records(),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    validate_selection(selected, require_live_selection=False)
    return selected


def validate_selection(value: dict[str, Any], *, require_live_selection: bool) -> None:
    expected_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "model_seed",
        "seed_contract", "status", "selected_at_utc", "decision",
        "primary_gate_passed", "primary_policy", "primary_nominal_call_rate",
        "verification_attempt", "completions", "formal_governance",
        "incident_004", "claim_boundary",
    }
    if (
        set(value) != expected_keys
        or value.get("schema_version")
        != "exp-router-replication-selection-incident-004-v1"
        or value.get("experiment_id") != EXPERIMENT_ID
        or value.get("run_id") != RUN_ID
        or value.get("attempt_id") != ATTEMPT_ID
        or type(value.get("model_seed")) is not int
        or value.get("model_seed") != MODEL_SEED
        or value.get("status") != "Selected"
        or value.get("decision") != "Pass"
        or value.get("primary_gate_passed") is not True
        or value.get("primary_policy") != "logistic_router"
        or type(value.get("primary_nominal_call_rate")) is not float
        or value.get("primary_nominal_call_rate") != 0.15
        or type(value.get("verification_attempt")) is not int
        or value.get("verification_attempt") != 2
        or value.get("claim_boundary") != CLAIM_BOUNDARY
    ):
        raise ValueError("EXP-062 selection payload drift")
    datetime.fromisoformat(value["selected_at_utc"])
    expected_completions = {
        "oof": artifact(OOF_COMPLETION_REL),
        "calibration": artifact(CALIBRATION_COMPLETION_REL),
        "router": artifact(ROUTER_COMPLETION_REL),
    }
    if value.get("completions") != expected_completions:
        raise ValueError("EXP-062 completion binding drift")
    if value.get("incident_004") != _source_records():
        raise ValueError("Incident004 source binding drift")
    if not isinstance(value.get("formal_governance"), dict) or set(
        value["formal_governance"]
    ) != {"run", "final", "complete", "completion"}:
        raise ValueError("EXP-062 governance binding drift")
    for record in iter_records(value):
        require_record(record)
    if require_live_selection and load_json(SELECTION_REL) != value:
        raise ValueError("Live EXP-062 selection bytes/value drift")


def create_json_once(path: Path, value: dict[str, Any]) -> None:
    if os.path.lexists(path):
        raise FileExistsError(path)
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o644)
    try:
        os.write(descriptor, payload.encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    metadata = os.lstat(path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o644
    ):
        raise PermissionError("Selection publication mode/type drift")


def select() -> dict[str, Any]:
    value = build_selection()
    create_json_once(SELECTION_PATH, value)
    validate_selection(value, require_live_selection=True)
    return value


def verify() -> dict[str, Any]:
    value = load_json(SELECTION_REL)
    validate_selection(value, require_live_selection=True)
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("select", "verify"), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    value = select() if args.stage == "select" else verify()
    print(
        json.dumps(
            {
                "attempt_id": value["attempt_id"],
                "decision": value["decision"],
                "stage": args.stage,
                "status": value["status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

