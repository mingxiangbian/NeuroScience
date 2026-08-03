#!/usr/bin/env python3
"""Pure NumPy metrics and artifact writers for EXP-025/026."""

from __future__ import annotations

from collections import Counter
import csv
import json
from pathlib import Path
import statistics
from typing import Any, Iterable

import numpy as np


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _divide(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    return np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator, dtype=np.float64),
        where=denominator != 0,
    )


def compute_metrics(
    gold: np.ndarray,
    predicted: np.ndarray,
    labels: tuple[str, ...],
) -> tuple[dict[str, Any], np.ndarray]:
    if gold.shape != predicted.shape or gold.shape[1] != len(labels):
        raise ValueError("Gold/predicted shape or label count mismatch")
    if not np.isin(gold, (0, 1)).all() or not np.isin(predicted, (0, 1)).all():
        raise ValueError("Metrics require binary matrices")

    gold_bool = gold.astype(bool)
    predicted_bool = predicted.astype(bool)
    tp = np.sum(gold_bool & predicted_bool, axis=0, dtype=np.int64)
    fp = np.sum(~gold_bool & predicted_bool, axis=0, dtype=np.int64)
    fn = np.sum(gold_bool & ~predicted_bool, axis=0, dtype=np.int64)
    tn = np.sum(~gold_bool & ~predicted_bool, axis=0, dtype=np.int64)
    support = tp + fn
    predicted_support = tp + fp
    precision = _divide(tp, tp + fp)
    recall = _divide(tp, tp + fn)
    f1 = _divide(2 * tp, 2 * tp + fp + fn)

    total_support = int(np.sum(support))
    macro = {
        "precision": float(np.mean(precision)),
        "recall": float(np.mean(recall)),
        "f1": float(np.mean(f1)),
    }
    micro_tp = int(np.sum(tp))
    micro_fp = int(np.sum(fp))
    micro_fn = int(np.sum(fn))
    micro = {
        "precision": float(micro_tp / (micro_tp + micro_fp))
        if micro_tp + micro_fp
        else 0.0,
        "recall": float(micro_tp / (micro_tp + micro_fn))
        if micro_tp + micro_fn
        else 0.0,
        "f1": float(2 * micro_tp / (2 * micro_tp + micro_fp + micro_fn))
        if 2 * micro_tp + micro_fp + micro_fn
        else 0.0,
    }
    weighted = {
        "precision": float(np.sum(precision * support) / total_support),
        "recall": float(np.sum(recall * support) / total_support),
        "f1": float(np.sum(f1 * support) / total_support),
    }

    sample_tp = np.sum(gold_bool & predicted_bool, axis=1, dtype=np.int64)
    sample_gold = np.sum(gold_bool, axis=1, dtype=np.int64)
    sample_predicted = np.sum(predicted_bool, axis=1, dtype=np.int64)
    samples = {
        "precision": float(np.mean(_divide(sample_tp, sample_predicted))),
        "recall": float(np.mean(_divide(sample_tp, sample_gold))),
        "f1": float(np.mean(_divide(2 * sample_tp, sample_gold + sample_predicted))),
    }

    subset_accuracy = float(np.mean(np.all(gold_bool == predicted_bool, axis=1)))
    loss = float(np.mean(gold_bool != predicted_bool))
    per_label = {
        label: {
            "f1": float(f1[index]),
            "label_id": index,
            "precision": float(precision[index]),
            "predicted_support": int(predicted_support[index]),
            "recall": float(recall[index]),
            "support": int(support[index]),
        }
        for index, label in enumerate(labels)
    }
    confusion = np.stack(
        [
            np.stack([tn, fp], axis=1),
            np.stack([fn, tp], axis=1),
        ],
        axis=1,
    )
    neutral_index = labels.index("neutral") if "neutral" in labels else None
    neutral_coprediction_rows = (
        int(np.sum(predicted_bool[:, neutral_index] & (sample_predicted > 1)))
        if neutral_index is not None
        else 0
    )
    metrics = {
        "accuracy": subset_accuracy,
        "accuracy_definition": "strict subset/exact-match accuracy",
        "hamming_loss": loss,
        "label_accuracy": 1.0 - loss,
        "label_cardinality": {
            "gold_mean": float(np.mean(sample_gold)),
            "predicted_mean": float(np.mean(sample_predicted)),
        },
        "macro": macro,
        "micro": micro,
        "per_label": per_label,
        "prediction_diagnostics": {
            "empty_prediction_rows": int(np.sum(sample_predicted == 0)),
            "neutral_coprediction_rows": neutral_coprediction_rows,
        },
        "primary": {"name": "macro_f1", "value": macro["f1"]},
        "samples": samples,
        "subset_accuracy": subset_accuracy,
        "weighted": weighted,
    }
    return metrics, confusion


