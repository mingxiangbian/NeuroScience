#!/usr/bin/env python3
"""Independently verify the no-result EXP-060 router preflight."""

from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import resource
import stat
import subprocess
import sys
import time
from typing import Any, Iterable
import zipfile

import numpy as np


EXPERIMENT_ID = "EXP-060"
RQ_ID = "RQ-S3"
LABEL_ORDER = ("love", "joy", "surprise", "anger", "sadness", "fear")
FEATURE_NAMES = (
    "m1_probability_love",
    "m1_probability_joy",
    "m1_probability_surprise",
    "m1_probability_anger",
    "m1_probability_sadness",
    "m1_probability_fear",
    "m1_mean_binary_entropy",
    "m1_max_binary_entropy",
    "m1_minimum_threshold_margin",
    "m1_predicted_cardinality",
    "m1_highest_probability",
    "m1_lowest_probability",
    "character_length",
    "m1_token_length",
)
PROHIBITED_RUNTIME_PREFIXES = (
    "m3_",
    "gold",
    "oracle",
    "sample_id",
    "component_id",
    "fold_id",
    "raw_text",
    "validation",
    "test",
)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-060-router-preflight.json"
REPLICATION_PREFLIGHT_SCHEMA = "exp-router-replication-preflight-config-v1"
REPLICATION_RUN_SCHEMA = "exp-router-replication-preflight-run-v1"
REPLICATION_CONTRACT_SCHEMA = "exp-router-replication-preflight-contract-v1"
REPLICATION_VERIFICATION_SCHEMA = "exp-router-replication-preflight-verification-v1"
REPLICATION_EXPERIMENT_ID = "EXP-062"
REPLICATION_RUN_ID = "exp-062-seed-44-router-replication"
REPLICATION_ATTEMPT_ID = "attempt-1"
REPLICATION_MODEL_SEED = 44
CHILD_TEST_TIMEOUT_SECONDS = 60
REPLICATION_STAGE = "pre-qwen-router-replication-preflight"
REPLICATION_CONFIG_NAME = (
    "exp-062-seed-44-router-replication-router-preflight-attempt-1.json"
)
POLICY_ORDER = (
    "m1_only",
    "m3_only",
    "m1_max_entropy",
    "m1_threshold_proximity",
    "logistic_router",
)
DEPLOYABLE_POLICY_ORDER = POLICY_ORDER[2:]
BASE_REPLICATION_PREREQUISITES = {
    "oof_verification", "exp059_run", "exp059_verification",
    "exp059_calibration_parameters",
}
BASE_FORMAL_SOURCE_SHA256 = {
    "runner": "873d53f45d587918b7c1b466a93b8da0b397732baa072af1b43e50a16150dc65",
    "verifier": "920f6565bd378c8f7cfe415a78e505123336602fb228dad95771fcc14e471b15",
    "tests": "4e6572f996fecd81f8715f808f1fdd44a5ae4d351813e605936478a97e86ddff",
}
REPLICATION_CALIBRATION_CONTRACT = {
    "calibrator": "identity",
    "temperature": 1.0,
    "probability_source": "direct_sigmoid_of_raw_oof_logits",
    "role": "frozen_exp060_replication_only",
}
REPLICATION_CONFIG_KEYS = {
    "schema_version", "experiment_id", "replication_parent_experiment_id", "run_id",
    "attempt_id", "model_seed", "seed_contract", "rq_id", "tier", "stage",
    "registered_at", "authorization", "provenance", "path_bases", "artifact_contract",
    "runtime", "implementation", "prerequisites", "input", "outputs", "data",
    "cross_fitting", "thresholds", "target_contract", "feature_contract", "router",
    "call_rates", "gate", "risk_coverage", "bootstrap", "resources", "claim_boundary",
    "commands",
}
REPLICATION_AUTHORIZATION_KEYS = {
    "basis", "model_seed", "no_result_preflight", "formal_router_training",
    "formal_result_computation", "validation_access", "test_access",
    "model_loading_or_forward", "raw_text_access",
}
REPLICATION_IMPLEMENTATION_KEYS = {
    "protocol", "preflight_runner", "preflight_verifier", "preflight_tests", "runner",
    "verifier", "tests", "runner_launcher", "verifier_launcher", "launcher_tests",
}
FORMAL_IMPLEMENTATION_KEYS = (
    "protocol", "runner", "verifier", "tests", "runner_launcher", "verifier_launcher",
    "launcher_tests",
)
REPLICATION_IMPLEMENTATION_PATHS = {
    "protocol": (
        "experiments/stack-overflow-emotion-gold/protocols/"
        "exp-060-pre-qwen-deployable-router.md"
    ),
    "preflight_runner": (
        "experiments/stack-overflow-emotion-gold/oof-router/"
        "run_exp060_router_preflight.py"
    ),
    "preflight_verifier": (
        "experiments/stack-overflow-emotion-gold/oof-router/"
        "verify_exp060_router_preflight.py"
    ),
    "preflight_tests": (
        "experiments/stack-overflow-emotion-gold/oof-router/tests/"
        "test_exp060_router_preflight.py"
    ),
    "runner": "experiments/stack-overflow-emotion-gold/oof-router/run_exp060_router.py",
    "verifier": (
        "experiments/stack-overflow-emotion-gold/oof-router/verify_exp060_router.py"
    ),
    "tests": (
        "experiments/stack-overflow-emotion-gold/oof-router/tests/test_exp060_router.py"
    ),
    "runner_launcher": (
        "experiments/stack-overflow-emotion-gold/oof-router/run_exp060_router_v3.py"
    ),
    "verifier_launcher": (
        "experiments/stack-overflow-emotion-gold/oof-router/verify_exp060_router_v3.py"
    ),
    "launcher_tests": (
        "experiments/stack-overflow-emotion-gold/oof-router/tests/test_exp060_router_v3.py"
    ),
}
REPLICATION_PREREQUISITE_KEYS = {
    "oof_verification", "oof_completion", "exp059_run", "exp059_verification",
    "exp059_calibration_parameters", "exp059_calibration_completion",
}
OOF_VERIFICATION_KEYS = {
    "attempt_id", "check_count", "checks", "claim_boundary", "cli_identity", "config",
    "experiment_id", "failed_count", "independence", "model_seed", "passed_count",
    "run_id", "schema_version", "scope", "seed_contract", "stage", "status",
    "verified_artifacts", "verified_at_utc",
}
OOF_COMPLETION_KEYS = {
    "artifacts", "attempt_id", "claim_boundary", "cli_identity", "completed_at_utc",
    "config", "experiment_id", "model_seed", "next_gate", "run_id", "schema_version",
    "seed_contract", "seed_contract_sha256", "stage", "status",
}
OOF_RUN_KEYS = {
    "artifacts", "attempt_id", "authorization", "claim_boundary", "cli_identity",
    "completed_at_utc", "config", "data", "experiment_id", "frozen_sources", "git",
    "initialization", "model_execution", "model_seed", "resources", "rq_id", "run_id",
    "schema_version", "seed_contract", "seed_contract_sha256", "split_access", "stage",
    "stages", "started_at_utc", "status", "tier", "working_directory",
}
EXP059_RUN_KEYS = {
    "attempt_id", "calibration_performed", "claim_boundary", "completed_at_utc",
    "component_count", "config", "experiment_id", "folds", "frozen_sources", "git",
    "input_before", "input_sha256_after", "model_loading_or_forward_performed",
    "model_seed", "oracle_analysis_performed", "performance_metrics_computed",
    "private_output", "public_outputs", "replication_parent_experiment_id", "resources",
    "router_replication_calibration", "router_training_performed", "rows", "rq_id",
    "run_id", "runtime", "schema_version", "seed_contract", "selective_prediction_performed",
    "split_access", "stage", "started_at_utc", "status", "temperature_adoption_role", "tier",
}
EXP059_VERIFICATION_KEYS = {
    "attempt_id", "checks", "config", "experiment_id", "failed_count", "model_seed",
    "passed_count", "replication_parent_experiment_id", "resources", "rq_id", "run_id",
    "schema_version", "scope", "seed_contract", "status", "verified_artifacts",
    "verified_at_utc",
}
EXP059_CALIBRATION_KEYS = {
    "attempt_id", "experiment_id", "families", "model_seed",
    "replication_parent_experiment_id", "router_replication_calibration", "run_id",
    "seed_contract",
}
EXP059_COMPLETION_KEYS = {
    "artifacts", "attempt_id", "claim_boundary", "completed_at_utc", "experiment_id",
    "model_seed", "next_gate", "replication_parent_experiment_id", "run_id",
    "schema_version", "seed_contract", "status",
}
EXP059_PUBLIC_OUTPUT_KEYS = {
    "abstention_gates", "bootstrap", "calibration_metrics", "calibration_parameters",
    "classification_metrics", "label_retention", "oracle_summary", "random_rejection",
    "reliability_bins", "reliability_figure", "report", "risk_coverage",
    "risk_coverage_figure",
}
OOF_EXPECTED_CHECK_COUNT = 27034
EXP059_EXPECTED_CHECK_COUNT = 4683
REPLICATION_OUTPUT_KEYS = {
    "public_namespace", "public_attempt_dir", "private_namespace", "private_attempt_dir",
    "selection_record",
}
REPLICATION_RESOURCE_CONTRACT = {
    "preflight_wall_seconds": 300,
    "verification_wall_seconds": 300,
    "peak_memory_gb": 2.0,
    "api_cost_usd": 0,
    "gpu_cost_usd": 0,
    "model_forward_runs": 0,
}
REPLICATION_REGISTERED_AT = "2026-08-24"
REPLICATION_PROVENANCE = {
    "base_git_head": "88cf763c1161aa8afda0f3d0b4ae4bb1c9c93833",
    "train_sha256": "fc2f853b5b8afb78253ca3a96b5093d2fd12ea7063801f57bf138c9d5cf528fc",
    "fold_manifest_sha256": "82929b1d837ceb9825c5bc39a8fea18f6d0736fca42aad630f3788b1ff8139d8",
    "source_order_sha256": "c9e4bd1eb2bdbb33c833234754c493b8818aa6c610acaf88659ae74fa94848a3",
}
REPLICATION_PATH_BASES = {
    "artifact_records": "projects/llm-forum-text-emotion-recognition",
    "commands": "/Users/phoenix/Assistant/NeuroScience",
}
REPLICATION_ARTIFACT_CONTRACT = {
    "public_directory_mode": "0755", "public_file_mode": "0644",
    "private_directory_mode": "0700", "private_file_mode": "0600",
    "public_row_level_data": False,
}
REPLICATION_RUNTIME = {
    "python_executable": "/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python",
    "python_version": "3.10.20", "numpy_version": "2.2.6",
    "scikit_learn_version": "1.7.2", "scipy_version": "1.15.3",
    "matplotlib_version": "3.10.7", "mplconfigdir": "/private/tmp/exp060-matplotlib",
}
REPLICATION_RISK_COVERAGE = {
    "methods": ["mean_entropy", "max_entropy", "margin"],
    "coverages": [1.0, 0.95, 0.9, 0.8, 0.7, 0.6],
    "mean_entropy": "mean_binary_entropy_of_final_selected_family_probability",
    "max_entropy": "max_binary_entropy_of_final_selected_family_probability",
    "margin": "negative_minimum_absolute_distance_to_final_selected_family_nested_threshold",
    "acceptance_count_rule": "floor_coverage_times_fold_rows_plus_0_5",
    "acceptance_tie_break": "stable_source_order", "diagnostic_only": True,
}
REPLICATION_COMMANDS = {
    "preflight": (
        "/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python "
        "projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/"
        "oof-router/run_exp060_router_preflight.py --config "
        "projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/"
        "oof-router/configs/exp-062-seed-44-router-replication-router-preflight-attempt-1.json"
    ),
    "verify_preflight": (
        "/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python "
        "projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/"
        "oof-router/verify_exp060_router_preflight.py --config "
        "projects/llm-forum-text-emotion-recognition/experiments/stack-overflow-emotion-gold/"
        "oof-router/configs/exp-062-seed-44-router-replication-router-preflight-attempt-1.json"
    ),
}
EXECUTION_CLAIM_KEYS = {
    "array_values_loaded", "real_features_constructed", "real_router_targets_constructed",
    "scaler_or_router_fitted", "router_metrics_computed", "bootstrap_computed",
    "validation_accessed", "test_accessed", "raw_text_accessed",
    "model_loaded_or_forward_run", "formal_router_training", "formal_result_computation",
}
REPLICATION_RUN_KEYS = {
    "schema_version", "experiment_id", "replication_parent_experiment_id", "run_id",
    "attempt_id", "model_seed", "seed_contract", "rq_id", "tier", "stage", "status",
    "started_at_utc", "completed_at_utc", "config", "upstreams", "input",
    "source_artifacts", "contract", "check_count", "passed_count", "failed_count",
    "checks", "resources", "execution_claims", "claim_boundary",
}
REPLICATION_CONTRACT_KEYS = {
    "schema_version", "experiment_id", "replication_parent_experiment_id", "run_id",
    "attempt_id", "model_seed", "seed_contract", "rq_id", "stage", "result_bearing",
    "data_scope", "input_schema", "ordered_model_features", "feature_count",
    "prohibited_runtime_feature_classes", "nested_cross_fitting_required",
    "router_replication_calibration", "policies", "deployable_policy_order",
    "formal_router_training_authorized", "formal_result_computation_authorized",
    "validation_access", "test_access", "raw_text_access", "model_loading_or_forward",
    "resource_contract", "claim_boundary",
}
REPLICATION_VERIFICATION_KEYS = {
    "schema_version", "experiment_id", "replication_parent_experiment_id", "run_id",
    "attempt_id", "model_seed", "seed_contract", "rq_id", "scope", "verified_at_utc",
    "status", "passed_count", "failed_count", "checks", "independent",
    "runner_imported", "execution_claims", "verified_artifacts", "resources",
    "claim_boundary",
}
REPLICATION_CLAIM_BOUNDARY = (
    "Seed-44 no-result router preflight only; no feature matrix, target, fitted "
    "router, metric, bootstrap, primary gate, or selection result."
)
VERIFICATION_CLAIM_BOUNDARY = (
    "Verified seed-44 no-result router preflight only; formal routing remains separately authorized."
)
RUN_REQUIRED_CHECK_NAMES = (
    "config.exact_schema",
    "config.identity",
    "config.authorization_no_result_only",
    "config.upstream_chain",
    "input.header_schema_only",
    "input.mode_0600_nlink1",
    "input.parent_mode_0700",
    "exp059.diagnostic_calibrators_allowed",
    "exp059.router_replication_identity",
    "router.policies_5",
    "router.deployable_policy_order_3",
    "router.formal_source_contract",
    "features.exact_14",
    "cross_fitting.inner3_outer4",
    "outputs.preflight_absent",
    "outputs.formal_public_absent",
    "outputs.formal_private_absent",
    "outputs.completion_absent",
    "outputs.selection_absent",
    "runtime.numpy_available",
    "runtime.scikit_learn_available",
    "tests.preflight",
    "tests.formal",
    "tests.launchers",
    "resources.wall_seconds",
    "resources.peak_memory_gb",
    "resources.api_gpu_forward_zero",
)
VERIFICATION_REQUIRED_CHECK_NAMES = (
    "verification.config",
    "verification.run_schema",
    "verification.contract_schema",
    "verification.runner_checks",
    "verification.upstream_chain",
    "verification.input_header_only",
    "verification.router_identity_calibration",
    "verification.policies_5",
    "verification.deployable_policy_order_3",
    "verification.formal_source_contract",
    "verification.frozen_sources",
    "verification.public_modes",
    "verification.public_privacy",
    "verification.formal_public_absent",
    "verification.formal_private_absent",
    "verification.completion_absent",
    "verification.selection_absent",
    "verification.resources.wall_seconds",
    "verification.resources.peak_memory_gb",
    "verification.resources.zero_cost_forward",
)
PUBLIC_SENSITIVE_KEYS = {
    "sample_id", "sample_ids", "component_id", "component_ids", "fold_id", "fold_ids",
    "gold", "logit", "logits", "probability", "probabilities", "feature", "features",
    "feature_matrix", "target", "targets", "router_targets", "route_score", "route_scores",
    "route_mask", "route_masks", "prediction", "predictions", "raw_text", "text",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(_secure_read_bytes(path)[0]).hexdigest()


def resolve_project(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Project-relative path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))


