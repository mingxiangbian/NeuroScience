"""EXP-085 driver checks with synthetic jobs, fake HTTP and no model/server run."""
import inspect
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_staged_runtime as driver


def test_executed_archive_function_is_byte_for_byte_preserved():
    assert driver.sha(inspect.getsource(driver.archive_parent)) == "7d7351fc982bc70813f9234212986e2ca4f83a8f9996d54a501b9c0559739c52"


def previous_attempt_fixture(monkeypatch, tmp_path):
    previous = tmp_path / "private/validation/exp-085/attempt-1"
    previous.mkdir(parents=True)
    sources = {f"topicweb/source-{index}.py": driver.sha(f"source {index}") for index in range(32)}
    protocol = driver.sha("attempt one protocol")
    documents = {
        "plan": {"attempt": 1, "sources": sources, "protocol": {"sha256": protocol}},
        "run": {"attempt": 1, "status": "Stopped", "failure_code": "staged_internal_error"},
        "verification": {"attempt": 1, "status": "Failed", "error_code": "staged_lower_bound_range",
                         "exp085_complete": False, "operational_state": "stop-required"},
    }
    hashes = {}
    for name, value in documents.items():
        path = previous / (name + ".json")
        path.write_text(json.dumps(value))
        hashes[name] = driver.sha(path.read_bytes())
    archive_path = previous / "frozen-code.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        payloads = {name: f"source {index}".encode() for index, name in enumerate(sources)}
        payloads["protocol.md"] = b"attempt one protocol"
        for name, raw in payloads.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(raw)
            archive.addfile(entry, io.BytesIO(raw))
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    monkeypatch.setattr(driver, "PREVIOUS", previous)
    monkeypatch.setattr(driver, "PREVIOUS_HASHES", hashes)
    monkeypatch.setattr(driver, "PREVIOUS_ARCHIVE_SHA256", driver.sha(archive_path.read_bytes()))
    return previous, documents


def test_attempt2_is_create_only_and_previous_failure_is_hash_bound(monkeypatch, tmp_path):
    assert driver.ATTEMPT == 2 and driver.RUN.name == "attempt-2"
    assert driver.PROTOCOL.name == "exp-085-staged-website-bounded-acceptance-attempt-2.md"
    previous, _ = previous_attempt_fixture(monkeypatch, tmp_path)
    bindings = driver.previous_attempt_documents()
    expected_prefix = "private/validation/exp-085/attempt-1/"
    assert all(binding["path"].startswith(expected_prefix) for binding in bindings.values())
    assert bindings["archive"]["members"] == 33
    target = tmp_path / "attempt-2-plan.json"
    driver.once(target, {"attempt": 2})
    with pytest.raises(FileExistsError):
        driver.once(target, {"attempt": 2})
    assert not any(path.name.endswith("results.jsonl") for path in previous.iterdir())


def test_previous_terminal_drift_is_rejected(monkeypatch, tmp_path):
    previous, documents = previous_attempt_fixture(monkeypatch, tmp_path)
    documents["verification"]["error_code"] = "changed_failure"
    path = previous / "verification.json"
    path.write_text(json.dumps(documents["verification"]))
    driver.PREVIOUS_HASHES["verification"] = driver.sha(path.read_bytes())
    with pytest.raises(ValueError, match="previous_attempt_verification_terminal"):
        driver.previous_attempt_documents()


def test_previous_hash_and_archive_member_drift_are_rejected(monkeypatch, tmp_path):
    previous, _ = previous_attempt_fixture(monkeypatch, tmp_path)
    (previous / "run.json").write_text("changed")
    with pytest.raises(ValueError, match="previous_attempt_artifact_drift"):
        driver.previous_attempt_documents()
    previous, _ = previous_attempt_fixture(monkeypatch, tmp_path / "member")
    archive_path = previous / "frozen-code.tar.gz"
    with tarfile.open(archive_path, "r:gz") as archive:
        payloads = {entry.name: archive.extractfile(entry).read() for entry in archive}
    payloads["extra.py"] = b"unexpected"
    with tarfile.open(archive_path, "w:gz") as archive:
        for name, raw in payloads.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(raw)
            archive.addfile(entry, io.BytesIO(raw))
    # Replacing a trusted archive hash is insufficient: the member contract is independent.
    driver.PREVIOUS_ARCHIVE_SHA256 = driver.sha(archive_path.read_bytes())
    with pytest.raises(ValueError):
        driver.previous_attempt_documents()


