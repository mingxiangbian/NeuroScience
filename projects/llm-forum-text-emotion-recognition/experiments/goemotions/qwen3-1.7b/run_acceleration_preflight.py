#!/usr/bin/env python3
"""Run the train-only EXP-032 retraining acceleration preflight."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time
import traceback
from typing import Any

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["PYTHONNOUSERSITE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

EXPERIMENT_ID = "EXP-032"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
CONFIG_PATH = SCRIPT_DIR / "configs" / "exp-032-acceleration-preflight.json"
VERIFIER_PATH = SCRIPT_DIR / "verify_acceleration_preflight.py"
PARENT_RUNNER_PATH = SCRIPT_DIR / "run_lora.py"
ONTOLOGY_RUNNER_PATH = SCRIPT_DIR / "run_neutral_ontology_ablation.py"
CONSTRAINT_PATH = SCRIPT_DIR / "label_json_constraint_neutral_cooccurrence.py"
TEST_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "test.tsv"
PYTHON = Path("/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python")
MLX_LORA = Path("/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/mlx_lm.lora")

sys.path.insert(0, str(SCRIPT_DIR))
import run_lora as parent
import run_neutral_ontology_ablation as ontology


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "kv-smoke", "run"))
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_token_ids(token_ids: list[int]) -> str:
    payload = json.dumps(token_ids, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


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
    return PROJECT_ROOT / value


def project_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": project_path(path),
        "sha256": sha256_file(path),
    }


def verify_hash(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"Frozen hash mismatch for {path}: {actual} != {expected}")


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if (
        config["experiment_id"] != EXPERIMENT_ID
        or config["tier"] != "Minor"
        or config["status"] != "Registered"
    ):
        raise ValueError("EXP-032 must remain a registered Minor configuration")
    if any(value == "PENDING" for value in config["implementation"].values()):
        raise ValueError("Implementation hashes must be frozen before execution")
    return config


def verify_static_inputs(config: dict[str, Any], *, require_train: bool) -> None:
    if TEST_PATH.exists():
        raise ValueError(f"Test split must remain absent: {TEST_PATH}")
    if not PYTHON.is_file() or not MLX_LORA.is_file():
        raise FileNotFoundError("The emotion-llm-mlx environment is unavailable")
    checks = [
        (resolve_project_path(config["data"]["labels_path"]), config["data"]["labels_sha256"]),
        (resolve_project_path(config["model"]["manifest_path"]), config["model"]["manifest_sha256"]),
        (resolve_project_path(config["inference_cache"]["prompt_path"]), config["inference_cache"]["prompt_sha256"]),
        (resolve_project_path(config["inference_cache"]["adapter_path"]), config["inference_cache"]["adapter_sha256"]),
        (resolve_project_path(config["implementation"]["constraint_path"]), config["implementation"]["constraint_sha256"]),
        (resolve_project_path(config["implementation"]["parent_config_path"]), config["implementation"]["parent_config_sha256"]),
        (resolve_project_path(config["implementation"]["parent_runner_path"]), config["implementation"]["parent_runner_sha256"]),
        (resolve_project_path(config["implementation"]["ontology_runner_path"]), config["implementation"]["ontology_runner_sha256"]),
        (Path(__file__).resolve(), config["implementation"]["runner_sha256"]),
        (VERIFIER_PATH, config["implementation"]["verifier_sha256"]),
    ]
    if require_train:
        checks.extend(
            [
                (resolve_project_path(config["data"]["train_path"]), config["data"]["train_sha256"]),
                (resolve_project_path(config["artifacts"]["prepared_train_path"]), config["data"]["prepared_train_sha256"]),
            ]
        )
    for path, expected in checks:
        verify_hash(path, expected)
    model_dir = resolve_project_path(config["model"]["local_path"])
    if not model_dir.is_dir() or not any(model_dir.glob("*.safetensors")):
        raise FileNotFoundError(f"Local model is unavailable: {model_dir}")
    conditions = config["training_benchmark"]["conditions"]
    if len(conditions) != int(config["resource_budget"]["training_runs_max"]):
        raise ValueError("Training condition count exceeds the registered run budget")
    for spec in conditions.values():
        if spec["batch_size"] * spec["grad_accumulation_steps"] != config["training_benchmark"]["effective_batch_size"]:
            raise ValueError("Training conditions do not preserve effective batch size")
        if spec["batch_size"] * spec["iterations"] != config["training_benchmark"]["fixed_processed_rows"]:
            raise ValueError("Training conditions do not preserve processed rows")
        if spec["iterations"] // spec["grad_accumulation_steps"] != config["training_benchmark"]["fixed_optimizer_updates"]:
            raise ValueError("Training conditions do not preserve optimizer updates")


def runtime_training_config(
    config: dict[str, Any], condition: str, adapter_dir: Path
) -> dict[str, Any]:
    parent_config = json.loads(
        resolve_project_path(config["implementation"]["parent_config_path"])
        .read_text(encoding="utf-8")
    )
    training = parent_config["training"]
    lora = training["lora"]
    benchmark = config["training_benchmark"]
    condition_spec = benchmark["conditions"][condition]
    return {
        "adapter_path": str(adapter_dir),
        "batch_size": int(condition_spec["batch_size"]),
        "clear_cache_threshold": 0,
        "data": str(resolve_project_path(config["artifacts"]["prepared_train_path"]).parent),
        "fine_tune_type": training["fine_tune_type"],
        "grad_accumulation_steps": int(condition_spec["grad_accumulation_steps"]),
        "grad_checkpoint": bool(training["grad_checkpoint"]),
        "iters": int(condition_spec["iterations"]),
        "learning_rate": float(benchmark["learning_rate"]),
        "lora_parameters": {
            "dropout": float(lora["dropout"]),
            "keys": list(lora["target_modules"]),
            "rank": int(lora["rank"]),
            "scale": float(lora["scale"]),
        },
        "mask_prompt": bool(training["mask_prompt"]),
        "max_seq_length": int(benchmark["max_sequence_length"]),
        "model": str(resolve_project_path(config["model"]["local_path"])),
        "num_layers": int(lora["num_layers"]),
        "optimizer": benchmark["optimizer"],
        "save_every": int(condition_spec["iterations"]) + 1,
        "seed": int(benchmark["seed"]),
        "steps_per_eval": int(condition_spec["iterations"]) + 1,
        "steps_per_report": int(benchmark["steps_per_report"]),
        "test": False,
        "train": True,
        "val_batches": 0,
    }


def summarize_history(
    config: dict[str, Any], condition: str, history: list[dict[str, Any]]
) -> dict[str, Any]:
    spec = config["training_benchmark"]["conditions"][condition]
    report_step = int(config["training_benchmark"]["steps_per_report"])
    steady = [
        row
        for row in history
        if int(row["iteration"]) >= report_step
        and int(row["iteration"]) % report_step == 0
    ]
    if not steady:
        raise ValueError(f"No steady-state reports for {condition}")
    rows_per_second = [
        float(row["iterations_per_second"]) * int(spec["batch_size"])
        for row in steady
    ]
    median_rows_per_second = statistics.median(rows_per_second)
    return {
        "batch_size": int(spec["batch_size"]),
        "effective_batch_size": int(config["training_benchmark"]["effective_batch_size"]),
        "final_train_loss": float(history[-1]["train_loss"]),
        "grad_accumulation_steps": int(spec["grad_accumulation_steps"]),
        "history_reports": len(history),
        "iterations": int(spec["iterations"]),
        "median_steady_iterations_per_second": statistics.median(
            float(row["iterations_per_second"]) for row in steady
        ),
        "median_steady_rows_per_second": median_rows_per_second,
        "optimizer_updates": int(spec["iterations"]) // int(spec["grad_accumulation_steps"]),
        "peak_mlx_memory_gb": max(float(row["peak_memory_gb"]) for row in history),
        "processed_rows": int(spec["iterations"]) * int(spec["batch_size"]),
        "projected_full_epoch_hours": int(config["data"]["prepared_train_rows"])
        / median_rows_per_second
        / 3600,
        "steady_report_count": len(steady),
    }


def run_training_condition(
    config: dict[str, Any], condition: str, run_root: Path
) -> dict[str, Any]:
    condition_dir = run_root / "training" / condition
    condition_dir.mkdir(parents=True, exist_ok=False)
    private_root = resolve_project_path(config["artifacts"]["private_adapter_root"])
    adapter_dir = private_root / condition
    if adapter_dir.exists():
        raise FileExistsError(f"Private benchmark adapter already exists: {adapter_dir}")
    adapter_dir.mkdir(parents=True, exist_ok=False)
    runtime = runtime_training_config(config, condition, adapter_dir)
    runtime_path = adapter_dir / "runtime-config.json"
    write_json(runtime_path, runtime)
    log_path = condition_dir / "stdout.log"
    command = [str(MLX_LORA), "-c", str(runtime_path)]
    started_at = datetime.now(timezone.utc)
    try:
        return_code, duration = parent.stream_subprocess(
            command,
            log_path,
            float(config["resource_budget"]["training_condition_wall_time_minutes_max"]) * 60,
        )
        if return_code != 0:
            raise RuntimeError(f"MLX-LM exited with status {return_code}")
        history, trainable = parent.parse_training_log(log_path)
        expected_iteration = int(config["training_benchmark"]["conditions"][condition]["iterations"])
        if int(history[-1]["iteration"]) != expected_iteration:
            raise ValueError(f"{condition} did not reach its frozen iteration budget")
        adapter_weights = adapter_dir / "adapters.safetensors"
        adapter_config = adapter_dir / "adapter_config.json"
        if not adapter_weights.is_file() or not adapter_config.is_file():
            raise FileNotFoundError(f"{condition} did not save a final adapter")
        weight_summary = parent.adapter_weight_summary(adapter_weights)
        if weight_summary["lora_b_nonzero_tensors"] != weight_summary["lora_b_tensor_count"]:
            raise ValueError(f"{condition} left a LoRA B tensor entirely zero")
        history_path = condition_dir / "history.csv"
        parent.write_history(history_path, history)
        summary = summarize_history(config, condition, history)
        memory_gate = float(config["training_benchmark"]["candidate_selection_gate"]["peak_mlx_memory_gb_max"])
        summary.update(
            {
                "adapter": {
                    "config": artifact(adapter_config),
                    "runtime_config": artifact(runtime_path),
                    "weights": artifact(adapter_weights),
                    **weight_summary,
                },
                "command": command,
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "condition": condition,
                "duration_seconds": duration,
                "history": artifact(history_path),
                "memory_gate_passed": summary["peak_mlx_memory_gb"] <= memory_gate,
                "started_at_utc": started_at.isoformat(),
                "status": "Passed" if summary["peak_mlx_memory_gb"] <= memory_gate else "Rejected",
                "stdout": artifact(log_path),
                "trainable_parameters_reported": trainable,
            }
        )
        return summary
    except BaseException as error:
        return {
            "command": command,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "condition": condition,
            "error": {"message": str(error), "traceback": traceback.format_exc()},
            "started_at_utc": started_at.isoformat(),
            "status": "Failed",
            "stdout": artifact(log_path) if log_path.is_file() else None,
        }


def load_train_texts(path: Path, row_numbers: list[int]) -> list[tuple[int, str]]:
    wanted = set(row_numbers)
    found: dict[int, str] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for index, row in enumerate(csv.reader(handle, delimiter="\t"), start=1):
            if index in wanted:
                if len(row) != 3:
                    raise ValueError(f"Invalid train row {index}")
                found[index] = row[0]
    if set(found) != wanted:
        raise ValueError("The frozen cache sample row inventory is incomplete")
    return [(row_number, found[row_number]) for row_number in row_numbers]


def encode_prompt(tokenizer: Any, prompt: str) -> list[int]:
    add_special_tokens = tokenizer.bos_token is None or not prompt.startswith(tokenizer.bos_token)
    return [int(value) for value in tokenizer.encode(prompt, add_special_tokens=add_special_tokens)]


def longest_common_prefix(sequences: list[list[int]]) -> list[int]:
    if not sequences:
        raise ValueError("No prompts supplied")
    prefix = list(sequences[0])
    for sequence in sequences[1:]:
        limit = min(len(prefix), len(sequence))
        index = 0
        while index < limit and prefix[index] == sequence[index]:
            index += 1
        prefix = prefix[:index]
        if not prefix:
            break
    if not prefix or any(len(sequence) <= len(prefix) for sequence in sequences):
        raise ValueError("Prompts do not provide a reusable non-terminal common prefix")
    return prefix


def cache_sizes(prompt_cache: list[Any]) -> list[int]:
    sizes = []
    for item in prompt_cache:
        if hasattr(item, "size"):
            sizes.append(int(item.size()))
        elif hasattr(item, "offset"):
            sizes.append(int(item.offset))
        else:
            raise TypeError(f"Unsupported prompt cache type: {type(item)}")
    return sizes


def generate_tokens(
    *,
    model: Any,
    tokenizer: Any,
    prompt: list[int],
    max_tokens: int,
    constraint: Any,
    mx: Any,
    stream_generate: Any,
    make_sampler: Any,
    prompt_cache: list[Any] | None = None,
) -> dict[str, Any]:
    constraint.reset()
    mx.reset_peak_memory()
    started = time.perf_counter()
    output_parts: list[str] = []
    token_ids: list[int] = []
    last_response = None
    kwargs: dict[str, Any] = {}
    if prompt_cache is not None:
        kwargs["prompt_cache"] = prompt_cache
    for response in stream_generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
        sampler=make_sampler(temp=0.0),
        logits_processors=[constraint],
        **kwargs,
    ):
        output_parts.append(response.text)
        token_ids.append(int(response.token))
        last_response = response
    elapsed = time.perf_counter() - started
    if last_response is None:
        raise RuntimeError("MLX-LM yielded no generation response")
    output = "".join(output_parts)
    return {
        "finish_reason": last_response.finish_reason,
        "generation_seconds": elapsed,
        "generated_tokens": int(last_response.generation_tokens),
        "output": output,
        "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
        "peak_memory_gb": float(last_response.peak_memory),
        "token_ids": token_ids,
        "token_ids_sha256": sha256_token_ids(token_ids),
        **constraint.snapshot(),
    }


def evaluate_cache(
    config: dict[str, Any], samples: list[tuple[str, str]]
) -> dict[str, Any]:
    from mlx_lm import load, stream_generate
    from mlx_lm.generate import generate_step
    from mlx_lm.models.cache import make_prompt_cache, trim_prompt_cache
    from mlx_lm.sample_utils import make_sampler
    import mlx.core as mx
    from label_json_constraint_neutral_cooccurrence import NeutralCooccurrenceLogitsProcessor

    labels = tuple(
        resolve_project_path(config["data"]["labels_path"])
        .read_text(encoding="utf-8")
        .splitlines()
    )
    prompt_spec = json.loads(
        resolve_project_path(config["inference_cache"]["prompt_path"]).read_text(encoding="utf-8")
    )
    adapter_dir = resolve_project_path(config["inference_cache"]["adapter_path"]).parent
    model_load_started = time.perf_counter()
    model, tokenizer = load(
        str(resolve_project_path(config["model"]["local_path"])),
        adapter_path=str(adapter_dir),
        lazy=False,
    )
    model_load_seconds = time.perf_counter() - model_load_started
    prompts = [
        encode_prompt(tokenizer, ontology.build_prompt(tokenizer, prompt_spec, labels, text))
        for _, text in samples
    ]
    prefix = longest_common_prefix(prompts)
    suffixes = [tokens[len(prefix) :] for tokens in prompts]
    if any(prefix + suffix != full for full, suffix in zip(prompts, suffixes)):
        raise AssertionError("Prompt prefix/suffix reconstruction failed")

    prefix_cache = make_prompt_cache(model)
    prefix_started = time.perf_counter()
    for _ in generate_step(mx.array(prefix), model, max_tokens=0, prompt_cache=prefix_cache):
        pass
    mx.eval([item.state for item in prefix_cache])
    prefix_build_seconds = time.perf_counter() - prefix_started
    prefix_sizes = cache_sizes(prefix_cache)
    if any(size != len(prefix) for size in prefix_sizes):
        raise ValueError("Precomputed cache length differs from common-prefix length")

    baseline_constraint = parent.TelemetryConstraint(
        NeutralCooccurrenceLogitsProcessor(tokenizer, labels, mx), mx
    )
    cached_constraint = parent.TelemetryConstraint(
        NeutralCooccurrenceLogitsProcessor(tokenizer, labels, mx), mx
    )
    maximum = int(config["inference_cache"]["max_new_tokens"])

    generate_tokens(
        model=model,
        tokenizer=tokenizer,
        prompt=prompts[0],
        max_tokens=maximum,
        constraint=baseline_constraint,
        mx=mx,
        stream_generate=stream_generate,
        make_sampler=make_sampler,
    )
    generate_tokens(
        model=model,
        tokenizer=tokenizer,
        prompt=suffixes[0],
        max_tokens=maximum,
        constraint=cached_constraint,
        mx=mx,
        stream_generate=stream_generate,
        make_sampler=make_sampler,
        prompt_cache=prefix_cache,
    )
    added = cache_sizes(prefix_cache)[0] - len(prefix)
    if added <= 0 or trim_prompt_cache(prefix_cache, added) != added:
        raise ValueError("Unable to restore the reusable cache after warm-up")
    if cache_sizes(prefix_cache) != prefix_sizes:
        raise ValueError("Warm-up did not restore the common-prefix cache")

    records = []
    baseline_total = 0.0
    cached_total = 0.0
    peak_memory = 0.0
    for index, ((sample_id, _), full_prompt, suffix) in enumerate(
        zip(samples, prompts, suffixes)
    ):
        def baseline_call() -> dict[str, Any]:
            return generate_tokens(
                model=model,
                tokenizer=tokenizer,
                prompt=full_prompt,
                max_tokens=maximum,
                constraint=baseline_constraint,
                mx=mx,
                stream_generate=stream_generate,
                make_sampler=make_sampler,
            )

        def cached_call() -> dict[str, Any]:
            started = time.perf_counter()
            generated = generate_tokens(
                model=model,
                tokenizer=tokenizer,
                prompt=suffix,
                max_tokens=maximum,
                constraint=cached_constraint,
                mx=mx,
                stream_generate=stream_generate,
                make_sampler=make_sampler,
                prompt_cache=prefix_cache,
            )
            current_sizes = cache_sizes(prefix_cache)
            if len(set(current_sizes)) != 1:
                raise ValueError("Layer cache sizes diverged")
            appended = current_sizes[0] - len(prefix)
            if appended <= 0 or trim_prompt_cache(prefix_cache, appended) != appended:
                raise ValueError("Unable to trim the per-sample cache suffix")
            if cache_sizes(prefix_cache) != prefix_sizes:
                raise ValueError("Reusable cache was not restored")
            generated["generation_seconds"] = time.perf_counter() - started
            return generated

        if index % 2 == 0:
            baseline = baseline_call()
            cached = cached_call()
        else:
            cached = cached_call()
            baseline = baseline_call()
        parsed_baseline = ontology.strict_parse(baseline["output"], labels)
        parsed_cached = ontology.strict_parse(cached["output"], labels)
        identical = (
            baseline["token_ids"] == cached["token_ids"]
            and baseline["finish_reason"] == cached["finish_reason"]
            and baseline["output_sha256"] == cached["output_sha256"]
        )
        baseline_total += float(baseline["generation_seconds"])
        cached_total += float(cached["generation_seconds"])
        peak_memory = max(
            peak_memory,
            float(baseline["peak_memory_gb"]),
            float(cached["peak_memory_gb"]),
        )
        records.append(
            {
                "baseline_finish_reason": baseline["finish_reason"],
                "baseline_generation_seconds": baseline["generation_seconds"],
                "baseline_output_sha256": baseline["output_sha256"],
                "baseline_parser_valid": parsed_baseline["error"] is None,
                "baseline_token_ids": baseline["token_ids"],
                "baseline_token_ids_sha256": baseline["token_ids_sha256"],
                "cached_finish_reason": cached["finish_reason"],
                "cached_generation_seconds": cached["generation_seconds"],
                "cached_output_sha256": cached["output_sha256"],
                "cached_parser_valid": parsed_cached["error"] is None,
                "cached_token_ids": cached["token_ids"],
                "cached_token_ids_sha256": cached["token_ids_sha256"],
                "exact_token_identity": identical,
                "full_prompt_tokens": len(full_prompt),
                "sample_id": sample_id,
                "suffix_tokens": len(suffix),
            }
        )
    cached_end_to_end = prefix_build_seconds + cached_total
    exact_count = sum(bool(record["exact_token_identity"]) for record in records)
    cache_speedup = baseline_total / cached_end_to_end
    cache_gate = config["inference_cache"]
    return {
        "baseline_generation_seconds_total": baseline_total,
        "cache_build_seconds": prefix_build_seconds,
        "cached_generation_seconds_total": cached_total,
        "cached_seconds_including_one_time_build": cached_end_to_end,
        "end_to_end_speedup": cache_speedup,
        "exact_token_identity_count": exact_count,
        "exact_token_identity_rate": exact_count / len(records),
        "full_prompt_tokens": {
            "max": max(len(tokens) for tokens in prompts),
            "median": statistics.median(len(tokens) for tokens in prompts),
            "min": min(len(tokens) for tokens in prompts),
        },
        "model_load_seconds": model_load_seconds,
        "peak_mlx_memory_gb": peak_memory,
        "prefix_tokens": len(prefix),
        "records": records,
        "recommended": exact_count == len(records)
        and cache_speedup >= float(cache_gate["minimum_end_to_end_speedup"]),
        "sample_count": len(records),
        "suffix_tokens": {
            "max": max(len(tokens) for tokens in suffixes),
            "median": statistics.median(len(tokens) for tokens in suffixes),
            "min": min(len(tokens) for tokens in suffixes),
        },
    }


def run_kv_smoke(config: dict[str, Any]) -> None:
    verify_static_inputs(config, require_train=False)
    samples = [
        ("synthetic-1", "I am pleased that the adapter is ready."),
        ("synthetic-2", "Nothing special happened, but I am slightly annoyed."),
    ]
    report = evaluate_cache(config, samples)
    if report["exact_token_identity_count"] != len(samples):
        raise ValueError("Synthetic KV-cache generation is not token-identical")
    sanitized = {key: value for key, value in report.items() if key != "records"}
    print(json.dumps({"status": "Passed", **sanitized}, indent=2, sort_keys=True))


def source_artifacts(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "config": artifact(CONFIG_PATH),
        "constraint": artifact(CONSTRAINT_PATH),
        "labels": artifact(resolve_project_path(config["data"]["labels_path"])),
        "model_manifest": artifact(resolve_project_path(config["model"]["manifest_path"])),
        "ontology_runner": artifact(ONTOLOGY_RUNNER_PATH),
        "parent_config": artifact(resolve_project_path(config["implementation"]["parent_config_path"])),
        "parent_runner": artifact(PARENT_RUNNER_PATH),
        "prompt": artifact(resolve_project_path(config["inference_cache"]["prompt_path"])),
        "runner": artifact(Path(__file__).resolve()),
        "verifier": artifact(VERIFIER_PATH),
    }


def run_formal(config: dict[str, Any]) -> None:
    verify_static_inputs(config, require_train=True)
    run_root = resolve_project_path(config["artifacts"]["run_root"])
    private_root = resolve_project_path(config["artifacts"]["private_adapter_root"])
    if run_root.exists() or private_root.exists():
        raise FileExistsError("Append-only EXP-032 output already exists")
    run_root.mkdir(parents=True, exist_ok=False)
    private_root.mkdir(parents=True, exist_ok=False)
    run_path = run_root / "run.json"
    started_at = datetime.now(timezone.utc)
    initial = {
        "accessed_splits": ["train"],
        "api_cost_usd": 0,
        "command": [str(PYTHON), project_path(Path(__file__)), "run"],
        "experiment_id": EXPERIMENT_ID,
        "git": parent.git_metadata(),
        "raw_comment_ids_stored": False,
        "raw_input_text_stored": False,
        "rq_id": config["rq_id"],
        "stage": config["stage"],
        "started_at_utc": started_at.isoformat(),
        "status": "In Progress",
        "test_split_accessed": False,
        "tier": "Minor",
        "validation_split_accessed": False,
        "working_directory": str(REPO_ROOT),
    }
    write_json(run_path, initial)
    try:
        training_results = {
            condition: run_training_condition(config, condition, run_root)
            for condition in config["training_benchmark"]["conditions"]
        }
        baseline = training_results["batch2-grad5"]
        candidate = training_results["batch5-grad2"]
        if baseline["status"] != "Passed":
            raise RuntimeError("The frozen current training configuration failed")
        speedup = None
        candidate_selected = False
        if candidate["status"] == "Passed":
            speedup = float(candidate["median_steady_rows_per_second"]) / float(
                baseline["median_steady_rows_per_second"]
            )
            candidate_selected = speedup >= float(
                config["training_benchmark"]["candidate_selection_gate"][
                    "minimum_steady_rows_per_second_speedup"
                ]
            )
        training_summary = {
            "candidate_selected": candidate_selected,
            "conditions": training_results,
            "fixed_effective_batch_size": config["training_benchmark"]["effective_batch_size"],
            "fixed_optimizer_updates": config["training_benchmark"]["fixed_optimizer_updates"],
            "fixed_processed_rows": config["training_benchmark"]["fixed_processed_rows"],
            "selected_condition": "batch5-grad2" if candidate_selected else "batch2-grad5",
            "steady_rows_per_second_speedup": speedup,
        }
        training_summary_path = run_root / "training-benchmark.json"
        write_json(training_summary_path, training_summary)

        train_samples = load_train_texts(
            resolve_project_path(config["data"]["train_path"]),
            [int(value) for value in config["inference_cache"]["sample_row_numbers"]],
        )
        cache_summary = evaluate_cache(
            config,
            [(f"train-row-{row_number}", text) for row_number, text in train_samples],
        )
        cache_records = cache_summary.pop("records")
        cache_records_path = run_root / "kv-cache-records.json"
        cache_summary_path = run_root / "kv-cache-summary.json"
        write_json(cache_records_path, cache_records)
        write_json(cache_summary_path, cache_summary)

        completed = {
            **initial,
            "artifacts": {
                "cache_records": artifact(cache_records_path),
                "cache_summary": artifact(cache_summary_path),
                "training_summary": artifact(training_summary_path),
            },
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "data": {
                "cache_sample_rows": len(train_samples),
                "prepared_training_rows_available": config["data"]["prepared_train_rows"],
                "split": "train",
                "test_rows_accessed": 0,
                "training_rows_processed_per_condition": config["training_benchmark"]["fixed_processed_rows"],
                "validation_rows_accessed": 0,
            },
            "duration_seconds": (datetime.now(timezone.utc) - started_at).total_seconds(),
            "environment": parent.package_versions(),
            "hardware": parent.hardware_metadata(),
            "inference_cache_decision": {
                "end_to_end_speedup": cache_summary["end_to_end_speedup"],
                "exact_token_identity_rate": cache_summary["exact_token_identity_rate"],
                "selected": "common-prefix-kv-cache" if cache_summary["recommended"] else "full-prompt",
            },
            "source_artifacts": source_artifacts(config),
            "status": "Completed",
            "training_decision": {
                "selected": training_summary["selected_condition"],
                "steady_rows_per_second_speedup": speedup,
            },
        }
        write_json(run_path, completed)
        print(json.dumps(completed, indent=2, sort_keys=True))
    except BaseException as error:
        failed = json.loads(run_path.read_text(encoding="utf-8"))
        failed.update(
            {
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "error": {"message": str(error), "traceback": traceback.format_exc()},
                "status": "Failed",
            }
        )
        write_json(run_path, failed)
        raise


def main() -> None:
    args = parse_args()
    config = load_config()
    if args.command == "check":
        verify_static_inputs(config, require_train=True)
        print(json.dumps({"experiment_id": EXPERIMENT_ID, "status": "Passed"}, indent=2))
    elif args.command == "kv-smoke":
        run_kv_smoke(config)
    else:
        run_formal(config)


if __name__ == "__main__":
    main()
