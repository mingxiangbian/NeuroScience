"""Offline EXP-080 lifecycle tests; no source, historical data or model is opened."""
import copy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import patch

from topicweb.core import aggregate, extended_views, make_record

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load("test_exp080_runner", "run_discourse_formal.py")
VERIFY = load("test_exp080_verifier", "verify_discourse_formal.py")
ID = "e" * 32


def prior():
    return ({"experiment_id": "EXP-079", "status": "Completed", "failure_code": None, "plan_sha256": "a"*64},
            {"experiment_id": "EXP-079", "status": "Passed", "exp079_complete": True, "operational_state": "safe-to-continue",
             "source_hashes": {"private/validation/exp-079/attempt-3/run.json": "b"*64,
                               "private/validation/exp-079/attempt-3/plan.json": "a"*64}})


def fixture(acknowledged=300):
    records, results, seen, third_seen = [], [], set(), set()
    totals = {key: 0 for key in VERIFY.LOCAL.COSTS}
    for index in range(300):
        identifier, number = index + 1000, index + 1
        raw = {"id": identifier, "topic_id": 10, "post_number": number, "post_type": 1,
               "raw": f"Synthetic raw {index % 3}", "username": "fixture_author", "user_id": 4,
               "created_at": "2026-08-31T00:00:00Z", "reply_to_post_number": number - 1 if number > 1 else None}
        record = make_record(source="discourse", site="discuss.python.org", object_type="post", source_object_id=str(identifier),
                             model_input_text=raw["raw"], source_payload_raw=raw, source_url=f"https://discuss.python.org/t/10/{number}",
                             thread_id=10, parent_object_id=identifier-1 if number > 1 else None, created_at=raw["created_at"],
                             author_display_name="fixture_author", content_license="CC BY-NC-SA 3.0",
                             provenance={"category_id": 7, "topic_id": 10, "post_number": number, "text_field": "raw",
                                         "reply_to_post_number": raw["reply_to_post_number"], "author_username": "fixture_author",
                                         "license_url": "https://creativecommons.org/licenses/by-nc-sa/3.0/", "source_policy_url": "https://discuss.python.org/tos"})
        records.append(record)
        if index >= acknowledged:
            results.append(None)
            continue
        exact = record["model_input_hash"]
        requested = index % 3 == 0
        costs = {key: 0 for key in totals}
        costs.update(m1_attempts=int(exact not in seen), m1_cache_hit=int(exact in seen))
        seen.add(exact)
        if requested:
            costs.update(m3_attempts=int(exact not in third_seen), m3_succeeded=int(exact not in third_seen), m3_cache_hit=int(exact in third_seen))
            third_seen.add(exact)
        for key in totals:
            totals[key] += costs[key]
        m1, m3 = [1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0] if requested else None
        results.append({"prediction": m3 or m1, "m1_prediction": m1, "m3_prediction": m3,
                        "m1_probabilities": [.7, .1, .1, .1, .1, .1], "m3_probabilities": [.1, .8, .1, .1, .1, .1] if requested else None,
                        "active_labels": ["joy" if requested else "love"], "neutral": False, "route_requested": requested,
                        "used_path": "m3" if requested else "m1", "fallback": False, "fallback_reason": None,
                        "counters": {**costs, "fallback_reason": None}, "cumulative_counters": totals.copy(), "latency_ms": 1.0,
                        "fingerprint": "f"*64, "tokenlengths": {"m1": {"input_tokens": 10, "used_tokens": 10, "truncated": False},
                                                               "m3": {"input_tokens": 20, "used_tokens": 20, "truncated": False} if requested else None},
                        "truncflags": {"m1": False, "m3": False if requested else None},
                        "resources": {"peak_rss_bytes": 1000, "mlx_peak_bytes": 2000 if requested else 0, "elapsed_seconds": 1.0}})
    manifest = {"source": "discourse", "site": "discuss.python.org", "category_id": 7, "category_name": "Python Help",
                "cohort": "latest_created_public_unpinned_topics_prefix", "topic_order": "created_desc", "post_order": "post_number_asc",
                "window_bounds": "not_a_time_window", "max_topics": 100, "max_items": 400, "text_field": "raw",
                "normalization_for_model_input": "none", "content_license": "CC BY-NC-SA 3.0",
                "license_url": "https://creativecommons.org/licenses/by-nc-sa/3.0/", "record_count": 300,
                "max_requests": 160, "max_seconds": 900, "min_request_interval_seconds": 1.0, "sampling_complete": False,
                "topic_ids": [10], "selected_topic_count": 1, "exclusions": {name: 0 for name in VERIFY.SOURCE.EXCLUSIONS},
                "unavailable_post_ids": [], "truncated_topic_ids": [], "collection_complete": True, "stop_reason": "source_exhausted",
                "source_link_count": 300, "observed_created_at_min": records[0]["created_at"], "observed_created_at_max": records[0]["created_at"],
                "fetched_post_count": 300, "elapsed_seconds": 16.0,
                "requests": [{"number": index+1, "endpoint_kind": "category" if index == 0 else "topic_posts", "http_status": 200,
                              "response_bytes": 1000, "response_sha256": "a"*64} for index in range(16)]}
    snapshot = VERIFY.sha(VERIFY.canonical(records))
    dashboard = aggregate(records, results, manifest, "research")
    reported = copy.deepcopy(dashboard)
    reported["derived"] = extended_views(records, results)
    job = {"id": ID, "source": "discourse", "mode": "research", "state": "completed" if acknowledged == 300 else "failed",
           "error_code": None if acknowledged == 300 else "resource_limit_exceeded", "total_items": 300, "completed_items": acknowledged,
           "snapshot_hash": snapshot, "manifest": manifest, "dashboard": dashboard, "raw_expired": 0, "items_expired": 0,
           "request": {"source": "discourse", "mode": "research", "max_qwen_calls": 500, "audit_rate": 0, "seed": 42, "query": VERIFY.QUERY.copy()},
           "items": [{"ordinal": index, "record": record, "result": result} for index, (record, result) in enumerate(zip(records, results))]}
    entry = {key: copy.deepcopy(job[key]) for key in ("id", "state", "error_code", "total_items", "completed_items", "snapshot_hash", "manifest")}
    entry.update(dashboard=reported, elapsed_seconds=10.0, started_monotonic=10.0, ended_monotonic=20.0,
                 readiness_started_monotonic=0.0, readiness_ended_monotonic=10.0,
                 readiness_indices=list(range(10)), exit_observation={"sample_index": 10, "absent_model_keys": ["fake-key"]},
                 manifest_sha256=VERIFY.sha(VERIFY.canonical(manifest)),
                 private_snapshot={"database": "private/validation/exp-080/attempt-1/bench/jobs.sqlite3", "job_id": ID, "snapshot_sha256": snapshot})
    service = {"experiment_id": "EXP-080", "root": str(VERIFY.ROOT), "bench_root": str(VERIFY.BENCH), "port": 8790,
               "pid": 123, "process_key": "123|Mon Aug 31 00:00:00 2026", "start_time": "Mon Aug 31 00:00:00 2026"}
    plan = {"experiment_id": "EXP-080", "service": service, "query": VERIFY.QUERY.copy(), "mode": "research",
            "max_qwen_calls": 500, "audit_rate": 0, "seed": 42, "maximum_seconds": 3600,
            "planned_jobs": 1, "planned_records_min": 300, "planned_records_max": 400}
    run = {"experiment_id": "EXP-080", "stage": "discourse_formal", "attempt": 1,
           "status": "Completed" if acknowledged == 300 else "Stopped", "failure_code": None if acknowledged == 300 else "critical_memory_pressure",
           "training": False, "gold_accessed": False, "validation_accessed": False, "test_accessed": False, "raw_read_by_driver": False,
           "unacknowledged_model_attempts": "not_applicable_completed_job" if acknowledged == 300 else "unknown",
           "started_monotonic": 0.0, "ended_monotonic": 21.0, "elapsed_seconds": 21.0, "jobs": [entry],
           "readiness": [{"status": "Ready", "started_monotonic": 0.0, "ended_monotonic": 10.0,
                          "observed_sample_indices": [], "readiness_indices": list(range(10))}]}
    return plan, run, service, entry, job


