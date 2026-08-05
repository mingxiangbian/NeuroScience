#!/usr/bin/env python3
"""Run the frozen, train-only EXP-033 target-aligned LoRA stages."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
from queue import Empty, Queue
import re
import statistics
import subprocess
import sys
from threading import Thread
import time
import traceback
from typing import Any

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["PYTHONNOUSERSITE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

EXPERIMENT_ID = "EXP-033"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
CONFIG_PATH = SCRIPT_DIR / "configs" / "exp-033-target-aligned-lora.json"
DATA_ROOT = PROJECT_ROOT / "data" / "goemotions" / "official"

TRAIN_LOG_PATTERN = re.compile(
    r"Iter (?P<iteration>\d+): Train loss (?P<loss>[^,]+), "
    r"Learning Rate (?P<learning_rate>[^,]+), It/sec (?P<iterations_per_second>[^,]+), "
    r"Tokens/sec (?P<tokens_per_second>[^,]+), Trained Tokens (?P<trained_tokens>\d+), "
    r"Peak mem (?P<peak_memory_gb>[^ ]+) GB"
)
TRAINABLE_PATTERN = re.compile(
    r"Trainable parameters: (?P<percent>[0-9.]+)% "
    r"\((?P<trainable>[0-9.]+)M/(?P<total>[0-9.]+)M\)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Frozen EXP-033 runner; no data-preparation or evaluation commands exist."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("dry-run")
    smoke = subparsers.add_parser("smoke")
    smoke.add_argument("--authorization", type=Path, required=True)
    train = subparsers.add_parser("train")
    train.add_argument("--seed", type=int, required=True)
    train.add_argument("--authorization", type=Path, required=True)
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


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def resolve_project_path(value: str) -> Path:
    path = (PROJECT_ROOT / value).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Project-relative path escapes the project root: {value}")
    return path


def artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "bytes": path.stat().st_size,
        "path": display_path(path),
        "sha256": sha256_file(path),
    }


def verify_artifact(spec: dict[str, Any]) -> Path:
    path = resolve_project_path(spec["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    observed = sha256_file(path)
    if observed != spec["sha256"]:
        raise ValueError(f"Artifact hash mismatch: {path}")
    return path


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if (
        config.get("experiment_id") != EXPERIMENT_ID
        or config.get("tier") != "Major"
        or config.get("status") != "Registered"
        or config.get("stage") != "target-aligned-supervised-generative-lora"
    ):
        raise ValueError("EXP-033 must remain a registered Major configuration")
    implementation = config["implementation"]
    if any(value == "PENDING" for value in implementation.values()):
        raise ValueError("EXP-033 implementation hashes are not frozen")
    runner_path = resolve_project_path(implementation["runner_path"])
    verifier_path = resolve_project_path(implementation["verifier_path"])
    if runner_path != Path(__file__).resolve():
        raise ValueError("Runner path does not resolve to this file")
    if sha256_file(runner_path) != implementation["runner_sha256"]:
        raise ValueError("Runner hash differs from the frozen config")
    if sha256_file(verifier_path) != implementation["verifier_sha256"]:
        raise ValueError("Verifier hash differs from the frozen config")
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
        path = verify_artifact(spec)
        verified.append(artifact(path))
    return verified


def verify_inheritance(config: dict[str, Any]) -> dict[str, Any]:
    parent_spec = config["evidence_chain"]["parent"]["exp_029_config"]
    parent_path = verify_artifact(parent_spec)
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
            raise ValueError(f"EXP-033 changed frozen EXP-029 field: {field}")
    return {
        "fields": list(inherited_fields),
        "parent_config": artifact(parent_path),
        "status": "Exact match",
    }


def verify_inference_alignment(config: dict[str, Any]) -> dict[str, Any]:
    alignment = config["inference_alignment"]
    prompt = verify_artifact(
        {"path": alignment["prompt_path"], "sha256": alignment["prompt_sha256"]}
    )
    constraint = verify_artifact(
        {
            "path": alignment["constraint_path"],
            "sha256": alignment["constraint_sha256"],
        }
    )
    if alignment["enable_thinking"] is not False:
        raise ValueError("EXP-033 aligned inference must keep thinking disabled")
    return {
        "constraint": artifact(constraint),
        "enable_thinking": False,
        "prompt": artifact(prompt),
    }


def source_tree_manifest(spec: dict[str, Any]) -> dict[str, Any]:
    root = Path(spec["root"])
    if not root.is_dir():
        raise FileNotFoundError(root)
    paths = sorted(root.rglob("*.py"), key=lambda item: item.relative_to(root).as_posix())
    aggregate = hashlib.sha256()
    total_bytes = 0
    for path in paths:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        size = path.stat().st_size
        digest = sha256_file(path).encode("ascii")
        aggregate.update(
            relative
            + bytes([0])
            + str(size).encode("ascii")
            + bytes([0])
            + digest
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
        raise ValueError(f"MLX-LM source tree drift: {observed}")
    return observed


def verify_environment(config: dict[str, Any]) -> dict[str, Any]:
    runtime = config["runtime"]
    configured_python = Path(runtime["python_executable"])
    if not configured_python.is_file() or not Path(sys.executable).samefile(configured_python):
        raise ValueError(
            f"Use the frozen Python executable: {runtime['python_executable']}"
        )
    observed_packages: dict[str, str] = {}
    for name in runtime["packages"]:
        observed_packages[name] = (
            platform.python_version()
            if name == "python"
            else importlib.metadata.version(name)
        )
    if observed_packages != runtime["packages"]:
        raise ValueError(f"Runtime package drift: {observed_packages}")
    cli_spec = runtime["mlx_lora_cli"]
    cli_path = Path(cli_spec["path"])
    if not cli_path.is_file() or not os.access(cli_path, os.X_OK):
        raise FileNotFoundError(f"MLX-LM CLI is unavailable: {cli_path}")
    if sha256_file(cli_path) != cli_spec["sha256"]:
        raise ValueError("MLX-LM CLI hash drift")
    return {
        "mlx_lm_source_tree": source_tree_manifest(runtime["mlx_lm_source_tree"]),
        "mlx_lora_cli": artifact(cli_path),
        "packages": observed_packages,
        "python_executable": str(configured_python),
    }


def load_canonical_runtime_contract(
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = config["runtime"]["canonical_contract"]
    path = verify_artifact(spec)
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("contract_id") != "EXP-033-CANONICAL-MLX-RUNTIME-V2":
        raise ValueError("Unexpected canonical runtime contract identity")
    if contract["execution_gate"]["formal_training_enabled"] is not False:
        raise ValueError("Canonical runtime contract must keep formal training disabled")
    if config["authorization_contract"]["formal_training_enabled"] is not False:
        raise ValueError("EXP-033 V2 config must keep formal training disabled")
    for source in contract["source_contracts"].values():
        verify_artifact(source)
    for source in contract["mlx_semantics_sources"].values():
        source_path = Path(source["path"])
        if not source_path.is_file() or sha256_file(source_path) != source["sha256"]:
            raise ValueError(f"Canonical runtime semantics source drift: {source_path}")
    return contract, artifact(path)


def verify_model(config: dict[str, Any]) -> dict[str, Any]:
    model = config["model"]
    manifest_path = resolve_project_path(model["manifest_path"])
    if sha256_file(manifest_path) != model["manifest_sha256"]:
        raise ValueError("Model manifest hash drift")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("repo_id") != model["repo_id"] or manifest.get("revision") != model["revision"]:
        raise ValueError("Model identity differs from the frozen config")
    model_root = resolve_project_path(model["local_path"])
    observed_files: list[dict[str, Any]] = []
    total_bytes = 0
    for expected in manifest["mlx_bf16"]["files"]:
        path = model_root / expected["path"]
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = {
            "bytes": path.stat().st_size,
            "path": expected["path"],
            "sha256": sha256_file(path),
        }
        if observed != expected:
            raise ValueError(f"Model file drift: {path}")
        observed_files.append(observed)
        total_bytes += observed["bytes"]
    if (
        len(observed_files) != int(manifest["mlx_bf16"]["file_count"])
        or total_bytes != int(manifest["mlx_bf16"]["total_bytes"])
    ):
        raise ValueError("Model manifest totals do not match its files")
    return {
        "file_count": len(observed_files),
        "manifest": artifact(manifest_path),
        "total_bytes": total_bytes,
    }


def load_labels(config: dict[str, Any]) -> tuple[str, ...]:
    spec = config["data"]["labels"]
    path = verify_artifact(spec)
    labels = tuple(line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    if len(labels) != int(spec["count"]) or len(labels) != len(set(labels)):
        raise ValueError("Label ontology count or uniqueness drift")
    return labels


def assert_train_only_directory(train_path: Path) -> None:
    if train_path.name != "train.jsonl":
        raise ValueError(f"Runtime data must be named train.jsonl: {train_path}")
    forbidden = ("valid.jsonl", "validation.jsonl", "dev.jsonl", "test.jsonl")
    present = [name for name in forbidden if (train_path.parent / name).exists()]
    if present:
        raise ValueError(f"Non-train runtime files are present: {present}")


def validate_prepared_jsonl(
    spec: dict[str, Any],
    labels: tuple[str, ...],
    *,
    expected_cardinality: dict[str, int] | None,
    expected_neutral_cooccurrence: int,
) -> dict[str, Any]:
    path = verify_artifact(spec)
    assert_train_only_directory(path)
    label_to_id = {label: index for index, label in enumerate(labels)}
    cardinality: Counter[int] = Counter()
    label_support: Counter[str] = Counter()
    target_stream = hashlib.sha256()
    rows = 0
    neutral_cooccurrence = 0
    with path.open("r", encoding="utf-8") as source:
        for row_number, line in enumerate(source, start=1):
            rows = row_number
            record = json.loads(line)
            if set(record) != {"messages"}:
                raise ValueError(f"Unexpected JSONL fields at row {row_number}")
            messages = record["messages"]
            if (
                not isinstance(messages, list)
                or len(messages) != 3
                or [message.get("role") for message in messages]
                != ["system", "user", "assistant"]
                or any(set(message) != {"role", "content"} for message in messages)
                or any(not isinstance(message["content"], str) for message in messages)
                or not messages[0]["content"]
                or not messages[1]["content"]
            ):
                raise ValueError(f"Invalid chat record at row {row_number}")
            target = messages[2]["content"]
            parsed = json.loads(target)
            if set(parsed) != {"labels"} or not isinstance(parsed["labels"], list):
                raise ValueError(f"Invalid target schema at row {row_number}")
            target_labels = parsed["labels"]
            if (
                not target_labels
                or any(label not in label_to_id for label in target_labels)
                or len(target_labels) != len(set(target_labels))
            ):
                raise ValueError(f"Invalid target labels at row {row_number}")
            target_ids = [label_to_id[label] for label in target_labels]
            if target_ids != sorted(target_ids):
                raise ValueError(f"Non-canonical target order at row {row_number}")
            canonical = json.dumps(
                {"labels": target_labels}, separators=(",", ":"), ensure_ascii=True
            )
            if target != canonical:
                raise ValueError(f"Non-canonical target JSON at row {row_number}")
            cardinality[len(target_labels)] += 1
            label_support.update(target_labels)
            if "neutral" in target_labels and len(target_labels) > 1:
                neutral_cooccurrence += 1
            target_stream.update(
                f"{row_number}\t{','.join(map(str, target_ids))}\t{target}\n".encode(
                    "utf-8"
                )
            )
    if rows != int(spec["rows"]):
        raise ValueError(f"Prepared row count {rows} != {spec['rows']}")
    if neutral_cooccurrence != expected_neutral_cooccurrence:
        raise ValueError("Neutral co-occurrence count drift")
    observed_cardinality = {str(key): cardinality[key] for key in sorted(cardinality)}
    if expected_cardinality is not None and observed_cardinality != expected_cardinality:
        raise ValueError(f"Target cardinality drift: {observed_cardinality}")
    return {
        "cardinality_support": observed_cardinality,
        "covers_all_labels": set(label_support) == set(labels),
        "label_support": dict(sorted(label_support.items())),
        "max_target_cardinality": max(cardinality),
        "neutral_cooccurrence_rows": neutral_cooccurrence,
        "path": display_path(path),
        "rows": rows,
        "sha256": spec["sha256"],
        "target_stream_sha256": target_stream.hexdigest(),
    }


def verify_data(config: dict[str, Any]) -> dict[str, Any]:
    data = config["data"]
    test_path = resolve_project_path(data["test"]["path"])
    if not data["test"]["must_be_absent"] or test_path.exists():
        raise ValueError("The frozen test-absence gate is not satisfied")
    source_train = verify_artifact(data["source_train"])
    labels = load_labels(config)
    target_contract = data["target_contract"]
    prepared = validate_prepared_jsonl(
        data["prepared_train"],
        labels,
        expected_cardinality=target_contract["cardinality_support"],
        expected_neutral_cooccurrence=int(target_contract["neutral_cooccurrence_rows"]),
    )
    if prepared["target_stream_sha256"] != target_contract["target_stream_sha256"]:
        raise ValueError("Prepared target stream hash drift")
    smoke = validate_prepared_jsonl(
        data["smoke_train"],
        labels,
        expected_cardinality=None,
        expected_neutral_cooccurrence=int(data["smoke_train"]["neutral_cooccurrence_rows"]),
    )
    if not smoke["covers_all_labels"]:
        raise ValueError("Boundary smoke no longer covers every label")
    if smoke["max_target_cardinality"] != int(data["smoke_train"]["max_target_cardinality"]):
        raise ValueError("Boundary-smoke maximum cardinality drift")
    return {
        "labels": {
            "count": len(labels),
            "path": data["labels"]["path"],
            "sha256": data["labels"]["sha256"],
        },
        "prepared_train": prepared,
        "smoke_train": smoke,
        "source_train": artifact(source_train),
        "test_split_absent": True,
    }


def adapter_path(config: dict[str, Any], stage: str, seed: int) -> Path:
    root = resolve_project_path(config["artifacts"]["private_adapter_root"])
    return root / ("smoke" if stage == "smoke" else f"seed-{seed}")


def expected_runtime_config(
    config: dict[str, Any], *, stage: str, seed: int
) -> dict[str, Any]:
    if stage not in ("smoke", "formal"):
        raise ValueError(stage)
    if seed != 42:
        raise ValueError("Only the registered seed 42 is executable in this runner version")
    contract, _ = load_canonical_runtime_contract(config)
    key = "smoke" if stage == "smoke" else "formal_seed_42"
    runtime = json.loads(json.dumps(contract["effective_configs"][key]))
    data_spec = config["data"]["smoke_train" if stage == "smoke" else "prepared_train"]
    expected_paths = {
        "adapter_path": str(adapter_path(config, stage, seed)),
        "data": str(resolve_project_path(data_spec["path"]).parent),
        "model": str(resolve_project_path(config["model"]["local_path"])),
    }
    for field, expected in expected_paths.items():
        if runtime.get(field) != expected:
            raise ValueError(f"Canonical runtime path mismatch: {field}")
    if (
        runtime.get("seed") != seed
        or runtime.get("test") is not False
        or runtime.get("train") is not True
        or runtime.get("val_batches") != 0
    ):
        raise ValueError("Canonical runtime is not the registered train-only seed")
    return runtime


def dry_run_output_paths(config: dict[str, Any]) -> list[Path]:
    artifacts = config["artifacts"]
    return [
        resolve_project_path(artifacts["dry_run_report"]),
        resolve_project_path(artifacts["dry_run_verification"]),
        resolve_project_path(artifacts["smoke_runtime_config"]),
        resolve_project_path(artifacts["formal_runtime_config"]),
        resolve_project_path(artifacts["smoke_report"]),
        resolve_project_path(artifacts["smoke_stdout"]),
        resolve_project_path(artifacts["smoke_history"]),
        resolve_project_path(artifacts["smoke_verification"]),
        resolve_project_path(artifacts["private_adapter_root"]),
        resolve_project_path(artifacts["run_root"]),
    ]


def run_dry_run(config: dict[str, Any]) -> None:
    collisions = [display_path(path) for path in dry_run_output_paths(config) if path.exists()]
    if collisions:
        raise FileExistsError(f"Append-only EXP-033 output already exists: {collisions}")
    protocol_path = verify_artifact(config["artifacts"]["protocol"])

    evidence = verify_evidence_chain(config)
    inheritance = verify_inheritance(config)
    inference_alignment = verify_inference_alignment(config)
    environment = verify_environment(config)
    model = verify_model(config)
    data = verify_data(config)
    runtime_contract, runtime_contract_artifact = load_canonical_runtime_contract(config)
    smoke_runtime = expected_runtime_config(config, stage="smoke", seed=42)
    formal_runtime = expected_runtime_config(config, stage="formal", seed=42)
    for runtime in (smoke_runtime, formal_runtime):
        if runtime["test"] or runtime["val_batches"] != 0 or not runtime["train"]:
            raise ValueError("Generated runtime config is not train-only")
        assert_train_only_directory(Path(runtime["data"]) / "train.jsonl")

    artifacts = config["artifacts"]
    smoke_runtime_path = resolve_project_path(artifacts["smoke_runtime_config"])
    formal_runtime_path = resolve_project_path(artifacts["formal_runtime_config"])
    report_path = resolve_project_path(artifacts["dry_run_report"])
    smoke_runtime_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(smoke_runtime_path, smoke_runtime)
    write_json(formal_runtime_path, formal_runtime)

    report = {
        "accessed_splits": ["train"],
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": artifact(CONFIG_PATH),
        "data": data,
        "evidence_chain": {
            "artifacts": evidence,
            "verified_count": len(evidence),
        },
        "environment": environment,
        "experiment_id": EXPERIMENT_ID,
        "formal_training_authorized": False,
        "implementation": {
            "runner": artifact(Path(__file__).resolve()),
            "verifier": artifact(
                resolve_project_path(config["implementation"]["verifier_path"])
            ),
        },
        "inference_alignment": inference_alignment,
        "inheritance": inheritance,
        "mlx_lora_subprocess_executed": False,
        "model": model,
        "model_forward_or_backward_executed": False,
        "next_required_step": (
            "Independently verify this dry-run, re-run PRE-EXP-033 execution V3 "
            "with --check, then request explicit authorization for the 50-iteration "
            "train-only smoke."
        ),
        "output_boundary": {
            "adapter_root_created": False,
            "formal_run_root_created": False,
            "runtime_configs_only": True,
        },
        "protocol": artifact(protocol_path),
        "runtime_configs": {
            "formal_seed_42": {
                "artifact": artifact(formal_runtime_path),
                "config": formal_runtime,
            },
            "smoke": {
                "artifact": artifact(smoke_runtime_path),
                "config": smoke_runtime,
            },
        },
        "runtime_contract": {
            "artifact": runtime_contract_artifact,
            "contract_id": runtime_contract["contract_id"],
            "formal_training_enabled": runtime_contract["execution_gate"][
                "formal_training_enabled"
            ],
        },
        "smoke_training_authorized": False,
        "stage": "runner-dry-run",
        "status": "Passed",
        "test_split_absent": True,
        "test_split_accessed": False,
        "tier": "Major preflight",
        "validation_split_accessed": False,
    }
    write_json(report_path, report)
    print(json.dumps(report, indent=2, sort_keys=True))


def load_verified_dry_run(config: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    verifier_path = resolve_project_path(config["implementation"]["verifier_path"])
    environment = os.environ.copy()
    environment.update(
        {
            "HF_HUB_OFFLINE": "1",
            "PYTHONNOUSERSITE": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "TRANSFORMERS_OFFLINE": "1",
        }
    )
    checked = subprocess.run(
        [sys.executable, str(verifier_path), "--check"],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if checked.returncode != 0:
        raise RuntimeError(
            "Independent dry-run check failed before authorization: "
            + checked.stderr.strip()
        )
    path = resolve_project_path(config["artifacts"]["dry_run_verification"])
    if not path.is_file():
        raise FileNotFoundError("Independent dry-run verification is required")
    report = json.loads(path.read_text(encoding="utf-8"))
    if (
        report.get("verification_id") != "EXP-033-RUNNER-DRY-RUN-VERIFY-V2"
        or report.get("experiment_id") != EXPERIMENT_ID
        or report.get("status") != "Passed"
        or report.get("model_forward_or_backward_executed") is not False
        or report.get("mlx_lora_subprocess_executed") is not False
        or report.get("test_split_accessed") is not False
        or report.get("validation_split_accessed") is not False
        or report.get("config_sha256") != sha256_file(CONFIG_PATH)
        or report.get("formal_training_authorized") is not False
        or report.get("smoke_training_authorized") is not False
    ):
        raise ValueError("Dry-run verification does not authorize later execution")
    dry_report_path = resolve_project_path(config["artifacts"]["dry_run_report"])
    if report.get("dry_run_report") != artifact(dry_report_path):
        raise ValueError("Dry-run verification is not bound to the current report")
    expected_implementation = {
        "runner": artifact(Path(__file__).resolve()),
        "verifier": artifact(verifier_path),
        "verifier_imports_runner": False,
    }
    if report.get("implementation") != expected_implementation:
        raise ValueError("Dry-run verification implementation binding drift")
    for stage, report_key in (("smoke", "smoke"), ("formal", "formal_seed_42")):
        runtime_path, _ = verify_frozen_runtime_file(config, stage=stage, seed=42)
        if report["recalculated"]["runtime_configs"][report_key]["artifact"] != artifact(
            runtime_path
        ):
            raise ValueError(f"Dry-run verification runtime binding drift: {stage}")
    return path, report


def verify_authorization(
    config: dict[str, Any], authorization_path: Path, *, expected_stage: str
) -> dict[str, Any]:
    if expected_stage == config["authorization_contract"]["formal_stage"]:
        raise RuntimeError(
            "Formal training is hard-disabled in runner contract V2; a new runner "
            "version is required after smoke verification"
        )
    dry_path, dry_verification = load_verified_dry_run(config)
    authorization_path = authorization_path.expanduser().resolve()
    if not authorization_path.is_file():
        raise FileNotFoundError(authorization_path)
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    runtime_stage = (
        "smoke"
        if expected_stage == config["authorization_contract"]["smoke_stage"]
        else "formal"
    )
    runtime_path, _ = verify_frozen_runtime_file(config, stage=runtime_stage, seed=42)
    expected = {
        "authorized": True,
        "config_sha256": sha256_file(CONFIG_PATH),
        "dry_run_verification_path": display_path(dry_path),
        "dry_run_verification_sha256": sha256_file(dry_path),
        "dry_run_verification_id": dry_verification["verification_id"],
        "experiment_id": EXPERIMENT_ID,
        "runtime_config_path": display_path(runtime_path),
        "runtime_config_sha256": sha256_file(runtime_path),
        "stage": expected_stage,
    }
    for key, value in expected.items():
        if authorization.get(key) != value:
            raise ValueError(f"Authorization binding mismatch: {key}")
    return artifact(authorization_path)


def parse_training_log(path: Path) -> tuple[list[dict[str, Any]], dict[str, float]]:
    history: list[dict[str, Any]] = []
    trainable: dict[str, float] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = TRAIN_LOG_PATTERN.search(line)
        if match:
            record: dict[str, Any] = {
                "iteration": int(match.group("iteration")),
                "train_loss": float(match.group("loss")),
                "learning_rate": float(match.group("learning_rate")),
                "iterations_per_second": float(match.group("iterations_per_second")),
                "tokens_per_second": float(match.group("tokens_per_second")),
                "trained_tokens": int(match.group("trained_tokens")),
                "peak_memory_gb": float(match.group("peak_memory_gb")),
            }
            if not all(
                math.isfinite(float(value))
                for key, value in record.items()
                if key not in ("iteration", "trained_tokens")
            ):
                raise ValueError("Training log contains a non-finite value")
            history.append(record)
        trainable_match = TRAINABLE_PATTERN.search(line)
        if trainable_match:
            trainable = {
                "percent": float(trainable_match.group("percent")),
                "total_millions": float(trainable_match.group("total")),
                "trainable_millions": float(trainable_match.group("trainable")),
            }
    if not history or trainable is None:
        raise ValueError("Training log is missing history or trainable-parameter output")
    return history, trainable


def write_history(path: Path, history: list[dict[str, Any]]) -> None:
    if path.exists():
        raise FileExistsError(path)
    fields = [
        "iteration",
        "train_loss",
        "learning_rate",
        "iterations_per_second",
        "tokens_per_second",
        "trained_tokens",
        "peak_memory_gb",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(history)


def adapter_weight_summary(path: Path) -> dict[str, Any]:
    import mlx.core as mx

    weights = mx.load(str(path))
    b_tensors = {name: value for name, value in weights.items() if name.endswith("lora_b")}
    if not b_tensors:
        raise ValueError("Saved adapter has no LoRA B tensors")
    return {
        "lora_b_nonzero_tensors": sum(
            bool(mx.any(value != 0).item()) for value in b_tensors.values()
        ),
        "lora_b_tensor_count": len(b_tensors),
        "tensor_count": len(weights),
        "trainable_parameter_count": int(sum(value.size for value in weights.values())),
    }


def stream_subprocess(
    command: list[str], log_path: Path, timeout_seconds: float
) -> tuple[int, float]:
    started = time.perf_counter()
    environment = os.environ.copy()
    environment.update(
        {
            "HF_HUB_OFFLINE": "1",
            "PYTHONNOUSERSITE": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "TRANSFORMERS_OFFLINE": "1",
        }
    )
    with log_path.open("x", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        output_queue: Queue[str | None] = Queue()

        def read_output() -> None:
            try:
                for line in process.stdout:
                    output_queue.put(line)
            finally:
                output_queue.put(None)

        reader = Thread(target=read_output, name="exp-033-mlx-stdout", daemon=True)
        reader.start()
        try:
            while True:
                elapsed = time.perf_counter() - started
                if elapsed > timeout_seconds:
                    raise TimeoutError("Training exceeded the registered wall-time budget")
                try:
                    line = output_queue.get(timeout=min(1.0, timeout_seconds - elapsed))
                except Empty:
                    continue
                if line is None:
                    break
                log.write(line)
                log.flush()
                print(line, end="", flush=True)
            return_code = process.wait()
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise
        finally:
            reader.join(timeout=5)
    return return_code, time.perf_counter() - started


def git_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--short"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return {"commit": commit, "dirty": dirty}


def verify_frozen_runtime_file(
    config: dict[str, Any], *, stage: str, seed: int
) -> tuple[Path, dict[str, Any]]:
    key = "smoke_runtime_config" if stage == "smoke" else "formal_runtime_config"
    path = resolve_project_path(config["artifacts"][key])
    if not path.is_file():
        raise FileNotFoundError(path)
    observed = json.loads(path.read_text(encoding="utf-8"))
    expected = expected_runtime_config(config, stage=stage, seed=seed)
    if observed != expected:
        raise ValueError(f"Frozen {stage} runtime config drift")
    return path, observed


def run_training(
    config: dict[str, Any], *, stage: str, seed: int, authorization_path: Path
) -> None:
    if stage == "formal" and seed != 42:
        raise ValueError("Seeds 43 and 44 remain closed until the repetition gate is evaluated")
    if stage == "formal":
        raise RuntimeError(
            "Formal training is hard-disabled in runner contract V2; a new runner version "
            "is required after smoke verification"
        )
    expected_authorization_stage = config["authorization_contract"][
        "smoke_stage" if stage == "smoke" else "formal_stage"
    ]
    authorization = verify_authorization(
        config, authorization_path, expected_stage=expected_authorization_stage
    )
    verify_evidence_chain(config)
    verify_inheritance(config)
    verify_inference_alignment(config)
    environment = verify_environment(config)
    model = verify_model(config)
    data = verify_data(config)
    runtime_path, runtime = verify_frozen_runtime_file(config, stage=stage, seed=seed)

    smoke = stage == "smoke"
    adapter_dir = adapter_path(config, stage, seed)
    if smoke:
        record_path = resolve_project_path(config["artifacts"]["smoke_report"])
        log_path = resolve_project_path(config["artifacts"]["smoke_stdout"])
        history_path = resolve_project_path(config["artifacts"]["smoke_history"])
        run_dir = None
    else:
        run_dir = resolve_project_path(config["artifacts"]["run_root"]) / f"seed-{seed}"
        record_path = run_dir / "run.json"
        log_path = run_dir / "stdout.log"
        history_path = run_dir / "history.csv"
    collision_candidates = [adapter_dir, record_path, log_path, history_path]
    if run_dir is not None:
        collision_candidates.append(run_dir)
    collisions = [path for path in collision_candidates if path.exists()]
    if collisions:
        raise FileExistsError(f"Append-only training output already exists: {collisions}")
    repository_state = git_state()
    if run_dir is None:
        record_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
    adapter_dir.mkdir(parents=True, exist_ok=False)

    cli_path = Path(config["runtime"]["mlx_lora_cli"]["path"])
    command = [str(cli_path), "-c", str(runtime_path)]
    started_at = datetime.now(timezone.utc)
    initial_record: dict[str, Any] = {
        "accessed_splits": ["train"],
        "authorization": authorization,
        "command": command,
        "config": artifact(CONFIG_PATH),
        "experiment_id": EXPERIMENT_ID,
        "git": repository_state,
        "seed": seed,
        "smoke": smoke,
        "stage": "train-only-smoke" if smoke else "formal-train-only",
        "started_at_utc": started_at.isoformat(),
        "status": "In Progress",
        "test_split_accessed": False,
        "tier": "Minor preflight" if smoke else "Major",
        "validation_split_accessed": False,
    }
    write_json(record_path, initial_record)

    try:
        timeout_minutes = (
            float(config["preflight"]["smoke_wall_time_minutes_max"])
            if smoke
            else float(config["resource_budget"]["training_wall_time_hours_max_per_seed"])
            * 60
        )
        return_code, elapsed = stream_subprocess(
            command, log_path, timeout_seconds=timeout_minutes * 60
        )
        if return_code != 0:
            raise RuntimeError(f"MLX-LM training exited with status {return_code}")
        adapter_file = adapter_dir / "adapters.safetensors"
        adapter_config = adapter_dir / "adapter_config.json"
        if not adapter_file.is_file() or not adapter_config.is_file():
            raise FileNotFoundError("Training did not save the final adapter")
        history, trainable = parse_training_log(log_path)
        expected_iteration = int(runtime["iters"])
        if history[-1]["iteration"] != expected_iteration:
            raise ValueError("Training history does not end at the registered iteration")
        max_peak = max(float(row["peak_memory_gb"]) for row in history)
        if max_peak > float(config["resource_budget"]["peak_mlx_memory_gb_max"]):
            raise MemoryError("Training exceeded the registered MLX memory budget")
        weights = adapter_weight_summary(adapter_file)
        if weights["trainable_parameter_count"] != int(
            config["preflight"]["expected_trainable_parameters"]
        ):
            raise ValueError("Saved adapter trainable-parameter count drift")
        if weights["lora_b_nonzero_tensors"] != weights["lora_b_tensor_count"]:
            raise ValueError("At least one trained LoRA B tensor remained entirely zero")
        write_history(history_path, history)

        completed: dict[str, Any] = {
            **initial_record,
            "adapter": {
                "config": artifact(adapter_config),
                "weights": artifact(adapter_file),
                **weights,
            },
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "data": data["smoke_train" if smoke else "prepared_train"],
            "duration_seconds": elapsed,
            "environment": environment,
            "history": artifact(history_path),
            "model": model,
            "peak_mlx_memory_gb": max_peak,
            "runtime_config": artifact(runtime_path),
            "status": "Completed" if not smoke else "Pending smoke gates",
            "stdout": artifact(log_path),
            "trainable_parameters_reported": trainable,
        }
        if smoke:
            initial_window = statistics.mean(row["train_loss"] for row in history[:2])
            final_window = statistics.mean(row["train_loss"] for row in history[-2:])
            full_reports = [
                row
                for row in history
                if row["iteration"] % int(runtime["steps_per_report"]) == 0
            ]
            if not full_reports:
                raise ValueError("Smoke log has no complete reporting interval")
            median_rate = statistics.median(
                row["iterations_per_second"] for row in full_reports
            )
            projected_hours = int(config["training"]["iterations"]) / median_rate / 3600
            passed = (
                final_window <= initial_window * 1.25
                and projected_hours
                <= float(config["resource_budget"]["training_wall_time_hours_max_per_seed"])
            )
            completed.update(
                {
                    "final_loss_window": final_window,
                    "initial_loss_window": initial_window,
                    "median_iterations_per_second": median_rate,
                    "projected_formal_training_hours": projected_hours,
                    "status": "Passed" if passed else "Failed",
                }
            )
            if not passed:
                write_json(record_path, completed)
                raise RuntimeError("Train-only smoke failed the loss or time gate")
        write_json(record_path, completed)
        print(json.dumps(completed, indent=2, sort_keys=True))
    except BaseException as error:
        failed = json.loads(record_path.read_text(encoding="utf-8"))
        if failed.get("status") not in ("Failed", "Passed"):
            failed.update(
                {
                    "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                    "error": {"message": str(error), "traceback": traceback.format_exc()},
                    "status": "Failed",
                }
            )
            write_json(record_path, failed)
        raise


def main() -> None:
    args = parse_args()
    config = load_config()
    if args.command == "dry-run":
        run_dry_run(config)
    elif args.command == "smoke":
        run_training(
            config,
            stage="smoke",
            seed=42,
            authorization_path=args.authorization,
        )
    elif args.command == "train":
        run_training(
            config,
            stage="formal",
            seed=args.seed,
            authorization_path=args.authorization,
        )
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()
