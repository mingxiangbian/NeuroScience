#!/usr/bin/env python3
"""Independently verify the V3 execution gate without importing its auditor."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any


AUDIT_ID = "PRE-EXP-033-EXECUTION-V3"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
CONTRACT_PATH = SCRIPT_DIR / "preflight" / "pre-exp-033-execution-v3-contract.json"
REPORT_PATH = SCRIPT_DIR / "preflight" / "pre-exp-033-execution-v3-audit.json"
VERIFICATION_PATH = (
    SCRIPT_DIR / "preflight" / "pre-exp-033-execution-v3-verification.json"
)
TEST_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "test.tsv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def locate(value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def assert_artifact(spec: dict[str, str]) -> Path:
    path = locate(spec["path"])
    if file_digest(path) != spec["sha256"]:
        raise ValueError(f"Artifact hash mismatch: {path}")
    return path


def recalculate_source_tree(spec: dict[str, Any]) -> dict[str, Any]:
    root = Path(spec["root"])
    paths = list(root.rglob("*.py"))
    paths.sort(key=lambda path: path.relative_to(root).as_posix())
    aggregate = hashlib.sha256()
    byte_count = 0
    for path in paths:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        size = path.stat().st_size
        digest = file_digest(path).encode("ascii")
        aggregate.update(
            relative
            + bytes([0])
            + str(size).encode("ascii")
            + bytes([0])
            + digest
            + bytes([10])
        )
        byte_count += size
    observed = {
        "file_count": len(paths),
        "manifest_sha256": aggregate.hexdigest(),
        "total_bytes": byte_count,
    }
    frozen = {
        "file_count": int(spec["file_count"]),
        "manifest_sha256": spec["manifest_sha256"],
        "total_bytes": int(spec["total_bytes"]),
    }
    if observed != frozen:
        raise ValueError(f"MLX-LM source closure mismatch: {observed}")
    return observed


def current_packages(frozen: dict[str, str]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for name in frozen:
        observed[name] = (
            platform.python_version()
            if name == "python"
            else importlib.metadata.version(name)
        )
    if observed != frozen:
        raise ValueError(f"Package versions changed: {observed}")
    return observed


def decode_process_json(stdout: str) -> dict[str, Any]:
    opening = stdout.find("{")
    if opening == -1:
        raise ValueError("Nested verifier emitted no JSON")
    return json.loads(stdout[opening:])


def independently_run_v1(v2: dict[str, Any]) -> dict[str, Any]:
    verifier = assert_artifact(v2["immutable_inputs"]["v1_verifier"])
    command = (v2["runtime"]["python_executable"], str(verifier), "--check")
    result = subprocess.run(
        command,
        cwd=SCRIPT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Nested V1 check failed with {result.returncode}: {result.stderr}"
        )
    payload = decode_process_json(result.stdout)
    if payload.get("status") != "Passed" or payload.get("mode") != "check":
        raise ValueError("Nested V1 check did not pass")
    return {"payload": payload, "stdout_sha256": text_digest(result.stdout)}


def independently_recheck_chain(contract: dict[str, Any]) -> dict[str, Any]:
    for frozen in contract["v2_evidence"].values():
        assert_artifact(frozen)
    v2_path = locate(contract["v2_evidence"]["contract"]["path"])
    v2 = json.loads(v2_path.read_text(encoding="utf-8"))
    for frozen in v2["immutable_inputs"].values():
        assert_artifact(frozen)
    for frozen in v2["runtime"]["sources"].values():
        assert_artifact(frozen)
    if sys.executable != v2["runtime"]["python_executable"]:
        raise ValueError(f"Unexpected Python executable: {sys.executable}")
    packages = current_packages(v2["runtime"]["packages"])

    parent_path = assert_artifact(
        v2["immutable_inputs"]["parent_exp_029_config"]
    )
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    if v2["resource_budget"] != parent["resource_budget"]:
        raise ValueError("V2 resource budget is not inherited exactly")
    if v2["repetition_gate"] != parent["repetition_gate"]:
        raise ValueError("V2 repetition gate is not inherited exactly")
    frozen_seeds = [
        v2["repetition_gate"]["initial_seed"],
        *v2["repetition_gate"]["remaining_seeds"],
    ]
    if frozen_seeds != parent["training"]["seed_schedule"]:
        raise ValueError("Seed repetition order differs from training schedule")

    labels_path = assert_artifact(v2["immutable_inputs"]["labels"])
    labels = labels_path.read_text(encoding="utf-8").splitlines()
    if len(labels) != 28 or len(set(labels)) != 28:
        raise ValueError("Label ontology cardinality changed")
    if labels.index("neutral") != 27:
        raise ValueError("Official neutral ID changed")

    v1_audit_path = assert_artifact(v2["immutable_inputs"]["v1_audit"])
    v1_verification_path = assert_artifact(
        v2["immutable_inputs"]["v1_verification"]
    )
    v1_audit = json.loads(v1_audit_path.read_text(encoding="utf-8"))
    v1_verification = json.loads(
        v1_verification_path.read_text(encoding="utf-8")
    )
    required = v2["required_v1_evidence"]
    observed = v1_verification["independent_checks"]
    if v1_audit.get("status") != "Passed" or v1_verification.get("status") != "Passed":
        raise ValueError("V1 audit chain is not passing")
    inherited_keys = (
        "complete_model_condition_inherited",
        "complete_preflight_condition_inherited",
        "complete_training_condition_inherited",
    )
    if any(observed[key] is not True or required[key] is not True for key in inherited_keys):
        raise ValueError("V1 full-condition inheritance changed")
    if observed["all_model_manifest_files_rehashed"] != int(
        required["model_manifest_files_rehashed"]
    ):
        raise ValueError("V1 model-file rehash count changed")
    smoke = v1_audit["smoke"]
    smoke_expectations = (
        ("rows", "smoke_rows"),
        ("neutral_cooccurrence_rows", "neutral_cooccurrence_smoke_rows"),
        ("max_sequence_tokens", "smoke_max_sequence_tokens"),
        ("max_target_cardinality", "smoke_max_target_cardinality"),
    )
    if any(smoke[left] != required[right] for left, right in smoke_expectations):
        raise ValueError("V1 boundary-smoke dimensions changed")
    if smoke["covers_all_labels"] is not True or smoke["includes_all_truncated_rows"] is not True:
        raise ValueError("V1 boundary-smoke coverage changed")
    smoke_path = assert_artifact(v2["immutable_inputs"]["v1_smoke"])
    with smoke_path.open("r", encoding="utf-8") as source:
        smoke_rows = sum(1 for _ in source)
    if smoke_rows != int(required["smoke_rows"]):
        raise ValueError("Private smoke row count changed")
    ignore_check = subprocess.run(
        ("git", "check-ignore", "--quiet", str(smoke_path)),
        cwd=REPO_ROOT,
        check=False,
    )
    if ignore_check.returncode != 0:
        raise ValueError("Private smoke is no longer gitignored")

    v2_audit = json.loads(
        locate(contract["v2_evidence"]["audit"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    v2_verification = json.loads(
        locate(contract["v2_evidence"]["verification"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    if v2_audit.get("status") != "Passed" or v2_verification.get("status") != "Passed":
        raise ValueError("V2 evidence is not passing")
    if v2_audit["execution_gate"]["formal_training_authorized"] is not False:
        raise ValueError("V2 audit unexpectedly authorizes training")
    if v2_verification["formal_training_authorized"] is not False:
        raise ValueError("V2 verifier unexpectedly authorizes training")

    return {
        "labels_sha256": v2["immutable_inputs"]["labels"]["sha256"],
        "packages": packages,
        "source_tree": recalculate_source_tree(contract["runtime_source_tree"]),
        "v1": independently_run_v1(v2),
        "v1_smoke_rows": smoke_rows,
    }


def main() -> None:
    args = parse_args()
    if not args.check and VERIFICATION_PATH.exists():
        raise FileExistsError("V3 verification already exists; use --check")
    if not REPORT_PATH.is_file():
        raise FileNotFoundError("V3 audit report is absent")
    if TEST_PATH.exists():
        raise ValueError(f"Test split must remain absent: {TEST_PATH}")

    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    if contract.get("audit_id") != AUDIT_ID or report.get("audit_id") != AUDIT_ID:
        raise ValueError("Unexpected V3 audit identity")
    if report.get("status") != "Passed":
        raise ValueError("V3 audit report is not passing")
    if report["contract"]["sha256"] != file_digest(CONTRACT_PATH):
        raise ValueError("V3 contract changed after audit")
    auditor_path = locate(report["implementation"]["auditor"]["path"])
    if file_digest(auditor_path) != report["implementation"]["auditor"]["sha256"]:
        raise ValueError("V3 auditor changed after evidence generation")
    if file_digest(Path(__file__)) != report["implementation"]["verifier"]["sha256"]:
        raise ValueError("V3 verifier changed after evidence generation")
    if report["implementation"]["verifier_reuses_auditor_logic"] is not False:
        raise ValueError("V3 verifier independence claim changed")

    checked = independently_recheck_chain(contract)
    if report["runtime"]["packages"] != checked["packages"]:
        raise ValueError("Reported package versions differ")
    if report["runtime"]["python_source_tree"] != checked["source_tree"]:
        raise ValueError("Reported source-tree evidence differs")
    if report["label_ontology"] != {
        "count": 28,
        "neutral_id": 27,
        "sha256": checked["labels_sha256"],
    }:
        raise ValueError("Reported ontology evidence differs")
    if not all(report["resource_and_repetition_gates"].values()):
        raise ValueError("Reported resource or repetition gate is open")
    if (
        report["execution_gate"]["formal_training_authorized"] is not False
        or report["execution_gate"]["model_forward_or_backward_executed"] is not False
    ):
        raise ValueError("V3 report incorrectly authorizes model execution")

    verification = {
        "accessed_splits": ["train"],
        "audit_id": AUDIT_ID,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract_sha256": file_digest(CONTRACT_PATH),
        "formal_training_authorized": False,
        "independent_checks": {
            "auditor_logic_imported": False,
            "full_mlx_lm_python_source_files_rehashed": checked["source_tree"]
            ["file_count"],
            "label_order_and_neutral_id_rechecked": True,
            "resource_budget_rechecked": True,
            "runtime_packages_rechecked": len(checked["packages"]),
            "seed_repetition_gate_rechecked": True,
            "test_split_absent": True,
            "v1_check_mode_reexecuted": True,
            "v1_model_files_rehashed": checked["v1"]["payload"]
            ["independent_checks"]["all_model_manifest_files_rehashed"],
            "v1_smoke_rows_rechecked": checked["v1_smoke_rows"],
        },
        "mode": "check" if args.check else "initial-write",
        "model_forward_or_backward_executed": False,
        "next_required_step": contract["execution_gate"]["next_required_step"],
        "report_sha256": file_digest(REPORT_PATH),
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
