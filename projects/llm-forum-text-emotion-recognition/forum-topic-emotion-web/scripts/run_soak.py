"""EXP-077 finite HTTP-to-worker soak. Only run after protocol/code freeze."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sqlite3
import statistics
import subprocess
import sys
import threading
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from topicweb.telemetry import system_memory

RUN = ROOT / "private/validation/exp-077/attempt-1"
BENCH = RUN / "bench"
SOURCE_JOB = "5ab3326150ee448ba326233264967d34"
SOURCE_SNAPSHOT = "cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16"
PROTOCOL = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-077-runtime-soak-v2.md"
MODES = ("m1_only", "research", "demo")
PHASES = ("warmup", "measured", "cache_tail")
COSTS = ("m1_attempts", "m3_attempts", "m3_succeeded", "m1_cache_hit", "m3_cache_hit", "audit_extra_calls")
MAX_SECONDS = 3600
NONDEPENDENT_C3 = {"scripts/run_discourse_validation.py", "scripts/verify_discourse_validation.py", "tests/test_discourse_validation.py"}
MODEL_CONFIG = ROOT.parent / "experiments/stack-overflow-emotion-gold/oof-router/runs/exp-066-headless-runtime-parity/attempt-2/frozen-sources/config.json"
MODEL_CONFIG_SHA = "106db4b86614ac70c84f04a322b046bc1049686099c590997955120993bb9983"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def latency_distribution(values):
    ordered = sorted(values)
    def quantile(probability):
        position = (len(ordered)-1)*probability
        lower = int(position)
        return ordered[lower]+(ordered[min(lower+1,len(ordered)-1)]-ordered[lower])*(position-lower)
    return {"n": len(ordered), "min": ordered[0], "median": quantile(.5),
            "p90": quantile(.9), "p95": quantile(.95), "max": ordered[-1]}


def ensure(condition, code):
    if not condition:
        raise RuntimeError(code)


def environment_metadata(command=None):
    """Read distribution/platform metadata only; never import a model backend."""
    def read(arguments, env=None):
        return subprocess.run(arguments, capture_output=True, text=True, check=True, timeout=10, env=env).stdout
    command = command or read
    lock = ROOT / "requirements-lock.txt"
    pinned = dict(line.split("==",1) for line in lock.read_text().splitlines() if line.strip() and not line.startswith("#"))
    actual = {name: importlib.metadata.version(name) for name in pinned}
    ensure(actual == pinned, "website_package_identity_drift")
    ensure(digest(MODEL_CONFIG.read_bytes()) == MODEL_CONFIG_SHA, "model_metadata_config_drift")
    expected = json.loads(MODEL_CONFIG.read_text())["environment"]
    code = (
        "import importlib.metadata,json,os,platform,sys; "
        "spec=json.loads(sys.argv[1]); "
        "print(json.dumps({'python_executable':sys.executable,'python_version':platform.python_version(),"
        "'architecture':platform.machine(),'packages':{name:importlib.metadata.version(name.replace('_','-')) for name in spec['packages']},"
        "'offline_environment':{name:os.environ.get(name) for name in spec['offline_environment']}},sort_keys=True))"
    )
    model_env = {**os.environ, **expected["offline_environment"]}
    observed = json.loads(command([expected["python_executable"], "-I", "-c", code, canonical(expected)], env=model_env))
    ensure(observed == expected, "model_package_identity_drift")
    memory = int(command(["/usr/sbin/sysctl", "-n", "hw.memsize"]).strip())
    cpu = command(["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"]).strip()
    ensure(memory > 0 and cpu, "hardware_metadata_unavailable")
    installed = {distribution.metadata["Name"]: distribution.version for distribution in importlib.metadata.distributions()}
    return {
        "website": {"python_executable": sys.executable, "python_version": platform.python_version(),
                    "architecture": platform.machine(), "platform": platform.platform(), "packages": actual,
                    "installed_distribution_inventory": installed},
        "model_runtime": observed,
        "model_config": {"path": str(MODEL_CONFIG.relative_to(ROOT.parent)), "sha256": MODEL_CONFIG_SHA},
        "requirements_lock": {"path": "requirements-lock.txt", "sha256": digest(lock.read_bytes()), "packages": pinned},
        "hardware": {"architecture": platform.machine(), "platform": platform.platform(), "cpu_model": cpu,
                     "logical_cpus": os.cpu_count(), "physical_memory_bytes": memory,
                     "gpu_metadata": "Not separately initialized; inherited frozen MLX backend and per-event memory observations."},
    }


def once(path, value):
    ensure(not any(p.is_symlink() for p in (path, *path.parents)), "artifact_symlink")
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_job(database, identifier):
    ensure(database.is_file() and not any(p.is_symlink() for p in (database, *database.parents)), "database_unavailable")
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone()
        ensure(row is not None, "source_job_missing")
        job = dict(row)
        rows = [{"ordinal": row["ordinal"], "record": json.loads(row["record"]),
                 "result": json.loads(row["result"]) if row["result"] else None}
                for row in db.execute("SELECT ordinal,record,result FROM items WHERE job_id=? ORDER BY ordinal", (identifier,))]
    return job, rows


def traffic_plan(rows):
    ensure(len(rows) == 340 and [row["ordinal"] for row in rows] == list(range(340)), "source_ordinal_contract")
    unique, metadata = {}, []
    for row in rows:
        text = row["record"]["model_input_text"]
        hashed = digest(text)
        eligible = row["result"].get("hypothetical_route")
        ensure(type(eligible) is bool and hashed == row["record"]["model_input_hash"], "source_input_contract")
        meta = {"source_ordinal": row["ordinal"], "input_sha256": hashed, "characters": len(text), "route_eligible": eligible}
        metadata.append(meta)
        if hashed in unique:
            ensure(unique[hashed]["route_eligible"] == eligible, "source_route_identity")
        else:
            unique[hashed] = meta
    ensure(len(unique) == 338 and sum(row["route_eligible"] for row in metadata) == 25, "source_fixture_identity")
    warmup = []
    for eligible in (True, False):
        candidates = sorted((row for row in unique.values() if row["route_eligible"] is eligible),
                            key=lambda row: (-row["characters"], row["source_ordinal"]))
        ensure(len(candidates) >= 8, "warmup_pool_insufficient")
        warmup.extend(row["source_ordinal"] for row in candidates[:8])
    schedule = [("warmup", index) for index in warmup] + [("measured", index) for index in range(340)] + [("cache_tail", index) for index in range(64)]
    events, payload = [], []
    for ordinal, (phase, source_ordinal) in enumerate(schedule):
        events.append({"ordinal": ordinal, "phase": phase, **metadata[source_ordinal]})
        payload.append(canonical({"id": f"event-{ordinal}-{phase}-source-{source_ordinal}", "text": rows[source_ordinal]["record"]["model_input_text"]}))
    content = "\n".join(payload) + "\n"
    ensure(len(content.encode()) <= 5 * 1024**2, "traffic_upload_budget")
    return {"source_rows": metadata, "warmup_ordinals": warmup, "events": events, "payload_sha256": digest(content)}, content


def system_stop(samples):
    consecutive = 0
    for index, row in enumerate(samples):
        if row.get("status") != "observed":
            return "system_telemetry_unknown"
        if row["pressure_level"] == 4:
            return "critical_memory_pressure"
        if index:
            previous = samples[index - 1]
            dt = row["monotonic"] - previous["monotonic"]
            if not 0 < dt <= 3 or row["page_size"] != previous["page_size"]:
                return "system_interval_unknown"
            pages = row["swapins"] - previous["swapins"] + row["swapouts"] - previous["swapouts"]
            if row["swapins"] < previous["swapins"] or row["swapouts"] < previous["swapouts"]:
                return "swap_counter_reset"
            rate = pages * row["page_size"] / dt
            consecutive = consecutive + 1 if rate >= 100 * 1024**2 else 0
            if consecutive >= 3:
                return "swap_thrashing"
    return None


class Monitor:
    def __init__(self, path):
        self.path, self.samples, self.reason = path, [], None
        self.stopped = threading.Event()
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        try:
            with self.path.open("x") as stream:
                next_sample = time.monotonic()
                while not self.stopped.is_set():
                    self.stopped.wait(max(0, next_sample - time.monotonic()))
                    if self.stopped.is_set():
                        break
                    row = system_memory()
                    self.samples.append(row)
                    stream.write(canonical(row) + "\n")
                    stream.flush()
                    self.reason = self.reason or system_stop(self.samples)
                    self.ready.set()
                    next_sample = max(next_sample + 1, time.monotonic())
        except Exception:
            self.reason = self.reason or "system_monitor_failed"
            self.ready.set()

    def start(self):
        self.thread.start()
        ensure(self.ready.wait(timeout=6) and self.samples, "monitor_start_failed")

    def finish(self):
        self.stopped.set()
        self.thread.join(timeout=6)
        ensure(not self.thread.is_alive(), "monitor_shutdown_failed")


def job_summary(rows, events):
    ensure(len(rows) == len(events) == 420 and all(isinstance(row["result"], dict) for row in rows), "incomplete_event_coverage")
    summary = {"phases": {}, "schema_valid": 0, "peak_child_rss_bytes": 0, "peak_parent_rss_bytes": 0, "mlx_peak_bytes": 0}
    child_measured, parent_measured = [], []
    for phase in PHASES:
        selected = [row for row, event in zip(rows, events) if event["phase"] == phase]
        costs = {name: sum(row["result"]["counters"][name] for row in selected) for name in COSTS}
        child, parent, latency = [], [], []
        for row in selected:
            result = row["result"]
            ensure(result.get("fallback_reason") in (None, "m3_budget_exhausted"), "model_runtime_unstable")
            ensure(len(result.get("prediction", [])) == 6 and all(type(bit) is int and bit in (0, 1) for bit in result["prediction"]), "invalid_result_schema")
            sample = result["telemetry"]
            ensure(sample["status"] == "observed", "rss_observation_unknown")
            child.append(sample["child_current_rss_bytes"])
            parent.append(sample["parent_current_rss_bytes"])
            latency.append(result["latency_ms"])
            summary["schema_valid"] += 1
            summary["mlx_peak_bytes"] = max(summary["mlx_peak_bytes"], result["resources"]["mlx_peak_bytes"])
        summary["peak_child_rss_bytes"] = max(summary["peak_child_rss_bytes"], max(child))
        summary["peak_parent_rss_bytes"] = max(summary["peak_parent_rss_bytes"], max(parent))
        summary["phases"][phase] = {"events": len(selected), "cost": costs, "mean_item_ms": sum(latency)/len(latency),
                                     "median_item_ms": statistics.median(latency), "child_median_bytes": statistics.median(child),
                                     "parent_median_bytes": statistics.median(parent), "latency_ms": latency_distribution(latency)}
        if phase == "measured":
            child_measured, parent_measured = child, parent
    summary["child_plateau_ratio"] = statistics.median(child_measured[-85:]) / statistics.median(child_measured[:85])
    summary["parent_plateau_ratio"] = statistics.median(parent_measured[-85:]) / statistics.median(parent_measured[:85])
    ensure(summary["peak_child_rss_bytes"] <= 12 * 1024**3 and summary["peak_parent_rss_bytes"] <= 1024**3
           and summary["mlx_peak_bytes"] <= 10_000_000_000, "memory_budget_exceeded")
    ensure(summary["phases"]["measured"]["cost"]["m1_attempts"] > 0, "all_cache_measured_workload")
    return summary


def http(path, payload=None):
    token = (BENCH / "access-token").read_text().strip()
    request = Request("http://127.0.0.1:8788/api/" + path,
                      data=canonical(payload).encode() if payload is not None else None,
                      headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def run():
    os.umask(0o077)
    ensure(not any(path.is_symlink() for path in (RUN, *RUN.parents)), "run_path_symlink")
    RUN.mkdir(parents=True, exist_ok=True, mode=0o700)
    ensure(not (RUN / "run-claim.json").exists() and not (RUN / "run.json").exists(), "attempt_already_used")
    with sqlite3.connect((BENCH / "jobs.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
        ensure(db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0, "bench_not_empty")
    source, source_rows = read_job(ROOT / "private/jobs.sqlite3", SOURCE_JOB)
    ensure(source["state"] == "completed" and source["snapshot_hash"] == SOURCE_SNAPSHOT
           and digest(canonical([row["record"] for row in source_rows])) == SOURCE_SNAPSHOT, "source_snapshot_drift")
    verification_path = ROOT / "private/validation/exp-076/attempt-3/verification.json"
    inherited = json.loads(verification_path.read_text())
    ensure(inherited.get("status") == "Passed" and inherited.get("exp076_verified") is True
           and any(row["job_id"] == SOURCE_JOB and row["snapshot_hash"] == SOURCE_SNAPSHOT for row in inherited["jobs"]), "source_not_verified")
    plan, content = traffic_plan(source_rows)
    implementation = {str(path.relative_to(ROOT)): digest(path.read_bytes())
                      for folder in ("topicweb", "scripts", "tests", "static") for path in (ROOT / folder).rglob("*")
                      if path.is_file() and path.suffix in {".py", ".js", ".css", ".html"}
                      and str(path.relative_to(ROOT)) not in NONDEPENDENT_C3}
    implementation["requirements-lock.txt"] = digest((ROOT / "requirements-lock.txt").read_bytes())
    environment = environment_metadata()
    git_status = subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=ROOT, text=True)
    plan.update(experiment_id="EXP-077", source_job=SOURCE_JOB, source_snapshot_sha256=SOURCE_SNAPSHOT,
                source_logical_sha256=digest(canonical(source_rows)), source_verification_sha256=digest(verification_path.read_bytes()),
                rounds=12, modes=list(MODES), planned_jobs=36, planned_events=15120, protocol_sha256=digest(PROTOCOL.read_bytes()), sources=implementation)
    once(RUN / "plan.json", plan)
    started = time.monotonic()
    claim = {"experiment_id": "EXP-077", "tier": "Major", "started_at": now(), "started_monotonic": started, "maximum_seconds": MAX_SECONDS,
             "plan_sha256": digest((RUN / "plan.json").read_bytes()), "command": sys.argv, "cwd": str(ROOT),
             "python": sys.executable, "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
             "git_dirty": bool(git_status), "git_status_porcelain": git_status.splitlines(), "environment": environment,
             "training": False, "gold_accessed": False, "source_network_fetched": False}
    once(RUN / "run-claim.json", claim)
    stdout = (RUN / "stdout.log").open("x")
    def report(value):
        line = canonical(value)
        print(line, flush=True)
        stdout.write(line+"\n")
        stdout.flush()
    monitor = Monitor(RUN / "system-samples.jsonl")
    entries, current_job, failure, unhandled = [], None, None, 0
    cancellation_status = "not_needed"
    try:
        monitor.start()
        with (RUN / "jobs.jsonl").open("x") as log:
            for round_index in range(12):
                for mode in MODES:
                    ensure(time.monotonic() - started < MAX_SECONDS, "total_time_limit")
                    ensure(not monitor.reason, monitor.reason or "monitor_failure")
                    request = {"name": f"EXP-077 round {round_index+1} {mode}", "source": "upload", "mode": mode,
                               "max_qwen_calls": 20 if mode == "demo" else 500 if mode == "research" else 0, "audit_rate": 0,
                               "upload": {"format": "jsonl", "content": content, "filename": "exp077-traffic.jsonl", "text_column": "text"}}
                    began = time.monotonic()
                    current_job = http("jobs", request)["job"]["id"]
                    entry = {"id": current_job, "round": round_index + 1, "mode": mode, "status": "submitted", "submitted_at": now(), "started_monotonic": began}
                    entries.append(entry)
                    log.write(canonical(entry) + "\n"); log.flush()
                    report({"round": round_index+1, "mode": mode, "status": "submitted"})
                    while True:
                        ensure(time.monotonic() - started < MAX_SECONDS, "total_time_limit")
                        ensure(not monitor.reason, monitor.reason or "monitor_failure")
                        job = http("jobs/" + current_job)["job"]
                        if job["state"] in {"completed", "completed_with_fallback", "failed", "cancelled"}:
                            break
                        time.sleep(.25)
                    finished = time.monotonic()
                    entry.update(status=job["state"], error_code=job["error_code"], elapsed_seconds=finished-began, ended_monotonic=finished,
                                 total_items=job["total_items"], completed_items=job["completed_items"], snapshot_hash=job["snapshot_hash"])
                    ensure(job["state"] in {"completed", "completed_with_fallback"}, "runtime_job_failed")
                    _, rows = read_job(BENCH / "jobs.sqlite3", current_job)
                    entry["summary"] = job_summary(rows, plan["events"])
                    log.write(canonical(entry) + "\n"); log.flush()
                    report({"round": round_index+1, "mode": mode, "status": job["state"],
                            "child_plateau_ratio": entry["summary"]["child_plateau_ratio"]})
                    current_job = None
                    ensure(all(digest((ROOT / path).read_bytes()) == value for path, value in implementation.items())
                           and digest(PROTOCOL.read_bytes()) == plan["protocol_sha256"], "implementation_drift")
    except Exception as error:
        failure = str(error) if isinstance(error, RuntimeError) else type(error).__name__
        unhandled = int(not isinstance(error, RuntimeError))
        if current_job:
            try:
                http(f"jobs/{current_job}/cancel", {})
                cancellation_status = "requested"
                cleanup_deadline = time.monotonic()+15
                while time.monotonic() < cleanup_deadline:
                    final_job = http("jobs/"+current_job)["job"]
                    if final_job["state"] in {"completed", "completed_with_fallback", "failed", "cancelled"}:
                        cancellation_status = "terminal_confirmed"
                        entries[-1].update(status=final_job["state"], error_code=final_job["error_code"],
                                           total_items=final_job["total_items"], completed_items=final_job["completed_items"],
                                           snapshot_hash=final_job["snapshot_hash"])
                        break
                    time.sleep(.25)
            except Exception:
                cancellation_status = "unconfirmed"
    finally:
        monitor.finish()
        failure = failure or monitor.reason
        ended = time.monotonic()
        record = {**claim, "status": "Stopped" if failure else "Completed", "ended_at": now(), "ended_monotonic": ended,
                  "elapsed_seconds": ended-started, "failure_code": failure, "jobs": entries,
                  "unhandled_errors": unhandled + sum(entry.get("error_code") == "worker_failed" for entry in entries),
                  "cancellation_status": cancellation_status,
                  "completed_jobs": sum(entry.get("status") in {"completed", "completed_with_fallback"} for entry in entries),
                  "system_samples_sha256": digest((RUN / "system-samples.jsonl").read_bytes()),
                  "timing_scope": {"job_elapsed": "HTTP submit through terminal response; includes queue, model initialization and polling",
                                   "per_item_latency": "Frozen bridge predict only; excludes HTTP, M1 engine startup, and parent RSS sampling; may include first M3 initialization",
                                   "phase_quantiles": "linear interpolation at (n-1)*p"},
                  "claim_boundary": "Finite local reused-snapshot runtime study; no SLA, accuracy, external-gold or population emotion claim."}
        report({"status": record["status"], "failure_code": failure, "completed_jobs": record["completed_jobs"]})
        stdout.flush()
        os.fsync(stdout.fileno())
        stdout.close()
        record["stdout_sha256"] = digest((RUN / "stdout.log").read_bytes())
        once(RUN / "run.json", record)
    return 0 if not failure else 1


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("serve", "run"))
    command = parser.parse_args(argv).command
    if command == "serve":
        os.environ["TOPICWEB_TELEMETRY"] = "1"
        os.umask(0o077)
        from topicweb.app import create_app
        import uvicorn
        uvicorn.run(create_app(private_dir=BENCH), host="127.0.0.1", port=8788, access_log=False)
        return 0
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
