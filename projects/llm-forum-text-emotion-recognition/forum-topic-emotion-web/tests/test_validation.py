"""Synthetic tests of the independent consumer; no real run is marked Passed."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("independent_local_verification", ROOT / "scripts/verify_local.py")
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def record(text, source_id, *, source="upload", kind="row", created_at=None, payload=None, provenance=None):
    identity = [source, "upload" if source == "upload" else "stackoverflow", kind, source_id]
    return {"source": identity[0], "site": identity[1], "object_type": identity[2], "source_object_id": identity[3],
            "record_id": digest(json.dumps(identity, ensure_ascii=False, separators=(",", ":"))),
            "model_input_text": text, "model_input_hash": digest(text),
            "dedup_hash": digest(" ".join(unicodedata.normalize("NFKC", text).casefold().split())),
            "created_at": created_at, "source_payload_raw": payload or {}, "provenance": provenance or {}}


def results(records, mode, route_hash=None):
    seen, third_seen = set(), set()
    totals = {key: 0 for key in VERIFY.COSTS}
    output = []
    for row in records:
        exact = row["model_input_hash"]
        routed = exact == route_hash and mode != "m1_only"
        use_m3 = mode == "research" and routed
        fallback = "m3_budget_exhausted" if mode == "demo" and routed else None
        m1 = [1, 0, 0, 0, 0, 0]
        m3 = [0, 1, 0, 0, 0, 0] if use_m3 else None
        pred = m3 or m1
        costs = {key: 0 for key in VERIFY.COSTS}
        costs.update(m1_attempts=int(exact not in seen), m1_cache_hit=int(exact in seen))
        seen.add(exact)
        if use_m3:
            costs.update(m3_attempts=int(exact not in third_seen), m3_succeeded=int(exact not in third_seen), m3_cache_hit=int(exact in third_seen))
            third_seen.add(exact)
        for key, value in costs.items():
            totals[key] += value
        output.append({"prediction": pred, "m1_prediction": m1, "m3_prediction": m3,
                       "active_labels": ["joy" if use_m3 else "love"], "neutral": False,
                       "m1_probabilities": [.7, .2, .1, .1, .1, .1],
                       "m3_probabilities": [.1, .9, .1, .1, .1, .1] if use_m3 else None,
                       "route_requested": routed, "used_path": "m3" if use_m3 else "m1",
                       "fallback": bool(fallback), "fallback_reason": fallback,
                       "counters": {**costs, "fallback_reason": fallback}, "cumulative_counters": dict(totals),
                       "latency_ms": 1.0, "fingerprint": "a" * 64})
    return output


def fixture_bundle(routing=True):
    raw = (ROOT / "tests/fixtures/operational.jsonl").read_text()
    fixture_hash = digest(raw)
    fixtures = [json.loads(line) for line in raw.splitlines()]
    authored = [record(row["text"], f"{fixture_hash}:{index}", created_at=row.get("created_at"), payload=row,
                       provenance={"file_sha256": fixture_hash, "row_number": index, "line_number": index,
                                   "supplied_id": row["id"], "text_field": "text"})
                for index, row in enumerate(fixtures, 1)]
    source_record = record("Synthetic source question", "1001", source="stackexchange", kind="question",
                           created_at="2026-08-24T00:00:00Z",
                           payload={"question_id": 1001, "body_markdown": "Synthetic source question", "creation_date": 1787529600},
                           provenance={"question_id": 1001, "filter_id": "nFzTOPGAOEckIq4Pwr_RZ8", "text_field": "body_markdown"})
    source_record.update(thread_id="1001", source_url="https://stackoverflow.com/q/1001")
    source_manifest = {"source": "stackexchange", "site": "stackoverflow", "cohort": "questions_created_in_window",
                       "query": "", "tags": "python", "from_utc": "2026-08-23T00:00:00Z", "to_utc": "2026-08-30T00:00:00Z",
                       "window_bounds": "start_inclusive_end_exclusive", "sort": "creation", "order": "asc",
                       "max_questions": 100, "max_items": 500, "filter_id": "nFzTOPGAOEckIq4Pwr_RZ8", "text_field": "body_markdown",
                       "normalization_for_model_input": "none", "record_count": 1, "included_types": ["question", "answer", "comment"],
                       "sampling_complete": True, "stop_reason": "complete", "requests": [{"endpoint": "search/advanced"}],
                       "selected_question_count": 1, "counts_by_type": {"question": 1, "answer": 0, "comment": 0}}
    modes = ["m1_only", "research", "demo", "research", "m1_only"]
    jobs, entries = {}, []
    for index, mode in enumerate(modes):
        job_id = "synthetic-job-" + str(index)
        rows = copy.deepcopy(authored if index < 4 else [source_record])
        outputs = results(rows, mode, authored[0]["model_input_hash"] if routing else None)
        dashboard = VERIFY.recalculate(rows, outputs, mode)
        manifest = source_manifest if index == 4 else {"source": "upload", "record_count": 8}
        snapshot = digest(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        state = "completed_with_fallback" if any(row["fallback"] for row in outputs) else "completed"
        jobs[job_id] = {"id": job_id, "mode": mode, "state": state, "error_code": None, "raw_expired": 0, "items_expired": 0,
                        "total_items": len(rows), "completed_items": len(rows), "snapshot_hash": snapshot,
                        "manifest": copy.deepcopy(manifest), "dashboard": copy.deepcopy(dashboard),
                        "items": [{"ordinal": number, "record": row, "result": out} for number, (row, out) in enumerate(zip(rows, outputs))],
                        "replay_of": "synthetic-job-1" if index == 3 else None}
        dashboard["routing"].update(cost_scope="completed_job", cost_complete=True)
        entries.append({"id": job_id, "mode": mode, "state": state, "total_items": len(rows), "completed_items": len(rows),
                        "snapshot_hash": snapshot, "manifest": copy.deepcopy(manifest), "dashboard": dashboard})
    base = {"experiment_id": "EXP-076", "status": "Passed", "input_sha256": fixture_hash, "fixture_sha256": fixture_hash,
            "validation_accessed": False, "test_accessed": False, "training": False, "external_gold_accessed": False}
    smoke = {**base, "stage": "smoke", "jobs": entries[:4]}
    source = {**base, "stage": "source", "jobs": entries[4:], "input_sha256": entries[4]["snapshot_hash"]}
    return smoke, source, jobs, fixtures, fixture_hash


class ValidationTests(unittest.TestCase):
    def test_known_counts_costs_and_descriptive_denominators(self):
        smoke, source, jobs, fixtures, fixture_hash = fixture_bundle()
        report = VERIFY.verify(smoke, source, jobs, fixtures, fixture_hash)
        research = report["jobs"][1]
        self.assertEqual(research["summary"]["successful_items"], 8)
        self.assertEqual(research["summary"]["exact_input_groups"], 7)
        self.assertEqual(research["summary"]["normalized_text_groups"], 6)
        self.assertEqual(research["summary"]["undated_items"], 1)
        self.assertEqual([row["count"] for row in research["emotions"]], [6, 2, 0, 0, 0, 0])
        self.assertEqual(research["emotions"][1]["prevalence"], .25)
        self.assertEqual(research["routing"]["cost"]["m1_attempts"], 7)
        self.assertEqual(research["routing"]["cost"]["m1_cache_hit"], 1)
        self.assertEqual(research["routing"]["cost"]["m3_attempts"], 1)
        self.assertEqual(report["replay"]["m3_rows"], 2)
        self.assertEqual(report["replay"]["m3_coverage"], .25)
        self.assertEqual(report["jobs"][2]["routing"]["fallbacks"], {"m3_budget_exhausted": 2})

    def test_zero_routed_rows_is_reported_as_insufficient_not_failure(self):
        report = VERIFY.verify(*fixture_bundle(routing=False))
        self.assertEqual(report["replay"]["m3_coverage_status"], "insufficient_no_routed_pairs")
        self.assertIsNone(report["replay"]["m3_max_abs"])
        self.assertIsNone(report["jobs"][1]["routing"]["paired_disagreement"])

    def test_missing_predictions_never_become_neutral(self):
        rows = [record("one", "one"), record("two", "two")]
        result = results(rows[:1], "m1_only")[0]
        result.update(prediction=[0] * 6, m1_prediction=[0] * 6, active_labels=[], neutral=True)
        summary = VERIFY.recalculate(rows, [result, None], "m1_only")["summary"]
        self.assertEqual(summary["coverage"], .5)
        self.assertEqual(summary["neutral_count"], 1)
        self.assertEqual(summary["neutral_rate"], 1.)
        self.assertEqual(summary["missing_predictions"], 1)

    def test_hash_snapshot_and_fixture_mutations_fail(self):
        for field, value in (("model_input_hash", "0" * 64), ("record_id", "0" * 64), ("dedup_hash", "0" * 64)):
            bundle = fixture_bundle()
            bundle[2]["synthetic-job-0"]["items"][0]["record"][field] = value
            with self.assertRaises(VERIFY.VerificationError):
                VERIFY.verify(*bundle)
        bundle = fixture_bundle()
        bundle[2]["synthetic-job-0"]["snapshot_hash"] = "0" * 64
        with self.assertRaisesRegex(VERIFY.VerificationError, "snapshot_hash_mismatch"):
            VERIFY.verify(*bundle)

    def test_wrong_prevalence_or_cost_does_not_pass(self):
        bundle = fixture_bundle()
        bundle[2]["synthetic-job-1"]["dashboard"]["emotions"][0]["prevalence"] = .1
        with self.assertRaisesRegex(VERIFY.VerificationError, "aggregate_mismatch"):
            VERIFY.verify(*bundle)
        bundle = fixture_bundle()
        bundle[2]["synthetic-job-0"]["items"][5]["result"]["counters"]["m1_attempts"] = 1
        with self.assertRaisesRegex(VERIFY.VerificationError, "component_cost_mismatch"):
            VERIFY.verify(*bundle)

    def test_demo_m3_attempt_and_cross_job_cache_are_rejected(self):
        for job_id, counter in (("synthetic-job-2", "m3_attempts"), ("synthetic-job-3", "m1_cache_hit")):
            bundle = fixture_bundle()
            bundle[2][job_id]["items"][0]["result"]["counters"][counter] = 1
            with self.assertRaisesRegex(VERIFY.VerificationError, "component_cost_mismatch"):
                VERIFY.verify(*bundle)

    def test_replay_probability_change_beyond_tolerance(self):
        bundle = fixture_bundle()
        repeated = bundle[2]["synthetic-job-3"]
        repeated["items"][0]["result"]["m3_probabilities"][0] += 1e-5
        with self.assertRaisesRegex(VERIFY.VerificationError, "replay_probability_mismatch"):
            VERIFY.verify(*bundle)

    def test_source_outside_window_or_wrong_url_is_rejected(self):
        for key, value in (("source_url", "https://example.com/q/1001"), ("created_at", "2026-09-01T00:00:00Z")):
            bundle = fixture_bundle()
            record = bundle[2]["synthetic-job-4"]["items"][0]["record"]
            record[key] = value
            manifest = bundle[2]["synthetic-job-4"]["manifest"]
            with self.assertRaises(VERIFY.VerificationError):
                VERIFY.check_source([record], manifest)

    def test_failed_or_absent_producer_never_creates_pass(self):
        bundle = fixture_bundle()
        bundle[0]["status"] = "Failed"
        with self.assertRaisesRegex(VERIFY.VerificationError, "producer_stage_not_passed"):
            VERIFY.verify(*bundle)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with patch.object(VERIFY, "ROOT", root):
                with self.assertRaises(VERIFY.VerificationError):
                    VERIFY.main([])
            self.assertFalse((root / "private/validation/exp-076/attempt-1/verification.json").exists())

    def test_sqlite_reader_does_not_change_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory).resolve() / "jobs.sqlite3"
            with sqlite3.connect(database) as connection:
                connection.executescript("CREATE TABLE jobs(id TEXT,request TEXT,progress TEXT,manifest TEXT,dashboard TEXT); CREATE TABLE items(job_id TEXT,ordinal INTEGER,record TEXT,result TEXT);")
                connection.execute("INSERT INTO jobs VALUES('j','{}','{}','{}','{}')")
                connection.execute("INSERT INTO items VALUES('j',0,'{}',NULL)")
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            loaded = VERIFY.read_jobs(database, ["j"])
            self.assertEqual(loaded["j"]["items"][0]["ordinal"], 0)
            self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), before)


class InheritedIdentityTests(unittest.TestCase):
    def setup_artifacts(self, directory):
        root = Path(directory).resolve() / "web"
        root.mkdir()
        old_code = {"start.py": "start", "topicweb/inference_process.py": "frozen inference",
                    "topicweb/core.py": "frozen core", "topicweb/app.py": "unchanged app",
                    "topicweb/adapters.py": "old collector", "topicweb/worker.py": "old worker",
                    "scripts/validate_local.py": "old runner", "scripts/verify_local.py": "old verifier",
                    "tests/test_validation.py": "old tests", "tests/fixtures/operational.jsonl": "fixture\n"}
        for name, text in old_code.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        first, second = (root / f"private/validation/exp-076/attempt-{n}" for n in (1, 2))
        first.mkdir(parents=True)
        second.mkdir()
        archive_path = second / "inherited-code.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            for name in old_code:
                archive.add(root / name, arcname=name, recursive=False)
        inherited_protocol = second / "inherited-protocol.md"
        inherited_protocol.write_text("original protocol\n")
        protocol = root.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-076-phase-c-local-system.md"
        protocol.parent.mkdir(parents=True)
        protocol.write_text("original protocol\n\nattempt two appended scope\n")
        old_sources = {name: digest(text) for name, text in old_code.items() if not name.endswith(".jsonl")}
        smoke = {"sources": old_sources, "protocol_sha256": digest("original protocol\n"),
                 "fixture_sha256": digest("fixture\n"), "experiment_id": "EXP-076", "stage": "smoke", "status": "Passed"}
        previous = {**smoke, "stage": "source", "status": "Failed"}
        (first / "smoke.json").write_text(json.dumps(smoke))
        (first / "source.json").write_text(json.dumps(previous))
        bindings = copy.deepcopy(VERIFY.ATTEMPT2_BINDINGS)
        for value in bindings.values():
            value["sha256"] = hashlib.sha256((root / value["path"]).read_bytes()).hexdigest()
        for name in ("topicweb/adapters.py", "topicweb/worker.py", "scripts/validate_local.py", "scripts/verify_local.py", "tests/test_validation.py"):
            (root / name).write_text("new " + name)
        source = {"attempt": 2, "sources": {name: VERIFY.regular_file(root / name) for name in old_sources},
                  "protocol_sha256": VERIFY.regular_file(protocol), "fixture_sha256": smoke["fixture_sha256"], **bindings}
        return root, smoke, source, bindings

    def test_inherited_smoke_uses_archive_and_only_declared_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root, smoke, source, bindings = self.setup_artifacts(directory)
            with patch.object(VERIFY, "ATTEMPT2_BINDINGS", bindings):
                details, watched = VERIFY.implementation_identity(smoke, source, 2, root)
            self.assertEqual(details["inherits_smoke"], bindings["inherits_smoke"])
            self.assertIn("topicweb/adapters.py", details["changed_implementation_paths"])
            self.assertEqual(len(details["unchanged_deployment_sources"]), 3)
            self.assertTrue(all(VERIFY.regular_file(path) == digest for path, digest in watched))

    def test_old_failure_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root, smoke, source, bindings = self.setup_artifacts(directory)
            (root / bindings["previous_failed_source"]["path"]).write_text('{"status":"Passed"}')
            with patch.object(VERIFY, "ATTEMPT2_BINDINGS", bindings):
                with self.assertRaisesRegex(VERIFY.VerificationError, "inherited_source_identity_drift"):
                    VERIFY.implementation_identity(smoke, source, 2, root)

    def test_model_input_or_unrelated_implementation_changes_are_rejected(self):
        for name in ("topicweb/inference_process.py", "topicweb/core.py", "topicweb/app.py", "tests/fixtures/operational.jsonl"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root, smoke, source, bindings = self.setup_artifacts(directory)
                (root / name).write_text("unexpected change")
                if name in source["sources"]:
                    source["sources"][name] = digest("unexpected change")
                with patch.object(VERIFY, "ATTEMPT2_BINDINGS", bindings):
                    with self.assertRaises(VERIFY.VerificationError):
                        VERIFY.implementation_identity(smoke, source, 2, root)

    def test_inherited_manifest_must_match_archive_not_only_current_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root, smoke, source, bindings = self.setup_artifacts(directory)
            smoke["sources"]["start.py"] = "0" * 64
            previous_path = root / bindings["previous_failed_source"]["path"]
            previous = json.loads(previous_path.read_text())
            previous["sources"] = smoke["sources"]
            previous_path.write_text(json.dumps(previous))
            bindings["previous_failed_source"]["sha256"] = VERIFY.regular_file(previous_path)
            with patch.object(VERIFY, "ATTEMPT2_BINDINGS", bindings):
                with self.assertRaisesRegex(VERIFY.VerificationError, "inherited_archive_identity"):
                    VERIFY.implementation_identity(smoke, source, 2, root)

    def test_attempt_one_still_requires_identical_current_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root, smoke, source, _ = self.setup_artifacts(directory)
            with self.assertRaisesRegex(VERIFY.VerificationError, "implementation_manifest_alignment"):
                VERIFY.implementation_identity(smoke, source, 1, root)

    def test_attempt_choice_rejects_unregistered_attempt(self):
        with self.assertRaises(SystemExit):
            VERIFY.main(["--attempt", "4"])


def field_probe(protocol_hash="b" * 64, script_hash="c" * 64):
    rows = [{"comment_id": identifier, "post_id": 1001, "creation_date": 1787529600,
             "old_has_markdown": True, "new_has_markdown": True, "new_has_body": True,
             "old_markdown_sha256": "d" * 64, "new_markdown_sha256": "d" * 64,
             "markdown_sha256": "d" * 64, "markdown_bytes": 12,
             "new_body_sha256": "e" * 64, "new_body_bytes": 12} for identifier in (11, 12, 13)]
    return {"experiment_id": "EXP-076", "stage": "comment_fields", "status": "Passed", "attempt": 3,
            "protocol_sha256": protocol_hash, "script_sha256": script_hash,
            "old_filter_id": VERIFY.OLD_FILTER_ID, "new_filter_id": "synthetic_dual_field_filter",
            "old_included_fields": ["comment.body_markdown", "comment.comment_id"],
            "new_included_fields": ["comment.body_markdown", "comment.comment_id", "comment.body"],
            "old_comment_ids": [11, 12, 13], "new_comment_ids": [11, 12, 13], "discovered_comment_ids": [11, 12, 13], "rows": rows,
            "dependency_reproduced": False, "old_missing_markdown_count": 0, "matched_identity": True,
            "model_accessed": False, "gold_accessed": False, "raw_content_persisted": False, "elapsed_seconds": 1.0,
            "requests": [{"stage": str(index)} for index in range(5)]}


class CommentFieldProbeTests(unittest.TestCase):
    def test_passed_probe_preserves_same_three_markdown_inputs(self):
        probe = field_probe()
        self.assertEqual(VERIFY.check_field_probe(probe, "b" * 64, "c" * 64), "synthetic_dual_field_filter")
        self.assertFalse(probe["dependency_reproduced"])

    def test_old_markdown_absent_new_present_passes_and_records_dependency(self):
        probe = field_probe()
        for row in probe["rows"]:
            row.update(old_has_markdown=False, old_markdown_sha256=None)
        probe["dependency_reproduced"] = True
        probe["old_missing_markdown_count"] = 3
        self.assertEqual(VERIFY.check_field_probe(probe, "b" * 64, "c" * 64), "synthetic_dual_field_filter")

    def test_absent_old_markdown_cannot_have_invented_digest(self):
        probe = field_probe()
        probe["rows"][0]["old_has_markdown"] = False
        probe["dependency_reproduced"] = True
        probe["old_missing_markdown_count"] = 1
        with self.assertRaisesRegex(VERIFY.VerificationError, "field_probe_absent_old_digest"):
            VERIFY.check_field_probe(probe, "b" * 64, "c" * 64)

    def test_dependency_claim_must_match_observed_missingness(self):
        probe = field_probe()
        probe["dependency_reproduced"] = True
        with self.assertRaisesRegex(VERIFY.VerificationError, "field_probe_dependency_observation"):
            VERIFY.check_field_probe(probe, "b" * 64, "c" * 64)

    def test_field_delta_ids_and_model_input_changes_fail(self):
        for change in ("extra_field", "missing_old_field", "changed_ids", "changed_markdown", "empty_body", "missing_body", "failed"):
            with self.subTest(change=change):
                probe = field_probe()
                if change == "extra_field":
                    probe["new_included_fields"].append("comment.unregistered_field")
                elif change == "missing_old_field":
                    probe["new_included_fields"].remove("comment.comment_id")
                elif change == "changed_ids":
                    probe["new_comment_ids"][0] = 99
                elif change == "changed_markdown":
                    probe["rows"][0]["new_markdown_sha256"] = "f" * 64
                elif change == "empty_body":
                    probe["rows"][0]["new_body_bytes"] = 0
                elif change == "missing_body":
                    probe["rows"][0]["new_has_body"] = False
                else:
                    probe["status"] = "Failed"
                with self.assertRaises(VERIFY.VerificationError):
                    VERIFY.check_field_probe(probe, "b" * 64, "c" * 64)

    def test_probe_implementation_or_protocol_drift_fails(self):
        for protocol, script in (("f" * 64, "c" * 64), ("b" * 64, "f" * 64)):
            with self.assertRaisesRegex(VERIFY.VerificationError, "field_probe_implementation_identity"):
                VERIFY.check_field_probe(field_probe(), protocol, script)

    def test_source_filter_is_parameterized_only_when_explicit(self):
        bundle = fixture_bundle()
        job = bundle[2]["synthetic-job-4"]
        records = [row["record"] for row in job["items"]]
        job["manifest"]["filter_id"] = "synthetic_dual_field_filter"
        records[0]["provenance"]["filter_id"] = "synthetic_dual_field_filter"
        VERIFY.check_source(records, job["manifest"], "synthetic_dual_field_filter")
        with self.assertRaisesRegex(VERIFY.VerificationError, "source_manifest"):
            VERIFY.check_source(records, job["manifest"])

    def test_attempt_three_binds_second_failure_and_probe_without_new_smoke(self):
        with tempfile.TemporaryDirectory() as directory:
            root, smoke, source2, inherited = InheritedIdentityTests().setup_artifacts(directory)
            third = root / "private/validation/exp-076/attempt-3"
            third.mkdir()
            source2.update(experiment_id="EXP-076", stage="source", status="Failed")
            second_path = root / "private/validation/exp-076/attempt-2/source.json"
            second_path.write_text(json.dumps(source2))
            protocol = root.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-076-phase-c-local-system.md"
            (third / "previous-protocol.md").write_bytes(protocol.read_bytes())
            with tarfile.open(third / "previous-code.tar.gz", "w:gz") as archive:
                for name in [*source2["sources"], "tests/fixtures/operational.jsonl"]:
                    archive.add(root / name, arcname=name, recursive=False)
            protocol.write_text(protocol.read_text() + "\nattempt three comment field gate\n")
            probe_script = root / "scripts/probe_comment_fields.py"
            probe_script.write_text("synthetic field probe")
            probe = field_probe(VERIFY.regular_file(protocol), VERIFY.regular_file(probe_script))
            probe_path = third / "field-probe.json"
            probe_path.write_text(json.dumps(probe))
            previous = copy.deepcopy(VERIFY.ATTEMPT3_BINDINGS)
            for binding in previous.values():
                binding["sha256"] = VERIFY.regular_file(root / binding["path"])
            source3 = {**source2, "attempt": 3, "status": "Passed", "protocol_sha256": VERIFY.regular_file(protocol),
                       "sources": {**source2["sources"], "scripts/probe_comment_fields.py": VERIFY.regular_file(probe_script)},
                       "comment_field_probe": {"path": str(probe_path.relative_to(root)), "sha256": VERIFY.regular_file(probe_path)}, **previous}
            with patch.object(VERIFY, "ATTEMPT2_BINDINGS", inherited), patch.object(VERIFY, "ATTEMPT3_BINDINGS", previous):
                details, watched = VERIFY.implementation_identity(smoke, source3, 3, root)
                self.assertEqual(details["expected_filter_id"], probe["new_filter_id"])
                self.assertEqual(details["inherits_smoke"], inherited["inherits_smoke"])
                self.assertTrue(all(VERIFY.regular_file(path) == digest for path, digest in watched))
                probe["rows"][0]["new_markdown_sha256"] = "f" * 64
                probe_path.write_text(json.dumps(probe))
                with self.assertRaisesRegex(VERIFY.VerificationError, "field_probe_identity_drift"):
                    VERIFY.implementation_identity(smoke, source3, 3, root)


if __name__ == "__main__":
    unittest.main()
