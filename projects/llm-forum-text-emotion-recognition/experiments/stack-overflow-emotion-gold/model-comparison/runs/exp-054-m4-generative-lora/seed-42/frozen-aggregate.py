#!/usr/bin/env python3
"""Aggregate the three independently verified EXP-054 validation seeds."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
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


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def artifact(path: Path) -> dict[str, Any]:
    return {"path": display_path(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def require_record(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file() or path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Artifact record mismatch: {path}")
    return path


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def summarize(values: Sequence[float]) -> dict[str, Any]:
    if len(values) != 3 or not all(math.isfinite(value) for value in values):
        raise ValueError("EXP-054 aggregate requires three finite seed values")
    return {
        "values_by_seed": {str(seed): float(value) for seed, value in zip(SEEDS, values)},
        "mean": float(statistics.fmean(values)),
        "sample_std": float(statistics.stdev(values)),
        "minimum": float(min(values)), "maximum": float(max(values)),
    }


def get_path(value: dict[str, Any], keys: Sequence[str]) -> float:
    current: Any = value
    for key in keys:
        current = current[key]
    return float(current)


def metric_summary(runs: Sequence[dict[str, Any]], keys: Sequence[str]) -> dict[str, Any]:
    return summarize([get_path(run, keys) for run in runs])


def load_inputs(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    runs: list[dict[str, Any]] = []
    verifications: list[dict[str, Any]] = []
    for seed in SEEDS:
        run_dir = resolve_project(config["execution"]["public_seed_dir_pattern"].format(seed=seed))
        run_path = run_dir / "run.json"
        verification_path = run_dir / "verification.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        if run.get("status") != "Completed" or run.get("test_split_accessed"):
            raise RuntimeError(f"Seed {seed} is not aggregate-ready")
        if verification.get("status") != "Passed" or verification.get("failed_checks"):
            raise RuntimeError(f"Seed {seed} is not independently verified")
        runs.append(run)
        verifications.append(verification)
    return runs, verifications


def run(config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID or config.get("formal_execution_authorized") is not True:
        raise ValueError("EXP-054 aggregate config drift")
    for record in config["implementation"].values():
        require_record(record)
    runs, verifications = load_inputs(config)
    output_dir = resolve_project(config["execution"]["aggregate_public_dir"])
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite aggregate: {output_dir}")
    output_dir.mkdir(parents=True)

    frozen_sources: dict[str, Any] = {}
    sources = {
        "config": {"path": display_path(config_path), "bytes": config_path.stat().st_size, "sha256": sha256(config_path)},
        "aggregate": config["implementation"]["aggregate"],
        "aggregate_verifier": config["implementation"]["aggregate_verifier"],
        "aggregate_tests": config["implementation"]["aggregate_tests"],
        "protocol": config["implementation"]["protocol"],
        "authorization": config["implementation"]["authorization"],
    }
    for name, record in sources.items():
        source = require_record(record)
        destination = output_dir / f"frozen-{name}{source.suffix}"
        shutil.copy2(source, destination)
        frozen_sources[name] = artifact(destination)

    metrics = {
        "macro_precision": metric_summary(runs, ("metrics", "macro", "precision")),
        "macro_recall": metric_summary(runs, ("metrics", "macro", "recall")),
        "macro_f1": metric_summary(runs, ("metrics", "macro", "f1")),
        "micro_f1": metric_summary(runs, ("metrics", "micro_f1")),
        "weighted_f1": metric_summary(runs, ("metrics", "weighted_f1")),
        "subset_accuracy": metric_summary(runs, ("metrics", "subset_accuracy")),
        "hamming_loss": metric_summary(runs, ("metrics", "hamming_loss")),
        "five_label_macro_f1_without_surprise": metric_summary(
            runs, ("metrics", "five_label_macro_f1_without_surprise")
        ),
    }
    per_label = {
        label: {
            metric: metric_summary(runs, ("metrics", "per_label", label, metric))
            for metric in ("precision", "recall", "f1", "predicted_support")
        }
        for label in LABELS
    }
    generation = {
        "parser_valid_rate": metric_summary(runs, ("parser_and_generation", "parser_valid_rate")),
        "empty_prediction_rate": metric_summary(runs, ("metrics", "prediction_diagnostics", "empty_prediction_rate")),
        "predicted_label_cardinality_mean": metric_summary(
            runs, ("metrics", "prediction_diagnostics", "predicted_label_cardinality_mean")
        ),
        "generated_tokens_mean": metric_summary(runs, ("parser_and_generation", "generated_tokens", "mean")),
        "latency_median_seconds": metric_summary(runs, ("parser_and_generation", "latency_seconds", "median")),
        "latency_p95_seconds": metric_summary(runs, ("parser_and_generation", "latency_seconds", "p95")),
        "throughput_rows_per_second": metric_summary(runs, ("parser_and_generation", "throughput_rows_per_second")),
    }
    paired = {
        metric: metric_summary(runs, ("paired_m4_minus_m3", "metric_deltas", metric))
        for metric in (
            "macro_f1", "micro_f1", "weighted_f1", "subset_accuracy",
            "five_label_macro_f1_without_surprise",
        )
    }
    paired["component_bootstrap_macro_f1_delta"] = summarize([
        run["paired_m4_minus_m3"]["macro_f1_delta"]["point"] for run in runs
    ])
    resources = {
        "wall_seconds": metric_summary(runs, ("resources", "wall_seconds")),
        "training_seconds": metric_summary(runs, ("resources", "training_seconds")),
        "validation_generation_seconds": metric_summary(runs, ("resources", "validation_generation_seconds")),
        "peak_mlx_memory_gb": metric_summary(runs, ("resources", "peak_mlx_memory_gb")),
        "api_cost_usd_total": sum(run["resources"]["api_cost_usd"] for run in runs),
    }
    replay = {
        "passes_per_seed": 2,
        "rows_per_pass": config["execution"]["replay_rows"],
        "all_passes_fresh_process": True,
        "raw_output_matches_between_passes": {},
        "formal_raw_matches_per_pass": {},
    }
    for seed, run_value in zip(SEEDS, runs):
        run_dir = resolve_project(config["execution"]["public_seed_dir_pattern"].format(seed=seed))
        pass_one = json.loads((run_dir / "replay-pass-1.json").read_text(encoding="utf-8"))
        pass_two = json.loads((run_dir / "replay-pass-2.json").read_text(encoding="utf-8"))
        replay["raw_output_matches_between_passes"][str(seed)] = pass_two["agreement_with_pass_1"]["raw_output_matches"]
        replay["formal_raw_matches_per_pass"][str(seed)] = {
            "pass_1": pass_one["agreement_with_formal_selected_validation"]["raw_output_matches"],
            "pass_2": pass_two["agreement_with_formal_selected_validation"]["raw_output_matches"],
        }

    seed_table_path = output_dir / "seed-results.csv"
    with seed_table_path.open("w", encoding="utf-8", newline="") as target:
        fields = (
            "seed", "selected_epoch", "macro_f1", "micro_f1", "weighted_f1",
            "subset_accuracy", "five_label_macro_f1_without_surprise", "parser_valid_rate",
            "m4_minus_m3_macro_f1", "wall_hours", "peak_mlx_memory_gb",
        )
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for seed, value in zip(SEEDS, runs):
            writer.writerow({
                "seed": seed, "selected_epoch": value["selection"]["selected_epoch"],
                "macro_f1": value["metrics"]["macro"]["f1"], "micro_f1": value["metrics"]["micro_f1"],
                "weighted_f1": value["metrics"]["weighted_f1"],
                "subset_accuracy": value["metrics"]["subset_accuracy"],
                "five_label_macro_f1_without_surprise": value["metrics"]["five_label_macro_f1_without_surprise"],
                "parser_valid_rate": value["parser_and_generation"]["parser_valid_rate"],
                "m4_minus_m3_macro_f1": value["paired_m4_minus_m3"]["metric_deltas"]["macro_f1"],
                "wall_hours": value["resources"]["wall_seconds"] / 3600,
                "peak_mlx_memory_gb": value["resources"]["peak_mlx_memory_gb"],
            })

    aggregate = {
        "schema_version": "exp-054-m4-three-seed-aggregate-v1",
        "experiment_id": EXPERIMENT_ID, "rq_id": "RQ-S1", "tier": "Major",
        "stage": "m4-three-seed-validation-aggregate", "status": "Completed",
        "completed_at_utc": utc_now(), "seeds": list(SEEDS),
        "accessed_splits": ["public per-seed run records only"],
        "validation_row_level_predictions_accessed": False, "test_split_accessed": False,
        "frozen_sources": frozen_sources,
        "inputs": {
            str(seed): {
                "run": artifact(resolve_project(config["execution"]["public_seed_dir_pattern"].format(seed=seed)) / "run.json"),
                "verification": artifact(resolve_project(config["execution"]["public_seed_dir_pattern"].format(seed=seed)) / "verification.json"),
            }
            for seed in SEEDS
        },
        "metrics": metrics, "per_label": per_label, "generation": generation,
        "paired_m4_minus_m3": paired, "replay_stability": replay, "resources": resources,
        "selection_epochs": {str(seed): run_value["selection"]["selected_epoch"] for seed, run_value in zip(SEEDS, runs)},
        "claim_boundary": {
            "supported": "Three-seed validation performance, format reliability, cost, and end-to-end M4-versus-M3 formulation differences.",
            "not_supported": "An isolated causal effect of generation, a test result, or an internal emotion mechanism.",
        },
        "artifacts": {"seed_results": artifact(seed_table_path)},
    }
    aggregate_path = output_dir / "aggregate.json"
    atomic_json(aggregate_path, aggregate)
    report = "\n".join([
        "# EXP-054 M4 Three-Seed Validation", "",
        "- Status: `Completed`; independent aggregate verification pending",
        "- Test accessed: no",
        f"- Macro-F1: `{metrics['macro_f1']['mean']:.6f} +/- {metrics['macro_f1']['sample_std']:.6f}`",
        f"- Micro-F1: `{metrics['micro_f1']['mean']:.6f} +/- {metrics['micro_f1']['sample_std']:.6f}`",
        f"- Weighted-F1: `{metrics['weighted_f1']['mean']:.6f} +/- {metrics['weighted_f1']['sample_std']:.6f}`",
        f"- Strict subset accuracy: `{metrics['subset_accuracy']['mean']:.6f} +/- {metrics['subset_accuracy']['sample_std']:.6f}`",
        f"- Parser-valid rate: `{generation['parser_valid_rate']['mean']:.6f} +/- {generation['parser_valid_rate']['sample_std']:.6f}`",
        f"- M4-M3 Macro-F1 delta: `{paired['macro_f1']['mean']:+.6f} +/- {paired['macro_f1']['sample_std']:.6f}`", "",
        "M3 and M4 differ jointly in head, loss, supervision tokens, and decoding. Test remains sealed.", "",
    ])
    (output_dir / "REPORT.md").write_text(report, encoding="utf-8")
    return aggregate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    result = run(args.config.resolve())
    print(json.dumps({"status": result["status"], "macro_f1_mean": result["metrics"]["macro_f1"]["mean"]}, sort_keys=True))


if __name__ == "__main__":
    main()
