"""Serial per-job M1 prepass and in-memory receipt transfer, with physical costs."""
from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import time

from .staged_safety import SafetyError, SafetyMonitor
from .store import ACTIVE, dumps
from .worker import Dispatcher, ProcessRunner, Revoked, WorkerError

COSTS = ("m1_attempts", "m3_attempts", "m3_succeeded", "m1_cache_hit", "m3_cache_hit", "audit_extra_calls")
M1_COSTS = {"m1_attempts", "m1_cache_hit"}
STRATEGY = "m1-receipt-transfer-v1"
BLOCKING_INFERENCE_CODES = {
    "inference_initialization_failed", "inference_process_exited", "inference_final_gate_failed", "inference_failed",
    "inference_response_limit", "invalid_staged_progress", "model_output_invalid", "unexpected_m1_prelude_cost",
    "invalid_resource_metadata", "model_resource_unknown", "invalid_telemetry", "research_fallback_forbidden",
    "invalid_dispatch_lock", "invalid_heavy_lock", "invalid_init", "invalid_json", "invalid_request",
    "network_access_forbidden", "parent_not_verified", "m3_runtime_failure", "m3_unavailable",
}
RESULT_FIELDS = {
    "prediction", "prediction6", "active_labels", "labels", "neutral", "used_path", "actual_model",
    "route_requested", "route_eligible", "routed", "hypothetical_route", "fallback", "fallback_reason", "degraded",
    "m1_probabilities", "m3_probabilities", "m1_prediction", "m3_prediction", "route_score", "m1_entropy",
    "threshold_margin", "tokenlengths", "truncflags", "counters", "cumulative_counters", "m3_attempted", "m3_succeeded",
    "cache_hit", "audit_extra_calls", "latency_ms", "resources", "fingerprint", "telemetry",
    "prelude_transfer_reuse", "m1_execution_origin",
}


class CleanupPending(BaseException):
    """Do not let the legacy dispatcher publish terminal state before revocation."""


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def counters(value):
    if not isinstance(value, dict) or any(type(value.get(key)) is not int or value[key] < 0 for key in COSTS):
        raise WorkerError("invalid_inference_counters")
    return {key: value[key] for key in COSTS}


