#!/usr/bin/env python3
"""Standalone Incident-002 finalizer for EXP-061 verification attempt 3."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
BASE = Path("experiments/stack-overflow-emotion-gold/oof-router")
EXPERIMENT_ID = "EXP-061"
RUN_ID = "exp-061-seed-43-router-replication"
ATTEMPT_ID = "attempt-1"
MODEL_SEED = 43
RQ_ID = "RQ-S3"
ROUTER_STAGE = "pre-qwen-router-replication"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

PUBLIC_ATTEMPT_REL = BASE / "runs" / RUN_ID / ATTEMPT_ID
PRIVATE_ATTEMPT_REL = BASE / "private" / RUN_ID / ATTEMPT_ID
ROUTER_REL = PUBLIC_ATTEMPT_REL / "router"
FORMAL_CONFIG_REL = BASE / "configs/exp-061-seed-43-router-replication-router-formal-attempt-1.json"
RUN_REL = ROUTER_REL / "run.json"
SELECTED_REL = ROUTER_REL / "selected-operating-point.json"
PAIRED_OOF_REL = PRIVATE_ATTEMPT_REL / "paired-oof.npz"
PRIVATE_ROUTER_REL = PRIVATE_ATTEMPT_REL / "router/router-oof.npz"
ATTEMPT1_VERIFICATION_REL = ROUTER_REL / "verification.json"
ATTEMPT1_SUMMARY_REL = ROUTER_REL / "VERIFICATION-SUMMARY.md"
ATTEMPT2_VERIFICATION_REL = ROUTER_REL / "verification-attempt-2.json"
ATTEMPT2_SUMMARY_REL = ROUTER_REL / "VERIFICATION-SUMMARY-ATTEMPT-2.md"
ATTEMPT3_VERIFICATION_REL = ROUTER_REL / "verification-attempt-3.json"
ATTEMPT3_SUMMARY_REL = ROUTER_REL / "VERIFICATION-SUMMARY-ATTEMPT-3.md"
COMPLETION_REL = ROUTER_REL / "router-complete.json"
OOF_COMPLETION_REL = PUBLIC_ATTEMPT_REL / "oof-complete.json"
CALIBRATION_COMPLETION_REL = PUBLIC_ATTEMPT_REL / "calibration-complete.json"
SELECTION_REL = BASE / "runs" / RUN_ID / "selected-attempt.json"

INCIDENT2_CONFIG_REL = BASE / (
    "configs/exp-061-seed-43-router-replication-router-"
    "verification-attempt-3-incident-002.json"
)
INCIDENT2_PROTOCOL_REL = Path(
    "experiments/stack-overflow-emotion-gold/protocols/"
    "exp-061-exp060-final-verification-attempt-3-incident-002-amendment.md"
)
INCIDENT2_VERIFIER_REL = BASE / "verify_exp060_router_attempt3.py"
INCIDENT2_TESTS_REL = BASE / "tests/test_exp060_router_attempt3.py"
INCIDENT2_FINALIZER_REL = BASE / "finalize_router_replication_attempt3.py"
INCIDENT2_FINALIZER_TESTS_REL = BASE / "tests/test_finalize_router_attempt3.py"
INCIDENT1_CONFIG_REL = BASE / (
    "configs/exp-061-seed-43-router-replication-router-"
    "verification-attempt-2-amendment.json"
)
INCIDENT1_PATHS = {
    "amendment_config": INCIDENT1_CONFIG_REL,
    "amendment_protocol": Path(
        "experiments/stack-overflow-emotion-gold/protocols/"
        "exp-061-exp060-final-verification-attempt-2-amendment.md"
    ),
    "recovery_verifier": BASE / "verify_exp060_router_attempt2.py",
    "recovery_tests": BASE / "tests/test_exp060_router_attempt2.py",
    "finalizer": BASE / "finalize_router_replication_attempt.py",
    "finalizer_tests": BASE / "tests/test_finalize_router_recovery_attempt.py",
}
FULL_POLICY_ORDER = (
    "m1_only", "m3_only", "m1_max_entropy", "m1_threshold_proximity",
    "logistic_router",
)
DEPLOYABLE_POLICY_ORDER = FULL_POLICY_ORDER[2:]
RECOVERY_CHECK_NAMES = (
    "recovery.attempt1_failed_lineage",
    "recovery.attempt2_failed_lineage",
    "recovery.incident1_frozen",
    "recovery.public_modes_normalized",
    "recovery.public_content_unchanged",
    "recovery.private_artifacts_unchanged",
    "recovery.canonical_mirror_paths",
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
CALIBRATION_PUBLIC_OUTPUTS = {
    "calibration_parameters", "calibration_metrics", "classification_metrics",
    "oracle_summary", "abstention_gates", "bootstrap", "reliability_bins",
    "risk_coverage", "label_retention", "random_rejection",
    "reliability_figure", "risk_coverage_figure", "report",
}
CALIBRATION_FROZEN_SOURCES = {"config", "protocol", "runner", "verifier", "tests"}

ATTEMPT1_FAILURES = {
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
INDEPENDENCE = {
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
BASE_INDEPENDENCE = {
    "runner_imported": False,
    "raw_exp058_recomputation": True,
    "nested_thresholds_recomputed": True,
    "scalers_and_routers_refit": True,
    "public_and_private_outputs_recomputed": True,
}
SPLIT_ACCESS = {
    "accessed_splits": ["train-oof"],
    "validation_accessed": False,
    "test_inputs_accessed": False,
    "test_labels_accessed": False,
    "raw_text_accessed": False,
    "model_loaded_or_forward_run": False,
}
PUBLIC_SENSITIVE_KEYS = {
    "component_id", "component_ids", "feature_matrix", "features", "fold_id",
    "fold_ids", "gold", "logit", "logits", "prediction", "predictions",
    "probability", "probabilities", "feature", "router_targets", "route_mask",
    "route_masks", "route_score", "route_scores", "sample_id", "sample_ids",
    "target", "targets", "raw_text", "text",
}
TREE_EXCLUSIONS = {
    Path("verification-attempt-2.json"),
    Path("VERIFICATION-SUMMARY-ATTEMPT-2.md"),
    Path("verification-attempt-3.json"),
    Path("VERIFICATION-SUMMARY-ATTEMPT-3.md"),
    Path("router-complete.json"),
}
MODE_TARGETS = (
    (Path("router"), "directory", 0o755),
    (Path("router/frozen-sources"), "directory", 0o755),
    (Path("router/REPORT.md"), "file", 0o644),
    (Path("router/bootstrap.json"), "file", 0o644),
    (Path("router/call-rate-performance.csv"), "file", 0o644),
    (Path("router/call-rate-performance.png"), "file", 0o644),
    (Path("router/feature-contract.json"), "file", 0o644),
    (Path("router/fold-summary.csv"), "file", 0o644),
    (Path("router/policy-comparisons.csv"), "file", 0o644),
    (Path("router/positive-label-retention.csv"), "file", 0o644),
    (Path("router/random-routing.csv"), "file", 0o644),
    (Path("router/routed-risk-coverage.csv"), "file", 0o644),
    (Path("router/routed-risk-coverage.png"), "file", 0o644),
    (Path("router/router-discrimination.json"), "file", 0o644),
    (Path("router/run.json"), "file", 0o644),
    (Path("router/selected-operating-point.json"), "file", 0o644),
)
PRIVATE_MODES = (
    (BASE / "private" / RUN_ID, "directory", 0o700),
    (PRIVATE_ATTEMPT_REL, "directory", 0o700),
    (PAIRED_OOF_REL, "file", 0o600),
    (PRIVATE_ATTEMPT_REL / "router", "directory", 0o700),
    (PRIVATE_ROUTER_REL, "file", 0o600),
)
ATTEMPT3_CLAIM_BOUNDARY = (
    "Independent verification of unchanged seed-43 train-OOF router evidence under "
    "Incident-002's canonical fresh-mirror path repair and Incident-001's sole "
    "SHA-bound clerical config overlay; no validation, test, model, raw-text, "
    "deployment-generalization, or mechanism claim."
)
COMPLETION_NEXT_GATE = (
    "The dedicated Incident-002 finalizer must bind OOF, EXP-059, Attempt-1 Failed, "
    "Attempt-2 Failed, and Attempt-3 Passed lineage."
)
COMPLETION_CLAIM_BOUNDARY = (
    "Completes one independently recovered seed-43 train-only router stage after "
    "two preserved verification failures; not a cross-seed claim."
)
SELECTION_CLAIM_BOUNDARY = (
    "Selects one verified same-train seed attempt with preserved Failed-Failed-Passed "
    "verification lineage; EXP-063 alone may form the two-seed replication decision."
)


def resolve_relative(value: Path | str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or not relative.parts or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise ValueError(f"Non-canonical project-relative path: {value}")
    cursor = PROJECT_ROOT
    for part in relative.parts:
        cursor = cursor / part
        if os.path.lexists(cursor) and cursor.is_symlink():
            raise ValueError(f"Path traverses symlink: {value}")
    resolved = (PROJECT_ROOT / relative).resolve()
    if not resolved.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return resolved


def display_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def exact_typed_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(
            exact_typed_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            exact_typed_equal(a, b) for a, b in zip(left, right)
        )
    return left == right


def _read_bound_regular(path: Path, expected_mode: int | None = None) -> bytes:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise OSError("O_NOFOLLOW is required")
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    try:
        before = os.fstat(descriptor)
        lexical_before = os.lstat(path)
        with os.fdopen(descriptor, "rb", closefd=False) as source:
            payload = source.read()
        after = os.fstat(descriptor)
        lexical_after = os.lstat(path)
        identity = (before.st_dev, before.st_ino)
        mode_matches = expected_mode is None or (
            stat.S_IMODE(before.st_mode) == expected_mode
            and stat.S_IMODE(after.st_mode) == expected_mode
        )
        if not (
            stat.S_ISREG(before.st_mode)
            and mode_matches
            and before.st_nlink == after.st_nlink == 1
            and before.st_size == len(payload) == after.st_size
            and (lexical_before.st_dev, lexical_before.st_ino) == identity
            and (after.st_dev, after.st_ino) == identity
            and (lexical_after.st_dev, lexical_after.st_ino) == identity
        ):
            raise ValueError(f"Bound file mode/link/inode drift: {path}")
        return payload
    finally:
        os.close(descriptor)


def artifact(path: Path) -> dict[str, Any]:
    payload = _read_bound_regular(path)
    return {
        "path": display_path(path),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def require_record(record: Any, *, expected_relative: Path | None = None) -> Path:
    if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
        raise ValueError("Artifact record inventory drift")
    if not (
        type(record["path"]) is str
        and type(record["bytes"]) is int
        and record["bytes"] >= 0
        and type(record["sha256"]) is str
        and SHA256_RE.fullmatch(record["sha256"])
    ):
        raise ValueError("Artifact record types drift")
    if expected_relative is not None and record["path"] != str(expected_relative):
        raise ValueError("Artifact record canonical path drift")
    path = resolve_relative(record["path"])
    payload = _read_bound_regular(path)
    if (
        len(payload) != record["bytes"]
        or hashlib.sha256(payload).hexdigest() != record["sha256"]
    ):
        raise ValueError(f"Artifact bytes drift: {record['path']}")
    return path


def iter_records(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if set(value) == {"path", "bytes", "sha256"}:
            yield value
        else:
            for child in value.values():
                yield from iter_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_records(child)


def read_bound(path: Path, mode: int) -> bytes:
    return _read_bound_regular(path, expected_mode=mode)


def load_bound_json(path: Path, mode: int) -> dict[str, Any]:
    value = json.loads(read_bound(path, mode))
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object")
    return value


def is_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("+00:00"):
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0 and parsed.isoformat() == value


def timestamp(value: Any) -> datetime:
    if not is_timestamp(value):
        raise ValueError("Non-canonical UTC timestamp")
    return datetime.fromisoformat(value)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def load_config() -> tuple[Path, dict[str, Any]]:
    path = resolve_relative(INCIDENT2_CONFIG_REL)
    config = load_bound_json(path, 0o644)
    expected_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "model_seed",
        "incident_id", "predecessor_incident_id", "authorization",
        "implementation", "lineage", "target", "clerical_overlay", "public_state",
        "private_invariant", "outputs", "commands", "failure_policy",
        "resource_contract",
    }
    if not (
        isinstance(config, dict)
        and set(config) == expected_keys
        and config.get("schema_version")
        == "exp-router-verification-attempt-3-incident-002-config-v1"
        and config.get("experiment_id") == EXPERIMENT_ID
        and config.get("run_id") == RUN_ID
        and config.get("attempt_id") == ATTEMPT_ID
        and type(config.get("model_seed")) is int
        and config.get("model_seed") == MODEL_SEED
        and config.get("incident_id") == "002"
        and config.get("predecessor_incident_id") == "001"
    ):
        raise ValueError("Incident-002 config identity/schema drift")
    expected_authorization = {
        "verification_attempt": 3,
        "independent_verification_recomputation": True,
        "scientific_analysis_rerun": False,
        "public_mode_metadata_repair": False,
        "private_artifact_mutation": False,
        "validation_access": False,
        "test_access": False,
        "model_loading_or_forward": False,
        "raw_text_access": False,
        "seed44_execution": False,
    }
    if not exact_typed_equal(config.get("authorization"), expected_authorization):
        raise ValueError("Incident-002 authorization drift")
    expected_paths = {
        "amendment_protocol": INCIDENT2_PROTOCOL_REL,
        "base_verifier": BASE / "verify_exp060_router.py",
        "recovery_verifier": INCIDENT2_VERIFIER_REL,
        "recovery_tests": INCIDENT2_TESTS_REL,
        "finalizer": INCIDENT2_FINALIZER_REL,
        "finalizer_tests": INCIDENT2_FINALIZER_TESTS_REL,
    }
    implementation = config.get("implementation", {})
    if set(implementation) != set(expected_paths):
        raise ValueError("Incident-002 implementation inventory drift")
    for name, relative in expected_paths.items():
        require_record(implementation[name], expected_relative=relative)
    if artifact(Path(__file__).resolve()) != implementation["finalizer"]:
        raise ValueError("Dedicated finalizer self-binding drift")

    expected_outputs = {
        "verification": str(ATTEMPT3_VERIFICATION_REL),
        "summary": str(ATTEMPT3_SUMMARY_REL),
        "completion": str(COMPLETION_REL),
        "selection": str(SELECTION_REL),
    }
    if not exact_typed_equal(config.get("outputs"), expected_outputs):
        raise ValueError("Incident-002 output namespace drift")
    expected_commands = {
        scope: (
            "/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python "
            f"{BASE}/verify_exp060_router_attempt3.py --scope {scope}"
        )
        for scope in ("final", "complete", "completion")
    }
    if not exact_typed_equal(config.get("commands"), expected_commands):
        raise ValueError("Incident-002 command contract drift")
    if not exact_typed_equal(
        config.get("failure_policy"),
        {
            "append_only": True,
            "failed_attempt_terminal": True,
            "json_written_before_summary": True,
            "exception_details_recorded": False,
            "retry_same_path": False,
        },
    ):
        raise ValueError("Incident-002 failure policy drift")
    formal_resources = load_bound_json(
        resolve_relative(FORMAL_CONFIG_REL), 0o644
    )["resources"]
    expected_resources = {
        "mirror_execution_count": 2,
        "sequential_order": ["mirror_a", "mirror_b"],
        "per_mirror_verification_wall_seconds": formal_resources[
            "verification_wall_seconds"
        ],
        "per_mirror_peak_memory_gb": formal_resources["peak_memory_gb"],
        "api_cost_usd": 0,
        "gpu_cost_usd": 0,
        "model_forward_runs": 0,
        "outer_budget_extension": False,
    }
    if not exact_typed_equal(config.get("resource_contract"), expected_resources):
        raise ValueError("Incident-002 resource contract drift")

    expected_targets = {
        "formal_config": FORMAL_CONFIG_REL,
        "run": RUN_REL,
        "selected_operating_point": SELECTED_REL,
        "paired_oof": PAIRED_OOF_REL,
        "private_router_oof": PRIVATE_ROUTER_REL,
    }
    target = config.get("target", {})
    if not isinstance(target, dict) or set(target) != set(expected_targets):
        raise ValueError("Incident-002 target inventory drift")
    for name, relative in expected_targets.items():
        require_record(target[name], expected_relative=relative)

    lineage = config.get("lineage", {})
    if not isinstance(lineage, dict) or set(lineage) != {
        "incident_001", "attempt_1", "attempt_2"
    }:
        raise ValueError("Incident-002 lineage inventory drift")
    incident1_records = lineage.get("incident_001", {})
    if not isinstance(incident1_records, dict) or set(incident1_records) != set(
        INCIDENT1_PATHS
    ):
        raise ValueError("Incident-001 frozen inventory drift")
    for name, relative in INCIDENT1_PATHS.items():
        require_record(incident1_records[name], expected_relative=relative)
    incident1_config = load_bound_json(resolve_relative(INCIDENT1_CONFIG_REL), 0o644)
    if not (
        incident1_config.get("schema_version")
        == "exp-router-verification-attempt-2-amendment-config-v1"
        and incident1_config.get("incident_id") == "001"
        and incident1_config.get("experiment_id") == EXPERIMENT_ID
        and incident1_config.get("run_id") == RUN_ID
        and incident1_config.get("attempt_id") == ATTEMPT_ID
        and type(incident1_config.get("model_seed")) is int
        and incident1_config.get("model_seed") == MODEL_SEED
        and exact_typed_equal(
            incident1_records["amendment_config"],
            artifact(resolve_relative(INCIDENT1_CONFIG_REL)),
        )
        and exact_typed_equal(
            incident1_records["amendment_protocol"],
            incident1_config["implementation"]["amendment_protocol"],
        )
        and exact_typed_equal(
            incident1_records["recovery_verifier"],
            incident1_config["implementation"]["recovery_verifier"],
        )
        and exact_typed_equal(
            incident1_records["recovery_tests"],
            incident1_config["implementation"]["recovery_tests"],
        )
        and exact_typed_equal(
            incident1_records["finalizer"],
            incident1_config["implementation"]["finalizer"],
        )
        and exact_typed_equal(
            incident1_records["finalizer_tests"],
            incident1_config["implementation"]["finalizer_tests"],
        )
    ):
        raise ValueError("Incident-001 config/implementation cross-binding drift")
    if not isinstance(lineage.get("attempt_1"), dict) or set(
        lineage["attempt_1"]
    ) != {"verification", "summary"}:
        raise ValueError("Attempt-1 lineage record inventory drift")
    if not isinstance(lineage.get("attempt_2"), dict) or set(
        lineage["attempt_2"]
    ) != {"verification", "summary"}:
        raise ValueError("Attempt-2 lineage record inventory drift")
    require_record(
        lineage["attempt_1"]["verification"],
        expected_relative=ATTEMPT1_VERIFICATION_REL,
    )
    require_record(
        lineage["attempt_1"]["summary"], expected_relative=ATTEMPT1_SUMMARY_REL
    )
    require_record(
        lineage["attempt_2"]["verification"],
        expected_relative=ATTEMPT2_VERIFICATION_REL,
    )
    require_record(
        lineage["attempt_2"]["summary"], expected_relative=ATTEMPT2_SUMMARY_REL
    )
    if not exact_typed_equal(
        lineage["attempt_1"],
        {
            "verification": incident1_config["target"][
                "attempt_1_failed_verification"
            ],
            "summary": incident1_config["target"]["attempt_1_failed_summary"],
        },
    ):
        raise ValueError("Attempt-1 lineage is not cross-bound to Incident-001")

    formal_config = load_bound_json(resolve_relative(FORMAL_CONFIG_REL), 0o644)
    expected_overlay = {
        "operation": "replace",
        "json_pointer": "/router/policies",
        "match_input_sha256": target["formal_config"]["sha256"],
        "before": list(DEPLOYABLE_POLICY_ORDER),
        "after": list(FULL_POLICY_ORDER),
        "deployable_policy_order_unchanged": list(DEPLOYABLE_POLICY_ORDER),
        "recursive_diff": [
            {
                "path": "$.router.policies",
                "before": list(DEPLOYABLE_POLICY_ORDER),
                "after": list(FULL_POLICY_ORDER),
            }
        ],
        "maximum_changed_nodes": 1,
    }
    if not (
        formal_config.get("router", {}).get("policies")
        == list(DEPLOYABLE_POLICY_ORDER)
        and formal_config.get("router", {}).get("deployable_policy_order")
        == list(DEPLOYABLE_POLICY_ORDER)
        and exact_typed_equal(config.get("clerical_overlay"), expected_overlay)
        and exact_typed_equal(
            config.get("clerical_overlay"), incident1_config.get("clerical_overlay")
        )
    ):
        raise ValueError("Incident-002 clerical overlay drift")

    public_state = config.get("public_state", {})
    if not (
        isinstance(public_state, dict)
        and set(public_state)
        == {
            "path_count", "normalized_manifest", "content_tree_digest_algorithm",
            "content_tree",
        }
        and type(public_state.get("path_count")) is int
        and public_state.get("path_count") == 16
        and isinstance(public_state.get("normalized_manifest"), list)
        and len(public_state["normalized_manifest"]) == 16
        and public_state.get("content_tree_digest_algorithm")
        == (
            "sha256(canonical-json(sorted(relative_path,bytes,sha256))); exclude exact "
            "router-root-relative Attempt-2 JSON/summary, Attempt-3 JSON/summary, and "
            "router-complete.json paths"
        )
        and public_state.get("content_tree")
        == incident1_config["public_mode_normalization"]["content_tree_before"]
    ):
        raise ValueError("Incident-002 public-state contract drift")
    expected_mode_rows = []
    incident1_pre = incident1_config["public_mode_normalization"]["pre_manifest"]
    for row in incident1_pre:
        expected_mode_rows.append(
            {
                **row,
                "observed_mode": row["after_mode"],
                "matches_expected": True,
            }
        )
    if not exact_typed_equal(public_state["normalized_manifest"], expected_mode_rows):
        raise ValueError("Incident-002 exact16 normalized manifest drift")
    private = config.get("private_invariant", {})
    if not (
        isinstance(private, dict)
        and set(private) == {"artifact_count", "sha256", "artifacts", "modes"}
        and exact_typed_equal(private, incident1_config.get("private_invariant"))
        and type(private.get("artifact_count")) is int
        and private.get("artifact_count") == 2
    ):
        raise ValueError("Incident-002 private invariant drift")
    for record in private["artifacts"]:
        require_record(record)
    return path, config


def exact_check_rows(value: Any, count: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) == count
        and all(
            isinstance(row, dict)
            and set(row) == {"name", "passed", "detail"}
            and type(row["name"]) is str
            and type(row["passed"]) is bool
            for row in value
        )
    )


def expected_attempt1_summary(value: dict[str, Any]) -> bytes:
    lines = [
        f"# {value['experiment_id']} Formal Router Verification",
        "",
        f"- Status: `{value['status']}`",
        f"- Passed checks: `{value['passed_count']}`",
        f"- Failed checks: `{value['failed_count']}`",
        "- Runner imported: `false`",
        "- Input: frozen EXP-058 train-OOF only",
        "- Validation/test/model/raw-text access: `false`",
        "",
        value["claim_boundary"],
        "",
    ]
    if value["failed_count"]:
        lines.extend(["## Failed checks", ""])
        lines.extend(
            f"- `{row['name']}`" for row in value["checks"] if row["passed"] is False
        )
        lines.append("")
    return "\n".join(lines).encode("utf-8")


def validate_attempt1(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    records = config["lineage"]["attempt_1"]
    if set(records) != {"verification", "summary"}:
        raise ValueError("Attempt-1 lineage inventory drift")
    verification_path = require_record(
        records["verification"], expected_relative=ATTEMPT1_VERIFICATION_REL
    )
    summary_path = require_record(records["summary"], expected_relative=ATTEMPT1_SUMMARY_REL)
    value = load_bound_json(verification_path, 0o600)
    summary = read_bound(summary_path, 0o600)
    rows = value.get("checks", [])
    failed = {row["name"] for row in rows if row.get("passed") is False}
    if not (
        value.get("schema_version") == "exp-router-formal-verification-v2"
        and value.get("experiment_id") == EXPERIMENT_ID
        and value.get("rq_id") == RQ_ID
        and value.get("stage") == ROUTER_STAGE
        and value.get("run_id") == RUN_ID
        and value.get("attempt_id") == ATTEMPT_ID
        and type(value.get("model_seed")) is int
        and value.get("model_seed") == MODEL_SEED
        and value.get("scope") == "final"
        and value.get("status") == "Failed"
        and type(value.get("passed_count")) is int
        and value.get("passed_count") == 4417
        and type(value.get("failed_count")) is int
        and value.get("failed_count") == 17
        and exact_check_rows(rows, 4434)
        and len({row["name"] for row in rows}) == 4434
        and failed == ATTEMPT1_FAILURES
        and is_timestamp(value.get("verified_at_utc"))
        and summary == expected_attempt1_summary(value)
    ):
        raise ValueError("Attempt-1 Failed contract drift")
    return value, records


def expected_attempt2_summary(value: dict[str, Any]) -> bytes:
    text = "\n".join(
        [
            "# EXP-061 / EXP-060 Final Router Verification Attempt 2",
            "",
            "- Status: `Failed`",
            "- Failure sealed: `true`",
            "- Failure stage: `verification_build`",
            "- Failure code: `deterministic_contract_failure`",
            "- Exception details recorded: `false`",
            "- Scientific conclusion: none",
            "",
            value["claim_boundary"],
            "",
        ]
    )
    return (text + "\n").encode("utf-8")


def validate_attempt2(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    records = config["lineage"]["attempt_2"]
    if set(records) != {"verification", "summary"}:
        raise ValueError("Attempt-2 lineage inventory drift")
    verification_path = require_record(records["verification"], expected_relative=ATTEMPT2_VERIFICATION_REL)
    summary_path = require_record(records["summary"], expected_relative=ATTEMPT2_SUMMARY_REL)
    value = load_bound_json(verification_path, 0o644)
    summary = read_bound(summary_path, 0o644)
    expected_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "model_seed",
        "scope", "verification_attempt", "status", "runner_imported",
        "verified_at_utc", "passed_count", "failed_count", "checks", "failure",
        "claim_boundary",
    }
    if not (
        set(value) == expected_keys
        and value.get("schema_version")
        == "exp-router-formal-verification-attempt-2-failure-v1"
        and value.get("experiment_id") == EXPERIMENT_ID
        and value.get("run_id") == RUN_ID
        and value.get("attempt_id") == ATTEMPT_ID
        and type(value.get("model_seed")) is int
        and value.get("model_seed") == MODEL_SEED
        and value.get("scope") == "final"
        and type(value.get("verification_attempt")) is int
        and value.get("verification_attempt") == 2
        and value.get("status") == "Failed"
        and value.get("runner_imported") is False
        and is_timestamp(value.get("verified_at_utc"))
        and type(value.get("passed_count")) is int
        and value.get("passed_count") == 0
        and type(value.get("failed_count")) is int
        and value.get("failed_count") == 1
        and exact_typed_equal(value.get("checks"), [{
            "name": "recovery.attempt2_deterministic_failure",
            "passed": False,
            "detail": {"stage": "verification_build", "code": "deterministic_contract_failure"},
        }])
        and exact_typed_equal(value.get("failure"), {
            "sealed": True,
            "stage": "verification_build",
            "code": "deterministic_contract_failure",
            "exception_details_recorded": False,
        })
        and summary == expected_attempt2_summary(value)
        and not public_sensitive_paths(value)
    ):
        raise ValueError("Attempt-2 terminal Failed contract drift")
    return value, records


def expected_attempt3_summary(value: dict[str, Any]) -> bytes:
    text = "\n".join(
        [
            "# EXP-061 / EXP-060 Final Router Verification Attempt 3",
            "",
            "- Status: `Passed`",
            "- Main verifier checks: `4434 / 4434`",
            "- Mirror A (unchanged config): `4433 / 4434`; sole failure `config.router`",
            "- Mirror B (registered SHA-bound overlay): `4434 / 4434`",
            "- Fresh-mirror canonical path repair: `Incident-002`",
            "- Scientific analysis rerun: `false`",
            "- Attempt-1 and Attempt-2 Failed lineage: preserved",
            "- Validation/test/model/raw-text access: `false`",
            "",
            value["claim_boundary"],
            "",
        ]
    )
    return (text + "\n").encode("utf-8")


def mirror_source_manifest() -> list[dict[str, Any]]:
    config = load_bound_json(resolve_relative(FORMAL_CONFIG_REL), 0o644)
    run = load_bound_json(resolve_relative(RUN_REL), 0o644)
    relatives = {FORMAL_CONFIG_REL, BASE / "verify_exp060_router.py", RUN_REL}
    for record in [*iter_records(config), *iter_records(run)]:
        relatives.add(Path(record["path"]))
    forbidden = {
        ATTEMPT1_VERIFICATION_REL, ATTEMPT1_SUMMARY_REL, ATTEMPT2_VERIFICATION_REL,
        ATTEMPT2_SUMMARY_REL, ATTEMPT3_VERIFICATION_REL, ATTEMPT3_SUMMARY_REL,
        COMPLETION_REL, SELECTION_REL,
    }
    if relatives & forbidden:
        raise ValueError("Mirror manifest includes governance output")
    return [artifact(resolve_relative(relative)) for relative in sorted(relatives)]


def validate_mirror(value: Any, *, overlay: bool) -> None:
    keys = {
        "fresh_project_root", "project_root_mode", "canonical_layout", "copy_only",
        "copied_file_count", "copy_manifest_sha256", "no_symlinks", "no_hardlinks",
        "instance_token_sha256", "overlay_enabled", "overlay_load_count",
        "matching_sha_load_count", "overlay_input_sha256", "cleaned",
    }
    manifest = mirror_source_manifest()
    if not (
        isinstance(value, dict)
        and set(value) == keys
        and all(value.get(name) is True for name in (
            "fresh_project_root", "canonical_layout", "copy_only", "no_symlinks",
            "no_hardlinks", "cleaned",
        ))
        and value.get("project_root_mode") == "0o700"
        and type(value.get("copied_file_count")) is int
        and value.get("copied_file_count") == len(manifest) == 30
        and value.get("copy_manifest_sha256") == canonical_digest(manifest)
        and value.get("copy_manifest_sha256")
        == "6ee47d1974a88d9b94091423d9c57deeb239065894a6083ebbdf3e283cacfa67"
        and type(value.get("instance_token_sha256")) is str
        and SHA256_RE.fullmatch(value["instance_token_sha256"])
        and value.get("overlay_enabled") is overlay
        and type(value.get("overlay_load_count")) is int
        and type(value.get("matching_sha_load_count")) is int
    ):
        raise ValueError("Fresh-mirror metadata/manifest drift")
    if overlay:
        valid = (
            value.get("overlay_load_count") == 1
            and value.get("matching_sha_load_count") == 2
            and value.get("overlay_input_sha256")
            == sha256(resolve_relative(FORMAL_CONFIG_REL))
        )
    else:
        valid = value.get("overlay_load_count") == 0 and value.get("matching_sha_load_count") == 0 and value.get("overlay_input_sha256") is None
    if not valid:
        raise ValueError("Fresh-mirror overlay metadata drift")


def public_tree_digest() -> dict[str, Any]:
    root = resolve_relative(ROUTER_REL)
    rows: list[dict[str, Any]] = []
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Router root missing/symbolic")
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Router tree contains symlink")
        relative = path.relative_to(root)
        if path.is_file() and relative not in TREE_EXCLUSIONS:
            rows.append({"path": str(relative), "bytes": path.stat().st_size, "sha256": sha256(path)})
    return {"file_count": len(rows), "sha256": canonical_digest(rows)}


def validate_modes() -> None:
    for relative, kind, expected_mode in MODE_TARGETS:
        path = resolve_relative(PUBLIC_ATTEMPT_REL / relative)
        observed = os.lstat(path)
        valid_type = stat.S_ISDIR(observed.st_mode) if kind == "directory" else stat.S_ISREG(observed.st_mode)
        valid_links = kind == "directory" or observed.st_nlink == 1
        if not valid_type or not valid_links or stat.S_IMODE(observed.st_mode) != expected_mode:
            raise ValueError(f"Public mode/type/link drift: {relative}")
    for relative, kind, expected_mode in PRIVATE_MODES:
        path = resolve_relative(relative)
        observed = os.lstat(path)
        valid_type = stat.S_ISDIR(observed.st_mode) if kind == "directory" else stat.S_ISREG(observed.st_mode)
        if not valid_type or stat.S_IMODE(observed.st_mode) != expected_mode or (kind == "file" and observed.st_nlink != 1):
            raise ValueError(f"Private mode/type/link drift: {relative}")


def validate_attempt3(
    config: dict[str, Any], attempt1: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    path = resolve_relative(ATTEMPT3_VERIFICATION_REL)
    summary_path = resolve_relative(ATTEMPT3_SUMMARY_REL)
    value = load_bound_json(path, 0o644)
    summary = read_bound(summary_path, 0o644)
    expected_top = {
        "schema_version", "experiment_id", "rq_id", "stage", "run_id",
        "attempt_id", "model_seed", "seed_contract", "scope",
        "verification_attempt", "status", "runner_imported", "verified_at_utc",
        "passed_count", "failed_count", "checks", "independence",
        "verified_artifacts", "split_access", "recovery", "claim_boundary",
    }
    formal_config = load_bound_json(resolve_relative(FORMAL_CONFIG_REL), 0o644)
    checks = value.get("checks", [])
    names = [row.get("name") for row in checks] if isinstance(checks, list) else []
    if not (
        set(value) == expected_top
        and value.get("schema_version") == "exp-router-formal-verification-attempt-3-v1"
        and value.get("experiment_id") == EXPERIMENT_ID
        and value.get("rq_id") == RQ_ID
        and value.get("stage") == ROUTER_STAGE
        and value.get("run_id") == RUN_ID
        and value.get("attempt_id") == ATTEMPT_ID
        and type(value.get("model_seed")) is int
        and value.get("model_seed") == MODEL_SEED
        and exact_typed_equal(
            value.get("seed_contract"), formal_config.get("seed_contract")
        )
        and value.get("scope") == "final"
        and type(value.get("verification_attempt")) is int
        and value.get("verification_attempt") == 3
        and value.get("status") == "Passed"
        and value.get("runner_imported") is False
        and is_timestamp(value.get("verified_at_utc"))
        and type(value.get("passed_count")) is int
        and value.get("passed_count") == 4434
        and type(value.get("failed_count")) is int
        and value.get("failed_count") == 0
        and exact_check_rows(checks, 4434)
        and names == [row["name"] for row in attempt1["checks"]]
        and all(row["passed"] is True for row in checks)
        and exact_typed_equal(value.get("independence"), INDEPENDENCE)
        and exact_typed_equal(value.get("split_access"), SPLIT_ACCESS)
        and value.get("claim_boundary") == ATTEMPT3_CLAIM_BOUNDARY
        and summary == expected_attempt3_summary(value)
        and not public_sensitive_paths(value)
    ):
        raise ValueError("Attempt-3 Passed contract drift")
    target = config["target"]
    expected_verified = {
        "config": target["formal_config"],
        "run": target["run"],
        "input": target["paired_oof"],
        "private_router_oof": target["private_router_oof"],
    }
    if not exact_typed_equal(value.get("verified_artifacts"), expected_verified):
        raise ValueError("Attempt-3 verified artifact inventory drift")
    recovery = value.get("recovery", {})
    expected_recovery_keys = {
        "schema_version", "incident_id", "predecessor_incident_id",
        "classification", "amendment_config", "amendment_protocol",
        "incident_001", "attempt_1_failed", "attempt_2_failed", "base_verifier",
        "recovery_verifier", "path_canonicalization", "overlay", "public_state",
        "private_state", "recomputation", "recovery_checks",
    }
    config_path = resolve_relative(INCIDENT2_CONFIG_REL)
    if not (
        isinstance(recovery, dict)
        and set(recovery) == expected_recovery_keys
        and recovery.get("schema_version") == "exp-router-verification-recovery-attempt-3-v1"
        and recovery.get("incident_id") == "002"
        and recovery.get("predecessor_incident_id") == "001"
        and recovery.get("classification") == "fresh_mirror_path_canonicalization"
        and exact_typed_equal(recovery.get("amendment_config"), artifact(config_path))
        and exact_typed_equal(
            recovery.get("amendment_protocol"),
            config["implementation"]["amendment_protocol"],
        )
        and exact_typed_equal(
            recovery.get("incident_001"), config["lineage"]["incident_001"]
        )
        and exact_typed_equal(
            recovery.get("attempt_1_failed"), config["lineage"]["attempt_1"]
        )
        and exact_typed_equal(
            recovery.get("attempt_2_failed"), config["lineage"]["attempt_2"]
        )
        and exact_typed_equal(
            recovery.get("base_verifier"), config["implementation"]["base_verifier"]
        )
        and exact_typed_equal(
            recovery.get("recovery_verifier"),
            config["implementation"]["recovery_verifier"],
        )
        and exact_typed_equal(
            recovery.get("path_canonicalization"),
            {
                "loaded_verifier_project_root_used": True,
                "config_argument": "module.PROJECT_ROOT / FORMAL_CONFIG_REL",
                "semantic_change_count": 1,
            },
        )
        and exact_typed_equal(
            recovery.get("overlay"),
            {**config["clerical_overlay"], "applied_load_count": 1},
        )
        and exact_typed_equal(
            recovery.get("public_state"),
            {
                **config["public_state"],
                "observed_content_tree": config["public_state"]["content_tree"],
            },
        )
        and exact_typed_equal(
            recovery.get("private_state"),
            {
                "before": config["private_invariant"],
                "after": config["private_invariant"],
            },
        )
    ):
        raise ValueError("Attempt-3 recovery lineage/state drift")
    recomputation = recovery.get("recomputation", {})
    if not isinstance(recomputation, dict) or set(recomputation) != {"mirror_a", "mirror_b", "check_name_order_sha256"}:
        raise ValueError("Attempt-3 recomputation inventory drift")
    mirror_a = recomputation["mirror_a"]
    mirror_b = recomputation["mirror_b"]
    a_checks = mirror_a.get("checks", [])
    if not (
        set(mirror_a) == {"role", "status", "passed_count", "failed_count", "checks", "independence", "verified_artifacts", "split_access", "mirror"}
        and mirror_a.get("role") == "unchanged_config_control"
        and mirror_a.get("status") == "Failed"
        and type(mirror_a.get("passed_count")) is int
        and mirror_a.get("passed_count") == 4433
        and type(mirror_a.get("failed_count")) is int
        and mirror_a.get("failed_count") == 1
        and exact_check_rows(a_checks, 4434)
        and [row["name"] for row in a_checks] == names
        and [row["name"] for row in a_checks if row["passed"] is False] == ["config.router"]
        and exact_typed_equal(mirror_a.get("independence"), BASE_INDEPENDENCE)
        and exact_typed_equal(mirror_a.get("verified_artifacts"), expected_verified)
        and exact_typed_equal(mirror_a.get("split_access"), SPLIT_ACCESS)
    ):
        raise ValueError("Attempt-3 Mirror-A evidence drift")
    if not (
        set(mirror_b) == {"role", "status", "passed_count", "failed_count", "checks_location", "checks_sha256", "independence", "verified_artifacts", "split_access", "mirror"}
        and mirror_b.get("role") == "sha_bound_overlay_recovery"
        and mirror_b.get("status") == "Passed"
        and type(mirror_b.get("passed_count")) is int
        and mirror_b.get("passed_count") == 4434
        and type(mirror_b.get("failed_count")) is int
        and mirror_b.get("failed_count") == 0
        and mirror_b.get("checks_location") == "$.checks"
        and mirror_b.get("checks_sha256") == canonical_digest(checks)
        and exact_typed_equal(mirror_b.get("independence"), BASE_INDEPENDENCE)
        and exact_typed_equal(mirror_b.get("verified_artifacts"), expected_verified)
        and exact_typed_equal(mirror_b.get("split_access"), SPLIT_ACCESS)
        and recomputation.get("check_name_order_sha256") == canonical_digest(names)
    ):
        raise ValueError("Attempt-3 Mirror-B evidence drift")
    validate_mirror(mirror_a.get("mirror"), overlay=False)
    validate_mirror(mirror_b.get("mirror"), overlay=True)
    if mirror_a["mirror"]["instance_token_sha256"] == mirror_b["mirror"]["instance_token_sha256"]:
        raise ValueError("Attempt-3 mirrors are not distinct")
    recovery_checks = recovery.get("recovery_checks")
    if not (
        exact_check_rows(recovery_checks, 16)
        and [row["name"] for row in recovery_checks] == list(RECOVERY_CHECK_NAMES)
        and all(row["passed"] is True and row["detail"] is None for row in recovery_checks)
    ):
        raise ValueError("Attempt-3 recovery checks drift")
    return value, {"verification": artifact(path), "summary": artifact(summary_path)}


def validate_completion(
    config: dict[str, Any], attempt3: dict[str, Any], attempt3_records: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    path = resolve_relative(COMPLETION_REL)
    value = load_bound_json(path, 0o644)
    expected_keys = {
        "schema_version", "experiment_id", "rq_id", "stage", "run_id",
        "attempt_id", "model_seed", "seed_contract", "status", "completed_at_utc",
        "decision", "primary_gate_passed", "verification_attempt",
        "recovery_lineage", "artifacts", "next_gate", "claim_boundary",
    }
    target = config["target"]
    expected_artifacts = {
        "config": target["formal_config"],
        "run": target["run"],
        "selected_operating_point": target["selected_operating_point"],
        "final_verification": attempt3_records["verification"],
        "private_router_oof": target["private_router_oof"],
    }
    lineage = value.get("recovery_lineage", {})
    expected_lineage_keys = {
        "incident_id", "attempt_1_failed", "incident_001", "attempt_2_failed",
        "incident_002_config", "incident_002_protocol", "incident_002_verifier",
        "incident_002_tests", "incident_002_finalizer",
        "incident_002_finalizer_tests", "attempt_3_passed", "attempt_3_summary",
    }
    config_path = resolve_relative(INCIDENT2_CONFIG_REL)
    expected_lineage = {
        "incident_id": "002",
        "attempt_1_failed": config["lineage"]["attempt_1"],
        "incident_001": config["lineage"]["incident_001"],
        "attempt_2_failed": config["lineage"]["attempt_2"],
        "incident_002_config": artifact(config_path),
        "incident_002_protocol": config["implementation"]["amendment_protocol"],
        "incident_002_verifier": config["implementation"]["recovery_verifier"],
        "incident_002_tests": config["implementation"]["recovery_tests"],
        "incident_002_finalizer": config["implementation"]["finalizer"],
        "incident_002_finalizer_tests": config["implementation"]["finalizer_tests"],
        "attempt_3_passed": attempt3_records["verification"],
        "attempt_3_summary": attempt3_records["summary"],
    }
    selected = load_bound_json(resolve_relative(SELECTED_REL), 0o644)
    policies = selected.get("policies", {})
    if not isinstance(policies, dict) or set(policies) != set(DEPLOYABLE_POLICY_ORDER):
        raise ValueError("Selected policy inventory drift")
    primary = policies.get("logistic_router", {})
    candidate = primary.get("candidate", {}) if isinstance(primary, dict) else {}
    passed = primary.get("passed")
    if not isinstance(passed, bool):
        raise ValueError("Selected primary gate must be boolean")
    decision = "Pass" if passed else "Fail"
    overall = selected.get("overall", {})
    primary_valid = (
        selected.get("schema_version") == "exp-router-selected-operating-point-v2"
        and selected.get("experiment_id") == EXPERIMENT_ID
        and selected.get("run_id") == RUN_ID
        and selected.get("attempt_id") == ATTEMPT_ID
        and type(selected.get("model_seed")) is int
        and selected.get("model_seed") == MODEL_SEED
        and selected.get("primary_policy") == "logistic_router"
        and type(selected.get("primary_nominal_call_rate")) is float
        and selected.get("primary_nominal_call_rate") == 0.15
        and primary.get("evidence_role") == "primary"
        and type(candidate.get("target_call_rate")) is float
        and candidate.get("target_call_rate") == 0.15
        and all(
            policies[name].get("evidence_role") == "descriptive_only"
            and policies[name].get("passed") is False
            for name in ("m1_max_entropy", "m1_threshold_proximity")
        )
        and overall.get("decision") == decision
        and overall.get("selected_policy") == "logistic_router"
        and exact_typed_equal(overall.get("selected_candidate"), candidate)
    )
    formal_config = load_bound_json(resolve_relative(FORMAL_CONFIG_REL), 0o644)
    run = load_bound_json(resolve_relative(RUN_REL), 0o644)
    if not (
        set(value) == expected_keys
        and value.get("schema_version") == "exp-router-completion-v3"
        and value.get("experiment_id") == EXPERIMENT_ID
        and value.get("rq_id") == RQ_ID
        and value.get("stage") == ROUTER_STAGE
        and value.get("run_id") == RUN_ID
        and value.get("attempt_id") == ATTEMPT_ID
        and type(value.get("model_seed")) is int
        and value.get("model_seed") == MODEL_SEED
        and exact_typed_equal(value.get("seed_contract"), formal_config.get("seed_contract"))
        and value.get("status") == "Complete"
        and is_timestamp(value.get("completed_at_utc"))
        and value.get("decision") == decision
        and value.get("primary_gate_passed") is passed
        and type(value.get("verification_attempt")) is int
        and value.get("verification_attempt") == 3
        and isinstance(lineage, dict)
        and set(lineage) == expected_lineage_keys
        and exact_typed_equal(lineage, expected_lineage)
        and exact_typed_equal(value.get("artifacts"), expected_artifacts)
        and value.get("next_gate") == COMPLETION_NEXT_GATE
        and value.get("claim_boundary") == COMPLETION_CLAIM_BOUNDARY
        and timestamp(attempt3["verified_at_utc"]) <= timestamp(value["completed_at_utc"])
        and primary_valid
        and run.get("status") == "CompletedAwaitingVerification"
        and run.get("experiment_id") == EXPERIMENT_ID
        and run.get("rq_id") == RQ_ID
        and run.get("stage") == ROUTER_STAGE
        and run.get("run_id") == RUN_ID
        and run.get("attempt_id") == ATTEMPT_ID
        and type(run.get("model_seed")) is int
        and run.get("model_seed") == MODEL_SEED
        and exact_typed_equal(run.get("seed_contract"), formal_config.get("seed_contract"))
        and run.get("decision") == decision
        and exact_typed_equal(run.get("config"), target["formal_config"])
        and exact_typed_equal(
            run.get("public_outputs", {}).get("selected_operating_point_json"),
            target["selected_operating_point"],
        )
        and not public_sensitive_paths(value)
    ):
        raise ValueError("Attempt-3 completion contract drift")
    return value, artifact(path)


def validate_stage_completion(
    name: str, relative: Path, expected_schema: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    path = resolve_relative(relative)
    value = load_bound_json(path, 0o600)
    formal_config = load_bound_json(resolve_relative(FORMAL_CONFIG_REL), 0o644)
    expected_seed = formal_config["seed_contract"]
    expected_keys = (
        {
            "schema_version", "experiment_id", "run_id", "attempt_id", "model_seed",
            "seed_contract", "seed_contract_sha256", "stage", "status",
            "completed_at_utc", "cli_identity", "config", "artifacts", "next_gate",
            "claim_boundary",
        }
        if name == "oof"
        else {
            "schema_version", "experiment_id", "replication_parent_experiment_id",
            "run_id", "attempt_id", "model_seed", "seed_contract", "status",
            "completed_at_utc", "artifacts", "next_gate", "claim_boundary",
        }
    )
    expected_artifact_keys = (
        {"run", "summary", "final_verification", "paired_oof_private"}
        if name == "oof"
        else {
            "config", "exp059_run", "exp059_verification",
            "exp059_verification_summary", "exp059_calibration_parameters",
            "paired_oof_private", "private_calibration", "public_outputs",
            "frozen_sources",
        }
    )
    if not (
        isinstance(value, dict)
        and set(value) == expected_keys
        and value.get("schema_version") == expected_schema
        and value.get("run_id") == RUN_ID
        and value.get("attempt_id") == ATTEMPT_ID
        and type(value.get("model_seed")) is int
        and value.get("model_seed") == MODEL_SEED
        and exact_typed_equal(value.get("seed_contract"), expected_seed)
        and value.get("status") == "Complete"
        and is_timestamp(value.get("completed_at_utc"))
        and isinstance(value.get("artifacts"), dict)
        and set(value["artifacts"]) == expected_artifact_keys
        and not public_sensitive_paths(value)
    ):
        raise ValueError(f"{name} completion contract drift")
    if name == "oof":
        if not (
            value.get("experiment_id") == EXPERIMENT_ID
            and value.get("stage") == "paired-m1-m3-oof-production"
            and value.get("next_gate")
            == "Seed-specific EXP-059 and identity-nested EXP-060 must pass before namespace selection."
            and value.get("claim_boundary")
            == "Completes one verified train-only paired OOF stage; this is not final pipeline selection."
        ):
            raise ValueError("OOF completion identity/claim drift")
    else:
        if not (
            value.get("experiment_id") == "EXP-059"
            and value.get("replication_parent_experiment_id") == EXPERIMENT_ID
            and value.get("next_gate")
            == "Identity-nested EXP-060 must pass before final attempt selection."
            and value.get("claim_boundary")
            == "Completes only the seed-specific EXP-059 diagnostic stage."
        ):
            raise ValueError("Calibration completion parent/claim drift")

    records = value["artifacts"]
    artifact_paths: dict[str, Path] = {}
    for artifact_name, record in records.items():
        expected_nested = None
        if name == "calibration" and artifact_name == "public_outputs":
            expected_nested = CALIBRATION_PUBLIC_OUTPUTS
        elif name == "calibration" and artifact_name == "frozen_sources":
            expected_nested = CALIBRATION_FROZEN_SOURCES
        if expected_nested is not None:
            if not isinstance(record, dict) or set(record) != expected_nested:
                raise ValueError(f"Calibration {artifact_name} inventory drift")
            record_items = record.items()
        else:
            record_items = ((artifact_name, record),)
        for _nested_name, artifact_record in record_items:
            artifact_path = require_record(artifact_record)
            if expected_nested is None:
                artifact_paths[artifact_name] = artifact_path
            if not (
                artifact_path.is_relative_to(resolve_relative(PUBLIC_ATTEMPT_REL))
                or artifact_path.is_relative_to(resolve_relative(PRIVATE_ATTEMPT_REL))
                or artifact_path.parent == resolve_relative(BASE / "configs")
            ):
                raise ValueError(f"{name} artifact outside canonical roots")
    if name == "oof":
        config_record = value.get("config")
        config_path = require_record(config_record)
        if config_path.parent != resolve_relative(BASE / "configs"):
            raise ValueError("OOF config is outside canonical config root")
        run = load_bound_json(artifact_paths["run"], 0o600)
        verification = load_bound_json(artifact_paths["final_verification"], 0o600)
        verified = verification.get("verified_artifacts", {})
        identity = {
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "attempt_id": ATTEMPT_ID,
            "model_seed": MODEL_SEED,
            "seed_contract": expected_seed,
        }
        if not (
            run.get("status") == "CompletedAwaitingVerification"
            and all(exact_typed_equal(run.get(key), expected) for key, expected in identity.items())
            and verification.get("status") == "Passed"
            and type(verification.get("failed_count")) is int
            and verification.get("failed_count") == 0
            and all(
                exact_typed_equal(verification.get(key), expected)
                for key, expected in identity.items()
            )
            and exact_typed_equal(verified.get("config"), config_record)
            and exact_typed_equal(verified.get("run"), records["run"])
            and exact_typed_equal(verified.get("summary"), records["summary"])
            and exact_typed_equal(
                verified.get("paired_oof_private"), records["paired_oof_private"]
            )
        ):
            raise ValueError("OOF completion is not bound to a Passed verification")
    else:
        run = load_bound_json(artifact_paths["exp059_run"], 0o600)
        verification = load_bound_json(
            artifact_paths["exp059_verification"], 0o600
        )
        parameters = load_bound_json(
            artifact_paths["exp059_calibration_parameters"], 0o600
        )
        expected_identity = {
            "experiment_id": "EXP-059",
            "replication_parent_experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "attempt_id": ATTEMPT_ID,
            "model_seed": MODEL_SEED,
            "seed_contract": expected_seed,
        }
        expected_verified = {
            "config": records["config"],
            "run": records["exp059_run"],
            "calibration_parameters": records["exp059_calibration_parameters"],
            "paired_oof": records["paired_oof_private"],
            "private_output": records["private_calibration"],
            "public_outputs": records["public_outputs"],
            "frozen_sources": records["frozen_sources"],
        }
        if not (
            run.get("status") == "CompletedAwaitingVerification"
            and all(exact_typed_equal(run.get(key), expected) for key, expected in expected_identity.items())
            and exact_typed_equal(run.get("config"), records["config"])
            and exact_typed_equal(
                run.get("private_output"), records["private_calibration"]
            )
            and exact_typed_equal(run.get("public_outputs"), records["public_outputs"])
            and exact_typed_equal(run.get("frozen_sources"), records["frozen_sources"])
            and verification.get("status") == "Passed"
            and type(verification.get("failed_count")) is int
            and verification.get("failed_count") == 0
            and all(
                exact_typed_equal(verification.get(key), expected)
                for key, expected in expected_identity.items()
            )
            and all(
                exact_typed_equal(parameters.get(key), expected)
                for key, expected in expected_identity.items()
            )
            and exact_typed_equal(verification.get("verified_artifacts"), expected_verified)
        ):
            raise ValueError("Calibration completion is not bound to a Passed verification")
    return value, artifact(path)


def create_json_once(path: Path, value: dict[str, Any]) -> None:
    if os.path.lexists(path):
        raise FileExistsError(path)
    payload = (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if os.path.lexists(temporary):
        raise FileExistsError(temporary)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
            os.fchmod(target.fileno(), 0o644)
            os.fsync(target.fileno())
        held = os.fstat(descriptor)
        lexical = os.lstat(temporary)
        if not (
            stat.S_ISREG(held.st_mode)
            and stat.S_IMODE(held.st_mode) == 0o644
            and held.st_nlink == lexical.st_nlink == 1
            and held.st_size == len(payload)
            and (held.st_dev, held.st_ino) == (lexical.st_dev, lexical.st_ino)
        ):
            raise RuntimeError("Selection temporary identity/mode drift")
        os.link(temporary, path)
        temporary.unlink()
        created = os.lstat(path)
        after = os.fstat(descriptor)
        if not (
            stat.S_ISREG(created.st_mode)
            and stat.S_IMODE(created.st_mode) == 0o644
            and created.st_nlink == after.st_nlink == 1
            and created.st_size == after.st_size == len(payload)
            and (created.st_dev, created.st_ino) == (after.st_dev, after.st_ino)
        ):
            raise RuntimeError("Selection output identity/mode drift")
    finally:
        os.close(descriptor)
        if os.path.lexists(temporary):
            temporary.unlink()


def validate_selection_payload(
    selection: dict[str, Any],
    *,
    expected_chain: list[dict[str, Any]],
    expected_completions: dict[str, Any],
    expected_stage_artifacts: dict[str, Any],
    expected_lineage: dict[str, Any],
) -> None:
    formal_config = load_bound_json(resolve_relative(FORMAL_CONFIG_REL), 0o644)
    expected_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "model_seed",
        "seed_contract", "status", "selected_at_utc", "primary_policy",
        "primary_nominal_call_rate", "primary_gate_passed", "decision",
        "verification_attempt", "finalizer", "completions", "stage_artifacts",
        "attempt_chain", "recovery_lineage", "claim_boundary",
    }
    chain = selection.get("attempt_chain")
    chain_keys = {
        "verification_attempt", "status", "passed_count", "failed_count",
        "verified_at_utc", "verification", "summary", "failure_code",
        "failure_stage",
    }
    if not (
        set(selection) == expected_keys
        and selection.get("schema_version")
        == "exp-router-replication-selection-attempt-3-v1"
        and selection.get("experiment_id") == EXPERIMENT_ID
        and selection.get("run_id") == RUN_ID
        and selection.get("attempt_id") == ATTEMPT_ID
        and type(selection.get("model_seed")) is int
        and selection.get("model_seed") == MODEL_SEED
        and exact_typed_equal(
            selection.get("seed_contract"), formal_config.get("seed_contract")
        )
        and selection.get("status") == "Selected"
        and is_timestamp(selection.get("selected_at_utc"))
        and selection.get("primary_policy") == "logistic_router"
        and type(selection.get("primary_nominal_call_rate")) is float
        and selection.get("primary_nominal_call_rate") == 0.15
        and type(selection.get("primary_gate_passed")) is bool
        and selection.get("decision")
        == ("Pass" if selection.get("primary_gate_passed") else "Fail")
        and type(selection.get("verification_attempt")) is int
        and selection.get("verification_attempt") == 3
        and exact_typed_equal(
            selection.get("finalizer"), artifact(Path(__file__).resolve())
        )
        and exact_typed_equal(selection.get("completions"), expected_completions)
        and exact_typed_equal(
            selection.get("stage_artifacts"), expected_stage_artifacts
        )
        and isinstance(chain, list)
        and len(chain) == 3
        and all(isinstance(row, dict) and set(row) == chain_keys for row in chain)
        and exact_typed_equal(chain, expected_chain)
        and [row["verification_attempt"] for row in chain] == [1, 2, 3]
        and [row["status"] for row in chain] == ["Failed", "Failed", "Passed"]
        and all(type(row["passed_count"]) is int for row in chain)
        and all(type(row["failed_count"]) is int for row in chain)
        and exact_typed_equal(selection.get("recovery_lineage"), expected_lineage)
        and selection.get("claim_boundary") == SELECTION_CLAIM_BOUNDARY
        and timestamp(chain[0]["verified_at_utc"])
        <= timestamp(chain[1]["verified_at_utc"])
        <= timestamp(chain[2]["verified_at_utc"])
        <= timestamp(selection["selected_at_utc"])
        and not public_sensitive_paths(selection)
    ):
        raise ValueError("Incident-002 selection payload drift")


def build_selection() -> tuple[dict[str, Any], Path]:
    selection_path = resolve_relative(SELECTION_REL)
    if os.path.lexists(selection_path):
        raise FileExistsError("Selection is append-only")
    config_path, config = load_config()
    attempt1, attempt1_records = validate_attempt1(config)
    attempt2, attempt2_records = validate_attempt2(config)
    attempt3, attempt3_records = validate_attempt3(config, attempt1)
    completion, completion_record = validate_completion(config, attempt3, attempt3_records)
    oof, oof_record = validate_stage_completion("oof", OOF_COMPLETION_REL, "exp-oof-completion-v2")
    calibration, calibration_record = validate_stage_completion(
        "calibration", CALIBRATION_COMPLETION_REL, "exp-059-calibration-completion-v2"
    )
    validate_modes()
    if public_tree_digest() != config["public_state"]["content_tree"]:
        raise ValueError("Public content tree drift")
    private = config["private_invariant"]
    for record in private["artifacts"]:
        require_record(record)
    if not (
        type(private.get("artifact_count")) is int
        and private.get("artifact_count") == 2
        and private.get("sha256") == canonical_digest(private["artifacts"])
        and isinstance(private.get("modes"), list)
        and len(private["modes"]) == 5
        and all(row.get("matches_expected") is True for row in private["modes"])
    ):
        raise ValueError("Private artifact digest/mode inventory drift")
    if not (
        timestamp(attempt1["verified_at_utc"])
        <= timestamp(attempt2["verified_at_utc"])
        <= timestamp(attempt3["verified_at_utc"])
        <= timestamp(completion["completed_at_utc"])
    ):
        raise ValueError("Failed-Failed-Passed chronology drift")
    selected_at = utc_now()
    if timestamp(completion["completed_at_utc"]) > timestamp(selected_at):
        raise ValueError("Selection timestamp precedes completion")
    attempt_chain = [
        {
            "verification_attempt": 1,
            "status": "Failed",
            "passed_count": 4417,
            "failed_count": 17,
            "verified_at_utc": attempt1["verified_at_utc"],
            "verification": attempt1_records["verification"],
            "summary": attempt1_records["summary"],
            "failure_code": None,
            "failure_stage": None,
        },
        {
            "verification_attempt": 2,
            "status": "Failed",
            "passed_count": 0,
            "failed_count": 1,
            "verified_at_utc": attempt2["verified_at_utc"],
            "verification": attempt2_records["verification"],
            "summary": attempt2_records["summary"],
            "failure_code": "deterministic_contract_failure",
            "failure_stage": "verification_build",
        },
        {
            "verification_attempt": 3,
            "status": "Passed",
            "passed_count": 4434,
            "failed_count": 0,
            "verified_at_utc": attempt3["verified_at_utc"],
            "verification": attempt3_records["verification"],
            "summary": attempt3_records["summary"],
            "failure_code": None,
            "failure_stage": None,
        },
    ]
    selection = {
        "schema_version": "exp-router-replication-selection-attempt-3-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "model_seed": MODEL_SEED,
        "seed_contract": completion["seed_contract"],
        "status": "Selected",
        "selected_at_utc": selected_at,
        "primary_policy": "logistic_router",
        "primary_nominal_call_rate": 0.15,
        "primary_gate_passed": completion["primary_gate_passed"],
        "decision": completion["decision"],
        "verification_attempt": 3,
        "finalizer": artifact(Path(__file__).resolve()),
        "completions": {
            "oof": oof_record,
            "calibration": calibration_record,
            "router": completion_record,
        },
        "stage_artifacts": {
            "oof": {"config": oof["config"], **oof["artifacts"]},
            "calibration": calibration["artifacts"],
            "router": completion["artifacts"],
        },
        "attempt_chain": attempt_chain,
        "recovery_lineage": completion["recovery_lineage"],
        "claim_boundary": SELECTION_CLAIM_BOUNDARY,
    }
    validate_selection_payload(
        selection,
        expected_chain=attempt_chain,
        expected_completions={
            "oof": oof_record,
            "calibration": calibration_record,
            "router": completion_record,
        },
        expected_stage_artifacts={
            "oof": {"config": oof["config"], **oof["artifacts"]},
            "calibration": calibration["artifacts"],
            "router": completion["artifacts"],
        },
        expected_lineage=completion["recovery_lineage"],
    )
    if artifact(config_path) != selection["recovery_lineage"]["incident_002_config"]:
        raise ValueError("Selection Incident-002 config binding drift")
    return selection, selection_path


def finalize() -> dict[str, Any]:
    selection, path = build_selection()
    create_json_once(path, selection)
    return selection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-id", choices=(EXPERIMENT_ID,), required=True)
    parser.add_argument("--attempt-id", choices=(ATTEMPT_ID,), required=True)
    return parser.parse_args()


def main() -> None:
    parse_args()
    result = finalize()
    print(json.dumps({"status": result["status"], "decision": result["decision"]}, sort_keys=True))


if __name__ == "__main__":
    main()
