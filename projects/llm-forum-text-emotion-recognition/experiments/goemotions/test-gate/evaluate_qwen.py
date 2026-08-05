#!/usr/bin/env python3
"""Evaluate the five frozen Qwen units for the EXP-038 test gate."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gc
import json
import math
import os
from pathlib import Path
import sys
from time import perf_counter
from typing import Any

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import mlx.core as mx
from mlx_lm import load, stream_generate
from mlx_lm.sample_utils import make_sampler
import numpy as np

from test_gate_common import (
    artifact,
    finalize_bundle,
    load_config,
    load_labels,
    load_split,
    resolve_project_path,
    sha256_text,
    verify_artifact,
    verify_formal_preflight,
    write_json,
)


SCRIPT_DIR = Path(__file__).resolve().parent
QWEN_DIR = SCRIPT_DIR.parent / "qwen3-1.7b"
sys.path.insert(0, str(QWEN_DIR))

import llm_full_dev_metrics as metric_tools
from label_json_constraint import LabelJsonLogitsProcessor
from label_json_constraint_neutral_cooccurrence import (
    NeutralCooccurrenceLogitsProcessor,
)
import run_lora as generation_helper
import run_resource_parser_trial as closed_prompt_helper


DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-038-frozen-test.json"
DEFAULT_PREFLIGHT = SCRIPT_DIR / "preflight" / "exp-038-qwen.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--config-sha256")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_log(path: Path, message: str) -> None:
    line = f"{utc_now()} {message}"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
    print(line, flush=True)


def verify_unit(unit: dict[str, Any]) -> None:
    for name in (
        "source_run",
        "source_verification",
        "source_predictions",
        "adapter_weights",
        "adapter_config",
        "prompt",
        "constraint",
        "model_manifest",
        "training_run",
        "training_verification",
    ):
        if name in unit:
            verify_artifact(unit[name])
    source_run = json.loads(
        resolve_project_path(unit["source_run"]["path"]).read_text(encoding="utf-8")
    )
    if source_run.get("test_split_accessed") is not False:
        raise ValueError(f"Source run already accessed test: {unit['id']}")


def strict_parse(output: str, labels: tuple[str, ...], allow_neutral_pair: bool) -> dict[str, Any]:
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
    if not allow_neutral_pair and "neutral" in values and len(values) > 1:
        return {"canonical_output": None, "error": "neutral-combined", "labels": []}
    return {
        "canonical_output": json.dumps({"labels": values}, separators=(",", ":")),
        "error": None,
        "labels": values,
    }


def build_prompt(
    tokenizer: Any,
    prompt_spec: dict[str, Any],
    labels: tuple[str, ...],
    text: str,
    unit: dict[str, Any],
) -> str:
    if unit["prompt_mode"] == "closed-neutral":
        return closed_prompt_helper.build_prompt(
            tokenizer,
            prompt_spec,
            labels,
            text,
            unit["scientific_condition"],
        )
    messages = [
        {
            "role": "system",
            "content": prompt_spec["system_template"].format(
                allowed_labels=", ".join(labels)
            ),
        },
        {"role": "user", "content": prompt_spec["user_template"].format(text=text)},
    ]
    return tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        enable_thinking=False,
        tokenize=False,
    )


def make_constraint(tokenizer: Any, labels: tuple[str, ...], unit: dict[str, Any]) -> Any:
    if unit["constraint_mode"] == "closed-neutral":
        processor = LabelJsonLogitsProcessor(tokenizer, labels, mx)
    elif unit["constraint_mode"] == "open-neutral":
        processor = NeutralCooccurrenceLogitsProcessor(tokenizer, labels, mx)
    else:
        raise ValueError(f"Unknown constraint mode: {unit['constraint_mode']}")
    return generation_helper.TelemetryConstraint(processor, mx)


def load_model(unit: dict[str, Any]) -> tuple[Any, Any]:
    model_path = resolve_project_path(unit["model_path"])
    if "adapter_weights" not in unit:
        return load(str(model_path), lazy=False)
    weights = verify_artifact(unit["adapter_weights"])
    config = verify_artifact(unit["adapter_config"])
    if weights.parent != config.parent:
        raise ValueError("Adapter weights and config do not share a directory")
    return load(str(model_path), adapter_path=str(weights.parent), lazy=False)


def source_output_hash(unit: dict[str, Any]) -> str:
    path = verify_artifact(unit["source_predictions"])
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if (
            record.get("row_number") == 1
            and record.get("condition") == unit["scientific_condition"]
        ):
            return str(record["output_sha256"])
    raise ValueError(f"Missing source preflight record for {unit['id']}")


def release_model(model: Any, tokenizer: Any, constraint: Any) -> None:
    del model, tokenizer, constraint
    gc.collect()
    if hasattr(mx, "clear_cache"):
        mx.clear_cache()


def generate_record(
    unit: dict[str, Any],
    model: Any,
    tokenizer: Any,
    constraint: Any,
    prompt_spec: dict[str, Any],
    labels: tuple[str, ...],
    text: str,
    gold_ids: list[int],
    row_number: int,
) -> dict[str, Any]:
    generated = generation_helper.generate_one(
        model,
        tokenizer,
        build_prompt(tokenizer, prompt_spec, labels, text, unit),
        int(unit["max_new_tokens"]),
        constraint,
        mx,
        stream_generate,
        make_sampler,
    )
    raw_output = generated.pop("output")
    parsed = strict_parse(
        raw_output,
        labels,
        allow_neutral_pair=unit["constraint_mode"] == "open-neutral",
    )
    parser_error = parsed["error"]
    parser_valid = parser_error is None
    if generated["finish_reason"] != "stop":
        parser_valid = False
        parser_error = "length-terminated"
    predicted_labels = parsed["labels"] if parser_valid else []
    label_to_id = {label: index for index, label in enumerate(labels)}
    return {
        "canonical_output": parsed["canonical_output"] if parser_valid else None,
        "condition": unit["scientific_condition"],
        "constraint_intervened": generated["constraint_intervened"],
        "finish_reason": generated["finish_reason"],
        "first_blocked_step": generated["first_blocked_step"],
        "first_blocked_token_id": generated["first_blocked_token_id"],
        "generated_tokens": generated["generated_tokens"],
        "generation_seconds": generated["generation_seconds"],
        "generation_tps": generated["generation_tps"],
        "gold_label_ids": gold_ids,
        "gold_labels": [labels[value] for value in gold_ids],
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
        "row_number": row_number,
        "sequence_logprob_mean": generated["sequence_logprob_mean"],
        "sequence_logprob_sum": generated["sequence_logprob_sum"],
        "sequence_score_space": unit["sequence_score_space"],
    }


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def verify_record_prefix(
    records: list[dict[str, Any]],
    gold_ids: list[list[int]],
    labels: tuple[str, ...],
    unit: dict[str, Any],
) -> None:
    if len(records) > len(gold_ids):
        raise ValueError("Generation checkpoint has too many rows")
    for index, record in enumerate(records):
        raw_output = record.get("raw_output")
        parsed = strict_parse(
            raw_output,
            labels,
            allow_neutral_pair=unit["constraint_mode"] == "open-neutral",
        )
        valid = parsed["error"] is None and record.get("finish_reason") == "stop"
        expected_labels = parsed["labels"] if valid else []
        if (
            record.get("row_number") != index + 1
            or record.get("gold_label_ids") != gold_ids[index]
            or record.get("condition") != unit["scientific_condition"]
            or record.get("output_sha256") != sha256_text(raw_output)
            or record.get("predicted_labels") != expected_labels
        ):
            raise ValueError(f"Generation checkpoint diverges at row {index + 1}")


def generation_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary = metric_tools.summarize_generation(records)
    summary["api_cost_usd"] = 0.0
    summary["raw_input_text_stored"] = False
    summary["raw_comment_ids_stored"] = False
    return summary


def run_preflight(config: dict[str, Any], config_sha256: str) -> None:
    if resolve_project_path(config["data"]["test"]["path"]).exists():
        raise RuntimeError("Qwen preflight must finish before test acquisition")
    labels = load_labels(config["data"]["labels"])
    dev_path = verify_artifact(config["data"]["dev"])
    texts, _, gold_ids, _ = load_split(dev_path, 5426, labels)
    report: dict[str, Any] = {
        "config_sha256": config_sha256,
        "experiment_id": "EXP-038",
        "status": "In Progress",
        "test_split_accessed": False,
        "units": {},
    }
    for unit in config["units"][4:]:
        verify_unit(unit)
        model, tokenizer = load_model(unit)
        constraint = make_constraint(tokenizer, labels, unit)
        prompt_spec = json.loads(verify_artifact(unit["prompt"]).read_text(encoding="utf-8"))
        record = generate_record(
            unit, model, tokenizer, constraint, prompt_spec, labels, texts[0], gold_ids[0], 1
        )
        expected_hash = source_output_hash(unit)
        if record["output_sha256"] != expected_hash:
            raise ValueError(
                f"{unit['id']} deterministic dev preflight changed: "
                f"{record['output_sha256']} != {expected_hash}"
            )
        report["units"][unit["id"]] = {
            "deterministic_output_match": True,
            "generated_tokens": record["generated_tokens"],
            "model_loaded": True,
            "output_sha256": record["output_sha256"],
            "peak_memory_gb": record["peak_memory_gb"],
        }
        release_model(model, tokenizer, constraint)
    report.update({"completed_at_utc": utc_now(), "status": "Passed"})
    write_json(DEFAULT_PREFLIGHT, report)
    print("EXP-038 Qwen preflight passed")


def run_unit(
    config: dict[str, Any],
    config_sha256: str,
    unit: dict[str, Any],
    texts: list[str],
    gold: np.ndarray,
    gold_ids: list[list[int]],
    labels: tuple[str, ...],
    output_root: Path,
    resume: bool,
) -> dict[str, Any]:
    unit_dir = output_root / unit["id"]
    records_path = unit_dir / "generation-records.jsonl"
    run_path = unit_dir / "run.json"
    if unit_dir.exists() and not resume:
        raise FileExistsError(f"Qwen unit output already exists: {unit_dir}")
    if not unit_dir.exists():
        unit_dir.mkdir()
        run = {
            "accessed_splits": ["test"],
            "config_sha256": config_sha256,
            "source_experiment_id": unit["source_experiment_id"],
            "started_at_utc": utc_now(),
            "status": "In Progress",
            "test_split_accessed": True,
            "unit_id": unit["id"],
        }
        write_json(run_path, run)
    else:
        run = json.loads(run_path.read_text(encoding="utf-8"))
        if run.get("config_sha256") != config_sha256:
            raise ValueError("Technical resume config changed")
        if run.get("status") == "Completed; pending independent verification":
            return run
        if run.get("status") not in {"In Progress", "Failed"}:
            raise ValueError("Only an incomplete Qwen unit may resume")
        run["status"] = "In Progress"
        run.pop("error", None)
        write_json(run_path, run)

    records = read_records(records_path)
    verify_record_prefix(records, gold_ids, labels, unit)
    verify_unit(unit)
    model, tokenizer = load_model(unit)
    constraint = make_constraint(tokenizer, labels, unit)
    prompt_spec = json.loads(verify_artifact(unit["prompt"]).read_text(encoding="utf-8"))
    started = perf_counter()
    active_generation_seconds = sum(
        float(record["generation_seconds"]) for record in records
    )
    try:
        with records_path.open("a" if records else "x", encoding="utf-8") as handle:
            for index in range(len(records), len(texts)):
                record = generate_record(
                    unit,
                    model,
                    tokenizer,
                    constraint,
                    prompt_spec,
                    labels,
                    texts[index],
                    gold_ids[index],
                    index + 1,
                )
                if float(record["peak_memory_gb"]) > float(
                    config["resource_budget"]["peak_mlx_memory_gb_max"]
                ):
                    raise MemoryError("Qwen test unit exceeded the frozen memory gate")
                handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
                handle.flush()
                records.append(record)
                active_generation_seconds += float(record["generation_seconds"])
                if (index + 1) % 100 == 0 or index + 1 == len(texts):
                    os.fsync(handle.fileno())
                    run["progress"] = {"completed": index + 1, "total": len(texts)}
                    write_json(run_path, run)
                    append_log(
                        output_root / "stdout.log",
                        f"{unit['id']} {index + 1}/{len(texts)}; "
                        f"elapsed={(perf_counter() - started) / 60:.1f} min",
                    )
                if active_generation_seconds > float(
                    config["resource_budget"]["qwen_wall_time_hours_max_per_unit"]
                ) * 3600:
                    raise TimeoutError(
                        "Qwen test unit exceeded its frozen active-generation gate"
                    )
        verify_record_prefix(records, gold_ids, labels, unit)
        predicted = metric_tools.records_to_prediction_matrix(records, labels)
        metric_tools.write_predictions(unit_dir / "predictions.csv", records)
        metrics = finalize_bundle(
            unit_dir,
            gold,
            predicted,
            labels,
            extra_metrics={"generation": generation_summary(records)},
        )
        run.update(
            {
                "artifacts": {
                    path.name: artifact(path)
                    for path in sorted(unit_dir.iterdir())
                    if path.is_file() and path.name != "run.json"
                },
                "completed_at_utc": utc_now(),
                "generation_count": len(records),
                "metrics": {
                    "macro_f1": metrics["macro"]["f1"],
                    "micro_f1": metrics["micro"]["f1"],
                    "subset_accuracy": metrics["subset_accuracy"],
                    "weighted_f1": metrics["weighted"]["f1"],
                },
                "raw_comment_ids_stored": False,
                "raw_input_text_stored": False,
                "status": "Completed; pending independent verification",
                "test_rows_accessed": len(texts),
            }
        )
        write_json(run_path, run)
        return run
    except BaseException as error:
        run.update(
            {
                "completed_at_utc": utc_now(),
                "error": {"message": str(error), "type": type(error).__name__},
                "status": "Failed",
            }
        )
        write_json(run_path, run)
        raise
    finally:
        release_model(model, tokenizer, constraint)


def run_formal(config: dict[str, Any], config_sha256: str, resume: bool) -> None:
    verify_formal_preflight(config)
    output_root = resolve_project_path(config["output_dir"])
    classical = output_root / "classical-bert-worker.json"
    if not classical.is_file():
        raise FileNotFoundError("Classical/BERT stage must complete before Qwen test")
    classical_record = json.loads(classical.read_text(encoding="utf-8"))
    if classical_record.get("status") != "Completed; pending independent verification":
        raise ValueError("Classical/BERT test stage is incomplete")
    test_path = verify_artifact(config["data"]["test"])
    labels = load_labels(config["data"]["labels"])
    texts, gold, gold_ids, _ = load_split(test_path, 5427, labels)
    worker_path = output_root / "qwen-worker.json"
    worker = (
        json.loads(worker_path.read_text(encoding="utf-8"))
        if worker_path.exists()
        else {
            "config_sha256": config_sha256,
            "experiment_id": "EXP-038",
            "started_at_utc": utc_now(),
            "status": "In Progress",
            "test_split_accessed": True,
            "units": {},
        }
    )
    if worker.get("config_sha256") != config_sha256:
        raise ValueError("Qwen worker config changed")
    write_json(worker_path, worker)
    for unit in config["units"][4:]:
        result = run_unit(
            config,
            config_sha256,
            unit,
            texts,
            gold,
            gold_ids,
            labels,
            output_root,
            resume,
        )
        worker["units"][unit["id"]] = result["metrics"]
        write_json(worker_path, worker)
    worker.update(
        {
            "completed_at_utc": utc_now(),
            "status": "Completed; pending independent verification",
            "test_rows_accessed": len(texts),
        }
    )
    write_json(worker_path, worker)


def main() -> None:
    args = parse_args()
    config, config_sha256 = load_config(
        args.config.resolve(),
        args.config_sha256,
        allow_unbound_test=args.preflight,
    )
    if args.preflight:
        if args.resume:
            raise ValueError("--resume is not valid for preflight")
        run_preflight(config, config_sha256)
    else:
        run_formal(config, config_sha256, args.resume)


if __name__ == "__main__":
    main()
