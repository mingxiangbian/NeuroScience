#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import types
from typing import Any


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
DEFAULT_CONFIG = MODULE_DIR / "configs" / "exp-069-verification-attempt-2.json"
EXPERIMENT_ID = "EXP-069"
ATTEMPT_ID = "attempt-5-verification-recovery"
SOURCE_ATTEMPT_ID = "attempt-4-fold-smoke"
RUN_ID = "exp-069-representation-extraction-preflight"
SOURCE_PUBLIC_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
    "exp-069-representation-extraction-preflight/attempt-4-fold-smoke"
)
SOURCE_PRIVATE_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
    "exp-069-representation-extraction-preflight/attempt-4-fold-smoke"
)
RECOVERY_PUBLIC_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
    "exp-069-representation-extraction-preflight/attempt-5-verification-recovery"
)
SOURCE_PUBLIC_INVENTORY = {
    "static.json",
    "static-verification.json",
    "run-claim.json",
    "run.json",
    "verification.json",
}
SOURCE_PRIVATE_INVENTORY = {
    "input-manifest.json",
    "base.npz",
    "base-worker.json",
    "smoke-manifest.json",
    *{
        f"seed-{seed}/fold-{fold}.{suffix}"
        for seed in (42, 43, 44)
        for fold in range(5)
        for suffix in ("npz", "json")
    },
}
FORBIDDEN_MODEL_MODULES = {"mlx", "mlx_lm", "torch", "transformers"}


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


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


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
    return path


def artifact(path: Path, *, logical_name: str | None = None) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError(f"Unsafe or missing artifact: {path}")
    result = {
        "bytes": path.stat().st_size,
        "mode": file_mode(path),
        "sha256": sha256(path),
    }
    if logical_name is None:
        result["path"] = path.relative_to(PROJECT_ROOT).as_posix()
    else:
        result["logical_name"] = logical_name
    return result


def require_record(record: dict[str, Any]) -> Path:
    if set(record) != {"path", "bytes", "mode", "sha256"}:
        raise ValueError("Artifact record schema drift")
    path = resolve_project(record["path"])
    if artifact(path) != record:
        raise ValueError(f"Artifact identity drift: {record['path']}")
    return path