def artifact(path: Path) -> dict[str, Any]:
    payload, metadata = _secure_read_bytes(path)
    return {
        "path": display_path(path),
        "bytes": metadata.st_size,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


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


def require_record(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Frozen artifact drift: {path}")
    return path


def is_replication_preflight(config: dict[str, Any]) -> bool:
    return config.get("schema_version") == REPLICATION_PREFLIGHT_SCHEMA


def expected_seed_contract() -> dict[str, int]:
    return {
        "model_seed": 44,
        "python_seed": 44,
        "numpy_seed": 44,
        "torch_seed": 44,
        "m1_batch_seed": 44,
        "m3_head_seed": 44,
        "m3_batch_seed": 44,
        "m3_lora_seed": 100044,
    }


def _same_typed_dict(actual: Any, expected: dict[str, Any]) -> bool:
    return (
        isinstance(actual, dict)
        and set(actual) == set(expected)
        and all(type(actual[key]) is type(value) and actual[key] == value for key, value in expected.items())
    )


def _finite_nonnegative_number(value: Any) -> bool:
    return (
        type(value) in (int, float)
        and math.isfinite(float(value))
        and float(value) >= 0.0
    )


def _runtime_resource_record_exact(
    value: Any, *, wall_budget: float, memory_budget: float
) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "wall_seconds", "peak_process_rss_gb", "api_cost_usd", "gpu_cost_usd",
        "model_forward_runs",
    }:
        return False
    return (
        _finite_nonnegative_number(value["wall_seconds"])
        and float(value["wall_seconds"]) <= wall_budget
        and _finite_nonnegative_number(value["peak_process_rss_gb"])
        and float(value["peak_process_rss_gb"]) <= memory_budget
        and type(value["api_cost_usd"]) is int
        and value["api_cost_usd"] == 0
        and type(value["gpu_cost_usd"]) is int
        and value["gpu_cost_usd"] == 0
        and type(value["model_forward_runs"]) is int
        and value["model_forward_runs"] == 0
    )


def _replication_calibration_exact(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == set(REPLICATION_CALIBRATION_CONTRACT)
        and value.get("calibrator") == "identity"
        and type(value.get("temperature")) is float
        and value["temperature"] == 1.0
        and value.get("probability_source") == "direct_sigmoid_of_raw_oof_logits"
        and value.get("role") == "frozen_exp060_replication_only"
    )


def _runtime_environment_exact(config: dict[str, Any]) -> bool:
    return (
        config.get("runtime") == REPLICATION_RUNTIME
        and os.path.realpath(sys.executable)
        == os.path.realpath(REPLICATION_RUNTIME["python_executable"])
        and platform.python_version() == REPLICATION_RUNTIME["python_version"]
        and importlib.metadata.version("numpy") == REPLICATION_RUNTIME["numpy_version"]
        and importlib.metadata.version("scikit-learn")
        == REPLICATION_RUNTIME["scikit_learn_version"]
        and importlib.metadata.version("scipy") == REPLICATION_RUNTIME["scipy_version"]
        and importlib.metadata.version("matplotlib")
        == REPLICATION_RUNTIME["matplotlib_version"]
    )


def expected_replication_outputs() -> dict[str, str]:
    base = "experiments/stack-overflow-emotion-gold/oof-router"
    return {
        "public_namespace": f"{base}/runs/{REPLICATION_RUN_ID}",
        "public_attempt_dir": f"{base}/runs/{REPLICATION_RUN_ID}/{REPLICATION_ATTEMPT_ID}",
        "private_namespace": f"{base}/private/{REPLICATION_RUN_ID}",
        "private_attempt_dir": f"{base}/private/{REPLICATION_RUN_ID}/{REPLICATION_ATTEMPT_ID}",
        "selection_record": f"{base}/runs/{REPLICATION_RUN_ID}/selected-attempt.json",
    }


def _normalized_relative(value: str) -> Path:
    relative = Path(str(value))
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in ("", ".", "..") for part in relative.parts)
    ):
        raise ValueError(f"Path is not normalized project-relative: {value}")
    return relative


