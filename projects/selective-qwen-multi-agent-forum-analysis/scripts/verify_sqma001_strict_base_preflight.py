#!/usr/bin/env python3
"""Independent verifier for the SQMA-001 no-training readiness preflight."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import stat
import subprocess
import sys
import time
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TOP_LEVEL = {
    "schema_version",
    "experiment_id",
    "tier",
    "stage",
    "registered_at",
    "authorization",
    "implementation",
    "prerequisites",
    "private_source_contract",
    "data",
    "snapshot_contract",
    "model_assets",
    "runtimes",
    "resources",
    "outputs",
    "commands",
}
EXPECTED_AUTHORIZATION = {
    "basis": "User instructed: 行，开始下一步",
    "static_preflight": True,
    "public_fold_metadata_access": True,
    "model_asset_hashing": True,
    "runtime_metadata_probe": True,
    "private_source_open": False,
    "private_rows_parsed": False,
    "model_loading": False,
    "forward": False,
    "training": False,
    "optimizer": False,
    "heldout_logits": False,
    "agent_calls": False,
    "network": False,
    "tune_access": False,
    "confirm_access": False,
    "validation_access": False,
    "test_access": False,
    "formal_training": False,
    "automatic_next_stage": False,
}
EXPECTED_ACCESS = {
    "training_executed": False,
    "model_loaded": False,
    "forward_executed": False,
    "private_files_opened": False,
    "private_rows_parsed": False,
    "tune_accessed": False,
    "confirm_opened": False,
    "validation_accessed": False,
    "test_accessed": False,
    "agent_calls": 0,
    "network_accessed": False,
    "files_written_private": False,
    "public_fold_metadata_accessed": True,
    "model_bytes_hashed": True,
    "runtime_metadata_probed": True,
}


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact(path: Path, root: Path = REPO_ROOT) -> dict[str, Any]:
    return {
        "path": str(path.resolve().relative_to(root.resolve())),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def checked_path(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute(), "relative path required")
    path = (root / relative).resolve()
    require(path == root.resolve() or root.resolve() in path.parents, "path escapes root")
    return path


def regular_file(path: Path, label: str) -> Path:
    require(os.path.lexists(path), f"missing {label}")
    observed = os.lstat(path)
    require(stat.S_ISREG(observed.st_mode) and not stat.S_ISLNK(observed.st_mode), f"invalid {label}")
    return path


def read_json(path: Path) -> dict[str, Any]:
    regular_file(path, "JSON")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationError("invalid JSON") from exc
    require(isinstance(value, dict), "JSON root must be object")
    return value


def verify_record(record: dict[str, Any]) -> Path:
    require(set(record) == {"path", "bytes", "sha256"}, "artifact record schema drift")
    path = checked_path(REPO_ROOT, record["path"])
    regular_file(path, "artifact")
    require(path.stat().st_size == record["bytes"], "artifact byte drift")
    require(sha256(path) == record["sha256"], "artifact hash drift")
    return path


def load_contract(record: dict[str, Any]) -> Any:
    path = verify_record(record)
    spec = importlib.util.spec_from_file_location("sqma001_contract_for_verifier", path)
    require(spec is not None and spec.loader is not None, "contract import spec unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fit_specs(config: dict[str, Any], contract: Any) -> tuple[Any, ...]:
    values = []
    for item in config["data"]["full_fit_plan"]:
        require(set(item) == {"fit_id", "phase", "train_folds", "heldout_folds"}, "fit config schema drift")
        values.append(
            contract.FitSpec(
                item["fit_id"],
                item["phase"],
                tuple(item["train_folds"]),
                tuple(item["heldout_folds"]),
            )
        )
    return contract.validate_full_plan(values)


def normalized_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def distribution_versions(site_packages: Path) -> dict[str, str]:
    require(site_packages.is_dir(), "runtime site-packages missing")
    output: dict[str, str] = {}
    for metadata in site_packages.glob("*.dist-info/METADATA"):
        name = None
        version = None
        for line in metadata.read_text(encoding="utf-8").splitlines():
            if line.startswith("Name: ") and name is None:
                name = normalized_name(line[6:])
            elif line.startswith("Version: ") and version is None:
                version = line[9:]
            if name is not None and version is not None:
                break
        if name is not None and version is not None:
            output[name] = version
    return output


def runtime_probe(spec: dict[str, Any]) -> dict[str, Any]:
    require(set(spec) == {"executable", "python", "machine", "packages"}, "runtime schema drift")
    executable = Path(spec["executable"])
    require(executable.is_file() and os.access(executable, os.X_OK), "runtime executable unavailable")
    code = "import json,platform;print(json.dumps({'python':platform.python_version(),'machine':platform.machine()},sort_keys=True))"
    env = {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    completed = subprocess.run(
        [str(executable), "-I", "-S", "-c", code],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        cwd="/",
        env=env,
    )
    require(completed.returncode == 0, "isolated runtime probe failed")
    observed = json.loads(completed.stdout)
    require(observed == {"python": spec["python"], "machine": spec["machine"]}, "runtime identity drift")
    major_minor = ".".join(spec["python"].split(".")[:2])
    site_packages = executable.parent.parent / "lib" / f"python{major_minor}" / "site-packages"
    installed = distribution_versions(site_packages)
    for name, version in spec["packages"].items():
        require(installed.get(normalized_name(name)) == version, f"runtime package drift: {name}")
    return {"python": spec["python"], "machine": spec["machine"], "packages": spec["packages"]}


def model_probe(archive_root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "repo_id",
        "revision",
        "manifest_path",
        "manifest_bytes",
        "manifest_sha256",
        "root_path",
        "manifest_inventory_key",
        "file_count",
        "total_bytes",
    }
    require(set(spec) == expected, "model asset schema drift")
    manifest_path = checked_path(archive_root, spec["manifest_path"])
    regular_file(manifest_path, "model manifest")
    require(manifest_path.stat().st_size == spec["manifest_bytes"], "model manifest byte drift")
    require(sha256(manifest_path) == spec["manifest_sha256"], "model manifest hash drift")
    manifest = read_json(manifest_path)
    require(manifest["repo_id"] == spec["repo_id"] and manifest["revision"] == spec["revision"], "model identity drift")
    if spec["manifest_inventory_key"] == "files":
        files = manifest["files"]
    elif spec["manifest_inventory_key"] == "mlx_bf16.files":
        files = manifest["mlx_bf16"]["files"]
    else:
        raise VerificationError("unsupported model inventory key")
    require(len(files) == spec["file_count"], "model inventory count drift")
    require(sum(int(item["bytes"]) for item in files) == spec["total_bytes"], "model inventory byte drift")
    root = checked_path(archive_root, spec["root_path"])
    require(root.is_dir() and not root.is_symlink(), "model root invalid")
    expected_names = {item["path"] for item in files}
    actual_names = {str(item.relative_to(root)) for item in root.rglob("*") if item.is_file()}
    require(actual_names == expected_names, "model root inventory drift")
    for item in files:
        path = checked_path(root, item["path"])
        regular_file(path, "model file")
        require(path.stat().st_size == item["bytes"] and sha256(path) == item["sha256"], "model file drift")
    return {
        "repo_id": spec["repo_id"],
        "revision": spec["revision"],
        "manifest_sha256": spec["manifest_sha256"],
        "file_count": len(files),
        "total_bytes": spec["total_bytes"],
        "all_file_hashes_verified": True,
        "framework_imported": False,
    }


def validate_config(config: dict[str, Any], contract: Any) -> None:
    require(set(config) == EXPECTED_TOP_LEVEL, "config top-level schema drift")
    require(
        config["schema_version"] == "sqma-001-strict-base-readiness-preflight-v1"
        and config["experiment_id"] == "SQMA-001"
        and config["tier"] == "Minor"
        and config["stage"] == "strict-base-readiness-preflight",
        "config identity drift",
    )
    require(config["authorization"] == EXPECTED_AUTHORIZATION, "authorization drift")
    for section in ("implementation", "prerequisites"):
        for record in config[section].values():
            require(record["sha256"] != "TO_BE_REGISTERED" and record["bytes"] > 0, "unregistered source")
    plan = fit_specs(config, contract)
    require(tuple(item.fit_id for item in plan if item.phase == "dev") == tuple(config["data"]["active_fit_ids"]), "active fit drift")
    require(config["data"]["fold4_in_fit_plan"] is False, "fold4 plan drift")
    require(config["data"]["future_plan_is_declarative_only"] is True, "future plan authority drift")
    require(config["private_source_contract"]["paths_resolved_or_opened"] is False, "private source path authority drift")
    require(config["private_source_contract"]["bytes_hashed_by_sqma001"] is False, "private byte access drift")
    require(config["private_source_contract"]["rows_parsed"] is False, "private row access drift")
    require(config["snapshot_contract"]["heldout_logits_contains_gold"] is False, "heldout gold drift")
    require(config["outputs"]["private_output_dir"] is None, "private output drift")
    require(config["outputs"]["allowed_files_after_completion"] == ["run.json", "verification.json", "complete.json"], "output allowlist drift")


def output_dir(config: dict[str, Any]) -> Path:
    root = (PROJECT_ROOT / "runs").resolve()
    path = checked_path(REPO_ROOT, config["outputs"]["public_attempt_dir"])
    require(path.parent.parent == root, "output namespace drift")
    return path


def recompute(config: dict[str, Any], contract: Any) -> dict[str, Any]:
    for section in ("implementation", "prerequisites"):
        for record in config[section].values():
            verify_record(record)
    d0 = read_json(verify_record(config["prerequisites"]["d0_static_contract"]))
    require(all(value is False for value in d0["authorization"].values()), "D0 execution authority drift")
    dependency = read_json(verify_record(config["prerequisites"]["d0_dependency_manifest"]))
    private_contract = config["private_source_contract"]
    private_registered = dependency["private_dependencies"]
    require(private_contract["train_sha256"] == private_registered["train"]["sha256"], "private train identity string drift")
    require(private_contract["fold_manifest_private_sha256"] == private_registered["fold_manifest_private"]["sha256"], "private manifest identity string drift")

    manifest_path = verify_record(config["prerequisites"]["public_fold_manifest"])
    rows = contract.load_public_manifest(manifest_path)
    aggregate = contract.validate_exp058_public_manifest(rows)
    public_contract = {
        "schema_version": aggregate["schema_version"],
        "rows": aggregate["rows"],
        "components": aggregate["components"],
        "membership_sha256": aggregate["membership_sha256"],
        "active_folds": {str(fold): aggregate["folds"][str(fold)] for fold in range(3)},
    }
    active = list(contract.summarize_active_dev(rows))
    expected_active = config["data"]["active_expected"]
    for item in active:
        expected = expected_active[item["fit_id"]]
        require(item["training"]["rows"] == expected["training_rows"], "active training row drift")
        require(item["training"]["components"] == expected["training_components"], "active training component drift")
        require(item["heldout"]["rows"] == expected["heldout_rows"], "active heldout row drift")
        require(item["heldout"]["components"] == expected["heldout_components"], "active heldout component drift")
    contract.assert_public_safe(public_contract)
    contract.assert_public_safe(active)

    model_spec = config["model_assets"]
    archive_value = os.environ.get(model_spec["archive_root_env"], model_spec["audited_archive_root"])
    require(bool(archive_value), "archive root empty")
    archive_root = Path(archive_value).expanduser().resolve()
    require(archive_root.is_dir(), "archive root unavailable")
    models = {key: model_probe(archive_root, value) for key, value in (('m1', model_spec['m1']), ('m3', model_spec['m3']))}
    require(config["runtimes"]["probe"] == "isolated_-I_-S_stdlib_plus_direct_dist_info_no_framework_import", "runtime probe contract drift")
    runtimes = {key: runtime_probe(config["runtimes"][key]) for key in ("m1", "m3")}
    for value in runtimes.values():
        value["packages"] = dict(sorted(value["packages"].items()))
        value["isolated"] = True
        value["site_disabled"] = True
        value["framework_imported"] = False
    return {
        "public_fold_contract": public_contract,
        "active_dev_fits": active,
        "model_assets": models,
        "runtimes": runtimes,
    }


def sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    forbidden = {"sample_id", "sample_ids", "component_id", "component_ids", "text", "texts", "gold", "labels", "logits", "probabilities"}
    output: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in forbidden:
                output.append(path)
            output.extend(sensitive_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            output.extend(sensitive_paths(child, f"{prefix}[{index}]"))
    elif isinstance(value, str) and (value.startswith("sample-") or value.startswith("component-")):
        output.append(prefix)
    return output


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    require(not os.path.lexists(temporary), "temporary output exists")
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def verify(config_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    config = read_json(config_path)
    contract = load_contract(config["implementation"]["contract"])
    validate_config(config, contract)
    attempt = output_dir(config)
    regular_file(attempt / "run.json", "SQMA-001 run")
    require(not os.path.lexists(attempt / "verification.json") and not os.path.lexists(attempt / "complete.json"), "verification output already exists")
    require({item.name for item in attempt.iterdir()} == {"run.json"}, "unexpected pre-verification output")
    expected = recompute(config, contract)
    run = read_json(attempt / "run.json")
    required_run_keys = {
        "schema_version", "experiment_id", "tier", "stage", "status", "started_at_utc", "completed_at_utc",
        "config", "claim_boundary", "public_fold_contract", "active_dev_fits", "model_assets", "runtimes",
        "resources", "access", "next_gate"
    }
    require(set(run) == required_run_keys, "run top-level schema drift")
    require(run["schema_version"] == "sqma-001-strict-base-preflight-run-v1" and run["experiment_id"] == "SQMA-001", "run identity drift")
    require(run["tier"] == "Minor" and run["stage"] == config["stage"] and run["status"] == "CompletedAwaitingVerification", "run status drift")
    require(run["config"] == artifact(config_path), "run config identity drift")
    for key, value in expected.items():
        require(run[key] == value, f"run recomputation drift: {key}")
    require(run["access"] == EXPECTED_ACCESS, "run access drift")
    require(run["next_gate"] == "independent_dev_scoped_input_materialization", "next gate drift")
    require(
        run["claim_boundary"]
        == "Static Agent-Dev strict-base identities and the three-fit public fold plan were checked without opening private sources, loading models, training, forwarding, calling Agents, or producing strict outputs. Formal training remains unauthorized.",
        "claim boundary drift",
    )
    resources = run["resources"]
    require(
        set(resources)
        == {
            "wall_seconds",
            "peak_rss_bytes",
            "free_disk_bytes_before",
            "public_output_bytes",
            "maximum_wall_seconds",
            "maximum_peak_rss_bytes",
            "minimum_free_disk_bytes",
            "model_or_mlx_allocations",
            "critical_memory_events",
            "oom_or_kill_events",
            "orphan_processes_after_exit",
        },
        "resource schema drift",
    )
    require(resources["wall_seconds"] <= config["resources"]["maximum_wall_seconds"], "runner wall budget exceeded")
    require(resources["peak_rss_bytes"] <= config["resources"]["maximum_peak_rss_bytes"], "runner RSS budget exceeded")
    require(resources["free_disk_bytes_before"] >= config["resources"]["minimum_free_disk_bytes"], "formal disk gate failed")
    require(resources["public_output_bytes"] == (attempt / "run.json").stat().st_size, "runner output byte record drift")
    require(resources["model_or_mlx_allocations"] == 0, "model allocation drift")
    require(resources["critical_memory_events"] == 0 and resources["oom_or_kill_events"] == 0, "memory event drift")
    require(resources["orphan_processes_after_exit"] == 0, "orphan process drift")
    require((attempt / "run.json").stat().st_size <= config["resources"]["maximum_public_output_bytes"], "run output budget exceeded")
    require(not sensitive_paths(run), "run contains sensitive public content")
    require(not contract.public_sensitive_paths(run), "run violates contract public allowlist")

    checks = [
        "config_identity", "authorization_false_for_execution", "source_hashes", "d0_authority",
        "private_identity_strings_only", "seven_fit_plan", "active_dev_three_fit_plan", "public_fold_membership",
        "m1_schedule", "m3_schedule", "snapshot_contract", "heldout_gold_forbidden",
        "m1_model_assets", "m3_model_assets", "m1_runtime", "m3_runtime", "output_append_only",
        "public_privacy", "resource_gate", "access_report"
    ]
    verifier_wall = time.perf_counter() - started
    verifier_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform.startswith("linux"):
        verifier_rss *= 1024
    require(verifier_wall <= config["resources"]["maximum_wall_seconds"], "verifier wall budget exceeded")
    require(verifier_rss <= config["resources"]["maximum_peak_rss_bytes"], "verifier RSS budget exceeded")
    verification = {
        "schema_version": "sqma-001-verification-v1",
        "experiment_id": "SQMA-001",
        "status": "Passed",
        "verified_at_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "config": artifact(config_path),
        "run": artifact(attempt / "run.json"),
        "checks": checks,
        "checks_passed": len(checks),
        "checks_failed": 0,
        "resources": {"wall_seconds": verifier_wall, "peak_rss_bytes": verifier_rss},
        "access": EXPECTED_ACCESS,
        "formal_training_authorized": False,
    }
    complete = {
        "schema_version": "sqma-001-complete-v1",
        "experiment_id": "SQMA-001",
        "status": "Complete",
        "sqma001_complete": True,
        "run": artifact(attempt / "run.json"),
        "verification_pending_artifact": True,
        "training_executed": False,
        "model_loaded": False,
        "private_rows_parsed": False,
        "strict_outputs_exist": False,
        "formal_training_authorized": False,
        "next_gate": "independent_dev_scoped_input_materialization",
    }
    return verification, complete


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    require(config_path == (PROJECT_ROOT / "configs" / "sqma-001-strict-base-readiness-preflight.json").resolve(), "noncanonical config path")
    verification, complete = verify(config_path)
    config = read_json(config_path)
    attempt = output_dir(config)
    atomic_json(attempt / "verification.json", verification)
    complete["verification"] = artifact(attempt / "verification.json")
    complete.pop("verification_pending_artifact")
    atomic_json(attempt / "complete.json", complete)
    require(sum(item.stat().st_size for item in attempt.iterdir()) <= config["resources"]["maximum_public_output_bytes"], "total output budget exceeded")
    print(json.dumps({"status": "Passed", "experiment_id": "SQMA-001", "sqma001_complete": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, VerificationError, subprocess.SubprocessError) as exc:
        print(f"SQMA-001 verification Failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
