#!/usr/bin/env python3
"""Audit the full MLX-LM source closure before building the EXP-033 runner."""

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


AUDIT_ID = "PRE-EXP-033-EXECUTION-V3"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
CONTRACT_PATH = SCRIPT_DIR / "preflight" / "pre-exp-033-execution-v3-contract.json"
VERIFIER_PATH = SCRIPT_DIR / "verify_target_aligned_execution_v3.py"
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


def source_tree_manifest(spec: dict[str, Any]) -> dict[str, Any]:
    root = Path(spec["root"])
    files = sorted(root.rglob("*.py"), key=lambda path: path.relative_to(root).as_posix())
    digest = hashlib.sha256()
    total_bytes = 0
    for path in files:
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        file_hash = sha256_file(path)
        digest.update(
            relative.encode("utf-8")
            + b"\0"
            + str(size).encode("ascii")
            + b"\0"
            + file_hash.encode("ascii")
            + b"\n"
        )
        total_bytes += size
    result = {
        "file_count": len(files),
        "manifest_sha256": digest.hexdigest(),
        "total_bytes": total_bytes,
    }
    expected = {
        "file_count": int(spec["file_count"]),
        "manifest_sha256": spec["manifest_sha256"],
        "total_bytes": int(spec["total_bytes"]),
    }
    if result != expected:
        raise ValueError(f"MLX-LM Python source tree changed: {result}")
    return result


def package_versions(expected: dict[str, str]) -> dict[str, str]:
    versions = {
        name: importlib.metadata.version(name)
        for name in expected
        if name != "python"
    }
    versions["python"] = platform.python_version()
    if versions != expected:
        raise ValueError(f"Runtime package drift: {versions}")
    return versions


def parse_json_output(output: str) -> dict[str, Any]:
    start = output.find("{")
    if start < 0:
        raise ValueError("V1 verifier did not emit JSON")
    return json.loads(output[start:])


def run_v1_check(v2: dict[str, Any]) -> dict[str, Any]:
    verifier = resolve_path(v2["immutable_inputs"]["v1_verifier"]["path"])
    command = [v2["runtime"]["python_executable"], str(verifier), "--check"]
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
        raise ValueError("V1 verifier did not return Passed in check mode")
    return {"result": result, "stdout_sha256": sha256_text(completed.stdout)}


