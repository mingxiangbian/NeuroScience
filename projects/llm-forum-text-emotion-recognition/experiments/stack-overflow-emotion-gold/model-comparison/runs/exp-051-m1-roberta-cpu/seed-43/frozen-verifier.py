#!/usr/bin/env python3
"""Independently verify an EXP-051 seed from private validation probabilities."""

from __future__ import annotations

import argparse
import ast
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    hamming_loss,
    multilabel_confusion_matrix,
    precision_recall_fscore_support,
)


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-051-m1-roberta-seed-42.json"
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
TOLERANCE = 1e-10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--private-dir", type=Path)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def resolve_project(recorded: str) -> Path:
    path = Path(recorded)
    return path if path.is_absolute() else PROJECT_ROOT / path


def project_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def artifact(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "path": project_path(path), "sha256": sha256_file(path)}


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def assert_close(name: str, actual: float, expected: float, tolerance: float = TOLERANCE) -> None:
    if not math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=tolerance):
        raise ValueError(f"{name} differs: observed={actual}, recorded={expected}")


def metric_bundle(gold: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    values: dict[str, tuple[float, float, float]] = {}
    for average in ("macro", "micro", "weighted"):
        precision, recall, f1, _ = precision_recall_fscore_support(
            gold, predicted, average=average, zero_division=0
        )
        values[average] = (float(precision), float(recall), float(f1))
    precision, recall, f1, support = precision_recall_fscore_support(
        gold, predicted, average=None, zero_division=0
    )
    predicted_support = predicted.sum(axis=0)
    without_surprise = [0, 1, 3, 4, 5]
    _, _, five_label_f1, _ = precision_recall_fscore_support(
        gold[:, without_surprise], predicted[:, without_surprise], average="macro", zero_division=0
    )
    cardinality = predicted.sum(axis=1)
    return {
        "subset_accuracy": float(accuracy_score(gold, predicted)),
        "accuracy_definition": "strict subset/exact-match accuracy",
        "hamming_loss": float(hamming_loss(gold, predicted)),
        "macro": {"precision": values["macro"][0], "recall": values["macro"][1], "f1": values["macro"][2]},
        "micro_f1": values["micro"][2],
        "weighted_f1": values["weighted"][2],
        "five_label_macro_f1_without_surprise": float(five_label_f1),
        "per_label": {
            label: {
                "label_id": index,
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
                "predicted_support": int(predicted_support[index]),
            }
            for index, label in enumerate(LABELS)
        },
        "prediction_diagnostics": {
            "empty_prediction_rows": int(np.sum(cardinality == 0)),
            "predicted_label_cardinality_mean": float(np.mean(cardinality)),
        },
        "primary": {"name": "six_label_macro_f1", "value": values["macro"][2]},
    }


def compare_metrics(name: str, observed: dict[str, Any], recorded: dict[str, Any]) -> None:
    for key in ("subset_accuracy", "hamming_loss", "micro_f1", "weighted_f1", "five_label_macro_f1_without_surprise"):
        assert_close(f"{name}.{key}", observed[key], recorded[key])
    for key in ("precision", "recall", "f1"):
        assert_close(f"{name}.macro.{key}", observed["macro"][key], recorded["macro"][key])
    for label in LABELS:
        for key in ("precision", "recall", "f1"):
            assert_close(f"{name}.{label}.{key}", observed["per_label"][label][key], recorded["per_label"][label][key])
        for key in ("support", "predicted_support"):
            if observed["per_label"][label][key] != recorded["per_label"][label][key]:
                raise ValueError(f"{name}.{label}.{key} differs")
    diagnostics = ("empty_prediction_rows", "predicted_label_cardinality_mean")
    for key in diagnostics:
        assert_close(f"{name}.prediction_diagnostics.{key}", observed["prediction_diagnostics"][key], recorded["prediction_diagnostics"][key])


def select_checkpoint(values: Sequence[float], delta: float) -> dict[str, Any]:
    maximum = max(values)
    eligible = [index + 1 for index, value in enumerate(values) if maximum - value < delta]
    selected = min(eligible)
    return {
        "maximum_fixed_macro_f1": maximum,
        "practical_tie_delta": delta,
        "selected_epoch": selected,
        "selected_fixed_macro_f1": values[selected - 1],
        "selection_deficit_from_maximum": maximum - values[selected - 1],
        "eligible_epochs": eligible,
    }


def select_threshold(gold: np.ndarray, probabilities: np.ndarray, grid: Sequence[float]) -> tuple[float, list[dict[str, float]]]:
    rows = [
        {
            "threshold": float(threshold),
            "macro_f1": metric_bundle(gold, (probabilities >= threshold).astype(np.uint8))["macro"]["f1"],
        }
        for threshold in grid
    ]
    selected = min(rows, key=lambda row: (-row["macro_f1"], abs(row["threshold"] - 0.5), row["threshold"]))
    return selected["threshold"], rows


def fast_f1(gold: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    tp = np.sum((gold == 1) & (predicted == 1), axis=0, dtype=np.int64)
    fp = np.sum((gold == 0) & (predicted == 1), axis=0, dtype=np.int64)
    fn = np.sum((gold == 1) & (predicted == 0), axis=0, dtype=np.int64)
    denominator = 2 * tp + fp + fn
    return np.divide(2 * tp, denominator, out=np.zeros(len(LABELS), dtype=np.float64), where=denominator != 0)


def bootstrap_summary(
    gold: np.ndarray,
    predicted: np.ndarray,
    component_ids: Sequence[str],
    model_seed: int,
    replicates: int,
    namespace: str,
    condition: str,
) -> dict[str, Any]:
    components = sorted(set(component_ids))
    groups = {
        component: np.flatnonzero(np.asarray(component_ids) == component)
        for component in components
    }
    seed_material = f"{namespace}|EXP-051|seed-{model_seed}|{condition}"
    seed = int(hashlib.sha256(seed_material.encode()).hexdigest()[:16], 16) % (2**32)
    rng = np.random.default_rng(seed)
    values = np.zeros((replicates, len(LABELS)), dtype=np.float64)
    for replicate in range(replicates):
        draws = rng.integers(0, len(components), size=len(components))
        indices = np.concatenate([groups[components[index]] for index in draws])
        values[replicate] = fast_f1(gold[indices], predicted[indices])
    point = fast_f1(gold, predicted)

    def interval(series: np.ndarray, point_value: float) -> dict[str, float]:
        lower, upper = np.quantile(series, [0.025, 0.975], method="linear")
        return {"point": float(point_value), "lower": float(lower), "upper": float(upper)}

    return {
        "unit": "duplicate_component_id",
        "component_count": len(components),
        "row_count": len(component_ids),
        "replicates": replicates,
        "seed": seed,
        "seed_material": seed_material,
        "interval": "percentile_2.5_97.5",
        "macro_f1": interval(values.mean(axis=1), float(point.mean())),
        "five_label_macro_f1_without_surprise": interval(
            values[:, [0, 1, 3, 4, 5]].mean(axis=1), float(point[[0, 1, 3, 4, 5]].mean())
        ),
        "per_label_f1": {
            label: interval(values[:, index], float(point[index]))
            for index, label in enumerate(LABELS)
        },
    }


def compare_bootstrap(name: str, observed: dict[str, Any], recorded: dict[str, Any]) -> None:
    for key in ("unit", "component_count", "row_count", "replicates", "seed", "seed_material", "interval"):
        if observed[key] != recorded[key]:
            raise ValueError(f"{name}.{key} differs")
    for group in ("macro_f1", "five_label_macro_f1_without_surprise"):
        for key in ("point", "lower", "upper"):
            assert_close(f"{name}.{group}.{key}", observed[group][key], recorded[group][key])
    for label in LABELS:
        for key in ("point", "lower", "upper"):
            assert_close(
                f"{name}.{label}.{key}",
                observed["per_label_f1"][label][key],
                recorded["per_label_f1"][label][key],
            )


def read_history(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def read_thresholds(path: Path) -> list[dict[str, float]]:
    with path.open("r", encoding="utf-8", newline="") as source:
        return [
            {"threshold": float(row["threshold"]), "macro_f1": float(row["macro_f1"])}
            for row in csv.DictReader(source)
        ]


def verify_artifact(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file() or path.stat().st_size != record["bytes"] or sha256_file(path) != record["sha256"]:
        raise ValueError(f"Artifact drift: {path}")
    return path


def tree_digest(path: Path) -> str:
    files = [
        {
            "bytes": item.stat().st_size,
            "path": str(item.relative_to(path)),
            "sha256": sha256_file(item),
        }
        for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    ]
    return canonical_digest(files)


def source_access_audit(path: Path) -> dict[str, bool]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    load_split = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "load_split"
    )
    function_source = ast.get_source_segment(source, load_split) or ""
    return {
        "explicit_split_allowlist": "if split not in (\"train\", \"validation\")" in function_source,
        "no_test_path_lookup": '[f"{split}_path"]' in function_source and '["test_path"]' not in function_source,
        "no_glob_or_walk_data_access": all(
            token not in function_source for token in (".glob(", ".rglob(", "os.walk(")
        ),
    }


def infer_selected_checkpoint(
    checkpoint: Path,
    validation: Sequence[dict[str, Any]],
    max_length: int,
    batch_size: int,
    device_name: str,
) -> np.ndarray:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if device_name == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS is required to verify the selected checkpoint")
    tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(checkpoint, local_files_only=True)
    device = torch.device(device_name)
    model.to(device)
    model.eval()
    probability_batches = []
    with torch.inference_mode():
        for start in range(0, len(validation), batch_size):
            rows = validation[start : start + batch_size]
            batch = tokenizer(
                [row["text"] for row in rows],
                max_length=max_length,
                padding=True,
                return_tensors="pt",
                truncation=True,
            ).to(device)
            probability_batches.append(
                torch.sigmoid(model(**batch).logits).detach().cpu().numpy()
            )
    if device.type == "mps":
        torch.mps.synchronize()
    return np.concatenate(probability_batches, axis=0).astype(np.float32, copy=False)


def verify() -> dict[str, Any]:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.seed not in config["authorization"]["seeds"]:
        raise PermissionError("Seed is not authorized by the frozen run contract")
    run_dir = (args.run_dir or resolve_project(config["execution"]["public_run_root"]) / f"seed-{args.seed}").resolve()
    private_dir = (args.private_dir or resolve_project(config["execution"]["private_run_root"]) / f"seed-{args.seed}").resolve()
    output = run_dir / "verification.json"
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    shared = json.loads((run_dir / "frozen-shared-config.json").read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": bool(condition), "detail": detail})

    check("run completed", run["status"] == "Completed")
    check("experiment identity", run["experiment_id"] == "EXP-051" and run["seed"] == args.seed)
    check(
        "single-seed authorization",
        config["authorization"]["seeds"] == [args.seed] and args.seed in (42, 43, 44),
    )
    check("split access", run["accessed_splits"] == ["train", "validation"] and run["validation_split_accessed"] is True)
    check("test sealed", run["test_split_accessed"] is False and config["authorization"]["test_access"] is False)
    check("unrequested seeds sealed", len(config["authorization"]["seeds"]) == 1)
    check("labels frozen", tuple(run["data"]["labels"]) == LABELS)

    for record in run["artifacts"]["frozen_sources"].values():
        verify_artifact(record)
    check(
        "run config matches frozen config",
        sha256_file(args.config.resolve()) == run["artifacts"]["frozen_sources"]["config"]["sha256"],
    )
    amendment = config.get("authorization_amendment")
    if amendment is not None:
        frozen_amendment = run["artifacts"]["frozen_sources"].get("authorization-amendment")
        check(
            "authorization amendment frozen",
            frozen_amendment is not None and frozen_amendment["sha256"] == amendment["sha256"],
        )
    prior_gate = config.get("prior_seed_gate")
    if prior_gate is not None:
        recorded_gate = run.get("prior_seed_gate") or {}
        check(
            "prior seed gate recorded",
            recorded_gate.get("seed") == prior_gate["seed"]
            and recorded_gate.get("status") == prior_gate["status"]
            and recorded_gate.get("verification_check_count") == prior_gate["check_count"]
            and recorded_gate.get("test_split_accessed") is False,
        )
        check(
            "prior seed run unchanged",
            recorded_gate.get("run", {}).get("sha256") == prior_gate["run_sha256"]
            and sha256_file(resolve_project(prior_gate["run_path"])) == prior_gate["run_sha256"],
        )
        check(
            "prior seed verification unchanged",
            recorded_gate.get("verification", {}).get("sha256")
            == prior_gate["verification_sha256"]
            and sha256_file(resolve_project(prior_gate["verification_path"]))
            == prior_gate["verification_sha256"],
        )
    for key in ("history", "threshold_grid", "metrics_fixed", "metrics_shared_threshold", "bootstrap", "selection", "report", "stdout_log", "private_manifest", "validation_predictions_private"):
        verify_artifact(run["artifacts"][key])
    for condition in ("fixed-0.5", "shared-threshold"):
        verify_artifact(run["artifacts"]["tables"][condition]["per_label"])
        verify_artifact(run["artifacts"]["tables"][condition]["confusion"])
    check("selected checkpoint tree hash", tree_digest(resolve_project(run["artifacts"]["selected_checkpoint_private"]["path"])) == run["artifacts"]["selected_checkpoint_private"]["sha256"])

    train_path = resolve_project(shared["data"]["train_path"])
    validation_path = resolve_project(shared["data"]["validation_path"])
    check("train hash", sha256_file(train_path) == shared["data"]["train_sha256"])
    check("validation hash", sha256_file(validation_path) == shared["data"]["validation_sha256"])
    validation = [json.loads(line) for line in validation_path.read_text(encoding="utf-8").splitlines()]
    check("validation rows", len(validation) == shared["data"]["validation_rows"])
    gold = np.asarray([row["labels"] for row in validation], dtype=np.uint8)
    component_ids = [row["component_id"] for row in validation]
    private = np.load(private_dir / "validation-predictions.npz", allow_pickle=False)
    probabilities = private["probabilities"]
    check("probability shape", probabilities.shape == (5, 720, 6), list(probabilities.shape))
    check("probabilities finite", np.isfinite(probabilities).all())
    check("sample order", private["sample_ids"].tolist() == [row["sample_id"] for row in validation])
    check("component order", private["component_ids"].tolist() == component_ids)
    check("private gold independently matches", np.array_equal(private["gold"], gold))

    fixed_threshold = shared["evaluation"]["fixed_threshold"]
    epoch_metrics = [metric_bundle(gold, (epoch >= fixed_threshold).astype(np.uint8)) for epoch in probabilities]
    history = read_history(run_dir / "history.csv")
    check("five history rows", len(history) == 5)
    for index, (metric, row) in enumerate(zip(epoch_metrics, history), start=1):
        check(f"epoch {index} identity", int(row["epoch"]) == index and int(row["optimizer_steps"]) == index * 210)
        check(f"epoch {index} fixed Macro-F1", math.isclose(metric["macro"]["f1"], float(row["fixed_macro_f1"]), rel_tol=0.0, abs_tol=TOLERANCE))
        check(f"epoch {index} finite losses", math.isfinite(float(row["train_loss"])) and math.isfinite(float(row["validation_loss"])))
        check(f"epoch {index} order digest", len(row["batch_order_sha256"]) == 64)

    selection = select_checkpoint(
        [metric["macro"]["f1"] for metric in epoch_metrics],
        shared["evaluation"]["practical_tie_delta"],
    )
    recorded_selection = json.loads((run_dir / "selection.json").read_text(encoding="utf-8"))
    check("checkpoint selection", selection == recorded_selection == run["selection"], selection)
    selected_probabilities = probabilities[selection["selected_epoch"] - 1]
    checkpoint = resolve_project(run["artifacts"]["selected_checkpoint_private"]["path"])
    replay_probabilities = infer_selected_checkpoint(
        checkpoint,
        validation,
        shared["models"]["m1"]["max_sequence_length"],
        config["execution"]["evaluation_batch_size"],
        run["environment"]["device"],
    )
    replay_max_abs = float(np.max(np.abs(replay_probabilities - selected_probabilities)))
    check("selected checkpoint reproduces saved probabilities", replay_max_abs <= 1e-5, replay_max_abs)
    selected_threshold, threshold_rows = select_threshold(
        gold, selected_probabilities, shared["evaluation"]["shared_threshold_grid"]
    )
    recorded_thresholds = read_thresholds(run_dir / "threshold-grid.csv")
    check("threshold grid length", len(recorded_thresholds) == len(threshold_rows) == 19)
    check("shared threshold selection", selected_threshold == run["threshold_selection"]["selected_threshold"])
    for observed, recorded in zip(threshold_rows, recorded_thresholds):
        assert_close("threshold value", observed["threshold"], recorded["threshold"])
        assert_close("threshold Macro-F1", observed["macro_f1"], recorded["macro_f1"])

    conditions = {
        "fixed_0.5": (fixed_threshold, "fixed-0.5"),
        "shared_threshold": (selected_threshold, f"shared-{selected_threshold:.2f}"),
    }
    recorded_bootstrap = json.loads((run_dir / "bootstrap.json").read_text(encoding="utf-8"))
    for name, (threshold, bootstrap_condition) in conditions.items():
        predicted = (selected_probabilities >= threshold).astype(np.uint8)
        private_key = "fixed_predictions" if name == "fixed_0.5" else "shared_threshold_predictions"
        check(f"{name} private predictions", np.array_equal(private[private_key], predicted))
        observed_metrics = metric_bundle(gold, predicted)
        compare_metrics(name, observed_metrics, run["metrics"][name])
        file_name = "metrics-fixed-0.5.json" if name == "fixed_0.5" else "metrics-shared-threshold.json"
        compare_metrics(name + ".file", observed_metrics, json.loads((run_dir / file_name).read_text(encoding="utf-8")))
        matrix = multilabel_confusion_matrix(gold, predicted)
        confusion_path = run_dir / ("multilabel-confusion-fixed-0.5.csv" if name == "fixed_0.5" else "multilabel-confusion-shared-threshold.csv")
        with confusion_path.open("r", encoding="utf-8", newline="") as source:
            recorded_rows = list(csv.DictReader(source))
        check(f"{name} confusion rows", len(recorded_rows) == len(LABELS))
        for index, row in enumerate(recorded_rows):
            tn, fp, fn, tp = matrix[index].ravel()
            check(
                f"{name} confusion {LABELS[index]}",
                [int(row[key]) for key in ("tn", "fp", "fn", "tp")] == [int(tn), int(fp), int(fn), int(tp)],
            )
        observed_bootstrap = bootstrap_summary(
            gold,
            predicted,
            component_ids,
            args.seed,
            shared["evaluation"]["bootstrap"]["replicates"],
            shared["evaluation"]["bootstrap"]["seed_namespace"],
            bootstrap_condition,
        )
        compare_bootstrap(name, observed_bootstrap, recorded_bootstrap[name])

    audit = source_access_audit(run_dir / "frozen-runner.py")
    for name, passed in audit.items():
        check(f"source access audit: {name}", passed)
    public_files = [
        path for path in run_dir.rglob("*")
        if path.is_file() and not path.name.startswith("frozen-")
    ]
    public_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in public_files
        if path.suffix not in (".npz", ".safetensors")
    )
    check(
        "public artifacts contain no substantive raw text",
        all(row["text"] not in public_text for row in validation if len(row["text"]) >= 24),
    )
    check("public artifacts contain no sample IDs", all(row["sample_id"] not in public_text for row in validation))
    check("public artifacts contain no component IDs", all(row["component_id"] not in public_text for row in validation))
    check("private predictions ignored", subprocess_check_ignore(private_dir / "validation-predictions.npz"))
    check("private checkpoint ignored", subprocess_check_ignore(private_dir / "selected-checkpoint" / "model.safetensors"))
    check("wall-time budget", run["resource_usage"]["wall_seconds"] <= config["execution"]["maximum_wall_minutes"] * 60)
    observed_peak = (
        run["resource_usage"]["peak_mps_driver_gb"]
        if run["environment"]["device"] == "mps"
        else run["resource_usage"]["peak_process_rss_gb"]
    )
    check("memory budget", observed_peak <= config["execution"]["maximum_peak_memory_gb"])

    failed = [item["name"] for item in checks if not item["passed"]]
    verification = {
        "schema_version": "exp-051-m1-verification-v1",
        "experiment_id": "EXP-051",
        "seed": args.seed,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "Passed" if not failed else "Failed",
        "check_count": len(checks),
        "failed_checks": failed,
        "checks": checks,
        "recomputed": {
            "selected_epoch": selection["selected_epoch"],
            "fixed_macro_f1": run["metrics"]["fixed_0.5"]["macro"]["f1"],
            "shared_threshold": selected_threshold,
            "calibrated_macro_f1": run["metrics"]["shared_threshold"]["macro"]["f1"],
        },
        "test_split_accessed": False,
    }
    atomic_json(output, verification)
    if failed:
        raise ValueError(f"EXP-051 verification failed: {failed}")
    return verification


def subprocess_check_ignore(path: Path) -> bool:
    import subprocess

    result = subprocess.run(
        ["git", "check-ignore", "-q", str(path)], cwd=PROJECT_ROOT.parents[1], check=False
    )
    return result.returncode == 0


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
