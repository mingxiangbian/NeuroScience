"""EXP-082: one observed process, seven frozen inputs, no HTTP or source fetch."""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import sys
import time

from bounded_runtime_support import (
    ROOT, Monitor, SupportError, canonical, digest, environment_metadata,
    make_runner_factory, now, once, process_identity, require, wait_absent, wait_ready,
)
from topicweb.worker import WorkerError

RUN = ROOT / "private/validation/exp-082/attempt-1"
PRIOR = ROOT / "private/validation/exp-079/attempt-3"
PROTOCOL = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-082-first-m3-memory-diagnostic.md"
SOURCE_JOB = "5ab3326150ee448ba326233264967d34"
SOURCE_SNAPSHOT = "cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16"
PARENT_HASHES = {
    "plan": "6635d7022959642ae0adff5c42b483ca30a0cc598924ee814c25667c1e5d236c",
    "run": "990efbb28bf91025b6554d3756e2f471a8edd8eac8a1962535cb98384e2a0722",
    "verification": "2f078610f6ff4be0d17fdd047cbca0f6d156425e577ddba34cbe1d30581990ec",
}
ADDITIONAL_SOURCES = (
    "scripts/run_m3_diagnostic.py", "scripts/diagnostic_m3_child.py", "scripts/verify_m3_diagnostic.py",
    "tests/test_m3_diagnostic.py", "tests/test_diagnostic_m3_child.py", "tests/test_verify_m3_diagnostic.py",
)


def file_hash(path):
    require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), "source_missing_or_symlink")
    return digest(path.read_bytes())


def select_prefix(database, expected):
    require(database.is_file() and not any(p.is_symlink() for p in (database, *database.parents)), "source_database_missing")
    require(len(expected) == 7 and [row["ordinal"] for row in expected] == list(range(7)), "prefix_contract")
    require([row["route_eligible"] for row in expected] == [False]*6+[True], "prefix_route_contract")
    with sqlite3.connect(database.as_uri()+"?mode=ro", uri=True, timeout=1) as db:
        job = db.execute("SELECT state,snapshot_hash,total_items FROM jobs WHERE id=?", (SOURCE_JOB,)).fetchone()
        require(job == ("completed", SOURCE_SNAPSHOT, 340), "source_job_identity")
        rows = db.execute("SELECT ordinal,record FROM items WHERE job_id=? AND ordinal>=0 AND ordinal<7 ORDER BY ordinal", (SOURCE_JOB,)).fetchall()
    require([row[0] for row in rows] == list(range(7)), "prefix_rows_missing")
    records = []
    for (ordinal, raw), metadata in zip(rows, expected):
        record = json.loads(raw)
        text = record["model_input_text"]
        require(isinstance(text, str) and text and len(text.encode()) <= 65536, "source_input_contract")
        require(digest(text) == record["model_input_hash"] == metadata["input_sha256"], "source_input_drift")
        records.append({"model_input_text": text, "model_input_hash": metadata["input_sha256"]})
    return records


def prepare():
    previous, bindings = {}, {}
    for name, expected in PARENT_HASHES.items():
        path = PRIOR / (name+".json")
        require(file_hash(path) == expected, "parent_identity_drift")
        previous[name] = json.loads(path.read_text())
        bindings[name] = {"path": str(path.relative_to(ROOT)), "sha256": expected}
    require(previous["run"]["status"] == "Stopped" and previous["run"]["failure_code"] == "critical_memory_pressure"
            and previous["verification"]["status"] == "Passed" and previous["verification"]["exp079_complete"] is False,
            "parent_terminal_contract")
    for name, expected in previous["verification"]["source_hashes"].items():
        require(file_hash(ROOT/name) == expected, "parent_artifact_drift")
    sources = dict(previous["plan"]["sources"])
    require(all(file_hash(ROOT/name) == expected for name, expected in sources.items()), "frozen_implementation_drift")
    sources.update({name: file_hash(ROOT/name) for name in ADDITIONAL_SOURCES})
    prefix = previous["plan"]["source_rows"][:7]
    records = select_prefix(ROOT/"private/jobs.sqlite3", prefix)
    plan = {"experiment_id": "EXP-082", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", "planned_events": 7,
            "max_seconds": 180, "work_seconds": 150, "max_readiness_seconds": 60, "cleanup_seconds": 15,
            "mode": "research", "max_qwen_calls": 1, "audit_rate": 0, "seed": 42,
            "source_job": SOURCE_JOB, "source_snapshot_sha256": SOURCE_SNAPSHOT,
            "source_database": "private/jobs.sqlite3", "source_rows": prefix, "parent_bindings": bindings,
            "sources": sources, "protocol": {"path": str(PROTOCOL.relative_to(ROOT.parent)), "sha256": file_hash(PROTOCOL)},
            "instrumentation_claim": "Python stage tracing only; original model code unchanged; timing overhead not a benchmark."}
    return plan, records