def safe_result(result):
    if not isinstance(result, dict):
        raise WorkerError("invalid_inference_response")
    out = {key: value for key, value in result.items() if key in RESULT_FIELDS}
    original_counters = out.get("counters")
    out["counters"] = counters(original_counters)
    if "fallback_reason" in original_counters:
        out["counters"]["fallback_reason"] = original_counters["fallback_reason"]
    out["cumulative_counters"] = counters(out.get("cumulative_counters"))
    for name in ("m1_probabilities", "m3_probabilities"):
        value = out.get(name)
        if value is None and name == "m3_probabilities":
            continue
        if not isinstance(value, list) or len(value) != 6 or any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1 for p in value):
            raise WorkerError("invalid_inference_probabilities")
    for name in ("prediction", "m1_prediction", "m3_prediction"):
        value = out.get(name)
        if value is None and name == "m3_prediction":
            continue
        if not isinstance(value, list) or len(value) != 6 or any(type(p) is not int or p not in (0, 1) for p in value):
            raise WorkerError("invalid_inference_prediction")
    labels = {"love", "joy", "surprise", "anger", "sadness", "fear"}
    for name in ("labels", "active_labels"):
        if name in out and (not isinstance(out[name], list) or any(label not in labels for label in out[name])):
            raise WorkerError("invalid_inference_labels")
    if out.get("fallback_reason") is not None and not re.fullmatch(r"[a-z0-9_]{1,64}", str(out["fallback_reason"])):
        raise WorkerError("invalid_fallback_reason")
    if out["counters"].get("fallback_reason") != out.get("fallback_reason"):
        raise WorkerError("invalid_fallback_reason")
    if not isinstance(out.get("fingerprint"), str) or not re.fullmatch(r"[a-f0-9]{64}", out["fingerprint"]):
        raise WorkerError("invalid_inference_fingerprint")
    for name in ("route_requested", "route_eligible", "routed", "hypothetical_route", "fallback", "degraded", "neutral", "cache_hit", "m3_attempted", "m3_succeeded", "prelude_transfer_reuse"):
        if name in out and type(out[name]) is not bool:
            raise WorkerError("invalid_inference_flag")
    for name in ("used_path", "actual_model"):
        if name in out and out[name] not in {"m1", "m3"}:
            raise WorkerError("invalid_inference_path")
    for name in ("route_score", "m1_entropy", "threshold_margin", "latency_ms"):
        if name in out and (type(out[name]) not in (int, float) or not math.isfinite(out[name]) or out[name] < 0):
            raise WorkerError("invalid_inference_number")
    if "prediction6" in out and out["prediction6"] != out["prediction"]:
        raise WorkerError("invalid_prediction_alias")
    if "m1_execution_origin" in out and out["m1_execution_origin"] != "current_job_m1_receipt":
        raise WorkerError("invalid_execution_origin")
    tokens = out.get("tokenlengths")
    if not isinstance(tokens, dict) or set(tokens) != {"m1", "m3"}:
        raise WorkerError("invalid_token_metadata")
    for name, metadata in tokens.items():
        if metadata is None and name == "m3":
            continue
        if (not isinstance(metadata, dict) or set(metadata) != {"input_tokens", "used_tokens", "truncated"}
                or type(metadata["input_tokens"]) is not int or type(metadata["used_tokens"]) is not int
                or not 1 <= metadata["used_tokens"] <= metadata["input_tokens"]
                or type(metadata["truncated"]) is not bool or metadata["truncated"] != (metadata["input_tokens"] > metadata["used_tokens"])):
            raise WorkerError("invalid_token_metadata")
    resource = out.get("resources")
    if not isinstance(resource, dict) or not {"peak_rss_bytes", "mlx_peak_bytes", "elapsed_seconds"} <= set(resource):
        raise WorkerError("invalid_resource_metadata")
    out["resources"] = {key: resource[key] for key in ("peak_rss_bytes", "mlx_peak_bytes", "elapsed_seconds")}
    if "truncflags" in out:
        if not isinstance(out["truncflags"], dict) or set(out["truncflags"]) != {"m1", "m3"} or any(value is not None and type(value) is not bool for value in out["truncflags"].values()):
            raise WorkerError("invalid_truncation_flags")
    if "telemetry" in out:
        telemetry = out["telemetry"]
        fields = {"status", "sampled_at", "monotonic", "child_pid", "parent_pid", "child_current_rss_bytes", "parent_current_rss_bytes", "raw_ps", "sampling_seconds", "error_type"}
        if not isinstance(telemetry, dict) or telemetry.get("status") not in {"observed", "unknown"}:
            raise WorkerError("invalid_telemetry")
        out["telemetry"] = {key: value for key, value in telemetry.items() if key in fields}
        raw = telemetry.get("raw_ps")
        if raw is not None and (not isinstance(raw, str) or len(raw) > 1024 or not all(re.fullmatch(r"\s*\d+\s+\d+\s*", line) for line in raw.splitlines())):
            raise WorkerError("invalid_telemetry")
    return json.loads(dumps(out))


