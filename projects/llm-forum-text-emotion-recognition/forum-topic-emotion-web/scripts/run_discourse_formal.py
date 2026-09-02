"""EXP-080 isolated Discourse Research task, gated by EXP-079 and live safety."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
RUN = ROOT / "private/validation/exp-080/attempt-1"
BENCH = RUN / "bench"
PRIOR = ROOT / "private/validation/exp-079/attempt-3"
PROTOCOL = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-080-discourse-formal-topic-run.md"
DECISION = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/dec-phase-c1-bounded-operational-validation-v1.md"
SOURCE_PROTOCOL = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-078-discourse-operational.md"
OBSERVER_CORRECTION = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-079-observer-correction-attempt-2.md"
BACKGROUND_REDUCTION = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-079-reduced-background-attempt-3.md"
REVIEW = ROOT / "docs/discourse-source-review.md"
MAX_SECONDS = 3600
QUERY = {"site": "discuss.python.org", "category_id": 7, "max_topics": 100, "max_items": 400}
ADDITIONAL_SOURCES = {
    "scripts/run_discourse_formal.py", "scripts/verify_discourse_formal.py", "tests/test_discourse_formal.py",
    "scripts/verify_discourse_validation.py", "scripts/verify_local.py",
}
TERMINAL = {"completed", "completed_with_fallback", "failed", "cancelled"}


class FormalError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def ensure(condition, code):
    if not condition:
        raise FormalError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def file_hash(path):
    ensure(path.is_file() and not any(item.is_symlink() for item in (path, *path.parents)), "source_unavailable")
    return digest(path.read_bytes())


def once(path, value):
    ensure(not any(item.is_symlink() for item in (path, *path.parents)), "artifact_symlink")
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def prior_gate(run, verification, *, run_hash, plan_hash):
    prefix = "private/validation/exp-079/attempt-3/"
    ensure(run.get("experiment_id") == "EXP-079" and run.get("status") == "Completed"
           and run.get("failure_code") is None and run.get("plan_sha256") == plan_hash, "exp079_run_not_safe")
    ensure(verification.get("experiment_id") == "EXP-079" and verification.get("status") == "Passed"
           and verification.get("exp079_complete") is True
           and verification.get("operational_state") == "safe-to-continue", "exp079_verification_not_safe")
    bindings = verification.get("source_hashes", {})
    ensure(bindings.get(prefix + "run.json") == run_hash and bindings.get(prefix + "plan.json") == plan_hash,
           "exp079_hash_binding")


def source_scope(prior_sources, current_sources):
    ensure(isinstance(prior_sources, dict) and prior_sources and isinstance(current_sources, dict)
           and set(prior_sources) <= set(current_sources)
           and set(current_sources) - set(prior_sources) <= ADDITIONAL_SOURCES
           and all(current_sources[name] == value for name, value in prior_sources.items()), "exp079_dependency_drift")


def load_prior():
    paths = {key: PRIOR / (key + ".json") for key in ("run", "verification", "plan")}
    bindings = {key: {"path": str(path.relative_to(ROOT)), "sha256": file_hash(path)} for key, path in paths.items()}
    previous = {key: json.loads(path.read_text()) for key, path in paths.items()}
    prior_gate(previous["run"], previous["verification"], run_hash=bindings["run"]["sha256"], plan_hash=bindings["plan"]["sha256"])
    ensure(previous["plan"].get("reduced_background_sha256") == file_hash(BACKGROUND_REDUCTION), "exp079_background_note_drift")
    sources = previous["plan"].get("sources")
    ensure(isinstance(sources, dict) and sources, "exp079_sources_missing")
    current = {}
    for name in set(sources) | ADDITIONAL_SOURCES:
        relative = Path(name)
        ensure(not relative.is_absolute() and ".." not in relative.parts
               and (relative.parts[0] in {"topicweb", "scripts", "tests", "static"}
                    or name in {"requirements.txt", "requirements-lock.txt", "start.py"}), "source_path")
        current[name] = file_hash(ROOT / relative)
    source_scope(sources, current)
    return bindings, current


def api(path, payload=None, *, timeout=10):
    token_file = BENCH / "access-token"
    file_hash(token_file)
    token = token_file.read_text().strip()
    ensure(bool(token), "api_token_missing")
    request = Request("http://127.0.0.1:8790/api/" + path,
                      data=canonical(payload).encode() if payload is not None else None,
                      headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
    ensure(len(raw) <= 2 * 1024 * 1024, "api_response_limit")
    data = json.loads(raw)
    ensure(isinstance(data, dict), "api_response_contract")
    return data


def database_job_ids(database):
    ensure(database.is_file() and not any(path.is_symlink() for path in (database, *database.parents)), "bench_database_missing")
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        return [row[0] for row in db.execute("SELECT id FROM jobs")]


def safe_code(error):
    code = error.code if isinstance(error, FormalError) else str(error) if isinstance(error, RuntimeError) else "driver_error"
    return code if isinstance(code, str) and re.fullmatch(r"[a-z0-9_]{1,96}", code) else "driver_error"


def execute(monitor, support, *, call=api, clock=time.monotonic, sleeper=time.sleep, report=lambda value: None, deadline=None):
    started = clock()
    deadline = min(started + MAX_SECONDS, deadline) if deadline is not None else started + MAX_SECONDS
    jobs, readiness_attempts, failure, cleanup = [], [], None, None
    identifier = None
    submission_attempted = False
    try:
        waiting = {"status": "Waiting", "started_monotonic": clock(), "readiness_indices": []}
        readiness_attempts.append(waiting)
        before = monitor.samples[-1]["index"] if monitor.samples else -1
        try:
            readiness = support.wait_ready(monitor, deadline, timeout=60)
            waiting.update(status="Ready", readiness_indices=readiness)
        except Exception as error:
            waiting.update(status="NotReady", error_code=safe_code(error))
            raise
        finally:
            waiting["ended_monotonic"] = clock()
            waiting["observed_sample_indices"] = [row["index"] for row in monitor.samples if row["index"] > before]
        ensure(not monitor.reason and clock() < deadline, monitor.reason or "total_time_limit")
        entry = {"readiness_indices": readiness, "readiness_started_monotonic": waiting["started_monotonic"],
                 "readiness_ended_monotonic": waiting["ended_monotonic"], "started_monotonic": clock(),
                 "mode": "research", "source": "discourse", "cost_complete": False}
        jobs.append(entry)
        submission_attempted = True
        submitted = call("jobs", {"name": "EXP-080 / Python Help / formal public-topic prefix", "source": "discourse",
                                   "mode": "research", "max_qwen_calls": 500, "audit_rate": 0, "query": QUERY.copy()})
        identifier = submitted.get("job", {}).get("id")
        ensure(isinstance(identifier, str) and re.fullmatch(r"[0-9a-f]{32}", identifier), "submitted_job_identity")
        entry.update(id=identifier, state="submitted", status="submitted", http_submission_acknowledged=True)
        monitor.set_job(identifier)
        report({"stage": "submitted", "job_id": identifier})
        previous = None
        while True:
            ensure(clock() < deadline, "total_time_limit")
            ensure(not monitor.reason, monitor.reason or "monitor_failure")
            job = call("jobs/" + identifier)["job"]
            ensure(job.get("id") == identifier, "job_identity")
            state = (job.get("state"), job.get("completed_items"), job.get("total_items"))
            if state != previous:
                report({"stage": state[0], "completed_items": state[1], "total_items": state[2]})
                previous = state
            if job.get("state") in TERMINAL:
                break
            sleeper(.25)
        entry.update({key: job.get(key) for key in ("state", "error_code", "total_items", "completed_items", "snapshot_hash", "manifest", "progress")})
        entry["status"] = job["state"]
        entry["ended_monotonic"] = clock()
        entry["elapsed_seconds"] = entry["ended_monotonic"] - entry["started_monotonic"]
        if job.get("snapshot_hash"):
            entry["private_snapshot"] = {"database": "private/validation/exp-080/attempt-1/bench/jobs.sqlite3",
                                          "job_id": identifier, "snapshot_sha256": job["snapshot_hash"]}
            entry["manifest_sha256"] = digest(canonical(job["manifest"]))
        entry["dashboard"] = call("jobs/" + identifier + "/dashboard")
        ensure(job.get("state") == "completed" and job.get("error_code") is None, "runtime_job_failed")
        ensure(type(job.get("total_items")) is int and 300 <= job["total_items"] <= 400
               and job.get("completed_items") == job["total_items"], "source_sample_or_coverage")
        ensure(not monitor.reason, monitor.reason or "monitor_failure")
        after_index = monitor.samples[-1]["index"] if monitor.samples else -1
        entry["exit_observation"] = support.wait_absent(monitor, after_index, deadline, timeout=15)
        entry.update(normal_exit=True, production_final_gate="completed_state_after_exit0", cost_complete=True)
        ensure(not monitor.reason and clock() <= deadline, monitor.reason or "total_time_limit")
        monitor.set_job(None)
    except Exception as error:
        failure = safe_code(error)
        if identifier is None and submission_attempted:
            # A lost HTTP acknowledgement never causes a second submission.
            try:
                ids = database_job_ids(BENCH / "jobs.sqlite3")
            except Exception:
                ids = []
            if len(ids) == 1:
                identifier = ids[0]
                jobs[-1]["id"] = identifier
                jobs[-1]["http_submission_acknowledged"] = False
            else:
                jobs[-1]["submission_outcome"] = "unknown"
        if identifier:
            cleanup_deadline = clock() + 15
            try:
                cleanup = support.cancel_and_confirm(identifier, call, monitor, timeout=15)
            except Exception:
                cleanup = {"normal_exit": False, "terminal_confirmed": False, "models_absent_confirmed": False,
                           "exit_observation": None, "error_code": "cleanup_observation_unknown",
                           "started_monotonic": cleanup_deadline-15, "ended_monotonic": clock(), "max_seconds": 15}
            jobs[-1]["cleanup"] = cleanup
            jobs[-1]["exit_observation"] = cleanup.get("exit_observation")
            try:
                remaining = cleanup_deadline - clock()
                ensure(remaining > 0, "cleanup_observation_unknown")
                job = call("jobs/" + identifier, timeout=min(10, remaining))["job"]
                jobs[-1].update({key: job.get(key) for key in ("state", "error_code", "total_items", "completed_items", "snapshot_hash", "manifest", "progress")})
                jobs[-1]["status"] = job["state"]
                jobs[-1]["ended_monotonic"] = clock()
                jobs[-1]["elapsed_seconds"] = clock() - jobs[-1]["started_monotonic"]
                if job.get("snapshot_hash"):
                    jobs[-1]["private_snapshot"] = {"database": "private/validation/exp-080/attempt-1/bench/jobs.sqlite3",
                                                     "job_id": identifier, "snapshot_sha256": job["snapshot_hash"]}
                    jobs[-1]["manifest_sha256"] = digest(canonical(job["manifest"]))
                    remaining = cleanup_deadline - clock()
                    ensure(remaining > 0, "cleanup_observation_unknown")
                    jobs[-1]["dashboard"] = call("jobs/" + identifier + "/dashboard", timeout=min(10, remaining))
            except Exception:
                jobs[-1]["final_job_observation"] = "unknown"
        monitor.set_job(None)
    return {"status": "Stopped" if failure else "Completed", "failure_code": failure, "jobs": jobs, "readiness": readiness_attempts,
            "cleanup": cleanup, "elapsed_seconds": clock() - started,
            "unacknowledged_model_attempts": "unknown" if failure else "not_applicable_completed_job"}


def run(support):
    prior, sources = load_prior()
    service = support.load_service(RUN, 8790)
    ensure(service.get("experiment_id") == "EXP-080" and service.get("bench_root") == str(BENCH), "service_experiment_identity")
    ensure(not database_job_ids(BENCH / "jobs.sqlite3"), "bench_not_empty")
    ensure(not (RUN / "plan.json").exists() and not (RUN / "run.json").exists(), "attempt_already_used")
    plan = {"experiment_id": "EXP-080", "tier": "Minor", "rq": "RQ-S3", "query": QUERY.copy(), "mode": "research",
            "max_qwen_calls": 500, "audit_rate": 0, "seed": 42, "sources": sources, "prior_exp079": prior,
            "protocol_sha256": file_hash(PROTOCOL), "decision_sha256": file_hash(DECISION),
            "source_protocol_sha256": file_hash(SOURCE_PROTOCOL), "source_review_sha256": file_hash(REVIEW),
            "observer_correction_path": str(OBSERVER_CORRECTION.relative_to(ROOT.parent)),
            "observer_correction_sha256": file_hash(OBSERVER_CORRECTION),
            "background_reduction_path": str(BACKGROUND_REDUCTION.relative_to(ROOT.parent)),
            "background_reduction_sha256": file_hash(BACKGROUND_REDUCTION),
            "service": service, "service_sha256": file_hash(RUN / "service.json"),
            "maximum_seconds": MAX_SECONDS, "planned_jobs": 1, "planned_records_min": 300, "planned_records_max": 400,
            "environment": support.environment_metadata()}
    ensure(plan["environment"] == json.loads((PRIOR / "run.json").read_text()).get("environment"), "environment_changed_after_exp079")
    os.umask(0o077)
    once(RUN / "plan.json", plan)
    started, started_at = time.monotonic(), datetime.now(timezone.utc).isoformat()
    once(RUN / "run-claim.json", {"experiment_id": "EXP-080", "plan_sha256": file_hash(RUN / "plan.json"),
                                   "started_at": started_at, "started_monotonic": started, "command": sys.argv, "cwd": str(ROOT),
                                   "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                                   "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT))})
    monitor = support.Monitor(RUN / "system-process-samples.jsonl", service)
    result = {"status": "Stopped", "failure_code": "monitor_not_started", "jobs": [], "readiness": [], "cleanup": None, "elapsed_seconds": 0,
              "unacknowledged_model_attempts": "unknown"}
    with (RUN / "stdout.log").open("x", encoding="utf-8") as stdout:
        def report(value):
            line = canonical(value)
            print(line, flush=True)
            stdout.write(line + "\n")
            stdout.flush()
        try:
            monitor.start()
            result = execute(monitor, support, report=report, deadline=started + MAX_SECONDS)
        except Exception as error:
            result.update(status="Stopped", failure_code=safe_code(error))
        finally:
            try:
                monitor.finish()
            except Exception:
                result.update(status="Stopped", failure_code="monitor_shutdown_unknown")
            if monitor.reason:
                result.update(status="Stopped", failure_code=result.get("failure_code") or monitor.reason)
            try:
                if any(file_hash(ROOT / name) != hashed for name, hashed in sources.items()):
                    result.update(status="Stopped", failure_code="implementation_drift")
                if (file_hash(PROTOCOL) != plan["protocol_sha256"] or file_hash(DECISION) != plan["decision_sha256"]
                        or file_hash(SOURCE_PROTOCOL) != plan["source_protocol_sha256"] or file_hash(REVIEW) != plan["source_review_sha256"]
                        or file_hash(OBSERVER_CORRECTION) != plan["observer_correction_sha256"]
                        or file_hash(BACKGROUND_REDUCTION) != plan["background_reduction_sha256"]):
                    result.update(status="Stopped", failure_code="protocol_drift")
                if any(file_hash(ROOT / item["path"]) != item["sha256"] for item in prior.values()):
                    result.update(status="Stopped", failure_code="prior_terminal_drift")
            except Exception:
                result.update(status="Stopped", failure_code="identity_observation_unknown")
            hashes = {}
            for key, path in (("samples_sha256", RUN / "system-process-samples.jsonl"),
                              ("process_events_sha256", RUN / "process-events.jsonl")):
                try:
                    hashes[key] = file_hash(path)
                except Exception:
                    hashes[key] = None
                    result.update(status="Stopped", failure_code="monitor_artifact_unknown")
            ended = time.monotonic()
            result.update(experiment_id="EXP-080", tier="Minor", stage="discourse_formal", attempt=1,
                          plan_sha256=file_hash(RUN / "plan.json"), ended_at=datetime.now(timezone.utc).isoformat(),
                          run_claim_sha256=file_hash(RUN / "run-claim.json"), started_at=started_at,
                          started_monotonic=started, ended_monotonic=ended, elapsed_seconds=ended - started,
                          training=False, gold_accessed=False,
                          validation_accessed=False, test_accessed=False, raw_read_by_driver=False,
                          **hashes,
                          claim_boundary="One bounded unlabelled cross-platform operational run, not external accuracy or a production SLA.")
            once(RUN / "run.json", result)
            report({"experiment_id": "EXP-080", "status": result["status"], "failure_code": result["failure_code"]})
    return 0 if result["status"] == "Completed" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("serve", "run"))
    command = parser.parse_args(argv).command
    support = importlib.import_module("bounded_runtime_support")
    if command == "serve":
        return support.serve_app(RUN, "EXP-080", 8790)
    try:
        return run(support)
    except Exception as error:
        print(safe_code(error), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
