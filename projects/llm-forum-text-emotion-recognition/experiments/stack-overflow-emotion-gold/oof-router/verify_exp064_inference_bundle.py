#!/usr/bin/env python3
"""Independently recompute and verify the EXP-064 inference bundle."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from typing import Any
import warnings
import zipfile

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


EXPERIMENT_ID = "EXP-064"
RUN_ID = "exp-064-seed42-inference-bundle"
CONFIG_SCHEMA = "exp-064-inference-bundle-config-v1"
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
INPUT_SCHEMA = {
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
PARAMETER_SCHEMA = {
    "scaler_mean": {"shape": [14], "dtype": "float64", "fortran_order": False},
    "scaler_var": {"shape": [14], "dtype": "float64", "fortran_order": False},
    "scaler_scale": {"shape": [14], "dtype": "float64", "fortran_order": False},
    "classes": {"shape": [2], "dtype": "int64", "fortran_order": False},
    "coef": {"shape": [1, 14], "dtype": "float64", "fortran_order": False},
    "intercept": {"shape": [1], "dtype": "float64", "fortran_order": False},
}
SENSITIVE_KEYS = {
    "sample_id", "sample_ids", "component_id", "component_ids", "gold", "logits",
    "m1_logits", "m3_logits", "probabilities", "predictions", "features", "targets",
    "route_scores", "route_mask", "text", "raw_text", "cutoff", "thresholds", "coef",
    "intercept", "scaler_mean", "scaler_var", "scaler_scale",
}
CLAIM_BOUNDARY = (
    "A seed-42 full-OOF inference artifact only; no same-data performance, independent-test, "
    "cross-seed deployment, production, forum-generalization, or emotion-mechanism claim."
)


def _project_root(source: Path) -> Path:
    for candidate in (source, *source.parents):
        if candidate.name == "llm-forum-text-emotion-recognition":
            return candidate
    raise RuntimeError("Could not locate project root")


PROJECT_ROOT = _project_root(Path(__file__).resolve())
BASE = Path("experiments/stack-overflow-emotion-gold/oof-router")
DEFAULT_CONFIG = PROJECT_ROOT / BASE / "configs/exp-064-seed42-inference-bundle.json"
PUBLIC_DIR = PROJECT_ROOT / BASE / "runs" / RUN_ID
PRIVATE_DIR = PROJECT_ROOT / BASE / "private" / RUN_ID


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _resolve(value: str | Path) -> Path:
    relative = Path(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"Unsafe relative path: {value}")
    cursor = PROJECT_ROOT
    for part in relative.parts:
        cursor = cursor / part
        if os.path.lexists(cursor) and stat.S_ISLNK(os.lstat(cursor).st_mode):
            raise ValueError(f"Path traverses symlink: {value}")
    resolved = (PROJECT_ROOT / relative).resolve()
    if not resolved.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return resolved


def _regular(path: Path, mode: int) -> os.stat_result:
    metadata = os.lstat(path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != mode
    ):
        raise ValueError(f"File type/mode drift: {path}")
    return metadata


def record(path: Path, include_path: bool = True) -> dict[str, Any]:
    metadata = os.lstat(path)
    value: dict[str, Any] = {
        "bytes": metadata.st_size,
        "sha256": sha256_file(path),
        "mode": f"{stat.S_IMODE(metadata.st_mode):04o}",
    }
    if include_path:
        value["path"] = str(path.relative_to(PROJECT_ROOT))
    return value


def require_record(value: dict[str, Any], mode: int) -> Path:
    if set(value) != {"path", "bytes", "sha256", "mode"}:
        raise ValueError("Source record schema drift")
    path = _resolve(value["path"])
    metadata = _regular(path, mode)
    if (
        metadata.st_size != value["bytes"]
        or value["mode"] != f"{mode:04o}"
        or sha256_file(path) != value["sha256"]
    ):
        raise ValueError(f"Source record identity drift: {value['path']}")
    return path


def load_json(path: Path, mode: int, *, require_canonical: bool = True) -> dict[str, Any]:
    _regular(path, mode)
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    if require_canonical and canonical_json_bytes(value) != raw:
        raise ValueError(f"Non-canonical JSON: {path}")
    return value


def npz_schema(path: Path) -> dict[str, dict[str, Any]]:
    schema: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        if len(members) != len(set(members)):
            raise ValueError("NPZ duplicate members")
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
                "shape": list(shape), "dtype": str(dtype), "fortran_order": bool(fortran)
            }
    return schema


def stable_sigmoid(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    result = np.empty_like(array)
    positive = array >= 0
    result[positive] = 1.0 / (1.0 + np.exp(-array[positive]))
    exponent = np.exp(array[~positive])
    result[~positive] = exponent / (1.0 + exponent)
    return result


def metrics(gold: np.ndarray, prediction: np.ndarray) -> tuple[float, float]:
    labels = np.asarray(gold, dtype=np.uint8)
    predicted = np.asarray(prediction, dtype=np.uint8)
    f1: list[float] = []
    for column in range(6):
        tp = int(np.sum((labels[:, column] == 1) & (predicted[:, column] == 1)))
        fp = int(np.sum((labels[:, column] == 0) & (predicted[:, column] == 1)))
        fn = int(np.sum((labels[:, column] == 1) & (predicted[:, column] == 0)))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return float(np.mean(f1)), float(np.mean(labels != predicted))


def choose_threshold(probabilities: np.ndarray, gold: np.ndarray) -> float:
    candidates: list[tuple[float, float, float]] = []
    for value in range(5, 96):
        threshold = value / 100.0
        macro, hamming = metrics(gold, (probabilities >= threshold).astype(np.uint8))
        candidates.append((threshold, macro, hamming))
    best_macro = max(row[1] for row in candidates)
    tied = [row for row in candidates if abs(row[1] - best_macro) <= 1e-12]
    best_hamming = min(row[2] for row in tied)
    tied = [row for row in tied if abs(row[2] - best_hamming) <= 1e-12]
    return sorted(tied, key=lambda row: (abs(row[0] - 0.5), row[0]))[0][0]


def features(
    probabilities: np.ndarray, threshold: float, characters: np.ndarray, tokens: np.ndarray
) -> np.ndarray:
    values = np.asarray(probabilities, dtype=np.float64)
    clipped = np.clip(values, 1e-15, 1.0 - 1e-15)
    entropy = -(clipped * np.log(clipped) + (1.0 - clipped) * np.log1p(-clipped))
    return np.ascontiguousarray(
        np.column_stack(
            [
                values,
                np.mean(entropy, axis=1),
                np.max(entropy, axis=1),
                np.min(np.abs(values - threshold), axis=1),
                np.sum(values >= threshold, axis=1),
                np.max(values, axis=1),
                np.min(values, axis=1),
                np.asarray(characters, dtype=np.float64),
                np.asarray(tokens, dtype=np.float64),
            ]
        ),
        dtype=np.float64,
    )


def target(m1: np.ndarray, m3: np.ndarray, gold: np.ndarray) -> np.ndarray:
    return (np.mean(m3 != gold, axis=1) < np.mean(m1 != gold, axis=1)).astype(np.uint8)


def cutoff(scores: np.ndarray) -> float:
    count = int(math.ceil(0.15 * len(scores)))
    return float(np.sort(np.asarray(scores, dtype=np.float64))[::-1][count - 1])


def _load_input(config: dict[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    contract = config["input"]
    path = require_record(contract["artifact"], 0o600)
    if npz_schema(path) != INPUT_SCHEMA or contract["array_schema"] != INPUT_SCHEMA:
        raise ValueError("Input NPZ schema drift")
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != set(INPUT_SCHEMA):
            raise ValueError("Input NPZ keys drift")
        sample_ids = np.asarray(archive["sample_ids"])
        component_ids = np.asarray(archive["component_ids"])
        folds = np.asarray(archive["fold_ids"], dtype=np.int8)
        arrays = {
            "gold": np.asarray(archive["gold"], dtype=np.uint8),
            "m1_logits": np.asarray(archive["m1_logits"], dtype=np.float32),
            "m3_logits": np.asarray(archive["m3_logits"], dtype=np.float32),
            "characters": np.asarray(archive["character_lengths"], dtype=np.int32),
            "tokens": np.asarray(archive["m1_token_lengths"], dtype=np.int32),
        }
    source_order = canonical_digest(sample_ids.tolist())
    if source_order != contract["source_order_sha256"] or len(set(sample_ids.tolist())) != 3360:
        raise ValueError("Input source order drift")
    if not np.all(np.isin(arrays["gold"], [0, 1])):
        raise ValueError("Gold is not binary")
    if not np.all(np.isfinite(arrays["m1_logits"])) or not np.all(np.isfinite(arrays["m3_logits"])):
        raise ValueError("Logits are non-finite")
    if np.any(arrays["characters"] < 0) or np.any(arrays["tokens"] < 0):
        raise ValueError("Negative length")
    if any(int(np.sum(folds == fold)) != 672 for fold in range(5)):
        raise ValueError("Fold row count drift")
    component_fold: dict[str, int] = {}
    for component, fold in zip(component_ids.tolist(), folds.tolist()):
        previous = component_fold.setdefault(component, int(fold))
        if previous != int(fold):
            raise ValueError("Component crosses folds")
    identity = {
        "logical_name": "seed42_paired_train_oof",
        "bytes": contract["artifact"]["bytes"],
        "sha256": contract["artifact"]["sha256"],
        "mode": "0600",
        "rows": 3360,
        "labels": 6,
        "array_schema_sha256": canonical_digest(INPUT_SCHEMA),
        "source_order_sha256": source_order,
    }
    return arrays, identity


def recompute(config: dict[str, Any], input_identity: dict[str, Any], arrays: dict[str, np.ndarray]) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    gold = arrays["gold"]
    m1_prob = stable_sigmoid(arrays["m1_logits"])
    m3_prob = stable_sigmoid(arrays["m3_logits"])
    tau_m1 = choose_threshold(m1_prob, gold)
    tau_m3 = choose_threshold(m3_prob, gold)
    pred_m1 = (m1_prob >= tau_m1).astype(np.uint8)
    pred_m3 = (m3_prob >= tau_m3).astype(np.uint8)
    y = target(pred_m1, pred_m3, gold)
    if np.unique(y).tolist() != [0, 1]:
        raise ValueError("Router target is not two-class")
    x = features(m1_prob, tau_m1, arrays["characters"], arrays["tokens"])
    scaler = StandardScaler()
    z = scaler.fit_transform(x)
    settings = config["router"]["logistic_regression"]
    model = LogisticRegression(**settings)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model.fit(z, y)
    if any(issubclass(item.category, ConvergenceWarning) for item in caught):
        raise ValueError("Independent logistic fit did not converge")
    scores = np.asarray(model.predict_proba(z)[:, 1], dtype=np.float64)
    manual = stable_sigmoid(z @ model.coef_[0] + model.intercept_[0])
    if not np.allclose(scores, manual, rtol=0.0, atol=1e-12):
        raise ValueError("Independent manual score mismatch")
    cut = cutoff(scores)
    mask = scores >= cut
    expected_arrays = {
        "scaler_mean": np.ascontiguousarray(scaler.mean_, dtype="<f8"),
        "scaler_var": np.ascontiguousarray(scaler.var_, dtype="<f8"),
        "scaler_scale": np.ascontiguousarray(scaler.scale_, dtype="<f8"),
        "classes": np.ascontiguousarray(model.classes_, dtype="<i8"),
        "coef": np.ascontiguousarray(model.coef_, dtype="<f8"),
        "intercept": np.ascontiguousarray(model.intercept_, dtype="<f8"),
    }
    expected_bundle = {
        "schema_version": BUNDLE_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "model_seed": 42,
        "status": "FittedAwaitingVerification",
        "labels": list(LABEL_ORDER),
        "features": list(FEATURE_NAMES),
        "calibration": {"m1": "identity", "m3": "identity", "sigmoid": "stable_float64"},
        "thresholds": {
            "m1": tau_m1,
            "m3": tau_m3,
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
            "n_iter": int(model.n_iter_[0]),
            "converged": True,
        },
        "operating_point": {
            "nominal_call_rate": 0.15,
            "cutoff_count": 504,
            "cutoff": cut,
            "comparator": ">=",
            "actual_route_count": int(np.sum(mask)),
            "actual_route_rate": float(np.mean(mask)),
            "cutoff_tie_count": int(np.sum(scores == cut)),
        },
        "input": {**config["input"], "source_order_sha256": input_identity["source_order_sha256"]},
        "serialization": {
            "numeric_format": "NPZ with NPY members; content-canonical only",
            "npz_byte_hash_role": "this-run lineage identity",
            "allow_pickle": False,
            "array_schema": PARAMETER_SCHEMA,
            "json": "UTF-8 sorted keys compact separators allow_nan=false terminal newline",
        },
        "access_attestation": config["access"],
        "no_performance_claim": True,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return expected_arrays, expected_bundle


def _typed_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(_typed_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            if key in SENSITIVE_KEYS:
                violations.append(child_path)
            violations.extend(public_sensitive_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    return violations


def _create(path: Path, payload: bytes, mode: int = 0o644) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as target_file:
        target_file.write(payload)
        target_file.flush()
        os.fsync(target_file.fileno())
    os.chmod(path, mode)


def verify(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    if config_path.resolve() != DEFAULT_CONFIG.resolve():
        raise ValueError("Verifier requires frozen EXP-064 config path")
    config = load_json(config_path, 0o644, require_canonical=False)
    if (
        config.get("schema_version") != CONFIG_SCHEMA
        or config.get("experiment_id") != EXPERIMENT_ID
        or config.get("run_id") != RUN_ID
        or config.get("labels") != list(LABEL_ORDER)
        or config.get("feature_contract", {}).get("ordered_features") != list(FEATURE_NAMES)
        or config.get("claim_boundary") != CLAIM_BOUNDARY
    ):
        raise ValueError("Verifier config identity drift")
    if stat.S_IMODE(os.lstat(PUBLIC_DIR).st_mode) != 0o755:
        raise ValueError("Public directory mode drift")
    if stat.S_IMODE(os.lstat(PRIVATE_DIR).st_mode) != 0o700:
        raise ValueError("Private directory mode drift")
    for terminal in ("verification.json", "VERIFICATION-SUMMARY.md", "bundle-complete.json"):
        if os.path.lexists(PUBLIC_DIR / terminal):
            raise FileExistsError(f"EXP-064 verification output already exists: {terminal}")
    claim = load_json(PUBLIC_DIR / "run-claim.json", 0o644)
    run = load_json(PUBLIC_DIR / "run.json", 0o644)
    _regular(PUBLIC_DIR / "stdout.log", 0o644)
    if claim.get("status") != "Claimed" or run.get("status") != "CompletedAwaitingVerification":
        raise ValueError("EXP-064 run state drift")
    if run.get("legacy_lineage") != config.get("legacy_lineage"):
        raise ValueError("EXP-064 public legacy lineage drift")
    if run.get("contract") != {
        "model_seed": 42,
        "rows": 3360,
        "label_count": 6,
        "feature_count": 14,
        "calibrator": "identity",
        "nominal_call_rate": 0.15,
        "no_performance_claim": True,
    }:
        raise ValueError("EXP-064 public contract drift")
    if public_sensitive_paths(claim) or public_sensitive_paths(run):
        raise ValueError("EXP-064 public privacy violation")
    source_map = {"config": config_path}
    for name, source_record in config["implementation"].items():
        source_map[name] = require_record(source_record, 0o644)
    for source_record in config["legacy_lineage"].values():
        require_record(source_record, 0o644)
    frozen_records = run.get("implementation", {})
    if set(frozen_records) != {"config", "protocol", "runner", "verifier", "tests"}:
        raise ValueError("Frozen source record set drift")
    for name, original in source_map.items():
        frozen_record = frozen_records[name]
        frozen_path = require_record(frozen_record, 0o644)
        if original.read_bytes() != frozen_path.read_bytes():
            raise ValueError(f"Frozen source bytes drift: {name}")
    arrays, input_identity = _load_input(config)
    expected_arrays, expected_bundle = recompute(config, input_identity, arrays)
    parameters_path = PRIVATE_DIR / "router-parameters.npz"
    bundle_path = PRIVATE_DIR / "bundle.json"
    _regular(parameters_path, 0o600)
    if npz_schema(parameters_path) != PARAMETER_SCHEMA:
        raise ValueError("EXP-064 parameter NPZ schema drift")
    with np.load(parameters_path, allow_pickle=False) as archive:
        if set(archive.files) != set(PARAMETER_SCHEMA):
            raise ValueError("EXP-064 parameter key drift")
        observed_arrays = {name: np.asarray(archive[name]) for name in archive.files}
    for name, expected in expected_arrays.items():
        observed = observed_arrays[name]
        if name == "classes":
            if not np.array_equal(observed, expected):
                raise ValueError("EXP-064 classes mismatch")
        elif not np.allclose(observed, expected, rtol=0.0, atol=1e-12):
            raise ValueError(f"EXP-064 numeric parameter mismatch: {name}")
    observed_bundle = load_json(bundle_path, 0o600)
    parameter_record = record(parameters_path, include_path=False)
    expected_bundle["numeric_npz"] = {"logical_name": "router-parameters.npz", **parameter_record}
    if not _typed_equal(observed_bundle, expected_bundle):
        raise ValueError("EXP-064 bundle JSON independent replay mismatch")
    private_outputs = run.get("private_outputs", {})
    if private_outputs != {
        "router_parameters": {"logical_name": "router-parameters.npz", **parameter_record},
        "bundle_manifest": {"logical_name": "bundle.json", **record(bundle_path, include_path=False)},
    }:
        raise ValueError("EXP-064 public/private cross-hash mismatch")
    if run.get("input_identity") != input_identity:
        raise ValueError("EXP-064 public input identity mismatch")
    access = run.get("access_attestation", {})
    if any(
        access.get(key) is not False
        for key in (
            "checkpoint_accessed", "raw_text_accessed", "validation_accessed",
            "test_accessed", "model_forward_executed",
        )
    ):
        raise ValueError("EXP-064 forbidden access attestation")
    checks = [
        "config_identity", "source_records", "legacy_lineage", "output_modes",
        "append_only_terminal_absence", "run_state", "public_privacy", "frozen_sources",
        "input_file_identity", "input_npz_schema", "source_order", "binary_gold",
        "finite_logits", "nonnegative_lengths", "fold_integrity", "stable_sigmoid",
        "m1_threshold", "m3_threshold", "strict_router_target", "feature_contract",
        "standard_scaler", "logistic_router", "manual_score_parity", "cutoff_and_ties",
        "parameter_npz_schema", "numeric_parameter_replay", "bundle_json_replay",
        "public_private_cross_hash", "access_boundary", "no_performance_claim",
    ]
    result = {
        "schema_version": "exp-064-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "status": "Passed",
        "verified_at_utc": utc_now(),
        "passed_count": len(checks),
        "failed_count": 0,
        "checks": checks,
        "input_identity": input_identity,
        "bundle_artifacts": private_outputs,
        "access_attestation": {
            "paired_train_oof_accessed": True,
            "checkpoint_accessed": False,
            "raw_text_accessed": False,
            "validation_accessed": False,
            "test_accessed": False,
            "model_forward_executed": False,
        },
        "no_performance_claim": True,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    if public_sensitive_paths(result):
        raise ValueError("EXP-064 verification privacy violation")
    summary = (
        "# EXP-064 Verification Summary\n\n"
        "- Status: `Passed`\n"
        f"- Checks: `{len(checks)}/{len(checks)}`\n"
        "- Artifact: seed-42 full-OOF inference bundle\n"
        "- Validation access: `false`\n"
        "- Test access: `false`\n"
        "- Performance claim: `none`\n\n"
        f"Claim boundary: {CLAIM_BOUNDARY}\n"
    ).encode("utf-8")
    verification_payload = canonical_json_bytes(result)
    _create(PUBLIC_DIR / "VERIFICATION-SUMMARY.md", summary)
    _create(PUBLIC_DIR / "verification.json", verification_payload)
    completion = {
        "schema_version": "exp-064-bundle-complete-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "status": "Complete",
        "completed_at_utc": utc_now(),
        "run": record(PUBLIC_DIR / "run.json"),
        "verification": record(PUBLIC_DIR / "verification.json"),
        "bundle_artifacts": private_outputs,
        "no_performance_claim": True,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    _create(PUBLIC_DIR / "bundle-complete.json", canonical_json_bytes(completion))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    try:
        result = verify(args.config)
    except Exception as error:
        if PUBLIC_DIR.exists() and not os.path.lexists(PUBLIC_DIR / "verification.json"):
            failed = {
                "schema_version": "exp-064-verification-v1",
                "experiment_id": EXPERIMENT_ID,
                "run_id": RUN_ID,
                "status": "Failed",
                "verified_at_utc": utc_now(),
                "passed_count": 0,
                "failed_count": 1,
                "error_type": type(error).__name__,
                "claim_boundary": CLAIM_BOUNDARY,
            }
            _create(PUBLIC_DIR / "verification.json", canonical_json_bytes(failed))
        raise
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
