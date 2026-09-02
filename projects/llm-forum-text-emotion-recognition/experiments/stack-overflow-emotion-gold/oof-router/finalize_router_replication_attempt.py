#!/usr/bin/env python3
"""Atomically select one fully verified EXP-061/062 attempt.

This finalizer does not import any analysis runner or verifier.  It only validates
the three immutable stage-completion records and their artifact hashes, then
creates the experiment-level selection marker once.
"""

from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
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
            "exp059_verification_summary",
            "exp059_calibration_parameters",
            "paired_oof_private",
            "private_calibration",
            "public_outputs",
            "frozen_sources",
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
CALIBRATION_PUBLIC_OUTPUTS = {
    "calibration_parameters",
    "calibration_metrics",
    "classification_metrics",
    "oracle_summary",
    "abstention_gates",
    "bootstrap",
    "reliability_bins",
    "risk_coverage",
    "label_retention",
    "random_rejection",
    "reliability_figure",
    "risk_coverage_figure",
    "report",
}
CALIBRATION_FROZEN_SOURCES = {"config", "protocol", "runner", "verifier", "tests"}
RECOVERY_EXPERIMENT_ID = "EXP-061"
RECOVERY_ATTEMPT_ID = "attempt-1"
RECOVERY_RQ_ID = "RQ-S3"
RECOVERY_STAGE = "pre-qwen-router-replication"
RECOVERY_ATTEMPT2_CLAIM_BOUNDARY = (
    "Independent verification of unchanged seed-43 train-OOF router evidence under "
    "Incident-001's sole SHA-bound clerical config overlay; no validation, test, "
    "model, raw-text, deployment-generalization, or mechanism claim."
)
RECOVERY_COMPLETION_NEXT_GATE = (
    "Finalizer must bind OOF, EXP-059, router completion, and recovery lineage."
)
RECOVERY_COMPLETION_CLAIM_BOUNDARY = (
    "Completes one independently recovered seed-43 train-only router stage; not a "
    "cross-seed claim."
)
RECOVERY_PYTHON = "/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python"
RECOVERY_VERIFICATION_NAME = "verification-attempt-2.json"
RECOVERY_SUMMARY_NAME = "VERIFICATION-SUMMARY-ATTEMPT-2.md"
STANDARD_VERIFICATION_NAME = "verification.json"
RECOVERY_FULL_POLICIES = (
    "m1_only",
    "m3_only",
    "m1_max_entropy",
    "m1_threshold_proximity",
    "logistic_router",
)
RECOVERY_MODE_PATHS = (
    (Path("router"), "directory", 0o700, 0o755),
    (Path("router/frozen-sources"), "directory", 0o700, 0o755),
    (Path("router/REPORT.md"), "file", 0o600, 0o644),
    (Path("router/bootstrap.json"), "file", 0o600, 0o644),
    (Path("router/call-rate-performance.csv"), "file", 0o600, 0o644),
    (Path("router/call-rate-performance.png"), "file", 0o600, 0o644),
    (Path("router/feature-contract.json"), "file", 0o600, 0o644),
    (Path("router/fold-summary.csv"), "file", 0o600, 0o644),
    (Path("router/policy-comparisons.csv"), "file", 0o600, 0o644),
    (Path("router/positive-label-retention.csv"), "file", 0o600, 0o644),
    (Path("router/random-routing.csv"), "file", 0o600, 0o644),
    (Path("router/routed-risk-coverage.csv"), "file", 0o600, 0o644),
    (Path("router/routed-risk-coverage.png"), "file", 0o600, 0o644),
    (Path("router/router-discrimination.json"), "file", 0o600, 0o644),
    (Path("router/run.json"), "file", 0o600, 0o644),
    (Path("router/selected-operating-point.json"), "file", 0o600, 0o644),
)
RECOVERY_ATTEMPT1_FAILURES = {
    "config.router",
    "permissions.public_root",
    "permissions.public.REPORT.md",
    "permissions.public.bootstrap.json",
    "permissions.public.call-rate-performance.csv",
    "permissions.public.call-rate-performance.png",
    "permissions.public.feature-contract.json",
    "permissions.public.fold-summary.csv",
    "permissions.public.frozen-sources",
    "permissions.public.policy-comparisons.csv",
    "permissions.public.positive-label-retention.csv",
    "permissions.public.random-routing.csv",
    "permissions.public.routed-risk-coverage.csv",
    "permissions.public.routed-risk-coverage.png",
    "permissions.public.router-discrimination.json",
    "permissions.public.run.json",
    "permissions.public.selected-operating-point.json",
}
RECOVERY_CHECK_NAMES = (
    "recovery.original_failed_lineage",
    "recovery.public_modes_normalized",
    "recovery.public_content_unchanged",
    "recovery.private_artifacts_unchanged",
    "recovery.mirrors_distinct",
    "recovery.mirror_a_fresh_clean",
    "recovery.mirror_b_fresh_clean",
    "recovery.base_verifier_unchanged",
    "recovery.mirror_a_only_config_failed",
    "recovery.overlay_sha_bound_once",
    "recovery.mirror_b_all_passed",
    "recovery.check_names_same_order",
    "recovery.runner_not_imported",
)
RECOVERY_TREE_DIGEST_ALGORITHM = (
    "sha256(canonical-json(sorted(relative_path,bytes,sha256))); "
    "exclude exact router-root-relative paths verification-attempt-2.json, "
    "VERIFICATION-SUMMARY-ATTEMPT-2.md, router-complete.json"
)
RECOVERY_APPEND_ONLY_PATHS = {
    Path(RECOVERY_VERIFICATION_NAME),
    Path(RECOVERY_SUMMARY_NAME),
    Path("router-complete.json"),
}
RECOVERY_ATTEMPT2_INDEPENDENCE = {
    "base_verifier_unchanged": True,
    "recovery_verifier_runner_import_absent": True,
    "fresh_mirror_a": True,
    "fresh_mirror_b": True,
    "mirrors_distinct": True,
    "raw_exp058_recomputed_in_both": True,
    "nested_thresholds_recomputed_in_both": True,
    "scalers_and_routers_refit_in_both": True,
    "public_and_private_outputs_recomputed_in_both": True,
}
RECOVERY_MIRROR_METADATA_KEYS = {
    "fresh_project_root",
    "project_root_mode",
    "canonical_layout",
    "copy_only",
    "copied_file_count",
    "copy_manifest_sha256",
    "no_symlinks",
    "no_hardlinks",
    "instance_token_sha256",
    "overlay_enabled",
    "overlay_load_count",
    "matching_sha_load_count",
    "overlay_input_sha256",
    "cleaned",
}
PUBLIC_SENSITIVE_KEYS = {
    "component_id",
    "component_ids",
    "feature_matrix",
    "features",
    "fold_id",
    "fold_ids",
    "gold",
    "logit",
    "logits",
    "prediction",
    "predictions",
    "probability",
    "probabilities",
    "feature",
    "router_targets",
    "route_mask",
    "route_masks",
    "route_score",
    "route_scores",
    "sample_id",
    "sample_ids",
    "target",
    "targets",
    "raw_text",
    "text",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_canonical_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo == timezone.utc and parsed.isoformat() == value


def canonical_utc_datetime(value: Any) -> datetime:
    if not is_canonical_utc_timestamp(value):
        raise ValueError("Timestamp must be canonical ISO-8601 UTC")
    return datetime.fromisoformat(value)


def is_exact_int(value: Any) -> bool:
    return type(value) is int


def exact_check_rows(value: Any, expected_count: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) == expected_count
        and all(
            isinstance(row, dict)
            and set(row) == {"name", "passed", "detail"}
            and type(row["name"]) is str
            and type(row["passed"]) is bool
            for row in value
        )
    )


