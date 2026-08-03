#!/usr/bin/env python3
"""Download, convert, and smoke-test the paired Qwen3-1.7B models."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from huggingface_hub import model_info, snapshot_download


EXPERIMENT_ID = "EXP-021"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
RUN_DIR = SCRIPT_DIR / "runs" / "exp-021-environment-model-smoke"
MAX_MODEL_BYTES = 16 * 1024**3
MODEL_SPECS = [
    {
        "condition": "post-trained",
        "repo_id": "Qwen/Qwen3-1.7B",
        "revision": "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e",
        "root": PROJECT_ROOT / "models" / "qwen3-1.7b",
        "smoke_condition": "post-trained",
        "training_stage": "pretraining and post-training",
    },
    {
        "condition": "base",
        "repo_id": "Qwen/Qwen3-1.7B-Base",
        "revision": "ea980cb0a6c2ae4b936e82123acc929f1cec04c1",
        "root": PROJECT_ROOT / "models" / "qwen3-1.7b-base",
        "smoke_condition": "base",
        "training_stage": "pretraining only",
    },
]


class Tee:
    def __init__(self, *streams: Any) -> None:
        self.streams = streams

    def write(self, data: str) -> int:
        for stream in self.streams:
            stream.write(data)
            stream.flush()
        return len(data)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()

    def isatty(self) -> bool:
        return False


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".cache" in path.parts:
            continue
        files.append(
            {
                "bytes": path.stat().st_size,
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256(path),
            }
        )
    return {
        "file_count": len(files),
        "files": files,
        "total_bytes": sum(item["bytes"] for item in files),
    }


def git_metadata() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return {
        "commit": commit,
        "dirty": bool(status),
        "dirty_path_count": len(status),
    }


def package_versions() -> dict[str, str]:
    names = [
        "huggingface-hub",
        "mlx",
        "mlx-lm",
        "numpy",
        "safetensors",
        "tokenizers",
        "transformers",
    ]
    return {name: importlib.metadata.version(name) for name in names}


def hardware_metadata() -> dict[str, Any]:
    memory_bytes = int(
        subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    chip = subprocess.run(
        ["sysctl", "-n", "machdep.cpu.brand_string"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return {
        "architecture": platform.machine(),
        "chip": chip,
        "memory_bytes": memory_bytes,
        "platform": platform.platform(),
    }


def run_logged(
    command: list[str],
    *,
    environment: dict[str, str] | None = None,
) -> None:
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    result.check_returncode()


def download_model(spec: dict[str, Any]) -> Path:
    remote = model_info(spec["repo_id"], revision=spec["revision"])
    if remote.sha != spec["revision"]:
        raise ValueError(
            f"Resolved revision mismatch for {spec['repo_id']}: "
            f"{remote.sha} != {spec['revision']}"
        )

    upstream = spec["root"] / "upstream"
    upstream.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {spec['repo_id']}@{spec['revision']}")
    resolved = Path(
        snapshot_download(
            repo_id=spec["repo_id"],
            revision=spec["revision"],
            local_dir=upstream,
        )
    ).resolve()
    if resolved != upstream.resolve():
        raise ValueError(f"Unexpected snapshot path: {resolved}")
    if not any(upstream.glob("*.safetensors")):
        raise FileNotFoundError(f"No safetensors weights in {upstream}")
    return upstream


def convert_model(spec: dict[str, Any], upstream: Path) -> Path:
    mlx_path = spec["root"] / "mlx-bf16"
    temp_path = spec["root"] / "mlx-bf16.tmp"
    if mlx_path.exists() and any(mlx_path.glob("*.safetensors")):
        print(f"Using existing complete conversion: {mlx_path}")
        return mlx_path
    if temp_path.exists():
        raise FileExistsError(
            f"Partial conversion requires manual review before retry: {temp_path}"
        )

    converter = Path(sys.executable).parent / "mlx_lm.convert"
    command = [
        str(converter),
        "--hf-path",
        str(upstream),
        "--mlx-path",
        str(temp_path),
        "--dtype",
        "bfloat16",
    ]
    print("Converting with:", " ".join(command))
    run_logged(command)
    if not any(temp_path.glob("*.safetensors")):
        raise FileNotFoundError(f"Conversion produced no safetensors: {temp_path}")
    temp_path.rename(mlx_path)
    return mlx_path


def write_manifest(
    spec: dict[str, Any],
    upstream: Path,
    mlx_path: Path,
    downloaded_at: str,
) -> tuple[Path, dict[str, Any]]:
    manifest = {
        "condition": spec["condition"],
        "conversion": {
            "command": [
                str(Path(sys.executable).parent / "mlx_lm.convert"),
                "--hf-path",
                str(upstream.relative_to(PROJECT_ROOT)),
                "--mlx-path",
                str(mlx_path.relative_to(PROJECT_ROOT)),
                "--dtype",
                "bfloat16",
            ],
            "dtype": "bfloat16",
            "mlx": importlib.metadata.version("mlx"),
            "mlx_lm": importlib.metadata.version("mlx-lm"),
            "quantized": False,
        },
        "download_method": "huggingface_hub.snapshot_download",
        "downloaded_at_utc": downloaded_at,
        "local_paths": {
            "mlx_bf16": str(mlx_path.relative_to(PROJECT_ROOT)),
            "upstream": str(upstream.relative_to(PROJECT_ROOT)),
        },
        "mlx_bf16": inventory(mlx_path),
        "repo_id": spec["repo_id"],
        "revision": spec["revision"],
        "training_stage": spec["training_stage"],
        "upstream": inventory(upstream),
    }
    path = spec["root"] / "manifest.json"
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path, manifest


def run_smoke(spec: dict[str, Any], mlx_path: Path) -> tuple[Path, dict[str, Any]]:
    output = RUN_DIR / f"smoke-{spec['condition']}.json"
    command = [
        sys.executable,
        str(SCRIPT_DIR / "smoke_one_model.py"),
        "--condition",
        spec["smoke_condition"],
        "--model-dir",
        str(mlx_path),
        "--output",
        str(output),
    ]
    environment = os.environ.copy()
    environment.update(
        {
            "HF_HUB_OFFLINE": "1",
            "PYTHONNOUSERSITE": "1",
            "TRANSFORMERS_OFFLINE": "1",
        }
    )
    print("Running smoke:", " ".join(command))
    run_logged(command, environment=environment)
    return output, json.loads(output.read_text(encoding="utf-8"))


def write_environment_lock() -> Path:
    environment = os.environ.copy()
    environment["PYTHONNOUSERSITE"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "pip", "--isolated", "freeze"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    if not result.stdout.strip():
        raise RuntimeError("pip freeze returned an empty environment lock")
    path = RUN_DIR / "environment-lock.txt"
    path.write_text(result.stdout, encoding="utf-8")
    return path


def main() -> None:
    if RUN_DIR.exists() and any(RUN_DIR.iterdir()):
        raise FileExistsError(f"Append-only run directory is not empty: {RUN_DIR}")
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    run: dict[str, Any] = {
        "accessed_splits": [],
        "errors": [],
        "experiment_id": EXPERIMENT_ID,
        "rq_id": "RQ-G2",
        "stage": "environment-and-model-provenance",
        "started_at_utc": started_at.isoformat(),
        "status": "In Progress",
        "test_split_accessed": False,
        "tier": "Minor",
        "validation_split_accessed": False,
        "warnings": [
            "The first pip install attempt followed global.user=true and was "
            "not importable with user-site disabled.",
            "The second and final setup attempt used pip --isolated --no-user "
            "and installed packages inside the Conda environment.",
            "Synthetic generation is an implementation check, not task evidence.",
        ],
    }
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    log_path = RUN_DIR / "stdout.log"
    with log_path.open("w", encoding="utf-8") as log:
        sys.stdout = Tee(original_stdout, log)
        sys.stderr = Tee(original_stderr, log)
        try:
            print(f"Starting {EXPERIMENT_ID} at {started_at.isoformat()}")
            versions = package_versions()
            if versions["mlx-lm"] != "0.31.3":
                raise ValueError(f"Unexpected mlx-lm version: {versions['mlx-lm']}")
            if not sys.flags.no_user_site:
                raise RuntimeError("PYTHONNOUSERSITE must be enabled")

            lock_path = write_environment_lock()
            model_records = []
            total_model_bytes = 0
            for spec in MODEL_SPECS:
                downloaded_at = datetime.now(timezone.utc).isoformat()
                upstream = download_model(spec)
                mlx_path = convert_model(spec, upstream)
                manifest_path, manifest = write_manifest(
                    spec,
                    upstream,
                    mlx_path,
                    downloaded_at,
                )
                smoke_path, smoke = run_smoke(spec, mlx_path)
                total_model_bytes += (
                    manifest["upstream"]["total_bytes"]
                    + manifest["mlx_bf16"]["total_bytes"]
                )
                model_records.append(
                    {
                        "condition": spec["condition"],
                        "manifest": {
                            "path": str(manifest_path.relative_to(PROJECT_ROOT)),
                            "sha256": sha256(manifest_path),
                        },
                        "mlx_total_bytes": manifest["mlx_bf16"]["total_bytes"],
                        "repo_id": spec["repo_id"],
                        "revision": spec["revision"],
                        "smoke": {
                            "generated_nonempty": smoke["generated_nonempty"],
                            "generated_token_count": smoke["generated_token_count"],
                            "path": str(smoke_path.relative_to(PROJECT_ROOT)),
                            "sha256": sha256(smoke_path),
                        },
                        "upstream_total_bytes": manifest["upstream"]["total_bytes"],
                    }
                )

            if total_model_bytes > MAX_MODEL_BYTES:
                raise ValueError(
                    f"Model storage {total_model_bytes} exceeds {MAX_MODEL_BYTES}"
                )

            run.update(
                {
                    "artifacts": {
                        "environment_lock": {
                            "path": str(lock_path.relative_to(PROJECT_ROOT)),
                            "sha256": sha256(lock_path),
                        },
                        "stdout_log": {
                            "path": str(log_path.relative_to(PROJECT_ROOT)),
                        },
                    },
                    "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                    "data": {
                        "dataset": "synthetic inputs only",
                        "project_data_rows": 0,
                        "split": "N/A",
                    },
                    "invocation": [sys.executable, *sys.argv],
                    "models": model_records,
                    "resource_usage": {
                        "api_cost_usd": 0,
                        "model_storage_bytes": total_model_bytes,
                        "total_seconds": time.perf_counter() - started,
                    },
                    "runtime": {
                        "environment": "emotion-llm-mlx",
                        "executable": sys.executable,
                        "git": git_metadata(),
                        "hardware": hardware_metadata(),
                        "packages": versions,
                        "python": platform.python_version(),
                        "user_site_disabled": bool(sys.flags.no_user_site),
                    },
                    "status": "Completed",
                }
            )
        except Exception as error:
            run["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
            run["errors"].append(
                {
                    "message": str(error),
                    "traceback": traceback.format_exc(),
                    "type": type(error).__name__,
                }
            )
            run["resource_usage"] = {
                "api_cost_usd": 0,
                "total_seconds": time.perf_counter() - started,
            }
            run["status"] = "Rejected"
            raise
        finally:
            run_path = RUN_DIR / "run.json"
            run_path.write_text(
                json.dumps(run, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            sys.stdout = original_stdout
            sys.stderr = original_stderr

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "model_storage_bytes": run["resource_usage"].get(
                    "model_storage_bytes"
                ),
                "status": run["status"],
                "total_seconds": run["resource_usage"]["total_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
