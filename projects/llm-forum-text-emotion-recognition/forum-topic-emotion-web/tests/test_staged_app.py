"""API accounting and stop-latch checks without models or real source records."""
from copy import deepcopy
import json

import pytest
from fastapi.testclient import TestClient

from topicweb.app import COST_COUNTERS, create_app, dashboard_cost_scope
from topicweb.worker import Dispatcher


def costs(**updates):
    return dict.fromkeys(COST_COUNTERS, 0) | updates


def test_prepass_is_counted_before_any_final_result():
    job = {"state": "inferencing", "progress": {"staged_execution": {
        "cumulative_counters": costs(m1_attempts=338, m1_cache_hit=2),
        "cost_complete": False, "prelude_transfer_reuses": 0}}}
    value = dashboard_cost_scope({"routing": {"cost": costs()}}, job)["routing"]
    assert value["cost"]["m1_attempts"] == 338
    assert value["cost_scope"] == "staged_known_lower_bound"
    assert value["cost_complete"] is False


@pytest.mark.parametrize("state", ["inferencing", "failed", "cancelled"])
def test_stage_two_cost_replaces_not_adds_receipts_or_raw_child_cache(state):
    job = {"state": state, "progress": {
        "staged_execution": {"cumulative_counters": costs(m1_attempts=338, m1_cache_hit=2, m3_attempts=1),
                             "cost_complete": False, "prelude_transfer_reuses": 6},
        "failure_cost": {"cumulative_counters": costs(m1_cache_hit=7, m3_attempts=1)}}}
    value = dashboard_cost_scope({"routing": {"cost": costs(m1_attempts=6)}}, job)["routing"]
    assert value["cost"] == costs(m1_attempts=338, m1_cache_hit=2, m3_attempts=1)
    assert value["prelude_transfer_reuses"] == 6
    assert value["cost_complete"] is False


@pytest.mark.parametrize("bad", [True, -1, None, "338"])
def test_bad_staged_count_never_promotes_failure_cost_or_completeness(bad):
    total = costs(m1_attempts=bad)
    job = {"state": "completed", "progress": {
        "staged_execution": {"cumulative_counters": total, "cost_complete": True},
        "failure_cost": {"cumulative_counters": costs(m1_attempts=999)}}}
    value = dashboard_cost_scope({"routing": {"cost": costs(m1_attempts=1)}}, job)["routing"]
    assert value["cost"] == costs(m1_attempts=1)
    assert value["cost_complete"] is False


def test_completed_stage_cost_and_transfer_are_separate():
    total = costs(m1_attempts=338, m1_cache_hit=2, m3_attempts=20, m3_succeeded=20)
    job = {"state": "completed_with_fallback", "progress": {"staged_execution": {
        "cumulative_counters": total, "cost_complete": True, "prelude_transfer_reuses": 340}}}
    value = dashboard_cost_scope({"routing": {"cost": deepcopy(total)}}, job)["routing"]
    assert value["cost"] == total and value["prelude_transfer_reuses"] == 340
    assert value["cost_scope"] == "staged_job_cumulative" and value["cost_complete"]


def test_dispatcher_hook_and_latch_preserve_authenticated_read_and_delete(tmp_path):
    class StubDispatcher(Dispatcher):
        runtime_strategy = "m1-receipt-transfer-v1"
        blocked_reason = None

    app = create_app(private_dir=tmp_path / "private", token="synthetic-local-token-32-characters", start_worker=False,
                     dispatcher_factory=StubDispatcher)
    with TestClient(app, base_url="http://127.0.0.1:8787", client=("127.0.0.1", 5678)) as client:
        client.headers["Authorization"] = "Bearer synthetic-local-token-32-characters"
        request = {"name": "Synthetic staged task", "source": "upload", "mode": "m1_only",
                   "upload": {"content": json.dumps([{"text": "synthetic input"}]), "format": "json"}}
        job = client.post("/api/jobs", json=request).json()["job"]
        client.post(f"/api/jobs/{job['id']}/cancel")
        app.state.dispatcher.blocked_reason = "critical_memory_pressure"
        assert client.post("/api/jobs", json=request).status_code == 409
        assert client.post(f"/api/jobs/{job['id']}/replay").status_code == 409
        model = client.get("/api/model-status").json()
        assert model["blocked_reason"] == "critical_memory_pressure" and model["runtime"] == "m1-receipt-transfer-v1"
        assert model["weights_loaded_in_api"] is False
        assert client.get(f"/api/jobs/{job['id']}/dashboard").status_code == 200
        assert client.delete(f"/api/jobs/{job['id']}").status_code == 204
        del client.headers["Authorization"]
        assert client.get("/api/model-status").status_code == 401
