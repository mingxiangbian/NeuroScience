import fcntl
import json
import os
import subprocess
import sys
import threading
import time

import pytest

from topicweb.core import aggregate, make_record
from topicweb.store import QueueFull, Store
from topicweb.worker import Dispatcher, ProcessRunner, WorkerError


def record(text="Synthetic hello", identity="1"):
    return make_record(source="upload", site="fixture", object_type="row", source_object_id=identity, model_input_text=text, source_payload_raw={"text": text})


def request(mode="m1_only"):
    return {"name": "Synthetic test", "source": "upload", "mode": mode, "max_qwen_calls": 0}


def wait_until(predicate, timeout=5):
    limit = time.monotonic() + timeout
    while time.monotonic() < limit:
        value = predicate()
        if value:
            return value
        time.sleep(0.01)
    raise AssertionError("timed out")


def test_private_modes_snapshot_and_no_duplicate_content(tmp_path):
    store = Store(tmp_path / "private")
    job = store.create({**request(), "upload": {"content": "secret"}}, [record()], {"fixture": True})
    assert store.private_dir.stat().st_mode & 0o777 == 0o700
    assert store.path.stat().st_mode & 0o777 == 0o600
    assert "upload" not in store.get(job["id"], private=True)["request"]
    assert store.get(job["id"])["snapshot_hash"]
    assert "model_input_text" not in store.items(job["id"])[0]["record"]
    assert store.items(job["id"], private=True)[0]["record"]["model_input_text"] == "Synthetic hello"


