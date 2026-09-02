from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import resource
import shutil
import stat
import subprocess
import time
from typing import Any, Iterable
import zipfile

import numpy as np
from scipy.optimize import minimize_scalar


EXPERIMENT_ID = "EXP-059"
RQ_ID = "RQ-S3"
CONFIG_V2_SCHEMA = "exp-059-calibration-config-v2"
LEGACY_CONFIG_SCHEMAS = {"exp-059-preflight-config-v1", "exp-059-formal-config-v1"}
ATTEMPT_RE = re.compile(r"attempt-[1-9][0-9]*\Z")
REPLICATIONS = {
    "EXP-061": {"model_seed": 43, "run_id": "exp-061-seed-43-router-replication"},
    "EXP-062": {"model_seed": 44, "run_id": "exp-062-seed-44-router-replication"},
}
CANONICAL_IMPLEMENTATION_PATHS = {
    "protocol": "experiments/stack-overflow-emotion-gold/protocols/exp-059-calibration-selective-prediction.md",
    "runner": "experiments/stack-overflow-emotion-gold/oof-router/run_exp059_calibration.py",
    "verifier": "experiments/stack-overflow-emotion-gold/oof-router/verify_exp059_calibration.py",
    "tests": "experiments/stack-overflow-emotion-gold/oof-router/tests/test_exp059_calibration.py",
}
FROZEN_RESOURCES = {
    "formal_wall_seconds": 1800,
    "verification_wall_seconds": 1800,
    "peak_memory_gb": 4.0,
    "api_cost_usd": 0,
}
OOF_FROZEN_RESOURCES = {
    "api_cost_usd": 0,
    "minimum_free_disk_gb": 8.0,
    "m1_peak_process_memory_gb": 8.0,
    "m1_total_wall_hours": 4.0,
    "m3_peak_mlx_memory_gb": 13.0,
    "m3_per_fold_wall_hours": 4.5,
    "m3_total_wall_hours": 22.5,
    "maximum_m1_fold_runs": 5,
    "maximum_m3_fold_runs": 5,
}
OOF_CONFIG_KEYS = {
    "schema_version", "experiment_id", "rq_id", "tier", "stage", "run_id",
    "attempt_id", "authorization", "execution", "seed_contract", "data",
    "implementation", "prerequisites", "outputs", "initialization", "m1", "m3",
    "resources",
}
OOF_FINAL_REQUIRED_CHECKS = {
    "final.public_allowlist", "final.run_status", "final.identity",
    "final.summary_identity", "final.selection_absent", "final.summary_record",
    "final.summary_status", "final.rows", "final.fold_counts", "final.no_metrics",
    "final.no_calibration", "final.no_oracle", "final.no_router",
    "final.no_validation", "final.no_test", "final.train_only",
    "final.run_no_validation", "final.run_no_test_inputs",
    "final.run_no_test_labels", "final.m1_coverage", "final.m3_coverage",
    "final.summary_paired_record", "final.paired_schema",
    "final.paired_source_order", "final.paired_shapes", "final.paired_finite_m1",
    "final.paired_finite_m3", "final.source_order_digest", "final.m1_wall_budget",
    "final.m3_wall_budget", "final.private_root_mode", "final.public_privacy",
} | {
    f"final.{family}.fold_{fold_id}.{suffix}"
    for family in ("m1", "m3")
    for fold_id in range(5)
    for suffix in ("verification", "identity", "top_binding", "verified_table")
}
PREFLIGHT_CORE_KEYS = {
    "experiment_id", "replication_parent_experiment_id", "run_id", "attempt_id",
    "model_seed", "seed_contract", "rq_id", "tier", "implementation", "input",
    "outputs", "data", "cross_fitting", "calibration", "thresholds",
    "selective_prediction", "oracle", "bootstrap", "resources",
}
PREFLIGHT_VERIFICATION_REQUIRED_CHECKS = {
    "preflight.identity",
    "preflight.status",
    "preflight.header_schema",
    "preflight.public_schema",
    "preflight.exp058_passed",
    "preflight.no_values",
    "preflight.no_metrics",
    "preflight.no_analysis",
    "preflight.no_validation",
    "preflight.no_test_inputs",
    "preflight.no_test_labels",
    "preflight.header_only_split",
    "preflight.input_bound",
    "preflight.privacy",
    "preflight.formal_public_absent",
    "preflight.formal_private_absent",
    "preflight.oof_prerequisites",
    "preflight.config",
    "preflight.no_selection",
    "preflight.no_completion",
    "preflight.runtime",
    "preflight.frozen_sources",
    "verification.resource.wall_budget",
    "verification.resource.memory_budget",
    "verification.resource.api_cost",
}
V2_CONFIG_KEYS = {
    "schema_version",
    "experiment_id",
    "replication_parent_experiment_id",
    "run_id",
    "attempt_id",
    "model_seed",
    "seed_contract",
    "rq_id",
    "stage",
    "tier",
    "implementation",
    "prerequisites",
    "input",
    "outputs",
    "data",
    "cross_fitting",
    "calibration",
    "thresholds",
    "selective_prediction",
    "oracle",
    "bootstrap",
    "authorization",
    "resources",
}
FIGURE_METADATA = {"Software": "EXP-059 deterministic verifier-bound figure"}
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
FAMILY_ORDER = ("m1", "m3")
METHOD_ORDER = ("mean_entropy", "max_entropy", "margin")
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-059-calibration-selective-prediction.json"
PUBLIC_SENSITIVE_KEYS = {
    "component_id",
    "component_ids",
    "gold",
    "logits",
    "prediction",
    "predictions",
    "probabilities",
    "sample_id",
    "sample_ids",
    "text",
    "uncertainty_scores",
}


def is_v2(config: dict[str, Any]) -> bool:
    return config.get("schema_version") == CONFIG_V2_SCHEMA


def expected_seed_contract(model_seed: int) -> dict[str, int]:
    return {
        "model_seed": model_seed,
        "python_seed": model_seed,
        "numpy_seed": model_seed,
        "torch_seed": model_seed,
        "m1_batch_seed": model_seed,
        "m3_head_seed": model_seed,
        "m3_batch_seed": model_seed,
        "m3_lora_seed": model_seed + 100_000,
    }


def identity_provenance(config: dict[str, Any]) -> dict[str, Any]:
    if not is_v2(config):
        return {"experiment_id": EXPERIMENT_ID}
    return {
        "experiment_id": EXPERIMENT_ID,
        "replication_parent_experiment_id": config["replication_parent_experiment_id"],
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "model_seed": config["model_seed"],
        "seed_contract": config["seed_contract"],
    }


def expected_outputs(config: dict[str, Any]) -> dict[str, str]:
    run_id = config["run_id"]
    attempt_id = config["attempt_id"]
    public_namespace = f"experiments/stack-overflow-emotion-gold/oof-router/runs/{run_id}"
    private_namespace = f"experiments/stack-overflow-emotion-gold/oof-router/private/{run_id}"
    return {
        "public_namespace": public_namespace,
        "public_attempt_dir": f"{public_namespace}/{attempt_id}",
        "private_namespace": private_namespace,
        "private_attempt_dir": f"{private_namespace}/{attempt_id}",
        "selection_record": f"{public_namespace}/selected-attempt.json",
    }


def _assert_no_symlink(value: str) -> None:
    root = PROJECT_ROOT.resolve()
    current = root
    for part in Path(value).parts:
        current = current / part
        if os.path.lexists(current) and stat.S_ISLNK(os.lstat(current).st_mode):
            raise ValueError(f"Symlink path component is forbidden: {current}")


def output_paths(config: dict[str, Any]) -> dict[str, Path]:
    if not is_v2(config):
        return {
            "preflight": resolve_project(config["outputs"]["preflight_run_dir"]),
            "public_calibration": resolve_project(config["outputs"]["public_run_dir"]),
            "private_calibration": resolve_project(config["outputs"]["private_run_dir"]),
        }
    outputs = config["outputs"]
    public_attempt = resolve_project(outputs["public_attempt_dir"])
    private_attempt = resolve_project(outputs["private_attempt_dir"])
    return {
        "public_namespace": resolve_project(outputs["public_namespace"]),
        "public_attempt": public_attempt,
        "private_namespace": resolve_project(outputs["private_namespace"]),
        "private_attempt": private_attempt,
        "selection": resolve_project(outputs["selection_record"]),
        "preflight": public_attempt / "calibration-preflight",
        "public_calibration": public_attempt / "calibration",
        "private_calibration": private_attempt / "calibration",
        "completion": public_attempt / "calibration-complete.json",
    }


def expected_frozen_source_names(config: dict[str, Any]) -> set[str]:
    names = {"config.json"}
    names.update(Path(record["path"]).name for record in config["implementation"].values())
    if len(names) != len(config["implementation"]) + 1:
        raise ValueError("EXP-059 frozen source basenames must be unique")
    return names


def assert_exact_public_tree(
    run_dir: Path,
    config: dict[str, Any],
    *,
    stage: str,
    verified: bool,
) -> None:
    if stage == "preflight":
        allowed_files = {"run.json"}
    elif stage == "calibration":
        allowed_files = {
            "REPORT.md",
            "abstention-gates.json",
            "bootstrap.json",
            "calibration-metrics.json",
            "calibration-parameters.json",
            "classification-metrics.json",
            "label-retention.csv",
            "random-rejection.csv",
            "reliability-bins.csv",
            "reliability-diagram.png",
            "risk-coverage-curve.png",
            "risk-coverage.csv",
            "oracle-summary.json",
            "run.json",
        }
    else:
        raise ValueError(f"Unknown EXP-059 public stage: {stage}")
    if verified:
        allowed_files |= {"verification.json", "VERIFICATION-SUMMARY.md"}
    run_mode = os.lstat(run_dir).st_mode
    if stat.S_ISLNK(run_mode) or not stat.S_ISDIR(run_mode):
        raise ValueError("EXP-059 public run path must be a real directory")
    entries = {entry.name: entry for entry in os.scandir(run_dir)}
    if set(entries) != allowed_files | {"frozen-sources"}:
        raise ValueError(f"Unexpected EXP-059 public artifacts: {sorted(entries)}")
    for name in allowed_files:
        mode = os.lstat(entries[name].path).st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            raise ValueError(f"EXP-059 public artifact must be a regular file: {name}")
    frozen = entries["frozen-sources"]
    frozen_mode = os.lstat(frozen.path).st_mode
    if stat.S_ISLNK(frozen_mode) or not stat.S_ISDIR(frozen_mode):
        raise ValueError("EXP-059 frozen-sources must be a real directory")
    frozen_entries = {entry.name: entry for entry in os.scandir(frozen.path)}
    if set(frozen_entries) != expected_frozen_source_names(config):
        raise ValueError(f"Unexpected EXP-059 frozen sources: {sorted(frozen_entries)}")
    for name, entry in frozen_entries.items():
        mode = os.lstat(entry.path).st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            raise ValueError(f"EXP-059 frozen source must be a regular file: {name}")


