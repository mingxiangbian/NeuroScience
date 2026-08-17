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
import stat
import struct
from typing import Any, Iterable
import zipfile

import numpy as np
from scipy.optimize import minimize_scalar


EXPERIMENT_ID = "EXP-059"
RQ_ID = "RQ-S3"
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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_project(value: str) -> Path:
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


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def require_record(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Frozen artifact drift: {path}")
    return path


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


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID or config.get("rq_id") != RQ_ID:
        raise ValueError("Unexpected EXP-059 config identity")
    if tuple(config["data"]["label_order"]) != LABELS:
        raise ValueError("Label order drift")
    for section in ("implementation", "prerequisites", "input"):
        for record in iter_records(config.get(section, {})):
            require_record(record)
    if config["authorization"]["validation_access"] or config["authorization"]["test_access"]:
        raise ValueError("EXP-059 may not access validation or test")
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


def expected_results(data: dict[str, np.ndarray], config: dict[str, Any]) -> dict[str, Any]:
    gold = data["gold"]
    folds = data["fold_ids"]
    family_results = {
        family: crossfit_family(data[f"{family}_logits"], gold, folds, config)
        for family in FAMILIES
    }
    reliability_rows = []
    calibration_public = {"families": {}}
    parameters_public = {"families": {}}
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
        parameters_public["families"][family] = {
            "fold_fits": result["fold_fits"],
            "full_oof_temperature_fit": result["full_fit"],
            "selected_calibrator": "temperature" if result["temperature_accepted"] else "identity",
            "final_temperature": result["final_temperature"],
            "final_global_threshold": result["final_threshold_selection"],
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


def verification_result(scope: str, checks: Checks) -> dict[str, Any]:
    return {
        "schema_version": "exp-059-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "rq_id": RQ_ID,
        "scope": scope,
        "status": "Passed" if not checks.failed else "Failed",
        "verified_at_utc": utc_now(),
        "passed_count": len(checks.rows) - len(checks.failed),
        "failed_count": len(checks.failed),
        "checks": checks.rows,
    }


def write_summary(path: Path, result: dict[str, Any]) -> None:
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
    path.write_text("\n".join(lines), encoding="utf-8")


def verify_preflight(config: dict[str, Any]) -> dict[str, Any]:
    run_dir = resolve_project(config["outputs"]["preflight_run_dir"])
    output = run_dir / "verification.json"
    summary = run_dir / "VERIFICATION-SUMMARY.md"
    if output.exists() or summary.exists():
        raise FileExistsError("Refusing to overwrite append-only preflight verification")
    checks = Checks()
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    schema = npz_header_schema(require_record(config["input"]["paired_oof"]))
    exp058 = json.loads(require_record(config["prerequisites"]["exp058_verification"]).read_text(encoding="utf-8"))
    checks.add("preflight.identity", run.get("experiment_id") == EXPERIMENT_ID and run.get("rq_id") == RQ_ID)
    checks.add("preflight.status", run.get("status") == "CompletedAwaitingVerification")
    checks.add("preflight.header_schema", schema == expected_schema(), schema)
    checks.add("preflight.public_schema", run.get("input_schema") == public_schema_records(schema))
    checks.add("preflight.exp058_passed", exp058.get("status") == "Passed" and exp058.get("failed_count") == 0 and exp058.get("passed_count") == 26989)
    checks.add("preflight.no_values", run.get("array_values_loaded") is False)
    checks.add("preflight.no_metrics", run.get("performance_metrics_computed") is False)
    checks.add("preflight.no_analysis", run.get("formal_analysis_performed") is False)
    checks.add("preflight.no_validation", run["split_access"].get("validation_accessed") is False)
    checks.add("preflight.no_test_inputs", run["split_access"].get("test_inputs_accessed") is False)
    checks.add("preflight.no_test_labels", run["split_access"].get("test_labels_accessed") is False)
    checks.add("preflight.header_only_split", run["split_access"].get("accessed_splits") == ["train-oof-header"])
    checks.add("preflight.input_bound", run.get("input") == artifact(require_record(config["input"]["paired_oof"])))
    checks.add("preflight.privacy", not public_sensitive_paths(run), public_sensitive_paths(run))
    checks.add("preflight.formal_public_absent", not resolve_project(config["outputs"]["public_run_dir"]).exists())
    checks.add("preflight.formal_private_absent", not resolve_project(config["outputs"]["private_run_dir"]).exists())
    checks.add("preflight.runtime", all(run["dependencies"].get(name) != "not-installed" for name in ("numpy", "scipy", "matplotlib")))
    for name, record in run.get("frozen_sources", {}).items():
        path = resolve_project(record["path"])
        checks.add(f"preflight.frozen_source.{name}", path.is_file() and artifact(path) == record)
    result = verification_result("preflight", checks)
    atomic_json(output, result)
    write_summary(summary, result)
    return result


def verify_final(config: dict[str, Any]) -> dict[str, Any]:
    run_dir = resolve_project(config["outputs"]["public_run_dir"])
    private_dir = resolve_project(config["outputs"]["private_run_dir"])
    output = run_dir / "verification.json"
    summary = run_dir / "VERIFICATION-SUMMARY.md"
    if output.exists() or summary.exists():
        raise FileExistsError("Refusing to overwrite append-only final verification")
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
    checks.add("run.identity", run.get("experiment_id") == EXPERIMENT_ID and run.get("rq_id") == RQ_ID)
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
    checks.add("run.privacy", not public_sensitive_paths(run), public_sensitive_paths(run))
    for name, record in run.get("public_outputs", {}).items():
        path = resolve_project(record["path"])
        checks.add(f"run.public_output.{name}", path.is_file() and artifact(path) == record)
    for name, record in run.get("frozen_sources", {}).items():
        path = resolve_project(record["path"])
        checks.add(f"run.frozen_source.{name}", path.is_file() and artifact(path) == record)
    for filename in ("reliability-diagram.png", "risk-coverage-curve.png"):
        path = run_dir / filename
        try:
            dimensions = png_dimensions(path)
            checks.add(f"figure.{filename}.dimensions", dimensions == (1600, 640), dimensions)
        except (OSError, ValueError) as error:
            checks.add(f"figure.{filename}.valid", False, str(error))
    checks.add("resource.wall_budget", float(run["resources"]["wall_seconds"]) <= float(config["resources"]["formal_wall_seconds"]))
    checks.add("resource.memory_budget", float(run["resources"]["peak_process_rss_gb"]) <= float(config["resources"]["peak_memory_gb"]))
    checks.add("resource.api_cost", run["resources"].get("api_cost_usd") == 0)
    for path in sorted(run_dir.iterdir()):
        if path.suffix == ".json" and path.name not in {"verification.json"}:
            value = json.loads(path.read_text(encoding="utf-8"))
            checks.add(f"privacy.{path.name}", not public_sensitive_paths(value), public_sensitive_paths(value))
    result = verification_result("final", checks)
    atomic_json(output, result)
    write_summary(summary, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify EXP-059 artifacts independently")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--scope", choices=("preflight", "final"), required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config.resolve())
    result = verify_preflight(config) if args.scope == "preflight" else verify_final(config)
    print(json.dumps({"scope": args.scope, "status": result["status"], "passed": result["passed_count"], "failed": result["failed_count"]}, sort_keys=True))
    if result["status"] != "Passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