def validate_v2_chain(contract: dict[str, Any]) -> dict[str, Any]:
    for spec in contract["v2_evidence"].values():
        verify_spec(spec)
    v2 = json.loads(
        resolve_path(contract["v2_evidence"]["contract"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    for spec in v2["immutable_inputs"].values():
        verify_spec(spec)
    for spec in v2["runtime"]["sources"].values():
        verify_spec(spec)
    if sys.executable != v2["runtime"]["python_executable"]:
        raise ValueError(f"Wrong Python interpreter: {sys.executable}")
    versions = package_versions(v2["runtime"]["packages"])

    parent = json.loads(
        resolve_path(v2["immutable_inputs"]["parent_exp_029_config"]["path"])
        .read_text(encoding="utf-8")
    )
    if v2["resource_budget"] != parent["resource_budget"]:
        raise ValueError("Resource budget differs from EXP-029")
    if v2["repetition_gate"] != parent["repetition_gate"]:
        raise ValueError("Repetition gate differs from EXP-029")
    if [v2["repetition_gate"]["initial_seed"], *v2["repetition_gate"]["remaining_seeds"]] != parent["training"]["seed_schedule"]:
        raise ValueError("Seed gate differs from the training schedule")

    label_path = verify_spec(v2["immutable_inputs"]["labels"])
    labels = tuple(label_path.read_text(encoding="utf-8").splitlines())
    if len(labels) != 28 or len(set(labels)) != 28 or labels[27] != "neutral":
        raise ValueError("Official label order or neutral ID changed")

    v1_audit = json.loads(
        resolve_path(v2["immutable_inputs"]["v1_audit"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    v1_verification = json.loads(
        resolve_path(v2["immutable_inputs"]["v1_verification"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    required = v2["required_v1_evidence"]
    independent = v1_verification["independent_checks"]
    if v1_audit["status"] != "Passed" or v1_verification["status"] != "Passed":
        raise ValueError("V1 evidence is not passing")
    for key in (
        "complete_model_condition_inherited",
        "complete_preflight_condition_inherited",
        "complete_training_condition_inherited",
    ):
        if independent[key] is not True or required[key] is not True:
            raise ValueError(f"V1 inheritance gate changed: {key}")
    if independent["all_model_manifest_files_rehashed"] != required[
        "model_manifest_files_rehashed"
    ]:
        raise ValueError("V1 model-file coverage changed")
    smoke = v1_audit["smoke"]
    if (
        smoke["rows"] != required["smoke_rows"]
        or smoke["neutral_cooccurrence_rows"]
        != required["neutral_cooccurrence_smoke_rows"]
        or smoke["max_sequence_tokens"] != required["smoke_max_sequence_tokens"]
        or smoke["max_target_cardinality"]
        != required["smoke_max_target_cardinality"]
        or not smoke["covers_all_labels"]
        or not smoke["includes_all_truncated_rows"]
    ):
        raise ValueError("V1 boundary-smoke evidence changed")
    smoke_path = verify_spec(v2["immutable_inputs"]["v1_smoke"])
    if sum(1 for _ in smoke_path.open("r", encoding="utf-8")) != required["smoke_rows"]:
        raise ValueError("V1 private smoke row count changed")
    if subprocess.run(
        ["git", "check-ignore", "--quiet", str(smoke_path)],
        cwd=REPO_ROOT,
        check=False,
    ).returncode != 0:
        raise ValueError("Private smoke is not gitignored")

    v2_audit = json.loads(
        resolve_path(contract["v2_evidence"]["audit"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    v2_verification = json.loads(
        resolve_path(contract["v2_evidence"]["verification"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    if v2_audit["status"] != "Passed" or v2_verification["status"] != "Passed":
        raise ValueError("V2 evidence is not passing")
    if (
        v2_audit["execution_gate"]["formal_training_authorized"] is not False
        or v2_verification["formal_training_authorized"] is not False
    ):
        raise ValueError("An earlier gate incorrectly authorizes training")
    return {
        "labels": labels,
        "packages": versions,
        "smoke": smoke,
        "v1_check": run_v1_check(v2),
        "v2": v2,
    }


def main() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if contract["audit_id"] != AUDIT_ID:
        raise ValueError("Unexpected V3 audit ID")
    if TEST_PATH.exists():
        raise ValueError(f"Test split must remain absent: {TEST_PATH}")
    report_path = resolve_path(contract["outputs"]["audit_report"])
    verification_path = resolve_path(contract["outputs"]["verification_report"])
    if report_path.exists() or verification_path.exists():
        raise FileExistsError("V3 execution evidence already exists; it is append-only")

    validated = validate_v2_chain(contract)
    source_tree = source_tree_manifest(contract["runtime_source_tree"])
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
            "verifier_reuses_auditor_logic": False,
        },
        "label_ontology": {
            "count": len(validated["labels"]),
            "neutral_id": validated["labels"].index("neutral"),
            "sha256": validated["v2"]["immutable_inputs"]["labels"]["sha256"],
        },
        "resource_and_repetition_gates": {
            "resource_budget_equals_exp_029": True,
            "repetition_gate_equals_exp_029": True,
            "seed_42_required_first": True,
        },
        "runtime": {
            "packages": validated["packages"],
            "python_executable": sys.executable,
            "python_source_tree": source_tree,
        },
        "status": "Passed",
        "test_split_absent": True,
        "test_split_accessed": False,
        "validation_split_accessed": False,
        "v1_recheck": {
            "boundary_smoke_rows": validated["smoke"]["rows"],
            "model_files_rehashed": validated["v1_check"]["result"]
            ["independent_checks"]["all_model_manifest_files_rehashed"],
            "status": validated["v1_check"]["result"]["status"],
            "stdout_sha256": validated["v1_check"]["stdout_sha256"],
        },
        "v2_chain_rechecked": True,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
