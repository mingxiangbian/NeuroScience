"""EXP-080 independent source/accounting audit; never impersonates an EXP-078 run."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "private/validation/exp-080/attempt-1"
BENCH = RUN / "bench"
PRIOR = ROOT / "private/validation/exp-079/attempt-3"
PROTOCOL = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-080-discourse-formal-topic-run.md"
DECISION = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/dec-phase-c1-bounded-operational-validation-v1.md"
OBSERVER_CORRECTION = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-079-observer-correction-attempt-2.md"
BACKGROUND_REDUCTION = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-079-reduced-background-attempt-3.md"
REVIEW = ROOT / "docs/discourse-source-review.md"
QUERY = {"site": "discuss.python.org", "category_id": 7, "max_topics": 100, "max_items": 400}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SOURCE = load_module("exp080_source_accounting_helpers", ROOT / "scripts/verify_discourse_validation.py")
SAFETY = load_module("exp080_independent_runtime_safety", ROOT / "scripts/verify_bounded_runtime.py")
LOCAL = SOURCE.LOCAL
require, close, sha, canonical = LOCAL.require, LOCAL.close, LOCAL.sha, LOCAL.canonical
ADDITIONAL_SOURCES = {"scripts/run_discourse_formal.py", "scripts/verify_discourse_formal.py", "tests/test_discourse_formal.py",
                      "scripts/verify_discourse_validation.py", "scripts/verify_local.py"}


def check_prior(run, verification, *, run_hash, plan_hash):
    prefix = "private/validation/exp-079/attempt-3/"
    require(run.get("experiment_id") == "EXP-079" and run.get("status") == "Completed"
            and run.get("failure_code") is None and run.get("plan_sha256") == plan_hash, "exp079_run_not_safe")
    require(verification.get("experiment_id") == "EXP-079" and verification.get("status") == "Passed"
            and verification.get("exp079_complete") is True
            and verification.get("operational_state") == "safe-to-continue", "exp079_verification_not_safe")
    bindings = verification.get("source_hashes", {})
    require(bindings.get(prefix + "run.json") == run_hash and bindings.get(prefix + "plan.json") == plan_hash,
            "exp079_hash_binding")


def check_prior_scope(prior_sources, current_sources, additional):
    require(isinstance(prior_sources, dict) and prior_sources and isinstance(current_sources, dict)
            and set(prior_sources) <= set(current_sources)
            and set(current_sources) - set(prior_sources) <= set(additional)
            and all(current_sources[name] == digest for name, digest in prior_sources.items()), "exp079_dependency_drift")


def check_job(entry, job, *, complete):
    """Uses source/record/statistics helpers only, with EXP-080's own lifecycle."""
    require(isinstance(entry, dict) and entry.get("id") == job.get("id"), "job_binding")
    require(job.get("source") == "discourse" and job.get("mode") == "research"
            and not job.get("raw_expired") and not job.get("items_expired"), "job_source_or_retention")
    close(job.get("request"), {"source": "discourse", "mode": "research", "max_qwen_calls": 500,
                               "audit_rate": 0, "seed": 42, "query": QUERY}, "job_request")
    require(job.get("state") == entry.get("state") and job.get("state") in {"completed", "failed", "cancelled"}, "job_terminal")
    rows = job.get("items")
    require(isinstance(rows, list) and len(rows) <= 400
            and [row.get("ordinal") for row in rows] == list(range(len(rows))), "row_ordinals")
    records, results = [row["record"] for row in rows], [row["result"] for row in rows]
    acknowledged = sum(result is not None for result in results)
    require(len(records) == job.get("total_items") == entry.get("total_items")
            and acknowledged == job.get("completed_items") == entry.get("completed_items"), "job_counts")
    require(type(entry.get("elapsed_seconds")) in (int, float) and math.isfinite(entry["elapsed_seconds"])
            and 0 <= entry["elapsed_seconds"] <= 3615, "job_elapsed")
    if complete:
        require(job["state"] == "completed" and job.get("error_code") is None
                and 300 <= len(records) <= 400 and acknowledged == len(records)
                and entry["elapsed_seconds"] <= 3600, "complete_job_contract")
    if not records:
        require(not complete and job.get("snapshot_hash") is None, "missing_snapshot")
        return {"job_id": job["id"], "records": 0, "acknowledged_rows": 0,
                "source_complete": False, "unacknowledged_model_attempts": "unknown", "model_peak_observations": None}
    snapshot = LOCAL.check_records(records)
    require(snapshot == job.get("snapshot_hash") == entry.get("snapshot_hash"), "snapshot_hash")
    close(entry.get("private_snapshot"), {"database": "private/validation/exp-080/attempt-1/bench/jobs.sqlite3",
                                          "job_id": job["id"], "snapshot_sha256": snapshot}, "isolated_snapshot_reference")
    require(canonical(entry.get("manifest")) == canonical(job.get("manifest"))
            and entry.get("manifest_sha256") == sha(canonical(job["manifest"])), "manifest_binding")
    source_check = SOURCE.check_source(records, job["manifest"]) if len(records) >= 300 else {"records": len(records), "registered_count_met": False}
    computed = LOCAL.recalculate(records, results, "research")
    reported = entry.get("dashboard")
    require(isinstance(reported, dict), "dashboard_missing")
    # A stopped task can expose complete-counter lower bounds/unknowns in the API;
    # the independent count below remains acknowledged-result accounting only.
    for key in ("summary", "emotions", "daily", "object_types", "uncertainty", "timing"):
        close(reported.get(key), computed[key], "dashboard_" + key)
    if complete:
        close(job.get("dashboard"), computed, "stored_complete_dashboard")
        close(reported, computed, "reported_complete_dashboard")
    derived = SOURCE.check_derived(records, results, reported.get("derived"))
    fingerprints = set()
    m1_tokens, m3_tokens = [], []
    truncated = {"m1": 0, "m3": 0}
    peak_rss = peak_mlx = None
    for result in (value for value in results if value is not None):
        fingerprint = result.get("fingerprint")
        require(isinstance(fingerprint, str) and re.fullmatch(r"[0-9a-f]{64}", fingerprint), "pipeline_fingerprint")
        fingerprints.add(fingerprint)
        for model, cap, values in (("m1", 256, m1_tokens), ("m3", 384, m3_tokens)):
            meta = result.get("tokenlengths", {}).get(model)
            if model == "m3" and not result["route_requested"]:
                require(meta is None and result.get("truncflags", {}).get(model) is None, "unobserved_m3_tokens")
                continue
            require(isinstance(meta, dict) and type(meta.get("input_tokens")) is int
                    and type(meta.get("used_tokens")) is int and 1 <= meta["used_tokens"] <= cap
                    and meta["input_tokens"] >= meta["used_tokens"], "token_length")
            flag = meta["input_tokens"] > meta["used_tokens"]
            require(meta.get("truncated") is flag and result.get("truncflags", {}).get(model) is flag, "truncation_flag")
            values.append(meta["input_tokens"])
            truncated[model] += flag
        resources = result.get("resources")
        require(isinstance(resources, dict) and type(resources.get("peak_rss_bytes")) is int
                and 0 <= resources["peak_rss_bytes"] <= 12 * 1024**3
                and type(resources.get("mlx_peak_bytes")) is int and 0 <= resources["mlx_peak_bytes"] <= 10_000_000_000,
                "acknowledged_resource_budget")
        peak_rss = max(peak_rss or 0, resources["peak_rss_bytes"])
        peak_mlx = max(peak_mlx or 0, resources["mlx_peak_bytes"])
    require(len(fingerprints) <= 1 and (not complete or len(fingerprints) == 1), "mixed_pipeline")
    return {"job_id": job["id"], "snapshot_sha256": snapshot, "source": source_check,
            "acknowledged_rows": acknowledged, "acknowledged_derived": computed, "derived_check": derived,
            "route_requested_rate_on_acknowledged": computed["routing"]["route_requested"] / acknowledged if acknowledged else None,
            "pipeline_fingerprint": next(iter(fingerprints)) if fingerprints else None,
            "lengths": {"m1_observed": len(m1_tokens), "m3_observed": len(m3_tokens), "truncated_count": truncated},
            "model_peak_observations": {"rss_bytes": peak_rss, "mlx_bytes": peak_mlx} if acknowledged else None,
            "unacknowledged_model_attempts": "not_applicable_completed_job" if complete else "unknown"}


