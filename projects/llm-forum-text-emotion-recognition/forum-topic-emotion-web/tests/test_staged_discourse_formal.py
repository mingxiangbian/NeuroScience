"""EXP-086 producer tests use fake source/API/server components only."""
import io
import json
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
import run_staged_discourse_formal as runner


class SourceJournal:
    def __init__(self):
        self.rows = []

    def source_progress(self, value):
        self.rows.append(value)


def gates(journal):
    return [row for row in journal.rows if row["stage"] == "source_count_gate"]


def test_atomic_source_gate_accepts400_before_caller_can_start_phase():
    journal, order = SourceJournal(), []
    def fetch(request, *, cancelled, progress):
        progress({"stage": "collecting", "record_count": 100})
        return [{}] * 400, {"record_count": 400}
    gated = runner.gate_fetch(journal, lambda: "a" * 32, fetch)
    records, _ = gated(runner.QUERY, cancelled=lambda: False, progress=lambda value: None)
    order.extend(row["stage"] for row in journal.rows)
    order.append("phase_started")
    assert len(records) == 400 and gates(journal) == [{"stage": "source_count_gate", "record_count": 400,
        "status": "accepted", "logical_job_id": "a" * 32, "monotonic": gates(journal)[0]["monotonic"]}]
    assert order.index("source_count_gate") < order.index("phase_started")


def test_atomic_source_gate_rejects250_without_returning_records():
    from topicweb.adapters import SourceError
    journal = SourceJournal()
    gated = runner.gate_fetch(journal, lambda: "b" * 32,
                              lambda *args, **kwargs: ([{}] * 250, {"record_count": 250}))
    with pytest.raises(SourceError):
        gated(runner.QUERY, cancelled=lambda: False, progress=lambda value: None)
    assert len(gates(journal)) == 1 and gates(journal)[0]["status"] == "rejected_before_model"
    assert gates(journal)[0]["record_count"] == 250


def test_source_error_records_zero_rejected_gate_without_partial_raw():
    from topicweb.adapters import SourceError
    journal = SourceJournal()
    def failed(*args, **kwargs):
        raise SourceError("synthetic private source error", metadata={"stage": "http", "record_count": 0})
    gated = runner.gate_fetch(journal, lambda: "c" * 32, failed)
    with pytest.raises(SourceError):
        gated(runner.QUERY, cancelled=lambda: False, progress=lambda value: None)
    assert len(gates(journal)) == 1 and gates(journal)[0]["record_count"] == 0
    assert not any("synthetic private source error" in json.dumps(row) for row in journal.rows)


def test_formal_journal_preserves_binding_and_clock_but_no_text(tmp_path):
    journal = runner.FormalJournal(tmp_path)
    before = journal.snapshot()
    assert runner.network_attestation(before) == {"source_network_authorized": True,
        "source_network_attempted": False, "source_network_fetched": False, "source_response_count": 0}
    journal.source_progress({"stage": "collecting", "source_stage": "request_started", "record_count": 0,
                             "logical_job_id": "d" * 32, "monotonic": 10.5})
    journal.source_progress({"stage": "collecting", "source_stage": "response_received", "record_count": 10,
                             "logical_job_id": "d" * 32, "monotonic": 11.5})
    journal.source_progress({"stage": "source_count_gate", "record_count": 350, "status": "accepted",
                             "logical_job_id": "d" * 32, "monotonic": 12.5, "raw": "DO NOT SAVE"})
    assert runner.network_attestation(journal.snapshot()) == {"source_network_authorized": True,
        "source_network_attempted": True, "source_network_fetched": True, "source_response_count": 1}
    journal.close()
    text = (tmp_path / "source-progress.jsonl").read_text()
    saved = [json.loads(line) for line in text.splitlines()][-1]
    assert saved["logical_job_id"] == "d" * 32 and saved["monotonic"] == 12.5
    assert "raw" not in saved and "DO NOT SAVE" not in text


class FakeJournal:
    def __init__(self):
        self.rows, self.reports = [], []

    def source_progress(self, value): self.rows.append(value)
    def report(self, value): self.reports.append(value)


class API:
    def __init__(self, *, fail=False, lose_ack=False):
        self.fail, self.lose_ack, self.posts, self.cancels = fail, lose_ack, 0, 0
        self.job = None

    def __call__(self, path, payload=None, timeout=10):
        if path == "jobs":
            self.posts += 1
            self.job = {"id": "e" * 32, "name": "EXP-086 Python Help staged formal", "source": "discourse",
                        "mode": "research", "state": "queued", "total_items": 0, "completed_items": 0,
                        "snapshot_hash": None, "error_code": None, "manifest": None}
            if self.lose_ack: raise OSError("private lost ack")
            return {"job": dict(self.job)}
        if path.endswith("/cancel"):
            self.cancels += 1
            self.job["state"] = "cancelled"
            return {"job": dict(self.job)}
        if path.endswith("/dashboard"):
            return {"source": {"records": 350}}
        self.job.update(state="failed" if self.fail else "completed", total_items=350,
                        completed_items=0 if self.fail else 350, snapshot_hash="f" * 64,
                        error_code="source_network_error" if self.fail else None,
                        manifest={"record_count": 350, "requests": [{}], "stop_reason": "source_exhausted"})
        return {"job": dict(self.job)}


