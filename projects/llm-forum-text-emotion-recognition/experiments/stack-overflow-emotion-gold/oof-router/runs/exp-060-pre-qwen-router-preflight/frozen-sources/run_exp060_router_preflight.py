#!/usr/bin/env python3
"""Run the no-result contract preflight for EXP-060."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
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
PROHIBITED_MODEL_FEATURE_PREFIXES = (
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
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-060-router-preflight.json"


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
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))


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
    path = resolve_project(record["path"])
    if not path.is_file():
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


def binary_entropy(probabilities: np.ndarray) -> np.ndarray:
    values = np.asarray(probabilities, dtype=np.float64)
    clipped = np.clip(values, 1e-15, 1.0 - 1e-15)
    return -(clipped * np.log(clipped) + (1.0 - clipped) * np.log1p(-clipped))


def build_pre_qwen_features(
    m1_probabilities: np.ndarray,
    m1_thresholds: np.ndarray,
    character_lengths: np.ndarray,
    m1_token_lengths: np.ndarray,
) -> tuple[np.ndarray, tuple[str, ...]]:
    """Construct only the frozen 14 pre-Qwen feature columns."""
    probabilities = np.asarray(m1_probabilities, dtype=np.float64)
    thresholds = np.asarray(m1_thresholds, dtype=np.float64)
    characters = np.asarray(character_lengths, dtype=np.float64)
    tokens = np.asarray(m1_token_lengths, dtype=np.float64)
    if probabilities.ndim != 2 or probabilities.shape[1] != len(LABEL_ORDER):
        raise ValueError("M1 probability matrix must have six columns")
    rows = probabilities.shape[0]
    if thresholds.shape != (rows,) or characters.shape != (rows,) or tokens.shape != (rows,):
        raise ValueError("Threshold and length vectors must align with M1 rows")
    if not np.all(np.isfinite(probabilities)) or np.any((probabilities < 0) | (probabilities > 1)):
        raise ValueError("M1 probabilities must be finite values in [0, 1]")
    if not np.all(np.isfinite(thresholds)) or np.any((thresholds <= 0) | (thresholds >= 1)):
        raise ValueError("M1 thresholds must be finite values in (0, 1)")
    if np.any(characters < 0) or np.any(tokens < 0):
        raise ValueError("Length features must be non-negative")

    entropy = binary_entropy(probabilities)
    margin = np.min(np.abs(probabilities - thresholds[:, None]), axis=1)
    cardinality = np.sum(probabilities >= thresholds[:, None], axis=1)
    matrix = np.column_stack(
        [
            probabilities,
            np.mean(entropy, axis=1),
            np.max(entropy, axis=1),
            margin,
            cardinality,
            np.max(probabilities, axis=1),
            np.min(probabilities, axis=1),
            characters,
            tokens,
        ]
    ).astype(np.float64, copy=False)
    if matrix.shape != (rows, len(FEATURE_NAMES)) or not np.all(np.isfinite(matrix)):
        raise ValueError("Pre-Qwen feature matrix contract failed")
    return matrix, FEATURE_NAMES


def build_router_target(
    m1_prediction: np.ndarray,
    m3_prediction: np.ndarray,
    gold: np.ndarray,
) -> np.ndarray:
    m1 = np.asarray(m1_prediction, dtype=np.uint8)
    m3 = np.asarray(m3_prediction, dtype=np.uint8)
    labels = np.asarray(gold, dtype=np.uint8)
    if m1.shape != m3.shape or m1.shape != labels.shape or m1.ndim != 2:
        raise ValueError("Prediction and gold matrices must align")
    m1_loss = np.mean(m1 != labels, axis=1)
    m3_loss = np.mean(m3 != labels, axis=1)
    return (m3_loss < m1_loss).astype(np.uint8)


def score_cutoff(meta_train_scores: np.ndarray, target_rate: float) -> float:
    scores = np.asarray(meta_train_scores, dtype=np.float64)
    if scores.ndim != 1 or scores.size == 0 or not np.all(np.isfinite(scores)):
        raise ValueError("Route scores must be a non-empty finite vector")
    if not 0.0 <= target_rate <= 1.0:
        raise ValueError("Target call rate must be in [0, 1]")
    if target_rate == 0.0:
        return math.inf
    if target_rate == 1.0:
        return -math.inf
    count = max(1, int(math.ceil(target_rate * scores.size)))
    return float(np.sort(scores)[::-1][count - 1])


def apply_score_cutoff(scores: np.ndarray, cutoff: float) -> np.ndarray:
    values = np.asarray(scores, dtype=np.float64)
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("Held-out route scores must be a finite vector")
    return (values >= cutoff).astype(np.uint8)


class Checks:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, name: str, passed: bool, detail: Any = None) -> None:
        self.rows.append({"name": name, "passed": bool(passed), "detail": detail})

    @property
    def failed(self) -> list[dict[str, Any]]:
        return [row for row in self.rows if not row["passed"]]


def dependency_versions() -> dict[str, str]:
    result = {"python": platform.python_version()}
    for package in ("numpy", "scikit-learn"):
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = "not-installed"
    return result


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    return {"commit": commit, "dirty": bool(status), "dirty_path_count": len(status)}


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID or config.get("rq_id") != RQ_ID:
        raise ValueError("EXP-060 config identity drift")
    if tuple(config["data"]["label_order"]) != LABEL_ORDER:
        raise ValueError("Label order drift")
    for section in ("implementation", "prerequisites", "input"):
        for record in iter_records(config.get(section, {})):
            require_record(record)
    return config


def freeze_sources(run_dir: Path, config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    frozen = run_dir / "frozen-sources"
    frozen.mkdir(parents=True)
    sources = {"config": config_path}
    for key, record in config["implementation"].items():
        sources[key] = require_record(record)
    records: dict[str, Any] = {}
    for key, source in sources.items():
        target = frozen / source.name
        shutil.copy2(source, target)
        records[key] = artifact(target)
    return records


def run_preflight(config_path: Path) -> int:
    started = utc_now()
    config = load_config(config_path)
    run_dir = resolve_project(config["outputs"]["preflight_run_dir"])
    formal_run_dir = resolve_project(config["outputs"]["formal_run_dir"])
    formal_private_dir = resolve_project(config["outputs"]["formal_private_dir"])
    if run_dir.exists():
        raise FileExistsError(f"Append-only preflight output already exists: {run_dir}")

    checks = Checks()
    authorization = config["authorization"]
    checks.add("formal_router_training_forbidden", not authorization["formal_router_training"])
    checks.add("formal_result_computation_forbidden", not authorization["formal_result_computation"])
    checks.add("validation_access_forbidden", not authorization["validation_access"])
    checks.add("test_access_forbidden", not authorization["test_access"])
    checks.add("model_loading_or_forward_forbidden", not authorization["model_loading_or_forward"])
    checks.add("raw_text_access_forbidden", not authorization["raw_text_access"])
    checks.add("formal_public_output_empty", not formal_run_dir.exists(), display_path(formal_run_dir))
    checks.add("formal_private_output_empty", not formal_private_dir.exists(), display_path(formal_private_dir))

    paired_path = require_record(config["input"]["paired_oof"])
    actual_schema = npz_header_schema(paired_path)
    checks.add("paired_oof_header_schema", actual_schema == expected_paired_schema())
    checks.add("paired_oof_file_mode_0600", stat.S_IMODE(paired_path.stat().st_mode) == 0o600)
    checks.add("paired_oof_parent_mode_0700", stat.S_IMODE(paired_path.parent.stat().st_mode) == 0o700)

    calibration_path = require_record(config["prerequisites"]["exp059_calibration_parameters"])
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    selected = {
        family: calibration["families"][family]["selected_calibrator"] for family in ("m1", "m3")
    }
    temperatures = {
        family: calibration["families"][family]["final_temperature"] for family in ("m1", "m3")
    }
    checks.add("selected_calibrators_are_identity", selected == {"m1": "identity", "m3": "identity"}, selected)
    checks.add("selected_temperatures_are_one", temperatures == {"m1": 1.0, "m3": 1.0}, temperatures)

    features = tuple(config["feature_contract"]["ordered_features"])
    checks.add("feature_order_exact", features == FEATURE_NAMES, list(features))
    feature_violations = [
        name for name in features if any(name.startswith(prefix) for prefix in PROHIBITED_MODEL_FEATURE_PREFIXES)
    ]
    checks.add("feature_whitelist_has_no_prohibited_prefix", not feature_violations, feature_violations)
    checks.add("feature_count_14", len(features) == 14)
    checks.add("router_c_frozen", config["router"]["logistic_regression"]["C"] == 1.0)
    checks.add("router_hyperparameter_search_forbidden", not config["router"]["hyperparameter_search"])
    checks.add("outer_fold_contract", config["cross_fitting"]["outer_fold_ids"] == [0, 1, 2, 3, 4])
    checks.add("nested_threshold_contract", config["cross_fitting"]["nested_threshold_recomputation"])
    checks.add("call_rates_frozen", config["call_rates"] == [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0])
    checks.add("bootstrap_contract", config["bootstrap"] == {
        "unit": "duplicate_component",
        "repetitions": 2000,
        "seed": 20260817,
        "interval": "percentile_95",
    })

    versions = dependency_versions()
    checks.add("numpy_available", versions["numpy"] != "not-installed", versions["numpy"])
    checks.add("scikit_learn_available", versions["scikit-learn"] != "not-installed", versions["scikit-learn"])

    tests_path = require_record(config["implementation"]["tests"])
    test_result = subprocess.run(
        [sys.executable, str(tests_path)], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    checks.add("synthetic_contract_tests", test_result.returncode == 0, {
        "returncode": test_result.returncode,
        "stdout_tail": test_result.stdout[-2000:],
        "stderr_tail": test_result.stderr[-2000:],
    })

    run_dir.mkdir(parents=True)
    frozen_sources = freeze_sources(run_dir, config_path, config)
    contract = {
        "schema_version": "exp-060-preflight-contract-v1",
        "experiment_id": EXPERIMENT_ID,
        "result_bearing": False,
        "data_scope": "DATA-SO-TASK-V1 train OOF only",
        "input_schema": [
            {"array_name": name, **details} for name, details in sorted(actual_schema.items())
        ],
        "ordered_model_features": list(FEATURE_NAMES),
        "feature_count": len(FEATURE_NAMES),
        "prohibited_runtime_feature_classes": list(PROHIBITED_MODEL_FEATURE_PREFIXES),
        "selected_calibrators": selected,
        "nested_cross_fitting_required": True,
        "formal_router_training_authorized": False,
        "formal_result_computation_authorized": False,
        "validation_access": False,
        "test_access": False,
    }
    atomic_json(run_dir / "preflight-contract.json", contract)
    finished = utc_now()
    run_record = {
        "schema_version": "exp-060-preflight-run-v1",
        "experiment_id": EXPERIMENT_ID,
        "rq_id": RQ_ID,
        "tier": "Major infrastructure preflight",
        "stage": "no-result-preflight",
        "status": "Failed" if checks.failed else "Completed",
        "started_at": started,
        "finished_at": finished,
        "command": " ".join(sys.argv),
        "cwd": str(REPO_ROOT),
        "git": git_metadata(),
        "environment": versions,
        "authorization": authorization,
        "source_artifacts": frozen_sources,
        "input_artifacts": {
            "paired_oof": artifact(paired_path),
            "exp059_calibration_parameters": artifact(calibration_path),
        },
        "checks": {
            "passed": len(checks.rows) - len(checks.failed),
            "failed": len(checks.failed),
            "total": len(checks.rows),
            "records": checks.rows,
        },
        "execution_flags": {
            "real_features_constructed": False,
            "real_router_targets_constructed": False,
            "scaler_or_router_fitted": False,
            "router_metrics_computed": False,
            "bootstrap_computed": False,
            "validation_accessed": False,
            "test_accessed": False,
            "raw_text_accessed": False,
            "model_loaded_or_forward_run": False,
        },
        "outputs": {
            "contract": artifact(run_dir / "preflight-contract.json"),
        },
        "claim_boundary": "No-result protocol and environment preflight; no routing evidence.",
    }
    atomic_json(run_dir / "run.json", run_record)
    print(json.dumps({
        "status": run_record["status"],
        "checks_passed": run_record["checks"]["passed"],
        "checks_total": run_record["checks"]["total"],
        "run_dir": display_path(run_dir),
    }, sort_keys=True))
    return 1 if checks.failed else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_preflight(parse_args().config.resolve()))
