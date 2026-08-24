#!/usr/bin/env python3
"""Independent governed seed-44 launcher for the frozen EXP-060 verifier.

This module validates the v3/preflight release contract, temporarily adapts only
the two frozen governance constants and two public sidecar writers, and calls the
byte-pinned verifier once.  It never imports the runner or alters science code.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import resource
import shlex
import stat
import sys
import time
from types import ModuleType
from typing import Any


FORMAL_CONFIG_SCHEMA = "exp-router-replication-config-v3"
PREFLIGHT_CONFIG_SCHEMA = "exp-router-replication-preflight-config-v1"
PREFLIGHT_RUN_SCHEMA = "exp-router-replication-preflight-run-v1"
PREFLIGHT_CONTRACT_SCHEMA = "exp-router-replication-preflight-contract-v1"
PREFLIGHT_VERIFICATION_SCHEMA = "exp-router-replication-preflight-verification-v1"
FORMAL_EXPERIMENT_ID = "EXP-062"
PREFLIGHT_EXPERIMENT_ID = "EXP-060"
PREFLIGHT_PARENT_EXPERIMENT_ID = "EXP-062"
RUN_ID = "exp-062-seed-44-router-replication"
ATTEMPT_ID = "attempt-1"
MODEL_SEED = 44
RQ_ID = "RQ-S3"
FORMAL_STAGE = "pre-qwen-router-replication"
PREFLIGHT_STAGE = "pre-qwen-router-replication-preflight"

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
CONFIGS_DIR = SCRIPT_DIR / "configs"
FORMAL_CONFIG_NAME = "exp-062-seed-44-router-replication-router-formal-attempt-1.json"
BASE_RUNNER_PATH = SCRIPT_DIR / "run_exp060_router.py"
BASE_VERIFIER_PATH = SCRIPT_DIR / "verify_exp060_router.py"
BASE_TESTS_PATH = SCRIPT_DIR / "tests" / "test_exp060_router.py"
RUNNER_LAUNCHER_PATH = SCRIPT_DIR / "run_exp060_router_v3.py"
VERIFIER_LAUNCHER_PATH = SCRIPT_DIR / "verify_exp060_router_v3.py"
LAUNCHER_TESTS_PATH = SCRIPT_DIR / "tests" / "test_exp060_router_v3.py"
PROTOCOL_PATH = (
    PROJECT_ROOT
    / "experiments/stack-overflow-emotion-gold/protocols/exp-060-pre-qwen-deployable-router.md"
)

BASE_RUNNER_SHA256 = "873d53f45d587918b7c1b466a93b8da0b397732baa072af1b43e50a16150dc65"
BASE_VERIFIER_SHA256 = "920f6565bd378c8f7cfe415a78e505123336602fb228dad95771fcc14e471b15"
BASE_TESTS_SHA256 = "4e6572f996fecd81f8715f808f1fdd44a5ae4d351813e605936478a97e86ddff"

FORMAL_IMPLEMENTATION_KEYS = {
    "protocol",
    "runner",
    "verifier",
    "tests",
    "runner_launcher",
    "verifier_launcher",
    "launcher_tests",
}
PREFLIGHT_IMPLEMENTATION_KEYS = {
    "protocol",
    "preflight_runner",
    "preflight_verifier",
    "preflight_tests",
    *FORMAL_IMPLEMENTATION_KEYS - {"protocol"},
}
FORMAL_PREREQUISITE_KEYS = {
    "oof_verification",
    "exp059_run",
    "exp059_verification",
    "exp059_calibration_parameters",
    "exp060_preflight_verification",
}
BASE_PREREQUISITE_KEYS = FORMAL_PREREQUISITE_KEYS - {"exp060_preflight_verification"}
PREFLIGHT_UPSTREAM_KEYS = {
    "oof_verification",
    "oof_completion",
    "exp059_run",
    "exp059_verification",
    "exp059_calibration_parameters",
    "exp059_calibration_completion",
}
POLICIES = (
    "m1_only",
    "m3_only",
    "m1_max_entropy",
    "m1_threshold_proximity",
    "logistic_router",
)
DEPLOYABLE_POLICIES = POLICIES[2:]
REPLICATION_CALIBRATION = {
    "calibrator": "identity",
    "temperature": 1.0,
    "probability_source": "direct_sigmoid_of_raw_oof_logits",
    "role": "frozen_exp060_replication_only",
}
PREFLIGHT_CLAIM_BOUNDARY = (
    "Seed-44 no-result router preflight only; no feature matrix, target, fitted "
    "router, metric, bootstrap, primary gate, or selection result."
)
FORMAL_CLAIM_BOUNDARY = (
    "Fully nested DATA-SO-TASK-V1 train-OOF development evidence for the registered "
    "seed-44 M1/M3 pair only; not an independent-test deployment benefit, cross-seed "
    "result, general forum result, or emotional-mechanism claim."
)
SEED_CONTRACT = {
    "model_seed": 44,
    "python_seed": 44,
    "numpy_seed": 44,
    "torch_seed": 44,
    "m1_batch_seed": 44,
    "m3_head_seed": 44,
    "m3_batch_seed": 44,
    "m3_lora_seed": 100044,
}
EXECUTION_CLAIMS = {
    "array_values_loaded",
    "real_features_constructed",
    "real_router_targets_constructed",
    "scaler_or_router_fitted",
    "router_metrics_computed",
    "bootstrap_computed",
    "validation_accessed",
    "test_accessed",
    "raw_text_accessed",
    "model_loaded_or_forward_run",
    "formal_router_training",
    "formal_result_computation",
}
FORMAL_TOP_KEYS = {
    "schema_version", "experiment_id", "run_id", "attempt_id", "seed_contract",
    "rq_id", "tier", "stage", "registered_at", "authorization", "provenance",
    "path_bases", "artifact_contract", "runtime", "implementation", "prerequisites",
    "input", "outputs", "data", "cross_fitting", "thresholds", "target_contract",
    "feature_contract", "router", "call_rates", "gate", "risk_coverage", "bootstrap",
    "resources", "claim_boundary", "commands",
}
PREFLIGHT_TOP_KEYS = {
    "schema_version", "experiment_id", "replication_parent_experiment_id", "run_id",
    "attempt_id", "model_seed", "seed_contract", "rq_id", "tier", "stage",
    "registered_at", "authorization", "provenance", "path_bases", "artifact_contract",
    "runtime", "implementation", "prerequisites", "input", "outputs", "data",
    "cross_fitting", "thresholds", "target_contract", "feature_contract", "router",
    "call_rates", "gate", "risk_coverage", "bootstrap", "resources", "claim_boundary",
    "commands",
}
PREFLIGHT_RUN_KEYS = {
    "schema_version", "experiment_id", "replication_parent_experiment_id", "run_id",
    "attempt_id", "model_seed", "seed_contract", "rq_id", "tier", "stage", "status",
    "started_at_utc", "completed_at_utc", "config", "upstreams", "input",
    "source_artifacts", "contract", "check_count", "passed_count", "failed_count",
    "checks", "resources", "execution_claims", "claim_boundary",
}
PREFLIGHT_CONTRACT_KEYS = {
    "schema_version", "experiment_id", "replication_parent_experiment_id", "run_id",
    "attempt_id", "model_seed", "seed_contract", "rq_id", "stage", "result_bearing",
    "data_scope", "input_schema", "ordered_model_features", "feature_count",
    "prohibited_runtime_feature_classes", "nested_cross_fitting_required",
    "router_replication_calibration", "policies", "deployable_policy_order",
    "formal_router_training_authorized", "formal_result_computation_authorized",
    "validation_access", "test_access", "raw_text_access", "model_loading_or_forward",
    "resource_contract", "claim_boundary",
}
PREFLIGHT_VERIFICATION_KEYS = {
    "schema_version", "experiment_id", "replication_parent_experiment_id", "run_id",
    "attempt_id", "model_seed", "seed_contract", "rq_id", "scope", "verified_at_utc",
    "status", "passed_count", "failed_count", "checks", "independent",
    "runner_imported", "execution_claims", "verified_artifacts", "resources",
    "claim_boundary",
}
VERIFIED_ARTIFACT_KEYS = {
    "config", "run", "contract", "input", "upstreams", "frozen_sources", "formal_sources"
}
PUBLIC_ROOT_NAMES = {
    "feature-contract.json", "fold-summary.csv", "router-discrimination.json",
    "call-rate-performance.csv", "policy-comparisons.csv", "random-routing.csv",
    "selected-operating-point.json", "bootstrap.json", "routed-risk-coverage.csv",
    "positive-label-retention.csv", "call-rate-performance.png",
    "routed-risk-coverage.png", "REPORT.md", "run.json", "frozen-sources",
}
PUBLIC_SENSITIVE_KEYS = {
    "sample_id", "sample_ids", "component_id", "component_ids", "fold_id", "fold_ids",
    "gold", "logit", "logits", "probability", "probabilities", "feature", "features",
    "feature_matrix", "target", "targets", "router_targets", "route_score", "route_scores",
    "route_mask", "route_masks", "prediction", "predictions", "raw_text", "text",
}
PREFLIGHT_RUN_CHECK_NAMES = (
    "config.exact_schema", "config.identity", "config.authorization_no_result_only",
    "config.upstream_chain", "input.header_schema_only", "input.mode_0600_nlink1",
    "input.parent_mode_0700", "exp059.diagnostic_calibrators_allowed",
    "exp059.router_replication_identity", "router.policies_5",
    "router.deployable_policy_order_3", "router.formal_source_contract",
    "features.exact_14", "cross_fitting.inner3_outer4", "outputs.preflight_absent",
    "outputs.formal_public_absent", "outputs.formal_private_absent",
    "outputs.completion_absent", "outputs.selection_absent", "runtime.numpy_available",
    "runtime.scikit_learn_available", "tests.preflight", "tests.formal",
    "tests.launchers", "resources.wall_seconds", "resources.peak_memory_gb",
    "resources.api_gpu_forward_zero",
)
PREFLIGHT_VERIFICATION_CHECK_NAMES = (
    "verification.config", "verification.run_schema", "verification.contract_schema",
    "verification.runner_checks", "verification.upstream_chain",
    "verification.input_header_only", "verification.router_identity_calibration",
    "verification.policies_5", "verification.deployable_policy_order_3",
    "verification.formal_source_contract", "verification.frozen_sources",
    "verification.public_modes", "verification.public_privacy",
    "verification.formal_public_absent", "verification.formal_private_absent",
    "verification.completion_absent", "verification.selection_absent",
    "verification.resources.wall_seconds", "verification.resources.peak_memory_gb",
    "verification.resources.zero_cost_forward",
)
EXPECTED_INPUT_SCHEMA = {
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
PREFLIGHT_RESOURCE_CONTRACT = {
    "preflight_wall_seconds": 300,
    "verification_wall_seconds": 300,
    "peak_memory_gb": 2.0,
    "api_cost_usd": 0,
    "gpu_cost_usd": 0,
    "model_forward_runs": 0,
}
FORMAL_RESOURCE_CONTRACT = {
    "formal_wall_seconds": 1800,
    "verification_wall_seconds": 1800,
    "formal_peak_memory_gb": 4.0,
    "peak_memory_gb": 4.0,
    "api_cost_usd": 0,
    "gpu_cost_usd": 0,
    "model_forward_runs": 0,
}
EXPECTED_PROVENANCE = {
    "base_git_head": "88cf763c1161aa8afda0f3d0b4ae4bb1c9c93833",
    "train_sha256": "fc2f853b5b8afb78253ca3a96b5093d2fd12ea7063801f57bf138c9d5cf528fc",
    "fold_manifest_sha256": "82929b1d837ceb9825c5bc39a8fea18f6d0736fca42aad630f3788b1ff8139d8",
    "source_order_sha256": "c9e4bd1eb2bdbb33c833234754c493b8818aa6c610acaf88659ae74fa94848a3",
}
EXPECTED_PATH_BASES = {
    "artifact_records": "projects/llm-forum-text-emotion-recognition",
    "commands": "/Users/phoenix/Assistant/NeuroScience",
}
EXPECTED_RUNTIME = {
    "python_executable": "/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python",
    "python_version": "3.10.20",
    "numpy_version": "2.2.6",
    "scikit_learn_version": "1.7.2",
    "scipy_version": "1.15.3",
    "matplotlib_version": "3.10.7",
    "mplconfigdir": "/private/tmp/exp060-matplotlib",
}
PREFLIGHT_ARTIFACT_CONTRACT = {
    "public_directory_mode": "0755", "public_file_mode": "0644",
    "private_directory_mode": "0700", "private_file_mode": "0600",
    "public_row_level_data": False,
}
FORMAL_ARTIFACT_CONTRACT = {
    "float_comparison_tolerance": 1e-12,
    "public_directory_mode": "0755", "public_file_mode": "0644",
    "private_directory_mode": "0700", "private_file_mode": "0600",
    "private_npz": "router-oof.npz",
    "private_arrays": [
        "sample_ids", "component_ids", "fold_ids", "gold", "features", "router_targets",
        "nested_m1_thresholds", "nested_m3_thresholds", "m1_thresholds", "m3_thresholds",
        "m1_predictions", "m3_predictions", "route_scores", "route_masks", "score_cutoffs",
        "scaler_mean", "scaler_scale", "router_coef", "router_intercept", "router_n_iter",
    ],
    "public_files": [
        "feature-contract.json", "fold-summary.csv", "router-discrimination.json",
        "call-rate-performance.csv", "policy-comparisons.csv", "random-routing.csv",
        "selected-operating-point.json", "bootstrap.json", "routed-risk-coverage.csv",
        "positive-label-retention.csv", "call-rate-performance.png",
        "routed-risk-coverage.png", "REPORT.md", "run.json", "frozen-sources",
    ],
    "public_row_level_data": False,
    "forbidden_public_suffixes": [".npy", ".npz", ".parquet", ".jsonl"],
}
EXPECTED_DATA = {
    "protocol_id": "DATA-SO-TASK-V1", "split": "train-oof", "rows": 3360,
    "duplicate_components": 3277, "upstream_seed": 44,
    "source_order_sha256": "c9e4bd1eb2bdbb33c833234754c493b8818aa6c610acaf88659ae74fa94848a3",
    "label_order": ["love", "joy", "surprise", "anger", "sadness", "fear"],
}
EXPECTED_CROSS_FITTING = {
    "outer_fold_ids": [0, 1, 2, 3, 4], "outer_router_train_folds": 4,
    "outer_router_heldout_folds": 1, "nested_threshold_recomputation": True,
    "nested_router_train_threshold_folds": 3, "outer_heldout_threshold_folds": 4,
    "reuse_exp058_duplicate_component_partition": True, "restore_exp058_source_order": True,
    "outer_router_train_single_class_policy": "stop",
    "outer_heldout_single_class_auc_policy": "pr_auc_and_roc_auc_null",
}
EXPECTED_THRESHOLDS = {
    "calibrator": "identity_for_m1_and_m3",
    "probability_source": "direct_sigmoid_of_raw_oof_logits", "grid_start": 0.05,
    "grid_end": 0.95, "grid_step": 0.01,
    "selection_order": [
        "highest_six_label_macro_f1", "lowest_hamming_loss", "closest_to_0_5",
        "lower_threshold",
    ],
    "numeric_tolerance": 1e-12,
}
EXPECTED_TARGET_CONTRACT = {
    "unit": "whole_six_bit_vector",
    "positive": "m3_row_hamming_loss_strictly_lower_than_m1", "tie_policy": "m1",
    "gold_is_training_outcome_only": True, "m3_is_training_outcome_only": True,
    "exp059_oracle_array_used_as_formal_target": False,
}
EXPECTED_FEATURE_CONTRACT = {
    "ordered_features": [
        "m1_probability_love", "m1_probability_joy", "m1_probability_surprise",
        "m1_probability_anger", "m1_probability_sadness", "m1_probability_fear",
        "m1_mean_binary_entropy", "m1_max_binary_entropy", "m1_minimum_threshold_margin",
        "m1_predicted_cardinality", "m1_highest_probability", "m1_lowest_probability",
        "character_length", "m1_token_length",
    ],
    "feature_count": 14, "scaler": "StandardScaler_fit_inside_outer_router_train",
    "forbidden_runtime_feature_classes": [
        "all_m3_values", "gold_or_correctness", "oracle_or_model_disagreement",
        "sample_component_or_fold_ids", "raw_text", "validation_or_test_statistics",
    ],
    "m1_raw_logits_included": False, "m3_token_length_included": False,
}
EXPECTED_ROUTER = {
    "policies": list(POLICIES), "deployable_policy_order": list(DEPLOYABLE_POLICIES),
    "logistic_regression": {
        "penalty": "l2", "C": 1.0, "class_weight": "balanced", "solver": "liblinear",
        "max_iter": 1000, "random_state": 42,
    },
    "hyperparameter_search": False,
    "cutoff_count_rule": "ceil_target_rate_times_outer_router_train_rows",
    "cutoff_tie_policy": "route_all_scores_equal_to_cutoff",
    "random_routing_repetitions": 100, "random_routing_seed": 20260817,
    "random_routing": {
        "unit": "duplicate_component",
        "matched_row_count_contract": "heldout_policy_routed_row_count_per_outer_fold",
        "algorithm": "seeded_component_permutation_then_zero_one_subset_sum",
        "closest_count_tie_policy": "lower_row_count_before_overshoot",
        "seed_sequence": [
            "base_seed", "policy_index", "rate_index", "outer_fold_id", "repetition_index",
        ],
        "candidate_policy": False,
    },
}
EXPECTED_CALL_RATES = [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0]
EXPECTED_GATE = {
    "maximum_actual_qwen_call_rate": 0.2, "minimum_six_label_macro_f1_gain": 0.01,
    "minimum_five_label_macro_f1_gain": -0.005, "maximum_hamming_loss_increase": 1e-12,
    "minimum_one_non_surprise_label_f1_gain": 0.005,
    "candidate_tie_order": [
        "highest_six_label_macro_f1", "lowest_hamming_loss", "lower_actual_call_rate",
        "lower_target_call_rate",
    ],
    "primary_policy": "logistic_router", "primary_nominal_call_rate": 0.15,
    "replication_pass_rule": "primary_policy_only",
    "point_estimate_determines_development_gate": True,
    "bootstrap_interval_determines_stability_claim": True,
}
EXPECTED_RISK_COVERAGE = {
    "methods": ["mean_entropy", "max_entropy", "margin"],
    "coverages": [1.0, 0.95, 0.9, 0.8, 0.7, 0.6],
    "mean_entropy": "mean_binary_entropy_of_final_selected_family_probability",
    "max_entropy": "max_binary_entropy_of_final_selected_family_probability",
    "margin": "negative_minimum_absolute_distance_to_final_selected_family_nested_threshold",
    "acceptance_count_rule": "floor_coverage_times_fold_rows_plus_0_5",
    "acceptance_tie_break": "stable_source_order", "diagnostic_only": True,
}
EXPECTED_BOOTSTRAP = {
    "unit": "duplicate_component", "repetitions": 2000, "seed": 20260817,
    "interval": "percentile_95",
    "selected_points": "one_frozen_candidate_per_deployable_policy",
    "selection_warning": (
        "No correction for operating-point or policy selection; train-OOF development evidence only."
    ),
}


def _typed_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _typed_number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(float(value))


def _typed_equal(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            _typed_equal(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _typed_equal(left, right) for left, right in zip(actual, expected)
        )
    if isinstance(expected, float):
        return math.isfinite(actual) and actual == expected
    return actual == expected


def _same_typed_dict(actual: Any, expected: dict[str, Any]) -> bool:
    return _typed_equal(actual, expected)


def _runtime_resources_exact(value: Any, *, wall_limit: float, memory_limit: float) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "wall_seconds", "peak_process_rss_gb", "api_cost_usd", "gpu_cost_usd",
        "model_forward_runs",
    }:
        return False
    return (
        _typed_number(value["wall_seconds"])
        and 0 <= float(value["wall_seconds"]) <= wall_limit
        and _typed_number(value["peak_process_rss_gb"])
        and 0 <= float(value["peak_process_rss_gb"]) <= memory_limit
        and type(value["api_cost_usd"]) is int and value["api_cost_usd"] == 0
        and type(value["gpu_cost_usd"]) is int and value["gpu_cost_usd"] == 0
        and type(value["model_forward_runs"]) is int and value["model_forward_runs"] == 0
    )


def _peak_rss_gb() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / 1e9 if platform.system() == "Darwin" else value * 1024 / 1e9


def _validate_process_runtime() -> None:
    if os.path.realpath(sys.executable) != os.path.realpath(EXPECTED_RUNTIME["python_executable"]):
        raise PermissionError("Formal verifier is not using the frozen Python environment")
    observed = {
        "python_version": platform.python_version(),
        "numpy_version": importlib.metadata.version("numpy"),
        "scikit_learn_version": importlib.metadata.version("scikit-learn"),
        "scipy_version": importlib.metadata.version("scipy"),
        "matplotlib_version": importlib.metadata.version("matplotlib"),
    }
    if not _typed_equal(observed, {key: EXPECTED_RUNTIME[key] for key in observed}):
        raise PermissionError(f"Formal verifier dependency version drift: {observed}")


def _stat_signature(value: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        value.st_dev, value.st_ino, value.st_mode, value.st_nlink, value.st_size,
        value.st_mtime_ns, value.st_ctime_ns,
    )


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))


def _expected_outputs() -> dict[str, str]:
    base = _relative(SCRIPT_DIR)
    public_namespace = f"{base}/runs/{RUN_ID}"
    private_namespace = f"{base}/private/{RUN_ID}"
    return {
        "public_namespace": public_namespace,
        "public_attempt_dir": f"{public_namespace}/{ATTEMPT_ID}",
        "private_namespace": private_namespace,
        "private_attempt_dir": f"{private_namespace}/{ATTEMPT_ID}",
        "selection_record": f"{public_namespace}/selected-attempt.json",
    }


def _assert_no_symlink_components(path: Path) -> None:
    absolute = Path(os.path.abspath(os.fspath(path)))
    anchor = Path(absolute.anchor)
    current = anchor
    for part in absolute.parts[1:]:
        current = current / part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            raise
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"Path traverses a symbolic link: {path}")


def _secure_read(path: Path, expected_mode: int | None = None) -> tuple[bytes, os.stat_result]:
    lexical = Path(os.path.abspath(os.fspath(path)))
    _assert_no_symlink_components(lexical)
    before = os.lstat(lexical)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError(f"Expected one-link regular file: {lexical}")
    if expected_mode is not None and stat.S_IMODE(before.st_mode) != expected_mode:
        raise PermissionError(
            f"Unexpected mode for {lexical}: {oct(stat.S_IMODE(before.st_mode))}"
        )
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("O_NOFOLLOW is required for governed artifact reads")
    flags = os.O_RDONLY | os.O_NOFOLLOW
    descriptor = os.open(lexical, flags)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise ValueError(f"File identity changed before open: {lexical}")
        if expected_mode is not None and stat.S_IMODE(opened.st_mode) != expected_mode:
            raise PermissionError(f"File mode changed before open: {lexical}")
        if _stat_signature(opened) != _stat_signature(before):
            raise ValueError(f"File metadata changed before open: {lexical}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        payload = b"".join(chunks)
        if len(payload) != opened.st_size:
            raise ValueError(f"Short read: {lexical}")
    finally:
        os.close(descriptor)
    after = os.lstat(lexical)
    if not stat.S_ISREG(after.st_mode) or after.st_nlink != 1:
        raise ValueError(f"File type/link count changed during secure read: {lexical}")
    if expected_mode is not None and stat.S_IMODE(after.st_mode) != expected_mode:
        raise PermissionError(f"File mode changed during secure read: {lexical}")
    if _stat_signature(after) != _stat_signature(opened):
        raise ValueError(f"File changed during secure read: {lexical}")
    return payload, after


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _record_for(path: Path, expected_mode: int | None = None) -> dict[str, Any]:
    payload, metadata = _secure_read(path, expected_mode)
    return {"path": _relative(path), "bytes": metadata.st_size, "sha256": _sha256(payload)}


def _require_record(record: Any, expected_mode: int) -> tuple[Path, bytes]:
    if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
        raise ValueError("Artifact record must have exact path/bytes/sha256 keys")
    relative = Path(str(record["path"]))
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("Artifact record path must be project-relative")
    path = PROJECT_ROOT / relative
    payload, metadata = _secure_read(path, expected_mode)
    if not _typed_int(record["bytes"]) or record["bytes"] != metadata.st_size:
        raise ValueError(f"Artifact byte count drift: {relative}")
    if record["sha256"] != _sha256(payload):
        raise ValueError(f"Artifact hash drift: {relative}")
    return path, payload


def _json_record(record: Any, expected_mode: int = 0o644) -> tuple[Path, dict[str, Any]]:
    path, payload = _require_record(record, expected_mode)
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return path, value


def _require_config_path(path: Path) -> tuple[Path, bytes]:
    lexical = Path(os.path.abspath(os.fspath(path)))
    if lexical.parent != CONFIGS_DIR.resolve() or lexical.name != FORMAL_CONFIG_NAME:
        raise ValueError("v3 config must be the canonical seed-44 configs direct child")
    return lexical, _secure_read(lexical, 0o644)[0]


def _identity(payload: dict[str, Any], *, parent: bool = False) -> bool:
    required = (
        payload.get("experiment_id") == PREFLIGHT_EXPERIMENT_ID
        and payload.get("run_id") == RUN_ID
        and payload.get("attempt_id") == ATTEMPT_ID
        and payload.get("model_seed") == MODEL_SEED
        and payload.get("seed_contract") == SEED_CONTRACT
        and payload.get("rq_id") == RQ_ID
    )
    return required and (
        not parent
        or payload.get("replication_parent_experiment_id") == PREFLIGHT_PARENT_EXPERIMENT_ID
    )


def _checks_passed(
    payload: dict[str, Any], expected_names: tuple[str, ...], *, has_check_count: bool
) -> None:
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("Preflight checks must be a non-empty list")
    names: list[str] = []
    for row in checks:
        if not isinstance(row, dict) or set(row) != {"name", "passed", "detail"}:
            raise ValueError("Preflight check row schema drift")
        if not isinstance(row["name"], str) or not row["name"] or row["passed"] is not True:
            raise ValueError("Preflight contains a failed or unnamed check")
        names.append(row["name"])
    if tuple(names) != expected_names or len(names) != len(set(names)):
        raise ValueError("Preflight ordered check-name inventory drift")
    if (
        not _typed_int(payload.get("passed_count"))
        or not _typed_int(payload.get("failed_count"))
        or payload["passed_count"] != len(checks)
        or payload["failed_count"] != 0
    ):
        raise ValueError("Preflight check counts drift")
    if has_check_count and (
        not _typed_int(payload.get("check_count"))
        or payload["check_count"] != len(expected_names)
    ):
        raise ValueError("Preflight check_count drift")


def _claims_are_false(payload: dict[str, Any]) -> None:
    claims = payload.get("execution_claims")
    if not isinstance(claims, dict) or set(claims) != EXECUTION_CLAIMS:
        raise ValueError("No-result execution-claim inventory drift")
    if any(value is not False for value in claims.values()):
        raise PermissionError("No-result preflight made a formal execution claim")


def _public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            if key in PUBLIC_SENSITIVE_KEYS:
                violations.append(child_path)
            violations.extend(_public_sensitive_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(_public_sensitive_paths(child, f"{prefix}[{index}]"))
    return violations


def _validate_upstream_identity(name: str, payload: dict[str, Any], paired: dict[str, Any]) -> None:
    if name.startswith("oof_"):
        if payload.get("experiment_id") != FORMAL_EXPERIMENT_ID:
            raise ValueError(f"{name} experiment identity drift")
    else:
        if (
            payload.get("experiment_id") != "EXP-059"
            or payload.get("replication_parent_experiment_id") != FORMAL_EXPERIMENT_ID
        ):
            raise ValueError(f"{name} experiment identity drift")
    for key, expected in (
        ("run_id", RUN_ID), ("attempt_id", ATTEMPT_ID), ("model_seed", MODEL_SEED)
    ):
        if payload.get(key) != expected:
            raise ValueError(f"{name} {key} drift")
    if payload.get("seed_contract") != SEED_CONTRACT:
        raise ValueError(f"{name} seed_contract drift")
    if name.endswith("verification"):
        if (
            payload.get("status") != "Passed"
            or not _typed_int(payload.get("failed_count"))
            or payload.get("failed_count") != 0
        ):
            raise ValueError(f"{name} is not Passed")
    elif name.endswith("completion"):
        if payload.get("status") != "Complete":
            raise ValueError(f"{name} is not Complete")
    elif name == "exp059_run" and payload.get("status") != "CompletedAwaitingVerification":
        raise ValueError("EXP-059 run status drift")
    if name == "oof_verification":
        if payload.get("verified_artifacts", {}).get("paired_oof_private") != paired:
            raise ValueError("OOF verification no longer binds the paired OOF")
    if name == "exp059_calibration_parameters":
        if not _typed_equal(
            payload.get("router_replication_calibration"), REPLICATION_CALIBRATION
        ):
            raise ValueError("EXP-059 router replication calibration drift")


def _validate_governance_and_science(
    formal: dict[str, Any], preflight: dict[str, Any]
) -> None:
    if formal.get("registered_at") != "2026-08-24" or preflight.get("registered_at") != "2026-08-24":
        raise ValueError("Seed-44 registration date drift")
    shared_expected = {
        "provenance": EXPECTED_PROVENANCE,
        "path_bases": EXPECTED_PATH_BASES,
        "runtime": EXPECTED_RUNTIME,
        "data": EXPECTED_DATA,
        "cross_fitting": EXPECTED_CROSS_FITTING,
        "thresholds": EXPECTED_THRESHOLDS,
        "target_contract": EXPECTED_TARGET_CONTRACT,
        "feature_contract": EXPECTED_FEATURE_CONTRACT,
        "router": EXPECTED_ROUTER,
        "call_rates": EXPECTED_CALL_RATES,
        "gate": EXPECTED_GATE,
        "risk_coverage": EXPECTED_RISK_COVERAGE,
        "bootstrap": EXPECTED_BOOTSTRAP,
    }
    for name, expected in shared_expected.items():
        if not _typed_equal(preflight.get(name), expected):
            raise ValueError(f"Preflight exact governance/science drift: {name}")
        if not _typed_equal(formal.get(name), expected):
            raise ValueError(f"Formal exact governance/science drift: {name}")
    if not _typed_equal(preflight.get("artifact_contract"), PREFLIGHT_ARTIFACT_CONTRACT):
        raise ValueError("Preflight artifact governance drift")
    if not _typed_equal(formal.get("artifact_contract"), FORMAL_ARTIFACT_CONTRACT):
        raise ValueError("Formal artifact governance drift")
    if not _typed_equal(preflight.get("resources"), PREFLIGHT_RESOURCE_CONTRACT):
        raise ValueError("Preflight resource governance drift")
    if not _typed_equal(formal.get("resources"), FORMAL_RESOURCE_CONTRACT):
        raise ValueError("Formal resource governance drift")


def _validate_preflight(formal: dict[str, Any]) -> None:
    outputs = _expected_outputs()
    preflight_dir = PROJECT_ROOT / outputs["public_attempt_dir"] / "router-preflight"
    expected_verification = preflight_dir / "verification.json"
    record = formal["prerequisites"]["exp060_preflight_verification"]
    verification_path, verification = _json_record(record)
    if verification_path != expected_verification:
        raise ValueError("Preflight verification path is not canonical")
    if set(verification) != PREFLIGHT_VERIFICATION_KEYS:
        raise ValueError("Preflight verification top-level schema drift")
    if (
        verification.get("schema_version") != PREFLIGHT_VERIFICATION_SCHEMA
        or not _identity(verification, parent=True)
        or verification.get("scope") != "preflight"
        or verification.get("status") != "Passed"
        or verification.get("independent") is not True
        or verification.get("runner_imported") is not False
        or verification.get("claim_boundary")
        != "Verified seed-44 no-result router preflight only; formal routing remains separately authorized."
    ):
        raise ValueError("Preflight verification identity/status drift")
    _checks_passed(
        verification, PREFLIGHT_VERIFICATION_CHECK_NAMES, has_check_count=False
    )
    _claims_are_false(verification)
    resources = verification.get("resources")
    if not _runtime_resources_exact(resources, wall_limit=300, memory_limit=2.0):
        raise ValueError("Preflight verification resource budget exceeded")

    artifacts = verification.get("verified_artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != VERIFIED_ARTIFACT_KEYS:
        raise ValueError("Preflight verified-artifact inventory drift")
    preflight_config_path, preflight = _json_record(artifacts["config"])
    run_path, run = _json_record(artifacts["run"])
    contract_path, contract = _json_record(artifacts["contract"])
    paired_path, _ = _require_record(artifacts["input"], 0o600)
    if (
        preflight_config_path.parent != CONFIGS_DIR.resolve()
        or preflight_config_path.name
        != "exp-062-seed-44-router-replication-router-preflight-attempt-1.json"
        or run_path != preflight_dir / "run.json"
        or contract_path != preflight_dir / "preflight-contract.json"
        or paired_path != PROJECT_ROOT / formal["input"]["paired_oof"]["path"]
        or artifacts["input"] != formal["input"]["paired_oof"]
    ):
        raise ValueError("Preflight canonical artifact binding drift")

    if set(preflight) != PREFLIGHT_TOP_KEYS:
        raise ValueError("Preflight config top-level schema drift")
    if (
        preflight.get("schema_version") != PREFLIGHT_CONFIG_SCHEMA
        or not _identity(preflight, parent=True)
        or preflight.get("stage") != PREFLIGHT_STAGE
        or preflight.get("outputs") != outputs
        or set(preflight.get("input", {})) != {"paired_oof"}
        or preflight["input"]["paired_oof"] != formal["input"]["paired_oof"]
        or set(preflight.get("prerequisites", {})) != PREFLIGHT_UPSTREAM_KEYS
        or set(preflight.get("implementation", {})) != PREFLIGHT_IMPLEMENTATION_KEYS
        or preflight.get("claim_boundary") != PREFLIGHT_CLAIM_BOUNDARY
        or preflight.get("tier") != "Major infrastructure preflight"
    ):
        raise ValueError("Preflight config contract drift")
    _validate_governance_and_science(formal, preflight)
    authorization = preflight.get("authorization")
    if not isinstance(authorization, dict) or set(authorization) != {
        "basis", "model_seed", "no_result_preflight", "formal_router_training",
        "formal_result_computation", "validation_access", "test_access",
        "model_loading_or_forward", "raw_text_access",
    }:
        raise ValueError("Preflight authorization inventory drift")
    if (
        not _typed_int(authorization.get("model_seed"))
        or authorization["model_seed"] != MODEL_SEED
        or authorization["no_result_preflight"] is not True
        or any(
            authorization[key] is not False
            for key in (
                "formal_router_training", "formal_result_computation", "validation_access",
                "test_access", "model_loading_or_forward", "raw_text_access",
            )
        )
    ):
        raise PermissionError("Preflight authorization drift")
    expected_preflight_resources = PREFLIGHT_RESOURCE_CONTRACT
    if not _same_typed_dict(preflight.get("resources"), expected_preflight_resources):
        raise ValueError("Preflight resource contract drift")
    expected_preflight_paths = {
        "protocol": PROTOCOL_PATH,
        "preflight_runner": SCRIPT_DIR / "run_exp060_router_preflight.py",
        "preflight_verifier": SCRIPT_DIR / "verify_exp060_router_preflight.py",
        "preflight_tests": SCRIPT_DIR / "tests/test_exp060_router_preflight.py",
        "runner": BASE_RUNNER_PATH,
        "verifier": BASE_VERIFIER_PATH,
        "tests": BASE_TESTS_PATH,
        "runner_launcher": RUNNER_LAUNCHER_PATH,
        "verifier_launcher": Path(__file__).resolve(),
        "launcher_tests": LAUNCHER_TESTS_PATH,
    }
    for name, expected_path in expected_preflight_paths.items():
        live_path, _ = _require_record(preflight["implementation"][name], 0o644)
        if live_path != expected_path.resolve():
            raise ValueError(f"Preflight implementation path drift: {name}")

    if set(run) != PREFLIGHT_RUN_KEYS:
        raise ValueError("Preflight run top-level schema drift")
    if (
        run.get("schema_version") != PREFLIGHT_RUN_SCHEMA
        or not _identity(run, parent=True)
        or run.get("stage") != PREFLIGHT_STAGE
        or run.get("tier") != "Major infrastructure preflight"
        or run.get("status") != "CompletedAwaitingVerification"
        or run.get("config") != artifacts["config"]
        or run.get("contract") != artifacts["contract"]
        or run.get("input") != artifacts["input"]
        or run.get("upstreams") != artifacts["upstreams"]
        or run.get("claim_boundary") != PREFLIGHT_CLAIM_BOUNDARY
    ):
        raise ValueError("Preflight run binding drift")
    _checks_passed(run, PREFLIGHT_RUN_CHECK_NAMES, has_check_count=True)
    _claims_are_false(run)
    if not _runtime_resources_exact(
        run.get("resources"), wall_limit=300, memory_limit=2.0
    ):
        raise ValueError("Preflight run resource contract drift")

    if set(contract) != PREFLIGHT_CONTRACT_KEYS:
        raise ValueError("Preflight contract top-level schema drift")
    if (
        contract.get("schema_version") != PREFLIGHT_CONTRACT_SCHEMA
        or not _identity(contract, parent=True)
        or contract.get("stage") != PREFLIGHT_STAGE
        or contract.get("result_bearing") is not False
        or contract.get("data_scope")
        != "DATA-SO-TASK-V1 train-OOF header and frozen public records only"
        or not _typed_equal(
            contract.get("ordered_model_features"), EXPECTED_FEATURE_CONTRACT["ordered_features"]
        )
        or not _typed_equal(
            contract.get("prohibited_runtime_feature_classes"),
            [
                "m3_", "gold", "oracle", "sample_id", "component_id", "fold_id",
                "raw_text", "validation", "test",
            ],
        )
        or not _typed_equal(
            contract.get("router_replication_calibration"), REPLICATION_CALIBRATION
        )
        or tuple(contract.get("policies", ())) != POLICIES
        or tuple(contract.get("deployable_policy_order", ())) != DEPLOYABLE_POLICIES
        or type(contract.get("feature_count")) is not int
        or contract.get("feature_count") != 14
        or contract.get("nested_cross_fitting_required") is not True
        or any(
            contract.get(key) is not False
            for key in (
                "formal_router_training_authorized", "formal_result_computation_authorized",
                "validation_access", "test_access", "raw_text_access",
                "model_loading_or_forward",
            )
        )
        or not _same_typed_dict(contract.get("resource_contract"), expected_preflight_resources)
        or contract.get("claim_boundary") != PREFLIGHT_CLAIM_BOUNDARY
    ):
        raise ValueError("Preflight no-result scientific contract drift")
    expected_schema_rows = [
        {"array_name": name, **details}
        for name, details in sorted(EXPECTED_INPUT_SCHEMA.items())
    ]
    if not _typed_equal(contract.get("input_schema"), expected_schema_rows):
        raise ValueError("Preflight exact 11-array header schema drift")
    for name, public_payload in (
        ("config", preflight), ("run", run), ("contract", contract),
        ("verification", verification),
    ):
        violations = _public_sensitive_paths(public_payload)
        if violations:
            raise ValueError(f"Preflight public privacy drift in {name}: {violations}")

    upstreams = artifacts.get("upstreams")
    if (
        not isinstance(upstreams, dict)
        or set(upstreams) != PREFLIGHT_UPSTREAM_KEYS
        or upstreams != preflight["prerequisites"]
        or upstreams != run["upstreams"]
    ):
        raise ValueError("Preflight upstream inventory/binding drift")
    expected_upstream_paths = {
        "oof_verification": PROJECT_ROOT / outputs["public_attempt_dir"] / "verification.json",
        "oof_completion": PROJECT_ROOT / outputs["public_attempt_dir"] / "oof-complete.json",
        "exp059_run": PROJECT_ROOT / outputs["public_attempt_dir"] / "calibration/run.json",
        "exp059_verification": PROJECT_ROOT / outputs["public_attempt_dir"] / "calibration/verification.json",
        "exp059_calibration_parameters": PROJECT_ROOT / outputs["public_attempt_dir"] / "calibration/calibration-parameters.json",
        "exp059_calibration_completion": PROJECT_ROOT / outputs["public_attempt_dir"] / "calibration-complete.json",
    }
    for name, upstream_record in upstreams.items():
        upstream_path, payload = _json_record(upstream_record)
        if upstream_path != expected_upstream_paths[name]:
            raise ValueError(f"Preflight upstream path drift: {name}")
        _validate_upstream_identity(name, payload, formal["input"]["paired_oof"])
    for name in BASE_PREREQUISITE_KEYS:
        if formal["prerequisites"][name] != upstreams[name]:
            raise ValueError(f"Formal/preflight prerequisite drift: {name}")

    source_artifacts = run.get("source_artifacts")
    frozen_sources = artifacts.get("frozen_sources")
    expected_source_keys = {"config", *PREFLIGHT_IMPLEMENTATION_KEYS}
    if (
        not isinstance(source_artifacts, dict)
        or not isinstance(frozen_sources, dict)
        or set(source_artifacts) != expected_source_keys
        or set(frozen_sources) != expected_source_keys
        or source_artifacts != frozen_sources
    ):
        raise ValueError("Preflight frozen-source inventory drift")
    for name, frozen_record in frozen_sources.items():
        frozen_path, _ = _require_record(frozen_record, 0o644)
        if frozen_path.parent != preflight_dir / "frozen-sources":
            raise ValueError(f"Preflight frozen source path drift: {name}")
        if name == "config":
            canonical_payload = _secure_read(preflight_config_path, 0o644)[0]
            if _secure_read(frozen_path, 0o644)[0] != canonical_payload:
                raise ValueError("Preflight frozen config bytes drift")
        else:
            live_record = preflight["implementation"][name]
            live_path, live_payload = _require_record(live_record, 0o644)
            frozen_payload = _secure_read(frozen_path, 0o644)[0]
            if live_payload != frozen_payload or live_path.name != frozen_path.name:
                raise ValueError(f"Preflight frozen source bytes drift: {name}")

    formal_sources = artifacts.get("formal_sources")
    if not isinstance(formal_sources, dict) or set(formal_sources) != FORMAL_IMPLEMENTATION_KEYS:
        raise ValueError("Preflight formal-source inventory drift")
    for name in FORMAL_IMPLEMENTATION_KEYS:
        if formal_sources[name] != frozen_sources[name]:
            raise ValueError(f"Preflight formal-source/frozen-source drift: {name}")
        if (
            formal_sources[name]["bytes"] != formal["implementation"][name]["bytes"]
            or formal_sources[name]["sha256"] != formal["implementation"][name]["sha256"]
        ):
            raise ValueError(f"Preflight/formal implementation drift: {name}")
    preflight_metadata = os.lstat(preflight_dir)
    frozen_metadata = os.lstat(preflight_dir / "frozen-sources")
    if (
        not stat.S_ISDIR(preflight_metadata.st_mode)
        or stat.S_IMODE(preflight_metadata.st_mode) != 0o755
        or not stat.S_ISDIR(frozen_metadata.st_mode)
        or stat.S_IMODE(frozen_metadata.st_mode) != 0o755
        or {entry.name for entry in os.scandir(preflight_dir)}
        != {
            "frozen-sources", "preflight-contract.json", "run.json", "verification.json",
            "VERIFICATION-SUMMARY.md",
        }
    ):
        raise PermissionError("Preflight public tree manifest/mode drift")
    _secure_read(preflight_dir / "VERIFICATION-SUMMARY.md", 0o644)


def validate_launch_contract(config_path: Path) -> tuple[Path, dict[str, Any]]:
    path, payload = _require_config_path(config_path)
    config = json.loads(payload.decode("utf-8"))
    if not isinstance(config, dict) or set(config) != FORMAL_TOP_KEYS:
        raise ValueError("Formal config-v3 top-level schema drift")
    violations = _public_sensitive_paths(config)
    if violations:
        raise ValueError(f"Formal config public privacy drift: {violations}")
    if (
        config.get("schema_version") != FORMAL_CONFIG_SCHEMA
        or config.get("experiment_id") != FORMAL_EXPERIMENT_ID
        or config.get("run_id") != RUN_ID
        or config.get("attempt_id") != ATTEMPT_ID
        or config.get("seed_contract") != SEED_CONTRACT
        or config.get("rq_id") != RQ_ID
        or config.get("tier") != "Major system experiment"
        or config.get("stage") != FORMAL_STAGE
        or config.get("outputs") != _expected_outputs()
        or config.get("claim_boundary") != FORMAL_CLAIM_BOUNDARY
    ):
        raise ValueError("Formal config-v3 identity/path drift")
    if not _same_typed_dict(config.get("resources"), FORMAL_RESOURCE_CONTRACT):
        raise ValueError("Formal resource contract drift")
    if os.path.lexists(PROJECT_ROOT / config["outputs"]["selection_record"]):
        raise FileExistsError("A final pipeline selection already exists")
    python_executable = config.get("runtime", {}).get("python_executable")
    if not isinstance(python_executable, str) or not Path(python_executable).is_absolute():
        raise ValueError("Formal runtime Python executable must be absolute")
    config_argument = str(path.relative_to(REPO_ROOT.resolve()))
    runner_argument = str((SCRIPT_DIR / "run_exp060_router_v3.py").relative_to(REPO_ROOT.resolve()))
    verifier_argument = str((SCRIPT_DIR / "verify_exp060_router_v3.py").relative_to(REPO_ROOT.resolve()))
    expected_commands = {
        "run": [python_executable, runner_argument, "--config", config_argument, "--stage", "run"],
        "verify_final": [
            python_executable, verifier_argument, "--config", config_argument, "--scope", "final",
        ],
        "complete": [
            python_executable, runner_argument, "--config", config_argument, "--stage", "complete",
        ],
        "verify_completion": [
            python_executable, verifier_argument, "--config", config_argument, "--scope", "completion",
        ],
    }
    commands = config.get("commands")
    if (
        not isinstance(commands, dict)
        or set(commands) != set(expected_commands)
        or any(shlex.split(str(commands[name])) != expected for name, expected in expected_commands.items())
    ):
        raise ValueError("Formal v3 launcher command contract drift")
    authorization = config.get("authorization")
    if not isinstance(authorization, dict) or set(authorization) != {
        "basis", "model_seed", "formal_router_training", "formal_result_computation",
        "validation_access", "test_access", "model_loading_or_forward", "raw_text_access",
    }:
        raise ValueError("Formal authorization inventory drift")
    if (
        not _typed_int(authorization.get("model_seed"))
        or authorization["model_seed"] != MODEL_SEED
        or authorization["formal_router_training"] is not True
        or authorization["formal_result_computation"] is not True
        or any(
            authorization[key] is not False
            for key in (
                "validation_access", "test_access", "model_loading_or_forward",
                "raw_text_access",
            )
        )
    ):
        raise PermissionError("Formal authorization drift")
    if set(config.get("implementation", {})) != FORMAL_IMPLEMENTATION_KEYS:
        raise ValueError("Formal implementation inventory is not exact7")
    expected_paths = {
        "protocol": PROTOCOL_PATH,
        "runner": BASE_RUNNER_PATH,
        "verifier": BASE_VERIFIER_PATH,
        "tests": BASE_TESTS_PATH,
        "runner_launcher": RUNNER_LAUNCHER_PATH,
        "verifier_launcher": Path(__file__).resolve(),
        "launcher_tests": LAUNCHER_TESTS_PATH,
    }
    for name, expected in expected_paths.items():
        actual, _ = _require_record(config["implementation"][name], 0o644)
        if actual != expected.resolve():
            raise ValueError(f"Formal implementation path drift: {name}")
    for name, expected_hash in (
        ("runner", BASE_RUNNER_SHA256),
        ("verifier", BASE_VERIFIER_SHA256),
        ("tests", BASE_TESTS_SHA256),
    ):
        if config["implementation"][name]["sha256"] != expected_hash:
            raise ValueError(f"Frozen base hash drift: {name}")
    if set(config.get("prerequisites", {})) != FORMAL_PREREQUISITE_KEYS:
        raise ValueError("Formal prerequisite inventory is not exact5")
    outputs = _expected_outputs()
    public_attempt = PROJECT_ROOT / outputs["public_attempt_dir"]
    expected_prerequisite_paths = {
        "oof_verification": public_attempt / "verification.json",
        "exp059_run": public_attempt / "calibration/run.json",
        "exp059_verification": public_attempt / "calibration/verification.json",
        "exp059_calibration_parameters": public_attempt / "calibration/calibration-parameters.json",
        "exp060_preflight_verification": public_attempt / "router-preflight/verification.json",
    }
    for name, expected in expected_prerequisite_paths.items():
        actual, _ = _require_record(config["prerequisites"][name], 0o644)
        if actual != expected:
            raise ValueError(f"Formal prerequisite path drift: {name}")
    if set(config.get("input", {})) != {"paired_oof"}:
        raise ValueError("Formal input inventory drift")
    paired_path, _ = _require_record(config["input"]["paired_oof"], 0o600)
    expected_paired = PROJECT_ROOT / outputs["private_attempt_dir"] / "paired-oof.npz"
    if paired_path != expected_paired:
        raise ValueError("Formal paired OOF path drift")
    parent_metadata = os.lstat(paired_path.parent)
    if not stat.S_ISDIR(parent_metadata.st_mode) or stat.S_IMODE(parent_metadata.st_mode) != 0o700:
        raise PermissionError("Formal paired OOF parent must be mode 0700")
    router = config.get("router", {})
    if (
        tuple(router.get("policies", ())) != POLICIES
        or tuple(router.get("deployable_policy_order", ())) != DEPLOYABLE_POLICIES
    ):
        raise ValueError("Formal policy inventory/order drift")
    if (
        config.get("thresholds", {}).get("calibrator") != "identity_for_m1_and_m3"
        or config.get("thresholds", {}).get("probability_source")
        != "direct_sigmoid_of_raw_oof_logits"
        or config.get("data", {}).get("upstream_seed") != MODEL_SEED
        or config.get("feature_contract", {}).get("feature_count") != 14
        or config.get("cross_fitting", {}).get("nested_router_train_threshold_folds") != 3
        or config.get("cross_fitting", {}).get("outer_heldout_threshold_folds") != 4
        or config.get("gate", {}).get("primary_policy") != "logistic_router"
        or config.get("gate", {}).get("primary_nominal_call_rate") != 0.15
    ):
        raise ValueError("Formal frozen scientific contract drift")
    _validate_preflight(config)
    return path, config


def _load_base_verifier(config: dict[str, Any]) -> ModuleType:
    payload, _ = _secure_read(BASE_VERIFIER_PATH, 0o644)
    if _sha256(payload) != BASE_VERIFIER_SHA256:
        raise ValueError("Frozen base verifier hash drift before import")
    if config["implementation"]["verifier"]["sha256"] != BASE_VERIFIER_SHA256:
        raise ValueError("Config does not bind the frozen base verifier")
    module_name = "_exp060_router_base_v2_verifier"
    module = ModuleType(module_name)
    module.__file__ = str(BASE_VERIFIER_PATH)
    module.__package__ = ""
    code = compile(
        payload.decode("utf-8"), str(BASE_VERIFIER_PATH), "exec", dont_inherit=True
    )
    exec(code, module.__dict__)
    return module


def _normalize_public_tree(
    root: Path, expected_root: set[str], expected_frozen: set[str]
) -> dict[str, Any]:
    if "frozen-sources" not in expected_root:
        raise ValueError("Frozen-source directory is missing from the expected public manifest")
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("O_DIRECTORY and O_NOFOLLOW are required")

    frozen_dir = root / "frozen-sources"
    root_before = os.lstat(root)
    frozen_before = os.lstat(frozen_dir)
    if (
        stat.S_ISLNK(root_before.st_mode)
        or not stat.S_ISDIR(root_before.st_mode)
        or stat.S_ISLNK(frozen_before.st_mode)
        or not stat.S_ISDIR(frozen_before.st_mode)
    ):
        raise ValueError("Formal public roots must be real directories")
    if {entry.name for entry in os.scandir(root)} != expected_root:
        raise ValueError("Formal public root manifest drift")
    if {entry.name for entry in os.scandir(frozen_dir)} != expected_frozen:
        raise ValueError("Formal frozen-source manifest drift")

    root_file_names = sorted(expected_root - {"frozen-sources"})
    frozen_file_names = sorted(expected_frozen)
    file_paths = [root / name for name in root_file_names]
    file_paths.extend(frozen_dir / name for name in frozen_file_names)
    file_before: dict[Path, os.stat_result] = {}
    for path in file_paths:
        observed = os.lstat(path)
        if stat.S_ISLNK(observed.st_mode) or not stat.S_ISREG(observed.st_mode):
            raise ValueError(f"Expected public manifest file is not regular: {path}")
        if observed.st_nlink != 1:
            raise ValueError(f"Expected public manifest file nlink=1: {path}")
        file_before[path] = observed

    directory_records: dict[Path, tuple[int, os.stat_result, os.stat_result]] = {}
    file_records: dict[
        Path, tuple[int, os.stat_result, os.stat_result, bytes, str]
    ] = {}
    descriptors: list[int] = []
    try:
        for path, before in ((root, root_before), (frozen_dir, frozen_before)):
            descriptor = os.open(
                path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            )
            descriptors.append(descriptor)
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(opened.st_mode)
                or _stat_signature(opened) != _stat_signature(before)
            ):
                raise ValueError(f"Public directory changed before normalization: {path}")
            directory_records[path] = (descriptor, before, opened)

        for path in file_paths:
            before = file_before[path]
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            descriptors.append(descriptor)
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or _stat_signature(opened) != _stat_signature(before)
            ):
                raise ValueError(f"Public file changed before normalization: {path}")
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            payload = b"".join(chunks)
            if len(payload) != opened.st_size:
                raise OSError(f"Short public file read: {path}")
            file_records[path] = (
                descriptor, before, opened, payload, _sha256(payload)
            )

        if {entry.name for entry in os.scandir(root)} != expected_root:
            raise ValueError("Formal public root changed during pre-normalization")
        if {entry.name for entry in os.scandir(frozen_dir)} != expected_frozen:
            raise ValueError("Formal frozen tree changed during pre-normalization")
        for path, (_, before, opened) in directory_records.items():
            current = os.lstat(path)
            if (
                not stat.S_ISDIR(current.st_mode)
                or _stat_signature(current) != _stat_signature(before)
                or _stat_signature(opened) != _stat_signature(before)
            ):
                raise ValueError(f"Public directory binding drift before chmod: {path}")
        for path, (_, before, opened, payload, digest) in file_records.items():
            current = os.lstat(path)
            if (
                not stat.S_ISREG(current.st_mode)
                or current.st_nlink != 1
                or _stat_signature(current) != _stat_signature(before)
                or _stat_signature(opened) != _stat_signature(before)
                or len(payload) != before.st_size
                or _sha256(payload) != digest
            ):
                raise ValueError(f"Public file binding drift before chmod: {path}")

        for descriptor, _, _ in directory_records.values():
            os.fchmod(descriptor, 0o755)
        for descriptor, _, _, _, _ in file_records.values():
            os.fchmod(descriptor, 0o644)

        normalized: dict[str, Any] = {}
        for path, (descriptor, before, _) in directory_records.items():
            after_fd = os.fstat(descriptor)
            after_path = os.lstat(path)
            if (
                not stat.S_ISDIR(after_fd.st_mode)
                or not stat.S_ISDIR(after_path.st_mode)
                or stat.S_IMODE(after_fd.st_mode) != 0o755
                or stat.S_IMODE(after_path.st_mode) != 0o755
                or (after_fd.st_dev, after_fd.st_ino)
                != (before.st_dev, before.st_ino)
                or (after_path.st_dev, after_path.st_ino)
                != (before.st_dev, before.st_ino)
            ):
                raise PermissionError(f"Public directory post-normalization drift: {path}")
            normalized[str(path.relative_to(root)) if path != root else "."] = (
                "dir", after_fd.st_dev, after_fd.st_ino
            )

        for path, (descriptor, before, _, payload, digest) in file_records.items():
            after_fd = os.fstat(descriptor)
            after_path = os.lstat(path)
            os.lseek(descriptor, 0, os.SEEK_SET)
            after_chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                after_chunks.append(chunk)
            after_payload = b"".join(after_chunks)
            expected_identity = (
                before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns
            )
            if (
                not stat.S_ISREG(after_fd.st_mode)
                or not stat.S_ISREG(after_path.st_mode)
                or after_fd.st_nlink != 1
                or after_path.st_nlink != 1
                or stat.S_IMODE(after_fd.st_mode) != 0o644
                or stat.S_IMODE(after_path.st_mode) != 0o644
                or (
                    after_fd.st_dev, after_fd.st_ino, after_fd.st_size,
                    after_fd.st_mtime_ns,
                )
                != expected_identity
                or (
                    after_path.st_dev, after_path.st_ino, after_path.st_size,
                    after_path.st_mtime_ns,
                )
                != expected_identity
                or after_payload != payload
                or _sha256(after_payload) != digest
            ):
                raise ValueError(f"Public file post-normalization drift: {path}")
            normalized[str(path.relative_to(root))] = (
                "file", after_fd.st_dev, after_fd.st_ino, after_fd.st_size, digest
            )

        if {entry.name for entry in os.scandir(root)} != expected_root:
            raise ValueError("Formal public root manifest changed after normalization")
        if {entry.name for entry in os.scandir(frozen_dir)} != expected_frozen:
            raise ValueError("Formal frozen manifest changed after normalization")
        return normalized
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _private_snapshot(private_dir: Path) -> tuple[Any, ...]:
    metadata = os.lstat(private_dir)
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or {entry.name for entry in os.scandir(private_dir)} != {"router-oof.npz"}
    ):
        raise PermissionError("Formal private router manifest/mode drift")
    payload, file_metadata = _secure_read(private_dir / "router-oof.npz", 0o600)
    return (
        _stat_signature(metadata), _stat_signature(file_metadata), _sha256(payload)
    )


def _validate_post_state(config: dict[str, Any], scope: str) -> None:
    outputs = _expected_outputs()
    public_attempt = PROJECT_ROOT / outputs["public_attempt_dir"]
    private_attempt = PROJECT_ROOT / outputs["private_attempt_dir"]
    for path, expected_mode in ((public_attempt, 0o755), (private_attempt, 0o700)):
        metadata = os.lstat(path)
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != expected_mode
        ):
            raise PermissionError(f"Attempt parent mode/type drift: {path}")
    run_dir = public_attempt / "router"
    private_dir = private_attempt / "router"
    expected_root = set(PUBLIC_ROOT_NAMES)
    expected_root.update({"verification.json", "VERIFICATION-SUMMARY.md"})
    if scope == "completion":
        expected_root.add("router-complete.json")
    frozen_names = {"config.json", *(Path(record["path"]).name for record in config["implementation"].values())}
    if len(frozen_names) != len(config["implementation"]) + 1:
        raise ValueError("Formal frozen-source basenames are not unique")
    private_before = _private_snapshot(private_dir)
    _normalize_public_tree(run_dir, expected_root, frozen_names)
    private_after = _private_snapshot(private_dir)
    if private_before != private_after:
        raise ValueError("Private router tree changed during public normalization")


def _write_once(path: Path, payload: bytes) -> None:
    parent_metadata = os.lstat(path.parent)
    if (
        stat.S_ISLNK(parent_metadata.st_mode)
        or not stat.S_ISDIR(parent_metadata.st_mode)
        or stat.S_IMODE(parent_metadata.st_mode) != 0o755
    ):
        raise PermissionError("Verifier sidecar parent must be a real mode-0755 directory")
    if os.path.lexists(path):
        raise FileExistsError(f"Refusing to overwrite append-only verifier sidecar: {path}")
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o644,
    )
    try:
        os.fchmod(descriptor, 0o644)
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("Short verifier sidecar write")
            view = view[written:]
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o644
            or metadata.st_size != len(payload)
        ):
            raise PermissionError("Verifier sidecar FD invariant failed")
    finally:
        os.close(descriptor)
    _secure_read(path, 0o644)


def _atomic_json_once(path: Path, value: Any) -> None:
    payload = (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    _write_once(path, payload)


def _write_summary_once(path: Path, result: dict[str, Any]) -> None:
    lines = [
        f"# {result['experiment_id']} Formal Router Verification",
        "",
        f"- Status: `{result['status']}`",
        f"- Passed checks: `{result['passed_count']}`",
        f"- Failed checks: `{result['failed_count']}`",
        "- Runner imported: `false`",
        "- Input: frozen EXP-058 train-OOF only",
        "- Validation/test/model/raw-text access: `false`",
        "",
        result["claim_boundary"],
        "",
    ]
    if result["failed_count"]:
        lines.extend(["## Failed checks", ""])
        lines.extend(f"- `{row['name']}`" for row in result["checks"] if not row["passed"])
        lines.append("")
    _write_once(path, "\n".join(lines).encode("utf-8"))


def execute(config_path: Path, scope: str, *, base_module: ModuleType | None = None) -> dict[str, Any]:
    if scope not in {"final", "completion"}:
        raise ValueError("Unexpected verifier scope")
    outer_started = time.monotonic()
    canonical, prevalidated = validate_launch_contract(config_path)
    _validate_process_runtime()
    base = base_module if base_module is not None else _load_base_verifier(prevalidated)
    old_schema = base.REPLICATION_CONFIG_SCHEMA
    old_prerequisites = base.REPLICATION_REQUIRED_PREREQUISITES
    old_atomic_json = base.atomic_json
    old_write_summary = base.write_summary
    try:
        base.REPLICATION_CONFIG_SCHEMA = FORMAL_CONFIG_SCHEMA
        base.REPLICATION_REQUIRED_PREREQUISITES = set(FORMAL_PREREQUISITE_KEYS)
        base.atomic_json = _atomic_json_once
        base.write_summary = _write_summary_once
        result = base.verify(canonical) if scope == "final" else base.verify_completion(canonical)
    finally:
        base.REPLICATION_CONFIG_SCHEMA = old_schema
        base.REPLICATION_REQUIRED_PREREQUISITES = old_prerequisites
        base.atomic_json = old_atomic_json
        base.write_summary = old_write_summary
    _, postvalidated = validate_launch_contract(canonical)
    if postvalidated != prevalidated:
        raise ValueError("Formal launch contract changed during the base call")
    _validate_post_state(postvalidated, scope)
    outer_elapsed = time.monotonic() - outer_started
    outer_rss = _peak_rss_gb()
    if (
        outer_elapsed > float(FORMAL_RESOURCE_CONTRACT["verification_wall_seconds"])
        or outer_rss > float(FORMAL_RESOURCE_CONTRACT["peak_memory_gb"])
    ):
        raise RuntimeError(
            f"Outer governed verifier budget exceeded: wall={outer_elapsed}, rss={outer_rss}"
        )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--scope", choices=("final", "completion"), default="final")
    return parser.parse_args()


def main() -> None:
    if Path.cwd().resolve() != REPO_ROOT.resolve():
        raise RuntimeError(f"EXP-060 v3 must run from repository root: {REPO_ROOT}")
    args = parse_args()
    result = execute(args.config, args.scope)
    print(
        json.dumps(
            {
                "status": result["status"],
                "passed": result["passed_count"],
                "failed": result["failed_count"],
            },
            sort_keys=True,
        )
    )
    if result["status"] != "Passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
