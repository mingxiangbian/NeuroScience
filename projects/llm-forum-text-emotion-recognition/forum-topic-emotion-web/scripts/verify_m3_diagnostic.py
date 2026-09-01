"""Independent EXP-082 prefix/stage/exit audit; no model or producer imports."""
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
RUN = ROOT / "private/validation/exp-082/attempt-1"
SPEC = importlib.util.spec_from_file_location("exp082_independent_safety", ROOT / "scripts/verify_bounded_runtime.py")
BOUNDED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BOUNDED)
LOCAL = BOUNDED.LOCAL
require, close, sha, finite = BOUNDED.require, BOUNDED.close, BOUNDED.sha, BOUNDED.finite
regular_file = BOUNDED.regular_file
SOURCE_JOB = "5ab3326150ee448ba326233264967d34"
SOURCE_SNAPSHOT = "cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16"
PARENT_HASHES = {
    "plan": "6635d7022959642ae0adff5c42b483ca30a0cc598924ee814c25667c1e5d236c",
    "run": "990efbb28bf91025b6554d3756e2f471a8edd8eac8a1962535cb98384e2a0722",
    "verification": "2f078610f6ff4be0d17fdd047cbca0f6d156425e577ddba34cbe1d30581990ec",
}
ADDITIONAL_SOURCES = {
    "scripts/run_m3_diagnostic.py", "scripts/diagnostic_m3_child.py", "scripts/verify_m3_diagnostic.py",
    "tests/test_m3_diagnostic.py", "tests/test_diagnostic_m3_child.py", "tests/test_verify_m3_diagnostic.py",
}
PROTOCOL = "experiments/stack-overflow-emotion-gold/protocols/exp-082-first-m3-memory-diagnostic.md"
ARTIFACTS = ("service.json", "plan.json", "run-claim.json", "results.jsonl", "samples.jsonl",
             "process-events.jsonl", "stages.jsonl", "stdout.log", "run.json")
STAGES = {
    "engine_build", "m1_load", "request_predict", "m1_predict", "m3_factory", "mlx_import", "m3_backend_init",
    "adapter_head_numpy_load", "base_load", "lora_setup", "adapter_load", "head_load",
    "adapter_head_eval", "m3_predict", "m3_tokenization", "first_forward",
}
POINTS = {"mlx_limits_configured", "predict_complete"}


def path_for(name, root=None):
    return BOUNDED.source_path(name, ROOT if root is None else root)


def read_lines(raw, *, allow_tail=False):
    """Only newline-terminated JSON is a committed event, even if a tail parses."""
    require(isinstance(raw, bytes), "journal_bytes")
    split = raw.rfind(b"\n") + 1
    committed, tail = raw[:split], raw[split:]
    require(allow_tail or not tail, "unterminated_artifact_line")
    rows = []
    for line in committed.splitlines():
        require(bool(line.strip()), "empty_artifact_line")
        rows.append(LOCAL.strict_json(line.decode("utf-8")))
    return rows, {"bytes": len(tail), "sha256": sha(tail) if tail else None,
                  "treated_as_complete_event": False}


def read_prefix(database, expected):
    """The full 340-row snapshot identity is inherited; only seven rows are read."""
    require(database.is_file() and not any(p.is_symlink() for p in (database, *database.parents)), "source_database_identity")
    with sqlite3.connect(database.as_uri()+"?mode=ro", uri=True, timeout=1) as db:
        metadata = db.execute("SELECT state,snapshot_hash,total_items FROM jobs WHERE id=?", (SOURCE_JOB,)).fetchone()
        rows = db.execute("SELECT ordinal,record,result FROM items WHERE job_id=? AND ordinal>=0 AND ordinal<7 ORDER BY ordinal", (SOURCE_JOB,)).fetchall()
    require(metadata == ("completed", SOURCE_SNAPSHOT, 340), "source_job_identity")
    require([row[0] for row in rows] == list(range(7)), "source_prefix_count")
    records, baseline = [], []
    for (ordinal, raw, receipt), planned in zip(rows, expected):
        record = LOCAL.strict_json(raw)
        result = LOCAL.strict_json(receipt)
        require(record.get("model_input_hash") == planned["input_sha256"] == sha(record.get("model_input_text", "")), "source_input_identity")
        require(result.get("hypothetical_route") is planned["route_eligible"], "source_route_identity")
        LOCAL.probabilities(result.get("m1_probabilities"))
        records.append(record)
        baseline.append(result)
    prefix_hash = LOCAL.check_records(records)
    return baseline, sha(LOCAL.canonical({"prefix_records_sha256": prefix_hash, "results": baseline}))


