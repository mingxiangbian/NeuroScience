"""Independent EXP-079 replay, accounting, process and safety verification.

This consumer never imports the bounded producer or a model backend. An audited
stop can pass artifact verification while failing operational completion.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import statistics
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "private/validation/exp-079/attempt-3"
PREVIOUS_ARCHIVE_HASH = "bbb4237c55548df50a00ac5687a1b6f382ce03d8cf7d6a669d709a7c20b7b281"
PREVIOUS_VERIFICATION_HASH = "f3ab1b94efbc1333b3f04c5e094658dd7b1d9b84dba35adf7bb7c68887c373c4"
SOURCE_JOB = "5ab3326150ee448ba326233264967d34"
SOURCE_HASH = "cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16"
SOURCE_VERIFICATION_HASH = "7138c80740eed3cda2f646f9061ae345c44ae8dec749daae1bd0505c61cadff8"
MODES = ("m1_only", "research", "demo")
COSTS = ("m1_attempts", "m3_attempts", "m3_succeeded", "m1_cache_hit", "m3_cache_hit", "audit_extra_calls")
MIB = 1024**2
DEPENDENCIES = {
    "requirements.txt", "requirements-lock.txt", "start.py", "topicweb/__init__.py",
    "topicweb/app.py", "topicweb/core.py", "topicweb/adapters.py", "topicweb/store.py",
    "topicweb/worker.py", "topicweb/inference_process.py", "topicweb/telemetry.py",
    "static/index.html", "static/app.js", "static/app.css", "scripts/run_soak.py",
    "scripts/bounded_runtime_support.py", "scripts/run_bounded_runtime.py", "scripts/verify_bounded_runtime.py",
    "scripts/verify_local.py", "scripts/verify_discourse_validation.py",
    "tests/test_bounded_runtime.py", "tests/test_verify_bounded_runtime.py",
}


def load_independent(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LOCAL = load_independent("exp079_local_independent", "verify_local.py")
DERIVED = load_independent("exp079_derived_independent", "verify_discourse_validation.py")


class VerificationError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise VerificationError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def finite(value, *, minimum=0):
    return type(value) in (int, float) and math.isfinite(value) and value >= minimum


def close(actual, expected, code="reported_value_mismatch", tolerance=1e-9):
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(expected) <= set(actual), code)
        for key, value in expected.items():
            close(actual[key], value, code, tolerance)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), code)
        for one, two in zip(actual, expected):
            close(one, two, code, tolerance)
    elif type(expected) in (int, float) and not isinstance(expected, bool):
        require(type(actual) in (int, float) and math.isfinite(actual) and abs(actual - expected) <= tolerance, code)
    else:
        require(type(actual) is type(expected) and actual == expected, code)


def latency_distribution(values):
    require(all(finite(value) for value in values), "invalid_latency")
    values = sorted(values)
    def quantile(p):
        position = (len(values)-1)*p
        low, high = math.floor(position), math.ceil(position)
        return values[low] * (1-(position-low)) + values[high] * (position-low)
    return {"n": len(values), "min": values[0] if values else None, "max": values[-1] if values else None,
            **{name: quantile(p) if values else None for name, p in (("median", .5), ("p90", .9), ("p95", .95))}}


def validate_source_rows(rows):
    require(isinstance(rows, list) and len(rows) == 340 and [row.get("ordinal") for row in rows] == list(range(340)), "source_ordinal_alignment")
    require(LOCAL.check_records([row["record"] for row in rows]) == SOURCE_HASH, "source_snapshot_identity")
    metadata = []
    unique, routed_unique = set(), set()
    for row in rows:
        record, result = row["record"], row.get("result")
        require(isinstance(result, dict) and type(result.get("hypothetical_route")) is bool, "source_route_identity")
        LOCAL.probabilities(result.get("m1_probabilities"))
        LOCAL.decisions(result.get("m1_prediction"))
        metadata.append({"ordinal": row["ordinal"], "input_sha256": record["model_input_hash"],
                         "route_eligible": result["hypothetical_route"]})
        unique.add(record["model_input_hash"])
        if result["hypothetical_route"]:
            routed_unique.add(record["model_input_hash"])
    require(len(unique) == 338 and len(routed_unique) == sum(row["route_eligible"] for row in metadata) == 25, "source_route_coverage")
    return metadata


def parse_system(sample):
    require(isinstance(sample, dict) and finite(sample.get("monotonic")), "system_sample_time")
    require(sample.get("status") in {"observed", "unknown"}, "system_sample_status")
    if sample["status"] == "unknown":
        return None
    pressure = sample.get("pressure_raw")
    raw = sample.get("vm_stat_raw")
    require(isinstance(pressure, str) and pressure.strip() in {"1", "2", "4"} and isinstance(raw, str), "system_raw_schema")
    page = re.search(r"page size of (\d+) bytes", raw)
    incoming = re.search(r"^Swapins:\s*(\d+)\.?\s*$", raw, re.MULTILINE)
    outgoing = re.search(r"^Swapouts:\s*(\d+)\.?\s*$", raw, re.MULTILINE)
    require(page is not None and incoming is not None and outgoing is not None and int(page[1]) > 0, "system_raw_parse")
    values = {"pressure_level": int(pressure.strip()), "page_size": int(page[1]), "swapins": int(incoming[1]), "swapouts": int(outgoing[1])}
    require(all(type(sample.get(key)) is int and sample[key] == value for key, value in values.items()), "system_raw_identity")
    return values


def system_summary(samples):
    parsed = [parse_system(sample) for sample in samples]
    unknown = sum(value is None for value in parsed)
    critical = sum(value is not None and value["pressure_level"] == 4 for value in parsed)
    warning = sum(value is not None and value["pressure_level"] == 2 for value in parsed)
    rates, invalid, streak, longest = [None] * len(samples), 0, 0, 0
    for index in range(1, len(samples)):
        old, new = parsed[index-1], parsed[index]
        dt = samples[index]["monotonic"] - samples[index-1]["monotonic"]
        if (old is None or new is None or not 0 < dt <= 3 or new["page_size"] != old["page_size"]
                or new["swapins"] < old["swapins"] or new["swapouts"] < old["swapouts"]):
            invalid += 1
            streak = 0
            continue
        rates[index] = ((new["swapins"]-old["swapins"]) + (new["swapouts"]-old["swapouts"])) * new["page_size"] / dt
        streak = streak+1 if rates[index] >= 100*MIB else 0
        longest = max(longest, streak)
    observed_rates = [rate for rate in rates if rate is not None]
    return {"sample_count": len(samples), "unknown_samples": unknown, "critical_samples": critical,
            "warning_samples": warning, "invalid_intervals": invalid, "longest_thrashing_intervals": longest,
            "thrashing": longest >= 3, "maximum_swap_bytes_per_second": max(observed_rates) if observed_rates else None,
            "gate_passed": len(samples) >= 2 and unknown == critical == invalid == 0 and longest < 3,
            "swap_rates": rates, "initial_swap_occupancy_used_as_failure": False}


def result_rss(sample):
    require(isinstance(sample, dict) and sample.get("status") == "observed", "receipt_rss_unknown")
    require(type(sample.get("child_pid")) is int and type(sample.get("parent_pid")) is int
            and sample["child_pid"] > 0 and sample["parent_pid"] > 0, "receipt_pid_identity")
    require(isinstance(sample.get("raw_ps"), str), "receipt_rss_raw")
    rows = {}
    for line in sample["raw_ps"].splitlines():
        match = re.fullmatch(r"\s*(\d+)\s+(\d+)\s*", line)
        require(match is not None and int(match[1]) not in rows, "receipt_rss_parse")
        rows[int(match[1])] = int(match[2]) * 1024
    require(set(rows) == {sample["child_pid"], sample["parent_pid"]}, "receipt_rss_pid_set")
    require(rows[sample["child_pid"]] == sample.get("child_current_rss_bytes")
            and rows[sample["parent_pid"]] == sample.get("parent_current_rss_bytes") and min(rows.values()) > 0, "receipt_rss_identity")
    return rows[sample["child_pid"]], rows[sample["parent_pid"]]


def parse_processes(sample, service):
    require(isinstance(sample, dict) and sample.get("status") in {"observed", "unknown"}, "process_sample_status")
    if sample["status"] == "unknown":
        return None
    raw_rows = sample.get("selected_ps")
    require(isinstance(raw_rows, list) and all(isinstance(line, str) for line in raw_rows), "selected_ps_schema")
    parsed = {}
    for line in raw_rows:
        fields = line.strip().split(None, 8)
        require(len(fields) == 9 and all(value.isdigit() for value in fields[:3]), "selected_ps_parse")
        pid, ppid, rss = map(int, fields[:3])
        start = " ".join(fields[3:8])
        try:
            datetime.strptime(start, "%a %b %d %H:%M:%S %Y")
        except ValueError:
            raise VerificationError("process_birth_time_parse") from None
        require(pid > 0 and pid not in parsed, "selected_ps_pid")
        parsed[pid] = {"pid": pid, "ppid": ppid, "current_rss_bytes": rss*1024,
                       "start_time": start, "process_key": f"{pid}|{start}", "comm": Path(fields[8]).name}
    parent, models, orphans = sample.get("parent"), sample.get("models"), sample.get("orphan_models")
    tracked_other = sample.get("tracked_other", [])
    require(isinstance(parent, dict) and isinstance(models, list) and isinstance(orphans, list)
            and isinstance(tracked_other, list), "process_members_schema")
    retained_owned = [*models, *tracked_other]
    selected = [parent, *retained_owned, *orphans]
    require(all(isinstance(item, dict) and type(item.get("pid")) is int for item in selected), "process_record_schema")
    require(len({item["pid"] for item in selected}) == len(selected) and set(parsed) == {item["pid"] for item in selected}, "selected_ps_members")
    for item in selected:
        close(item, parsed[item["pid"]], "process_raw_identity")
    require(parent["pid"] == service.get("pid") and parent["process_key"] == service.get("process_key"), "service_identity_changed")
    require(parent["comm"] == service.get("comm") and parent["start_time"] == service.get("start_time"), "service_birth_identity")
    owned = {parent["pid"]}
    for _ in retained_owned:
        owned.update(model["pid"] for model in retained_owned if model["ppid"] in owned)
    require(all(model["pid"] in owned for model in retained_owned), "model_parentage_unverified")
    workers = [model for model in retained_owned if parsed[model["pid"]]["ppid"] == service["pid"]]
    auxiliary = [model for model in retained_owned if parsed[model["pid"]]["ppid"] != service["pid"]]
    for field, expected in (("inference_workers", workers), ("auxiliary_processes", auxiliary)):
        if field in sample:
            close(sample[field], expected, "process_role_mismatch")
    seen, absent = sample.get("seen_model_keys"), sample.get("absent_model_keys")
    require(isinstance(seen, list) and isinstance(absent, list) and all(isinstance(key, str) for key in [*seen, *absent])
            and len(set(seen)) == len(seen) and len(set(absent)) == len(absent), "process_history_schema")
    live = {item["process_key"] for item in [*retained_owned, *orphans]}
    require(live <= set(seen) and set(absent) == set(seen)-live, "process_absence_identity")
    return {"parent": parent, "models": models, "tracked_other": tracked_other,
            "inference_workers": workers, "auxiliary_processes": auxiliary,
            "orphans": orphans, "live": live, "seen": set(seen), "absent": set(absent)}


def verify_safety(samples, process_events, service, jobs, *, elapsed_seconds, limit_seconds=1800):
    """Pure independent monitor/readiness/exit gates, reusable for one-job EXP-080."""
    require(isinstance(samples, list) and isinstance(process_events, list) and isinstance(jobs, list), "safety_sequence_schema")
    require(isinstance(service, dict) and type(service.get("pid")) is int and service["pid"] > 0
            and isinstance(service.get("process_key"), str), "service_schema")
    require([row.get("index") for row in samples] == list(range(len(samples))), "sample_index_alignment")
    systems = []
    process_rows = []
    cadence_invalid = unknown_process = multiple_workers = orphan_observations = resource_violations = 0
    auxiliary_samples = tracked_other_samples = 0
    maximum_workers = maximum_auxiliary = None
    previous_seen, peak_child, peak_parent, disk_minimum = set(), None, None, None
    unknown_history = False
    for index, sample in enumerate(samples):
        require(finite(sample.get("started_monotonic")) and finite(sample.get("monotonic"))
                and sample["started_monotonic"] <= sample["monotonic"], "sample_clock_schema")
        system = sample.get("system")
        require(isinstance(system, dict) and finite(system.get("monotonic"))
                and sample["started_monotonic"] <= system["monotonic"] <= sample["monotonic"], "system_clock_coverage")
        if index and sample["started_monotonic"] - samples[index-1]["monotonic"] < 1-1e-6:
            cadence_invalid += 1
        systems.append(system)
        processes = parse_processes(sample.get("processes"), service)
        process_rows.append(processes)
        disk = sample.get("disk_free_bytes")
        if type(disk) is not int or disk < 0:
            resource_violations += 1
        else:
            disk_minimum = disk if disk_minimum is None else min(disk_minimum, disk)
            resource_violations += disk < 512*MIB
        if processes is None:
            unknown_process += 1
            unknown_history = True
            continue
        require(previous_seen <= processes["seen"], "seen_process_history_lost")
        if not unknown_history:
            event_keys = {event["process_key"] for event in process_events
                          if isinstance(event, dict) and isinstance(event.get("process_key"), str)
                          and finite(event.get("monotonic")) and event["monotonic"] <= sample["monotonic"]}
            require(previous_seen | processes["live"] <= processes["seen"] <= previous_seen | processes["live"] | event_keys,
                    "seen_process_without_observation")
            require({row["process_key"] for row in processes["tracked_other"]} <= previous_seen | event_keys,
                    "tracked_other_without_prior_identity")
        previous_seen = processes["seen"]
        worker_count, auxiliary_count = len(processes["inference_workers"]), len(processes["auxiliary_processes"])
        maximum_workers = worker_count if maximum_workers is None else max(maximum_workers, worker_count)
        maximum_auxiliary = auxiliary_count if maximum_auxiliary is None else max(maximum_auxiliary, auxiliary_count)
        multiple_workers += worker_count > 1
        auxiliary_samples += auxiliary_count > 0
        tracked_other_samples += bool(processes["tracked_other"])
        orphan_observations += len(processes["orphans"])
        parent_rss = processes["parent"]["current_rss_bytes"]
        peak_parent = parent_rss if peak_parent is None else max(peak_parent, parent_rss)
        resource_violations += parent_rss > 1024*MIB
        for model in [*processes["models"], *processes["tracked_other"], *processes["orphans"]]:
            rss = model["current_rss_bytes"]
            peak_child = rss if peak_child is None else max(peak_child, rss)
            resource_violations += rss > 12*1024*MIB
    system = system_summary(systems)
    events_by_job = {}
    previous_time = None
    for event in process_events:
        require(isinstance(event, dict) and isinstance(event.get("job_id"), str)
                and event.get("type") in {"constructor_started", "ready", "process_exit", "final_gate_passed"}
                and finite(event.get("monotonic")), "process_event_schema")
        require(previous_time is None or event["monotonic"] >= previous_time, "process_event_order")
        previous_time = event["monotonic"]
        events_by_job.setdefault(event["job_id"], []).append(event)
        if event["type"] == "constructor_started":
            require(event.get("pid") is None and event.get("process_key") is None, "constructor_event_pid")
        else:
            require(event.get("pid") is None or type(event["pid"]) is int and event["pid"] > 0, "process_event_pid")
            require(event.get("process_key") is None or isinstance(event["process_key"], str)
                    and event["process_key"].startswith(f"{event['pid']}|"), "process_event_key")
        if event["type"] == "final_gate_passed":
            require(event.get("returncode") == 0 and type(event.get("returncode")) is int, "false_final_gate_event")
    require(set(events_by_job) <= {job.get("id") for job in jobs}, "unbound_process_event")
    readiness, exits, cleanups, used_processes = [], [], [], set()
    previous_job = None
    for job in jobs:
        indices = job.get("readiness_indices")
        require(isinstance(indices, list) and all(type(index) is int and 0 <= index < len(samples) for index in indices), "readiness_index_schema")
        ready = len(indices) == 10 and indices == list(range(indices[0], indices[0]+10))
        if ready:
            ready = all(systems[index].get("status") == "observed" and systems[index].get("pressure_level") == 1
                        and process_rows[index] is not None and not process_rows[index]["live"] for index in indices)
            ready = ready and all(system["swap_rates"][index] is not None and system["swap_rates"][index] < 10*MIB for index in indices[1:])
            require(finite(job.get("started_monotonic")), "job_submission_time")
            ready = ready and samples[indices[-1]]["monotonic"] <= job["started_monotonic"]
            ready_start, ready_end = job.get("readiness_started_monotonic"), job.get("readiness_ended_monotonic")
            require(finite(ready_start) and finite(ready_end) and ready_start <= ready_end, "readiness_clock_schema")
            ready = ready and ready_end-ready_start <= 60+1e-6 and ready_end <= job["started_monotonic"]
            ready = ready and samples[indices[0]]["monotonic"] >= ready_start
            if previous_job is not None:
                previous_exit = previous_job.get("exit_observation") or {}
                ready = ready and previous_job.get("status", previous_job.get("state")) in {"completed", "completed_with_fallback"}
                ready = ready and finite(previous_job.get("ended_monotonic")) and ready_start >= previous_job["ended_monotonic"]
                ready = ready and type(previous_exit.get("sample_index")) is int and indices[0] > previous_exit["sample_index"]
        readiness.append({"id": job["id"], "indices": indices, "passed": bool(ready)})
        events = events_by_job.get(job["id"], [])
        types = [event["type"] for event in events]
        if events:
            require(types[0] == "constructor_started" and types.count("constructor_started") == 1
                    and types.count("ready") <= 1 and types.count("process_exit") <= 1
                    and types.count("final_gate_passed") <= 1, "process_event_sequence")
            require(all(event["monotonic"] >= job["started_monotonic"] for event in events), "process_before_submission")
        keys = {event["process_key"] for event in events if event.get("process_key") is not None}
        require(len(keys) <= 1 and not used_processes.intersection(keys), "model_process_reused")
        used_processes.update(keys)
        completed = job.get("status", job.get("state")) in {"completed", "completed_with_fallback"}
        actual_exits = [event for event in events if event["type"] == "process_exit"]
        normal = bool(keys) and len(actual_exits) == 1 and actual_exits[0].get("returncode") == 0 and any(event["type"] == "final_gate_passed" and event.get("normal_exit") is True for event in events)
        if normal:
            require(types == ["constructor_started", "ready", "process_exit", "final_gate_passed"], "normal_exit_event_sequence")
        observation = job.get("exit_observation") or (job.get("cleanup") or {}).get("exit_observation")
        absent = False
        if isinstance(observation, dict) and type(observation.get("sample_index")) is int:
            index = observation["sample_index"]
            require(0 <= index < len(samples), "exit_observation_index")
            process = process_rows[index]
            if process is not None:
                close(observation.get("absent_model_keys"), sorted(process["absent"]), "exit_absence_binding")
                absent = keys <= process["absent"] and not process["live"]
                if actual_exits:
                    absent = absent and samples[index]["monotonic"] >= actual_exits[-1]["monotonic"]
        if not events and not completed:
            absent = bool(process_rows and process_rows[-1] is not None and not process_rows[-1]["live"])
        exits.append({"id": job["id"], "process_keys": sorted(keys), "normal_exit": normal if completed else False,
                      "absence_observed": absent, "passed": absent and (normal if completed else True)})
        cleanup = job.get("cleanup")
        if isinstance(cleanup, dict):
            start, end = cleanup.get("started_monotonic"), cleanup.get("ended_monotonic")
            require(finite(start) and finite(end) and start <= end and cleanup.get("max_seconds") == 15, "cleanup_clock_schema")
            cleanups.append({"id": job["id"], "elapsed_seconds": end-start,
                             "passed": end-start <= 15+1e-6 and cleanup.get("terminal_confirmed") is True
                             and cleanup.get("models_absent_confirmed") is True and absent})
        previous_job = job
    final_absent = bool(process_rows and process_rows[-1] is not None and not process_rows[-1]["live"]
                        and used_processes <= process_rows[-1]["absent"])
    readiness_gate = all(row["passed"] for row in readiness)
    exit_gate = final_absent and all(row["passed"] for row in exits)
    gate = (system["gate_passed"] and not any((cadence_invalid, unknown_process, multiple_workers, orphan_observations, resource_violations))
            and readiness_gate and exit_gate and all(row["passed"] for row in cleanups)
            and finite(elapsed_seconds) and elapsed_seconds <= limit_seconds)
    return {"system": {key: value for key, value in system.items() if key != "swap_rates"},
            "processes": {"unknown_samples": unknown_process, "multiple_inference_worker_samples": multiple_workers,
                          "maximum_inference_workers": maximum_workers, "maximum_auxiliary_processes": maximum_auxiliary,
                          "samples_with_auxiliary_processes": auxiliary_samples,
                          "samples_with_tracked_other": tracked_other_samples,
                          "concurrency_basis": "owned_python_roots_with_ppid_equal_to_service_pid",
                          "auxiliary_role_claim": "ownership_only_specific_library_role_unconfirmed",
                          "orphan_observations": orphan_observations, "peak_observed_child_rss_bytes": peak_child,
                          "peak_observed_parent_rss_bytes": peak_parent, "seen_process_keys": sorted(previous_seen),
                          "all_seen_absent_at_end": final_absent},
            "cadence_invalid_intervals": cadence_invalid, "minimum_disk_free_bytes": disk_minimum,
            "resource_violation_count": resource_violations, "readiness": readiness, "exits": exits,
            "cleanup": cleanups, "readiness_gate": readiness_gate, "exit_gate": exit_gate, "gate_passed": bool(gate)}


def recalculate_aggregate(records, results, mode, costs):
    derived = DERIVED.recalculate_derived(records, results)
    objects = derived["views"]["object_weighted"]
    summary = objects["summary"]
    available = [(record, result) for record, result in zip(records, results) if result is not None]
    paths, fallback = Counter(), Counter()
    paired = disagree = requested = 0
    latencies = []
    for _, result in available:
        paths[result["used_path"]] += 1
        requested += result["route_requested"]
        if result.get("fallback_reason"):
            fallback[result["fallback_reason"]] += 1
        if result.get("m3_prediction") is not None:
            paired += 1
            disagree += result["m1_prediction"] != result["m3_prediction"]
        latencies.append(result["latency_ms"])
    types = Counter(record["object_type"] for record in records)
    successful_types = Counter(record["object_type"] for record, _ in available)
    return {"mode": mode, "labels": list(LOCAL.LABELS),
            "summary": {"eligible_items": len(records), "successful_items": len(available),
                        "missing_predictions": len(records)-len(available), "coverage": summary["coverage"],
                        "neutral_count": summary["neutral_count"], "neutral_rate": summary["neutral_rate"],
                        "exact_input_groups": len({record["model_input_hash"] for record in records}),
                        "normalized_text_groups": len({record["dedup_hash"] for record in records}),
                        "undated_items": sum(not record.get("created_at") for record in records)},
            "emotions": objects["emotions"],
            "daily": [{"date": bucket["date"], "n": bucket["summary"]["successful_units"],
                       "neutral": bucket["summary"]["neutral_count"],
                       "prevalence": {item["label"]: item["prevalence"] for item in bucket["emotions"]}}
                      for bucket in objects["trends"]["daily"] if bucket["summary"]["successful_units"]],
            "object_types": [{"type": name, "eligible": count, "successful": successful_types[name]} for name, count in sorted(types.items())],
            "routing": {"route_requested": requested, "paths": dict(paths), "cost": costs, "fallbacks": dict(fallback),
                        "paired_n": paired, "paired_disagreement": disagree/paired if paired else None},
            "uncertainty": {"m1_mean_binary_entropy_nats": derived["diagnostics"]["m1_binary_entropy_nats"]["mean"],
                            "n": derived["diagnostics"]["m1_binary_entropy_nats"]["n"]},
            "timing": {"mean_item_ms": sum(latencies)/len(latencies) if latencies else None, "n": len(latencies)}}


def recompute_job(job, source_rows, mode, m3_reference):
    require(mode in MODES and job.get("mode") == mode, "job_mode_identity")
    rows = job.get("items")
    require(isinstance(rows, list) and len(rows) == 340 and [row.get("ordinal") for row in rows] == list(range(340)), "job_ordinal_alignment")
    records = [row["record"] for row in rows]
    results = [row.get("result") for row in rows]
    require(LOCAL.check_records(records) == job.get("snapshot_hash"), "job_snapshot_identity")
    observed_count = sum(result is not None for result in results)
    require(all(result is not None for result in results[:observed_count]) and all(result is None for result in results[observed_count:]), "noncontiguous_result_prefix")
    require(job.get("total_items") == 340 and job.get("completed_items") == observed_count, "job_result_count")
    completed = job.get("state") in {"completed", "completed_with_fallback"}
    if completed:
        require(observed_count == 340, "completed_job_has_missing_results")
    cumulative = {name: 0 for name in COSTS}
    seen_m1, seen_m3, child_pids, parent_pids = set(), set(), set(), set()
    children, parents, latency, peak_rss, mlx_peak = [], [], [], [], []
    m1_difference, m3_difference, m3_unavailable = None, None, False
    violations = set()
    for index, (record, result) in enumerate(zip(records, results)):
        baseline = source_rows[index]
        require(record["model_input_text"] == baseline["record"]["model_input_text"]
                and record["model_input_hash"] == baseline["record"]["model_input_hash"], "source_input_reordered_or_changed")
        if result is None:
            continue
        require(isinstance(result, dict), "invalid_result_schema")
        p1 = LOCAL.probabilities(result.get("m1_probabilities"))
        d1 = LOCAL.decisions(result.get("m1_prediction"))
        old = baseline["result"]
        delta = max(abs(a-b) for a, b in zip(p1, old["m1_probabilities"]))
        require(delta <= 1e-6 and d1 == old["m1_prediction"] and d1 == [int(p >= .31) for p in p1], "m1_replay_mismatch")
        m1_difference = delta if m1_difference is None else max(m1_difference, delta)
        eligible = old["hypothetical_route"]
        require(result.get("hypothetical_route") is eligible, "hypothetical_route_mismatch")
        requested = eligible and mode != "m1_only"
        require(result.get("route_requested") is requested, "actual_route_mismatch")
        hashed = record["model_input_hash"]
        expected = {name: 0 for name in COSTS}
        expected["m1_attempts"], expected["m1_cache_hit"] = int(hashed not in seen_m1), int(hashed in seen_m1)
        seen_m1.add(hashed)
        use_m3, fallback = False, None
        if requested:
            if hashed in seen_m3:
                expected["m3_cache_hit"], use_m3 = 1, True
            elif m3_unavailable:
                fallback = "m3_unavailable"
                violations.add("unexpected_m3_runtime_failure")
            elif mode == "demo" and cumulative["m3_attempts"] >= 20:
                fallback = "m3_budget_exhausted"
            else:
                expected["m3_attempts"] = 1
                if mode == "demo" and result.get("fallback_reason") == "m3_runtime_failure":
                    fallback, m3_unavailable = "m3_runtime_failure", True
                    violations.add("unexpected_m3_runtime_failure")
                else:
                    expected["m3_succeeded"], use_m3 = 1, True
                    seen_m3.add(hashed)
        require(result.get("fallback_reason") == fallback and result.get("fallback") is bool(fallback), "fallback_accounting_mismatch")
        require(result.get("used_path") == ("m3" if use_m3 else "m1"), "final_path_mismatch")
        selected = d1
        if use_m3:
            p3, d3 = LOCAL.probabilities(result.get("m3_probabilities")), LOCAL.decisions(result.get("m3_prediction"))
            require(d3 == [int(p >= .31) for p in p3], "m3_threshold_mismatch")
            if hashed not in m3_reference:
                m3_reference[hashed] = (p3, d3)
            reference, decision = m3_reference[hashed]
            delta = max(abs(a-b) for a, b in zip(p3, reference))
            require(delta <= 1e-6 and d3 == decision, "m3_replay_mismatch")
            m3_difference = delta if m3_difference is None else max(m3_difference, delta)
            selected = d3
        else:
            require(result.get("m3_probabilities") is None and result.get("m3_prediction") is None, "unrequested_m3_output")
        require(LOCAL.decisions(result.get("prediction")) == selected and result.get("neutral") is (not any(selected)), "selected_decision_mismatch")
        require(result.get("active_labels") == [name for name, bit in zip(LOCAL.LABELS, selected) if bit], "active_labels_mismatch")
        counters = result.get("counters")
        require(isinstance(counters, dict) and all(type(counters.get(name)) is int and counters[name] == expected[name] for name in COSTS)
                and counters.get("fallback_reason") == fallback, "component_cost_mismatch")
        for name in COSTS:
            cumulative[name] += expected[name]
        close(result.get("cumulative_counters"), cumulative, "cumulative_cost_mismatch")
        child, parent = result_rss(result.get("telemetry"))
        child_pids.add(result["telemetry"]["child_pid"]); parent_pids.add(result["telemetry"]["parent_pid"])
        children.append(child); parents.append(parent)
        resources = result.get("resources")
        require(isinstance(resources, dict) and finite(resources.get("peak_rss_bytes")) and finite(resources.get("mlx_peak_bytes")), "receipt_resource_schema")
        peak_rss.append(resources["peak_rss_bytes"]); mlx_peak.append(resources["mlx_peak_bytes"])
        if child > 12*1024*MIB or parent > 1024*MIB or resources["peak_rss_bytes"] > 12*1024*MIB or resources["mlx_peak_bytes"] > 10_000_000_000:
            violations.add("receipt_resource_limit")
        require(finite(result.get("latency_ms")), "latency_schema")
        latency.append(result["latency_ms"])
    require(len(child_pids) <= 1 and len(parent_pids) <= 1, "within_job_process_changed")
    expected_state = "completed_with_fallback" if mode == "demo" else "completed"
    if completed:
        require(job["state"] == expected_state, "completed_mode_state")
        if not violations:
            require(cumulative["m1_attempts"] == 338 and cumulative["m1_cache_hit"] == 2, "complete_m1_cost")
            require(cumulative["m3_attempts"] == {"m1_only": 0, "research": 25, "demo": 20}[mode], "complete_m3_cost")
            require(sum(bool(result.get("fallback_reason")) for result in results) == (5 if mode == "demo" else 0), "complete_fallback_count")
    expected_aggregate = recalculate_aggregate(records, results, mode, cumulative)
    if job.get("dashboard") is not None:
        close(job["dashboard"], expected_aggregate, "aggregate_mismatch")
        DERIVED.check_derived(records, results, job["dashboard"].get("derived"))
    elif completed:
        raise VerificationError("completed_aggregate_missing")
    cost, scope, complete_cost = cumulative if completed else None, "completed_job" if completed else "acknowledged_items_lower_bound", completed
    failure = (job.get("progress") or {}).get("failure_cost") or {}
    total = failure.get("cumulative_counters")
    if not completed and isinstance(total, dict) and all(type(total.get(name)) is int and total[name] >= cumulative[name] for name in COSTS):
        require(observed_count <= total["m1_attempts"] + total["m1_cache_hit"] <= observed_count+1
                and total["m3_succeeded"] <= total["m3_attempts"], "failure_cost_inconsistent")
        cost, scope, complete_cost = {name: total[name] for name in COSTS}, "job_cumulative", True
    return {"acknowledged_events": observed_count, "completed": completed, "cost": cost,
            "acknowledged_cost": cumulative, "cost_scope": scope, "cost_complete": complete_cost,
            "latency_ms": latency_distribution(latency),
            "peak_child_rss_bytes": max(children + peak_rss) if children else None,
            "child_current_rss_peak_bytes": max(children) if children else None,
            "child_reported_peak_rss_bytes": max(peak_rss) if peak_rss else None,
            "peak_parent_rss_bytes": max(parents) if parents else None,
            "mlx_peak_bytes": max(mlx_peak) if mlx_peak else None,
            "child_median_bytes": statistics.median(children) if children else None,
            "child_plateau_ratio": statistics.median(children[-85:])/statistics.median(children[:85]) if completed else None,
            "m1_max_abs_difference": m1_difference, "m3_max_abs_difference": m3_difference,
            "fallback_count": sum(bool(result.get("fallback_reason")) for result in results if result is not None),
            "child_pids": sorted(child_pids), "parent_pids": sorted(parent_pids), "policy_violations": sorted(violations)}


def validate_plan(plan, source_rows):
    expected = {"experiment_id": "EXP-079", "attempt": 3, "source_job": SOURCE_JOB, "source_snapshot_sha256": SOURCE_HASH,
                "previous_attempt_archive_sha256": PREVIOUS_ARCHIVE_HASH,
                "previous_attempt_verification_sha256": PREVIOUS_VERIFICATION_HASH,
                "source_verification_sha256": SOURCE_VERIFICATION_HASH, "rounds": 3, "modes": list(MODES),
                "planned_jobs": 9, "events_per_job": 340, "planned_events": 3060,
                "max_seconds": 1800, "max_readiness_seconds": 60, "readiness_samples": 10}
    close(plan, expected, "plan_contract")
    close(plan.get("source_rows"), validate_source_rows(source_rows), "plan_source_mapping")
    require(plan.get("source_logical_sha256") == sha(canonical(source_rows)), "source_logical_identity")
    payload = "\n".join(canonical({"id": f"source-{row['ordinal']}", "text": row["record"]["model_input_text"]}) for row in source_rows) + "\n"
    require(plan.get("payload_sha256") == sha(payload) and len(payload.encode()) <= 5*MIB, "payload_identity")
    return payload


def verify_readiness_attempts(attempts, jobs, samples, *, allow_unsubmitted_ready=False):
    require(isinstance(attempts, list) and len(jobs) <= len(attempts) <= min(9, len(jobs)+1), "readiness_attempt_count")
    for index, attempt in enumerate(attempts):
        require(isinstance(attempt, dict) and attempt.get("round") == index//3+1 and attempt.get("mode") == MODES[index%3]
                and attempt.get("status") in {"Ready", "NotReady"}, "readiness_attempt_identity")
        start, end = attempt.get("started_monotonic"), attempt.get("ended_monotonic")
        require(finite(start) and finite(end) and start <= end, "readiness_attempt_clock")
        observed = attempt.get("observed_sample_indices")
        require(isinstance(observed, list) and all(type(value) is int and 0 <= value < len(samples) for value in observed)
                and observed == sorted(set(observed)), "readiness_observed_indices")
        require(all(samples[value]["monotonic"] >= start and samples[value]["started_monotonic"] <= end for value in observed), "readiness_sample_window")
        if index < len(jobs):
            job = jobs[index]
            require(attempt["status"] == "Ready" and attempt.get("readiness_indices") == job.get("readiness_indices")
                    and job.get("readiness_started_monotonic") == start and job.get("readiness_ended_monotonic") == end,
                    "submission_without_ready_attempt")
        else:
            require(index == len(attempts)-1 and (attempt["status"] == "NotReady" or allow_unsubmitted_ready), "unused_ready_attempt")
    return all(attempt["ended_monotonic"]-attempt["started_monotonic"] <= 60+1e-6 for attempt in attempts)


def analyze(plan, run, jobs, source_rows, samples, process_events, service):
    payload = validate_plan(plan, source_rows)
    require(run.get("experiment_id") == "EXP-079" and run.get("status") in {"Completed", "Stopped", "NotReady"}, "run_status_contract")
    require(run.get("planned_jobs") == 9 and run.get("planned_events") == 3060, "run_plan_counts")
    require(finite(run.get("started_monotonic")) and finite(run.get("ended_monotonic")), "run_clock_schema")
    close(run.get("elapsed_seconds"), run["ended_monotonic"]-run["started_monotonic"], "run_elapsed_mismatch")
    require(all(run["started_monotonic"] <= sample.get("started_monotonic", -1) <= sample.get("monotonic", -1) <= run["ended_monotonic"]
                for sample in samples), "run_monitor_clock_coverage")
    entries = run.get("jobs")
    require(isinstance(entries, list) and len(entries) <= 9 and len({entry.get("id") for entry in entries}) == len(entries), "submitted_job_count")
    require(set(jobs) == {entry.get("id") for entry in entries}, "database_job_set")
    attempts = run.get("readiness_attempts", [])
    cleanup = run.get("cleanup") or {}
    recovery = cleanup.get("submission_recovery") or {}
    allow_unsubmitted = cleanup.get("error_code") == "submission_identity_unconfirmed" and recovery.get("candidate_count") == 0
    ready_timeout_gate = verify_readiness_attempts(attempts, entries, samples, allow_unsubmitted_ready=allow_unsubmitted)
    summaries, third_reference, fingerprints = [], {}, set()
    pooled, accepted = {}, 0
    for index, entry in enumerate(entries):
        require(entry.get("round") == index//3+1 and entry.get("mode") == MODES[index%3], "job_schedule")
        job = jobs[entry["id"]]
        require(job.get("state") in {"completed", "completed_with_fallback", "failed", "cancelled"}, "job_not_terminal")
        require(entry.get("status") == job["state"] and entry.get("completed_items") == job.get("completed_items")
                and entry.get("total_items") == job.get("total_items") and entry.get("snapshot_hash") == job.get("snapshot_hash")
                and entry.get("error_code") == job.get("error_code"), "entry_database_identity")
        request = job.get("request")
        require(isinstance(request, dict) and request.get("source") == "upload" and request.get("mode") == entry["mode"]
                and request.get("max_qwen_calls") == {"m1_only": 0, "research": 500, "demo": 20}[entry["mode"]]
                and request.get("audit_rate") == 0 and request.get("seed") == 42, "job_request_contract")
        require(job.get("manifest", {}).get("file_sha256") == sha(payload)
                and job["manifest"].get("filename") == "exp079-snapshot.jsonl", "upload_payload_manifest")
        for row in job["items"]:
            record = row["record"]
            require(record.get("source") == "upload" and record.get("site") == "upload" and record.get("object_type") == "row"
                    and record.get("source_payload_raw", {}).get("id") == f"source-{row['ordinal']}"
                    and record.get("provenance", {}).get("file_sha256") == sha(payload)
                    and record["provenance"].get("row_number") == row["ordinal"]+1, "uploaded_occurrence_identity")
        summary = recompute_job(job, source_rows, entry["mode"], third_reference)
        if summary["parent_pids"]:
            require(summary["parent_pids"] == [service["pid"]], "receipt_service_pid_mismatch")
        for row in job["items"]:
            if row["result"] is not None:
                fingerprint = row["result"].get("fingerprint")
                require(isinstance(fingerprint, str) and re.fullmatch(r"[a-f0-9]{64}", fingerprint), "result_fingerprint")
                fingerprints.add(fingerprint)
        require(len(fingerprints) <= 1, "model_fingerprint_changed")
        if entry.get("summary") is not None:
            require(summary["completed"], "summary_claims_incomplete_job")
            expected = {"events": 340, "schema_valid": summary["acknowledged_events"], "cost": summary["acknowledged_cost"],
                        "fallback_count": summary["fallback_count"], "latency_ms": summary["latency_ms"],
                        "child_current_rss_median_bytes": summary["child_median_bytes"],
                        "child_current_rss_peak_bytes": summary["child_current_rss_peak_bytes"],
                        "parent_current_rss_peak_bytes": summary["peak_parent_rss_bytes"],
                        "child_reported_peak_rss_bytes": summary["child_reported_peak_rss_bytes"],
                        "mlx_peak_bytes": summary["mlx_peak_bytes"], "child_first85_last85_ratio": summary["child_plateau_ratio"]}
            close(entry["summary"], expected, "producer_summary_mismatch")
        if entry.get("cost_complete") is True:
            require(summary["completed"] and entry.get("summary") is not None and entry.get("normal_exit") is True, "false_completion_claim")
            accepted += 1
        elif "acknowledged_results" in entry:
            require(entry.get("acknowledged_results") == summary["acknowledged_events"] and entry.get("unacknowledged_attempts") is None, "partial_unknown_cost_contract")
            close(entry.get("acknowledged_cost_lower_bound"), summary["acknowledged_cost"], "partial_cost_mismatch")
        if "elapsed_seconds" in entry:
            close(entry["elapsed_seconds"], entry.get("ended_monotonic", 0)-entry["started_monotonic"], "job_elapsed_mismatch")
        summary.update(id=entry["id"], mode=entry["mode"], round=entry["round"], status=job["state"], elapsed_seconds=entry.get("elapsed_seconds"))
        summaries.append(summary)
        if summary["completed"]:
            pooled[(entry["mode"], entry["round"])] = summary["child_median_bytes"]
    require(run.get("completed_jobs") == accepted, "driver_completion_count")
    worker_errors = sum(job.get("error_code") == "worker_failed" for job in jobs.values())
    require(type(run.get("driver_unhandled_errors")) is int and run["driver_unhandled_errors"] >= 0
            and run.get("worker_unhandled_errors") == worker_errors
            and run.get("unhandled_errors") == worker_errors+run["driver_unhandled_errors"], "unhandled_error_count")
    safety = verify_safety(samples, process_events, service, entries, elapsed_seconds=run["elapsed_seconds"])
    safety["readiness_timeout_gate"] = ready_timeout_gate
    cleanup_gate, cleanup_seconds = True, None
    if cleanup:
        start, end = cleanup.get("started_monotonic"), cleanup.get("ended_monotonic")
        require(finite(start) and finite(end) and start <= end and cleanup.get("max_seconds") == 15, "run_cleanup_clock_schema")
        cleanup_seconds = end-start
        cleanup_gate = cleanup_seconds <= 15+1e-6 and cleanup.get("models_absent_confirmed") is True
        if cleanup.get("job_id") is not None:
            require(entries and cleanup["job_id"] == entries[-1]["id"] and entries[-1].get("cleanup") == cleanup, "run_cleanup_job_binding")
    safety.update(run_cleanup_seconds=cleanup_seconds, run_cleanup_gate=cleanup_gate)
    safety["gate_passed"] = safety["gate_passed"] and ready_timeout_gate and cleanup_gate
    for summary, exit_info in zip(summaries, safety["exits"]):
        keys = exit_info["process_keys"]
        require(all(any(key.startswith(f"{pid}|") for key in keys) for pid in summary["child_pids"]), "receipt_event_pid_mismatch")
    completed = sum(summary["completed"] for summary in summaries)
    all_complete = len(entries) == completed == accepted == 9
    policy_gate = not any(summary["policy_violations"] for summary in summaries)
    complete = (all_complete and policy_gate and safety["gate_passed"] and run["status"] == "Completed"
                and run.get("failure_code") is None and run.get("unhandled_errors") == 0)
    cross = [{"mode": mode, "round3_over_round1": pooled[(mode, 3)]/pooled[(mode, 1)] if (mode, 1) in pooled and (mode, 3) in pooled else None,
              "descriptive_only": True} for mode in MODES]
    return {"planned_jobs": 9, "submitted_jobs": len(entries), "completed_jobs": completed,
            "completed_jobs_by_mode": {mode: sum(row["completed"] and row["mode"] == mode for row in summaries) for mode in MODES},
            "driver_completed_jobs": accepted, "planned_events": 3060,
            "verified_acknowledged_events": sum(row["acknowledged_events"] for row in summaries),
            "jobs": summaries, "m3_distinct_inputs_with_results": len(third_reference), "cross_job_plateau": cross,
            "safety": safety, "gates": {"all_nine_jobs": all_complete, "mode_policy": policy_gate, "safety": safety["gate_passed"]},
            "exp079_complete": bool(complete), "operational_state": "safe-to-continue" if complete else "stop-required",
            "claim_boundary": "Nine bounded local replay jobs only; plateau descriptive, unknown attempts not zero, no SLA, external-gold or whole-machine causal claim."}


def regular_file(path):
    path = Path(path)
    require(not any(parent.is_symlink() for parent in (path, *path.parents)), "artifact_symlink")
    require(path.is_file() and stat.S_ISREG(path.stat().st_mode), "artifact_not_regular")
    return sha(path.read_bytes())


def source_path(name, root=None):
    value = Path(name)
    require(not value.is_absolute() and ".." not in value.parts and bool(value.parts), "relative_source_path")
    return (ROOT if root is None else root) / value


def check_environment(plan, run, claim):
    for key in ("experiment_id", "tier", "started_at", "started_monotonic", "plan_sha256", "command", "cwd", "environment",
                "git_commit", "git_dirty", "git_status_porcelain", "training", "gold_accessed", "source_network_fetched"):
        require(key in claim and run.get(key) == claim[key], "run_claim_binding")
    require(claim["tier"] == "Major" and claim["git_dirty"] is bool(claim["git_status_porcelain"])
            and all(claim[name] is False for name in ("training", "gold_accessed", "source_network_fetched")), "run_access_attestation")
    environment = run["environment"]
    require(isinstance(environment, dict), "environment_schema")
    lock = environment.get("requirements_lock", {})
    require(lock.get("path") == "requirements-lock.txt" and lock.get("sha256") == plan["sources"]["requirements-lock.txt"], "environment_lock_binding")
    pinned = dict(line.split("==", 1) for line in source_path(lock["path"]).read_text().splitlines() if line.strip() and not line.startswith("#"))
    require(lock.get("packages") == pinned and environment.get("website", {}).get("packages") == pinned, "website_packages_binding")
    model = environment.get("model_config", {})
    require(model.get("path") == "experiments/stack-overflow-emotion-gold/oof-router/runs/exp-066-headless-runtime-parity/attempt-2/frozen-sources/config.json"
            and model.get("sha256") == "106db4b86614ac70c84f04a322b046bc1049686099c590997955120993bb9983", "model_config_contract")
    model_path = source_path(model["path"], ROOT.parent)
    require(regular_file(model_path) == model["sha256"]
            and LOCAL.strict_json(model_path.read_text())["environment"] == environment.get("model_runtime"), "frozen_environment_binding")
    hardware = environment.get("hardware", {})
    require(type(hardware.get("physical_memory_bytes")) is int and hardware["physical_memory_bytes"] > 0
            and type(hardware.get("logical_cpus")) is int and hardware["logical_cpus"] > 0
            and isinstance(hardware.get("cpu_model"), str) and bool(hardware["cpu_model"]), "hardware_metadata")


def service_absent(service):
    result = subprocess.run(["/bin/ps", "-p", str(service["pid"]), "-o", "lstart="], capture_output=True, text=True,
                            timeout=3, env={**os.environ, "LC_ALL": "C"})
    require(result.returncode in (0, 1), "service_state_unknown")
    if result.returncode == 1 and not result.stdout.strip():
        return True
    return " ".join(result.stdout.split()) != service["start_time"]


def check_job_log(lines, entries):
    mapping = {entry["id"]: entry for entry in entries}
    grouped = {}
    for line in lines:
        require(isinstance(line, dict) and line.get("id") in mapping, "job_log_identity")
        entry = mapping[line["id"]]
        require(all(line.get(key) == entry.get(key) for key in ("round", "mode", "started_monotonic", "readiness_indices")), "job_log_submission_binding")
        grouped.setdefault(line["id"], []).append(line)
    require(set(grouped) == set(mapping), "job_log_coverage")
    for identifier, rows in grouped.items():
        require(rows[0].get("status") in {"submitted", "submission_ack_lost"} and len(rows) <= 2, "job_log_order")
        if rows[0]["status"] == "submission_ack_lost":
            require(rows[0].get("http_submission_acknowledged") is False
                    and rows[0].get("recovered_for_cancellation_only") is True, "lost_ack_log_contract")
        if len(rows) == 2:
            require(rows[-1] == mapping[identifier], "job_log_terminal_binding")
        else:
            require(mapping[identifier].get("cost_complete") is not True, "completed_job_log_missing")


def main():
    target = RUN / "verification.json"
    require(not target.exists() and not any(path.is_symlink() for path in (target, *target.parents)), "verification_exists_or_symlink")
    names = ("plan.json", "run.json", "run-claim.json", "samples.jsonl", "process-events.jsonl", "service.json", "jobs.jsonl", "stdout.log", "bench/jobs.sqlite3")
    before = {name: regular_file(RUN / name) for name in names}
    require(not (RUN / "bench/jobs.sqlite3-wal").exists() or (RUN / "bench/jobs.sqlite3-wal").stat().st_size == 0, "bench_wal_not_sealed")
    plan, run, claim, service = (LOCAL.strict_json((RUN/name).read_text()) for name in ("plan.json", "run.json", "run-claim.json", "service.json"))
    require(service_absent(service), "isolated_service_still_running")
    report = {"experiment_id": "EXP-079", "attempt": 3, "status": "Failed", "exp079_complete": False,
              "operational_state": "stop-required", "verified_at": datetime.now(timezone.utc).isoformat(),
              "source_hashes": {"private/validation/exp-079/attempt-3/"+name: value for name, value in before.items()},
              "models_loaded": False, "producer_numerical_helpers_imported": False, "gold_accessed": False,
              "verifier_sha256": regular_file(Path(__file__))}
    try:
        require(run.get("plan_sha256") == before["plan.json"] == claim.get("plan_sha256"), "plan_hash_binding")
        for filename, field in (("samples.jsonl", "samples_sha256"), ("process-events.jsonl", "process_events_sha256"),
                                ("service.json", "service_sha256"), ("stdout.log", "stdout_sha256"), ("jobs.jsonl", "jobs_sha256")):
            require(run.get(field) == before[filename], "run_artifact_binding")
        require(plan.get("service_sha256") == before["service.json"], "plan_service_binding")
        require(service.get("experiment_id") == "EXP-079" and service.get("port") == 8789
                and service.get("root") == str(ROOT) and service.get("bench_root") == str(RUN/"bench"), "service_registered_scope")
        require(isinstance(plan.get("sources"), dict) and set(plan["sources"]) == DEPENDENCIES, "implementation_dependency_set")
        for name, digest in plan["sources"].items():
            require(regular_file(source_path(name)) == digest, "implementation_identity_drift")
        protocols = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols"
        require(regular_file(protocols/"exp-079-bounded-runtime-acceptance.md") == plan.get("protocol_sha256")
                and regular_file(protocols/"dec-phase-c1-bounded-operational-validation-v1.md") == plan.get("decision_sha256"), "protocol_identity_drift")
        require(regular_file(protocols/"exp-079-observer-correction-attempt-2.md") == plan.get("correction_sha256"), "observer_correction_identity")
        require(regular_file(protocols/"exp-079-reduced-background-attempt-3.md") == plan.get("reduced_background_sha256"), "reduced_background_protocol_identity")
        previous = ROOT/"private/validation/exp-079/attempt-2"
        require(regular_file(previous/"frozen-code.tar.gz") == plan.get("previous_attempt_archive_sha256") == PREVIOUS_ARCHIVE_HASH
                and regular_file(previous/"verification.json") == plan.get("previous_attempt_verification_sha256") == PREVIOUS_VERIFICATION_HASH,
                "previous_attempt_binding")
        check_environment(plan, run, claim)
        source_verification = ROOT / "private/validation/exp-076/attempt-3/verification.json"
        require(regular_file(source_verification) == SOURCE_VERIFICATION_HASH, "parent_verification_identity")
        parent = LOCAL.strict_json(source_verification.read_text())
        require(parent.get("status") == "Passed" and parent.get("exp076_verified") is True, "parent_not_verified")
        original = LOCAL.read_jobs(ROOT/"private/jobs.sqlite3", [SOURCE_JOB])[SOURCE_JOB]
        require(original.get("state") == "completed" and original.get("snapshot_hash") == SOURCE_HASH, "parent_job_identity")
        identifiers = [entry["id"] for entry in run.get("jobs", [])]
        with sqlite3.connect((RUN/"bench/jobs.sqlite3").as_uri()+"?mode=ro", uri=True) as db:
            all_ids = {row[0] for row in db.execute("SELECT id FROM jobs")}
        require(all_ids == set(identifiers), "unregistered_bench_job")
        jobs = LOCAL.read_jobs(RUN/"bench/jobs.sqlite3", identifiers)
        samples = [LOCAL.strict_json(line) for line in (RUN/"samples.jsonl").read_text().splitlines() if line]
        events = [LOCAL.strict_json(line) for line in (RUN/"process-events.jsonl").read_text().splitlines() if line]
        lines = [LOCAL.strict_json(line) for line in (RUN/"jobs.jsonl").read_text().splitlines() if line]
        check_job_log(lines, run.get("jobs", []))
        report.update(analyze(plan, run, jobs, original["items"], samples, events, service))
        require(all(regular_file(RUN/name) == digest for name, digest in before.items()), "artifact_changed_during_verification")
        require(all(regular_file(source_path(name)) == digest for name, digest in plan["sources"].items()), "dependency_changed_during_verification")
        report["status"] = "Passed"
    except Exception as error:
        code = str(error) if isinstance(error, (VerificationError, LOCAL.VerificationError)) else type(error).__name__
        report.update(status="Failed", exp079_complete=False, operational_state="stop-required",
                      error_code=code if re.fullmatch(r"[A-Za-z0-9_]{1,100}", code) else "verification_failed")
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)+"\n")
    print(json.dumps({key: report.get(key) for key in ("status", "exp079_complete", "operational_state", "error_code")}))
    return 0 if report["status"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
