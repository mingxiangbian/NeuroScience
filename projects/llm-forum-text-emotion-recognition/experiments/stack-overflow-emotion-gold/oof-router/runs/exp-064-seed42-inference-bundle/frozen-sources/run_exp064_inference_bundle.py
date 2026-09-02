#!/usr/bin/env python3
"""Fit the one-shot EXP-064 seed-42 inference bundle."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
import sys
import time
from typing import Any
import warnings
import zipfile

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


EXPERIMENT_ID = "EXP-064"
RUN_ID = "exp-064-seed42-inference-bundle"
SCHEMA_VERSION = "exp-064-inference-bundle-config-v1"
BUNDLE_SCHEMA = "exp-064-inference-bundle-v1"
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
EXPECTED_BUNDLE_SCHEMA = {
    "scaler_mean": {"shape": [14], "dtype": "float64", "fortran_order": False},
    "scaler_var": {"shape": [14], "dtype": "float64", "fortran_order": False},
    "scaler_scale": {"shape": [14], "dtype": "float64", "fortran_order": False},
    "classes": {"shape": [2], "dtype": "int64", "fortran_order": False},
    "coef": {"shape": [1, 14], "dtype": "float64", "fortran_order": False},
    "intercept": {"shape": [1], "dtype": "float64", "fortran_order": False},
}
PUBLIC_SENSITIVE_KEYS = {
    "sample_id", "sample_ids", "component_id", "component_ids", "gold", "logits",
    "m1_logits", "m3_logits", "probabilities", "predictions", "features", "targets",
    "route_scores", "route_mask", "text", "raw_text", "cutoff", "thresholds", "coef",
    "intercept", "scaler_mean", "scaler_var", "scaler_scale",
}
CLAIM_BOUNDARY = (
    "A seed-42 full-OOF inference artifact only; no same-data performance, independent-test, "
    "cross-seed deployment, production, forum-generalization, or emotion-mechanism claim."
)


def _locate_project_root(source: Path) -> Path:
    for candidate in (source, *source.parents):
        if candidate.name == "llm-forum-text-emotion-recognition":
            return candidate
    raise RuntimeError("Could not locate llm-forum-text-emotion-recognition project root")


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = _locate_project_root(SCRIPT_PATH)
BASE_REL = Path("experiments/stack-overflow-emotion-gold/oof-router")
DEFAULT_CONFIG = PROJECT_ROOT / BASE_REL / "configs/exp-064-seed42-inference-bundle.json"
PUBLIC_REL = BASE_REL / "runs" / RUN_ID
PRIVATE_REL = BASE_REL / "private" / RUN_ID


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def _resolve_relative(value: str | Path) -> Path:
    relative = Path(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ValueError(f"Unsafe project-relative path: {value}")
    cursor = PROJECT_ROOT
    for part in relative.parts:
        cursor = cursor / part
        if os.path.lexists(cursor) and stat.S_ISLNK(os.lstat(cursor).st_mode):
            raise ValueError(f"Path traverses symlink: {value}")
    resolved = (PROJECT_ROOT / relative).resolve()
    if not resolved.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return resolved


def artifact_record(path: Path, *, include_path: bool = True) -> dict[str, Any]:
    metadata = os.lstat(path)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ValueError(f"Artifact is not a single regular file: {path}")
    record: dict[str, Any] = {
        "bytes": metadata.st_size,
        "sha256": sha256_file(path),
        "mode": f"{stat.S_IMODE(metadata.st_mode):04o}",
    }
    if include_path:
        record["path"] = str(path.relative_to(PROJECT_ROOT))
    return record


def require_record(record: dict[str, Any], expected_mode: int) -> Path:
    if set(record) != {"path", "bytes", "sha256", "mode"}:
        raise ValueError("Artifact record schema drift")
    path = _resolve_relative(record["path"])
    metadata = os.lstat(path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != expected_mode
        or metadata.st_size != int(record["bytes"])
        or f"{expected_mode:04o}" != record["mode"]
        or sha256_file(path) != record["sha256"]
    ):
        raise ValueError(f"Artifact identity/mode drift: {record['path']}")
    return path


def npz_header_schema(path: Path) -> dict[str, dict[str, Any]]:
    schema: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        if len(members) != len(set(members)):
            raise ValueError("NPZ contains duplicate members")
        if any(not member.endswith(".npy") or "/" in member for member in members):
            raise ValueError("NPZ member layout drift")
        for member in sorted(members):
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


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_and_validate_config(config_path: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    config_path = config_path.resolve()
    if config_path.resolve() != DEFAULT_CONFIG.resolve():
        raise ValueError("EXP-064 requires the frozen config path")
    config_record = artifact_record(config_path)
    if config_record["mode"] != "0644":
        raise ValueError("EXP-064 config must be mode 0644")
    config = _load_json(config_path)
    if (
        config.get("schema_version") != SCHEMA_VERSION
        or config.get("experiment_id") != EXPERIMENT_ID
        or config.get("run_id") != RUN_ID
        or config.get("rq_id") != "RQ-S3"
        or config.get("tier") != "Major"
        or config.get("model_seed") != 42
    ):
        raise ValueError("EXP-064 config identity drift")
    outputs = config.get("outputs", {})
    if outputs != {"public_dir": str(PUBLIC_REL), "private_dir": str(PRIVATE_REL)}:
        raise ValueError("EXP-064 output contract drift")
    thresholds = config.get("thresholds", {})
    if thresholds != {
        "calibrator": "identity",
        "grid_start": 0.05,
        "grid_end": 0.95,
        "grid_step": 0.01,
        "numeric_tolerance": 1e-12,
        "selection_order": [
            "highest_six_label_macro_f1",
            "lowest_hamming_loss",
            "closest_to_0_5",
            "lower_threshold",
        ],
    }:
        raise ValueError("EXP-064 threshold contract drift")
    feature_contract = config.get("feature_contract", {})
    if feature_contract != {
        "ordered_features": list(FEATURE_NAMES),
        "feature_count": 14,
        "entropy_clip": [1e-15, 0.999999999999999],
        "entropy_log": "natural",
    }:
        raise ValueError("EXP-064 feature contract drift")
    router = config.get("router", {})
    if router != {
        "scaler": "StandardScaler",
        "logistic_regression": {
            "penalty": "l2",
            "C": 1.0,
            "class_weight": "balanced",
            "solver": "liblinear",
            "max_iter": 1000,
            "random_state": 42,
        },
        "positive_class": 1,
        "nominal_call_rate": 0.15,
        "cutoff_count_rule": "ceil_target_rate_times_rows",
        "cutoff_comparator": ">=",
    }:
        raise ValueError("EXP-064 router contract drift")
    if config.get("labels") != list(LABEL_ORDER):
        raise ValueError("EXP-064 label order drift")
    access = config.get("access", {})
    if access != {
        "paired_train_oof_only": True,
        "checkpoint_access": False,
        "raw_text_access": False,
        "validation_access": False,
        "test_access": False,
        "model_forward": False,
    }:
        raise ValueError("EXP-064 access contract drift")
    source_paths: dict[str, Path] = {"config": config_path}
    input_contract = config.get("input", {})
    if set(input_contract) != {"artifact", "source_order_sha256", "array_schema"}:
        raise ValueError("EXP-064 input contract schema drift")
    source_paths["input"] = require_record(input_contract["artifact"], 0o600)
    if input_contract["artifact"].get("path") != (
        "experiments/stack-overflow-emotion-gold/oof-router/private/"
        "exp-058-paired-oof-production/paired-oof.npz"
    ):
        raise ValueError("EXP-064 paired OOF path drift")
    if input_contract.get("source_order_sha256") != (
        "c9e4bd1eb2bdbb33c833234754c493b8818aa6c610acaf88659ae74fa94848a3"
    ):
        raise ValueError("EXP-064 source-order identity drift")
    if input_contract.get("array_schema") != EXPECTED_INPUT_SCHEMA:
        raise ValueError("EXP-064 input schema contract drift")
    for section in ("implementation", "legacy_lineage"):
        records = config.get(section)
        if not isinstance(records, dict) or not records:
            raise ValueError(f"EXP-064 {section} missing")
        for name, record in records.items():
            source_paths[name] = require_record(record, 0o644)
    if config.get("claim_boundary") != CLAIM_BOUNDARY:
        raise ValueError("EXP-064 claim boundary drift")
    return config, source_paths


def validate_input(path: Path, config: dict[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    header = npz_header_schema(path)
    if header != EXPECTED_INPUT_SCHEMA:
        raise ValueError("EXP-064 paired OOF header drift")
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != set(EXPECTED_INPUT_SCHEMA):
            raise ValueError("EXP-064 paired OOF key drift")
        sample_ids = np.asarray(archive["sample_ids"])
        component_ids = np.asarray(archive["component_ids"])
        fold_ids = np.asarray(archive["fold_ids"], dtype=np.int8)
        gold = np.asarray(archive["gold"], dtype=np.uint8)
        m1_logits = np.asarray(archive["m1_logits"], dtype=np.float32)
        m3_logits = np.asarray(archive["m3_logits"], dtype=np.float32)
        character_lengths = np.asarray(archive["character_lengths"], dtype=np.int32)
        m1_token_lengths = np.asarray(archive["m1_token_lengths"], dtype=np.int32)
        m3_token_lengths = np.asarray(archive["m3_token_lengths"], dtype=np.int32)
        m1_hashes = np.asarray(archive["m1_fold_run_sha256"])
        m3_hashes = np.asarray(archive["m3_fold_run_sha256"])
    if len(set(sample_ids.tolist())) != 3360:
        raise ValueError("EXP-064 sample IDs are not unique")
    source_order = canonical_digest(sample_ids.tolist())
    if source_order != config["input"]["source_order_sha256"]:
        raise ValueError("EXP-064 source order drift")
    if not np.all(np.isin(gold, [0, 1])):
        raise ValueError("EXP-064 gold is not binary")
    if not np.all(np.isfinite(m1_logits)) or not np.all(np.isfinite(m3_logits)):
        raise ValueError("EXP-064 logits are non-finite")
    if (
        np.any(character_lengths < 0)
        or np.any(m1_token_lengths < 0)
        or np.any(m3_token_lengths < 0)
    ):
        raise ValueError("EXP-064 length arrays contain negatives")
    if sorted(np.unique(fold_ids).tolist()) != [0, 1, 2, 3, 4]:
        raise ValueError("EXP-064 fold identity drift")
    if any(int(np.sum(fold_ids == fold)) != 672 for fold in range(5)):
        raise ValueError("EXP-064 fold row count drift")
    component_fold: dict[str, int] = {}
    for component, fold in zip(component_ids.tolist(), fold_ids.tolist()):
        previous = component_fold.setdefault(component, int(fold))
        if previous != int(fold):
            raise ValueError("EXP-064 duplicate component crosses folds")
    for family, values in (("m1", m1_hashes), ("m3", m3_hashes)):
        hashes = values.tolist()
        if len(set(hashes)) != 5 or any(len(value) != 64 for value in hashes):
            raise ValueError(f"EXP-064 {family} fold-run hash drift")
    arrays = {
        "gold": gold,
        "m1_logits": m1_logits,
        "m3_logits": m3_logits,
        "character_lengths": character_lengths,
        "m1_token_lengths": m1_token_lengths,
    }
    identity = {
        "logical_name": "seed42_paired_train_oof",
        "bytes": int(config["input"]["artifact"]["bytes"]),
        "sha256": config["input"]["artifact"]["sha256"],
        "mode": "0600",
        "rows": 3360,
        "labels": 6,
        "array_schema_sha256": canonical_digest(header),
        "source_order_sha256": source_order,
    }
    return arrays, identity


def stable_sigmoid(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    result = np.empty_like(array)
    positive = array >= 0
    result[positive] = 1.0 / (1.0 + np.exp(-array[positive]))
    exp_values = np.exp(array[~positive])
    result[~positive] = exp_values / (1.0 + exp_values)
    return result


def classification_summary(gold: np.ndarray, prediction: np.ndarray) -> tuple[float, float]:
    labels = np.asarray(gold, dtype=np.uint8)
    predicted = np.asarray(prediction, dtype=np.uint8)
    if labels.shape != predicted.shape or labels.ndim != 2 or labels.shape[1] != 6:
        raise ValueError("EXP-064 classification shape mismatch")
    f1_values: list[float] = []
    for index in range(6):
        tp = int(np.sum((labels[:, index] == 1) & (predicted[:, index] == 1)))
        fp = int(np.sum((labels[:, index] == 0) & (predicted[:, index] == 1)))
        fn = int(np.sum((labels[:, index] == 1) & (predicted[:, index] == 0)))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1_values.append(
            2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
    return float(np.mean(f1_values)), float(np.mean(labels != predicted))


def select_threshold(probabilities: np.ndarray, gold: np.ndarray, grid: list[float]) -> float:
    candidates: list[tuple[float, float, float]] = []
    for threshold in grid:
        macro_f1, hamming = classification_summary(
            gold, (np.asarray(probabilities) >= threshold).astype(np.uint8)
        )
        candidates.append((float(threshold), macro_f1, hamming))
    best_macro = max(row[1] for row in candidates)
    tied = [row for row in candidates if abs(row[1] - best_macro) <= 1e-12]
    best_hamming = min(row[2] for row in tied)
    tied = [row for row in tied if abs(row[2] - best_hamming) <= 1e-12]
    tied.sort(key=lambda row: (abs(row[0] - 0.5), row[0]))
    return tied[0][0]


def build_features(
    probabilities: np.ndarray,
    threshold: float,
    character_lengths: np.ndarray,
    token_lengths: np.ndarray,
) -> np.ndarray:
    values = np.asarray(probabilities, dtype=np.float64)
    clipped = np.clip(values, 1e-15, 1.0 - 1e-15)
    entropy = -(clipped * np.log(clipped) + (1.0 - clipped) * np.log1p(-clipped))
    matrix = np.column_stack(
        [
            values,
            np.mean(entropy, axis=1),
            np.max(entropy, axis=1),
            np.min(np.abs(values - threshold), axis=1),
            np.sum(values >= threshold, axis=1),
            np.max(values, axis=1),
            np.min(values, axis=1),
            np.asarray(character_lengths, dtype=np.float64),
            np.asarray(token_lengths, dtype=np.float64),
        ]
    ).astype(np.float64, copy=False)
    if matrix.shape != (len(values), 14) or not np.all(np.isfinite(matrix)):
        raise ValueError("EXP-064 feature contract failed")
    return matrix


def build_target(m1_prediction: np.ndarray, m3_prediction: np.ndarray, gold: np.ndarray) -> np.ndarray:
    m1 = np.asarray(m1_prediction, dtype=np.uint8)
    m3 = np.asarray(m3_prediction, dtype=np.uint8)
    labels = np.asarray(gold, dtype=np.uint8)
    if m1.shape != m3.shape or m1.shape != labels.shape:
        raise ValueError("EXP-064 target input mismatch")
    return (np.mean(m3 != labels, axis=1) < np.mean(m1 != labels, axis=1)).astype(np.uint8)


def cutoff_for_rate(scores: np.ndarray, target_rate: float) -> float:
    values = np.asarray(scores, dtype=np.float64)
    if values.ndim != 1 or not values.size or not np.all(np.isfinite(values)):
        raise ValueError("EXP-064 cutoff scores invalid")
    count = max(1, int(math.ceil(target_rate * len(values))))
    return float(np.sort(values)[::-1][count - 1])


def fit_bundle(arrays: dict[str, np.ndarray], config: dict[str, Any], input_identity: dict[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    gold = arrays["gold"]
    m1_probabilities = stable_sigmoid(arrays["m1_logits"])
    m3_probabilities = stable_sigmoid(arrays["m3_logits"])
    grid = [value / 100.0 for value in range(5, 96)]
    m1_threshold = select_threshold(m1_probabilities, gold, grid)
    m3_threshold = select_threshold(m3_probabilities, gold, grid)
    m1_prediction = (m1_probabilities >= m1_threshold).astype(np.uint8)
    m3_prediction = (m3_probabilities >= m3_threshold).astype(np.uint8)
    target = build_target(m1_prediction, m3_prediction, gold)
    if np.unique(target).tolist() != [0, 1]:
        raise ValueError("EXP-064 router target is not exact binary two-class")
    features = build_features(
        m1_probabilities,
        m1_threshold,
        arrays["character_lengths"],
        arrays["m1_token_lengths"],
    )
    scaler = StandardScaler()
    standardized = scaler.fit_transform(features)
    settings = config["router"]["logistic_regression"]
    router = LogisticRegression(**settings)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        router.fit(standardized, target)
    if any(issubclass(item.category, ConvergenceWarning) for item in caught):
        raise RuntimeError("EXP-064 logistic router did not converge")
    if router.classes_.tolist() != [0, 1] or int(router.n_iter_[0]) >= settings["max_iter"]:
        raise RuntimeError("EXP-064 fitted router class/convergence drift")
    route_scores = np.asarray(router.predict_proba(standardized)[:, 1], dtype=np.float64)
    manual_scores = stable_sigmoid(standardized @ router.coef_[0] + router.intercept_[0])
    if not np.allclose(route_scores, manual_scores, rtol=0.0, atol=1e-12):
        raise RuntimeError("EXP-064 manual router score parity failed")
    cutoff = cutoff_for_rate(route_scores, 0.15)
    route_mask = route_scores >= cutoff
    count = int(math.ceil(0.15 * len(route_scores)))
    output_arrays = {
        "scaler_mean": np.ascontiguousarray(scaler.mean_, dtype="<f8"),
        "scaler_var": np.ascontiguousarray(scaler.var_, dtype="<f8"),
        "scaler_scale": np.ascontiguousarray(scaler.scale_, dtype="<f8"),
        "classes": np.ascontiguousarray(router.classes_, dtype="<i8"),
        "coef": np.ascontiguousarray(router.coef_, dtype="<f8"),
        "intercept": np.ascontiguousarray(router.intercept_, dtype="<f8"),
    }
    bundle = {
        "schema_version": BUNDLE_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "model_seed": 42,
        "status": "FittedAwaitingVerification",
        "labels": list(LABEL_ORDER),
        "features": list(FEATURE_NAMES),
        "calibration": {"m1": "identity", "m3": "identity", "sigmoid": "stable_float64"},
        "thresholds": {
            "m1": m1_threshold,
            "m3": m3_threshold,
            "grid_start": 0.05,
            "grid_end": 0.95,
            "grid_step": 0.01,
            "numeric_tolerance": 1e-12,
            "selection_order": config["thresholds"]["selection_order"],
        },
        "router": {
            "scaler": "StandardScaler",
            "logistic_regression": settings,
            "positive_class": 1,
            "n_iter": int(router.n_iter_[0]),
            "converged": True,
        },
        "operating_point": {
            "nominal_call_rate": 0.15,
            "cutoff_count": count,
            "cutoff": cutoff,
            "comparator": ">=",
            "actual_route_count": int(np.sum(route_mask)),
            "actual_route_rate": float(np.mean(route_mask)),
            "cutoff_tie_count": int(np.sum(route_scores == cutoff)),
        },
        "input": {**config["input"], **{"source_order_sha256": input_identity["source_order_sha256"]}},
        "serialization": {
            "numeric_format": "NPZ with NPY members; content-canonical only",
            "npz_byte_hash_role": "this-run lineage identity",
            "allow_pickle": False,
            "array_schema": EXPECTED_BUNDLE_SCHEMA,
            "json": "UTF-8 sorted keys compact separators allow_nan=false terminal newline",
        },
        "access_attestation": config["access"],
        "no_performance_claim": True,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return output_arrays, bundle


def _create_bytes_once(path: Path, payload: bytes, mode: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
    except Exception:
        raise
    os.chmod(path, mode)


def _create_json_once(path: Path, value: Any, mode: int) -> None:
    _create_bytes_once(path, canonical_json_bytes(value), mode)


def _create_npz_once(path: Path, arrays: dict[str, np.ndarray]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as target:
            np.savez(target, **arrays)
            target.flush()
            os.fsync(target.fileno())
    except Exception:
        raise
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


def _freeze_sources(public_dir: Path, sources: dict[str, Path]) -> dict[str, Any]:
    frozen = public_dir / "frozen-sources"
    frozen.mkdir(mode=0o755)
    records: dict[str, Any] = {}
    for name in ("config", "protocol", "runner", "verifier", "tests"):
        source = sources[name]
        target_name = "config.json" if name == "config" else source.name
        target = frozen / target_name
        _create_bytes_once(target, source.read_bytes(), 0o644)
        records[name] = artifact_record(target)
    return records


def _assert_outputs_absent(public_dir: Path, private_dir: Path) -> None:
    for path in (public_dir, private_dir):
        if os.path.lexists(path):
            raise FileExistsError(f"EXP-064 output already exists: {path.relative_to(PROJECT_ROOT)}")
        _resolve_relative(path.relative_to(PROJECT_ROOT))


def preflight(config_path: Path) -> dict[str, Any]:
    config, sources = load_and_validate_config(config_path)
    public_dir = _resolve_relative(config["outputs"]["public_dir"])
    private_dir = _resolve_relative(config["outputs"]["private_dir"])
    _assert_outputs_absent(public_dir, private_dir)
    arrays, identity = validate_input(sources["input"], config)
    del arrays
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": "Ready",
        "rows": identity["rows"],
        "input_sha256": identity["sha256"],
        "source_order_sha256": identity["source_order_sha256"],
        "public_output_absent": True,
        "private_output_absent": True,
        "validation_access": False,
        "test_access": False,
    }


def execute(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    started_at = utc_now()
    started = time.perf_counter()
    config, sources = load_and_validate_config(config_path)
    config_record = artifact_record(config_path)
    public_dir = _resolve_relative(config["outputs"]["public_dir"])
    private_dir = _resolve_relative(config["outputs"]["private_dir"])
    _assert_outputs_absent(public_dir, private_dir)
    public_dir.mkdir(mode=0o755)
    os.chmod(public_dir, 0o755)
    private_dir.mkdir(mode=0o700)
    os.chmod(private_dir, 0o700)
    implementation = _freeze_sources(public_dir, sources)
    claim = {
        "schema_version": "exp-064-run-claim-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "status": "Claimed",
        "claimed_at_utc": started_at,
        "config": config_record,
        "outputs": {"public": str(PUBLIC_REL), "private_logical_name": RUN_ID},
        "one_shot": True,
    }
    _create_json_once(public_dir / "run-claim.json", claim, 0o644)
    try:
        arrays, input_identity = validate_input(sources["input"], config)
        output_arrays, bundle = fit_bundle(arrays, config, input_identity)
        parameters_path = private_dir / "router-parameters.npz"
        _create_npz_once(parameters_path, output_arrays)
        if npz_header_schema(parameters_path) != EXPECTED_BUNDLE_SCHEMA:
            raise RuntimeError("EXP-064 written parameter schema drift")
        parameters_record = artifact_record(parameters_path, include_path=False)
        bundle["numeric_npz"] = {"logical_name": "router-parameters.npz", **parameters_record}
        bundle_path = private_dir / "bundle.json"
        _create_json_once(bundle_path, bundle, 0o600)
        bundle_record = artifact_record(bundle_path, include_path=False)
        completed_at = utc_now()
        run = {
            "schema_version": "exp-064-run-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "tier": "Major",
            "rq_id": "RQ-S3",
            "stage": "seed42-full-oof-inference-bundle",
            "status": "CompletedAwaitingVerification",
            "started_at_utc": started_at,
            "completed_at_utc": completed_at,
            "elapsed_seconds": time.perf_counter() - started,
            "command": f"{sys.executable} {Path(__file__).relative_to(PROJECT_ROOT)} --config {config_path.relative_to(PROJECT_ROOT)}",
            "working_directory": str(PROJECT_ROOT),
            "input_identity": input_identity,
            "implementation": implementation,
            "legacy_lineage": config["legacy_lineage"],
            "contract": {
                "model_seed": 42,
                "rows": 3360,
                "label_count": 6,
                "feature_count": 14,
                "calibrator": "identity",
                "nominal_call_rate": 0.15,
                "no_performance_claim": True,
            },
            "private_outputs": {
                "router_parameters": {"logical_name": "router-parameters.npz", **parameters_record},
                "bundle_manifest": {"logical_name": "bundle.json", **bundle_record},
            },
            "access_attestation": {
                "paired_train_oof_accessed": True,
                "checkpoint_accessed": False,
                "raw_text_accessed": False,
                "validation_accessed": False,
                "test_accessed": False,
                "model_forward_executed": False,
            },
            "privacy": {"row_level_public": False, "public_scan_passed": True},
            "claim_boundary": CLAIM_BOUNDARY,
            "warnings": [],
        }
        violations = public_sensitive_paths(run)
        if violations:
            raise RuntimeError(f"EXP-064 public privacy schema violation: {violations}")
        _create_bytes_once(
            public_dir / "stdout.log",
            (
                f"{EXPERIMENT_ID} {RUN_ID}\n"
                "status=CompletedAwaitingVerification\n"
                "rows=3360\nvalidation_access=false\ntest_access=false\n"
            ).encode("utf-8"),
            0o644,
        )
        _create_json_once(public_dir / "run.json", run, 0o644)
        return run
    except Exception as error:
        failure = {
            "schema_version": "exp-064-private-failure-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "status": "Failed",
            "failed_at_utc": utc_now(),
            "error_type": type(error).__name__,
            "error": str(error),
        }
        if not os.path.lexists(private_dir / "failure.json"):
            _create_json_once(private_dir / "failure.json", failure, 0o600)
        public_failure = {
            "schema_version": "exp-064-run-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "tier": "Major",
            "rq_id": "RQ-S3",
            "stage": "seed42-full-oof-inference-bundle",
            "status": "Failed",
            "started_at_utc": started_at,
            "failed_at_utc": utc_now(),
            "error_type": type(error).__name__,
            "private_failure_recorded": True,
            "access_attestation": {
                "validation_accessed": False,
                "test_accessed": False,
            },
            "claim_boundary": CLAIM_BOUNDARY,
        }
        if not os.path.lexists(public_dir / "run.json"):
            _create_json_once(public_dir / "run.json", public_failure, 0o644)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = preflight(args.config) if args.check else execute(args.config)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