class StagedProcessRunner(ProcessRunner):
    """Observe the existing transport; do not change its termination semantics."""
    def __init__(self, job, *, lock_fd, cancelled, deadline, monitor, logical_job_id,
                 transfer=None, on_progress=None, command=None):
        self.monitor, self.logical_job_id, self.phase_id = monitor, logical_job_id, job["id"]
        self._mode = job["mode"]
        self.transfer, self.on_progress = transfer, on_progress
        self.ready_response = None
        self.process_key = None
        self.exit_recorded = self.closed = False
        self.close_error = None
        self.process = None
        self.constructed_at = time.monotonic()
        monitor.current_runner = self
        if command is None and transfer is not None:
            command = ["/Users/phoenix/miniconda3/envs/phase-a-runtime/bin/python", "-m", "topicweb.staged_inference"]
        try:
            monitor.process_event("constructor_started", logical_job_id, self.phase_id)
            monitor.check()
            super().__init__(job, lock_fd=lock_fd, cancelled=cancelled, deadline=deadline, command=command)
            self._birth()
            monitor.process_event("ready", logical_job_id, self.phase_id, pid=self.process.pid,
                                  process_key=self.process_key, ready=self.ready_response)
            monitor.check()
        except BaseException as exc:
            try:
                self.close()
            except BaseException as cleanup:
                exc = cleanup
            exc._staged_phase_runner = self
            raise exc

    def _birth(self):
        if self.process is not None and self.process_key is None:
            identity = self.monitor.identify(self.process.pid, not_before=self.constructed_at)
            self.process_key = identity["process_key"]

    def _send(self, value):
        if value.get("op") == "init":
            self._birth()
            if self.transfer is not None:
                value = {**value, "transfer": self.transfer, "transfer_sha256": digest(dumps(self.transfer))}
        return super()._send(value)

    def _read(self):
        while True:
            response = super()._read()
            if response.get("type") == "staged_progress":
                if (self.transfer is None or set(response) != {"type", "stage", "kind", "ordinal", "cumulative_counters", "resources"}
                        or response["stage"] not in {"m3_load", "m3_forward"} or response["kind"] not in {"begin", "end"}
                        or type(response["ordinal"]) is not int or not 0 <= response["ordinal"] < 500):
                    raise WorkerError("invalid_staged_progress")
                response["cumulative_counters"] = counters(response["cumulative_counters"])
                self.monitor.observe_resources(response["resources"])
                if self.on_progress:
                    self.on_progress(response)
                self.monitor.check()
                continue
            if response.get("type") == "ready":
                if not isinstance(response.get("fingerprint"), str) or not re.fullmatch(r"[a-f0-9]{64}", response["fingerprint"]):
                    raise WorkerError("invalid_ready_identity")
                allowed = {"type", "fingerprint", "modelstatus", "audit_rate", "cache_scope", "m1_instance_absent",
                           "base_fingerprint", "transfer_sha256", "transfer_items", "cache_entries", "strategy"}
                self.ready_response = {key: value for key, value in response.items() if key in allowed}
                if response.get("audit_rate") != 0 or response.get("cache_scope") not in {"job_exact_input_components", "job_m1_receipt_transfer"}:
                    raise WorkerError("invalid_ready_metadata")
                if self.transfer is not None:
                    expected_fingerprint = digest(dumps({"base_fingerprint": self.transfer["base_fingerprint"], "strategy": STRATEGY,
                                                         "transfer_sha256": digest(dumps(self.transfer))}))
                    if (response.get("m1_instance_absent") is not True
                            or response.get("modelstatus") != {"m1": "receipt_replay_not_loaded", "m3": "not_loaded", "mode": self._mode}
                            or response.get("strategy") != STRATEGY or response["fingerprint"] != expected_fingerprint
                            or response.get("transfer_sha256") != digest(dumps(self.transfer))
                            or response.get("base_fingerprint") != self.transfer["base_fingerprint"]
                            or response.get("transfer_items") != len(self.transfer["entries"])
                            or response.get("cache_entries") != len({row["input_sha256"] for row in self.transfer["entries"]})):
                        raise WorkerError("staged_ready_identity")
                elif response.get("modelstatus") != {"m1": "loaded", "m3": "not_loaded", "mode": "m1_only"}:
                    raise WorkerError("m1_ready_identity")
            return response

    def predict(self, item_id, record):
        result = safe_result(super().predict(item_id, record))
        self.monitor.observe_resources(result["resources"])
        self.monitor.check()
        return result

    def finish(self):
        super().finish()
        self.monitor.process_event("final_gate_passed", self.logical_job_id, self.phase_id, pid=self.process.pid,
                                   process_key=self.process_key, returncode=self.process.returncode, normal_exit=True)

    def close(self):
        if self.closed:
            return
        if self.close_error is not None:
            raise self.close_error
        process = getattr(self, "process", None)
        if process is not None and self.process_key is None:
            try:
                self._birth()
            except Exception:
                self.monitor.block("process_birth_unobserved")
        try:
            if hasattr(self, "selector"):
                super().close()
        except BaseException as exc:
            self.close_error = exc
            raise
        finally:
            if process is not None and process.returncode is not None and not self.exit_recorded:
                self.monitor.process_event("process_exit", self.logical_job_id, self.phase_id, pid=process.pid,
                                           process_key=self.process_key, returncode=process.returncode)
                self.exit_recorded = True
            self.transfer = None
            self.closed = process is None or process.returncode is not None
            if self.closed and getattr(self.monitor, "current_runner", None) is self:
                self.monitor.current_runner = None


