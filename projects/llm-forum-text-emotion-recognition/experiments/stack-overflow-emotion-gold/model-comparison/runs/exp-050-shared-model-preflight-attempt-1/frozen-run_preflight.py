#!/usr/bin/env python3
"""Run the train-only EXP-050 model-stack preflight in explicit stages."""

from __future__ import annotations

import argparse
from collections import Counter
import gc
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "config.json"
DEFAULT_RUN_DIR = SCRIPT_DIR / "runs" / "exp-050-shared-model-preflight"
PRIVATE_DIR = SCRIPT_DIR / "private" / "exp-050-shared-model-preflight"
FROZEN_FILES = (
    "config.json",
    "prompt-v1.json",
    "run_preflight.py",
    "strict_multilabel_parser.py",
    "verify_preflight.py",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def write_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if private:
        os.chmod(path.parent, 0o700)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if private:
        os.chmod(temporary, 0o600)
    temporary.replace(path)
    if private:
        os.chmod(path, 0o600)


def resolve_project(path: str) -> Path:
    return PROJECT_ROOT / path


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config["preflight"]["experiment_id"] != "EXP-050":
        raise ValueError("Unexpected experiment identity")
    return config


def require_hash(path: Path, expected: str) -> None:
    observed = sha256(path)
    if observed != expected:
        raise ValueError(f"Hash mismatch for {path}: {observed}")


def load_train(config: dict[str, Any]) -> list[dict[str, Any]]:
    path = resolve_project(config["data"]["train_path"])
    require_hash(path, config["data"]["train_sha256"])
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if len(rows) != config["data"]["train_rows"]:
        raise ValueError("Train row count drift")
    expected_fields = {
        "component_id", "label_cardinality", "labels", "neutral",
        "protocol_id", "sample_id", "schema_version", "text",
    }
    for row in rows:
        if set(row) != expected_fields or row["protocol_id"] != config["data"]["protocol_id"]:
            raise ValueError("Train schema drift")
        if len(row["labels"]) != 6 or any(value not in (0, 1) for value in row["labels"]):
            raise ValueError("Invalid train label vector")
        if row["label_cardinality"] != sum(row["labels"]):
            raise ValueError("Label cardinality drift")
        if row["neutral"] != (sum(row["labels"]) == 0):
            raise ValueError("Neutral derivation drift")
    return rows


def ranked(rows: list[dict[str, Any]], namespace: str) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: hashlib.sha256(f"{namespace}|{row['sample_id']}".encode()).hexdigest(),
    )


