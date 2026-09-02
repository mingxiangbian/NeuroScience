"""EXP-084: finish M1, then transfer its receipts to an independent M3 process."""
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

RUN = ROOT / "private/validation/exp-084/attempt-1"
PRIOR = ROOT / "private/validation/exp-083/attempt-1"
PROTOCOL = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-084-m1-transfer-memory-prototype.md"
SOURCE_JOB = "5ab3326150ee448ba326233264967d34"
SOURCE_SNAPSHOT = "cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16"
PARENT_HASHES = {
    "plan": "daf611f054a0f870491651798b2f7bd24fbfb30181c41ea88776df14f18fe559",
    "run": "1b566d0007ae3bbb6bcfa194472c77ab50ab27cd6ebebec4f0373826f488e417",
    "verification": "7276798a09f641f36ba9017af8768cc786c39e4564cd1a5974a3bd7880363a09",
}
ADDITIONAL_SOURCES = (
    "scripts/run_transfer_diagnostic.py", "scripts/transferred_m3_child.py", "scripts/verify_transfer_diagnostic.py",
    "tests/test_transfer_diagnostic.py", "tests/test_transferred_m3_child.py", "tests/test_verify_transfer_diagnostic.py",
)
PHASES = (
    {"phase": "m1_prelude", "job_id": "exp084-m1-prelude", "mode": "m1_only", "planned_events": 340, "max_qwen_calls": 0},
    {"phase": "research_prefix", "job_id": "exp084-m3-replay", "mode": "research", "planned_events": 7, "max_qwen_calls": 1},
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
    require(previous["run"]["status"] == "Stopped" and previous["run"]["failure_code"] == "swap_thrashing"
            and previous["verification"]["status"] == "Passed"
            and previous["verification"]["diagnostic_completed"] is False
            and previous["verification"]["safety"]["gate_passed"] is False, "parent_terminal_contract")
    for name, expected in previous["verification"]["source_hashes"].items():
        require(file_hash(ROOT / name) == expected, "parent_artifact_drift")
    sources = dict(previous["plan"]["sources"])
    require(all(file_hash(ROOT / name) == expected for name, expected in sources.items()), "frozen_implementation_drift")
    sources.update({name: file_hash(ROOT / name) for name in ADDITIONAL_SOURCES})
    references = dict(previous["plan"]["parent_bindings"])
    for name, binding in references.items():
        require(binding["path"] == f"private/validation/exp-082/attempt-1/{name}.json"
                and file_hash(ROOT/binding["path"]) == binding["sha256"], "reference_identity_drift")
    reference_verification = json.loads((ROOT/references["verification"]["path"]).read_text())
    require(reference_verification["status"] == "Passed" and reference_verification["diagnostic_completed"] is True, "reference_not_verified")
    reference_results = "private/validation/exp-082/attempt-1/results.jsonl"
    references["results"] = {"path": reference_results, "sha256": reference_verification["source_hashes"][reference_results]}
    require(file_hash(ROOT/reference_results) == references["results"]["sha256"], "reference_results_drift")
    source_binding = previous["plan"]["source_plan_binding"]
    source_path = ROOT / source_binding["path"]
    require(file_hash(source_path) == source_binding["sha256"], "source_plan_drift")
    source = json.loads(source_path.read_text())
    require(source["source_job"] == SOURCE_JOB and source["source_snapshot_sha256"] == SOURCE_SNAPSHOT
            and source["source_rows"][:7] == previous["plan"]["prefix_rows"]
            and [row["route_eligible"] for row in source["source_rows"][:7]] == [False] * 6 + [True], "prefix_identity_drift")
    records = select_records(ROOT / "private/jobs.sqlite3", source["source_rows"], source["source_logical_sha256"])
    plan = {"experiment_id": "EXP-084", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", "planned_events": 347,
            "planned_jobs": 2, "phase_order": [phase["phase"] for phase in PHASES], "phases": list(PHASES),
            "max_seconds": 180, "work_seconds": 150, "max_readiness_seconds": 60, "cleanup_seconds": 15,
            "audit_rate": 0, "seed": 42, "source_job": SOURCE_JOB, "source_snapshot_sha256": SOURCE_SNAPSHOT,
            "source_database": "private/jobs.sqlite3", "source_rows": source["source_rows"],
            "prefix_rows": source["source_rows"][:7], "source_logical_sha256": source["source_logical_sha256"],
            "source_plan_binding": source_binding, "parent_bindings": bindings, "reference_bindings": references,
            "sources": sources, "strategy": "m1-receipt-transfer-v1",
            "protocol": {"path": str(PROTOCOL.relative_to(ROOT.parent)), "sha256": file_hash(PROTOCOL)},
            "instrumentation_claim": "M1 process exits before M3; current-run receipts replace second M1 model and work. Functional equivalence only, not execution or causal equivalence."}
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


def seal_transfer(path, results_path, source_rows, job):
    require(job["id"] == "exp084-m1-prelude" and job["status"] == "completed"
            and job["completed_items"] == 340 and job["normal_exit"] is True
            and isinstance(job.get("exit_observation"), dict), "prelude_not_sealed")
    expected_hash = file_hash(results_path)
    raw = results_path.read_bytes()
    require(digest(raw) == expected_hash and raw.endswith(b"\n"), "prelude_results_drift")
    rows = [json.loads(line) for line in raw.splitlines()]
    require(len(rows) == 340 and [row["ordinal"] for row in rows] == list(range(340))
            and all(row["phase"] == "m1_prelude" for row in rows), "prelude_results_incomplete")
    fingerprints = {row["result"]["fingerprint"] for row in rows}
    require(len(fingerprints) == 1, "prelude_fingerprint_drift")
    entries = []
    for row, planned in zip(rows[:7], source_rows[:7]):
        require(row["input_sha256"] == planned["input_sha256"], "transfer_input_identity")
        entries.append({"ordinal": row["ordinal"], "input_sha256": row["input_sha256"],
                        "m1_probabilities": row["result"]["m1_probabilities"],
                        "tokenlengths": {"m1": row["result"]["tokenlengths"]["m1"]},
                        "source_result_sha256": digest(canonical(row))})
    transfer = {"experiment_id": "EXP-084", "attempt": 1, "source_job_id": job["id"], "source_phase": "m1_prelude",
                "source_results_path": str(results_path.relative_to(ROOT)), "source_results_sha256": expected_hash,
                "source_results_count": 340, "fingerprint": next(iter(fingerprints)), "entries": entries}
    once(path, transfer)
    return file_hash(path)


def check_replay_result(result, ordinal):
    check_research_result(result, ordinal)
    require(result.get("prelude_transfer_reuse") is True
            and result.get("m1_execution_origin") == "current_run_m1_prelude_receipt"
            and type(result["counters"].get("m1_attempts")) is int and result["counters"]["m1_attempts"] == 0
            and type(result["counters"].get("m1_cache_hit")) is int and result["counters"]["m1_cache_hit"] == 1,
            "replay_cost_or_origin")


def execute(monitor, records, source_rows, factory, work_deadline, results, report,
            identity_check=lambda: None, on_prelude_complete=lambda _: None):
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
                    check_replay_result(result, ordinal)
                append(results[phase["phase"]], {"phase": phase["phase"], "ordinal": ordinal, "input_sha256": record["model_input_hash"], "result": result})
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
            if phase["phase"] == "m1_prelude":
                require(not monitor.reason, monitor.reason or "monitoring_failed")
                on_prelude_complete(job)
        except BaseException as error:
            failure = monitor.reason or safe_error(error)
            readiness.setdefault("ended_monotonic", time.monotonic())
            if readiness["status"] != "Ready":
                readiness.update(status="NotReady", error_code=failure)
            if job is not None and job["status"] != "completed":
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
    service = {**identity, "experiment_id": "EXP-084", "root": str(ROOT), "bench_root": str(RUN / "bench"),
               "port": None, "created_at": now(), "role": "diagnostic_supervisor_no_http"}
    once(RUN / "service.json", service)
    once(RUN / "plan.json", plan)
    once(RUN / "run-claim.json", {"experiment_id": "EXP-084", "attempt": 1, "tier": "Minor", "rq": "RQ-S3",
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
    os.environ["TOPICWEB_EXP084_STAGE_PATH"] = str(RUN / "stages.jsonl")
    monitor = Monitor(RUN / "samples.jsonl", service)
    def request_stop(_signum, _frame):
        monitor.reason = monitor.reason or "diagnostic_interrupted"
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    observed_runner = make_runner_factory(RUN / "process-events.jsonl")
    def factory(job):
        command = ([environment["model_runtime"]["python_executable"], "-m", "topicweb.inference_process"]
                   if job["phase"] == "m1_prelude" else
                   [environment["model_runtime"]["python_executable"], str(ROOT / "scripts/transferred_m3_child.py")])
        return observed_runner(job, lock_fd=descriptor, cancelled=lambda: bool(monitor.reason) or time.monotonic() >= started + 150,
                               deadline=started + 150, command=command)
    def identity_check():
        require(all(file_hash(ROOT / name) == expected for name, expected in plan["sources"].items()), "implementation_identity_drift")
        require(file_hash(PROTOCOL) == plan["protocol"]["sha256"], "protocol_identity_drift")
    def on_prelude_complete(job):
        identity_check()
        os.environ["TOPICWEB_EXP084_TRANSFER_SHA256"] = seal_transfer(
            RUN/"transfer.json", RUN/"m1-results.jsonl", plan["source_rows"], job)
    outcome = {"jobs": [], "readiness_attempts": [], "cleanups": [], "failure_code": None, "completed_events": 0, "completed_jobs": 0}
    with (RUN/"m1-results.jsonl").open("x") as m1_results, (RUN/"replay-results.jsonl").open("x") as replay_results, (RUN/"stdout.log").open("x") as output:
        def report(value):
            append(output, value)
            print(canonical(value), flush=True)
        try:
            monitor.start()
            outcome = execute(monitor, records, plan["source_rows"], factory, started + 150,
                              {"m1_prelude": m1_results, "research_prefix": replay_results}, report,
                              identity_check, on_prelude_complete)
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
    artifacts = ("service.json", "plan.json", "run-claim.json", "m1-results.jsonl", "replay-results.jsonl",
                 "samples.jsonl", "process-events.jsonl", "stages.jsonl", "stdout.log")
    optional = ("transfer.json", "m3-ready.json")
    missing = [name for name in optional if not (RUN/name).exists()]
    artifacts += tuple(name for name in optional if name not in missing)
    terminal = {"experiment_id": "EXP-084", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", **outcome,
                "status": "Completed" if outcome["failure_code"] is None else "Stopped",
                "started_at": started_at, "ended_at": now(), "started_monotonic": started, "ended_monotonic": ended,
                "elapsed_seconds": ended - started, "planned_events": 347, "planned_jobs": 2,
                "total_budget_exceeded": ended - started > 180, "child_exit_summary": child_exits,
                "plan_sha256": file_hash(RUN / "plan.json"),
                "source_hashes": {str((RUN / name).relative_to(ROOT)): file_hash(RUN / name) for name in artifacts},
                "artifacts_missing": missing,
                "training": False, "gold_accessed": False, "source_network_fetched": False,
                "operational_followup_authorized": False}
    once(RUN / "run.json", terminal)
    return 0 if terminal["status"] == "Completed" else 1


if __name__ == "__main__":
    if sys.argv[1:] in (["--help"], ["-h"]):
        print("EXP-084 run: 340 M1-only then seven Research inputs; unchanged tracing and safety gates.")
    elif sys.argv[1:] == ["run"]:
        raise SystemExit(run())
    else:
        raise SystemExit("usage: run_transfer_diagnostic.py run")
