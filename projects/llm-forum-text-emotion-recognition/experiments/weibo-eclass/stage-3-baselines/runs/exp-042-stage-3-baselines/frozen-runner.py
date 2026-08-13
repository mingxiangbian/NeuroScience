#!/usr/bin/env python3
"""Run the frozen EXP-042 Weibo EClass Stage 3 train/dev baselines."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import json
import logging
import math
import os
from pathlib import Path
import platform
import random
import shutil
import site
import statistics
import subprocess
import sys
import time
from typing import Any, Iterable, Sequence


EXPERIMENT_ID = "EXP-042"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
CONFIG_PATH = SCRIPT_DIR / "config.json"
VIEWS = ("target_only", "previous_context")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("initialize")
    subparsers.add_parser("m0-m1")
    m2 = subparsers.add_parser("m2")
    m2.add_argument("--view", required=True, choices=VIEWS)
    m2.add_argument("--seed", required=True, type=int)
    subparsers.add_parser("aggregate")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Project-relative path escapes project root: {value}")
    return path


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "bytes": path.stat().st_size,
        "path": project_path(path),
        "sha256": sha256_file(path),
    }


def tree_artifact(root: Path) -> dict[str, Any]:
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
    return {
        "file_count": len(files),
        "files": files,
        "path": project_path(root),
        "total_bytes": sum(item["bytes"] for item in files),
    }


def write_private_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.chmod(temporary, 0o600)
    temporary.replace(path)
    os.chmod(path, 0o600)


def setup_logger(output_dir: Path) -> logging.Logger:
    logger = logging.getLogger("exp-042")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s")
    formatter.converter = time.gmtime
    file_handler = logging.FileHandler(output_dir / "stdout.log", mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("EXP-042 config ID mismatch")
    if config.get("tier") != "Major" or config.get("status") != "Registered":
        raise ValueError("EXP-042 must remain a registered Major experiment")
    if not config["data"]["validation_access"] or config["data"]["test_access"]:
        raise ValueError("EXP-042 split gate drift")
    if config["m2"]["seeds"] != [42, 43, 44] or config["prompt"]["views"] != list(VIEWS):
        raise ValueError("EXP-042 seed or view drift")

    implementation = config["implementation"]
    bindings = (
        (implementation["runner_path"], implementation["runner_sha256"]),
        (implementation["test_path"], implementation["test_sha256"]),
        (implementation["verifier_path"], implementation["verifier_sha256"]),
        (
            implementation["requirements_lock_path"],
            implementation["requirements_lock_sha256"],
        ),
        (config["prompt"]["path"], config["prompt"]["sha256"]),
        (config["data"]["manifest_path"], config["data"]["manifest_sha256"]),
        (config["m2"]["model_manifest_path"], config["m2"]["model_manifest_sha256"]),
    )
    for relative, expected in bindings:
        if expected == "PENDING":
            raise ValueError(f"Implementation hash is not frozen: {relative}")
        path = resolve_project_path(relative)
        if sha256_file(path) != expected:
            raise ValueError(f"Frozen artifact hash mismatch: {relative}")
    if not resolve_project_path(implementation["protocol_path"]).is_file():
        raise FileNotFoundError(implementation["protocol_path"])
    return config


def run_dir(config: dict[str, Any]) -> Path:
    return resolve_project_path(config["run_dir"])


def private_root(config: dict[str, Any]) -> Path:
    return resolve_project_path(config["private_root"])


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return {
        "branch": branch or "detached",
        "commit": commit,
        "dirty": bool(status),
        "dirty_path_count": len(status),
    }


def environment_gate(config: dict[str, Any]) -> dict[str, Any]:
    if os.environ.get("PYTHONNOUSERSITE") != "1" or os.environ.get("PIP_USER") != "0":
        raise RuntimeError("PYTHONNOUSERSITE=1 and PIP_USER=0 are required")
    if site.ENABLE_USER_SITE:
        raise RuntimeError("Python user site is enabled")

    import numpy
    import sklearn
    import torch
    import transformers

    prefix = Path(sys.prefix).resolve()
    modules = {
        "numpy": Path(numpy.__file__).resolve(),
        "scikit-learn": Path(sklearn.__file__).resolve(),
        "torch": Path(torch.__file__).resolve(),
        "transformers": Path(transformers.__file__).resolve(),
    }
    outside = {name: str(path) for name, path in modules.items() if prefix not in path.parents}
    if outside:
        raise RuntimeError(f"Dependencies outside environment: {outside}")

    frozen = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    lock = resolve_project_path(config["implementation"]["requirements_lock_path"])
    if frozen != lock.read_text(encoding="utf-8").strip():
        raise RuntimeError("Runtime pip freeze differs from requirements-lock.txt")
    pip_check = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not torch.backends.mps.is_built() or not torch.backends.mps.is_available():
        raise RuntimeError("Apple MPS is unavailable; EXP-042 must not fall back to CPU")

    return {
        "architecture": platform.machine(),
        "device": "mps",
        "environment_prefix": str(prefix),
        "executable": sys.executable,
        "mps_available": True,
        "package_paths": {name: str(path) for name, path in modules.items()},
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "safetensors", "scikit-learn", "torch", "transformers")
        },
        "pip_check": pip_check or "No broken requirements found.",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "requirements_lock": artifact(lock),
    }


def verify_model(config: dict[str, Any]) -> dict[str, Any]:
    m2 = config["m2"]
    manifest_path = resolve_project_path(m2["model_manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["repo_id"] != m2["repo_id"] or manifest["revision"] != m2["revision"]:
        raise ValueError("M2 model identity drift")
    model_root = resolve_project_path(m2["local_path"])
    verified = []
    for expected in manifest["snapshot"]["files"]:
        path = model_root / expected["path"]
        current = {
            "bytes": path.stat().st_size,
            "path": expected["path"],
            "sha256": sha256_file(path),
        }
        if current != expected:
            raise ValueError(f"M2 model file drift: {expected['path']}")
        verified.append(current)
    return {
        "files": verified,
        "manifest": artifact(manifest_path),
        "repo_id": manifest["repo_id"],
        "revision": manifest["revision"],
        "snapshot": project_path(model_root),
        "total_bytes": sum(item["bytes"] for item in verified),
    }


def load_rows(config: dict[str, Any], split: str) -> list[dict[str, Any]]:
    if split not in ("train", "validation"):
        raise ValueError(f"Split is not authorized: {split}")
    data = config["data"]
    path = resolve_project_path(data[f"{split}_path"])
    if sha256_file(path) != data[f"{split}_sha256"]:
        raise ValueError(f"Frozen {split} hash mismatch")
    expected_keys = {
        "ambiguous_target",
        "context_available",
        "group_id",
        "label",
        "protocol_id",
        "sample_id",
        "schema_version",
        "views",
    }
    rows = []
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            row = json.loads(line)
            if set(row) != expected_keys:
                raise ValueError(f"Unexpected {split} schema at line {line_number}")
            if row["protocol_id"] != data["protocol_id"] or row["label"] not in data["labels"]:
                raise ValueError(f"Protocol or label drift at {split}:{line_number}")
            target = row["views"]["target_only"]["target"]
            paired = row["views"]["previous_context"]
            if not isinstance(target, str) or not target or paired["target"] != target:
                raise ValueError(f"Paired target mismatch at {split}:{line_number}")
            if bool(paired["previous"]) != bool(row["context_available"]):
                raise ValueError(f"Context flag mismatch at {split}:{line_number}")
            rows.append(row)
    if len(rows) != data[f"{split}_rows"]:
        raise ValueError(f"Frozen {split} row count mismatch")
    if len({row["sample_id"] for row in rows}) != len(rows):
        raise ValueError(f"Duplicate sample IDs in {split}")
    return rows


def load_prompt(config: dict[str, Any]) -> dict[str, Any]:
    return json.loads(resolve_project_path(config["prompt"]["path"]).read_text(encoding="utf-8"))


def render_view(prompt: dict[str, Any], row: dict[str, Any], view: str) -> str:
    target = row["views"]["target_only"]["target"]
    if view == "target_only":
        return prompt["target_only_template"].format(target=target)
    if view != "previous_context":
        raise ValueError(view)
    previous = row["views"]["previous_context"]["previous"]
    if not previous:
        return prompt["target_only_template"].format(target=target)
    return prompt["previous_context_template"].format(previous=previous, target=target)


def classification_metrics(
    gold: Sequence[str], predicted: Sequence[str], labels: Sequence[str]
) -> dict[str, Any]:
    from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

    if len(gold) != len(predicted) or not gold:
        raise ValueError("Metric inputs must be non-empty and aligned")
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
    matrix = confusion_matrix(gold, predicted, labels=list(labels))
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
        "confusion_matrix": matrix.astype(int).tolist(),
    }


def metrics_by_slice(
    rows: Sequence[dict[str, Any]], predicted: Sequence[str], labels: Sequence[str]
) -> dict[str, Any]:
    selectors = {
        "all": [True] * len(rows),
        "context_available": [bool(row["context_available"]) for row in rows],
        "first_clause": [not bool(row["context_available"]) for row in rows],
    }
    result = {}
    for name, mask in selectors.items():
        gold = [row["label"] for row, keep in zip(rows, mask) if keep]
        chosen = [value for value, keep in zip(predicted, mask) if keep]
        result[name] = classification_metrics(gold, chosen, labels)
    return result


def write_metric_tables(output_dir: Path, metrics: dict[str, Any], labels: Sequence[str]) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    metrics_path = output_dir / "metrics.json"
    atomic_json(metrics_path, metrics)

    per_class_path = output_dir / "per_class_metrics.csv"
    with per_class_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(
            target,
            fieldnames=("slice", "label", "precision", "recall", "f1", "support"),
        )
        writer.writeheader()
        for slice_name, slice_metrics in metrics["slices"].items():
            for label in labels:
                writer.writerow(
                    {
                        "slice": slice_name,
                        "label": label,
                        **slice_metrics["per_class"][label],
                    }
                )

    matrix_path = output_dir / "confusion_matrix.csv"
    with matrix_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(["gold\\predicted", *labels])
        for label, values in zip(labels, metrics["slices"]["all"]["confusion_matrix"]):
            writer.writerow([label, *values])
    return {
        "confusion_matrix": artifact(matrix_path),
        "metrics": artifact(metrics_path),
        "per_class_metrics": artifact(per_class_path),
    }


def write_predictions(
    path: Path,
    rows: Sequence[dict[str, Any]],
    predicted: Sequence[str],
    labels: Sequence[str],
    scores: Sequence[Sequence[float]] | None,
    score_prefix: str,
) -> dict[str, Any]:
    fieldnames = ["sample_id", "group_id", "context_available", "gold", "prediction"]
    if scores is not None:
        fieldnames.extend(f"{score_prefix}__{label}" for label in labels)
    records = []
    for index, (row, prediction) in enumerate(zip(rows, predicted)):
        record: dict[str, Any] = {
            "sample_id": row["sample_id"],
            "group_id": row["group_id"],
            "context_available": int(bool(row["context_available"])),
            "gold": row["label"],
            "prediction": prediction,
        }
        if scores is not None:
            for label, value in zip(labels, scores[index]):
                record[f"{score_prefix}__{label}"] = f"{float(value):.17g}"
        records.append(record)
    write_private_csv(path, fieldnames, records)
    return artifact(path)


def read_run(config: dict[str, Any]) -> dict[str, Any]:
    path = run_dir(config) / "run.json"
    if not path.is_file():
        raise FileNotFoundError("Run initialize before later EXP-042 stages")
    run = json.loads(path.read_text(encoding="utf-8"))
    if run.get("experiment_id") != EXPERIMENT_ID or run.get("test_split_accessed"):
        raise ValueError("EXP-042 run metadata drift")
    return run


def save_run(config: dict[str, Any], run: dict[str, Any]) -> None:
    atomic_json(run_dir(config) / "run.json", run)


def append_command(run: dict[str, Any], command: str) -> None:
    run["command_history"].append(command)


def run_initialize(config: dict[str, Any]) -> None:
    public = run_dir(config)
    private = private_root(config)
    if public.exists() and any(public.iterdir()):
        raise FileExistsError(f"Append-only public run directory is not empty: {public}")
    if private.exists() and any(private.iterdir()):
        raise FileExistsError(f"Append-only private run directory is not empty: {private}")
    public.mkdir(parents=True, exist_ok=True)
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(private, 0o700)
    logger = setup_logger(public)
    started = time.perf_counter()
    logger.info("Initializing EXP-042")

    environment = environment_gate(config)
    model = verify_model(config)
    train_path = resolve_project_path(config["data"]["train_path"])
    validation_path = resolve_project_path(config["data"]["validation_path"])
    if sha256_file(train_path) != config["data"]["train_sha256"]:
        raise ValueError("Train input hash drift")
    if sha256_file(validation_path) != config["data"]["validation_sha256"]:
        raise ValueError("Validation input hash drift")

    frozen_files = {
        "frozen-config.json": CONFIG_PATH,
        "frozen-protocol.md": resolve_project_path(config["implementation"]["protocol_path"]),
        "frozen-requirements-lock.txt": resolve_project_path(
            config["implementation"]["requirements_lock_path"]
        ),
        "frozen-runner.py": resolve_project_path(config["implementation"]["runner_path"]),
        "frozen-test.py": resolve_project_path(config["implementation"]["test_path"]),
        "frozen-verifier.py": resolve_project_path(config["implementation"]["verifier_path"]),
    }
    for name, source in frozen_files.items():
        shutil.copy2(source, public / name)

    run = {
        "accessed_splits": [],
        "command_history": [
            f"{sys.executable} {project_path(Path(__file__))} initialize"
        ],
        "config": artifact(CONFIG_PATH),
        "data": {
            "manifest": artifact(resolve_project_path(config["data"]["manifest_path"])),
            "protocol_id": config["data"]["protocol_id"],
            "train": artifact(train_path),
            "validation": artifact(validation_path),
        },
        "environment": environment,
        "experiment_id": EXPERIMENT_ID,
        "git": git_metadata(),
        "model": model,
        "private_root": project_path(private),
        "resource_usage": {
            "api_cost_usd": 0,
            "device": "mps",
            "elapsed_seconds": time.perf_counter() - started,
        },
        "rq_ids": config["rq_ids"],
        "stage": config["stage"],
        "stages": {"initialize": {"completed_at_utc": utc_now(), "status": "Passed"}},
        "started_at_utc": utc_now(),
        "status": "In Progress",
        "test_split_accessed": False,
        "tier": "Major",
        "validation_split_accessed": False,
    }
    save_run(config, run)
    logger.info("EXP-042 initialization passed")


def run_m0_m1(config: dict[str, Any]) -> None:
    public = run_dir(config)
    logger = setup_logger(public)
    run = read_run(config)
    if run["stages"].get("initialize", {}).get("status") != "Passed":
        raise RuntimeError("EXP-042 initialization has not passed")
    if "m0_m1" in run["stages"]:
        raise FileExistsError("EXP-042 M0/M1 stage is append-only")

    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import FeatureUnion
    from sklearn.svm import LinearSVC

    started_at = utc_now()
    started = time.perf_counter()
    train = load_rows(config, "train")
    validation = load_rows(config, "validation")
    labels = config["data"]["labels"]
    prompt = load_prompt(config)

    counts = Counter(row["label"] for row in train)
    majority_label = counts.most_common(1)[0][0]
    if majority_label != config["m0"]["expected_majority_label"]:
        raise ValueError("M0 train-majority label differs from the frozen expectation")
    m0_predictions = [majority_label] * len(validation)
    m0_metrics = {
        "label_counts": {label: counts[label] for label in labels},
        "majority_label": majority_label,
        "model_id": "M0",
        "slices": metrics_by_slice(validation, m0_predictions, labels),
        "view": "target_only",
    }
    m0_public = public / "m0" / "majority"
    m0_artifacts = write_metric_tables(m0_public, m0_metrics, labels)
    m0_private = private_root(config) / "m0" / "predictions.csv"
    m0_prediction_artifact = write_predictions(
        m0_private,
        validation,
        m0_predictions,
        labels,
        None,
        "score",
    )

    m1_results = {}
    for view in VIEWS:
        logger.info("Fitting M1 view=%s", view)
        train_texts = [render_view(prompt, row, view) for row in train]
        validation_texts = [render_view(prompt, row, view) for row in validation]
        m1 = config["m1"]
        vectorizer = FeatureUnion(
            [
                (
                    "word",
                    TfidfVectorizer(
                        ngram_range=tuple(m1["word_ngram_range"]),
                        min_df=m1["min_df"],
                        sublinear_tf=m1["sublinear_tf"],
                        lowercase=m1["lowercase"],
                    ),
                ),
                (
                    "char",
                    TfidfVectorizer(
                        analyzer=m1["char_analyzer"],
                        ngram_range=tuple(m1["char_ngram_range"]),
                        min_df=m1["min_df"],
                        sublinear_tf=m1["sublinear_tf"],
                        lowercase=m1["lowercase"],
                    ),
                ),
            ]
        )
        fit_started = time.perf_counter()
        train_matrix = vectorizer.fit_transform(train_texts)
        validation_matrix = vectorizer.transform(validation_texts)
        classifier = LinearSVC(
            C=m1["c"],
            class_weight=m1["class_weight"],
            random_state=m1["random_state"],
        )
        classifier.fit(train_matrix, [row["label"] for row in train])
        predictions = classifier.predict(validation_matrix).tolist()
        raw_scores = classifier.decision_function(validation_matrix)
        if raw_scores.shape != (len(validation), len(labels)) or not np.isfinite(raw_scores).all():
            raise ValueError(f"M1 produced invalid decision scores for {view}")
        class_indices = {label: index for index, label in enumerate(classifier.classes_.tolist())}
        if set(class_indices) != set(labels):
            raise ValueError("M1 class set drift")
        scores = raw_scores[:, [class_indices[label] for label in labels]]
        metrics = {
            "classifier": m1,
            "feature_count": int(train_matrix.shape[1]),
            "fit_seconds": time.perf_counter() - fit_started,
            "model_id": "M1",
            "slices": metrics_by_slice(validation, predictions, labels),
            "train_rows": len(train),
            "validation_rows": len(validation),
            "view": view,
        }
        condition_public = public / "m1" / view
        public_artifacts = write_metric_tables(condition_public, metrics, labels)
        private_predictions = private_root(config) / "m1" / view / "predictions.csv"
        prediction_artifact = write_predictions(
            private_predictions,
            validation,
            predictions,
            labels,
            scores.tolist(),
            "decision",
        )
        m1_results[view] = {
            "artifacts": public_artifacts,
            "metrics": metrics,
            "private_predictions": prediction_artifact,
        }
        logger.info(
            "M1 view=%s macro_f1=%.6f accuracy=%.6f features=%d",
            view,
            metrics["slices"]["all"]["macro_f1"],
            metrics["slices"]["all"]["accuracy"],
            metrics["feature_count"],
        )

    summary = {
        "accessed_splits": ["train", "validation"],
        "completed_at_utc": utc_now(),
        "duration_seconds": time.perf_counter() - started,
        "experiment_id": EXPERIMENT_ID,
        "m0": {
            "artifacts": m0_artifacts,
            "metrics": m0_metrics,
            "private_predictions": m0_prediction_artifact,
        },
        "m1": m1_results,
        "status": "Completed",
        "test_split_accessed": False,
        "validation_split_accessed": True,
    }
    summary_path = public / "m0-m1.json"
    atomic_json(summary_path, summary)
    append_command(run, f"{sys.executable} {project_path(Path(__file__))} m0-m1")
    run["accessed_splits"] = ["train", "validation"]
    run["validation_split_accessed"] = True
    run["stages"]["m0_m1"] = {
        "artifact": artifact(summary_path),
        "completed_at_utc": utc_now(),
        "duration_seconds": summary["duration_seconds"],
        "started_at_utc": started_at,
        "status": "Completed",
    }
    run["resource_usage"]["elapsed_seconds"] += summary["duration_seconds"]
    save_run(config, run)
    logger.info("M0/M1 completed")


class EncodedDataset:
    def __init__(self, encodings: dict[str, list[list[int]]], labels: Sequence[int]) -> None:
        self.encodings = encodings
        self.labels = list(labels)

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, index: int) -> dict[str, Any]:
        item = {key: values[index] for key, values in self.encodings.items()}
        item["labels"] = self.labels[index]
        return item


def seed_everything(seed: int) -> None:
    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.mps.manual_seed(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)


def encoder_texts(
    tokenizer: Any,
    prompt: dict[str, Any],
    rows: Sequence[dict[str, Any]],
    view: str,
    max_length: int,
) -> tuple[list[str], dict[str, Any]]:
    texts = [render_view(prompt, row, view) for row in rows]
    lengths = [len(tokenizer.encode(text, add_special_tokens=True)) for text in texts]
    if max(lengths) > max_length:
        raise ValueError(
            f"M2 {view} input exceeds {max_length} tokens; target-preserving truncation was not preregistered"
        )
    return texts, {
        "count": len(lengths),
        "max": max(lengths),
        "mean": statistics.fmean(lengths),
        "min": min(lengths),
    }


def optimizer_groups(model: Any, weight_decay: float, exclusions: Sequence[str]) -> list[dict[str, Any]]:
    decay = []
    no_decay = []
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        if any(name.endswith(exclusion) for exclusion in exclusions):
            no_decay.append(parameter)
        else:
            decay.append(parameter)
    return [
        {"params": decay, "weight_decay": weight_decay},
        {"params": no_decay, "weight_decay": 0.0},
    ]


def linear_schedule(step: int, warmup_steps: int, total_steps: int) -> float:
    if step < warmup_steps:
        return float(step) / float(max(1, warmup_steps))
    return max(
        0.0,
        float(total_steps - step) / float(max(1, total_steps - warmup_steps)),
    )


def evaluate_encoder(model: Any, loader: Any, device: Any) -> tuple[float, list[int], list[int], list[list[float]]]:
    import torch

    model.eval()
    losses = []
    gold = []
    predicted = []
    probabilities = []
    with torch.no_grad():
        for batch in loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            result = model(**batch)
            if not torch.isfinite(result.loss):
                raise ValueError("M2 validation loss is not finite")
            probs = torch.softmax(result.logits, dim=-1)
            losses.append(float(result.loss.detach().cpu()))
            gold.extend(batch["labels"].detach().cpu().tolist())
            predicted.extend(probs.argmax(dim=-1).detach().cpu().tolist())
            probabilities.extend(probs.detach().cpu().tolist())
    return statistics.fmean(losses), gold, predicted, probabilities


def run_m2(config: dict[str, Any], view: str, seed: int) -> None:
    public = run_dir(config)
    logger = setup_logger(public)
    run = read_run(config)
    if run["stages"].get("m0_m1", {}).get("status") != "Completed":
        raise RuntimeError("M0/M1 must complete before M2")
    if seed not in config["m2"]["seeds"]:
        raise ValueError(f"Seed is not frozen: {seed}")
    stage_key = f"m2__{view}__seed_{seed}"
    if stage_key in run["stages"]:
        raise FileExistsError(f"M2 stage is append-only: {stage_key}")

    os.environ.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "TRANSFORMERS_OFFLINE": "1",
        }
    )
    import numpy as np
    import torch
    from torch.optim.lr_scheduler import LambdaLR
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, DataCollatorWithPadding

    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS became unavailable before M2")
    seed_everything(seed)
    started_at = utc_now()
    started = time.perf_counter()
    logger.info("Starting M2 view=%s seed=%d", view, seed)

    train = load_rows(config, "train")
    validation = load_rows(config, "validation")
    labels = config["data"]["labels"]
    label_to_id = {label: index for index, label in enumerate(labels)}
    id_to_label = {index: label for label, index in label_to_id.items()}
    prompt = load_prompt(config)
    m2 = config["m2"]
    model_path = resolve_project_path(m2["local_path"])
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    train_texts, train_lengths = encoder_texts(
        tokenizer, prompt, train, view, m2["max_sequence_length"]
    )
    validation_texts, validation_lengths = encoder_texts(
        tokenizer, prompt, validation, view, m2["max_sequence_length"]
    )
    train_encodings = tokenizer(
        train_texts,
        add_special_tokens=True,
        padding=False,
        truncation=False,
    )
    validation_encodings = tokenizer(
        validation_texts,
        add_special_tokens=True,
        padding=False,
        truncation=False,
    )
    train_dataset = EncodedDataset(train_encodings, [label_to_id[row["label"]] for row in train])
    validation_dataset = EncodedDataset(
        validation_encodings, [label_to_id[row["label"]] for row in validation]
    )
    collator = DataCollatorWithPadding(tokenizer=tokenizer, padding=True, return_tensors="pt")
    generator = torch.Generator()
    generator.manual_seed(seed)
    train_loader = DataLoader(
        train_dataset,
        batch_size=m2["train_batch_size"],
        shuffle=m2["shuffle"],
        drop_last=m2["drop_last"],
        num_workers=m2["num_workers"],
        collate_fn=collator,
        generator=generator,
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=m2["evaluation_batch_size"],
        shuffle=False,
        drop_last=False,
        num_workers=m2["num_workers"],
        collate_fn=collator,
    )

    model = AutoModelForSequenceClassification.from_pretrained(
        model_path,
        local_files_only=True,
        num_labels=len(labels),
        id2label=id_to_label,
        label2id=label_to_id,
        ignore_mismatched_sizes=True,
    )
    device = torch.device("mps")
    model.to(device)
    optimizer = torch.optim.AdamW(
        optimizer_groups(model, m2["weight_decay"], m2["weight_decay_exclusions"]),
        lr=m2["learning_rate"],
        betas=(m2["adam_beta1"], m2["adam_beta2"]),
        eps=m2["adam_epsilon"],
    )
    steps_per_epoch = len(train_loader)
    total_steps = steps_per_epoch * m2["epochs"]
    warmup_steps = math.ceil(total_steps * m2["warmup_ratio"])
    scheduler = LambdaLR(
        optimizer,
        lambda step: linear_schedule(step, warmup_steps, total_steps),
    )

    history = []
    final_gold: list[int] = []
    final_predicted: list[int] = []
    final_probabilities: list[list[float]] = []
    for epoch in range(1, m2["epochs"] + 1):
        model.train()
        losses = []
        epoch_started = time.perf_counter()
        for step, batch in enumerate(train_loader, start=1):
            batch = {key: value.to(device) for key, value in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            result = model(**batch)
            if not torch.isfinite(result.loss):
                raise ValueError(f"M2 non-finite train loss at epoch={epoch} step={step}")
            result.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), m2["max_grad_norm"])
            optimizer.step()
            scheduler.step()
            losses.append(float(result.loss.detach().cpu()))
            if step % 100 == 0 or step == steps_per_epoch:
                logger.info(
                    "M2 view=%s seed=%d epoch=%d step=%d/%d loss=%.6f lr=%.8g",
                    view,
                    seed,
                    epoch,
                    step,
                    steps_per_epoch,
                    losses[-1],
                    scheduler.get_last_lr()[0],
                )
        dev_loss, gold_ids, predicted_ids, probabilities = evaluate_encoder(
            model, validation_loader, device
        )
        gold_labels = [id_to_label[value] for value in gold_ids]
        predicted_labels = [id_to_label[value] for value in predicted_ids]
        epoch_metrics = classification_metrics(gold_labels, predicted_labels, labels)
        history.append(
            {
                "dev_accuracy": epoch_metrics["accuracy"],
                "dev_loss": dev_loss,
                "dev_macro_f1": epoch_metrics["macro_f1"],
                "epoch": epoch,
                "epoch_seconds": time.perf_counter() - epoch_started,
                "learning_rate_end": scheduler.get_last_lr()[0],
                "train_loss": statistics.fmean(losses),
            }
        )
        logger.info(
            "M2 view=%s seed=%d epoch=%d train_loss=%.6f dev_loss=%.6f macro_f1=%.6f",
            view,
            seed,
            epoch,
            history[-1]["train_loss"],
            dev_loss,
            epoch_metrics["macro_f1"],
        )
        if epoch == m2["epochs"]:
            final_gold = gold_ids
            final_predicted = predicted_ids
            final_probabilities = probabilities

    if final_gold != [label_to_id[row["label"]] for row in validation]:
        raise ValueError("M2 validation order drift")
    probability_array = np.asarray(final_probabilities, dtype=np.float64)
    if probability_array.shape != (len(validation), len(labels)):
        raise ValueError("M2 probability tensor shape drift")
    if not np.isfinite(probability_array).all() or not np.allclose(
        probability_array.sum(axis=1), 1.0, atol=1e-5
    ):
        raise ValueError("M2 probabilities are invalid")
    predicted_labels = [id_to_label[value] for value in final_predicted]
    metrics = {
        "checkpoint_rule": f"final epoch {m2['epochs']}; no dev early stopping",
        "history": history,
        "model_id": "M2",
        "seed": seed,
        "slices": metrics_by_slice(validation, predicted_labels, labels),
        "train_input_lengths": train_lengths,
        "training": m2,
        "validation_input_lengths": validation_lengths,
        "view": view,
    }

    condition_public = public / "m2" / view / f"seed-{seed}"
    public_artifacts = write_metric_tables(condition_public, metrics, labels)
    history_path = condition_public / "history.csv"
    with history_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=tuple(history[0]))
        writer.writeheader()
        writer.writerows(history)
    public_artifacts["history"] = artifact(history_path)

    condition_private = private_root(config) / "m2" / view / f"seed-{seed}"
    predictions_path = condition_private / "predictions.csv"
    prediction_artifact = write_predictions(
        predictions_path,
        validation,
        predicted_labels,
        labels,
        final_probabilities,
        "probability",
    )
    checkpoint_dir = condition_private / "final-model"
    if checkpoint_dir.exists():
        raise FileExistsError(f"Private checkpoint already exists: {checkpoint_dir}")
    checkpoint_dir.mkdir(parents=True, mode=0o700)
    model.save_pretrained(checkpoint_dir, safe_serialization=True)
    tokenizer.save_pretrained(checkpoint_dir)
    for path in checkpoint_dir.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o600)
    checkpoint_artifact = tree_artifact(checkpoint_dir)
    if checkpoint_artifact["total_bytes"] > config["resource_budget"]["storage_bytes_max"]:
        raise RuntimeError("A single M2 checkpoint exceeds the total frozen storage budget")

    duration = time.perf_counter() - started
    report = {
        "accessed_splits": ["train", "validation"],
        "artifacts": public_artifacts,
        "checkpoint": checkpoint_artifact,
        "completed_at_utc": utc_now(),
        "duration_seconds": duration,
        "experiment_id": EXPERIMENT_ID,
        "model_parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "private_predictions": prediction_artifact,
        "seed": seed,
        "status": "Completed",
        "test_split_accessed": False,
        "trainable_parameter_count": sum(
            parameter.numel() for parameter in model.parameters() if parameter.requires_grad
        ),
        "validation_split_accessed": True,
        "view": view,
    }
    report_path = condition_public / "run.json"
    atomic_json(report_path, report)
    append_command(
        run,
        f"{sys.executable} {project_path(Path(__file__))} m2 --view {view} --seed {seed}",
    )
    run["stages"][stage_key] = {
        "artifact": artifact(report_path),
        "completed_at_utc": utc_now(),
        "duration_seconds": duration,
        "started_at_utc": started_at,
        "status": "Completed",
    }
    run["resource_usage"]["elapsed_seconds"] += duration
    save_run(config, run)
    logger.info(
        "M2 completed view=%s seed=%d macro_f1=%.6f accuracy=%.6f duration=%.1fs",
        view,
        seed,
        metrics["slices"]["all"]["macro_f1"],
        metrics["slices"]["all"]["accuracy"],
        duration,
    )
    del model, optimizer, scheduler, train_loader, validation_loader
    gc.collect()
    torch.mps.empty_cache()


def mean_std(values: Sequence[float]) -> dict[str, float]:
    return {
        "mean": statistics.fmean(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def run_aggregate(config: dict[str, Any]) -> None:
    public = run_dir(config)
    logger = setup_logger(public)
    run = read_run(config)
    expected = [f"m2__{view}__seed_{seed}" for view in VIEWS for seed in config["m2"]["seeds"]]
    missing = [key for key in expected if run["stages"].get(key, {}).get("status") != "Completed"]
    if missing:
        raise RuntimeError(f"Cannot aggregate before all M2 runs complete: {missing}")
    if "aggregate" in run["stages"]:
        raise FileExistsError("EXP-042 aggregate is append-only")

    started_at = utc_now()
    started = time.perf_counter()
    m0_m1 = json.loads((public / "m0-m1.json").read_text(encoding="utf-8"))
    metrics_names = ("macro_f1", "accuracy", "macro_precision", "macro_recall", "weighted_f1")
    m2_metrics: dict[str, dict[int, dict[str, Any]]] = {view: {} for view in VIEWS}
    for view in VIEWS:
        for seed in config["m2"]["seeds"]:
            path = public / "m2" / view / f"seed-{seed}" / "metrics.json"
            m2_metrics[view][seed] = json.loads(path.read_text(encoding="utf-8"))

    m2_aggregate = {}
    for view in VIEWS:
        slices = {}
        for slice_name in config["evaluation"]["slices"]:
            slices[slice_name] = {
                metric: mean_std(
                    [m2_metrics[view][seed]["slices"][slice_name][metric] for seed in config["m2"]["seeds"]]
                )
                for metric in metrics_names
            }
        m2_aggregate[view] = {"seeds": config["m2"]["seeds"], "slices": slices}

    paired_deltas = {}
    for slice_name in config["evaluation"]["slices"]:
        per_seed = {
            str(seed): {
                metric: (
                    m2_metrics["previous_context"][seed]["slices"][slice_name][metric]
                    - m2_metrics["target_only"][seed]["slices"][slice_name][metric]
                )
                for metric in metrics_names
            }
            for seed in config["m2"]["seeds"]
        }
        paired_deltas[slice_name] = {
            "per_seed": per_seed,
            "summary": {
                metric: mean_std([per_seed[str(seed)][metric] for seed in config["m2"]["seeds"]])
                for metric in metrics_names
            },
        }

    target_mean = m2_aggregate["target_only"]["slices"]["all"]["macro_f1"]["mean"]
    context_mean = m2_aggregate["previous_context"]["slices"]["all"]["macro_f1"]["mean"]
    delta = context_mean - target_mean
    if abs(delta) < config["evaluation"]["practical_tie_absolute"]:
        selected_view = "target_only"
        selection_reason = "practical tie; prefer lower-complexity target-only input"
    elif delta > 0:
        selected_view = "previous_context"
        selection_reason = "higher three-seed mean validation Macro-F1"
    else:
        selected_view = "target_only"
        selection_reason = "higher three-seed mean validation Macro-F1"

    aggregate = {
        "completed_at_utc": utc_now(),
        "experiment_id": EXPERIMENT_ID,
        "m0": m0_m1["m0"]["metrics"]["slices"],
        "m1": {
            view: m0_m1["m1"][view]["metrics"]["slices"] for view in VIEWS
        },
        "m2": m2_aggregate,
        "m2_paired_context_minus_target": paired_deltas,
        "m2_primary_view_selection": {
            "context_mean_macro_f1": context_mean,
            "delta": delta,
            "practical_tie_threshold": config["evaluation"]["practical_tie_absolute"],
            "reason": selection_reason,
            "selected_view": selected_view,
            "target_mean_macro_f1": target_mean,
        },
        "primary_metric": config["evaluation"]["primary_metric"],
        "status": "Completed",
        "test_split_accessed": False,
        "validation_split_accessed": True,
    }
    aggregate_path = public / "aggregate_metrics.json"
    atomic_json(aggregate_path, aggregate)

    seed_summary_path = public / "seed_summary.csv"
    with seed_summary_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(
            target,
            fieldnames=("model", "view", "seed", *metrics_names),
        )
        writer.writeheader()
        writer.writerow(
            {
                "model": "M0",
                "view": "target_only",
                "seed": "deterministic",
                **{metric: m0_m1["m0"]["metrics"]["slices"]["all"][metric] for metric in metrics_names},
            }
        )
        for view in VIEWS:
            writer.writerow(
                {
                    "model": "M1",
                    "view": view,
                    "seed": "deterministic",
                    **{
                        metric: m0_m1["m1"][view]["metrics"]["slices"]["all"][metric]
                        for metric in metrics_names
                    },
                }
            )
            for seed in config["m2"]["seeds"]:
                writer.writerow(
                    {
                        "model": "M2",
                        "view": view,
                        "seed": seed,
                        **{
                            metric: m2_metrics[view][seed]["slices"]["all"][metric]
                            for metric in metrics_names
                        },
                    }
                )

    report_path = public / "REPORT.md"
    report_path.write_text(
        "\n".join(
            [
                "# EXP-042 Stage 3 Results",
                "",
                "Status: Awaiting independent verification.",
                "",
                "| Model | View | Validation Macro-F1 | Accuracy |",
                "| --- | --- | ---: | ---: |",
                f"| M0 | target_only | {m0_m1['m0']['metrics']['slices']['all']['macro_f1']:.4f} | {m0_m1['m0']['metrics']['slices']['all']['accuracy']:.4f} |",
                f"| M1 | target_only | {m0_m1['m1']['target_only']['metrics']['slices']['all']['macro_f1']:.4f} | {m0_m1['m1']['target_only']['metrics']['slices']['all']['accuracy']:.4f} |",
                f"| M1 | previous_context | {m0_m1['m1']['previous_context']['metrics']['slices']['all']['macro_f1']:.4f} | {m0_m1['m1']['previous_context']['metrics']['slices']['all']['accuracy']:.4f} |",
                f"| M2 | target_only | {target_mean:.4f} +/- {m2_aggregate['target_only']['slices']['all']['macro_f1']['std']:.4f} | {m2_aggregate['target_only']['slices']['all']['accuracy']['mean']:.4f} +/- {m2_aggregate['target_only']['slices']['all']['accuracy']['std']:.4f} |",
                f"| M2 | previous_context | {context_mean:.4f} +/- {m2_aggregate['previous_context']['slices']['all']['macro_f1']['std']:.4f} | {m2_aggregate['previous_context']['slices']['all']['accuracy']['mean']:.4f} +/- {m2_aggregate['previous_context']['slices']['all']['accuracy']['std']:.4f} |",
                "",
                f"Frozen M2 primary view: `{selected_view}` ({selection_reason}).",
                "",
                "These are validation results. The sealed test split was not accessed.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    duration = time.perf_counter() - started
    append_command(run, f"{sys.executable} {project_path(Path(__file__))} aggregate")
    run["stages"]["aggregate"] = {
        "artifact": artifact(aggregate_path),
        "completed_at_utc": utc_now(),
        "duration_seconds": duration,
        "started_at_utc": started_at,
        "status": "Completed",
    }
    run["resource_usage"]["elapsed_seconds"] += duration
    run["execution_finished_at_utc"] = utc_now()
    run["status"] = "Awaiting Independent Verification"
    run["artifacts"] = {
        "aggregate_metrics": artifact(aggregate_path),
        "report": artifact(report_path),
        "seed_summary": artifact(seed_summary_path),
    }
    save_run(config, run)
    logger.info("EXP-042 aggregate completed; independent verification required")


def mark_failed(error: BaseException) -> None:
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        path = resolve_project_path(config["run_dir"]) / "run.json"
        if not path.is_file():
            return
        run = json.loads(path.read_text(encoding="utf-8"))
        run["status"] = "Failed"
        run.setdefault("failures", []).append(
            {
                "at_utc": utc_now(),
                "error": type(error).__name__,
                "message": str(error),
            }
        )
        atomic_json(path, run)
    except Exception:
        pass


def main() -> None:
    args = parse_args()
    try:
        config = load_config()
        if args.command == "initialize":
            run_initialize(config)
        elif args.command == "m0-m1":
            run_m0_m1(config)
        elif args.command == "m2":
            run_m2(config, args.view, args.seed)
        elif args.command == "aggregate":
            run_aggregate(config)
        else:
            raise ValueError(args.command)
    except BaseException as error:
        mark_failed(error)
        raise


if __name__ == "__main__":
    main()
