"""EXP-086 independent staged Discourse source, semantics and safety audit."""
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
import tarfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "private/validation/exp-086/attempt-1"
PROTOCOL = "experiments/stack-overflow-emotion-gold/protocols/exp-086-staged-discourse-formal.md"
QUERY = {"site": "discuss.python.org", "category_id": 7, "max_topics": 100, "max_items": 400}
PARENT_HASHES = {
    "plan": "fc72df94b88315752c0e896af1636779391b4baeee01757041b5d1134faeb28a",
    "run": "3ec838fbfbc68867a98496f80ee0eb34c62cb74c2a3b7467a1554ce45f176b1d",
    "verification": "a33ba29be93e631074b07c140a4fdbad9566b4aa9483633ab31497dcd91af13a",
}
PARENT_ARCHIVE_SHA256 = "56386775dd61226ba3fe7f214c89b3a55cad393bb61ed868b77bc5f6082f0435"


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STAGED = load("exp086_independent_staged", "scripts/verify_staged_runtime.py")
SOURCE = load("exp086_independent_source", "scripts/verify_discourse_validation.py")
B, LOCAL = STAGED.B, STAGED.LOCAL
require, close, sha = B.require, B.close, B.sha
JOURNALS = STAGED.JOURNALS


def check_parent(plan):
    bindings = plan.get("parent_exp085")
    require(isinstance(bindings, dict) and set(bindings) == {"plan", "run", "verification", "archive"}, "parent_binding_schema")
    documents = {}
    for name, expected in PARENT_HASHES.items():
        relative = f"private/validation/exp-085/attempt-2/{name}.json"
        require(bindings[name] == {"path": relative, "sha256": expected}
                and B.regular_file(ROOT / relative) == expected, "parent_artifact_binding")
        documents[name] = LOCAL.strict_json((ROOT / relative).read_text())
    run, verification, parent_plan = documents["run"], documents["verification"], documents["plan"]
    require(run.get("experiment_id") == "EXP-085" and run.get("attempt") == 2
            and run.get("status") == "Completed" and run.get("failure_code") is None, "parent_run_not_complete")
    require(verification.get("experiment_id") == "EXP-085" and verification.get("attempt") == 2
            and verification.get("status") == "Passed" and verification.get("exp085_complete") is True
            and verification.get("operational_state") == "safe-to-continue"
            and verification.get("safety", {}).get("gate_passed") is True, "parent_verification_not_safe")
    archive_binding = {"path": "private/validation/exp-085/attempt-2/frozen-code.tar.gz",
                       "sha256": PARENT_ARCHIVE_SHA256, "members": 33}
    require(bindings["archive"] == archive_binding, "parent_archive_binding")
    archive_path = ROOT / archive_binding["path"]
    require(B.regular_file(archive_path) == PARENT_ARCHIVE_SHA256, "parent_archive_hash")
    sources = parent_plan.get("sources")
    require(isinstance(sources, dict) and len(sources) == 32, "parent_source_count")
    expected_members = {**sources, "protocol.md": parent_plan["protocol"]["sha256"]}
    actual, total = {}, 0
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive:
            require(not Path(member.name).is_absolute() and ".." not in Path(member.name).parts and member.isfile()
                    and member.name in expected_members and member.name not in actual and member.size <= 2 * 1024**2,
                    "parent_archive_member")
            stream = archive.extractfile(member)
            require(stream is not None, "parent_archive_payload")
            payload = stream.read(member.size + 1); total += len(payload)
            require(len(payload) == member.size and total <= 32 * 1024**2, "parent_archive_payload")
            actual[member.name] = sha(payload)
    require(actual == expected_members and B.regular_file(archive_path) == PARENT_ARCHIVE_SHA256, "parent_archive_sources")
    return ({"status": "Passed", "exp085_complete": True, "safety_gate_passed": True,
             "archive_members": 33, "archive_sha256": PARENT_ARCHIVE_SHA256}, parent_plan)


