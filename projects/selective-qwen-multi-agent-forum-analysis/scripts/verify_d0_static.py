#!/usr/bin/env python3
"""Verify the D0 static contract without loading a model or parsing private rows."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any


EXPECTED_STATIC_CONTRACT_SHA256 = "b0226e0113f34ddacca97d68d1be445ca019edf01175e42ccb0910330aab32ad"


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def read_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing JSON: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON: {path}: {exc}") from exc
    require(isinstance(value, dict), f"JSON root must be object: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob(path: Path) -> str:
    payload = path.read_bytes()
    digest = hashlib.sha1()
    digest.update(f"blob {len(payload)}\0".encode("ascii"))
    digest.update(payload)
    return digest.hexdigest()


def checked_path(root: Path, relative: str) -> Path:
    require(relative and not Path(relative).is_absolute(), f"expected relative path: {relative}")
    path = (root / relative).resolve()
    require(path == root or root in path.parents, f"path escapes root: {relative}")
    return path


def verify_file(path: Path, expected_sha256: str, expected_bytes: int | None = None) -> None:
    require(path.is_file(), f"missing file: {path}")
    if expected_bytes is not None:
        require(path.stat().st_size == expected_bytes, f"byte drift: {path}")
    require(sha256(path) == expected_sha256, f"SHA-256 drift: {path}")


def verify_mode(path: Path, expected: str) -> None:
    actual = f"{stat.S_IMODE(path.stat().st_mode):04o}"
    require(actual == expected, f"mode drift: {path}: {actual} != {expected}")


def runtime_snapshot(executable: Path) -> dict[str, Any]:
    code = r'''
import json
import platform
print(json.dumps({
    "python": platform.python_version(),
    "machine": platform.machine(),
}, sort_keys=True))
'''
    probe_env = {
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
        env=probe_env,
    )
    require(completed.returncode == 0, f"runtime probe failed: {completed.stderr.strip()}")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise VerificationError("runtime probe returned invalid JSON") from exc
    require(isinstance(value, dict), "runtime probe root must be object")
    return value


def normalized_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def installed_distribution_versions(site_packages: Path) -> dict[str, str]:
    require(site_packages.is_dir(), f"site-packages missing: {site_packages}")
    versions: dict[str, str] = {}
    for metadata_path in site_packages.glob("*.dist-info/METADATA"):
        name = None
        version = None
        for line in metadata_path.read_text(encoding="utf-8", errors="strict").splitlines():
            if line.startswith("Name: ") and name is None:
                name = normalized_distribution_name(line[6:])
            elif line.startswith("Version: ") and version is None:
                version = line[9:]
            if name is not None and version is not None:
                break
        if name is not None and version is not None:
            versions[name] = version
    return versions


def commit_blob(repo_root: Path, commit: str, relative_path: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", f"{commit}:{relative_path}"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    require(completed.returncode == 0, f"source commit path missing: {relative_path}")
    return completed.stdout.strip()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    project_root = Path(__file__).resolve().parents[1]
    dependency_path = project_root / "configs" / "d0-dependency-manifest.json"
    static_path = project_root / "configs" / "d0-static-contract.json"
    dependency = read_json(dependency_path)
    static_contract = read_json(static_path)

    static_sha256 = sha256(static_path)
    require(static_sha256 == EXPECTED_STATIC_CONTRACT_SHA256, "static method contract identity drift")

    registered_dependency = static_contract["dependency_manifest"]
    registered_dependency_path = checked_path(repo_root, registered_dependency["path"])
    require(registered_dependency_path == dependency_path.resolve(), "dependency manifest path drift")
    require(
        sha256(dependency_path) == registered_dependency["sha256"],
        "dependency manifest identity drift",
    )

    require(static_contract["status"] == "static_contract_registered_no_execution_authority", "static status drift")
    require(all(value is False for value in static_contract["authorization"].values()), "execution authority drift")
    strict = static_contract["strict_base_production"]
    require(strict["validation_access"] is False and strict["test_access"] is False and strict["fold4_access"] is False, "strict access drift")
    confirm_access = static_contract["confirm_access"]
    require(confirm_access["raw_source_npz_contains_gold"] is True, "Confirm source declaration drift")
    require(confirm_access["producer_may_open_raw_source_npz"] is False, "Confirm producer access drift")

    public_count = 0
    source_commit = dependency["source_snapshot_commit"]
    for entry in dependency["public_dependencies"]:
        path = checked_path(repo_root, entry["path"])
        verify_file(path, entry["sha256"])
        require(git_blob(path) == entry["git_blob"], f"Git blob drift: {path}")
        require(commit_blob(repo_root, source_commit, entry["path"]) == entry["git_blob"], f"source commit blob drift: {path}")
        public_count += 1

    for key in ("prompt_bundle", "output_schema"):
        entry = static_contract[key]
        path = checked_path(repo_root, entry["path"])
        verify_file(path, entry["sha256"])
        read_json(path)
    validator = static_contract["runtime_validator"]
    verify_file(checked_path(repo_root, validator["path"]), validator["sha256"])
    verify_file(checked_path(repo_root, validator["tests_path"]), validator["tests_sha256"])

    private_spec = dependency["private_dependencies"]
    archive_env = private_spec["archive_root_env"]
    archive_value = os.environ.get(archive_env, private_spec["audited_archive_root"])
    require(bool(archive_value), f"empty archive root: {archive_env}")
    archive_root = Path(archive_value).expanduser().resolve()
    require(archive_root.is_absolute() and archive_root.is_dir(), f"invalid archive root: {archive_root}")

    private_count = 0
    for key in ("train", "fold_manifest_private", "confirm_m1_source", "confirm_m3_source"):
        entry = private_spec[key]
        path = checked_path(archive_root, entry["relative_path"])
        verify_file(path, entry["sha256"], entry["bytes"])
        verify_mode(path, entry["mode"])
        require(path.stat().st_uid == os.getuid(), f"owner drift: {path}")
        private_count += 1
    for key in ("confirm_m1_source", "confirm_m3_source"):
        entry = private_spec[key]
        require(entry["contains_gold_field"] is True, f"gold-field declaration drift: {key}")
        require(entry["producer_access"] == "forbidden", f"producer access drift: {key}")
    require(
        private_spec["confirm_readiness"]
        == "blocked_until_independent_gold_free_snapshot_is_sealed",
        "Confirm readiness must remain blocked",
    )

    model = dependency["agent_model"]
    model_dir = checked_path(archive_root, model["relative_path"])
    require(model_dir.is_dir(), f"missing model directory: {model_dir}")
    model_manifest_path = checked_path(archive_root, model["manifest_path"])
    verify_file(model_manifest_path, model["manifest_sha256"])
    model_manifest = read_json(model_manifest_path)
    require(model_manifest["repo_id"] == model["repo_id"], "model repo drift")
    require(model_manifest["revision"] == model["revision"], "model revision drift")
    files = model_manifest["mlx_bf16"]["files"]
    require(len(files) == model["file_count"], "model file count drift")
    require(model_manifest["mlx_bf16"]["total_bytes"] == model["total_bytes"], "model byte total drift")
    for entry in files:
        verify_file(checked_path(model_dir, entry["path"]), entry["sha256"], entry["bytes"])

    runtime = dependency["runtime"]
    executable = Path(runtime["executable"])
    require(executable.is_file() and os.access(executable, os.X_OK), f"runtime missing: {executable}")
    observed = runtime_snapshot(executable)
    require(observed["python"] == runtime["packages"]["python"], "Python version drift")
    require(observed["machine"] == runtime["machine"], "runtime architecture drift")
    python_major_minor = ".".join(runtime["packages"]["python"].split(".")[:2])
    site_packages = executable.parent.parent / "lib" / f"python{python_major_minor}" / "site-packages"
    installed = installed_distribution_versions(site_packages)
    for name, expected_version in runtime["packages"].items():
        if name == "python":
            continue
        normalized = normalized_distribution_name(name)
        require(installed.get(normalized) == expected_version, f"package drift: {name}")
    qwen3_path = checked_path(site_packages, runtime["mlx_qwen3_implementation_path"])
    verify_file(qwen3_path, runtime["mlx_qwen3_implementation_sha256"])

    summary = {
        "schema_version": "sqma-d0-static-verification-v1",
        "status": "Passed",
        "public_dependencies_verified": public_count,
        "private_identities_verified": private_count,
        "model_files_verified": len(files),
        "runtime_verified": True,
        "static_contract_sha256": static_sha256,
        "confirm_ready": False,
        "access": {
            "model_loaded": False,
            "private_rows_parsed": False,
            "gold_values_read": False,
            "validation_accessed": False,
            "test_accessed": False,
            "network_accessed": False,
            "files_written": False,
            "runtime_probe_isolated_and_site_disabled": True,
        },
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, VerificationError, OSError, subprocess.SubprocessError) as exc:
        print(f"D0 static verification Failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
