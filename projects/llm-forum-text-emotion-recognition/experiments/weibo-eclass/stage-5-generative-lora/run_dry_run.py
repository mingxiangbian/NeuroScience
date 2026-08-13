#!/usr/bin/env python3
"""Build the no-model EXP-047 training contract and dry-run artifacts."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
from typing import Any, Iterable

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["PYTHONNOUSERSITE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

EXPERIMENT_ID = "EXP-047"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
CONFIG_PATH = SCRIPT_DIR / "config.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EXP-047 no-model dry-run only")
    parser.add_argument("command", choices=["dry-run"])
    return parser.parse_args()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Project-relative path escapes project root: {value}")
    return path


def artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "bytes": path.stat().st_size,
        "path": display_path(path),
        "sha256": sha256_file(path),
    }


def expected_artifact(path_value: str, sha256_value: str) -> Path:
    path = resolve_project_path(path_value)
    if not path.is_file() or sha256_file(path) != sha256_value:
        raise ValueError(f"Frozen artifact drift: {path}")
    return path


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if (
        config.get("experiment_id") != EXPERIMENT_ID
        or config.get("tier") != "Major"
        or config.get("status") != "Registered"
        or config.get("stage") != "stage-5-generative-lora"
        or config["execution"].get("authorized") is not False
        or config["data"].get("test_access") is not False
    ):
        raise ValueError("EXP-047 must remain registered, unauthorized and test-closed")
    implementation = config["implementation"]
    for key in ("runner_sha256", "verifier_sha256", "test_sha256"):
        if implementation.get(key) in (None, "PENDING"):
            raise ValueError(f"Implementation hash is not frozen: {key}")
    bindings = (
        (implementation["runner_path"], implementation["runner_sha256"]),
        (implementation["verifier_path"], implementation["verifier_sha256"]),
        (implementation["test_path"], implementation["test_sha256"]),
        (config["paths"]["protocol"], config["paths"]["protocol_sha256"]),
    )
    for path_value, digest in bindings:
        expected_artifact(path_value, digest)
    if resolve_project_path(implementation["runner_path"]) != Path(__file__).resolve():
        raise ValueError("Frozen runner path does not resolve to this script")
    return config


def verify_environment(config: dict[str, Any]) -> dict[str, Any]:
    runtime = config["runtime"]
    python_path = Path(runtime["python_executable"])
    if not python_path.is_file() or not Path(sys.executable).samefile(python_path):
        raise ValueError(f"Use the frozen Python executable: {python_path}")
    packages = {
        name: platform.python_version() if name == "python" else importlib.metadata.version(name)
        for name in runtime["packages"]
    }
    if packages != runtime["packages"]:
        raise ValueError(f"Runtime package drift: {packages}")
    cli = Path(runtime["mlx_lora_cli"]["path"])
    if (
        not cli.is_file()
        or not os.access(cli, os.X_OK)
        or sha256_file(cli) != runtime["mlx_lora_cli"]["sha256"]
    ):
        raise ValueError("Frozen MLX-LM CLI drift")
    return {
        "mlx_lora_cli": artifact(cli),
        "offline_environment": True,
        "packages": packages,
        "python_executable": str(python_path),
    }


def verify_model_files(config: dict[str, Any]) -> dict[str, Any]:
    model = config["model"]
    manifest_path = expected_artifact(model["manifest_path"], model["manifest_sha256"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("repo_id") != model["repo_id"] or manifest.get("revision") != model["revision"]:
        raise ValueError("Model identity drift")
    model_root = resolve_project_path(model["local_path"])
    stream = hashlib.sha256()
    total_bytes = 0
    files = manifest["mlx_bf16"]["files"]
    for expected in files:
        path = model_root / expected["path"]
        observed = {
            "bytes": path.stat().st_size if path.is_file() else -1,
            "path": expected["path"],
            "sha256": sha256_file(path) if path.is_file() else None,
        }
        if observed != expected:
            raise ValueError(f"Model file drift: {path}")
        stream.update(
            f"{expected['path']}\0{expected['bytes']}\0{expected['sha256']}\n".encode("utf-8")
        )
        total_bytes += expected["bytes"]
    if len(files) != manifest["mlx_bf16"]["file_count"] or total_bytes != manifest["mlx_bf16"]["total_bytes"]:
        raise ValueError("Model manifest totals drift")
    return {
        "file_count": len(files),
        "files_manifest_sha256": stream.hexdigest(),
        "manifest": artifact(manifest_path),
        "model_weights_loaded": False,
        "total_bytes": total_bytes,
        "weight_files_hashed": True,
    }


def normalize_token_ids(value: Any) -> list[int]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, list) or any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        raise TypeError("Chat template must return one flat integer token sequence")
    return value


def percentile(values: Iterable[int], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Cannot summarize an empty sequence")
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def numeric_summary(values: list[int]) -> dict[str, Any]:
    return {
        "count": len(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "min": min(values),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
    }


def render_messages(config: dict[str, Any], prompt: dict[str, Any], row: dict[str, Any]) -> list[dict[str, str]]:
    labels = config["data"]["labels"]
    definitions = "\n".join(f"- {label}: {prompt['label_definitions'][label]}" for label in labels)
    system = prompt["system_template"].format(
        label_definitions=definitions,
        output_schema=prompt["output_schema"],
    )
    assistant = prompt["assistant_target_template"].replace("{label}", row["label"])
    if json.loads(assistant) != {"label": row["label"]}:
        raise ValueError("Assistant target violates strict JSON schema")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt["target_only_template"].format(target=row["views"]["target_only"]["target"])},
        {"role": "assistant", "content": assistant},
    ]


def build_prepared_train(config: dict[str, Any]) -> tuple[bytes, dict[str, Any], list[str]]:
    train_path = expected_artifact(config["data"]["train_path"], config["data"]["train_sha256"])
    prompt_path = expected_artifact(
        config["implementation"]["prompt_path"], config["implementation"]["prompt_sha256"]
    )
    prompt = json.loads(prompt_path.read_text(encoding="utf-8"))
    labels = config["data"]["labels"]
    if list(prompt["label_definitions"]) != labels:
        raise ValueError("Prompt label order drift")

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        resolve_project_path(config["model"]["local_path"]),
        local_files_only=True,
    )
    expected_fields = {
        "ambiguous_target",
        "context_available",
        "group_id",
        "label",
        "protocol_id",
        "sample_id",
        "schema_version",
        "views",
    }
    prepared: list[bytes] = []
    raw_targets: list[str] = []
    label_counts: Counter[str] = Counter()
    sample_ids: set[str] = set()
    group_ids: set[str] = set()
    token_lengths: list[int] = []
    supervised_lengths: list[int] = []
    target_stream = hashlib.sha256()
    wrapper = "<think>\n\n</think>\n\n"

    with train_path.open("r", encoding="utf-8") as source:
        for row_number, line in enumerate(source, start=1):
            row = json.loads(line)
            if set(row) != expected_fields or row.get("protocol_id") != config["data"]["protocol_id"]:
                raise ValueError(f"Frozen train schema drift at row {row_number}")
            if row["label"] not in labels or row["sample_id"] in sample_ids:
                raise ValueError(f"Label or sample identity drift at row {row_number}")
            if set(row["views"]) != {"previous_context", "target_only"} or set(row["views"]["target_only"]) != {"target"}:
                raise ValueError(f"Frozen view schema drift at row {row_number}")
            target = row["views"]["target_only"]["target"]
            if not isinstance(target, str) or not target:
                raise ValueError(f"Invalid target text at row {row_number}")
            messages = render_messages(config, prompt, row)
            token_ids = normalize_token_ids(tokenizer.apply_chat_template(messages, return_dict=False))
            prompt_ids = normalize_token_ids(
                tokenizer.apply_chat_template(
                    messages[:-1],
                    add_generation_prompt=True,
                    return_dict=False,
                )
            )
            if token_ids[: len(prompt_ids)] != prompt_ids:
                raise ValueError(f"Prompt prefix drift at row {row_number}")
            supervised = tokenizer.decode(token_ids[len(prompt_ids) :])
            expected_supervised = wrapper + messages[-1]["content"] + "<|im_end|>\n"
            if supervised != expected_supervised:
                raise ValueError(f"Supervision boundary drift at row {row_number}")
            if len(token_ids) > config["training"]["max_sequence_length"]:
                raise ValueError(f"Train row exceeds frozen token budget at row {row_number}")

            encoded = (
                json.dumps({"messages": messages}, ensure_ascii=False, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            prepared.append(encoded)
            raw_targets.append(target)
            sample_ids.add(row["sample_id"])
            group_ids.add(row["group_id"])
            label_counts[row["label"]] += 1
            token_lengths.append(len(token_ids))
            supervised_lengths.append(len(token_ids) - len(prompt_ids))
            target_stream.update(
                f"{row_number}\t{row['label']}\t{len(token_ids)}\t{len(token_ids) - len(prompt_ids)}\n".encode("utf-8")
            )

    if len(prepared) != config["data"]["train_rows"] or set(label_counts) != set(labels):
        raise ValueError("Full-train row count or label coverage drift")
    prepared_bytes = b"".join(prepared)
    summary = {
        "group_count": len(group_ids),
        "label_counts": {label: label_counts[label] for label in labels},
        "prepared_bytes": len(prepared_bytes),
        "prepared_sha256": sha256_bytes(prepared_bytes),
        "raw_ids_stored_publicly": False,
        "raw_text_stored_publicly": False,
        "rows": len(prepared),
        "supervised_token_lengths": numeric_summary(supervised_lengths),
        "target_stream_sha256": target_stream.hexdigest(),
        "template_contract": {
            "assistant_target": "strict JSON single label",
            "empty_think_wrapper_inserted_by_chat_template": True,
            "input_view": "target_only",
            "mask_prompt": True,
            "rationale_gold": False,
        },
        "token_lengths": numeric_summary(token_lengths),
        "truncated_rows": 0,
    }
    return prepared_bytes, summary, raw_targets


def build_runtime_config(config: dict[str, Any], seed: int) -> dict[str, Any]:
    if seed not in config["training"]["seeds"]:
        raise ValueError(f"Unregistered seed: {seed}")
    private_root = resolve_project_path(config["paths"]["private_root"])
    training = config["training"]
    return {
        "adapter_path": str(private_root / "adapters" / f"seed-{seed}"),
        "batch_size": training["batch_size"],
        "clear_cache_threshold": 0,
        "data": str(private_root / "lora-data"),
        "fine_tune_type": "lora",
        "grad_accumulation_steps": training["grad_accumulation_steps"],
        "grad_checkpoint": training["grad_checkpoint"],
        "iters": training["total_iterations_per_seed"],
        "learning_rate": training["learning_rate"],
        "lora_parameters": {
            "dropout": training["dropout"],
            "keys": training["target_modules"],
            "rank": training["rank"],
            "scale": training["scale"],
        },
        "lr_schedule": training["lr_schedule"],
        "mask_prompt": training["mask_prompt"],
        "max_seq_length": training["max_sequence_length"],
        "model": str(resolve_project_path(config["model"]["local_path"])),
        "num_layers": training["num_layers"],
        "optimizer": training["optimizer"],
        "optimizer_config": training["optimizer_config"],
        "project_name": None,
        "report_to": None,
        "resume_adapter_file": None,
        "save_every": training["iterations_per_epoch"],
        "seed": seed,
        "steps_per_eval": training["total_iterations_per_seed"] + 1,
        "steps_per_report": 10,
        "test": False,
        "test_batches": 0,
        "train": True,
        "val_batches": 0,
    }


def validate_runtime(config: dict[str, Any], runtime: dict[str, Any], seed: int) -> None:
    private_root = resolve_project_path(config["paths"]["private_root"])
    if (
        runtime["seed"] != seed
        or runtime["iters"] != 11990
        or runtime["save_every"] != 5995
        or runtime["test"] is not False
        or runtime["train"] is not True
        or runtime["test_batches"] != 0
        or runtime["val_batches"] != 0
        or Path(runtime["data"]) != private_root / "lora-data"
        or "validation" in runtime["data"].lower()
        or "test" in runtime["data"].lower()
    ):
        raise ValueError(f"Runtime config violates the train-only contract for seed {seed}")


def public_paths(config: dict[str, Any]) -> list[Path]:
    return [
        resolve_project_path(config["paths"]["dry_run_report"]),
        resolve_project_path(config["paths"]["dry_run_verification"]),
        *[
            resolve_project_path(config["paths"]["runtime_config_pattern"].format(seed=seed))
            for seed in config["training"]["seeds"]
        ],
    ]


def assert_no_collisions(config: dict[str, Any]) -> None:
    private_root = resolve_project_path(config["paths"]["private_root"])
    candidates = public_paths(config) + [
        private_root,
    ]
    collisions = [display_path(path) for path in candidates if path.exists()]
    if collisions:
        raise FileExistsError(f"Append-only EXP-047 dry-run output already exists: {collisions}")


def exclusive_write(path: Path, content: bytes, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    with path.open("xb") as output:
        output.write(content)
    if private:
        path.parent.chmod(0o700)
        path.chmod(0o600)


def contains_raw_text(public_bytes: bytes, raw_targets: list[str]) -> bool:
    text = public_bytes.decode("utf-8")
    return any(len(target) >= 16 and target in text for target in raw_targets)


def run_dry_run(config: dict[str, Any]) -> dict[str, Any]:
    assert_no_collisions(config)
    environment = verify_environment(config)
    model = verify_model_files(config)
    prepared_bytes, train_summary, raw_targets = build_prepared_train(config)
    private_root = resolve_project_path(config["paths"]["private_root"])
    prepared_path = private_root / "lora-data" / "train.jsonl"
    runtime_values = {
        str(seed): build_runtime_config(config, seed) for seed in config["training"]["seeds"]
    }
    for seed_text, runtime in runtime_values.items():
        validate_runtime(config, runtime, int(seed_text))

    runtime_paths = {
        seed_text: resolve_project_path(config["paths"]["runtime_config_pattern"].format(seed=seed_text))
        for seed_text in runtime_values
    }
    runtime_bytes = {seed: json_bytes(value) for seed, value in runtime_values.items()}
    planned_runtime_artifacts = {
        seed: {
            "bytes": len(runtime_bytes[seed]),
            "path": display_path(runtime_paths[seed]),
            "sha256": sha256_bytes(runtime_bytes[seed]),
        }
        for seed in runtime_values
    }
    report = {
        "accessed_splits": ["train"],
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": artifact(CONFIG_PATH),
        "environment": environment,
        "execution_gate": {
            "config_authorized": False,
            "formal_execution_entrypoints_present": False,
            "model_commands_executed": [],
            "next_required_step": "independent verifier pass, then separate user decision",
        },
        "experiment_id": EXPERIMENT_ID,
        "implementation": {
            "runner": artifact(Path(__file__).resolve()),
            "test": artifact(resolve_project_path(config["implementation"]["test_path"])),
            "verifier": artifact(resolve_project_path(config["implementation"]["verifier_path"])),
        },
        "mlx_lora_subprocess_executed": False,
        "model": model,
        "model_forward_or_backward_executed": False,
        "model_weights_loaded": False,
        "output_boundary": {
            "adapter_root_created": False,
            "prepared_train_private": True,
            "public_raw_ids": False,
            "public_raw_text": False,
            "runtime_configs_only": True,
        },
        "prepared_train": {
            "bytes": len(prepared_bytes),
            "path": display_path(prepared_path),
            "sha256": sha256_bytes(prepared_bytes),
        },
        "protocol": artifact(resolve_project_path(config["paths"]["protocol"])),
        "resource_contract": config["resource_budget"],
        "runtime_configs": planned_runtime_artifacts,
        "stage": "no-model-runner-dry-run",
        "status": "Passed",
        "test_split_accessed": False,
        "tokenizer_loaded": True,
        "train": train_summary,
        "training_contract": {
            "checkpoint_selection": config["training"]["checkpoint_selection"],
            "epochs": config["training"]["epochs"],
            "iterations_per_epoch": config["training"]["iterations_per_epoch"],
            "seeds": config["training"]["seeds"],
            "total_iterations_per_seed": config["training"]["total_iterations_per_seed"],
        },
        "validation_split_accessed": False,
    }
    report_bytes = json_bytes(report)
    if contains_raw_text(report_bytes, raw_targets):
        raise ValueError("Public dry-run report would leak raw train text")

    private_root.mkdir(parents=True, mode=0o700)
    private_root.chmod(0o700)
    exclusive_write(prepared_path, prepared_bytes, private=True)
    for seed, path in runtime_paths.items():
        exclusive_write(path, runtime_bytes[seed])
    report_path = resolve_project_path(config["paths"]["dry_run_report"])
    exclusive_write(report_path, report_bytes)
    return report


def main() -> int:
    args = parse_args()
    if args.command != "dry-run":
        raise ValueError(args.command)
    config = load_config()
    report = run_dry_run(config)
    print(
        json.dumps(
            {
                "experiment_id": report["experiment_id"],
                "model_execution": False,
                "prepared_train_sha256": report["prepared_train"]["sha256"],
                "rows": report["train"]["rows"],
                "status": report["status"],
                "test_access": False,
                "validation_access": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
