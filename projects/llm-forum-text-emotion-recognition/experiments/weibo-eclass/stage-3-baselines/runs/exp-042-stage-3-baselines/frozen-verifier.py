#!/usr/bin/env python3
"""Independently verify EXP-042 from saved private predictions and public artifacts."""

from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any, Sequence

from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support


EXPERIMENT_ID = "EXP-042"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
CONFIG_PATH = SCRIPT_DIR / "config.json"
VIEWS = ("target_only", "previous_context")
METRIC_NAMES = ("macro_f1", "accuracy", "macro_precision", "macro_recall", "weighted_f1")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def project_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": project_path(path),
        "sha256": sha256_file(path),
    }


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config["experiment_id"] != EXPERIMENT_ID or config["data"]["test_access"]:
        raise ValueError("EXP-042 config identity or test gate drift")
    bindings = (
        (config["implementation"]["runner_path"], config["implementation"]["runner_sha256"]),
        (config["implementation"]["test_path"], config["implementation"]["test_sha256"]),
        (config["implementation"]["verifier_path"], config["implementation"]["verifier_sha256"]),
        (
            config["implementation"]["requirements_lock_path"],
            config["implementation"]["requirements_lock_sha256"],
        ),
        (config["prompt"]["path"], config["prompt"]["sha256"]),
        (config["data"]["manifest_path"], config["data"]["manifest_sha256"]),
        (config["m2"]["model_manifest_path"], config["m2"]["model_manifest_sha256"]),
    )
    for relative, expected in bindings:
        if expected == "PENDING" or sha256_file(resolve_project_path(relative)) != expected:
            raise ValueError(f"Frozen source mismatch: {relative}")
    return config


def load_rows(config: dict[str, Any], split: str) -> list[dict[str, Any]]:
    if split not in ("train", "validation"):
        raise ValueError(f"Unauthorized split: {split}")
    path = resolve_project_path(config["data"][f"{split}_path"])
    if sha256_file(path) != config["data"][f"{split}_sha256"]:
        raise ValueError(f"{split} hash mismatch")
    rows = []
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            rows.append(
                {
                    "context_available": bool(row["context_available"]),
                    "group_id": row["group_id"],
                    "label": row["label"],
                    "sample_id": row["sample_id"],
                }
            )
    if len(rows) != config["data"][f"{split}_rows"]:
        raise ValueError(f"{split} row count mismatch")
    return rows


def recompute_metrics(
    gold: Sequence[str], predicted: Sequence[str], labels: Sequence[str]
) -> dict[str, Any]:
    precision, recall, f1, support = precision_recall_fscore_support(
        gold,
        predicted,
        labels=list(labels),
        average=None,
        zero_division=0,
    )
    macro = precision_recall_fscore_support(
        gold,
        predicted,
        labels=list(labels),
        average="macro",
        zero_division=0,
    )
    weighted = precision_recall_fscore_support(
        gold,
        predicted,
        labels=list(labels),
        average="weighted",
        zero_division=0,
    )
    return {
        "accuracy": float(accuracy_score(gold, predicted)),
        "macro_f1": float(macro[2]),
        "macro_precision": float(macro[0]),
        "macro_recall": float(macro[1]),
        "per_class": {
            label: {
                "f1": float(f1[index]),
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "support": int(support[index]),
            }
            for index, label in enumerate(labels)
        },
        "rows": len(gold),
        "weighted_f1": float(weighted[2]),
        "confusion_matrix": confusion_matrix(gold, predicted, labels=list(labels)).astype(int).tolist(),
    }


def recompute_slices(
    validation: Sequence[dict[str, Any]], predictions: Sequence[dict[str, str]], labels: Sequence[str]
) -> dict[str, Any]:
    masks = {
        "all": [True] * len(validation),
        "context_available": [row["context_available"] for row in validation],
        "first_clause": [not row["context_available"] for row in validation],
    }
    result = {}
    for name, mask in masks.items():
        gold = [row["label"] for row, keep in zip(validation, mask) if keep]
        predicted = [row["prediction"] for row, keep in zip(predictions, mask) if keep]
        result[name] = recompute_metrics(gold, predicted, labels)
    return result


