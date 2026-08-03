#!/usr/bin/env python3
"""Independently verify EXP-031 inference-only ontology ablation artifacts."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import sys
import time
from typing import Any

import numpy as np

EXPERIMENT_ID = "EXP-031"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
CONFIG_PATH = SCRIPT_DIR / "configs" / "exp-031-neutral-ontology-inference-ablation.json"
PROTOCOL_PATH = SCRIPT_DIR / "protocols" / "exp-031-neutral-ontology-inference-ablation.md"
RUNNER_PATH = SCRIPT_DIR / "run_neutral_ontology_ablation.py"
PARENT_RUNNER_PATH = SCRIPT_DIR / "run_lora.py"
METRICS_PATH = SCRIPT_DIR / "llm_full_dev_metrics.py"
CONSTRAINT_PATH = SCRIPT_DIR / "label_json_constraint_neutral_cooccurrence.py"
DATA_ROOT = PROJECT_ROOT / "data" / "goemotions" / "official"
DEV_PATH = DATA_ROOT / "dev.tsv"
LABELS_PATH = DATA_ROOT / "emotions.txt"
TEST_PATH = DATA_ROOT / "test.tsv"
MODEL_ROOT = PROJECT_ROOT / "models" / "qwen3-1.7b"
MODEL_DIR = MODEL_ROOT / "mlx-bf16"
MODEL_MANIFEST_PATH = MODEL_ROOT / "manifest.json"
CONDITIONS = (
    "old-prompt-closed-decoder",
    "old-prompt-open-decoder",
    "aligned-prompt-open-decoder",
)
OPEN_CONDITIONS = CONDITIONS[1:]
HISTORICAL_BASELINE = "exp-029-zero-shot-closed-ontology"
ALL_CONDITIONS = (*CONDITIONS, HISTORICAL_BASELINE)
SLICE_NAMES = (
    "all",
    "single_label",
    "any_multilabel",
    "neutral_cooccurrence",
    "without_neutral_cooccurrence",
)
ALLOWED_RECORD_KEYS = {
    "canonical_output",
    "condition",
    "constraint_intervened",
    "finish_reason",
    "first_blocked_step",
    "first_blocked_token_id",
    "generated_tokens",
    "generation_seconds",
    "generation_tps",
    "gold_label_ids",
    "gold_labels",
    "output_character_count",
    "output_sha256",
    "parser_error",
    "parser_valid",
    "peak_memory_gb",
    "predicted_label_ids",
    "predicted_labels",
    "prompt_tokens",
    "prompt_tps",
    "raw_argmax_blocked_steps",
    "row_number",
    "sequence_logprob_mean",
    "sequence_logprob_sum",
    "sequence_score_space",
}
PREDICTION_FIELDS = (
    "row_number",
    "gold_label_ids",
    "gold_labels",
    "predicted_label_ids",
    "predicted_labels",
    "parser_valid",
    "parser_error",
    "finish_reason",
    "canonical_output",
    "output_sha256",
    "output_character_count",
    "prompt_tokens",
    "generated_tokens",
    "generation_seconds",
    "prompt_tps",
    "generation_tps",
    "peak_memory_gb",
    "sequence_logprob_sum",
    "sequence_logprob_mean",
    "sequence_score_space",
    "constraint_intervened",
    "raw_argmax_blocked_steps",
    "first_blocked_step",
    "first_blocked_token_id",
)
PER_LABEL_FIELDS = (
    "label_id",
    "label",
    "precision",
    "recall",
    "f1",
    "support",
    "predicted_support",
)
CONFUSION_FIELDS = ("label_id", "label", "tn", "fp", "fn", "tp")
CONDITION_SUMMARY_FIELDS = (
    "condition",
    "macro_f1",
    "micro_f1",
    "weighted_f1",
    "samples_f1",
    "subset_accuracy",
    "parser_valid_rate",
    "empty_prediction_rows",
    "predicted_label_cardinality",
    "generation_seconds_total",
    "generation_seconds_median",
    "generation_seconds_p95",
    "prompt_tokens_total",
    "generated_tokens_total",
    "peak_memory_gb_max",
    "constraint_intervention_rate",
)
SLICE_FIELDS = (
    "condition",
    "slice",
    "row_count",
    "macro_f1",
    "exact_match",
    "samples_f1",
    "predicted_cardinality_mean",
    "neutral_coprediction_rows",
)
ALLOWED_RUN_KEYS = {
    "accessed_splits",
    "active_duration_seconds",
    "adapter",
    "adapter_config",
    "api_cost_usd",
    "artifacts",
    "attempt_failures",
    "command",
    "completed_at_utc",
    "config",
    "data",
    "dev_duration_seconds",
    "dev_generation_pairs",
    "dev_model_load_seconds",
    "dev_peak_mlx_memory_gb",
    "dev_progress",
    "environment",
    "experiment_id",
    "git",
    "hardware",
    "model",
    "output_directory",
    "protocol",
    "raw_comment_ids_stored",
    "raw_input_text_stored",
    "reproduction_commands",
    "rq_id",
    "seed",
    "stage",
    "started_at_utc",
    "status",
    "terminal_failure",
    "test_rows_accessed",
    "test_split_accessed",
    "tier",
    "validation_split_accessed",
    "warnings",
    "working_directory",
}

sys.path.insert(0, str(SCRIPT_DIR))
import llm_full_dev_metrics as metric_tools


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--seed", type=int)
    group.add_argument("--aggregate", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": str(path.resolve().relative_to(PROJECT_ROOT)),
        "sha256": sha256_file(path),
    }


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(
        f".{path.name}.tmp-{os.getpid()}-{time.time_ns()}"
    )
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
    return PROJECT_ROOT / value


def read_csv_exact(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != fields:
            raise ValueError(f"CSV schema differs for {path}")
        return list(reader)


def verify_hash(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"Hash mismatch for {path}: {actual} != {expected}")


def verify_model_inventory(config: dict[str, Any]) -> None:
    manifest = json.loads(MODEL_MANIFEST_PATH.read_text(encoding="utf-8"))
    inventory = manifest.get("mlx_bf16", {})
    files = inventory.get("files", [])
    if len(files) != int(inventory.get("file_count", -1)):
        raise ValueError("Model manifest file count differs")
    total_bytes = 0
    for entry in files:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Model manifest contains an unsafe path")
        path = MODEL_DIR / relative
        if path.stat().st_size != int(entry["bytes"]):
            raise ValueError(f"Model file size differs: {path}")
        verify_hash(path, entry["sha256"])
        total_bytes += path.stat().st_size
    if total_bytes != int(inventory.get("total_bytes", -1)):
        raise ValueError("Model manifest total bytes differ")
    if manifest.get("revision") != config["model"]["revision"]:
        raise ValueError("Model revision differs from the frozen config")


def verify_environment(config: dict[str, Any]) -> None:
    expected = config["environment"]
    actual_major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    if actual_major_minor != expected["python_major_minor"]:
        raise ValueError("Python major/minor version differs")
    for package, expected_version in expected["packages"].items():
        try:
            actual_version = metadata.version(package)
        except metadata.PackageNotFoundError as error:
            raise ValueError(f"Frozen package is missing: {package}") from error
        if actual_version != expected_version:
            raise ValueError(
                f"Package version differs for {package}: {actual_version} != {expected_version}"
            )


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if (
        config.get("experiment_id") != EXPERIMENT_ID
        or config.get("tier") != "Major"
        or config.get("status") != "Registered"
        or config.get("parent_experiment") != "EXP-029"
    ):
        raise ValueError("Unexpected EXP-031 registration identity")
    if "PENDING" in json.dumps(config, sort_keys=True):
        raise ValueError("EXP-031 configuration hashes are not frozen")
    seeds = [int(value) for value in config["resource_budget"]["formal_seeds"]]
    if (
        tuple(config["decoding"]["conditions"]) != CONDITIONS
        or set(config["prompts"]) != set(CONDITIONS)
        or seeds != [42, 43, 44]
        or set(config["adapter_inputs"]) != {str(seed) for seed in seeds}
        or int(config["resource_budget"]["dev_conditions_per_seed"])
        != len(CONDITIONS)
        or tuple(config["evaluation"]["comparisons"])
        != (
            "concurrent-closed-minus-historical-closed",
            "old-open-minus-closed",
            "aligned-open-minus-closed",
            "aligned-open-minus-old-open",
        )
        or config["data"]["test_access"] is not False
        or config["evaluation"]["test_gate"] != "closed"
    ):
        raise ValueError("EXP-031 frozen condition, seed, or test policy differs")
    implementation = config["implementation"]
    checks = [
        (RUNNER_PATH, implementation["runner_sha256"]),
        (PARENT_RUNNER_PATH, implementation["parent_runner_sha256"]),
        (METRICS_PATH, implementation["metrics_sha256"]),
        (CONSTRAINT_PATH, implementation["constraint_sha256"]),
        (Path(__file__).resolve(), implementation["verifier_sha256"]),
        (PROTOCOL_PATH, config["protocol_sha256"]),
        (LABELS_PATH, config["data"]["labels_sha256"]),
        (DEV_PATH, config["data"]["dev_sha256"]),
        (
            resolve_project_path(config["model"]["manifest_path"]),
            config["model"]["manifest_sha256"],
        ),
        (
            resolve_project_path(config["parent_inputs"]["config_path"]),
            config["parent_inputs"]["config_sha256"],
        ),
        (
            resolve_project_path(config["parent_inputs"]["constraint_path"]),
            config["parent_inputs"]["constraint_sha256"],
        ),
    ]
    checks.extend(
        (
            resolve_project_path(prompt["path"]),
            prompt["sha256"],
        )
        for prompt in config["prompts"].values()
    )
    for path, expected in checks:
        verify_hash(path, expected)
    verify_model_inventory(config)
    verify_environment(config)
    if TEST_PATH.exists():
        raise FileExistsError(f"GoEmotions test must remain absent: {TEST_PATH}")
    return config


def load_gold(
    expected_rows: int,
    labels: tuple[str, ...],
) -> tuple[np.ndarray, list[list[int]]]:
    gold = np.zeros((expected_rows, len(labels)), dtype=np.uint8)
    gold_ids: list[list[int]] = []
    seen_ids: set[str] = set()
    with DEV_PATH.open("r", encoding="utf-8", newline="") as handle:
        for row_index, row in enumerate(csv.reader(handle, delimiter="\t")):
            row_number = row_index + 1
            if row_index >= expected_rows or len(row) != 3:
                raise ValueError(f"Invalid dev row {row_number}")
            _, encoded_labels, comment_id = row
            if comment_id in seen_ids:
                raise ValueError("Duplicate dev comment ID")
            seen_ids.add(comment_id)
            values = [int(value) for value in encoded_labels.split(",")]
            if (
                not values
                or len(values) != len(set(values))
                or values != sorted(values)
                or any(value < 0 or value >= len(labels) for value in values)
            ):
                raise ValueError(f"Invalid dev labels at row {row_number}")
            gold[row_index, values] = 1
            gold_ids.append(values)
    if len(gold_ids) != expected_rows:
        raise ValueError("Dev row count changed")
    return gold, gold_ids


def assert_nested_close(actual: Any, expected: Any, path: str = "root") -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise ValueError(f"Object keys differ at {path}")
        for key in expected:
            assert_nested_close(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError(f"List differs at {path}")
        for index, (left, right) in enumerate(zip(actual, expected, strict=True)):
            assert_nested_close(left, right, f"{path}[{index}]")
    elif isinstance(expected, float):
        if not isinstance(actual, (int, float)) or not math.isclose(
            float(actual), expected, rel_tol=1e-12, abs_tol=1e-12
        ):
            raise ValueError(f"Numeric value differs at {path}: {actual} != {expected}")
    elif actual != expected:
        raise ValueError(f"Value differs at {path}: {actual!r} != {expected!r}")


def parse_canonical_output(output: str, labels: tuple[str, ...]) -> list[str]:
    decoded = json.loads(output)
    if not isinstance(decoded, dict) or set(decoded) != {"labels"}:
        raise ValueError("Canonical output has the wrong object schema")
    values = decoded["labels"]
    if (
        not isinstance(values, list)
        or not values
        or not all(isinstance(value, str) for value in values)
        or len(values) != len(set(values))
        or any(value not in labels for value in values)
    ):
        raise ValueError("Canonical output has invalid labels")
    canonical = json.dumps({"labels": values}, separators=(",", ":"))
    if output != canonical:
        raise ValueError("Canonical output is not compact deterministic JSON")
    return values


def expected_pairs(row_count: int) -> list[tuple[int, str]]:
    return [
        (row_number, condition)
        for row_number in range(1, row_count + 1)
        for condition in (
            CONDITIONS[(row_number - 1) % len(CONDITIONS) :]
            + CONDITIONS[: (row_number - 1) % len(CONDITIONS)]
        )
    ]


def read_generation_records(
    path: Path,
    expected_rows: int,
    gold_ids: list[list[int]],
    labels: tuple[str, ...],
) -> list[dict[str, Any]]:
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    pairs = expected_pairs(expected_rows)
    if len(records) != len(pairs):
        raise ValueError("Generation record count is incomplete")
    label_to_id = {label: index for index, label in enumerate(labels)}
    for index, (record, expected) in enumerate(zip(records, pairs, strict=True)):
        if set(record) != ALLOWED_RECORD_KEYS:
            raise ValueError(f"Public record {index + 1} differs from the privacy schema")
        row_number, condition = expected
        if (
            record.get("row_number") != row_number
            or record.get("condition") != condition
            or record.get("gold_label_ids") != gold_ids[row_number - 1]
            or record.get("gold_labels")
            != [labels[value] for value in gold_ids[row_number - 1]]
        ):
            raise ValueError(f"Generation record order or gold differs at {index + 1}")
        if record.get("parser_valid"):
            if record.get("finish_reason") != "stop" or record.get("parser_error") is not None:
                raise ValueError("A valid record has inconsistent parser metadata")
            canonical = record.get("canonical_output")
            if not isinstance(canonical, str):
                raise ValueError("A valid record is missing canonical output")
            predicted_labels = parse_canonical_output(canonical, labels)
            predicted_ids = [label_to_id[label] for label in predicted_labels]
            if (
                record.get("predicted_labels") != predicted_labels
                or record.get("predicted_label_ids") != predicted_ids
                or record.get("output_sha256") != sha256_text(canonical)
                or record.get("output_character_count") != len(canonical)
            ):
                raise ValueError("A valid record's prediction fields disagree")
            if (
                condition == "old-prompt-closed-decoder"
                and "neutral" in predicted_labels
                and len(predicted_labels) > 1
            ):
                raise ValueError("Closed decoder produced neutral co-occurrence")
        elif (
            record.get("predicted_labels")
            or record.get("predicted_label_ids")
            or record.get("canonical_output") is not None
        ):
            raise ValueError("An invalid record was not scored as an empty prediction")
        if record.get("parser_error") not in {
            None,
            "duplicate-label",
            "invalid-json",
            "labels-not-nonempty-list",
            "length-terminated",
            "non-string-label",
            "unknown-label",
            "wrong-object",
        }:
            raise ValueError("Parser error field contains an unexpected value")
        if (
            record.get("sequence_score_space")
            != "condition-specific constrained label-name JSON"
        ):
            raise ValueError("Sequence score-space metadata differs")
        for field in (
            "generated_tokens",
            "generation_seconds",
            "generation_tps",
            "peak_memory_gb",
            "prompt_tokens",
            "prompt_tps",
            "sequence_logprob_mean",
            "sequence_logprob_sum",
        ):
            if not math.isfinite(float(record[field])):
                raise ValueError(f"Non-finite telemetry at record {index + 1}: {field}")
    return records


def verify_condition_files(
    run_dir: Path,
    condition: str,
    records: list[dict[str, Any]],
    labels: tuple[str, ...],
    gold: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any], dict[str, Any]]:
    condition_dir = run_dir / condition
    read_csv_exact(condition_dir / "predictions.csv", PREDICTION_FIELDS)
    csv_gold, csv_prediction = metric_tools.read_baseline_predictions(
        condition_dir / "predictions.csv", labels, gold.shape[0]
    )
    if not np.array_equal(csv_gold, gold):
        raise ValueError(f"{condition} prediction gold differs")
    record_prediction = metric_tools.records_to_prediction_matrix(records, labels)
    if not np.array_equal(record_prediction, csv_prediction):
        raise ValueError(f"{condition} prediction CSV differs from records")
    metrics, confusion = metric_tools.compute_metrics(gold, csv_prediction, labels)
    generation = metric_tools.summarize_generation(records)
    saved = json.loads((condition_dir / "metrics.json").read_text(encoding="utf-8"))
    assert_nested_close(saved, {"condition": condition, "generation": generation, "task": metrics})

    rows = read_csv_exact(condition_dir / "per-label-metrics.csv", PER_LABEL_FIELDS)
    if len(rows) != len(labels):
        raise ValueError(f"{condition} per-label row count differs")
    for label_id, row in enumerate(rows):
        expected = metrics["per_label"][labels[label_id]]
        if int(row["label_id"]) != label_id or row["label"] != labels[label_id]:
            raise ValueError(f"{condition} per-label order differs")
        for field in ("precision", "recall", "f1"):
            if not math.isclose(float(row[field]), expected[field], abs_tol=1e-12):
                raise ValueError(f"{condition} per-label {field} differs")
        for field in ("support", "predicted_support"):
            if int(row[field]) != expected[field]:
                raise ValueError(f"{condition} per-label {field} differs")

    rows = read_csv_exact(
        condition_dir / "multilabel-confusion-matrix.csv", CONFUSION_FIELDS
    )
    if len(rows) != len(labels):
        raise ValueError(f"{condition} confusion row count differs")
    for label_id, row in enumerate(rows):
        actual = np.asarray([int(row[field]) for field in ("tn", "fp", "fn", "tp")])
        if (
            row["label"] != labels[label_id]
            or int(row["label_id"]) != label_id
            or not np.array_equal(actual, confusion[label_id].ravel())
        ):
            raise ValueError(f"{condition} confusion values differ")
    return csv_prediction, metrics, generation


def verify_condition_summary(
    path: Path,
    metrics: dict[str, dict[str, Any]],
    generation: dict[str, dict[str, Any]],
) -> None:
    rows = read_csv_exact(path, CONDITION_SUMMARY_FIELDS)
    if [row["condition"] for row in rows] != list(CONDITIONS):
        raise ValueError("Condition summary order differs")
    for row in rows:
        condition = row["condition"]
        task = metrics[condition]
        runtime = generation[condition]
        expected = {
            "macro_f1": task["macro"]["f1"],
            "micro_f1": task["micro"]["f1"],
            "weighted_f1": task["weighted"]["f1"],
            "samples_f1": task["samples"]["f1"],
            "subset_accuracy": task["subset_accuracy"],
            "parser_valid_rate": runtime["parser_valid_rate"],
            "predicted_label_cardinality": task["label_cardinality"]["predicted_mean"],
            "generation_seconds_total": runtime["generation_seconds"]["total"],
            "generation_seconds_median": runtime["generation_seconds"]["median"],
            "generation_seconds_p95": runtime["generation_seconds"]["p95"],
            "prompt_tokens_total": runtime["prompt_tokens"]["total"],
            "generated_tokens_total": runtime["generated_tokens"]["total"],
            "peak_memory_gb_max": runtime["peak_memory_gb_max"],
        }
        for field, value in expected.items():
            if not math.isclose(float(row[field]), float(value), abs_tol=1e-12):
                raise ValueError(f"Condition summary differs at {condition}.{field}")
        if int(row["empty_prediction_rows"]) != task["prediction_diagnostics"][
            "empty_prediction_rows"
        ]:
            raise ValueError(f"Condition summary empty rows differ for {condition}")
        intervention = runtime.get("constraint_intervention", {})
        if "rate" not in intervention or not math.isclose(
            float(row["constraint_intervention_rate"]),
            float(intervention["rate"]),
            abs_tol=1e-12,
        ):
            raise ValueError(f"Condition intervention rate differs for {condition}")


def transition_counts(
    gold: np.ndarray,
    baseline: np.ndarray,
    treatment: np.ndarray,
    mask: np.ndarray,
) -> dict[str, int]:
    baseline_correct = (baseline[mask] == gold[mask]).all(axis=1)
    treatment_correct = (treatment[mask] == gold[mask]).all(axis=1)
    return {
        "improved": int((~baseline_correct & treatment_correct).sum()),
        "unchanged_correct": int((baseline_correct & treatment_correct).sum()),
        "unchanged_wrong": int((~baseline_correct & ~treatment_correct).sum()),
        "worsened": int((baseline_correct & ~treatment_correct).sum()),
    }


def compute_slice_rows(
    labels: tuple[str, ...],
    gold: np.ndarray,
    predictions: dict[str, np.ndarray],
) -> list[dict[str, Any]]:
    neutral_id = labels.index("neutral")
    cardinality = gold.sum(axis=1)
    neutral_mask = (gold[:, neutral_id] == 1) & (cardinality > 1)
    masks = {
        "all": np.ones(gold.shape[0], dtype=bool),
        "single_label": cardinality == 1,
        "any_multilabel": cardinality > 1,
        "neutral_cooccurrence": neutral_mask,
        "without_neutral_cooccurrence": ~neutral_mask,
    }
    rows: list[dict[str, Any]] = []
    for condition, predicted in predictions.items():
        predicted_cardinality = predicted.sum(axis=1)
        for slice_name, mask in masks.items():
            metrics, _ = metric_tools.compute_metrics(gold[mask], predicted[mask], labels)
            rows.append(
                {
                    "condition": condition,
                    "exact_match": metrics["subset_accuracy"],
                    "macro_f1": metrics["macro"]["f1"],
                    "neutral_coprediction_rows": int(
                        (
                            (predicted[mask][:, neutral_id] == 1)
                            & (predicted_cardinality[mask] > 1)
                        ).sum()
                    ),
                    "predicted_cardinality_mean": float(predicted_cardinality[mask].mean()),
                    "row_count": int(mask.sum()),
                    "samples_f1": metrics["samples"]["f1"],
                    "slice": slice_name,
                }
            )
    return rows


def verify_slice_rows(path: Path, expected: list[dict[str, Any]]) -> None:
    actual = read_csv_exact(path, SLICE_FIELDS)
    if len(actual) != len(expected):
        raise ValueError("Slice metric row count differs")
    for index, (row, target) in enumerate(zip(actual, expected, strict=True)):
        for field in ("condition", "slice"):
            if row[field] != target[field]:
                raise ValueError(f"Slice identity differs at row {index + 1}")
        for field in ("row_count", "neutral_coprediction_rows"):
            if int(row[field]) != target[field]:
                raise ValueError(f"Slice count differs at row {index + 1}.{field}")
        for field in (
            "macro_f1",
            "exact_match",
            "samples_f1",
            "predicted_cardinality_mean",
        ):
            if not math.isclose(float(row[field]), target[field], abs_tol=1e-12):
                raise ValueError(f"Slice metric differs at row {index + 1}.{field}")


def expected_ontology_analysis(
    seed: int,
    labels: tuple[str, ...],
    gold: np.ndarray,
    baseline: np.ndarray,
    historical: np.ndarray,
    predictions: dict[str, np.ndarray],
) -> dict[str, Any]:
    neutral_id = labels.index("neutral")
    neutral_mask = (gold[:, neutral_id] == 1) & (gold.sum(axis=1) > 1)
    all_mask = np.ones(gold.shape[0], dtype=bool)
    return {
        "baseline_condition": "old-prompt-closed-decoder",
        "conditions": {
            condition: {
                "all_rows_transition": transition_counts(
                    gold, baseline, predictions[condition], all_mask
                ),
                "neutral_cooccurrence_transition": transition_counts(
                    gold, baseline, predictions[condition], neutral_mask
                ),
                "predicted_neutral_cooccurrence_rows_all": int(
                    (
                        (predictions[condition][:, neutral_id] == 1)
                        & (predictions[condition].sum(axis=1) > 1)
                    ).sum()
                ),
                "predicted_neutral_cooccurrence_rows_gold_slice": int(
                    (
                        (predictions[condition][neutral_mask][:, neutral_id] == 1)
                        & (predictions[condition][neutral_mask].sum(axis=1) > 1)
                    ).sum()
                ),
            }
            for condition in OPEN_CONDITIONS
        },
        "historical_reproducibility": {
            "different_prediction_rows": int(
                (~(baseline == historical).all(axis=1)).sum()
            ),
            "identical_prediction_rate": float(
                (baseline == historical).all(axis=1).mean()
            ),
            "macro_f1_difference_concurrent_minus_historical": float(
                metric_tools.compute_metrics(gold, baseline, labels)[0]["macro"]["f1"]
                - metric_tools.compute_metrics(gold, historical, labels)[0]["macro"]["f1"]
            ),
        },
        "neutral_cooccurrence_gold_rows": int(neutral_mask.sum()),
        "seed": seed,
    }


def verify_parent_inputs(config: dict[str, Any], seed: int) -> dict[str, Any]:
    seed_spec = config["adapter_inputs"][str(seed)]
    for path_key, hash_key in (
        ("adapter_config_path", "adapter_config_sha256"),
        ("adapter_path", "adapter_sha256"),
        ("historical_predictions_path", "historical_predictions_sha256"),
        ("parent_verification_path", "parent_verification_sha256"),
    ):
        verify_hash(resolve_project_path(seed_spec[path_key]), seed_spec[hash_key])
    parent = json.loads(
        resolve_project_path(seed_spec["parent_verification_path"]).read_text(
            encoding="utf-8"
        )
    )
    if (
        parent.get("experiment_id") != "EXP-029"
        or parent.get("status") != "Passed"
        or parent.get("seed") != seed
        or parent.get("test_absent") is not True
        or parent.get("test_split_accessed") is not False
    ):
        raise ValueError(f"EXP-029 seed {seed} is not independently verified")
    return seed_spec


def verify_smoke(config: dict[str, Any]) -> Path:
    smoke_path = resolve_project_path(config["artifacts"]["smoke_path"])
    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    if (
        smoke.get("experiment_id") != EXPERIMENT_ID
        or smoke.get("status") != "Passed"
        or smoke.get("accessed_splits") != []
        or smoke.get("test_absent") is not True
        or smoke.get("seed") != 42
        or smoke.get("grammar_assertions_passed") != 6
        or len(smoke.get("records", [])) != 6
        or smoke.get("api_cost_usd") != 0
        or float(smoke["duration_seconds"])
        > float(config["resource_budget"]["smoke_wall_time_minutes_max"]) * 60
    ):
        raise ValueError("EXP-031 synthetic smoke report failed verification")
    if {row.get("condition") for row in smoke["records"]} != set(CONDITIONS):
        raise ValueError("EXP-031 smoke did not cover all conditions")
    if any(
        sum(row.get("condition") == condition for row in smoke["records"]) != 2
        for condition in CONDITIONS
    ):
        raise ValueError("EXP-031 smoke condition counts differ")
    if smoke.get("environment", {}).get("packages") != config["environment"][
        "packages"
    ]:
        raise ValueError("EXP-031 smoke environment differs")
    verify_hash(CONFIG_PATH, smoke["config"]["sha256"])
    verify_hash(PROTOCOL_PATH, smoke["protocol"]["sha256"])
    smoke_adapter = resolve_project_path(
        config["adapter_inputs"]["42"]["adapter_path"]
    )
    verify_hash(smoke_adapter, config["adapter_inputs"]["42"]["adapter_sha256"])
    verify_hash(smoke_adapter, smoke["adapter"]["sha256"])
    verify_hash(
        resolve_project_path(config["adapter_inputs"]["42"]["adapter_config_path"]),
        config["adapter_inputs"]["42"]["adapter_config_sha256"],
    )
    verify_hash(
        resolve_project_path(config["model"]["manifest_path"]),
        smoke["model_manifest"]["sha256"],
    )
    labels = tuple(LABELS_PATH.read_text(encoding="utf-8").splitlines())
    for row in smoke["records"]:
        canonical = row.get("canonical_output")
        if not isinstance(canonical, str) or row.get("output_sha256") != sha256_text(
            canonical
        ):
            raise ValueError("EXP-031 smoke output hash differs")
        parse_canonical_output(canonical, labels)
    return smoke_path


def required_seed_artifact_paths() -> list[str]:
    required = [
        "run.json",
        "stdout.log",
        "generation-records.jsonl",
        "analysis/condition-summary.csv",
        "analysis/aggregate-metrics.json",
        "analysis/paired-bootstrap.json",
        "analysis/slice-metrics.csv",
        "analysis/ontology-analysis.json",
    ]
    for condition in CONDITIONS:
        required.extend(
            [
                f"analysis/{condition}/predictions.csv",
                f"analysis/{condition}/metrics.json",
                f"analysis/{condition}/per-label-metrics.csv",
                f"analysis/{condition}/multilabel-confusion-matrix.csv",
            ]
        )
    return required


def verify_seed(config: dict[str, Any], seed: int) -> None:
    seeds = [int(value) for value in config["resource_budget"]["formal_seeds"]]
    if seed not in seeds:
        raise ValueError("Seed is outside the registered schedule")
    smoke_path = verify_smoke(config)
    seed_spec = verify_parent_inputs(config, seed)
    run_dir = resolve_project_path(config["artifacts"]["run_root"]) / f"seed-{seed}"
    verification_path = run_dir / "verification.json"
    if verification_path.exists():
        raise FileExistsError("Append-only EXP-031 verification already exists")
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    if not set(run).issubset(ALLOWED_RUN_KEYS):
        raise ValueError("run.json contains an unregistered public field")
    if (
        run.get("experiment_id") != EXPERIMENT_ID
        or run.get("tier") != "Major"
        or run.get("rq_id") != config["rq_id"]
        or run.get("stage") != config["stage"]
        or run.get("seed") != seed
        or run.get("status") != "Completed"
        or run.get("accessed_splits") != ["dev"]
        or run.get("validation_split_accessed") is not True
        or run.get("test_split_accessed") is not False
        or run.get("test_rows_accessed") != 0
        or run.get("terminal_failure") is not None
    ):
        raise ValueError("Run metadata is not a completed dev-only EXP-031 seed")
    if any(
        failure.get("terminal_resource_violation") is True
        for failure in run.get("attempt_failures", [])
    ):
        raise ValueError("Run history contains a registered resource-gate violation")
    verify_hash(CONFIG_PATH, run["config"]["sha256"])
    verify_hash(PROTOCOL_PATH, run["protocol"]["sha256"])
    verify_hash(resolve_project_path(seed_spec["adapter_path"]), run["adapter"]["sha256"])
    verify_hash(
        resolve_project_path(seed_spec["adapter_config_path"]),
        run["adapter_config"]["sha256"],
    )
    if (
        run.get("api_cost_usd") != 0
        or run.get("raw_comment_ids_stored") is not False
        or run.get("raw_input_text_stored") is not False
        or float(run["active_duration_seconds"])
        > float(config["resource_budget"]["dev_wall_time_hours_max_per_seed"]) * 3600
        or float(run["dev_peak_mlx_memory_gb"])
        > float(config["resource_budget"]["peak_mlx_memory_gb_max"])
        or run.get("dev_generation_pairs")
        != int(config["data"]["dev_rows"]) * len(CONDITIONS)
        or run.get("environment", {}).get("packages")
        != config["environment"]["packages"]
    ):
        raise ValueError("Run resource or privacy metadata failed")

    labels = tuple(LABELS_PATH.read_text(encoding="utf-8").splitlines())
    if len(labels) != int(config["data"]["labels"]):
        raise ValueError("Label count differs")
    gold, gold_ids = load_gold(int(config["data"]["dev_rows"]), labels)
    neutral_id = labels.index("neutral")
    neutral_rows = int(((gold[:, neutral_id] == 1) & (gold.sum(axis=1) > 1)).sum())
    if neutral_rows != int(config["data"]["neutral_cooccurrence_dev_rows"]):
        raise ValueError("Neutral co-occurrence slice changed")
    records = read_generation_records(
        run_dir / "generation-records.jsonl",
        gold.shape[0],
        gold_ids,
        labels,
    )
    predictions: dict[str, np.ndarray] = {}
    metrics: dict[str, dict[str, Any]] = {}
    generation: dict[str, dict[str, Any]] = {}
    analysis_dir = run_dir / "analysis"
    for condition in CONDITIONS:
        condition_records = [row for row in records if row["condition"] == condition]
        predictions[condition], metrics[condition], generation[condition] = (
            verify_condition_files(
                analysis_dir, condition, condition_records, labels, gold
            )
        )
    verify_condition_summary(
        analysis_dir / "condition-summary.csv", metrics, generation
    )

    historical_gold, historical_prediction = metric_tools.read_baseline_predictions(
        resolve_project_path(seed_spec["historical_predictions_path"]),
        labels,
        gold.shape[0],
    )
    if not np.array_equal(historical_gold, gold):
        raise ValueError("EXP-029 baseline gold differs")
    historical_metrics, _ = metric_tools.compute_metrics(
        gold, historical_prediction, labels
    )
    all_predictions = {**predictions, HISTORICAL_BASELINE: historical_prediction}
    concurrent_closed = predictions["old-prompt-closed-decoder"]

    named = {
        "historical-closed": historical_prediction,
        "closed": concurrent_closed,
        "old-open": predictions["old-prompt-open-decoder"],
        "aligned-open": predictions["aligned-prompt-open-decoder"],
    }
    comparisons = [
        (
            "concurrent-closed-minus-historical-closed",
            "closed",
            "historical-closed",
        ),
        ("old-open-minus-closed", "old-open", "closed"),
        ("aligned-open-minus-closed", "aligned-open", "closed"),
        ("aligned-open-minus-old-open", "aligned-open", "old-open"),
    ]
    bootstrap = config["evaluation"]["bootstrap"]
    expected_bootstrap = metric_tools.paired_bootstrap_macro_f1(
        gold,
        named,
        comparisons,
        int(bootstrap["replicates"]),
        int(bootstrap["seed"]) + seed,
        float(config["evaluation"]["practical_tie_absolute_macro_f1"]),
    )
    saved_bootstrap = json.loads(
        (analysis_dir / "paired-bootstrap.json").read_text(encoding="utf-8")
    )
    assert_nested_close(saved_bootstrap, expected_bootstrap, "paired_bootstrap")

    expected_slices = compute_slice_rows(labels, gold, all_predictions)
    verify_slice_rows(analysis_dir / "slice-metrics.csv", expected_slices)
    ontology = expected_ontology_analysis(
        seed,
        labels,
        gold,
        concurrent_closed,
        historical_prediction,
        predictions,
    )
    saved_ontology = json.loads(
        (analysis_dir / "ontology-analysis.json").read_text(encoding="utf-8")
    )
    assert_nested_close(saved_ontology, ontology, "ontology_analysis")

    expected_aggregate = {
        "historical_baseline": {
            "condition": HISTORICAL_BASELINE,
            "task": historical_metrics,
        },
        "conditions": {
            condition: {"generation": generation[condition], "task": metrics[condition]}
            for condition in CONDITIONS
        },
        "experiment_id": EXPERIMENT_ID,
        "paired_comparisons": expected_bootstrap,
        "seed": seed,
    }
    saved_aggregate = json.loads(
        (analysis_dir / "aggregate-metrics.json").read_text(encoding="utf-8")
    )
    assert_nested_close(saved_aggregate, expected_aggregate, "aggregate")

    required = required_seed_artifact_paths()
    actual_files = {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file() and path.name != "verification.json"
    }
    if actual_files != set(required):
        raise ValueError("Completed run contains missing or unregistered public files")
    expected_run_artifacts = {
        relative: artifact(run_dir / relative)
        for relative in required
        if relative != "run.json"
    }
    assert_nested_close(run.get("artifacts"), expected_run_artifacts, "run.artifacts")
    artifacts = {relative: artifact(run_dir / relative) for relative in required}
    report = {
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": EXPERIMENT_ID,
        "metrics_recomputed_from_predictions": True,
        "ontology_analysis_recomputed": True,
        "paired_bootstrap_recomputed": True,
        "parent_exp_029_verified": True,
        "privacy_schema_passed": True,
        "resource_gates_passed": True,
        "seed": seed,
        "slice_metrics_recomputed": True,
        "smoke": artifact(smoke_path),
        "status": "Passed",
        "test_absent": not TEST_PATH.exists(),
        "test_split_accessed": False,
    }
    write_json(verification_path, report)
    print(json.dumps(report, indent=2, sort_keys=True))


def numeric_summary(values: list[float]) -> dict[str, Any]:
    return {
        "mean": statistics.mean(values),
        "sample_std": statistics.stdev(values),
        "values": values,
    }


def read_slice_metrics(path: Path) -> dict[tuple[str, str], dict[str, float]]:
    rows = read_csv_exact(path, SLICE_FIELDS)
    output: dict[tuple[str, str], dict[str, float]] = {}
    for row in rows:
        output[(row["condition"], row["slice"])] = {
            "exact_match": float(row["exact_match"]),
            "macro_f1": float(row["macro_f1"]),
            "neutral_coprediction_rows": float(row["neutral_coprediction_rows"]),
            "predicted_cardinality_mean": float(row["predicted_cardinality_mean"]),
            "row_count": float(row["row_count"]),
            "samples_f1": float(row["samples_f1"]),
        }
    return output


def write_seed_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "seed",
        "historical_closed_macro_f1",
        "closed_macro_f1",
        "old_open_macro_f1",
        "aligned_open_macro_f1",
        "old_open_minus_closed_macro_f1",
        "aligned_open_minus_closed_macro_f1",
        "aligned_open_minus_old_open_macro_f1",
        "concurrent_closed_minus_historical_macro_f1",
        "closed_subset_accuracy",
        "old_open_subset_accuracy",
        "aligned_open_subset_accuracy",
        "closed_samples_f1",
        "old_open_samples_f1",
        "aligned_open_samples_f1",
        "old_open_neutral_coprediction_rows",
        "aligned_open_neutral_coprediction_rows",
        "active_seconds",
        "peak_memory_gb",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: format(value, ".17g") if isinstance(value, float) else value
                    for key, value in row.items()
                }
            )


def write_report(path: Path, aggregate: dict[str, Any]) -> None:
    conditions = aggregate["conditions"]
    rows = []
    for condition in ALL_CONDITIONS:
        metrics = conditions[condition]
        rows.append(
            "| "
            + " | ".join(
                [
                    condition,
                    f"{metrics['macro_f1']['mean']:.4f} +/- {metrics['macro_f1']['sample_std']:.4f}",
                    f"{metrics['samples_f1']['mean']:.4f} +/- {metrics['samples_f1']['sample_std']:.4f}",
                    f"{metrics['subset_accuracy']['mean']:.4f} +/- {metrics['subset_accuracy']['sample_std']:.4f}",
                    f"{metrics['predicted_cardinality']['mean']:.3f}",
                ]
            )
            + " |"
        )
    decision = aggregate["decision"]
    content = "\n".join(
        [
            "# EXP-031 Verified Report",
            "",
            "Validation-only, three-seed inference ablation. No test split was acquired or read.",
            "",
            "| Condition | Macro-F1 | Samples-F1 | Exact match | Predicted cardinality |",
            "| --- | ---: | ---: | ---: | ---: |",
            *rows,
            "",
            "## Paired Mean Effects",
            "",
            f"- Concurrent closed minus historical closed Macro-F1: {aggregate['differences']['concurrent-closed-minus-historical-closed']['mean']:+.4f}.",
            f"- Old prompt/open decoder minus closed Macro-F1: {aggregate['differences']['old-open-minus-closed']['mean']:+.4f}.",
            f"- Aligned prompt/open decoder minus closed Macro-F1: {aggregate['differences']['aligned-open-minus-closed']['mean']:+.4f}.",
            f"- Aligned prompt/open decoder minus old prompt/open decoder Macro-F1: {aggregate['differences']['aligned-open-minus-old-open']['mean']:+.4f}.",
            f"- Aligned-open minus closed Samples-F1 on the 174-row neutral co-occurrence slice: {decision['neutral_slice_aligned_minus_closed_samples_f1']:+.4f}.",
            "",
            "## Decision",
            "",
            f"Classification: `{decision['classification']}`.",
            "",
            decision["interpretation"],
            "",
            "This experiment isolates inference policy only. The adapters were trained with co-occurring neutral removed, so the result does not estimate target-aligned retraining and does not support an internal-mechanism claim.",
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")


def publish_staged(staged: Path, destination: Path) -> None:
    if destination.exists():
        if not destination.is_file() or artifact(staged)["sha256"] != artifact(
            destination
        )["sha256"]:
            raise FileExistsError(
                f"Existing aggregate artifact differs from recomputation: {destination}"
            )
        staged.unlink()
        return
    os.replace(staged, destination)


def verify_aggregate(config: dict[str, Any]) -> None:
    run_root = resolve_project_path(config["artifacts"]["run_root"])
    aggregate_path = run_root / "multi-seed-aggregate.json"
    summary_path = run_root / "seed-summary.csv"
    report_path = run_root / "REPORT.md"
    verification_path = run_root / "multi-seed-verification.json"
    if verification_path.exists():
        raise FileExistsError(
            f"Append-only aggregate verification already exists: {verification_path}"
        )
    for path in (aggregate_path, summary_path, report_path):
        if path.exists() and not path.is_file():
            raise FileExistsError(f"Aggregate artifact path is not a file: {path}")

    seeds = [int(value) for value in config["resource_budget"]["formal_seeds"]]
    condition_values = {
        condition: {
            metric: []
            for metric in (
                "macro_f1",
                "macro_precision",
                "macro_recall",
                "micro_f1",
                "weighted_f1",
                "samples_f1",
                "subset_accuracy",
                "predicted_cardinality",
                "neutral_coprediction_rows",
            )
        }
        for condition in ALL_CONDITIONS
    }
    differences = {
        name: []
        for name in (
            "concurrent-closed-minus-historical-closed",
            "old-open-minus-closed",
            "aligned-open-minus-closed",
            "aligned-open-minus-old-open",
        )
    }
    slice_values: dict[tuple[str, str, str], list[float]] = {}
    summary_rows: list[dict[str, Any]] = []
    seed_verifications: dict[str, Any] = {}
    for seed in seeds:
        seed_dir = run_root / f"seed-{seed}"
        verification_file = seed_dir / "verification.json"
        if not verification_file.is_file():
            raise FileNotFoundError(f"Seed {seed} has not been independently verified")
        verification = json.loads(verification_file.read_text(encoding="utf-8"))
        if verification.get("status") != "Passed" or verification.get("seed") != seed:
            raise ValueError(f"Seed {seed} verification failed")
        if set(verification.get("artifacts", {})) != set(
            required_seed_artifact_paths()
        ):
            raise ValueError(f"Seed {seed} verification artifact set differs")
        for relative, saved_artifact in verification["artifacts"].items():
            relative_path = Path(relative)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise ValueError("Seed verification contains an unsafe artifact path")
            path = seed_dir / relative
            try:
                assert_nested_close(
                    saved_artifact,
                    artifact(path),
                    f"seed-{seed}.{relative}",
                )
            except ValueError as error:
                raise ValueError(
                    f"Seed {seed} artifact changed after verification: {relative}"
                ) from error
        analysis_dir = seed_dir / "analysis"
        saved = json.loads(
            (analysis_dir / "aggregate-metrics.json").read_text(encoding="utf-8")
        )
        run = json.loads((seed_dir / "run.json").read_text(encoding="utf-8"))
        metrics_by_condition = {
            HISTORICAL_BASELINE: saved["historical_baseline"]["task"],
            **{
                condition: saved["conditions"][condition]["task"]
                for condition in CONDITIONS
            },
        }
        for condition, metrics in metrics_by_condition.items():
            values = condition_values[condition]
            values["macro_f1"].append(float(metrics["macro"]["f1"]))
            values["macro_precision"].append(float(metrics["macro"]["precision"]))
            values["macro_recall"].append(float(metrics["macro"]["recall"]))
            values["micro_f1"].append(float(metrics["micro"]["f1"]))
            values["weighted_f1"].append(float(metrics["weighted"]["f1"]))
            values["samples_f1"].append(float(metrics["samples"]["f1"]))
            values["subset_accuracy"].append(float(metrics["subset_accuracy"]))
            values["predicted_cardinality"].append(
                float(metrics["label_cardinality"]["predicted_mean"])
            )
            values["neutral_coprediction_rows"].append(
                float(metrics["prediction_diagnostics"]["neutral_coprediction_rows"])
            )
        historical_closed = metrics_by_condition[HISTORICAL_BASELINE]["macro"]["f1"]
        closed = metrics_by_condition["old-prompt-closed-decoder"]["macro"]["f1"]
        old_open = metrics_by_condition["old-prompt-open-decoder"]["macro"]["f1"]
        aligned_open = metrics_by_condition["aligned-prompt-open-decoder"]["macro"]["f1"]
        differences["concurrent-closed-minus-historical-closed"].append(
            closed - historical_closed
        )
        differences["old-open-minus-closed"].append(old_open - closed)
        differences["aligned-open-minus-closed"].append(aligned_open - closed)
        differences["aligned-open-minus-old-open"].append(aligned_open - old_open)

        slices = read_slice_metrics(analysis_dir / "slice-metrics.csv")
        for (condition, slice_name), row in slices.items():
            for metric in (
                "macro_f1",
                "samples_f1",
                "exact_match",
                "predicted_cardinality_mean",
                "neutral_coprediction_rows",
            ):
                slice_values.setdefault((condition, slice_name, metric), []).append(
                    float(row[metric])
                )
        summary_rows.append(
            {
                "active_seconds": float(run["active_duration_seconds"]),
                "aligned_open_macro_f1": aligned_open,
                "aligned_open_minus_closed_macro_f1": aligned_open - closed,
                "aligned_open_minus_old_open_macro_f1": aligned_open - old_open,
                "aligned_open_neutral_coprediction_rows": metrics_by_condition[
                    "aligned-prompt-open-decoder"
                ]["prediction_diagnostics"]["neutral_coprediction_rows"],
                "aligned_open_samples_f1": metrics_by_condition[
                    "aligned-prompt-open-decoder"
                ]["samples"]["f1"],
                "aligned_open_subset_accuracy": metrics_by_condition[
                    "aligned-prompt-open-decoder"
                ]["subset_accuracy"],
                "closed_macro_f1": closed,
                "closed_samples_f1": metrics_by_condition[
                    "old-prompt-closed-decoder"
                ]["samples"]["f1"],
                "closed_subset_accuracy": metrics_by_condition[
                    "old-prompt-closed-decoder"
                ]["subset_accuracy"],
                "concurrent_closed_minus_historical_macro_f1": closed
                - historical_closed,
                "historical_closed_macro_f1": historical_closed,
                "old_open_macro_f1": old_open,
                "old_open_minus_closed_macro_f1": old_open - closed,
                "old_open_neutral_coprediction_rows": metrics_by_condition[
                    "old-prompt-open-decoder"
                ]["prediction_diagnostics"]["neutral_coprediction_rows"],
                "old_open_samples_f1": metrics_by_condition[
                    "old-prompt-open-decoder"
                ]["samples"]["f1"],
                "old_open_subset_accuracy": metrics_by_condition[
                    "old-prompt-open-decoder"
                ]["subset_accuracy"],
                "peak_memory_gb": float(run["dev_peak_mlx_memory_gb"]),
                "seed": seed,
            }
        )
        seed_verifications[f"seed-{seed}"] = artifact(verification_file)

    condition_summaries = {
        condition: {
            metric: numeric_summary(values)
            for metric, values in metrics.items()
        }
        for condition, metrics in condition_values.items()
    }
    difference_summaries = {
        name: numeric_summary(values) for name, values in differences.items()
    }
    slice_summaries = {
        condition: {
            slice_name: {
                metric: numeric_summary(slice_values[(condition, slice_name, metric)])
                for metric in (
                    "macro_f1",
                    "samples_f1",
                    "exact_match",
                    "predicted_cardinality_mean",
                    "neutral_coprediction_rows",
                )
            }
            for slice_name in SLICE_NAMES
        }
        for condition in ALL_CONDITIONS
    }

    threshold = float(config["evaluation"]["practical_tie_absolute_macro_f1"])
    tolerance = float(
        config["evaluation"]["secondary_noninferiority_tolerance_absolute"]
    )
    full_macro_delta = difference_summaries["aligned-open-minus-closed"]["mean"]
    aligned = condition_summaries["aligned-prompt-open-decoder"]
    closed = condition_summaries["old-prompt-closed-decoder"]
    samples_delta = aligned["samples_f1"]["mean"] - closed["samples_f1"]["mean"]
    exact_delta = aligned["subset_accuracy"]["mean"] - closed["subset_accuracy"]["mean"]
    neutral_slice_samples_delta = (
        slice_summaries["aligned-prompt-open-decoder"]["neutral_cooccurrence"][
            "samples_f1"
        ]["mean"]
        - slice_summaries["old-prompt-closed-decoder"]["neutral_cooccurrence"][
            "samples_f1"
        ]["mean"]
    )
    general_improvement = (
        full_macro_delta >= threshold
        and samples_delta >= -tolerance
        and exact_delta >= -tolerance
    )
    localized_improvement = (
        not general_improvement
        and neutral_slice_samples_delta >= float(
            config["evaluation"]["neutral_slice_practical_improvement_samples_f1"]
        )
        and full_macro_delta >= -tolerance
    )
    localized_gain_with_global_regression = (
        not general_improvement
        and not localized_improvement
        and neutral_slice_samples_delta
        >= float(config["evaluation"]["neutral_slice_practical_improvement_samples_f1"])
        and full_macro_delta < -tolerance
    )
    if general_improvement:
        classification = "general_inference_improvement"
        interpretation = (
            "The aligned open ontology materially improves full-dev Macro-F1 while the registered "
            "Samples-F1 and exact-match non-inferiority checks pass."
        )
    elif localized_improvement:
        classification = "localized_neutral_slice_improvement"
        interpretation = (
            "The full-dev effect is not a registered general improvement, but the neutral "
            "co-occurrence slice shows a practically meaningful Samples-F1 gain."
        )
    elif localized_gain_with_global_regression:
        classification = "localized_gain_with_global_regression"
        interpretation = (
            "The neutral co-occurrence slice improves, but full-dev Macro-F1 regresses beyond "
            "the registered tolerance; this is a tradeoff, not a model improvement."
        )
    else:
        classification = "no_material_inference_improvement"
        interpretation = (
            "Inference-time ontology correction does not meet the registered general or localized "
            "improvement rule for these target-misaligned adapters."
        )
    decision = {
        "aligned_minus_closed_exact_match": exact_delta,
        "aligned_minus_closed_macro_f1": full_macro_delta,
        "aligned_minus_closed_samples_f1": samples_delta,
        "classification": classification,
        "general_improvement": general_improvement,
        "interpretation": interpretation,
        "localized_improvement": localized_improvement,
        "localized_gain_with_global_regression": localized_gain_with_global_regression,
        "macro_f1_practical_threshold": threshold,
        "neutral_slice_aligned_minus_closed_samples_f1": neutral_slice_samples_delta,
        "secondary_noninferiority_tolerance": tolerance,
        "test_selection_performed": False,
    }
    aggregate = {
        "conditions": condition_summaries,
        "decision": decision,
        "differences": difference_summaries,
        "experiment_id": EXPERIMENT_ID,
        "seed_count": len(seeds),
        "seeds": seeds,
        "slices": slice_summaries,
        "status": "Verified",
        "test_split_accessed": False,
    }
    run_root.mkdir(parents=True, exist_ok=True)
    private_root = (
        resolve_project_path(config["artifacts"]["private_finalization_root"])
        / "aggregate"
    )
    private_root.mkdir(parents=True, exist_ok=True)
    attempt_dir = private_root / f"attempt-{time.time_ns()}"
    attempt_dir.mkdir()
    try:
        staged_aggregate = attempt_dir / aggregate_path.name
        staged_summary = attempt_dir / summary_path.name
        staged_report = attempt_dir / report_path.name
        write_json(staged_aggregate, aggregate)
        write_seed_summary(staged_summary, summary_rows)
        write_report(staged_report, aggregate)
        publish_staged(staged_aggregate, aggregate_path)
        publish_staged(staged_summary, summary_path)
        publish_staged(staged_report, report_path)
        write_json(
            verification_path,
            {
                "aggregate": artifact(aggregate_path),
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "experiment_id": EXPERIMENT_ID,
                "report": artifact(report_path),
                "seed_summary": artifact(summary_path),
                "seed_verifications": seed_verifications,
                "status": "Passed",
                "test_absent": not TEST_PATH.exists(),
                "test_split_accessed": False,
            },
        )
    finally:
        if attempt_dir.exists():
            shutil.rmtree(attempt_dir)
    print(json.dumps(aggregate, indent=2, sort_keys=True))


def main() -> None:
    args = parse_args()
    config = load_config()
    if args.aggregate:
        verify_aggregate(config)
    else:
        verify_seed(config, args.seed)


if __name__ == "__main__":
    main()
