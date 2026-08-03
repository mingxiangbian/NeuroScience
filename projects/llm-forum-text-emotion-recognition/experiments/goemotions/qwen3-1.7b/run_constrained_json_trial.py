#!/usr/bin/env python3
"""Run the frozen EXP-024 constrained label-JSON repair trial."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import platform
import sys
import time
import traceback
from typing import Any

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["PYTHONNOUSERSITE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import run_resource_parser_trial as exp022
from label_json_constraint import LabelJsonLogitsProcessor


EXPERIMENT_ID = "EXP-024"
PROJECT_ROOT = SCRIPT_DIR.parents[2]
CONFIG_PATH = SCRIPT_DIR / "configs" / "exp-024-constrained-json-trial.json"
PROMPT_PATH = SCRIPT_DIR / "prompts" / "exp-022-resource-v1.json"
CONSTRAINT_PATH = SCRIPT_DIR / "label_json_constraint.py"
RUN_DIR = SCRIPT_DIR / "runs" / "exp-024-constrained-json-trial"
RUNNER_PATH = Path(__file__).resolve()
PARENT_RUNNER_PATH = SCRIPT_DIR / "run_resource_parser_trial.py"
PARENT_SELECTED_PATH = (
    SCRIPT_DIR
    / "runs"
    / "exp-022-resource-parser-trial"
    / "selected-samples.json"
)
TRAIN_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "train.tsv"
LABELS_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "emotions.txt"
TEST_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "test.tsv"
MODEL_ROOT = PROJECT_ROOT / "models" / "qwen3-1.7b"
MODEL_DIR = MODEL_ROOT / "mlx-bf16"
MODEL_MANIFEST_PATH = MODEL_ROOT / "manifest.json"

EXPECTED_CONFIG_SHA256 = (
    "b16d3cda88d06e4bc89f8201471118be797f1ef668ad0df06f322a6c49e64494"
)
EXPECTED_PROMPT_SHA256 = (
    "2ce7083d41df7ff15292b4211bba26e5403d9cd66c67f8f12f9386cb99bf328c"
)
EXPECTED_CONSTRAINT_SHA256 = (
    "6e4d1d21d79d2fed3c8a5d118748591db6e72cfcfefb74386f913fb5fd164efa"
)
EXPECTED_PARENT_RUNNER_SHA256 = (
    "d2051f5c621190117cb5c874e5d8c3a128aee262a1a070b038c5254d90b40e5e"
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
EXPECTED_SELECTION_DIGEST = (
    "7dcdbe002627948d6e1c5ed4eceb950085585ad0c726333ba3012515dbd8c525"
)
EXPECTED_LABELS = exp022.EXPECTED_LABELS
CONDITIONS = ("zero-shot", "few-shot-synthetic-3")


def prepare_run_dir() -> None:
    if RUN_DIR.exists() and any(RUN_DIR.iterdir()):
        raise FileExistsError(f"Append-only run directory is not empty: {RUN_DIR}")
    RUN_DIR.mkdir(parents=True, exist_ok=True)


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("exp-024")
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


def load_frozen_inputs() -> tuple[dict[str, Any], dict[str, Any], tuple[str, ...]]:
    expected_hashes = {
        CONFIG_PATH: EXPECTED_CONFIG_SHA256,
        PROMPT_PATH: EXPECTED_PROMPT_SHA256,
        CONSTRAINT_PATH: EXPECTED_CONSTRAINT_SHA256,
        PARENT_RUNNER_PATH: EXPECTED_PARENT_RUNNER_SHA256,
        TRAIN_PATH: EXPECTED_TRAIN_SHA256,
        LABELS_PATH: EXPECTED_LABELS_SHA256,
        MODEL_MANIFEST_PATH: EXPECTED_MODEL_MANIFEST_SHA256,
    }
    for path, expected in expected_hashes.items():
        actual = exp022.sha256_file(path)
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
    if config["parent_experiment"] != "EXP-022":
        raise ValueError("Parent experiment mismatch")
    if config["data"]["expected_selection_digest_sha256"] != EXPECTED_SELECTION_DIGEST:
        raise ValueError("Frozen selection digest changed")
    if prompt_spec["prompt_id"] != "EXP-022-resource-v1":
        raise ValueError("EXP-022 prompt identity changed")

    manifest = json.loads(MODEL_MANIFEST_PATH.read_text(encoding="utf-8"))
    if (
        manifest["repo_id"] != config["model"]["repo_id"]
        or manifest["revision"] != EXPECTED_MODEL_REVISION
        or manifest["conversion"]["dtype"] != "bfloat16"
        or manifest["conversion"]["quantized"] is not False
    ):
        raise ValueError("Model manifest differs from the frozen EXP-024 condition")
    if not MODEL_DIR.is_dir() or not any(MODEL_DIR.glob("*.safetensors")):
        raise FileNotFoundError(f"Missing local MLX model: {MODEL_DIR}")
    return config, prompt_spec, labels


def generate_one(
    model: Any,
    tokenizer: Any,
    prompt: str,
    max_tokens: int,
    processor: LabelJsonLogitsProcessor,
) -> dict[str, Any]:
    processor.reset()
    exp022.mx.reset_peak_memory()
    started = time.perf_counter()
    output_parts: list[str] = []
    last_response = None
    for response in exp022.stream_generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
        sampler=exp022.make_sampler(temp=0.0),
        logits_processors=[processor],
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


def main() -> None:
    prepare_run_dir()
    logger = setup_logger()
    started_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    run: dict[str, Any] = {
        "accessed_splits": [],
        "errors": [],
        "experiment_id": EXPERIMENT_ID,
        "parent_experiment": "EXP-022",
        "rq_id": "RQ-G2 implementation gate",
        "stage": "constrained-label-json-repair-trial",
        "started_at_utc": started_at.isoformat(),
        "status": "In Progress",
        "test_split_accessed": False,
        "tier": "Minor",
        "validation_split_accessed": False,
        "warnings": [
            "This run measures engineering cost and parser behavior, not classification performance.",
            "Gold labels are discarded and no Accuracy or F1 metric is computed.",
            "Strict format validity under constrained decoding is not evidence of instruction-following ability.",
            "The decoder masks invalid continuations but does not map synonyms or repair completed outputs.",
            "Full-dev hours are linear estimates for unbatched generation without prompt caching.",
        ],
    }

    try:
        logger.info("Starting %s", EXPERIMENT_ID)
        config, prompt_spec, labels = load_frozen_inputs()
        run["accessed_splits"] = ["train"]
        selected, selected_public = exp022.select_samples(config)
        if selected_public["selection_digest_sha256"] != EXPECTED_SELECTION_DIGEST:
            raise ValueError("EXP-024 did not reconstruct the frozen EXP-022 sample")
        parent_selected = json.loads(PARENT_SELECTED_PATH.read_text(encoding="utf-8"))
        if selected_public != parent_selected:
            raise ValueError("EXP-024 selected-sample metadata differs from EXP-022")
        selected_path = RUN_DIR / "selected-samples.json"
        exp022.write_json(selected_path, selected_public)
        logger.info(
            "Reconstructed %d anonymous EXP-022 train samples",
            len(selected),
        )

        exp022.mx.reset_peak_memory()
        load_started = time.perf_counter()
        model, tokenizer = exp022.load(str(MODEL_DIR), lazy=False)
        model_load_seconds = time.perf_counter() - load_started
        model_load_peak_gb = exp022.mx.get_peak_memory() / 1e9
        model_active_memory_gb = exp022.mx.get_active_memory() / 1e9

        constraint_started = time.perf_counter()
        processor = LabelJsonLogitsProcessor(tokenizer, labels, exp022.mx)
        constraint_init_seconds = time.perf_counter() - constraint_started
        logger.info(
            "Loaded model in %.3fs and initialized %d constrained tokens in %.3fs",
            model_load_seconds,
            processor.candidate_token_count,
            constraint_init_seconds,
        )

        max_tokens = config["decoding"]["max_new_tokens"]
        warmup_text = "The local generation pipeline is ready for a timing check."
        for condition in CONDITIONS:
            prompt = exp022.build_prompt(
                tokenizer,
                prompt_spec,
                labels,
                warmup_text,
                condition,
            )
            generate_one(model, tokenizer, prompt, max_tokens, processor)
        logger.info("Completed two synthetic warm-up generations")

        results_path = RUN_DIR / "sample-results.jsonl"
        results: list[dict[str, Any]] = []
        with results_path.open("x", encoding="utf-8") as sink:
            for selected_row in selected:
                condition_order = list(CONDITIONS)
                if selected_row["sample_index"] % 2:
                    condition_order.reverse()
                for condition in condition_order:
                    if time.perf_counter() - started > (
                        config["resource_budget"]["wall_time_minutes_max"] * 60
                    ):
                        raise TimeoutError("EXP-024 exceeded its frozen wall-time budget")
                    prompt = exp022.build_prompt(
                        tokenizer,
                        prompt_spec,
                        labels,
                        selected_row["text"],
                        condition,
                    )
                    measured = generate_one(
                        model,
                        tokenizer,
                        prompt,
                        max_tokens,
                        processor,
                    )
                    raw_output = measured.pop("output")
                    parsed = exp022.strict_parse(raw_output, labels)
                    record = {
                        "canonical_output": parsed["canonical_output"],
                        "condition": condition,
                        "finish_reason": measured["finish_reason"],
                        "generated_tokens": measured["generated_tokens"],
                        "generation_seconds": measured["generation_seconds"],
                        "generation_tps": measured["generation_tps"],
                        "length_stratum": selected_row["length_stratum"],
                        "output_character_count": len(raw_output),
                        "output_sha256": exp022.sha256_text(raw_output),
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
            raise ValueError(
                f"Measured {len(results)} generations; expected {expected_generations}"
            )

        full_dev_rows = config["data"]["dev_rows_for_linear_estimate"]
        condition_summaries = {
            condition: exp022.summarize_condition(
                [row for row in results if row["condition"] == condition],
                full_dev_rows=full_dev_rows,
            )
            for condition in CONDITIONS
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
            "constraint_candidate_token_count": processor.candidate_token_count,
            "constraint_init_seconds": constraint_init_seconds,
            "full_dev_rows_for_linear_estimate": full_dev_rows,
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
            "warmup_generations": len(CONDITIONS),
        }
        summary_path = RUN_DIR / "summary.json"
        exp022.write_json(summary_path, summary)

        run.update(
            {
                "artifacts": {
                    "config": {
                        "path": exp022.project_path(CONFIG_PATH),
                        "sha256": exp022.sha256_file(CONFIG_PATH),
                    },
                    "constraint": {
                        "path": exp022.project_path(CONSTRAINT_PATH),
                        "sha256": exp022.sha256_file(CONSTRAINT_PATH),
                    },
                    "parent_runner": {
                        "path": exp022.project_path(PARENT_RUNNER_PATH),
                        "sha256": exp022.sha256_file(PARENT_RUNNER_PATH),
                    },
                    "parent_selected_samples": {
                        "path": exp022.project_path(PARENT_SELECTED_PATH),
                        "sha256": exp022.sha256_file(PARENT_SELECTED_PATH),
                    },
                    "prompt": {
                        "path": exp022.project_path(PROMPT_PATH),
                        "sha256": exp022.sha256_file(PROMPT_PATH),
                    },
                    "runner": {
                        "path": exp022.project_path(RUNNER_PATH),
                        "sha256": exp022.sha256_file(RUNNER_PATH),
                    },
                    "sample_results": {
                        "path": exp022.project_path(results_path),
                        "sha256": exp022.sha256_file(results_path),
                    },
                    "selected_samples": {
                        "path": exp022.project_path(selected_path),
                        "sha256": exp022.sha256_file(selected_path),
                    },
                    "summary": {
                        "path": exp022.project_path(summary_path),
                        "sha256": exp022.sha256_file(summary_path),
                    },
                },
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "data_rows_scanned": config["data"]["expected_train_rows"],
                    "dataset_protocol": config["data"]["dataset_protocol"],
                    "dev_rows_accessed": 0,
                    "gold_labels_retained_or_used": False,
                    "measured_sample_count": config["data"]["sample_count"],
                    "selection_digest_sha256": selected_public[
                        "selection_digest_sha256"
                    ],
                    "split": "train",
                    "test_rows_accessed": 0,
                    "train_sha256": exp022.sha256_file(TRAIN_PATH),
                },
                "decoder": {
                    "candidate_token_count": processor.candidate_token_count,
                    "constraint": "finite-state label-name JSON token mask",
                    "fallback_to_unrestricted_generation": False,
                    "retries": 0,
                    "silent_repairs": False,
                    "synonym_mapping": False,
                },
                "gate_status": gate_status,
                "invocation": [sys.executable, *sys.argv],
                "model": {
                    "condition": "post-trained",
                    "local_path": exp022.project_path(MODEL_DIR),
                    "manifest_path": exp022.project_path(MODEL_MANIFEST_PATH),
                    "manifest_sha256": exp022.sha256_file(MODEL_MANIFEST_PATH),
                    "precision": "bfloat16",
                    "quantized": False,
                    "repo_id": "Qwen/Qwen3-1.7B",
                    "revision": EXPECTED_MODEL_REVISION,
                },
                "resource_usage": summary,
                "runtime": {
                    "environment": "emotion-llm-mlx",
                    "executable": sys.executable,
                    "git": exp022.git_metadata(),
                    "hardware": exp022.hardware_metadata(),
                    "packages": exp022.package_versions(),
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
        exp022.write_json(RUN_DIR / "run.json", run)

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
