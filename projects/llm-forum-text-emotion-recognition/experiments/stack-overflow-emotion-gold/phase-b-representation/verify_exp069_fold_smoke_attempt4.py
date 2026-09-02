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
DEFAULT_CONFIG = MODULE_DIR / "configs" / "exp-069-fold-smoke-attempt-4.json"
ATTEMPT_ID = "attempt-4-fold-smoke"
RUN_ID = "exp-069-representation-extraction-preflight"
PUBLIC_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
    "exp-069-representation-extraction-preflight/attempt-4-fold-smoke"
)
PRIVATE_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
    "exp-069-representation-extraction-preflight/attempt-4-fold-smoke"
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


def require_copied(record: dict[str, Any], path: Path, expected_mode: str) -> None:
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_nlink != 1
        or file_mode(path) != expected_mode
        or path.stat().st_size != record["bytes"]
        or sha256(path) != record["sha256"]
    ):
        raise ValueError(f"Attempt-4 copied evidence drift: {path.name}")


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_config(path: Path) -> dict[str, Any]:
    if path.resolve() != DEFAULT_CONFIG.resolve():
        raise PermissionError("Attempt-4 verifier requires the frozen config")
    config = strict_json(path)
    if (
        config.get("schema_version") != "exp-069-fold-smoke-attempt-4-v1"
        or config.get("experiment_id") != "EXP-069"
        or config.get("attempt_id") != ATTEMPT_ID
    ):
        raise ValueError("Attempt-4 verifier config drift")
    if config["scope"] != {
        "base_smoke": False,
        "fold_smoke": True,
        "assemble": True,
        "exp070": False,
    }:
        raise ValueError("Attempt-4 verifier scope drift")
    if config["outputs"] != {"public_root": PUBLIC_ROOT, "private_root": PRIVATE_ROOT}:
        raise ValueError("Attempt-4 verifier output root drift")
    if config["authorization"] != {
        "design_authorized": True,
        "static_execution_authorized": False,
        "smoke_execution_authorized": True,
        "model_loading_authorized": True,
        "forward_authorized": True,
        "training_authorized": False,
        "performance_metrics_authorized": False,
        "validation_access": False,
        "test_access": False,
    }:
        raise ValueError("Attempt-4 verifier authorization drift")
    for group in ("parent_static", "parent_base"):
        for record in config[group].values():
            require_record(record)
    for key in ("source_runner", "source_verifier"):
        require_record(config[key])
    for record in config["implementation"].values():
        require_record(record)
    parent_config = strict_json(require_record(config["parent_static"]["config"]))
    if config["source_runner"] != parent_config["implementation"]["runner"]:
        raise ValueError("Attempt-4 verifier source runner drift")
    if config["source_verifier"] != parent_config["implementation"]["verifier"]:
        raise ValueError("Attempt-4 verifier source verifier drift")
    for key in ("environment", "smoke", "resources"):
        if config[key] != parent_config[key]:
            raise ValueError(f"Attempt-4 verifier unchanged contract drift: {key}")
    return config


def continuation_view(config: dict[str, Any], parent: dict[str, Any]) -> dict[str, Any]:
    view = dict(parent)
    for key in ("authorization", "environment", "smoke", "resources", "claim_boundary"):
        view[key] = config[key]
    outputs = dict(parent["outputs"])
    outputs.update(config["outputs"])
    view["outputs"] = outputs
    view["implementation"] = config["implementation"]
    view["attempt_id"] = ATTEMPT_ID
    return view


