#!/usr/bin/env python3
"""Append-only SQMA-001 verification recovery using the sealed attempt-1 run."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any


sys.dont_write_bytecode = True

import verify_sqma001_strict_base_preflight as base  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RECOVERY_CONFIG = PROJECT_ROOT / "configs" / "sqma-001-verification-recovery-attempt-2.json"
EXPECTED_AUTHORIZATION = {
    "verification_recovery": True,
    "reuse_sealed_run": True,
    "runner_reexecution": False,
    "run_mutation": False,
    "model_loading": False,
    "private_access": False,
    "training": False,
    "agent_calls": False,
    "validation_access": False,
    "test_access": False,
    "network": False,
}


def fixed_load_contract(record: dict[str, Any]) -> Any:
    path = base.verify_record(record)
    module_name = "sqma001_contract_for_verifier_recovery_attempt2"
    spec = importlib.util.spec_from_file_location(module_name, path)
    base.require(spec is not None and spec.loader is not None, "contract import spec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def validate_recovery_config(path: Path) -> dict[str, Any]:
    value = base.read_json(path)
    base.require(
        set(value)
        == {
            "schema_version",
            "incident_id",
            "verification_attempt",
            "authorization",
            "base_config",
            "sealed_run",
            "incident",
            "failed_verifier",
            "recovery_verifier",
        },
        "recovery config schema drift",
    )
    base.require(value["schema_version"] == "sqma-001-verification-recovery-v1", "recovery schema drift")
    base.require(value["incident_id"] == "SQMA-001-INCIDENT-001", "incident identity drift")
    base.require(value["verification_attempt"] == 2, "verification attempt drift")
    base.require(value["authorization"] == EXPECTED_AUTHORIZATION, "recovery authorization drift")
    for key in ("base_config", "sealed_run", "incident", "failed_verifier", "recovery_verifier"):
        base.verify_record(value[key])
    base.require(Path(value["recovery_verifier"]["path"]).name == Path(__file__).name, "recovery verifier path drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    supplied = Path(args.config).resolve()
    base.require(supplied == RECOVERY_CONFIG.resolve(), "noncanonical recovery config")
    recovery = validate_recovery_config(supplied)
    base_config_path = base.checked_path(REPO_ROOT, recovery["base_config"]["path"])
    sealed_run_path = base.checked_path(REPO_ROOT, recovery["sealed_run"]["path"])
    base.require(base.artifact(base_config_path) == recovery["base_config"], "base config artifact drift")
    base.require(base.artifact(sealed_run_path) == recovery["sealed_run"], "sealed run artifact drift")

    base.load_contract = fixed_load_contract
    verification, complete = base.verify(base_config_path)
    verification["verification_attempt"] = 2
    verification["recovery_config"] = base.artifact(supplied)
    verification["prior_failure"] = recovery["incident"]
    verification["runner_reexecuted"] = False
    verification["run_mutated"] = False
    complete["verification_attempt"] = 2
    complete["recovery_config"] = base.artifact(supplied)
    complete["prior_failure"] = recovery["incident"]
    complete["runner_reexecuted"] = False
    complete["run_mutated"] = False

    base_config = base.read_json(base_config_path)
    attempt = base.output_dir(base_config)
    base.atomic_json(attempt / "verification.json", verification)
    complete["verification"] = base.artifact(attempt / "verification.json")
    complete.pop("verification_pending_artifact")
    base.atomic_json(attempt / "complete.json", complete)
    base.require(
        sum(item.stat().st_size for item in attempt.iterdir())
        <= base_config["resources"]["maximum_public_output_bytes"],
        "total output budget exceeded",
    )
    print(
        json.dumps(
            {
                "status": "Passed",
                "experiment_id": "SQMA-001",
                "verification_attempt": 2,
                "sqma001_complete": True,
                "runner_reexecuted": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, base.VerificationError) as exc:
        print(f"SQMA-001 verification recovery Failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
