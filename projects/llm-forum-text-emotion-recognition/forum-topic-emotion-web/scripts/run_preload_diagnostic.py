"""EXP-083: one complete M1 prelude, then the unchanged seven-input diagnostic."""
from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
import sys
import time

from bounded_runtime_support import (
    ROOT, Monitor, SupportError, canonical, digest, environment_metadata,
    make_runner_factory, now, once, process_identity, read_job, require, wait_absent, wait_ready,
)
from run_m3_diagnostic import append, check_result as check_research_result, file_hash, safe_error

RUN = ROOT / "private/validation/exp-083/attempt-1"
PRIOR = ROOT / "private/validation/exp-082/attempt-1"
PROTOCOL = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-083-m1-prelude-memory-diagnostic.md"
SOURCE_JOB = "5ab3326150ee448ba326233264967d34"
SOURCE_SNAPSHOT = "cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16"
PARENT_HASHES = {
    "plan": "896067922d9029e35ccdf1eeb44976bb22fc96a71ce0791424861d16547a5298",
    "run": "10125ffc1c22bd020dc75f2c05647464be22ea90f8d509b7e3f7e78eb9d4e952",
    "verification": "0d98fef8a5662bace2299bd7f11f9d17c99f13b14dca4a7c3765f4fe2ea3deb6",
}
ADDITIONAL_SOURCES = (
    "scripts/run_preload_diagnostic.py", "scripts/preload_diagnostic_child.py", "scripts/verify_preload_diagnostic.py",
    "tests/test_preload_diagnostic.py", "tests/test_verify_preload_diagnostic.py",
)
PHASES = (
    {"phase": "m1_prelude", "job_id": "exp083-m1-prelude", "mode": "m1_only", "planned_events": 340, "max_qwen_calls": 0},
    {"phase": "research_prefix", "job_id": "exp083-research-prefix", "mode": "research", "planned_events": 7, "max_qwen_calls": 1},
)


def select_records(database, expected, logical_hash):
    require(len(expected) == 340 and [row["ordinal"] for row in expected] == list(range(340)), "source_ordinal_contract")
    job, rows = read_job(database, SOURCE_JOB)
    require(job["state"] == "completed" and job["snapshot_hash"] == SOURCE_SNAPSHOT
            and job["total_items"] == 340 and len(rows) == 340, "source_job_identity")
    require(digest(canonical([row["record"] for row in rows])) == SOURCE_SNAPSHOT
            and digest(canonical(rows)) == logical_hash, "source_snapshot_drift")
    records = []
    for row, metadata in zip(rows, expected):
        record, result = row["record"], row["result"]
        text = record["model_input_text"]
        require(row["ordinal"] == metadata["ordinal"] and isinstance(text, str)
                and 0 < len(text.encode("utf-8")) <= 65536, "source_input_contract")
        require(digest(text) == record["model_input_hash"] == metadata["input_sha256"]
                and type(metadata["route_eligible"]) is bool
                and result["hypothetical_route"] is metadata["route_eligible"], "source_input_drift")
        records.append({"model_input_text": text, "model_input_hash": metadata["input_sha256"]})
    return records


