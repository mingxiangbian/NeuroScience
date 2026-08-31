"""Authenticated loopback-only API; model loading belongs to the child worker."""
from __future__ import annotations

import hmac
import csv
import io
import ipaddress
import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .store import QueueFull, Store, dumps
from .worker import Dispatcher


# JSON escaping can expand a valid 5 MiB uploaded string by up to six times.
# core/adapters still enforce the 5 MiB decoded-content budget.
MAX_BODY = 6 * 5 * 1024 * 1024 + 8192
COOKIE = "topicweb_session"
COST_COUNTERS = ("m1_attempts", "m3_attempts", "m3_succeeded", "m1_cache_hit", "m3_cache_hit", "audit_extra_calls")
CSV_RECORD_FIELDS = ("record_id", "source", "site", "object_type", "source_object_id", "thread_id", "parent_object_id", "source_url", "recorded_source_url", "author_display_name", "content_license", "created_at", "updated_at", "model_input_hash", "dedup_hash")


def csv_cell(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    if (text and (ord(text[0]) < 32 or text[0] == "\ufeff")) or text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def dashboard_cost_scope(dashboard, job):
    """Final child totals replace acknowledged-item costs, never add to them."""
    routing = dashboard.setdefault("routing", {})
    acknowledged = routing.get("cost", {})
    failure = (job.get("progress") or {}).get("failure_cost") or {}
    cumulative = failure.get("cumulative_counters")
    valid = isinstance(cumulative, dict) and all(
        type(cumulative.get(name)) is int
        and cumulative[name] >= acknowledged.get(name, 0)
        and cumulative[name] >= 0
        for name in COST_COUNTERS
    )
    if valid:
        routing["cost"] = {name: cumulative[name] for name in COST_COUNTERS}
        routing["cost_scope"] = "job_cumulative"
        routing["cost_complete"] = True
    elif job["state"] in {"completed", "completed_with_fallback"}:
        routing["cost_scope"] = "completed_job"
        routing["cost_complete"] = True
    else:
        routing["cost_scope"] = "acknowledged_items_lower_bound"
        routing["cost_complete"] = False
    return dashboard


def load_token(private_dir):
    path = Path(private_dir) / "access-token"
    if path.is_symlink():
        raise ValueError("token_symlink")
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(secrets.token_urlsafe(32))
    if path.stat().st_mode & 0o077:
        raise ValueError("token_permissions")
    token = path.read_text().strip()
    if len(token) < 32:
        raise ValueError("token_too_short")
    return token


def local_host(value):
    try:
        parsed = urlsplit("//" + value)
        _ = parsed.port
        return parsed.username is None and parsed.password is None and parsed.path == "" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    except ValueError:
        return False


async def limited_json(request):
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > MAX_BODY):
        raise HTTPException(413, "upload_size_limit")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_BODY:
            raise HTTPException(413, "upload_size_limit")
    try:
        value = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, "invalid_json") from None


