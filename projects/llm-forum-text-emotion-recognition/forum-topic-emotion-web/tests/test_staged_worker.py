"""Staged lifecycle and real JSONL transport with synthetic children, never models."""
from functools import partial
import json
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from topicweb.app import create_app
from topicweb.core import aggregate, make_record
from topicweb.staged_worker import CleanupPending, StagedDispatcher, StagedProcessRunner, StagedRunner, counters, digest, safe_result
from topicweb.store import Store, dumps
from topicweb.worker import Revoked, WorkerError
from test_staged_integration import InstantMonitor, SyntheticPhaseRunner


class Monitor(InstantMonitor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.phase_exits = {}
        self.current_runner = None
        self.events = []
        self.updated = threading.Condition()

    def identify(self, pid, *, not_before):
        return {"pid": pid, "process_key": f"{pid}|synthetic_birth"}

    def process_event(self, kind, logical_job_id, phase_id, **fields):
        value = {"type": kind, "logical_job_id": logical_job_id, "phase_id": phase_id, **fields}
        self.events.append(value)
        if fields.get("process_key"):
            self.seen.add(fields["process_key"])
        if kind == "process_exit":
            self.phase_exits[phase_id] = value

    def observe_resources(self, resources):
        assert resources["peak_rss_bytes"] == 1024


def records(count=4):
    return [make_record(source="upload", site="upload", object_type="row", source_object_id=str(i),
                        model_input_text="Self-authored repeated input "+str(i//2)) for i in range(count)]


def setup(tmp_path, factory=SyntheticPhaseRunner, *, mode="research", budget=500, monitor_factory=Monitor, observer=None):
    store = Store(tmp_path/"private")
    item = store.create({"name":"Synthetic staged task","source":"upload","mode":mode,"max_qwen_calls":budget,"audit_rate":0}, records(), {})
    dispatcher = StagedDispatcher(store, aggregate, lambda *args, **kwargs: None, factory,
                                  monitor_factory=monitor_factory, observer=observer)
    dispatcher.lock = (tmp_path/"synthetic.lock").open("w+")
    return store, dispatcher, store.claim(), item["id"]


@pytest.mark.parametrize("budget", [0, 1])
def test_physical_counters_and_original_full_cache_alias(tmp_path, budget):
    store, dispatcher, job, identifier = setup(tmp_path, mode="demo", budget=budget)
    try:
        dispatcher.run_job(job)
        result = store.get(identifier)
        assert result["state"] == "completed_with_fallback"
        rows = store.items(identifier)
        for row in rows:
            value = row["result"]
            assert value["cumulative_counters"]["m1_attempts"] == 2
            assert value["cumulative_counters"]["m1_cache_hit"] == 2
            assert value["staged_raw_counters"]["m1_cache_hit"] == 1
            assert "fallback_reason" in value["counters"]
            assert value["staged_latency_scope"] == "phase_response_only_m1_prepass_excluded"
        assert [row["result"]["cache_hit"] for row in rows] == ([False,False,False,False] if budget == 0 else [False,True,False,False])
        progress = result["progress"]["staged_execution"]
        assert progress["prelude_transfer_reuses"] == 4 and progress["cost_complete"]
    finally:
        dispatcher.lock.close()


def test_failure_keeps_spent_prepass_and_error_attempt_evidence(tmp_path):
    observed = []
    class FailReplay(SyntheticPhaseRunner):
        def __init__(self, job, **kwargs):
            self.mode = job["mode"]
            super().__init__(job, **kwargs)
        def predict(self, item_id, record):
            if self.mode == "research":
                counts = {key:0 for key in ("m1_attempts","m3_attempts","m3_succeeded","m1_cache_hit","m3_cache_hit","audit_extra_calls")}
                counts.update(m1_cache_hit=1,m3_attempts=1)
                raise WorkerError("m3_runtime_failure", {"cumulative_counters":counts})
            return super().predict(item_id, record)
    store, dispatcher, job, identifier = setup(tmp_path, FailReplay, observer=lambda kind,payload:observed.append((kind,payload)))
    try:
        dispatcher.run_job(job)
        result = store.get(identifier)
        assert result["state"] == "failed" and result["completed_items"] == 0
        value = result["progress"]["staged_execution"]
        assert value["cumulative_counters"]["m1_attempts"] == value["cumulative_counters"]["m1_cache_hit"] == 2
        assert value["cumulative_counters"]["m3_attempts"] == 1 and not value["cost_complete"]
        assert any(kind == "runtime_event" and payload["type"] == "failure_cost" for kind,payload in observed)
    finally:
        dispatcher.lock.close()


def test_cancel_in_second_quiet_keeps_full_prepass_and_no_final_rows(tmp_path):
    store = None
    class CancelQuiet(Monitor):
        waits = 0
        def wait_ready(self, deadline, cancelled):
            self.waits += 1
            if self.waits == 2:
                store.cancel(identifier)
                raise Revoked("job_revoked")
            return super().wait_ready(deadline, cancelled)
    store, dispatcher, job, identifier = setup(tmp_path, monitor_factory=CancelQuiet)
    try:
        dispatcher.run_job(job)
        value = store.get(identifier)
        assert value["state"] == "cancelled" and value["completed_items"] == 0
        progress = value["progress"]["staged_execution"]
        assert progress["stage"] == "waiting_m3_quiet" and progress["phase_id"] == identifier+":m3"
        assert progress["cumulative_counters"]["m1_attempts"] == 2 and not progress["cost_complete"]
    finally:
        dispatcher.lock.close()


def test_expiry_and_changed_snapshot_fail_before_any_phase(tmp_path):
    factory = Mock(side_effect=AssertionError("no child allowed"))
    store, dispatcher, job, identifier = setup(tmp_path, factory)
    try:
        with store.connect() as db:
            db.execute("UPDATE jobs SET created_at=? WHERE id=?", (time.time()-8*86400,identifier))
        dispatcher.run_job(job)
        assert store.get(identifier)["state"] == "failed"
        assert not factory.called
    finally:
        dispatcher.lock.close()


def test_unconfirmed_cleanup_never_retries_or_publishes_deletable_terminal(tmp_path):
    closes=[]
    class Unconfirmed(SyntheticPhaseRunner):
        def __init__(self, job, **kwargs):
            self.mode=job["mode"]
            super().__init__(job, **kwargs)
        def predict(self, item_id, record):
            if self.mode == "research": raise WorkerError("m3_runtime_failure")
            return super().predict(item_id,record)
        def close(self):
            if self.mode == "research":
                closes.append(True)
                raise RuntimeError("synthetic unconfirmed exit")
            super().close()
    store,dispatcher,job,identifier=setup(tmp_path,Unconfirmed)
    try:
        with pytest.raises(CleanupPending): dispatcher.run_job(job)
        assert closes == [True]
        assert store.get(identifier)["state"] == "cancel_requested"
        assert not store.put_result(identifier,0,{})
        assert store.request_delete(identifier) == "deleting"
        assert store.get(identifier) is not None
        assert dispatcher.blocked_reason == "owned_process_exit_unconfirmed"
    finally:
        dispatcher.lock.close()


def test_http_delete_waits_for_failure_cleanup_before_removing_data(tmp_path):
    entered,release=threading.Event(),threading.Event()
    class BlockingClose(SyntheticPhaseRunner):
        def __init__(self,job,**kwargs):
            self.mode=job["mode"]
            super().__init__(job,**kwargs)
        def predict(self,item_id,record):
            if self.mode == "research": raise WorkerError("m3_runtime_failure")
            return super().predict(item_id,record)
        def close(self):
            if self.mode == "research":
                entered.set()
                assert release.wait(5)
            super().close()
    app=create_app(private_dir=tmp_path/"private",token="synthetic-staged-cleanup-token-32-chars",
                   dispatcher_factory=partial(StagedDispatcher,monitor_factory=Monitor),runner_factory=BlockingClose)
    with TestClient(app,base_url="http://127.0.0.1:8787",client=("127.0.0.1",1234)) as client:
        client.headers["Authorization"]="Bearer synthetic-staged-cleanup-token-32-chars"
        item=client.post("/api/jobs",json={"source":"upload","mode":"research","upload":{"format":"json","content":json.dumps([{"text":"Self-authored synthetic input"}])}}).json()["job"]
        identifier=item["id"]
        try:
            assert entered.wait(3)
            assert client.delete(f"/api/jobs/{identifier}").status_code == 202
            assert client.get(f"/api/jobs/{identifier}").status_code == 410
            assert app.state.store.get(identifier)["state"] == "deleting"
            assert not app.state.store.put_result(identifier,0,{})
        finally:
            release.set()
        until=time.monotonic()+3
        while time.monotonic()<until and client.get(f"/api/jobs/{identifier}").status_code != 404:
            time.sleep(.01)
        assert client.get(f"/api/jobs/{identifier}").status_code == 404


@pytest.mark.parametrize("failure", ["outer_deadline", "result_store"])
def test_legacy_outer_failure_waits_for_cleanup_before_terminal(tmp_path, failure):
    entered,release=threading.Event(),threading.Event()
    closes=[]
    class BlockingClose(SyntheticPhaseRunner):
        def close(self):
            closes.append(True)
            entered.set()
            assert release.wait(5)
            super().close()
    store,dispatcher,job,identifier=setup(tmp_path,BlockingClose,mode="m1_only",budget=0)
    original=store.put_result
    if failure=="outer_deadline":
        dispatcher.deadline_seconds=.5
    def fail_outside_runner(*args):
        if failure=="result_store":
            raise RuntimeError("synthetic result-store failure")
        changed=original(*args)
        # The next deadline check belongs to Dispatcher, not StagedRunner.predict.
        time.sleep(.6)
        return changed
    store.put_result=fail_outside_runner
    errors=[]
    def execute():
        try:
            dispatcher.run_job(job)
        except BaseException as error:
            errors.append(type(error).__name__)
    thread=threading.Thread(target=execute)
    thread.start()
    try:
        assert entered.wait(3)
        assert store.get(identifier)["state"] not in {"failed","cancelled","completed","completed_with_fallback"}
        assert store.request_delete(identifier)=="deleting"
        assert store.get(identifier) is not None and thread.is_alive()
        assert not original(identifier,1,{})
    finally:
        release.set()
        thread.join(3)
        dispatcher.lock.close()
    assert not thread.is_alive() and not errors
    assert store.get(identifier) is None and closes==[True]


def test_birth_key_is_not_published_as_seen_before_event(tmp_path):
    monitor=Monitor(tmp_path)
    runner=StagedProcessRunner.__new__(StagedProcessRunner)
    runner.monitor,runner.process,runner.process_key,runner.constructed_at=monitor,SimpleNamespace(pid=123),None,1.
    runner._birth()
    assert runner.process_key == "123|synthetic_birth" and monitor.seen == set()


@pytest.mark.parametrize("code", ["resource_limit_exceeded", "invalid_staged_progress", "model_output_invalid"])
def test_latched_resource_failure_leaves_later_jobs_queued(tmp_path, code):
    calls=[]
    class Unsafe(SyntheticPhaseRunner):
        def predict(self,item_id,record):
            calls.append(item_id)
            raise WorkerError(code)
    store=Store(tmp_path/"private")
    request={"name":"Synthetic resource task","source":"upload","mode":"m1_only","max_qwen_calls":0}
    first=store.create(request,records(1),{})
    second=store.create(request,records(1),{})
    dispatcher=StagedDispatcher(store,aggregate,lambda *args,**kwargs:None,Unsafe,monitor_factory=Monitor)
    dispatcher.start()
    try:
        deadline=time.monotonic()+3
        while time.monotonic()<deadline and store.get(first["id"])["state"]!="failed": time.sleep(.01)
        assert store.get(first["id"])["state"]=="failed"
        assert dispatcher.blocked_reason==code
        assert store.get(second["id"])["state"]=="queued" and calls==[0]
    finally:
        dispatcher.stop()


def test_source_fetch_cancel_callback_sees_resource_latch(tmp_path):
    store=Store(tmp_path/"private")
    item=store.create({"name":"Synthetic source task","source":"stackexchange","mode":"m1_only","query":{}},None,None)
    factory=Mock(side_effect=AssertionError("must not start child"))
    def fetch(request,*,cancelled,progress):
        dispatcher.monitor.block("critical_memory_pressure")
        assert cancelled() is True
        return records(1),{}
    dispatcher=StagedDispatcher(store,aggregate,fetch,factory,monitor_factory=Monitor)
    dispatcher.lock=(tmp_path/"synthetic.lock").open("w+")
    try:
        dispatcher.run_job(store.claim())
        assert store.get(item["id"])["state"]=="failed"
        assert store.get(item["id"])["error_code"]=="critical_memory_pressure"
        assert not factory.called
    finally:
        dispatcher.lock.close()


def test_constructor_monitor_failure_releases_transfer_reference(tmp_path):
    monitor=Monitor(tmp_path)
    monitor.reason="observer_callback_failed"
    transfer={"base_fingerprint":"b"*64,"entries":[]}
    with pytest.raises(WorkerError):
        StagedProcessRunner({"id":"logical:m3","mode":"research","request":{}},lock_fd=0,cancelled=lambda:False,
                            deadline=time.monotonic()+2,monitor=monitor,logical_job_id="logical",transfer=transfer)
    assert monitor.current_runner is None


CHILD = r'''
import hashlib,json,sys
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'))
def emit(value): print(json.dumps(value),flush=True)
init=json.loads(sys.stdin.readline()); transfer=init.get('transfer')
base='b'*64; fingerprint=base
if transfer:
    fingerprint=hashlib.sha256(canonical({'base_fingerprint':base,'strategy':'m1-receipt-transfer-v1','transfer_sha256':init['transfer_sha256']}).encode()).hexdigest()
ready={'type':'ready','fingerprint':fingerprint,'audit_rate':0,'cache_scope':'job_exact_input_components','modelstatus':{'m1':'loaded','m3':'not_loaded','mode':'m1_only'}}
if transfer:
    ready.update(cache_scope='job_m1_receipt_transfer',modelstatus={'m1':'receipt_replay_not_loaded','m3':'not_loaded','mode':init['mode']},m1_instance_absent=True,base_fingerprint=base,transfer_sha256=init['transfer_sha256'],transfer_items=1,cache_entries=1,strategy='m1-receipt-transfer-v1')
emit(ready)
for line in sys.stdin:
    request=json.loads(line)
    if request['op']=='close': break
    costs={key:0 for key in ('m1_attempts','m3_attempts','m3_succeeded','m1_cache_hit','m3_cache_hit','audit_extra_calls')}
    costs.update(m1_cache_hit=1,m3_attempts=1)
    emit({'type':'staged_progress','stage':'m3_load','kind':'begin','ordinal':0,'cumulative_counters':costs,'resources':{'peak_rss_bytes':1024,'mlx_peak_bytes':0,'elapsed_seconds':0}})
    emit({'type':'error','item_id':request['item_id'],'code':'synthetic_m3_failure','counters':costs,'cumulative_counters':costs})
'''


def test_real_jsonl_transport_filters_progress_preserves_error_and_exit_order(tmp_path):
    monitor=Monitor(tmp_path)
    seen=[]
    record=records(1)[0]
    transfer={"base_fingerprint":"b"*64,"entries":[{"ordinal":0,"input_sha256":record["model_input_hash"],
               "m1_probabilities":[.5]*6,"tokenlengths":{"m1":{"input_tokens":1,"used_tokens":1,"truncated":False}}}]}
    with (tmp_path/"synthetic.lock").open("w+") as lock:
        runner=StagedProcessRunner({"id":"logical:m3","mode":"research","request":{"max_qwen_calls":1}},lock_fd=lock.fileno(),
             cancelled=lambda:False,deadline=time.monotonic()+5,monitor=monitor,logical_job_id="logical",transfer=transfer,
             on_progress=seen.append,command=[sys.executable,"-u","-c",CHILD])
        with pytest.raises(WorkerError,match="synthetic_m3_failure") as failure: runner.predict(0,record)
        assert failure.value.metadata["cumulative_counters"]["m3_attempts"]==1
        assert len(seen)==1 and seen[0]["stage"]=="m3_load"
        runner.close()
    assert [row["type"] for row in monitor.events]==["constructor_started","ready","process_exit"]
    assert monitor.current_runner is None and runner.transfer is None


def test_real_jsonl_progress_reaches_staged_runner_observer_and_store(tmp_path):
    runtime_events=[]
    monitor=Monitor(tmp_path,observer=lambda kind,payload:runtime_events.append((kind,payload)))
    record=records(1)[0]
    transfer={"base_fingerprint":"b"*64,"entries":[{"ordinal":0,"input_sha256":record["model_input_hash"],
               "m1_probabilities":[.5]*6,"tokenlengths":{"m1":{"input_tokens":1,"used_tokens":1,"truncated":False}}}]}
    class ProgressStore:
        def __init__(self): self.value={"progress":{}}
        def get(self, job_id): return self.value
        def progress(self, job_id, value): self.value["progress"]=value
    store=ProgressStore()
    staged=StagedRunner.__new__(StagedRunner)
    staged.job={"id":"logical"}
    staged.store=store
    staged.monitor=monitor
    staged.rows=[{"ordinal":0,"record":record}]
    staged.phase={"id":"logical:m3","completed_items":0}
    staged.m1_total={"m1_attempts":1,"m1_cache_hit":0,"m3_attempts":0,"m3_succeeded":0,"m3_cache_hit":0,"audit_extra_calls":0}
    staged.m3_total={key:0 for key in staged.m1_total}
    staged.transfer_reuses=0
    staged.progress_stage="m3_replay"
    staged.progress_completed=0
    staged.progress_phase_id="logical:m3"
    with (tmp_path/"synthetic.lock").open("w+") as lock:
        runner=StagedProcessRunner({"id":"logical:m3","mode":"research","request":{"max_qwen_calls":1}},lock_fd=lock.fileno(),
             cancelled=lambda:False,deadline=time.monotonic()+5,monitor=monitor,logical_job_id="logical",transfer=transfer,
             on_progress=staged._phase_progress,command=[sys.executable,"-u","-c",CHILD])
        with pytest.raises(WorkerError,match="synthetic_m3_failure"):
            runner.predict(0,record)
        runner.close()
    event=[payload for kind,payload in runtime_events if kind=="runtime_event" and payload.get("type")=="staged_progress"]
    assert len(event)==1 and event[0]["kind"]=="begin" and event[0]["stage"]=="m3_load"
    progress=store.value["progress"]["staged_execution"]
    assert progress["phase_id"]=="logical:m3" and progress["stage"]=="m3_replay"
    assert progress["cumulative_counters"]["m1_attempts"]==1
    assert progress["cumulative_counters"]["m3_attempts"]==1
    assert progress["prelude_transfer_reuses"]==1 and progress["cost_complete"] is False


def test_real_transport_normal_finish_and_failed_constructor(tmp_path):
    for command,normal in ((CHILD,True),("import json;print(json.dumps({'type':'error','code':'synthetic_init_failure'}),flush=True)",False)):
        monitor=Monitor(tmp_path)
        with (tmp_path/"synthetic.lock").open("w+") as lock:
            args=dict(lock_fd=lock.fileno(),cancelled=lambda:False,deadline=time.monotonic()+5,monitor=monitor,logical_job_id="logical",
                      command=[sys.executable,"-u","-c",command])
            if normal:
                runner=StagedProcessRunner({"id":"logical:m1","mode":"m1_only","request":{"max_qwen_calls":0}},**args)
                runner.finish()
                assert [row["type"] for row in monitor.events]==["constructor_started","ready","process_exit","final_gate_passed"]
                assert runner.process.returncode==0
            else:
                with pytest.raises(WorkerError,match="synthetic_init_failure"):
                    StagedProcessRunner({"id":"logical:m1","mode":"m1_only","request":{}},**args)
                assert [row["type"] for row in monitor.events]==["constructor_started","process_exit"]
            assert monitor.current_runner is None
