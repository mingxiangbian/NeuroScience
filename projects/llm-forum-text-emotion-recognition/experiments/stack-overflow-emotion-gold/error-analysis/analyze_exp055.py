#!/usr/bin/env python3
"""Prepare the frozen EXP-055 quantitative analysis and qualitative review deck."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[5]
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
SURPRISE_INDEX = 2
CONDITIONS = ("fixed_0.5", "shared_threshold")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def assert_record(record: dict[str, Any]) -> Path:
    path = resolve(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]):
        raise ValueError(f"Byte-size drift: {path}")
    if sha256_file(path) != record["sha256"]:
        raise ValueError(f"SHA-256 drift: {path}")
    return path


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any, *, private: bool = False) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if private:
        os.chmod(path, 0o600)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]], *, private: bool = False) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    if private:
        os.chmod(path, 0o600)


def write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def safe_div(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def metric_bundle(gold: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    gold = gold.astype(np.uint8, copy=False)
    predicted = predicted.astype(np.uint8, copy=False)
    tp = np.sum((gold == 1) & (predicted == 1), axis=0, dtype=np.int64)
    fp = np.sum((gold == 0) & (predicted == 1), axis=0, dtype=np.int64)
    fn = np.sum((gold == 1) & (predicted == 0), axis=0, dtype=np.int64)
    tn = np.sum((gold == 0) & (predicted == 0), axis=0, dtype=np.int64)
    support = np.sum(gold, axis=0, dtype=np.int64)
    precision = np.asarray([safe_div(a, a + b) for a, b in zip(tp, fp)])
    recall = np.asarray([safe_div(a, a + b) for a, b in zip(tp, fn)])
    f1 = np.asarray([safe_div(2 * p * r, p + r) for p, r in zip(precision, recall)])
    micro_tp, micro_fp, micro_fn = int(tp.sum()), int(fp.sum()), int(fn.sum())
    micro_precision = safe_div(micro_tp, micro_tp + micro_fp)
    micro_recall = safe_div(micro_tp, micro_tp + micro_fn)
    intersections = np.sum((gold == 1) & (predicted == 1), axis=1)
    sample_denominator = np.sum(gold, axis=1) + np.sum(predicted, axis=1)
    sample_f1 = np.divide(
        2.0 * intersections,
        sample_denominator,
        out=np.zeros_like(sample_denominator, dtype=np.float64),
        where=sample_denominator != 0,
    )
    without_surprise = [index for index in range(len(LABELS)) if index != SURPRISE_INDEX]
    return {
        "macro_f1": float(f1.mean()),
        "macro_precision": float(precision.mean()),
        "macro_recall": float(recall.mean()),
        "micro_f1": safe_div(2 * micro_precision * micro_recall, micro_precision + micro_recall),
        "weighted_f1": safe_div(float(np.sum(f1 * support)), float(np.sum(support))),
        "subset_accuracy": float(np.mean(np.all(gold == predicted, axis=1))),
        "samples_f1_zero_division_0": float(np.mean(sample_f1)),
        "hamming_loss": float(np.mean(gold != predicted)),
        "five_label_macro_f1_without_surprise": float(f1[without_surprise].mean()),
        "per_label": {
            label: {
                "tp": int(tp[index]),
                "fp": int(fp[index]),
                "fn": int(fn[index]),
                "tn": int(tn[index]),
                "support": int(support[index]),
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
            }
            for index, label in enumerate(LABELS)
        },
    }


def fast_macro_f1(gold: np.ndarray, predicted: np.ndarray, indices: Sequence[int]) -> float:
    tp = np.sum((gold[:, indices] == 1) & (predicted[:, indices] == 1), axis=0)
    fp = np.sum((gold[:, indices] == 0) & (predicted[:, indices] == 1), axis=0)
    fn = np.sum((gold[:, indices] == 1) & (predicted[:, indices] == 0), axis=0)
    denominator = 2 * tp + fp + fn
    f1 = np.divide(2 * tp, denominator, out=np.zeros_like(tp, dtype=float), where=denominator != 0)
    return float(np.mean(f1))


def mean_std(values: Sequence[float]) -> dict[str, Any]:
    return {
        "values": [float(value) for value in values],
        "mean": float(statistics.fmean(values)),
        "sample_std": float(statistics.stdev(values)),
    }


def case_id(sample_id: str) -> str:
    digest = hashlib.sha256(f"EXP-055:{sample_id}".encode("utf-8")).hexdigest()
    return f"case-{digest[:16]}"


def label_names(vector: np.ndarray) -> str:
    selected = [label for label, present in zip(LABELS, vector) if int(present)]
    return ";".join(selected) if selected else "neutral"


def gold_stratum(vector: np.ndarray) -> str:
    return label_names(vector)


def deterministic_rank(role: str, sample_id: str) -> str:
    value = f"20260815:EXP-055:{role}:{sample_id}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def component_bootstrap(
    gold: np.ndarray,
    m1: np.ndarray,
    oracle: np.ndarray,
    component_ids: Sequence[str],
    seed: int,
    condition: str,
    replicates: int,
) -> dict[str, Any]:
    groups: dict[str, list[int]] = defaultdict(list)
    for index, component_id in enumerate(component_ids):
        groups[str(component_id)].append(index)
    group_names = sorted(groups)
    entropy = hashlib.sha256(f"EXP-055:{condition}:{seed}".encode("ascii")).digest()
    rng = np.random.default_rng(int.from_bytes(entropy[:8], "big"))
    all_indices = list(range(len(LABELS)))
    five_indices = [index for index in all_indices if index != SURPRISE_INDEX]
    six_values = np.empty(replicates, dtype=float)
    five_values = np.empty(replicates, dtype=float)
    for replicate in range(replicates):
        sampled = rng.integers(0, len(group_names), size=len(group_names))
        row_indices = np.asarray(
            [row for group_index in sampled for row in groups[group_names[int(group_index)]]],
            dtype=np.int64,
        )
        six_values[replicate] = fast_macro_f1(gold[row_indices], oracle[row_indices], all_indices) - fast_macro_f1(
            gold[row_indices], m1[row_indices], all_indices
        )
        five_values[replicate] = fast_macro_f1(gold[row_indices], oracle[row_indices], five_indices) - fast_macro_f1(
            gold[row_indices], m1[row_indices], five_indices
        )
    return {
        "replicates": replicates,
        "six_label_delta_ci95": [float(np.quantile(six_values, 0.025)), float(np.quantile(six_values, 0.975))],
        "five_label_delta_ci95": [float(np.quantile(five_values, 0.025)), float(np.quantile(five_values, 0.975))],
    }


def load_source(config: dict[str, Any], family: str, seed: int) -> dict[str, Any]:
    record = next(item for item in config["sources"][family] if int(item["seed"]) == seed)
    prediction_path = assert_record(record["predictions"])
    verification_path = assert_record(record["verification"])
    verification = load_json(verification_path)
    if verification.get("status") != "Passed" or verification.get("test_split_accessed") is not False:
        raise ValueError(f"Unverified or test-accessed source: {family} seed {seed}")
    data = np.load(prediction_path, allow_pickle=False)
    required = {
        "probabilities",
        "gold",
        "fixed_predictions",
        "shared_threshold_predictions",
        "sample_ids",
        "component_ids",
    }
    if set(data.files) != required:
        raise ValueError(f"Unexpected NPZ schema for {family} seed {seed}: {data.files}")
    probabilities = np.asarray(data["probabilities"], dtype=np.float32)
    selected_epoch = int(record["selected_epoch"])
    if probabilities.ndim != 3 or probabilities.shape[1:] != (720, len(LABELS)):
        raise ValueError(f"Probability shape drift for {family} seed {seed}: {probabilities.shape}")
    selected = probabilities[selected_epoch - 1]
    fixed = (selected >= 0.5).astype(np.uint8)
    shared = (selected >= float(record["shared_threshold"])).astype(np.uint8)
    if not np.array_equal(fixed, data["fixed_predictions"]):
        raise ValueError(f"Fixed prediction drift for {family} seed {seed}")
    if not np.array_equal(shared, data["shared_threshold_predictions"]):
        raise ValueError(f"Shared prediction drift for {family} seed {seed}")
    return {
        "record": record,
        "probabilities": selected,
        "gold": np.asarray(data["gold"], dtype=np.uint8),
        "sample_ids": np.asarray(data["sample_ids"]).astype(str),
        "component_ids": np.asarray(data["component_ids"]).astype(str),
        "fixed_0.5": fixed,
        "shared_threshold": shared,
    }


def select_role(
    role: str,
    candidates: Sequence[int],
    quota: int,
    sample_ids: Sequence[str],
    gold: np.ndarray,
    used: set[int],
) -> list[int]:
    ordered = sorted((index for index in candidates if index not in used), key=lambda index: deterministic_rank(role, sample_ids[index]))
    selected: list[int] = []
    stratum_counts: Counter[str] = Counter()
    for index in ordered:
        stratum = gold_stratum(gold[index])
        if stratum_counts[stratum] >= 2:
            continue
        selected.append(index)
        stratum_counts[stratum] += 1
        if len(selected) == quota:
            return selected
    for index in ordered:
        if index in selected:
            continue
        selected.append(index)
        if len(selected) == quota:
            break
    return selected


def slice_row(name: str, mask: np.ndarray, gold: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    subset_gold = gold[mask]
    subset_predicted = predicted[mask]
    if len(subset_gold) == 0:
        raise ValueError(f"Empty registered slice: {name}")
    intersection = np.sum((subset_gold == 1) & (subset_predicted == 1), axis=1)
    denominator = np.sum(subset_gold, axis=1) + np.sum(subset_predicted, axis=1)
    sample_f1 = np.divide(
        2.0 * intersection,
        denominator,
        out=np.zeros_like(denominator, dtype=float),
        where=denominator != 0,
    )
    return {
        "slice": name,
        "rows": int(mask.sum()),
        "subset_accuracy": float(np.mean(np.all(subset_gold == subset_predicted, axis=1))),
        "samples_f1_zero_division_0": float(np.mean(sample_f1)),
        "hamming_loss": float(np.mean(subset_gold != subset_predicted)),
        "mean_predicted_cardinality": float(np.mean(np.sum(subset_predicted, axis=1))),
        "empty_prediction_rate": float(np.mean(np.sum(subset_predicted, axis=1) == 0)),
    }


def main() -> None:
    started = time.time()
    args = parse_args()
    config_path = args.config.resolve()
    config = load_json(config_path)
    if config.get("experiment_id") != "EXP-055" or config.get("test_access") is not False:
        raise ValueError("Invalid EXP-055 authorization")
    if config.get("source_splits") != ["validation"] or config.get("training_authorized") is not False:
        raise ValueError("Invalid split or training boundary")

    protocol_path = assert_record(config["protocol"])
    implementation_paths = {name: assert_record(record) for name, record in config["implementation"].items()}
    validation_path = assert_record(config["validation"])
    for record in config["upstream_aggregates"]:
        payload = load_json(assert_record(record))
        if payload.get("status") != "Passed" or payload.get("test_split_accessed") is not False:
            raise ValueError("Upstream aggregate is not validation-only Passed evidence")

    output_dir = resolve(config["output_dir"])
    private_dir = resolve(config["private_output_dir"])
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite append-only output: {output_dir}")
    if private_dir.exists() and any(private_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite private output: {private_dir}")
    if args.check:
        print(json.dumps({"status": "Ready", "test_accessed": False, "output_empty": True}))
        return

    output_dir.mkdir(parents=True, exist_ok=False)
    private_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.chmod(private_dir, 0o700)

    shutil.copy2(config_path, output_dir / "frozen-config.json")
    shutil.copy2(protocol_path, output_dir / "frozen-protocol.md")
    frozen_names = {
        "analyzer": "frozen-analyzer.py",
        "finalizer": "frozen-finalizer.py",
        "verifier": "frozen-verifier.py",
        "tests": "frozen-tests.py",
    }
    for name, path in implementation_paths.items():
        shutil.copy2(path, output_dir / frozen_names[name])

    validation_rows = load_jsonl(validation_path)
    if len(validation_rows) != 720:
        raise ValueError("Validation row count drift")
    sample_ids = np.asarray([row["sample_id"] for row in validation_rows]).astype(str)
    component_ids = np.asarray([row["component_id"] for row in validation_rows]).astype(str)
    gold = np.asarray([row["labels"] for row in validation_rows], dtype=np.uint8)
    if gold.shape != (720, len(LABELS)) or len(set(sample_ids)) != 720:
        raise ValueError("Validation identity or gold shape drift")

    sources: dict[str, dict[int, dict[str, Any]]] = {"m1": {}, "m3": {}}
    for family in sources:
        for seed in (42, 43, 44):
            source = load_source(config, family, seed)
            if not np.array_equal(source["sample_ids"], sample_ids):
                raise ValueError(f"Sample order mismatch for {family} seed {seed}")
            if not np.array_equal(source["component_ids"], component_ids):
                raise ValueError(f"Component order mismatch for {family} seed {seed}")
            if not np.array_equal(source["gold"], gold):
                raise ValueError(f"Gold mismatch for {family} seed {seed}")
            sources[family][seed] = source

    seed_metrics: list[dict[str, Any]] = []
    per_label_metrics: list[dict[str, Any]] = []
    exact_transitions: list[dict[str, Any]] = []
    per_label_transitions: list[dict[str, Any]] = []
    slice_metrics: list[dict[str, Any]] = []
    cardinality_rows: list[dict[str, Any]] = []
    calibration_rows: list[dict[str, Any]] = []
    oracle_rows: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []

    cardinality = np.sum(gold, axis=1)
    slices: list[tuple[str, np.ndarray]] = [
        ("all", np.ones(len(gold), dtype=bool)),
        ("neutral", cardinality == 0),
        ("single_label", cardinality == 1),
        ("two_label", cardinality == 2),
    ] + [(f"gold_{label}", gold[:, index] == 1) for index, label in enumerate(LABELS)]

    for family in ("m1", "m3"):
        for seed in (42, 43, 44):
            source = sources[family][seed]
            fixed_metrics = metric_bundle(gold, source["fixed_0.5"])
            shared_metrics = metric_bundle(gold, source["shared_threshold"])
            calibration_rows.append({
                "family": family,
                "seed": seed,
                "changed_rows": int(np.sum(np.any(source["fixed_0.5"] != source["shared_threshold"], axis=1))),
                "changed_label_bits": int(np.sum(source["fixed_0.5"] != source["shared_threshold"])),
                "macro_f1_delta_shared_minus_fixed": shared_metrics["macro_f1"] - fixed_metrics["macro_f1"],
                "subset_accuracy_delta_shared_minus_fixed": shared_metrics["subset_accuracy"] - fixed_metrics["subset_accuracy"],
                "hamming_loss_delta_shared_minus_fixed": shared_metrics["hamming_loss"] - fixed_metrics["hamming_loss"],
            })
            for condition in CONDITIONS:
                predicted = source[condition]
                metrics = metric_bundle(gold, predicted)
                seed_metrics.append({
                    "family": family,
                    "seed": seed,
                    "condition": condition,
                    **{key: value for key, value in metrics.items() if key != "per_label"},
                })
                for label, values in metrics["per_label"].items():
                    per_label_metrics.append({
                        "family": family,
                        "seed": seed,
                        "condition": condition,
                        "label": label,
                        **values,
                    })
                predicted_cardinality = np.sum(predicted, axis=1)
                cardinality_rows.append({
                    "family": family,
                    "seed": seed,
                    "condition": condition,
                    "mean_predicted_cardinality": float(np.mean(predicted_cardinality)),
                    "empty_predictions": int(np.sum(predicted_cardinality == 0)),
                    "false_empty_positive_rows": int(np.sum((predicted_cardinality == 0) & (cardinality > 0))),
                    "neutral_false_positive_rows": int(np.sum((cardinality == 0) & (predicted_cardinality > 0))),
                    "two_label_underpredicted_rows": int(np.sum((cardinality == 2) & (predicted_cardinality < 2))),
                    "exact_cardinality_rows": int(np.sum(predicted_cardinality == cardinality)),
                })
                for slice_name, mask in slices:
                    slice_metrics.append({"family": family, "seed": seed, "condition": condition, **slice_row(slice_name, mask, gold, predicted)})

    for condition in CONDITIONS:
        for seed in (42, 43, 44):
            m1 = sources["m1"][seed][condition]
            m3 = sources["m3"][seed][condition]
            m1_exact = np.all(m1 == gold, axis=1)
            m3_exact = np.all(m3 == gold, axis=1)
            exact_transitions.append({
                "seed": seed,
                "condition": condition,
                "both_correct": int(np.sum(m1_exact & m3_exact)),
                "m1_only_correct": int(np.sum(m1_exact & ~m3_exact)),
                "m3_only_correct": int(np.sum(~m1_exact & m3_exact)),
                "both_wrong": int(np.sum(~m1_exact & ~m3_exact)),
            })
            for index, label in enumerate(LABELS):
                m1_correct = m1[:, index] == gold[:, index]
                m3_correct = m3[:, index] == gold[:, index]
                per_label_transitions.append({
                    "seed": seed,
                    "condition": condition,
                    "label": label,
                    "support": int(gold[:, index].sum()),
                    "both_correct": int(np.sum(m1_correct & m3_correct)),
                    "m1_only_correct": int(np.sum(m1_correct & ~m3_correct)),
                    "m3_only_correct": int(np.sum(~m1_correct & m3_correct)),
                    "both_wrong": int(np.sum(~m1_correct & ~m3_correct)),
                    "m1_false_positive_recovered": int(np.sum((gold[:, index] == 0) & (m1[:, index] == 1) & (m3[:, index] == 0))),
                    "m1_false_negative_recovered": int(np.sum((gold[:, index] == 1) & (m1[:, index] == 0) & (m3[:, index] == 1))),
                    "m3_false_positive_regression": int(np.sum((gold[:, index] == 0) & (m1[:, index] == 0) & (m3[:, index] == 1))),
                    "m3_false_negative_regression": int(np.sum((gold[:, index] == 1) & (m1[:, index] == 1) & (m3[:, index] == 0))),
                })

            m1_errors = np.sum(m1 != gold, axis=1)
            m3_errors = np.sum(m3 != gold, axis=1)
            choose_m3 = m3_errors < m1_errors
            oracle = np.where(choose_m3[:, None], m3, m1)
            m1_metrics = metric_bundle(gold, m1)
            m3_metrics = metric_bundle(gold, m3)
            oracle_metrics = metric_bundle(gold, oracle)
            bootstrap = component_bootstrap(
                gold, m1, oracle, component_ids, seed, condition, int(config["bootstrap_replicates"])
            )
            oracle_rows.append({
                "seed": seed,
                "condition": condition,
                "m3_selected_rows": int(choose_m3.sum()),
                "m3_selection_rate": float(choose_m3.mean()),
                "tie_rows_select_m1": int(np.sum(m3_errors == m1_errors)),
                "oracle_macro_f1": oracle_metrics["macro_f1"],
                "oracle_five_label_macro_f1_without_surprise": oracle_metrics["five_label_macro_f1_without_surprise"],
                "oracle_micro_f1": oracle_metrics["micro_f1"],
                "oracle_weighted_f1": oracle_metrics["weighted_f1"],
                "oracle_subset_accuracy": oracle_metrics["subset_accuracy"],
                "oracle_hamming_loss": oracle_metrics["hamming_loss"],
                "macro_f1_delta_vs_m1": oracle_metrics["macro_f1"] - m1_metrics["macro_f1"],
                "macro_f1_delta_vs_m3": oracle_metrics["macro_f1"] - m3_metrics["macro_f1"],
                "five_label_macro_f1_delta_vs_m1": oracle_metrics["five_label_macro_f1_without_surprise"] - m1_metrics["five_label_macro_f1_without_surprise"],
                "five_label_macro_f1_delta_vs_m3": oracle_metrics["five_label_macro_f1_without_surprise"] - m3_metrics["five_label_macro_f1_without_surprise"],
                "six_label_delta_ci95_low": bootstrap["six_label_delta_ci95"][0],
                "six_label_delta_ci95_high": bootstrap["six_label_delta_ci95"][1],
                "five_label_delta_ci95_low": bootstrap["five_label_delta_ci95"][0],
                "five_label_delta_ci95_high": bootstrap["five_label_delta_ci95"][1],
            })

        for family in ("m1", "m3"):
            correct_counts = np.sum(
                np.stack([np.all(sources[family][seed][condition] == gold, axis=1) for seed in (42, 43, 44)]),
                axis=0,
            )
            stability_rows.extend([
                {"family": family, "condition": condition, "category": "stable_exact_correct_3_of_3", "rows": int(np.sum(correct_counts == 3))},
                {"family": family, "condition": condition, "category": "seed_unstable_1_or_2_of_3", "rows": int(np.sum((correct_counts == 1) | (correct_counts == 2)))},
                {"family": family, "condition": condition, "category": "stable_exact_wrong_0_of_3", "rows": int(np.sum(correct_counts == 0))},
            ])

    shared_oracle = [row for row in oracle_rows if row["condition"] == "shared_threshold"]
    six_deltas = [float(row["macro_f1_delta_vs_m1"]) for row in shared_oracle]
    five_deltas = [float(row["five_label_macro_f1_delta_vs_m1"]) for row in shared_oracle]
    selection_rates = [float(row["m3_selection_rate"]) for row in shared_oracle]
    gate_checks = {
        "six_label_positive_3_of_3": all(value > 0 for value in six_deltas),
        "six_label_mean_at_least_0.020": statistics.fmean(six_deltas) >= 0.020,
        "five_label_positive_3_of_3": all(value > 0 for value in five_deltas),
        "five_label_mean_at_least_0.010": statistics.fmean(five_deltas) >= 0.010,
        "m3_selection_rate_at_least_0.05_3_of_3": all(value >= 0.05 for value in selection_rates),
    }
    router_gate = {"passed": all(gate_checks.values()), "checks": gate_checks}

    shared_exact: dict[str, np.ndarray] = {}
    majority: dict[str, np.ndarray] = {}
    for family in ("m1", "m3"):
        stack = np.stack([sources[family][seed]["shared_threshold"] for seed in (42, 43, 44)])
        majority[family] = (stack.sum(axis=0) >= 2).astype(np.uint8)
        shared_exact[family] = np.stack([np.all(stack[index] == gold, axis=1) for index in range(3)]).sum(axis=0)

    role_specs = [
        ("surprise_gold", np.flatnonzero(gold[:, SURPRISE_INDEX] == 1), 7),
        ("m3_stable_exact_recovery", np.flatnonzero((shared_exact["m1"] == 0) & (shared_exact["m3"] == 3)), 8),
        ("m1_stable_exact_recovery", np.flatnonzero((shared_exact["m1"] == 3) & (shared_exact["m3"] == 0)), 8),
        ("shared_stable_exact_error", np.flatnonzero((shared_exact["m1"] == 0) & (shared_exact["m3"] == 0)), 8),
        ("m1_seed_unstable", np.flatnonzero((shared_exact["m1"] == 1) | (shared_exact["m1"] == 2)), 6),
        ("m3_seed_unstable", np.flatnonzero((shared_exact["m3"] == 1) | (shared_exact["m3"] == 2)), 6),
        ("two_label_disagreement", np.flatnonzero((cardinality == 2) & np.any(majority["m1"] != majority["m3"], axis=1)), 5),
    ]
    used: set[int] = set()
    selected_cases: list[tuple[str, int]] = []
    role_counts: dict[str, int] = {}
    for role, candidates, quota in role_specs:
        selected = select_role(role, candidates.tolist(), quota, sample_ids, gold, used)
        used.update(selected)
        selected_cases.extend((role, index) for index in selected)
        role_counts[role] = len(selected)
    if len(selected_cases) > int(config["qualitative_max_rows"]):
        raise ValueError("Qualitative sample budget exceeded")

    sample_manifest: list[dict[str, Any]] = []
    private_case_map: list[dict[str, Any]] = []
    review_deck: list[dict[str, Any]] = []
    for role, index in selected_cases:
        cid = case_id(sample_ids[index])
        sample_manifest.append({
            "case_id": cid,
            "role": role,
            "gold_labels": label_names(gold[index]),
            "gold_cardinality": int(cardinality[index]),
            "m1_exact_correct_seeds": int(shared_exact["m1"][index]),
            "m3_exact_correct_seeds": int(shared_exact["m3"][index]),
            "m1_majority_labels": label_names(majority["m1"][index]),
            "m3_majority_labels": label_names(majority["m3"][index]),
        })
        private_case_map.append({"case_id": cid, "sample_id": sample_ids[index], "component_id": component_ids[index]})
        review_deck.append({
            "case_id": cid,
            "role": role,
            "text": validation_rows[index]["text"],
            "gold_labels": label_names(gold[index]),
            "m1_seed_predictions": [label_names(sources["m1"][seed]["shared_threshold"][index]) for seed in (42, 43, 44)],
            "m3_seed_predictions": [label_names(sources["m3"][seed]["shared_threshold"][index]) for seed in (42, 43, 44)],
        })

    high_confidence: list[dict[str, Any]] = []
    for family in ("m1", "m3"):
        mean_probabilities = np.mean(np.stack([sources[family][seed]["probabilities"] for seed in (42, 43, 44)]), axis=0)
        for label_index, label in enumerate(LABELS):
            majority_positive = majority[family][:, label_index] == 1
            for error_type, candidate_mask, reverse in (
                ("false_positive", (gold[:, label_index] == 0) & majority_positive, True),
                ("false_negative", (gold[:, label_index] == 1) & ~majority_positive, False),
            ):
                indices = np.flatnonzero(candidate_mask).tolist()
                indices.sort(key=lambda index: float(mean_probabilities[index, label_index]), reverse=reverse)
                for rank, index in enumerate(indices[:3], start=1):
                    high_confidence.append({
                        "family": family,
                        "label": label,
                        "error_type": error_type,
                        "rank": rank,
                        "case_id": case_id(sample_ids[index]),
                        "mean_probability": float(mean_probabilities[index, label_index]),
                        "gold_labels": label_names(gold[index]),
                        "family_majority_labels": label_names(majority[family][index]),
                    })

    fields = {
        "seed_metrics.csv": ["family", "seed", "condition", "macro_f1", "macro_precision", "macro_recall", "micro_f1", "weighted_f1", "subset_accuracy", "samples_f1_zero_division_0", "hamming_loss", "five_label_macro_f1_without_surprise"],
        "per_label_metrics.csv": ["family", "seed", "condition", "label", "tp", "fp", "fn", "tn", "support", "precision", "recall", "f1"],
        "exact_transitions.csv": ["seed", "condition", "both_correct", "m1_only_correct", "m3_only_correct", "both_wrong"],
        "family_stability.csv": ["family", "condition", "category", "rows"],
        "per_label_transitions.csv": ["seed", "condition", "label", "support", "both_correct", "m1_only_correct", "m3_only_correct", "both_wrong", "m1_false_positive_recovered", "m1_false_negative_recovered", "m3_false_positive_regression", "m3_false_negative_regression"],
        "slice_metrics.csv": ["family", "seed", "condition", "slice", "rows", "subset_accuracy", "samples_f1_zero_division_0", "hamming_loss", "mean_predicted_cardinality", "empty_prediction_rate"],
        "cardinality_summary.csv": ["family", "seed", "condition", "mean_predicted_cardinality", "empty_predictions", "false_empty_positive_rows", "neutral_false_positive_rows", "two_label_underpredicted_rows", "exact_cardinality_rows"],
        "calibration_sensitivity.csv": ["family", "seed", "changed_rows", "changed_label_bits", "macro_f1_delta_shared_minus_fixed", "subset_accuracy_delta_shared_minus_fixed", "hamming_loss_delta_shared_minus_fixed"],
        "oracle_summary.csv": ["seed", "condition", "m3_selected_rows", "m3_selection_rate", "tie_rows_select_m1", "oracle_macro_f1", "oracle_five_label_macro_f1_without_surprise", "oracle_micro_f1", "oracle_weighted_f1", "oracle_subset_accuracy", "oracle_hamming_loss", "macro_f1_delta_vs_m1", "macro_f1_delta_vs_m3", "five_label_macro_f1_delta_vs_m1", "five_label_macro_f1_delta_vs_m3", "six_label_delta_ci95_low", "six_label_delta_ci95_high", "five_label_delta_ci95_low", "five_label_delta_ci95_high"],
        "high_confidence_errors.csv": ["family", "label", "error_type", "rank", "case_id", "mean_probability", "gold_labels", "family_majority_labels"],
        "sample_manifest.csv": ["case_id", "role", "gold_labels", "gold_cardinality", "m1_exact_correct_seeds", "m3_exact_correct_seeds", "m1_majority_labels", "m3_majority_labels"],
    }
    payloads = {
        "seed_metrics.csv": seed_metrics,
        "per_label_metrics.csv": per_label_metrics,
        "exact_transitions.csv": exact_transitions,
        "family_stability.csv": stability_rows,
        "per_label_transitions.csv": per_label_transitions,
        "slice_metrics.csv": slice_metrics,
        "cardinality_summary.csv": cardinality_rows,
        "calibration_sensitivity.csv": calibration_rows,
        "oracle_summary.csv": oracle_rows,
        "high_confidence_errors.csv": high_confidence,
        "sample_manifest.csv": sample_manifest,
    }
    for filename, rows in payloads.items():
        write_csv(output_dir / filename, rows, fields[filename])
    write_jsonl(private_dir / "case-map.jsonl", private_case_map, private=True)
    write_jsonl(private_dir / "review-deck.jsonl", review_deck, private=True)

    primary_summary = {
        family: {
            metric: mean_std([
                next(row[metric] for row in seed_metrics if row["family"] == family and row["seed"] == seed and row["condition"] == "shared_threshold")
                for seed in (42, 43, 44)
            ])
            for metric in ("macro_f1", "micro_f1", "weighted_f1", "subset_accuracy", "hamming_loss", "five_label_macro_f1_without_surprise")
        }
        for family in ("m1", "m3")
    }
    analysis = {
        "schema_version": "exp-055-m1-m3-error-analysis-prepare-v1",
        "experiment_id": "EXP-055",
        "tier": "Major",
        "stage": "quantitative-complete-awaiting-qualitative-review",
        "status": "Prepared",
        "source_split": "validation",
        "rows": 720,
        "components": len(set(component_ids)),
        "labels": list(LABELS),
        "test_split_accessed": False,
        "training_performed": False,
        "inference_performed": False,
        "primary_shared_threshold_summary": primary_summary,
        "router_headroom_gate": router_gate,
        "router_gate_values": {
            "six_label_delta_vs_m1": mean_std(six_deltas),
            "five_label_delta_vs_m1": mean_std(five_deltas),
            "m3_selection_rate": mean_std(selection_rates),
        },
        "qualitative_sample": {"rows": len(sample_manifest), "role_counts": role_counts, "max_rows": int(config["qualitative_max_rows"])},
        "private_review": {"contains_raw_text": True, "tracked": False, "directory_mode": "0700", "file_mode": "0600"},
        "artifacts": {filename: artifact(output_dir / filename) for filename in payloads},
        "frozen_inputs": {
            "config": artifact(output_dir / "frozen-config.json"),
            "protocol": artifact(output_dir / "frozen-protocol.md"),
            **{name: artifact(output_dir / frozen_name) for name, frozen_name in frozen_names.items()},
        },
        "wall_seconds": time.time() - started,
    }
    write_json(output_dir / "analysis.json", analysis)
    print(json.dumps({
        "status": "Prepared",
        "router_gate_passed": router_gate["passed"],
        "qualitative_rows": len(sample_manifest),
        "test_accessed": False,
    }))


if __name__ == "__main__":
    main()