def check_transfer(envelope, prelude, logical_job_id):
    require(len(prelude) >= 1 and envelope.get("logical_job_id") == logical_job_id
            and envelope.get("phase_id") == logical_job_id + ":m3"
            and envelope.get("m1_receipts_sha256") == STAGED.receipt_digest(prelude), "transfer_prelude_binding")
    transfer = envelope.get("transfer")
    require(isinstance(transfer, dict) and set(transfer) == {"base_fingerprint", "entries"}
            and envelope.get("transfer_sha256") == sha(LOCAL.canonical(transfer)), "transfer_schema")
    entries = transfer["entries"]
    require(len(entries) == len(prelude), "transfer_count")
    groups = {}
    for ordinal, (entry, row) in enumerate(zip(entries, prelude)):
        require(set(entry) == {"ordinal", "input_sha256", "m1_probabilities", "tokenlengths"}
                and entry["ordinal"] == row["ordinal"] == ordinal and entry["input_sha256"] == row["input_sha256"],
                "transfer_row_identity")
        packed = STAGED.float32_bytes(entry["m1_probabilities"])
        require(packed == STAGED.float32_bytes(row["result"]["m1_probabilities"])
                and entry["tokenlengths"] == {"m1": row["result"]["tokenlengths"]["m1"]}, "transfer_value_identity")
        STAGED.token_metadata(entry["tokenlengths"]["m1"])
        value = (packed, LOCAL.canonical(entry["tokenlengths"]))
        require(entry["input_sha256"] not in groups or groups[entry["input_sha256"]] == value, "transfer_duplicate_disagreement")
        groups[entry["input_sha256"]] = value
    fingerprint = sha(LOCAL.canonical({"base_fingerprint": transfer["base_fingerprint"], "strategy": STAGED.STRATEGY,
                                      "transfer_sha256": envelope["transfer_sha256"]}))
    return {"items": len(entries), "cache_entries": len(groups), "base_fingerprint": transfer["base_fingerprint"],
            "fingerprint": fingerprint, "transfer_sha256": envelope["transfer_sha256"]}


def check_ready(ready, transfer, mode="research"):
    close(ready, {"type": "ready", "fingerprint": transfer["fingerprint"], "base_fingerprint": transfer["base_fingerprint"],
                  "transfer_sha256": transfer["transfer_sha256"], "strategy": STAGED.STRATEGY,
                  "transfer_items": transfer["items"], "cache_entries": transfer["cache_entries"], "m1_instance_absent": True,
                  "modelstatus": {"m1": "receipt_replay_not_loaded", "m3": "not_loaded", "mode": mode},
                  "cache_scope": "job_m1_receipt_transfer", "audit_rate": 0}, "staged_ready", tolerance=0)


def check_progress(events, phase, rows, source_results):
    markers = [row for row in events if row.get("type") == "staged_progress" and row.get("phase_id") == phase["id"]]
    first_occurrence, seen = [], set()
    for ordinal, result in enumerate(source_results):
        if result["hypothetical_route"] and rows[ordinal]["input_sha256"] not in seen:
            first_occurrence.append(ordinal); seen.add(rows[ordinal]["input_sha256"])
    open_stage, closed, previous = None, Counter(), -1
    for marker in markers:
        ordinal, stage, kind = marker.get("ordinal"), marker.get("stage"), marker.get("kind")
        require(ordinal in first_occurrence and stage in {"m3_load", "m3_forward"} and kind in {"begin", "end"}, "progress_schema")
        index = first_occurrence.index(ordinal)
        if kind == "begin":
            require(open_stage is None and ordinal >= previous, "progress_overlap")
            if stage == "m3_load": require(index == 0 and not closed[stage], "m3_load_order")
            else: require(closed["m3_load"] == 1 and closed[stage] == index, "m3_forward_order")
            open_stage = (stage, ordinal)
        else:
            require(open_stage == (stage, ordinal), "progress_end_without_begin")
            closed[stage] += 1; open_stage = None
        previous = ordinal
        counters = marker.get("cumulative_counters")
        expected = {name: 0 for name in STAGED.COSTS}
        expected.update(m1_cache_hit=ordinal + 1, m3_attempts=index + 1, m3_succeeded=index)
        close(counters, expected, "progress_cost", tolerance=0)
        resources = marker.get("resources")
        require(isinstance(resources, dict) and all(type(resources.get(name)) is int and resources[name] >= 0
                for name in ("peak_rss_bytes", "mlx_peak_bytes")), "progress_resource")
    if phase["status"] == "completed":
        require(open_stage is None and closed["m3_load"] == (1 if first_occurrence else 0)
                and closed["m3_forward"] == len(first_occurrence), "complete_progress_coverage")
    return {"m3_unique_attempts": len(first_occurrence), "progress_events": len(markers),
            "m3_load_spans": closed["m3_load"], "m3_forward_spans": closed["m3_forward"],
            "unfinished_stage": list(open_stage) if open_stage else None}