def validate_plan(plan):
    close(plan, {"experiment_id": "EXP-082", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", "planned_events": 7,
                 "max_seconds": 180, "work_seconds": 150, "max_readiness_seconds": 60, "cleanup_seconds": 15,
                 "mode": "research", "max_qwen_calls": 1, "audit_rate": 0, "seed": 42,
                 "source_job": SOURCE_JOB, "source_snapshot_sha256": SOURCE_SNAPSHOT,
                 "source_database": "private/jobs.sqlite3"}, "plan_contract")
    rows = plan.get("source_rows")
    require(isinstance(rows, list) and len(rows) == 7 and [row.get("ordinal") for row in rows] == list(range(7)), "source_prefix_contract")
    require([row.get("route_eligible") for row in rows] == [False]*6+[True]
            and all(type(row["route_eligible"]) is bool and re.fullmatch(r"[a-f0-9]{64}", row.get("input_sha256", "")) for row in rows), "source_prefix_route_hash")


def stage_summary(raw, run, process_events, samples):
    events, tail = read_lines(raw, allow_tail=True)
    require([event.get("seq") for event in events] == list(range(len(events))), "stage_sequence")
    pids = {event.get("pid") for event in events}
    require(len(pids) <= 1 and all(type(pid) is int and pid > 0 for pid in pids), "stage_pid_schema")
    known_pids = {event["pid"] for event in process_events if event.get("pid") is not None}
    require(pids <= known_pids, "stage_process_identity")
    exits = [event for event in process_events if event["type"] == "process_exit"]
    constructors = [event for event in process_events if event["type"] == "constructor_started"]
    start = constructors[0]["monotonic"] if constructors else run["started_monotonic"]
    end = exits[-1]["monotonic"] if exits else run["ended_monotonic"]
    stack, spans, points, errors = [], [], [], []
    requests, completed, memory_states = [], [], Counter()
    limits_seen, previous_time, rss_peak, mlx_peak = False, start, None, None
    memory_violations = unknown_after_limits = 0
    required_keys = {"seq", "pid", "monotonic", "kind", "stage", "item_ordinal", "memory"}
    for event in events:
        require(set(event) == required_keys and finite(event.get("monotonic"))
                and previous_time <= event["monotonic"] <= end, "stage_clock_or_schema")
        previous_time = event["monotonic"]
        kind, stage, ordinal = event["kind"], event["stage"], event["item_ordinal"]
        require(kind in {"begin", "end", "error", "point"}
                and stage in (POINTS if kind == "point" else STAGES), "stage_kind")
        require(ordinal is None or type(ordinal) is int and 0 <= ordinal < 7, "stage_ordinal")
        if stage in {"engine_build", "m1_load"}:
            require(ordinal is None, "initialization_ordinal")
        else:
            require(ordinal is not None, "request_stage_ordinal_missing")
        if kind == "begin":
            if stage == "request_predict":
                require(not stack and ordinal == len(requests), "request_stage_order")
                requests.append(ordinal)
            elif stage == "engine_build":
                require(not stack and not spans and not requests, "engine_stage_order")
            else:
                require(bool(stack) and stack[-1]["item_ordinal"] == ordinal, "stage_parent_ordinal")
            if stage.startswith("m3_") or stage in {"mlx_import", "adapter_head_numpy_load", "base_load", "lora_setup", "adapter_load", "head_load", "adapter_head_eval", "first_forward"}:
                require(ordinal == 6, "m3_before_first_route")
            stack.append(event)
        elif kind in {"end", "error"}:
            require(bool(stack) and (stack[-1]["stage"], stack[-1]["item_ordinal"]) == (stage, ordinal), "stage_close_order")
            opened = stack.pop()
            spans.append({"stage": stage, "item_ordinal": ordinal, "begin_seq": opened["seq"], "end_seq": event["seq"],
                          "started_monotonic": opened["monotonic"], "ended_monotonic": event["monotonic"], "outcome": kind})
            if kind == "error": errors.append({"stage": stage, "item_ordinal": ordinal, "seq": event["seq"]})
        elif stage == "mlx_limits_configured":
            require(not limits_seen and ordinal == 6 and any(row["stage"] == "m3_factory" for row in stack), "mlx_limits_stage")
            limits_seen = True
            points.append(event)
        else:
            require(not stack and spans and spans[-1]["stage"] == "request_predict" and spans[-1]["outcome"] == "end"
                    and spans[-1]["item_ordinal"] == ordinal and ordinal == len(completed), "predict_complete_stage")
            completed.append(ordinal)
            points.append(event)
        memory = event["memory"]
        require(isinstance(memory, dict) and set(memory) == {"rss_peak_bytes", "mlx_status", "active_bytes", "cache_bytes", "peak_bytes"}, "stage_memory_schema")
        rss = memory["rss_peak_bytes"]
        require(type(rss) is int and rss >= 0 and (rss_peak is None or rss >= rss_peak), "stage_rss_peak")
        rss_peak = rss
        state = memory["mlx_status"]
        require(state in {"not_loaded", "not_sampled", "observed"}, "stage_mlx_status")
        memory_states[state] += 1
        values = [memory[name] for name in ("active_bytes", "cache_bytes", "peak_bytes")]
        if state == "observed":
            require(limits_seen and all(type(value) is int and value >= 0 for value in values), "stage_mlx_observation")
            mlx_peak = values[-1] if mlx_peak is None else max(mlx_peak, values[-1])
            memory_violations += values[-1] > 10_000_000_000
        else:
            require(all(value is None for value in values), "unmeasured_memory_not_null")
            unknown_after_limits += limits_seen
        memory_violations += rss > 12*1024**3
    open_stages = [{"stage": row["stage"], "item_ordinal": row["item_ordinal"], "begin_seq": row["seq"],
                    "started_monotonic": row["monotonic"], "ended_monotonic": None} for row in stack]
    critical = []
    for sample in samples:
        observed = BOUNDED.parse_system(sample["system"])
        if observed is None or observed["pressure_level"] != 4:
            continue
        when = sample["system"]["monotonic"]
        active = [span for span in spans if span["started_monotonic"] <= when < span["ended_monotonic"]]
        active += [span for span in open_stages if span["started_monotonic"] <= when <= end]
        before = [event for event in events if event["monotonic"] <= when]
        critical.append({"sample_index": sample["index"], "monotonic": when,
                         "active_stages": [{"stage": row["stage"], "item_ordinal": row["item_ordinal"]} for row in sorted(active, key=lambda row: row["begin_seq"])],
                         "last_committed_marker": {key: before[-1][key] for key in ("seq", "stage", "kind", "item_ordinal", "monotonic")} if before else None,
                         "causal_attribution": False})
    return {"committed_events": len(events), "request_ordinals": requests, "predict_complete_ordinals": completed,
            "closed_stages": spans, "open_stages": open_stages, "errors": errors, "truncated_tail": tail,
            "memory_status_counts": dict(memory_states), "rss_peak_bytes": rss_peak, "observed_mlx_peak_bytes": mlx_peak,
            "memory_resource_violations": memory_violations, "unknown_memory_after_limits": unknown_after_limits,
            "critical_at_stage": critical,
            "stage_completion_gate": bool(events) and limits_seen and completed == list(range(7)) and not (stack or errors or tail["bytes"] or unknown_after_limits)}