def execute(tmp_path, api, journal=None, **kwargs):
    journal = journal or FakeJournal()
    local_jobs = lambda: [dict(api.job)] if api.job else []
    local_job = lambda _: dict(api.job)
    return runner.execute(api, local_jobs, local_job, journal, time.monotonic()+100, tmp_path,
                          identity_check=lambda: None, **kwargs), journal


def test_complete_job_saves_dashboard_and_manifest_progress(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    outcome, journal = execute(tmp_path, API())
    assert outcome["failure_code"] is None and outcome["logical_jobs"][0]["status"] == "completed"
    assert outcome["logical_jobs"][0]["budget"] == 500
    assert (tmp_path / "dashboard.json").is_file()
    assert journal.rows[-1]["stage"] == "manifest" and journal.rows[-1]["record_count"] == 350


def test_source_failure_cancels_and_stops(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    api = API(fail=True)
    outcome, _ = execute(tmp_path, api)
    assert outcome["failure_code"] == "formal_job_not_complete" and api.cancels == 1
    assert outcome["cleanup"]["terminal_confirmed"]


def test_lost_ack_is_only_recovered_for_cancellation(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    api = API(lose_ack=True)
    outcome, _ = execute(tmp_path, api)
    assert api.posts == 1 and api.cancels == 1
    assert outcome["logical_jobs"][0]["recovered_for_cancellation_only"]
    assert outcome["failure_code"] == "formal_driver_error"


def test_resource_block_before_post_starts_no_job(tmp_path):
    api = API()
    outcome, _ = execute(tmp_path, api, blocked=lambda: "critical_memory_pressure")
    assert api.posts == 0 and outcome["failure_code"] == "formal_precondition_stopped"
    assert outcome["logical_jobs"] == []


def test_empty_pre_submission_stop_never_indexes_a_logical_job():
    outcome = {"logical_jobs": [], "failure_code": "critical_memory_pressure"}
    job = runner.first_logical_job(outcome)
    assert job is None and outcome["failure_code"] == "critical_memory_pressure"


def parent_fixture(monkeypatch, tmp_path):
    parent = tmp_path / "private/validation/exp-085/attempt-2"
    parent.mkdir(parents=True)
    sources = {f"topicweb/source-{index}.py": runner.sha(f"source {index}") for index in range(32)}
    documents = {"plan": {"sources": sources, "protocol": {"sha256": runner.sha("protocol")}},
                 "run": {"experiment_id": "EXP-085", "attempt": 2, "status": "Completed", "failure_code": None},
                 "verification": {"experiment_id": "EXP-085", "attempt": 2, "status": "Passed", "exp085_complete": True,
                                  "safety": {"gate_passed": True}, "operational_state": "safe-to-continue"}}
    hashes = {}
    for name, value in documents.items():
        path = parent / (name + ".json")
        path.write_text(json.dumps(value))
        hashes[name] = runner.sha(path.read_bytes())
    archive_path = parent / "frozen-code.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        payloads = {name: f"source {index}".encode() for index, name in enumerate(sources)}
        payloads["protocol.md"] = b"protocol"
        for name, raw in payloads.items():
            entry = tarfile.TarInfo(name); entry.size = len(raw)
            archive.addfile(entry, io.BytesIO(raw))
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "PARENT", parent)
    monkeypatch.setattr(runner, "PARENT_HASHES", hashes)
    monkeypatch.setattr(runner, "PARENT_ARCHIVE_SHA256", runner.sha(archive_path.read_bytes()))
    return parent, documents


def test_parent_success_and_archive_are_required(monkeypatch, tmp_path):
    parent, documents = parent_fixture(monkeypatch, tmp_path)
    _, bindings = runner.parent_gate()
    assert bindings["archive"]["members"] == 33
    documents["verification"]["operational_state"] = "stop-required"
    path = parent / "verification.json"
    path.write_text(json.dumps(documents["verification"]))
    runner.PARENT_HASHES["verification"] = runner.sha(path.read_bytes())
    with pytest.raises(runner.RunFailure, match="parent_verification_not_safe"):
        runner.parent_gate()


def test_parent_hash_drift_is_rejected(monkeypatch, tmp_path):
    parent, _ = parent_fixture(monkeypatch, tmp_path)
    (parent / "run.json").write_text("changed")
    with pytest.raises(runner.RunFailure, match="parent_artifact_drift"):
        runner.parent_gate()


def test_shutdown_failure_is_scoped_to_exp086(monkeypatch, tmp_path):
    dispatcher = SimpleNamespace(stop_event=threading.Event(), thread=None, lock=object(), blocked_reason="shutdown",
                                 monitor=SimpleNamespace(thread=None, current_runner=None, seen=set()))
    app = SimpleNamespace(state=SimpleNamespace(dispatcher=dispatcher))
    http = SimpleNamespace(join=Mock(), is_alive=lambda: False)
    journal = SimpleNamespace(snapshot=lambda: {"monitor_terminal": None}, report=Mock())
    retention = Mock()
    monkeypatch.setattr(runner.threading, "Thread", Mock(return_value=retention))
    with pytest.raises(runner.RunFailure, match="server_shutdown_unconfirmed"):
        runner.stop_server(app, SimpleNamespace(should_exit=False), http, time.monotonic()+1, journal, tmp_path)
    assert json.loads((tmp_path / "shutdown-failure.json").read_text())["experiment_id"] == "EXP-086"
    assert retention.start.called and not (tmp_path / "run.json").exists()