def verify_run(plan, run, service, samples, events, jobs):
    require(plan.get("experiment_id") == run.get("experiment_id") == "EXP-080"
            and run.get("stage") == "discourse_formal" and run.get("attempt") == 1
            and run.get("status") in {"Completed", "Stopped"}, "exp080_identity")
    require(all(run.get(name) is False for name in ("training", "gold_accessed", "validation_accessed", "test_accessed", "raw_read_by_driver")), "access_boundary")
    close(plan, {"query": QUERY, "mode": "research", "max_qwen_calls": 500, "audit_rate": 0, "seed": 42,
                 "maximum_seconds": 3600, "planned_jobs": 1, "planned_records_min": 300, "planned_records_max": 400}, "formal_plan")
    require(service.get("experiment_id") == "EXP-080" and service.get("root") == str(ROOT)
            and service.get("bench_root") == str(BENCH) and service.get("port") == 8790, "isolated_service_identity")
    require(plan.get("service") == service, "service_plan_binding")
    start, end = run.get("started_monotonic"), run.get("ended_monotonic")
    require(type(start) in (int, float) and type(end) in (int, float) and math.isfinite(start) and math.isfinite(end)
            and 0 <= start <= end, "run_clock")
    close(run.get("elapsed_seconds"), float(end-start), "run_elapsed")
    entries = run.get("jobs")
    require(isinstance(entries, list) and len(entries) <= 1 and isinstance(jobs, dict) and len(jobs) <= 1, "single_job_scope")
    complete = run["status"] == "Completed"
    require(all(entry.get("status", entry.get("state")) == entry.get("state") for entry in entries
                if entry.get("state") is not None), "entry_terminal_alias")
    if complete:
        require(run.get("failure_code") is None and len(entries) == 1, "completed_run_contract")
    else:
        require(isinstance(run.get("failure_code"), str) and bool(run["failure_code"])
                and run.get("unacknowledged_model_attempts") == "unknown", "stopped_run_contract")
    identifiers = {entry["id"] for entry in entries if isinstance(entry.get("id"), str)}
    bound = identifiers == set(jobs) and len(identifiers) == len(entries)
    if not bound:
        require(not complete and any(entry.get("submission_outcome") == "unknown" for entry in entries), "unbound_job")
    if samples is None or events is None or not bound:
        require(not complete, "complete_without_monitor")
        safety = {"gate_passed": False, "observation_state": "unknown"}
    else:
        require(all(start <= row.get("started_monotonic", -1) <= row.get("monotonic", -1) <= end for row in samples), "sample_run_clock")
        attempts = run.get("readiness")
        require(isinstance(attempts, list) and len(entries) <= len(attempts) <= 1, "readiness_attempt_count")
        for attempt in attempts:
            require(attempt.get("status") in {"Ready", "NotReady"}
                    and type(attempt.get("started_monotonic")) in (int, float)
                    and type(attempt.get("ended_monotonic")) in (int, float)
                    and start <= attempt["started_monotonic"] <= attempt["ended_monotonic"] <= end, "readiness_attempt_clock")
            observed = attempt.get("observed_sample_indices")
            require(isinstance(observed, list) and all(type(index) is int and 0 <= index < len(samples) for index in observed)
                    and observed == sorted(set(observed)), "readiness_observed_indices")
            require(all(samples[index]["monotonic"] >= attempt["started_monotonic"]
                        and samples[index]["started_monotonic"] <= attempt["ended_monotonic"] for index in observed), "readiness_observed_window")
        if entries:
            attempt, entry = attempts[0], entries[0]
            require(attempt["status"] == "Ready" and attempt.get("readiness_indices") == entry.get("readiness_indices")
                    and attempt["started_monotonic"] == entry.get("readiness_started_monotonic")
                    and attempt["ended_monotonic"] == entry.get("readiness_ended_monotonic"), "job_readiness_binding")
        safety = SAFETY.verify_safety(samples, events, service, entries, elapsed_seconds=run.get("elapsed_seconds"), limit_seconds=3600)
    checks = []
    for entry in entries:
        if entry.get("id") not in jobs:
            continue
        if not complete and (entry.get("final_job_observation") == "unknown" or entry.get("state") not in {"completed", "failed", "cancelled"}):
            checks.append({"job_id": entry["id"], "final_observation": "unknown", "unacknowledged_model_attempts": "unknown"})
            continue
        checks.append(check_job(entry, jobs[entry["id"]], complete=complete))
    passed = complete and bound and bool(safety["gate_passed"]) and len(checks) == 1
    return {"status": "Passed", "exp080_complete": passed,
            "operational_state": "safe-to-continue" if passed else "stop-required", "safety": safety, "jobs": checks,
            "claim_boundary": SOURCE.BOUNDARY + " EXP-080 has its own EXP-079 dependency and isolated benchmark; EXP-078 is not relabelled or rerun."}