def analyze(plan, run, results, baseline, samples, process_events, service, stage_bytes):
    validate_plan(plan)
    close(run, {"experiment_id": "EXP-082", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", "planned_events": 7,
                "training": False, "gold_accessed": False, "source_network_fetched": False,
                "operational_followup_authorized": False}, "run_contract")
    require(run.get("status") in {"Completed", "Stopped", "Failed"} and finite(run.get("started_monotonic"))
            and finite(run.get("ended_monotonic")) and run["ended_monotonic"] >= run["started_monotonic"], "run_clock_status")
    close(run.get("elapsed_seconds"), run["ended_monotonic"]-run["started_monotonic"], "run_elapsed")
    require(run.get("total_budget_exceeded") is (run["elapsed_seconds"] > 180), "total_budget_flag")
    require(all(run["started_monotonic"] <= sample["started_monotonic"] <= sample["monotonic"] <= run["ended_monotonic"] for sample in samples)
            and all(run["started_monotonic"] <= event["monotonic"] <= run["ended_monotonic"] for event in process_events), "run_observation_window")
    require(len(results) <= 7 and [row.get("ordinal") for row in results] == list(range(len(results)))
            and run.get("completed_events") == len(results), "result_prefix_count")
    require(len(baseline) == 7, "baseline_prefix_count")
    job = run.get("job")
    require(job is None or job.get("id") == "exp082-prefix7" and job.get("mode") == "research"
            and job.get("status") in {"completed", "cancelled", "failed"}
            and job.get("total_items") == 7 and job.get("completed_items") == len(results), "job_contract")
    exits = [event for event in process_events if event.get("type") == "process_exit"]
    require((run.get("child_returncode") is None or type(run["child_returncode"]) is int)
            and all(type(event.get("returncode")) is int for event in exits)
            and run.get("child_returncode") == (exits[-1]["returncode"] if exits else None)
            and type(run.get("child_launched")) is bool
            and run["child_launched"] is any(event.get("pid") is not None for event in process_events), "child_exit_binding")
    if job is None:
        require(not results and not process_events and not stage_bytes, "unlaunched_child_artifacts")
    readiness = run.get("readiness")
    require(isinstance(readiness, dict) and readiness.get("status") in {"Ready", "NotReady"}
            and finite(readiness.get("started_monotonic")) and finite(readiness.get("ended_monotonic"))
            and run["started_monotonic"] <= readiness["started_monotonic"] <= readiness["ended_monotonic"] <= run["ended_monotonic"], "readiness_contract")
    if job is not None:
        require(readiness["status"] == "Ready" and readiness.get("indices") == job.get("readiness_indices")
                and readiness["started_monotonic"] == job.get("readiness_started_monotonic")
                and readiness["ended_monotonic"] == job.get("readiness_ended_monotonic"), "readiness_job_binding")
    safety = BOUNDED.verify_safety(samples, process_events, service, [job] if job else [], elapsed_seconds=run["elapsed_seconds"], limit_seconds=180)
    readiness_gate = readiness["status"] == "Ready" and readiness["ended_monotonic"]-readiness["started_monotonic"] <= 60+1e-6
    safety["readiness_gate"] = safety["readiness_gate"] and readiness_gate
    require(run.get("cleanup") == (job.get("cleanup") if job else None), "cleanup_job_binding")
    if job is not None and job.get("cleanup"):
        require(job["cleanup"]["started_monotonic"] <= job["cleanup"]["ended_monotonic"] <= job["ended_monotonic"] <= run["ended_monotonic"], "cleanup_run_window")
    costs = {name: 0 for name in BOUNDED.COSTS}
    seen = set()
    receipt_violations = 0
    for row in results:
        index, result = row["ordinal"], row["result"]
        hashed = plan["source_rows"][index]["input_sha256"]
        require(row.get("input_sha256") == hashed, "receipt_input_identity")
        p1 = LOCAL.probabilities(result.get("m1_probabilities"))
        d1 = LOCAL.decisions(result.get("m1_prediction"))
        require(max(abs(a-b) for a, b in zip(p1, LOCAL.probabilities(baseline[index].get("m1_probabilities")))) <= 1e-6
                and d1 == [int(value >= .31) for value in p1], "m1_replay_identity")
        routed = index == 6
        require(result.get("route_requested") is routed and result.get("hypothetical_route") is routed
                and result.get("used_path") == ("m3" if routed else "m1") and result.get("fallback_reason") is None
                and result.get("fallback") is False, "receipt_route_contract")
        selected = d1
        if routed:
            p3 = LOCAL.probabilities(result.get("m3_probabilities"))
            selected = LOCAL.decisions(result.get("m3_prediction"))
            require(selected == [int(value >= .31) for value in p3], "m3_threshold_identity")
        else:
            require(result.get("m3_probabilities") is None and result.get("m3_prediction") is None, "unrouted_m3_receipt")
        require(LOCAL.decisions(result.get("prediction")) == selected, "prediction_path_identity")
        expected = {name: 0 for name in costs}
        expected.update(m1_attempts=int(hashed not in seen), m1_cache_hit=int(hashed in seen), m3_attempts=int(routed), m3_succeeded=int(routed))
        seen.add(hashed)
        close(result.get("counters"), expected, "receipt_cost_identity")
        costs = {name: costs[name]+expected[name] for name in costs}
        close(result.get("cumulative_counters"), costs, "cumulative_cost_identity")
        require(all(type(result[field].get(name)) is int for field in ("counters", "cumulative_counters") for name in costs), "receipt_cost_types")
        child_rss, parent_rss = BOUNDED.result_rss(result.get("telemetry"))
        require(result["telemetry"]["parent_pid"] == service["pid"]
                and any(event.get("pid") == result["telemetry"]["child_pid"] for event in process_events), "receipt_process_identity")
        resources = result.get("resources")
        require(isinstance(resources, dict) and all(type(resources.get(key)) is int and resources[key] >= 0 for key in ("peak_rss_bytes", "mlx_peak_bytes")), "receipt_resource_schema")
        receipt_violations += child_rss > 12*1024**3 or parent_rss > 1024**3 or resources["peak_rss_bytes"] > 12*1024**3 or resources["mlx_peak_bytes"] > 10_000_000_000
    stages = stage_summary(stage_bytes, run, process_events, samples)
    require(stages["predict_complete_ordinals"][:len(results)] == list(range(len(results))), "receipt_without_completed_stage")
    committed = read_lines(stage_bytes, allow_tail=True)[0]
    completed_markers = {event["item_ordinal"]: event["monotonic"] for event in committed if event["stage"] == "predict_complete"}
    for row in results:
        when = row["result"]["telemetry"].get("monotonic")
        require(finite(when) and completed_markers[row["ordinal"]] <= when <= exits[-1]["monotonic"], "receipt_stage_clock")
    closed_counts = Counter(span["stage"] for span in stages["closed_stages"] if span["outcome"] == "end")
    expected_counts = {stage: 1 for stage in STAGES}
    expected_counts.update(request_predict=7, m1_predict=len({row["input_sha256"] for row in plan["source_rows"]}))
    if len(results) == 7:
        require(dict(closed_counts) == expected_counts, "complete_stage_coverage")
    work_deadline = run["started_monotonic"] + plan["work_seconds"]
    work_gate = all(event["monotonic"] <= work_deadline for event in committed if event["kind"] != "error")
    work_gate = work_gate and all(row["result"]["telemetry"]["monotonic"] <= work_deadline for row in results)
    normal = bool(safety["exits"] and safety["exits"][0]["normal_exit"])
    complete = len(results) == 7 and normal and stages["stage_completion_gate"]
    if run["status"] == "Completed":
        require(complete and run.get("failure_code") is None, "false_diagnostic_completion")
    else:
        require(isinstance(run.get("failure_code"), str) and bool(run["failure_code"]), "missing_failure_code")
    if run.get("failure_code") == "critical_memory_pressure":
        require(safety["system"]["critical_samples"] > 0, "critical_stop_without_observation")
    safety.update(stage_resource_gate=stages["memory_resource_violations"] == 0 and stages["unknown_memory_after_limits"] == 0,
                  receipt_resource_gate=receipt_violations == 0, work_budget_gate=work_gate)
    safety["gate_passed"] = safety["gate_passed"] and readiness_gate and safety["stage_resource_gate"] and safety["receipt_resource_gate"] and work_gate
    return {"planned_events": 7, "verified_acknowledged_events": len(results), "missing_acknowledged_events": 7-len(results),
            "diagnostic_completed": bool(complete and run["status"] == "Completed"), "safety": safety,
            "acknowledged_cost_lower_bound": costs, "cost_complete": bool(complete),
            "unacknowledged_attempts": 0 if complete else None,
            "cost_scope": "completed_diagnostic" if complete else "acknowledged_results_lower_bound",
            "stage_summary": stages, "critical_at_stage": stages["critical_at_stage"],
            "operational_followup_authorized": False, "operational_state": "stop-required",
            "claim_boundary": "Seven frozen inputs only; committed stages localize an observation interval, not an allocation cause. Missing MLX samples and unacknowledged attempts are not observed zero; no EXP-079 completion, efficiency, accuracy or generalization claim."}


