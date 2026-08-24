#!/usr/bin/env python3
"""Run the frozen EXP-060 pre-Qwen deployable-router analysis.

The runner consumes only the verified EXP-058 train-OOF artifact.  It never loads
an upstream model, raw text, validation, or test data.  Public files contain only
aggregate records; all row-level values are written to one private mode-0600 NPZ.
"""

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
import sys
import tempfile
import time
from typing import Any, Iterable
import zipfile

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
POLICY_ORDER = ("m1_max_entropy", "m1_threshold_proximity", "logistic_router")
UNCERTAINTY_ORDER = ("mean_entropy", "max_entropy", "margin")
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-060-pre-qwen-router.json"
EXPECTED_PUBLIC_RUN_DIR = (
    "experiments/stack-overflow-emotion-gold/oof-router/runs/exp-060-pre-qwen-router"
)
EXPECTED_PRIVATE_RUN_DIR = (
    "experiments/stack-overflow-emotion-gold/oof-router/private/exp-060-pre-qwen-router"
)
EXPECTED_SOURCE_ORDER_SHA256 = "c9e4bd1eb2bdbb33c833234754c493b8818aa6c610acaf88659ae74fa94848a3"
EXPECTED_INPUT_PATH = (
    "experiments/stack-overflow-emotion-gold/oof-router/private/"
    "exp-058-paired-oof-production/paired-oof.npz"
)
EXPECTED_INPUT_BYTES = 307755
EXPECTED_INPUT_SHA256 = "e8d2efde7ca62b3f09519390a6305d09ba0f3ea1dfbecbe8a11dbe4ffd482bfc"
EXPECTED_IMPLEMENTATION_PATHS = {
    "protocol": "experiments/stack-overflow-emotion-gold/protocols/exp-060-pre-qwen-deployable-router.md",
    "runner": "experiments/stack-overflow-emotion-gold/oof-router/run_exp060_router.py",
    "verifier": "experiments/stack-overflow-emotion-gold/oof-router/verify_exp060_router.py",
    "tests": "experiments/stack-overflow-emotion-gold/oof-router/tests/test_exp060_router.py",
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
    "sample_id",
    "sample_ids",
    "component_id",
    "component_ids",
    "fold_id",
    "fold_ids",
    "gold",
    "logit",
    "logits",
    "probability",
    "probabilities",
    "feature",
    "features",
    "feature_matrix",
    "target",
    "targets",
    "router_targets",
    "route_score",
    "route_scores",
    "route_mask",
    "route_masks",
    "prediction",
    "predictions",
    "raw_text",
    "text",
}
FOLD_SUMMARY_COLUMNS = (
    "outer_fold_index", "router_train_rows", "heldout_rows", "router_train_components",
    "heldout_components", "router_train_target_positive", "router_train_target_prevalence",
    "heldout_target_positive", "heldout_target_prevalence", "router_pr_auc", "router_roc_auc",
    "router_precision_at_0_5", "router_recall_at_0_5", "router_n_iter", "router_converged",
    "coefficient_l2_norm",
)
CALL_RATE_COLUMNS = (
    "policy", "target_call_rate", "actual_call_rate", "routed_rows", "qwen_calls_per_1000",
    "macro_f1", "five_label_macro_f1", "micro_f1", "hamming_loss", "subset_accuracy",
    "f1_love", "f1_joy", "f1_surprise", "f1_anger", "f1_sadness", "f1_fear",
)
POLICY_COMPARISON_COLUMNS = (
    "target_call_rate", "r4_actual_call_rate", "best_heuristic_policy",
    "best_heuristic_actual_call_rate", "r4_macro_f1", "best_heuristic_macro_f1",
    "macro_f1_delta", "r4_five_label_macro_f1", "best_heuristic_five_label_macro_f1",
    "five_label_macro_f1_delta", "r4_hamming_loss", "best_heuristic_hamming_loss",
    "hamming_loss_delta",
)
RANDOM_ROUTING_COLUMNS = (
    "policy", "target_call_rate", "matched_policy_actual_call_rate",
    "random_actual_call_rate_mean", "random_actual_call_rate_min", "random_actual_call_rate_max",
    "macro_f1_mean", "macro_f1_p05", "macro_f1_p50", "macro_f1_p95",
    "five_label_macro_f1_mean", "five_label_macro_f1_p05", "five_label_macro_f1_p50",
    "five_label_macro_f1_p95", "hamming_loss_mean", "hamming_loss_p05",
    "hamming_loss_p50", "hamming_loss_p95",
)
RISK_COVERAGE_COLUMNS = (
    "policy", "uncertainty_method", "target_coverage", "actual_coverage", "accepted_rows",
    "hamming_risk", "subset_error", "micro_f1", "macro_f1", "five_label_macro_f1",
)
RETENTION_COLUMNS = (
    "policy", "uncertainty_method", "target_coverage", "label", "positive_support",
    "retained_positive", "positive_retention",
)
CSV_ALLOWLISTS = {
    "fold-summary.csv": FOLD_SUMMARY_COLUMNS,
    "call-rate-performance.csv": CALL_RATE_COLUMNS,
    "policy-comparisons.csv": POLICY_COMPARISON_COLUMNS,
    "random-routing.csv": RANDOM_ROUTING_COLUMNS,
    "routed-risk-coverage.csv": RISK_COVERAGE_COLUMNS,
    "positive-label-retention.csv": RETENTION_COLUMNS,
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


def identity_provenance(config: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "experiment_id": experiment_id(config),
        "rq_id": str(config.get("rq_id", RQ_ID)),
        "stage": str(config["stage"]),
    }
    if is_replication(config):
        payload.update({
            "run_id": run_id(config),
            "attempt_id": attempt_id(config),
            "model_seed": model_seed(config),
            "seed_contract": seed_contract(config),
            "seed_contract_sha256": canonical_digest(seed_contract(config)),
        })
    return payload


def resolve_project(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Project-relative path escapes project root: {value}")
    return path


def resolve_output(value: str) -> Path:
    relative = Path(str(value))
    if relative.is_absolute() or not relative.parts or any(part in ("", ".", "..") for part in relative.parts):
        raise ValueError(f"Output path is not a normalized project-relative path: {value}")
    lexical = PROJECT_ROOT / relative
    cursor = PROJECT_ROOT
    for part in relative.parts:
        cursor = cursor / part
        if os.path.lexists(cursor) and cursor.is_symlink():
            raise ValueError(f"Output path traverses a symbolic link: {value}")
    resolved = lexical.resolve()
    if not resolved.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Output path escapes project root: {value}")
    return resolved


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(resolved)


def display_repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT.resolve()))
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
        raise ValueError(f"Artifact record path must stay project-relative: {relative}")
    lexical = PROJECT_ROOT / relative
    candidate = PROJECT_ROOT
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError(f"Artifact record path traverses a symbolic link: {relative}")
    path = resolve_project(str(relative))
    if not path.is_file() or lexical.is_symlink():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Frozen artifact drift: {path}")
    return path


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def atomic_csv(path: Path, rows: list[dict[str, Any]], columns: tuple[str, ...]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    if any(tuple(row) != columns for row in rows):
        raise ValueError(f"CSV schema drift: {path.name}")
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def atomic_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    if path.parent.exists() and stat.S_IMODE(path.parent.stat().st_mode) != 0o700:
        raise PermissionError("Private EXP-060 directory is not mode 0700")
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


def stable_sigmoid(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    result = np.empty_like(array)
    positive = array >= 0
    result[positive] = 1.0 / (1.0 + np.exp(-array[positive]))
    exp_values = np.exp(array[~positive])
    result[~positive] = exp_values / (1.0 + exp_values)
    return result


def classification_metrics(gold: np.ndarray, prediction: np.ndarray) -> dict[str, Any]:
    y = np.asarray(gold, dtype=np.uint8)
    pred = np.asarray(prediction, dtype=np.uint8)
    if y.shape != pred.shape or y.ndim != 2 or y.shape[1] != len(LABEL_ORDER) or not len(y):
        raise ValueError("Classification metric shape mismatch")
    if not np.all(np.isin(y, [0, 1])) or not np.all(np.isin(pred, [0, 1])):
        raise ValueError("Classification metrics require binary matrices")
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
            "precision": float(precision), "recall": float(recall), "f1": float(f1),
            "support": support, "predicted_positive": int(np.sum(pred[:, index] == 1)),
        }
        f1_values.append(float(f1))
        tp_total += tp
        fp_total += fp
        fn_total += fn
    micro_precision = tp_total / (tp_total + fp_total) if tp_total + fp_total else 0.0
    micro_recall = tp_total / (tp_total + fn_total) if tp_total + fn_total else 0.0
    micro_f1 = (
        2.0 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if micro_precision + micro_recall else 0.0
    )
    five = [value for index, value in enumerate(f1_values) if index != 2]
    subset_accuracy = float(np.mean(np.all(y == pred, axis=1)))
    return {
        "rows": int(len(y)), "macro_f1": float(np.mean(f1_values)),
        "five_label_macro_f1": float(np.mean(five)), "micro_f1": float(micro_f1),
        "hamming_loss": float(np.mean(y != pred)), "subset_accuracy": subset_accuracy,
        "subset_error": float(1.0 - subset_accuracy), "per_label": per_label,
    }


def select_threshold(probabilities: np.ndarray, gold: np.ndarray, grid: list[float]) -> dict[str, Any]:
    values = np.asarray(probabilities, dtype=np.float64)
    if values.shape != np.asarray(gold).shape or values.ndim != 2 or not grid:
        raise ValueError("Threshold selection inputs are invalid")
    candidates: list[dict[str, Any]] = []
    for threshold in grid:
        metrics = classification_metrics(gold, (values >= float(threshold)).astype(np.uint8))
        candidates.append({
            "threshold": float(threshold), "macro_f1": metrics["macro_f1"],
            "hamming_loss": metrics["hamming_loss"],
        })
    best_macro = max(row["macro_f1"] for row in candidates)
    tied = [row for row in candidates if abs(row["macro_f1"] - best_macro) <= 1e-12]
    best_hamming = min(row["hamming_loss"] for row in tied)
    tied = [row for row in tied if abs(row["hamming_loss"] - best_hamming) <= 1e-12]
    tied.sort(key=lambda row: (abs(row["threshold"] - 0.5), row["threshold"]))
    return tied[0]


def _binary_entropy(probabilities: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(probabilities, dtype=np.float64), 1e-15, 1.0 - 1e-15)
    return -(clipped * np.log(clipped) + (1.0 - clipped) * np.log1p(-clipped))


def build_pre_qwen_features(
    m1_probabilities: np.ndarray,
    m1_thresholds: np.ndarray,
    character_lengths: np.ndarray,
    m1_token_lengths: np.ndarray,
) -> tuple[np.ndarray, tuple[str, ...]]:
    probabilities = np.asarray(m1_probabilities, dtype=np.float64)
    thresholds = np.asarray(m1_thresholds, dtype=np.float64)
    characters = np.asarray(character_lengths, dtype=np.float64)
    tokens = np.asarray(m1_token_lengths, dtype=np.float64)
    if probabilities.ndim != 2 or probabilities.shape[1] != len(LABEL_ORDER):
        raise ValueError("M1 probability matrix must have six columns")
    rows = len(probabilities)
    if thresholds.shape != (rows,) or characters.shape != (rows,) or tokens.shape != (rows,):
        raise ValueError("Threshold and length vectors must align with M1 rows")
    if not np.all(np.isfinite(probabilities)) or np.any((probabilities < 0) | (probabilities > 1)):
        raise ValueError("M1 probabilities must be finite values in [0, 1]")
    if not np.all(np.isfinite(thresholds)) or np.any((thresholds <= 0) | (thresholds >= 1)):
        raise ValueError("M1 thresholds must be finite values in (0, 1)")
    if not np.all(np.isfinite(characters)) or not np.all(np.isfinite(tokens)):
        raise ValueError("Length features must be finite")
    if np.any(characters < 0) or np.any(tokens < 0):
        raise ValueError("Length features must be non-negative")
    entropy = _binary_entropy(probabilities)
    matrix = np.column_stack([
        probabilities,
        np.mean(entropy, axis=1),
        np.max(entropy, axis=1),
        np.min(np.abs(probabilities - thresholds[:, None]), axis=1),
        np.sum(probabilities >= thresholds[:, None], axis=1),
        np.max(probabilities, axis=1),
        np.min(probabilities, axis=1),
        characters,
        tokens,
    ]).astype(np.float64, copy=False)
    if matrix.shape != (rows, len(FEATURE_NAMES)) or not np.all(np.isfinite(matrix)):
        raise ValueError("Pre-Qwen feature matrix contract failed")
    return matrix, FEATURE_NAMES


def build_router_target(
    m1_prediction: np.ndarray, m3_prediction: np.ndarray, gold: np.ndarray
) -> np.ndarray:
    m1 = np.asarray(m1_prediction, dtype=np.uint8)
    m3 = np.asarray(m3_prediction, dtype=np.uint8)
    labels = np.asarray(gold, dtype=np.uint8)
    if m1.shape != m3.shape or m1.shape != labels.shape or m1.ndim != 2:
        raise ValueError("Prediction and gold matrices must align")
    return (np.mean(m3 != labels, axis=1) < np.mean(m1 != labels, axis=1)).astype(np.uint8)


def score_cutoff(meta_train_scores: np.ndarray, target_rate: float) -> float:
    scores = np.asarray(meta_train_scores, dtype=np.float64)
    if scores.ndim != 1 or not scores.size or not np.all(np.isfinite(scores)):
        raise ValueError("Route scores must be a non-empty finite vector")
    if not 0.0 <= target_rate <= 1.0:
        raise ValueError("Target call rate must be in [0, 1]")
    if target_rate == 0.0:
        return math.inf
    if target_rate == 1.0:
        return -math.inf
    count = max(1, int(math.ceil(target_rate * len(scores))))
    return float(np.sort(scores)[::-1][count - 1])


def apply_score_cutoff(scores: np.ndarray, cutoff: float) -> np.ndarray:
    values = np.asarray(scores, dtype=np.float64)
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("Held-out route scores must be a finite vector")
    return (values >= cutoff).astype(np.uint8)


def component_aware_random_mask(
    component_ids: np.ndarray, target_count: int, seed: int | np.random.SeedSequence
) -> np.ndarray:
    components = np.asarray(component_ids)
    if components.ndim != 1 or not len(components):
        raise ValueError("Component IDs must be a non-empty vector")
    if not 0 <= int(target_count) <= len(components):
        raise ValueError("Target row count is out of range")
    groups: dict[str, list[int]] = {}
    for row_index, component in enumerate(components.tolist()):
        groups.setdefault(str(component), []).append(row_index)
    keys = sorted(groups)
    rng = np.random.default_rng(seed)
    permuted_keys = [keys[index] for index in rng.permutation(len(keys))]
    sizes = [len(groups[key]) for key in permuted_keys]
    target = int(target_count)
    reachable = 1
    history: list[int] = []
    used_sizes: list[int] = []
    for size in sizes:
        history.append(reachable)
        used_sizes.append(size)
        reachable |= reachable << size
        if (reachable >> target) & 1:
            break
    chosen_total: int | None = None
    for delta in range(len(components) + 1):
        lower = target - delta
        upper = target + delta
        if lower >= 0 and ((reachable >> lower) & 1):
            chosen_total = lower
            break
        if upper <= len(components) and ((reachable >> upper) & 1):
            chosen_total = upper
            break
    if chosen_total is None:
        raise RuntimeError("Component subset-sum failed")
    selected_positions: set[int] = set()
    remaining = chosen_total
    for position in range(len(used_sizes) - 1, -1, -1):
        before = history[position]
        if (before >> remaining) & 1:
            continue
        size = used_sizes[position]
        if remaining < size or not ((before >> (remaining - size)) & 1):
            raise RuntimeError("Component subset reconstruction failed")
        selected_positions.add(position)
        remaining -= size
    if remaining != 0:
        raise RuntimeError("Component subset reconstruction did not reach zero")
    selected_keys = {permuted_keys[position] for position in selected_positions}
    mask = np.asarray([str(value) in selected_keys for value in components.tolist()], dtype=np.uint8)
    for key, indices in groups.items():
        if len(np.unique(mask[np.asarray(indices, dtype=np.int64)])) != 1:
            raise RuntimeError(f"Component was split: {key}")
    return mask


def safe_router_metrics(
    target: np.ndarray, scores: np.ndarray, route_mask: np.ndarray
) -> dict[str, Any]:
    labels = np.asarray(target, dtype=np.uint8)
    values = np.asarray(scores, dtype=np.float64)
    predicted = np.asarray(route_mask, dtype=np.uint8)
    if labels.ndim != 1 or values.shape != labels.shape or predicted.shape != labels.shape:
        raise ValueError("Router metric vectors must align")
    if not np.all(np.isin(labels, [0, 1])) or not np.all(np.isin(predicted, [0, 1])):
        raise ValueError("Router targets and masks must be binary")
    if not np.all(np.isfinite(values)):
        raise ValueError("Router scores must be finite")
    tp = int(np.sum((labels == 1) & (predicted == 1)))
    fp = int(np.sum((labels == 0) & (predicted == 1)))
    fn = int(np.sum((labels == 1) & (predicted == 0)))
    tn = int(np.sum((labels == 0) & (predicted == 0)))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    two_classes = len(np.unique(labels)) == 2
    return {
        "rows": int(len(labels)), "positive_targets": int(np.sum(labels)),
        "target_prevalence": float(np.mean(labels)),
        "pr_auc": float(average_precision_score(labels, values)) if two_classes else None,
        "roc_auc": float(roc_auc_score(labels, values)) if two_classes else None,
        "precision_at_0_5": float(precision), "recall_at_0_5": float(recall),
        "predicted_positive": int(np.sum(predicted)), "true_positive": tp,
        "false_positive": fp, "false_negative": fn, "true_negative": tn,
    }


def choose_candidate(rows: list[dict[str, Any]], maximum_call_rate: float) -> dict[str, Any] | None:
    eligible = [row for row in rows if float(row["actual_call_rate"]) <= maximum_call_rate + 1e-12]
    if not eligible:
        return None
    eligible.sort(key=lambda row: (
        -float(row["six_label_macro_f1"]), float(row["hamming_loss"]),
        float(row["actual_call_rate"]), float(row["target_call_rate"]),
    ))
    return eligible[0]


def routed_uncertainty_scores(
    route_mask: np.ndarray,
    m1_probabilities: np.ndarray,
    m3_probabilities: np.ndarray,
    m1_thresholds: np.ndarray,
    m3_thresholds: np.ndarray,
) -> dict[str, np.ndarray]:
    route = np.asarray(route_mask, dtype=bool)
    m1 = np.asarray(m1_probabilities, dtype=np.float64)
    m3 = np.asarray(m3_probabilities, dtype=np.float64)
    t1 = np.asarray(m1_thresholds, dtype=np.float64)
    t3 = np.asarray(m3_thresholds, dtype=np.float64)
    if m1.shape != m3.shape or m1.ndim != 2 or m1.shape[0] != len(route):
        raise ValueError("Routed uncertainty probability shapes do not align")
    if t1.shape != route.shape or t3.shape != route.shape:
        raise ValueError("Routed uncertainty thresholds do not align")
    selected = np.where(route[:, None], m3, m1)
    thresholds = np.where(route, t3, t1)
    entropy = _binary_entropy(selected)
    return {
        "mean_entropy": np.mean(entropy, axis=1),
        "max_entropy": np.max(entropy, axis=1),
        "margin": -np.min(np.abs(selected - thresholds[:, None]), axis=1),
    }


def component_groups(component_ids: np.ndarray) -> list[np.ndarray]:
    groups: dict[str, list[int]] = {}
    for index, component in enumerate(np.asarray(component_ids).tolist()):
        groups.setdefault(str(component), []).append(index)
    return [np.asarray(groups[key], dtype=np.int64) for key in sorted(groups)]


def component_bootstrap_indices(
    groups: list[np.ndarray], rng: np.random.Generator
) -> np.ndarray:
    sampled = rng.integers(0, len(groups), size=len(groups))
    return np.concatenate([groups[index] for index in sampled])


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
                "shape": list(shape), "dtype": str(dtype), "fortran_order": bool(fortran),
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
        {"array_name": name, **schema[name]}
        for name in sorted(schema)
    ]


