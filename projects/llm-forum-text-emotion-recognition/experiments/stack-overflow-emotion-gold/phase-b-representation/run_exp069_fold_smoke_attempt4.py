#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
from typing import Any


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
DEFAULT_CONFIG = MODULE_DIR / "configs" / "exp-069-fold-smoke-attempt-4.json"
ATTEMPT_ID = "attempt-4-fold-smoke"
PUBLIC_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
    "exp-069-representation-extraction-preflight/attempt-4-fold-smoke"
)
PRIVATE_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
    "exp-069-representation-extraction-preflight/attempt-4-fold-smoke"
)
SEEDS = (42, 43, 44)
FOLDS = (0, 1, 2, 3, 4)


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


def inventory(root: Path) -> set[str]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Invalid output root")
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def atomic_copy(source: Path, target: Path, *, mode: int) -> None:
    if os.path.lexists(target):
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if mode == 0o600 else 0o755)
    temporary = target.with_name(target.name + f".{os.getpid()}.tmp")
    if os.path.lexists(temporary):
        raise FileExistsError(temporary)
    try:
        with source.open("rb") as reader, temporary.open("xb") as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, target)
        os.chmod(target, mode)
    finally:
        if os.path.lexists(temporary):
            temporary.unlink()


def validate_config(config: dict[str, Any]) -> None:
    expected = {
        "schema_version",
        "experiment_id",
        "attempt_id",
        "rq_id",
        "tier",
        "registered_at",
        "scope",
        "parent_static",
        "parent_base",
        "source_runner",
        "source_verifier",
        "implementation",
        "authorization",
        "environment",
        "smoke",
        "resources",
        "outputs",
        "claim_boundary",
    }
    if set(config) != expected:
        raise ValueError("Attempt-4 config schema drift")
    if (
        config["schema_version"] != "exp-069-fold-smoke-attempt-4-v1"
        or config["experiment_id"] != "EXP-069"
        or config["attempt_id"] != ATTEMPT_ID
        or config["rq_id"] != "RQ-S4"
    ):
        raise ValueError("Attempt-4 config identity drift")
    if config["scope"] != {
        "base_smoke": False,
        "fold_smoke": True,
        "assemble": True,
        "exp070": False,
    }:
        raise ValueError("Attempt-4 scope drift")
    if config["outputs"] != {"public_root": PUBLIC_ROOT, "private_root": PRIVATE_ROOT}:
        raise ValueError("Attempt-4 output root drift")
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
        raise ValueError("Attempt-4 authorization drift")
    for key in ("public_root", "private_root"):
        resolve_project(config["outputs"][key], must_exist=False)


def load_config(path: Path) -> dict[str, Any]:
    if path.resolve() != DEFAULT_CONFIG.resolve():
        raise PermissionError("Attempt-4 requires the frozen config")
    value = strict_json(path)
    validate_config(value)
    return value


def require_records(config: dict[str, Any]) -> None:
    for group in ("parent_static", "parent_base"):
        for record in config[group].values():
            require_record(record)
    for key in ("source_runner", "source_verifier"):
        require_record(config[key])
    for record in config["implementation"].values():
        require_record(record)


