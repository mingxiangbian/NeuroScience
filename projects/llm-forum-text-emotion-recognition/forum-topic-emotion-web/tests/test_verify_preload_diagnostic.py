"""Only self-authored fixtures: EXP-083 full/partial schedule and CLI audit."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

from topicweb.core import make_record

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFY = load("exp083_test_verifier", "scripts/verify_preload_diagnostic.py")
FIXTURE082 = load("exp083_prior_synthetic_fixture", "tests/test_verify_m3_diagnostic.py")


def fixture(monkeypatch, state="complete", acknowledged=6):
    old, first_seven = FIXTURE082.fixture()
    plan082, run082, reference, _, samples082, events082, service, _ = old
    source = []
    for i in range(340):
        unique = i if i < 338 else i-313
        record = make_record(source="upload", site="upload", object_type="row", source_object_id=str(i),
                             model_input_text=f"Self-authored diagnostic fixture {unique}.")
        source.append({"ordinal": i, "record": record,
                       "result": {"m1_probabilities": [.7, .2, .1, .1, .1, .1], "m1_prediction": [1, 0, 0, 0, 0, 0],
                                  "hypothetical_route": i == 6 or 50 <= i < 74}})
    snapshot = VERIFY.LOCAL.check_records([row["record"] for row in source])
    logical = VERIFY.sha(VERIFY.LOCAL.canonical(source))
    monkeypatch.setattr(VERIFY, "SOURCE_SNAPSHOT", snapshot)
    monkeypatch.setattr(VERIFY.B, "SOURCE_HASH", snapshot)
    monkeypatch.setattr(VERIFY, "SOURCE_LOGICAL", logical)
    source_metadata = VERIFY.B.validate_source_rows(source)
    plan = {"experiment_id": "EXP-083", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", "planned_jobs": 2,
            "planned_events": 347, "phase_order": [phase["phase"] for phase in VERIFY.PHASES], "phases": list(VERIFY.PHASES),
            "max_seconds": 180, "work_seconds": 150, "cleanup_seconds": 15, "max_readiness_seconds": 60,
            "audit_rate": 0, "seed": 42, "source_job": VERIFY.SOURCE_JOB, "source_snapshot_sha256": snapshot,
            "source_database": "private/jobs.sqlite3", "source_logical_sha256": logical,
            "source_rows": source_metadata, "prefix_rows": source_metadata[:7]}
    service["experiment_id"] = "EXP-083"
    first = copy.deepcopy(run082["job"])
    first.update(id=VERIFY.PHASES[0]["job_id"], phase="m1_prelude", mode="m1_only", total_items=340, completed_items=340)
    samples = copy.deepcopy(samples082)
    events = copy.deepcopy(events082)
    for sample in samples:
        if sample["job_id"]: sample["job_id"] = first["id"]
    for event in events: event["job_id"] = first["id"]
    jobs = [first]
    attempts = [{**copy.deepcopy(run082["readiness"]), "phase": "m1_prelude"}]
    results, costs, seen = [], {name: 0 for name in VERIFY.B.COSTS}, set()
    for i, row in enumerate(source):
        result = copy.deepcopy(reference[0]["result"])
        hashed = row["record"]["model_input_hash"]
        one = {name: 0 for name in costs}
        one.update(m1_attempts=int(hashed not in seen), m1_cache_hit=int(hashed in seen))
        seen.add(hashed)
        costs = {name: costs[name]+one[name] for name in costs}
        result.update(hypothetical_route=row["result"]["hypothetical_route"], counters=one, cumulative_counters=dict(costs))
        result["telemetry"]["monotonic"] = 13.06+i*.006
        results.append({"phase": "m1_prelude", "ordinal": i, "input_sha256": hashed, "result": result})
    stage_bytes = b""
    failure = None
    if state == "prelude_cancelled":
        first.update(status="cancelled", normal_exit=False, completed_items=12)
        results = results[:12]
        first.pop("exit_observation")
        first["cleanup"] = {"phase": first["phase"], "job_id": first["id"], "started_monotonic": 15.85,
                            "ended_monotonic": 17.02, "max_seconds": 15, "normal_exit": False,
                            "terminal_confirmed": True, "models_absent_confirmed": True,
                            "exit_observation": copy.deepcopy(run082["job"]["exit_observation"])}
        events = [event for event in events if event["type"] != "final_gate_passed"]
        events[-1]["returncode"] = -15
        samples[13]["system"].update(pressure_level=4, pressure_raw="4\n")
        failure = "critical_memory_pressure"
    elif state == "initial_quiet_fail":
        jobs, events, results = [], [], []
        samples = samples[:11]
        attempts[0].update(status="NotReady", indices=[])
        failure = "diagnostic_interrupted"
    else:
        r_bundle, _ = FIXTURE082.fixture("cancelled" if state == "research_cancelled" else "complete")
        _, r_run, r_results, _, r_samples, r_events, _, r_stages = r_bundle
        shift = 16.8
        old_key = r_events[1]["process_key"]
        new_key = old_key.replace("201|", "301|", 1)
        prior_key = events[1]["process_key"]
        def move_event(event):
            out = copy.deepcopy(event)
            out["monotonic"] += shift
            out["job_id"] = VERIFY.PHASES[1]["job_id"]
            if out["pid"] is not None:
                out.update(pid=301, process_key=new_key)
            return out
        moved = []
        for original in r_samples[1:]:
            row = copy.deepcopy(original)
            row["index"] += 14
            row["started_monotonic"] += shift
            row["monotonic"] += shift
            row["system"]["monotonic"] += shift
            if row["job_id"]: row["job_id"] = VERIFY.PHASES[1]["job_id"]
            processes = row["processes"]
            processes["seen_model_keys"] = sorted([prior_key]+[new_key for key in processes["seen_model_keys"]])
            processes["absent_model_keys"] = sorted([prior_key]+[new_key for key in processes["absent_model_keys"]])
            for model in processes["models"]: model.update(pid=301, process_key=new_key)
            processes["selected_ps"] = [line.replace("201 100", "301 100") for line in processes["selected_ps"]]
            moved.append(row)
        ready = copy.deepcopy(r_run["readiness"])
        ready.update(phase="research_prefix", started_monotonic=17.05, ended_monotonic=29.05, indices=list(range(15,25)))
        attempts.append(ready)
        if state in {"research_quiet_fail", "critical_after_prelude"}:
            ready.update(status="NotReady", indices=[])
            moved = moved[:10]
            moved[-1]["system"].update(pressure_level=4, pressure_raw="4\n")
            samples += moved
            if state == "critical_after_prelude":
                samples[14]["system"].update(pressure_level=4, pressure_raw="4\n")
            failure = "critical_memory_pressure"
        else:
            samples += moved
            second = copy.deepcopy(r_run["job"])
            second.update(id=VERIFY.PHASES[1]["job_id"], phase="research_prefix", started_monotonic=29.1,
                          ended_monotonic=33.83, readiness_indices=list(range(15,25)),
                          readiness_started_monotonic=17.05, readiness_ended_monotonic=29.05)
            if state == "research_cancelled":
                second["completed_items"] = acknowledged
                second["cleanup"].update(job_id=second["id"], phase=second["phase"], started_monotonic=32.65, ended_monotonic=33.82)
                second["cleanup"]["exit_observation"] = {"sample_index": 28, "absent_model_keys": sorted([prior_key,new_key])}
                r_results = r_results[:acknowledged]
                failure = "critical_memory_pressure"
            else:
                second["exit_observation"] = {"sample_index": 28, "absent_model_keys": sorted([prior_key,new_key])}
            jobs.append(second)
            events += [move_event(event) for event in r_events]
            stage_rows = VERIFY.read_lines(r_stages)[0]
            if state == "research_cancelled" and acknowledged < 6:
                stage_rows = [event for event in stage_rows if event["item_ordinal"] is None
                              or event["item_ordinal"] < acknowledged
                              or event["item_ordinal"] == acknowledged and event["kind"] == "begin" and event["stage"] in {"request_predict", "m1_predict"}]
            for i, event in enumerate(stage_rows):
                event.update(seq=i, pid=301, monotonic=event["monotonic"]+shift)
            stage_bytes = FIXTURE082.encoded(stage_rows)
            for row in r_results:
                row = copy.deepcopy(row)
                row["phase"] = "research_prefix"
                telemetry = row["result"]["telemetry"]
                telemetry.update(child_pid=301, monotonic=telemetry["monotonic"]+shift,
                                 raw_ps=telemetry["raw_ps"].replace("201 1024", "301 1024"))
                results.append(row)
    ended = max(samples[-1]["monotonic"], attempts[-1]["ended_monotonic"], jobs[-1]["ended_monotonic"] if jobs else 0)+.1
    exits = []
    for job in jobs:
        owned = [event for event in events if event["job_id"] == job["id"]]
        exited = [event for event in owned if event["type"] == "process_exit"]
        exits.append({"id": job["id"], "phase": job["phase"], "child_launched": any(event.get("pid") is not None for event in owned),
                      "returncode": exited[-1]["returncode"] if exited else None})
    run = {"experiment_id": "EXP-083", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", "planned_jobs": 2, "planned_events": 347,
           "status": "Completed" if failure is None else "Stopped", "failure_code": failure,
           "started_at": "2026-08-31T02:00:00Z", "started_monotonic": 0., "ended_monotonic": ended, "elapsed_seconds": ended,
           "jobs": jobs, "readiness_attempts": attempts, "cleanups": [job["cleanup"] for job in jobs if job.get("cleanup")],
           "child_exit_summary": exits, "completed_jobs": sum(job["status"] == "completed" for job in jobs),
           "completed_events": len(results), "total_budget_exceeded": False,
           "training": False, "gold_accessed": False, "source_network_fetched": False, "operational_followup_authorized": False}
    return [plan, run, source, reference, results, samples, events, service, stage_bytes]


def test_complete_two_processes_347_events_and_fresh_cache(monkeypatch):
    report = VERIFY.analyze(*fixture(monkeypatch))
    assert report["diagnostic_completed"] and report["safety"]["gate_passed"]
    assert report["verified_acknowledged_events"] == report["planned_events"] == 347
    assert [phase["acknowledged_cost_lower_bound"]["m1_attempts"] for phase in report["phases"]] == [338,7]
    assert [phase["acknowledged_cost_lower_bound"]["m3_attempts"] for phase in report["phases"]] == [0,1]
    assert report["phases"][1]["exp082_probability_max_abs_difference"] == 0
    assert report["operational_followup_authorized"] is False


@pytest.mark.parametrize("count", range(7))
def test_research_cancelled_prefix_keeps_denominator_and_unknown_cost(monkeypatch, count):
    report = VERIFY.analyze(*fixture(monkeypatch, "research_cancelled", count))
    assert report["verified_acknowledged_events"] == 340+count and report["planned_events"] == 347
    assert report["diagnostic_completed"] is False and report["safety"]["gate_passed"] is False
    assert report["phases"][1]["unacknowledged_attempts"] is None
    assert report["phases"][1]["cost_complete"] is False and report["safety"]["exit_gate"] is True


@pytest.mark.parametrize("state", ["prelude_cancelled", "initial_quiet_fail", "research_quiet_fail", "critical_after_prelude"])
def test_stops_without_unregistered_research_or_fake_stages(monkeypatch, state):
    report = VERIFY.analyze(*fixture(monkeypatch, state))
    assert report["diagnostic_completed"] is False
    assert report["phases"][1]["submitted"] is False and report["phases"][1]["verified_acknowledged_events"] == 0
    assert report["stage_summary"]["committed_events"] == 0


@pytest.mark.parametrize("mutation", ["failed_prelude", "unsafe_prelude", "denominator", "phase_order", "m1_counter", "shared_cache", "parity", "missing_base", "pid", "lost_absence"])
def test_preconditions_identity_parity_and_stage_integrity_fail_closed(monkeypatch, mutation):
    bundle = fixture(monkeypatch)
    if mutation == "failed_prelude": bundle[1]["jobs"][0]["status"] = "failed"
    elif mutation == "unsafe_prelude": bundle[5][13]["system"].update(pressure_level=4, pressure_raw="4\n")
    elif mutation == "denominator": bundle[0]["planned_events"] = 7
    elif mutation == "phase_order": bundle[4][0]["phase"] = "research_prefix"
    elif mutation == "m1_counter": bundle[4][0]["result"]["counters"]["m3_attempts"] = 1
    elif mutation == "shared_cache": bundle[4][340]["result"]["counters"].update(m1_attempts=0,m1_cache_hit=1)
    elif mutation == "parity": bundle[4][-1]["result"]["m3_probabilities"][1] = .75
    elif mutation in {"missing_base", "pid"}:
        rows = VERIFY.read_lines(bundle[-1])[0]
        if mutation == "missing_base": rows = [row for row in rows if row["stage"] != "base_load"]
        else: rows[0]["pid"] = 201
        for i,row in enumerate(rows): row["seq"] = i
        bundle[-1] = FIXTURE082.encoded(rows)
    else: bundle[5][-1]["processes"]["absent_model_keys"] = []
    with pytest.raises(ValueError): VERIFY.analyze(*bundle)


def test_after_limits_unknown_and_truncated_tail_remain_partial(monkeypatch):
    bundle = fixture(monkeypatch, "research_cancelled")
    rows = VERIFY.read_lines(bundle[-1])[0]
    rows[-1]["memory"].update(mlx_status="not_sampled", active_bytes=None, cache_bytes=None, peak_bytes=None)
    bundle[-1] = FIXTURE082.encoded(rows)+b'{"incomplete":'
    report = VERIFY.analyze(*bundle)
    assert report["stage_summary"]["unknown_memory_after_limits"] == 1
    assert report["stage_summary"]["truncated_tail"]["bytes"] > 0
    assert report["diagnostic_completed"] is False and report["safety"]["stage_resource_gate"] is False


def test_two_direct_workers_are_not_accepted_as_serial(monkeypatch):
    bundle = fixture(monkeypatch)
    first = copy.deepcopy(bundle[5][11]["processes"]["models"][0])
    second_sample = bundle[5][26]["processes"]
    second_sample["models"].append(first)
    second_sample["absent_model_keys"] = []
    second_sample["selected_ps"].append(FIXTURE082.raw_process(first))
    report = VERIFY.analyze(*bundle)
    assert report["safety"]["processes"]["multiple_inference_worker_samples"] == 1
    assert report["safety"]["processes"]["maximum_inference_workers"] == 2
    assert report["diagnostic_completed"] is False


def test_failed_research_constructor_cannot_borrow_prelude_exit(monkeypatch):
    bundle = fixture(monkeypatch, "research_cancelled", 0)
    job = bundle[1]["jobs"][1]
    job.update(status="failed", completed_items=0)
    job["cleanup"]["terminal_confirmed"] = False
    prior_key = bundle[6][1]["process_key"]
    for row in bundle[5][15:]:
        p = row["processes"]
        p.update(models=[], seen_model_keys=[prior_key], absent_model_keys=[prior_key], selected_ps=p["selected_ps"][:1])
    job["cleanup"]["exit_observation"]["absent_model_keys"] = [prior_key]
    bundle[6][:] = [event for event in bundle[6] if event["job_id"] != job["id"] or event["type"] == "constructor_started"]
    bundle[-1] = b""
    bundle[1]["child_exit_summary"][1].update(child_launched=False, returncode=None)
    report = VERIFY.analyze(*bundle)
    assert report["diagnostic_completed"] is False and report["safety"]["gate_passed"] is False
    assert report["phases"][1]["normal_exit"] is False and report["phases"][1]["cost_complete"] is False
    bundle[1]["child_exit_summary"][1]["returncode"] = 0
    with pytest.raises(ValueError, match="child_exit_summary_binding"): VERIFY.analyze(*bundle)


def cli_fixture(tmp_path, monkeypatch, state):
    bundle = fixture(monkeypatch, state)
    plan, run, source, reference, results, samples, events, service, stages = bundle
    root = tmp_path/"web"
    target = root/"private/validation/exp-083/attempt-1"
    target.mkdir(parents=True)
    monkeypatch.setattr(VERIFY, "ROOT", root)
    monkeypatch.setattr(VERIFY, "RUN", target)
    monkeypatch.setattr(VERIFY.B, "service_absent", lambda _: True)
    frozen_name = "scripts/frozen_fixture.py"
    for name in VERIFY.ADDITIONAL_SOURCES | {frozen_name}:
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Self-authored synthetic frozen dependency.\n")
    source_plan = root/"private/validation/exp-079/attempt-3/plan.json"
    source_plan.parent.mkdir(parents=True)
    source_plan.write_text(json.dumps({"source_rows": plan["source_rows"], "source_logical_sha256": plan["source_logical_sha256"]}))
    source_hash = VERIFY.regular_file(source_plan)
    monkeypatch.setattr(VERIFY, "SOURCE_PLAN_HASH", source_hash)
    source_binding = {"path": str(source_plan.relative_to(root)), "sha256": source_hash}
    prior = root/"private/validation/exp-082/attempt-1"
    prior.mkdir(parents=True)
    (prior/"results.jsonl").write_bytes(FIXTURE082.encoded(reference))
    parents = {
        "plan": {"parent_bindings": {"plan": source_binding}, "source_rows": plan["prefix_rows"], "sources": {frozen_name: VERIFY.regular_file(root/frozen_name)}},
        "run": {"status": "Completed", "completed_events": 7},
        "verification": {"status": "Passed", "diagnostic_completed": True, "safety": {"gate_passed": True},
                         "source_hashes": {str((prior/"results.jsonl").relative_to(root)): VERIFY.regular_file(prior/"results.jsonl")}},
    }
    parent_hashes, bindings = {}, {}
    for name,value in parents.items():
        path = prior/(name+".json")
        path.write_text(json.dumps(value))
        parent_hashes[name] = VERIFY.regular_file(path)
        bindings[name] = {"path": str(path.relative_to(root)), "sha256": parent_hashes[name]}
    monkeypatch.setattr(VERIFY, "PARENT_HASHES", parent_hashes)
    protocol = root.parent/VERIFY.PROTOCOL
    protocol.parent.mkdir(parents=True)
    protocol.write_text("# Synthetic EXP083 protocol\n")
    plan.update(parent_bindings=bindings, source_plan_binding=source_binding,
                sources={name: VERIFY.regular_file(root/name) for name in VERIFY.ADDITIONAL_SOURCES | {frozen_name}},
                protocol={"path": VERIFY.PROTOCOL, "sha256": VERIFY.regular_file(protocol)})
    with sqlite3.connect(root/"private/jobs.sqlite3") as db:
        db.execute("CREATE TABLE jobs (id TEXT, state TEXT, snapshot_hash TEXT, total_items INTEGER)")
        db.execute("CREATE TABLE items (job_id TEXT, ordinal INTEGER, record TEXT, result TEXT)")
        db.execute("INSERT INTO jobs VALUES (?,?,?,?)", (VERIFY.SOURCE_JOB,"completed",VERIFY.SOURCE_SNAPSHOT,340))
        for row in source:
            db.execute("INSERT INTO items VALUES (?,?,?,?)", (VERIFY.SOURCE_JOB,row["ordinal"],json.dumps(row["record"]),json.dumps(row["result"])))
        db.execute("INSERT INTO items VALUES (?,?,?,?)", ("out-of-scope",0,"NOT JSON","NOT JSON"))
    service.update(root=str(root), bench_root=str(target/"bench"))
    (target/"plan.json").write_text(json.dumps(plan))
    plan_hash = VERIFY.regular_file(target/"plan.json")
    claim = {"experiment_id": "EXP-083", "attempt": 1, "tier": "Minor", "rq": "RQ-S3", "cwd": str(root),
             "started_at": run["started_at"], "started_monotonic": 0., "plan_sha256": plan_hash,
             "environment": {}, "git_commit": "synthetic", "git_status_porcelain": [], "command": ["fixture-run"],
             "training": False, "gold_accessed": False, "source_network_fetched": False}
    for name,value in (("service.json",service),("run-claim.json",claim)):
        (target/name).write_text(json.dumps(value))
    for name,rows in (("results.jsonl",results),("samples.jsonl",samples),("process-events.jsonl",events)):
        (target/name).write_bytes(FIXTURE082.encoded(rows))
    (target/"stages.jsonl").write_bytes(stages)
    (target/"stdout.log").write_text("Synthetic phase log.\n")
    run.update(plan_sha256=plan_hash, source_hashes={str((target/name).relative_to(root)): VERIFY.regular_file(target/name) for name in VERIFY.ARTIFACTS if name != "run.json"})
    (target/"run.json").write_text(json.dumps(run))
    return target


@pytest.mark.parametrize("state", ["complete", "research_cancelled", "prelude_cancelled", "research_quiet_fail", "initial_quiet_fail", "critical_after_prelude"])
def test_main_cli_temp_database_full_and_partial_are_append_only(tmp_path, monkeypatch, state):
    target = cli_fixture(tmp_path, monkeypatch, state)
    before = {path.name:path.read_bytes() for path in target.iterdir()}
    assert VERIFY.main() == 0
    report = json.loads((target/"verification.json").read_text())
    assert report["status"] == "Passed" and report["diagnostic_completed"] is (state == "complete")
    assert report["planned_events"] == 347 and report["models_loaded"] is False
    assert all((target/name).read_bytes() == value for name,value in before.items())
    assert (target/"verification.json").stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError, match="verification_exists_or_symlink"): VERIFY.main()


def test_main_hash_drift_is_failed_audit_not_repaired(tmp_path, monkeypatch):
    target = cli_fixture(tmp_path, monkeypatch, "research_cancelled")
    with (target/"stages.jsonl").open("ab") as output: output.write(b" ")
    assert VERIFY.main() == 1
    report = json.loads((target/"verification.json").read_text())
    assert report["status"] == "Failed" and report["error_code"] == "artifact_hash_binding"