def check_final_results(records, items, prelude, replay):
    count = len(records)
    require(len(items) == count and [row.get("ordinal") for row in items] == list(range(count)), "final_row_alignment")
    observed = [row for row in items if row.get("result") is not None]
    require([row["ordinal"] for row in observed] == list(range(len(observed))) and len(observed) <= len(replay), "final_result_prefix")
    require(not observed or len(prelude) == count, "final_before_complete_prelude")
    base = prelude[-1]["result"]["cumulative_counters"] if prelude else {name: 0 for name in STAGED.COSTS}
    for final, raw, record in zip(observed, replay, records):
        require(final["record"]["model_input_text"] == record["model_input_text"]
                and final["record"]["model_input_hash"] == record["model_input_hash"], "final_input_identity")
        actual, phase = final["result"], raw["result"]
        close(actual, {key: value for key, value in phase.items() if key not in {"counters", "cumulative_counters", "cache_hit"}},
              "stored_phase_result", tolerance=0)
        first = prelude[final["ordinal"]]["result"]
        expected = {name: phase["counters"][name] for name in STAGED.COSTS}
        cumulative = {name: phase["cumulative_counters"][name] for name in STAGED.COSTS}
        for name in ("m1_attempts", "m1_cache_hit"):
            expected[name] = first["counters"][name]; cumulative[name] = base[name]
        close(actual.get("counters"), expected, "stored_physical_row_cost", tolerance=0)
        close(actual.get("cumulative_counters"), cumulative, "stored_physical_cumulative", tolerance=0)
        close(actual.get("staged_raw_counters"), {name: phase["counters"][name] for name in STAGED.COSTS}, "stored_raw_cost", tolerance=0)
        require(actual.get("staged_counter_scope") == "physical_job_cumulative"
                and actual.get("staged_latency_scope") == "phase_response_only_m1_prepass_excluded"
                and actual.get("cache_hit") is bool(first["counters"]["m1_cache_hit"]
                    and (not phase["route_requested"] or phase["counters"]["m3_cache_hit"])), "stored_scope_or_cache")
    return {"acknowledged_items": len(observed), "missing_items": count-len(observed)}


def check_dashboard(job, physical, transfer_reuses, dashboard, *, complete):
    records = [row["record"] for row in job["items"]]
    results = [row.get("result") for row in job["items"]]
    count = len(records)
    progress = (job.get("progress") or {}).get("staged_execution")
    require(isinstance(progress, dict) or not complete, "staged_progress_missing")
    acknowledged = {name: sum(result["counters"][name] for result in results if result is not None) for name in STAGED.COSTS}
    if progress:
        reported = progress.get("cumulative_counters")
        require(all(type(reported.get(name)) is int and acknowledged[name] <= reported[name] <= physical[name]
                    for name in STAGED.COSTS), "staged_cost_range")
        require(type(progress.get("prelude_transfer_reuses")) is int and 0 <= progress["prelude_transfer_reuses"] <= transfer_reuses,
                "staged_transfer_range")
        if complete:
            close(reported, physical, "complete_physical_cost", tolerance=0)
            require(progress.get("strategy") == STAGED.STRATEGY and progress.get("stage") == "completed"
                    and progress.get("phase_completed_items") == progress.get("phase_total_items") == count
                    and progress.get("cost_complete") is True and progress.get("cost_scope") == "completed_job"
                    and progress.get("unacknowledged_attempts") == 0 and progress["prelude_transfer_reuses"] == transfer_reuses,
                    "complete_progress_contract")
    else:
        reported = acknowledged
    expected = B.recalculate_aggregate(records, results, "research", reported)
    if isinstance(job.get("dashboard"), dict):
        close(job["dashboard"], {key:value for key,value in expected.items() if key != "routing"}, "stored_dashboard")
        if "derived" in job["dashboard"]: SOURCE.check_derived(records, results, job["dashboard"]["derived"])
    require(isinstance(dashboard, dict) or not complete, "api_dashboard_missing")
    if dashboard:
        close(dashboard, expected, "api_dashboard")
        close(dashboard["routing"], {"cost_scope":"staged_job_cumulative" if complete else "staged_known_lower_bound",
                                     "cost_complete":complete,"prelude_transfer_reuses":progress.get("prelude_transfer_reuses",0) if progress else 0},
              "api_cost_scope", tolerance=0)
        SOURCE.check_derived(records, results, dashboard.get("derived"))
    return {"api_dashboard": "verified" if dashboard else "not_observed_partial", "count": count,
            "cost_complete": bool(complete), "derived_verified": bool(dashboard)}


