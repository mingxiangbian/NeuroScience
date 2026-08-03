#!/usr/bin/env python3
"""Run the frozen EXP-022 local resource and strict-parser trial."""

from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import logging
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
import traceback
from typing import Any

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["PYTHONNOUSERSITE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import mlx.core as mx
from mlx_lm import load, stream_generate
from mlx_lm.sample_utils import make_sampler


EXPERIMENT_ID = "EXP-022"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
CONFIG_PATH = SCRIPT_DIR / "configs" / "exp-022-resource-parser-trial.json"
PROMPT_PATH = SCRIPT_DIR / "prompts" / "exp-022-resource-v1.json"
RUN_DIR = SCRIPT_DIR / "runs" / "exp-022-resource-parser-trial"
DATA_ROOT = PROJECT_ROOT / "data" / "goemotions" / "official"
TRAIN_PATH = DATA_ROOT / "train.tsv"
LABELS_PATH = DATA_ROOT / "emotions.txt"
TEST_PATH = DATA_ROOT / "test.tsv"
MODEL_ROOT = PROJECT_ROOT / "models" / "qwen3-1.7b"
MODEL_DIR = MODEL_ROOT / "mlx-bf16"
MODEL_MANIFEST_PATH = MODEL_ROOT / "manifest.json"

EXPECTED_CONFIG_SHA256 = (
    "58fce1005e1dc8a61fcb122ea4748df1ecf9d0916d29dd3557ced2bfbfb0e10e"
)
EXPECTED_PROMPT_SHA256 = (
    "2ce7083d41df7ff15292b4211bba26e5403d9cd66c67f8f12f9386cb99bf328c"
)
EXPECTED_TRAIN_SHA256 = (
    "1c254a142be5c00e80d819b9ae1bbd36d94b2eeb8f4b1271846508d57e57d9c5"
)
EXPECTED_LABELS_SHA256 = (
    "45c3ef86782d2a4d7fedcd6d8c111aa0d0e94720689bd164fac94fefb4495a89"
)
EXPECTED_MODEL_MANIFEST_SHA256 = (
    "7c1e0e53e6340d5ce33c366569a07763be41546045017870cc149a8f50d1e877"
)
EXPECTED_MODEL_REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
SELECTION_SALT = "EXP-022-selection-v1:"
EXPECTED_LABELS = (
    "admiration",
    "amusement",
    "anger",
    "annoyance",
    "approval",
    "caring",
    "confusion",
    "curiosity",
    "desire",
    "disappointment",
    "disapproval",
    "disgust",
    "embarrassment",
    "excitement",
    "fear",
    "gratitude",
    "grief",
    "joy",
    "love",
    "nervousness",
    "optimism",
    "pride",
    "realization",
    "relief",
    "remorse",
    "sadness",
    "surprise",
    "neutral",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def project_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def prepare_run_dir() -> None:
    if RUN_DIR.exists() and any(RUN_DIR.iterdir()):
        raise FileExistsError(f"Append-only run directory is not empty: {RUN_DIR}")
    RUN_DIR.mkdir(parents=True, exist_ok=True)


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("exp-022")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s")
    formatter.converter = time.gmtime

    file_handler = logging.FileHandler(RUN_DIR / "stdout.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
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
        "commit": commit,
        "dirty": bool(status),
        "dirty_path_count": len(status),
    }


def hardware_metadata() -> dict[str, Any]:
    memory_bytes = int(
        subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    chip = subprocess.run(
        ["sysctl", "-n", "machdep.cpu.brand_string"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {
        "architecture": platform.machine(),
        "chip": chip,
        "memory_bytes": memory_bytes,
        "platform": platform.platform(),
    }


def package_versions() -> dict[str, str]:
    return {
        name: importlib.metadata.version(name)
        for name in (
            "huggingface-hub",
            "mlx",
            "mlx-lm",
            "numpy",
            "transformers",
        )
    }


def load_frozen_inputs() -> tuple[dict[str, Any], dict[str, Any], tuple[str, ...]]:
    expected_hashes = {
        CONFIG_PATH: EXPECTED_CONFIG_SHA256,
        PROMPT_PATH: EXPECTED_PROMPT_SHA256,
        TRAIN_PATH: EXPECTED_TRAIN_SHA256,
        LABELS_PATH: EXPECTED_LABELS_SHA256,
        MODEL_MANIFEST_PATH: EXPECTED_MODEL_MANIFEST_SHA256,
    }
    for path, expected in expected_hashes.items():
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(f"Frozen hash mismatch for {path}: {actual} != {expected}")
    if TEST_PATH.exists():
        raise ValueError(f"Test split must remain absent: {TEST_PATH}")

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    prompt_spec = json.loads(PROMPT_PATH.read_text(encoding="utf-8"))
    labels = tuple(LABELS_PATH.read_text(encoding="utf-8").splitlines())
    if labels != EXPECTED_LABELS:
        raise ValueError("GoEmotions label order changed")
    if config["experiment_id"] != EXPERIMENT_ID:
        raise ValueError("Config experiment ID mismatch")

    manifest = json.loads(MODEL_MANIFEST_PATH.read_text(encoding="utf-8"))
    if (
        manifest["repo_id"] != config["model"]["repo_id"]
        or manifest["revision"] != EXPECTED_MODEL_REVISION
        or manifest["conversion"]["dtype"] != "bfloat16"
        or manifest["conversion"]["quantized"] is not False
    ):
        raise ValueError("Model manifest differs from frozen EXP-022 condition")
    if not MODEL_DIR.is_dir() or not any(MODEL_DIR.glob("*.safetensors")):
        raise FileNotFoundError(f"Missing local MLX model: {MODEL_DIR}")
    return config, prompt_spec, labels


def select_samples(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    expected_rows = config["data"]["expected_train_rows"]
    rows: list[dict[str, Any]] = []
    with TRAIN_PATH.open("r", encoding="utf-8", newline="") as source:
        reader = csv.reader(source, delimiter="\t")
        for row_number, row in enumerate(reader, start=1):
            if len(row) != 3:
                raise ValueError(f"train.tsv row {row_number} has {len(row)} columns")
            text, _discarded_gold_labels, comment_id = row
            if not text or not comment_id:
                raise ValueError(f"train.tsv row {row_number} has empty text or ID")
            rows.append(
                {
                    "comment_id": comment_id,
                    "id_hash": sha256_text(comment_id),
                    "row_number": row_number,
                    "selector_hash": sha256_text(SELECTION_SALT + comment_id),
                    "text": text,
                    "text_character_count": len(text),
                }
            )
    if len(rows) != expected_rows:
        raise ValueError(f"train.tsv has {len(rows)} rows; expected {expected_rows}")

    ranked = sorted(
        rows,
        key=lambda row: (
            row["text_character_count"],
            row["id_hash"],
            row["row_number"],
        ),
    )
    strata: list[list[dict[str, Any]]] = [[] for _ in range(4)]
    for rank, row in enumerate(ranked):
        stratum = min(3, (rank * 4) // expected_rows)
        row["length_stratum"] = stratum
        strata[stratum].append(row)

    selected: list[dict[str, Any]] = []
    per_stratum = config["data"]["selection"]["per_stratum"]
    for stratum_rows in strata:
        selected.extend(
            sorted(
                stratum_rows,
                key=lambda row: (row["selector_hash"], row["row_number"]),
            )[:per_stratum]
        )
    selected.sort(
        key=lambda row: (
            row["length_stratum"],
            row["selector_hash"],
            row["row_number"],
        )
    )
    if len(selected) != config["data"]["sample_count"]:
        raise ValueError("Deterministic sample count mismatch")
    for sample_index, row in enumerate(selected):
        row["sample_index"] = sample_index

    selection_material = "\n".join(
        f"{row['row_number']}:{row['comment_id']}" for row in selected
    )
    public_record = {
        "data_rows_scanned": len(rows),
        "gold_labels_retained_or_used": False,
        "raw_comment_ids_stored": False,
        "raw_text_stored": False,
        "sample_count": len(selected),
        "samples": [
            {
                "length_stratum": row["length_stratum"],
                "sample_index": row["sample_index"],
                "text_character_count": row["text_character_count"],
            }
            for row in selected
        ],
        "selection_digest_sha256": sha256_text(selection_material),
        "strata": [
            {
                "length_max": max(row["text_character_count"] for row in values),
                "length_min": min(row["text_character_count"] for row in values),
                "population": len(values),
                "selected": per_stratum,
                "stratum": index,
            }
            for index, values in enumerate(strata)
        ],
    }
    return selected, public_record


def build_prompt(
    tokenizer: Any,
    prompt_spec: dict[str, Any],
    labels: tuple[str, ...],
    text: str,
    condition: str,
) -> str:
    system = prompt_spec["system_template"].format(
        allowed_labels=", ".join(labels)
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    if condition == "few-shot-synthetic-3":
        for example in prompt_spec["few_shot_examples"]:
            messages.extend(
                [
                    {"role": "user", "content": example["user"]},
                    {"role": "assistant", "content": example["assistant"]},
                ]
            )
    elif condition != "zero-shot":
        raise ValueError(f"Unknown condition: {condition}")
    messages.append(
        {
            "role": "user",
            "content": prompt_spec["user_template"].format(text=text),
        }
    )
    return tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        enable_thinking=False,
        tokenize=False,
    )


def strict_parse(output: str, labels: tuple[str, ...]) -> dict[str, Any]:
    try:
        decoded = json.loads(output.strip())
    except json.JSONDecodeError:
        return {"canonical_output": None, "error": "invalid-json", "labels": []}
    if not isinstance(decoded, dict):
        return {"canonical_output": None, "error": "not-object", "labels": []}
    if set(decoded) != {"labels"}:
        return {"canonical_output": None, "error": "wrong-keys", "labels": []}
    values = decoded["labels"]
    if not isinstance(values, list) or not values:
        return {"canonical_output": None, "error": "labels-not-nonempty-list", "labels": []}
    if not all(isinstance(value, str) for value in values):
        return {"canonical_output": None, "error": "non-string-label", "labels": []}
    if len(values) != len(set(values)):
        return {"canonical_output": None, "error": "duplicate-label", "labels": []}
    if any(value not in labels for value in values):
        return {"canonical_output": None, "error": "unknown-label", "labels": []}
    if "neutral" in values and len(values) > 1:
        return {"canonical_output": None, "error": "neutral-combined", "labels": []}
    canonical = json.dumps({"labels": values}, separators=(",", ":"))
    return {"canonical_output": canonical, "error": None, "labels": values}


def generate_one(
    model: Any,
    tokenizer: Any,
    prompt: str,
    max_tokens: int,
) -> dict[str, Any]:
    mx.reset_peak_memory()
    started = time.perf_counter()
    output_parts: list[str] = []
    last_response = None
    for response in stream_generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
        sampler=make_sampler(temp=0.0),
    ):
        output_parts.append(response.text)
        last_response = response
    elapsed = time.perf_counter() - started
    if last_response is None:
        raise RuntimeError("MLX-LM yielded no generation response")
    output = "".join(output_parts)
    if not output.strip():
        raise RuntimeError("MLX-LM generated an empty output")
    numeric_values = (
        last_response.prompt_tps,
        last_response.generation_tps,
        last_response.peak_memory,
        elapsed,
    )
    if not all(math.isfinite(float(value)) for value in numeric_values):
        raise ValueError("Generation returned a non-finite resource measurement")
    return {
        "finish_reason": last_response.finish_reason,
        "generated_tokens": int(last_response.generation_tokens),
        "generation_seconds": elapsed,
        "generation_tps": float(last_response.generation_tps),
        "output": output,
        "peak_memory_gb": float(last_response.peak_memory),
        "prompt_tokens": int(last_response.prompt_tokens),
        "prompt_tps": float(last_response.prompt_tps),
    }


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def summarize_condition(
    rows: list[dict[str, Any]],
    full_dev_rows: int,
) -> dict[str, Any]:
    latencies = [float(row["generation_seconds"]) for row in rows]
    prompt_tokens = [float(row["prompt_tokens"]) for row in rows]
    generated_tokens = [float(row["generated_tokens"]) for row in rows]
    prompt_tps = [float(row["prompt_tps"]) for row in rows]
    generation_tps = [float(row["generation_tps"]) for row in rows]
    valid_count = sum(bool(row["parser_valid"]) for row in rows)
    return {
        "estimated_full_dev_hours": statistics.mean(latencies)
        * full_dev_rows
        / 3600,
        "finish_reasons": dict(sorted(Counter(row["finish_reason"] for row in rows).items())),
        "generated_tokens": {
            "mean": statistics.mean(generated_tokens),
            "p95": percentile(generated_tokens, 0.95),
            "total": int(sum(generated_tokens)),
        },
        "generation_seconds": {
            "mean": statistics.mean(latencies),
            "median": statistics.median(latencies),
            "p95": percentile(latencies, 0.95),
            "total": sum(latencies),
        },
        "generation_tps": {
            "mean": statistics.mean(generation_tps),
            "median": statistics.median(generation_tps),
        },
        "length_terminated": sum(row["finish_reason"] == "length" for row in rows),
        "parser_errors": dict(
            sorted(Counter(row["parser_error"] for row in rows if row["parser_error"]).items())
        ),
        "parser_valid_count": valid_count,
        "parser_valid_rate": valid_count / len(rows),
        "peak_memory_gb_max": max(float(row["peak_memory_gb"]) for row in rows),
        "prompt_tokens": {
            "mean": statistics.mean(prompt_tokens),
            "p95": percentile(prompt_tokens, 0.95),
            "total": int(sum(prompt_tokens)),
        },
        "prompt_tps": {
            "mean": statistics.mean(prompt_tps),
            "median": statistics.median(prompt_tps),
        },
        "sample_count": len(rows),
    }


def main() -> None:
    prepare_run_dir()
    logger = setup_logger()
    started_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    run: dict[str, Any] = {
        "accessed_splits": [],
        "errors": [],
        "experiment_id": EXPERIMENT_ID,
        "parent_experiment": "EXP-021",
        "rq_id": "RQ-G2 implementation gate",
        "stage": "small-sample-throughput-and-parser-budget",
        "started_at_utc": started_at.isoformat(),
        "status": "In Progress",
        "test_split_accessed": False,
        "tier": "Minor",
        "validation_split_accessed": False,
        "warnings": [
            "This run measures engineering cost and parser behavior, not classification performance.",
            "Gold labels are discarded and no Accuracy or F1 metric is computed.",
            "Full-dev hours are linear estimates for unbatched generation without prompt caching.",
        ],
    }

    try:
        logger.info("Starting %s", EXPERIMENT_ID)
        config, prompt_spec, labels = load_frozen_inputs()
        run["accessed_splits"] = ["train"]
        selected, selected_public = select_samples(config)
        selected_path = RUN_DIR / "selected-samples.json"
        write_json(selected_path, selected_public)
        logger.info(
            "Selected %d anonymous train samples across four length strata",
            len(selected),
        )

        mx.reset_peak_memory()
        load_started = time.perf_counter()
        model, tokenizer = load(str(MODEL_DIR), lazy=False)
        model_load_seconds = time.perf_counter() - load_started
        model_load_peak_gb = mx.get_peak_memory() / 1e9
        model_active_memory_gb = mx.get_active_memory() / 1e9
        logger.info(
            "Loaded model in %.3fs; active MLX memory %.3f GB",
            model_load_seconds,
            model_active_memory_gb,
        )

        max_tokens = config["decoding"]["max_new_tokens"]
        warmup_text = "The local generation pipeline is ready for a timing check."
        for condition in ("zero-shot", "few-shot-synthetic-3"):
            prompt = build_prompt(tokenizer, prompt_spec, labels, warmup_text, condition)
            generate_one(model, tokenizer, prompt, max_tokens)
        logger.info("Completed two synthetic warm-up generations")

        results_path = RUN_DIR / "sample-results.jsonl"
        results: list[dict[str, Any]] = []
        with results_path.open("x", encoding="utf-8") as sink:
            for selected_row in selected:
                condition_order = ["zero-shot", "few-shot-synthetic-3"]
                if selected_row["sample_index"] % 2:
                    condition_order.reverse()
                for condition in condition_order:
                    if time.perf_counter() - started > (
                        config["resource_budget"]["wall_time_minutes_max"] * 60
                    ):
                        raise TimeoutError("EXP-022 exceeded its frozen wall-time budget")
                    prompt = build_prompt(
                        tokenizer,
                        prompt_spec,
                        labels,
                        selected_row["text"],
                        condition,
                    )
                    measured = generate_one(model, tokenizer, prompt, max_tokens)
                    raw_output = measured.pop("output")
                    parsed = strict_parse(raw_output, labels)
                    # The actual unrestricted output is intentionally not persisted.
                    record = {
                        "canonical_output": parsed["canonical_output"],
                        "condition": condition,
                        "finish_reason": measured["finish_reason"],
                        "generated_tokens": measured["generated_tokens"],
                        "generation_seconds": measured["generation_seconds"],
                        "generation_tps": measured["generation_tps"],
                        "length_stratum": selected_row["length_stratum"],
                        "output_character_count": len(raw_output),
                        "output_sha256": sha256_text(raw_output),
                        "parser_error": parsed["error"],
                        "parser_valid": parsed["error"] is None,
                        "parsed_labels": parsed["labels"],
                        "peak_memory_gb": measured["peak_memory_gb"],
                        "prompt_tokens": measured["prompt_tokens"],
                        "prompt_tps": measured["prompt_tps"],
                        "raw_output_stored": False,
                        "sample_index": selected_row["sample_index"],
                        "text_character_count": selected_row["text_character_count"],
                    }
                    results.append(record)
                    sink.write(json.dumps(record, sort_keys=True) + "\n")
                    sink.flush()
                if (selected_row["sample_index"] + 1) % 8 == 0:
                    logger.info(
                        "Completed %d/%d anonymous samples",
                        selected_row["sample_index"] + 1,
                        len(selected),
                    )

        expected_generations = config["resource_budget"]["measured_generations"]
        if len(results) != expected_generations:
            raise ValueError(f"Measured {len(results)} generations; expected {expected_generations}")

        condition_summaries = {
            condition: summarize_condition(
                [row for row in results if row["condition"] == condition],
                full_dev_rows=5426,
            )
            for condition in ("zero-shot", "few-shot-synthetic-3")
        }
        total_seconds = time.perf_counter() - started
        peak_memory_gb = max(
            [model_load_peak_gb]
            + [summary["peak_memory_gb_max"] for summary in condition_summaries.values()]
        )
        gate_rules = config["success_gate"]
        budget = config["resource_budget"]
        gate_checks = {
            "full_dev_estimate_within_budget": all(
                summary["estimated_full_dev_hours"]
                <= budget["full_dev_estimate_hours_per_condition_max"]
                for summary in condition_summaries.values()
            ),
            "generation_failures_within_budget": True,
            "length_termination_within_budget": all(
                summary["length_terminated"]
                <= gate_rules["length_terminated_max_per_condition"]
                for summary in condition_summaries.values()
            ),
            "peak_memory_within_budget": peak_memory_gb
            <= budget["peak_mlx_memory_gb_max"],
            "strict_parser_rate_within_budget": all(
                summary["parser_valid_rate"]
                >= gate_rules["strict_parser_valid_rate_min_per_condition"]
                for summary in condition_summaries.values()
            ),
            "wall_time_within_budget": total_seconds
            <= budget["wall_time_minutes_max"] * 60,
        }
        gate_status = "Passed" if all(gate_checks.values()) else "Failed"
        summary = {
            "api_cost_usd": 0,
            "conditions": condition_summaries,
            "full_dev_rows_for_linear_estimate": 5426,
            "gate_checks": gate_checks,
            "gate_status": gate_status,
            "generation_failures": 0,
            "gold_labels_retained_or_used": False,
            "measured_generations": len(results),
            "model_active_memory_after_load_gb": model_active_memory_gb,
            "model_load_peak_memory_gb": model_load_peak_gb,
            "model_load_seconds": model_load_seconds,
            "overall_peak_memory_gb": peak_memory_gb,
            "raw_generation_text_stored": False,
            "total_seconds": total_seconds,
            "warmup_generations": 2,
        }
        summary_path = RUN_DIR / "summary.json"
        write_json(summary_path, summary)

        run.update(
            {
                "artifacts": {
                    "config": {
                        "path": project_path(CONFIG_PATH),
                        "sha256": sha256_file(CONFIG_PATH),
                    },
                    "prompt": {
                        "path": project_path(PROMPT_PATH),
                        "sha256": sha256_file(PROMPT_PATH),
                    },
                    "sample_results": {
                        "path": project_path(results_path),
                        "sha256": sha256_file(results_path),
                    },
                    "selected_samples": {
                        "path": project_path(selected_path),
                        "sha256": sha256_file(selected_path),
                    },
                    "summary": {
                        "path": project_path(summary_path),
                        "sha256": sha256_file(summary_path),
                    },
                },
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "data_rows_scanned": 43410,
                    "dataset_protocol": "DATA-GOE-V1",
                    "dev_rows_accessed": 0,
                    "gold_labels_retained_or_used": False,
                    "measured_sample_count": 32,
                    "split": "train",
                    "test_rows_accessed": 0,
                    "train_sha256": sha256_file(TRAIN_PATH),
                },
                "gate_status": gate_status,
                "invocation": [sys.executable, *sys.argv],
                "model": {
                    "condition": "post-trained",
                    "local_path": project_path(MODEL_DIR),
                    "manifest_path": project_path(MODEL_MANIFEST_PATH),
                    "manifest_sha256": sha256_file(MODEL_MANIFEST_PATH),
                    "precision": "bfloat16",
                    "quantized": False,
                    "repo_id": "Qwen/Qwen3-1.7B",
                    "revision": EXPECTED_MODEL_REVISION,
                },
                "resource_usage": summary,
                "runtime": {
                    "environment": "emotion-llm-mlx",
                    "executable": sys.executable,
                    "git": git_metadata(),
                    "hardware": hardware_metadata(),
                    "packages": package_versions(),
                    "python": platform.python_version(),
                    "user_site_disabled": bool(sys.flags.no_user_site),
                },
                "status": "Completed",
            }
        )
        logger.info("Completed %s with gate status %s", EXPERIMENT_ID, gate_status)
    except Exception as error:
        run["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        run["errors"].append(
            {
                "message": str(error),
                "traceback": traceback.format_exc(),
                "type": type(error).__name__,
            }
        )
        run["status"] = "Rejected"
        logger.exception("%s failed", EXPERIMENT_ID)
        raise
    finally:
        write_json(RUN_DIR / "run.json", run)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "gate_status": run["gate_status"],
                "status": run["status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
