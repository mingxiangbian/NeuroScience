import json
import csv
import io
from pathlib import Path
import subprocess
import time

from fastapi.testclient import TestClient
import pytest

from topicweb.app import COST_COUNTERS, MAX_BODY, create_app, csv_cell
from topicweb.adapters import SourceError
from topicweb.core import aggregate, make_record
from topicweb import adapters


TOKEN = "synthetic-test-token-32-characters-long"


@pytest.fixture
def client(tmp_path):
    app = create_app(private_dir=tmp_path / "private", token=TOKEN, start_worker=False)
    with TestClient(app, base_url="http://127.0.0.1:8787", client=("127.0.0.1", 5678)) as session:
        session.headers["Authorization"] = "Bearer " + TOKEN
        yield session


def payload():
    return {"name": "Synthetic topic", "source": "upload", "mode": "m1_only", "upload": {"content": json.dumps([{"text": "Synthetic hello"}]), "format": "json", "filename": "synthetic.json"}}


def test_auth_all_data_routes(client):
    job = client.post("/api/jobs", json=payload()).json()["job"]
    del client.headers["Authorization"]
    for method, path in [("GET", "/api/jobs"), ("GET", f"/api/jobs/{job['id']}"), ("GET", f"/api/jobs/{job['id']}/items"), ("GET", f"/api/jobs/{job['id']}/dashboard"), ("GET", f"/api/jobs/{job['id']}/export"), ("GET", f"/api/jobs/{job['id']}/export.csv"), ("DELETE", f"/api/jobs/{job['id']}/raw"), ("DELETE", f"/api/jobs/{job['id']}"), ("GET", "/api/model-status"), ("GET", "/api/sources"), ("POST", "/api/purge")]:
        assert client.request(method, path).status_code == 401
    assert client.get("/api/health").json() == {"status": "ok"}