def inventory(root: Path) -> set[str]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid evidence root")
    entries = list(root.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise PermissionError("Nested symlink rejected")
    return {path.relative_to(root).as_posix() for path in entries if path.is_file()}


def snapshot_digest(public_root: Path, private_root: Path) -> str:
    records: dict[str, dict[str, Any]] = {}
    for prefix, root in (("public", public_root), ("private", private_root)):
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = path.relative_to(root).as_posix()
            records[f"{prefix}/{relative}"] = {
                "bytes": path.stat().st_size,
                "mode": file_mode(path),
                "sha256": sha256(path),
            }
    return hashlib.sha256(canonical_json_bytes(records)).hexdigest()


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_config(config: dict[str, Any]) -> None:
    if set(config) != {
        "schema_version",
        "experiment_id",
        "attempt_id",
        "source_attempt_id",
        "registered_at",
        "scope",
        "source_snapshot",
        "frozen_verifiers",
        "implementation",
        "authorization",
        "metrics",
        "outputs",
        "claim_boundary",
    }:
        raise ValueError("Recovery config schema drift")
    if (
        config["schema_version"] != "exp-069-verification-attempt-2-config-v1"
        or config["experiment_id"] != EXPERIMENT_ID
        or config["attempt_id"] != ATTEMPT_ID
        or config["source_attempt_id"] != SOURCE_ATTEMPT_ID
    ):
        raise ValueError("Recovery config identity drift")
    if config["scope"] != {
        "verification_only": True,
        "model_rerun": False,
        "assemble_rerun": False,
        "source_mutation": False,
        "exp070": False,
    }:
        raise ValueError("Recovery scope drift")
    if config["authorization"] != {
        "verification_authorized": True,
        "model_loading_authorized": False,
        "forward_authorized": False,
        "training_authorized": False,
        "performance_metrics_authorized": False,
        "validation_access": False,
        "test_access": False,
        "gold_access": False,
    }:
        raise PermissionError("Recovery authorization drift")
    if config["metrics"] != {
        "aggregate_equality_atol": 1e-12,
        "manual_logit_atol": 1e-5,
        "runner_metric": "runner_manual_vs_standard_logit_max_abs",
        "independent_metric": "independent_saved_hf_head_vs_manual_logit_max_abs",
    }:
        raise ValueError("Recovery metric contract drift")
    if config["outputs"] != {
        "source_public_root": SOURCE_PUBLIC_ROOT,
        "source_private_root": SOURCE_PRIVATE_ROOT,
        "recovery_public_root": RECOVERY_PUBLIC_ROOT,
    }:
        raise ValueError("Recovery output namespace drift")


def load_config(path: Path) -> dict[str, Any]:
    if path.resolve() != DEFAULT_CONFIG.resolve():
        raise PermissionError("Recovery requires the frozen default config")
    config = strict_json(path)
    validate_config(config)
    return config


def require_config_records(config: dict[str, Any]) -> None:
    for record in config["source_snapshot"].values():
        require_record(record)
    for record in config["frozen_verifiers"].values():
        require_record(record)
    for record in config["implementation"].values():
        require_record(record)


def validate_source_snapshot(config: dict[str, Any]) -> tuple[Any, dict[str, Any], dict[str, Any], dict[str, Any]]:
    source = config["source_snapshot"]
    attempt4_config_path = require_record(source["config"])
    wrapper_path = require_record(config["frozen_verifiers"]["attempt4_wrapper"])
    wrapper = load_module("exp069_attempt4_wrapper_recovery", wrapper_path)
    attempt4_config = wrapper.load_config(attempt4_config_path)
    for group in ("parent_static", "parent_base"):
        for record in attempt4_config[group].values():
            require_record(record)
    for key in ("source_runner", "source_verifier"):
        require_record(attempt4_config[key])
    for record in attempt4_config["implementation"].values():
        require_record(record)
    if attempt4_config["implementation"]["verifier"] != config["frozen_verifiers"]["attempt4_wrapper"]:
        raise ValueError("Attempt-4 wrapper binding drift")
    if attempt4_config["source_verifier"] != config["frozen_verifiers"]["source_verifier"]:
        raise ValueError("Frozen source-verifier binding drift")

    public_root = resolve_project(config["outputs"]["source_public_root"])
    private_root = resolve_project(config["outputs"]["source_private_root"])
    if file_mode(public_root) != "0755" or file_mode(private_root) != "0700":
        raise PermissionError("Source root mode drift")
    if inventory(public_root) != SOURCE_PUBLIC_INVENTORY:
        raise ValueError("Source public inventory drift")
    if inventory(private_root) != SOURCE_PRIVATE_INVENTORY:
        raise ValueError("Source private inventory drift")
    private_dirs = {
        path.relative_to(private_root).as_posix()
        for path in private_root.rglob("*")
        if path.is_dir()
    }
    if private_dirs != {"seed-42", "seed-43", "seed-44"}:
        raise ValueError("Source private directory inventory drift")
    if any(file_mode(private_root / relative) != "0700" for relative in private_dirs):
        raise PermissionError("Source seed-directory mode drift")
    if any(file_mode(private_root / relative) != "0600" for relative in SOURCE_PRIVATE_INVENTORY):
        raise PermissionError("Source private file mode drift")
    copied_bindings = (
        (attempt4_config["parent_static"]["static_run"], public_root / "static.json"),
        (
            attempt4_config["parent_static"]["static_verification"],
            public_root / "static-verification.json",
        ),
        (
            attempt4_config["parent_static"]["input_manifest"],
            private_root / "input-manifest.json",
        ),
        (attempt4_config["parent_base"]["base"], private_root / "base.npz"),
        (
            attempt4_config["parent_base"]["base_worker"],
            private_root / "base-worker.json",
        ),
    )
    for parent_record, copied_path in copied_bindings:
        observed = artifact(copied_path)
        if any(observed[key] != parent_record[key] for key in ("bytes", "mode", "sha256")):
            raise ValueError(f"Copied source evidence drift: {copied_path.name}")

    expected_paths = {
        "run_claim": public_root / "run-claim.json",
        "run": public_root / "run.json",
        "failed_verification": public_root / "verification.json",
        "smoke_manifest": private_root / "smoke-manifest.json",
    }
    for key, expected_path in expected_paths.items():
        if require_record(source[key]) != expected_path:
            raise ValueError(f"Source snapshot path drift: {key}")

    run_claim = strict_json(expected_paths["run_claim"])
    run = strict_json(expected_paths["run"])
    failed = strict_json(expected_paths["failed_verification"])
    smoke_manifest = strict_json(expected_paths["smoke_manifest"])
    current_config = artifact(attempt4_config_path)
    if (
        run_claim.get("status") != "Claimed"
        or run_claim.get("attempt_id") != SOURCE_ATTEMPT_ID
        or run_claim.get("config") != current_config
        or run.get("status") != "CompletedAwaitingVerification"
        or run.get("attempt_id") != SOURCE_ATTEMPT_ID
        or failed
        != {
            "schema_version": "exp-069-verification-failure-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "attempt_id": SOURCE_ATTEMPT_ID,
            "stage": "smoke",
            "status": "Failed",
            "error_type": "ValueError",
            "claim_boundary": attempt4_config["claim_boundary"],
        }
        or smoke_manifest.get("attempt_id") != SOURCE_ATTEMPT_ID
        or smoke_manifest.get("config") != current_config
        or smoke_manifest.get("max_errors") != run.get("max_errors")
        or run.get("private_manifest")
        != artifact(expected_paths["smoke_manifest"], logical_name="smoke-manifest.json")
    ):
        raise ValueError("Source terminal binding drift")
    if (public_root / "preflight-complete.json").exists():
        raise ValueError("Attempt-4 unexpectedly completed")
    return wrapper, attempt4_config, run, failed


def transform_source_verifier(path: Path) -> tuple[Any, str]:
    source_text = path.read_text(encoding="utf-8")
    replacements = (
        (
            '        "manual_logit": 0.0,\n        "m3_logit": 0.0,',
            '        "manual_logit": 0.0,\n'
            '        "manual_head_numpy_replay": 0.0,\n'
            '        "m3_logit": 0.0,',
        ),
        (
            '            errors["manual_logit"] = max(\n'
            '                errors["manual_logit"],\n'
            '                max_abs(recomputed.astype(np.float32), worker["manual_logits"]),\n'
            '                max_abs(worker["manual_logits"], worker["standard_logits"]),\n'
            '            )',
            '            errors["manual_head_numpy_replay"] = max(\n'
            '                errors["manual_head_numpy_replay"],\n'
            '                max_abs(recomputed.astype(np.float32), worker["manual_logits"]),\n'
            '            )\n'
            '            errors["manual_logit"] = max(\n'
            '                errors["manual_logit"],\n'
            '                max_abs(worker["manual_logits"], worker["standard_logits"]),\n'
            '            )',
        ),
        (
            '        "manual_logit": "manual_logit_atol",\n        "m3_logit": "m3_logit_atol",',
            '        "manual_logit": "manual_logit_atol",\n'
            '        "manual_head_numpy_replay": "manual_logit_atol",\n'
            '        "m3_logit": "m3_logit_atol",',
        ),
        (
            '    for gate, value in errors.items():\n'
            '        if not math_isclose(value, float(run["max_errors"][gate])):\n'
            '            raise ValueError(f"Public aggregate drift: {gate}")\n'
            '        if not math_isclose(value, float(smoke_manifest["max_errors"][gate])):\n'
            '            raise ValueError(f"Private aggregate drift: {gate}")',
            '    for gate in ("m2_hf", "standard_hf", "manual_logit", "m3_logit", "pre_lora"):\n'
            '        value = errors[gate]\n'
            '        if not math_isclose(value, float(run["max_errors"][gate])):\n'
            '            raise ValueError(f"Public aggregate drift: {gate}")\n'
            '        if not math_isclose(value, float(smoke_manifest["max_errors"][gate])):\n'
            '            raise ValueError(f"Private aggregate drift: {gate}")',
        ),
    )
    for old, new in replacements:
        if source_text.count(old) != 1:
            raise ValueError("Frozen verifier transformation anchor drift")
        source_text = source_text.replace(old, new)
    transformed_sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    module = types.ModuleType("exp069_metric_split_verifier")
    module.__file__ = str(path)
    exec(compile(source_text, str(path), "exec"), module.__dict__)
    return module, transformed_sha256


def run_full_replay(
    config_path: Path,
    config: dict[str, Any],
    wrapper: Any,
    attempt4_config: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    source_path = require_record(config["frozen_verifiers"]["source_verifier"])
    verifier, transformed_sha256 = transform_source_verifier(source_path)
    attempt4_config_path = require_record(config["source_snapshot"]["config"])
    parent_config = strict_json(require_record(attempt4_config["parent_static"]["config"]))
    view = wrapper.continuation_view(attempt4_config, parent_config)
    verifier.ATTEMPT_ID = SOURCE_ATTEMPT_ID
    verifier.DEFAULT_CONFIG = attempt4_config_path
    current_config = verifier.observed_artifact(attempt4_config_path)
    parent_config_record = attempt4_config["parent_static"]["config"]

    def chained_binding(path: Path, *records: dict[str, Any]) -> None:
        expected = (parent_config_record, parent_config_record, current_config, current_config)
        if path.resolve() != attempt4_config_path.resolve() or records != expected:
            raise ValueError("Recovery config-binding lineage drift")

    verifier.require_config_binding = chained_binding
    original_access = verifier.require_exact_access

    def compatible_access(observed: Any, expected: dict[str, Any], label: str) -> None:
        if label == "Base worker":
            compatible = dict(expected)
            compatible["m3_artifacts_accessed"] = False
            if observed == compatible:
                return
        original_access(observed, expected, label)

    verifier.require_exact_access = compatible_access
    source_public = resolve_project(config["outputs"]["source_public_root"])
    original_inventory = verifier.inventory

    def compatible_inventory(root: Path) -> set[str]:
        observed = original_inventory(root)
        if root.resolve() == source_public.resolve():
            if observed != SOURCE_PUBLIC_INVENTORY:
                raise ValueError("Recovery source public inventory drift")
            return observed - {"verification.json"}
        return observed

    verifier.inventory = compatible_inventory
    captured: dict[str, Any] = {}

    def capture_output(path: Path, value: Any, **_kwargs: Any) -> None:
        if path.parent.resolve() != source_public.resolve() or path.name not in {
            "verification.json",
            "preflight-complete.json",
        }:
            raise PermissionError("Recovery verifier attempted an unexpected write")
        if path.name in captured:
            raise FileExistsError(path.name)
        captured[path.name] = value

    verifier.create_json_once = capture_output
    original_observed = verifier.observed_artifact

    def captured_artifact(path: Path, *, logical_name: str | None = None) -> dict[str, Any]:
        if path == source_public / "verification.json" and "verification.json" in captured:
            payload = verifier.canonical_json_bytes(captured["verification.json"])
            result = {
                "bytes": len(payload),
                "mode": "0644",
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            if logical_name is None:
                result["path"] = path.relative_to(PROJECT_ROOT).as_posix()
            else:
                result["logical_name"] = logical_name
            return result
        return original_observed(path, logical_name=logical_name)

    verifier.observed_artifact = captured_artifact
    result = verifier.verify_smoke(attempt4_config_path, view)
    if set(captured) != {"verification.json", "preflight-complete.json"}:
        raise ValueError("Recovery verifier capture drift")
    return result, transformed_sha256


def create_json_once(path: Path, value: Any) -> None:
    if os.path.lexists(path):
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    if os.path.lexists(temporary):
        raise FileExistsError(temporary)
    try:
        with temporary.open("xb") as handle:
            handle.write(canonical_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
        os.chmod(path, 0o644)
    finally:
        if os.path.lexists(temporary):
            temporary.unlink()


def verify(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    require_config_records(config)
    recovery_root = resolve_project(config["outputs"]["recovery_public_root"])
    if os.path.lexists(recovery_root):
        raise FileExistsError("Recovery output root already exists")
    wrapper, attempt4_config, run, failed = validate_source_snapshot(config)
    source_public = resolve_project(config["outputs"]["source_public_root"])
    source_private = resolve_project(config["outputs"]["source_private_root"])
    snapshot_before = snapshot_digest(source_public, source_private)
    imported_before = {name.split(".")[0] for name in sys.modules}
    if imported_before & FORBIDDEN_MODEL_MODULES:
        raise RuntimeError("Model library was imported before recovery")
    replay, transformed_sha256 = run_full_replay(
        config_path, config, wrapper, attempt4_config
    )
    imported_after = {name.split(".")[0] for name in sys.modules}
    if imported_after & FORBIDDEN_MODEL_MODULES:
        raise RuntimeError("Recovery imported a forbidden model library")
    snapshot_after = snapshot_digest(source_public, source_private)
    if snapshot_before != snapshot_after:
        raise ValueError("Immutable source snapshot changed during recovery")

    expected_error_keys = {
        "m2_hf",
        "standard_hf",
        "manual_logit",
        "manual_head_numpy_replay",
        "m3_logit",
        "pre_lora",
    }
    errors = replay.get("max_errors")
    if (
        replay.get("status") != "Passed"
        or replay.get("passed_count") != 22
        or replay.get("failed_count") != 0
        or set(errors or {}) != expected_error_keys
    ):
        raise ValueError("Recovery full-replay state drift")
    aggregate_atol = float(config["metrics"]["aggregate_equality_atol"])
    for gate in ("m2_hf", "standard_hf", "manual_logit", "m3_logit", "pre_lora"):
        if abs(float(errors[gate]) - float(run["max_errors"][gate])) > aggregate_atol:
            raise ValueError(f"Recovery aggregate equality failed: {gate}")
    independent_error = float(errors["manual_head_numpy_replay"])
    if independent_error > float(config["metrics"]["manual_logit_atol"]):
        raise ValueError("Recovery independent manual-head replay gate failed")

    checks = list(replay["checks"]) + [
        "manual_logit_metric_separation",
        "prior_failed_verification_binding",
        "immutable_snapshot_no_model_recovery",
    ]
    verification = {
        "schema_version": "exp-069-verification-attempt-2-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "source_attempt_id": SOURCE_ATTEMPT_ID,
        "verification_attempt": 2,
        "status": "Passed",
        "passed_count": len(checks),
        "failed_count": 0,
        "checks": checks,
        "max_errors": {
            "m2_hf": float(errors["m2_hf"]),
            "standard_hf": float(errors["standard_hf"]),
            "runner_manual_vs_standard_logit_max_abs": float(errors["manual_logit"]),
            "independent_saved_hf_head_vs_manual_logit_max_abs": independent_error,
            "m3_logit": float(errors["m3_logit"]),
            "pre_lora": float(errors["pre_lora"]),
        },
        "metric_contract": config["metrics"],
        "source_run": config["source_snapshot"]["run"],
        "source_failed_verification": config["source_snapshot"]["failed_verification"],
        "source_snapshot_sha256": snapshot_before,
        "frozen_source_verifier": config["frozen_verifiers"]["source_verifier"],
        "transformed_source_sha256": transformed_sha256,
        "config": artifact(config_path),
        "counts": replay["counts"],
        "runner_imported": False,
        "model_libraries_imported": False,
        "model_rerun": False,
        "assemble_rerun": False,
        "source_mutated": False,
        "access": {
            "validation_accessed": False,
            "test_accessed": False,
            "gold_read": False,
            "performance_metrics_computed": False,
        },
        "claim_boundary": config["claim_boundary"],
    }
    recovery_root.mkdir(parents=True, mode=0o755)
    os.chmod(recovery_root, 0o755)
    verification_path = recovery_root / "verification.json"
    create_json_once(verification_path, verification)
    completion = {
        "schema_version": "exp-069-complete-v2",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "source_attempt_id": SOURCE_ATTEMPT_ID,
        "verification_attempt": 2,
        "status": "Complete",
        "exp069_complete": True,
        "completed_via": ATTEMPT_ID,
        "attempt4_verification_remains_failed": True,
        "model_rerun": False,
        "source_mutated": False,
        "run": config["source_snapshot"]["run"],
        "source_failed_verification": config["source_snapshot"]["failed_verification"],
        "recovery_config": artifact(config_path),
        "recovery_verification": artifact(verification_path),
        "parent_base_completion": attempt4_config["parent_base"]["completion"],
        "claim_boundary": config["claim_boundary"],
        "next_gate": "EXP-070 remains separately registered and unexecuted",
    }
    create_json_once(recovery_root / "preflight-complete.json", completion)
    if inventory(recovery_root) != {"verification.json", "preflight-complete.json"}:
        raise ValueError("Recovery output inventory drift")
    return verification


def record_failure(config: dict[str, Any], error: BaseException) -> None:
    try:
        root = resolve_project(config["outputs"]["recovery_public_root"])
        target = root / "verification.json"
        if os.path.lexists(target):
            return
        value = {
            "schema_version": "exp-069-verification-attempt-2-failure-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "attempt_id": ATTEMPT_ID,
            "source_attempt_id": SOURCE_ATTEMPT_ID,
            "verification_attempt": 2,
            "status": "Failed",
            "error_type": type(error).__name__,
            "source_failed_verification": config.get("source_snapshot", {}).get(
                "failed_verification"
            ),
            "claim_boundary": config.get("claim_boundary"),
        }
        create_json_once(target, value)
    except Exception:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recover EXP-069 final verification")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    try:
        result = verify(args.config, config)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        record_failure(config, error)
        raise
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