def service_is_stopped(service):
    require(type(service.get("pid")) is int and service["pid"] > 0 and isinstance(service.get("start_time"), str), "service_exit_identity")
    result = subprocess.run(["/bin/ps", "-p", str(service["pid"]), "-o", "lstart="], capture_output=True, text=True,
                            timeout=3, env={**os.environ, "LC_ALL": "C"})
    require(result.returncode in (0, 1), "service_exit_observation_unknown")
    if result.returncode == 0:
        current = " ".join(result.stdout.split())
        require(bool(current), "service_exit_observation_unknown")
        require(current != " ".join(service["start_time"].split()), "service_must_stop_before_verification")


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    target = RUN / "verification.json"
    require(not target.exists() and not any(path.is_symlink() for path in (target, *target.parents)), "verification_exists_or_symlink")
    result = {"experiment_id": "EXP-080", "status": "Failed", "exp080_complete": False, "operational_state": "stop-required",
              "verified_at": datetime.now(timezone.utc).isoformat(), "models_loaded": False, "gold_accessed": False,
              "producer_statistical_helpers_imported": False, "old_exp078_relabelled": False}
    paths = {"plan": RUN / "plan.json", "run": RUN / "run.json", "service": RUN / "service.json", "claim": RUN / "run-claim.json"}
    try:
        hashes = {key: SOURCE.file_hash(path) for key, path in paths.items()}
        plan, run, service = [LOCAL.strict_json(paths[key].read_text()) for key in ("plan", "run", "service")]
        claim = LOCAL.strict_json(paths["claim"].read_text())
        require(run.get("plan_sha256") == hashes["plan"] and plan.get("service_sha256") == hashes["service"], "plan_or_service_hash")
        require(run.get("run_claim_sha256") == hashes["claim"] and claim.get("experiment_id") == "EXP-080"
                and claim.get("plan_sha256") == hashes["plan"] and claim.get("started_at") == run.get("started_at")
                and claim.get("started_monotonic") == run.get("started_monotonic"), "run_claim_binding")
        service_is_stopped(service)
        require(plan.get("protocol_sha256") == SOURCE.file_hash(PROTOCOL)
                and plan.get("decision_sha256") == SOURCE.file_hash(DECISION)
                and plan.get("source_review_sha256") == SOURCE.file_hash(REVIEW)
                and plan.get("source_protocol_sha256") == SOURCE.file_hash(SOURCE.PROTOCOL), "protocol_or_review_hash")
        require(plan.get("observer_correction_path") == str(OBSERVER_CORRECTION.relative_to(ROOT.parent))
                and plan.get("observer_correction_sha256") == SOURCE.file_hash(OBSERVER_CORRECTION), "observer_correction_binding")
        require(plan.get("background_reduction_path") == str(BACKGROUND_REDUCTION.relative_to(ROOT.parent))
                and plan.get("background_reduction_sha256") == SOURCE.file_hash(BACKGROUND_REDUCTION), "background_reduction_binding")
        sources = plan.get("sources")
        require(isinstance(sources, dict) and sources, "source_bindings_missing")
        for name, digest in sources.items():
            relative = Path(name)
            require(not relative.is_absolute() and ".." not in relative.parts
                    and (relative.parts[0] in {"topicweb", "scripts", "tests", "static"}
                         or name in {"requirements.txt", "requirements-lock.txt", "start.py"}), "source_path")
            require(SOURCE.file_hash(ROOT / relative) == digest, "source_drift")
        previous = {}
        bindings = plan.get("prior_exp079")
        require(isinstance(bindings, dict) and set(bindings) == {"run", "verification", "plan"}, "exp079_bindings")
        for key, binding in bindings.items():
            expected = "private/validation/exp-079/attempt-3/" + key + ".json"
            require(binding.get("path") == expected and SOURCE.file_hash(ROOT / expected) == binding.get("sha256"), "exp079_artifact_hash")
            previous[key] = LOCAL.strict_json((ROOT / expected).read_text())
        check_prior(previous["run"], previous["verification"], run_hash=bindings["run"]["sha256"], plan_hash=bindings["plan"]["sha256"])
        require(previous["plan"].get("reduced_background_sha256") == plan.get("background_reduction_sha256"), "exp079_background_note_binding")
        check_prior_scope(previous["plan"].get("sources"), sources, ADDITIONAL_SOURCES)
        require(plan.get("environment") == previous["run"].get("environment") and isinstance(plan.get("environment"), dict), "environment_binding")
        monitor_data = {}
        for key, name, digest_key in (("samples", "system-process-samples.jsonl", "samples_sha256"),
                                       ("events", "process-events.jsonl", "process_events_sha256")):
            path = RUN / name
            expected = run.get(digest_key)
            if expected is None:
                require(run["status"] == "Stopped", "monitor_hash_missing")
                monitor_data[key] = None
                continue
            require(SOURCE.file_hash(path) == expected, "monitor_artifact_hash")
            monitor_data[key] = [LOCAL.strict_json(line) for line in path.read_text().splitlines() if line]
            hashes[key] = expected
        database = BENCH / "jobs.sqlite3"
        SOURCE.regular(database)
        wal = BENCH / "jobs.sqlite3-wal"
        require(not wal.exists() or wal.stat().st_size == 0, "bench_wal_not_sealed")
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
            identifiers = [row[0] for row in db.execute("SELECT id FROM jobs")]
        require(len(identifiers) <= 1, "bench_job_scope")
        jobs = {identifier: SOURCE.read_selected_job(database, identifier) for identifier in identifiers}
        logical = sha(canonical(jobs))
        result.update(verify_run(plan, run, service, monitor_data["samples"], monitor_data["events"], jobs))
        require(all(SOURCE.file_hash(paths[key]) == value for key, value in hashes.items() if key in paths), "terminal_changed")
        require(sha(canonical({identifier: SOURCE.read_selected_job(database, identifier) for identifier in identifiers})) == logical, "database_changed")
        result.update(source_hashes={str(paths[key].relative_to(ROOT)): value for key, value in hashes.items() if key in paths},
                      selected_database_logical_sha256=logical, verifier_sha256=SOURCE.file_hash(Path(__file__)), service_stopped=True)
    except Exception as error:
        result.update(status="Failed", exp080_complete=False, operational_state="stop-required",
                      error_code=str(error) if isinstance(error, (LOCAL.VerificationError, SAFETY.VerificationError)) else "formal_verification_input_error")
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")
        output.flush()
        os.fsync(output.fileno())
    print(json.dumps({key: result.get(key) for key in ("status", "exp080_complete", "operational_state", "error_code")}))
    return 0 if result["status"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
