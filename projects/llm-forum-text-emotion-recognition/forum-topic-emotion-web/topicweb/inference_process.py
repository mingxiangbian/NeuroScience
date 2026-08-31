"""Job-scoped JSONL bridge to the unchanged, verified seed-42 runtime.

Only deployment assets are opened. Historical projection/replay/label data are
deliberately excluded from the asset allowlist. Run with phase-a-runtime Python.
"""

from __future__ import annotations

import fcntl
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import resource
import signal
import stat
import sys
import time
from typing import Any, Callable, TextIO

sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARENT_RUN = (
    "experiments/stack-overflow-emotion-gold/oof-router/runs/"
    "exp-066-headless-runtime-parity/attempt-2/"
)
CONFIG_RECORD = {
    "path": PARENT_RUN + "frozen-sources/config.json", "bytes": 12778,
    "sha256": "106db4b86614ac70c84f04a322b046bc1049686099c590997955120993bb9983",
    "mode": "0644",
}
COMPLETION_RECORD = {
    "path": PARENT_RUN + "runtime-complete.json", "bytes": 1475,
    "sha256": "b039b80a3ba1778d38352fc8ee7c075dc342e17dd127d9acfd1574d99c149408",
    "mode": "0644",
}
OFFLINE_ENV = {
    "PYTHONNOUSERSITE": "1", "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false",
    "OMP_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1",
}
MAX_TEXT_BYTES = 65_536
MAX_ITEMS = 500
MAX_LINE_BYTES = 650_000
MAX_RSS_BYTES = 12 * 1024**3
MAX_MLX_BYTES = 10_000_000_000
MAX_SECONDS = 3600


