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


def resolve_project(relative: str) -> Path:
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
    if not path.is_file() or path.stat().st_nlink != 1:
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


def validate_parent_failure(config: dict[str, Any], source_config: dict[str, Any]) -> None:
    config_record = config["parent_failure"]["config"]
    claim_path = require_record(config["parent_failure"]["claim"])
    run_path = require_record(config["parent_failure"]["run"])
    private_root = PROJECT_ROOT / (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
        "exp-069-representation-extraction-preflight/attempt-2-base-smoke"
    )
    if inventory(claim_path.parent) != {"run-claim.json", "run.json"} or inventory(private_root):
        raise ValueError("Attempt-2 failure inventory drift")
    if file_mode(claim_path.parent) != "0755" or file_mode(private_root) != "0700":
        raise PermissionError("Attempt-2 failure root mode drift")
    for path in (claim_path, run_path):
        if path.is_symlink() or path.stat().st_nlink != 1 or file_mode(path) != "0644":
            raise PermissionError("Attempt-2 failure file mode/link drift")
    claim = strict_json(claim_path)
    if set(claim) != {
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
    } or (
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
        raise PermissionError("Attempt-3 verifier requires the frozen config")
    config = strict_json(path)
    if (
        config.get("schema_version") != "exp-069-base-smoke-attempt-3-v1"
        or config.get("experiment_id") != "EXP-069"
        or config.get("attempt_id") != ATTEMPT_ID
    ):
        raise ValueError("Attempt-3 verifier config drift")
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
        raise ValueError("Attempt-3 verifier authorization drift")
    for record in config["parent_failure"].values():
        require_record(record)
    for record in config["implementation"].values():
        require_record(record)
    require_record(config["source_consumer"])
    require_record(config["source_verifier"])
    if config["outputs"] != {"public_root": PUBLIC_ROOT, "private_root": PRIVATE_ROOT}:
        raise ValueError("Attempt-3 verifier output root drift")
    return config


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


def verify(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    source_verifier = load_module(
        "exp069_attempt2_independent_verifier", require_record(config["source_verifier"])
    )
    source_config = strict_json(require_record(config["parent_failure"]["config"]))
    if source_config.get("schema_version") != "exp-069-base-smoke-attempt-2-v1":
        raise ValueError("Attempt-2 source config schema drift")
    if config["source_consumer"] != source_config["implementation"]["runner"]:
        raise ValueError("Attempt-3 verifier source consumer drift")
    if config["source_verifier"] != source_config["implementation"]["verifier"]:
        raise ValueError("Attempt-3 verifier source verifier drift")
    for key in ("authorization", "parent_static", "source_runner", "environment", "smoke", "resources"):
        if config[key] != source_config[key]:
            raise ValueError(f"Attempt-3 verifier unchanged contract drift: {key}")
    validate_parent_failure(config, source_config)
    source_verifier.ATTEMPT_ID = ATTEMPT_ID
    view = continuation_view(config, source_config)
    try:
        return source_verifier.verify(config_path, view)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        source_verifier.record_failure(view, error)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify EXP-069 base-smoke directory recovery")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> None:
    config = load_config(parse_args().config)
    result = verify(DEFAULT_CONFIG, config)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
