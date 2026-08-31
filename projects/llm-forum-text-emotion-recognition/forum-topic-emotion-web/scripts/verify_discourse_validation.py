"""Independent, selected-job-only EXP-078 source and Research accounting checks."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import statistics

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "private/validation/exp-078/attempt-1"
PROTOCOL = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-078-discourse-operational.md"
REVIEW = ROOT / "docs/discourse-source-review.md"
SPEC = importlib.util.spec_from_file_location("exp078_independent_local_checks", ROOT / "scripts/verify_local.py")
LOCAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LOCAL)
require, close, sha, canonical = LOCAL.require, LOCAL.close, LOCAL.sha, LOCAL.canonical
QUERY = {"site": "discuss.python.org", "category_id": 7, "max_topics": 100, "max_items": 400}
C3_TOOLS = {"scripts/run_discourse_validation.py", "scripts/verify_discourse_validation.py", "tests/test_discourse_validation.py"}
EXCLUSIONS = {"pinned_topics", "nonpublic_topics", "system_posts", "nonregular_posts", "deleted_or_hidden_posts",
              "duplicate_topics", "duplicate_posts", "unavailable_stream_ids", "unresolved_reply_parent"}
BOUNDARY = ("One 300–400-post unlabelled public-source Research job. Native raw identity and saved accounting are verified; "
            "excluded-source totals are checked for metadata consistency, not independently rescanned. No original response bodies "
            "or per-request timestamps are persisted, so HTTP response hashes and frozen rate-limit policy are not a second source crawl. "
            "Not external-gold accuracy, whole-forum emotion prevalence, an independent numerical backend parity test, or an SLA.")


def regular(path):
    require(path.is_file() and stat.S_ISREG(path.stat().st_mode)
            and not any(item.is_symlink() for item in (path, *path.parents)), "source_not_regular")


def file_hash(path):
    regular(path)
    return sha(path.read_bytes())


def current_source_hashes():
    bindings = {str(path.relative_to(ROOT)): file_hash(path)
                for directory in ("topicweb", "scripts", "tests", "static")
                for path in sorted((ROOT / directory).rglob("*"))
                if path.is_file() and path.suffix in {".py", ".js", ".css", ".html"}}
    bindings["requirements-lock.txt"] = file_hash(ROOT / "requirements-lock.txt")
    return bindings


def utc(value):
    require(isinstance(value, str), "source_timestamp_missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(parsed.tzinfo is not None, "source_timestamp_timezone")
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except ValueError as error:
        raise LOCAL.VerificationError("source_timestamp_invalid") from error


def read_selected_job(database, identifier):
    """Do not read raw records belonging to earlier SO jobs or any other job."""
    regular(database)
    db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        row = db.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone()
        require(row is not None, "job_missing")
        job = dict(row)
        for key in ("request", "manifest", "dashboard", "progress"):
            job[key] = LOCAL.strict_json(job[key]) if job.get(key) is not None else None
        job["items"] = [{"ordinal": row["ordinal"], "record": LOCAL.strict_json(row["record"]),
                         "result": LOCAL.strict_json(row["result"]) if row["result"] is not None else None}
                        for row in db.execute("SELECT ordinal,record,result FROM items WHERE job_id=? ORDER BY ordinal", (identifier,))]
        db.execute("ROLLBACK")
        return job
    finally:
        db.close()


def check_soak(run, verification, bindings):
    prefix = "private/validation/exp-077/attempt-1/"
    require(run.get("experiment_id") == "EXP-077" and run.get("status") == "Completed"
            and run.get("failure_code") is None and run.get("plan_sha256") == bindings["plan"]["sha256"], "soak_run_not_safe")
    require(verification.get("experiment_id") == "EXP-077" and verification.get("status") == "Passed"
            and verification.get("exp077_complete") is True and verification.get("gates", {}).get("base") is True
            and verification.get("operational_state") == "safe-to-continue", "soak_verification_not_safe")
    require(verification.get("source_hashes", {}).get(prefix + "run.json") == bindings["run"]["sha256"]
            and verification["source_hashes"].get(prefix + "plan.json") == bindings["plan"]["sha256"], "soak_binding")


def check_source_scope(soak_sources, current):
    require(isinstance(soak_sources, dict) and bool(soak_sources)
            and set(soak_sources) <= set(current) and set(current) - set(soak_sources) <= C3_TOOLS
            and all(current[name] == value for name, value in soak_sources.items()), "post_soak_source_change")


def recalculate_derived(records, results):
    """Independent rational-weight groups; bucket membership uses every occurrence."""
    require(len(records) == len(results), "derived_alignment")
    predictions = [LOCAL.decisions(result.get("prediction")) if isinstance(result, dict) else None for result in results]
    group_ids = [record.get("dedup_hash") for record in records]
    require(all(isinstance(value, str) and value for value in group_ids), "derived_group_identity")

    def weighted(indices, unique):
        members = defaultdict(list)
        for index in indices:
            members[group_ids[index] if unique else index].append(index)
        label_totals = [Fraction(0) for _ in LOCAL.LABELS]
        neutral = Fraction(0)
        successes = occurrences = partial = mixed = 0
        for group in members.values():
            observed = [predictions[index] for index in group if predictions[index] is not None]
            if not observed:
                continue
            successes += 1
            occurrences += len(observed)
            partial += len(observed) != len(group)
            mixed += len(set(map(tuple, observed))) > 1
            denominator = len(observed)
            neutral += Fraction(sum(not any(bits) for bits in observed), denominator)
            for label in range(6):
                label_totals[label] += Fraction(sum(bits[label] for bits in observed), denominator)
        positives = sum(label_totals)
        return {"unit": "normalized_text_group" if unique else "occurrence",
                "summary": {"eligible_units": len(members), "successful_units": successes,
                            "missing_units": len(members) - successes, "coverage": successes / len(members) if members else None,
                            "eligible_occurrences": len(indices), "successful_occurrences": occurrences,
                            "neutral_count": float(neutral), "neutral_rate": float(neutral / successes) if successes else None,
                            "cardinality": float(positives / successes) if successes else None,
                            "mixed_prediction_groups": mixed, "partially_predicted_groups": partial},
                "emotions": [{"label": label, "count": float(count),
                              "prevalence": float(count / successes) if successes else None,
                              "positive_share": float(count / positives) if positives else None}
                             for label, count in zip(LOCAL.LABELS, label_totals)]}

    def distribution(values):
        values = sorted(float(value) for value in values if type(value) in (int, float) and math.isfinite(value))
        return {"n": len(values), "mean": statistics.fmean(values) if values else None,
                "median": float(statistics.median(values)) if values else None,
                "p95": statistics.quantiles(values, n=100, method="inclusive")[94] if len(values) > 1 else values[0] if values else None,
                "min": values[0] if values else None, "max": values[-1] if values else None}

    daily, weekly, types = defaultdict(list), defaultdict(list), defaultdict(list)
    routed_groups = {name: [] for name in ("false", "true", "unknown")}
    for index, (record, result) in enumerate(zip(records, results)):
        types[str(record.get("object_type", "unknown"))].append(index)
        route = result.get("route_requested") if isinstance(result, dict) else None
        routed_groups["true" if route is True else "false" if route is False else "unknown"].append(index)
        if record.get("created_at"):
            date = datetime.fromisoformat(utc(record["created_at"]).replace("Z", "+00:00")).date()
            daily[date.isoformat()].append(index)
            weekly[(date - timedelta(days=date.weekday())).isoformat()].append(index)
    views = {}
    for name, unique in (("object_weighted", False), ("normalized_unique_text", True)):
        view = weighted(list(range(len(records))), unique)
        view["trends"] = {name: [{"date": date, **weighted(indices, unique)} for date, indices in sorted(buckets.items())]
                          for name, buckets in (("daily", daily), ("weekly", weekly))}
        view["strata"] = {name: [{"group": group, **weighted(indices, unique)} for group, indices in sorted(buckets.items())]
                          for name, buckets in (("object_type", types), ("route_requested", routed_groups))}
        views[name] = view
    valid = [result for result, prediction in zip(results, predictions) if prediction is not None]
    cardinalities = [sum(bits) for bits in predictions if bits is not None]
    entropies, margins = [], []
    for result in valid:
        values = result.get("m1_probabilities")
        if isinstance(values, list) and len(values) == 6 and all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in values):
            entropies.append(sum((-p * math.log(p) if p else 0) - ((1-p) * math.log(1-p) if p < 1 else 0) for p in values) / 6)
        margins.append(result.get("threshold_margin"))
    tokenlengths = {}
    for model in ("m1", "m3"):
        metadata = [result.get("tokenlengths", {}).get(model) for result in valid if isinstance(result.get("tokenlengths"), dict)]
        metadata = [value for value in metadata if isinstance(value, dict)]
        flags = [value["truncated"] for value in metadata if type(value.get("truncated")) is bool]
        tokenlengths[model] = {"input_tokens": distribution([value.get("input_tokens") for value in metadata]),
                               "used_tokens": distribution([value.get("used_tokens") for value in metadata]),
                               "truncation_n": len(flags), "truncated_count": sum(flags),
                               "truncated_rate": sum(flags) / len(flags) if flags else None}
    actual = [result["route_requested"] for result in valid if type(result.get("route_requested")) is bool]
    hypothetical = [result.get("hypothetical_route", result.get("route_eligible")) for result in valid]
    hypothetical = [value for value in hypothetical if type(value) is bool]
    fallbacks = sum(bool(result.get("fallback") or result.get("fallback_reason")) for result in valid)
    return {"schema_version": "topicweb-derived-v1", "available": True, "views": views,
            "diagnostics": {"basis": "acknowledged_object_occurrences", "eligible_items": len(records),
                            "successful_items": len(valid), "coverage": len(valid) / len(records) if records else None,
                            "undated_items": sum(not record.get("created_at") for record in records),
                            "cardinality": {**distribution(cardinalities), "counts": [cardinalities.count(i) for i in range(7)]},
                            "m1_binary_entropy_nats": distribution(entropies), "m1_threshold_margin": distribution(margins),
                            "tokenlengths": tokenlengths,
                            "routing": {"actual_requested": sum(actual), "actual_known_n": len(actual),
                                        "actual_rate": sum(actual) / len(actual) if actual else None,
                                        "hypothetical_requested": sum(hypothetical), "hypothetical_known_n": len(hypothetical),
                                        "hypothetical_rate": sum(hypothetical) / len(hypothetical) if hypothetical else None,
                                        "m3_used": sum(result.get("used_path") == "m3" for result in valid),
                                        "fallback_count": fallbacks, "fallback_rate": fallbacks / len(valid) if valid else None}}}


def check_derived(records, results, reported):
    expected = recalculate_derived(records, results)
    close(reported, expected, "derived_view_mismatch")
    return {"schema_version": expected["schema_version"], "weighting_and_buckets_verified": True,
            "object_type_and_routing_strata_verified": True, "known_n_diagnostics_verified": True}


def check_source(records, manifest):
    require(300 <= len(records) <= 400, "registered_source_sample_count")
    close(manifest, {"source": "discourse", "site": "discuss.python.org", "category_id": 7, "category_name": "Python Help",
                     "cohort": "latest_created_public_unpinned_topics_prefix", "topic_order": "created_desc", "post_order": "post_number_asc",
                     "window_bounds": "not_a_time_window", "max_topics": 100, "max_items": 400, "text_field": "raw",
                     "normalization_for_model_input": "none", "content_license": "CC BY-NC-SA 3.0",
                     "license_url": "https://creativecommons.org/licenses/by-nc-sa/3.0/", "record_count": len(records),
                     "max_requests": 160, "max_seconds": 900, "min_request_interval_seconds": 1.0}, "source_manifest_contract")
    require(manifest.get("from_utc") is None and manifest.get("to_utc") is None
            and manifest.get("sampling_complete") is False, "false_time_window_or_census")
    topics = manifest.get("topic_ids")
    require(isinstance(topics, list) and 0 < len(topics) <= 100 and all(type(i) is int and i > 0 for i in topics)
            and len(topics) == len(set(topics)) == manifest.get("selected_topic_count"), "topic_cohort")
    exclusions = manifest.get("exclusions")
    require(isinstance(exclusions, dict) and set(exclusions) == EXCLUSIONS
            and all(type(value) is int and value >= 0 for value in exclusions.values()), "exclusion_metadata")
    unavailable, truncated = manifest.get("unavailable_post_ids"), manifest.get("truncated_topic_ids")
    for values in (unavailable, truncated):
        require(isinstance(values, list) and all(type(value) is int and value > 0 for value in values)
                and len(set(values)) == len(values), "availability_identity_lists")
    require(exclusions["unavailable_stream_ids"] == len(unavailable) and set(truncated) <= set(topics), "availability_counts")
    require(manifest.get("collection_complete") is (not unavailable and not truncated), "thread_completeness_claim")
    require(manifest.get("stop_reason") in {"item_limit", "topic_limit", "source_exhausted"}, "sampling_stop_reason")
    if manifest["stop_reason"] == "item_limit":
        require(len(records) == 400, "item_stop_count")
    if manifest["stop_reason"] == "topic_limit":
        require(len(topics) == 100, "topic_stop_count")
    requests = manifest.get("requests")
    require(isinstance(requests, list) and 0 < len(requests) <= 160, "source_request_count")
    for number, request in enumerate(requests, 1):
        require(request.get("number") == number and request.get("http_status") == 200
                and request.get("endpoint_kind") in {"category", "topic", "topic_posts"}, "source_request_identity")
        require(type(request.get("response_bytes")) is int and 0 < request["response_bytes"] <= 2 * 1024**2
                and isinstance(request.get("response_sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", request["response_sha256"]), "source_response_binding")
    elapsed = manifest.get("elapsed_seconds")
    require(type(elapsed) in (int, float) and math.isfinite(elapsed) and 0 <= elapsed <= 900, "source_time_budget")
    require(elapsed + .01 >= len(requests) - 1, "source_minimum_interval_lower_bound")
    topic_positions = {identifier: index for index, identifier in enumerate(topics)}
    previous_position = -1
    previous_numbers, by_id = {}, {}
    unresolved = external_parents = 0
    for record in records:
        raw, provenance = record.get("source_payload_raw"), record.get("provenance")
        require(isinstance(raw, dict) and isinstance(provenance, dict), "source_payload_missing")
        identifier, topic, number = raw.get("id"), raw.get("topic_id"), raw.get("post_number")
        require(all(type(value) is int and value > 0 for value in (identifier, topic, number))
                and topic in topic_positions and type(raw.get("post_type")) is int and raw["post_type"] == 1, "ordinary_post_identity")
        require(record.get("source") == "discourse" and record.get("site") == "discuss.python.org"
                and record.get("object_type") == "post" and record.get("source_object_id") == str(identifier)
                and record.get("thread_id") == str(topic), "record_source_identity")
        require(identifier not in unavailable and identifier not in by_id, "record_unavailable_or_duplicate")
        require(raw.get("raw") == record["model_input_text"] and "cooked" not in raw, "native_raw_only")
        username = raw.get("username")
        require(isinstance(username, str) and username and username not in {"system", "discobot"}
                and raw.get("user_id") != -1 and raw.get("hidden") is not True and raw.get("deleted_at") is None, "public_non_system_post")
        require(record.get("author_display_name") == username and provenance.get("author_username") == username
                and record.get("content_license") == "CC BY-NC-SA 3.0"
                and provenance.get("license_url") == "https://creativecommons.org/licenses/by-nc-sa/3.0/"
                and provenance.get("source_policy_url") == "https://discuss.python.org/tos", "source_attribution")
        require(record.get("source_url") == f"https://discuss.python.org/t/{topic}/{number}"
                and provenance.get("category_id") == 7 and provenance.get("topic_id") == topic
                and provenance.get("post_number") == number and provenance.get("text_field") == "raw", "source_url_or_provenance")
        require(record.get("created_at") == utc(raw.get("created_at")), "source_creation_time")
        if raw.get("updated_at") is not None:
            require(record.get("updated_at") == utc(raw["updated_at"]), "source_update_time")
        require(topic_positions[topic] >= previous_position and number > previous_numbers.get(topic, 0), "source_order")
        previous_position, previous_numbers[topic] = topic_positions[topic], number
        by_id[identifier] = (topic, number)
        reply = raw.get("reply_to_post_number")
        require(provenance.get("reply_to_post_number") == reply, "reply_provenance")
        parent = record.get("parent_object_id")
        if reply is None:
            require(parent is None, "parent_without_reply")
        else:
            require(type(reply) is int and 0 < reply < number, "reply_number")
            if parent is None:
                unresolved += 1
            else:
                require(isinstance(parent, str) and parent.isdigit() and int(parent) > 0, "parent_identity")
                if int(parent) in by_id:
                    require(by_id[int(parent)] == (topic, reply), "parent_link")
                else:
                    external_parents += 1
    require(unresolved == exclusions["unresolved_reply_parent"], "unresolved_reply_count")
    require(manifest.get("source_link_count") == len(records)
            and manifest.get("observed_created_at_min") == min(row["created_at"] for row in records)
            and manifest.get("observed_created_at_max") == max(row["created_at"] for row in records), "source_date_or_link_summary")
    fetched = manifest.get("fetched_post_count")
    excluded_posts = sum(exclusions[key] for key in ("system_posts", "nonregular_posts", "deleted_or_hidden_posts", "duplicate_posts"))
    require(type(fetched) is int and fetched >= len(records) + excluded_posts, "fetched_post_count")
    return {"records": len(records), "selected_topics": len(topics), "source_link_coverage": 1.0,
            "unavailable_stream_ids": len(unavailable), "truncated_topics": len(truncated), "exclusions": exclusions,
            "parent_ids_outside_selected_records": external_parents, "sampling_complete": False,
            "collection_complete": manifest["collection_complete"], "stop_reason": manifest["stop_reason"]}


def verify(run, job):
    require(run.get("experiment_id") == "EXP-078" and run.get("status") == "Passed"
            and run.get("stage") == "discourse_operational" and run.get("attempt") == 1, "run_not_passed")
    require(all(run.get(flag) is False for flag in ("training", "validation_accessed", "test_accessed", "external_gold_accessed", "source_raw_read_by_driver")), "access_boundary")
    require(run.get("seed") == 42 and run.get("label_order") == list(LOCAL.LABELS)
            and run.get("maximum_seconds") == 3600, "run_model_or_budget_contract")
    close(run.get("query"), QUERY, "run_query")
    entry = run.get("job")
    require(isinstance(entry, dict) and entry.get("id") == job.get("id") and entry.get("status") == "Passed", "job_binding")
    require(job.get("state") == entry.get("state") == "completed" and job.get("error_code") is None
            and job.get("mode") == "research" and job.get("source") == "discourse"
            and not job.get("raw_expired") and not job.get("items_expired"), "job_terminal_contract")
    close(job.get("request"), {"source": "discourse", "mode": "research", "max_qwen_calls": 500, "audit_rate": 0, "seed": 42, "query": QUERY}, "job_request_contract")
    items = job.get("items")
    require(isinstance(items, list) and [item.get("ordinal") for item in items] == list(range(len(items))), "row_ordinals")
    records, results = [item["record"] for item in items], [item["result"] for item in items]
    require(len(records) == job.get("total_items") == job.get("completed_items") == entry.get("total_items") == entry.get("completed_items"), "completed_count")
    snapshot = LOCAL.check_records(records)
    require(snapshot == job.get("snapshot_hash") == entry.get("snapshot_hash"), "snapshot_hash")
    close(entry.get("private_snapshot"), {"database": "private/jobs.sqlite3", "job_id": job["id"], "snapshot_sha256": snapshot}, "snapshot_reference")
    close(entry.get("manifest"), job["manifest"], "manifest_binding")
    require(entry.get("manifest_sha256") == sha(canonical(job["manifest"])) == sha(canonical(entry["manifest"])), "manifest_hash")
    require(type(entry.get("elapsed_seconds")) in (int, float) and 0 <= entry["elapsed_seconds"] <= 3600, "job_time_limit")
    source = check_source(records, job["manifest"])
    computed = LOCAL.recalculate(records, results, "research")
    close(job.get("dashboard"), computed, "saved_dashboard")
    close(entry.get("dashboard"), computed, "reported_dashboard")
    derived_check = check_derived(records, results, entry.get("dashboard", {}).get("derived"))
    require(computed["summary"]["coverage"] == 1.0 and not computed["routing"]["fallbacks"], "research_full_coverage")
    fingerprints = set()
    token_counts, truncated = {"m1": [], "m3": []}, {"m1": 0, "m3": 0}
    peak_rss = peak_mlx = 0
    for result in results:
        fingerprint = result.get("fingerprint")
        require(isinstance(fingerprint, str) and re.fullmatch(r"[0-9a-f]{64}", fingerprint), "pipeline_fingerprint")
        fingerprints.add(fingerprint)
        for model, cap in (("m1", 256), ("m3", 384)):
            meta = result.get("tokenlengths", {}).get(model)
            if model == "m3" and not result["route_requested"]:
                require(meta is None and result.get("truncflags", {}).get(model) is None, "unobserved_m3_tokens")
                continue
            require(isinstance(meta, dict) and type(meta.get("input_tokens")) is int and type(meta.get("used_tokens")) is int
                    and 1 <= meta["used_tokens"] <= cap and meta["input_tokens"] >= meta["used_tokens"], "token_length_contract")
            flag = meta["input_tokens"] > meta["used_tokens"]
            require(meta.get("truncated") is flag and result.get("truncflags", {}).get(model) is flag, "truncation_contract")
            token_counts[model].append(meta["input_tokens"])
            truncated[model] += flag
        resources = result.get("resources")
        require(isinstance(resources, dict) and type(resources.get("peak_rss_bytes")) is int and 0 <= resources["peak_rss_bytes"] <= 12 * 1024**3
                and type(resources.get("mlx_peak_bytes")) is int and 0 <= resources["mlx_peak_bytes"] <= 10_000_000_000
                and type(resources.get("elapsed_seconds")) in (int, float) and 0 <= resources["elapsed_seconds"] <= 3600, "resource_budget")
        peak_rss = max(peak_rss, resources["peak_rss_bytes"])
        peak_mlx = max(peak_mlx, resources["mlx_peak_bytes"])
    require(len(fingerprints) == 1, "mixed_pipeline_fingerprints")
    lengths = {model: {"observed": len(values), "min": min(values) if values else None,
                      "median": statistics.median(values) if values else None, "max": max(values) if values else None,
                      "truncated_count": truncated[model]} for model, values in token_counts.items()}
    return {"job_id": job["id"], "snapshot_sha256": snapshot, "source": source, "derived": computed,
            "route_requested_rate": computed["routing"]["route_requested"] / len(records),
            "pipeline_fingerprint": next(iter(fingerprints)), "length_diagnostics": lengths,
            "peak_rss_bytes": peak_rss, "mlx_peak_bytes": peak_mlx, "derived_check": derived_check, "claim_boundary": BOUNDARY}


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    target = RUN / "verification.json"
    require(not target.exists() and not any(path.is_symlink() for path in (target, *target.parents)), "verification_exists_or_symlink")
    result = {"experiment_id": "EXP-078", "status": "Failed", "exp078_complete": False,
              "verified_at": datetime.now(timezone.utc).isoformat(), "models_loaded": False,
              "producer_numerical_helpers_imported": False, "gold_accessed": False, "database_scope": "selected_job_only"}
    try:
        run_path = RUN / "run.json"
        run_hash = file_hash(run_path)
        run = LOCAL.strict_json(run_path.read_text())
        require(run.get("protocol_sha256") == file_hash(PROTOCOL) and run.get("source_review_sha256") == file_hash(REVIEW), "protocol_or_review_drift")
        sources = run.get("sources")
        require(isinstance(sources, dict) and sources, "implementation_bindings_missing")
        for name, expected in sources.items():
            relative = Path(name)
            require(not relative.is_absolute() and ".." not in relative.parts
                    and (relative.parts[0] in {"topicweb", "scripts", "tests", "static"}
                         or name == "requirements-lock.txt"), "implementation_path")
            require(file_hash(ROOT / relative) == expected, "implementation_drift")
        require(current_source_hashes() == sources, "implementation_scope_changed")
        bindings = run.get("soak")
        require(isinstance(bindings, dict), "soak_bindings_missing")
        prefix = "private/validation/exp-077/attempt-1/"
        documents = {}
        for key in ("run", "verification", "plan"):
            require(bindings[key]["path"] == prefix + key + ".json", "soak_binding_path")
            path = ROOT / bindings[key]["path"]
            require(file_hash(path) == bindings[key]["sha256"], "soak_terminal_drift")
            documents[key] = LOCAL.strict_json(path.read_text())
        check_soak(documents["run"], documents["verification"], bindings)
        check_source_scope(documents["plan"].get("sources"), sources)
        identifier = run.get("job", {}).get("id")
        require(isinstance(identifier, str) and re.fullmatch(r"[0-9a-f]{32}", identifier), "job_id")
        job = read_selected_job(ROOT / "private/jobs.sqlite3", identifier)
        logical = sha(canonical(job))
        result.update(verify(run, job))
        require(file_hash(run_path) == run_hash and sha(canonical(read_selected_job(ROOT / "private/jobs.sqlite3", identifier))) == logical, "source_changed_during_verification")
        result.update(status="Passed", exp078_complete=True, run_sha256=run_hash,
                      selected_job_logical_sha256=logical, verifier_sha256=file_hash(Path(__file__)))
    except Exception as error:
        result["error_code"] = str(error) if isinstance(error, LOCAL.VerificationError) else "verification_input_or_internal_error"
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")
        output.flush()
        os.fsync(output.fileno())
    print(json.dumps({key: result.get(key) for key in ("status", "exp078_complete", "error_code")}))
    return 0 if result["status"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
