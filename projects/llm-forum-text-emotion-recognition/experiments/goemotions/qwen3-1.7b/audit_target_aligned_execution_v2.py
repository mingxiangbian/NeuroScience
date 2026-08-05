#!/usr/bin/env python3
"""Close execution-contract gaps without running the model or training."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any


AUDIT_ID = "PRE-EXP-033-EXECUTION-V2"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
CONTRACT_PATH = SCRIPT_DIR / "preflight" / "pre-exp-033-execution-v2-contract.json"
VERIFIER_PATH = SCRIPT_DIR / "verify_target_aligned_execution_v2.py"
TEST_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "test.tsv"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def project_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": project_path(path),
        "sha256": sha256_file(path),
    }


def verify_spec(spec: dict[str, str]) -> Path:
    path = resolve_path(spec["path"])
    if sha256_file(path) != spec["sha256"]:
        raise ValueError(f"Frozen artifact changed: {path}")
    return path


def package_versions(names: list[str]) -> dict[str, str]:
    versions = {name: importlib.metadata.version(name) for name in names}
    versions["python"] = platform.python_version()
    return versions


def parse_json_output(output: str) -> dict[str, Any]:
    start = output.find("{")
    if start < 0:
        raise ValueError("V1 verifier did not emit JSON")
    return json.loads(output[start:])


def run_v1_check(contract: dict[str, Any]) -> dict[str, Any]:
    verifier = resolve_path(contract["immutable_inputs"]["v1_verifier"]["path"])
    command = [contract["runtime"]["python_executable"], str(verifier), "--check"]
    completed = subprocess.run(
        command,
        cwd=SCRIPT_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"V1 verifier failed with {completed.returncode}: {completed.stderr}"
        )
    result = parse_json_output(completed.stdout)
    if result.get("status") != "Passed" or result.get("mode") != "check":
        raise ValueError("V1 verifier did not return a passing check-mode result")
    return {
        "command": command,
        "result": result,
        "stdout_sha256": sha256_text(completed.stdout),
    }


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    if contract["audit_id"] != AUDIT_ID:
        raise ValueError("Unexpected V2 audit ID")
    if TEST_PATH.exists():
        raise ValueError(f"Test split must remain absent: {TEST_PATH}")
    if sys.executable != contract["runtime"]["python_executable"]:
        raise ValueError(f"Wrong Python interpreter: {sys.executable}")
    for spec in contract["immutable_inputs"].values():
        verify_spec(spec)
    for spec in contract["runtime"]["sources"].values():
        verify_spec(spec)

    package_names = [
        name for name in contract["runtime"]["packages"] if name != "python"
    ]
    versions = package_versions(package_names)
    if versions != contract["runtime"]["packages"]:
        raise ValueError(f"Runtime package drift: {versions}")

    parent = json.loads(
        resolve_path(
            contract["immutable_inputs"]["parent_exp_029_config"]["path"]
        ).read_text(encoding="utf-8")
    )
    if contract["resource_budget"] != parent["resource_budget"]:
        raise ValueError("Resource budget differs from EXP-029")
    if contract["repetition_gate"] != parent["repetition_gate"]:
        raise ValueError("Seed repetition gate differs from EXP-029")
    if (
        int(contract["repetition_gate"]["initial_seed"])
        not in parent["training"]["seed_schedule"]
        or contract["repetition_gate"]["remaining_seeds"]
        != parent["training"]["seed_schedule"][1:]
    ):
        raise ValueError("Repetition gate and training seed schedule disagree")

    labels = resolve_path(contract["immutable_inputs"]["labels"]["path"])
    ontology = tuple(labels.read_text(encoding="utf-8").splitlines())
    if len(ontology) != 28 or len(set(ontology)) != 28 or ontology[27] != "neutral":
        raise ValueError("Official label order or neutral ID changed")

    v1_audit = json.loads(
        resolve_path(contract["immutable_inputs"]["v1_audit"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    v1_verification = json.loads(
        resolve_path(
            contract["immutable_inputs"]["v1_verification"]["path"]
        ).read_text(encoding="utf-8")
    )
    required = contract["required_v1_evidence"]
    checks = v1_verification["independent_checks"]
    if v1_audit["status"] != "Passed" or v1_verification["status"] != "Passed":
        raise ValueError("V1 execution audit is not passing")
    if any(
        checks[key] is not required[key]
        for key in (
            "complete_model_condition_inherited",
            "complete_preflight_condition_inherited",
            "complete_training_condition_inherited",
        )
    ):
        raise ValueError("V1 complete-condition inheritance changed")
    if checks["all_model_manifest_files_rehashed"] != required[
        "model_manifest_files_rehashed"
    ]:
        raise ValueError("V1 model-file coverage changed")
    smoke = v1_audit["smoke"]
    expected_smoke = {
        "max_sequence_tokens": required["smoke_max_sequence_tokens"],
        "max_target_cardinality": required["smoke_max_target_cardinality"],
        "neutral_cooccurrence_rows": required["neutral_cooccurrence_smoke_rows"],
        "rows": required["smoke_rows"],
    }
    if any(smoke[key] != value for key, value in expected_smoke.items()):
        raise ValueError("V1 boundary-smoke evidence changed")
    if not smoke["covers_all_labels"] or not smoke["includes_all_truncated_rows"]:
        raise ValueError("V1 boundary-smoke coverage changed")

    smoke_path = resolve_path(contract["immutable_inputs"]["v1_smoke"]["path"])
    if sum(1 for _ in smoke_path.open("r", encoding="utf-8")) != required["smoke_rows"]:
        raise ValueError("V1 private smoke row count changed")
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", str(smoke_path)],
        cwd=REPO_ROOT,
        check=False,
    )
    if ignored.returncode != 0:
        raise ValueError("Private smoke data is not gitignored")

    return {
        "labels": ontology,
        "packages": versions,
        "parent": parent,
        "smoke": smoke,
        "v1_check": run_v1_check(contract),
    }


def main() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    report_path = resolve_path(contract["outputs"]["audit_report"])
    verification_path = resolve_path(contract["outputs"]["verification_report"])
    if report_path.exists() or verification_path.exists():
        raise FileExistsError("V2 execution evidence already exists; it is append-only")
    validated = validate_contract(contract)
    report = {
        "accessed_splits": ["train"],
        "audit_id": AUDIT_ID,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract": artifact(CONTRACT_PATH),
        "execution_gate": {
            "formal_training_authorized": False,
            "model_forward_or_backward_executed": False,
            "next_required_step": contract["execution_gate"]["next_required_step"],
        },
        "implementation": {
            "auditor": artifact(Path(__file__)),
            "verifier": artifact(VERIFIER_PATH),
        },
        "label_ontology": {
            "count": len(validated["labels"]),
            "neutral_id": validated["labels"].index("neutral"),
            "order_sha256": contract["immutable_inputs"]["labels"]["sha256"],
        },
        "resource_and_repetition_gates": {
            "resource_budget_equals_exp_029": True,
            "repetition_gate_equals_exp_029": True,
            "seed_42_required_first": True,
            "remaining_seeds_require_verified_improvement": True,
        },
        "runtime": {
            "frozen_source_count": len(contract["runtime"]["sources"]),
            "packages": validated["packages"],
            "python_executable": sys.executable,
        },
        "status": "Passed",
        "test_split_absent": True,
        "test_split_accessed": False,
        "validation_split_accessed": False,
        "v1_evidence": {
            "boundary_smoke_rows": validated["smoke"]["rows"],
            "check_mode_status": validated["v1_check"]["result"]["status"],
            "check_stdout_sha256": validated["v1_check"]["stdout_sha256"],
            "complete_condition_inheritance_rechecked": True,
            "model_files_rehashed_in_v1_check": validated["v1_check"]["result"]
            ["independent_checks"]["all_model_manifest_files_rehashed"],
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