def test_queue_capacity_and_single_claim(tmp_path):
    store = Store(tmp_path / "private", max_queue=2)
    store.create(request(), [record()])
    store.create(request(), [record()])
    with pytest.raises(QueueFull):
        store.create(request(), [record()])
    claims = []
    threads = [threading.Thread(target=lambda: claims.append(store.claim())) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(job is not None for job in claims) == 1


def test_delete_revokes_late_writes_and_purges_rows(tmp_path):
    store = Store(tmp_path / "private")
    job = store.create(request(), [record()])
    assert store.claim()["id"] == job["id"]
    assert store.transition(job["id"], "snapshot_sealed", "inferencing")
    assert store.request_delete(job["id"]) == "deleting"
    assert not store.put_result(job["id"], 0, {"prediction": [0] * 6})
    store.finish_revocation(job["id"])
    assert store.get(job["id"]) is None
    assert store.items(job["id"], private=True) == []


def test_cancel_and_result_idempotency(tmp_path):
    store = Store(tmp_path / "private")
    job = store.create(request(), [record()])
    store.claim()
    store.transition(job["id"], "snapshot_sealed", "inferencing")
    assert store.put_result(job["id"], 0, {"prediction": [0] * 6})
    assert not store.put_result(job["id"], 0, {"prediction": [1] * 6})
    assert store.get(job["id"])["completed_items"] == 1
    store.cancel(job["id"])
    assert store.cancelled(job["id"])
    assert not store.put_result(job["id"], 1, {})
    store.finish_revocation(job["id"])
    assert store.get(job["id"])["state"] == "cancelled"


def test_replay_uses_sealed_snapshot_and_retention(tmp_path):
    store = Store(tmp_path / "private")
    job = store.create(request(), [record()])
    store.transition(job["id"], "queued", "completed", dashboard={"n": 1})
    replay = store.replay(job["id"])
    assert replay["id"] != job["id"] and replay["snapshot_hash"] == job["snapshot_hash"]
    assert replay["completed_items"] == 0 and store.items(replay["id"])[0]["result"] is None
    assert store.purge(job["created_at"] + 7 * 86400)["raw_redacted"] == 1
    row = store.items(job["id"], private=True)[0]["record"]
    assert "display_text" not in row and "source_payload_raw" not in row and "model_input_text" not in row
    with pytest.raises(ValueError, match="snapshot_not_replayable"):
        store.replay(job["id"])
    assert store.purge(job["created_at"] + 30 * 86400)["items_removed"] == 1
    assert store.items(job["id"]) == []
    assert store.get(job["id"])["dashboard"] == {"n": 1}
    assert store.purge(job["created_at"] + 90 * 86400)["jobs_removed"] == 1
    assert store.get(job["id"]) is None


class FakeRunner:
    def __init__(self, job, **kwargs):
        self.closed = False

    def predict(self, item_id, record):
        return {"prediction": [0, 1, 0, 0, 0, 0], "used_path": "m1", "fallback": False}

    def close(self):
        self.closed = True


def test_dispatcher_completes_synthetic_job(tmp_path):
    store = Store(tmp_path / "private")
    job = store.create(request(), [record(), record(identity="2")])
    dispatcher = Dispatcher(store, aggregate, None, FakeRunner)
    dispatcher.start()
    try:
        wait_until(lambda: store.get(job["id"])["state"] == "completed")
        assert store.get(job["id"])["dashboard"]["summary"]["successful_items"] == 2
    finally:
        dispatcher.stop()


def test_snapshot_drift_fails_before_inference(tmp_path):
    store = Store(tmp_path / "private")
    job = store.create(request(), [record()])
    with store.connect() as db:
        db.execute("UPDATE items SET record=? WHERE job_id=?", (json.dumps(record("changed fixture")), job["id"]))
    dispatcher = Dispatcher(store, aggregate, None, FakeRunner)
    dispatcher.start()
    try:
        wait_until(lambda: store.get(job["id"])["state"] == "failed")
        assert store.get(job["id"])["error_code"] == "snapshot_hash_mismatch"
        assert store.get(job["id"])["completed_items"] == 0
    finally:
        dispatcher.stop()


def test_dispatcher_cancel_delete_and_no_late_result(tmp_path):
    store = Store(tmp_path / "private")
    entered = threading.Event()
    release = threading.Event()

    class SlowRunner(FakeRunner):
        def predict(self, item_id, record):
            entered.set()
            release.wait(3)
            return super().predict(item_id, record)

    job = store.create(request(), [record()])
    dispatcher = Dispatcher(store, aggregate, None, SlowRunner)
    dispatcher.start()
    try:
        assert entered.wait(2)
        assert store.request_delete(job["id"]) == "deleting"
        release.set()
        wait_until(lambda: store.get(job["id"]) is None)
        assert store.items(job["id"]) == []
    finally:
        release.set()
        dispatcher.stop()


def test_research_cannot_complete_with_demo_fallback(tmp_path):
    class FallbackRunner(FakeRunner):
        def predict(self, item_id, record):
            return {**super().predict(item_id, record), "fallback": True}

    store = Store(tmp_path / "private")
    job = store.create(request("research"), [record()])
    dispatcher = Dispatcher(store, aggregate, None, FallbackRunner)
    dispatcher.start()
    try:
        wait_until(lambda: store.get(job["id"])["state"] == "failed")
        assert store.get(job["id"])["error_code"] == "research_fallback_forbidden"
    finally:
        dispatcher.stop()


def test_single_dispatcher_and_crash_recovery(tmp_path):
    store = Store(tmp_path / "private")
    job = store.create(request(), [record()])
    store.claim()
    first = Dispatcher(store, aggregate, None, FakeRunner)
    second = Dispatcher(store, aggregate, None, FakeRunner)
    first.start()
    try:
        assert store.get(job["id"])["state"] == "failed"
        assert store.get(job["id"])["error_code"] == "worker_interrupted"
        with pytest.raises(WorkerError, match="dispatcher_already_running"):
            second.start()
    finally:
        first.stop()


def test_surviving_child_inherited_lock_blocks_new_dispatcher(tmp_path):
    store = Store(tmp_path / "private")
    lock = open(store.private_dir / "dispatcher.lock", "a+")
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"], pass_fds=(lock.fileno(),))
    lock.close()
    dispatcher = Dispatcher(store, aggregate, None, FakeRunner)
    try:
        with pytest.raises(WorkerError, match="dispatcher_already_running"):
            dispatcher.start()
    finally:
        child.terminate()
        child.wait(timeout=5)
    dispatcher.start()
    dispatcher.stop()


def test_process_runner_jsonl_and_exact_cancel(tmp_path):
    # In-memory synthetic child only; no model or real forum data are accessed.
    child_code = "import json,sys,time\nfor line in sys.stdin:\n p=json.loads(line)\n if p['op']=='init': print(json.dumps({'type':'ready'}),flush=True)\n elif p['op']=='predict': print(json.dumps({'type':'result','item_id':p['item_id'],'result':{'prediction':[0]*6}}),flush=True)\n else: break\n"
    lock = open(tmp_path / "test.lock", "w")
    runner = ProcessRunner({"request": {}, "mode": "m1_only"}, lock_fd=lock.fileno(), cancelled=lambda: False, deadline=time.monotonic() + 5, command=[sys.executable, "-c", child_code])
    try:
        assert runner.predict(0, record())["prediction"] == [0] * 6
    finally:
        runner.close()
        lock.close()
    assert runner.process.poll() == 0


def test_process_final_gate_error_and_costs_are_not_lost(tmp_path):
    child_code = "import json,sys\nfor line in sys.stdin:\n p=json.loads(line)\n if p['op']=='init': print(json.dumps({'type':'ready'}),flush=True)\n else:\n  print(json.dumps({'type':'error','code':'source_drift','counters':{'m3_attempts':1},'cumulative_counters':{'m3_attempts':2}}),flush=True)\n  sys.exit(1)\n"
    lock = open(tmp_path / "test.lock", "w")
    runner = ProcessRunner({"request": {}, "mode": "m1_only"}, lock_fd=lock.fileno(), cancelled=lambda: False, deadline=time.monotonic() + 5, command=[sys.executable, "-c", child_code])
    try:
        with pytest.raises(WorkerError, match="source_drift") as error:
            runner.finish()
        assert error.value.metadata["cumulative_counters"]["m3_attempts"] == 2
    finally:
        runner.close()
        lock.close()


def test_cancel_stops_only_owned_subprocess(tmp_path):
    child_code = "import json,sys,time\nfor line in sys.stdin:\n p=json.loads(line)\n if p['op']=='init': print(json.dumps({'type':'ready'}),flush=True)\n else: time.sleep(10)\n"
    lock = open(tmp_path / "test.lock", "w")
    cancelled = threading.Event()
    runner = ProcessRunner({"request": {}, "mode": "m1_only"}, lock_fd=lock.fileno(), cancelled=cancelled.is_set, deadline=time.monotonic() + 5, command=[sys.executable, "-c", child_code])
    unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(10)"])
    try:
        cancelled.set()
        runner.close()
        assert runner.process.poll() is not None
        assert unrelated.poll() is None
    finally:
        runner.close()
        unrelated.terminate()
        unrelated.wait(timeout=5)
        lock.close()
