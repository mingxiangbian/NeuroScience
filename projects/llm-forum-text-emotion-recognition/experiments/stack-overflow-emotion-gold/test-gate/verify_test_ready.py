#!/usr/bin/env python3
"""Verify EXP-056 TEST-READY without opening either sealed test file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any

from test_gate_common import (
    LABELS,
    artifact,
    atomic_json,
    load_json,
    path_is_gitignored,
    require_artifact,
    require_tree,
    resolve_project,
    utc_now,
)


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONTRACT = SCRIPT_DIR / "configs" / "exp-056-test-ready.json"
DEFAULT_OUTPUT = SCRIPT_DIR / "preflight" / "exp-056-test-ready-verification-v1.json"
EXPECTED_ORDER = [f"m{family}-seed-{seed}" for family in range(1, 5) for seed in (42, 43, 44)]
EXPECTED_THRESHOLDS = {
    "m1-seed-42": 0.25, "m1-seed-43": 0.30, "m1-seed-44": 0.50,
    "m2-seed-42": 0.25, "m2-seed-43": 0.20, "m2-seed-44": 0.25,
    "m3-seed-42": 0.40, "m3-seed-43": 0.35, "m3-seed-44": 0.25,
    "m4-seed-42": None, "m4-seed-43": None, "m4-seed-44": None,
}
EXPECTED_EPOCHS = {
    "m1-seed-42": 4, "m1-seed-43": 4, "m1-seed-44": 5,
    **{f"m{family}-seed-{seed}": 2 for family in (2, 3, 4) for seed in (42, 43, 44)},
}


def verify(contract_path: Path, output_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    contract = load_json(contract_path)
    check("schema", contract.get("schema_version") == "exp-056-test-ready-contract-v1")
    check("experiment", contract.get("experiment_id") == "EXP-056")
    check("status", contract.get("status") == "Frozen TEST-READY; test access not authorized")
    check("labels", contract.get("labels") == list(LABELS))
    check("unit_order", contract.get("unit_order") == EXPECTED_ORDER)
    check("unit_count", len(contract.get("units", [])) == 12)

    for name, record in contract.get("implementation", {}).items():
        try:
            require_artifact(record)
            check(f"implementation:{name}", True)
        except Exception as error:  # verifier must retain every failed gate
            check(f"implementation:{name}", False, str(error))

    for name, record in contract.get("models", {}).items():
        if not name.endswith("_manifest"):
            continue
        try:
            require_artifact(record)
            check(f"model:{name}", True)
        except Exception as error:
            check(f"model:{name}", False, str(error))

    for family in ("m1", "m2", "m3", "m4"):
        records = contract.get("upstream", {}).get(family, {})
        try:
            require_artifact(records["aggregate"])
            verification = load_json(require_artifact(records["verification"]))
            check(f"upstream:{family}", verification.get("status") == "Passed")
        except Exception as error:
            check(f"upstream:{family}", False, str(error))
    try:
        exp055 = contract["upstream"]["exp055_validation_error_analysis"]
        verification = load_json(require_artifact(exp055["verification"]))
        check("upstream:exp055", verification.get("status") == "Passed")
        check(
            "exp055_excluded_from_test",
            exp055.get("test_scope") == "excluded_non_deployable_oracle_and_no_oof_router_gate",
        )
    except Exception as error:
        check("upstream:exp055", False, str(error))

    for unit in contract.get("units", []):
        unit_id = unit.get("unit_id", "unknown")
        check(f"{unit_id}:threshold", unit.get("shared_threshold") == EXPECTED_THRESHOLDS.get(unit_id))
        check(f"{unit_id}:epoch", unit.get("selected_epoch") == EXPECTED_EPOCHS.get(unit_id))
        try:
            run = load_json(require_artifact(unit["source_run"]))
            check(
                f"{unit_id}:source_run",
                run.get("status") == "Completed" and run.get("test_split_accessed") is False,
            )
            if unit["family"] == "m1":
                require_tree(unit["selected_checkpoint"])
            elif unit["family"] == "m2":
                require_artifact(unit["selected_head"])
            elif unit["family"] == "m3":
                require_artifact(unit["selected_adapter"])
                require_artifact(unit["selected_head"])
            else:
                require_artifact(unit["selected_adapter"])
            check(f"{unit_id}:selected_artifacts", True)
        except Exception as error:
            check(f"{unit_id}:selected_artifacts", False, str(error))

    data = contract.get("data", {})
    check("data_protocol", data.get("protocol_id") == "DATA-SO-TASK-V1")
    check("test_rows", data.get("test_rows") == 720)
    check("freeze_did_not_open_inputs", data.get("test_inputs_opened_during_freeze") is False)
    check("freeze_did_not_open_labels", data.get("test_labels_opened_during_freeze") is False)
    for name in ("test_inputs", "test_labels"):
        record = data.get(name, {})
        path = resolve_project(record["path"])
        # Metadata-only gate: intentionally no sha256_file() and no file open().
        passed = path.is_file() and path.stat().st_size == int(record["bytes"])
        check(f"sealed_metadata_only:{name}", passed, {"bytes": path.stat().st_size if path.is_file() else None})

    execution = contract.get("execution", {})
    authorization_path = resolve_project(execution["authorization"]["path"])
    check("authorization_absent", not authorization_path.exists())
    public_output = resolve_project(execution["public_output_dir"])
    private_output = resolve_project(execution["private_output_dir"])
    check("public_formal_output_absent", not public_output.exists())
    check("private_formal_output_absent", not private_output.exists())
    check("private_output_gitignored", path_is_gitignored(private_output))
    check("formal_unit_scope", set(unit["family"] for unit in contract["units"]) == {"m1", "m2", "m3", "m4"})
    check("no_test_router_or_oracle", all(unit["family"] in {"m1", "m2", "m3", "m4"} for unit in contract["units"]))

    test_command = [
        "/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python", "-m", "unittest", "-v",
        str(SCRIPT_DIR / "tests" / "test_test_gate.py"),
    ]
    completed = subprocess.run(test_command, capture_output=True, text=True, check=False)
    check("synthetic_tests", completed.returncode == 0, completed.stdout + completed.stderr)

    failed = [row["name"] for row in checks if not row["passed"]]
    report = {
        "schema_version": "exp-056-test-ready-verification-v1",
        "experiment_id": "EXP-056",
        "verified_at_utc": utc_now(),
        "status": "Passed" if not failed else "Failed",
        "contract": artifact(contract_path),
        "checks": checks,
        "check_count": len(checks),
        "failed_checks": failed,
        "test_inputs_opened": False,
        "test_labels_opened": False,
        "authorization_present": False,
        "formal_output_created": False,
    }
    atomic_json(output_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = verify(args.contract.resolve(), args.output.resolve())
    print(json.dumps({
        "status": report["status"], "checks": report["check_count"],
        "failed_checks": report["failed_checks"],
        "test_inputs_opened": False, "test_labels_opened": False,
    }, indent=2))
    raise SystemExit(0 if report["status"] == "Passed" else 1)


if __name__ == "__main__":
    main()