def prepare():
    previous, bindings = {}, {}
    for name, expected in PARENT_HASHES.items():
        path = PRIOR / (name + ".json")
        require(file_hash(path) == expected, "parent_identity_drift")
        previous[name] = json.loads(path.read_text())
        bindings[name] = {"path": str(path.relative_to(ROOT)), "sha256": expected}
    require(previous["run"]["status"] == "Completed" and previous["run"]["completed_events"] == 7
            and previous["verification"]["status"] == "Passed"
            and previous["verification"]["diagnostic_completed"] is True
            and previous["verification"]["safety"]["gate_passed"] is True, "parent_terminal_contract")
    for name, expected in previous["verification"]["source_hashes"].items():
        require(file_hash(ROOT / name) == expected, "parent_artifact_drift")
    sources = dict(previous["plan"]["sources"])
    require(all(file_hash(ROOT / name) == expected for name, expected in sources.items()), "frozen_implementation_drift")
    sources.update({name: file_hash(ROOT / name) for name in ADDITIONAL_SOURCES})
    source_binding = previous["plan"]["parent_bindings"]["plan"]
    source_path = ROOT / source_binding["path"]
    require(file_hash(source_path) == source_binding["sha256"], "source_plan_drift")
    source = json.loads(source_path.read_text())
    require(source["source_job"] == SOURCE_JOB and source["source_snapshot_sha256"] == SOURCE_SNAPSHOT
            and source["source_rows"][:7] == previous["plan"]["source_rows"]
            and [row["route_eligible"] for row in source["source_rows"][:7]] == [False] * 6 + [True], "prefix_identity_drift")
    records = select_records(ROOT / "private/jobs.sqlite3", source["source_rows"], source["source_logical_sha256"])
    plan = {"experiment_id": "EXP-083", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", "planned_events": 347,
            "planned_jobs": 2, "phase_order": [phase["phase"] for phase in PHASES], "phases": list(PHASES),
            "max_seconds": 180, "work_seconds": 150, "max_readiness_seconds": 60, "cleanup_seconds": 15,
            "audit_rate": 0, "seed": 42, "source_job": SOURCE_JOB, "source_snapshot_sha256": SOURCE_SNAPSHOT,
            "source_database": "private/jobs.sqlite3", "source_rows": source["source_rows"],
            "prefix_rows": source["source_rows"][:7], "source_logical_sha256": source["source_logical_sha256"],
            "source_plan_binding": source_binding, "parent_bindings": bindings, "sources": sources,
            "protocol": {"path": str(PROTOCOL.relative_to(ROOT.parent)), "sha256": file_hash(PROTOCOL)},
            "instrumentation_claim": "Original EXP-082 trace; complete M1 task added before the same direct Research entry; not a causal or efficiency benchmark."}
    return plan, records


def check_prelude_result(result, eligible):
    require(isinstance(result, dict) and len(result.get("prediction", [])) == 6
            and all(type(bit) is int and bit in (0, 1) for bit in result["prediction"]), "result_schema")
    require(result.get("route_requested") is False and result.get("hypothetical_route") is eligible
            and result.get("used_path") == "m1" and result.get("fallback_reason") is None, "prelude_result_path")
    counters = result["counters"]
    require(all(type(counters.get(name)) is int and counters[name] == 0
                for name in ("m3_attempts", "m3_succeeded", "m3_cache_hit", "audit_extra_calls")), "prelude_m3_forbidden")
    resources = result["resources"]
    require(resources["peak_rss_bytes"] <= 12 * 1024**3 and resources["mlx_peak_bytes"] == 0, "result_resource_limit")


def process_events(path):
    return [json.loads(line) for line in path.read_text().splitlines(keepends=True) if line.endswith("\n")]


