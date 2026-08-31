"""One dispatcher and one separately owned inference process at a time."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import selectors
import shutil
import subprocess
import threading
import time
from pathlib import Path

from .adapters import SourceError
from .store import ACTIVE, dumps


class WorkerError(RuntimeError):
    def __init__(self, code, metadata=None):
        super().__init__(code)
        self.metadata = metadata or {}


class Revoked(WorkerError):
    pass


def safe_error_frames(exc):
    root = Path(__file__).resolve().parents[1]
    allowed = {f"topicweb/{name}.py" for name in ("worker", "adapters", "core", "store", "app", "inference_process")}
    frames = []
    cursor = exc.__traceback__
    while cursor is not None:
        code = cursor.tb_frame.f_code
        try:
            relative = Path(code.co_filename).resolve().relative_to(root).as_posix()
        except ValueError:
            relative = None
        if relative in allowed and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", code.co_name):
            frames.append({"file": relative, "function": code.co_name, "line": cursor.tb_lineno})
        cursor = cursor.tb_next
    return frames[-4:]


class ProcessRunner:
    def __init__(self, job, *, lock_fd, cancelled, deadline, command=None):
        self.cancelled = cancelled
        self.deadline = deadline
        self.process = None
        self.selector = selectors.DefaultSelector()
        self.buffer = b""
        self.command = command or [
            "/Users/phoenix/miniconda3/envs/phase-a-runtime/bin/python",
            "-m", "topicweb.inference_process",
        ]
        env = dict(os.environ)
        env.update({"PYTHONNOUSERSITE": "1", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false", "OMP_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1", "TOPICWEB_DISPATCH_LOCK_FD": str(lock_fd)})
        try:
            self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=Path(__file__).resolve().parents[1], env=env, pass_fds=(lock_fd,), bufsize=0)
            os.set_blocking(self.process.stdin.fileno(), False)
            self.selector.register(self.process.stdout, selectors.EVENT_READ)
            request = job["request"]
            self._send({"op": "init", "mode": job["mode"], "max_qwen_calls": request.get("max_qwen_calls", 20), "audit_rate": request.get("audit_rate", 0), "seed": 42})
            if self._read().get("type") != "ready":
                raise WorkerError("inference_initialization_failed")
        except BaseException:
            self.close()
            raise

    def _check(self):
        if self.cancelled():
            raise Revoked("job_revoked")
        if time.monotonic() >= self.deadline:
            raise WorkerError("job_time_limit")

    def _send(self, value):
        encoded = memoryview((dumps(value) + "\n").encode("utf-8"))
        with selectors.DefaultSelector() as writable:
            writable.register(self.process.stdin, selectors.EVENT_WRITE)
            while encoded:
                self._check()
                if self.process.poll() is not None:
                    raise WorkerError("inference_process_exited")
                if writable.select(timeout=0.2):
                    try:
                        count = os.write(self.process.stdin.fileno(), encoded[:65536])
                        encoded = encoded[count:]
                    except BlockingIOError:
                        continue

    def _read(self):
        while True:
            self._check()
            if b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                try:
                    result = json.loads(line)
                    if not isinstance(result, dict):
                        raise ValueError()
                except (ValueError, UnicodeDecodeError):
                    raise WorkerError("invalid_inference_response") from None
                if result.get("type") == "error":
                    # Never echo a child exception or a model input into API errors.
                    raise self._failure(result)
                return result
            if len(self.buffer) > 2 * 1024 * 1024:
                raise WorkerError("inference_response_limit")
            events = self.selector.select(timeout=0.2)
            if events:
                chunk = os.read(self.process.stdout.fileno(), 65536)
                if not chunk:
                    raise WorkerError("inference_process_exited")
                self.buffer += chunk
            elif self.process.poll() is not None:
                raise WorkerError("inference_process_exited")

    def predict(self, item_id, record):
        text = record.get("model_input_text", record.get("model_input"))
        if not isinstance(text, str) or len(text.encode("utf-8")) > 65536:
            raise WorkerError("invalid_model_input")
        self._send({"op": "predict", "item_id": str(item_id), "text": text, "model_input_hash": record["model_input_hash"]})
        response = self._read()
        if response.get("type") != "result" or response.get("item_id") != str(item_id) or not isinstance(response.get("result"), dict):
            raise WorkerError("inference_identity_mismatch")
        if os.environ.get("TOPICWEB_TELEMETRY") == "1":
            from .telemetry import current_rss
            sample = current_rss(self.process.pid)
            response["result"]["telemetry"] = sample
            if (sample["status"] != "observed" or sample["child_current_rss_bytes"] > 12 * 1024**3
                    or sample["parent_current_rss_bytes"] > 1024**3):
                raise WorkerError("telemetry_unavailable" if sample["status"] != "observed" else "current_rss_limit",
                                  {"telemetry": sample, "cumulative_counters": response["result"].get("cumulative_counters", {})})
        return response["result"]

    @staticmethod
    def _failure(response):
        code = response.get("code", "inference_failed")
        if not isinstance(code, str) or not re.fullmatch(r"[a-z0-9_]{1,64}", code):
            code = "inference_failed"
        metadata = {}
        for key in ("counters", "cumulative_counters"):
            if isinstance(response.get(key), dict):
                metadata[key] = {name: value for name, value in response[key].items() if name in {"m1_attempts", "m3_attempts", "m3_succeeded", "m1_cache_hit", "m3_cache_hit", "audit_extra_calls"} and type(value) is int and value >= 0}
        return WorkerError(code, metadata)

    def finish(self):
        """A successful job also requires the child's final identity gate and exit 0."""
        self._send({"op": "close"})
        while self.process.poll() is None:
            self._check()
            time.sleep(0.05)
        if self.process.returncode != 0:
            remaining = self.buffer + self.process.stdout.read(2 * 1024 * 1024)
            for line in remaining.splitlines():
                try:
                    response = json.loads(line)
                except ValueError:
                    continue
                if isinstance(response, dict) and response.get("type") == "error":
                    raise self._failure(response)
            raise WorkerError("inference_final_gate_failed")
        self.close()

    def close(self):
        process = self.process
        if process is not None:
            if process.poll() is None:
                try:
                    process.stdin.write(b'{"op":"close"}\n')
                    process.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass
                try:
                    if self.cancelled() or time.monotonic() >= self.deadline:
                        process.terminate()
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            if process.stdin:
                process.stdin.close()
            if process.stdout:
                process.stdout.close()
        self.selector.close()


