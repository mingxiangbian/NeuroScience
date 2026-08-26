#!/usr/bin/env python3
"""Orchestrate the one-shot EXP-067 B0/B1/B2 steady-state benchmark."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys
import time
from typing import Any

import numpy as np


EXPERIMENT_ID = "EXP-067"
RUN_ID = "exp-067-steady-state-benchmark"
CONFIG_SCHEMA = "exp-067-steady-state-benchmark-config-v1"
LATIN_ORDER = (
    (1, "B0"), (1, "B1"), (1, "B2"),
    (2, "B1"), (2, "B2"), (2, "B0"),
    (3, "B2"), (3, "B0"), (3, "B1"),
)
CLAIM_BOUNDARY = (
    "A same-device, model-loaded, batch-size-1 steady-state latency and memory benchmark for "
    "the frozen seed-42 local development runtime only; no cold-start, production, independent-test, "
    "classification-performance, forum-generalization, or emotion-mechanism claim."
)
PUBLIC_SENSITIVE_KEYS = {
    "text", "raw_text", "ordinal", "ordinals", "opaque_component_group",
    "sample_id", "sample_ids", "component_id", "component_ids", "probabilities",
    "prediction", "predictions", "final_prediction", "route_mask", "selected_path",
    "timing_rows", "memory_samples", "pid", "pids",
}


def _project_root(source: Path) -> Path:
    for candidate in (source, *source.parents):
        if candidate.name == "llm-forum-text-emotion-recognition":
            return candidate
    raise RuntimeError("Could not locate project root")


PROJECT_ROOT = _project_root(Path(__file__).resolve())
BASE = Path("experiments/stack-overflow-emotion-gold/oof-router")
DEFAULT_CONFIG = PROJECT_ROOT / BASE / "configs/exp-067-steady-state-benchmark.json"
PUBLIC_REL = BASE / "runs" / RUN_ID
PRIVATE_REL = BASE / "private" / RUN_ID


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def _resolve(value: str | Path) -> Path:
    relative = Path(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"Unsafe path: {value}")
    cursor = PROJECT_ROOT
    for part in relative.parts:
        cursor = cursor / part
        if os.path.lexists(cursor) and stat.S_ISLNK(os.lstat(cursor).st_mode):
            raise ValueError(f"Path traverses symlink: {value}")
    result = (PROJECT_ROOT / relative).resolve()
    if not result.is_relative_to(PROJECT_ROOT.resolve()):
        raise ValueError(f"Path escapes project: {value}")
    return result


def artifact(path: Path, include_path: bool = True) -> dict[str, Any]:
    metadata = os.lstat(path)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ValueError(f"Artifact type drift: {path}")
    value: dict[str, Any] = {
        "bytes": metadata.st_size,
        "sha256": sha256(path),
        "mode": f"{stat.S_IMODE(metadata.st_mode):04o}",
    }
    if include_path:
        value["path"] = str(path.relative_to(PROJECT_ROOT))
    return value


def require_record(value: dict[str, Any], mode: int) -> Path:
    if set(value) != {"path", "bytes", "sha256", "mode"}:
        raise ValueError("Artifact record schema drift")
    path = _resolve(value["path"])
    metadata = os.lstat(path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != mode
        or metadata.st_size != value["bytes"]
        or value["mode"] != f"{mode:04o}"
        or sha256(path) != value["sha256"]
    ):
        raise ValueError(f"Artifact identity drift: {value['path']}")
    return path


def require_inventory(root_value: str, rows: list[dict[str, Any]], mode: int) -> Path:
    root = _resolve(root_value)
    metadata = os.lstat(root)
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != mode:
        raise ValueError("Asset root drift")
    if {path.name for path in root.iterdir() if path.is_file()} != {row["name"] for row in rows}:
        raise ValueError("Asset inventory name drift")
    for row in rows:
        require_record(
            {
                "path": str((root / row["name"]).relative_to(PROJECT_ROOT)),
                "bytes": row["bytes"], "sha256": row["sha256"], "mode": row["mode"],
            },
            int(row["mode"], 8),
        )
    return root


def environment_identity() -> dict[str, Any]:
    distributions = {
        "numpy": "numpy", "torch": "torch", "transformers": "transformers",
        "tokenizers": "tokenizers", "mlx": "mlx", "mlx_lm": "mlx-lm",
        "safetensors": "safetensors",
    }
    return {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "packages": {name: importlib.metadata.version(dist) for name, dist in distributions.items()},
        "offline_environment": {
            key: os.environ.get(key)
            for key in (
                "PYTHONNOUSERSITE", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE",
                "TOKENIZERS_PARALLELISM", "OMP_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
            )
        },
    }


def load_config(path: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    path = path.resolve()
    if path != DEFAULT_CONFIG.resolve():
        raise ValueError("EXP-067 requires frozen config path")
    config = json.loads(path.read_text(encoding="utf-8"))
    if (
        config.get("schema_version") != CONFIG_SCHEMA
        or config.get("experiment_id") != EXPERIMENT_ID
        or config.get("run_id") != RUN_ID
        or config.get("environment") != environment_identity()
        or config.get("claim_boundary") != CLAIM_BOUNDARY
        or config.get("outputs") != {
            "public_dir": str(PUBLIC_REL), "private_dir": str(PRIVATE_REL)
        }
        or config.get("benchmark", {}).get("latin_order")
        != [[rep, mode] for rep, mode in LATIN_ORDER]
    ):
        raise ValueError("EXP-067 config/environment drift")
    sources: dict[str, Path] = {"config": path}
    for section in ("prerequisite", "implementation"):
        for name, value in config[section].items():
            sources[name] = require_record(value, 0o644)
    if json.loads(sources["exp066_completion"].read_text())["status"] != "Complete":
        raise ValueError("EXP-067 EXP-066 completion drift")
    if json.loads(sources["exp066_verification"].read_text())["status"] != "Passed":
        raise ValueError("EXP-067 EXP-066 verification drift")
    assets = config["runtime_assets"]
    for name, mode in (
        ("bundle_manifest", 0o600), ("bundle_parameters", 0o600),
        ("projection", 0o600), ("m3_adapter", 0o600), ("m3_head", 0o600),
        ("m3_prompt", 0o644), ("m3_base_manifest", 0o644),
    ):
        sources[name] = require_record(assets[name], mode)
    sources["m1_checkpoint_root"] = require_inventory(
        assets["m1_checkpoint_root"], assets["m1_checkpoint_files"], 0o755
    )
    sources["m3_base_root"] = require_inventory(
        assets["m3_base_root"], assets["m3_base_files"], 0o755
    )
    return config, sources


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    output: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in PUBLIC_SENSITIVE_KEYS:
                output.append(path)
            output.extend(public_sensitive_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            output.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    return output


def _create(path: Path, payload: bytes, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, mode)
    with os.fdopen(descriptor, "wb") as target:
        target.write(payload)
        target.flush()
        os.fsync(target.fileno())
    os.chmod(path, mode)


def acquire_lock(config: dict[str, Any]):
    path = _resolve(config["heavy_workload_lock"])
    descriptor = path.open("r+")
    try:
        fcntl.flock(descriptor.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        descriptor.close()
        raise RuntimeError("EXP-067 heavy workload lock busy")
    return descriptor


def _assert_outputs_absent(config: dict[str, Any]) -> tuple[Path, Path]:
    public = _resolve(config["outputs"]["public_dir"])
    private = _resolve(config["outputs"]["private_dir"])
    for path in (public, private):
        if os.path.lexists(path):
            raise FileExistsError(f"EXP-067 output exists: {path.relative_to(PROJECT_ROOT)}")
    return public, private


def worker_command(config: dict[str, Any], *arguments: str) -> list[str]:
    return [
        config["environment"]["python_executable"],
        str(PROJECT_ROOT / config["implementation"]["worker"]["path"]),
        "--config", str(DEFAULT_CONFIG),
        *arguments,
    ]


def run_subprocess(command: list[str], timeout: float) -> tuple[int, dict[str, Any], str]:
    process = subprocess.Popen(
        command, cwd=PROJECT_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.terminate()
        stdout, stderr = process.communicate(timeout=30)
        raise RuntimeError("EXP-067 worker timeout")
    if process.returncode != 0:
        raise RuntimeError(f"EXP-067 worker nonzero exit: {process.returncode}")
    lines = [line for line in stdout.splitlines() if line.strip().startswith("{")]
    if not lines:
        raise RuntimeError("EXP-067 worker summary missing")
    value = json.loads(lines[-1])
    return process.pid, value, stderr[-2000:]


def load_groups(config: dict[str, Any]) -> np.ndarray:
    path = PROJECT_ROOT / config["runtime_assets"]["projection"]["path"]
    groups: list[int] = []
    with path.open("r", encoding="utf-8") as source:
        for expected, line in enumerate(source):
            row = json.loads(line)
            if row["ordinal"] != expected:
                raise ValueError("EXP-067 group order drift")
            groups.append(int(row["opaque_component_group"]))
    if len(groups) != 720:
        raise ValueError("EXP-067 group row count drift")
    return np.asarray(groups, dtype=np.int16)


def load_worker(private_dir: Path, repetition: int, mode: str) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    directory = private_dir / "workers" / f"rep-{repetition}-{mode}"
    manifest = json.loads((directory / "worker-manifest.json").read_text(encoding="utf-8"))
    with np.load(directory / "timing-output.npz", allow_pickle=False) as archive:
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    return arrays, manifest


def hierarchical_bootstrap(
    b1: np.ndarray,
    b2: np.ndarray,
    groups: np.ndarray,
    repetitions: int,
    seed: int,
) -> dict[str, Any]:
    unique = np.unique(groups)
    indices = {int(group): np.flatnonzero(groups == group) for group in unique}
    rng = np.random.default_rng(seed)
    reductions = np.empty(repetitions, dtype=np.float64)
    p95_differences = np.empty(repetitions, dtype=np.float64)
    for draw in range(repetitions):
        sampled_repetitions = rng.integers(0, 3, size=3)
        b1_parts: list[np.ndarray] = []
        b2_parts: list[np.ndarray] = []
        for rep in sampled_repetitions:
            sampled_groups = rng.choice(unique, size=len(unique), replace=True)
            sampled_indices = np.concatenate([indices[int(group)] for group in sampled_groups])
            b1_parts.append(b1[int(rep), sampled_indices])
            b2_parts.append(b2[int(rep), sampled_indices])
        left = np.concatenate(b1_parts)
        right = np.concatenate(b2_parts)
        reductions[draw] = 1.0 - float(np.mean(right)) / float(np.mean(left))
        p95_differences[draw] = float(np.quantile(right, 0.95, method="linear")) - float(
            np.quantile(left, 0.95, method="linear")
        )
    return {
        "repetitions": repetitions,
        "seed": seed,
        "rng": "numpy.default_rng_PCG64",
        "quantile_method": "linear",
        "reduction_ci95": [
            float(np.quantile(reductions, 0.025, method="linear")),
            float(np.quantile(reductions, 0.975, method="linear")),
        ],
        "p95_difference_ns_ci95": [
            float(np.quantile(p95_differences, 0.025, method="linear")),
            float(np.quantile(p95_differences, 0.975, method="linear")),
        ],
    }


def summarize(config: dict[str, Any], private_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    arrays: dict[str, list[np.ndarray]] = {mode: [] for mode in ("B0", "B1", "B2")}
    manifests: dict[str, list[dict[str, Any]]] = {mode: [] for mode in ("B0", "B1", "B2")}
    final: dict[tuple[int, str], np.ndarray] = {}
    route_masks: list[np.ndarray] = []
    for rep in (1, 2, 3):
        for mode in ("B0", "B1", "B2"):
            value, manifest = load_worker(private_dir, rep, mode)
            if value["ordinal"].tolist() != list(range(720)):
                raise ValueError("EXP-067 worker ordinal drift")
            arrays[mode].append(value["total_ns"].astype(np.float64))
            manifests[mode].append(manifest)
            final[(rep, mode)] = value["final_prediction"]
            if mode == "B2":
                route_masks.append(value["route_mask"])
                route = value["route_mask"].astype(bool)
                if not np.array_equal(value["selected_path"], value["route_mask"]):
                    raise ValueError("EXP-067 B2 selected path drift")
                if not np.array_equal(value["final_prediction"][~route], final[(rep, "B0")][~route]):
                    raise ValueError("EXP-067 B2 M1 replacement drift")
                if not np.array_equal(value["final_prediction"][route], final[(rep, "B1")][route]):
                    raise ValueError("EXP-067 B2 M3 replacement drift")
    if not all(np.array_equal(route_masks[0], mask) for mask in route_masks[1:]):
        raise ValueError("EXP-067 B2 route mask nondeterminism")
    matrix = {mode: np.stack(arrays[mode]) for mode in arrays}
    groups = load_groups(config)
    bootstrap = hierarchical_bootstrap(
        matrix["B1"], matrix["B2"], groups,
        int(config["bootstrap"]["repetitions"]), int(config["bootstrap"]["seed"]),
    )
    mean_b1 = float(np.mean(matrix["B1"]))
    mean_b2 = float(np.mean(matrix["B2"]))
    reduction = 1.0 - mean_b2 / mean_b1
    p95_difference = float(np.quantile(matrix["B2"], 0.95, method="linear")) - float(
        np.quantile(matrix["B1"], 0.95, method="linear")
    )
    call_rate = float(np.mean(route_masks[0]))
    memory_pass = all(manifest["memory_gate"]["passed"] for mode in manifests for manifest in manifests[mode])
    lower = bootstrap["reduction_ci95"][0]
    if lower >= 0.50:
        level = "Strong"
    elif lower >= 0.10:
        level = "Moderate"
    else:
        level = "Insufficient"
    positive_gate = bool(
        level in ("Strong", "Moderate")
        and bootstrap["p95_difference_ns_ci95"][1] <= 0
        and call_rate <= 0.20
        and memory_pass
    )

    def mode_summary(mode: str) -> dict[str, Any]:
        values = matrix[mode]
        return {
            "mean_ms": float(np.mean(values) / 1e6),
            "median_ms": float(np.median(values) / 1e6),
            "p95_ms": float(np.quantile(values, 0.95, method="linear") / 1e6),
            "per_repetition": [
                {
                    "repetition": rep + 1,
                    "mean_ms": float(np.mean(values[rep]) / 1e6),
                    "median_ms": float(np.median(values[rep]) / 1e6),
                    "p95_ms": float(np.quantile(values[rep], 0.95, method="linear") / 1e6),
                }
                for rep in range(3)
            ],
        }

    worker_resources = {
        mode: [
            {
                "repetition": manifest["repetition"],
                "elapsed_seconds": manifest["elapsed_seconds"],
                "memory_gate": manifest["memory_gate"],
            }
            for manifest in manifests[mode]
        ]
        for mode in manifests
    }
    aggregate = {
        "schema_version": "exp-067-benchmark-aggregate-private-v1",
        "experiment_id": EXPERIMENT_ID,
        "rows_per_mode_repetition": 720,
        "mode_summaries": {mode: mode_summary(mode) for mode in ("B0", "B1", "B2")},
        "primary": {
            "mean_reduction": reduction,
            "p95_difference_ns": p95_difference,
            "actual_m3_call_rate": call_rate,
            "efficiency_level": level,
            "positive_efficiency_gate": positive_gate,
        },
        "bootstrap": bootstrap,
        "route_masks_exact_across_repetitions": True,
        "fallback_count": 0,
        "error_count": 0,
        "memory_gates_all_passed": memory_pass,
        "worker_resources": worker_resources,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    public = {
        "schema_version": "exp-067-benchmark-summary-v1",
        "experiment_id": EXPERIMENT_ID,
        "status": "CompletedAwaitingVerification",
        "mode_summaries": aggregate["mode_summaries"],
        "primary": aggregate["primary"],
        "bootstrap": aggregate["bootstrap"],
        "route_masks_exact_across_repetitions": True,
        "fallback_count": 0,
        "error_count": 0,
        "memory_gates_all_passed": memory_pass,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return aggregate, public


def _freeze(public_dir: Path, sources: dict[str, Path]) -> dict[str, Any]:
    frozen = public_dir / "frozen-sources"
    frozen.mkdir(mode=0o755)
    output: dict[str, Any] = {}
    for name in ("config", "protocol", "runtime", "worker", "runner", "verifier", "tests"):
        source = sources[name]
        target = frozen / ("config.json" if name == "config" else source.name)
        _create(target, source.read_bytes(), 0o644)
        output[name] = artifact(target)
    return output


def preflight(config_path: Path) -> dict[str, Any]:
    config, _ = load_config(config_path)
    _assert_outputs_absent(config)
    lock = acquire_lock(config)
    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    lock.close()
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": "Ready",
        "workers": 9,
        "latin_order": [[rep, mode] for rep, mode in LATIN_ORDER],
        "public_output_absent": True,
        "private_output_absent": True,
        "test_access": False,
    }


def execute(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    started_at = utc_now()
    started = time.perf_counter()
    config, sources = load_config(config_path)
    public_dir, private_dir = _assert_outputs_absent(config)
    lock = acquire_lock(config)
    try:
        _, smoke, _ = run_subprocess(
            worker_command(config, "--resource-smoke"),
            float(config["benchmark"]["worker_timeout_seconds"]),
        )
        if smoke.get("status") != "Passed":
            raise RuntimeError("EXP-067 resource smoke failed")
        public_dir.mkdir(mode=0o755)
        os.chmod(public_dir, 0o755)
        private_dir.mkdir(mode=0o700)
        os.chmod(private_dir, 0o700)
        (private_dir / "workers").mkdir(mode=0o700)
        implementation = _freeze(public_dir, sources)
        claim = {
            "schema_version": "exp-067-run-claim-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "status": "Claimed",
            "claimed_at_utc": started_at,
            "config": artifact(config_path),
            "resource_smoke": smoke,
            "workers": 9,
            "one_shot": True,
        }
        _create(public_dir / "run-claim.json", canonical_json(claim), 0o644)
        worker_records: list[dict[str, Any]] = []
        seen_pids: set[int] = set()
        try:
            for sequence, (rep, mode) in enumerate(LATIN_ORDER, start=1):
                output = private_dir / "workers" / f"rep-{rep}-{mode}"
                pid, value, _ = run_subprocess(
                    worker_command(
                        config,
                        "--mode", mode,
                        "--repetition", str(rep),
                        "--output-dir", str(output),
                    ),
                    float(config["benchmark"]["worker_timeout_seconds"]),
                )
                if pid in seen_pids or value.get("status") != "Completed":
                    raise RuntimeError("EXP-067 fresh worker identity/status drift")
                seen_pids.add(pid)
                worker_records.append(
                    {
                        "sequence": sequence,
                        "repetition": rep,
                        "mode": mode,
                        "pid": pid,
                        "summary": value,
                    }
                )
                print(json.dumps({"worker_complete": value}, sort_keys=True), flush=True)
                if value.get("memory_gate_passed") is not True:
                    raise RuntimeError("EXP-067 worker memory gate failed")
            aggregate, public_summary = summarize(config, private_dir)
            aggregate["worker_execution"] = worker_records
            aggregate_path = private_dir / "benchmark-aggregate.json"
            _create(aggregate_path, canonical_json(aggregate), 0o600)
            summary_path = public_dir / "benchmark-summary.json"
            _create(summary_path, canonical_json(public_summary), 0o644)
            run = {
                "schema_version": "exp-067-run-v1",
                "experiment_id": EXPERIMENT_ID,
                "run_id": RUN_ID,
                "tier": "Major",
                "rq_id": "RQ-S3",
                "status": "CompletedAwaitingVerification",
                "started_at_utc": started_at,
                "completed_at_utc": utc_now(),
                "elapsed_seconds": time.perf_counter() - started,
                "environment": config["environment"],
                "implementation": implementation,
                "prerequisite": config["prerequisite"],
                "resource_smoke": smoke,
                "worker_order": [[rep, mode] for rep, mode in LATIN_ORDER],
                "worker_count": 9,
                "unique_worker_count": len(seen_pids),
                "aggregate": public_summary,
                "private_aggregate": {
                    "logical_name": aggregate_path.name,
                    **artifact(aggregate_path, include_path=False),
                },
                "public_summary": artifact(summary_path),
                "access_attestation": {
                    "label_free_projection_accessed": True,
                    "original_validation_accessed": False,
                    "test_accessed": False,
                    "network_accessed": False,
                    "fallback_count": 0,
                },
                "claim_boundary": CLAIM_BOUNDARY,
            }
            if public_sensitive_paths(run):
                raise RuntimeError("EXP-067 public privacy drift")
            _create(public_dir / "run.json", canonical_json(run), 0o644)
            _create(
                public_dir / "stdout.log",
                (
                    f"{EXPERIMENT_ID} {RUN_ID}\nstatus=CompletedAwaitingVerification\n"
                    "workers=9\nrows_per_worker=720\nfallback_count=0\ntest_access=false\n"
                ).encode("utf-8"),
                0o644,
            )
            return run
        except Exception as error:
            failure = {
                "schema_version": "exp-067-private-failure-v1",
                "experiment_id": EXPERIMENT_ID,
                "run_id": RUN_ID,
                "status": "Failed",
                "failed_at_utc": utc_now(),
                "error_type": type(error).__name__,
                "error": str(error),
                "completed_workers": worker_records,
            }
            if not os.path.lexists(private_dir / "failure.json"):
                _create(private_dir / "failure.json", canonical_json(failure), 0o600)
            public_failure = {
                "schema_version": "exp-067-run-v1",
                "experiment_id": EXPERIMENT_ID,
                "run_id": RUN_ID,
                "status": "Failed",
                "failed_at_utc": utc_now(),
                "error_type": type(error).__name__,
                "completed_worker_count": len(worker_records),
                "fallback_count": 0,
                "test_accessed": False,
                "claim_boundary": CLAIM_BOUNDARY,
            }
            if not os.path.lexists(public_dir / "run.json"):
                _create(public_dir / "run.json", canonical_json(public_failure), 0o644)
            raise
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = preflight(args.config) if args.check else execute(args.config)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