def exact_typed_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(
            exact_typed_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            exact_typed_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    return left == right


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
    if not (
        type(record["path"]) is str
        and type(record["bytes"]) is int
        and record["bytes"] >= 0
        and type(record["sha256"]) is str
        and SHA256_RE.fullmatch(record["sha256"])
    ):
        raise ValueError("Artifact record field types are invalid")
    digest = record["sha256"]
    relative = Path(record["path"])
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        raise ValueError("Artifact path must be normalized and project-relative")
    path = reject_symlink_components(project_root / relative, project_root)
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != record["bytes"] or sha256(path) != digest:
        raise ValueError(f"Artifact record drift: {relative}")
    return path


def iter_artifact_records(value: Any):
    if isinstance(value, dict):
        if {"path", "bytes", "sha256"}.issubset(value):
            yield value
        else:
            for child in value.values():
                yield from iter_artifact_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_artifact_records(child)


def recovery_mirror_copy_manifest(
    config: dict[str, Any],
    run: dict[str, Any],
    *,
    formal_config_path: Path,
    run_path: Path,
    base_verifier_path: Path,
    canonical_runner_path: Path,
    project_root: Path,
) -> list[dict[str, Any]]:
    sources = {
        reject_symlink_components(formal_config_path, project_root),
        reject_symlink_components(run_path, project_root),
        reject_symlink_components(base_verifier_path, project_root),
        reject_symlink_components(canonical_runner_path, project_root),
    }
    for record in (*iter_artifact_records(config), *iter_artifact_records(run)):
        sources.add(require_record(record, project_root))
    router_dir = run_path.parent
    forbidden = {
        router_dir / STANDARD_VERIFICATION_NAME,
        router_dir / "VERIFICATION-SUMMARY.md",
        router_dir / RECOVERY_VERIFICATION_NAME,
        router_dir / RECOVERY_SUMMARY_NAME,
        router_dir / "router-complete.json",
        router_dir.parent.parent / "selected-attempt.json",
    }
    if sources & forbidden:
        raise ValueError("Recovery mirror source inventory includes governance sidecars")
    return [
        artifact(path, project_root)
        for path in sorted(sources, key=lambda path: display_path(path, project_root))
    ]


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


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def recursive_diff(left: Any, right: Any, prefix: str = "$") -> list[dict[str, Any]]:
    if type(left) is not type(right):
        return [{"path": prefix, "before": left, "after": right}]
    if isinstance(left, dict):
        rows: list[dict[str, Any]] = []
        for key in sorted(set(left) | set(right)):
            child = f"{prefix}.{key}"
            if key not in left:
                rows.append({"path": child, "before": None, "after": right[key]})
            elif key not in right:
                rows.append({"path": child, "before": left[key], "after": None})
            else:
                rows.extend(recursive_diff(left[key], right[key], child))
        return rows
    if isinstance(left, list):
        return [] if left == right else [{"path": prefix, "before": left, "after": right}]
    return [] if left == right else [{"path": prefix, "before": left, "after": right}]


def recovery_public_tree_digest(router_dir: Path, project_root: Path) -> dict[str, Any]:
    checked = reject_symlink_components(router_dir, project_root)
    rows: list[dict[str, Any]] = []
    for path in sorted(checked.rglob("*")):
        reject_symlink_components(path, project_root)
        relative = path.relative_to(checked)
        if path.is_file() and relative not in RECOVERY_APPEND_ONLY_PATHS:
            rows.append(
                {
                    "path": str(relative),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    return {"file_count": len(rows), "sha256": canonical_digest(rows)}


def verifier_has_no_runner_import(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    runner_module = "run_" + "exp060_router"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            runner_module in alias.name for alias in node.names
        ):
            return False
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and runner_module in node.module
        ):
            return False
    return True


def validate_fresh_mirror_evidence(
    value: Any,
    *,
    overlay: bool,
    expected_copy_count: int,
    expected_copy_digest: str,
) -> None:
    if not isinstance(value, dict):
        raise ValueError("Recovery fresh-mirror evidence must be an object")
    positive = (
        "fresh_project_root",
        "canonical_layout",
        "copy_only",
        "no_symlinks",
        "no_hardlinks",
        "cleaned",
    )
    if not (
        set(value) == RECOVERY_MIRROR_METADATA_KEYS
        and all(value.get(key) is True for key in positive)
        and value.get("project_root_mode") == "0o700"
        and is_exact_int(value.get("copied_file_count"))
        and value.get("copied_file_count") == expected_copy_count
        and value.get("copy_manifest_sha256") == expected_copy_digest
        and type(value.get("instance_token_sha256")) is str
        and SHA256_RE.fullmatch(value.get("instance_token_sha256"))
        and value.get("overlay_enabled") is overlay
        and is_exact_int(value.get("overlay_load_count"))
        and value.get("overlay_load_count") == (1 if overlay else 0)
        and is_exact_int(value.get("matching_sha_load_count"))
        and value.get("matching_sha_load_count") == (2 if overlay else 0)
        and (
            (
                overlay
                and type(value.get("overlay_input_sha256")) is str
                and SHA256_RE.fullmatch(value.get("overlay_input_sha256"))
            )
            or (not overlay and value.get("overlay_input_sha256") is None)
        )
    ):
        raise ValueError("Recovery fresh-mirror evidence drift")


def render_recovery_summary(verification: dict[str, Any]) -> bytes:
    if verification.get("status") != "Passed":
        raise ValueError("Recovery summary requires a Passed attempt-2 verification")
    text = "\n".join(
        [
            "# EXP-061 / EXP-060 Final Router Verification Attempt 2",
            "",
            "- Status: `Passed`",
            "- Main verifier checks: `4434 / 4434`",
            "- Mirror A (unchanged config): `4433 / 4434`; sole failure `config.router`",
            "- Mirror B (registered SHA-bound overlay): `4434 / 4434`",
            "- Scientific analysis rerun: `false`",
            "- Original Failed verification and summary: preserved",
            "- Validation/test/model/raw-text access: `false`",
            "",
            verification["claim_boundary"],
            "",
        ]
    )
    return (text + "\n").encode("utf-8")


def read_bound_regular_file(
    path: Path, *, project_root: Path, expected_mode: int
) -> bytes:
    checked = reject_symlink_components(path, project_root)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise OSError("O_NOFOLLOW is required")
    descriptor = os.open(checked, os.O_RDONLY | nofollow)
    try:
        lexical_before = os.lstat(checked)
        observed_before = os.fstat(descriptor)
        with os.fdopen(descriptor, "rb", closefd=False) as source:
            payload = source.read()
        observed_after = os.fstat(descriptor)
        lexical_after = os.lstat(checked)
        identity = (observed_before.st_dev, observed_before.st_ino)
        if not (
            stat.S_ISREG(observed_before.st_mode)
            and stat.S_IMODE(observed_before.st_mode) == expected_mode
            and observed_before.st_nlink == 1
            and (lexical_before.st_dev, lexical_before.st_ino) == identity
            and (observed_after.st_dev, observed_after.st_ino) == identity
            and (lexical_after.st_dev, lexical_after.st_ino) == identity
            and observed_after.st_size == observed_before.st_size == len(payload)
            and observed_after.st_nlink == observed_before.st_nlink
            and stat.S_IMODE(observed_after.st_mode) == expected_mode
        ):
            raise ValueError("Bound regular-file identity/mode drift")
        return payload
    finally:
        os.close(descriptor)


def validate_router_recovery(
    completion: dict[str, Any],
    verification: dict[str, Any],
    verification_path: Path,
    records: dict[str, Any],
    expected: dict[str, Any],
    *,
    project_root: Path,
    public_attempt: Path,
    private_attempt: Path,
) -> dict[str, Any]:
    """Independently validate the one registered EXP-061 Incident-001 recovery."""

    if not (
        expected["experiment_id"] == RECOVERY_EXPERIMENT_ID
        and expected["attempt_id"] == RECOVERY_ATTEMPT_ID
        and verification_path.name == RECOVERY_VERIFICATION_NAME
        and verification_path == public_attempt / "router" / RECOVERY_VERIFICATION_NAME
        and completion.get("verification_attempt") == 2
    ):
        raise PermissionError("Router recovery is restricted to EXP-061 attempt-1")
    canonical_completion_path = public_attempt / "router" / "router-complete.json"
    if json.loads(
        read_bound_regular_file(
            canonical_completion_path, project_root=project_root, expected_mode=0o644
        )
    ) != completion:
        raise ValueError("Router recovery completion path/mode/content drift")
    if json.loads(
        read_bound_regular_file(
            verification_path, project_root=project_root, expected_mode=0o644
        )
    ) != verification:
        raise ValueError("Router recovery attempt-2 path/mode/content drift")
    expected_completion_keys = {
        "schema_version", "experiment_id", "stage", "run_id", "attempt_id",
        "model_seed", "seed_contract", "status", "completed_at_utc", "decision",
        "primary_gate_passed", "verification_attempt", "recovery_lineage", "artifacts",
        "next_gate", "claim_boundary",
    }
    if not (
        set(completion) == expected_completion_keys
        and is_canonical_utc_timestamp(completion.get("completed_at_utc"))
        and completion.get("next_gate") == RECOVERY_COMPLETION_NEXT_GATE
        and completion.get("claim_boundary") == RECOVERY_COMPLETION_CLAIM_BOUNDARY
    ):
        raise ValueError("Router recovery completion top-level schema drift")

    lineage = completion.get("recovery_lineage")
    if not isinstance(lineage, dict) or set(lineage) != {
        "incident_id",
        "original_failed_verification",
        "original_failed_summary",
        "amendment_config",
        "amendment_protocol",
        "passed_verification",
        "passed_summary",
    }:
        raise ValueError("Router completion recovery-lineage schema drift")
    expected_paths = {
        "original_failed_verification": public_attempt / "router" / "verification.json",
        "original_failed_summary": public_attempt / "router" / "VERIFICATION-SUMMARY.md",
        "amendment_config": project_root
        / "experiments/stack-overflow-emotion-gold/oof-router/configs/"
        "exp-061-seed-43-router-replication-router-verification-attempt-2-amendment.json",
        "amendment_protocol": project_root
        / "experiments/stack-overflow-emotion-gold/protocols/"
        "exp-061-exp060-final-verification-attempt-2-amendment.md",
        "passed_verification": verification_path,
        "passed_summary": public_attempt / "router" / RECOVERY_SUMMARY_NAME,
    }
    lineage_paths: dict[str, Path] = {}
    for key, expected_path in expected_paths.items():
        lineage_paths[key] = require_record(lineage.get(key), project_root)
        if lineage_paths[key] != expected_path:
            raise ValueError(f"Router recovery lineage path drift: {key}")
    if lineage.get("incident_id") != "001":
        raise ValueError("Router recovery incident id drift")

    amendment = require_json(lineage_paths["amendment_config"])
    expected_amendment_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "model_seed",
        "incident_id", "authorization", "implementation", "target",
        "clerical_overlay", "public_mode_normalization", "private_invariant",
        "outputs", "commands",
    }
    expected_authorization = {
        "verification_attempt": 2,
        "public_mode_metadata_repair": True,
        "scientific_analysis_rerun": False,
        "private_artifact_mutation": False,
        "validation_access": False,
        "test_access": False,
        "model_loading_or_forward": False,
        "raw_text_access": False,
        "seed44_execution": False,
    }
    if not (
        set(amendment) == expected_amendment_keys
        and amendment.get("schema_version")
        == "exp-router-verification-attempt-2-amendment-config-v1"
        and amendment.get("experiment_id") == RECOVERY_EXPERIMENT_ID
        and amendment.get("run_id") == expected["run_id"]
        and amendment.get("attempt_id") == RECOVERY_ATTEMPT_ID
        and amendment.get("model_seed") == 43
        and amendment.get("incident_id") == "001"
        and exact_typed_equal(amendment.get("authorization"), expected_authorization)
    ):
        raise ValueError("Router recovery amendment identity/authorization drift")
    expected_outputs = {
        "verification": display_path(verification_path, project_root),
        "summary": display_path(
            public_attempt / "router" / "VERIFICATION-SUMMARY-ATTEMPT-2.md",
            project_root,
        ),
        "completion": display_path(
            public_attempt / "router" / "router-complete.json", project_root
        ),
        "selection": display_path(
            public_attempt.parent / "selected-attempt.json", project_root
        ),
    }
    if amendment.get("outputs") != expected_outputs:
        raise ValueError("Router recovery amendment output paths drift")
    recovery_command = (
        RECOVERY_PYTHON
        + " experiments/stack-overflow-emotion-gold/oof-router/"
        + "verify_"
        + "exp060_router_attempt2.py --scope "
    )
    expected_commands = {
        scope: recovery_command + scope
        for scope in ("normalize", "final", "complete", "completion")
    }
    if amendment.get("commands") != expected_commands:
        raise ValueError("Router recovery amendment commands drift")

    implementation = amendment.get("implementation", {})
    implementation_root = (
        project_root / "experiments/stack-overflow-emotion-gold/oof-router"
    )
    required_implementation = {
        "amendment_protocol": expected_paths["amendment_protocol"],
        "base_verifier": implementation_root / ("verify_" + "exp060_router.py"),
        "recovery_verifier": implementation_root
        / ("verify_" + "exp060_router_attempt2.py"),
        "recovery_tests": project_root
        / "experiments/stack-overflow-emotion-gold/oof-router/tests/test_exp060_router_attempt2.py",
        "finalizer": project_root
        / "experiments/stack-overflow-emotion-gold/oof-router/finalize_router_replication_attempt.py",
        "finalizer_tests": project_root
        / "experiments/stack-overflow-emotion-gold/oof-router/tests/test_finalize_router_recovery_attempt.py",
    }
    if set(implementation) != set(required_implementation):
        raise ValueError("Router recovery implementation inventory drift")
    implementation_paths: dict[str, Path] = {}
    for key, expected_path in required_implementation.items():
        implementation_paths[key] = require_record(implementation[key], project_root)
        if implementation_paths[key] != expected_path:
            raise ValueError(f"Router recovery implementation path drift: {key}")
    if (
        lineage["amendment_protocol"] != implementation["amendment_protocol"]
        or not verifier_has_no_runner_import(implementation_paths["base_verifier"])
        or not verifier_has_no_runner_import(implementation_paths["recovery_verifier"])
    ):
        raise ValueError("Router recovery verifier independence drift")

    target = amendment.get("target", {})
    expected_target_paths = {
        "formal_config": project_root
        / "experiments/stack-overflow-emotion-gold/oof-router/configs/"
        "exp-061-seed-43-router-replication-router-formal-attempt-1.json",
        "run": public_attempt / "router/run.json",
        "selected_operating_point": public_attempt
        / "router/selected-operating-point.json",
        "paired_oof": private_attempt / "paired-oof.npz",
        "private_router_oof": private_attempt / "router/router-oof.npz",
        "attempt_1_failed_verification": expected_paths["original_failed_verification"],
        "attempt_1_failed_summary": expected_paths["original_failed_summary"],
    }
    completion_paths = {
        "formal_config": require_record(records["config"], project_root),
        "run": require_record(records["run"], project_root),
        "selected_operating_point": require_record(
            records["selected_operating_point"], project_root
        ),
        "private_router_oof": require_record(
            records["private_router_oof"], project_root
        ),
    }
    if any(
        completion_paths[key] != expected_target_paths[key]
        for key in completion_paths
    ):
        raise ValueError("Router recovery completion artifact canonical path drift")
    if set(target) != set(expected_target_paths):
        raise ValueError("Router recovery target inventory drift")
    for key, expected_path in expected_target_paths.items():
        if require_record(target[key], project_root) != expected_path:
            raise ValueError(f"Router recovery target path drift: {key}")
    if (
        lineage["original_failed_verification"] != target["attempt_1_failed_verification"]
        or lineage["original_failed_summary"] != target["attempt_1_failed_summary"]
    ):
        raise ValueError("Router recovery Failed-lineage record drift")

    original_config = require_json(expected_target_paths["formal_config"])
    effective_config = json.loads(json.dumps(original_config))
    if not (
        original_config.get("router", {}).get("policies") == list(DEPLOYABLE_POLICIES)
        and original_config.get("router", {}).get("deployable_policy_order")
        == list(DEPLOYABLE_POLICIES)
        and original_config.get("rq_id") == RECOVERY_RQ_ID
        and original_config.get("stage") == RECOVERY_STAGE
        and original_config.get("seed_contract") == expected["seed_contract"]
        and completion.get("stage") == original_config.get("stage")
    ):
        raise ValueError("Router recovery original three/three config state drift")
    effective_config["router"]["policies"] = list(RECOVERY_FULL_POLICIES)
    expected_diff = [
        {
            "path": "$.router.policies",
            "before": list(DEPLOYABLE_POLICIES),
            "after": list(RECOVERY_FULL_POLICIES),
        }
    ]
    overlay = amendment.get("clerical_overlay", {})
    expected_overlay = {
        "operation": "replace",
        "json_pointer": "/router/policies",
        "match_input_sha256": target["formal_config"]["sha256"],
        "before": list(DEPLOYABLE_POLICIES),
        "after": list(RECOVERY_FULL_POLICIES),
        "deployable_policy_order_unchanged": list(DEPLOYABLE_POLICIES),
        "recursive_diff": expected_diff,
        "maximum_changed_nodes": 1,
    }
    if not (
        original_config.get("schema_version") == "exp-router-replication-config-v2"
        and original_config.get("experiment_id") == RECOVERY_EXPERIMENT_ID
        and original_config.get("rq_id") == RECOVERY_RQ_ID
        and original_config.get("stage") == RECOVERY_STAGE
        and original_config.get("run_id") == expected["run_id"]
        and original_config.get("attempt_id") == RECOVERY_ATTEMPT_ID
        and original_config.get("seed_contract") == expected["seed_contract"]
        and exact_typed_equal(overlay, expected_overlay)
        and recursive_diff(original_config, effective_config) == expected_diff
    ):
        raise ValueError("Router recovery unique clerical overlay drift")

    original_failed = require_json(expected_paths["original_failed_verification"])
    original_checks = original_failed.get("checks", [])
    original_names = [str(row.get("name")) for row in original_checks]
    original_failures = {
        str(row.get("name")) for row in original_checks if row.get("passed") is not True
    }
    if not (
        original_failed.get("schema_version") == "exp-router-formal-verification-v2"
        and original_failed.get("scope") == "final"
        and original_failed.get("status") == "Failed"
        and original_failed.get("rq_id") == RECOVERY_RQ_ID
        and original_failed.get("stage") == RECOVERY_STAGE
        and is_canonical_utc_timestamp(original_failed.get("verified_at_utc"))
        and is_exact_int(original_failed.get("passed_count"))
        and original_failed.get("passed_count") == 4417
        and is_exact_int(original_failed.get("failed_count"))
        and original_failed.get("failed_count") == 17
        and len(original_checks) == 4434
        and len(set(original_names)) == 4434
        and original_failures == RECOVERY_ATTEMPT1_FAILURES
        and stage_identity_matches(original_failed, expected)
    ):
        raise ValueError("Router recovery original Failed result drift")

    expected_verified = {
        "config": target["formal_config"],
        "run": target["run"],
        "input": target["paired_oof"],
        "private_router_oof": target["private_router_oof"],
    }
    expected_split = {
        "accessed_splits": ["train-oof"],
        "validation_accessed": False,
        "test_inputs_accessed": False,
        "test_labels_accessed": False,
        "raw_text_accessed": False,
        "model_loaded_or_forward_run": False,
    }
    expected_base_independence = {
        "runner_imported": False,
        "raw_exp058_recomputation": True,
        "nested_thresholds_recomputed": True,
        "scalers_and_routers_refit": True,
        "public_and_private_outputs_recomputed": True,
    }
    if not (
        original_failed.get("verified_artifacts") == expected_verified
        and exact_typed_equal(original_failed.get("split_access"), expected_split)
        and exact_typed_equal(
            original_failed.get("independence"), expected_base_independence
        )
    ):
        raise ValueError("Router recovery original Failed verifier bindings drift")
    recovery_run = require_json(expected_target_paths["run"])
    if not (
        recovery_run.get("config") == target["formal_config"]
        and recovery_run.get("status") == "CompletedAwaitingVerification"
        and recovery_run.get("rq_id") == RECOVERY_RQ_ID
        and recovery_run.get("stage") == RECOVERY_STAGE
        and stage_identity_matches(recovery_run, expected)
        and recovery_run.get("decision") == completion.get("decision")
        and recovery_run.get("public_outputs", {}).get("selected_operating_point_json")
        == target["selected_operating_point"]
    ):
        raise ValueError("Router recovery run/config/result binding drift")
    canonical_runner_path = implementation_root / ("run_" + "exp060_router.py")
    canonical_runner = artifact(canonical_runner_path, project_root)
    frozen_sources = recovery_run.get("frozen_sources", {})
    if not isinstance(frozen_sources, dict) or "runner" not in frozen_sources:
        raise ValueError("Router recovery run has no frozen runner record")
    frozen_runner = frozen_sources["runner"]
    require_record(frozen_runner, project_root)
    if not (
        frozen_runner.get("bytes") == canonical_runner["bytes"]
        and frozen_runner.get("sha256") == canonical_runner["sha256"]
    ):
        raise ValueError("Canonical and run-frozen router runner bytes differ")
    expected_copy_manifest = recovery_mirror_copy_manifest(
        original_config,
        recovery_run,
        formal_config_path=expected_target_paths["formal_config"],
        run_path=expected_target_paths["run"],
        base_verifier_path=implementation_paths["base_verifier"],
        canonical_runner_path=canonical_runner_path,
        project_root=project_root,
    )
    expected_copy_count = len(expected_copy_manifest)
    expected_copy_digest = canonical_digest(expected_copy_manifest)
    top_keys = {
        "schema_version", "experiment_id", "rq_id", "stage", "run_id", "attempt_id",
        "model_seed", "seed_contract", "scope", "verification_attempt", "status",
        "runner_imported", "verified_at_utc", "passed_count", "failed_count", "checks",
        "independence", "verified_artifacts", "split_access", "recovery", "claim_boundary",
    }
    checks = verification.get("checks", [])
    names = [str(row.get("name")) for row in checks]
    independence = verification.get("independence", {})
    if not (
        set(verification) == top_keys
        and verification.get("schema_version")
        == "exp-router-formal-verification-attempt-2-v1"
        and verification.get("scope") == "final"
        and verification.get("verification_attempt") == 2
        and verification.get("status") == "Passed"
        and verification.get("runner_imported") is False
        and is_canonical_utc_timestamp(verification.get("verified_at_utc"))
        and verification.get("rq_id") == original_failed.get("rq_id") == RECOVERY_RQ_ID
        and verification.get("stage")
        == original_failed.get("stage")
        == original_config.get("stage")
        == recovery_run.get("stage")
        == RECOVERY_STAGE
        and verification.get("seed_contract")
        == original_failed.get("seed_contract")
        == original_config.get("seed_contract")
        == recovery_run.get("seed_contract")
        == expected["seed_contract"]
        and stage_identity_matches(verification, expected)
        and is_exact_int(verification.get("passed_count"))
        and verification.get("passed_count") == 4434
        and is_exact_int(verification.get("failed_count"))
        and verification.get("failed_count") == 0
        and exact_check_rows(checks, 4434)
        and names == original_names
        and all(row.get("passed") is True for row in checks)
        and exact_typed_equal(independence, RECOVERY_ATTEMPT2_INDEPENDENCE)
        and verification.get("verified_artifacts") == expected_verified
        and exact_typed_equal(verification.get("split_access"), expected_split)
        and verification.get("claim_boundary") == RECOVERY_ATTEMPT2_CLAIM_BOUNDARY
        and canonical_utc_datetime(original_failed.get("verified_at_utc"))
        <= canonical_utc_datetime(verification.get("verified_at_utc"))
        <= canonical_utc_datetime(completion.get("completed_at_utc"))
    ):
        raise ValueError("Router recovery Passed attempt-2 schema/check drift")
    if public_sensitive_paths(verification):
        raise ValueError("Router recovery Passed attempt-2 contains row-level fields")

    summary_path = lineage_paths["passed_summary"]
    if read_bound_regular_file(
        summary_path, project_root=project_root, expected_mode=0o644
    ) != render_recovery_summary(verification):
        raise ValueError("Router recovery attempt-2 summary path/mode/content drift")

    recovery = verification.get("recovery", {})
    recovery_keys = {
        "schema_version", "incident_id", "classification", "amendment_config",
        "amendment_protocol", "original_failed_verification", "original_failed_summary",
        "base_verifier", "recovery_verifier", "overlay", "mode_normalization",
        "recomputation", "recovery_checks",
    }
    if not (
        set(recovery) == recovery_keys
        and recovery.get("schema_version") == "exp-router-verification-recovery-evidence-v1"
        and recovery.get("incident_id") == "001"
        and recovery.get("classification") == "clerical_config_misencoding"
        and recovery.get("amendment_config") == lineage["amendment_config"]
        and recovery.get("amendment_protocol") == lineage["amendment_protocol"]
        and recovery.get("original_failed_verification")
        == lineage["original_failed_verification"]
        and recovery.get("original_failed_summary") == lineage["original_failed_summary"]
        and recovery.get("base_verifier") == implementation["base_verifier"]
        and recovery.get("recovery_verifier") == implementation["recovery_verifier"]
        and exact_typed_equal(
            recovery.get("overlay"),
            {**expected_overlay, "applied_load_count": 1},
        )
    ):
        raise ValueError("Router recovery evidence lineage/overlay drift")

    normalization = amendment.get("public_mode_normalization", {})
    pre_manifest = normalization.get("pre_manifest", [])
    expected_pre: list[dict[str, Any]] = []
    expected_after: list[dict[str, Any]] = []
    for (relative, kind, before_mode, after_mode), frozen in zip(
        RECOVERY_MODE_PATHS, pre_manifest, strict=True
    ):
        path = reject_symlink_components(public_attempt / relative, project_root)
        lexical = os.lstat(path)
        if kind == "file":
            payload = read_bound_regular_file(
                path, project_root=project_root, expected_mode=after_mode
            )
            observed_mode = stat.S_IMODE(os.lstat(path).st_mode)
        else:
            nofollow = getattr(os, "O_NOFOLLOW", None)
            odirectory = getattr(os, "O_DIRECTORY", None)
            if nofollow is None or odirectory is None:
                raise OSError("O_NOFOLLOW and O_DIRECTORY are required")
            descriptor = os.open(path, os.O_RDONLY | nofollow | odirectory)
            try:
                observed = os.fstat(descriptor)
                lexical_after = os.lstat(path)
                identity = (observed.st_dev, observed.st_ino)
                if not (
                    stat.S_ISDIR(lexical.st_mode)
                    and stat.S_ISDIR(observed.st_mode)
                    and stat.S_IMODE(observed.st_mode) == after_mode
                    and (lexical.st_dev, lexical.st_ino) == identity
                    and (lexical_after.st_dev, lexical_after.st_ino) == identity
                ):
                    raise ValueError(
                        f"Router recovery public directory drift: {relative}"
                    )
                observed_mode = stat.S_IMODE(observed.st_mode)
            finally:
                os.close(descriptor)
            payload = b""
        row: dict[str, Any] = {
            "path": display_path(path, project_root),
            "type": kind,
            "before_mode": f"0o{before_mode:o}",
            "after_mode": f"0o{after_mode:o}",
        }
        if kind == "file":
            row.update(
                {
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
        expected_pre.append(row)
        expected_after.append(
            {
                **row,
                "observed_mode": f"0o{observed_mode:o}",
                "matches_expected": observed_mode == after_mode,
            }
        )
    tree = recovery_public_tree_digest(public_attempt / "router", project_root)
    private_rows = [target["paired_oof"], target["private_router_oof"]]
    private_mode_specs = (
        (private_attempt.parent, "directory", 0o700),
        (private_attempt, "directory", 0o700),
        (expected_target_paths["paired_oof"], "file", 0o600),
        (private_attempt / "router", "directory", 0o700),
        (expected_target_paths["private_router_oof"], "file", 0o600),
    )
    private_modes = [
        {
            "path": display_path(path, project_root),
            "type": kind,
            "expected_mode": f"0o{expected_mode:o}",
            "observed_mode": f"0o{stat.S_IMODE(path.stat().st_mode):o}",
            "matches_expected": stat.S_IMODE(path.stat().st_mode) == expected_mode,
        }
        for path, kind, expected_mode in private_mode_specs
    ]
    private_digest = {
        "artifact_count": 2,
        "sha256": canonical_digest(private_rows),
        "artifacts": private_rows,
        "modes": private_modes,
    }
    mode_evidence = recovery.get("mode_normalization", {})
    expected_mode_keys = {
        "path_count", "content_tree_digest_algorithm", "before", "after",
        "content_tree_before", "content_tree_after", "private_before",
        "private_after",
    }
    if not (
        normalization == {
            "path_count": 16,
            "pre_manifest": expected_pre,
            "content_tree_digest_algorithm": RECOVERY_TREE_DIGEST_ALGORITHM,
            "content_tree_before": tree,
        }
        and amendment.get("private_invariant") == private_digest
        and isinstance(mode_evidence, dict)
        and set(mode_evidence) == expected_mode_keys
        and is_exact_int(mode_evidence.get("path_count"))
        and mode_evidence.get("path_count") == 16
        and mode_evidence.get("content_tree_digest_algorithm")
        == RECOVERY_TREE_DIGEST_ALGORITHM
        and mode_evidence.get("before") == expected_pre
        and mode_evidence.get("after") == expected_after
        and all(row["matches_expected"] for row in expected_after)
        and mode_evidence.get("content_tree_before") == tree
        and mode_evidence.get("content_tree_after") == tree
        and mode_evidence.get("private_before") == private_digest
        and mode_evidence.get("private_after") == private_digest
        and all(row["matches_expected"] for row in private_modes)
    ):
        raise ValueError("Router recovery exact mode/content/private invariant drift")

    recomputation = recovery.get("recomputation", {})
    mirror_a = recomputation.get("mirror_a", {})
    mirror_b = recomputation.get("mirror_b", {})
    checks_a = mirror_a.get("checks", [])
    validate_fresh_mirror_evidence(
        mirror_a.get("mirror"),
        overlay=False,
        expected_copy_count=expected_copy_count,
        expected_copy_digest=expected_copy_digest,
    )
    validate_fresh_mirror_evidence(
        mirror_b.get("mirror"),
        overlay=True,
        expected_copy_count=expected_copy_count,
        expected_copy_digest=expected_copy_digest,
    )
    recovery_rows = recovery.get("recovery_checks", [])
    expected_recomputation_keys = {
        "mirror_a", "mirror_b", "check_name_order_sha256"
    }
    expected_mirror_a_keys = {
        "role", "status", "passed_count", "failed_count", "checks",
        "independence", "verified_artifacts", "split_access", "mirror",
    }
    expected_mirror_b_keys = {
        "role", "status", "passed_count", "failed_count", "checks_location",
        "checks_sha256", "independence", "verified_artifacts", "split_access",
        "mirror",
    }
    if not (
        isinstance(recomputation, dict)
        and set(recomputation) == expected_recomputation_keys
        and isinstance(mirror_a, dict)
        and set(mirror_a) == expected_mirror_a_keys
        and mirror_a.get("role") == "unchanged_config_control"
        and mirror_a.get("status") == "Failed"
        and is_exact_int(mirror_a.get("passed_count"))
        and mirror_a.get("passed_count") == 4433
        and is_exact_int(mirror_a.get("failed_count"))
        and mirror_a.get("failed_count") == 1
        and exact_check_rows(checks_a, 4434)
        and [str(row.get("name")) for row in checks_a] == names
        and {str(row.get("name")) for row in checks_a if row.get("passed") is not True}
        == {"config.router"}
        and mirror_a.get("verified_artifacts") == expected_verified
        and exact_typed_equal(mirror_a.get("split_access"), expected_split)
        and exact_typed_equal(
            mirror_a.get("independence"), expected_base_independence
        )
        and isinstance(mirror_b, dict)
        and set(mirror_b) == expected_mirror_b_keys
        and mirror_b.get("role") == "sha_bound_overlay_recovery"
        and mirror_b.get("status") == "Passed"
        and is_exact_int(mirror_b.get("passed_count"))
        and mirror_b.get("passed_count") == 4434
        and is_exact_int(mirror_b.get("failed_count"))
        and mirror_b.get("failed_count") == 0
        and mirror_b.get("checks_location") == "$.checks"
        and mirror_b.get("checks_sha256") == canonical_digest(checks)
        and mirror_b.get("verified_artifacts") == expected_verified
        and exact_typed_equal(mirror_b.get("split_access"), expected_split)
        and exact_typed_equal(
            mirror_b.get("independence"), expected_base_independence
        )
        and exact_typed_equal(
            mirror_a.get("independence"), mirror_b.get("independence")
        )
        and recomputation.get("check_name_order_sha256") == canonical_digest(names)
        and mirror_a["mirror"]["instance_token_sha256"]
        != mirror_b["mirror"]["instance_token_sha256"]
        and mirror_a["mirror"]["copied_file_count"]
        == mirror_b["mirror"]["copied_file_count"]
        and mirror_a["mirror"]["copy_manifest_sha256"]
        == mirror_b["mirror"]["copy_manifest_sha256"]
        and mirror_b["mirror"]["overlay_input_sha256"] == target["formal_config"]["sha256"]
        and exact_typed_equal(
            recovery_rows,
            [
                {"name": name, "passed": True, "detail": None}
                for name in RECOVERY_CHECK_NAMES
            ],
        )
    ):
        raise ValueError("Router recovery dual-recomputation evidence drift")
    return lineage


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
        expected_nested_keys = None
        if name == "calibration" and artifact_name == "public_outputs":
            expected_nested_keys = CALIBRATION_PUBLIC_OUTPUTS
        elif name == "calibration" and artifact_name == "frozen_sources":
            expected_nested_keys = CALIBRATION_FROZEN_SOURCES
        if expected_nested_keys is not None:
            if not isinstance(record, dict) or set(record) != expected_nested_keys:
                raise ValueError(f"{name} {artifact_name} inventory drift")
            record_items = record.items()
        else:
            record_items = ((artifact_name, record),)
        for _record_name, artifact_record in record_items:
            artifact_path = require_record(artifact_record, project_root)
            if expected_nested_keys is None:
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
        expected_verified = {
            "config": records["config"],
            "run": records["exp059_run"],
            "calibration_parameters": records["exp059_calibration_parameters"],
            "paired_oof": records["paired_oof_private"],
            "private_output": records["private_calibration"],
            "public_outputs": records["public_outputs"],
            "frozen_sources": records["frozen_sources"],
        }
        if (
            run.get("status") != "CompletedAwaitingVerification"
            or not stage_identity_matches(run, expected, calibration=True)
            or run.get("config") != records["config"]
            or run.get("private_output") != records["private_calibration"]
            or run.get("public_outputs") != records["public_outputs"]
            or run.get("frozen_sources") != records["frozen_sources"]
            or verification.get("status") != "Passed"
            or int(verification.get("failed_count", -1)) != 0
            or not stage_identity_matches(verification, expected, calibration=True)
            or not stage_identity_matches(parameters, expected, calibration=True)
            or verified != expected_verified
        ):
            raise ValueError("Calibration completion is not bound to a Passed final verification")
    else:
        run = require_json(artifact_paths["run"])
        verification = require_json(artifact_paths["final_verification"])
        verification_name = artifact_paths["final_verification"].name
        if verification_name not in {STANDARD_VERIFICATION_NAME, RECOVERY_VERIFICATION_NAME}:
            raise ValueError("Router final-verification basename is not registered")
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
        if verification_name == RECOVERY_VERIFICATION_NAME:
            validate_router_recovery(
                value,
                verification,
                artifact_paths["final_verification"],
                records,
                expected,
                project_root=project_root,
                public_attempt=public_attempt,
                private_attempt=private_attempt,
            )
        elif "recovery_lineage" in value or value.get("verification_attempt") == 2:
            raise ValueError("Router recovery fields require the exact attempt-2 verification path")
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
        **(
            {"recovery_lineage": router["recovery_lineage"]}
            if "recovery_lineage" in router
            else {}
        ),
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
        with os.fdopen(descriptor, "wb", closefd=False) as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
            os.fchmod(target.fileno(), 0o644)
            os.fsync(target.fileno())
        held = os.fstat(descriptor)
        temporary_stat = os.lstat(temporary)
        if not (
            stat.S_ISREG(held.st_mode)
            and stat.S_IMODE(held.st_mode) == 0o644
            and (temporary_stat.st_dev, temporary_stat.st_ino)
            == (held.st_dev, held.st_ino)
        ):
            raise RuntimeError("Finalizer temporary output identity/mode drift")
        os.link(temporary, path)
        temporary.unlink()
        created = os.lstat(path)
        held_after = os.fstat(descriptor)
        if not (
            stat.S_ISREG(created.st_mode)
            and stat.S_IMODE(created.st_mode) == 0o644
            and created.st_nlink == held_after.st_nlink == 1
            and (created.st_dev, created.st_ino)
            == (held_after.st_dev, held_after.st_ino)
        ):
            raise RuntimeError("Finalizer output mode/link/inode contract failed")
    finally:
        os.close(descriptor)
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
