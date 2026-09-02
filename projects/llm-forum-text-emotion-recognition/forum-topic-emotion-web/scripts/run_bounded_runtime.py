"""EXP-079: nine new HTTP snapshot jobs under explicit bounded-use conditions."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sqlite3
import statistics
import subprocess
import sys
import time
from urllib.request import Request, urlopen

from bounded_runtime_support import (
    ROOT, DEPENDS, Monitor, SupportError, cancel_and_confirm, canonical, digest,
    environment_metadata, load_service, now, once, read_job, require, serve_app,
    wait_absent, wait_ready,
)

RUN = ROOT / "private/validation/exp-079/attempt-3"
BENCH = RUN / "bench"
PROTOCOL = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-079-bounded-runtime-acceptance.md"
DECISION = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/dec-phase-c1-bounded-operational-validation-v1.md"
CORRECTION = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-079-observer-correction-attempt-2.md"
REDUCED_BACKGROUND = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-079-reduced-background-attempt-3.md"
PREVIOUS_ARCHIVE_SHA = "bbb4237c55548df50a00ac5687a1b6f382ce03d8cf7d6a669d709a7c20b7b281"
PREVIOUS_VERIFICATION_SHA = "f3ab1b94efbc1333b3f04c5e094658dd7b1d9b84dba35adf7bb7c68887c373c4"
SOURCE_JOB = "5ab3326150ee448ba326233264967d34"
SOURCE_SNAPSHOT = "cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16"
SOURCE_VERIFICATION = "7138c80740eed3cda2f646f9061ae345c44ae8dec749daae1bd0505c61cadff8"
MODES = ("m1_only","research","demo")
COSTS = ("m1_attempts","m3_attempts","m3_succeeded","m1_cache_hit","m3_cache_hit","audit_extra_calls")


def error_counts(jobs,driver_errors):
    worker_errors=sum(job.get("error_code")=="worker_failed" for job in jobs)
    return {"unhandled_errors":driver_errors+worker_errors,"driver_unhandled_errors":driver_errors,"worker_unhandled_errors":worker_errors}


def known_job_ids(database):
    with sqlite3.connect(Path(database).as_uri()+"?mode=ro",uri=True,timeout=1) as db:
        return {row[0] for row in db.execute("SELECT id FROM jobs")}


def recover_unacknowledged_submission(database,known,mode,payload_hash,name):
    """Identify only the unique matching new row, solely to cancel it; never POST again."""
    with sqlite3.connect(Path(database).as_uri()+"?mode=ro",uri=True,timeout=1) as db:
        db.row_factory=sqlite3.Row
        candidates=[dict(row) for row in db.execute("SELECT id,name,source,mode,total_items,manifest,state FROM jobs") if row["id"] not in known]
    result={"status":"unconfirmed","candidate_count":len(candidates)}
    if len(candidates)!=1:
        return result
    row=candidates[0]
    try:
        manifest=json.loads(row["manifest"])
        matches=(row["source"]=="upload" and row["mode"]==mode and row["name"]==name and row["total_items"]==340
                 and manifest["file_sha256"]==payload_hash and manifest["filename"]=="exp079-snapshot.jsonl")
    except (TypeError,ValueError,KeyError):
        matches=False
    if matches:
        result.update(status="identified_for_cancellation",id=row["id"],mode=row["mode"],state=row["state"])
    return result


def make_plan(rows):
    require(len(rows) == 340 and [row["ordinal"] for row in rows] == list(range(340)), "source_ordinal_contract")
    source_rows, lines = [], []
    for row in rows:
        text, result = row["record"]["model_input_text"], row["result"]
        require(digest(text) == row["record"]["model_input_hash"] and type(result["hypothetical_route"]) is bool, "source_input_contract")
        source_rows.append({"ordinal":row["ordinal"],"input_sha256":digest(text),"route_eligible":result["hypothetical_route"]})
        lines.append(canonical({"id":f"source-{row['ordinal']}","text":text}))
    require(len({row["input_sha256"] for row in source_rows}) == 338 and sum(row["route_eligible"] for row in source_rows) == 25
            and len({row["input_sha256"] for row in source_rows if row["route_eligible"]}) == 25, "source_fixture_identity")
    content = "\n".join(lines)+"\n"
    require(len(content.encode()) <= 5*1024**2, "payload_budget")
    return {"experiment_id":"EXP-079","attempt":3,"source_job":SOURCE_JOB,"source_snapshot_sha256":SOURCE_SNAPSHOT,
            "source_verification_sha256":SOURCE_VERIFICATION,"source_rows":source_rows,
            "source_logical_sha256":digest(canonical(rows)),"payload_sha256":digest(content),
            "rounds":3,"modes":list(MODES),"planned_jobs":9,"events_per_job":340,"planned_events":3060,
            "max_seconds":1800,"max_readiness_seconds":60,"readiness_samples":10}, content


def summarize(rows):
    require(len(rows)==340 and all(isinstance(row["result"],dict) for row in rows),"incomplete_results")
    values = [row["result"] for row in rows]
    require(all(value.get("fallback_reason") in (None,"m3_budget_exhausted") for value in values),"model_runtime_failure")
    require(all(len(value.get("prediction",[]))==6 and all(type(bit)is int and bit in (0,1) for bit in value["prediction"]) for value in values),"invalid_schema")
    latency = sorted(value["latency_ms"] for value in values)
    require(all(type(value) in (int,float) and math.isfinite(value) and value>=0 for value in latency),"invalid_latency")
    def q(probability):
        index=(len(latency)-1)*probability; lower=int(index)
        return latency[lower]+(latency[min(lower+1,len(latency)-1)]-latency[lower])*(index-lower)
    child=[value["telemetry"]["child_current_rss_bytes"] for value in values]
    parent=[value["telemetry"]["parent_current_rss_bytes"] for value in values]
    require(all(value["telemetry"]["status"]=="observed" for value in values),"receipt_rss_unknown")
    peak_reported=max(value["resources"]["peak_rss_bytes"] for value in values)
    mlx=max(value["resources"]["mlx_peak_bytes"] for value in values)
    require(max(child)<=12*1024**3 and peak_reported<=12*1024**3 and max(parent)<=1024**3 and mlx<=10_000_000_000,"resource_limit")
    return {"events":340,"schema_valid":340,"cost":{key:sum(value["counters"][key] for value in values) for key in COSTS},
            "fallback_count":sum(bool(value.get("fallback_reason")) for value in values),
            "latency_ms":{"n":340,"min":latency[0],"median":q(.5),"p90":q(.9),"p95":q(.95),"max":latency[-1]},
            "child_current_rss_median_bytes":statistics.median(child),"child_current_rss_peak_bytes":max(child),
            "parent_current_rss_peak_bytes":max(parent),"child_reported_peak_rss_bytes":peak_reported,"mlx_peak_bytes":mlx,
            "child_first85_last85_ratio":statistics.median(child[-85:])/statistics.median(child[:85])}


def api(path,payload=None,timeout=10):
    token=(BENCH/"access-token").read_text().strip()
    request=Request("http://127.0.0.1:8789/api/"+path,data=canonical(payload).encode() if payload is not None else None,
                    headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"})
    with urlopen(request,timeout=timeout) as response:
        return json.load(response)


def run():
    os.umask(0o077)
    require(not any(path.is_symlink() for path in (RUN,*RUN.parents)),"run_path_symlink")
    require(not any((RUN/name).exists() for name in ("run-claim.json","run.json","plan.json","stdout.log","samples.jsonl","jobs.jsonl")),"attempt_already_used")
    service=load_service(RUN,8789)
    with sqlite3.connect((BENCH/"jobs.sqlite3").as_uri()+"?mode=ro",uri=True) as db:
        require(db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]==0,"bench_not_empty")
    started=time.monotonic(); deadline=started+1800
    source,rows=read_job(ROOT/"private/jobs.sqlite3",SOURCE_JOB)
    require(source["state"]=="completed" and source["snapshot_hash"]==SOURCE_SNAPSHOT
            and digest(canonical([row["record"] for row in rows]))==SOURCE_SNAPSHOT,"source_snapshot_drift")
    verification_path=ROOT/"private/validation/exp-076/attempt-3/verification.json"
    require(digest(verification_path.read_bytes())==SOURCE_VERIFICATION,"source_verification_drift")
    plan,content=make_plan(rows)
    dependencies={name:digest((ROOT/name).read_bytes()) for name in DEPENDS}
    previous=RUN.parent/"attempt-2"
    require(digest((previous/"frozen-code.tar.gz").read_bytes())==PREVIOUS_ARCHIVE_SHA
            and digest((previous/"verification.json").read_bytes())==PREVIOUS_VERIFICATION_SHA,"previous_attempt_identity_drift")
    plan.update(sources=dependencies,protocol_sha256=digest(PROTOCOL.read_bytes()),decision_sha256=digest(DECISION.read_bytes()),
                correction_sha256=digest(CORRECTION.read_bytes()),reduced_background_sha256=digest(REDUCED_BACKGROUND.read_bytes()),
                previous_attempt_archive_sha256=PREVIOUS_ARCHIVE_SHA,
                previous_attempt_verification_sha256=PREVIOUS_VERIFICATION_SHA,service_sha256=digest((RUN/"service.json").read_bytes()))
    environment=environment_metadata()
    dirty=subprocess.check_output(["git","status","--porcelain=v1"],cwd=ROOT,text=True)
    once(RUN/"plan.json",plan)
    claim={"experiment_id":"EXP-079","attempt":3,"tier":"Major","started_at":now(),"started_monotonic":started,
           "plan_sha256":digest((RUN/"plan.json").read_bytes()),"command":sys.argv,"cwd":str(ROOT),"environment":environment,
           "git_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
           "git_dirty":bool(dirty),"git_status_porcelain":dirty.splitlines(),"training":False,"gold_accessed":False,"source_network_fetched":False}
    once(RUN/"run-claim.json",claim)
    monitor=Monitor(RUN/"samples.jsonl",service)
    jobs,readiness,current,failure,cleanup=[],[],None,None,None
    pending_submission=None
    unhandled=0
    with (RUN/"stdout.log").open("x") as output,(RUN/"jobs.jsonl").open("x") as job_log:
        def report(value):
            line=canonical(value);print(line,flush=True);output.write(line+"\n");output.flush()
        try:
            monitor.start()
            for round_index in range(1,4):
                for mode in MODES:
                    require(time.monotonic()<deadline,"total_time_limit")
                    waiting={"round":round_index,"mode":mode,"started_monotonic":time.monotonic(),"status":"Waiting","readiness_indices":[]}
                    readiness.append(waiting)
                    before=monitor.samples[-1]["index"] if monitor.samples else -1
                    report({"round":round_index,"mode":mode,"status":"waiting_for_quiet_window"})
                    try:
                        indices=wait_ready(monitor,deadline,60)
                        waiting.update(status="Ready",readiness_indices=indices)
                    except Exception as error:
                        waiting.update(status="NotReady",error_code=str(error) if isinstance(error,SupportError) else type(error).__name__)
                        raise
                    finally:
                        waiting["ended_monotonic"]=time.monotonic()
                        waiting["observed_sample_indices"]=[row["index"] for row in monitor.samples if row["index"]>before]
                    require(not monitor.reason,monitor.reason or "monitor_failure")
                    began=time.monotonic()
                    request={"name":f"EXP-079 round {round_index} {mode}","source":"upload","mode":mode,"audit_rate":0,
                             "max_qwen_calls":20 if mode=="demo" else 500 if mode=="research" else 0,
                             "upload":{"format":"jsonl","content":content,"filename":"exp079-snapshot.jsonl","text_column":"text"}}
                    pending_submission={"known_ids":known_job_ids(BENCH/"jobs.sqlite3"),"mode":mode,"round":round_index,
                                        "name":request["name"],"started_monotonic":began,"readiness":dict(waiting)}
                    current=api("jobs",request)["job"]["id"];monitor.set_job(current)
                    entry={"id":current,"round":round_index,"mode":mode,"status":"submitted","started_monotonic":began,
                           "readiness_indices":indices,"readiness_started_monotonic":waiting["started_monotonic"],
                           "readiness_ended_monotonic":waiting["ended_monotonic"],"summary":None,"cost_complete":False,
                           "http_submission_acknowledged":True}
                    jobs.append(entry);job_log.write(canonical(entry)+"\n");job_log.flush()
                    pending_submission=None
                    report({"id":current,"round":round_index,"mode":mode,"status":"submitted"})
                    while True:
                        require(time.monotonic()<deadline,"total_time_limit")
                        require(not monitor.reason,monitor.reason or "monitor_failure")
                        job=api("jobs/"+current)["job"]
                        if job["state"] in {"completed","completed_with_fallback","failed","cancelled"}:
                            break
                        # Preserve production Demo behavior, but do not continue a bounded study after runtime fallback.
                        if job["completed_items"]:
                            _,partial=read_job(BENCH/"jobs.sqlite3",current)
                            require(all(row["result"] is None or row["result"].get("fallback_reason") in (None,"m3_budget_exhausted") for row in partial),"model_runtime_failure")
                        time.sleep(.2)
                    ended=time.monotonic()
                    entry.update(status=job["state"],error_code=job["error_code"],ended_monotonic=ended,elapsed_seconds=ended-began,
                                 total_items=job["total_items"],completed_items=job["completed_items"],snapshot_hash=job["snapshot_hash"])
                    require(job["state"] in {"completed","completed_with_fallback"},"runtime_job_failed")
                    _,completed=read_job(BENCH/"jobs.sqlite3",current)
                    entry["summary"]=summarize(completed)
                    after=monitor.samples[-1]["index"] if monitor.samples else -1
                    entry["exit_observation"]=wait_absent(monitor,after,min(deadline,time.monotonic()+15),15)
                    entry.update(normal_exit=True,production_final_gate="completed_state_after_exit0",cost_complete=True)
                    job_log.write(canonical(entry)+"\n");job_log.flush()
                    report({"id":current,"status":entry["status"],"completed_items":340,"cost":entry["summary"]["cost"]})
                    monitor.set_job(None);current=None
                    require(all(digest((ROOT/name).read_bytes())==hashed for name,hashed in dependencies.items())
                            and digest(PROTOCOL.read_bytes())==plan["protocol_sha256"] and digest(DECISION.read_bytes())==plan["decision_sha256"]
                            and digest(CORRECTION.read_bytes())==plan["correction_sha256"]
                            and digest(REDUCED_BACKGROUND.read_bytes())==plan["reduced_background_sha256"],"implementation_identity_drift")
        except Exception as error:
            failure=str(error) if isinstance(error,SupportError) else type(error).__name__
            unhandled=int(not isinstance(error,SupportError))
            if current is None and pending_submission is not None:
                recovered_at=time.monotonic()
                try:
                    recovery=recover_unacknowledged_submission(BENCH/"jobs.sqlite3",pending_submission["known_ids"],
                                                               pending_submission["mode"],plan["payload_sha256"],pending_submission["name"])
                except Exception:
                    recovery={"status":"unconfirmed","candidate_count":None}
                if recovery["status"]=="identified_for_cancellation":
                    current=recovery["id"];monitor.set_job(current);waiting=pending_submission["readiness"]
                    jobs.append({"id":current,"round":pending_submission["round"],"mode":pending_submission["mode"],
                                 "status":"submission_ack_lost","started_monotonic":pending_submission["started_monotonic"],
                                 "readiness_indices":waiting["readiness_indices"],"readiness_started_monotonic":waiting["started_monotonic"],
                                 "readiness_ended_monotonic":waiting["ended_monotonic"],"http_submission_acknowledged":False,
                                 "recovered_for_cancellation_only":True,"submission_recovery":recovery,"summary":None,"cost_complete":False})
                    job_log.write(canonical(jobs[-1])+"\n");job_log.flush()
                else:
                    cleanup={"normal_exit":False,"terminal_confirmed":False,"models_absent_confirmed":False,
                             "started_monotonic":recovered_at,"ended_monotonic":time.monotonic(),"max_seconds":15,
                             "submission_recovery":recovery,"error_code":"submission_identity_unconfirmed"}
            if current is not None:
                cleanup=cancel_and_confirm(current,api,monitor,15)
                try:
                    job,partial=read_job(BENCH/"jobs.sqlite3",current)
                    acknowledged=[row["result"] for row in partial if row["result"] is not None]
                    jobs[-1].update(status=job["state"],completed_items=job["completed_items"],total_items=job["total_items"],
                                    error_code=job["error_code"],snapshot_hash=job["snapshot_hash"],normal_exit=False,cost_complete=False,
                                    acknowledged_results=len(acknowledged),acknowledged_cost_lower_bound={key:sum(value["counters"][key] for value in acknowledged) for key in COSTS},
                                    unacknowledged_attempts=None,cleanup=cleanup)
                except Exception:
                    pass
                cleanup_ended=time.monotonic()
                jobs[-1].update(ended_monotonic=cleanup_ended,elapsed_seconds=cleanup_ended-jobs[-1]["started_monotonic"])
                job_log.write(canonical(jobs[-1])+"\n");job_log.flush()
            elif cleanup is None:
                initial=monitor.samples[-1]["index"] if monitor.samples else -1
                cleanup_started=time.monotonic()
                try:
                    absent=wait_absent(monitor,initial,cleanup_started+15,15)
                    cleanup={"normal_exit":False,"models_absent_confirmed":True,"exit_observation":absent}
                except Exception:
                    cleanup={"normal_exit":False,"models_absent_confirmed":False}
                cleanup.update(started_monotonic=cleanup_started,ended_monotonic=time.monotonic(),max_seconds=15)
        finally:
            monitor.finish();failure=failure or monitor.reason;ended=time.monotonic()
            report({"status":"Stopped" if failure else "Completed","failure_code":failure,"completed_jobs":sum(job.get("cost_complete") is True for job in jobs)})
            output.flush();os.fsync(output.fileno());job_log.flush();os.fsync(job_log.fileno())
    record={**claim,"status":"Stopped" if failure else "Completed","ended_at":now(),"ended_monotonic":ended,"elapsed_seconds":ended-started,
            "failure_code":failure,**error_counts(jobs,unhandled),
            "jobs":jobs,"readiness_attempts":readiness,"cleanup":cleanup,
            "completed_jobs":sum(job.get("cost_complete") is True for job in jobs),"planned_jobs":9,"planned_events":3060,
            "samples_sha256":digest((RUN/"samples.jsonl").read_bytes()),"stdout_sha256":digest((RUN/"stdout.log").read_bytes()),
            "jobs_sha256":digest((RUN/"jobs.jsonl").read_bytes()),"process_events_sha256":digest((RUN/"process-events.jsonl").read_bytes()),
            "service_sha256":digest((RUN/"service.json").read_bytes()),
            "claim_boundary":"Bounded local use only; not the old Soak, an SLA, external gold accuracy, or attribution of whole-machine pressure."}
    once(RUN/"run.json",record)
    return 0 if failure is None else 1


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument("command",choices=("serve","run"));args=parser.parse_args(argv)
    return serve_app(RUN,"EXP-079",8789) if args.command=="serve" else run()


if __name__ == "__main__":
    raise SystemExit(main())