def test_previous_attempt_reader_never_opens_predictions_or_journals(monkeypatch, tmp_path):
    previous, _ = previous_attempt_fixture(monkeypatch, tmp_path)
    opened = []
    original = driver.regular
    def observed(path):
        opened.append(Path(path))
        return original(path)
    monkeypatch.setattr(driver, "regular", observed)
    driver.previous_attempt_documents()
    assert set(opened) == {previous / "plan.json", previous / "run.json", previous / "verification.json",
                           previous / "frozen-code.tar.gz"}


def test_parent_archive_reads_old_code_not_current_production(monkeypatch, tmp_path):
    parent = tmp_path / "private/validation/exp-084/attempt-1"
    parent.mkdir(parents=True)
    bodies = {f"topicweb/source-{index}.py": f"old source {index}".encode() for index in range(39)}
    bodies["protocol.md"] = b"old protocol"
    path = parent / "frozen-code.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        for name, raw in bodies.items():
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
    artifact = parent / "run.json"
    artifact.write_text('{"status":"Completed"}')
    documents = {"plan": {"sources": {name: driver.sha(raw) for name, raw in bodies.items() if name != "protocol.md"},
                           "protocol": {"sha256": driver.sha(bodies["protocol.md"])}},
                 "verification": {"source_hashes": {str(artifact.relative_to(tmp_path)): driver.sha(artifact.read_bytes())}}}
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    monkeypatch.setattr(driver, "PARENT", parent)
    monkeypatch.setattr(driver, "ARCHIVE_SHA256", driver.sha(path.read_bytes()))
    assert driver.verify_parent_archive(documents)["members"] == 40
    artifact.write_text("changed terminal")
    with pytest.raises(ValueError, match="parent_artifact_drift"):
        driver.verify_parent_archive(documents)


def test_source_snapshot_payload_keeps340_order_and_exact_input(monkeypatch):
    import run_soak
    rows = []
    for ordinal in range(340):
        identity = ordinal if ordinal < 338 else ordinal - 238
        text = f"synthetic {identity}"
        rows.append({"ordinal": ordinal, "record": {"model_input_text": text, "model_input_hash": driver.sha(text)},
                     "result": {"hypothetical_route": 6 <= identity <= 30}})
    snapshot = driver.sha(driver.canonical([row["record"] for row in rows]))
    logical = driver.sha(driver.canonical(rows))
    monkeypatch.setattr(driver, "SOURCE_SNAPSHOT", snapshot)
    monkeypatch.setattr(driver, "SOURCE_LOGICAL", logical)
    monkeypatch.setattr(run_soak, "read_job", lambda *args: ({"state": "completed", "snapshot_hash": snapshot, "total_items": 340}, rows))
    metadata, content = driver.source_input(Path("synthetic-unused.sqlite3"))
    assert len(metadata) == 340 and len({row["input_sha256"] for row in metadata}) == 338
    decoded = [json.loads(line) for line in content.splitlines()]
    assert [row["id"] for row in decoded] == [f"source-{index}" for index in range(340)]
    assert [row["text"] for row in decoded] == [row["record"]["model_input_text"] for row in rows]
    rows[0]["record"]["model_input_text"] = "changed"
    with pytest.raises(ValueError, match="source_snapshot_identity"):
        driver.source_input(Path("synthetic-unused.sqlite3"))