def check_bindings(plan, run, claim, service, before):
    require(run.get("plan_sha256") == before["plan.json"] == claim.get("plan_sha256"), "plan_hash_binding")
    require(run.get("source_hashes") == {str((RUN/name).relative_to(ROOT)): digest for name, digest in before.items() if name != "run.json"}, "artifact_hash_binding")
    parents = {}
    for name, digest in PARENT_HASHES.items():
        relative = f"private/validation/exp-079/attempt-3/{name}.json"
        require(plan.get("parent_bindings", {}).get(name) == {"path": relative, "sha256": digest}
                and regular_file(path_for(relative)) == digest, "parent_hash_binding")
        parents[name] = LOCAL.strict_json(path_for(relative).read_text())
    require(parents["verification"].get("status") == "Passed" and parents["verification"].get("exp079_complete") is False
            and parents["verification"].get("operational_state") == "stop-required"
            and parents["run"].get("status") == "Stopped" and parents["run"].get("failure_code") == "critical_memory_pressure", "parent_terminal_identity")
    require(plan.get("source_rows") == parents["plan"]["source_rows"][:7], "parent_prefix_binding")
    sources = plan.get("sources")
    require(isinstance(sources, dict) and set(sources) == set(parents["plan"]["sources"]) | ADDITIONAL_SOURCES
            and all(sources[name] == digest for name, digest in parents["plan"]["sources"].items()), "dependency_set")
    for name, digest in sources.items():
        require(regular_file(path_for(name)) == digest, "implementation_identity_drift")
    for name, digest in parents["verification"].get("source_hashes", {}).items():
        require(regular_file(path_for(name)) == digest, "parent_artifact_identity")
    require(plan.get("protocol", {}).get("path") == PROTOCOL
            and regular_file(path_for(PROTOCOL, ROOT.parent)) == plan["protocol"].get("sha256"), "protocol_identity")
    close(service, {"experiment_id": "EXP-082", "root": str(ROOT), "bench_root": str(RUN/"bench"), "port": None}, "supervisor_scope")
    close(claim, {"experiment_id": "EXP-082", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", "cwd": str(ROOT),
                  "training": False, "gold_accessed": False, "source_network_fetched": False}, "claim_contract")
    require(all(claim.get(key) == run.get(key) for key in ("started_at", "started_monotonic")), "claim_start_binding")
    require(isinstance(claim.get("environment"), dict) and isinstance(claim.get("git_commit"), str)
            and isinstance(claim.get("git_status_porcelain"), list) and isinstance(claim.get("command"), list), "claim_environment_schema")