class Dispatcher:
    def __init__(self, store, aggregate, fetch, runner_factory=ProcessRunner, *, deadline_seconds=3600):
        self.store = store
        self.aggregate = aggregate
        self.fetch = fetch
        self.runner_factory = runner_factory
        self.deadline_seconds = deadline_seconds
        self.stop_event = threading.Event()
        self.lock = None
        self.thread = None
        self.current_job = None

    def start(self):
        lock_path = self.store.private_dir / "dispatcher.lock"
        if lock_path.is_symlink():
            raise WorkerError("dispatcher_lock_symlink")
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        self.lock = os.fdopen(fd, "a+")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            self.lock = None
            raise WorkerError("dispatcher_already_running") from None
        self.store.recover_after_exclusive_lock()
        self.store.purge()
        self.thread = threading.Thread(target=self._loop, name="topicweb-dispatcher", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=12)
            if self.thread.is_alive():
                # Keep the lock held if a worker has not acknowledged shutdown.
                raise WorkerError("dispatcher_shutdown_pending")
        if self.lock:
            self.lock.close()
            self.lock = None

    def _loop(self):
        last_purge = time.monotonic()
        while not self.stop_event.is_set():
            job = self.store.claim()
            if job:
                self.current_job = job["id"]
                self.run_job(job)
                self.current_job = None
            else:
                self.stop_event.wait(0.25)
            if time.monotonic() - last_purge >= 3600:
                self.store.purge()
                last_purge = time.monotonic()

    def run_job(self, job):
        job_id = job["id"]
        deadline = time.monotonic() + self.deadline_seconds
        runner = None
        stage = "resource_check"

        def cancelled():
            return self.stop_event.is_set() or self.store.cancelled(job_id)

        try:
            if shutil.disk_usage(self.store.private_dir).free < 512 * 1024 * 1024:
                raise WorkerError("disk_budget_exceeded")
            if job["state"] == "fetching":
                stage = "fetch"
                fetched = self.fetch(job["request"]["query"], cancelled=cancelled, progress=lambda value: self.store.progress(job_id, value))
                stage = "validation"
                records, manifest = fetched
                if not isinstance(records, list) or not isinstance(manifest, dict):
                    raise TypeError("invalid_source_snapshot")
                dumps(records)
                dumps(manifest)
                if cancelled():
                    raise Revoked("job_revoked")
                stage = "seal"
                if not self.store.seal(job_id, records, manifest):
                    raise Revoked("job_revoked")
                job = self.store.get(job_id, private=True)
            stage = "snapshot_validation"
            if not self.store.transition(job_id, "snapshot_sealed", "inferencing"):
                raise Revoked("job_revoked")
            rows = self.store.items(job_id, private=True)
            if not rows:
                raise WorkerError("empty_snapshot")
            observed_hash = hashlib.sha256(dumps([row["record"] for row in rows]).encode()).hexdigest()
            if observed_hash != job["snapshot_hash"]:
                raise WorkerError("snapshot_hash_mismatch")
            stage = "inference_start"
            runner = self.runner_factory(job, lock_fd=self.lock.fileno(), cancelled=cancelled, deadline=deadline)
            results = []
            records = []
            for row in rows:
                stage = "inference"
                if cancelled():
                    raise Revoked("job_revoked")
                if time.monotonic() >= deadline:
                    raise WorkerError("job_time_limit")
                result = runner.predict(row["ordinal"], row["record"])
                if job["mode"] == "research" and result.get("fallback"):
                    raise WorkerError("research_fallback_forbidden")
                stage = "result_store"
                if not self.store.put_result(job_id, row["ordinal"], result):
                    if cancelled():
                        raise Revoked("job_revoked")
                    raise WorkerError("result_write_conflict")
                records.append(row["record"])
                results.append(result)
            stage = "inference_final_gate"
            if hasattr(runner, "finish"):
                runner.finish()
            else:
                runner.close()
            runner = None
            stage = "aggregation"
            if not self.store.transition(job_id, "inferencing", "aggregating"):
                raise Revoked("job_revoked")
            dashboard = self.aggregate(records, results, job["manifest"], job["mode"])
            terminal = "completed_with_fallback" if any(result.get("fallback") for result in results) else "completed"
            self.store.transition(job_id, "aggregating", terminal, dashboard=dashboard)
        except Revoked:
            # Shutdown is a failure, explicit user cancellation remains cancelled.
            if self.stop_event.is_set():
                self.store.transition(job_id, ACTIVE, "failed", error_code="worker_shutdown")
        except Exception as exc:
            current = self.store.get(job_id)
            progress = dict(current["progress"] or {}) if current else {}
            exception_type = type(exc).__name__
            if isinstance(exc, SourceError):
                code = getattr(exc, "code", "source_validation_error")
                progress["source_error"] = dict(getattr(exc, "metadata", {}))
                exception_type = "SourceError"
            elif isinstance(exc, WorkerError):
                code = str(exc)
                if not re.fullmatch(r"[a-z0-9_]{1,64}", code):
                    code = "worker_failed"
                if exc.metadata:
                    progress["failure_cost"] = exc.metadata
                exception_type = "WorkerError"
            else:
                code = "worker_failed"
                if exception_type not in {"TypeError", "ValueError", "KeyError", "IndexError", "AttributeError", "OSError", "TimeoutError", "RuntimeError", "MemoryError", "JSONDecodeError"}:
                    exception_type = "Exception"
            progress["worker_error"] = {"stage": stage, "exception_type": exception_type, "frames": safe_error_frames(exc)}
            self.store.transition(job_id, ACTIVE, "failed", error_code=code, progress=progress)
        finally:
            if runner is not None:
                runner.close()
            self.store.finish_revocation(job_id)
