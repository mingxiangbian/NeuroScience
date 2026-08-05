#!/usr/bin/env python3
"""Independently recheck the PRE-EXP-033 V2 execution contract."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import audit_target_aligned_execution_v2 as audit


SCRIPT_DIR = Path(__file__).resolve().parent
CONTRACT_PATH = SCRIPT_DIR / "preflight" / "pre-exp-033-execution-v2-contract.json"
REPORT_PATH = SCRIPT_DIR / "preflight" / "pre-exp-033-execution-v2-audit.json"
VERIFICATION_PATH = (
    SCRIPT_DIR / "preflight" / "pre-exp-033-execution-v2-verification.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.check and VERIFICATION_PATH.exists():
        raise FileExistsError("V2 verification already exists; use --check")
    if not REPORT_PATH.is_file():
        raise FileNotFoundError("V2 audit report is absent")

    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    if report.get("status") != "Passed" or report.get("audit_id") != audit.AUDIT_ID:
        raise ValueError("V2 audit report is not passing")
    if report["contract"]["sha256"] != audit.sha256_file(CONTRACT_PATH):
        raise ValueError("V2 contract changed after audit")
    if (
        audit.sha256_file(Path(audit.__file__).resolve())
        != report["implementation"]["auditor"]["sha256"]
    ):
        raise ValueError("V2 auditor changed after evidence generation")
    if (
        audit.sha256_file(Path(__file__).resolve())
        != report["implementation"]["verifier"]["sha256"]
    ):
        raise ValueError("V2 verifier changed after evidence generation")

    validated = audit.validate_contract(contract)
    if report["runtime"]["packages"] != validated["packages"]:
        raise ValueError("Reported package evidence changed")
    if report["runtime"]["frozen_source_count"] != len(
        contract["runtime"]["sources"]
    ):
        raise ValueError("Reported runtime-source coverage changed")
    if report["label_ontology"] != {
        "count": 28,
        "neutral_id": 27,
        "order_sha256": contract["immutable_inputs"]["labels"]["sha256"],
    }:
        raise ValueError("Reported label-order evidence changed")
    gates = report["resource_and_repetition_gates"]
    if not all(gates.values()):
        raise ValueError("Resource or repetition gate is not closed")
    if (
        report["execution_gate"]["formal_training_authorized"] is not False
        or report["execution_gate"]["model_forward_or_backward_executed"] is not False
    ):
        raise ValueError("V2 audit incorrectly authorizes model execution")

    verification = {
        "accessed_splits": ["train"],
        "audit_id": audit.AUDIT_ID,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract_sha256": audit.sha256_file(CONTRACT_PATH),
        "formal_training_authorized": False,
        "independent_checks": {
            "label_order_and_neutral_id_rechecked": True,
            "resource_budget_inherited": True,
            "runtime_entrypoint_and_sources_rehashed": len(
                contract["runtime"]["sources"]
            ),
            "runtime_packages_rechecked": len(validated["packages"]),
            "seed_repetition_gate_inherited": True,
            "test_split_absent": True,
            "v1_check_mode_reexecuted": True,
            "v1_model_files_rehashed": validated["v1_check"]["result"]
            ["independent_checks"]["all_model_manifest_files_rehashed"],
            "v1_smoke_rows_rechecked": validated["smoke"]["rows"],
        },
        "mode": "check" if args.check else "initial-write",
        "model_forward_or_backward_executed": False,
        "next_required_step": contract["execution_gate"]["next_required_step"],
        "report_sha256": audit.sha256_file(REPORT_PATH),
        "status": "Passed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
    }
    if not args.check:
        VERIFICATION_PATH.write_text(
            json.dumps(verification, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(verification, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
