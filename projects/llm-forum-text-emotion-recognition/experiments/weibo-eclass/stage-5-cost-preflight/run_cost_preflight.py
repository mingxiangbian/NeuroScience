#!/usr/bin/env python3
"""Run the train-only EXP-044 Qwen3-4B LoRA cost preflight."""

from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
from typing import Any, Iterable


EXPERIMENT_ID = "EXP-044"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
CONFIG_PATH = SCRIPT_DIR / "config.json"
MLX_PYTHON = Path("/Users/phoenix/miniconda3/envs/emotion-llm-mlx/bin/python")
MLX_LORA = MLX_PYTHON.parent / "mlx_lm.lora"
TRAIN_LOG_PATTERN = re.compile(
    r"Iter (?P<iteration>\d+): Train loss (?P<loss>[^,]+), "
    r"Learning Rate (?P<learning_rate>[^,]+), It/sec (?P<iterations_per_second>[^,]+), "
    r"Tokens/sec (?P<tokens_per_second>[^,]+), Trained Tokens (?P<trained_tokens>\d+), "
    r"Peak mem (?P<peak_memory_gb>[^ ]+) GB"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Project-relative path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def write_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if private:
        os.chmod(temporary, 0o600)
    temporary.replace(path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]], *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    if private:
        os.chmod(temporary, 0o600)
    temporary.replace(path)


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("Unexpected experiment ID")
    if config.get("tier") != "Minor" or config.get("status") != "Registered":
        raise ValueError("EXP-044 must remain a registered Minor experiment")
    data = config["data"]
    if data["split"] != "train" or data["validation_access"] or data["test_access"]:
        raise ValueError("EXP-044 must remain train-only")
    return config


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    return {"commit": commit, "dirty": bool(status), "dirty_path_count": len(status)}


def package_versions(names: Iterable[str]) -> dict[str, str]:
    result = {"python": platform.python_version()}
    for name in names:
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = "not-installed"
    return result


def machine_metadata() -> dict[str, Any]:
    def sysctl(name: str) -> str | None:
        completed = subprocess.run(["sysctl", "-n", name], capture_output=True, text=True)
        return completed.stdout.strip() if completed.returncode == 0 else None

    memory = sysctl("hw.memsize")
    return {
        "machine": platform.machine(),
        "mac_model": sysctl("hw.model"),
        "memory_bytes": int(memory) if memory else None,
        "platform": platform.platform(),
    }


def load_train(config: dict[str, Any]) -> list[dict[str, Any]]:
    path = resolve_project_path(config["data"]["train_path"])
    if sha256_file(path) != config["data"]["train_sha256"]:
        raise ValueError("Frozen train hash mismatch")
    rows: list[dict[str, Any]] = []
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
    for line_number, line in enumerate(path.open(encoding="utf-8"), start=1):
        row = json.loads(line)
        if set(row) != expected_keys:
            raise ValueError(f"Unexpected train schema at line {line_number}")
        if row["protocol_id"] != config["data"]["protocol_id"]:
            raise ValueError(f"Protocol mismatch at line {line_number}")
        if row["label"] not in config["data"]["labels"]:
            raise ValueError(f"Unknown label at line {line_number}")
        target = row["views"]["target_only"]["target"]
        if not isinstance(target, str) or not target:
            raise ValueError(f"Invalid target at line {line_number}")
        rows.append(row)
    if len(rows) != config["data"]["train_rows"]:
        raise ValueError("Frozen train row count mismatch")
    if len({row["sample_id"] for row in rows}) != len(rows):
        raise ValueError("Train sample IDs are not unique")
    return rows


def load_prompt(config: dict[str, Any]) -> dict[str, Any]:
    path = resolve_project_path(config["prompt"]["path"])
    if sha256_file(path) != config["prompt"]["sha256"]:
        raise ValueError("Frozen prompt hash mismatch")
    prompt = json.loads(path.read_text(encoding="utf-8"))
    if list(prompt["label_definitions"]) != config["data"]["labels"]:
        raise ValueError("Prompt label order drift")
    return prompt


def render_messages(config: dict[str, Any], prompt: dict[str, Any], row: dict[str, Any]) -> list[dict[str, str]]:
    definitions = "\n".join(
        f"- {label}: {prompt['label_definitions'][label]}" for label in config["data"]["labels"]
    )
    system = prompt["system_template"].format(
        label_definitions=definitions,
        output_schema=prompt["output_schema"],
    )
    target = row["views"]["target_only"]["target"]
    assistant = prompt["assistant_target_template"].replace("{label}", row["label"])
    if json.loads(assistant) != {"label": row["label"]}:
        raise ValueError("Assistant target violates the strict JSON contract")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt["target_only_template"].format(target=target)},
        {"role": "assistant", "content": assistant},
    ]


