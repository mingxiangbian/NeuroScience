"""EXP-078: one Research job, only after an independently safe EXP-077 terminal."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "private/validation/exp-078/attempt-1"
SOAK = ROOT / "private/validation/exp-077/attempt-1"
PROTOCOL = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-078-discourse-operational.md"
REVIEW = ROOT / "docs/discourse-source-review.md"
MAX_SECONDS = 3600
QUERY = {"site": "discuss.python.org", "category_id": 7, "max_topics": 100, "max_items": 400}
STATES = {"queued", "fetching", "snapshot_sealed", "inferencing", "aggregating", "completed",
          "completed_with_fallback", "failed", "cancel_requested", "cancelled", "deleting"}
C3_TOOLS = {"scripts/run_discourse_validation.py", "scripts/verify_discourse_validation.py", "tests/test_discourse_validation.py"}


class RunError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def ensure(condition, code):
    if not condition:
        raise RunError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def file_hash(path):
    ensure(not any(item.is_symlink() for item in (path, *path.parents)) and path.is_file()
           and stat.S_ISREG(path.stat().st_mode), "source_file_unavailable")
    return sha(path.read_bytes())


def source_hashes(root=ROOT):
    result = {str(path.relative_to(root)): file_hash(path)
              for folder in ("topicweb", "scripts", "tests", "static")
              for path in sorted((root / folder).rglob("*"))
              if path.is_file() and path.suffix in {".py", ".js", ".css", ".html"}}
    result["requirements-lock.txt"] = file_hash(root / "requirements-lock.txt")
    return result


def check_source_scope(soak_sources, current):
    ensure(isinstance(soak_sources, dict) and bool(soak_sources)
           and set(soak_sources) <= set(current) and set(current) - set(soak_sources) <= C3_TOOLS
           and all(current[name] == value for name, value in soak_sources.items()), "implementation_changed_after_soak")


def check_soak(run, verification, *, run_hash, plan_hash):
    prefix = "private/validation/exp-077/attempt-1/"
    ensure(run.get("experiment_id") == "EXP-077" and run.get("status") == "Completed"
           and run.get("failure_code") is None and run.get("plan_sha256") == plan_hash, "soak_run_not_safe")
    ensure(verification.get("experiment_id") == "EXP-077" and verification.get("status") == "Passed"
           and verification.get("exp077_complete") is True and verification.get("gates", {}).get("base") is True
           and verification.get("operational_state") == "safe-to-continue"
           and type(verification.get("soak_gate_passed")) is bool, "soak_verification_not_safe")
    ensure(verification.get("source_hashes", {}).get(prefix + "run.json") == run_hash
           and verification["source_hashes"].get(prefix + "plan.json") == plan_hash, "soak_terminal_binding")


def gate_sources():
    paths = {"run": SOAK / "run.json", "verification": SOAK / "verification.json", "plan": SOAK / "plan.json"}
    bindings = {key: {"path": str(path.relative_to(ROOT)), "sha256": file_hash(path)} for key, path in paths.items()}
    run, verification, plan = (json.loads(paths[key].read_text()) for key in ("run", "verification", "plan"))
    check_soak(run, verification, run_hash=bindings["run"]["sha256"], plan_hash=bindings["plan"]["sha256"])
    current = source_hashes()
    check_source_scope(plan.get("sources"), current)
    return {**bindings, "operational_state": "safe-to-continue", "soak_gate_passed": verification["soak_gate_passed"]}, current


def api(path, payload=None, method=None):
    token_path = ROOT / "private/access-token"
    file_hash(token_path)
    token = token_path.read_text().strip()
    ensure(bool(token), "api_token_missing")
    request = Request("http://127.0.0.1:8787/api/" + path,
                      data=canonical(payload).encode() if payload is not None else None,
                      headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"}, method=method)
    with urlopen(request, timeout=20) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
    ensure(len(raw) <= 2 * 1024 * 1024, "api_response_limit")
    result = json.loads(raw)
    ensure(isinstance(result, dict), "api_response_contract")
    return result


def execute_job(call=api, report=lambda value: None, *, clock=time.monotonic, sleeper=time.sleep):
    started = clock()
    identifier = None
    last_state = None
    entry = {"source": "discourse", "mode": "research", "query": QUERY.copy()}
    try:
        payload = {"name": "EXP-078 / Python Help / public topic prefix", "source": "discourse",
                   "mode": "research", "max_qwen_calls": 500, "audit_rate": 0, "query": QUERY.copy()}
        response = call("jobs", payload, "POST")
        identifier = response.get("job", {}).get("id")
        ensure(isinstance(identifier, str) and re.fullmatch(r"[0-9a-f]{32}", identifier), "submitted_job_identity")
        entry["id"] = identifier
        report({"stage": "submitted", "job_id": identifier})
        while True:
            ensure(clock() - started < MAX_SECONDS, "job_time_limit")
            job = call("jobs/" + identifier)["job"]
            ensure(job.get("id") == identifier and job.get("state") in STATES, "job_identity_or_state")
            state = (job["state"], job.get("completed_items"), job.get("total_items"))
            if state != last_state:
                report({"stage": job["state"], "completed_items": job.get("completed_items"), "total_items": job.get("total_items")})
                last_state = state
            if job["state"] in {"completed", "completed_with_fallback", "failed", "cancelled"}:
                break
            sleeper(0.5)
        entry.update({key: job.get(key) for key in ("state", "created_at", "updated_at", "total_items", "completed_items",
                                                   "snapshot_hash", "manifest", "progress")})
        supplied_error = job.get("error_code")
        entry["error_code"] = supplied_error if isinstance(supplied_error, str) and re.fullmatch(r"[a-z0-9_]{1,64}", supplied_error) else None
        ensure(job["state"] == "completed" and supplied_error is None, "discourse_job_failed")
        ensure(type(job.get("total_items")) is int and 300 <= job["total_items"] <= 400
               and job.get("completed_items") == job["total_items"], "discourse_sample_or_completion_count")
        ensure(isinstance(job.get("snapshot_hash"), str) and re.fullmatch(r"[0-9a-f]{64}", job["snapshot_hash"]), "snapshot_identity_missing")
        ensure(isinstance(job.get("manifest"), dict), "source_manifest_missing")
        entry["manifest_sha256"] = sha(canonical(job["manifest"]))
        entry["dashboard"] = call("jobs/" + identifier + "/dashboard")
        entry["private_snapshot"] = {"database": "private/jobs.sqlite3", "job_id": identifier,
                                      "snapshot_sha256": job["snapshot_hash"]}
        ensure(clock() - started <= MAX_SECONDS, "job_time_limit")
        entry.update(status="Passed", elapsed_seconds=clock() - started)
    except Exception as error:
        entry.update(status="Failed", failure_code=error.code if isinstance(error, RunError) else "api_or_runtime_failure",
                     elapsed_seconds=clock() - started)
        if identifier and (last_state is None or last_state[0] not in {"completed", "completed_with_fallback", "failed", "cancelled"}):
            try:
                call("jobs/" + identifier + "/cancel", {}, "POST")
                entry["cancellation_requested"] = True
            except Exception:
                entry["cancellation_requested"] = False
    return entry


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    # Check safe-to-continue before reserving a formal attempt or creating a job.
    try:
        soak, sources = gate_sources()
        protocol_hash, review_hash = file_hash(PROTOCOL), file_hash(REVIEW)
        ensure(not any(path.is_symlink() for path in (RUN, *RUN.parents)), "run_path_symlink")
        ensure(not (RUN / "run.json").exists() and not (RUN / "stdout.log").exists(), "attempt_already_used")
    except Exception as error:
        print(error.code if isinstance(error, RunError) else "precondition_unavailable", flush=True)
        return 2
    os.umask(0o077)
    RUN.mkdir(parents=True, exist_ok=True, mode=0o700)
    started = time.monotonic()
    descriptor = os.open(RUN / "run.json", os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    record = {"experiment_id": "EXP-078", "tier": "Minor", "rq": "RQ-S3", "stage": "discourse_operational", "attempt": 1,
              "started_at": datetime.now(timezone.utc).isoformat(), "status": "Running", "sources": sources,
              "protocol_sha256": protocol_hash, "source_review_sha256": review_hash, "soak": soak,
              "command": sys.argv, "cwd": str(ROOT), "python": sys.executable, "seed": 42,
              "label_order": ["love", "joy", "surprise", "anger", "sadness", "fear"],
              "query": QUERY.copy(), "maximum_seconds": MAX_SECONDS,
              "training": False, "validation_accessed": False, "test_accessed": False, "external_gold_accessed": False,
              "source_raw_read_by_driver": False, "api_cost_usd": 0,
              "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
              "claim_boundary": "One unlabelled public-source Research job; not external-gold accuracy, population emotion prevalence, or an SLA."}
    with os.fdopen(descriptor, "w", encoding="utf-8") as terminal, (RUN / "stdout.log").open("x", encoding="utf-8") as log:
        def report(value):
            text = canonical(value)
            print(text, flush=True)
            log.write(text + "\n")
            log.flush()
        try:
            record["job"] = execute_job(report=report)
            record["status"] = record["job"]["status"]
            ensure(source_hashes() == sources and file_hash(PROTOCOL) == protocol_hash
                   and file_hash(REVIEW) == review_hash, "implementation_or_protocol_changed")
            ensure(all(file_hash(ROOT / soak[key]["path"]) == soak[key]["sha256"] for key in ("run", "verification", "plan")), "soak_terminal_changed")
        except Exception as error:
            record.update(status="Failed", error_code=error.code if isinstance(error, RunError) else "run_integrity_failure")
        record["ended_at"] = datetime.now(timezone.utc).isoformat()
        record["elapsed_seconds"] = time.monotonic() - started
        json.dump(record, terminal, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        terminal.write("\n")
        terminal.flush()
        os.fsync(terminal.fileno())
        report({"status": record["status"], "experiment_id": "EXP-078"})
    return 0 if record["status"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
