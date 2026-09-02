"""Persistent in-memory safety observations for the serial staged dispatcher."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time

from .telemetry import system_memory
from .worker import Revoked, WorkerError

MIB = 1024**2


class SafetyError(WorkerError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def ps_command(arguments):
    return subprocess.run(arguments, capture_output=True, text=True, timeout=2, check=True,
                          env={**os.environ, "LC_ALL": "C"}).stdout


def parse_process_table(raw):
    rows = {}
    for line in raw.splitlines():
        fields = line.split(None, 8)
        if len(fields) != 9 or not all(value.isdigit() for value in fields[:3]):
            raise SafetyError("process_table_unknown")
        pid, ppid, rss = map(int, fields[:3])
        start = " ".join(fields[3:8])
        datetime.strptime(start, "%a %b %d %H:%M:%S %Y")
        if pid in rows:
            raise SafetyError("process_table_duplicate")
        rows[pid] = {"pid": pid, "ppid": ppid, "current_rss_bytes": rss*1024,
                     "start_time": start, "process_key": f"{pid}|{start}",
                     "comm": Path(fields[8]).name, "raw": line}
    return rows


def process_identity(pid, command=ps_command):
    rows = parse_process_table(command(["/bin/ps", "-p", str(pid), "-o", "pid=,ppid=,rss=,lstart=,comm="]))
    if pid not in rows:
        raise SafetyError("process_birth_unobserved")
    return {key: value for key, value in rows[pid].items() if key != "raw"}


def process_snapshot(service, seen, command=ps_command):
    """Discard non-owned rows; retain all known live identities, even renamed ones."""
    result = {"status": "unknown", "parent": None, "models": [], "tracked_other": [],
              "inference_workers": [], "auxiliary_processes": [], "orphan_models": [],
              "seen_model_keys": sorted(seen), "absent_model_keys": [], "selected_ps": []}
    try:
        table = parse_process_table(command(["/bin/ps", "-axo", "pid=,ppid=,rss=,lstart=,comm="]))
        parent = table.get(service["pid"])
        if parent is None or any(parent[key] != service[key] for key in ("process_key", "comm")):
            raise SafetyError("service_identity_drift")
        owned = {parent["pid"]}
        while True:
            extra = {pid for pid, row in table.items() if row["ppid"] in owned}-owned
            if not extra:
                break
            owned.update(extra)
        models = [row for pid, row in table.items() if pid in owned and pid != parent["pid"] and row["comm"].lower().startswith("python")]
        seen = set(seen) | {row["process_key"] for row in models}
        current = {row["process_key"]: row for row in table.values()}
        model_keys = {row["process_key"] for row in models}
        tracked = [current[key] for key in sorted(seen) if key in current and current[key]["pid"] in owned and key not in model_keys]
        orphans = [current[key] for key in sorted(seen) if key in current and current[key]["pid"] not in owned]
        retained = [*models, *tracked]
        live = {row["process_key"] for row in [*retained, *orphans]}
        absent = seen-set(current)
        if live & absent or live | absent != seen or len(live) != len(retained)+len(orphans):
            raise SafetyError("process_partition_unknown")
        clean = lambda row: {key: value for key, value in row.items() if key != "raw"}
        result.update(status="observed", parent=clean(parent), models=[clean(row) for row in models],
                      tracked_other=[clean(row) for row in tracked], orphan_models=[clean(row) for row in orphans],
                      inference_workers=[clean(row) for row in retained if row["ppid"] == parent["pid"]],
                      auxiliary_processes=[clean(row) for row in retained if row["ppid"] != parent["pid"]],
                      seen_model_keys=sorted(seen), absent_model_keys=sorted(absent),
                      selected_ps=[row["raw"] for row in [parent, *retained, *orphans]])
    except Exception:
        result["error_type"] = "ProcessObservationUnknown"
    return result


def swap_rate(first, last):
    a, b = first["system"], last["system"]
    if a.get("status") != "observed" or b.get("status") != "observed":
        return None
    dt = b["monotonic"]-a["monotonic"]
    if not 0 < dt <= 3 or a["page_size"] != b["page_size"]:
        return None
    incoming, outgoing = b["swapins"]-a["swapins"], b["swapouts"]-a["swapouts"]
    return None if min(incoming, outgoing) < 0 else (incoming+outgoing)*b["page_size"]/dt


def safety_reason(samples):
    row = samples[-1]
    system, processes = row["system"], row["processes"]
    if system.get("status") != "observed" or processes.get("status") != "observed":
        return "monitoring_unknown"
    if system["pressure_level"] == 4:
        return "critical_memory_pressure"
    if processes["orphan_models"]:
        return "owned_orphan_detected"
    owned = [*processes["models"], *processes["tracked_other"]]
    if sum(row["ppid"] == processes["parent"]["pid"] for row in owned) > 1:
        return "concurrent_model_processes"
    if processes["parent"]["current_rss_bytes"] > 1024*MIB:
        return "parent_rss_limit"
    if any(row["current_rss_bytes"] > 12*1024*MIB for row in [*owned, *processes["orphan_models"]]):
        return "child_rss_limit"
    if type(row.get("disk_free_bytes")) is not int or row["disk_free_bytes"] < 512*MIB:
        return "disk_budget_exceeded"
    if len(samples) > 1 and swap_rate(samples[-2], samples[-1]) is None:
        return "system_interval_unknown"
    if len(samples) >= 4:
        rates = [swap_rate(a, b) for a, b in zip(samples[-4:-1], samples[-3:])]
        if any(rate is None for rate in rates):
            return "system_interval_unknown"
        if all(rate >= 100*MIB for rate in rates):
            return "swap_thrashing"
    return None


class SafetyMonitor:
    def __init__(self, private_dir, *, observer=None, on_block=None, system=system_memory,
                 command=ps_command, clock=time.monotonic, service=None, disk_free=None, history_limit=120):
        self.private_dir = Path(private_dir)
        self.observer, self.on_block = observer, on_block
        self.system, self.command, self.clock = system, command, clock
        self.service = service
        self.disk_free = disk_free or (lambda: shutil.disk_usage(self.private_dir).free)
        self.samples = deque(maxlen=max(16, history_limit))
        self.seen, self.unknown_births = set(), set()
        self.reason = None
        self.logical_job_id = self.phase_id = None
        self.index = 0
        self.last_absence = None
        self.phase_exits = {}
        self.stopped = threading.Event()
        self.updated = threading.Condition(threading.RLock())
        self.thread = None

    def block(self, reason):
        if not isinstance(reason, str) or not re.fullmatch(r"[a-z0-9_]{1,64}", reason):
            reason = "staged_safety_failed"
        with self.updated:
            if self.reason is None:
                self.reason = reason
                if self.on_block:
                    try:
                        self.on_block(reason)
                    except Exception:
                        pass
            self.updated.notify_all()

    def emit(self, kind, payload):
        if self.observer is None:
            return
        if kind not in {"sample", "process_event", "phase_receipt", "transfer", "runtime_event"}:
            self.block("observer_schema_error")
            return
        try:
            # Isolate callbacks from retained mutable state and reject nonfinite values.
            safe = json.loads(json.dumps(payload, ensure_ascii=False, allow_nan=False))
            self.observer(kind, safe)
        except Exception:
            self.block("observer_callback_failed")

    def set_phase(self, logical_job_id, phase_id):
        with self.updated:
            self.logical_job_id, self.phase_id = logical_job_id, phase_id

    def identify(self, pid, *, not_before):
        try:
            identity = process_identity(pid, self.command)
        except Exception:
            with self.updated:
                for sample in reversed(self.samples):
                    if sample["started_monotonic"] < not_before:
                        continue
                    p = sample["processes"]
                    for row in [*p.get("models", []), *p.get("tracked_other", []), *p.get("orphan_models", [])]:
                        if row["pid"] == pid and row["ppid"] == self.service["pid"]:
                            return row
            raise SafetyError("process_birth_unobserved") from None
        if identity["ppid"] != self.service["pid"]:
            raise SafetyError("process_parent_identity")
        return identity

    def process_event(self, kind, logical_job_id, phase_id, *, pid=None, process_key=None, returncode=None, normal_exit=False, ready=None):
        event = {"type": kind, "logical_job_id": logical_job_id, "phase_id": phase_id, "job_id": phase_id,
                 "pid": pid, "process_key": process_key, "returncode": returncode,
                 "normal_exit": normal_exit, "monotonic": self.clock(), "at": now()}
        if ready is not None:
            event["ready"] = ready
        with self.updated:
            if pid is not None:
                if process_key is None:
                    self.unknown_births.add(pid)
                    self.block("process_birth_unobserved")
                else:
                    self.seen.add(process_key)
            if kind == "process_exit":
                self.phase_exits[phase_id] = dict(event)
            self.emit("process_event", event)
            self.updated.notify_all()

    def observe_resources(self, resources):
        if (not isinstance(resources, dict)
                or any(type(resources.get(key)) is not int or resources[key] < 0 for key in ("peak_rss_bytes", "mlx_peak_bytes"))
                or type(resources.get("elapsed_seconds")) not in (int, float)
                or not math.isfinite(resources["elapsed_seconds"]) or resources["elapsed_seconds"] < 0):
            self.block("model_resource_unknown")
        elif resources["peak_rss_bytes"] > 12*1024*MIB or resources["mlx_peak_bytes"] > 10_000_000_000:
            self.block("resource_limit_exceeded")

    def check(self):
        if self.reason:
            raise SafetyError(self.reason)
        if self.samples and self.clock()-self.samples[-1]["monotonic"] > 3:
            self.block("monitor_sample_stale")
            raise SafetyError(self.reason)

    def sample_once(self):
        started = self.clock()
        system = self.system()
        with self.updated:
            seen = set(self.seen)
            phase_id, logical = self.phase_id, self.logical_job_id
        processes = process_snapshot(self.service, seen, self.command)
        with self.updated:
            if self.unknown_births:
                processes.update(status="unknown", error_type="UnobservedBirthIdentity")
            row = {"index": self.index, "job_id": phase_id, "logical_job_id": logical,
                   "started_monotonic": started, "system": system, "processes": processes,
                   "disk_free_bytes": self.disk_free(), "monotonic": self.clock(), "sampled_at": now()}
            self.index += 1
            self.seen.update(processes["seen_model_keys"])
            self.samples.append(row)
            reason = safety_reason(list(self.samples))
            if reason:
                self.block(reason)
            self.emit("sample", row)
            self.updated.notify_all()
        return row

    def _loop(self):
        try:
            while not self.stopped.is_set():
                self.sample_once()
                self.stopped.wait(1.0)
        except Exception:
            self.block("monitoring_failed")

    def start(self):
        if self.thread is not None:
            return
        self.service = self.service or process_identity(os.getpid(), self.command)
        self.emit("runtime_event", {"type": "monitor_started", "service": self.service, "monotonic": self.clock()})
        self.thread = threading.Thread(target=self._loop, name="topicweb-staged-monitor", daemon=True)
        self.thread.start()
        with self.updated:
            self.updated.wait_for(lambda: bool(self.samples) or self.reason, timeout=7)
        if not self.samples:
            self.block("monitor_start_timeout")
        self.check()

    def wait_ready(self, deadline, cancelled=lambda: False, timeout=60):
        boundary = self.samples[-1]["index"] if self.samples else -1
        end = min(deadline, self.clock()+timeout)
        while self.clock() < end:
            self.check()
            if cancelled():
                raise Revoked("job_revoked")
            with self.updated:
                rows = [row for row in self.samples if row["index"] > boundary]
                rows = rows[-10:]
                if len(rows) == 10:
                    quiet = all(row["system"].get("status") == "observed" and row["system"]["pressure_level"] == 1
                                and row["processes"].get("status") == "observed" and not row["processes"]["models"]
                                and not row["processes"]["tracked_other"] and not row["processes"]["orphan_models"]
                                and set(row["processes"]["seen_model_keys"]) == set(row["processes"]["absent_model_keys"]) for row in rows)
                    rates = [swap_rate(a, b) for a, b in zip(rows, rows[1:])]
                    if quiet and all(rate is not None and rate < 10*MIB for rate in rates):
                        return [row["index"] for row in rows]
                self.updated.wait(timeout=min(.2, max(0, end-self.clock())))
        self.block("quiet_window_not_ready")
        raise SafetyError(self.reason)

    def wait_absent(self, after_index, deadline, timeout=15):
        end = min(deadline, self.clock()+timeout)
        while self.clock() < end:
            with self.updated:
                if self.samples:
                    row = self.samples[-1]
                    p = row["processes"]
                    if (row["index"] > after_index and p.get("status") == "observed" and not self.unknown_births
                            and not p["models"] and not p["tracked_other"] and not p["orphan_models"]
                            and set(p["seen_model_keys"]) == set(p["absent_model_keys"])
                            and self.seen <= set(p["absent_model_keys"]) and self.clock()-row["monotonic"] <= 3):
                        self.last_absence = {"sample_index": row["index"], "absent_model_keys": p["absent_model_keys"]}
                        return dict(self.last_absence)
                self.updated.wait(timeout=min(.2, max(0, end-self.clock())))
        self.block("owned_process_exit_unconfirmed")
        raise SafetyError(self.reason)

    def finish(self):
        if self.thread is None:
            return
        error = None
        observation = None
        try:
            initial = self.samples[-1]["index"] if self.samples else -1
            observation = self.wait_absent(initial, self.clock()+15)
        except Exception as exc:
            error = exc
        finally:
            self.stopped.set()
            self.thread.join(timeout=7)
        if self.thread.is_alive():
            self.block("monitor_shutdown_timeout")
            error = SafetyError(self.reason)
        self.emit("runtime_event", {"type": "monitor_terminal", "monotonic": self.clock(),
                                    "seen_process_keys": sorted(self.seen), "all_seen_absent": error is None,
                                    "exit_observation": observation, "blocked_reason": self.reason})
        if error is not None:
            raise error
