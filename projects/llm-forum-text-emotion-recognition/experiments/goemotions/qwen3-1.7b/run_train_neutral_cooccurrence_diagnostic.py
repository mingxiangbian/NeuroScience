#!/usr/bin/env python3
"""Run EXP-034 on the frozen EXP-033 training neutral-cooccurrence slice."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
from importlib import metadata
from itertools import zip_longest
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback
from typing import Any

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["PYTHONNOUSERSITE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

EXPERIMENT_ID = "EXP-034"
CONDITION = "aligned-prompt-open-neutral"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
CONFIG_PATH = SCRIPT_DIR / "configs" / "exp-034-train-neutral-cooccurrence-diagnostic.json"
EXPECTED_PYTHON = Path("/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{time.time_ns()}")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(resolved)


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": display_path(path),
        "sha256": sha256_file(path),
    }


def verify_spec(spec: dict[str, Any]) -> dict[str, Any]:
    path = resolve_project_path(str(spec["path"]))
    observed = artifact(path)
    if observed["sha256"] != spec["sha256"]:
        raise ValueError(f"Frozen artifact drift: {path}")
    return observed


def verify_model(config: dict[str, Any]) -> dict[str, Any]:
    manifest_spec = config["model"]["manifest"]
    verify_spec(manifest_spec)
    manifest = load_json(resolve_project_path(manifest_spec["path"]))
    if (
        manifest.get("repo_id") != config["model"]["repo_id"]
        or manifest.get("revision") != config["model"]["revision"]
    ):
        raise ValueError("Frozen model identity drift")
    model_root = resolve_project_path(config["model"]["local_path"])
    count = 0
    total_bytes = 0
    for expected in manifest["mlx_bf16"]["files"]:
        relative = Path(expected["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe model manifest path")
        path = model_root / relative
        if path.stat().st_size != int(expected["bytes"]):
            raise ValueError(f"Model size drift: {path}")
        if sha256_file(path) != expected["sha256"]:
            raise ValueError(f"Model hash drift: {path}")
        count += 1
        total_bytes += path.stat().st_size
    if (
        count != int(manifest["mlx_bf16"]["file_count"])
        or total_bytes != int(manifest["mlx_bf16"]["total_bytes"])
    ):
        raise ValueError("Model inventory totals drift")
    return {"file_count": count, "total_bytes": total_bytes}


def validate_config(path: Path, expected_sha256: str) -> dict[str, Any]:
    if path.resolve() != CONFIG_PATH.resolve():
        raise ValueError(f"Use the registered config: {CONFIG_PATH}")
    if sha256_file(path) != expected_sha256:
        raise ValueError("Config SHA-256 mismatch")
    config = load_json(path)
    if "PENDING" in json.dumps(config, sort_keys=True):
        raise ValueError("Config still contains an unfrozen hash")
    if (
        config.get("experiment_id") != EXPERIMENT_ID
        or config.get("tier") != "Minor"
        or config.get("status") != "Registered"
        or config.get("parent_experiment") != "EXP-033"
        or config.get("scope", {}).get("split") != "train-neutral-cooccurrence-only"
        or config.get("scope", {}).get("expected_rows") != 1396
        or config.get("scope", {}).get("final_adapter_only") is not True
        or config.get("scope", {}).get("checkpoint_selection") is not False
        or config.get("data", {}).get("test_access") is not False
        or config.get("decoding", {}).get("condition") != CONDITION
        or config.get("decoding", {}).get("sampler") != "greedy"
        or float(config.get("decoding", {}).get("temperature", -1)) != 0.0
        or config.get("decoding", {}).get("enable_thinking") is not False
        or config.get("decoding", {}).get("generation_per_sample") != 1
        or config.get("decoding", {}).get("retry") is not False
        or config.get("decoding", {}).get("repair") is not False
    ):
        raise ValueError("EXP-034 registered scope or decoding policy drift")
    return config


def verify_static_inputs(config: dict[str, Any]) -> dict[str, Any]:
    test_path = resolve_project_path(config["data"]["test_path"])
    if test_path.exists():
        raise FileExistsError(f"GoEmotions test must remain absent: {test_path}")
    if not EXPECTED_PYTHON.is_file() or not Path(sys.executable).samefile(EXPECTED_PYTHON):
        raise ValueError(f"Use the frozen Python executable: {EXPECTED_PYTHON}")
    expected_packages = {
        "mlx": "0.32.0",
        "mlx-lm": "0.31.3",
        "numpy": "2.4.6",
        "transformers": "5.14.1",
    }
    observed_packages = {name: metadata.version(name) for name in expected_packages}
    if observed_packages != expected_packages or platform.python_version() != "3.11.15":
        raise ValueError("Frozen EXP-034 runtime drift")
    specs = {
        "source_train": config["data"]["source_train"],
        "prepared_train": config["data"]["prepared_train"],
        "labels": config["data"]["labels"],
        "target_alignment_verification": config["data"]["target_alignment_verification"],
        "adapter_config": config["adapter"]["config"],
        "adapter_weights": config["adapter"]["weights"],
        "training_verification": config["training_verification"],
        "validation_reference": config["comparison"]["validation_neutral_cooccurrence_slice"],
        "model_manifest": config["model"]["manifest"],
        **config["implementation"],
    }
    observed = {name: verify_spec(spec) for name, spec in specs.items()}
    training_verification = load_json(resolve_project_path(config["training_verification"]["path"]))
    if training_verification.get("status") != "Passed":
        raise ValueError("EXP-033 seed-42 training verification is not Passed")
    observed["model_inventory"] = verify_model(config)
    observed["packages"] = observed_packages
    observed["python"] = platform.python_version()
    return observed


def load_training_slice(
    config: dict[str, Any], labels: tuple[str, ...]
) -> list[dict[str, Any]]:
    source_path = resolve_project_path(config["data"]["source_train"]["path"])
    prepared_path = resolve_project_path(config["data"]["prepared_train"]["path"])
    neutral_id = labels.index("neutral")
    samples: list[dict[str, Any]] = []
    cardinality = Counter()
    seen_ids: set[str] = set()
    source_rows = 0
    with source_path.open("r", encoding="utf-8", newline="") as source_handle, prepared_path.open(
        "r", encoding="utf-8"
    ) as prepared_handle:
        source_reader = csv.reader(source_handle, delimiter="\t")
        for row_number, pair in enumerate(
            zip_longest(source_reader, prepared_handle, fillvalue=None), start=1
        ):
            source_row, prepared_line = pair
            if source_row is None or prepared_line is None or len(source_row) != 3:
                raise ValueError(f"Source/prepared train alignment failed at row {row_number}")
            source_rows = row_number
            _, encoded_labels, comment_id = source_row
            if comment_id in seen_ids:
                raise ValueError("Official train repeats a comment ID")
            seen_ids.add(comment_id)
            gold_ids = [int(value) for value in encoded_labels.split(",")]
            if (
                not gold_ids
                or len(gold_ids) != len(set(gold_ids))
                or any(value < 0 or value >= len(labels) for value in gold_ids)
            ):
                raise ValueError(f"Invalid official labels at row {row_number}")
            prepared = json.loads(prepared_line)
            messages = prepared.get("messages")
            if (
                not isinstance(messages, list)
                or len(messages) != 3
                or [message.get("role") for message in messages]
                != ["system", "user", "assistant"]
            ):
                raise ValueError(f"Invalid prepared messages at row {row_number}")
            target = json.loads(messages[2]["content"])
            expected_labels = [labels[value] for value in gold_ids]
            if target != {"labels": expected_labels}:
                raise ValueError(f"Prepared target drift at row {row_number}")
            if neutral_id in gold_ids and len(gold_ids) > 1:
                samples.append(
                    {
                        "comment_id_sha256": sha256_text(comment_id),
                        "gold_label_ids": gold_ids,
                        "messages": messages[:2],
                        "source_row_number": row_number,
                    }
                )
                cardinality[len(gold_ids)] += 1
    scope = config["scope"]
    row_hash = sha256_text(
        ",".join(str(sample["source_row_number"]) for sample in samples)
    )
    expected_cardinality = {
        int(key): int(value) for key, value in scope["expected_gold_cardinality"].items()
    }
    if (
        source_rows != int(config["data"]["source_train"]["rows"])
        or len(samples) != int(scope["expected_rows"])
        or row_hash != scope["source_row_numbers_sha256"]
        or dict(cardinality) != expected_cardinality
    ):
        raise ValueError("Frozen training slice membership drift")
    return samples


def strict_parse(output: str, labels: tuple[str, ...]) -> dict[str, Any]:
    try:
        decoded = json.loads(output.strip())
    except json.JSONDecodeError:
        return {"canonical_output": None, "error": "invalid-json", "labels": []}
    if not isinstance(decoded, dict) or set(decoded) != {"labels"}:
        return {"canonical_output": None, "error": "wrong-object", "labels": []}
    values = decoded["labels"]
    if not isinstance(values, list) or not values:
        return {"canonical_output": None, "error": "labels-not-nonempty-list", "labels": []}
    if not all(isinstance(value, str) for value in values):
        return {"canonical_output": None, "error": "non-string-label", "labels": []}
    if len(values) != len(set(values)):
        return {"canonical_output": None, "error": "duplicate-label", "labels": []}
    if any(value not in labels for value in values):
        return {"canonical_output": None, "error": "unknown-label", "labels": []}
    return {
        "canonical_output": json.dumps({"labels": values}, separators=(",", ":")),
        "error": None,
        "labels": values,
    }


def make_record(
    slice_index: int,
    sample: dict[str, Any],
    labels: tuple[str, ...],
    generated: dict[str, Any],
) -> dict[str, Any]:
    raw_output = generated.pop("output")
    parsed = strict_parse(raw_output, labels)
    parser_error = parsed["error"]
    parser_valid = parser_error is None
    if generated["finish_reason"] != "stop":
        parser_valid = False
        parser_error = "length-terminated"
    predicted_labels = parsed["labels"] if parser_valid else []
    label_to_id = {label: index for index, label in enumerate(labels)}
    return {
        "canonical_output": parsed["canonical_output"] if parser_valid else None,
        "comment_id_sha256": sample["comment_id_sha256"],
        "condition": CONDITION,
        "constraint_intervened": generated["constraint_intervened"],
        "finish_reason": generated["finish_reason"],
        "first_blocked_step": generated["first_blocked_step"],
        "first_blocked_token_id": generated["first_blocked_token_id"],
        "generated_tokens": generated["generated_tokens"],
        "generation_seconds": generated["generation_seconds"],
        "generation_tps": generated["generation_tps"],
        "gold_label_ids": sample["gold_label_ids"],
        "gold_labels": [labels[value] for value in sample["gold_label_ids"]],
        "output_character_count": len(raw_output),
        "output_sha256": sha256_text(raw_output),
        "parser_error": parser_error,
        "parser_valid": parser_valid,
        "peak_memory_gb": generated["peak_memory_gb"],
        "predicted_label_ids": [label_to_id[label] for label in predicted_labels],
        "predicted_labels": predicted_labels,
        "prompt_tokens": generated["prompt_tokens"],
        "prompt_tps": generated["prompt_tps"],
        "raw_argmax_blocked_steps": generated["raw_argmax_blocked_steps"],
        "raw_output": raw_output,
        "row_number": slice_index,
        "sequence_logprob_mean": generated["sequence_logprob_mean"],
        "sequence_logprob_sum": generated["sequence_logprob_sum"],
        "sequence_score_space": "open-neutral constrained label-name JSON",
        "source_row_number": sample["source_row_number"],
    }


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def verify_record_prefix(
    records: list[dict[str, Any]], samples: list[dict[str, Any]], labels: tuple[str, ...]
) -> None:
    if len(records) > len(samples):
        raise ValueError("Prediction checkpoint has too many rows")
    label_to_id = {label: index for index, label in enumerate(labels)}
    for index, record in enumerate(records):
        sample = samples[index]
        raw_output = record.get("raw_output")
        if not isinstance(raw_output, str):
            raise ValueError(f"Missing raw output at slice row {index + 1}")
        parsed = strict_parse(raw_output, labels)
        valid = parsed["error"] is None and record.get("finish_reason") == "stop"
        error = parsed["error"] if record.get("finish_reason") == "stop" else "length-terminated"
        predicted_labels = parsed["labels"] if valid else []
        if (
            record.get("row_number") != index + 1
            or record.get("source_row_number") != sample["source_row_number"]
            or record.get("comment_id_sha256") != sample["comment_id_sha256"]
            or record.get("gold_label_ids") != sample["gold_label_ids"]
            or record.get("predicted_labels") != predicted_labels
            or record.get("predicted_label_ids")
            != [label_to_id[label] for label in predicted_labels]
            or record.get("parser_valid") is not valid
            or record.get("parser_error") != error
            or record.get("output_sha256") != sha256_text(raw_output)
            or record.get("condition") != CONDITION
        ):
            raise ValueError(f"Prediction checkpoint drift at slice row {index + 1}")


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return {"commit": commit, "dirty": dirty}


def diagnostic_counts(gold: Any, predicted: Any, labels: tuple[str, ...]) -> dict[str, Any]:
    import numpy as np

    neutral = labels.index("neutral")
    predicted_cardinality = predicted.sum(axis=1)
    gold_cardinality = gold.sum(axis=1)
    structural = predicted[:, neutral].astype(bool) & (predicted_cardinality > 1)
    non_neutral = np.ones(len(labels), dtype=bool)
    non_neutral[neutral] = False
    correct_non_neutral = np.any(
        predicted[:, non_neutral].astype(bool) & gold[:, non_neutral].astype(bool), axis=1
    )
    target_compatible = structural & correct_non_neutral
    return {
        "gold_cardinality_distribution": {
            str(int(key)): int(value)
            for key, value in sorted(Counter(gold_cardinality.tolist()).items())
        },
        "neutral_coprediction_rate": float(structural.mean()),
        "neutral_coprediction_rows": int(structural.sum()),
        "predicted_cardinality_distribution": {
            str(int(key)): int(value)
            for key, value in sorted(Counter(predicted_cardinality.tolist()).items())
        },
        "predicted_label_cardinality": float(predicted_cardinality.mean()),
        "rows": int(gold.shape[0]),
        "target_compatible_coprediction_rate": float(target_compatible.mean()),
        "target_compatible_coprediction_rows": int(target_compatible.sum()),
    }


def write_predictions(path: Path, records: list[dict[str, Any]]) -> None:
    fields = (
        "row_number",
        "source_row_number",
        "comment_id_sha256",
        "gold_label_ids",
        "gold_labels",
        "predicted_label_ids",
        "predicted_labels",
        "parser_valid",
        "parser_error",
        "finish_reason",
        "canonical_output",
        "output_sha256",
        "prompt_tokens",
        "generated_tokens",
        "generation_seconds",
        "peak_memory_gb",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    **{name: record[name] for name in fields if name in record},
                    "gold_label_ids": "|".join(map(str, record["gold_label_ids"])),
                    "gold_labels": "|".join(record["gold_labels"]),
                    "predicted_label_ids": "|".join(map(str, record["predicted_label_ids"])),
                    "predicted_labels": "|".join(record["predicted_labels"]),
                }
            )


def finalize(
    config: dict[str, Any],
    run_dir: Path,
    records: list[dict[str, Any]],
    labels: tuple[str, ...],
) -> dict[str, Any]:
    import numpy as np

    sys.path.insert(0, str(SCRIPT_DIR))
    import llm_full_dev_metrics as metric_tools

    gold = np.zeros((len(records), len(labels)), dtype=np.uint8)
    for index, record in enumerate(records):
        gold[index, record["gold_label_ids"]] = 1
    predicted = metric_tools.records_to_prediction_matrix(records, labels)
    metrics, confusion = metric_tools.compute_metrics(gold, predicted, labels)
    generation = metric_tools.summarize_generation(records)
    diagnostics = diagnostic_counts(gold, predicted, labels)
    validation = load_json(
        resolve_project_path(
            config["comparison"]["validation_neutral_cooccurrence_slice"]["path"]
        )
    )["neutral_cooccurrence"]
    validation_metrics = validation["metrics"]
    comparison = {
        "interpretation_boundary": (
            "Training-slice performance measures memorization only; validation remains the held-out "
            "generalization evidence."
        ),
        "train": {
            "macro_f1": metrics["macro"]["f1"],
            "neutral_coprediction_rate": diagnostics["neutral_coprediction_rate"],
            "neutral_coprediction_rows": diagnostics["neutral_coprediction_rows"],
            "predicted_label_cardinality": diagnostics["predicted_label_cardinality"],
            "rows": len(records),
            "samples_f1": metrics["samples"]["f1"],
            "subset_accuracy": metrics["subset_accuracy"],
        },
        "validation": {
            "macro_f1": validation_metrics["macro"]["f1"],
            "neutral_coprediction_rate": (
                validation_metrics["prediction_diagnostics"]["neutral_coprediction_rows"]
                / validation["row_count"]
            ),
            "neutral_coprediction_rows": validation_metrics["prediction_diagnostics"][
                "neutral_coprediction_rows"
            ],
            "predicted_label_cardinality": validation_metrics["label_cardinality"][
                "predicted_mean"
            ],
            "rows": validation["row_count"],
            "samples_f1": validation_metrics["samples"]["f1"],
            "subset_accuracy": validation_metrics["subset_accuracy"],
        },
    }
    metric_tools.write_json(run_dir / "metrics.json", {"generation": generation, "task": metrics})
    metric_tools.write_per_label(run_dir / "per-label-metrics.csv", metrics, labels)
    metric_tools.write_confusion(run_dir / "multilabel-confusion-matrix.csv", confusion, labels)
    write_predictions(run_dir / "predictions.csv", records)
    write_json(run_dir / "diagnostics.json", diagnostics)
    write_json(run_dir / "comparison.json", comparison)
    return {"comparison": comparison, "diagnostics": diagnostics, "task": metrics}


def run(config: dict[str, Any], config_path: Path, config_sha256: str, resume: bool) -> None:
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler

    sys.path.insert(0, str(SCRIPT_DIR))
    from label_json_constraint_neutral_cooccurrence import NeutralCooccurrenceLogitsProcessor
    import run_lora as generation_helper

    run_dir = resolve_project_path(config["outputs"]["run_dir"])
    run_path = run_dir / "run.json"
    records_path = run_dir / "predictions.jsonl"
    log_path = run_dir / "stdout.log"
    if resume:
        if not run_path.is_file() or not records_path.is_file():
            raise FileNotFoundError("EXP-034 resume requires an existing partial run")
        run_record = load_json(run_path)
        if run_record.get("status") not in {"Interrupted", "Failed"}:
            raise ValueError("Only an interrupted or failed EXP-034 run may resume")
    else:
        if run_dir.exists():
            raise FileExistsError(f"EXP-034 output already exists: {run_dir}")
        run_dir.mkdir(parents=True)
        run_record = {
            "command": sys.argv,
            "config": artifact(config_path),
            "experiment_id": EXPERIMENT_ID,
            "git": git_metadata(),
            "parent_experiment": "EXP-033",
            "seed": 42,
            "split": "train-neutral-cooccurrence-only",
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "Running",
            "test_split_accessed": False,
            "tier": "Minor",
        }
        write_json(run_path, run_record)
    labels = tuple(
        resolve_project_path(config["data"]["labels"]["path"])
        .read_text(encoding="utf-8")
        .splitlines()
    )
    samples = load_training_slice(config, labels)
    records = read_records(records_path) if resume else []
    verify_record_prefix(records, samples, labels)
    time_limit = float(config["resource_budget"]["active_wall_time_hours_max"]) * 3600
    prior_seconds = float(run_record.get("active_duration_seconds", 0.0))
    started = time.perf_counter()
    try:
        model_dir = resolve_project_path(config["model"]["local_path"])
        adapter_dir = resolve_project_path(config["adapter"]["weights"]["path"]).parent
        mx.reset_peak_memory()
        model, tokenizer = load(str(model_dir), adapter_path=str(adapter_dir), lazy=False)
        constraint = generation_helper.TelemetryConstraint(
            NeutralCooccurrenceLogitsProcessor(tokenizer, labels, mx), mx
        )
        mode = "a" if resume else "x"
        with records_path.open(mode, encoding="utf-8") as output, log_path.open(
            "a", encoding="utf-8"
        ) as log:
            log.write(f"Starting {EXPERIMENT_ID}; completed prefix={len(records)}\n")
            log.flush()
            for index in range(len(records), len(samples)):
                if prior_seconds + time.perf_counter() - started > time_limit:
                    raise TimeoutError("EXP-034 exceeded its one-hour active-time budget")
                prompt = tokenizer.apply_chat_template(
                    samples[index]["messages"],
                    add_generation_prompt=True,
                    enable_thinking=False,
                    tokenize=False,
                )
                generated = generation_helper.generate_one(
                    model,
                    tokenizer,
                    prompt,
                    int(config["decoding"]["max_new_tokens"]),
                    constraint,
                    mx,
                    stream_generate,
                    make_sampler,
                )
                if float(generated["peak_memory_gb"]) > float(
                    config["resource_budget"]["peak_mlx_memory_gb_max"]
                ):
                    raise MemoryError("EXP-034 exceeded its peak-memory budget")
                record = make_record(index + 1, samples[index], labels, generated)
                output.write(json.dumps(record, sort_keys=True) + "\n")
                output.flush()
                records.append(record)
                if (index + 1) % 50 == 0 or index + 1 == len(samples):
                    os.fsync(output.fileno())
                if (index + 1) % 100 == 0 or index + 1 == len(samples):
                    elapsed = prior_seconds + time.perf_counter() - started
                    run_record["active_duration_seconds"] = elapsed
                    run_record["progress"] = {"completed": index + 1, "total": len(samples)}
                    write_json(run_path, run_record)
                    log.write(f"Train slice {index + 1}/{len(samples)}; elapsed={elapsed / 60:.1f} min\n")
                    log.flush()
        verify_record_prefix(records, samples, labels)
        if len(records) != len(samples):
            raise ValueError("EXP-034 prediction set is incomplete")
        summary = finalize(config, run_dir, records, labels)
        duration = prior_seconds + time.perf_counter() - started
        peak_memory = max(float(record["peak_memory_gb"]) for record in records)
        run_record.update(
            {
                "active_duration_seconds": duration,
                "artifacts": {
                    name: artifact(run_dir / name)
                    for name in (
                        "comparison.json",
                        "diagnostics.json",
                        "metrics.json",
                        "multilabel-confusion-matrix.csv",
                        "per-label-metrics.csv",
                        "predictions.csv",
                        "predictions.jsonl",
                        "stdout.log",
                    )
                },
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "peak_mlx_memory_gb": peak_memory,
                "progress": {"completed": len(samples), "total": len(samples)},
                "result_summary": summary,
                "status": "Completed; pending independent verification",
            }
        )
        write_json(run_path, run_record)
    except BaseException as error:
        run_record.update(
            {
                "active_duration_seconds": prior_seconds + time.perf_counter() - started,
                "error": {"message": str(error), "traceback": traceback.format_exc()},
                "status": "Interrupted" if isinstance(error, KeyboardInterrupt) else "Failed",
            }
        )
        write_json(run_path, run_record)
        raise


def main() -> None:
    args = parse_args()
    config = validate_config(args.config, args.config_sha256)
    observed = verify_static_inputs(config)
    labels = tuple(
        resolve_project_path(config["data"]["labels"]["path"])
        .read_text(encoding="utf-8")
        .splitlines()
    )
    samples = load_training_slice(config, labels)
    if args.preflight:
        print(
            json.dumps(
                {
                    "config_sha256": args.config_sha256,
                    "implementation_verified": sorted(config["implementation"]),
                    "model_inventory": observed["model_inventory"],
                    "slice_rows": len(samples),
                    "source_row_numbers_sha256": config["scope"][
                        "source_row_numbers_sha256"
                    ],
                    "status": "Passed",
                    "test_split_absent": True,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    run(config, args.config.resolve(), args.config_sha256, args.resume)


if __name__ == "__main__":
    main()