def test_login_cookie_and_origin_host_validation(client):
    del client.headers["Authorization"]
    assert client.post("/api/login", json={"token": "不正确"}).status_code == 401
    response = client.post("/api/login", json={"token": TOKEN})
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert client.get("/api/jobs").status_code == 200
    assert client.post("/api/jobs", json=payload(), headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.get("/api/jobs", headers={"Host": "attacker.example"}).status_code == 403
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/jobs").status_code == 401


def test_upload_summary_private_text_redaction_and_cancel(client):
    response = client.post("/api/jobs", json=payload())
    assert response.status_code == 202
    job = response.json()["job"]
    assert job["state"] == "queued" and job["total_items"] == 1
    rows = client.get(f"/api/jobs/{job['id']}/items").json()["items"]
    assert rows[0]["record"]["display_text"] == "Synthetic hello"
    assert "model_input_text" not in rows[0]["record"] and "source_payload_raw" not in rows[0]["record"]
    dashboard = client.get(f"/api/jobs/{job['id']}/dashboard").json()
    assert dashboard["summary"]["successful_items"] == 0
    assert dashboard["summary"]["neutral_rate"] is None
    assert client.post(f"/api/jobs/{job['id']}/cancel").json()["job"]["state"] == "cancelled"
    replay = client.post(f"/api/jobs/{job['id']}/replay")
    assert replay.status_code == 202 and replay.json()["job"]["id"] != job["id"]
    assert client.delete(f"/api/jobs/{job['id']}").status_code == 204
    assert client.get(f"/api/jobs/{job['id']}").status_code == 404


def test_running_delete_hides_all_outputs_immediately(client):
    job = client.post("/api/jobs", json=payload()).json()["job"]
    store = client.app.state.store
    store.claim()
    response = client.delete(f"/api/jobs/{job['id']}")
    assert response.status_code == 202 and response.json()["state"] == "deleting"
    for suffix in ("", "/items", "/dashboard", "/export"):
        assert client.get(f"/api/jobs/{job['id']}" + suffix).status_code == 410
    assert not store.put_result(job["id"], 0, {})
    store.finish_revocation(job["id"])
    assert client.get(f"/api/jobs/{job['id']}").status_code == 404


def test_budgets_and_unreviewed_source(client):
    assert client.post("/api/jobs", json={**payload(), "source": "discourse"}).status_code == 422
    bad = payload()
    bad["upload"]["content"] = json.dumps([{"text": "x" * 65537}])
    assert client.post("/api/jobs", json=bad).status_code == 422
    assert client.post("/api/jobs", content="{}", headers={"Content-Length": str(MAX_BODY + 1)}).status_code == 413
    for _ in range(8):
        assert client.post("/api/jobs", json=payload()).status_code == 202
    assert client.post("/api/jobs", json=payload()).status_code == 429


def test_json_escaping_does_not_shrink_decoded_upload_budget(client):
    request = payload()
    request["upload"]["content"] = json.dumps([{"id": str(i), "text": "\\" * 32000} for i in range(65)])
    assert len(request["upload"]["content"].encode()) < 5 * 1024 * 1024
    assert len(json.dumps(request).encode()) > 5 * 1024 * 1024
    response = client.post("/api/jobs", json=request)
    assert response.status_code == 202 and response.json()["job"]["total_items"] == 65


def test_remote_connection_refused(tmp_path):
    app = create_app(private_dir=tmp_path / "private", token=TOKEN, start_worker=False)
    with TestClient(app, base_url="http://127.0.0.1:8787", client=("192.0.2.10", 5678)) as client:
        assert client.get("/api/health").status_code == 403


def test_api_dispatcher_end_to_end_with_synthetic_runner(tmp_path):
    class FixtureRunner:
        def __init__(self, job, **kwargs):
            pass

        def predict(self, item_id, record):
            return {"prediction": [1, 0, 0, 0, 0, 0], "used_path": "m1", "fallback": False}

        def close(self):
            pass

    app = create_app(private_dir=tmp_path / "private", token=TOKEN, runner_factory=FixtureRunner)
    with TestClient(app, base_url="http://127.0.0.1:8787", client=("127.0.0.1", 5678)) as client:
        client.headers["Authorization"] = "Bearer " + TOKEN
        job_id = client.post("/api/jobs", json=payload()).json()["job"]["id"]
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            job = client.get(f"/api/jobs/{job_id}").json()["job"]
            if job["state"] == "completed":
                break
            time.sleep(0.02)
        assert job["state"] == "completed"
        dashboard = client.get(f"/api/jobs/{job_id}/dashboard").json()
        assert dashboard["summary"]["coverage"] == 1
        assert dashboard["emotions"][0]["count"] == 1
        assert dashboard["routing"]["cost_scope"] == "completed_job"
        assert dashboard["routing"]["cost_complete"] is True


def partial_job(client, terminal="failed", progress=None):
    request = payload()
    request["upload"]["content"] = json.dumps([{"text": "Synthetic first"}, {"text": "Synthetic second"}])
    job = client.post("/api/jobs", json=request).json()["job"]
    store = client.app.state.store
    store.claim()
    store.transition(job["id"], "snapshot_sealed", "inferencing")
    costs = {name: 0 for name in COST_COUNTERS}
    costs["m1_attempts"] = 1
    store.put_result(job["id"], 0, {"prediction": [0, 1, 0, 0, 0, 0], "used_path": "m1", "counters": costs})
    if terminal:
        store.transition(job["id"], "inferencing", terminal, progress=progress or {})
    return job


def test_failed_job_cumulative_cost_replaces_receipts(client):
    costs = {name: 0 for name in COST_COUNTERS}
    costs.update(m1_attempts=2, m3_attempts=1)
    job = partial_job(client, progress={"failure_cost": {"cumulative_counters": costs}})
    dashboard = client.get(f"/api/jobs/{job['id']}/dashboard").json()
    assert dashboard["routing"]["cost"] == costs
    assert dashboard["routing"]["cost_scope"] == "job_cumulative"
    assert dashboard["routing"]["cost_complete"] is True
    assert dashboard["summary"]["successful_items"] == 1


@pytest.mark.parametrize("terminal", ["failed", "cancelled", None])
def test_unacknowledged_cost_is_explicit_lower_bound(client, terminal):
    job = partial_job(client, terminal)
    routing = client.get(f"/api/jobs/{job['id']}/dashboard").json()["routing"]
    assert routing["cost"]["m1_attempts"] == 1
    assert routing["cost_scope"] == "acknowledged_items_lower_bound"
    assert routing["cost_complete"] is False


def test_incomplete_or_contradictory_cumulative_cost_is_not_trusted(client):
    job = partial_job(client, progress={"failure_cost": {"cumulative_counters": {"m3_attempts": 1}}})
    store = client.app.state.store
    path = f"/api/jobs/{job['id']}/dashboard"
    assert client.get(path).json()["routing"]["cost_complete"] is False
    store.transition(job["id"], "failed", "failed", progress={"failure_cost": {"cumulative_counters": {name: 0 for name in COST_COUNTERS}}})
    assert client.get(path).json()["routing"]["cost_scope"] == "acknowledged_items_lower_bound"


@pytest.mark.parametrize("terminal", ["failed", "cancelled"])
def test_retention_preserves_partial_dashboard_denominator(client, terminal):
    job = partial_job(client, terminal)
    store = client.app.state.store
    assert store.get(job["id"])["dashboard"] is None
    path = f"/api/jobs/{job['id']}/dashboard"
    before = client.get(path).json()
    store.purge(job["created_at"] + 7 * 86400)
    store.purge(job["created_at"] + 30 * 86400)
    assert store.items(job["id"]) == []
    assert store.get(job["id"])["total_items"] == 2
    after = client.get(path).json()
    assert before.pop("derived")["available"] is True
    derived_after = after.pop("derived")
    assert derived_after["available"] is False and derived_after["reason"] == "item_retention_expired"
    assert after == before
    assert after["summary"]["coverage"] == 0.5
    assert after["summary"]["missing_predictions"] == 1


def test_retention_preserves_queued_cancellation_denominator(client):
    job = client.post("/api/jobs", json=payload()).json()["job"]
    store = client.app.state.store
    store.cancel(job["id"])
    store.purge(job["created_at"] + 30 * 86400)
    dashboard = client.get(f"/api/jobs/{job['id']}/dashboard").json()
    assert dashboard["summary"]["eligible_items"] == 1
    assert dashboard["summary"]["missing_predictions"] == 1
    assert dashboard["summary"]["coverage"] == 0
    assert dashboard["summary"]["neutral_rate"] is None


def source_payload():
    return {"name": "Synthetic source failure", "source": "stackexchange", "mode": "m1_only",
            "query": {"site": "stackoverflow", "tags": "python", "query": "",
                      "from_utc": "2026-08-01T00:00:00Z", "to_utc": "2026-08-02T00:00:00Z",
                      "max_questions": 1, "max_items": 1}}


def wait_failed(client, job_id):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        job = response.json()["job"]
        if job["state"] == "failed":
            return job
        time.sleep(0.02)
    raise AssertionError("synthetic failed job did not reach terminal state")


def test_source_error_is_structured_and_preserves_fetch_progress(tmp_path):
    marker = "RAW_EXCEPTION_MUST_NOT_PERSIST_https://private.invalid/?token=secret"
    metadata = {"stage": "decompression", "exception_type": "ZlibError", "http_status": 200,
                "response_bytes": 12, "content_encoding": "gzip", "response_sha256": "a" * 64,
                "request_count": 1, "page": 1, "record_count": 0, "endpoint_kind": "search"}
    calls = []

    def fetch(query, *, cancelled, progress):
        calls.append(query)
        progress({"stage": "collecting", "source_stage": "response_received", "request_count": 1,
                  "page": 1, "endpoint_kind": "search", "record_count": 0})
        raise SourceError(marker, code="source_decompression_error", metadata=metadata)

    def no_inference(*args, **kwargs):
        raise AssertionError("source failure must not start inference")

    app = create_app(private_dir=tmp_path / "private", token=TOKEN, fetch=fetch, runner_factory=no_inference)
    with TestClient(app, base_url="http://127.0.0.1:8787", client=("127.0.0.1", 5678)) as client:
        client.headers["Authorization"] = "Bearer " + TOKEN
        response = client.post("/api/jobs", json=source_payload())
        assert response.status_code == 202
        job = wait_failed(client, response.json()["job"]["id"])
        assert job["error_code"] == "source_decompression_error"
        assert job["progress"]["source_error"] == metadata
        assert job["progress"]["stage"] == "collecting"
        assert job["progress"]["request_count"] == 1
        diagnostic = job["progress"]["worker_error"]
        assert diagnostic["stage"] == "fetch" and diagnostic["exception_type"] == "SourceError"
        assert 1 <= len(diagnostic["frames"]) <= 4
        assert all(set(frame) == {"file", "function", "line"} for frame in diagnostic["frames"])
        assert diagnostic["frames"][-1]["file"] == "topicweb/worker.py"
        assert marker not in json.dumps(job)
        assert job["snapshot_hash"] is None and job["completed_items"] == 0
        assert len(calls) == 1


@pytest.mark.parametrize(("failed_stage", "exception_type"), [("fetch", "KeyError"), ("validation", "TypeError"), ("seal", "ValueError")])
def test_unexpected_source_pipeline_failures_record_safe_stage(tmp_path, monkeypatch, failed_stage, exception_type):
    marker = "PRIVATE_RAW_URL_https://private.invalid/?token=do-not-store"

    def fetch(query, *, cancelled, progress):
        progress({"stage": "collecting", "source_stage": "response_received", "request_count": 2,
                  "page": 1, "endpoint_kind": "search", "record_count": 0})
        if failed_stage == "fetch":
            raise KeyError(marker)
        if failed_stage == "validation":
            return None, {}
        return [], {}

    def no_inference(*args, **kwargs):
        raise AssertionError("source failure must not start inference")

    app = create_app(private_dir=tmp_path / "private", token=TOKEN, fetch=fetch, runner_factory=no_inference)
    if failed_stage == "seal":
        def failed_seal(*args):
            raise ValueError(marker)
        monkeypatch.setattr(app.state.store, "seal", failed_seal)
    with TestClient(app, base_url="http://127.0.0.1:8787", client=("127.0.0.1", 5678)) as client:
        client.headers["Authorization"] = "Bearer " + TOKEN
        response = client.post("/api/jobs", json=source_payload())
        assert response.status_code == 202
        job = wait_failed(client, response.json()["job"]["id"])
        assert job["error_code"] == "worker_failed"
        diagnostic = job["progress"]["worker_error"]
        assert diagnostic["stage"] == failed_stage and diagnostic["exception_type"] == exception_type
        assert 1 <= len(diagnostic["frames"]) <= 4
        assert all(set(frame) == {"file", "function", "line"} and frame["file"] == "topicweb/worker.py"
                   and frame["function"] == "run_job" and type(frame["line"]) is int for frame in diagnostic["frames"])
        assert job["progress"]["request_count"] == 2
        assert "source_error" not in job["progress"]
        serialized = json.dumps(job)
        assert marker not in serialized and "traceback" not in serialized
        assert job["snapshot_hash"] is None and job["completed_items"] == 0


def comment_record():
    return make_record(source="stackexchange", site="stackoverflow", object_type="comment",
                       source_object_id="345", thread_id="123", parent_object_id="234",
                       model_input_text="Synthetic comment fixture", source_payload_raw={"body_markdown": "Synthetic comment fixture"},
                       source_url="https://stackoverflow.com/posts/234#comment345_234")


def test_comment_permalink_projection_and_export_preserve_private_bytes(client):
    store = client.app.state.store
    original = comment_record()
    job = store.create({"name": "Synthetic comment", "source": "stackexchange", "mode": "m1_only"}, [original], {"fixture": True})
    private_before = store.items(job["id"], private=True)
    database_before = store.path.read_bytes()
    with store.connect() as db:
        stored_before = db.execute("SELECT record FROM items WHERE job_id=?", (job["id"],)).fetchone()[0]
    items = client.get(f"/api/jobs/{job['id']}/items").json()["items"]
    public = items[0]["record"]
    assert public["source_url"] == "https://stackoverflow.com/questions/123#comment345_234"
    assert public["recorded_source_url"] == original["source_url"]
    assert public["model_input_hash"] == original["model_input_hash"]
    exported = client.get(f"/api/jobs/{job['id']}/export").json()["items"][0]["record"]
    assert exported == public
    assert store.items(job["id"], private=True) == private_before
    assert "recorded_source_url" not in store.items(job["id"], private=True)[0]["record"]
    assert store.get(job["id"])["snapshot_hash"] == job["snapshot_hash"]
    with store.connect() as db:
        assert db.execute("SELECT record FROM items WHERE job_id=?", (job["id"],)).fetchone()[0] == stored_before
    assert store.path.read_bytes() == database_before


@pytest.mark.parametrize("changes", [{"object_type": "question"}, {"object_type": "answer"},
                                     {"source": "upload"}, {"site": "askubuntu"},
                                     {"thread_id": "0"}, {"source_object_id": "-1"},
                                     {"parent_object_id": "1/2"}, {"thread_id": "１２３"},
                                     {"source_object_id": 345}, {"parent_object_id": None},
                                     {"thread_id": ""}, {"source_object_id": "0345"}])
def test_comment_permalink_projection_does_not_change_other_records(client, changes):
    store = client.app.state.store
    original = {**comment_record(), **changes}
    job = store.create({"name": "Synthetic projection scope", "source": "upload", "mode": "m1_only"}, [original])
    public = client.get(f"/api/jobs/{job['id']}/items").json()["items"][0]["record"]
    assert public["source_url"] == original["source_url"]
    assert "recorded_source_url" not in public
    assert store.items(job["id"], private=True)[0]["record"] == original


def test_old_dashboard_gets_readonly_derived_views_without_mutation(client):
    store = client.app.state.store
    records = [make_record(source="upload", site="upload", object_type="row", source_object_id=str(i), model_input_text=text)
               for i, text in enumerate(("SAME", "same", "other"))]
    results = [{"prediction": values, "used_path": "m1", "counters": {"m1_attempts": 1}}
               for values in ([1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0], [1, 1, 0, 0, 0, 0])]
    job = store.create({"name": "Archived aggregate fixture", "source": "upload", "mode": "m1_only"}, records)
    store.claim()
    store.transition(job["id"], "snapshot_sealed", "inferencing")
    for index, result in enumerate(results):
        store.put_result(job["id"], index, result)
    original = aggregate(records, results)
    store.transition(job["id"], "inferencing", "completed", dashboard=original)
    private_before = store.items(job["id"], private=True)
    database_before = store.path.read_bytes()
    response = client.get(f"/api/jobs/{job['id']}/dashboard").json()
    assert response["derived"]["schema_version"] == "topicweb-derived-v1"
    assert response["derived"]["views"]["normalized_unique_text"]["emotions"][0]["prevalence"] == .75
    assert response["emotions"] == original["emotions"]
    assert response["routing"]["cost"]["m1_attempts"] == 3
    assert store.get(job["id"])["dashboard"] == original
    assert store.items(job["id"], private=True) == private_before
    assert store.path.read_bytes() == database_before
    store.purge(job["created_at"] + 30 * 86400)
    after_expiry = client.get(f"/api/jobs/{job['id']}/dashboard").json()
    assert after_expiry["derived"]["available"] is False
    assert after_expiry["derived"]["reason"] == "item_retention_expired"
    assert after_expiry["emotions"] == original["emotions"]
    assert store.get(job["id"])["dashboard"] == original


def test_reviewed_discourse_api_dispatches_only_to_fixed_collector(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(adapters, "APPROVED_DISCOURSE_HOSTS", ("discuss.python.org",))

    def collect(query, *, cancelled, progress):
        calls.append(query)
        return [make_record(source="discourse", site="discuss.python.org", object_type="post", source_object_id="12", model_input_text="Synthetic Python question")], {"fixture": True}

    monkeypatch.setattr(adapters, "fetch_discourse", collect)
    class FixtureRunner:
        def __init__(self, job, **kwargs):
            pass
        def predict(self, item_id, record):
            return {"prediction": [0]*6, "used_path": "m1"}
        def close(self):
            pass
    app = create_app(private_dir=tmp_path / "private", token=TOKEN, runner_factory=FixtureRunner)
    with TestClient(app, base_url="http://127.0.0.1:8787", client=("127.0.0.1", 5678)) as client:
        client.headers["Authorization"] = "Bearer " + TOKEN
        query = {"site": "discuss.python.org", "category_id": 7, "max_topics": 2, "max_items": 10}
        response = client.post("/api/jobs", json={"name": "Synthetic Discourse", "source": "discourse", "query": query})
        assert response.status_code == 202
        job_id = response.json()["job"]["id"]
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            job = client.get(f"/api/jobs/{job_id}").json()["job"]
            if job["state"] == "completed":
                break
            time.sleep(.02)
        assert job["state"] == "completed" and calls == [query]
        sources = client.get("/api/sources").json()["sources"]
        assert next(source for source in sources if source["id"] == "discourse")["available"] is True


def test_new_completed_job_keeps_derived_aggregate_for_90_days(tmp_path):
    class FixtureRunner:
        def __init__(self, job, **kwargs):
            pass
        def predict(self, item_id, record):
            return {"prediction": [1, 0, 0, 0, 0, 0], "used_path": "m1"}
        def close(self):
            pass
    app = create_app(private_dir=tmp_path / "private", token=TOKEN, runner_factory=FixtureRunner)
    with TestClient(app, base_url="http://127.0.0.1:8787", client=("127.0.0.1", 5678)) as client:
        client.headers["Authorization"] = "Bearer " + TOKEN
        request = payload()
        request["upload"]["content"] = json.dumps([{"text": "Synthetic hello", "created_at": "2026-08-24T01:00:00Z"}])
        job = client.post("/api/jobs", json=request).json()["job"]
        store = app.state.store
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            stored = store.get(job["id"])
            if stored["state"] == "completed":
                break
            time.sleep(.02)
        assert stored["state"] == "completed"
        saved = stored["dashboard"]["derived"]
        assert saved["available"] is True
        assert saved["views"]["normalized_unique_text"]["trends"]["weekly"][0]["date"] == "2026-08-24"
        store.purge(job["created_at"] + 30 * 86400)
        assert store.items(job["id"]) == []
        assert client.get(f"/api/jobs/{job['id']}/dashboard").json()["derived"] == saved
        assert store.get(job["id"])["dashboard"]["derived"] == saved
        store.purge(job["created_at"] + 90 * 86400)
        assert client.get(f"/api/jobs/{job['id']}/dashboard").status_code == 404


def test_custom_aggregator_is_not_wrapped_or_changed(tmp_path):
    def custom(records, results, manifest, mode):
        return {"custom_fixture": True}
    app = create_app(private_dir=tmp_path / "private", token=TOKEN, start_worker=False, aggregator=custom)
    assert app.state.dispatcher.aggregate is custom
    assert app.state.dispatcher.aggregate([], [], {}, "m1_only") == {"custom_fixture": True}


def test_ui_license_link_allowlist():
    source = (Path(__file__).resolve().parents[1] / "static/app.js").read_text()
    helper = source[source.index("function approvedLicenseUrl("):source.index("\nfunction notice(")]
    valid = "https://creativecommons.org/licenses/by-nc-sa/3.0/"
    cases = [valid, None, "javascript:alert(1)", "http://creativecommons.org/licenses/by-nc-sa/3.0/",
             "https://creativecommons.org.evil.example/licenses/by-nc-sa/3.0/",
             "https://user:secret@creativecommons.org/licenses/by-nc-sa/3.0/",
             "https://creativecommons.org/other/", valid + "?redirect=evil", valid + "#fragment",
             "https://creativecommons.org:444/licenses/by-nc-sa/3.0/"]
    code = helper + "\nconsole.log(JSON.stringify(" + json.dumps(cases) + ".map(approvedLicenseUrl)));"
    result = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == [valid] + [None] * (len(cases) - 1)


def test_csv_export_uses_public_links_and_omits_all_text(client):
    store = client.app.state.store
    record = {**comment_record(), "author_display_name": "=HYPERLINK(\"https://example.invalid\")",
              "author_id_hash": "private-author-hash", "provenance": {"filename": "@file", "file_sha256": "a" * 64, "row_number": 3}}
    job = store.create({"name": "CSV fixture", "source": "upload", "mode": "m1_only"}, [record, {**record, "record_id": "other-record"}])
    store.claim(); store.transition(job["id"], "snapshot_sealed", "inferencing")
    store.put_result(job["id"], 0, {"prediction": [1, 0, 0, 0, 0, 0], "used_path": "m1", "route_requested": False, "counters": {"m1_attempts": 1}})
    response = client.get(f"/api/jobs/{job['id']}/export.csv")
    assert response.status_code == 200 and response.content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 2
    assert rows[0]["source_url"] == store.items(job["id"])[0]["record"]["source_url"]
    assert rows[0]["recorded_source_url"] == record["source_url"]
    assert rows[0]["author_display_name"] == "'" + record["author_display_name"]
    assert rows[0]["filename"] == "'@file" and rows[0]["row_number"] == "3"
    assert rows[0]["prediction_love"] == "1" and rows[0]["route_requested"] == "false"
    assert rows[1]["prediction_love"] == "" and rows[1]["m1_attempts"] == ""
    for forbidden in ("model_input_text", "source_payload_raw", "display_text", "author_id_hash"):
        assert forbidden not in rows[0]
    assert "Synthetic comment fixture" not in response.text and "private-author-hash" not in response.text


@pytest.mark.parametrize("value", ["=1+1", "+formula", "-formula", "@formula", "   =1+1", "\tname", "\rname", "\nname", "\x00=1+1", "\ufeff=1+1"])
def test_csv_formula_prefixes_are_neutralized(value):
    assert csv_cell(value) == "'" + value
    assert csv_cell(0) == "0" and csv_cell(None) == ""


def test_csv_expired_items_are_unavailable_not_empty_observations(client):
    job = client.post("/api/jobs", json=payload()).json()["job"]
    store = client.app.state.store
    store.cancel(job["id"])
    store.purge(job["created_at"] + 30 * 86400)
    assert client.get(f"/api/jobs/{job['id']}/export.csv").status_code == 410


def test_clear_raw_removes_legacy_request_copy_but_keeps_results_and_aggregate(client):
    secret = "SYNTHETIC_RAW_REMOVE_THIS_CONTENT"
    record = make_record(source="upload", site="upload", object_type="row", source_object_id="1", model_input_text=secret, source_payload_raw={"text": secret})
    result = {"prediction": [1, 0, 0, 0, 0, 0], "used_path": "m1"}
    store = client.app.state.store
    job = store.create({"name": "Raw clear fixture", "source": "upload", "mode": "m1_only"}, [record])
    store.claim(); store.transition(job["id"], "snapshot_sealed", "inferencing")
    store.put_result(job["id"], 0, result)
    dashboard = aggregate([record], [result])
    store.transition(job["id"], "inferencing", "completed", dashboard=dashboard)
    with store.connect() as db:
        db.execute("UPDATE jobs SET request=? WHERE id=?", (json.dumps({"source": "upload", "mode": "m1_only", "upload": {"content": secret}, "records": [{"text": secret}]}), job["id"]))
    response = client.delete(f"/api/jobs/{job['id']}/raw")
    assert response.status_code == 200 and response.json()["job"]["raw_expired"] == 1
    saved = store.get(job["id"], private=True)
    assert saved["state"] == "completed" and saved["snapshot_hash"] == job["snapshot_hash"]
    assert saved["dashboard"] == dashboard and saved["completed_items"] == 1
    assert "upload" not in saved["request"] and "records" not in saved["request"]
    item = store.items(job["id"], private=True)[0]
    assert item["result"] == result and item["record"]["model_input_hash"] == record["model_input_hash"]
    assert not {"display_text", "source_payload_raw", "model_input_text"} & set(item["record"])
    assert secret.encode() not in store.path.read_bytes()
    assert client.post(f"/api/jobs/{job['id']}/replay").status_code == 409
    assert client.delete(f"/api/jobs/{job['id']}/raw").status_code == 200


@pytest.mark.parametrize("state", ["queued", "fetching", "snapshot_sealed", "inferencing", "aggregating", "cancel_requested"])
def test_clear_raw_rejects_nonterminal_jobs_without_touching_input(client, state):
    job = client.post("/api/jobs", json=payload()).json()["job"]
    store = client.app.state.store
    if state != "queued":
        store.transition(job["id"], "queued", state)
    original = store.items(job["id"], private=True)
    assert client.delete(f"/api/jobs/{job['id']}/raw").status_code == 409
    assert store.items(job["id"], private=True) == original
    assert store.get(job["id"])["raw_expired"] == 0
