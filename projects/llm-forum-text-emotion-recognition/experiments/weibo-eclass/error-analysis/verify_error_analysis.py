#!/usr/bin/env python3
"""Independently verify EXP-048 without importing its analysis runner."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import statistics
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def artifact_record(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "sha256": sha256_file(path),
    }


def verify_hash(path: Path, expected: str) -> None:
    if not path.is_file() or sha256_file(path) != expected:
        raise ValueError(f"Pinned artifact mismatch: {path}")


def f12(value: float) -> str:
    return f"{value:.12f}"


def stdev(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def metric(golds: list[str], predictions: list[str], labels: list[str]) -> dict[str, Any]:
    classes = labels + ([INVALID] if INVALID in predictions else [])
    confusion = {gold: Counter() for gold in labels}
    for gold, prediction in zip(golds, predictions):
        confusion[gold][prediction] += 1
    per_class: dict[str, dict[str, Any]] = {}
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[gold][label] for gold in labels if gold != label)
        fn = sum(confusion[label][pred] for pred in classes if pred != label)
        support = sum(confusion[label].values())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"tp": tp, "fp": fp, "fn": fn, "support": support, "precision": precision, "recall": recall, "f1": f1}
    return {
        "accuracy": sum(gold == pred for gold, pred in zip(golds, predictions)) / len(golds),
        "macro_precision": statistics.fmean(row["precision"] for row in per_class.values()),
        "macro_recall": statistics.fmean(row["recall"] for row in per_class.values()),
        "macro_f1": statistics.fmean(row["f1"] for row in per_class.values()),
        "weighted_f1": sum(row["f1"] * row["support"] for row in per_class.values()) / len(golds),
        "per_class": per_class,
        "confusion": confusion,
    }


def transition_name(source: int, target: int, source_runs: int, target_runs: int) -> str:
    if source == 0 and target == target_runs:
        return "stable_recovery"
    if source == source_runs and target == 0:
        return "stable_regression"
    if target / target_runs > source / source_runs:
        return "higher_correct_rate"
    if target / target_runs < source / source_runs:
        return "lower_correct_rate"
    return "unchanged_correct_rate"


def load_sources(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, list[list[dict[str, Any]]]]]:
    labels = config["data"]["labels"]
    validation_spec = config["data"]["validation"]
    validation_path = PROJECT_ROOT / validation_spec["path"]
    verify_hash(validation_path, validation_spec["sha256"])
    validation: list[dict[str, Any]] = []
    with validation_path.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            row = json.loads(line)
            target = row["views"]["target_only"]["target"]
            if row["views"]["previous_context"]["target"] != target:
                raise ValueError(f"Target-view mismatch at row {index}")
            previous = row["views"]["previous_context"]["previous"]
            if row["context_available"]:
                if not isinstance(previous, str):
                    raise ValueError(f"Missing available context at row {index}")
            elif previous is not None:
                raise ValueError(f"Unexpected first-clause context at row {index}")
            validation.append(
                {
                    "row_index": index,
                    "sample_id": row["sample_id"],
                    "group_id": row["group_id"],
                    "gold": row["label"],
                    "context_available": row["context_available"],
                    "ambiguous_target": row["ambiguous_target"],
                    "previous": previous,
                    "target": target,
                }
            )
    if len(validation) != validation_spec["rows"] or len({row["sample_id"] for row in validation}) != len(validation):
        raise ValueError("Validation count or identity mismatch")

    all_runs: dict[str, list[list[dict[str, Any]]]] = {}
    for condition in config["conditions"]:
        condition_runs: list[list[dict[str, Any]]] = []
        for run_spec in condition["runs"]:
            path = PROJECT_ROOT / run_spec["path"]
            verify_hash(path, run_spec["sha256"])
            rows: list[dict[str, Any]] = []
            if condition["format"] == "generative_jsonl":
                with path.open(encoding="utf-8") as handle:
                    raw_rows = [json.loads(line) for line in handle]
                for index, raw in enumerate(raw_rows):
                    source = validation[index]
                    if (raw["row_index"], raw["sample_id"], raw["group_id"], raw["gold_label"], raw["view"]) != (index, source["sample_id"], source["group_id"], source["gold"], "target_only"):
                        raise ValueError(f"Generative alignment mismatch: {path}, row {index}")
                    valid = raw["parse"]["valid"]
                    prediction = raw["prediction"] if valid else INVALID
                    if valid and prediction not in labels:
                        raise ValueError(f"Invalid parsed label: {path}, row {index}")
                    rows.append(
                        {
                            "prediction": prediction,
                            "parse_valid": valid,
                            "likely_truncated": raw["likely_truncated"],
                            "failed_output": (not valid) or raw["likely_truncated"],
                            "parse_error": raw["parse"].get("error") or "",
                        }
                    )
            else:
                with path.open(encoding="utf-8", newline="") as handle:
                    raw_rows = list(csv.DictReader(handle))
                for index, raw in enumerate(raw_rows):
                    source = validation[index]
                    if (raw["sample_id"], raw["group_id"], raw["gold"]) != (source["sample_id"], source["group_id"], source["gold"]):
                        raise ValueError(f"Encoder alignment mismatch: {path}, row {index}")
                    if raw["prediction"] not in labels:
                        raise ValueError(f"Encoder label mismatch: {path}, row {index}")
                    rows.append({"prediction": raw["prediction"], "parse_valid": True, "likely_truncated": False, "failed_output": False, "parse_error": ""})
            if len(rows) != len(validation):
                raise ValueError(f"Prediction count mismatch: {path}")
            condition_runs.append(rows)
        all_runs[condition["id"]] = condition_runs
    return validation, all_runs


def records_from(validation: list[dict[str, Any]], runs: dict[str, list[list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    output = []
    for index, source in enumerate(validation):
        conditions = {}
        for condition_id, condition_runs in runs.items():
            predictions = [run[index]["prediction"] for run in condition_runs]
            conditions[condition_id] = {"predictions": predictions, "correct_count": sum(pred == source["gold"] for pred in predictions), "runs": [run[index] for run in condition_runs]}
        output.append({**source, "conditions": conditions})
    return output


def normalized(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{key: str(value) for key, value in row.items()} for row in rows]


def assert_csv(path: Path, expected: list[dict[str, Any]]) -> None:
    if read_csv(path) != normalized(expected):
        raise ValueError(f"Recomputed CSV differs: {path}")


def deterministic_key(seed: str, role: str, sample_id: str) -> str:
    return hashlib.sha256(f"{seed}:{role}:{sample_id}".encode()).hexdigest()


def public_case_id(sample_id: str) -> str:
    return "case-" + hashlib.sha256(f"EXP-048:{sample_id}".encode()).hexdigest()[:16]


def select_cases(records: list[dict[str, Any]], sampling: dict[str, Any]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    for role_spec in sampling["roles"]:
        role = role_spec["id"]
        available = [record for record in records if record["sample_id"] not in used]
        if role == "format_recoveries":
            candidates = [record for record in available if record["conditions"]["reference"]["runs"][0]["failed_output"] and record["conditions"]["lora"]["correct_count"] == 3]
        elif role == "valid_reference_recoveries":
            candidates = [record for record in available if not record["conditions"]["reference"]["runs"][0]["failed_output"] and record["conditions"]["reference"]["correct_count"] == 0 and record["conditions"]["lora"]["correct_count"] == 3]
        elif role == "lora_over_encoder":
            candidates = [record for record in available if record["conditions"]["encoder"]["correct_count"] == 0 and record["conditions"]["lora"]["correct_count"] == 3]
        elif role == "encoder_over_lora":
            candidates = [record for record in available if record["conditions"]["encoder"]["correct_count"] == 3 and record["conditions"]["lora"]["correct_count"] == 0]
        elif role == "shared_stable_errors":
            candidates = [record for record in available if record["conditions"]["encoder"]["correct_count"] == 0 and record["conditions"]["lora"]["correct_count"] == 0]
        elif role == "seed_unstable_lora":
            candidates = [record for record in available if record["conditions"]["lora"]["correct_count"] in {1, 2}]
        else:
            raise ValueError(f"Unknown role: {role}")
        ordered = sorted(candidates, key=lambda row: deterministic_key(sampling["seed"], role, row["sample_id"]))
        chosen: list[dict[str, Any]] = []
        chosen_ids: set[str] = set()
        per_label: Counter[str] = Counter()
        for record in ordered:
            if per_label[record["gold"]] >= 2:
                continue
            chosen.append(record); chosen_ids.add(record["sample_id"]); per_label[record["gold"]] += 1
            if len(chosen) == role_spec["limit"]:
                break
        if len(chosen) < role_spec["limit"]:
            for record in ordered:
                if record["sample_id"] in chosen_ids:
                    continue
                chosen.append(record)
                if len(chosen) == role_spec["limit"]:
                    break
        for record in chosen:
            selected.append({"role": role, "record": record})
            used.add(record["sample_id"])
    return selected


def verify_private(output_dir: Path, selections: list[dict[str, Any]]) -> dict[str, Any]:
    path = output_dir / "private" / "selected_cases.private.jsonl"
    ignored = subprocess.run(["git", "check-ignore", "-q", str(path)], cwd=REPO_ROOT, check=False).returncode == 0
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", str(path)], cwd=REPO_ROOT, check=False, capture_output=True).returncode == 0
    if not ignored or tracked or (path.stat().st_mode & 0o077):
        raise ValueError("Private review file boundary failed")
    with path.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle]
    if len(rows) != len(selections):
        raise ValueError("Private review count mismatch")
    for rank, (observed, selection) in enumerate(zip(rows, selections), start=1):
        record = selection["record"]
        expected = {
            "sample_rank": rank,
            "case_id": public_case_id(record["sample_id"]),
            "sample_id": record["sample_id"],
            "group_id": record["group_id"],
            "role": selection["role"],
            "gold_label": record["gold"],
            "context_available": record["context_available"],
            "ambiguous_target": record["ambiguous_target"],
            "previous": record["previous"],
            "target": record["target"],
            "reference_prediction": record["conditions"]["reference"]["predictions"][0],
            "reference_parse_error": record["conditions"]["reference"]["runs"][0]["parse_error"],
            "reference_likely_truncated": record["conditions"]["reference"]["runs"][0]["likely_truncated"],
            "lora_predictions_by_seed": record["conditions"]["lora"]["predictions"],
            "encoder_predictions_by_seed": record["conditions"]["encoder"]["predictions"],
        }
        if observed != expected:
            raise ValueError(f"Private case mismatch at rank {rank}")

    public_files = [path for path in output_dir.iterdir() if path.is_file() and path.suffix in {".csv", ".json", ".md", ".log"}]
    payload = "\n".join(path.read_text(encoding="utf-8") for path in public_files)
    leaks = 0
    for row in rows:
        for private_value in (row["sample_id"], row["group_id"], row["target"], row["previous"]):
            if isinstance(private_value, str) and len(private_value) >= 8 and private_value in payload:
                leaks += 1
    forbidden_headers = {"sample_id", "group_id", "text", "target", "previous", "raw_output", "reasoning", "note", "notes", "rationale"}
    for csv_path in output_dir.glob("*.csv"):
        with csv_path.open(encoding="utf-8", newline="") as handle:
            if forbidden_headers & set(csv.DictReader(handle).fieldnames or []):
                raise ValueError(f"Private column leaked: {csv_path}")
    if leaks:
        raise ValueError(f"Private values leaked into public artifacts: {leaks}")
    return {"private_file_gitignored": ignored, "private_file_tracked": tracked, "private_mode": oct(path.stat().st_mode & 0o777), "private_rows_verified": len(rows), "raw_value_leak_count": leaks, "public_files_scanned": len(public_files)}


def verify_artifacts(records: dict[str, dict[str, Any]], skip: set[str] | None = None) -> int:
    checked = 0
    skip = skip or set()
    for name, record in records.items():
        if name in skip:
            continue
        path = PROJECT_ROOT / record["path"]
        if artifact_record(path) != record:
            raise ValueError(f"Artifact record mismatch: {name}")
        checked += 1
    return checked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = read_json(config_path)
    output_dir = PROJECT_ROOT / config["output_dir"]
    verification_path = output_dir / "verification.json"
    if verification_path.exists():
        raise FileExistsError("Verification already exists")
    if config.get("test_access") is not False:
        raise ValueError("Test access declaration changed")
    for spec in config["upstream_verifications"]:
        path = PROJECT_ROOT / spec["path"]
        verify_hash(path, spec["sha256"])
        if read_json(path).get("status") != spec["expected_status"]:
            raise ValueError("Upstream verification status changed")

    validation, runs = load_sources(config)
    records = records_from(validation, runs)
    labels = config["data"]["labels"]
    support = Counter(record["gold"] for record in records)
    long_tail = {label for label, count in support.items() if count < config["sampling"]["long_tail_support_below"]}

    run_metrics_rows: list[dict[str, Any]] = []
    metrics_by_condition: dict[str, list[dict[str, Any]]] = {}
    golds = [record["gold"] for record in records]
    for condition in config["conditions"]:
        values = []
        for run_index, run_spec in enumerate(condition["runs"]):
            predictions = [record["conditions"][condition["id"]]["predictions"][run_index] for record in records]
            metrics = metric(golds, predictions, labels)
            run_rows = [record["conditions"][condition["id"]]["runs"][run_index] for record in records]
            metrics["parse_valid_rate"] = statistics.fmean(row["parse_valid"] for row in run_rows)
            metrics["failed_output_rate"] = statistics.fmean(row["failed_output"] for row in run_rows)
            values.append(metrics)
            run_metrics_rows.append({"condition_id": condition["id"], "run_index": run_index, "seed": "" if run_spec.get("seed") is None else run_spec["seed"], "rows": len(records), "accuracy": f12(metrics["accuracy"]), "macro_precision": f12(metrics["macro_precision"]), "macro_recall": f12(metrics["macro_recall"]), "macro_f1": f12(metrics["macro_f1"]), "weighted_f1": f12(metrics["weighted_f1"]), "parse_valid_rate": f12(metrics["parse_valid_rate"]), "failed_output_rate": f12(metrics["failed_output_rate"])})
        metrics_by_condition[condition["id"]] = values
    assert_csv(output_dir / "run_metrics.csv", run_metrics_rows)

    per_class_rows: list[dict[str, Any]] = []
    for condition in config["conditions"]:
        values = metrics_by_condition[condition["id"]]
        for label in labels:
            rows = [metric_row["per_class"][label] for metric_row in values]
            per_class_rows.append({"condition_id": condition["id"], "label": label, "support": rows[0]["support"], "run_count": len(rows), "tp_mean": f12(statistics.fmean(row["tp"] for row in rows)), "fp_mean": f12(statistics.fmean(row["fp"] for row in rows)), "fn_mean": f12(statistics.fmean(row["fn"] for row in rows)), "precision_mean": f12(statistics.fmean(row["precision"] for row in rows)), "precision_sample_std": f12(stdev([row["precision"] for row in rows])), "recall_mean": f12(statistics.fmean(row["recall"] for row in rows)), "recall_sample_std": f12(stdev([row["recall"] for row in rows])), "f1_mean": f12(statistics.fmean(row["f1"] for row in rows)), "f1_sample_std": f12(stdev([row["f1"] for row in rows]))})
    assert_csv(output_dir / "per_class_metrics.csv", per_class_rows)
    indexed = {(row["condition_id"], row["label"]): row for row in per_class_rows}
    class_gap = []
    for label in labels:
        lora, encoder = indexed[("lora", label)], indexed[("encoder", label)]
        class_gap.append({"label": label, "support": lora["support"], "lora_f1_mean": lora["f1_mean"], "encoder_f1_mean": encoder["f1_mean"], "lora_minus_encoder_f1": f12(float(lora["f1_mean"]) - float(encoder["f1_mean"])), "lora_minus_encoder_precision": f12(float(lora["precision_mean"]) - float(encoder["precision_mean"])), "lora_minus_encoder_recall": f12(float(lora["recall_mean"]) - float(encoder["recall_mean"]))})
    class_gap.sort(key=lambda row: float(row["lora_minus_encoder_f1"]))
    assert_csv(output_dir / "class_gap.csv", class_gap)

    confusion_rows = []
    for condition in config["conditions"]:
        condition_id = condition["id"]
        values = metrics_by_condition[condition_id]
        prediction_classes = labels + ([INVALID] if condition_id == "reference" else [])
        for gold in labels:
            for prediction in prediction_classes:
                if prediction == gold:
                    continue
                counts = [row["confusion"][gold][prediction] for row in values]
                if any(counts):
                    support_n = values[0]["per_class"][gold]["support"]
                    confusion_rows.append({"condition_id": condition_id, "gold": gold, "prediction": prediction, "support": support_n, "run_count": len(values), "count_mean": f12(statistics.fmean(counts)), "count_sample_std": f12(stdev(counts)), "rate_within_gold_mean": f12(statistics.fmean(counts) / support_n)})
    confusion_rows.sort(key=lambda row: (row["condition_id"], -float(row["count_mean"]), row["gold"], row["prediction"]))
    assert_csv(output_dir / "confusion_pairs.csv", confusion_rows)

    stability_rows = []
    strata = [("ALL", records)] + [(label, [record for record in records if record["gold"] == label]) for label in labels]
    for condition in config["conditions"]:
        run_count = len(condition["runs"])
        for stratum, subset in strata:
            correct = sum(record["conditions"][condition["id"]]["correct_count"] == run_count for record in subset)
            wrong = sum(record["conditions"][condition["id"]]["correct_count"] == 0 for record in subset)
            mixed = len(subset) - correct - wrong
            stability_rows.append({"condition_id": condition["id"], "stratum": stratum, "row_count": len(subset), "runs_per_row": run_count, "all_runs_correct": correct, "all_runs_wrong": wrong, "mixed_outcome": mixed, "all_runs_correct_rate": f12(correct / len(subset)), "all_runs_wrong_rate": f12(wrong / len(subset)), "mixed_outcome_rate": f12(mixed / len(subset))})
    assert_csv(output_dir / "condition_stability.csv", stability_rows)

    slices = [
        ("all", records),
        ("context_available", [row for row in records if row["context_available"]]),
        ("first_clause", [row for row in records if not row["context_available"]]),
        ("ambiguous_target", [row for row in records if row["ambiguous_target"]]),
        ("unambiguous_target", [row for row in records if not row["ambiguous_target"]]),
        ("no_emotion", [row for row in records if row["gold"] == "no_emotion"]),
        ("emotion_label", [row for row in records if row["gold"] != "no_emotion"]),
        ("long_tail_label", [row for row in records if row["gold"] in long_tail]),
        ("reference_output_valid", [row for row in records if not row["conditions"]["reference"]["runs"][0]["failed_output"]]),
        ("reference_output_failed", [row for row in records if row["conditions"]["reference"]["runs"][0]["failed_output"]]),
    ]
    slice_rows = []
    for slice_id, subset in slices:
        slice_golds = [row["gold"] for row in subset]
        for condition in config["conditions"]:
            for run_index, run_spec in enumerate(condition["runs"]):
                values = metric(slice_golds, [row["conditions"][condition["id"]]["predictions"][run_index] for row in subset], labels)
                slice_rows.append({"condition_id": condition["id"], "run_index": run_index, "seed": "" if run_spec.get("seed") is None else run_spec["seed"], "slice": slice_id, "row_count": len(subset), "accuracy": f12(values["accuracy"]), "macro_precision": f12(values["macro_precision"]), "macro_recall": f12(values["macro_recall"]), "macro_f1": f12(values["macro_f1"]), "weighted_f1": f12(values["weighted_f1"])})
    assert_csv(output_dir / "slice_metrics.csv", slice_rows)

    transition_rows = []
    for comparison_id, source_id, target_id in (("reference_to_lora", "reference", "lora"), ("encoder_to_lora", "encoder", "lora")):
        source_runs, target_runs = len(runs[source_id]), len(runs[target_id])
        counts = Counter((row["conditions"][source_id]["correct_count"], row["conditions"][target_id]["correct_count"]) for row in records)
        for source_count in range(source_runs + 1):
            for target_count in range(target_runs + 1):
                count = counts[(source_count, target_count)]
                transition_rows.append({"comparison_id": comparison_id, "source_condition": source_id, "target_condition": target_id, "source_correct_count": source_count, "source_run_count": source_runs, "target_correct_count": target_count, "target_run_count": target_runs, "transition": transition_name(source_count, target_count, source_runs, target_runs), "row_count": count, "rate": f12(count / len(records))})
    assert_csv(output_dir / "pairwise_transitions.csv", transition_rows)

    agreement_rows = []
    for condition in config["conditions"]:
        condition_id = condition["id"]
        for left in range(len(condition["runs"])):
            for right in range(left + 1, len(condition["runs"])):
                exact = correctness = both = 0
                for row in records:
                    predictions = row["conditions"][condition_id]["predictions"]
                    left_correct, right_correct = predictions[left] == row["gold"], predictions[right] == row["gold"]
                    exact += predictions[left] == predictions[right]
                    correctness += left_correct == right_correct
                    both += left_correct and right_correct
                agreement_rows.append({"condition_id": condition_id, "left_seed": condition["runs"][left]["seed"], "right_seed": condition["runs"][right]["seed"], "row_count": len(records), "exact_prediction_agreement": f12(exact / len(records)), "correctness_agreement": f12(correctness / len(records)), "both_correct_rate": f12(both / len(records))})
    assert_csv(output_dir / "seed_agreement.csv", agreement_rows)

    selections = select_cases(records, config["sampling"])
    realized = Counter(row["role"] for row in selections)
    manifest_rows = []
    for rank, selection in enumerate(selections, start=1):
        row = selection["record"]
        reference_run = row["conditions"]["reference"]["runs"][0]
        manifest_rows.append({"sample_rank": rank, "case_id": public_case_id(row["sample_id"]), "role": selection["role"], "gold_label": row["gold"], "gold_support": support[row["gold"]], "long_tail": str(row["gold"] in long_tail).lower(), "context_available": str(row["context_available"]).lower(), "ambiguous_target": str(row["ambiguous_target"]).lower(), "reference_output_status": "failed" if reference_run["failed_output"] else "valid", "reference_prediction": row["conditions"]["reference"]["predictions"][0], "lora_correct_count": row["conditions"]["lora"]["correct_count"], "lora_predictions_by_seed": ";".join(row["conditions"]["lora"]["predictions"]), "encoder_correct_count": row["conditions"]["encoder"]["correct_count"], "encoder_predictions_by_seed": ";".join(row["conditions"]["encoder"]["predictions"])})
    assert_csv(output_dir / "sample_manifest.csv", manifest_rows)

    def summary_values(condition_id: str) -> dict[str, Any]:
        values = metrics_by_condition[condition_id]
        output: dict[str, Any] = {}
        for field in ("accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1", "parse_valid_rate", "failed_output_rate"):
            field_values = [row[field] for row in values]
            output[f"{field}_mean"] = statistics.fmean(field_values)
            output[f"{field}_sample_std"] = stdev(field_values)
        return output
    aggregate_expected = {
        "experiment_id": config["experiment_id"], "split": "validation", "row_count": len(records),
        "label_support": dict(sorted(support.items())), "long_tail_labels": sorted(long_tail),
        "conditions": {condition_id: summary_values(condition_id) for condition_id in metrics_by_condition},
        "sampling": {"realized_role_counts": {role["id"]: realized[role["id"]] for role in config["sampling"]["roles"]}, "unique_rows": len(selections)},
        "stable_transitions": {comparison_id: {transition: sum(int(row["row_count"]) for row in transition_rows if row["comparison_id"] == comparison_id and row["transition"] == transition) for transition in ("stable_recovery", "stable_regression", "higher_correct_rate", "lower_correct_rate", "unchanged_correct_rate")} for comparison_id in ("reference_to_lora", "encoder_to_lora")},
        "test_accessed": False,
    }
    if read_json(output_dir / "aggregate_summary.json") != aggregate_expected:
        raise ValueError("Aggregate summary mismatch")

    attribution = read_json(output_dir / "format_attribution.json")
    if abs(attribution["additive_contribution_check"] - attribution["overall_accuracy_delta"]) > 1e-12:
        raise ValueError("Format attribution does not add to overall accuracy delta")
    failed_rows = sum(row["conditions"]["reference"]["runs"][0]["failed_output"] for row in records)
    if attribution["slices"]["reference_output_failed"]["rows"] != failed_rows:
        raise ValueError("Failed-output attribution count mismatch")

    annotations = read_csv(output_dir / "manual_annotations.csv")
    manifest = read_csv(output_dir / "sample_manifest.csv")
    if len(annotations) != len(manifest):
        raise ValueError("Qualitative row count mismatch")
    allowed_flags = set(config["annotation"]["allowed_evidence_flags"])
    allowed_sources = set(config["annotation"]["allowed_primary_sources"])
    allowed_confidence = set(config["annotation"]["confidence_levels"])
    all_flags: list[str] = []
    for manifest_row, row in zip(manifest, annotations):
        if [row[key] for key in ("sample_rank", "case_id", "role", "gold_label")] != [manifest_row[key] for key in ("sample_rank", "case_id", "role", "gold_label")]:
            raise ValueError("Annotation identity mismatch")
        flags = row["evidence_flags"].split("|") if row["evidence_flags"] else []
        if not flags or len(flags) != len(set(flags)) or not set(flags) <= allowed_flags:
            raise ValueError("Invalid qualitative flags")
        if "none_observed" in flags and len(flags) != 1:
            raise ValueError("none_observed is not exclusive")
        if ("long_tail_class" in flags) != (manifest_row["long_tail"] == "true"):
            raise ValueError("Long-tail coding mismatch")
        if row["primary_possible_source"] not in allowed_sources or row["reviewer_confidence"] not in allowed_confidence:
            raise ValueError("Invalid qualitative category")
        all_flags.extend(flags)
    qualitative_expected = {
        "annotation_count": len(annotations),
        "evidence_flag_counts": dict(sorted(Counter(all_flags).items())),
        "primary_possible_source_counts": dict(sorted(Counter(row["primary_possible_source"] for row in annotations).items())),
        "reviewer_confidence_counts": dict(sorted(Counter(row["reviewer_confidence"] for row in annotations).items())),
        "role_counts": dict(sorted(Counter(row["role"] for row in annotations).items())),
    }
    if read_json(output_dir / "qualitative_summary.json") != qualitative_expected:
        raise ValueError("Qualitative summary mismatch")

    private = verify_private(output_dir, selections)
    run = read_json(output_dir / "run.json")
    if run.get("status") != "CompletedAwaitingVerification" or run.get("test_accessed") or run.get("accessed_splits") != ["validation"]:
        raise ValueError("Run status or split boundary mismatch")
    artifacts_checked = verify_artifacts(run["artifacts"])
    review = read_json(output_dir / "manual_review.json")
    if review.get("status") != "Completed" or review.get("qualitative_summary") != qualitative_expected:
        raise ValueError("Manual review summary mismatch")
    report_path = output_dir / "REPORT.md"
    report = report_path.read_text(encoding="utf-8")
    if "sealed test" not in report or any(row["target"] in report for row in validation if len(row["target"]) >= 8):
        raise ValueError("Report boundary or text leakage failed")

    pending_status = "Status: `Completed; verification pending`"
    if pending_status not in report:
        raise ValueError("Report is not awaiting verification")
    report = report.replace(pending_status, "Status: `Verified`", 1)
    report_path.write_text(report, encoding="utf-8")
    run["status"] = "Verified"
    run["verified_at_utc"] = datetime.now(timezone.utc).isoformat()
    run["artifacts"]["REPORT.md"] = artifact_record(report_path)
    with (output_dir / "run.json").open("w", encoding="utf-8") as handle:
        json.dump(run, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")

    verification = {
        "analysis_rows": len(records),
        "annotation_rows": len(annotations),
        "artifacts_checked": artifacts_checked,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": artifact_record(config_path),
        "experiment_id": config["experiment_id"],
        "independent_implementation": True,
        "max_absolute_numeric_difference": 0.0,
        "prediction_files_checked": sum(len(condition["runs"]) for condition in config["conditions"]),
        "privacy": private,
        "protocol": artifact_record(PROJECT_ROOT / config["protocol"]["path"]),
        "report": artifact_record(report_path),
        "recomputed_csvs": ["run_metrics.csv", "per_class_metrics.csv", "class_gap.csv", "confusion_pairs.csv", "condition_stability.csv", "slice_metrics.csv", "pairwise_transitions.csv", "seed_agreement.csv", "sample_manifest.csv"],
        "recomputed_jsons": ["aggregate_summary.json", "format_attribution.json", "qualitative_summary.json"],
        "run": artifact_record(output_dir / "run.json"),
        "sample_selection_deterministic": True,
        "split": "validation",
        "status": "Verified",
        "test_accessed": False,
        "verifier": artifact_record(Path(__file__).resolve()),
    }
    with verification_path.open("w", encoding="utf-8") as handle:
        json.dump(verification, handle, indent=2, sort_keys=True, ensure_ascii=False); handle.write("\n")
    print(json.dumps({"experiment_id": config["experiment_id"], "prediction_files_checked": verification["prediction_files_checked"], "status": "Verified"}, indent=2))


if __name__ == "__main__":
    main()
