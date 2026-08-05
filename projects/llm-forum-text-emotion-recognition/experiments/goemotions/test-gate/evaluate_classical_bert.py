#!/usr/bin/env python3
"""Evaluate frozen EXP-018 and EXP-020 units for the EXP-038 test gate."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gc
import os
from pathlib import Path
import platform
import sys
from time import perf_counter
from typing import Any

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import joblib
import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from test_gate_common import (
    artifact,
    finalize_bundle,
    load_config,
    load_labels,
    load_split,
    project_path,
    resolve_project_path,
    verify_artifact,
    verify_formal_preflight,
    write_json,
    write_score_predictions,
)


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-038-frozen-test.json"
DEFAULT_PREFLIGHT = SCRIPT_DIR / "preflight" / "exp-038-classical-bert.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--config-sha256")
    parser.add_argument("--preflight", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def verify_unit(unit: dict[str, Any]) -> None:
    for name in (
        "source_run",
        "source_verification",
        "source_predictions",
        "model",
        "model_config",
        "model_manifest",
    ):
        if name in unit:
            verify_artifact(unit[name])
    source_run = __import__("json").loads(
        resolve_project_path(unit["source_run"]["path"]).read_text(encoding="utf-8")
    )
    if source_run.get("test_split_accessed") is not False:
        raise ValueError(f"Source run already accessed test: {unit['id']}")


def read_reference_probabilities(
    path: Path, labels: tuple[str, ...], rows: int
) -> np.ndarray:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        values = []
        for expected_row, row in enumerate(reader, start=1):
            if expected_row > rows:
                break
            if int(row["row_number"]) != expected_row:
                raise ValueError("Source prediction order changed")
            values.append([float(row[f"prob_{label}"]) for label in labels])
    if len(values) != rows:
        raise ValueError("Source prediction preflight rows are incomplete")
    return np.asarray(values, dtype=np.float64)


def tfidf_probabilities(
    unit: dict[str, Any], texts: list[str], labels: tuple[str, ...]
) -> np.ndarray:
    bundle = joblib.load(verify_artifact(unit["model"]))
    if (
        not isinstance(bundle, dict)
        or tuple(bundle.get("labels", ())) != labels
        or float(bundle.get("threshold", -1)) != float(unit["threshold"])
    ):
        raise ValueError("Frozen EXP-018 model bundle metadata changed")
    features = bundle["vectorizer"].transform(texts)
    return np.asarray(bundle["classifier"].predict_proba(features), dtype=np.float64)


def bert_probabilities(
    unit: dict[str, Any], texts: list[str], batch_size: int
) -> tuple[np.ndarray, float]:
    if not torch.backends.mps.is_available():
        raise RuntimeError("Apple MPS is unavailable")
    tokenizer = AutoTokenizer.from_pretrained(
        resolve_project_path(unit["tokenizer_snapshot"]), local_files_only=True
    )
    model_path = verify_artifact(unit["model"]).parent
    model = AutoModelForSequenceClassification.from_pretrained(
        model_path,
        local_files_only=True,
        use_safetensors=True,
    )
    device = torch.device("mps")
    model.to(device)
    model.eval()
    batches: list[np.ndarray] = []
    started = perf_counter()
    with torch.inference_mode():
        for start in range(0, len(texts), batch_size):
            encoded = tokenizer(
                texts[start : start + batch_size],
                max_length=int(unit["max_sequence_length"]),
                padding=True,
                return_tensors="pt",
                truncation=True,
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            logits = model(**encoded).logits
            batches.append(torch.sigmoid(logits).cpu().numpy())
    elapsed = perf_counter() - started
    del model, tokenizer
    gc.collect()
    torch.mps.empty_cache()
    return np.concatenate(batches, axis=0), elapsed


def run_preflight(config: dict[str, Any], config_sha256: str) -> None:
    test_path = resolve_project_path(config["data"]["test"]["path"])
    if test_path.exists():
        raise RuntimeError("Preflight must finish before test acquisition")
    labels = load_labels(config["data"]["labels"])
    dev_path = verify_artifact(config["data"]["dev"])
    texts, _, _, _ = load_split(dev_path, 5426, labels)
    report: dict[str, Any] = {
        "completed_at_utc": None,
        "config_sha256": config_sha256,
        "experiment_id": "EXP-038",
        "status": "In Progress",
        "test_split_accessed": False,
        "units": {},
    }
    for unit in config["units"][:4]:
        verify_unit(unit)
        reference = read_reference_probabilities(
            resolve_project_path(unit["source_predictions"]["path"]), labels, 2
        )
        if unit["type"] == "sklearn_joblib":
            observed = tfidf_probabilities(unit, texts[:2], labels)
        else:
            observed, _ = bert_probabilities(unit, texts[:2], batch_size=2)
        maximum_difference = float(np.max(np.abs(observed - reference)))
        tolerance = 1e-12 if unit["type"] == "sklearn_joblib" else 2e-6
        if maximum_difference > tolerance:
            raise ValueError(
                f"{unit['id']} dev probability preflight drift: {maximum_difference}"
            )
        report["units"][unit["id"]] = {
            "maximum_probability_absolute_difference": maximum_difference,
            "model_loaded": True,
            "reference_rows": 2,
            "tolerance": tolerance,
        }
    report.update(
        {
            "completed_at_utc": utc_now(),
            "environment": {
                "mps_available": torch.backends.mps.is_available(),
                "platform": platform.platform(),
                "python": platform.python_version(),
                "python_executable": sys.executable,
                "torch": torch.__version__,
            },
            "status": "Passed",
        }
    )
    write_json(DEFAULT_PREFLIGHT, report)
    print("EXP-038 classical/BERT preflight passed")


def run_formal(config: dict[str, Any], config_sha256: str) -> None:
    verify_formal_preflight(config)
    output_root = resolve_project_path(config["output_dir"])
    if output_root.exists():
        raise FileExistsError(f"Append-only EXP-038 output already exists: {output_root}")
    output_root.mkdir(parents=True, exist_ok=False)
    log_path = output_root / "stdout.log"
    test_path = verify_artifact(config["data"]["test"])
    labels = load_labels(config["data"]["labels"])
    texts, gold, _, structural = load_split(test_path, 5427, labels)
    worker = {
        "accessed_splits": ["test"],
        "completed_at_utc": None,
        "config_sha256": config_sha256,
        "experiment_id": "EXP-038",
        "stage": "classical-and-bert-test",
        "started_at_utc": utc_now(),
        "status": "In Progress",
        "test_rows_accessed": len(texts),
        "test_split_accessed": True,
        "units": {},
    }
    write_json(output_root / "classical-bert-worker.json", worker)
    with log_path.open("x", encoding="utf-8") as log:
        log.write(f"{utc_now()} Starting frozen classical/BERT test units\n")
        for unit in config["units"][:4]:
            verify_unit(unit)
            unit_dir = output_root / unit["id"]
            unit_dir.mkdir()
            started = perf_counter()
            if unit["type"] == "sklearn_joblib":
                scores = tfidf_probabilities(unit, texts, labels)
                inference_seconds = perf_counter() - started
            else:
                scores, inference_seconds = bert_probabilities(
                    unit, texts, int(unit["batch_size"])
                )
            if scores.shape != gold.shape or not np.isfinite(scores).all():
                raise ValueError(f"Invalid score matrix for {unit['id']}")
            threshold = float(unit["threshold"])
            predicted = (scores >= threshold).astype(np.uint8)
            write_score_predictions(
                unit_dir / "predictions.csv", gold, predicted, scores, labels
            )
            metrics = finalize_bundle(unit_dir, gold, predicted, labels)
            unit_run = {
                "artifacts": {
                    path.name: artifact(path)
                    for path in sorted(unit_dir.iterdir())
                    if path.is_file()
                },
                "completed_at_utc": utc_now(),
                "config_sha256": config_sha256,
                "inference_seconds": inference_seconds,
                "metrics": {
                    "macro_f1": metrics["macro"]["f1"],
                    "micro_f1": metrics["micro"]["f1"],
                    "subset_accuracy": metrics["subset_accuracy"],
                    "weighted_f1": metrics["weighted"]["f1"],
                },
                "source_experiment_id": unit["source_experiment_id"],
                "status": "Completed; pending independent verification",
                "test_rows_accessed": len(texts),
                "test_split_accessed": True,
                "threshold": threshold,
                "unit_id": unit["id"],
            }
            write_json(unit_dir / "run.json", unit_run)
            worker["units"][unit["id"]] = unit_run["metrics"]
            write_json(output_root / "classical-bert-worker.json", worker)
            log.write(
                f"{utc_now()} {unit['id']} Macro-F1={metrics['macro']['f1']:.6f}\n"
            )
            log.flush()
    worker.update(
        {
            "completed_at_utc": utc_now(),
            "status": "Completed; pending independent verification",
            "test": structural,
        }
    )
    write_json(output_root / "classical-bert-worker.json", worker)


def main() -> None:
    args = parse_args()
    config, config_sha256 = load_config(
        args.config.resolve(),
        args.config_sha256,
        allow_unbound_test=args.preflight,
    )
    if args.preflight:
        run_preflight(config, config_sha256)
    else:
        run_formal(config, config_sha256)


if __name__ == "__main__":
    main()