def assert_exact_private_tree(private_dir: Path) -> None:
    directory_mode = os.lstat(private_dir).st_mode
    if stat.S_ISLNK(directory_mode) or not stat.S_ISDIR(directory_mode):
        raise ValueError("EXP-059 private calibration path must be a real directory")
    entries = {entry.name: entry for entry in os.scandir(private_dir)}
    if set(entries) != {"cross-fitted-calibration.npz"}:
        raise ValueError(f"Unexpected EXP-059 private artifacts: {sorted(entries)}")
    file_mode = os.lstat(entries["cross-fitted-calibration.npz"].path).st_mode
    if stat.S_ISLNK(file_mode) or not stat.S_ISREG(file_mode):
        raise ValueError("EXP-059 private calibration artifact must be a regular file")


def _validate_frozen_analysis_contract(config: dict[str, Any]) -> None:
    expected_grid = [round(0.05 + index * 0.01, 2) for index in range(91)]
    if config.get("cross_fitting") != {
        "fold_ids": [0, 1, 2, 3, 4],
        "meta_train_folds": 4,
        "heldout_folds": 1,
        "reuse_exp058_duplicate_component_partition": True,
    }:
        raise ValueError("EXP-059 cross-fitting contract drift")
    if config.get("calibration") != {
        "method": "one_scalar_temperature_per_family",
        "temperature_bounds": [0.05, 20.0],
        "optimizer_parameter": "log_temperature",
        "optimizer_tolerance": 1e-12,
        "optimizer_max_iterations": 1000,
        "ece_bins": 15,
        "minimum_nll_improvement": 1e-6,
        "maximum_brier_worsening": 1e-6,
    }:
        raise ValueError("EXP-059 calibration contract drift")
    thresholds = config.get("thresholds", {})
    if (
        thresholds.get("scope") != "one_global_threshold_per_family_pipeline_and_meta_fold"
        or thresholds.get("grid") != expected_grid
        or thresholds.get("tie_tolerance") != 1e-12
        or thresholds.get("selection_order")
        != ["highest_macro_f1", "lowest_hamming_loss", "closest_to_0_5", "lower_threshold"]
    ):
        raise ValueError("EXP-059 threshold contract drift")
    if config.get("selective_prediction") != {
        "methods": ["mean_entropy", "max_entropy", "margin"],
        "coverages": [1.0, 0.95, 0.9, 0.8, 0.7, 0.6],
        "random_repetitions": 100,
        "random_seed": 20260817,
        "gate_minimum_coverage": 0.8,
        "gate_hamming_relative_reduction": 0.2,
        "gate_max_five_label_macro_drop": 0.01,
        "gate_min_non_surprise_retention": 0.5,
    }:
        raise ValueError("EXP-059 selective-prediction contract drift")
    if config.get("bootstrap") != {
        "unit": "duplicate_component",
        "repetitions": 2000,
        "seed": 20260817,
        "interval": "percentile_95",
    }:
        raise ValueError("EXP-059 bootstrap contract drift")
    if config.get("oracle") != {
        "selection_unit": "whole_six_bit_vector",
        "tie_policy": "m1",
        "minimum_macro_gain": 0.01,
    }:
        raise ValueError("EXP-059 oracle contract drift")


def validate_v2_config(config: dict[str, Any]) -> None:
    if set(config) != V2_CONFIG_KEYS:
        raise ValueError("EXP-059 config-v2 top-level schema drift")
    parent = config.get("replication_parent_experiment_id")
    if parent not in REPLICATIONS:
        raise ValueError("EXP-059 replication parent must be EXP-061 or EXP-062")
    registration = REPLICATIONS[parent]
    if config.get("run_id") != registration["run_id"]:
        raise ValueError("EXP-059 replication run_id drift")
    attempt_id = config.get("attempt_id")
    if not isinstance(attempt_id, str) or ATTEMPT_RE.fullmatch(attempt_id) is None:
        raise ValueError("EXP-059 attempt_id must match attempt-[1-9][0-9]*")
    model_seed = config.get("model_seed")
    if model_seed != registration["model_seed"]:
        raise ValueError("EXP-059 replication model_seed drift")
    if config.get("seed_contract") != expected_seed_contract(model_seed):
        raise ValueError("EXP-059 seed contract drift")
    if config.get("outputs") != expected_outputs(config):
        raise ValueError("EXP-059 replication output path drift")
    for value in config["outputs"].values():
        resolve_project(value)
        _assert_no_symlink(value)
    paths = output_paths(config)
    expected_input = display_path(paths["private_attempt"] / "paired-oof.npz")
    if set(config.get("input", {})) != {"paired_oof"}:
        raise ValueError("EXP-059 replication input inventory drift")
    if config["input"]["paired_oof"].get("path") != expected_input:
        raise ValueError("EXP-059 paired OOF must come from the same private attempt")
    if config.get("data") != {
        "protocol_id": "DATA-SO-TASK-V1",
        "split": "train-oof",
        "rows": 3360,
        "label_order": list(LABEL_ORDER),
    }:
        raise ValueError("EXP-059 data contract drift")
    if set(config.get("implementation", {})) != set(CANONICAL_IMPLEMENTATION_PATHS):
        raise ValueError("EXP-059 implementation inventory drift")
    for name, expected_path in CANONICAL_IMPLEMENTATION_PATHS.items():
        if config["implementation"][name].get("path") != expected_path:
            raise ValueError(f"EXP-059 canonical implementation path drift: {name}")
    required = {"oof_run", "oof_verification", "oof_completion"}
    allowed = required | {"preflight_run", "preflight_verification"}
    prerequisite_keys = set(config.get("prerequisites", {}))
    if not required.issubset(prerequisite_keys) or not prerequisite_keys.issubset(allowed):
        raise ValueError("EXP-059 prerequisite inventory drift")
    public_attempt = display_path(paths["public_attempt"])
    required_paths = {
        "oof_run": f"{public_attempt}/run.json",
        "oof_verification": f"{public_attempt}/verification.json",
        "oof_completion": f"{public_attempt}/oof-complete.json",
    }
    if "preflight_run" in prerequisite_keys:
        required_paths["preflight_run"] = f"{public_attempt}/calibration-preflight/run.json"
    if "preflight_verification" in prerequisite_keys:
        required_paths["preflight_verification"] = (
            f"{public_attempt}/calibration-preflight/verification.json"
        )
    for name, expected in required_paths.items():
        if config["prerequisites"][name].get("path") != expected:
            raise ValueError(f"EXP-059 prerequisite path drift: {name}")
    formal = "preflight_run" in prerequisite_keys or "preflight_verification" in prerequisite_keys
    expected_authorization = {
        "preflight": True,
        "formal_analysis": formal,
        "validation_access": False,
        "test_access": False,
        "model_loading_or_forward": False,
        "router_training": False,
    }
    expected_stage = (
        "cross-fitted-calibration-selective-prediction"
        if formal
        else "calibration-selective-preflight"
    )
    if (prerequisite_keys & {"preflight_run", "preflight_verification"}) not in (
        set(),
        {"preflight_run", "preflight_verification"},
    ):
        raise ValueError("EXP-059 preflight prerequisite pair is incomplete")
    if (
        config.get("tier") != "Major"
        or config.get("stage") != expected_stage
        or config.get("authorization") != expected_authorization
    ):
        raise ValueError("EXP-059 stage/authorization contract drift")
    if config.get("resources") != FROZEN_RESOURCES:
        raise ValueError("EXP-059 frozen resource contract drift")
    _validate_frozen_analysis_contract(config)