def records_to_prediction_matrix(
    records: list[dict[str, Any]],
    labels: tuple[str, ...],
) -> np.ndarray:
    matrix = np.zeros((len(records), len(labels)), dtype=np.uint8)
    for index, record in enumerate(records):
        for label_id in record["predicted_label_ids"]:
            matrix[index, int(label_id)] = 1
    return matrix


def write_predictions(
    path: Path,
    records: list[dict[str, Any]],
) -> None:
    fields = [
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
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "row_number": record["row_number"],
                    "gold_label_ids": "|".join(
                        str(value) for value in record["gold_label_ids"]
                    ),
                    "gold_labels": "|".join(record["gold_labels"]),
                    "predicted_label_ids": "|".join(
                        str(value) for value in record["predicted_label_ids"]
                    ),
                    "predicted_labels": "|".join(record["predicted_labels"]),
                    "parser_valid": str(record["parser_valid"]).lower(),
                    "parser_error": record["parser_error"] or "",
                    "finish_reason": record["finish_reason"] or "",
                    "canonical_output": record["canonical_output"] or "",
                    "output_sha256": record["output_sha256"],
                    "output_character_count": record["output_character_count"],
                    "prompt_tokens": record["prompt_tokens"],
                    "generated_tokens": record["generated_tokens"],
                    "generation_seconds": format(
                        float(record["generation_seconds"]), ".17g"
                    ),
                    "prompt_tps": format(float(record["prompt_tps"]), ".17g"),
                    "generation_tps": format(
                        float(record["generation_tps"]), ".17g"
                    ),
                    "peak_memory_gb": format(
                        float(record["peak_memory_gb"]), ".17g"
                    ),
                    "sequence_logprob_sum": format(
                        float(record["sequence_logprob_sum"]), ".17g"
                    ),
                    "sequence_logprob_mean": format(
                        float(record["sequence_logprob_mean"]), ".17g"
                    ),
                    "sequence_score_space": record["sequence_score_space"],
                    "constraint_intervened": ""
                    if record["constraint_intervened"] is None
                    else str(record["constraint_intervened"]).lower(),
                    "raw_argmax_blocked_steps": ""
                    if record["raw_argmax_blocked_steps"] is None
                    else record["raw_argmax_blocked_steps"],
                    "first_blocked_step": ""
                    if record["first_blocked_step"] is None
                    else record["first_blocked_step"],
                    "first_blocked_token_id": ""
                    if record["first_blocked_token_id"] is None
                    else record["first_blocked_token_id"],
                }
            )


