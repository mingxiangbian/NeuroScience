#!/usr/bin/env python3
"""Run the train-only EXP-046 Qwen batch-equivalence gate."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
from typing import Any, Iterable, Sequence


EXPERIMENT_ID = "EXP-046"
INVALID_LABEL = "__invalid__"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
CONFIG_PATH = SCRIPT_DIR / "config.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("initialize")
    infer = subparsers.add_parser("infer")
    infer.add_argument("--mode", required=True)
    subparsers.add_parser("aggregate")
    return parser.parse_args()


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
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def atomic_json(path: Path, value: Any, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if private:
        os.chmod(temporary, 0o600)
    temporary.replace(path)


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]], *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    if private:
        os.chmod(temporary, 0o600)
    temporary.replace(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        return [json.loads(line) for line in source]


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("EXP-046 identity drift")
    if config.get("tier") != "Minor" or config.get("status") != "Registered":
        raise ValueError("EXP-046 must remain a registered Minor experiment")
    if config["data"]["split"] != "train":
        raise ValueError("EXP-046 must remain train-only")
    if config["data"]["validation_access"] or config["data"]["test_access"]:
        raise ValueError("Validation/test access is forbidden")
    generation = config["generation"]
    if not generation["deterministic"] or generation["temperature"] != 0.0 or not generation["reasoning"]:
        raise ValueError("EXP-046 must remain greedy reasoning-on")
    if len(generation["modes"]) != len(set(generation["modes"])):
        raise ValueError("Generation modes are not unique")
    for key in ("parser", "prompt", "requirements"):
        path = resolve_project_path(config["implementation"][f"{key}_path"])
        if sha256_file(path) != config["implementation"][f"{key}_sha256"]:
            raise ValueError(f"Frozen {key} hash drift")
    manifest = resolve_project_path(config["model"]["manifest_path"])
    if sha256_file(manifest) != config["model"]["manifest_sha256"]:
        raise ValueError("Frozen model manifest hash drift")
    return config


def run_dir(config: dict[str, Any]) -> Path:
    return resolve_project_path(config["run_dir"])


def private_root(config: dict[str, Any]) -> Path:
    return resolve_project_path(config["private_root"])


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    return {"commit": commit, "dirty": bool(status), "dirty_path_count": len(status)}


def package_versions() -> dict[str, str]:
    names = ("mlx", "mlx-lm", "numpy", "safetensors", "tokenizers", "transformers")
    return {"python": platform.python_version(), **{name: importlib.metadata.version(name) for name in names}}


def load_train(config: dict[str, Any]) -> list[dict[str, Any]]:
    path = resolve_project_path(config["data"]["train_path"])
    if sha256_file(path) != config["data"]["train_sha256"]:
        raise ValueError("Frozen train hash drift")
    rows = read_jsonl(path)
    if len(rows) != config["data"]["train_rows"]:
        raise ValueError("Frozen train row count drift")
    labels = set(config["data"]["labels"])
    seen: set[str] = set()
    for row in rows:
        if row.get("protocol_id") != config["data"]["protocol_id"] or row.get("label") not in labels:
            raise ValueError("Train schema or ontology drift")
        if row["sample_id"] in seen:
            raise ValueError("Duplicate train sample ID")
        seen.add(row["sample_id"])
        target = row["views"]["target_only"]["target"]
        if not isinstance(target, str) or not target:
            raise ValueError("Invalid train target")
    return rows


def load_prompt(config: dict[str, Any]) -> dict[str, Any]:
    prompt = json.loads(
        resolve_project_path(config["implementation"]["prompt_path"]).read_text(encoding="utf-8")
    )
    if list(prompt["label_definitions"]) != config["data"]["labels"]:
        raise ValueError("Prompt ontology order drift")
    return prompt


def prompt_messages(config: dict[str, Any], prompt: dict[str, Any], row: dict[str, Any]) -> list[dict[str, str]]:
    definitions = "\n".join(
        f"- {label}: {prompt['label_definitions'][label]}" for label in config["data"]["labels"]
    )
    system = prompt["system_template"].format(
        label_definitions=definitions,
        output_schema=prompt["output_schema"],
    )
    user = prompt["target_only_template"].format(target=row["views"]["target_only"]["target"])
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def messages_sha256(messages: list[dict[str, str]]) -> str:
    payload = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(payload)


def require_token_ids(value: Any) -> list[int]:
    tokens = list(value)
    if not tokens or not all(isinstance(token, int) and not isinstance(token, bool) for token in tokens):
        raise TypeError("Chat template must return a non-empty sequence of integer token IDs")
    return tokens


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


def allocate_quotas(counts: dict[str, int], total: int, labels: list[str]) -> dict[str, int]:
    population = sum(counts.values())
    if total < len(labels) or total > population:
        raise ValueError("Invalid sample size")
    raw = {label: total * counts[label] / population for label in labels}
    quotas = {label: max(1, math.floor(raw[label])) for label in labels}
    while sum(quotas.values()) > total:
        choices = [label for label in labels if quotas[label] > 1]
        label = min(choices, key=lambda item: (raw[item] - quotas[item], labels.index(item)))
        quotas[label] -= 1
    while sum(quotas.values()) < total:
        label = max(labels, key=lambda item: (raw[item] - quotas[item], -labels.index(item)))
        quotas[label] += 1
    return quotas


def select_representative_rows(
    measured: list[dict[str, Any]], quotas: dict[str, int], labels: list[str], namespace: str
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for label in labels:
        values = [row for row in measured if row["label"] == label]
        values.sort(
            key=lambda row: (
                row["prompt_tokens"],
                sha256_text(f"{namespace}:length-tie:{row['sample_id']}"),
            )
        )
        quota = quotas[label]
        indices = [min(len(values) - 1, ((2 * rank + 1) * len(values)) // (2 * quota)) for rank in range(quota)]
        if len(set(indices)) != quota:
            raise ValueError(f"Selection duplicated a {label} row")
        selected.extend(values[index] for index in indices)
    selected.sort(key=lambda row: sha256_text(f"{namespace}:native-order:{row['sample_id']}"))
    for index, row in enumerate(selected):
        row["selection_index"] = index
        row["selector_sha256"] = sha256_text(f"{namespace}:sample:{row['sample_id']}")
    return selected


def mode_spec(config: dict[str, Any], mode: str, selection: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, str]:
    if mode not in config["generation"]["modes"]:
        raise ValueError(f"Unknown mode: {mode}")
    if mode.startswith("singleton"):
        return list(selection), 1, "selection_hash"
    if mode == "batch8-length-stress":
        ordered = sorted(selection, key=lambda row: (row["prompt_tokens"], row["selector_sha256"]))
        return ordered, config["generation"]["batch_size"], "prompt_length_ascending"
    return list(selection), config["generation"]["batch_size"], "selection_hash"


def compare_records(left: Sequence[dict[str, Any]], right: Sequence[dict[str, Any]]) -> dict[str, Any]:
    left_map = {row["selection_index"]: row for row in left}
    right_map = {row["selection_index"]: row for row in right}
    if set(left_map) != set(right_map) or not left_map:
        raise ValueError("Comparison row identities differ")
    indices = sorted(left_map)
    raw_equal = sum(left_map[index]["raw_output_sha256"] == right_map[index]["raw_output_sha256"] for index in indices)
    label_equal = sum(left_map[index]["prediction"] == right_map[index]["prediction"] for index in indices)
    parser_equal = sum(left_map[index]["parse"] == right_map[index]["parse"] for index in indices)
    return {
        "final_label_equal_count": label_equal,
        "final_label_equal_rate": label_equal / len(indices),
        "parser_state_equal_count": parser_equal,
        "parser_state_equal_rate": parser_equal / len(indices),
        "raw_output_equal_count": raw_equal,
        "raw_output_equal_rate": raw_equal / len(indices),
        "rows": len(indices),
    }


def choose_execution_protocol(config: dict[str, Any], comparisons: dict[str, dict[str, Any]]) -> dict[str, Any]:
    decision = config["decision"]
    batch_replay = comparisons["batch8_replay"]["final_label_equal_rate"]
    composition = comparisons["batch8_composition"]["final_label_equal_rate"]
    singleton = comparisons["singleton_replay"]["final_label_equal_rate"]
    if (
        batch_replay >= decision["batch_replay_label_agreement_min"]
        and composition >= decision["batch_composition_label_agreement_min"]
    ):
        selected = "batch8_fixed_order"
        gate = "Passed"
        requirements = [
            "freeze validation row order",
            "batch_size=completion_batch_size=prefill_batch_size=8",
            "repeat the train-only replay after each adapter is trained and before dev access",
        ]
    elif singleton >= decision["singleton_replay_label_agreement_min"]:
        selected = "singleton"
        gate = "Passed"
        requirements = [
            "batch_size=completion_batch_size=prefill_batch_size=1",
            "repeat the train-only replay after each adapter is trained and before dev access",
        ]
    else:
        selected = decision["fallback_if_no_stable_reasoning_on_mode"]
        gate = "Blocked"
        requirements = ["register and run a reasoning-off replay gate before Stage 5 dev evaluation"]
    return {
        "gate_status": gate,
        "recommended_execution_protocol": selected,
        "requirements": requirements,
        "rules_applied": decision,
    }


def load_parser(config: dict[str, Any]):
    path = resolve_project_path(config["implementation"]["parser_path"])
    spec = importlib.util.spec_from_file_location("exp046_frozen_parser", path)
    if not spec or not spec.loader:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.parse_final_label


def load_run(config: dict[str, Any]) -> dict[str, Any]:
    path = run_dir(config) / "run.json"
    if not path.is_file():
        raise FileNotFoundError("Run is not initialized")
    return json.loads(path.read_text(encoding="utf-8"))


def save_run(config: dict[str, Any], run: dict[str, Any]) -> None:
    atomic_json(run_dir(config) / "run.json", run)


def command_string() -> str:
    return f"{sys.executable} {display_path(Path(__file__))} " + " ".join(sys.argv[1:])


def update_stage(config: dict[str, Any], name: str, artifact_path: Path, elapsed: float) -> None:
    run = load_run(config)
    if name in run["stages"]:
        raise FileExistsError(f"Stage already recorded: {name}")
    run["command_history"].append(command_string())
    run["stages"][name] = {
        "artifact": {
            "bytes": artifact_path.stat().st_size,
            "path": display_path(artifact_path),
            "sha256": sha256_file(artifact_path),
        },
        "completed_at_utc": utc_now(),
        "duration_seconds": elapsed,
        "status": "Passed",
    }
    run["status"] = "Running"
    save_run(config, run)


def initialize(config: dict[str, Any]) -> None:
    started_at = utc_now()
    public = run_dir(config)
    private = private_root(config)
    if (public.exists() and any(public.iterdir())) or (private.exists() and any(private.iterdir())):
        raise FileExistsError("EXP-046 output directory is not empty")
    public.mkdir(parents=True, exist_ok=True)
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    started = time.perf_counter()
    rows = load_train(config)
    prompt = load_prompt(config)
    os.environ.update(
        {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    )
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        resolve_project_path(config["model"]["local_path"]), local_files_only=True
    )
    measured = []
    for row in rows:
        messages = prompt_messages(config, prompt, row)
        prompt_ids = require_token_ids(
            tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                enable_thinking=True,
                tokenize=True,
                return_dict=False,
            )
        )
        measured.append(
            {
                "label": row["label"],
                "messages": messages,
                "prompt_sha256": sha256_text(json.dumps(prompt_ids, separators=(",", ":"))),
                "prompt_tokens": len(prompt_ids),
                "row": row,
                "sample_id": row["sample_id"],
            }
        )
    populations = Counter(row["label"] for row in measured)
    quotas = allocate_quotas(dict(populations), config["sampling"]["rows"], config["data"]["labels"])
    selected = select_representative_rows(
        measured, quotas, config["data"]["labels"], config["sampling"]["seed_namespace"]
    )
    if len(selected) != config["sampling"]["rows"]:
        raise ValueError("Selection row count drift")
    native_groups = {
        frozenset(row["selection_index"] for row in selected[start : start + config["generation"]["batch_size"]])
        for start in range(0, len(selected), config["generation"]["batch_size"])
    }
    stressed = sorted(selected, key=lambda row: (row["prompt_tokens"], row["selector_sha256"]))
    stress_groups = {
        frozenset(row["selection_index"] for row in stressed[start : start + config["generation"]["batch_size"]])
        for start in range(0, len(stressed), config["generation"]["batch_size"])
    }
    if native_groups == stress_groups:
        raise ValueError("Length-stress ordering did not change batch composition")
    atomic_jsonl(private / "selection.jsonl", selected, private=True)
    selection_material = "\n".join(row["selector_sha256"] for row in selected)
    sample_summary = {
        "accessed_splits": ["train"],
        "experiment_id": EXPERIMENT_ID,
        "native_and_stress_batch_partitions_differ": True,
        "population_label_counts": dict(populations),
        "raw_ids_stored_publicly": False,
        "raw_text_stored_publicly": False,
        "sample_label_counts": dict(Counter(row["label"] for row in selected)),
        "sample_prompt_tokens": numeric_summary([row["prompt_tokens"] for row in selected]),
        "sample_rows": len(selected),
        "selection_digest_sha256": sha256_text(selection_material),
        "selection_method": config["sampling"]["selection"],
        "status": "Passed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
    }
    sample_path = public / "sample_summary.json"
    atomic_json(sample_path, sample_summary)
    implementation = {
        "config_sha256": sha256_file(CONFIG_PATH),
        "runner_sha256": sha256_file(Path(__file__)),
        "verifier_sha256": sha256_file(SCRIPT_DIR / "verify_batch_equivalence.py"),
        "test_sha256": sha256_file(SCRIPT_DIR / "test_batch_equivalence.py"),
    }
    run = {
        "accessed_splits": ["train"],
        "command_history": [command_string()],
        "data": {
            "labels": config["data"]["labels"],
            "protocol_id": config["data"]["protocol_id"],
            "sample_rows": len(selected),
            "split": "train",
            "train_rows": len(rows),
            "train_sha256": config["data"]["train_sha256"],
        },
        "environment": package_versions(),
        "experiment_id": EXPERIMENT_ID,
        "git": git_metadata(),
        "implementation": implementation,
        "model": config["model"],
        "rq_ids": config["rq_ids"],
        "stage": config["stage"],
        "stages": {
            "initialize": {
                "artifact": {
                    "bytes": sample_path.stat().st_size,
                    "path": display_path(sample_path),
                    "sha256": sha256_file(sample_path),
                },
                "completed_at_utc": utc_now(),
                "duration_seconds": time.perf_counter() - started,
                "status": "Passed",
            }
        },
        "started_at_utc": started_at,
        "status": "Initialized",
        "test_split_accessed": False,
        "tier": config["tier"],
        "validation_split_accessed": False,
        "warnings": [
            "This Minor run measures generation reproducibility and does not compute classification performance.",
            "Gold labels are used only for train-sample stratification.",
        ],
    }
    save_run(config, run)
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "sample_rows": len(selected), "status": "Initialized"}))


def infer(config: dict[str, Any], mode: str) -> None:
    run = load_run(config)
    if run["stages"].get("initialize", {}).get("status") != "Passed":
        raise RuntimeError("Initialize must pass before inference")
    public_path = run_dir(config) / f"mode-{mode}.json"
    private_path = private_root(config) / f"mode-{mode}.jsonl"
    if public_path.exists() or private_path.exists():
        raise FileExistsError(f"Mode output already exists: {mode}")
    selection = read_jsonl(private_root(config) / "selection.jsonl")
    ordered, batch_size, order_strategy = mode_spec(config, mode, selection)
    started = time.perf_counter()
    os.environ.update(
        {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    )
    import mlx.core as mx
    from mlx_lm import batch_generate, load
    from mlx_lm.sample_utils import make_sampler

    parse_final_label = load_parser(config)
    model, tokenizer = load(str(resolve_project_path(config["model"]["local_path"])))
    sampler = make_sampler(temp=config["generation"]["temperature"])
    records: list[dict[str, Any]] = []
    batch_stats: list[dict[str, Any]] = []
    for start in range(0, len(ordered), batch_size):
        batch_rows = ordered[start : start + batch_size]
        messages = [row["messages"] for row in batch_rows]
        prompts = [
            require_token_ids(
                tokenizer.apply_chat_template(
                    value,
                    add_generation_prompt=True,
                    enable_thinking=True,
                    tokenize=True,
                    return_dict=False,
                )
            )
            for value in messages
        ]
        generated = batch_generate(
            model,
            tokenizer,
            prompts,
            max_tokens=config["generation"]["max_new_tokens"],
            sampler=sampler,
            completion_batch_size=len(batch_rows),
            prefill_batch_size=len(batch_rows),
            prefill_step_size=config["generation"]["prefill_step_size"],
            verbose=False,
        )
        stats = asdict(generated.stats)
        stats["batch_rows"] = len(batch_rows)
        stats["execution_batch_index"] = start // batch_size
        batch_stats.append(stats)
        for offset, (source, messages_value, prompt_ids, output) in enumerate(
            zip(batch_rows, messages, prompts, generated.texts)
        ):
            parsed = parse_final_label(output, thinking=True, labels=config["data"]["labels"])
            records.append(
                {
                    "batch_stats": stats,
                    "execution_position": start + offset,
                    "message_sha256": messages_sha256(messages_value),
                    "mode": mode,
                    "parse": parsed.to_dict(),
                    "prediction": parsed.label if parsed.valid else INVALID_LABEL,
                    "prompt_sha256": sha256_text(json.dumps(prompt_ids, separators=(",", ":"))),
                    "prompt_tokens": len(prompt_ids),
                    "raw_output": output,
                    "raw_output_sha256": sha256_text(output),
                    "sample_id": source["sample_id"],
                    "selection_index": source["selection_index"],
                    "generated_tokens": len(tokenizer.encode(output, add_special_tokens=False)),
                }
            )
        print(
            json.dumps(
                {
                    "completed": min(start + len(batch_rows), len(ordered)),
                    "mode": mode,
                    "total": len(ordered),
                }
            ),
            flush=True,
        )
    elapsed = time.perf_counter() - started
    records.sort(key=lambda row: row["selection_index"])
    valid = sum(row["parse"]["valid"] for row in records)
    peak_memory_gb = max(float(row["peak_memory"]) for row in batch_stats)
    elapsed_with_prior_stages = elapsed + sum(
        float(stage.get("duration_seconds", 0.0)) for stage in run["stages"].values()
    )
    if peak_memory_gb > config["resource_budget"]["peak_memory_gb_max"]:
        raise RuntimeError("Mode exceeded the frozen memory gate")
    if elapsed_with_prior_stages > config["resource_budget"]["local_wall_time_minutes_max"] * 60:
        raise RuntimeError("EXP-046 exceeded the frozen wall-time gate")
    atomic_jsonl(private_path, records, private=True)
    summary = {
        "accessed_splits": ["train"],
        "api_cost_usd": 0,
        "batch_size": batch_size,
        "batches": len(batch_stats),
        "command_elapsed_seconds": elapsed,
        "experiment_id": EXPERIMENT_ID,
        "generated_tokens": numeric_summary([row["generated_tokens"] for row in records]),
        "mode": mode,
        "order_strategy": order_strategy,
        "parser_error_counts": dict(
            Counter(row["parse"]["error"] for row in records if row["parse"]["error"])
        ),
        "parser_valid_count": valid,
        "parser_valid_rate": valid / len(records),
        "peak_memory_gb": peak_memory_gb,
        "performance_metrics_computed": False,
        "private_output_sha256": sha256_file(private_path),
        "prompt_tokens": numeric_summary([row["prompt_tokens"] for row in records]),
        "raw_output_stored_publicly": False,
        "rows": len(records),
        "status": "Passed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
    }
    atomic_json(public_path, summary)
    update_stage(config, f"infer_{mode}", public_path, elapsed)
    del model, tokenizer
    gc.collect()
    mx.clear_cache()
    print(json.dumps({"elapsed_seconds": elapsed, "mode": mode, "status": "Passed"}))


def aggregate(config: dict[str, Any]) -> None:
    run = load_run(config)
    required = {f"infer_{mode}" for mode in config["generation"]["modes"]}
    if any(run["stages"].get(name, {}).get("status") != "Passed" for name in required):
        raise RuntimeError("All five inference modes must pass before aggregation")
    output = run_dir(config) / "aggregate.json"
    report_path = run_dir(config) / "REPORT.md"
    if output.exists() or report_path.exists():
        raise FileExistsError("Aggregate output already exists")
    started = time.perf_counter()
    records = {
        mode: read_jsonl(private_root(config) / f"mode-{mode}.jsonl")
        for mode in config["generation"]["modes"]
    }
    prompt_contract_ok = all(
        [row["message_sha256"] for row in records[mode]]
        == [row["message_sha256"] for row in records["singleton-r1"]]
        and [row["prompt_sha256"] for row in records[mode]]
        == [row["prompt_sha256"] for row in records["singleton-r1"]]
        for mode in config["generation"]["modes"]
    )
    if not prompt_contract_ok:
        raise ValueError("Prompt identities drifted across modes")
    comparisons = {
        "singleton_replay": compare_records(records["singleton-r1"], records["singleton-r2"]),
        "batch8_replay": compare_records(records["batch8-r1"], records["batch8-r2"]),
        "batch8_composition": compare_records(
            records["batch8-r1"], records["batch8-length-stress"]
        ),
        "singleton_vs_batch8": compare_records(records["singleton-r1"], records["batch8-r1"]),
    }
    decision = choose_execution_protocol(config, comparisons)
    aggregate_value = {
        "accessed_splits": ["train"],
        "comparison_semantics": "same prompt, final labels include __invalid__ for strict-parse failure",
        "comparisons": comparisons,
        "completed_at_utc": utc_now(),
        "decision": decision,
        "experiment_id": EXPERIMENT_ID,
        "formal_generations": sum(len(values) for values in records.values()),
        "gold_labels_used_for_performance": False,
        "performance_metrics_computed": False,
        "prompt_contract_identical_across_modes": True,
        "raw_outputs_stored_publicly": False,
        "status": "Passed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
    }
    atomic_json(output, aggregate_value)
    rows = []
    for name, value in comparisons.items():
        rows.append(
            f"| {name} | {value['final_label_equal_count']}/{value['rows']} "
            f"({value['final_label_equal_rate']:.3f}) | {value['raw_output_equal_count']}/{value['rows']} "
            f"({value['raw_output_equal_rate']:.3f}) |"
        )
    report = "\n".join(
        [
            "# EXP-046 Batch-Equivalence Gate",
            "",
            "Status: `Completed; awaiting independent verification`",
            "",
            "This train-only Minor experiment computed no classification performance and did not access validation/test.",
            "",
            "| Comparison | Final-label agreement | Raw-output agreement |",
            "| --- | ---: | ---: |",
            *rows,
            "",
            "## Frozen Decision",
            "",
            f"- Gate: `{decision['gate_status']}`",
            f"- Recommended execution protocol: `{decision['recommended_execution_protocol']}`",
            *[f"- Requirement: {item}" for item in decision["requirements"]],
            "",
            "## Boundary",
            "",
            "The result concerns runtime reproducibility only. It does not show that reasoning improves emotion recognition,",
            "does not validate generated reasoning as faithful, and does not authorize Stage 5 training or test access.",
            "",
        ]
    )
    report_path.write_text(report, encoding="utf-8")
    update_stage(config, "aggregate", output, time.perf_counter() - started)
    run = load_run(config)
    run["status"] = "Awaiting Independent Verification"
    run["completed_at_utc"] = utc_now()
    run["result"] = {
        "decision": decision,
        "formal_generations": aggregate_value["formal_generations"],
        "performance_metrics_computed": False,
    }
    run["report"] = {
        "path": display_path(report_path),
        "sha256": sha256_file(report_path),
    }
    save_run(config, run)
    print(json.dumps({"decision": decision, "status": run["status"]}))


def main() -> None:
    args = parse_args()
    config = load_config()
    if args.command == "initialize":
        initialize(config)
    elif args.command == "infer":
        infer(config, args.mode)
    else:
        aggregate(config)


if __name__ == "__main__":
    main()
