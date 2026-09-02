"""EXP-086: one bounded staged Research job over reviewed Discourse JSON."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
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
RUN = ROOT / "private/validation/exp-086/attempt-1"
PARENT = ROOT / "private/validation/exp-085/attempt-2"
PROTOCOL = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-086-staged-discourse-formal.md"
REVIEW = ROOT / "docs/discourse-source-review.md"
QUERY = {"site": "discuss.python.org", "category_id": 7, "max_topics": 100, "max_items": 400}
PARENT_HASHES = {
    "plan": "fc72df94b88315752c0e896af1636779391b4baeee01757041b5d1134faeb28a",
    "run": "3ec838fbfbc68867a98496f80ee0eb34c62cb74c2a3b7467a1554ce45f176b1d",
    "verification": "a33ba29be93e631074b07c140a4fdbad9566b4aa9483633ab31497dcd91af13a",
}
PARENT_ARCHIVE_SHA256 = "56386775dd61226ba3fe7f214c89b3a55cad393bb61ed868b77bc5f6082f0435"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("exp086_staged_support", ROOT / "scripts/run_staged_runtime.py")
SUPPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUPPORT)
canonical, sha, regular, once = SUPPORT.canonical, SUPPORT.sha, SUPPORT.regular, SUPPORT.once
RunFailure, run_check = SUPPORT.RunFailure, SUPPORT.run_check


def require(condition, code):
    if not condition:
        raise RunFailure(code)


def parent_gate():
    documents, bindings = {}, {}
    for name, expected in PARENT_HASHES.items():
        path = PARENT / (name + ".json")
        raw = regular(path)
        require(sha(raw) == expected, "parent_artifact_drift")
        documents[name] = json.loads(raw)
        bindings[name] = {"path": str(path.relative_to(ROOT)), "sha256": expected}
    run, verification, plan = documents["run"], documents["verification"], documents["plan"]
    require(run.get("experiment_id") == "EXP-085" and run.get("attempt") == 2
            and run.get("status") == "Completed" and run.get("failure_code") is None, "parent_run_not_complete")
    require(verification.get("experiment_id") == "EXP-085" and verification.get("attempt") == 2
            and verification.get("status") == "Passed" and verification.get("exp085_complete") is True
            and verification.get("safety", {}).get("gate_passed") is True
            and verification.get("operational_state") == "safe-to-continue", "parent_verification_not_safe")
    path = PARENT / "frozen-code.tar.gz"
    require(sha(regular(path)) == PARENT_ARCHIVE_SHA256, "parent_archive_drift")
    expected = {**plan["sources"], "protocol.md": plan["protocol"]["sha256"]}
    require(len(plan["sources"]) == 32 and len(expected) == 33, "parent_source_count")
    actual, total = {}, 0
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            require(member.isfile() and member.name in expected and member.name not in actual
                    and not Path(member.name).is_absolute() and ".." not in Path(member.name).parts
                    and 0 <= member.size <= 2 * 1024**2, "parent_archive_member")
            stream = archive.extractfile(member)
            require(stream is not None, "parent_archive_payload")
            raw = stream.read(member.size + 1)
            total += len(raw)
            require(len(raw) == member.size and total <= 32 * 1024**2, "parent_archive_payload")
            actual[member.name] = sha(raw)
    require(actual == expected and sha(regular(path)) == PARENT_ARCHIVE_SHA256, "parent_archive_sources")
    bindings["archive"] = {"path": str(path.relative_to(ROOT)), "sha256": PARENT_ARCHIVE_SHA256, "members": 33}
    return documents, bindings


def dependencies(parent_sources):
    additions = (
        "scripts/run_staged_discourse_formal.py", "scripts/verify_staged_discourse_formal.py",
        "tests/test_staged_discourse_formal.py", "tests/test_verify_staged_discourse_formal.py",
    )
    sources = dict(parent_sources)
    for name in additions:
        sources[name] = sha(regular(ROOT / name))
    require(all(sha(regular(ROOT / name)) == expected for name, expected in parent_sources.items()), "parent_production_drift")
    return sources


def prepare():
    from run_soak import environment_metadata
    documents, parent = parent_gate()
    environment = environment_metadata()
    plan = {"experiment_id": "EXP-086", "attempt": 1, "tier": "Minor", "rq": "RQ-S3",
            "parent_exp085": parent, "query": QUERY, "mode": "research", "max_qwen_calls": 500,
            "audit_rate": 0, "seed": 42, "planned_jobs": 1, "planned_records_min": 300, "planned_records_max": 400,
            "max_seconds": 3600, "work_seconds": 3570, "cleanup_seconds": 15, "port": 8790,
            "sources": dependencies(documents["plan"]["sources"]),
            "protocol": {"path": str(PROTOCOL.relative_to(ROOT.parent)), "sha256": sha(regular(PROTOCOL))},
            "source_review": {"path": str(REVIEW.relative_to(ROOT)), "sha256": sha(regular(REVIEW))},
            "model_config": documents["plan"]["model_config"], "router_assets": documents["plan"]["router_assets"],
            "runtime_environment": {"TOPICWEB_TELEMETRY": "1"},
            "source_network_authorized": True,
            "scope": "source_and_local_system_closure_without_external_gold"}
    return plan, environment


class FormalJournal(SUPPORT.Journal):
    SAFE_SOURCE_KEYS = {"stage", "source_stage", "endpoint_kind", "page", "request_count", "record_count",
                        "http_status", "response_bytes", "response_sha256", "content_encoding", "number", "topic_id",
                        "stop_reason", "status", "logical_job_id", "monotonic"}

    def __init__(self, directory):
        super().__init__(directory)
        descriptor = os.open(directory / "source-progress.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        self.source_output = os.fdopen(descriptor, "w")
        self.source_count = 0
        self.source_request_count = 0
        self.source_response_count = 0
        self.source_last = None

    def source_progress(self, value):
        require(isinstance(value, dict), "source_progress_schema")
        safe = {key: value[key] for key in self.SAFE_SOURCE_KEYS if key in value
                and (type(value[key]) in (str, int, bool) or value[key] is None
                     or type(value[key]) is float and math.isfinite(value[key]) and value[key] >= 0)}
        require(safe and safe != self.source_last, "source_progress_duplicate_or_empty")
        with self.lock:
            self.source_output.write(canonical(safe) + "\n")
            self.source_output.flush()
            os.fsync(self.source_output.fileno())
            self.source_count += 1
            self.source_last = safe
            self.source_request_count += safe.get("source_stage") == "request_started"
            self.source_response_count += safe.get("source_stage") == "response_received"

    def snapshot(self):
        value = super().snapshot()
        value["source_progress_count"] = self.source_count
        value["source_request_count"] = self.source_request_count
        value["source_response_count"] = self.source_response_count
        return value

    def close(self):
        with self.lock:
            self.source_output.close()
            super().close()


class HTTP:
    def __init__(self, bench):
        token = regular(bench / "access-token").decode().strip()
        require(len(token) >= 32, "token_identity")
        self.token = token

    def __call__(self, path, payload=None, timeout=10):
        request = Request("http://127.0.0.1:8790/api/" + path,
                          data=canonical(payload).encode() if payload is not None else None,
                          headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        with urlopen(request, timeout=max(.01, timeout)) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
        require(len(raw) <= 2 * 1024 * 1024, "local_api_response_limit")
        value = json.loads(raw)
        require(isinstance(value, dict), "local_api_response_schema")
        return value


def submission_matches(job):
    return (isinstance(job, dict) and isinstance(job.get("id"), str) and re.fullmatch(r"[a-f0-9]{32}", job["id"]) is not None
            and job.get("name") == "EXP-086 Python Help staged formal" and job.get("source") == "discourse"
            and job.get("mode") == "research")


def execute(api, local_jobs, local_job, journal, deadline, directory, *, blocked=lambda: None,
            interrupted=lambda: False, identity_check=lambda: None):
    job_entry = {"id": None, "mode": "research", "budget": 500, "source": "discourse", "query": QUERY,
                 "status": "submission_pending", "started_monotonic": time.monotonic(),
                 "http_submission_acknowledged": False, "phase_ids": []}
    current, pending, failure, cleanup = None, None, None, None
    try:
        identity_check()
        require(not interrupted() and time.monotonic() < deadline and not blocked(), "formal_precondition_stopped")
        known = {job["id"] for job in local_jobs()}
        pending = known
        payload = {"name": "EXP-086 Python Help staged formal", "source": "discourse", "mode": "research",
                   "max_qwen_calls": 500, "audit_rate": 0, "query": QUERY}
        submitted = api("jobs", payload, timeout=min(10, max(.01, deadline-time.monotonic())))["job"]
        require(submission_matches(submitted), "submission_identity")
        current, pending = submitted["id"], None
        job_entry.update(id=current, status=submitted["state"], http_submission_acknowledged=True)
        journal.report({"type": "formal_job_submitted", "id": current})
        while True:
            reason = blocked()
            require(not interrupted() and time.monotonic() < deadline, "formal_time_or_interrupt")
            require(not reason, reason if isinstance(reason, str) and re.fullmatch(r"[a-z0-9_]{1,96}", reason) else "formal_safety_stopped")
            local = local_job(current)
            require(isinstance(local, dict) and local.get("id") == current, "local_job_identity")
            job = api("jobs/" + current, timeout=min(2, max(.01, deadline-time.monotonic())))["job"]
            job_entry.update(status=job["state"], total_items=job["total_items"], completed_items=job["completed_items"],
                             snapshot_hash=job.get("snapshot_hash"), error_code=job.get("error_code"), manifest=job.get("manifest"))
            if job["state"] in {"completed", "completed_with_fallback", "failed", "cancelled"}:
                break
            time.sleep(.25)
        require(job["state"] == "completed" and job.get("error_code") is None
                and type(job["total_items"]) is int and 300 <= job["total_items"] <= 400
                and job["completed_items"] == job["total_items"], "formal_job_not_complete")
        manifest = job["manifest"]
        journal.source_progress({"stage": "manifest", "record_count": manifest["record_count"],
                                 "request_count": len(manifest["requests"]), "stop_reason": manifest["stop_reason"],
                                 "status": "complete", "logical_job_id": current, "monotonic": time.monotonic()})
        dashboard = api("jobs/" + current + "/dashboard", timeout=min(10, max(.01, deadline-time.monotonic())))
        path = directory / "dashboard.json"
        once(path, dashboard)
        job_entry.update(status="completed", dashboard_path=str(path.relative_to(ROOT)),
                         api_dashboard_observed=True, ended_monotonic=time.monotonic())
    except BaseException as error:
        failure = str(error) if isinstance(error, RunFailure) else "formal_driver_error"
        if current is None and pending is not None:
            candidates = [job for job in local_jobs() if job.get("id") not in pending]
            if len(candidates) == 1 and submission_matches(candidates[0]):
                current = candidates[0]["id"]
                job_entry.update(id=current, status=candidates[0]["state"], recovered_for_cancellation_only=True)
            else:
                job_entry.update(status="submission_unconfirmed", submission_recovery_confirmed=False)
        if current is not None:
            started = time.monotonic()
            cleanup = {"started_monotonic": started, "max_seconds": 15, "terminal_confirmed": False}
            try:
                end = min(deadline + 15, started + 15)
                api("jobs/" + current + "/cancel", {}, timeout=min(3, max(.01, end-time.monotonic())))
                while time.monotonic() < end:
                    job = api("jobs/" + current, timeout=min(2, max(.01, end-time.monotonic())))["job"]
                    if job["state"] in {"completed", "completed_with_fallback", "failed", "cancelled"}:
                        cleanup["terminal_confirmed"] = True
                        job_entry.update(status=job["state"], total_items=job["total_items"], completed_items=job["completed_items"],
                                         snapshot_hash=job.get("snapshot_hash"), error_code=job.get("error_code"), manifest=job.get("manifest"))
                        break
                    time.sleep(.1)
            except BaseException:
                cleanup["error_code"] = "formal_cleanup_unconfirmed"
            cleanup["ended_monotonic"] = time.monotonic()
    jobs = [] if current is None and pending is None and job_entry["status"] == "submission_pending" else [job_entry]
    return {"logical_jobs": jobs, "failure_code": failure, "cleanup": cleanup}


def first_logical_job(outcome):
    jobs = outcome.get("logical_jobs")
    return jobs[0] if isinstance(jobs, list) and jobs else None


def gate_fetch(journal, logical_job_id, fetch):
    from topicweb.adapters import SourceError
    def gated(request, *, cancelled, progress):
        identifier = logical_job_id()
        require(isinstance(identifier, str) and re.fullmatch(r"[a-f0-9]{32}", identifier), "source_job_identity")
        observed_count = 0
        def observed(value):
            nonlocal observed_count
            if type(value.get("record_count")) is int and value["record_count"] >= observed_count:
                observed_count = value["record_count"]
            progress(value)
            journal.source_progress({**value, "logical_job_id": identifier, "monotonic": time.monotonic()})
        try:
            records, manifest = fetch(request, cancelled=cancelled, progress=observed)
        except SourceError as error:
            count = error.metadata.get("record_count") if type(error.metadata.get("record_count")) is int else observed_count
            journal.source_progress({**error.metadata, "stage": "source_error", "status": "failed",
                                     "logical_job_id": identifier, "monotonic": time.monotonic()})
            journal.source_progress({"stage": "source_count_gate", "record_count": count,
                                     "status": "rejected_before_model", "logical_job_id": identifier,
                                     "monotonic": time.monotonic()})
            raise
        status = "accepted" if 300 <= len(records) <= 400 else "rejected_before_model"
        journal.source_progress({"stage": "source_count_gate", "record_count": len(records), "status": status,
                                 "logical_job_id": identifier, "monotonic": time.monotonic()})
        if status != "accepted":
            raise SourceError("Discourse sample count outside formal gate", code="source_validation_error",
                              metadata={"stage": "validation", "record_count": len(records)})
        return records, manifest
    return gated


def start_server(journal, bench, deadline):
    import uvicorn
    from topicweb.adapters import fetch_discourse
    from topicweb.staged_app import create_app
    holder = {}
    fetch = gate_fetch(journal, lambda: holder["app"].state.dispatcher.current_job, fetch_discourse)
    app = create_app(private_dir=bench, observer=journal, fetch=fetch)
    holder["app"] = app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8790, access_log=False,
                                         log_level="error", timeout_graceful_shutdown=15))
    errors = []
    def serve():
        try:
            server.run()
        except BaseException:
            errors.append("http_server_failed")
    thread = threading.Thread(target=serve, name="exp086-http-server", daemon=False)
    thread.start()
    end = min(deadline, time.monotonic()+20)
    while not server.started and thread.is_alive() and time.monotonic() < end:
        time.sleep(.05)
    if not server.started or errors:
        shutdown = stop_server(app, server, thread, min(deadline + 30, time.monotonic() + 20), journal, RUN)
        error = RunFailure("http_server_start_failed")
        error.shutdown = shutdown
        raise error
    return app, server, thread


def stop_server(app, server, thread, deadline, journal, run_dir):
    started = time.monotonic()
    dispatcher, monitor = app.state.dispatcher, app.state.dispatcher.monitor
    dispatcher.stop_event.set()
    server.should_exit = True
    thread.join(timeout=min(20, max(0, deadline-time.monotonic())))
    monitor_thread = getattr(monitor, "thread", None)
    terminal = journal.snapshot().get("monitor_terminal")
    runner = getattr(monitor, "current_runner", None)
    process = getattr(runner, "process", None)
    try:
        process_absent = process is None or process.poll() is not None
    except Exception:
        process_absent = False
    fresh = monitor_thread is None and not monitor.seen and process is None
    if terminal is not None:
        fresh = (terminal.get("all_seen_absent") is True and terminal.get("monotonic", -1) >= started
                 and set(terminal.get("seen_process_keys", ())) == set(monitor.seen))
    stopped = (not thread.is_alive() and not (dispatcher.thread and dispatcher.thread.is_alive())
               and (monitor_thread is None or not monitor_thread.is_alive()) and dispatcher.lock is None
               and process_absent and fresh)
    if not stopped:
        failure = {"experiment_id": "EXP-086", "status": "ShutdownUnconfirmed", "ended_monotonic": time.monotonic(),
                   "owned_process_keys": sorted(monitor.seen), "current_owned_pid": getattr(process, "pid", None)}
        once(run_dir / "shutdown-failure.json", failure)
        journal.report({"status": "ShutdownUnconfirmed", "next_action": "manual_takeover_required_no_retry"})
        def retain():
            for existing in (dispatcher.thread, monitor_thread):
                if existing is not None and existing.is_alive():
                    existing.join()
            if process is not None and process.poll() is None:
                process.wait()
            threading.Event().wait()
        threading.Thread(target=retain, name="exp086-shutdown-retention", daemon=False).start()
        raise RunFailure("server_shutdown_unconfirmed")
    return {"server_stopped": True, "dispatcher_stopped": True, "monitor_stopped": True,
            "dispatcher_lock_released": True, "current_process_absent": True, "fresh_absence_confirmed": True,
            "exit_observation": terminal.get("exit_observation"), "blocked_reason": dispatcher.blocked_reason,
            "started_monotonic": started, "ended_monotonic": time.monotonic()}


def save_results(bench, job, directory):
    from run_soak import read_job
    database = bench / "jobs.sqlite3"
    with sqlite3.connect(database) as connection:
        require(connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] == 0, "bench_checkpoint_failed")
    stored, rows = read_job(database, job["id"])
    job.update(status=stored["state"], total_items=stored["total_items"], completed_items=stored["completed_items"],
               snapshot_hash=stored["snapshot_hash"], manifest=stored["manifest"])
    artifact = {"id": job["id"], "snapshot_hash": stored["snapshot_hash"], "items": [
        {"ordinal": row["ordinal"], "input_sha256": row["record"]["model_input_hash"], "result": row["result"]} for row in rows]}
    path = directory / "results.json"
    once(path, artifact)
    job["results_path"] = str(path.relative_to(ROOT))


def network_attestation(observed):
    requests, responses = observed["source_request_count"], observed["source_response_count"]
    require(type(requests) is int and type(responses) is int and 0 <= responses <= requests, "source_network_evidence")
    return {"source_network_authorized": True, "source_network_attempted": requests > 0,
            "source_network_fetched": responses > 0, "source_response_count": responses}


def _run():
    from run_soak import now
    from topicweb.staged_safety import process_identity
    os.umask(0o077)
    started, started_at = time.monotonic(), now()
    require(not RUN.exists() and not any(path.is_symlink() for path in (RUN, *RUN.parents)), "attempt_already_used")
    plan, environment = prepare()
    RUN.mkdir(parents=True, mode=0o700)
    bench = RUN / "bench"
    service = {**process_identity(os.getpid()), "experiment_id": "EXP-086", "attempt": 1,
               "root": str(ROOT), "bench_root": str(bench), "port": 8790, "created_at": now()}
    once(RUN / "service.json", service)
    once(RUN / "plan.json", plan)
    once(RUN / "run-claim.json", {"experiment_id": "EXP-086", "attempt": 1, "tier": "Minor", "rq": "RQ-S3",
         "started_at": started_at, "started_monotonic": started, "plan_sha256": sha(regular(RUN / "plan.json")),
         "command": sys.argv, "cwd": str(ROOT), "environment": environment, "runtime_environment": plan["runtime_environment"],
         "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
         "git_status_porcelain": subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=ROOT, text=True).splitlines(),
         "training": False, "gold_accessed": False,
         "source_network_authorized": True, "source_network_fetched": False})
    journal = FormalJournal(RUN)
    interrupted = threading.Event()
    old_signals = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}
    for number in old_signals:
        signal.signal(number, lambda *_: interrupted.set())
    app = server = thread = shutdown = None
    outcome = {"logical_jobs": [], "failure_code": None, "cleanup": None}
    def identity():
        require(all(sha(regular(ROOT / name)) == expected for name, expected in plan["sources"].items())
                and sha(regular(PROTOCOL)) == plan["protocol"]["sha256"], "runtime_identity_drift")
    try:
        app, server, thread = start_server(journal, bench, started+3570)
        client = HTTP(bench)
        outcome = execute(client, app.state.store.list, lambda job_id: app.state.store.get(job_id), journal,
                          started+3570, RUN, blocked=lambda: app.state.dispatcher.blocked_reason,
                          interrupted=interrupted.is_set, identity_check=identity)
    except BaseException as error:
        if isinstance(error, RunFailure) and str(error) == "server_shutdown_unconfirmed":
            raise
        shutdown = getattr(error, "shutdown", shutdown)
        outcome["failure_code"] = str(error) if isinstance(error, RunFailure) else "formal_supervisor_failed"
    finally:
        try:
            if app is not None:
                shutdown = stop_server(app, server, thread, started+3600, journal, RUN)
        finally:
            for number, handler in old_signals.items():
                signal.signal(number, handler)
    if shutdown and shutdown["blocked_reason"]:
        outcome["failure_code"] = outcome["failure_code"] or shutdown["blocked_reason"]
    job = first_logical_job(outcome)
    try:
        identity()
        parent_gate()
        if (bench / "jobs.sqlite3").is_file() and job is not None and job.get("id"):
            save_results(bench, job, RUN)
    except BaseException:
        outcome["failure_code"] = outcome["failure_code"] or "final_identity_or_database_failed"
    observed = journal.snapshot()
    if job:
        job["phase_ids"] = [phase["id"] for phase in observed["phases"] if phase["logical_job_id"] == job.get("id")]
    network = network_attestation(observed)
    complete = (job is not None and job.get("status") == "completed" and 300 <= job.get("completed_items", 0) <= 400
                and len(job.get("phase_ids", ())) == 2 and outcome["failure_code"] is None
                and network["source_network_attempted"] and network["source_network_fetched"])
    if not complete:
        outcome["failure_code"] = outcome["failure_code"] or "formal_sequence_incomplete"
    journal.report({"type": "run_terminal", "status": "Completed" if complete else "Stopped", "failure_code": outcome["failure_code"]})
    journal.close()
    artifacts = [RUN / name for name in (*SUPPORT.JOURNALS.values(), "source-progress.jsonl", "stdout.log",
                                          "service.json", "plan.json", "run-claim.json")]
    artifacts += [path for path in (RUN / "dashboard.json", RUN / "results.json", bench / "jobs.sqlite3") if path.is_file()]
    source_hashes = {str(path.relative_to(ROOT)): sha(regular(path)) for path in artifacts}
    ended = time.monotonic()
    if ended-started > 3600:
        outcome["failure_code"] = outcome["failure_code"] or "formal_total_time_limit"
    terminal = {"experiment_id": "EXP-086", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", **outcome,
                "status": "Completed" if complete and outcome["failure_code"] is None else "Stopped",
                "started_at": started_at, "ended_at": now(), "started_monotonic": started, "ended_monotonic": ended,
                "elapsed_seconds": ended-started, "planned_jobs": 1,
                "planned_records_min": 300, "planned_records_max": 400,
                "phases": observed["phases"], "journal_counts": observed["counts"],
                "source_progress_count": observed["source_progress_count"], "shutdown": shutdown,
                "bench_database": str((bench / "jobs.sqlite3").relative_to(ROOT)) if (bench / "jobs.sqlite3").is_file() else None,
                "source_hashes": source_hashes, "plan_sha256": sha(regular(RUN / "plan.json")),
                "total_budget_exceeded": ended-started > 3600,
                "training": False, "gold_accessed": False, **network}
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
    if sys.argv[1:] == ["run"]:
        raise SystemExit(run())
    raise SystemExit("usage: run_staged_discourse_formal.py run")