def analyze_job(plan, run, job, phases, receipts, transfers, samples, events, runtime_events, service, dashboard, router):
    items = job["items"]
    records, results = [row["record"] for row in items], [row.get("result") for row in items]
    count = len(records)
    require(job.get("source") == "discourse" and job.get("mode") == "research" and job.get("total_items") == count
            and job.get("completed_items") == sum(result is not None for result in results), "job_identity_count")
    close(job.get("request"), {"source": "discourse", "mode": "research", "max_qwen_calls": 500,
                               "audit_rate": 0, "seed": 42, "query": QUERY}, "job_request", tolerance=0)
    if count:
        require(LOCAL.check_records(records) == job.get("snapshot_hash"), "snapshot_identity")
    complete = run["status"] == "Completed"
    if complete:
        require(job.get("state") == "completed" and 300 <= count <= 400 and all(result is not None for result in results), "complete_job")
        source = SOURCE.check_source(records, job["manifest"])
    else:
        source = SOURCE.check_source(records, job["manifest"]) if count >= 300 else {
            "records": count, "registered_count_met": False, "details_verified": False,
            "boundary": "Only the pre-seal count is retained for a rejected source; rejected raw records are not retained or promoted to a verified cohort."}
    phase_map = {phase["id"]: phase for phase in phases}
    m1_id, m3_id = job["id"] + ":m1", job["id"] + ":m3"
    require(set(phase_map) <= {m1_id, m3_id} and [phase["id"] for phase in phases] == [value for value in (m1_id, m3_id) if value in phase_map], "phase_order")
    receipt_map = {m1_id: [], m3_id: []}
    for row in receipts:
        require(row.get("logical_job_id") == job["id"] and row.get("phase_id") in receipt_map, "receipt_job_binding")
        receipt_map[row["phase_id"]].append(row)
    prelude, replay = receipt_map[m1_id], receipt_map[m3_id]
    for phase_id, rows in receipt_map.items():
        require([row["ordinal"] for row in rows] == list(range(len(rows))) and len(rows) <= count, "receipt_prefix")
        if phase_id in phase_map:
            require(phase_map[phase_id]["completed_items"] == len(rows), "phase_receipt_count")
    transfer = None
    if transfers:
        require(len(transfers) == 1 and m1_id in phase_map and phase_map[m1_id]["status"] == "completed", "transfer_phase_count")
        transfer = check_transfer(transfers[0], prelude, job["id"])
        require(transfer["base_fingerprint"] == router["base_fingerprint"], "transfer_base_fingerprint")
    summaries = []
    for phase_id, rows in ((m1_id, prelude), (m3_id, replay)):
        if phase_id not in phase_map:
            require(not rows, "receipt_without_phase")
            continue
        phase = phase_map[phase_id]; stage = phase["phase"]
        is_complete = phase["status"] == "completed"
        if is_complete: require(len(rows) == count and phase.get("normal_exit") is True, "partial_phase_complete")
        costs = STAGED.recompute_cost(records, rows, mode="m1_only" if stage == "m1" else "research",
                                      budget=0 if stage == "m1" else 500, phase=stage, complete=is_complete)
        functional = STAGED.functional_comparison(records, rows, router, mode="m1_only" if stage == "m1" else "research",
                                                   budget=0 if stage == "m1" else 500, phase=stage,
                                                   source_results=[row["result"] for row in prelude] if prelude else [],
                                                   prelude=prelude if stage == "m3" else None)
        own_events = [event for event in events if event.get("phase_id") == phase_id]
        violations = STAGED.receipt_safety(rows, own_events, service, run)
        summary = {"id": phase_id, "phase": stage, "completed": is_complete, "cost": costs,
                   "functional": functional, "receipt_resource_violations": violations}
        if stage == "m3":
            require(transfer is not None, "m3_without_transfer")
            ready = [event for event in own_events if event["type"] == "ready"]
            require(not rows or len(ready) == 1, "m3_ready_count")
            if ready: check_ready(ready[0].get("ready"), transfer)
            summary["progress"] = check_progress(runtime_events, phase, rows, [row["result"] for row in prelude])
        else:
            require(all(row["result"]["fingerprint"] == router["base_fingerprint"] for row in rows), "m1_base_fingerprint")
            ready = [event for event in own_events if event["type"] == "ready"]
            require(not rows or len(ready) == 1, "m1_ready_count")
            if ready:
                close(ready[0].get("ready"), {"type": "ready", "fingerprint": router["base_fingerprint"],
                      "modelstatus": {"m1": "loaded", "m3": "not_loaded", "mode": "m1_only"},
                      "cache_scope": "job_exact_input_components", "audit_rate": 0}, "m1_ready", tolerance=0)
        summaries.append(summary)
    phase_complete = len(summaries) == 2 and all(row["completed"] for row in summaries)
    final = check_final_results(records, items, prelude, replay)
    physical = {name: 0 for name in STAGED.COSTS}
    if prelude:
        physical.update(prelude[-1]["result"]["cumulative_counters"])
    if replay:
        for name in STAGED.COSTS:
            if name not in {"m1_attempts", "m1_cache_hit"}: physical[name] = replay[-1]["result"]["cumulative_counters"][name]
    transfer_reuses = replay[-1]["result"]["cumulative_counters"]["m1_cache_hit"] if replay else 0
    dashboard_check = check_dashboard(job, physical, transfer_reuses, dashboard, complete=phase_complete)
    return {"records": count, "source": source, "snapshot_sha256": job.get("snapshot_hash"), "final": final,
            "phases": summaries, "transfer": transfer, "physical_counters": physical,
            "dashboard": dashboard_check, "phase_complete": phase_complete,
            "historical_m3_reference": {"ordinal6_reference_preserved": True, "applicable": False,
                "reason": "EXP-082/084 ordinal 6 belongs to the Stack Overflow snapshot and is not an input reference for Discourse."}}