def create_app(*, private_dir=None, token=None, start_worker=True, runner_factory=None,
               fetch=None, parser=None, validator=None, aggregator=None,
               model_status=None, source_status=None):
    from . import adapters, core

    private_dir = private_dir or Path(__file__).resolve().parents[1] / "private"
    store = Store(private_dir)
    access_token = token or load_token(store.private_dir)
    validator = validator or core.validate_request
    parser = parser or adapters.parse_upload
    if aggregator is None:
        def aggregator(records, results, manifest=None, mode="m1_only"):
            value = core.aggregate(records, results, manifest, mode)
            value["derived"] = core.extended_views(records, results)
            return value
    default_fetch = fetch is None
    def configured_fetch(query, *, cancelled, progress):
        if query.get("site") == "stackoverflow":
            return adapters.fetch_stackexchange(query, cancelled=cancelled, progress=progress)
        if query.get("site") == "discuss.python.org":
            return adapters.fetch_discourse(query, cancelled=cancelled, progress=progress)
        raise ValueError("source_not_allowed")
    fetch = fetch or configured_fetch
    kwargs = {"runner_factory": runner_factory} if runner_factory else {}
    dispatcher = Dispatcher(store, aggregator, fetch, **kwargs)

    @asynccontextmanager
    async def lifespan(app):
        if start_worker:
            dispatcher.start()
        try:
            yield
        finally:
            if start_worker:
                dispatcher.stop()

    app = FastAPI(title="Topic Emotion Local", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.store = store
    app.state.dispatcher = dispatcher

    @app.middleware("http")
    async def security(request: Request, call_next):
        host = request.headers.get("host", "")
        if not local_host(host):
            return JSONResponse({"detail": "invalid_host"}, 403)
        # Direct connections only: reverse-proxy/X-Forwarded-For is not trusted.
        client = request.client.host if request.client else ""
        try:
            loopback = ipaddress.ip_address(client).is_loopback
        except ValueError:
            loopback = False
        if not loopback:
            return JSONResponse({"detail": "loopback_only"}, 403)
        origin = request.headers.get("origin")
        if origin and origin not in {f"http://{host}", f"https://{host}"}:
            return JSONResponse({"detail": "invalid_origin"}, 403)
        if request.url.path.startswith("/api/") and request.url.path not in {"/api/login", "/api/health"}:
            auth = request.headers.get("authorization", "")
            presented = auth[7:] if auth.startswith("Bearer ") else request.cookies.get(COOKIE, "")
            if not hmac.compare_digest(presented.encode("utf-8"), access_token.encode("utf-8")):
                return JSONResponse({"detail": "authentication_required"}, 401)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    def require_job(job_id):
        job = store.get(job_id)
        if job is None:
            raise HTTPException(404, "job_not_found")
        if job["state"] == "deleting":
            raise HTTPException(410, "job_deleting")
        return job

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.post("/api/login")
    async def login(request: Request):
        payload = await limited_json(request)
        provided = payload.get("token", "")
        if not isinstance(provided, str) or not hmac.compare_digest(provided.encode("utf-8"), access_token.encode("utf-8")):
            raise HTTPException(401, "authentication_required")
        response = JSONResponse({"authenticated": True})
        response.set_cookie(COOKIE, access_token, httponly=True, samesite="strict", max_age=8 * 3600, path="/")
        return response

    @app.post("/api/logout")
    async def logout():
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(COOKIE, path="/")
        return response

    @app.get("/api/jobs")
    async def jobs():
        return {"jobs": store.list()}

    @app.post("/api/jobs", status_code=202)
    async def create_job(request: Request):
        payload = await limited_json(request)
        try:
            normalized = validator(payload)
            records = manifest = None
            if normalized["source"] == "upload":
                upload = normalized["upload"]
                records, manifest = parser(upload["content"], upload.get("format", "jsonl"), text_column=upload.get("text_column", "text"), filename=upload.get("filename", "upload"))
            elif normalized["source"] == "discourse":
                if "discuss.python.org" not in adapters.APPROVED_DISCOURSE_HOSTS:
                    raise HTTPException(409, "source_not_reviewed")
            elif normalized["source"] != "stackexchange":
                raise HTTPException(409, "source_not_reviewed")
            elif default_fetch and not adapters.STACKEXCHANGE_FILTER_ID:
                raise HTTPException(409, "source_filter_review_required")
            job = store.create(normalized, records, manifest)
        except QueueFull:
            raise HTTPException(429, "queue_full") from None
        except (ValueError, TypeError, KeyError):
            raise HTTPException(422, "invalid_job_request") from None
        return {"job": job}

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: str):
        return {"job": require_job(job_id)}

    @app.get("/api/jobs/{job_id}/items")
    async def get_items(job_id: str, limit: int = 50, offset: int = 0):
        job = require_job(job_id)
        if not 1 <= limit <= 500 or offset < 0:
            raise HTTPException(422, "invalid_pagination")
        return {"items": store.items(job_id, limit, offset), "total": job["total_items"], "items_expired": bool(job["items_expired"])}

    @app.get("/api/jobs/{job_id}/dashboard")
    async def dashboard(job_id: str):
        job = require_job(job_id)
        rows = store.items(job_id) if not job["items_expired"] else []
        value = job["dashboard"] if job["dashboard"] is not None else aggregator(
            [row["record"] for row in rows], [row["result"] for row in rows], job["manifest"] or {}, job["mode"])
        if not job["items_expired"]:
            value["derived"] = core.extended_views([row["record"] for row in rows], [row["result"] for row in rows])
        elif "derived" not in value:
            value["derived"] = {"schema_version": core.DERIVED_SCHEMA, "available": False,
                                "reason": "item_retention_expired", "views": None, "diagnostics": None}
        return dashboard_cost_scope(value, job)

    @app.get("/api/jobs/{job_id}/export")
    async def export(job_id: str):
        job = require_job(job_id)
        # Export is authenticated and excludes complete text and source payloads.
        body = dumps({"job": job, "items": store.items(job_id)})
        return Response(body, media_type="application/json", headers={"Content-Disposition": f'attachment; filename="topic-{job_id}.json"'})

    @app.get("/api/jobs/{job_id}/export.csv")
    async def export_csv(job_id: str):
        job = require_job(job_id)
        if job["items_expired"]:
            raise HTTPException(410, "item_records_expired")
        if not job["snapshot_hash"]:
            raise HTTPException(409, "snapshot_not_sealed")
        output = io.StringIO()
        writer = csv.writer(output)
        result_fields = ("used_path", "route_requested", "hypothetical_route", "fallback_reason")
        writer.writerow(("ordinal", *CSV_RECORD_FIELDS, "filename", "file_sha256", "row_number", *result_fields, *(f"prediction_{label}" for label in core.LABELS), *COST_COUNTERS))
        for item in store.items(job_id):
            record, result = item["record"], item["result"] or {}
            prediction = result.get("prediction") or [None] * len(core.LABELS)
            counters = result.get("counters") or {}
            provenance = record.get("provenance") or {}
            row = [item["ordinal"], *(record.get(key) for key in CSV_RECORD_FIELDS),
                   *(provenance.get(key) for key in ("filename", "file_sha256", "row_number")),
                   *(result.get(key) for key in result_fields), *prediction, *(counters.get(key) for key in COST_COUNTERS)]
            writer.writerow(csv_cell(value) for value in row)
        return Response("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="topic-{job_id}.csv"'})

    @app.delete("/api/jobs/{job_id}/raw")
    async def clear_raw(job_id: str):
        require_job(job_id)
        try:
            return {"job": store.clear_raw(job_id)}
        except ValueError:
            raise HTTPException(409, "job_not_terminal") from None

    @app.post("/api/jobs/{job_id}/cancel")
    async def cancel(job_id: str):
        require_job(job_id)
        return {"job": store.cancel(job_id)}

    @app.delete("/api/jobs/{job_id}")
    async def delete(job_id: str):
        status = store.request_delete(job_id)
        if status == "missing":
            raise HTTPException(404, "job_not_found")
        if status == "deleted":
            return Response(status_code=204)
        return JSONResponse({"job_id": job_id, "state": "deleting"}, 202)

    @app.post("/api/jobs/{job_id}/replay", status_code=202)
    async def replay(job_id: str):
        require_job(job_id)
        try:
            return {"job": store.replay(job_id)}
        except QueueFull:
            raise HTTPException(429, "queue_full") from None
        except ValueError:
            raise HTTPException(409, "snapshot_not_replayable") from None

    @app.post("/api/purge")
    async def purge():
        return store.purge()

    @app.get("/api/model-status")
    async def models():
        if model_status:
            return model_status()
        return {"configured": True, "runtime": "isolated-child", "model_state": "not_loaded_by_api", "dispatcher_running": bool(dispatcher.thread and dispatcher.thread.is_alive()), "current_job": dispatcher.current_job, "weights_loaded_in_api": False, "verified": False}

    @app.get("/api/sources")
    async def sources():
        if source_status:
            return source_status()
        discourse_available = "discuss.python.org" in adapters.APPROVED_DISCOURSE_HOSTS
        return {"sources": [{"id": "upload", "available": True}, {"id": "stackexchange", "available": bool(adapters.STACKEXCHANGE_FILTER_ID), "site": "stackoverflow", "reason": None if adapters.STACKEXCHANGE_FILTER_ID else "source_filter_review_required"},
                            {"id": "discourse", "available": discourse_available, "site": "discuss.python.org", "category_id": 7,
                             "reason": None if discourse_available else "site_review_required"}]}

    static = Path(__file__).resolve().parents[1] / "static"
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="static")
    return app
