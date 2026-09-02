import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]/"scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("exp082_driver_tested", SCRIPTS/"run_m3_diagnostic.py")
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def test_prefix_only_and_frozen_identity(tmp_path):
    path = tmp_path/"source.sqlite3"
    expected = [{"ordinal": i, "input_sha256": driver.digest(f"synthetic-{i}"), "route_eligible": i == 6} for i in range(7)]
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE jobs(id,state,snapshot_hash,total_items)")
        db.execute("INSERT INTO jobs VALUES(?,?,?,?)", (driver.SOURCE_JOB, "completed", driver.SOURCE_SNAPSHOT, 340))
        db.execute("CREATE TABLE items(job_id,ordinal,record)")
        for row in expected:
            db.execute("INSERT INTO items VALUES(?,?,?)", (driver.SOURCE_JOB, row["ordinal"], json.dumps({
                "model_input_text": f"synthetic-{row['ordinal']}", "model_input_hash": row["input_sha256"]})))
        db.execute("INSERT INTO items VALUES(?,?,?)", (driver.SOURCE_JOB, 7, "NOT JSON: must not be read"))
    assert len(driver.select_prefix(path, expected)) == 7
    expected[0]["input_sha256"] = "0"*64
    with pytest.raises(driver.SupportError, match="source_input_drift"):
        driver.select_prefix(path, expected)


def result(ordinal):
    return {"prediction": [0]*6, "route_requested": ordinal == 6, "fallback_reason": None,
            "used_path": "m3" if ordinal == 6 else "m1", "resources": {"peak_rss_bytes": 1024, "mlx_peak_bytes": 0}}


def fixture(monkeypatch, tmp_path, stop=False):
    event_path = tmp_path/"events.jsonl"
    event_path.write_text("")
    monitor = SimpleNamespace(reason=None, samples=[{"index": 10}], events_path=event_path, set_job=lambda _: None)
    monkeypatch.setattr(driver, "wait_ready", lambda *args: list(range(1, 11)))
    monkeypatch.setattr(driver, "wait_absent", lambda *args: {"sample_index": 11, "absent_model_keys": ["1234|synthetic"]})
    calls = []
    class Runner:
        process = SimpleNamespace(pid=1234)
        def predict(self, item_id, record):
            ordinal = int(item_id)
            calls.append(ordinal)
            if stop and ordinal == 6:
                monitor.reason = "critical_memory_pressure"
                raise driver.WorkerError("job_revoked")
            return result(ordinal)
        def finish(self):
            calls.append("finish")
        def close(self):
            event_path.write_text(json.dumps({"type": "process_exit", "returncode": -15})+"\n")
            calls.append("close")
    records = [{"model_input_text": f"synthetic-{i}", "model_input_hash": driver.digest(f"synthetic-{i}")} for i in range(7)]
    def factory(job):
        assert job["mode"] == "research" and job["request"]["max_qwen_calls"] == 1
        return Runner()
    return monitor, records, calls, factory


def test_exactly_seven_then_original_finish(monkeypatch, tmp_path):
    monitor, records, calls, factory = fixture(monkeypatch, tmp_path)
    with (tmp_path/"results.jsonl").open("x") as stream:
        out = driver.execute(monitor, records, factory, driver.time.monotonic()+165, stream, lambda _: None)
    assert calls == [*range(7), "finish"]
    assert out["completed_events"] == 7 and out["failure_code"] is None
    assert out["job"]["normal_exit"] is True


def test_critical_preserves_six_and_never_retries(monkeypatch, tmp_path):
    monitor, records, calls, factory = fixture(monkeypatch, tmp_path, stop=True)
    with (tmp_path/"results.jsonl").open("x") as stream:
        out = driver.execute(monitor, records, factory, driver.time.monotonic()+165, stream, lambda _: None)
    assert calls == [*range(7), "close"]
    assert out["completed_events"] == 6 and out["failure_code"] == "critical_memory_pressure"
    assert out["job"]["status"] == "cancelled" and out["cleanup"]["models_absent_confirmed"] is True


def test_not_ready_starts_no_child(monkeypatch, tmp_path):
    monitor, records, calls, factory = fixture(monkeypatch, tmp_path)
    def not_ready(*args):
        raise driver.SupportError("quiet_window_not_ready")
    monkeypatch.setattr(driver, "wait_ready", not_ready)
    with (tmp_path/"results.jsonl").open("x") as stream:
        out = driver.execute(monitor, records, factory, driver.time.monotonic()+165, stream, lambda _: None)
    assert not calls and out["job"] is None and out["completed_events"] == 0
    assert out["readiness"]["status"] == "NotReady"


@pytest.mark.parametrize("mutate", [
    lambda value: value.update(fallback_reason="m3_budget_exhausted"),
    lambda value: value["resources"].update(mlx_peak_bytes=10_000_000_001),
    lambda value: value.update(route_requested=False),
])
def test_seventh_item_cannot_hide_failure(mutate):
    value = result(6)
    mutate(value)
    with pytest.raises(driver.SupportError):
        driver.check_result(value, 6)


def test_untrusted_error_text_is_not_logged():
    assert driver.safe_error(ValueError("private text")) == "diagnostic_driver_error"


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit])
def test_interrupt_uses_same_cleanup(monkeypatch, tmp_path, interrupt):
    monitor, records, calls, factory = fixture(monkeypatch, tmp_path)
    runner = factory({"mode": "research", "request": {"max_qwen_calls": 1}})
    def interrupted(*args):
        raise interrupt()
    runner.predict = interrupted
    with (tmp_path/"results.jsonl").open("x") as stream:
        out = driver.execute(monitor, records, lambda _: runner, driver.time.monotonic()+150, stream, lambda _: None)
    assert calls == ["close"]
    assert out["failure_code"] == "diagnostic_interrupted"
    assert out["cleanup"]["models_absent_confirmed"] is True