def append(stream, value):
    stream.write(canonical(value)+"\n")
    stream.flush()
    os.fsync(stream.fileno())


def safe_error(error):
    if isinstance(error, (KeyboardInterrupt, SystemExit)):
        return "diagnostic_interrupted"
    code = str(error) if isinstance(error, (SupportError, WorkerError)) else "diagnostic_driver_error"
    return code if re.fullmatch(r"[a-z0-9_]{1,96}", code) else "diagnostic_driver_error"


def check_result(result, ordinal):
    require(isinstance(result, dict) and len(result.get("prediction", [])) == 6
            and all(type(v) is int and v in (0, 1) for v in result["prediction"]), "result_schema")
    require(result.get("route_requested") is (ordinal == 6) and result.get("fallback_reason") is None, "result_route_or_fallback")
    require(result.get("used_path") == ("m3" if ordinal == 6 else "m1"), "result_path")
    resources = result["resources"]
    require(resources["peak_rss_bytes"] <= 12*1024**3 and resources["mlx_peak_bytes"] <= 10_000_000_000, "result_resource_limit")


def execute(monitor, records, factory, work_deadline, results, report):
    job = runner = cleanup = failure = None
    count = 0
    readiness = {"status": "Waiting", "started_monotonic": time.monotonic(), "indices": []}
    report({"status": "waiting_for_quiet_window"})
    try:
        indices = wait_ready(monitor, work_deadline, 60)
        readiness.update(status="Ready", indices=indices, ended_monotonic=time.monotonic())
        require(not monitor.reason, monitor.reason or "monitoring_failed")
        job = {"id": "exp082-prefix7", "mode": "research", "status": "running", "total_items": 7,
               "completed_items": 0, "started_monotonic": time.monotonic(),
               "readiness_indices": indices, "readiness_started_monotonic": readiness["started_monotonic"],
               "readiness_ended_monotonic": readiness["ended_monotonic"], "normal_exit": False}
        monitor.set_job(job["id"])
        runner = factory({"id": job["id"], "mode": "research", "request": {"max_qwen_calls": 1, "audit_rate": 0}})
        report({"status": "child_ready", "pid": runner.process.pid})
        for ordinal, record in enumerate(records):
            require(not monitor.reason, monitor.reason or "monitoring_failed")
            require(time.monotonic() < work_deadline, "diagnostic_time_limit")
            result = runner.predict(str(ordinal), record)
            check_result(result, ordinal)
            append(results, {"ordinal": ordinal, "input_sha256": record["model_input_hash"], "result": result})
            count += 1
            job["completed_items"] = count
            report({"status": "result_received", "ordinal": ordinal})
        runner.finish()
        require(not monitor.reason, monitor.reason or "monitoring_failed")
        observation = wait_absent(monitor, monitor.samples[-1]["index"], work_deadline, 15)
        job.update(status="completed", normal_exit=True, exit_observation=observation, ended_monotonic=time.monotonic())
    except BaseException as error:
        failure = monitor.reason or safe_error(error)
        readiness.setdefault("ended_monotonic", time.monotonic())
        if readiness["status"] != "Ready":
            readiness.update(status="NotReady", error_code=failure)
        if job is not None:
            start = time.monotonic()
            cleanup = {"job_id": job["id"], "started_monotonic": start, "max_seconds": 15,
                       "terminal_confirmed": False, "models_absent_confirmed": False, "normal_exit": False}
            try:
                initial = monitor.samples[-1]["index"] if monitor.samples else -1
                if runner is not None:
                    runner.close()
                events = [json.loads(line) for line in monitor.events_path.read_text().splitlines()]
                cleanup["terminal_confirmed"] = any(event["type"] == "process_exit" for event in events)
                cleanup["exit_observation"] = wait_absent(monitor, initial, min(work_deadline+15, start+15), 15)
                cleanup["models_absent_confirmed"] = True
            except BaseException as cleanup_error:
                cleanup["error_code"] = safe_error(cleanup_error)
            cleanup["ended_monotonic"] = time.monotonic()
            job.update(status="cancelled" if monitor.reason else "failed", cleanup=cleanup, ended_monotonic=time.monotonic())
        report({"status": "Stopped", "failure_code": failure, "completed_events": count})
    return {"job": job, "readiness": readiness, "cleanup": cleanup, "failure_code": failure, "completed_events": count}