def execute(monitor, records, source_rows, factory, work_deadline, results, report, identity_check=lambda: None):
    jobs, readiness_attempts, cleanups = [], [], []
    failure, count = None, 0
    for phase in PHASES:
        job = runner = None
        readiness = {"phase": phase["phase"], "status": "Waiting", "started_monotonic": time.monotonic(), "indices": []}
        readiness_attempts.append(readiness)
        try:
            require(time.monotonic() < work_deadline, "diagnostic_time_limit")
            report({"phase": phase["phase"], "status": "waiting_for_quiet_window"})
            indices = wait_ready(monitor, work_deadline, 60)
            readiness.update(status="Ready", indices=indices, ended_monotonic=time.monotonic())
            require(not monitor.reason, monitor.reason or "monitoring_failed")
            identity_check()
            require(not monitor.reason, monitor.reason or "monitoring_failed")
            require(time.monotonic() < work_deadline, "diagnostic_time_limit")
            job = {"id": phase["job_id"], "phase": phase["phase"], "mode": phase["mode"], "status": "running",
                   "total_items": phase["planned_events"], "completed_items": 0, "started_monotonic": time.monotonic(),
                   "readiness_indices": indices, "readiness_started_monotonic": readiness["started_monotonic"],
                   "readiness_ended_monotonic": readiness["ended_monotonic"], "normal_exit": False}
            jobs.append(job)
            monitor.set_job(job["id"])
            runner = factory({"id": job["id"], "phase": phase["phase"], "mode": phase["mode"],
                              "request": {"max_qwen_calls": phase["max_qwen_calls"], "audit_rate": 0}})
            report({"phase": phase["phase"], "status": "child_ready", "pid": runner.process.pid})
            for ordinal, record in enumerate(records[:phase["planned_events"]]):
                require(not monitor.reason, monitor.reason or "monitoring_failed")
                require(time.monotonic() < work_deadline, "diagnostic_time_limit")
                result = runner.predict(str(ordinal), record)
                if phase["phase"] == "m1_prelude":
                    check_prelude_result(result, source_rows[ordinal]["route_eligible"])
                else:
                    check_research_result(result, ordinal)
                append(results, {"phase": phase["phase"], "ordinal": ordinal, "input_sha256": record["model_input_hash"], "result": result})
                count += 1
                job["completed_items"] += 1
                if phase["phase"] == "research_prefix" or (ordinal + 1) % 50 == 0 or ordinal + 1 == phase["planned_events"]:
                    report({"phase": phase["phase"], "status": "result_received", "ordinal": ordinal})
            require(job["completed_items"] == phase["planned_events"], "phase_input_count")
            runner.finish()
            require(not monitor.reason, monitor.reason or "monitoring_failed")
            initial = monitor.samples[-1]["index"] if monitor.samples else -1
            observation = wait_absent(monitor, initial, work_deadline, 15)
            job.update(status="completed", normal_exit=True, exit_observation=observation, ended_monotonic=time.monotonic())
            monitor.set_job(None)
        except BaseException as error:
            failure = monitor.reason or safe_error(error)
            readiness.setdefault("ended_monotonic", time.monotonic())
            if readiness["status"] != "Ready":
                readiness.update(status="NotReady", error_code=failure)
            if job is not None:
                start = time.monotonic()
                cleanup = {"phase": phase["phase"], "job_id": job["id"], "started_monotonic": start, "max_seconds": 15,
                           "terminal_confirmed": False, "models_absent_confirmed": False, "normal_exit": False}
                cleanups.append(cleanup)
                try:
                    initial = monitor.samples[-1]["index"] if monitor.samples else -1
                    if runner is not None:
                        runner.close()
                    events = process_events(monitor.events_path)
                    cleanup["terminal_confirmed"] = any(event["type"] == "process_exit" and event["job_id"] == job["id"] for event in events)
                    cleanup["exit_observation"] = wait_absent(monitor, initial, min(work_deadline + 15, start + 15), 15)
                    cleanup["models_absent_confirmed"] = True
                except BaseException as cleanup_error:
                    cleanup["error_code"] = safe_error(cleanup_error)
                cleanup["ended_monotonic"] = time.monotonic()
                job.update(status="cancelled" if monitor.reason else "failed", cleanup=cleanup, ended_monotonic=time.monotonic())
            report({"phase": phase["phase"], "status": "Stopped", "failure_code": failure, "completed_events": count})
            break
    return {"jobs": jobs, "readiness_attempts": readiness_attempts, "cleanups": cleanups,
            "failure_code": failure, "completed_events": count,
            "completed_jobs": sum(job["status"] == "completed" for job in jobs)}


