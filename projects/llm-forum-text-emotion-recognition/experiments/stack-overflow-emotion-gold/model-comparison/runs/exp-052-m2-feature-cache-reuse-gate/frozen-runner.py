#!/usr/bin/env python3
"""Freeze the verified EXP-052 seed-42 feature cache for read-only reuse."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import traceback
from typing import Any

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]
ALLOWED_SPLITS = ("train", "validation")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path)
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def resolve_project(recorded: str) -> Path:
    path = Path(recorded)
    resolved = path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()
    if resolved != PROJECT_ROOT and PROJECT_ROOT not in resolved.parents:
        raise ValueError(f"Path escapes project root: {recorded}")
    return resolved


def project_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": project_path(path),
        "sha256": sha256_file(path),
    }


def require_artifact(record: dict[str, Any]) -> Path:
    path = resolve_project(record["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != int(record["bytes"]):
        raise ValueError(f"Byte-size mismatch for {path}")
    observed = sha256_file(path)
    if observed != record["sha256"]:
        raise ValueError(f"Hash mismatch for {path}: {observed}")
    return path


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def load_split_rows(shared: dict[str, Any], split: str) -> list[dict[str, Any]]:
    if split not in ALLOWED_SPLITS:
        raise PermissionError(f"Feature-cache gate cannot access split: {split}")
    path = resolve_project(shared["data"][f"{split}_path"])
    if sha256_file(path) != shared["data"][f"{split}_sha256"]:
        raise ValueError(f"{split} data hash drift")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if len(rows) != int(shared["data"][f"{split}_rows"]):
        raise ValueError(f"{split} row-count drift")
    return rows


def validate_cache_array(
    record: dict[str, Any], *, expected_shape: tuple[int, int]
) -> tuple[np.memmap, dict[str, Any]]:
    path = require_artifact(record)
    array = np.load(path, mmap_mode="r", allow_pickle=False)
    if tuple(array.shape) != expected_shape:
        raise ValueError(f"Feature shape drift for {path}: {array.shape}")
    if array.dtype != np.float32:
        raise ValueError(f"Feature dtype drift for {path}: {array.dtype}")
    if array.flags.writeable:
        raise PermissionError(f"Feature cache was not opened read-only: {path}")
    if not np.isfinite(array).all():
        raise ValueError(f"Non-finite feature cache: {path}")
    return array, {
        **artifact(path),
        "shape": list(array.shape),
        "dtype": str(array.dtype),
        "all_finite": True,
        "mmap_mode": "r",
        "writeable": False,
    }


def gitignored(path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(path)], cwd=REPO_ROOT, check=False
    )
    return result.returncode == 0


def git_metadata() -> dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()

    status = git("status", "--short")
    return {
        "branch": git("branch", "--show-current") or "detached",
        "commit": git("rev-parse", "HEAD"),
        "dirty": bool(status),
        "dirty_path_count": len(status.splitlines()) if status else 0,
    }


def validate_authorization(config: dict[str, Any]) -> None:
    if config.get("experiment_id") != "EXP-052":
        raise ValueError("Unexpected experiment identity")
    if config.get("stage") != "feature-cache-reuse-integrity-gate":
        raise ValueError("Unexpected gate stage")
    authorization = config["authorization"]
    required_false = (
        "training_authorized",
        "performance_metrics_authorized",
        "test_access",
        "consumer_seeds_authorized",
        "exp_053_054_authorized",
    )
    if any(authorization.get(field) is not False for field in required_false):
        raise PermissionError("Cache gate cannot authorize training, metrics, test, or later models")
    if authorization.get("source_seed") != 42 or authorization.get("candidate_consumers") != [43, 44]:
        raise PermissionError("Unexpected source or consumer seed registry")


def freeze_sources(
    run_dir: Path, config: dict[str, Any], config_path: Path
) -> dict[str, Any]:
    sources = {"config": config_path.resolve()}
    for name, record in config["implementation"].items():
        path = resolve_project(record["path"])
        if sha256_file(path) != record["sha256"]:
            raise ValueError(f"Implementation hash drift: {name}")
        sources[name] = path
    frozen: dict[str, Any] = {}
    for name, source in sources.items():
        target = run_dir / f"frozen-{name}{source.suffix}"
        shutil.copy2(source, target)
        frozen[name] = artifact(target)
    return frozen


def validate_source_chain(
    config: dict[str, Any], shared: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = config["source_seed_42"]
    run_path = require_artifact(source["run"])
    verification_path = require_artifact(source["verification"])
    run = json.loads(run_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    if (
        run.get("status") != "Completed"
        or run.get("experiment_id") != "EXP-052"
        or run.get("seed") != 42
        or run.get("stage") != "seed-42-train-validation-integrity-gate"
    ):
        raise RuntimeError("Source EXP-052 seed-42 run is not the frozen completed gate")
    if run.get("accessed_splits") != ["train", "validation"] or run.get("test_split_accessed") is not False:
        raise PermissionError("Source split-access record drift")
    if (
        verification.get("status") != "Passed"
        or verification.get("check_count") != 70
        or verification.get("failed_checks")
        or verification.get("test_split_accessed") is not False
    ):
        raise RuntimeError("Source EXP-052 seed-42 verification is not 70/70 Passed")
    if run["data"]["train"]["sha256"] != shared["data"]["train_sha256"]:
        raise ValueError("Source train hash differs from shared contract")
    if run["data"]["validation"]["sha256"] != shared["data"]["validation_sha256"]:
        raise ValueError("Source validation hash differs from shared contract")
    if run["model"]["repo_id"] != shared["models"]["qwen_shared"]["repo_id"]:
        raise ValueError("Source model identity drift")
    if run["model"]["revision"] != shared["models"]["qwen_shared"]["revision"]:
        raise ValueError("Source model revision drift")
    if run["model_runtime"]["pooling"] != shared["prompt"]["pooling"]:
        raise ValueError("Source pooling drift")
    if run["model_runtime"]["feature_dtype"] != "float32":
        raise ValueError("Source cache dtype contract drift")
    return run, verification


def build_gate(config: dict[str, Any], config_path: Path, run_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    validate_authorization(config)
    shared_path = require_artifact(config["shared_contract"])
    shared = json.loads(shared_path.read_text(encoding="utf-8"))
    if shared["data"]["model_access_whitelist"] != ["train", "validation"]:
        raise PermissionError("Shared data allowlist drift")
    if shared["data"]["test_status"] != "sealed_not_authorized_for_model_access":
        raise PermissionError("Shared contract no longer seals test")
    source_run, source_verification = validate_source_chain(config, shared)

    cache_results: dict[str, Any] = {}
    for split in ALLOWED_SPLITS:
        expected = config["feature_cache"][split]
        source_metadata = source_run["feature_cache"][split]
        source_artifact = source_run["artifacts"][f"{split}_features_private"]
        if expected["artifact"] != source_artifact or expected["artifact"] != source_metadata["feature"]:
            raise ValueError(f"{split} cache provenance differs from source run")
        rows = load_split_rows(shared, split)
        order_digest = canonical_digest([row["sample_id"] for row in rows])
        if order_digest != expected["sample_order_sha256"] or order_digest != source_metadata["sample_order_sha256"]:
            raise ValueError(f"{split} sample-order digest drift")
        if expected["token_id_stream_sha256"] != source_metadata["token_id_stream_sha256"]:
            raise ValueError(f"{split} token-stream digest drift")
        array, validated = validate_cache_array(
            expected["artifact"], expected_shape=tuple(expected["shape"])
        )
        if not gitignored(resolve_project(expected["artifact"]["path"])):
            raise PermissionError(f"{split} cache is not Git ignored")
        cache_results[split] = {
            **validated,
            "rows": len(rows),
            "sample_order_sha256": order_digest,
            "token_id_stream_sha256": expected["token_id_stream_sha256"],
            "gold_labels_used_for_features": False,
            "source_seed": 42,
        }
        del array

    source_manifest = require_artifact(config["source_seed_42"]["private_manifest"])
    frozen_sources = freeze_sources(run_dir, config, config_path)
    return {
        "schema_version": "exp-052-feature-cache-reuse-gate-v1",
        "experiment_id": "EXP-052",
        "rq_id": "RQ-S1",
        "tier": "Major infrastructure gate",
        "stage": "feature-cache-reuse-integrity-gate",
        "status": "Completed",
        "completed_at_utc": utc_now(),
        "authorization": config["authorization"],
        "accessed_splits": ["train", "validation"],
        "validation_split_accessed": True,
        "test_split_accessed": False,
        "training_performed": False,
        "performance_metrics_computed": False,
        "qwen_forward_executed": False,
        "source_seed_42": {
            "run": artifact(resolve_project(config["source_seed_42"]["run"]["path"])),
            "verification": artifact(resolve_project(config["source_seed_42"]["verification"]["path"])),
            "verification_check_count": source_verification["check_count"],
            "private_manifest": artifact(source_manifest),
        },
        "frozen_contract": {
            "data_protocol": shared["data"]["protocol_id"],
            "model_repo_id": shared["models"]["qwen_shared"]["repo_id"],
            "model_revision": shared["models"]["qwen_shared"]["revision"],
            "model_manifest_sha256": shared["models"]["qwen_shared"]["manifest_sha256"],
            "precision": shared["models"]["qwen_shared"]["precision"],
            "prompt_sha256": shared["prompt"]["sha256"],
            "chat_template_sha256": shared["prompt"]["chat_template_sha256"],
            "tokenizer_asset_sha256": shared["prompt"]["tokenizer_asset_sha256"],
            "enable_thinking": shared["prompt"]["enable_thinking"],
            "input_view": shared["prompt"]["input_view"],
            "max_sequence_length": shared["prompt"]["max_sequence_length"],
            "truncation": shared["prompt"]["truncation"],
            "pooling": shared["prompt"]["pooling"],
            "feature_dtype": "float32",
        },
        "feature_cache": cache_results,
        "consumer_contract": {
            "candidate_seeds": [43, 44],
            "training_authorized_by_this_gate": False,
            "allowed_experiment": "EXP-052 M2 only",
            "read_mode": "numpy mmap_mode=r",
            "hash_before_and_after_use": True,
            "seed_specific_artifacts_must_be_new": [
                "head initialization",
                "batch order",
                "optimizer state",
                "checkpoints",
                "validation probabilities",
                "bootstrap",
            ],
            "forbidden_consumers": ["EXP-053", "EXP-054", "context", "router", "test"],
        },
        "privacy": {
            "public_raw_text": False,
            "public_row_identifiers": False,
            "feature_cache": "private_gitignored_representation_may_encode_source_text",
        },
        "git": git_metadata(),
        "resource_usage": {"wall_seconds": time.perf_counter() - started, "api_cost_usd": 0},
        "artifacts": {"frozen_sources": frozen_sources},
    }


def render_report(run: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# EXP-052 Feature-cache Reuse Gate",
            "",
            f"- Status: `{run['status']}`; independent verification pending",
            "- Source: verified EXP-052 seed 42 train/validation feature cache",
            "- Training performed: no",
            "- Performance metrics computed: no",
            "- Qwen forward executed: no",
            "- Test accessed: no",
            "- Candidate consumers after separate authorization: seeds 43 and 44",
            "- M3/M4 cache reuse: forbidden",
            "",
        ]
    )


def run() -> dict[str, Any]:
    args = parse_args()
    config_path = args.config.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    run_dir = (args.run_dir or resolve_project(config["execution"]["public_run_dir"])).resolve()
    if run_dir.exists():
        raise FileExistsError(f"Refusing to overwrite append-only gate output: {run_dir}")
    run_dir.mkdir(parents=True)
    run_path = run_dir / "run.json"
    initial = {
        "schema_version": "exp-052-feature-cache-reuse-gate-v1",
        "experiment_id": "EXP-052",
        "stage": config.get("stage"),
        "status": "Running",
        "started_at_utc": utc_now(),
        "accessed_splits": [],
        "validation_split_accessed": False,
        "test_split_accessed": False,
        "training_performed": False,
        "performance_metrics_computed": False,
    }
    atomic_json(run_path, initial)
    try:
        completed = build_gate(config, config_path, run_dir)
        report_path = run_dir / "REPORT.md"
        report_path.write_text(render_report(completed), encoding="utf-8")
        completed["artifacts"]["report"] = artifact(report_path)
        atomic_json(run_path, completed)
        return completed
    except Exception as error:
        initial.update(
            {
                "status": "Failed",
                "failed_at_utc": utc_now(),
                "failure": {
                    "type": type(error).__name__,
                    "message": str(error),
                    "traceback": traceback.format_exc(),
                },
            }
        )
        atomic_json(run_path, initial)
        raise


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
