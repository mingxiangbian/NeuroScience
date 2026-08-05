#!/usr/bin/env python3
"""Independently verify EXP-034 without importing its runner."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
from itertools import zip_longest
import json
import math
import os
from pathlib import Path
import time
from typing import Any

import numpy as np

EXPERIMENT_ID = "EXP-034"
VERIFICATION_ID = "EXP-034-VERIFY-V1"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
CONFIG_PATH = SCRIPT_DIR / "configs" / "exp-034-train-neutral-cooccurrence-diagnostic.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{time.time_ns()}")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": str(path.resolve().relative_to(PROJECT_ROOT.resolve())),
        "sha256": sha256_file(path),
    }


def verify_spec(spec: dict[str, Any]) -> None:
    path = resolve_project_path(str(spec["path"]))
    if sha256_file(path) != spec["sha256"]:
        raise ValueError(f"Frozen artifact drift: {path}")


def strict_parse(output: str, labels: tuple[str, ...]) -> dict[str, Any]:
    try:
        decoded = json.loads(output.strip())
    except json.JSONDecodeError:
        return {"canonical_output": None, "error": "invalid-json", "labels": []}
    if not isinstance(decoded, dict) or set(decoded) != {"labels"}:
        return {"canonical_output": None, "error": "wrong-object", "labels": []}
    values = decoded["labels"]
    if not isinstance(values, list) or not values:
        return {"canonical_output": None, "error": "labels-not-nonempty-list", "labels": []}
    if not all(isinstance(value, str) for value in values):
        return {"canonical_output": None, "error": "non-string-label", "labels": []}
    if len(values) != len(set(values)):
        return {"canonical_output": None, "error": "duplicate-label", "labels": []}
    if any(value not in labels for value in values):
        return {"canonical_output": None, "error": "unknown-label", "labels": []}
    return {
        "canonical_output": json.dumps({"labels": values}, separators=(",", ":")),
        "error": None,
        "labels": values,
    }


def independently_load_gold(
    config: dict[str, Any], labels: tuple[str, ...]
) -> list[dict[str, Any]]:
    source_path = resolve_project_path(config["data"]["source_train"]["path"])
    prepared_path = resolve_project_path(config["data"]["prepared_train"]["path"])
    neutral_id = labels.index("neutral")
    selected: list[dict[str, Any]] = []
    source_rows = 0
    with source_path.open("r", encoding="utf-8", newline="") as source_handle, prepared_path.open(
        "r", encoding="utf-8"
    ) as prepared_handle:
        source_reader = csv.reader(source_handle, delimiter="\t")
        for row_number, pair in enumerate(
            zip_longest(source_reader, prepared_handle, fillvalue=None), start=1
        ):
            source_row, prepared_line = pair
            if source_row is None or prepared_line is None or len(source_row) != 3:
                raise ValueError(f"Source/prepared alignment failed at row {row_number}")
            source_rows = row_number
            _, encoded_labels, comment_id = source_row
            gold_ids = [int(value) for value in encoded_labels.split(",")]
            prepared = json.loads(prepared_line)
            messages = prepared.get("messages")
            if not isinstance(messages, list) or len(messages) != 3:
                raise ValueError(f"Prepared message drift at row {row_number}")
            target = json.loads(messages[2]["content"])
            if target != {"labels": [labels[value] for value in gold_ids]}:
                raise ValueError(f"Prepared target drift at row {row_number}")
            if neutral_id in gold_ids and len(gold_ids) > 1:
                selected.append(
                    {
                        "comment_id_sha256": sha256_text(comment_id),
                        "gold_label_ids": gold_ids,
                        "source_row_number": row_number,
                    }
                )
    row_hash = sha256_text(",".join(str(row["source_row_number"]) for row in selected))
    if (
        source_rows != int(config["data"]["source_train"]["rows"])
        or len(selected) != int(config["scope"]["expected_rows"])
        or row_hash != config["scope"]["source_row_numbers_sha256"]
    ):
        raise ValueError("Independent EXP-034 slice membership drift")
    return selected


def build_matrices(
    records: list[dict[str, Any]], selected: list[dict[str, Any]], labels: tuple[str, ...]
) -> tuple[np.ndarray, np.ndarray]:
    if len(records) != len(selected):
        raise ValueError("EXP-034 record count differs from frozen slice")
    gold = np.zeros((len(records), len(labels)), dtype=np.uint8)
    predicted = np.zeros_like(gold)
    label_to_id = {label: index for index, label in enumerate(labels)}
    forbidden_keys = {"input", "messages", "text", "comment_id"}
    for index, (record, expected) in enumerate(zip(records, selected, strict=True)):
        if forbidden_keys & set(record):
            raise ValueError("Public prediction checkpoint contains raw input fields")
        raw_output = record.get("raw_output")
        if not isinstance(raw_output, str):
            raise ValueError(f"Missing raw output at slice row {index + 1}")
        parsed = strict_parse(raw_output, labels)
        valid = parsed["error"] is None and record.get("finish_reason") == "stop"
        error = parsed["error"] if record.get("finish_reason") == "stop" else "length-terminated"
        predicted_labels = parsed["labels"] if valid else []
        predicted_ids = [label_to_id[label] for label in predicted_labels]
        if (
            record.get("row_number") != index + 1
            or record.get("source_row_number") != expected["source_row_number"]
            or record.get("comment_id_sha256") != expected["comment_id_sha256"]
            or record.get("gold_label_ids") != expected["gold_label_ids"]
            or record.get("gold_labels")
            != [labels[value] for value in expected["gold_label_ids"]]
            or record.get("predicted_labels") != predicted_labels
            or record.get("predicted_label_ids") != predicted_ids
            or record.get("parser_valid") is not valid
            or record.get("parser_error") != error
            or record.get("canonical_output")
            != (parsed["canonical_output"] if valid else None)
            or record.get("output_sha256") != sha256_text(raw_output)
            or record.get("output_character_count") != len(raw_output)
        ):
            raise ValueError(f"Prediction evidence drift at slice row {index + 1}")
        gold[index, expected["gold_label_ids"]] = 1
        predicted[index, predicted_ids] = 1
    return gold, predicted


def divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    return np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator, dtype=np.float64),
        where=denominator != 0,
    )


def independent_metrics(
    gold: np.ndarray, predicted: np.ndarray, labels: tuple[str, ...]
) -> dict[str, Any]:
    gold_bool = gold.astype(bool)
    predicted_bool = predicted.astype(bool)
    tp = np.sum(gold_bool & predicted_bool, axis=0, dtype=np.int64)
    fp = np.sum(~gold_bool & predicted_bool, axis=0, dtype=np.int64)
    fn = np.sum(gold_bool & ~predicted_bool, axis=0, dtype=np.int64)
    per_label_f1 = divide(2 * tp, 2 * tp + fp + fn)
    micro_tp = int(tp.sum())
    micro_fp = int(fp.sum())
    micro_fn = int(fn.sum())
    sample_tp = np.sum(gold_bool & predicted_bool, axis=1, dtype=np.int64)
    gold_cardinality = np.sum(gold_bool, axis=1, dtype=np.int64)
    predicted_cardinality = np.sum(predicted_bool, axis=1, dtype=np.int64)
    neutral = labels.index("neutral")
    structural = predicted_bool[:, neutral] & (predicted_cardinality > 1)
    non_neutral = np.ones(len(labels), dtype=bool)
    non_neutral[neutral] = False
    correct_non_neutral = np.any(
        predicted_bool[:, non_neutral] & gold_bool[:, non_neutral], axis=1
    )
    target_compatible = structural & correct_non_neutral
    return {
        "macro_f1": float(per_label_f1.mean()),
        "micro_f1": float(
            2 * micro_tp / (2 * micro_tp + micro_fp + micro_fn)
            if 2 * micro_tp + micro_fp + micro_fn
            else 0.0
        ),
        "neutral_coprediction_rate": float(structural.mean()),
        "neutral_coprediction_rows": int(structural.sum()),
        "predicted_cardinality_distribution": {
            str(int(key)): int(value)
            for key, value in sorted(Counter(predicted_cardinality.tolist()).items())
        },
        "predicted_label_cardinality": float(predicted_cardinality.mean()),
        "samples_f1": float(
            np.mean(divide(2 * sample_tp, gold_cardinality + predicted_cardinality))
        ),
        "subset_accuracy": float(np.mean(np.all(gold_bool == predicted_bool, axis=1))),
        "target_compatible_coprediction_rate": float(target_compatible.mean()),
        "target_compatible_coprediction_rows": int(target_compatible.sum()),
    }


def require_close(actual: Any, expected: Any, name: str) -> None:
    if isinstance(expected, float):
        if not isinstance(actual, (int, float)) or not math.isclose(
            float(actual), expected, rel_tol=1e-12, abs_tol=1e-15
        ):
            raise ValueError(f"{name} differs: {actual} != {expected}")
    elif actual != expected:
        raise ValueError(f"{name} differs: {actual} != {expected}")


def verify(config: dict[str, Any], config_path: Path) -> dict[str, Any]:
    test_path = resolve_project_path(config["data"]["test_path"])
    if test_path.exists():
        raise FileExistsError(f"GoEmotions test must remain absent: {test_path}")
    for section in (
        config["data"]["source_train"],
        config["data"]["prepared_train"],
        config["data"]["labels"],
        config["data"]["target_alignment_verification"],
        config["adapter"]["config"],
        config["adapter"]["weights"],
        config["training_verification"],
        config["comparison"]["validation_neutral_cooccurrence_slice"],
        config["model"]["manifest"],
        *config["implementation"].values(),
    ):
        verify_spec(section)
    run_dir = resolve_project_path(config["outputs"]["run_dir"])
    run_record = load_json(run_dir / "run.json")
    if (
        run_record.get("experiment_id") != EXPERIMENT_ID
        or run_record.get("tier") != "Minor"
        or run_record.get("status") != "Completed; pending independent verification"
        or run_record.get("split") != "train-neutral-cooccurrence-only"
        or run_record.get("test_split_accessed") is not False
        or run_record.get("progress") != {"completed": 1396, "total": 1396}
    ):
        raise ValueError("EXP-034 run record is incomplete or out of scope")
    for name, spec in run_record["artifacts"].items():
        path = run_dir / name
        observed = artifact(path)
        if observed != spec:
            raise ValueError(f"Recorded run artifact drift: {name}")
    labels = tuple(
        resolve_project_path(config["data"]["labels"]["path"])
        .read_text(encoding="utf-8")
        .splitlines()
    )
    selected = independently_load_gold(config, labels)
    records = [
        json.loads(line)
        for line in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    gold, predicted = build_matrices(records, selected, labels)
    recalculated = independent_metrics(gold, predicted, labels)
    metrics = load_json(run_dir / "metrics.json")["task"]
    diagnostics = load_json(run_dir / "diagnostics.json")
    comparisons = {
        "macro_f1": metrics["macro"]["f1"],
        "micro_f1": metrics["micro"]["f1"],
        "neutral_coprediction_rate": diagnostics["neutral_coprediction_rate"],
        "neutral_coprediction_rows": diagnostics["neutral_coprediction_rows"],
        "predicted_cardinality_distribution": diagnostics[
            "predicted_cardinality_distribution"
        ],
        "predicted_label_cardinality": diagnostics["predicted_label_cardinality"],
        "samples_f1": metrics["samples"]["f1"],
        "subset_accuracy": metrics["subset_accuracy"],
        "target_compatible_coprediction_rate": diagnostics[
            "target_compatible_coprediction_rate"
        ],
        "target_compatible_coprediction_rows": diagnostics[
            "target_compatible_coprediction_rows"
        ],
    }
    for name, expected in recalculated.items():
        require_close(comparisons[name], expected, name)
    with (run_dir / "predictions.csv").open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if {"text", "input", "messages", "comment_id"} & set(reader.fieldnames or []):
            raise ValueError("Public predictions CSV contains a raw input field")
        if sum(1 for _ in reader) != 1396:
            raise ValueError("Public predictions CSV row count differs")
    comparison = load_json(run_dir / "comparison.json")
    for name in (
        "macro_f1",
        "neutral_coprediction_rate",
        "neutral_coprediction_rows",
        "predicted_label_cardinality",
        "samples_f1",
        "subset_accuracy",
    ):
        require_close(comparison["train"][name], recalculated[name], f"comparison.train.{name}")
    return {
        "artifacts": {
            name: artifact(run_dir / name)
            for name in (
                "comparison.json",
                "diagnostics.json",
                "metrics.json",
                "multilabel-confusion-matrix.csv",
                "per-label-metrics.csv",
                "predictions.csv",
                "predictions.jsonl",
                "run.json",
                "stdout.log",
            )
        },
        "config": artifact(config_path),
        "recalculated": recalculated,
        "rows": len(records),
        "test_split_absent": True,
        "test_split_accessed": False,
    }


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    if config_path != CONFIG_PATH.resolve() or sha256_file(config_path) != args.config_sha256:
        raise ValueError("EXP-034 config path or SHA-256 mismatch")
    config = load_json(config_path)
    if (
        config.get("experiment_id") != EXPERIMENT_ID
        or config.get("tier") != "Minor"
        or config.get("status") != "Registered"
        or "PENDING" in json.dumps(config, sort_keys=True)
    ):
        raise ValueError("EXP-034 config is not frozen")
    recalculated = verify(config, config_path)
    verification = {
        "recalculated": recalculated,
        "status": "Passed",
        "verification_id": VERIFICATION_ID,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    output_path = resolve_project_path(config["outputs"]["run_dir"]) / "verification.json"
    if args.check:
        existing = load_json(output_path)
        if (
            existing.get("status") != "Passed"
            or existing.get("verification_id") != VERIFICATION_ID
            or existing.get("recalculated") != recalculated
        ):
            raise ValueError("Existing EXP-034 verification does not match recomputation")
        print(json.dumps({"status": "Passed", "verification_id": VERIFICATION_ID}))
        return
    if output_path.exists():
        raise FileExistsError(f"Verification already exists: {output_path}")
    write_json(output_path, verification)
    print(json.dumps({"status": "Passed", "verification_id": VERIFICATION_ID}))


if __name__ == "__main__":
    main()