def run():
    os.umask(0o077)
    started, started_at = time.monotonic(), now()
    require(not RUN.exists() and not any(p.is_symlink() for p in (RUN, *RUN.parents)), "attempt_already_used_or_symlink")
    plan, records = prepare()
    environment = environment_metadata()
    RUN.mkdir(parents=True, mode=0o700)
    identity = process_identity(os.getpid())
    identity.pop("raw")
    service = {**identity, "experiment_id": "EXP-082", "root": str(ROOT), "bench_root": str(RUN/"bench"),
               "port": None, "created_at": now(), "role": "diagnostic_supervisor_no_http"}
    once(RUN/"service.json", service)
    once(RUN/"plan.json", plan)
    once(RUN/"run-claim.json", {"experiment_id": "EXP-082", "attempt": 1, "tier": "Minor", "rq": "RQ-S3",
         "started_at": started_at, "started_monotonic": started, "command": sys.argv, "cwd": str(ROOT),
         "environment": environment, "plan_sha256": file_hash(RUN/"plan.json"),
         "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
         "git_status_porcelain": subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=ROOT, text=True).splitlines(),
         "training": False, "gold_accessed": False, "source_network_fetched": False})
    for name in ("process-events.jsonl", "stages.jsonl"):
        descriptor = os.open(RUN/name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.close(descriptor)
    descriptor = os.open(RUN/"dispatch.lock", os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    os.environ["TOPICWEB_TELEMETRY"] = "1"
    os.environ["TOPICWEB_EXP082_STAGE_PATH"] = str(RUN/"stages.jsonl")
    monitor = Monitor(RUN/"samples.jsonl", service)
    def request_stop(_signum, _frame):
        monitor.reason = monitor.reason or "diagnostic_interrupted"
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    observed_runner = make_runner_factory(RUN/"process-events.jsonl")
    def factory(job):
        return observed_runner(job, lock_fd=descriptor,
            cancelled=lambda: bool(monitor.reason) or time.monotonic() >= started+150,
            deadline=started+150, command=[environment["model_runtime"]["python_executable"], str(ROOT/"scripts/diagnostic_m3_child.py")])
    outcome = {"job": None, "readiness": None, "cleanup": None, "failure_code": None, "completed_events": 0}
    with (RUN/"results.jsonl").open("x") as results, (RUN/"stdout.log").open("x") as output:
        def report(value):
            append(output, value)
            print(canonical(value), flush=True)
        try:
            monitor.start()
            outcome = execute(monitor, records, factory, started+150, results, report)
        except BaseException as error:
            outcome["failure_code"] = monitor.reason or safe_error(error)
        finally:
            try:
                monitor.finish()
            except BaseException as error:
                outcome["failure_code"] = outcome["failure_code"] or safe_error(error)
            os.close(descriptor)
        if monitor.reason:
            outcome["failure_code"] = outcome["failure_code"] or monitor.reason
        try:
            require(all(file_hash(ROOT/name) == expected for name, expected in plan["sources"].items()), "implementation_identity_drift")
            require(file_hash(PROTOCOL) == plan["protocol"]["sha256"], "protocol_identity_drift")
            select_prefix(ROOT/"private/jobs.sqlite3", plan["source_rows"])
        except Exception as error:
            outcome["failure_code"] = outcome["failure_code"] or safe_error(error)
        report({"status": "Completed" if outcome["failure_code"] is None else "Stopped",
                "completed_events": outcome["completed_events"], "failure_code": outcome["failure_code"]})
    events = [json.loads(line) for line in (RUN/"process-events.jsonl").read_text().splitlines()]
    exits = [event for event in events if event["type"] == "process_exit"]
    ended = time.monotonic()
    if ended-started > 180:
        outcome["failure_code"] = outcome["failure_code"] or "diagnostic_total_time_limit"
    artifacts = ("service.json", "plan.json", "run-claim.json", "results.jsonl", "samples.jsonl", "process-events.jsonl", "stages.jsonl", "stdout.log")
    terminal = {"experiment_id": "EXP-082", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", **outcome,
                "status": "Completed" if outcome["failure_code"] is None else "Stopped",
                "started_at": started_at, "ended_at": now(), "started_monotonic": started, "ended_monotonic": ended,
                "elapsed_seconds": ended-started, "planned_events": 7,
                "total_budget_exceeded": ended-started > 180,
                "child_launched": any(event.get("pid") is not None for event in events),
                "child_returncode": exits[-1]["returncode"] if exits else None,
                "plan_sha256": file_hash(RUN/"plan.json"),
                "source_hashes": {str((RUN/name).relative_to(ROOT)): file_hash(RUN/name) for name in artifacts},
                "training": False, "gold_accessed": False, "source_network_fetched": False,
                "operational_followup_authorized": False}
    once(RUN/"run.json", terminal)
    return 0 if terminal["status"] == "Completed" else 1


if __name__ == "__main__":
    if sys.argv[1:] in (["--help"], ["-h"]):
        print("EXP-082 run: one seven-input process, stage metadata only, unchanged safety gates.")
    elif sys.argv[1:] == ["run"]:
        raise SystemExit(run())
    else:
        raise SystemExit("usage: run_m3_diagnostic.py run")
