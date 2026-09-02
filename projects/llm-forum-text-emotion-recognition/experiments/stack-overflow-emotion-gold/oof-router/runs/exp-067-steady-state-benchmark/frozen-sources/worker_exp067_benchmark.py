#!/usr/bin/env python3
"""Fresh-process worker for one EXP-067 benchmark mode/repetition."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import resource
import stat
import subprocess
import sys
import threading
import time
from typing import Any

import numpy as np

import runtime_exp066 as runtime_core


EXPERIMENT_ID = "EXP-067"
MODES = ("B0", "B1", "B2")
TIMING_SCHEMA = {
    "ordinal": {"shape": [720], "dtype": "int16"},
    "tokenize_preprocess_ns": {"shape": [720], "dtype": "int64"},
    "m1_inference_ns": {"shape": [720], "dtype": "int64"},
    "feature_router_ns": {"shape": [720], "dtype": "int64"},
    "m3_inference_ns": {"shape": [720], "dtype": "int64"},
    "postprocess_materialize_ns": {"shape": [720], "dtype": "int64"},
    "total_ns": {"shape": [720], "dtype": "int64"},
    "route_mask": {"shape": [720], "dtype": "uint8"},
    "selected_path": {"shape": [720], "dtype": "uint8"},
    "final_prediction": {"shape": [720, 6], "dtype": "uint8"},
    "neutral": {"shape": [720], "dtype": "uint8"},
}
MEMORY_FIELDS = (
    "timestamp_ns", "phase", "rss_bytes", "ru_maxrss_bytes", "mlx_active_bytes",
    "mlx_cache_bytes", "mlx_peak_bytes", "memory_free_percent", "pressure_code",
    "compressed_bytes", "pageouts_bytes", "swapouts_bytes",
)
WARMUP_TEXTS = (
    "A short synthetic warmup message.",
    "A second synthetic warmup message with different punctuation!",
)


def _project_root(source: Path) -> Path:
    for candidate in (source, *source.parents):
        if candidate.name == "llm-forum-text-emotion-recognition":
            return candidate
    raise RuntimeError("Could not locate project root")


PROJECT_ROOT = _project_root(Path(__file__).resolve())
BASE = Path("experiments/stack-overflow-emotion-gold/oof-router")
DEFAULT_CONFIG = PROJECT_ROOT / BASE / "configs/exp-067-steady-state-benchmark.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def record(path: Path) -> dict[str, Any]:
    metadata = os.lstat(path)
    return {
        "logical_name": path.name,
        "bytes": metadata.st_size,
        "sha256": sha256(path),
        "mode": f"{stat.S_IMODE(metadata.st_mode):04o}",
    }


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


def load_config(path: Path) -> dict[str, Any]:
    if path.resolve() != DEFAULT_CONFIG.resolve():
        raise ValueError("EXP-067 worker requires frozen config")
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        value.get("experiment_id") != EXPERIMENT_ID
        or value.get("environment") != environment_identity()
        or value.get("benchmark", {}).get("modes") != list(MODES)
    ):
        raise ValueError("EXP-067 worker config/environment drift")
    return value


def load_projection(config: dict[str, Any]) -> list[str]:
    path = PROJECT_ROOT / config["runtime_assets"]["projection"]["path"]
    rows: list[str] = []
    with path.open("r", encoding="utf-8") as source:
        for expected, line in enumerate(source):
            row = json.loads(line)
            if set(row) != {"ordinal", "opaque_component_group", "text"}:
                raise ValueError("EXP-067 projection schema drift")
            if row["ordinal"] != expected or type(row["text"]) is not str:
                raise ValueError("EXP-067 projection order/text drift")
            rows.append(row["text"])
    if len(rows) != 720:
        raise ValueError("EXP-067 projection row count drift")
    return rows


def _vm_sample() -> dict[str, int | float]:
    pressure = subprocess.run(
        ["/usr/bin/memory_pressure", "-Q"], capture_output=True, text=True, check=True
    ).stdout
    match = re.search(r"System-wide memory free percentage:\s*(\d+)%", pressure)
    if not match:
        raise RuntimeError("Could not parse memory_pressure -Q")
    free_percent = float(match.group(1))
    vm = subprocess.run(["/usr/bin/vm_stat"], capture_output=True, text=True, check=True).stdout
    page_match = re.search(r"page size of (\d+) bytes", vm)
    if not page_match:
        raise RuntimeError("Could not parse vm_stat page size")
    page_size = int(page_match.group(1))

    def pages(label: str) -> int:
        found = re.search(rf"^{re.escape(label)}:\s+([0-9.]+)\.?$", vm, re.MULTILINE)
        if not found:
            raise RuntimeError(f"Could not parse vm_stat {label}")
        return int(float(found.group(1)))

    rss_kib = int(
        subprocess.run(
            ["/bin/ps", "-o", "rss=", "-p", str(os.getpid())],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    )
    if free_percent >= 15:
        pressure_code = 0
    elif free_percent >= 5:
        pressure_code = 1
    else:
        pressure_code = 2
    mlx_active = mlx_cache = mlx_peak = 0
    if "mlx.core" in sys.modules:
        import mlx.core as mx

        mlx_active = int(mx.get_active_memory())
        mlx_cache = int(mx.get_cache_memory())
        mlx_peak = int(mx.get_peak_memory())
    return {
        "rss_bytes": rss_kib * 1024,
        "ru_maxrss_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "mlx_active_bytes": mlx_active,
        "mlx_cache_bytes": mlx_cache,
        "mlx_peak_bytes": mlx_peak,
        "memory_free_percent": free_percent,
        "pressure_code": pressure_code,
        "compressed_bytes": pages("Pages occupied by compressor") * page_size,
        "pageouts_bytes": pages("Pageouts") * page_size,
        "swapouts_bytes": pages("Swapouts") * page_size,
        "page_size": page_size,
    }


class MemorySampler:
    def __init__(self) -> None:
        self.phase = 0
        self.samples: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def set_phase(self, phase: int) -> None:
        with self._lock:
            self.phase = phase

    def sample(self) -> dict[str, Any]:
        try:
            value = {"timestamp_ns": time.perf_counter_ns(), "phase": self.phase, **_vm_sample()}
            with self._lock:
                self.samples.append(value)
            return value
        except Exception as error:
            with self._lock:
                self.errors.append(type(error).__name__)
            raise

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.sample()
            except Exception:
                pass
            self._stop.wait(1.0)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=3.0)


def m1_parts(backend: runtime_core.TorchM1Backend, text: str) -> tuple[int, int, np.ndarray, int]:
    start = time.perf_counter_ns()
    batch = backend.tokenizer(
        [text], add_special_tokens=True, max_length=backend.max_length, truncation=True,
        padding=True, return_attention_mask=True, return_tensors="pt",
    )
    token_length = int(batch["attention_mask"][0].sum().item())
    token_ns = time.perf_counter_ns() - start
    started = time.perf_counter_ns()
    with backend._torch.inference_mode():
        logits = backend.model(**batch).logits
        probabilities = backend._torch.sigmoid(logits).detach().cpu().numpy().astype(np.float32)
    inference_ns = time.perf_counter_ns() - started
    return token_ns, inference_ns, np.ascontiguousarray(probabilities[0]), token_length


def m3_parts(backend: runtime_core.MlxM3Backend, text: str) -> tuple[int, int, np.ndarray]:
    start = time.perf_counter_ns()
    ids = runtime_core.qwen_prompt_ids(backend.tokenizer, backend.prompt, text, backend.max_length)
    token_ns = time.perf_counter_ns() - start
    started = time.perf_counter_ns()
    logits = backend.wrapper(backend._mx.array([ids], dtype=backend._mx.int32)).astype(
        backend._mx.float32
    )
    backend._mx.eval(logits)
    values = np.asarray(logits, dtype=np.float32)
    probabilities = runtime_core.stable_sigmoid32(values)[0]
    inference_ns = time.perf_counter_ns() - started
    return token_ns, inference_ns, np.ascontiguousarray(probabilities)


def warm(mode: str, bundle: runtime_core.RouterBundle, m1: Any, m3: Any) -> None:
    for text in WARMUP_TEXTS:
        if mode in ("B0", "B2"):
            _, _, probability, length = m1_parts(m1, text)
            if mode == "B2":
                feature = runtime_core.build_features(probability, bundle.m1_threshold, len(text), length)
                bundle.route(feature)
        if mode in ("B1", "B2"):
            m3_parts(m3, text)


def timed_row(
    mode: str,
    text: str,
    bundle: runtime_core.RouterBundle,
    m1: Any,
    m3: Any,
) -> dict[str, Any]:
    total_started = time.perf_counter_ns()
    tokenize_ns = m1_ns = router_ns = m3_ns = 0
    route = False
    m1_probability = m3_probability = None
    if mode in ("B0", "B2"):
        token, m1_ns, m1_probability, token_length = m1_parts(m1, text)
        tokenize_ns += token
    if mode == "B2":
        started = time.perf_counter_ns()
        feature = runtime_core.build_features(
            m1_probability, bundle.m1_threshold, len(text), token_length
        )
        _, _, route = bundle.route(feature)
        router_ns = time.perf_counter_ns() - started
        if route:
            token, m3_ns, m3_probability = m3_parts(m3, text)
            tokenize_ns += token
    elif mode == "B1":
        token, m3_ns, m3_probability = m3_parts(m3, text)
        tokenize_ns += token
    post_started = time.perf_counter_ns()
    if mode == "B1" or (mode == "B2" and route):
        selected = m3_probability
        threshold = bundle.m3_threshold
        selected_path = 1
    else:
        selected = m1_probability
        threshold = bundle.m1_threshold
        selected_path = 0
    prediction = (selected >= threshold).astype(np.uint8)
    active_labels = [
        label for label, value in zip(runtime_core.LABEL_ORDER, prediction.tolist()) if value == 1
    ]
    materialized = {
        "prediction": prediction.astype(int).tolist(),
        "active_labels": active_labels,
        "neutral": bool(not active_labels),
        "used_path": "m3" if selected_path else "m1",
        "degraded": False,
    }
    post_ns = time.perf_counter_ns() - post_started
    total_ns = time.perf_counter_ns() - total_started
    components = tokenize_ns + m1_ns + router_ns + m3_ns + post_ns
    if abs(total_ns - components) > max(1_000_000, int(0.02 * total_ns)):
        raise RuntimeError("EXP-067 timing component coverage failed")
    return {
        "tokenize_preprocess_ns": tokenize_ns,
        "m1_inference_ns": m1_ns,
        "feature_router_ns": router_ns,
        "m3_inference_ns": m3_ns,
        "postprocess_materialize_ns": post_ns,
        "total_ns": total_ns,
        "route_mask": int(route),
        "selected_path": selected_path,
        "final_prediction": prediction,
        "neutral": int(materialized["neutral"]),
    }


def memory_arrays(samples: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    if not samples:
        raise ValueError("EXP-067 no memory samples")
    output: dict[str, np.ndarray] = {}
    for key in MEMORY_FIELDS:
        dtype = np.float64 if key == "memory_free_percent" else np.int64
        output[key] = np.asarray([row[key] for row in samples], dtype=dtype)
    return output


def memory_gate(samples: list[dict[str, Any]], post_warm: dict[str, Any], post_run: dict[str, Any]) -> dict[str, Any]:
    idle = [row for row in samples if row["phase"] == 0]
    timed = [row for row in samples if row["phase"] == 3]
    if len(idle) < 2 or len(timed) < 2:
        raise ValueError("EXP-067 insufficient baseline/timed memory samples")

    def rate(rows: list[dict[str, Any]], key: str) -> tuple[float, int]:
        elapsed = max((rows[-1]["timestamp_ns"] - rows[0]["timestamp_ns"]) / 1e9, 1e-9)
        total = max(0, int(rows[-1][key] - rows[0][key]))
        return total / elapsed, total

    thrash: dict[str, bool] = {}
    for key in ("pageouts_bytes", "swapouts_bytes"):
        idle_rate, _ = rate(idle, key)
        timed_rate, timed_total = rate(timed, key)
        page_size = int(timed[-1]["page_size"])
        thrash[key] = bool(
            timed_rate > idle_rate + page_size and timed_total > 16 * page_size
        )
    critical = any(int(row["pressure_code"]) == 2 for row in samples)
    rss_retained = post_run["rss_bytes"] <= 1.10 * post_warm["rss_bytes"]
    return {
        "critical_pressure": critical,
        "pageout_thrashing": thrash["pageouts_bytes"],
        "swapout_thrashing": thrash["swapouts_bytes"],
        "post_run_rss_within_110pct": bool(rss_retained),
        "passed": bool(not critical and not any(thrash.values()) and rss_retained),
        "post_warm_rss_bytes": int(post_warm["rss_bytes"]),
        "post_run_rss_bytes": int(post_run["rss_bytes"]),
    }


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


def npz_bytes(arrays: dict[str, np.ndarray]) -> bytes:
    buffer = BytesIO()
    np.savez(buffer, **arrays)
    return buffer.getvalue()


def load_models(config: dict[str, Any], mode: str):
    assets = config["runtime_assets"]
    bundle = runtime_core.load_bundle(
        PROJECT_ROOT / assets["bundle_manifest"]["path"],
        PROJECT_ROOT / assets["bundle_parameters"]["path"],
    )
    m1 = m3 = None
    if mode in ("B0", "B2"):
        m1 = runtime_core.TorchM1Backend(PROJECT_ROOT / assets["m1_checkpoint_root"])
    if mode in ("B1", "B2"):
        m3 = runtime_core.MlxM3Backend(
            PROJECT_ROOT / assets["m3_base_root"],
            PROJECT_ROOT / assets["m3_adapter"]["path"],
            PROJECT_ROOT / assets["m3_head"]["path"],
            PROJECT_ROOT / assets["m3_prompt"]["path"],
        )
    return bundle, m1, m3


def resource_smoke(config: dict[str, Any]) -> dict[str, Any]:
    sampler = MemorySampler()
    sampler.start()
    time.sleep(15.0)
    sampler.set_phase(1)
    bundle, m1, m3 = load_models(config, "B2")
    sampler.set_phase(2)
    warm("B2", bundle, m1, m3)
    sample = sampler.sample()
    sampler.stop()
    if sampler.errors or sample["pressure_code"] == 2:
        raise RuntimeError("EXP-067 both-resident resource smoke failed")
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": "Passed",
        "both_resident": True,
        "synthetic_warmup_only": True,
        "critical_pressure": False,
        "rss_bytes": int(sample["rss_bytes"]),
        "mlx_active_bytes": int(sample["mlx_active_bytes"]),
        "mlx_cache_bytes": int(sample["mlx_cache_bytes"]),
        "mlx_peak_bytes": int(sample["mlx_peak_bytes"]),
    }


def run_worker(config: dict[str, Any], mode: str, repetition: int, output_dir: Path) -> dict[str, Any]:
    if mode not in MODES or repetition not in (1, 2, 3):
        raise ValueError("EXP-067 worker identity drift")
    if os.path.lexists(output_dir):
        raise FileExistsError("EXP-067 worker output exists")
    output_dir.mkdir(mode=0o700)
    os.chmod(output_dir, 0o700)
    sampler = MemorySampler()
    started_at = utc_now()
    started = time.perf_counter()
    sampler.start()
    try:
        time.sleep(15.0)
        sampler.set_phase(1)
        bundle, m1, m3 = load_models(config, mode)
        sampler.set_phase(2)
        warm(mode, bundle, m1, m3)
        if mode in ("B1", "B2"):
            import mlx.core as mx

            mx.reset_peak_memory()
        post_warm = sampler.sample()
        texts = load_projection(config)
        arrays = {
            "ordinal": np.arange(720, dtype="<i2"),
            "tokenize_preprocess_ns": np.empty(720, dtype="<i8"),
            "m1_inference_ns": np.empty(720, dtype="<i8"),
            "feature_router_ns": np.empty(720, dtype="<i8"),
            "m3_inference_ns": np.empty(720, dtype="<i8"),
            "postprocess_materialize_ns": np.empty(720, dtype="<i8"),
            "total_ns": np.empty(720, dtype="<i8"),
            "route_mask": np.empty(720, dtype=np.uint8),
            "selected_path": np.empty(720, dtype=np.uint8),
            "final_prediction": np.empty((720, 6), dtype=np.uint8),
            "neutral": np.empty(720, dtype=np.uint8),
        }
        sampler.set_phase(3)
        for index, text in enumerate(texts):
            row = timed_row(mode, text, bundle, m1, m3)
            for key in arrays:
                if key != "ordinal":
                    arrays[key][index] = row[key]
        sampler.set_phase(4)
        post_run = sampler.sample()
        time.sleep(1.05)
        sampler.stop()
        if sampler.errors:
            raise RuntimeError("EXP-067 memory sampler error")
        gate = memory_gate(sampler.samples, post_warm, post_run)
        timing_path = output_dir / "timing-output.npz"
        memory_path = output_dir / "memory-samples.npz"
        _create(timing_path, npz_bytes(arrays), 0o600)
        _create(memory_path, npz_bytes(memory_arrays(sampler.samples)), 0o600)
        manifest = {
            "schema_version": "exp-067-worker-manifest-v1",
            "experiment_id": EXPERIMENT_ID,
            "mode": mode,
            "repetition": repetition,
            "status": "Completed",
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
            "elapsed_seconds": time.perf_counter() - started,
            "environment": config["environment"],
            "resident_set": {
                "m1": mode in ("B0", "B2"), "m3": mode in ("B1", "B2")
            },
            "warmup": {"synthetic_rows": 2, "excluded_from_timing": True},
            "rows": 720,
            "route_count": int(np.sum(arrays["route_mask"])),
            "fallback_count": 0,
            "errors": 0,
            "timing_output": record(timing_path),
            "memory_samples": record(memory_path),
            "memory_gate": gate,
            "access_attestation": {
                "label_free_projection_accessed": True,
                "original_validation_accessed": False,
                "test_accessed": False,
                "network_accessed": False,
            },
        }
        manifest_path = output_dir / "worker-manifest.json"
        _create(manifest_path, canonical_json(manifest), 0o600)
        return {
            "experiment_id": EXPERIMENT_ID,
            "status": "Completed",
            "mode": mode,
            "repetition": repetition,
            "rows": 720,
            "route_count": int(np.sum(arrays["route_mask"])),
            "memory_gate_passed": gate["passed"],
            "elapsed_seconds": manifest["elapsed_seconds"],
        }
    except Exception:
        sampler.stop()
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--mode", choices=MODES)
    parser.add_argument("--repetition", type=int)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--resource-smoke", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.resource_smoke:
        result = resource_smoke(config)
    else:
        if args.mode is None or args.repetition is None or args.output_dir is None:
            raise ValueError("EXP-067 formal worker arguments missing")
        result = run_worker(config, args.mode, args.repetition, args.output_dir.resolve())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
