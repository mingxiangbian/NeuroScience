#!/usr/bin/env python3
"""Independently verify the no-model EXP-033 runner dry-run."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
from typing import Any

EXPERIMENT_ID = "EXP-033"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
CONFIG_PATH = SCRIPT_DIR / "configs" / "exp-033-target-aligned-lora.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project root: {value}")
    return path


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "bytes": path.stat().st_size,
        "path": display_path(path),
        "sha256": sha256_file(path),
    }


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if (
        config.get("experiment_id") != EXPERIMENT_ID
        or config.get("status") != "Registered"
        or config.get("tier") != "Major"
    ):
        raise ValueError("Unexpected EXP-033 registration identity")
    implementation = config["implementation"]
    if any(value == "PENDING" for value in implementation.values()):
        raise ValueError("Implementation hashes are not frozen")
    runner = resolve_project_path(implementation["runner_path"])
    verifier = resolve_project_path(implementation["verifier_path"])
    if verifier != Path(__file__).resolve():
        raise ValueError("Verifier path does not resolve to this file")
    if sha256_file(runner) != implementation["runner_sha256"]:
        raise ValueError("Runner hash mismatch")
    if sha256_file(verifier) != implementation["verifier_sha256"]:
        raise ValueError("Verifier hash mismatch")
    return config


def iter_hashed_artifacts(value: Any):
    if isinstance(value, dict):
        if set(("path", "sha256")).issubset(value):
            yield value
        else:
            for child in value.values():
                yield from iter_hashed_artifacts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_hashed_artifacts(child)


def verify_evidence_chain(config: dict[str, Any]) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    for spec in iter_hashed_artifacts(config["evidence_chain"]):
        path = resolve_project_path(spec["path"])
        if not path.is_file() or sha256_file(path) != spec["sha256"]:
            raise ValueError(f"Evidence-chain drift: {path}")
        verified.append(artifact(path))
    return verified


def verify_inheritance(config: dict[str, Any]) -> dict[str, Any]:
    parent_spec = config["evidence_chain"]["parent"]["exp_029_config"]
    parent_path = resolve_project_path(parent_spec["path"])
    if sha256_file(parent_path) != parent_spec["sha256"]:
        raise ValueError("EXP-029 parent-config drift")
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    inherited_fields = (
        "model",
        "preflight",
        "repetition_gate",
        "resource_budget",
        "training",
    )
    for field in inherited_fields:
        if config[field] != parent[field]:
            raise ValueError(f"EXP-033 changed inherited field: {field}")
    return {
        "fields": list(inherited_fields),
        "parent_config": artifact(parent_path),
        "status": "Exact match",
    }


def verify_inference_alignment(config: dict[str, Any]) -> dict[str, Any]:
    alignment = config["inference_alignment"]
    prompt = resolve_project_path(alignment["prompt_path"])
    constraint = resolve_project_path(alignment["constraint_path"])
    if sha256_file(prompt) != alignment["prompt_sha256"]:
        raise ValueError("Aligned prompt drift")
    if sha256_file(constraint) != alignment["constraint_sha256"]:
        raise ValueError("Aligned constraint drift")
    if alignment["enable_thinking"] is not False:
        raise ValueError("Aligned inference thinking flag drift")
    return {
        "constraint": artifact(constraint),
        "enable_thinking": False,
        "prompt": artifact(prompt),
    }


def recalculate_source_tree(spec: dict[str, Any]) -> dict[str, Any]:
    root = Path(spec["root"])
    paths = sorted(root.rglob("*.py"), key=lambda item: item.relative_to(root).as_posix())
    aggregate = hashlib.sha256()
    total_bytes = 0
    for path in paths:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        size = path.stat().st_size
        aggregate.update(
            relative
            + bytes([0])
            + str(size).encode("ascii")
            + bytes([0])
            + sha256_file(path).encode("ascii")
            + bytes([10])
        )
        total_bytes += size
    observed = {
        "file_count": len(paths),
        "manifest_sha256": aggregate.hexdigest(),
        "total_bytes": total_bytes,
    }
    expected = {
        "file_count": int(spec["file_count"]),
        "manifest_sha256": spec["manifest_sha256"],
        "total_bytes": int(spec["total_bytes"]),
    }
    if observed != expected:
        raise ValueError(f"MLX-LM source-tree drift: {observed}")
    return observed


def verify_environment(config: dict[str, Any]) -> dict[str, Any]:
    runtime = config["runtime"]
    configured_python = Path(runtime["python_executable"])
    if not configured_python.is_file() or not Path(sys.executable).samefile(configured_python):
        raise ValueError("Verifier is not running in the frozen Python environment")
    packages: dict[str, str] = {}
    for name in runtime["packages"]:
        packages[name] = (
            platform.python_version()
            if name == "python"
            else importlib.metadata.version(name)
        )
    if packages != runtime["packages"]:
        raise ValueError(f"Runtime package drift: {packages}")
    cli_spec = runtime["mlx_lora_cli"]
    cli = Path(cli_spec["path"])
    if (
        not cli.is_file()
        or not os.access(cli, os.X_OK)
        or sha256_file(cli) != cli_spec["sha256"]
    ):
        raise ValueError("MLX-LM CLI drift")
    return {
        "mlx_lm_source_tree": recalculate_source_tree(runtime["mlx_lm_source_tree"]),
        "mlx_lora_cli": artifact(cli),
        "packages": packages,
        "python_executable": str(configured_python),
    }


def verify_canonical_runtime_contract(
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    spec = config["runtime"]["canonical_contract"]
    path = resolve_project_path(spec["path"])
    if not path.is_file() or sha256_file(path) != spec["sha256"]:
        raise ValueError("Canonical MLX runtime contract drift")
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("contract_id") != "EXP-033-CANONICAL-MLX-RUNTIME-V2":
        raise ValueError("Canonical MLX runtime identity drift")
    if (
        contract["execution_gate"]["formal_training_enabled"] is not False
        or config["authorization_contract"]["formal_training_enabled"] is not False
    ):
        raise ValueError("Formal training must remain hard-disabled in V2")

    for source in contract["source_contracts"].values():
        source_path = resolve_project_path(source["path"])
        if sha256_file(source_path) != source["sha256"]:
            raise ValueError(f"Canonical source-contract drift: {source_path}")

    source_text: dict[str, str] = {}
    source_artifacts: dict[str, Any] = {}
    for name, source in contract["mlx_semantics_sources"].items():
        source_path = Path(source["path"])
        if not source_path.is_file() or sha256_file(source_path) != source["sha256"]:
            raise ValueError(f"MLX semantics-source drift: {source_path}")
        source_text[name] = source_path.read_text(encoding="utf-8")
        source_artifacts[name] = artifact(source_path)
    required_source_fragments = {
        "config_and_optimizer": (
            "build_schedule(args.lr_schedule) if args.lr_schedule else args.learning_rate",
            "optimizer_config = args.optimizer_config.get(optimizer_name, {})",
        ),
        "dataset_and_prompt_mask": (
            "messages[:-1]",
            "add_generation_prompt=add_generation_prompt",
        ),
        "layer_selection": ("model.layers[-max(num_layers, 0) :]",),
        "training_loop": (
            "range(1, args.iters + 1)",
            "it % grad_accum_steps == 0",
        ),
    }
    for name, fragments in required_source_fragments.items():
        for fragment in fragments:
            if fragment not in source_text[name]:
                raise ValueError(f"Expected MLX runtime semantics are absent: {fragment}")

    training = config["training"]
    lora = training["lora"]
    model_config_path = resolve_project_path(config["model"]["local_path"]) / "config.json"
    model_config = json.loads(model_config_path.read_text(encoding="utf-8"))
    hidden_layers = int(model_config["num_hidden_layers"])
    expected_indices = list(range(hidden_layers - int(lora["num_layers"]), hidden_layers))
    assertions = contract["semantic_assertions"]
    if assertions != {
        "adapted_block_indices": expected_indices,
        "formal_micro_iterations": int(training["iterations"]),
        "formal_optimizer_updates": int(training["optimizer_updates"]),
        "gradient_update_rule": "optimizer update when micro-iteration modulo grad_accumulation_steps equals zero",
        "layer_selection_rule": "model.layers[-max(num_layers, 0):]",
        "learning_rate_schedule": "constant scalar 1e-5 because lr_schedule is null",
        "mask_prompt": bool(training["mask_prompt"]),
        "model_hidden_layers": hidden_layers,
        "smoke_micro_iterations": int(config["preflight"]["smoke_iterations"]),
        "smoke_optimizer_updates": int(config["preflight"]["smoke_iterations"])
        // int(training["grad_accumulation_steps"]),
    }:
        raise ValueError("Canonical runtime semantic assertions drift")
    if lora["adapted_block_indices"] != expected_indices:
        raise ValueError("Registered adapted block indices are not the final num_layers blocks")
    if int(training["iterations"]) % int(training["grad_accumulation_steps"]):
        raise ValueError("Formal iterations do not end on an optimizer update")
    if (
        int(training["iterations"]) // int(training["grad_accumulation_steps"])
        != int(training["optimizer_updates"])
    ):
        raise ValueError("Formal optimizer-update count drift")

    expected_keys = {
        "adapter_path",
        "batch_size",
        "clear_cache_threshold",
        "data",
        "fine_tune_type",
        "grad_accumulation_steps",
        "grad_checkpoint",
        "iters",
        "learning_rate",
        "lora_parameters",
        "lr_schedule",
        "mask_prompt",
        "max_seq_length",
        "model",
        "num_layers",
        "optimizer",
        "optimizer_config",
        "project_name",
        "report_to",
        "resume_adapter_file",
        "save_every",
        "seed",
        "steps_per_eval",
        "steps_per_report",
        "test",
        "test_batches",
        "train",
        "val_batches",
    }
    common_expected = {
        "batch_size": int(training["batch_size"]),
        "clear_cache_threshold": 0,
        "fine_tune_type": training["fine_tune_type"],
        "grad_accumulation_steps": int(training["grad_accumulation_steps"]),
        "grad_checkpoint": bool(training["grad_checkpoint"]),
        "learning_rate": float(training["learning_rate"]),
        "lora_parameters": {
            "dropout": float(lora["dropout"]),
            "keys": list(lora["target_modules"]),
            "rank": int(lora["rank"]),
            "scale": float(lora["scale"]),
        },
        "lr_schedule": None,
        "mask_prompt": bool(training["mask_prompt"]),
        "max_seq_length": int(training["max_sequence_length"]),
        "model": str(resolve_project_path(config["model"]["local_path"])),
        "num_layers": int(lora["num_layers"]),
        "optimizer": training["optimizer"],
        "optimizer_config": {"adam": {}},
        "project_name": None,
        "report_to": None,
        "resume_adapter_file": None,
        "seed": 42,
        "test": False,
        "test_batches": 0,
        "train": True,
        "val_batches": 0,
    }
    stage_expected = {
        "smoke": {
            "adapter_path": str(
                resolve_project_path(config["artifacts"]["private_adapter_root"]) / "smoke"
            ),
            "data": str(resolve_project_path(config["data"]["smoke_train"]["path"]).parent),
            "iters": int(config["preflight"]["smoke_iterations"]),
            "save_every": int(config["preflight"]["smoke_iterations"]) + 1,
            "steps_per_eval": int(config["preflight"]["smoke_iterations"]) + 1,
            "steps_per_report": 5,
        },
        "formal_seed_42": {
            "adapter_path": str(
                resolve_project_path(config["artifacts"]["private_adapter_root"])
                / "seed-42"
            ),
            "data": str(
                resolve_project_path(config["data"]["prepared_train"]["path"]).parent
            ),
            "iters": int(training["iterations"]),
            "save_every": int(training["save_every_iterations"]),
            "steps_per_eval": int(training["iterations"]) + 1,
            "steps_per_report": int(training["steps_per_report"]),
        },
    }
    for stage, stage_values in stage_expected.items():
        runtime = contract["effective_configs"][stage]
        if set(runtime) != expected_keys:
            raise ValueError(f"Canonical {stage} runtime key set drift")
        expected = {**common_expected, **stage_values}
        if runtime != expected:
            raise ValueError(f"Canonical {stage} runtime values drift")

    semantic_checks = {
        "adapted_blocks_are_final_16": True,
        "formal_micro_iterations": int(training["iterations"]),
        "formal_optimizer_updates": int(training["optimizer_updates"]),
        "mlx_source_semantics_rechecked": sorted(required_source_fragments),
        "runtime_configs_match_inherited_training": True,
        "smoke_micro_iterations": int(config["preflight"]["smoke_iterations"]),
        "smoke_optimizer_updates": int(config["preflight"]["smoke_iterations"])
        // int(training["grad_accumulation_steps"]),
    }
    return contract, artifact(path), {
        "checks": semantic_checks,
        "source_artifacts": source_artifacts,
    }


def verify_model(config: dict[str, Any]) -> dict[str, Any]:
    model = config["model"]
    manifest_path = resolve_project_path(model["manifest_path"])
    if sha256_file(manifest_path) != model["manifest_sha256"]:
        raise ValueError("Model manifest drift")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("repo_id") != model["repo_id"] or manifest.get("revision") != model["revision"]:
        raise ValueError("Model identity drift")
    model_root = resolve_project_path(model["local_path"])
    files = manifest["mlx_bf16"]["files"]
    total_bytes = 0
    for expected in files:
        path = model_root / expected["path"]
        observed = {
            "bytes": path.stat().st_size,
            "path": expected["path"],
            "sha256": sha256_file(path),
        }
        if observed != expected:
            raise ValueError(f"Model-file drift: {path}")
        total_bytes += observed["bytes"]
    if len(files) != manifest["mlx_bf16"]["file_count"] or total_bytes != manifest["mlx_bf16"]["total_bytes"]:
        raise ValueError("Model manifest totals drift")
    return {
        "file_count": len(files),
        "manifest": artifact(manifest_path),
        "total_bytes": total_bytes,
    }


def load_labels(config: dict[str, Any]) -> tuple[str, ...]:
    spec = config["data"]["labels"]
    path = resolve_project_path(spec["path"])
    if sha256_file(path) != spec["sha256"]:
        raise ValueError("Label hash drift")
    labels = tuple(line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    if len(labels) != spec["count"] or len(labels) != len(set(labels)):
        raise ValueError("Label ontology drift")
    return labels


def assert_train_only_directory(path: Path) -> None:
    if path.name != "train.jsonl":
        raise ValueError("Runtime dataset is not train.jsonl")
    for name in ("valid.jsonl", "validation.jsonl", "dev.jsonl", "test.jsonl"):
        if (path.parent / name).exists():
            raise ValueError(f"Non-train runtime file is present: {name}")


def verify_jsonl(
    spec: dict[str, Any],
    labels: tuple[str, ...],
    *,
    expected_cardinality: dict[str, int] | None,
    expected_neutral: int,
) -> dict[str, Any]:
    path = resolve_project_path(spec["path"])
    if sha256_file(path) != spec["sha256"]:
        raise ValueError(f"Prepared-data hash drift: {path}")
    assert_train_only_directory(path)
    label_ids = {label: index for index, label in enumerate(labels)}
    cardinality: Counter[int] = Counter()
    support: Counter[str] = Counter()
    target_stream = hashlib.sha256()
    rows = 0
    neutral = 0
    with path.open("r", encoding="utf-8") as source:
        for row_number, line in enumerate(source, start=1):
            rows = row_number
            record = json.loads(line)
            if set(record) != {"messages"}:
                raise ValueError(f"Unexpected record keys at row {row_number}")
            messages = record["messages"]
            if (
                not isinstance(messages, list)
                or len(messages) != 3
                or [message.get("role") for message in messages]
                != ["system", "user", "assistant"]
                or any(set(message) != {"role", "content"} for message in messages)
                or any(not isinstance(message["content"], str) for message in messages)
            ):
                raise ValueError(f"Invalid messages at row {row_number}")
            target = messages[-1]["content"]
            parsed = json.loads(target)
            if set(parsed) != {"labels"} or not isinstance(parsed["labels"], list):
                raise ValueError(f"Invalid target schema at row {row_number}")
            target_labels = parsed["labels"]
            if (
                not target_labels
                or any(label not in label_ids for label in target_labels)
                or len(target_labels) != len(set(target_labels))
            ):
                raise ValueError(f"Invalid target labels at row {row_number}")
            ids = [label_ids[label] for label in target_labels]
            if ids != sorted(ids):
                raise ValueError(f"Target order drift at row {row_number}")
            canonical = json.dumps(
                {"labels": target_labels}, separators=(",", ":"), ensure_ascii=True
            )
            if target != canonical:
                raise ValueError(f"Target serialization drift at row {row_number}")
            cardinality[len(target_labels)] += 1
            support.update(target_labels)
            neutral += int("neutral" in target_labels and len(target_labels) > 1)
            target_stream.update(
                f"{row_number}\t{','.join(map(str, ids))}\t{target}\n".encode("utf-8")
            )
    observed_cardinality = {str(key): cardinality[key] for key in sorted(cardinality)}
    if rows != spec["rows"] or neutral != expected_neutral:
        raise ValueError("Prepared-data row or neutral count drift")
    if expected_cardinality is not None and observed_cardinality != expected_cardinality:
        raise ValueError("Prepared-data cardinality drift")
    return {
        "cardinality_support": observed_cardinality,
        "covers_all_labels": set(support) == set(labels),
        "label_support": dict(sorted(support.items())),
        "max_target_cardinality": max(cardinality),
        "neutral_cooccurrence_rows": neutral,
        "path": display_path(path),
        "rows": rows,
        "sha256": spec["sha256"],
        "target_stream_sha256": target_stream.hexdigest(),
    }


def verify_data(config: dict[str, Any]) -> dict[str, Any]:
    data = config["data"]
    test_path = resolve_project_path(data["test"]["path"])
    if not data["test"]["must_be_absent"] or test_path.exists():
        raise ValueError("Test-absence gate failed")
    source = resolve_project_path(data["source_train"]["path"])
    if sha256_file(source) != data["source_train"]["sha256"]:
        raise ValueError("Source-train hash drift")
    labels = load_labels(config)
    contract = data["target_contract"]
    prepared = verify_jsonl(
        data["prepared_train"],
        labels,
        expected_cardinality=contract["cardinality_support"],
        expected_neutral=contract["neutral_cooccurrence_rows"],
    )
    if prepared["target_stream_sha256"] != contract["target_stream_sha256"]:
        raise ValueError("Target-stream hash drift")
    smoke = verify_jsonl(
        data["smoke_train"],
        labels,
        expected_cardinality=None,
        expected_neutral=data["smoke_train"]["neutral_cooccurrence_rows"],
    )
    if not smoke["covers_all_labels"] or smoke["max_target_cardinality"] != data["smoke_train"]["max_target_cardinality"]:
        raise ValueError("Boundary-smoke coverage drift")
    return {
        "labels": {
            "count": len(labels),
            "path": data["labels"]["path"],
            "sha256": data["labels"]["sha256"],
        },
        "prepared_train": prepared,
        "smoke_train": smoke,
        "source_train": artifact(source),
        "test_split_absent": True,
    }


def verify_runtime_configs(
    config: dict[str, Any],
    dry_report: dict[str, Any],
    canonical_contract: dict[str, Any],
) -> dict[str, Any]:
    observed: dict[str, Any] = {}
    cases = (
        ("smoke", "smoke_runtime_config", "smoke"),
        ("formal_seed_42", "formal_runtime_config", "formal"),
    )
    for report_key, artifact_key, stage in cases:
        path = resolve_project_path(config["artifacts"][artifact_key])
        runtime = json.loads(path.read_text(encoding="utf-8"))
        expected = canonical_contract["effective_configs"][report_key]
        if runtime != expected:
            raise ValueError(f"Generated {stage} runtime config differs from the contract")
        if dry_report["runtime_configs"][report_key]["config"] != expected:
            raise ValueError(f"Dry-run embedded {stage} runtime config differs")
        observed_artifact = artifact(path)
        if dry_report["runtime_configs"][report_key]["artifact"] != observed_artifact:
            raise ValueError(f"Dry-run {stage} runtime artifact metadata differs")
        if runtime["test"] or runtime["val_batches"] != 0 or not runtime["train"]:
            raise ValueError(f"Generated {stage} config is not train-only")
        assert_train_only_directory(Path(runtime["data"]) / "train.jsonl")
        observed[report_key] = {
            "artifact": observed_artifact,
            "config": runtime,
        }
    return observed


def assert_no_execution_outputs(config: dict[str, Any]) -> None:
    artifacts = config["artifacts"]
    forbidden = [
        resolve_project_path(artifacts["private_adapter_root"]),
        resolve_project_path(artifacts["run_root"]),
        resolve_project_path(artifacts["smoke_report"]),
        resolve_project_path(artifacts["smoke_stdout"]),
        resolve_project_path(artifacts["smoke_history"]),
        resolve_project_path(artifacts["smoke_verification"]),
    ]
    present = [display_path(path) for path in forbidden if path.exists()]
    if present:
        raise ValueError(f"Dry-run created or followed training outputs: {present}")


def build_verification(config: dict[str, Any]) -> dict[str, Any]:
    report_path = resolve_project_path(config["artifacts"]["dry_run_report"])
    if not report_path.is_file():
        raise FileNotFoundError(report_path)
    dry_report = json.loads(report_path.read_text(encoding="utf-8"))
    if (
        dry_report.get("experiment_id") != EXPERIMENT_ID
        or dry_report.get("stage") != "runner-dry-run"
        or dry_report.get("status") != "Passed"
        or dry_report.get("accessed_splits") != ["train"]
        or dry_report.get("model_forward_or_backward_executed") is not False
        or dry_report.get("mlx_lora_subprocess_executed") is not False
        or dry_report.get("validation_split_accessed") is not False
        or dry_report.get("test_split_accessed") is not False
        or dry_report.get("formal_training_authorized") is not False
        or dry_report.get("smoke_training_authorized") is not False
    ):
        raise ValueError("Dry-run execution boundary fields are invalid")

    assert_no_execution_outputs(config)
    evidence = verify_evidence_chain(config)
    inheritance = verify_inheritance(config)
    inference_alignment = verify_inference_alignment(config)
    environment = verify_environment(config)
    model = verify_model(config)
    data = verify_data(config)
    runtime_contract, runtime_contract_artifact, runtime_semantics = (
        verify_canonical_runtime_contract(config)
    )
    runtimes = verify_runtime_configs(config, dry_report, runtime_contract)
    protocol_spec = config["artifacts"]["protocol"]
    protocol_path = resolve_project_path(protocol_spec["path"])
    if sha256_file(protocol_path) != protocol_spec["sha256"]:
        raise ValueError("EXP-033 protocol hash drift")
    expected_config_artifact = artifact(CONFIG_PATH)
    runner_artifact = artifact(resolve_project_path(config["implementation"]["runner_path"]))
    verifier_artifact = artifact(Path(__file__).resolve())
    if dry_report["config"] != expected_config_artifact:
        raise ValueError("Dry-run config artifact metadata drift")
    if dry_report["implementation"] != {
        "runner": runner_artifact,
        "verifier": verifier_artifact,
    }:
        raise ValueError("Dry-run implementation metadata drift")
    if dry_report["inheritance"] != inheritance:
        raise ValueError("Dry-run inheritance report drift")
    if dry_report["inference_alignment"] != inference_alignment:
        raise ValueError("Dry-run inference-alignment report drift")
    if dry_report["evidence_chain"] != {
        "artifacts": evidence,
        "verified_count": len(evidence),
    }:
        raise ValueError("Dry-run evidence-chain report drift")
    if dry_report["environment"] != environment:
        raise ValueError("Dry-run environment report drift")
    if dry_report["model"] != model:
        raise ValueError("Dry-run model report drift")
    if dry_report["data"] != data:
        raise ValueError("Dry-run data report drift")
    if dry_report["runtime_configs"] != runtimes:
        raise ValueError("Dry-run runtime report drift")
    if dry_report.get("runtime_contract") != {
        "artifact": runtime_contract_artifact,
        "contract_id": runtime_contract["contract_id"],
        "formal_training_enabled": False,
    }:
        raise ValueError("Dry-run canonical-runtime contract report drift")
    if dry_report.get("protocol") != artifact(protocol_path):
        raise ValueError("Dry-run protocol artifact drift")
    if dry_report.get("output_boundary") != {
        "adapter_root_created": False,
        "formal_run_root_created": False,
        "runtime_configs_only": True,
    }:
        raise ValueError("Dry-run output-boundary report drift")

    return {
        "accessed_splits": ["train"],
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "config_sha256": sha256_file(CONFIG_PATH),
        "dry_run_report": artifact(report_path),
        "experiment_id": EXPERIMENT_ID,
        "formal_training_authorized": False,
        "implementation": {
            "runner": runner_artifact,
            "verifier": verifier_artifact,
            "verifier_imports_runner": False,
        },
        "mlx_lora_subprocess_executed": False,
        "model_forward_or_backward_executed": False,
        "next_required_step": (
            "Re-run PRE-EXP-033 execution V3 with --check, then request explicit "
            "authorization for the 50-iteration train-only smoke."
        ),
        "recalculated": {
            "data": data,
            "environment": environment,
            "evidence_chain_artifacts": evidence,
            "inference_alignment": inference_alignment,
            "inheritance": inheritance,
            "model": model,
            "protocol": artifact(protocol_path),
            "runtime_contract": {
                "artifact": runtime_contract_artifact,
                **runtime_semantics,
            },
            "runtime_configs": runtimes,
        },
        "smoke_training_authorized": False,
        "status": "Passed",
        "test_split_absent": True,
        "test_split_accessed": False,
        "validation_split_accessed": False,
        "verification_id": "EXP-033-RUNNER-DRY-RUN-VERIFY-V2",
    }


def check_existing(expected: dict[str, Any], path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    existing = json.loads(path.read_text(encoding="utf-8"))
    expected["completed_at_utc"] = existing.get("completed_at_utc")
    if existing != expected:
        raise ValueError("Stored dry-run verification differs from independent recomputation")


def main() -> None:
    args = parse_args()
    config = load_config()
    verification_path = resolve_project_path(config["artifacts"]["dry_run_verification"])
    verification = build_verification(config)
    if args.check:
        check_existing(verification, verification_path)
        print(json.dumps({"path": display_path(verification_path), "status": "Passed"}, indent=2))
        return
    if verification_path.exists():
        raise FileExistsError(verification_path)
    write_json(verification_path, verification)
    print(json.dumps(verification, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
