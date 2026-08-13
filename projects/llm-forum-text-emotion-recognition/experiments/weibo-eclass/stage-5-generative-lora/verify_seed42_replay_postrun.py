#!/usr/bin/env python3
"""Recompute the EXP-047 seed-42 replay without self-counting verification files."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
BASE_VERIFIER_PATH = SCRIPT_DIR / "verify_seed42_replay.py"
AMENDMENT_PATH = SCRIPT_DIR / "preflight" / "exp-047-seed-42-replay-postrun-amendment-v1.json"
OUTPUT_PATH = (
    SCRIPT_DIR
    / "runs"
    / "exp-047-stage-5-generative-lora"
    / "seed-42-replay-verification-v2.json"
)
AMENDMENT_ID = "EXP-047-SEED-42-REPLAY-POSTRUN-AMENDMENT-V1"
VERIFICATION_ID = "EXP-047-SEED-42-REPLAY-VERIFY-V2"


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BASE = load_module("exp047_seed42_replay_verifier_v1", BASE_VERIFIER_PATH)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def stable_public_privacy(
    contract: dict[str, Any], records: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    public = BASE.resolve_project_path(contract["outputs"]["public_dir"])
    source_files = sorted(path for path in public.glob("*.json") if not path.name.startswith("verification"))
    BASE.require_equal(
        {path.name for path in source_files},
        {"aggregate.json", "pass-r1.json", "pass-r2.json", "run.json"},
        "Replay source-public inventory drift",
    )
    contents = "\n".join(path.read_text(encoding="utf-8") for path in source_files)
    forbidden = {
        str(row["raw_output"])
        for pass_rows in records.values()
        for row in pass_rows
        if isinstance(row.get("raw_output"), str) and len(row["raw_output"]) >= 4
    }
    leaked = [BASE.sha256_text(value) for value in forbidden if value in contents]
    if leaked:
        raise ValueError("Replay source-public artifacts contain raw model output")
    return {
        "public_json_files_scanned": len(source_files),
        "raw_output_leaks": 0,
        "verification_files_excluded_from_source_count": True,
    }


def predecessor_path(contract: dict[str, Any]) -> Path:
    return BASE.resolve_project_path(contract["outputs"]["public_dir"]) / "verification.json"


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
        raise ValueError("Unexpected replay post-run amendment identity or boundary")
    predecessor = predecessor_path(contract)
    expected_bindings = {
        "base_replay_verifier": BASE.artifact(BASE_VERIFIER_PATH),
        "contract": BASE.artifact(BASE.CONTRACT_PATH),
        "postrun_verifier": BASE.artifact(Path(__file__).resolve()),
        "predecessor_verification": BASE.artifact(predecessor),
    }
    BASE.require_equal(amendment.get("bindings"), expected_bindings, "Replay amendment binding drift")
    BASE.require_equal(
        amendment.get("permitted_delta"),
        {
            "field": "recalculated.privacy.public_json_files_scanned",
            "post_write_observed": 5,
            "stable_source_artifact_count": 4,
        },
        "Replay amendment scope drift",
    )
    predecessor_value = BASE.load_json(predecessor)
    if (
        predecessor_value.get("verification_id") != "EXP-047-SEED-42-REPLAY-VERIFY-V1"
        or predecessor_value.get("status") != "Passed"
        or predecessor_value.get("validation_split_accessed") is not False
        or predecessor_value.get("test_split_accessed") is not False
    ):
        raise ValueError("Replay V1 predecessor evidence is invalid")
    return contract, amendment


def build_verification(contract: dict[str, Any], completed_at_utc: str) -> dict[str, Any]:
    original_privacy = BASE.verify_public_privacy
    BASE.verify_public_privacy = stable_public_privacy
    try:
        verification = BASE.build_verification(contract, completed_at_utc)
    finally:
        BASE.verify_public_privacy = original_privacy
    verification["amendment"] = BASE.artifact(AMENDMENT_PATH)
    verification["implementation"] = {
        "base_replay_verifier": BASE.artifact(BASE_VERIFIER_PATH),
        "imports_runner": False,
        "postrun_verifier": BASE.artifact(Path(__file__).resolve()),
    }
    verification["predecessor_verification"] = BASE.artifact(predecessor_path(contract))
    verification["self_counting_defect_corrected"] = True
    verification["verification_id"] = VERIFICATION_ID
    return verification


def main() -> None:
    args = parse_args()
    contract, _ = load_context()
    if args.check:
        existing = BASE.load_json(OUTPUT_PATH)
        expected = build_verification(contract, str(existing.get("completed_at_utc")))
        BASE.require_equal(existing, expected, "Stored replay V2 verification differs from recomputation")
        print(json.dumps({"path": BASE.display_path(OUTPUT_PATH), "status": "Passed"}, sort_keys=True))
        return
    if OUTPUT_PATH.exists():
        raise FileExistsError(OUTPUT_PATH)
    verification = build_verification(contract, datetime.now(timezone.utc).isoformat())
    BASE.write_json(OUTPUT_PATH, verification)
    print(json.dumps({"path": BASE.display_path(OUTPUT_PATH), "status": "Passed"}, sort_keys=True))


if __name__ == "__main__":
    main()