def load_source(config: dict[str, Any]) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    source = load_module("exp069_attempt1_fold_source", require_record(config["source_runner"]))
    parent_config_path = require_record(config["parent_static"]["config"])
    parent_config = source.load_config(parent_config_path)
    if config["source_runner"] != parent_config["implementation"]["runner"]:
        raise ValueError("Attempt-4 source runner drift")
    if config["source_verifier"] != parent_config["implementation"]["verifier"]:
        raise ValueError("Attempt-4 source verifier drift")
    for key in ("environment", "smoke", "resources"):
        if config[key] != parent_config[key]:
            raise ValueError(f"Attempt-4 unchanged contract drift: {key}")
    static, manifest = source.require_static_pass(
        parent_config_path, parent_config
    )
    if strict_json(require_record(config["parent_static"]["static_run"])) != static:
        raise ValueError("Attempt-1 static run drift")
    static_run_path = require_record(config["parent_static"]["static_run"])
    static_verification_path = require_record(config["parent_static"]["static_verification"])
    static_manifest_path = require_record(config["parent_static"]["input_manifest"])
    if inventory(static_run_path.parent) != {"static.json", "static-verification.json"}:
        raise ValueError("Attempt-1 static public inventory drift")
    if inventory(static_manifest_path.parent) != {"input-manifest.json"}:
        raise ValueError("Attempt-1 static private inventory drift")
    base_run_path = require_record(config["parent_base"]["run"])
    base_verification_path = require_record(config["parent_base"]["verification"])
    base_completion_path = require_record(config["parent_base"]["completion"])
    base_path = require_record(config["parent_base"]["base"])
    base_worker_path = require_record(config["parent_base"]["base_worker"])
    if inventory(base_run_path.parent) != {
        "run-claim.json",
        "run.json",
        "verification.json",
        "base-complete.json",
    }:
        raise ValueError("Attempt-3 base public inventory drift")
    if inventory(base_path.parent) != {"base.npz", "base-worker.json"}:
        raise ValueError("Attempt-3 base private inventory drift")
    base_run = strict_json(base_run_path)
    base_completion = strict_json(base_completion_path)
    base_verification = strict_json(base_verification_path)
    base_worker = strict_json(base_worker_path)
    if (
        base_run.get("status") != "CompletedAwaitingVerification"
        or base_run.get("attempt_id") != "attempt-3-base-smoke"
        or base_completion.get("status") != "Complete"
        or base_completion.get("base_smoke_complete") is not True
        or base_completion.get("exp069_complete") is not False
        or base_verification.get("status") != "Passed"
        or base_verification.get("passed_count") != 23
        or base_verification.get("attempt_id") != "attempt-3-base-smoke"
        or base_completion.get("run") != observed_artifact(base_run_path)
        or base_completion.get("verification") != observed_artifact(base_verification_path)
        or base_worker.get("output", {}).get("sha256") != config["parent_base"]["base"]["sha256"]
    ):
        raise ValueError("Attempt-3 base prerequisite drift")
    return source, parent_config, manifest


def continuation_view(config: dict[str, Any], parent_config: dict[str, Any]) -> dict[str, Any]:
    view = dict(parent_config)
    for key in ("authorization", "environment", "smoke", "resources", "claim_boundary"):
        view[key] = config[key]
    outputs = dict(parent_config["outputs"])
    outputs.update(config["outputs"])
    view["outputs"] = outputs
    view["implementation"] = config["implementation"]
    view["attempt_id"] = ATTEMPT_ID
    return view


