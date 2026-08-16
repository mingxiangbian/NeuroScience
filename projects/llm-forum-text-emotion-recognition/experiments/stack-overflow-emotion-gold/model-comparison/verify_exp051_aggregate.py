#!/usr/bin/env python3
"""Independently verify the EXP-051 three-seed validation aggregate."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
OUTPUT_DIR = SCRIPT_DIR / "runs" / "exp-051-m1-roberta-three-seed-validation"
AGGREGATE_PATH = OUTPUT_DIR / "aggregate.json"
VERIFICATION_PATH = OUTPUT_DIR / "verification.json"
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
PER_LABEL_FIELDS = ("precision", "recall", "f1", "support", "predicted_support")
EXPECTED_CHECK_COUNTS = {42: 67, 43: 72, 44: 72}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_project(recorded: str) -> Path:
    path = Path(recorded)
    return path if path.is_absolute() else PROJECT_ROOT / path


def independent_summary(values: list[float | int]) -> dict[str, Any]:
    if len(values) != 3:
        raise ValueError("Expected exactly three values")
    mean = sum(values) / 3
    sample_variance = sum((value - mean) ** 2 for value in values) / 2
    return {
        "values": values,
        "mean": mean,
        "sample_std": math.sqrt(sample_variance),
        "n": 3,
    }


def extract_metric(metric: dict[str, Any]) -> dict[str, Any]:
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


def independently_aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    per_seed = {
        str(run["seed"]): {
            "selected_epoch": run["selection"]["selected_epoch"],
            "selected_shared_threshold": run["threshold_selection"]["selected_threshold"],
            "metrics": {
                condition: extract_metric(run["metrics"][condition])
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
    aggregate_metrics: dict[str, Any] = {}
    for condition in CONDITIONS:
        condition_rows = [row["metrics"][condition] for row in rows]
        condition_result = {
            field: independent_summary([row[field] for row in condition_rows])
            for field in SCALAR_FIELDS
        }
        condition_result["per_label"] = {
            label: {
                field: independent_summary(
                    [row["per_label"][label][field] for row in condition_rows]
                )
                for field in PER_LABEL_FIELDS
            }
            for label in LABELS
        }
        aggregate_metrics[condition] = condition_result
    return {
        "selected_epoch": independent_summary([row["selected_epoch"] for row in rows]),
        "selected_shared_threshold": independent_summary(
            [row["selected_shared_threshold"] for row in rows]
        ),
        "metrics": aggregate_metrics,
        "resource_usage": {
            field: independent_summary([row["resource_usage"][field] for row in rows])
            for field in ("wall_seconds", "peak_process_rss_gb")
        },
        "per_seed": per_seed,
    }


def values_match(left: Any, right: Any, tolerance: float = 1e-12) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            values_match(left[key], right[key], tolerance) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            values_match(a, b, tolerance) for a, b in zip(left, right)
        )
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=tolerance)
    return left == right


def main() -> None:
    if VERIFICATION_PATH.exists():
        raise FileExistsError(f"Refusing to overwrite append-only output: {VERIFICATION_PATH}")
    payload = json.loads(AGGREGATE_PATH.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check("schema", payload.get("schema_version") == "exp-051-m1-three-seed-validation-aggregate-v1")
    check("experiment identity", payload.get("experiment_id") == "EXP-051")
    check("status", payload.get("status") == "Completed")
    authorization = payload.get("authorization", {})
    check("seed set", authorization.get("seeds") == [42, 43, 44])
    check("split boundary", authorization.get("splits") == ["train", "validation"])
    check("test sealed", authorization.get("test_access") is False)
    check("EXP-052 sealed", authorization.get("exp_052_authorized") is False)
    check("aggregate test flag", payload.get("test_split_accessed") is False)
    method = payload.get("method", {})
    check("arithmetic mean", method.get("center") == "arithmetic_mean")
    check("sample standard deviation", method.get("dispersion") == "sample_standard_deviation")
    check("ddof one", method.get("ddof") == 1)
    check("no pooled predictions", method.get("pool_predictions_across_seeds") is False)

    sources = payload.get("sources", [])
    check("three source records", [source.get("seed") for source in sources] == [42, 43, 44])
    runs = []
    for source in sources:
        seed = source["seed"]
        run_path = resolve_project(source["run"]["path"])
        verification_path = resolve_project(source["verification"]["path"])
        check(f"seed {seed} run exists", run_path.is_file())
        check(f"seed {seed} verification exists", verification_path.is_file())
        check(f"seed {seed} run hash", sha256_file(run_path) == source["run"]["sha256"])
        check(
            f"seed {seed} verification hash",
            sha256_file(verification_path) == source["verification"]["sha256"],
        )
        run = json.loads(run_path.read_text(encoding="utf-8"))
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        check(f"seed {seed} run identity", run.get("seed") == seed)
        check(f"seed {seed} completed", run.get("status") == "Completed")
        check(f"seed {seed} train-validation only", run.get("accessed_splits") == ["train", "validation"])
        check(f"seed {seed} test sealed", run.get("test_split_accessed") is False)
        check(f"seed {seed} verification passed", verification.get("status") == "Passed")
        check(f"seed {seed} no failed checks", verification.get("failed_checks") == [])
        check(
            f"seed {seed} verification count",
            verification.get("check_count") == EXPECTED_CHECK_COUNTS[seed],
        )
        check(f"seed {seed} verifier test sealed", verification.get("test_split_accessed") is False)
        runs.append(run)

    recomputed = independently_aggregate(runs)
    check("independent aggregate replay", values_match(payload.get("aggregate"), recomputed))
    report_path = OUTPUT_DIR / "REPORT.md"
    report = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    check("report exists", report_path.is_file())
    check("report states validation boundary", "validation-only M1 result" in report)
    check("report retains surprise", "Surprise F1" in report and "six-label Macro-F1" in report)

    failed = [item["name"] for item in checks if not item["passed"]]
    result = {
        "schema_version": "exp-051-m1-three-seed-validation-verification-v1",
        "experiment_id": "EXP-051",
        "status": "Passed" if not failed else "Failed",
        "verified_at_utc": utc_now(),
        "check_count": len(checks),
        "checks": checks,
        "failed_checks": failed,
        "aggregate_sha256": sha256_file(AGGREGATE_PATH),
        "recomputed_primary": {
            condition: recomputed["metrics"][condition]["macro_f1"]
            for condition in CONDITIONS
        },
        "test_split_accessed": False,
    }
    VERIFICATION_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "check_count": len(checks), "failed": failed}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