def check_source_progress(rows, logical_job_id, run, runtime_events, process_events):
    require(isinstance(rows, list) and rows, "source_progress_missing")
    previous = None
    for row in rows:
        require(isinstance(row, dict) and row.get("logical_job_id") == logical_job_id
                and type(row.get("monotonic")) in (int, float), "source_progress_schema")
        require(previous is None or row["monotonic"] >= previous, "source_progress_order")
        previous = row["monotonic"]
        if "record_count" in row:
            require(type(row["record_count"]) is int and row["record_count"] >= 0, "source_progress_record_count")
        encoded = LOCAL.canonical(row)
        require(len(encoded.encode()) <= 65536 and not any(value in encoded.lower() for value in
                ('"raw"', 'model_input_text', 'author_display_name', 'access_token', 'cookie')), "source_progress_privacy")
    gates = [row for row in rows if row.get("stage") == "source_count_gate"]
    if not gates:
        require(run["status"] == "Stopped" and any(row.get("stage") == "source_error" and row.get("status") == "failed" for row in rows)
                and not any(row.get("type") == "phase_started" for row in runtime_events)
                and not any(row.get("type") == "constructor_started" for row in process_events), "source_count_gate")
        result = {"status": "source_error_before_count", "record_count": max((row.get("record_count", 0) for row in rows), default=0),
                  "rejected_before_model": True}
    else:
        require(len(gates) == 1, "source_count_gate")
        gate = gates[0]
        require(gate.get("status") in {"accepted", "rejected_before_model"}, "source_count_gate_status")
        phase_starts = [row for row in runtime_events if row.get("type") == "phase_started"]
        constructors = [row for row in process_events if row.get("type") == "constructor_started"]
        if gate["status"] == "accepted":
            require(300 <= gate["record_count"] <= 400
                    and all(gate["monotonic"] <= row["started_monotonic"] for row in phase_starts), "accepted_source_gate")
        else:
            source_failed = any(row.get("stage") == "source_error" and row.get("status") == "failed" for row in rows)
            require((not 300 <= gate["record_count"] <= 400 or source_failed) and not phase_starts and not constructors
                    and run["status"] == "Stopped", "rejected_source_started_model")
        result = {"status": gate["status"], "record_count": gate["record_count"],
                  "rejected_before_model": gate["status"] == "rejected_before_model"}
    attempted = sum(row.get("source_stage") == "request_started" for row in rows)
    responses = sum(row.get("source_stage") == "response_received" for row in rows)
    require(run.get("source_network_authorized") is True
            and run.get("source_network_attempted") is bool(attempted)
            and run.get("source_network_fetched") is bool(responses)
            and run.get("source_response_count") == responses, "source_network_terminal_binding")
    if run["status"] == "Completed":
        require(attempted > 0 and responses > 0, "complete_without_source_response")
    result.update(request_started_count=attempted, response_received_count=responses)
    return result


