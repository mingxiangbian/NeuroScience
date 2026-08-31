"""Independent EXP-076 consumer of sealed local jobs; never imports a producer.

This verifies storage, descriptive accounting and same-snapshot replay only.
It does not run a model, fetch a source, read historical datasets, or score gold.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import tarfile
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
COSTS = ("m1_attempts", "m3_attempts", "m3_succeeded", "m1_cache_hit", "m3_cache_hit", "audit_extra_calls")
OLD_FILTER_ID = "nFzTOPGAOEckIq4Pwr_RZ8"
ATTEMPT2_BINDINGS = {
    "inherits_smoke": {"path": "private/validation/exp-076/attempt-1/smoke.json", "sha256": "c6fd6f79aafb2743912b0be10e8e67592ccd17335a8e35edcfaa21576c67d4c8"},
    "previous_failed_source": {"path": "private/validation/exp-076/attempt-1/source.json", "sha256": "cabe894ee37509f59cc2ac6aab4227250731a9b7a7d03b5aef5170cf420e848b"},
    "inherited_code_archive": {"path": "private/validation/exp-076/attempt-2/inherited-code.tar.gz", "sha256": "8e5e1fe64249ed0a42a37245b40c950f26bd5aa52cb277a96dd08746c44a79f4"},
    "inherited_protocol": {"path": "private/validation/exp-076/attempt-2/inherited-protocol.md", "sha256": "5aefa0e0380b85615995669360334b2e842ba501d086a4e0f579e82e735c6d40"},
}
ATTEMPT3_BINDINGS = {
    "previous_failed_source_2": {"path": "private/validation/exp-076/attempt-2/source.json", "sha256": "205778bf617dac7712010de0367ea544829c4a438bc518bd6f1d94b8a6083a37"},
    "previous_source_code_archive": {"path": "private/validation/exp-076/attempt-3/previous-code.tar.gz", "sha256": "84fcd91d32649f076bd9508162caecea19bd8fda8aabecf822fc27a1fdc1b8ad"},
    "previous_source_protocol": {"path": "private/validation/exp-076/attempt-3/previous-protocol.md", "sha256": "da07395cf4311e1462effb3db92d1983d17e7a5f3a5af03a3bd681e05a3a349e"},
}
BOUNDARY = (
    "Finite-workload local implementation verification: source-to-record identity, "
    "descriptive prediction accounting and same-snapshot fresh-process replay. "
    "Not independent backend parity, gold-label accuracy, external generalization, "
    "whole-forum emotion prevalence, SLA, long-run stability or deployment-efficiency evidence. "
    "M1/M3 paired coverage is observed, never required or extrapolated to the full corpus."
)


class VerificationError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise VerificationError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def strict_json(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            require(key not in out, "duplicate_json_key")
            out[key] = value
        return out
    def nonfinite(_):
        raise VerificationError("nonfinite_json")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def close(actual, expected, code="aggregate_mismatch", atol=1e-10):
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(expected) <= set(actual), code)
        for key, value in expected.items():
            close(actual[key], value, code, atol)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), code)
        for first, second in zip(actual, expected):
            close(first, second, code, atol)
    elif isinstance(expected, float):
        require(type(actual) in (int, float) and math.isfinite(actual) and abs(actual - expected) <= atol, code)
    else:
        require(type(actual) is type(expected) and actual == expected, code)


def probabilities(value, optional=False):
    if value is None and optional:
        return None
    require(isinstance(value, list) and len(value) == 6, "probability_shape")
    require(all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in value), "probability_range")
    return value


def decisions(value, optional=False):
    if value is None and optional:
        return None
    require(isinstance(value, list) and len(value) == 6 and all(type(p) is int and p in (0, 1) for p in value), "decision_shape")
    return value


def check_records(records):
    require(0 < len(records) <= 500, "record_count")
    identities = set()
    for record in records:
        text = record.get("model_input_text")
        require(isinstance(text, str) and 0 < len(text.encode("utf-8")) <= 65536, "input_text_contract")
        require(record.get("model_input_hash") == sha(text), "input_hash_mismatch")
        normalized = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
        require(record.get("dedup_hash") == sha(normalized), "group_hash_mismatch")
        identity = [record.get(name) for name in ("source", "site", "object_type", "source_object_id")]
        require(all(isinstance(part, str) and part for part in identity), "record_identity_fields")
        digest = sha(json.dumps(identity, ensure_ascii=False, separators=(",", ":")))
        require(record.get("record_id") == digest and digest not in identities, "record_identity_mismatch")
        identities.add(digest)
    return sha(canonical(records))


def recalculate(records, results, mode):
    """Independent occurrence-level reconstruction, including missing predictions."""
    require(len(records) == len(results), "row_alignment")
    available = [(record, result) for record, result in zip(records, results) if result is not None]
    label_counts = [0] * 6
    neutral = paired = disagree = routed = 0
    paths, fallback_counts, cost = Counter(), Counter(), Counter({key: 0 for key in COSTS})
    seen_m1, seen_m3 = set(), set()
    dates = {}
    entropy, latency = [], []
    for record, result in available:
        require(isinstance(result, dict), "result_not_object")
        pred = decisions(result.get("prediction"))
        m1p, m3p = probabilities(result.get("m1_probabilities")), probabilities(result.get("m3_probabilities"), True)
        m1d, m3d = decisions(result.get("m1_prediction")), decisions(result.get("m3_prediction"), True)
        require((m3p is None) == (m3d is None), "paired_component_alignment")
        require(type(result.get("route_requested")) is bool, "route_flag")
        requested = result["route_requested"]
        path = result.get("used_path")
        require(path in {"m1", "m3"}, "used_path")
        require(pred == (m3d if path == "m3" else m1d), "selected_prediction_mismatch")
        require(result.get("active_labels") == [name for name, bit in zip(LABELS, pred) if bit], "active_labels_mismatch")
        require(result.get("neutral") is (not any(pred)), "neutral_mismatch")
        fallback = result.get("fallback_reason")
        require(result.get("fallback") is bool(fallback), "fallback_flag")
        counters = result.get("counters")
        require(isinstance(counters, dict) and all(type(counters.get(key)) is int and counters[key] in (0, 1) for key in COSTS), "component_cost_shape")
        require(counters.get("fallback_reason") == fallback, "fallback_counter_alignment")
        exact = record["model_input_hash"]
        expected = {key: 0 for key in COSTS}
        expected["m1_cache_hit"] = int(exact in seen_m1)
        expected["m1_attempts"] = int(exact not in seen_m1)
        seen_m1.add(exact)
        if mode == "m1_only":
            require(not requested and path == "m1" and m3p is None and not fallback, "m1_only_contract")
        elif mode == "demo":
            # This experiment freezes Demo's budget at zero, not all Demo deployments.
            require(path == "m1" and m3p is None and fallback == ("m3_budget_exhausted" if requested else None), "demo_zero_budget_contract")
        elif mode == "research":
            require(not fallback and path == ("m3" if requested else "m1") and (m3p is not None) == requested, "research_contract")
            if requested:
                expected["m3_cache_hit"] = int(exact in seen_m3)
                expected["m3_attempts"] = expected["m3_succeeded"] = int(exact not in seen_m3)
                seen_m3.add(exact)
        else:
            raise VerificationError("mode_contract")
        for key in COSTS:
            require(counters[key] == expected[key], "component_cost_mismatch")
            cost[key] += counters[key]
        close(result.get("cumulative_counters"), dict(cost), "cumulative_cost_mismatch")
        for index, bit in enumerate(pred):
            label_counts[index] += bit
        neutral += not any(pred)
        routed += requested
        paths[path] += 1
        if fallback:
            fallback_counts[fallback] += 1
        if m3d is not None:
            paired += 1
            disagree += m1d != m3d
        entropy.append(sum(-p * math.log(p) if p else 0 for p in m1p) / 6 +
                       sum(-(1-p) * math.log(1-p) if p < 1 else 0 for p in m1p) / 6)
        value = result.get("latency_ms")
        require(type(value) in (int, float) and math.isfinite(value) and value >= 0, "latency_contract")
        latency.append(value)
        if record.get("created_at"):
            day = record["created_at"][:10]
            bucket = dates.setdefault(day, {"n": 0, "neutral": 0, "counts": [0] * 6})
            bucket["n"] += 1
            bucket["neutral"] += not any(pred)
            bucket["counts"] = [a + b for a, b in zip(bucket["counts"], pred)]
    size, positive = len(available), sum(label_counts)
    eligible_types = Counter(record["object_type"] for record in records)
    successful_types = Counter(record["object_type"] for record, _ in available)
    return {
        "mode": mode, "labels": list(LABELS),
        "summary": {"eligible_items": len(records), "successful_items": size,
                    "missing_predictions": len(records)-size, "coverage": size / len(records) if records else None,
                    "neutral_count": neutral, "neutral_rate": neutral / size if size else None,
                    "exact_input_groups": len({row["model_input_hash"] for row in records}),
                    "normalized_text_groups": len({row["dedup_hash"] for row in records}),
                    "undated_items": sum(not row.get("created_at") for row in records)},
        "emotions": [{"label": label, "count": count, "prevalence": count / size if size else None,
                      "positive_share": count / positive if positive else None} for label, count in zip(LABELS, label_counts)],
        "daily": [{"date": day, "n": bucket["n"], "neutral": bucket["neutral"],
                   "prevalence": {label: count / bucket["n"] for label, count in zip(LABELS, bucket["counts"])}}
                  for day, bucket in sorted(dates.items())],
        "object_types": [{"type": kind, "eligible": count, "successful": successful_types[kind]} for kind, count in sorted(eligible_types.items())],
        "routing": {"route_requested": routed, "paths": dict(paths), "cost": dict(cost), "fallbacks": dict(fallback_counts),
                    "paired_n": paired, "paired_disagreement": disagree / paired if paired else None},
        "uncertainty": {"m1_mean_binary_entropy_nats": sum(entropy) / len(entropy) if entropy else None, "n": len(entropy)},
        "timing": {"mean_item_ms": sum(latency) / len(latency) if latency else None, "n": len(latency)},
    }


def check_fixture(records, fixture_rows, fixture_hash):
    require(len(records) == len(fixture_rows) == 8, "fixture_count")
    require(records[0]["model_input_text"] == records[5]["model_input_text"], "fixture_duplicate")
    require(records[0]["model_input_hash"] != records[6]["model_input_hash"] and records[0]["dedup_hash"] == records[6]["dedup_hash"], "fixture_case_whitespace")
    require(records[7]["model_input_text"].startswith("<script>") and records[7].get("created_at") is None, "fixture_html_undated")
    for ordinal, (record, fixture) in enumerate(zip(records, fixture_rows), 1):
        require(record["model_input_text"] == fixture["text"] and record["source_payload_raw"] == fixture, "fixture_text_alignment")
        require(record["source"] == record["site"] == "upload" and record["object_type"] == "row", "fixture_source")
        require(record["source_object_id"] == f"{fixture_hash}:{ordinal}", "fixture_source_id")
        require(record.get("created_at") == fixture.get("created_at"), "fixture_time_alignment")
        provenance = record["provenance"]
        require(provenance.get("file_sha256") == fixture_hash and provenance.get("row_number") == ordinal
                and provenance.get("line_number") == ordinal and provenance.get("supplied_id") == fixture["id"]
                and provenance.get("text_field") == "text", "fixture_provenance")


def check_source(records, manifest, expected_filter_id=OLD_FILTER_ID):
    close(manifest, {"source": "stackexchange", "site": "stackoverflow", "cohort": "questions_created_in_window",
                    "query": "", "tags": "python", "from_utc": "2026-08-23T00:00:00Z", "to_utc": "2026-08-30T00:00:00Z",
                    "window_bounds": "start_inclusive_end_exclusive", "sort": "creation", "order": "asc",
                    "max_questions": 100, "max_items": 500, "filter_id": expected_filter_id,
                    "text_field": "body_markdown", "normalization_for_model_input": "none", "record_count": len(records)}, "source_manifest")
    require(set(manifest.get("included_types", [])) == {"question", "answer", "comment"}, "source_types")
    require(isinstance(manifest.get("sampling_complete"), bool) and isinstance(manifest.get("stop_reason"), str), "source_sampling_boundary")
    require(0 < len(manifest.get("requests", [])) <= 30, "source_request_budget")
    question_ids = {int(row["source_object_id"]) for row in records if row["object_type"] == "question"}
    require(0 < len(question_ids) <= 100 and manifest.get("selected_question_count") == len(question_ids), "source_question_cohort")
    parent_questions = {identifier: identifier for identifier in question_ids}
    for row in records:
        if row["object_type"] == "answer":
            parent_questions[int(row["source_object_id"])] = int(row["source_payload_raw"]["question_id"])
    counts = Counter({kind: 0 for kind in ("question", "answer", "comment")})
    for row in records:
        kind, raw, provenance = row["object_type"], row["source_payload_raw"], row["provenance"]
        require(row["source"] == "stackexchange" and row["site"] == "stackoverflow" and kind in counts, "source_record_type")
        identifier = int(row["source_object_id"])
        require(raw.get(kind + "_id") == identifier and raw.get("body_markdown") == row["model_input_text"], "source_payload_alignment")
        stamp = datetime.fromtimestamp(raw["creation_date"], timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        require(stamp == row.get("created_at") and "2026-08-23T00:00:00Z" <= stamp < "2026-08-30T00:00:00Z", "source_window_alignment")
        parent = raw["post_id"] if kind == "comment" else identifier
        require(parent in parent_questions and parent_questions[parent] in question_ids, "source_parent_cohort")
        require(provenance.get("question_id") == parent_questions[parent] and row.get("thread_id") == str(parent_questions[parent]), "source_thread_alignment")
        require(provenance.get("filter_id") == expected_filter_id and provenance.get("text_field") == "body_markdown", "source_text_contract")
        expected_url = (f"https://stackoverflow.com/posts/{parent}#comment{identifier}_{parent}" if kind == "comment"
                        else f"https://stackoverflow.com/{'q' if kind == 'question' else 'a'}/{identifier}")
        require(row.get("source_url") == expected_url, "source_url_alignment")
        counts[kind] += 1
    close(manifest.get("counts_by_type"), dict(counts), "source_type_counts")
    return {"records": len(records), "source_link_coverage": 1.0, "selected_questions": len(question_ids),
            "sampling_complete": manifest["sampling_complete"], "stop_reason": manifest["stop_reason"]}


def verify(smoke, source, jobs, fixture_rows, fixture_hash, expected_filter_id=OLD_FILTER_ID):
    for stage, record, count in (("smoke", smoke, 4), ("source", source, 1)):
        require(record.get("experiment_id") == "EXP-076" and record.get("status") == "Passed" and record.get("stage") == stage, "producer_stage_not_passed")
        require(len(record.get("jobs", [])) == count and record.get("fixture_sha256") == fixture_hash, "producer_stage_contract")
        for flag in ("validation_accessed", "test_accessed", "training", "external_gold_accessed"):
            require(record.get(flag) is False, "access_boundary")
    entries = smoke["jobs"] + source["jobs"]
    require(smoke.get("input_sha256") == fixture_hash
            and source.get("input_sha256") == source["jobs"][0]["snapshot_hash"], "stage_input_hash")
    require(len({entry["id"] for entry in entries}) == 5 and set(jobs) == {entry["id"] for entry in entries}, "job_identity_alignment")
    require([entry["mode"] for entry in entries] == ["m1_only", "research", "demo", "research", "m1_only"], "job_mode_order")
    outputs, fingerprints = [], set()
    for index, entry in enumerate(entries):
        job = jobs[entry["id"]]
        require(job["state"] in {"completed", "completed_with_fallback"} and not job["error_code"], "job_not_completed")
        require(job["mode"] == entry["mode"] and job["state"] == entry["state"] and not job["raw_expired"] and not job["items_expired"], "job_terminal_alignment")
        rows = job["items"]
        require([row["ordinal"] for row in rows] == list(range(len(rows))), "ordinal_alignment")
        records, results = [row["record"] for row in rows], [row["result"] for row in rows]
        require(len(rows) == job["total_items"] == job["completed_items"] == entry["total_items"] == entry["completed_items"], "job_coverage_alignment")
        require(all(isinstance(result, dict) for result in results), "missing_completed_prediction")
        observed = check_records(records)
        require(observed == job["snapshot_hash"] == entry["snapshot_hash"], "snapshot_hash_mismatch")
        close(entry["manifest"], job["manifest"], "manifest_copy_mismatch")
        if index < 4:
            check_fixture(records, fixture_rows, fixture_hash)
        else:
            source_check = check_source(records, job["manifest"], expected_filter_id)
        expected = recalculate(records, results, job["mode"])
        close(job["dashboard"], expected)
        close(entry["dashboard"], expected)
        close(entry["dashboard"]["routing"], {"cost_scope": "completed_job", "cost_complete": True}, "cost_scope")
        require(job["state"] == ("completed_with_fallback" if expected["routing"]["fallbacks"] else "completed"), "fallback_terminal")
        for result in results:
            require(isinstance(result.get("fingerprint"), str) and len(result["fingerprint"]) == 64, "pipeline_fingerprint")
            fingerprints.add(result["fingerprint"])
        outputs.append({"job_id": entry["id"], "mode": job["mode"], "snapshot_hash": observed,
                        "summary": expected["summary"], "emotions": expected["emotions"], "routing": expected["routing"]})
    require(len(fingerprints) == 1, "pipeline_fingerprint_drift")
    first, repeated = jobs[entries[1]["id"]], jobs[entries[3]["id"]]
    require(repeated.get("replay_of") == first["id"] and first["snapshot_hash"] == repeated["snapshot_hash"], "replay_lineage")
    differences = {"m1_max_abs": 0.0, "m3_max_abs": 0.0}
    for left, right in zip(first["items"], repeated["items"]):
        require(left["record"] == right["record"], "replay_record_alignment")
        a, b = left["result"], right["result"]
        for key in ("prediction", "m1_prediction", "m3_prediction", "active_labels", "neutral", "route_requested", "used_path", "fallback_reason"):
            require(a[key] == b[key], "replay_discrete_mismatch")
        for key, metric in (("m1_probabilities", "m1_max_abs"), ("m3_probabilities", "m3_max_abs")):
            require((a[key] is None) == (b[key] is None), "replay_probability_presence")
            if a[key] is not None:
                delta = max(abs(x-y) for x, y in zip(a[key], b[key]))
                require(delta <= 1e-6, "replay_probability_mismatch")
                differences[metric] = max(differences[metric], delta)
    paired = outputs[1]["routing"]["paired_n"]
    if not paired:
        differences["m3_max_abs"] = None
    return {"checks": ["producer_terminals", "five_job_identity_and_modes", "complete_ordinal_alignment",
                        "exact_input_and_record_hashes", "normalized_group_hashes", "sealed_snapshot_hashes",
                        "authored_eight_row_alignment", "source_markdown_parent_time_and_link_alignment",
                        "independent_counts_prevalence_neutral_coverage", "independent_daily_types_entropy_latency",
                        "component_cost_and_exact_cache_accounting", "mode_and_final_path_contracts",
                        "zero_budget_demo", "research_snapshot_replay_decisions", "research_replay_probabilities_1e-6",
                        "pipeline_fingerprint_consistency", "bounded_claims_and_no_gold"],
            "jobs": outputs, "replay": {**differences, "m1_rows": 8, "m3_rows": paired,
                                         "m3_coverage": paired / 8, "m3_coverage_status": "observed_routed_subset" if paired else "insufficient_no_routed_pairs"},
            "source": source_check, "pipeline_fingerprint": next(iter(fingerprints)), "claim_boundary": BOUNDARY}


def regular_file(path):
    require(not any(parent.is_symlink() for parent in (path, *path.parents)), "source_symlink")
    require(path.is_file() and stat.S_ISREG(path.stat().st_mode), "source_not_regular")
    return sha(path.read_bytes())


def read_jobs(database, identifiers):
    regular_file(database)
    db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        jobs = {}
        for identifier in identifiers:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone()
            require(row is not None, "job_missing")
            job = dict(row)
            for key in ("request", "progress", "manifest", "dashboard"):
                job[key] = strict_json(job[key]) if job[key] is not None else None
            job["items"] = [{"ordinal": row["ordinal"], "record": strict_json(row["record"]),
                             "result": strict_json(row["result"]) if row["result"] is not None else None}
                            for row in db.execute("SELECT ordinal,record,result FROM items WHERE job_id=? ORDER BY ordinal", (identifier,))]
            jobs[identifier] = job
        db.execute("ROLLBACK")
        return jobs
    finally:
        db.close()


def archive_hashes(path):
    archived = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            require(not Path(member.name).is_absolute() and ".." not in Path(member.name).parts, "archive_path")
            if member.isdir():
                continue
            require(member.isfile() and member.name not in archived and member.size <= 2 * 1024 * 1024, "archive_member")
            archived[member.name] = sha(archive.extractfile(member).read())
    return archived


def check_field_probe(probe, protocol_hash, script_hash):
    require(probe.get("experiment_id") == "EXP-076" and probe.get("stage") == "comment_fields"
            and probe.get("status") == "Passed" and probe.get("attempt") == 3, "field_probe_not_passed")
    require(probe.get("matched_identity") is True
            and all(probe.get(key) is False for key in ("model_accessed", "gold_accessed", "raw_content_persisted")), "field_probe_access_and_identity")
    require(isinstance(script_hash, str) and re.fullmatch(r"[0-9a-f]{64}", script_hash) is not None
            and probe.get("protocol_sha256") == protocol_hash and probe.get("script_sha256") == script_hash, "field_probe_implementation_identity")
    require(probe.get("old_filter_id") == OLD_FILTER_ID and isinstance(probe.get("new_filter_id"), str)
            and 0 < len(probe["new_filter_id"]) <= 128 and probe["new_filter_id"] != OLD_FILTER_ID, "field_probe_filter_identity")
    old_fields, new_fields = probe.get("old_included_fields"), probe.get("new_included_fields")
    require(isinstance(old_fields, list) and isinstance(new_fields, list)
            and all(isinstance(name, str) for name in old_fields + new_fields), "field_probe_field_schema")
    require(len(old_fields) == len(set(old_fields)) and len(new_fields) == len(set(new_fields))
            and "comment.body" not in old_fields and "comment.body_markdown" in old_fields
            and set(new_fields) == set(old_fields) | {"comment.body"}, "field_probe_field_delta")
    rows = probe.get("rows")
    require(isinstance(rows, list) and len(rows) == 3, "field_probe_row_count")
    identifiers = [row.get("comment_id") for row in rows]
    require(all(type(identifier) is int and identifier > 0 for identifier in identifiers)
            and len(set(identifiers)) == 3, "field_probe_comment_identity")
    for key in ("old_comment_ids", "new_comment_ids", "discovered_comment_ids"):
        require(isinstance(probe.get(key), list) and all(type(identifier) is int for identifier in probe[key])
                and sorted(probe[key]) == sorted(identifiers), "field_probe_comment_alignment")
    for row in rows:
        require(type(row.get("post_id")) is int and row["post_id"] > 0
                and type(row.get("creation_date")) is int and row["creation_date"] > 0, "field_probe_source_identity")
        require(type(row.get("old_has_markdown")) is bool and all(row.get(key) is True for key in ("new_has_markdown", "new_has_body")), "field_probe_missing_field")
        for key in ("new_markdown_sha256", "new_body_sha256"):
            require(isinstance(row.get(key), str) and re.fullmatch(r"[0-9a-f]{64}", row[key]) is not None, "field_probe_text_digest")
        require(row["new_markdown_sha256"] == row.get("markdown_sha256"), "field_probe_model_input_changed")
        if row["old_has_markdown"]:
            require(row.get("old_markdown_sha256") == row["new_markdown_sha256"], "field_probe_model_input_changed")
        else:
            require(row.get("old_markdown_sha256") is None, "field_probe_absent_old_digest")
        require(type(row.get("markdown_bytes")) is int and row["markdown_bytes"] > 0
                and type(row.get("new_body_bytes")) is int and row["new_body_bytes"] > 0, "field_probe_empty_field")
    require(isinstance(probe.get("requests"), list) and 0 < len(probe["requests"]) <= 5
            and type(probe.get("elapsed_seconds")) in (int, float) and math.isfinite(probe["elapsed_seconds"])
            and 0 <= probe["elapsed_seconds"] <= 120, "field_probe_request_budget")
    missing = sum(not row["old_has_markdown"] for row in rows)
    require(type(probe.get("old_missing_markdown_count")) is int and probe["old_missing_markdown_count"] == missing
            and probe.get("dependency_reproduced") is (missing > 0), "field_probe_dependency_observation")
    return probe["new_filter_id"]


def implementation_identity(smoke, source, attempt, root):
    """Bind old evidence to its sealed source archive, without extracting files."""
    implementation = source.get("sources")
    require(isinstance(implementation, dict) and implementation, "implementation_manifest_alignment")
    paths = []
    for name, expected in implementation.items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "implementation_path")
        path = root / name
        require(regular_file(path) == expected, "implementation_identity_drift")
        paths.append((path, expected))
    protocol = root.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-076-phase-c-local-system.md"
    protocol_hash = regular_file(protocol)
    require(source.get("protocol_sha256") == protocol_hash, "protocol_identity_drift")
    paths.append((protocol, protocol_hash))
    details = {"implementation_manifest_sha256": sha(canonical(implementation)), "protocol_sha256": protocol_hash}
    if attempt == 1:
        require(smoke.get("sources") == implementation, "implementation_manifest_alignment")
        require(smoke.get("protocol_sha256") == protocol_hash, "protocol_identity_drift")
        return details, paths
    require(source.get("attempt") == attempt, "source_attempt_mismatch")
    for key, binding in ATTEMPT2_BINDINGS.items():
        require(source.get(key) == binding, "inheritance_binding_mismatch")
        path = root / binding["path"]
        require(regular_file(path) == binding["sha256"], "inherited_source_identity_drift")
        paths.append((path, binding["sha256"]))
    previous = strict_json((root / ATTEMPT2_BINDINGS["previous_failed_source"]["path"]).read_text())
    require(previous.get("status") == "Failed" and previous.get("stage") == "source"
            and previous.get("experiment_id") == "EXP-076", "previous_failure_lineage")
    inherited_protocol = root / ATTEMPT2_BINDINGS["inherited_protocol"]["path"]
    old_protocol_hash = ATTEMPT2_BINDINGS["inherited_protocol"]["sha256"]
    require(smoke.get("protocol_sha256") == previous.get("protocol_sha256") == old_protocol_hash, "inherited_protocol_identity")
    require(protocol.read_bytes().startswith(inherited_protocol.read_bytes()), "protocol_not_append_only")
    archived = archive_hashes(root / ATTEMPT2_BINDINGS["inherited_code_archive"]["path"])
    inherited = smoke.get("sources")
    require(isinstance(inherited, dict) and inherited and inherited == previous.get("sources"), "inherited_implementation_alignment")
    require(all(archived.get(name) == expected for name, expected in inherited.items()), "inherited_archive_identity")
    changed = sorted(name for name in set(inherited) | set(implementation) if inherited.get(name) != implementation.get(name))
    allowed = {"topicweb/adapters.py", "topicweb/worker.py", "scripts/validate_local.py", "scripts/verify_local.py"}
    if attempt == 3:
        allowed.add("scripts/probe_comment_fields.py")
    require(all(name in allowed or (name.startswith("tests/") and name.endswith(".py")) for name in changed), "undeclared_implementation_change")
    immutable = {}
    for name in ("topicweb/inference_process.py", "topicweb/core.py", "tests/fixtures/operational.jsonl"):
        path = root / name
        require(name in archived and regular_file(path) == archived[name], "inherited_deployment_identity_drift")
        immutable[name] = archived[name]
        paths.append((path, archived[name]))
    require(smoke.get("fixture_sha256") == source.get("fixture_sha256") == immutable["tests/fixtures/operational.jsonl"], "inherited_fixture_identity")
    details.update(inherits_smoke=ATTEMPT2_BINDINGS["inherits_smoke"], previous_failed_source=ATTEMPT2_BINDINGS["previous_failed_source"],
                   inherited_code_archive=ATTEMPT2_BINDINGS["inherited_code_archive"], inherited_protocol=ATTEMPT2_BINDINGS["inherited_protocol"],
                   unchanged_deployment_sources=immutable, changed_implementation_paths=changed)
    if attempt == 3:
        for key, binding in ATTEMPT3_BINDINGS.items():
            require(source.get(key) == binding, "previous_source_binding_mismatch")
            path = root / binding["path"]
            require(regular_file(path) == binding["sha256"], "previous_source_identity_drift")
            paths.append((path, binding["sha256"]))
        second = strict_json((root / ATTEMPT3_BINDINGS["previous_failed_source_2"]["path"]).read_text())
        require(second.get("experiment_id") == "EXP-076" and second.get("stage") == "source"
                and second.get("status") == "Failed" and second.get("attempt") == 2, "previous_second_failure_lineage")
        second_archive = archive_hashes(root / ATTEMPT3_BINDINGS["previous_source_code_archive"]["path"])
        require(isinstance(second.get("sources"), dict) and second["sources"]
                and all(second_archive.get(name) == expected for name, expected in second["sources"].items()), "previous_source_archive_identity")
        second_protocol = root / ATTEMPT3_BINDINGS["previous_source_protocol"]["path"]
        require(second.get("protocol_sha256") == ATTEMPT3_BINDINGS["previous_source_protocol"]["sha256"]
                and protocol.read_bytes().startswith(second_protocol.read_bytes()), "previous_source_protocol_identity")
        require(all(second_archive.get(name) == expected for name, expected in immutable.items()), "previous_deployment_identity_drift")
        changed_since_second = sorted(name for name in set(second["sources"]) | set(implementation)
                                      if second["sources"].get(name) != implementation.get(name))
        require(all(name in allowed or (name.startswith("tests/") and name.endswith(".py")) for name in changed_since_second), "undeclared_source_retry_change")
        binding = source.get("comment_field_probe")
        require(isinstance(binding, dict) and set(binding) == {"path", "sha256"}
                and binding.get("path") == "private/validation/exp-076/attempt-3/field-probe.json", "field_probe_binding")
        probe_path = root / binding["path"]
        require(regular_file(probe_path) == binding.get("sha256"), "field_probe_identity_drift")
        paths.append((probe_path, binding["sha256"]))
        probe = strict_json(probe_path.read_text())
        expected_filter = check_field_probe(probe, protocol_hash, implementation.get("scripts/probe_comment_fields.py"))
        details.update(ATTEMPT3_BINDINGS)
        details.update(comment_field_probe=binding, expected_filter_id=expected_filter,
                       comment_field_dependency_reproduced=probe["dependency_reproduced"], changed_since_previous_source=changed_since_second)
    return details, paths


def main(argv=None):
    parser = argparse.ArgumentParser(description="Independently verify sealed EXP-076 jobs")
    parser.add_argument("--attempt", type=int, choices=(1, 2, 3), default=1)
    attempt = parser.parse_args(argv).attempt
    run = ROOT / f"private/validation/exp-076/attempt-{attempt}"
    target = run / "verification.json"
    require(not target.exists() and not target.is_symlink(), "verification_already_exists")
    fixture = ROOT / "tests/fixtures/operational.jsonl"
    database = ROOT / "private/jobs.sqlite3"
    smoke_path = ROOT / "private/validation/exp-076/attempt-1/smoke.json"
    paths = [smoke_path, run / "source.json", fixture, database]
    wal = database.with_name(database.name + "-wal")
    if wal.exists():
        paths.append(wal)
    # Missing prerequisite files do not manufacture a failed or successful terminal.
    hashes = {str(path.relative_to(ROOT)): regular_file(path) for path in paths}
    result = {"experiment_id": "EXP-076", "tier": "Minor", "status": "Failed", "attempt": attempt,
              "verified_at": datetime.now(timezone.utc).isoformat(), "source_hashes": hashes,
              "verifier_sha256": regular_file(Path(__file__).resolve()), "claim_boundary": BOUNDARY,
              "models_loaded": False, "source_fetched": False, "historical_data_accessed": False,
              "gold_accessed": False, "producer_aggregation_called": False}
    try:
        smoke, source = (strict_json(path.read_text()) for path in paths[:2])
        identity_details, implementation_paths = implementation_identity(smoke, source, attempt, ROOT)
        result.update(identity_details)
        entries = smoke["jobs"] + source["jobs"]
        jobs = read_jobs(database, [entry["id"] for entry in entries])
        result["logical_job_selection_sha256"] = sha(canonical(jobs))
        fixture_rows = [strict_json(line) for line in fixture.read_text().splitlines() if line.strip()]
        result.update(verify(smoke, source, jobs, fixture_rows, hashes[str(fixture.relative_to(ROOT))],
                             identity_details.get("expected_filter_id", OLD_FILTER_ID)))
        require(all(regular_file(path) == hashes[str(path.relative_to(ROOT))] for path in paths), "source_changed_during_verification")
        require(all(regular_file(path) == expected for path, expected in implementation_paths), "implementation_changed_during_verification")
        result["checks"].append("producer_implementation_and_protocol_identities")
        if attempt in (2, 3):
            result["checks"].extend(["inherited_smoke_archive_and_failed_source_lineage", "unchanged_deployment_core_and_fixture"])
        if attempt == 3:
            result["checks"].extend(["previous_source_failure_archive_and_protocol", "hash_bound_comment_field_probe_and_filter_delta"])
        result.update(status="Passed", passed_count=len(result["checks"]), failed_count=0, exp076_verified=True)
    except Exception as error:
        result.update(error_code=str(error) if isinstance(error, VerificationError) else "verification_failed", exp076_verified=False)
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": result["status"], "exp076_verified": result["exp076_verified"]}))
    return 0 if result["status"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