class StagedRunner:
    def __init__(self, job, *, store, lock_fd, cancelled, deadline, monitor, phase_runner_factory=StagedProcessRunner):
        self.job, self.store, self.lock_fd = job, store, lock_fd
        self.cancelled_callback, self.deadline, self.monitor = cancelled, deadline, monitor
        self.phase_runner_factory = phase_runner_factory
        self.rows = store.items(job["id"], private=True)
        self.prelude = []
        self.receipt_events = []
        self.transfer = None
        self.active = None
        self.phase = None
        self.phase_complete = False
        self.ready_for_outputs = False
        self.closed = False
        self.cleanup_error = None
        self.output_ordinal = 0
        self.m1_total = {key: 0 for key in COSTS}
        self.m3_total = {key: 0 for key in COSTS}
        self.transfer_reuses = 0
        self.progress_stage, self.progress_completed, self.progress_phase_id = "waiting_m1_quiet", 0, None
        self._check()
        if not 1 <= len(self.rows) <= 500 or [row["ordinal"] for row in self.rows] != list(range(len(self.rows))):
            raise WorkerError("staged_snapshot_count")
        if digest(dumps([row["record"] for row in self.rows])) != job["snapshot_hash"]:
            raise WorkerError("snapshot_hash_mismatch")

    def _revoked(self):
        # This callback is passed into old ProcessRunner.close: it must never raise.
        try:
            return bool(self.cancelled_callback())
        except Exception:
            self.monitor.block("cancellation_check_failed")
            return True

    def _expired(self):
        current = self.store.get(self.job["id"])
        return current is not None and (current.get("raw_expired") or current.get("items_expired")
                                       or time.time() >= current["raw_expires_at"])

    def _transport_cancelled(self):
        try:
            return bool(self.monitor.reason or self._revoked() or self._expired())
        except Exception:
            self.monitor.block("cancellation_check_failed")
            return True

    def _check(self):
        self.monitor.check()
        if self._revoked():
            raise Revoked("job_revoked")
        if self._expired():
            raise WorkerError("snapshot_expired")
        if time.monotonic() >= self.deadline:
            raise WorkerError("job_time_limit")

    def _physical(self):
        return {key: self.m1_total[key] if key in M1_COSTS else self.m3_total[key] for key in COSTS}

    def _progress(self, stage, completed, *, complete=False, phase_id=None):
        self.progress_stage, self.progress_completed = stage, completed
        self.progress_phase_id = phase_id or (self.phase["id"] if self.phase else None)
        current = self.store.get(self.job["id"])
        if current is None:
            return
        progress = dict(current.get("progress") or {})
        progress["staged_execution"] = {"strategy": STRATEGY, "stage": stage,
            "phase_id": self.progress_phase_id, "phase_completed_items": completed,
            "phase_total_items": len(self.rows), "cumulative_counters": self._physical(),
            "prelude_transfer_reuses": self.transfer_reuses, "cost_complete": complete,
            "cost_scope": "completed_job" if complete else "job_cumulative_lower_bound",
            "unacknowledged_attempts": 0 if complete else None}
        self.store.progress(self.job["id"], progress)

    def _event(self, event_type, /, **fields):
        self.monitor.emit("runtime_event", {"type": event_type, "logical_job_id": self.job["id"], **fields})

    def _phase_progress(self, response):
        self.m3_total = counters(response["cumulative_counters"])
        self.transfer_reuses = self.m3_total["m1_cache_hit"]
        self._event("staged_progress", phase_id=self.phase["id"], **{key: value for key, value in response.items() if key != "type"})
        self._progress("m3_replay", self.phase["completed_items"])

    def _start_phase(self, name):
        self._check()
        mode = "m1_only" if name == "m1" else self.job["mode"]
        phase_id = self.job["id"]+":"+name
        wait = {"phase_id": phase_id, "phase": name, "mode": mode,
                "started_monotonic": time.monotonic(), "status": "Waiting", "indices": []}
        self.monitor.set_phase(self.job["id"], None)
        self._event("quiet_started", **wait)
        self._progress("waiting_m1_quiet" if name == "m1" else "waiting_m3_quiet", 0, phase_id=phase_id)
        try:
            indices = self.monitor.wait_ready(self.deadline, self._transport_cancelled)
        except BaseException:
            wait.update(status="NotReady", ended_monotonic=time.monotonic())
            self._event("quiet_finished", **wait)
            raise
        wait.update(status="Ready", ended_monotonic=time.monotonic(), indices=indices)
        self._event("quiet_finished", **wait)
        self._check()
        self.phase = {"id": phase_id, "phase_id": phase_id, "phase": name, "mode": mode, "status": "running",
                      "total_items": len(self.rows), "completed_items": 0, "normal_exit": False, "cost_complete": False,
                      "started_monotonic": time.monotonic(), "readiness_indices": indices,
                      "readiness_started_monotonic": wait["started_monotonic"], "readiness_ended_monotonic": wait["ended_monotonic"]}
        self.phase_complete = False
        self.monitor.set_phase(self.job["id"], phase_id)
        self._event("phase_started", **self.phase)
        request = {"max_qwen_calls": 0 if name == "m1" else self.job["request"].get("max_qwen_calls", 20), "audit_rate": 0}
        phase_job = {"id": phase_id, "mode": mode, "request": request}
        try:
            self.active = self.phase_runner_factory(phase_job, lock_fd=self.lock_fd, cancelled=self._transport_cancelled,
                            deadline=self.deadline, monitor=self.monitor, logical_job_id=self.job["id"],
                            transfer=self.transfer if name == "m3" else None, on_progress=self._phase_progress)
        except BaseException as exc:
            owner = getattr(exc, "_staged_phase_runner", None)
            if owner is not None and owner.phase_id == phase_id:
                self.active = owner
            raise
        self._check()
        self._progress("m1_prepass" if name == "m1" else "m3_replay", 0)

    def _receipt(self, row, result):
        result = safe_result(result)
        self.monitor.observe_resources(result["resources"])
        payload = {"logical_job_id": self.job["id"], "phase_id": self.phase["id"],
                   "ordinal": row["ordinal"], "input_sha256": row["record"]["model_input_hash"], "result": result}
        self.monitor.emit("phase_receipt", payload)
        self.phase["completed_items"] += 1
        if self.phase["phase"] == "m1":
            if any(counters(result["counters"])[key] for key in COSTS if key not in M1_COSTS):
                raise WorkerError("unexpected_m1_prelude_cost")
            self.m1_total = counters(result["cumulative_counters"])
            self.receipt_events.append(payload)
        else:
            self.m3_total = counters(result["cumulative_counters"])
            self.transfer_reuses = self.m3_total["m1_cache_hit"]
        self._progress("m1_prepass" if self.phase["phase"] == "m1" else "m3_replay", self.phase["completed_items"])
        self._check()
        return result

    def _finish_phase(self):
        self._check()
        self.active.finish()
        self._check()
        boundary = self.monitor.samples[-1]["index"] if self.monitor.samples else -1
        observation = self.monitor.wait_absent(boundary, self.deadline)
        self._check()
        self.phase.update(status="completed", normal_exit=True, cost_complete=True,
                          exit_observation=observation, ended_monotonic=time.monotonic())
        self._event("phase_terminal", **self.phase)
        self.phase_complete = True
        self.active = None
        self.monitor.set_phase(self.job["id"], None)

    def _prepare(self):
        self._start_phase("m1")
        if self.job["mode"] == "m1_only":
            self.ready_for_outputs = True
            return
        for row in self.rows:
            self._check()
            result = self._receipt(row, self.active.predict(row["ordinal"], row["record"]))
            self.prelude.append(result)
        self._finish_phase()
        fingerprints = {row["fingerprint"] for row in self.prelude}
        if len(fingerprints) != 1:
            raise WorkerError("m1_fingerprint_drift")
        self.transfer = {"base_fingerprint": next(iter(fingerprints)), "entries": [
            {"ordinal": row["ordinal"], "input_sha256": row["record"]["model_input_hash"],
             "m1_probabilities": result["m1_probabilities"], "tokenlengths": {"m1": result["tokenlengths"]["m1"]}}
            for row, result in zip(self.rows, self.prelude)]}
        self.monitor.emit("transfer", {"logical_job_id": self.job["id"], "phase_id": self.job["id"]+":m3",
            "transfer": self.transfer, "transfer_sha256": digest(dumps(self.transfer)),
            "m1_receipts_sha256": digest("".join(dumps(row)+"\n" for row in self.receipt_events))})
        self._start_phase("m3")
        self.ready_for_outputs = True

    def _translate_failure(self, exc):
        metadata = dict(exc.metadata) if isinstance(exc, WorkerError) else {}
        if isinstance(metadata.get("cumulative_counters"), dict) and all(key in metadata["cumulative_counters"] for key in COSTS):
            raw = counters(metadata["cumulative_counters"])
            if self.phase and self.phase["phase"] == "m1": self.m1_total = raw
            else: self.m3_total = raw; self.transfer_reuses = raw["m1_cache_hit"]
            code = str(exc) if isinstance(exc, WorkerError) else "worker_failed"
            if not re.fullmatch(r"[a-z0-9_]{1,64}", code): code = "worker_failed"
            self._event("failure_cost", phase_id=self.phase["id"] if self.phase else None,
                        cumulative_counters=raw, error_code=code)
        self._progress(self.progress_stage, self.progress_completed, phase_id=self.progress_phase_id)
        cost = {"cumulative_counters": self._physical(), "cost_complete": False,
                "cost_scope": "job_cumulative_lower_bound", "prelude_transfer_reuses": self.transfer_reuses,
                "unacknowledged_attempts": None}
        try:
            self.close()
        except BaseException:
            # A failed cleanup must leave revocation pending, not publish a deletable terminal.
            self.store.transition(self.job["id"], ACTIVE, "cancel_requested", error_code="owned_process_exit_unconfirmed")
            raise CleanupPending("owned_process_exit_unconfirmed") from None
        if self.monitor.reason:
            raise WorkerError(self.monitor.reason, cost) from None
        if self._expired():
            raise WorkerError("snapshot_expired", cost) from None
        if isinstance(exc, Revoked):
            raise exc
        if isinstance(exc, WorkerError):
            code = str(exc)
            if code in BLOCKING_INFERENCE_CODES or code.startswith(("invalid_inference_", "invalid_ready_", "transfer_", "m1_cache_")) or any(part in code for part in ("resource_limit", "rss_limit", "telemetry_unavailable", "identity", "hash_mismatch", "fingerprint_drift")):
                self.monitor.block(code)
            raise WorkerError(code, cost) from None
        self.monitor.block("staged_internal_error")
        raise exc

    def predict(self, item_id, record):
        try:
            self._check()
            ordinal = int(item_id)
            if ordinal != self.output_ordinal or ordinal >= len(self.rows) or record != self.rows[ordinal]["record"]:
                raise WorkerError("staged_input_identity")
            if not self.ready_for_outputs:
                self._prepare()
            raw = self._receipt(self.rows[ordinal], self.active.predict(ordinal, record))
            if self.job["mode"] == "research" and raw.get("fallback"):
                raise WorkerError("research_fallback_forbidden")
            result = dict(raw)
            if self.job["mode"] != "m1_only":
                source = self.prelude[ordinal]
                if (raw.get("prelude_transfer_reuse") is not True or raw.get("m1_execution_origin") != "current_job_m1_receipt"
                        or raw["m1_probabilities"] != source["m1_probabilities"]
                        or raw["tokenlengths"]["m1"] != source["tokenlengths"]["m1"]):
                    raise WorkerError("staged_transfer_identity")
                first, second = counters(source["counters"]), counters(raw["counters"])
                result["staged_raw_counters"] = dict(raw["counters"])
                result["counters"] = {**raw["counters"], **{key: first[key] for key in M1_COSTS}}
                result["cumulative_counters"] = self._physical()
                result["staged_counter_scope"] = "physical_job_cumulative"
                result["cache_hit"] = bool(first["m1_cache_hit"] and (not raw["route_requested"] or second["m3_cache_hit"]))
                result["staged_latency_scope"] = "phase_response_only_m1_prepass_excluded"
            self.output_ordinal += 1
            return result
        except BaseException as exc:
            self._translate_failure(exc)

    def finish(self):
        try:
            self._check()
            if self.output_ordinal != len(self.rows):
                raise WorkerError("staged_output_incomplete")
            self._finish_phase()
            self._progress("completed", len(self.rows), complete=True)
            self._clear()
            self.closed = True
        except BaseException as exc:
            self._translate_failure(exc)

    def _clear(self):
        self.transfer = None
        self.prelude.clear()
        self.receipt_events.clear()
        self.rows.clear()

    def close(self):
        if self.closed:
            return
        if self.cleanup_error is not None:
            raise CleanupPending("owned_process_exit_unconfirmed") from None
        error = None
        if self.phase and not self.phase_complete:
            start = time.monotonic()
            boundary = self.monitor.samples[-1]["index"] if self.monitor.samples else -1
            cleanup = {"job_id": self.phase["id"], "phase": self.phase["phase"], "started_monotonic": start,
                       "max_seconds": 15, "terminal_confirmed": False, "models_absent_confirmed": False, "normal_exit": False}
            try:
                if self.active is not None:
                    self.active.close()
                cleanup["terminal_confirmed"] = (self.phase["id"] in getattr(self.monitor, "phase_exits", {})
                    or self.active is not None and (getattr(self.active, "exit_recorded", False)
                        or hasattr(self.active, "process") and self.active.process is None))
                cleanup["exit_observation"] = self.monitor.wait_absent(boundary, start+15)
                cleanup["models_absent_confirmed"] = True
            except BaseException as exc:
                self.monitor.block("owned_process_exit_unconfirmed")
                error = exc
            cleanup["ended_monotonic"] = time.monotonic()
            self.phase.update(status="cancelled" if self._revoked() else "failed", normal_exit=False,
                              cost_complete=False, cleanup=cleanup, ended_monotonic=time.monotonic())
            self._event("phase_terminal", **self.phase)
        if error is None:
            self.active = None
        self._clear()
        self.closed = error is None
        self.cleanup_error = error
        self.monitor.set_phase(None, None)
        if error is not None:
            raise CleanupPending("owned_process_exit_unconfirmed") from None


