"""Bounded source readers. Model input is always the original selected string."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
import zlib
from datetime import datetime, timezone
from pathlib import PurePath
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .core import ValidationError, make_record


MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ITEMS = 500
MAX_TEXT_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REQUESTS = 30
MAX_FETCH_SECONDS = 300
STACKEXCHANGE_HOST = "api.stackexchange.com"
# The reviewed filter adds comment.body to expose native body_markdown.
# HTML is never a model input or a fallback for missing Markdown.
STACKEXCHANGE_FILTER_ID: str | None = "nFzTOPGAOEckIq4PwsL9Jd"
STACKEXCHANGE_FILTER_SPEC = {
    "base": "nFzTOPGAOEckIq4Pwr_RZ8",
    "include": "comment.body",
    "unsafe": "true",
}
# Reviewed for bounded, anonymous, noncommercial collection on 2026-08-31.
APPROVED_DISCOURSE_HOSTS: tuple[str, ...] = ("discuss.python.org",)
DISCOURSE_MAX_REQUESTS = 160
DISCOURSE_MAX_SECONDS = 900
DISCOURSE_MIN_INTERVAL = 1.0
DISCOURSE_LICENSE = "CC BY-NC-SA 3.0"
DISCOURSE_LICENSE_URL = "https://creativecommons.org/licenses/by-nc-sa/3.0/"


class SourceError(ValidationError):
    """Invalid or unsafe source input; messages never include source text."""

    CODES = frozenset({
        "source_validation_error", "source_http_error", "source_network_error",
        "source_response_limit", "source_decompression_error", "source_content_encoding_unsupported",
        "source_utf8_error", "source_json_error", "source_wrapper_error", "source_api_error",
        "source_body_markdown_missing",
        "source_raw_missing", "source_resource_limit",
    })

    def __init__(self, message: str, *, code: str = "source_validation_error", metadata: dict | None = None):
        super().__init__(message)
        self.code = code if code in self.CODES else "source_validation_error"
        self.metadata = _safe_metadata(metadata or {})


def _safe_metadata(metadata: dict) -> dict:
    safe = {}
    categories = {
        "stage": {"request", "http", "read", "decompression", "utf8", "json", "wrapper", "validation", "record"},
        "content_encoding": {"missing", "identity", "gzip", "deflate", "unsupported"},
        "endpoint_kind": {"search", "answers", "comments", "category", "topic", "topic_posts"},
        "exception_type": {"SourceError", "HTTPError", "URLError", "TimeoutError", "OSError",
                           "ConnectionError", "ConnectionResetError", "RemoteDisconnected", "IncompleteRead",
                           "SSLError", "SSLCertVerificationError", "UnicodeDecodeError", "JSONDecodeError",
                           "RecursionError", "BadGzipFile", "EOFError", "ZlibError", "Exception"},
    }
    for key, values in categories.items():
        if isinstance(metadata.get(key), str) and metadata[key] in values:
            safe[key] = metadata[key]
    for key in ("http_status", "response_bytes", "request_count", "page", "record_count"):
        value = metadata.get(key)
        if type(value) is int and value >= 0 and (key != "http_status" or 100 <= value <= 599):
            safe[key] = value
    digest = metadata.get("response_sha256")
    if isinstance(digest, str) and re.fullmatch(r"[a-f0-9]{64}", digest):
        safe["response_sha256"] = digest
    return safe


def _exception_type(error: BaseException) -> str:
    if isinstance(error, zlib.error):
        return "ZlibError"
    candidate = type(error).__name__
    return _safe_metadata({"exception_type": candidate}).get("exception_type", "Exception")


def _encoding(value: Any) -> str:
    if value is None or value == "":
        return "missing"
    if isinstance(value, str) and value.strip().lower() in {"identity", "gzip", "deflate"}:
        return value.strip().lower()
    return "unsupported"


def _inflate_bounded(data: bytes, wbits: int, metadata: dict) -> bytes:
    """Bound every incremental output, including concatenated gzip members."""
    output = bytearray()
    pending = data
    try:
        while pending:
            stream = zlib.decompressobj(wbits)
            position = 0
            trailing = b""
            while position < len(pending):
                chunk = pending[position:position + 65536]
                position += len(chunk)
                output.extend(stream.decompress(chunk, MAX_RESPONSE_BYTES - len(output) + 1))
                if len(output) > MAX_RESPONSE_BYTES:
                    raise SourceError("Expanded API response exceeds 2 MiB", code="source_response_limit",
                                      metadata={**metadata, "stage": "decompression"})
                if stream.eof:
                    trailing = stream.unused_data + pending[position:]
                    break
            if not stream.eof:
                raise zlib.error("Incomplete compressed response")
            if not trailing:
                return bytes(output)
            if wbits != 31 or not trailing.startswith(b"\x1f\x8b"):
                raise zlib.error("Unexpected compressed response trailer")
            pending = trailing
        raise zlib.error("Empty compressed response")
    except zlib.error as error:
        raise SourceError("API response decompression failed", code="source_decompression_error",
                          metadata={**metadata, "stage": "decompression", "exception_type": "ZlibError"}) from error


def _decode_response(data: bytes, metadata: dict) -> bytes:
    encoding = metadata["content_encoding"]
    if encoding == "unsupported":
        raise SourceError("Unsupported API response encoding", code="source_content_encoding_unsupported",
                          metadata={**metadata, "stage": "decompression"})
    # A proxy or an early API error can return an uncompressed JSON wrapper,
    # including when the proxy leaves the original compression header intact.
    if data.lstrip(b" \t\r\n").startswith((b"{", b"[")):
        return data
    if encoding == "deflate":
        wrapped = len(data) >= 2 and (data[0] & 15) == 8 and (data[0] >> 4) <= 7 and (data[0] * 256 + data[1]) % 31 == 0
        return _inflate_bounded(data, zlib.MAX_WBITS if wrapped else -zlib.MAX_WBITS, metadata)
    if encoding == "gzip" or encoding == "missing" or data.startswith(b"\x1f\x8b"):
        return _inflate_bounded(data, 31, metadata)
    return data


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json(text: str) -> Any:
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise SourceError("Duplicate JSON object key")
            result[key] = value
        return result

    def nonfinite(_):
        raise SourceError("Non-finite JSON value")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceError("Text must be a non-empty string")
    if len(value.encode("utf-8")) > MAX_TEXT_BYTES:
        raise SourceError("Text exceeds 64 KiB")
    return value


def _url(value: Any, host: str | None = None) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or len(value) > 4096 or any(ord(char) < 32 for char in value):
        raise SourceError("Invalid source URL")
    parsed = urlparse(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise SourceError("Invalid source URL") from exc
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or port not in (None, 80, 443)
            or (host is not None and parsed.hostname != host)):
        raise SourceError("Invalid source URL")
    return value


def _timestamp(value: Any, *, required: bool = False) -> tuple[str | None, int | None]:
    if value in (None, "") and not required:
        return None, None
    try:
        if isinstance(value, bool):
            raise ValueError
        if isinstance(value, int):
            parsed = datetime.fromtimestamp(value, timezone.utc)
        elif isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError
            parsed = parsed.astimezone(timezone.utc)
        else:
            raise ValueError
        return parsed.isoformat().replace("+00:00", "Z"), int(parsed.timestamp())
    except (ValueError, OverflowError, OSError) as exc:
        raise SourceError("Timestamp must include a timezone or be integer Unix seconds") from exc


def _record(*, text: Any, source: str, site: str, kind: str, source_id: str,
            source_url: Any, created_at: Any, payload: dict, provenance: dict) -> dict:
    original = _text(text)
    stamp, _ = _timestamp(created_at)
    owner = payload.get("owner")
    owner = owner if isinstance(owner, dict) else {}
    return make_record(
        source=source, site=site, object_type=kind, source_object_id=source_id,
        source_url=_url(source_url), created_at=stamp, updated_at=payload.get("last_edit_date"), model_input_text=original,
        source_payload_raw=payload, provenance=provenance,
        parent_object_id=str(payload["post_id"]) if payload.get("post_id") is not None
        else str(payload["question_id"]) if kind == "answer" and payload.get("question_id") is not None else None,
        thread_id=str(provenance["question_id"]) if provenance.get("question_id") is not None
        else str(provenance["topic_id"]) if provenance.get("topic_id") is not None else None,
        author_display_name=owner.get("display_name"),
        author_id_hash=_sha(f"{site}:{owner['user_id']}") if "user_id" in owner else None,
        content_license=payload.get("content_license"),
    )


def parse_upload(content: str, format: str, text_column: str = "text",
                 filename: str = "upload") -> tuple[list[dict], dict]:
    """Read CSV, a JSON object array, or JSONL without changing text or using labels."""
    if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_UPLOAD_BYTES:
        raise SourceError("Upload exceeds 5 MiB or is not decoded UTF-8 text")
    if format not in ("csv", "json", "jsonl"):
        raise SourceError("Upload format must be csv, json, or jsonl")
    if not isinstance(text_column, str) or not text_column or len(text_column) > 128:
        raise SourceError("Invalid text column")
    digest = _sha(content)
    rows: list[tuple[dict, int | None]] = []
    try:
        if format == "csv":
            reader = csv.DictReader(io.StringIO(content.removeprefix("\ufeff"), newline=""))
            if (not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames)
                    or text_column not in reader.fieldnames):
                raise SourceError("CSV requires a unique text column")
            previous_line = reader.line_num
            for row in reader:
                if None in row:
                    raise SourceError("CSV row has extra columns")
                rows.append((row, previous_line + 1))
                previous_line = reader.line_num
                if len(rows) > MAX_ITEMS:
                    raise SourceError("Upload exceeds 500 records")
        elif format == "json":
            decoded = _json(content)
            if not isinstance(decoded, list):
                raise SourceError("JSON upload must be an array of objects")
            rows = [(row, None) for row in decoded]
        else:
            for line_number, line in enumerate(content.splitlines(), 1):
                if line.strip():
                    rows.append((_json(line), line_number))
                    if len(rows) > MAX_ITEMS:
                        raise SourceError("Upload exceeds 500 records")
    except (json.JSONDecodeError, csv.Error, RecursionError) as exc:
        raise SourceError("Upload cannot be parsed as the selected format") from exc
    if not rows or len(rows) > MAX_ITEMS:
        raise SourceError("Upload must contain 1 to 500 records")
    records = []
    for ordinal, (row, line_number) in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise SourceError("Every upload record must be an object")
        # Do not retain unknown fields, labels, or surrounding conversation context.
        payload = {key: row[key] for key in (text_column, "id", "url", "created_at") if key in row}
        supplied_id = payload.get("id")
        if supplied_id is not None and (isinstance(supplied_id, bool)
                                       or not isinstance(supplied_id, (str, int))):
            raise SourceError("Optional source id must be a string or integer")
        records.append(_record(
            text=payload.get(text_column), source="upload", site="upload", kind="row",
            source_id=f"{digest}:{ordinal}", source_url=payload.get("url"),
            created_at=payload.get("created_at"), payload=payload,
            provenance={"file_sha256": digest, "filename": PurePath(str(filename)).name,
                        "row_number": ordinal, "line_number": line_number,
                        "supplied_id": supplied_id, "text_field": text_column},
        ))
    return records, {
        "source": "upload", "format": format, "file_sha256": digest,
        "filename": PurePath(str(filename)).name, "input_bytes": len(content.encode("utf-8")),
        "text_field": text_column, "record_count": len(records),
        "source_link_count": sum(record["source_url"] is not None for record in records),
        "stop_reason": "complete", "sampling_complete": True,
        "labels_used": False, "normalization_for_model_input": "none",
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SourceError("Source API redirects are not allowed", code="source_http_error",
                          metadata={"stage": "http", "http_status": code, "exception_type": "SourceError"})


def _get_json(url: str, host: str, *, response_metadata: dict | None = None) -> dict:
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname != host or parsed.username
            or parsed.password or parsed.port not in (None, 443) or parsed.fragment):
        raise SourceError("API destination is not allowlisted", metadata={"stage": "request"})
    request = Request(url, headers={"User-Agent": "TopicEmotionResearch/0.1",
                                    "Accept": "application/json", "Accept-Encoding": "gzip, deflate"})
    metadata = {"stage": "request"}
    try:
        with build_opener(_NoRedirect()).open(request, timeout=15) as response:
            metadata.update(stage="read", http_status=getattr(response, "status", 200),
                            content_encoding=_encoding(response.headers.get("Content-Encoding")))
            if urlparse(response.geturl()).hostname != host:
                raise SourceError("API response origin changed", code="source_http_error", metadata=metadata)
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        metadata.update(stage="http", http_status=error.code, exception_type="HTTPError",
                        content_encoding=_encoding(error.headers.get("Content-Encoding") if error.headers else None))
        try:
            data = error.read(MAX_RESPONSE_BYTES + 1)
            metadata.update(response_bytes=len(data), response_sha256=hashlib.sha256(data).hexdigest())
        except Exception:
            pass
        finally:
            error.close()
        code = "source_response_limit" if metadata.get("response_bytes", 0) > MAX_RESPONSE_BYTES else "source_http_error"
        raise SourceError("Source API returned a non-success HTTP status", code=code, metadata=metadata) from error
    except SourceError:
        raise
    except Exception as error:
        raise SourceError("Source API request failed", code="source_network_error",
                          metadata={**metadata, "exception_type": _exception_type(error)}) from error
    # When a size cap is hit, the digest covers only the bytes actually read.
    metadata.update(response_bytes=len(data), response_sha256=hashlib.sha256(data).hexdigest())
    if len(data) > MAX_RESPONSE_BYTES:
        raise SourceError("API response exceeds 2 MiB", code="source_response_limit", metadata=metadata)
    expanded = _decode_response(data, metadata)
    try:
        text = expanded.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SourceError("API response is not valid UTF-8", code="source_utf8_error",
                          metadata={**metadata, "stage": "utf8", "exception_type": "UnicodeDecodeError"}) from error
    try:
        decoded = _json(text)
    except (SourceError, json.JSONDecodeError, RecursionError) as error:
        raise SourceError("API response is not valid JSON", code="source_json_error",
                          metadata={**metadata, "stage": "json", "exception_type": _exception_type(error)}) from error
    if not isinstance(decoded, dict):
        raise SourceError("API response must be a JSON object", code="source_wrapper_error",
                          metadata={**metadata, "stage": "wrapper"})
    if response_metadata is not None:
        response_metadata.update(_safe_metadata(metadata))
    return decoded


def _limit(value: Any, maximum: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise SourceError(f"{name} must be an integer between 1 and {maximum}")
    return value


def fetch_stackexchange(request: dict, cancelled: Callable[[], bool] = lambda: False,
                        progress: Callable[[dict], None] | None = None) -> tuple[list[dict], dict]:
    """Creation-ordered Question Cohort, with related objects in the same UTC window."""
    if request.get("site", "stackoverflow") != "stackoverflow":
        raise SourceError("Only Stack Overflow is enabled")
    if not STACKEXCHANGE_FILTER_ID:
        raise SourceError("Stack Exchange body_markdown filter is not yet reviewed")
    start_iso, start = _timestamp(request.get("from_utc"), required=True)
    end_iso, end = _timestamp(request.get("to_utc"), required=True)
    if start is None or end is None or start >= end:
        raise SourceError("UTC window must have a start before its end")
    query = request.get("query", "")
    tags = request.get("tags", "")
    if not isinstance(query, str) or not isinstance(tags, str) or len(query) > 500 or len(tags) > 500:
        raise SourceError("Query and tags must be short strings")
    if not query.strip() and not tags.strip():
        raise SourceError("A topic query or tag is required")
    question_limit = _limit(request.get("max_questions", 100), 100, "max_questions")
    item_limit = _limit(request.get("max_items", MAX_ITEMS), MAX_ITEMS, "max_items")
    included = {kind: request.get(f"include_{kind}s", True) for kind in ("question", "answer", "comment")}
    if not all(isinstance(value, bool) for value in included.values()) or not any(included.values()):
        raise SourceError("Select at least one object type")
    manifest = {
        "source": "stackexchange", "site": "stackoverflow", "api_version": "2.3",
        "cohort": "questions_created_in_window", "query": query, "tags": tags,
        "from_utc": start_iso, "to_utc": end_iso, "window_bounds": "start_inclusive_end_exclusive",
        "sort": "creation", "order": "asc", "max_questions": question_limit,
        "max_items": item_limit, "included_types": [key for key, value in included.items() if value],
        "filter_id": STACKEXCHANGE_FILTER_ID, "text_field": "body_markdown",
        "normalization_for_model_input": "none", "requests": [], "quota_remaining": None,
        "record_count": 0, "selected_question_count": 0, "duplicate_source_ids": 0,
        "outside_window_count": 0, "counts_by_type": {key: 0 for key in included},
        "stop_reason": "complete", "sampling_complete": True,
    }
    records: list[dict] = []
    seen: set[tuple[str, int]] = set()
    begun = time.monotonic()
    next_request_at = begun
    hard_stop = False
    cohort_limited = False
    active_context: dict = {"stage": "validation", "record_count": 0}

    def source_error(message: str, code: str = "source_validation_error", stage: str = "record") -> SourceError:
        return SourceError(message, code=code,
                           metadata={**active_context, "stage": stage, "record_count": len(records)})

    def notify(source_stage: str, data: dict | None = None) -> None:
        if progress:
            value = {**_safe_metadata(active_context), "stage": "collecting", "source_stage": source_stage,
                     "record_count": len(records)}
            if data is not None:
                if isinstance(data.get("items"), list):
                    value["returned_count"] = len(data["items"])
                for key in ("quota_remaining", "backoff"):
                    if type(data.get(key)) is int and data[key] >= 0:
                        value[key] = data[key]
                if isinstance(data.get("has_more"), bool):
                    value["has_more"] = data["has_more"]
            progress(value)

    def stop(reason: str) -> None:
        nonlocal hard_stop
        hard_stop = True
        manifest.update(stop_reason=reason, sampling_complete=False)

    def pages(endpoint: str, extra: dict | None = None):
        nonlocal next_request_at
        page = 1
        while not hard_stop:
            if cancelled():
                stop("cancelled")
                return
            if manifest["quota_remaining"] == 0:
                stop("quota_exhausted")
                return
            if len(manifest["requests"]) >= MAX_REQUESTS:
                stop("max_requests")
                return
            if time.monotonic() - begun >= MAX_FETCH_SECONDS:
                stop("time_limit")
                return
            while time.monotonic() < next_request_at:
                if cancelled():
                    stop("cancelled")
                    return
                if time.monotonic() - begun >= MAX_FETCH_SECONDS:
                    stop("time_limit")
                    return
                time.sleep(min(0.1, max(0, next_request_at - time.monotonic())))
            params = {"site": "stackoverflow", "fromdate": start, "todate": end - 1,
                      "sort": "creation", "order": "asc", "pagesize": 100,
                      "page": page, "filter": STACKEXCHANGE_FILTER_ID, **(extra or {})}
            active_context.clear()
            active_context.update(stage="request", request_count=len(manifest["requests"]) + 1, page=page,
                                  record_count=len(records), endpoint_kind="search" if endpoint == "search/advanced"
                                  else "answers" if endpoint.endswith("/answers") else "comments")
            notify("request_started")
            response_metadata: dict = {}
            try:
                data = _get_json(f"https://{STACKEXCHANGE_HOST}/2.3/{endpoint}?{urlencode(params)}", STACKEXCHANGE_HOST,
                                 response_metadata=response_metadata)
            except SourceError as error:
                raise SourceError("Source request failed", code=error.code,
                                  metadata={**active_context, **error.metadata}) from error
            active_context.update(response_metadata)
            notify("response_received", data)
            if "error_id" in data or "error_message" in data:
                raise source_error("Stack Exchange returned an API error", "source_api_error", "wrapper")
            items = data.get("items")
            has_more = data.get("has_more")
            quota = data.get("quota_remaining")
            backoff = data.get("backoff", 0)
            if (not isinstance(items, list) or len(items) > 100 or not isinstance(has_more, bool)
                    or isinstance(quota, bool) or not isinstance(quota, int) or quota < 0
                    or isinstance(backoff, bool) or not isinstance(backoff, int) or backoff < 0):
                raise source_error("Stack Exchange response metadata is invalid", "source_wrapper_error", "wrapper")
            manifest["requests"].append({"endpoint": endpoint, "page": page,
                                         "returned_count": len(items), "has_more": has_more,
                                         "quota_remaining": quota, "backoff": backoff})
            manifest["quota_remaining"] = quota
            next_request_at = time.monotonic() + backoff
            yield items, has_more
            if not has_more:
                return
            if quota == 0:
                stop("quota_exhausted")
                return
            if not items:
                raise source_error("Stack Exchange pagination made no progress", "source_wrapper_error", "wrapper")
            page += 1

    def accept(item: dict, kind: str) -> bool:
        if not isinstance(item, dict):
            raise source_error("Stack Exchange item is not an object")
        identifier = item.get(f"{kind}_id")
        if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier <= 0:
            raise source_error("Stack Exchange object id is invalid")
        try:
            _, timestamp = _timestamp(item.get("creation_date"), required=True)
        except SourceError as error:
            raise source_error("Stack Exchange creation timestamp is invalid") from error
        if timestamp is None or not start <= timestamp < end:
            manifest["outside_window_count"] += 1
            return False
        key = (kind, identifier)
        if key in seen:
            manifest["duplicate_source_ids"] += 1
            return False
        seen.add(key)
        return True

    def append(item: dict, kind: str) -> None:
        if not included[kind]:
            return
        if len(records) >= item_limit:
            stop("item_limit")
            return
        identifier = item[f"{kind}_id"]
        post_id = item.get("post_id") if kind == "comment" else identifier
        if kind == "comment":
            if isinstance(post_id, bool) or not isinstance(post_id, int) or post_id <= 0:
                raise source_error("Comment parent id is invalid")
            source_url = f"https://stackoverflow.com/posts/{post_id}#comment{identifier}_{post_id}"
        else:
            source_url = f"https://stackoverflow.com/{'q' if kind == 'question' else 'a'}/{identifier}"
        selected = {key: item[key] for key in (
            f"{kind}_id", "question_id", "post_id", "creation_date", "last_edit_date", "body_markdown",
            "link", "owner", "content_license") if key in item}
        if not isinstance(item.get("body_markdown"), str):
            raise source_error("Required source-native body is absent", "source_body_markdown_missing")
        try:
            records.append(_record(
                text=item["body_markdown"], source="stackexchange", site="stackoverflow", kind=kind,
                source_id=str(identifier), source_url=source_url, created_at=item["creation_date"],
                payload=selected, provenance={"text_field": "body_markdown", "filter_id": STACKEXCHANGE_FILTER_ID,
                                              "question_id": question_by_post.get(post_id), "post_id": post_id},
            ))
        except ValidationError as error:
            raise source_error("Source record does not satisfy the input contract") from error
        manifest["counts_by_type"][kind] += 1

    questions: list[int] = []
    question_by_post: dict[int, int] = {}
    for items, has_more in pages("search/advanced", {"q": query, "tagged": tags}):
        for index, item in enumerate(items):
            if accept(item, "question"):
                questions.append(item["question_id"])
                question_by_post[item["question_id"]] = item["question_id"]
                append(item, "question")
            if hard_stop:
                break
            if len(questions) >= question_limit:
                cohort_limited = has_more or index + 1 < len(items)
                break
        if hard_stop or len(questions) >= question_limit:
            break
    manifest["selected_question_count"] = len(questions)
    posts = list(questions)
    if questions and (included["answer"] or included["comment"]) and not hard_stop:
        ids = ";".join(map(str, questions))
        for items, _ in pages(f"questions/{ids}/answers"):
            for item in items:
                if accept(item, "answer"):
                    if item.get("question_id") not in questions:
                        raise source_error("Answer is outside the selected question cohort")
                    posts.append(item["answer_id"])
                    question_by_post[item["answer_id"]] = item["question_id"]
                    append(item, "answer")
                if hard_stop:
                    break
    if included["comment"] and not hard_stop:
        for offset in range(0, len(posts), 100):
            batch = posts[offset:offset + 100]
            ids = ";".join(map(str, batch))
            for items, _ in pages(f"posts/{ids}/comments"):
                for item in items:
                    if accept(item, "comment"):
                        if item.get("post_id") not in batch:
                            raise source_error("Comment is outside the selected question cohort")
                        append(item, "comment")
                    if hard_stop:
                        break
            if hard_stop:
                break
    if cohort_limited and not hard_stop:
        manifest.update(stop_reason="question_limit", sampling_complete=False)
    manifest["record_count"] = len(records)
    manifest["elapsed_seconds"] = round(time.monotonic() - begun, 3)
    return records, manifest


def parse_discourse_snapshot(payload: dict, *, topic_url: str, approved_hosts: tuple[str, ...] = ()):
    """Validate a controlled topic snapshot; no cooked-to-text fallback is permitted."""
    parsed = urlparse(topic_url)
    if parsed.scheme != "https" or parsed.hostname not in approved_hosts or parsed.query or parsed.fragment:
        raise SourceError("Discourse site has not been reviewed and allowlisted")
    _url(topic_url, parsed.hostname)
    topic_id = payload.get("id")
    match = re.fullmatch(r"/t/(?:(?![0-9]+/)[^/]+/)?([1-9][0-9]*)(?:/[1-9][0-9]*)?/?", parsed.path)
    if match is None or str(topic_id) != match.group(1):
        raise SourceError("Discourse topic URL and snapshot identity differ")
    stream = payload.get("post_stream", {})
    posts = stream.get("posts")
    ids = stream.get("stream")
    if (isinstance(topic_id, bool) or not isinstance(topic_id, int) or topic_id <= 0
            or not isinstance(posts, list) or not isinstance(ids, list) or len(posts) > MAX_ITEMS
            or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in ids)
            or len(ids) != len(set(ids))):
        raise SourceError("Invalid Discourse topic snapshot")
    records = []
    seen = set()
    for post in posts:
        if not isinstance(post, dict) or post.get("topic_id") != topic_id:
            raise SourceError("Discourse post is outside its topic")
        identifier = post.get("id")
        number = post.get("post_number")
        if (isinstance(identifier, bool) or not isinstance(identifier, int) or identifier <= 0
                or isinstance(number, bool) or not isinstance(number, int) or number <= 0):
            raise SourceError("Invalid Discourse post identity")
        if identifier not in ids:
            raise SourceError("Discourse post is outside the declared stream")
        if identifier in seen:
            continue
        seen.add(identifier)
        selected = {key: post[key] for key in ("id", "topic_id", "post_number", "raw", "created_at") if key in post}
        records.append(_record(
            text=post.get("raw"), source="discourse", site=parsed.hostname, kind="post",
            source_id=str(identifier), source_url=f"https://{parsed.hostname}/t/{topic_id}/{number}",
            created_at=post.get("created_at"), payload=selected,
            provenance={"topic_id": topic_id, "post_number": number, "text_field": "raw"},
        ))
    complete = seen == set(ids)
    return records, {"source": "discourse", "site": parsed.hostname, "topic_id": topic_id,
                     "text_field": "raw", "record_count": len(records), "declared_post_count": len(ids),
                     "sampling_complete": complete, "stop_reason": "complete" if complete else "incomplete_snapshot",
                     "normalization_for_model_input": "none"}


def fetch_discourse(request: dict, cancelled: Callable[[], bool] = lambda: False,
                    progress: Callable[[dict], None] | None = None) -> tuple[list[dict], dict]:
    """Public Python Help topic prefix, native raw only, with no search or login."""
    if (not isinstance(request, dict) or set(request) - {"site", "category_id", "max_topics", "max_items"}
            or request.get("site") != "discuss.python.org" or type(request.get("category_id")) is not int
            or request["category_id"] != 7):
        raise SourceError("Only the reviewed Python Help category is enabled")
    max_topics = _limit(request.get("max_topics", 100), 100, "max_topics")
    max_items = _limit(request.get("max_items", 400), MAX_ITEMS, "max_items")
    host = "discuss.python.org"
    records: list[dict] = []
    exclusions = {"pinned_topics": 0, "nonpublic_topics": 0, "system_posts": 0,
                  "nonregular_posts": 0, "deleted_or_hidden_posts": 0, "duplicate_topics": 0,
                  "duplicate_posts": 0, "unavailable_stream_ids": 0, "unresolved_reply_parent": 0}
    manifest = {
        "source": "discourse", "site": host, "category_id": 7, "category_name": "Python Help",
        "cohort": "latest_created_public_unpinned_topics_prefix", "topic_order": "created_desc",
        "post_order": "post_number_asc", "window_bounds": "not_a_time_window",
        "max_topics": max_topics, "max_items": max_items, "text_field": "raw",
        "normalization_for_model_input": "none", "content_license": DISCOURSE_LICENSE,
        "license_url": DISCOURSE_LICENSE_URL, "source_policy_url": f"https://{host}/tos",
        "source_review": "docs/discourse-source-review.md", "source_review_date": "2026-08-31",
        "requests": [], "topic_ids": [], "unavailable_post_ids": [], "truncated_topic_ids": [], "exclusions": exclusions,
        "record_count": 0, "fetched_post_count": 0, "stop_reason": "source_exhausted", "sampling_complete": False,
        "max_requests": DISCOURSE_MAX_REQUESTS, "max_seconds": DISCOURSE_MAX_SECONDS,
        "min_request_interval_seconds": DISCOURSE_MIN_INTERVAL,
        "sampling_caveat": "Observed topic prefix, not all forum activity or a population emotion estimate.",
    }
    started = time.monotonic()
    next_request_at = started
    active_context = {"stage": "validation", "record_count": 0}
    seen_topics: set[int] = set()
    seen_posts: set[int] = set()
    previous_created = None

    def fail(message, code="source_validation_error", stage="validation"):
        return SourceError(message, code=code,
                           metadata={**active_context, "stage": stage, "record_count": len(records)})

    def get(endpoint, kind, params=None, *, page=0, topic_id=None):
        nonlocal next_request_at
        if cancelled():
            raise fail("Discourse collection cancelled", stage="request")
        if len(manifest["requests"]) >= DISCOURSE_MAX_REQUESTS:
            raise fail("Discourse request budget exhausted", "source_resource_limit", "request")
        # Leave the existing HTTP helper's whole request timeout available.
        if time.monotonic() - started > DISCOURSE_MAX_SECONDS - 15:
            raise fail("Discourse time budget exhausted", "source_resource_limit", "request")
        while time.monotonic() < next_request_at:
            if cancelled():
                raise fail("Discourse collection cancelled", stage="request")
            if time.monotonic() - started > DISCOURSE_MAX_SECONDS - 15:
                raise fail("Discourse time budget exhausted", "source_resource_limit", "request")
            time.sleep(min(0.1, max(0, next_request_at - time.monotonic())))
        active_context.clear()
        active_context.update(stage="request", endpoint_kind=kind, page=page,
                              request_count=len(manifest["requests"]) + 1, record_count=len(records))
        if progress:
            progress({**active_context, "stage": "collecting", "source_stage": "request_started"})
        response_metadata = {}
        url = f"https://{host}/{endpoint}"
        if params:
            url += "?" + urlencode(params, doseq=True)
        try:
            data = _get_json(url, host, response_metadata=response_metadata)
        except SourceError as error:
            raise SourceError("Discourse request failed", code=error.code,
                              metadata={**active_context, **error.metadata}) from error
        active_context.update(response_metadata)
        entry = {**_safe_metadata(active_context), "number": len(manifest["requests"]) + 1}
        if topic_id is not None:
            entry["topic_id"] = topic_id
        manifest["requests"].append(entry)
        if progress:
            progress({**entry, "stage": "collecting", "source_stage": "response_received", "record_count": len(records)})
        if time.monotonic() - started > DISCOURSE_MAX_SECONDS:
            raise fail("Discourse time budget exhausted", "source_resource_limit", "read")
        if "errors" in data or "error_type" in data:
            raise fail("Discourse returned an API error", "source_api_error", "wrapper")
        backoff = data.get("backoff", 0)
        if type(backoff) is not int or backoff < 0:
            raise fail("Discourse backoff metadata is invalid", stage="wrapper")
        next_request_at = time.monotonic() + max(DISCOURSE_MIN_INTERVAL, backoff)
        return data

    def collect_topic(topic):
        topic_id = topic["id"]
        data = get(f"t/{topic_id}.json", "topic", {"include_raw": "true"}, topic_id=topic_id)
        if (data.get("id") != topic_id or data.get("category_id") != 7
                or data.get("archetype") != "regular" or data.get("visible") is not True):
            raise fail("Selected topic is no longer the same public category topic")
        stream = data.get("post_stream")
        ids = stream.get("stream") if isinstance(stream, dict) else None
        first_posts = stream.get("posts") if isinstance(stream, dict) else None
        if (not isinstance(ids, list) or any(type(value) is not int or value <= 0 for value in ids)
                or len(set(ids)) != len(ids) or not isinstance(first_posts, list)):
            raise fail("Discourse topic stream is invalid", stage="wrapper")
        manifest["topic_ids"].append(topic_id)
        number_to_id = {}
        last_number = 0
        handled_ids = set()

        def consume(posts, requested_ids):
            nonlocal last_number
            if not isinstance(posts, list) or len(posts) > 100:
                raise fail("Discourse post response is invalid", stage="wrapper")
            manifest["fetched_post_count"] += len(posts)
            by_id = {}
            for post in posts:
                if (not isinstance(post, dict) or type(post.get("id")) is not int
                        or post["id"] not in requested_ids or post.get("topic_id") != topic_id
                        or post["id"] in by_id):
                    raise fail("Discourse post identity does not match its requested topic", stage="record")
                by_id[post["id"]] = post
            for identifier in requested_ids:
                if len(records) >= max_items:
                    return
                handled_ids.add(identifier)
                post = by_id.get(identifier)
                if post is None:
                    exclusions["unavailable_stream_ids"] += 1
                    manifest["unavailable_post_ids"].append(identifier)
                    continue
                number, post_type = post.get("post_number"), post.get("post_type")
                if type(number) is not int or number <= last_number or type(post_type) is not int:
                    raise fail("Discourse post-number ordering or type is invalid", stage="record")
                last_number = number
                number_to_id[number] = identifier
                if post.get("deleted_at") is not None or post.get("hidden") is True or post.get("user_deleted") is True:
                    exclusions["deleted_or_hidden_posts"] += 1
                    continue
                username = post.get("username")
                if post.get("user_id") == -1 or (isinstance(username, str) and username in {"system", "discobot"}):
                    exclusions["system_posts"] += 1
                    continue
                if post_type != 1:
                    exclusions["nonregular_posts"] += 1
                    continue
                if identifier in seen_posts:
                    exclusions["duplicate_posts"] += 1
                    continue
                if not isinstance(post.get("raw"), str) or not post["raw"]:
                    raise fail("Public ordinary post has no native raw", "source_raw_missing", "record")
                if not isinstance(username, str) or not username:
                    raise fail("Public post has no attribution username", stage="record")
                try:
                    created_at, _ = _timestamp(post.get("created_at"), required=True)
                    raw = _text(post["raw"])
                except SourceError as error:
                    raise fail("Discourse post violates the native-text contract", stage="record") from error
                reply_number = post.get("reply_to_post_number")
                if reply_number is not None and (type(reply_number) is not int or reply_number <= 0):
                    raise fail("Discourse reply parent is invalid", stage="record")
                parent_id = number_to_id.get(reply_number) if reply_number is not None else None
                if reply_number is not None and parent_id is None:
                    exclusions["unresolved_reply_parent"] += 1
                selected = {key: post[key] for key in ("id", "topic_id", "post_number", "post_type", "raw", "created_at",
                                                      "updated_at", "reply_to_post_number", "username", "name", "user_id") if key in post}
                records.append(make_record(
                    source="discourse", site=host, object_type="post", source_object_id=str(identifier),
                    model_input_text=raw, source_payload_raw=selected, source_url=f"https://{host}/t/{topic_id}/{number}",
                    created_at=created_at, updated_at=post.get("updated_at"), parent_object_id=parent_id, thread_id=topic_id,
                    author_display_name=username, author_id_hash=_sha(f"{host}:{post['user_id']}") if "user_id" in post else None,
                    content_license=DISCOURSE_LICENSE,
                    provenance={"category_id": 7, "topic_id": topic_id, "post_number": number, "reply_to_post_number": reply_number,
                                "text_field": "raw", "license_url": DISCOURSE_LICENSE_URL, "source_policy_url": f"https://{host}/tos",
                                "author_username": username, "display_is_excerpt": True},
                ))
                seen_posts.add(identifier)

        first_ids = []
        for post in first_posts:
            if not isinstance(post, dict) or type(post.get("id")) is not int:
                raise fail("Discourse initial post identity is invalid", stage="record")
            first_ids.append(post["id"])
        if first_ids != ids[:len(first_ids)]:
            raise fail("Discourse initial posts are not the topic stream prefix", stage="record")
        consume(first_posts, first_ids)
        for offset in range(len(first_ids), len(ids), 20):
            if len(records) >= max_items:
                break
            wanted = ids[offset:offset + 20]
            batch = get(f"t/{topic_id}/posts.json", "topic_posts",
                        {"post_ids[]": wanted, "include_raw": "true", "asc": "true"}, topic_id=topic_id)
            if batch.get("id") != topic_id or not isinstance(batch.get("post_stream"), dict):
                raise fail("Discourse batch topic identity is invalid", stage="wrapper")
            consume(batch["post_stream"].get("posts"), wanted)
        if len(handled_ids) < len(ids):
            manifest["truncated_topic_ids"].append(topic_id)

    page = 0
    while len(records) < max_items and len(manifest["topic_ids"]) < max_topics:
        data = get("c/help/7/l/latest.json", "category", {"order": "created", "ascending": "false", "page": page}, page=page)
        listing = data.get("topic_list")
        topics = listing.get("topics") if isinstance(listing, dict) else None
        if not isinstance(topics, list) or len(topics) > 100:
            raise fail("Discourse category listing is invalid", stage="wrapper")
        new_topics = 0
        for topic in topics:
            if len(records) >= max_items or len(manifest["topic_ids"]) >= max_topics:
                break
            if not isinstance(topic, dict) or type(topic.get("id")) is not int or topic["id"] <= 0:
                raise fail("Discourse category topic identity is invalid")
            if topic["id"] in seen_topics:
                exclusions["duplicate_topics"] += 1
                continue
            seen_topics.add(topic["id"])
            new_topics += 1
            if topic.get("pinned") is True:
                exclusions["pinned_topics"] += 1
                continue
            if topic.get("category_id") != 7 or topic.get("visible") is not True or topic.get("archetype") != "regular":
                exclusions["nonpublic_topics"] += 1
                continue
            try:
                created = datetime.fromisoformat(topic["created_at"].replace("Z", "+00:00"))
                if created.tzinfo is None:
                    raise ValueError()
            except (KeyError, AttributeError, TypeError, ValueError) as error:
                raise fail("Discourse topic creation time is invalid") from error
            if previous_created is not None and created > previous_created:
                raise fail("Discourse category creation order changed")
            previous_created = created
            collect_topic(topic)
        if len(records) >= max_items:
            manifest["stop_reason"] = "item_limit"
            break
        if len(manifest["topic_ids"]) >= max_topics:
            manifest["stop_reason"] = "topic_limit"
            break
        if not listing.get("more_topics_url"):
            break
        if not new_topics:
            raise fail("Discourse pagination made no progress", stage="wrapper")
        page += 1
    manifest.update(record_count=len(records), selected_topic_count=len(manifest["topic_ids"]),
                    source_link_count=len(records), elapsed_seconds=round(time.monotonic() - started, 3),
                    collection_complete=not manifest["unavailable_post_ids"] and not manifest["truncated_topic_ids"],
                    observed_created_at_min=min((row["created_at"] for row in records), default=None),
                    observed_created_at_max=max((row["created_at"] for row in records), default=None))
    return records, manifest
