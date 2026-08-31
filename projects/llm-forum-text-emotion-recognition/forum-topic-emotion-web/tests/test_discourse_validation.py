"""Synthetic EXP-078 runner/verifier tests; no source or model is contacted."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import unicodedata


ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DRIVER = load("test_exp078_driver", "run_discourse_validation.py")
VERIFY = load("test_exp078_verifier", "verify_discourse_validation.py")
ID = "d" * 32


def soak():
    run = {"experiment_id": "EXP-077", "status": "Completed", "failure_code": None, "plan_sha256": "a" * 64}
    verification = {"experiment_id": "EXP-077", "status": "Passed", "exp077_complete": True,
                    "gates": {"base": True}, "operational_state": "safe-to-continue", "soak_gate_passed": False,
                    "source_hashes": {"private/validation/exp-077/attempt-1/run.json": "b" * 64,
                                      "private/validation/exp-077/attempt-1/plan.json": "a" * 64}}
    bindings = {"run": {"sha256": "b" * 64}, "plan": {"sha256": "a" * 64}}
    return run, verification, bindings


def fixture():
    records, results = [], []
    seen, seen_third = set(), set()
    total = {key: 0 for key in VERIFY.LOCAL.COSTS}
    for ordinal in range(300):
        topic, number, identifier = 100 - ordinal // 75, ordinal % 75 + 1, 10000 + ordinal
        group = ordinal % 17
        text = f"synthetic raw {group}"
        digest = VERIFY.sha(text)
        raw = {"id": identifier, "topic_id": topic, "post_number": number, "post_type": 1, "raw": text,
               "created_at": "2026-08-10T00:00:00Z", "username": "fixture_user", "user_id": 12,
               "reply_to_post_number": number - 1 if number > 1 else None}
        identity = ["discourse", "discuss.python.org", "post", str(identifier)]
        record = {"source": identity[0], "site": identity[1], "object_type": "post", "source_object_id": str(identifier),
                  "record_id": VERIFY.sha(json.dumps(identity, ensure_ascii=False, separators=(",", ":"))),
                  "model_input_text": text, "model_input_hash": digest,
                  "dedup_hash": VERIFY.sha(" ".join(unicodedata.normalize("NFKC", text).casefold().split())),
                  "source_payload_raw": raw, "thread_id": str(topic), "parent_object_id": str(identifier-1) if number > 1 else None,
                  "source_url": f"https://discuss.python.org/t/{topic}/{number}", "created_at": raw["created_at"],
                  "author_display_name": "fixture_user", "content_license": "CC BY-NC-SA 3.0",
                  "provenance": {"category_id": 7, "topic_id": topic, "post_number": number,
                                 "reply_to_post_number": raw["reply_to_post_number"], "text_field": "raw", "author_username": "fixture_user",
                                 "license_url": "https://creativecommons.org/licenses/by-nc-sa/3.0/", "source_policy_url": "https://discuss.python.org/tos"}}
        requested = group % 3 == 0
        costs = {key: 0 for key in total}
        costs.update(m1_attempts=int(digest not in seen), m1_cache_hit=int(digest in seen))
        seen.add(digest)
        if requested:
            costs.update(m3_attempts=int(digest not in seen_third), m3_succeeded=int(digest not in seen_third), m3_cache_hit=int(digest in seen_third))
            seen_third.add(digest)
        for key, value in costs.items():
            total[key] += value
        m1, m3 = [1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0] if requested else None
        prediction = m3 or m1
        result = {"prediction": prediction, "m1_prediction": m1, "m3_prediction": m3,
                  "m1_probabilities": [.7, .2, .1, .1, .1, .1], "m3_probabilities": [.1, .8, .1, .1, .1, .1] if requested else None,
                  "active_labels": ["joy" if requested else "love"], "neutral": False,
                  "route_requested": requested, "used_path": "m3" if requested else "m1", "fallback": False, "fallback_reason": None,
                  "counters": {**costs, "fallback_reason": None}, "cumulative_counters": total.copy(), "latency_ms": 2.0,
                  "fingerprint": "f" * 64, "tokenlengths": {"m1": {"input_tokens": 11, "used_tokens": 11, "truncated": False},
                                                           "m3": {"input_tokens": 20, "used_tokens": 20, "truncated": False} if requested else None},
                  "truncflags": {"m1": False, "m3": False if requested else None},
                  "resources": {"peak_rss_bytes": 1024, "mlx_peak_bytes": 2048 if requested else 0, "elapsed_seconds": 1.0}}
        records.append(record)
        results.append(result)
    manifest = {"source": "discourse", "site": "discuss.python.org", "category_id": 7, "category_name": "Python Help",
                "cohort": "latest_created_public_unpinned_topics_prefix", "topic_order": "created_desc", "post_order": "post_number_asc",
                "window_bounds": "not_a_time_window", "max_topics": 100, "max_items": 400, "text_field": "raw",
                "normalization_for_model_input": "none", "content_license": "CC BY-NC-SA 3.0",
                "license_url": "https://creativecommons.org/licenses/by-nc-sa/3.0/", "record_count": 300,
                "max_requests": 160, "max_seconds": 900, "min_request_interval_seconds": 1.0,
                "sampling_complete": False, "topic_ids": [100, 99, 98, 97], "selected_topic_count": 4,
                "exclusions": {name: 0 for name in VERIFY.EXCLUSIONS}, "unavailable_post_ids": [], "truncated_topic_ids": [],
                "collection_complete": True, "stop_reason": "source_exhausted", "source_link_count": 300,
                "observed_created_at_min": records[0]["created_at"], "observed_created_at_max": records[0]["created_at"],
                "fetched_post_count": 300, "elapsed_seconds": 5.0,
                "requests": [{"number": number, "endpoint_kind": "category" if number == 1 else "topic", "http_status": 200,
                              "response_bytes": 1000, "response_sha256": "c" * 64} for number in range(1, 6)]}
    dashboard = VERIFY.LOCAL.recalculate(records, results, "research")
    snapshot = VERIFY.LOCAL.check_records(records)
    request = {"source": "discourse", "mode": "research", "max_qwen_calls": 500, "audit_rate": 0, "seed": 42, "query": DRIVER.QUERY.copy()}
    job = {"id": ID, "source": "discourse", "mode": "research", "state": "completed", "error_code": None,
           "raw_expired": 0, "items_expired": 0, "total_items": 300, "completed_items": 300,
           "snapshot_hash": snapshot, "manifest": manifest, "dashboard": dashboard, "request": request, "progress": {},
           "items": [{"ordinal": index, "record": row, "result": result} for index, (row, result) in enumerate(zip(records, results))]}
    entry = {"id": ID, "status": "Passed", "state": "completed", "total_items": 300, "completed_items": 300,
             "snapshot_hash": snapshot, "manifest": copy.deepcopy(manifest), "manifest_sha256": VERIFY.sha(VERIFY.canonical(manifest)),
             "dashboard": copy.deepcopy(dashboard), "elapsed_seconds": 30.0,
             "private_snapshot": {"database": "private/jobs.sqlite3", "job_id": ID, "snapshot_sha256": snapshot}}
    entry["dashboard"]["derived"] = VERIFY.recalculate_derived(records, results)
    run = {"experiment_id": "EXP-078", "stage": "discourse_operational", "attempt": 1, "status": "Passed", "query": DRIVER.QUERY.copy(),
           "seed": 42, "label_order": list(VERIFY.LOCAL.LABELS), "maximum_seconds": 3600,
           "training": False, "validation_accessed": False, "test_accessed": False, "external_gold_accessed": False,
           "source_raw_read_by_driver": False, "job": entry}
    return run, job


class DiscourseValidationTests(unittest.TestCase):
    def test_plateau_negative_but_safe_soak_can_continue(self):
        run, verification, bindings = soak()
        DRIVER.check_soak(run, verification, run_hash="b"*64, plan_hash="a"*64)
        VERIFY.check_soak(run, verification, bindings)

    def test_unknown_critical_or_runtime_failed_soak_is_blocked(self):
        for change in ({"operational_state": "stop-required"}, {"exp077_complete": False}, {"gates": {"base": False}}, {"status": "Failed"}):
            run, verification, bindings = soak()
            verification.update(change)
            with self.subTest(change=change), self.assertRaises(DRIVER.RunError):
                DRIVER.check_soak(run, verification, run_hash="b"*64, plan_hash="a"*64)
            with self.assertRaises(VERIFY.LOCAL.VerificationError):
                VERIFY.check_soak(run, verification, bindings)
        run, verification, _ = soak()
        run["failure_code"] = "runtime_job_failed"
        with self.assertRaises(DRIVER.RunError):
            DRIVER.check_soak(run, verification, run_hash="b"*64, plan_hash="a"*64)

    def test_only_three_c3_files_may_be_added_after_soak(self):
        source = {"topicweb/core.py": "a"*64, "requirements-lock.txt": "b"*64}
        current = {**source, **{name: "c"*64 for name in DRIVER.C3_TOOLS}}
        DRIVER.check_source_scope(source, current)
        VERIFY.check_source_scope(source, current)
        for changed in ({**current, "topicweb/new_producer.py": "d"*64}, {**current, "topicweb/core.py": "e"*64}):
            with self.assertRaises(DRIVER.RunError):
                DRIVER.check_source_scope(source, changed)
            with self.assertRaises(VERIFY.LOCAL.VerificationError):
                VERIFY.check_source_scope(source, changed)

    def test_driver_creates_one_job_and_never_reads_raw_items(self):
        run, job = fixture()
        calls = []
        public = {key: value for key, value in job.items() if key not in {"items", "request"}}
        def call(path, payload=None, method=None):
            calls.append((path, payload, method))
            return run["job"]["dashboard"] if path.endswith("/dashboard") else {"job": public}
        result = DRIVER.execute_job(call=call)
        self.assertEqual(result["status"], "Passed")
        self.assertEqual(sum(path == "jobs" and method == "POST" for path, _, method in calls), 1)
        self.assertEqual(calls[0][1]["max_qwen_calls"], 500)
        self.assertEqual(calls[0][1]["query"], DRIVER.QUERY)
        self.assertFalse(any("items" in path for path, _, _ in calls))

    def test_driver_failure_or_insufficient_sample_never_retries(self):
        _, job = fixture()
        for change in ({"state": "failed", "error_code": "source_raw_missing"}, {"total_items": 299, "completed_items": 299}):
            calls = []
            public = {**{key: value for key, value in job.items() if key not in {"items", "request"}}, **change}
            def call(path, payload=None, method=None):
                calls.append((path, method))
                return {"job": public}
            result = DRIVER.execute_job(call=call)
            self.assertEqual(result["status"], "Failed")
            self.assertEqual(sum(path == "jobs" and method == "POST" for path, method in calls), 1)

    def test_independent_native_raw_counts_costs_and_no_gold(self):
        run, job = fixture()
        result = VERIFY.verify(run, job)
        self.assertEqual(result["source"]["records"], 300)
        self.assertEqual(result["derived"]["summary"]["exact_input_groups"], 17)
        self.assertEqual(result["derived"]["routing"]["cost"]["m1_attempts"], 17)
        self.assertEqual(result["derived"]["routing"]["cost"]["m3_attempts"], 6)
        self.assertEqual(result["length_diagnostics"]["m1"]["observed"], 300)
        self.assertNotIn("accuracy", result)

    def test_raw_hash_url_license_and_counts_fail_independently(self):
        for change in (lambda r, j: j["items"][0]["record"].update(model_input_text="altered"),
                       lambda r, j: j["items"][0]["record"].update(source_url="https://example.org"),
                       lambda r, j: j["items"][0]["record"].update(content_license="CC0"),
                       lambda r, j: j.update(completed_items=299),
                       lambda r, j: j["items"][0]["result"]["counters"].update(m1_attempts=0)):
            run, job = fixture()
            change(run, job)
            with self.assertRaises(VERIFY.LOCAL.VerificationError):
                VERIFY.verify(run, job)

    def test_no_fabricated_window_or_complete_threads(self):
        run, job = fixture()
        records = [item["record"] for item in job["items"]]
        for change in ({"from_utc": "2026-08-01T00:00:00Z"}, {"sampling_complete": True},
                       {"unavailable_post_ids": [999999]}, {"truncated_topic_ids": [100], "collection_complete": True}):
            with self.assertRaises(VERIFY.LOCAL.VerificationError):
                VERIFY.check_source(records, {**job["manifest"], **change})
        manifest = copy.deepcopy(job["manifest"])
        manifest.update(unavailable_post_ids=[999999], truncated_topic_ids=[100], collection_complete=False)
        manifest["exclusions"]["unavailable_stream_ids"] = 1
        result = VERIFY.check_source(records, manifest)
        self.assertEqual(result["unavailable_stream_ids"], 1)
        self.assertFalse(result["collection_complete"])

    def test_selected_job_reader_does_not_parse_unrelated_private_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary).resolve() / "jobs.sqlite3"
            with sqlite3.connect(database) as db:
                db.executescript("CREATE TABLE jobs(id TEXT PRIMARY KEY,request TEXT,manifest TEXT,dashboard TEXT,progress TEXT); CREATE TABLE items(job_id TEXT,ordinal INTEGER,record TEXT,result TEXT);")
                db.execute("INSERT INTO jobs VALUES(?,?,?,?,?)", (ID, "{}", "{}", "{}", "{}"))
                db.execute("INSERT INTO items VALUES(?,?,?,?)", (ID, 0, '{"synthetic":true}', "{}"))
                db.execute("INSERT INTO jobs VALUES(?,?,?,?,?)", ("old-so-job", "not-json-must-not-read", "", "", ""))
                db.execute("INSERT INTO items VALUES(?,?,?,?)", ("old-so-job", 0, "not-json-private-raw", ""))
            loaded = VERIFY.read_selected_job(database, ID)
            self.assertEqual(len(loaded["items"]), 1)
            self.assertEqual(loaded["items"][0]["record"], {"synthetic": True})

    def test_derived_independently_checks_fractional_groups_days_weeks_and_known_n(self):
        from topicweb.core import extended_views
        records = [
            {"dedup_hash": "group-a", "object_type": "post", "created_at": "2026-08-23T01:00:00Z"},
            {"dedup_hash": "group-a", "object_type": "question", "created_at": "2026-08-24T01:00:00Z"},
            {"dedup_hash": "group-a", "object_type": "post", "created_at": "2026-08-24T01:00:00Z"},
            {"dedup_hash": "group-b", "object_type": "post", "created_at": None},
            {"dedup_hash": "group-c", "object_type": "post", "created_at": None},
        ]
        results = [
            {"prediction": [1, 0, 0, 0, 0, 0], "route_requested": True, "m1_probabilities": [.1]*6},
            {"prediction": [0, 1, 0, 0, 0, 0], "route_requested": False, "m1_probabilities": [.1]*6},
            None, {"prediction": [0]*6, "m1_probabilities": [.1]*6}, None,
        ]
        actual = extended_views(records, results)
        check = VERIFY.check_derived(records, results, actual)
        self.assertTrue(check["weighting_and_buckets_verified"])
        unique = actual["views"]["normalized_unique_text"]
        self.assertEqual(unique["summary"]["eligible_units"], 3)
        self.assertEqual(unique["summary"]["successful_units"], 2)
        self.assertEqual(unique["emotions"][0]["count"], .5)
        self.assertEqual(unique["emotions"][1]["count"], .5)
        self.assertEqual([row["date"] for row in unique["trends"]["weekly"]], ["2026-08-17", "2026-08-24"])
        self.assertEqual(actual["diagnostics"]["routing"]["actual_known_n"], 2)
        self.assertEqual(actual["diagnostics"]["routing"]["actual_rate"], .5)
        altered = copy.deepcopy(actual)
        altered["views"]["normalized_unique_text"]["emotions"][0]["count"] = 1.0
        with self.assertRaises(VERIFY.LOCAL.VerificationError):
            VERIFY.check_derived(records, results, altered)
        altered = copy.deepcopy(actual)
        altered["diagnostics"]["routing"]["actual_known_n"] = 3
        with self.assertRaises(VERIFY.LOCAL.VerificationError):
            VERIFY.check_derived(records, results, altered)


if __name__ == "__main__":
    unittest.main()
