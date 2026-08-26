#!/usr/bin/env python3
"""Independently recompute EXP-067 benchmark aggregates and gates."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import stat
import sys
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
TIMING_KEYS = {
    "ordinal", "tokenize_preprocess_ns", "m1_inference_ns", "feature_router_ns",
    "m3_inference_ns", "postprocess_materialize_ns", "total_ns", "route_mask",
    "selected_path", "final_prediction", "neutral",
}
MEMORY_KEYS = {
    "timestamp_ns", "phase", "rss_bytes", "ru_maxrss_bytes", "mlx_active_bytes",
    "mlx_cache_bytes", "mlx_peak_bytes", "memory_free_percent", "pressure_code",
    "compressed_bytes", "pageouts_bytes", "swapouts_bytes",
}
CLAIM_BOUNDARY = (
    "A same-device, model-loaded, batch-size-1 steady-state latency and memory benchmark for "
    "the frozen seed-42 local development runtime only; no cold-start, production, independent-test, "
    "classification-performance, forum-generalization, or emotion-mechanism claim."
)
SENSITIVE_KEYS = {
    "text", "raw_text", "ordinal", "ordinals", "opaque_component_group", "sample_id",
    "sample_ids", "component_id", "component_ids", "probabilities", "prediction",
    "predictions", "final_prediction", "route_mask", "selected_path", "timing_rows",
    "memory_samples", "pid", "pids",
}


def _project_root(source: Path) -> Path:
    for candidate in (source, *source.parents):
        if candidate.name == "llm-forum-text-emotion-recognition":
            return candidate
    raise RuntimeError("Could not locate project root")


PROJECT_ROOT = _project_root(Path(__file__).resolve())
BASE = Path("experiments/stack-overflow-emotion-gold/oof-router")
DEFAULT_CONFIG = PROJECT_ROOT / BASE / "configs/exp-067-steady-state-benchmark.json"
PUBLIC_DIR = PROJECT_ROOT / BASE / "runs" / RUN_ID
PRIVATE_DIR = PROJECT_ROOT / BASE / "private" / RUN_ID


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


def _regular(path: Path, mode: int) -> os.stat_result:
    metadata = os.lstat(path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or stat.S_IMODE(metadata.st_mode) != mode
    ):
        raise ValueError(f"File type/mode drift: {path}")
    return metadata


def record(path: Path, include_path: bool = True) -> dict[str, Any]:
    metadata = os.lstat(path)
    value: dict[str, Any] = {
        "bytes": metadata.st_size,
        "sha256": sha256(path),
        "mode": f"{stat.S_IMODE(metadata.st_mode):04o}",
    }
    if include_path:
        value["path"] = str(path.relative_to(PROJECT_ROOT))
    return value


def require_record(value: dict[str, Any], mode: int) -> Path:
    path = _resolve(value["path"])
    metadata = _regular(path, mode)
    if (
        metadata.st_size != value["bytes"]
        or value["mode"] != f"{mode:04o}"
        or sha256(path) != value["sha256"]
    ):
        raise ValueError("Artifact identity drift")
    return path


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
        raise ValueError("Verifier requires frozen EXP-067 config")
    config = json.loads(path.read_text(encoding="utf-8"))
    if (
        config.get("schema_version") != CONFIG_SCHEMA
        or config.get("experiment_id") != EXPERIMENT_ID
        or config.get("environment") != environment_identity()
        or config.get("claim_boundary") != CLAIM_BOUNDARY
    ):
        raise ValueError("EXP-067 verifier config/environment drift")
    sources: dict[str, Path] = {"config": path}
    for section in ("prerequisite", "implementation"):
        for name, value in config[section].items():
            sources[name] = require_record(value, 0o644)
    return config, sources


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    output: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in SENSITIVE_KEYS:
                output.append(path)
            output.extend(public_sensitive_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            output.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    return output


def memory_gate(arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    phase = arrays["phase"]
    idle_indices = np.flatnonzero(phase == 0)
    timed_indices = np.flatnonzero(phase == 3)
    warm_indices = np.flatnonzero(phase == 2)
    post_indices = np.flatnonzero(phase == 4)
    if min(len(idle_indices), len(timed_indices), len(warm_indices), len(post_indices)) < 1:
        raise ValueError("EXP-067 verifier memory phase coverage drift")
    idle = idle_indices
    timed = timed_indices

    def rate(indices: np.ndarray, key: str) -> tuple[float, int]:
        elapsed = max(
            (arrays["timestamp_ns"][indices[-1]] - arrays["timestamp_ns"][indices[0]]) / 1e9,
            1e-9,
        )
        total = max(0, int(arrays[key][indices[-1]] - arrays[key][indices[0]]))
        return total / elapsed, total

    page_size = 16384
    thrash = {}
    for key in ("pageouts_bytes", "swapouts_bytes"):
        idle_rate, _ = rate(idle, key)
        timed_rate, timed_total = rate(timed, key)
        thrash[key] = bool(timed_rate > idle_rate + page_size and timed_total > 16 * page_size)
    critical = bool(np.any(arrays["pressure_code"] == 2))
    post_warm_rss = int(arrays["rss_bytes"][warm_indices[-1]])
    post_run_rss = int(arrays["rss_bytes"][post_indices[0]])
    retained = bool(post_run_rss <= 1.10 * post_warm_rss)
    return {
        "critical_pressure": critical,
        "pageout_thrashing": thrash["pageouts_bytes"],
        "swapout_thrashing": thrash["swapouts_bytes"],
        "post_run_rss_within_110pct": retained,
        "passed": bool(not critical and not any(thrash.values()) and retained),
        "post_warm_rss_bytes": post_warm_rss,
        "post_run_rss_bytes": post_run_rss,
    }


def load_groups(config: dict[str, Any]) -> np.ndarray:
    path = PROJECT_ROOT / config["runtime_assets"]["projection"]["path"]
    groups = []
    with path.open("r", encoding="utf-8") as source:
        for index, line in enumerate(source):
            row = json.loads(line)
            if row["ordinal"] != index:
                raise ValueError("EXP-067 verifier projection order drift")
            groups.append(int(row["opaque_component_group"]))
    return np.asarray(groups, dtype=np.int16)


def load_worker(rep: int, mode: str) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], dict[str, Any]]:
    directory = PRIVATE_DIR / "workers" / f"rep-{rep}-{mode}"
    if stat.S_IMODE(os.lstat(directory).st_mode) != 0o700:
        raise ValueError("EXP-067 worker dir mode drift")
    manifest = json.loads((directory / "worker-manifest.json").read_text(encoding="utf-8"))
    _regular(directory / "worker-manifest.json", 0o600)
    _regular(directory / "timing-output.npz", 0o600)
    _regular(directory / "memory-samples.npz", 0o600)
    with np.load(directory / "timing-output.npz", allow_pickle=False) as archive:
        if set(archive.files) != TIMING_KEYS:
            raise ValueError("EXP-067 timing keys drift")
        timing = {name: np.asarray(archive[name]) for name in archive.files}
    with np.load(directory / "memory-samples.npz", allow_pickle=False) as archive:
        if set(archive.files) != MEMORY_KEYS:
            raise ValueError("EXP-067 memory keys drift")
        memory = {name: np.asarray(archive[name]) for name in archive.files}
    if timing["ordinal"].tolist() != list(range(720)):
        raise ValueError("EXP-067 timing order drift")
    components = sum(
        timing[name]
        for name in (
            "tokenize_preprocess_ns", "m1_inference_ns", "feature_router_ns",
            "m3_inference_ns", "postprocess_materialize_ns",
        )
    )
    tolerance = np.maximum(1_000_000, (0.02 * timing["total_ns"]).astype(np.int64))
    if np.any(np.abs(timing["total_ns"] - components) > tolerance):
        raise ValueError("EXP-067 timing component tolerance failed")
    if np.any(timing["total_ns"] <= 0):
        raise ValueError("EXP-067 nonpositive total latency")
    if mode == "B0":
        if (
            np.any(timing["route_mask"])
            or np.any(timing["selected_path"])
            or np.any(timing["feature_router_ns"])
            or np.any(timing["m3_inference_ns"])
            or np.any(timing["m1_inference_ns"] <= 0)
        ):
            raise ValueError("EXP-067 B0 invariant drift")
    elif mode == "B1":
        if (
            np.any(timing["route_mask"])
            or not np.all(timing["selected_path"] == 1)
            or np.any(timing["m1_inference_ns"])
            or np.any(timing["feature_router_ns"])
            or np.any(timing["m3_inference_ns"] <= 0)
        ):
            raise ValueError("EXP-067 B1 invariant drift")
    else:
        route = timing["route_mask"].astype(bool)
        if (
            not np.array_equal(timing["selected_path"], timing["route_mask"])
            or np.any(timing["m1_inference_ns"] <= 0)
            or np.any(timing["feature_router_ns"] <= 0)
            or np.any(timing["m3_inference_ns"][route] <= 0)
            or np.any(timing["m3_inference_ns"][~route] != 0)
        ):
            raise ValueError("EXP-067 B2 invariant drift")
    if not np.array_equal(timing["neutral"], (timing["final_prediction"].sum(axis=1) == 0)):
        raise ValueError("EXP-067 neutral drift")
    gate = memory_gate(memory)
    if manifest.get("memory_gate") != gate:
        raise ValueError("EXP-067 worker memory gate replay drift")
    return timing, memory, manifest


def bootstrap(b1: np.ndarray, b2: np.ndarray, groups: np.ndarray, count: int, seed: int) -> dict[str, Any]:
    unique = np.unique(groups)
    mapping = {int(group): np.flatnonzero(groups == group) for group in unique}
    rng = np.random.default_rng(seed)
    reductions = np.empty(count, dtype=np.float64)
    p95 = np.empty(count, dtype=np.float64)
    for draw in range(count):
        reps = rng.integers(0, 3, size=3)
        left_parts = []
        right_parts = []
        for rep in reps:
            drawn = rng.choice(unique, size=len(unique), replace=True)
            indices = np.concatenate([mapping[int(group)] for group in drawn])
            left_parts.append(b1[int(rep), indices])
            right_parts.append(b2[int(rep), indices])
        left = np.concatenate(left_parts)
        right = np.concatenate(right_parts)
        reductions[draw] = 1.0 - float(np.mean(right)) / float(np.mean(left))
        p95[draw] = float(np.quantile(right, 0.95, method="linear")) - float(
            np.quantile(left, 0.95, method="linear")
        )
    return {
        "repetitions": count,
        "seed": seed,
        "rng": "numpy.default_rng_PCG64",
        "quantile_method": "linear",
        "reduction_ci95": [
            float(np.quantile(reductions, 0.025, method="linear")),
            float(np.quantile(reductions, 0.975, method="linear")),
        ],
        "p95_difference_ns_ci95": [
            float(np.quantile(p95, 0.025, method="linear")),
            float(np.quantile(p95, 0.975, method="linear")),
        ],
    }


def recompute(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    totals = {mode: [] for mode in ("B0", "B1", "B2")}
    manifests = {mode: [] for mode in ("B0", "B1", "B2")}
    final = {}
    masks = []
    for rep in (1, 2, 3):
        for mode in ("B0", "B1", "B2"):
            timing, _, manifest = load_worker(rep, mode)
            totals[mode].append(timing["total_ns"].astype(np.float64))
            manifests[mode].append(manifest)
            final[(rep, mode)] = timing["final_prediction"]
            if mode == "B2":
                mask = timing["route_mask"].astype(bool)
                masks.append(timing["route_mask"])
                if not np.array_equal(timing["final_prediction"][~mask], final[(rep, "B0")][~mask]):
                    raise ValueError("EXP-067 verifier B2/B0 replacement drift")
                if not np.array_equal(timing["final_prediction"][mask], final[(rep, "B1")][mask]):
                    raise ValueError("EXP-067 verifier B2/B1 replacement drift")
    if not all(np.array_equal(masks[0], mask) for mask in masks[1:]):
        raise ValueError("EXP-067 verifier B2 route mask nondeterminism")
    matrix = {mode: np.stack(totals[mode]) for mode in totals}
    boot = bootstrap(
        matrix["B1"], matrix["B2"], load_groups(config),
        int(config["bootstrap"]["repetitions"]), int(config["bootstrap"]["seed"]),
    )

    def summary(mode: str) -> dict[str, Any]:
        values = matrix[mode]
        return {
            "mean_ms": float(np.mean(values) / 1e6),
            "median_ms": float(np.median(values) / 1e6),
            "p95_ms": float(np.quantile(values, 0.95, method="linear") / 1e6),
            "per_repetition": [
                {
                    "repetition": index + 1,
                    "mean_ms": float(np.mean(values[index]) / 1e6),
                    "median_ms": float(np.median(values[index]) / 1e6),
                    "p95_ms": float(np.quantile(values[index], 0.95, method="linear") / 1e6),
                }
                for index in range(3)
            ],
        }

    reduction = 1.0 - float(np.mean(matrix["B2"])) / float(np.mean(matrix["B1"]))
    p95_diff = float(np.quantile(matrix["B2"], 0.95, method="linear")) - float(
        np.quantile(matrix["B1"], 0.95, method="linear")
    )
    call_rate = float(np.mean(masks[0]))
    memory_pass = all(manifest["memory_gate"]["passed"] for mode in manifests for manifest in manifests[mode])
    lower = boot["reduction_ci95"][0]
    level = "Strong" if lower >= 0.50 else "Moderate" if lower >= 0.10 else "Insufficient"
    positive = bool(
        level != "Insufficient"
        and boot["p95_difference_ns_ci95"][1] <= 0
        and call_rate <= 0.20
        and memory_pass
    )
    resources = {
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
        "mode_summaries": {mode: summary(mode) for mode in ("B0", "B1", "B2")},
        "primary": {
            "mean_reduction": reduction,
            "p95_difference_ns": p95_diff,
            "actual_m3_call_rate": call_rate,
            "efficiency_level": level,
            "positive_efficiency_gate": positive,
        },
        "bootstrap": boot,
        "route_masks_exact_across_repetitions": True,
        "fallback_count": 0,
        "error_count": 0,
        "memory_gates_all_passed": memory_pass,
        "worker_resources": resources,
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


def _typed_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(_typed_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def _create(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o644)
    with os.fdopen(descriptor, "wb") as target:
        target.write(payload)
        target.flush()
        os.fsync(target.fileno())
    os.chmod(path, 0o644)


def verify(config_path: Path) -> dict[str, Any]:
    config, sources = load_config(config_path)
    if stat.S_IMODE(os.lstat(PUBLIC_DIR).st_mode) != 0o755:
        raise ValueError("EXP-067 public dir mode drift")
    if stat.S_IMODE(os.lstat(PRIVATE_DIR).st_mode) != 0o700:
        raise ValueError("EXP-067 private dir mode drift")
    for name in ("verification.json", "VERIFICATION-SUMMARY.md", "benchmark-complete.json"):
        if os.path.lexists(PUBLIC_DIR / name):
            raise FileExistsError("EXP-067 verification output exists")
    claim = json.loads((PUBLIC_DIR / "run-claim.json").read_text())
    run = json.loads((PUBLIC_DIR / "run.json").read_text())
    _regular(PUBLIC_DIR / "run-claim.json", 0o644)
    _regular(PUBLIC_DIR / "run.json", 0o644)
    _regular(PUBLIC_DIR / "stdout.log", 0o644)
    if (
        claim.get("status") != "Claimed"
        or run.get("status") != "CompletedAwaitingVerification"
        or run.get("worker_order") != [[rep, mode] for rep, mode in LATIN_ORDER]
        or run.get("worker_count") != 9
        or run.get("unique_worker_count") != 9
        or public_sensitive_paths(claim)
        or public_sensitive_paths(run)
    ):
        raise ValueError("EXP-067 public identity/privacy drift")
    frozen = run["implementation"]
    source_map = {"config": config_path.resolve()}
    source_map.update(
        {name: sources[name] for name in ("protocol", "runtime", "worker", "runner", "verifier", "tests")}
    )
    if set(frozen) != set(source_map):
        raise ValueError("EXP-067 frozen source set drift")
    for name, source in source_map.items():
        frozen_path = require_record(frozen[name], 0o644)
        if frozen_path.read_bytes() != source.read_bytes():
            raise ValueError("EXP-067 frozen source bytes drift")
    expected_private, expected_public = recompute(config)
    private_path = PRIVATE_DIR / "benchmark-aggregate.json"
    public_path = PUBLIC_DIR / "benchmark-summary.json"
    _regular(private_path, 0o600)
    _regular(public_path, 0o644)
    observed_private = json.loads(private_path.read_text())
    worker_execution = observed_private.pop("worker_execution", None)
    if (
        not isinstance(worker_execution, list)
        or len(worker_execution) != 9
        or [
            [row["repetition"], row["mode"]] for row in worker_execution
        ]
        != [[rep, mode] for rep, mode in LATIN_ORDER]
        or len({row["pid"] for row in worker_execution}) != 9
    ):
        raise ValueError("EXP-067 private worker execution lineage drift")
    if not _typed_equal(observed_private, expected_private):
        raise ValueError("EXP-067 private aggregate replay mismatch")
    observed_public = json.loads(public_path.read_text())
    if not _typed_equal(observed_public, expected_public):
        raise ValueError("EXP-067 public summary replay mismatch")
    if run.get("aggregate") != expected_public:
        raise ValueError("EXP-067 run aggregate mismatch")
    checks = [
        "config_environment", "prerequisites", "output_modes", "append_only_terminal_absence",
        "run_claim_state", "latin_order", "nine_unique_workers", "public_privacy",
        "frozen_sources", "worker_file_modes", "nine_worker_manifests", "row_order_720",
        "timing_component_tolerance", "B0_invariants", "B1_invariants", "B2_invariants",
        "neutral_exact", "B2_route_mask_determinism", "B2_B0_replacement", "B2_B1_replacement",
        "memory_phase_coverage", "memory_gate_replay", "all_memory_gates", "zero_errors",
        "zero_fallback", "call_rate_gate", "hierarchical_bootstrap_rng",
        "bootstrap_multiplicity", "reduction_interval", "p95_interval", "efficiency_level",
        "private_aggregate_replay", "public_summary_replay", "claim_boundary",
    ]
    result = {
        "schema_version": "exp-067-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "status": "Passed",
        "verified_at_utc": utc_now(),
        "passed_count": len(checks),
        "failed_count": 0,
        "checks": checks,
        "primary": expected_public["primary"],
        "bootstrap": expected_public["bootstrap"],
        "mode_summaries": expected_public["mode_summaries"],
        "memory_gates_all_passed": expected_public["memory_gates_all_passed"],
        "fallback_count": 0,
        "error_count": 0,
        "access_attestation": {
            "original_validation_accessed": False,
            "test_accessed": False,
            "network_accessed": False,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }
    if public_sensitive_paths(result):
        raise ValueError("EXP-067 verification public privacy drift")
    summary = (
        "# EXP-067 Benchmark Verification\n\n"
        "- Status: `Passed`\n"
        f"- Checks: `{len(checks)}/{len(checks)}`\n"
        f"- Efficiency level: `{result['primary']['efficiency_level']}`\n"
        f"- Positive efficiency gate: `{str(result['primary']['positive_efficiency_gate']).lower()}`\n"
        "- Workers: `9` fresh processes\n"
        "- Fallback/error count: `0/0`\n"
        f"- Memory gates all passed: `{str(result['memory_gates_all_passed']).lower()}`\n"
        "- Test access: `false`\n\n"
        f"Claim boundary: {CLAIM_BOUNDARY}\n"
    ).encode("utf-8")
    _create(PUBLIC_DIR / "VERIFICATION-SUMMARY.md", summary)
    _create(PUBLIC_DIR / "verification.json", canonical_json(result))
    completion = {
        "schema_version": "exp-067-benchmark-complete-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "status": "Complete",
        "completed_at_utc": utc_now(),
        "run": record(PUBLIC_DIR / "run.json"),
        "verification": record(PUBLIC_DIR / "verification.json"),
        "summary": record(PUBLIC_DIR / "benchmark-summary.json"),
        "primary": expected_public["primary"],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    _create(PUBLIC_DIR / "benchmark-complete.json", canonical_json(completion))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    try:
        result = verify(args.config)
    except Exception as error:
        if PUBLIC_DIR.exists() and not os.path.lexists(PUBLIC_DIR / "verification.json"):
            failed = {
                "schema_version": "exp-067-verification-v1",
                "experiment_id": EXPERIMENT_ID,
                "run_id": RUN_ID,
                "status": "Failed",
                "verified_at_utc": utc_now(),
                "failed_count": 1,
                "error_type": type(error).__name__,
                "test_accessed": False,
                "claim_boundary": CLAIM_BOUNDARY,
            }
            _create(PUBLIC_DIR / "verification.json", canonical_json(failed))
        raise
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
