"""Bounded EXP-076 implementation smoke through the real local HTTP service."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PROJECT = ROOT.parent
RUN = ROOT / "private/validation/exp-076/attempt-1"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def call(path, payload=None, method=None):
    token = (ROOT / "private/access-token").read_text().strip()
    request = Request("http://127.0.0.1:8787/api/" + path,
                      data=json.dumps(payload).encode() if payload is not None else None,
                      headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                      method=method)
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def persist(record):
    phase_dir = RUN / record["stage"]
    phase_dir.mkdir(exist_ok=True, mode=0o700)
    target = phase_dir / "run.json"
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    target.chmod(0o600)


def main():
    global RUN
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["smoke", "source"])
    parser.add_argument("--attempt", choices=[1, 2, 3], type=int, default=1)
    args = parser.parse_args()
    if args.attempt > 1 and args.phase != "source":
        parser.error("recovery attempts are source-only; reuse the completed attempt-1 smoke")
    RUN = ROOT / f"private/validation/exp-076/attempt-{args.attempt}"
    os.umask(0o077)
    if any(path.is_symlink() for path in (RUN, *RUN.parents)):
        raise SystemExit("validation_path_symlink")
    terminal = RUN / (args.phase + ".json")
    if terminal.exists():
        raise SystemExit("phase_already_recorded")
    RUN.mkdir(parents=True, exist_ok=True, mode=0o700)
    log_path = RUN / (args.phase + "-stdout.log")
    log = log_path.open("x")
    protocol = PROJECT / "experiments/stack-overflow-emotion-gold/protocols/exp-076-phase-c-local-system.md"
    fixed = ROOT / "tests/fixtures/operational.jsonl"
    sources = [p for p in ROOT.rglob("*") if p.is_file() and p.suffix in {".py", ".js", ".css", ".html"}
               and not any(part in {".venv", "private", "__pycache__", ".pytest_cache"} for part in p.relative_to(ROOT).parts)]
    identities = {str(p.relative_to(ROOT)): digest(p) for p in sources}
    record = {"experiment_id": "EXP-076", "tier": "Minor", "rq": "RQ-S3", "stage": args.phase, "attempt": args.attempt,
              "status": "Running", "started_at": now(), "command": sys.argv,
              "cwd": str(ROOT), "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
              "fixture_sha256": digest(fixed), "input_sha256": digest(fixed) if args.phase == "smoke" else None,
              "data_version": "authored-operational-fixtures-v1" if args.phase == "smoke" else "StackOverflow-2026-08-23_30-python-cohort",
              "split": "none_new_unlabelled_inputs", "seed": 42, "label_order": ["love","joy","surprise","anger","sadness","fear"],
              "protocol_sha256": digest(protocol), "sources": identities, "jobs": [],
              "model_parent": "EXP-066 attempt-2 immutable seed-42 runtime", "validation_accessed": False,
              "test_accessed": False, "training": False, "external_gold_accessed": False, "api_cost_usd": 0}
    inherited = {}
    if args.attempt > 1:
        import tarfile
        inherited_paths = {
            "inherits_smoke": RUN.parent / "attempt-1/smoke.json",
            "previous_failed_source": RUN.parent / "attempt-1/source.json",
            "inherited_code_archive": RUN.parent / "attempt-2/inherited-code.tar.gz",
            "inherited_protocol": RUN.parent / "attempt-2/inherited-protocol.md",
        }
        if args.attempt == 3:
            inherited_paths.update({
                "previous_failed_source_2": RUN.parent / "attempt-2/source.json",
                "previous_source_code_archive": RUN / "previous-code.tar.gz",
                "previous_source_protocol": RUN / "previous-protocol.md",
                "comment_field_probe": RUN / "field-probe.json",
            })
        for key, path in inherited_paths.items():
            if not path.is_file() or any(parent.is_symlink() for parent in (path, *path.parents)):
                raise RuntimeError("inherited_source_unavailable")
            inherited[key] = {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}
        old_smoke = json.loads(inherited_paths["inherits_smoke"].read_text())
        old_failed = json.loads(inherited_paths["previous_failed_source"].read_text())
        if old_smoke["status"] != "Passed" or old_failed["status"] != "Failed":
            raise RuntimeError("inherited_status_mismatch")
        if old_smoke["protocol_sha256"] != digest(inherited_paths["inherited_protocol"]):
            raise RuntimeError("inherited_protocol_drift")
        with tarfile.open(inherited_paths["inherited_code_archive"]) as archive:
            for previous in (old_smoke, old_failed):
                for name, expected in previous["sources"].items():
                    if hashlib.sha256(archive.extractfile(name).read()).hexdigest() != expected:
                        raise RuntimeError("inherited_code_drift")
            for name in ("topicweb/core.py", "topicweb/inference_process.py", "tests/fixtures/operational.jsonl"):
                if digest(ROOT / name) != hashlib.sha256(archive.extractfile(name).read()).hexdigest():
                    raise RuntimeError("frozen_inference_or_input_changed")
        if args.attempt == 3:
            from topicweb import adapters
            probe = json.loads(inherited_paths["comment_field_probe"].read_text())
            failed2 = json.loads(inherited_paths["previous_failed_source_2"].read_text())
            if (probe.get("status") != "Passed" or len(probe.get("rows", [])) != 3
                    or probe.get("new_filter_id") != adapters.STACKEXCHANGE_FILTER_ID
                    or probe.get("protocol_sha256") != digest(protocol)
                    or probe.get("script_sha256") != digest(ROOT / "scripts/probe_comment_fields.py")):
                raise RuntimeError("comment_field_probe_not_passed")
            if (set(probe["new_included_fields"]) != set(probe["old_included_fields"]) | {"comment.body"}
                    or not all(row["new_has_markdown"] and row["new_has_body"] for row in probe["rows"])):
                raise RuntimeError("comment_field_contract_mismatch")
            if failed2["status"] != "Failed" or failed2["protocol_sha256"] != digest(inherited_paths["previous_source_protocol"]):
                raise RuntimeError("previous_source_status_or_protocol_drift")
            with tarfile.open(inherited_paths["previous_source_code_archive"]) as archive:
                if any(hashlib.sha256(archive.extractfile(name).read()).hexdigest() != expected
                       for name, expected in failed2["sources"].items()):
                    raise RuntimeError("previous_source_code_drift")
        record.update(inherited)
    def report(message):
        print(message, flush=True)
        log.write(message + "\n")
        log.flush()
    started = time.monotonic()
    persist(record)
    def submit(name, mode, *, source="upload", replay=None):
        if replay:
            job = call(f"jobs/{replay}/replay", {}, "POST")["job"]
        else:
            suffix = f" / source attempt {args.attempt}" if args.attempt > 1 else ""
            request = {"name": "EXP-076 / " + name + suffix, "source": source, "mode": mode, "max_qwen_calls": 0, "audit_rate": 0}
            if source == "upload":
                request["upload"] = {"format": "jsonl", "content": fixed.read_text(), "filename": fixed.name, "text_column": "text"}
            else:
                request["query"] = {"site": "stackoverflow", "tags": "python", "query": "",
                                    "from_utc": "2026-08-23T00:00:00Z", "to_utc": "2026-08-30T00:00:00Z",
                                    "max_questions": 100, "max_items": 500,
                                    "include_questions": True, "include_answers": True, "include_comments": True}
            job = call("jobs", request, "POST")["job"]
        entry = {"name": name, "id": job["id"], "mode": mode, "created_at": job["created_at"]}
        record["jobs"].append(entry)
        persist(record)
        last = None
        deadline = min(started + (3600 if args.attempt > 1 else 5400), time.monotonic() + 3600)
        while True:
            job = call("jobs/" + job["id"])["job"]
            state = (job["state"], job["completed_items"], job["total_items"])
            if state != last:
                report(f"{name}: {state[0]} {state[1]}/{state[2]}")
                last = state
            if job["state"] in {"completed", "completed_with_fallback", "failed", "cancelled"}:
                break
            if time.monotonic() >= deadline:
                call(f"jobs/{job['id']}/cancel", {}, "POST")
                raise RuntimeError("acceptance_deadline")
            time.sleep(2)
        entry.update(state=job["state"], error_code=job["error_code"], snapshot_hash=job["snapshot_hash"],
                     total_items=job["total_items"], completed_items=job["completed_items"],
                     elapsed_seconds=job["updated_at"]-job["created_at"], manifest=job["manifest"], progress=job["progress"])
        if source == "stackexchange":
            record["input_sha256"] = job["snapshot_hash"]
        dashboard = call(f"jobs/{job['id']}/dashboard")
        entry["dashboard"] = dashboard
        persist(record)
        if job["state"] not in {"completed", "completed_with_fallback"}:
            raise RuntimeError("job_failed_" + (job["error_code"] or "unknown"))
        if not job["total_items"] or job["total_items"] != job["completed_items"]:
            raise RuntimeError("incomplete_coverage")
        if source == "upload" and job["total_items"] != 8:
            raise RuntimeError("fixture_count_mismatch")
        return job["id"]
    try:
        if args.phase == "smoke":
            submit("M1 / 8 authored inputs", "m1_only")
            research = submit("Research / same snapshot inputs", "research")
            submit("Demo / M3 budget zero", "demo")
            submit("Research / fresh-process replay", "research", replay=research)
        else:
            smoke_path = RUN / "smoke.json" if args.attempt == 1 else RUN.parent / "attempt-1/smoke.json"
            smoke = json.loads(smoke_path.read_text())
            if smoke["status"] != "Passed":
                raise RuntimeError("smoke_not_passed")
            submit("Stack Overflow / python / UTC week", "m1_only", source="stackexchange")
        if any(digest(ROOT / name) != expected for name, expected in identities.items()):
            raise RuntimeError("implementation_changed_during_run")
        if any(digest(ROOT / binding["path"]) != binding["sha256"] for binding in inherited.values()):
            raise RuntimeError("inherited_source_changed_during_run")
        record["status"] = "Passed"
    except Exception as error:
        record["status"] = "Failed"
        record["error_type"] = type(error).__name__
        record["error_code"] = str(error) if isinstance(error, RuntimeError) else "acceptance_request_failed"
        report("Stopped: " + record["error_code"])
    finally:
        record["ended_at"] = now()
        record["elapsed_seconds"] = time.monotonic() - started
        with terminal.open("x") as output:
            json.dump(record, output, ensure_ascii=False, indent=2, allow_nan=False)
            output.write("\n")
        persist(record)
        log.close()
    return 0 if record["status"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