def verify(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    parent_config_path = require_record(config["parent_static"]["config"])
    parent_config = strict_json(parent_config_path)
    root_public = PROJECT_ROOT / PUBLIC_ROOT
    root_private = PROJECT_ROOT / PRIVATE_ROOT
    if (
        root_public.is_symlink()
        or root_private.is_symlink()
        or file_mode(root_public) != "0755"
        or file_mode(root_private) != "0700"
    ):
        raise PermissionError("Attempt-4 verifier root mode/link drift")
    if any(
        path.is_symlink()
        for root in (root_public, root_private)
        for path in root.rglob("*")
    ):
        raise PermissionError("Attempt-4 verifier nested symlink drift")
    private_dirs = {
        path.relative_to(root_private).as_posix()
        for path in root_private.rglob("*")
        if path.is_dir()
    }
    if private_dirs != {"seed-42", "seed-43", "seed-44"}:
        raise ValueError("Attempt-4 verifier private directory inventory drift")
    for relative in private_dirs:
        path = root_private / relative
        if path.is_symlink() or file_mode(path) != "0700":
            raise PermissionError("Attempt-4 verifier seed-directory mode/link drift")
    require_copied(config["parent_static"]["static_run"], root_public / "static.json", "0644")
    require_copied(
        config["parent_static"]["static_verification"],
        root_public / "static-verification.json",
        "0644",
    )
    require_copied(
        config["parent_static"]["input_manifest"],
        root_private / "input-manifest.json",
        "0600",
    )
    require_copied(config["parent_base"]["base"], root_private / "base.npz", "0600")
    require_copied(
        config["parent_base"]["base_worker"], root_private / "base-worker.json", "0600"
    )
    base_run_path = require_record(config["parent_base"]["run"])
    base_verification_path = require_record(config["parent_base"]["verification"])
    base_completion = strict_json(require_record(config["parent_base"]["completion"]))
    if (
        base_completion.get("status") != "Complete"
        or base_completion.get("base_smoke_complete") is not True
        or base_completion.get("exp069_complete") is not False
        or base_completion.get("run") != observed_artifact(base_run_path)
        or base_completion.get("verification") != observed_artifact(base_verification_path)
    ):
        raise ValueError("Attempt-4 verifier parent-base binding drift")
    source_verifier = load_module(
        "exp069_attempt1_independent_verifier", require_record(config["source_verifier"])
    )
    source_verifier.ATTEMPT_ID = ATTEMPT_ID
    source_verifier.DEFAULT_CONFIG = config_path
    view = continuation_view(config, parent_config)
    current_config = source_verifier.observed_artifact(config_path)
    parent_config_record = config["parent_static"]["config"]
    claim_path = root_public / "run-claim.json"
    if (
        claim_path.is_symlink()
        or not claim_path.is_file()
        or claim_path.stat().st_nlink != 1
        or file_mode(claim_path) != "0644"
    ):
        raise ValueError("Attempt-4 verifier run claim mode/link drift")
    expected_claim = {
        "schema_version": "exp-069-run-claim-v1",
        "experiment_id": config["experiment_id"],
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "Claimed",
        "config": current_config,
        "workers": 16,
        "model_loading_authorized": True,
        "smoke_execution_authorized": True,
        "claim_boundary": config["claim_boundary"],
    }
    if strict_json(claim_path) != expected_claim:
        raise ValueError("Attempt-4 verifier run claim binding drift")

    def chained_binding(path: Path, *records: dict[str, Any]) -> None:
        if path.resolve() != config_path.resolve() or len(records) != 4:
            raise ValueError("Attempt-4 config-binding call drift")
        expected = (parent_config_record, parent_config_record, current_config, current_config)
        if records != expected:
            raise ValueError("Attempt-4 config-binding lineage drift")

    source_verifier.require_config_binding = chained_binding
    original_access_check = source_verifier.require_exact_access

    def compatible_access(observed: Any, expected: dict[str, Any], label: str) -> None:
        if label == "Base worker":
            compatible = dict(expected)
            compatible["m3_artifacts_accessed"] = False
            if observed == compatible:
                return
        original_access_check(observed, expected, label)

    source_verifier.require_exact_access = compatible_access
    original_create = source_verifier.create_json_once

    def adapted_create(path: Path, value: Any) -> None:
        if path.name == "preflight-complete.json":
            value = dict(value)
            value["exp069_complete"] = True
            value["parent_base_completion"] = config["parent_base"]["completion"]
        original_create(path, value)

    source_verifier.create_json_once = adapted_create
    try:
        result = source_verifier.verify_smoke(config_path, view)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        source_verifier.record_failed_verification(view, "smoke", error)
        raise
    completion_path = PROJECT_ROOT / PUBLIC_ROOT / "preflight-complete.json"
    completion = strict_json(completion_path)
    if (
        completion.get("status") != "Complete"
        or completion.get("exp069_complete") is not True
        or completion.get("parent_base_completion") != config["parent_base"]["completion"]
    ):
        raise ValueError("Attempt-4 completion drift")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify EXP-069 fold-smoke continuation")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = verify(args.config, load_config(args.config))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
