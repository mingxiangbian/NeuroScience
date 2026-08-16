#!/usr/bin/env python3
"""Shared, frozen primitives for the EXP-056 Stack Overflow test gate."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Iterable, Sequence

import numpy as np


LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
TEST_INPUT_FIELDS = {
    "schema_version", "protocol_id", "sample_id", "component_id", "text",
}
TEST_LABEL_FIELDS = {"schema_version", "protocol_id", "sample_id", "labels"}
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_project(value: str | Path) -> Path:
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "path": display_path(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def tree_artifact(path: Path) -> dict[str, Any]:
    if not path.is_dir():
        raise FileNotFoundError(path)
    files = []
    for file_path in sorted(value for value in path.rglob("*") if value.is_file()):
        relative = str(file_path.relative_to(path))
        record = {
            "path": relative,
            "bytes": file_path.stat().st_size,
            "sha256": sha256_file(file_path),
        }
        files.append(record)
    return {
        "path": display_path(path),
        "file_count": len(files),
        "total_bytes": sum(record["bytes"] for record in files),
        "sha256": canonical_digest(files),
        "files": files,
    }


def require_artifact(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]):
        raise ValueError(f"Frozen artifact byte drift: {path}")
    if sha256_file(path) != record["sha256"]:
        raise ValueError(f"Frozen artifact hash drift: {path}")
    return path


def require_tree(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    observed = tree_artifact(path)
    for key in ("path", "file_count", "sha256", "files"):
        if observed.get(key) != record.get(key):
            raise ValueError(f"Frozen artifact tree drift: {path} ({key})")
    if "total_bytes" in record and observed["total_bytes"] != record["total_bytes"]:
        raise ValueError(f"Frozen artifact tree drift: {path} (total_bytes)")
    return path


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_frozen_json(record: dict[str, Any]) -> dict[str, Any]:
    return load_json(require_artifact(record))


def atomic_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if private:
        os.chmod(temporary, 0o600)
    temporary.replace(path)
    if private:
        os.chmod(path, 0o600)


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]], *, private: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
    if private:
        os.chmod(temporary, 0o600)
    temporary.replace(path)
    if private:
        os.chmod(path, 0o600)


def dynamic_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def path_is_gitignored(path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(path)],
        cwd=REPO_ROOT,
        check=False,
    )
    return result.returncode == 0


def verify_authorization(
    contract: dict[str, Any], authorization_path: Path
) -> dict[str, Any]:
    if not authorization_path.is_file():
        raise PermissionError("EXP-056 test access has not been explicitly authorized")
    authorization = load_json(authorization_path)
    expected = {
        "schema_version": "exp-056-test-authorization-v1",
        "experiment_id": "EXP-056",
        "authorized": True,
        "contract_sha256": sha256_file(resolve_project(contract["contract_path"])),
        "scope": "one_time_stack_overflow_test_execution_for_all_12_frozen_units",
    }
    for key, value in expected.items():
        if authorization.get(key) != value:
            raise PermissionError(f"Authorization field drift: {key}")
    if not isinstance(authorization.get("authorized_at_utc"), str):
        raise PermissionError("Authorization timestamp is missing")
    if not isinstance(authorization.get("user_instruction"), str) or not authorization["user_instruction"].strip():
        raise PermissionError("Authorization does not preserve the user instruction")
    return authorization


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from error
    return rows


def load_test_inputs(
    contract: dict[str, Any], authorization_path: Path
) -> list[dict[str, Any]]:
    verify_authorization(contract, authorization_path)
    record = contract["data"]["test_inputs"]
    path = resolve_project(record["path"])
    if path.stat().st_size != record["bytes"] or sha256_file(path) != record["sha256"]:
        raise ValueError("Frozen test input drift")
    rows = _load_jsonl(path)
    if len(rows) != contract["data"]["test_rows"]:
        raise ValueError("Test input row-count drift")
    seen: set[str] = set()
    for row in rows:
        if set(row) != TEST_INPUT_FIELDS:
            raise ValueError("Test input schema drift")
        if row["schema_version"] != "so-emotion-c0-v1":
            raise ValueError("Test input schema version drift")
        if row["protocol_id"] != contract["data"]["protocol_id"]:
            raise ValueError("Test input protocol drift")
        if not isinstance(row["text"], str) or not row["text"].strip():
            raise ValueError("Test input contains empty text")
        if row["sample_id"] in seen:
            raise ValueError("Test input sample IDs are not unique")
        seen.add(row["sample_id"])
    return rows


def load_test_labels_after_prediction_seal(
    contract: dict[str, Any], authorization_path: Path, prediction_seal: dict[str, Any]
) -> list[dict[str, Any]]:
    verify_authorization(contract, authorization_path)
    if prediction_seal.get("status") != "Predictions sealed before labels opened":
        raise PermissionError("All 12 predictions must be sealed before labels are opened")
    if prediction_seal.get("unit_ids") != contract["unit_order"]:
        raise PermissionError("Prediction seal unit order drift")
    record = contract["data"]["test_labels"]
    path = resolve_project(record["path"])
    if path.stat().st_size != record["bytes"] or sha256_file(path) != record["sha256"]:
        raise ValueError("Frozen test label drift")
    rows = _load_jsonl(path)
    if len(rows) != contract["data"]["test_rows"]:
        raise ValueError("Test label row-count drift")
    seen: set[str] = set()
    for row in rows:
        if set(row) != TEST_LABEL_FIELDS:
            raise ValueError("Test label schema drift")
        if row["schema_version"] != "so-emotion-c0-test-label-v1":
            raise ValueError("Test label schema version drift")
        if row["protocol_id"] != contract["data"]["protocol_id"]:
            raise ValueError("Test label protocol drift")
        labels = row["labels"]
        if len(labels) != len(LABELS) or any(value not in (0, 1) for value in labels):
            raise ValueError("Test label vector drift")
        if row["sample_id"] in seen:
            raise ValueError("Test label sample IDs are not unique")
        seen.add(row["sample_id"])
    return rows


def sigmoid(logits: np.ndarray) -> np.ndarray:
    logits = np.asarray(logits, dtype=np.float32)
    result = np.empty_like(logits)
    positive = logits >= 0
    result[positive] = 1.0 / (1.0 + np.exp(-logits[positive]))
    exp_value = np.exp(logits[~positive])
    result[~positive] = exp_value / (1.0 + exp_value)
    return result


def metric_bundle(gold: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    gold = np.asarray(gold, dtype=np.uint8)
    predicted = np.asarray(predicted, dtype=np.uint8)
    if gold.shape != predicted.shape or gold.ndim != 2 or gold.shape[1] != len(LABELS):
        raise ValueError("Metric array shape drift")
    tp = np.sum((gold == 1) & (predicted == 1), axis=0, dtype=np.int64)
    fp = np.sum((gold == 0) & (predicted == 1), axis=0, dtype=np.int64)
    fn = np.sum((gold == 1) & (predicted == 0), axis=0, dtype=np.int64)
    tn = np.sum((gold == 0) & (predicted == 0), axis=0, dtype=np.int64)
    precision = np.divide(tp, tp + fp, out=np.zeros(6), where=(tp + fp) != 0)
    recall = np.divide(tp, tp + fn, out=np.zeros(6), where=(tp + fn) != 0)
    f1 = np.divide(2 * tp, 2 * tp + fp + fn, out=np.zeros(6), where=(2 * tp + fp + fn) != 0)
    support = tp + fn
    denominator = 2 * tp.sum() + fp.sum() + fn.sum()
    cardinality = predicted.sum(axis=1)
    without_surprise = [0, 1, 3, 4, 5]
    return {
        "subset_accuracy": float(np.mean(np.all(gold == predicted, axis=1))),
        "accuracy_definition": "strict subset/exact-match accuracy",
        "hamming_loss": float(np.mean(gold != predicted)),
        "macro_precision": float(precision.mean()),
        "macro_recall": float(recall.mean()),
        "macro_f1": float(f1.mean()),
        "micro_f1": float(2 * tp.sum() / denominator) if denominator else 0.0,
        "weighted_f1": float(np.sum(f1 * support) / support.sum()) if support.sum() else 0.0,
        "five_label_macro_f1_without_surprise": float(f1[without_surprise].mean()),
        "per_label": {
            label: {
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
                "predicted_support": int(tp[index] + fp[index]),
                "tn": int(tn[index]),
                "fp": int(fp[index]),
                "fn": int(fn[index]),
                "tp": int(tp[index]),
            }
            for index, label in enumerate(LABELS)
        },
        "empty_prediction_rows": int(np.sum(cardinality == 0)),
        "empty_prediction_rate": float(np.mean(cardinality == 0)),
        "predicted_label_cardinality_mean": float(np.mean(cardinality)),
    }


def aggregate_values(values: Sequence[float]) -> dict[str, Any]:
    array = np.asarray(values, dtype=np.float64)
    if len(array) != 3:
        raise ValueError("Formal family aggregation requires exactly three seeds")
    return {
        "values": [float(value) for value in array],
        "mean": float(array.mean()),
        "sample_std": float(array.std(ddof=1)),
        "n": 3,
    }


def save_prediction_npz(
    path: Path,
    sample_ids: Sequence[str],
    component_ids: Sequence[str],
    probabilities: np.ndarray,
    predicted: np.ndarray,
    *,
    parser_valid: np.ndarray | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    maximum_sample = max(len(value) for value in sample_ids)
    maximum_component = max(len(value) for value in component_ids)
    payload: dict[str, np.ndarray] = {
        "sample_ids": np.asarray(sample_ids, dtype=f"<U{maximum_sample}"),
        "component_ids": np.asarray(component_ids, dtype=f"<U{maximum_component}"),
        "probabilities": np.asarray(probabilities, dtype=np.float32),
        "predicted": np.asarray(predicted, dtype=np.uint8),
    }
    if parser_valid is not None:
        payload["parser_valid"] = np.asarray(parser_valid, dtype=np.uint8)
    temporary = path.with_name(path.name + ".tmp.npz")
    np.savez_compressed(temporary, **payload)
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)


def load_prediction_npz(path: Path, expected_rows: int) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as source:
        payload = {name: source[name] for name in source.files}
    required = {"sample_ids", "component_ids", "probabilities", "predicted"}
    if not required.issubset(payload):
        raise ValueError(f"Prediction artifact schema drift: {path}")
    if payload["probabilities"].shape != (expected_rows, len(LABELS)):
        raise ValueError(f"Prediction probability shape drift: {path}")
    if payload["predicted"].shape != (expected_rows, len(LABELS)):
        raise ValueError(f"Prediction vector shape drift: {path}")
    if payload["sample_ids"].shape != (expected_rows,) or payload["component_ids"].shape != (expected_rows,):
        raise ValueError(f"Prediction ID shape drift: {path}")
    if not np.isfinite(payload["probabilities"]).all():
        raise ValueError(f"Non-finite prediction probability: {path}")
    if np.any((payload["predicted"] != 0) & (payload["predicted"] != 1)):
        raise ValueError(f"Non-binary prediction vector: {path}")
    return payload