def resolve_replication_path(value: str) -> Path:
    relative = _normalized_relative(value)
    cursor = PROJECT_ROOT
    for part in relative.parts:
        cursor = cursor / part
        if os.path.lexists(cursor) and stat.S_ISLNK(os.lstat(cursor).st_mode):
            raise ValueError(f"Path traverses a symbolic link: {value}")
    resolved = (PROJECT_ROOT / relative).resolve()
    if not resolved.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return resolved


def replication_output_paths(config: dict[str, Any]) -> dict[str, Path]:
    outputs = config["outputs"]
    public_attempt = resolve_replication_path(outputs["public_attempt_dir"])
    private_attempt = resolve_replication_path(outputs["private_attempt_dir"])
    formal_public = public_attempt / "router"
    return {
        "public_namespace": resolve_replication_path(outputs["public_namespace"]),
        "public_attempt": public_attempt,
        "private_namespace": resolve_replication_path(outputs["private_namespace"]),
        "private_attempt": private_attempt,
        "selection": resolve_replication_path(outputs["selection_record"]),
        "preflight": public_attempt / "router-preflight",
        "formal_public": formal_public,
        "formal_private": private_attempt / "router",
        "completion": formal_public / "router-complete.json",
    }


def _require_regular_metadata(path: Path, *, mode: int | None = None) -> os.stat_result:
    observed = os.lstat(path)
    if stat.S_ISLNK(observed.st_mode) or not stat.S_ISREG(observed.st_mode):
        raise ValueError(f"Expected a real regular file: {path}")
    if observed.st_nlink != 1:
        raise ValueError(f"Expected nlink=1: {path}")
    if mode is not None and stat.S_IMODE(observed.st_mode) != mode:
        raise PermissionError(f"Unexpected file mode for {path}: {oct(stat.S_IMODE(observed.st_mode))}")
    return observed