def install_source_adapters(
    source: Any,
    config_path: Path,
    config: dict[str, Any],
    view: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    source.ATTEMPT_ID = ATTEMPT_ID
    source.DEFAULT_CONFIG = config_path
    original_resolver = source.resolve_project
    base_relative = strict_json(require_record(config["parent_static"]["config"]))["model"]["base_path"]

    def adapted_resolver(relative: str, *, must_exist: bool = True) -> Path:
        if relative != base_relative:
            return original_resolver(relative, must_exist=must_exist)
        candidate = original_resolver(relative, must_exist=False)
        if must_exist and (not candidate.is_dir() or candidate.is_symlink()):
            raise FileNotFoundError(candidate)
        return candidate

    source.resolve_project = adapted_resolver

    def chained_static(path: Path, observed_view: dict[str, Any]):
        if path.resolve() != config_path.resolve() or observed_view != view:
            raise ValueError("Attempt-4 continuation view drift")
        source.require_environment(observed_view)
        source.require_implementation(observed_view, path)
        copied_static = source.strict_json(source.public_root(observed_view) / "static.json")
        copied_verification = source.strict_json(
            source.public_root(observed_view) / "static-verification.json"
        )
        copied_manifest = source.strict_json(source.private_root(observed_view) / "input-manifest.json")
        if copied_static != strict_json(require_record(config["parent_static"]["static_run"])):
            raise ValueError("Copied static run drift")
        if copied_verification != strict_json(
            require_record(config["parent_static"]["static_verification"])
        ):
            raise ValueError("Copied static verification drift")
        if copied_manifest != manifest:
            raise ValueError("Copied input manifest drift")
        return copied_static, copied_manifest

    source.require_static_pass = chained_static


def validate_copies(config: dict[str, Any], source: Any, view: dict[str, Any]) -> None:
    root_public = source.public_root(view)
    root_private = source.private_root(view)
    if file_mode(root_public) != "0755" or file_mode(root_private) != "0700":
        raise PermissionError("Attempt-4 root mode drift")
    bindings = (
        (config["parent_static"]["static_run"], root_public / "static.json", "0644"),
        (
            config["parent_static"]["static_verification"],
            root_public / "static-verification.json",
            "0644",
        ),
        (config["parent_static"]["input_manifest"], root_private / "input-manifest.json", "0600"),
        (config["parent_base"]["base"], root_private / "base.npz", "0600"),
        (config["parent_base"]["base_worker"], root_private / "base-worker.json", "0600"),
    )
    for parent_record, copied_path, expected_mode in bindings:
        if (
            copied_path.is_symlink()
            or not copied_path.is_file()
            or copied_path.stat().st_nlink != 1
            or file_mode(copied_path) != expected_mode
            or copied_path.stat().st_size != parent_record["bytes"]
            or sha256(copied_path) != parent_record["sha256"]
        ):
            raise ValueError(f"Attempt-4 copied evidence drift: {copied_path.name}")


def validate_claim(config_path: Path, config: dict[str, Any], source: Any, view: dict[str, Any]) -> None:
    claim_path = source.public_root(view) / "run-claim.json"
    if (
        claim_path.is_symlink()
        or not claim_path.is_file()
        or claim_path.stat().st_nlink != 1
        or file_mode(claim_path) != "0644"
    ):
        raise ValueError("Attempt-4 run claim mode/link drift")
    expected = {
        "schema_version": "exp-069-run-claim-v1",
        "experiment_id": config["experiment_id"],
        "run_id": source.RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "Claimed",
        "config": observed_artifact(config_path),
        "workers": 16,
        "model_loading_authorized": True,
        "smoke_execution_authorized": True,
        "claim_boundary": config["claim_boundary"],
    }
    if strict_json(claim_path) != expected:
        raise ValueError("Attempt-4 run claim binding drift")


def completed_prefix(config: dict[str, Any], source: Any, view: dict[str, Any]) -> list[tuple[int, int]]:
    root_public = source.public_root(view)
    root_private = source.private_root(view)
    if inventory(root_public) != {"static.json", "static-verification.json", "run-claim.json"}:
        raise ValueError("Attempt-4 preterminal public inventory drift")
    if any(
        path.is_symlink()
        for root in (root_public, root_private)
        for path in root.rglob("*")
    ):
        raise PermissionError("Attempt-4 preterminal nested symlink drift")
    root_files = {"input-manifest.json", "base.npz", "base-worker.json"}
    allowed_seed_dirs = {f"seed-{seed}" for seed in SEEDS}
    observed_seed_dirs: set[str] = set()
    for path in root_private.iterdir():
        if path.name in root_files:
            continue
        if (
            path.name not in allowed_seed_dirs
            or path.is_symlink()
            or not path.is_dir()
            or file_mode(path) != "0700"
        ):
            raise PermissionError("Attempt-4 private child directory drift")
        observed_seed_dirs.add(path.name)
    completed: list[tuple[int, int]] = []
    missing_seen = False
    expected_private = set(root_files)
    for seed in SEEDS:
        for fold in FOLDS:
            npz_relative = f"seed-{seed}/fold-{fold}.npz"
            json_relative = f"seed-{seed}/fold-{fold}.json"
            npz_path = root_private / npz_relative
            json_path = root_private / json_relative
            present = (os.path.lexists(npz_path), os.path.lexists(json_path))
            if present[0] != present[1]:
                raise ValueError("Attempt-4 orphan fold artifact")
            if present[0]:
                if missing_seen:
                    raise ValueError("Attempt-4 worker order is not a continuous prefix")
                if (
                    npz_path.is_symlink()
                    or json_path.is_symlink()
                    or npz_path.stat().st_nlink != 1
                    or json_path.stat().st_nlink != 1
                    or file_mode(npz_path) != "0600"
                    or file_mode(json_path) != "0600"
                    or file_mode(npz_path.parent) != "0700"
                ):
                    raise PermissionError("Attempt-4 fold artifact mode/link drift")
                worker = strict_json(json_path)
                if worker.get("status") != "Completed" or worker.get("seed") != seed or worker.get("fold") != fold:
                    raise ValueError("Attempt-4 fold worker state drift")
                expected_private.update({npz_relative, json_relative})
                completed.append((seed, fold))
            else:
                missing_seen = True
    expected_seed_dirs = {f"seed-{seed}" for seed, _ in completed}
    if observed_seed_dirs != expected_seed_dirs:
        raise ValueError("Attempt-4 seed-directory prefix drift")
    if inventory(root_private) != expected_private:
        raise ValueError("Attempt-4 preassemble private inventory drift")
    return completed


def initialize(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    require_records(config)
    source, parent_config, manifest = load_source(config)
    view = continuation_view(config, parent_config)
    root_public = source.resolve_project(config["outputs"]["public_root"], must_exist=False)
    root_private = source.resolve_project(config["outputs"]["private_root"], must_exist=False)
    if os.path.lexists(root_public) or os.path.lexists(root_private):
        raise FileExistsError("Attempt-4 output root exists")
    root_public.mkdir(parents=True, mode=0o755)
    root_private.mkdir(parents=True, mode=0o700)
    os.chmod(root_private, 0o700)
    copies = (
        (require_record(config["parent_static"]["static_run"]), root_public / "static.json", 0o644),
        (
            require_record(config["parent_static"]["static_verification"]),
            root_public / "static-verification.json",
            0o644,
        ),
        (
            require_record(config["parent_static"]["input_manifest"]),
            root_private / "input-manifest.json",
            0o600,
        ),
        (require_record(config["parent_base"]["base"]), root_private / "base.npz", 0o600),
        (
            require_record(config["parent_base"]["base_worker"]),
            root_private / "base-worker.json",
            0o600,
        ),
    )
    for source_path, target_path, mode in copies:
        atomic_copy(source_path, target_path, mode=mode)
        if sha256(source_path) != sha256(target_path) or source_path.stat().st_size != target_path.stat().st_size:
            raise ValueError("Attempt-4 evidence copy drift")
    install_source_adapters(source, config_path, config, view, manifest)
    source.create_claim(config_path, view)
    validate_claim(config_path, config, source, view)
    validate_copies(config, source, view)
    if completed_prefix(config, source, view):
        raise ValueError("Attempt-4 initialized with completed workers")
    return {
        "status": "Initialized",
        "attempt_id": ATTEMPT_ID,
        "copied_public": ["static.json", "static-verification.json"],
        "copied_private": ["input-manifest.json", "base.npz", "base-worker.json"],
        "workers": 15,
        "claim_boundary": config["claim_boundary"],
    }


def load_initialized(
    config_path: Path, config: dict[str, Any]
) -> tuple[Any, dict[str, Any]]:
    require_records(config)
    source, parent_config, manifest = load_source(config)
    view = continuation_view(config, parent_config)
    install_source_adapters(source, config_path, config, view, manifest)
    root_public = source.public_root(view)
    root_private = source.private_root(view)
    if not (root_public / "run-claim.json").is_file():
        raise ValueError("Attempt-4 is not initialized")
    if (root_public / "run.json").exists():
        raise ValueError("Attempt-4 already has a terminal run")
    validate_claim(config_path, config, source, view)
    validate_copies(config, source, view)
    completed_prefix(config, source, view)
    return source, view


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EXP-069 fold-smoke continuation")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--stage", required=True, choices=("initialize", "fold-smoke", "assemble"))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--fold", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    source: Any = None
    view: dict[str, Any] = {}
    try:
        if args.stage == "initialize":
            if args.seed is not None or args.fold is not None:
                raise ValueError("Initialize does not take seed/fold")
            result = initialize(args.config, config)
        else:
            source, view = load_initialized(args.config, config)
            if args.stage == "fold-smoke":
                if args.seed not in SEEDS or args.fold not in FOLDS:
                    raise ValueError("Fold smoke requires a registered seed/fold")
                order = [(seed, fold) for seed in SEEDS for fold in FOLDS]
                completed = completed_prefix(config, source, view)
                if len(completed) >= len(order) or order[len(completed)] != (args.seed, args.fold):
                    raise ValueError("Fold smoke invocation is not the next registered worker")
                result = source.fold_stage(args.config, view, args.seed, args.fold)
            else:
                if args.seed is not None or args.fold is not None:
                    raise ValueError("Assemble does not take seed/fold")
                if len(completed_prefix(config, source, view)) != 15:
                    raise ValueError("Assemble requires all 15 fold workers")
                result = source.assemble_stage(args.config, view)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        if source is not None and view:
            source.record_failure(view, args.stage, error)
        raise


if __name__ == "__main__":
    main()
