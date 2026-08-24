#!/usr/bin/env python3
"""Finalize and verify the immutable EXP-063 synthesis selection."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
BASE = Path("experiments/stack-overflow-emotion-gold/oof-router")
RUN_ID = "exp-063-router-replication-synthesis"
ATTEMPT_ID = "attempt-1"
NAMESPACE_REL = BASE / "runs" / RUN_ID
ATTEMPT_REL = NAMESPACE_REL / ATTEMPT_ID
SELECTION_REL = NAMESPACE_REL / "selected-attempt.json"
SELECTION_PATH = PROJECT_ROOT / SELECTION_REL
RUN_REL = ATTEMPT_REL / "run.json"
SYNTHESIS_REL = ATTEMPT_REL / "replication-synthesis.json"
VERIFICATION_REL = ATTEMPT_REL / "verification.json"
SUMMARY_REL = ATTEMPT_REL / "VERIFICATION-SUMMARY.md"
DECISION_REL = Path(
    "experiments/stack-overflow-emotion-gold/protocols/dec-so-router-replication-v1.md"
)
PROTOCOL_REL = Path(
    "experiments/stack-overflow-emotion-gold/protocols/exp-063-router-replication-synthesis.md"
)
RUNNER_REL = BASE / "run_exp063_router_replication_synthesis.py"
VERIFIER_REL = BASE / "verify_exp063_router_replication_synthesis.py"
FINALIZER_REL = BASE / "finalize_exp063_router_replication_synthesis.py"
TESTS_REL = BASE / "tests/test_exp063_router_replication_synthesis.py"
SEED43_SELECTION_REL = BASE / "runs/exp-061-seed-43-router-replication/selected-attempt.json"
SEED44_SELECTION_REL = BASE / "runs/exp-062-seed-44-router-replication/selected-attempt.json"
CLAIM_BOUNDARY = (
    "Commits the verified 2/2 same-train cross-seed meta-level replication "
    "result; not independent-data validation, deployment benefit, latency, "
    "forum generality, or an emotion-mechanism claim."
)


def _path(value: Path | str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"Non-canonical path: {value}")
    path = (PROJECT_ROOT / relative).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project: {value}")
    return path


def _read(value: Path | str) -> bytes:
    path = _path(value)
    metadata = os.lstat(path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != 0o644
    ):
        raise PermissionError(f"EXP-063 finalizer artifact drift: {value}")
    return path.read_bytes()


def artifact(value: Path | str) -> dict[str, Any]:
    relative = Path(value)
    payload = _read(relative)
    return {
        "path": str(relative),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def load_json(value: Path | str) -> dict[str, Any]:
    result = json.loads(_read(value).decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"Expected JSON object: {value}")
    return result


def _expected_sources() -> dict[str, Any]:
    return {
        "decision_protocol": artifact(DECISION_REL),
        "synthesis_protocol": artifact(PROTOCOL_REL),
        "runner": artifact(RUNNER_REL),
        "verifier": artifact(VERIFIER_REL),
        "finalizer": artifact(FINALIZER_REL),
        "tests": artifact(TESTS_REL),
    }


def build_selection() -> dict[str, Any]:
    if os.path.lexists(SELECTION_PATH):
        raise FileExistsError("EXP-063 selection already exists")
    run = load_json(RUN_REL)
    synthesis = load_json(SYNTHESIS_REL)
    verification = load_json(VERIFICATION_REL)
    if (
        run.get("status") != "CompletedAwaitingVerification"
        or synthesis.get("status") != "CompletedAwaitingVerification"
        or synthesis.get("decision", {}).get("result") != "2/2 pass"
        or synthesis.get("decision", {}).get("pass_count") != 2
        or verification.get("status") != "Passed"
        or verification.get("failed_count") != 0
        or verification.get("synthesis") != artifact(SYNTHESIS_REL)
        or verification.get("run") != artifact(RUN_REL)
        or verification.get("independence", {}).get("runner_imported") is not False
    ):
        raise ValueError("EXP-063 completion/verification drift")
    return {
        "schema_version": "exp-063-router-replication-selection-v1",
        "experiment_id": "EXP-063",
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "Selected",
        "selected_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": synthesis["decision"],
        "inputs": {
            "seed43_selection": artifact(SEED43_SELECTION_REL),
            "seed44_selection": artifact(SEED44_SELECTION_REL),
        },
        "artifacts": {
            "run": artifact(RUN_REL),
            "synthesis": artifact(SYNTHESIS_REL),
            "verification": artifact(VERIFICATION_REL),
            "summary": artifact(SUMMARY_REL),
        },
        "implementation": _expected_sources(),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def validate(value: dict[str, Any], *, live: bool) -> None:
    expected_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "status",
        "selected_at_utc", "decision", "inputs", "artifacts", "implementation",
        "claim_boundary",
    }
    if (
        set(value) != expected_keys
        or value.get("schema_version") != "exp-063-router-replication-selection-v1"
        or value.get("experiment_id") != "EXP-063"
        or value.get("run_id") != RUN_ID
        or value.get("attempt_id") != ATTEMPT_ID
        or value.get("status") != "Selected"
        or value.get("decision", {}).get("result") != "2/2 pass"
        or value.get("decision", {}).get("pass_count") != 2
        or value.get("decision", {}).get("eligible_seed_count") != 2
        or value.get("inputs")
        != {
            "seed43_selection": artifact(SEED43_SELECTION_REL),
            "seed44_selection": artifact(SEED44_SELECTION_REL),
        }
        or value.get("artifacts")
        != {
            "run": artifact(RUN_REL),
            "synthesis": artifact(SYNTHESIS_REL),
            "verification": artifact(VERIFICATION_REL),
            "summary": artifact(SUMMARY_REL),
        }
        or value.get("implementation") != _expected_sources()
        or value.get("claim_boundary") != CLAIM_BOUNDARY
    ):
        raise ValueError("EXP-063 selection payload drift")
    datetime.fromisoformat(value["selected_at_utc"])
    if live and load_json(SELECTION_REL) != value:
        raise ValueError("EXP-063 live selection drift")


def _create_json_once(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o644)
    try:
        os.write(descriptor, payload.encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def select() -> dict[str, Any]:
    value = build_selection()
    validate(value, live=False)
    _create_json_once(SELECTION_PATH, value)
    validate(value, live=True)
    return value


def verify() -> dict[str, Any]:
    value = load_json(SELECTION_REL)
    validate(value, live=True)
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("select", "verify"), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    value = select() if args.stage == "select" else verify()
    print(json.dumps({"decision": value["decision"]["result"], "stage": args.stage, "status": value["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()

