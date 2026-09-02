#!/usr/bin/env python3
"""Independently verify EXP-059 preflight and formal analysis artifacts."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import resource
import stat
import struct
import tempfile
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
PUBLIC_OUTPUT_FILENAMES = {
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
    "reliability_figure": "reliability-diagram.png",
    "risk_coverage_figure": "risk-coverage-curve.png",
    "report": "REPORT.md",
}
FINAL_COMPLETION_REQUIRED_CHECKS = {
    "data.keys",
    "data.unique_sample_ids",
    "data.binary_gold",
    "data.finite_m1",
    "data.finite_m3",
    "data.component_fold_disjoint",
    "private.keys",
    "run.identity",
    "run.input_before",
    "run.input_after",
    "run.private_output",
    "run.no_validation",
    "run.no_test_inputs",
    "run.no_test_labels",
    "run.no_model_forward",
    "run.no_router",
    "run.router_identity",
    "run.oof_prerequisites",
    "run.preflight_provenance",
    "run.public_outputs",
    "run.frozen_sources",
    "report.exact",
    "report.no_private_ids",
    "figure.reliability-diagram.png.sha256",
    "figure.risk-coverage-curve.png.sha256",
    "resource.wall_budget",
    "resource.memory_budget",
    "resource.api_cost",
    "verification.resource.wall_budget",
    "verification.resource.memory_budget",
    "verification.resource.api_cost",
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
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
FAMILIES = ("m1", "m3")
METHODS = ("mean_entropy", "max_entropy", "margin")
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-059-calibration-selective-prediction.json"
PROHIBITED_PUBLIC_KEYS = {
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
    current = PROJECT_ROOT.resolve()
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
    if set(config.get("input", {})) != {"paired_oof"}:
        raise ValueError("EXP-059 replication input inventory drift")
    if config["input"]["paired_oof"].get("path") != display_path(
        paths["private_attempt"] / "paired-oof.npz"
    ):
        raise ValueError("EXP-059 paired OOF must come from the same private attempt")
    if config.get("data") != {
        "protocol_id": "DATA-SO-TASK-V1",
        "split": "train-oof",
        "rows": 3360,
        "label_order": list(LABELS),
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
    expected_paths = {
        "oof_run": f"{public_attempt}/run.json",
        "oof_verification": f"{public_attempt}/verification.json",
        "oof_completion": f"{public_attempt}/oof-complete.json",
    }
    if "preflight_run" in prerequisite_keys:
        expected_paths["preflight_run"] = f"{public_attempt}/calibration-preflight/run.json"
    if "preflight_verification" in prerequisite_keys:
        expected_paths["preflight_verification"] = (
            f"{public_attempt}/calibration-preflight/verification.json"
        )
    for name, expected in expected_paths.items():
        if config["prerequisites"][name].get("path") != expected:
            raise ValueError(f"EXP-059 prerequisite path drift: {name}")
    formal = "preflight_run" in prerequisite_keys or "preflight_verification" in prerequisite_keys
    if (prerequisite_keys & {"preflight_run", "preflight_verification"}) not in (
        set(),
        {"preflight_run", "preflight_verification"},
    ):
        raise ValueError("EXP-059 preflight prerequisite pair is incomplete")
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


def oof_prerequisites(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = config["prerequisites"]
    values = {
        "run": json.loads(require_record(records["oof_run"]).read_text(encoding="utf-8")),
        "verification": json.loads(
            require_record(records["oof_verification"]).read_text(encoding="utf-8")
        ),
        "completion": json.loads(
            require_record(records["oof_completion"]).read_text(encoding="utf-8")
        ),
    }
    validate_oof_chain(
        config, records, values["run"], values["verification"], values["completion"]
    )
    return values


def preflight_prerequisites(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = config["prerequisites"]
    if not {"preflight_run", "preflight_verification"}.issubset(records):
        raise ValueError("Formal EXP-059 requires a complete preflight pair")
    run_path = require_record(records["preflight_run"])
    values = {
        "run": json.loads(run_path.read_text(encoding="utf-8")),
        "verification": json.loads(
            require_record(records["preflight_verification"]).read_text(encoding="utf-8")
        ),
    }
    identity = identity_provenance(config)
    run = values["run"]
    verification = values["verification"]
    verified = verification.get("verified_artifacts", {})
    try:
        validate_verification_document(
            verification, config, "preflight", run.get("config")
        )
        verification_contract_valid = True
    except (KeyError, TypeError, ValueError):
        verification_contract_valid = False
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
        or not verification_contract_valid
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
    return values


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
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def artifact(path: Path) -> dict[str, Any]:
    return {"path": display_path(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def create_json_once(path: Path, value: Any) -> None:
    if os.path.lexists(path):
        raise FileExistsError(f"Refusing to overwrite immutable artifact: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    try:
        os.link(temporary, path)
    except FileExistsError as error:
        raise FileExistsError(f"Refusing to overwrite immutable artifact: {path}") from error
    finally:
        temporary.unlink(missing_ok=True)


def create_text_once(path: Path, text: str) -> None:
    if os.path.lexists(path):
        raise FileExistsError(f"Refusing to overwrite immutable artifact: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    try:
        os.link(temporary, path)
    except FileExistsError as error:
        raise FileExistsError(f"Refusing to overwrite immutable artifact: {path}") from error
    finally:
        temporary.unlink(missing_ok=True)


def require_record(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Frozen artifact drift: {path}")
    return path


def expected_public_output_records(run_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        name: artifact(run_dir / filename)
        for name, filename in PUBLIC_OUTPUT_FILENAMES.items()
    }


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
        raise ValueError("Unexpected EXP-059 config identity")
    if is_v2(config):
        validate_v2_config(config)
    if tuple(config["data"]["label_order"]) != LABELS:
        raise ValueError("Label order drift")
    if is_v2(config):
        for section in ("implementation", "prerequisites", "input"):
            for record in iter_records(config.get(section, {})):
                require_record(record)
    else:
        validate_legacy_archive(path, config)
        config["_archive_only"] = True
    if config["authorization"]["validation_access"] or config["authorization"]["test_access"]:
        raise ValueError("EXP-059 may not access validation or test")
    if is_v2(config) and (
        config["authorization"].get("model_loading_or_forward") is not False
        or config["authorization"].get("router_training") is not False
    ):
        raise ValueError("EXP-059 diagnostics may not load models or train a router")
    return config


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            if key in PROHIBITED_PUBLIC_KEYS:
                violations.append(child_path)
            violations.extend(public_sensitive_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    return violations


def expected_schema() -> dict[str, dict[str, Any]]:
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
                    raise ValueError(f"Unsupported NPY header version: {version}")
            schema[Path(member).stem] = {
                "shape": list(shape),
                "dtype": str(dtype),
                "fortran_order": bool(fortran),
            }
    return schema


def public_schema_records(schema: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"array_name": name, **details}
        for name, details in sorted(schema.items())
    ]


class Checks:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, name: str, passed: bool, detail: Any = None) -> None:
        self.rows.append({"name": name, "passed": bool(passed), "detail": detail})

    @property
    def failed(self) -> list[dict[str, Any]]:
        return [row for row in self.rows if not row["passed"]]


def numeric_equal(left: Any, right: Any, tolerance: float = 1e-10) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isfinite(float(left)) and math.isfinite(float(right)) and math.isclose(
            float(left), float(right), rel_tol=0.0, abs_tol=tolerance
        )
    return left == right


def compare_tree(checks: Checks, name: str, actual: Any, expected: Any) -> None:
    if isinstance(expected, dict):
        checks.add(f"{name}.keys", isinstance(actual, dict) and set(actual) == set(expected), {
            "actual": sorted(actual) if isinstance(actual, dict) else type(actual).__name__,
            "expected": sorted(expected),
        })
        if not isinstance(actual, dict):
            return
        for key in sorted(set(actual) & set(expected)):
            compare_tree(checks, f"{name}.{key}", actual[key], expected[key])
    elif isinstance(expected, list):
        checks.add(f"{name}.length", isinstance(actual, list) and len(actual) == len(expected), {
            "actual": len(actual) if isinstance(actual, list) else type(actual).__name__,
            "expected": len(expected),
        })
        if not isinstance(actual, list):
            return
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
            compare_tree(checks, f"{name}[{index}]", actual_item, expected_item)
    else:
        checks.add(name, numeric_equal(actual, expected), {"actual": actual, "expected": expected})


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def compare_csv(checks: Checks, name: str, actual: list[dict[str, str]], expected: list[dict[str, Any]]) -> None:
    checks.add(f"{name}.row_count", len(actual) == len(expected), {"actual": len(actual), "expected": len(expected)})
    if not expected:
        return
    expected_columns = list(expected[0])
    actual_columns = list(actual[0]) if actual else []
    checks.add(f"{name}.columns", actual_columns == expected_columns, {"actual": actual_columns, "expected": expected_columns})
    for row_index, (actual_row, expected_row) in enumerate(zip(actual, expected)):
        for key in expected_columns:
            expected_value = expected_row[key]
            raw = actual_row.get(key)
            if isinstance(expected_value, bool):
                converted: Any = raw == "True"
            elif isinstance(expected_value, int):
                converted = int(raw) if raw is not None else None
            elif isinstance(expected_value, float):
                converted = float(raw) if raw is not None else None
            else:
                converted = raw
            checks.add(
                f"{name}.row_{row_index}.{key}",
                numeric_equal(converted, expected_value),
                {"actual": converted, "expected": expected_value},
            )


def sigmoid(values: np.ndarray) -> np.ndarray:
    x = np.asarray(values, dtype=np.float64)
    result = np.empty_like(x)
    positive = x >= 0
    result[positive] = 1.0 / (1.0 + np.exp(-x[positive]))
    exp_x = np.exp(x[~positive])
    result[~positive] = exp_x / (1.0 + exp_x)
    return result


def logits_nll(logits: np.ndarray, gold: np.ndarray) -> float:
    x = np.asarray(logits, dtype=np.float64)
    y = np.asarray(gold, dtype=np.float64)
    return float(np.mean(np.maximum(x, 0.0) - x * y + np.log1p(np.exp(-np.abs(x)))))


def probability_nll(probabilities: np.ndarray, gold: np.ndarray) -> float:
    p = np.clip(np.asarray(probabilities, dtype=np.float64), 1e-12, 1.0 - 1e-12)
    y = np.asarray(gold, dtype=np.float64)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log1p(-p)))


def brier(probabilities: np.ndarray, gold: np.ndarray) -> float:
    return float(np.mean((np.asarray(probabilities, dtype=np.float64) - gold) ** 2))


def fit_temperature(logits: np.ndarray, gold: np.ndarray, config: dict[str, Any]) -> dict[str, Any]:
    settings = config["calibration"]
    low, high = (float(value) for value in settings["temperature_bounds"])

    def objective(log_t: float) -> float:
        return logits_nll(logits / math.exp(log_t), gold)

    result = minimize_scalar(
        objective,
        bounds=(math.log(low), math.log(high)),
        method="bounded",
        options={
            "xatol": float(settings["optimizer_tolerance"]),
            "maxiter": int(settings["optimizer_max_iterations"]),
        },
    )
    temperature = float(math.exp(float(result.x)))
    return {
        "temperature": temperature,
        "objective_nll": float(result.fun),
        "success": bool(result.success),
        "iterations": int(result.nfev),
        "at_lower_bound": temperature <= low * (1.0 + 1e-6),
        "at_upper_bound": temperature >= high * (1.0 - 1e-6),
    }


def classification(gold: np.ndarray, prediction: np.ndarray) -> dict[str, Any]:
    y = np.asarray(gold, dtype=np.uint8)
    pred = np.asarray(prediction, dtype=np.uint8)
    per_label: dict[str, Any] = {}
    f1_values: list[float] = []
    tp_total = fp_total = fn_total = 0
    for index, label in enumerate(LABELS):
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
    return {
        "rows": int(y.shape[0]),
        "macro_f1": float(np.mean(f1_values)),
        "five_label_macro_f1": float(np.mean([value for index, value in enumerate(f1_values) if index != 2])),
        "micro_f1": float(micro_f1),
        "hamming_loss": float(np.mean(y != pred)),
        "subset_accuracy": float(np.mean(np.all(y == pred, axis=1))),
        "subset_error": float(1.0 - np.mean(np.all(y == pred, axis=1))),
        "per_label": per_label,
    }


def choose_threshold(probabilities: np.ndarray, gold: np.ndarray, grid: list[float]) -> dict[str, Any]:
    candidates = []
    for threshold in grid:
        metrics = classification(gold, (probabilities >= threshold).astype(np.uint8))
        candidates.append({
            "threshold": float(threshold),
            "macro_f1": metrics["macro_f1"],
            "hamming_loss": metrics["hamming_loss"],
        })
    best_macro = max(row["macro_f1"] for row in candidates)
    tied = [row for row in candidates if abs(row["macro_f1"] - best_macro) <= 1e-12]
    best_hamming = min(row["hamming_loss"] for row in tied)
    tied = [row for row in tied if abs(row["hamming_loss"] - best_hamming) <= 1e-12]
    return sorted(tied, key=lambda row: (abs(row["threshold"] - 0.5), row["threshold"]))[0]


def equal_frequency(probabilities: np.ndarray, gold: np.ndarray, bins: int) -> tuple[float, list[dict[str, Any]]]:
    p = np.asarray(probabilities, dtype=np.float64).reshape(-1)
    y = np.asarray(gold, dtype=np.float64).reshape(-1)
    order = np.argsort(p, kind="stable")
    records = []
    weighted = 0.0
    for bin_index, indices in enumerate(np.array_split(order, bins), start=1):
        confidence = float(np.mean(p[indices]))
        frequency = float(np.mean(y[indices]))
        gap = abs(confidence - frequency)
        weighted += len(indices) * gap
        records.append({
            "bin": bin_index,
            "count": int(len(indices)),
            "mean_confidence": confidence,
            "empirical_positive_rate": frequency,
            "absolute_gap": float(gap),
            "minimum_probability": float(np.min(p[indices])),
            "maximum_probability": float(np.max(p[indices])),
        })
    return float(weighted / len(order)), records


def calibration(probabilities: np.ndarray, gold: np.ndarray, bins: int) -> tuple[dict[str, float], list[dict[str, Any]]]:
    micro_ece, records = equal_frequency(probabilities, gold, bins)
    classwise = [equal_frequency(probabilities[:, index], gold[:, index], bins)[0] for index in range(6)]
    return ({
        "nll": probability_nll(probabilities, gold),
        "brier": brier(probabilities, gold),
        "micro_ece": micro_ece,
        "macro_classwise_ece": float(np.mean(classwise)),
    }, records)


def crossfit_family(logits: np.ndarray, gold: np.ndarray, folds: np.ndarray, config: dict[str, Any]) -> dict[str, Any]:
    grid = [float(value) for value in config["thresholds"]["grid"]]
    raw = sigmoid(logits)
    temperature_probabilities = np.empty_like(raw)
    raw_thresholds = np.empty(len(gold), dtype=np.float64)
    temperature_thresholds = np.empty(len(gold), dtype=np.float64)
    fold_fits = []
    for fold_id in config["cross_fitting"]["fold_ids"]:
        train = folds != fold_id
        heldout = folds == fold_id
        fit = fit_temperature(logits[train], gold[train], config)
        temperature_probabilities[heldout] = sigmoid(logits[heldout] / fit["temperature"])
        raw_selection = choose_threshold(raw[train], gold[train], grid)
        temperature_selection = choose_threshold(
            sigmoid(logits[train] / fit["temperature"]), gold[train], grid
        )
        raw_thresholds[heldout] = raw_selection["threshold"]
        temperature_thresholds[heldout] = temperature_selection["threshold"]
        fold_fits.append({
            "fold_id": int(fold_id),
            "meta_train_rows": int(np.sum(train)),
            "heldout_rows": int(np.sum(heldout)),
            "temperature_fit": fit,
            "raw_threshold_selection": raw_selection,
            "temperature_threshold_selection": temperature_selection,
        })
    bins = int(config["calibration"]["ece_bins"])
    raw_calibration, raw_reliability = calibration(raw, gold, bins)
    temperature_calibration, temperature_reliability = calibration(temperature_probabilities, gold, bins)
    deltas = {
        "nll": temperature_calibration["nll"] - raw_calibration["nll"],
        "brier": temperature_calibration["brier"] - raw_calibration["brier"],
    }
    accepted = (
        deltas["nll"] <= -float(config["calibration"]["minimum_nll_improvement"])
        and deltas["brier"] <= float(config["calibration"]["maximum_brier_worsening"])
    )
    raw_prediction = (raw >= raw_thresholds[:, None]).astype(np.uint8)
    temperature_prediction = (temperature_probabilities >= temperature_thresholds[:, None]).astype(np.uint8)
    selected_probabilities = temperature_probabilities if accepted else raw
    selected_thresholds = temperature_thresholds if accepted else raw_thresholds
    selected_prediction = temperature_prediction if accepted else raw_prediction
    full_fit = fit_temperature(logits, gold, config)
    final_temperature = full_fit["temperature"] if accepted else 1.0
    final_selection = choose_threshold(sigmoid(logits / final_temperature), gold, grid)
    return {
        "raw_probabilities": raw,
        "temperature_probabilities": temperature_probabilities,
        "selected_probabilities": selected_probabilities,
        "raw_thresholds": raw_thresholds,
        "temperature_thresholds": temperature_thresholds,
        "selected_thresholds": selected_thresholds,
        "selected_prediction": selected_prediction,
        "fold_fits": fold_fits,
        "raw_calibration": raw_calibration,
        "temperature_calibration": temperature_calibration,
        "raw_reliability": raw_reliability,
        "temperature_reliability": temperature_reliability,
        "temperature_accepted": bool(accepted),
        "calibration_deltas": {key: float(value) for key, value in deltas.items()},
        "full_fit": full_fit,
        "final_temperature": float(final_temperature),
        "final_threshold_selection": final_selection,
        "classification": {
            "raw_fixed_0_5": classification(gold, (raw >= 0.5).astype(np.uint8)),
            "raw_cross_fitted_threshold": classification(gold, raw_prediction),
            "temperature_fixed_0_5": classification(gold, (temperature_probabilities >= 0.5).astype(np.uint8)),
            "temperature_cross_fitted_threshold": classification(gold, temperature_prediction),
            "selected_cross_fitted_threshold": classification(gold, selected_prediction),
        },
    }


def uncertainty(probabilities: np.ndarray, thresholds: np.ndarray) -> dict[str, np.ndarray]:
    p = np.clip(probabilities.astype(np.float64), 1e-12, 1.0 - 1e-12)
    entropy = -(p * np.log(p) + (1.0 - p) * np.log1p(-p))
    return {
        "mean_entropy": np.mean(entropy, axis=1),
        "max_entropy": np.max(entropy, axis=1),
        "margin": -np.min(np.abs(p - thresholds[:, None]), axis=1),
    }


def accept_mask(scores: np.ndarray, folds: np.ndarray, sample_ids: np.ndarray, coverage: float) -> np.ndarray:
    accepted = np.zeros(len(scores), dtype=bool)
    for fold_id in sorted(int(value) for value in np.unique(folds)):
        indices = np.flatnonzero(folds == fold_id)
        count = int(math.floor(coverage * len(indices) + 0.5))
        order = np.lexsort((sample_ids[indices], scores[indices]))
        accepted[indices[order[:count]]] = True
    return accepted


def retention(family: str, method: str, coverage: float, gold: np.ndarray, accepted: np.ndarray) -> list[dict[str, Any]]:
    rows = []
    for index, label in enumerate(LABELS):
        support = int(np.sum(gold[:, index] == 1))
        retained = int(np.sum((gold[:, index] == 1) & accepted))
        rows.append({
            "family": family,
            "method": method,
            "target_coverage": coverage,
            "label": label,
            "positive_support": support,
            "retained_positive": retained,
            "positive_retention": retained / support if support else 0.0,
        })
    return rows


def selective(family: str, gold: np.ndarray, prediction: np.ndarray, scores: dict[str, np.ndarray], folds: np.ndarray, sample_ids: np.ndarray, config: dict[str, Any]) -> dict[str, Any]:
    coverages = [float(value) for value in config["selective_prediction"]["coverages"]]
    risk_rows = []
    retention_rows = []
    masks = {}
    for method in METHODS:
        for coverage in coverages:
            mask = accept_mask(scores[method], folds, sample_ids, coverage)
            masks[f"{method}__{str(coverage).replace('.', '_')}"] = mask
            metrics = classification(gold[mask], prediction[mask])
            risk_rows.append({
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
            })
            retention_rows.extend(retention(family, method, coverage, gold, mask))
    repetitions = int(config["selective_prediction"]["random_repetitions"])
    base_seed = int(config["selective_prediction"]["random_seed"])
    family_offset = 0 if family == "m1" else 1_000_000
    random_rows = []
    random_lookup = {}
    for coverage_index, coverage in enumerate(coverages):
        values = {name: [] for name in ("hamming_risk", "macro_f1", "five_label_macro_f1")}
        accepted_count = 0
        for repetition in range(repetitions):
            rng = np.random.default_rng(base_seed + family_offset + coverage_index * 10_000 + repetition)
            mask = np.zeros(len(gold), dtype=bool)
            for fold_id in sorted(int(value) for value in np.unique(folds)):
                indices = np.flatnonzero(folds == fold_id)
                count = int(math.floor(coverage * len(indices) + 0.5))
                mask[rng.permutation(indices)[:count]] = True
            accepted_count = int(np.sum(mask))
            metrics = classification(gold[mask], prediction[mask])
            values["hamming_risk"].append(metrics["hamming_loss"])
            values["macro_f1"].append(metrics["macro_f1"])
            values["five_label_macro_f1"].append(metrics["five_label_macro_f1"])
        for metric, metric_values in values.items():
            array = np.asarray(metric_values, dtype=np.float64)
            row = {
                "family": family,
                "target_coverage": coverage,
                "actual_coverage": accepted_count / len(gold),
                "accepted_rows": accepted_count,
                "metric": metric,
                "mean": float(np.mean(array)),
                "p2_5": float(np.percentile(array, 2.5)),
                "p5": float(np.percentile(array, 5.0)),
                "p50": float(np.percentile(array, 50.0)),
                "p95": float(np.percentile(array, 95.0)),
                "p97_5": float(np.percentile(array, 97.5)),
            }
            random_rows.append(row)
            if metric == "hamming_risk":
                random_lookup[coverage] = row
    full_metrics = classification(gold, prediction)
    retention_lookup = {
        (row["method"], row["target_coverage"], row["label"]): row["positive_retention"]
        for row in retention_rows
    }
    candidates = []
    for row in risk_rows:
        coverage = float(row["target_coverage"])
        if coverage < float(config["selective_prediction"]["gate_minimum_coverage"]) or coverage >= 1.0:
            continue
        reduction = (
            (full_metrics["hamming_loss"] - row["hamming_risk"]) / full_metrics["hamming_loss"]
            if full_metrics["hamming_loss"] > 0 else 0.0
        )
        min_retention = min(
            retention_lookup[(row["method"], coverage, label)] for label in LABELS if label != "surprise"
        )
        checks = {
            "hamming_relative_reduction": reduction >= float(config["selective_prediction"]["gate_hamming_relative_reduction"]),
            "five_label_macro_f1": row["five_label_macro_f1"] >= full_metrics["five_label_macro_f1"] - float(config["selective_prediction"]["gate_max_five_label_macro_drop"]),
            "non_surprise_positive_retention": min_retention >= float(config["selective_prediction"]["gate_min_non_surprise_retention"]),
            "better_than_random": row["hamming_risk"] < random_lookup[coverage]["p5"],
        }
        candidates.append({
            **row,
            "hamming_relative_reduction": float(reduction),
            "minimum_non_surprise_positive_retention": float(min_retention),
            "random_hamming_p5": float(random_lookup[coverage]["p5"]),
            "checks": checks,
            "qualifies": bool(all(checks.values())),
        })
    qualifying = [row for row in candidates if row["qualifies"]]
    selected = None
    if qualifying:
        method_rank = {name: index for index, name in enumerate(METHODS)}
        selected = sorted(qualifying, key=lambda row: (-row["hamming_relative_reduction"], -row["target_coverage"], method_rank[row["method"]]))[0]
    cutoffs = []
    for method in METHODS:
        for coverage in coverages:
            order = np.lexsort((sample_ids, scores[method]))
            count = int(math.floor(coverage * len(order) + 0.5))
            cutoff = float(scores[method][order[count - 1]]) if count else float("-inf")
            cutoffs.append({
                "method": method,
                "target_coverage": coverage,
                "accepted_rows": count,
                "score_cutoff": cutoff,
                "online_tie_policy": "accept_score_below_cutoff_then_sample_id_order_for_boundary_ties",
            })
    return {
        "risk_rows": risk_rows,
        "retention_rows": retention_rows,
        "random_rows": random_rows,
        "masks": masks,
        "gate": {
            "passed": selected is not None,
            "selected_operating_point": selected,
            "evaluated_candidates": candidates,
            "full_coverage_metrics": full_metrics,
        },
        "full_oof_cutoffs": cutoffs,
    }


def oracle(gold: np.ndarray, m1: np.ndarray, m3: np.ndarray, minimum_gain: float) -> tuple[dict[str, Any], np.ndarray]:
    choose_m3 = np.sum(m3 != gold, axis=1) < np.sum(m1 != gold, axis=1)
    combined = np.where(choose_m3[:, None], m3, m1)
    m1_metrics = classification(gold, m1)
    m3_metrics = classification(gold, m3)
    combined_metrics = classification(gold, combined)
    six_gain = combined_metrics["macro_f1"] - m1_metrics["macro_f1"]
    five_gain = combined_metrics["five_label_macro_f1"] - m1_metrics["five_label_macro_f1"]
    return ({
        "m1": m1_metrics,
        "m3": m3_metrics,
        "whole_vector_oracle": combined_metrics,
        "m3_selected_rows": int(np.sum(choose_m3)),
        "m3_selection_rate": float(np.mean(choose_m3)),
        "macro_f1_gain_over_m1": float(six_gain),
        "five_label_macro_f1_gain_over_m1": float(five_gain),
        "router_headroom_gate": {
            "minimum_gain": minimum_gain,
            "passed": bool(not (six_gain < minimum_gain and five_gain < minimum_gain)),
            "surprise_only_or_low_support_warning": bool(six_gain >= minimum_gain and five_gain < minimum_gain),
            "claim_boundary": "Non-deployable whole-vector oracle; not a router result.",
        },
    }, choose_m3)


def component_groups(component_ids: np.ndarray) -> list[np.ndarray]:
    grouped: dict[str, list[int]] = {}
    for index, component in enumerate(component_ids.tolist()):
        grouped.setdefault(str(component), []).append(index)
    return [np.asarray(grouped[key], dtype=np.int64) for key in sorted(grouped)]


def interval(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "mean": float(np.mean(array)),
        "lower_95": float(np.percentile(array, 2.5)),
        "upper_95": float(np.percentile(array, 97.5)),
    }


def bootstrap(gold: np.ndarray, component_ids: np.ndarray, families: dict[str, dict[str, Any]], selective_results: dict[str, dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    repetitions = int(config["bootstrap"]["repetitions"])
    rng = np.random.default_rng(int(config["bootstrap"]["seed"]))
    groups = component_groups(component_ids)
    calibration_values = {family: {"nll_delta": [], "brier_delta": []} for family in FAMILIES}
    oracle_six: list[float] = []
    oracle_five: list[float] = []
    gate_reductions = {family: [] for family in FAMILIES if selective_results[family]["gate"]["passed"]}
    gate_masks = {}
    for family in gate_reductions:
        selected = selective_results[family]["gate"]["selected_operating_point"]
        gate_masks[family] = selective_results[family]["masks"][f"{selected['method']}__{str(selected['target_coverage']).replace('.', '_')}"]
    for _ in range(repetitions):
        sampled = rng.integers(0, len(groups), size=len(groups))
        indices = np.concatenate([groups[index] for index in sampled])
        sampled_gold = gold[indices]
        for family in FAMILIES:
            raw = families[family]["raw_probabilities"][indices]
            calibrated = families[family]["temperature_probabilities"][indices]
            calibration_values[family]["nll_delta"].append(probability_nll(calibrated, sampled_gold) - probability_nll(raw, sampled_gold))
            calibration_values[family]["brier_delta"].append(brier(calibrated, sampled_gold) - brier(raw, sampled_gold))
        oracle_result, _ = oracle(
            sampled_gold,
            families["m1"]["selected_prediction"][indices],
            families["m3"]["selected_prediction"][indices],
            0.01,
        )
        oracle_six.append(oracle_result["macro_f1_gain_over_m1"])
        oracle_five.append(oracle_result["five_label_macro_f1_gain_over_m1"])
        for family, values in gate_reductions.items():
            prediction = families[family]["selected_prediction"][indices]
            mask = gate_masks[family][indices]
            full_risk = classification(sampled_gold, prediction)["hamming_loss"]
            if np.any(mask) and full_risk > 0:
                selective_risk = classification(sampled_gold[mask], prediction[mask])["hamming_loss"]
                values.append((full_risk - selective_risk) / full_risk)
    return {
        "repetitions": repetitions,
        "seed": int(config["bootstrap"]["seed"]),
        "unit": "duplicate_component",
        "component_count": len(groups),
        "calibration_deltas": {
            family: {metric: interval(values) for metric, values in calibration_values[family].items()}
            for family in FAMILIES
        },
        "oracle_gains": {
            "macro_f1": interval(oracle_six),
            "five_label_macro_f1": interval(oracle_five),
        },
        "selected_abstention_hamming_relative_reduction": {
            family: interval(values) for family, values in gate_reductions.items()
        },
        "selection_warning": "Intervals do not correct for uncertainty-method selection.",
    }


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
    for family in FAMILIES:
        result = family_results[family]
        document["families"][family] = {
            "fold_fits": result["fold_fits"],
            "full_oof_temperature_fit": result["full_fit"],
            "selected_calibrator": "temperature" if result["temperature_accepted"] else "identity",
            "final_temperature": result["final_temperature"],
            "final_global_threshold": result["final_threshold_selection"],
        }
    return document


def expected_results(data: dict[str, np.ndarray], config: dict[str, Any]) -> dict[str, Any]:
    gold = data["gold"]
    folds = data["fold_ids"]
    family_results = {
        family: crossfit_family(data[f"{family}_logits"], gold, folds, config)
        for family in FAMILIES
    }
    reliability_rows = []
    calibration_public = {"families": {}}
    parameters_public = calibration_parameters_document(config, family_results)
    classification_public = {"families": {}}
    selective_results = {}
    risk_rows = []
    retention_rows = []
    random_rows = []
    gates_public = {"families": {}}
    private_arrays = {
        name: data[name]
        for name in ("sample_ids", "component_ids", "fold_ids", "gold", "character_lengths", "m1_token_lengths", "m3_token_lengths")
    }
    for family in FAMILIES:
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
        for pipeline, rows in (("identity", result["raw_reliability"]), ("temperature", result["temperature_reliability"])):
            reliability_rows.extend({"family": family, "pipeline": pipeline, **row} for row in rows)
        scores = uncertainty(result["selected_probabilities"], result["selected_thresholds"])
        selected = selective(family, gold, result["selected_prediction"], scores, folds, data["sample_ids"], config)
        selective_results[family] = selected
        risk_rows.extend(selected["risk_rows"])
        retention_rows.extend(selected["retention_rows"])
        random_rows.extend(selected["random_rows"])
        gates_public["families"][family] = {
            **selected["gate"],
            "full_oof_uncertainty_cutoffs": selected["full_oof_cutoffs"],
        }
        private_arrays[f"{family}_temperature_probabilities"] = result["temperature_probabilities"].astype(np.float64)
        private_arrays[f"{family}_selected_probabilities"] = result["selected_probabilities"].astype(np.float64)
        private_arrays[f"{family}_raw_thresholds"] = result["raw_thresholds"].astype(np.float64)
        private_arrays[f"{family}_temperature_thresholds"] = result["temperature_thresholds"].astype(np.float64)
        private_arrays[f"{family}_selected_thresholds"] = result["selected_thresholds"].astype(np.float64)
        private_arrays[f"{family}_selected_prediction"] = result["selected_prediction"].astype(np.uint8)
        for method, values in scores.items():
            private_arrays[f"{family}_uncertainty_{method}"] = values.astype(np.float64)
        for key, mask in selected["masks"].items():
            private_arrays[f"{family}_accept_{key}"] = mask.astype(np.uint8)
    oracle_public, choose_m3 = oracle(
        gold,
        family_results["m1"]["selected_prediction"],
        family_results["m3"]["selected_prediction"],
        float(config["oracle"]["minimum_macro_gain"]),
    )
    private_arrays["oracle_choose_m3"] = choose_m3.astype(np.uint8)
    return {
        "parameters": parameters_public,
        "calibration": calibration_public,
        "classification": classification_public,
        "gates": gates_public,
        "oracle": oracle_public,
        "bootstrap": bootstrap(gold, data["component_ids"], family_results, selective_results, config),
        "reliability_rows": reliability_rows,
        "risk_rows": risk_rows,
        "retention_rows": retention_rows,
        "random_rows": random_rows,
        "private_arrays": private_arrays,
    }


def validate_data(checks: Checks, data: dict[str, np.ndarray], config: dict[str, Any]) -> None:
    checks.add("data.keys", set(data) == set(expected_schema()), sorted(data))
    checks.add("data.unique_sample_ids", len(set(data["sample_ids"].tolist())) == 3360)
    checks.add("data.binary_gold", bool(np.all(np.isin(data["gold"], [0, 1]))))
    checks.add("data.finite_m1", bool(np.all(np.isfinite(data["m1_logits"]))))
    checks.add("data.finite_m3", bool(np.all(np.isfinite(data["m3_logits"]))))
    checks.add("data.fold_ids", sorted(np.unique(data["fold_ids"]).tolist()) == config["cross_fitting"]["fold_ids"])
    for fold_id in config["cross_fitting"]["fold_ids"]:
        checks.add(f"data.fold_{fold_id}_rows", int(np.sum(data["fold_ids"] == fold_id)) == 672)
    component_folds: dict[str, set[int]] = {}
    for component, fold in zip(data["component_ids"].tolist(), data["fold_ids"].tolist()):
        component_folds.setdefault(str(component), set()).add(int(fold))
    checks.add("data.component_fold_disjoint", all(len(value) == 1 for value in component_folds.values()))


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as source:
        header = source.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"Invalid PNG: {path}")
    return struct.unpack(">II", header[16:24])


def expected_report_text(expected: dict[str, Any], config: dict[str, Any]) -> str:
    calibration = expected["calibration"]
    classification = expected["classification"]
    gates = expected["gates"]
    oracle = expected["oracle"]
    bootstrap = expected["bootstrap"]
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
    for family in FAMILIES:
        item = calibration["families"][family]
        lines.append(
            f"| {family.upper()} | {item['identity']['nll']:.6f} | "
            f"{item['temperature_cross_fitted']['nll']:.6f} | {item['identity']['brier']:.6f} | "
            f"{item['temperature_cross_fitted']['brier']:.6f} | {item['selected_calibrator']} | "
            f"{item['final_temperature']:.6f} |"
        )
    lines.extend([
        "",
        "## Selected Classification",
        "",
        "| Family | Macro-F1 | Five-label Macro-F1 | Micro-F1 | Hamming loss | Subset accuracy |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for family in FAMILIES:
        metrics = classification["families"][family]["selected_cross_fitted_threshold"]
        lines.append(
            f"| {family.upper()} | {metrics['macro_f1']:.6f} | {metrics['five_label_macro_f1']:.6f} | "
            f"{metrics['micro_f1']:.6f} | {metrics['hamming_loss']:.6f} | {metrics['subset_accuracy']:.6f} |"
        )
    lines.extend(["", "## Abstention Gates", ""])
    for family in FAMILIES:
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
    return "\n".join(lines)


def report_private_identifier_leaks(
    report_text: str, data: dict[str, np.ndarray]
) -> list[str]:
    private_tokens = {
        str(value)
        for name in ("sample_ids", "component_ids")
        for value in data[name].tolist()
    }
    return sorted(token for token in private_tokens if token and token in report_text)


def make_expected_figures(
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
    for axis, family in zip(axes, FAMILIES):
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
    for axis, family in zip(axes, FAMILIES):
        for method in METHODS:
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


def peak_rss_gb() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value / 1_000_000_000 if platform.system() == "Darwin" else value * 1024 / 1_000_000_000


def verification_resources(started: float) -> dict[str, Any]:
    return {
        "wall_seconds": float(time.monotonic() - started),
        "peak_process_rss_gb": peak_rss_gb(),
        "api_cost_usd": 0,
    }


def verification_result(
    scope: str,
    checks: Checks,
    config: dict[str, Any],
    resources: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "exp-059-verification-v2" if is_v2(config) else "exp-059-verification-v1",
        **identity_provenance(config),
        "rq_id": RQ_ID,
        "scope": scope,
        "status": "Passed" if not checks.failed else "Failed",
        "verified_at_utc": utc_now(),
        "passed_count": len(checks.rows) - len(checks.failed),
        "failed_count": len(checks.failed),
        "checks": checks.rows,
        "resources": resources,
    }


def render_summary(result: dict[str, Any]) -> str:
    failed = [row for row in result["checks"] if not row["passed"]]
    lines = [
        f"# EXP-059 {result['scope'].title()} Verification",
        "",
        f"- Status: `{result['status']}`",
        f"- Passed checks: `{result['passed_count']}`",
        f"- Failed checks: `{result['failed_count']}`",
        "",
    ]
    if failed:
        lines.extend(["## Failures", ""])
        lines.extend(f"- `{row['name']}`: `{row['detail']}`" for row in failed[:50])
    else:
        lines.extend([
            "The frozen inputs, split boundary, independent recomputation, public privacy boundary, and output hashes passed.",
            "",
        ])
    return "\n".join(lines)


def validate_verification_document(
    result: dict[str, Any],
    config: dict[str, Any],
    scope: str,
    config_record: dict[str, Any] | None,
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
    }
    if is_v2(config):
        expected_keys |= {"config", "verified_artifacts"}
    if set(result) != expected_keys:
        raise ValueError("EXP-059 verification top-level schema drift")
    try:
        verified_at = datetime.fromisoformat(result["verified_at_utc"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("EXP-059 verification timestamp drift") from error
    checks = result.get("checks")
    if not isinstance(checks, list) or any(
        not isinstance(row, dict)
        or set(row) != {"name", "passed", "detail"}
        or not isinstance(row["name"], str)
        or not isinstance(row["passed"], bool)
        for row in checks
    ):
        raise ValueError("EXP-059 verification check schema drift")
    failed = sum(not row["passed"] for row in checks)
    passed = len(checks) - failed
    check_names = [row["name"] for row in checks]
    required_checks = (
        PREFLIGHT_VERIFICATION_REQUIRED_CHECKS
        if scope == "preflight"
        else FINAL_COMPLETION_REQUIRED_CHECKS
    )
    expected_schema = "exp-059-verification-v2" if is_v2(config) else "exp-059-verification-v1"
    if (
        result.get("schema_version") != expected_schema
        or result.get("rq_id") != RQ_ID
        or result.get("scope") != scope
        or result.get("passed_count") != passed
        or result.get("failed_count") != failed
        or result.get("status") != ("Passed" if failed == 0 else "Failed")
        or any(result.get(key) != value for key, value in identity_provenance(config).items())
        or verified_at.tzinfo is None
        or len(check_names) != len(set(check_names))
        or not required_checks.issubset(check_names)
    ):
        raise ValueError("EXP-059 verification result schema or identity drift")
    resources = result.get("resources")
    if (
        not isinstance(resources, dict)
        or set(resources) != {"wall_seconds", "peak_process_rss_gb", "api_cost_usd"}
        or not isinstance(resources["wall_seconds"], (int, float))
        or not isinstance(resources["peak_process_rss_gb"], (int, float))
        or isinstance(resources["wall_seconds"], bool)
        or isinstance(resources["peak_process_rss_gb"], bool)
        or not math.isfinite(float(resources["wall_seconds"]))
        or not math.isfinite(float(resources["peak_process_rss_gb"]))
        or resources["wall_seconds"] < 0
        or resources["peak_process_rss_gb"] < 0
        or resources["api_cost_usd"] != 0
        or resources["wall_seconds"]
        > float(config["resources"]["verification_wall_seconds"])
        or resources["peak_process_rss_gb"]
        > float(config["resources"]["peak_memory_gb"])
    ):
        raise ValueError("EXP-059 verifier resource accounting drift")
    if is_v2(config) and result.get("config") != config_record:
        raise ValueError("EXP-059 verification is not bound to the current config")
    if is_v2(config):
        expected_verified_keys = (
            {"config", "run", "paired_oof"}
            if scope == "preflight"
            else {
                "config",
                "run",
                "calibration_parameters",
                "paired_oof",
                "private_output",
                "public_outputs",
                "frozen_sources",
            }
        )
        verified = result.get("verified_artifacts")
        if not isinstance(verified, dict) or set(verified) != expected_verified_keys:
            raise ValueError("EXP-059 verified artifact inventory drift")


def resume_verification_bundle(
    output: Path,
    summary: Path,
    config: dict[str, Any],
    scope: str,
    config_record: dict[str, Any] | None,
) -> dict[str, Any] | None:
    output_exists = os.path.lexists(output)
    summary_exists = os.path.lexists(summary)
    if summary_exists and not output_exists:
        raise FileExistsError("Orphan EXP-059 verification summary cannot be resumed")
    if not output_exists:
        return None
    output_mode = os.lstat(output).st_mode
    if stat.S_ISLNK(output_mode) or not stat.S_ISREG(output_mode):
        raise ValueError("EXP-059 verification output must be a regular file")
    result = json.loads(output.read_text(encoding="utf-8"))
    validate_verification_document(result, config, scope, config_record)
    if is_v2(config):
        for record in iter_records(result["verified_artifacts"]):
            require_record(record)
    expected_summary = render_summary(result)
    if summary_exists:
        summary_mode = os.lstat(summary).st_mode
        if stat.S_ISLNK(summary_mode) or not stat.S_ISREG(summary_mode):
            raise ValueError("EXP-059 verification summary must be a regular file")
        if summary.read_text(encoding="utf-8") != expected_summary:
            raise ValueError("EXP-059 verification summary drift")
    else:
        create_text_once(summary, expected_summary)
    return result


def _create_calibration_completion(
    config: dict[str, Any],
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    if not is_v2(config):
        raise PermissionError("Calibration completion applies only to config-v2")
    completion = {
        "schema_version": "exp-059-calibration-completion-v2",
        **identity_provenance(config),
        "status": "Complete",
        "completed_at_utc": utc_now(),
        "artifacts": artifacts,
        "next_gate": "Identity-nested EXP-060 must pass before final attempt selection.",
        "claim_boundary": "Completes only the seed-specific EXP-059 diagnostic stage.",
    }
    create_json_once(output_paths(config)["completion"], completion)
    return completion


def validate_existing_completion(
    completion: dict[str, Any],
    config: dict[str, Any],
    expected_artifacts: dict[str, Any],
) -> None:
    expected_keys = {
        "schema_version",
        *identity_provenance(config),
        "status",
        "completed_at_utc",
        "artifacts",
        "next_gate",
        "claim_boundary",
    }
    try:
        completed_at = datetime.fromisoformat(completion["completed_at_utc"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("EXP-059 completion timestamp drift") from error
    if (
        set(completion) != expected_keys
        or completion.get("schema_version") != "exp-059-calibration-completion-v2"
        or any(
            completion.get(key) != value
            for key, value in identity_provenance(config).items()
        )
        or completion.get("status") != "Complete"
        or completed_at.tzinfo is None
        or completion.get("artifacts") != expected_artifacts
        or completion.get("next_gate")
        != "Identity-nested EXP-060 must pass before final attempt selection."
        or completion.get("claim_boundary")
        != "Completes only the seed-specific EXP-059 diagnostic stage."
    ):
        raise ValueError("EXP-059 immutable completion provenance drift")


def verify_preflight(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    paths = output_paths(config)
    run_dir = paths["preflight"]
    output = run_dir / "verification.json"
    summary = run_dir / "VERIFICATION-SUMMARY.md"
    config_record = artifact(config_path) if is_v2(config) else None
    resumed = resume_verification_bundle(
        output, summary, config, "preflight", config_record
    )
    if resumed is not None:
        if is_v2(config):
            assert_exact_public_tree(run_dir, config, stage="preflight", verified=True)
        return resumed
    if is_v2(config):
        if os.path.lexists(paths["selection"]) or os.path.lexists(paths["completion"]):
            raise FileExistsError("A selected or completed attempt blocks EXP-059 preflight verification")
        assert_exact_public_tree(run_dir, config, stage="preflight", verified=False)
    checks = Checks()
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    input_path = require_record(config["input"]["paired_oof"])
    schema = npz_header_schema(input_path)
    verification_key = "oof_verification" if is_v2(config) else "exp058_verification"
    exp058 = json.loads(require_record(
        config["prerequisites"][verification_key]
    ).read_text(encoding="utf-8"))
    checks.add(
        "preflight.identity",
        run.get("rq_id") == RQ_ID
        and all(run.get(key) == value for key, value in identity_provenance(config).items()),
    )
    checks.add("preflight.status", run.get("status") == "CompletedAwaitingVerification")
    checks.add("preflight.header_schema", schema == expected_schema(), schema)
    checks.add("preflight.public_schema", run.get("input_schema") == public_schema_records(schema))
    checks.add(
        "preflight.exp058_passed",
        exp058.get("status") == "Passed"
        and exp058.get("failed_count") == 0
        and (is_v2(config) or exp058.get("passed_count") == 26989),
    )
    checks.add("preflight.no_values", run.get("array_values_loaded") is False)
    checks.add("preflight.no_metrics", run.get("performance_metrics_computed") is False)
    checks.add("preflight.no_analysis", run.get("formal_analysis_performed") is False)
    checks.add("preflight.no_validation", run["split_access"].get("validation_accessed") is False)
    checks.add("preflight.no_test_inputs", run["split_access"].get("test_inputs_accessed") is False)
    checks.add("preflight.no_test_labels", run["split_access"].get("test_labels_accessed") is False)
    checks.add("preflight.header_only_split", run["split_access"].get("accessed_splits") == ["train-oof-header"])
    checks.add("preflight.input_bound", run.get("input") == artifact(input_path))
    checks.add("preflight.privacy", not public_sensitive_paths(run), public_sensitive_paths(run))
    checks.add("preflight.formal_public_absent", not paths["public_calibration"].exists())
    checks.add("preflight.formal_private_absent", not paths["private_calibration"].exists())
    if is_v2(config):
        try:
            oof_prerequisites(config)
            checks.add("preflight.oof_prerequisites", True)
        except (KeyError, OSError, ValueError, TypeError) as error:
            checks.add("preflight.oof_prerequisites", False, str(error))
        checks.add("preflight.config", run.get("config") == config_record)
        checks.add("preflight.no_selection", not paths["selection"].exists())
        checks.add("preflight.no_completion", not paths["completion"].exists())
    checks.add("preflight.runtime", all(run["dependencies"].get(name) != "not-installed" for name in ("numpy", "scipy", "matplotlib")))
    try:
        frozen_sources = expected_frozen_source_records(
            run_dir, config, config_record if config_record is not None else artifact(config_path)
        )
        checks.add("preflight.frozen_sources", run.get("frozen_sources") == frozen_sources)
    except (KeyError, OSError, TypeError, ValueError) as error:
        checks.add("preflight.frozen_sources", False, str(error))
    resources = verification_resources(started)
    checks.add(
        "verification.resource.wall_budget",
        resources["wall_seconds"] <= float(config["resources"]["verification_wall_seconds"]),
        resources["wall_seconds"],
    )
    checks.add(
        "verification.resource.memory_budget",
        resources["peak_process_rss_gb"] <= float(config["resources"]["peak_memory_gb"]),
        resources["peak_process_rss_gb"],
    )
    checks.add("verification.resource.api_cost", resources["api_cost_usd"] == 0)
    result = verification_result("preflight", checks, config, resources)
    if is_v2(config):
        result["config"] = config_record
        result["verified_artifacts"] = {
            "config": config_record,
            "run": artifact(run_dir / "run.json"),
            "paired_oof": artifact(input_path),
        }
    create_json_once(output, result)
    create_text_once(summary, render_summary(result))
    if is_v2(config):
        assert_exact_public_tree(run_dir, config, stage="preflight", verified=True)
    return result


def verify_final(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    if is_v2(config) and not {
        "preflight_run",
        "preflight_verification",
    }.issubset(config["prerequisites"]):
        raise ValueError("Final EXP-059 v2 verification requires preflight artifacts")
    paths = output_paths(config)
    run_dir = paths["public_calibration"]
    private_dir = paths["private_calibration"]
    output = run_dir / "verification.json"
    summary = run_dir / "VERIFICATION-SUMMARY.md"
    config_record = artifact(config_path) if is_v2(config) else None
    resumed = resume_verification_bundle(output, summary, config, "final", config_record)
    if resumed is not None:
        if is_v2(config):
            assert_exact_public_tree(run_dir, config, stage="calibration", verified=True)
        return resumed
    if is_v2(config) and os.path.lexists(paths["completion"]):
        raise FileExistsError("A completed attempt cannot create a new final verification")
    if is_v2(config):
        if os.path.lexists(paths["selection"]):
            raise FileExistsError("A final selected attempt blocks EXP-059 verification")
        assert_exact_public_tree(run_dir, config, stage="calibration", verified=False)
    checks = Checks()
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    input_path = require_record(config["input"]["paired_oof"])
    with np.load(input_path, allow_pickle=False) as archive:
        data = {name: np.array(archive[name], copy=True) for name in archive.files}
    validate_data(checks, data, config)
    expected = expected_results(data, config)
    public_files = {
        "parameters": "calibration-parameters.json",
        "calibration": "calibration-metrics.json",
        "classification": "classification-metrics.json",
        "oracle": "oracle-summary.json",
        "gates": "abstention-gates.json",
        "bootstrap": "bootstrap.json",
    }
    for name, filename in public_files.items():
        actual = json.loads((run_dir / filename).read_text(encoding="utf-8"))
        compare_tree(checks, f"public.{name}", actual, expected[name])
        checks.add(f"public.{name}.privacy", not public_sensitive_paths(actual), public_sensitive_paths(actual))
    csv_files = {
        "reliability": ("reliability-bins.csv", expected["reliability_rows"]),
        "risk": ("risk-coverage.csv", expected["risk_rows"]),
        "retention": ("label-retention.csv", expected["retention_rows"]),
        "random": ("random-rejection.csv", expected["random_rows"]),
    }
    for name, (filename, expected_rows) in csv_files.items():
        compare_csv(checks, f"csv.{name}", read_csv(run_dir / filename), expected_rows)
    private_path = private_dir / "cross-fitted-calibration.npz"
    if is_v2(config):
        assert_exact_private_tree(private_dir)
    checks.add("private.root_mode", mode(private_dir) == 0o700, oct(mode(private_dir)))
    checks.add("private.file_mode", mode(private_path) == 0o600, oct(mode(private_path)))
    with np.load(private_path, allow_pickle=False) as archive:
        actual_private = {name: np.array(archive[name], copy=True) for name in archive.files}
    checks.add("private.keys", set(actual_private) == set(expected["private_arrays"]), {
        "actual": sorted(actual_private), "expected": sorted(expected["private_arrays"])
    })
    for name in sorted(set(actual_private) & set(expected["private_arrays"])):
        actual_array = actual_private[name]
        expected_array = expected["private_arrays"][name]
        checks.add(f"private.{name}.shape", actual_array.shape == expected_array.shape, {"actual": actual_array.shape, "expected": expected_array.shape})
        checks.add(f"private.{name}.dtype", actual_array.dtype == expected_array.dtype, {"actual": str(actual_array.dtype), "expected": str(expected_array.dtype)})
        if actual_array.dtype.kind in "f":
            passed = bool(np.allclose(actual_array, expected_array, rtol=0.0, atol=1e-10, equal_nan=False))
            detail = float(np.max(np.abs(actual_array - expected_array))) if actual_array.size else 0.0
        else:
            passed = bool(np.array_equal(actual_array, expected_array))
            detail = None
        checks.add(f"private.{name}.values", passed, detail)
    checks.add(
        "run.identity",
        run.get("rq_id") == RQ_ID
        and all(run.get(key) == value for key, value in identity_provenance(config).items()),
    )
    checks.add("run.status", run.get("status") == "CompletedAwaitingVerification")
    checks.add("run.rows", run.get("rows") == 3360)
    checks.add("run.folds", run.get("folds") == 5)
    checks.add("run.components", run.get("component_count") == len(component_groups(data["component_ids"])))
    checks.add("run.input_before", run.get("input_before") == artifact(input_path))
    checks.add("run.input_after", run.get("input_sha256_after") == sha256(input_path))
    checks.add("run.private_output", run.get("private_output") == artifact(private_path))
    checks.add("run.no_validation", run["split_access"].get("validation_accessed") is False)
    checks.add("run.no_test_inputs", run["split_access"].get("test_inputs_accessed") is False)
    checks.add("run.no_test_labels", run["split_access"].get("test_labels_accessed") is False)
    checks.add("run.train_oof_only", run["split_access"].get("accessed_splits") == ["train-oof"])
    checks.add("run.no_model_forward", run.get("model_loading_or_forward_performed") is False)
    checks.add("run.no_router", run.get("router_training_performed") is False)
    if is_v2(config):
        checks.add("run.config", run.get("config") == config_record)
        checks.add("run.temperature_diagnostic", run.get("temperature_adoption_role") == "diagnostic_only")
        checks.add("run.router_identity", run.get("router_replication_calibration") == {
            "calibrator": "identity",
            "temperature": 1.0,
            "probability_source": "direct_sigmoid_of_raw_oof_logits",
            "role": "frozen_exp060_replication_only",
        })
        checks.add("run.no_selection", not paths["selection"].exists())
        try:
            oof_prerequisites(config)
            checks.add("run.oof_prerequisites", True)
        except (KeyError, OSError, ValueError, TypeError) as error:
            checks.add("run.oof_prerequisites", False, str(error))
        try:
            preflight_prerequisites(config)
            checks.add("run.preflight_provenance", True)
        except (KeyError, OSError, ValueError, TypeError) as error:
            checks.add("run.preflight_provenance", False, str(error))
        for name in ("preflight_run", "preflight_verification"):
            value = json.loads(require_record(
                config["prerequisites"][name]
            ).read_text(encoding="utf-8"))
            checks.add(
                f"run.{name}.identity",
                all(
                    value.get(key) == expected
                    for key, expected in identity_provenance(config).items()
                ),
            )
            expected_status = "CompletedAwaitingVerification" if name == "preflight_run" else "Passed"
            checks.add(f"run.{name}.status", value.get("status") == expected_status)
            if name == "preflight_verification":
                checks.add(f"run.{name}.failed_count", value.get("failed_count") == 0)
    checks.add("run.privacy", not public_sensitive_paths(run), public_sensitive_paths(run))
    public_output_records = expected_public_output_records(run_dir)
    checks.add("run.public_outputs", run.get("public_outputs") == public_output_records)
    try:
        frozen_source_records = expected_frozen_source_records(
            run_dir, config, config_record if config_record is not None else artifact(config_path)
        )
        checks.add("run.frozen_sources", run.get("frozen_sources") == frozen_source_records)
    except (KeyError, OSError, TypeError, ValueError) as error:
        frozen_source_records = {}
        checks.add("run.frozen_sources", False, str(error))
    report_text = (run_dir / "REPORT.md").read_text(encoding="utf-8")
    checks.add("report.exact", report_text == expected_report_text(expected, config))
    leaked_tokens = report_private_identifier_leaks(report_text, data)
    checks.add("report.no_private_ids", not leaked_tokens, leaked_tokens[:20])
    for filename in ("reliability-diagram.png", "risk-coverage-curve.png"):
        path = run_dir / filename
        try:
            dimensions = png_dimensions(path)
            checks.add(f"figure.{filename}.dimensions", dimensions == (1600, 640), dimensions)
        except (OSError, ValueError) as error:
            checks.add(f"figure.{filename}.valid", False, str(error))
    try:
        with tempfile.TemporaryDirectory(prefix="exp059-figures-", dir="/private/tmp") as temporary:
            expected_figures = make_expected_figures(
                Path(temporary),
                expected["reliability_rows"],
                expected["risk_rows"],
                expected["random_rows"],
            )
            for generated in expected_figures:
                actual = run_dir / generated.name
                checks.add(
                    f"figure.{generated.name}.sha256",
                    sha256(actual) == sha256(generated),
                    {"actual": sha256(actual), "expected": sha256(generated)},
                )
    except (OSError, RuntimeError, ValueError) as error:
        for filename in ("reliability-diagram.png", "risk-coverage-curve.png"):
            checks.add(f"figure.{filename}.sha256", False, str(error))
    run_resources = run.get("resources", {})
    checks.add(
        "resource.accounting_schema",
        isinstance(run_resources, dict)
        and set(run_resources) == {"wall_seconds", "peak_process_rss_gb", "api_cost_usd"},
    )
    checks.add("resource.wall_budget", float(run_resources.get("wall_seconds", math.inf)) <= float(config["resources"]["formal_wall_seconds"]))
    checks.add("resource.memory_budget", float(run_resources.get("peak_process_rss_gb", math.inf)) <= float(config["resources"]["peak_memory_gb"]))
    checks.add("resource.api_cost", run_resources.get("api_cost_usd") == 0)
    for path in sorted(run_dir.iterdir()):
        if path.suffix == ".json" and path.name not in {"verification.json"}:
            value = json.loads(path.read_text(encoding="utf-8"))
            checks.add(f"privacy.{path.name}", not public_sensitive_paths(value), public_sensitive_paths(value))
    resources = verification_resources(started)
    checks.add(
        "verification.resource.wall_budget",
        resources["wall_seconds"] <= float(config["resources"]["verification_wall_seconds"]),
        resources["wall_seconds"],
    )
    checks.add(
        "verification.resource.memory_budget",
        resources["peak_process_rss_gb"] <= float(config["resources"]["peak_memory_gb"]),
        resources["peak_process_rss_gb"],
    )
    checks.add("verification.resource.api_cost", resources["api_cost_usd"] == 0)
    result = verification_result("final", checks, config, resources)
    if is_v2(config):
        result["config"] = config_record
        result["verified_artifacts"] = {
            "config": config_record,
            "run": artifact(run_dir / "run.json"),
            "calibration_parameters": artifact(run_dir / "calibration-parameters.json"),
            "paired_oof": artifact(input_path),
            "private_output": artifact(private_path),
            "public_outputs": public_output_records,
            "frozen_sources": frozen_source_records,
        }
    create_json_once(output, result)
    create_text_once(summary, render_summary(result))
    if is_v2(config):
        assert_exact_public_tree(run_dir, config, stage="calibration", verified=True)
    return result


def verify_completion(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    if not is_v2(config):
        raise PermissionError("Calibration completion applies only to config-v2")
    paths = output_paths(config)
    completion_path = paths["completion"]
    if os.path.lexists(paths["selection"]):
        raise FileExistsError("A final selected attempt blocks EXP-059 completion")
    run_dir = paths["public_calibration"]
    assert_exact_public_tree(run_dir, config, stage="calibration", verified=True)
    run_path = run_dir / "run.json"
    parameters_path = run_dir / "calibration-parameters.json"
    verification_path = run_dir / "verification.json"
    summary_path = run_dir / "VERIFICATION-SUMMARY.md"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    parameters = json.loads(parameters_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    identity = identity_provenance(config)
    config_record = artifact(config_path)
    run_record = artifact(run_path)
    parameters_record = artifact(parameters_path)
    input_path = require_record(config["input"]["paired_oof"])
    private_path = paths["private_calibration"] / "cross-fitted-calibration.npz"
    assert_exact_private_tree(paths["private_calibration"])
    if mode(paths["private_calibration"]) != 0o700 or mode(private_path) != 0o600:
        raise RuntimeError("EXP-059 private completion permissions drift")
    private_record = artifact(private_path)
    public_output_records = expected_public_output_records(run_dir)
    frozen_source_records = expected_frozen_source_records(run_dir, config, config_record)
    if (
        run.get("schema_version") != "exp-059-formal-run-v2"
        or run.get("rq_id") != RQ_ID
        or run.get("status") != "CompletedAwaitingVerification"
        or any(run.get(key) != value for key, value in identity.items())
        or run.get("config") != config_record
        or run.get("input_before") != artifact(input_path)
        or run.get("input_sha256_after") != sha256(input_path)
        or run.get("private_output") != private_record
        or run.get("public_outputs") != public_output_records
        or run.get("frozen_sources") != frozen_source_records
        or run.get("model_loading_or_forward_performed") is not False
        or run.get("router_training_performed") is not False
        or run.get("split_access")
        != {
            "accessed_splits": ["train-oof"],
            "validation_accessed": False,
            "test_inputs_accessed": False,
            "test_labels_accessed": False,
        }
    ):
        raise RuntimeError("EXP-059 completion run provenance failed")
    router_contract = {
        "calibrator": "identity",
        "temperature": 1.0,
        "probability_source": "direct_sigmoid_of_raw_oof_logits",
        "role": "frozen_exp060_replication_only",
    }
    if (
        any(parameters.get(key) != value for key, value in identity.items())
        or parameters.get("router_replication_calibration") != router_contract
    ):
        raise RuntimeError("EXP-059 completion calibration provenance failed")
    verified = verification.get("verified_artifacts", {})
    validate_verification_document(verification, config, "final", config_record)
    verification_checks = verification["checks"]
    check_names = [row["name"] for row in verification_checks]
    required_checks_passed = (
        len(check_names) == len(set(check_names))
        and FINAL_COMPLETION_REQUIRED_CHECKS.issubset(check_names)
        and all(row["passed"] for row in verification_checks)
    )
    expected_verified = {
        "config": config_record,
        "run": run_record,
        "calibration_parameters": parameters_record,
        "paired_oof": artifact(input_path),
        "private_output": private_record,
        "public_outputs": public_output_records,
        "frozen_sources": frozen_source_records,
    }
    if (
        verification.get("status") != "Passed"
        or verification.get("failed_count") != 0
        or any(verification.get(key) != value for key, value in identity.items())
        or verification.get("config") != config_record
        or not required_checks_passed
        or verified != expected_verified
        or verification["resources"]["wall_seconds"]
        > config["resources"]["verification_wall_seconds"]
        or verification["resources"]["peak_process_rss_gb"]
        > config["resources"]["peak_memory_gb"]
    ):
        raise RuntimeError("Only a Passed, provenance-bound EXP-059 verification can complete")
    if summary_path.read_text(encoding="utf-8") != render_summary(verification):
        raise RuntimeError("EXP-059 final verification summary drift")
    try:
        oof_prerequisites(config)
        preflight_prerequisites(config)
    except (KeyError, OSError, TypeError, ValueError) as error:
        raise RuntimeError("EXP-059 prerequisite chain drift at completion") from error
    completion_artifacts = {
        "config": config_record,
        "exp059_run": run_record,
        "exp059_verification": artifact(verification_path),
        "exp059_verification_summary": artifact(summary_path),
        "exp059_calibration_parameters": parameters_record,
        "paired_oof_private": artifact(input_path),
        "private_calibration": private_record,
        "public_outputs": public_output_records,
        "frozen_sources": frozen_source_records,
    }
    if os.path.lexists(completion_path):
        completion_mode = os.lstat(completion_path).st_mode
        if stat.S_ISLNK(completion_mode) or not stat.S_ISREG(completion_mode):
            raise ValueError("EXP-059 completion must be a regular file")
        completion = json.loads(completion_path.read_text(encoding="utf-8"))
        validate_existing_completion(completion, config, completion_artifacts)
        return completion
    return _create_calibration_completion(config, completion_artifacts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify EXP-059 artifacts independently")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--scope", choices=("preflight", "final", "completion"), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    config = load_config(config_path)
    if config.get("_archive_only"):
        raise PermissionError("Sealed EXP-059 is archive-only; use its frozen sources for audit")
    if args.scope == "preflight":
        result = verify_preflight(config_path, config)
    elif args.scope == "final":
        result = verify_final(config_path, config)
    else:
        result = verify_completion(config_path, config)
    payload = {"scope": args.scope, "status": result["status"]}
    if args.scope != "completion":
        payload.update({"passed": result["passed_count"], "failed": result["failed_count"]})
    print(json.dumps(payload, sort_keys=True))
    if result["status"] not in {"Passed", "Complete"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
