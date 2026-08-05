#!/usr/bin/env python3
"""Independently recompute EXP-037 from frozen inputs and private rater records."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def resolve_config_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.exists() else resolve_project_path(value).resolve()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def artifact_record(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "sha256": sha256_file(path),
    }


def parse_label_ids(value: str) -> list[int]:
    stripped = value.strip()
    return [] if not stripped else [int(item) for item in stripped.split("|")]


def set_f1(left: set[int], right: set[int]) -> float:
    if not left and not right:
        return 1.0
    return 2.0 * len(left & right) / (len(left) + len(right))


def jaccard(left: set[int], right: set[int]) -> float:
    union = left | right
    return 1.0 if not union else len(left & right) / len(union)


def recursively_find_true_test_access(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = key.lower()
            if "test" in normalized and "access" in normalized and nested is True:
                return True
            if recursively_find_true_test_access(nested):
                return True
    if isinstance(value, list):
        return any(recursively_find_true_test_access(item) for item in value)
    return False


def verify_implementation(config: dict[str, Any]) -> None:
    for name, record in config["implementation"].items():
        if sha256_file(resolve_project_path(record["path"])) != record["sha256"]:
            raise RuntimeError(f"Implementation hash changed: {name}")


def load_dev(
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[list[int]]]:
    selection = config["selection"]
    dev_path = resolve_project_path(selection["dev_path"])
    labels_path = resolve_project_path(selection["labels_path"])
    if resolve_project_path(selection["simplified_test_path"]).exists():
        raise RuntimeError("Simplified test.tsv exists")
    if sha256_file(dev_path) != selection["dev_sha256"]:
        raise RuntimeError("Frozen dev hash changed")
    if sha256_file(labels_path) != selection["labels_sha256"]:
        raise RuntimeError("Frozen labels hash changed")
    labels = labels_path.read_text(encoding="utf-8").splitlines()
    if labels != config["labels"] or labels.index("neutral") != 27:
        raise RuntimeError("Frozen label order changed")

    selected: list[dict[str, Any]] = []
    all_gold: list[list[int]] = []
    with dev_path.open("r", encoding="utf-8", newline="") as handle:
        for row_number, row in enumerate(csv.reader(handle, delimiter="\t"), start=1):
            if len(row) != 3:
                raise RuntimeError(f"Malformed dev row {row_number}")
            text, encoded, comment_id = row
            label_ids = [int(value) for value in encoded.split(",")]
            if label_ids != sorted(set(label_ids)):
                raise RuntimeError(f"Invalid dev labels at row {row_number}")
            all_gold.append(label_ids)
            selected.append(
                {
                    "comment_id": comment_id,
                    "example_hash": sha256_text(comment_id),
                    "gold_label_ids": label_ids,
                    "source_dev_row": row_number,
                    "text_sha256": sha256_text(text),
                }
            )
    row_hash = sha256_text(",".join(str(row["source_dev_row"]) for row in selected))
    if (
        len(selected) != selection["expected_rows"]
        or len(all_gold) != selection["dev_rows"]
        or row_hash != selection["source_dev_rows_sha256"]
        or [row["source_dev_row"] for row in selected]
        != list(range(1, selection["expected_rows"] + 1))
    ):
        raise RuntimeError("Frozen full-dev allowlist changed")
    return selected, all_gold


def load_private_records(
    path: Path, selected: list[dict[str, Any]], label_count: int
) -> list[dict[str, Any]]:
    targets = {row["source_dev_row"]: row for row in selected}
    allowed_keys = {
        "example_hash",
        "label_ids",
        "rater_hash",
        "source_dev_row",
        "source_file",
        "source_line",
        "text_sha256",
        "unclear",
    }
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            record = json.loads(line)
            target = targets.get(record.get("source_dev_row"))
            if set(record) != allowed_keys or target is None:
                raise RuntimeError(f"Private schema or row changed at line {line_number}")
            if (
                record["example_hash"] != target["example_hash"]
                or record["text_sha256"] != target["text_sha256"]
                or len(record["rater_hash"]) != 64
                or record["label_ids"] != sorted(set(record["label_ids"]))
                or any(value < 0 or value >= label_count for value in record["label_ids"])
                or not isinstance(record["unclear"], bool)
            ):
                raise RuntimeError(f"Private record integrity mismatch at line {line_number}")
            records.append(record)
    return records


def rebuild_rater_view(
    selected: list[dict[str, Any]],
    records: list[dict[str, Any]],
    label_count: int,
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], dict[str, Any]]:
    by_row: dict[int, list[dict[str, Any]]] = defaultdict(list)
    seen_pairs: set[tuple[str, str]] = set()
    duplicates = 0
    for record in records:
        pair = (record["example_hash"], record["rater_hash"])
        duplicates += int(pair in seen_pairs)
        seen_pairs.add(pair)
        by_row[record["source_dev_row"]].append(record)

    structures: list[dict[str, Any]] = []
    view: dict[int, dict[str, Any]] = {}
    rater_distribution: Counter[int] = Counter()
    clear_distribution: Counter[int] = Counter()
    unclear_examples = 0
    unclear_annotations = 0
    disagreement_examples = 0
    aggregate_not_individual = 0
    aggregation_mismatches = 0
    clear_empty = 0
    for target in selected:
        row_number = target["source_dev_row"]
        rows = by_row.get(row_number, [])
        if not rows:
            raise RuntimeError(f"Missing private annotations for dev row {row_number}")
        vote_counts = [0] * label_count
        for row in rows:
            for label_id in row["label_ids"]:
                vote_counts[label_id] += 1
        derived = [label_id for label_id, count in enumerate(vote_counts) if count >= 2]
        derived_matches = derived == target["gold_label_ids"]
        aggregation_mismatches += int(not derived_matches)

        clear_sets = [set(row["label_ids"]) for row in rows if not row["unclear"]]
        all_labeled_sets = [set(row["label_ids"]) for row in rows if row["label_ids"]]
        clear_empty += sum(int(not row["label_ids"]) for row in rows if not row["unclear"])
        if not clear_sets or any(not label_set for label_set in clear_sets) or not all_labeled_sets:
            raise RuntimeError(f"Invalid rater sets at dev row {row_number}")

        clear_probs = np.zeros(label_count, dtype=np.float64)
        for label_set in clear_sets:
            for label_id in label_set:
                clear_probs[label_id] += 1.0 / len(clear_sets)
        all_probs = np.zeros(label_count, dtype=np.float64)
        for label_set in all_labeled_sets:
            for label_id in label_set:
                all_probs[label_id] += 1.0 / len(all_labeled_sets)

        unique_count = len({tuple(sorted(label_set)) for label_set in clear_sets})
        matches_individual = set(target["gold_label_ids"]) in clear_sets
        unclear_count = sum(int(row["unclear"]) for row in rows)
        disagreement_examples += int(unique_count > 1)
        aggregate_not_individual += int(not matches_individual)
        unclear_examples += int(unclear_count > 0)
        unclear_annotations += unclear_count
        rater_distribution[len(rows)] += 1
        clear_distribution[len(clear_sets)] += 1
        structures.append(
            {
                "source_dev_row": row_number,
                "example_hash": target["example_hash"],
                "gold_label_ids": "|".join(str(value) for value in target["gold_label_ids"]),
                "gold_cardinality": len(target["gold_label_ids"]),
                "rater_count": len(rows),
                "clear_rater_count": len(clear_sets),
                "labeled_rater_count": len(all_labeled_sets),
                "unclear_count": unclear_count,
                "unique_clear_label_set_count": unique_count,
                "clear_rater_disagreement": unique_count > 1,
                "official_target_matches_any_clear_rater": matches_individual,
                "derived_labels_match": derived_matches,
            }
        )
        view[row_number] = {
            "all_labeled_probs": all_probs,
            "all_labeled_sets": all_labeled_sets,
            "clear_probs": clear_probs,
            "clear_sets": clear_sets,
            "gold": set(target["gold_label_ids"]),
        }

    if len(by_row) != len(selected) or duplicates or aggregation_mismatches or clear_empty:
        raise RuntimeError("Rater reconstruction integrity failed")
    summary = {
        "aggregate_target_not_any_clear_rater_rate": aggregate_not_individual / len(selected),
        "aggregate_target_not_any_clear_rater_rows": aggregate_not_individual,
        "any_unclear_rate": unclear_examples / len(selected),
        "any_unclear_rows": unclear_examples,
        "clear_empty_annotations": clear_empty,
        "clear_rater_count_distribution": dict(sorted(clear_distribution.items())),
        "clear_rater_disagreement_rate": disagreement_examples / len(selected),
        "clear_rater_disagreement_rows": disagreement_examples,
        "duplicate_comment_rater_pairs": duplicates,
        "matched_annotation_rows": len(records),
        "official_threshold_reproduction_mismatches": aggregation_mismatches,
        "rater_count_distribution": dict(sorted(rater_distribution.items())),
        "rows": len(selected),
        "unclear_annotation_rows": unclear_annotations,
    }
    return structures, view, summary


def load_predictions(
    config: dict[str, Any], all_gold: list[list[int]]
) -> tuple[dict[str, list[set[int]]], list[dict[str, Any]]]:
    predictions: dict[str, list[set[int]]] = {}
    manifest: list[dict[str, Any]] = []
    for spec in config["predictions"]:
        path = resolve_project_path(spec["path"])
        verification_path = resolve_project_path(spec["verification_path"])
        if sha256_file(path) != spec["sha256"]:
            raise RuntimeError(f"Prediction hash changed: {spec['run_id']}")
        if sha256_file(verification_path) != spec["verification_sha256"]:
            raise RuntimeError(f"Verification hash changed: {spec['run_id']}")
        upstream = read_json(verification_path)
        if upstream.get("status") != spec["verification_status"] or recursively_find_true_test_access(upstream):
            raise RuntimeError(f"Upstream verification invalid: {spec['run_id']}")
        values: list[set[int]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"row_number", "gold_label_ids", "predicted_label_ids"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise RuntimeError(f"Prediction schema changed: {spec['run_id']}")
            for expected_row, row in enumerate(reader, start=1):
                row_number = int(row["row_number"])
                gold = parse_label_ids(row["gold_label_ids"])
                predicted = parse_label_ids(row["predicted_label_ids"])
                if row_number != expected_row or gold != all_gold[row_number - 1]:
                    raise RuntimeError(f"Prediction alignment failed: {spec['run_id']}")
                if predicted != sorted(set(predicted)):
                    raise RuntimeError(f"Prediction labels invalid: {spec['run_id']}")
                values.append(set(predicted))
        if len(values) != config["selection"]["dev_rows"]:
            raise RuntimeError(f"Prediction row count changed: {spec['run_id']}")
        predictions[spec["run_id"]] = values
        manifest.append(
            {
                "condition": spec["condition"],
                "path": spec["path"],
                "rows": len(values),
                "run_id": spec["run_id"],
                "seed": spec["seed"],
                "sha256": spec["sha256"],
                "verification_path": spec["verification_path"],
                "verification_sha256": spec["verification_sha256"],
                "verification_status": spec["verification_status"],
            }
        )
    return predictions, manifest


def score_binary(
    prediction: np.ndarray, target: np.ndarray
) -> tuple[dict[str, float], list[dict[str, float]]]:
    tp = (prediction * target).sum(axis=0)
    prediction_total = prediction.sum(axis=0)
    target_total = target.sum(axis=0)
    fp = prediction_total - tp
    fn = target_total - tp
    precision = np.zeros_like(tp)
    recall = np.zeros_like(tp)
    f1 = np.zeros_like(tp)
    np.divide(tp, prediction_total, out=precision, where=prediction_total > 0)
    np.divide(tp, target_total, out=recall, where=target_total > 0)
    np.divide(2.0 * tp, prediction_total + target_total, out=f1, where=(prediction_total + target_total) > 0)
    denominator = float(prediction_total.sum() + target_total.sum())
    summary = {
        "macro_f1": float(f1.mean()),
        "micro_f1": 0.0 if denominator == 0 else float(2.0 * tp.sum() / denominator),
    }
    details = [
        {
            "target_support": float(target_total[index]),
            "predicted_positive_mass": float(prediction_total[index]),
            "true_positive": float(tp[index]),
            "false_positive": float(fp[index]),
            "false_negative": float(fn[index]),
            "precision": float(precision[index]),
            "recall": float(recall[index]),
            "f1": float(f1[index]),
        }
        for index in range(prediction.shape[1])
    ]
    return summary, details


RUN_SUMMARY_METRICS = [
    "official_macro_f1",
    "official_micro_f1",
    "official_sample_set_f1",
    "official_sample_jaccard",
    "official_subset_accuracy",
    "clear_rater_soft_macro_f1",
    "clear_rater_soft_micro_f1",
    "clear_rater_expected_set_f1",
    "clear_rater_expected_jaccard",
    "clear_rater_expected_exact",
    "any_clear_rater_exact",
    "best_clear_rater_set_f1",
    "all_labeled_rater_soft_macro_f1",
    "all_labeled_rater_soft_micro_f1",
    "all_labeled_rater_expected_set_f1",
    "mean_predicted_cardinality",
]


def independently_score_runs(
    config: dict[str, Any],
    selected: list[dict[str, Any]],
    view: dict[int, dict[str, Any]],
    predictions: dict[str, list[set[int]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, np.ndarray]]]:
    rows = len(selected)
    labels = len(config["labels"])
    gold = np.zeros((rows, labels), dtype=np.float64)
    clear = np.zeros((rows, labels), dtype=np.float64)
    all_labeled = np.zeros((rows, labels), dtype=np.float64)
    for index, target in enumerate(selected):
        gold[index, target["gold_label_ids"]] = 1.0
        clear[index] = view[target["source_dev_row"]]["clear_probs"]
        all_labeled[index] = view[target["source_dev_row"]]["all_labeled_probs"]

    metrics: list[dict[str, Any]] = []
    per_label: list[dict[str, Any]] = []
    arrays: dict[str, dict[str, np.ndarray]] = {}
    for spec in config["predictions"]:
        run_id = spec["run_id"]
        predicted_sets = predictions[run_id]
        matrix = np.zeros((rows, labels), dtype=np.float64)
        official_set = np.zeros(rows)
        official_jaccard = np.zeros(rows)
        official_exact = np.zeros(rows)
        clear_set = np.zeros(rows)
        clear_jaccard = np.zeros(rows)
        clear_exact = np.zeros(rows)
        any_exact = np.zeros(rows)
        best_set = np.zeros(rows)
        all_set = np.zeros(rows)
        for index, target in enumerate(selected):
            prediction = predicted_sets[index]
            matrix[index, list(prediction)] = 1.0
            rater = view[target["source_dev_row"]]
            official_set[index] = set_f1(prediction, rater["gold"])
            official_jaccard[index] = jaccard(prediction, rater["gold"])
            official_exact[index] = float(prediction == rater["gold"])
            clear_set[index] = sum(set_f1(prediction, item) for item in rater["clear_sets"]) / len(rater["clear_sets"])
            clear_jaccard[index] = sum(jaccard(prediction, item) for item in rater["clear_sets"]) / len(rater["clear_sets"])
            clear_exact[index] = sum(float(prediction == item) for item in rater["clear_sets"]) / len(rater["clear_sets"])
            any_exact[index] = float(any(prediction == item for item in rater["clear_sets"]))
            best_set[index] = max(set_f1(prediction, item) for item in rater["clear_sets"])
            all_set[index] = sum(set_f1(prediction, item) for item in rater["all_labeled_sets"]) / len(rater["all_labeled_sets"])

        official_summary, official_details = score_binary(matrix, gold)
        clear_summary, clear_details = score_binary(matrix, clear)
        all_summary, all_details = score_binary(matrix, all_labeled)
        metrics.append(
            {
                "condition": spec["condition"],
                "run_id": run_id,
                "seed": spec["seed"],
                "rows": rows,
                "empty_prediction_count": sum(int(not value) for value in predicted_sets),
                "official_macro_f1": official_summary["macro_f1"],
                "official_micro_f1": official_summary["micro_f1"],
                "official_sample_set_f1": float(official_set.mean()),
                "official_sample_jaccard": float(official_jaccard.mean()),
                "official_subset_accuracy": float(official_exact.mean()),
                "clear_rater_soft_macro_f1": clear_summary["macro_f1"],
                "clear_rater_soft_micro_f1": clear_summary["micro_f1"],
                "clear_rater_expected_set_f1": float(clear_set.mean()),
                "clear_rater_expected_jaccard": float(clear_jaccard.mean()),
                "clear_rater_expected_exact": float(clear_exact.mean()),
                "any_clear_rater_exact": float(any_exact.mean()),
                "best_clear_rater_set_f1": float(best_set.mean()),
                "all_labeled_rater_soft_macro_f1": all_summary["macro_f1"],
                "all_labeled_rater_soft_micro_f1": all_summary["micro_f1"],
                "all_labeled_rater_expected_set_f1": float(all_set.mean()),
                "mean_predicted_cardinality": sum(len(value) for value in predicted_sets) / rows,
            }
        )
        for target_type, details in (
            ("official_hard", official_details),
            ("clear_rater_soft", clear_details),
            ("all_labeled_rater_soft", all_details),
        ):
            for label_id, detail in enumerate(details):
                per_label.append(
                    {
                        "condition": spec["condition"],
                        "run_id": run_id,
                        "seed": spec["seed"],
                        "target_type": target_type,
                        "label_id": label_id,
                        "label": config["labels"][label_id],
                        **detail,
                    }
                )
        arrays[run_id] = {
            "official_sample_set_f1": official_set,
            "clear_rater_expected_set_f1": clear_set,
            "prediction": matrix,
        }
    arrays["__targets__"] = {"gold": gold, "clear": clear}
    return metrics, per_label, arrays


def summarize_families(run_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in run_metrics:
        grouped[row["condition"]].append(row)
    summaries: list[dict[str, Any]] = []
    for condition in sorted(grouped):
        rows = grouped[condition]
        summary: dict[str, Any] = {
            "condition": condition,
            "run_count": len(rows),
            "seeds": "|".join(str(row["seed"]) for row in sorted(rows, key=lambda value: value["seed"])),
        }
        for metric in RUN_SUMMARY_METRICS:
            values = [float(row[metric]) for row in rows]
            summary[f"{metric}_mean"] = statistics.mean(values)
            summary[f"{metric}_std"] = statistics.stdev(values) if len(values) > 1 else None
        summaries.append(summary)
    return summaries


def operand_run_ids(operand: dict[str, Any], config: dict[str, Any]) -> list[str]:
    specs = sorted(
        (
            spec
            for spec in config["predictions"]
            if spec["condition"] == operand["condition"] and spec["seed"] in operand["seeds"]
        ),
        key=lambda spec: spec["seed"],
    )
    if len(specs) != len(operand["seeds"]):
        raise RuntimeError("Incomplete comparison operand")
    return [spec["run_id"] for spec in specs]


def derived_seed(base: int, comparison_id: str, kind: str) -> int:
    return int(sha256_text(f"{base}:{comparison_id}:{kind}")[:16], 16)


def ci(values: np.ndarray) -> tuple[float, float]:
    result = np.quantile(values, [0.025, 0.975], method="linear")
    return float(result[0]), float(result[1])


def sample_bootstrap(
    official: np.ndarray, rater: np.ndarray, iterations: int, seed: int
) -> dict[str, tuple[float, float]]:
    generator = np.random.default_rng(seed)
    count = len(official)
    official_samples = np.empty(iterations)
    rater_samples = np.empty(iterations)
    for start in range(0, iterations, 100):
        size = min(100, iterations - start)
        indexes = generator.integers(0, count, size=(size, count))
        official_samples[start : start + size] = official[indexes].mean(axis=1)
        rater_samples[start : start + size] = rater[indexes].mean(axis=1)
    return {
        "official": ci(official_samples),
        "rater": ci(rater_samples),
        "shift": ci(rater_samples - official_samples),
    }


def bootstrap_macro(
    candidate: np.ndarray,
    reference: np.ndarray,
    gold: np.ndarray,
    clear: np.ndarray,
    iterations: int,
    seed: int,
) -> dict[str, tuple[float, float]]:
    generator = np.random.default_rng(seed)
    count = len(gold)
    split = len(candidate)
    prediction = np.concatenate((candidate, reference), axis=0)
    official_product = prediction * gold[None, :, :]
    clear_product = prediction * clear[None, :, :]
    official_deltas = np.empty(iterations)
    soft_deltas = np.empty(iterations)
    for start in range(0, iterations, 20):
        size = min(20, iterations - start)
        indexes = generator.integers(0, count, size=(size, count))
        weights = np.stack([np.bincount(index, minlength=count) for index in indexes]).astype(float)
        prediction_mass = np.einsum("bn,rnl->brl", weights, prediction, optimize=True)
        official_mass = weights @ gold
        clear_mass = weights @ clear
        official_tp = np.einsum("bn,rnl->brl", weights, official_product, optimize=True)
        clear_tp = np.einsum("bn,rnl->brl", weights, clear_product, optimize=True)
        official_f1 = np.divide(
            2.0 * official_tp,
            prediction_mass + official_mass[:, None, :],
            out=np.zeros_like(official_tp),
            where=(prediction_mass + official_mass[:, None, :]) != 0,
        ).mean(axis=2)
        clear_f1 = np.divide(
            2.0 * clear_tp,
            prediction_mass + clear_mass[:, None, :],
            out=np.zeros_like(clear_tp),
            where=(prediction_mass + clear_mass[:, None, :]) != 0,
        ).mean(axis=2)
        official_deltas[start : start + size] = official_f1[:, :split].mean(axis=1) - official_f1[:, split:].mean(axis=1)
        soft_deltas[start : start + size] = clear_f1[:, :split].mean(axis=1) - clear_f1[:, split:].mean(axis=1)
    return {
        "official": ci(official_deltas),
        "soft": ci(soft_deltas),
        "shift": ci(soft_deltas - official_deltas),
    }


def independently_compare(
    config: dict[str, Any],
    run_metrics: list[dict[str, Any]],
    arrays: dict[str, dict[str, np.ndarray]],
) -> list[dict[str, Any]]:
    by_run = {row["run_id"]: row for row in run_metrics}
    gold = arrays["__targets__"]["gold"]
    clear = arrays["__targets__"]["clear"]
    base = config["statistics"]["bootstrap_seed"]
    tie = config["statistics"]["practical_tie_threshold"]
    material = config["statistics"]["material_shift_threshold"]
    sample_iterations = config["statistics"]["sample_bootstrap_iterations"]
    macro_iterations = config["statistics"]["macro_bootstrap_iterations"]
    comparisons: list[dict[str, Any]] = []
    for spec in config["comparisons"]:
        candidate_ids = operand_run_ids(spec["candidate"], config)
        reference_ids = operand_run_ids(spec["reference"], config)
        candidate_official = np.stack([arrays[value]["official_sample_set_f1"] for value in candidate_ids]).mean(axis=0)
        reference_official = np.stack([arrays[value]["official_sample_set_f1"] for value in reference_ids]).mean(axis=0)
        candidate_rater = np.stack([arrays[value]["clear_rater_expected_set_f1"] for value in candidate_ids]).mean(axis=0)
        reference_rater = np.stack([arrays[value]["clear_rater_expected_set_f1"] for value in reference_ids]).mean(axis=0)
        official_sample_delta = candidate_official - reference_official
        rater_delta = candidate_rater - reference_rater
        sample_seed = derived_seed(base, spec["comparison_id"], "sample")
        sample_cis = sample_bootstrap(official_sample_delta, rater_delta, sample_iterations, sample_seed)
        macro_seed = derived_seed(base, spec["comparison_id"], "macro")
        macro_cis = bootstrap_macro(
            np.stack([arrays[value]["prediction"] for value in candidate_ids]),
            np.stack([arrays[value]["prediction"] for value in reference_ids]),
            gold,
            clear,
            macro_iterations,
            macro_seed,
        )
        official_macro_delta = statistics.mean(by_run[value]["official_macro_f1"] for value in candidate_ids) - statistics.mean(by_run[value]["official_macro_f1"] for value in reference_ids)
        soft_macro_delta = statistics.mean(by_run[value]["clear_rater_soft_macro_f1"] for value in candidate_ids) - statistics.mean(by_run[value]["clear_rater_soft_macro_f1"] for value in reference_ids)
        shift = soft_macro_delta - official_macro_delta
        if soft_macro_delta <= -tie and macro_cis["soft"][1] < 0:
            decision = "gap_remains"
        elif soft_macro_delta >= tie and macro_cis["soft"][0] > 0:
            decision = "candidate_advantage"
        else:
            decision = "practical_tie_or_uncertain"
        zero = np.isclose(rater_delta, 0.0, rtol=0.0, atol=1e-15)
        comparisons.append(
            {
                "comparison_id": spec["comparison_id"],
                "candidate": spec["candidate"]["label"],
                "reference": spec["reference"]["label"],
                "rows": len(gold),
                "macro_bootstrap_iterations": macro_iterations,
                "macro_bootstrap_seed": macro_seed,
                "official_macro_f1_delta": official_macro_delta,
                "official_macro_f1_delta_ci_low": macro_cis["official"][0],
                "official_macro_f1_delta_ci_high": macro_cis["official"][1],
                "clear_rater_soft_macro_f1_delta": soft_macro_delta,
                "clear_rater_soft_macro_f1_delta_ci_low": macro_cis["soft"][0],
                "clear_rater_soft_macro_f1_delta_ci_high": macro_cis["soft"][1],
                "soft_vs_official_macro_shift": shift,
                "soft_vs_official_macro_shift_ci_low": macro_cis["shift"][0],
                "soft_vs_official_macro_shift_ci_high": macro_cis["shift"][1],
                "sample_bootstrap_iterations": sample_iterations,
                "sample_bootstrap_seed": sample_seed,
                "official_sample_set_f1_delta": float(official_sample_delta.mean()),
                "official_sample_set_f1_delta_ci_low": sample_cis["official"][0],
                "official_sample_set_f1_delta_ci_high": sample_cis["official"][1],
                "clear_rater_expected_set_f1_delta": float(rater_delta.mean()),
                "clear_rater_expected_set_f1_delta_ci_low": sample_cis["rater"][0],
                "clear_rater_expected_set_f1_delta_ci_high": sample_cis["rater"][1],
                "rater_vs_official_sample_shift": float((rater_delta - official_sample_delta).mean()),
                "rater_vs_official_sample_shift_ci_low": sample_cis["shift"][0],
                "rater_vs_official_sample_shift_ci_high": sample_cis["shift"][1],
                "rater_example_wins": int(np.sum((rater_delta > 0) & ~zero)),
                "rater_example_ties": int(np.sum(zero)),
                "rater_example_losses": int(np.sum((rater_delta < 0) & ~zero)),
                "aggregation_materially_shifts_macro_comparison": shift >= material and macro_cis["shift"][0] > 0,
                "decision": decision,
            }
        )
    return comparisons


ROW_FIELDS = [
    "source_dev_row", "example_hash", "gold_label_ids", "gold_cardinality", "rater_count",
    "clear_rater_count", "labeled_rater_count", "unclear_count", "unique_clear_label_set_count",
    "clear_rater_disagreement", "official_target_matches_any_clear_rater", "derived_labels_match",
]
RUN_FIELDS = ["condition", "run_id", "seed", "rows", "empty_prediction_count", *RUN_SUMMARY_METRICS]
FAMILY_FIELDS = ["condition", "run_count", "seeds"] + [field for metric in RUN_SUMMARY_METRICS for field in (f"{metric}_mean", f"{metric}_std")]
PER_LABEL_FIELDS = [
    "condition", "run_id", "seed", "target_type", "label_id", "label", "target_support",
    "predicted_positive_mass", "true_positive", "false_positive", "false_negative", "precision",
    "recall", "f1",
]
COMPARISON_FIELDS = [
    "comparison_id", "candidate", "reference", "rows", "macro_bootstrap_iterations",
    "macro_bootstrap_seed", "official_macro_f1_delta", "official_macro_f1_delta_ci_low",
    "official_macro_f1_delta_ci_high", "clear_rater_soft_macro_f1_delta",
    "clear_rater_soft_macro_f1_delta_ci_low", "clear_rater_soft_macro_f1_delta_ci_high",
    "soft_vs_official_macro_shift", "soft_vs_official_macro_shift_ci_low",
    "soft_vs_official_macro_shift_ci_high", "sample_bootstrap_iterations", "sample_bootstrap_seed",
    "official_sample_set_f1_delta", "official_sample_set_f1_delta_ci_low",
    "official_sample_set_f1_delta_ci_high", "clear_rater_expected_set_f1_delta",
    "clear_rater_expected_set_f1_delta_ci_low", "clear_rater_expected_set_f1_delta_ci_high",
    "rater_vs_official_sample_shift", "rater_vs_official_sample_shift_ci_low",
    "rater_vs_official_sample_shift_ci_high", "rater_example_wins", "rater_example_ties",
    "rater_example_losses", "aggregation_materially_shifts_macro_comparison", "decision",
]


def scalar_matches(observed: str, expected: Any, tolerance: float = 5e-11) -> tuple[bool, float]:
    if isinstance(expected, float):
        try:
            difference = abs(float(observed) - expected)
        except ValueError:
            return False, float("inf")
        return difference <= tolerance, difference
    if expected is None:
        return observed == "", 0.0
    if isinstance(expected, bool):
        return observed == str(expected).lower(), 0.0
    return observed == str(expected), 0.0


def verify_csv(
    path: Path, rows: list[dict[str, Any]], fieldnames: list[str]
) -> tuple[int, float]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        observed = list(reader)
        if reader.fieldnames != fieldnames or len(observed) != len(rows):
            raise RuntimeError(f"CSV shape differs: {path.name}")
    maximum = 0.0
    for row_number, (actual, expected) in enumerate(zip(observed, rows), start=2):
        for field in fieldnames:
            matches, difference = scalar_matches(actual[field], expected.get(field))
            maximum = max(maximum, difference)
            if not matches:
                raise RuntimeError(f"CSV content differs: {path.name} row {row_number} field {field}")
    return len(observed), maximum


def compare_nested(observed: Any, expected: Any, path: str = "$") -> float:
    if isinstance(expected, bool) or expected is None or isinstance(expected, str) or isinstance(expected, int):
        if observed != expected:
            raise RuntimeError(f"JSON differs at {path}")
        return 0.0
    if isinstance(expected, float):
        difference = abs(float(observed) - expected)
        if difference > 1e-12:
            raise RuntimeError(f"JSON numeric difference at {path}: {difference}")
        return difference
    if isinstance(expected, list):
        if not isinstance(observed, list) or len(observed) != len(expected):
            raise RuntimeError(f"JSON list differs at {path}")
        return max((compare_nested(left, right, f"{path}[{index}]") for index, (left, right) in enumerate(zip(observed, expected))), default=0.0)
    if isinstance(expected, dict):
        if not isinstance(observed, dict) or set(observed) != set(expected):
            raise RuntimeError(f"JSON object differs at {path}")
        return max((compare_nested(observed[key], expected[key], f"{path}.{key}") for key in expected), default=0.0)
    raise TypeError(f"Unsupported JSON value at {path}")


def render_report(structure: dict[str, Any], families: list[dict[str, Any]], comparisons: list[dict[str, Any]]) -> str:
    family_lines = [
        "| Condition | Runs | Official Macro-F1 | Clear-rater soft Macro-F1 | Expected rater set-F1 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in families:
        family_lines.append("| {condition} | {runs} | {official:.6f} | {soft:.6f} | {expected:.6f} |".format(
            condition=row["condition"], runs=row["run_count"], official=row["official_macro_f1_mean"],
            soft=row["clear_rater_soft_macro_f1_mean"], expected=row["clear_rater_expected_set_f1_mean"],
        ))
    comparison_lines = [
        "| Comparison (candidate - reference) | Official Macro delta | Soft Macro delta | Macro shift | Decision |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in comparisons:
        comparison_lines.append("| {comparison} | {official:+.6f} | {soft:+.6f} | {shift:+.6f} | {decision} |".format(
            comparison=row["comparison_id"], official=row["official_macro_f1_delta"],
            soft=row["clear_rater_soft_macro_f1_delta"], shift=row["soft_vs_official_macro_shift"],
            decision=row["decision"],
        ))
    primary = comparisons[0]
    return "\n".join([
        "# EXP-037: Full-dev Rater-aware Frozen-prediction Diagnostic", "", "## Boundary", "",
        "This validation-only diagnostic rescored seven frozen prediction files on all 5,426",
        "official GoEmotions dev rows. It performed no training, model inference, checkpoint",
        "selection, threshold change, or test access.", "", "## Annotation Integrity", "",
        f"- Rows joined and reproduced: {structure['rows']}; official aggregation mismatches: {structure['official_threshold_reproduction_mismatches']}.",
        f"- Matched per-rater annotations: {structure['matched_annotation_rows']}.",
        f"- Rows with disagreement among clear raters: {structure['clear_rater_disagreement_rows']} ({structure['clear_rater_disagreement_rate']:.6f}).",
        f"- Official targets matching no clear individual rater: {structure['aggregate_target_not_any_clear_rater_rows']} ({structure['aggregate_target_not_any_clear_rater_rate']:.6f}).",
        f"- Rows with unclear annotations: {structure['any_unclear_rows']} ({structure['any_unclear_rate']:.6f}).",
        "", "## Frozen Predictions", "", *family_lines, "",
        "Soft Macro-F1 uses each clear annotator's vote fraction as the label target. Expected",
        "rater set-F1 instead averages set agreement against one clear annotator at a time.",
        "Neither diagnostic is replacement truth; official dev metrics remain the benchmark.",
        "", "## Paired Comparisons", "", *comparison_lines, "",
        f"Primary classification: `{primary['decision']}`. Annotation-aware soft scoring",
        f"materially shifts the primary Macro-F1 comparison under the frozen rule: `{str(primary['aggregation_materially_shifts_macro_comparison']).lower()}`.",
        "", "## Limits", "", "- Annotator votes measure observed agreement, not latent human emotion.",
        "- Original raters saw isolated comments, so missing conversational context remains.",
        "- Bootstrap intervals resample dev examples, not training seeds.",
        "- Soft-label rescoring does not change the official benchmark target or model outputs.",
        "- The result is behavioral evidence and does not identify an internal mechanism.", "",
        "Status: completed, pending independent artifact verification.", "",
    ])


def verify_source_manifest(
    path: Path,
    config: dict[str, Any],
    records: list[dict[str, Any]],
    prediction_manifest: list[dict[str, Any]],
) -> dict[str, Any]:
    matched = Counter(record["source_file"] for record in records)
    expected = {
        "full_archive_transport": True,
        "nonmatching_raw_records_persisted": 0,
        "official_repository_revision": config["official_source"]["revision"],
        "prediction_files": prediction_manifest,
        "retained_annotation_rows": len(records),
        "retained_dev_rows": config["selection"]["expected_rows"],
        "simplified_test_accessed": False,
        "simplified_test_exists": False,
        "sources": [
            {
                "bytes": source["content_length"],
                "etag": source["etag"],
                "last_modified": source["last_modified"],
                "matched_annotation_rows": matched[source["name"]],
                "md5_base64": source["md5_base64"],
                "name": source["name"],
                "raw_annotation_rows": source["raw_annotation_rows"],
                "sha256": source["sha256"],
                "url": source["url"],
            }
            for source in config["raw_sources"]
        ],
    }
    compare_nested(read_json(path), expected)
    return expected


def verify_privacy(run_dir: Path, selected: list[dict[str, Any]]) -> dict[str, Any]:
    public_names = [
        "REPORT.md", "aggregate-summary.json", "family-summary.csv", "pairwise-comparisons.csv",
        "per-label-metrics.csv", "row-structure.csv", "run-metrics.csv", "source-manifest.json",
        "stdout.log",
    ]
    contents = "\n".join((run_dir / name).read_text(encoding="utf-8") for name in public_names)
    leaked = sum(int(row["comment_id"] in contents) for row in selected)
    if leaked or '"text"' in contents or '"rater_id"' in contents:
        raise RuntimeError("Private raw field leaked into public artifacts")
    return {
        "public_raw_text_fields": 0,
        "public_upstream_comment_id_matches": leaked,
        "raw_rater_ids_persisted": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    config_path = resolve_config_path(args.config)
    if sha256_file(config_path) != args.config_sha256:
        raise RuntimeError("Config SHA-256 does not match frozen command")
    config = read_json(config_path)
    if config["experiment_id"] != "EXP-037":
        raise RuntimeError("Unexpected experiment identity")
    verify_implementation(config)
    run_dir = resolve_project_path(config["outputs"]["run_dir"])
    verification_path = run_dir / "verification.json"

    selected, all_gold = load_dev(config)
    records = load_private_records(
        run_dir / "private" / "matched-annotations.private.jsonl",
        selected,
        len(config["labels"]),
    )
    structures, view, structure_summary = rebuild_rater_view(selected, records, len(config["labels"]))
    predictions, prediction_manifest = load_predictions(config, all_gold)
    run_metrics, per_label, arrays = independently_score_runs(config, selected, view, predictions)
    families = summarize_families(run_metrics)
    comparisons = independently_compare(config, run_metrics, arrays)

    checks: dict[str, int] = {}
    differences: list[float] = []
    for name, expected, fields in (
        ("row_structure", structures, ROW_FIELDS),
        ("run_metrics", run_metrics, RUN_FIELDS),
        ("family_summary", families, FAMILY_FIELDS),
        ("per_label_metrics", per_label, PER_LABEL_FIELDS),
        ("pairwise_comparisons", comparisons, COMPARISON_FIELDS),
    ):
        rows, difference = verify_csv(run_dir / f"{name.replace('_', '-')}.csv", expected, fields)
        checks[name] = rows
        differences.append(difference)

    aggregate = {
        "comparisons": comparisons,
        "family_summary": families,
        "metric_semantics": {
            "primary_diagnostic": "clear-rater vote-fraction soft-label Macro-F1",
            "secondary_diagnostic": "example-weighted expected set-F1 against a clear individual rater",
            "replacement_ground_truth": False,
            "selection_use_authorized": False,
        },
        "run_metrics": run_metrics,
        "structure": structure_summary,
        "test_accessed": False,
        "test_exists": False,
    }
    stored_aggregate = read_json(run_dir / "aggregate-summary.json")
    differences.append(compare_nested(stored_aggregate, aggregate))
    if (run_dir / "REPORT.md").read_text(encoding="utf-8") != render_report(structure_summary, families, comparisons):
        raise RuntimeError("REPORT.md does not regenerate exactly")
    source_manifest = verify_source_manifest(
        run_dir / "source-manifest.json", config, records, prediction_manifest
    )
    privacy = verify_privacy(run_dir, selected)

    run = read_json(run_dir / "run.json")
    if (
        run["status"] != "CompletedAwaitingVerification"
        or run["accessed_splits"] != ["validation"]
        or run["training_performed"]
        or run["model_inference_performed"]
        or run["test_accessed"]
        or run["test_exists"]
        or run["config"] != artifact_record(config_path)
    ):
        raise RuntimeError("run.json discipline differs")
    differences.append(compare_nested(run["result_summary"], stored_aggregate))
    for record in run["artifacts"]:
        if artifact_record(resolve_project_path(record["path"])) != record:
            raise RuntimeError(f"Artifact identity differs: {record['path']}")

    existing = read_json(verification_path) if args.check else None
    verified_at = existing["verified_at_utc"] if existing else datetime.now(timezone.utc).isoformat()
    verification = {
        "artifacts_checked": len(run["artifacts"]),
        "bootstrap_comparisons_recomputed": len(comparisons),
        "config": artifact_record(config_path),
        "csv_rows_recomputed": checks,
        "experiment_id": config["experiment_id"],
        "implementation_files_checked": len(config["implementation"]),
        "matched_annotation_rows_recomputed": len(records),
        "max_absolute_numeric_difference": max(differences, default=0.0),
        "prediction_files_recomputed": len(predictions),
        "privacy": privacy,
        "report_regenerated_exactly": True,
        "source_objects_checked": len(source_manifest["sources"]),
        "status": "Verified",
        "test_accessed": False,
        "test_absent": not resolve_project_path(config["selection"]["simplified_test_path"]).exists(),
        "verified_at_utc": verified_at,
        "verifier": artifact_record(Path(__file__).resolve()),
    }
    if args.check:
        if existing != verification:
            raise RuntimeError("Stored verification differs from independent recomputation")
    else:
        write_json(verification_path, verification)
    print(json.dumps({"experiment_id": config["experiment_id"], "status": "Verified"}, sort_keys=True))


if __name__ == "__main__":
    main()