def check_plan_contract(plan):
    close(plan, {"experiment_id": "EXP-086", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", "query": QUERY,
                 "mode": "research", "max_qwen_calls": 500, "audit_rate": 0, "seed": 42,
                 "planned_jobs": 1, "planned_records_min": 300, "planned_records_max": 400,
                 "max_seconds": 3600, "work_seconds": 3570, "cleanup_seconds": 15, "port": 8790,
                 "runtime_environment": {"TOPICWEB_TELEMETRY": "1"},
                 "scope": "source_and_local_system_closure_without_external_gold"}, "plan_contract", tolerance=0)
    return True


def analyze(plan, run, service, jobs, receipts, transfers, samples, events, runtime_events, source_progress, dashboards, router):
    check_plan_contract(plan)
    close(run, {"experiment_id": "EXP-086", "attempt": 1, "tier": "Minor", "planned_jobs": 1,
                "training": False, "gold_accessed": False, "source_network_authorized": True}, "run_contract", tolerance=0)
    require(run.get("status") in {"Completed", "Stopped"} and type(run.get("started_monotonic")) in (int, float)
            and type(run.get("ended_monotonic")) in (int, float)
            and run["started_monotonic"] <= run["ended_monotonic"], "run_clock")
    close(run.get("elapsed_seconds"), run["ended_monotonic"] - run["started_monotonic"], "run_elapsed")
    require(run.get("total_budget_exceeded") is (run["elapsed_seconds"] > 3600), "run_budget")
    logical, phases = run.get("logical_jobs"), run.get("phases")
    require(isinstance(logical, list) and len(logical) <= 1 and isinstance(phases, list) and len(phases) <= 2, "run_scope")
    if run["status"] == "Completed":
        require(run.get("failure_code") is None and len(logical) == 1, "false_run_completion")
    else:
        require(isinstance(run.get("failure_code"), str) and bool(run["failure_code"]), "stopped_without_reason")
    identifiers = {entry.get("id") for entry in logical if isinstance(entry.get("id"), str)}
    require(set(jobs) == identifiers and len(identifiers) == len(logical), "bench_job_binding")
    if not logical:
        require(run["status"] == "Stopped" and not jobs and not receipts and not transfers and not phases, "empty_stopped_scope")
        return {"exp086_complete": False, "source": {"status": "not_observed"}, "jobs": [],
                "safety": {"gate_passed": False, "observation_state": "pre_submission_stop"}, "operational_state": "stop-required"}
    entry, identifier = logical[0], next(iter(identifiers))
    require(entry.get("mode") == "research" and entry.get("budget") == 500, "logical_job_contract")
    source_gate = check_source_progress(source_progress, identifier, run, runtime_events, events)
    for event in events:
        require(event.get("logical_job_id") == identifier and event.get("phase_id") == event.get("job_id"), "process_event_job")
    require(all(run["started_monotonic"] <= row["started_monotonic"] <= row["monotonic"] <= run["ended_monotonic"] for row in samples)
            and all(run["started_monotonic"] <= row["monotonic"] <= run["ended_monotonic"] for row in events), "observation_clock")
    safety = B.verify_safety(samples, events, service, phases, elapsed_seconds=run["elapsed_seconds"], limit_seconds=3600)
    for phase in phases:
        terminals = [row for row in runtime_events if row.get("type") == "phase_terminal" and row.get("phase_id") == phase["id"]]
        require(len(terminals) == 1, "phase_terminal_count")
        for field in ("id", "phase", "mode", "status", "total_items", "completed_items", "started_monotonic", "ended_monotonic",
                      "readiness_started_monotonic", "readiness_ended_monotonic", "readiness_indices", "normal_exit", "cost_complete"):
            close(phase.get(field), terminals[0].get(field), "phase_terminal_binding", tolerance=0)
    result = analyze_job(plan, run, jobs[identifier], phases, receipts, transfers, samples, events, runtime_events,
                         service, dashboards.get(identifier), router)
    complete = (run["status"] == "Completed" and entry.get("status") == "completed"
                and result["phase_complete"] and result["source"].get("registered_count_met", True)
                and 300 <= result["records"] <= 400 and safety["gate_passed"])
    require(not complete or result["source"].get("records") == result["records"] == entry.get("completed_items"), "complete_count_binding")
    return {"exp086_complete": bool(complete), "source_gate": source_gate, "jobs": [result], "safety": safety,
            "operational_state": "safe-to-continue" if complete else "stop-required",
            "claim_boundary": SOURCE.BOUNDARY + " EXP-086 verifies one staged Discourse chain without gold labels, F1, SLA or population-level claims."}


