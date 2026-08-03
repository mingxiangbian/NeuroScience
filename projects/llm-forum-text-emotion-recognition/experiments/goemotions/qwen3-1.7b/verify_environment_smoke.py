#!/usr/bin/env python3
"""Independently verify EXP-021 artifacts and local model integrity."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
RUN_DIR = SCRIPT_DIR / "runs" / "exp-021-environment-model-smoke"
RUN_PATH = RUN_DIR / "run.json"
OUTPUT_PATH = RUN_DIR / "verification.json"
MODEL_ROOTS = [
    PROJECT_ROOT / "models" / "qwen3-1.7b",
    PROJECT_ROOT / "models" / "qwen3-1.7b-base",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_inventory(
    root: Path,
    expected: dict[str, Any],
) -> dict[str, Any]:
    actual_files = []
    for item in expected["files"]:
        path = root / item["path"]
        actual = {
            "bytes": path.stat().st_size,
            "path": item["path"],
            "sha256": sha256(path),
        }
        if actual != item:
            raise ValueError(
                f"Integrity mismatch for {path}: expected {item}, got {actual}"
            )
        actual_files.append(actual)
    total = sum(item["bytes"] for item in actual_files)
    if total != expected["total_bytes"]:
        raise ValueError(
            f"Total byte mismatch for {root}: {total} != {expected['total_bytes']}"
        )
    return {
        "file_count": len(actual_files),
        "total_bytes": total,
    }


def verify_ignored(path: Path) -> None:
    probe = next(path.rglob("*.safetensors"))
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(probe)],
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"Model binary is not ignored by Git: {probe}")


def main() -> None:
    if OUTPUT_PATH.exists():
        raise FileExistsError(f"Refusing to overwrite: {OUTPUT_PATH}")
    run = json.loads(RUN_PATH.read_text(encoding="utf-8"))
    checks: dict[str, Any] = {
        "environment": {},
        "models": [],
        "run": {},
    }

    if run["experiment_id"] != "EXP-021" or run["status"] != "Completed":
        raise ValueError("EXP-021 run is not completed")
    if run["accessed_splits"] or run["data"]["project_data_rows"] != 0:
        raise ValueError("EXP-021 unexpectedly reports project data access")
    if run["test_split_accessed"] or run["validation_split_accessed"]:
        raise ValueError("EXP-021 unexpectedly reports validation/test access")

    package_versions = {
        name: importlib.metadata.version(name)
        for name in (
            "huggingface-hub",
            "mlx",
            "mlx-lm",
            "transformers",
        )
    }
    if package_versions != {
        name: run["runtime"]["packages"][name] for name in package_versions
    }:
        raise ValueError("Current package versions differ from run metadata")
    checks["environment"] = {
        "packages": package_versions,
        "lock_sha256": sha256(RUN_DIR / "environment-lock.txt"),
    }
    if (
        checks["environment"]["lock_sha256"]
        != run["artifacts"]["environment_lock"]["sha256"]
    ):
        raise ValueError("Environment lock hash mismatch")

    expected_revisions = {
        "Qwen/Qwen3-1.7B": "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e",
        "Qwen/Qwen3-1.7B-Base": "ea980cb0a6c2ae4b936e82123acc929f1cec04c1",
    }
    for root in MODEL_ROOTS:
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if expected_revisions.get(manifest["repo_id"]) != manifest["revision"]:
            raise ValueError(f"Unexpected model revision in {manifest_path}")
        upstream = PROJECT_ROOT / manifest["local_paths"]["upstream"]
        mlx_path = PROJECT_ROOT / manifest["local_paths"]["mlx_bf16"]
        verify_ignored(upstream)
        verify_ignored(mlx_path)
        checks["models"].append(
            {
                "condition": manifest["condition"],
                "manifest_sha256": sha256(manifest_path),
                "mlx_bf16": verify_inventory(
                    mlx_path,
                    manifest["mlx_bf16"],
                ),
                "quantized": manifest["conversion"]["quantized"],
                "repo_id": manifest["repo_id"],
                "revision": manifest["revision"],
                "upstream": verify_inventory(
                    upstream,
                    manifest["upstream"],
                ),
            }
        )

    for condition in ("base", "post-trained"):
        smoke_path = RUN_DIR / f"smoke-{condition}.json"
        smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
        if (
            not smoke["generated_nonempty"]
            or smoke["accessed_splits"]
            or smoke["test_split_accessed"]
            or smoke["validation_split_accessed"]
        ):
            raise ValueError(f"Invalid smoke record: {smoke_path}")

    checks["run"] = {
        "accessed_splits": run["accessed_splits"],
        "model_count": len(run["models"]),
        "project_data_rows": run["data"]["project_data_rows"],
        "status": run["status"],
        "test_split_accessed": run["test_split_accessed"],
        "validation_split_accessed": run["validation_split_accessed"],
    }
    report = {
        "checks": checks,
        "experiment_id": "EXP-021",
        "status": "Verified",
    }
    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["checks"]["run"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

