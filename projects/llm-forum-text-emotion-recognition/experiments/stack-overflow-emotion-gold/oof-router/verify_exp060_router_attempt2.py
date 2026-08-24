#!/usr/bin/env python3
"""Incident-001 recovery verifier for the EXP-061 seed-43 router attempt.

The scientific analysis is never rerun.  The ``normalize`` scope performs the
authorized sixteen-path metadata-only repair.  The ``final`` scope then executes
the frozen verifier twice in separate fresh canonical mirrors: once unchanged,
and once with the single registered ``/router/policies`` JSON overlay.
"""

from __future__ import annotations

import argparse
import ast
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]

EXPERIMENT_ID = "EXP-061"
RUN_ID = "exp-061-seed-43-router-replication"
ATTEMPT_ID = "attempt-1"
MODEL_SEED = 43
RQ_ID = "RQ-S3"
ROUTER_STAGE = "pre-qwen-router-replication"
RECOVERY_PYTHON = "/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
FULL_POLICY_ORDER = (
    "m1_only",
    "m3_only",
    "m1_max_entropy",
    "m1_threshold_proximity",
    "logistic_router",
)
DEPLOYABLE_POLICY_ORDER = FULL_POLICY_ORDER[2:]

BASE = Path("experiments/stack-overflow-emotion-gold/oof-router")
PUBLIC_ATTEMPT_REL = BASE / "runs" / RUN_ID / ATTEMPT_ID
PRIVATE_ATTEMPT_REL = BASE / "private" / RUN_ID / ATTEMPT_ID
ROUTER_REL = PUBLIC_ATTEMPT_REL / "router"
PRIVATE_ROUTER_REL = PRIVATE_ATTEMPT_REL / "router"
FORMAL_CONFIG_REL = BASE / "configs/exp-061-seed-43-router-replication-router-formal-attempt-1.json"
CANONICAL_VERIFIER_REL = BASE / "verify_exp060_router.py"
CANONICAL_RUNNER_REL = BASE / "run_exp060_router.py"
RECOVERY_TESTS_REL = BASE / "tests/test_exp060_router_attempt2.py"
FINALIZER_REL = BASE / "finalize_router_replication_attempt.py"
FINALIZER_TESTS_REL = BASE / "tests/test_finalize_router_recovery_attempt.py"
AMENDMENT_REL = Path(
    "experiments/stack-overflow-emotion-gold/protocols/"
    "exp-061-exp060-final-verification-attempt-2-amendment.md"
)
AMENDMENT_CONFIG_REL = BASE / (
    "configs/exp-061-seed-43-router-replication-router-"
    "verification-attempt-2-amendment.json"
)
ORIGINAL_VERIFICATION_REL = ROUTER_REL / "verification.json"
ORIGINAL_SUMMARY_REL = ROUTER_REL / "VERIFICATION-SUMMARY.md"
ATTEMPT2_VERIFICATION_REL = ROUTER_REL / "verification-attempt-2.json"
ATTEMPT2_SUMMARY_REL = ROUTER_REL / "VERIFICATION-SUMMARY-ATTEMPT-2.md"
RUN_REL = ROUTER_REL / "run.json"
SELECTED_REL = ROUTER_REL / "selected-operating-point.json"
PRIVATE_ROUTER_OOF_REL = PRIVATE_ROUTER_REL / "router-oof.npz"
PAIRED_OOF_REL = PRIVATE_ATTEMPT_REL / "paired-oof.npz"
COMPLETION_REL = ROUTER_REL / "router-complete.json"
SELECTION_REL = BASE / "runs" / RUN_ID / "selected-attempt.json"

EXPECTED_IMMUTABLE: dict[Path, tuple[int, str]] = {
    FORMAL_CONFIG_REL: (13393, "d74beb9b3dd1140be0215e29e87b71b2a25f332682420a2883af7aa867cd566b"),
    CANONICAL_VERIFIER_REL: (119887, "920f6565bd378c8f7cfe415a78e505123336602fb228dad95771fcc14e471b15"),
    CANONICAL_RUNNER_REL: (106000, "873d53f45d587918b7c1b466a93b8da0b397732baa072af1b43e50a16150dc65"),
    RUN_REL: (10497, "199249d6d7a1cc1e8fb2daab43ade9ca63deabc3a25dc8bdf3f1a3370c677884"),
    SELECTED_REL: (6669, "8bb32ef80a594a9b8341877efa37d0deb1d54f11650801dfae7bf232d66fa7a7"),
    PRIVATE_ROUTER_OOF_REL: (500924, "9c71020d194454e60e384f5f195089d6bced95e45d67e8046cb55b74afeeb755"),
    PAIRED_OOF_REL: (308098, "b9513696e80aca12e60e719fb109e24f1412781e9996e5ad6b9e0221803bb2e8"),
    ORIGINAL_VERIFICATION_REL: (1090642, "69057b2f1af3ab2964f6d6a5037d1cc28a9a1c3017d68be44c872a71d44a5d62"),
    ORIGINAL_SUMMARY_REL: (1083, "f783230f779fcb149def1cca1c0b0b8cdce8c659a2dbd0aa6a319c7971b1822e"),
}

