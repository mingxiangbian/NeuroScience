"""Synthetic EXP-082 audit fixtures; no real model or historical source reads."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

from topicweb.core import make_record

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("test_exp082_verifier", ROOT/"scripts/verify_m3_diagnostic.py")
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)
MIB = 1024**2


def encoded(rows):
    return b"".join((json.dumps(row)+"\n").encode() for row in rows)


def process(pid, parent):
    start = "Mon Aug 31 10:00:00 2026"
    return {"pid": pid, "ppid": parent, "current_rss_bytes": MIB, "start_time": start,
            "process_key": f"{pid}|{start}", "comm": "Python"}


def raw_process(row):
    return f"{row['pid']} {row['ppid']} {row['current_rss_bytes']//1024} {row['start_time']} /usr/bin/Python"


def fixture(state="complete"):
    records = [make_record(source="upload", site="upload", object_type="row", source_object_id=str(i),
                           model_input_text=f"Self-authored diagnostic fixture {i}.") for i in range(7)]
    baseline = [{"m1_probabilities": [.7, .2, .1, .1, .1, .1], "hypothetical_route": i == 6} for i in range(7)]
    plan = {"experiment_id": "EXP-082", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", "planned_events": 7,
            "max_seconds": 180, "work_seconds": 150, "max_readiness_seconds": 60, "cleanup_seconds": 15,
            "mode": "research", "max_qwen_calls": 1, "audit_rate": 0, "seed": 42,
            "source_job": VERIFY.SOURCE_JOB, "source_snapshot_sha256": VERIFY.SOURCE_SNAPSHOT,
            "source_database": "private/jobs.sqlite3",
            "source_rows": [{"ordinal": i, "input_sha256": record["model_input_hash"], "route_eligible": i == 6} for i, record in enumerate(records)]}
    parent, child = process(100, 1), process(201, 100)
    service = {**parent, "experiment_id": "EXP-082", "port": None}
    samples, events, stages, results = [], [], [], []
    sample_count = 11 if state == "empty" else 15
    for i in range(sample_count):
        live = state != "empty" and 11 <= i <= 13
        seen = [child["process_key"]] if i >= 11 and state != "empty" else []
        pressure = 4 if state == "cancelled" and i == 13 else 1
        samples.append({"index": i, "job_id": "exp082-prefix7" if live else None,
                        "started_monotonic": i*1.2, "monotonic": i*1.2+.2, "disk_free_bytes": 2*1024*MIB,
                        "system": {"status": "observed", "monotonic": i*1.2+.1, "pressure_level": pressure,
                                   "pressure_raw": f"{pressure}\n", "page_size": 4096, "swapins": 1000, "swapouts": 2000,
                                   "vm_stat_raw": "Mach Virtual Memory Statistics: (page size of 4096 bytes)\nSwapins: 1000.\nSwapouts: 2000.\n"},
                        "processes": {"status": "observed", "parent": parent, "models": [child] if live else [],
                                      "tracked_other": [], "orphan_models": [], "seen_model_keys": seen,
                                      "absent_model_keys": [] if live else seen,
                                      "selected_ps": [raw_process(parent), *([raw_process(child)] if live else [])]}})
    ready = {"status": "NotReady" if state == "empty" else "Ready", "started_monotonic": .25,
             "ended_monotonic": 12.25, "indices": [] if state == "empty" else list(range(1, 11))}
    job = None
    if state != "empty":
        def event(kind, when, code=None, normal=False):
            events.append({"type": kind, "job_id": "exp082-prefix7", "monotonic": when,
                           "pid": None if kind == "constructor_started" else 201,
                           "process_key": None if kind == "constructor_started" else child["process_key"],
                           "returncode": code, "normal_exit": normal})
        event("constructor_started", 12.35)
        event("ready", 12.8)
        event("process_exit", 16., 0 if state == "complete" else -15)
        if state == "complete": event("final_gate_passed", 16.01, 0, True)
        job = {"id": "exp082-prefix7", "mode": "research", "status": "completed" if state == "complete" else "cancelled",
               "total_items": 7, "completed_items": 7 if state == "complete" else 6,
               "started_monotonic": 12.3, "ended_monotonic": 17.03, "normal_exit": state == "complete",
               "readiness_indices": ready["indices"], "readiness_started_monotonic": .25, "readiness_ended_monotonic": 12.25}
        observation = {"sample_index": 14, "absent_model_keys": [child["process_key"]]}
        if state == "complete": job["exit_observation"] = observation
        else:
            job["cleanup"] = {"job_id": job["id"], "started_monotonic": 15.85, "ended_monotonic": 17.02,
                              "max_seconds": 15, "terminal_confirmed": True, "models_absent_confirmed": True,
                              "normal_exit": False, "exit_observation": observation}
        def stage(kind, name, when, ordinal=None, observed=False):
            stages.append({"seq": len(stages), "pid": 201, "monotonic": when, "kind": kind, "stage": name,
                           "item_ordinal": ordinal, "memory": {"rss_peak_bytes": 2*MIB,
                            "mlx_status": "observed" if observed else "not_loaded", "active_bytes": MIB if observed else None,
                            "cache_bytes": 0 if observed else None, "peak_bytes": 2*MIB if observed else None}})
        stage("begin", "engine_build", 12.4)
        stage("begin", "m1_load", 12.5)
        stage("end", "m1_load", 12.6)
        stage("end", "engine_build", 12.7)
        for i in range(6):
            when = 13+i*.12
            for offset, kind, name in ((0, "begin", "request_predict"), (.01, "begin", "m1_predict"),
                                       (.02, "end", "m1_predict"), (.03, "end", "request_predict"), (.04, "point", "predict_complete")):
                stage(kind, name, when+offset, i)
        stage("begin", "request_predict", 13.8, 6)
        stage("begin", "m1_predict", 13.81, 6)
        stage("end", "m1_predict", 13.82, 6)
        stage("begin", "m3_factory", 13.9, 6)
        stage("begin", "mlx_import", 13.901, 6)
        stage("end", "mlx_import", 13.905, 6)
        stage("point", "mlx_limits_configured", 13.91, 6, True)
        stage("begin", "m3_backend_init", 13.92, 6, True)
        for i, name in enumerate(("adapter_head_numpy_load", "base_load", "lora_setup", "adapter_load", "head_load", "adapter_head_eval")):
            stage("begin", name, 14+i*.1, 6, True)
            stage("end", name, 14.05+i*.1, 6, True)
        stage("end", "m3_backend_init", 14.7, 6, True)
        stage("end", "m3_factory", 14.8, 6, True)
        stage("begin", "m3_predict", 14.9, 6, True)
        stage("begin", "m3_tokenization", 15., 6, True)
        stage("end", "m3_tokenization", 15.1, 6, True)
        stage("begin", "first_forward", 15.2, 6, True)
        if state == "complete":
            stage("end", "first_forward", 15.3, 6, True)
            stage("end", "m3_predict", 15.35, 6, True)
            stage("end", "request_predict", 15.4, 6, True)
            stage("point", "predict_complete", 15.45, 6, True)
        for i in range(job["completed_items"]):
            routed = i == 6
            costs = {name: 0 for name in VERIFY.BOUNDED.COSTS}
            costs.update(m1_attempts=1, m3_attempts=int(routed), m3_succeeded=int(routed))
            cumulative = {**costs, "m1_attempts": i+1}
            result = {"m1_probabilities": baseline[i]["m1_probabilities"], "m1_prediction": [1, 0, 0, 0, 0, 0],
                      "prediction": [0, 1, 0, 0, 0, 0] if routed else [1, 0, 0, 0, 0, 0],
                      "m3_probabilities": [.1, .8, .1, .1, .1, .1] if routed else None,
                      "m3_prediction": [0, 1, 0, 0, 0, 0] if routed else None,
                      "route_requested": routed, "hypothetical_route": routed, "used_path": "m3" if routed else "m1",
                      "fallback": False, "fallback_reason": None, "counters": costs, "cumulative_counters": cumulative,
                      "resources": {"peak_rss_bytes": 2*MIB, "mlx_peak_bytes": 2*MIB if routed else 0},
                      "telemetry": {"status": "observed", "monotonic": 15.46 if routed else 13.06+i*.12,
                                    "child_pid": 201, "parent_pid": 100, "child_current_rss_bytes": MIB, "parent_current_rss_bytes": MIB,
                                    "raw_ps": "201 1024\n100 1024\n"}}
            results.append({"ordinal": i, "input_sha256": records[i]["model_input_hash"], "result": result})
    end = 12.3 if state == "empty" else 17.1
    run = {"experiment_id": "EXP-082", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", "planned_events": 7,
           "status": "Completed" if state == "complete" else "Stopped", "failure_code": None if state == "complete" else "critical_memory_pressure" if state == "cancelled" else "readiness_timeout",
           "started_at": "2026-08-31T02:00:00Z", "started_monotonic": 0., "ended_monotonic": end, "elapsed_seconds": end,
           "completed_events": len(results), "job": job, "readiness": ready, "cleanup": job.get("cleanup") if job else None,
           "total_budget_exceeded": False,
           "child_launched": state != "empty", "child_returncode": 0 if state == "complete" else -15 if state == "cancelled" else None,
           "training": False, "gold_accessed": False, "source_network_fetched": False, "operational_followup_authorized": False}
    return [plan, run, results, baseline, samples, events, service, encoded(stages)], records


def test_seven_receipts_normal_exit_are_diagnostic_only():
    report = VERIFY.analyze(*fixture()[0])
    assert report["diagnostic_completed"] and report["safety"]["gate_passed"]
    assert report["planned_events"] == report["verified_acknowledged_events"] == 7
    assert report["cost_complete"] and report["acknowledged_cost_lower_bound"]["m3_attempts"] == 1
    assert report["operational_followup_authorized"] is False


def test_critical_cancelled_prefix_is_auditable_not_complete():
    report = VERIFY.analyze(*fixture("cancelled")[0])
    assert report["planned_events"] == 7 and report["verified_acknowledged_events"] == 6
    assert report["diagnostic_completed"] is False and report["safety"]["gate_passed"] is False
    assert report["safety"]["exit_gate"] is True
    assert report["unacknowledged_attempts"] is None and report["cost_complete"] is False
    assert report["acknowledged_cost_lower_bound"]["m3_attempts"] == 0
    point = report["critical_at_stage"][0]
    assert point["sample_index"] == 13 and point["causal_attribution"] is False
    assert point["active_stages"][-1]["stage"] == "first_forward"
    assert report["stage_summary"]["open_stages"][-1]["ended_monotonic"] is None


def test_quiet_failure_preserves_no_child_no_observed_model_memory():
    report = VERIFY.analyze(*fixture("empty")[0])
    assert report["verified_acknowledged_events"] == 0 and report["missing_acknowledged_events"] == 7
    assert report["diagnostic_completed"] is False and report["safety"]["readiness_gate"] is False
    assert report["stage_summary"]["observed_mlx_peak_bytes"] is None
    assert report["unacknowledged_attempts"] is None


def test_unterminated_json_even_if_parseable_is_not_committed():
    bundle, _ = fixture("cancelled")
    tail = json.dumps({"kind": "end", "stage": "first_forward"}).encode()
    bundle[-1] += tail
    report = VERIFY.analyze(*bundle)
    assert report["stage_summary"]["truncated_tail"]["bytes"] == len(tail)
    assert report["stage_summary"]["open_stages"][-1]["stage"] == "first_forward"
    with pytest.raises(ValueError, match="unterminated_artifact_line"):
        VERIFY.read_lines(tail)


@pytest.mark.parametrize("mutation", ["denominator", "reorder", "input", "unmeasured_zero", "early_observed", "wrong_close", "pid", "late_stage", "fake_exit", "lost_absence"])
def test_identity_missingness_and_stage_order_fail_closed(mutation):
    bundle, _ = fixture()
    stages = VERIFY.read_lines(bundle[-1])[0]
    if mutation == "denominator": bundle[0]["planned_events"] = 6
    elif mutation == "reorder": bundle[2][0]["ordinal"] = 1
    elif mutation == "input": bundle[2][0]["input_sha256"] = "0"*64
    elif mutation == "unmeasured_zero": stages[0]["memory"]["peak_bytes"] = 0
    elif mutation == "early_observed": stages[0]["memory"].update(mlx_status="observed", active_bytes=0, cache_bytes=0, peak_bytes=0)
    elif mutation == "wrong_close": stages[2]["stage"] = "engine_build"
    elif mutation == "pid": stages[0]["pid"] = 202
    elif mutation == "late_stage": stages[-1]["monotonic"] = 16.2
    elif mutation == "fake_exit": bundle[1]["child_returncode"] = -15
    else: bundle[4][-1]["processes"]["absent_model_keys"] = []
    bundle[-1] = encoded(stages)
    with pytest.raises(ValueError): VERIFY.analyze(*bundle)


def test_observed_stage_memory_limit_fails_safety_not_audit():
    bundle, _ = fixture()
    stages = VERIFY.read_lines(bundle[-1])[0]
    for event in stages:
        if event["memory"]["mlx_status"] == "observed": event["memory"]["peak_bytes"] = 10_000_000_001
    bundle[-1] = encoded(stages)
    report = VERIFY.analyze(*bundle)
    assert report["diagnostic_completed"] is True
    assert report["safety"]["stage_resource_gate"] is False and report["safety"]["gate_passed"] is False


def test_exception_unwind_is_not_success():
    bundle, _ = fixture("cancelled")
    stages = VERIFY.read_lines(bundle[-1])[0]
    for i, stage in enumerate(("first_forward", "m3_predict", "request_predict")):
        event = copy.deepcopy(stages[-1])
        event.update(seq=len(stages), monotonic=15.81+i*.01, kind="error", stage=stage)
        stages.append(event)
    bundle[-1] = encoded(stages)
    report = VERIFY.analyze(*bundle)
    assert len(report["stage_summary"]["errors"]) == 3 and not report["stage_summary"]["open_stages"]
    assert report["diagnostic_completed"] is False


def test_after_limit_unavailable_memory_is_auditable_unknown_stop():
    bundle, _ = fixture("cancelled")
    stages = VERIFY.read_lines(bundle[-1])[0]
    stages[-1]["memory"].update(mlx_status="not_sampled", active_bytes=None, cache_bytes=None, peak_bytes=None)
    bundle[-1] = encoded(stages)
    report = VERIFY.analyze(*bundle)
    assert report["stage_summary"]["unknown_memory_after_limits"] == 1
    assert report["safety"]["stage_resource_gate"] is False and report["diagnostic_completed"] is False


def test_complete_receipts_cannot_hide_a_missing_base_load_stage():
    bundle, _ = fixture()
    stages = [event for event in VERIFY.read_lines(bundle[-1])[0] if event["stage"] != "base_load"]
    for i, event in enumerate(stages): event["seq"] = i
    bundle[-1] = encoded(stages)
    with pytest.raises(ValueError, match="complete_stage_coverage"): VERIFY.analyze(*bundle)


def write_cli_fixture(tmp_path, monkeypatch, state):
    bundle, records = fixture(state)
    plan, run, results, baseline, samples, events, service, stages = bundle
    root = tmp_path/"web"
    target = root/"private/validation/exp-082/attempt-1"
    target.mkdir(parents=True)
    monkeypatch.setattr(VERIFY, "ROOT", root)
    monkeypatch.setattr(VERIFY, "RUN", target)
    monkeypatch.setattr(VERIFY.BOUNDED, "service_absent", lambda _: True)
    source_name = "scripts/frozen_fixture.py"
    for name in {source_name} | VERIFY.ADDITIONAL_SOURCES:
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Self-authored synthetic dependency.\n")
    parent_plan = {"source_rows": plan["source_rows"], "sources": {source_name: VERIFY.regular_file(root/source_name)}}
    parents = {"plan": parent_plan, "run": {"status": "Stopped", "failure_code": "critical_memory_pressure"},
               "verification": {"status": "Passed", "exp079_complete": False, "operational_state": "stop-required", "source_hashes": {}}}
    bindings, hashes = {}, {}
    for name, value in parents.items():
        path = root/f"private/validation/exp-079/attempt-3/{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        hashes[name] = VERIFY.regular_file(path)
        bindings[name] = {"path": str(path.relative_to(root)), "sha256": hashes[name]}
    monkeypatch.setattr(VERIFY, "PARENT_HASHES", hashes)
    protocol = root.parent/VERIFY.PROTOCOL
    protocol.parent.mkdir(parents=True, exist_ok=True)
    protocol.write_text("# Synthetic protocol fixture\n")
    plan.update(parent_bindings=bindings, sources={name: VERIFY.regular_file(root/name) for name in {source_name} | VERIFY.ADDITIONAL_SOURCES},
                protocol={"path": VERIFY.PROTOCOL, "sha256": VERIFY.regular_file(protocol)})
    with sqlite3.connect(root/"private/jobs.sqlite3") as db:
        db.execute("CREATE TABLE jobs (id TEXT, state TEXT, snapshot_hash TEXT, total_items INTEGER)")
        db.execute("CREATE TABLE items (job_id TEXT, ordinal INTEGER, record TEXT, result TEXT)")
        db.execute("INSERT INTO jobs VALUES (?,?,?,?)", (VERIFY.SOURCE_JOB, "completed", VERIFY.SOURCE_SNAPSHOT, 340))
        for i, (record, result) in enumerate(zip(records, baseline)):
            db.execute("INSERT INTO items VALUES (?,?,?,?)", (VERIFY.SOURCE_JOB, i, json.dumps(record), json.dumps(result)))
        # Reading beyond the authorized prefix would try to decode this invalid row.
        db.execute("INSERT INTO items VALUES (?,?,?,?)", (VERIFY.SOURCE_JOB, 7, "NOT JSON", "NOT JSON"))
    service.update(root=str(root), bench_root=str(target/"bench"))
    (target/"plan.json").write_text(json.dumps(plan))
    plan_hash = VERIFY.regular_file(target/"plan.json")
    claim = {"experiment_id": "EXP-082", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", "cwd": str(root),
             "started_at": run["started_at"], "started_monotonic": run["started_monotonic"], "plan_sha256": plan_hash,
             "environment": {}, "git_commit": "synthetic", "git_status_porcelain": [], "command": ["synthetic-run"],
             "training": False, "gold_accessed": False, "source_network_fetched": False}
    for name, value in (("service.json", service), ("run-claim.json", claim)):
        (target/name).write_text(json.dumps(value))
    for name, rows in (("results.jsonl", results), ("samples.jsonl", samples), ("process-events.jsonl", events)):
        (target/name).write_bytes(encoded(rows))
    (target/"stages.jsonl").write_bytes(stages)
    (target/"stdout.log").write_text("Synthetic observation only.\n")
    run.update(plan_sha256=plan_hash, source_hashes={str((target/name).relative_to(root)): VERIFY.regular_file(target/name) for name in VERIFY.ARTIFACTS if name != "run.json"})
    (target/"run.json").write_text(json.dumps(run))
    return target


@pytest.mark.parametrize("state", ["complete", "cancelled", "empty"])
def test_main_full_partial_empty_create_only_with_seven_row_database(tmp_path, monkeypatch, state):
    target = write_cli_fixture(tmp_path, monkeypatch, state)
    before = {path.name: path.read_bytes() for path in target.iterdir()}
    assert VERIFY.main() == 0
    report = json.loads((target/"verification.json").read_text())
    assert report["status"] == "Passed"
    assert report["diagnostic_completed"] is (state == "complete")
    assert report["planned_events"] == 7 and report["models_loaded"] is False
    assert all((target/name).read_bytes() == raw for name, raw in before.items())
    assert (target/"verification.json").stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError, match="verification_exists_or_symlink"): VERIFY.main()


def test_main_hash_drift_produces_failed_audit_without_repair(tmp_path, monkeypatch):
    target = write_cli_fixture(tmp_path, monkeypatch, "cancelled")
    with (target/"stages.jsonl").open("ab") as output: output.write(b" ")
    assert VERIFY.main() == 1
    report = json.loads((target/"verification.json").read_text())
    assert report["status"] == "Failed" and report["error_code"] == "artifact_hash_binding"
