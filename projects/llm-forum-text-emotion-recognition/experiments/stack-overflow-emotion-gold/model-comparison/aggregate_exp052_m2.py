#!/usr/bin/env python3
"""Create the registered EXP-052 M2 three-seed validation aggregate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import statistics
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
CONDITIONS = ("fixed_0.5", "shared_threshold")
SCALAR_FIELDS = (
    "macro_precision",
    "macro_recall",
    "macro_f1",
    "micro_f1",
    "weighted_f1",
    "subset_accuracy",
    "hamming_loss",
    "five_label_macro_f1_without_surprise",
    "empty_prediction_rows",
    "predicted_label_cardinality_mean",
)
COMPARISON_FIELDS = (
    "macro_f1",
    "micro_f1",
    "weighted_f1",
    "subset_accuracy",
    "hamming_loss",
    "five_label_macro_f1_without_surprise",
)
PER_LABEL_FIELDS = ("precision", "recall", "f1", "support", "predicted_support")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_project(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


def project_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def validate_file(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != record["bytes"]:
        raise ValueError(f"Byte-size drift: {path}")
    if sha256_file(path) != record["sha256"]:
        raise ValueError(f"SHA-256 drift: {path}")
    return path


def scalar_summary(values: list[float | int]) -> dict[str, Any]:
    if len(values) != 3:
        raise ValueError("EXP-052 aggregate requires exactly three values")
    return {
        "values": values,
        "mean": statistics.fmean(values),
        "sample_std": statistics.stdev(values),
        "n": 3,
    }


def extract_condition(metric: dict[str, Any]) -> dict[str, Any]:
    result = {
        "macro_precision": metric["macro"]["precision"],
        "macro_recall": metric["macro"]["recall"],
        "macro_f1": metric["macro"]["f1"],
        "micro_f1": metric["micro_f1"],
        "weighted_f1": metric["weighted_f1"],
        "subset_accuracy": metric["subset_accuracy"],
        "hamming_loss": metric["hamming_loss"],
        "five_label_macro_f1_without_surprise": metric[
            "five_label_macro_f1_without_surprise"
        ],
        "empty_prediction_rows": metric["prediction_diagnostics"]["empty_prediction_rows"],
        "predicted_label_cardinality_mean": metric["prediction_diagnostics"][
            "predicted_label_cardinality_mean"
        ],
    }
    result["per_label"] = {
        label: {field: metric["per_label"][label][field] for field in PER_LABEL_FIELDS}
        for label in LABELS
    }
    return result


def aggregate_conditions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {field: scalar_summary([row[field] for row in rows]) for field in SCALAR_FIELDS}
    result["per_label"] = {
        label: {
            field: scalar_summary([row["per_label"][label][field] for row in rows])
            for field in PER_LABEL_FIELDS
        }
        for label in LABELS
    }
    return result


def validate_config(config: dict[str, Any]) -> None:
    if config.get("schema_version") != "exp-052-m2-three-seed-aggregate-config-v1":
        raise ValueError("Unexpected config schema")
    if config.get("experiment_id") != "EXP-052" or config.get("rq_id") != "RQ-S1":
        raise ValueError("Experiment identity drift")
    if config.get("stage") != "m2-three-seed-validation-aggregate":
        raise ValueError("Stage drift")
    authorization = config.get("authorization", {})
    expected = {
        "seeds": [42, 43, 44],
        "source_splits": ["train", "validation"],
        "test_access": False,
        "test_ready": False,
        "m3_authorized": False,
        "m4_authorized": False,
        "read_private_artifacts": False,
    }
    if authorization != expected:
        raise PermissionError("Authorization drift")
    method = config.get("method", {})
    if method != {
        "center": "arithmetic_mean",
        "dispersion": "sample_standard_deviation",
        "ddof": 1,
        "conditions": ["fixed_0.5", "shared_threshold"],
        "pool_predictions_across_seeds": False,
        "paired_reference": "EXP-051",
        "pair_by_seed": True,
        "inferential_test": False,
        "aggregate_resources": False,
    }:
        raise ValueError("Aggregation method drift")
    if [source.get("seed") for source in config.get("m2_sources", [])] != [42, 43, 44]:
        raise ValueError("M2 source order drift")


def validate_implementation(config: dict[str, Any]) -> None:
    for record in config["implementation"].values():
        validate_file(record)


def load_sources(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    runs: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for record in config["m2_sources"]:
        seed = record["seed"]
        run_path = validate_file(record["run"])
        verification_path = validate_file(record["verification"])
        run = json.loads(run_path.read_text(encoding="utf-8"))
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        if run.get("experiment_id") != "EXP-052" or run.get("seed") != seed:
            raise ValueError(f"Seed {seed} run identity drift")
        if run.get("status") != "Completed" or run.get("accessed_splits") != [
            "train",
            "validation",
        ]:
            raise ValueError(f"Seed {seed} run is not completed train/validation")
        if run.get("test_split_accessed") is not False:
            raise PermissionError(f"Seed {seed} accessed test")
        if verification.get("experiment_id") != "EXP-052" or verification.get("seed") != seed:
            raise ValueError(f"Seed {seed} verification identity drift")
        if verification.get("status") != "Passed" or verification.get("failed_checks") != []:
            raise ValueError(f"Seed {seed} verification did not pass")
        if verification.get("check_count") != record["verification"]["check_count"]:
            raise ValueError(f"Seed {seed} verification count drift")
        if verification.get("test_split_accessed") is not False:
            raise PermissionError(f"Seed {seed} verifier records test access")
        runs.append(run)
        sources.append(
            {
                "seed": seed,
                "run": {key: record["run"][key] for key in ("path", "bytes", "sha256")},
                "verification": {
                    key: record["verification"][key]
                    for key in ("path", "bytes", "sha256", "check_count")
                },
            }
        )
    return runs, sources


def load_m1_reference(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    record = config["m1_reference"]
    aggregate_path = validate_file(record["aggregate"])
    verification_path = validate_file(record["verification"])
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if aggregate.get("experiment_id") != "EXP-051" or aggregate.get("status") != "Completed":
        raise ValueError("M1 aggregate identity drift")
    if aggregate.get("test_split_accessed") is not False:
        raise PermissionError("M1 aggregate records test access")
    if verification.get("status") != "Passed" or verification.get("failed_checks") != []:
        raise ValueError("M1 aggregate verification did not pass")
    if verification.get("check_count") != record["verification"]["check_count"]:
        raise ValueError("M1 aggregate verification count drift")
    if verification.get("test_split_accessed") is not False:
        raise PermissionError("M1 aggregate verifier records test access")
    source = {
        "aggregate": {key: record["aggregate"][key] for key in ("path", "bytes", "sha256")},
        "verification": {
            key: record["verification"][key]
            for key in ("path", "bytes", "sha256", "check_count")
        },
    }
    return aggregate, source


def build_aggregate(runs: list[dict[str, Any]], m1: dict[str, Any]) -> dict[str, Any]:
    if [run["seed"] for run in runs] != [42, 43, 44]:
        raise ValueError("Expected ordered seeds 42, 43 and 44")
    per_seed: dict[str, Any] = {}
    for run in runs:
        seed = str(run["seed"])
        execution_mode = (
            "full_qwen_feature_extraction_and_head_training"
            if run.get("feature_extraction_performed") is True
            else "verified_cache_reuse_head_only"
        )
        per_seed[seed] = {
            "selected_epoch": run["selection"]["selected_epoch"],
            "selected_shared_threshold": run["threshold_selection"]["selected_threshold"],
            "metrics": {
                condition: extract_condition(run["metrics"][condition])
                for condition in CONDITIONS
            },
            "resource_usage": dict(run["resource_usage"]),
            "execution_mode": execution_mode,
        }
    rows = list(per_seed.values())
    paired_deltas: dict[str, Any] = {}
    for condition in CONDITIONS:
        seed_deltas: dict[str, Any] = {}
        for seed, row in per_seed.items():
            m1_metrics = m1["aggregate"]["per_seed"][seed]["metrics"][condition]
            seed_deltas[seed] = {
                field: row["metrics"][condition][field] - m1_metrics[field]
                for field in COMPARISON_FIELDS
            }
        paired_deltas[condition] = {
            "per_seed": seed_deltas,
            "summary": {
                field: scalar_summary([seed_deltas[str(seed)][field] for seed in (42, 43, 44)])
                for field in COMPARISON_FIELDS
            },
        }
    return {
        "selected_epoch": scalar_summary([row["selected_epoch"] for row in rows]),
        "selected_shared_threshold": scalar_summary(
            [row["selected_shared_threshold"] for row in rows]
        ),
        "metrics": {
            condition: aggregate_conditions([row["metrics"][condition] for row in rows])
            for condition in CONDITIONS
        },
        "paired_m2_minus_m1": paired_deltas,
        "per_seed": per_seed,
        "resource_aggregation": {
            "performed": False,
            "reason": "seed_42_includes_feature_extraction_while_seeds_43_44_are_cache_only",
        },
    }


def render_summary(summary: dict[str, Any]) -> str:
    return f"{summary['mean']:.6f} +/- {summary['sample_std']:.6f}"


def render_report(payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate"]
    lines = [
        "# EXP-052 M2 Three-Seed Validation Aggregate",
        "",
        "- Status: `Completed; pending independent aggregate verification`",
        "- Seeds: `42, 43, 44`",
        "- Source splits: `train`, `validation`",
        "- Test access: `false`",
        "- Center / dispersion: arithmetic mean / sample standard deviation (`ddof=1`)",
        "- Predictions pooled across seeds: `false`",
        "",
        "| Metric | Fixed 0.5 | Per-seed shared threshold |",
        "|---|---:|---:|",
    ]
    for label, field in (
        ("Six-label Macro-F1", "macro_f1"),
        ("Micro-F1", "micro_f1"),
        ("Weighted-F1", "weighted_f1"),
        ("Strict subset accuracy", "subset_accuracy"),
        ("Hamming loss", "hamming_loss"),
        ("Five-label Macro-F1 without surprise", "five_label_macro_f1_without_surprise"),
    ):
        fixed = aggregate["metrics"]["fixed_0.5"][field]
        shared = aggregate["metrics"]["shared_threshold"][field]
        lines.append(f"| {label} | {render_summary(fixed)} | {render_summary(shared)} |")
    lines.extend(
        [
            "",
            "## Seed-Level Primary Results",
            "",
            "| Seed | Epoch | Threshold | Fixed Macro-F1 | Shared Macro-F1 | Surprise F1 | Mode |",
            "|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for seed, row in aggregate["per_seed"].items():
        lines.append(
            f"| {seed} | {row['selected_epoch']} | {row['selected_shared_threshold']:.2f} | "
            f"{row['metrics']['fixed_0.5']['macro_f1']:.6f} | "
            f"{row['metrics']['shared_threshold']['macro_f1']:.6f} | "
            f"{row['metrics']['shared_threshold']['per_label']['surprise']['f1']:.6f} | "
            f"{row['execution_mode']} |"
        )
    lines.extend(
        [
            "",
            "## Matched M2 Minus M1",
            "",
            "| Metric | Fixed 0.5 delta | Per-seed shared-threshold delta |",
            "|---|---:|---:|",
        ]
    )
    for label, field in (
        ("Six-label Macro-F1", "macro_f1"),
        ("Micro-F1", "micro_f1"),
        ("Weighted-F1", "weighted_f1"),
        ("Strict subset accuracy", "subset_accuracy"),
        ("Hamming loss", "hamming_loss"),
        ("Five-label Macro-F1 without surprise", "five_label_macro_f1_without_surprise"),
    ):
        fixed = aggregate["paired_m2_minus_m1"]["fixed_0.5"]["summary"][field]
        shared = aggregate["paired_m2_minus_m1"]["shared_threshold"]["summary"][field]
        lines.append(f"| {label} | {render_summary(fixed)} | {render_summary(shared)} |")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This is a validation-only M2 family result. No row-level predictions were read or "
            "pooled. Shared-threshold comparisons use each model's already frozen validation "
            "operating point; fixed 0.5 is the calibration-independent companion. The paired "
            "M2-minus-M1 values are descriptive for three matched seeds and do not authorize "
            "significance claims. Heterogeneous execution paths are reported per seed and are "
            "not averaged into a family cost. Test, TEST-READY, EXP-053 and EXP-054 remain sealed.",
            "",
        ]
    )
    return "\n".join(lines)


def freeze_implementation(config: dict[str, Any], config_path: Path, output_dir: Path) -> None:
    copies = {
        config_path: "frozen-config.json",
        resolve_project(config["implementation"]["protocol"]["path"]): "frozen-protocol.md",
        resolve_project(config["implementation"]["runner"]["path"]): "frozen-runner.py",
        resolve_project(config["implementation"]["verifier"]["path"]): "frozen-verifier.py",
        resolve_project(config["implementation"]["tests"]["path"]): "frozen-tests.py",
    }
    for source, name in copies.items():
        shutil.copyfile(source, output_dir / name)


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_config(config)
    validate_implementation(config)
    output_dir = resolve_project(config["output_dir"])
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite append-only output: {output_dir}")
    runs, sources = load_sources(config)
    m1, m1_source = load_m1_reference(config)
    payload = {
        "schema_version": "exp-052-m2-three-seed-validation-aggregate-v1",
        "experiment_id": "EXP-052",
        "tier": "Major",
        "rq_id": "RQ-S1",
        "stage": "m2-three-seed-validation-aggregate",
        "status": "Completed",
        "created_at_utc": utc_now(),
        "authorization": dict(config["authorization"]),
        "method": dict(config["method"]),
        "config": {
            "path": project_path(config_path),
            "bytes": config_path.stat().st_size,
            "sha256": sha256_file(config_path),
        },
        "implementation": config["implementation"],
        "m2_sources": sources,
        "m1_reference": m1_source,
        "aggregate": build_aggregate(runs, m1),
        "test_split_accessed": False,
        "warnings": [
            "validation_only",
            "no_row_level_predictions_read_or_pooled",
            "shared_thresholds_are_model_specific_validation_operating_points",
            "paired_deltas_are_descriptive_for_n_3",
            "surprise_is_retained_in_primary_six_label_macro_f1",
            "resource_paths_are_heterogeneous_and_not_aggregated",
            "test_m3_m4_remain_sealed",
        ],
    }
    output_dir.mkdir(parents=True)
    freeze_implementation(config, config_path, output_dir)
    aggregate_path = output_dir / "aggregate.json"
    aggregate_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "REPORT.md").write_text(render_report(payload), encoding="utf-8")
    print(json.dumps({"status": "Completed", "output": project_path(aggregate_path)}))


if __name__ == "__main__":
    main()
