#!/usr/bin/env python3
"""Independently verify EXP-029 LoRA dev artifacts and multi-seed summaries."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any

import numpy as np

EXPERIMENT_ID = "EXP-029"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
CONFIG_PATH = SCRIPT_DIR / "configs" / "exp-029-instruct-lora.json"
RUNNER_PATH = SCRIPT_DIR / "run_lora.py"
METRICS_PATH = SCRIPT_DIR / "llm_full_dev_metrics.py"
DATA_ROOT = PROJECT_ROOT / "data" / "goemotions" / "official"
DEV_PATH = DATA_ROOT / "dev.tsv"
LABELS_PATH = DATA_ROOT / "emotions.txt"
TEST_PATH = DATA_ROOT / "test.tsv"
CONDITIONS = ("zero-shot", "few-shot-synthetic-3")
FORBIDDEN_RECORD_KEYS = {
    "comment_id",
    "input",
    "input_text",
    "prompt",
    "raw_generation",
    "raw_input_text",
    "text",
    "upstream_comment_id",
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


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": str(path.resolve().relative_to(PROJECT_ROOT)),
        "sha256": sha256_file(path),
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def resolve_project_path(value: str) -> Path:
    return PROJECT_ROOT / value


def verify_hash(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"Hash mismatch for {path}: {actual} != {expected}")


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config["experiment_id"] != EXPERIMENT_ID or config["status"] != "Registered":
        raise ValueError("Unexpected EXP-029 configuration identity or status")
    verify_hash(RUNNER_PATH, config["implementation"]["runner_sha256"])
    verify_hash(METRICS_PATH, config["implementation"]["metrics_sha256"])
    verify_hash(Path(__file__).resolve(), config["implementation"]["verifier_sha256"])
    verify_hash(LABELS_PATH, config["data"]["labels_sha256"])
    verify_hash(DEV_PATH, config["data"]["dev_sha256"])
    if TEST_PATH.exists():
        raise ValueError("test.tsv must remain absent")
    return config


def load_gold(
    expected_rows: int, labels: tuple[str, ...]
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


def read_generation_records(
    path: Path,
    expected_rows: int,
    gold_ids: list[list[int]],
) -> list[dict[str, Any]]:
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(records) != expected_rows * len(CONDITIONS):
        raise ValueError("Generation record count is incomplete")
    expected_pairs = [
        (row_number, condition)
        for row_number in range(1, expected_rows + 1)
        for condition in (
            CONDITIONS if row_number % 2 else tuple(reversed(CONDITIONS))
        )
    ]
    for index, record in enumerate(records):
        if FORBIDDEN_RECORD_KEYS & set(record):
            raise ValueError(f"Public generation record {index + 1} contains raw fields")
        row_number, condition = expected_pairs[index]
        if (
            record["row_number"] != row_number
            or record["condition"] != condition
            or record["gold_label_ids"] != gold_ids[row_number - 1]
        ):
            raise ValueError(f"Generation record order differs at row {index + 1}")
        if record["parser_valid"]:
            decoded = json.loads(record["canonical_output"])
            if decoded != {"labels": record["predicted_labels"]}:
                raise ValueError("Canonical output does not match predicted labels")
        elif record["predicted_label_ids"] or record["predicted_labels"]:
            raise ValueError("Invalid output was not scored as an empty prediction")
    return records


def verify_condition_files(
    run_dir: Path,
    condition: str,
    condition_records: list[dict[str, Any]],
    labels: tuple[str, ...],
    gold: np.ndarray,
) -> tuple[np.ndarray, dict[str, Any], dict[str, Any]]:
    condition_dir = run_dir / condition
    prediction_gold, predicted = metric_tools.read_baseline_predictions(
        condition_dir / "predictions.csv", labels, gold.shape[0]
    )
    if not np.array_equal(prediction_gold, gold):
        raise ValueError(f"{condition} prediction gold differs from dev")
    record_prediction = metric_tools.records_to_prediction_matrix(condition_records, labels)
    if not np.array_equal(record_prediction, predicted):
        raise ValueError(f"{condition} CSV differs from generation records")
    recomputed, confusion = metric_tools.compute_metrics(gold, predicted, labels)
    generation = metric_tools.summarize_generation(condition_records)
    saved = json.loads((condition_dir / "metrics.json").read_text(encoding="utf-8"))
    assert_nested_close(saved["task"], recomputed, f"{condition}.task")
    assert_nested_close(saved["generation"], generation, f"{condition}.generation")

    with (condition_dir / "per-label-metrics.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        per_label = list(csv.DictReader(handle))
    if len(per_label) != len(labels):
        raise ValueError(f"{condition} per-label row count differs")
    for label_id, row in enumerate(per_label):
        expected = recomputed["per_label"][labels[label_id]]
        if int(row["label_id"]) != label_id or row["label"] != labels[label_id]:
            raise ValueError(f"{condition} per-label order differs")
        for field in ("precision", "recall", "f1"):
            if not math.isclose(float(row[field]), expected[field], abs_tol=1e-12):
                raise ValueError(f"{condition} per-label {field} differs")
        for field in ("support", "predicted_support"):
            if int(row[field]) != expected[field]:
                raise ValueError(f"{condition} per-label {field} differs")

    with (condition_dir / "multilabel-confusion-matrix.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        confusion_rows = list(csv.DictReader(handle))
    if len(confusion_rows) != len(labels):
        raise ValueError(f"{condition} confusion row count differs")
    for label_id, row in enumerate(confusion_rows):
        expected_values = confusion[label_id].ravel()
        actual_values = np.asarray(
            [int(row[field]) for field in ("tn", "fp", "fn", "tp")]
        )
        if row["label"] != labels[label_id] or not np.array_equal(
            actual_values, expected_values
        ):
            raise ValueError(f"{condition} confusion values differ")
    return predicted, recomputed, generation


def bootstrap_inputs(
    config: dict[str, Any],
    labels: tuple[str, ...],
    gold: np.ndarray,
    predictions: dict[str, np.ndarray],
) -> tuple[dict[str, np.ndarray], list[tuple[str, str, str]]]:
    named = {
        f"lora-{condition}": predictions[condition] for condition in CONDITIONS
    }
    comparisons = [
        ("lora-zero-minus-lora-few", "lora-zero-shot", "lora-few-shot-synthetic-3")
    ]
    exp025 = config["comparison_inputs"]["EXP-025"]
    for condition in CONDITIONS:
        path = resolve_project_path(exp025["conditions"][condition]["predictions_path"])
        verify_hash(path, exp025["conditions"][condition]["predictions_sha256"])
        baseline_gold, baseline_prediction = metric_tools.read_baseline_predictions(
            path, labels, gold.shape[0]
        )
        if not np.array_equal(baseline_gold, gold):
            raise ValueError("EXP-025 gold differs")
        named[f"frozen-{condition}"] = baseline_prediction
        comparisons.append(
            (
                f"lora-minus-frozen-{condition}",
                f"lora-{condition}",
                f"frozen-{condition}",
            )
        )
    selected_frozen = exp025["selected_condition"]
    for condition in CONDITIONS:
        comparisons.append(
            (
                f"lora-{condition}-minus-frozen-selected",
                f"lora-{condition}",
                f"frozen-{selected_frozen}",
            )
        )
    for baseline in config["comparison_inputs"]["EXP-020"]["seed_predictions"]:
        path = resolve_project_path(baseline["path"])
        verify_hash(path, baseline["sha256"])
        baseline_gold, baseline_prediction = metric_tools.read_baseline_predictions(
            path, labels, gold.shape[0]
        )
        if not np.array_equal(baseline_gold, gold):
            raise ValueError("EXP-020 gold differs")
        name = f"bert-seed-{baseline['seed']}"
        named[name] = baseline_prediction
        for condition in CONDITIONS:
            comparisons.append(
                (
                    f"lora-{condition}-minus-{name}",
                    f"lora-{condition}",
                    name,
                )
            )
    return named, comparisons


def expected_selection(
    metrics: dict[str, dict[str, Any]], threshold: float
) -> dict[str, Any]:
    zero = metrics["zero-shot"]["macro"]["f1"]
    few = metrics["few-shot-synthetic-3"]["macro"]["f1"]
    difference = zero - few
    if abs(difference) < threshold:
        selected = "zero-shot"
        reason = "practical tie; zero-shot selected for lower cost and complexity"
    elif difference > 0:
        selected = "zero-shot"
        reason = "zero-shot has higher dev Macro-F1 beyond the practical threshold"
    else:
        selected = "few-shot-synthetic-3"
        reason = "few-shot has higher dev Macro-F1 beyond the practical threshold"
    return {
        "absolute_difference": abs(difference),
        "difference_zero_minus_few": difference,
        "practical_tie": abs(difference) < threshold,
        "practical_tie_threshold": threshold,
        "reason": reason,
        "selected_condition": selected,
    }


def verify_seed(config: dict[str, Any], seed: int) -> None:
    if seed not in [int(value) for value in config["training"]["seed_schedule"]]:
        raise ValueError("Seed is outside the registered schedule")
    run_dir = resolve_project_path(config["artifacts"]["run_root"]) / f"seed-{seed}"
    verification_path = run_dir / "verification.json"
    if verification_path.exists():
        raise FileExistsError("Append-only verification already exists")
    run_path = run_dir / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    if (
        run.get("experiment_id") != EXPERIMENT_ID
        or run.get("seed") != seed
        or run.get("status") != "Completed"
        or run.get("test_split_accessed") is not False
        or run.get("validation_split_accessed") is not True
    ):
        raise ValueError("Run metadata is not a completed dev-only EXP-029 seed")
    if run.get("accessed_splits") != ["train", "dev"]:
        raise ValueError("Unexpected split access record")
    adapter_path = (
        resolve_project_path(config["artifacts"]["private_adapter_root"])
        / f"seed-{seed}"
        / "adapters.safetensors"
    )
    verify_hash(adapter_path, run["adapter"]["weights"]["sha256"])
    if run["adapter"]["lora_b_nonzero_tensors"] != run["adapter"]["lora_b_tensor_count"]:
        raise ValueError("Run reports an untrained LoRA B tensor")

    with (run_dir / "history.csv").open("r", encoding="utf-8", newline="") as handle:
        history = list(csv.DictReader(handle))
    if not history or int(history[-1]["iteration"]) != int(
        config["training"]["iterations"]
    ):
        raise ValueError("Training history does not reach the registered final iteration")
    if max(float(row["peak_memory_gb"]) for row in history) > float(
        config["resource_budget"]["peak_mlx_memory_gb_max"]
    ):
        raise ValueError("Training history exceeds the memory budget")
    if float(run["duration_seconds"]) > float(
        config["resource_budget"]["training_wall_time_hours_max_per_seed"]
    ) * 3600:
        raise ValueError("Training duration exceeds the budget")
    if float(run["dev_duration_seconds"]) > float(
        config["resource_budget"]["dev_wall_time_hours_max_per_seed"]
    ) * 3600:
        raise ValueError("Dev duration exceeds the budget")

    labels = tuple(LABELS_PATH.read_text(encoding="utf-8").splitlines())
    gold, gold_ids = load_gold(int(config["data"]["dev_rows"]), labels)
    records = read_generation_records(
        run_dir / "generation-records.jsonl", gold.shape[0], gold_ids
    )
    predictions: dict[str, np.ndarray] = {}
    metrics: dict[str, dict[str, Any]] = {}
    generation: dict[str, dict[str, Any]] = {}
    for condition in CONDITIONS:
        condition_records = [row for row in records if row["condition"] == condition]
        predictions[condition], metrics[condition], generation[condition] = (
            verify_condition_files(
                run_dir, condition, condition_records, labels, gold
            )
        )

    named, comparisons = bootstrap_inputs(config, labels, gold, predictions)
    bootstrap_config = config["evaluation"]["bootstrap"]
    recomputed_bootstrap = metric_tools.paired_bootstrap_macro_f1(
        gold,
        named,
        comparisons,
        int(bootstrap_config["replicates"]),
        int(bootstrap_config["seed"]) + seed,
        float(config["evaluation"]["practical_tie_absolute_macro_f1"]),
    )
    saved_bootstrap = json.loads(
        (run_dir / "paired-bootstrap.json").read_text(encoding="utf-8")
    )
    assert_nested_close(saved_bootstrap, recomputed_bootstrap, "paired_bootstrap")

    aggregate_path = run_dir / "aggregate-metrics.json"
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    threshold = float(config["evaluation"]["practical_tie_absolute_macro_f1"])
    selection = expected_selection(metrics, threshold)
    assert_nested_close(aggregate["selection"], selection, "selection")
    for condition in CONDITIONS:
        assert_nested_close(
            aggregate["conditions"][condition]["task"],
            metrics[condition],
            f"aggregate.{condition}.task",
        )
        assert_nested_close(
            aggregate["conditions"][condition]["generation"],
            generation[condition],
            f"aggregate.{condition}.generation",
        )
    selected = selection["selected_condition"]
    observed = metrics[selected]["macro"]["f1"] - float(
        config["comparison_inputs"]["EXP-025"]["selected_dev_macro_f1"]
    )
    expected_continue = observed >= threshold
    if aggregate["repetition_gate"]["continue_remaining_seeds"] != expected_continue:
        raise ValueError("Saved repetition gate differs from recomputation")

    required = [
        "run.json",
        "stdout.log",
        "history.csv",
        "generation-records.jsonl",
        "condition-summary.csv",
        "aggregate-metrics.json",
        "paired-bootstrap.json",
    ]
    for condition in CONDITIONS:
        required.extend(
            [
                f"{condition}/predictions.csv",
                f"{condition}/metrics.json",
                f"{condition}/per-label-metrics.csv",
                f"{condition}/multilabel-confusion-matrix.csv",
            ]
        )
    artifacts = {relative: artifact(run_dir / relative) for relative in required}
    report = {
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "continue_remaining_seeds": expected_continue if seed == 42 else None,
        "experiment_id": EXPERIMENT_ID,
        "metrics_recomputed_from_predictions": True,
        "paired_bootstrap_recomputed": True,
        "privacy_schema_passed": True,
        "resource_gates_passed": True,
        "seed": seed,
        "selected_condition": selected,
        "selected_macro_f1": metrics[selected]["macro"]["f1"],
        "selected_minus_frozen_exp_025": observed,
        "status": "Passed",
        "test_absent": not TEST_PATH.exists(),
        "test_split_accessed": False,
    }
    write_json(verification_path, report)
    print(json.dumps(report, indent=2, sort_keys=True))


def write_seed_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "seed",
        "zero_shot_macro_f1",
        "few_shot_macro_f1",
        "selected_condition",
        "selected_macro_f1",
        "training_seconds",
        "dev_seconds",
        "peak_training_memory_gb",
        "peak_dev_memory_gb",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def verify_aggregate(config: dict[str, Any]) -> None:
    run_root = resolve_project_path(config["artifacts"]["run_root"])
    output_path = run_root / "multi-seed-aggregate.json"
    verification_path = run_root / "multi-seed-verification.json"
    summary_path = run_root / "seed-summary.csv"
    if output_path.exists() or verification_path.exists() or summary_path.exists():
        raise FileExistsError("Append-only multi-seed aggregate already exists")
    seeds = [int(value) for value in config["training"]["seed_schedule"]]
    rows: list[dict[str, Any]] = []
    condition_values = {condition: [] for condition in CONDITIONS}
    verification_artifacts: dict[str, Any] = {}
    for seed in seeds:
        seed_dir = run_root / f"seed-{seed}"
        verification = seed_dir / "verification.json"
        if not verification.is_file():
            raise FileNotFoundError(f"Seed {seed} has not been independently verified")
        verified = json.loads(verification.read_text(encoding="utf-8"))
        if verified.get("status") != "Passed":
            raise ValueError(f"Seed {seed} verification failed")
        aggregate = json.loads(
            (seed_dir / "aggregate-metrics.json").read_text(encoding="utf-8")
        )
        run = json.loads((seed_dir / "run.json").read_text(encoding="utf-8"))
        for condition in CONDITIONS:
            condition_values[condition].append(
                float(aggregate["conditions"][condition]["task"]["macro"]["f1"])
            )
        selected = aggregate["selection"]["selected_condition"]
        rows.append(
            {
                "dev_seconds": run["dev_duration_seconds"],
                "few_shot_macro_f1": condition_values["few-shot-synthetic-3"][-1],
                "peak_dev_memory_gb": run["dev_peak_mlx_memory_gb"],
                "peak_training_memory_gb": run["peak_mlx_memory_gb"],
                "seed": seed,
                "selected_condition": selected,
                "selected_macro_f1": aggregate["conditions"][selected]["task"]["macro"][
                    "f1"
                ],
                "training_seconds": run["duration_seconds"],
                "zero_shot_macro_f1": condition_values["zero-shot"][-1],
            }
        )
        verification_artifacts[f"seed-{seed}"] = artifact(verification)

    summaries = {
        condition: {
            "mean_macro_f1": statistics.mean(values),
            "sample_std_macro_f1": statistics.stdev(values),
            "seeds": seeds,
            "values": values,
        }
        for condition, values in condition_values.items()
    }
    difference = (
        summaries["zero-shot"]["mean_macro_f1"]
        - summaries["few-shot-synthetic-3"]["mean_macro_f1"]
    )
    threshold = float(config["evaluation"]["practical_tie_absolute_macro_f1"])
    if abs(difference) < threshold:
        selected = "zero-shot"
        reason = "practical tie on mean Macro-F1; selected zero-shot"
    elif difference > 0:
        selected = "zero-shot"
        reason = "higher mean Macro-F1 beyond the practical threshold"
    else:
        selected = "few-shot-synthetic-3"
        reason = "higher mean Macro-F1 beyond the practical threshold"
    aggregate = {
        "conditions": summaries,
        "experiment_id": EXPERIMENT_ID,
        "seed_count": len(seeds),
        "selection": {
            "difference_zero_minus_few": difference,
            "practical_tie": abs(difference) < threshold,
            "practical_tie_threshold": threshold,
            "reason": reason,
            "selected_condition": selected,
        },
        "selected_minus_exp_020_mean": summaries[selected]["mean_macro_f1"]
        - float(config["comparison_inputs"]["EXP-020"]["dev_macro_f1_mean"]),
        "selected_minus_exp_025": summaries[selected]["mean_macro_f1"]
        - float(config["comparison_inputs"]["EXP-025"]["selected_dev_macro_f1"]),
        "status": "Verified",
    }
    write_seed_summary(summary_path, rows)
    write_json(output_path, aggregate)
    write_json(
        verification_path,
        {
            "aggregate": artifact(output_path),
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "experiment_id": EXPERIMENT_ID,
            "seed_summary": artifact(summary_path),
            "seed_verifications": verification_artifacts,
            "status": "Passed",
            "test_absent": not TEST_PATH.exists(),
        },
    )
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