def select_smoke_rows(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    namespace = config["preflight"]["selection_namespace"]
    labels = config["data"]["labels"]
    selected: dict[str, dict[str, Any]] = {}

    def add(candidates: list[dict[str, Any]], criterion: str, count: int) -> None:
        for row in ranked(candidates, f"{namespace}|{criterion}"):
            if row["sample_id"] not in selected:
                selected[row["sample_id"]] = row
            if sum(1 for item in selected.values() if item in candidates) >= count:
                break

    for index, label in enumerate(labels):
        positives = [row for row in rows if row["labels"][index] == 1]
        before = len(selected)
        for row in ranked(positives, f"{namespace}|positive|{label}"):
            selected.setdefault(row["sample_id"], row)
            if len(selected) >= before + 2:
                break
    for criterion, candidates, count in (
        ("neutral", [row for row in rows if row["neutral"]], 4),
        ("cardinality2", [row for row in rows if row["label_cardinality"] == 2], 4),
    ):
        added = 0
        for row in ranked(candidates, f"{namespace}|{criterion}"):
            if row["sample_id"] in selected:
                continue
            selected[row["sample_id"]] = row
            added += 1
            if added == count:
                break
    for row in ranked(rows, f"{namespace}|fill"):
        selected.setdefault(row["sample_id"], row)
        if len(selected) == config["preflight"]["sample_rows"]:
            break
    output = ranked(list(selected.values()), f"{namespace}|final-order")
    if len(output) != config["preflight"]["sample_rows"]:
        raise ValueError("Smoke selection size drift")
    positives = [sum(row["labels"][index] for row in output) for index in range(6)]
    if any(count < 2 or count == len(output) for count in positives):
        raise ValueError("Smoke selection lacks positive/negative label coverage")
    if sum(row["neutral"] for row in output) < 4:
        raise ValueError("Smoke selection lacks neutral coverage")
    if sum(row["label_cardinality"] == 2 for row in output) < 4:
        raise ValueError("Smoke selection lacks multi-label coverage")
    return output


def selection_summary(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    labels = config["data"]["labels"]
    identities = [{"sample_id": row["sample_id"], "component_id": row["component_id"]} for row in rows]
    return {
        "rows": len(rows),
        "selection_digest_sha256": canonical_digest(identities),
        "order_digest_sha256": canonical_digest([row["sample_id"] for row in rows]),
        "positive_counts": {label: sum(row["labels"][i] for row in rows) for i, label in enumerate(labels)},
        "neutral_rows": sum(row["neutral"] for row in rows),
        "cardinality_2_rows": sum(row["label_cardinality"] == 2 for row in rows),
        "identities_public": False,
    }


def load_prompt(config: dict[str, Any]) -> dict[str, Any]:
    path = resolve_project(config["prompt"]["path"])
    require_hash(path, config["prompt"]["sha256"])
    return json.loads(path.read_text(encoding="utf-8"))


def messages(prompt: dict[str, Any], text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": prompt["system"]},
        {"role": "user", "content": prompt["user_prefix"] + text + prompt["user_suffix"]},
    ]


def normalize_token_ids(value: Any) -> list[int]:
    if not isinstance(value, list) or any(type(token) is not int for token in value):
        raise TypeError("Tokenizer must return a plain list of integer token IDs")
    return value


def qwen_prompt_ids(tokenizer: Any, prompt: dict[str, Any], text: str, limit: int) -> list[int]:
    ids = normalize_token_ids(
        tokenizer.apply_chat_template(
            messages(prompt, text),
            tokenize=True,
            return_dict=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    )
    if len(ids) > limit:
        raise ValueError("Frozen train input unexpectedly exceeds the 384-token contract")
    decoded = tokenizer.decode(ids)
    if not decoded.endswith("<think>\n\n</think>\n\n"):
        raise ValueError("Qwen prompt does not end in the frozen empty-think wrapper")
    return ids


def package_versions(names: tuple[str, ...]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in names:
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = "not-installed"
    return result


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    return {"commit": commit, "dirty": bool(status), "dirty_path_count": len(status)}


def report_path(run_dir: Path, stage: str) -> Path:
    return run_dir / f"{stage}.json"


def load_run(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "run.json"
    if not path.is_file():
        raise FileNotFoundError("Static stage must run first")
    return json.loads(path.read_text(encoding="utf-8"))


def record_stage(run_dir: Path, stage: str, status: str, started: str, elapsed: float) -> None:
    run = load_run(run_dir)
    run["stages"][stage] = {
        "status": status,
        "started_at_utc": started,
        "completed_at_utc": utc_now(),
        "wall_seconds": elapsed,
    }
    run["status"] = "Failed" if status == "Failed" else (
        "Passed" if all(run["stages"].get(name, {}).get("status") == "Passed" for name in run["required_stages"])
        else "In progress"
    )
    write_json(run_dir / "run.json", run)


def require_stage(run_dir: Path, *stages: str) -> None:
    run = load_run(run_dir)
    for stage in stages:
        if run["stages"].get(stage, {}).get("status") != "Passed":
            raise ValueError(f"Required stage has not passed: {stage}")


def numeric_summary(values: list[int]) -> dict[str, int]:
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "p50": ordered[len(ordered) // 2],
        "p95": ordered[int(len(ordered) * 0.95)],
        "p99": ordered[int(len(ordered) * 0.99)],
        "max": ordered[-1],
    }


def run_static(config_path: Path, config: dict[str, Any], run_dir: Path) -> None:
    if run_dir.exists():
        raise FileExistsError(f"Refusing to overwrite {run_dir}")
    started_at, started = utc_now(), time.perf_counter()
    run_dir.mkdir(parents=True)
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(PRIVATE_DIR, 0o700)
    for name in FROZEN_FILES:
        source = SCRIPT_DIR / name
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copy2(source, run_dir / f"frozen-{name}")

    require_hash(resolve_project(config["data"]["task_manifest_path"]), config["data"]["task_manifest_sha256"])
    require_hash(resolve_project(config["prompt"]["chat_template_path"]), config["prompt"]["chat_template_sha256"])
    require_hash(resolve_project(config["prompt"]["tokenizer_asset_path"]), config["prompt"]["tokenizer_asset_sha256"])
    for model in (config["models"]["m1"], config["models"]["qwen_shared"]):
        require_hash(resolve_project(model["manifest_path"]), model["manifest_sha256"])

    rows = load_train(config)
    selected = select_smoke_rows(rows, config)
    prompt = load_prompt(config)
    from transformers import AutoTokenizer

    roberta = AutoTokenizer.from_pretrained(resolve_project(config["models"]["m1"]["local_path"]), local_files_only=True)
    qwen = AutoTokenizer.from_pretrained(resolve_project(config["models"]["qwen_shared"]["local_path"]), local_files_only=True)
    roberta_lengths = [len(roberta.encode(row["text"], add_special_tokens=True)) for row in rows]
    qwen_lengths = [qwen_prompt_ids(qwen, prompt, row["text"], config["prompt"]["max_sequence_length"]) for row in rows]
    qwen_length_values = [len(ids) for ids in qwen_lengths]
    if max(roberta_lengths) > config["models"]["m1"]["max_sequence_length"]:
        raise ValueError("RoBERTa train input exceeds frozen max length")
    if max(qwen_length_values) > config["prompt"]["max_sequence_length"]:
        raise ValueError("Qwen train input exceeds frozen max length")
    if len({tuple(ids[-5:]) for ids in qwen_lengths}) != 1:
        raise ValueError("Qwen frozen prompt suffix token IDs drift across train rows")

    static = {
        "status": "Passed",
        "experiment_id": "EXP-050",
        "accessed_splits": ["train"],
        "accessed_row_level_files": [config["data"]["train_path"]],
        "validation_split_accessed": False,
        "test_split_accessed": False,
        "performance_metrics_computed": False,
        "selection": selection_summary(selected, config),
        "label_order": config["data"]["labels"],
        "roberta_token_lengths": numeric_summary(roberta_lengths),
        "qwen_prompt_token_lengths": numeric_summary(qwen_length_values),
        "qwen_prompt_suffix_token_sha256": canonical_digest(qwen_lengths[0][-5:]),
        "prompt_sha256": config["prompt"]["sha256"],
        "config_sha256": sha256(config_path),
        "raw_text_stored_publicly": False,
        "row_level_labels_stored_publicly": False,
    }
    write_json(report_path(run_dir, "static"), static)
    run = {
        "experiment_id": "EXP-050",
        "tier": "Minor",
        "rq_id": config["rq_id"],
        "status": "In progress",
        "created_at_utc": utc_now(),
        "command_contract": "run_preflight.py --stage {static,m1,m2,m3,m4}",
        "cwd": str(REPO_ROOT),
        "git": git_metadata(),
        "platform": platform.platform(),
        "required_stages": ["static", "m1", "m2", "m3", "m4"],
        "stages": {},
        "accessed_splits": ["train"],
        "validation_split_accessed": False,
        "test_split_accessed": False,
        "formal_training_authorized": False,
    }
    write_json(run_dir / "run.json", run)
    record_stage(run_dir, "static", "Passed", started_at, time.perf_counter() - started)


def tensor_digest_torch(parameters: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(parameters.items()):
        array = tensor.detach().cpu().float().contiguous().numpy()
        digest.update(name.encode())
        digest.update(str(tuple(array.shape)).encode())
        digest.update(array.tobytes())
    return digest.hexdigest()


def run_m1(config: dict[str, Any], run_dir: Path) -> None:
    require_stage(run_dir, "static")
    output = report_path(run_dir, "m1")
    if output.exists():
        raise FileExistsError(output)
    started_at, started = utc_now(), time.perf_counter()
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    seed = config["evaluation"]["seeds"][0]
    torch.manual_seed(seed)
    if torch.backends.mps.is_available():
        torch.mps.manual_seed(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    rows = select_smoke_rows(load_train(config), config)
    model_spec = config["models"]["m1"]
    model_path = resolve_project(model_spec["local_path"])
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_path,
        local_files_only=True,
        num_labels=6,
        problem_type="multi_label_classification",
        ignore_mismatched_sizes=True,
    ).to(device)
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=model_spec["learning_rate"], weight_decay=model_spec["weight_decay"])
    before = {name: value.detach().clone() for name, value in model.named_parameters() if name.startswith("classifier.")}
    before_digest = tensor_digest_torch(before)
    losses: list[float] = []
    shapes: list[list[int]] = []
    for batch_rows in (rows[:12], rows[12:24]):
        batch = tokenizer(
            [row["text"] for row in batch_rows], padding=True, truncation=False, return_tensors="pt"
        ).to(device)
        targets = torch.tensor([row["labels"] for row in batch_rows], dtype=torch.float32, device=device)
        optimizer.zero_grad(set_to_none=True)
        logits = model(**batch).logits
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, targets)
        if not torch.isfinite(loss) or tuple(logits.shape) != (12, 6):
            raise ValueError("M1 finite loss/logit-shape gate failed")
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu()))
        shapes.append(list(logits.shape))
    after = {name: value.detach().clone() for name, value in model.named_parameters() if name.startswith("classifier.")}
    after_digest = tensor_digest_torch(after)
    if before_digest == after_digest:
        raise ValueError("M1 classifier parameters did not change")
    report = {
        "status": "Passed", "experiment_id": "EXP-050", "model_condition": "M1",
        "accessed_splits": ["train"], "validation_split_accessed": False, "test_split_accessed": False,
        "optimizer_steps": 2, "batch_sizes": [12, 12], "logit_shapes": shapes,
        "finite_losses": losses, "classifier_initial_sha256": before_digest,
        "classifier_final_sha256": after_digest, "trainable_parameters_changed": True,
        "device": str(device), "packages": package_versions(("torch", "transformers")),
        "performance_metrics_computed": False, "raw_text_stored_publicly": False,
    }
    write_json(output, report)
    record_stage(run_dir, "m1", "Passed", started_at, time.perf_counter() - started)


def mlx_tensor_digest(items: list[tuple[str, Any]]) -> str:
    import numpy as np
    import mlx.core as mx
    digest = hashlib.sha256()
    for name, tensor in sorted(items):
        array = np.asarray(tensor.astype(mx.float32))
        digest.update(name.encode())
        digest.update(str(tuple(array.shape)).encode())
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def mlx_trainable(module: Any) -> list[tuple[str, Any]]:
    from mlx.utils import tree_flatten
    return list(tree_flatten(module.trainable_parameters()))


def build_qwen_head(seed: int, hidden_size: int) -> Any:
    import mlx.core as mx
    import mlx.nn as nn
    mx.random.seed(seed)
    return nn.Linear(hidden_size, 6, bias=True)


def qwen_row_ids(tokenizer: Any, prompt: dict[str, Any], row: dict[str, Any], config: dict[str, Any]) -> Any:
    import mlx.core as mx
    ids = qwen_prompt_ids(tokenizer, prompt, row["text"], config["prompt"]["max_sequence_length"])
    return mx.array([ids], dtype=mx.int32)


def make_classification_wrapper(backbone: Any, head: Any) -> Any:
    import mlx.nn as nn

    class Wrapper(nn.Module):
        def __init__(self, base: Any, linear: Any):
            super().__init__()
            self.backbone = base
            self.head = linear

        def __call__(self, input_ids: Any) -> Any:
            hidden = self.backbone.model(input_ids)
            return self.head(hidden[:, -1, :].astype(self.head.weight.dtype))

    return Wrapper(backbone, head)


def classification_loss(wrapper: Any, input_ids: Any, targets: Any) -> Any:
    import mlx.nn as nn
    return nn.losses.binary_cross_entropy(wrapper(input_ids), targets, with_logits=True, reduction="mean")


def insertion_contract(model: Any, config: dict[str, Any]) -> list[tuple[int, str]]:
    import re
    observed: list[tuple[int, str]] = []
    for name, module in model.named_modules():
        if type(module).__name__ != "LoRALinear":
            continue
        match = re.search(r"(?:^|\.)layers\.(\d+)\.(.+)$", name)
        if not match:
            raise ValueError(f"Unexpected LoRA path: {name}")
        observed.append((int(match.group(1)), match.group(2)))
    lora = config["models"]["lora_shared"]
    expected = [(block, target) for block in lora["adapted_block_indices"] for target in lora["target_modules"]]
    if sorted(observed) != sorted(expected):
        raise ValueError("LoRA insertion set drift")
    return observed


def run_m2(config: dict[str, Any], run_dir: Path) -> None:
    require_stage(run_dir, "static")
    output = report_path(run_dir, "m2")
    if output.exists():
        raise FileExistsError(output)
    started_at, started = utc_now(), time.perf_counter()
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx_lm import load

    mx.reset_peak_memory()
    seed = config["evaluation"]["seeds"][0]
    rows = select_smoke_rows(load_train(config), config)
    prompt = load_prompt(config)
    spec = config["models"]["qwen_shared"]
    model, tokenizer = load(str(resolve_project(spec["local_path"])), lazy=False)
    model.freeze()
    model.eval()
    head = build_qwen_head(seed, spec["hidden_size"])
    wrapper = make_classification_wrapper(model, head)
    trainable = mlx_trainable(wrapper)
    if [name for name, _ in trainable if not name.startswith("head.")]:
        raise ValueError("M2 exposes non-head trainable parameters")
    count = sum(int(tensor.size) for _, tensor in trainable)
    if count != spec["head_parameters"]:
        raise ValueError("M2 head parameter count drift")
    initial_digest = mlx_tensor_digest(trainable)
    first_ids = qwen_row_ids(tokenizer, prompt, rows[0], config)
    initial_logits = wrapper(first_ids)
    mx.eval(initial_logits)
    initial_logits_digest = mlx_tensor_digest([("logits", initial_logits)])
    pooled_shape = [1, spec["hidden_size"]]
    optimizer = optim.AdamW(learning_rate=spec["head_learning_rate"], weight_decay=spec["head_weight_decay"])
    loss_and_grad = nn.value_and_grad(wrapper, classification_loss)
    losses: list[float] = []
    for row in rows[:2]:
        ids = qwen_row_ids(tokenizer, prompt, row, config)
        targets = mx.array([row["labels"]], dtype=mx.float32)
        loss, grads = loss_and_grad(wrapper, ids, targets)
        optimizer.update(wrapper.head, grads["head"])
        mx.eval(loss, wrapper.head.parameters(), optimizer.state)
        value = float(loss.item())
        if not (value == value and value < float("inf")):
            raise ValueError("M2 non-finite loss")
        losses.append(value)
    final_digest = mlx_tensor_digest(mlx_trainable(wrapper))
    if initial_digest == final_digest:
        raise ValueError("M2 head did not update")
    report = {
        "status": "Passed", "experiment_id": "EXP-050", "model_condition": "M2",
        "accessed_splits": ["train"], "validation_split_accessed": False, "test_split_accessed": False,
        "optimizer_steps": 2, "batch_size": 1, "pooled_shape": pooled_shape, "logit_shape": [1, 6],
        "finite_losses": losses, "trainable_parameter_count": count,
        "head_initial_sha256": initial_digest, "head_final_sha256": final_digest,
        "initial_logits_sha256": initial_logits_digest, "qwen_parameters_frozen": True,
        "peak_memory_gb": float(mx.get_peak_memory() / 1e9),
        "packages": package_versions(("mlx", "mlx-lm", "transformers")),
        "performance_metrics_computed": False, "raw_text_stored_publicly": False,
    }
    if report["peak_memory_gb"] > config["preflight"]["max_peak_memory_gb"]:
        raise MemoryError("M2 peak memory exceeded budget")
    write_json(output, report)
    record_stage(run_dir, "m2", "Passed", started_at, time.perf_counter() - started)
    del wrapper, head, model, tokenizer
    gc.collect()
    mx.clear_cache()


def run_m3(config: dict[str, Any], run_dir: Path) -> None:
    require_stage(run_dir, "static", "m2")
    output = report_path(run_dir, "m3")
    if output.exists():
        raise FileExistsError(output)
    started_at, started = utc_now(), time.perf_counter()
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx_lm import load
    from mlx_lm.tuner import linear_to_lora_layers
    from mlx_lm.tuner.trainer import grad_checkpoint

    mx.reset_peak_memory()
    seed = config["evaluation"]["seeds"][0]
    rows = select_smoke_rows(load_train(config), config)
    prompt = load_prompt(config)
    spec = config["models"]["qwen_shared"]
    lora = config["models"]["lora_shared"]
    model, tokenizer = load(str(resolve_project(spec["local_path"])), lazy=False)
    model.freeze()
    model.eval()
    head = build_qwen_head(seed, spec["hidden_size"])
    head_initial_digest = mlx_tensor_digest(mlx_trainable(head))
    m2 = json.loads(report_path(run_dir, "m2").read_text(encoding="utf-8"))
    if head_initial_digest != m2["head_initial_sha256"]:
        raise ValueError("M2/M3 matched head initialization failed")
    first_ids = qwen_row_ids(tokenizer, prompt, rows[0], config)
    wrapper = make_classification_wrapper(model, head)
    base_logits = wrapper(first_ids)
    mx.eval(base_logits)
    base_logits_digest = mlx_tensor_digest([("logits", base_logits)])
    if base_logits_digest != m2["initial_logits_sha256"]:
        raise ValueError("M2/M3 zero-step logits differ before LoRA insertion")

    mx.random.seed(seed + 100000)
    linear_to_lora_layers(model, lora["num_layers"], {
        "rank": lora["rank"], "scale": lora["scale"], "dropout": lora["dropout"], "keys": lora["target_modules"]
    })
    observed = insertion_contract(model, config)
    lora_items = mlx_trainable(model)
    lora_count = sum(int(tensor.size) for _, tensor in lora_items)
    if lora_count != lora["trainable_parameters"]:
        raise ValueError("M3 LoRA parameter count drift")
    lora_initial_digest = mlx_tensor_digest(lora_items)
    converted_logits = wrapper(first_ids)
    mx.eval(converted_logits)
    zero_step_difference = float(mx.max(mx.abs(base_logits - converted_logits)).item())
    if zero_step_difference != 0.0:
        raise ValueError("M3 initial LoRA delta is not exactly zero")
    trainable = mlx_trainable(wrapper)
    total = sum(int(tensor.size) for _, tensor in trainable)
    if total != lora["classification_total_trainable_parameters"]:
        raise ValueError("M3 total trainable parameter count drift")
    grad_checkpoint(model.layers[0])
    model.train()
    head_optimizer = optim.AdamW(learning_rate=spec["head_learning_rate"], weight_decay=spec["head_weight_decay"])
    lora_optimizer = optim.AdamW(learning_rate=lora["learning_rate"], weight_decay=lora["weight_decay"])
    loss_and_grad = nn.value_and_grad(wrapper, classification_loss)
    losses: list[float] = []
    for row in rows[:2]:
        ids = qwen_row_ids(tokenizer, prompt, row, config)
        targets = mx.array([row["labels"]], dtype=mx.float32)
        loss, grads = loss_and_grad(wrapper, ids, targets)
        lora_optimizer.update(wrapper.backbone, grads["backbone"])
        head_optimizer.update(wrapper.head, grads["head"])
        mx.eval(loss, wrapper.trainable_parameters(), lora_optimizer.state, head_optimizer.state)
        value = float(loss.item())
        if not (value == value and value < float("inf")):
            raise ValueError("M3 non-finite loss")
        losses.append(value)
    head_final_digest = mlx_tensor_digest(mlx_trainable(head))
    lora_final_items = mlx_trainable(model)
    lora_final_digest = mlx_tensor_digest(lora_final_items)
    nonzero_b = sum(bool(mx.any(tensor != 0).item()) for name, tensor in lora_final_items if name.endswith("lora_b"))
    if head_final_digest == head_initial_digest or lora_final_digest == lora_initial_digest or nonzero_b == 0:
        raise ValueError("M3 head or LoRA did not update")
    peak = float(mx.get_peak_memory() / 1e9)
    if peak > config["preflight"]["max_peak_memory_gb"]:
        raise MemoryError("M3 peak memory exceeded budget")
    report = {
        "status": "Passed", "experiment_id": "EXP-050", "model_condition": "M3",
        "accessed_splits": ["train"], "validation_split_accessed": False, "test_split_accessed": False,
        "optimizer_steps": 2, "batch_size": 1, "finite_losses": losses,
        "insertion_count": len(observed), "adapted_blocks": sorted(set(block for block, _ in observed)),
        "target_modules": lora["target_modules"], "lora_parameter_count": lora_count,
        "head_parameter_count": spec["head_parameters"], "total_trainable_parameter_count": total,
        "head_initial_sha256": head_initial_digest, "head_final_sha256": head_final_digest,
        "lora_initial_sha256": lora_initial_digest, "lora_final_sha256": lora_final_digest,
        "initial_logits_sha256": base_logits_digest, "zero_step_max_abs_logit_difference": zero_step_difference,
        "nonzero_lora_b_tensors_after_training": nonzero_b, "base_parameters_frozen": True,
        "separate_head_and_lora_optimizers": True, "gradient_checkpointing": True,
        "peak_memory_gb": peak, "packages": package_versions(("mlx", "mlx-lm", "transformers")),
        "performance_metrics_computed": False, "raw_text_stored_publicly": False,
    }
    write_json(output, report)
    record_stage(run_dir, "m3", "Passed", started_at, time.perf_counter() - started)
    del wrapper, head, model, tokenizer
    gc.collect()
    mx.clear_cache()


def m4_sequence(tokenizer: Any, prompt: dict[str, Any], row: dict[str, Any], config: dict[str, Any]) -> tuple[list[int], list[int], list[float]]:
    from strict_multilabel_parser import canonical_target
    prefix = qwen_prompt_ids(tokenizer, prompt, row["text"], config["prompt"]["max_sequence_length"])
    target = canonical_target(row["labels"], tuple(config["data"]["labels"]))
    full = normalize_token_ids(
        tokenizer.apply_chat_template(
            messages(prompt, row["text"]) + [{"role": "assistant", "content": target}],
            tokenize=True, return_dict=False, enable_thinking=False,
        )
    )
    if full[: len(prefix)] != prefix:
        raise ValueError("M4 prompt/full token prefix mismatch")
    if len(full) > config["prompt"]["max_sequence_length"]:
        raise ValueError("M4 full train sequence exceeds max length")
    inputs, targets = full[:-1], full[1:]
    weights = [0.0] * (len(prefix) - 1) + [1.0] * (len(full) - len(prefix))
    if len(weights) != len(targets) or sum(weights) <= 1:
        raise ValueError("M4 assistant-only loss mask drift")
    return inputs, targets, weights


def m4_loss(model: Any, inputs: Any, targets: Any, weights: Any) -> Any:
    import mlx.core as mx
    import mlx.nn as nn
    logits = model(inputs).astype(mx.float32)
    losses = nn.losses.cross_entropy(logits, targets, reduction="none")
    return mx.sum(losses * weights) / mx.sum(weights)


def run_m4(config: dict[str, Any], run_dir: Path) -> None:
    require_stage(run_dir, "static", "m3")
    output = report_path(run_dir, "m4")
    if output.exists():
        raise FileExistsError(output)
    started_at, started = utc_now(), time.perf_counter()
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"})
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx_lm import generate, load
    from mlx_lm.sample_utils import make_sampler
    from mlx_lm.tuner import linear_to_lora_layers
    from mlx_lm.tuner.trainer import grad_checkpoint
    from strict_multilabel_parser import parse_output

    mx.reset_peak_memory()
    seed = config["evaluation"]["seeds"][0]
    rows = select_smoke_rows(load_train(config), config)
    prompt = load_prompt(config)
    spec = config["models"]["qwen_shared"]
    lora = config["models"]["lora_shared"]
    model, tokenizer = load(str(resolve_project(spec["local_path"])), lazy=False)
    model.freeze()
    mx.random.seed(seed + 100000)
    linear_to_lora_layers(model, lora["num_layers"], {
        "rank": lora["rank"], "scale": lora["scale"], "dropout": lora["dropout"], "keys": lora["target_modules"]
    })
    observed = insertion_contract(model, config)
    initial_items = mlx_trainable(model)
    count = sum(int(tensor.size) for _, tensor in initial_items)
    initial_digest = mlx_tensor_digest(initial_items)
    m3 = json.loads(report_path(run_dir, "m3").read_text(encoding="utf-8"))
    if initial_digest != m3["lora_initial_sha256"]:
        raise ValueError("M3/M4 LoRA initialization mismatch")
    if count != lora["trainable_parameters"]:
        raise ValueError("M4 trainable parameter count drift")
    grad_checkpoint(model.layers[0])
    model.train()
    optimizer = optim.AdamW(learning_rate=lora["learning_rate"], weight_decay=lora["weight_decay"])
    loss_and_grad = nn.value_and_grad(model, m4_loss)
    losses: list[float] = []
    supervised_token_counts: list[int] = []
    for row in rows[:2]:
        input_ids, target_ids, mask = m4_sequence(tokenizer, prompt, row, config)
        inputs = mx.array([input_ids], dtype=mx.int32)
        targets = mx.array([target_ids], dtype=mx.int32)
        weights = mx.array([mask], dtype=mx.float32)
        loss, grads = loss_and_grad(model, inputs, targets, weights)
        optimizer.update(model, grads)
        mx.eval(loss, model.trainable_parameters(), optimizer.state)
        value = float(loss.item())
        if not (value == value and value < float("inf")):
            raise ValueError("M4 non-finite loss")
        losses.append(value)
        supervised_token_counts.append(int(sum(mask)))
    final_items = mlx_trainable(model)
    final_digest = mlx_tensor_digest(final_items)
    nonzero_b = sum(bool(mx.any(tensor != 0).item()) for name, tensor in final_items if name.endswith("lora_b"))
    if initial_digest == final_digest or nonzero_b == 0:
        raise ValueError("M4 LoRA did not update")

    model.eval()
    sampler = make_sampler(temp=0.0)
    parsed: list[dict[str, Any]] = []
    private_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows[: config["preflight"]["generation_rows"]]):
        prefix = qwen_prompt_ids(tokenizer, prompt, row["text"], config["prompt"]["max_sequence_length"])
        raw = generate(model, tokenizer, prompt=prefix, max_tokens=config["models"]["m4"]["generation"]["max_new_tokens"], sampler=sampler, verbose=False)
        result = parse_output(raw, tuple(config["data"]["labels"]))
        parsed.append(result)
        private_rows.append({"index": index, "raw_output": raw, "parsed": result})
    private_path = PRIVATE_DIR / "m4-generations.jsonl"
    if private_path.exists():
        raise FileExistsError(private_path)
    private_path.write_text("".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in private_rows), encoding="utf-8")
    os.chmod(private_path, 0o600)
    errors = Counter(result["error"] or "valid" for result in parsed)
    peak = float(mx.get_peak_memory() / 1e9)
    if peak > config["preflight"]["max_peak_memory_gb"]:
        raise MemoryError("M4 peak memory exceeded budget")
    report = {
        "status": "Passed", "experiment_id": "EXP-050", "model_condition": "M4",
        "accessed_splits": ["train"], "validation_split_accessed": False, "test_split_accessed": False,
        "optimizer_steps": 2, "batch_size": 1, "finite_losses": losses,
        "supervised_token_counts": supervised_token_counts, "prompt_loss_masked": True,
        "insertion_count": len(observed), "trainable_parameter_count": count,
        "lora_initial_sha256": initial_digest, "lora_final_sha256": final_digest,
        "nonzero_lora_b_tensors_after_training": nonzero_b, "base_parameters_frozen": True,
        "gradient_checkpointing": True, "generation_rows": len(parsed),
        "generation_retries": 0, "parser_valid_count": sum(result["valid"] for result in parsed),
        "parser_outcome_counts": dict(sorted(errors.items())),
        "private_generation_sha256": sha256(private_path), "raw_generation_stored_publicly": False,
        "peak_memory_gb": peak, "packages": package_versions(("mlx", "mlx-lm", "transformers")),
        "performance_metrics_computed": False, "raw_text_stored_publicly": False,
    }
    write_json(output, report)
    record_stage(run_dir, "m4", "Passed", started_at, time.perf_counter() - started)
    del model, tokenizer
    gc.collect()
    mx.clear_cache()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("static", "m1", "m2", "m3", "m4"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args()
    config_path = args.config.resolve()
    run_dir = args.run_dir.resolve()
    config = load_config(config_path)
    stages = {"static": run_static, "m1": run_m1, "m2": run_m2, "m3": run_m3, "m4": run_m4}
    if args.stage == "static":
        stages[args.stage](config_path, config, run_dir)
    else:
        stages[args.stage](config, run_dir)


if __name__ == "__main__":
    main()
