#!/usr/bin/env python3
"""EXP-055 verifier attempt 2 with whitespace-normalized report checks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[5]
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
SURPRISE_INDEX = 2
CONDITIONS = ("fixed_0.5", "shared_threshold")
ALLOWED_FLAGS = {
    "sarcasm_or_irony", "negation", "implicit_emotion", "mixed_emotion",
    "surface_noise", "possible_missing_context", "annotation_ambiguity",
    "lexical_cue_conflict", "emotion_ontology_overlap",
    "weak_emotion_neutral_boundary", "multilabel_underprediction",
    "low_support_surprise", "no_listed_factor",
}
ALLOWED_SOURCES = {
    "annotation_or_data_uncertainty", "overlapping_label_ontology",
    "missing_forum_context", "model_or_representation_limitation",
    "calibration_or_threshold_policy", "surface_form_noise",
    "low_support_label_uncertainty", "uncertain",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--authorization", required=True, type=Path)
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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def safe_div(a: float, b: float) -> float:
    return float(a / b) if b else 0.0


def metrics(gold: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    tp = np.sum((gold == 1) & (predicted == 1), axis=0, dtype=np.int64)
    fp = np.sum((gold == 0) & (predicted == 1), axis=0, dtype=np.int64)
    fn = np.sum((gold == 1) & (predicted == 0), axis=0, dtype=np.int64)
    tn = np.sum((gold == 0) & (predicted == 0), axis=0, dtype=np.int64)
    support = np.sum(gold, axis=0, dtype=np.int64)
    precision = np.asarray([safe_div(a, a + b) for a, b in zip(tp, fp)])
    recall = np.asarray([safe_div(a, a + b) for a, b in zip(tp, fn)])
    f1 = np.asarray([safe_div(2 * p * r, p + r) for p, r in zip(precision, recall)])
    micro_p = safe_div(int(tp.sum()), int(tp.sum() + fp.sum()))
    micro_r = safe_div(int(tp.sum()), int(tp.sum() + fn.sum()))
    intersection = np.sum((gold == 1) & (predicted == 1), axis=1)
    denominator = np.sum(gold, axis=1) + np.sum(predicted, axis=1)
    sample_f1 = np.divide(2 * intersection, denominator, out=np.zeros_like(denominator, dtype=float), where=denominator != 0)
    five = [index for index in range(6) if index != SURPRISE_INDEX]
    return {
        "macro_f1": float(f1.mean()),
        "macro_precision": float(precision.mean()),
        "macro_recall": float(recall.mean()),
        "micro_f1": safe_div(2 * micro_p * micro_r, micro_p + micro_r),
        "weighted_f1": safe_div(float(np.sum(f1 * support)), float(np.sum(support))),
        "subset_accuracy": float(np.mean(np.all(gold == predicted, axis=1))),
        "samples_f1_zero_division_0": float(np.mean(sample_f1)),
        "hamming_loss": float(np.mean(gold != predicted)),
        "five_label_macro_f1_without_surprise": float(f1[five].mean()),
        "per_label": {
            label: {
                "tp": int(tp[index]), "fp": int(fp[index]), "fn": int(fn[index]),
                "tn": int(tn[index]), "support": int(support[index]),
                "precision": float(precision[index]), "recall": float(recall[index]),
                "f1": float(f1[index]),
            }
            for index, label in enumerate(LABELS)
        },
    }


def fast_macro(gold: np.ndarray, predicted: np.ndarray, indices: Sequence[int]) -> float:
    tp = np.sum((gold[:, indices] == 1) & (predicted[:, indices] == 1), axis=0)
    fp = np.sum((gold[:, indices] == 0) & (predicted[:, indices] == 1), axis=0)
    fn = np.sum((gold[:, indices] == 1) & (predicted[:, indices] == 0), axis=0)
    denominator = 2 * tp + fp + fn
    f1 = np.divide(2 * tp, denominator, out=np.zeros_like(tp, dtype=float), where=denominator != 0)
    return float(np.mean(f1))


def bootstrap(
    gold: np.ndarray, m1: np.ndarray, oracle: np.ndarray,
    component_ids: Sequence[str], seed: int, condition: str, replicates: int,
) -> tuple[tuple[float, float], tuple[float, float]]:
    groups: dict[str, list[int]] = defaultdict(list)
    for index, component in enumerate(component_ids):
        groups[str(component)].append(index)
    names = sorted(groups)
    entropy = hashlib.sha256(f"EXP-055:{condition}:{seed}".encode("ascii")).digest()
    rng = np.random.default_rng(int.from_bytes(entropy[:8], "big"))
    six = np.empty(replicates, dtype=float)
    five = np.empty(replicates, dtype=float)
    six_indices = list(range(6))
    five_indices = [index for index in six_indices if index != SURPRISE_INDEX]
    for replicate in range(replicates):
        sampled = rng.integers(0, len(names), size=len(names))
        indices = np.asarray([row for group_index in sampled for row in groups[names[int(group_index)]]])
        six[replicate] = fast_macro(gold[indices], oracle[indices], six_indices) - fast_macro(gold[indices], m1[indices], six_indices)
        five[replicate] = fast_macro(gold[indices], oracle[indices], five_indices) - fast_macro(gold[indices], m1[indices], five_indices)
    return (
        (float(np.quantile(six, 0.025)), float(np.quantile(six, 0.975))),
        (float(np.quantile(five, 0.025)), float(np.quantile(five, 0.975))),
    )


def case_id(sample_id: str) -> str:
    return "case-" + hashlib.sha256(f"EXP-055:{sample_id}".encode()).hexdigest()[:16]


def label_names(vector: np.ndarray) -> str:
    labels = [label for label, present in zip(LABELS, vector) if int(present)]
    return ";".join(labels) if labels else "neutral"


def rank_key(role: str, sample_id: str) -> str:
    return hashlib.sha256(f"20260815:EXP-055:{role}:{sample_id}".encode()).hexdigest()


def select_role(role: str, candidates: Iterable[int], quota: int, sample_ids: Sequence[str], gold: np.ndarray, used: set[int]) -> list[int]:
    ordered = sorted((index for index in candidates if index not in used), key=lambda index: rank_key(role, sample_ids[index]))
    selected: list[int] = []
    strata: Counter[str] = Counter()
    for index in ordered:
        stratum = label_names(gold[index])
        if strata[stratum] >= 2:
            continue
        selected.append(index)
        strata[stratum] += 1
        if len(selected) == quota:
            return selected
    for index in ordered:
        if index not in selected:
            selected.append(index)
        if len(selected) == quota:
            break
    return selected


def values_equal(expected: Any, actual: str, tolerance: float = 1e-12) -> bool:
    if isinstance(expected, bool):
        return actual.lower() == str(expected).lower()
    if isinstance(expected, int):
        try:
            return int(actual) == expected
        except ValueError:
            return False
    if isinstance(expected, float):
        try:
            return math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=tolerance)
        except ValueError:
            return False
    return actual == str(expected)


def rows_equal(expected: Sequence[dict[str, Any]], actual: Sequence[dict[str, str]]) -> bool:
    if len(expected) != len(actual):
        return False
    for left, right in zip(expected, actual):
        if set(left) != set(right):
            return False
        if not all(values_equal(value, right[key]) for key, value in left.items()):
            return False
    return True


def slice_values(name: str, mask: np.ndarray, gold: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    subset_gold, subset_pred = gold[mask], predicted[mask]
    intersection = np.sum((subset_gold == 1) & (subset_pred == 1), axis=1)
    denominator = np.sum(subset_gold, axis=1) + np.sum(subset_pred, axis=1)
    sample_f1 = np.divide(2 * intersection, denominator, out=np.zeros_like(denominator, dtype=float), where=denominator != 0)
    return {
        "slice": name,
        "rows": int(mask.sum()),
        "subset_accuracy": float(np.mean(np.all(subset_gold == subset_pred, axis=1))),
        "samples_f1_zero_division_0": float(np.mean(sample_f1)),
        "hamming_loss": float(np.mean(subset_gold != subset_pred)),
        "mean_predicted_cardinality": float(np.mean(np.sum(subset_pred, axis=1))),
        "empty_prediction_rate": float(np.mean(np.sum(subset_pred, axis=1) == 0)),
    }


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    run_dir = args.run_dir.resolve()
    authorization_path = args.authorization.resolve()
    verification_path = run_dir / "verification-attempt-2.json"
    if verification_path.exists():
        raise FileExistsError(f"Refusing to overwrite append-only output: {verification_path}")
    config = load_json(config_path)
    authorization = load_json(authorization_path)
    analysis = load_json(run_dir / "analysis.json")
    run = load_json(run_dir / "run.json")
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check(
        "attempt-2 authorization identity",
        authorization.get("experiment_id") == "EXP-055"
        and authorization.get("verification_attempt") == 2
        and authorization.get("permitted_correction") == "report_whitespace_normalization_only",
    )
    check(
        "attempt-2 base config",
        authorization["base_config"]["sha256"] == sha256_file(config_path),
    )
    for name, frozen_name in (
        ("verifier", "frozen-verifier-attempt-2.py"),
        ("amendment", "frozen-verification-attempt-2-amendment.md"),
    ):
        record = authorization[name]
        live = resolve(record["path"])
        check(f"attempt-2 {name} exists", live.is_file())
        check(f"attempt-2 {name} bytes", live.stat().st_size == int(record["bytes"]))
        check(f"attempt-2 {name} hash", sha256_file(live) == record["sha256"])
        check(f"attempt-2 frozen {name}", sha256_file(run_dir / frozen_name) == record["sha256"])
    check(
        "attempt-2 frozen authorization",
        sha256_file(run_dir / "frozen-verification-attempt-2-authorization.json")
        == sha256_file(authorization_path),
    )

    check("experiment identity", config.get("experiment_id") == "EXP-055" == run.get("experiment_id"))
    check("Major tier", run.get("tier") == "Major")
    check("run completed", run.get("status") == "Completed")
    check("validation only", config.get("source_splits") == ["validation"] and run.get("source_split") == "validation")
    check("training sealed", config.get("training_authorized") is False and run.get("training_performed") is False)
    check("inference sealed", config.get("inference_authorized") is False and run.get("inference_performed") is False)
    check("test sealed", config.get("test_access") is False and run.get("test_split_accessed") is False and analysis.get("test_split_accessed") is False)
    check("M4 sealed", config.get("exp054_authorized") is False and run["claim_boundary"]["exp054_authorized"] is False)
    check("test-ready sealed", config.get("test_ready") is False and run["claim_boundary"]["test_ready"] is False)
    check("config hash", run["config"]["sha256"] == sha256_file(config_path))
    check("frozen config", sha256_file(run_dir / "frozen-config.json") == sha256_file(config_path))

    frozen_names = {"analyzer": "frozen-analyzer.py", "finalizer": "frozen-finalizer.py", "verifier": "frozen-verifier.py", "tests": "frozen-tests.py"}
    for name, record in config["implementation"].items():
        live = resolve(record["path"])
        check(f"implementation exists {name}", live.is_file())
        check(f"implementation bytes {name}", live.stat().st_size == int(record["bytes"]))
        check(f"implementation hash {name}", sha256_file(live) == record["sha256"])
        check(f"frozen implementation {name}", sha256_file(run_dir / frozen_names[name]) == record["sha256"])
    protocol = resolve(config["protocol"]["path"])
    check("protocol hash", sha256_file(protocol) == config["protocol"]["sha256"])
    check("frozen protocol", sha256_file(run_dir / "frozen-protocol.md") == config["protocol"]["sha256"])

    validation_path = resolve(config["validation"]["path"])
    check("validation hash", sha256_file(validation_path) == config["validation"]["sha256"])
    validation_rows = load_jsonl(validation_path)
    gold = np.asarray([row["labels"] for row in validation_rows], dtype=np.uint8)
    sample_ids = np.asarray([row["sample_id"] for row in validation_rows]).astype(str)
    component_ids = np.asarray([row["component_id"] for row in validation_rows]).astype(str)
    check("validation rows", len(validation_rows) == 720)
    check("validation components", len(set(component_ids)) == 702)
    check("validation labels", gold.shape == (720, 6))
    check("validation supports", gold.sum(axis=0).tolist() == [183, 74, 7, 132, 34, 16])
    check("validation cardinality", Counter(gold.sum(axis=1).tolist()) == Counter({0: 294, 1: 406, 2: 20}))

    for aggregate_record in config["upstream_aggregates"]:
        path = resolve(aggregate_record["path"])
        payload = load_json(path)
        check(f"aggregate hash {path.name}", sha256_file(path) == aggregate_record["sha256"])
        check(f"aggregate Passed {path.name}", payload.get("status") == "Passed")
        check(f"aggregate test sealed {path.name}", payload.get("test_split_accessed") is False)

    sources: dict[str, dict[int, dict[str, Any]]] = {"m1": {}, "m3": {}}
    for family in sources:
        for record in config["sources"][family]:
            seed = int(record["seed"])
            pred_path = resolve(record["predictions"]["path"])
            verifier_path = resolve(record["verification"]["path"])
            check(f"{family} seed {seed} prediction hash", sha256_file(pred_path) == record["predictions"]["sha256"])
            check(f"{family} seed {seed} verification hash", sha256_file(verifier_path) == record["verification"]["sha256"])
            verifier = load_json(verifier_path)
            check(f"{family} seed {seed} Passed", verifier.get("status") == "Passed")
            check(f"{family} seed {seed} test sealed", verifier.get("test_split_accessed") is False)
            data = np.load(pred_path, allow_pickle=False)
            check(f"{family} seed {seed} NPZ schema", set(data.files) == {"probabilities", "gold", "fixed_predictions", "shared_threshold_predictions", "sample_ids", "component_ids"})
            probabilities = np.asarray(data["probabilities"], dtype=np.float32)
            selected = probabilities[int(record["selected_epoch"]) - 1]
            fixed = (selected >= 0.5).astype(np.uint8)
            shared = (selected >= float(record["shared_threshold"])).astype(np.uint8)
            check(f"{family} seed {seed} row order", np.array_equal(np.asarray(data["sample_ids"]).astype(str), sample_ids))
            check(f"{family} seed {seed} component order", np.array_equal(np.asarray(data["component_ids"]).astype(str), component_ids))
            check(f"{family} seed {seed} gold", np.array_equal(np.asarray(data["gold"], dtype=np.uint8), gold))
            check(f"{family} seed {seed} fixed replay", np.array_equal(fixed, data["fixed_predictions"]))
            check(f"{family} seed {seed} shared replay", np.array_equal(shared, data["shared_threshold_predictions"]))
            sources[family][seed] = {"probabilities": selected, "fixed_0.5": fixed, "shared_threshold": shared}

    expected_seed_metrics: list[dict[str, Any]] = []
    expected_label_metrics: list[dict[str, Any]] = []
    expected_slices: list[dict[str, Any]] = []
    expected_cardinality: list[dict[str, Any]] = []
    expected_calibration: list[dict[str, Any]] = []
    cardinality = gold.sum(axis=1)
    slices = [
        ("all", np.ones(720, dtype=bool)), ("neutral", cardinality == 0),
        ("single_label", cardinality == 1), ("two_label", cardinality == 2),
    ] + [(f"gold_{label}", gold[:, index] == 1) for index, label in enumerate(LABELS)]
    for family in ("m1", "m3"):
        for seed in (42, 43, 44):
            fixed_metrics = metrics(gold, sources[family][seed]["fixed_0.5"])
            shared_metrics = metrics(gold, sources[family][seed]["shared_threshold"])
            expected_calibration.append({
                "family": family, "seed": seed,
                "changed_rows": int(np.any(sources[family][seed]["fixed_0.5"] != sources[family][seed]["shared_threshold"], axis=1).sum()),
                "changed_label_bits": int(np.sum(sources[family][seed]["fixed_0.5"] != sources[family][seed]["shared_threshold"])),
                "macro_f1_delta_shared_minus_fixed": shared_metrics["macro_f1"] - fixed_metrics["macro_f1"],
                "subset_accuracy_delta_shared_minus_fixed": shared_metrics["subset_accuracy"] - fixed_metrics["subset_accuracy"],
                "hamming_loss_delta_shared_minus_fixed": shared_metrics["hamming_loss"] - fixed_metrics["hamming_loss"],
            })
            for condition in CONDITIONS:
                predicted = sources[family][seed][condition]
                bundle = metrics(gold, predicted)
                expected_seed_metrics.append({"family": family, "seed": seed, "condition": condition, **{k: v for k, v in bundle.items() if k != "per_label"}})
                for label, values in bundle["per_label"].items():
                    expected_label_metrics.append({"family": family, "seed": seed, "condition": condition, "label": label, **values})
                pred_cardinality = predicted.sum(axis=1)
                expected_cardinality.append({
                    "family": family, "seed": seed, "condition": condition,
                    "mean_predicted_cardinality": float(np.mean(pred_cardinality)),
                    "empty_predictions": int(np.sum(pred_cardinality == 0)),
                    "false_empty_positive_rows": int(np.sum((pred_cardinality == 0) & (cardinality > 0))),
                    "neutral_false_positive_rows": int(np.sum((cardinality == 0) & (pred_cardinality > 0))),
                    "two_label_underpredicted_rows": int(np.sum((cardinality == 2) & (pred_cardinality < 2))),
                    "exact_cardinality_rows": int(np.sum(pred_cardinality == cardinality)),
                })
                for slice_name, mask in slices:
                    expected_slices.append({"family": family, "seed": seed, "condition": condition, **slice_values(slice_name, mask, gold, predicted)})

    check("seed metrics", rows_equal(expected_seed_metrics, read_csv(run_dir / "seed_metrics.csv")))
    check("per-label metrics", rows_equal(expected_label_metrics, read_csv(run_dir / "per_label_metrics.csv")))
    check("slice metrics", rows_equal(expected_slices, read_csv(run_dir / "slice_metrics.csv")))
    check("cardinality summary", rows_equal(expected_cardinality, read_csv(run_dir / "cardinality_summary.csv")))
    check("calibration sensitivity", rows_equal(expected_calibration, read_csv(run_dir / "calibration_sensitivity.csv")))

    expected_exact: list[dict[str, Any]] = []
    expected_transitions: list[dict[str, Any]] = []
    expected_stability: list[dict[str, Any]] = []
    expected_oracle: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        for seed in (42, 43, 44):
            m1, m3 = sources["m1"][seed][condition], sources["m3"][seed][condition]
            m1_exact, m3_exact = np.all(m1 == gold, axis=1), np.all(m3 == gold, axis=1)
            expected_exact.append({
                "seed": seed, "condition": condition,
                "both_correct": int(np.sum(m1_exact & m3_exact)),
                "m1_only_correct": int(np.sum(m1_exact & ~m3_exact)),
                "m3_only_correct": int(np.sum(~m1_exact & m3_exact)),
                "both_wrong": int(np.sum(~m1_exact & ~m3_exact)),
            })
            for index, label in enumerate(LABELS):
                c1, c3 = m1[:, index] == gold[:, index], m3[:, index] == gold[:, index]
                expected_transitions.append({
                    "seed": seed, "condition": condition, "label": label, "support": int(gold[:, index].sum()),
                    "both_correct": int(np.sum(c1 & c3)), "m1_only_correct": int(np.sum(c1 & ~c3)),
                    "m3_only_correct": int(np.sum(~c1 & c3)), "both_wrong": int(np.sum(~c1 & ~c3)),
                    "m1_false_positive_recovered": int(np.sum((gold[:, index] == 0) & (m1[:, index] == 1) & (m3[:, index] == 0))),
                    "m1_false_negative_recovered": int(np.sum((gold[:, index] == 1) & (m1[:, index] == 0) & (m3[:, index] == 1))),
                    "m3_false_positive_regression": int(np.sum((gold[:, index] == 0) & (m1[:, index] == 0) & (m3[:, index] == 1))),
                    "m3_false_negative_regression": int(np.sum((gold[:, index] == 1) & (m1[:, index] == 1) & (m3[:, index] == 0))),
                })
            error1, error3 = np.sum(m1 != gold, axis=1), np.sum(m3 != gold, axis=1)
            choose3 = error3 < error1
            oracle = np.where(choose3[:, None], m3, m1)
            metric1, metric3, metric_oracle = metrics(gold, m1), metrics(gold, m3), metrics(gold, oracle)
            six_ci, five_ci = bootstrap(gold, m1, oracle, component_ids, seed, condition, int(config["bootstrap_replicates"]))
            expected_oracle.append({
                "seed": seed, "condition": condition, "m3_selected_rows": int(choose3.sum()),
                "m3_selection_rate": float(choose3.mean()), "tie_rows_select_m1": int(np.sum(error3 == error1)),
                "oracle_macro_f1": metric_oracle["macro_f1"],
                "oracle_five_label_macro_f1_without_surprise": metric_oracle["five_label_macro_f1_without_surprise"],
                "oracle_micro_f1": metric_oracle["micro_f1"], "oracle_weighted_f1": metric_oracle["weighted_f1"],
                "oracle_subset_accuracy": metric_oracle["subset_accuracy"], "oracle_hamming_loss": metric_oracle["hamming_loss"],
                "macro_f1_delta_vs_m1": metric_oracle["macro_f1"] - metric1["macro_f1"],
                "macro_f1_delta_vs_m3": metric_oracle["macro_f1"] - metric3["macro_f1"],
                "five_label_macro_f1_delta_vs_m1": metric_oracle["five_label_macro_f1_without_surprise"] - metric1["five_label_macro_f1_without_surprise"],
                "five_label_macro_f1_delta_vs_m3": metric_oracle["five_label_macro_f1_without_surprise"] - metric3["five_label_macro_f1_without_surprise"],
                "six_label_delta_ci95_low": six_ci[0], "six_label_delta_ci95_high": six_ci[1],
                "five_label_delta_ci95_low": five_ci[0], "five_label_delta_ci95_high": five_ci[1],
            })
        for family in ("m1", "m3"):
            counts = np.stack([np.all(sources[family][seed][condition] == gold, axis=1) for seed in (42, 43, 44)]).sum(axis=0)
            expected_stability.extend([
                {"family": family, "condition": condition, "category": "stable_exact_correct_3_of_3", "rows": int(np.sum(counts == 3))},
                {"family": family, "condition": condition, "category": "seed_unstable_1_or_2_of_3", "rows": int(np.sum((counts == 1) | (counts == 2)))},
                {"family": family, "condition": condition, "category": "stable_exact_wrong_0_of_3", "rows": int(np.sum(counts == 0))},
            ])
    check("exact transitions", rows_equal(expected_exact, read_csv(run_dir / "exact_transitions.csv")))
    check("per-label transitions", rows_equal(expected_transitions, read_csv(run_dir / "per_label_transitions.csv")))
    check("family stability", rows_equal(expected_stability, read_csv(run_dir / "family_stability.csv")))
    check("oracle summary", rows_equal(expected_oracle, read_csv(run_dir / "oracle_summary.csv")))

    shared_oracle = [row for row in expected_oracle if row["condition"] == "shared_threshold"]
    six_values = [row["macro_f1_delta_vs_m1"] for row in shared_oracle]
    five_values = [row["five_label_macro_f1_delta_vs_m1"] for row in shared_oracle]
    rates = [row["m3_selection_rate"] for row in shared_oracle]
    expected_gate = {
        "six_label_positive_3_of_3": all(value > 0 for value in six_values),
        "six_label_mean_at_least_0.020": sum(six_values) / 3 >= 0.020,
        "five_label_positive_3_of_3": all(value > 0 for value in five_values),
        "five_label_mean_at_least_0.010": sum(five_values) / 3 >= 0.010,
        "m3_selection_rate_at_least_0.05_3_of_3": all(value >= 0.05 for value in rates),
    }
    check("router gate checks", analysis["router_headroom_gate"]["checks"] == expected_gate)
    check("router gate result", analysis["router_headroom_gate"]["passed"] == all(expected_gate.values()) == run["router_headroom_gate"]["passed"])

    stacks = {family: np.stack([sources[family][seed]["shared_threshold"] for seed in (42, 43, 44)]) for family in ("m1", "m3")}
    majority = {family: (stack.sum(axis=0) >= 2).astype(np.uint8) for family, stack in stacks.items()}
    exact_count = {family: np.stack([np.all(stack[index] == gold, axis=1) for index in range(3)]).sum(axis=0) for family, stack in stacks.items()}
    specs = [
        ("surprise_gold", np.flatnonzero(gold[:, 2] == 1), 7),
        ("m3_stable_exact_recovery", np.flatnonzero((exact_count["m1"] == 0) & (exact_count["m3"] == 3)), 8),
        ("m1_stable_exact_recovery", np.flatnonzero((exact_count["m1"] == 3) & (exact_count["m3"] == 0)), 8),
        ("shared_stable_exact_error", np.flatnonzero((exact_count["m1"] == 0) & (exact_count["m3"] == 0)), 8),
        ("m1_seed_unstable", np.flatnonzero((exact_count["m1"] == 1) | (exact_count["m1"] == 2)), 6),
        ("m3_seed_unstable", np.flatnonzero((exact_count["m3"] == 1) | (exact_count["m3"] == 2)), 6),
        ("two_label_disagreement", np.flatnonzero((gold.sum(axis=1) == 2) & np.any(majority["m1"] != majority["m3"], axis=1)), 5),
    ]
    used: set[int] = set()
    expected_samples: list[dict[str, Any]] = []
    for role, candidates, quota in specs:
        selected = select_role(role, candidates.tolist(), quota, sample_ids, gold, used)
        used.update(selected)
        for index in selected:
            expected_samples.append({
                "case_id": case_id(sample_ids[index]), "role": role, "gold_labels": label_names(gold[index]),
                "gold_cardinality": int(gold[index].sum()), "m1_exact_correct_seeds": int(exact_count["m1"][index]),
                "m3_exact_correct_seeds": int(exact_count["m3"][index]), "m1_majority_labels": label_names(majority["m1"][index]),
                "m3_majority_labels": label_names(majority["m3"][index]),
            })
    check("qualitative budget", len(expected_samples) <= int(config["qualitative_max_rows"]))
    check("deterministic sample manifest", rows_equal(expected_samples, read_csv(run_dir / "sample_manifest.csv")))

    expected_high: list[dict[str, Any]] = []
    for family in ("m1", "m3"):
        mean_prob = np.mean(np.stack([sources[family][seed]["probabilities"] for seed in (42, 43, 44)]), axis=0)
        for label_index, label in enumerate(LABELS):
            positive = majority[family][:, label_index] == 1
            for error_type, mask, reverse in (
                ("false_positive", (gold[:, label_index] == 0) & positive, True),
                ("false_negative", (gold[:, label_index] == 1) & ~positive, False),
            ):
                indices = np.flatnonzero(mask).tolist()
                indices.sort(key=lambda index: float(mean_prob[index, label_index]), reverse=reverse)
                for rank, index in enumerate(indices[:3], 1):
                    expected_high.append({
                        "family": family, "label": label, "error_type": error_type, "rank": rank,
                        "case_id": case_id(sample_ids[index]), "mean_probability": float(mean_prob[index, label_index]),
                        "gold_labels": label_names(gold[index]), "family_majority_labels": label_names(majority[family][index]),
                    })
    check("high-confidence errors", rows_equal(expected_high, read_csv(run_dir / "high_confidence_errors.csv")))

    annotations = read_csv(run_dir / "manual_annotations.csv")
    check("annotation coverage", {row["case_id"] for row in annotations} == {row["case_id"] for row in expected_samples} and len(annotations) == len(expected_samples))
    check("annotation reviewer", all(row["reviewer"] == "assistant_single_reviewer" for row in annotations))
    check("annotation sources", all(row["primary_source"] in ALLOWED_SOURCES for row in annotations))
    check("annotation plausibility", all(row["gold_plausibility"] in {"plausible", "debatable", "implausible"} for row in annotations))
    check("annotation flags", all(
        bool(row["flags"]) and set(row["flags"].split(";")).issubset(ALLOWED_FLAGS)
        and not ("no_listed_factor" in row["flags"].split(";") and len(row["flags"].split(";")) != 1)
        for row in annotations
    ))
    qualitative = load_json(run_dir / "qualitative_summary.json")
    flag_counts: Counter[str] = Counter(flag for row in annotations for flag in row["flags"].split(";"))
    source_counts = Counter(row["primary_source"] for row in annotations)
    plausibility_counts = Counter(row["gold_plausibility"] for row in annotations)
    check("qualitative flag counts", qualitative["flag_counts"] == dict(sorted(flag_counts.items())))
    check("qualitative source counts", qualitative["primary_source_counts"] == dict(sorted(source_counts.items())))
    check("qualitative plausibility counts", qualitative["gold_plausibility_counts"] == dict(sorted(plausibility_counts.items())))
    check("single-reviewer boundary", qualitative["reviewer_count"] == 1 and "not revised ground truth" in qualitative["claim_boundary"])

    summary = load_json(run_dir / "summary.json")
    check("summary identity", summary.get("experiment_id") == "EXP-055" and summary.get("source_split") == "validation")
    check("summary test sealed", summary.get("test_split_accessed") is False)
    check("summary primary metrics", summary.get("primary_shared_threshold_summary") == analysis["primary_shared_threshold_summary"])
    check("summary router gate", summary.get("router_headroom_gate") == run["router_headroom_gate"])
    check("summary qualitative counts", summary.get("qualitative") == {
        "rows": len(annotations),
        "reviewer_count": 1,
        "flag_counts": dict(sorted(flag_counts.items())),
        "primary_source_counts": dict(sorted(source_counts.items())),
        "gold_plausibility_counts": dict(sorted(plausibility_counts.items())),
    })

    private_dir = resolve(config["private_output_dir"])
    check("private directory mode", (private_dir.stat().st_mode & 0o777) == 0o700)
    private_files = [private_dir / "case-map.jsonl", private_dir / "review-deck.jsonl"]
    check("private files exist", all(path.is_file() for path in private_files))
    check("private file modes", all((path.stat().st_mode & 0o777) == 0o600 for path in private_files))
    ignored = subprocess.run(["git", "check-ignore", "-q", str(private_dir)], cwd=REPO_ROOT).returncode == 0
    check("private directory gitignored", ignored)
    case_map = load_jsonl(private_files[0])
    deck = load_jsonl(private_files[1])
    check("private case map coverage", {row["case_id"] for row in case_map} == {row["case_id"] for row in expected_samples})
    check("private deck coverage", {row["case_id"] for row in deck} == {row["case_id"] for row in expected_samples})

    tracked_files = [path for path in run_dir.iterdir() if path.is_file() and path.name not in {"verification.json", "VERIFICATION-SUMMARY.md"}]
    public_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in tracked_files)
    check("no source sample IDs", not any(sample_id in public_text for sample_id in sample_ids))
    check("no source component IDs", not any(component_id in public_text for component_id in component_ids))
    normalized_public = re.sub(r"\s+", " ", public_text)
    windows: set[str] = set()
    for row in validation_rows:
        normalized = re.sub(r"\s+", " ", row["text"]).strip()
        for index in range(max(0, len(normalized) - 19)):
            windows.add(normalized[index:index + 20])
    leaked_windows = [normalized_public[index:index + 20] for index in range(max(0, len(normalized_public) - 19)) if normalized_public[index:index + 20] in windows]
    check("no raw-text 20-character window", not leaked_windows, leaked_windows[:3])

    for name, record in analysis["artifacts"].items():
        path = run_dir / name
        check(f"analysis artifact exists {name}", path.is_file())
        check(f"analysis artifact hash {name}", sha256_file(path) == record["sha256"])
    for name, record in run["artifacts"].items():
        path = run_dir / name
        check(f"run artifact exists {name}", path.is_file())
        check(f"run artifact hash {name}", sha256_file(path) == record["sha256"])
    report = (run_dir / "REPORT.md").read_text(encoding="utf-8")
    normalized_report = re.sub(r"\s+", " ", report)
    check("report validation boundary", "validation only" in normalized_report)
    check("report oracle boundary", "not deployable" in normalized_report)
    check("report qualitative boundary", "not dataset-wide prevalence" in normalized_report)
    check("report test boundary", "access test" in normalized_report and "did not" in normalized_report)
    check("report mechanism boundary", "internal emotion mechanism" in normalized_report)

    failed = [item["name"] for item in checks if not item["passed"]]
    payload = {
        "schema_version": "exp-055-m1-m3-error-analysis-verification-attempt-2-v1",
        "experiment_id": "EXP-055",
        "verification_attempt": 2,
        "permitted_correction": "report_whitespace_normalization_only",
        "authorization_sha256": sha256_file(authorization_path),
        "status": "Passed" if not failed else "Failed",
        "check_count": len(checks),
        "failed_checks": failed,
        "checks": checks,
        "test_split_accessed": False,
        "recomputed_router_gate": {"passed": all(expected_gate.values()), "checks": expected_gate},
    }
    verification_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "check_count": len(checks), "failed": failed}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
