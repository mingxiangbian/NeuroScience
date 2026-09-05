#!/usr/bin/env python3
"""Run the SQMA-001 no-training strict-base readiness preflight.

The runner is intentionally standard-library-only.  It reads public metadata,
hashes registered model assets, and probes runtime metadata.  It never resolves
or opens private train, fold-manifest, Tune, or Confirm artifacts.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import stat
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence


sys.dont_write_bytecode = True


# Loaded only after the config-bound source identity has been verified.
contract: Any = None


CONFIG_RELATIVE_PATH = (
    "projects/selective-qwen-multi-agent-forum-analysis/configs/"
    "sqma-001-strict-base-readiness-preflight.json"
)
OUTPUT_RELATIVE_PATH = (
    "projects/selective-qwen-multi-agent-forum-analysis/runs/"
    "sqma-001-strict-base-readiness-preflight/attempt-1"
)

EXPECTED_TOP_LEVEL_KEYS = {
    "schema_version",
    "experiment_id",
    "tier",
    "stage",
    "registered_at",
    "authorization",
    "implementation",
    "prerequisites",
    "private_source_contract",
    "data",
    "snapshot_contract",
    "model_assets",
    "runtimes",
    "resources",
    "outputs",
    "commands",
}
EXPECTED_AUTHORIZATION = {
    "basis": "User instructed: 行，开始下一步",
    "static_preflight": True,
    "public_fold_metadata_access": True,
    "model_asset_hashing": True,
    "runtime_metadata_probe": True,
    "private_source_open": False,
    "private_rows_parsed": False,
    "model_loading": False,
    "forward": False,
    "training": False,
    "optimizer": False,
    "heldout_logits": False,
    "agent_calls": 0,
    "network": False,
    "tune_access": False,
    "confirm_access": False,
    "validation_access": False,
    "test_access": False,
    "formal_training": False,
    "automatic_next_stage": False,
}
EXPECTED_IMPLEMENTATION_PATHS = {
    "protocol": (
        "projects/selective-qwen-multi-agent-forum-analysis/protocols/"
        "sqma-001-strict-base-readiness-preflight.md"
    ),
    "contract": (
        "projects/selective-qwen-multi-agent-forum-analysis/scripts/"
        "strict_base_contract.py"
    ),
    "runner": (
        "projects/selective-qwen-multi-agent-forum-analysis/scripts/"
        "run_sqma001_strict_base_preflight.py"
    ),
    "verifier": (
        "projects/selective-qwen-multi-agent-forum-analysis/scripts/"
        "verify_sqma001_strict_base_preflight.py"
    ),
    "contract_tests": (
        "projects/selective-qwen-multi-agent-forum-analysis/tests/"
        "test_strict_base_contract.py"
    ),
    "preflight_tests": (
        "projects/selective-qwen-multi-agent-forum-analysis/tests/"
        "test_sqma001_strict_base_preflight.py"
    ),
}
EXPECTED_PREREQUISITE_PATHS = {
    "d0_static_contract": (
        "projects/selective-qwen-multi-agent-forum-analysis/configs/"
        "d0-static-contract.json"
    ),
    "d0_dependency_manifest": (
        "projects/selective-qwen-multi-agent-forum-analysis/configs/"
        "d0-dependency-manifest.json"
    ),
    "shared_model_contract": (
        "projects/llm-forum-text-emotion-recognition/experiments/"
        "stack-overflow-emotion-gold/model-comparison/config.json"
    ),
    "public_fold_manifest": (
        "projects/llm-forum-text-emotion-recognition/experiments/"
        "stack-overflow-emotion-gold/oof-router/runs/"
        "exp-058-fold-manifest-preflight-attempt-2/fold-manifest.public.jsonl"
    ),
    "public_fold_summary": (
        "projects/llm-forum-text-emotion-recognition/experiments/"
        "stack-overflow-emotion-gold/oof-router/runs/"
        "exp-058-fold-manifest-preflight-attempt-2/fold-summary.json"
    ),
    "m1_reference": (
        "projects/llm-forum-text-emotion-recognition/experiments/"
        "stack-overflow-emotion-gold/model-comparison/run_exp051_m1.py"
    ),
    "qwen_primitives": (
        "projects/llm-forum-text-emotion-recognition/experiments/"
        "stack-overflow-emotion-gold/model-comparison/run_preflight.py"
    ),
    "m3_reference": (
        "projects/llm-forum-text-emotion-recognition/experiments/"
        "stack-overflow-emotion-gold/model-comparison/run_exp053_m3_preflight.py"
    ),
    "historical_oof_runner_reference": (
        "projects/llm-forum-text-emotion-recognition/experiments/"
        "stack-overflow-emotion-gold/oof-router/run_exp058_oof_production.py"
    ),
    "historical_oof_verifier_reference": (
        "projects/llm-forum-text-emotion-recognition/experiments/"
        "stack-overflow-emotion-gold/oof-router/verify_exp058_oof_production.py"
    ),
}
EXPECTED_RUNTIME_EXECUTABLES = {
    "m1": "/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python",
    "m3": "/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python",
}
EXPECTED_MODEL_PATHS = {
    "m1": {
        "manifest_path": (
            "projects/llm-forum-text-emotion-recognition/models/"
            "roberta-base/manifest.json"
        ),
        "root_path": (
            "projects/llm-forum-text-emotion-recognition/models/"
            "roberta-base/snapshot"
        ),
    },
    "m3": {
        "manifest_path": (
            "projects/llm-forum-text-emotion-recognition/models/"
            "qwen3-4b/manifest.json"
        ),
        "root_path": (
            "projects/llm-forum-text-emotion-recognition/models/"
            "qwen3-4b/mlx-bf16"
        ),
    },
}
ARTIFACT_KEYS = {"path", "bytes", "sha256"}
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class PreflightError(RuntimeError):
    """Raised when an SQMA-001 readiness gate fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PreflightError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path, label: str) -> dict[str, Any]:
    require(path.is_file(), f"missing {label}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreflightError(f"invalid {label}") from exc
    require(isinstance(value, dict), f"{label} root must be an object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checked_repo_path(repo_root: Path, relative: str, label: str) -> Path:
    require(isinstance(relative, str) and relative, f"invalid {label} path")
    candidate = Path(relative)
    require(not candidate.is_absolute(), f"absolute {label} path is forbidden")
    require(".." not in candidate.parts, f"parent traversal in {label} path is forbidden")
    lexical = repo_root / candidate
    resolved = lexical.resolve()
    require(repo_root == resolved or repo_root in resolved.parents, f"{label} path escapes repository")
    current = repo_root
    for part in candidate.parts:
        current = current / part
        if os.path.lexists(current):
            require(not stat.S_ISLNK(os.lstat(current).st_mode), f"{label} path contains a symlink")
    return lexical


def checked_archive_path(archive_root: Path, relative: str, label: str) -> Path:
    require(isinstance(relative, str) and relative, f"invalid {label} path")
    candidate = Path(relative)
    require(not candidate.is_absolute(), f"absolute {label} path is forbidden")
    require(".." not in candidate.parts, f"parent traversal in {label} path is forbidden")
    lexical = archive_root / candidate
    resolved = lexical.resolve()
    require(
        archive_root == resolved or archive_root in resolved.parents,
        f"{label} path escapes archive root",
    )
    current = archive_root
    for part in candidate.parts:
        current = current / part
        if os.path.lexists(current):
            require(not stat.S_ISLNK(os.lstat(current).st_mode), f"{label} path contains a symlink")
    return lexical


def require_regular_non_symlink(path: Path, label: str) -> os.stat_result:
    require(os.path.lexists(path), f"missing {label}")
    observed = os.lstat(path)
    require(not stat.S_ISLNK(observed.st_mode), f"{label} must not be a symlink")
    require(stat.S_ISREG(observed.st_mode), f"{label} must be a regular file")
    return observed


def validate_artifact_record(
    repo_root: Path,
    name: str,
    value: Any,
    expected_path: str,
) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == ARTIFACT_KEYS, f"invalid {name} record")
    require(value["path"] == expected_path, f"{name} path drift")
    require(type(value["bytes"]) is int and value["bytes"] > 0, f"invalid {name} bytes")
    require(
        isinstance(value["sha256"], str) and SHA256_RE.fullmatch(value["sha256"]),
        f"invalid {name} SHA-256",
    )
    path = checked_repo_path(repo_root, value["path"], name)
    observed = require_regular_non_symlink(path, name)
    require(observed.st_size == value["bytes"], f"{name} byte drift")
    require(sha256(path) == value["sha256"], f"{name} SHA-256 drift")
    return {"path": value["path"], "bytes": value["bytes"], "sha256": value["sha256"]}


def validate_file_records(
    repo_root: Path,
    config: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    implementation = config.get("implementation")
    prerequisites = config.get("prerequisites")
    require(
        isinstance(implementation, dict) and set(implementation) == set(EXPECTED_IMPLEMENTATION_PATHS),
        "implementation record set drift",
    )
    require(
        isinstance(prerequisites, dict) and set(prerequisites) == set(EXPECTED_PREREQUISITE_PATHS),
        "prerequisite record set drift",
    )
    checked_implementation = {
        key: validate_artifact_record(repo_root, f"implementation.{key}", implementation[key], path)
        for key, path in EXPECTED_IMPLEMENTATION_PATHS.items()
    }
    checked_prerequisites = {
        key: validate_artifact_record(repo_root, f"prerequisites.{key}", prerequisites[key], path)
        for key, path in EXPECTED_PREREQUISITE_PATHS.items()
    }
    return checked_implementation, checked_prerequisites


def parse_fit_plan(value: Any) -> tuple[contract.FitSpec, ...]:
    require(isinstance(value, list), "data.full_fit_plan must be an array")
    plans: list[contract.FitSpec] = []
    for index, item in enumerate(value):
        require(
            isinstance(item, dict)
            and set(item) == {"fit_id", "phase", "train_folds", "heldout_folds"},
            f"invalid fit record at index {index}",
        )
        require(
            isinstance(item["fit_id"], str)
            and isinstance(item["phase"], str)
            and isinstance(item["train_folds"], list)
            and isinstance(item["heldout_folds"], list),
            f"invalid fit types at index {index}",
        )
        require(
            all(type(fold) is int for fold in item["train_folds"] + item["heldout_folds"]),
            f"invalid fold type at index {index}",
        )
        plans.append(
            contract.FitSpec(
                item["fit_id"],
                item["phase"],
                tuple(item["train_folds"]),
                tuple(item["heldout_folds"]),
            )
        )
    try:
        return contract.validate_fit_plan(plans)
    except contract.ContractError as exc:
        raise PreflightError(f"fit plan drift: {exc}") from exc


def validate_config_contract(config: Mapping[str, Any]) -> tuple[contract.FitSpec, ...]:
    require(set(config) == EXPECTED_TOP_LEVEL_KEYS, "config top-level schema drift")
    require(
        config.get("schema_version") == "sqma-001-strict-base-readiness-preflight-v1",
        "config schema version drift",
    )
    require(config.get("experiment_id") == "SQMA-001", "experiment identity drift")
    require(config.get("tier") == "Minor", "tier drift")
    require(config.get("stage") == "strict-base-readiness-preflight", "stage drift")
    require(config.get("registered_at") == "2026-09-03", "registration date drift")
    require(config.get("authorization") == EXPECTED_AUTHORIZATION, "authorization drift")

    private_contract = config.get("private_source_contract")
    require(
        isinstance(private_contract, dict)
        and set(private_contract)
        == {
            "identity_source",
            "train_sha256",
            "fold_manifest_private_sha256",
            "paths_resolved_or_opened",
            "bytes_hashed_by_sqma001",
            "rows_parsed",
            "next_gate",
        },
        "private source contract schema drift",
    )
    require(
        private_contract.get("identity_source") == "d0_dependency_manifest_strings_only"
        and private_contract.get("paths_resolved_or_opened") is False
        and private_contract.get("bytes_hashed_by_sqma001") is False
        and private_contract.get("rows_parsed") is False
        and private_contract.get("next_gate") == "independent_dev_scoped_input_materialization",
        "private source access contract drift",
    )

    data = config.get("data")
    require(
        isinstance(data, dict)
        and set(data)
        == {
            "protocol_id",
            "label_order",
            "public_fold_rows",
            "public_fold_components",
            "active_fit_ids",
            "full_fit_plan",
            "active_expected",
            "future_plan_is_declarative_only",
            "fold4_in_fit_plan",
        },
        "data contract schema drift",
    )
    require(data.get("protocol_id") == "DATA-SO-TASK-V1", "protocol ID drift")
    require(tuple(data.get("label_order", ())) == contract.LABELS, "label order drift")
    require(data.get("public_fold_rows") == 3360, "public row count drift")
    require(data.get("public_fold_components") == 3277, "public component count drift")
    require(tuple(data.get("active_fit_ids", ())) == contract.ACTIVE_DEV_FIT_IDS, "active fit drift")
    require(data.get("future_plan_is_declarative_only") is True, "future plan status drift")
    require(data.get("fold4_in_fit_plan") is False, "fold 4 authorization drift")
    plans = parse_fit_plan(data.get("full_fit_plan"))

    snapshots = config.get("snapshot_contract")
    require(
        isinstance(snapshots, dict)
        and set(snapshots)
        == {
            "scopes",
            "producer_full_source_access",
            "first_stage_output_folds",
            "fold3_or_fold4_rows_in_first_stage_outputs",
            "heldout_logits_contains_gold",
            "output_mode",
        },
        "snapshot contract schema drift",
    )
    require(
        snapshots.get("scopes")
        == ["train-capable", "gold-free-inference", "consumer-gold", "heldout-logits"],
        "snapshot scope drift",
    )
    require(snapshots.get("producer_full_source_access") is False, "full-source access drift")
    require(snapshots.get("first_stage_output_folds") == [0, 1, 2], "snapshot fold drift")
    require(snapshots.get("fold3_or_fold4_rows_in_first_stage_outputs") == 0, "future row leak")
    require(snapshots.get("heldout_logits_contains_gold") is False, "heldout gold leak")
    require(snapshots.get("output_mode") == "0600", "private output mode drift")

    resources = config.get("resources")
    require(
        resources
        == {
            "maximum_wall_seconds": 300,
            "maximum_peak_rss_bytes": 1073741824,
            "maximum_public_output_bytes": 16777216,
            "minimum_free_disk_bytes": 21474836480,
            "model_or_mlx_allocations": 0,
            "critical_memory_events": 0,
            "oom_or_kill_events": 0,
            "orphan_processes_after_exit": 0,
        },
        "resource contract drift",
    )
    outputs = config.get("outputs")
    require(isinstance(outputs, dict), "outputs contract missing")
    require(outputs.get("public_attempt_dir") == OUTPUT_RELATIVE_PATH, "output path drift")
    require(
        outputs.get("allowed_files_after_completion")
        == ["run.json", "verification.json", "complete.json"],
        "allowed output file drift",
    )
    require(outputs.get("private_output_dir") is None, "private output is forbidden")
    commands = config.get("commands")
    require(
        commands
        == {
            "run": f"python3 {EXPECTED_IMPLEMENTATION_PATHS['runner']} --config {CONFIG_RELATIVE_PATH}",
            "verify": (
                f"python3 {EXPECTED_IMPLEMENTATION_PATHS['verifier']} --config "
                f"{CONFIG_RELATIVE_PATH}"
            ),
        },
        "command contract drift",
    )
    return plans


def validate_preimport_config(config: Mapping[str, Any]) -> None:
    """Validate the fields needed before it is safe to import the contract."""
    require(set(config) == EXPECTED_TOP_LEVEL_KEYS, "config top-level schema drift")
    require(
        config.get("schema_version") == "sqma-001-strict-base-readiness-preflight-v1"
        and config.get("experiment_id") == "SQMA-001"
        and config.get("tier") == "Minor"
        and config.get("stage") == "strict-base-readiness-preflight"
        and config.get("registered_at") == "2026-09-03",
        "config identity drift",
    )
    require(config.get("authorization") == EXPECTED_AUTHORIZATION, "authorization drift")


def load_verified_contract(repo_root: Path) -> Any:
    module = importlib.import_module("strict_base_contract")
    expected = checked_repo_path(
        repo_root,
        EXPECTED_IMPLEMENTATION_PATHS["contract"],
        "strict-base contract",
    )
    observed = Path(module.__file__).resolve()
    require(observed == expected, "imported strict-base contract path drift")
    return module


def validate_d0_identities(
    repo_root: Path,
    config: Mapping[str, Any],
    prerequisites: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    static_path = checked_repo_path(
        repo_root,
        prerequisites["d0_static_contract"]["path"],
        "D0 static contract",
    )
    dependency_path = checked_repo_path(
        repo_root,
        prerequisites["d0_dependency_manifest"]["path"],
        "D0 dependency manifest",
    )
    static_contract = read_json(static_path, "D0 static contract")
    dependency = read_json(dependency_path, "D0 dependency manifest")
    require(
        static_contract.get("status") == "static_contract_registered_no_execution_authority",
        "D0 static status drift",
    )
    authorization = static_contract.get("authorization")
    require(
        isinstance(authorization, dict) and all(value is False for value in authorization.values()),
        "D0 execution authority drift",
    )
    registered_dependency = static_contract.get("dependency_manifest")
    require(
        isinstance(registered_dependency, dict)
        and registered_dependency.get("path") == prerequisites["d0_dependency_manifest"]["path"]
        and registered_dependency.get("sha256") == prerequisites["d0_dependency_manifest"]["sha256"],
        "D0 dependency binding drift",
    )
    strict = static_contract.get("strict_base_production")
    require(isinstance(strict, dict), "D0 strict-base contract missing")
    require(
        strict.get("validation_access") is False
        and strict.get("test_access") is False
        and strict.get("fold4_access") is False,
        "D0 strict-base access drift",
    )
    first_scope = strict.get("first_formal_scope")
    require(
        isinstance(first_scope, dict)
        and first_scope.get("stage") == "dev_crossfit"
        and first_scope.get("m1_fits") == 3
        and first_scope.get("m3_fits") == 3
        and first_scope.get("allowed_folds") == [0, 1, 2]
        and first_scope.get("tune_or_final_refit_in_same_run") is False,
        "D0 first formal scope drift",
    )

    private = dependency.get("private_dependencies")
    private_contract = config["private_source_contract"]
    require(isinstance(private, dict), "private dependency declaration missing")
    require(
        private.get("train", {}).get("sha256") == private_contract.get("train_sha256")
        and private.get("fold_manifest_private", {}).get("sha256")
        == private_contract.get("fold_manifest_private_sha256"),
        "private identity string drift",
    )
    require(
        private.get("confirm_m1_source", {}).get("producer_access") == "forbidden"
        and private.get("confirm_m3_source", {}).get("producer_access") == "forbidden",
        "Confirm producer access drift",
    )
    return static_contract, dependency


def validate_active_dev(
    config: Mapping[str, Any],
    manifest_path: Path,
    plans: Sequence[contract.FitSpec],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        rows = contract.load_public_fold_manifest(manifest_path)
        aggregate = contract.validate_exp058_public_manifest(rows)
        active = [
            contract.summarize_fit(rows, fit)
            for fit in plans
            if fit.fit_id in contract.ACTIVE_DEV_FIT_IDS
        ]
    except contract.ContractError as exc:
        raise PreflightError(f"public fold contract failed: {exc}") from exc
    require(len(active) == 3, "active Dev fit count drift")
    expected = config["data"].get("active_expected")
    require(isinstance(expected, dict) and set(expected) == set(contract.ACTIVE_DEV_FIT_IDS), "active expected schema drift")
    for fit in active:
        item = expected[fit["fit_id"]]
        require(
            item
            == {
                "training_rows": fit["training"]["rows"],
                "training_components": fit["training"]["components"],
                "heldout_rows": fit["heldout"]["rows"],
                "heldout_components": fit["heldout"]["components"],
            },
            f"active summary drift for {fit['fit_id']}",
        )
        require(fit["m1_schedule"]["steps_per_epoch"] == 84, "M1 steps-per-epoch drift")
        require(fit["m1_schedule"]["warmup_steps"] == 42, "M1 warmup drift")
        require(fit["m1_schedule"]["selected_stop_steps"] == 336, "M1 stop-step drift")
        require(fit["m3_schedule"]["optimizer_steps"] == 2688, "M3 optimizer-step drift")

    public_value = {
        "schema_version": aggregate["schema_version"],
        "rows": aggregate["rows"],
        "components": aggregate["components"],
        "membership_sha256": aggregate["membership_sha256"],
        "active_folds": {
            str(fold): aggregate["folds"][str(fold)] for fold in range(3)
        },
    }
    try:
        contract.assert_public_safe(public_value)
        contract.assert_public_safe(active)
    except contract.ContractError as exc:
        raise PreflightError(f"public privacy gate failed: {exc}") from exc
    return public_value, active


def nested_value(value: Mapping[str, Any], dotted_key: str) -> Any:
    current: Any = value
    for part in dotted_key.split("."):
        require(isinstance(current, dict) and part in current, f"missing manifest inventory key: {dotted_key}")
        current = current[part]
    return current


def validate_model_asset(
    archive_root: Path,
    model_id: str,
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    require(
        set(spec)
        == {
            "repo_id",
            "revision",
            "manifest_path",
            "manifest_bytes",
            "manifest_sha256",
            "root_path",
            "manifest_inventory_key",
            "file_count",
            "total_bytes",
        },
        f"{model_id} model contract schema drift",
    )
    expected_paths = EXPECTED_MODEL_PATHS[model_id]
    require(spec.get("manifest_path") == expected_paths["manifest_path"], f"{model_id} manifest path drift")
    require(spec.get("root_path") == expected_paths["root_path"], f"{model_id} root path drift")
    manifest_path = checked_archive_path(archive_root, spec["manifest_path"], f"{model_id} manifest")
    observed_manifest = require_regular_non_symlink(manifest_path, f"{model_id} manifest")
    require(observed_manifest.st_size == spec["manifest_bytes"], f"{model_id} manifest byte drift")
    require(sha256(manifest_path) == spec["manifest_sha256"], f"{model_id} manifest hash drift")
    manifest = read_json(manifest_path, f"{model_id} model manifest")
    require(manifest.get("repo_id") == spec["repo_id"], f"{model_id} repo drift")
    require(manifest.get("revision") == spec["revision"], f"{model_id} revision drift")
    inventory = nested_value(manifest, spec["manifest_inventory_key"])
    require(isinstance(inventory, list), f"{model_id} inventory must be an array")
    require(len(inventory) == spec["file_count"], f"{model_id} file count drift")
    model_root = checked_archive_path(archive_root, spec["root_path"], f"{model_id} root")
    require(model_root.is_dir(), f"missing {model_id} model root")
    total_bytes = 0
    for index, item in enumerate(inventory):
        require(
            isinstance(item, dict) and set(item) >= {"path", "bytes", "sha256"},
            f"invalid {model_id} inventory record {index}",
        )
        require(
            type(item["bytes"]) is int
            and item["bytes"] >= 0
            and isinstance(item["sha256"], str)
            and SHA256_RE.fullmatch(item["sha256"]),
            f"invalid {model_id} inventory identity {index}",
        )
        file_path = checked_archive_path(model_root, item["path"], f"{model_id} model file")
        observed = require_regular_non_symlink(file_path, f"{model_id} model file")
        require(observed.st_size == item["bytes"], f"{model_id} model file byte drift")
        require(sha256(file_path) == item["sha256"], f"{model_id} model file hash drift")
        total_bytes += item["bytes"]
    require(total_bytes == spec["total_bytes"], f"{model_id} total bytes drift")
    return {
        "repo_id": spec["repo_id"],
        "revision": spec["revision"],
        "manifest_sha256": spec["manifest_sha256"],
        "file_count": len(inventory),
        "total_bytes": total_bytes,
        "all_file_hashes_verified": True,
        "framework_imported": False,
    }


def normalize_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def installed_distribution_versions(site_packages: Path) -> dict[str, str]:
    require(site_packages.is_dir(), "runtime site-packages missing")
    versions: dict[str, str] = {}
    for metadata_path in site_packages.glob("*.dist-info/METADATA"):
        name = None
        version = None
        for line in metadata_path.read_text(encoding="utf-8", errors="strict").splitlines():
            if line.startswith("Name: ") and name is None:
                name = normalize_distribution_name(line[6:])
            elif line.startswith("Version: ") and version is None:
                version = line[9:]
            if name is not None and version is not None:
                break
        if name is not None and version is not None:
            versions[name] = version
    return versions


def probe_runtime(runtime_id: str, spec: Mapping[str, Any]) -> dict[str, Any]:
    require(
        set(spec) == {"executable", "python", "machine", "packages"},
        f"{runtime_id} runtime contract schema drift",
    )
    require(spec.get("executable") == EXPECTED_RUNTIME_EXECUTABLES[runtime_id], f"{runtime_id} executable drift")
    executable = Path(spec["executable"])
    require(executable.is_file() and os.access(executable, os.X_OK), f"{runtime_id} runtime missing")
    resolved = executable.resolve()
    require(resolved.is_file() and os.access(resolved, os.X_OK), f"{runtime_id} runtime target missing")
    probe_code = (
        "import json,platform;"
        "print(json.dumps({'python':platform.python_version(),'machine':platform.machine()},sort_keys=True))"
    )
    probe_env = {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TOKENIZERS_PARALLELISM": "false",
        "OMP_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    completed = subprocess.run(
        [str(executable), "-I", "-S", "-c", probe_code],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        cwd="/",
        env=probe_env,
    )
    require(completed.returncode == 0, f"{runtime_id} isolated runtime probe failed")
    try:
        observed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise PreflightError(f"{runtime_id} runtime probe returned invalid JSON") from exc
    require(
        observed == {"python": spec.get("python"), "machine": spec.get("machine")},
        f"{runtime_id} runtime identity drift",
    )
    python_major_minor = ".".join(spec["python"].split(".")[:2])
    site_packages = executable.parent.parent / "lib" / f"python{python_major_minor}" / "site-packages"
    installed = installed_distribution_versions(site_packages)
    packages = spec.get("packages")
    require(isinstance(packages, dict) and packages, f"{runtime_id} package contract missing")
    for name, expected in packages.items():
        require(
            installed.get(normalize_distribution_name(name)) == expected,
            f"{runtime_id} package drift: {name}",
        )
    return {
        "python": observed["python"],
        "machine": observed["machine"],
        "packages": dict(sorted(packages.items())),
        "isolated": True,
        "site_disabled": True,
        "framework_imported": False,
    }


def peak_rss_bytes() -> int:
    observed = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform.startswith("linux"):
        return observed * 1024
    return observed


def nearest_existing_ancestor(path: Path) -> Path:
    current = path
    while not os.path.lexists(current):
        require(current.parent != current, "no existing output ancestor")
        current = current.parent
    return current


def validate_output_target(repo_root: Path, output_dir: Path, minimum_free: int) -> int:
    require(not os.path.lexists(output_dir), "target output directory already exists")
    ancestor = nearest_existing_ancestor(output_dir.parent)
    current = ancestor
    while True:
        observed = os.lstat(current)
        require(not stat.S_ISLNK(observed.st_mode), "output ancestor must not be a symlink")
        if current == repo_root:
            break
        require(repo_root in current.parents or current == repo_root, "output ancestor escapes repository")
        current = current.parent
    free_bytes = shutil.disk_usage(ancestor).free
    require(free_bytes >= minimum_free, "free disk below SQMA-001 minimum")
    return free_bytes


def artifact_record(repo_root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(repo_root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def write_run_json(output_dir: Path, payload: Mapping[str, Any], maximum_bytes: int) -> int:
    encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    require(len(encoded) <= maximum_bytes, "public run.json exceeds registered byte cap")
    require(not os.path.lexists(output_dir), "target output directory appeared during preflight")
    output_dir.mkdir(parents=True, exist_ok=False)
    run_path = output_dir / "run.json"
    descriptor = os.open(run_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as destination:
        destination.write(encoded)
        destination.flush()
        os.fsync(destination.fileno())
    return len(encoded)


def set_exact_public_output_bytes(payload: dict[str, Any]) -> int:
    prior = -1
    for _ in range(4):
        encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        observed = len(encoded)
        payload["resources"]["public_output_bytes"] = observed
        if observed == prior:
            return observed
        prior = observed
    raise PreflightError("public output byte count did not converge")


def run(config_path_argument: str) -> dict[str, Any]:
    global contract
    started_monotonic = time.monotonic()
    started_at = utc_now()
    repo_root = Path(__file__).resolve().parents[3]
    expected_config_path = checked_repo_path(repo_root, CONFIG_RELATIVE_PATH, "SQMA-001 config")
    supplied_config_path = Path(config_path_argument).expanduser().resolve()
    require(supplied_config_path == expected_config_path, "unexpected config path")
    require_regular_non_symlink(supplied_config_path, "SQMA-001 config")
    config = read_json(supplied_config_path, "SQMA-001 config")
    validate_preimport_config(config)
    _, prerequisites = validate_file_records(repo_root, config)
    contract = load_verified_contract(repo_root)
    plans = validate_config_contract(config)
    validate_d0_identities(repo_root, config, prerequisites)

    output_dir = checked_repo_path(repo_root, config["outputs"]["public_attempt_dir"], "public output")
    free_disk = validate_output_target(
        repo_root,
        output_dir,
        config["resources"]["minimum_free_disk_bytes"],
    )

    public_manifest_path = checked_repo_path(
        repo_root,
        prerequisites["public_fold_manifest"]["path"],
        "public fold manifest",
    )
    public_fold_contract, active_dev_fits = validate_active_dev(config, public_manifest_path, plans)

    model_contract = config.get("model_assets")
    require(
        isinstance(model_contract, dict)
        and set(model_contract) == {"archive_root_env", "audited_archive_root", "m1", "m3"},
        "model asset contract schema drift",
    )
    require(model_contract.get("archive_root_env") == "NEUROSCIENCE_ARCHIVE_ROOT", "archive env drift")
    require(
        model_contract.get("audited_archive_root") == "/Users/phoenix/Assistant/NeuroScience",
        "audited archive root drift",
    )
    archive_value = os.environ.get(
        model_contract["archive_root_env"],
        model_contract.get("audited_archive_root"),
    )
    require(isinstance(archive_value, str) and archive_value, "archive root is unavailable")
    archive_root = Path(archive_value).expanduser().resolve()
    require(archive_root.is_absolute() and archive_root.is_dir(), "archive root is invalid")
    model_assets = {
        model_id: validate_model_asset(archive_root, model_id, model_contract[model_id])
        for model_id in ("m1", "m3")
    }

    runtime_contract = config.get("runtimes")
    require(
        isinstance(runtime_contract, dict) and set(runtime_contract) == {"m1", "m3", "probe"},
        "runtime contract schema drift",
    )
    require(
        runtime_contract.get("probe")
        == "isolated_-I_-S_stdlib_plus_direct_dist_info_no_framework_import",
        "runtime probe contract drift",
    )
    runtimes = {
        runtime_id: probe_runtime(runtime_id, runtime_contract[runtime_id])
        for runtime_id in ("m1", "m3")
    }

    elapsed = time.monotonic() - started_monotonic
    rss = peak_rss_bytes()
    require(elapsed <= config["resources"]["maximum_wall_seconds"], "wall-time cap exceeded")
    require(rss <= config["resources"]["maximum_peak_rss_bytes"], "RSS cap exceeded")
    completed_at = utc_now()
    run_payload: dict[str, Any] = {
        "schema_version": "sqma-001-strict-base-preflight-run-v1",
        "experiment_id": "SQMA-001",
        "tier": "Minor",
        "stage": "strict-base-readiness-preflight",
        "status": "CompletedAwaitingVerification",
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "config": artifact_record(repo_root, supplied_config_path),
        "claim_boundary": (
            "Static Agent-Dev strict-base identities and the three-fit public fold plan were "
            "checked without opening private sources, loading models, training, forwarding, "
            "calling Agents, or producing strict outputs. Formal training remains unauthorized."
        ),
        "public_fold_contract": public_fold_contract,
        "active_dev_fits": active_dev_fits,
        "model_assets": model_assets,
        "runtimes": runtimes,
        "resources": {
            "wall_seconds": elapsed,
            "peak_rss_bytes": rss,
            "free_disk_bytes_before": free_disk,
            "public_output_bytes": 0,
            "maximum_wall_seconds": config["resources"]["maximum_wall_seconds"],
            "maximum_peak_rss_bytes": config["resources"]["maximum_peak_rss_bytes"],
            "minimum_free_disk_bytes": config["resources"]["minimum_free_disk_bytes"],
            "model_or_mlx_allocations": 0,
            "critical_memory_events": 0,
            "oom_or_kill_events": 0,
            "orphan_processes_after_exit": 0,
        },
        "access": {
            "training_executed": False,
            "model_loaded": False,
            "forward_executed": False,
            "private_files_opened": False,
            "private_rows_parsed": False,
            "tune_accessed": False,
            "confirm_opened": False,
            "validation_accessed": False,
            "test_accessed": False,
            "agent_calls": 0,
            "network_accessed": False,
            "files_written_private": False,
            "public_fold_metadata_accessed": True,
            "model_bytes_hashed": True,
            "runtime_metadata_probed": True,
        },
        "next_gate": "independent_dev_scoped_input_materialization",
    }
    contract.assert_public_safe(run_payload)
    maximum_output = config["resources"]["maximum_public_output_bytes"]
    set_exact_public_output_bytes(run_payload)
    contract.assert_public_safe(run_payload)
    written = write_run_json(output_dir, run_payload, maximum_output)
    require(written == run_payload["resources"]["public_output_bytes"], "public output byte count drift")
    return run_payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    arguments = parser.parse_args()
    payload = run(arguments.config)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "training_executed": payload["access"]["training_executed"],
                "model_loaded": payload["access"]["model_loaded"],
                "next_gate": payload["next_gate"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        KeyError,
        TypeError,
        ValueError,
        OSError,
        ImportError,
        subprocess.SubprocessError,
        PreflightError,
    ) as exc:
        print(f"SQMA-001 preflight Failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
