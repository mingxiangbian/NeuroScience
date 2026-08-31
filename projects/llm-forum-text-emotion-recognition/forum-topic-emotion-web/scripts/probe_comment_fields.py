"""One bounded, metadata-only check of Stack Exchange comment field filters."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sys
import time
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from topicweb import adapters


OLD_FILTER_ID = "nFzTOPGAOEckIq4Pwr_RZ8"
OUTPUT = ROOT / "private/validation/exp-076/attempt-3/field-probe.json"
PROTOCOL = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-076-phase-c-local-system.md"
MAX_REQUESTS = 5
MAX_SECONDS = 120
FROM_UTC = "2026-08-23T00:00:00Z"
TO_UTC = "2026-08-30T00:00:00Z"
FROM_SECONDS = int(datetime.fromisoformat(FROM_UTC.replace("Z", "+00:00")).timestamp())
TO_SECONDS = int(datetime.fromisoformat(TO_UTC.replace("Z", "+00:00")).timestamp())


class ProbeError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _field_hash(text):
    data = text.encode("utf-8")
    return hashlib.sha256(data).hexdigest(), len(data)


def _filter(item, expected_id=None):
    identifier = item.get("filter") if isinstance(item, dict) else None
    fields = item.get("included_fields") if isinstance(item, dict) else None
    if (not isinstance(identifier, str) or not 1 <= len(identifier) <= 128
            or any(not 33 <= ord(character) <= 126 for character in identifier)
            or (expected_id is not None and identifier != expected_id) or item.get("filter_type") != "unsafe"
            or not isinstance(fields, list) or not fields or len(fields) > 5000
            or any(not isinstance(field, str) or not re.fullmatch(r"\.?[A-Za-z_][A-Za-z0-9_.]*", field) for field in fields)
            or len(set(fields)) != len(fields)):
        raise ProbeError("field_probe_filter_contract")
    return identifier, set(fields)


def _comment_map(items):
    if len(items) != 3:
        raise ProbeError("field_probe_requires_three_comments")
    mapped = {}
    for item in items:
        if not isinstance(item, dict):
            raise ProbeError("field_probe_comment_identity")
        identity = tuple(item.get(key) for key in ("comment_id", "post_id", "creation_date"))
        if (any(type(value) is not int or value <= 0 for value in identity)
                or not FROM_SECONDS <= identity[2] < TO_SECONDS or identity[0] in mapped):
            raise ProbeError("field_probe_comment_identity")
        mapped[identity[0]] = item
    return mapped


def run_probe(protocol_sha256, script_sha256, *, get_json=None, clock=None, sleeper=None):
    """Return only safe evidence. Dependencies are injectable for offline tests."""
    get_json = get_json or adapters._get_json
    clock, sleeper = clock or time.monotonic, sleeper or time.sleep
    started = clock()
    deadline = started + MAX_SECONDS
    next_request_at = started
    record = {
        "status": "Running", "experiment_id": "EXP-076", "stage": "comment_fields", "attempt": 3,
        "old_filter_id": OLD_FILTER_ID, "new_filter_id": None,
        "old_included_fields": [], "new_included_fields": [], "rows": [], "requests": [],
        "old_comment_ids": [], "new_comment_ids": [], "discovered_comment_ids": [],
        "matched_identity": False, "old_missing_markdown_count": None, "dependency_reproduced": False,
        "protocol_sha256": protocol_sha256, "script_sha256": script_sha256,
        "scope": "three_comment_field_fixture_not_python_topic_statistics",
        "from_utc": FROM_UTC, "to_utc": TO_UTC, "window_bounds": "start_inclusive_end_exclusive",
        "max_requests": MAX_REQUESTS, "max_seconds": MAX_SECONDS,
        "max_wire_response_bytes": adapters.MAX_RESPONSE_BYTES, "max_expanded_response_bytes": adapters.MAX_RESPONSE_BYTES,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model_accessed": False, "gold_accessed": False, "raw_content_persisted": False,
    }

    def request(step, endpoint, params=None):
        nonlocal next_request_at
        if len(record["requests"]) >= MAX_REQUESTS:
            raise ProbeError("field_probe_request_limit")
        if next_request_at >= deadline or clock() >= deadline:
            raise ProbeError("field_probe_time_limit")
        while clock() < next_request_at:
            if clock() >= deadline:
                raise ProbeError("field_probe_time_limit")
            sleeper(min(0.25, next_request_at - clock(), deadline - clock()))
        entry = {"number": len(record["requests"]) + 1, "step": step, "status": "Requested"}
        record["requests"].append(entry)
        metadata = {}
        url = f"https://{adapters.STACKEXCHANGE_HOST}/2.3/{endpoint}"
        if params:
            url += "?" + urlencode(params)
        try:
            data = get_json(url, adapters.STACKEXCHANGE_HOST, response_metadata=metadata)
        except adapters.SourceError as error:
            entry.update(adapters._safe_metadata(error.metadata), status="Failed", error_code=error.code)
            if clock() >= deadline:
                raise ProbeError("field_probe_time_limit") from error
            raise
        entry.update(adapters._safe_metadata(metadata), status="Received")
        if clock() >= deadline:
            raise ProbeError("field_probe_time_limit")
        if not isinstance(data, dict) or "error_id" in data or "error_message" in data:
            raise ProbeError("field_probe_api_error")
        items, quota = data.get("items"), data.get("quota_remaining")
        backoff, has_more = data.get("backoff", 0), data.get("has_more")
        if (not isinstance(items, list) or type(quota) is not int or quota < 0
                or type(backoff) is not int or backoff < 0 or not isinstance(has_more, bool)):
            raise ProbeError("field_probe_wrapper_contract")
        entry.update(returned_count=len(items), quota_remaining=quota, backoff=backoff, has_more=has_more)
        next_request_at = clock() + backoff
        if quota == 0:
            raise ProbeError("field_probe_quota_exhausted")
        return items

    try:
        old_metadata = request("old_filter_metadata", "filters/" + quote(OLD_FILTER_ID, safe=""))
        if len(old_metadata) != 1:
            raise ProbeError("field_probe_filter_contract")
        _, old_fields = _filter(old_metadata[0], OLD_FILTER_ID)
        required = {"question.body_markdown", "answer.body_markdown", "comment.body_markdown",
                    ".items", ".has_more", ".quota_remaining", ".backoff"}
        if not required <= old_fields:
            raise ProbeError("field_probe_old_filter_fields")
        record["old_included_fields"] = sorted(old_fields)

        new_metadata = request("create_filter", "filters/create",
                               {"base": OLD_FILTER_ID, "include": "comment.body", "unsafe": "true"})
        if len(new_metadata) != 1:
            raise ProbeError("field_probe_filter_contract")
        new_id, new_fields = _filter(new_metadata[0])
        if new_fields != old_fields | {"comment.body"}:
            raise ProbeError("field_probe_new_filter_fields")
        record.update(new_filter_id=new_id, new_included_fields=sorted(new_fields))

        discovery = _comment_map(request("discover_comments", "comments", {
            "site": "stackoverflow", "pagesize": 3, "page": 1,
            "sort": "creation", "order": "asc", "fromdate": FROM_SECONDS,
            "todate": TO_SECONDS - 1, "filter": OLD_FILTER_ID,
        }))
        ids = sorted(discovery)
        record["discovered_comment_ids"] = ids
        endpoint = "comments/" + ";".join(map(str, ids))
        old_comments = _comment_map(request("old_comments", endpoint,
                                             {"site": "stackoverflow", "pagesize": 3, "filter": OLD_FILTER_ID}))
        record["old_comment_ids"] = sorted(old_comments)
        new_comments = _comment_map(request("new_comments", endpoint,
                                             {"site": "stackoverflow", "pagesize": 3, "filter": new_id}))
        record["new_comment_ids"] = sorted(new_comments)
        if set(old_comments) != set(new_comments) or set(old_comments) != set(discovery):
            raise ProbeError("field_probe_same_ids_required")
        rows = []
        for identifier in ids:
            first, old, new = discovery[identifier], old_comments[identifier], new_comments[identifier]
            if any(first[key] != old[key] or first[key] != new[key] for key in ("comment_id", "post_id", "creation_date")):
                raise ProbeError("field_probe_comment_identity_changed")
            old_markdown = old.get("body_markdown")
            new_markdown, body = new.get("body_markdown"), new.get("body")
            if not isinstance(new_markdown, str) or not new_markdown or not isinstance(body, str) or not body:
                raise ProbeError("field_probe_new_fields_missing")
            new_hash, markdown_bytes = _field_hash(new_markdown)
            body_hash, body_bytes = _field_hash(body)
            old_hash = _field_hash(old_markdown)[0] if isinstance(old_markdown, str) else None
            if old_hash is not None and old_hash != new_hash:
                raise ProbeError("field_probe_existing_markdown_changed")
            rows.append({
                "comment_id": identifier, "post_id": new["post_id"], "creation_date": new["creation_date"],
                "old_has_markdown": isinstance(old_markdown, str), "new_has_markdown": True, "new_has_body": True,
                "old_markdown_sha256": old_hash, "new_markdown_sha256": new_hash,
                "markdown_sha256": new_hash, "markdown_bytes": markdown_bytes,
                "new_body_sha256": body_hash, "new_body_bytes": body_bytes,
            })
        missing = sum(not row["old_has_markdown"] for row in rows)
        record.update(rows=rows, matched_identity=True, old_missing_markdown_count=missing,
                      dependency_reproduced=missing > 0,
                      dependency_statement="old_missing_new_present_on_fixture" if missing else "old_missing_not_reproduced_on_fixture",
                      status="Passed")
    except adapters.SourceError as error:
        record.update(status="Failed", error_code=error.code, error_metadata=adapters._safe_metadata(error.metadata))
    except ProbeError as error:
        record.update(status="Failed", error_code=error.code)
    except Exception as error:
        record.update(status="Failed", error_code="field_probe_internal_error",
                      error_metadata={"exception_type": adapters._exception_type(error)})
    finally:
        record["ended_at"] = datetime.now(timezone.utc).isoformat()
        record["elapsed_seconds"] = clock() - started
    return record


def record_probe(protocol_path, output_path=OUTPUT, *, get_json=None, clock=None, sleeper=None):
    """Reserve one terminal before any request; never overwrite or resume it."""
    protocol_path, output_path = Path(protocol_path).absolute(), Path(output_path).absolute()
    script_path = Path(__file__).absolute()
    for path in (protocol_path, script_path, output_path):
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise ProbeError("field_probe_path_symlink")
    if not protocol_path.is_file() or not script_path.is_file():
        raise ProbeError("field_probe_source_missing")
    protocol_hash, script_hash = digest(protocol_path), digest(script_path)
    old_umask = os.umask(0o077)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(output_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    finally:
        os.umask(old_umask)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        record = run_probe(protocol_hash, script_hash, get_json=get_json, clock=clock, sleeper=sleeper)
        if digest(protocol_path) != protocol_hash or digest(script_path) != script_hash:
            record.update(status="Failed", error_code="field_probe_source_changed")
        json.dump(record, output, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    return record


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    args = parser.parse_args(argv)
    if args.protocol.absolute() != PROTOCOL.absolute():
        parser.error("the registered EXP-076 protocol path is required")
    previous_handler = signal.getsignal(signal.SIGALRM)
    def timeout(_signum, _frame):
        raise ProbeError("field_probe_time_limit")
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS)
    try:
        record = record_probe(args.protocol)
    except FileExistsError:
        print("field_probe_already_recorded", flush=True)
        return 2
    except ProbeError as error:
        print(error.code, flush=True)
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
    print(json.dumps({"status": record["status"], "request_count": len(record["requests"]),
                      "error_code": record.get("error_code")}), flush=True)
    return 0 if record["status"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
