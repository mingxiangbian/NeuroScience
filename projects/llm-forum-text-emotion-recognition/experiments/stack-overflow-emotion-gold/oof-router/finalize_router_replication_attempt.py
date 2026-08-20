#!/usr/bin/env python3
"""Atomically select one fully verified EXP-061/062 attempt.

This finalizer does not import any analysis runner or verifier.  It only validates
the three immutable stage-completion records and their artifact hashes, then
creates the experiment-level selection marker once.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
ATTEMPT_RE = re.compile(r"attempt-[1-9][0-9]*\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
REGISTERED = {
    "EXP-061": (43, "exp-061-seed-43-router-replication"),
    "EXP-062": (44, "exp-062-seed-44-router-replication"),
}
DEPLOYABLE_POLICIES = (
    "m1_max_entropy",
    "m1_threshold_proximity",
    "logistic_router",
)
STAGES = {
    "oof": {
        "relative": Path("oof-complete.json"),
        "schema": "exp-oof-completion-v2",
        "status": "Complete",
        "artifacts": {"run", "summary", "final_verification", "paired_oof_private"},
    },
    "calibration": {
        "relative": Path("calibration-complete.json"),
        "schema": "exp-059-calibration-completion-v2",
        "status": "Complete",
        "artifacts": {
            "config",
            "exp059_run",
            "exp059_verification",
            "exp059_calibration_parameters",
        },
    },
    "router": {
        "relative": Path("router") / "router-complete.json",
        "schema": "exp-router-completion-v2",
        "status": "Complete",
        "artifacts": {
            "config",
            "run",
            "final_verification",
            "selected_operating_point",
            "private_router_oof",
        },
    },
}
PUBLIC_SENSITIVE_KEYS = {
    "sample_id",
    "sample_ids",
    "component_id",
    "component_ids",
    "gold",
    "logits",
    "probabilities",
    "features",
    "targets",
    "masks",
    "predictions",
    "text",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_seed_contract(seed: int) -> dict[str, int]:
    return {
        "model_seed": seed,
        "python_seed": seed,
        "numpy_seed": seed,
        "torch_seed": seed,
        "m1_batch_seed": seed,
        "m3_head_seed": seed,
        "m3_batch_seed": seed,
        "m3_lora_seed": seed + 100_000,
    }


def lexical_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def reject_symlink_components(path: Path, project_root: Path) -> Path:
    root = lexical_path(project_root)
    candidate = lexical_path(path)
    try:
        relative = candidate.relative_to(root)
    except ValueError as error:
        raise ValueError(f"Path escapes project root: {path}") from error
    cursor = root
    if os.path.lexists(cursor) and cursor.is_symlink():
        raise ValueError(f"Project root is a symlink: {cursor}")
    for part in relative.parts:
        cursor /= part
        if os.path.lexists(cursor) and cursor.is_symlink():
            raise ValueError(f"Symlink path component is forbidden: {cursor}")
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Resolved path escapes project root: {path}")
    return candidate


def display_path(path: Path, project_root: Path) -> str:
    return str(lexical_path(path).relative_to(lexical_path(project_root)))


def artifact(path: Path, project_root: Path) -> dict[str, Any]:
    checked = reject_symlink_components(path, project_root)
    if not checked.is_file():
        raise FileNotFoundError(checked)
    return {
        "path": display_path(checked, project_root),
        "bytes": checked.stat().st_size,
        "sha256": sha256(checked),
    }


def require_record(record: Any, project_root: Path) -> Path:
    if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
        raise ValueError("Artifact record must contain exactly path/bytes/sha256")
    digest = str(record["sha256"])
    if not SHA256_RE.fullmatch(digest):
        raise ValueError("Artifact record contains an invalid SHA-256")
    relative = Path(str(record["path"]))
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        raise ValueError("Artifact path must be normalized and project-relative")
    path = reject_symlink_components(project_root / relative, project_root)
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]) or sha256(path) != digest:
        raise ValueError(f"Artifact record drift: {relative}")
    return path


def identity(experiment_id: str, attempt_id: str) -> dict[str, Any]:
    if experiment_id not in REGISTERED:
        raise ValueError("Finalizer is restricted to EXP-061/EXP-062")
    if ATTEMPT_RE.fullmatch(attempt_id) is None:
        raise ValueError("attempt_id must match attempt-[1-9][0-9]*")
    seed, run_id = REGISTERED[experiment_id]
    return {
        "experiment_id": experiment_id,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "model_seed": seed,
        "seed_contract": expected_seed_contract(seed),
    }


def attempt_paths(
    experiment_id: str,
    attempt_id: str,
    *,
    script_dir: Path = SCRIPT_DIR,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Path]:
    values = identity(experiment_id, attempt_id)
    namespace = script_dir / "runs" / values["run_id"]
    private_namespace = script_dir / "private" / values["run_id"]
    paths = {
        "namespace": namespace,
        "attempt": namespace / attempt_id,
        "private_attempt": private_namespace / attempt_id,
        "selection": namespace / "selected-attempt.json",
    }
    return {name: reject_symlink_components(path, project_root) for name, path in paths.items()}


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            if key in PUBLIC_SENSITIVE_KEYS:
                violations.append(child_path)
            violations.extend(public_sensitive_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    return violations


def require_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def stage_identity_matches(
    value: dict[str, Any], expected: dict[str, Any], *, calibration: bool = False
) -> bool:
    expected_experiment = "EXP-059" if calibration else expected["experiment_id"]
    return (
        value.get("experiment_id") == expected_experiment
        and (
            not calibration
            or value.get("replication_parent_experiment_id") == expected["experiment_id"]
        )
        and value.get("run_id") == expected["run_id"]
        and value.get("attempt_id") == expected["attempt_id"]
        and value.get("model_seed") == expected["model_seed"]
        and value.get("seed_contract") == expected["seed_contract"]
    )


def validate_completion(
    name: str,
    path: Path,
    expected: dict[str, Any],
    *,
    project_root: Path,
    public_attempt: Path,
    private_attempt: Path,
) -> dict[str, Any]:
    spec = STAGES[name]
    checked = reject_symlink_components(path, project_root)
    if not checked.is_file():
        raise FileNotFoundError(checked)
    value = json.loads(checked.read_text(encoding="utf-8"))
    if value.get("schema_version") != spec["schema"] or value.get("status") != spec["status"]:
        raise ValueError(f"{name} completion schema/status drift")
    for key in ("run_id", "attempt_id", "model_seed", "seed_contract"):
        if value.get(key) != expected[key]:
            raise ValueError(f"{name} completion identity drift: {key}")
    if name == "calibration":
        if (
            value.get("experiment_id") != "EXP-059"
            or value.get("replication_parent_experiment_id") != expected["experiment_id"]
        ):
            raise ValueError("Calibration completion parent identity drift")
    elif value.get("experiment_id") != expected["experiment_id"]:
        raise ValueError(f"{name} completion experiment identity drift")
    records = value.get("artifacts")
    if not isinstance(records, dict) or set(records) != spec["artifacts"]:
        raise ValueError(f"{name} completion artifact inventory drift")
    artifact_paths: dict[str, Path] = {}
    for artifact_name, record in records.items():
        artifact_path = require_record(record, project_root)
        artifact_paths[artifact_name] = artifact_path
        if not (
            artifact_path.is_relative_to(public_attempt)
            or artifact_path.is_relative_to(private_attempt)
            or artifact_path.parent == project_root / "experiments" / "stack-overflow-emotion-gold" / "oof-router" / "configs"
        ):
            raise ValueError(f"{name} artifact is outside the matching attempt/config roots")
    top_config = value.get("config")
    if top_config is not None:
        config_path = require_record(top_config, project_root)
        expected_config_dir = (
            project_root
            / "experiments"
            / "stack-overflow-emotion-gold"
            / "oof-router"
            / "configs"
        )
        if config_path.parent != expected_config_dir:
            raise ValueError(f"{name} top-level config is outside the canonical config root")
    if name == "oof":
        run = require_json(artifact_paths["run"])
        verification = require_json(artifact_paths["final_verification"])
        verified = verification.get("verified_artifacts", {})
        if (
            run.get("status") != "CompletedAwaitingVerification"
            or not stage_identity_matches(run, expected)
            or verification.get("status") != "Passed"
            or int(verification.get("failed_count", -1)) != 0
            or not stage_identity_matches(verification, expected)
            or verified.get("config") != top_config
            or verified.get("run") != records["run"]
            or verified.get("summary") != records["summary"]
            or verified.get("paired_oof_private") != records["paired_oof_private"]
        ):
            raise ValueError("OOF completion is not bound to a Passed final verification")
    elif name == "calibration":
        run = require_json(artifact_paths["exp059_run"])
        verification = require_json(artifact_paths["exp059_verification"])
        parameters = require_json(artifact_paths["exp059_calibration_parameters"])
        verified = verification.get("verified_artifacts", {})
        if (
            run.get("status") != "CompletedAwaitingVerification"
            or not stage_identity_matches(run, expected, calibration=True)
            or verification.get("status") != "Passed"
            or int(verification.get("failed_count", -1)) != 0
            or not stage_identity_matches(verification, expected, calibration=True)
            or not stage_identity_matches(parameters, expected, calibration=True)
            or verified.get("config") != records["config"]
            or verified.get("run") != records["exp059_run"]
            or verified.get("calibration_parameters")
            != records["exp059_calibration_parameters"]
        ):
            raise ValueError("Calibration completion is not bound to a Passed final verification")
    else:
        run = require_json(artifact_paths["run"])
        verification = require_json(artifact_paths["final_verification"])
        selected = require_json(artifact_paths["selected_operating_point"])
        policies = selected.get("policies", {})
        policy_inventory_valid = (
            isinstance(policies, dict)
            and set(policies) == set(DEPLOYABLE_POLICIES)
        )
        primary = policies.get("logistic_router", {}) if policy_inventory_valid else {}
        candidate = primary.get("candidate", {}) if isinstance(primary, dict) else {}
        passed = primary.get("passed")
        expected_decision = "Pass" if passed is True else "Fail"
        overall = selected.get("overall", {})
        verified = verification.get("verified_artifacts", {})
        selected_identity_valid = (
            selected.get("schema_version") == "exp-router-selected-operating-point-v2"
            and selected.get("experiment_id") == expected["experiment_id"]
            and selected.get("run_id") == expected["run_id"]
            and selected.get("attempt_id") == expected["attempt_id"]
            and selected.get("model_seed") == expected["model_seed"]
        )
        heuristic_roles_valid = policy_inventory_valid and all(
            isinstance(policies[policy], dict)
            and policies[policy].get("evidence_role") == "descriptive_only"
            and policies[policy].get("passed") is False
            for policy in ("m1_max_entropy", "m1_threshold_proximity")
        )
        primary_valid = (
            selected_identity_valid
            and policy_inventory_valid
            and heuristic_roles_valid
            and isinstance(passed, bool)
            and selected.get("primary_policy") == "logistic_router"
            and float(selected.get("primary_nominal_call_rate", -1)) == 0.15
            and float(candidate.get("target_call_rate", -1)) == 0.15
            and primary.get("evidence_role") == "primary"
            and overall.get("decision") == expected_decision
            and overall.get("selected_policy") == "logistic_router"
            and overall.get("selected_candidate") == candidate
        )
        if (
            run.get("status") != "CompletedAwaitingVerification"
            or not stage_identity_matches(run, expected)
            or run.get("decision") != expected_decision
            or run.get("public_outputs", {}).get("selected_operating_point_json")
            != records["selected_operating_point"]
            or verification.get("status") != "Passed"
            or int(verification.get("failed_count", -1)) != 0
            or not stage_identity_matches(verification, expected)
            or verified.get("config") != records["config"]
            or verified.get("run") != records["run"]
            or verified.get("private_router_oof") != records["private_router_oof"]
            or not primary_valid
            or value.get("primary_gate_passed") is not passed
            or value.get("decision") != expected_decision
        ):
            raise ValueError("Router completion is not bound to the verified frozen primary gate")
    if public_sensitive_paths(value):
        raise ValueError(f"{name} completion contains row-level public fields")
    return value


def validate_attempt(
    experiment_id: str,
    attempt_id: str,
    *,
    script_dir: Path = SCRIPT_DIR,
    project_root: Path = PROJECT_ROOT,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Path]]:
    expected = identity(experiment_id, attempt_id)
    paths = attempt_paths(
        experiment_id, attempt_id, script_dir=script_dir, project_root=project_root
    )
    if not paths["attempt"].is_dir() or not paths["private_attempt"].is_dir():
        raise FileNotFoundError("Matching public/private attempt directories are required")
    if os.path.lexists(paths["selection"]):
        raise FileExistsError("A selected attempt already exists")
    completions: dict[str, Any] = {}
    completion_paths: dict[str, Path] = {}
    for name, spec in STAGES.items():
        path = paths["attempt"] / spec["relative"]
        completion_paths[name] = path
        completions[name] = validate_completion(
            name,
            path,
            expected,
            project_root=project_root,
            public_attempt=paths["attempt"],
            private_attempt=paths["private_attempt"],
        )
    router = completions["router"]
    passed = router.get("primary_gate_passed")
    decision = router.get("decision")
    if not isinstance(passed, bool) or decision != ("Pass" if passed else "Fail"):
        raise ValueError("Router completion primary decision drift")
    selection = {
        "schema_version": "exp-router-replication-selection-v1",
        **expected,
        "status": "Selected",
        "selected_at_utc": utc_now(),
        "primary_policy": "logistic_router",
        "primary_nominal_call_rate": 0.15,
        "primary_gate_passed": passed,
        "decision": decision,
        "finalizer": artifact(
            script_dir / "finalize_router_replication_attempt.py", project_root
        ),
        "completions": {
            name: artifact(path, project_root) for name, path in completion_paths.items()
        },
        "stage_artifacts": {
            name: {
                **({"config": completions[name]["config"]} if name == "oof" else {}),
                **completions[name]["artifacts"],
            }
            for name in STAGES
        },
        "claim_boundary": (
            "Selects one verified same-train seed attempt only; EXP-063 alone may form the "
            "two-seed replication decision."
        ),
    }
    if public_sensitive_paths(selection):
        raise ValueError("Selection record contains row-level fields")
    return selection, completions, paths


def create_json_once(path: Path, value: Any) -> None:
    if os.path.lexists(path):
        raise FileExistsError(path)
    payload = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
        os.link(temporary, path)
    finally:
        if os.path.lexists(temporary):
            temporary.unlink()


def finalize_attempt(
    experiment_id: str,
    attempt_id: str,
    *,
    script_dir: Path = SCRIPT_DIR,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    selection, _completions, paths = validate_attempt(
        experiment_id, attempt_id, script_dir=script_dir, project_root=project_root
    )
    create_json_once(paths["selection"], selection)
    return selection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-id", choices=sorted(REGISTERED), required=True)
    parser.add_argument("--attempt-id", required=True)
    args = parser.parse_args()
    result = finalize_attempt(args.experiment_id, args.attempt_id)
    print(json.dumps({"status": result["status"], "decision": result["decision"]}, sort_keys=True))


if __name__ == "__main__":
    main()