def allocate_quotas(counts: dict[str, int], total: int, label_order: list[str]) -> dict[str, int]:
    population = sum(counts.values())
    if total < len(label_order) or total > population:
        raise ValueError("Invalid proportional sample size")
    raw = {label: total * counts[label] / population for label in label_order}
    quotas = {label: max(1, math.floor(raw[label])) for label in label_order}
    while sum(quotas.values()) > total:
        candidates = [label for label in label_order if quotas[label] > 1]
        label = min(candidates, key=lambda item: (raw[item] - quotas[item], label_order.index(item)))
        quotas[label] -= 1
    while sum(quotas.values()) < total:
        label = max(
            label_order,
            key=lambda item: (raw[item] - quotas[item], -label_order.index(item)),
        )
        quotas[label] += 1
    return quotas


def select_length_quantiles(
    measured: list[dict[str, Any]], quotas: dict[str, int], label_order: list[str], namespace: str
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for label in label_order:
        values = [row for row in measured if row["label"] == label]
        values.sort(
            key=lambda row: (
                row["token_length"],
                sha256_text(f"{namespace}:{row['sample_id']}"),
            )
        )
        quota = quotas[label]
        if quota > len(values):
            raise ValueError(f"Quota exceeds label population: {label}")
        indices = [min(len(values) - 1, ((2 * rank + 1) * len(values)) // (2 * quota)) for rank in range(quota)]
        if len(set(indices)) != quota:
            raise ValueError(f"Systematic selection duplicated a row for {label}")
        selected.extend(values[index] for index in indices)
    return selected


def quantile(values: list[float | int], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("Cannot summarize an empty sequence")
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def numeric_summary(values: list[float | int]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "min": min(values),
        "p50": quantile(values, 0.50),
        "p95": quantile(values, 0.95),
        "p99": quantile(values, 0.99),
    }


def parse_history(log_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = TRAIN_LOG_PATTERN.search(line)
        if not match:
            continue
        row = {
            "iteration": int(match.group("iteration")),
            "train_loss": float(match.group("loss")),
            "learning_rate": float(match.group("learning_rate")),
            "iterations_per_second": float(match.group("iterations_per_second")),
            "tokens_per_second": float(match.group("tokens_per_second")),
            "trained_tokens": int(match.group("trained_tokens")),
            "peak_memory_gb": float(match.group("peak_memory_gb")),
        }
        if not all(math.isfinite(value) for value in row.values() if isinstance(value, float)):
            raise ValueError("Training history contains NaN or infinity")
        rows.append(row)
    return rows


def write_history(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("Cannot write an empty history")
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def adapter_summary(path: Path) -> dict[str, Any]:
    import numpy as np
    from safetensors import safe_open

    result = Counter()
    finite = True
    with safe_open(path, framework="numpy") as source:
        for name in source.keys():
            tensor = source.get_tensor(name)
            result["tensor_count"] += 1
            result["trainable_parameter_count"] += int(tensor.size)
            finite = finite and bool(np.all(np.isfinite(tensor)))
            if name.endswith("lora_b"):
                result["lora_b_tensor_count"] += 1
                result["lora_b_nonzero_tensors"] += int(bool(np.any(tensor != 0)))
    return {**dict(result), "all_finite": finite}


def runtime_config(config: dict[str, Any], private_root: Path) -> dict[str, Any]:
    training = config["training"]
    return {
        "adapter_path": str(private_root / "adapter"),
        "batch_size": training["batch_size"],
        "clear_cache_threshold": 0,
        "data": str(private_root / "lora-data"),
        "fine_tune_type": "lora",
        "grad_accumulation_steps": training["grad_accumulation_steps"],
        "grad_checkpoint": training["grad_checkpoint"],
        "iters": training["iterations"],
        "learning_rate": training["learning_rate"],
        "lora_parameters": {
            "dropout": training["dropout"],
            "keys": training["target_modules"],
            "rank": training["rank"],
            "scale": training["scale"],
        },
        "lr_schedule": None,
        "mask_prompt": training["mask_prompt"],
        "max_seq_length": training["max_sequence_length"],
        "model": str(resolve_project_path(config["model"]["local_path"])),
        "num_layers": training["num_layers"],
        "optimizer": training["optimizer"],
        "optimizer_config": {training["optimizer"]: {}},
        "project_name": None,
        "report_to": None,
        "resume_adapter_file": None,
        "save_every": training["iterations"] + 1,
        "seed": training["seed"],
        "steps_per_eval": training["iterations"] + 1,
        "steps_per_report": training["report_every"],
        "test": False,
        "test_batches": 0,
        "train": True,
        "val_batches": 0,
    }


def run_training(command: list[str], log_path: Path, timeout_seconds: float) -> tuple[int, float]:
    started = time.perf_counter()
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env={
                **os.environ,
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "TOKENIZERS_PARALLELISM": "false",
            },
        )
        assert process.stdout is not None
        for line in process.stdout:
            log.write(line)
            log.flush()
            print(line, end="", flush=True)
            if time.perf_counter() - started > timeout_seconds:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                return 124, time.perf_counter() - started
        return process.wait(), time.perf_counter() - started


def insertion_contract(config: dict[str, Any]) -> tuple[int, int]:
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.tuner import linear_to_lora_layers
    from mlx.utils import tree_flatten

    training = config["training"]
    model, _ = load(str(resolve_project_path(config["model"]["local_path"])))
    if len(model.layers) != config["model"]["num_hidden_layers"]:
        raise ValueError("Loaded Qwen layer count drift")
    model.freeze()
    linear_to_lora_layers(
        model,
        training["num_layers"],
        {
            "dropout": training["dropout"],
            "keys": training["target_modules"],
            "rank": training["rank"],
            "scale": training["scale"],
        },
    )
    observed: list[tuple[int, str]] = []
    trainable_parameters = sum(
        int(parameter.size) for _, parameter in tree_flatten(model.trainable_parameters())
    )
    for name, module in model.named_modules():
        if type(module).__name__ != "LoRALinear":
            continue
        match = re.search(r"(?:^|\.)layers\.(\d+)\.(.+)$", name)
        if not match:
            raise ValueError(f"Unexpected LoRA module path: {name}")
        observed.append((int(match.group(1)), match.group(2)))
    expected = [
        (block, target)
        for block in training["adapted_block_indices"]
        for target in training["target_modules"]
    ]
    if sorted(observed) != sorted(expected):
        raise ValueError("LoRA insertion set differs from the frozen contract")
    del model
    gc.collect()
    mx.clear_cache()
    return len(observed), trainable_parameters


def reload_adapter(config: dict[str, Any], adapter_dir: Path) -> bool:
    import mlx.core as mx
    from mlx_lm import load

    model, tokenizer = load(
        str(resolve_project_path(config["model"]["local_path"])),
        adapter_path=str(adapter_dir),
    )
    token_ids = tokenizer.encode("预检", add_special_tokens=False)[:1]
    logits = model(mx.array([token_ids]))
    mx.eval(logits)
    finite = bool(mx.all(mx.isfinite(logits)).item())
    del model, tokenizer, logits
    gc.collect()
    mx.clear_cache()
    return finite


def cost_projection(config: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    cutoff = config["training"]["steady_state_after_iteration"]
    steady = [row for row in history if row["iteration"] > cutoff]
    if len(steady) < 5:
        raise ValueError("Insufficient steady-state training reports")
    rates = [row["iterations_per_second"] for row in steady]
    median_rate = statistics.median(rates)
    safety = config["resource_budget"]["safety_multiplier"]
    projections = []
    for epochs in config["training"]["epochs_for_projection"]:
        raw_hours = config["data"]["train_rows"] * epochs / median_rate / 3600
        projections.append(
            {
                "epochs": epochs,
                "one_seed_hours_raw": raw_hours,
                "one_seed_hours_with_safety": raw_hours * safety,
                "three_seeds_hours_sequential_with_safety": raw_hours * safety * 3,
            }
        )
    return {
        "basis": "median steady-state iterations/second; training only; sequential seeds",
        "median_iterations_per_second": median_rate,
        "p25_iterations_per_second": quantile(rates, 0.25),
        "p75_iterations_per_second": quantile(rates, 0.75),
        "safety_multiplier": safety,
        "steady_state_after_iteration": cutoff,
        "steady_state_report_count": len(steady),
        "training_rows": config["data"]["train_rows"],
        "projections": projections,
        "validation_and_inference_time_included": False,
    }


def main() -> None:
    config = load_config()
    run_dir = resolve_project_path(config["run_dir"])
    private_root = resolve_project_path(config["private_root"])
    if (run_dir.exists() and any(run_dir.iterdir())) or (private_root.exists() and any(private_root.iterdir())):
        raise FileExistsError("EXP-044 output directory is not empty; completed runs are append-only")
    run_dir.mkdir(parents=True, exist_ok=True)
    private_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    started_at = utc_now()
    started = time.perf_counter()
    command = [str(MLX_LORA), "-c", str(private_root / "lora-runtime.json")]
    run: dict[str, Any] = {
        "accessed_splits": ["train"],
        "command": " ".join(command),
        "config_sha256": sha256_file(CONFIG_PATH),
        "cwd": str(REPO_ROOT),
        "experiment_id": EXPERIMENT_ID,
        "git": git_metadata(),
        "rq_ids": config["rq_ids"],
        "stage": config["stage"],
        "started_at_utc": started_at,
        "status": "In Progress",
        "test_split_accessed": False,
        "tier": config["tier"],
        "validation_split_accessed": False,
    }
    write_json(run_dir / "run.json", run)
    try:
        if not MLX_LORA.is_file():
            raise FileNotFoundError(f"MLX-LM CLI is missing: {MLX_LORA}")
        if sha256_file(resolve_project_path(config["model"]["manifest_path"])) != config["model"]["manifest_sha256"]:
            raise ValueError("Frozen model manifest hash mismatch")
        rows = load_train(config)
        prompt = load_prompt(config)

        os.environ.update(
            {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
        )
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            resolve_project_path(config["model"]["local_path"]), local_files_only=True
        )
        measured: list[dict[str, Any]] = []
        expected_wrapper = "<think>\n\n</think>\n\n"
        for row in rows:
            messages = render_messages(config, prompt, row)
            token_ids = tokenizer.apply_chat_template(messages, return_dict=False)
            prompt_ids = tokenizer.apply_chat_template(
                messages[:-1], add_generation_prompt=True, return_dict=False
            )
            supervised = tokenizer.decode(token_ids[len(prompt_ids) :])
            expected = expected_wrapper + messages[-1]["content"] + "<|im_end|>\n"
            if supervised != expected:
                raise ValueError("Qwen chat-template supervision boundary drift")
            if len(token_ids) > config["training"]["max_sequence_length"]:
                raise ValueError("A target-only train row exceeds the frozen token budget")
            measured.append(
                {
                    "label": row["label"],
                    "messages": messages,
                    "sample_id": row["sample_id"],
                    "supervised_tokens": len(token_ids) - len(prompt_ids),
                    "token_length": len(token_ids),
                }
            )

        populations = Counter(row["label"] for row in measured)
        quotas = allocate_quotas(dict(populations), config["sampling"]["rows"], config["data"]["labels"])
        selected = select_length_quantiles(
            measured,
            quotas,
            config["data"]["labels"],
            config["sampling"]["seed_namespace"],
        )
        if len(selected) != config["sampling"]["rows"]:
            raise ValueError("Representative sample row count mismatch")
        selected_counts = Counter(row["label"] for row in selected)
        selection_material = "\n".join(
            sha256_text(f"{config['sampling']['seed_namespace']}:{row['sample_id']}") for row in selected
        )
        sample_summary = {
            "accessed_splits": ["train"],
            "experiment_id": EXPERIMENT_ID,
            "method": config["sampling"]["method"],
            "population_label_counts": dict(populations),
            "population_token_lengths": numeric_summary([row["token_length"] for row in measured]),
            "raw_ids_stored_publicly": False,
            "raw_text_stored_publicly": False,
            "sample_label_counts": dict(selected_counts),
            "sample_rows": len(selected),
            "sample_token_lengths": numeric_summary([row["token_length"] for row in selected]),
            "selection_digest_sha256": sha256_text(selection_material),
            "supervised_token_lengths": numeric_summary([row["supervised_tokens"] for row in selected]),
            "template_contract": {
                "assistant_target": "strict JSON single label",
                "empty_think_wrapper_inserted_by_chat_template": True,
                "mask_prompt": True,
                "rationale_gold": False,
            },
            "test_split_accessed": False,
            "validation_split_accessed": False,
        }
        write_json(run_dir / "sample_summary.json", sample_summary)
        write_jsonl(
            private_root / "selection-manifest.jsonl",
            (
                {
                    "label": row["label"],
                    "sample_id": row["sample_id"],
                    "sample_id_sha256": sha256_text(row["sample_id"]),
                    "supervised_tokens": row["supervised_tokens"],
                    "token_length": row["token_length"],
                }
                for row in selected
            ),
            private=True,
        )
        lora_data = private_root / "lora-data" / "train.jsonl"
        write_jsonl(lora_data, ({"messages": row["messages"]} for row in selected), private=True)

        insertion_count, trainable_parameters = insertion_contract(config)
        runtime = runtime_config(config, private_root)
        write_json(private_root / "lora-runtime.json", runtime, private=True)
        log_path = private_root / "stdout.log"
        return_code, training_seconds = run_training(
            command,
            log_path,
            config["resource_budget"]["local_wall_time_minutes_max"] * 60,
        )
        if return_code != 0:
            raise RuntimeError(f"MLX-LM exited with return code {return_code}")
        history = parse_history(log_path)
        if not history or history[-1]["iteration"] != config["training"]["iterations"]:
            raise ValueError("Training history did not reach the frozen iteration count")
        write_history(run_dir / "history.csv", history)

        adapter_dir = private_root / "adapter"
        adapter_file = adapter_dir / "adapters.safetensors"
        adapter_config = adapter_dir / "adapter_config.json"
        if not adapter_file.is_file() or not adapter_config.is_file():
            raise FileNotFoundError("MLX-LM did not save the final adapter")
        adapter = adapter_summary(adapter_file)
        expected_lora_b = len(config["training"]["adapted_block_indices"]) * len(
            config["training"]["target_modules"]
        )
        if (
            adapter.get("lora_b_tensor_count") != expected_lora_b
            or adapter.get("lora_b_nonzero_tensors") != expected_lora_b
            or adapter.get("trainable_parameter_count") != trainable_parameters
            or not adapter["all_finite"]
        ):
            raise ValueError("Saved adapter violates the LoRA tensor contract")
        if not reload_adapter(config, adapter_dir):
            raise ValueError("Reloaded adapter produced non-finite logits")

        projection = cost_projection(config, history)
        peak_memory = max(row["peak_memory_gb"] for row in history)
        if peak_memory > config["resource_budget"]["peak_memory_gb_max"]:
            raise RuntimeError("Training exceeded the frozen peak-memory gate")
        projection.update(
            {
                "api_cost_usd": 0,
                "observed_peak_memory_gb": peak_memory,
                "observed_preflight_iterations": config["training"]["iterations"],
                "observed_training_seconds": training_seconds,
                "practical_local_training_decision": "Pending user decision",
                "technical_feasibility": "Passed",
            }
        )
        write_json(run_dir / "cost_projection.json", projection)

        run.update(
            {
                "artifacts": {
                    "adapter": {
                        "bytes": adapter_file.stat().st_size,
                        "path_publicly_disclosed": False,
                        "sha256": sha256_file(adapter_file),
                    },
                    "cost_projection": display_path(run_dir / "cost_projection.json"),
                    "history": display_path(run_dir / "history.csv"),
                    "private_train": {
                        "path_publicly_disclosed": False,
                        "rows": len(selected),
                        "sha256": sha256_file(lora_data),
                    },
                    "sample_summary": display_path(run_dir / "sample_summary.json"),
                },
                "completed_at_utc": utc_now(),
                "data": {
                    "labels": config["data"]["labels"],
                    "protocol_id": config["data"]["protocol_id"],
                    "sample_rows": len(selected),
                    "split": "train",
                    "train_rows": len(rows),
                    "train_sha256": config["data"]["train_sha256"],
                },
                "duration_seconds": time.perf_counter() - started,
                "environment": package_versions(("mlx", "mlx-lm", "numpy", "safetensors", "transformers")),
                "hardware": machine_metadata(),
                "model": config["model"],
                "result": {
                    "adapter": adapter,
                    "exact_insertion_count": insertion_count,
                    "history_report_rows": len(history),
                    "peak_memory_gb": peak_memory,
                    "reload_finite_logits": True,
                    "trainable_parameter_count": trainable_parameters,
                    "training_seconds": training_seconds,
                },
                "status": "Awaiting Independent Verification",
                "training": config["training"],
                "warnings": [
                    "This Minor run estimates training cost and does not report classification performance.",
                    "The projection excludes validation generation, checkpoint selection, and error analysis.",
                    "Label-only SFT uses Qwen3's empty-think chat-template wrapper; no rationale is supervised.",
                ],
            }
        )
        write_json(run_dir / "run.json", run)
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "peak_memory_gb": peak_memory,
                    "status": run["status"],
                    "training_seconds": training_seconds,
                }
            )
        )
    except Exception as error:
        run.update(
            {
                "completed_at_utc": utc_now(),
                "duration_seconds": time.perf_counter() - started,
                "error": {"message": str(error), "type": type(error).__name__},
                "status": "Failed",
            }
        )
        write_json(run_dir / "run.json", run)
        raise


if __name__ == "__main__":
    main()