def run():
    os.umask(0o077)
    started, started_at = time.monotonic(), now()
    require(not RUN.exists() and not any(path.is_symlink() for path in (RUN, *RUN.parents)), "attempt_already_used_or_symlink")
    plan, records = prepare()
    environment = environment_metadata()
    RUN.mkdir(parents=True, mode=0o700)
    identity = process_identity(os.getpid())
    identity.pop("raw")
    service = {**identity, "experiment_id": "EXP-083", "root": str(ROOT), "bench_root": str(RUN / "bench"),
               "port": None, "created_at": now(), "role": "diagnostic_supervisor_no_http"}
    once(RUN / "service.json", service)
    once(RUN / "plan.json", plan)
    once(RUN / "run-claim.json", {"experiment_id": "EXP-083", "attempt": 1, "tier": "Minor", "rq": "RQ-S3",
         "started_at": started_at, "started_monotonic": started, "command": sys.argv, "cwd": str(ROOT),
         "environment": environment, "plan_sha256": file_hash(RUN / "plan.json"),
         "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
         "git_status_porcelain": subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=ROOT, text=True).splitlines(),
         "training": False, "gold_accessed": False, "source_network_fetched": False})
    for name in ("process-events.jsonl", "stages.jsonl"):
        descriptor = os.open(RUN / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.close(descriptor)
    descriptor = os.open(RUN / "dispatch.lock", os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    os.environ["TOPICWEB_TELEMETRY"] = "1"
    os.environ["TOPICWEB_EXP082_STAGE_PATH"] = str(RUN / "stages.jsonl")
    monitor = Monitor(RUN / "samples.jsonl", service)
    def request_stop(_signum, _frame):
        monitor.reason = monitor.reason or "diagnostic_interrupted"
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    observed_runner = make_runner_factory(RUN / "process-events.jsonl")
    def factory(job):
        command = ([environment["model_runtime"]["python_executable"], "-m", "topicweb.inference_process"]
                   if job["phase"] == "m1_prelude" else
                   [environment["model_runtime"]["python_executable"], str(ROOT / "scripts/preload_diagnostic_child.py")])
        return observed_runner(job, lock_fd=descriptor, cancelled=lambda: bool(monitor.reason) or time.monotonic() >= started + 150,
                               deadline=started + 150, command=command)
    def identity_check():
        require(all(file_hash(ROOT / name) == expected for name, expected in plan["sources"].items()), "implementation_identity_drift")
        require(file_hash(PROTOCOL) == plan["protocol"]["sha256"], "protocol_identity_drift")
    outcome = {"jobs": [], "readiness_attempts": [], "cleanups": [], "failure_code": None, "completed_events": 0, "completed_jobs": 0}
    with (RUN / "results.jsonl").open("x") as results, (RUN / "stdout.log").open("x") as output:
        def report(value):
            append(output, value)
            print(canonical(value), flush=True)
        try:
            monitor.start()
            outcome = execute(monitor, records, plan["source_rows"], factory, started + 150, results, report, identity_check)
        except BaseException as error:
            outcome["failure_code"] = monitor.reason or safe_error(error)
        finally:
            try:
                monitor.finish()
            except BaseException as error:
                outcome["failure_code"] = outcome["failure_code"] or safe_error(error)
            os.close(descriptor)
        outcome["failure_code"] = outcome["failure_code"] or monitor.reason
        try:
            identity_check()
            select_records(ROOT / "private/jobs.sqlite3", plan["source_rows"], plan["source_logical_sha256"])
        except BaseException as error:
            outcome["failure_code"] = outcome["failure_code"] or safe_error(error)
        report({"status": "Completed" if outcome["failure_code"] is None else "Stopped",
                "completed_events": outcome["completed_events"], "failure_code": outcome["failure_code"]})
    events = process_events(RUN / "process-events.jsonl")
    child_exits = []
    for job in outcome["jobs"]:
        owned = [event for event in events if event["job_id"] == job["id"]]
        exits = [event for event in owned if event["type"] == "process_exit"]
        child_exits.append({"id": job["id"], "phase": job["phase"], "child_launched": any(event.get("pid") is not None for event in owned),
                            "returncode": exits[-1]["returncode"] if exits else None})
    ended = time.monotonic()
    if ended - started > 180:
        outcome["failure_code"] = outcome["failure_code"] or "diagnostic_total_time_limit"
    artifacts = ("service.json", "plan.json", "run-claim.json", "results.jsonl", "samples.jsonl", "process-events.jsonl", "stages.jsonl", "stdout.log")
    terminal = {"experiment_id": "EXP-083", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", **outcome,
                "status": "Completed" if outcome["failure_code"] is None else "Stopped",
                "started_at": started_at, "ended_at": now(), "started_monotonic": started, "ended_monotonic": ended,
                "elapsed_seconds": ended - started, "planned_events": 347, "planned_jobs": 2,
                "total_budget_exceeded": ended - started > 180, "child_exit_summary": child_exits,
                "plan_sha256": file_hash(RUN / "plan.json"),
                "source_hashes": {str((RUN / name).relative_to(ROOT)): file_hash(RUN / name) for name in artifacts},
                "training": False, "gold_accessed": False, "source_network_fetched": False,
                "operational_followup_authorized": False}
    once(RUN / "run.json", terminal)
    return 0 if terminal["status"] == "Completed" else 1


if __name__ == "__main__":
    if sys.argv[1:] in (["--help"], ["-h"]):
        print("EXP-083 run: 340 M1-only then seven Research inputs; unchanged tracing and safety gates.")
    elif sys.argv[1:] == ["run"]:
        raise SystemExit(run())
    else:
        raise SystemExit("usage: run_preload_diagnostic.py run")