ADDITIONAL_SOURCES = {"scripts/run_staged_discourse_formal.py", "scripts/verify_staged_discourse_formal.py",
                      "tests/test_staged_discourse_formal.py", "tests/test_verify_staged_discourse_formal.py"}


def jsonl(path):
    raw = path.read_bytes()
    require(not raw or raw.endswith(b"\n"), "incomplete_jsonl")
    return [LOCAL.strict_json(line) for line in raw.splitlines()]


def check_bindings(plan, run, claim, service):
    close(claim, {"experiment_id": "EXP-086", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", "cwd": str(ROOT),
                  "training": False, "gold_accessed": False, "source_network_authorized": True,
                  "source_network_fetched": False}, "claim_contract", tolerance=0)
    require(all(run.get(name) == claim.get(name) for name in ("started_at", "started_monotonic", "plan_sha256")), "claim_run_binding")
    require(run.get("plan_sha256") == B.regular_file(RUN / "plan.json"), "plan_hash_binding")
    parent, parent_plan = check_parent(plan)
    sources = plan.get("sources")
    require(isinstance(sources, dict) and set(sources) == set(parent_plan["sources"]) | ADDITIONAL_SOURCES
            and all(sources.get(name) == value for name, value in parent_plan["sources"].items()), "source_dependency_set")
    for name, expected in sources.items():
        require(B.regular_file(B.source_path(name, ROOT)) == expected, "implementation_identity")
    require(plan.get("protocol", {}).get("path") == PROTOCOL
            and B.regular_file(B.source_path(PROTOCOL, ROOT.parent)) == plan["protocol"].get("sha256"), "protocol_binding")
    review = plan.get("source_review")
    require(review == {"path": "docs/discourse-source-review.md", "sha256": B.regular_file(ROOT / "docs/discourse-source-review.md")},
            "source_review_binding")
    require(plan.get("model_config") == parent_plan.get("model_config")
            and plan.get("router_assets") == parent_plan.get("router_assets"), "model_router_parent_binding")
    require(plan.get("runtime_environment") == claim.get("runtime_environment") == {"TOPICWEB_TELEMETRY": "1"}, "telemetry_binding")
    close(service, {"experiment_id": "EXP-086", "attempt": 1, "root": str(ROOT), "bench_root": str(RUN / "bench"), "port": 8790},
          "service_scope", tolerance=0)
    require(B.service_absent(service), "service_still_running")
    shutdown = run.get("shutdown")
    require(isinstance(shutdown, dict) and all(shutdown.get(name) is True for name in
            ("server_stopped", "dispatcher_stopped", "monitor_stopped", "dispatcher_lock_released", "current_process_absent", "fresh_absence_confirmed")),
            "shutdown_unconfirmed")
    env = claim.get("environment")
    require(isinstance(env, dict) and env.get("model_config") == plan["model_config"], "environment_binding")
    return parent


