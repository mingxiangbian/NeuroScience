#!/usr/bin/env python3
"""Incident-002 recovery verifier for EXP-061 router verification attempt 3.

This verifier never imports the analysis runner and never mutates the frozen
Attempt-1/Attempt-2 artifacts.  Its only recovery behavior change from the
Incident-001 wrapper is canonicalizing each disposable mirror root before the
unchanged base verifier is called.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any

import verify_exp060_router_attempt2 as incident1


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]

EXPERIMENT_ID = incident1.EXPERIMENT_ID
RUN_ID = incident1.RUN_ID
ATTEMPT_ID = incident1.ATTEMPT_ID
MODEL_SEED = incident1.MODEL_SEED
RQ_ID = incident1.RQ_ID
ROUTER_STAGE = incident1.ROUTER_STAGE
RECOVERY_PYTHON = incident1.RECOVERY_PYTHON

BASE = incident1.BASE
ROUTER_REL = incident1.ROUTER_REL
FORMAL_CONFIG_REL = incident1.FORMAL_CONFIG_REL
RUN_REL = incident1.RUN_REL
SELECTED_REL = incident1.SELECTED_REL
PAIRED_OOF_REL = incident1.PAIRED_OOF_REL
PRIVATE_ROUTER_OOF_REL = incident1.PRIVATE_ROUTER_OOF_REL
ORIGINAL_VERIFICATION_REL = incident1.ORIGINAL_VERIFICATION_REL
ORIGINAL_SUMMARY_REL = incident1.ORIGINAL_SUMMARY_REL
ATTEMPT2_VERIFICATION_REL = incident1.ATTEMPT2_VERIFICATION_REL
ATTEMPT2_SUMMARY_REL = incident1.ATTEMPT2_SUMMARY_REL
ATTEMPT3_VERIFICATION_REL = ROUTER_REL / "verification-attempt-3.json"
ATTEMPT3_SUMMARY_REL = ROUTER_REL / "VERIFICATION-SUMMARY-ATTEMPT-3.md"
COMPLETION_REL = incident1.COMPLETION_REL
SELECTION_REL = incident1.SELECTION_REL

INCIDENT1_PROTOCOL_REL = incident1.AMENDMENT_REL
INCIDENT1_CONFIG_REL = incident1.AMENDMENT_CONFIG_REL
INCIDENT1_VERIFIER_REL = BASE / "verify_exp060_router_attempt2.py"
INCIDENT1_TESTS_REL = incident1.RECOVERY_TESTS_REL
INCIDENT1_FINALIZER_REL = incident1.FINALIZER_REL
INCIDENT1_FINALIZER_TESTS_REL = incident1.FINALIZER_TESTS_REL

INCIDENT2_PROTOCOL_REL = Path(
    "experiments/stack-overflow-emotion-gold/protocols/"
    "exp-061-exp060-final-verification-attempt-3-incident-002-amendment.md"
)
INCIDENT2_CONFIG_REL = BASE / (
    "configs/exp-061-seed-43-router-replication-router-"
    "verification-attempt-3-incident-002.json"
)
INCIDENT2_VERIFIER_REL = BASE / "verify_exp060_router_attempt3.py"
INCIDENT2_TESTS_REL = BASE / "tests/test_exp060_router_attempt3.py"
INCIDENT2_FINALIZER_REL = BASE / "finalize_router_replication_attempt3.py"
INCIDENT2_FINALIZER_TESTS_REL = BASE / "tests/test_finalize_router_attempt3.py"

FULL_POLICY_ORDER = incident1.FULL_POLICY_ORDER
DEPLOYABLE_POLICY_ORDER = incident1.DEPLOYABLE_POLICY_ORDER
PUBLIC_SENSITIVE_KEYS = frozenset(incident1.PUBLIC_SENSITIVE_KEYS)
ATTEMPT3_INDEPENDENCE = copy.deepcopy(incident1.ATTEMPT2_INDEPENDENCE)
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
TREE_EXCLUSIONS = {
    Path("verification-attempt-2.json"),
    Path("VERIFICATION-SUMMARY-ATTEMPT-2.md"),
    Path("verification-attempt-3.json"),
    Path("VERIFICATION-SUMMARY-ATTEMPT-3.md"),
    Path("router-complete.json"),
}
PUBLIC_TREE_DIGEST_ALGORITHM = (
    "sha256(canonical-json(sorted(relative_path,bytes,sha256))); exclude exact "
    "router-root-relative Attempt-2 JSON/summary, Attempt-3 JSON/summary, and "
    "router-complete.json paths"
)
ATTEMPT3_RECOVERY_CHECK_NAMES = (
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


def resolve_relative(value: Path | str) -> Path:
    return incident1.resolve_relative(value)


def display_path(path: Path) -> str:
    return incident1.display_path(path)


def sha256(path: Path) -> str:
    return incident1.sha256(path)


def artifact(path: Path) -> dict[str, Any]:
    return incident1.artifact(path)


def canonical_digest(value: Any) -> str:
    return incident1.canonical_digest(value)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_canonical_utc_timestamp(value: Any) -> bool:
    return incident1.is_canonical_utc_timestamp(value)


def canonical_utc_datetime(value: Any) -> datetime:
    return incident1.canonical_utc_datetime(value)


def check(name: str, passed: bool, detail: Any = None) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def exact_artifact_record(record: Any, relative: Path) -> bool:
    if not isinstance(record, dict):
        return False
    try:
        return incident1.require_record(record) == resolve_relative(relative)
    except (FileNotFoundError, OSError, TypeError, ValueError):
        return False


def read_bound_json(path: Path) -> dict[str, Any]:
    return incident1.load_bound_json(path)


def public_tree_digest() -> dict[str, Any]:
    root = resolve_relative(ROUTER_REL)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Router public root is missing or symbolic")
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Router public tree contains a symlink: {path}")
        relative = path.relative_to(root)
        if path.is_file() and relative not in TREE_EXCLUSIONS:
            rows.append(
                {
                    "path": str(relative),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    return {"file_count": len(rows), "sha256": canonical_digest(rows)}


def incident1_lineage_records() -> dict[str, Any]:
    config_path, config = incident1.load_amendment_config()
    return {
        "amendment_config": artifact(config_path),
        "amendment_protocol": copy.deepcopy(config["implementation"]["amendment_protocol"]),
        "recovery_verifier": copy.deepcopy(config["implementation"]["recovery_verifier"]),
        "recovery_tests": copy.deepcopy(config["implementation"]["recovery_tests"]),
        "finalizer": copy.deepcopy(config["implementation"]["finalizer"]),
        "finalizer_tests": copy.deepcopy(config["implementation"]["finalizer_tests"]),
    }


def attempt1_lineage_records() -> dict[str, Any]:
    require_attempt1_failure()
    return {
        "verification": artifact(incident1.require_expected(ORIGINAL_VERIFICATION_REL)),
        "summary": artifact(incident1.require_expected(ORIGINAL_SUMMARY_REL)),
    }


def require_attempt1_failure() -> dict[str, Any]:
    verification_path = incident1.require_expected(ORIGINAL_VERIFICATION_REL)
    summary_path = incident1.require_expected(ORIGINAL_SUMMARY_REL)
    verification = incident1.load_bound_json(verification_path, expected_mode=0o600)
    incident1.read_bound_regular_file(summary_path, expected_mode=0o600)
    if not incident1.exact_attempt1_failure_bound():
        raise ValueError("Attempt-1 Failed lineage drift")
    return verification


def require_attempt2_failure() -> tuple[dict[str, Any], dict[str, Any]]:
    verification_path = resolve_relative(ATTEMPT2_VERIFICATION_REL)
    summary_path = resolve_relative(ATTEMPT2_SUMMARY_REL)
    verification = read_bound_json(verification_path)
    incident1.validate_failed_attempt2_result(verification)
    summary_payload = incident1.read_bound_regular_file(summary_path)
    if summary_payload != incident1.expected_summary_payload(verification):
        raise ValueError("Attempt-2 terminal summary content drift")
    return verification, {
        "verification": artifact(verification_path),
        "summary": artifact(summary_path),
    }


def attempt2_lineage_records() -> dict[str, Any]:
    _value, records = require_attempt2_failure()
    return records


def expected_incident2_implementation_paths() -> dict[str, Path]:
    return {
        "amendment_protocol": INCIDENT2_PROTOCOL_REL,
        "base_verifier": incident1.CANONICAL_VERIFIER_REL,
        "recovery_verifier": INCIDENT2_VERIFIER_REL,
        "recovery_tests": INCIDENT2_TESTS_REL,
        "finalizer": INCIDENT2_FINALIZER_REL,
        "finalizer_tests": INCIDENT2_FINALIZER_TESTS_REL,
    }


def load_incident2_config() -> tuple[Path, dict[str, Any]]:
    path = resolve_relative(INCIDENT2_CONFIG_REL)
    config = incident1.load_json(path)
    expected_keys = {
        "schema_version",
        "experiment_id",
        "run_id",
        "attempt_id",
        "model_seed",
        "incident_id",
        "predecessor_incident_id",
        "authorization",
        "implementation",
        "lineage",
        "target",
        "clerical_overlay",
        "public_state",
        "private_invariant",
        "outputs",
        "commands",
        "failure_policy",
        "resource_contract",
    }
    if not (
        set(config) == expected_keys
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
        raise ValueError("Unexpected Incident-002 config identity/schema")

    authorization = {
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
    if not incident1.exact_typed_equal(config.get("authorization"), authorization):
        raise PermissionError("Incident-002 authorization drift")

    expected_outputs = {
        "verification": str(ATTEMPT3_VERIFICATION_REL),
        "summary": str(ATTEMPT3_SUMMARY_REL),
        "completion": str(COMPLETION_REL),
        "selection": str(SELECTION_REL),
    }
    if not incident1.exact_typed_equal(config.get("outputs"), expected_outputs):
        raise ValueError("Incident-002 output namespace drift")

    implementation = config.get("implementation", {})
    paths = expected_incident2_implementation_paths()
    if set(implementation) != set(paths):
        raise ValueError("Incident-002 implementation inventory drift")
    for name, relative in paths.items():
        if not exact_artifact_record(implementation[name], relative):
            raise ValueError(f"Incident-002 implementation drift: {name}")

    lineage = config.get("lineage", {})
    if not (
        isinstance(lineage, dict)
        and set(lineage) == {"incident_001", "attempt_1", "attempt_2"}
        and incident1.exact_typed_equal(lineage.get("incident_001"), incident1_lineage_records())
        and incident1.exact_typed_equal(lineage.get("attempt_1"), attempt1_lineage_records())
        and incident1.exact_typed_equal(lineage.get("attempt_2"), attempt2_lineage_records())
    ):
        raise ValueError("Incident-002 predecessor lineage drift")

    expected_targets = {
        "formal_config": FORMAL_CONFIG_REL,
        "run": RUN_REL,
        "selected_operating_point": SELECTED_REL,
        "paired_oof": PAIRED_OOF_REL,
        "private_router_oof": PRIVATE_ROUTER_OOF_REL,
    }
    target = config.get("target", {})
    if set(target) != set(expected_targets):
        raise ValueError("Incident-002 target inventory drift")
    for name, relative in expected_targets.items():
        if not exact_artifact_record(target[name], relative):
            raise ValueError(f"Incident-002 target drift: {name}")

    _incident1_path, incident1_config = incident1.load_amendment_config()
    if not incident1.exact_typed_equal(
        config.get("clerical_overlay"), incident1_config["clerical_overlay"]
    ):
        raise ValueError("Incident-002 changed the Incident-001 overlay")
    expected_public = {
        "path_count": len(incident1.MODE_REPAIRS),
        "normalized_manifest": incident1.mode_manifest(after=True),
        "content_tree_digest_algorithm": PUBLIC_TREE_DIGEST_ALGORITHM,
        "content_tree": incident1_config["public_mode_normalization"]["content_tree_before"],
    }
    if not incident1.exact_typed_equal(config.get("public_state"), expected_public):
        raise ValueError("Incident-002 normalized public state drift")
    if not incident1.exact_typed_equal(
        config.get("private_invariant"), incident1_config["private_invariant"]
    ):
        raise ValueError("Incident-002 private invariant drift")
    expected_commands = {
        scope: f"{RECOVERY_PYTHON} {BASE}/verify_exp060_router_attempt3.py --scope {scope}"
        for scope in ("final", "complete", "completion")
    }
    if not incident1.exact_typed_equal(config.get("commands"), expected_commands):
        raise ValueError("Incident-002 command contract drift")
    if not incident1.exact_typed_equal(config.get("failure_policy"), {
        "append_only": True,
        "failed_attempt_terminal": True,
        "json_written_before_summary": True,
        "exception_details_recorded": False,
        "retry_same_path": False,
    }):
        raise ValueError("Incident-002 failure policy drift")
    formal_resources = incident1.load_json(
        incident1.require_expected(FORMAL_CONFIG_REL)
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
    if not incident1.exact_typed_equal(
        config.get("resource_contract"), expected_resources
    ):
        raise ValueError("Incident-002 resource contract drift")
    return path, config


def attempt3_preflight() -> dict[str, Any]:
    for relative in (
        ATTEMPT3_VERIFICATION_REL,
        ATTEMPT3_SUMMARY_REL,
        COMPLETION_REL,
        SELECTION_REL,
    ):
        if os.path.lexists(resolve_relative(relative)):
            raise FileExistsError(f"Attempt-3/downstream output already exists: {relative}")
    config_path, config = load_incident2_config()
    incident1.assert_no_runner_import(Path(__file__).resolve())
    incident1.assert_no_runner_import(incident1.require_expected(incident1.CANONICAL_VERIFIER_REL))
    incident1.require_canonical_runner_binding()
    attempt2, attempt2_records = require_attempt2_failure()
    mode_rows = incident1.mode_manifest(after=True)
    tree = public_tree_digest()
    private = incident1.private_artifact_digest()
    if not (
        incident1.exact_attempt1_failure_bound()
        and all(row["matches_expected"] for row in mode_rows)
        and tree == config["public_state"]["content_tree"]
        and private == config["private_invariant"]
    ):
        raise ValueError("Incident-002 immutable preflight state drift")
    return {
        "config_path": config_path,
        "config": config,
        "attempt1": attempt1_lineage_records(),
        "attempt2": attempt2,
        "attempt2_records": attempt2_records,
        "tree": tree,
        "private": private,
        "modes": mode_rows,
    }


def canonical_mirror_config_path(module: Any) -> Path:
    """Return the config under the verifier's resolved canonical project root."""

    path = module.PROJECT_ROOT / FORMAL_CONFIG_REL
    if path.parent != module.SCRIPT_DIR / "configs":
        raise ValueError("Mirror config is not under the loaded verifier's canonical configs dir")
    return path


