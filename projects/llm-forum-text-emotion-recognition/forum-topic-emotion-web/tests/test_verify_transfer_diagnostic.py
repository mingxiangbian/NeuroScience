"""EXP-084 self-authored transfer fixtures; no model, real source or verifier run."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import struct

import pytest

ROOT=Path(__file__).resolve().parents[1]


def load(name,relative):
    spec=importlib.util.spec_from_file_location(name,ROOT/relative)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFY=load("exp084_test_verifier","scripts/verify_transfer_diagnostic.py")
OLD=load("exp084_synthetic_prior_fixture","tests/test_verify_preload_diagnostic.py")


def encoded(rows):
    return b"".join((json.dumps(row)+"\n").encode() for row in rows)


def as_float32(values):
    return list(struct.unpack("<6f",struct.pack("<6f",*values)))


def functional(result):
    result["m1_probabilities"]=as_float32(result["m1_probabilities"])
    if result["m3_probabilities"] is not None:
        result["m3_probabilities"]=as_float32(result["m3_probabilities"])
    labels=[name for name,on in zip(VERIFY.LOCAL.LABELS,result["prediction"]) if on]
    routed=result["route_requested"]
    result.update(prediction6=list(result["prediction"]),active_labels=labels,labels=labels,neutral=not labels,
                  actual_model=result["used_path"],route_eligible=result["hypothetical_route"],routed=routed,degraded=False,
                  route_score=.8 if result["hypothetical_route"] else .2,m1_entropy=.4,threshold_margin=.11,
                  tokenlengths={"m1":{"input_tokens":32,"used_tokens":32,"truncated":False},
                                "m3":{"input_tokens":50,"used_tokens":50,"truncated":False} if routed else None},
                  truncflags={"m1":False,"m3":False if routed else None})


def fixture(monkeypatch,state="complete",acknowledged=6):
    initial="research_cancelled" if state=="constructor_failed" else state
    bundle=OLD.fixture(monkeypatch,initial,0 if state=="constructor_failed" else acknowledged)
    plan,run,source,reference,rows,samples,events,service,stages=bundle
    for row in source:
        row["result"]["m1_probabilities"]=as_float32(row["result"]["m1_probabilities"])
    logical=VERIFY.sha(VERIFY.LOCAL.canonical(source))
    monkeypatch.setattr(VERIFY,"SOURCE_SNAPSHOT",plan["source_snapshot_sha256"])
    monkeypatch.setattr(VERIFY.B,"SOURCE_HASH",plan["source_snapshot_sha256"])
    monkeypatch.setattr(VERIFY,"SOURCE_LOGICAL",logical)
    plan.update(experiment_id="EXP-084",strategy=VERIFY.STRATEGY,source_logical_sha256=logical,
                phases=copy.deepcopy(list(VERIFY.PHASES)))
    run["experiment_id"]="EXP-084"
    service["experiment_id"]="EXP-084"
    mapping={"exp083-m1-prelude":"exp084-m1-prelude","exp083-research-prefix":"exp084-m3-replay"}
    for job in run["jobs"]:
        job["id"]=mapping[job["id"]]
        if job.get("cleanup"): job["cleanup"]["job_id"]=job["id"]
    for item in run["child_exit_summary"]: item["id"]=mapping[item["id"]]
    for event in events: event["job_id"]=mapping[event["job_id"]]
    for sample in samples:
        if sample["job_id"]: sample["job_id"]=mapping[sample["job_id"]]
    for row in [*rows,*reference]: functional(row["result"])
    prelude=[row for row in rows if row["phase"]=="m1_prelude"]
    replay=[row for row in rows if row["phase"]=="research_prefix"]
    for row in prelude: row["result"]["fingerprint"]="b"*64
    for row in reference:
        row["result"].update(fingerprint="a"*64,cache_hit=False,latency_ms=9.9)
    m1_hash=VERIFY.sha(encoded(prelude))
    transfer=proof=None
    transfer_hash=None
    if run["jobs"] and run["jobs"][0]["status"]=="completed":
        transfer={"experiment_id":"EXP-084","attempt":1,"source_job_id":"exp084-m1-prelude","source_phase":"m1_prelude",
                  "source_results_path":"private/validation/exp-084/attempt-1/m1-results.jsonl",
                  "source_results_sha256":m1_hash,"source_results_count":340,"fingerprint":"b"*64,
                  "entries":[{"ordinal":row["ordinal"],"input_sha256":row["input_sha256"],
                              "m1_probabilities":row["result"]["m1_probabilities"],
                              "tokenlengths":{"m1":copy.deepcopy(row["result"]["tokenlengths"]["m1"])},
                              "source_result_sha256":VERIFY.sha(VERIFY.LOCAL.canonical(row))} for row in prelude[:7]]}
        transfer_hash=VERIFY.sha(json.dumps(transfer).encode())
        fingerprint=VERIFY.sha(VERIFY.LOCAL.canonical({"base_fingerprint":"b"*64,"strategy":VERIFY.STRATEGY,"transfer_sha256":transfer_hash}))
        if len(run["jobs"])==2:
            proof={"experiment_id":"EXP-084","pid":301,"monotonic":29.55,"transfer_sha256":transfer_hash,
                   "cache_entries":7,"cache_input_sha256s":[row["input_sha256"] for row in transfer["entries"]],
                   "m1_instance_absent":True,"m1_backend_calls":0,"fingerprint":fingerprint,"base_fingerprint":"b"*64,
                   "strategy":VERIFY.STRATEGY,"modelstatus":{"m1":"receipt_replay_not_loaded","m3":"not_loaded","mode":"research"}}
            for i,row in enumerate(replay):
                row["result"].update(prelude_transfer_reuse=True,m1_execution_origin="current_run_m1_prelude_receipt",
                                     fingerprint=fingerprint,cache_hit=i!=6,latency_ms=0.01)
                row["result"]["counters"].update(m1_attempts=0,m1_cache_hit=1)
                row["result"]["cumulative_counters"].update(m1_attempts=0,m1_cache_hit=i+1)
    stage_rows=[row for row in VERIFY.read_lines(stages)[0] if row["stage"] not in {"m1_load","m1_predict"}]
    for i,row in enumerate(stage_rows): row["seq"]=i
    stages=encoded(stage_rows)
    if state=="constructor_failed":
        job=run["jobs"][1]
        job["status"]="failed"
        job["cleanup"]["terminal_confirmed"]=False
        prior_key=events[1]["process_key"]
        for row in samples[15:]:
            p=row["processes"]
            p.update(models=[],seen_model_keys=[prior_key],absent_model_keys=[prior_key],selected_ps=p["selected_ps"][:1])
        job["cleanup"]["exit_observation"]["absent_model_keys"]=[prior_key]
        events[:]=[event for event in events if event["job_id"]!=job["id"] or event["type"]=="constructor_started"]
        run["child_exit_summary"][1].update(child_launched=False,returncode=None)
        stages=b""
        proof=None
    run["artifacts_missing"]=[name for name,value in (("transfer.json",transfer),("m3-ready.json",proof)) if value is None]
    return [plan,run,source,reference,prelude,replay,samples,events,service,stages,transfer,proof,m1_hash,transfer_hash]


def test_completed_transfer_is_not_seven_m1_forwards_or_nine_duplicates(monkeypatch):
    report=VERIFY.analyze(*fixture(monkeypatch))
    assert report["diagnostic_completed"] and report["safety"]["gate_passed"]
    assert report["planned_events"]==report["verified_acknowledged_events"]==347
    assert report["execution_accounting_lower_bound"]=={"actual_m1_forward_attempts":338,"within_phase_duplicate_cache_hits":2,
                                                       "prelude_transfer_reuse":7,"m3_attempts":1,"m3_succeeded":1}
    assert report["phases"][1]["raw_jobinfer_counters"]["m1_cache_hit"]==7
    assert report["phases"][1]["raw_jobinfer_counters"]["m1_attempts"]==0
    assert report["m1_absence_proof"]["available"] and report["operational_followup_authorized"] is False


@pytest.mark.parametrize("count",range(7))
def test_replay_cancelled_prefix_preserves_unknown_remaining_cost(monkeypatch,count):
    report=VERIFY.analyze(*fixture(monkeypatch,"research_cancelled",count))
    assert report["verified_acknowledged_events"]==340+count and report["planned_events"]==347
    assert report["diagnostic_completed"] is False and report["phases"][1]["unacknowledged_attempts"] is None
    assert report["phases"][1]["execution_accounting"]["prelude_transfer_reuse"]==count
    assert report["safety"]["exit_gate"] is True


@pytest.mark.parametrize("state",["prelude_cancelled","initial_quiet_fail","research_quiet_fail","critical_after_prelude","constructor_failed"])
def test_missing_optional_artifacts_are_not_fabricated_success(monkeypatch,state):
    report=VERIFY.analyze(*fixture(monkeypatch,state))
    assert report["diagnostic_completed"] is False
    assert report["m1_absence_proof"]["available"] is False
    assert report["stage_summary"]["committed_events"]==0


@pytest.mark.parametrize("mutation",["old_run_source","row_hash","token","lossy_float","sealed_p1","receipt_p1","raw_m1_cost","reuse_flag",
                                     "model_loaded","proof_pid","proof_hash","proof_missing","m1_stage","missing_base","label","probability","shared_raw_cache"])
def test_provenance_absence_cost_and_functional_drift_fail_closed(monkeypatch,mutation):
    bundle=fixture(monkeypatch)
    transfer,proof=bundle[10],bundle[11]
    if mutation=="old_run_source": transfer["source_results_path"]="private/validation/exp-082/attempt-1/results.jsonl"
    elif mutation=="row_hash": transfer["entries"][0]["source_result_sha256"]="0"*64
    elif mutation=="token": transfer["entries"][0]["tokenlengths"]["m1"]["used_tokens"]=31
    elif mutation=="lossy_float": transfer["entries"][0]["m1_probabilities"]=list(transfer["entries"][0]["m1_probabilities"]); transfer["entries"][0]["m1_probabilities"][0]=.7
    elif mutation=="sealed_p1": transfer["entries"][0]["m1_probabilities"]=as_float32([.6,.2,.1,.1,.1,.1])
    elif mutation=="receipt_p1": bundle[5][0]["result"]["m1_probabilities"]=as_float32([.6,.2,.1,.1,.1,.1])
    elif mutation=="raw_m1_cost": bundle[5][0]["result"]["counters"].update(m1_attempts=1,m1_cache_hit=0)
    elif mutation=="reuse_flag": bundle[5][0]["result"]["prelude_transfer_reuse"]=False
    elif mutation=="model_loaded": proof["modelstatus"]["m1"]="loaded"
    elif mutation=="proof_pid": proof["pid"]=201
    elif mutation=="proof_hash": proof["transfer_sha256"]="0"*64
    elif mutation=="proof_missing": bundle[11]=None
    elif mutation in {"m1_stage","missing_base"}:
        rows=VERIFY.read_lines(bundle[9])[0]
        if mutation=="m1_stage": rows[0]["stage"]="m1_load"
        else: rows=[row for row in rows if row["stage"]!="base_load"]
        for i,row in enumerate(rows): row["seq"]=i
        bundle[9]=encoded(rows)
    elif mutation=="label": bundle[5][0]["result"]["labels"]=["fear"]
    elif mutation=="probability": bundle[5][-1]["result"]["m3_probabilities"][1]=.75
    else: bundle[5][0]["result"]["cumulative_counters"]["m1_cache_hit"]=3
    with pytest.raises(ValueError): VERIFY.analyze(*bundle)


def test_unknown_after_limit_and_open_forward_remain_unknown(monkeypatch):
    bundle=fixture(monkeypatch,"research_cancelled")
    rows=VERIFY.read_lines(bundle[9])[0]
    rows[-1]["memory"].update(mlx_status="not_sampled",active_bytes=None,cache_bytes=None,peak_bytes=None)
    bundle[9]=encoded(rows)+b'{"tail":'
    report=VERIFY.analyze(*bundle)
    assert report["diagnostic_completed"] is False and report["safety"]["stage_resource_gate"] is False
    assert report["stage_summary"]["truncated_tail"]["bytes"]>0


def cli_fixture(tmp_path,monkeypatch,state):
    data=fixture(monkeypatch,state)
    plan,run,source,reference,prelude,replay,samples,events,service,stages,transfer,proof,_,_=data
    root=tmp_path/"web"
    target=root/"private/validation/exp-084/attempt-1"
    target.mkdir(parents=True)
    monkeypatch.setattr(VERIFY,"ROOT",root)
    monkeypatch.setattr(VERIFY,"RUN",target)
    monkeypatch.setattr(VERIFY.B,"service_absent",lambda _:True)
    frozen="scripts/frozen_fixture.py"
    for name in VERIFY.ADDITIONAL_SOURCES|{frozen}:
        path=root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text("# Self-authored synthetic dependency.\n")
    source_plan=root/"private/validation/exp-079/attempt-3/plan.json"
    source_plan.parent.mkdir(parents=True)
    source_plan.write_text(json.dumps({"source_rows":plan["source_rows"],"source_logical_sha256":plan["source_logical_sha256"]}))
    digest=VERIFY.regular_file(source_plan)
    monkeypatch.setattr(VERIFY,"SOURCE_PLAN_HASH",digest)
    binding={"path":str(source_plan.relative_to(root)),"sha256":digest}
    documents={
        "parent_bindings":{"plan":{"source_plan_binding":binding,"sources":{frozen:VERIFY.regular_file(root/frozen)}},
                           "run":{"status":"Stopped","failure_code":"swap_thrashing"},
                           "verification":{"status":"Passed","diagnostic_completed":False,"safety":{"gate_passed":False},"source_hashes":{}}},
        "reference_bindings":{"plan":{"source_rows":plan["prefix_rows"]},"run":{"status":"Completed"},
                              "verification":{"status":"Passed","diagnostic_completed":True,"safety":{"gate_passed":True},"source_hashes":{}},"results":reference},
    }
    for group,number,constant in (("parent_bindings","083","PARENT_HASHES"),("reference_bindings","082","REFERENCE_HASHES")):
        bindings,hashes={},{}
        for name,value in documents[group].items():
            path=root/f"private/validation/exp-{number}/attempt-1"/(name+(".jsonl" if name=="results" else ".json"))
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(encoded(value) if name=="results" else json.dumps(value).encode())
            hashes[name]=VERIFY.regular_file(path)
            bindings[name]={"path":str(path.relative_to(root)),"sha256":hashes[name]}
        monkeypatch.setattr(VERIFY,constant,hashes)
        plan[group]=bindings
    protocol=root.parent/VERIFY.PROTOCOL
    protocol.parent.mkdir(parents=True)
    protocol.write_text("# Synthetic EXP084 protocol\n")
    plan.update(source_plan_binding=binding,sources={name:VERIFY.regular_file(root/name) for name in VERIFY.ADDITIONAL_SOURCES|{frozen}},
                protocol={"path":VERIFY.PROTOCOL,"sha256":VERIFY.regular_file(protocol)})
    with sqlite3.connect(root/"private/jobs.sqlite3") as db:
        db.execute("CREATE TABLE jobs (id TEXT,state TEXT,snapshot_hash TEXT,total_items INTEGER)")
        db.execute("CREATE TABLE items (job_id TEXT,ordinal INTEGER,record TEXT,result TEXT)")
        db.execute("INSERT INTO jobs VALUES (?,?,?,?)",(VERIFY.SOURCE_JOB,"completed",VERIFY.SOURCE_SNAPSHOT,340))
        for row in source:
            db.execute("INSERT INTO items VALUES (?,?,?,?)",(VERIFY.SOURCE_JOB,row["ordinal"],json.dumps(row["record"]),json.dumps(row["result"])))
        db.execute("INSERT INTO items VALUES (?,?,?,?)",("unrelated",0,"NOT JSON","NOT JSON"))
    service.update(root=str(root),bench_root=str(target/"bench"))
    (target/"plan.json").write_text(json.dumps(plan))
    plan_hash=VERIFY.regular_file(target/"plan.json")
    claim={"experiment_id":"EXP-084","attempt":1,"tier":"Minor","rq":"RQ-S3","cwd":str(root),
           "started_at":run["started_at"],"started_monotonic":0.,"plan_sha256":plan_hash,"environment":{},
           "git_commit":"synthetic","git_status_porcelain":[],"command":["fixture"],
           "training":False,"gold_accessed":False,"source_network_fetched":False}
    for name,value in (("service.json",service),("run-claim.json",claim),("transfer.json",transfer),("m3-ready.json",proof)):
        if value is not None: (target/name).write_text(json.dumps(value))
    for name,rows in (("m1-results.jsonl",prelude),("replay-results.jsonl",replay),("samples.jsonl",samples),("process-events.jsonl",events)):
        (target/name).write_bytes(encoded(rows))
    (target/"stages.jsonl").write_bytes(stages)
    (target/"stdout.log").write_text("Synthetic transfer log.\n")
    run.update(plan_sha256=plan_hash,source_hashes={str((target/name).relative_to(root)):VERIFY.regular_file(target/name)
               for name in (*VERIFY.ARTIFACTS,*VERIFY.OPTIONAL_ARTIFACTS) if name!="run.json" and (target/name).exists()})
    (target/"run.json").write_text(json.dumps(run))
    return target


@pytest.mark.parametrize("state",["complete","research_cancelled","prelude_cancelled","initial_quiet_fail","research_quiet_fail","critical_after_prelude","constructor_failed"])
def test_cli_full_partial_and_optional_absence_are_create_only(tmp_path,monkeypatch,state):
    target=cli_fixture(tmp_path,monkeypatch,state)
    before={path.name:path.read_bytes() for path in target.iterdir()}
    assert VERIFY.main()==0
    result=json.loads((target/"verification.json").read_text())
    assert result["status"]=="Passed" and result["diagnostic_completed"] is (state=="complete")
    assert result["planned_events"]==347 and result["models_loaded"] is False
    assert all((target/name).read_bytes()==value for name,value in before.items())
    assert (target/"verification.json").stat().st_mode&0o777==0o600
    with pytest.raises(ValueError,match="verification_exists_or_symlink"): VERIFY.main()


def test_cli_source_hash_drift_is_failed_audit_not_repaired(tmp_path,monkeypatch):
    target=cli_fixture(tmp_path,monkeypatch,"complete")
    with (target/"transfer.json").open("ab") as output: output.write(b" ")
    assert VERIFY.main()==1
    result=json.loads((target/"verification.json").read_text())
    assert result["status"]=="Failed" and result["error_code"]=="artifact_hash_binding"