def test_journal_seals_all_five_streams_and_replaces_started_phase(tmp_path):
    journal = driver.Journal(tmp_path)
    journal("sample", {"index": 0})
    journal("process_event", {"type": "constructor_started", "job_id": "job:m1"})
    phase = {"type": "phase_started", "logical_job_id": "job", "phase_id": "job:m1", "id": "job:m1", "phase": "m1", "status": "running", "completed_items": 0}
    journal("runtime_event", phase)
    journal("phase_receipt", {"logical_job_id": "job", "phase_id": "job:m1", "ordinal": 0, "input_sha256": "a" * 64,
                               "result": {"fallback_reason": None}})
    journal("transfer", {"logical_job_id": "job", "phase_id": "job:m3", "transfer": {}, "transfer_sha256": "b" * 64, "m1_receipts_sha256": "c" * 64})
    journal("runtime_event", {**phase, "type": "phase_terminal", "status": "completed", "completed_items": 340})
    observed = journal.snapshot()
    assert observed["phases"][0]["status"] == "completed" and len(observed["phases"]) == 1
    assert observed["counts"]["runtime_event"] == 2
    journal.close()
    assert all((tmp_path / name).read_bytes().endswith(b"\n") for name in driver.JOURNALS.values())
    with pytest.raises(FileExistsError):
        driver.Journal(tmp_path)


class API:
    def __init__(self, payload_hash, *, fail_job=None, lose_ack=False, bad_dashboard=False):
        self.payload_hash, self.fail_job, self.lose_ack, self.bad_dashboard = payload_hash, fail_job, lose_ack, bad_dashboard
        self.jobs, self.posts, self.cancels = [], [], []

    def __call__(self, path, payload=None, timeout=10):
        if path == "jobs" and payload is None:
            return {"jobs": [dict(job) for job in self.jobs]}
        if path == "jobs":
            self.posts.append(payload)
            number = len(self.posts)
            job = {"id": f"{number:032x}", "name": payload["name"], "mode": payload["mode"], "source": "upload",
                   "state": "queued", "total_items": 340, "completed_items": 0, "snapshot_hash": "d" * 64,
                   "manifest": {"file_sha256": self.payload_hash, "filename": "exp085-snapshot.jsonl"}, "error_code": None}
            self.jobs.append(job)
            if self.lose_ack:
                raise OSError("SYNTHETIC PRIVATE EXCEPTION")
            return {"job": dict(job)}
        identifier = path.split("/")[1]
        job = next(job for job in self.jobs if job["id"] == identifier)
        if path.endswith("/cancel"):
            self.cancels.append(identifier)
            job["state"] = "cancelled"
            return {"job": dict(job)}
        if path.endswith("/dashboard"):
            if self.bad_dashboard:
                raise OSError("SYNTHETIC PRIVATE EXCEPTION")
            return {"synthetic": True}
        if job["state"] == "queued":
            job["state"] = "failed" if int(identifier, 16) == self.fail_job else "completed_with_fallback" if job["mode"] == "demo" else "completed"
            job["completed_items"] = 1 if job["state"] == "failed" else 340
        return {"job": dict(job)}


def setup_execute(monkeypatch, tmp_path, **api_kwargs):
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    (tmp_path / "dashboards").mkdir()
    plan = {"payload_sha256": driver.sha("synthetic payload")}
    api = API(plan["payload_sha256"], **api_kwargs)
    journal = SimpleNamespace(model_failure=None, report=Mock())
    return api, journal, plan


def execute(api, journal, plan, tmp_path, **kwargs):
    return driver.execute_jobs(api, journal, "synthetic payload", plan, time.monotonic() + 1770, tmp_path, **kwargs)


def test_nine_http_jobs_have_frozen_order_budgets_and_dashboards(monkeypatch, tmp_path):
    api, journal, plan = setup_execute(monkeypatch, tmp_path)
    result = execute(api, journal, plan, tmp_path)
    assert result["failure_code"] is None
    assert [request["mode"] for request in api.posts] == list(driver.MODES) * 3
    assert [request["max_qwen_calls"] for request in api.posts] == [0, 500, 20] * 3
    assert len(result["logical_jobs"]) == 9 and len(list((tmp_path / "dashboards").glob("*.json"))) == 9
    assert not api.cancels


