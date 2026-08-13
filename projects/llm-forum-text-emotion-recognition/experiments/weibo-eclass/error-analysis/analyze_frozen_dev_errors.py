#!/usr/bin/env python3
"""Prepare the frozen EXP-048 Weibo EClass validation error analysis."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import statistics
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-048-frozen-dev-error-analysis.json"
INVALID = "__invalid__"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_path(relative_path: str) -> Path:
    return PROJECT_ROOT / relative_path


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: float) -> str:
    return f"{value:.12f}"


def sample_std(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def artifact_record(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "sha256": sha256_file(path),
    }


def verify_file(spec: dict[str, Any]) -> Path:
    path = project_path(spec["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    observed = sha256_file(path)
    if observed != spec["sha256"]:
        raise ValueError(
            f"Hash mismatch for {path}: expected {spec['sha256']}, observed {observed}"
        )
    return path


def load_validation(
    path: Path, labels: list[str], expected_rows: int, protocol_id: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_sample_ids: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for row_index, line in enumerate(handle):
            raw = json.loads(line)
            if raw.get("protocol_id") != protocol_id:
                raise ValueError(f"Protocol mismatch at validation row {row_index}")
            sample_id = raw.get("sample_id")
            group_id = raw.get("group_id")
            label = raw.get("label")
            if not isinstance(sample_id, str) or sample_id in seen_sample_ids:
                raise ValueError(f"Invalid or duplicate sample_id at row {row_index}")
            if not isinstance(group_id, str) or label not in labels:
                raise ValueError(f"Invalid group or label at row {row_index}")
            views = raw.get("views", {})
            target = views.get("target_only", {}).get("target")
            context_target = views.get("previous_context", {}).get("target")
            previous = views.get("previous_context", {}).get("previous")
            if not isinstance(target, str) or context_target != target:
                raise ValueError(f"Paired target mismatch at row {row_index}")
            if not isinstance(raw.get("context_available"), bool):
                raise ValueError(f"Invalid context flag at row {row_index}")
            if raw["context_available"]:
                if not isinstance(previous, str):
                    raise ValueError(f"Missing available context at row {row_index}")
            elif previous is not None:
                raise ValueError(f"Unexpected first-clause context at row {row_index}")
            if not isinstance(raw.get("ambiguous_target"), bool):
                raise ValueError(f"Invalid ambiguity flag at row {row_index}")
            seen_sample_ids.add(sample_id)
            rows.append(
                {
                    "row_index": row_index,
                    "sample_id": sample_id,
                    "group_id": group_id,
                    "gold": label,
                    "context_available": raw["context_available"],
                    "ambiguous_target": raw["ambiguous_target"],
                    "previous": previous,
                    "target": target,
                }
            )
    if len(rows) != expected_rows:
        raise ValueError(f"Expected {expected_rows} validation rows, observed {len(rows)}")
    return rows


def load_generative_run(
    path: Path, validation: list[dict[str, Any]], labels: list[str], seed: int | None
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for row_index, line in enumerate(handle):
            raw = json.loads(line)
            if row_index >= len(validation):
                raise ValueError(f"Extra prediction row in {path}")
            source = validation[row_index]
            if raw.get("row_index") != row_index:
                raise ValueError(f"row_index mismatch in {path}, row {row_index}")
            if raw.get("sample_id") != source["sample_id"]:
                raise ValueError(f"sample_id mismatch in {path}, row {row_index}")
            if raw.get("group_id") != source["group_id"]:
                raise ValueError(f"group_id mismatch in {path}, row {row_index}")
            if raw.get("gold_label") != source["gold"]:
                raise ValueError(f"gold label mismatch in {path}, row {row_index}")
            if raw.get("view") != "target_only":
                raise ValueError(f"Unexpected view in {path}, row {row_index}")
            parse = raw.get("parse")
            if not isinstance(parse, dict) or not isinstance(parse.get("valid"), bool):
                raise ValueError(f"Invalid parse record in {path}, row {row_index}")
            parse_valid = parse["valid"]
            prediction = raw.get("prediction")
            if parse_valid and prediction not in labels:
                raise ValueError(f"Valid parse has invalid label in {path}, row {row_index}")
            if not isinstance(raw.get("likely_truncated"), bool):
                raise ValueError(f"Invalid truncation flag in {path}, row {row_index}")
            failed_output = (not parse_valid) or raw["likely_truncated"]
            rows.append(
                {
                    "prediction": prediction if parse_valid else INVALID,
                    "parse_valid": parse_valid,
                    "likely_truncated": raw["likely_truncated"],
                    "failed_output": failed_output,
                    "parse_error": parse.get("error") or "",
                    "seed": seed,
                }
            )
    if len(rows) != len(validation):
        raise ValueError(f"Incomplete prediction file: {path}")
    return rows


def load_encoder_run(
    path: Path, validation: list[dict[str, Any]], labels: list[str], seed: int | None
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"sample_id", "group_id", "gold", "prediction"}
        required.update(f"probability__{label}" for label in labels)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing encoder columns in {path}")
        for row_index, raw in enumerate(reader):
            if row_index >= len(validation):
                raise ValueError(f"Extra prediction row in {path}")
            source = validation[row_index]
            if raw["sample_id"] != source["sample_id"]:
                raise ValueError(f"sample_id mismatch in {path}, row {row_index}")
            if raw["group_id"] != source["group_id"]:
                raise ValueError(f"group_id mismatch in {path}, row {row_index}")
            if raw["gold"] != source["gold"] or raw["prediction"] not in labels:
                raise ValueError(f"Label mismatch in {path}, row {row_index}")
            probabilities = [float(raw[f"probability__{label}"]) for label in labels]
            if any(value < 0.0 or value > 1.0 for value in probabilities):
                raise ValueError(f"Invalid probability in {path}, row {row_index}")
            rows.append(
                {
                    "prediction": raw["prediction"],
                    "parse_valid": True,
                    "likely_truncated": False,
                    "failed_output": False,
                    "parse_error": "",
                    "seed": seed,
                }
            )
    if len(rows) != len(validation):
        raise ValueError(f"Incomplete prediction file: {path}")
    return rows


def classification_metrics(
    golds: list[str], predictions: list[str], labels: list[str]
) -> dict[str, Any]:
    if not golds or len(golds) != len(predictions):
        raise ValueError("Metrics require equally sized, non-empty inputs")
    classes = labels + ([INVALID] if INVALID in predictions else [])
    confusion = {gold: Counter() for gold in labels}
    for gold, prediction in zip(golds, predictions):
        if gold not in labels or prediction not in classes:
            raise ValueError("Unexpected class in metrics input")
        confusion[gold][prediction] += 1

    per_class: dict[str, dict[str, Any]] = {}
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[gold][label] for gold in labels if gold != label)
        fn = sum(confusion[label][prediction] for prediction in classes if prediction != label)
        support = sum(confusion[label].values())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "support": support,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    correct = sum(gold == prediction for gold, prediction in zip(golds, predictions))
    total_support = len(golds)
    return {
        "rows": total_support,
        "accuracy": correct / total_support,
        "macro_precision": statistics.fmean(item["precision"] for item in per_class.values()),
        "macro_recall": statistics.fmean(item["recall"] for item in per_class.values()),
        "macro_f1": statistics.fmean(item["f1"] for item in per_class.values()),
        "weighted_f1": sum(
            item["f1"] * item["support"] for item in per_class.values()
        )
        / total_support,
        "per_class": per_class,
        "confusion": confusion,
        "classes": classes,
    }


def build_records(
    validation: list[dict[str, Any]], runs: dict[str, list[list[dict[str, Any]]]]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row_index, source in enumerate(validation):
        conditions: dict[str, Any] = {}
        for condition_id, condition_runs in runs.items():
            predictions = [run[row_index]["prediction"] for run in condition_runs]
            conditions[condition_id] = {
                "predictions": predictions,
                "correct_count": sum(item == source["gold"] for item in predictions),
                "runs": [run[row_index] for run in condition_runs],
            }
        records.append({**source, "conditions": conditions})
    return records


def run_metrics_rows(
    records: list[dict[str, Any]], conditions: list[dict[str, Any]], labels: list[str]
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    output: list[dict[str, Any]] = []
    metrics_by_condition: dict[str, list[dict[str, Any]]] = {}
    golds = [record["gold"] for record in records]
    for condition in conditions:
        condition_id = condition["id"]
        run_metrics: list[dict[str, Any]] = []
        for run_index, run_spec in enumerate(condition["runs"]):
            predictions = [
                record["conditions"][condition_id]["predictions"][run_index]
                for record in records
            ]
            metrics = classification_metrics(golds, predictions, labels)
            run_rows = [record["conditions"][condition_id]["runs"][run_index] for record in records]
            parse_valid_rate = statistics.fmean(row["parse_valid"] for row in run_rows)
            failed_output_rate = statistics.fmean(row["failed_output"] for row in run_rows)
            metrics["parse_valid_rate"] = parse_valid_rate
            metrics["failed_output_rate"] = failed_output_rate
            run_metrics.append(metrics)
            output.append(
                {
                    "condition_id": condition_id,
                    "run_index": run_index,
                    "seed": "" if run_spec.get("seed") is None else run_spec["seed"],
                    "rows": len(records),
                    "accuracy": fmt(metrics["accuracy"]),
                    "macro_precision": fmt(metrics["macro_precision"]),
                    "macro_recall": fmt(metrics["macro_recall"]),
                    "macro_f1": fmt(metrics["macro_f1"]),
                    "weighted_f1": fmt(metrics["weighted_f1"]),
                    "parse_valid_rate": fmt(parse_valid_rate),
                    "failed_output_rate": fmt(failed_output_rate),
                }
            )
        metrics_by_condition[condition_id] = run_metrics
    return output, metrics_by_condition


def condition_summary(run_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    fields = [
        "accuracy",
        "macro_precision",
        "macro_recall",
        "macro_f1",
        "weighted_f1",
        "parse_valid_rate",
        "failed_output_rate",
    ]
    return {
        f"{field}_{suffix}": function([item[field] for item in run_metrics])
        for field in fields
        for suffix, function in (("mean", statistics.fmean), ("sample_std", sample_std))
    }


def build_per_class_metrics(
    conditions: list[dict[str, Any]], labels: list[str], metrics: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for condition in conditions:
        condition_id = condition["id"]
        runs = metrics[condition_id]
        for label in labels:
            values = [run["per_class"][label] for run in runs]
            output.append(
                {
                    "condition_id": condition_id,
                    "label": label,
                    "support": values[0]["support"],
                    "run_count": len(values),
                    "tp_mean": fmt(statistics.fmean(item["tp"] for item in values)),
                    "fp_mean": fmt(statistics.fmean(item["fp"] for item in values)),
                    "fn_mean": fmt(statistics.fmean(item["fn"] for item in values)),
                    "precision_mean": fmt(statistics.fmean(item["precision"] for item in values)),
                    "precision_sample_std": fmt(sample_std([item["precision"] for item in values])),
                    "recall_mean": fmt(statistics.fmean(item["recall"] for item in values)),
                    "recall_sample_std": fmt(sample_std([item["recall"] for item in values])),
                    "f1_mean": fmt(statistics.fmean(item["f1"] for item in values)),
                    "f1_sample_std": fmt(sample_std([item["f1"] for item in values])),
                }
            )
    return output


def build_class_gap(per_class_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = {(row["condition_id"], row["label"]): row for row in per_class_rows}
    output: list[dict[str, Any]] = []
    for label in sorted({row["label"] for row in per_class_rows}):
        lora = indexed[("lora", label)]
        encoder = indexed[("encoder", label)]
        output.append(
            {
                "label": label,
                "support": lora["support"],
                "lora_f1_mean": lora["f1_mean"],
                "encoder_f1_mean": encoder["f1_mean"],
                "lora_minus_encoder_f1": fmt(float(lora["f1_mean"]) - float(encoder["f1_mean"])),
                "lora_minus_encoder_precision": fmt(float(lora["precision_mean"]) - float(encoder["precision_mean"])),
                "lora_minus_encoder_recall": fmt(float(lora["recall_mean"]) - float(encoder["recall_mean"])),
            }
        )
    return sorted(output, key=lambda row: float(row["lora_minus_encoder_f1"]))


def build_confusion_pairs(
    conditions: list[dict[str, Any]], metrics: dict[str, list[dict[str, Any]]], labels: list[str]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for condition in conditions:
        condition_id = condition["id"]
        runs = metrics[condition_id]
        predictions = labels + ([INVALID] if condition_id == "reference" else [])
        for gold in labels:
            for predicted in predictions:
                if predicted == gold:
                    continue
                counts = [run["confusion"][gold][predicted] for run in runs]
                if not any(counts):
                    continue
                support = runs[0]["per_class"][gold]["support"]
                output.append(
                    {
                        "condition_id": condition_id,
                        "gold": gold,
                        "prediction": predicted,
                        "support": support,
                        "run_count": len(runs),
                        "count_mean": fmt(statistics.fmean(counts)),
                        "count_sample_std": fmt(sample_std(counts)),
                        "rate_within_gold_mean": fmt(statistics.fmean(counts) / support),
                    }
                )
    return sorted(output, key=lambda row: (row["condition_id"], -float(row["count_mean"]), row["gold"], row["prediction"]))


def build_condition_stability(
    records: list[dict[str, Any]], conditions: list[dict[str, Any]], labels: list[str]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    strata = [("ALL", records)] + [
        (label, [record for record in records if record["gold"] == label]) for label in labels
    ]
    for condition in conditions:
        condition_id = condition["id"]
        run_count = len(condition["runs"])
        for stratum, subset in strata:
            stable_correct = sum(record["conditions"][condition_id]["correct_count"] == run_count for record in subset)
            stable_wrong = sum(record["conditions"][condition_id]["correct_count"] == 0 for record in subset)
            mixed = len(subset) - stable_correct - stable_wrong
            output.append(
                {
                    "condition_id": condition_id,
                    "stratum": stratum,
                    "row_count": len(subset),
                    "runs_per_row": run_count,
                    "all_runs_correct": stable_correct,
                    "all_runs_wrong": stable_wrong,
                    "mixed_outcome": mixed,
                    "all_runs_correct_rate": fmt(stable_correct / len(subset)),
                    "all_runs_wrong_rate": fmt(stable_wrong / len(subset)),
                    "mixed_outcome_rate": fmt(mixed / len(subset)),
                }
            )
    return output


def slice_definitions(
    records: list[dict[str, Any]], long_tail: set[str]
) -> list[tuple[str, list[dict[str, Any]]]]:
    return [
        ("all", records),
        ("context_available", [record for record in records if record["context_available"]]),
        ("first_clause", [record for record in records if not record["context_available"]]),
        ("ambiguous_target", [record for record in records if record["ambiguous_target"]]),
        ("unambiguous_target", [record for record in records if not record["ambiguous_target"]]),
        ("no_emotion", [record for record in records if record["gold"] == "no_emotion"]),
        ("emotion_label", [record for record in records if record["gold"] != "no_emotion"]),
        ("long_tail_label", [record for record in records if record["gold"] in long_tail]),
        ("reference_output_valid", [record for record in records if not record["conditions"]["reference"]["runs"][0]["failed_output"]]),
        ("reference_output_failed", [record for record in records if record["conditions"]["reference"]["runs"][0]["failed_output"]]),
    ]


def build_slice_metrics(
    records: list[dict[str, Any]], conditions: list[dict[str, Any]], labels: list[str], long_tail: set[str]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for slice_id, subset in slice_definitions(records, long_tail):
        if not subset:
            raise ValueError(f"Registered slice is empty: {slice_id}")
        golds = [record["gold"] for record in subset]
        for condition in conditions:
            condition_id = condition["id"]
            for run_index, run_spec in enumerate(condition["runs"]):
                predictions = [record["conditions"][condition_id]["predictions"][run_index] for record in subset]
                metrics = classification_metrics(golds, predictions, labels)
                output.append(
                    {
                        "condition_id": condition_id,
                        "run_index": run_index,
                        "seed": "" if run_spec.get("seed") is None else run_spec["seed"],
                        "slice": slice_id,
                        "row_count": len(subset),
                        "accuracy": fmt(metrics["accuracy"]),
                        "macro_precision": fmt(metrics["macro_precision"]),
                        "macro_recall": fmt(metrics["macro_recall"]),
                        "macro_f1": fmt(metrics["macro_f1"]),
                        "weighted_f1": fmt(metrics["weighted_f1"]),
                    }
                )
    return output


def transition_name(source_count: int, target_count: int, source_runs: int, target_runs: int) -> str:
    if source_count == 0 and target_count == target_runs:
        return "stable_recovery"
    if source_count == source_runs and target_count == 0:
        return "stable_regression"
    source_rate = source_count / source_runs
    target_rate = target_count / target_runs
    if target_rate > source_rate:
        return "higher_correct_rate"
    if target_rate < source_rate:
        return "lower_correct_rate"
    return "unchanged_correct_rate"


def build_pairwise_transitions(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    comparisons = [
        ("reference_to_lora", "reference", "lora"),
        ("encoder_to_lora", "encoder", "lora"),
    ]
    for comparison_id, source_id, target_id in comparisons:
        source_runs = len(records[0]["conditions"][source_id]["predictions"])
        target_runs = len(records[0]["conditions"][target_id]["predictions"])
        counts = Counter(
            (
                record["conditions"][source_id]["correct_count"],
                record["conditions"][target_id]["correct_count"],
            )
            for record in records
        )
        for source_count in range(source_runs + 1):
            for target_count in range(target_runs + 1):
                count = counts[(source_count, target_count)]
                output.append(
                    {
                        "comparison_id": comparison_id,
                        "source_condition": source_id,
                        "target_condition": target_id,
                        "source_correct_count": source_count,
                        "source_run_count": source_runs,
                        "target_correct_count": target_count,
                        "target_run_count": target_runs,
                        "transition": transition_name(source_count, target_count, source_runs, target_runs),
                        "row_count": count,
                        "rate": fmt(count / len(records)),
                    }
                )
    return output


def build_seed_agreement(
    records: list[dict[str, Any]], conditions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for condition in conditions:
        if len(condition["runs"]) < 2:
            continue
        condition_id = condition["id"]
        for left in range(len(condition["runs"])):
            for right in range(left + 1, len(condition["runs"])):
                exact_prediction = 0
                correctness = 0
                both_correct = 0
                for record in records:
                    predictions = record["conditions"][condition_id]["predictions"]
                    left_correct = predictions[left] == record["gold"]
                    right_correct = predictions[right] == record["gold"]
                    exact_prediction += predictions[left] == predictions[right]
                    correctness += left_correct == right_correct
                    both_correct += left_correct and right_correct
                output.append(
                    {
                        "condition_id": condition_id,
                        "left_seed": condition["runs"][left]["seed"],
                        "right_seed": condition["runs"][right]["seed"],
                        "row_count": len(records),
                        "exact_prediction_agreement": fmt(exact_prediction / len(records)),
                        "correctness_agreement": fmt(correctness / len(records)),
                        "both_correct_rate": fmt(both_correct / len(records)),
                    }
                )
    return output


def build_format_attribution(
    records: list[dict[str, Any]], labels: list[str]
) -> dict[str, Any]:
    total = len(records)
    slices: dict[str, Any] = {}
    contributions: list[float] = []
    for slice_id, failed in (("reference_output_failed", True), ("reference_output_valid", False)):
        subset = [
            record
            for record in records
            if record["conditions"]["reference"]["runs"][0]["failed_output"] == failed
        ]
        golds = [record["gold"] for record in subset]
        ref_predictions = [record["conditions"]["reference"]["predictions"][0] for record in subset]
        ref_metrics = classification_metrics(golds, ref_predictions, labels)
        lora_metrics = [
            classification_metrics(
                golds,
                [record["conditions"]["lora"]["predictions"][run_index] for record in subset],
                labels,
            )
            for run_index in range(3)
        ]
        lora_accuracy = statistics.fmean(item["accuracy"] for item in lora_metrics)
        delta = lora_accuracy - ref_metrics["accuracy"]
        contribution = len(subset) / total * delta
        contributions.append(contribution)
        slices[slice_id] = {
            "rows": len(subset),
            "gold_counts": dict(sorted(Counter(golds).items())),
            "reference_accuracy": ref_metrics["accuracy"],
            "reference_macro_f1": ref_metrics["macro_f1"],
            "lora_accuracy_mean": lora_accuracy,
            "lora_accuracy_sample_std": sample_std([item["accuracy"] for item in lora_metrics]),
            "lora_macro_f1_mean": statistics.fmean(item["macro_f1"] for item in lora_metrics),
            "lora_macro_f1_sample_std": sample_std([item["macro_f1"] for item in lora_metrics]),
            "lora_minus_reference_accuracy": delta,
            "weighted_accuracy_delta_contribution": contribution,
        }
    overall_reference_accuracy = statistics.fmean(
        record["conditions"]["reference"]["correct_count"] for record in records
    )
    overall_lora_accuracy = statistics.fmean(
        record["conditions"]["lora"]["correct_count"] / 3 for record in records
    )
    return {
        "definition": "Reference output failure means parse.valid=false or likely_truncated=true.",
        "overall_reference_accuracy": overall_reference_accuracy,
        "overall_lora_accuracy_mean": overall_lora_accuracy,
        "overall_accuracy_delta": overall_lora_accuracy - overall_reference_accuracy,
        "additive_contribution_check": sum(contributions),
        "failed_output_stable_lora_recoveries": sum(
            record["conditions"]["reference"]["runs"][0]["failed_output"]
            and record["conditions"]["lora"]["correct_count"] == 3
            for record in records
        ),
        "valid_reference_stable_lora_recoveries": sum(
            not record["conditions"]["reference"]["runs"][0]["failed_output"]
            and record["conditions"]["reference"]["correct_count"] == 0
            and record["conditions"]["lora"]["correct_count"] == 3
            for record in records
        ),
        "reference_correct_stable_lora_regressions": sum(
            record["conditions"]["reference"]["correct_count"] == 1
            and record["conditions"]["lora"]["correct_count"] == 0
            for record in records
        ),
        "slices": slices,
        "macro_f1_decomposition_claimed": False,
    }


def deterministic_key(seed: str, role: str, sample_id: str) -> str:
    return hashlib.sha256(f"{seed}:{role}:{sample_id}".encode()).hexdigest()


def case_id(sample_id: str) -> str:
    return "case-" + hashlib.sha256(f"EXP-048:{sample_id}".encode()).hexdigest()[:16]


def stratified_select(
    candidates: list[dict[str, Any]], limit: int, role: str, seed: str
) -> list[dict[str, Any]]:
    ordered = sorted(candidates, key=lambda row: deterministic_key(seed, role, row["sample_id"]))
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    per_label: Counter[str] = Counter()
    for record in ordered:
        if per_label[record["gold"]] >= 2:
            continue
        selected.append(record)
        selected_ids.add(record["sample_id"])
        per_label[record["gold"]] += 1
        if len(selected) == limit:
            return selected
    for record in ordered:
        if record["sample_id"] in selected_ids:
            continue
        selected.append(record)
        if len(selected) == limit:
            break
    return selected


def select_cases(
    records: list[dict[str, Any]], sampling: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    realized: dict[str, int] = {}

    def candidates(role: str) -> list[dict[str, Any]]:
        available = [record for record in records if record["sample_id"] not in used]
        if role == "format_recoveries":
            return [record for record in available if record["conditions"]["reference"]["runs"][0]["failed_output"] and record["conditions"]["lora"]["correct_count"] == 3]
        if role == "valid_reference_recoveries":
            return [record for record in available if not record["conditions"]["reference"]["runs"][0]["failed_output"] and record["conditions"]["reference"]["correct_count"] == 0 and record["conditions"]["lora"]["correct_count"] == 3]
        if role == "lora_over_encoder":
            return [record for record in available if record["conditions"]["encoder"]["correct_count"] == 0 and record["conditions"]["lora"]["correct_count"] == 3]
        if role == "encoder_over_lora":
            return [record for record in available if record["conditions"]["encoder"]["correct_count"] == 3 and record["conditions"]["lora"]["correct_count"] == 0]
        if role == "shared_stable_errors":
            return [record for record in available if record["conditions"]["encoder"]["correct_count"] == 0 and record["conditions"]["lora"]["correct_count"] == 0]
        if role == "seed_unstable_lora":
            return [record for record in available if record["conditions"]["lora"]["correct_count"] in {1, 2}]
        raise ValueError(f"Unknown sampling role: {role}")

    for role_spec in sampling["roles"]:
        role = role_spec["id"]
        chosen = stratified_select(candidates(role), role_spec["limit"], role, sampling["seed"])
        for record in chosen:
            selected.append({"role": role, "record": record})
            used.add(record["sample_id"])
        realized[role] = len(chosen)
    if len(selected) > sampling["maximum_unique_rows"]:
        raise ValueError("Qualitative sample exceeds frozen maximum")
    return selected, {"realized_role_counts": realized, "unique_rows": len(selected)}


def build_sample_manifest(
    selections: list[dict[str, Any]], support: Counter[str], long_tail: set[str]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for rank, selection in enumerate(selections, start=1):
        record = selection["record"]
        reference_run = record["conditions"]["reference"]["runs"][0]
        output.append(
            {
                "sample_rank": rank,
                "case_id": case_id(record["sample_id"]),
                "role": selection["role"],
                "gold_label": record["gold"],
                "gold_support": support[record["gold"]],
                "long_tail": str(record["gold"] in long_tail).lower(),
                "context_available": str(record["context_available"]).lower(),
                "ambiguous_target": str(record["ambiguous_target"]).lower(),
                "reference_output_status": "failed" if reference_run["failed_output"] else "valid",
                "reference_prediction": record["conditions"]["reference"]["predictions"][0],
                "lora_correct_count": record["conditions"]["lora"]["correct_count"],
                "lora_predictions_by_seed": ";".join(record["conditions"]["lora"]["predictions"]),
                "encoder_correct_count": record["conditions"]["encoder"]["correct_count"],
                "encoder_predictions_by_seed": ";".join(record["conditions"]["encoder"]["predictions"]),
            }
        )
    return output


def annotation_template(manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "sample_rank": row["sample_rank"],
            "case_id": row["case_id"],
            "role": row["role"],
            "gold_label": row["gold_label"],
            "evidence_flags": "",
            "primary_possible_source": "",
            "reviewer_confidence": "",
        }
        for row in manifest
    ]


def git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    started = time.perf_counter()

    config_path = args.config.resolve()
    config = read_json(config_path)
    configured_paths = [
        config["data"]["validation"]["path"],
        config["protocol"]["path"],
        config["output_dir"],
        *(spec["path"] for spec in config["upstream_verifications"]),
        *(
            spec["path"]
            for condition in config["conditions"]
            for spec in condition["runs"]
        ),
    ]
    if config.get("test_access") is not False or any(
        "/test" in path.lower() or "test." in Path(path).name.lower()
        for path in configured_paths
    ):
        raise ValueError("EXP-048 config must not contain a test access path")
    output_dir = project_path(config["output_dir"])
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {output_dir}")
    protocol_path = project_path(config["protocol"]["path"])
    if not protocol_path.is_file():
        raise FileNotFoundError(protocol_path)

    verification_artifacts: list[dict[str, Any]] = []
    for spec in config["upstream_verifications"]:
        path = verify_file(spec)
        payload = read_json(path)
        if payload.get("status") != spec["expected_status"]:
            raise ValueError(f"Upstream verification failed: {path}")
        verification_artifacts.append(artifact_record(path))

    validation_path = verify_file(config["data"]["validation"])
    labels = config["data"]["labels"]
    if len(labels) != len(set(labels)) or "no_emotion" not in labels:
        raise ValueError("Invalid label ontology")
    validation = load_validation(
        validation_path,
        labels,
        config["data"]["validation"]["rows"],
        config["data"]["protocol_id"],
    )

    runs: dict[str, list[list[dict[str, Any]]]] = {}
    prediction_artifacts: dict[str, list[dict[str, Any]]] = {}
    for condition in config["conditions"]:
        if len(condition["runs"]) != condition["expected_runs"]:
            raise ValueError(f"Unexpected run count for {condition['id']}")
        loaded_runs: list[list[dict[str, Any]]] = []
        artifacts: list[dict[str, Any]] = []
        for spec in condition["runs"]:
            path = verify_file(spec)
            loader = load_generative_run if condition["format"] == "generative_jsonl" else load_encoder_run
            loaded_runs.append(loader(path, validation, labels, spec.get("seed")))
            artifacts.append(artifact_record(path))
        runs[condition["id"]] = loaded_runs
        prediction_artifacts[condition["id"]] = artifacts

    records = build_records(validation, runs)
    support = Counter(record["gold"] for record in records)
    long_tail = {label for label, count in support.items() if count < config["sampling"]["long_tail_support_below"]}
    metric_rows, metrics = run_metrics_rows(records, config["conditions"], labels)
    per_class_rows = build_per_class_metrics(config["conditions"], labels, metrics)
    class_gap_rows = build_class_gap(per_class_rows)
    confusion_rows = build_confusion_pairs(config["conditions"], metrics, labels)
    stability_rows = build_condition_stability(records, config["conditions"], labels)
    slice_rows = build_slice_metrics(records, config["conditions"], labels, long_tail)
    transition_rows = build_pairwise_transitions(records)
    agreement_rows = build_seed_agreement(records, config["conditions"])
    attribution = build_format_attribution(records, labels)
    selections, sampling_summary = select_cases(records, config["sampling"])
    manifest = build_sample_manifest(selections, support, long_tail)

    output_dir.mkdir(parents=True)
    private_dir = output_dir / "private"
    private_dir.mkdir(mode=0o700)

    csv_outputs: dict[str, tuple[list[str], list[dict[str, Any]]]] = {
        "run_metrics.csv": (
            ["condition_id", "run_index", "seed", "rows", "accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1", "parse_valid_rate", "failed_output_rate"],
            metric_rows,
        ),
        "per_class_metrics.csv": (
            ["condition_id", "label", "support", "run_count", "tp_mean", "fp_mean", "fn_mean", "precision_mean", "precision_sample_std", "recall_mean", "recall_sample_std", "f1_mean", "f1_sample_std"],
            per_class_rows,
        ),
        "class_gap.csv": (
            ["label", "support", "lora_f1_mean", "encoder_f1_mean", "lora_minus_encoder_f1", "lora_minus_encoder_precision", "lora_minus_encoder_recall"],
            class_gap_rows,
        ),
        "confusion_pairs.csv": (
            ["condition_id", "gold", "prediction", "support", "run_count", "count_mean", "count_sample_std", "rate_within_gold_mean"],
            confusion_rows,
        ),
        "condition_stability.csv": (
            ["condition_id", "stratum", "row_count", "runs_per_row", "all_runs_correct", "all_runs_wrong", "mixed_outcome", "all_runs_correct_rate", "all_runs_wrong_rate", "mixed_outcome_rate"],
            stability_rows,
        ),
        "slice_metrics.csv": (
            ["condition_id", "run_index", "seed", "slice", "row_count", "accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1"],
            slice_rows,
        ),
        "pairwise_transitions.csv": (
            ["comparison_id", "source_condition", "target_condition", "source_correct_count", "source_run_count", "target_correct_count", "target_run_count", "transition", "row_count", "rate"],
            transition_rows,
        ),
        "seed_agreement.csv": (
            ["condition_id", "left_seed", "right_seed", "row_count", "exact_prediction_agreement", "correctness_agreement", "both_correct_rate"],
            agreement_rows,
        ),
        "sample_manifest.csv": (list(manifest[0]), manifest),
        "manual_annotations.csv": (
            ["sample_rank", "case_id", "role", "gold_label", "evidence_flags", "primary_possible_source", "reviewer_confidence"],
            annotation_template(manifest),
        ),
    }
    for filename, (fieldnames, rows) in csv_outputs.items():
        write_csv(output_dir / filename, fieldnames, rows)

    private_path = private_dir / "selected_cases.private.jsonl"
    with private_path.open("w", encoding="utf-8") as handle:
        for rank, selection in enumerate(selections, start=1):
            record = selection["record"]
            reference = record["conditions"]["reference"]["runs"][0]
            payload = {
                "sample_rank": rank,
                "case_id": case_id(record["sample_id"]),
                "sample_id": record["sample_id"],
                "group_id": record["group_id"],
                "role": selection["role"],
                "gold_label": record["gold"],
                "context_available": record["context_available"],
                "ambiguous_target": record["ambiguous_target"],
                "previous": record["previous"],
                "target": record["target"],
                "reference_prediction": record["conditions"]["reference"]["predictions"][0],
                "reference_parse_error": reference["parse_error"],
                "reference_likely_truncated": reference["likely_truncated"],
                "lora_predictions_by_seed": record["conditions"]["lora"]["predictions"],
                "encoder_predictions_by_seed": record["conditions"]["encoder"]["predictions"],
            }
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    os.chmod(private_path, 0o600)

    aggregate = {
        "experiment_id": config["experiment_id"],
        "split": "validation",
        "row_count": len(records),
        "label_support": dict(sorted(support.items())),
        "long_tail_labels": sorted(long_tail),
        "conditions": {condition_id: condition_summary(run_values) for condition_id, run_values in metrics.items()},
        "sampling": sampling_summary,
        "stable_transitions": {
            comparison_id: {
                transition: sum(int(row["row_count"]) for row in transition_rows if row["comparison_id"] == comparison_id and row["transition"] == transition)
                for transition in ("stable_recovery", "stable_regression", "higher_correct_rate", "lower_correct_rate", "unchanged_correct_rate")
            }
            for comparison_id in ("reference_to_lora", "encoder_to_lora")
        },
        "test_accessed": False,
    }
    write_json(output_dir / "aggregate_summary.json", aggregate)
    write_json(output_dir / "format_attribution.json", attribution)

    public_artifacts = {
        path.name: artifact_record(path)
        for path in sorted(output_dir.iterdir())
        if path.is_file()
    }
    run = {
        "accessed_splits": ["validation"],
        "api_cost_usd": 0,
        "artifacts": public_artifacts,
        "command": "python3 experiments/weibo-eclass/error-analysis/analyze_frozen_dev_errors.py",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": artifact_record(config_path),
        "data": artifact_record(validation_path),
        "experiment_id": config["experiment_id"],
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_dirty": bool(git_value("status", "--short")),
        "implementation": artifact_record(Path(__file__).resolve()),
        "prediction_artifacts": prediction_artifacts,
        "private_review_artifact": artifact_record(private_path),
        "protocol": artifact_record(protocol_path),
        "resource": {"new_model_runs": 0, "api_calls": 0, "wall_seconds": time.perf_counter() - started},
        "source_verifications": verification_artifacts,
        "stage": config["stage"],
        "status": "AwaitingManualReview",
        "test_accessed": False,
        "tier": config["tier"],
    }
    write_json(output_dir / "run.json", run)
    print(json.dumps({"experiment_id": config["experiment_id"], "sample_rows": len(manifest), "status": run["status"]}, indent=2))


if __name__ == "__main__":
    main()