EXPECTED_ATTEMPT1_FAILURES = {
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

MODE_REPAIRS: tuple[tuple[Path, str, int, int], ...] = (
    (ROUTER_REL, "directory", 0o700, 0o755),
    (ROUTER_REL / "frozen-sources", "directory", 0o700, 0o755),
    (ROUTER_REL / "REPORT.md", "file", 0o600, 0o644),
    (ROUTER_REL / "bootstrap.json", "file", 0o600, 0o644),
    (ROUTER_REL / "call-rate-performance.csv", "file", 0o600, 0o644),
    (ROUTER_REL / "call-rate-performance.png", "file", 0o600, 0o644),
    (ROUTER_REL / "feature-contract.json", "file", 0o600, 0o644),
    (ROUTER_REL / "fold-summary.csv", "file", 0o600, 0o644),
    (ROUTER_REL / "policy-comparisons.csv", "file", 0o600, 0o644),
    (ROUTER_REL / "positive-label-retention.csv", "file", 0o600, 0o644),
    (ROUTER_REL / "random-routing.csv", "file", 0o600, 0o644),
    (ROUTER_REL / "routed-risk-coverage.csv", "file", 0o600, 0o644),
    (ROUTER_REL / "routed-risk-coverage.png", "file", 0o600, 0o644),
    (ROUTER_REL / "router-discrimination.json", "file", 0o600, 0o644),
    (ROUTER_REL / "run.json", "file", 0o600, 0o644),
    (ROUTER_REL / "selected-operating-point.json", "file", 0o600, 0o644),
)

PRIVATE_MODE_INVARIANTS: tuple[tuple[Path, str, int], ...] = (
    (BASE / "private" / RUN_ID, "directory", 0o700),
    (PRIVATE_ATTEMPT_REL, "directory", 0o700),
    (PAIRED_OOF_REL, "file", 0o600),
    (PRIVATE_ROUTER_REL, "directory", 0o700),
    (PRIVATE_ROUTER_OOF_REL, "file", 0o600),
)

APPEND_ONLY_ROUTER_PATHS = {
    Path("verification-attempt-2.json"),
    Path("VERIFICATION-SUMMARY-ATTEMPT-2.md"),
    Path("router-complete.json"),
}
PUBLIC_TREE_DIGEST_ALGORITHM = (
    "sha256(canonical-json(sorted(relative_path,bytes,sha256))); "
    "exclude exact router-root-relative paths verification-attempt-2.json, "
    "VERIFICATION-SUMMARY-ATTEMPT-2.md, router-complete.json"
)
ATTEMPT2_INDEPENDENCE = {
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
ATTEMPT2_FAILURE_STAGES = {"verification_build"}
ATTEMPT2_FAILURE_CODES = {"deterministic_contract_failure"}
ATTEMPT2_CLAIM_BOUNDARY = (
    "Independent verification of unchanged seed-43 train-OOF router evidence under "
    "Incident-001's sole SHA-bound clerical config overlay; no validation, test, "
    "model, raw-text, deployment-generalization, or mechanism claim."
)
COMPLETION_NEXT_GATE = (
    "Finalizer must bind OOF, EXP-059, router completion, and recovery lineage."
)
COMPLETION_CLAIM_BOUNDARY = (
    "Completes one independently recovered seed-43 train-only router stage; not a "
    "cross-seed claim."
)
MIRROR_METADATA_KEYS = {
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


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def resolve_relative(relative: Path | str) -> Path:
    value = Path(relative)
    if value.is_absolute() or not value.parts or any(part in ("", ".", "..") for part in value.parts):
        raise ValueError(f"Path is not normalized project-relative: {relative}")
    cursor = PROJECT_ROOT
    for part in value.parts:
        cursor = cursor / part
        if os.path.lexists(cursor) and cursor.is_symlink():
            raise ValueError(f"Path traverses a symbolic link: {relative}")
    resolved = (PROJECT_ROOT / value).resolve()
    if not resolved.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {relative}")
    return resolved


def display_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))


def artifact(path: Path) -> dict[str, Any]:
    return {"path": display_path(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def require_expected(relative: Path) -> Path:
    expected_bytes, expected_sha256 = EXPECTED_IMMUTABLE[relative]
    path = resolve_relative(relative)
    if (
        not path.is_file()
        or path.stat().st_size != expected_bytes
        or sha256(path) != expected_sha256
    ):
        raise ValueError(f"Immutable Incident-001 artifact drift: {relative}")
    return path


def require_canonical_runner_binding() -> Path:
    canonical = require_expected(CANONICAL_RUNNER_REL)
    run = load_json(require_expected(RUN_REL))
    frozen_sources = run.get("frozen_sources", {})
    if not isinstance(frozen_sources, dict) or "runner" not in frozen_sources:
        raise ValueError("Router run has no frozen runner record")
    frozen_record = frozen_sources["runner"]
    require_record(frozen_record)
    canonical_record = artifact(canonical)
    if not (
        frozen_record.get("bytes") == canonical_record["bytes"]
        and frozen_record.get("sha256") == canonical_record["sha256"]
    ):
        raise ValueError("Canonical and run-frozen router runner bytes differ")
    return canonical


def require_record(record: dict[str, Any]) -> Path:
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
    path = resolve_relative(record["path"])
    if (
        not path.is_file()
        or path.stat().st_size != record["bytes"]
        or sha256(path) != record["sha256"]
    ):
        raise ValueError(f"Artifact record drift: {record.get('path')}")
    return path


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def read_bound_regular_file(path: Path, *, expected_mode: int = 0o644) -> bytes:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise OSError("O_NOFOLLOW is required")
    descriptor = os.open(path, os.O_RDONLY | nofollow)
    try:
        lexical_before = os.lstat(path)
        observed_before = os.fstat(descriptor)
        with os.fdopen(descriptor, "rb", closefd=False) as source:
            payload = source.read()
        observed_after = os.fstat(descriptor)
        lexical_after = os.lstat(path)
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
            raise ValueError(f"Bound regular-file identity/mode drift: {path}")
        return payload
    finally:
        os.close(descriptor)


def load_bound_json(path: Path, *, expected_mode: int = 0o644) -> dict[str, Any]:
    value = json.loads(read_bound_regular_file(path, expected_mode=expected_mode))
    if not isinstance(value, dict):
        raise ValueError(f"Expected bound JSON object: {path}")
    return value


def iter_records(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if {"path", "bytes", "sha256"}.issubset(value):
            yield value
        else:
            for child in value.values():
                yield from iter_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_records(child)


def file_tree_digest(root: Path) -> dict[str, Any]:
    """Digest immutable public content while ignoring later append-only recovery files."""

    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"Tree root is missing or symbolic: {root}")
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Tree contains a symbolic link: {path}")
        relative = path.relative_to(root)
        if path.is_file() and relative not in APPEND_ONLY_ROUTER_PATHS:
            rows.append(
                {
                    "path": str(relative),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    return {"file_count": len(rows), "sha256": canonical_digest(rows)}


def private_artifact_digest() -> dict[str, Any]:
    rows = [artifact(require_expected(PAIRED_OOF_REL)), artifact(require_expected(PRIVATE_ROUTER_OOF_REL))]
    return {
        "artifact_count": len(rows),
        "sha256": canonical_digest(rows),
        "artifacts": rows,
        "modes": private_mode_manifest(),
    }


def private_mode_manifest() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative, kind, expected_mode in PRIVATE_MODE_INVARIANTS:
        path = resolve_relative(relative)
        observed = stat.S_IMODE(path.stat().st_mode)
        rows.append(
            {
                "path": str(relative),
                "type": kind,
                "expected_mode": f"0o{expected_mode:o}",
                "observed_mode": f"0o{observed:o}",
                "matches_expected": observed == expected_mode,
            }
        )
    return rows


def mode_manifest(after: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative, kind, before_mode, after_mode in MODE_REPAIRS:
        path = resolve_relative(relative)
        expected = after_mode if after else before_mode
        nofollow = getattr(os, "O_NOFOLLOW", None)
        odirectory = getattr(os, "O_DIRECTORY", None)
        if nofollow is None or odirectory is None:
            raise OSError("O_NOFOLLOW and O_DIRECTORY are required")
        flags = os.O_RDONLY | nofollow | (odirectory if kind == "directory" else 0)
        descriptor = os.open(path, flags)
        try:
            lexical_before = os.lstat(path)
            observed_before = os.fstat(descriptor)
            identity = (observed_before.st_dev, observed_before.st_ino)
            observed_kind = (
                "directory"
                if stat.S_ISDIR(observed_before.st_mode)
                else "file"
                if stat.S_ISREG(observed_before.st_mode)
                else "other"
            )
            payload = b""
            if kind == "file":
                with os.fdopen(descriptor, "rb", closefd=False) as source:
                    payload = source.read()
            observed_after = os.fstat(descriptor)
            lexical_after = os.lstat(path)
            if not (
                observed_kind == kind
                and (lexical_before.st_dev, lexical_before.st_ino) == identity
                and (observed_after.st_dev, observed_after.st_ino) == identity
                and (lexical_after.st_dev, lexical_after.st_ino) == identity
                and observed_after.st_size == observed_before.st_size
                and observed_after.st_nlink == observed_before.st_nlink
                and stat.S_IMODE(observed_after.st_mode)
                == stat.S_IMODE(observed_before.st_mode)
                and (kind != "file" or observed_before.st_size == len(payload))
            ):
                raise ValueError(f"Public mode target identity/type drift: {relative}")
            observed = stat.S_IMODE(observed_before.st_mode)
            link_contract = kind != "file" or observed_before.st_nlink == 1
        finally:
            os.close(descriptor)
        row: dict[str, Any] = {
            "path": str(relative),
            "type": kind,
            "before_mode": f"0o{before_mode:o}",
            "after_mode": f"0o{after_mode:o}",
            "observed_mode": f"0o{observed:o}",
            "matches_expected": observed == expected and link_contract,
        }
        if kind == "file":
            row.update(
                {
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
        rows.append(row)
    return rows


def frozen_mode_manifest() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative, kind, before_mode, after_mode in MODE_REPAIRS:
        row: dict[str, Any] = {
            "path": str(relative),
            "type": kind,
            "before_mode": f"0o{before_mode:o}",
            "after_mode": f"0o{after_mode:o}",
        }
        if kind == "file":
            path = resolve_relative(relative)
            row.update({"bytes": path.stat().st_size, "sha256": sha256(path)})
        rows.append(row)
    return rows


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


def load_amendment_config() -> tuple[Path, dict[str, Any]]:
    path = resolve_relative(AMENDMENT_CONFIG_REL)
    config = load_json(path)
    expected_top_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "model_seed",
        "incident_id", "authorization", "implementation", "target",
        "clerical_overlay", "public_mode_normalization", "private_invariant",
        "outputs", "commands",
    }
    if not (
        set(config) == expected_top_keys
        and config.get("schema_version")
        == "exp-router-verification-attempt-2-amendment-config-v1"
        and config.get("experiment_id") == EXPERIMENT_ID
        and config.get("run_id") == RUN_ID
        and config.get("attempt_id") == ATTEMPT_ID
        and int(config.get("model_seed", -1)) == MODEL_SEED
        and config.get("incident_id") == "001"
    ):
        raise ValueError("Unexpected Incident-001 amendment config identity")
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
    if config.get("authorization") != expected_authorization:
        raise PermissionError("Incident-001 authorization drift")
    expected_outputs = {
        "verification": str(ATTEMPT2_VERIFICATION_REL),
        "summary": str(ATTEMPT2_SUMMARY_REL),
        "completion": str(COMPLETION_REL),
        "selection": str(SELECTION_REL),
    }
    if config.get("outputs") != expected_outputs:
        raise ValueError("Incident-001 output-path drift")

    implementation = config.get("implementation", {})
    expected_implementation = {
        "amendment_protocol": AMENDMENT_REL,
        "base_verifier": CANONICAL_VERIFIER_REL,
        "recovery_verifier": Path(display_path(Path(__file__).resolve())),
        "recovery_tests": RECOVERY_TESTS_REL,
        "finalizer": FINALIZER_REL,
        "finalizer_tests": FINALIZER_TESTS_REL,
    }
    if set(implementation) != set(expected_implementation):
        raise ValueError("Incident-001 implementation inventory drift")
    for name, relative in expected_implementation.items():
        if require_record(implementation[name]) != resolve_relative(relative):
            raise ValueError(f"Incident-001 implementation path drift: {name}")
    if require_record(implementation["base_verifier"]) != require_expected(CANONICAL_VERIFIER_REL):
        raise ValueError("Incident-001 base verifier hash drift")

    expected_target_paths = {
        "formal_config": FORMAL_CONFIG_REL,
        "run": RUN_REL,
        "selected_operating_point": SELECTED_REL,
        "paired_oof": PAIRED_OOF_REL,
        "private_router_oof": PRIVATE_ROUTER_OOF_REL,
        "attempt_1_failed_verification": ORIGINAL_VERIFICATION_REL,
        "attempt_1_failed_summary": ORIGINAL_SUMMARY_REL,
    }
    target = config.get("target", {})
    if set(target) != set(expected_target_paths):
        raise ValueError("Incident-001 target inventory drift")
    for name, relative in expected_target_paths.items():
        if require_record(target[name]) != require_expected(relative):
            raise ValueError(f"Incident-001 target path drift: {name}")

    original = load_json(require_expected(FORMAL_CONFIG_REL))
    effective = copy.deepcopy(original)
    effective["router"]["policies"] = list(FULL_POLICY_ORDER)
    expected_diff = [
        {"path": "$.router.policies", "before": list(DEPLOYABLE_POLICY_ORDER), "after": list(FULL_POLICY_ORDER)}
    ]
    expected_overlay = {
        "operation": "replace",
        "json_pointer": "/router/policies",
        "match_input_sha256": EXPECTED_IMMUTABLE[FORMAL_CONFIG_REL][1],
        "before": list(DEPLOYABLE_POLICY_ORDER),
        "after": list(FULL_POLICY_ORDER),
        "deployable_policy_order_unchanged": list(DEPLOYABLE_POLICY_ORDER),
        "recursive_diff": expected_diff,
        "maximum_changed_nodes": 1,
    }
    if config.get("clerical_overlay") != expected_overlay or recursive_diff(original, effective) != expected_diff:
        raise ValueError("Incident-001 clerical overlay is not the unique registered diff")

    normalization = config.get("public_mode_normalization", {})
    if normalization != {
        "path_count": len(MODE_REPAIRS),
        "pre_manifest": frozen_mode_manifest(),
        "content_tree_digest_algorithm": PUBLIC_TREE_DIGEST_ALGORITHM,
        "content_tree_before": normalization.get("content_tree_before"),
    }:
        raise ValueError("Incident-001 exact public-mode manifest drift")
    tree = normalization.get("content_tree_before")
    if not isinstance(tree, dict) or set(tree) != {"file_count", "sha256"}:
        raise ValueError("Incident-001 public tree digest schema drift")
    private = config.get("private_invariant")
    if not isinstance(private, dict) or set(private) != {"artifact_count", "sha256", "artifacts", "modes"}:
        raise ValueError("Incident-001 private invariant schema drift")
    expected_commands = {
        scope: f"{RECOVERY_PYTHON} {BASE}/verify_exp060_router_attempt2.py --scope {scope}"
        for scope in ("normalize", "final", "complete", "completion")
    }
    if config.get("commands") != expected_commands:
        raise ValueError("Incident-001 command contract drift")
    if len(list(iter_records(config))) != 29:
        raise ValueError("Incident-001 artifact-record inventory drift")
    return path, config


def check(name: str, passed: bool, detail: Any = None) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


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


def failed_names(result: dict[str, Any]) -> set[str]:
    return {
        str(row.get("name"))
        for row in result.get("checks", [])
        if isinstance(row, dict) and row.get("passed") is not True
    }


def identity_matches(value: dict[str, Any]) -> bool:
    return (
        value.get("experiment_id") == EXPERIMENT_ID
        and value.get("run_id") == RUN_ID
        and value.get("attempt_id") == ATTEMPT_ID
        and is_exact_int(value.get("model_seed"))
        and value.get("model_seed") == MODEL_SEED
    )


def failure_snapshots() -> dict[str, dict[str, Any]]:
    return {
        "verification": artifact(require_expected(ORIGINAL_VERIFICATION_REL)),
        "summary": artifact(require_expected(ORIGINAL_SUMMARY_REL)),
    }


def exact_attempt1_failure_bound() -> bool:
    value = load_json(require_expected(ORIGINAL_VERIFICATION_REL))
    return (
        value.get("status") == "Failed"
        and is_exact_int(value.get("passed_count"))
        and value.get("passed_count") == 4417
        and is_exact_int(value.get("failed_count"))
        and value.get("failed_count") == 17
        and exact_check_rows(value.get("checks", []), 4434)
        and failed_names(value) == EXPECTED_ATTEMPT1_FAILURES
        and identity_matches(value)
    )


def fd_sha256(descriptor: int, size: int) -> str:
    digest = hashlib.sha256()
    offset = 0
    while offset < size:
        chunk = os.pread(descriptor, min(4 * 1024 * 1024, size - offset), offset)
        if not chunk:
            raise RuntimeError("File descriptor ended before its frozen byte count")
        digest.update(chunk)
        offset += len(chunk)
    if os.pread(descriptor, 1, size):
        raise RuntimeError("File descriptor exceeds its frozen byte count")
    return digest.hexdigest()


def verify_opened_mode_preflight(
    opened: list[dict[str, Any]], pre_manifest: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Revalidate all opened targets from descriptors before the first fchmod."""

    frozen = {str(row.get("path")): row for row in pre_manifest}
    if len(frozen) != len(pre_manifest) or len(opened) != len(pre_manifest):
        raise ValueError("Mode-preflight inventory is not one-to-one")
    proofs: list[dict[str, Any]] = []
    for item in opened:
        descriptor = int(item["descriptor"])
        path = Path(item["path"])
        relative = str(item["relative"])
        kind = str(item["kind"])
        before_mode = int(item["before_mode"])
        identity = tuple(item["identity"])
        expected = frozen.get(relative)
        if expected is None:
            raise ValueError(f"Opened target is absent from frozen manifest: {relative}")
        observed_before = os.fstat(descriptor)
        lexical_before = os.lstat(path)
        observed_kind = (
            "directory" if stat.S_ISDIR(observed_before.st_mode)
            else "file" if stat.S_ISREG(observed_before.st_mode)
            else "other"
        )
        if not (
            expected.get("path") == relative
            and expected.get("type") == kind
            and expected.get("before_mode") == f"0o{before_mode:o}"
            and observed_kind == kind
            and stat.S_IMODE(observed_before.st_mode) == before_mode
            and (observed_before.st_dev, observed_before.st_ino) == identity
            and (lexical_before.st_dev, lexical_before.st_ino) == identity
            and observed_before.st_nlink >= 1
            and (kind != "file" or observed_before.st_nlink == 1)
        ):
            raise PermissionError(f"Opened mode-preflight identity drift: {relative}")
        proof: dict[str, Any] = {
            "path": relative,
            "type": kind,
            "device": observed_before.st_dev,
            "inode": observed_before.st_ino,
            "link_count": observed_before.st_nlink,
            "mode": f"0o{stat.S_IMODE(observed_before.st_mode):o}",
        }
        if kind == "file":
            expected_bytes = int(expected.get("bytes", -1))
            expected_sha256 = str(expected.get("sha256", ""))
            observed_sha256 = fd_sha256(descriptor, expected_bytes)
            if (
                observed_before.st_size != expected_bytes
                or observed_sha256 != expected_sha256
            ):
                raise ValueError(f"Opened mode-preflight frozen bytes drift: {relative}")
            proof.update({"bytes": expected_bytes, "sha256": observed_sha256})
        observed_after = os.fstat(descriptor)
        lexical_after = os.lstat(path)
        if not (
            (observed_after.st_dev, observed_after.st_ino) == identity
            and (lexical_after.st_dev, lexical_after.st_ino) == identity
            and observed_after.st_nlink == observed_before.st_nlink
            and observed_after.st_size == observed_before.st_size
            and stat.S_IMODE(observed_after.st_mode) == before_mode
        ):
            raise PermissionError(f"Opened mode-preflight changed during hashing: {relative}")
        proofs.append(proof)
    return proofs


def normalize_public_modes() -> dict[str, Any]:
    """Apply the exact authorized sixteen-path mode repair, and nothing else."""

    _, config = load_amendment_config()
    before_tree = file_tree_digest(resolve_relative(ROUTER_REL))
    before_private = private_artifact_digest()
    before_failure = failure_snapshots()
    if (
        before_tree != config["public_mode_normalization"]["content_tree_before"]
        or before_private != config["private_invariant"]
        or not exact_attempt1_failure_bound()
    ):
        raise ValueError("Incident-001 pre-normalization invariant drift")
    before_rows = mode_manifest(after=False)
    if not all(row["matches_expected"] for row in before_rows):
        raise PermissionError("Incident-001 modes do not match the frozen pre-manifest")

    nofollow = getattr(os, "O_NOFOLLOW", None)
    odirectory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or odirectory is None:
        raise OSError("O_NOFOLLOW and O_DIRECTORY are required")
    if not all(row["matches_expected"] for row in before_private["modes"]):
        raise PermissionError("Incident-001 private mode/parent invariant drift")
    opened: list[dict[str, Any]] = []
    fd_preflight: list[dict[str, Any]] = []
    try:
        for relative, kind, before_mode, after_mode in MODE_REPAIRS:
            path = resolve_relative(relative)
            lexical = os.lstat(path)
            flags = os.O_RDONLY | nofollow | (odirectory if kind == "directory" else 0)
            descriptor = os.open(path, flags)
            observed = os.fstat(descriptor)
            observed_kind = (
                "directory" if stat.S_ISDIR(observed.st_mode)
                else "file" if stat.S_ISREG(observed.st_mode)
                else "other"
            )
            if (
                observed_kind != kind
                or stat.S_IMODE(observed.st_mode) != before_mode
                or (lexical.st_dev, lexical.st_ino) != (observed.st_dev, observed.st_ino)
                or (kind == "file" and observed.st_nlink != 1)
            ):
                os.close(descriptor)
                raise PermissionError(f"Mode-normalization target drift: {relative}")
            opened.append(
                {
                    "descriptor": descriptor,
                    "after_mode": after_mode,
                    "before_mode": before_mode,
                    "path": path,
                    "relative": str(relative),
                    "identity": (observed.st_dev, observed.st_ino),
                    "kind": kind,
                }
            )
        fd_preflight = verify_opened_mode_preflight(
            opened, config["public_mode_normalization"]["pre_manifest"]
        )
        for item in opened:
            os.fchmod(int(item["descriptor"]), int(item["after_mode"]))
        for item in opened:
            descriptor = int(item["descriptor"])
            after_mode = int(item["after_mode"])
            path = Path(item["path"])
            identity = tuple(item["identity"])
            kind = str(item["kind"])
            observed = os.fstat(descriptor)
            lexical = os.lstat(path)
            if (
                stat.S_IMODE(observed.st_mode) != after_mode
                or (observed.st_dev, observed.st_ino) != identity
                or (lexical.st_dev, lexical.st_ino) != identity
                or (kind == "file" and observed.st_nlink != 1)
            ):
                raise RuntimeError(f"Post-normalization inode binding drift: {path}")
    finally:
        for item in opened:
            os.close(int(item["descriptor"]))

    after_rows = mode_manifest(after=True)
    after_tree = file_tree_digest(resolve_relative(ROUTER_REL))
    after_private = private_artifact_digest()
    if (
        not all(row["matches_expected"] for row in after_rows)
        or after_tree != before_tree
        or after_private != before_private
        or not all(row["matches_expected"] for row in after_private["modes"])
        or failure_snapshots() != before_failure
    ):
        raise RuntimeError("Incident-001 post-normalization invariant failed")
    return {
        "status": "Complete",
        "scope": "normalize",
        "target_count": len(MODE_REPAIRS),
        "fd_preflight": fd_preflight,
        "before": before_rows,
        "after": after_rows,
        "content_tree_before": before_tree,
        "content_tree_after": after_tree,
        "private_before": before_private,
        "private_after": after_private,
        "attempt_1_failure_before": before_failure,
        "attempt_1_failure_after": failure_snapshots(),
    }


def assert_no_runner_import(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            forbidden.extend(alias.name for alias in node.names if "run_exp060_router" in alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module and "run_exp060_router" in node.module:
            forbidden.append(node.module)
    if forbidden:
        raise ImportError(f"Verifier imports the analysis runner: {forbidden}")


class JsonOverlayProxy:
    """Module-local JSON proxy for the one SHA-bound clerical overlay."""

    def __init__(self, base: Any, expected_sha256: str) -> None:
        self._base = base
        self.expected_sha256 = expected_sha256
        self.loads_calls = 0
        self.matching_sha_load_count = 0
        self.overlay_load_count = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)

    def loads(self, value: Any, *args: Any, **kwargs: Any) -> Any:
        self.loads_calls += 1
        parsed = self._base.loads(value, *args, **kwargs)
        if isinstance(value, str):
            payload = value.encode("utf-8")
        elif isinstance(value, (bytes, bytearray)):
            payload = bytes(value)
        else:
            return parsed
        if hashlib.sha256(payload).hexdigest() != self.expected_sha256:
            return parsed
        self.matching_sha_load_count += 1
        if self.overlay_load_count:
            return parsed
        if not isinstance(parsed, dict):
            raise ValueError("SHA-bound config overlay did not parse as an object")
        effective = copy.deepcopy(parsed)
        if (
            effective.get("router", {}).get("policies") != list(DEPLOYABLE_POLICY_ORDER)
            or effective.get("router", {}).get("deployable_policy_order") != list(DEPLOYABLE_POLICY_ORDER)
        ):
            raise ValueError("SHA-bound config does not contain the registered clerical state")
        effective["router"]["policies"] = list(FULL_POLICY_ORDER)
        expected = [
            {"path": "$.router.policies", "before": list(DEPLOYABLE_POLICY_ORDER), "after": list(FULL_POLICY_ORDER)}
        ]
        if recursive_diff(parsed, effective) != expected:
            raise ValueError("JSON proxy attempted more than the registered overlay")
        self.overlay_load_count += 1
        return effective


def copy_regular_file(source: Path, destination: Path) -> dict[str, Any]:
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"Mirror source is not a regular non-symlink file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    source_fd = os.open(source, os.O_RDONLY | nofollow)
    try:
        source_stat = os.fstat(source_fd)
        lexical = os.lstat(source)
        if (
            not stat.S_ISREG(source_stat.st_mode)
            or (source_stat.st_dev, source_stat.st_ino) != (lexical.st_dev, lexical.st_ino)
        ):
            raise ValueError(f"Mirror source identity changed: {source}")
        destination_fd = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
            0o600,
        )
        try:
            while True:
                chunk = os.read(source_fd, 4 * 1024 * 1024)
                if not chunk:
                    break
                cursor = 0
                while cursor < len(chunk):
                    cursor += os.write(destination_fd, chunk[cursor:])
            os.fsync(destination_fd)
        finally:
            os.close(destination_fd)
    finally:
        os.close(source_fd)
    copied = os.lstat(destination)
    if not stat.S_ISREG(copied.st_mode) or copied.st_nlink != 1:
        raise ValueError(f"Mirror destination is linked or non-regular: {destination}")
    if destination.stat().st_size != source.stat().st_size or sha256(destination) != sha256(source):
        raise ValueError(f"Mirror byte copy mismatch: {source}")
    return {
        "path": display_path(source),
        "bytes": source.stat().st_size,
        "sha256": sha256(source),
    }


def mirror_source_relatives() -> list[Path]:
    config = load_json(require_expected(FORMAL_CONFIG_REL))
    run = load_json(require_expected(RUN_REL))
    relatives = {FORMAL_CONFIG_REL, CANONICAL_VERIFIER_REL, RUN_REL}
    for record in [*iter_records(config), *iter_records(run)]:
        source = require_record(record)
        relatives.add(Path(display_path(source)))
    forbidden = {
        ORIGINAL_VERIFICATION_REL,
        ORIGINAL_SUMMARY_REL,
        ATTEMPT2_VERIFICATION_REL,
        ATTEMPT2_SUMMARY_REL,
        COMPLETION_REL,
        SELECTION_REL,
    }
    if relatives & forbidden:
        raise ValueError("Mirror source inventory includes governance sidecars")
    return sorted(relatives)


def expected_mirror_copy_manifest() -> list[dict[str, Any]]:
    return [artifact(resolve_relative(relative)) for relative in mirror_source_relatives()]


def load_mirror_verifier(project_root: Path, label: str) -> Any:
    path = project_root / CANONICAL_VERIFIER_REL
    assert_no_runner_import(path)
    spec = importlib.util.spec_from_file_location(f"exp060_incident001_{label}", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.PROJECT_ROOT.resolve() != project_root.resolve():
        raise ValueError("Mirror verifier did not resolve the canonical temporary project root")
    return module


def set_mirror_output_modes(project_root: Path) -> None:
    public = project_root / ROUTER_REL
    private = project_root / PRIVATE_ROUTER_REL
    for root, directory_mode, file_mode in ((public, 0o755, 0o644), (private, 0o700, 0o600)):
        if not root.is_dir() or root.is_symlink():
            raise ValueError(f"Mirror output root is invalid: {root}")
        os.chmod(root, directory_mode)
        for child in sorted(root.rglob("*")):
            if child.is_symlink():
                raise ValueError(f"Mirror output contains a symlink: {child}")
            os.chmod(child, directory_mode if child.is_dir() else file_mode)


def run_fresh_mirror(label: str, overlay: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    """Execute the frozen verifier in one disposable canonical project mirror."""

    metadata: dict[str, Any] = {}
    temporary_path: Path | None = None
    with tempfile.TemporaryDirectory(prefix=f"exp061-incident001-{label}-") as temporary:
        project_root = Path(temporary)
        temporary_path = project_root
        os.chmod(project_root, 0o700)
        instance_token = hashlib.sha256(os.urandom(32)).hexdigest()
        expected_manifest = expected_mirror_copy_manifest()
        manifest = [
            copy_regular_file(resolve_relative(relative), project_root / relative)
            for relative in mirror_source_relatives()
        ]
        if manifest != expected_manifest:
            raise RuntimeError("Fresh mirror source-copy manifest drift")
        set_mirror_output_modes(project_root)
        module = load_mirror_verifier(project_root, label)
        proxy: JsonOverlayProxy | None = None
        if overlay:
            proxy = JsonOverlayProxy(module.json, EXPECTED_IMMUTABLE[FORMAL_CONFIG_REL][1])
            module.json = proxy
        result = module.verify(project_root / FORMAL_CONFIG_REL)
        verification_path = project_root / ORIGINAL_VERIFICATION_REL
        summary_path = project_root / ORIGINAL_SUMMARY_REL
        if not verification_path.is_file() or not summary_path.is_file():
            raise RuntimeError("Fresh mirror verifier did not emit both local sidecars")
        metadata = {
            "fresh_project_root": True,
            "project_root_mode": "0o700",
            "canonical_layout": True,
            "copy_only": True,
            "copied_file_count": len(manifest),
            "copy_manifest_sha256": canonical_digest(manifest),
            "no_symlinks": True,
            "no_hardlinks": True,
            "instance_token_sha256": instance_token,
            "overlay_enabled": overlay,
            "overlay_load_count": proxy.overlay_load_count if proxy else 0,
            "matching_sha_load_count": proxy.matching_sha_load_count if proxy else 0,
            "overlay_input_sha256": proxy.expected_sha256 if proxy else None,
            "cleaned": False,
        }
    if temporary_path is None or temporary_path.exists():
        raise RuntimeError("Fresh mirror was not cleaned")
    metadata["cleaned"] = True
    return result, metadata


def expected_verified_artifacts() -> dict[str, Any]:
    return {
        "config": artifact(require_expected(FORMAL_CONFIG_REL)),
        "run": artifact(require_expected(RUN_REL)),
        "input": artifact(require_expected(PAIRED_OOF_REL)),
        "private_router_oof": artifact(require_expected(PRIVATE_ROUTER_OOF_REL)),
    }


def original_check_names() -> list[str]:
    original = load_json(require_expected(ORIGINAL_VERIFICATION_REL))
    names = [str(row.get("name")) for row in original.get("checks", [])]
    if len(names) != 4434 or len(set(names)) != 4434:
        raise ValueError("Original verifier check-name inventory drift")
    return names


def validate_base_recomputation(result: dict[str, Any], *, overlay: bool) -> None:
    checks = result.get("checks", [])
    names = [str(row.get("name")) for row in checks]
    expected_independence = {
        "runner_imported": False,
        "raw_exp058_recomputation": True,
        "nested_thresholds_recomputed": True,
        "scalers_and_routers_refit": True,
        "public_and_private_outputs_recomputed": True,
    }
    expected_split = {
        "accessed_splits": ["train-oof"],
        "validation_accessed": False,
        "test_inputs_accessed": False,
        "test_labels_accessed": False,
        "raw_text_accessed": False,
        "model_loaded_or_forward_run": False,
    }
    expected_failures = set() if overlay else {"config.router"}
    if not (
        result.get("schema_version") == "exp-router-formal-verification-v2"
        and result.get("scope") == "final"
        and result.get("rq_id") == RQ_ID
        and result.get("stage") == ROUTER_STAGE
        and identity_matches(result)
        and names == original_check_names()
        and exact_check_rows(checks, 4434)
        and failed_names(result) == expected_failures
        and is_exact_int(result.get("passed_count"))
        and result.get("passed_count") == (4434 if overlay else 4433)
        and is_exact_int(result.get("failed_count"))
        and result.get("failed_count") == (0 if overlay else 1)
        and result.get("status") == ("Passed" if overlay else "Failed")
        and exact_typed_equal(result.get("independence"), expected_independence)
        and exact_typed_equal(result.get("split_access"), expected_split)
        and result.get("verified_artifacts") == expected_verified_artifacts()
    ):
        raise ValueError(f"Fresh mirror {('B' if overlay else 'A')} verifier contract failed")


def recovery_check_rows(
    mirror_a: dict[str, Any],
    metadata_a: dict[str, Any],
    mirror_b: dict[str, Any],
    metadata_b: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    current_tree = file_tree_digest(resolve_relative(ROUTER_REL))
    current_private = private_artifact_digest()
    return [
        check("recovery.original_failed_lineage", exact_attempt1_failure_bound()),
        check("recovery.public_modes_normalized", all(row["matches_expected"] for row in mode_manifest(True))),
        check("recovery.public_content_unchanged", current_tree == config["public_mode_normalization"]["content_tree_before"]),
        check("recovery.private_artifacts_unchanged", current_private == config["private_invariant"]),
        check("recovery.mirrors_distinct", metadata_a["instance_token_sha256"] != metadata_b["instance_token_sha256"]),
        check("recovery.mirror_a_fresh_clean", all(metadata_a[key] is True for key in ("fresh_project_root", "canonical_layout", "copy_only", "no_symlinks", "no_hardlinks", "cleaned"))),
        check("recovery.mirror_b_fresh_clean", all(metadata_b[key] is True for key in ("fresh_project_root", "canonical_layout", "copy_only", "no_symlinks", "no_hardlinks", "cleaned"))),
        check("recovery.base_verifier_unchanged", artifact(require_expected(CANONICAL_VERIFIER_REL)) == config["implementation"]["base_verifier"]),
        check("recovery.mirror_a_only_config_failed", failed_names(mirror_a) == {"config.router"} and mirror_a.get("passed_count") == 4433),
        check(
            "recovery.overlay_sha_bound_once",
            metadata_b["overlay_load_count"] == 1
            and metadata_b["matching_sha_load_count"] == 2
            and metadata_b["overlay_input_sha256"]
            == EXPECTED_IMMUTABLE[FORMAL_CONFIG_REL][1],
        ),
        check("recovery.mirror_b_all_passed", not failed_names(mirror_b) and mirror_b.get("passed_count") == 4434),
        check("recovery.check_names_same_order", [row["name"] for row in mirror_a["checks"]] == [row["name"] for row in mirror_b["checks"]] == original_check_names()),
        check("recovery.runner_not_imported", True),
    ]


def attempt2_preflight() -> dict[str, Any]:
    """Validate all prerequisites before attempt 2 enters Mirror A."""

    if any(
        os.path.lexists(resolve_relative(relative))
        for relative in (
            ATTEMPT2_VERIFICATION_REL,
            ATTEMPT2_SUMMARY_REL,
            COMPLETION_REL,
            SELECTION_REL,
        )
    ):
        raise FileExistsError("Attempt-2 and downstream governance outputs must be absent")
    amendment_path, amendment_config = load_amendment_config()
    assert_no_runner_import(Path(__file__).resolve())
    assert_no_runner_import(require_expected(CANONICAL_VERIFIER_REL))
    require_canonical_runner_binding()
    before_failure = failure_snapshots()
    before_private = private_artifact_digest()
    before_tree = file_tree_digest(resolve_relative(ROUTER_REL))
    if (
        not exact_attempt1_failure_bound()
        or not all(row["matches_expected"] for row in mode_manifest(after=True))
        or before_tree != amendment_config["public_mode_normalization"]["content_tree_before"]
        or before_private != amendment_config["private_invariant"]
    ):
        raise PermissionError("Final attempt 2 requires the separately completed normalization scope")
    return {
        "amendment_path": amendment_path,
        "amendment_config": amendment_config,
        "before_failure": before_failure,
        "before_private": before_private,
        "before_tree": before_tree,
    }


def build_attempt2_result(preflight: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run both fresh mirrors and construct the strict append-only recovery result."""

    context = attempt2_preflight() if preflight is None else preflight
    amendment_path = Path(context["amendment_path"])
    amendment_config = context["amendment_config"]
    before_failure = context["before_failure"]
    before_private = context["before_private"]
    before_tree = context["before_tree"]

    mirror_a, metadata_a = run_fresh_mirror("mirror_a", overlay=False)
    validate_base_recomputation(mirror_a, overlay=False)
    mirror_b, metadata_b = run_fresh_mirror("mirror_b", overlay=True)
    validate_base_recomputation(mirror_b, overlay=True)
    rows = recovery_check_rows(mirror_a, metadata_a, mirror_b, metadata_b, amendment_config)
    if not all(row["passed"] for row in rows):
        raise RuntimeError("Incident-001 recovery evidence did not fully pass")
    if (
        failure_snapshots() != before_failure
        or private_artifact_digest() != before_private
        or file_tree_digest(resolve_relative(ROUTER_REL)) != before_tree
    ):
        raise RuntimeError("Original artifacts changed during fresh-mirror verification")

    config = load_json(require_expected(FORMAL_CONFIG_REL))
    main_checks = copy.deepcopy(mirror_b["checks"])
    result = {
        "schema_version": "exp-router-formal-verification-attempt-2-v1",
        "experiment_id": EXPERIMENT_ID,
        "rq_id": mirror_b["rq_id"],
        "stage": config["stage"],
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "model_seed": MODEL_SEED,
        "seed_contract": config["seed_contract"],
        "scope": "final",
        "verification_attempt": 2,
        "status": "Passed",
        "runner_imported": False,
        "verified_at_utc": utc_now(),
        "passed_count": 4434,
        "failed_count": 0,
        "checks": main_checks,
        "independence": copy.deepcopy(ATTEMPT2_INDEPENDENCE),
        "verified_artifacts": copy.deepcopy(mirror_b["verified_artifacts"]),
        "split_access": copy.deepcopy(mirror_b["split_access"]),
        "recovery": {
            "schema_version": "exp-router-verification-recovery-evidence-v1",
            "incident_id": "001",
            "classification": "clerical_config_misencoding",
            "amendment_config": artifact(amendment_path),
            "amendment_protocol": artifact(require_record(amendment_config["implementation"]["amendment_protocol"])),
            "original_failed_verification": artifact(require_expected(ORIGINAL_VERIFICATION_REL)),
            "original_failed_summary": artifact(require_expected(ORIGINAL_SUMMARY_REL)),
            "base_verifier": artifact(require_expected(CANONICAL_VERIFIER_REL)),
            "recovery_verifier": artifact(Path(__file__).resolve()),
            "overlay": {
                **copy.deepcopy(amendment_config["clerical_overlay"]),
                "applied_load_count": metadata_b["overlay_load_count"],
            },
            "mode_normalization": {
                "path_count": len(MODE_REPAIRS),
                "content_tree_digest_algorithm": PUBLIC_TREE_DIGEST_ALGORITHM,
                "before": copy.deepcopy(amendment_config["public_mode_normalization"]["pre_manifest"]),
                "after": mode_manifest(after=True),
                "content_tree_before": copy.deepcopy(amendment_config["public_mode_normalization"]["content_tree_before"]),
                "content_tree_after": file_tree_digest(resolve_relative(ROUTER_REL)),
                "private_before": copy.deepcopy(amendment_config["private_invariant"]),
                "private_after": private_artifact_digest(),
            },
            "recomputation": {
                "mirror_a": {
                    "role": "unchanged_config_control",
                    "status": mirror_a["status"],
                    "passed_count": mirror_a["passed_count"],
                    "failed_count": mirror_a["failed_count"],
                    "checks": copy.deepcopy(mirror_a["checks"]),
                    "independence": copy.deepcopy(mirror_a["independence"]),
                    "verified_artifacts": copy.deepcopy(mirror_a["verified_artifacts"]),
                    "split_access": copy.deepcopy(mirror_a["split_access"]),
                    "mirror": metadata_a,
                },
                "mirror_b": {
                    "role": "sha_bound_overlay_recovery",
                    "status": mirror_b["status"],
                    "passed_count": mirror_b["passed_count"],
                    "failed_count": mirror_b["failed_count"],
                    "checks_location": "$.checks",
                    "checks_sha256": canonical_digest(main_checks),
                    "independence": copy.deepcopy(mirror_b["independence"]),
                    "verified_artifacts": copy.deepcopy(mirror_b["verified_artifacts"]),
                    "split_access": copy.deepcopy(mirror_b["split_access"]),
                    "mirror": metadata_b,
                },
                "check_name_order_sha256": canonical_digest([row["name"] for row in main_checks]),
            },
            "recovery_checks": rows,
        },
        "claim_boundary": ATTEMPT2_CLAIM_BOUNDARY,
    }
    validate_attempt2_result(result, verify_artifact_record=False)
    return result


def expected_recovery_check_names() -> list[str]:
    return [
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
    ]


def validate_attempt2_result(value: dict[str, Any], *, verify_artifact_record: bool = True) -> None:
    """Strictly validate the exact Incident-001 Passed recovery schema and live bindings."""

    expected_top = {
        "schema_version", "experiment_id", "rq_id", "stage", "run_id", "attempt_id",
        "model_seed", "seed_contract", "scope", "verification_attempt", "status",
        "runner_imported", "verified_at_utc", "passed_count", "failed_count", "checks",
        "independence", "verified_artifacts", "split_access", "recovery", "claim_boundary",
    }
    checks = value.get("checks", [])
    names = [str(row.get("name")) for row in checks]
    independence = value.get("independence", {})
    recovery = value.get("recovery", {})
    original_failed = load_json(require_expected(ORIGINAL_VERIFICATION_REL))
    formal_config = load_json(require_expected(FORMAL_CONFIG_REL))
    formal_run = load_json(require_expected(RUN_REL))
    require_canonical_runner_binding()
    expected_base_independence = {
        "runner_imported": False,
        "raw_exp058_recomputation": True,
        "nested_thresholds_recomputed": True,
        "scalers_and_routers_refit": True,
        "public_and_private_outputs_recomputed": True,
    }
    expected_split = {
        "accessed_splits": ["train-oof"],
        "validation_accessed": False,
        "test_inputs_accessed": False,
        "test_labels_accessed": False,
        "raw_text_accessed": False,
        "model_loaded_or_forward_run": False,
    }
    expected_recovery_keys = {
        "schema_version", "incident_id", "classification", "amendment_config",
        "amendment_protocol", "original_failed_verification", "original_failed_summary",
        "base_verifier", "recovery_verifier", "overlay", "mode_normalization",
        "recomputation", "recovery_checks",
    }
    if not (
        set(value) == expected_top
        and value.get("schema_version") == "exp-router-formal-verification-attempt-2-v1"
        and value.get("scope") == "final"
        and value.get("verification_attempt") == 2
        and value.get("status") == "Passed"
        and value.get("runner_imported") is False
        and is_canonical_utc_timestamp(value.get("verified_at_utc"))
        and value.get("rq_id")
        == original_failed.get("rq_id")
        == formal_config.get("rq_id")
        == formal_run.get("rq_id")
        == RQ_ID
        and value.get("stage")
        == original_failed.get("stage")
        == formal_config.get("stage")
        == formal_run.get("stage")
        == ROUTER_STAGE
        and value.get("seed_contract")
        == original_failed.get("seed_contract")
        == formal_config.get("seed_contract")
        == formal_run.get("seed_contract")
        and identity_matches(value)
        and is_exact_int(value.get("passed_count"))
        and value.get("passed_count") == 4434
        and is_exact_int(value.get("failed_count"))
        and value.get("failed_count") == 0
        and exact_check_rows(checks, 4434)
        and names == original_check_names()
        and all(row.get("passed") is True for row in checks)
        and exact_typed_equal(independence, ATTEMPT2_INDEPENDENCE)
        and value.get("verified_artifacts") == expected_verified_artifacts()
        and exact_typed_equal(value.get("split_access"), expected_split)
        and set(recovery) == expected_recovery_keys
        and recovery.get("schema_version") == "exp-router-verification-recovery-evidence-v1"
        and recovery.get("incident_id") == "001"
        and recovery.get("classification") == "clerical_config_misencoding"
        and value.get("claim_boundary") == ATTEMPT2_CLAIM_BOUNDARY
        and is_canonical_utc_timestamp(original_failed.get("verified_at_utc"))
        and canonical_utc_datetime(original_failed.get("verified_at_utc"))
        <= canonical_utc_datetime(value.get("verified_at_utc"))
    ):
        raise ValueError("Attempt-2 top-level recovery contract failed")

    amendment_path, amendment = load_amendment_config()
    if not (
        recovery.get("amendment_config") == artifact(amendment_path)
        and recovery.get("amendment_protocol") == artifact(require_record(amendment["implementation"]["amendment_protocol"]))
        and recovery.get("original_failed_verification") == artifact(require_expected(ORIGINAL_VERIFICATION_REL))
        and recovery.get("original_failed_summary") == artifact(require_expected(ORIGINAL_SUMMARY_REL))
        and recovery.get("base_verifier") == artifact(require_expected(CANONICAL_VERIFIER_REL))
        and recovery.get("recovery_verifier") == artifact(Path(__file__).resolve())
        and exact_attempt1_failure_bound()
    ):
        raise ValueError("Attempt-2 recovery artifact lineage failed")

    overlay = recovery.get("overlay", {})
    expected_overlay = {**amendment["clerical_overlay"], "applied_load_count": 1}
    modes = recovery.get("mode_normalization", {})
    recomputation = recovery.get("recomputation", {})
    mirror_a = recomputation.get("mirror_a", {})
    mirror_b = recomputation.get("mirror_b", {})
    recovery_rows = recovery.get("recovery_checks", [])
    expected_mode_keys = {
        "path_count", "content_tree_digest_algorithm", "before", "after",
        "content_tree_before", "content_tree_after", "private_before",
        "private_after",
    }
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
        exact_typed_equal(overlay, expected_overlay)
        and isinstance(modes, dict)
        and set(modes) == expected_mode_keys
        and is_exact_int(modes.get("path_count"))
        and modes.get("path_count") == 16
        and modes.get("content_tree_digest_algorithm") == PUBLIC_TREE_DIGEST_ALGORITHM
        and modes.get("before") == amendment["public_mode_normalization"]["pre_manifest"]
        and modes.get("after") == mode_manifest(after=True)
        and modes.get("content_tree_before") == amendment["public_mode_normalization"]["content_tree_before"]
        and modes.get("content_tree_after") == file_tree_digest(resolve_relative(ROUTER_REL))
        and modes.get("content_tree_before") == modes.get("content_tree_after")
        and modes.get("private_before") == amendment["private_invariant"]
        and modes.get("private_after") == private_artifact_digest()
        and modes.get("private_before") == modes.get("private_after")
        and isinstance(recomputation, dict)
        and set(recomputation) == expected_recomputation_keys
        and isinstance(mirror_a, dict)
        and set(mirror_a) == expected_mirror_a_keys
        and mirror_a.get("role") == "unchanged_config_control"
        and mirror_a.get("status") == "Failed"
        and is_exact_int(mirror_a.get("passed_count"))
        and mirror_a.get("passed_count") == 4433
        and is_exact_int(mirror_a.get("failed_count"))
        and mirror_a.get("failed_count") == 1
        and exact_check_rows(mirror_a.get("checks", []), 4434)
        and [row.get("name") for row in mirror_a.get("checks", [])] == names
        and failed_names(mirror_a) == {"config.router"}
        and mirror_a.get("verified_artifacts") == expected_verified_artifacts()
        and exact_typed_equal(
            mirror_a.get("independence"), expected_base_independence
        )
        and exact_typed_equal(mirror_a.get("split_access"), expected_split)
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
        and mirror_b.get("verified_artifacts") == expected_verified_artifacts()
        and exact_typed_equal(
            mirror_b.get("independence"), expected_base_independence
        )
        and exact_typed_equal(mirror_b.get("split_access"), expected_split)
        and recomputation.get("check_name_order_sha256") == canonical_digest(names)
        and exact_typed_equal(
            recovery_rows,
            [check(name, True) for name in expected_recovery_check_names()],
        )
    ):
        raise ValueError("Attempt-2 A/B recomputation or invariant evidence failed")
    expected_copy_manifest = expected_mirror_copy_manifest()
    expected_copy_count = len(expected_copy_manifest)
    expected_copy_digest = canonical_digest(expected_copy_manifest)
    for mirror in (mirror_a.get("mirror", {}), mirror_b.get("mirror", {})):
        if not (
            isinstance(mirror, dict)
            and set(mirror) == MIRROR_METADATA_KEYS
            and mirror.get("fresh_project_root") is True
            and mirror.get("project_root_mode") == "0o700"
            and mirror.get("canonical_layout") is True
            and mirror.get("copy_only") is True
            and mirror.get("no_symlinks") is True
            and mirror.get("no_hardlinks") is True
            and mirror.get("cleaned") is True
            and is_exact_int(mirror.get("copied_file_count"))
            and mirror.get("copied_file_count") == expected_copy_count
            and mirror.get("copy_manifest_sha256") == expected_copy_digest
            and type(mirror.get("instance_token_sha256")) is str
            and len(mirror.get("instance_token_sha256")) == 64
            and all(
                character in "0123456789abcdef"
                for character in mirror.get("instance_token_sha256")
            )
            and is_exact_int(mirror.get("overlay_load_count"))
            and is_exact_int(mirror.get("matching_sha_load_count"))
        ):
            raise ValueError("Attempt-2 fresh mirror evidence failed")
    if (
        mirror_a["mirror"].get("instance_token_sha256")
        == mirror_b["mirror"].get("instance_token_sha256")
        or mirror_a["mirror"].get("copied_file_count")
        != mirror_b["mirror"].get("copied_file_count")
        or mirror_a["mirror"].get("copy_manifest_sha256")
        != mirror_b["mirror"].get("copy_manifest_sha256")
        or mirror_a.get("independence") != mirror_b.get("independence")
        or mirror_a.get("split_access") != mirror_b.get("split_access")
        or mirror_a["mirror"].get("overlay_enabled") is not False
        or mirror_a["mirror"].get("overlay_load_count") != 0
        or mirror_a["mirror"].get("matching_sha_load_count") != 0
        or mirror_a["mirror"].get("overlay_input_sha256") is not None
        or mirror_b["mirror"].get("overlay_enabled") is not True
        or mirror_b["mirror"].get("overlay_load_count") != 1
        or mirror_b["mirror"].get("matching_sha_load_count") != 2
        or type(mirror_b["mirror"].get("overlay_input_sha256")) is not str
        or mirror_b["mirror"].get("overlay_input_sha256")
        != EXPECTED_IMMUTABLE[FORMAL_CONFIG_REL][1]
    ):
        raise ValueError("Attempt-2 mirror independence binding failed")
    if public_sensitive_paths(value):
        raise ValueError("Attempt-2 public result contains row-level fields")
    if verify_artifact_record:
        path = resolve_relative(ATTEMPT2_VERIFICATION_REL)
        if load_bound_json(path) != value:
            raise ValueError("Attempt-2 result is not the exact canonical artifact")


def validate_failed_attempt2_result(value: dict[str, Any]) -> None:
    """Validate the exact non-sensitive terminal failure schema."""

    expected_top = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "model_seed",
        "scope", "verification_attempt", "status", "runner_imported",
        "verified_at_utc", "passed_count", "failed_count", "checks", "failure",
        "claim_boundary",
    }
    failure = value.get("failure", {})
    stage = failure.get("stage") if isinstance(failure, dict) else None
    code = failure.get("code") if isinstance(failure, dict) else None
    expected_check = check(
        "recovery.attempt2_deterministic_failure",
        False,
        {"stage": stage, "code": code},
    )
    if not (
        set(value) == expected_top
        and value.get("schema_version")
        == "exp-router-formal-verification-attempt-2-failure-v1"
        and value.get("experiment_id") == EXPERIMENT_ID
        and value.get("run_id") == RUN_ID
        and value.get("attempt_id") == ATTEMPT_ID
        and value.get("model_seed") == MODEL_SEED
        and value.get("scope") == "final"
        and value.get("verification_attempt") == 2
        and value.get("status") == "Failed"
        and value.get("runner_imported") is False
        and is_canonical_utc_timestamp(value.get("verified_at_utc"))
        and is_exact_int(value.get("passed_count"))
        and value.get("passed_count") == 0
        and is_exact_int(value.get("failed_count"))
        and value.get("failed_count") == 1
        and exact_check_rows(value.get("checks"), 1)
        and value.get("checks") == [expected_check]
        and isinstance(failure, dict)
        and set(failure) == {"sealed", "stage", "code", "exception_details_recorded"}
        and failure.get("sealed") is True
        and stage in ATTEMPT2_FAILURE_STAGES
        and code in ATTEMPT2_FAILURE_CODES
        and failure.get("exception_details_recorded") is False
        and value.get("claim_boundary")
        == "Terminal Incident-001 attempt-2 failure seal; no scientific conclusion."
        and not public_sensitive_paths(value)
    ):
        raise ValueError("Attempt-2 terminal failure schema drift")


def build_failed_attempt2_result(*, stage: str, code: str) -> dict[str, Any]:
    result = {
        "schema_version": "exp-router-formal-verification-attempt-2-failure-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "model_seed": MODEL_SEED,
        "scope": "final",
        "verification_attempt": 2,
        "status": "Failed",
        "runner_imported": False,
        "verified_at_utc": utc_now(),
        "passed_count": 0,
        "failed_count": 1,
        "checks": [
            check(
                "recovery.attempt2_deterministic_failure",
                False,
                {"stage": stage, "code": code},
            )
        ],
        "failure": {
            "sealed": True,
            "stage": stage,
            "code": code,
            "exception_details_recorded": False,
        },
        "claim_boundary": (
            "Terminal Incident-001 attempt-2 failure seal; no scientific conclusion."
        ),
    }
    validate_failed_attempt2_result(result)
    return result


def render_summary(result: dict[str, Any]) -> str:
    status = result.get("status")
    if status == "Failed":
        validate_failed_attempt2_result(result)
        failure = result["failure"]
        return "\n".join(
            [
                "# EXP-061 / EXP-060 Final Router Verification Attempt 2",
                "",
                "- Status: `Failed`",
                "- Failure sealed: `true`",
                f"- Failure stage: `{failure['stage']}`",
                f"- Failure code: `{failure['code']}`",
                "- Exception details recorded: `false`",
                "- Scientific conclusion: none",
                "",
                result["claim_boundary"],
                "",
            ]
        )
    if status != "Passed":
        raise ValueError("Attempt-2 summary status is not registered")
    return "\n".join(
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
            result["claim_boundary"],
            "",
        ]
    )


def expected_summary_payload(result: dict[str, Any]) -> bytes:
    return (render_summary(result) + "\n").encode("utf-8")


def require_attempt2_summary(result: dict[str, Any]) -> dict[str, Any]:
    path = resolve_relative(ATTEMPT2_SUMMARY_REL)
    expected = expected_summary_payload(result)
    if read_bound_regular_file(path) != expected:
        raise ValueError("Attempt-2 summary path/mode/content drift")
    return {
        "path": display_path(path),
        "bytes": len(expected),
        "sha256": hashlib.sha256(expected).hexdigest(),
    }


def create_once(path: Path, payload: bytes, mode: int = 0o644) -> None:
    if os.path.lexists(path):
        raise FileExistsError(f"Refusing to overwrite append-only artifact: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if os.path.lexists(temporary):
        raise FileExistsError(f"Refusing to reuse temporary path: {temporary}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
            os.fchmod(target.fileno(), mode)
            os.fsync(target.fileno())
        held = os.fstat(descriptor)
        temporary_stat = os.lstat(temporary)
        if not (
            stat.S_ISREG(held.st_mode)
            and stat.S_IMODE(held.st_mode) == mode
            and held.st_nlink == temporary_stat.st_nlink == 1
            and held.st_size == len(payload)
            and (temporary_stat.st_dev, temporary_stat.st_ino)
            == (held.st_dev, held.st_ino)
        ):
            raise RuntimeError("Append-only temporary output identity/mode drift")
        os.link(temporary, path)
        temporary.unlink()
        created = os.lstat(path)
        held_after = os.fstat(descriptor)
        if not (
            stat.S_ISREG(created.st_mode)
            and stat.S_IMODE(created.st_mode) == mode
            and created.st_nlink == held_after.st_nlink == 1
            and created.st_size == held_after.st_size == len(payload)
            and (created.st_dev, created.st_ino)
            == (held_after.st_dev, held_after.st_ino)
        ):
            raise RuntimeError("Append-only output mode/link/inode contract failed")
    finally:
        os.close(descriptor)
        if os.path.lexists(temporary):
            temporary.unlink()


def write_attempt2(result: dict[str, Any]) -> None:
    output = resolve_relative(ATTEMPT2_VERIFICATION_REL)
    summary = resolve_relative(ATTEMPT2_SUMMARY_REL)
    if os.path.lexists(output) or os.path.lexists(summary):
        raise FileExistsError("Attempt-2 verification outputs are append-only")
    json_payload = (json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")
    summary_payload = expected_summary_payload(result)
    create_once(output, json_payload)
    create_once(summary, summary_payload)


def primary_gate_result(selected: dict[str, Any]) -> bool:
    policies = selected.get("policies", {})
    if not isinstance(policies, dict) or set(policies) != set(DEPLOYABLE_POLICY_ORDER):
        raise ValueError("Selected deployable policy inventory drift")
    primary = policies.get("logistic_router", {})
    candidate = primary.get("candidate", {})
    passed = primary.get("passed")
    if not isinstance(passed, bool):
        raise ValueError("Primary gate must be boolean")
    decision = "Pass" if passed else "Fail"
    overall = selected.get("overall", {})
    if not (
        identity_matches(selected)
        and selected.get("schema_version") == "exp-router-selected-operating-point-v2"
        and selected.get("primary_policy") == "logistic_router"
        and float(selected.get("primary_nominal_call_rate", -1)) == 0.15
        and primary.get("evidence_role") == "primary"
        and float(candidate.get("target_call_rate", -1)) == 0.15
        and all(
            policies[policy].get("evidence_role") == "descriptive_only"
            and policies[policy].get("passed") is False
            for policy in ("m1_max_entropy", "m1_threshold_proximity")
        )
        and overall.get("decision") == decision
        and overall.get("selected_policy") == "logistic_router"
        and overall.get("selected_candidate") == candidate
    ):
        raise ValueError("Frozen logistic_router@15% primary result drift")
    return passed


def require_passed_attempt2() -> tuple[Path, dict[str, Any], dict[str, Any]]:
    path = resolve_relative(ATTEMPT2_VERIFICATION_REL)
    value = load_bound_json(path)
    validate_attempt2_result(value)
    summary = require_attempt2_summary(value)
    return path, value, summary


def recovery_lineage(
    verification_path: Path, summary_record: dict[str, Any]
) -> dict[str, Any]:
    amendment_path, amendment = load_amendment_config()
    return {
        "incident_id": "001",
        "original_failed_verification": artifact(require_expected(ORIGINAL_VERIFICATION_REL)),
        "original_failed_summary": artifact(require_expected(ORIGINAL_SUMMARY_REL)),
        "amendment_config": artifact(amendment_path),
        "amendment_protocol": artifact(require_record(amendment["implementation"]["amendment_protocol"])),
        "passed_verification": artifact(verification_path),
        "passed_summary": copy.deepcopy(summary_record),
    }


def complete() -> dict[str, Any]:
    completion_path = resolve_relative(COMPLETION_REL)
    selection_path = resolve_relative(SELECTION_REL)
    if os.path.lexists(completion_path):
        raise FileExistsError("Router completion record is immutable")
    if os.path.lexists(selection_path):
        raise FileExistsError("A final pipeline selection already exists")
    verification_path, verification, summary_record = require_passed_attempt2()
    config_path = require_expected(FORMAL_CONFIG_REL)
    run_path = require_expected(RUN_REL)
    selected_path = require_expected(SELECTED_REL)
    private_path = require_expected(PRIVATE_ROUTER_OOF_REL)
    config = load_json(config_path)
    run = load_json(run_path)
    selected = load_json(selected_path)
    passed = primary_gate_result(selected)
    decision = "Pass" if passed else "Fail"
    if not (
        identity_matches(run)
        and run.get("status") == "CompletedAwaitingVerification"
        and config.get("rq_id") == run.get("rq_id") == RQ_ID
        and config.get("stage") == run.get("stage") == ROUTER_STAGE
        and config.get("seed_contract") == run.get("seed_contract")
        and run.get("decision") == decision
        and run.get("config") == artifact(config_path)
        and run.get("public_outputs", {}).get("selected_operating_point_json") == artifact(selected_path)
        and config.get("seed_contract", {}).get("model_seed") == MODEL_SEED
    ):
        raise ValueError("Formal router run/result identity drift")
    completed_at_utc = utc_now()
    if canonical_utc_datetime(verification.get("verified_at_utc")) > canonical_utc_datetime(
        completed_at_utc
    ):
        raise ValueError("Attempt-2 verification timestamp is after completion")
    completion = {
        "schema_version": "exp-router-completion-v2",
        "experiment_id": EXPERIMENT_ID,
        "stage": config["stage"],
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "model_seed": MODEL_SEED,
        "seed_contract": config["seed_contract"],
        "status": "Complete",
        "completed_at_utc": completed_at_utc,
        "decision": decision,
        "primary_gate_passed": passed,
        "verification_attempt": 2,
        "recovery_lineage": recovery_lineage(verification_path, summary_record),
        "artifacts": {
            "config": artifact(config_path),
            "run": artifact(run_path),
            "selected_operating_point": artifact(selected_path),
            "final_verification": artifact(verification_path),
            "private_router_oof": artifact(private_path),
        },
        "next_gate": COMPLETION_NEXT_GATE,
        "claim_boundary": COMPLETION_CLAIM_BOUNDARY,
    }
    if public_sensitive_paths(completion):
        raise ValueError("Router completion contains row-level public fields")
    create_once(
        completion_path,
        (json.dumps(completion, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8"),
    )
    return completion


def verify_completion() -> dict[str, Any]:
    completion_path = resolve_relative(COMPLETION_REL)
    selection_path = resolve_relative(SELECTION_REL)
    verification_path, verification, summary_record = require_passed_attempt2()
    config_path = require_expected(FORMAL_CONFIG_REL)
    run_path = require_expected(RUN_REL)
    selected_path = require_expected(SELECTED_REL)
    private_path = require_expected(PRIVATE_ROUTER_OOF_REL)
    completion = load_bound_json(completion_path)
    config = load_json(config_path)
    run = load_json(run_path)
    selected = load_json(selected_path)
    passed = primary_gate_result(selected)
    decision = "Pass" if passed else "Fail"
    artifacts = completion.get("artifacts", {})
    expected_completion_keys = {
        "schema_version", "experiment_id", "stage", "run_id", "attempt_id",
        "model_seed", "seed_contract", "status", "completed_at_utc", "decision",
        "primary_gate_passed", "verification_attempt", "recovery_lineage", "artifacts",
        "next_gate", "claim_boundary",
    }
    rows = [
        check("completion.top_level_schema", set(completion) == expected_completion_keys),
        check("completion.identity", identity_matches(completion)),
        check("completion.schema", completion.get("schema_version") == "exp-router-completion-v2"),
        check("completion.stage", completion.get("stage") == config.get("stage")),
        check("completion.seed_contract", completion.get("seed_contract") == config.get("seed_contract")),
        check(
            "completion.completed_at_utc",
            is_canonical_utc_timestamp(completion.get("completed_at_utc")),
        ),
        check(
            "completion.chronology",
            is_canonical_utc_timestamp(verification.get("verified_at_utc"))
            and is_canonical_utc_timestamp(completion.get("completed_at_utc"))
            and canonical_utc_datetime(verification.get("verified_at_utc"))
            <= canonical_utc_datetime(completion.get("completed_at_utc")),
        ),
        check("completion.status", completion.get("status") == "Complete"),
        check("completion.decision", completion.get("decision") == decision),
        check("completion.primary_gate", completion.get("primary_gate_passed") is passed),
        check("completion.verification_attempt", completion.get("verification_attempt") == 2),
        check(
            "completion.recovery_lineage",
            completion.get("recovery_lineage")
            == recovery_lineage(verification_path, summary_record),
        ),
        check("completion.artifact_inventory", set(artifacts) == {"config", "run", "selected_operating_point", "final_verification", "private_router_oof"}),
        check("completion.config", artifacts.get("config") == artifact(config_path)),
        check("completion.run", artifacts.get("run") == artifact(run_path)),
        check("completion.selected", artifacts.get("selected_operating_point") == artifact(selected_path)),
        check("completion.verification", artifacts.get("final_verification") == artifact(verification_path)),
        check("completion.private", artifacts.get("private_router_oof") == artifact(private_path)),
        check("completion.next_gate", completion.get("next_gate") == COMPLETION_NEXT_GATE),
        check(
            "completion.claim_boundary",
            completion.get("claim_boundary") == COMPLETION_CLAIM_BOUNDARY,
        ),
        check(
            "completion.run_binding",
            identity_matches(run)
            and run.get("status") == "CompletedAwaitingVerification"
            and config.get("rq_id") == run.get("rq_id") == RQ_ID
            and config.get("stage") == run.get("stage") == ROUTER_STAGE
            and config.get("seed_contract") == run.get("seed_contract")
            and run.get("decision") == decision
            and run.get("config") == artifact(config_path)
            and run.get("public_outputs", {}).get("selected_operating_point_json")
            == artifact(selected_path),
        ),
        check("completion.final_passed", verification.get("status") == "Passed" and not failed_names(verification)),
        check("completion.selection_absent", not os.path.lexists(selection_path)),
        check("completion.original_failure_preserved", exact_attempt1_failure_bound()),
        check(
            "completion.private_modes",
            all(row["matches_expected"] for row in private_mode_manifest()),
        ),
        check("completion.public_privacy", not public_sensitive_paths(completion)),
    ]
    failures = [row for row in rows if row["passed"] is not True]
    return {
        "schema_version": "exp-router-completion-verification-attempt-2-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "model_seed": MODEL_SEED,
        "scope": "completion",
        "verified_at_utc": utc_now(),
        "status": "Passed" if not failures else "Failed",
        "passed_count": len(rows) - len(failures),
        "failed_count": len(failures),
        "checks": rows,
        "independence": {"runner_not_imported": True, "completion_rehashed": True, "attempt2_revalidated": True},
    }


def run_final() -> dict[str, Any]:
    output = resolve_relative(ATTEMPT2_VERIFICATION_REL)
    summary = resolve_relative(ATTEMPT2_SUMMARY_REL)
    if os.path.lexists(output) or os.path.lexists(summary):
        raise FileExistsError("Attempt-2 verification outputs are append-only")
    preflight = attempt2_preflight()
    try:
        result = build_attempt2_result(preflight)
    except Exception:
        result = build_failed_attempt2_result(
            stage="verification_build",
            code="deterministic_contract_failure",
        )
        write_attempt2(result)
        return result
    write_attempt2(result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("normalize", "final", "complete", "completion"), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.scope == "normalize":
        result = normalize_public_modes()
    elif args.scope == "final":
        result = run_final()
    elif args.scope == "complete":
        result = complete()
    else:
        result = verify_completion()
    print(json.dumps(result, indent=2 if args.scope == "normalize" else None, sort_keys=True))
    if result.get("status") not in {"Passed", "Complete"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