def dependency_versions() -> dict[str, str]:
    versions = {"python": platform.python_version()}
    for name in ("numpy", "scikit-learn", "matplotlib"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    status_rows = subprocess.run(
        ["git", "status", "--short"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    return {"commit": commit, "dirty": bool(status_rows), "dirty_path_count": len(status_rows)}


def peak_rss_gb() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / 1e9 if platform.system() == "Darwin" else value * 1024 / 1e9


def _record_by_names(section: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    for name in names:
        record = section.get(name)
        if isinstance(record, dict) and {"path", "bytes", "sha256"}.issubset(record):
            return record
    raise KeyError(f"Missing frozen prerequisite; expected one of {names}")


def _load_frozen_json(record: dict[str, Any]) -> dict[str, Any]:
    return json.loads(require_record(record).read_text(encoding="utf-8"))


def _verification_passed(payload: dict[str, Any], name: str) -> None:
    failed = payload.get("failed_count")
    if failed is None and isinstance(payload.get("checks"), dict):
        failed = payload["checks"].get("failed")
    if payload.get("status") != "Passed" or int(failed or 0) != 0:
        raise ValueError(f"{name} verification is not Passed")


def _identity_matches(payload: dict[str, Any], config: dict[str, Any]) -> bool:
    return (
        payload.get("experiment_id") == experiment_id(config)
        and payload.get("run_id") == run_id(config)
        and payload.get("attempt_id") == attempt_id(config)
        and payload.get("model_seed") == model_seed(config)
    )


def exp059_identity_matches(payload: dict[str, Any], config: dict[str, Any]) -> bool:
    return (
        payload.get("experiment_id") == "EXP-059"
        and payload.get("replication_parent_experiment_id") == experiment_id(config)
        and payload.get("run_id") == run_id(config)
        and payload.get("attempt_id") == attempt_id(config)
        and payload.get("model_seed") == model_seed(config)
        and payload.get("seed_contract") == seed_contract(config)
    )


def _expected_replication_outputs(config: dict[str, Any]) -> dict[str, str]:
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
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(config.get("stage", ""))):
        raise ValueError("Replication stage must be a normalized identifier")
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
    expected_outputs = _expected_replication_outputs(config)
    if config.get("outputs") != expected_outputs:
        raise ValueError("Router config-v2 output paths are not canonical")
    for value in expected_outputs.values():
        resolve_output(value)
    expected_input = f"{expected_outputs['private_attempt_dir']}/paired-oof.npz"
    if set(config.get("input", {})) != REPLICATION_INPUT_KEYS:
        raise ValueError("Router config-v2 input inventory drift")
    if config.get("input", {}).get("paired_oof", {}).get("path") != expected_input:
        raise ValueError("Router paired OOF must come from the matching private attempt")
    prerequisites = config.get("prerequisites")
    if not isinstance(prerequisites, dict) or set(prerequisites) != REPLICATION_REQUIRED_PREREQUISITES:
        raise ValueError("Router config-v2 prerequisite inventory drift")
    public_attempt = resolve_output(expected_outputs["public_attempt_dir"])
    for name in REPLICATION_REQUIRED_PREREQUISITES:
        record = prerequisites[name]
        record_path = resolve_output(str(record.get("path", "")))
        if not record_path.is_relative_to(public_attempt):
            raise ValueError(f"{name} is not inside the matching public attempt")


def replication_calibration_contract_matches(payload: dict[str, Any]) -> bool:
    return payload.get("router_replication_calibration") == REPLICATION_CALIBRATION_CONTRACT


def _validate_legacy_archive(config_path: Path, config: dict[str, Any]) -> None:
    run_dir = resolve_project(EXPECTED_PUBLIC_RUN_DIR)
    run_path = run_dir / "run.json"
    verification_path = run_dir / "verification.json"
    if not run_path.is_file() or not verification_path.is_file():
        raise PermissionError("Legacy EXP-060 fallback requires the sealed verified archive")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if (
        run.get("experiment_id") != EXPERIMENT_ID
        or run.get("status") != "CompletedAwaitingVerification"
        or verification.get("experiment_id") != EXPERIMENT_ID
        or verification.get("status") != "Passed"
        or int(verification.get("failed_count", -1)) != 0
    ):
        raise PermissionError("Legacy EXP-060 archive is not sealed and Passed")
    frozen = run.get("frozen_sources")
    if not isinstance(frozen, dict) or set(frozen) != {"config", *config["implementation"]}:
        raise ValueError("Legacy EXP-060 frozen-source inventory drift")
    frozen_config = require_record(frozen["config"])
    if frozen_config.parent != run_dir / "frozen-sources" or sha256(frozen_config) != sha256(config_path):
        raise ValueError("Legacy EXP-060 frozen config drift")
    for name, expected in config["implementation"].items():
        archived = require_record(frozen[name])
        if (
            archived.parent != run_dir / "frozen-sources"
            or int(frozen[name]["bytes"]) != int(expected["bytes"])
            or frozen[name]["sha256"] != expected["sha256"]
        ):
            raise ValueError(f"Legacy EXP-060 frozen source drift: {name}")


def _validate_upstream_semantics(config: dict[str, Any]) -> None:
    prerequisites = config["prerequisites"]
    if is_replication(config):
        paired_record = config["input"]["paired_oof"]
        oof = _load_frozen_json(prerequisites["oof_verification"])
        exp059_run = _load_frozen_json(prerequisites["exp059_run"])
        exp059 = _load_frozen_json(prerequisites["exp059_verification"])
        calibration = _load_frozen_json(prerequisites["exp059_calibration_parameters"])
        _verification_passed(oof, "seed-specific OOF")
        _verification_passed(exp059, "seed-specific EXP-059")
        if not _identity_matches(oof, config):
            raise ValueError("Seed-specific OOF verification identity drift")
        if not exp059_identity_matches(exp059, config):
            raise ValueError("Seed-specific EXP-059 verification identity drift")
        if not exp059_identity_matches(exp059_run, config) or exp059_run.get("status") not in {
            "CompletedAwaitingVerification", "Passed"
        }:
            raise ValueError("Seed-specific EXP-059 run identity/status drift")
        verified_oof = oof.get("verified_artifacts", {}).get("paired_oof_private")
        if verified_oof != paired_record:
            raise ValueError("Router paired OOF is not the OOF-verifier-bound artifact")
        if not exp059_identity_matches(calibration, config):
            raise ValueError("EXP-059 calibration identity drift")
        if not replication_calibration_contract_matches(calibration):
            raise ValueError("EXP-059 replication identity-probability contract drift")
        return

    exp058 = _load_frozen_json(_record_by_names(
        prerequisites, ("exp058_verification", "exp_058_verification")
    ))
    exp059 = _load_frozen_json(_record_by_names(
        prerequisites, ("exp059_verification", "exp_059_verification")
    ))
    preflight = _load_frozen_json(_record_by_names(
        prerequisites,
        ("exp060_preflight_verification", "preflight_verification", "exp_060_preflight_verification"),
    ))
    _verification_passed(exp058, "EXP-058")
    _verification_passed(exp059, "EXP-059")
    _verification_passed(preflight, "EXP-060 preflight")
    if preflight.get("runner_imported") is not False:
        raise ValueError("EXP-060 preflight verifier independence drift")
    claims = preflight.get("execution_claims", {})
    if any(bool(value) for value in claims.values()):
        raise ValueError("EXP-060 preflight unexpectedly computed a formal result")
    calibration = _load_frozen_json(_record_by_names(
        prerequisites,
        ("exp059_calibration_parameters", "calibration_parameters", "exp_059_calibration_parameters"),
    ))
    for family in ("m1", "m3"):
        values = calibration.get("families", {}).get(family, {})
        if values.get("selected_calibrator") != "identity" or float(values.get("final_temperature", -1)) != 1.0:
            raise ValueError(f"EXP-059 {family} identity calibration drift")


def _guard_record_paths(config: dict[str, Any]) -> None:
    forbidden_parts = {"validation", "test", "raw-text", "raw_text", "checkpoints", "checkpoint"}
    for section in ("implementation", "prerequisites", "input"):
        for record in iter_records(config.get(section, {})):
            parts = {part.lower() for part in Path(str(record["path"])).parts}
            if parts & forbidden_parts:
                raise ValueError(f"Forbidden EXP-060 path in config: {record['path']}")


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    schema = config.get("schema_version")
    if schema not in (LEGACY_CONFIG_SCHEMA, REPLICATION_CONFIG_SCHEMA):
        raise ValueError("Unexpected router config schema")
    if schema == LEGACY_CONFIG_SCHEMA:
        if config.get("experiment_id") != EXPERIMENT_ID or config.get("rq_id") != RQ_ID:
            raise ValueError("EXP-060 config identity drift")
    else:
        if config.get("rq_id") != RQ_ID:
            raise ValueError("Replication RQ identity drift")
        validate_replication_identity(config)
    authorization = config["authorization"]
    if not authorization.get("formal_router_training") or not authorization.get("formal_result_computation"):
        raise PermissionError("Formal EXP-060 router/result computation is not authorized")
    for key in ("validation_access", "test_access", "model_loading_or_forward", "raw_text_access"):
        if authorization.get(key) is not False:
            raise ValueError(f"EXP-060 must explicitly forbid {key}")
    if tuple(config["data"]["label_order"]) != LABEL_ORDER:
        raise ValueError("EXP-060 label order drift")
    if int(config["data"]["rows"]) != 3360 or int(config["data"]["duplicate_components"]) != 3277:
        raise ValueError("EXP-060 data count drift")
    if list(config["cross_fitting"]["outer_fold_ids"]) != [0, 1, 2, 3, 4]:
        raise ValueError("EXP-060 outer-fold contract drift")
    if not config["cross_fitting"]["nested_threshold_recomputation"]:
        raise ValueError("Nested threshold recomputation is required")
    if int(config["cross_fitting"]["nested_router_train_threshold_folds"]) != 3:
        raise ValueError("Inner threshold fit must use three folds")
    if int(config["cross_fitting"]["outer_heldout_threshold_folds"]) != 4:
        raise ValueError("Outer-heldout threshold fit must use four folds")
    if tuple(config["feature_contract"]["ordered_features"]) != FEATURE_NAMES:
        raise ValueError("EXP-060 feature order drift")
    if int(config["feature_contract"]["feature_count"]) != len(FEATURE_NAMES):
        raise ValueError("EXP-060 feature count drift")
    if config["thresholds"]["calibrator"] != "identity_for_m1_and_m3":
        raise ValueError("EXP-060 calibration contract drift")
    if is_replication(config) and config["thresholds"].get("probability_source") != "direct_sigmoid_of_raw_oof_logits":
        raise ValueError("Replication probabilities must be recomputed directly from raw OOF logits")
    if float(config["thresholds"].get("numeric_tolerance", -1)) != 1e-12:
        raise ValueError("Router numeric tolerance drift")
    if config["target_contract"]["unit"] != "whole_six_bit_vector":
        raise ValueError("EXP-060 target unit drift")
    if config["target_contract"].get("exp059_oracle_array_used_as_formal_target") is not False:
        raise ValueError("EXP-059 oracle is forbidden as the formal target")
    logistic = config["router"]["logistic_regression"]
    expected_logistic = {
        "penalty": "l2", "C": 1.0, "class_weight": "balanced", "solver": "liblinear",
        "max_iter": 1000, "random_state": 42,
    }
    if any(logistic.get(key) != value for key, value in expected_logistic.items()):
        raise ValueError("EXP-060 logistic-regression contract drift")
    if config["router"].get("hyperparameter_search") is not False:
        raise ValueError("EXP-060 hyperparameter search is forbidden")
    if [float(value) for value in config["call_rates"]] != [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0]:
        raise ValueError("EXP-060 call-rate grid drift")
    if int(config["bootstrap"]["repetitions"]) != 2000 or config["bootstrap"]["unit"] != "duplicate_component":
        raise ValueError("EXP-060 bootstrap contract drift")
    if int(config["bootstrap"]["seed"]) != 20260817:
        raise ValueError("EXP-060 bootstrap seed drift")
    if (
        int(config["router"].get("random_routing_repetitions", -1)) != 100
        or int(config["router"].get("random_routing_seed", -1)) != 20260817
    ):
        raise ValueError("EXP-060 component-aware random-routing contract drift")
    if float(config["gate"].get("maximum_hamming_loss_increase", -1)) != 1e-12:
        raise ValueError("EXP-060 Hamming tolerance drift")
    if is_replication(config) and (
        config["gate"].get("primary_policy") != "logistic_router"
        or float(config["gate"].get("primary_nominal_call_rate", -1)) != 0.15
        or config["gate"].get("replication_pass_rule") != "primary_policy_only"
    ):
        raise ValueError("Replication must use only logistic_router at nominal 15% as its primary gate")
    for name, expected_path in EXPECTED_IMPLEMENTATION_PATHS.items():
        if config["implementation"][name].get("path") != expected_path:
            raise ValueError(f"EXP-060 {name} implementation path drift")
    if resolve_project(config["implementation"]["runner"]["path"]) != Path(__file__).resolve():
        raise ValueError("The executing EXP-060 runner is not the frozen runner")
    input_record = _record_by_names(config["input"], ("paired_oof",))
    if not is_replication(config):
        if (
            input_record.get("path") != EXPECTED_INPUT_PATH
            or int(input_record.get("bytes", -1)) != EXPECTED_INPUT_BYTES
            or input_record.get("sha256") != EXPECTED_INPUT_SHA256
        ):
            raise ValueError("EXP-060 paired-OOF input identity drift")
        public_value = config["outputs"].get("formal_run_dir", config["outputs"].get("public_run_dir"))
        private_value = config["outputs"].get("formal_private_dir", config["outputs"].get("private_run_dir"))
        if public_value != EXPECTED_PUBLIC_RUN_DIR or private_value != EXPECTED_PRIVATE_RUN_DIR:
            raise ValueError("EXP-060 canonical output-path drift")
    _guard_record_paths(config)
    if not is_replication(config):
        _validate_legacy_archive(path, config)
        config["_archive_only"] = True
        return config
    for section in ("implementation", "prerequisites", "input"):
        for record in iter_records(config.get(section, {})):
            require_record(record)
    _validate_upstream_semantics(config)
    violations = public_sensitive_paths(config)
    if violations:
        raise ValueError(f"Formal config violates public privacy contract: {violations}")
    return config


def freeze_sources(run_dir: Path, config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    frozen_dir = run_dir / "frozen-sources"
    frozen_dir.mkdir(mode=0o755)
    sources: dict[str, Path] = {"config": config_path}
    for name, record in config["implementation"].items():
        sources[name] = require_record(record)
    records: dict[str, Any] = {}
    for name, source in sources.items():
        target = frozen_dir / ("config.json" if name == "config" else source.name)
        shutil.copy2(source, target)
        records[name] = artifact(target)
    return records


def validate_loaded_input(data: dict[str, np.ndarray], config: dict[str, Any]) -> None:
    if set(data) != set(expected_input_schema()):
        raise ValueError("EXP-058 paired input key drift")
    if len(set(data["sample_ids"].tolist())) != 3360:
        raise ValueError("EXP-058 sample IDs are not unique")
    source_hash = canonical_digest(data["sample_ids"].tolist())
    expected_source = config["data"].get("source_order_sha256", EXPECTED_SOURCE_ORDER_SHA256)
    if source_hash != expected_source or (
        not is_replication(config) and source_hash != EXPECTED_SOURCE_ORDER_SHA256
    ):
        raise ValueError("EXP-058 source-order drift")
    if not np.all(np.isin(data["gold"], [0, 1])):
        raise ValueError("Gold matrix is not binary")
    for family in ("m1", "m3"):
        if not np.all(np.isfinite(data[f"{family}_logits"])):
            raise ValueError(f"Non-finite {family} logits")
        hashes = data[f"{family}_fold_run_sha256"].tolist()
        if len(set(hashes)) != 5 or any(len(value) != 64 for value in hashes):
            raise ValueError(f"{family} fold-run hash contract drift")
    if np.any(data["character_lengths"] < 0) or np.any(data["m1_token_lengths"] < 0):
        raise ValueError("Negative pre-Qwen length")
    folds = [int(value) for value in config["cross_fitting"]["outer_fold_ids"]]
    if sorted(np.unique(data["fold_ids"]).tolist()) != folds:
        raise ValueError("Fold ID drift")
    for fold in folds:
        if int(np.sum(data["fold_ids"] == fold)) != 672:
            raise ValueError(f"Fold {fold} row-count drift")
    component_folds: dict[str, set[int]] = {}
    for component, fold in zip(data["component_ids"].tolist(), data["fold_ids"].tolist()):
        component_folds.setdefault(str(component), set()).add(int(fold))
    if len(component_folds) != 3277 or any(len(values) != 1 for values in component_folds.values()):
        raise ValueError("Duplicate-component fold integrity drift")


def _threshold_grid(config: dict[str, Any]) -> list[float]:
    values = config["thresholds"]
    start, end, step = float(values["grid_start"]), float(values["grid_end"]), float(values["grid_step"])
    count = int(round((end - start) / step)) + 1
    grid = [round(start + index * step, 12) for index in range(count)]
    if grid != [round(0.05 + index * 0.01, 12) for index in range(91)]:
        raise ValueError("Threshold grid must be 0.05..0.95 step 0.01")
    return grid


def _route_prediction(
    m1_prediction: np.ndarray, m3_prediction: np.ndarray, route_mask: np.ndarray
) -> np.ndarray:
    route = np.asarray(route_mask, dtype=bool)
    if route.shape != (len(m1_prediction),) or m1_prediction.shape != m3_prediction.shape:
        raise ValueError("Whole-vector routing inputs do not align")
    return np.where(route[:, None], m3_prediction, m1_prediction).astype(np.uint8)


def _call_rate_row(
    policy: str,
    target_rate: float,
    route_mask: np.ndarray,
    gold: np.ndarray,
    prediction: np.ndarray,
) -> dict[str, Any]:
    metrics = classification_metrics(gold, prediction)
    actual_rate = float(np.mean(route_mask))
    return {
        "policy": policy,
        "target_call_rate": float(target_rate),
        "actual_call_rate": actual_rate,
        "routed_rows": int(np.sum(route_mask)),
        "qwen_calls_per_1000": float(actual_rate * 1000.0),
        "macro_f1": metrics["macro_f1"],
        "five_label_macro_f1": metrics["five_label_macro_f1"],
        "micro_f1": metrics["micro_f1"],
        "hamming_loss": metrics["hamming_loss"],
        "subset_accuracy": metrics["subset_accuracy"],
        "f1_love": metrics["per_label"]["love"]["f1"],
        "f1_joy": metrics["per_label"]["joy"]["f1"],
        "f1_surprise": metrics["per_label"]["surprise"]["f1"],
        "f1_anger": metrics["per_label"]["anger"]["f1"],
        "f1_sadness": metrics["per_label"]["sadness"]["f1"],
        "f1_fear": metrics["per_label"]["fear"]["f1"],
    }


def _candidate_sort_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
    macro = float(row.get("six_label_macro_f1", row["macro_f1"]))
    return (-macro, float(row["hamming_loss"]), float(row["actual_call_rate"]), float(row["target_call_rate"]))


def _gate_candidate(
    candidate: dict[str, Any], baseline: dict[str, Any], config: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, bool], bool]:
    gate = config["gate"]
    non_surprise = [label for label in LABEL_ORDER if label != "surprise"]
    label_gain = max(
        float(candidate[f"f1_{label}"]) - float(baseline["per_label"][label]["f1"])
        for label in non_surprise
    )
    gains = {
        "six_label_macro_f1_gain": float(candidate["macro_f1"] - baseline["macro_f1"]),
        "five_label_macro_f1_gain": float(
            candidate["five_label_macro_f1"] - baseline["five_label_macro_f1"]
        ),
        "hamming_loss_delta": float(candidate["hamming_loss"] - baseline["hamming_loss"]),
        "maximum_non_surprise_label_f1_gain": float(label_gain),
    }
    gates = {
        "maximum_actual_qwen_call_rate": (
            float(candidate["actual_call_rate"])
            <= float(gate["maximum_actual_qwen_call_rate"]) + 1e-12
        ),
        "minimum_six_label_macro_f1_gain": (
            gains["six_label_macro_f1_gain"] + 1e-12
            >= float(gate["minimum_six_label_macro_f1_gain"])
        ),
        "minimum_five_label_macro_f1_gain": (
            gains["five_label_macro_f1_gain"] + 1e-12
            >= float(gate["minimum_five_label_macro_f1_gain"])
        ),
        "hamming_loss_not_worse": (
            gains["hamming_loss_delta"] <= float(gate["maximum_hamming_loss_increase"])
        ),
        "minimum_non_surprise_label_f1_gain": (
            gains["maximum_non_surprise_label_f1_gain"] + 1e-12
            >= float(gate["minimum_one_non_surprise_label_f1_gain"])
        ),
    }
    return gains, gates, all(gates.values())


def analyze_arrays(data: dict[str, np.ndarray], config: dict[str, Any]) -> dict[str, Any]:
    """Compute EXP-060 from already-loaded arrays without writing any file."""
    fold_values = [int(value) for value in config["cross_fitting"]["outer_fold_ids"]]
    fold_to_position = {fold: index for index, fold in enumerate(fold_values)}
    fold_ids = np.asarray(data["fold_ids"], dtype=np.int8)
    gold = np.asarray(data["gold"], dtype=np.uint8)
    component_ids = np.asarray(data["component_ids"])
    rows = len(gold)
    if len(fold_values) != 5 or sorted(np.unique(fold_ids).tolist()) != fold_values:
        raise ValueError("analyze_arrays requires the frozen five folds")
    m1_probabilities = stable_sigmoid(data["m1_logits"])
    m3_probabilities = stable_sigmoid(data["m3_logits"])
    grid = _threshold_grid(config)
    call_rates = [float(value) for value in config["call_rates"]]
    feature_count = len(FEATURE_NAMES)
    fold_count = len(fold_values)

    features = np.full((rows, feature_count), np.nan, dtype=np.float64)
    router_targets = np.full(rows, 255, dtype=np.uint8)
    m1_thresholds = np.full(rows, np.nan, dtype=np.float64)
    m3_thresholds = np.full(rows, np.nan, dtype=np.float64)
    m1_predictions = np.zeros_like(gold, dtype=np.uint8)
    m3_predictions = np.zeros_like(gold, dtype=np.uint8)
    nested_m1_thresholds = np.full((fold_count, fold_count), np.nan, dtype=np.float64)
    nested_m3_thresholds = np.full((fold_count, fold_count), np.nan, dtype=np.float64)
    route_scores = np.full((len(POLICY_ORDER), rows), np.nan, dtype=np.float64)
    route_masks = np.zeros((len(POLICY_ORDER), len(call_rates), rows), dtype=np.uint8)
    score_cutoffs = np.full(
        (len(POLICY_ORDER), len(call_rates), fold_count), np.nan, dtype=np.float64
    )
    scaler_mean = np.full((fold_count, feature_count), np.nan, dtype=np.float64)
    scaler_scale = np.full((fold_count, feature_count), np.nan, dtype=np.float64)
    router_coef = np.full((fold_count, feature_count), np.nan, dtype=np.float64)
    router_intercept = np.full(fold_count, np.nan, dtype=np.float64)
    router_n_iter = np.zeros(fold_count, dtype=np.int32)
    fold_rows: list[dict[str, Any]] = []
    fold_metrics: list[dict[str, Any]] = []

    logistic_config = config["router"]["logistic_regression"]
    for outer_fold in fold_values:
        outer_position = fold_to_position[outer_fold]
        outer_indices = np.flatnonzero(fold_ids == outer_fold)
        outer_train_mask = fold_ids != outer_fold
        router_train_features: list[np.ndarray] = []
        router_train_targets: list[np.ndarray] = []

        for inner_fold in fold_values:
            if inner_fold == outer_fold:
                continue
            fit_mask = outer_train_mask & (fold_ids != inner_fold)
            inner_indices = np.flatnonzero(fold_ids == inner_fold)
            m1_selection = select_threshold(m1_probabilities[fit_mask], gold[fit_mask], grid)
            m3_selection = select_threshold(m3_probabilities[fit_mask], gold[fit_mask], grid)
            m1_threshold = float(m1_selection["threshold"])
            m3_threshold = float(m3_selection["threshold"])
            inner_position = fold_to_position[inner_fold]
            nested_m1_thresholds[outer_position, inner_position] = m1_threshold
            nested_m3_thresholds[outer_position, inner_position] = m3_threshold
            inner_m1_prediction = (m1_probabilities[inner_indices] >= m1_threshold).astype(np.uint8)
            inner_m3_prediction = (m3_probabilities[inner_indices] >= m3_threshold).astype(np.uint8)
            inner_features, names = build_pre_qwen_features(
                m1_probabilities[inner_indices],
                np.full(len(inner_indices), m1_threshold, dtype=np.float64),
                data["character_lengths"][inner_indices],
                data["m1_token_lengths"][inner_indices],
            )
            if names != FEATURE_NAMES:
                raise RuntimeError("Feature order changed inside nested construction")
            inner_target = build_router_target(
                inner_m1_prediction, inner_m3_prediction, gold[inner_indices]
            )
            router_train_features.append(inner_features)
            router_train_targets.append(inner_target)

        train_features = np.concatenate(router_train_features, axis=0)
        train_target = np.concatenate(router_train_targets, axis=0)
        if len(np.unique(train_target)) != 2:
            raise RuntimeError(f"Outer fold {outer_fold} router-training target is single-class")

        m1_outer_selection = select_threshold(
            m1_probabilities[outer_train_mask], gold[outer_train_mask], grid
        )
        m3_outer_selection = select_threshold(
            m3_probabilities[outer_train_mask], gold[outer_train_mask], grid
        )
        m1_outer_threshold = float(m1_outer_selection["threshold"])
        m3_outer_threshold = float(m3_outer_selection["threshold"])
        nested_m1_thresholds[outer_position, outer_position] = m1_outer_threshold
        nested_m3_thresholds[outer_position, outer_position] = m3_outer_threshold
        outer_m1_prediction = (
            m1_probabilities[outer_indices] >= m1_outer_threshold
        ).astype(np.uint8)
        outer_m3_prediction = (
            m3_probabilities[outer_indices] >= m3_outer_threshold
        ).astype(np.uint8)
        outer_features, _ = build_pre_qwen_features(
            m1_probabilities[outer_indices],
            np.full(len(outer_indices), m1_outer_threshold, dtype=np.float64),
            data["character_lengths"][outer_indices],
            data["m1_token_lengths"][outer_indices],
        )
        outer_target = build_router_target(
            outer_m1_prediction, outer_m3_prediction, gold[outer_indices]
        )
        features[outer_indices] = outer_features
        router_targets[outer_indices] = outer_target
        m1_thresholds[outer_indices] = m1_outer_threshold
        m3_thresholds[outer_indices] = m3_outer_threshold
        m1_predictions[outer_indices] = outer_m1_prediction
        m3_predictions[outer_indices] = outer_m3_prediction

        scaler = StandardScaler()
        scaled_train = scaler.fit_transform(train_features)
        scaled_outer = scaler.transform(outer_features)
        router = LogisticRegression(
            penalty=logistic_config["penalty"], C=float(logistic_config["C"]),
            class_weight=logistic_config["class_weight"], solver=logistic_config["solver"],
            max_iter=int(logistic_config["max_iter"]),
            random_state=int(logistic_config["random_state"]),
        )
        router.fit(scaled_train, train_target)
        iterations = int(router.n_iter_[0])
        converged = iterations < int(logistic_config["max_iter"])
        if not converged:
            raise RuntimeError(f"Outer fold {outer_fold} logistic router did not converge")
        logistic_train_score = router.predict_proba(scaled_train)[:, 1]
        logistic_outer_score = router.predict_proba(scaled_outer)[:, 1]
        policy_train_scores = (
            train_features[:, FEATURE_NAMES.index("m1_max_binary_entropy")],
            -train_features[:, FEATURE_NAMES.index("m1_minimum_threshold_margin")],
            logistic_train_score,
        )
        policy_outer_scores = (
            outer_features[:, FEATURE_NAMES.index("m1_max_binary_entropy")],
            -outer_features[:, FEATURE_NAMES.index("m1_minimum_threshold_margin")],
            logistic_outer_score,
        )
        for policy_index, (train_score, outer_score) in enumerate(
            zip(policy_train_scores, policy_outer_scores)
        ):
            route_scores[policy_index, outer_indices] = outer_score
            for rate_index, target_rate in enumerate(call_rates):
                cutoff = score_cutoff(train_score, target_rate)
                score_cutoffs[policy_index, rate_index, outer_position] = cutoff
                route_masks[policy_index, rate_index, outer_indices] = apply_score_cutoff(
                    outer_score, cutoff
                )

        scaler_mean[outer_position] = scaler.mean_
        scaler_scale[outer_position] = scaler.scale_
        router_coef[outer_position] = router.coef_[0]
        router_intercept[outer_position] = router.intercept_[0]
        router_n_iter[outer_position] = iterations
        diagnostic = safe_router_metrics(
            outer_target, logistic_outer_score, (logistic_outer_score >= 0.5).astype(np.uint8)
        )
        fold_metrics.append(diagnostic)
        fold_rows.append({
            "outer_fold_index": outer_fold,
            "router_train_rows": int(len(train_target)),
            "heldout_rows": int(len(outer_indices)),
            "router_train_components": int(len(np.unique(component_ids[outer_train_mask]))),
            "heldout_components": int(len(np.unique(component_ids[outer_indices]))),
            "router_train_target_positive": int(np.sum(train_target)),
            "router_train_target_prevalence": float(np.mean(train_target)),
            "heldout_target_positive": int(np.sum(outer_target)),
            "heldout_target_prevalence": float(np.mean(outer_target)),
            "router_pr_auc": diagnostic["pr_auc"],
            "router_roc_auc": diagnostic["roc_auc"],
            "router_precision_at_0_5": diagnostic["precision_at_0_5"],
            "router_recall_at_0_5": diagnostic["recall_at_0_5"],
            "router_n_iter": iterations,
            "router_converged": converged,
            "coefficient_l2_norm": float(np.linalg.norm(router.coef_[0])),
        })

    finite_arrays = (
        features, m1_thresholds, m3_thresholds, nested_m1_thresholds, nested_m3_thresholds,
        route_scores, scaler_mean, scaler_scale, router_coef, router_intercept,
    )
    if any(not np.all(np.isfinite(array)) for array in finite_arrays):
        raise RuntimeError("Non-finite nested EXP-060 output")
    for rate_index, target_rate in enumerate(call_rates):
        cutoffs = score_cutoffs[:, rate_index, :]
        if target_rate == 0.0:
            valid_cutoffs = np.all(np.isposinf(cutoffs))
        elif target_rate == 1.0:
            valid_cutoffs = np.all(np.isneginf(cutoffs))
        else:
            valid_cutoffs = np.all(np.isfinite(cutoffs))
        if not valid_cutoffs:
            raise RuntimeError(f"Invalid score cutoffs for target rate {target_rate}")
    if np.any(router_targets == 255):
        raise RuntimeError("Router target source order was not fully restored")

    baseline_metrics = classification_metrics(gold, m1_predictions)
    call_rows: list[dict[str, Any]] = [
        _call_rate_row("m1_only", 0.0, np.zeros(rows, dtype=np.uint8), gold, m1_predictions),
        _call_rate_row("m3_only", 1.0, np.ones(rows, dtype=np.uint8), gold, m3_predictions),
    ]
    policy_internal_rows: dict[str, list[dict[str, Any]]] = {policy: [] for policy in POLICY_ORDER}
    for policy_index, policy in enumerate(POLICY_ORDER):
        for rate_index, target_rate in enumerate(call_rates):
            mask = route_masks[policy_index, rate_index]
            prediction = _route_prediction(m1_predictions, m3_predictions, mask)
            public_row = _call_rate_row(policy, target_rate, mask, gold, prediction)
            call_rows.append(public_row)
            policy_internal_rows[policy].append({
                **public_row,
                "six_label_macro_f1": public_row["macro_f1"],
                "_policy_index": policy_index,
                "_rate_index": rate_index,
            })

    maximum_rate = float(config["gate"]["maximum_actual_qwen_call_rate"])
    policy_records: dict[str, Any] = {}
    selected_internal: dict[str, dict[str, Any]] = {}
    passing: list[tuple[str, dict[str, Any]]] = []
    for policy in POLICY_ORDER:
        if is_replication(config):
            candidate = next(
                row for row in policy_internal_rows[policy]
                if float(row["target_call_rate"]) == 0.15
            )
        else:
            candidate = choose_candidate(policy_internal_rows[policy], maximum_rate)
        if candidate is None:
            raise RuntimeError(f"No <=20% candidate exists for {policy}")
        gains, gates, passed = _gate_candidate(candidate, baseline_metrics, config)
        selected_internal[policy] = candidate
        public_candidate = {
            key: value for key, value in candidate.items()
            if not key.startswith("_") and key != "six_label_macro_f1"
        }
        public_candidate.update(gains)
        primary_eligible = not is_replication(config) or policy == "logistic_router"
        policy_records[policy] = {
            "candidate": public_candidate,
            "gates": gates,
            "passed": bool(passed and primary_eligible),
            **({
                "diagnostic_gate_passed": bool(passed),
                "evidence_role": "primary" if primary_eligible else "descriptive_only",
            } if is_replication(config) else {}),
        }
        if passed and primary_eligible:
            passing.append((policy, candidate))
    precedence = {policy: index for index, policy in enumerate(POLICY_ORDER)}
    passing.sort(key=lambda item: (*_candidate_sort_key(item[1]), precedence[item[0]]))
    if is_replication(config):
        overall_policy = "logistic_router"
        overall_candidate = policy_records[overall_policy]["candidate"]
        overall_decision = "Pass" if policy_records[overall_policy]["passed"] else "Fail"
    else:
        overall_policy = passing[0][0] if passing else None
        overall_candidate = policy_records[overall_policy]["candidate"] if overall_policy else None
        overall_decision = "Pass" if overall_policy else "Stop router branch"
    selected_public = {
        "schema_version": (
            "exp-router-selected-operating-point-v2"
            if is_replication(config)
            else "exp-060-selected-operating-point-v1"
        ),
        "experiment_id": experiment_id(config),
        **({
            "run_id": run_id(config),
            "attempt_id": attempt_id(config),
            "model_seed": model_seed(config),
            "primary_policy": "logistic_router",
            "primary_nominal_call_rate": 0.15,
        } if is_replication(config) else {}),
        "baseline": baseline_metrics,
        "policies": policy_records,
        "overall": {
            "decision": overall_decision,
            "selected_policy": overall_policy,
            "selected_candidate": overall_candidate,
        },
    }

    policy_comparisons: list[dict[str, Any]] = []
    for rate_index, target_rate in enumerate(call_rates):
        r4 = policy_internal_rows["logistic_router"][rate_index]
        heuristics = [
            policy_internal_rows["m1_max_entropy"][rate_index],
            policy_internal_rows["m1_threshold_proximity"][rate_index],
        ]
        heuristics.sort(key=_candidate_sort_key)
        best = heuristics[0]
        policy_comparisons.append({
            "target_call_rate": target_rate,
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
        })

    overall_router = safe_router_metrics(
        router_targets, route_scores[2], (route_scores[2] >= 0.5).astype(np.uint8)
    )
    router_discrimination = {
        "schema_version": (
            "exp-router-discrimination-v2"
            if is_replication(config)
            else "exp-060-router-discrimination-v1"
        ),
        "experiment_id": experiment_id(config),
        "overall": overall_router,
        "fold_auc_undefined": {
            "pr_auc": int(sum(row["pr_auc"] is None for row in fold_metrics)),
            "roc_auc": int(sum(row["roc_auc"] is None for row in fold_metrics)),
        },
        "all_folds_converged": True,
    }

    private_arrays = {
        "sample_ids": np.asarray(data["sample_ids"]),
        "component_ids": component_ids,
        "fold_ids": fold_ids,
        "gold": gold,
        "features": features,
        "router_targets": router_targets,
        "nested_m1_thresholds": nested_m1_thresholds,
        "nested_m3_thresholds": nested_m3_thresholds,
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
    return {
        "private_arrays": private_arrays,
        "m1_probabilities": m1_probabilities,
        "m3_probabilities": m3_probabilities,
        "fold_rows": fold_rows,
        "router_discrimination": router_discrimination,
        "call_rows": call_rows,
        "policy_comparisons": policy_comparisons,
        "selected": selected_public,
        "selected_internal": selected_internal,
    }


def _distribution(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "mean": float(np.mean(array)),
        "p05": float(np.percentile(array, 5.0)),
        "p50": float(np.percentile(array, 50.0)),
        "p95": float(np.percentile(array, 95.0)),
        "minimum": float(np.min(array)),
        "maximum": float(np.max(array)),
    }


def random_routing_diagnostics(
    analysis: dict[str, Any], data: dict[str, np.ndarray], config: dict[str, Any]
) -> list[dict[str, Any]]:
    arrays = analysis["private_arrays"]
    fold_ids = arrays["fold_ids"]
    gold = arrays["gold"]
    component_ids = arrays["component_ids"]
    m1_prediction = arrays["m1_predictions"]
    m3_prediction = arrays["m3_predictions"]
    route_masks = arrays["route_masks"]
    fold_values = [int(value) for value in config["cross_fitting"]["outer_fold_ids"]]
    call_rates = [float(value) for value in config["call_rates"]]
    repetitions = int(config["router"]["random_routing_repetitions"])
    if repetitions != 100:
        raise ValueError("EXP-060 random-routing repetitions must be 100")
    base_seed = int(config["router"].get("random_routing_seed", 20260817))
    rows: list[dict[str, Any]] = []
    for policy_index, policy in enumerate(POLICY_ORDER):
        for rate_index, target_rate in enumerate(call_rates):
            metric_values = {
                "actual_rate": [], "macro_f1": [], "five_label_macro_f1": [], "hamming_loss": []
            }
            for repetition in range(repetitions):
                random_mask = np.zeros(len(gold), dtype=np.uint8)
                for fold in fold_values:
                    indices = np.flatnonzero(fold_ids == fold)
                    matched_count = int(np.sum(route_masks[policy_index, rate_index, indices]))
                    seed = np.random.SeedSequence(
                        [base_seed, policy_index, rate_index, int(fold), repetition]
                    )
                    random_mask[indices] = component_aware_random_mask(
                        component_ids[indices], matched_count, seed
                    )
                prediction = _route_prediction(m1_prediction, m3_prediction, random_mask)
                metrics = classification_metrics(gold, prediction)
                metric_values["actual_rate"].append(float(np.mean(random_mask)))
                metric_values["macro_f1"].append(metrics["macro_f1"])
                metric_values["five_label_macro_f1"].append(metrics["five_label_macro_f1"])
                metric_values["hamming_loss"].append(metrics["hamming_loss"])
            actual = _distribution(metric_values["actual_rate"])
            macro = _distribution(metric_values["macro_f1"])
            five = _distribution(metric_values["five_label_macro_f1"])
            hamming = _distribution(metric_values["hamming_loss"])
            rows.append({
                "policy": policy,
                "target_call_rate": target_rate,
                "matched_policy_actual_call_rate": float(
                    np.mean(route_masks[policy_index, rate_index])
                ),
                "random_actual_call_rate_mean": actual["mean"],
                "random_actual_call_rate_min": actual["minimum"],
                "random_actual_call_rate_max": actual["maximum"],
                "macro_f1_mean": macro["mean"],
                "macro_f1_p05": macro["p05"],
                "macro_f1_p50": macro["p50"],
                "macro_f1_p95": macro["p95"],
                "five_label_macro_f1_mean": five["mean"],
                "five_label_macro_f1_p05": five["p05"],
                "five_label_macro_f1_p50": five["p50"],
                "five_label_macro_f1_p95": five["p95"],
                "hamming_loss_mean": hamming["mean"],
                "hamming_loss_p05": hamming["p05"],
                "hamming_loss_p50": hamming["p50"],
                "hamming_loss_p95": hamming["p95"],
            })
    return rows


def _bootstrap_interval(values: list[float], point_estimate: float) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "point_estimate": float(point_estimate),
        "mean": float(np.mean(array)),
        "lower_95": float(np.percentile(array, 2.5)),
        "upper_95": float(np.percentile(array, 97.5)),
    }


def bootstrap_selected_candidates(
    analysis: dict[str, Any], data: dict[str, np.ndarray], config: dict[str, Any]
) -> dict[str, Any]:
    arrays = analysis["private_arrays"]
    gold = arrays["gold"]
    m1_prediction = arrays["m1_predictions"]
    m3_prediction = arrays["m3_predictions"]
    groups = component_groups(arrays["component_ids"])
    repetitions = int(config["bootstrap"]["repetitions"])
    base_seed = int(config["bootstrap"]["seed"])
    records: dict[str, Any] = {}
    for policy_index, policy in enumerate(POLICY_ORDER):
        candidate = analysis["selected_internal"][policy]
        rate_index = int(candidate["_rate_index"])
        route_mask = arrays["route_masks"][policy_index, rate_index]
        routed_prediction = _route_prediction(m1_prediction, m3_prediction, route_mask)
        baseline_point = classification_metrics(gold, m1_prediction)
        routed_point = classification_metrics(gold, routed_prediction)
        point_values = {
            "macro_f1_gain": routed_point["macro_f1"] - baseline_point["macro_f1"],
            "five_label_macro_f1_gain": (
                routed_point["five_label_macro_f1"] - baseline_point["five_label_macro_f1"]
            ),
            "hamming_loss_delta": routed_point["hamming_loss"] - baseline_point["hamming_loss"],
            "actual_call_rate": float(np.mean(route_mask)),
        }
        values = {name: [] for name in point_values}
        rng = np.random.default_rng(np.random.SeedSequence([base_seed, policy_index]))
        for _ in range(repetitions):
            indices = component_bootstrap_indices(groups, rng)
            baseline = classification_metrics(gold[indices], m1_prediction[indices])
            routed = classification_metrics(gold[indices], routed_prediction[indices])
            values["macro_f1_gain"].append(routed["macro_f1"] - baseline["macro_f1"])
            values["five_label_macro_f1_gain"].append(
                routed["five_label_macro_f1"] - baseline["five_label_macro_f1"]
            )
            values["hamming_loss_delta"].append(
                routed["hamming_loss"] - baseline["hamming_loss"]
            )
            values["actual_call_rate"].append(float(np.mean(route_mask[indices])))
        records[policy] = {
            "target_call_rate": float(candidate["target_call_rate"]),
            "actual_call_rate": float(candidate["actual_call_rate"]),
            "intervals": {
                name: _bootstrap_interval(values[name], point_values[name]) for name in point_values
            },
        }
    return {
        "schema_version": "exp-router-bootstrap-v2" if is_replication(config) else "exp-060-bootstrap-v1",
        "experiment_id": experiment_id(config),
        "repetitions": repetitions,
        "seed": base_seed,
        "unit": "duplicate_component",
        "interval": "percentile_95",
        "policy_candidates": records,
        "overall_selected_policy": analysis["selected"]["overall"]["selected_policy"],
        "selection_warning": (
            "Point estimates determine the frozen development gate; intervals only qualify stability. "
            "This train-OOF bootstrap is not an independent test."
        ),
    }


def _fold_stable_acceptance_mask(
    scores: np.ndarray, fold_ids: np.ndarray, coverage: float
) -> np.ndarray:
    accepted = np.zeros(len(scores), dtype=bool)
    for fold in sorted(int(value) for value in np.unique(fold_ids)):
        indices = np.flatnonzero(fold_ids == fold)
        count = int(math.floor(float(coverage) * len(indices) + 0.5))
        order = np.argsort(scores[indices], kind="stable")
        accepted[indices[order[:count]]] = True
    return accepted


def routed_selective_diagnostics(
    analysis: dict[str, Any], data: dict[str, np.ndarray], config: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    arrays = analysis["private_arrays"]
    fold_ids = arrays["fold_ids"]
    gold = arrays["gold"]
    coverages: list[float] | None = None
    for section in ("routed_evaluation", "risk_coverage", "selective_prediction"):
        values = config.get(section)
        if isinstance(values, dict) and "coverages" in values:
            coverages = [float(value) for value in values["coverages"]]
            break
    if coverages is None:
        coverages = [1.0, 0.95, 0.9, 0.8, 0.7, 0.6]
    risk_rows: list[dict[str, Any]] = []
    retention_rows: list[dict[str, Any]] = []
    for policy_index, policy in enumerate(POLICY_ORDER):
        candidate = analysis["selected_internal"][policy]
        rate_index = int(candidate["_rate_index"])
        route_mask = arrays["route_masks"][policy_index, rate_index]
        prediction = _route_prediction(
            arrays["m1_predictions"], arrays["m3_predictions"], route_mask
        )
        uncertainty = routed_uncertainty_scores(
            route_mask,
            analysis["m1_probabilities"],
            analysis["m3_probabilities"],
            arrays["m1_thresholds"],
            arrays["m3_thresholds"],
        )
        for method in UNCERTAINTY_ORDER:
            for coverage in coverages:
                accepted = _fold_stable_acceptance_mask(uncertainty[method], fold_ids, coverage)
                if not np.any(accepted):
                    raise RuntimeError("Risk-coverage contract produced zero accepted rows")
                metrics = classification_metrics(gold[accepted], prediction[accepted])
                risk_rows.append({
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
                })
                for label_index, label in enumerate(LABEL_ORDER):
                    positive = gold[:, label_index] == 1
                    support = int(np.sum(positive))
                    retained = int(np.sum(positive & accepted))
                    retention_rows.append({
                        "policy": policy,
                        "uncertainty_method": method,
                        "target_coverage": coverage,
                        "label": label,
                        "positive_support": support,
                        "retained_positive": retained,
                        "positive_retention": float(retained / support if support else 0.0),
                    })
    return risk_rows, retention_rows


def _matplotlib_config(config: dict[str, Any]) -> tuple[str, tempfile.TemporaryDirectory[str] | None]:
    configured = config.get("runtime", {}).get("mplconfigdir")
    if configured:
        path = Path(str(configured)).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return str(path), None
    temporary = tempfile.TemporaryDirectory(prefix="exp060-mpl-")
    return temporary.name, temporary


def make_figures(
    run_dir: Path,
    call_rows: list[dict[str, Any]],
    risk_rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[Path, Path]:
    mplconfigdir, temporary = _matplotlib_config(config)
    previous = os.environ.get("MPLCONFIGDIR")
    os.environ["MPLCONFIGDIR"] = mplconfigdir
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        call_path = run_dir / "call-rate-performance.png"
        figure, axis = plt.subplots(figsize=(8.0, 5.0))
        for policy in POLICY_ORDER:
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

        risk_path = run_dir / "routed-risk-coverage.png"
        figure, axis = plt.subplots(figsize=(8.0, 5.0))
        for policy in POLICY_ORDER:
            for method in UNCERTAINTY_ORDER:
                rows = [
                    row for row in risk_rows
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
        return call_path, risk_path
    finally:
        if previous is None:
            os.environ.pop("MPLCONFIGDIR", None)
        else:
            os.environ["MPLCONFIGDIR"] = previous
        if temporary is not None:
            temporary.cleanup()


def write_report(
    path: Path,
    selected: dict[str, Any],
    bootstrap: dict[str, Any],
    config: dict[str, Any],
) -> None:
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
    for policy in POLICY_ORDER:
        record = selected["policies"][policy]
        candidate = record["candidate"]
        lines.append(
            f"- `{policy}`: passed=`{record['passed']}`, actual call rate="
            f"`{candidate['actual_call_rate']:.6f}`, Macro-F1 gain="
            f"`{candidate['six_label_macro_f1_gain']:+.6f}`."
        )
    lines.extend([
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
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def feature_contract(config: dict[str, Any]) -> dict[str, Any]:
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
            "outer_folds": 5,
            "outer_train_folds": 4,
            "inner_threshold_train_folds": 3,
        },
        "target_contract": {
            "unit": "whole_six_bit_vector",
            "positive": "m3_row_hamming_loss_strictly_lower_than_m1",
            "tie_policy": "m1",
        },
        "policy_order": ["m1_only", "m3_only", *POLICY_ORDER],
        "call_rates": [float(value) for value in config["call_rates"]],
        "forbidden_runtime_feature_classes": list(
            config["feature_contract"]["forbidden_runtime_feature_classes"]
        ),
        "public_row_level_data": False,
    }


def scan_public_outputs(run_dir: Path) -> None:
    expected = {
        "feature-contract.json", "fold-summary.csv", "router-discrimination.json",
        "call-rate-performance.csv", "policy-comparisons.csv", "random-routing.csv",
        "selected-operating-point.json", "bootstrap.json", "routed-risk-coverage.csv",
        "positive-label-retention.csv", "call-rate-performance.png", "routed-risk-coverage.png",
        "REPORT.md", "run.json", "frozen-sources",
    }
    actual = {path.name for path in run_dir.iterdir()}
    if actual != expected:
        raise ValueError(f"EXP-060 public artifact set drift: {sorted(actual ^ expected)}")
    for path in run_dir.rglob("*.json"):
        violations = public_sensitive_paths(json.loads(path.read_text(encoding="utf-8")))
        if violations:
            raise ValueError(f"Public JSON privacy violation in {path}: {violations}")
    for filename, columns in CSV_ALLOWLISTS.items():
        with (run_dir / filename).open("r", encoding="utf-8", newline="") as source:
            reader = csv.reader(source)
            header = tuple(next(reader))
        if header != columns:
            raise ValueError(f"Public CSV schema drift: {filename}")
    forbidden_suffixes = {".npy", ".npz", ".parquet", ".jsonl"}
    leaked = [display_path(path) for path in run_dir.rglob("*") if path.suffix in forbidden_suffixes]
    if leaked:
        raise ValueError(f"Forbidden public row-level artifact types: {leaked}")


def validate_public_csv_payloads(
    payloads: dict[str, tuple[list[dict[str, Any]], tuple[str, ...]]],
    sample_ids: np.ndarray,
    component_ids: np.ndarray,
) -> None:
    """Fail before publication if a fixed aggregate CSV payload can expose row identifiers."""
    sensitive_values = {str(value) for value in sample_ids.tolist()}
    sensitive_values.update(str(value) for value in component_ids.tolist())
    if set(payloads) != set(CSV_ALLOWLISTS):
        raise ValueError("EXP-060 public CSV artifact set drift before write")
    for filename, (rows, columns) in payloads.items():
        if columns != CSV_ALLOWLISTS[filename] or not rows:
            raise ValueError(f"EXP-060 public CSV schema drift before write: {filename}")
        for row in rows:
            if tuple(row) != columns:
                raise ValueError(f"EXP-060 public CSV row drift before write: {filename}")
            for value in row.values():
                if isinstance(value, (dict, list, tuple, np.ndarray)):
                    raise ValueError(f"Nested value in public aggregate CSV: {filename}")
                if isinstance(value, str) and value in sensitive_values:
                    raise ValueError(f"Row identifier in public aggregate CSV: {filename}")


def _output_paths(config: dict[str, Any]) -> tuple[Path, Path]:
    if is_replication(config):
        outputs = _expected_replication_outputs(config)
        return (
            resolve_output(outputs["public_attempt_dir"]) / "router",
            resolve_output(outputs["private_attempt_dir"]) / "router",
        )
    public_value = config["outputs"].get("formal_run_dir", config["outputs"].get("public_run_dir"))
    private_value = config["outputs"].get(
        "formal_private_dir", config["outputs"].get("private_run_dir")
    )
    return resolve_project(public_value), resolve_project(private_value)


def formal_run(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    if config.get("_archive_only"):
        raise PermissionError("Sealed EXP-060 is archive-only and can never be rerun")
    run_dir, private_dir = _output_paths(config)
    if os.path.lexists(run_dir) or os.path.lexists(private_dir):
        raise FileExistsError("Refusing to overwrite append-only EXP-060 output")
    if is_replication(config):
        outputs = _expected_replication_outputs(config)
        public_attempt = resolve_output(outputs["public_attempt_dir"])
        private_attempt = resolve_output(outputs["private_attempt_dir"])
        selection = resolve_output(outputs["selection_record"])
        if os.path.lexists(selection):
            raise FileExistsError("A final pipeline selection already exists")
        if not public_attempt.is_dir() or not private_attempt.is_dir():
            raise FileNotFoundError("Router requires the matching pre-existing public/private attempt")
        if stat.S_IMODE(private_attempt.stat().st_mode) != 0o700:
            raise PermissionError("Private replication attempt must be mode 0700")
    input_record = _record_by_names(config["input"], ("paired_oof",))
    input_path = require_record(input_record)
    if input_path.is_symlink() or stat.S_IMODE(input_path.stat().st_mode) != 0o600:
        raise PermissionError("EXP-058 paired OOF must be a regular mode-0600 file")
    if input_path.parent.is_symlink() or stat.S_IMODE(input_path.parent.stat().st_mode) != 0o700:
        raise PermissionError("EXP-058 paired OOF parent must be mode 0700")
    schema = npz_header_schema(input_path)
    if schema != expected_input_schema():
        raise ValueError("EXP-058 paired OOF header schema drift")

    started_at = utc_now()
    started = time.monotonic()
    input_hash_before = sha256(input_path)
    with np.load(input_path, allow_pickle=False) as archive:
        data = {name: np.array(archive[name], copy=True) for name in archive.files}
    validate_loaded_input(data, config)
    analysis = analyze_arrays(data, config)
    random_rows = random_routing_diagnostics(analysis, data, config)
    bootstrap = bootstrap_selected_candidates(analysis, data, config)
    risk_rows, retention_rows = routed_selective_diagnostics(analysis, data, config)
    input_hash_after = sha256(input_path)
    if input_hash_before != input_hash_after or input_hash_after != input_record["sha256"]:
        raise ValueError("EXP-058 paired input changed during EXP-060")
    wall_seconds = float(time.monotonic() - started)
    peak_memory = peak_rss_gb()
    maximum_wall = float(config["resources"].get("formal_wall_seconds", 1800))
    maximum_memory = float(config["resources"].get("formal_peak_memory_gb", 4.0))
    if wall_seconds > maximum_wall or peak_memory > maximum_memory:
        raise RuntimeError("EXP-060 formal resource budget exceeded")

    public_json = {
        "feature-contract.json": feature_contract(config),
        "router-discrimination.json": analysis["router_discrimination"],
        "selected-operating-point.json": analysis["selected"],
        "bootstrap.json": bootstrap,
    }
    for filename, payload in public_json.items():
        violations = public_sensitive_paths(payload)
        if violations:
            raise ValueError(f"Public JSON privacy violation before write: {filename}: {violations}")
    public_csv = {
        "fold-summary.csv": (analysis["fold_rows"], FOLD_SUMMARY_COLUMNS),
        "call-rate-performance.csv": (analysis["call_rows"], CALL_RATE_COLUMNS),
        "policy-comparisons.csv": (analysis["policy_comparisons"], POLICY_COMPARISON_COLUMNS),
        "random-routing.csv": (random_rows, RANDOM_ROUTING_COLUMNS),
        "routed-risk-coverage.csv": (risk_rows, RISK_COVERAGE_COLUMNS),
        "positive-label-retention.csv": (retention_rows, RETENTION_COLUMNS),
    }
    validate_public_csv_payloads(
        public_csv, np.asarray(data["sample_ids"]), np.asarray(data["component_ids"])
    )

    run_dir.mkdir(parents=not is_replication(config), mode=0o755)
    private_dir.mkdir(parents=not is_replication(config), mode=0o700)
    os.chmod(private_dir, 0o700)
    frozen_sources = freeze_sources(run_dir, config_path, config)
    private_path = private_dir / "router-oof.npz"
    atomic_npz(private_path, analysis["private_arrays"])
    for filename, payload in public_json.items():
        atomic_json(run_dir / filename, payload)
    for filename, (rows, columns) in public_csv.items():
        atomic_csv(run_dir / filename, rows, columns)
    call_figure, risk_figure = make_figures(run_dir, analysis["call_rows"], risk_rows, config)
    write_report(run_dir / "REPORT.md", analysis["selected"], bootstrap, config)
    public_outputs = {
        name.replace("-", "_").replace(".", "_"): artifact(run_dir / name)
        for name in (
            "feature-contract.json", "fold-summary.csv", "router-discrimination.json",
            "call-rate-performance.csv", "policy-comparisons.csv", "random-routing.csv",
            "selected-operating-point.json", "bootstrap.json", "routed-risk-coverage.csv",
            "positive-label-retention.csv", call_figure.name, risk_figure.name, "REPORT.md",
        )
    }
    run = {
        "schema_version": "exp-router-formal-run-v2" if is_replication(config) else "exp-060-formal-run-v1",
        **identity_provenance(config),
        "tier": "Major system experiment",
        "status": "CompletedAwaitingVerification",
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "command": " ".join([
            os.path.realpath(sys.executable), display_repo_path(Path(__file__)), "--config",
            display_repo_path(config_path),
        ]),
        "cwd": str(REPO_ROOT),
        "runtime": {
            "python_executable": os.path.realpath(sys.executable),
            "platform": platform.platform(),
            "dependencies": dependency_versions(),
            "mplconfigdir_configured": bool(config.get("runtime", {}).get("mplconfigdir")),
        },
        "git": git_metadata(),
        **({"config": artifact(config_path)} if is_replication(config) else {}),
        "input_before": artifact(input_path),
        "input_sha256_after": input_hash_after,
        "input_schema": public_schema_records(schema),
        "source_order_sha256": config["data"].get(
            "source_order_sha256", EXPECTED_SOURCE_ORDER_SHA256
        ),
        "private_output": artifact(private_path),
        "public_outputs": public_outputs,
        "frozen_sources": frozen_sources,
        "rows": int(len(data["gold"])),
        "folds": 5,
        "component_count": int(len(np.unique(data["component_ids"]))),
        "execution_flags": {
            "nested_threshold_recomputation": True,
            "scaler_and_router_fitted": True,
            "router_results_computed": True,
            "component_bootstrap_computed": True,
            "model_loaded_or_forward_run": False,
            "raw_text_accessed": False,
            "validation_accessed": False,
            "test_accessed": False,
        },
        "resources": {
            "wall_seconds": wall_seconds,
            "peak_process_rss_gb": peak_memory,
            "api_cost_usd": 0,
            "gpu_cost_usd": 0,
            "model_forward_runs": 0,
        },
        "split_access": {
            "accessed_splits": ["train-oof"],
            "validation_accessed": False,
            "test_inputs_accessed": False,
            "test_labels_accessed": False,
        },
        "decision": analysis["selected"]["overall"]["decision"],
        "claim_boundary": config["claim_boundary"],
    }
    violations = public_sensitive_paths(run)
    if violations:
        raise ValueError(f"Public run privacy violation: {violations}")
    atomic_json(run_dir / "run.json", run)
    scan_public_outputs(run_dir)
    return run


def create_json_once(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
        os.link(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def replication_primary_gate_result(
    selected: dict[str, Any], config: dict[str, Any]
) -> bool:
    if not is_replication(config):
        raise PermissionError("Primary replication gate applies only to config-v2")
    policies = selected.get("policies", {})
    if not isinstance(policies, dict) or set(policies) != set(POLICY_ORDER):
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


def complete_router_attempt(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    if not is_replication(config):
        raise PermissionError("Router completion applies only to config-v2 attempts")
    run_dir, private_dir = _output_paths(config)
    selection = resolve_output(_expected_replication_outputs(config)["selection_record"])
    if os.path.lexists(selection):
        raise FileExistsError("A final pipeline selection already exists")
    completion_path = run_dir / "router-complete.json"
    if os.path.lexists(completion_path):
        raise FileExistsError("Router completion record is immutable")
    run_path = run_dir / "run.json"
    verification_path = run_dir / "verification.json"
    selected_path = run_dir / "selected-operating-point.json"
    private_path = private_dir / "router-oof.npz"
    if (
        not run_path.is_file()
        or not verification_path.is_file()
        or not selected_path.is_file()
        or not private_path.is_file()
    ):
        raise FileNotFoundError(
            "Router completion requires run, selected point, verification, and private router OOF"
        )
    run = json.loads(run_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    primary_gate_passed = replication_primary_gate_result(selected, config)
    expected_decision = "Pass" if primary_gate_passed else "Fail"
    verified = verification.get("verified_artifacts", {})
    selected_record = run.get("public_outputs", {}).get("selected_operating_point_json")
    if (
        run.get("status") != "CompletedAwaitingVerification"
        or not _identity_matches(run, config)
        or run.get("decision") != expected_decision
        or selected_record != artifact(selected_path)
        or verification.get("status") != "Passed"
        or int(verification.get("failed_count", -1)) != 0
        or not _identity_matches(verification, config)
        or verified.get("config") != artifact(config_path)
        or verified.get("run") != artifact(run_path)
        or verified.get("private_router_oof") != artifact(private_path)
    ):
        raise RuntimeError("Only a matching Passed router verification can complete this stage")
    completion = {
        "schema_version": "exp-router-completion-v2",
        **identity_provenance(config),
        "status": "Complete",
        "completed_at_utc": utc_now(),
        "decision": expected_decision,
        "primary_gate_passed": primary_gate_passed,
        "artifacts": {
            "config": artifact(config_path),
            "run": artifact(run_path),
            "selected_operating_point": artifact(selected_path),
            "final_verification": artifact(verification_path),
            "private_router_oof": artifact(private_path),
        },
        "next_gate": "Finalizer must bind OOF, EXP-059, and router completion records.",
        "claim_boundary": (
            "Completes one verified train-only router stage; this is not namespace selection "
            "or a completed cross-seed claim."
        ),
    }
    if public_sensitive_paths(completion):
        raise ValueError("Router completion contains row-level fields")
    create_json_once(completion_path, completion)
    return completion


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run frozen EXP-060 pre-Qwen router")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--stage", choices=("run", "complete"), default="run")
    return parser.parse_args()


def main() -> None:
    if Path.cwd().resolve() != REPO_ROOT.resolve():
        raise RuntimeError(f"EXP-060 must run from repository root: {REPO_ROOT}")
    args = parse_args()
    config_path = args.config.resolve()
    if config_path.parent != (SCRIPT_DIR / "configs").resolve() or config_path.is_symlink():
        raise ValueError("Router config must be a regular direct child of the canonical configs directory")
    config = load_config(config_path)
    if not is_replication(config) and config_path != DEFAULT_CONFIG.resolve():
        raise ValueError(f"Legacy EXP-060 must use the canonical formal config: {DEFAULT_CONFIG}")
    result = (
        formal_run(config_path, config)
        if args.stage == "run"
        else complete_router_attempt(config_path, config)
    )
    print(json.dumps({"stage": args.stage, "status": result["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
