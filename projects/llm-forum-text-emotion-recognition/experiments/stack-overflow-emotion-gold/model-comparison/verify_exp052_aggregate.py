#!/usr/bin/env python3
"""Independently verify the EXP-052 M2 three-seed validation aggregate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
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
    parser.add_argument("--run-dir", type=Path, required=True)
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


def independent_summary(values: list[float | int]) -> dict[str, Any]:
    if len(values) != 3:
        raise ValueError("Expected exactly three values")
    mean = sum(values) / 3
    variance = sum((value - mean) ** 2 for value in values) / 2
    return {"values": values, "mean": mean, "sample_std": math.sqrt(variance), "n": 3}


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


def independently_aggregate(runs: list[dict[str, Any]], m1: dict[str, Any]) -> dict[str, Any]:
    per_seed: dict[str, Any] = {}
    for run in runs:
        seed = str(run["seed"])
        per_seed[seed] = {
            "selected_epoch": run["selection"]["selected_epoch"],
            "selected_shared_threshold": run["threshold_selection"]["selected_threshold"],
            "metrics": {
                condition: extract_metric(run["metrics"][condition])
                for condition in CONDITIONS
            },
            "resource_usage": dict(run["resource_usage"]),
            "execution_mode": (
                "full_qwen_feature_extraction_and_head_training"
                if run.get("feature_extraction_performed") is True
                else "verified_cache_reuse_head_only"
            ),
        }
    rows = list(per_seed.values())
    aggregate_metrics: dict[str, Any] = {}
    for condition in CONDITIONS:
        metric_rows = [row["metrics"][condition] for row in rows]
        condition_result = {
            field: independent_summary([row[field] for row in metric_rows])
            for field in SCALAR_FIELDS
        }
        condition_result["per_label"] = {
            label: {
                field: independent_summary(
                    [row["per_label"][label][field] for row in metric_rows]
                )
                for field in PER_LABEL_FIELDS
            }
            for label in LABELS
        }
        aggregate_metrics[condition] = condition_result
    paired: dict[str, Any] = {}
    for condition in CONDITIONS:
        per_seed_delta: dict[str, Any] = {}
        for seed, row in per_seed.items():
            m1_metric = m1["aggregate"]["per_seed"][seed]["metrics"][condition]
            per_seed_delta[seed] = {
                field: row["metrics"][condition][field] - m1_metric[field]
                for field in COMPARISON_FIELDS
            }
        paired[condition] = {
            "per_seed": per_seed_delta,
            "summary": {
                field: independent_summary(
                    [per_seed_delta[str(seed)][field] for seed in (42, 43, 44)]
                )
                for field in COMPARISON_FIELDS
            },
        }
    return {
        "selected_epoch": independent_summary([row["selected_epoch"] for row in rows]),
        "selected_shared_threshold": independent_summary(
            [row["selected_shared_threshold"] for row in rows]
        ),
        "metrics": aggregate_metrics,
        "paired_m2_minus_m1": paired,
        "per_seed": per_seed,
        "resource_aggregation": {
            "performed": False,
            "reason": "seed_42_includes_feature_extraction_while_seeds_43_44_are_cache_only",
        },
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
    args = parse_args()
    config_path = args.config.resolve()
    run_dir = args.run_dir.resolve()
    verification_path = run_dir / "verification.json"
    if verification_path.exists():
        raise FileExistsError(f"Refusing to overwrite append-only output: {verification_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    payload = json.loads((run_dir / "aggregate.json").read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check("schema", payload.get("schema_version") == "exp-052-m2-three-seed-validation-aggregate-v1")
    check("experiment identity", payload.get("experiment_id") == "EXP-052")
    check("tier", payload.get("tier") == "Major")
    check("stage", payload.get("stage") == "m2-three-seed-validation-aggregate")
    check("status", payload.get("status") == "Completed")
    check("config hash", payload.get("config", {}).get("sha256") == sha256_file(config_path))
    check(
        "frozen config",
        sha256_file(run_dir / "frozen-config.json") == sha256_file(config_path),
    )
    authorization = payload.get("authorization", {})
    check("seed set", authorization.get("seeds") == [42, 43, 44])
    check("split boundary", authorization.get("source_splits") == ["train", "validation"])
    check("test sealed", authorization.get("test_access") is False)
    check("TEST-READY sealed", authorization.get("test_ready") is False)
    check("M3 sealed", authorization.get("m3_authorized") is False)
    check("M4 sealed", authorization.get("m4_authorized") is False)
    check("private artifacts sealed", authorization.get("read_private_artifacts") is False)
    check("aggregate test flag", payload.get("test_split_accessed") is False)
    method = payload.get("method", {})
    check("arithmetic mean", method.get("center") == "arithmetic_mean")
    check("sample standard deviation", method.get("dispersion") == "sample_standard_deviation")
    check("ddof one", method.get("ddof") == 1)
    check("no pooled predictions", method.get("pool_predictions_across_seeds") is False)
    check("paired by seed", method.get("pair_by_seed") is True)
    check("no inferential test", method.get("inferential_test") is False)
    check("resources not aggregated", method.get("aggregate_resources") is False)

    for name, record in config["implementation"].items():
        path = resolve_project(record["path"])
        check(f"implementation exists: {name}", path.is_file())
        check(f"implementation bytes: {name}", path.stat().st_size == record["bytes"])
        check(f"implementation hash: {name}", sha256_file(path) == record["sha256"])
        frozen_name = {
            "protocol": "frozen-protocol.md",
            "runner": "frozen-runner.py",
            "verifier": "frozen-verifier.py",
            "tests": "frozen-tests.py",
        }[name]
        check(f"frozen implementation: {name}", sha256_file(run_dir / frozen_name) == record["sha256"])

    sources = payload.get("m2_sources", [])
    check("three M2 sources", [record.get("seed") for record in sources] == [42, 43, 44])
    runs: list[dict[str, Any]] = []
    for source, frozen in zip(config["m2_sources"], sources):
        seed = source["seed"]
        run_path = resolve_project(source["run"]["path"])
        source_verification_path = resolve_project(source["verification"]["path"])
        check(f"seed {seed} source record", source == frozen)
        check(f"seed {seed} run hash", sha256_file(run_path) == source["run"]["sha256"])
        check(
            f"seed {seed} verification hash",
            sha256_file(source_verification_path) == source["verification"]["sha256"],
        )
        run = json.loads(run_path.read_text(encoding="utf-8"))
        source_verification = json.loads(source_verification_path.read_text(encoding="utf-8"))
        check(f"seed {seed} completed", run.get("status") == "Completed")
        check(f"seed {seed} train-validation only", run.get("accessed_splits") == ["train", "validation"])
        check(f"seed {seed} test sealed", run.get("test_split_accessed") is False)
        check(f"seed {seed} verification passed", source_verification.get("status") == "Passed")
        check(f"seed {seed} no failed checks", source_verification.get("failed_checks") == [])
        check(
            f"seed {seed} verification count",
            source_verification.get("check_count") == source["verification"]["check_count"],
        )
        check(f"seed {seed} verifier test sealed", source_verification.get("test_split_accessed") is False)
        runs.append(run)

    m1_record = config["m1_reference"]
    check("M1 source record", payload.get("m1_reference") == m1_record)
    m1_path = resolve_project(m1_record["aggregate"]["path"])
    m1_verification_path = resolve_project(m1_record["verification"]["path"])
    check("M1 aggregate hash", sha256_file(m1_path) == m1_record["aggregate"]["sha256"])
    check(
        "M1 verification hash",
        sha256_file(m1_verification_path) == m1_record["verification"]["sha256"],
    )
    m1 = json.loads(m1_path.read_text(encoding="utf-8"))
    m1_verification = json.loads(m1_verification_path.read_text(encoding="utf-8"))
    check("M1 aggregate completed", m1.get("status") == "Completed")
    check("M1 aggregate test sealed", m1.get("test_split_accessed") is False)
    check("M1 verification passed", m1_verification.get("status") == "Passed")
    check("M1 verification count", m1_verification.get("check_count") == 53)
    check("M1 verifier test sealed", m1_verification.get("test_split_accessed") is False)

    recomputed = independently_aggregate(runs, m1)
    check("independent aggregate replay", values_match(payload.get("aggregate"), recomputed))
    serialized = json.dumps(payload, sort_keys=True)
    check("no private artifact path", '"private' not in serialized and "/private/" not in serialized)
    check("no row-level prediction path", "predictions." not in serialized and "probabilities." not in serialized)
    report_path = run_dir / "REPORT.md"
    report = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    check("report exists", report_path.is_file())
    check("report states validation boundary", "validation-only M2 family result" in report)
    check("report states paired boundary", "descriptive for three matched seeds" in report)
    check("report states heterogeneous resources", "not averaged into a family cost" in report)
    check("report seals later stages", "EXP-053 and EXP-054 remain sealed" in report)

    failed = [item["name"] for item in checks if not item["passed"]]
    result = {
        "schema_version": "exp-052-m2-three-seed-validation-verification-v1",
        "experiment_id": "EXP-052",
        "stage": "m2-three-seed-validation-aggregate",
        "status": "Passed" if not failed else "Failed",
        "verified_at_utc": utc_now(),
        "check_count": len(checks),
        "checks": checks,
        "failed_checks": failed,
        "aggregate_sha256": sha256_file(run_dir / "aggregate.json"),
        "recomputed_primary": {
            condition: recomputed["metrics"][condition]["macro_f1"]
            for condition in CONDITIONS
        },
        "recomputed_paired_macro_f1": {
            condition: recomputed["paired_m2_minus_m1"][condition]["summary"]["macro_f1"]
            for condition in CONDITIONS
        },
        "test_split_accessed": False,
    }
    verification_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary = (
        "# EXP-052 M2 Three-Seed Validation Aggregate Verification\n\n"
        f"- Status: `{result['status']}`\n"
        f"- Checks: `{len(checks) - len(failed)}/{len(checks)}` passed\n"
        "- Row-level predictions read or pooled: no\n"
        "- Test accessed: no\n"
        "- EXP-053/054 authorized: no\n"
    )
    (run_dir / "VERIFICATION-SUMMARY.md").write_text(summary, encoding="utf-8")
    print(json.dumps({"status": result["status"], "check_count": len(checks), "failed": failed}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
