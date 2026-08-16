#!/usr/bin/env python3
"""Independently verify the EXP-054 three-seed public aggregate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any, Sequence


EXPERIMENT_ID = "EXP-054"
SEEDS = (42, 43, 44)
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-054-m4-three-seed.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_project(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def require_record(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file() or path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Artifact record mismatch: {path}")
    return path


def summarize(values: Sequence[float]) -> dict[str, Any]:
    return {
        "values_by_seed": {str(seed): float(value) for seed, value in zip(SEEDS, values)},
        "mean": float(statistics.fmean(values)), "sample_std": float(statistics.stdev(values)),
        "minimum": float(min(values)), "maximum": float(max(values)),
    }


def get_path(value: dict[str, Any], keys: Sequence[str]) -> float:
    current: Any = value
    for key in keys:
        current = current[key]
    return float(current)


def close_values(left: Any, right: Any, tolerance: float = 1e-12) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(close_values(left[key], right[key], tolerance) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(close_values(a, b, tolerance) for a, b in zip(left, right))
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=tolerance)
    return left == right


def metric(runs: Sequence[dict[str, Any]], keys: Sequence[str]) -> dict[str, Any]:
    return summarize([get_path(run, keys) for run in runs])


def verify(config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    output_dir = resolve_project(config["execution"]["aggregate_public_dir"])
    aggregate_path = output_dir / "aggregate.json"
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check("experiment identity", aggregate.get("experiment_id") == EXPERIMENT_ID)
    check("aggregate completed", aggregate.get("status") == "Completed")
    check("seed set frozen", aggregate.get("seeds") == list(SEEDS))
    check("row-level predictions not accessed", aggregate.get("validation_row_level_predictions_accessed") is False)
    check("test sealed", aggregate.get("test_split_accessed") is False)
    for name, record in aggregate["frozen_sources"].items():
        try:
            require_record(record)
            check(f"frozen source {name}", True)
        except Exception as exc:
            check(f"frozen source {name}", False, str(exc))
    runs: list[dict[str, Any]] = []
    for seed in SEEDS:
        records = aggregate["inputs"][str(seed)]
        try:
            run = json.loads(require_record(records["run"]).read_text(encoding="utf-8"))
            verification = json.loads(require_record(records["verification"]).read_text(encoding="utf-8"))
            check(f"seed {seed} run completed", run.get("status") == "Completed")
            check(f"seed {seed} verified", verification.get("status") == "Passed" and not verification.get("failed_checks"))
            check(f"seed {seed} test sealed", run.get("test_split_accessed") is False and verification.get("test_split_accessed") is False)
            runs.append(run)
        except Exception as exc:
            check(f"seed {seed} input records", False, str(exc))
    if len(runs) == 3:
        expected_metrics = {
            "macro_precision": metric(runs, ("metrics", "macro", "precision")),
            "macro_recall": metric(runs, ("metrics", "macro", "recall")),
            "macro_f1": metric(runs, ("metrics", "macro", "f1")),
            "micro_f1": metric(runs, ("metrics", "micro_f1")),
            "weighted_f1": metric(runs, ("metrics", "weighted_f1")),
            "subset_accuracy": metric(runs, ("metrics", "subset_accuracy")),
            "hamming_loss": metric(runs, ("metrics", "hamming_loss")),
            "five_label_macro_f1_without_surprise": metric(runs, ("metrics", "five_label_macro_f1_without_surprise")),
        }
        check("aggregate metrics independently recomputed", close_values(expected_metrics, aggregate["metrics"]))
        expected_per_label = {
            label: {
                name: metric(runs, ("metrics", "per_label", label, name))
                for name in ("precision", "recall", "f1", "predicted_support")
            }
            for label in LABELS
        }
        check("per-label aggregate independently recomputed", close_values(expected_per_label, aggregate["per_label"]))
        expected_generation = {
            "parser_valid_rate": metric(runs, ("parser_and_generation", "parser_valid_rate")),
            "empty_prediction_rate": metric(runs, ("metrics", "prediction_diagnostics", "empty_prediction_rate")),
            "predicted_label_cardinality_mean": metric(runs, ("metrics", "prediction_diagnostics", "predicted_label_cardinality_mean")),
            "generated_tokens_mean": metric(runs, ("parser_and_generation", "generated_tokens", "mean")),
            "latency_median_seconds": metric(runs, ("parser_and_generation", "latency_seconds", "median")),
            "latency_p95_seconds": metric(runs, ("parser_and_generation", "latency_seconds", "p95")),
            "throughput_rows_per_second": metric(runs, ("parser_and_generation", "throughput_rows_per_second")),
        }
        check("generation aggregate independently recomputed", close_values(expected_generation, aggregate["generation"]))
        expected_paired = {
            name: metric(runs, ("paired_m4_minus_m3", "metric_deltas", name))
            for name in ("macro_f1", "micro_f1", "weighted_f1", "subset_accuracy", "five_label_macro_f1_without_surprise")
        }
        expected_paired["component_bootstrap_macro_f1_delta"] = summarize([
            run["paired_m4_minus_m3"]["macro_f1_delta"]["point"] for run in runs
        ])
        check("paired aggregate independently recomputed", close_values(expected_paired, aggregate["paired_m4_minus_m3"]))
        expected_resources = {
            "wall_seconds": metric(runs, ("resources", "wall_seconds")),
            "training_seconds": metric(runs, ("resources", "training_seconds")),
            "validation_generation_seconds": metric(runs, ("resources", "validation_generation_seconds")),
            "peak_mlx_memory_gb": metric(runs, ("resources", "peak_mlx_memory_gb")),
            "api_cost_usd_total": sum(run["resources"]["api_cost_usd"] for run in runs),
        }
        check("resource aggregate independently recomputed", close_values(expected_resources, aggregate["resources"]))
        check("selection epochs independently recomputed", aggregate["selection_epochs"] == {
            str(seed): run["selection"]["selected_epoch"] for seed, run in zip(SEEDS, runs)
        })
        for seed in SEEDS:
            run_dir = resolve_project(config["execution"]["public_seed_dir_pattern"].format(seed=seed))
            pass_two = json.loads((run_dir / "replay-pass-2.json").read_text(encoding="utf-8"))
            check(f"seed {seed} replay raw stability", pass_two["agreement_with_pass_1"]["raw_output_matches"] == config["execution"]["replay_rows"])
            check(f"seed {seed} replay vector stability", pass_two["agreement_with_pass_1"]["parsed_vector_matches"] == config["execution"]["replay_rows"])
    try:
        require_record(aggregate["artifacts"]["seed_results"])
        check("seed-results artifact", True)
    except Exception as exc:
        check("seed-results artifact", False, str(exc))
    failures = [row["name"] for row in checks if not row["passed"]]
    result = {
        "schema_version": "exp-054-m4-aggregate-verification-v1",
        "experiment_id": EXPERIMENT_ID, "stage": "m4-three-seed-validation-aggregate",
        "status": "Passed" if not failures else "Failed", "verified_at_utc": utc_now(),
        "checks_total": len(checks), "checks_passed": len(checks) - len(failures),
        "failed_checks": failures, "checks": checks,
        "validation_row_level_predictions_accessed": False, "test_split_accessed": False,
    }
    output_path = output_dir / "verification.json"
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite aggregate verification: {output_path}")
    temporary = output_path.with_name(output_path.name + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(output_path)
    (output_dir / "VERIFICATION-SUMMARY.md").write_text(
        "\n".join([
            "# EXP-054 Aggregate Verification", "", f"- Status: `{result['status']}`",
            f"- Checks: `{result['checks_passed']}/{result['checks_total']}`",
            "- Row-level predictions accessed: no", "- Test accessed: no", "",
            "Failures: " + (", ".join(failures) if failures else "none"), "",
        ]),
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    result = verify(args.config.resolve())
    print(json.dumps({"status": result["status"], "checks": result["checks_total"], "failed": result["failed_checks"]}, sort_keys=True))
    if result["status"] != "Passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
