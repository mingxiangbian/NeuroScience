#!/usr/bin/env python3
"""Model-free independent verification of sealed EXP-072 ablation scores."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import shutil
import stat
import sys
import time
import traceback
from typing import Any, Mapping, Sequence
import zipfile

import numpy as np


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
EXPERIMENT_ID = "EXP-072"
ROWS = 3360
FOLDS = (0, 1, 2, 3, 4)
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
PRIMARY_COLUMNS = (0, 1, 3, 4, 5)
CONDITIONS = tuple((seed, condition) for seed in (42, 43, 44)
                   for condition in (("A0", "A1", "A2", "A3", "A4", "A5") if seed == 42
                                     else ("A0", "A1", "A2", "A3")))
CONDITION_KEYS = tuple(f"s{seed}:{condition}" for seed, condition in CONDITIONS)
METRIC_KEYS = ("six_label_macro_f1", "five_label_macro_f1", "micro_f1", "weighted_f1", "hamming_loss", "subset_accuracy")
RUNNER_PATH = "experiments/stack-overflow-emotion-gold/phase-b-representation/run_exp072_ablation.py"
VERIFIER_PATH = "experiments/stack-overflow-emotion-gold/phase-b-representation/verify_exp072_ablation.py"
RUN_ID = "exp-072-lora-functional-ablation"
ATTEMPT_ID = "formal-attempt-1"
LORA_MODULES = ("self_attn.q_proj", "self_attn.k_proj", "self_attn.v_proj", "self_attn.o_proj",
                "mlp.gate_proj", "mlp.up_proj", "mlp.down_proj")
INFERENCE_ACCESS = {
    "train_heldout_text_accessed": True, "sample_identity_accessed": True,
    "row_ordinal_fold_id_accessed": True, "model_forward_executed": True,
    "heldout_reference_logits_accessed": True, "labels_accessed": False,
    "component_ids_accessed": False, "threshold_values_accessed": False,
    "metrics_computed": False, "validation_accessed": False, "test_accessed": False,
    "training_executed": False, "calibration_executed": False,
    "token_cache_written": False, "external_api_accessed": False,
}
SCORE_ACCESS = {
    "labels_after_prediction_seal": True, "train_labels_read": True,
    "threshold_members_read": ["fold_ids", "m3_raw_thresholds"], "model_loaded": False,
    "forward_executed": False, "text_read": False, "validation_accessed": False, "test_accessed": False,
}


def expected_workers() -> list[dict[str, Any]]:
    def item(seed: int, fold: int, condition: str) -> dict[str, Any]:
        return {"worker_id": f"s{seed}-f{fold}-{condition}", "seed": seed, "fold": fold, "condition": condition}
    result = [item(seed, fold, "A0") for seed in (42, 43, 44) for fold in FOLDS]
    for seed in (42, 43, 44):
        for condition in (("A1", "A2", "A3", "A4", "A5") if seed == 42 else ("A1", "A2", "A3")):
            result.extend(item(seed, fold, condition) for fold in FOLDS)
    return result


def scale_map(condition: str) -> list[dict[str, Any]]:
    if condition not in {"A0", "A1", "A2", "A3", "A4", "A5"}:
        raise ValueError("Unknown independent ablation condition")
    result = []
    for block in range(20, 36):
        for module in LORA_MODULES:
            off = condition == "A1" or condition == "A2" and module.startswith("self_attn.") or condition == "A3" and module.startswith("mlp.") or condition == "A4" and block < 28 or condition == "A5" and block >= 28
            result.append({"block": block, "module": module, "scale": 0.0 if off else 20.0})
    return result


def string_digest(values: Sequence[str]) -> str:
    checksum = hashlib.sha256()
    for value in values:
        encoded = value.encode("utf-8")
        checksum.update(len(encoded).to_bytes(4, "little"))
        checksum.update(encoded)
    return checksum.hexdigest()


def array_digest(value: Any) -> str:
    return hashlib.sha256(np.ascontiguousarray(value).tobytes(order="C")).hexdigest()


def _canonical(runner: Any, path: Path) -> dict[str, Any]:
    value = runner.strict_json(path)
    if not isinstance(value, dict) or path.read_bytes() != runner.canonical_json_bytes(value):
        raise ValueError("Non-canonical EXP-072 result artifact")
    return value


def require_tree(root: Path, files: set[str], directories: set[str], *, private: bool) -> None:
    if root.is_symlink() or not root.is_dir() or stat.S_IMODE(root.stat().st_mode) != (0o700 if private else 0o755):
        raise ValueError("EXP-072 output root mode drift")
    observed_files, observed_dirs = set(), set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("EXP-072 output symlink")
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            observed_dirs.add(relative)
            expected_mode = 0o700 if private else 0o755
        elif path.is_file():
            observed_files.add(relative)
            expected_mode = 0o600 if private else 0o644
            if path.stat().st_nlink != 1:
                raise ValueError("EXP-072 extra output hard link")
        else:
            raise ValueError("EXP-072 special output entry")
        if stat.S_IMODE(path.stat().st_mode) != expected_mode:
            raise ValueError("EXP-072 output entry mode drift")
    if observed_files != files or observed_dirs != directories:
        raise ValueError("EXP-072 failed or unexpected output prefix")


def require_scored_prefix(runner: Any, config: Mapping[str, Any]) -> tuple[Path, Path]:
    public, private = runner.roots(config)
    order = [value["worker_id"] for value in expected_workers()]
    public_files = {"run-claim.json", "stdout.log", "run.json", "prediction-seal.json", "score.json"} | {f"workers/{worker}.json" for worker in order}
    private_files = {"input-manifest.json", "prediction-manifest.json", "scored-predictions.npz"} | {f"workers/{worker}{suffix}" for worker in order for suffix in (".json", ".npz")}
    require_tree(public, public_files, {"workers"}, private=False)
    require_tree(private, private_files, {"workers"}, private=True)
    if sum(path.stat().st_size for path in private.rglob("*") if path.is_file()) > 1024**3:
        raise ValueError("EXP-072 private output budget exceeded")
    return public, private


def _common() -> dict[str, Any]:
    return {"experiment_id": EXPERIMENT_ID, "run_id": RUN_ID, "attempt_id": ATTEMPT_ID}


def _exact(value: Mapping[str, Any], expected: Mapping[str, Any], extras: set[str] = frozenset()) -> None:
    if set(value) != set(expected) | extras or any(not recursive_close(value.get(key), item) for key, item in expected.items()):
        raise ValueError("EXP-072 exact metadata binding drift")


def _worker_source(metadata: Mapping[str, Any], spec: Mapping[str, Any]) -> Mapping[str, Any]:
    matches = [source for source in metadata["exp069_manifest"]["m3_sources"] if source["seed"] == spec["seed"] and source["fold"] == spec["fold"]]
    if len(matches) != 1:
        raise ValueError("EXP-072 source checkpoint is ambiguous")
    return matches[0]


def validate_worker_metadata(runner: Any, config_path: Path, config: Mapping[str, Any], metadata: Mapping[str, Any], spec: Mapping[str, Any], records: Mapping[str, Any], prior: Mapping[str, Any]) -> dict[str, Any]:
    public, private = runner.roots(config)
    worker_id = spec["worker_id"]
    paths = {"public": public / "workers" / f"{worker_id}.json", "manifest": private / "workers" / f"{worker_id}.json", "logits": private / "workers" / f"{worker_id}.npz"}
    if set(records) != set(paths):
        raise ValueError("EXP-072 worker artifact inventory drift")
    for name, path in paths.items():
        if runner.require_record(records[name]) != path:
            raise ValueError("EXP-072 worker artifact path drift")
    value = _canonical(runner, paths["manifest"])
    source = _worker_source(metadata, spec)
    expected_source = {name: source[key] for name, key in (("adapter", "adapter"), ("head", "head"), ("heldout", "heldout_logits"))}
    mask = scale_map(spec["condition"])
    expected = {
        "schema_version": "exp-072-worker-private-v1", **_common(), **spec, "status": "Completed",
        "config": runner.artifact(config_path), "input_manifest": runner.artifact(private / "input-manifest.json"),
        "output": records["logits"], "source_before": expected_source, "source_after": expected_source,
        "scale_map_sha256": runner.digest(mask), "disabled_modules": sum(item["scale"] == 0.0 for item in mask),
        "rows": 672, "access": INFERENCE_ACCESS,
    }
    extras = {"row_order_sha256", "fold_id_sha256", "sample_id_order_sha256", "token_stream_sha256", "tensor_before", "tensor_after", "replay", "resources"}
    _exact(value, expected, extras)
    if set(value["tensor_before"]) != {"adapter", "head", "base_sentinel"} or value["tensor_after"] != value["tensor_before"]:
        raise ValueError("EXP-072 runtime tensor preservation drift")
    checksums = [value[key] for key in ("row_order_sha256", "fold_id_sha256", "sample_id_order_sha256", "token_stream_sha256")] + list(value["tensor_before"].values())
    if any(type(item) is not str or len(item) != 64 or any(char not in "0123456789abcdef" for char in item) for item in checksums):
        raise ValueError("EXP-072 worker digest format drift")
    replay = value["replay"]
    if spec["condition"] == "A0":
        if set(replay) != {"required", "checked_rows", "max_abs_error", "atol", "rtol"} or replay["required"] is not True or replay["checked_rows"] != 672 or replay["atol"] != 1e-5 or replay["rtol"] != 0.0 or type(replay["max_abs_error"]) not in (int, float) or not math.isfinite(replay["max_abs_error"]) or not 0 <= replay["max_abs_error"] <= 1e-5:
            raise ValueError("EXP-072 A0 replay seal failed")
    else:
        if replay != {"required": False, "checked_rows": 0, "max_abs_error": None, "atol": 1e-5, "rtol": 0.0}:
            raise ValueError("EXP-072 ablation replay metadata drift")
        full = prior[f"s{spec['seed']}-f{spec['fold']}-A0"]
        if any(value[key] != full[key] for key in ("row_order_sha256", "fold_id_sha256", "sample_id_order_sha256", "token_stream_sha256", "tensor_before", "source_before")):
            raise ValueError("EXP-072 full/ablation matching drift")
    resources = value["resources"]
    maxima = {"wall_seconds": 3600, "peak_mlx_bytes": 10_000_000_000, "peak_rss_bytes": 16 * 1024**3}
    if set(resources) != set(maxima) or any(type(resources[key]) not in (int, float) or not math.isfinite(resources[key]) or not 0 <= resources[key] <= maximum for key, maximum in maxima.items()):
        raise ValueError("EXP-072 worker resource ceiling failed")
    public_value = _canonical(runner, paths["public"])
    _exact(public_value, {"schema_version": "exp-072-worker-public-v1", **_common(), **spec, "status": "Completed", "rows": 672,
                          "output_sha256": records["logits"]["sha256"], "manifest_sha256": records["manifest"]["sha256"],
                          "replay": replay, "disabled_modules": expected["disabled_modules"], "scale_map_sha256": expected["scale_map_sha256"],
                          "resources": resources, "access": INFERENCE_ACCESS})
    return value


def sigmoid(logits: Any) -> np.ndarray:
    values = np.asarray(logits, dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise ValueError("Non-finite independent scoring logits")
    result = np.empty(values.shape, dtype=np.float64)
    nonnegative = values >= 0.0
    result[nonnegative] = 1.0 / (1.0 + np.exp(-values[nonnegative]))
    negative_exp = np.exp(values[~nonnegative])
    result[~nonnegative] = negative_exp / (1.0 + negative_exp)
    return result


def classification(gold: Any, predictions: Any) -> dict[str, Any]:
    truth, guess = np.asarray(gold), np.asarray(predictions)
    if truth.shape != guess.shape or truth.ndim != 2 or truth.shape[1] != 6 or truth.shape[0] == 0 or not np.all((truth == 0) | (truth == 1)) or not np.all((guess == 0) | (guess == 1)):
        raise ValueError("Invalid independent binary score arrays")
    rows = truth.shape[0]
    tp = np.count_nonzero((truth == 1) & (guess == 1), axis=0)
    fp = np.count_nonzero((truth == 0) & (guess == 1), axis=0)
    fn = np.count_nonzero((truth == 1) & (guess == 0), axis=0)
    support = np.count_nonzero(truth == 1, axis=0)
    per_label, f1_values = {}, []
    for index, label in enumerate(LABELS):
        true_positive, false_positive, false_negative = int(tp[index]), int(fp[index]), int(fn[index])
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        denominator = 2 * true_positive + false_positive + false_negative
        f1 = 2 * true_positive / denominator if denominator else 0.0
        f1_values.append(float(f1))
        per_label[label] = {"precision": float(precision), "recall": float(recall), "f1": float(f1), "support": int(support[index])}
    total_tp, total_fp, total_fn = int(tp.sum()), int(fp.sum()), int(fn.sum())
    micro_denominator = 2 * total_tp + total_fp + total_fn
    support_total = int(support.sum())
    return {
        "rows": int(rows), "six_label_macro_f1": float(sum(f1_values) / 6),
        "five_label_macro_f1": float(sum(f1_values[index] for index in PRIMARY_COLUMNS) / 5),
        "micro_f1": float(2 * total_tp / micro_denominator) if micro_denominator else 0.0,
        "weighted_f1": float(sum(f1_values[index] * int(support[index]) for index in range(6)) / support_total) if support_total else 0.0,
        "hamming_loss": float(np.count_nonzero(truth != guess) / truth.size),
        "subset_accuracy": float(np.count_nonzero(np.all(truth == guess, axis=1)) / rows),
        "per_label": per_label,
    }


def score_arrays(gold: Any, logits: Mapping[str, Any], thresholds: Mapping[int, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    truth = np.asarray(gold)
    if truth.shape != (ROWS, 6) or set(logits) != set(CONDITION_KEYS) or set(thresholds) != {42, 43, 44}:
        raise ValueError("Independent scoring family inventory drift")
    for seed in (42, 43, 44):
        threshold = np.asarray(thresholds[seed])
        if threshold.shape != (ROWS,) or not np.all(np.isfinite(threshold)) or np.any(threshold < 0) or np.any(threshold > 1):
            raise ValueError("Frozen independent threshold drift")
    results, predictions = {}, {}
    for seed, condition in CONDITIONS:
        key, baseline = f"s{seed}:{condition}", f"s{seed}:A0"
        values = np.asarray(logits[key])
        if values.shape != (ROWS, 6) or not np.all(np.isfinite(values)):
            raise ValueError("Independent OOF logit shape or finite gate failed")
        prediction = np.asarray(sigmoid(values) >= np.asarray(thresholds[seed])[:, None], dtype=np.uint8)
        predictions[key] = prediction
        metrics = classification(truth, prediction)
        full_metrics = metrics if condition == "A0" else results[baseline]["metrics"]
        delta = {name: float(metrics[name] - full_metrics[name]) for name in METRIC_KEYS}
        delta["per_label_f1"] = {label: float(metrics["per_label"][label]["f1"] - full_metrics["per_label"][label]["f1"]) for label in LABELS}
        changed = np.any(prediction != predictions[baseline], axis=1)
        logit_difference = values.astype(np.float64) - np.asarray(logits[baseline], dtype=np.float64)
        results[key] = {"seed": seed, "condition": condition, "metrics": metrics, "delta_from_full": delta,
                        "prediction_vector_flip_rate": float(np.count_nonzero(changed) / ROWS),
                        "mean_absolute_logit_change": float(np.sum(np.abs(logit_difference), dtype=np.float64) / (ROWS * 6))}
    return {"condition_order": list(CONDITION_KEYS), "conditions": results}, predictions


def recursive_close(actual: Any, expected: Any) -> bool:
    if isinstance(expected, Mapping):
        return isinstance(actual, Mapping) and set(actual) == set(expected) and all(recursive_close(actual[key], expected[key]) for key in expected)
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(recursive_close(a, b) for a, b in zip(actual, expected, strict=True))
    if type(expected) is float:
        return type(actual) is float and math.isfinite(actual) and math.isfinite(expected) and math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12)
    return type(actual) is type(expected) and actual == expected


def load_runner(config_path: Path) -> Any:
    config = json.loads(config_path.resolve().read_bytes())
    record = config["implementation"]["runner"]
    if record["path"] != RUNNER_PATH:
        raise ValueError("EXP-072 runner helper path drift")
    path = PROJECT_ROOT / record["path"]
    cursor = path
    while cursor != PROJECT_ROOT:
        if cursor.is_symlink():
            raise ValueError("Symlink in EXP-072 runner helper path")
        cursor = cursor.parent
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != record["bytes"] or f"{stat.S_IMODE(info.st_mode):04o}" != record["mode"] or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError("EXP-072 runner helper identity drift")
    specification = importlib.util.spec_from_file_location("exp072_verifier_io_only", path)
    if specification is None or specification.loader is None:
        raise RuntimeError("Cannot import EXP-072 metadata helpers")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def validate_run_metadata(runner: Any, config_path: Path, config: Mapping[str, Any], metadata: Mapping[str, Any]) -> None:
    public, private = runner.roots(config)
    config_record = runner.artifact(config_path)
    input_path = private / "input-manifest.json"
    input_manifest = _canonical(runner, input_path)
    _exact(input_manifest, {"schema_version": "exp-072-input-manifest-v1", **_common(), "status": "Frozen",
                            "config": config_record, "source_snapshot": metadata["source_snapshot"],
                            "source_snapshot_sha256": metadata["source_snapshot_sha256"],
                            "method_sha256": runner.digest(config["method"]), "worker_plan": expected_workers(),
                            "fold_sources": [{key: item[key] for key in ("seed", "fold", "adapter", "head", "heldout_logits")}
                                             for item in metadata["exp069_manifest"]["m3_sources"]],
                            "access": {key: False for key in INFERENCE_ACCESS}})
    if runner.digest(input_manifest["source_snapshot"]) != input_manifest["source_snapshot_sha256"]:
        raise ValueError("EXP-072 input source snapshot digest drift")
    claim_path = public / "run-claim.json"
    claim = _canonical(runner, claim_path)
    expected_claim = {"schema_version": "exp-072-run-claim-v1", **_common(), "status": "Running", "tier": "Major",
                      "rq_id": "RQ-S4.3", "stage": "run", "config": config_record,
                      "input_manifest": runner.artifact(input_path), "environment": config["environment"],
                      "resources": config["resources"], "access": {key: False for key in INFERENCE_ACCESS}}
    _exact(claim, expected_claim, {"started_at", "command", "cwd", "git", "scheduler_pid"})
    command = claim["command"]
    if not isinstance(command, list) or len(command) != 6 or os.path.realpath(command[0]) != os.path.realpath(config["environment"]["python_executable"]) or command[1:] != [str(PROJECT_ROOT / RUNNER_PATH), "--stage", "run", "--config", str(config_path)] or claim["cwd"] != str(PROJECT_ROOT) or type(claim["scheduler_pid"]) is not int or claim["scheduler_pid"] <= 0:
        raise ValueError("EXP-072 inference execution identity drift")
    git = claim["git"]
    if set(git) != {"commit", "dirty"} or type(git["dirty"]) is not bool or type(git["commit"]) is not str or len(git["commit"]) != 40 or any(char not in "0123456789abcdef" for char in git["commit"]):
        raise ValueError("EXP-072 git identity schema drift")
    run = _canonical(runner, public / "run.json")
    expected_run = {"schema_version": "exp-072-inference-run-v1", **_common(), "tier": "Major", "rq_id": "RQ-S4.3",
                    "stage": "run", "status": "CompletedAwaitingScore", "started_at": claim["started_at"],
                    "command": command, "cwd": claim["cwd"], "git": git, "config": config_record,
                    "run_claim": runner.artifact(claim_path), "prediction_seal": runner.artifact(public / "prediction-seal.json"),
                    "worker_count": 70, "a0_worker_count": 15, "total_forward_rows": 47040,
                    "dataset": "DATA-SO-TASK-V1", "split": "train_oof", "rows": ROWS, "labels": list(LABELS),
                    "method": config["method"], "source_snapshot_sha256": metadata["source_snapshot_sha256"],
                    "environment": config["environment"], "access": INFERENCE_ACCESS,
                    "metrics": None, "warnings": [], "exception": None, "exp072_complete": False}
    _exact(run, expected_run, {"finished_at", "resources"})
    began, ended = datetime.fromisoformat(run["started_at"].replace("Z", "+00:00")), datetime.fromisoformat(run["finished_at"].replace("Z", "+00:00"))
    if began.utcoffset() is None or ended.utcoffset() is None or began.utcoffset().total_seconds() != 0 or ended.utcoffset().total_seconds() != 0 or not 0 <= (ended - began).total_seconds() <= 57600:
        raise ValueError("EXP-072 inference timestamps drift")
    limits = {"wall_seconds": 57600, "peak_mlx_bytes": 10_000_000_000, "peak_rss_bytes": 16 * 1024**3}
    if set(run["resources"]) != set(limits) or any(type(run["resources"][key]) not in (int, float) or not math.isfinite(run["resources"][key]) or not 0 <= run["resources"][key] <= maximum for key, maximum in limits.items()):
        raise ValueError("EXP-072 inference resource ceiling failed")
    events = []
    for index, spec in enumerate(expected_workers(), 1):
        events.extend([{"event": "worker_started", "worker_id": spec["worker_id"]},
                       {"event": "worker_completed", "worker_id": spec["worker_id"], "completed_workers": index}])
    events.append({"event": "predictions_sealed", "worker_count": 70})
    if (public / "stdout.log").read_bytes() != b"".join(runner.canonical_json_bytes(event) for event in events):
        raise ValueError("EXP-072 frozen worker execution order drift")


def validate_prediction_seal(runner: Any, config_path: Path, config: Mapping[str, Any], metadata: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Finish the entire metadata gate before any label-bearing member is decoded."""
    public, private = require_scored_prefix(runner, config)
    validate_run_metadata(runner, config_path, config, metadata)
    seal_path, manifest_path = public / "prediction-seal.json", private / "prediction-manifest.json"
    seal, manifest = _canonical(runner, seal_path), _canonical(runner, manifest_path)
    order = [value["worker_id"] for value in expected_workers()]
    expected_manifest = {"schema_version": "exp-072-prediction-manifest-v1", **_common(), "status": "Sealed",
                         "config": runner.artifact(config_path), "input_manifest": runner.artifact(private / "input-manifest.json"),
                         "worker_order": order, "worker_count": 70, "a0_worker_count": 15, "total_forward_rows": 47040,
                         "source_snapshot_sha256": metadata["source_snapshot_sha256"], "access": INFERENCE_ACCESS}
    _exact(manifest, expected_manifest, {"workers"})
    if set(manifest["workers"]) != set(order):
        raise ValueError("EXP-072 prediction family is incomplete")
    expected_seal = {"schema_version": "exp-072-prediction-seal-v1", **_common(), "status": "Sealed",
                     "config": runner.artifact(config_path), "prediction_manifest": runner.artifact(manifest_path),
                     "worker_count": 70, "a0_worker_count": 15, "total_forward_rows": 47040,
                     "worker_inventory_sha256": runner.digest(manifest["workers"]), "all_a0_passed": True,
                     "all_predictions_sealed": True, "labels_accessed": False, "metrics_computed": False}
    _exact(seal, expected_seal)
    workers = {}
    for spec in expected_workers():
        worker = validate_worker_metadata(runner, config_path, config, metadata, spec, manifest["workers"][spec["worker_id"]], workers)
        workers[spec["worker_id"]] = worker
        path = runner.require_record(manifest["workers"][spec["worker_id"]]["logits"])
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if [info.filename for info in infos] != ["ordinal.npy", "fold_id.npy", "logits.npy"] or any(info.compress_type != zipfile.ZIP_STORED for info in infos):
                raise ValueError("EXP-072 worker prediction member inventory drift")
    return manifest, workers, runner.artifact(seal_path)


