#!/usr/bin/env python3
"""Aggregate the three independently verified EXP-051 validation seeds."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
OUTPUT_DIR = SCRIPT_DIR / "runs" / "exp-051-m1-roberta-three-seed-validation"
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
SOURCE_PATHS = {
    42: SCRIPT_DIR / "runs" / "exp-051-m1-roberta-cpu-recovery" / "seed-42",
    43: SCRIPT_DIR / "runs" / "exp-051-m1-roberta-cpu" / "seed-43",
    44: SCRIPT_DIR / "runs" / "exp-051-m1-roberta-cpu" / "seed-44",
}
EXPECTED_CHECK_COUNTS = {42: 67, 43: 72, 44: 72}
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
PER_LABEL_FIELDS = ("precision", "recall", "f1", "support", "predicted_support")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def scalar_summary(values: list[float | int]) -> dict[str, Any]:
    if len(values) != 3:
        raise ValueError("EXP-051 main aggregation requires exactly three seeds")
    return {
        "values": values,
        "mean": statistics.fmean(values),
        "sample_std": statistics.stdev(values),
        "n": len(values),
    }


def extract_condition(metric: dict[str, Any]) -> dict[str, Any]:
    return {
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
        "per_label": {
            label: {field: metric["per_label"][label][field] for field in PER_LABEL_FIELDS}
            for label in LABELS
        },
    }


def aggregate_conditions(per_seed: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        field: scalar_summary([row[field] for row in per_seed]) for field in SCALAR_FIELDS
    }
    result["per_label"] = {
        label: {
            field: scalar_summary([row["per_label"][label][field] for row in per_seed])
            for field in PER_LABEL_FIELDS
        }
        for label in LABELS
    }
    return result


def load_verified_sources() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records = []
    source_records = []
    for seed, directory in SOURCE_PATHS.items():
        run_path = directory / "run.json"
        verification_path = directory / "verification.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        if run.get("seed") != seed or run.get("status") != "Completed":
            raise ValueError(f"Seed {seed} run is not a completed matching run")
        if run.get("accessed_splits") != ["train", "validation"]:
            raise PermissionError(f"Seed {seed} split boundary drift")
        if run.get("test_split_accessed") is not False:
            raise PermissionError(f"Seed {seed} accessed test")
        if verification.get("seed") != seed or verification.get("status") != "Passed":
            raise ValueError(f"Seed {seed} verification did not pass")
        if verification.get("failed_checks") != []:
            raise ValueError(f"Seed {seed} verification has failed checks")
        if verification.get("check_count") != EXPECTED_CHECK_COUNTS[seed]:
            raise ValueError(f"Seed {seed} verification check-count drift")
        if verification.get("test_split_accessed") is not False:
            raise PermissionError(f"Seed {seed} verifier records test access")
        records.append(run)
        source_records.append(
            {
                "seed": seed,
                "run": {
                    "path": project_path(run_path),
                    "sha256": sha256_file(run_path),
                },
                "verification": {
                    "path": project_path(verification_path),
                    "sha256": sha256_file(verification_path),
                    "check_count": verification["check_count"],
                },
            }
        )
    return records, source_records


def build_aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if [run["seed"] for run in runs] != [42, 43, 44]:
        raise ValueError("Expected ordered seeds 42, 43 and 44")
    per_seed = {
        str(run["seed"]): {
            "selected_epoch": run["selection"]["selected_epoch"],
            "selected_shared_threshold": run["threshold_selection"]["selected_threshold"],
            "metrics": {
                condition: extract_condition(run["metrics"][condition])
                for condition in CONDITIONS
            },
            "resource_usage": {
                "wall_seconds": run["resource_usage"]["wall_seconds"],
                "peak_process_rss_gb": run["resource_usage"]["peak_process_rss_gb"],
            },
        }
        for run in runs
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
        "resource_usage": {
            field: scalar_summary([row["resource_usage"][field] for row in rows])
            for field in ("wall_seconds", "peak_process_rss_gb")
        },
        "per_seed": per_seed,
    }


def render_report(payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate"]
    lines = [
        "# EXP-051 M1 Three-Seed Validation Aggregate",
        "",
        "- Status: `Completed; pending independent aggregate verification`",
        "- Seeds: `42, 43, 44`",
        "- Splits: `train`, `validation`",
        "- Test access: `false`",
        "- Center / dispersion: arithmetic mean / sample standard deviation (`ddof=1`)",
        "",
        "| Metric | Fixed 0.5 | Shared threshold |",
        "|---|---:|---:|",
    ]
    for label, field in (
        ("Six-label Macro-F1", "macro_f1"),
        ("Micro-F1", "micro_f1"),
        ("Weighted-F1", "weighted_f1"),
        ("Subset accuracy", "subset_accuracy"),
        ("Hamming loss", "hamming_loss"),
        ("Five-label Macro-F1 without surprise", "five_label_macro_f1_without_surprise"),
    ):
        fixed = aggregate["metrics"]["fixed_0.5"][field]
        shared = aggregate["metrics"]["shared_threshold"][field]
        lines.append(
            f"| {label} | {fixed['mean']:.6f} +/- {fixed['sample_std']:.6f} | "
            f"{shared['mean']:.6f} +/- {shared['sample_std']:.6f} |"
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
        fixed = row["metrics"]["fixed_0.5"]["macro_f1"]
        shared = row["metrics"]["shared_threshold"]["macro_f1"]
        surprise = row["metrics"]["shared_threshold"]["per_label"]["surprise"]["f1"]
        lines.append(
            f"| {seed} | {row['selected_epoch']} | {row['selected_shared_threshold']:.2f} | "
            f"{fixed:.6f} | {shared:.6f} | {surprise:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This is a validation-only M1 result. It does not authorize test access, establish "
            "TEST-READY status, or support an M1-versus-M2 conclusion. The six-label Macro-F1 "
            "remains primary; the five-label value is a registered low-support sensitivity analysis.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    if OUTPUT_DIR.exists():
        raise FileExistsError(f"Refusing to overwrite append-only output: {OUTPUT_DIR}")
    runs, sources = load_verified_sources()
    payload = {
        "schema_version": "exp-051-m1-three-seed-validation-aggregate-v1",
        "experiment_id": "EXP-051",
        "rq_id": "RQ-S1",
        "stage": "m1-three-seed-validation-aggregate",
        "status": "Completed",
        "created_at_utc": utc_now(),
        "authorization": {
            "seeds": [42, 43, 44],
            "splits": ["train", "validation"],
            "test_access": False,
            "exp_052_authorized": False,
        },
        "method": {
            "center": "arithmetic_mean",
            "dispersion": "sample_standard_deviation",
            "ddof": 1,
            "pool_predictions_across_seeds": False,
        },
        "sources": sources,
        "aggregate": build_aggregate(runs),
        "test_split_accessed": False,
        "warnings": [
            "validation_only",
            "surprise_is_low_support_and_retained_in_primary_six_label_macro_f1",
            "no_m1_vs_m2_claim_authorized",
        ],
    }
    OUTPUT_DIR.mkdir(parents=True)
    aggregate_path = OUTPUT_DIR / "aggregate.json"
    aggregate_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "REPORT.md").write_text(render_report(payload), encoding="utf-8")
    print(json.dumps({"status": "Completed", "output": project_path(aggregate_path)}))


if __name__ == "__main__":
    main()
