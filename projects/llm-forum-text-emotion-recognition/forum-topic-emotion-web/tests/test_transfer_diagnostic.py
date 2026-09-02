"""Synthetic EXP-084 input, serial execution, adapter and fail-closed checks."""
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_transfer_diagnostic as driver


def test_all340_source_snapshot_results_and_prefix_identity(monkeypatch, tmp_path):
    rows = []
    for ordinal in range(340):
        text = f"synthetic-{ordinal}"
        rows.append({"ordinal": ordinal, "record": {"model_input_text": text, "model_input_hash": driver.digest(text)},
                     "result": {"hypothetical_route": ordinal == 6}})
    snapshot = driver.digest(driver.canonical([row["record"] for row in rows]))
    expected = [{"ordinal": row["ordinal"], "input_sha256": row["record"]["model_input_hash"],
                 "route_eligible": row["result"]["hypothetical_route"]} for row in rows]
    monkeypatch.setattr(driver, "SOURCE_SNAPSHOT", snapshot)
    database = tmp_path / "synthetic.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE jobs(id,state,snapshot_hash,total_items)")
        db.execute("INSERT INTO jobs VALUES(?,?,?,?)", (driver.SOURCE_JOB, "completed", snapshot, 340))
        db.execute("CREATE TABLE items(job_id,ordinal,record,result)")
        for row in rows:
            db.execute("INSERT INTO items VALUES(?,?,?,?)", (driver.SOURCE_JOB, row["ordinal"],
                       json.dumps(row["record"]), json.dumps(row["result"])))
        db.execute("INSERT INTO items VALUES(?,?,?,?)", ("unrelated-job", 0, "not JSON", "not JSON"))
    logical = driver.digest(driver.canonical(rows))
    records = driver.select_records(database, expected, logical)
    assert len(records) == 340 and records[6] == rows[6]["record"]
    with pytest.raises(driver.SupportError, match="source_snapshot_drift"):
        driver.select_records(database, expected, "0" * 64)
    expected[6]["route_eligible"] = False
    with pytest.raises(driver.SupportError, match="source_input_drift"):
        driver.select_records(database, expected, logical)


def result(mode, ordinal):
    routed = mode == "research" and ordinal == 6
    value = {"prediction": [0] * 6, "route_requested": routed, "hypothetical_route": ordinal == 6,
            "fallback_reason": None, "used_path": "m3" if routed else "m1",
            "resources": {"peak_rss_bytes": 1024, "mlx_peak_bytes": 0},
            "counters": {"m1_attempts": int(mode == "m1_only"), "m1_cache_hit": int(mode == "research"), "m3_attempts": int(routed),
                         "m3_succeeded": int(routed), "m3_cache_hit": 0, "audit_extra_calls": 0}}
    value.update(fingerprint="f"*64, m1_probabilities=[0.75,0.25,0.125,0.125,0.125,0.125],
                 tokenlengths={"m1":{"input_tokens":8,"used_tokens":8,"truncated":False}})
    if mode == "research":
        value.update(prelude_transfer_reuse=True, m1_execution_origin="current_run_m1_prelude_receipt")
    return value


def fixture(monkeypatch, tmp_path, fail_at=None, fail_kind="critical"):
    path = tmp_path / "events.jsonl"
    path.write_text("")
    calls, active = [], []
    monitor = SimpleNamespace(reason=None, samples=[{"index": 10}], events_path=path, set_job=lambda identifier: calls.append(("set_job", identifier)))
    def ready(*args):
        assert not active
        calls.append(("ready", None))
        return list(range(1, 11))
    def absent(*args):
        assert not active
        calls.append(("absent", None))
        return {"sample_index": 11, "absent_model_keys": ["1234|synthetic"]}
    monkeypatch.setattr(driver, "wait_ready", ready)
    monkeypatch.setattr(driver, "wait_absent", absent)
    class Runner:
        process = SimpleNamespace(pid=1234)
        def __init__(self, job):
            self.job = job
            assert not active
            active.append(job["id"])
            calls.append(("launch", job["phase"]))
        def predict(self, item_id, record):
            ordinal = int(item_id)
            calls.append((self.job["phase"], ordinal))
            if fail_at == (self.job["phase"], ordinal):
                if fail_kind == "critical":
                    monitor.reason = "critical_memory_pressure"
                    raise driver.SupportError("job_revoked")
                if fail_kind == "interrupt":
                    raise KeyboardInterrupt()
                if fail_kind == "systemexit":
                    raise SystemExit()
            return result(self.job["mode"], ordinal)
        def finish(self):
            calls.append(("finish", self.job["phase"]))
            self.close(0)
        def close(self, returncode=-15):
            if active:
                active.clear()
                calls.append(("close", self.job["phase"]))
                with path.open("a") as stream:
                    stream.write(json.dumps({"type": "process_exit", "job_id": self.job["id"], "returncode": returncode}) + "\n")
    def factory(job):
        assert job["request"]["max_qwen_calls"] == (0 if job["mode"] == "m1_only" else 1)
        assert job["request"]["audit_rate"] == 0
        return Runner(job)
    records = [{"model_input_text": f"synthetic-{i}", "model_input_hash": driver.digest(f"synthetic-{i}")} for i in range(340)]
    source_rows = [{"ordinal": i, "input_sha256": row["model_input_hash"], "route_eligible": i == 6} for i, row in enumerate(records)]
    return monitor, records, source_rows, calls, factory


