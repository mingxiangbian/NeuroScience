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
import resource
import shutil
import subprocess
import time
from typing import Any, Iterable
import zipfile

import numpy as np
from scipy.optimize import minimize_scalar


EXPERIMENT_ID = "EXP-059"
RQ_ID = "RQ-S3"
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
        raise ValueError("EXP-059 config identity drift")
    if tuple(config["data"]["label_order"]) != LABEL_ORDER:
        raise ValueError("Label order drift")
    for section in ("implementation", "prerequisites", "input"):
        for record in iter_records(config.get(section, {})):
            require_record(record)
    if config["authorization"]["validation_access"] or config["authorization"]["test_access"]:
        raise ValueError("EXP-059 config must forbid validation and test")
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
    figure.savefig(reliability_path, dpi=160)
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
    figure.savefig(risk_path, dpi=160)
    plt.close(figure)
    return reliability_path, risk_path


def write_report(
    path: Path,
    calibration: dict[str, Any],
    classification: dict[str, Any],
    gates: dict[str, Any],
    oracle: dict[str, Any],
    bootstrap: dict[str, Any],
) -> None:
    lines = [
        "# EXP-059 Cross-Fitted Calibration And Selective Prediction",
        "",
        "## Scope",
        "",
        "This report uses only the frozen EXP-058 paired train-OOF artifact. Validation and test were not accessed.",
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
            "EXP-059 can support claims about the frozen seed-42 pair's cross-fitted calibration and selective-risk ranking. "
            "It does not support a new test result, a three-seed stability claim, deployment benefit, context benefit, or an internal emotion mechanism.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


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


def preflight(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    run_dir = resolve_project(config["outputs"]["preflight_run_dir"])
    formal_public = resolve_project(config["outputs"]["public_run_dir"])
    formal_private = resolve_project(config["outputs"]["private_run_dir"])
    if run_dir.exists() or formal_public.exists() or formal_private.exists():
        raise FileExistsError("Refusing to overwrite EXP-059 preflight/formal outputs")
    input_path = require_record(config["input"]["paired_oof"])
    schema = npz_header_schema(input_path)
    if schema != expected_input_schema():
        raise ValueError(f"Paired OOF header schema drift: {schema}")
    exp058_verification = json.loads(
        require_record(config["prerequisites"]["exp058_verification"]).read_text(encoding="utf-8")
    )
    if exp058_verification.get("status") != "Passed" or exp058_verification.get("failed_count") != 0:
        raise ValueError("EXP-058 final verification is not passed")
    versions = dependency_versions()
    if any(versions[name] == "not-installed" for name in ("numpy", "scipy", "matplotlib")):
        raise RuntimeError("EXP-059 analysis dependencies are incomplete")
    run_dir.mkdir(parents=True)
    frozen = freeze_sources(run_dir, config_path, config)
    run = {
        "schema_version": "exp-059-preflight-run-v1",
        "experiment_id": EXPERIMENT_ID,
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
    if public_sensitive_paths(run):
        raise ValueError("Preflight public privacy violation")
    atomic_json(run_dir / "run.json", run)
    return run


def formal_run(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    if not config["authorization"]["formal_analysis"]:
        raise PermissionError("Formal EXP-059 analysis is not authorized")
    preflight_verification = json.loads(
        require_record(config["prerequisites"]["preflight_verification"]).read_text(encoding="utf-8")
    )
    if preflight_verification.get("status") != "Passed" or preflight_verification.get("failed_count") != 0:
        raise ValueError("EXP-059 preflight verification is not passed")
    run_dir = resolve_project(config["outputs"]["public_run_dir"])
    private_dir = resolve_project(config["outputs"]["private_run_dir"])
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
    parameters_public: dict[str, Any] = {"families": {}}
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
        parameters_public["families"][family] = {
            "fold_fits": result["fold_fits"],
            "full_oof_temperature_fit": result["full_fit"],
            "selected_calibrator": "temperature" if result["temperature_accepted"] else "identity",
            "final_temperature": result["final_temperature"],
            "final_global_threshold": result["final_threshold_selection"],
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
    )
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
        "experiment_id": EXPERIMENT_ID,
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
    violations = public_sensitive_paths(run)
    if violations:
        raise ValueError(f"Public run privacy violation: {violations}")
    atomic_json(run_dir / "run.json", run)
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
    if args.stage == "preflight":
        result = preflight(config_path, config)
    else:
        result = formal_run(config_path, config)
    print(json.dumps({"stage": args.stage, "status": result["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
