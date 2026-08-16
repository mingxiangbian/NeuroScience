#!/usr/bin/env python3
"""Independently verify the EXP-053 M3 three-seed validation aggregate."""

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


def paired_summary(
    per_seed: dict[str, Any], reference: dict[str, Any]
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for condition in CONDITIONS:
        per_seed_delta: dict[str, Any] = {}
        for seed, row in per_seed.items():
            reference_metrics = reference["aggregate"]["per_seed"][seed]["metrics"][condition]
            per_seed_delta[seed] = {
                field: row["metrics"][condition][field] - reference_metrics[field]
                for field in COMPARISON_FIELDS
            }
        result[condition] = {
            "per_seed": per_seed_delta,
            "summary": {
                field: independent_summary(
                    [per_seed_delta[str(seed)][field] for seed in (42, 43, 44)]
                )
                for field in COMPARISON_FIELDS
            },
        }
    return result


def independently_aggregate(
    runs: list[dict[str, Any]], m1: dict[str, Any], m2: dict[str, Any]
) -> dict[str, Any]:
    per_seed: dict[str, Any] = {}
    for run in runs:
        seed = str(run["training"]["seed"])
        per_seed[seed] = {
            "selected_epoch": run["selection"]["selected_epoch"],
            "selected_shared_threshold": run["threshold_selection"]["selected_threshold"],
            "metrics": {
                condition: extract_metric(run["metrics"][condition])
                for condition in CONDITIONS
            },
            "resources": {field: run["resources"][field] for field in RESOURCE_FIELDS},
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
    return {
        "selected_epoch": independent_summary([row["selected_epoch"] for row in rows]),
        "selected_shared_threshold": independent_summary(
            [row["selected_shared_threshold"] for row in rows]
        ),
        "metrics": aggregate_metrics,
        "paired_m3_minus_m1": paired_summary(per_seed, m1),
        "paired_m3_minus_m2": paired_summary(per_seed, m2),
        "resources": {
            field: independent_summary([row["resources"][field] for row in rows])
            for field in RESOURCE_FIELDS
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


def verification_count(payload: dict[str, Any]) -> int | None:
    return payload.get("checks_total", payload.get("check_count"))


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

    check("schema", payload.get("schema_version") == "exp-053-m3-three-seed-validation-aggregate-v1")
    check("experiment identity", payload.get("experiment_id") == "EXP-053")
    check("tier", payload.get("tier") == "Major")
    check("stage", payload.get("stage") == "m3-three-seed-validation-aggregate")
    check("status", payload.get("status") == "Completed")
    check("config hash", payload.get("config", {}).get("sha256") == sha256_file(config_path))
    check("frozen config", sha256_file(run_dir / "frozen-config.json") == sha256_file(config_path))

    authorization = payload.get("authorization", {})
    check("aggregate explicitly authorized", authorization.get("m3_aggregate_authorized") is True)
    check("seed set", authorization.get("seeds") == [42, 43, 44])
    check("split boundary", authorization.get("source_splits") == ["train", "validation"])
    check("training sealed", authorization.get("m3_training_authorized") is False)
    check("test sealed", authorization.get("test_access") is False)
    check("TEST-READY sealed", authorization.get("test_ready") is False)
    check("M4 sealed", authorization.get("m4_authorized") is False)
    check("error analysis sealed", authorization.get("error_analysis_authorized") is False)
    check("private artifacts sealed", authorization.get("read_private_artifacts") is False)
    check("aggregate test flag", payload.get("test_split_accessed") is False)

    method = payload.get("method", {})
    check("arithmetic mean", method.get("center") == "arithmetic_mean")
    check("sample standard deviation", method.get("dispersion") == "sample_standard_deviation")
    check("ddof one", method.get("ddof") == 1)
    check("no pooled predictions", method.get("pool_predictions_across_seeds") is False)
    check("paired references", method.get("paired_references") == ["EXP-051", "EXP-052"])
    check("paired by seed", method.get("pair_by_seed") is True)
    check("no inferential test", method.get("inferential_test") is False)
    check("M3 resources aggregated", method.get("aggregate_m3_resources") is True)
    check(
        "cross-model resource comparison sealed",
        method.get("cross_model_resource_comparison") is False,
    )

    frozen_names = {
        "protocol": "frozen-protocol.md",
        "runner": "frozen-runner.py",
        "verifier": "frozen-verifier.py",
        "tests": "frozen-tests.py",
    }
    for name, record in config["implementation"].items():
        path = resolve_project(record["path"])
        check(f"implementation exists: {name}", path.is_file())
        check(f"implementation bytes: {name}", path.stat().st_size == record["bytes"])
        check(f"implementation hash: {name}", sha256_file(path) == record["sha256"])
        check(
            f"frozen implementation: {name}",
            sha256_file(run_dir / frozen_names[name]) == record["sha256"],
        )

    frozen_sources = payload.get("m3_sources", [])
    check("three M3 sources", [record.get("seed") for record in frozen_sources] == [42, 43, 44])
    runs: list[dict[str, Any]] = []
    for source, frozen in zip(config["m3_sources"], frozen_sources):
        seed = source["seed"]
        run_path = resolve_project(source["run"]["path"])
        source_verification_path = resolve_project(source["verification"]["path"])
        check(f"seed {seed} source record", source == frozen)
        check(f"seed {seed} run bytes", run_path.stat().st_size == source["run"]["bytes"])
        check(f"seed {seed} run hash", sha256_file(run_path) == source["run"]["sha256"])
        check(
            f"seed {seed} verification bytes",
            source_verification_path.stat().st_size == source["verification"]["bytes"],
        )
        check(
            f"seed {seed} verification hash",
            sha256_file(source_verification_path) == source["verification"]["sha256"],
        )
        run = json.loads(run_path.read_text(encoding="utf-8"))
        verification = json.loads(source_verification_path.read_text(encoding="utf-8"))
        check(f"seed {seed} identity", run.get("training", {}).get("seed") == seed)
        check(f"seed {seed} completed", run.get("status") == "Completed")
        check(f"seed {seed} train-validation only", run.get("accessed_splits") == ["train", "validation"])
        check(f"seed {seed} validation accessed", run.get("validation_split_accessed") is True)
        check(f"seed {seed} test sealed", run.get("test_split_accessed") is False)
        check(f"seed {seed} verification passed", verification.get("status") == "Passed")
        check(f"seed {seed} no failed checks", verification.get("failed_checks") == [])
        check(
            f"seed {seed} verification count",
            verification_count(verification) == source["verification"]["check_count"],
        )
        check(
            f"seed {seed} verification list",
            len(verification.get("checks", [])) == source["verification"]["check_count"],
        )
        check(
            f"seed {seed} all verification checks passed",
            all(item.get("passed") is True for item in verification.get("checks", [])),
        )
        check(f"seed {seed} verifier test sealed", verification.get("test_split_accessed") is False)
        check(
            f"seed {seed} replay exact",
            verification.get("selected_checkpoint_probability_replay_max_abs_error") == 0.0,
        )
        if seed == 42:
            prior_record = source["prior_failed_verification"]
            prior_path = resolve_project(prior_record["path"])
            prior = json.loads(prior_path.read_text(encoding="utf-8"))
            check("seed 42 uses attempt 2", verification.get("verification_attempt") == 2)
            check("seed 42 prior failed hash", sha256_file(prior_path) == prior_record["sha256"])
            check("seed 42 prior failure preserved", prior.get("status") == "Failed")
        if seed == 44:
            correction_record = source["documentation_correction"]
            correction_path = resolve_project(correction_record["path"])
            correction = correction_path.read_text(encoding="utf-8")
            check("seed 44 correction hash", sha256_file(correction_path) == correction_record["sha256"])
            check(
                "seed 44 correction meaning",
                "Seed 44 is the third authorized EXP-053 M3 seed." in correction,
            )
        runs.append(run)

    references: dict[str, dict[str, Any]] = {}
    for key, experiment_id, expected_count in (
        ("m1_reference", "EXP-051", 53),
        ("m2_reference", "EXP-052", 85),
    ):
        record = config[key]
        check(f"{experiment_id} source record", payload.get(key) == record)
        aggregate_path = resolve_project(record["aggregate"]["path"])
        reference_verification_path = resolve_project(record["verification"]["path"])
        check(
            f"{experiment_id} aggregate hash",
            sha256_file(aggregate_path) == record["aggregate"]["sha256"],
        )
        check(
            f"{experiment_id} verification hash",
            sha256_file(reference_verification_path) == record["verification"]["sha256"],
        )
        reference = json.loads(aggregate_path.read_text(encoding="utf-8"))
        reference_verification = json.loads(
            reference_verification_path.read_text(encoding="utf-8")
        )
        check(f"{experiment_id} aggregate completed", reference.get("status") == "Completed")
        check(f"{experiment_id} aggregate test sealed", reference.get("test_split_accessed") is False)
        check(f"{experiment_id} verification passed", reference_verification.get("status") == "Passed")
        check(
            f"{experiment_id} verification count",
            reference_verification.get("check_count") == expected_count,
        )
        check(
            f"{experiment_id} verifier test sealed",
            reference_verification.get("test_split_accessed") is False,
        )
        references[experiment_id] = reference

    recomputed = independently_aggregate(runs, references["EXP-051"], references["EXP-052"])
    check("independent aggregate replay", values_match(payload.get("aggregate"), recomputed))
    serialized = json.dumps(payload, sort_keys=True)
    check("no private artifact path", '"private' not in serialized and "/private/" not in serialized)
    check(
        "no row-level prediction path",
        "predictions." not in serialized and "probabilities." not in serialized,
    )
    report_path = run_dir / "REPORT.md"
    report = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    check("report exists", report_path.is_file())
    check("report states validation boundary", "validation-only M3 family result" in report)
    check("report states descriptive boundary", "descriptive for three seed-matched runs" in report)
    check("report rejects cross-model cost", "not a cross-model cost comparison" in report)
    check("report states surprise boundary", "seven validation positives" in report)
    check("report seals later stages", "EXP-054 and error analysis remain sealed" in report)

    failed = [item["name"] for item in checks if not item["passed"]]
    result = {
        "schema_version": "exp-053-m3-three-seed-validation-verification-v1",
        "experiment_id": "EXP-053",
        "stage": "m3-three-seed-validation-aggregate",
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
            "m3_minus_m1": {
                condition: recomputed["paired_m3_minus_m1"][condition]["summary"]["macro_f1"]
                for condition in CONDITIONS
            },
            "m3_minus_m2": {
                condition: recomputed["paired_m3_minus_m2"][condition]["summary"]["macro_f1"]
                for condition in CONDITIONS
            },
        },
        "test_split_accessed": False,
    }
    verification_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary = (
        "# EXP-053 M3 Three-Seed Validation Aggregate Verification\n\n"
        f"- Status: `{result['status']}`\n"
        f"- Checks: `{len(checks) - len(failed)}/{len(checks)}` passed\n"
        "- Row-level predictions read or pooled: no\n"
        "- Test accessed: no\n"
        "- EXP-054 and error analysis authorized: no\n"
    )
    (run_dir / "VERIFICATION-SUMMARY.md").write_text(summary, encoding="utf-8")
    print(json.dumps({"status": result["status"], "check_count": len(checks), "failed": failed}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
