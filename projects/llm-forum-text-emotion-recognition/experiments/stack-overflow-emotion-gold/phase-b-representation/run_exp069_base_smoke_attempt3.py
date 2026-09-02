#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
DEFAULT_CONFIG = MODULE_DIR / "configs" / "exp-069-base-smoke-attempt-3.json"
ATTEMPT_ID = "attempt-3-base-smoke"
PUBLIC_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
    "exp-069-representation-extraction-preflight/attempt-3-base-smoke"
)
PRIVATE_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
    "exp-069-representation-extraction-preflight/attempt-3-base-smoke"
)


def _no_constant(value: str) -> Any:
    raise ValueError(f"Non-finite JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_no_constant,
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def resolve_project(relative: str, *, must_exist: bool = True) -> Path:
    pure = PurePosixPath(relative)
    if type(relative) is not str or not relative or pure.is_absolute() or pure.as_posix() != relative:
        raise ValueError("Unsafe project path")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("Unsafe project path")
    path = PROJECT_ROOT.joinpath(*pure.parts)
    current = PROJECT_ROOT
    for part in pure.parts:
        current = current / part
        if os.path.lexists(current) and current.is_symlink():
            raise ValueError("Symlink path rejected")
    if must_exist and (not path.is_file() or path.stat().st_nlink != 1):
        raise ValueError("Unsafe or missing input")
    return path


def observed_artifact(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "mode": file_mode(path),
        "sha256": sha256(path),
    }


def require_record(record: dict[str, Any]) -> Path:
    if set(record) != {"path", "bytes", "mode", "sha256"}:
        raise ValueError("Artifact record schema drift")
    path = resolve_project(record["path"])
    if observed_artifact(path) != record:
        raise ValueError(f"Artifact identity drift: {record['path']}")
    return path


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inventory(root: Path) -> set[str]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Invalid attempt output root")
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


def validate_config(config: dict[str, Any]) -> None:
    expected = {
        "schema_version",
        "experiment_id",
        "attempt_id",
        "rq_id",
        "tier",
        "registered_at",
        "authorization",
        "parent_failure",
        "source_consumer",
        "source_verifier",
        "implementation",
        "environment",
        "parent_static",
        "source_runner",
        "smoke",
        "resources",
        "outputs",
        "claim_boundary",
    }
    if set(config) != expected:
        raise ValueError("Attempt-3 config schema drift")
    if (
        config["schema_version"] != "exp-069-base-smoke-attempt-3-v1"
        or config["experiment_id"] != "EXP-069"
        or config["attempt_id"] != ATTEMPT_ID
        or config["rq_id"] != "RQ-S4"
    ):
        raise ValueError("Attempt-3 config identity drift")
    if config["authorization"] != {
        "base_smoke_authorized": True,
        "model_loading_authorized": True,
        "forward_authorized": True,
        "fold_smoke_authorized": False,
        "assemble_authorized": False,
        "training_authorized": False,
        "performance_metrics_authorized": False,
        "validation_access": False,
        "test_access": False,
    }:
        raise ValueError("Attempt-3 authorization drift")
    for key in ("public_root", "private_root"):
        resolve_project(config["outputs"][key], must_exist=False)
    if config["outputs"] != {"public_root": PUBLIC_ROOT, "private_root": PRIVATE_ROOT}:
        raise ValueError("Attempt-3 output root drift")


def validate_parent_failure(config: dict[str, Any], source_config: dict[str, Any]) -> None:
    config_record = config["parent_failure"]["config"]
    claim_path = require_record(config["parent_failure"]["claim"])
    run_path = require_record(config["parent_failure"]["run"])
    public_root = claim_path.parent
    private_root = PROJECT_ROOT / (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
        "exp-069-representation-extraction-preflight/attempt-2-base-smoke"
    )
    if inventory(public_root) != {"run-claim.json", "run.json"}:
        raise ValueError("Attempt-2 public failure inventory drift")
    if file_mode(public_root) != "0755" or file_mode(private_root) != "0700":
        raise PermissionError("Attempt-2 failure root mode drift")
    if inventory(private_root):
        raise ValueError("Attempt-2 private failure inventory is not empty")
    for path in (claim_path, run_path):
        if path.is_symlink() or path.stat().st_nlink != 1 or file_mode(path) != "0644":
            raise PermissionError("Attempt-2 failure file mode/link drift")
    claim = strict_json(claim_path)
    expected_claim_keys = {
        "schema_version",
        "experiment_id",
        "attempt_id",
        "status",
        "config",
        "parent_static_verification",
        "authorized_stage",
        "fold_smoke_authorized",
        "assemble_authorized",
        "claim_boundary",
    }
    if set(claim) != expected_claim_keys or (
        claim["schema_version"] != "exp-069-base-smoke-claim-v1"
        or claim["experiment_id"] != "EXP-069"
        or claim["attempt_id"] != "attempt-2-base-smoke"
        or claim["status"] != "Claimed"
        or claim["config"] != config_record
        or claim["parent_static_verification"] != source_config["parent_static"]["static_verification"]
        or claim["authorized_stage"] != "base-smoke"
        or claim["fold_smoke_authorized"] is not False
        or claim["assemble_authorized"] is not False
        or claim["claim_boundary"] != source_config["claim_boundary"]
    ):
        raise ValueError("Attempt-2 claim lineage drift")
    failure = strict_json(run_path)
    if set(failure) != {
        "schema_version",
        "experiment_id",
        "attempt_id",
        "claim_boundary",
        "error_type",
        "stage",
        "status",
    } or (
        failure["schema_version"] != "exp-069-base-smoke-failure-v1"
        or failure["experiment_id"] != "EXP-069"
        or failure["attempt_id"] != "attempt-2-base-smoke"
        or failure["claim_boundary"] != source_config["claim_boundary"]
        or failure["error_type"] != "FileNotFoundError"
        or failure["stage"] != "base-smoke"
        or failure["status"] != "Failed"
    ):
        raise ValueError("Attempt-2 failure lineage drift")


def load_config(path: Path) -> dict[str, Any]:
    if path.resolve() != DEFAULT_CONFIG.resolve():
        raise PermissionError("Attempt-3 requires the frozen config")
    value = strict_json(path)
    validate_config(value)
    return value


def require_inputs(config: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    for record in config["parent_failure"].values():
        require_record(record)
    for record in config["implementation"].values():
        require_record(record)
    source_consumer_path = require_record(config["source_consumer"])
    require_record(config["source_verifier"])
    consumer = load_module("exp069_attempt2_consumer", source_consumer_path)
    source_config = consumer.load_config(require_record(config["parent_failure"]["config"]))
    if config["source_consumer"] != source_config["implementation"]["runner"]:
        raise ValueError("Attempt-3 source consumer drift")
    if config["source_verifier"] != source_config["implementation"]["verifier"]:
        raise ValueError("Attempt-3 source verifier drift")
    for key in ("authorization", "parent_static", "source_runner", "environment", "smoke", "resources"):
        if config[key] != source_config[key]:
            raise ValueError(f"Attempt-3 unchanged contract drift: {key}")
    validate_parent_failure(config, source_config)
    return consumer, source_config


def install_directory_adapter(consumer: Any, source_config: dict[str, Any]) -> None:
    original_loader = consumer.load_source_runner
    base_relative = strict_json(require_record(source_config["parent_static"]["config"]))["model"][
        "base_path"
    ]

    def adapted_loader(config: dict[str, Any]) -> Any:
        source = original_loader(config)
        original_resolver = source.resolve_project

        def adapted_resolver(relative: str, *, must_exist: bool = True) -> Path:
            if relative != base_relative:
                return original_resolver(relative, must_exist=must_exist)
            candidate = original_resolver(relative, must_exist=False)
            if must_exist and (not candidate.is_dir() or candidate.is_symlink()):
                raise FileNotFoundError(candidate)
            return candidate

        source.resolve_project = adapted_resolver
        return source

    consumer.load_source_runner = adapted_loader


def continuation_view(config: dict[str, Any], source_config: dict[str, Any]) -> dict[str, Any]:
    view = dict(source_config)
    for key in (
        "authorization",
        "parent_static",
        "source_runner",
        "implementation",
        "environment",
        "smoke",
        "resources",
        "outputs",
        "claim_boundary",
    ):
        view[key] = config[key]
    return view


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EXP-069 base-smoke directory recovery")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--stage", required=True, choices=("base-smoke",))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config: dict[str, Any] = {}
    consumer: Any = None
    view: dict[str, Any] = {}
    try:
        config = load_config(args.config)
        consumer, source_config = require_inputs(config)
        install_directory_adapter(consumer, source_config)
        consumer.ATTEMPT_ID = ATTEMPT_ID
        view = continuation_view(config, source_config)
        result = consumer.execute(args.config, view)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        if consumer is not None and view:
            consumer.record_failure(view, error)
        raise


if __name__ == "__main__":
    main()