def assert_nested_equal(expected: Any, observed: Any, location: str) -> None:
    if isinstance(expected, dict):
        if not isinstance(observed, dict) or set(expected) != set(observed):
            raise AssertionError(f"Key mismatch at {location}")
        for key in expected:
            assert_nested_equal(expected[key], observed[key], f"{location}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(observed, list) or len(expected) != len(observed):
            raise AssertionError(f"List mismatch at {location}")
        for index, (left, right) in enumerate(zip(expected, observed)):
            assert_nested_equal(left, right, f"{location}[{index}]")
        return
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if not isinstance(observed, (int, float)) or not math.isclose(
            float(expected), float(observed), rel_tol=1e-12, abs_tol=1e-12
        ):
            raise AssertionError(f"Numeric mismatch at {location}: {expected} != {observed}")
        return
    if expected != observed:
        raise AssertionError(f"Value mismatch at {location}: {expected!r} != {observed!r}")


def load_predictions(
    path: Path,
    validation: Sequence[dict[str, Any]],
    labels: Sequence[str],
    score_prefix: str | None,
) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    base_fields = {"sample_id", "group_id", "context_available", "gold", "prediction"}
    score_fields = {f"{score_prefix}__{label}" for label in labels} if score_prefix else set()
    if set(fieldnames) != base_fields | score_fields:
        raise AssertionError(f"Prediction schema mismatch: {path}")
    if len(rows) != len(validation):
        raise AssertionError(f"Prediction row count mismatch: {path}")
    for expected, observed in zip(validation, rows):
        if observed["sample_id"] != expected["sample_id"]:
            raise AssertionError(f"Sample order mismatch: {path}")
        if observed["group_id"] != expected["group_id"] or observed["gold"] != expected["label"]:
            raise AssertionError(f"Prediction metadata mismatch: {path}")
        if int(observed["context_available"]) != int(expected["context_available"]):
            raise AssertionError(f"Context flag mismatch: {path}")
        if observed["prediction"] not in labels:
            raise AssertionError(f"Unknown prediction label: {path}")
        if score_prefix:
            values = [float(observed[f"{score_prefix}__{label}"]) for label in labels]
            if not all(math.isfinite(value) for value in values):
                raise AssertionError(f"Non-finite score: {path}")
            if score_prefix == "probability":
                if not all(0.0 <= value <= 1.0 for value in values):
                    raise AssertionError(f"Probability outside [0, 1]: {path}")
                if not math.isclose(sum(values), 1.0, rel_tol=0.0, abs_tol=1e-5):
                    raise AssertionError(f"Probability row does not sum to one: {path}")
    return rows


def verify_tables(condition_dir: Path, metrics: dict[str, Any], labels: Sequence[str]) -> None:
    with (condition_dir / "per_class_metrics.csv").open(
        "r", encoding="utf-8", newline=""
    ) as source:
        rows = list(csv.DictReader(source))
    expected_rows = len(metrics["slices"]) * len(labels)
    if len(rows) != expected_rows:
        raise AssertionError(f"Per-class table row count mismatch: {condition_dir}")
    lookup = {(row["slice"], row["label"]): row for row in rows}
    for slice_name, slice_metrics in metrics["slices"].items():
        for label in labels:
            observed = lookup[(slice_name, label)]
            expected = slice_metrics["per_class"][label]
            for metric in ("precision", "recall", "f1"):
                if not math.isclose(float(observed[metric]), expected[metric], abs_tol=1e-12):
                    raise AssertionError(f"Per-class {metric} mismatch: {condition_dir}")
            if int(observed["support"]) != expected["support"]:
                raise AssertionError(f"Per-class support mismatch: {condition_dir}")

    with (condition_dir / "confusion_matrix.csv").open(
        "r", encoding="utf-8", newline=""
    ) as source:
        matrix_rows = list(csv.reader(source))
    if matrix_rows[0] != ["gold\\predicted", *labels]:
        raise AssertionError(f"Confusion header mismatch: {condition_dir}")
    expected_matrix = metrics["slices"]["all"]["confusion_matrix"]
    for index, label in enumerate(labels):
        if matrix_rows[index + 1][0] != label:
            raise AssertionError(f"Confusion label mismatch: {condition_dir}")
        if [int(value) for value in matrix_rows[index + 1][1:]] != expected_matrix[index]:
            raise AssertionError(f"Confusion values mismatch: {condition_dir}")


def verify_checkpoint(root: Path, recorded: dict[str, Any]) -> int:
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".cache" in path.parts:
            continue
        files.append(
            {
                "bytes": path.stat().st_size,
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
            }
        )
    expected = {
        "file_count": len(files),
        "files": files,
        "path": project_path(root),
        "total_bytes": sum(item["bytes"] for item in files),
    }
    assert_nested_equal(expected, recorded, f"checkpoint.{root}")
    return expected["total_bytes"]


def mean_std(values: Sequence[float]) -> dict[str, float]:
    return {
        "mean": statistics.fmean(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def main() -> None:
    config = load_config()
    public = resolve_project_path(config["run_dir"])
    private = resolve_project_path(config["private_root"])
    output = public / "verification.json"
    if output.exists():
        raise FileExistsError("EXP-042 verification is append-only")
    run_path = public / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    if run["status"] != "Awaiting Independent Verification":
        raise AssertionError("EXP-042 is not ready for independent verification")
    if run["accessed_splits"] != ["train", "validation"]:
        raise AssertionError("Unexpected split access record")
    if run["test_split_accessed"] or not run["validation_split_accessed"]:
        raise AssertionError("Run split flags violate EXP-042")

    checks: list[str] = []
    train = load_rows(config, "train")
    validation = load_rows(config, "validation")
    labels = config["data"]["labels"]
    checks.append("frozen_train_validation_hashes_and_counts")

    counts = Counter(row["label"] for row in train)
    majority = counts.most_common(1)[0][0]
    if majority != config["m0"]["expected_majority_label"]:
        raise AssertionError("M0 majority derivation mismatch")
    conditions: dict[str, dict[str, Any]] = {}

    m0_dir = public / "m0" / "majority"
    m0_metrics = json.loads((m0_dir / "metrics.json").read_text(encoding="utf-8"))
    m0_predictions = load_predictions(private / "m0" / "predictions.csv", validation, labels, None)
    if {row["prediction"] for row in m0_predictions} != {majority}:
        raise AssertionError("M0 predictions are not the train majority")
    expected_slices = recompute_slices(validation, m0_predictions, labels)
    assert_nested_equal(expected_slices, m0_metrics["slices"], "m0.slices")
    verify_tables(m0_dir, m0_metrics, labels)
    conditions["m0"] = m0_metrics
    checks.append("m0_predictions_metrics_and_tables")

    for view in VIEWS:
        condition_dir = public / "m1" / view
        metrics = json.loads((condition_dir / "metrics.json").read_text(encoding="utf-8"))
        predictions = load_predictions(
            private / "m1" / view / "predictions.csv",
            validation,
            labels,
            "decision",
        )
        expected_slices = recompute_slices(validation, predictions, labels)
        assert_nested_equal(expected_slices, metrics["slices"], f"m1.{view}.slices")
        verify_tables(condition_dir, metrics, labels)
        conditions[f"m1.{view}"] = metrics
    checks.append("m1_predictions_scores_metrics_and_tables")

    m2_metrics: dict[str, dict[int, dict[str, Any]]] = {view: {} for view in VIEWS}
    checkpoint_bytes = 0
    for view in VIEWS:
        for seed in config["m2"]["seeds"]:
            condition_dir = public / "m2" / view / f"seed-{seed}"
            metrics = json.loads((condition_dir / "metrics.json").read_text(encoding="utf-8"))
            report = json.loads((condition_dir / "run.json").read_text(encoding="utf-8"))
            if report["seed"] != seed or report["view"] != view or report["test_split_accessed"]:
                raise AssertionError(f"M2 run identity mismatch: {view}/{seed}")
            predictions = load_predictions(
                private / "m2" / view / f"seed-{seed}" / "predictions.csv",
                validation,
                labels,
                "probability",
            )
            expected_slices = recompute_slices(validation, predictions, labels)
            assert_nested_equal(expected_slices, metrics["slices"], f"m2.{view}.{seed}.slices")
            verify_tables(condition_dir, metrics, labels)
            checkpoint_bytes += verify_checkpoint(
                private / "m2" / view / f"seed-{seed}" / "final-model",
                report["checkpoint"],
            )
            m2_metrics[view][seed] = metrics
    if checkpoint_bytes > config["resource_budget"]["storage_bytes_max"]:
        raise AssertionError("Retained checkpoints exceed the frozen storage budget")
    checks.append("six_m2_prediction_probability_metric_table_and_checkpoint_runs")

    aggregate_path = public / "aggregate_metrics.json"
    observed_aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    expected_m2 = {}
    for view in VIEWS:
        expected_m2[view] = {
            "seeds": config["m2"]["seeds"],
            "slices": {
                slice_name: {
                    metric: mean_std(
                        [
                            m2_metrics[view][seed]["slices"][slice_name][metric]
                            for seed in config["m2"]["seeds"]
                        ]
                    )
                    for metric in METRIC_NAMES
                }
                for slice_name in config["evaluation"]["slices"]
            },
        }
    assert_nested_equal(expected_m2, observed_aggregate["m2"], "aggregate.m2")

    expected_deltas = {}
    for slice_name in config["evaluation"]["slices"]:
        per_seed = {
            str(seed): {
                metric: (
                    m2_metrics["previous_context"][seed]["slices"][slice_name][metric]
                    - m2_metrics["target_only"][seed]["slices"][slice_name][metric]
                )
                for metric in METRIC_NAMES
            }
            for seed in config["m2"]["seeds"]
        }
        expected_deltas[slice_name] = {
            "per_seed": per_seed,
            "summary": {
                metric: mean_std(
                    [per_seed[str(seed)][metric] for seed in config["m2"]["seeds"]]
                )
                for metric in METRIC_NAMES
            },
        }
    assert_nested_equal(
        expected_deltas,
        observed_aggregate["m2_paired_context_minus_target"],
        "aggregate.paired_deltas",
    )
    checks.append("m2_seed_aggregates_and_paired_deltas")

    target_mean = expected_m2["target_only"]["slices"]["all"]["macro_f1"]["mean"]
    context_mean = expected_m2["previous_context"]["slices"]["all"]["macro_f1"]["mean"]
    delta = context_mean - target_mean
    if abs(delta) < config["evaluation"]["practical_tie_absolute"]:
        selected = "target_only"
    else:
        selected = "previous_context" if delta > 0 else "target_only"
    selection = observed_aggregate["m2_primary_view_selection"]
    if selection["selected_view"] != selected:
        raise AssertionError("M2 primary view selection mismatch")
    for key, expected in (
        ("target_mean_macro_f1", target_mean),
        ("context_mean_macro_f1", context_mean),
        ("delta", delta),
    ):
        if not math.isclose(selection[key], expected, abs_tol=1e-12):
            raise AssertionError(f"M2 selection value mismatch: {key}")
    checks.append("m2_practical_tie_selection_rule")

    private_ids = {row["sample_id"] for row in validation} | {row["group_id"] for row in validation}
    for path in public.rglob("*"):
        if not path.is_file() or path == output:
            continue
        if path.suffix.lower() not in {".json", ".csv", ".md", ".log", ".py", ".txt"}:
            continue
        contents = path.read_text(encoding="utf-8", errors="ignore")
        if any(identifier in contents for identifier in private_ids):
            raise AssertionError(f"Private row/group ID leaked into public artifact: {path}")
    checks.append("public_artifacts_exclude_private_row_and_group_ids")

    for name, record in run.get("artifacts", {}).items():
        path = resolve_project_path(record["path"])
        if artifact(path) != record:
            raise AssertionError(f"Run artifact hash mismatch: {name}")
    checks.append("run_level_artifact_hashes")

    verification = {
        "accessed_splits": ["train", "validation"],
        "check_count": len(checks),
        "checks": checks,
        "completed_at_utc": utc_now(),
        "experiment_id": EXPERIMENT_ID,
        "mismatch_count": 0,
        "private_checkpoint_bytes": checkpoint_bytes,
        "status": "Verified",
        "test_split_accessed": False,
        "validation_split_accessed": True,
        "verifier": artifact(Path(__file__)),
    }
    atomic_json(output, verification)
    run["status"] = "Verified"
    run["verified_at_utc"] = utc_now()
    run["stages"]["independent_verification"] = {
        "artifact": artifact(output),
        "completed_at_utc": utc_now(),
        "status": "Verified",
    }
    atomic_json(run_path, run)
    print(
        json.dumps(
            {
                "check_count": len(checks),
                "experiment_id": EXPERIMENT_ID,
                "mismatch_count": 0,
                "status": "Verified",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
