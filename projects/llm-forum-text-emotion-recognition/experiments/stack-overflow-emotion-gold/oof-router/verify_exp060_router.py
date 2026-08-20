#!/usr/bin/env python3
"""Independently recompute and verify the formal EXP-060 router artifacts."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import stat
import struct
import tempfile
import time
from typing import Any, Iterable, Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler


EXPERIMENT_ID = "EXP-060"
RQ_ID = "RQ-S3"
LEGACY_CONFIG_SCHEMA = "exp-060-formal-config-v1"
REPLICATION_CONFIG_SCHEMA = "exp-router-replication-config-v2"
ATTEMPT_RE = re.compile(r"attempt-[1-9][0-9]*\Z")
REGISTERED_REPLICATIONS = {
    "EXP-061": (43, "exp-061-seed-43-router-replication"),
    "EXP-062": (44, "exp-062-seed-44-router-replication"),
}
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
POLICY_ORDER = (
    "m1_only",
    "m3_only",
    "m1_max_entropy",
    "m1_threshold_proximity",
    "logistic_router",
)
DEPLOYABLE_POLICIES = POLICY_ORDER[2:]
UNCERTAINTY_METHODS = ("mean_entropy", "max_entropy", "margin")
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-060-pre-qwen-router.json"
EXPECTED_SOURCE_ORDER_SHA256 = "c9e4bd1eb2bdbb33c833234754c493b8818aa6c610acaf88659ae74fa94848a3"
EXPECTED_PUBLIC_RUN_DIR = (
    "experiments/stack-overflow-emotion-gold/oof-router/runs/exp-060-pre-qwen-router"
)
EXPECTED_PRIVATE_RUN_DIR = (
    "experiments/stack-overflow-emotion-gold/oof-router/private/exp-060-pre-qwen-router"
)
EXPECTED_INPUT_PATH = (
    "experiments/stack-overflow-emotion-gold/oof-router/private/"
    "exp-058-paired-oof-production/paired-oof.npz"
)
EXPECTED_INPUT_BYTES = 307755
EXPECTED_INPUT_SHA256 = "e8d2efde7ca62b3f09519390a6305d09ba0f3ea1dfbecbe8a11dbe4ffd482bfc"
EXPECTED_PUBLIC_ARTIFACTS = {
    "feature-contract.json",
    "fold-summary.csv",
    "router-discrimination.json",
    "call-rate-performance.csv",
    "policy-comparisons.csv",
    "random-routing.csv",
    "selected-operating-point.json",
    "bootstrap.json",
    "routed-risk-coverage.csv",
    "positive-label-retention.csv",
    "call-rate-performance.png",
    "routed-risk-coverage.png",
    "REPORT.md",
    "run.json",
    "frozen-sources",
}
REPLICATION_REQUIRED_PREREQUISITES = {
    "oof_verification",
    "exp059_run",
    "exp059_verification",
    "exp059_calibration_parameters",
}
REPLICATION_INPUT_KEYS = {"paired_oof"}
REPLICATION_CALIBRATION_CONTRACT = {
    "calibrator": "identity",
    "temperature": 1.0,
    "probability_source": "direct_sigmoid_of_raw_oof_logits",
    "role": "frozen_exp060_replication_only",
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

CSV_COLUMNS = {
    "fold-summary.csv": (
        "outer_fold_index",
        "router_train_rows",
        "heldout_rows",
        "router_train_components",
        "heldout_components",
        "router_train_target_positive",
        "router_train_target_prevalence",
        "heldout_target_positive",
        "heldout_target_prevalence",
        "router_pr_auc",
        "router_roc_auc",
        "router_precision_at_0_5",
        "router_recall_at_0_5",
        "router_n_iter",
        "router_converged",
        "coefficient_l2_norm",
    ),
    "call-rate-performance.csv": (
        "policy",
        "target_call_rate",
        "actual_call_rate",
        "routed_rows",
        "qwen_calls_per_1000",
        "macro_f1",
        "five_label_macro_f1",
        "micro_f1",
        "hamming_loss",
        "subset_accuracy",
        "f1_love",
        "f1_joy",
        "f1_surprise",
        "f1_anger",
        "f1_sadness",
        "f1_fear",
    ),
    "policy-comparisons.csv": (
        "target_call_rate",
        "r4_actual_call_rate",
        "best_heuristic_policy",
        "best_heuristic_actual_call_rate",
        "r4_macro_f1",
        "best_heuristic_macro_f1",
        "macro_f1_delta",
        "r4_five_label_macro_f1",
        "best_heuristic_five_label_macro_f1",
        "five_label_macro_f1_delta",
        "r4_hamming_loss",
        "best_heuristic_hamming_loss",
        "hamming_loss_delta",
    ),
    "random-routing.csv": (
        "policy",
        "target_call_rate",
        "matched_policy_actual_call_rate",
        "random_actual_call_rate_mean",
        "random_actual_call_rate_min",
        "random_actual_call_rate_max",
        "macro_f1_mean",
        "macro_f1_p05",
        "macro_f1_p50",
        "macro_f1_p95",
        "five_label_macro_f1_mean",
        "five_label_macro_f1_p05",
        "five_label_macro_f1_p50",
        "five_label_macro_f1_p95",
        "hamming_loss_mean",
        "hamming_loss_p05",
        "hamming_loss_p50",
        "hamming_loss_p95",
    ),
    "routed-risk-coverage.csv": (
        "policy",
        "uncertainty_method",
        "target_coverage",
        "actual_coverage",
        "accepted_rows",
        "hamming_risk",
        "subset_error",
        "micro_f1",
        "macro_f1",
        "five_label_macro_f1",
    ),
    "positive-label-retention.csv": (
        "policy",
        "uncertainty_method",
        "target_coverage",
        "label",
        "positive_support",
        "retained_positive",
        "positive_retention",
    ),
}


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


def is_replication(config: dict[str, Any]) -> bool:
    return config.get("schema_version") == REPLICATION_CONFIG_SCHEMA


def experiment_id(config: dict[str, Any]) -> str:
    return str(config.get("experiment_id", EXPERIMENT_ID))


def run_id(config: dict[str, Any]) -> str:
    return str(config["run_id"]) if is_replication(config) else "exp-060-pre-qwen-router"


def attempt_id(config: dict[str, Any]) -> str | None:
    return str(config["attempt_id"]) if is_replication(config) else None


def model_seed(config: dict[str, Any]) -> int:
    if is_replication(config):
        return int(config["seed_contract"]["model_seed"])
    return int(config["data"].get("upstream_seed", 42))


def seed_contract(config: dict[str, Any]) -> dict[str, int]:
    seed = model_seed(config)
    if not is_replication(config):
        return {
            "model_seed": seed,
            "python_seed": seed,
            "numpy_seed": seed,
            "torch_seed": seed,
            "m1_batch_seed": seed,
            "m3_head_seed": seed,
            "m3_batch_seed": seed,
            "m3_lora_seed": seed + 100000,
        }
    return {key: int(value) for key, value in config["seed_contract"].items()}


def identity_matches(payload: dict[str, Any], config: dict[str, Any]) -> bool:
    return (
        payload.get("experiment_id") == experiment_id(config)
        and payload.get("run_id") == run_id(config)
        and payload.get("attempt_id") == attempt_id(config)
        and payload.get("model_seed") == model_seed(config)
    )


def resolve_project(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Project-relative path escapes project root: {value}")
    return path


def resolve_output(value: str) -> Path:
    relative = Path(str(value))
    if relative.is_absolute() or not relative.parts or any(part in ("", ".", "..") for part in relative.parts):
        raise ValueError(f"Output path is not a normalized project-relative path: {value}")
    cursor = PROJECT_ROOT
    for part in relative.parts:
        cursor = cursor / part
        if os.path.lexists(cursor) and cursor.is_symlink():
            raise ValueError(f"Output path traverses a symbolic link: {value}")
    resolved = (PROJECT_ROOT / relative).resolve()
    if not resolved.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Output path escapes project root: {value}")
    return resolved


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(resolved)


def artifact(path: Path) -> dict[str, Any]:
    return {"path": display_path(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


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
    relative = Path(str(record["path"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Frozen artifact record must be a direct project-relative path")
    lexical = PROJECT_ROOT / relative
    candidate = PROJECT_ROOT
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError("Frozen artifact record traverses a symbolic link")
    path = resolve_project(str(relative))
    if not path.is_file() or lexical.is_symlink():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Frozen artifact drift: {path}")
    return path


def require_canonical_config_path(path: Path) -> Path:
    lexical = Path(os.path.abspath(os.fspath(path)))
    configs_dir = (SCRIPT_DIR / "configs").resolve()
    if lexical.parent != configs_dir:
        raise ValueError("Router config must be a direct child of the canonical configs directory")
    relative = lexical.relative_to(PROJECT_ROOT)
    candidate = PROJECT_ROOT
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError("EXP-060 canonical config path traverses a symbolic link")
    if not lexical.is_file():
        raise FileNotFoundError(lexical)
    return lexical


def expected_replication_outputs(config: dict[str, Any]) -> dict[str, str]:
    base = display_path(SCRIPT_DIR)
    identifier = run_id(config)
    attempt = attempt_id(config)
    return {
        "public_namespace": f"{base}/runs/{identifier}",
        "public_attempt_dir": f"{base}/runs/{identifier}/{attempt}",
        "private_namespace": f"{base}/private/{identifier}",
        "private_attempt_dir": f"{base}/private/{identifier}/{attempt}",
        "selection_record": f"{base}/runs/{identifier}/selected-attempt.json",
    }


def validate_replication_identity(config: dict[str, Any]) -> None:
    identity = REGISTERED_REPLICATIONS.get(str(config.get("experiment_id")))
    if identity is None:
        raise ValueError("Router config-v2 is restricted to registered EXP-061/EXP-062")
    expected_seed, expected_run_id = identity
    if config.get("run_id") != expected_run_id:
        raise ValueError("Replication experiment/run_id identity drift")
    if not ATTEMPT_RE.fullmatch(str(config.get("attempt_id", ""))):
        raise ValueError("attempt_id must match attempt-[1-9][0-9]*")
    expected_seeds = {
        "model_seed": expected_seed,
        "python_seed": expected_seed,
        "numpy_seed": expected_seed,
        "torch_seed": expected_seed,
        "m1_batch_seed": expected_seed,
        "m3_head_seed": expected_seed,
        "m3_batch_seed": expected_seed,
        "m3_lora_seed": expected_seed + 100000,
    }
    if config.get("seed_contract") != expected_seeds:
        raise ValueError("Exact replication RNG seed contract drift")
    if int(config.get("authorization", {}).get("model_seed", -1)) != expected_seed:
        raise PermissionError("Router authorization model_seed drift")
    if int(config.get("data", {}).get("upstream_seed", -1)) != expected_seed:
        raise ValueError("Router data/model_seed binding drift")
    outputs = expected_replication_outputs(config)
    if config.get("outputs") != outputs:
        raise ValueError("Router config-v2 output paths are not canonical")
    expected_input = f"{outputs['private_attempt_dir']}/paired-oof.npz"
    if set(config.get("input", {})) != REPLICATION_INPUT_KEYS:
        raise ValueError("Router config-v2 input inventory drift")
    if config.get("input", {}).get("paired_oof", {}).get("path") != expected_input:
        raise ValueError("Router paired OOF must come from the matching private attempt")
    prerequisites = config.get("prerequisites")
    if not isinstance(prerequisites, dict) or set(prerequisites) != REPLICATION_REQUIRED_PREREQUISITES:
        raise ValueError("Router config-v2 prerequisite inventory drift")
    public_attempt = resolve_output(outputs["public_attempt_dir"])
    for name in REPLICATION_REQUIRED_PREREQUISITES:
        record_path = resolve_output(str(prerequisites[name].get("path", "")))
        if not record_path.is_relative_to(public_attempt):
            raise ValueError(f"{name} is not inside the matching public attempt")


def replication_calibration_contract_matches(payload: dict[str, Any]) -> bool:
    return payload.get("router_replication_calibration") == REPLICATION_CALIBRATION_CONTRACT


def guard_record_paths(config: dict[str, Any]) -> None:
    """Reject forbidden split/model/raw-data paths before opening any frozen record."""
    forbidden = {"validation", "test", "raw-text", "raw_text", "checkpoint", "checkpoints"}
    violation_count = 0
    for section in ("implementation", "prerequisites", "input"):
        for record in iter_records(config.get(section, {})):
            parts = {part.lower() for part in Path(str(record.get("path", ""))).parts}
            violation_count += int(bool(parts & forbidden))
    if violation_count:
        raise ValueError(f"Forbidden EXP-060 frozen-record paths: count={violation_count}")


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


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


class Checks:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, name: str, passed: bool, detail: Any = None) -> None:
        self.rows.append({"name": name, "passed": bool(passed), "detail": detail})

    @property
    def failed(self) -> list[dict[str, Any]]:
        return [row for row in self.rows if not row["passed"]]


def expected_paired_schema() -> dict[str, tuple[tuple[int, ...], str]]:
    return {
        "sample_ids": ((3360,), "<U31"),
        "component_ids": ((3360,), "<U34"),
        "fold_ids": ((3360,), "int8"),
        "gold": ((3360, 6), "uint8"),
        "m1_logits": ((3360, 6), "float32"),
        "m3_logits": ((3360, 6), "float32"),
        "character_lengths": ((3360,), "int32"),
        "m1_token_lengths": ((3360,), "int32"),
        "m3_token_lengths": ((3360,), "int32"),
        "m1_fold_run_sha256": ((3360,), "<U64"),
        "m3_fold_run_sha256": ((3360,), "<U64"),
    }


def stable_sigmoid(values: np.ndarray) -> np.ndarray:
    source = np.asarray(values, dtype=np.float64)
    result = np.empty_like(source)
    positive = source >= 0
    result[positive] = 1.0 / (1.0 + np.exp(-source[positive]))
    exponent = np.exp(source[~positive])
    result[~positive] = exponent / (1.0 + exponent)
    return result


def binary_entropy(probabilities: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(probabilities, dtype=np.float64), 1e-15, 1.0 - 1e-15)
    return -(clipped * np.log(clipped) + (1.0 - clipped) * np.log1p(-clipped))


def classification(gold: np.ndarray, prediction: np.ndarray) -> dict[str, Any]:
    labels = np.asarray(gold, dtype=np.uint8)
    predicted = np.asarray(prediction, dtype=np.uint8)
    if labels.shape != predicted.shape or labels.ndim != 2 or labels.shape[1] != 6:
        raise ValueError("Classification matrices must align as [rows, 6]")
    per_label: dict[str, Any] = {}
    f1_values: list[float] = []
    tp_total = fp_total = fn_total = 0
    for index, label in enumerate(LABEL_ORDER):
        truth = labels[:, index]
        guess = predicted[:, index]
        tp = int(np.sum((truth == 1) & (guess == 1)))
        fp = int(np.sum((truth == 0) & (guess == 1)))
        fn = int(np.sum((truth == 1) & (guess == 0)))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "support": int(np.sum(truth == 1)),
            "predicted_positive": int(np.sum(guess == 1)),
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
    subset_accuracy = float(np.mean(np.all(labels == predicted, axis=1)))
    return {
        "rows": int(labels.shape[0]),
        "macro_f1": float(np.mean(f1_values)),
        "five_label_macro_f1": float(np.mean([v for i, v in enumerate(f1_values) if i != 2])),
        "micro_f1": float(micro_f1),
        "hamming_loss": float(np.mean(labels != predicted)),
        "subset_accuracy": subset_accuracy,
        "subset_error": float(1.0 - subset_accuracy),
        "per_label": per_label,
    }


def threshold_grid(config: dict[str, Any]) -> list[float]:
    settings = config["thresholds"]
    if "grid" in settings:
        return [float(value) for value in settings["grid"]]
    start = float(settings["grid_start"])
    end = float(settings["grid_end"])
    step = float(settings["grid_step"])
    count = int(round((end - start) / step))
    return [float(round(start + index * step, 12)) for index in range(count + 1)]


def choose_threshold(
    probabilities: np.ndarray,
    gold: np.ndarray,
    grid: Sequence[float],
    tolerance: float,
) -> float:
    candidates: list[dict[str, float]] = []
    for threshold in grid:
        metrics = classification(gold, (probabilities >= threshold).astype(np.uint8))
        candidates.append(
            {
                "threshold": float(threshold),
                "macro_f1": float(metrics["macro_f1"]),
                "hamming_loss": float(metrics["hamming_loss"]),
            }
        )
    best_macro = max(row["macro_f1"] for row in candidates)
    tied = [row for row in candidates if abs(row["macro_f1"] - best_macro) <= tolerance]
    best_hamming = min(row["hamming_loss"] for row in tied)
    tied = [row for row in tied if abs(row["hamming_loss"] - best_hamming) <= tolerance]
    tied.sort(key=lambda row: (abs(row["threshold"] - 0.5), row["threshold"]))
    return float(tied[0]["threshold"])


def build_features(
    m1_probabilities: np.ndarray,
    thresholds: np.ndarray,
    character_lengths: np.ndarray,
    token_lengths: np.ndarray,
) -> np.ndarray:
    probabilities = np.asarray(m1_probabilities, dtype=np.float64)
    threshold_values = np.asarray(thresholds, dtype=np.float64)
    characters = np.asarray(character_lengths, dtype=np.float64)
    tokens = np.asarray(token_lengths, dtype=np.float64)
    rows = probabilities.shape[0]
    if probabilities.shape != (rows, 6):
        raise ValueError("M1 probabilities must have six columns")
    if threshold_values.shape != (rows,) or characters.shape != (rows,) or tokens.shape != (rows,):
        raise ValueError("Feature inputs are not row aligned")
    entropy = binary_entropy(probabilities)
    matrix = np.column_stack(
        [
            probabilities,
            np.mean(entropy, axis=1),
            np.max(entropy, axis=1),
            np.min(np.abs(probabilities - threshold_values[:, None]), axis=1),
            np.sum(probabilities >= threshold_values[:, None], axis=1),
            np.max(probabilities, axis=1),
            np.min(probabilities, axis=1),
            characters,
            tokens,
        ]
    ).astype(np.float64, copy=False)
    if matrix.shape != (rows, 14) or not np.all(np.isfinite(matrix)):
        raise ValueError("Frozen 14-column feature contract failed")
    return matrix


def build_target(m1_prediction: np.ndarray, m3_prediction: np.ndarray, gold: np.ndarray) -> np.ndarray:
    m1 = np.asarray(m1_prediction, dtype=np.uint8)
    m3 = np.asarray(m3_prediction, dtype=np.uint8)
    labels = np.asarray(gold, dtype=np.uint8)
    if m1.shape != m3.shape or m1.shape != labels.shape:
        raise ValueError("Router target inputs are not aligned")
    m1_loss = np.mean(m1 != labels, axis=1)
    m3_loss = np.mean(m3 != labels, axis=1)
    return (m3_loss < m1_loss).astype(np.uint8)


def score_cutoff(scores: np.ndarray, target_rate: float) -> float:
    values = np.asarray(scores, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("Cutoff scores must be a non-empty finite vector")
    if target_rate == 0.0:
        return math.inf
    if target_rate == 1.0:
        return -math.inf
    count = max(1, int(math.ceil(float(target_rate) * values.size)))
    return float(np.sort(values)[::-1][count - 1])


def apply_cutoff(scores: np.ndarray, cutoff: float) -> np.ndarray:
    values = np.asarray(scores, dtype=np.float64)
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("Held-out route scores must be finite")
    return (values >= cutoff).astype(np.uint8)


def binary_discrimination(target: np.ndarray, scores: np.ndarray) -> dict[str, Any]:
    labels = np.asarray(target, dtype=np.uint8)
    values = np.asarray(scores, dtype=np.float64)
    predicted = values >= 0.5
    tp = int(np.sum((labels == 1) & predicted))
    fp = int(np.sum((labels == 0) & predicted))
    fn = int(np.sum((labels == 1) & ~predicted))
    tn = int(np.sum((labels == 0) & ~predicted))
    both_classes = len(np.unique(labels)) == 2
    return {
        "rows": int(len(labels)),
        "positive_targets": int(np.sum(labels)),
        "target_prevalence": float(np.mean(labels)),
        "pr_auc": float(average_precision_score(labels, values)) if both_classes else None,
        "roc_auc": float(roc_auc_score(labels, values)) if both_classes else None,
        "precision_at_0_5": float(tp / (tp + fp)) if tp + fp else 0.0,
        "recall_at_0_5": float(tp / (tp + fn)) if tp + fn else 0.0,
        "predicted_positive": int(np.sum(predicted)),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
    }


def component_groups(component_ids: np.ndarray, indices: np.ndarray | None = None) -> list[np.ndarray]:
    selected = np.arange(len(component_ids), dtype=np.int64) if indices is None else np.asarray(indices)
    groups: dict[str, list[int]] = {}
    for index in selected.tolist():
        groups.setdefault(str(component_ids[index]), []).append(int(index))
    return [np.asarray(groups[key], dtype=np.int64) for key in sorted(groups)]


def component_random_mask(
    component_ids: np.ndarray,
    heldout_indices: np.ndarray,
    target_rows: int,
    seed_parts: Sequence[int],
) -> np.ndarray:
    """Select whole components with nearest 0/1 subset-sum; equal distances prefer fewer rows."""
    indices = np.asarray(heldout_indices, dtype=np.int64)
    local_components = np.asarray(component_ids)[indices]
    grouped: dict[str, list[int]] = {}
    for local_index, component in enumerate(local_components.tolist()):
        grouped.setdefault(str(component), []).append(local_index)
    keys = sorted(grouped)
    rng = np.random.default_rng(np.random.SeedSequence([int(value) for value in seed_parts]))
    ordered_keys = [keys[int(index)] for index in rng.permutation(len(keys))]
    sizes = [len(grouped[key]) for key in ordered_keys]
    row_count = len(indices)
    if target_rows <= 0:
        return np.zeros(len(component_ids), dtype=np.uint8)
    if target_rows >= row_count:
        result = np.zeros(len(component_ids), dtype=np.uint8)
        result[indices] = 1
        return result

    reachable = 1
    history: list[int] = []
    used_sizes: list[int] = []
    for size in sizes:
        history.append(reachable)
        used_sizes.append(size)
        reachable |= reachable << size
        if (reachable >> int(target_rows)) & 1:
            break
    chosen_count: int | None = None
    for delta in range(row_count + 1):
        lower = int(target_rows) - delta
        upper = int(target_rows) + delta
        if lower >= 0 and ((reachable >> lower) & 1):
            chosen_count = lower
            break
        if upper <= row_count and ((reachable >> upper) & 1):
            chosen_count = upper
            break
    if chosen_count is None:
        raise RuntimeError("Component subset-sum failed")
    selected_positions: set[int] = set()
    remaining = chosen_count
    for position in range(len(used_sizes) - 1, -1, -1):
        before = history[position]
        if (before >> remaining) & 1:
            continue
        size = used_sizes[position]
        if remaining < size or not ((before >> (remaining - size)) & 1):
            raise RuntimeError("Component subset-sum reconstruction failed")
        selected_positions.add(position)
        remaining -= size
    if remaining != 0:
        raise RuntimeError("Component subset-sum did not reach the selected count")
    result = np.zeros(len(component_ids), dtype=np.uint8)
    selected_keys = {ordered_keys[position] for position in selected_positions}
    local_mask = np.asarray(
        [str(value) in selected_keys for value in local_components.tolist()], dtype=np.uint8
    )
    result[indices] = local_mask
    return result


def routed_prediction(mask: np.ndarray, m1_prediction: np.ndarray, m3_prediction: np.ndarray) -> np.ndarray:
    selected = np.asarray(mask, dtype=bool)
    return np.where(selected[:, None], m3_prediction, m1_prediction).astype(np.uint8)


def call_rate_row(
    policy: str,
    target_call_rate: float,
    route_mask: np.ndarray,
    gold: np.ndarray,
    prediction: np.ndarray,
) -> dict[str, Any]:
    metrics = classification(gold, prediction)
    calls = int(np.sum(route_mask))
    return {
        "policy": policy,
        "target_call_rate": float(target_call_rate),
        "actual_call_rate": float(calls / len(route_mask)),
        "routed_rows": calls,
        "qwen_calls_per_1000": float(1000.0 * calls / len(route_mask)),
        "macro_f1": metrics["macro_f1"],
        "five_label_macro_f1": metrics["five_label_macro_f1"],
        "micro_f1": metrics["micro_f1"],
        "hamming_loss": metrics["hamming_loss"],
        "subset_accuracy": metrics["subset_accuracy"],
        **{f"f1_{label}": metrics["per_label"][label]["f1"] for label in LABEL_ORDER},
    }


def candidate_sort_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        -float(row["macro_f1"]),
        float(row["hamming_loss"]),
        float(row["actual_call_rate"]),
        float(row["target_call_rate"]),
    )


def build_expected_state(data: dict[str, np.ndarray], config: dict[str, Any]) -> dict[str, Any]:
    gold = np.asarray(data["gold"], dtype=np.uint8)
    folds = np.asarray(data["fold_ids"], dtype=np.int8)
    components = np.asarray(data["component_ids"])
    m1_probabilities = stable_sigmoid(data["m1_logits"])
    m3_probabilities = stable_sigmoid(data["m3_logits"])
    grid = threshold_grid(config)
    tolerance = float(config["thresholds"]["numeric_tolerance"])
    outer_folds = [int(value) for value in config["cross_fitting"]["outer_fold_ids"]]
    call_rates = [float(value) for value in config["call_rates"]]
    rows = len(gold)

    features = np.empty((rows, len(FEATURE_NAMES)), dtype=np.float64)
    router_targets = np.empty(rows, dtype=np.uint8)
    nested_m1 = np.empty((5, 5), dtype=np.float64)
    nested_m3 = np.empty((5, 5), dtype=np.float64)
    m1_thresholds = np.empty(rows, dtype=np.float64)
    m3_thresholds = np.empty(rows, dtype=np.float64)
    m1_predictions = np.empty((rows, 6), dtype=np.uint8)
    m3_predictions = np.empty((rows, 6), dtype=np.uint8)
    route_scores = np.empty((len(DEPLOYABLE_POLICIES), rows), dtype=np.float64)
    route_masks = np.zeros(
        (len(DEPLOYABLE_POLICIES), len(call_rates), rows), dtype=np.uint8
    )
    score_cutoffs = np.empty(
        (len(DEPLOYABLE_POLICIES), len(call_rates), len(outer_folds)), dtype=np.float64
    )
    scaler_mean = np.empty((5, 14), dtype=np.float64)
    scaler_scale = np.empty((5, 14), dtype=np.float64)
    router_coef = np.empty((5, 14), dtype=np.float64)
    router_intercept = np.empty(5, dtype=np.float64)
    router_n_iter = np.empty(5, dtype=np.int32)
    fold_rows: list[dict[str, Any]] = []
    fold_states: dict[int, dict[str, Any]] = {}

    router_settings = config["router"]["logistic_regression"]
    for outer_position, outer_fold in enumerate(outer_folds):
        heldout_indices = np.flatnonzero(folds == outer_fold)
        train_indices = np.flatnonzero(folds != outer_fold)
        nested_feature_parts: list[np.ndarray] = []
        nested_target_parts: list[np.ndarray] = []

        for inner_fold in outer_folds:
            if inner_fold == outer_fold:
                continue
            threshold_fit = (folds != outer_fold) & (folds != inner_fold)
            inner_indices = np.flatnonzero(folds == inner_fold)
            m1_threshold = choose_threshold(
                m1_probabilities[threshold_fit], gold[threshold_fit], grid, tolerance
            )
            m3_threshold = choose_threshold(
                m3_probabilities[threshold_fit], gold[threshold_fit], grid, tolerance
            )
            nested_m1[outer_fold, inner_fold] = m1_threshold
            nested_m3[outer_fold, inner_fold] = m3_threshold
            inner_m1_prediction = (
                m1_probabilities[inner_indices] >= m1_threshold
            ).astype(np.uint8)
            inner_m3_prediction = (
                m3_probabilities[inner_indices] >= m3_threshold
            ).astype(np.uint8)
            inner_features = build_features(
                m1_probabilities[inner_indices],
                np.full(len(inner_indices), m1_threshold, dtype=np.float64),
                data["character_lengths"][inner_indices],
                data["m1_token_lengths"][inner_indices],
            )
            inner_target = build_target(
                inner_m1_prediction, inner_m3_prediction, gold[inner_indices]
            )
            nested_feature_parts.append(inner_features)
            nested_target_parts.append(inner_target)

        nested_train_features = np.concatenate(nested_feature_parts, axis=0)
        nested_train_target = np.concatenate(nested_target_parts, axis=0)

        if len(np.unique(nested_train_target)) != 2:
            raise ValueError(f"Outer fold {outer_fold} router-training target has one class")

        outer_train = folds != outer_fold
        heldout_m1_threshold = choose_threshold(
            m1_probabilities[outer_train], gold[outer_train], grid, tolerance
        )
        heldout_m3_threshold = choose_threshold(
            m3_probabilities[outer_train], gold[outer_train], grid, tolerance
        )
        nested_m1[outer_fold, outer_fold] = heldout_m1_threshold
        nested_m3[outer_fold, outer_fold] = heldout_m3_threshold
        heldout_features = build_features(
            m1_probabilities[heldout_indices],
            np.full(len(heldout_indices), heldout_m1_threshold, dtype=np.float64),
            data["character_lengths"][heldout_indices],
            data["m1_token_lengths"][heldout_indices],
        )
        heldout_m1_prediction = (
            m1_probabilities[heldout_indices] >= heldout_m1_threshold
        ).astype(np.uint8)
        heldout_m3_prediction = (
            m3_probabilities[heldout_indices] >= heldout_m3_threshold
        ).astype(np.uint8)
        heldout_target = build_target(
            heldout_m1_prediction, heldout_m3_prediction, gold[heldout_indices]
        )
        features[heldout_indices] = heldout_features
        router_targets[heldout_indices] = heldout_target
        m1_thresholds[heldout_indices] = heldout_m1_threshold
        m3_thresholds[heldout_indices] = heldout_m3_threshold
        m1_predictions[heldout_indices] = heldout_m1_prediction
        m3_predictions[heldout_indices] = heldout_m3_prediction

        scaler = StandardScaler()
        scaled_train = scaler.fit_transform(nested_train_features)
        scaled_heldout = scaler.transform(heldout_features)
        router = LogisticRegression(
            penalty=router_settings["penalty"],
            C=float(router_settings["C"]),
            class_weight=router_settings["class_weight"],
            solver=router_settings["solver"],
            max_iter=int(router_settings["max_iter"]),
            random_state=int(router_settings["random_state"]),
        )
        router.fit(scaled_train, nested_train_target)
        train_logistic_score = router.predict_proba(scaled_train)[:, 1]
        heldout_logistic_score = router.predict_proba(scaled_heldout)[:, 1]
        train_policy_scores = (
            nested_train_features[:, 7],
            -nested_train_features[:, 8],
            train_logistic_score,
        )
        heldout_policy_scores = (
            heldout_features[:, 7],
            -heldout_features[:, 8],
            heldout_logistic_score,
        )
        for policy_index in range(len(DEPLOYABLE_POLICIES)):
            route_scores[policy_index, heldout_indices] = heldout_policy_scores[policy_index]
            for rate_index, target_rate in enumerate(call_rates):
                cutoff = score_cutoff(train_policy_scores[policy_index], target_rate)
                score_cutoffs[policy_index, rate_index, outer_position] = cutoff
                route_masks[policy_index, rate_index, heldout_indices] = apply_cutoff(
                    heldout_policy_scores[policy_index], cutoff
                )

        scaler_mean[outer_position] = scaler.mean_
        scaler_scale[outer_position] = scaler.scale_
        router_coef[outer_position] = router.coef_[0]
        router_intercept[outer_position] = router.intercept_[0]
        n_iter = int(router.n_iter_[0])
        if n_iter >= int(router_settings["max_iter"]):
            raise RuntimeError(f"Outer fold {outer_fold} logistic router did not converge")
        router_n_iter[outer_position] = n_iter
        discrimination = binary_discrimination(heldout_target, heldout_logistic_score)
        predicted_positive = heldout_logistic_score >= 0.5
        fold_rows.append(
            {
                "outer_fold_index": outer_fold,
                "router_train_rows": int(len(train_indices)),
                "heldout_rows": int(len(heldout_indices)),
                "router_train_components": int(len(component_groups(components, train_indices))),
                "heldout_components": int(len(component_groups(components, heldout_indices))),
                "router_train_target_positive": int(np.sum(nested_train_target)),
                "router_train_target_prevalence": float(np.mean(nested_train_target)),
                "heldout_target_positive": int(np.sum(heldout_target)),
                "heldout_target_prevalence": float(np.mean(heldout_target)),
                "router_pr_auc": discrimination["pr_auc"],
                "router_roc_auc": discrimination["roc_auc"],
                "router_precision_at_0_5": discrimination["precision_at_0_5"],
                "router_recall_at_0_5": discrimination["recall_at_0_5"],
                "router_n_iter": n_iter,
                "router_converged": bool(n_iter < int(router_settings["max_iter"])),
                "coefficient_l2_norm": float(np.linalg.norm(router.coef_[0])),
            }
        )
        fold_states[outer_fold] = {
            "heldout_indices": heldout_indices,
            "train_indices": train_indices,
            "train_target": nested_train_target,
            "heldout_target": heldout_target,
            "train_features": nested_train_features,
            "train_policy_scores": train_policy_scores,
            "heldout_policy_scores": heldout_policy_scores,
            "predicted_positive": predicted_positive,
        }

    finite_arrays = (
        features,
        m1_thresholds,
        m3_thresholds,
        nested_m1,
        nested_m3,
        route_scores,
        scaler_mean,
        scaler_scale,
        router_coef,
        router_intercept,
    )
    if any(not np.all(np.isfinite(array)) for array in finite_arrays):
        raise RuntimeError("Non-finite nested EXP-060 verifier output")
    for rate_index, target_rate in enumerate(call_rates):
        cutoffs = score_cutoffs[:, rate_index, :]
        if target_rate == 0.0:
            valid_cutoffs = np.all(np.isposinf(cutoffs))
        elif target_rate == 1.0:
            valid_cutoffs = np.all(np.isneginf(cutoffs))
        else:
            valid_cutoffs = np.all(np.isfinite(cutoffs))
        if not valid_cutoffs:
            raise RuntimeError(f"Invalid verifier score cutoffs for target rate {target_rate}")

    private_arrays: dict[str, np.ndarray] = {
        "sample_ids": np.asarray(data["sample_ids"]),
        "component_ids": components,
        "fold_ids": folds,
        "gold": gold,
        "features": features,
        "router_targets": router_targets,
        "nested_m1_thresholds": nested_m1,
        "nested_m3_thresholds": nested_m3,
        "m1_thresholds": m1_thresholds,
        "m3_thresholds": m3_thresholds,
        "m1_predictions": m1_predictions,
        "m3_predictions": m3_predictions,
        "route_scores": route_scores,
        "route_masks": route_masks,
        "score_cutoffs": score_cutoffs,
        "scaler_mean": scaler_mean,
        "scaler_scale": scaler_scale,
        "router_coef": router_coef,
        "router_intercept": router_intercept,
        "router_n_iter": router_n_iter,
    }
    call_rows: list[dict[str, Any]] = []
    zero_mask = np.zeros(rows, dtype=np.uint8)
    one_mask = np.ones(rows, dtype=np.uint8)
    call_rows.append(call_rate_row("m1_only", 0.0, zero_mask, gold, m1_predictions))
    call_rows.append(call_rate_row("m3_only", 1.0, one_mask, gold, m3_predictions))
    routed_predictions: dict[tuple[str, float], np.ndarray] = {}
    call_lookup: dict[tuple[str, float], dict[str, Any]] = {}
    for policy_index, policy in enumerate(DEPLOYABLE_POLICIES):
        for rate_index, target_rate in enumerate(call_rates):
            mask = route_masks[policy_index, rate_index]
            prediction = routed_prediction(mask, m1_predictions, m3_predictions)
            row = call_rate_row(policy, target_rate, mask, gold, prediction)
            call_rows.append(row)
            call_lookup[(policy, target_rate)] = row
            routed_predictions[(policy, target_rate)] = prediction

    baseline = classification(gold, m1_predictions)
    maximum_rate = float(config["gate"]["maximum_actual_qwen_call_rate"])
    policy_results: dict[str, Any] = {}
    candidate_rows: dict[str, dict[str, Any]] = {}
    for policy in DEPLOYABLE_POLICIES:
        if is_replication(config):
            candidate = call_lookup[(policy, 0.15)]
        else:
            eligible = [
                call_lookup[(policy, rate)]
                for rate in call_rates
                if call_lookup[(policy, rate)]["actual_call_rate"] <= maximum_rate
            ]
            candidate = sorted(eligible, key=candidate_sort_key)[0]
        gains = {
            "six_label_macro_f1_gain": float(candidate["macro_f1"] - baseline["macro_f1"]),
            "five_label_macro_f1_gain": float(
                candidate["five_label_macro_f1"] - baseline["five_label_macro_f1"]
            ),
            "hamming_loss_delta": float(candidate["hamming_loss"] - baseline["hamming_loss"]),
        }
        non_surprise_gains = {
            label: float(candidate[f"f1_{label}"] - baseline["per_label"][label]["f1"])
            for label in LABEL_ORDER
            if label != "surprise"
        }
        gains["maximum_non_surprise_label_f1_gain"] = max(non_surprise_gains.values())
        gates = {
            "maximum_actual_qwen_call_rate": candidate["actual_call_rate"]
            <= float(config["gate"]["maximum_actual_qwen_call_rate"]) + tolerance,
            "minimum_six_label_macro_f1_gain": gains["six_label_macro_f1_gain"]
            >= float(config["gate"]["minimum_six_label_macro_f1_gain"]) - tolerance,
            "minimum_five_label_macro_f1_gain": gains["five_label_macro_f1_gain"]
            >= float(config["gate"]["minimum_five_label_macro_f1_gain"]) - tolerance,
            "hamming_loss_not_worse": gains["hamming_loss_delta"]
            <= float(config["gate"]["maximum_hamming_loss_increase"]),
            "minimum_non_surprise_label_f1_gain": gains["maximum_non_surprise_label_f1_gain"]
            >= float(config["gate"]["minimum_one_non_surprise_label_f1_gain"]) - tolerance,
        }
        candidate_public = {**candidate, **gains}
        policy_results[policy] = {
            "candidate": candidate_public,
            "gates": gates,
            "passed": bool(all(gates.values()) and (not is_replication(config) or policy == "logistic_router")),
            **({
                "diagnostic_gate_passed": bool(all(gates.values())),
                "evidence_role": "primary" if policy == "logistic_router" else "descriptive_only",
            } if is_replication(config) else {}),
        }
        candidate_rows[policy] = candidate

    if is_replication(config):
        selected_policy: str | None = "logistic_router"
        overall_decision = "Pass" if policy_results[selected_policy]["passed"] else "Fail"
    else:
        passing = [policy for policy in DEPLOYABLE_POLICIES if policy_results[policy]["passed"]]
        selected_policy = None
        if passing:
            precedence = {policy: index for index, policy in enumerate(DEPLOYABLE_POLICIES)}
            passing.sort(
                key=lambda policy: (*candidate_sort_key(candidate_rows[policy]), precedence[policy])
            )
            selected_policy = passing[0]
        overall_decision = "Pass" if selected_policy is not None else "Stop router branch"

    selected = {
        "schema_version": "exp-router-selected-operating-point-v2" if is_replication(config) else "exp-060-selected-operating-point-v1",
        "experiment_id": experiment_id(config),
        **({
            "run_id": run_id(config),
            "attempt_id": attempt_id(config),
            "model_seed": model_seed(config),
            "primary_policy": "logistic_router",
            "primary_nominal_call_rate": 0.15,
        } if is_replication(config) else {}),
        "baseline": baseline,
        "policies": policy_results,
        "overall": {
            "decision": overall_decision,
            "selected_policy": selected_policy,
            "selected_candidate": (
                policy_results[selected_policy]["candidate"] if selected_policy is not None else None
            ),
        },
    }

    return {
        "m1_probabilities": m1_probabilities,
        "m3_probabilities": m3_probabilities,
        "private_arrays": private_arrays,
        "fold_rows": fold_rows,
        "fold_states": fold_states,
        "call_rows": call_rows,
        "call_lookup": call_lookup,
        "routed_predictions": routed_predictions,
        "baseline": baseline,
        "selected": selected,
        "candidate_rows": candidate_rows,
        "policy_results": policy_results,
        "selected_policy": selected_policy,
    }


def policy_comparison_rows(state: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rate in [float(value) for value in config["call_rates"]]:
        r4 = state["call_lookup"][("logistic_router", rate)]
        heuristics = [
            state["call_lookup"][("m1_max_entropy", rate)],
            state["call_lookup"][("m1_threshold_proximity", rate)],
        ]
        best = sorted(heuristics, key=candidate_sort_key)[0]
        rows.append(
            {
                "target_call_rate": rate,
                "r4_actual_call_rate": r4["actual_call_rate"],
                "best_heuristic_policy": best["policy"],
                "best_heuristic_actual_call_rate": best["actual_call_rate"],
                "r4_macro_f1": r4["macro_f1"],
                "best_heuristic_macro_f1": best["macro_f1"],
                "macro_f1_delta": float(r4["macro_f1"] - best["macro_f1"]),
                "r4_five_label_macro_f1": r4["five_label_macro_f1"],
                "best_heuristic_five_label_macro_f1": best["five_label_macro_f1"],
                "five_label_macro_f1_delta": float(
                    r4["five_label_macro_f1"] - best["five_label_macro_f1"]
                ),
                "r4_hamming_loss": r4["hamming_loss"],
                "best_heuristic_hamming_loss": best["hamming_loss"],
                "hamming_loss_delta": float(r4["hamming_loss"] - best["hamming_loss"]),
            }
        )
    return rows


def random_routing_rows(
    state: dict[str, Any], data: dict[str, np.ndarray], config: dict[str, Any]
) -> list[dict[str, Any]]:
    repetitions = int(config["router"]["random_routing_repetitions"])
    base_seed = int(config["router"]["random_routing_seed"])
    rates = [float(value) for value in config["call_rates"]]
    folds = np.asarray(data["fold_ids"])
    components = np.asarray(data["component_ids"])
    gold = np.asarray(data["gold"], dtype=np.uint8)
    private = state["private_arrays"]
    m1_prediction = private["m1_predictions"]
    m3_prediction = private["m3_predictions"]
    rows: list[dict[str, Any]] = []
    for policy_index, policy in enumerate(DEPLOYABLE_POLICIES):
        for rate_index, rate in enumerate(rates):
            matched_mask = private["route_masks"][policy_index, rate_index]
            macro_values: list[float] = []
            five_values: list[float] = []
            hamming_values: list[float] = []
            call_values: list[float] = []
            for repetition in range(repetitions):
                random_mask = np.zeros(len(gold), dtype=np.uint8)
                for fold_id in [int(value) for value in config["cross_fitting"]["outer_fold_ids"]]:
                    heldout = np.flatnonzero(folds == fold_id)
                    target_rows = int(np.sum(matched_mask[heldout]))
                    fold_mask = component_random_mask(
                        components,
                        heldout,
                        target_rows,
                        (base_seed, policy_index, rate_index, fold_id, repetition),
                    )
                    random_mask[heldout] = fold_mask[heldout]
                prediction = routed_prediction(random_mask, m1_prediction, m3_prediction)
                metrics = classification(gold, prediction)
                macro_values.append(metrics["macro_f1"])
                five_values.append(metrics["five_label_macro_f1"])
                hamming_values.append(metrics["hamming_loss"])
                call_values.append(float(np.mean(random_mask)))
            macro = np.asarray(macro_values, dtype=np.float64)
            five = np.asarray(five_values, dtype=np.float64)
            hamming = np.asarray(hamming_values, dtype=np.float64)
            calls = np.asarray(call_values, dtype=np.float64)
            rows.append(
                {
                    "policy": policy,
                    "target_call_rate": rate,
                    "matched_policy_actual_call_rate": float(np.mean(matched_mask)),
                    "random_actual_call_rate_mean": float(np.mean(calls)),
                    "random_actual_call_rate_min": float(np.min(calls)),
                    "random_actual_call_rate_max": float(np.max(calls)),
                    "macro_f1_mean": float(np.mean(macro)),
                    "macro_f1_p05": float(np.percentile(macro, 5.0)),
                    "macro_f1_p50": float(np.percentile(macro, 50.0)),
                    "macro_f1_p95": float(np.percentile(macro, 95.0)),
                    "five_label_macro_f1_mean": float(np.mean(five)),
                    "five_label_macro_f1_p05": float(np.percentile(five, 5.0)),
                    "five_label_macro_f1_p50": float(np.percentile(five, 50.0)),
                    "five_label_macro_f1_p95": float(np.percentile(five, 95.0)),
                    "hamming_loss_mean": float(np.mean(hamming)),
                    "hamming_loss_p05": float(np.percentile(hamming, 5.0)),
                    "hamming_loss_p50": float(np.percentile(hamming, 50.0)),
                    "hamming_loss_p95": float(np.percentile(hamming, 95.0)),
                }
            )
    return rows


def coverage_values(config: dict[str, Any]) -> list[float]:
    return [float(item) for item in config["risk_coverage"]["coverages"]]


def routed_uncertainty_scores(
    route_mask: np.ndarray,
    m1_probabilities: np.ndarray,
    m3_probabilities: np.ndarray,
    m1_thresholds: np.ndarray,
    m3_thresholds: np.ndarray,
) -> dict[str, np.ndarray]:
    route = np.asarray(route_mask, dtype=bool)
    probabilities = np.where(route[:, None], m3_probabilities, m1_probabilities)
    thresholds = np.where(route, m3_thresholds, m1_thresholds)
    entropy = binary_entropy(probabilities)
    return {
        "mean_entropy": np.mean(entropy, axis=1),
        "max_entropy": np.max(entropy, axis=1),
        "margin": -np.min(np.abs(probabilities - thresholds[:, None]), axis=1),
    }


def foldwise_acceptance_mask(
    scores: np.ndarray, folds: np.ndarray, coverage: float, outer_folds: Sequence[int]
) -> np.ndarray:
    accepted = np.zeros(len(scores), dtype=np.uint8)
    for fold_id in outer_folds:
        indices = np.flatnonzero(folds == fold_id)
        count = int(math.floor(float(coverage) * len(indices) + 0.5))
        if count <= 0:
            raise ValueError("Risk-coverage contract produced zero accepted rows")
        order = np.argsort(scores[indices], kind="stable")
        accepted[indices[order[:count]]] = 1
    return accepted


def risk_and_retention_rows(
    state: dict[str, Any], data: dict[str, np.ndarray], config: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    private = state["private_arrays"]
    gold = np.asarray(data["gold"], dtype=np.uint8)
    folds = np.asarray(data["fold_ids"])
    outer_folds = [int(value) for value in config["cross_fitting"]["outer_fold_ids"]]
    risks: list[dict[str, Any]] = []
    retention: list[dict[str, Any]] = []
    rates = [float(value) for value in config["call_rates"]]
    for policy_index, policy in enumerate(DEPLOYABLE_POLICIES):
        candidate_rate = float(state["candidate_rows"][policy]["target_call_rate"])
        rate_index = rates.index(candidate_rate)
        route_mask = private["route_masks"][policy_index, rate_index]
        prediction = state["routed_predictions"][(policy, candidate_rate)]
        scores = routed_uncertainty_scores(
            route_mask,
            state["m1_probabilities"],
            state["m3_probabilities"],
            private["m1_thresholds"],
            private["m3_thresholds"],
        )
        for method in UNCERTAINTY_METHODS:
            for coverage in coverage_values(config):
                accepted = foldwise_acceptance_mask(scores[method], folds, coverage, outer_folds)
                selected = accepted.astype(bool)
                metrics = classification(gold[selected], prediction[selected])
                risks.append(
                    {
                        "policy": policy,
                        "uncertainty_method": method,
                        "target_coverage": coverage,
                        "actual_coverage": float(np.mean(accepted)),
                        "accepted_rows": int(np.sum(accepted)),
                        "hamming_risk": metrics["hamming_loss"],
                        "subset_error": metrics["subset_error"],
                        "micro_f1": metrics["micro_f1"],
                        "macro_f1": metrics["macro_f1"],
                        "five_label_macro_f1": metrics["five_label_macro_f1"],
                    }
                )
                for label_index, label in enumerate(LABEL_ORDER):
                    positive = gold[:, label_index] == 1
                    support = int(np.sum(positive))
                    retained = int(np.sum(positive & selected))
                    retention.append(
                        {
                            "policy": policy,
                            "uncertainty_method": method,
                            "target_coverage": coverage,
                            "label": label,
                            "positive_support": support,
                            "retained_positive": retained,
                            "positive_retention": float(retained / support) if support else 0.0,
                        }
                    )
    return risks, retention


def percentile_interval(values: Sequence[float], point_estimate: float) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "point_estimate": float(point_estimate),
        "mean": float(np.mean(array)),
        "lower_95": float(np.percentile(array, 2.5)),
        "upper_95": float(np.percentile(array, 97.5)),
    }


def bootstrap_result(
    state: dict[str, Any], data: dict[str, np.ndarray], config: dict[str, Any]
) -> dict[str, Any]:
    repetitions = int(config["bootstrap"]["repetitions"])
    seed = int(config["bootstrap"]["seed"])
    groups = component_groups(np.asarray(data["component_ids"]))
    gold = np.asarray(data["gold"], dtype=np.uint8)
    private = state["private_arrays"]
    rates = [float(value) for value in config["call_rates"]]
    policy_candidates: dict[str, Any] = {}
    for policy_index, policy in enumerate(DEPLOYABLE_POLICIES):
        candidate = state["candidate_rows"][policy]
        rate = float(candidate["target_call_rate"])
        rate_index = rates.index(rate)
        route_mask = private["route_masks"][policy_index, rate_index]
        routed = state["routed_predictions"][(policy, rate)]
        macro_deltas: list[float] = []
        five_deltas: list[float] = []
        hamming_deltas: list[float] = []
        call_rates: list[float] = []
        rng = np.random.default_rng(np.random.SeedSequence([seed, policy_index]))
        for _ in range(repetitions):
            sampled_groups = rng.integers(0, len(groups), size=len(groups))
            sampled_indices = np.concatenate([groups[int(index)] for index in sampled_groups])
            baseline_metrics = classification(
                gold[sampled_indices], private["m1_predictions"][sampled_indices]
            )
            routed_metrics = classification(gold[sampled_indices], routed[sampled_indices])
            macro_deltas.append(routed_metrics["macro_f1"] - baseline_metrics["macro_f1"])
            five_deltas.append(
                routed_metrics["five_label_macro_f1"]
                - baseline_metrics["five_label_macro_f1"]
            )
            hamming_deltas.append(
                routed_metrics["hamming_loss"] - baseline_metrics["hamming_loss"]
            )
            call_rates.append(float(np.mean(route_mask[sampled_indices])))
        point_macro = float(candidate["macro_f1"] - state["baseline"]["macro_f1"])
        point_five = float(
            candidate["five_label_macro_f1"] - state["baseline"]["five_label_macro_f1"]
        )
        point_hamming = float(candidate["hamming_loss"] - state["baseline"]["hamming_loss"])
        policy_candidates[policy] = {
            "target_call_rate": rate,
            "actual_call_rate": float(candidate["actual_call_rate"]),
            "intervals": {
                "macro_f1_gain": percentile_interval(macro_deltas, point_macro),
                "five_label_macro_f1_gain": percentile_interval(five_deltas, point_five),
                "hamming_loss_delta": percentile_interval(hamming_deltas, point_hamming),
                "actual_call_rate": percentile_interval(
                    call_rates, float(candidate["actual_call_rate"])
                ),
            },
        }
    return {
        "schema_version": "exp-router-bootstrap-v2" if is_replication(config) else "exp-060-bootstrap-v1",
        "experiment_id": experiment_id(config),
        "repetitions": repetitions,
        "seed": seed,
        "unit": config["bootstrap"]["unit"],
        "interval": config["bootstrap"]["interval"],
        "policy_candidates": policy_candidates,
        "overall_selected_policy": state["selected_policy"],
        "selection_warning": (
            "Point estimates determine the frozen development gate; intervals only qualify stability. "
            "This train-OOF bootstrap is not an independent test."
        ),
    }


def feature_contract(config: dict[str, Any]) -> dict[str, Any]:
    cross_fitting = config["cross_fitting"]
    target = config["target_contract"]
    return {
        "schema_version": "exp-router-feature-contract-v2" if is_replication(config) else "exp-060-feature-contract-v1",
        "experiment_id": experiment_id(config),
        **({
            "run_id": run_id(config),
            "attempt_id": attempt_id(config),
            "model_seed": model_seed(config),
        } if is_replication(config) else {}),
        "label_order": list(LABEL_ORDER),
        "ordered_features": list(FEATURE_NAMES),
        "feature_count": len(FEATURE_NAMES),
        "calibration": {"m1": "identity", "m3": "identity"},
        "nested_cross_fitting": {
            "outer_folds": len(cross_fitting["outer_fold_ids"]),
            "outer_train_folds": int(cross_fitting["outer_router_train_folds"]),
            "inner_threshold_train_folds": int(
                cross_fitting["nested_router_train_threshold_folds"]
            ),
        },
        "target_contract": {
            "unit": target["unit"],
            "positive": target["positive"],
            "tie_policy": target["tie_policy"],
        },
        "policy_order": list(POLICY_ORDER),
        "call_rates": [float(value) for value in config["call_rates"]],
        "forbidden_runtime_feature_classes": list(
            config["feature_contract"]["forbidden_runtime_feature_classes"]
        ),
        "public_row_level_data": False,
    }


def expected_report(
    selected: dict[str, Any], bootstrap: dict[str, Any], config: dict[str, Any]
) -> str:
    overall = selected["overall"]
    lines = [
        f"# {experiment_id(config)} Pre-Qwen Deployable Router",
        "",
        f"- Decision: `{overall['decision']}`",
        f"- Selected policy: `{overall['selected_policy']}`",
        "- Evidence scope: fully nested DATA-SO-TASK-V1 train OOF only.",
        "- Validation/test/raw text/model forward access: `false`.",
        "",
        "## Frozen policy candidates",
        "",
    ]
    for policy in DEPLOYABLE_POLICIES:
        record = selected["policies"][policy]
        candidate = record["candidate"]
        lines.append(
            f"- `{policy}`: passed=`{record['passed']}`, actual call rate="
            f"`{candidate['actual_call_rate']:.6f}`, Macro-F1 gain="
            f"`{candidate['six_label_macro_f1_gain']:+.6f}`."
        )
    lines.extend(
        [
            "",
            "## Uncertainty",
            "",
            f"All intervals use `{bootstrap['repetitions']}` duplicate-component bootstrap replicates. ",
            "Point estimates determine the development gate; intervals qualify stability only.",
            "",
            "## Claim boundary",
            "",
            (
                f"This is train-OOF evidence for the frozen seed-{model_seed(config)} model pair. "
                "It is not an independent-test deployment result, a completed cross-seed claim, or "
                "evidence of an emotion mechanism."
                if is_replication(config)
                else "This is train-OOF development evidence for one frozen seed-42 model pair. It is not an "
            ),
            *( [] if is_replication(config) else [
                "independent-test deployment result, a cross-seed claim, or evidence of an emotion mechanism."
            ] ),
            "",
        ]
    )
    return "\n".join(lines)


def router_discrimination(state: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    target = state["private_arrays"]["router_targets"]
    scores = state["private_arrays"]["route_scores"][2]
    overall = binary_discrimination(target, scores)
    return {
        "schema_version": "exp-router-discrimination-v2" if is_replication(config) else "exp-060-router-discrimination-v1",
        "experiment_id": experiment_id(config),
        "overall": overall,
        "fold_auc_undefined": {
            "pr_auc": int(sum(row["router_pr_auc"] is None for row in state["fold_rows"])),
            "roc_auc": int(sum(row["router_roc_auc"] is None for row in state["fold_rows"])),
        },
        "all_folds_converged": bool(
            all(bool(row["router_converged"]) for row in state["fold_rows"])
        ),
    }


def numeric_equal(left: Any, right: Any, tolerance: float) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isfinite(float(left)) and math.isfinite(float(right)) and math.isclose(
            float(left), float(right), rel_tol=0.0, abs_tol=tolerance
        )
    return left == right


def scalar_detail(actual: Any, expected: Any) -> dict[str, Any]:
    if isinstance(actual, str) or isinstance(expected, str):
        actual_text = str(actual)
        expected_text = str(expected)
        return {
            "actual_length": len(actual_text),
            "expected_length": len(expected_text),
            "actual_sha256": hashlib.sha256(actual_text.encode()).hexdigest(),
            "expected_sha256": hashlib.sha256(expected_text.encode()).hexdigest(),
        }
    def safe(value: Any) -> Any:
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        return value

    return {"actual": safe(actual), "expected": safe(expected)}


def compare_tree(
    checks: Checks, name: str, actual: Any, expected: Any, tolerance: float
) -> None:
    if isinstance(expected, dict):
        checks.add(
            f"{name}.keys",
            isinstance(actual, dict) and set(actual) == set(expected),
            {
                "actual_count": len(actual) if isinstance(actual, dict) else None,
                "expected_count": len(expected),
                "missing_count": (
                    len(set(expected) - set(actual)) if isinstance(actual, dict) else len(expected)
                ),
                "extra_count": len(set(actual) - set(expected)) if isinstance(actual, dict) else 0,
            },
        )
        if not isinstance(actual, dict):
            return
        for key in sorted(set(actual) & set(expected)):
            compare_tree(checks, f"{name}.{key}", actual[key], expected[key], tolerance)
    elif isinstance(expected, list):
        checks.add(
            f"{name}.length",
            isinstance(actual, list) and len(actual) == len(expected),
            {
                "actual": len(actual) if isinstance(actual, list) else None,
                "expected": len(expected),
            },
        )
        if not isinstance(actual, list):
            return
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected)):
            compare_tree(checks, f"{name}[{index}]", actual_item, expected_item, tolerance)
    else:
        checks.add(
            name,
            numeric_equal(actual, expected, tolerance),
            scalar_detail(actual, expected),
        )


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        return list(reader.fieldnames or []), list(reader)


def convert_csv_value(raw: str | None, expected: Any) -> Any:
    if expected is None:
        return None if raw in (None, "", "None", "null") else raw
    if isinstance(expected, bool):
        if raw == "True":
            return True
        if raw == "False":
            return False
        return raw
    if isinstance(expected, int) and not isinstance(expected, bool):
        try:
            return int(str(raw))
        except (TypeError, ValueError):
            return raw
    if isinstance(expected, float):
        try:
            return float(str(raw))
        except (TypeError, ValueError):
            return raw
    return raw


def compare_csv(
    checks: Checks,
    name: str,
    path: Path,
    expected_rows: list[dict[str, Any]],
    tolerance: float,
) -> None:
    columns, actual_rows = read_csv(path)
    expected_columns = list(CSV_COLUMNS[path.name])
    checks.add(
        f"{name}.columns",
        columns == expected_columns,
        {"actual_count": len(columns), "expected_count": len(expected_columns)},
    )
    checks.add(
        f"{name}.rows",
        len(actual_rows) == len(expected_rows),
        {"actual": len(actual_rows), "expected": len(expected_rows)},
    )
    for row_index, (actual, expected) in enumerate(zip(actual_rows, expected_rows)):
        for column in expected_columns:
            converted = convert_csv_value(actual.get(column), expected[column])
            checks.add(
                f"{name}.row_{row_index}.{column}",
                numeric_equal(converted, expected[column], tolerance),
                scalar_detail(converted, expected[column]),
            )


def compare_private_arrays(
    checks: Checks,
    actual: dict[str, np.ndarray],
    expected: dict[str, np.ndarray],
    tolerance: float,
) -> None:
    checks.add(
        "private.keys",
        set(actual) == set(expected),
        {
            "actual_count": len(actual),
            "expected_count": len(expected),
            "missing_count": len(set(expected) - set(actual)),
            "extra_count": len(set(actual) - set(expected)),
        },
    )
    for name in sorted(set(actual) & set(expected)):
        observed = actual[name]
        reference = expected[name]
        checks.add(
            f"private.{name}.shape",
            observed.shape == reference.shape,
            {"actual": list(observed.shape), "expected": list(reference.shape)},
        )
        checks.add(
            f"private.{name}.dtype",
            observed.dtype == reference.dtype,
            {"actual": str(observed.dtype), "expected": str(reference.dtype)},
        )
        if observed.shape != reference.shape:
            continue
        if observed.dtype.kind == "f" and reference.dtype.kind == "f":
            no_nan = bool(not np.any(np.isnan(observed)) and not np.any(np.isnan(reference)))
            infinity_match = bool(
                np.array_equal(np.isposinf(observed), np.isposinf(reference))
                and np.array_equal(np.isneginf(observed), np.isneginf(reference))
            )
            finite_positions = np.isfinite(observed) & np.isfinite(reference)
            maximum_error = (
                float(np.max(np.abs(observed[finite_positions] - reference[finite_positions])))
                if np.any(finite_positions)
                else 0.0
            )
            checks.add(
                f"private.{name}.values",
                no_nan and infinity_match and maximum_error <= tolerance,
                {
                    "nan_free": no_nan,
                    "infinity_pattern_match": infinity_match,
                    "maximum_finite_absolute_error": maximum_error,
                },
            )
        else:
            mismatch_count = int(np.sum(observed != reference))
            checks.add(
                f"private.{name}.values",
                mismatch_count == 0,
                {"mismatch_count": mismatch_count, "element_count": int(observed.size)},
            )


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as source:
        header = source.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("Invalid PNG header")
    return struct.unpack(">II", header[16:24])


def render_expected_figures(
    output_dir: Path,
    call_rows: list[dict[str, Any]],
    risk_rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Path]:
    """Independently render the two frozen public figures from recomputed rows."""
    configured = config.get("runtime", {}).get("mplconfigdir")
    mplconfigdir = (
        Path(str(configured)).expanduser().resolve()
        if configured
        else output_dir / "mplconfig"
    )
    mplconfigdir.mkdir(parents=True, exist_ok=True)
    previous = os.environ.get("MPLCONFIGDIR")
    os.environ["MPLCONFIGDIR"] = str(mplconfigdir)
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        call_path = output_dir / "call-rate-performance.png"
        figure, axis = plt.subplots(figsize=(8.0, 5.0))
        for policy in DEPLOYABLE_POLICIES:
            rows = [row for row in call_rows if row["policy"] == policy]
            axis.plot(
                [100.0 * row["actual_call_rate"] for row in rows],
                [row["macro_f1"] for row in rows],
                marker="o",
                label=policy,
            )
        axis.set_xlabel("Actual Qwen call rate (%)")
        axis.set_ylabel("Six-label Macro-F1")
        axis.grid(alpha=0.25)
        axis.legend()
        figure.tight_layout()
        figure.savefig(call_path, dpi=180)
        plt.close(figure)

        risk_path = output_dir / "routed-risk-coverage.png"
        figure, axis = plt.subplots(figsize=(8.0, 5.0))
        for policy in DEPLOYABLE_POLICIES:
            for method in UNCERTAINTY_METHODS:
                rows = [
                    row
                    for row in risk_rows
                    if row["policy"] == policy and row["uncertainty_method"] == method
                ]
                axis.plot(
                    [row["actual_coverage"] for row in rows],
                    [row["hamming_risk"] for row in rows],
                    marker=".",
                    label=f"{policy}:{method}",
                )
        axis.set_xlabel("Actual coverage")
        axis.set_ylabel("Hamming risk")
        axis.grid(alpha=0.25)
        axis.legend(fontsize=7, ncol=2)
        figure.tight_layout()
        figure.savefig(risk_path, dpi=180)
        plt.close(figure)
        return {call_path.name: call_path, risk_path.name: risk_path}
    finally:
        if previous is None:
            os.environ.pop("MPLCONFIGDIR", None)
        else:
            os.environ["MPLCONFIGDIR"] = previous


def decoded_png_rgba(path: Path) -> np.ndarray:
    from PIL import Image

    with Image.open(path) as image:
        return np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()


def find_prerequisite(config: dict[str, Any], *names: str) -> Path:
    prerequisites = config["prerequisites"]
    for name in names:
        if name in prerequisites:
            return require_record(prerequisites[name])
    raise KeyError(f"Missing prerequisite record; expected one of {names}")


def verification_passed(value: dict[str, Any]) -> bool:
    if value.get("status") != "Passed":
        return False
    if "failed_count" in value:
        return int(value["failed_count"]) == 0
    if isinstance(value.get("checks"), dict) and "failed" in value["checks"]:
        return int(value["checks"]["failed"]) == 0
    return True


def validate_input(checks: Checks, data: dict[str, np.ndarray], config: dict[str, Any]) -> None:
    expected = expected_paired_schema()
    checks.add(
        "input.keys",
        set(data) == set(expected),
        {
            "actual_count": len(data),
            "expected_count": len(expected),
            "missing_count": len(set(expected) - set(data)),
            "extra_count": len(set(data) - set(expected)),
        },
    )
    for name in sorted(set(data) & set(expected)):
        shape, dtype = expected[name]
        checks.add(
            f"input.{name}.shape",
            data[name].shape == shape,
            {"actual": list(data[name].shape), "expected": list(shape)},
        )
        checks.add(
            f"input.{name}.dtype",
            str(data[name].dtype) == dtype,
            {"actual": str(data[name].dtype), "expected": dtype},
        )
    checks.add("input.unique_samples", len(set(data["sample_ids"].tolist())) == len(data["sample_ids"]))
    observed_source_order = canonical_digest(data["sample_ids"].tolist())
    registered_source_order = config["data"].get(
        "source_order_sha256", EXPECTED_SOURCE_ORDER_SHA256
    )
    checks.add(
        "input.source_order",
        observed_source_order == registered_source_order
        and (is_replication(config) or observed_source_order == EXPECTED_SOURCE_ORDER_SHA256),
        {
            "registered_match": observed_source_order == registered_source_order,
            "canonical_match": observed_source_order == EXPECTED_SOURCE_ORDER_SHA256,
        },
    )
    checks.add("input.binary_gold", bool(np.all(np.isin(data["gold"], [0, 1]))))
    checks.add("input.finite_m1_logits", bool(np.all(np.isfinite(data["m1_logits"]))))
    checks.add("input.finite_m3_logits", bool(np.all(np.isfinite(data["m3_logits"]))))
    checks.add("input.nonnegative_character_lengths", bool(np.all(data["character_lengths"] >= 0)))
    checks.add("input.nonnegative_m1_token_lengths", bool(np.all(data["m1_token_lengths"] >= 0)))
    outer_folds = [int(value) for value in config["cross_fitting"]["outer_fold_ids"]]
    checks.add("input.fold_ids", sorted(np.unique(data["fold_ids"]).tolist()) == outer_folds)
    for fold_id in outer_folds:
        checks.add(f"input.fold_{fold_id}_rows", int(np.sum(data["fold_ids"] == fold_id)) == 672)
    component_folds: dict[str, set[int]] = {}
    for component, fold in zip(data["component_ids"].tolist(), data["fold_ids"].tolist()):
        component_folds.setdefault(str(component), set()).add(int(fold))
    checks.add(
        "input.component_fold_disjoint",
        len(component_folds) == 3277 and all(len(value) == 1 for value in component_folds.values()),
        {"component_count": len(component_folds)},
    )
    for family in ("m1", "m3"):
        hashes = [str(value) for value in data[f"{family}_fold_run_sha256"].tolist()]
        checks.add(
            f"input.{family}_fold_hashes",
            len(set(hashes)) == 5 and all(len(value) == 64 for value in hashes),
            {"unique_count": len(set(hashes))},
        )


def scan_public_artifacts(
    checks: Checks,
    run_dir: Path,
    sample_ids: np.ndarray,
    component_ids: np.ndarray,
) -> None:
    forbidden_suffixes = {".npz", ".npy", ".parquet", ".jsonl"}
    forbidden_files = [path for path in run_dir.rglob("*") if path.is_file() and path.suffix in forbidden_suffixes]
    checks.add("privacy.no_private_file_types", not forbidden_files, {"count": len(forbidden_files)})

    privacy_paths: list[str] = []
    malformed_json = 0
    for path in sorted(run_dir.rglob("*.json")):
        if path.name == "verification.json":
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            malformed_json += 1
            continue
        privacy_paths.extend(public_sensitive_paths(value))
    checks.add("privacy.public_json_well_formed", malformed_json == 0, {"count": malformed_json})
    checks.add("privacy.public_json_keys", not privacy_paths, {"violation_count": len(privacy_paths)})

    unknown_csv = []
    for path in sorted(run_dir.rglob("*.csv")):
        if path.name not in CSV_COLUMNS:
            unknown_csv.append(path)
            continue
        columns, _ = read_csv(path)
        checks.add(
            f"privacy.csv_columns.{path.name}",
            columns == list(CSV_COLUMNS[path.name]),
            {"actual_count": len(columns), "expected_count": len(CSV_COLUMNS[path.name])},
        )
    checks.add("privacy.no_unknown_csv", not unknown_csv, {"count": len(unknown_csv)})

    identifiers = {str(value) for value in sample_ids.tolist()}
    identifiers.update(str(value) for value in component_ids.tolist())
    identifier_hits = 0
    token_pattern = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]*")
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path.suffix not in {".json", ".csv", ".md"}:
            continue
        if path.name == "verification.json":
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        identifier_hits += len(set(token_pattern.findall(content)) & identifiers)
    checks.add("privacy.no_real_identifiers_in_public_text", identifier_hits == 0, {"hit_count": identifier_hits})


def verify_modes(checks: Checks, run_dir: Path, private_dir: Path) -> None:
    checks.add("permissions.public_root", mode(run_dir) == 0o755, {"mode": oct(mode(run_dir))})
    for child in sorted(run_dir.rglob("*")):
        if child.name in {"verification.json", "VERIFICATION-SUMMARY.md"}:
            continue
        expected = 0o755 if child.is_dir() else 0o644
        checks.add(
            f"permissions.public.{child.relative_to(run_dir)}",
            mode(child) == expected,
            {"mode": oct(mode(child)), "expected": oct(expected)},
        )
    checks.add("permissions.private_root", mode(private_dir) == 0o700, {"mode": oct(mode(private_dir))})
    for child in sorted(private_dir.rglob("*")):
        expected = 0o700 if child.is_dir() else 0o600
        checks.add(
            f"permissions.private.{child.relative_to(private_dir)}",
            mode(child) == expected,
            {"mode": oct(mode(child)), "expected": oct(expected)},
        )


def write_summary(path: Path, result: dict[str, Any]) -> None:
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
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text("\n".join(lines), encoding="utf-8")
    temporary.replace(path)


def verify(config_path: Path) -> dict[str, Any]:
    started = time.monotonic()
    config_path = require_canonical_config_path(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    schema = config.get("schema_version")
    if schema not in (LEGACY_CONFIG_SCHEMA, REPLICATION_CONFIG_SCHEMA):
        raise ValueError("Unexpected router config schema")
    if schema == LEGACY_CONFIG_SCHEMA:
        if (
            config_path != DEFAULT_CONFIG.resolve()
            or config.get("experiment_id") != EXPERIMENT_ID
            or config.get("rq_id") != RQ_ID
        ):
            raise ValueError("EXP-060 formal config identity drift")
    else:
        if config.get("rq_id") != RQ_ID:
            raise ValueError("Replication RQ identity drift")
        validate_replication_identity(config)
    if tuple(config["data"]["label_order"]) != LABEL_ORDER:
        raise ValueError("EXP-060 label-order drift")
    input_record = config.get("input", {}).get("paired_oof", {})
    if not is_replication(config) and (
        input_record.get("path") != EXPECTED_INPUT_PATH
        or input_record.get("bytes") != EXPECTED_INPUT_BYTES
        or input_record.get("sha256") != EXPECTED_INPUT_SHA256
    ):
        raise ValueError("EXP-060 paired-OOF input identity drift")
    guard_record_paths(config)
    outputs = config["outputs"]
    if is_replication(config):
        expected_outputs = expected_replication_outputs(config)
        public_attempt = resolve_output(expected_outputs["public_attempt_dir"])
        private_attempt = resolve_output(expected_outputs["private_attempt_dir"])
        run_dir = public_attempt / "router"
        private_dir = private_attempt / "router"
        if os.path.lexists(resolve_output(expected_outputs["selection_record"])):
            raise FileExistsError("A final pipeline selection already exists")
    else:
        public_value = outputs.get("formal_run_dir", outputs.get("public_run_dir"))
        private_value = outputs.get("formal_private_dir", outputs.get("private_run_dir"))
        if public_value != EXPECTED_PUBLIC_RUN_DIR or private_value != EXPECTED_PRIVATE_RUN_DIR:
            raise ValueError("EXP-060 canonical output-path drift")
        run_dir = resolve_project(public_value)
        private_dir = resolve_project(private_value)
    lexical_run_dir = run_dir
    lexical_private_dir = private_dir
    if lexical_run_dir.is_symlink() or lexical_private_dir.is_symlink():
        raise ValueError("EXP-060 formal output roots must not be symbolic links")
    output_path = run_dir / "verification.json"
    summary_path = run_dir / "VERIFICATION-SUMMARY.md"
    if os.path.lexists(output_path) or os.path.lexists(summary_path):
        raise FileExistsError("Refusing to overwrite append-only EXP-060 verification")
    if not run_dir.is_dir() or not private_dir.is_dir():
        raise FileNotFoundError("Formal EXP-060 public/private output is incomplete")

    checks = Checks()
    tolerance = float(config["thresholds"]["numeric_tolerance"])
    expected_logistic = {
        "penalty": "l2",
        "C": 1.0,
        "class_weight": "balanced",
        "solver": "liblinear",
        "max_iter": 1000,
        "random_state": 42,
    }
    checks.add("config.identity", config.get("experiment_id") == experiment_id(config))
    checks.add("config.rq", config.get("rq_id") == RQ_ID)
    checks.add(
        "config.filename",
        is_replication(config) or config_path.name == DEFAULT_CONFIG.name,
    )
    if is_replication(config):
        checks.add("config.run_id", config.get("run_id") == run_id(config))
        checks.add("config.attempt_id", config.get("attempt_id") == attempt_id(config))
        checks.add("config.model_seed", model_seed(config) in (43, 44))
        checks.add("config.seed_contract", config.get("seed_contract") == seed_contract(config))
    checks.add("config.tier", str(config.get("tier", "")).startswith("Major"))
    checks.add(
        "config.data",
        config["data"].get("split") == "train-oof"
        and int(config["data"].get("rows", -1)) == 3360
        and int(config["data"].get("duplicate_components", -1)) == 3277,
    )
    cross_fitting = config["cross_fitting"]
    checks.add(
        "config.cross_fitting",
        list(cross_fitting.get("outer_fold_ids", [])) == [0, 1, 2, 3, 4]
        and int(cross_fitting.get("outer_router_train_folds", -1)) == 4
        and int(cross_fitting.get("outer_router_heldout_folds", -1)) == 1
        and cross_fitting.get("nested_threshold_recomputation") is True
        and int(cross_fitting.get("nested_router_train_threshold_folds", -1)) == 3
        and int(cross_fitting.get("outer_heldout_threshold_folds", -1)) == 4
        and cross_fitting.get("reuse_exp058_duplicate_component_partition") is True
        and cross_fitting.get("restore_exp058_source_order") is True,
    )
    threshold_settings = config["thresholds"]
    checks.add(
        "config.thresholds",
        threshold_settings.get("calibrator") == "identity_for_m1_and_m3"
        and float(threshold_settings.get("grid_start", math.nan)) == 0.05
        and float(threshold_settings.get("grid_end", math.nan)) == 0.95
        and float(threshold_settings.get("grid_step", math.nan)) == 0.01
        and tolerance == 1e-12
        and (
            not is_replication(config)
            or threshold_settings.get("probability_source") == "direct_sigmoid_of_raw_oof_logits"
        ),
    )
    target_contract = config["target_contract"]
    checks.add(
        "config.target_contract",
        target_contract.get("unit") == "whole_six_bit_vector"
        and target_contract.get("positive") == "m3_row_hamming_loss_strictly_lower_than_m1"
        and target_contract.get("tie_policy") == "m1"
        and target_contract.get("exp059_oracle_array_used_as_formal_target") is False,
    )
    feature_settings = config["feature_contract"]
    checks.add(
        "config.features",
        tuple(feature_settings.get("ordered_features", [])) == FEATURE_NAMES
        and int(feature_settings.get("feature_count", -1)) == len(FEATURE_NAMES),
    )
    router_settings = config["router"]
    checks.add(
        "config.router",
        list(router_settings.get("policies", [])) == list(POLICY_ORDER)
        and router_settings.get("logistic_regression") == expected_logistic
        and router_settings.get("hyperparameter_search") is False
        and int(router_settings.get("random_routing_repetitions", -1)) == 100
        and int(router_settings.get("random_routing_seed", -1)) == 20260817,
    )
    checks.add(
        "config.call_rates",
        [float(value) for value in config.get("call_rates", [])]
        == [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0],
    )
    checks.add(
        "config.bootstrap",
        config["bootstrap"].get("unit") == "duplicate_component"
        and int(config["bootstrap"].get("repetitions", -1)) == 2000
        and int(config["bootstrap"].get("seed", -1)) == 20260817
        and config["bootstrap"].get("interval") == "percentile_95",
    )
    checks.add(
        "config.primary_gate",
        not is_replication(config)
        or (
            config["gate"].get("primary_policy") == "logistic_router"
            and float(config["gate"].get("primary_nominal_call_rate", -1)) == 0.15
            and config["gate"].get("replication_pass_rule") == "primary_policy_only"
            and float(config["gate"].get("maximum_hamming_loss_increase", -1)) == 1e-12
        ),
    )
    checks.add(
        "config.risk_coverage",
        coverage_values(config) == [1.0, 0.95, 0.9, 0.8, 0.7, 0.6],
    )
    authorization = config["authorization"]
    checks.add("authorization.formal_router_training", authorization.get("formal_router_training") is True)
    checks.add("authorization.formal_result_computation", authorization.get("formal_result_computation") is True)
    for key in ("validation_access", "test_access", "model_loading_or_forward", "raw_text_access"):
        checks.add(f"authorization.{key}_false", authorization.get(key) is False)
    for section in ("implementation", "prerequisites", "input"):
        record_count = 0
        for record in iter_records(config.get(section, {})):
            require_record(record)
            record_count += 1
        checks.add(f"config.{section}_records_frozen", record_count > 0, {"record_count": record_count})

    if is_replication(config):
        oof_verification = json.loads(
            find_prerequisite(config, "oof_verification").read_text(encoding="utf-8")
        )
        exp059_run = json.loads(
            find_prerequisite(config, "exp059_run").read_text(encoding="utf-8")
        )
        exp059_verification = json.loads(
            find_prerequisite(config, "exp059_verification").read_text(encoding="utf-8")
        )
        calibration = json.loads(
            find_prerequisite(config, "exp059_calibration_parameters").read_text(encoding="utf-8")
        )
        checks.add(
            "prerequisite.oof_passed",
            verification_passed(oof_verification)
            and identity_matches(oof_verification, config)
            and oof_verification.get("verified_artifacts", {}).get("paired_oof_private")
            == config["input"]["paired_oof"],
        )
        checks.add(
            "prerequisite.exp059_passed",
            verification_passed(exp059_verification)
            and identity_matches(exp059_verification, config)
            and identity_matches(exp059_run, config)
            and exp059_run.get("status") in {"CompletedAwaitingVerification", "Passed"},
        )
        checks.add(
            "prerequisite.calibration_provenance",
            all(
                calibration.get(key) == value
                for key, value in {
                    "experiment_id": experiment_id(config),
                    "run_id": run_id(config),
                    "attempt_id": attempt_id(config),
                    "model_seed": model_seed(config),
                }.items()
            ),
        )
        checks.add(
            "prerequisite.router_replication_calibration",
            replication_calibration_contract_matches(calibration),
        )
    else:
        exp058_verification = json.loads(
            find_prerequisite(config, "exp058_verification", "exp058_final_verification").read_text(encoding="utf-8")
        )
        exp059_verification = json.loads(
            find_prerequisite(config, "exp059_verification", "exp059_final_verification").read_text(encoding="utf-8")
        )
        preflight_verification = json.loads(
            find_prerequisite(config, "exp060_preflight_verification", "preflight_verification").read_text(encoding="utf-8")
        )
        calibration = json.loads(
            find_prerequisite(config, "exp059_calibration_parameters", "calibration_parameters").read_text(encoding="utf-8")
        )
        checks.add(
            "prerequisite.exp058_passed",
            exp058_verification.get("experiment_id") == "EXP-058"
            and verification_passed(exp058_verification),
        )
        checks.add(
            "prerequisite.exp059_passed",
            exp059_verification.get("experiment_id") == "EXP-059"
            and verification_passed(exp059_verification),
        )
        checks.add(
            "prerequisite.exp060_preflight_passed",
            preflight_verification.get("experiment_id") == EXPERIMENT_ID
            and preflight_verification.get("rq_id") == RQ_ID
            and verification_passed(preflight_verification),
        )
        execution_claims = preflight_verification.get("execution_claims", {})
        checks.add(
            "prerequisite.exp060_preflight_independent",
            preflight_verification.get("runner_imported") is False
            and isinstance(execution_claims, dict)
            and bool(execution_claims)
            and not any(bool(value) for value in execution_claims.values()),
            {"claim_count": len(execution_claims) if isinstance(execution_claims, dict) else 0},
        )
    families = calibration.get("families", {})
    selected_calibrators = {
        family: families.get(family, {}).get("selected_calibrator") for family in ("m1", "m3")
    }
    selected_temperatures = {
        family: families.get(family, {}).get("final_temperature") for family in ("m1", "m3")
    }
    if is_replication(config):
        diagnostics_valid = all(
            selected_calibrators[family] in {"identity", "temperature"}
            and isinstance(selected_temperatures[family], (int, float))
            and math.isfinite(float(selected_temperatures[family]))
            and float(selected_temperatures[family]) > 0.0
            for family in ("m1", "m3")
        )
        checks.add("prerequisite.calibration_diagnostics", diagnostics_valid)
    else:
        checks.add(
            "prerequisite.identity_calibration",
            selected_calibrators == {"m1": "identity", "m3": "identity"},
            {"identity_count": sum(value == "identity" for value in selected_calibrators.values())},
        )
        checks.add(
            "prerequisite.identity_temperature",
            selected_temperatures == {"m1": 1.0, "m3": 1.0},
            {"one_count": sum(float(value) == 1.0 for value in selected_temperatures.values())},
        )

    input_path = require_record(config["input"]["paired_oof"])
    checks.add(
        "input.private_permissions",
        not input_path.is_symlink()
        and mode(input_path) == 0o600
        and not input_path.parent.is_symlink()
        and mode(input_path.parent) == 0o700,
        {"file_mode": oct(mode(input_path)), "parent_mode": oct(mode(input_path.parent))},
    )
    input_hash_before = sha256(input_path)
    with np.load(input_path, allow_pickle=False) as archive:
        data = {name: np.array(archive[name], copy=True) for name in archive.files}
    validate_input(checks, data, config)
    state: dict[str, Any] | None = None
    try:
        state = build_expected_state(data, config)
        checks.add("recomputation.completed", True)
    except Exception as error:
        checks.add(
            "recomputation.completed",
            False,
            {"error_type": type(error).__name__, "message_sha256": hashlib.sha256(str(error).encode()).hexdigest()},
        )

    run_path = run_dir / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    actual_public_artifacts = {path.name for path in run_dir.iterdir()}
    checks.add(
        "public.artifact_set",
        actual_public_artifacts == EXPECTED_PUBLIC_ARTIFACTS,
        {
            "actual_count": len(actual_public_artifacts),
            "expected_count": len(EXPECTED_PUBLIC_ARTIFACTS),
            "missing_count": len(EXPECTED_PUBLIC_ARTIFACTS - actual_public_artifacts),
            "extra_count": len(actual_public_artifacts - EXPECTED_PUBLIC_ARTIFACTS),
        },
    )
    checks.add(
        "run.identity",
        (
            identity_matches(run, config)
            if is_replication(config)
            else run.get("experiment_id") == EXPERIMENT_ID and run.get("rq_id") == RQ_ID
        ),
    )
    checks.add(
        "run.schema",
        run.get("schema_version")
        == ("exp-router-formal-run-v2" if is_replication(config) else "exp-060-formal-run-v1"),
    )
    checks.add("run.tier", run.get("tier") == "Major system experiment")
    checks.add("run.stage", run.get("stage") == config.get("stage"))
    checks.add("run.status", run.get("status") == "CompletedAwaitingVerification")
    if is_replication(config):
        checks.add("run.config", run.get("config") == artifact(config_path))
    checks.add("run.rows", run.get("rows") == 3360)
    checks.add("run.folds", run.get("folds") == 5)
    checks.add("run.components", run.get("component_count") == 3277)
    split_access = run.get("split_access", {})
    checks.add("run.train_oof_only", split_access.get("accessed_splits") == ["train-oof"])
    checks.add("run.no_validation", split_access.get("validation_accessed") is False)
    checks.add("run.no_test_inputs", split_access.get("test_inputs_accessed") is False)
    checks.add("run.no_test_labels", split_access.get("test_labels_accessed") is False)
    execution_flags = run.get("execution_flags", {})
    checks.add(
        "run.no_model_forward",
        execution_flags.get("model_loaded_or_forward_run") is False,
    )
    checks.add(
        "run.no_raw_text",
        execution_flags.get("raw_text_accessed") is False,
    )
    checks.add(
        "run.no_validation_or_test_execution",
        execution_flags.get("validation_accessed") is False
        and execution_flags.get("test_accessed") is False,
    )
    checks.add(
        "run.router_performed",
        execution_flags.get("nested_threshold_recomputation") is True
        and execution_flags.get("scaler_and_router_fitted") is True
        and execution_flags.get("router_results_computed") is True
        and execution_flags.get("component_bootstrap_computed") is True,
    )
    run_input = run.get("input_before", run.get("input"))
    checks.add("run.input_before", run_input == artifact(input_path))
    checks.add("run.input_after", run.get("input_sha256_after") == input_hash_before)
    checks.add(
        "run.source_order",
        run.get("source_order_sha256")
        == config["data"].get("source_order_sha256", EXPECTED_SOURCE_ORDER_SHA256),
    )
    expected_run_schema = [
        {
            "array_name": name,
            "shape": list(expected_paired_schema()[name][0]),
            "dtype": expected_paired_schema()[name][1],
            "fortran_order": False,
        }
        for name in sorted(expected_paired_schema())
    ]
    checks.add("run.input_schema", run.get("input_schema") == expected_run_schema)
    if state is not None:
        checks.add(
            "run.decision",
            run.get("decision") == state["selected"]["overall"]["decision"],
        )
    checks.add(
        "run.claim_boundary",
        run.get("claim_boundary") == config.get("claim_boundary"),
        {
            "actual_sha256": hashlib.sha256(
                str(run.get("claim_boundary", "")).encode("utf-8")
            ).hexdigest(),
            "expected_sha256": hashlib.sha256(
                str(config.get("claim_boundary", "")).encode("utf-8")
            ).hexdigest(),
        },
    )

    private_path = private_dir / "router-oof.npz"
    checks.add(
        "private.exists",
        private_path.is_file() and not private_path.is_symlink(),
    )
    if private_path.is_file() and state is not None:
        with np.load(private_path, allow_pickle=False) as archive:
            private_actual = {name: np.array(archive[name], copy=True) for name in archive.files}
        compare_private_arrays(checks, private_actual, state["private_arrays"], tolerance)
        recorded_private = run.get("private_output")
        if recorded_private is None:
            recorded_private = run.get("artifacts", {}).get("router_oof_private")
        checks.add("run.private_output", recorded_private == artifact(private_path))

    expected_json: dict[str, dict[str, Any]] = {}
    expected_csv: dict[str, list[dict[str, Any]]] = {}
    if state is not None:
        risk_rows, retention_rows = risk_and_retention_rows(state, data, config)
        expected_json = {
            "feature-contract.json": feature_contract(config),
            "router-discrimination.json": router_discrimination(state, config),
            "selected-operating-point.json": state["selected"],
            "bootstrap.json": bootstrap_result(state, data, config),
        }
        expected_csv = {
            "fold-summary.csv": state["fold_rows"],
            "call-rate-performance.csv": state["call_rows"],
            "policy-comparisons.csv": policy_comparison_rows(state, config),
            "random-routing.csv": random_routing_rows(state, data, config),
            "routed-risk-coverage.csv": risk_rows,
            "positive-label-retention.csv": retention_rows,
        }
    for filename, expected in expected_json.items():
        path = run_dir / filename
        checks.add(f"public.{filename}.exists", path.is_file())
        if path.is_file():
            actual = json.loads(path.read_text(encoding="utf-8"))
            compare_tree(checks, f"public.{filename}", actual, expected, tolerance)
            violations = public_sensitive_paths(actual)
            checks.add(
                f"public.{filename}.privacy", not violations, {"violation_count": len(violations)}
            )
    for filename, expected in expected_csv.items():
        path = run_dir / filename
        checks.add(f"public.{filename}.exists", path.is_file())
        if path.is_file():
            compare_csv(checks, f"public.{filename}", path, expected, tolerance)

    report_path = run_dir / "REPORT.md"
    checks.add("public.report.exists", report_path.is_file())
    if report_path.is_file():
        report = report_path.read_text(encoding="utf-8")
        checks.add("public.report.identity", experiment_id(config) in report)
        checks.add("public.report.claim_boundary", "train-OOF" in report and "test" in report)
        if state is not None:
            report_expected = expected_report(
                state["selected"], expected_json["bootstrap.json"], config
            )
            checks.add(
                "public.report.contents",
                report == report_expected,
                {
                    "actual_bytes": len(report.encode("utf-8")),
                    "expected_bytes": len(report_expected.encode("utf-8")),
                    "actual_sha256": hashlib.sha256(report.encode("utf-8")).hexdigest(),
                    "expected_sha256": hashlib.sha256(report_expected.encode("utf-8")).hexdigest(),
                },
            )
    figures = sorted(run_dir.glob("*.png"))
    checks.add(
        "public.figures.present",
        {path.name for path in figures}
        == {"call-rate-performance.png", "routed-risk-coverage.png"},
        {"count": len(figures)},
    )
    for figure in figures:
        try:
            width, height = png_dimensions(figure)
            checks.add(
                f"public.figure.{figure.name}",
                width == 1440 and height == 900,
                {"width": width, "height": height},
            )
        except (OSError, ValueError) as error:
            checks.add(
                f"public.figure.{figure.name}",
                False,
                {"error_type": type(error).__name__},
            )
    if state is not None:
        try:
            with tempfile.TemporaryDirectory(prefix="exp060-verify-figures-") as temporary:
                expected_figures = render_expected_figures(
                    Path(temporary),
                    state["call_rows"],
                    expected_csv["routed-risk-coverage.csv"],
                    config,
                )
                actual_figures = {path.name: path for path in figures}
                for name, expected_path in expected_figures.items():
                    if name not in actual_figures:
                        checks.add(f"public.figure.{name}.rgba", False, {"missing": True})
                        continue
                    try:
                        actual_rgba = decoded_png_rgba(actual_figures[name])
                        expected_rgba = decoded_png_rgba(expected_path)
                        shapes_match = actual_rgba.shape == expected_rgba.shape
                        mismatch_count = (
                            int(np.sum(actual_rgba != expected_rgba)) if shapes_match else None
                        )
                        checks.add(
                            f"public.figure.{name}.rgba",
                            shapes_match and mismatch_count == 0,
                            {
                                "actual_shape": list(actual_rgba.shape),
                                "expected_shape": list(expected_rgba.shape),
                                "channel_mismatch_count": mismatch_count,
                            },
                        )
                    except (OSError, ValueError) as error:
                        checks.add(
                            f"public.figure.{name}.rgba",
                            False,
                            {"error_type": type(error).__name__},
                        )
        except Exception as error:
            checks.add(
                "public.figures.independent_render",
                False,
                {"error_type": type(error).__name__},
            )

    public_output_records = run.get("public_outputs", {})
    recorded_paths: set[str] = set()
    for name, record in public_output_records.items():
        try:
            path = require_record(record)
            checks.add(f"run.public_output.{name}", path.is_file() and artifact(path) == record)
            recorded_paths.add(str(path.resolve()))
        except (KeyError, OSError, ValueError) as error:
            checks.add(
                f"run.public_output.{name}", False, {"error_type": type(error).__name__}
            )
    recorded_public_names = EXPECTED_PUBLIC_ARTIFACTS - {"run.json", "frozen-sources"}
    required_public_paths = {
        str((run_dir / filename).resolve()) for filename in recorded_public_names
    }
    checks.add(
        "run.public_outputs.complete",
        required_public_paths == recorded_paths,
        {
            "missing_count": len(required_public_paths - recorded_paths),
            "extra_count": len(recorded_paths - required_public_paths),
        },
    )

    frozen_sources = run.get("frozen_sources", run.get("source_artifacts", {}))
    expected_frozen_keys = {"config", *config["implementation"].keys()}
    checks.add(
        "run.frozen_sources.keys",
        set(frozen_sources) == expected_frozen_keys,
        {
            "actual_count": len(frozen_sources),
            "expected_count": len(expected_frozen_keys),
            "missing_count": len(expected_frozen_keys - set(frozen_sources)),
            "extra_count": len(set(frozen_sources) - expected_frozen_keys),
        },
    )
    recorded_frozen_paths: set[str] = set()
    for name, record in frozen_sources.items():
        if name not in expected_frozen_keys:
            continue
        frozen_path = require_record(record)
        source_path = config_path if name == "config" else require_record(config["implementation"][name])
        recorded_frozen_paths.add(str(frozen_path.resolve()))
        checks.add(
            f"run.frozen_source.{name}",
            frozen_path.parent == run_dir / "frozen-sources"
            and not frozen_path.is_symlink()
            and frozen_path.read_bytes() == source_path.read_bytes(),
            {"bytes": frozen_path.stat().st_size},
        )
    frozen_dir = run_dir / "frozen-sources"
    actual_frozen_paths = {
        str(path.resolve()) for path in frozen_dir.iterdir() if path.is_file()
    } if frozen_dir.is_dir() else set()
    checks.add(
        "run.frozen_sources.complete",
        actual_frozen_paths == recorded_frozen_paths
        and all(path.is_file() for path in frozen_dir.iterdir()) if frozen_dir.is_dir() else False,
        {
            "actual_count": len(actual_frozen_paths),
            "recorded_count": len(recorded_frozen_paths),
        },
    )

    scan_public_artifacts(checks, run_dir, data["sample_ids"], data["component_ids"])
    verify_modes(checks, run_dir, private_dir)
    resources = run.get("resources", {})
    checks.add(
        "resource.formal_wall",
        float(resources.get("wall_seconds", math.inf))
        <= float(config["resources"].get("formal_wall_seconds", 1800)),
        {"wall_seconds": resources.get("wall_seconds")},
    )
    checks.add(
        "resource.formal_memory",
        float(resources.get("peak_process_rss_gb", math.inf))
        <= float(config["resources"].get("formal_peak_memory_gb", 4.0)),
        {"peak_process_rss_gb": resources.get("peak_process_rss_gb")},
    )
    checks.add("resource.api_cost", resources.get("api_cost_usd") == 0)
    checks.add("resource.gpu_cost", resources.get("gpu_cost_usd") == 0)
    checks.add("resource.model_forward_runs", resources.get("model_forward_runs", 0) == 0)
    input_hash_after = sha256(input_path)
    checks.add("input.unchanged", input_hash_after == input_hash_before)
    elapsed = time.monotonic() - started
    verification_budget = float(config["resources"]["verification_wall_seconds"])
    checks.add(
        "resource.verification_wall",
        elapsed <= verification_budget,
        {"wall_seconds": float(elapsed), "budget_seconds": verification_budget},
    )
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_gb = peak_rss / 1e9 if os.uname().sysname == "Darwin" else peak_rss * 1024 / 1e9
    checks.add(
        "resource.verification_memory",
        peak_gb <= float(config["resources"]["peak_memory_gb"]),
        {"peak_process_rss_gb": float(peak_gb)},
    )

    result = {
        "schema_version": "exp-router-formal-verification-v2" if is_replication(config) else "exp-060-formal-verification-v1",
        "experiment_id": experiment_id(config),
        "rq_id": RQ_ID,
        **({
            "stage": config["stage"],
            "run_id": run_id(config),
            "attempt_id": attempt_id(config),
            "model_seed": model_seed(config),
            "seed_contract": seed_contract(config),
            "config": artifact(config_path),
        } if is_replication(config) else {}),
        "scope": "final",
        "status": "Passed" if not checks.failed else "Failed",
        "runner_imported": False,
        "verified_at_utc": utc_now(),
        "passed_count": len(checks.rows) - len(checks.failed),
        "failed_count": len(checks.failed),
        "checks": checks.rows,
        "independence": {
            "runner_imported": False,
            "raw_exp058_recomputation": True,
            "nested_thresholds_recomputed": state is not None,
            "scalers_and_routers_refit": state is not None,
            "public_and_private_outputs_recomputed": state is not None,
        },
        "verified_artifacts": {
            "config": artifact(config_path),
            "run": artifact(run_path),
            "input": artifact(input_path),
            "private_router_oof": artifact(private_path) if private_path.is_file() else None,
        },
        "split_access": {
            "accessed_splits": ["train-oof"],
            "validation_accessed": False,
            "test_inputs_accessed": False,
            "test_labels_accessed": False,
            "raw_text_accessed": False,
            "model_loaded_or_forward_run": False,
        },
        "claim_boundary": (
            "Independent verification of frozen train-OOF routing evidence only; no validation, "
            "test, deployment-generalization, or mechanism claim."
        ),
    }
    atomic_json(output_path, result)
    write_summary(summary_path, result)
    return result


def replication_primary_gate_result(
    selected: dict[str, Any], config: dict[str, Any]
) -> bool:
    if not is_replication(config):
        raise PermissionError("Primary replication gate applies only to config-v2")
    policies = selected.get("policies", {})
    if not isinstance(policies, dict) or set(policies) != set(DEPLOYABLE_POLICIES):
        raise ValueError("Replication selected-policy inventory drift")
    primary = policies.get("logistic_router", {})
    candidate = primary.get("candidate", {})
    passed = primary.get("passed")
    if not isinstance(passed, bool):
        raise ValueError("Replication primary gate must be boolean")
    expected_decision = "Pass" if passed else "Fail"
    overall = selected.get("overall", {})
    identity_ok = (
        selected.get("schema_version") == "exp-router-selected-operating-point-v2"
        and selected.get("experiment_id") == experiment_id(config)
        and selected.get("run_id") == run_id(config)
        and selected.get("attempt_id") == attempt_id(config)
        and selected.get("model_seed") == model_seed(config)
        and selected.get("primary_policy") == "logistic_router"
        and float(selected.get("primary_nominal_call_rate", -1)) == 0.15
    )
    primary_ok = (
        primary.get("evidence_role") == "primary"
        and float(candidate.get("target_call_rate", -1)) == 0.15
        and all(
            policies[policy].get("evidence_role") == "descriptive_only"
            and policies[policy].get("passed") is False
            for policy in ("m1_max_entropy", "m1_threshold_proximity")
        )
    )
    overall_ok = (
        overall.get("decision") == expected_decision
        and overall.get("selected_policy") == "logistic_router"
        and overall.get("selected_candidate") == candidate
    )
    if not identity_ok or not primary_ok or not overall_ok:
        raise ValueError("Frozen logistic_router@15% primary result drift")
    return passed


def verify_completion(config_path: Path) -> dict[str, Any]:
    config_path = require_canonical_config_path(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not is_replication(config):
        raise PermissionError("Router completion verification applies only to config-v2")
    validate_replication_identity(config)
    outputs = expected_replication_outputs(config)
    run_dir = resolve_output(outputs["public_attempt_dir"]) / "router"
    private_dir = resolve_output(outputs["private_attempt_dir"]) / "router"
    completion_path = run_dir / "router-complete.json"
    run_path = run_dir / "run.json"
    verification_path = run_dir / "verification.json"
    selected_path = run_dir / "selected-operating-point.json"
    private_path = private_dir / "router-oof.npz"
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    run = json.loads(run_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    primary_gate_passed = replication_primary_gate_result(selected, config)
    expected_decision = "Pass" if primary_gate_passed else "Fail"
    checks = Checks()
    checks.add("completion.identity", identity_matches(completion, config))
    checks.add("completion.schema", completion.get("schema_version") == "exp-router-completion-v2")
    checks.add("completion.status", completion.get("status") == "Complete")
    checks.add("completion.decision", completion.get("decision") == expected_decision)
    checks.add(
        "completion.primary_gate_passed",
        completion.get("primary_gate_passed") is primary_gate_passed,
    )
    checks.add("completion.public_privacy", not public_sensitive_paths(completion))
    checks.add(
        "completion.run_result",
        run.get("status") == "CompletedAwaitingVerification"
        and identity_matches(run, config)
        and run.get("decision") == expected_decision
        and run.get("public_outputs", {}).get("selected_operating_point_json")
        == artifact(selected_path),
    )
    verified = verification.get("verified_artifacts", {})
    checks.add(
        "completion.final_passed",
        verification.get("status") == "Passed"
        and int(verification.get("failed_count", -1)) == 0
        and identity_matches(verification, config)
        and verified.get("config") == artifact(config_path)
        and verified.get("run") == artifact(run_path)
        and verified.get("private_router_oof") == artifact(private_path),
    )
    artifacts = completion.get("artifacts", {})
    expected_artifact_keys = {
        "config",
        "run",
        "selected_operating_point",
        "final_verification",
        "private_router_oof",
    }
    checks.add("completion.artifact_inventory", set(artifacts) == expected_artifact_keys)
    checks.add("completion.config", artifacts.get("config") == artifact(config_path))
    checks.add("completion.run", artifacts.get("run") == artifact(run_path))
    checks.add(
        "completion.selected_operating_point",
        artifacts.get("selected_operating_point") == artifact(selected_path),
    )
    checks.add(
        "completion.verification",
        artifacts.get("final_verification") == artifact(verification_path),
    )
    checks.add(
        "completion.private_router_oof",
        artifacts.get("private_router_oof") == artifact(private_path),
    )
    checks.add("completion.selection_not_written", not os.path.lexists(resolve_output(outputs["selection_record"])))
    result = {
        "schema_version": "exp-router-completion-verification-v2",
        "experiment_id": experiment_id(config),
        "stage": config["stage"],
        "run_id": run_id(config),
        "attempt_id": attempt_id(config),
        "model_seed": model_seed(config),
        "scope": "completion",
        "verified_at_utc": utc_now(),
        "status": "Passed" if not checks.failed else "Failed",
        "passed_count": len(checks.rows) - len(checks.failed),
        "failed_count": len(checks.failed),
        "checks": checks.rows,
        "independence": {"runner_imported": False, "completion_rehashed": True},
    }
    if checks.failed:
        raise RuntimeError(f"Router completion verification failed: {len(checks.failed)} checks")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--scope", choices=("final", "completion"), default="final")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify(args.config) if args.scope == "final" else verify_completion(args.config)
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