def test_failed_job_cancelled_and_later_jobs_never_submitted(monkeypatch, tmp_path):
    api, journal, plan = setup_execute(monkeypatch, tmp_path, fail_job=2)
    result = execute(api, journal, plan, tmp_path)
    assert result["failure_code"] == "logical_job_not_complete"
    assert len(api.posts) == 2 and api.cancels == [f"{2:032x}"]
    assert result["cleanup"]["terminal_confirmed"]
    assert result["logical_jobs"][-1]["api_dashboard_observed"]


def test_lost_post_ack_is_recovered_only_for_cancellation(monkeypatch, tmp_path):
    api, journal, plan = setup_execute(monkeypatch, tmp_path, lose_ack=True)
    result = execute(api, journal, plan, tmp_path)
    assert len(api.posts) == 1 and len(api.cancels) == 1
    assert result["logical_jobs"][0]["recovered_for_cancellation_only"]
    assert not result["logical_jobs"][0]["http_submission_acknowledged"]
    assert result["failure_code"] == "http_acceptance_failed"


def test_ambiguous_lost_ack_never_selects_arbitrary_job():
    first = {"id": "a" * 32}
    assert driver.recover_submission(set(), [first, {"id": "b" * 32}], {}, "c" * 64) is None


def test_blocked_reason_and_partial_unobserved_dashboard_are_explicit(monkeypatch, tmp_path):
    api, journal, plan = setup_execute(monkeypatch, tmp_path, bad_dashboard=True)
    blocked = lambda: "swap_thrashing" if api.posts else None
    result = execute(api, journal, plan, tmp_path, blocked=blocked)
    assert result["failure_code"] == result["blocked_reason"] == "swap_thrashing"
    assert len(api.posts) == 1 and len(api.cancels) == 1
    assert result["logical_jobs"][0]["api_dashboard_observed"] is False
    assert "dashboard_path" not in result["logical_jobs"][0]


def test_partial_dashboard_time_does_not_extend_cancel_cleanup(monkeypatch, tmp_path):
    api, journal, plan = setup_execute(monkeypatch, tmp_path, fail_job=1)
    clock = [100.0]
    monkeypatch.setattr(driver.time, "monotonic", lambda: clock[0])
    cancelling = [False]
    original = api.__call__
    def client(path, payload=None, timeout=10):
        if path.endswith("/cancel"):
            cancelling[0] = True
            return original(path, payload, timeout)
        if path.endswith("/dashboard"):
            clock[0] += 2
        elif cancelling[0] and path.startswith("jobs/"):
            clock[0] += 14
        return original(path, payload, timeout)
    result = execute(client, journal, plan, tmp_path)
    cleanup = result["cleanup"]
    assert cleanup["terminal_confirmed"]
    assert cleanup["ended_monotonic"] - cleanup["started_monotonic"] == 14
    assert clock[0] - cleanup["started_monotonic"] == 16
    assert result["logical_jobs"][0]["api_dashboard_observed"]


def test_nonbudget_fallback_stops_before_next_job(monkeypatch, tmp_path):
    api, journal, plan = setup_execute(monkeypatch, tmp_path)
    original = api.__call__
    def client(path, payload=None, timeout=10):
        result = original(path, payload, timeout)
        if payload and path == "jobs":
            journal.model_failure = "nonbudget_model_fallback"
        return result
    result = execute(client, journal, plan, tmp_path)
    assert result["failure_code"] == "nonbudget_model_fallback" and len(api.posts) == 1


def test_budget_or_interrupt_starts_no_job(monkeypatch, tmp_path):
    api, journal, plan = setup_execute(monkeypatch, tmp_path)
    outcome = driver.execute_jobs(api, journal, "synthetic payload", plan, time.monotonic() - 1, tmp_path)
    assert outcome["failure_code"] == "run_time_limit" and not api.posts
    outcome = execute(api, journal, plan, tmp_path, interrupted=lambda: True)
    assert outcome["failure_code"] == "run_interrupted" and not api.posts


