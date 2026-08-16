#!/usr/bin/env python3
"""Create the registered EXP-053 M3 three-seed validation aggregate."""

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
RESOURCE_FIELDS = (
    "wall_seconds",
    "training_and_epoch_validation_seconds",
    "peak_mlx_memory_gb",
    "peak_process_rss_gb",
    "model_load_seconds",
    "tokenization_seconds",
    "api_cost_usd",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
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


def public_record(record: dict[str, Any], *extra: str) -> dict[str, Any]:
    return {
        key: record[key]
        for key in ("path", "bytes", "sha256", *extra)
    }


def scalar_summary(values: list[float | int]) -> dict[str, Any]:
    if len(values) != 3:
        raise ValueError("EXP-053 aggregate requires exactly three values")
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
    if config.get("schema_version") != "exp-053-m3-three-seed-aggregate-config-v1":
        raise ValueError("Unexpected config schema")
    if config.get("experiment_id") != "EXP-053" or config.get("rq_id") != "RQ-S1":
        raise ValueError("Experiment identity drift")
    if config.get("stage") != "m3-three-seed-validation-aggregate":
        raise ValueError("Stage drift")
    expected_authorization = {
        "authorized_at": "2026-08-15",
        "basis": "User instructed the agent to execute the next registered step after seed 44.",
        "seeds": [42, 43, 44],
        "source_splits": ["train", "validation"],
        "m3_aggregate_authorized": True,
        "m3_training_authorized": False,
        "test_access": False,
        "test_ready": False,
        "m4_authorized": False,
        "error_analysis_authorized": False,
        "read_private_artifacts": False,
    }
    if config.get("authorization") != expected_authorization:
        raise PermissionError("Authorization drift")
    expected_method = {
        "center": "arithmetic_mean",
        "dispersion": "sample_standard_deviation",
        "ddof": 1,
        "conditions": ["fixed_0.5", "shared_threshold"],
        "pool_predictions_across_seeds": False,
        "paired_references": ["EXP-051", "EXP-052"],
        "pair_by_seed": True,
        "inferential_test": False,
        "aggregate_m3_resources": True,
        "cross_model_resource_comparison": False,
    }
    if config.get("method") != expected_method:
        raise ValueError("Aggregation method drift")
    if [source.get("seed") for source in config.get("m3_sources", [])] != [42, 43, 44]:
        raise ValueError("M3 source order drift")


def validate_implementation(config: dict[str, Any]) -> None:
    for record in config["implementation"].values():
        validate_file(record)


def verification_count(payload: dict[str, Any]) -> int | None:
    return payload.get("checks_total", payload.get("check_count"))


def load_sources(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    runs: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for record in config["m3_sources"]:
        seed = record["seed"]
        run_path = validate_file(record["run"])
        verification_path = validate_file(record["verification"])
        run = json.loads(run_path.read_text(encoding="utf-8"))
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        if run.get("experiment_id") != "EXP-053" or run.get("training", {}).get("seed") != seed:
            raise ValueError(f"Seed {seed} run identity drift")
        if run.get("status") != "Completed" or run.get("accessed_splits") != [
            "train",
            "validation",
        ]:
            raise ValueError(f"Seed {seed} run is not completed train/validation")
        if run.get("validation_split_accessed") is not True:
            raise ValueError(f"Seed {seed} did not record validation access")
        if run.get("test_split_accessed") is not False:
            raise PermissionError(f"Seed {seed} accessed test")
        if verification.get("experiment_id") != "EXP-053":
            raise ValueError(f"Seed {seed} verification identity drift")
        if verification.get("stage") != f"seed-{seed}-train-validation":
            raise ValueError(f"Seed {seed} verification stage drift")
        if verification.get("status") != "Passed" or verification.get("failed_checks") != []:
            raise ValueError(f"Seed {seed} verification did not pass")
        expected_count = record["verification"]["check_count"]
        if verification_count(verification) != expected_count:
            raise ValueError(f"Seed {seed} verification count drift")
        if len(verification.get("checks", [])) != expected_count:
            raise ValueError(f"Seed {seed} verification list drift")
        if any(check.get("passed") is not True for check in verification["checks"]):
            raise ValueError(f"Seed {seed} verification contains a failed check")
        if verification.get("test_split_accessed") is not False:
            raise PermissionError(f"Seed {seed} verifier records test access")
        if verification.get("selected_checkpoint_probability_replay_max_abs_error") != 0.0:
            raise ValueError(f"Seed {seed} checkpoint replay drift")

        source = {
            "seed": seed,
            "run": public_record(record["run"]),
            "verification": public_record(record["verification"], "check_count"),
        }
        if "prior_failed_verification" in record:
            failed_path = validate_file(record["prior_failed_verification"])
            failed_payload = json.loads(failed_path.read_text(encoding="utf-8"))
            if failed_payload.get("status") != "Failed":
                raise ValueError("Seed 42 prior verifier history drift")
            source["prior_failed_verification"] = public_record(
                record["prior_failed_verification"], "check_count"
            )
        if "documentation_correction" in record:
            correction_path = validate_file(record["documentation_correction"])
            correction = correction_path.read_text(encoding="utf-8")
            if "Seed 44 is the third authorized EXP-053 M3 seed." not in correction:
                raise ValueError("Seed 44 correction content drift")
            source["documentation_correction"] = public_record(
                record["documentation_correction"]
            )
        runs.append(run)
        sources.append(source)
    return runs, sources


def load_reference(
    config: dict[str, Any], key: str, experiment_id: str, check_count: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    record = config[key]
    aggregate_path = validate_file(record["aggregate"])
    verification_path = validate_file(record["verification"])
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if aggregate.get("experiment_id") != experiment_id or aggregate.get("status") != "Completed":
        raise ValueError(f"{experiment_id} aggregate identity drift")
    if aggregate.get("test_split_accessed") is not False:
        raise PermissionError(f"{experiment_id} aggregate records test access")
    if verification.get("status") != "Passed" or verification.get("failed_checks") != []:
        raise ValueError(f"{experiment_id} aggregate verification did not pass")
    if verification.get("check_count") != check_count:
        raise ValueError(f"{experiment_id} verification count drift")
    if verification.get("test_split_accessed") is not False:
        raise PermissionError(f"{experiment_id} verifier records test access")
    if list(aggregate.get("aggregate", {}).get("per_seed", {})) != ["42", "43", "44"]:
        raise ValueError(f"{experiment_id} per-seed order drift")
    return aggregate, {
        "aggregate": public_record(record["aggregate"]),
        "verification": public_record(record["verification"], "check_count"),
    }


def paired_summary(
    per_seed: dict[str, Any], reference: dict[str, Any]
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for condition in CONDITIONS:
        seed_deltas: dict[str, Any] = {}
        for seed, row in per_seed.items():
            reference_metrics = reference["aggregate"]["per_seed"][seed]["metrics"][condition]
            seed_deltas[seed] = {
                field: row["metrics"][condition][field] - reference_metrics[field]
                for field in COMPARISON_FIELDS
            }
        result[condition] = {
            "per_seed": seed_deltas,
            "summary": {
                field: scalar_summary(
                    [seed_deltas[str(seed)][field] for seed in (42, 43, 44)]
                )
                for field in COMPARISON_FIELDS
            },
        }
    return result


def build_aggregate(
    runs: list[dict[str, Any]], m1: dict[str, Any], m2: dict[str, Any]
) -> dict[str, Any]:
    if [run["training"]["seed"] for run in runs] != [42, 43, 44]:
        raise ValueError("Expected ordered seeds 42, 43 and 44")
    per_seed: dict[str, Any] = {}
    for run in runs:
        seed = str(run["training"]["seed"])
        per_seed[seed] = {
            "selected_epoch": run["selection"]["selected_epoch"],
            "selected_shared_threshold": run["threshold_selection"]["selected_threshold"],
            "metrics": {
                condition: extract_condition(run["metrics"][condition])
                for condition in CONDITIONS
            },
            "resources": {field: run["resources"][field] for field in RESOURCE_FIELDS},
        }
    rows = list(per_seed.values())
    return {
        "selected_epoch": scalar_summary([row["selected_epoch"] for row in rows]),
        "selected_shared_threshold": scalar_summary(
            [row["selected_shared_threshold"] for row in rows]
        ),
        "metrics": {
            condition: aggregate_conditions([row["metrics"][condition] for row in rows])
            for condition in CONDITIONS
        },
        "paired_m3_minus_m1": paired_summary(per_seed, m1),
        "paired_m3_minus_m2": paired_summary(per_seed, m2),
        "resources": {
            field: scalar_summary([row["resources"][field] for row in rows])
            for field in RESOURCE_FIELDS
        },
        "per_seed": per_seed,
    }


def render_summary(summary: dict[str, Any]) -> str:
    return f"{summary['mean']:.6f} +/- {summary['sample_std']:.6f}"


def render_report(payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate"]
    lines = [
        "# EXP-053 M3 Three-Seed Validation Aggregate",
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
        lines.append(
            f"| {label} | {render_summary(aggregate['metrics']['fixed_0.5'][field])} | "
            f"{render_summary(aggregate['metrics']['shared_threshold'][field])} |"
        )
    lines.extend(
        [
            "",
            "## Seed-Level Primary Results",
            "",
            "| Seed | Epoch | Threshold | Fixed Macro-F1 | Shared Macro-F1 | Surprise F1 |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for seed, row in aggregate["per_seed"].items():
        lines.append(
            f"| {seed} | {row['selected_epoch']} | {row['selected_shared_threshold']:.2f} | "
            f"{row['metrics']['fixed_0.5']['macro_f1']:.6f} | "
            f"{row['metrics']['shared_threshold']['macro_f1']:.6f} | "
            f"{row['metrics']['shared_threshold']['per_label']['surprise']['f1']:.6f} |"
        )
    for title, key in (
        ("Matched M3 Minus M2", "paired_m3_minus_m2"),
        ("Seed-Matched Descriptive M3 Minus M1", "paired_m3_minus_m1"),
    ):
        lines.extend(
            [
                "",
                f"## {title}",
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
            lines.append(
                f"| {label} | {render_summary(aggregate[key]['fixed_0.5']['summary'][field])} | "
                f"{render_summary(aggregate[key]['shared_threshold']['summary'][field])} |"
            )
    lines.extend(
        [
            "",
            "## M3 Resources",
            "",
            f"- Wall time: {render_summary(aggregate['resources']['wall_seconds'])} seconds",
            f"- Peak MLX memory: {render_summary(aggregate['resources']['peak_mlx_memory_gb'])} GB",
            f"- API cost: {render_summary(aggregate['resources']['api_cost_usd'])} USD",
            "",
            "## Boundary",
            "",
            "This is a validation-only M3 family result. No row-level predictions were read or "
            "pooled. Shared-threshold comparisons use each model's already frozen validation "
            "operating point; fixed 0.5 is the calibration-independent companion. M3-minus-M2 "
            "and M3-minus-M1 values are descriptive for three seed-matched runs; no p-value, "
            "confidence interval, or significance claim is authorized. M3 resources are "
            "summarized only within the homogeneous M3 execution path and are not a cross-model cost comparison. "
            "Surprise has seven validation positives, so its stability remains "
            "uncertain. Test, TEST-READY, EXP-054 and error analysis remain sealed.",
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
    m1, m1_source = load_reference(config, "m1_reference", "EXP-051", 53)
    m2, m2_source = load_reference(config, "m2_reference", "EXP-052", 85)
    aggregate = build_aggregate(runs, m1, m2)
    if args.check:
        print(
            json.dumps(
                {
                    "status": "Ready",
                    "seeds": [42, 43, 44],
                    "shared_macro_f1": aggregate["metrics"]["shared_threshold"]["macro_f1"],
                    "test_accessed": False,
                }
            )
        )
        return
    payload = {
        "schema_version": "exp-053-m3-three-seed-validation-aggregate-v1",
        "experiment_id": "EXP-053",
        "tier": "Major",
        "rq_id": "RQ-S1",
        "stage": "m3-three-seed-validation-aggregate",
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
        "m3_sources": sources,
        "m1_reference": m1_source,
        "m2_reference": m2_source,
        "aggregate": aggregate,
        "test_split_accessed": False,
        "warnings": [
            "validation_only",
            "no_row_level_predictions_read_or_pooled",
            "shared_thresholds_are_model_specific_validation_operating_points",
            "paired_deltas_are_descriptive_for_n_3",
            "surprise_has_seven_validation_positives",
            "m3_resources_are_not_a_cross_model_cost_comparison",
            "test_m4_error_analysis_remain_sealed",
        ],
    }
    output_dir.mkdir(parents=True)
    freeze_implementation(config, config_path, output_dir)
    aggregate_path = output_dir / "aggregate.json"
    aggregate_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "REPORT.md").write_text(render_report(payload), encoding="utf-8")
    print(json.dumps({"status": "Completed", "output": project_path(aggregate_path)}))


if __name__ == "__main__":
    main()
