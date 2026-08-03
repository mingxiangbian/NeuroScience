#!/usr/bin/env python3
"""Analyze frozen GoEmotions dev predictions and select qualitative cases."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import subprocess
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-030-frozen-dev-error-analysis.json"


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


def artifact_record(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "sha256": sha256_file(path),
    }


def fmt(value: float) -> str:
    return f"{value:.12f}"


def sample_std(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def load_labels(path: Path, expected_count: int) -> list[str]:
    labels = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    if len(labels) != expected_count or len(set(labels)) != expected_count:
        raise ValueError("Unexpected GoEmotions label file")
    return labels


def parse_id_set(value: str, separator: str) -> frozenset[int]:
    if not value.strip():
        return frozenset()
    return frozenset(int(item) for item in value.split(separator))


def label_string(ids: frozenset[int], labels: list[str]) -> str:
    return "|".join(labels[index] for index in sorted(ids))


def id_string(ids: frozenset[int]) -> str:
    return "|".join(str(index) for index in sorted(ids))


def load_dev(path: Path, labels: list[str], expected_rows: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row_number, raw in enumerate(reader, start=1):
            if len(raw) != 3:
                raise ValueError(f"Unexpected dev TSV width at row {row_number}")
            text, label_ids_raw, comment_id = raw
            gold_ids = parse_id_set(label_ids_raw, ",")
            if not gold_ids or max(gold_ids) >= len(labels):
                raise ValueError(f"Invalid gold labels at dev row {row_number}")
            rows.append(
                {
                    "row_number": row_number,
                    "text": text,
                    "comment_id": comment_id,
                    "gold_ids": gold_ids,
                }
            )
    if len(rows) != expected_rows:
        raise ValueError(f"Expected {expected_rows} dev rows, observed {len(rows)}")
    return rows


def load_prediction_run(
    spec: dict[str, Any], labels: list[str], expected_rows: int
) -> dict[int, dict[str, Any]]:
    path = verify_file(spec)
    rows: dict[int, dict[str, Any]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "row_number",
            "gold_label_ids",
            "gold_labels",
            "predicted_label_ids",
            "predicted_labels",
        }
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing prediction columns in {path}")
        for raw in reader:
            row_number = int(raw["row_number"])
            if row_number in rows:
                raise ValueError(f"Duplicate row_number {row_number} in {path}")
            gold_ids = parse_id_set(raw["gold_label_ids"], "|")
            predicted_ids = parse_id_set(raw["predicted_label_ids"], "|")
            if gold_ids and label_string(gold_ids, labels) != "|".join(
                sorted(raw["gold_labels"].split("|"), key=labels.index)
            ):
                raise ValueError(f"Gold label mapping mismatch in {path}, row {row_number}")
            if predicted_ids and set(raw["predicted_labels"].split("|")) != {
                labels[index] for index in predicted_ids
            }:
                raise ValueError(
                    f"Prediction label mapping mismatch in {path}, row {row_number}"
                )
            if any(index < 0 or index >= len(labels) for index in predicted_ids):
                raise ValueError(f"Invalid prediction label in {path}, row {row_number}")
            rows[row_number] = {
                "gold_ids": gold_ids,
                "predicted_ids": predicted_ids,
                "seed": spec.get("seed"),
            }
    if set(rows) != set(range(1, expected_rows + 1)):
        raise ValueError(f"Prediction row numbers are incomplete in {path}")
    return rows


def validate_sources(config: dict[str, Any]) -> dict[str, Any]:
    test_path = project_path(config["data"]["test_path"])
    if test_path.exists():
        raise ValueError(f"GoEmotions test gate is closed, but {test_path} exists")

    verified: dict[str, Any] = {}
    for condition in config["conditions"]:
        if len(condition["runs"]) != condition["expected_runs"]:
            raise ValueError(f"Unexpected run count for {condition['id']}")
        verification_path = verify_file(condition["verification"])
        verification = read_json(verification_path)
        status = verification.get(condition["verification"]["status_field"])
        if status != condition["verification"]["expected_status"]:
            raise ValueError(f"Upstream verification did not pass for {condition['id']}")
        verified[condition["id"]] = {
            "status": status,
            "verification": artifact_record(verification_path),
        }
    return verified


def error_mode(gold: frozenset[int], prediction: frozenset[int]) -> str:
    if prediction == gold:
        return "exact"
    if not prediction:
        return "empty_prediction"
    if prediction < gold:
        return "underprediction_only"
    if gold < prediction:
        return "overprediction_only"
    return "mixed_fp_fn"


def build_records(
    dev_rows: list[dict[str, Any]],
    predictions: dict[str, list[dict[int, dict[str, Any]]]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for dev_row in dev_rows:
        row_number = dev_row["row_number"]
        gold_ids = dev_row["gold_ids"]
        record: dict[str, Any] = {
            "row_number": row_number,
            "gold_ids": gold_ids,
            "text": dev_row["text"],
            "conditions": {},
        }
        for condition_id, runs in predictions.items():
            run_rows = [run[row_number] for run in runs]
            if any(row["gold_ids"] != gold_ids for row in run_rows):
                raise ValueError(
                    f"Prediction gold disagrees with official dev at row {row_number}"
                )
            predicted_sets = [row["predicted_ids"] for row in run_rows]
            record["conditions"][condition_id] = {
                "correct_count": sum(prediction == gold_ids for prediction in predicted_sets),
                "error_modes": [error_mode(gold_ids, prediction) for prediction in predicted_sets],
                "predicted_sets": predicted_sets,
                "run_count": len(run_rows),
                "seeds": [row["seed"] for row in run_rows],
            }
        records.append(record)
    return records


def build_condition_stability(
    records: list[dict[str, Any]], condition_ids: list[str], labels: list[str]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    strata: list[tuple[str, list[dict[str, Any]]]] = [("ALL", records)]
    for label_id, label in enumerate(labels):
        strata.append((label, [record for record in records if label_id in record["gold_ids"]]))
    for condition_id in condition_ids:
        for stratum, subset in strata:
            run_count = records[0]["conditions"][condition_id]["run_count"]
            all_correct = sum(
                record["conditions"][condition_id]["correct_count"] == run_count
                for record in subset
            )
            all_wrong = sum(
                record["conditions"][condition_id]["correct_count"] == 0
                for record in subset
            )
            mixed = len(subset) - all_correct - all_wrong
            rows.append(
                {
                    "condition_id": condition_id,
                    "stratum": stratum,
                    "row_count": len(subset),
                    "runs_per_row": run_count,
                    "all_runs_correct": all_correct,
                    "all_runs_wrong": all_wrong,
                    "mixed_outcome": mixed,
                    "all_runs_correct_rate": fmt(all_correct / len(subset)),
                    "all_runs_wrong_rate": fmt(all_wrong / len(subset)),
                    "mixed_outcome_rate": fmt(mixed / len(subset)),
                }
            )
    return rows


def build_error_modes(
    records: list[dict[str, Any]], conditions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    ordered_modes = [
        "exact",
        "underprediction_only",
        "overprediction_only",
        "mixed_fp_fn",
        "empty_prediction",
    ]
    for condition in conditions:
        condition_id = condition["id"]
        for run_index, run_spec in enumerate(condition["runs"]):
            counts = Counter(
                record["conditions"][condition_id]["error_modes"][run_index]
                for record in records
            )
            for mode in ordered_modes:
                output.append(
                    {
                        "condition_id": condition_id,
                        "run_index": run_index,
                        "seed": "" if run_spec.get("seed") is None else run_spec["seed"],
                        "error_mode": mode,
                        "row_count": counts[mode],
                        "rate": fmt(counts[mode] / len(records)),
                    }
                )
    return output


def slice_definitions(
    records: list[dict[str, Any]], neutral_id: int, long_tail_ids: set[int]
) -> list[tuple[str, list[dict[str, Any]]]]:
    return [
        ("all", records),
        ("single_label", [record for record in records if len(record["gold_ids"]) == 1]),
        ("any_multilabel", [record for record in records if len(record["gold_ids"]) > 1]),
        ("neutral_only", [record for record in records if record["gold_ids"] == {neutral_id}]),
        (
            "neutral_cooccurrence",
            [
                record
                for record in records
                if neutral_id in record["gold_ids"] and len(record["gold_ids"]) > 1
            ],
        ),
        (
            "emotion_only_multilabel",
            [
                record
                for record in records
                if neutral_id not in record["gold_ids"] and len(record["gold_ids"]) > 1
            ],
        ),
        (
            "long_tail_label",
            [record for record in records if record["gold_ids"] & long_tail_ids],
        ),
    ]


def build_slice_metrics(
    records: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    neutral_id: int,
    long_tail_ids: set[int],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for slice_id, subset in slice_definitions(records, neutral_id, long_tail_ids):
        if not subset:
            raise ValueError(f"Empty registered slice: {slice_id}")
        for condition in conditions:
            condition_id = condition["id"]
            for run_index, run_spec in enumerate(condition["runs"]):
                exact = 0
                precisions: list[float] = []
                recalls: list[float] = []
                f1s: list[float] = []
                predicted_cardinality: list[int] = []
                for record in subset:
                    gold = record["gold_ids"]
                    prediction = record["conditions"][condition_id]["predicted_sets"][run_index]
                    exact += prediction == gold
                    overlap = len(gold & prediction)
                    precision = overlap / len(prediction) if prediction else 0.0
                    recall = overlap / len(gold)
                    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
                    precisions.append(precision)
                    recalls.append(recall)
                    f1s.append(f1)
                    predicted_cardinality.append(len(prediction))
                output.append(
                    {
                        "condition_id": condition_id,
                        "run_index": run_index,
                        "seed": "" if run_spec.get("seed") is None else run_spec["seed"],
                        "slice": slice_id,
                        "row_count": len(subset),
                        "exact_count": exact,
                        "exact_match_accuracy": fmt(exact / len(subset)),
                        "samples_precision": fmt(statistics.fmean(precisions)),
                        "samples_recall": fmt(statistics.fmean(recalls)),
                        "samples_f1": fmt(statistics.fmean(f1s)),
                        "gold_cardinality_mean": fmt(
                            statistics.fmean(len(record["gold_ids"]) for record in subset)
                        ),
                        "predicted_cardinality_mean": fmt(
                            statistics.fmean(predicted_cardinality)
                        ),
                    }
                )
    return output


def binary_label_metrics(
    records: list[dict[str, Any]], condition_id: str, run_index: int, label_id: int
) -> dict[str, float]:
    tp = fp = fn = 0
    for record in records:
        gold = label_id in record["gold_ids"]
        prediction = label_id in record["conditions"][condition_id]["predicted_sets"][run_index]
        tp += gold and prediction
        fp += not gold and prediction
        fn += gold and not prediction
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def build_per_label_metrics(
    records: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    labels: list[str],
    official_f1: dict[str, float],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    output: list[dict[str, Any]] = []
    summaries: dict[str, dict[str, Any]] = {}
    for condition in conditions:
        condition_id = condition["id"]
        condition_f1_by_run: list[list[float]] = [[] for _ in condition["runs"]]
        per_label_summary: dict[str, Any] = {}
        for label_id, label in enumerate(labels):
            run_metrics = [
                binary_label_metrics(records, condition_id, run_index, label_id)
                for run_index in range(len(condition["runs"]))
            ]
            for run_index, metrics in enumerate(run_metrics):
                condition_f1_by_run[run_index].append(metrics["f1"])
            support = sum(label_id in record["gold_ids"] for record in records)
            precision_values = [item["precision"] for item in run_metrics]
            recall_values = [item["recall"] for item in run_metrics]
            f1_values = [item["f1"] for item in run_metrics]
            f1_mean = statistics.fmean(f1_values)
            output.append(
                {
                    "condition_id": condition_id,
                    "label_id": label_id,
                    "label": label,
                    "support": support,
                    "run_count": len(run_metrics),
                    "tp_mean": fmt(statistics.fmean(item["tp"] for item in run_metrics)),
                    "fp_mean": fmt(statistics.fmean(item["fp"] for item in run_metrics)),
                    "fn_mean": fmt(statistics.fmean(item["fn"] for item in run_metrics)),
                    "precision_mean": fmt(statistics.fmean(precision_values)),
                    "precision_sample_std": fmt(sample_std(precision_values)),
                    "recall_mean": fmt(statistics.fmean(recall_values)),
                    "recall_sample_std": fmt(sample_std(recall_values)),
                    "f1_mean": fmt(f1_mean),
                    "f1_sample_std": fmt(sample_std(f1_values)),
                    "official_test_f1_reference": fmt(official_f1[label]),
                    "local_dev_minus_official_test_reference": fmt(
                        f1_mean - official_f1[label]
                    ),
                }
            )
            per_label_summary[label] = {
                "f1_mean": f1_mean,
                "recall_mean": statistics.fmean(recall_values),
                "support": support,
            }
        macro_values = [statistics.fmean(values) for values in condition_f1_by_run]
        summaries[condition_id] = {
            "macro_f1_mean": statistics.fmean(macro_values),
            "macro_f1_sample_std": sample_std(macro_values),
            "macro_f1_values": macro_values,
            "per_label": per_label_summary,
        }
    return output, summaries


def build_missed_spurious_pairs(
    records: list[dict[str, Any]], conditions: list[dict[str, Any]], labels: list[str]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for condition in conditions:
        condition_id = condition["id"]
        pairs: Counter[tuple[int, int]] = Counter()
        mixed_run_rows = 0
        for record in records:
            gold = record["gold_ids"]
            for prediction in record["conditions"][condition_id]["predicted_sets"]:
                missed = gold - prediction
                spurious = prediction - gold
                if missed and spurious:
                    mixed_run_rows += 1
                    for missed_id in missed:
                        for spurious_id in spurious:
                            pairs[(missed_id, spurious_id)] += 1
        for (missed_id, spurious_id), count in sorted(
            pairs.items(), key=lambda item: (-item[1], item[0])
        ):
            output.append(
                {
                    "condition_id": condition_id,
                    "missed_label": labels[missed_id],
                    "spurious_label": labels[spurious_id],
                    "pair_count": count,
                    "mixed_run_rows": mixed_run_rows,
                    "pair_count_per_mixed_run_row": fmt(count / mixed_run_rows),
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


def build_pairwise_transitions(
    records: list[dict[str, Any]], comparisons: list[tuple[str, str, str]]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for comparison_id, source_id, target_id in comparisons:
        source_runs = records[0]["conditions"][source_id]["run_count"]
        target_runs = records[0]["conditions"][target_id]["run_count"]
        matrix = Counter(
            (
                record["conditions"][source_id]["correct_count"],
                record["conditions"][target_id]["correct_count"],
            )
            for record in records
        )
        for source_count in range(source_runs + 1):
            for target_count in range(target_runs + 1):
                count = matrix[(source_count, target_count)]
                output.append(
                    {
                        "comparison_id": comparison_id,
                        "source_condition": source_id,
                        "target_condition": target_id,
                        "source_correct_count": source_count,
                        "source_run_count": source_runs,
                        "target_correct_count": target_count,
                        "target_run_count": target_runs,
                        "transition": transition_name(
                            source_count, target_count, source_runs, target_runs
                        ),
                        "row_count": count,
                        "rate": fmt(count / len(records)),
                    }
                )
    return output


def prediction_jaccard(left: frozenset[int], right: frozenset[int]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def build_seed_agreement(
    records: list[dict[str, Any]], conditions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for condition in conditions:
        condition_id = condition["id"]
        runs = condition["runs"]
        for left_index in range(len(runs)):
            for right_index in range(left_index + 1, len(runs)):
                set_agreement = 0
                correctness_agreement = 0
                both_exact = 0
                jaccards: list[float] = []
                for record in records:
                    gold = record["gold_ids"]
                    left = record["conditions"][condition_id]["predicted_sets"][left_index]
                    right = record["conditions"][condition_id]["predicted_sets"][right_index]
                    set_agreement += left == right
                    left_correct = left == gold
                    right_correct = right == gold
                    correctness_agreement += left_correct == right_correct
                    both_exact += left_correct and right_correct
                    jaccards.append(prediction_jaccard(left, right))
                output.append(
                    {
                        "condition_id": condition_id,
                        "left_seed": runs[left_index]["seed"],
                        "right_seed": runs[right_index]["seed"],
                        "row_count": len(records),
                        "exact_prediction_set_agreement": fmt(set_agreement / len(records)),
                        "mean_prediction_set_jaccard": fmt(statistics.fmean(jaccards)),
                        "correctness_agreement": fmt(correctness_agreement / len(records)),
                        "both_exact_rate": fmt(both_exact / len(records)),
                    }
                )
    return output


def deterministic_key(seed: str, role: str, row_number: int) -> str:
    return hashlib.sha256(f"{seed}:{role}:{row_number}".encode()).hexdigest()


def least_supported_label(
    record: dict[str, Any], support: dict[int, int], labels: list[str]
) -> str:
    label_id = min(record["gold_ids"], key=lambda item: (support[item], item))
    return labels[label_id]


def stratified_select(
    candidates: list[dict[str, Any]],
    limit: int,
    role: str,
    seed: str,
    support: dict[int, int],
    labels: list[str],
) -> list[dict[str, Any]]:
    ordered = sorted(
        candidates, key=lambda record: deterministic_key(seed, role, record["row_number"])
    )
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    per_stratum: Counter[str] = Counter()
    for record in ordered:
        stratum = least_supported_label(record, support, labels)
        if per_stratum[stratum] >= 2:
            continue
        selected.append(record)
        selected_ids.add(record["row_number"])
        per_stratum[stratum] += 1
        if len(selected) == limit:
            return selected
    for record in ordered:
        if record["row_number"] in selected_ids:
            continue
        selected.append(record)
        if len(selected) == limit:
            break
    return selected


def select_cases(
    records: list[dict[str, Any]],
    config: dict[str, Any],
    labels: list[str],
    support: dict[int, int],
    long_tail_ids: set[int],
    neutral_id: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    bert_id = "exp-020-bert"
    frozen_id = "exp-025-frozen-qwen"
    lora_id = "exp-029-lora-qwen"
    selected: list[dict[str, Any]] = []
    used: set[int] = set()
    realized: dict[str, int] = {}
    seed = config["sampling"]["seed"]

    def eligible(role: str) -> list[dict[str, Any]]:
        available = [record for record in records if record["row_number"] not in used]
        if role == "lora_over_bert_recoveries":
            return [
                record
                for record in available
                if record["conditions"][bert_id]["correct_count"] == 0
                and record["conditions"][lora_id]["correct_count"] == 3
            ]
        if role == "bert_over_lora_regressions":
            return [
                record
                for record in available
                if record["conditions"][bert_id]["correct_count"] == 3
                and record["conditions"][lora_id]["correct_count"] == 0
            ]
        if role == "lora_over_frozen_recoveries":
            return [
                record
                for record in available
                if record["conditions"][frozen_id]["correct_count"] == 0
                and record["conditions"][lora_id]["correct_count"] == 3
            ]
        if role == "neutral_cooccurrence_errors":
            return [
                record
                for record in available
                if neutral_id in record["gold_ids"]
                and len(record["gold_ids"]) > 1
                and record["conditions"][lora_id]["correct_count"] == 0
            ]
        if role == "shared_errors":
            return [
                record
                for record in available
                if record["conditions"][bert_id]["correct_count"] == 0
                and record["conditions"][frozen_id]["correct_count"] == 0
                and record["conditions"][lora_id]["correct_count"] == 0
            ]
        if role == "ordinary_lora_errors":
            return [
                record
                for record in available
                if record["conditions"][lora_id]["correct_count"] <= 1
            ]
        raise ValueError(f"Unknown sample role: {role}")

    for role_spec in config["sampling"]["roles"]:
        role = role_spec["id"]
        candidates = eligible(role)
        if role == "ordinary_lora_errors":
            long_tail = [record for record in candidates if record["gold_ids"] & long_tail_ids]
            other = [record for record in candidates if not record["gold_ids"] & long_tail_ids]
            target = min(role_spec["long_tail_target"], role_spec["limit"])
            chosen = stratified_select(
                long_tail, target, role, seed, support, labels
            )
            remaining = role_spec["limit"] - len(chosen)
            chosen.extend(
                stratified_select(other, remaining, role, seed, support, labels)
            )
            if len(chosen) < role_spec["limit"]:
                chosen_ids = {record["row_number"] for record in chosen}
                leftovers = [
                    record for record in candidates if record["row_number"] not in chosen_ids
                ]
                chosen.extend(
                    stratified_select(
                        leftovers,
                        role_spec["limit"] - len(chosen),
                        role,
                        seed,
                        support,
                        labels,
                    )
                )
        else:
            chosen = stratified_select(
                candidates, role_spec["limit"], role, seed, support, labels
            )
        for record in chosen:
            selected.append({"record": record, "role": role})
            used.add(record["row_number"])
        realized[role] = len(chosen)

    if len(selected) > config["sampling"]["maximum_unique_rows"]:
        raise ValueError("Qualitative sample exceeds frozen maximum")
    return selected, {"realized_role_counts": realized, "unique_rows": len(selected)}


def manifest_rows(
    selections: list[dict[str, Any]], labels: list[str], support: dict[int, int]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for sample_rank, selection in enumerate(selections, start=1):
        record = selection["record"]
        gold = record["gold_ids"]
        row: dict[str, Any] = {
            "sample_rank": sample_rank,
            "role": selection["role"],
            "row_number": record["row_number"],
            "gold_label_ids": id_string(gold),
            "gold_labels": label_string(gold, labels),
            "gold_cardinality": len(gold),
            "least_supported_gold_label": least_supported_label(record, support, labels),
            "bert_correct_count": record["conditions"]["exp-020-bert"]["correct_count"],
            "bert_predictions_by_seed": ";".join(
                label_string(item, labels) or "<empty>"
                for item in record["conditions"]["exp-020-bert"]["predicted_sets"]
            ),
            "frozen_qwen_correct": record["conditions"]["exp-025-frozen-qwen"]["correct_count"],
            "frozen_qwen_prediction": label_string(
                record["conditions"]["exp-025-frozen-qwen"]["predicted_sets"][0], labels
            )
            or "<empty>",
            "lora_correct_count": record["conditions"]["exp-029-lora-qwen"]["correct_count"],
            "lora_predictions_by_seed": ";".join(
                label_string(item, labels) or "<empty>"
                for item in record["conditions"]["exp-029-lora-qwen"]["predicted_sets"]
            ),
        }
        output.append(row)
    return output


def annotation_template(manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "sample_rank": row["sample_rank"],
            "role": row["role"],
            "row_number": row["row_number"],
            "gold_labels": row["gold_labels"],
            "evidence_flags": "",
            "primary_possible_source": "",
            "reviewer_confidence": "",
        }
        for row in manifest
    ]


def summarize_condition(
    condition_id: str,
    stability_rows: list[dict[str, Any]],
    error_mode_rows: list[dict[str, Any]],
    slice_rows: list[dict[str, Any]],
    per_label_summary: dict[str, Any],
) -> dict[str, Any]:
    all_stability = next(
        row
        for row in stability_rows
        if row["condition_id"] == condition_id and row["stratum"] == "ALL"
    )
    all_slice = [
        row
        for row in slice_rows
        if row["condition_id"] == condition_id and row["slice"] == "all"
    ]
    modes_by_run: dict[int, dict[str, int]] = defaultdict(dict)
    for row in error_mode_rows:
        if row["condition_id"] == condition_id:
            modes_by_run[int(row["run_index"])][row["error_mode"]] = int(row["row_count"])
    return {
        "all_runs_correct": int(all_stability["all_runs_correct"]),
        "all_runs_wrong": int(all_stability["all_runs_wrong"]),
        "mixed_outcome": int(all_stability["mixed_outcome"]),
        "exact_match_accuracy_mean": statistics.fmean(
            float(row["exact_match_accuracy"]) for row in all_slice
        ),
        "exact_match_accuracy_sample_std": sample_std(
            [float(row["exact_match_accuracy"]) for row in all_slice]
        ),
        "samples_f1_mean": statistics.fmean(float(row["samples_f1"]) for row in all_slice),
        "predicted_cardinality_mean": statistics.fmean(
            float(row["predicted_cardinality_mean"]) for row in all_slice
        ),
        "error_mode_mean_counts": {
            mode: statistics.fmean(run[mode] for run in modes_by_run.values())
            for mode in [
                "exact",
                "underprediction_only",
                "overprediction_only",
                "mixed_fp_fn",
                "empty_prediction",
            ]
        },
        **{key: value for key, value in per_label_summary.items() if key != "per_label"},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    started = time.perf_counter()
    config_path = args.config.resolve()
    config = read_json(config_path)
    output_dir = project_path(config["output_dir"])
    if output_dir.exists():
        raise FileExistsError(f"Output directory already exists: {output_dir}")

    protocol_path = project_path(config["protocol"]["path"])
    if not protocol_path.is_file():
        raise FileNotFoundError(protocol_path)
    source_verifications = validate_sources(config)
    labels_path = verify_file(config["data"]["labels"])
    dev_path = verify_file(config["data"]["dev"])
    labels = load_labels(labels_path, config["data"]["labels"]["count"])
    if set(config["official_reference"]["per_label_f1"]) != set(labels):
        raise ValueError("Official per-label reference does not match label order")

    dev_rows = load_dev(dev_path, labels, config["data"]["dev"]["rows"])
    support = Counter(
        label_id for row in dev_rows for label_id in row["gold_ids"]
    )
    long_tail_ids = {
        label_id
        for label_id, count in support.items()
        if count < config["sampling"]["long_tail_support_below"]
    }
    neutral_id = labels.index("neutral")

    predictions: dict[str, list[dict[int, dict[str, Any]]]] = {}
    prediction_artifacts: dict[str, Any] = {}
    for condition in config["conditions"]:
        runs = [
            load_prediction_run(spec, labels, config["data"]["dev"]["rows"])
            for spec in condition["runs"]
        ]
        predictions[condition["id"]] = runs
        prediction_artifacts[condition["id"]] = [
            artifact_record(project_path(spec["path"])) for spec in condition["runs"]
        ]

    records = build_records(dev_rows, predictions)
    condition_ids = [condition["id"] for condition in config["conditions"]]
    stability_rows = build_condition_stability(records, condition_ids, labels)
    error_mode_rows = build_error_modes(records, config["conditions"])
    slice_rows = build_slice_metrics(
        records, config["conditions"], neutral_id, long_tail_ids
    )
    per_label_rows, per_label_summaries = build_per_label_metrics(
        records,
        config["conditions"],
        labels,
        config["official_reference"]["per_label_f1"],
    )
    pair_rows = build_missed_spurious_pairs(records, config["conditions"], labels)
    transition_rows = build_pairwise_transitions(
        records,
        [
            ("bert_to_lora", "exp-020-bert", "exp-029-lora-qwen"),
            ("frozen_qwen_to_lora", "exp-025-frozen-qwen", "exp-029-lora-qwen"),
        ],
    )
    agreement_rows = build_seed_agreement(records, config["conditions"])
    selections, sampling_summary = select_cases(
        records, config, labels, support, long_tail_ids, neutral_id
    )
    manifest = manifest_rows(selections, labels, support)

    output_dir.mkdir(parents=True)
    private_dir = output_dir / "private"
    private_dir.mkdir()

    csv_outputs = {
        "condition_stability.csv": (
            [
                "condition_id",
                "stratum",
                "row_count",
                "runs_per_row",
                "all_runs_correct",
                "all_runs_wrong",
                "mixed_outcome",
                "all_runs_correct_rate",
                "all_runs_wrong_rate",
                "mixed_outcome_rate",
            ],
            stability_rows,
        ),
        "error_modes.csv": (
            ["condition_id", "run_index", "seed", "error_mode", "row_count", "rate"],
            error_mode_rows,
        ),
        "slice_metrics.csv": (
            [
                "condition_id",
                "run_index",
                "seed",
                "slice",
                "row_count",
                "exact_count",
                "exact_match_accuracy",
                "samples_precision",
                "samples_recall",
                "samples_f1",
                "gold_cardinality_mean",
                "predicted_cardinality_mean",
            ],
            slice_rows,
        ),
        "per_label_metrics.csv": (
            [
                "condition_id",
                "label_id",
                "label",
                "support",
                "run_count",
                "tp_mean",
                "fp_mean",
                "fn_mean",
                "precision_mean",
                "precision_sample_std",
                "recall_mean",
                "recall_sample_std",
                "f1_mean",
                "f1_sample_std",
                "official_test_f1_reference",
                "local_dev_minus_official_test_reference",
            ],
            per_label_rows,
        ),
        "missed_spurious_pairs.csv": (
            [
                "condition_id",
                "missed_label",
                "spurious_label",
                "pair_count",
                "mixed_run_rows",
                "pair_count_per_mixed_run_row",
            ],
            pair_rows,
        ),
        "pairwise_transitions.csv": (
            [
                "comparison_id",
                "source_condition",
                "target_condition",
                "source_correct_count",
                "source_run_count",
                "target_correct_count",
                "target_run_count",
                "transition",
                "row_count",
                "rate",
            ],
            transition_rows,
        ),
        "seed_agreement.csv": (
            [
                "condition_id",
                "left_seed",
                "right_seed",
                "row_count",
                "exact_prediction_set_agreement",
                "mean_prediction_set_jaccard",
                "correctness_agreement",
                "both_exact_rate",
            ],
            agreement_rows,
        ),
        "sample_manifest.csv": (
            list(manifest[0]),
            manifest,
        ),
        "manual_annotations.csv": (
            [
                "sample_rank",
                "role",
                "row_number",
                "gold_labels",
                "evidence_flags",
                "primary_possible_source",
                "reviewer_confidence",
            ],
            annotation_template(manifest),
        ),
    }
    for filename, (fieldnames, rows) in csv_outputs.items():
        write_csv(output_dir / filename, fieldnames, rows)

    private_path = private_dir / "selected_text.private.jsonl"
    with private_path.open("w", encoding="utf-8") as handle:
        for rank, selection in enumerate(selections, start=1):
            record = selection["record"]
            payload = {
                "gold_labels": label_string(record["gold_ids"], labels),
                "role": selection["role"],
                "row_number": record["row_number"],
                "sample_rank": rank,
                "text": record["text"],
            }
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    neutral_cooccurrence_rows = sum(
        neutral_id in record["gold_ids"] and len(record["gold_ids"]) > 1
        for record in records
    )
    shared_stable_errors = sum(
        record["conditions"]["exp-020-bert"]["correct_count"] == 0
        and record["conditions"]["exp-025-frozen-qwen"]["correct_count"] == 0
        and record["conditions"]["exp-029-lora-qwen"]["correct_count"] == 0
        for record in records
    )
    condition_summary = {
        condition_id: summarize_condition(
            condition_id,
            stability_rows,
            error_mode_rows,
            slice_rows,
            per_label_summaries[condition_id],
        )
        for condition_id in condition_ids
    }
    transition_summary: dict[str, dict[str, int]] = {}
    for comparison_id in {row["comparison_id"] for row in transition_rows}:
        counts = Counter()
        for row in transition_rows:
            if row["comparison_id"] == comparison_id:
                counts[row["transition"]] += int(row["row_count"])
        transition_summary[comparison_id] = dict(sorted(counts.items()))

    aggregate_summary = {
        "condition_summary": condition_summary,
        "experiment_id": config["experiment_id"],
        "gold_cardinality_mean": statistics.fmean(
            len(record["gold_ids"]) for record in records
        ),
        "long_tail_labels": {
            labels[label_id]: support[label_id] for label_id in sorted(long_tail_ids)
        },
        "neutral_cooccurrence_rows": neutral_cooccurrence_rows,
        "row_count": len(records),
        "sampling": sampling_summary,
        "shared_stable_error_rows": shared_stable_errors,
        "split": "dev",
        "test_accessed": False,
        "transition_summary": transition_summary,
    }
    write_json(output_dir / "aggregate_summary.json", aggregate_summary)

    official_reference = {
        **config["official_reference"],
        "local_exp020_dev_macro_f1_mean": condition_summary["exp-020-bert"]["macro_f1_mean"],
        "local_exp020_dev_macro_f1_sample_std": condition_summary["exp-020-bert"][
            "macro_f1_sample_std"
        ],
        "local_dev_minus_official_test_macro_f1_reference": condition_summary[
            "exp-020-bert"
        ]["macro_f1_mean"]
        - config["official_reference"]["test_macro_f1"],
        "official_validation_comparison_available": False,
    }
    write_json(output_dir / "official_reference.json", official_reference)

    public_artifacts = {
        path.name: artifact_record(path)
        for path in sorted(output_dir.iterdir())
        if path.is_file()
    }
    analysis_manifest = {
        "artifacts": public_artifacts,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": artifact_record(config_path),
        "data": {
            "dev": artifact_record(dev_path),
            "labels": artifact_record(labels_path),
            "test_absent": not project_path(config["data"]["test_path"]).exists(),
        },
        "experiment_id": config["experiment_id"],
        "implementation": artifact_record(Path(__file__).resolve()),
        "prediction_artifacts": prediction_artifacts,
        "private_selected_text": artifact_record(private_path),
        "protocol": artifact_record(protocol_path),
        "source_verifications": source_verifications,
        "split": "dev",
        "status": "AwaitingManualReview",
        "test_accessed": False,
        "wall_seconds": time.perf_counter() - started,
    }
    write_json(output_dir / "analysis_manifest.json", analysis_manifest)

    print(
        json.dumps(
            {
                "experiment_id": config["experiment_id"],
                "output_dir": str(output_dir),
                "sample_rows": len(selections),
                "status": "AwaitingManualReview",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