def _selector(runner: Any, config: Mapping[str, Any]) -> Any:
    return runner._import_record(config["source"]["helpers"]["selective_json"], "exp072_independent_selective_json")


def load_prediction_sources(runner: Any, metadata: Mapping[str, Any], config: Mapping[str, Any], manifest: Mapping[str, Any], workers: Mapping[str, Any], *, started: float | None = None) -> tuple[list[str], np.ndarray, dict[str, np.ndarray], dict[int, np.ndarray], dict[str, float]]:
    """Read identities/logits and replay every A0; never read labels or text."""
    selector = _selector(runner, config)
    original = metadata["original_config"]
    public_rows = []
    with runner.require_record(original["data"]["fold_manifest_public"]).open("rb") as handle:
        for line in handle:
            selected, _ = selector.select_json_scalars(line, [("sample_id",), ("fold_id",)])
            sample_id, fold_id = selected[("sample_id",)], selected[("fold_id",)]
            if type(sample_id) is not str or not sample_id or type(fold_id) is not int or fold_id not in FOLDS:
                raise ValueError("EXP-072 public row identity drift")
            public_rows.append((sample_id, fold_id))
    sample_ids = [row[0] for row in public_rows]
    if len(public_rows) != ROWS or len(set(sample_ids)) != ROWS:
        raise ValueError("EXP-072 public row coverage drift")
    folds = np.asarray([row[1] for row in public_rows], dtype=np.int8)
    row_contract = runner.read_npz_members(runner.require_record(config["source"]["exp070_row_contract"]), ["ordinal", "fold_id"])
    if row_contract["ordinal"].dtype != np.int32 or row_contract["fold_id"].dtype != np.int8 or not np.array_equal(row_contract["ordinal"], np.arange(ROWS, dtype=np.int32)) or not np.array_equal(row_contract["fold_id"], folds):
        raise ValueError("EXP-072 independent ordinal/fold source mismatch")
    logits = {key: np.empty((ROWS, 6), dtype=np.float32) for key in CONDITION_KEYS}
    replays = {}
    for spec in expected_workers():
        if started is not None:
            _budget(started)
        worker_id = spec["worker_id"]
        worker = workers[worker_id]
        values = runner.read_npz_members(runner.require_record(manifest["workers"][worker_id]["logits"]), ["ordinal", "fold_id", "logits"])
        ordinals = np.flatnonzero(folds == spec["fold"]).astype(np.int32)
        if ordinals.shape != (672,) or values["ordinal"].dtype != np.int32 or values["fold_id"].dtype != np.int8 or values["logits"].dtype != np.float32 or values["logits"].shape != (672, 6) or not np.array_equal(values["ordinal"], ordinals) or not np.array_equal(values["fold_id"], folds[ordinals]) or not np.all(np.isfinite(values["logits"])):
            raise ValueError("EXP-072 heldout prediction alignment drift")
        selected_ids = [sample_ids[index] for index in ordinals]
        if worker["row_order_sha256"] != array_digest(ordinals) or worker["fold_id_sha256"] != array_digest(folds[ordinals]) or worker["sample_id_order_sha256"] != string_digest(selected_ids):
            raise ValueError("EXP-072 worker ordinal/sample digest mismatch")
        if spec["condition"] == "A0":
            source = _worker_source(metadata, spec)
            reference = runner.read_npz_members(runner.require_record(source["heldout_logits"]), ["sample_ids", "fold_ids", "logits"])
            ids = [str(value) for value in reference["sample_ids"].tolist()]
            if reference["sample_ids"].shape != (672,) or reference["fold_ids"].shape != (672,) or reference["logits"].dtype != np.float32 or reference["logits"].shape != (672, 6) or len(set(ids)) != 672 or set(ids) != set(selected_ids) or not np.all(reference["fold_ids"] == spec["fold"]) or not np.all(np.isfinite(reference["logits"])):
                raise ValueError("EXP-072 saved A0 reference alignment drift")
            index = {sample_id: position for position, sample_id in enumerate(ids)}
            aligned = reference["logits"][[index[sample_id] for sample_id in selected_ids]]
            error = float(np.max(np.abs(values["logits"].astype(np.float64) - aligned.astype(np.float64))))
            if error > 1e-5 or not math.isclose(float(worker["replay"]["max_abs_error"]), error, rel_tol=0, abs_tol=1e-12):
                raise ValueError("EXP-072 independent full A0 replay failed")
            replays[worker_id] = error
        logits[f"s{spec['seed']}:{spec['condition']}"][ordinals] = values["logits"]
    if len(replays) != 15:
        raise ValueError("EXP-072 all A0 replays are required before label access")
    thresholds = {}
    if [item["seed"] for item in config["source"]["thresholds"]] != [42, 43, 44]:
        raise ValueError("EXP-072 threshold seed order drift")
    for item in config["source"]["thresholds"]:
        if item["allowed_members"] != ["fold_ids", "m3_raw_thresholds"]:
            raise ValueError("EXP-072 threshold value allowlist drift")
        values = runner.read_npz_members(runner.require_record(item["artifact"]), ["fold_ids", "m3_raw_thresholds"])
        if values["fold_ids"].dtype != np.int8 or values["m3_raw_thresholds"].dtype != np.float64 or not np.array_equal(values["fold_ids"], folds) or values["m3_raw_thresholds"].shape != (ROWS,) or not np.all(np.isfinite(values["m3_raw_thresholds"])) or np.any(values["m3_raw_thresholds"] < 0) or np.any(values["m3_raw_thresholds"] > 1):
            raise ValueError("EXP-072 threshold row contract drift")
        thresholds[item["seed"]] = values["m3_raw_thresholds"]
    return sample_ids, folds, logits, thresholds, replays