def run_fresh_mirror(label: str, overlay: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the frozen verifier in one disposable canonical mirror."""

    metadata: dict[str, Any] = {}
    temporary_path: Path | None = None
    with tempfile.TemporaryDirectory(prefix=f"exp061-incident002-{label}-") as temporary:
        project_root = Path(temporary)
        temporary_path = project_root
        os.chmod(project_root, 0o700)
        instance_token = hashlib.sha256(os.urandom(32)).hexdigest()
        source_relatives = incident1.mirror_source_relatives()
        forbidden = {
            ORIGINAL_VERIFICATION_REL,
            ORIGINAL_SUMMARY_REL,
            ATTEMPT2_VERIFICATION_REL,
            ATTEMPT2_SUMMARY_REL,
            ATTEMPT3_VERIFICATION_REL,
            ATTEMPT3_SUMMARY_REL,
            COMPLETION_REL,
            SELECTION_REL,
        }
        if set(source_relatives) & forbidden:
            raise ValueError("Fresh mirror source inventory includes governance sidecars")
        expected_manifest = incident1.expected_mirror_copy_manifest()
        manifest = [
            incident1.copy_regular_file(
                incident1.resolve_relative(relative), project_root / relative
            )
            for relative in source_relatives
        ]
        if manifest != expected_manifest:
            raise RuntimeError("Fresh mirror source-copy manifest drift")
        incident1.set_mirror_output_modes(project_root)
        module = incident1.load_mirror_verifier(project_root, label)
        if module.PROJECT_ROOT.resolve() != project_root.resolve():
            raise ValueError("Loaded verifier project root is not the resolved mirror root")
        proxy: incident1.JsonOverlayProxy | None = None
        if overlay:
            proxy = incident1.JsonOverlayProxy(
                module.json,
                incident1.EXPECTED_IMMUTABLE[FORMAL_CONFIG_REL][1],
            )
            module.json = proxy
        result = module.verify(canonical_mirror_config_path(module))
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


def validate_mirror_metadata(value: Any, *, overlay: bool) -> None:
    expected_manifest = incident1.expected_mirror_copy_manifest()
    if not isinstance(value, dict) or set(value) != incident1.MIRROR_METADATA_KEYS:
        raise ValueError("Attempt-3 mirror metadata inventory drift")
    booleans = (
        "fresh_project_root",
        "canonical_layout",
        "copy_only",
        "no_symlinks",
        "no_hardlinks",
        "cleaned",
    )
    if not all(value.get(name) is True for name in booleans):
        raise ValueError("Attempt-3 mirror freshness evidence drift")
    if not (
        value.get("project_root_mode") == "0o700"
        and type(value.get("copied_file_count")) is int
        and value.get("copied_file_count") == len(expected_manifest) == 30
        and value.get("copy_manifest_sha256") == canonical_digest(expected_manifest)
        and type(value.get("instance_token_sha256")) is str
        and incident1.SHA256_RE.fullmatch(value["instance_token_sha256"])
        and value.get("overlay_enabled") is overlay
        and type(value.get("overlay_load_count")) is int
        and type(value.get("matching_sha_load_count")) is int
    ):
        raise ValueError("Attempt-3 mirror identity/manifest drift")
    if overlay:
        valid_overlay = (
            value.get("overlay_load_count") == 1
            and value.get("matching_sha_load_count") == 2
            and value.get("overlay_input_sha256")
            == incident1.EXPECTED_IMMUTABLE[FORMAL_CONFIG_REL][1]
        )
    else:
        valid_overlay = (
            value.get("overlay_load_count") == 0
            and value.get("matching_sha_load_count") == 0
            and value.get("overlay_input_sha256") is None
        )
    if not valid_overlay:
        raise ValueError("Attempt-3 mirror overlay evidence drift")


def recovery_rows(
    mirror_a: dict[str, Any],
    metadata_a: dict[str, Any],
    mirror_b: dict[str, Any],
    metadata_b: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        check("recovery.attempt1_failed_lineage", incident1.exact_attempt1_failure_bound()),
        check("recovery.attempt2_failed_lineage", attempt2_lineage_records() == config["lineage"]["attempt_2"]),
        check("recovery.incident1_frozen", incident1_lineage_records() == config["lineage"]["incident_001"]),
        check("recovery.public_modes_normalized", all(row["matches_expected"] for row in incident1.mode_manifest(after=True))),
        check("recovery.public_content_unchanged", public_tree_digest() == config["public_state"]["content_tree"]),
        check("recovery.private_artifacts_unchanged", incident1.private_artifact_digest() == config["private_invariant"]),
        check("recovery.canonical_mirror_paths", True),
        check("recovery.mirrors_distinct", metadata_a["instance_token_sha256"] != metadata_b["instance_token_sha256"]),
        check("recovery.mirror_a_fresh_clean", all(metadata_a[name] is True for name in ("fresh_project_root", "canonical_layout", "copy_only", "no_symlinks", "no_hardlinks", "cleaned"))),
        check("recovery.mirror_b_fresh_clean", all(metadata_b[name] is True for name in ("fresh_project_root", "canonical_layout", "copy_only", "no_symlinks", "no_hardlinks", "cleaned"))),
        check("recovery.base_verifier_unchanged", artifact(incident1.require_expected(incident1.CANONICAL_VERIFIER_REL)) == config["implementation"]["base_verifier"]),
        check("recovery.mirror_a_only_config_failed", incident1.failed_names(mirror_a) == {"config.router"} and mirror_a.get("passed_count") == 4433),
        check("recovery.overlay_sha_bound_once", metadata_b["overlay_load_count"] == 1 and metadata_b["matching_sha_load_count"] == 2),
        check("recovery.mirror_b_all_passed", not incident1.failed_names(mirror_b) and mirror_b.get("passed_count") == 4434),
        check("recovery.check_names_same_order", [row["name"] for row in mirror_a["checks"]] == [row["name"] for row in mirror_b["checks"]] == incident1.original_check_names()),
        check("recovery.runner_not_imported", True),
    ]


def build_attempt3_result(preflight: dict[str, Any] | None = None) -> dict[str, Any]:
    context = attempt3_preflight() if preflight is None else preflight
    config_path = Path(context["config_path"])
    config = context["config"]
    before_attempt1 = copy.deepcopy(context["attempt1"])
    before_attempt2 = copy.deepcopy(context["attempt2_records"])
    before_tree = copy.deepcopy(context["tree"])
    before_private = copy.deepcopy(context["private"])

    mirror_a, metadata_a = run_fresh_mirror("mirror_a", overlay=False)
    incident1.validate_base_recomputation(mirror_a, overlay=False)
    mirror_b, metadata_b = run_fresh_mirror("mirror_b", overlay=True)
    incident1.validate_base_recomputation(mirror_b, overlay=True)
    validate_mirror_metadata(metadata_a, overlay=False)
    validate_mirror_metadata(metadata_b, overlay=True)
    rows = recovery_rows(mirror_a, metadata_a, mirror_b, metadata_b, config)
    if [row["name"] for row in rows] != list(ATTEMPT3_RECOVERY_CHECK_NAMES) or not all(
        row["passed"] is True for row in rows
    ):
        raise RuntimeError("Incident-002 recovery evidence did not fully pass")
    if not (
        attempt1_lineage_records() == before_attempt1
        and attempt2_lineage_records() == before_attempt2
        and public_tree_digest() == before_tree
        and incident1.private_artifact_digest() == before_private
    ):
        raise RuntimeError("Frozen artifacts changed during Attempt-3 mirrors")

    formal_config = incident1.load_json(incident1.require_expected(FORMAL_CONFIG_REL))
    main_checks = copy.deepcopy(mirror_b["checks"])
    result = {
        "schema_version": "exp-router-formal-verification-attempt-3-v1",
        "experiment_id": EXPERIMENT_ID,
        "rq_id": RQ_ID,
        "stage": ROUTER_STAGE,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "model_seed": MODEL_SEED,
        "seed_contract": formal_config["seed_contract"],
        "scope": "final",
        "verification_attempt": 3,
        "status": "Passed",
        "runner_imported": False,
        "verified_at_utc": utc_now(),
        "passed_count": 4434,
        "failed_count": 0,
        "checks": main_checks,
        "independence": copy.deepcopy(ATTEMPT3_INDEPENDENCE),
        "verified_artifacts": copy.deepcopy(mirror_b["verified_artifacts"]),
        "split_access": copy.deepcopy(mirror_b["split_access"]),
        "recovery": {
            "schema_version": "exp-router-verification-recovery-attempt-3-v1",
            "incident_id": "002",
            "predecessor_incident_id": "001",
            "classification": "fresh_mirror_path_canonicalization",
            "amendment_config": artifact(config_path),
            "amendment_protocol": copy.deepcopy(config["implementation"]["amendment_protocol"]),
            "incident_001": copy.deepcopy(config["lineage"]["incident_001"]),
            "attempt_1_failed": copy.deepcopy(config["lineage"]["attempt_1"]),
            "attempt_2_failed": copy.deepcopy(config["lineage"]["attempt_2"]),
            "base_verifier": copy.deepcopy(config["implementation"]["base_verifier"]),
            "recovery_verifier": copy.deepcopy(config["implementation"]["recovery_verifier"]),
            "path_canonicalization": {
                "loaded_verifier_project_root_used": True,
                "config_argument": "module.PROJECT_ROOT / FORMAL_CONFIG_REL",
                "semantic_change_count": 1,
            },
            "overlay": {
                **copy.deepcopy(config["clerical_overlay"]),
                "applied_load_count": metadata_b["overlay_load_count"],
            },
            "public_state": {
                **copy.deepcopy(config["public_state"]),
                "observed_content_tree": public_tree_digest(),
            },
            "private_state": {
                "before": before_private,
                "after": incident1.private_artifact_digest(),
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
                "check_name_order_sha256": canonical_digest(
                    [row["name"] for row in main_checks]
                ),
            },
            "recovery_checks": rows,
        },
        "claim_boundary": ATTEMPT3_CLAIM_BOUNDARY,
    }
    validate_attempt3_result(result, verify_live_artifacts=False)
    return result


def validate_attempt3_result(
    value: dict[str, Any], *, verify_live_artifacts: bool = True
) -> None:
    expected_top = {
        "schema_version", "experiment_id", "rq_id", "stage", "run_id",
        "attempt_id", "model_seed", "seed_contract", "scope",
        "verification_attempt", "status", "runner_imported", "verified_at_utc",
        "passed_count", "failed_count", "checks", "independence",
        "verified_artifacts", "split_access", "recovery", "claim_boundary",
    }
    formal_config = incident1.load_json(incident1.require_expected(FORMAL_CONFIG_REL))
    original = require_attempt1_failure()
    attempt2, attempt2_records = require_attempt2_failure()
    recovery = value.get("recovery", {})
    checks = value.get("checks", [])
    if not (
        set(value) == expected_top
        and value.get("schema_version") == "exp-router-formal-verification-attempt-3-v1"
        and value.get("experiment_id") == EXPERIMENT_ID
        and value.get("rq_id") == original.get("rq_id") == RQ_ID
        and value.get("stage") == original.get("stage") == ROUTER_STAGE
        and value.get("run_id") == RUN_ID
        and value.get("attempt_id") == ATTEMPT_ID
        and type(value.get("model_seed")) is int
        and value.get("model_seed") == MODEL_SEED
        and incident1.exact_typed_equal(
            value.get("seed_contract"), formal_config.get("seed_contract")
        )
        and value.get("scope") == "final"
        and type(value.get("verification_attempt")) is int
        and value.get("verification_attempt") == 3
        and value.get("status") == "Passed"
        and value.get("runner_imported") is False
        and is_canonical_utc_timestamp(value.get("verified_at_utc"))
        and canonical_utc_datetime(original["verified_at_utc"])
        <= canonical_utc_datetime(attempt2["verified_at_utc"])
        <= canonical_utc_datetime(value["verified_at_utc"])
        and type(value.get("passed_count")) is int
        and value.get("passed_count") == 4434
        and type(value.get("failed_count")) is int
        and value.get("failed_count") == 0
        and incident1.exact_check_rows(checks, 4434)
        and [row["name"] for row in checks] == incident1.original_check_names()
        and all(row["passed"] is True for row in checks)
        and incident1.exact_typed_equal(value.get("independence"), ATTEMPT3_INDEPENDENCE)
        and incident1.exact_typed_equal(
            value.get("verified_artifacts"), incident1.expected_verified_artifacts()
        )
        and incident1.exact_typed_equal(value.get("split_access"), {
            "accessed_splits": ["train-oof"],
            "validation_accessed": False,
            "test_inputs_accessed": False,
            "test_labels_accessed": False,
            "raw_text_accessed": False,
            "model_loaded_or_forward_run": False,
        })
        and value.get("claim_boundary") == ATTEMPT3_CLAIM_BOUNDARY
        and not incident1.public_sensitive_paths(value)
    ):
        raise ValueError("Attempt-3 Passed top-level contract drift")
    expected_recovery_keys = {
        "schema_version", "incident_id", "predecessor_incident_id",
        "classification", "amendment_config", "amendment_protocol",
        "incident_001", "attempt_1_failed", "attempt_2_failed", "base_verifier",
        "recovery_verifier", "path_canonicalization", "overlay", "public_state",
        "private_state", "recomputation", "recovery_checks",
    }
    if not (
        isinstance(recovery, dict)
        and set(recovery) == expected_recovery_keys
        and recovery.get("schema_version")
        == "exp-router-verification-recovery-attempt-3-v1"
        and recovery.get("incident_id") == "002"
        and recovery.get("predecessor_incident_id") == "001"
        and recovery.get("classification") == "fresh_mirror_path_canonicalization"
        and incident1.exact_typed_equal(
            recovery.get("incident_001"), incident1_lineage_records()
        )
        and incident1.exact_typed_equal(
            recovery.get("attempt_1_failed"), attempt1_lineage_records()
        )
        and incident1.exact_typed_equal(
            recovery.get("attempt_2_failed"), attempt2_records
        )
        and incident1.exact_typed_equal(
            recovery.get("path_canonicalization"),
            {
                "loaded_verifier_project_root_used": True,
                "config_argument": "module.PROJECT_ROOT / FORMAL_CONFIG_REL",
                "semantic_change_count": 1,
            },
        )
    ):
        raise ValueError("Attempt-3 recovery lineage/path contract drift")
    config_path, config = load_incident2_config()
    if not (
        incident1.exact_typed_equal(
            recovery.get("amendment_config"), artifact(config_path)
        )
        and incident1.exact_typed_equal(
            recovery.get("amendment_protocol"),
            config["implementation"]["amendment_protocol"],
        )
        and incident1.exact_typed_equal(
            recovery.get("base_verifier"), config["implementation"]["base_verifier"]
        )
        and incident1.exact_typed_equal(
            recovery.get("recovery_verifier"),
            config["implementation"]["recovery_verifier"],
        )
        and incident1.exact_typed_equal(
            recovery.get("overlay"),
            {**config["clerical_overlay"], "applied_load_count": 1},
        )
        and incident1.exact_typed_equal(
            recovery.get("public_state"),
            {
                **config["public_state"],
                "observed_content_tree": config["public_state"]["content_tree"],
            },
        )
        and incident1.exact_typed_equal(
            recovery.get("private_state"),
            {
                "before": config["private_invariant"],
                "after": config["private_invariant"],
            },
        )
    ):
        raise ValueError("Attempt-3 immutable state evidence drift")
    recomputation = recovery.get("recomputation", {})
    if not isinstance(recomputation, dict) or set(recomputation) != {
        "mirror_a", "mirror_b", "check_name_order_sha256"
    }:
        raise ValueError("Attempt-3 recomputation inventory drift")
    mirror_a = recomputation.get("mirror_a", {})
    mirror_b = recomputation.get("mirror_b", {})
    expected_a_keys = {
        "role", "status", "passed_count", "failed_count", "checks",
        "independence", "verified_artifacts", "split_access", "mirror",
    }
    expected_b_keys = {
        "role", "status", "passed_count", "failed_count", "checks_location",
        "checks_sha256", "independence", "verified_artifacts", "split_access", "mirror",
    }
    if not (
        isinstance(mirror_a, dict)
        and set(mirror_a) == expected_a_keys
        and isinstance(mirror_b, dict)
        and set(mirror_b) == expected_b_keys
        and mirror_a.get("role") == "unchanged_config_control"
        and mirror_b.get("role") == "sha_bound_overlay_recovery"
        and mirror_b.get("checks_location") == "$.checks"
        and mirror_b.get("checks_sha256") == canonical_digest(checks)
        and recomputation.get("check_name_order_sha256")
        == canonical_digest([row["name"] for row in checks])
    ):
        raise ValueError("Attempt-3 A/B recomputation schema drift")
    synthetic_a = {
        "schema_version": "exp-router-formal-verification-v2",
        "scope": "final",
        "rq_id": RQ_ID,
        "stage": ROUTER_STAGE,
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "model_seed": MODEL_SEED,
        **{name: copy.deepcopy(mirror_a[name]) for name in (
            "status", "passed_count", "failed_count", "checks", "independence",
            "verified_artifacts", "split_access",
        )},
    }
    synthetic_b = {
        "schema_version": "exp-router-formal-verification-v2",
        "scope": "final",
        "rq_id": RQ_ID,
        "stage": ROUTER_STAGE,
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "model_seed": MODEL_SEED,
        "status": mirror_b.get("status"),
        "passed_count": mirror_b.get("passed_count"),
        "failed_count": mirror_b.get("failed_count"),
        "checks": copy.deepcopy(checks),
        "independence": copy.deepcopy(mirror_b.get("independence")),
        "verified_artifacts": copy.deepcopy(mirror_b.get("verified_artifacts")),
        "split_access": copy.deepcopy(mirror_b.get("split_access")),
    }
    incident1.validate_base_recomputation(synthetic_a, overlay=False)
    incident1.validate_base_recomputation(synthetic_b, overlay=True)
    validate_mirror_metadata(mirror_a.get("mirror"), overlay=False)
    validate_mirror_metadata(mirror_b.get("mirror"), overlay=True)
    if mirror_a["mirror"]["instance_token_sha256"] == mirror_b["mirror"]["instance_token_sha256"]:
        raise ValueError("Attempt-3 mirror instance tokens are not distinct")
    recovery_checks = recovery.get("recovery_checks")
    if not (
        incident1.exact_check_rows(recovery_checks, len(ATTEMPT3_RECOVERY_CHECK_NAMES))
        and [row["name"] for row in recovery_checks]
        == list(ATTEMPT3_RECOVERY_CHECK_NAMES)
        and all(row["passed"] is True and row["detail"] is None for row in recovery_checks)
    ):
        raise ValueError("Attempt-3 recovery checks drift")
    if verify_live_artifacts and not (
        public_tree_digest() == config["public_state"]["content_tree"]
        and incident1.private_artifact_digest() == config["private_invariant"]
        and all(row["matches_expected"] for row in incident1.mode_manifest(after=True))
    ):
        raise ValueError("Attempt-3 live artifact state drift")


def build_failed_attempt3_result() -> dict[str, Any]:
    result = {
        "schema_version": "exp-router-formal-verification-attempt-3-failure-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "model_seed": MODEL_SEED,
        "scope": "final",
        "verification_attempt": 3,
        "status": "Failed",
        "runner_imported": False,
        "verified_at_utc": utc_now(),
        "passed_count": 0,
        "failed_count": 1,
        "checks": [
            check(
                "recovery.attempt3_deterministic_failure",
                False,
                {"stage": "verification_build", "code": "deterministic_contract_failure"},
            )
        ],
        "failure": {
            "sealed": True,
            "stage": "verification_build",
            "code": "deterministic_contract_failure",
            "exception_details_recorded": False,
        },
        "claim_boundary": (
            "Terminal Incident-002 verification attempt-3 failure seal; no scientific conclusion."
        ),
    }
    validate_failed_attempt3_result(result)
    return result


def validate_failed_attempt3_result(value: dict[str, Any]) -> None:
    expected = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "model_seed",
        "scope", "verification_attempt", "status", "runner_imported",
        "verified_at_utc", "passed_count", "failed_count", "checks", "failure",
        "claim_boundary",
    }
    rows = value.get("checks", [])
    failure = value.get("failure", {})
    attempt2, _records = require_attempt2_failure()
    require_attempt1_failure()
    if not (
        set(value) == expected
        and value.get("schema_version")
        == "exp-router-formal-verification-attempt-3-failure-v1"
        and value.get("experiment_id") == EXPERIMENT_ID
        and value.get("run_id") == RUN_ID
        and value.get("attempt_id") == ATTEMPT_ID
        and type(value.get("model_seed")) is int
        and value.get("model_seed") == MODEL_SEED
        and value.get("scope") == "final"
        and type(value.get("verification_attempt")) is int
        and value.get("verification_attempt") == 3
        and value.get("status") == "Failed"
        and value.get("runner_imported") is False
        and is_canonical_utc_timestamp(value.get("verified_at_utc"))
        and canonical_utc_datetime(attempt2["verified_at_utc"])
        <= canonical_utc_datetime(value["verified_at_utc"])
        and type(value.get("passed_count")) is int
        and value.get("passed_count") == 0
        and type(value.get("failed_count")) is int
        and value.get("failed_count") == 1
        and incident1.exact_typed_equal(rows, [{
            "name": "recovery.attempt3_deterministic_failure",
            "passed": False,
            "detail": {"stage": "verification_build", "code": "deterministic_contract_failure"},
        }])
        and incident1.exact_typed_equal(failure, {
            "sealed": True,
            "stage": "verification_build",
            "code": "deterministic_contract_failure",
            "exception_details_recorded": False,
        })
        and value.get("claim_boundary")
        == "Terminal Incident-002 verification attempt-3 failure seal; no scientific conclusion."
        and not incident1.public_sensitive_paths(value)
    ):
        raise ValueError("Attempt-3 terminal failure schema drift")


def render_summary(result: dict[str, Any]) -> str:
    if result.get("status") == "Failed":
        validate_failed_attempt3_result(result)
        return "\n".join(
            [
                "# EXP-061 / EXP-060 Final Router Verification Attempt 3",
                "",
                "- Status: `Failed`",
                "- Failure sealed: `true`",
                "- Failure stage: `verification_build`",
                "- Failure code: `deterministic_contract_failure`",
                "- Exception details recorded: `false`",
                "- Scientific conclusion: none",
                "",
                result["claim_boundary"],
                "",
            ]
        )
    if result.get("status") != "Passed":
        raise ValueError("Attempt-3 summary status is not registered")
    return "\n".join(
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
            result["claim_boundary"],
            "",
        ]
    )


def expected_summary_payload(result: dict[str, Any]) -> bytes:
    return (render_summary(result) + "\n").encode("utf-8")


def write_attempt3(result: dict[str, Any]) -> None:
    output = resolve_relative(ATTEMPT3_VERIFICATION_REL)
    summary = resolve_relative(ATTEMPT3_SUMMARY_REL)
    if os.path.lexists(output) or os.path.lexists(summary):
        raise FileExistsError("Attempt-3 verification outputs are append-only")
    payload = canonical_json_payload(result)
    incident1.create_once(output, payload)
    incident1.create_once(summary, expected_summary_payload(result))


def canonical_json_payload(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def require_passed_attempt3() -> tuple[Path, dict[str, Any], dict[str, Any]]:
    path = resolve_relative(ATTEMPT3_VERIFICATION_REL)
    value = read_bound_json(path)
    validate_attempt3_result(value)
    summary_path = resolve_relative(ATTEMPT3_SUMMARY_REL)
    if incident1.read_bound_regular_file(summary_path) != expected_summary_payload(value):
        raise ValueError("Attempt-3 summary path/mode/content drift")
    return path, value, artifact(summary_path)


def completion_lineage(
    verification_path: Path, summary_record: dict[str, Any]
) -> dict[str, Any]:
    config_path, config = load_incident2_config()
    return {
        "incident_id": "002",
        "attempt_1_failed": copy.deepcopy(config["lineage"]["attempt_1"]),
        "incident_001": copy.deepcopy(config["lineage"]["incident_001"]),
        "attempt_2_failed": copy.deepcopy(config["lineage"]["attempt_2"]),
        "incident_002_config": artifact(config_path),
        "incident_002_protocol": copy.deepcopy(config["implementation"]["amendment_protocol"]),
        "incident_002_verifier": copy.deepcopy(config["implementation"]["recovery_verifier"]),
        "incident_002_tests": copy.deepcopy(config["implementation"]["recovery_tests"]),
        "incident_002_finalizer": copy.deepcopy(config["implementation"]["finalizer"]),
        "incident_002_finalizer_tests": copy.deepcopy(config["implementation"]["finalizer_tests"]),
        "attempt_3_passed": artifact(verification_path),
        "attempt_3_summary": copy.deepcopy(summary_record),
    }


def complete() -> dict[str, Any]:
    completion_path = resolve_relative(COMPLETION_REL)
    if os.path.lexists(completion_path):
        raise FileExistsError("Router completion record is immutable")
    if os.path.lexists(resolve_relative(SELECTION_REL)):
        raise FileExistsError("A final pipeline selection already exists")
    verification_path, verification, summary = require_passed_attempt3()
    config_path = incident1.require_expected(FORMAL_CONFIG_REL)
    run_path = incident1.require_expected(RUN_REL)
    selected_path = incident1.require_expected(SELECTED_REL)
    private_path = incident1.require_expected(PRIVATE_ROUTER_OOF_REL)
    config = incident1.load_json(config_path)
    run = incident1.load_json(run_path)
    selected = incident1.load_json(selected_path)
    passed = incident1.primary_gate_result(selected)
    decision = "Pass" if passed else "Fail"
    if not (
        incident1.identity_matches(run)
        and run.get("status") == "CompletedAwaitingVerification"
        and config.get("rq_id") == run.get("rq_id") == RQ_ID
        and config.get("stage") == run.get("stage") == ROUTER_STAGE
        and incident1.exact_typed_equal(
            config.get("seed_contract"), run.get("seed_contract")
        )
        and run.get("decision") == decision
        and run.get("config") == artifact(config_path)
        and run.get("public_outputs", {}).get("selected_operating_point_json")
        == artifact(selected_path)
    ):
        raise ValueError("Formal router run/result identity drift")
    completed_at = utc_now()
    attempt2, _records = require_attempt2_failure()
    if not (
        canonical_utc_datetime(attempt2["verified_at_utc"])
        <= canonical_utc_datetime(verification["verified_at_utc"])
        <= canonical_utc_datetime(completed_at)
    ):
        raise ValueError("Failed-to-Passed completion chronology drift")
    completion = {
        "schema_version": "exp-router-completion-v3",
        "experiment_id": EXPERIMENT_ID,
        "rq_id": RQ_ID,
        "stage": ROUTER_STAGE,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "model_seed": MODEL_SEED,
        "seed_contract": config["seed_contract"],
        "status": "Complete",
        "completed_at_utc": completed_at,
        "decision": decision,
        "primary_gate_passed": passed,
        "verification_attempt": 3,
        "recovery_lineage": completion_lineage(verification_path, summary),
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
    if incident1.public_sensitive_paths(completion):
        raise ValueError("Attempt-3 completion contains row-level fields")
    validate_completion_record(completion)
    payload = canonical_json_payload(completion)
    incident1.create_once(completion_path, payload)
    return completion


def validate_completion_record(completion: dict[str, Any]) -> None:
    expected_keys = {
        "schema_version", "experiment_id", "rq_id", "stage", "run_id",
        "attempt_id", "model_seed", "seed_contract", "status", "completed_at_utc",
        "decision", "primary_gate_passed", "verification_attempt",
        "recovery_lineage", "artifacts", "next_gate", "claim_boundary",
    }
    verification_path, verification, summary = require_passed_attempt3()
    formal_config_path = incident1.require_expected(FORMAL_CONFIG_REL)
    run_path = incident1.require_expected(RUN_REL)
    selected_path = incident1.require_expected(SELECTED_REL)
    formal_config = incident1.load_bound_json(formal_config_path)
    run = incident1.load_bound_json(run_path)
    selected = incident1.load_bound_json(selected_path)
    passed = incident1.primary_gate_result(selected)
    decision = "Pass" if passed else "Fail"
    artifacts = completion.get("artifacts", {})
    expected_artifacts = {
        "config": artifact(incident1.require_expected(FORMAL_CONFIG_REL)),
        "run": artifact(incident1.require_expected(RUN_REL)),
        "selected_operating_point": artifact(incident1.require_expected(SELECTED_REL)),
        "final_verification": artifact(verification_path),
        "private_router_oof": artifact(incident1.require_expected(PRIVATE_ROUTER_OOF_REL)),
    }
    attempt2, _records = require_attempt2_failure()
    if not (
        set(completion) == expected_keys
        and completion.get("schema_version") == "exp-router-completion-v3"
        and completion.get("experiment_id") == EXPERIMENT_ID
        and completion.get("rq_id") == RQ_ID
        and completion.get("stage") == ROUTER_STAGE
        and completion.get("run_id") == RUN_ID
        and completion.get("attempt_id") == ATTEMPT_ID
        and type(completion.get("model_seed")) is int
        and completion.get("model_seed") == MODEL_SEED
        and incident1.exact_typed_equal(
            completion.get("seed_contract"), formal_config.get("seed_contract")
        )
        and completion.get("status") == "Complete"
        and is_canonical_utc_timestamp(completion.get("completed_at_utc"))
        and canonical_utc_datetime(attempt2["verified_at_utc"])
        <= canonical_utc_datetime(verification["verified_at_utc"])
        <= canonical_utc_datetime(completion["completed_at_utc"])
        and completion.get("decision") == decision
        and completion.get("primary_gate_passed") is passed
        and type(completion.get("verification_attempt")) is int
        and completion.get("verification_attempt") == 3
        and incident1.exact_typed_equal(
            completion.get("recovery_lineage"),
            completion_lineage(verification_path, summary),
        )
        and incident1.exact_typed_equal(artifacts, expected_artifacts)
        and completion.get("next_gate") == COMPLETION_NEXT_GATE
        and completion.get("claim_boundary") == COMPLETION_CLAIM_BOUNDARY
        and incident1.identity_matches(run)
        and run.get("status") == "CompletedAwaitingVerification"
        and formal_config.get("rq_id") == run.get("rq_id") == RQ_ID
        and formal_config.get("stage") == run.get("stage") == ROUTER_STAGE
        and incident1.exact_typed_equal(
            formal_config.get("seed_contract"), run.get("seed_contract")
        )
        and run.get("decision") == decision
        and incident1.exact_typed_equal(
            run.get("config"), artifact(formal_config_path)
        )
        and incident1.exact_typed_equal(
            run.get("public_outputs", {}).get("selected_operating_point_json"),
            artifact(selected_path),
        )
        and not incident1.public_sensitive_paths(completion)
    ):
        raise ValueError("Attempt-3 completion contract drift")


def verify_completion() -> dict[str, Any]:
    completion = read_bound_json(resolve_relative(COMPLETION_REL))
    validate_completion_record(completion)
    rows = [
        check("completion.attempt3_passed", True),
        check("completion.failed_lineage_preserved", True),
        check("completion.artifacts_rehashed", True),
        check("completion.private_modes", all(row["matches_expected"] for row in incident1.private_mode_manifest())),
        check("completion.public_modes", all(row["matches_expected"] for row in incident1.mode_manifest(after=True))),
        check("completion.public_tree", public_tree_digest() == load_incident2_config()[1]["public_state"]["content_tree"]),
        check("completion.selection_absent", not os.path.lexists(resolve_relative(SELECTION_REL))),
        check("completion.public_privacy", not incident1.public_sensitive_paths(completion)),
    ]
    return {
        "schema_version": "exp-router-completion-verification-attempt-3-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "model_seed": MODEL_SEED,
        "scope": "completion",
        "verified_at_utc": utc_now(),
        "status": "Passed" if all(row["passed"] for row in rows) else "Failed",
        "passed_count": sum(row["passed"] for row in rows),
        "failed_count": sum(not row["passed"] for row in rows),
        "checks": rows,
        "independence": {
            "runner_not_imported": True,
            "completion_rehashed": True,
            "attempt3_revalidated": True,
            "failed_lineage_revalidated": True,
        },
    }


def run_final() -> dict[str, Any]:
    if os.path.lexists(resolve_relative(ATTEMPT3_VERIFICATION_REL)) or os.path.lexists(
        resolve_relative(ATTEMPT3_SUMMARY_REL)
    ):
        raise FileExistsError("Attempt-3 verification outputs are append-only")
    preflight = attempt3_preflight()
    try:
        result = build_attempt3_result(preflight)
    except Exception:
        result = build_failed_attempt3_result()
        write_attempt3(result)
        return result
    write_attempt3(result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("final", "complete", "completion"), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.scope == "final":
        result = run_final()
    elif args.scope == "complete":
        result = complete()
    else:
        result = verify_completion()
    print(json.dumps(result, sort_keys=True))
    if result.get("status") not in {"Passed", "Complete"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