def test_shutdown_none_thread_and_remaining_budget_are_safe():
    thread = SimpleNamespace(join=Mock(), is_alive=lambda: False)
    dispatcher = SimpleNamespace(stop_event=threading.Event(), thread=None, monitor=SimpleNamespace(thread=None), blocked_reason=None)
    app, server = SimpleNamespace(state=SimpleNamespace(dispatcher=dispatcher)), SimpleNamespace(should_exit=False)
    result = driver.stop_server(app, server, thread, time.monotonic() + 2)
    assert 0 <= thread.join.call_args.kwargs["timeout"] <= 2
    assert result["server_stopped"] and result["monitor_stopped"] and server.should_exit


def test_unconfirmed_shutdown_retains_ownership_without_model_or_run_seal(monkeypatch, tmp_path):
    monkeypatch.setattr(driver, "RUN", tmp_path)
    child_thread = SimpleNamespace(join=Mock(), is_alive=lambda: True)
    monitor = SimpleNamespace(thread=None, seen={"123|synthetic-time"})
    dispatcher = SimpleNamespace(stop_event=threading.Event(), thread=child_thread, monitor=monitor, blocked_reason="shutdown_unconfirmed")
    app = SimpleNamespace(state=SimpleNamespace(dispatcher=dispatcher))
    server = SimpleNamespace(should_exit=False)
    http_thread = SimpleNamespace(join=Mock(), is_alive=lambda: False)
    retention = Mock()
    constructor = Mock(return_value=retention)
    monkeypatch.setattr(driver.threading, "Thread", constructor)
    with pytest.raises(driver.RunFailure, match="server_shutdown_unconfirmed"):
        driver.stop_server(app, server, http_thread, time.monotonic() + 1)
    retained = json.loads((tmp_path / "shutdown-failure.json").read_text())
    assert retained["status"] == "ShutdownUnconfirmed" and retained["shutdown_budget_failed"]
    assert retained["owned_process_keys"] == ["123|synthetic-time"]
    assert constructor.call_args.kwargs["daemon"] is False
    retention.start.assert_called_once()
    assert not (tmp_path / "run.json").exists()


def test_dead_threads_do_not_hide_live_owned_child_or_retained_lock(monkeypatch, tmp_path):
    monkeypatch.setattr(driver, "RUN", tmp_path)
    process = SimpleNamespace(pid=123, poll=Mock(return_value=None), wait=Mock())
    monitor = SimpleNamespace(thread=None, seen={"123|synthetic-time"}, current_runner=SimpleNamespace(process=process))
    dispatcher = SimpleNamespace(stop_event=threading.Event(), thread=None, monitor=monitor, lock=object(), blocked_reason="owned_process_exit_unconfirmed")
    app = SimpleNamespace(state=SimpleNamespace(dispatcher=dispatcher))
    http_thread = SimpleNamespace(join=Mock(), is_alive=lambda: False)
    retention = Mock()
    constructor = Mock(return_value=retention)
    manual_wait = Mock()
    monkeypatch.setattr(driver.threading, "Thread", constructor)
    monkeypatch.setattr(driver.threading, "Event", lambda: SimpleNamespace(wait=manual_wait))
    with pytest.raises(driver.RunFailure, match="server_shutdown_unconfirmed"):
        driver.stop_server(app, SimpleNamespace(should_exit=False), http_thread, time.monotonic() + 1)
    proof = json.loads((tmp_path / "shutdown-failure.json").read_text())
    assert not proof["current_process_absent"] and not proof["dispatcher_lock_released"]
    assert proof["current_owned_pid"] == 123
    constructor.call_args.kwargs["target"]()
    process.wait.assert_called_once()
    manual_wait.assert_called_once()


@pytest.mark.parametrize("failure", [False, True])
def test_telemetry_is_enabled_before_startup_and_restored(monkeypatch, failure):
    monkeypatch.setenv("TOPICWEB_TELEMETRY", "prior-value")
    def startup():
        assert os.environ["TOPICWEB_TELEMETRY"] == "1"
        if failure:
            raise driver.RunFailure("synthetic_startup_failure")
        return 0
    monkeypatch.setattr(driver, "_run", startup)
    if failure:
        with pytest.raises(driver.RunFailure):
            driver.run()
    else:
        assert driver.run() == 0
    assert os.environ["TOPICWEB_TELEMETRY"] == "prior-value"
