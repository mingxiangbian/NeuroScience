#!/usr/bin/env python3
"""Independently verify EXP-054 preflight or one completed seed."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import subprocess
from typing import Any, Callable, Sequence

import numpy as np
from safetensors import safe_open


EXPERIMENT_ID = "EXP-054"
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-054-m4-three-seed.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def resolve_project(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def require_record(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file() or path.stat().st_size != int(record["bytes"]) or sha256(path) != record["sha256"]:
        raise ValueError(f"Artifact record mismatch: {path}")
    return path


def load_record(record: dict[str, Any]) -> dict[str, Any]:
    return json.loads(require_record(record).read_text(encoding="utf-8"))


def dynamic_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


class Checks:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.rows.append({"name": name, "passed": bool(passed), "detail": detail})

    def run(self, name: str, callback: Callable[[], Any]) -> Any:
        try:
            value = callback()
            self.add(name, True)
            return value
        except Exception as exc:
            self.add(name, False, f"{type(exc).__name__}: {exc}")
            return None

    @property
    def failures(self) -> list[str]:
        return [row["name"] for row in self.rows if not row["passed"]]


def close_values(left: Any, right: Any, tolerance: float = 1e-10) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(close_values(left[key], right[key], tolerance) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(close_values(a, b, tolerance) for a, b in zip(left, right))
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=tolerance)
    return left == right


def metric_bundle(gold: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    tp = np.sum((gold == 1) & (predicted == 1), axis=0, dtype=np.int64)
    fp = np.sum((gold == 0) & (predicted == 1), axis=0, dtype=np.int64)
    fn = np.sum((gold == 1) & (predicted == 0), axis=0, dtype=np.int64)
    tn = np.sum((gold == 0) & (predicted == 0), axis=0, dtype=np.int64)
    precision = np.divide(tp, tp + fp, out=np.zeros(6), where=(tp + fp) != 0)
    recall = np.divide(tp, tp + fn, out=np.zeros(6), where=(tp + fn) != 0)
    f1 = np.divide(2 * tp, 2 * tp + fp + fn, out=np.zeros(6), where=(2 * tp + fp + fn) != 0)
    support = tp + fn
    denominator = 2 * tp.sum() + fp.sum() + fn.sum()
    cardinality = predicted.sum(axis=1)
    keep = [0, 1, 3, 4, 5]
    return {
        "subset_accuracy": float(np.mean(np.all(gold == predicted, axis=1))),
        "accuracy_definition": "strict subset/exact-match accuracy",
        "hamming_loss": float(np.mean(gold != predicted)),
        "macro": {"precision": float(precision.mean()), "recall": float(recall.mean()), "f1": float(f1.mean())},
        "micro_f1": float(2 * tp.sum() / denominator) if denominator else 0.0,
        "weighted_f1": float(np.sum(f1 * support) / support.sum()) if support.sum() else 0.0,
        "five_label_macro_f1_without_surprise": float(f1[keep].mean()),
        "per_label": {
            label: {
                "label_id": index, "precision": float(precision[index]), "recall": float(recall[index]),
                "f1": float(f1[index]), "support": int(support[index]),
                "predicted_support": int(tp[index] + fp[index]), "tn": int(tn[index]),
                "fp": int(fp[index]), "fn": int(fn[index]), "tp": int(tp[index]),
            }
            for index, label in enumerate(LABELS)
        },
        "prediction_diagnostics": {
            "empty_prediction_rows": int(np.sum(cardinality == 0)),
            "empty_prediction_rate": float(np.mean(cardinality == 0)),
            "predicted_label_cardinality_mean": float(np.mean(cardinality)),
            "predicted_label_cardinality_median": float(np.median(cardinality)),
        },
        "primary": {"name": "six_label_macro_f1", "value": float(f1.mean())},
    }


def fast_f1(gold: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    tp = np.sum((gold == 1) & (predicted == 1), axis=0, dtype=np.int64)
    fp = np.sum((gold == 0) & (predicted == 1), axis=0, dtype=np.int64)
    fn = np.sum((gold == 1) & (predicted == 0), axis=0, dtype=np.int64)
    denominator = 2 * tp + fp + fn
    return np.divide(2 * tp, denominator, out=np.zeros(6), where=denominator != 0)


def component_bootstrap(
    gold: np.ndarray, first: np.ndarray, components_by_row: Sequence[str], seed_material: str,
    replicates: int, second: np.ndarray | None = None,
) -> dict[str, Any]:
    components = sorted(set(components_by_row))
    component_array = np.asarray(components_by_row)
    groups = {component: np.flatnonzero(component_array == component) for component in components}
    rng_seed = int(hashlib.sha256(seed_material.encode()).hexdigest()[:16], 16) % (2**32)
    rng = np.random.default_rng(rng_seed)
    values = np.zeros((replicates, 6))
    for replicate in range(replicates):
        draws = rng.integers(0, len(components), size=len(components))
        indices = np.concatenate([groups[components[index]] for index in draws])
        values[replicate] = fast_f1(gold[indices], first[indices])
        if second is not None:
            values[replicate] -= fast_f1(gold[indices], second[indices])
    point = fast_f1(gold, first)
    if second is not None:
        point -= fast_f1(gold, second)

    def interval(series: np.ndarray, value: float) -> dict[str, float]:
        lower, upper = np.quantile(series, [0.025, 0.975], method="linear")
        return {"point": float(value), "lower": float(lower), "upper": float(upper)}

    keep = [0, 1, 3, 4, 5]
    prefix = "macro_f1_delta" if second is not None else "macro_f1"
    five_prefix = "five_label_macro_f1_delta_without_surprise" if second is not None else "five_label_macro_f1_without_surprise"
    label_prefix = "per_label_f1_delta" if second is not None else "per_label_f1"
    return {
        "unit": "duplicate_component_id", "component_count": len(components),
        "row_count": len(components_by_row), "replicates": replicates, "seed": rng_seed,
        "seed_material": seed_material, "interval": "percentile_2.5_97.5",
        prefix: interval(values.mean(axis=1), float(point.mean())),
        five_prefix: interval(values[:, keep].mean(axis=1), float(point[keep].mean())),
        label_prefix: {
            label: interval(values[:, index], float(point[index]))
            for index, label in enumerate(LABELS)
        },
    }


def load_config(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID or config.get("formal_execution_authorized") is not True:
        raise ValueError("EXP-054 config identity/authorization drift")
    for record in config["implementation"].values():
        require_record(record)
    shared = load_record(config["prerequisites"]["shared_config"])
    if shared["data"]["test_status"] != "sealed_not_authorized_for_model_access":
        raise PermissionError("Test boundary drift")
    return config, shared


def load_split(shared: dict[str, Any], split: str) -> list[dict[str, Any]]:
    if split not in ("train", "validation"):
        raise PermissionError(split)
    path = resolve_project(shared["data"][f"{split}_path"])
    if sha256(path) != shared["data"][f"{split}_sha256"]:
        raise ValueError(f"{split} hash drift")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if len(rows) != shared["data"][f"{split}_rows"]:
        raise ValueError(f"{split} row count drift")
    return rows


def private_mode(path: Path) -> bool:
    return stat.S_IMODE(path.stat().st_mode) == 0o600


def gitignored(path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(path)], cwd=REPO_ROOT, check=False
    )
    return result.returncode == 0


def verify_preflight(config_path: Path) -> dict[str, Any]:
    config, shared = load_config(config_path)
    checks = Checks()
    public_dir = resolve_project(config["execution"]["preflight_public_dir"])
    run_path = public_dir / "run.json"
    run = checks.run("preflight run readable", lambda: json.loads(run_path.read_text(encoding="utf-8")))
    if run is None:
        return finish_verification(public_dir, checks, "formal-train-only-preflight", False, False)
    checks.add("preflight status passed", run.get("status") == "Passed")
    checks.add("preflight train only", run.get("accessed_splits") == ["train"])
    checks.add("preflight validation sealed", run.get("validation_split_accessed") is False)
    checks.add("preflight test sealed", run.get("test_split_accessed") is False)
    checks.add("preflight no metrics", run.get("performance_metrics_computed") is False)
    checks.add("two finite updates", len(run["training"]["finite_losses"]) == 2 and all(math.isfinite(x) for x in run["training"]["finite_losses"]))
    checks.add("prompt fully masked", run["training"].get("prompt_loss_masked") is True)
    checks.add("all train sequences checked", run["training"]["tokenization"]["rows"] == shared["data"]["train_rows"])
    checks.add("all targets canonical", run["training"]["tokenization"].get("all_targets_canonical") is True)
    checks.add("LoRA insertion count", run["model"]["insertion_count"] == 112)
    checks.add("LoRA parameter count", run["model"]["trainable_parameter_count"] == 7340032)
    checks.add("all LoRA B tensors updated", run["model"]["nonzero_lora_b_tensors"] == 112)
    checks.add("LoRA digest changed", run["model"]["lora_initial_sha256"] != run["model"]["lora_final_sha256"])
    checks.add("peak memory within budget", run["resources"]["peak_mlx_memory_gb"] <= config["execution"]["maximum_peak_memory_gb"])
    for name, record in run["artifacts"].items():
        checks.run(f"artifact {name}", lambda record=record: require_record(record))
    adapter = require_record(run["artifacts"]["adapter_private"])
    generations = require_record(run["artifacts"]["generation_private"])
    checks.add("private adapter mode", private_mode(adapter))
    checks.add("private generations mode", private_mode(generations))
    checks.add("private adapter ignored", gitignored(adapter))
    checks.add("private generations ignored", gitignored(generations))
    parser_module = dynamic_module("exp054_verify_preflight_parser", require_record(config["implementation"]["parser"]))
    rows = [json.loads(line) for line in generations.read_text(encoding="utf-8").splitlines()]
    checks.add("four preflight generations", len(rows) == 4)
    checks.add("preflight parser independently matches", all(
        parser_module.parse_output(row["raw_output"], LABELS) == row["parsed"] for row in rows
    ))
    checks.add("preflight public output has no raw generation", '"raw_output"' not in run_path.read_text(encoding="utf-8"))
    checks.add("preflight API cost zero", run["resources"]["api_cost_usd"] == 0)
    return finish_verification(public_dir, checks, "formal-train-only-preflight", False, False)


def verify_seed(config_path: Path, seed: int) -> dict[str, Any]:
    config, shared = load_config(config_path)
    if seed not in (42, 43, 44):
        raise ValueError(seed)
    checks = Checks()
    run_dir = resolve_project(config["execution"]["public_seed_dir_pattern"].format(seed=seed))
    run_path = run_dir / "run.json"
    run = checks.run("formal run readable", lambda: json.loads(run_path.read_text(encoding="utf-8")))
    if run is None:
        return finish_verification(run_dir, checks, f"seed-{seed}-train-validation", True, False)
    checks.add("experiment identity", run.get("experiment_id") == EXPERIMENT_ID)
    checks.add("seed stage identity", run.get("stage") == f"seed-{seed}-train-validation")
    checks.add("run completed", run.get("status") == "Completed")
    checks.add("train and validation only", run.get("accessed_splits") == ["train", "validation"])
    checks.add("test sealed", run.get("test_split_accessed") is False)
    checks.add("formal training authorized", run.get("formal_training_authorized") is True)
    checks.add("exact optimizer steps", run["training"]["total_optimizer_steps"] == 6720)
    checks.add("two epochs", run["training"]["epochs"] == 2 and len(run["training"]["history"]) == 2)
    checks.add("assistant-only objective", run["training"]["loss"] == "assistant_only_next_token_cross_entropy")
    checks.add("prompt masked", run["training"]["prompt_loss_masked"] is True)
    checks.add("greedy no retry", run["parser_and_generation"]["temperature"] == 0.0 and run["parser_and_generation"]["retries"] == 0)
    checks.add("max new tokens 48", run["parser_and_generation"]["max_new_tokens"] == 48)
    checks.add("LoRA insertion count", run["model"]["insertion_count"] == 112)
    checks.add("LoRA parameter count", run["model"]["trainable_parameter_count"] == 7340032)
    checks.add("all LoRA B tensors updated", run["model"]["nonzero_lora_b_tensors"] == 112)
    checks.add("base sentinel unchanged", run["model"]["base_parameter_sentinel_before"] == run["model"]["base_parameter_sentinel_after"])
    m3_run = load_record(config["prerequisites"][f"m3_seed_{seed}"]["run"])
    checks.add("M3-M4 initial LoRA matched", run["model"]["lora_initial_sha256"] == m3_run["model"]["lora_initial_sha256"])
    checks.add("training budget", run["resources"]["training_seconds"] <= config["execution"]["maximum_training_hours_per_seed"] * 3600)
    checks.add("validation inference budget", run["resources"]["validation_generation_seconds"] <= config["execution"]["maximum_validation_inference_hours_per_seed"] * 3600)
    checks.add("wall budget", run["resources"]["wall_seconds"] <= config["execution"]["maximum_total_wall_hours_per_seed"] * 3600)
    checks.add("memory budget", run["resources"]["peak_mlx_memory_gb"] <= config["execution"]["maximum_peak_memory_gb"])
    checks.add("API cost zero", run["resources"]["api_cost_usd"] == 0)
    for name, record in run["artifacts"].items():
        if name == "epoch_checkpoints_private":
            for epoch_name, nested in record.items():
                checks.run(f"artifact {name} {epoch_name}", lambda nested=nested: require_record(nested))
        else:
            checks.run(f"artifact {name}", lambda record=record: require_record(record))

    validation_rows = load_split(shared, "validation")
    expected_ids = [row["sample_id"] for row in validation_rows]
    expected_components = [row["component_id"] for row in validation_rows]
    expected_gold = np.asarray([row["labels"] for row in validation_rows], dtype=np.uint8)
    predictions_path = require_record(run["artifacts"]["selected_predictions_private"])
    raw_path = require_record(run["artifacts"]["selected_raw_generations_private"])
    checks.add("private predictions mode", private_mode(predictions_path))
    checks.add("private raw mode", private_mode(raw_path))
    checks.add("private predictions ignored", gitignored(predictions_path))
    checks.add("private raw ignored", gitignored(raw_path))
    with np.load(predictions_path, allow_pickle=False) as private:
        predicted = np.asarray(private["predictions"], dtype=np.uint8)
        private_gold = np.asarray(private["gold"], dtype=np.uint8)
        private_ids = private["sample_ids"].tolist()
        private_components = private["component_ids"].tolist()
        parser_valid = np.asarray(private["parser_valid"], dtype=np.uint8)
    checks.add("prediction shape", predicted.shape == (720, 6))
    checks.add("prediction binary", set(np.unique(predicted)).issubset({0, 1}))
    checks.add("gold independently matches", np.array_equal(private_gold, expected_gold))
    checks.add("validation order independently matches", private_ids == expected_ids)
    checks.add("component order independently matches", private_components == expected_components)
    parser_module = dynamic_module(f"exp054_verify_parser_{seed}", require_record(config["implementation"]["parser"]))
    raw_rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    checks.add("raw generation row count", len(raw_rows) == 720)
    checks.add("raw generation row order", [row["sample_id"] for row in raw_rows] == expected_ids)
    independently_parsed = [parser_module.parse_output(row["raw_output"], LABELS) for row in raw_rows]
    parsed_vectors = np.asarray([row["vector"] for row in independently_parsed], dtype=np.uint8)
    parsed_valid = np.asarray([row["valid"] for row in independently_parsed], dtype=np.uint8)
    checks.add("strict parser independently matches saved rows", all(a == b["parsed"] for a, b in zip(independently_parsed, raw_rows)))
    checks.add("strict parser independently matches predictions", np.array_equal(parsed_vectors, predicted))
    checks.add("strict parser independently matches validity", np.array_equal(parsed_valid, parser_valid))
    checks.add("invalid output retained as all zero", all(row["vector"] == [0] * 6 for row in independently_parsed if not row["valid"]))
    recomputed = metric_bundle(expected_gold, predicted)
    checks.add("metrics independently recomputed", close_values(recomputed, run["metrics"]))
    checks.add("parser valid count recomputed", int(parsed_valid.sum()) == run["parser_and_generation"]["parser_valid_count"])
    checks.add("parser valid rate recomputed", math.isclose(float(parsed_valid.mean()), run["parser_and_generation"]["parser_valid_rate"], abs_tol=1e-12))

    history = run["training"]["history"]
    max_macro = max(row["macro_f1"] for row in history)
    eligible = [row for row in history if max_macro - row["macro_f1"] < 0.005]
    selected_epoch = min(row["epoch"] for row in eligible)
    checks.add("checkpoint selection independently recomputed", selected_epoch == run["selection"]["selected_epoch"])
    checks.add("selected metrics match selected history", math.isclose(run["metrics"]["macro"]["f1"], next(row["macro_f1"] for row in history if row["epoch"] == selected_epoch), abs_tol=1e-12))

    replicates = int(shared["evaluation"]["bootstrap"]["replicates"])
    namespace = shared["evaluation"]["bootstrap"]["seed_namespace"]
    bootstrap = component_bootstrap(
        expected_gold, predicted, expected_components,
        f"{namespace}|EXP-054|seed-{seed}|M4", replicates,
    )
    checks.add("bootstrap independently recomputed", close_values(bootstrap, run["bootstrap"]))
    m3_predictions_path = require_record(m3_run["artifacts"]["validation_predictions_private"])
    with np.load(m3_predictions_path, allow_pickle=False) as m3_private:
        m3_predicted = np.asarray(m3_private["shared_threshold_predictions"], dtype=np.uint8)
    paired = component_bootstrap(
        expected_gold, predicted, expected_components,
        f"{namespace}|EXP-054|seed-{seed}|M4-minus-M3-shared-threshold", replicates, m3_predicted,
    )
    run_paired_core = {key: value for key, value in run["paired_m4_minus_m3"].items() if key not in ("comparison", "metric_deltas")}
    checks.add("paired bootstrap independently recomputed", close_values(paired, run_paired_core))
    checks.add("paired macro delta arithmetic", math.isclose(
        run["paired_m4_minus_m3"]["metric_deltas"]["macro_f1"],
        run["metrics"]["macro"]["f1"] - m3_run["metrics"]["shared_threshold"]["macro"]["f1"],
        abs_tol=1e-12,
    ))

    adapter_path = require_record(run["artifacts"]["selected_adapter_private"])
    with safe_open(str(adapter_path), framework="numpy") as source:
        adapter_names = sorted(source.keys())
        adapter_parameters = sum(int(np.prod(source.get_tensor(name).shape)) for name in adapter_names)
    checks.add("selected adapter tensor count", len(adapter_names) == 224)
    checks.add("selected adapter parameter count", adapter_parameters == 7340032)
    checks.add("selected adapter private mode", private_mode(adapter_path))
    checks.add("selected adapter ignored", gitignored(adapter_path))

    replay_rows: list[list[dict[str, Any]]] = []
    for pass_index in (1, 2):
        replay_path = run_dir / f"replay-pass-{pass_index}.json"
        replay = checks.run(f"replay pass {pass_index} readable", lambda replay_path=replay_path: json.loads(replay_path.read_text(encoding="utf-8")))
        if replay is None:
            continue
        checks.add(f"replay pass {pass_index} completed", replay.get("status") == "Completed")
        checks.add(f"replay pass {pass_index} validation only", replay.get("accessed_splits") == ["validation"] and replay.get("test_split_accessed") is False)
        checks.add(f"replay pass {pass_index} no retry", replay.get("retries") == 0)
        checks.add(f"replay pass {pass_index} selection unchanged", replay.get("checkpoint_selection_changed") is False)
        private_replay = require_record(replay["artifacts"]["private_generations"])
        checks.add(f"replay pass {pass_index} private mode", private_mode(private_replay))
        checks.add(f"replay pass {pass_index} ignored", gitignored(private_replay))
        rows = [json.loads(line) for line in private_replay.read_text(encoding="utf-8").splitlines()]
        replay_rows.append(rows)
        checks.add(f"replay pass {pass_index} row count", len(rows) == 60)
        checks.add(f"replay pass {pass_index} parser recomputed", all(
            parser_module.parse_output(row["raw_output"], LABELS) == row["parsed"] for row in rows
        ))
        checks.add(f"replay pass {pass_index} formal raw agreement", all(
            row["raw_output"] == raw_rows[expected_ids.index(row["sample_id"])]["raw_output"] for row in rows
        ))
    if len(replay_rows) == 2:
        checks.add("replay sample order stable", [row["sample_id"] for row in replay_rows[0]] == [row["sample_id"] for row in replay_rows[1]])
        checks.add("replay raw output stable", [row["raw_output"] for row in replay_rows[0]] == [row["raw_output"] for row in replay_rows[1]])
        checks.add("replay parsed vector stable", [row["parsed"]["vector"] for row in replay_rows[0]] == [row["parsed"]["vector"] for row in replay_rows[1]])
        expected_subset = sorted(
            validation_rows,
            key=lambda row: hashlib.sha256(f"{config['execution']['replay_selection_namespace']}|{row['sample_id']}".encode()).hexdigest(),
        )[:60]
        checks.add("replay subset independently selected", [row["sample_id"] for row in replay_rows[0]] == [row["sample_id"] for row in expected_subset])
        checks.add("replay subset digest frozen", canonical_digest([row["sample_id"] for row in expected_subset]) == config["execution"]["expected_replay_subset_digest_sha256"])
    checks.add("public run omits raw output", '"raw_output"' not in run_path.read_text(encoding="utf-8"))
    return finish_verification(run_dir, checks, f"seed-{seed}-train-validation", True, False)


def finish_verification(
    directory: Path, checks: Checks, stage: str, validation_accessed: bool, test_accessed: bool,
) -> dict[str, Any]:
    result = {
        "schema_version": "exp-054-m4-verification-v1", "experiment_id": EXPERIMENT_ID,
        "stage": stage, "status": "Passed" if not checks.failures else "Failed",
        "verified_at_utc": utc_now(), "checks_total": len(checks.rows),
        "checks_passed": len(checks.rows) - len(checks.failures),
        "failed_checks": checks.failures, "checks": checks.rows,
        "performance_metrics_recomputed": stage != "formal-train-only-preflight",
        "validation_split_accessed": validation_accessed, "test_split_accessed": test_accessed,
    }
    output = directory / "verification.json"
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite verification: {output}")
    atomic_json(output, result)
    summary = "\n".join([
        f"# EXP-054 Verification: {stage}", "",
        f"- Status: `{result['status']}`",
        f"- Checks: `{result['checks_passed']}/{result['checks_total']}`",
        f"- Validation accessed by verifier: `{'yes' if validation_accessed else 'no'}`",
        "- Test accessed: `no`", "",
        "Failures: " + (", ".join(checks.failures) if checks.failures else "none"), "",
    ])
    (directory / "VERIFICATION-SUMMARY.md").write_text(summary, encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--mode", required=True, choices=("preflight", "seed"))
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    if args.mode == "preflight":
        if args.seed is not None:
            raise ValueError("Preflight verification does not accept --seed")
        result = verify_preflight(args.config.resolve())
    else:
        if args.seed is None:
            raise ValueError("Seed verification requires --seed")
        result = verify_seed(args.config.resolve(), args.seed)
    print(json.dumps({"status": result["status"], "checks": result["checks_total"], "failed": result["failed_checks"]}, sort_keys=True))
    if result["status"] != "Passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