def main():
    target = RUN / "verification.json"
    require(not target.exists() and not any(path.is_symlink() for path in (target, *target.parents)), "verification_exists_or_symlink")
    report = {"experiment_id": "EXP-086", "attempt": 1, "tier": "Minor", "status": "Failed", "exp086_complete": False,
              "operational_state": "stop-required", "models_loaded": False, "gold_accessed": False,
              "accuracy_computed": False, "f1_computed": False, "producer_numerical_helpers_imported": False,
              "verified_at": datetime.now(timezone.utc).isoformat(), "verifier_sha256": B.regular_file(Path(__file__))}
    try:
        plan, run, claim, service = (LOCAL.strict_json((RUN / name).read_text()) for name in ("plan.json", "run.json", "run-claim.json", "service.json"))
        before = dict(run.get("source_hashes", {}))
        fixed = {str((RUN / name).relative_to(ROOT)) for name in (*JOURNALS.values(), "source-progress.jsonl", "stdout.log",
                                                                  "service.json", "plan.json", "run-claim.json")}
        database_name = str((RUN / "bench/jobs.sqlite3").relative_to(ROOT))
        require(run.get("bench_database") == database_name, "bench_database_binding")
        fixed.add(database_name)
        logical = run.get("logical_jobs", [])
        dashboards = {}
        for entry in logical:
            identifier = entry.get("id")
            require(isinstance(identifier, str) and re.fullmatch(r"[a-f0-9]{32}", identifier), "job_identity")
            if entry.get("results_path"):
                require(entry["results_path"] == str((RUN / "results.json").relative_to(ROOT)), "results_path")
                fixed.add(entry["results_path"])
            if entry.get("dashboard_path"):
                require(entry["dashboard_path"] == str((RUN / "dashboard.json").relative_to(ROOT)), "dashboard_path")
                fixed.add(entry["dashboard_path"])
        require(set(before) == fixed, "artifact_set")
        for name, expected in before.items():
            path = B.source_path(name, ROOT)
            require(path.is_relative_to(RUN) and B.regular_file(path) == expected and path.stat().st_mode & 0o777 == 0o600,
                    "artifact_identity_or_mode")
        run_hash = B.regular_file(RUN / "run.json")
        parent = check_bindings(plan, run, claim, service)
        router = STAGED.load_router(plan)
        database = ROOT / database_name
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            identifiers = {row[0] for row in connection.execute("SELECT id FROM jobs")}
        require(identifiers == {entry["id"] for entry in logical}, "unbound_bench_job")
        jobs = {identifier: SOURCE.read_selected_job(database, identifier) for identifier in identifiers}
        for entry in logical:
            if entry.get("results_path"):
                artifact = LOCAL.strict_json((ROOT / entry["results_path"]).read_text())
                job = jobs[entry["id"]]
                expected = {"id": entry["id"], "snapshot_hash": job["snapshot_hash"], "items": [
                    {"ordinal": row["ordinal"], "input_sha256": row["record"]["model_input_hash"], "result": row["result"]} for row in job["items"]]}
                require(artifact == expected, "database_result_artifact")
            if entry.get("dashboard_path"):
                dashboards[entry["id"]] = LOCAL.strict_json((ROOT / entry["dashboard_path"]).read_text())
        journals = {kind: jsonl(RUN / name) for kind, name in JOURNALS.items()}
        source_progress = jsonl(RUN / "source-progress.jsonl")
        require(run.get("journal_counts") == {kind: len(rows) for kind, rows in journals.items()}
                and run.get("source_progress_count") == len(source_progress), "journal_count_binding")
        report.update(analyze(plan, run, service, jobs, journals["phase_receipt"], journals["transfer"], journals["sample"],
                              journals["process_event"], journals["runtime_event"], source_progress, dashboards, router))
        require(B.regular_file(RUN / "run.json") == run_hash
                and all(B.regular_file(ROOT / name) == expected for name, expected in before.items()), "artifact_changed_during_audit")
        require(all(B.regular_file(ROOT / name) == expected for name, expected in plan["sources"].items()), "implementation_changed_during_audit")
        report.update(status="Passed", parent_exp085=parent,
                      source_hashes={**before, str((RUN / "run.json").relative_to(ROOT)): run_hash})
    except Exception as error:
        code = str(error) if isinstance(error, (B.VerificationError, LOCAL.VerificationError, SOURCE.LOCAL.VerificationError)) else type(error).__name__
        report.update(status="Failed", exp086_complete=False, operational_state="stop-required",
                      error_code=code if re.fullmatch(r"[A-Za-z0-9_]{1,100}", code) else "verification_failed")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")
        output.flush(); os.fsync(output.fileno())
    print(json.dumps({name: report.get(name) for name in ("status", "exp086_complete", "operational_state", "error_code")}))
    return 0 if report["status"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