def validate_oof_chain(
    config: dict[str, Any],
    records: dict[str, Any],
    oof_run: dict[str, Any],
    verification: dict[str, Any],
    completion: dict[str, Any],
) -> None:
    oof_config_record = oof_run.get("config")
    if not isinstance(oof_config_record, dict):
        raise ValueError("Seed-specific OOF run is missing config provenance")
    oof_config_path = require_record(oof_config_record)
    if artifact(oof_config_path) != oof_config_record:
        raise ValueError("Seed-specific OOF config provenance drift")
    oof_config = json.loads(oof_config_path.read_text(encoding="utf-8"))
    data_section = oof_config.get("data")
    prerequisite_section = oof_config.get("prerequisites")
    if not isinstance(data_section, dict) or not isinstance(prerequisite_section, dict):
        raise ValueError("Seed-specific OOF config data/prerequisite schema drift")
    data_train = data_section.get("train")
    fold_manifest = prerequisite_section.get("fold_manifest")
    if not isinstance(data_train, dict) or not isinstance(fold_manifest, dict):
        raise ValueError("Seed-specific OOF CLI provenance inputs are missing")
    expected_cli = {
        "model_seed": config["model_seed"],
        "run_id": config["run_id"],
        "output_root": config["outputs"]["public_attempt_dir"],
        "expected_fold_manifest_sha256": fold_manifest.get("sha256"),
        "expected_data_manifest_sha256": data_train.get("sha256"),
    }
    expected_identity = {
        "experiment_id": config["replication_parent_experiment_id"],
        "stage": oof_config.get("stage"),
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "model_seed": config["model_seed"],
        "seed_contract": config["seed_contract"],
        "config": oof_config_record,
        "cli_identity": expected_cli,
    }
    if (
        set(oof_config) != OOF_CONFIG_KEYS
        or oof_config.get("schema_version") != "exp-oof-production-config-v2"
        or oof_config.get("experiment_id") != config["replication_parent_experiment_id"]
        or oof_config.get("rq_id") != RQ_ID
        or oof_config.get("tier") != "Major"
        or oof_config.get("stage") != "paired-m1-m3-oof-production"
        or oof_config.get("run_id") != config["run_id"]
        or oof_config.get("attempt_id") != config["attempt_id"]
        or oof_config.get("seed_contract") != config["seed_contract"]
        or oof_config.get("outputs") != config["outputs"]
        or oof_config.get("resources") != OOF_FROZEN_RESOURCES
    ):
        raise ValueError("Seed-specific OOF config contract drift")
    seed_digest = canonical_digest(config["seed_contract"])
    if (
        oof_run.get("schema_version") != "exp-oof-production-run-v2"
        or oof_run.get("status") != "CompletedAwaitingVerification"
        or oof_run.get("seed_contract_sha256") != seed_digest
        or any(oof_run.get(key) != value for key, value in expected_identity.items())
    ):
        raise ValueError("Seed-specific OOF run identity drift")
    verification_keys = {
        "schema_version", "experiment_id", "stage", "run_id", "attempt_id",
        "model_seed", "seed_contract", "config", "cli_identity", "scope",
        "verified_at_utc", "status", "check_count", "passed_count", "failed_count",
        "checks", "independence", "verified_artifacts", "claim_boundary",
    }
    checks = verification.get("checks")
    if not isinstance(checks, list) or any(
        not isinstance(row, dict)
        or set(row) != {"name", "passed", "detail"}
        or not isinstance(row["name"], str)
        or row["passed"] is not True
        for row in checks
    ):
        raise ValueError("Seed-specific OOF final verifier check schema drift")
    check_names = [row["name"] for row in checks]
    try:
        verified_at = datetime.fromisoformat(verification["verified_at_utc"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Seed-specific OOF verification timestamp drift") from error
    if (
        set(verification) != verification_keys
        or verification.get("schema_version") != "exp-oof-final-verification-v2"
        or verification.get("scope") != "final"
        or verification.get("status") != "Passed"
        or verification.get("check_count") != len(checks)
        or verification.get("passed_count") != len(checks)
        or verification.get("failed_count") != 0
        or len(check_names) != len(set(check_names))
        or not OOF_FINAL_REQUIRED_CHECKS.issubset(check_names)
        or verified_at.tzinfo is None
        or verification.get("independence")
        != {
            "runner_imported": False,
            "model_libraries_imported": False,
            "all_fold_tables_recomputed": True,
            "paired_table_recomputed": True,
        }
        or verification.get("claim_boundary")
        != "Verified paired train OOF logits only; calibration and routing remain separate experiments."
        or any(verification.get(key) != value for key, value in expected_identity.items())
    ):
        raise ValueError("Seed-specific OOF final verifier contract drift")
    paired = config["input"]["paired_oof"]
    summary_record = oof_run.get("artifacts", {}).get("paired_oof_summary")
    expected_summary_path = display_path(
        output_paths(config)["public_attempt"] / "paired-oof-summary.json"
    )
    if (
        not isinstance(summary_record, dict)
        or summary_record.get("path") != expected_summary_path
        or artifact(require_record(summary_record)) != summary_record
        or oof_run.get("artifacts", {}).get("paired_oof_private") != paired
    ):
        raise ValueError("Seed-specific OOF run artifact provenance drift")
    verified = verification.get("verified_artifacts")
    if not isinstance(verified, dict) or set(verified) != {
        "config", "run", "summary", "paired_oof_private", "fold_runs",
        "fold_verifications",
    }:
        raise ValueError("Seed-specific OOF verified artifact inventory drift")
    if (
        verified.get("config") != oof_config_record
        or verified.get("run") != records["oof_run"]
        or verified.get("summary") != summary_record
        or verified.get("paired_oof_private") != paired
    ):
        raise ValueError("Seed-specific OOF verified artifact provenance drift")
    for map_name, filename in (
        ("fold_runs", "run.json"),
        ("fold_verifications", "verification.json"),
    ):
        mapping = verified.get(map_name)
        if not isinstance(mapping, dict) or set(mapping) != {"m1", "m3"}:
            raise ValueError(f"Seed-specific OOF {map_name} inventory drift")
        for family in ("m1", "m3"):
            if not isinstance(mapping[family], dict) or set(mapping[family]) != {
                str(index) for index in range(5)
            }:
                raise ValueError(f"Seed-specific OOF {map_name}.{family} inventory drift")
            for fold_id, record in mapping[family].items():
                expected_path = display_path(
                    output_paths(config)["public_attempt"]
                    / f"fold-{fold_id}"
                    / family
                    / filename
                )
                if (
                    not isinstance(record, dict)
                    or record.get("path") != expected_path
                    or artifact(require_record(record)) != record
                ):
                    raise ValueError(f"Seed-specific OOF {map_name}.{family}.{fold_id} drift")
    completion_artifacts = completion.get("artifacts")
    expected_completion_artifacts = {
        "run": records["oof_run"],
        "summary": summary_record,
        "final_verification": records["oof_verification"],
        "paired_oof_private": paired,
    }
    completion_keys = {
        "schema_version", "experiment_id", "stage", "run_id", "attempt_id",
        "model_seed", "seed_contract", "seed_contract_sha256", "config",
        "cli_identity", "status", "completed_at_utc", "artifacts", "next_gate",
        "claim_boundary",
    }
    try:
        completed_at = datetime.fromisoformat(completion["completed_at_utc"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Seed-specific OOF completion timestamp drift") from error
    if (
        set(completion) != completion_keys
        or completion.get("schema_version") != "exp-oof-completion-v2"
        or completion.get("status") != "Complete"
        or completion.get("seed_contract_sha256") != seed_digest
        or completion_artifacts != expected_completion_artifacts
        or completed_at.tzinfo is None
        or completion.get("next_gate")
        != "Seed-specific EXP-059 and identity-nested EXP-060 must pass before namespace selection."
        or completion.get("claim_boundary")
        != "Completes one verified train-only paired OOF stage; this is not final pipeline selection."
        or any(completion.get(key) != value for key, value in expected_identity.items())
    ):
        raise ValueError("Seed-specific OOF completion contract drift")
    for record in iter_records(verified):
        require_record(record)


def validate_oof_prerequisites(config: dict[str, Any]) -> None:
    if not is_v2(config):
        return
    records = config["prerequisites"]
    oof_run = json.loads(require_record(records["oof_run"]).read_text(encoding="utf-8"))
    verification = json.loads(
        require_record(records["oof_verification"]).read_text(encoding="utf-8")
    )
    completion = json.loads(
        require_record(records["oof_completion"]).read_text(encoding="utf-8")
    )
    validate_oof_chain(config, records, oof_run, verification, completion)


def validate_preflight_verification_document(
    verification: dict[str, Any],
    config: dict[str, Any],
    config_record: dict[str, Any],
) -> None:
    expected_keys = {
        "schema_version",
        *identity_provenance(config),
        "rq_id",
        "scope",
        "status",
        "verified_at_utc",
        "passed_count",
        "failed_count",
        "checks",
        "resources",
        "config",
        "verified_artifacts",
    }
    if set(verification) != expected_keys:
        raise ValueError("EXP-059 preflight verification top-level schema drift")
    try:
        verified_at = datetime.fromisoformat(verification["verified_at_utc"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("EXP-059 preflight verification timestamp drift") from error
    checks = verification.get("checks")
    if not isinstance(checks, list) or any(
        not isinstance(row, dict)
        or set(row) != {"name", "passed", "detail"}
        or not isinstance(row["name"], str)
        or row["passed"] is not True
        for row in checks
    ):
        raise ValueError("EXP-059 preflight verification check schema drift")
    check_names = [row["name"] for row in checks]
    resources = verification.get("resources")
    if (
        verification.get("schema_version") != "exp-059-verification-v2"
        or verification.get("rq_id") != RQ_ID
        or verification.get("scope") != "preflight"
        or verification.get("status") != "Passed"
        or verification.get("passed_count") != len(checks)
        or verification.get("failed_count") != 0
        or len(check_names) != len(set(check_names))
        or not PREFLIGHT_VERIFICATION_REQUIRED_CHECKS.issubset(check_names)
        or verified_at.tzinfo is None
        or any(
            verification.get(key) != value
            for key, value in identity_provenance(config).items()
        )
        or verification.get("config") != config_record
        or not isinstance(resources, dict)
        or set(resources) != {"wall_seconds", "peak_process_rss_gb", "api_cost_usd"}
        or not isinstance(resources.get("wall_seconds"), (int, float))
        or isinstance(resources.get("wall_seconds"), bool)
        or not math.isfinite(float(resources.get("wall_seconds", math.inf)))
        or resources.get("wall_seconds", -1) < 0
        or resources.get("wall_seconds", math.inf)
        > float(config["resources"]["verification_wall_seconds"])
        or not isinstance(resources.get("peak_process_rss_gb"), (int, float))
        or isinstance(resources.get("peak_process_rss_gb"), bool)
        or not math.isfinite(float(resources.get("peak_process_rss_gb", math.inf)))
        or resources.get("peak_process_rss_gb", -1) < 0
        or resources.get("peak_process_rss_gb", math.inf)
        > float(config["resources"]["peak_memory_gb"])
        or resources.get("api_cost_usd") != 0
    ):
        raise ValueError("EXP-059 preflight verification contract drift")
    verified = verification.get("verified_artifacts")
    if (
        not isinstance(verified, dict)
        or set(verified) != {"config", "run", "paired_oof"}
        or verified.get("config") != config_record
    ):
        raise ValueError("EXP-059 preflight verified artifact inventory drift")
    for record in iter_records(verified):
        require_record(record)


def validate_preflight_prerequisites(config: dict[str, Any]) -> None:
    if not is_v2(config):
        return
    records = config["prerequisites"]
    if not {"preflight_run", "preflight_verification"}.issubset(records):
        raise ValueError("Formal EXP-059 requires a complete preflight pair")
    run_path = require_record(records["preflight_run"])
    run = json.loads(run_path.read_text(encoding="utf-8"))
    verification = json.loads(
        require_record(records["preflight_verification"]).read_text(encoding="utf-8")
    )
    validate_preflight_verification_document(verification, config, run.get("config"))
    identity = identity_provenance(config)
    verified = verification.get("verified_artifacts", {})
    try:
        frozen_sources = expected_frozen_source_records(run_path.parent, config, run["config"])
        frozen_config = json.loads(
            (run_path.parent / "frozen-sources" / "config.json").read_text(
                encoding="utf-8"
            )
        )
        validate_v2_config(frozen_config)
        expected_oof_prerequisites = {
            name: config["prerequisites"][name]
            for name in ("oof_run", "oof_verification", "oof_completion")
        }
        core_equivalent = all(
            frozen_config.get(name) == config.get(name) for name in PREFLIGHT_CORE_KEYS
        )
    except (KeyError, OSError, TypeError, ValueError):
        frozen_sources = None
        frozen_config = None
        expected_oof_prerequisites = None
        core_equivalent = False
    if (
        run.get("schema_version") != "exp-059-preflight-run-v2"
        or run.get("status") != "CompletedAwaitingVerification"
        or any(run.get(key) != value for key, value in identity.items())
        or run.get("input") != config["input"]["paired_oof"]
        or verification.get("schema_version") != "exp-059-verification-v2"
        or verification.get("scope") != "preflight"
        or verification.get("status") != "Passed"
        or verification.get("failed_count") != 0
        or any(verification.get(key) != value for key, value in identity.items())
        or verification.get("config") != run.get("config")
        or verified.get("config") != run.get("config")
        or verified.get("run") != records["preflight_run"]
        or verified.get("paired_oof") != config["input"]["paired_oof"]
        or frozen_sources is None
        or run.get("frozen_sources") != frozen_sources
        or frozen_config is None
        or frozen_config.get("schema_version") != CONFIG_V2_SCHEMA
        or frozen_config.get("prerequisites") != expected_oof_prerequisites
        or not core_equivalent
    ):
        raise ValueError("EXP-059 preflight provenance chain drift")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def resolve_project(value: str) -> Path:
    if Path(value).is_absolute():
        raise ValueError(f"Project-relative path must not be absolute: {value}")
    _assert_no_symlink(value)
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Project-relative path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(resolved)


def artifact(path: Path) -> dict[str, Any]:
    return {
        "path": display_path(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def atomic_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    if private:
        os.chmod(temporary, 0o600)
    temporary.replace(path)
    if private:
        os.chmod(path, 0o600)


def atomic_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def atomic_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as target:
        np.savez_compressed(target, **arrays)
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)


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


def require_record(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Frozen artifact drift: {path}")
    return path


def expected_frozen_source_records(
    run_dir: Path,
    config: dict[str, Any],
    config_record: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    frozen_dir = run_dir / "frozen-sources"
    frozen_mode = os.lstat(frozen_dir).st_mode
    if stat.S_ISLNK(frozen_mode) or not stat.S_ISDIR(frozen_mode):
        raise ValueError("EXP-059 frozen-sources must be a real directory")
    expected_names = expected_frozen_source_names(config)
    entries = {entry.name: entry for entry in os.scandir(frozen_dir)}
    if set(entries) != expected_names:
        raise ValueError("EXP-059 frozen source inventory drift")
    if any(
        stat.S_ISLNK(os.lstat(entry.path).st_mode)
        or not stat.S_ISREG(os.lstat(entry.path).st_mode)
        for entry in entries.values()
    ):
        raise ValueError("EXP-059 frozen sources must be regular files")
    records = {"config": artifact(frozen_dir / "config.json")}
    if {
        key: records["config"][key] for key in ("bytes", "sha256")
    } != {key: config_record[key] for key in ("bytes", "sha256")}:
        raise ValueError("EXP-059 frozen config does not bind the recorded config")
    for name, source_record in config["implementation"].items():
        source_path = require_record(source_record)
        frozen_path = frozen_dir / source_path.name
        frozen_record = artifact(frozen_path)
        if {
            key: frozen_record[key] for key in ("bytes", "sha256")
        } != {key: source_record[key] for key in ("bytes", "sha256")}:
            raise ValueError(f"EXP-059 frozen implementation drift: {name}")
        records[name] = frozen_record
    return records


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


def validate_legacy_archive(config_path: Path, config: dict[str, Any]) -> None:
    if config.get("schema_version") not in LEGACY_CONFIG_SCHEMAS:
        raise ValueError("Unsupported EXP-059 config schema")
    output_key = (
        "preflight_run_dir"
        if config["schema_version"] == "exp-059-preflight-config-v1"
        else "public_run_dir"
    )
    run_dir = resolve_project(config["outputs"][output_key])
    run_path = run_dir / "run.json"
    verification_path = run_dir / "verification.json"
    if not run_path.is_file() or not verification_path.is_file():
        raise PermissionError("Legacy EXP-059 may only be opened as an existing sealed archive")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if (
        run.get("experiment_id") != EXPERIMENT_ID
        or run.get("status") != "CompletedAwaitingVerification"
        or verification.get("experiment_id") != EXPERIMENT_ID
        or verification.get("status") != "Passed"
        or verification.get("failed_count") != 0
    ):
        raise ValueError("Legacy EXP-059 archive is not sealed and Passed")
    frozen = run.get("frozen_sources", {})
    config_record = frozen.get("config")
    current_config = artifact(config_path)
    if (
        not isinstance(config_record, dict)
        or config_record.get("bytes") != current_config["bytes"]
        or config_record.get("sha256") != current_config["sha256"]
        or artifact(require_record(config_record)) != config_record
    ):
        raise ValueError("Legacy EXP-059 frozen config provenance drift")
    for name, source_record in config.get("implementation", {}).items():
        frozen_record = frozen.get(name)
        if (
            not isinstance(frozen_record, dict)
            or frozen_record.get("bytes") != source_record.get("bytes")
            or frozen_record.get("sha256") != source_record.get("sha256")
            or artifact(require_record(frozen_record)) != frozen_record
        ):
            raise ValueError(f"Legacy EXP-059 frozen source provenance drift: {name}")


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID or config.get("rq_id") != RQ_ID:
        raise ValueError("EXP-059 config identity drift")
    if is_v2(config):
        validate_v2_config(config)
    if tuple(config["data"]["label_order"]) != LABEL_ORDER:
        raise ValueError("Label order drift")
    if is_v2(config):
        for section in ("implementation", "prerequisites", "input"):
            for record in iter_records(config.get(section, {})):
                require_record(record)
    else:
        validate_legacy_archive(path, config)
        config["_archive_only"] = True
    if config["authorization"]["validation_access"] or config["authorization"]["test_access"]:
        raise ValueError("EXP-059 config must forbid validation and test")
    if is_v2(config) and (
        config["authorization"].get("model_loading_or_forward") is not False
        or config["authorization"].get("router_training") is not False
    ):
        raise ValueError("EXP-059 diagnostics may not load models or train a router")
    return config


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return {"commit": commit, "dirty": bool(status), "dirty_path_count": len(status)}


def peak_rss_gb() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / 1e9 if platform.system() == "Darwin" else value * 1024 / 1e9


def dependency_versions() -> dict[str, str]:
    result = {"python": platform.python_version()}
    for name in ("numpy", "scipy", "matplotlib", "scikit-learn"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = "not-installed"
    return result


def npz_header_schema(path: Path) -> dict[str, dict[str, Any]]:
    schema: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(path) as archive:
        for member in sorted(archive.namelist()):
            if not member.endswith(".npy"):
                continue
            with archive.open(member) as source:
                version = np.lib.format.read_magic(source)
                if version == (1, 0):
                    shape, fortran, dtype = np.lib.format.read_array_header_1_0(source)
                elif version == (2, 0):
                    shape, fortran, dtype = np.lib.format.read_array_header_2_0(source)
                else:
                    shape, fortran, dtype = np.lib.format._read_array_header(source, version)
            schema[Path(member).stem] = {
                "shape": list(shape),
                "dtype": str(dtype),
                "fortran_order": bool(fortran),
            }
    return schema


def expected_input_schema() -> dict[str, dict[str, Any]]:
    return {
        "sample_ids": {"shape": [3360], "dtype": "<U31", "fortran_order": False},
        "component_ids": {"shape": [3360], "dtype": "<U34", "fortran_order": False},
        "fold_ids": {"shape": [3360], "dtype": "int8", "fortran_order": False},
        "gold": {"shape": [3360, 6], "dtype": "uint8", "fortran_order": False},
        "m1_logits": {"shape": [3360, 6], "dtype": "float32", "fortran_order": False},
        "m3_logits": {"shape": [3360, 6], "dtype": "float32", "fortran_order": False},
        "character_lengths": {"shape": [3360], "dtype": "int32", "fortran_order": False},
        "m1_token_lengths": {"shape": [3360], "dtype": "int32", "fortran_order": False},
        "m3_token_lengths": {"shape": [3360], "dtype": "int32", "fortran_order": False},
        "m1_fold_run_sha256": {"shape": [3360], "dtype": "<U64", "fortran_order": False},
        "m3_fold_run_sha256": {"shape": [3360], "dtype": "<U64", "fortran_order": False},
    }


def public_schema_records(schema: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "array_name": name,
            "shape": details["shape"],
            "dtype": details["dtype"],
            "fortran_order": details["fortran_order"],
        }
        for name, details in sorted(schema.items())
    ]


def freeze_sources(run_dir: Path, config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    frozen = run_dir / "frozen-sources"
    frozen.mkdir(parents=True)
    records: dict[str, Any] = {}
    sources = {"config": config_path}
    for name, record in config["implementation"].items():
        sources[name] = require_record(record)
    for name, source in sources.items():
        target = frozen / ("config.json" if name == "config" else source.name)
        shutil.copy2(source, target)
        records[name] = artifact(target)
    return records


def sigmoid(value: np.ndarray) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    result = np.empty_like(array)
    positive = array >= 0
    result[positive] = 1.0 / (1.0 + np.exp(-array[positive]))
    exp_value = np.exp(array[~positive])
    result[~positive] = exp_value / (1.0 + exp_value)
    return result


def bce_with_logits(logits: np.ndarray, gold: np.ndarray) -> float:
    x = np.asarray(logits, dtype=np.float64)
    y = np.asarray(gold, dtype=np.float64)
    return float(np.mean(np.maximum(x, 0.0) - x * y + np.log1p(np.exp(-np.abs(x)))))


def probability_nll(probabilities: np.ndarray, gold: np.ndarray) -> float:
    p = np.clip(np.asarray(probabilities, dtype=np.float64), 1e-12, 1.0 - 1e-12)
    y = np.asarray(gold, dtype=np.float64)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log1p(-p)))


def brier_score(probabilities: np.ndarray, gold: np.ndarray) -> float:
    return float(np.mean((np.asarray(probabilities, dtype=np.float64) - gold) ** 2))


def fit_temperature(
    logits: np.ndarray, gold: np.ndarray, bounds: tuple[float, float], tolerance: float, maxiter: int
) -> dict[str, Any]:
    log_bounds = (math.log(bounds[0]), math.log(bounds[1]))

    def objective(log_temperature: float) -> float:
        return bce_with_logits(logits / math.exp(log_temperature), gold)

    result = minimize_scalar(
        objective,
        bounds=log_bounds,
        method="bounded",
        options={"xatol": tolerance, "maxiter": maxiter},
    )
    temperature = float(math.exp(float(result.x)))
    boundary_tolerance = 1e-6
    return {
        "temperature": temperature,
        "objective_nll": float(result.fun),
        "success": bool(result.success),
        "iterations": int(result.nfev),
        "at_lower_bound": temperature <= bounds[0] * (1.0 + boundary_tolerance),
        "at_upper_bound": temperature >= bounds[1] * (1.0 - boundary_tolerance),
    }


def classification_metrics(gold: np.ndarray, prediction: np.ndarray) -> dict[str, Any]:
    y = np.asarray(gold, dtype=np.uint8)
    pred = np.asarray(prediction, dtype=np.uint8)
    if y.shape != pred.shape or y.ndim != 2 or y.shape[1] != len(LABEL_ORDER):
        raise ValueError("Classification metric shape mismatch")
    per_label: dict[str, Any] = {}
    f1_values: list[float] = []
    tp_total = fp_total = fn_total = 0
    for index, label in enumerate(LABEL_ORDER):
        tp = int(np.sum((y[:, index] == 1) & (pred[:, index] == 1)))
        fp = int(np.sum((y[:, index] == 0) & (pred[:, index] == 1)))
        fn = int(np.sum((y[:, index] == 1) & (pred[:, index] == 0)))
        support = int(np.sum(y[:, index] == 1))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "support": support,
            "predicted_positive": int(np.sum(pred[:, index] == 1)),
        }
        f1_values.append(float(f1))
        tp_total += tp
        fp_total += fp
        fn_total += fn
    micro_precision = tp_total / (tp_total + fp_total) if tp_total + fp_total else 0.0
    micro_recall = tp_total / (tp_total + fn_total) if tp_total + fn_total else 0.0
    micro_f1 = (
        2.0 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if micro_precision + micro_recall
        else 0.0
    )
    five = [value for index, value in enumerate(f1_values) if index != 2]
    return {
        "rows": int(y.shape[0]),
        "macro_f1": float(np.mean(f1_values)),
        "five_label_macro_f1": float(np.mean(five)),
        "micro_f1": float(micro_f1),
        "hamming_loss": float(np.mean(y != pred)),
        "subset_accuracy": float(np.mean(np.all(y == pred, axis=1))),
        "subset_error": float(1.0 - np.mean(np.all(y == pred, axis=1))),
        "per_label": per_label,
    }


def select_threshold(probabilities: np.ndarray, gold: np.ndarray, grid: list[float]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for threshold in grid:
        metrics = classification_metrics(gold, (probabilities >= threshold).astype(np.uint8))
        candidates.append(
            {
                "threshold": float(threshold),
                "macro_f1": metrics["macro_f1"],
                "hamming_loss": metrics["hamming_loss"],
            }
        )
    best_macro = max(item["macro_f1"] for item in candidates)
    tied = [item for item in candidates if abs(item["macro_f1"] - best_macro) <= 1e-12]
    best_hamming = min(item["hamming_loss"] for item in tied)
    tied = [item for item in tied if abs(item["hamming_loss"] - best_hamming) <= 1e-12]
    tied.sort(key=lambda item: (abs(item["threshold"] - 0.5), item["threshold"]))
    return tied[0]


def equal_frequency_bins(
    probabilities: np.ndarray, gold: np.ndarray, bins: int
) -> tuple[float, list[dict[str, Any]]]:
    p = np.asarray(probabilities, dtype=np.float64).reshape(-1)
    y = np.asarray(gold, dtype=np.float64).reshape(-1)
    order = np.argsort(p, kind="stable")
    records: list[dict[str, Any]] = []
    weighted_gap = 0.0
    for bin_index, indices in enumerate(np.array_split(order, bins), start=1):
        confidence = float(np.mean(p[indices]))
        frequency = float(np.mean(y[indices]))
        gap = abs(confidence - frequency)
        weighted_gap += len(indices) * gap
        records.append(
            {
                "bin": bin_index,
                "count": int(len(indices)),
                "mean_confidence": confidence,
                "empirical_positive_rate": frequency,
                "absolute_gap": float(gap),
                "minimum_probability": float(np.min(p[indices])),
                "maximum_probability": float(np.max(p[indices])),
            }
        )
    return float(weighted_gap / len(order)), records


def calibration_metrics(
    probabilities: np.ndarray, gold: np.ndarray, bins: int
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    micro_ece, reliability = equal_frequency_bins(probabilities, gold, bins)
    classwise = [equal_frequency_bins(probabilities[:, index], gold[:, index], bins)[0] for index in range(6)]
    return (
        {
            "nll": probability_nll(probabilities, gold),
            "brier": brier_score(probabilities, gold),
            "micro_ece": micro_ece,
            "macro_classwise_ece": float(np.mean(classwise)),
        },
        reliability,
    )


def cross_fit_family(
    logits: np.ndarray,
    gold: np.ndarray,
    fold_ids: np.ndarray,
    config: dict[str, Any],
) -> dict[str, Any]:
    settings = config["calibration"]
    threshold_grid = [float(value) for value in config["thresholds"]["grid"]]
    raw_probabilities = sigmoid(logits)
    temperature_probabilities = np.empty_like(raw_probabilities)
    raw_thresholds = np.empty(len(gold), dtype=np.float64)
    temperature_thresholds = np.empty(len(gold), dtype=np.float64)
    fold_fits: list[dict[str, Any]] = []
    for fold_id in config["cross_fitting"]["fold_ids"]:
        meta_train = fold_ids != fold_id
        heldout = fold_ids == fold_id
        fit = fit_temperature(
            logits[meta_train],
            gold[meta_train],
            tuple(settings["temperature_bounds"]),
            float(settings["optimizer_tolerance"]),
            int(settings["optimizer_max_iterations"]),
        )
        temperature = fit["temperature"]
        temperature_probabilities[heldout] = sigmoid(logits[heldout] / temperature)
        raw_selection = select_threshold(raw_probabilities[meta_train], gold[meta_train], threshold_grid)
        temperature_train = sigmoid(logits[meta_train] / temperature)
        temperature_selection = select_threshold(temperature_train, gold[meta_train], threshold_grid)
        raw_thresholds[heldout] = raw_selection["threshold"]
        temperature_thresholds[heldout] = temperature_selection["threshold"]
        fold_fits.append(
            {
                "fold_id": int(fold_id),
                "meta_train_rows": int(np.sum(meta_train)),
                "heldout_rows": int(np.sum(heldout)),
                "temperature_fit": fit,
                "raw_threshold_selection": raw_selection,
                "temperature_threshold_selection": temperature_selection,
            }
        )

    raw_calibration, raw_reliability = calibration_metrics(
        raw_probabilities, gold, int(settings["ece_bins"])
    )
    temperature_calibration, temperature_reliability = calibration_metrics(
        temperature_probabilities, gold, int(settings["ece_bins"])
    )
    nll_delta = temperature_calibration["nll"] - raw_calibration["nll"]
    brier_delta = temperature_calibration["brier"] - raw_calibration["brier"]
    accepted = (
        nll_delta <= -float(settings["minimum_nll_improvement"])
        and brier_delta <= float(settings["maximum_brier_worsening"])
    )
    selected_probabilities = temperature_probabilities if accepted else raw_probabilities
    selected_thresholds = temperature_thresholds if accepted else raw_thresholds
    raw_crossfit_prediction = (raw_probabilities >= raw_thresholds[:, None]).astype(np.uint8)
    temperature_crossfit_prediction = (
        temperature_probabilities >= temperature_thresholds[:, None]
    ).astype(np.uint8)
    selected_prediction = (
        temperature_crossfit_prediction if accepted else raw_crossfit_prediction
    )
    full_fit = fit_temperature(
        logits,
        gold,
        tuple(settings["temperature_bounds"]),
        float(settings["optimizer_tolerance"]),
        int(settings["optimizer_max_iterations"]),
    )
    final_temperature = full_fit["temperature"] if accepted else 1.0
    final_probabilities = sigmoid(logits / final_temperature)
    final_threshold = select_threshold(final_probabilities, gold, threshold_grid)
    return {
        "raw_probabilities": raw_probabilities,
        "temperature_probabilities": temperature_probabilities,
        "selected_probabilities": selected_probabilities,
        "raw_thresholds": raw_thresholds,
        "temperature_thresholds": temperature_thresholds,
        "selected_thresholds": selected_thresholds,
        "raw_crossfit_prediction": raw_crossfit_prediction,
        "temperature_crossfit_prediction": temperature_crossfit_prediction,
        "selected_prediction": selected_prediction,
        "fold_fits": fold_fits,
        "raw_calibration": raw_calibration,
        "temperature_calibration": temperature_calibration,
        "raw_reliability": raw_reliability,
        "temperature_reliability": temperature_reliability,
        "temperature_accepted": bool(accepted),
        "calibration_deltas": {"nll": float(nll_delta), "brier": float(brier_delta)},
        "full_fit": full_fit,
        "final_temperature": float(final_temperature),
        "final_threshold_selection": final_threshold,
        "classification": {
            "raw_fixed_0_5": classification_metrics(
                gold, (raw_probabilities >= 0.5).astype(np.uint8)
            ),
            "raw_cross_fitted_threshold": classification_metrics(gold, raw_crossfit_prediction),
            "temperature_fixed_0_5": classification_metrics(
                gold, (temperature_probabilities >= 0.5).astype(np.uint8)
            ),
            "temperature_cross_fitted_threshold": classification_metrics(
                gold, temperature_crossfit_prediction
            ),
            "selected_cross_fitted_threshold": classification_metrics(gold, selected_prediction),
        },
    }


def uncertainty_scores(probabilities: np.ndarray, thresholds: np.ndarray) -> dict[str, np.ndarray]:
    p = np.clip(np.asarray(probabilities, dtype=np.float64), 1e-12, 1.0 - 1e-12)
    entropy = -(p * np.log(p) + (1.0 - p) * np.log1p(-p))
    return {
        "mean_entropy": np.mean(entropy, axis=1),
        "max_entropy": np.max(entropy, axis=1),
        "margin": -np.min(np.abs(p - thresholds[:, None]), axis=1),
    }


def acceptance_mask(
    scores: np.ndarray,
    fold_ids: np.ndarray,
    sample_ids: np.ndarray,
    coverage: float,
) -> np.ndarray:
    accepted = np.zeros(len(scores), dtype=bool)
    for fold_id in sorted(int(value) for value in np.unique(fold_ids)):
        indices = np.flatnonzero(fold_ids == fold_id)
        count = int(math.floor(coverage * len(indices) + 0.5))
        order = np.lexsort((sample_ids[indices], scores[indices]))
        accepted[indices[order[:count]]] = True
    return accepted


def retention_rows(
    family: str,
    method: str,
    target_coverage: float,
    gold: np.ndarray,
    accepted: np.ndarray,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, label in enumerate(LABEL_ORDER):
        support = int(np.sum(gold[:, index] == 1))
        retained = int(np.sum((gold[:, index] == 1) & accepted))
        rows.append(
            {
                "family": family,
                "method": method,
                "target_coverage": target_coverage,
                "label": label,
                "positive_support": support,
                "retained_positive": retained,
                "positive_retention": retained / support if support else 0.0,
            }
        )
    return rows


def selective_analysis(
    family: str,
    gold: np.ndarray,
    prediction: np.ndarray,
    scores: dict[str, np.ndarray],
    fold_ids: np.ndarray,
    sample_ids: np.ndarray,
    config: dict[str, Any],
) -> dict[str, Any]:
    coverages = [float(value) for value in config["selective_prediction"]["coverages"]]
    risk_rows: list[dict[str, Any]] = []
    retention: list[dict[str, Any]] = []
    masks: dict[str, np.ndarray] = {}
    for method in METHOD_ORDER:
        for coverage in coverages:
            mask = acceptance_mask(scores[method], fold_ids, sample_ids, coverage)
            key = f"{method}__{str(coverage).replace('.', '_')}"
            masks[key] = mask
            metrics = classification_metrics(gold[mask], prediction[mask])
            risk_rows.append(
                {
                    "family": family,
                    "method": method,
                    "target_coverage": coverage,
                    "actual_coverage": float(np.mean(mask)),
                    "accepted_rows": int(np.sum(mask)),
                    "hamming_risk": metrics["hamming_loss"],
                    "subset_error": metrics["subset_error"],
                    "micro_f1": metrics["micro_f1"],
                    "macro_f1": metrics["macro_f1"],
                    "five_label_macro_f1": metrics["five_label_macro_f1"],
                }
            )
            retention.extend(retention_rows(family, method, coverage, gold, mask))

    random_rows: list[dict[str, Any]] = []
    random_lookup: dict[float, dict[str, float]] = {}
    repetitions = int(config["selective_prediction"]["random_repetitions"])
    base_seed = int(config["selective_prediction"]["random_seed"])
    family_offset = 0 if family == "m1" else 1_000_000
    for coverage_index, coverage in enumerate(coverages):
        metric_values = {name: [] for name in ("hamming_risk", "macro_f1", "five_label_macro_f1")}
        accepted_count = 0
        for repetition in range(repetitions):
            rng = np.random.default_rng(base_seed + family_offset + coverage_index * 10_000 + repetition)
            mask = np.zeros(len(gold), dtype=bool)
            for fold_id in sorted(int(value) for value in np.unique(fold_ids)):
                indices = np.flatnonzero(fold_ids == fold_id)
                count = int(math.floor(coverage * len(indices) + 0.5))
                chosen = rng.permutation(indices)[:count]
                mask[chosen] = True
            accepted_count = int(np.sum(mask))
            metrics = classification_metrics(gold[mask], prediction[mask])
            metric_values["hamming_risk"].append(metrics["hamming_loss"])
            metric_values["macro_f1"].append(metrics["macro_f1"])
            metric_values["five_label_macro_f1"].append(metrics["five_label_macro_f1"])
        for metric_name, values in metric_values.items():
            array = np.asarray(values, dtype=np.float64)
            record = {
                "family": family,
                "target_coverage": coverage,
                "actual_coverage": accepted_count / len(gold),
                "accepted_rows": accepted_count,
                "metric": metric_name,
                "mean": float(np.mean(array)),
                "p2_5": float(np.percentile(array, 2.5)),
                "p5": float(np.percentile(array, 5.0)),
                "p50": float(np.percentile(array, 50.0)),
                "p95": float(np.percentile(array, 95.0)),
                "p97_5": float(np.percentile(array, 97.5)),
            }
            random_rows.append(record)
            if metric_name == "hamming_risk":
                random_lookup[coverage] = record

    full_metrics = classification_metrics(gold, prediction)
    gate_candidates: list[dict[str, Any]] = []
    retention_lookup = {
        (row["method"], row["target_coverage"], row["label"]): row["positive_retention"]
        for row in retention
    }
    for row in risk_rows:
        coverage = float(row["target_coverage"])
        if coverage < float(config["selective_prediction"]["gate_minimum_coverage"]) or coverage >= 1.0:
            continue
        reduction = (
            (full_metrics["hamming_loss"] - row["hamming_risk"]) / full_metrics["hamming_loss"]
            if full_metrics["hamming_loss"] > 0
            else 0.0
        )
        minimum_retention = min(
            retention_lookup[(row["method"], coverage, label)]
            for label in LABEL_ORDER
            if label != "surprise"
        )
        checks = {
            "hamming_relative_reduction": reduction
            >= float(config["selective_prediction"]["gate_hamming_relative_reduction"]),
            "five_label_macro_f1": row["five_label_macro_f1"]
            >= full_metrics["five_label_macro_f1"]
            - float(config["selective_prediction"]["gate_max_five_label_macro_drop"]),
            "non_surprise_positive_retention": minimum_retention
            >= float(config["selective_prediction"]["gate_min_non_surprise_retention"]),
            "better_than_random": row["hamming_risk"] < random_lookup[coverage]["p5"],
        }
        gate_candidates.append(
            {
                **row,
                "hamming_relative_reduction": float(reduction),
                "minimum_non_surprise_positive_retention": float(minimum_retention),
                "random_hamming_p5": float(random_lookup[coverage]["p5"]),
                "checks": checks,
                "qualifies": bool(all(checks.values())),
            }
        )
    qualifying = [row for row in gate_candidates if row["qualifies"]]
    selected_gate = None
    if qualifying:
        method_rank = {name: index for index, name in enumerate(METHOD_ORDER)}
        qualifying.sort(
            key=lambda row: (
                -row["hamming_relative_reduction"],
                -row["target_coverage"],
                method_rank[row["method"]],
            )
        )
        selected_gate = qualifying[0]

    cutoffs: list[dict[str, Any]] = []
    for method in METHOD_ORDER:
        for coverage in coverages:
            order = np.lexsort((sample_ids, scores[method]))
            count = int(math.floor(coverage * len(order) + 0.5))
            cutoff = float(scores[method][order[count - 1]]) if count else float("-inf")
            cutoffs.append(
                {
                    "method": method,
                    "target_coverage": coverage,
                    "accepted_rows": count,
                    "score_cutoff": cutoff,
                    "online_tie_policy": "accept_score_below_cutoff_then_sample_id_order_for_boundary_ties",
                }
            )
    return {
        "risk_rows": risk_rows,
        "retention_rows": retention,
        "random_rows": random_rows,
        "masks": masks,
        "gate": {
            "passed": selected_gate is not None,
            "selected_operating_point": selected_gate,
            "evaluated_candidates": gate_candidates,
            "full_coverage_metrics": full_metrics,
        },
        "full_oof_cutoffs": cutoffs,
    }


def whole_vector_oracle(
    gold: np.ndarray, m1_prediction: np.ndarray, m3_prediction: np.ndarray, minimum_gain: float
) -> tuple[dict[str, Any], np.ndarray]:
    m1_loss = np.sum(m1_prediction != gold, axis=1)
    m3_loss = np.sum(m3_prediction != gold, axis=1)
    choose_m3 = m3_loss < m1_loss
    oracle_prediction = np.where(choose_m3[:, None], m3_prediction, m1_prediction)
    m1_metrics = classification_metrics(gold, m1_prediction)
    m3_metrics = classification_metrics(gold, m3_prediction)
    oracle_metrics = classification_metrics(gold, oracle_prediction)
    six_gain = oracle_metrics["macro_f1"] - m1_metrics["macro_f1"]
    five_gain = oracle_metrics["five_label_macro_f1"] - m1_metrics["five_label_macro_f1"]
    return (
        {
            "m1": m1_metrics,
            "m3": m3_metrics,
            "whole_vector_oracle": oracle_metrics,
            "m3_selected_rows": int(np.sum(choose_m3)),
            "m3_selection_rate": float(np.mean(choose_m3)),
            "macro_f1_gain_over_m1": float(six_gain),
            "five_label_macro_f1_gain_over_m1": float(five_gain),
            "router_headroom_gate": {
                "minimum_gain": minimum_gain,
                "passed": bool(not (six_gain < minimum_gain and five_gain < minimum_gain)),
                "surprise_only_or_low_support_warning": bool(
                    six_gain >= minimum_gain and five_gain < minimum_gain
                ),
                "claim_boundary": "Non-deployable whole-vector oracle; not a router result.",
            },
        },
        choose_m3,
    )


def component_groups(component_ids: np.ndarray) -> list[np.ndarray]:
    groups: dict[str, list[int]] = {}
    for index, component in enumerate(component_ids.tolist()):
        groups.setdefault(str(component), []).append(index)
    return [np.asarray(groups[key], dtype=np.int64) for key in sorted(groups)]


def percentile_interval(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "mean": float(np.mean(array)),
        "lower_95": float(np.percentile(array, 2.5)),
        "upper_95": float(np.percentile(array, 97.5)),
    }


def bootstrap_analysis(
    gold: np.ndarray,
    component_ids: np.ndarray,
    family_results: dict[str, dict[str, Any]],
    selective: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    repetitions = int(config["bootstrap"]["repetitions"])
    rng = np.random.default_rng(int(config["bootstrap"]["seed"]))
    groups = component_groups(component_ids)
    calibration_values = {
        family: {"nll_delta": [], "brier_delta": []} for family in FAMILY_ORDER
    }
    oracle_six: list[float] = []
    oracle_five: list[float] = []
    gate_reductions: dict[str, list[float]] = {
        family: [] for family in FAMILY_ORDER if selective[family]["gate"]["passed"]
    }
    gate_masks: dict[str, np.ndarray] = {}
    for family in gate_reductions:
        selected = selective[family]["gate"]["selected_operating_point"]
        key = f"{selected['method']}__{str(selected['target_coverage']).replace('.', '_')}"
        gate_masks[family] = selective[family]["masks"][key]

    for _ in range(repetitions):
        sampled = rng.integers(0, len(groups), size=len(groups))
        indices = np.concatenate([groups[index] for index in sampled])
        sampled_gold = gold[indices]
        for family in FAMILY_ORDER:
            result = family_results[family]
            raw = result["raw_probabilities"][indices]
            temperature = result["temperature_probabilities"][indices]
            calibration_values[family]["nll_delta"].append(
                probability_nll(temperature, sampled_gold) - probability_nll(raw, sampled_gold)
            )
            calibration_values[family]["brier_delta"].append(
                brier_score(temperature, sampled_gold) - brier_score(raw, sampled_gold)
            )
        m1_prediction = family_results["m1"]["selected_prediction"][indices]
        m3_prediction = family_results["m3"]["selected_prediction"][indices]
        oracle, _ = whole_vector_oracle(sampled_gold, m1_prediction, m3_prediction, 0.01)
        oracle_six.append(oracle["macro_f1_gain_over_m1"])
        oracle_five.append(oracle["five_label_macro_f1_gain_over_m1"])
        for family, values in gate_reductions.items():
            prediction = family_results[family]["selected_prediction"][indices]
            mask = gate_masks[family][indices]
            full_risk = classification_metrics(sampled_gold, prediction)["hamming_loss"]
            if np.any(mask) and full_risk > 0:
                selective_risk = classification_metrics(sampled_gold[mask], prediction[mask])[
                    "hamming_loss"
                ]
                values.append((full_risk - selective_risk) / full_risk)

    return {
        "repetitions": repetitions,
        "seed": int(config["bootstrap"]["seed"]),
        "unit": "duplicate_component",
        "component_count": len(groups),
        "calibration_deltas": {
            family: {
                metric: percentile_interval(values)
                for metric, values in calibration_values[family].items()
            }
            for family in FAMILY_ORDER
        },
        "oracle_gains": {
            "macro_f1": percentile_interval(oracle_six),
            "five_label_macro_f1": percentile_interval(oracle_five),
        },
        "selected_abstention_hamming_relative_reduction": {
            family: percentile_interval(values) for family, values in gate_reductions.items()
        },
        "selection_warning": "Intervals do not correct for uncertainty-method selection.",
    }


def make_figures(
    run_dir: Path,
    reliability_rows: list[dict[str, Any]],
    risk_rows: list[dict[str, Any]],
    random_rows: list[dict[str, Any]],
) -> tuple[Path, Path]:
    os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/exp059-matplotlib")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    reliability_path = run_dir / "reliability-diagram.png"
    figure, axes = plt.subplots(1, 2, figsize=(10, 4), sharex=True, sharey=True)
    for axis, family in zip(axes, FAMILY_ORDER):
        for pipeline, color in (("identity", "#4666a5"), ("temperature", "#b34b3f")):
            rows = [
                row
                for row in reliability_rows
                if row["family"] == family and row["pipeline"] == pipeline
            ]
            axis.plot(
                [row["mean_confidence"] for row in rows],
                [row["empirical_positive_rate"] for row in rows],
                marker="o",
                linewidth=1.5,
                markersize=3,
                label=pipeline,
                color=color,
            )
        axis.plot([0, 1], [0, 1], linestyle="--", color="#777777", linewidth=1)
        axis.set_title(family.upper())
        axis.set_xlabel("Mean predicted probability")
        axis.grid(alpha=0.2)
    axes[0].set_ylabel("Empirical positive rate")
    axes[1].legend(frameon=False)
    figure.tight_layout()
    figure.savefig(reliability_path, dpi=160, metadata=FIGURE_METADATA)
    plt.close(figure)

    risk_path = run_dir / "risk-coverage-curve.png"
    figure, axes = plt.subplots(1, 2, figsize=(10, 4), sharex=True)
    colors = {"mean_entropy": "#4666a5", "max_entropy": "#b34b3f", "margin": "#2f7d5c"}
    for axis, family in zip(axes, FAMILY_ORDER):
        for method in METHOD_ORDER:
            rows = [
                row for row in risk_rows if row["family"] == family and row["method"] == method
            ]
            rows.sort(key=lambda row: row["actual_coverage"])
            axis.plot(
                [row["actual_coverage"] for row in rows],
                [row["hamming_risk"] for row in rows],
                marker="o",
                label=method,
                color=colors[method],
            )
        random = [
            row
            for row in random_rows
            if row["family"] == family and row["metric"] == "hamming_risk"
        ]
        random.sort(key=lambda row: row["actual_coverage"])
        axis.plot(
            [row["actual_coverage"] for row in random],
            [row["mean"] for row in random],
            linestyle="--",
            color="#777777",
            label="random mean",
        )
        axis.set_title(family.upper())
        axis.set_xlabel("Coverage")
        axis.set_ylabel("Selective Hamming risk")
        axis.grid(alpha=0.2)
    axes[1].legend(frameon=False, fontsize=8)
    figure.tight_layout()
    figure.savefig(risk_path, dpi=160, metadata=FIGURE_METADATA)
    plt.close(figure)
    return reliability_path, risk_path


def write_report(
    path: Path,
    calibration: dict[str, Any],
    classification: dict[str, Any],
    gates: dict[str, Any],
    oracle: dict[str, Any],
    bootstrap: dict[str, Any],
    config: dict[str, Any],
) -> None:
    if is_v2(config):
        seed_scope = (
            f"the frozen seed-{config['model_seed']} paired train-OOF artifact from "
            f"{config['replication_parent_experiment_id']}"
        )
        claim_scope = f"the frozen seed-{config['model_seed']} pair"
        router_note = (
            "Temperature adoption is diagnostic only for this seed; EXP-060 replication "
            "uses identity probabilities computed directly from raw OOF logits (`T=1`)."
        )
    else:
        seed_scope = "the frozen EXP-058 paired train-OOF artifact"
        claim_scope = "the frozen seed-42 pair"
        router_note = ""
    lines = [
        "# EXP-059 Cross-Fitted Calibration And Selective Prediction",
        "",
        "## Scope",
        "",
        f"This report uses only {seed_scope}. Validation and test were not accessed.",
        router_note,
        "",
        "## Calibration",
        "",
        "| Family | Raw NLL | Temperature NLL | Raw Brier | Temperature Brier | Selected calibrator | Final T |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for family in FAMILY_ORDER:
        item = calibration["families"][family]
        lines.append(
            f"| {family.upper()} | {item['identity']['nll']:.6f} | "
            f"{item['temperature_cross_fitted']['nll']:.6f} | {item['identity']['brier']:.6f} | "
            f"{item['temperature_cross_fitted']['brier']:.6f} | {item['selected_calibrator']} | "
            f"{item['final_temperature']:.6f} |"
        )
    lines.extend(["", "## Selected Classification", "", "| Family | Macro-F1 | Five-label Macro-F1 | Micro-F1 | Hamming loss | Subset accuracy |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
    for family in FAMILY_ORDER:
        metrics = classification["families"][family]["selected_cross_fitted_threshold"]
        lines.append(
            f"| {family.upper()} | {metrics['macro_f1']:.6f} | {metrics['five_label_macro_f1']:.6f} | "
            f"{metrics['micro_f1']:.6f} | {metrics['hamming_loss']:.6f} | {metrics['subset_accuracy']:.6f} |"
        )
    lines.extend(["", "## Abstention Gates", ""])
    for family in FAMILY_ORDER:
        gate = gates["families"][family]
        if gate["passed"]:
            selected = gate["selected_operating_point"]
            lines.append(
                f"- {family.upper()}: Passed at {selected['target_coverage']:.2f} target coverage with "
                f"`{selected['method']}`; Hamming-risk relative reduction "
                f"`{selected['hamming_relative_reduction']:.6f}`."
            )
        else:
            lines.append(f"- {family.upper()}: Failed; no preregistered operating point qualified.")
    lines.extend(
        [
            "",
            "## Router Headroom Diagnostic",
            "",
            f"- M3 selection rate: `{oracle['m3_selection_rate']:.6f}`",
            f"- Six-label Macro-F1 gain over M1: `{oracle['macro_f1_gain_over_m1']:.6f}`",
            f"- Five-label Macro-F1 gain over M1: `{oracle['five_label_macro_f1_gain_over_m1']:.6f}`",
            f"- Preliminary EXP-060 headroom gate: `{oracle['router_headroom_gate']['passed']}`",
            "",
            "This is a non-deployable whole-vector oracle and is not a learned-router result.",
            "",
            "## Uncertainty",
            "",
            f"All intervals use `{bootstrap['repetitions']}` duplicate-component bootstrap replicates. "
            "They are train-OOF development intervals and do not replace an independent test.",
            "",
            "## Claim Boundary",
            "",
            f"EXP-059 can support claims about {claim_scope}'s cross-fitted calibration and selective-risk ranking. "
            "It does not support a new test result, a three-seed stability claim, deployment benefit, context benefit, or an internal emotion mechanism.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def report_private_identifier_leaks(
    report_text: str, data: dict[str, np.ndarray]
) -> list[str]:
    private_tokens = {
        str(value)
        for name in ("sample_ids", "component_ids")
        for value in data[name].tolist()
    }
    return sorted(token for token in private_tokens if token and token in report_text)


def validate_loaded_input(data: dict[str, np.ndarray], config: dict[str, Any]) -> None:
    if set(data) != set(expected_input_schema()):
        raise ValueError("EXP-058 paired input key drift")
    if len(set(data["sample_ids"].tolist())) != 3360:
        raise ValueError("Sample IDs are not unique")
    if not np.all(np.isin(data["gold"], [0, 1])):
        raise ValueError("Gold matrix is not binary")
    for family in FAMILY_ORDER:
        if not np.all(np.isfinite(data[f"{family}_logits"])):
            raise ValueError(f"Non-finite {family} logits")
    if sorted(np.unique(data["fold_ids"]).tolist()) != config["cross_fitting"]["fold_ids"]:
        raise ValueError("Fold ID drift")
    for fold_id in config["cross_fitting"]["fold_ids"]:
        if int(np.sum(data["fold_ids"] == fold_id)) != 672:
            raise ValueError(f"Fold {fold_id} row-count drift")
    component_folds: dict[str, set[int]] = {}
    for component, fold in zip(data["component_ids"].tolist(), data["fold_ids"].tolist()):
        component_folds.setdefault(str(component), set()).add(int(fold))
    if any(len(folds) != 1 for folds in component_folds.values()):
        raise ValueError("Duplicate component crosses folds")


def calibration_parameters_document(
    config: dict[str, Any], family_results: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    document: dict[str, Any] = {"families": {}}
    if is_v2(config):
        document = {
            **identity_provenance(config),
            "router_replication_calibration": {
                "calibrator": "identity",
                "temperature": 1.0,
                "probability_source": "direct_sigmoid_of_raw_oof_logits",
                "role": "frozen_exp060_replication_only",
            },
            "families": {},
        }
    for family in FAMILY_ORDER:
        result = family_results[family]
        document["families"][family] = {
            "fold_fits": result["fold_fits"],
            "full_oof_temperature_fit": result["full_fit"],
            "selected_calibrator": "temperature" if result["temperature_accepted"] else "identity",
            "final_temperature": result["final_temperature"],
            "final_global_threshold": result["final_threshold_selection"],
        }
    return document


def preflight(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    paths = output_paths(config)
    run_dir = paths["preflight"]
    formal_public = paths["public_calibration"]
    formal_private = paths["private_calibration"]
    if is_v2(config):
        if os.path.lexists(paths["selection"]) or os.path.lexists(paths["completion"]):
            raise FileExistsError("A selected or completed attempt blocks EXP-059 preflight")
        if not paths["public_attempt"].is_dir() or not paths["private_attempt"].is_dir():
            raise FileNotFoundError("EXP-059 requires existing OOF public/private attempt directories")
        validate_oof_prerequisites(config)
    if run_dir.exists() or formal_public.exists() or formal_private.exists():
        raise FileExistsError("Refusing to overwrite EXP-059 preflight/formal outputs")
    input_path = require_record(config["input"]["paired_oof"])
    schema = npz_header_schema(input_path)
    if schema != expected_input_schema():
        raise ValueError(f"Paired OOF header schema drift: {schema}")
    verification_key = "oof_verification" if is_v2(config) else "exp058_verification"
    exp058_verification = json.loads(require_record(
        config["prerequisites"][verification_key]
    ).read_text(encoding="utf-8"))
    if exp058_verification.get("status") != "Passed" or exp058_verification.get("failed_count") != 0:
        raise ValueError("EXP-058 final verification is not passed")
    versions = dependency_versions()
    if any(versions[name] == "not-installed" for name in ("numpy", "scipy", "matplotlib")):
        raise RuntimeError("EXP-059 analysis dependencies are incomplete")
    run_dir.mkdir(parents=True)
    frozen = freeze_sources(run_dir, config_path, config)
    run = {
        "schema_version": "exp-059-preflight-run-v1",
        **identity_provenance(config),
        "rq_id": RQ_ID,
        "tier": "Major",
        "stage": "calibration-selective-preflight",
        "status": "CompletedAwaitingVerification",
        "completed_at_utc": utc_now(),
        "input": artifact(input_path),
        "input_schema": public_schema_records(schema),
        "dependencies": versions,
        "runtime": {"python_executable": os.path.realpath(os.sys.executable), "platform": platform.platform()},
        "git": git_metadata(),
        "frozen_sources": frozen,
        "formal_analysis_performed": False,
        "performance_metrics_computed": False,
        "array_values_loaded": False,
        "split_access": {
            "accessed_splits": ["train-oof-header"],
            "validation_accessed": False,
            "test_inputs_accessed": False,
            "test_labels_accessed": False,
        },
    }
    if is_v2(config):
        run["schema_version"] = "exp-059-preflight-run-v2"
        run["config"] = artifact(config_path)
    if public_sensitive_paths(run):
        raise ValueError("Preflight public privacy violation")
    atomic_json(run_dir / "run.json", run)
    if is_v2(config):
        assert_exact_public_tree(run_dir, config, stage="preflight", verified=False)
    return run


def formal_run(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    if not config["authorization"]["formal_analysis"]:
        raise PermissionError("Formal EXP-059 analysis is not authorized")
    if is_v2(config) and not {
        "preflight_run",
        "preflight_verification",
    }.issubset(config["prerequisites"]):
        raise ValueError("Formal EXP-059 v2 requires preflight run and verification")
    if is_v2(config):
        validate_preflight_prerequisites(config)
    else:
        preflight_verification = json.loads(require_record(
            config["prerequisites"]["preflight_verification"]
        ).read_text(encoding="utf-8"))
        if (
            preflight_verification.get("status") != "Passed"
            or preflight_verification.get("failed_count") != 0
        ):
            raise ValueError("EXP-059 preflight verification is not passed")
    paths = output_paths(config)
    run_dir = paths["public_calibration"]
    private_dir = paths["private_calibration"]
    if is_v2(config):
        if os.path.lexists(paths["selection"]) or os.path.lexists(paths["completion"]):
            raise FileExistsError("A selected or completed attempt blocks EXP-059 formal analysis")
        validate_oof_prerequisites(config)
    if run_dir.exists() or private_dir.exists():
        raise FileExistsError("Refusing to overwrite append-only EXP-059 output")
    started_at_utc = utc_now()
    started = time.monotonic()
    run_dir.mkdir(parents=True)
    private_dir.mkdir(parents=True, mode=0o700)
    os.chmod(private_dir, 0o700)
    frozen = freeze_sources(run_dir, config_path, config)
    input_path = require_record(config["input"]["paired_oof"])
    input_hash_before = sha256(input_path)
    with np.load(input_path, allow_pickle=False) as archive:
        data = {name: np.array(archive[name], copy=True) for name in archive.files}
    validate_loaded_input(data, config)
    gold = data["gold"]
    fold_ids = data["fold_ids"]
    family_results = {
        family: cross_fit_family(data[f"{family}_logits"], gold, fold_ids, config)
        for family in FAMILY_ORDER
    }
    reliability_rows: list[dict[str, Any]] = []
    calibration_public: dict[str, Any] = {"families": {}}
    parameters_public = calibration_parameters_document(config, family_results)
    classification_public: dict[str, Any] = {"families": {}}
    selective: dict[str, dict[str, Any]] = {}
    risk_rows: list[dict[str, Any]] = []
    retention_rows_all: list[dict[str, Any]] = []
    random_rows: list[dict[str, Any]] = []
    gates_public: dict[str, Any] = {"families": {}}
    private_arrays: dict[str, np.ndarray] = {
        name: data[name]
        for name in ("sample_ids", "component_ids", "fold_ids", "gold", "character_lengths", "m1_token_lengths", "m3_token_lengths")
    }
    for family in FAMILY_ORDER:
        result = family_results[family]
        calibration_public["families"][family] = {
            "identity": result["raw_calibration"],
            "temperature_cross_fitted": result["temperature_calibration"],
            "temperature_minus_identity": result["calibration_deltas"],
            "selected_calibrator": "temperature" if result["temperature_accepted"] else "identity",
            "temperature_accepted": result["temperature_accepted"],
            "final_temperature": result["final_temperature"],
        }
        classification_public["families"][family] = result["classification"]
        for pipeline, rows in (
            ("identity", result["raw_reliability"]),
            ("temperature", result["temperature_reliability"]),
        ):
            for row in rows:
                reliability_rows.append({"family": family, "pipeline": pipeline, **row})
        scores = uncertainty_scores(result["selected_probabilities"], result["selected_thresholds"])
        selective[family] = selective_analysis(
            family,
            gold,
            result["selected_prediction"],
            scores,
            fold_ids,
            data["sample_ids"],
            config,
        )
        risk_rows.extend(selective[family]["risk_rows"])
        retention_rows_all.extend(selective[family]["retention_rows"])
        random_rows.extend(selective[family]["random_rows"])
        gates_public["families"][family] = {
            **selective[family]["gate"],
            "full_oof_uncertainty_cutoffs": selective[family]["full_oof_cutoffs"],
        }
        private_arrays[f"{family}_temperature_probabilities"] = result[
            "temperature_probabilities"
        ].astype(np.float64)
        private_arrays[f"{family}_selected_probabilities"] = result[
            "selected_probabilities"
        ].astype(np.float64)
        private_arrays[f"{family}_raw_thresholds"] = result["raw_thresholds"].astype(np.float64)
        private_arrays[f"{family}_temperature_thresholds"] = result[
            "temperature_thresholds"
        ].astype(np.float64)
        private_arrays[f"{family}_selected_thresholds"] = result["selected_thresholds"].astype(
            np.float64
        )
        private_arrays[f"{family}_selected_prediction"] = result["selected_prediction"].astype(
            np.uint8
        )
        for method, values in scores.items():
            private_arrays[f"{family}_uncertainty_{method}"] = values.astype(np.float64)
        for key, mask in selective[family]["masks"].items():
            private_arrays[f"{family}_accept_{key}"] = mask.astype(np.uint8)

    oracle_public, oracle_choose_m3 = whole_vector_oracle(
        gold,
        family_results["m1"]["selected_prediction"],
        family_results["m3"]["selected_prediction"],
        float(config["oracle"]["minimum_macro_gain"]),
    )
    private_arrays["oracle_choose_m3"] = oracle_choose_m3.astype(np.uint8)
    bootstrap_public = bootstrap_analysis(data["gold"], data["component_ids"], family_results, selective, config)
    private_path = private_dir / "cross-fitted-calibration.npz"
    atomic_npz(private_path, private_arrays)
    atomic_json(run_dir / "calibration-parameters.json", parameters_public)
    atomic_json(run_dir / "calibration-metrics.json", calibration_public)
    atomic_json(run_dir / "classification-metrics.json", classification_public)
    atomic_json(run_dir / "oracle-summary.json", oracle_public)
    atomic_json(run_dir / "abstention-gates.json", gates_public)
    atomic_json(run_dir / "bootstrap.json", bootstrap_public)
    atomic_csv(run_dir / "reliability-bins.csv", reliability_rows)
    atomic_csv(run_dir / "risk-coverage.csv", risk_rows)
    atomic_csv(run_dir / "label-retention.csv", retention_rows_all)
    atomic_csv(run_dir / "random-rejection.csv", random_rows)
    reliability_figure, risk_figure = make_figures(run_dir, reliability_rows, risk_rows, random_rows)
    write_report(
        run_dir / "REPORT.md",
        calibration_public,
        classification_public,
        gates_public,
        oracle_public,
        bootstrap_public,
        config,
    )
    report_text = (run_dir / "REPORT.md").read_text(encoding="utf-8")
    if report_private_identifier_leaks(report_text, data):
        raise ValueError("EXP-059 report contains a private row identifier")
    input_hash_after = sha256(input_path)
    if input_hash_before != input_hash_after:
        raise ValueError("EXP-058 paired input changed during EXP-059")
    public_outputs = {
        name: artifact(run_dir / filename)
        for name, filename in {
            "calibration_parameters": "calibration-parameters.json",
            "calibration_metrics": "calibration-metrics.json",
            "classification_metrics": "classification-metrics.json",
            "oracle_summary": "oracle-summary.json",
            "abstention_gates": "abstention-gates.json",
            "bootstrap": "bootstrap.json",
            "reliability_bins": "reliability-bins.csv",
            "risk_coverage": "risk-coverage.csv",
            "label_retention": "label-retention.csv",
            "random_rejection": "random-rejection.csv",
            "reliability_figure": reliability_figure.name,
            "risk_coverage_figure": risk_figure.name,
            "report": "REPORT.md",
        }.items()
    }
    run = {
        "schema_version": "exp-059-formal-run-v1",
        **identity_provenance(config),
        "rq_id": RQ_ID,
        "tier": "Major",
        "stage": "cross-fitted-calibration-selective-prediction",
        "status": "CompletedAwaitingVerification",
        "started_at_utc": started_at_utc,
        "completed_at_utc": utc_now(),
        "runtime": {
            "python_executable": os.path.realpath(os.sys.executable),
            "platform": platform.platform(),
            "dependencies": dependency_versions(),
        },
        "git": git_metadata(),
        "input_before": artifact(input_path),
        "input_sha256_after": input_hash_after,
        "private_output": artifact(private_path),
        "public_outputs": public_outputs,
        "frozen_sources": frozen,
        "rows": int(len(gold)),
        "folds": int(len(np.unique(fold_ids))),
        "component_count": int(len(np.unique(data["component_ids"]))),
        "performance_metrics_computed": True,
        "calibration_performed": True,
        "selective_prediction_performed": True,
        "oracle_analysis_performed": True,
        "router_training_performed": False,
        "model_loading_or_forward_performed": False,
        "resources": {
            "wall_seconds": float(time.monotonic() - started),
            "peak_process_rss_gb": peak_rss_gb(),
            "api_cost_usd": 0,
        },
        "split_access": {
            "accessed_splits": ["train-oof"],
            "validation_accessed": False,
            "test_inputs_accessed": False,
            "test_labels_accessed": False,
        },
        "claim_boundary": "Fully cross-fitted train-OOF development evidence only; no new test or deployable-router claim.",
    }
    if is_v2(config):
        run["schema_version"] = "exp-059-formal-run-v2"
        run["config"] = artifact(config_path)
        run["temperature_adoption_role"] = "diagnostic_only"
        run["router_replication_calibration"] = {
            "calibrator": "identity",
            "temperature": 1.0,
            "probability_source": "direct_sigmoid_of_raw_oof_logits",
            "role": "frozen_exp060_replication_only",
        }
    violations = public_sensitive_paths(run)
    if violations:
        raise ValueError(f"Public run privacy violation: {violations}")
    atomic_json(run_dir / "run.json", run)
    if is_v2(config):
        assert_exact_public_tree(run_dir, config, stage="calibration", verified=False)
        assert_exact_private_tree(private_dir)
    return run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EXP-059 calibration/selective prediction")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--stage", choices=("preflight", "run"), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    config = load_config(config_path)
    if config.get("_archive_only"):
        raise PermissionError("Sealed EXP-059 is archive-only; use its frozen sources for audit")
    if args.stage == "preflight":
        result = preflight(config_path, config)
    else:
        result = formal_run(config_path, config)
    print(json.dumps({"stage": args.stage, "status": result["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
