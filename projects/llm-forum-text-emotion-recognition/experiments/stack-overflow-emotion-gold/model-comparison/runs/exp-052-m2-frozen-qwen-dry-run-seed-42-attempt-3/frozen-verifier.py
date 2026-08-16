#!/usr/bin/env python3
"""Independently verify one authorized EXP-052 stage."""

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
import subprocess
from typing import Any, Sequence

import numpy as np
from safetensors.numpy import load_file as load_safetensors


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
TOLERANCE = 1e-10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
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
    encoded = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def resolve_project(recorded: str) -> Path:
    path = Path(recorded)
    resolved = path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()
    if resolved != PROJECT_ROOT and PROJECT_ROOT not in resolved.parents:
        raise ValueError(f"Path escapes project root: {recorded}")
    return resolved


def project_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def artifact(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "path": project_path(path), "sha256": sha256_file(path)}


def verify_artifact(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file() or path.stat().st_size != record["bytes"] or sha256_file(path) != record["sha256"]:
        raise ValueError(f"Artifact drift: {path}")
    return path


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def assert_close(name: str, observed: float, recorded: float, tolerance: float = TOLERANCE) -> None:
    if not math.isclose(float(observed), float(recorded), rel_tol=0.0, abs_tol=tolerance):
        raise ValueError(f"{name} differs: observed={observed}, recorded={recorded}")


def load_rows(shared: dict[str, Any], split: str) -> list[dict[str, Any]]:
    if split not in ("train", "validation"):
        raise PermissionError(split)
    path = resolve_project(shared["data"][f"{split}_path"])
    if sha256_file(path) != shared["data"][f"{split}_sha256"]:
        raise ValueError(f"{split} hash drift")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if len(rows) != shared["data"][f"{split}_rows"]:
        raise ValueError(f"{split} row count drift")
    return rows


def independently_select_dry_rows(
    rows: Sequence[dict[str, Any]], count: int, namespace: str
) -> list[dict[str, Any]]:
    ranked = sorted(
        rows,
        key=lambda row: hashlib.sha256(f"{namespace}|{row['sample_id']}".encode()).hexdigest(),
    )
    chosen: dict[str, dict[str, Any]] = {}
    for label_index, label in enumerate(LABELS):
        positives = [row for row in ranked if row["labels"][label_index] == 1]
        ordered = sorted(
            positives,
            key=lambda row: hashlib.sha256(
                f"{namespace}|positive|{label}|{row['sample_id']}".encode()
            ).hexdigest(),
        )
        for row in ordered[:2]:
            chosen[row["sample_id"]] = row
    for row in ranked:
        chosen.setdefault(row["sample_id"], row)
        if len(chosen) == count:
            break
    return sorted(
        chosen.values(),
        key=lambda row: hashlib.sha256(
            f"{namespace}|final|{row['sample_id']}".encode()
        ).hexdigest(),
    )


def _messages(prompt: dict[str, Any], text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": prompt["system"]},
        {"role": "user", "content": prompt["user_prefix"] + text + prompt["user_suffix"]},
    ]


def _chat_ids(tokenizer: Any, prompt: dict[str, Any], text: str) -> list[int]:
    value = tokenizer.apply_chat_template(
        _messages(prompt, text),
        tokenize=True,
        return_dict=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    if not isinstance(value, list) or any(type(token) is not int for token in value):
        raise TypeError("Unexpected tokenizer output")
    return value


def independently_tokenize(
    tokenizer: Any, prompt: dict[str, Any], text: str, limit: int
) -> tuple[list[int], int, bool]:
    full = _chat_ids(tokenizer, prompt, text)
    if len(full) <= limit:
        selected, truncated = full, False
    else:
        target_ids = tokenizer.encode(text, add_special_tokens=False)
        selected = _chat_ids(tokenizer, prompt, "")
        for count in range(len(target_ids) + 1):
            candidate = _chat_ids(
                tokenizer,
                prompt,
                tokenizer.decode(target_ids[:count], skip_special_tokens=False),
            )
            if len(candidate) <= limit:
                selected = candidate
            else:
                break
        truncated = True
    if len(selected) > limit or not tokenizer.decode(selected).endswith("<think>\n\n</think>\n\n"):
        raise ValueError("Independent tokenization contract failed")
    return selected, len(full), truncated


def tokenization_summary(
    rows: Sequence[dict[str, Any]], shared: dict[str, Any]
) -> dict[str, Any]:
    from transformers import AutoTokenizer

    prompt_path = resolve_project(shared["prompt"]["path"])
    if sha256_file(prompt_path) != shared["prompt"]["sha256"]:
        raise ValueError("Prompt hash drift")
    prompt = json.loads(prompt_path.read_text(encoding="utf-8"))
    tokenizer = AutoTokenizer.from_pretrained(
        resolve_project(shared["models"]["qwen_shared"]["local_path"]),
        local_files_only=True,
    )
    digest = hashlib.sha256()
    lengths: list[int] = []
    raw_lengths: list[int] = []
    truncated = 0
    for index, row in enumerate(rows):
        ids, raw_length, was_truncated = independently_tokenize(
            tokenizer, prompt, row["text"], int(shared["prompt"]["max_sequence_length"])
        )
        canonical = np.asarray(ids, dtype="<i4")
        digest.update((index + 1).to_bytes(8, "little", signed=False))
        digest.update(len(ids).to_bytes(4, "little", signed=False))
        digest.update(canonical.tobytes(order="C"))
        lengths.append(len(ids))
        raw_lengths.append(raw_length)
        truncated += int(was_truncated)
    return {
        "token_id_stream_sha256": digest.hexdigest(),
        "minimum": min(lengths),
        "maximum": max(lengths),
        "mean": float(np.mean(lengths)),
        "p95": float(np.quantile(lengths, 0.95)),
        "raw_maximum": max(raw_lengths),
        "truncated_rows": truncated,
    }


def metric_bundle(gold: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    tp = np.sum((gold == 1) & (predicted == 1), axis=0, dtype=np.int64)
    fp = np.sum((gold == 0) & (predicted == 1), axis=0, dtype=np.int64)
    fn = np.sum((gold == 1) & (predicted == 0), axis=0, dtype=np.int64)
    tn = np.sum((gold == 0) & (predicted == 0), axis=0, dtype=np.int64)
    precision = np.divide(tp, tp + fp, out=np.zeros(6, dtype=np.float64), where=(tp + fp) != 0)
    recall = np.divide(tp, tp + fn, out=np.zeros(6, dtype=np.float64), where=(tp + fn) != 0)
    f1 = np.divide(2 * tp, 2 * tp + fp + fn, out=np.zeros(6, dtype=np.float64), where=(2 * tp + fp + fn) != 0)
    micro_denominator = 2 * tp.sum() + fp.sum() + fn.sum()
    micro_f1 = float(2 * tp.sum() / micro_denominator) if micro_denominator else 0.0
    support = tp + fn
    weighted_f1 = float(np.sum(f1 * support) / support.sum()) if support.sum() else 0.0
    cardinality = predicted.sum(axis=1)
    without_surprise = [0, 1, 3, 4, 5]
    return {
        "subset_accuracy": float(np.mean(np.all(gold == predicted, axis=1))),
        "accuracy_definition": "strict subset/exact-match accuracy",
        "hamming_loss": float(np.mean(gold != predicted)),
        "macro": {"precision": float(np.mean(precision)), "recall": float(np.mean(recall)), "f1": float(np.mean(f1))},
        "micro_f1": micro_f1,
        "weighted_f1": weighted_f1,
        "five_label_macro_f1_without_surprise": float(np.mean(f1[without_surprise])),
        "per_label": {
            label: {
                "label_id": index,
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
                "predicted_support": int(tp[index] + fp[index]),
                "tn": int(tn[index]),
                "fp": int(fp[index]),
                "fn": int(fn[index]),
                "tp": int(tp[index]),
            }
            for index, label in enumerate(LABELS)
        },
        "prediction_diagnostics": {
            "empty_prediction_rows": int(np.sum(cardinality == 0)),
            "predicted_label_cardinality_mean": float(np.mean(cardinality)),
        },
        "primary": {"name": "six_label_macro_f1", "value": float(np.mean(f1))},
    }


def compare_metrics(name: str, observed: dict[str, Any], recorded: dict[str, Any]) -> None:
    for key in ("subset_accuracy", "hamming_loss", "micro_f1", "weighted_f1", "five_label_macro_f1_without_surprise"):
        assert_close(f"{name}.{key}", observed[key], recorded[key])
    for key in ("precision", "recall", "f1"):
        assert_close(f"{name}.macro.{key}", observed["macro"][key], recorded["macro"][key])
    for label in LABELS:
        for key in ("precision", "recall", "f1"):
            assert_close(f"{name}.{label}.{key}", observed["per_label"][label][key], recorded["per_label"][label][key])
        for key in ("support", "predicted_support", "tn", "fp", "fn", "tp"):
            if observed["per_label"][label][key] != recorded["per_label"][label][key]:
                raise ValueError(f"{name}.{label}.{key} differs")


def independently_select_checkpoint(values: Sequence[float], delta: float) -> dict[str, Any]:
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


def independently_select_threshold(
    gold: np.ndarray, probabilities: np.ndarray, grid: Sequence[float]
) -> tuple[float, list[dict[str, float]]]:
    rows = [
        {
            "threshold": float(threshold),
            "macro_f1": metric_bundle(gold, (probabilities >= threshold).astype(np.uint8))["macro"]["f1"],
        }
        for threshold in grid
    ]
    best_score = max(row["macro_f1"] for row in rows)
    candidates = [row for row in rows if row["macro_f1"] == best_score]
    candidates.sort(key=lambda row: (abs(row["threshold"] - 0.5), row["threshold"]))
    return candidates[0]["threshold"], rows


def fast_f1(gold: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    tp = np.sum((gold == 1) & (predicted == 1), axis=0, dtype=np.int64)
    fp = np.sum((gold == 0) & (predicted == 1), axis=0, dtype=np.int64)
    fn = np.sum((gold == 1) & (predicted == 0), axis=0, dtype=np.int64)
    denominator = 2 * tp + fp + fn
    return np.divide(2 * tp, denominator, out=np.zeros(6, dtype=np.float64), where=denominator != 0)


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
    component_array = np.asarray(component_ids)
    groups = {component: np.flatnonzero(component_array == component) for component in components}
    seed_material = f"{namespace}|EXP-052|seed-{model_seed}|{condition}"
    seed = int(hashlib.sha256(seed_material.encode()).hexdigest()[:16], 16) % (2**32)
    rng = np.random.default_rng(seed)
    values = np.zeros((replicates, 6), dtype=np.float64)
    for replicate in range(replicates):
        draws = rng.integers(0, len(components), size=len(components))
        indices = np.concatenate([groups[components[index]] for index in draws])
        values[replicate] = fast_f1(gold[indices], predicted[indices])
    point = fast_f1(gold, predicted)

    def interval(series: np.ndarray, point_value: float) -> dict[str, float]:
        lower, upper = np.quantile(series, [0.025, 0.975], method="linear")
        return {"point": float(point_value), "lower": float(lower), "upper": float(upper)}

    keep = [0, 1, 3, 4, 5]
    return {
        "unit": "duplicate_component_id",
        "component_count": len(components),
        "row_count": len(component_ids),
        "replicates": replicates,
        "seed": seed,
        "seed_material": seed_material,
        "interval": "percentile_2.5_97.5",
        "macro_f1": interval(values.mean(axis=1), float(point.mean())),
        "five_label_macro_f1_without_surprise": interval(values[:, keep].mean(axis=1), float(point[keep].mean())),
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
            assert_close(f"{name}.{label}.{key}", observed["per_label_f1"][label][key], recorded["per_label_f1"][label][key])


def head_initial_digest(seed: int, hidden_size: int) -> str:
    import mlx.core as mx
    import mlx.nn as nn
    from mlx.utils import tree_flatten

    mx.random.seed(seed)
    head = nn.Linear(hidden_size, len(LABELS), bias=True)
    digest = hashlib.sha256()
    for name, tensor in sorted(tree_flatten(head.trainable_parameters())):
        array = np.asarray(tensor.astype(mx.float32))
        digest.update(name.encode())
        digest.update(str(tuple(array.shape)).encode())
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def replay_head(path: Path, features: np.ndarray) -> np.ndarray:
    tensors = load_safetensors(str(path))
    if set(tensors) != {"weight", "bias"}:
        raise ValueError(f"Unexpected head tensors: {sorted(tensors)}")
    weight = tensors["weight"].astype(np.float32, copy=False)
    bias = tensors["bias"].astype(np.float32, copy=False)
    logits = np.asarray(features, dtype=np.float32) @ weight.T + bias
    probabilities = np.empty_like(logits, dtype=np.float32)
    positive = logits >= 0
    probabilities[positive] = 1.0 / (1.0 + np.exp(-logits[positive]))
    exp_value = np.exp(logits[~positive])
    probabilities[~positive] = exp_value / (1.0 + exp_value)
    return probabilities


def source_access_audit(path: Path) -> dict[str, bool]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    load_split = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "load_split")
    function_source = ast.get_source_segment(source, load_split) or ""
    return {
        "explicit_train_validation_allowlist": 'if split not in ("train", "validation")' in function_source,
        "no_test_path_lookup": '[f"{split}_path"]' in function_source and '["test_path"]' not in function_source,
        "no_recursive_data_access": all(token not in function_source for token in (".glob(", ".rglob(", "os.walk(")),
        "qwen_freeze_present": source.count("model.freeze()") >= 2,
        "qwen_eval_present": source.count("model.eval()") >= 2,
        "optimizer_updates_head_only": "optimizer.update(head, gradients)" in source and "optimizer.update(model" not in source,
    }


def verify_model_files(run: dict[str, Any], shared: dict[str, Any]) -> None:
    spec = shared["models"]["qwen_shared"]
    if run["model"]["repo_id"] != spec["repo_id"] or run["model"]["revision"] != spec["revision"]:
        raise ValueError("Recorded Qwen identity drift")
    manifest_path = resolve_project(spec["manifest_path"])
    if sha256_file(manifest_path) != spec["manifest_sha256"]:
        raise ValueError("Qwen manifest drift")
    model_root = resolve_project(spec["local_path"])
    for expected in run["model"]["files"]:
        path = model_root / expected["path"]
        if path.stat().st_size != expected["bytes"] or sha256_file(path) != expected["sha256"]:
            raise ValueError(f"Qwen file drift: {expected['path']}")


def public_privacy_check(run_dir: Path, rows: Sequence[dict[str, Any]]) -> tuple[bool, bool]:
    public_files = [
        path for path in run_dir.rglob("*")
        if path.is_file() and not path.name.startswith("frozen-")
    ]
    public_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in public_files
        if path.suffix not in (".npz", ".npy", ".safetensors")
    )
    no_text = all(row["text"] not in public_text for row in rows if len(row["text"]) >= 24)
    no_ids = all(
        row["sample_id"] not in public_text and row["component_id"] not in public_text
        for row in rows
    )
    return no_text, no_ids


def subprocess_check_ignore(path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(path)], cwd=REPO_ROOT, check=False
    )
    return result.returncode == 0


def render_summary(verification: dict[str, Any], run: dict[str, Any]) -> str:
    lines = [
        f"# EXP-052 Seed {run['seed']} Verification",
        "",
        f"- Stage: `{run['stage']}`",
        f"- Status: `{verification['status']}`",
        f"- Checks: `{verification['check_count']}/{verification['check_count']}`",
        "- Test accessed: no",
    ]
    if run["stage"] == "train-only-dry-run":
        lines.extend(
            [
                "- Validation performance computed: no",
                f"- Projected extraction with safety: `{run['resource_projection']['projected_feature_extraction_minutes_with_safety']:.2f}` minutes",
                f"- Peak MLX memory: `{run['resource_usage']['peak_mlx_memory_gb']:.3f}` GB",
                "",
                "The dry-run gate passed. Formal seed-42 execution is a separate frozen contract.",
            ]
        )
    else:
        lines.extend(
            [
                f"- Selected epoch: `{run['selection']['selected_epoch']}`",
                f"- Fixed-0.5 Macro-F1: `{run['metrics']['fixed_0.5']['macro']['f1']:.6f}`",
                f"- Shared threshold: `{run['threshold_selection']['selected_threshold']:.2f}`",
                f"- Shared-threshold Macro-F1: `{run['metrics']['shared_threshold']['macro']['f1']:.6f}`",
                "",
                "This verifies only the seed-42 validation integrity gate. Test, seeds 43/44, M3 and M4 remain sealed.",
            ]
        )
    return "\n".join(lines) + "\n"


def verify() -> dict[str, Any]:
    args = parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["experiment_id"] != "EXP-052" or config["authorization"]["seeds"] != [args.seed] or args.seed != 42:
        raise PermissionError("Verifier received an unauthorized EXP-052 contract")
    run_dir = (args.run_dir or resolve_project(config["execution"]["public_run_dir"])).resolve()
    private_dir = (args.private_dir or resolve_project(config["execution"]["private_run_dir"])).resolve()
    output = run_dir / "verification.json"
    summary_path = run_dir / "VERIFICATION-SUMMARY.md"
    if output.exists() or summary_path.exists():
        raise FileExistsError("Refusing to overwrite append-only verification output")
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    shared = json.loads((run_dir / "frozen-shared-config.json").read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": bool(condition), "detail": detail})

    check("run completed", run.get("status") == "Completed")
    check("experiment identity", run.get("experiment_id") == "EXP-052" and run.get("seed") == args.seed)
    check("stage identity", run.get("stage") == config["stage"])
    check("single seed authorization", config["authorization"]["seeds"] == [42])
    check("test sealed", run.get("test_split_accessed") is False and config["authorization"]["test_access"] is False)
    check("seeds 43 and 44 sealed", config["authorization"]["seeds_43_44_authorized"] is False)
    check("M3 and M4 sealed", config["authorization"]["exp_053_054_authorized"] is False)
    check("labels frozen", tuple(run["data"]["labels"]) == LABELS)
    check("Qwen frozen", run["model_runtime"]["qwen_parameters_frozen"] is True and run["model_runtime"]["qwen_trainable_parameter_count"] == 0)
    check("linear head size", run["model_runtime"]["head_trainable_parameter_count"] == 15366)
    check("pooling frozen", run["model_runtime"]["pooling"] == shared["prompt"]["pooling"])
    check("feature dtype frozen", run["model_runtime"]["feature_dtype"] == "float32")

    for record in run["artifacts"]["frozen_sources"].values():
        verify_artifact(record)
    check("run config matches frozen config", sha256_file(config_path) == run["artifacts"]["frozen_sources"]["config"]["sha256"])
    check("shared config matches source", sha256_file(resolve_project(config["prerequisite"]["shared_config_path"])) == config["prerequisite"]["shared_config_sha256"])
    for name, record in config["implementation"].items():
        if isinstance(record, dict) and "path" in record:
            check(f"implementation hash: {name}", sha256_file(resolve_project(record["path"])) == record["sha256"])
    verify_artifact(run["artifacts"]["report"])
    verify_artifact(run["artifacts"]["stdout_log"])
    verify_artifact(run["artifacts"]["environment_freeze"])
    verify_artifact(run["artifacts"]["private_manifest"])
    verify_model_files(run, shared)
    check("model file count", run["model"]["file_count"] == 9)
    check("EXP-050 check count", run["prerequisite"]["exp050"]["check_count"] == 77)
    for name, passed in source_access_audit(run_dir / "frozen-runner.py").items():
        check(f"source access audit: {name}", passed)
    check("head initialization independently reproduced", head_initial_digest(args.seed, 2560) == run["model_runtime"]["head_initial_sha256"])
    check("head initialization matches EXP-050", run["model_runtime"]["head_initial_sha256"] == config["execution"]["expected_head_initial_sha256"])

    train_rows = load_rows(shared, "train")
    rows_for_privacy: list[dict[str, Any]] = list(train_rows)
    if run["stage"] == "train-only-dry-run":
        check("dry-run split access", run["accessed_splits"] == ["train"] and run["validation_split_accessed"] is False)
        check("no dry-run performance metrics", run["performance_metrics_computed"] is False and "metrics" not in run)
        selected = independently_select_dry_rows(
            train_rows,
            int(config["dry_run"]["sample_rows"]),
            config["dry_run"]["selection_namespace"],
        )
        check("dry-run selection count", len(selected) == run["data"]["selection"]["rows"])
        check("dry-run selection order", canonical_digest([row["sample_id"] for row in selected]) == run["data"]["selection"]["sample_order_sha256"])
        feature_path = verify_artifact(run["artifacts"]["feature_cache_private"])
        features = np.load(feature_path, mmap_mode="r")
        check("dry-run feature shape", features.shape == (len(selected), 2560), list(features.shape))
        check("dry-run feature dtype", features.dtype == np.float32, str(features.dtype))
        check("dry-run features finite", np.isfinite(features).all())
        tokenization = tokenization_summary(selected, shared)
        check("dry-run token digest", tokenization["token_id_stream_sha256"] == run["feature_cache"]["token_id_stream_sha256"])
        check("dry-run token lengths", tokenization["maximum"] == run["feature_cache"]["token_lengths"]["maximum"])
        check("dry-run no truncation", tokenization["truncated_rows"] == run["feature_cache"]["token_lengths"]["truncated_rows"] == 0)
        check("dry-run head updated", run["model_runtime"]["head_final_sha256"] != run["model_runtime"]["head_initial_sha256"])
        check("dry-run two optimizer steps", run["model_runtime"]["optimizer_steps"] == 2 and len(run["model_runtime"]["finite_losses"]) == 2)
        check("dry-run finite losses", all(math.isfinite(value) for value in run["model_runtime"]["finite_losses"]))
        check("dry-run projected extraction budget", run["resource_projection"]["projected_feature_extraction_minutes_with_safety"] <= config["execution"]["maximum_feature_extraction_minutes"])
    else:
        check("formal split access", run["accessed_splits"] == ["train", "validation"] and run["validation_split_accessed"] is True)
        check("formal performance metrics computed", run["performance_metrics_computed"] is True)
        dry_gate = run["prerequisite"]["dry_run_gate"]
        check("dry-run prerequisite recorded", dry_gate is not None and dry_gate["test_split_accessed"] is False)
        validation_rows = load_rows(shared, "validation")
        rows_for_privacy.extend(validation_rows)
        check("train validation component disjoint", not ({row["component_id"] for row in train_rows} & {row["component_id"] for row in validation_rows}))
        train_feature_path = verify_artifact(run["artifacts"]["train_features_private"])
        validation_feature_path = verify_artifact(run["artifacts"]["validation_features_private"])
        train_features = np.load(train_feature_path, mmap_mode="r")
        validation_features = np.load(validation_feature_path, mmap_mode="r")
        check("train feature shape", train_features.shape == (3360, 2560), list(train_features.shape))
        check("validation feature shape", validation_features.shape == (720, 2560), list(validation_features.shape))
        check("feature dtypes", train_features.dtype == validation_features.dtype == np.float32)
        check("features finite", np.isfinite(train_features).all() and np.isfinite(validation_features).all())
        check("train feature order", canonical_digest([row["sample_id"] for row in train_rows]) == run["feature_cache"]["train"]["sample_order_sha256"])
        check("validation feature order", canonical_digest([row["sample_id"] for row in validation_rows]) == run["feature_cache"]["validation"]["sample_order_sha256"])
        train_tokenization = tokenization_summary(train_rows, shared)
        validation_tokenization = tokenization_summary(validation_rows, shared)
        check("train token digest", train_tokenization["token_id_stream_sha256"] == run["feature_cache"]["train"]["token_id_stream_sha256"])
        check("validation token digest", validation_tokenization["token_id_stream_sha256"] == run["feature_cache"]["validation"]["token_id_stream_sha256"])
        check("formal no truncation", train_tokenization["truncated_rows"] == validation_tokenization["truncated_rows"] == 0)

        order_path = verify_artifact(run["artifacts"]["batch_orders_private"])
        orders = np.load(order_path, allow_pickle=False)
        rng = np.random.default_rng(args.seed)
        expected_orders = np.stack([rng.permutation(len(train_rows)) for _ in range(2)]).astype(np.int32)
        check("matched batch orders", np.array_equal(orders, expected_orders))
        check("two epochs and 6720 updates", run["training"]["epochs"] == 2 and run["training"]["total_optimizer_steps"] == 6720)
        for index, order in enumerate(expected_orders):
            expected_digest = canonical_digest([train_rows[int(row_index)]["sample_id"] for row_index in order])
            check(f"epoch {index + 1} order digest", run["training"]["history"][index]["batch_order_sha256"] == expected_digest)

        predictions_path = verify_artifact(run["artifacts"]["validation_predictions_private"])
        predictions = np.load(predictions_path, allow_pickle=False)
        probabilities = predictions["probabilities"]
        gold = np.asarray([row["labels"] for row in validation_rows], dtype=np.uint8)
        component_ids = [row["component_id"] for row in validation_rows]
        check("probability shape", probabilities.shape == (2, 720, 6), list(probabilities.shape))
        check("probabilities finite", np.isfinite(probabilities).all())
        check("private gold", np.array_equal(predictions["gold"], gold))
        check("private sample order", predictions["sample_ids"].tolist() == [row["sample_id"] for row in validation_rows])
        check("private component order", predictions["component_ids"].tolist() == component_ids)

        fixed_threshold = float(shared["evaluation"]["fixed_threshold"])
        epoch_metrics = [metric_bundle(gold, (values >= fixed_threshold).astype(np.uint8)) for values in probabilities]
        history_path = verify_artifact(run["artifacts"]["history"])
        with history_path.open("r", encoding="utf-8", newline="") as source:
            history = list(csv.DictReader(source))
        check("two history rows", len(history) == 2)
        for index, (metrics, row) in enumerate(zip(epoch_metrics, history), start=1):
            check(f"epoch {index} identity", int(row["epoch"]) == index and int(row["optimizer_steps"]) == index * 3360)
            check(f"epoch {index} fixed Macro-F1", math.isclose(metrics["macro"]["f1"], float(row["fixed_macro_f1"]), rel_tol=0.0, abs_tol=TOLERANCE))
            check(f"epoch {index} finite losses", math.isfinite(float(row["train_loss"])) and math.isfinite(float(row["validation_loss"])))
        selection = independently_select_checkpoint(
            [metrics["macro"]["f1"] for metrics in epoch_metrics],
            float(shared["evaluation"]["practical_tie_delta"]),
        )
        recorded_selection = json.loads(verify_artifact(run["artifacts"]["selection"]).read_text(encoding="utf-8"))
        check("checkpoint selection", selection == recorded_selection == run["selection"], selection)
        selected_probabilities = probabilities[selection["selected_epoch"] - 1]
        selected_head_path = verify_artifact(run["artifacts"]["selected_head_private"])
        replay = replay_head(selected_head_path, validation_features)
        replay_max_abs = float(np.max(np.abs(replay - selected_probabilities)))
        check("selected head replay", replay_max_abs <= 1e-7, replay_max_abs)

        selected_threshold, threshold_rows = independently_select_threshold(
            gold, selected_probabilities, shared["evaluation"]["shared_threshold_grid"]
        )
        check("shared threshold selection", selected_threshold == run["threshold_selection"]["selected_threshold"])
        threshold_path = verify_artifact(run["artifacts"]["threshold_grid"])
        with threshold_path.open("r", encoding="utf-8", newline="") as source:
            recorded_thresholds = list(csv.DictReader(source))
        check("threshold grid length", len(recorded_thresholds) == len(threshold_rows) == 19)
        for observed, recorded in zip(threshold_rows, recorded_thresholds):
            assert_close("threshold", observed["threshold"], float(recorded["threshold"]))
            assert_close("threshold Macro-F1", observed["macro_f1"], float(recorded["macro_f1"]))

        recorded_bootstrap = json.loads(verify_artifact(run["artifacts"]["bootstrap"]).read_text(encoding="utf-8"))
        for name, threshold, condition in (
            ("fixed_0.5", fixed_threshold, "fixed-0.5"),
            ("shared_threshold", selected_threshold, f"shared-{selected_threshold:.2f}"),
        ):
            predicted = (selected_probabilities >= threshold).astype(np.uint8)
            observed_metrics = metric_bundle(gold, predicted)
            compare_metrics(name, observed_metrics, run["metrics"][name])
            metrics_path = verify_artifact(run["artifacts"]["metrics_fixed" if name == "fixed_0.5" else "metrics_shared_threshold"])
            compare_metrics(name + ".file", observed_metrics, json.loads(metrics_path.read_text(encoding="utf-8")))
            observed_bootstrap = bootstrap_summary(
                gold,
                predicted,
                component_ids,
                args.seed,
                int(shared["evaluation"]["bootstrap"]["replicates"]),
                shared["evaluation"]["bootstrap"]["seed_namespace"],
                condition,
            )
            compare_bootstrap(name, observed_bootstrap, recorded_bootstrap[name])
            for kind in ("per_label", "confusion"):
                verify_artifact(run["artifacts"]["tables"]["fixed-0.5" if name == "fixed_0.5" else "shared-threshold"][kind])

    no_text, no_ids = public_privacy_check(run_dir, rows_for_privacy)
    check("public artifacts contain no substantive raw text", no_text)
    check("public artifacts contain no row identifiers", no_ids)
    check("private manifest ignored", subprocess_check_ignore(private_dir / "private-manifest.json"))
    check("private feature cache ignored", subprocess_check_ignore(resolve_project(run["artifacts"]["feature_cache_private"]["path"]) if run["stage"] == "train-only-dry-run" else resolve_project(run["artifacts"]["train_features_private"]["path"])))
    check("memory budget", run["resource_usage"]["peak_mlx_memory_gb"] <= config["execution"]["maximum_peak_memory_gb"])
    check("test remains sealed after verification", run["test_split_accessed"] is False)

    failed = [item["name"] for item in checks if not item["passed"]]
    verification = {
        "schema_version": "exp-052-m2-verification-v1",
        "experiment_id": "EXP-052",
        "stage": run["stage"],
        "seed": args.seed,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "Passed" if not failed else "Failed",
        "check_count": len(checks),
        "failed_checks": failed,
        "checks": checks,
        "test_split_accessed": False,
    }
    atomic_json(output, verification)
    summary_path.write_text(render_summary(verification, run), encoding="utf-8")
    if failed:
        raise ValueError(f"EXP-052 verification failed: {failed}")
    return verification


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