def _secure_read_bytes(
    path: Path, *, mode: int | None = None
) -> tuple[bytes, os.stat_result]:
    lexical = Path(os.path.abspath(os.fspath(path)))
    before = _require_regular_metadata(lexical, mode=mode)
    descriptor = os.open(lexical, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
            or (mode is not None and stat.S_IMODE(opened.st_mode) != mode)
        ):
            raise ValueError(f"File identity/mode changed before open: {lexical}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        payload = b"".join(chunks)
        after_fd = os.fstat(descriptor)
        if (
            len(payload) != opened.st_size
            or (
                after_fd.st_dev,
                after_fd.st_ino,
                after_fd.st_size,
                after_fd.st_mtime_ns,
                after_fd.st_ctime_ns,
                stat.S_IMODE(after_fd.st_mode),
                after_fd.st_nlink,
            )
            != (
                opened.st_dev,
                opened.st_ino,
                opened.st_size,
                opened.st_mtime_ns,
                opened.st_ctime_ns,
                stat.S_IMODE(opened.st_mode),
                opened.st_nlink,
            )
            or (mode is not None and stat.S_IMODE(after_fd.st_mode) != mode)
        ):
            raise ValueError(f"File changed during secure read: {lexical}")
    finally:
        os.close(descriptor)
    after = os.lstat(lexical)
    if (
        not stat.S_ISREG(after.st_mode)
        or after.st_nlink != 1
        or (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
            stat.S_IMODE(after.st_mode),
        )
        != (
            after_fd.st_dev,
            after_fd.st_ino,
            after_fd.st_size,
            after_fd.st_mtime_ns,
            after_fd.st_ctime_ns,
            stat.S_IMODE(after_fd.st_mode),
        )
        or (mode is not None and stat.S_IMODE(after.st_mode) != mode)
    ):
        raise ValueError(f"File identity/mode changed after read: {lexical}")
    return payload, after


def _require_directory_metadata(path: Path, mode: int) -> os.stat_result:
    observed = os.lstat(path)
    if stat.S_ISLNK(observed.st_mode) or not stat.S_ISDIR(observed.st_mode):
        raise ValueError(f"Expected a real directory: {path}")
    if stat.S_IMODE(observed.st_mode) != mode:
        raise PermissionError(f"Unexpected directory mode for {path}: {oct(stat.S_IMODE(observed.st_mode))}")
    return observed


def require_replication_record(record: dict[str, Any], *, mode: int | None = None) -> Path:
    if set(record) != {"path", "bytes", "sha256"}:
        raise ValueError("Artifact record exact schema drift")
    if (
        not isinstance(record["path"], str)
        or isinstance(record["bytes"], bool)
        or not isinstance(record["bytes"], int)
        or record["bytes"] < 0
        or not isinstance(record["sha256"], str)
        or len(record["sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in record["sha256"])
    ):
        raise ValueError("Artifact record field type drift")
    path = resolve_replication_path(record["path"])
    payload, observed = _secure_read_bytes(path, mode=mode)
    if observed.st_size != record["bytes"] or hashlib.sha256(payload).hexdigest() != record["sha256"]:
        raise ValueError(f"Frozen artifact drift: {path}")
    return path


def _canonical_config_path(path: Path) -> Path:
    lexical = Path(os.path.abspath(path))
    expected_parent = Path(os.path.abspath(SCRIPT_DIR / "configs"))
    if lexical.parent != expected_parent or lexical.name != REPLICATION_CONFIG_NAME:
        raise ValueError("Replication preflight config must be the canonical direct configs child")
    _secure_read_bytes(lexical, mode=0o644)
    return lexical


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
    ).encode("utf-8")


def _create_bytes_once(path: Path, payload: bytes, mode: int = 0o644) -> None:
    if os.path.lexists(path):
        raise FileExistsError(f"Refusing to overwrite append-only artifact: {path}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, mode)
    try:
        os.fchmod(descriptor, mode)
        offset = 0
        while offset < len(payload):
            offset += os.write(descriptor, payload[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    observed_payload, observed = _secure_read_bytes(path, mode=mode)
    if observed.st_size != len(payload) or observed_payload != payload:
        raise OSError(f"Append-only artifact size drift: {path}")


def peak_rss_gb() -> float:
    values = [
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    ]
    factor = 1 / 1e9 if platform.system() == "Darwin" else 1024 / 1e9
    return max(float(value) * factor for value in values)


def _pyc_snapshot() -> dict[str, tuple[int, int, int]]:
    return {
        str(path.relative_to(SCRIPT_DIR)): (
            os.lstat(path).st_size,
            os.lstat(path).st_mtime_ns,
            os.lstat(path).st_ctime_ns,
        )
        for path in SCRIPT_DIR.rglob("*.pyc")
        if path.is_file()
    }


def _run_child_test(path: Path) -> dict[str, Any]:
    if (
        type(CHILD_TEST_TIMEOUT_SECONDS) is not int
        or CHILD_TEST_TIMEOUT_SECONDS <= 0
        or CHILD_TEST_TIMEOUT_SECONDS > REPLICATION_RESOURCE_CONTRACT["verification_wall_seconds"]
        or 3 * CHILD_TEST_TIMEOUT_SECONDS
        > REPLICATION_RESOURCE_CONTRACT["verification_wall_seconds"]
    ):
        raise ValueError("Child-test timeout exceeds the verification budget")
    before_pyc = _pyc_snapshot()
    command = [os.path.realpath(sys.executable), "-B", str(path)]
    child_environment = os.environ.copy()
    child_environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=CHILD_TEST_TIMEOUT_SECONDS,
        env=child_environment,
    )
    after_pyc = _pyc_snapshot()
    if after_pyc != before_pyc:
        raise RuntimeError("Child test created or changed Python bytecode")
    return {
        "returncode": result.returncode,
        "command": command,
        "timeout_seconds": CHILD_TEST_TIMEOUT_SECONDS,
        "pythondontwritebytecode": child_environment["PYTHONDONTWRITEBYTECODE"],
        "pyc_unchanged": True,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def _child_test_result_exact(value: Any, path: Path) -> bool:
    return (
        isinstance(value, dict)
        and set(value)
        == {
            "returncode", "command", "timeout_seconds", "pythondontwritebytecode",
            "pyc_unchanged", "stdout_tail", "stderr_tail",
        }
        and type(value["returncode"]) is int
        and value["returncode"] == 0
        and value["command"] == [os.path.realpath(sys.executable), "-B", str(path)]
        and type(value["timeout_seconds"]) is int
        and 0 < value["timeout_seconds"] <= REPLICATION_RESOURCE_CONTRACT["verification_wall_seconds"]
        and value["pythondontwritebytecode"] == "1"
        and value["pyc_unchanged"] is True
        and isinstance(value["stdout_tail"], str)
        and isinstance(value["stderr_tail"], str)
    )


def npz_header_schema_strict(path: Path) -> dict[str, dict[str, Any]]:
    schema: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        if len(members) != len(set(members)):
            raise ValueError("NPZ contains duplicate members")
        expected_members = {f"{name}.npy" for name in expected_paired_schema()}
        if set(members) != expected_members:
            raise ValueError("NPZ member inventory drift")
        for member in sorted(members):
            if Path(member).name != member or not member.endswith(".npy"):
                raise ValueError("NPZ member path drift")
            with archive.open(member) as source:
                version = np.lib.format.read_magic(source)
                if version == (1, 0):
                    shape, fortran, dtype = np.lib.format.read_array_header_1_0(source)
                elif version == (2, 0):
                    shape, fortran, dtype = np.lib.format.read_array_header_2_0(source)
                else:
                    raise ValueError(f"Unsupported NPY header version: {version}")
            name = Path(member).stem
            if name in schema:
                raise ValueError("NPZ array stem collision")
            schema[name] = {
                "shape": list(shape),
                "dtype": str(dtype),
                "fortran_order": bool(fortran),
            }
    return schema


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


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


def expected_paired_schema() -> dict[str, dict[str, Any]]:
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


def _replication_identity(payload: dict[str, Any], *, experiment_id: str) -> bool:
    return (
        payload.get("experiment_id") == experiment_id
        and payload.get("run_id") == REPLICATION_RUN_ID
        and payload.get("attempt_id") == REPLICATION_ATTEMPT_ID
        and type(payload.get("model_seed")) is int
        and payload.get("model_seed") == REPLICATION_MODEL_SEED
        and _same_typed_dict(payload.get("seed_contract"), expected_seed_contract())
    )


def _exp059_identity(payload: dict[str, Any]) -> bool:
    return (
        payload.get("experiment_id") == "EXP-059"
        and payload.get("replication_parent_experiment_id") == REPLICATION_EXPERIMENT_ID
        and payload.get("run_id") == REPLICATION_RUN_ID
        and payload.get("attempt_id") == REPLICATION_ATTEMPT_ID
        and type(payload.get("model_seed")) is int
        and payload.get("model_seed") == REPLICATION_MODEL_SEED
        and _same_typed_dict(payload.get("seed_contract"), expected_seed_contract())
    )


def _load_record_json(record: dict[str, Any]) -> dict[str, Any]:
    path = require_replication_record(record, mode=0o644)
    return json.loads(_secure_read_bytes(path, mode=0o644)[0].decode("utf-8"))


def _passed_checks_exact(
    payload: dict[str, Any], *, has_check_count: bool, expected_count: int
) -> bool:
    checks = payload.get("checks")
    passed_count = payload.get("passed_count")
    failed_count = payload.get("failed_count")
    if (
        not isinstance(checks, list)
        or not checks
        or len(checks) != expected_count
        or isinstance(passed_count, bool)
        or not isinstance(passed_count, int)
        or isinstance(failed_count, bool)
        or not isinstance(failed_count, int)
        or passed_count != len(checks)
        or failed_count != 0
        or any(
            set(row) != {"name", "passed", "detail"}
            or not isinstance(row.get("name"), str)
            or not row["name"]
            or row.get("passed") is not True
            for row in checks
            if isinstance(row, dict)
        )
        or any(not isinstance(row, dict) for row in checks)
    ):
        return False
    names = [row["name"] for row in checks]
    if len(names) != len(set(names)):
        return False
    check_count = payload.get("check_count")
    return not has_check_count or (
        not isinstance(check_count, bool)
        and isinstance(check_count, int)
        and check_count == len(checks)
    )


def _exp059_resources_exact(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "wall_seconds", "peak_process_rss_gb", "api_cost_usd"
    }:
        return False
    for name in ("wall_seconds", "peak_process_rss_gb"):
        observed = value[name]
        if (
            isinstance(observed, bool)
            or not isinstance(observed, (int, float))
            or not math.isfinite(float(observed))
            or float(observed) < 0.0
        ):
            return False
    return type(value["api_cost_usd"]) is int and value["api_cost_usd"] == 0


def validate_replication_upstreams(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    prerequisites = config["prerequisites"]
    paired_record = config["input"]["paired_oof"]
    paired_path = require_replication_record(paired_record, mode=0o600)
    _require_directory_metadata(paired_path.parent, 0o700)
    values = {name: _load_record_json(record) for name, record in prerequisites.items()}
    oof_verification = values["oof_verification"]
    oof_completion = values["oof_completion"]
    exp059_run = values["exp059_run"]
    exp059_verification = values["exp059_verification"]
    calibration = values["exp059_calibration_parameters"]
    exp059_completion = values["exp059_calibration_completion"]
    if (
        set(oof_verification) != OOF_VERIFICATION_KEYS
        or not _replication_identity(oof_verification, experiment_id=REPLICATION_EXPERIMENT_ID)
        or oof_verification.get("schema_version") != "exp-oof-final-verification-v2"
        or oof_verification.get("scope") != "final"
        or oof_verification.get("stage") != "paired-m1-m3-oof-production"
        or oof_verification.get("status") != "Passed"
        or oof_verification.get("independence")
        != {
            "all_fold_tables_recomputed": True,
            "model_libraries_imported": False,
            "paired_table_recomputed": True,
            "runner_imported": False,
        }
        or not _passed_checks_exact(
            oof_verification,
            has_check_count=True,
            expected_count=OOF_EXPECTED_CHECK_COUNT,
        )
    ):
        raise ValueError("Seed-44 OOF final verification chain drift")
    oof_verified = oof_verification["verified_artifacts"]
    expected_folds = {str(index) for index in range(5)}
    if (
        set(oof_verified)
        != {"config", "fold_runs", "fold_verifications", "paired_oof_private", "run", "summary"}
        or set(oof_verified.get("fold_runs", {})) != {"m1", "m3"}
        or set(oof_verified.get("fold_verifications", {})) != {"m1", "m3"}
        or any(
            set(oof_verified[section][family]) != expected_folds
            for section in ("fold_runs", "fold_verifications")
            for family in ("m1", "m3")
        )
        or oof_verified.get("paired_oof_private") != paired_record
    ):
        raise ValueError("Seed-44 OOF verified-artifact inventory drift")
    if (
        set(oof_completion) != OOF_COMPLETION_KEYS
        or not _replication_identity(oof_completion, experiment_id=REPLICATION_EXPERIMENT_ID)
        or oof_completion.get("schema_version") != "exp-oof-completion-v2"
        or oof_completion.get("stage") != "paired-m1-m3-oof-production"
        or oof_completion.get("status") != "Complete"
        or set(oof_completion.get("artifacts", {}))
        != {"final_verification", "paired_oof_private", "run", "summary"}
        or oof_completion.get("artifacts", {}).get("final_verification")
        != prerequisites["oof_verification"]
        or oof_completion.get("artifacts", {}).get("paired_oof_private") != paired_record
        or oof_completion.get("artifacts", {}).get("run") != oof_verified.get("run")
        or oof_completion.get("artifacts", {}).get("summary") != oof_verified.get("summary")
        or oof_completion.get("config") != oof_verified.get("config")
    ):
        raise ValueError("Seed-44 OOF completion chain drift")
    oof_run_record = oof_completion.get("artifacts", {}).get("run")
    if not isinstance(oof_run_record, dict):
        raise ValueError("OOF completion is missing its run record")
    oof_run = _load_record_json(oof_run_record)
    exp059_verified = exp059_verification.get("verified_artifacts", {})
    if (
        set(oof_run) != OOF_RUN_KEYS
        or not _replication_identity(oof_run, experiment_id=REPLICATION_EXPERIMENT_ID)
        or oof_run.get("schema_version") != "exp-oof-production-run-v2"
        or oof_run.get("stage") != "paired-m1-m3-oof-production"
        or oof_run.get("status") != "CompletedAwaitingVerification"
        or oof_run.get("config") != oof_verified.get("config")
        or oof_run.get("artifacts", {}).get("paired_oof_private") != paired_record
        or oof_verified.get("run") != oof_run_record
    ):
        raise ValueError("Seed-44 OOF run chain drift")
    if (
        set(exp059_run) != EXP059_RUN_KEYS
        or not _exp059_identity(exp059_run)
        or exp059_run.get("schema_version") != "exp-059-formal-run-v2"
        or exp059_run.get("status") != "CompletedAwaitingVerification"
        or exp059_run.get("stage") != "cross-fitted-calibration-selective-prediction"
        or exp059_run.get("rows") != 3360
        or exp059_run.get("folds") != 5
        or exp059_run.get("component_count") != 3277
        or exp059_run.get("input_before") != paired_record
        or exp059_run.get("input_sha256_after") != paired_record["sha256"]
        or exp059_run.get("calibration_performed") is not True
        or exp059_run.get("oracle_analysis_performed") is not True
        or exp059_run.get("performance_metrics_computed") is not True
        or exp059_run.get("selective_prediction_performed") is not True
        or exp059_run.get("model_loading_or_forward_performed") is not False
        or exp059_run.get("router_training_performed") is not False
        or not _replication_calibration_exact(
            exp059_run.get("router_replication_calibration")
        )
        or not _exp059_resources_exact(exp059_run.get("resources"))
        or set(exp059_run.get("frozen_sources", {}))
        != {"config", "protocol", "runner", "verifier", "tests"}
        or set(exp059_run.get("public_outputs", {})) != EXP059_PUBLIC_OUTPUT_KEYS
        or exp059_run.get("split_access")
        != {
            "accessed_splits": ["train-oof"],
            "validation_accessed": False,
            "test_inputs_accessed": False,
            "test_labels_accessed": False,
        }
    ):
        raise ValueError("Seed-44 EXP-059 run chain drift")
    if (
        set(exp059_verification) != EXP059_VERIFICATION_KEYS
        or not _exp059_identity(exp059_verification)
        or exp059_verification.get("schema_version") != "exp-059-verification-v2"
        or exp059_verification.get("scope") != "final"
        or exp059_verification.get("status") != "Passed"
        or not _exp059_resources_exact(exp059_verification.get("resources"))
        or not _passed_checks_exact(
            exp059_verification,
            has_check_count=False,
            expected_count=EXP059_EXPECTED_CHECK_COUNT,
        )
        or set(exp059_verified)
        != {"calibration_parameters", "config", "frozen_sources", "paired_oof", "private_output", "public_outputs", "run"}
        or set(exp059_verified.get("frozen_sources", {}))
        != {"config", "protocol", "runner", "verifier", "tests"}
        or set(exp059_verified.get("public_outputs", {}))
        != EXP059_PUBLIC_OUTPUT_KEYS
        or exp059_verified.get("run") != prerequisites["exp059_run"]
        or exp059_verified.get("paired_oof") != paired_record
        or exp059_verified.get("calibration_parameters")
        != prerequisites["exp059_calibration_parameters"]
        or exp059_verified.get("config") != exp059_run.get("config")
        or exp059_verified.get("frozen_sources") != exp059_run.get("frozen_sources")
        or exp059_verified.get("public_outputs") != exp059_run.get("public_outputs")
        or exp059_verified.get("private_output") != exp059_run.get("private_output")
    ):
        raise ValueError("Seed-44 EXP-059 verification chain drift")
    if (
        set(calibration) != EXP059_CALIBRATION_KEYS
        or not _exp059_identity(calibration)
        or not _replication_calibration_exact(calibration.get("router_replication_calibration"))
        or set(calibration.get("families", {})) != {"m1", "m3"}
        or any(
            set(calibration["families"].get(family, {}))
            != {"final_global_threshold", "final_temperature", "fold_fits", "full_oof_temperature_fit", "selected_calibrator"}
            for family in ("m1", "m3")
        )
        or any(
            calibration.get("families", {}).get(family, {}).get("selected_calibrator")
            not in {"identity", "temperature"}
            for family in ("m1", "m3")
        )
        or any(
            isinstance(
                calibration.get("families", {}).get(family, {}).get("final_temperature"),
                bool,
            )
            or not isinstance(
                calibration.get("families", {}).get(family, {}).get("final_temperature"),
                (int, float),
            )
            or not math.isfinite(float(calibration["families"][family]["final_temperature"]))
            or float(calibration["families"][family]["final_temperature"]) <= 0.0
            for family in ("m1", "m3")
        )
    ):
        raise ValueError("Seed-44 router identity-calibration contract drift")
    if (
        set(exp059_completion) != EXP059_COMPLETION_KEYS
        or not _exp059_identity(exp059_completion)
        or exp059_completion.get("schema_version")
        != "exp-059-calibration-completion-v2"
        or exp059_completion.get("status") != "Complete"
        or set(exp059_completion.get("artifacts", {}))
        != {"config", "exp059_calibration_parameters", "exp059_run", "exp059_verification", "exp059_verification_summary", "frozen_sources", "paired_oof_private", "private_calibration", "public_outputs"}
        or set(exp059_completion.get("artifacts", {}).get("frozen_sources", {}))
        != {"config", "protocol", "runner", "verifier", "tests"}
        or set(exp059_completion.get("artifacts", {}).get("public_outputs", {}))
        != EXP059_PUBLIC_OUTPUT_KEYS
        or exp059_completion.get("artifacts", {}).get("exp059_run")
        != prerequisites["exp059_run"]
        or exp059_completion.get("artifacts", {}).get("exp059_verification")
        != prerequisites["exp059_verification"]
        or exp059_completion.get("artifacts", {}).get("exp059_calibration_parameters")
        != prerequisites["exp059_calibration_parameters"]
        or exp059_completion.get("artifacts", {}).get("paired_oof_private") != paired_record
        or exp059_completion.get("artifacts", {}).get("config") != exp059_verified.get("config")
        or exp059_completion.get("artifacts", {}).get("frozen_sources")
        != exp059_verified.get("frozen_sources")
        or exp059_completion.get("artifacts", {}).get("public_outputs")
        != exp059_verified.get("public_outputs")
        or exp059_completion.get("artifacts", {}).get("private_calibration")
        != exp059_verified.get("private_output")
    ):
        raise ValueError("Seed-44 EXP-059 completion chain drift")
    return values


def _literal_assignment(source: str, name: str) -> Any:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                value = node.value
                try:
                    return ast.literal_eval(value)
                except (ValueError, TypeError):
                    if (
                        name == "DEPLOYABLE_POLICIES"
                        and isinstance(value, ast.Subscript)
                        and isinstance(value.value, ast.Name)
                        and value.value.id == "POLICY_ORDER"
                    ):
                        return tuple(_literal_assignment(source, "POLICY_ORDER"))[2:]
                    raise ValueError(f"Non-literal formal source contract: {name}")
    raise ValueError(f"Missing formal source contract: {name}")


def validate_formal_source_contract(config: dict[str, Any]) -> dict[str, Path]:
    paths = {
        name: require_replication_record(config["implementation"][name], mode=0o644)
        for name in FORMAL_IMPLEMENTATION_KEYS
    }
    base_payloads = {
        name: _secure_read_bytes(paths[name], mode=0o644)[0]
        for name in BASE_FORMAL_SOURCE_SHA256
    }
    runner_source = base_payloads["runner"].decode("utf-8")
    verifier_source = base_payloads["verifier"].decode("utf-8")
    if any(
        hashlib.sha256(base_payloads[name]).hexdigest() != expected
        for name, expected in BASE_FORMAL_SOURCE_SHA256.items()
    ):
        raise ValueError("Frozen formal base source hash drift")
    if tuple(_literal_assignment(runner_source, "POLICY_ORDER")) != DEPLOYABLE_POLICY_ORDER:
        raise ValueError("Formal runner deployable policy order drift")
    if tuple(_literal_assignment(verifier_source, "POLICY_ORDER")) != POLICY_ORDER:
        raise ValueError("Base verifier five-policy inventory drift")
    if tuple(_literal_assignment(verifier_source, "DEPLOYABLE_POLICIES")) != DEPLOYABLE_POLICY_ORDER:
        raise ValueError("Base verifier deployable policy order drift")
    if _literal_assignment(runner_source, "REPLICATION_CONFIG_SCHEMA") != "exp-router-replication-config-v2":
        raise ValueError("Frozen formal runner base schema drift")
    if _literal_assignment(verifier_source, "REPLICATION_CONFIG_SCHEMA") != "exp-router-replication-config-v2":
        raise ValueError("Frozen formal verifier base schema drift")
    if set(_literal_assignment(runner_source, "REPLICATION_REQUIRED_PREREQUISITES")) != BASE_REPLICATION_PREREQUISITES:
        raise ValueError("Frozen formal runner prerequisite inventory drift")
    if set(_literal_assignment(verifier_source, "REPLICATION_REQUIRED_PREREQUISITES")) != BASE_REPLICATION_PREREQUISITES:
        raise ValueError("Frozen formal verifier prerequisite inventory drift")
    return paths


def _validate_replication_method(config: dict[str, Any]) -> None:
    expected_data = {
        "protocol_id": "DATA-SO-TASK-V1",
        "split": "train-oof",
        "rows": 3360,
        "duplicate_components": 3277,
        "upstream_seed": 44,
        "source_order_sha256": "c9e4bd1eb2bdbb33c833234754c493b8818aa6c610acaf88659ae74fa94848a3",
        "label_order": list(LABEL_ORDER),
    }
    if not _same_typed_dict(config.get("data"), expected_data):
        raise ValueError("Seed-44 preflight data contract drift")
    cross = config.get("cross_fitting", {})
    if (
        cross.get("outer_fold_ids") != [0, 1, 2, 3, 4]
        or cross.get("outer_router_train_folds") != 4
        or cross.get("outer_router_heldout_folds") != 1
        or cross.get("nested_threshold_recomputation") is not True
        or cross.get("nested_router_train_threshold_folds") != 3
        or cross.get("outer_heldout_threshold_folds") != 4
        or cross.get("reuse_exp058_duplicate_component_partition") is not True
        or cross.get("restore_exp058_source_order") is not True
    ):
        raise ValueError("Nested inner-3/outer-4 contract drift")
    thresholds = config.get("thresholds", {})
    if (
        thresholds.get("calibrator") != "identity_for_m1_and_m3"
        or thresholds.get("probability_source") != "direct_sigmoid_of_raw_oof_logits"
        or thresholds.get("grid_start") != 0.05
        or thresholds.get("grid_end") != 0.95
        or thresholds.get("grid_step") != 0.01
        or thresholds.get("numeric_tolerance") != 1e-12
        or thresholds.get("selection_order")
        != [
            "highest_six_label_macro_f1",
            "lowest_hamming_loss",
            "closest_to_0_5",
            "lower_threshold",
        ]
    ):
        raise ValueError("Identity threshold contract drift")
    target = config.get("target_contract", {})
    if (
        target.get("unit") != "whole_six_bit_vector"
        or target.get("positive") != "m3_row_hamming_loss_strictly_lower_than_m1"
        or target.get("tie_policy") != "m1"
        or target.get("gold_is_training_outcome_only") is not True
        or target.get("m3_is_training_outcome_only") is not True
        or target.get("exp059_oracle_array_used_as_formal_target") is not False
    ):
        raise ValueError("Router target contract drift")
    features = config.get("feature_contract", {})
    if (
        tuple(features.get("ordered_features", [])) != FEATURE_NAMES
        or features.get("feature_count") != 14
        or features.get("scaler") != "StandardScaler_fit_inside_outer_router_train"
        or features.get("m1_raw_logits_included") is not False
        or features.get("m3_token_length_included") is not False
    ):
        raise ValueError("Fourteen-feature contract drift")
    router = config.get("router", {})
    expected_logistic = {
        "penalty": "l2", "C": 1.0, "class_weight": "balanced", "solver": "liblinear",
        "max_iter": 1000, "random_state": 42,
    }
    if (
        tuple(router.get("policies", [])) != POLICY_ORDER
        or tuple(router.get("deployable_policy_order", [])) != DEPLOYABLE_POLICY_ORDER
        or router.get("logistic_regression") != expected_logistic
        or router.get("hyperparameter_search") is not False
        or router.get("random_routing_repetitions") != 100
        or router.get("random_routing_seed") != 20260817
    ):
        raise ValueError("Router policies=5/deployable=3 contract drift")
    if config.get("call_rates") != [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0]:
        raise ValueError("Router call-rate grid drift")
    gate = config.get("gate", {})
    if (
        gate.get("primary_policy") != "logistic_router"
        or gate.get("primary_nominal_call_rate") != 0.15
        or gate.get("replication_pass_rule") != "primary_policy_only"
        or gate.get("maximum_hamming_loss_increase") != 1e-12
    ):
        raise ValueError("Router primary gate drift")
    bootstrap = config.get("bootstrap", {})
    if (
        bootstrap.get("unit") != "duplicate_component"
        or bootstrap.get("repetitions") != 2000
        or bootstrap.get("seed") != 20260817
        or bootstrap.get("interval") != "percentile_95"
    ):
        raise ValueError("Router bootstrap contract drift")


def validate_replication_config(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    _canonical_config_path(config_path)
    if set(config) != REPLICATION_CONFIG_KEYS:
        raise ValueError("Replication preflight exact top-level schema drift")
    if (
        config.get("experiment_id") != EXPERIMENT_ID
        or config.get("replication_parent_experiment_id") != REPLICATION_EXPERIMENT_ID
        or config.get("run_id") != REPLICATION_RUN_ID
        or config.get("attempt_id") != REPLICATION_ATTEMPT_ID
        or type(config.get("model_seed")) is not int
        or config.get("model_seed") != REPLICATION_MODEL_SEED
        or not _same_typed_dict(config.get("seed_contract"), expected_seed_contract())
        or config.get("rq_id") != RQ_ID
        or config.get("stage") != REPLICATION_STAGE
        or config.get("tier") != "Major infrastructure preflight"
    ):
        raise ValueError("Replication preflight identity drift")
    if (
        config.get("registered_at") != REPLICATION_REGISTERED_AT
        or config.get("provenance") != REPLICATION_PROVENANCE
        or config.get("path_bases") != REPLICATION_PATH_BASES
        or config.get("artifact_contract") != REPLICATION_ARTIFACT_CONTRACT
        or not _runtime_environment_exact(config)
        or config.get("risk_coverage") != REPLICATION_RISK_COVERAGE
        or config.get("commands") != REPLICATION_COMMANDS
    ):
        raise ValueError("Replication preflight governance contract drift")
    authorization = config.get("authorization", {})
    if set(authorization) != REPLICATION_AUTHORIZATION_KEYS or (
        type(authorization.get("model_seed")) is not int
        or authorization.get("model_seed") != 44
        or authorization.get("no_result_preflight") is not True
        or any(
            authorization.get(key) is not False
            for key in (
                "formal_router_training", "formal_result_computation", "validation_access",
                "test_access", "model_loading_or_forward", "raw_text_access",
            )
        )
    ):
        raise PermissionError("Replication preflight authorization drift")
    if config.get("outputs") != expected_replication_outputs():
        raise ValueError("Replication preflight canonical output drift")
    if set(config.get("implementation", {})) != REPLICATION_IMPLEMENTATION_KEYS:
        raise ValueError("Replication preflight implementation inventory drift")
    if any(
        config["implementation"][name].get("path") != expected_path
        for name, expected_path in REPLICATION_IMPLEMENTATION_PATHS.items()
    ):
        raise ValueError("Replication preflight implementation path drift")
    if set(config.get("prerequisites", {})) != REPLICATION_PREREQUISITE_KEYS:
        raise ValueError("Replication preflight upstream inventory drift")
    if set(config.get("input", {})) != {"paired_oof"}:
        raise ValueError("Replication preflight input inventory drift")
    expected_base = "experiments/stack-overflow-emotion-gold/oof-router"
    expected_paths = {
        "oof_verification": f"{expected_base}/runs/{REPLICATION_RUN_ID}/attempt-1/verification.json",
        "oof_completion": f"{expected_base}/runs/{REPLICATION_RUN_ID}/attempt-1/oof-complete.json",
        "exp059_run": f"{expected_base}/runs/{REPLICATION_RUN_ID}/attempt-1/calibration/run.json",
        "exp059_verification": f"{expected_base}/runs/{REPLICATION_RUN_ID}/attempt-1/calibration/verification.json",
        "exp059_calibration_parameters": f"{expected_base}/runs/{REPLICATION_RUN_ID}/attempt-1/calibration/calibration-parameters.json",
        "exp059_calibration_completion": f"{expected_base}/runs/{REPLICATION_RUN_ID}/attempt-1/calibration-complete.json",
    }
    if any(
        config["prerequisites"][name].get("path") != expected
        for name, expected in expected_paths.items()
    ):
        raise ValueError("Replication preflight prerequisite path drift")
    if config["input"]["paired_oof"].get("path") != (
        f"{expected_base}/private/{REPLICATION_RUN_ID}/attempt-1/paired-oof.npz"
    ):
        raise ValueError("Replication preflight paired input path drift")
    if not _same_typed_dict(config.get("resources"), REPLICATION_RESOURCE_CONTRACT):
        raise ValueError("Replication preflight resource contract drift")
    if config.get("claim_boundary") != REPLICATION_CLAIM_BOUNDARY:
        raise ValueError("Replication preflight claim boundary drift")
    _validate_replication_method(config)
    for record in config["implementation"].values():
        require_replication_record(record, mode=0o644)
    values = validate_replication_upstreams(config)
    validate_formal_source_contract(config)
    return values


class Checks:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, name: str, passed: bool, detail: Any = None) -> None:
        self.rows.append({"name": name, "passed": bool(passed), "detail": detail})

    @property
    def failed(self) -> list[dict[str, Any]]:
        return [row for row in self.rows if not row["passed"]]


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


def _verify_legacy(config_path: Path) -> int:
    config = json.loads(_secure_read_bytes(config_path, mode=0o644)[0].decode("utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID or config.get("rq_id") != RQ_ID:
        raise ValueError("EXP-060 config identity drift")
    run_dir = resolve_project(config["outputs"]["preflight_run_dir"])
    run_path = run_dir / "run.json"
    contract_path = run_dir / "preflight-contract.json"
    if not run_path.is_file() or not contract_path.is_file():
        raise FileNotFoundError("EXP-060 preflight outputs are incomplete")
    sealed_verification = run_dir / "verification.json"
    sealed_summary = run_dir / "VERIFICATION-SUMMARY.md"
    if sealed_verification.is_file() and sealed_summary.is_file():
        existing = json.loads(sealed_verification.read_text(encoding="utf-8"))
        if existing.get("status") != "Passed":
            raise PermissionError("Legacy EXP-060 preflight archive is not Passed")
        return 0

    checks = Checks()
    run = json.loads(_secure_read_bytes(run_path, mode=0o644)[0].decode("utf-8"))
    contract = json.loads(_secure_read_bytes(contract_path, mode=0o644)[0].decode("utf-8"))
    checks.add("run_identity", run.get("experiment_id") == EXPERIMENT_ID and run.get("rq_id") == RQ_ID)
    checks.add("run_stage", run.get("stage") == "no-result-preflight")
    checks.add("run_completed", run.get("status") == "Completed")
    checks.add("runner_checks_all_passed", run["checks"]["failed"] == 0)

    authorization = config["authorization"]
    for key in (
        "formal_router_training",
        "formal_result_computation",
        "validation_access",
        "test_access",
        "model_loading_or_forward",
        "raw_text_access",
    ):
        checks.add(f"authorization_{key}_false", authorization[key] is False)
        checks.add(f"run_authorization_{key}_false", run["authorization"][key] is False)

    flags = run["execution_flags"]
    for key, value in flags.items():
        checks.add(f"execution_flag_{key}_false", value is False)

    for section in ("implementation", "prerequisites", "input"):
        for index, record in enumerate(iter_records(config[section])):
            path = require_record(record)
            checks.add(f"frozen_{section}_{index}", path.stat().st_size == record["bytes"])

    frozen_sources = run["source_artifacts"]
    expected_frozen_names = {"config", *config["implementation"].keys()}
    checks.add("frozen_source_keys", set(frozen_sources) == expected_frozen_names, sorted(frozen_sources))
    for key, record in frozen_sources.items():
        path = require_record(record)
        checks.add(f"frozen_source_{key}_exists", path.is_file())
        if key == "config":
            checks.add("frozen_config_matches", path.read_bytes() == config_path.read_bytes())
        else:
            source = require_record(config["implementation"][key])
            checks.add(f"frozen_source_{key}_matches", path.read_bytes() == source.read_bytes())

    paired = require_record(config["input"]["paired_oof"])
    schema = npz_header_schema(paired)
    checks.add("paired_schema_exact", schema == expected_paired_schema())
    checks.add("paired_mode_0600", stat.S_IMODE(paired.stat().st_mode) == 0o600)
    checks.add("paired_parent_mode_0700", stat.S_IMODE(paired.parent.stat().st_mode) == 0o700)

    calibration_path = require_record(config["prerequisites"]["exp059_calibration_parameters"])
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    selected = {
        family: calibration["families"][family]["selected_calibrator"] for family in ("m1", "m3")
    }
    temperatures = {
        family: calibration["families"][family]["final_temperature"] for family in ("m1", "m3")
    }
    checks.add("identity_calibration_recomputed", selected == {"m1": "identity", "m3": "identity"})
    checks.add("identity_temperature_recomputed", temperatures == {"m1": 1.0, "m3": 1.0})

    features = tuple(config["feature_contract"]["ordered_features"])
    checks.add("config_feature_order_exact", features == FEATURE_NAMES)
    checks.add("contract_feature_order_exact", tuple(contract["ordered_model_features"]) == FEATURE_NAMES)
    checks.add("contract_feature_count", contract["feature_count"] == 14)
    violations = [
        name for name in features if any(name.startswith(prefix) for prefix in PROHIBITED_RUNTIME_PREFIXES)
    ]
    checks.add("no_prohibited_model_feature", not violations, violations)
    checks.add("contract_result_bearing_false", contract["result_bearing"] is False)
    checks.add("contract_nested_cross_fitting", contract["nested_cross_fitting_required"] is True)
    checks.add("contract_formal_training_false", contract["formal_router_training_authorized"] is False)
    checks.add("contract_formal_results_false", contract["formal_result_computation_authorized"] is False)
    checks.add("contract_validation_false", contract["validation_access"] is False)
    checks.add("contract_test_false", contract["test_access"] is False)
    expected_schema_rows = [
        {"array_name": name, **details} for name, details in sorted(expected_paired_schema().items())
    ]
    checks.add("contract_schema_is_header_only", contract["input_schema"] == expected_schema_rows)

    formal_run = resolve_project(config["outputs"]["formal_run_dir"])
    formal_private = resolve_project(config["outputs"]["formal_private_dir"])
    checks.add("formal_run_still_absent", not formal_run.exists(), display_path(formal_run))
    checks.add("formal_private_still_absent", not formal_private.exists(), display_path(formal_private))

    allowed_public_suffixes = {".json", ".md", ".py"}
    unexpected = [
        display_path(path) for path in run_dir.rglob("*")
        if path.is_file() and path.suffix not in allowed_public_suffixes
    ]
    checks.add("no_row_level_artifact_type", not unexpected, unexpected)

    verification = {
        "schema_version": "exp-060-preflight-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "rq_id": RQ_ID,
        "verified_at": utc_now(),
        "status": "Failed" if checks.failed else "Passed",
        "independent": True,
        "runner_imported": False,
        "checks": {
            "passed": len(checks.rows) - len(checks.failed),
            "failed": len(checks.failed),
            "total": len(checks.rows),
            "records": checks.rows,
        },
        "verified_artifacts": {
            "run": artifact(run_path),
            "contract": artifact(contract_path),
            "paired_oof_header_only": artifact(paired),
            "calibration_parameters": artifact(calibration_path),
        },
        "execution_claims": {
            "router_fitted": False,
            "real_router_target_computed": False,
            "router_result_computed": False,
            "validation_accessed": False,
            "test_accessed": False,
            "raw_text_accessed": False,
            "model_loaded_or_forward_run": False,
        },
        "claim_boundary": "Verified no-result preflight only; formal EXP-060 remains unauthorized.",
    }
    atomic_json(run_dir / "verification.json", verification)
    summary = (
        "# EXP-060 Preflight Verification Summary\n\n"
        f"- Status: `{verification['status']}`\n"
        f"- Checks: `{verification['checks']['passed']}/{verification['checks']['total']}` passed\n"
        "- Independent verifier imported the runner: `false`\n"
        "- Router/scaler fitted: `false`\n"
        "- Real target, route score or metric computed: `false`\n"
        "- Validation/test/raw-text/model access: `false`\n"
        "- Claim boundary: protocol and environment preflight only; formal routing evidence does not yet exist.\n"
    )
    (run_dir / "VERIFICATION-SUMMARY.md").write_text(summary, encoding="utf-8")
    print(json.dumps({
        "status": verification["status"],
        "checks_passed": verification["checks"]["passed"],
        "checks_total": verification["checks"]["total"],
        "run_dir": display_path(run_dir),
    }, sort_keys=True))
    return 1 if checks.failed else 0


def _assert_replication_preflight_tree(
    run_dir: Path,
    config: dict[str, Any],
    *,
    verified: bool,
) -> tuple[Path, Path, Path]:
    _require_directory_metadata(run_dir, 0o755)
    expected = {"run.json", "preflight-contract.json", "frozen-sources"}
    if verified:
        expected |= {"verification.json", "VERIFICATION-SUMMARY.md"}
    entries = {entry.name: entry for entry in os.scandir(run_dir)}
    if set(entries) != expected:
        raise ValueError(f"Replication preflight public tree drift: {sorted(entries)}")
    frozen_dir = run_dir / "frozen-sources"
    _require_directory_metadata(frozen_dir, 0o755)
    expected_frozen = {
        "config.json",
        *(
            Path(record["path"]).name
            for record in config["implementation"].values()
        ),
    }
    target_names = [
        "config.json",
        *(Path(record["path"]).name for record in config["implementation"].values()),
    ]
    if len(target_names) != len(set(target_names)):
        raise ValueError("Replication preflight frozen-source basenames are not unique")
    frozen_entries = {entry.name: entry for entry in os.scandir(frozen_dir)}
    if set(frozen_entries) != expected_frozen:
        raise ValueError(f"Replication preflight frozen tree drift: {sorted(frozen_entries)}")
    for name, entry in entries.items():
        if name != "frozen-sources":
            _require_regular_metadata(Path(entry.path), mode=0o644)
    for entry in frozen_entries.values():
        _require_regular_metadata(Path(entry.path), mode=0o644)
    return run_dir / "run.json", run_dir / "preflight-contract.json", frozen_dir


def _record_matches(record: dict[str, Any], path: Path) -> bool:
    return record == artifact(path)


def _parse_utc(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Timestamp must be a string")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("Timestamp must be canonical UTC")
    return parsed


def verify_replication_preflight(config_path: Path) -> int:
    started = time.monotonic()
    config_path = _canonical_config_path(config_path)
    config = json.loads(_secure_read_bytes(config_path, mode=0o644)[0].decode("utf-8"))
    upstream_values = validate_replication_config(config_path, config)
    paths = replication_output_paths(config)
    if os.path.lexists(paths["selection"]):
        raise FileExistsError("Selection blocks preflight verification")
    for name in ("formal_public", "formal_private", "completion"):
        if os.path.lexists(paths[name]):
            raise FileExistsError(f"Formal result blocks preflight verification: {paths[name]}")
    output_path = paths["preflight"] / "verification.json"
    summary_path = paths["preflight"] / "VERIFICATION-SUMMARY.md"
    if os.path.lexists(output_path) or os.path.lexists(summary_path):
        raise FileExistsError("Refusing to overwrite append-only preflight verification")
    run_path, contract_path, frozen_dir = _assert_replication_preflight_tree(
        paths["preflight"], config, verified=False
    )
    run = json.loads(_secure_read_bytes(run_path, mode=0o644)[0].decode("utf-8"))
    contract = json.loads(_secure_read_bytes(contract_path, mode=0o644)[0].decode("utf-8"))
    if set(run) != REPLICATION_RUN_KEYS:
        raise ValueError("Replication preflight run exact schema drift")
    if set(contract) != REPLICATION_CONTRACT_KEYS:
        raise ValueError("Replication preflight contract exact schema drift")
    expected_identity = {
        "experiment_id": EXPERIMENT_ID,
        "replication_parent_experiment_id": REPLICATION_EXPERIMENT_ID,
        "run_id": REPLICATION_RUN_ID,
        "attempt_id": REPLICATION_ATTEMPT_ID,
        "model_seed": REPLICATION_MODEL_SEED,
        "seed_contract": expected_seed_contract(),
        "rq_id": RQ_ID,
        "stage": REPLICATION_STAGE,
    }
    if any(run.get(key) != value for key, value in expected_identity.items()):
        raise ValueError("Replication preflight run identity drift")
    if any(contract.get(key) != value for key, value in expected_identity.items()):
        raise ValueError("Replication preflight contract identity drift")
    if (
        run.get("schema_version") != REPLICATION_RUN_SCHEMA
        or run.get("status") != "CompletedAwaitingVerification"
        or run.get("tier") != "Major infrastructure preflight"
        or run.get("config") != artifact(config_path)
        or run.get("upstreams") != config["prerequisites"]
        or run.get("input") != config["input"]["paired_oof"]
        or run.get("contract") != artifact(contract_path)
        or run.get("claim_boundary") != REPLICATION_CLAIM_BOUNDARY
    ):
        raise ValueError("Replication preflight run provenance drift")
    started_at = _parse_utc(run.get("started_at_utc"))
    completed_at = _parse_utc(run.get("completed_at_utc"))
    if started_at > completed_at:
        raise ValueError("Replication preflight run chronology drift")
    run_checks = run.get("checks")
    if (
        not isinstance(run_checks, list)
        or [row.get("name") for row in run_checks] != list(RUN_REQUIRED_CHECK_NAMES)
        or any(set(row) != {"name", "passed", "detail"} for row in run_checks)
        or any(row.get("passed") is not True for row in run_checks)
        or type(run.get("check_count")) is not int
        or run.get("check_count") != len(RUN_REQUIRED_CHECK_NAMES)
        or type(run.get("passed_count")) is not int
        or run.get("passed_count") != len(RUN_REQUIRED_CHECK_NAMES)
        or type(run.get("failed_count")) is not int
        or run.get("failed_count") != 0
    ):
        raise ValueError("Replication preflight runner check inventory drift")
    if run.get("execution_claims") != {
        name: False for name in sorted(EXECUTION_CLAIM_KEYS)
    }:
        raise ValueError("Replication preflight execution claims drift")
    run_resources = run.get("resources", {})
    if not _runtime_resource_record_exact(
        run_resources,
        wall_budget=float(config["resources"]["preflight_wall_seconds"]),
        memory_budget=float(config["resources"]["peak_memory_gb"]),
    ):
        raise ValueError("Replication preflight runner resource drift")

    input_path = require_replication_record(config["input"]["paired_oof"], mode=0o600)
    input_schema = npz_header_schema_strict(input_path)
    expected_schema_rows = [
        {"array_name": name, **details} for name, details in sorted(input_schema.items())
    ]
    if (
        contract.get("schema_version") != REPLICATION_CONTRACT_SCHEMA
        or contract.get("result_bearing") is not False
        or contract.get("input_schema") != expected_schema_rows
        or contract.get("ordered_model_features") != list(FEATURE_NAMES)
        or contract.get("feature_count") != 14
        or contract.get("nested_cross_fitting_required") is not True
        or not _replication_calibration_exact(contract.get("router_replication_calibration"))
        or contract.get("policies") != list(POLICY_ORDER)
        or contract.get("deployable_policy_order") != list(DEPLOYABLE_POLICY_ORDER)
        or any(
            contract.get(key) is not False
            for key in (
                "formal_router_training_authorized", "formal_result_computation_authorized",
                "validation_access", "test_access", "raw_text_access", "model_loading_or_forward",
            )
        )
        or not _same_typed_dict(contract.get("resource_contract"), config["resources"])
        or contract.get("claim_boundary") != REPLICATION_CLAIM_BOUNDARY
    ):
        raise ValueError("Replication preflight contract payload drift")
    if public_sensitive_paths(run) or public_sensitive_paths(contract):
        raise ValueError("Replication preflight public privacy drift")

    source_artifacts = run.get("source_artifacts")
    if not isinstance(source_artifacts, dict) or set(source_artifacts) != {
        "config", *REPLICATION_IMPLEMENTATION_KEYS
    }:
        raise ValueError("Replication preflight frozen source inventory drift")
    frozen_by_name = {entry.name: Path(entry.path) for entry in os.scandir(frozen_dir)}
    config_frozen = frozen_by_name["config.json"]
    if not _record_matches(source_artifacts["config"], config_frozen):
        raise ValueError("Replication preflight frozen config record drift")
    if _secure_read_bytes(config_frozen, mode=0o644)[0] != _secure_read_bytes(config_path, mode=0o644)[0]:
        raise ValueError("Replication preflight frozen config bytes drift")
    for name, live_record in config["implementation"].items():
        live = require_replication_record(live_record, mode=0o644)
        frozen = frozen_by_name[live.name]
        if (
            not _record_matches(source_artifacts[name], frozen)
            or _secure_read_bytes(frozen, mode=0o644)[0]
            != _secure_read_bytes(live, mode=0o644)[0]
        ):
            raise ValueError(f"Replication preflight frozen source drift: {name}")

    formal_paths = validate_formal_source_contract(config)
    preflight_test_path = require_replication_record(
        config["implementation"]["preflight_tests"], mode=0o644
    )
    independent_child_tests = {
        "preflight": _run_child_test(preflight_test_path),
        "formal": _run_child_test(formal_paths["tests"]),
        "launchers": _run_child_test(formal_paths["launcher_tests"]),
    }
    independent_child_tests_passed = (
        _child_test_result_exact(independent_child_tests["preflight"], preflight_test_path)
        and _child_test_result_exact(independent_child_tests["formal"], formal_paths["tests"])
        and _child_test_result_exact(
            independent_child_tests["launchers"], formal_paths["launcher_tests"]
        )
        and _runtime_environment_exact(config)
    )
    checks = Checks()
    checks.add("verification.config", True)
    checks.add("verification.run_schema", True)
    checks.add("verification.contract_schema", True)
    checks.add("verification.runner_checks", True)
    checks.add("verification.upstream_chain", set(upstream_values) == REPLICATION_PREREQUISITE_KEYS)
    checks.add("verification.input_header_only", input_schema == expected_paired_schema())
    checks.add("verification.router_identity_calibration", True)
    checks.add("verification.policies_5", tuple(config["router"]["policies"]) == POLICY_ORDER)
    checks.add(
        "verification.deployable_policy_order_3",
        tuple(config["router"]["deployable_policy_order"]) == DEPLOYABLE_POLICY_ORDER,
    )
    checks.add(
        "verification.formal_source_contract",
        independent_child_tests_passed,
        independent_child_tests,
    )
    checks.add("verification.frozen_sources", True)
    checks.add("verification.public_modes", True)
    checks.add("verification.public_privacy", True)
    checks.add("verification.formal_public_absent", not os.path.lexists(paths["formal_public"]))
    checks.add("verification.formal_private_absent", not os.path.lexists(paths["formal_private"]))
    checks.add("verification.completion_absent", not os.path.lexists(paths["completion"]))
    checks.add("verification.selection_absent", not os.path.lexists(paths["selection"]))
    elapsed = time.monotonic() - started
    observed_rss = peak_rss_gb()
    checks.add(
        "verification.resources.wall_seconds",
        _finite_nonnegative_number(elapsed)
        and elapsed <= config["resources"]["verification_wall_seconds"],
        elapsed,
    )
    checks.add(
        "verification.resources.peak_memory_gb",
        _finite_nonnegative_number(observed_rss)
        and observed_rss <= config["resources"]["peak_memory_gb"],
        observed_rss,
    )
    checks.add("verification.resources.zero_cost_forward", True)
    if tuple(row["name"] for row in checks.rows) != VERIFICATION_REQUIRED_CHECK_NAMES:
        raise RuntimeError("Independent preflight verification check-name inventory drift")
    if checks.failed:
        raise RuntimeError(
            "Seed-44 independent preflight verification failed before claim: "
            + ", ".join(row["name"] for row in checks.failed)
        )
    formal_sources = {
        name: source_artifacts[name]
        for name in FORMAL_IMPLEMENTATION_KEYS
    }
    verification = {
        "schema_version": REPLICATION_VERIFICATION_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "replication_parent_experiment_id": REPLICATION_EXPERIMENT_ID,
        "run_id": REPLICATION_RUN_ID,
        "attempt_id": REPLICATION_ATTEMPT_ID,
        "model_seed": REPLICATION_MODEL_SEED,
        "seed_contract": expected_seed_contract(),
        "rq_id": RQ_ID,
        "scope": "preflight",
        "verified_at_utc": utc_now(),
        "status": "Passed",
        "passed_count": len(checks.rows),
        "failed_count": 0,
        "checks": checks.rows,
        "independent": True,
        "runner_imported": False,
        "execution_claims": {name: False for name in sorted(EXECUTION_CLAIM_KEYS)},
        "verified_artifacts": {
            "config": artifact(config_path),
            "run": artifact(run_path),
            "contract": artifact(contract_path),
            "input": dict(config["input"]["paired_oof"]),
            "upstreams": dict(config["prerequisites"]),
            "frozen_sources": dict(source_artifacts),
            "formal_sources": formal_sources,
        },
        "resources": {
            "wall_seconds": elapsed,
            "peak_process_rss_gb": observed_rss,
            "api_cost_usd": 0,
            "gpu_cost_usd": 0,
            "model_forward_runs": 0,
        },
        "claim_boundary": VERIFICATION_CLAIM_BOUNDARY,
    }
    if set(verification) != REPLICATION_VERIFICATION_KEYS:
        raise RuntimeError("Independent preflight verification schema inventory drift")
    verification_payload = _json_bytes(verification)
    summary = (
        "# Seed-44 EXP-060 No-Result Preflight Verification\n\n"
        "- Status: `Passed`\n"
        f"- Checks: `{len(checks.rows)}/{len(checks.rows)}`\n"
        "- Independent verifier imported the runner: `false`\n"
        "- Feature/target/router/metric/bootstrap computation: `false`\n"
        "- Formal router execution remains separately authorized.\n"
    ).encode("utf-8")
    _create_bytes_once(output_path, verification_payload, 0o644)
    _create_bytes_once(summary_path, summary, 0o644)
    _assert_replication_preflight_tree(paths["preflight"], config, verified=True)
    print(
        json.dumps(
            {"status": "Passed", "passed": len(checks.rows), "failed": 0},
            sort_keys=True,
        )
    )
    return 0


def verify(config_path: Path) -> int:
    lexical = Path(os.path.abspath(config_path))
    config = json.loads(_secure_read_bytes(lexical, mode=0o644)[0].decode("utf-8"))
    if is_replication_preflight(config):
        return verify_replication_preflight(lexical)
    return _verify_legacy(lexical)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(verify(parse_args().config))
