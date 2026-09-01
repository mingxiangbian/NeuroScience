"""EXP-084 independent receipt-transfer, accounting, equivalence and safety audit."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import struct
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT/"private/validation/exp-084/attempt-1"
SPEC = importlib.util.spec_from_file_location("exp084_independent_helpers", ROOT/"scripts/verify_preload_diagnostic.py")
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)
B, M3, LOCAL = D.B, D.M3, D.LOCAL
require, close, sha, finite = B.require, B.close, B.sha, B.finite
regular_file, read_lines = B.regular_file, M3.read_lines
SOURCE_JOB, SOURCE_SNAPSHOT, SOURCE_LOGICAL = D.SOURCE_JOB, D.SOURCE_SNAPSHOT, D.SOURCE_LOGICAL
SOURCE_PLAN_HASH = D.SOURCE_PLAN_HASH
STRATEGY = "m1-receipt-transfer-v1"
PARENT_HASHES = {
    "plan": "daf611f054a0f870491651798b2f7bd24fbfb30181c41ea88776df14f18fe559",
    "run": "1b566d0007ae3bbb6bcfa194472c77ab50ab27cd6ebebec4f0373826f488e417",
    "verification": "7276798a09f641f36ba9017af8768cc786c39e4564cd1a5974a3bd7880363a09",
}
REFERENCE_HASHES = {
    "plan": "896067922d9029e35ccdf1eeb44976bb22fc96a71ce0791424861d16547a5298",
    "run": "10125ffc1c22bd020dc75f2c05647464be22ea90f8d509b7e3f7e78eb9d4e952",
    "verification": "0d98fef8a5662bace2299bd7f11f9d17c99f13b14dca4a7c3765f4fe2ea3deb6",
    "results": "0f5e4ad8ece779ddea8d8b9148ebc414a2b3363a809242d4190e3458a597165d",
}
PHASES = (
    {"phase": "m1_prelude", "job_id": "exp084-m1-prelude", "mode": "m1_only", "planned_events": 340, "max_qwen_calls": 0},
    {"phase": "research_prefix", "job_id": "exp084-m3-replay", "mode": "research", "planned_events": 7, "max_qwen_calls": 1},
)
ADDITIONAL_SOURCES = {
    "scripts/run_transfer_diagnostic.py", "scripts/transferred_m3_child.py", "scripts/verify_transfer_diagnostic.py",
    "tests/test_transfer_diagnostic.py", "tests/test_transferred_m3_child.py", "tests/test_verify_transfer_diagnostic.py",
}
PROTOCOL = "experiments/stack-overflow-emotion-gold/protocols/exp-084-m1-transfer-memory-prototype.md"
ARTIFACTS = ("service.json", "plan.json", "run-claim.json", "m1-results.jsonl", "replay-results.jsonl",
             "samples.jsonl", "process-events.jsonl", "stages.jsonl", "stdout.log", "run.json")
OPTIONAL_ARTIFACTS = ("transfer.json", "m3-ready.json")
FUNCTIONAL_FIELDS = (
    "prediction", "prediction6", "active_labels", "labels", "neutral", "used_path", "actual_model",
    "route_requested", "route_eligible", "routed", "hypothetical_route", "fallback", "fallback_reason", "degraded",
    "m1_prediction", "m3_prediction", "tokenlengths", "truncflags",
)
NUMERIC_FIELDS = ("m1_probabilities", "m3_probabilities", "route_score", "m1_entropy", "threshold_margin")


def path_for(name, root=None):
    return B.source_path(name, ROOT if root is None else root)


def read_source(database):
    require(database.is_file() and not any(p.is_symlink() for p in (database,*database.parents)), "source_database_identity")
    with sqlite3.connect(database.as_uri()+"?mode=ro", uri=True, timeout=1) as db:
        metadata = db.execute("SELECT state,snapshot_hash,total_items FROM jobs WHERE id=?", (SOURCE_JOB,)).fetchone()
        rows = db.execute("SELECT ordinal,record,result FROM items WHERE job_id=? ORDER BY ordinal", (SOURCE_JOB,)).fetchall()
    require(metadata == ("completed",SOURCE_SNAPSHOT,340), "source_job_identity")
    return [{"ordinal": ordinal, "record": LOCAL.strict_json(record), "result": LOCAL.strict_json(result)} for ordinal,record,result in rows]


def validate_plan(plan, source):
    close(plan, {"experiment_id": "EXP-084", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", "strategy": STRATEGY,
                 "planned_jobs": 2, "planned_events": 347, "phase_order": [p["phase"] for p in PHASES], "phases": list(PHASES),
                 "max_seconds": 180, "work_seconds": 150, "cleanup_seconds": 15, "max_readiness_seconds": 60,
                 "audit_rate": 0, "seed": 42, "source_job": SOURCE_JOB, "source_snapshot_sha256": SOURCE_SNAPSHOT,
                 "source_database": "private/jobs.sqlite3", "source_logical_sha256": SOURCE_LOGICAL}, "plan_contract")
    metadata = B.validate_source_rows(source)
    require(plan.get("source_rows") == metadata and plan.get("prefix_rows") == metadata[:7]
            and [row["route_eligible"] for row in metadata[:7]] == [False]*6+[True], "source_mapping")
    require(sha(LOCAL.canonical(source)) == SOURCE_LOGICAL, "source_logical_identity")


def float32_bytes(values):
    values = LOCAL.probabilities(values)
    packed = struct.pack("<6f", *values)
    require(list(struct.unpack("<6f", packed)) == values, "lossy_float32_transfer")
    return packed


def check_transfer(transfer, prelude, jobs, exits, results_hash):
    if transfer is None:
        return None
    require(isinstance(transfer, dict) and set(transfer) == {"experiment_id", "attempt", "source_job_id", "source_phase",
            "source_results_path", "source_results_sha256", "source_results_count", "fingerprint", "entries"}, "transfer_schema")
    close(transfer, {"experiment_id": "EXP-084", "attempt": 1, "source_job_id": PHASES[0]["job_id"],
                    "source_phase": "m1_prelude", "source_results_path": "private/validation/exp-084/attempt-1/m1-results.jsonl",
                    "source_results_sha256": results_hash, "source_results_count": 340}, "transfer_source_binding")
    require(len(prelude) == 340 and jobs and jobs[0]["status"] == "completed"
            and exits[0]["normal_exit"] and exits[0]["absence_observed"], "transfer_before_complete_prelude")
    fingerprint = transfer.get("fingerprint")
    require(isinstance(fingerprint,str) and re.fullmatch(r"[a-f0-9]{64}",fingerprint)
            and all(row["result"].get("fingerprint") == fingerprint for row in prelude), "transfer_base_fingerprint")
    entries = transfer.get("entries")
    require(isinstance(entries,list) and len(entries) == 7 and [entry.get("ordinal") for entry in entries] == list(range(7)), "transfer_prefix_count")
    hashes = set()
    for entry,row in zip(entries,prelude[:7]):
        require(set(entry) == {"ordinal","input_sha256","m1_probabilities","tokenlengths","source_result_sha256"}, "transfer_entry_schema")
        require(entry["input_sha256"] == row["input_sha256"] and entry["input_sha256"] not in hashes
                and entry["source_result_sha256"] == sha(LOCAL.canonical(row)), "transfer_current_row_provenance")
        hashes.add(entry["input_sha256"])
        require(float32_bytes(entry["m1_probabilities"]) == float32_bytes(row["result"]["m1_probabilities"]), "transfer_probability_identity")
        require(entry["tokenlengths"] == {"m1":row["result"]["tokenlengths"]["m1"]}, "transfer_token_identity")
        metadata = entry["tokenlengths"]["m1"]
        require(set(metadata) == {"input_tokens","used_tokens","truncated"}
                and type(metadata["input_tokens"]) is int and type(metadata["used_tokens"]) is int
                and 1 <= metadata["used_tokens"] <= 256 and metadata["used_tokens"] == min(metadata["input_tokens"],256)
                and type(metadata["truncated"]) is bool and metadata["truncated"] == (metadata["input_tokens"] > metadata["used_tokens"]), "transfer_token_contract")
    return fingerprint


def check_ready(proof, transfer, transfer_hash, events, run):
    if proof is None:
        return {"available": False, "ready_acknowledged": False, "fingerprint": None}
    require(isinstance(proof,dict) and transfer is not None, "ready_without_transfer")
    fingerprint = sha(LOCAL.canonical({"base_fingerprint":transfer["fingerprint"],"strategy":STRATEGY,"transfer_sha256":transfer_hash}))
    close(proof, {"experiment_id":"EXP-084", "transfer_sha256":transfer_hash, "cache_entries":7,
                  "cache_input_sha256s":[row["input_sha256"] for row in transfer["entries"]],
                  "m1_instance_absent":True, "m1_backend_calls":0, "fingerprint":fingerprint,
                  "base_fingerprint":transfer["fingerprint"], "strategy":STRATEGY,
                  "modelstatus":{"m1":"receipt_replay_not_loaded","m3":"not_loaded","mode":"research"}}, "ready_absence_contract")
    require(type(proof.get("cache_entries")) is int and type(proof.get("m1_backend_calls")) is int,"ready_counter_types")
    known = {event["pid"] for event in events if event.get("pid") is not None}
    require(type(proof.get("pid")) is int and proof["pid"] in known and finite(proof.get("monotonic")), "ready_process_identity")
    starts = [event for event in events if event["type"] == "constructor_started"]
    ready = [event for event in events if event["type"] == "ready"]
    exits = [event for event in events if event["type"] == "process_exit"]
    require(len(starts) == 1 and starts[0]["monotonic"] <= proof["monotonic"] <= (exits[-1]["monotonic"] if exits else run["ended_monotonic"]), "ready_proof_clock")
    if ready:
        require(proof["pid"] == ready[0]["pid"] and proof["monotonic"] <= ready[0]["monotonic"], "ready_ack_clock")
    return {"available":True,"ready_acknowledged":bool(ready),"fingerprint":fingerprint,"m1_instance_absent":True,
            "m1_backend_calls":0,"observed_monotonic":proof["monotonic"],"scope":"ready_time_before_predictions"}


def replay_receipts(rows, prelude, transfer, ready_info, reference, events, service, run):
    require(len(rows) <= 7 and [row.get("ordinal") for row in rows] == list(range(len(rows)))
            and all(row.get("phase") == "research_prefix" for row in rows), "replay_prefix")
    if rows:
        require(transfer is not None and ready_info["available"] and ready_info["ready_acknowledged"], "replay_without_ready_proof")
    costs = {name:0 for name in B.COSTS}
    difference, violations = None, 0
    ready = [event for event in events if event["type"] == "ready"]
    exits = [event for event in events if event["type"] == "process_exit"]
    for row in rows:
        i,result = row["ordinal"],row["result"]
        original,entry,old = prelude[i]["result"],transfer["entries"][i],reference[i]["result"]
        require(row["input_sha256"] == entry["input_sha256"] == reference[i]["input_sha256"], "replay_input_identity")
        require(float32_bytes(result.get("m1_probabilities")) == float32_bytes(entry["m1_probabilities"])
                == float32_bytes(original["m1_probabilities"]), "replay_same_run_probability")
        require(result.get("tokenlengths",{}).get("m1") == original["tokenlengths"]["m1"]
                and result.get("m1_prediction") == original["m1_prediction"]
                and result.get("hypothetical_route") is original["hypothetical_route"], "replay_same_run_metadata")
        for field in ("route_score","m1_entropy","threshold_margin"):
            close(result.get(field),original.get(field),"replay_same_run_features",tolerance=0)
        require(result.get("prelude_transfer_reuse") is True and result.get("m1_execution_origin") == "current_run_m1_prelude_receipt"
                and result.get("fingerprint") == ready_info["fingerprint"], "replay_execution_origin")
        for field in FUNCTIONAL_FIELDS:
            require(field in old and field in result,"functional_field_missing")
            close(result[field],old[field],"exp082_functional_equivalence",tolerance=0)
        for field in NUMERIC_FIELDS:
            require(field in old and field in result,"numeric_field_missing")
            close(result[field],old[field],"exp082_numeric_equivalence",tolerance=1e-6)
        for field in ("m1_probabilities","m3_probabilities"):
            if result[field] is not None:
                delta=max(abs(a-b) for a,b in zip(LOCAL.probabilities(result[field]),LOCAL.probabilities(old[field])))
                difference=delta if difference is None else max(difference,delta)
        routed=i==6
        require(result["route_requested"] is routed and result["fallback"] is False
                and result["fallback_reason"] is None and result["used_path"] == ("m3" if routed else "m1"), "replay_route_contract")
        expected={name:0 for name in costs}
        expected.update(m1_cache_hit=1,m3_attempts=int(routed),m3_succeeded=int(routed))
        close(result.get("counters"),expected,"replay_raw_counters")
        costs={name:costs[name]+expected[name] for name in costs}
        close(result.get("cumulative_counters"),costs,"replay_cumulative_counters")
        require(all(type(result[field].get(name)) is int for field in ("counters","cumulative_counters") for name in costs), "counter_types")
        child_rss,parent_rss=B.result_rss(result.get("telemetry"))
        telemetry=result["telemetry"]
        require(telemetry["parent_pid"] == service["pid"] and len(ready)==1 and telemetry["child_pid"]==ready[0]["pid"]
                and finite(telemetry.get("monotonic")) and ready[0]["monotonic"] <= telemetry["monotonic"] <= (exits[-1]["monotonic"] if exits else run["ended_monotonic"]), "replay_receipt_identity")
        resource=result.get("resources")
        require(isinstance(resource,dict) and all(type(resource.get(key)) is int and resource[key]>=0 for key in ("peak_rss_bytes","mlx_peak_bytes")), "replay_resource_schema")
        violations += child_rss>12*1024**3 or parent_rss>1024**3 or resource["peak_rss_bytes"]>12*1024**3 or resource["mlx_peak_bytes"]>10_000_000_000
    return {"phase":"research_prefix","planned_events":7,"verified_acknowledged_events":len(rows),
            "missing_acknowledged_events":7-len(rows),"raw_jobinfer_counters":costs,
            "execution_accounting":{"actual_m1_forward_attempts":0,"within_phase_duplicate_cache_hits":0,
                                    "prelude_transfer_reuse":len(rows),"m3_attempts":costs["m3_attempts"],"m3_succeeded":costs["m3_succeeded"]},
            "exp082_probability_max_abs_difference":difference,"receipt_resource_violations":violations}


def sequence_safety(run, phases, samples, events, service):
    jobs,attempts=run.get("jobs"),run.get("readiness_attempts")
    require(isinstance(jobs,list) and len(jobs)<=2 and isinstance(attempts,list)
            and len(jobs)<=len(attempts)<=min(2,len(jobs)+1),"phase_attempt_count")
    for index,attempt in enumerate(attempts):
        require(attempt.get("phase")==PHASES[index]["phase"] and attempt.get("status") in {"Ready","NotReady"}
                and finite(attempt.get("started_monotonic")) and finite(attempt.get("ended_monotonic"))
                and run["started_monotonic"]<=attempt["started_monotonic"]<=attempt["ended_monotonic"]<=run["ended_monotonic"],"readiness_contract")
        require(isinstance(attempt.get("indices"),list) and all(type(i) is int and 0<=i<len(samples) for i in attempt["indices"]),"readiness_indices")
        if index<len(jobs):
            job,phase=jobs[index],PHASES[index]
            require(job.get("id")==phase["job_id"] and job.get("phase")==phase["phase"] and job.get("mode")==phase["mode"]
                    and job.get("status") in {"completed","cancelled","failed"} and job.get("total_items")==phase["planned_events"]
                    and job.get("completed_items")==len(phases[index]),"phase_job_contract")
            require(attempt["status"]=="Ready" and attempt["indices"]==job.get("readiness_indices")
                    and attempt["started_monotonic"]==job.get("readiness_started_monotonic")
                    and attempt["ended_monotonic"]==job.get("readiness_ended_monotonic"),"readiness_job_binding")
            require(finite(job.get("started_monotonic")) and finite(job.get("ended_monotonic"))
                    and attempt["ended_monotonic"]<=job["started_monotonic"]<=job["ended_monotonic"]<=run["ended_monotonic"],"job_clock")
            if job["status"]=="completed":
                require(job["completed_items"]==phase["planned_events"] and job.get("normal_exit") is True,"partial_job_called_complete")
        if index:
            require(jobs and jobs[0]["status"]=="completed" and jobs[0]["ended_monotonic"]<=attempt["started_monotonic"],"replay_after_failed_prelude")
    require(all(not rows or index<len(jobs) for index,rows in enumerate(phases)),"receipts_without_job")
    safety=B.verify_safety(samples,events,service,jobs,elapsed_seconds=run["elapsed_seconds"],limit_seconds=180)
    if len(jobs)==2:
        cutoff=attempts[1]["started_monotonic"]
        prior=B.verify_safety([s for s in samples if s["monotonic"]<=cutoff],
                             [e for e in events if e["job_id"]==PHASES[0]["job_id"]],service,jobs[:1],
                             elapsed_seconds=cutoff-run["started_monotonic"],limit_seconds=180)
        require(prior["gate_passed"],"replay_submitted_after_unsafe_prelude")
    require(run.get("cleanups")==[job["cleanup"] for job in jobs if job.get("cleanup") is not None],"cleanup_binding")
    exit_summary=[]
    for job in jobs:
        cleanup=job.get("cleanup")
        if cleanup:
            require(cleanup.get("job_id")==job["id"] and cleanup.get("phase")==job["phase"]
                    and cleanup["started_monotonic"]<=cleanup["ended_monotonic"]<=job["ended_monotonic"],"cleanup_clock")
        owned=[event for event in events if event["job_id"]==job["id"]]
        exits=[event for event in owned if event["type"]=="process_exit"]
        require(all(type(event.get("returncode")) is int for event in exits),"actual_exit_returncode")
        exit_summary.append({"id":job["id"],"phase":job["phase"],"child_launched":any(e.get("pid") is not None for e in owned),
                             "returncode":exits[-1]["returncode"] if exits else None})
    require(run.get("child_exit_summary")==exit_summary,"child_exit_summary_binding")
    safety["readiness_attempt_gate"]=bool(attempts) and len(attempts)==len(jobs) and all(a["status"]=="Ready" and a["ended_monotonic"]-a["started_monotonic"]<=60+1e-6 for a in attempts)
    return safety


def analyze(plan,run,source,reference,prelude,replay,samples,events,service,stage_bytes,transfer,proof,prelude_hash,transfer_hash):
    validate_plan(plan,source)
    close(run,{"experiment_id":"EXP-084","attempt":1,"tier":"Minor","rq":"RQ-S3","planned_jobs":2,"planned_events":347,
               "training":False,"gold_accessed":False,"source_network_fetched":False,"operational_followup_authorized":False},"run_contract")
    require(run.get("status") in {"Completed","Stopped","Failed"} and finite(run.get("started_monotonic")) and finite(run.get("ended_monotonic"))
            and run["started_monotonic"]<=run["ended_monotonic"],"run_clock")
    close(run.get("elapsed_seconds"),run["ended_monotonic"]-run["started_monotonic"],"run_elapsed")
    require(run.get("total_budget_exceeded") is (run["elapsed_seconds"]>180),"total_budget_flag")
    require(all(run["started_monotonic"]<=s["started_monotonic"]<=s["monotonic"]<=run["ended_monotonic"] for s in samples)
            and all(run["started_monotonic"]<=e["monotonic"]<=run["ended_monotonic"] for e in events),"run_observation_window")
    require(len(reference)==7 and [row.get("ordinal") for row in reference]==list(range(7)),"reference_count")
    require(all(row.get("phase")=="m1_prelude" for row in prelude),"prelude_phase_identity")
    safety=sequence_safety(run,[prelude,replay],samples,events,service)
    jobs=run["jobs"]
    m1_events=[e for e in events if e["job_id"]==PHASES[0]["job_id"]]
    r_events=[e for e in events if e["job_id"]==PHASES[1]["job_id"]]
    first=D.phase_receipts(PHASES[0],prelude,source,reference,m1_events,service,run)
    if len(jobs)==2:
        require(first["receipt_resource_violations"]==0,"replay_after_prelude_resource_failure")
    base=check_transfer(transfer,prelude,jobs,safety["exits"],prelude_hash)
    if len(jobs)==2:
        require(base is not None and transfer_hash is not None,"replay_without_transfer")
    ready_info=check_ready(proof,transfer,transfer_hash,r_events,run)
    require(proof is not None or not any(e["type"]=="ready" for e in r_events),"acknowledged_ready_missing_proof")
    second=replay_receipts(replay,prelude,transfer,ready_info,reference,r_events,service,run)
    first["raw_jobinfer_counters"]=first.pop("acknowledged_cost_lower_bound")
    first["execution_accounting"]={"actual_m1_forward_attempts":first["raw_jobinfer_counters"]["m1_attempts"],
            "within_phase_duplicate_cache_hits":first["raw_jobinfer_counters"]["m1_cache_hit"],"prelude_transfer_reuse":0,
            "m3_attempts":0,"m3_succeeded":0}
    stages=M3.stage_summary(stage_bytes,run,r_events,samples)
    markers=read_lines(stage_bytes,allow_tail=True)[0]
    require(not any(e["stage"] in {"m1_load","m1_predict"} for e in markers),"forbidden_m1_stage")
    require(len(jobs)==2 or not stage_bytes,"stage_without_replay_job")
    require(stages["predict_complete_ordinals"][:len(replay)]==list(range(len(replay))),"replay_without_completed_stage")
    completed_markers={e["item_ordinal"]:e["monotonic"] for e in markers if e["stage"]=="predict_complete"}
    require(all(completed_markers[row["ordinal"]]<=row["result"]["telemetry"]["monotonic"] for row in replay),"replay_stage_clock")
    if len(replay)==7:
        counts=Counter(span["stage"] for span in stages["closed_stages"] if span["outcome"]=="end")
        expected={stage:1 for stage in M3.STAGES if stage not in {"m1_load","m1_predict"}}
        expected["request_predict"]=7
        require(dict(counts)==expected,"complete_stage_coverage")
    summaries=[first,second]
    for i,summary in enumerate(summaries):
        normal=i<len(safety["exits"]) and safety["exits"][i]["normal_exit"]
        complete=i<len(jobs) and jobs[i]["status"]=="completed" and normal
        summary.update(submitted=i<len(jobs),completed=bool(complete),normal_exit=bool(normal),cost_complete=bool(complete),
                       unacknowledged_attempts=0 if complete else None,
                       cost_scope="completed_phase" if complete else "acknowledged_results_lower_bound")
    require(run.get("completed_events")==len(prelude)+len(replay)
            and run.get("completed_jobs")==sum(job["status"]=="completed" for job in jobs),"run_completion_counts")
    all_complete=len(jobs)==2 and all(s["completed"] for s in summaries) and stages["stage_completion_gate"] and ready_info["ready_acknowledged"]
    if run["status"]=="Completed":
        require(all_complete and run.get("failure_code") is None,"false_sequence_completion")
    else:
        require(isinstance(run.get("failure_code"),str) and bool(run["failure_code"]),"missing_failure_code")
    if run.get("failure_code")=="critical_memory_pressure":
        require(safety["system"]["critical_samples"]>0,"critical_without_observation")
    if run.get("failure_code")=="swap_thrashing":
        require(safety["system"]["thrashing"],"thrashing_without_observation")
    work_end=run["started_monotonic"]+150
    work_gate=all(e["monotonic"]<=work_end for e in markers if e["kind"]!="error") and all(row["result"]["telemetry"]["monotonic"]<=work_end for row in [*prelude,*replay])
    work_gate=work_gate and (proof is None or proof["monotonic"]<=work_end)
    safety.update(work_budget_gate=work_gate,stage_resource_gate=stages["memory_resource_violations"]==stages["unknown_memory_after_limits"]==0,
                  receipt_resource_gate=not any(s["receipt_resource_violations"] for s in summaries))
    safety["gate_passed"]=safety["gate_passed"] and all(safety[key] for key in ("work_budget_gate","readiness_attempt_gate","stage_resource_gate","receipt_resource_gate"))
    totals={key:sum(s["execution_accounting"][key] for s in summaries) for key in first["execution_accounting"]}
    return {"planned_jobs":2,"planned_events":347,"submitted_jobs":len(jobs),"verified_acknowledged_events":len(prelude)+len(replay),
            "missing_acknowledged_events":347-len(prelude)-len(replay),"phases":summaries,"execution_accounting_lower_bound":totals,
            "accounting_boundary":"Original raw m1_cache_hit is preserved per phase; transfer reuse is not an additional within-job duplicate hit.",
            "cost_complete":bool(all_complete),"unacknowledged_attempts":0 if all_complete else None,
            "transfer_verified":transfer is not None,"m1_absence_proof":ready_info,"all_planned_phases_completed":bool(all_complete),
            "diagnostic_completed":bool(all_complete and safety["gate_passed"] and run["status"]=="Completed"),
            "safety":safety,"stage_summary":stages,"critical_at_stage":stages["critical_at_stage"],
            "operational_followup_authorized":False,"operational_state":"stop-required",
            "claim_boundary":"One sealed current-run receipt transfer prototype; not the original website, execution equivalence, gold accuracy or causal memory attribution. Missing forward samples are not terminal peaks; EXP-079/080 statuses unchanged."}


def check_bindings(plan,run,claim,service,before):
    require(run.get("plan_sha256")==before["plan.json"]==claim.get("plan_sha256"),"plan_hash_binding")
    require(run.get("source_hashes")=={str((RUN/name).relative_to(ROOT)):digest for name,digest in before.items() if name!="run.json"},"artifact_hash_binding")
    require(run.get("artifacts_missing")==[name for name in OPTIONAL_ARTIFACTS if name not in before],"missing_artifact_binding")
    documents={}
    for group,number,hashes in (("parent_bindings","083",PARENT_HASHES),("reference_bindings","082",REFERENCE_HASHES)):
        documents[group]={}
        for name,digest in hashes.items():
            relative=f"private/validation/exp-{number}/attempt-1/{name}."+("jsonl" if name=="results" else "json")
            require(plan.get(group,{}).get(name)=={"path":relative,"sha256":digest} and regular_file(path_for(relative))==digest,"prior_hash_binding")
            documents[group][name]=read_lines(path_for(relative).read_bytes())[0] if name=="results" else LOCAL.strict_json(path_for(relative).read_text())
    parent,reference=documents["parent_bindings"],documents["reference_bindings"]
    require(parent["run"].get("status")=="Stopped" and parent["run"].get("failure_code")=="swap_thrashing"
            and parent["verification"].get("status")=="Passed" and parent["verification"].get("diagnostic_completed") is False
            and parent["verification"].get("safety",{}).get("gate_passed") is False,"parent_terminal_identity")
    require(reference["run"].get("status")=="Completed" and reference["verification"].get("status")=="Passed"
            and reference["verification"].get("diagnostic_completed") is True and reference["verification"].get("safety",{}).get("gate_passed") is True,"reference_terminal_identity")
    for prior in (parent,reference):
        for name,digest in prior["verification"]["source_hashes"].items():
            require(regular_file(path_for(name))==digest,"prior_artifact_identity")
    binding={"path":"private/validation/exp-079/attempt-3/plan.json","sha256":SOURCE_PLAN_HASH}
    require(plan.get("source_plan_binding")==parent["plan"]["source_plan_binding"]==binding
            and regular_file(path_for(binding["path"]))==binding["sha256"],"source_plan_binding")
    source_plan=LOCAL.strict_json(path_for(binding["path"]).read_text())
    require(plan.get("source_rows")==source_plan["source_rows"] and plan.get("source_logical_sha256")==source_plan["source_logical_sha256"]
            and plan.get("prefix_rows")==reference["plan"]["source_rows"],"source_parent_mapping")
    sources=plan.get("sources")
    require(isinstance(sources,dict) and set(sources)==set(parent["plan"]["sources"])|ADDITIONAL_SOURCES
            and all(sources.get(name)==digest for name,digest in parent["plan"]["sources"].items()),"dependency_set")
    for name,digest in sources.items():
        require(regular_file(path_for(name))==digest,"implementation_identity_drift")
    require(plan.get("protocol",{}).get("path")==PROTOCOL and regular_file(path_for(PROTOCOL,ROOT.parent))==plan["protocol"].get("sha256"),"protocol_identity")
    close(service,{"experiment_id":"EXP-084","root":str(ROOT),"bench_root":str(RUN/"bench"),"port":None},"supervisor_scope")
    close(claim,{"experiment_id":"EXP-084","attempt":1,"tier":"Minor","rq":"RQ-S3","cwd":str(ROOT),
                 "training":False,"gold_accessed":False,"source_network_fetched":False},"claim_contract")
    require(all(claim.get(key)==run.get(key) for key in ("started_at","started_monotonic")),"claim_start_binding")
    require(isinstance(claim.get("environment"),dict) and isinstance(claim.get("git_commit"),str)
            and isinstance(claim.get("git_status_porcelain"),list) and isinstance(claim.get("command"),list),"claim_environment_schema")
    return reference["results"]


def main():
    target=RUN/"verification.json"
    require(not target.exists() and not any(p.is_symlink() for p in (target,*target.parents)),"verification_exists_or_symlink")
    before={name:regular_file(RUN/name) for name in ARTIFACTS}
    before.update({name:regular_file(RUN/name) for name in OPTIONAL_ARTIFACTS if (RUN/name).exists() or (RUN/name).is_symlink()})
    report={"experiment_id":"EXP-084","attempt":1,"tier":"Minor","status":"Failed","diagnostic_completed":False,
            "operational_followup_authorized":False,"operational_state":"stop-required","models_loaded":False,
            "producer_numerical_helpers_imported":False,"gold_accessed":False,"verified_at":datetime.now(timezone.utc).isoformat(),
            "verifier_sha256":regular_file(Path(__file__)),"source_hashes":{str((RUN/name).relative_to(ROOT)):digest for name,digest in before.items()}}
    try:
        plan,run,claim,service=(LOCAL.strict_json((RUN/name).read_text()) for name in ("plan.json","run.json","run-claim.json","service.json"))
        reference=check_bindings(plan,run,claim,service,before)
        require(B.service_absent(service),"diagnostic_supervisor_still_running")
        source=read_source(path_for(plan["source_database"]))
        logical=sha(LOCAL.canonical(source))
        prelude,replay,samples,events=(read_lines((RUN/name).read_bytes())[0] for name in ("m1-results.jsonl","replay-results.jsonl","samples.jsonl","process-events.jsonl"))
        transfer,proof=(LOCAL.strict_json((RUN/name).read_text()) if name in before else None for name in OPTIONAL_ARTIFACTS)
        require(all(name not in before or isinstance(value,dict) for name,value in zip(OPTIONAL_ARTIFACTS,(transfer,proof))),"optional_artifact_schema")
        report.update(analyze(plan,run,source,reference,prelude,replay,samples,events,service,(RUN/"stages.jsonl").read_bytes(),transfer,proof,before["m1-results.jsonl"],before.get("transfer.json")))
        require(sha(LOCAL.canonical(read_source(path_for(plan["source_database"]))))==logical,"source_changed_during_audit")
        require(all(regular_file(RUN/name)==digest for name,digest in before.items()),"artifact_changed_during_audit")
        require([name for name in OPTIONAL_ARTIFACTS if not (RUN/name).exists()]==run["artifacts_missing"],"optional_artifact_changed_during_audit")
        require(all(regular_file(path_for(name))==digest for name,digest in plan["sources"].items()),"dependency_changed_during_audit")
        report.update(status="Passed",source_logical_sha256=logical,artifacts_missing=run["artifacts_missing"])
    except Exception as error:
        code=str(error) if isinstance(error,(B.VerificationError,LOCAL.VerificationError)) else type(error).__name__
        report.update(status="Failed",diagnostic_completed=False,error_code=code if re.fullmatch(r"[A-Za-z0-9_]{1,100}",code) else "verification_failed")
    descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,"w") as output:
        output.write(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print(json.dumps({key:report.get(key) for key in ("status","diagnostic_completed","operational_followup_authorized","error_code")}))
    return 0 if report["status"]=="Passed" else 1


if __name__=="__main__":
    raise SystemExit(main())
