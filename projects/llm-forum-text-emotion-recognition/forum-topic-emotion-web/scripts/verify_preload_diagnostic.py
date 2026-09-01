"""EXP-083 independent two-process replay and Research-stage audit, without models."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "private/validation/exp-083/attempt-1"
SPEC = importlib.util.spec_from_file_location("exp083_prior_stage_audit", ROOT/"scripts/verify_m3_diagnostic.py")
M3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M3)
B, LOCAL = M3.BOUNDED, M3.LOCAL
require, close, sha, finite = B.require, B.close, B.sha, B.finite
regular_file, read_lines = B.regular_file, M3.read_lines
SOURCE_JOB = "5ab3326150ee448ba326233264967d34"
SOURCE_SNAPSHOT = "cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16"
SOURCE_LOGICAL = "8c0cc285ff71fd041eb832d5a8422d68dcaad84228a9c3b00d14f213dacd17a4"
SOURCE_PLAN_HASH = "6635d7022959642ae0adff5c42b483ca30a0cc598924ee814c25667c1e5d236c"
PARENT_HASHES = {
    "plan": "896067922d9029e35ccdf1eeb44976bb22fc96a71ce0791424861d16547a5298",
    "run": "10125ffc1c22bd020dc75f2c05647464be22ea90f8d509b7e3f7e78eb9d4e952",
    "verification": "0d98fef8a5662bace2299bd7f11f9d17c99f13b14dca4a7c3765f4fe2ea3deb6",
}
PHASES = (
    {"phase": "m1_prelude", "job_id": "exp083-m1-prelude", "mode": "m1_only", "planned_events": 340, "max_qwen_calls": 0},
    {"phase": "research_prefix", "job_id": "exp083-research-prefix", "mode": "research", "planned_events": 7, "max_qwen_calls": 1},
)
ADDITIONAL_SOURCES = {
    "scripts/run_preload_diagnostic.py", "scripts/preload_diagnostic_child.py", "scripts/verify_preload_diagnostic.py",
    "tests/test_preload_diagnostic.py", "tests/test_verify_preload_diagnostic.py",
}
PROTOCOL = "experiments/stack-overflow-emotion-gold/protocols/exp-083-m1-prelude-memory-diagnostic.md"
ARTIFACTS = ("service.json", "plan.json", "run-claim.json", "results.jsonl", "samples.jsonl",
             "process-events.jsonl", "stages.jsonl", "stdout.log", "run.json")


def path_for(name, root=None):
    return B.source_path(name, ROOT if root is None else root)


def read_source(database):
    require(database.is_file() and not any(p.is_symlink() for p in (database, *database.parents)), "source_database_identity")
    with sqlite3.connect(database.as_uri()+"?mode=ro", uri=True, timeout=1) as db:
        metadata = db.execute("SELECT state,snapshot_hash,total_items FROM jobs WHERE id=?", (SOURCE_JOB,)).fetchone()
        rows = db.execute("SELECT ordinal,record,result FROM items WHERE job_id=? ORDER BY ordinal", (SOURCE_JOB,)).fetchall()
    require(metadata == ("completed", SOURCE_SNAPSHOT, 340), "source_job_identity")
    return [{"ordinal": ordinal, "record": LOCAL.strict_json(record), "result": LOCAL.strict_json(result)} for ordinal, record, result in rows]


def validate_plan(plan, source):
    close(plan, {"experiment_id": "EXP-083", "attempt": 1, "tier": "Minor", "rq": "RQ-S3",
                 "planned_jobs": 2, "planned_events": 347, "phase_order": [phase["phase"] for phase in PHASES],
                 "phases": list(PHASES), "max_seconds": 180, "work_seconds": 150,
                 "cleanup_seconds": 15, "max_readiness_seconds": 60, "audit_rate": 0, "seed": 42,
                 "source_job": SOURCE_JOB, "source_snapshot_sha256": SOURCE_SNAPSHOT,
                 "source_database": "private/jobs.sqlite3", "source_logical_sha256": SOURCE_LOGICAL}, "plan_contract")
    rows = B.validate_source_rows(source)
    require(plan.get("source_rows") == rows and plan.get("prefix_rows") == rows[:7], "source_mapping")
    require([row["route_eligible"] for row in rows[:7]] == [False]*6+[True], "prefix_route_contract")
    require(sha(LOCAL.canonical(source)) == plan["source_logical_sha256"], "source_logical_identity")


def phase_receipts(phase, rows, source, reference, events, service, run):
    count = phase["planned_events"]
    require(len(rows) <= count and [row.get("ordinal") for row in rows] == list(range(len(rows))), "phase_result_prefix")
    costs = {name: 0 for name in B.COSTS}
    seen, violations = set(), 0
    source_difference = reference_difference = None
    ready = [event for event in events if event["type"] == "ready"]
    exits = [event for event in events if event["type"] == "process_exit"]
    for row in rows:
        ordinal, result = row["ordinal"], row["result"]
        old = source[ordinal]
        hashed = old["record"]["model_input_hash"]
        require(row.get("input_sha256") == hashed, "receipt_input_identity")
        p1, d1 = LOCAL.probabilities(result.get("m1_probabilities")), LOCAL.decisions(result.get("m1_prediction"))
        delta = max(abs(a-b) for a,b in zip(p1, LOCAL.probabilities(old["result"].get("m1_probabilities"))))
        require(delta <= 1e-6 and d1 == old["result"]["m1_prediction"] == [int(value >= .31) for value in p1], "source_m1_parity")
        source_difference = delta if source_difference is None else max(source_difference, delta)
        eligible = old["result"]["hypothetical_route"]
        routed = eligible and phase["mode"] == "research"
        require(result.get("hypothetical_route") is eligible and result.get("route_requested") is routed
                and result.get("used_path") == ("m3" if routed else "m1")
                and result.get("fallback") is False and result.get("fallback_reason") is None, "receipt_route_identity")
        if routed:
            p3 = LOCAL.probabilities(result.get("m3_probabilities"))
            selected = LOCAL.decisions(result.get("m3_prediction"))
            require(selected == [int(value >= .31) for value in p3], "m3_threshold_identity")
        else:
            require(result.get("m3_probabilities") is None and result.get("m3_prediction") is None, "unexpected_m3_output")
            selected = d1
        require(LOCAL.decisions(result.get("prediction")) == selected, "selected_prediction_identity")
        if phase["mode"] == "research":
            previous = reference[ordinal]
            require(previous.get("ordinal") == ordinal and previous.get("input_sha256") == hashed, "exp082_reference_identity")
            for name in ("m1_probabilities", "m3_probabilities"):
                left, right = result.get(name), previous["result"].get(name)
                if left is None or right is None:
                    require(left is right, "exp082_probability_availability")
                    continue
                difference = max(abs(a-b) for a,b in zip(LOCAL.probabilities(left), LOCAL.probabilities(right)))
                require(difference <= 1e-6, "exp082_probability_parity")
                reference_difference = difference if reference_difference is None else max(reference_difference, difference)
            require(result["prediction"] == previous["result"]["prediction"], "exp082_prediction_parity")
        expected = {name: 0 for name in costs}
        expected.update(m1_attempts=int(hashed not in seen), m1_cache_hit=int(hashed in seen),
                        m3_attempts=int(routed), m3_succeeded=int(routed))
        seen.add(hashed)
        close(result.get("counters"), expected, "receipt_cost_identity")
        costs = {name: costs[name]+expected[name] for name in costs}
        close(result.get("cumulative_counters"), costs, "receipt_cumulative_cost")
        require(all(type(result[field].get(name)) is int for field in ("counters", "cumulative_counters") for name in costs), "receipt_cost_types")
        child_rss, parent_rss = B.result_rss(result.get("telemetry"))
        telemetry = result["telemetry"]
        require(len(ready) == 1 and telemetry["child_pid"] == ready[0].get("pid")
                and telemetry["parent_pid"] == service["pid"] and finite(telemetry.get("monotonic"))
                and ready[0]["monotonic"] <= telemetry["monotonic"] <= (exits[-1]["monotonic"] if exits else run["ended_monotonic"]), "receipt_process_time")
        resources = result.get("resources")
        require(isinstance(resources, dict) and all(type(resources.get(key)) is int and resources[key] >= 0 for key in ("peak_rss_bytes", "mlx_peak_bytes")), "receipt_resource_schema")
        if phase["mode"] == "m1_only":
            require(resources["mlx_peak_bytes"] == 0, "m1_reported_mlx_activity")
        violations += (child_rss > 12*1024**3 or parent_rss > 1024**3
                       or resources["peak_rss_bytes"] > 12*1024**3 or resources["mlx_peak_bytes"] > 10_000_000_000)
    return {"phase": phase["phase"], "planned_events": count, "verified_acknowledged_events": len(rows),
            "missing_acknowledged_events": count-len(rows), "acknowledged_cost_lower_bound": costs,
            "source_m1_max_abs_difference": source_difference,
            "exp082_probability_max_abs_difference": reference_difference,
            "receipt_resource_violations": violations}


def analyze(plan, run, source, reference, results, samples, events, service, stage_bytes):
    validate_plan(plan, source)
    close(run, {"experiment_id": "EXP-083", "attempt": 1, "tier": "Minor", "rq": "RQ-S3",
                "planned_jobs": 2, "planned_events": 347, "training": False, "gold_accessed": False,
                "source_network_fetched": False, "operational_followup_authorized": False}, "run_contract")
    require(run.get("status") in {"Completed", "Stopped", "Failed"} and finite(run.get("started_monotonic"))
            and finite(run.get("ended_monotonic")) and run["started_monotonic"] <= run["ended_monotonic"], "run_clock_status")
    close(run.get("elapsed_seconds"), run["ended_monotonic"]-run["started_monotonic"], "run_elapsed")
    require(run.get("total_budget_exceeded") is (run["elapsed_seconds"] > 180), "total_budget_flag")
    require(len(reference) == 7 and [row.get("ordinal") for row in reference] == list(range(7)), "exp082_reference_count")
    require(all(run["started_monotonic"] <= sample["started_monotonic"] <= sample["monotonic"] <= run["ended_monotonic"] for sample in samples)
            and all(run["started_monotonic"] <= event["monotonic"] <= run["ended_monotonic"] for event in events), "run_observation_window")
    jobs, attempts = run.get("jobs"), run.get("readiness_attempts")
    require(isinstance(jobs, list) and len(jobs) <= 2 and isinstance(attempts, list)
            and len(jobs) <= len(attempts) <= min(2, len(jobs)+1), "phase_attempt_count")
    mapping = {phase["phase"]: [] for phase in PHASES}
    previous_phase = 0
    for row in results:
        require(isinstance(row, dict) and row.get("phase") in mapping, "result_phase_identity")
        index = [phase["phase"] for phase in PHASES].index(row["phase"])
        require(previous_phase <= index and index < len(jobs), "result_phase_order")
        previous_phase = index
        mapping[row["phase"]].append(row)
    for index, attempt in enumerate(attempts):
        require(attempt.get("phase") == PHASES[index]["phase"] and attempt.get("status") in {"Ready", "NotReady"}
                and finite(attempt.get("started_monotonic")) and finite(attempt.get("ended_monotonic"))
                and run["started_monotonic"] <= attempt["started_monotonic"] <= attempt["ended_monotonic"] <= run["ended_monotonic"], "readiness_attempt_contract")
        indices = attempt.get("indices")
        require(isinstance(indices, list) and all(type(value) is int and 0 <= value < len(samples) for value in indices), "readiness_indices")
        if index < len(jobs):
            job, phase = jobs[index], PHASES[index]
            require(job.get("id") == phase["job_id"] and job.get("phase") == phase["phase"] and job.get("mode") == phase["mode"]
                    and job.get("status") in {"completed", "cancelled", "failed"} and job.get("total_items") == phase["planned_events"]
                    and job.get("completed_items") == len(mapping[phase["phase"]]), "phase_job_contract")
            require(attempt["status"] == "Ready" and indices == job.get("readiness_indices")
                    and attempt["started_monotonic"] == job.get("readiness_started_monotonic")
                    and attempt["ended_monotonic"] == job.get("readiness_ended_monotonic"), "readiness_job_binding")
            require(finite(job.get("started_monotonic")) and finite(job.get("ended_monotonic"))
                    and attempt["ended_monotonic"] <= job["started_monotonic"] <= job["ended_monotonic"] <= run["ended_monotonic"], "job_clock")
            if job["status"] == "completed":
                require(job["completed_items"] == phase["planned_events"] and job.get("normal_exit") is True, "partial_job_called_complete")
        if index:
            require(jobs and jobs[0]["status"] == "completed" and jobs[0]["ended_monotonic"] <= attempt["started_monotonic"], "research_after_failed_prelude")
    safety = B.verify_safety(samples, events, service, jobs, elapsed_seconds=run["elapsed_seconds"], limit_seconds=180)
    if len(jobs) == 2:
        cutoff = attempts[1]["started_monotonic"]
        prefix_samples = [sample for sample in samples if sample["monotonic"] <= cutoff]
        prefix_events = [event for event in events if event["job_id"] == PHASES[0]["job_id"]]
        prior_safety = B.verify_safety(prefix_samples, prefix_events, service, jobs[:1], elapsed_seconds=cutoff-run["started_monotonic"], limit_seconds=180)
        require(prior_safety["gate_passed"], "research_attempt_after_unsafe_prelude")
    cleanups = [job["cleanup"] for job in jobs if job.get("cleanup") is not None]
    require(run.get("cleanups") == cleanups, "cleanup_binding")
    for job in jobs:
        cleanup = job.get("cleanup")
        if cleanup:
            require(cleanup.get("job_id") == job["id"] and cleanup.get("phase") == job["phase"]
                    and cleanup["started_monotonic"] <= cleanup["ended_monotonic"] <= job["ended_monotonic"], "cleanup_phase_clock")
    exit_summary = []
    summaries = []
    for index, phase in enumerate(PHASES):
        phase_events = [event for event in events if event.get("job_id") == phase["job_id"]]
        actual_exits = [event for event in phase_events if event["type"] == "process_exit"]
        require(all(type(event.get("returncode")) is int for event in actual_exits), "actual_exit_returncode")
        if index < len(jobs):
            exit_summary.append({"id": phase["job_id"], "phase": phase["phase"],
                                 "child_launched": any(event.get("pid") is not None for event in phase_events),
                                 "returncode": actual_exits[-1]["returncode"] if actual_exits else None})
        summary = phase_receipts(phase, mapping[phase["phase"]], source, reference, phase_events, service, run)
        normal = index < len(safety["exits"]) and safety["exits"][index]["normal_exit"]
        completed = index < len(jobs) and jobs[index]["status"] == "completed" and normal
        summary.update(submitted=index < len(jobs), normal_exit=bool(normal), completed=bool(completed),
                       cost_complete=bool(completed), unacknowledged_attempts=0 if completed else None,
                       cost_scope="completed_phase" if completed else "acknowledged_results_lower_bound")
        summaries.append(summary)
    if len(jobs) == 2:
        require(summaries[0]["receipt_resource_violations"] == 0, "research_after_prelude_receipt_resource_failure")
    require(run.get("child_exit_summary") == exit_summary, "child_exit_summary_binding")
    require(run.get("completed_jobs") == sum(job["status"] == "completed" for job in jobs)
            and run.get("completed_events") == len(results), "run_completion_counts")
    research_events = [event for event in events if event.get("job_id") == PHASES[1]["job_id"]]
    stages = M3.stage_summary(stage_bytes, run, research_events, samples)
    require(len(jobs) == 2 or not stage_bytes, "stage_journal_without_research")
    rrows = mapping[PHASES[1]["phase"]]
    require(stages["predict_complete_ordinals"][:len(rrows)] == list(range(len(rrows))), "receipt_without_research_stage")
    markers = read_lines(stage_bytes, allow_tail=True)[0]
    completed_markers = {event["item_ordinal"]: event["monotonic"] for event in markers if event["stage"] == "predict_complete"}
    for row in rrows:
        require(completed_markers[row["ordinal"]] <= row["result"]["telemetry"]["monotonic"], "research_receipt_stage_clock")
    if len(rrows) == 7:
        counts = Counter(span["stage"] for span in stages["closed_stages"] if span["outcome"] == "end")
        expected = {stage: 1 for stage in M3.STAGES}
        expected.update(request_predict=7, m1_predict=len({row["input_sha256"] for row in plan["prefix_rows"]}))
        require(dict(counts) == expected, "complete_stage_coverage")
    all_complete = len(jobs) == 2 and all(summary["completed"] for summary in summaries) and stages["stage_completion_gate"]
    if run["status"] == "Completed":
        require(all_complete and run.get("failure_code") is None, "false_sequence_completion")
    else:
        require(isinstance(run.get("failure_code"), str) and bool(run["failure_code"]), "missing_failure_code")
    if run.get("failure_code") == "critical_memory_pressure":
        require(safety["system"]["critical_samples"] > 0, "critical_stop_without_observation")
    work_deadline = run["started_monotonic"]+150
    work_gate = all(event["monotonic"] <= work_deadline for event in markers if event["kind"] != "error")
    work_gate = work_gate and all(row["result"]["telemetry"]["monotonic"] <= work_deadline for row in results)
    readiness_gate = (bool(attempts) and len(attempts) == len(jobs) and all(attempt["status"] == "Ready"
                      and attempt["ended_monotonic"]-attempt["started_monotonic"] <= 60+1e-6 for attempt in attempts))
    stage_gate = stages["memory_resource_violations"] == stages["unknown_memory_after_limits"] == 0
    receipt_gate = not any(summary["receipt_resource_violations"] for summary in summaries)
    safety.update(work_budget_gate=work_gate, readiness_attempt_gate=readiness_gate,
                  stage_resource_gate=stage_gate, receipt_resource_gate=receipt_gate)
    safety["gate_passed"] = safety["gate_passed"] and work_gate and readiness_gate and stage_gate and receipt_gate
    return {"planned_jobs": 2, "planned_events": 347, "submitted_jobs": len(jobs),
            "verified_acknowledged_events": len(results), "missing_acknowledged_events": 347-len(results),
            "phases": summaries, "all_planned_phases_completed": bool(all_complete),
            "diagnostic_completed": bool(all_complete and safety["gate_passed"] and run["status"] == "Completed"),
            "safety": safety, "stage_summary": stages, "critical_at_stage": stages["critical_at_stage"],
            "operational_followup_authorized": False, "operational_state": "stop-required",
            "claim_boundary": "One finite 340-M1 then 7-Research sequence, including input/asset reads, caches and exits; EXP-082 parity is not gold accuracy. Different times and whole-machine states prevent single-run causal attribution; EXP-079 remains incomplete and EXP-080 is not authorized."}


def check_bindings(plan, run, claim, service, before):
    require(run.get("plan_sha256") == before["plan.json"] == claim.get("plan_sha256"), "plan_hash_binding")
    require(run.get("source_hashes") == {str((RUN/name).relative_to(ROOT)): digest for name,digest in before.items() if name != "run.json"}, "artifact_hash_binding")
    parents = {}
    for name,digest in PARENT_HASHES.items():
        relative = f"private/validation/exp-082/attempt-1/{name}.json"
        require(plan.get("parent_bindings", {}).get(name) == {"path": relative, "sha256": digest}
                and regular_file(path_for(relative)) == digest, "parent_hash_binding")
        parents[name] = LOCAL.strict_json(path_for(relative).read_text())
    require(parents["run"].get("status") == "Completed" and parents["run"].get("completed_events") == 7
            and parents["verification"].get("status") == "Passed" and parents["verification"].get("diagnostic_completed") is True
            and parents["verification"].get("safety", {}).get("gate_passed") is True, "parent_terminal_identity")
    for name,digest in parents["verification"]["source_hashes"].items():
        require(regular_file(path_for(name)) == digest, "parent_artifact_identity")
    binding = {"path": "private/validation/exp-079/attempt-3/plan.json", "sha256": SOURCE_PLAN_HASH}
    require(plan.get("source_plan_binding") == parents["plan"]["parent_bindings"]["plan"] == binding
            and regular_file(path_for(binding["path"])) == binding["sha256"], "source_plan_binding")
    source_plan = LOCAL.strict_json(path_for(binding["path"]).read_text())
    require(plan.get("source_rows") == source_plan["source_rows"] and plan.get("source_logical_sha256") == source_plan["source_logical_sha256"]
            and plan.get("prefix_rows") == parents["plan"]["source_rows"], "source_parent_mapping")
    sources = plan.get("sources")
    require(isinstance(sources, dict) and set(sources) == set(parents["plan"]["sources"]) | ADDITIONAL_SOURCES
            and all(sources.get(name) == digest for name,digest in parents["plan"]["sources"].items()), "dependency_set")
    for name,digest in sources.items():
        require(regular_file(path_for(name)) == digest, "implementation_identity_drift")
    require(plan.get("protocol", {}).get("path") == PROTOCOL
            and regular_file(path_for(PROTOCOL, ROOT.parent)) == plan["protocol"].get("sha256"), "protocol_identity")
    close(service, {"experiment_id": "EXP-083", "root": str(ROOT), "bench_root": str(RUN/"bench"), "port": None}, "supervisor_scope")
    close(claim, {"experiment_id": "EXP-083", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", "cwd": str(ROOT),
                  "training": False, "gold_accessed": False, "source_network_fetched": False}, "claim_contract")
    require(all(claim.get(key) == run.get(key) for key in ("started_at", "started_monotonic")), "claim_start_binding")
    require(isinstance(claim.get("environment"), dict) and isinstance(claim.get("git_commit"), str)
            and isinstance(claim.get("git_status_porcelain"), list) and isinstance(claim.get("command"), list), "claim_environment_schema")
    return read_lines((ROOT/"private/validation/exp-082/attempt-1/results.jsonl").read_bytes())[0]


def main():
    target = RUN/"verification.json"
    require(not target.exists() and not any(p.is_symlink() for p in (target,*target.parents)), "verification_exists_or_symlink")
    before = {name: regular_file(RUN/name) for name in ARTIFACTS}
    report = {"experiment_id": "EXP-083", "attempt": 1, "tier": "Minor", "status": "Failed", "diagnostic_completed": False,
              "operational_followup_authorized": False, "operational_state": "stop-required", "models_loaded": False,
              "producer_numerical_helpers_imported": False, "gold_accessed": False,
              "verified_at": datetime.now(timezone.utc).isoformat(), "verifier_sha256": regular_file(Path(__file__)),
              "source_hashes": {str((RUN/name).relative_to(ROOT)): digest for name,digest in before.items()}}
    try:
        plan, run, claim, service = (LOCAL.strict_json((RUN/name).read_text()) for name in ("plan.json", "run.json", "run-claim.json", "service.json"))
        reference = check_bindings(plan, run, claim, service, before)
        require(B.service_absent(service), "diagnostic_supervisor_still_running")
        source = read_source(path_for(plan["source_database"]))
        logical = sha(LOCAL.canonical(source))
        results, samples, events = (read_lines((RUN/name).read_bytes())[0] for name in ("results.jsonl", "samples.jsonl", "process-events.jsonl"))
        report.update(analyze(plan, run, source, reference, results, samples, events, service, (RUN/"stages.jsonl").read_bytes()))
        require(sha(LOCAL.canonical(read_source(path_for(plan["source_database"])))) == logical, "source_changed_during_audit")
        require(all(regular_file(RUN/name) == digest for name,digest in before.items()), "artifact_changed_during_audit")
        require(all(regular_file(path_for(name)) == digest for name,digest in plan["sources"].items()), "dependency_changed_during_audit")
        report.update(status="Passed", source_logical_sha256=logical)
    except Exception as error:
        code = str(error) if isinstance(error, (B.VerificationError, LOCAL.VerificationError)) else type(error).__name__
        report.update(status="Failed", diagnostic_completed=False,
                      error_code=code if re.fullmatch(r"[A-Za-z0-9_]{1,100}", code) else "verification_failed")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+"\n")
    print(json.dumps({key: report.get(key) for key in ("status", "diagnostic_completed", "operational_followup_authorized", "error_code")}))
    return 0 if report["status"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