class FakeMonitor:
    def __init__(self):
        self.reason = None
        self.samples = [{"index": index} for index in range(10)]
    def set_job(self, identifier):
        self.job_id = identifier


class FakeSupport:
    @staticmethod
    def wait_ready(monitor, deadline, timeout=60):
        return list(range(10))
    @staticmethod
    def wait_absent(monitor, after_index, deadline, timeout=15):
        return {"sample_index": 10, "absent_model_keys": ["fake-key"]}
    @staticmethod
    def cancel_and_confirm(identifier, api, monitor, timeout=15):
        api(f"jobs/{identifier}/cancel", {}, timeout=timeout)
        return {"terminal_confirmed": True, "models_absent_confirmed": True, "normal_exit": False,
                "exit_observation": {"sample_index": 10, "absent_model_keys": ["fake-key"]}}


class FormalTests(unittest.TestCase):
    def test_verifier_cli_temp_database_artifact_roundtrip_create_only(self):
        plan, run, service, entry, job = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            target = root / "private/validation/exp-080/attempt-1"
            bench = target / "bench"
            prior_dir = root / "private/validation/exp-079/attempt-3"
            for directory in (bench, prior_dir, root / "topicweb", root / "docs", root / "protocols"):
                directory.mkdir(parents=True, exist_ok=True)
            def write(path, value):
                with path.open("x") as output:
                    output.write(json.dumps(value, sort_keys=True))
                return VERIFY.SOURCE.file_hash(path)
            implementation = root / "topicweb/core.py"
            implementation.write_text("# Synthetic bound implementation; never imported\n")
            sources = {"topicweb/core.py": VERIFY.SOURCE.file_hash(implementation)}
            prior_plan = {"sources": sources, "reduced_background_sha256": VERIFY.sha("Synthetic protocol/review; no source collection\n")}
            plan_hash = write(prior_dir / "plan.json", prior_plan)
            prior_run = {"experiment_id": "EXP-079", "status": "Completed", "failure_code": None,
                         "plan_sha256": plan_hash, "environment": {"fixture": True}}
            prior_hash = write(prior_dir / "run.json", prior_run)
            prior_verified = {"experiment_id": "EXP-079", "status": "Passed", "exp079_complete": True,
                              "operational_state": "safe-to-continue", "source_hashes": {
                                  "private/validation/exp-079/attempt-3/run.json": prior_hash,
                                  "private/validation/exp-079/attempt-3/plan.json": plan_hash}}
            write(prior_dir / "verification.json", prior_verified)
            protocols = {name: root / "protocols" / (name + ".md") for name in ("formal", "decision", "source", "correction", "background")}
            review = root / "docs/discourse-source-review.md"
            for path in (*protocols.values(), review):
                path.write_text("Synthetic protocol/review; no source collection\n")
            service.update(root=str(root), bench_root=str(bench))
            service_hash = write(target / "service.json", service)
            plan.update(sources=sources, environment=prior_run["environment"], service_sha256=service_hash,
                        protocol_sha256=VERIFY.SOURCE.file_hash(protocols["formal"]),
                        decision_sha256=VERIFY.SOURCE.file_hash(protocols["decision"]),
                        source_protocol_sha256=VERIFY.SOURCE.file_hash(protocols["source"]),
                        source_review_sha256=VERIFY.SOURCE.file_hash(review),
                        observer_correction_path=str(protocols["correction"].relative_to(root.parent)),
                        observer_correction_sha256=VERIFY.SOURCE.file_hash(protocols["correction"]),
                        background_reduction_path=str(protocols["background"].relative_to(root.parent)),
                        background_reduction_sha256=VERIFY.SOURCE.file_hash(protocols["background"]),
                        prior_exp079={name: {"path": "private/validation/exp-079/attempt-3/" + name + ".json",
                                             "sha256": VERIFY.SOURCE.file_hash(prior_dir / (name + ".json"))}
                                      for name in ("plan", "run", "verification")})
            actual_plan = write(target / "plan.json", plan)
            claim = {"experiment_id": "EXP-080", "plan_sha256": actual_plan, "started_at": "2026-08-31T00:00:00Z", "started_monotonic": 0.0}
            claim_hash = write(target / "run-claim.json", claim)
            for name in ("system-process-samples.jsonl", "process-events.jsonl"):
                (target / name).write_text("")
            run.update(plan_sha256=actual_plan, run_claim_sha256=claim_hash, started_at=claim["started_at"],
                       samples_sha256=VERIFY.SOURCE.file_hash(target / "system-process-samples.jsonl"),
                       process_events_sha256=VERIFY.SOURCE.file_hash(target / "process-events.jsonl"))
            write(target / "run.json", run)
            metadata = {key: value for key, value in job.items() if key != "items"}
            metadata["progress"] = {}
            with sqlite3.connect(bench / "jobs.sqlite3") as db:
                columns = ",".join(name + (" INTEGER" if type(value) is int else " TEXT") for name, value in metadata.items())
                db.execute("CREATE TABLE jobs (" + columns + ")")
                db.execute("CREATE TABLE items(job_id TEXT,ordinal INTEGER,record TEXT,result TEXT)")
                values = [json.dumps(value) if isinstance(value, (dict, list)) else value for value in metadata.values()]
                db.execute("INSERT INTO jobs VALUES (" + ",".join("?" for _ in values) + ")", values)
                db.executemany("INSERT INTO items VALUES(?,?,?,?)",
                               [(ID, row["ordinal"], json.dumps(row["record"]), json.dumps(row["result"])) for row in job["items"]])
            with patch.multiple(VERIFY, ROOT=root, RUN=target, BENCH=bench, PRIOR=prior_dir, PROTOCOL=protocols["formal"], DECISION=protocols["decision"], OBSERVER_CORRECTION=protocols["correction"], BACKGROUND_REDUCTION=protocols["background"], REVIEW=review), \
                    patch.object(VERIFY.SOURCE, "PROTOCOL", protocols["source"]), \
                    patch.object(VERIFY, "service_is_stopped"), \
                    patch.object(VERIFY.SAFETY, "verify_safety", return_value={"gate_passed": True}), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(VERIFY.main([]), 0)
                saved = json.loads((target / "verification.json").read_text())
                self.assertTrue(saved["exp080_complete"])
                self.assertFalse(saved["old_exp078_relabelled"])
                self.assertEqual(stat.S_IMODE((target / "verification.json").stat().st_mode), 0o600)
                with self.assertRaises(VERIFY.LOCAL.VerificationError):
                    VERIFY.main([])

    def test_real_independent_safety_roundtrip_and_critical_stop(self):
        plan, run, service, entry, job = fixture()
        start = "Mon Aug 31 00:00:00 2026"
        child_start = "Mon Aug 31 00:01:00 2026"
        key = "124|" + child_start
        service.update(comm="Python", process_key="123|" + start, start_time=start)
        samples = []
        for index in range(13):
            parent = {"pid": 123, "ppid": 1, "current_rss_bytes": 100*1024**2,
                      "start_time": start, "process_key": service["process_key"], "comm": "Python"}
            child = {"pid": 124, "ppid": 123, "current_rss_bytes": 500*1024**2,
                     "start_time": child_start, "process_key": key, "comm": "Python"}
            live = index in (10, 11)
            selected = [f"123 1 102400 {start} Python"]
            if live:
                selected.append(f"124 123 512000 {child_start} Python")
            samples.append({"index": index, "started_monotonic": float(index), "monotonic": float(index),
                            "system": {"status": "observed", "monotonic": float(index), "pressure_raw": "1",
                                       "pressure_level": 1, "page_size": 16384, "swapins": 0, "swapouts": 0,
                                       "vm_stat_raw": "Mach Virtual Memory Statistics: (page size of 16384 bytes)\nSwapins: 0.\nSwapouts: 0.\n"},
                            "processes": {"status": "observed", "parent": parent, "models": [child] if live else [],
                                          "orphan_models": [], "seen_model_keys": [key] if index >= 10 else [],
                                          "absent_model_keys": [key] if index == 12 else [], "selected_ps": selected},
                            "disk_free_bytes": 10*1024**3})
        events = [{"type": kind, "job_id": ID, "monotonic": stamp, "pid": None if kind == "constructor_started" else 124,
                   "process_key": None if kind == "constructor_started" else key,
                   "returncode": 0 if kind in {"process_exit", "final_gate_passed"} else None,
                   "normal_exit": kind == "final_gate_passed"}
                  for kind, stamp in (("constructor_started", 9.6), ("ready", 9.7), ("process_exit", 11.5), ("final_gate_passed", 11.6))]
        entry.update(readiness_started_monotonic=0.0, readiness_ended_monotonic=9.25, started_monotonic=9.5,
                     ended_monotonic=11.7, elapsed_seconds=2.2, exit_observation={"sample_index": 12, "absent_model_keys": [key]})
        run.update(ended_monotonic=13.0, elapsed_seconds=13.0,
                   readiness=[{"status": "Ready", "started_monotonic": 0.0, "ended_monotonic": 9.25,
                               "readiness_indices": list(range(10)), "observed_sample_indices": list(range(10))}])
        result = VERIFY.verify_run(plan, run, service, samples, events, {ID: job})
        self.assertTrue(result["exp080_complete"])
        self.assertTrue(result["safety"]["readiness_gate"])
        self.assertTrue(result["safety"]["exit_gate"])
        samples[-1]["system"].update(pressure_raw="4", pressure_level=4)
        run.update(status="Stopped", failure_code="critical_memory_pressure", unacknowledged_model_attempts="unknown")
        result = VERIFY.verify_run(plan, run, service, samples, events, {ID: job})
        self.assertFalse(result["exp080_complete"])
        self.assertEqual(result["operational_state"], "stop-required")

    def test_prior_requires_new_exp079_safe_and_real_hash_bindings(self):
        run, verification = prior()
        RUNNER.prior_gate(run, verification, run_hash="b"*64, plan_hash="a"*64)
        VERIFY.check_prior(run, verification, run_hash="b"*64, plan_hash="a"*64)
        for change in ({"operational_state": "stop-required"}, {"exp079_complete": False}, {"status": "Failed"}, {"experiment_id": "EXP-078"}):
            bad = {**verification, **change}
            with self.assertRaises(RUNNER.FormalError):
                RUNNER.prior_gate(run, bad, run_hash="b"*64, plan_hash="a"*64)
            with self.assertRaises(VERIFY.LOCAL.VerificationError):
                VERIFY.check_prior(run, bad, run_hash="b"*64, plan_hash="a"*64)
        with self.assertRaises(RUNNER.FormalError):
            RUNNER.prior_gate(run, verification, run_hash="c"*64, plan_hash="a"*64)
        stale = copy.deepcopy(verification)
        stale["source_hashes"] = {path.replace("/attempt-3/", "/attempt-2/"): value for path, value in stale["source_hashes"].items()}
        with self.assertRaises(RUNNER.FormalError):
            RUNNER.prior_gate(run, stale, run_hash="b"*64, plan_hash="a"*64)
        with self.assertRaises(VERIFY.LOCAL.VerificationError):
            VERIFY.check_prior(run, stale, run_hash="b"*64, plan_hash="a"*64)

    def test_source_scope_permits_only_explicit_dependencies(self):
        old = {"topicweb/core.py": "a"*64, "requirements.txt": "b"*64}
        current = {**old, **{name: "c"*64 for name in RUNNER.ADDITIONAL_SOURCES}}
        RUNNER.source_scope(old, current)
        VERIFY.check_prior_scope(old, current, VERIFY.ADDITIONAL_SOURCES)
        for bad in ({**current, "scripts/unreviewed.py": "d"*64}, {**current, "topicweb/core.py": "e"*64}):
            with self.assertRaises(RUNNER.FormalError):
                RUNNER.source_scope(old, bad)
            with self.assertRaises(VERIFY.LOCAL.VerificationError):
                VERIFY.check_prior_scope(old, bad, VERIFY.ADDITIONAL_SOURCES)

    def test_complete_source_roundtrip_uses_own_lifecycle_and_pure_helpers(self):
        plan, run, service, entry, job = fixture()
        with patch.object(VERIFY.SOURCE, "verify", side_effect=AssertionError("must not relabel EXP078")), patch.object(VERIFY.SAFETY, "verify_safety", return_value={"gate_passed": True}) as safety:
            result = VERIFY.verify_run(plan, run, service, [], [], {ID: job})
        self.assertTrue(result["exp080_complete"])
        self.assertEqual(result["operational_state"], "safe-to-continue")
        self.assertEqual(safety.call_args.kwargs["limit_seconds"], 3600)
        self.assertEqual(result["jobs"][0]["source"]["records"], 300)
        self.assertEqual(result["jobs"][0]["acknowledged_derived"]["routing"]["cost"]["m1_attempts"], 3)

    def test_safety_negative_and_partial_unknown_never_complete(self):
        plan, run, service, entry, job = fixture(0)
        with patch.object(VERIFY.SAFETY, "verify_safety", return_value={"gate_passed": False, "system": {"critical": True}}):
            result = VERIFY.verify_run(plan, run, service, [], [], {ID: job})
        self.assertFalse(result["exp080_complete"])
        self.assertEqual(result["operational_state"], "stop-required")
        self.assertEqual(result["jobs"][0]["acknowledged_rows"], 0)
        self.assertIsNone(result["jobs"][0]["model_peak_observations"])
        self.assertEqual(result["jobs"][0]["unacknowledged_model_attempts"], "unknown")
        plan, run, service, entry, job = fixture(298)
        with patch.object(VERIFY.SAFETY, "verify_safety", return_value={"gate_passed": False}):
            result = VERIFY.verify_run(plan, run, service, [], [], {ID: job})
        self.assertEqual(result["jobs"][0]["acknowledged_rows"], 298)
        self.assertFalse(result["exp080_complete"])

    def test_old_experiment_and_old_database_namespace_are_rejected(self):
        plan, run, service, entry, job = fixture()
        bad = {**plan, "experiment_id": "EXP-078"}
        with self.assertRaises(VERIFY.LOCAL.VerificationError):
            VERIFY.verify_run(bad, run, service, [], [], {ID: job})
        entry["private_snapshot"]["database"] = "private/validation/exp-079/attempt-3/bench/jobs.sqlite3"
        with self.assertRaises(VERIFY.LOCAL.VerificationError):
            VERIFY.check_job(entry, job, complete=True)

    def test_runner_submits_once_only_after_readiness_and_observes_exit(self):
        _, _, _, entry, job = fixture()
        calls = []
        def api(path, payload=None, **kwargs):
            calls.append((path, payload))
            return entry["dashboard"] if path.endswith("/dashboard") else {"job": job}
        monitor = FakeMonitor()
        result = RUNNER.execute(monitor, FakeSupport, call=api)
        self.assertEqual(result["status"], "Completed")
        self.assertEqual(sum(path == "jobs" for path, _ in calls), 1)
        self.assertEqual(calls[0][1]["mode"], "research")
        self.assertEqual(calls[0][1]["max_qwen_calls"], 500)
        self.assertIn("exit_observation", result["jobs"][0])
        self.assertEqual(result["jobs"][0]["private_snapshot"]["database"], "private/validation/exp-080/attempt-1/bench/jobs.sqlite3")

    def test_not_ready_or_lost_submission_is_not_retried(self):
        monitor = FakeMonitor()
        with patch.object(FakeSupport, "wait_ready", side_effect=RuntimeError("quiet_window_not_ready")), patch.object(RUNNER, "api") as api:
            result = RUNNER.execute(monitor, FakeSupport, call=api)
        self.assertEqual(result["status"], "Stopped")
        self.assertEqual(result["jobs"], [])
        api.assert_not_called()
        with patch.object(RUNNER, "database_job_ids", return_value=[]), patch.object(RUNNER, "api", side_effect=TimeoutError()) as api:
            result = RUNNER.execute(monitor, FakeSupport, call=api)
        self.assertEqual(result["status"], "Stopped")
        self.assertEqual(result["jobs"][0]["submission_outcome"], "unknown")
        self.assertEqual(api.call_count, 1)


if __name__ == "__main__":
    unittest.main()