class InferenceError(RuntimeError):
    """A fixed, public-safe error code; never carries user or library text."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="strict")).hexdigest()


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InferenceError("invalid_json")
        result[key] = value
    return result


def _json(value: str) -> dict[str, Any]:
    try:
        decoded = json.loads(
            value, object_pairs_hook=_no_duplicate_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (ValueError, TypeError, RecursionError):
        raise InferenceError("invalid_json") from None
    if not isinstance(decoded, dict):
        raise InferenceError("invalid_json")
    return decoded


def _file_state(path: Path) -> tuple[int, int, int, int, int, int]:
    value = path.lstat()
    if not stat.S_ISREG(value.st_mode):
        raise InferenceError("source_identity_drift")
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_mode, value.st_ctime_ns)


class Identity:
    """Hash once before loading; reject metadata drift before each request."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve(strict=True)
        self.states: dict[Path, tuple[int, int, int, int, int, int]] = {}
        self.inventories: dict[Path, set[str]] = {}

    def resolve(self, relative: str) -> Path:
        part = Path(relative)
        if part.is_absolute() or ".." in part.parts or not part.parts:
            raise InferenceError("source_identity_drift")
        path = self.root
        for component in part.parts:
            path = path / component
            if path.is_symlink():
                raise InferenceError("source_identity_drift")
        if not path.resolve(strict=True).is_relative_to(self.root):
            raise InferenceError("source_identity_drift")
        return path

    def check(self, record: dict[str, Any]) -> Path:
        path = self.resolve(record["path"])
        before = _file_state(path)
        if before[2] != record["bytes"] or stat.S_IMODE(before[4]) != int(record["mode"], 8):
            raise InferenceError("source_identity_drift")
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(4 * 1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != record["sha256"] or _file_state(path) != before:
            raise InferenceError("source_identity_drift")
        self.states[path] = before
        return path

    def unchanged(self) -> None:
        if any(_file_state(path) != previous for path, previous in self.states.items()):
            raise InferenceError("source_identity_drift")
        if any({path.name for path in directory.iterdir()} != names for directory, names in self.inventories.items()):
            raise InferenceError("source_identity_drift")

    def inventory(self, root: str, records: list[dict[str, Any]]) -> None:
        directory = self.resolve(root)
        if {path.name for path in directory.iterdir()} != {row["name"] for row in records}:
            raise InferenceError("source_identity_drift")
        self.inventories[directory] = {row["name"] for row in records}
        for row in records:
            self.check({**row, "path": root + "/" + row["name"]})


def verified_assets(root: Path = PROJECT_ROOT) -> tuple[dict[str, Any], Identity, str]:
    identity = Identity(root)
    config = _json(identity.check(CONFIG_RECORD).read_text(encoding="utf-8"))
    completion = _json(identity.check(COMPLETION_RECORD).read_text(encoding="utf-8"))
    if completion.get("status") != "Complete" or completion.get("cli_gate") != "open":
        raise InferenceError("parent_not_verified")
    verification = _json(identity.check(completion["verification"]).read_text(encoding="utf-8"))
    if verification.get("status") != "Passed" or verification.get("failed_count") != 0:
        raise InferenceError("parent_not_verified")
    identity.check(completion["run"])
    identity.check(completion["cli"])
    identity.check(config["implementation"]["runtime"])
    assets = config["runtime_assets"]
    # Never walk the entire runtime_assets mapping: it also names old data.
    for key in ("bundle_manifest", "bundle_parameters", "m3_base_manifest",
                "m3_adapter", "m3_head", "m3_prompt"):
        identity.check(assets[key])
    identity.inventory(assets["m1_checkpoint_root"], assets["m1_checkpoint_files"])
    identity.inventory(assets["m3_base_root"], assets["m3_base_files"])
    environment = config["environment"]
    if (sys.executable != environment["python_executable"]
            or platform.python_version() != environment["python_version"]
            or platform.machine() != environment["architecture"]):
        raise InferenceError("environment_identity_drift")
    for name, version in environment["packages"].items():
        if importlib.metadata.version(name.replace("_", "-")) != version:
            raise InferenceError("environment_identity_drift")
    if any(os.environ.get(key) != value for key, value in OFFLINE_ENV.items()):
        raise InferenceError("offline_environment_drift")
    fingerprint = hashlib.sha256(json.dumps({
        "input_contract": "phase-c-exact-utf8-v1",
        "bridge": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "parent_config": CONFIG_RECORD["sha256"],
        "parent_completion": COMPLETION_RECORD["sha256"],
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return config, identity, fingerprint


class ResourceGuard:
    def __init__(self) -> None:
        self.started = time.monotonic()
        self.mx: Any = None

    def snapshot(self) -> dict[str, Any]:
        rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if sys.platform != "darwin":
            rss *= 1024
        return {
            "peak_rss_bytes": rss,
            "mlx_peak_bytes": int(self.mx.get_peak_memory()) if self.mx else 0,
            "elapsed_seconds": time.monotonic() - self.started,
        }

    def check(self) -> dict[str, Any]:
        result = self.snapshot()
        if (result["peak_rss_bytes"] > MAX_RSS_BYTES
                or result["mlx_peak_bytes"] > MAX_MLX_BYTES
                or result["elapsed_seconds"] > MAX_SECONDS):
            raise InferenceError("resource_limit_exceeded")
        return result


def _metadata(backend: Any, text: str, kind: str, actual: int | None, runtime: Any) -> dict[str, Any]:
    if kind == "m1":
        full = len(backend.tokenizer.encode(text, add_special_tokens=True))
        return {"input_tokens": full, "used_tokens": actual, "truncated": full > actual}
    prompt = backend.prompt
    full = backend.tokenizer.apply_chat_template(
        [{"role": "system", "content": prompt["system"]},
         {"role": "user", "content": prompt["user_prefix"] + text + prompt["user_suffix"]}],
        tokenize=True, return_dict=False, add_generation_prompt=True, enable_thinking=False,
    )
    used = runtime.qwen_prompt_ids(backend.tokenizer, prompt, text, backend.max_length)
    return {"input_tokens": len(full), "used_tokens": len(used), "truncated": len(full) > len(used)}


class JobInference:
    def __init__(
        self, init: dict[str, Any], *, runtime: Any, bundle: Any, m1: Any,
        m3_factory: Callable[[], Any], fingerprint: str,
        guard: Any = None, identity_check: Callable[[], None] = lambda: None,
        metadata: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        validate_init(init)
        self.mode = init["mode"]
        self.maximum = init["max_qwen_calls"]
        self.runtime, self.bundle, self.m1 = runtime, bundle, m1
        self.m3_factory, self.fingerprint = m3_factory, fingerprint
        self.guard = guard or ResourceGuard()
        self.identity_check = identity_check
        self.metadata = metadata or (lambda backend, text, kind, actual: _metadata(backend, text, kind, actual, runtime))
        self.m3: Any = None
        self.m3_unavailable = False
        self.m1_cache: dict[str, Any] = {}
        self.m3_cache: dict[str, Any] = {}
        self.item_ids: set[str] = set()
        self.totals = {key: 0 for key in (
            "m1_attempts", "m3_attempts", "m3_succeeded", "m1_cache_hit", "m3_cache_hit", "audit_extra_calls"
        )}
        self.last_counters = dict(self.totals)

    def ready(self) -> dict[str, Any]:
        return {"type": "ready", "fingerprint": self.fingerprint,
                "modelstatus": {"m1": "loaded", "m3": "not_loaded", "mode": self.mode},
                "audit_rate": 0, "cache_scope": "job_exact_input_components"}

    def predict(self, request: dict[str, Any]) -> dict[str, Any]:
        import numpy as np

        self.identity_check()
        self.guard.check()
        started = time.monotonic()
        if set(request) != {"op", "item_id", "text", "model_input_hash"} or request["op"] != "predict":
            raise InferenceError("invalid_request")
        item_id, text = request["item_id"], request["text"]
        if (not isinstance(item_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", item_id)
                or not isinstance(text, str) or not text or len(text.encode("utf-8")) > MAX_TEXT_BYTES
                or request["model_input_hash"] != text_hash(text)):
            raise InferenceError("invalid_input")
        if item_id in self.item_ids:
            raise InferenceError("duplicate_item_id")
        if len(self.item_ids) >= MAX_ITEMS:
            raise InferenceError("item_limit_exceeded")
        self.item_ids.add(item_id)
        key = self.fingerprint + ":" + request["model_input_hash"]
        counters = {name: 0 for name in self.totals}
        self.last_counters = counters
        def count(name: str) -> None:
            counters[name] += 1
            self.totals[name] += 1
        if key in self.m1_cache:
            m1_probabilities, m1_tokens, m1_metadata = self.m1_cache[key]
            count("m1_cache_hit")
        else:
            count("m1_attempts")
            m1_probabilities, m1_tokens = self.m1.predict_probabilities(text)
            m1_probabilities = np.asarray(m1_probabilities)
            if (m1_probabilities.shape != (6,) or not np.isfinite(m1_probabilities).all()
                    or np.any((m1_probabilities < 0) | (m1_probabilities > 1))
                    or type(m1_tokens) is not int or not 1 <= m1_tokens <= 256):
                raise InferenceError("model_output_invalid")
            m1_probabilities = np.ascontiguousarray(m1_probabilities, dtype=np.float32)
            m1_metadata = self.metadata(self.m1, text, "m1", m1_tokens)
            self.m1_cache[key] = (m1_probabilities, m1_tokens, m1_metadata)
        features = self.runtime.build_features(m1_probabilities, self.bundle.m1_threshold, len(text), m1_tokens)
        _, route_score, eligible = self.bundle.route(features)
        requested = bool(eligible and self.mode != "m1_only")
        m3_probabilities = m3_metadata = None
        fallback_reason = None
        if requested:
            if key in self.m3_cache:
                m3_probabilities, m3_metadata = self.m3_cache[key]
                count("m3_cache_hit")
            elif self.m3_unavailable:
                fallback_reason = "m3_unavailable"
            elif self.totals["m3_attempts"] >= self.maximum:
                fallback_reason = "m3_budget_exhausted"
            else:
                count("m3_attempts")
                # A failed model initialization/forward is still a consumed attempt.
                try:
                    if self.m3 is None:
                        self.m3 = self.m3_factory()
                    m3_probabilities = np.asarray(self.m3.predict_probabilities(text), dtype=np.float32)
                    if (m3_probabilities.shape != (6,) or not np.isfinite(m3_probabilities).all()
                            or np.any((m3_probabilities < 0) | (m3_probabilities > 1))):
                        raise InferenceError("model_output_invalid")
                    m3_metadata = self.metadata(self.m3, text, "m3", None)
                    self.m3_cache[key] = (m3_probabilities, m3_metadata)
                    count("m3_succeeded")
                except InferenceError:
                    raise
                except Exception:
                    self.guard.check()
                    self.m3_unavailable = True
                    m3_probabilities = None
                    fallback_reason = "m3_runtime_failure"
            if fallback_reason and self.mode == "research":
                raise InferenceError(fallback_reason)
        use_m3 = m3_probabilities is not None
        selected = m3_probabilities if use_m3 else np.asarray(m1_probabilities)
        threshold = self.bundle.m3_threshold if use_m3 else self.bundle.m1_threshold
        prediction = (selected >= threshold).astype(int).tolist()
        labels = [label for label, value in zip(self.runtime.LABEL_ORDER, prediction) if value]
        self.identity_check()
        resources = self.guard.check()
        result = {
            "prediction": prediction, "prediction6": prediction, "active_labels": labels, "labels": labels,
            "neutral": not labels, "used_path": "m3" if use_m3 else "m1",
            "actual_model": "m3" if use_m3 else "m1",
            "route_requested": requested, "route_eligible": bool(eligible), "routed": requested,
            "hypothetical_route": bool(eligible), "fallback": bool(fallback_reason),
            "fallback_reason": fallback_reason, "degraded": bool(fallback_reason),
            "m1_probabilities": np.asarray(m1_probabilities).tolist(),
            "m3_probabilities": m3_probabilities.tolist() if use_m3 else None,
            "m1_prediction": (np.asarray(m1_probabilities) >= self.bundle.m1_threshold).astype(int).tolist(),
            "m3_prediction": (m3_probabilities >= self.bundle.m3_threshold).astype(int).tolist() if use_m3 else None,
            "route_score": float(route_score), "m1_entropy": float(features[6]),
            "threshold_margin": float(features[8]),
            "tokenlengths": {"m1": m1_metadata, "m3": m3_metadata},
            "truncflags": {"m1": m1_metadata["truncated"], "m3": m3_metadata["truncated"] if m3_metadata else None},
            "counters": {**counters, "fallback_reason": fallback_reason}, "cumulative_counters": dict(self.totals),
            "m3_attempted": bool(counters["m3_attempts"]),
            "m3_succeeded": bool(counters["m3_succeeded"]),
            "cache_hit": bool(counters["m1_cache_hit"] and (not requested or counters["m3_cache_hit"])),
            "audit_extra_calls": 0, "latency_ms": (time.monotonic() - started) * 1000,
            "resources": resources, "fingerprint": self.fingerprint,
        }
        return {"type": "result", "item_id": item_id, "result": result}


def validate_init(init: dict[str, Any]) -> None:
    if (set(init) != {"op", "mode", "max_qwen_calls", "audit_rate", "seed"}
            or init["op"] != "init" or init["mode"] not in {"m1_only", "research", "demo"}
            or type(init["max_qwen_calls"]) is not int or not 0 <= init["max_qwen_calls"] <= MAX_ITEMS
            or type(init["seed"]) is not int or init["seed"] != 42
            or type(init["audit_rate"]) not in {int, float} or init["audit_rate"] != 0):
        raise InferenceError("invalid_init")


def _load_runtime(runtime_path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("topicweb_frozen_runtime_exp066", runtime_path)
    runtime = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runtime
    try:
        spec.loader.exec_module(runtime)
    except Exception:
        sys.modules.pop(spec.name, None)
        raise
    return runtime


def build_real_engine(init: dict[str, Any]) -> JobInference:
    validate_init(init)
    guard = ResourceGuard()
    config, identity, fingerprint = verified_assets()
    runtime_path = identity.resolve(config["implementation"]["runtime"]["path"])
    runtime = _load_runtime(runtime_path)
    assets = config["runtime_assets"]
    bundle = runtime.load_bundle(identity.resolve(assets["bundle_manifest"]["path"]), identity.resolve(assets["bundle_parameters"]["path"]))
    m1 = runtime.TorchM1Backend(identity.resolve(assets["m1_checkpoint_root"]), max_length=256)
    guard.check()

    def m3_factory() -> Any:
        import mlx.core as mx

        guard.mx = mx
        mx.set_memory_limit(MAX_MLX_BYTES)
        mx.set_cache_limit(512 * 1024**2)
        backend = runtime.MlxM3Backend(
            identity.resolve(assets["m3_base_root"]),
            identity.resolve(assets["m3_adapter"]["path"]),
            identity.resolve(assets["m3_head"]["path"]),
            identity.resolve(assets["m3_prompt"]["path"]), max_length=384,
        )
        guard.check()
        identity.unchanged()
        return backend

    identity.unchanged()
    return JobInference(init, runtime=runtime, bundle=bundle, m1=m1, m3_factory=m3_factory,
                        fingerprint=fingerprint, guard=guard, identity_check=identity.unchanged)


def serve(input_stream: TextIO, output: TextIO, factory: Callable[..., JobInference] = build_real_engine) -> int:
    def emit(value: dict[str, Any]) -> None:
        output.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
        output.flush()

    item_id: str | None = None
    engine: JobInference | None = None
    try:
        line = input_stream.readline(MAX_LINE_BYTES + 1)
        if not line or len(line.encode("utf-8")) > MAX_LINE_BYTES:
            raise InferenceError("invalid_init")
        init = _json(line)
        validate_init(init)
        engine = factory(init)
        emit(engine.ready())
        while True:
            item_id = None
            line = input_stream.readline(MAX_LINE_BYTES + 1)
            if not line:
                engine.identity_check()
                engine.guard.check()
                return 0
            if len(line.encode("utf-8")) > MAX_LINE_BYTES:
                raise InferenceError("invalid_request")
            request = _json(line)
            if request == {"op": "close"}:
                engine.identity_check()
                engine.guard.check()
                return 0
            candidate = request.get("item_id")
            # Backend IDs are opaque; untrusted malformed identifiers are not echoed.
            if isinstance(candidate, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", candidate):
                item_id = candidate
            emit(engine.predict(request))
    except Exception as error:
        response = {"type": "error", "item_id": item_id,
                    "code": error.code if isinstance(error, InferenceError) else "inference_failed"}
        if engine is not None:
            response["counters"] = engine.last_counters
            response["cumulative_counters"] = dict(engine.totals)
        emit(response)
        return 1


def main() -> int:
    os.environ.update(OFFLINE_ENV)
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    def deny_network(event: str, _: Any) -> None:
        if event in {"socket.connect", "socket.getaddrinfo"}:
            raise InferenceError("network_access_forbidden")
    sys.addaudithook(deny_network)
    # Keep JSONL on a separate descriptor. Native library diagnostics are discarded
    # too, rather than risking input text appearing on either captured log stream.
    output = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", buffering=1)
    with open(os.devnull, "w") as sink:
        os.dup2(sink.fileno(), 1)
        os.dup2(sink.fileno(), 2)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(InferenceError("resource_limit_exceeded")))
    signal.alarm(MAX_SECONDS)
    lock = None
    try:
        dispatch_fd = os.environ.get("TOPICWEB_DISPATCH_LOCK_FD")
        if dispatch_fd is not None:
            fd = int(dispatch_fd)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise InferenceError("invalid_dispatch_lock")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_path = PROJECT_ROOT / "experiments/stack-overflow-emotion-gold/oof-router/private/locks/heavy-research-workload.lock"
        if lock_path.is_symlink() or not lock_path.is_file():
            raise InferenceError("invalid_heavy_lock")
        lock = lock_path.open("r+")
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return serve(sys.stdin, output)
    except Exception as error:
        output.write(json.dumps({"type": "error", "item_id": None,
                                 "code": error.code if isinstance(error, InferenceError) else "startup_failed"}) + "\n")
        output.flush()
        return 1
    finally:
        signal.alarm(0)
        if lock is not None:
            lock.close()
        output.close()


if __name__ == "__main__":
    raise SystemExit(main())