def main():
    target = RUN / "verification.json"
    require(not target.exists() and not any(p.is_symlink() for p in (target, *target.parents)), "verification_exists_or_symlink")
    before = {name: regular_file(RUN/name) for name in ARTIFACTS}
    report = {"experiment_id": "EXP-082", "attempt": 1, "tier": "Minor", "status": "Failed", "diagnostic_completed": False,
              "operational_followup_authorized": False, "operational_state": "stop-required",
              "verified_at": datetime.now(timezone.utc).isoformat(), "models_loaded": False,
              "producer_numerical_helpers_imported": False, "gold_accessed": False,
              "source_hashes": {str((RUN/name).relative_to(ROOT)): digest for name, digest in before.items()},
              "verifier_sha256": regular_file(Path(__file__))}
    try:
        plan, run, claim, service = (LOCAL.strict_json((RUN/name).read_text()) for name in ("plan.json", "run.json", "run-claim.json", "service.json"))
        validate_plan(plan)
        check_bindings(plan, run, claim, service, before)
        require(BOUNDED.service_absent(service), "diagnostic_supervisor_still_running")
        baseline, prefix_hash = read_prefix(path_for(plan["source_database"]), plan["source_rows"])
        results, samples, events = (read_lines((RUN/name).read_bytes())[0] for name in ("results.jsonl", "samples.jsonl", "process-events.jsonl"))
        report.update(analyze(plan, run, results, baseline, samples, events, service, (RUN/"stages.jsonl").read_bytes()))
        require(read_prefix(path_for(plan["source_database"]), plan["source_rows"])[1] == prefix_hash, "source_prefix_changed")
        require(all(regular_file(RUN/name) == digest for name, digest in before.items()), "artifact_changed_during_verification")
        require(all(regular_file(path_for(name)) == digest for name, digest in plan["sources"].items()), "dependency_changed_during_verification")
        report.update(status="Passed", source_prefix_logical_sha256=prefix_hash,
                      source_record_read_scope="Only ordinals 0..6; complete 340-row snapshot identity inherited from bound parent certificate.")
    except Exception as error:
        code = str(error) if isinstance(error, (BOUNDED.VerificationError, LOCAL.VerificationError)) else type(error).__name__
        report.update(status="Failed", diagnostic_completed=False,
                      error_code=code if re.fullmatch(r"[A-Za-z0-9_]{1,100}", code) else "verification_failed")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+"\n")
    print(json.dumps({key: report.get(key) for key in ("status", "diagnostic_completed", "operational_followup_authorized", "error_code")}))
    return 0 if report["status"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
