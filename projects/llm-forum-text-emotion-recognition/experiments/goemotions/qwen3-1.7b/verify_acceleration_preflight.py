#!/usr/bin/env python3
"""Independently verify EXP-032 train-only acceleration artifacts."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import time
from typing import Any

EXPERIMENT_ID = "EXP-032"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
CONFIG_PATH = SCRIPT_DIR / "configs" / "exp-032-acceleration-preflight.json"
RUNNER_PATH = SCRIPT_DIR / "run_acceleration_preflight.py"
RUN_ROOT = SCRIPT_DIR / "runs" / "exp-032-acceleration-preflight"
RUN_PATH = RUN_ROOT / "run.json"
TRAINING_PATH = RUN_ROOT / "training-benchmark.json"
CACHE_SUMMARY_PATH = RUN_ROOT / "kv-cache-summary.json"
CACHE_RECORDS_PATH = RUN_ROOT / "kv-cache-records.json"
VERIFICATION_PATH = RUN_ROOT / "verification.json"
TEST_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "test.tsv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_token_ids(token_ids: list[int]) -> str:
    payload = json.dumps(token_ids, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


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
    return PROJECT_ROOT / value


def verify_hash(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"Hash mismatch for {path}: {actual} != {expected}")


def assert_close(actual: float, expected: float, name: str) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12):
        raise ValueError(f"{name} differs: {actual} != {expected}")


def read_history(path: Path) -> list[dict[str, float]]:
    fields = (
        "iteration",
        "train_loss",
        "learning_rate",
        "iterations_per_second",
        "tokens_per_second",
        "trained_tokens",
        "peak_memory_gb",
    )
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != fields:
            raise ValueError(f"Unexpected history schema: {path}")
        rows = [{key: float(value) for key, value in row.items()} for row in reader]
    if not rows or not all(math.isfinite(value) for row in rows for value in row.values()):
        raise ValueError(f"Invalid or non-finite history: {path}")
    return rows


def verify_privacy(value: Any, path: str = "root") -> None:
    forbidden = {"text", "raw_text", "raw_input", "raw_output", "comment_id", "gold_labels"}
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in forbidden:
                raise ValueError(f"Public artifact contains forbidden key {path}.{key}")
            verify_privacy(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            verify_privacy(child, f"{path}[{index}]")


def verify_training(config: dict[str, Any], training: dict[str, Any]) -> dict[str, Any]:
    recomputed: dict[str, dict[str, float]] = {}
    for condition, spec in config["training_benchmark"]["conditions"].items():
        result = training["conditions"][condition]
        if result["status"] not in ("Passed", "Rejected"):
            if condition == "batch2-grad5":
                raise ValueError("Frozen baseline training condition failed")
            continue
        history_path = resolve_project_path(result["history"]["path"])
        verify_hash(history_path, result["history"]["sha256"])
        history = read_history(history_path)
        if int(history[-1]["iteration"]) != int(spec["iterations"]):
            raise ValueError(f"Iteration budget differs for {condition}")
        steady = [
            row
            for row in history
            if int(row["iteration"]) >= int(config["training_benchmark"]["steps_per_report"])
            and int(row["iteration"]) % int(config["training_benchmark"]["steps_per_report"]) == 0
        ]
        rows_per_second = statistics.median(
            row["iterations_per_second"] * int(spec["batch_size"]) for row in steady
        )
        peak = max(row["peak_memory_gb"] for row in history)
        processed = int(spec["iterations"]) * int(spec["batch_size"])
        updates = int(spec["iterations"]) // int(spec["grad_accumulation_steps"])
        if processed != int(config["training_benchmark"]["fixed_processed_rows"]):
            raise ValueError(f"Processed-row budget differs for {condition}")
        if updates != int(config["training_benchmark"]["fixed_optimizer_updates"]):
            raise ValueError(f"Optimizer-update budget differs for {condition}")
        assert_close(rows_per_second, float(result["median_steady_rows_per_second"]), f"{condition} rows/s")
        assert_close(peak, float(result["peak_mlx_memory_gb"]), f"{condition} peak memory")
        recomputed[condition] = {"peak_mlx_memory_gb": peak, "rows_per_second": rows_per_second}
    baseline = recomputed["batch2-grad5"]
    candidate = recomputed.get("batch5-grad2")
    speedup = None if candidate is None else candidate["rows_per_second"] / baseline["rows_per_second"]
    expected_selected = bool(
        candidate is not None
        and candidate["peak_mlx_memory_gb"]
        <= float(config["training_benchmark"]["candidate_selection_gate"]["peak_mlx_memory_gb_max"])
        and speedup is not None
        and speedup
        >= float(config["training_benchmark"]["candidate_selection_gate"]["minimum_steady_rows_per_second_speedup"])
    )
    if bool(training["candidate_selected"]) != expected_selected:
        raise ValueError("Training selection gate was not applied exactly")
    if speedup is not None:
        assert_close(speedup, float(training["steady_rows_per_second_speedup"]), "training speedup")
    return {
        "candidate_selected": expected_selected,
        "selected_condition": "batch5-grad2" if expected_selected else "batch2-grad5",
        "steady_rows_per_second_speedup": speedup,
    }


def verify_cache(
    config: dict[str, Any], summary: dict[str, Any], records: list[dict[str, Any]]
) -> dict[str, Any]:
    expected_rows = [
        f"train-row-{int(value)}" for value in config["inference_cache"]["sample_row_numbers"]
    ]
    if [record["sample_id"] for record in records] != expected_rows:
        raise ValueError("Cache sample IDs differ from the frozen train-only sample")
    exact = 0
    for record in records:
        baseline_ids = [int(value) for value in record["baseline_token_ids"]]
        cached_ids = [int(value) for value in record["cached_token_ids"]]
        if sha256_token_ids(baseline_ids) != record["baseline_token_ids_sha256"]:
            raise ValueError("Baseline token hash differs")
        if sha256_token_ids(cached_ids) != record["cached_token_ids_sha256"]:
            raise ValueError("Cached token hash differs")
        identical = (
            baseline_ids == cached_ids
            and record["baseline_output_sha256"] == record["cached_output_sha256"]
            and record["baseline_finish_reason"] == record["cached_finish_reason"]
        )
        if identical != bool(record["exact_token_identity"]):
            raise ValueError("Per-sample token identity flag differs")
        exact += int(identical)
    baseline_total = sum(float(record["baseline_generation_seconds"]) for record in records)
    cached_total = sum(float(record["cached_generation_seconds"]) for record in records)
    cached_end_to_end = cached_total + float(summary["cache_build_seconds"])
    speedup = baseline_total / cached_end_to_end
    assert_close(baseline_total, float(summary["baseline_generation_seconds_total"]), "baseline cache time")
    assert_close(cached_total, float(summary["cached_generation_seconds_total"]), "cached generation time")
    assert_close(cached_end_to_end, float(summary["cached_seconds_including_one_time_build"]), "cached total time")
    assert_close(speedup, float(summary["end_to_end_speedup"]), "cache speedup")
    if exact != int(summary["exact_token_identity_count"]):
        raise ValueError("Exact token identity count differs")
    expected_recommended = exact == len(records) and speedup >= float(
        config["inference_cache"]["minimum_end_to_end_speedup"]
    )
    if expected_recommended != bool(summary["recommended"]):
        raise ValueError("Cache recommendation gate was not applied exactly")
    return {
        "end_to_end_speedup": speedup,
        "exact_token_identity_count": exact,
        "exact_token_identity_rate": exact / len(records),
        "recommended": expected_recommended,
    }


def verify() -> dict[str, Any]:
    if TEST_PATH.exists():
        raise ValueError("Test split must remain absent")
    if VERIFICATION_PATH.exists():
        raise FileExistsError("Append-only EXP-032 verification already exists")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    run = json.loads(RUN_PATH.read_text(encoding="utf-8"))
    training = json.loads(TRAINING_PATH.read_text(encoding="utf-8"))
    cache_summary = json.loads(CACHE_SUMMARY_PATH.read_text(encoding="utf-8"))
    cache_records = json.loads(CACHE_RECORDS_PATH.read_text(encoding="utf-8"))
    verify_privacy(run)
    verify_privacy(training)
    verify_privacy(cache_summary)
    verify_privacy(cache_records)
    if (
        run["experiment_id"] != EXPERIMENT_ID
        or run["tier"] != "Minor"
        or run["status"] != "Completed"
        or run["accessed_splits"] != ["train"]
        or run["validation_split_accessed"] is not False
        or run["test_split_accessed"] is not False
    ):
        raise ValueError("Run metadata violates the train-only Minor contract")
    for name, path in (
        ("training_summary", TRAINING_PATH),
        ("cache_summary", CACHE_SUMMARY_PATH),
        ("cache_records", CACHE_RECORDS_PATH),
    ):
        verify_hash(path, run["artifacts"][name]["sha256"])
    for key, spec in config["implementation"].items():
        if key.endswith("_path"):
            hash_key = key.removesuffix("_path") + "_sha256"
            verify_hash(resolve_project_path(spec), config["implementation"][hash_key])
    training_check = verify_training(config, training)
    cache_check = verify_cache(config, cache_summary, cache_records)
    return {
        "accessed_splits": ["train"],
        "cache": cache_check,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": EXPERIMENT_ID,
        "privacy_check_passed": True,
        "status": "Passed",
        "test_split_accessed": False,
        "tier": "Minor",
        "training": training_check,
        "validation_split_accessed": False,
    }


def main() -> None:
    args = parse_args()
    report = verify()
    if not args.check_only:
        write_json(VERIFICATION_PATH, report)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
