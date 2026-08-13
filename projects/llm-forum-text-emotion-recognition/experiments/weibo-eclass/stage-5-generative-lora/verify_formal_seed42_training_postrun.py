#!/usr/bin/env python3
"""Verify EXP-047 seed 42 after accounting for the declared adapter outputs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
BASE_VERIFIER_PATH = SCRIPT_DIR / "verify_formal_seed42_training.py"
GATE_VERIFIER_PATH = SCRIPT_DIR / "verify_formal_seed42_gate.py"
DRY_VERIFIER_PATH = SCRIPT_DIR / "verify_dry_run.py"
AMENDMENT_PATH = SCRIPT_DIR / "preflight" / "exp-047-formal-seed-42-postrun-amendment-v1.json"
VERIFICATION_ID = "EXP-047-FORMAL-SEED-42-TRAIN-VERIFY-V2"
AMENDMENT_ID = "EXP-047-FORMAL-SEED-42-POSTRUN-AMENDMENT-V1"
DRY_DELTA_CHECK = "private-prepared-train-is-exact-and-isolated"


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BASE = load_module("exp047_seed42_training_verifier_v1", BASE_VERIFIER_PATH)
GATE = load_module("exp047_seed42_gate_verifier", GATE_VERIFIER_PATH)
DRY = load_module("exp047_dry_run_verifier", DRY_VERIFIER_PATH)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def checks_by_name(verification: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks = verification.get("checks")
    if not isinstance(checks, list):
        raise ValueError("Dry-run verification has no check list")
    indexed = {item.get("check"): item for item in checks}
    if len(indexed) != len(checks) or not all(isinstance(key, str) for key in indexed):
        raise ValueError("Dry-run check names are missing or duplicated")
    return indexed


def expected_postrun_private_files(contract: dict[str, Any], config: dict[str, Any]) -> list[str]:
    private_root = BASE.resolve_project_path(config["paths"]["private_root"])
    adapter_dir = BASE.resolve_project_path(contract["outputs"]["adapter_dir"])
    try:
        adapter_prefix = adapter_dir.relative_to(private_root).as_posix()
    except ValueError as error:
        raise ValueError("Formal adapter directory is outside the private root") from error
    names = {
        "adapter_config.json",
        "adapters.safetensors",
        *contract["expected_adapter"]["checkpoint_names"],
    }
    return sorted(["lora-data/train.jsonl", *(f"{adapter_prefix}/{name}" for name in names)])


def verify_expected_dry_run_delta(
    contract: dict[str, Any], stored: dict[str, Any], current: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    if (
        current.get("status") != "Failed"
        or current.get("mismatches") != [DRY_DELTA_CHECK]
        or current.get("checks_passed") != int(stored["checks_passed"]) - 1
    ):
        raise ValueError("Unexpected post-run dry-run verification result")
    stable_fields = {
        "accessed_splits",
        "completed_at_utc",
        "experiment_id",
        "model_execution",
        "prepared_train_sha256",
        "test_split_accessed",
        "training_executed",
        "validation_split_accessed",
        "verification_id",
    }
    for field in stable_fields:
        BASE.require_equal(current.get(field), stored.get(field), f"Dry-run field drift: {field}")
    stored_checks = checks_by_name(stored)
    current_checks = checks_by_name(current)
    BASE.require_equal(set(current_checks), set(stored_checks), "Dry-run check inventory drift")
    for name in sorted(stored_checks):
        if name != DRY_DELTA_CHECK:
            BASE.require_equal(current_checks[name], stored_checks[name], f"Dry-run check drift: {name}")
    before = stored_checks[DRY_DELTA_CHECK]
    after = current_checks[DRY_DELTA_CHECK]
    BASE.require_equal(before.get("status"), "Passed", "Original private-isolation gate was not passed")
    BASE.require_equal(after.get("status"), "Failed", "Expected post-run private-isolation delta is absent")
    before_detail = dict(before["detail"])
    after_detail = dict(after["detail"])
    observed_files = after_detail.pop("files")
    BASE.require_equal(after_detail, {k: v for k, v in before_detail.items() if k != "files"}, "Private train evidence drift")
    expected_files = expected_postrun_private_files(contract, config)
    BASE.require_equal(observed_files, expected_files, "Undeclared private output appeared after training")
    return {
        "accepted_check_delta": DRY_DELTA_CHECK,
        "immutable_checks_reproduced": len(current_checks) - 1,
        "postrun_private_files": observed_files,
        "prepared_train_sha256": current["prepared_train_sha256"],
        "status": "Passed",
    }


def reproduce_postrun_gate(contract: dict[str, Any]) -> dict[str, Any]:
    gate_path = BASE.resolve_project_path(contract["outputs"]["gate_verification"])
    stored_gate = BASE.load_json(gate_path)
    if (
        stored_gate.get("verification_id") != "EXP-047-FORMAL-SEED-42-GATE-VERIFY-V1"
        or stored_gate.get("status") != "Passed"
        or stored_gate.get("outputs_absent_at_verification") is not True
    ):
        raise ValueError("Original formal gate evidence is invalid")
    recalculated = {
        "environment": GATE.verify_environment(contract),
        "model": GATE.verify_model(contract),
        "runtime_and_data": GATE.verify_runtime_and_data(contract),
    }
    for key, value in recalculated.items():
        BASE.require_equal(value, stored_gate["recalculated"][key], f"Formal gate section drift: {key}")
    python = Path(contract["runtime"]["python_executable"])
    test_path = BASE.resolve_project_path(contract["implementation"]["test"]["path"])
    static_tests = GATE.run_checked([str(python), str(test_path)])
    BASE.require_equal(
        static_tests,
        stored_gate["recalculated"]["subprocess_checks"]["formal_static_tests"],
        "Formal static-test evidence drift",
    )
    config = BASE.load_json(BASE.resolve_project_path(contract["frozen_artifacts"]["config"]["path"]))
    dry_path = BASE.resolve_project_path(contract["frozen_artifacts"]["dry_run_verification"]["path"])
    stored_dry = BASE.load_json(dry_path)
    current_dry = DRY.build_verification(config, str(stored_dry["completed_at_utc"]))
    dry_delta = verify_expected_dry_run_delta(contract, stored_dry, current_dry, config)
    return {
        "amendment_id": AMENDMENT_ID,
        "dry_run_postrun_delta": dry_delta,
        "formal_static_tests": static_tests,
        "immutable_gate_sections_reproduced": sorted(recalculated),
        "original_gate": BASE.artifact(gate_path),
        "status": "Passed",
    }


def load_context() -> tuple[dict[str, Any], dict[str, Any]]:
    contract = BASE.load_contract()
    amendment = BASE.load_json(AMENDMENT_PATH)
    if (
        amendment.get("amendment_id") != AMENDMENT_ID
        or amendment.get("experiment_id") != "EXP-047"
        or amendment.get("seed") != 42
        or amendment.get("status") != "Registered"
        or amendment.get("validation_split_accessed") is not False
        or amendment.get("test_split_accessed") is not False
    ):
        raise ValueError("Unexpected post-run amendment identity or boundary")
    bindings = amendment["bindings"]
    expected = {
        "authorization": BASE.artifact(
            SCRIPT_DIR / "preflight" / "exp-047-formal-seed-42-authorization-v1.json"
        ),
        "base_training_verifier": BASE.artifact(BASE_VERIFIER_PATH),
        "contract": BASE.artifact(BASE.CONTRACT_PATH),
        "dry_run_verifier": BASE.artifact(DRY_VERIFIER_PATH),
        "formal_gate": BASE.artifact(BASE.resolve_project_path(contract["outputs"]["gate_verification"])),
        "postrun_verifier": BASE.artifact(Path(__file__).resolve()),
    }
    BASE.require_equal(bindings, expected, "Post-run amendment binding drift")
    BASE.require_equal(
        amendment.get("permitted_delta"),
        {
            "check": DRY_DELTA_CHECK,
            "files": expected_postrun_private_files(
                contract,
                BASE.load_json(BASE.resolve_project_path(contract["frozen_artifacts"]["config"]["path"])),
            ),
        },
        "Post-run amendment scope drift",
    )
    return contract, amendment


def build_verification(contract: dict[str, Any], amendment: dict[str, Any], completed_at_utc: str) -> dict[str, Any]:
    original_gate_check = BASE.run_gate_check
    BASE.run_gate_check = reproduce_postrun_gate
    try:
        verification = BASE.build_verification(contract, completed_at_utc)
    finally:
        BASE.run_gate_check = original_gate_check
    verification["amendment"] = BASE.artifact(AMENDMENT_PATH)
    verification["implementation"] = {
        "amendment_verifier": BASE.artifact(Path(__file__).resolve()),
        "base_training_verifier": BASE.artifact(BASE_VERIFIER_PATH),
        "imports_runner": False,
    }
    verification["original_contract_unchanged"] = True
    verification["postrun_amendment_applied"] = True
    verification["training_rerun"] = False
    verification["verification_id"] = VERIFICATION_ID
    return verification


def main() -> None:
    args = parse_args()
    contract, amendment = load_context()
    verification_path = BASE.resolve_project_path(contract["outputs"]["run_dir"]) / "verification.json"
    if args.check:
        existing = BASE.load_json(verification_path)
        expected = build_verification(contract, amendment, str(existing.get("completed_at_utc")))
        BASE.require_equal(existing, expected, "Stored post-run verification differs from recomputation")
        print(json.dumps({"path": BASE.display_path(verification_path), "status": "Passed"}, sort_keys=True))
        return
    if verification_path.exists():
        raise FileExistsError(verification_path)
    verification = build_verification(contract, amendment, datetime.now(timezone.utc).isoformat())
    BASE.write_json(verification_path, verification)
    print(json.dumps({"path": BASE.display_path(verification_path), "status": "Passed"}, sort_keys=True))


if __name__ == "__main__":
    main()