def load_gold_after_gate(runner: Any, metadata: Mapping[str, Any], config: Mapping[str, Any], sample_ids: Sequence[str], folds: np.ndarray, gate: Mapping[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    public, _private = runner.roots(config)
    if gate.get("workers_validated") != 70 or gate.get("a0_replays_validated") != 15 or runner.artifact(public / "prediction-seal.json") != gate.get("seal"):
        raise ValueError("EXP-072 labels require the complete immutable prediction gate")
    source_record = metadata["original_config"]["data"]["fold_manifest_private"]
    path = runner.require_record(source_record)
    selector = _selector(runner, config)
    rows = []
    with path.open("rb") as handle:
        for ordinal, line in enumerate(handle):
            if ordinal >= ROWS:
                raise ValueError("EXP-072 label source has extra rows")
            selected, spans = selector.select_json_scalars(line, [("sample_id",), ("fold_id",)], capture_paths=[("labels",)])
            labels = json.loads(spans[("labels",)])
            if selected[("sample_id",)] != sample_ids[ordinal] or selected[("fold_id",)] != int(folds[ordinal]) or not isinstance(labels, list) or len(labels) != 6 or any(type(value) not in (bool, int) or value not in (0, 1) for value in labels):
                raise ValueError("EXP-072 independent label alignment drift")
            rows.append(labels)
    if len(rows) != ROWS:
        raise ValueError("EXP-072 label source coverage drift")
    runner.require_record(source_record)
    return np.asarray(rows, dtype=np.uint8), dict(source_record)


def validate_scored_predictions(runner: Any, path: Path, gold: np.ndarray, folds: np.ndarray, predictions: Mapping[str, np.ndarray]) -> None:
    expected = {"ordinal": np.arange(ROWS, dtype=np.int32), "fold_id": folds, "gold": gold}
    expected.update({key.replace(":", "_") + "_prediction": predictions[key] for key in CONDITION_KEYS})
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if [info.filename for info in infos] != [name + ".npy" for name in expected] or any(info.compress_type != zipfile.ZIP_STORED for info in infos):
            raise ValueError("EXP-072 scored prediction bundle schema drift")
    values = runner.read_npz_members(path, list(expected))
    for name, reference in expected.items():
        if values[name].dtype != reference.dtype or values[name].shape != reference.shape or not np.array_equal(values[name], reference):
            raise ValueError("EXP-072 scored prediction value mismatch")


def validate_score_report(runner: Any, config_path: Path, config: Mapping[str, Any], metadata: Mapping[str, Any], seal_record: Mapping[str, Any], results: Mapping[str, Any], gold: np.ndarray, folds: np.ndarray, predictions: Mapping[str, np.ndarray]) -> dict[str, Any]:
    public, private = runner.roots(config)
    score = _canonical(runner, public / "score.json")
    expected = {"schema_version": "exp-072-score-v1", "experiment_id": EXPERIMENT_ID, "tier": "Major",
                "status": "ScoredAwaitingVerification", "config": runner.artifact(config_path),
                "prediction_seal": dict(seal_record), "source_snapshot_sha256": metadata["source_snapshot_sha256"],
                "scored_predictions": runner.artifact(private / "scored-predictions.npz"), "access": SCORE_ACCESS}
    _exact(score, expected, {"results", "results_sha256", "created_at_utc", "resources"})
    if score["results_sha256"] != runner.digest(score["results"]) or not recursive_close(score["results"], results):
        raise ValueError("EXP-072 independent metrics or delta mismatch")
    timestamp = datetime.fromisoformat(score["created_at_utc"].replace("Z", "+00:00"))
    if timestamp.utcoffset() is None or timestamp.utcoffset().total_seconds() != 0:
        raise ValueError("EXP-072 score timestamp timezone drift")
    resources = score["resources"]
    if set(resources) != {"wall_seconds", "peak_rss_bytes", "api_cost_usd"} or type(resources["wall_seconds"]) not in (int, float) or not math.isfinite(resources["wall_seconds"]) or not 0 <= resources["wall_seconds"] <= 3600 or type(resources["peak_rss_bytes"]) is not int or not 0 < resources["peak_rss_bytes"] <= 16 * 1024**3 or resources["api_cost_usd"] != 0:
        raise ValueError("EXP-072 scorer resource gate failed")
    validate_scored_predictions(runner, private / "scored-predictions.npz", gold, folds, predictions)
    return score


def _peak_rss_bytes() -> int:
    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return peak if sys.platform == "darwin" else peak * 1024


def _budget(started: float) -> None:
    if time.monotonic() - started > 3600 or _peak_rss_bytes() > 16 * 1024**3:
        raise RuntimeError("EXP-072 model-free verifier resource ceiling exceeded")


def _no_model_or_scorer_import() -> None:
    if {name.split(".", 1)[0] for name in sys.modules} & {"mlx", "mlx_lm", "torch", "transformers"}:
        raise RuntimeError("EXP-072 verifier imported a model library")
    forbidden = MODULE_DIR / "score_exp072_ablation.py"
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path and Path(path).resolve() == forbidden:
            raise RuntimeError("EXP-072 verifier imported producer scoring code")


def _output_snapshot(runner: Any, public: Path, private: Path) -> dict[str, Any]:
    return {path.relative_to(PROJECT_ROOT).as_posix(): runner.artifact(path)
            for root in (public, private) for path in sorted(root.rglob("*")) if path.is_file()}


CHECKS = [
    "config_implementation_and_075_terminal", "source_identity_before_after", "exact_public_private_prefix",
    "seventy_worker_order_and_seal", "fifteen_a0_before_ablations", "independent_scale_masks_112_modules",
    "worker_source_tensor_preservation", "heldout_ordinal_fold_sample_alignment", "independent_saved_logit_a0_replay",
    "matching_full_ablation_rendering", "compressed_threshold_allowlist_only", "labels_after_complete_prediction_gate",
    "independent_stable_sigmoid_and_thresholds", "fourteen_pooled_oof_metrics", "independent_ablation_minus_full_deltas",
    "independent_vector_flip_and_logit_mae", "exact_private_gold_predictions", "public_score_schema_digest",
    "resource_and_model_free_access", "sealed_outputs_unchanged",
]


def verify(config_path: Path) -> dict[str, Any]:
    started = time.monotonic()
    config_path = config_path.resolve()
    runner = load_runner(config_path)
    config = runner.load_config(config_path)
    if runner.require_record(config["implementation"]["verifier"]).resolve() != Path(__file__).resolve():
        raise ValueError("EXP-072 verifier config identity drift")
    _no_model_or_scorer_import()
    with runner.file_lock(runner.HEAVY_LOCK), runner.file_lock(runner.PREFIX + "/private/locks/exp-072-verifier.lock"):
        if shutil.disk_usage(PROJECT_ROOT).free < 10 * 1024**3:
            raise ValueError("EXP-072 verifier free-disk gate failed")
        metadata = runner.metadata_gate(config_path, config)
        public, private = require_scored_prefix(runner, config)
        initial_config = runner.artifact(config_path)
        before_outputs = _output_snapshot(runner, public, private)
        manifest, workers, seal_record = validate_prediction_seal(runner, config_path, config, metadata)
        run = _canonical(runner, public / "run.json")
        if run["resources"]["peak_mlx_bytes"] < max(value["resources"]["peak_mlx_bytes"] for value in workers.values()) or run["resources"]["peak_rss_bytes"] < max(value["resources"]["peak_rss_bytes"] for value in workers.values()):
            raise ValueError("EXP-072 run resource peak under-reports sealed workers")
        _budget(started)
        sample_ids, folds, logits, thresholds, replays = load_prediction_sources(runner, metadata, config, manifest, workers, started=started)
        _budget(started)
        gate = {"seal": seal_record, "workers_validated": len(workers), "a0_replays_validated": len(replays)}
        gold, label_record = load_gold_after_gate(runner, metadata, config, sample_ids, folds, gate)
        results, predictions = score_arrays(gold, logits, thresholds)
        score = validate_score_report(runner, config_path, config, metadata, seal_record, results, gold, folds, predictions)
        after = runner.metadata_gate(config_path, config)
        runner.require_record(label_record)
        if after["source_snapshot"] != metadata["source_snapshot"] or after["source_snapshot_sha256"] != metadata["source_snapshot_sha256"] or runner.artifact(config_path) != initial_config or _output_snapshot(runner, public, private) != before_outputs:
            raise ValueError("EXP-072 source or sealed output mutation")
        _budget(started)
        _no_model_or_scorer_import()
        result = {
            "schema_version": "exp-072-ablation-verification-v1", **_common(), "tier": "Major", "rq_id": "RQ-S4.3",
            "status": "Passed", "complete": True, "exp072_complete": True, "passed_count": len(CHECKS), "failed_count": 0,
            "checks": CHECKS, "config": initial_config, "score": runner.artifact(public / "score.json"),
            "prediction_seal": seal_record, "results_sha256": runner.digest(score["results"]),
            "recomputed_results_sha256": runner.digest(results), "source_snapshot_sha256": metadata["source_snapshot_sha256"],
            "source_unchanged": True, "worker_count": 70, "a0_worker_count": 15, "condition_count": 14,
            "a0_replay_max_abs_error": max(replays.values()), "label_source_sha256": label_record["sha256"],
            "scored_predictions_sha256": runner.artifact(private / "scored-predictions.npz")["sha256"],
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "resources": {"wall_seconds": time.monotonic() - started, "peak_rss_bytes": _peak_rss_bytes(), "api_cost_usd": 0},
            "access": {**SCORE_ACCESS, "worker_logits_read": True, "a0_reference_members_read": ["sample_ids", "fold_ids", "logits"], "scale_maps_verified": True},
        }
        runner.create_json_once(public / "verification.json", result, private=False)
        return result


def _record_failure(config_path: Path, error: BaseException) -> None:
    try:
        runner = load_runner(config_path)
        config = runner.load_config(config_path)
        public, private = require_scored_prefix(runner, config)
        detail = runner.create_json_once(private / "verification-failure.json", {
            "schema_version": "exp-072-verification-failure-private-v1", **_common(),
            "error_type": type(error).__name__, "message": str(error),
            "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
        }, private=True)
        runner.create_json_once(public / "verification.json", {
            "schema_version": "exp-072-ablation-verification-v1", **_common(), "status": "Failed", "complete": False,
            "exp072_complete": False, "automatic_retry": False, "error_code": "verification_failed", "error_type": type(error).__name__,
            "config": runner.artifact(config_path), "private_failure_sha256": detail["sha256"]}, private=False)
    except Exception:
        return


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args(argv)
    path = args.config.resolve()
    try:
        result = verify(path)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as error:
        _record_failure(path, error)
        print(json.dumps({"experiment_id": EXPERIMENT_ID, "status": "Failed", "error_code": "verification_failed", "error_type": type(error).__name__}), file=sys.stderr)
        return 1
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "status": result["status"], "complete": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
