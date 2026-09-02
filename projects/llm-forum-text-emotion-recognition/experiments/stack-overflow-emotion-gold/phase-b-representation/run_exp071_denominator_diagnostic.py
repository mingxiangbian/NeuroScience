#!/usr/bin/env python3
"""Minor EXP-071 Incident-002 denominator-category diagnostic."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from typing import Any, Iterator, Mapping, Sequence


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
DEFAULT_STATIC_CONFIG = MODULE_DIR / "configs/exp-071-denominator-diagnostic-preflight.json"
DEFAULT_DIAGNOSTIC_CONFIG = MODULE_DIR / "configs/exp-071-denominator-diagnostic-formal-attempt-1.json"
EXPERIMENT_ID = "EXP-071"
DIAGNOSTIC_ID = "EXP-071-DENOMINATOR-DIAGNOSTIC-INCIDENT-002"
ALL_POINTS = ("H-1", "H7", "H15", "H19", "H20", "H27", "H31", "H35", "HF")
CONFIRMATION_POINTS = ("H19", "H27", "HF")
FOLDS = (0, 1, 2, 3, 4)
CONDITION_ORDER = tuple([f"s42:{p}" for p in ALL_POINTS] + [f"s43:{p}" for p in CONFIRMATION_POINTS] + [f"s44:{p}" for p in CONFIRMATION_POINTS])
CATEGORIES = frozenset({"zero", "finite_positive", "nonfinite"})
LOCALIZATION_KEYS = {"condition", "fold", "pairs_examined", "norm_x", "norm_z", "denominator"}
SNAPSHOT_SCOPE = "diagnostic_minimal_bound_artifacts_no_ap5_probe"
METHOD_SHA256 = "a90ed692f6171f4fd55ce1f67c85bb11c071c26276d3e48777d9c97aced7fa76"
SOURCE_SHA256 = "20ab3dd3789b2440d8cd9ab1b9a4035cee20224c05d2dcda85bfe9419f11516b"
INCIDENT_SHA256 = "b91c017308a410cacc1448142985ed868b534f757d53ff4147b1d476d90d3864"
PROTOCOL_RECORD = {
    "path": "experiments/stack-overflow-emotion-gold/protocols/exp-071-denominator-diagnostic-incident-002.md",
    "bytes": 6098, "mode": "0644",
    "sha256": "43cdf1efa8cea5cf226e3ea6877504200a8433c3d46314f8101e6b7ea129b353",
}
HELPER_PATH = MODULE_DIR / "run_exp071_drift.py"
HELPER_BYTES = 106530
HELPER_SHA256 = "d8c9b053652c93f2609910a35388e1fc4548590c5a79d679f246e6e17fed9e3f"
HEAVY_LOCK = MODULE_DIR / "private/locks/heavy-research-workload.lock"
DIAGNOSTIC_LOCK = MODULE_DIR / "private/locks/exp071-denominator-diagnostic.lock"
IMPLEMENTATION_PATHS = {
    "runner": "experiments/stack-overflow-emotion-gold/phase-b-representation/run_exp071_denominator_diagnostic.py",
    "verifier": "experiments/stack-overflow-emotion-gold/phase-b-representation/verify_exp071_denominator_diagnostic.py",
    "tests": "experiments/stack-overflow-emotion-gold/phase-b-representation/tests/test_exp071_denominator_diagnostic.py",
}
RESOURCES = {"maximum_concurrent_workers": 1, "runner_wall_seconds": 7200, "verifier_wall_seconds": 7200, "peak_rss_bytes": 4294967296, "private_output_budget_bytes": 8388608, "minimum_free_disk_bytes": 1073741824, "threads_per_library": 1, "api_cost_usd": 0}
STATIC_CLAIM = "No-result readiness for a Minor technical denominator-failure diagnostic. It supports no EXP-071 scientific result, no original-attempt resumption and no method change. Original formal-attempt-1 remains Failed; diagnostic execution requires a separate activated config."
DIAGNOSTIC_CLAIM = "Technical localization of the first original-order pair that fails the frozen CKA denominator gate, reported as categories only. Original EXP-071 formal-attempt-1 remains Failed. This diagnostic supports no geometry, effect-size, onset, causal, generalization or mechanism claim and authorizes no recovery, original-attempt resumption, method change, selection or EXP-072."
ACCESS_HASHES = {"static": "e398e14343d77f644b1aca598622677578baad715852452417395e8119b135b2", "diagnostic": "80a1df03f58f05fd22a1fa235565e7826c3119352b326afdfa1ce17b60e901f1"}
STATIC_ACCESS = {
    "bound_artifact_bytes_hashed": True, "headers_read": True,
    "original_failure_metadata_read": True, "representation_values_read": False,
    "row_contract_ordinal_fold_values_read": False, "component_code_values_read": False,
    "denominator_categories_computed": False, "other_drift_metrics_computed": False,
    "ap5_probe_files_opened": False, "labels_read": False,
    "sample_component_ids_read": False, "text_read": False,
    "model_loaded": False, "forward_executed": False,
    "validation_test_accessed": False, "exact_term_values_persisted": False,
    "source_mutated": False,
}
INITIALIZE_ACCESS = dict(STATIC_ACCESS)
DIAGNOSTIC_ACCESS = {**STATIC_ACCESS, "representation_values_read": True, "row_contract_ordinal_fold_values_read": True, "denominator_categories_computed": True}


def _load_identity_helpers() -> Any:
    if HELPER_PATH.is_symlink() or not HELPER_PATH.is_file():
        raise ValueError("Unsafe frozen runner helper")
    info = HELPER_PATH.stat()
    payload = HELPER_PATH.read_bytes()
    if info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o644 or len(payload) != HELPER_BYTES or hashlib.sha256(payload).hexdigest() != HELPER_SHA256:
        raise ValueError("Frozen runner helper identity drift")
    spec = importlib.util.spec_from_file_location("exp071_diagnostic_frozen_io_helpers", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load frozen safety helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SAFE = _load_identity_helpers()
canonical_json_bytes = SAFE.canonical_json_bytes
strict_json = SAFE.strict_json
artifact = SAFE.artifact
require_record = SAFE.require_record
resolve_project = SAFE.resolve_project
create_json_once = SAFE.create_json_once
read_npy_header = SAFE.read_npy_header
read_npz_headers = SAFE.read_npz_headers


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def classify_nonnegative(value: float) -> str:
    number = float(value)
    if not math.isfinite(number):
        return "nonfinite"
    if number < 0.0:
        raise ValueError("unexpected_finite_negative")
    return "zero" if number == 0.0 else "finite_positive"


def denominator_categories(x: Any, z: Any) -> dict[str, str]:
    import numpy as np

    frozen = np.ascontiguousarray(x, dtype=np.float64)
    adapted = np.ascontiguousarray(z, dtype=np.float64)
    if frozen.ndim != 2 or adapted.shape != frozen.shape or frozen.shape[0] < 2 or frozen.shape[1] < 1:
        raise ValueError("unexpected_input_shape")
    if not np.all(np.isfinite(frozen)) or not np.all(np.isfinite(adapted)):
        raise ValueError("unexpected_nonfinite_input")
    with np.errstate(over="ignore", invalid="ignore", under="ignore"):
        xc = frozen - np.mean(frozen, axis=0, dtype=np.float64)
        zc = adapted - np.mean(adapted, axis=0, dtype=np.float64)
        k = xc @ xc.T
        l = zc @ zc.T
        norm_x = float(np.sum(k * k, dtype=np.float64))
        norm_z = float(np.sum(l * l, dtype=np.float64))
        denominator = float(np.sqrt(norm_x * norm_z))
    return {"norm_x": classify_nonnegative(norm_x), "norm_z": classify_nonnegative(norm_z), "denominator": classify_nonnegative(denominator)}


def first_denominator_failure(partitions: Sequence[Any], pair_loader: Any, condition_order: Sequence[str] = CONDITION_ORDER, budget_check: Any = None) -> dict[str, Any]:
    if not partitions or not condition_order:
        raise ValueError("empty_comparison_plan")
    examined = 0
    for condition in condition_order:
        for fold, ordinals in enumerate(partitions):
            if budget_check is not None:
                budget_check()
            x, z = pair_loader(condition, fold, ordinals)
            categories = denominator_categories(x, z)
            examined += 1
            if any(value != "finite_positive" for value in categories.values()):
                return {"condition": condition, "fold": fold, "pairs_examined": examined, **categories}
    raise RuntimeError("failure_not_reproduced")


def validate_localization(value: Any) -> None:
    if not isinstance(value, Mapping) or set(value) != LOCALIZATION_KEYS:
        raise ValueError("localization_schema_drift")
    condition, fold = value["condition"], value["fold"]
    if condition not in CONDITION_ORDER or type(fold) is not int or fold not in FOLDS:
        raise ValueError("localization_identity_drift")
    if type(value["pairs_examined"]) is not int or value["pairs_examined"] != CONDITION_ORDER.index(condition) * 5 + fold + 1:
        raise ValueError("localization_prefix_drift")
    categories = [value[key] for key in ("norm_x", "norm_z", "denominator")]
    if any(item not in CATEGORIES for item in categories) or all(item == "finite_positive" for item in categories):
        raise ValueError("localization_category_drift")


@contextmanager
def diagnostic_lock() -> Iterator[None]:
    with SAFE._file_mutex(HEAVY_LOCK, "heavy research"):
        with SAFE._file_mutex(DIAGNOSTIC_LOCK, "EXP-071 denominator diagnostic"):
            yield


def expected_outputs(kind: str) -> dict[str, Any]:
    prefix = "experiments/stack-overflow-emotion-gold/phase-b-representation/"
    stem = "exp-071-representation-drift/"
    value = {
        "formal_public_root": prefix + "runs/" + stem + "denominator-diagnostic-attempt-1",
        "formal_private_root": prefix + "private/" + stem + "denominator-diagnostic-attempt-1",
        "public_directory_mode": "0755", "public_file_mode": "0644",
        "private_directory_mode": "0700", "private_file_mode": "0600",
    }
    if kind == "static":
        value.update({
            "preflight_public_root": prefix + "runs/" + stem + "denominator-diagnostic-preflight-attempt-1",
            "preflight_private_root": prefix + "private/" + stem + "denominator-diagnostic-preflight-attempt-1",
            "public_success_allowlist": ["static.json", "static-verification.json", "no-result-complete.json"],
            "public_runner_failure_allowlist": ["failure.json"],
            "private_success_allowlist": ["input-contract-manifest.json"],
            "formal_roots_must_be_absent": True,
        })
    else:
        value.update({
            "public_claim_allowlist": ["run-claim.json"],
            "public_diagnosed_allowlist": ["run-claim.json", "run.json"],
            "public_verified_allowlist": ["run-claim.json", "run.json", "verification.json"],
            "public_success_allowlist": ["run-claim.json", "run.json", "verification.json", "diagnostic-complete.json"],
            "public_runner_failure_allowlist": ["run-claim.json", "failure.json"],
            "private_initialized_allowlist": ["input-manifest.json"],
            "private_success_allowlist": ["input-manifest.json", "diagnostic-manifest.json"],
            "formal_roots_must_be_fresh": True,
            "active_config_path": prefix + "configs/exp-071-denominator-diagnostic-formal-attempt-1.json",
        })
    return value


def expected_authorization(kind: str) -> dict[str, Any]:
    value = {key: False for key in (
        "static_runner_authorized", "static_verifier_authorized", "diagnostic_initialize_authorized",
        "diagnostic_run_authorized", "diagnostic_verification_authorized", "diagnostic_completion_authorized",
        "representation_value_access_authorized", "row_contract_value_access_authorized",
        "probe_metric_value_access_authorized", "model_loading_authorized", "forward_authorized",
        "original_attempt_resume_authorized", "method_change_authorized",
    )}
    enabled = ("static_runner_authorized", "static_verifier_authorized") if kind == "static" else (
        "diagnostic_initialize_authorized", "diagnostic_run_authorized", "diagnostic_verification_authorized",
        "diagnostic_completion_authorized", "representation_value_access_authorized", "row_contract_value_access_authorized",
    )
    for key in enabled:
        value[key] = True
    if kind != "static":
        value["activation_condition"] = "Passed_static_completion_exact_identities_bound"
    return value


def validate_config(config: Mapping[str, Any], kind: str, *, allow_pending: bool = False) -> None:
    if kind not in {"static", "diagnostic"}:
        raise ValueError("config_kind_drift")
    top = {"schema_version", "experiment_id", "diagnostic_id", "rq_id", "tier", "registered_at", "method_protocol", "implementation", "incident", "source", "method", "environment", "resources", "run_id", "attempt_id", "stage", "authorization", "access", "outputs", "claim_boundary"}
    if kind != "static":
        top.add("preflight")
    suffix = "preflight" if kind == "static" else "formal"
    if set(config) != top or config.get("schema_version") != f"exp-071-denominator-diagnostic-{suffix}-config-v1":
        raise ValueError("config_schema_drift")
    expected = ("exp-071-denominator-diagnostic-preflight", "denominator-diagnostic-preflight-attempt-1", "no-result-preflight") if kind == "static" else ("exp-071-denominator-diagnostic", "denominator-diagnostic-attempt-1", "formal-diagnostic")
    if (config.get("run_id"), config.get("attempt_id"), config.get("stage")) != expected or config.get("experiment_id") != EXPERIMENT_ID or config.get("diagnostic_id") != DIAGNOSTIC_ID or config.get("rq_id") != "RQ-S4.2" or config.get("tier") != "Minor technical failure diagnostic" or config.get("registered_at") != "2026-08-30":
        raise ValueError("config_identity_drift")
    if config.get("method_protocol") != PROTOCOL_RECORD or digest(config.get("method")) != METHOD_SHA256 or digest(config.get("source")) != SOURCE_SHA256 or digest(config.get("incident")) != INCIDENT_SHA256:
        raise ValueError("frozen_contract_drift")
    if config.get("environment") != SAFE.EXPECTED_ENVIRONMENT or config.get("resources") != RESOURCES or config.get("outputs") != expected_outputs(kind):
        raise ValueError("runtime_resource_or_output_drift")
    if config.get("claim_boundary") != (STATIC_CLAIM if kind == "static" else DIAGNOSTIC_CLAIM):
        raise ValueError("claim_boundary_drift")
    implementation = config.get("implementation", {})
    if set(implementation) != set(IMPLEMENTATION_PATHS):
        raise ValueError("implementation_inventory_drift")
    for name, path in IMPLEMENTATION_PATHS.items():
        record = implementation[name]
        if set(record) != {"path", "bytes", "mode", "sha256", "status"} or record.get("path") != path:
            raise ValueError("implementation_path_drift")
        if not allow_pending and (record.get("status") != "Frozen" or record.get("mode") != "0644" or type(record.get("bytes")) is not int or record["bytes"] <= 0 or record.get("sha256") == "TBD"):
            raise ValueError("implementation_unfrozen")
    if not allow_pending and config.get("authorization") != expected_authorization(kind):
        raise PermissionError("authorization_drift")
    access = config.get("access", {})
    normalized_access = dict(access)
    if kind == "diagnostic":
        normalized_access["currently_authorized"] = False
    if digest(normalized_access) != ACCESS_HASHES[kind]:
        raise PermissionError("access_contract_drift")
    if kind == "static":
        if set(access) != {"static_may_read", "static_must_not_read", "formal_root_creation"} or access.get("formal_root_creation") is not False:
            raise PermissionError("static_access_drift")
    else:
        if set(access) != {"formal_may_read_after_activation", "formal_must_not_read", "formal_model_load", "formal_forward", "formal_source_mutation", "currently_authorized"} or any(access.get(key) is not False for key in ("formal_model_load", "formal_forward", "formal_source_mutation")):
            raise PermissionError("diagnostic_access_drift")
        if not allow_pending and access.get("currently_authorized") is not True:
            raise PermissionError("diagnostic_access_inactive")
        parent = config.get("preflight", {})
        if set(parent) != {"config", "static_run", "static_verification", "no_result_completion", "required_statuses", "diagnostic_execution_authorized_by_preflight"}:
            raise ValueError("preflight_schema_drift")
        for key in ("config", "static_run", "static_verification", "no_result_completion"):
            if set(parent[key]) != {"path", "bytes", "mode", "sha256"}:
                raise ValueError("preflight_record_schema_drift")


def load_config(path: Path, kind: str) -> dict[str, Any]:
    path = Path(path).resolve()
    config = strict_json(path)
    validate_config(config, kind)
    expected = DEFAULT_STATIC_CONFIG if kind == "static" else DEFAULT_DIAGNOSTIC_CONFIG
    if path != expected.resolve():
        raise ValueError("config_path_drift")
    return config


def require_implementation(config: Mapping[str, Any]) -> None:
    paths = {key: require_record(value) for key, value in config["implementation"].items()}
    if paths["runner"].resolve() != Path(__file__).resolve():
        raise ValueError("runner_identity_drift")


def source_identity_snapshot(config: Mapping[str, Any]) -> dict[str, Any]:
    records = {}
    for group in ("method_protocol", "implementation", "incident", "source"):
        for record in SAFE._walk_artifact_records(config[group]):
            path = require_record(record)
            current = artifact(path)
            if current["path"] in records and records[current["path"]] != current:
                raise ValueError("source_identity_conflict")
            records[current["path"]] = current
    ordered = [records[key] for key in sorted(records)]
    return {"artifact_count": len(ordered), "artifacts": ordered, "sha256": digest(ordered)}


def inspect_sources(config: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    incident, source = config["incident"], config["source"]
    original = strict_json(require_record(incident["failed_config"]))
    if digest(original["method"]) != incident["original_method_sha256"] or digest(original["source"]) != incident["original_source_contract_sha256"]:
        raise ValueError("original_metadata_drift")
    old_source = original["source"]
    if source["matrices"] != old_source["matrices"] or source["matrix_root"] != old_source["matrix_root"] or source["row_contract"] != old_source["exp070_extraction_terminal"]["row_contract"]:
        raise ValueError("minimal_source_binding_drift")
    original_identity = old_source["exp070_extraction_terminal"]["row_identity"]
    if source["row_identity"] != {key: original_identity[key] for key in ("rows", "ordinal_sha256", "fold_id_order_sha256")}:
        raise ValueError("row_metadata_binding_drift")
    for name in ("runner", "verifier"):
        if source["helpers"][name] != {key: original["implementation"][name][key] for key in ("path", "bytes", "mode", "sha256")}:
            raise ValueError("helper_binding_drift")
    failure_path = require_record(incident["failure_artifact"])
    selected, _ = SAFE.selective_json_scalars(failure_path.read_bytes(), [(key,) for key in incident["expected_failure"]])
    if {key[0]: value for key, value in selected.items()} != incident["expected_failure"]:
        raise ValueError("failed_prefix_drift")
    claim_path = require_record(incident["run_claim"])
    claim, _ = SAFE.selective_json_scalars(claim_path.read_bytes(), [("status",), ("config", "sha256"), ("input_manifest", "sha256"), ("method_sha256",)])
    input_path = require_record(incident["input_manifest"])
    original_input, _ = SAFE.selective_json_scalars(input_path.read_bytes(), [("status",), ("config", "sha256"), ("method_sha256",), ("source_snapshot_sha256",)])
    if claim[("status",)] != "Initialized" or original_input[("status",)] != "Initialized" or claim[("config", "sha256")] != incident["failed_config"]["sha256"] or original_input[("config", "sha256")] != incident["failed_config"]["sha256"] or claim[("input_manifest", "sha256")] != incident["input_manifest"]["sha256"] or claim[("method_sha256",)] != incident["original_method_sha256"] or original_input[("method_sha256",)] != incident["original_method_sha256"] or original_input[("source_snapshot_sha256",)] != incident["original_source_snapshot_sha256"]:
        raise ValueError("original_initialized_binding_drift")
    SAFE.require_exact_inventory(claim_path.parent, ["run-claim.json", "failure.json"], private=False)
    SAFE.require_exact_inventory(input_path.parent, ["input-manifest.json"], private=True)
    headers = []
    for item in source["matrices"]:
        path = require_record(item["artifact"])
        header = read_npy_header(path)
        if header["shape"] != item["shape"] or header["descr"] != "<f4" or header["fortran_order"] or header["file_bytes"] != header["data_offset"] + math.prod(item["shape"]) * 4:
            raise ValueError("matrix_header_drift")
        headers.append({"worker_id": item["worker_id"], **header})
    row_headers = read_npz_headers(require_record(source["row_contract"]))
    if row_headers["member_order"] != ["ordinal", "fold_id", "component_code"]:
        raise ValueError("row_header_inventory_drift")
    for name, dtype in (("ordinal", "<i4"), ("fold_id", "|i1"), ("component_code", "<i4")):
        header = row_headers["members"][name]
        if header["shape"] != [3360] or header["descr"] != dtype or header["fortran_order"]:
            raise ValueError("row_header_schema_drift")
    return headers, row_headers


def _root(config: Mapping[str, Any], *, private: bool, static: bool) -> Path:
    return resolve_project(config["outputs"][f"{'preflight' if static else 'formal'}_{'private' if private else 'public'}_root"], must_exist=False)


def _ids(config: Mapping[str, Any]) -> dict[str, Any]:
    return {key: config[key] for key in ("experiment_id", "diagnostic_id", "run_id", "attempt_id")}


def _resource_record(started: float, config: Mapping[str, Any]) -> dict[str, Any]:
    value = {"elapsed_seconds": time.monotonic() - started, "peak_rss_bytes": SAFE._peak_rss_bytes(), "api_cost_usd": 0}
    if value["elapsed_seconds"] > config["resources"]["runner_wall_seconds"] or value["peak_rss_bytes"] > config["resources"]["peak_rss_bytes"]:
        raise RuntimeError("resource_ceiling_exceeded")
    return value


def validate_public_payload(value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("public_payload_schema_drift")
    if "localization" in value:
        validate_localization(value["localization"])
    forbidden = {"representations", "rowwise_values", "heldout_ordinals", "labels", "probabilities", "predictions", "sample_ids", "component_ids", "component_codes", "exact_norm_values", "raw_text"}
    def visit(item: Any, path: tuple[Any, ...] = ()) -> None:
        if isinstance(item, Mapping):
            if set(item) & forbidden:
                raise ValueError("public_value_leakage")
            for key, child in item.items():
                if key in {"norm_x", "norm_z", "denominator"} and (type(child) is not str or child not in CATEGORIES):
                    raise ValueError("exact_term_value_leakage")
                visit(child, path + (key,))
        elif isinstance(item, list):
            if len(item) >= 672:
                raise ValueError("rowwise_value_leakage")
            for index, child in enumerate(item):
                visit(child, path + (index,))
        elif isinstance(item, str):
            if "phase-b-representation/private/" in item.lower():
                raise ValueError("private_path_leakage")
            if "/users/" in item.lower() and not (path == ("execution", "command", 0) and item == SAFE.EXPECTED_ENVIRONMENT["python_executable"]):
                raise ValueError("absolute_path_leakage")
    visit(value)


def static_stage(config_path: Path = DEFAULT_STATIC_CONFIG) -> dict[str, Any]:
    config_path = Path(config_path).resolve()
    started = time.monotonic()
    SAFE._require_static_import_boundary()
    config = load_config(config_path, "static")
    require_implementation(config)
    SAFE._require_private_ignore()
    SAFE._environment_record(config, check_process=True)
    public, private = _root(config, private=False, static=True), _root(config, private=True, static=True)
    for path in (public, private, _root(config, private=False, static=False), _root(config, private=True, static=False)):
        if os.path.lexists(path):
            raise FileExistsError("nonfresh_diagnostic_root")
    before = source_identity_snapshot(config)
    matrix_headers, row_headers = inspect_sources(config)
    synthetic = SAFE.run_synthetic_tests(config)
    after = source_identity_snapshot(config)
    if before != after:
        raise ValueError("minimal_diagnostic_source_drift")
    SAFE._create_root(private, private=True)
    SAFE._create_root(public, private=False)
    input_value = {**_ids(config), "schema_version": "exp-071-denominator-diagnostic-static-input-v1", "status": "Sealed", "config": artifact(config_path), "method_sha256": METHOD_SHA256, "source_snapshot": before, "matrix_headers": matrix_headers, "row_contract_headers": row_headers, "access": dict(STATIC_ACCESS)}
    input_path = private / "input-contract-manifest.json"
    create_json_once(input_path, input_value, private=True)
    if SAFE._private_size(private) > config["resources"]["private_output_budget_bytes"]:
        raise RuntimeError("private_budget_exceeded")
    report = {**_ids(config), "schema_version": "exp-071-denominator-diagnostic-static-run-v1", "stage": "static", "status": "CompletedAwaitingVerification", "config": artifact(config_path), "input_manifest": artifact(input_path, logical_name="input-contract-manifest.json"), "method_sha256": METHOD_SHA256, "source_snapshot_sha256": before["sha256"], "source_snapshot_scope": SNAPSHOT_SCOPE, "synthetic_tests": synthetic, "resources": _resource_record(started, config), "access": dict(STATIC_ACCESS), "claim_boundary": config["claim_boundary"]}
    validate_public_payload(report)
    create_json_once(public / "static.json", report)
    SAFE.require_exact_inventory(public, ["static.json"], private=False)
    SAFE.require_exact_inventory(private, ["input-contract-manifest.json"], private=True)
    return report


def require_preflight(config: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    parent = config["preflight"]
    if parent["required_statuses"] != {"static_run": "CompletedAwaitingVerification", "static_verification": "Passed", "no_result_completion": "Complete"} or parent["diagnostic_execution_authorized_by_preflight"] is not True:
        raise PermissionError("preflight_activation_drift")
    paths = {key: require_record(parent[key]) for key in ("config", "static_run", "static_verification", "no_result_completion")}
    static = load_config(paths["config"], "static")
    for key in ("method_protocol", "implementation", "incident", "source", "method", "environment", "resources"):
        if static[key] != config[key]:
            raise ValueError("static_diagnostic_contract_drift")
    public, private = _root(static, private=False, static=True), _root(static, private=True, static=True)
    expected_paths = {"config": DEFAULT_STATIC_CONFIG.resolve(), "static_run": public / "static.json", "static_verification": public / "static-verification.json", "no_result_completion": public / "no-result-complete.json"}
    if any(paths[key].resolve() != expected_paths[key] for key in paths):
        raise ValueError("preflight_path_drift")
    SAFE.require_exact_inventory(public, static["outputs"]["public_success_allowlist"], private=False)
    SAFE.require_exact_inventory(private, static["outputs"]["private_success_allowlist"], private=True)
    run, verification, completion = (strict_json(paths[key]) for key in ("static_run", "static_verification", "no_result_completion"))
    if run.get("status") != "CompletedAwaitingVerification" or verification.get("status") != "Passed" or verification.get("failed_count") != 0 or completion.get("status") != "Complete" or completion.get("diagnostic_execution_authorized") is not True:
        raise ValueError("preflight_status_drift")
    if completion.get("run") != artifact(paths["static_run"]) or completion.get("verification") != artifact(paths["static_verification"]) or verification.get("run") != artifact(paths["static_run"]):
        raise ValueError("preflight_artifact_chain_drift")
    if any(value.get("method_sha256") != METHOD_SHA256 or value.get("source_snapshot_sha256") != run["source_snapshot_sha256"] for value in (run, verification, completion)):
        raise ValueError("preflight_snapshot_drift")
    return static, completion


def initialize_stage(config_path: Path = DEFAULT_DIAGNOSTIC_CONFIG) -> dict[str, Any]:
    config_path = Path(config_path).resolve()
    started = time.monotonic()
    config = load_config(config_path, "diagnostic")
    require_implementation(config)
    _, completion = require_preflight(config)
    SAFE._environment_record(config, check_process=True)
    SAFE._require_private_ignore()
    public, private = _root(config, private=False, static=False), _root(config, private=True, static=False)
    if os.path.lexists(public) or os.path.lexists(private):
        raise FileExistsError("nonfresh_diagnostic_root")
    if SAFE.shutil.disk_usage(PROJECT_ROOT).free < config["resources"]["minimum_free_disk_bytes"]:
        raise OSError("free_disk_gate_failed")
    with diagnostic_lock():
        before = source_identity_snapshot(config)
        if before["sha256"] != completion["source_snapshot_sha256"]:
            raise ValueError("preflight_source_replay_mismatch")
        matrix_headers, row_headers = inspect_sources(config)
        if source_identity_snapshot(config) != before:
            raise ValueError("minimal_diagnostic_source_drift")
        SAFE._create_root(private, private=True)
        SAFE._create_root(public, private=False)
        input_value = initialized_input(config, config_path, before, matrix_headers, row_headers)
        input_path = private / "input-manifest.json"
        create_json_once(input_path, input_value, private=True)
        claim = initialized_claim(config, config_path, input_path, before)
        validate_public_payload(claim)
        create_json_once(public / "run-claim.json", claim)
        SAFE.require_exact_inventory(public, ["run-claim.json"], private=False)
        SAFE.require_exact_inventory(private, ["input-manifest.json"], private=True)
        _resource_record(started, config)
        return claim


def initialized_input(config: Mapping[str, Any], config_path: Path, snapshot: Mapping[str, Any], matrix_headers: Any, row_headers: Any) -> dict[str, Any]:
    return {**_ids(config), "schema_version": "exp-071-denominator-diagnostic-input-v1", "status": "Initialized", "config": artifact(config_path), "preflight_completion": config["preflight"]["no_result_completion"], "method_sha256": METHOD_SHA256, "source_snapshot": snapshot, "matrix_headers": matrix_headers, "row_contract_headers": row_headers, "access": dict(INITIALIZE_ACCESS)}


def initialized_claim(config: Mapping[str, Any], config_path: Path, input_path: Path, snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {**_ids(config), "schema_version": "exp-071-denominator-diagnostic-claim-v1", "stage": "initialize", "status": "Initialized", "config": artifact(config_path), "input_manifest": artifact(input_path, logical_name="input-manifest.json"), "preflight_completion": config["preflight"]["no_result_completion"], "method_sha256": METHOD_SHA256, "source_snapshot_sha256": snapshot["sha256"], "source_snapshot_scope": SNAPSHOT_SCOPE, "access": dict(INITIALIZE_ACCESS), "claim_boundary": config["claim_boundary"]}


def load_partitions(config: Mapping[str, Any]) -> list[Any]:
    import numpy as np

    source = config["source"]
    with np.load(require_record(source["row_contract"]), allow_pickle=False) as archive:
        if archive.files != ["ordinal", "fold_id", "component_code"]:
            raise ValueError("row_member_drift")
        ordinal, fold_id = archive["ordinal"], archive["fold_id"]
        if ordinal.dtype.str != "<i4" or fold_id.dtype.str != "|i1" or ordinal.shape != (3360,) or fold_id.shape != (3360,):
            raise ValueError("row_schema_drift")
        ordinal, fold_id = np.ascontiguousarray(ordinal), np.ascontiguousarray(fold_id)
    identity = source["row_identity"]
    if hashlib.sha256(ordinal.tobytes()).hexdigest() != identity["ordinal_sha256"] or hashlib.sha256(fold_id.tobytes()).hexdigest() != identity["fold_id_order_sha256"] or not np.array_equal(ordinal, np.arange(3360, dtype=np.int32)):
        raise ValueError("row_identity_drift")
    partitions = [np.sort(ordinal[fold_id == fold]) for fold in FOLDS]
    if any(value.shape != (672,) for value in partitions):
        raise ValueError("heldout_partition_drift")
    return partitions


def source_pair_loader(config: Mapping[str, Any]) -> Any:
    import numpy as np

    records = {item["worker_id"]: item for item in config["source"]["matrices"]}
    opened = {}
    def open_one(worker: str) -> Any:
        if worker not in opened:
            record = records[worker]
            array = np.load(require_record(record["artifact"]), mmap_mode="r", allow_pickle=False)
            if not isinstance(array, np.memmap) or array.flags.writeable or not array.flags.c_contiguous or array.dtype != np.float32 or list(array.shape) != record["shape"]:
                raise ValueError("readonly_matrix_contract_drift")
            opened[worker] = array
        return opened[worker]
    def pair(condition: str, fold: int, ordinals: Any) -> tuple[Any, Any]:
        seed, point = condition.split(":", 1)
        worker = f"m3-{seed}-f{fold}"
        x = np.ascontiguousarray(open_one("base")[ordinals, records["base"]["points"].index(point), :], dtype=np.float64)
        z = np.ascontiguousarray(open_one(worker)[ordinals, records[worker]["points"].index(point), :], dtype=np.float64)
        if x.shape != (672, 2560) or z.shape != x.shape:
            raise ValueError("heldout_slice_shape_drift")
        return x, z
    return pair


def diagnose_stage(config_path: Path = DEFAULT_DIAGNOSTIC_CONFIG) -> dict[str, Any]:
    config_path = Path(config_path).resolve()
    started = time.monotonic()
    config = load_config(config_path, "diagnostic")
    started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    require_implementation(config)
    _, completion = require_preflight(config)
    SAFE._environment_record(config, check_process=True)
    if SAFE.shutil.disk_usage(PROJECT_ROOT).free < config["resources"]["minimum_free_disk_bytes"]:
        raise OSError("free_disk_gate_failed")
    public, private = _root(config, private=False, static=False), _root(config, private=True, static=False)
    SAFE.require_exact_inventory(public, ["run-claim.json"], private=False)
    SAFE.require_exact_inventory(private, ["input-manifest.json"], private=True)
    input_path, claim_path = private / "input-manifest.json", public / "run-claim.json"
    input_value, claim = strict_json(input_path), strict_json(claim_path)
    if input_value.get("status") != "Initialized" or claim.get("status") != "Initialized" or input_value.get("config") != artifact(config_path) or claim.get("config") != artifact(config_path) or claim.get("input_manifest") != artifact(input_path, logical_name="input-manifest.json"):
        raise ValueError("initialized_binding_drift")
    with diagnostic_lock():
        before = source_identity_snapshot(config)
        if before != input_value["source_snapshot"] or before["sha256"] != completion["source_snapshot_sha256"]:
            raise ValueError("initialized_source_replay_mismatch")
        matrix_headers, row_headers = inspect_sources(config)
        if input_value != initialized_input(config, config_path, before, matrix_headers, row_headers) or claim != initialized_claim(config, config_path, input_path, before):
            raise ValueError("initialized_exact_payload_drift")
        localization = first_denominator_failure(load_partitions(config), source_pair_loader(config), budget_check=lambda: _resource_record(started, config))
        validate_localization(localization)
        after = source_identity_snapshot(config)
        if before != after:
            raise ValueError("minimal_diagnostic_source_drift")
        resources = _resource_record(started, config)
        manifest = {**_ids(config), "schema_version": "exp-071-denominator-diagnostic-manifest-v1", "status": "Sealed", "config": artifact(config_path), "input_manifest": artifact(input_path, logical_name="input-manifest.json"), "method_sha256": METHOD_SHA256, "source_before": before, "source_after": after, "localization": localization, "resources": resources, "access": dict(DIAGNOSTIC_ACCESS)}
        manifest_path = private / "diagnostic-manifest.json"
        create_json_once(manifest_path, manifest, private=True)
        private_bytes = SAFE._private_size(private)
        if private_bytes > config["resources"]["private_output_budget_bytes"]:
            raise RuntimeError("private_budget_exceeded")
        report = {**_ids(config), "schema_version": "exp-071-denominator-diagnostic-run-v1", "stage": "diagnose", "status": "CompletedAwaitingVerification", "config": artifact(config_path), "input_manifest": artifact(input_path, logical_name="input-manifest.json"), "diagnostic_manifest": artifact(manifest_path, logical_name="diagnostic-manifest.json"), "method_sha256": METHOD_SHA256, "source_snapshot_sha256": before["sha256"], "source_snapshot_scope": SNAPSHOT_SCOPE, "localization": localization, "resources": {**resources, "private_output_bytes": private_bytes}, "access": dict(DIAGNOSTIC_ACCESS), "diagnostic_complete": False, "exp071_complete": False, "recovery_authorized": False, "exp072_authorized": False, "claim_boundary": config["claim_boundary"]}
        report.update({"tier": config["tier"], "rq_id": config["rq_id"], "execution": execution_record(config, started_at)})
        validate_public_payload(report)
        create_json_once(public / "run.json", report)
        SAFE.require_exact_inventory(public, config["outputs"]["public_diagnosed_allowlist"], private=False)
        SAFE.require_exact_inventory(private, config["outputs"]["private_success_allowlist"], private=True)
        return report


def execution_record(config: Mapping[str, Any], started_at: str) -> dict[str, Any]:
    commit = subprocess.run(["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "-C", str(PROJECT_ROOT), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout)
    return {"started_at_utc": started_at, "ended_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "command": [config["environment"]["python_executable"], IMPLEMENTATION_PATHS["runner"], "--stage", "diagnose", "--config", config["outputs"]["active_config_path"]], "cwd": ".", "git_commit": commit, "git_dirty": dirty}


def _record_failure(config_path: Path, stage: str, error: BaseException) -> None:
    try:
        config = load_config(config_path, "static" if stage == "static" else "diagnostic")
        public = _root(config, private=False, static=stage == "static")
        if os.path.lexists(public):
            files, directories = SAFE.inventory(public)
            if directories or files not in (set(), {"run-claim.json"}):
                return
        else:
            SAFE._create_root(public, private=False)
        code = "failure_not_reproduced" if isinstance(error, RuntimeError) and str(error) == "failure_not_reproduced" else "unexpected_failure"
        create_json_once(public / "failure.json", {**_ids(config), "schema_version": "exp-071-denominator-diagnostic-failure-v1", "stage": stage, "status": "Failed", "error_code": code, "error_type": type(error).__name__, "original_attempt_status": "Failed", "recovery_authorized": False})
    except Exception:
        return


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("static", "initialize", "diagnose"))
    parser.add_argument("--config", type=Path)
    arguments = parser.parse_args(argv)
    config_path = (arguments.config or (DEFAULT_STATIC_CONFIG if arguments.stage == "static" else DEFAULT_DIAGNOSTIC_CONFIG)).resolve()
    try:
        result = {"static": static_stage, "initialize": initialize_stage, "diagnose": diagnose_stage}[arguments.stage](config_path)
    except Exception as error:
        _record_failure(config_path, arguments.stage, error)
        print(json.dumps({"stage": arguments.stage, "status": "Failed"}), file=sys.stderr)
        return 1
    print(json.dumps({"stage": arguments.stage, "status": result["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