def execute_fixture(tmp_path, fixture_value, **kwargs):
    monitor, records, source_rows, calls, factory = fixture_value
    with (tmp_path/"m1-results.jsonl").open("x") as m1, (tmp_path/"replay-results.jsonl").open("x") as replay:
        outcome = driver.execute(monitor, records, source_rows, factory, driver.time.monotonic()+150,
                                 {"m1_prelude":m1,"research_prefix":replay}, lambda _: None, **kwargs)
    rows = [json.loads(line) for name in ("m1-results.jsonl","replay-results.jsonl")
            for line in (tmp_path/name).read_text().splitlines()]
    return outcome, rows


def test_complete347_are_serial_and_research_waits_for_exit_and_new_quiet(monkeypatch, tmp_path):
    values = fixture(monkeypatch, tmp_path)
    out, rows = execute_fixture(tmp_path, values)
    assert out["failure_code"] is None and out["completed_jobs"] == 2 and out["completed_events"] == 347
    assert all(job["normal_exit"] for job in out["jobs"])
    assert [(row["phase"], row["ordinal"]) for row in rows] == [("m1_prelude", i) for i in range(340)] + [("research_prefix", i) for i in range(7)]
    calls = values[3]
    assert calls.index(("finish", "m1_prelude")) < calls.index(("absent", None)) < calls.index(("launch", "research_prefix"))
    assert [name for name, _ in calls].count("ready") == 2


@pytest.mark.parametrize("phase,ordinal,expected", [("m1_prelude", 3, 3), ("research_prefix", 6, 346)])
def test_failure_stops_later_phase_and_preserves_receipt_prefix(monkeypatch, tmp_path, phase, ordinal, expected):
    values = fixture(monkeypatch, tmp_path, fail_at=(phase, ordinal))
    out, rows = execute_fixture(tmp_path, values)
    assert out["failure_code"] == "critical_memory_pressure" and out["completed_events"] == len(rows) == expected
    assert out["cleanups"][-1]["models_absent_confirmed"] and out["cleanups"][-1]["terminal_confirmed"]
    assert not out["jobs"][-1]["normal_exit"]
    assert len([call for call in values[3] if call[0] == "launch"]) == (1 if phase == "m1_prelude" else 2)


@pytest.mark.parametrize("kind", ["interrupt", "systemexit"])
def test_baseexception_runs_same_cleanup(monkeypatch, tmp_path, kind):
    values = fixture(monkeypatch, tmp_path, fail_at=("m1_prelude", 0), fail_kind=kind)
    out, rows = execute_fixture(tmp_path, values)
    assert out["failure_code"] == "diagnostic_interrupted" and not rows
    assert out["cleanups"][0]["models_absent_confirmed"]
    assert len(out["jobs"]) == 1


def test_second_quiet_failure_does_not_launch_research(monkeypatch, tmp_path):
    values = fixture(monkeypatch, tmp_path)
    ready_calls = []
    def ready(*args):
        ready_calls.append(True)
        if len(ready_calls) == 2:
            raise driver.SupportError("quiet_window_not_ready")
        return list(range(1, 11))
    monkeypatch.setattr(driver, "wait_ready", ready)
    out, rows = execute_fixture(tmp_path, values)
    assert out["completed_jobs"] == 1 and len(rows) == 340 and len(out["jobs"]) == 1
    assert out["readiness_attempts"][1]["status"] == "NotReady"


def test_exit_unknown_blocks_research(monkeypatch, tmp_path):
    values = fixture(monkeypatch, tmp_path)
    def absent(*args):
        raise driver.SupportError("owned_process_exit_unconfirmed")
    monkeypatch.setattr(driver, "wait_absent", absent)
    out, rows = execute_fixture(tmp_path, values)
    assert len(rows) == 340 and len(out["jobs"]) == 1 and out["completed_jobs"] == 0
    assert not out["cleanups"][0]["models_absent_confirmed"]


def test_source_drift_between_phases_blocks_second_launch(monkeypatch, tmp_path):
    values = fixture(monkeypatch, tmp_path)
    checks = []
    def identity():
        checks.append(True)
        if len(checks) == 2:
            raise driver.SupportError("implementation_identity_drift")
    out, rows = execute_fixture(tmp_path, values, identity_check=identity)
    assert len(rows) == 340 and len(out["jobs"]) == 1 and out["failure_code"] == "implementation_identity_drift"