class StagedDispatcher(Dispatcher):
    runtime_strategy = STRATEGY

    def __init__(self, store, aggregate, fetch, runner_factory=None, *, deadline_seconds=3600,
                 observer=None, monitor_factory=SafetyMonitor):
        self.blocked_reason = None
        self.monitor = monitor_factory(store.private_dir, observer=observer, on_block=self._block)
        self.phase_runner_factory = StagedProcessRunner if runner_factory in (None, ProcessRunner) else runner_factory
        self.source_fetch = fetch
        super().__init__(store, aggregate, self._guarded_fetch, self._make_runner, deadline_seconds=deadline_seconds)

    def _block(self, reason):
        if self.blocked_reason is None:
            self.blocked_reason = reason

    def _make_runner(self, job, **kwargs):
        return StagedRunner(job, store=self.store, monitor=self.monitor, phase_runner_factory=self.phase_runner_factory, **kwargs)

    def _guarded_fetch(self, request, *, cancelled, progress):
        self.monitor.check()
        try:
            value = self.source_fetch(request, cancelled=lambda: bool(self.monitor.reason or cancelled()), progress=progress)
        except Exception:
            self.monitor.check()
            raise
        self.monitor.check()
        return value

    def _loop(self):
        try:
            self.monitor.start()
            last_purge = time.monotonic()
            while not self.stop_event.is_set():
                if self.blocked_reason or self.monitor.reason:
                    self.stop_event.wait(.2)
                    continue
                job = self.store.claim()
                if job:
                    if self.blocked_reason or self.monitor.reason:
                        self.store.transition(job["id"], job["state"], "queued")
                        continue
                    self.current_job = job["id"]
                    try:
                        self.run_job(job)
                    finally:
                        self.current_job = None
                else:
                    self.stop_event.wait(.2)
                if time.monotonic()-last_purge >= 3600:
                    self.store.purge()
                    last_purge = time.monotonic()
        except BaseException:
            self.monitor.block("staged_dispatcher_failed")

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=17)
            if self.thread.is_alive():
                self.monitor.block("dispatcher_shutdown_pending")
                raise WorkerError("dispatcher_shutdown_pending")
        self.monitor.finish()
        if self.lock:
            self.lock.close()
            self.lock = None
