#!/usr/bin/env python3
"""Audit complete scientific artifacts from the failed EXP-028 formal run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import multilabel_confusion_matrix

from verify_frozen_probe import (
    PROJECT_ROOT,
    compare_nested,
    compute_metrics,
    load_targets,
    parse_prediction_csv,
    recompute_bootstrap,
    sha256,
)


EXPECTED_CONFIG_SHA256 = "a932e62a1dbbd6d5cf0c46656b74043caedf63ddc488a578d0e5ac8a0ded4cea"
EXPECTED_FAILURE = "Probe fitting exceeded the frozen wall-time budget"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    return parser.parse_args()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def inventory(root: Path, *, excluded: set[str] | None = None) -> dict[str, dict[str, Any]]:
    excluded = excluded or set()
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = str(path.relative_to(root))
        if relative in excluded:
            continue
        records[relative] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    return records


def expected_public_paths(seeds: list[int]) -> set[str]:
    paths = {
        "aggregate-metrics.json",
        "condition-summary.csv",
        "failure.json",
        "paired-bootstrap.json",
        "stdout.log",
    }
    for condition in ("base", "post-trained"):
        paths.update(
            {
                f"{condition}/metrics.json",
                f"{condition}/multilabel-confusion-matrix.csv",
                f"{condition}/per-label-metrics.csv",
                f"{condition}/predictions.csv",
            }
        )
        for seed in seeds:
            paths.add(f"{condition}/label-shuffle/seed-{seed}-metrics.json")
            paths.add(f"{condition}/label-shuffle/seed-{seed}-predictions.csv")
    return paths


def validate_per_label_csv(path: Path, metrics: dict[str, Any], labels: list[str]) -> float:
    with path.open("r", encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    if len(rows) != len(labels):
        raise ValueError(f"Unexpected per-label row count: {path}")
    maximum = 0.0
    for label_id, (label, row) in enumerate(zip(labels, rows, strict=True)):
        if int(row["label_id"]) != label_id or row["label"] != label:
            raise ValueError(f"Per-label identity mismatch: {path}")
        expected = metrics["per_label"][label]
        for key in ("precision", "recall", "f1"):
            difference = abs(float(row[key]) - float(expected[key]))
            maximum = max(maximum, difference)
            if difference > 5e-12:
                raise ValueError(f"Per-label numeric mismatch for {label}/{key}: {path}")
        for key in ("support", "predicted_support"):
            if int(row[key]) != int(expected[key]):
                raise ValueError(f"Per-label count mismatch for {label}/{key}: {path}")
    return maximum


def validate_confusion_csv(
    path: Path,
    gold: np.ndarray,
    predicted: np.ndarray,
    labels: list[str],
) -> None:
    expected = multilabel_confusion_matrix(gold, predicted)
    with path.open("r", encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    if len(rows) != len(labels):
        raise ValueError(f"Unexpected confusion row count: {path}")
    for label_id, (label, row, matrix) in enumerate(zip(labels, rows, expected, strict=True)):
        if int(row["label_id"]) != label_id or row["label"] != label:
            raise ValueError(f"Confusion identity mismatch: {path}")
        observed = [int(row[key]) for key in ("tn", "fp", "fn", "tp")]
        if observed != [int(value) for value in matrix.ravel()]:
            raise ValueError(f"Confusion value mismatch for {label}: {path}")


def validate_condition_summary(
    path: Path,
    aggregate: dict[str, Any],
) -> float:
    with path.open("r", encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    if [row["condition"] for row in rows] != ["base", "post-trained"]:
        raise ValueError("Condition summary order or identity mismatch")
    maximum = 0.0
    for row in rows:
        condition = row["condition"]
        result = aggregate[condition]
        shuffled = [float(item["macro_f1"]) for item in result["label_shuffle"]["runs"]]
        expected = {
            "macro_f1": result["metrics"]["macro"]["f1"],
            "micro_f1": result["metrics"]["micro"]["f1"],
            "weighted_f1": result["metrics"]["weighted"]["f1"],
            "subset_accuracy": result["metrics"]["subset_accuracy"],
            "shuffle_macro_f1_mean": float(np.mean(shuffled)),
            "shuffle_macro_f1_max": max(shuffled),
            "real_minus_max_shuffle_macro_f1": (
                result["metrics"]["macro"]["f1"] - max(shuffled)
            ),
        }
        for key, value in expected.items():
            difference = abs(float(row[key]) - float(value))
            maximum = max(maximum, difference)
            if difference > 1e-12:
                raise ValueError(f"Condition summary mismatch for {condition}/{key}")
    return maximum


def source_runtime_seconds(stdout_path: Path, failure: dict[str, Any]) -> float:
    first_line = stdout_path.read_text(encoding="utf-8").splitlines()[0]
    match = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})Z", first_line)
    if match is None:
        raise ValueError("Could not parse EXP-028 start time")
    started = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S,%f").replace(
        tzinfo=timezone.utc
    )
    failed = datetime.fromisoformat(failure["created_at_utc"])
    return (failed - started).total_seconds()


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    run_dir = args.run_dir.resolve()
    manifest_path = run_dir / "failed-run-manifest.json"
    verification_path = run_dir / "failed-artifact-verification.json"
    if manifest_path.exists() or verification_path.exists():
        raise FileExistsError("Refusing to overwrite an existing failed-run audit")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["experiment_id"] != "EXP-028" or sha256(config_path) != EXPECTED_CONFIG_SHA256:
        raise ValueError("EXP-028 config identity or hash mismatch")
    expected_run_dir = PROJECT_ROOT / config["paths"]["formal_run_dir"]
    if run_dir != expected_run_dir.resolve():
        raise ValueError("Unexpected EXP-028 run directory")
    if (run_dir / "run.json").exists() or (run_dir / "verification.json").exists():
        raise ValueError("Failed EXP-028 must not contain formal completion artifacts")

    failure_path = run_dir / "failure.json"
    failure = json.loads(failure_path.read_text(encoding="utf-8"))
    if (
        failure.get("status") != "Failed"
        or failure.get("experiment_id") != "EXP-028"
        or failure.get("error") != EXPECTED_FAILURE
        or failure.get("test_split_accessed")
    ):
        raise ValueError("Unexpected EXP-028 failure artifact")

    seeds = [int(value) for value in config["label_shuffle"]["seeds"]]
    public_inventory = inventory(run_dir)
    expected_paths = expected_public_paths(seeds)
    if set(public_inventory) != expected_paths:
        missing = sorted(expected_paths - set(public_inventory))
        extra = sorted(set(public_inventory) - expected_paths)
        raise ValueError(f"Failed-run artifact set mismatch; missing={missing}, extra={extra}")

    test_path = PROJECT_ROOT / config["data"]["test_path"]
    if test_path.exists():
        raise FileExistsError("GoEmotions test must remain absent")
    labels_path = PROJECT_ROOT / config["data"]["labels_path"]
    labels = labels_path.read_text(encoding="utf-8").splitlines()
    if sha256(labels_path) != config["data"]["labels_sha256"]:
        raise ValueError("Frozen label hash mismatch")

    targets: dict[str, np.ndarray] = {}
    for split in ("train", "dev"):
        spec = config["data"]["splits"][split]
        path = PROJECT_ROOT / spec["path"]
        if sha256(path) != spec["sha256"]:
            raise ValueError(f"Frozen {split} hash mismatch")
        targets[split] = load_targets(path, int(spec["rows"]), len(labels))

    cache_root = PROJECT_ROOT / config["paths"]["private_cache_root"]
    feature_records: dict[str, dict[str, Any]] = {"base": {}, "post-trained": {}}
    token_digests: dict[str, dict[str, str]] = {"base": {}, "post-trained": {}}
    for condition in ("base", "post-trained"):
        for split in ("train", "dev"):
            metadata_path = cache_root / condition / split / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            feature_path = cache_root / condition / split / "features.npy"
            if (
                metadata["status"] != "Completed"
                or metadata["test_split_accessed"]
                or not metadata["test_absent_after_run"]
                or not metadata["vector_diagnostics"]["all_finite"]
                or sha256(feature_path) != metadata["feature"]["sha256"]
            ):
                raise ValueError(f"Feature cache gate failed for {condition}/{split}")
            token_digests[condition][split] = metadata["tokenization"]["token_id_stream_sha256"]
            feature_records[condition][split] = {
                "feature_bytes": feature_path.stat().st_size,
                "feature_sha256": metadata["feature"]["sha256"],
                "metadata_sha256": sha256(metadata_path),
            }
    for split in ("train", "dev"):
        if token_digests["base"][split] != token_digests["post-trained"][split]:
            raise ValueError(f"Base/post-trained token stream mismatch for {split}")

    aggregate_path = run_dir / "aggregate-metrics.json"
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    if set(aggregate) != {"base", "post-trained"}:
        raise ValueError("Unexpected aggregate condition set")
    numeric_differences: list[float] = []
    probability_differences: list[float] = []
    per_label_differences: list[float] = []
    predictions_by_condition: dict[str, np.ndarray] = {}
    model_root = cache_root / "probe-models"
    expected_models = {
        f"{condition}/{name}.joblib"
        for condition in ("base", "post-trained")
        for name in ["real-probe", *(f"label-shuffle-seed-{seed}" for seed in seeds)]
    }
    private_model_inventory = inventory(model_root)
    if set(private_model_inventory) != expected_models:
        raise ValueError("Unexpected private probe-model artifact set")

    for condition in ("base", "post-trained"):
        result = aggregate[condition]
        dev_features = np.load(cache_root / condition / "dev" / "features.npy", mmap_mode="r")
        real_model_path = model_root / condition / "real-probe.joblib"
        if sha256(real_model_path) != result["private_real_model_sha256"]:
            raise ValueError(f"Real model hash mismatch for {condition}")
        bundle = joblib.load(real_model_path)
        dev_scaled = bundle["scaler"].transform(dev_features).astype(np.float32, copy=False)
        recomputed_probabilities = bundle["classifier"].predict_proba(dev_scaled)
        saved_predictions, saved_probabilities = parse_prediction_csv(
            run_dir / condition / "predictions.csv",
            targets["dev"],
            labels,
            require_probabilities=True,
        )
        if saved_probabilities is None:
            raise ValueError(f"Missing real probabilities for {condition}")
        probability_difference = float(
            np.max(np.abs(recomputed_probabilities - saved_probabilities))
        )
        probability_differences.append(probability_difference)
        if probability_difference > 1e-12:
            raise ValueError(f"Probability mismatch for {condition}")
        recomputed_predictions = (
            recomputed_probabilities >= float(config["probe"]["threshold"])
        ).astype(np.uint8)
        if not np.array_equal(recomputed_predictions, saved_predictions):
            raise ValueError(f"Real prediction mismatch for {condition}")
        predictions_by_condition[condition] = saved_predictions
        recomputed_metrics = compute_metrics(targets["dev"], saved_predictions, labels)
        saved_metrics = json.loads((run_dir / condition / "metrics.json").read_text(encoding="utf-8"))
        compare_nested(
            recomputed_metrics,
            saved_metrics,
            path=f"{condition}.metrics",
            numeric_differences=numeric_differences,
        )
        compare_nested(
            saved_metrics,
            result["metrics"],
            path=f"{condition}.aggregate.metrics",
            numeric_differences=numeric_differences,
        )
        per_label_differences.append(
            validate_per_label_csv(
                run_dir / condition / "per-label-metrics.csv", saved_metrics, labels
            )
        )
        validate_confusion_csv(
            run_dir / condition / "multilabel-confusion-matrix.csv",
            targets["dev"],
            saved_predictions,
            labels,
        )

        runs_by_seed = {int(item["seed"]): item for item in result["label_shuffle"]["runs"]}
        if set(runs_by_seed) != set(seeds):
            raise ValueError(f"Aggregate shuffle seed mismatch for {condition}")
        for seed in seeds:
            permutation = np.random.default_rng(seed).permutation(targets["train"].shape[0])
            permutation_sha256 = hashlib.sha256(
                np.asarray(permutation, dtype="<i8").tobytes(order="C")
            ).hexdigest()
            shuffle_record = runs_by_seed[seed]
            if shuffle_record["permutation_sha256"] != permutation_sha256:
                raise ValueError(f"Aggregate permutation mismatch for {condition}/{seed}")
            shuffle_model_path = model_root / condition / f"label-shuffle-seed-{seed}.joblib"
            if sha256(shuffle_model_path) != shuffle_record["model_sha256"]:
                raise ValueError(f"Shuffle model hash mismatch for {condition}/{seed}")
            shuffle_bundle = joblib.load(shuffle_model_path)
            if shuffle_bundle["permutation_sha256"] != permutation_sha256:
                raise ValueError(f"Model permutation mismatch for {condition}/{seed}")
            shuffle_probabilities = shuffle_bundle["classifier"].predict_proba(dev_scaled)
            recomputed_shuffle = (
                shuffle_probabilities >= float(config["probe"]["threshold"])
            ).astype(np.uint8)
            shuffle_prediction_path = (
                run_dir / condition / "label-shuffle" / f"seed-{seed}-predictions.csv"
            )
            saved_shuffle, _ = parse_prediction_csv(
                shuffle_prediction_path,
                targets["dev"],
                labels,
                require_probabilities=False,
            )
            if not np.array_equal(recomputed_shuffle, saved_shuffle):
                raise ValueError(f"Shuffle prediction mismatch for {condition}/{seed}")
            if sha256(shuffle_prediction_path) != shuffle_record["prediction_sha256"]:
                raise ValueError(f"Shuffle prediction hash mismatch for {condition}/{seed}")
            recomputed_shuffle_metrics = compute_metrics(targets["dev"], saved_shuffle, labels)
            saved_shuffle_metrics = json.loads(
                (
                    run_dir
                    / condition
                    / "label-shuffle"
                    / f"seed-{seed}-metrics.json"
                ).read_text(encoding="utf-8")
            )
            compare_nested(
                recomputed_shuffle_metrics,
                saved_shuffle_metrics,
                path=f"{condition}.shuffle.{seed}",
                numeric_differences=numeric_differences,
            )
            compare_nested(
                saved_shuffle_metrics,
                shuffle_record["metrics"],
                path=f"{condition}.aggregate.shuffle.{seed}",
                numeric_differences=numeric_differences,
            )

    per_label_differences.append(validate_condition_summary(run_dir / "condition-summary.csv", aggregate))
    recomputed_bootstrap = recompute_bootstrap(targets["dev"], predictions_by_condition, config)
    saved_bootstrap = json.loads((run_dir / "paired-bootstrap.json").read_text(encoding="utf-8"))
    compare_nested(
        recomputed_bootstrap,
        saved_bootstrap,
        path="paired_bootstrap",
        numeric_differences=numeric_differences,
    )

    runtime_seconds = source_runtime_seconds(run_dir / "stdout.log", failure)
    budget_seconds = float(config["resource_budget"]["probe_wall_time_minutes_max"]) * 60
    if runtime_seconds <= budget_seconds:
        raise ValueError("Recorded EXP-028 runtime does not exceed its frozen budget")

    manifest = {
        "accessed_splits": ["train", "dev"],
        "artifacts": {
            "private_feature_cache": feature_records,
            "private_probe_models": private_model_inventory,
            "public_failed_run": public_inventory,
        },
        "comparison": saved_bootstrap,
        "config_path": str(config_path.relative_to(PROJECT_ROOT)),
        "config_sha256": sha256(config_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-028",
        "failure": failure,
        "resource_gate": {
            "budget_seconds": budget_seconds,
            "exceeded_by_seconds": runtime_seconds - budget_seconds,
            "observed_seconds_from_log": runtime_seconds,
            "passed": False,
        },
        "status": "Failed",
        "test_absent_after_audit": not test_path.exists(),
        "test_split_accessed": False,
    }
    write_json(manifest_path, manifest)

    verification = {
        "accessed_splits": ["train", "dev"],
        "artifact_integrity_status": "Passed",
        "checked_private_feature_files": 4,
        "checked_private_model_files": len(private_model_inventory),
        "checked_public_source_files": len(public_inventory),
        "config_sha256": sha256(config_path),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_eligibility": "Not eligible for Verified evidence; EXP-028 remains Failed",
        "experiment_id": "EXP-028",
        "failed_run_manifest_sha256": sha256(manifest_path),
        "max_metric_or_bootstrap_difference": max(numeric_differences, default=0.0),
        "max_per_label_csv_difference": max(per_label_differences, default=0.0),
        "max_probability_difference": max(probability_differences, default=0.0),
        "source_experiment_status": "Failed",
        "test_absent": not test_path.exists(),
        "test_split_accessed": False,
        "token_streams_identical_across_conditions": True,
        "verifier_sha256": sha256(Path(__file__).resolve()),
    }
    write_json(verification_path, verification)
    print(json.dumps(verification, sort_keys=True))


if __name__ == "__main__":
    main()
