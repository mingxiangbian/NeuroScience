"""Synthetic EXP-086 source, staged semantics, parent and stop regressions."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import tarfile
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("exp086_checker_tested", ROOT / "scripts/verify_staged_discourse_formal.py")
V = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(V)
OLD_SPEC = importlib.util.spec_from_file_location("exp086_source_fixture", ROOT / "tests/test_discourse_validation.py")
OLD = importlib.util.module_from_spec(OLD_SPEC); OLD_SPEC.loader.exec_module(OLD)
PRODUCER_SPEC = importlib.util.spec_from_file_location("exp086_producer_roundtrip", ROOT / "scripts/run_staged_discourse_formal.py")
PRODUCER = importlib.util.module_from_spec(PRODUCER_SPEC); PRODUCER_SPEC.loader.exec_module(PRODUCER)


def router():
    return {"labels": list(V.LOCAL.LABELS), "features": V.STAGED.FEATURES, "classes": [0, 1],
            "scaler_mean": [.5] + [0] * 13, "scaler_scale": [1] * 14, "coef": [4] + [0] * 13,
            "intercept": 0, "m1_threshold": .31, "m3_threshold": .31, "cutoff": .5,
            "base_fingerprint": "f" * 64}


def test_real_producer_prepare_plan_roundtrips_consumer_contract(monkeypatch):
    import run_soak
    parent = {"plan": {"sources": {}, "model_config": {"path": "config", "sha256": "a" * 64},
                       "router_assets": {"bundle_manifest": {}, "bundle_parameters": {}}}}
    monkeypatch.setattr(PRODUCER, "parent_gate", lambda: (parent, {"plan": {}, "run": {}, "verification": {}, "archive": {}}))
    monkeypatch.setattr(PRODUCER, "dependencies", lambda _: {})
    monkeypatch.setattr(run_soak, "environment_metadata", lambda: {"synthetic": True})
    plan, environment = PRODUCER.prepare()
    assert V.check_plan_contract(plan) and environment == {"synthetic": True}


def test_real_producer_resource_block_roundtrips_empty_stopped_consumer(tmp_path):
    class API:
        def __call__(self, *args, **kwargs): raise AssertionError("must not POST")
    class Journal:
        def report(self, value): pass
    outcome = PRODUCER.execute(API(), lambda: [], lambda _: None, Journal(), time.monotonic()+10, tmp_path,
                               blocked=lambda: "critical_memory_pressure")
    assert outcome["logical_jobs"] == []
    plan = {"experiment_id":"EXP-086","attempt":1,"tier":"Minor","rq":"RQ-S3","query":V.QUERY,"mode":"research",
            "max_qwen_calls":500,"audit_rate":0,"seed":42,"planned_jobs":1,"planned_records_min":300,"planned_records_max":400,
            "max_seconds":3600,"work_seconds":3570,"cleanup_seconds":15,"port":8790,
            "runtime_environment":{"TOPICWEB_TELEMETRY":"1"},"scope":"source_and_local_system_closure_without_external_gold"}
    run = {"experiment_id":"EXP-086","attempt":1,"tier":"Minor","planned_jobs":1,"status":"Stopped",
           "failure_code":outcome["failure_code"],"started_monotonic":0.,"ended_monotonic":1.,"elapsed_seconds":1.,
           "total_budget_exceeded":False,"logical_jobs":[],"phases":[],"training":False,"gold_accessed":False,
           "source_network_authorized":True,"source_network_attempted":False,"source_network_fetched":False,"source_response_count":0}
    checked = V.analyze(plan,run,{}, {},[],[],[],[],[],[],{},router())
    assert not checked["exp086_complete"] and checked["source"]["status"]=="not_observed"
    run["logical_jobs"]=[{"id":None,"status":"submission_unconfirmed","mode":"research","budget":500}]
    with pytest.raises(V.B.VerificationError,match="bench_job_binding"):
        V.analyze(plan,run,{}, {},[],[],[],[],[],[],{},router())


def receipts(records, mode):
    rows, seen_m1, seen_m3 = [], set(), set()
    totals = {name: 0 for name in V.STAGED.COSTS}
    for ordinal, record in enumerate(records):
        group = int(record["model_input_text"].split()[-1])
        eligible = group < 6
        p1 = [.75 if eligible else .125, .25, .375, .125, .25, .375]
        p3 = [.25, .75, .125, .375, .25, .125] if eligible and mode == "m3" else None
        exact = record["model_input_hash"]
        counters = {name: 0 for name in totals}
        if mode == "m1":
            counters.update(m1_attempts=int(exact not in seen_m1), m1_cache_hit=int(exact in seen_m1)); seen_m1.add(exact)
        else:
            counters["m1_cache_hit"] = 1
            if eligible:
                counters.update(m3_attempts=int(exact not in seen_m3), m3_succeeded=int(exact not in seen_m3),
                                m3_cache_hit=int(exact in seen_m3)); seen_m3.add(exact)
        totals = {name: totals[name] + counters[name] for name in totals}
        m1d, m3d = [int(value >= .31) for value in p1], [int(value >= .31) for value in p3] if p3 else None
        selected = m3d if m3d is not None else m1d; labels = [label for label, bit in zip(V.LOCAL.LABELS, selected) if bit]
        route = V.STAGED.recompute_route(p1, len(record["model_input_text"]),
                                         {"input_tokens": 12, "used_tokens": 12, "truncated": False}, router())
        result = {"prediction": selected, "prediction6": selected, "active_labels": labels, "labels": labels,
            "neutral": not labels, "used_path": "m3" if eligible and mode == "m3" else "m1",
            "actual_model": "m3" if eligible and mode == "m3" else "m1", "route_requested": eligible and mode == "m3",
            "route_eligible": eligible, "routed": eligible and mode == "m3", "hypothetical_route": eligible,
            "fallback": False, "fallback_reason": None, "degraded": False, "m1_probabilities": p1,
            "m3_probabilities": p3 if mode == "m3" else None, "m1_prediction": m1d, "m3_prediction": m3d if mode == "m3" else None,
            "route_score": route["score"], "m1_entropy": route["features"][6], "threshold_margin": route["features"][8],
            "tokenlengths": {"m1": {"input_tokens": 12, "used_tokens": 12, "truncated": False},
                             "m3": {"input_tokens": 20, "used_tokens": 20, "truncated": False} if eligible and mode == "m3" else None},
            "truncflags": {"m1": False, "m3": False if eligible and mode == "m3" else None},
            "counters": {**counters, "fallback_reason": None}, "cumulative_counters": dict(totals),
            "cache_hit": bool(counters["m1_cache_hit"] and (not (eligible and mode == "m3") or counters["m3_cache_hit"])),
            "m3_attempted": bool(counters["m3_attempts"]), "m3_succeeded": bool(counters["m3_succeeded"]),
            "audit_extra_calls": 0, "latency_ms": 1., "resources": {"peak_rss_bytes": 1024, "mlx_peak_bytes": 2048 if mode == "m3" else 0, "elapsed_seconds": 1.},
            "fingerprint": "f" * 64}
        if mode == "m3": result.update(prelude_transfer_reuse=True, m1_execution_origin="current_job_m1_receipt")
        rows.append({"logical_job_id": OLD.ID, "phase_id": OLD.ID + ":" + mode, "ordinal": ordinal,
                     "input_sha256": exact, "result": result})
    return rows


def source_fixture(count=300):
    _, old_job = OLD.fixture()
    records = copy.deepcopy([row["record"] for row in old_job["items"]][:count])
    for ordinal in range(len(records), count):
        topic, number, identifier = 96 - (ordinal - 300) // 75, (ordinal - 300) % 75 + 1, 10000 + ordinal
        group = ordinal % 17; text = f"synthetic raw {group}"; hashed = V.sha(text)
        raw = {"id":identifier,"topic_id":topic,"post_number":number,"post_type":1,"raw":text,
               "created_at":"2026-08-10T00:00:00Z","username":"fixture_user","user_id":12,
               "reply_to_post_number":number-1 if number>1 else None}
        identity=["discourse","discuss.python.org","post",str(identifier)]
        records.append({"source":"discourse","site":"discuss.python.org","object_type":"post","source_object_id":str(identifier),
            "record_id":V.sha(json.dumps(identity,ensure_ascii=False,separators=(",",":"))),"model_input_text":text,"model_input_hash":hashed,
            "dedup_hash":V.sha(text),"source_payload_raw":raw,"thread_id":str(topic),
            "parent_object_id":str(identifier-1) if number>1 else None,"source_url":f"https://discuss.python.org/t/{topic}/{number}",
            "created_at":raw["created_at"],"author_display_name":"fixture_user","content_license":"CC BY-NC-SA 3.0",
            "provenance":{"category_id":7,"topic_id":topic,"post_number":number,"reply_to_post_number":raw["reply_to_post_number"],
                "text_field":"raw","author_username":"fixture_user","license_url":"https://creativecommons.org/licenses/by-nc-sa/3.0/",
                "source_policy_url":"https://discuss.python.org/tos"}})
    manifest = copy.deepcopy(old_job["manifest"])
    manifest.update(record_count=count, source_link_count=count, fetched_post_count=count)
    manifest["topic_ids"] = [100,99,98,97,96,95][:1 + (count-1)//75]
    manifest["selected_topic_count"] = len(manifest["topic_ids"])
    if count == 400:
        manifest.update(stop_reason="item_limit")
    if count < 300:
        manifest["observed_created_at_min"] = manifest["observed_created_at_max"] = records[0]["created_at"] if records else None
    return records, manifest


def transfer(prelude):
    value = {"base_fingerprint": "f" * 64, "entries": [{"ordinal": row["ordinal"], "input_sha256": row["input_sha256"],
        "m1_probabilities": row["result"]["m1_probabilities"], "tokenlengths": {"m1": row["result"]["tokenlengths"]["m1"]}}
        for row in prelude]}
    return {"logical_job_id": OLD.ID, "phase_id": OLD.ID + ":m3", "transfer": value,
            "transfer_sha256": V.sha(V.LOCAL.canonical(value)), "m1_receipts_sha256": V.STAGED.receipt_digest(prelude)}


def test_source_native_raw_license_order_and_manifest():
    records, manifest = source_fixture()
    result = V.SOURCE.check_source(records, manifest)
    assert result["records"] == 300 and result["source_link_coverage"] == 1.
    records[0]["content_license"] = "CC0"
    with pytest.raises((V.LOCAL.VerificationError, V.SOURCE.LOCAL.VerificationError), match="source_attribution"):
        V.SOURCE.check_source(records, manifest)


def test_staged_cost_transfer_and_eligible_duplicate_cache():
    records, _ = source_fixture()
    first, second = receipts(records, "m1"), receipts(records, "m3")
    m1 = V.STAGED.recompute_cost(records, first, mode="m1_only", budget=0, phase="m1", complete=True)
    m3 = V.STAGED.recompute_cost(records, second, mode="research", budget=500, phase="m3", complete=True)
    assert m1["accounting"]["actual_m1_forward_attempts"] == 17
    assert m1["accounting"]["within_phase_duplicate_cache_hits"] == 283
    assert m3["accounting"]["prelude_transfer_reuse"] == 300
    assert m3["accounting"]["m3_attempts"] == 6 and m3["accounting"]["m3_cache_hits"] > 0
    info = V.check_transfer(transfer(first), first, OLD.ID)
    assert info["items"] == 300 and info["cache_entries"] == 17


@pytest.mark.parametrize("count,status,has_phase", [(400, "accepted", True), (250, "rejected_before_model", False), (0, "rejected_before_model", False)])
def test_source_count_gate_roundtrip(count, status, has_phase):
    phase = [{"type": "phase_started", "started_monotonic": 12.}] if has_phase else []
    processes = [{"type": "constructor_started"}] if has_phase else []
    rows = []
    if count:
        rows.extend([{"logical_job_id": OLD.ID, "monotonic": 8., "stage": "collecting", "source_stage": "request_started"},
                     {"logical_job_id": OLD.ID, "monotonic": 9., "stage": "collecting", "source_stage": "response_received"}])
    rows.append({"logical_job_id": OLD.ID, "monotonic": 10., "stage": "source_count_gate", "record_count": count, "status": status})
    run = {"status": "Completed" if has_phase else "Stopped", "source_network_authorized": True,
           "source_network_attempted": bool(count), "source_network_fetched": bool(count), "source_response_count": int(bool(count))}
    result = V.check_source_progress(rows, OLD.ID, run, phase, processes)
    assert result["record_count"] == count and result["rejected_before_model"] is (not has_phase)


@pytest.mark.parametrize("count,status", [(400, "accepted"), (250, "rejected_before_model"), (0, "rejected_before_model")])
def test_real_producer_gate_events_roundtrip_into_consumer(count, status):
    from topicweb.adapters import SourceError
    class Journal:
        def __init__(self): self.rows = []
        def source_progress(self, value): self.rows.append(value)
    journal = Journal()
    def fetch(request, *, cancelled, progress):
        if count == 0:
            raise SourceError("private synthetic failure", metadata={"stage": "http", "record_count": 0})
        progress({"stage": "collecting", "source_stage": "request_started", "record_count": 0})
        progress({"stage": "collecting", "source_stage": "response_received", "record_count": count})
        return [{}] * count, {"record_count": count}
    gated = PRODUCER.gate_fetch(journal, lambda: OLD.ID, fetch)
    if status == "accepted":
        records, _ = gated(PRODUCER.QUERY, cancelled=lambda: False, progress=lambda _: None)
        assert len(records) == count
    else:
        with pytest.raises(SourceError):
            gated(PRODUCER.QUERY, cancelled=lambda: False, progress=lambda _: None)
    attempted, fetched = count > 0, count > 0
    run = {"status": "Completed" if status == "accepted" else "Stopped", "source_network_authorized": True,
           "source_network_attempted": attempted, "source_network_fetched": fetched, "source_response_count": int(fetched)}
    phase = [{"type": "phase_started", "started_monotonic": journal.rows[-1]["monotonic"] + 1}] if status == "accepted" else []
    processes = [{"type": "constructor_started"}] if status == "accepted" else []
    checked = V.check_source_progress(journal.rows, OLD.ID, run, phase, processes)
    assert checked["status"] == status and checked["request_started_count"] == int(attempted)
    assert checked["response_received_count"] == int(fetched)
    if count == 250:
        database_items = []  # gate_fetch raised before Store.seal can receive records
        assert checked["record_count"] == 250 and database_items == []


def test_source_error_after_in_range_count_is_still_rejected_before_model():
    from topicweb.adapters import SourceError
    class Journal:
        def __init__(self): self.rows=[]
        def source_progress(self,value): self.rows.append(value)
    journal=Journal()
    def failed(request,*,cancelled,progress):
        progress({"stage":"collecting","source_stage":"request_started","record_count":0})
        progress({"stage":"collecting","source_stage":"response_received","record_count":350})
        raise SourceError("private synthetic failure",metadata={"stage":"http","record_count":350})
    with pytest.raises(SourceError):
        PRODUCER.gate_fetch(journal,lambda:OLD.ID,failed)(PRODUCER.QUERY,cancelled=lambda:False,progress=lambda _:None)
    run={"status":"Stopped","source_network_authorized":True,"source_network_attempted":True,
         "source_network_fetched":True,"source_response_count":1}
    checked=V.check_source_progress(journal.rows,OLD.ID,run,[],[])
    assert checked["status"]=="rejected_before_model" and checked["record_count"]==350


def test_completed_progress_requires_one_load_and_each_unique_forward():
    records, _ = source_fixture()
    second = receipts(records, "m3")
    eligible = []
    seen = set()
    for row in second:
        if row["result"]["hypothetical_route"] and row["input_sha256"] not in seen:
            eligible.append(row["ordinal"]); seen.add(row["input_sha256"])
    events = []
    for index, ordinal in enumerate(eligible):
        for stage in (["m3_load", "m3_forward"] if index == 0 else ["m3_forward"]):
            for kind in ("begin", "end"):
                counters = {name: 0 for name in V.STAGED.COSTS}; counters.update(m1_cache_hit=ordinal+1,m3_attempts=index+1,m3_succeeded=index)
                events.append({"type":"staged_progress","phase_id":OLD.ID+":m3","stage":stage,"kind":kind,"ordinal":ordinal,
                               "cumulative_counters":counters,"resources":{"peak_rss_bytes":1,"mlx_peak_bytes":1}})
    phase = {"id": OLD.ID+":m3", "status":"completed"}
    summary = V.check_progress(events, phase, second, [row["result"] for row in second])
    assert summary["m3_load_spans"] == 1 and summary["m3_forward_spans"] == 6
    events.pop(1)
    with pytest.raises(V.B.VerificationError): V.check_progress(events, phase, second, [row["result"] for row in second])


def monitored(prelude, replay):
    service = {"pid":100,"ppid":1,"current_rss_bytes":1024**2,"start_time":"Mon Sep 1 10:00:00 2026",
               "process_key":"100|Mon Sep 1 10:00:00 2026","comm":"Python","experiment_id":"EXP-086","attempt":1,
               "root":str(ROOT),"bench_root":str(ROOT/"private/validation/exp-086/attempt-1/bench"),"port":8790}
    samples, events, phases, runtime, seen = [], [], [], [], set()
    def proc(pid):
        return {"pid":pid,"ppid":100,"current_rss_bytes":1024**2,"start_time":"Mon Sep 1 10:00:00 2026",
                "process_key":f"{pid}|Mon Sep 1 10:00:00 2026","comm":"Python"}
    def raw(row): return f"{row['pid']} {row['ppid']} 1024 {row['start_time']} /usr/bin/Python"
    def sample(models=(),phase=None):
        index=len(samples); clock=index*1.2; live={row["process_key"] for row in models};seen.update(live)
        samples.append({"index":index,"job_id":phase,"logical_job_id":OLD.ID,"started_monotonic":clock,"monotonic":clock+.2,
            "system":{"status":"observed","monotonic":clock+.1,"pressure_level":1,"pressure_raw":"1\n","page_size":4096,
                      "swapins":1,"swapouts":2,"vm_stat_raw":"Mach Virtual Memory Statistics: (page size of 4096 bytes)\nSwapins: 1.\nSwapouts: 2.\n"},
            "disk_free_bytes":1024**3,"processes":{"status":"observed","parent":{key:service[key] for key in
                ("pid","ppid","current_rss_bytes","start_time","process_key","comm")},"models":list(models),"orphan_models":[],
                "seen_model_keys":sorted(seen),"absent_model_keys":sorted(seen-live),"selected_ps":[raw(service),*(raw(row) for row in models)]}})
        return index
    sample()
    for number,(stage,rows) in enumerate((("m1",prelude),("m3",replay))):
        phase_id=OLD.ID+":"+stage;ready_start=samples[-1]["monotonic"]+.01;indices=[sample() for _ in range(10)]
        ready_end=samples[-1]["monotonic"]+.005;start=ready_end+.01;model=proc(201+number)
        ready={"type":"ready","fingerprint":"f"*64,"modelstatus":{"m1":"loaded","m3":"not_loaded","mode":"m1_only"},
               "cache_scope":"job_exact_input_components","audit_rate":0}
        if stage=="m3":
            info=V.check_transfer(transfer(prelude),prelude,OLD.ID)
            ready={"type":"ready","fingerprint":info["fingerprint"],"base_fingerprint":info["base_fingerprint"],
                   "transfer_sha256":info["transfer_sha256"],"transfer_items":info["items"],"cache_entries":info["cache_entries"],
                   "strategy":V.STAGED.STRATEGY,"m1_instance_absent":True,
                   "modelstatus":{"m1":"receipt_replay_not_loaded","m3":"not_loaded","mode":"research"},
                   "cache_scope":"job_m1_receipt_transfer","audit_rate":0}
            for row in rows: row["result"]["fingerprint"]=info["fingerprint"]
        def event(kind,when,code=None):
            value={"type":kind,"logical_job_id":OLD.ID,"phase_id":phase_id,"job_id":phase_id,
                   "pid":None if kind=="constructor_started" else model["pid"],"process_key":None if kind=="constructor_started" else model["process_key"],
                   "returncode":code,"normal_exit":kind=="final_gate_passed","monotonic":when}
            if kind=="ready":value["ready"]=ready
            events.append(value)
        event("constructor_started",start+.01);event("ready",start+.05);sample([model],phase_id);sample([model],phase_id)
        exit_time=samples[-1]["monotonic"]+.05;event("process_exit",exit_time,0);event("final_gate_passed",exit_time+.01,0);absent=sample()
        for row in rows:
            row["result"]["telemetry"]={"status":"observed","monotonic":start+.2+row["ordinal"]*.0001,
                "child_pid":model["pid"],"parent_pid":100,"child_current_rss_bytes":1024**2,"parent_current_rss_bytes":1024**2,
                "raw_ps":f"{model['pid']} 1024\n100 1024\n"}
        phase={"id":phase_id,"phase_id":phase_id,"logical_job_id":OLD.ID,"phase":stage,"mode":"m1_only" if stage=="m1" else "research",
               "status":"completed","total_items":len(rows),"completed_items":len(rows),"normal_exit":True,"cost_complete":True,
               "started_monotonic":start,"ended_monotonic":samples[-1]["monotonic"]+.005,"readiness_started_monotonic":ready_start,
               "readiness_ended_monotonic":ready_end,"readiness_indices":indices,
               "exit_observation":{"sample_index":absent,"absent_model_keys":sorted(seen)}}
        phases.append(phase);runtime.append({"type":"phase_terminal",**phase})
    return service,samples,events,phases,runtime


def full_bundle(count=300):
    records,manifest=source_fixture(count);prelude,replay=receipts(records,"m1"),receipts(records,"m3")
    service,samples,events,phases,runtime=monitored(prelude,replay)
    eligible=[];seen=set()
    for row in replay:
        if row["result"]["hypothetical_route"] and row["input_sha256"] not in seen:eligible.append(row["ordinal"]);seen.add(row["input_sha256"])
    for index,ordinal in enumerate(eligible):
        for stage in (["m3_load","m3_forward"] if index==0 else ["m3_forward"]):
            for kind in ("begin","end"):
                counters={name:0 for name in V.STAGED.COSTS};counters.update(m1_cache_hit=ordinal+1,m3_attempts=index+1,m3_succeeded=index)
                runtime.append({"type":"staged_progress","logical_job_id":OLD.ID,"phase_id":OLD.ID+":m3","stage":stage,"kind":kind,
                                "ordinal":ordinal,"cumulative_counters":counters,"resources":{"peak_rss_bytes":1,"mlx_peak_bytes":1}})
    physical=dict(prelude[-1]["result"]["cumulative_counters"])
    for name in V.STAGED.COSTS:
        if name not in {"m1_attempts","m1_cache_hit"}:physical[name]=replay[-1]["result"]["cumulative_counters"][name]
    final=[]
    for ordinal,(record,first,second) in enumerate(zip(records,prelude,replay)):
        value=copy.deepcopy(second["result"]);value["staged_raw_counters"]=dict(value["counters"])
        value["staged_counter_scope"]="physical_job_cumulative";value["staged_latency_scope"]="phase_response_only_m1_prepass_excluded"
        for key in ("m1_attempts","m1_cache_hit"):value["counters"][key]=first["result"]["counters"][key]
        for key in ("m1_attempts","m1_cache_hit"):
            value["cumulative_counters"][key]=physical[key]
        value["cache_hit"]=bool(first["result"]["counters"]["m1_cache_hit"] and
                                (not value["route_requested"] or value["staged_raw_counters"]["m3_cache_hit"]))
        final.append({"ordinal":ordinal,"record":record,"result":value})
    progress={"staged_execution":{"strategy":V.STAGED.STRATEGY,"stage":"completed","phase_id":OLD.ID+":m3",
              "phase_completed_items":count,"phase_total_items":count,"cumulative_counters":physical,"prelude_transfer_reuses":count,
              "cost_complete":True,"cost_scope":"completed_job","unacknowledged_attempts":0}}
    result_values=[row["result"] for row in final]
    dashboard=V.B.recalculate_aggregate(records,result_values,"research",physical);dashboard["derived"]=V.B.DERIVED.recalculate_derived(records,result_values)
    dashboard["routing"].update(cost_scope="staged_job_cumulative",cost_complete=True,prelude_transfer_reuses=count)
    job={"id":OLD.ID,"source":"discourse","mode":"research","state":"completed","error_code":None,"total_items":count,"completed_items":count,
         "snapshot_hash":V.LOCAL.check_records(records),"manifest":manifest,"request":{"source":"discourse","mode":"research","max_qwen_calls":500,
         "audit_rate":0,"seed":42,"query":V.QUERY},"progress":progress,"dashboard":dashboard,"items":final}
    logical={"id":OLD.ID,"mode":"research","budget":500,"status":"completed","completed_items":count,"total_items":count}
    run={"experiment_id":"EXP-086","attempt":1,"tier":"Minor","planned_jobs":1,"status":"Completed","failure_code":None,
         "started_monotonic":0.,"ended_monotonic":samples[-1]["monotonic"]+.1,"elapsed_seconds":samples[-1]["monotonic"]+.1,
         "total_budget_exceeded":False,"logical_jobs":[logical],"phases":phases,"training":False,"gold_accessed":False,
         "source_network_authorized":True,"source_network_attempted":True,"source_network_fetched":True,"source_response_count":1}
    plan={"experiment_id":"EXP-086","attempt":1,"tier":"Minor","rq":"RQ-S3","query":V.QUERY,"mode":"research","max_qwen_calls":500,
          "audit_rate":0,"seed":42,"planned_jobs":1,"planned_records_min":300,"planned_records_max":400,"max_seconds":3600,
          "work_seconds":3570,"cleanup_seconds":15,"port":8790,"runtime_environment":{"TOPICWEB_TELEMETRY":"1"},
          "scope":"source_and_local_system_closure_without_external_gold"}
    source_progress=[{"logical_job_id":OLD.ID,"monotonic":1.,"stage":"collecting","source_stage":"request_started"},
                     {"logical_job_id":OLD.ID,"monotonic":2.,"stage":"collecting","source_stage":"response_received"},
                     {"logical_job_id":OLD.ID,"monotonic":3.,"stage":"source_count_gate","record_count":count,"status":"accepted"}]
    return [plan,run,service,{OLD.ID:job},[*prelude,*replay],[transfer(prelude)],samples,events,runtime,source_progress,{OLD.ID:dashboard},router()]


@pytest.mark.parametrize("count",[300,340,400])
def test_complete_and_stopped_consumer_outcomes(count):
    bundle=full_bundle(count);result=V.analyze(*bundle)
    assert result["exp086_complete"] and result["safety"]["gate_passed"] and result["jobs"][0]["records"]==count
    assert result["jobs"][0]["final"]["acknowledged_items"]==count
    assert result["jobs"][0]["dashboard"]["count"]==count
    stopped=full_bundle();stopped[1].update(status="Stopped",failure_code="synthetic_stop");stopped[1]["logical_jobs"][0]["status"]="cancelled"
    assert not V.analyze(*stopped)["exp086_complete"]


def test_complete_consumer_reads_only_selected_temp_database_job(tmp_path):
    bundle=full_bundle(300); job=next(iter(bundle[3].values())); database=tmp_path/"jobs.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE jobs(id,source,mode,state,error_code,raw_expired,items_expired,total_items,completed_items,snapshot_hash,request,progress,manifest,dashboard)")
        connection.execute("CREATE TABLE items(job_id,ordinal,record,result)")
        connection.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(job["id"],job["source"],job["mode"],job["state"],job["error_code"],0,0,
            job["total_items"],job["completed_items"],job["snapshot_hash"],json.dumps(job["request"]),json.dumps(job["progress"]),json.dumps(job["manifest"]),json.dumps(job["dashboard"])))
        for row in job["items"]:
            connection.execute("INSERT INTO items VALUES(?,?,?,?)",(job["id"],row["ordinal"],json.dumps(row["record"]),json.dumps(row["result"])))
        connection.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",("e"*32,"upload","m1_only","failed",None,0,0,0,0,None,"{}","{}","{}",None))
    selected=V.SOURCE.read_selected_job(database,job["id"])
    bundle[3]={job["id"]:selected}
    assert V.analyze(*bundle)["exp086_complete"]


def test_real_parent085_pass_and_archive_binding_is_not_optional():
    previous={name:{"path":f"private/validation/exp-085/attempt-2/{name}.json","sha256":value}
              for name,value in V.PARENT_HASHES.items()}
    previous["archive"]={"path":"private/validation/exp-085/attempt-2/frozen-code.tar.gz",
                         "sha256":V.PARENT_ARCHIVE_SHA256,"members":33}
    summary,parent_plan=V.check_parent({"parent_exp085":previous})
    assert summary["exp085_complete"] and summary["safety_gate_passed"] and len(parent_plan["sources"])==32
    previous["run"]["sha256"]="0"*64
    with pytest.raises(V.B.VerificationError,match="parent_artifact_binding"):
        V.check_parent({"parent_exp085":previous})