def test_zero_budget_prelude_rejects_hidden_m3_attempt():
    value = result("m1_only", 6)
    driver.check_prelude_result(value, True)
    value["counters"]["m3_attempts"] = 1
    with pytest.raises(driver.SupportError, match="prelude_m3_forbidden"):
        driver.check_prelude_result(value, True)


def test_failed_research_constructor_does_not_borrow_m1_exit(monkeypatch, tmp_path):
    values = fixture(monkeypatch, tmp_path)
    monitor, records, source_rows, calls, original_factory = values
    def factory(job):
        if job["phase"] == "research_prefix":
            raise driver.SupportError("constructor_failed_before_child")
        return original_factory(job)
    out, rows = execute_fixture(tmp_path, (monitor, records, source_rows, calls, factory))
    assert len(rows) == 340 and out["completed_jobs"] == 1
    assert driver.process_events(monitor.events_path)[0]["job_id"] == "exp084-m1-prelude"
    assert not out["cleanups"][0]["terminal_confirmed"]
    assert out["cleanups"][0]["models_absent_confirmed"]
    assert out["jobs"][1]["completed_items"] == 0 and not out["jobs"][1]["normal_exit"]


def test_deadline_exhausted_starts_no_child(monkeypatch, tmp_path):
    monitor, records, source_rows, calls, factory = fixture(monkeypatch, tmp_path)
    with (tmp_path / "results.jsonl").open("x") as stream:
        out = driver.execute(monitor, records, source_rows, factory, driver.time.monotonic() - 1, stream, lambda _: None)
    assert out["failure_code"] == "diagnostic_time_limit" and not out["jobs"]
    assert out["readiness_attempts"][0]["status"] == "NotReady"
    assert not calls


def test_transfer_seal_failure_preserves_completed_m1_and_blocks_research(monkeypatch, tmp_path):
    values = fixture(monkeypatch, tmp_path)
    def cannot_seal(job):
        assert job["status"] == "completed" and job["normal_exit"]
        raise driver.SupportError("transfer_seal_failed")
    out, rows = execute_fixture(tmp_path, values, on_prelude_complete=cannot_seal)
    assert len(rows) == 340 and out["completed_jobs"] == 1
    assert len(out["jobs"]) == 1 and out["jobs"][0]["status"] == "completed"
    assert out["failure_code"] == "transfer_seal_failed" and not out["cleanups"]
    assert ("launch", "research_prefix") not in values[3]


@pytest.mark.parametrize("change", [None, "partial", "fingerprint"])
def test_transfer_seals_exactly_current_run_receipts(monkeypatch, tmp_path, change):
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    run = tmp_path/"private/validation/exp-084/attempt-1"
    run.mkdir(parents=True)
    records = [{"phase": "m1_prelude", "ordinal": i, "input_sha256": driver.digest(f"synthetic-{i}"),
                "result": result("m1_only", i)} for i in range(340)]
    if change == "partial":
        records.pop()
    if change == "fingerprint":
        records[-1]["result"]["fingerprint"] = "e"*64
    source = run/"m1-results.jsonl"
    with source.open("x") as stream:
        for row in records:
            driver.append(stream, row)
    source_before = source.read_bytes()
    metadata = [{"input_sha256": row["input_sha256"]} for row in records]
    job = {"id": "exp084-m1-prelude", "status": "completed", "completed_items": 340,
           "normal_exit": True, "exit_observation": {"sample_index": 35}}
    target = run/"transfer.json"
    if change:
        with pytest.raises(driver.SupportError):
            driver.seal_transfer(target, source, metadata, job)
        assert not target.exists()
        return
    hashed = driver.seal_transfer(target, source, metadata, job)
    transfer = json.loads(target.read_text())
    assert hashed == driver.digest(target.read_bytes())
    assert transfer["source_results_sha256"] == driver.digest(source_before)
    assert transfer["source_results_path"] == "private/validation/exp-084/attempt-1/m1-results.jsonl"
    assert len(transfer["entries"]) == 7 and source.read_bytes() == source_before
    for entry, row in zip(transfer["entries"], records):
        assert entry["source_result_sha256"] == driver.digest(driver.canonical(row))
        assert entry["m1_probabilities"] == row["result"]["m1_probabilities"]
        assert entry["tokenlengths"] == row["result"]["tokenlengths"]
    assert "model_input_text" not in target.read_text()
    with pytest.raises(FileExistsError):
        driver.seal_transfer(target, source, metadata, job)


def test_replay_does_not_count_as_physical_m1_work():
    value = result("research", 6)
    driver.check_replay_result(value, 6)
    value["counters"]["m1_attempts"] = 1
    with pytest.raises(driver.SupportError, match="replay_cost_or_origin"):
        driver.check_replay_result(value, 6)