def write_per_label(
    path: Path,
    metrics: dict[str, Any],
    labels: tuple[str, ...],
) -> None:
    fields = [
        "label_id",
        "label",
        "precision",
        "recall",
        "f1",
        "support",
        "predicted_support",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for label in labels:
            record = metrics["per_label"][label]
            writer.writerow(
                {
                    "label_id": record["label_id"],
                    "label": label,
                    "precision": format(record["precision"], ".17g"),
                    "recall": format(record["recall"], ".17g"),
                    "f1": format(record["f1"], ".17g"),
                    "support": record["support"],
                    "predicted_support": record["predicted_support"],
                }
            )


def write_confusion(
    path: Path,
    confusion: np.ndarray,
    labels: tuple[str, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["label_id", "label", "tn", "fp", "fn", "tp"])
        for index, label in enumerate(labels):
            tn, fp, fn, tp = confusion[index].ravel()
            writer.writerow([index, label, int(tn), int(fp), int(fn), int(tp)])


def _numeric_summary(values: Iterable[float]) -> dict[str, float]:
    array = np.asarray(list(values), dtype=np.float64)
    if array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError("Cannot summarize empty or non-finite values")
    return {
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "p95": float(np.quantile(array, 0.95)),
        "total": float(np.sum(array)),
    }


def summarize_generation(records: list[dict[str, Any]]) -> dict[str, Any]:
    valid_count = sum(bool(row["parser_valid"]) for row in records)
    parser_errors = Counter(
        row["parser_error"] for row in records if row["parser_error"]
    )
    finish_reasons = Counter(row["finish_reason"] for row in records)
    summary: dict[str, Any] = {
        "finish_reasons": dict(sorted(finish_reasons.items())),
        "generated_tokens": _numeric_summary(
            float(row["generated_tokens"]) for row in records
        ),
        "generation_seconds": _numeric_summary(
            float(row["generation_seconds"]) for row in records
        ),
        "generation_tps": _numeric_summary(
            float(row["generation_tps"]) for row in records
        ),
        "parser_errors": dict(sorted(parser_errors.items())),
        "parser_valid_count": valid_count,
        "parser_valid_rate": valid_count / len(records),
        "peak_memory_gb_max": max(float(row["peak_memory_gb"]) for row in records),
        "prompt_tokens": _numeric_summary(
            float(row["prompt_tokens"]) for row in records
        ),
        "prompt_tps": _numeric_summary(
            float(row["prompt_tps"]) for row in records
        ),
        "sample_count": len(records),
        "sequence_logprob_mean": _numeric_summary(
            float(row["sequence_logprob_mean"]) for row in records
        ),
        "sequence_logprob_sum": _numeric_summary(
            float(row["sequence_logprob_sum"]) for row in records
        ),
    }
    if records[0]["constraint_intervened"] is not None:
        intervened = [bool(row["constraint_intervened"]) for row in records]
        blocked_steps = [int(row["raw_argmax_blocked_steps"]) for row in records]
        first_steps = [
            int(row["first_blocked_step"])
            for row in records
            if row["first_blocked_step"] is not None
        ]
        summary["constraint_intervention"] = {
            "blocked_steps_total": int(sum(blocked_steps)),
            "first_blocked_step_median": float(statistics.median(first_steps))
            if first_steps
            else None,
            "rows": int(sum(intervened)),
            "rate": float(sum(intervened) / len(intervened)),
        }
    return summary


def write_condition_summary(
    path: Path,
    conditions: tuple[str, ...],
    task_metrics: dict[str, dict[str, Any]],
    generation_metrics: dict[str, dict[str, Any]],
) -> None:
    fields = [
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
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for condition in conditions:
            task = task_metrics[condition]
            generation = generation_metrics[condition]
            intervention = generation.get("constraint_intervention", {})
            writer.writerow(
                {
                    "condition": condition,
                    "macro_f1": format(task["macro"]["f1"], ".17g"),
                    "micro_f1": format(task["micro"]["f1"], ".17g"),
                    "weighted_f1": format(task["weighted"]["f1"], ".17g"),
                    "samples_f1": format(task["samples"]["f1"], ".17g"),
                    "subset_accuracy": format(task["subset_accuracy"], ".17g"),
                    "parser_valid_rate": format(
                        generation["parser_valid_rate"], ".17g"
                    ),
                    "empty_prediction_rows": task["prediction_diagnostics"][
                        "empty_prediction_rows"
                    ],
                    "predicted_label_cardinality": format(
                        task["label_cardinality"]["predicted_mean"], ".17g"
                    ),
                    "generation_seconds_total": format(
                        generation["generation_seconds"]["total"], ".17g"
                    ),
                    "generation_seconds_median": format(
                        generation["generation_seconds"]["median"], ".17g"
                    ),
                    "generation_seconds_p95": format(
                        generation["generation_seconds"]["p95"], ".17g"
                    ),
                    "prompt_tokens_total": format(
                        generation["prompt_tokens"]["total"], ".17g"
                    ),
                    "generated_tokens_total": format(
                        generation["generated_tokens"]["total"], ".17g"
                    ),
                    "peak_memory_gb_max": format(
                        generation["peak_memory_gb_max"], ".17g"
                    ),
                    "constraint_intervention_rate": ""
                    if "rate" not in intervention
                    else format(intervention["rate"], ".17g"),
                }
            )


def read_baseline_predictions(
    path: Path,
    labels: tuple[str, ...],
    expected_rows: int,
) -> tuple[np.ndarray, np.ndarray]:
    gold = np.zeros((expected_rows, len(labels)), dtype=np.uint8)
    predicted = np.zeros_like(gold)
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != expected_rows:
        raise ValueError(f"{path} row count differs from {expected_rows}")
    for index, row in enumerate(rows):
        if int(row["row_number"]) != index + 1:
            raise ValueError(f"{path} row order changed")
        for field, matrix in (
            ("gold_label_ids", gold),
            ("predicted_label_ids", predicted),
        ):
            values = row[field].split("|") if row[field] else []
            for value in values:
                label_id = int(value)
                if not 0 <= label_id < len(labels):
                    raise ValueError(f"{path} has an out-of-range label")
                matrix[index, label_id] = 1
    return gold, predicted


def _macro_f1_from_counts(
    gold_support: np.ndarray,
    true_positive: np.ndarray,
    predicted_support: np.ndarray,
) -> np.ndarray:
    denominator = gold_support + predicted_support
    per_label = np.divide(
        2.0 * true_positive,
        denominator,
        out=np.zeros_like(true_positive, dtype=np.float64),
        where=denominator != 0,
    )
    return np.mean(per_label, axis=1)


def paired_bootstrap_macro_f1(
    gold: np.ndarray,
    predictions: dict[str, np.ndarray],
    comparisons: list[tuple[str, str, str]],
    replicates: int,
    seed: int,
    practical_threshold: float,
    batch_size: int = 100,
) -> dict[str, Any]:
    if replicates <= 0 or batch_size <= 0:
        raise ValueError("Bootstrap counts must be positive")
    for name, predicted in predictions.items():
        if predicted.shape != gold.shape:
            raise ValueError(f"Bootstrap shape mismatch for {name}")
    names = tuple(predictions)
    needed = {value for _, left, right in comparisons for value in (left, right)}
    if not needed.issubset(names):
        raise ValueError("Bootstrap comparison references a missing prediction")

    gold_u8 = gold.astype(np.uint8, copy=False)
    predicted_u8 = {
        name: value.astype(np.uint8, copy=False)
        for name, value in predictions.items()
    }
    tp_rows = {
        name: (gold_u8 & value).astype(np.uint8, copy=False)
        for name, value in predicted_u8.items()
    }
    samples = {
        name: np.empty(replicates, dtype=np.float64) for name in names
    }
    rng = np.random.default_rng(seed)
    row_count = gold.shape[0]
    for start in range(0, replicates, batch_size):
        stop = min(replicates, start + batch_size)
        indices = rng.integers(
            0,
            row_count,
            size=(stop - start, row_count),
            dtype=np.int32,
        )
        gold_support = np.sum(gold_u8[indices], axis=1, dtype=np.int32)
        for name in names:
            predicted_support = np.sum(
                predicted_u8[name][indices], axis=1, dtype=np.int32
            )
            true_positive = np.sum(
                tp_rows[name][indices], axis=1, dtype=np.int32
            )
            samples[name][start:stop] = _macro_f1_from_counts(
                gold_support,
                true_positive,
                predicted_support,
            )

    observed_metrics = {
        name: compute_metrics(gold_u8, value, tuple(str(i) for i in range(gold.shape[1])))[0][
            "macro"
        ]["f1"]
        for name, value in predicted_u8.items()
    }
    results = {}
    for comparison_name, left, right in comparisons:
        differences = samples[left] - samples[right]
        lower, upper = np.quantile(differences, [0.025, 0.975])
        observed = observed_metrics[left] - observed_metrics[right]
        results[comparison_name] = {
            "ci_95_percentile": {
                "lower": float(lower),
                "upper": float(upper),
            },
            "left": left,
            "observed_macro_f1_difference": float(observed),
            "practical_effect": abs(observed) >= practical_threshold,
            "practical_threshold": practical_threshold,
            "right": right,
            "two_sided_interval_excludes_zero": bool(lower > 0 or upper < 0),
        }
    return {
        "batch_size": batch_size,
        "confidence_interval": 0.95,
        "comparisons": results,
        "replicates": replicates,
        "resampling_unit": "dev row with replacement",
        "seed": seed,
        "statistic": "paired Macro-F1 difference",
    }
