"""EXP-085: HTTP acceptance of the sequential M1/M3 website runtime."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import sys
import tarfile
import threading
import time
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
ATTEMPT = 2
RUN = ROOT / "private/validation/exp-085/attempt-2"
PARENT = ROOT / "private/validation/exp-084/attempt-1"
PREVIOUS = ROOT / "private/validation/exp-085/attempt-1"
PARENT_HASHES = {
    "plan": "24c1c85d7aadb8a77743203972df4652c1204f2f626ec8f2c6182116e731338f",
    "run": "e97540cec9a2cf87bdfe22f99c06a979c50d54603702b260a5a30551ad591d2a",
    "verification": "22e667dd23da182b40e5fbb876999ac7465682275258e10a8663640bf4041bd1",
}
PROTOCOL = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-085-staged-website-bounded-acceptance-attempt-2.md"
ARCHIVE_SHA256 = "91ed8d8b0d8d8b631c7ad440cc824cd7dde813c0dc6f997bb1b8839dbef751af"
PREVIOUS_HASHES = {
    "plan": "9de78c110ef9a078025df831138e5acd63d08a596e7c972d5bd13d52f04aec25",
    "run": "b9965aaa8340212a3e49b3d1290febe962c402aeb3e31de97a10dc336f7d4686",
    "verification": "426c3ba406ca42b13942275b8d87384a8e8e9fa71fc9629739ec6b1a0f75bf2f",
}
PREVIOUS_ARCHIVE_SHA256 = "76664bc9b6d532e2fc0e81a7b169d25d512f32a72380cd5982e4360c9ce49733"
SOURCE_JOB = "5ab3326150ee448ba326233264967d34"
SOURCE_SNAPSHOT = "cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16"
SOURCE_LOGICAL = "8c0cc285ff71fd041eb832d5a8422d68dcaad84228a9c3b00d14f213dacd17a4"
MODES = ("m1_only", "research", "demo")
BUDGETS = {"m1_only": 0, "research": 500, "demo": 20}
JOURNALS = {"sample": "samples.jsonl", "process_event": "process-events.jsonl", "phase_receipt": "phase-receipts.jsonl",
            "transfer": "transfers.jsonl", "runtime_event": "runtime-events.jsonl"}
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def once(path, value):
    require(not any(part.is_symlink() for part in (path, *path.parents)), "artifact_path_symlink")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        output.flush()
        os.fsync(output.fileno())


def sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def require(value, code):
    if not value:
        raise ValueError(code)


def regular(path):
    require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), "unsafe_file")
    return path.read_bytes()


def parent_documents():
    values = {}
    for name, expected in PARENT_HASHES.items():
        raw = regular(PARENT / (name + ".json"))
        require(sha(raw) == expected, "parent_artifact_drift")
        values[name] = json.loads(raw)
    require(values["verification"]["status"] == "Passed"
            and values["verification"]["diagnostic_completed"] is True
            and values["verification"]["safety"]["gate_passed"] is True, "parent_not_verified")
    return values


def archive_parent():
    """Create-only snapshot before changing production dependencies of EXP-084."""
    documents = parent_documents()
    bindings = documents["plan"]["sources"]
    require(len(bindings) == 39, "parent_source_count")
    content = {}
    for name, expected in bindings.items():
        path = ROOT / name
        require(path.resolve().is_relative_to(ROOT) and ".." not in Path(name).parts, "source_path")
        raw = regular(path)
        require(sha(raw) == expected, "parent_source_drift")
        content[name] = raw
    protocol = documents["plan"]["protocol"]
    content["protocol.md"] = regular(ROOT.parent / protocol["path"])
    require(sha(content["protocol.md"]) == protocol["sha256"], "parent_protocol_drift")
    target = PARENT / "frozen-code.tar.gz"
    require(not target.exists() and not target.is_symlink(), "archive_already_exists")
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            for name, raw in sorted(content.items()):
                entry = tarfile.TarInfo(name)
                entry.size, entry.mode = len(raw), 0o600
                archive.addfile(entry, io.BytesIO(raw))
        stream.flush()
        os.fsync(stream.fileno())
    with tarfile.open(target, "r:gz") as archive:
        require(set(archive.getnames()) == set(content), "archive_members")
        for entry in archive:
            require(entry.isfile() and archive.extractfile(entry).read() == content[entry.name], "archive_payload")
    return {"path": str(target), "members": len(content), "sha256": sha(regular(target))}


def previous_attempt_documents():
    documents, bindings = {}, {}
    for name, expected_sha in PREVIOUS_HASHES.items():
        path = PREVIOUS / (name + ".json")
        raw = regular(path)
        require(sha(raw) == expected_sha, "previous_attempt_artifact_drift")
        documents[name] = json.loads(raw)
        bindings[name] = {"path": str(path.relative_to(ROOT)), "sha256": expected_sha}
    require(documents["run"].get("attempt") == 1 and documents["run"].get("status") == "Stopped"
            and documents["run"].get("failure_code") == "staged_internal_error", "previous_attempt_run_terminal")
    verification = documents["verification"]
    require(verification.get("attempt") == 1 and verification.get("status") == "Failed"
            and verification.get("error_code") == "staged_lower_bound_range"
            and verification.get("exp085_complete") is False
            and verification.get("operational_state") == "stop-required", "previous_attempt_verification_terminal")
    path = PREVIOUS / "frozen-code.tar.gz"
    require(sha(regular(path)) == PREVIOUS_ARCHIVE_SHA256, "previous_attempt_archive_drift")
    expected = {**documents["plan"]["sources"], "protocol.md": documents["plan"]["protocol"]["sha256"]}
    require(len(documents["plan"]["sources"]) == 32 and len(expected) == 33, "previous_attempt_source_count")
    total = 0
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        require(len(members) == 33 and len({member.name for member in members}) == 33
                and {member.name for member in members} == set(expected), "previous_attempt_archive_members")
        for member in members:
            require(member.isfile() and 0 <= member.size <= 2 * 1024**2
                    and not Path(member.name).is_absolute() and ".." not in Path(member.name).parts,
                    "previous_attempt_archive_member")
            total += member.size
            stream = archive.extractfile(member)
            require(total <= 32 * 1024**2 and stream is not None
                    and sha(stream.read()) == expected[member.name], "previous_attempt_archive_payload")
    require(sha(regular(path)) == PREVIOUS_ARCHIVE_SHA256, "previous_attempt_archive_drift")
    bindings["archive"] = {"path": str(path.relative_to(ROOT)), "sha256": PREVIOUS_ARCHIVE_SHA256, "members": 33}
    return bindings


def verify_parent_archive(documents):
    path = PARENT / "frozen-code.tar.gz"
    require(sha(regular(path)) == ARCHIVE_SHA256, "parent_archive_identity")
    expected = {**documents["plan"]["sources"], "protocol.md": documents["plan"]["protocol"]["sha256"]}
    with tarfile.open(path, "r:gz") as archive:
        entries = archive.getmembers()
        require(len(entries) == 40 and len(entries) == len(expected)
                and {entry.name for entry in entries} == set(expected), "parent_archive_members")
        for entry in entries:
            require(entry.isfile() and sha(archive.extractfile(entry).read()) == expected[entry.name], "parent_archive_payload")
    for name, expected_sha in documents["verification"]["source_hashes"].items():
        require(name.startswith("private/validation/exp-084/attempt-1/") and ".." not in Path(name).parts
                and sha(regular(ROOT / name)) == expected_sha, "parent_artifact_drift")
    return {"path": str(path.relative_to(ROOT)), "sha256": ARCHIVE_SHA256, "members": 40}


def source_input(database):
    from run_soak import read_job
    job, rows = read_job(database, SOURCE_JOB)
    require(job["state"] == "completed" and job["snapshot_hash"] == SOURCE_SNAPSHOT and job["total_items"] == 340,
            "source_job_identity")
    require(len(rows) == 340 and [row["ordinal"] for row in rows] == list(range(340))
            and sha(canonical([row["record"] for row in rows])) == SOURCE_SNAPSHOT
            and sha(canonical(rows)) == SOURCE_LOGICAL, "source_snapshot_identity")
    metadata, payload = [], []
    for row in rows:
        text = row["record"]["model_input_text"]
        eligible = row["result"]["hypothetical_route"]
        require(isinstance(text, str) and 0 < len(text.encode()) <= 65536
                and sha(text) == row["record"]["model_input_hash"] and type(eligible) is bool, "source_input_identity")
        metadata.append({"ordinal": row["ordinal"], "input_sha256": sha(text), "route_eligible": eligible})
        payload.append(canonical({"id": f"source-{row['ordinal']}", "text": text}))
    require(len({row["input_sha256"] for row in metadata}) == 338
            and sum(row["route_eligible"] for row in metadata) == 25
            and len({row["input_sha256"] for row in metadata if row["route_eligible"]}) == 25, "source_group_identity")
    content = "\n".join(payload) + "\n"
    require(len(content.encode()) <= 5 * 1024**2, "payload_budget")
    return metadata, content


def dependencies():
    from bounded_runtime_support import PRODUCTION_DEPENDS
    return tuple(PRODUCTION_DEPENDS) + (
        "topicweb/staged_inference.py", "topicweb/staged_safety.py", "topicweb/staged_worker.py", "topicweb/staged_app.py",
        "tests/test_staged_inference.py", "tests/test_staged_safety.py", "tests/test_staged_worker.py", "tests/test_staged_app.py",
        "tests/test_staged_integration.py",
        "scripts/run_soak.py", "scripts/bounded_runtime_support.py", "scripts/verify_bounded_runtime.py",
        "scripts/verify_local.py", "scripts/verify_discourse_validation.py",
        "scripts/run_staged_runtime.py", "scripts/verify_staged_runtime.py", "tests/test_staged_runtime.py", "tests/test_verify_staged_runtime.py",
    )


def prepare():
    from run_soak import environment_metadata
    documents = parent_documents()
    archive = verify_parent_archive(documents)
    previous_attempt = previous_attempt_documents()
    source_rows, content = source_input(ROOT / "private/jobs.sqlite3")
    environment = environment_metadata()
    model_config = environment["model_config"]
    raw_config = regular(ROOT.parent / model_config["path"])
    require(sha(raw_config) == model_config["sha256"], "model_config_identity")
    assets = json.loads(raw_config)["runtime_assets"]
    plan = {"experiment_id": "EXP-085", "attempt": ATTEMPT, "tier": "Major", "rq": "RQ-S3", "rounds": 3,
            "modes": list(MODES), "budgets": BUDGETS, "planned_jobs": 9, "planned_events": 3060,
            "events_per_job": 340, "max_seconds": 1800, "work_seconds": 1770, "cleanup_seconds": 15,
            "runtime_environment": {"TOPICWEB_TELEMETRY": "1"},
            "audit_rate": 0, "seed": 42, "port": 8789, "source_job": SOURCE_JOB,
            "source_snapshot_sha256": SOURCE_SNAPSHOT, "source_logical_sha256": SOURCE_LOGICAL,
            "source_rows": source_rows, "payload_sha256": sha(content), "payload_bytes": len(content.encode()),
            "parent_bindings": {name: {"path": str((PARENT / (name + '.json')).relative_to(ROOT)), "sha256": digest}
                                for name, digest in PARENT_HASHES.items()}, "parent_archive": archive,
            "previous_attempt": previous_attempt,
            "sources": {name: sha(regular(ROOT / name)) for name in dependencies()},
            "protocol": {"path": str(PROTOCOL.relative_to(ROOT.parent)), "sha256": sha(regular(PROTOCOL))},
            "model_config": model_config,
            "router_assets": {name: assets[name] for name in ("bundle_manifest", "bundle_parameters")},
            "reference_bindings": documents["plan"]["reference_bindings"],
            "parent_replay_results": {"path": str((PARENT / "replay-results.jsonl").relative_to(ROOT)),
                                      "sha256": documents["verification"]["source_hashes"][str((PARENT / "replay-results.jsonl").relative_to(ROOT))]}}
    return plan, content, environment


class Journal:
    """One create-only metadata observer, shared by dispatcher and sampler."""
    def __init__(self, directory):
        self.directory = directory
        self.lock = threading.RLock()
        self.streams = {}
        for kind, name in {**JOURNALS, "stdout": "stdout.log"}.items():
            fd = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            self.streams[kind] = os.fdopen(fd, "w")
        self.phases, self.last_sample, self.counts = {}, None, {kind: 0 for kind in JOURNALS}
        self.model_failure = None
        self.monitor_terminal = None
        self.closed = False

    def _write(self, kind, value):
        output = self.streams[kind]
        output.write(canonical(value) + "\n")
        output.flush()
        os.fsync(output.fileno())

    def report(self, value):
        with self.lock:
            self._write("stdout", value)
            print(canonical(value), flush=True)

    def __call__(self, kind, payload):
        require(kind in JOURNALS and isinstance(payload, dict), "observer_schema")
        with self.lock:
            require(not self.closed, "observer_already_closed")
            self._write(kind, payload)
            self.counts[kind] += 1
            if kind == "sample":
                self.last_sample = payload
            elif kind == "runtime_event" and payload.get("type") in {"phase_started", "phase_terminal"}:
                self.phases[payload["id"]] = {key: value for key, value in payload.items() if key != "type"}
                self.report({key: payload[key] for key in ("type", "logical_job_id", "phase_id", "phase", "status", "completed_items")})
            elif kind == "phase_receipt" and ((payload["ordinal"] + 1) % 50 == 0 or payload["ordinal"] == 339):
                self.report({"type": "phase_progress", "logical_job_id": payload["logical_job_id"],
                             "phase_id": payload["phase_id"], "completed_items": payload["ordinal"] + 1})
            if kind == "phase_receipt" and payload["result"].get("fallback_reason") not in (None, "m3_budget_exhausted"):
                self.model_failure = "nonbudget_model_fallback"
            if kind == "runtime_event" and payload.get("type") == "monitor_terminal":
                self.monitor_terminal = payload

    def snapshot(self):
        with self.lock:
            return json.loads(canonical({"phases": list(self.phases.values()), "counts": self.counts,
                                         "last_sample": self.last_sample, "monitor_terminal": self.monitor_terminal}))

    def close(self):
        with self.lock:
            for output in self.streams.values():
                output.close()
            self.closed = True


class RunFailure(RuntimeError):
    pass


def run_check(condition, code):
    if not condition:
        raise RunFailure(code)


class HTTP:
    def __init__(self, bench):
        token_path = bench / "access-token"
        self.token = regular(token_path).decode().strip()
        require(token_path.stat().st_mode & 0o077 == 0 and len(self.token) >= 32, "token_identity")

    def __call__(self, path, payload=None, timeout=10):
        request = Request("http://127.0.0.1:8789/api/" + path,
                          data=canonical(payload).encode() if payload is not None else None,
                          headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        with urlopen(request, timeout=max(.01, timeout)) as response:
            return json.load(response)


def submission_matches(job, expected, payload_hash):
    return (isinstance(job, dict) and isinstance(job.get("id"), str)
            and re.fullmatch(r"[a-f0-9]{32}", job["id"]) is not None
            and job.get("name") == expected["name"] and job.get("source") == "upload"
            and job.get("mode") == expected["mode"] and job.get("total_items") == 340
            and isinstance(job.get("manifest"), dict)
            and job["manifest"].get("file_sha256") == payload_hash
            and job["manifest"].get("filename") == "exp085-snapshot.jsonl")


def recover_submission(known, observed, expected, payload_hash):
    candidates = [job for job in observed if job.get("id") not in known]
    return candidates[0] if len(candidates) == 1 and submission_matches(candidates[0], expected, payload_hash) else None


def execute_jobs(api, journal, content, plan, deadline, directory, *, blocked=lambda: None, interrupted=lambda: False,
                 identity_check=lambda: None):
    jobs, current, pending, failure, cleanup = [], None, None, None, None
    blocked_reason = None
    def check_blocked():
        nonlocal blocked_reason
        reason = blocked()
        if reason:
            blocked_reason = reason if isinstance(reason, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,95}", reason) else "dispatcher_safety_stopped"
            if current is not None:
                jobs[-1]["blocked_reason"] = blocked_reason
            raise RunFailure(blocked_reason)
    try:
        for round_index in range(1, 4):
            for mode in MODES:
                run_check(not interrupted(), "run_interrupted")
                run_check(time.monotonic() < deadline, "run_time_limit")
                check_blocked()
                identity_check()
                expected = {"name": f"EXP-085 round {round_index} {mode}", "mode": mode}
                request = {**expected, "source": "upload", "audit_rate": 0, "max_qwen_calls": BUDGETS[mode],
                           "upload": {"content": content, "format": "jsonl", "filename": "exp085-snapshot.jsonl", "text_column": "text"}}
                known = {job["id"] for job in api("jobs", timeout=max(.01, min(10, deadline-time.monotonic())))["jobs"]}
                run_check(not interrupted(), "run_interrupted")
                run_check(time.monotonic() < deadline, "run_time_limit")
                check_blocked()
                entry = {"id": None, "round": round_index, "mode": mode, "budget": BUDGETS[mode], "status": "submission_pending",
                         "started_monotonic": time.monotonic(), "http_submission_acknowledged": False, "phase_ids": []}
                jobs.append(entry)
                pending = (known, expected, entry)
                job = api("jobs", request, timeout=max(.01, min(10, deadline-time.monotonic())))["job"]  # One POST; no replay.
                run_check(submission_matches(job, expected, plan["payload_sha256"]), "submitted_job_identity")
                current = job["id"]
                pending = None
                entry.update(id=current, http_submission_acknowledged=True, snapshot_hash=job["snapshot_hash"])
                journal.report({"type": "logical_job_started", "round": round_index, "mode": mode, "id": current})
                while True:
                    run_check(not interrupted(), "run_interrupted")
                    run_check(time.monotonic() < deadline, "run_time_limit")
                    check_blocked()
                    run_check(journal.model_failure is None, journal.model_failure or "nonbudget_model_fallback")
                    job = api("jobs/" + current, timeout=max(.01, min(10, deadline-time.monotonic())))["job"]
                    entry.update(status=job["state"], total_items=job["total_items"], completed_items=job["completed_items"],
                                 error_code=job.get("error_code"), snapshot_hash=job["snapshot_hash"])
                    if job["state"] in {"completed", "completed_with_fallback", "failed", "cancelled", "deleted"}:
                        break
                    time.sleep(.25)
                run_check(job["state"] == ("completed_with_fallback" if mode == "demo" else "completed")
                          and job["completed_items"] == job["total_items"] == 340, "logical_job_not_complete")
                run_check(time.monotonic() < deadline, "run_time_limit")
                dashboard = api("jobs/" + current + "/dashboard", timeout=max(.01, min(10, deadline-time.monotonic())))
                path = directory / "dashboards" / (current + ".json")
                once(path, dashboard)
                entry.update(ended_monotonic=time.monotonic(), dashboard_path=str(path.relative_to(ROOT)), api_dashboard_observed=True)
                journal.report({"type": "logical_job_completed", "round": round_index, "mode": mode, "id": current, "completed_items": 340})
                current = None
    except BaseException as error:
        failure = str(error) if isinstance(error, RunFailure) else "run_interrupted" if isinstance(error, (KeyboardInterrupt, SystemExit)) else "http_acceptance_failed"
        if pending is not None:
            known, expected, entry = pending
            try:
                recovered = recover_submission(known, api("jobs", timeout=3)["jobs"], expected, plan["payload_sha256"])
            except BaseException:
                recovered = None
            if recovered is not None:
                current = recovered["id"]
                entry.update(id=current, status=recovered["state"], recovered_for_cancellation_only=True,
                             snapshot_hash=recovered["snapshot_hash"], total_items=recovered["total_items"], completed_items=recovered["completed_items"])
            else:
                entry.update(status="submission_unconfirmed", submission_recovery_confirmed=False)
        if current is not None:
            started = time.monotonic()
            cleanup = {"id": current, "started_monotonic": started, "max_seconds": 15, "terminal_confirmed": False}
            try:
                end = min(deadline + 15, started + 15)
                api("jobs/" + current + "/cancel", {}, timeout=max(.01, min(3, end-time.monotonic())))
                while time.monotonic() < end:
                    job = api("jobs/" + current, timeout=max(.01, min(3, end-time.monotonic())))["job"]
                    if job["state"] in {"completed", "completed_with_fallback", "failed", "cancelled", "deleted"}:
                        cleanup["terminal_confirmed"] = True
                        jobs[-1].update(status=job["state"], completed_items=job["completed_items"], total_items=job["total_items"],
                                        error_code=job.get("error_code"), ended_monotonic=time.monotonic())
                        break
                    time.sleep(.1)
            except BaseException:
                cleanup["error_code"] = "http_cancel_unconfirmed"
            cleanup["ended_monotonic"] = time.monotonic()
            if cleanup["terminal_confirmed"] and not jobs[-1].get("dashboard_path"):
                try:
                    remaining = deadline + 30 - time.monotonic()
                    run_check(remaining > 0, "partial_dashboard_deadline")
                    dashboard = api("jobs/" + current + "/dashboard", timeout=min(3, remaining))
                    path = directory / "dashboards" / (current + ".json")
                    once(path, dashboard)
                    jobs[-1].update(dashboard_path=str(path.relative_to(ROOT)), api_dashboard_observed=True)
                except BaseException:
                    jobs[-1].update(api_dashboard_observed=False, api_dashboard_error="partial_dashboard_unavailable")
    return {"logical_jobs": jobs, "failure_code": failure, "initial_failure_code": failure,
            "blocked_reason": blocked_reason, "cleanup": cleanup}


def start_server(journal, bench, deadline):
    import uvicorn
    from topicweb.staged_app import create_app
    def no_source_network(*args, **kwargs):
        raise RunFailure("source_network_forbidden")
    app = create_app(private_dir=bench, observer=journal, fetch=no_source_network)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8789, access_log=False,
                                         log_level="error", timeout_graceful_shutdown=15))
    failures = []
    def serve():
        try:
            server.run()
        except BaseException:
            failures.append("http_server_failed")
    thread = threading.Thread(target=serve, name="exp085-http-server", daemon=False)
    thread.start()
    end = min(deadline, time.monotonic() + 20)
    while not server.started and thread.is_alive() and time.monotonic() < end:
        time.sleep(.05)
    if not server.started or failures:
        shutdown = stop_server(app, server, thread, min(deadline + 30, time.monotonic() + 20), journal)
        error = RunFailure("http_server_start_failed")
        error.shutdown = shutdown
        raise error
    return app, server, thread


def stop_server(app, server, thread, total_deadline, journal=None):
    started = time.monotonic()
    # Shutdown cancellation overlaps server lifespan cleanup; never start another worker.
    app.state.dispatcher.stop_event.set()
    server.should_exit = True
    thread.join(timeout=min(20, max(0, total_deadline - time.monotonic())))
    dispatcher = app.state.dispatcher
    monitor = getattr(dispatcher, "monitor", None)
    stopped = not thread.is_alive() and not (dispatcher.thread and dispatcher.thread.is_alive())
    monitor_thread = getattr(monitor, "thread", None)
    monitor_stopped = monitor_thread is None or not monitor_thread.is_alive()
    seen = set(getattr(monitor, "seen", ()))
    process = getattr(getattr(monitor, "current_runner", None), "process", None)
    try:
        process_absent = process is None or process.poll() is not None
    except Exception:
        process_absent = False
    lock_released = getattr(dispatcher, "lock", None) is None
    terminal = journal.snapshot().get("monitor_terminal") if journal is not None else None
    absence = getattr(monitor, "last_absence", None)
    samples = getattr(monitor, "samples", ())
    fresh_absence = monitor_thread is None and not seen and process is None
    if terminal is not None:
        fresh_absence = (terminal.get("all_seen_absent") is True and terminal.get("monotonic", -1) >= started
                         and set(terminal.get("seen_process_keys", ())) == seen)
        absence = terminal.get("exit_observation")
    elif absence and samples:
        last = samples[-1]
        p = last["processes"]
        fresh_absence = (last["monotonic"] >= started and last["index"] == absence["sample_index"]
                         and p.get("status") == "observed" and not any(p.get(name) for name in ("models", "tracked_other", "orphan_models"))
                         and seen <= set(absence["absent_model_keys"]) and set(p["seen_model_keys"]) == set(p["absent_model_keys"]))
    if not (stopped and monitor_stopped and lock_released and process_absent and fresh_absence):
        failure = {"experiment_id": "EXP-085", "attempt": ATTEMPT, "status": "ShutdownUnconfirmed", "shutdown_budget_failed": True,
                   "started_monotonic": started, "ended_monotonic": time.monotonic(),
                   "total_budget_exceeded": time.monotonic() > total_deadline,
                   "owned_process_keys": sorted(seen), "dispatcher_lock_released": lock_released,
                   "current_owned_pid": getattr(process, "pid", None), "current_process_absent": process_absent,
                   "fresh_absence_confirmed": fresh_absence,
                   "threads_alive": {"http": thread.is_alive(), "dispatcher": bool(dispatcher.thread and dispatcher.thread.is_alive()),
                                     "monitor": bool(monitor_thread is not None and monitor_thread.is_alive())}}
        once(RUN / "shutdown-failure.json", failure)
        message = {"status": "ShutdownUnconfirmed", "next_action": "manual_takeover_required_no_retry"}
        journal.report(message) if journal is not None else print(canonical(message), flush=True)
        # Retain this supervisor's ownership; only join already-existing cleanup
        # threads. No new inference, retry or stronger process termination occurs.
        def retain_ownership():
            for existing in (dispatcher.thread, getattr(monitor, "thread", None)):
                if existing is not None and existing.is_alive():
                    existing.join()
            if process is not None:
                try:
                    if process.poll() is None:
                        process.wait()  # Only this already-owned Popen; never terminate or restart it.
                except Exception:
                    pass
            threading.Event().wait()  # Explicit manual takeover; no automatic resume or new sampling.
        threading.Thread(target=retain_ownership, name="exp085-shutdown-retention", daemon=False).start()
        raise RunFailure("server_shutdown_unconfirmed")
    return {"started_monotonic": started, "ended_monotonic": time.monotonic(), "server_stopped": True,
            "dispatcher_stopped": True, "monitor_stopped": True, "dispatcher_lock_released": True,
            "current_process_absent": True, "fresh_absence_confirmed": True, "exit_observation": absence,
            "blocked_reason": getattr(dispatcher, "blocked_reason", None)}


def save_database_results(bench, directory, jobs):
    from run_soak import read_job
    database = bench / "jobs.sqlite3"
    require(database.is_file() and not database.is_symlink(), "bench_database_missing")
    # The API, dispatcher and monitor are already stopped. Fold WAL into the sealed DB.
    with sqlite3.connect(database) as connection:
        require(connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] == 0, "bench_checkpoint_failed")
    connection.close()
    for entry in jobs:
        if entry.get("id") is None:
            continue
        job, rows = read_job(database, entry["id"])
        entry.update(status=job["state"], total_items=job["total_items"], completed_items=job["completed_items"], snapshot_hash=job["snapshot_hash"])
        artifact = {"id": entry["id"], "snapshot_hash": job["snapshot_hash"], "items": [
            {"ordinal": row["ordinal"], "input_sha256": row["record"]["model_input_hash"], "result": row["result"]} for row in rows]}
        path = directory / "results" / (entry["id"] + ".json")
        once(path, artifact)
        entry["results_path"] = str(path.relative_to(ROOT))


def _run():
    from run_soak import now
    from topicweb.staged_safety import process_identity
    os.umask(0o077)
    started, started_at = time.monotonic(), now()
    require(not RUN.exists() and not any(path.is_symlink() for path in (RUN, *RUN.parents)), "attempt_already_used")
    plan, content, environment = prepare()
    RUN.mkdir(parents=True, mode=0o700)
    (RUN / "dashboards").mkdir(mode=0o700)
    (RUN / "results").mkdir(mode=0o700)
    bench = RUN / "bench"
    service = {**process_identity(os.getpid()), "experiment_id": "EXP-085", "attempt": ATTEMPT, "root": str(ROOT),
               "bench_root": str(bench), "port": 8789, "created_at": now(), "role": "http_supervisor_same_process"}
    once(RUN / "service.json", service)
    once(RUN / "plan.json", plan)
    once(RUN / "run-claim.json", {"experiment_id": "EXP-085", "tier": "Major", "attempt": ATTEMPT, "rq": "RQ-S3",
         "started_at": started_at, "started_monotonic": started, "command": sys.argv, "cwd": str(ROOT), "environment": environment,
         "runtime_environment": plan["runtime_environment"],
         "plan_sha256": sha(regular(RUN / "plan.json")),
         "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
         "git_status_porcelain": subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=ROOT, text=True).splitlines(),
         "training": False, "gold_accessed": False, "source_network_fetched": False})
    journal = Journal(RUN)
    interrupted = threading.Event()
    previous_signals = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}
    for number in previous_signals:
        signal.signal(number, lambda *_: interrupted.set())
    app = server = thread = shutdown = None
    outcome = {"logical_jobs": [], "failure_code": None, "cleanup": None}
    def identity_check():
        run_check(all(sha(regular(ROOT / name)) == digest for name, digest in plan["sources"].items())
                  and sha(regular(PROTOCOL)) == plan["protocol"]["sha256"], "runtime_identity_drift")
    try:
        app, server, thread = start_server(journal, bench, started + 1770)
        journal.report({"type": "http_ready", "port": 8789, "supervisor_pid": os.getpid()})
        outcome = execute_jobs(HTTP(bench), journal, content, plan, started + 1770, RUN,
                               blocked=lambda: getattr(app.state.dispatcher, "blocked_reason", None),
                               interrupted=interrupted.is_set, identity_check=identity_check)
    except BaseException as error:
        if isinstance(error, RunFailure) and str(error) == "server_shutdown_unconfirmed":
            raise  # Keep ownership and open journals; never seal a still-running service.
        shutdown = getattr(error, "shutdown", shutdown)
        outcome["failure_code"] = str(error) if isinstance(error, RunFailure) else "http_supervisor_failed"
    finally:
        try:
            if app is not None:
                shutdown = stop_server(app, server, thread, started + 1800, journal)
        finally:
            for number, handler in previous_signals.items():
                signal.signal(number, handler)
    if shutdown and shutdown["blocked_reason"]:
        reason = shutdown["blocked_reason"]
        code = reason if isinstance(reason, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,95}", reason) else "dispatcher_safety_stopped"
        outcome["blocked_reason"] = outcome.get("blocked_reason") or code
        outcome["failure_code"] = outcome["failure_code"] or code
    try:
        identity_check()
        source_input(ROOT / "private/jobs.sqlite3")
        verify_parent_archive(parent_documents())
        if (bench / "jobs.sqlite3").is_file():
            save_database_results(bench, RUN, outcome["logical_jobs"])
    except BaseException:
        outcome["failure_code"] = outcome["failure_code"] or "final_identity_or_database_failed"
    observed = journal.snapshot()
    for entry in outcome["logical_jobs"]:
        entry["phase_ids"] = [phase["id"] for phase in observed["phases"] if phase["logical_job_id"] == entry.get("id")]
    complete = len(outcome["logical_jobs"]) == 9 and all(entry["status"] in {"completed", "completed_with_fallback"}
                                                        and entry.get("completed_items") == 340 for entry in outcome["logical_jobs"])
    if not complete:
        outcome["failure_code"] = outcome["failure_code"] or "planned_sequence_incomplete"
    if time.monotonic() - started > 1800:
        outcome["failure_code"] = outcome["failure_code"] or "total_time_limit"
    journal.report({"type": "run_terminal", "status": "Completed" if outcome["failure_code"] is None else "Stopped",
                    "completed_jobs": sum(entry["status"] in {"completed", "completed_with_fallback"} for entry in outcome["logical_jobs"]),
                    "failure_code": outcome["failure_code"]})
    journal.close()
    artifacts = [RUN / name for name in (*JOURNALS.values(), "stdout.log", "service.json", "plan.json", "run-claim.json")]
    artifacts += sorted((RUN / "dashboards").glob("*.json")) + sorted((RUN / "results").glob("*.json"))
    if (bench / "jobs.sqlite3").is_file():
        artifacts.append(bench / "jobs.sqlite3")
    source_hashes = {str(path.relative_to(ROOT)): sha(regular(path)) for path in artifacts}
    ended = time.monotonic()
    if ended - started > 1800:
        outcome["failure_code"] = outcome["failure_code"] or "total_time_limit"
    terminal = {"experiment_id": "EXP-085", "tier": "Major", "attempt": ATTEMPT, "rq": "RQ-S3", **outcome,
                "status": "Completed" if outcome["failure_code"] is None else "Stopped", "started_at": started_at, "ended_at": now(),
                "started_monotonic": started, "ended_monotonic": ended, "elapsed_seconds": ended - started,
                "planned_jobs": 9, "planned_events": 3060, "phases": observed["phases"], "journal_counts": observed["counts"],
                "shutdown": shutdown, "source_hashes": source_hashes, "plan_sha256": sha(regular(RUN / "plan.json")),
                "bench_database": str((bench / "jobs.sqlite3").relative_to(ROOT)) if (bench / "jobs.sqlite3").is_file() else None,
                "training": False, "gold_accessed": False, "source_network_fetched": False, "total_budget_exceeded": ended - started > 1800}
    once(RUN / "run.json", terminal)
    return 0 if terminal["status"] == "Completed" else 1


def run():
    previous = os.environ.get("TOPICWEB_TELEMETRY")
    os.environ["TOPICWEB_TELEMETRY"] = "1"
    try:
        return _run()
    finally:
        if previous is None:
            os.environ.pop("TOPICWEB_TELEMETRY", None)
        else:
            os.environ["TOPICWEB_TELEMETRY"] = previous


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("archive-parent", "run"))
    arguments = parser.parse_args()
    if arguments.command == "archive-parent":
        print(json.dumps(archive_parent(), sort_keys=True))
    else:
        raise SystemExit(run())
