"""Independent EXP-077 event, memory, replay and finite-workload gate verification."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "private/validation/exp-077/attempt-1"
COSTS = ("m1_attempts", "m3_attempts", "m3_succeeded", "m1_cache_hit", "m3_cache_hit", "audit_extra_calls")
MODES = ("m1_only", "research", "demo")
PHASES = ("warmup", "measured", "cache_tail")
SOURCE_JOB = "5ab3326150ee448ba326233264967d34"
SOURCE_HASH = "cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16"


def require(value, code):
    if not value:
        raise ValueError(code)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def median(values):
    ordered = sorted(values)
    require(bool(ordered), "missing_median_observations")
    half = len(ordered) // 2
    return ordered[half] if len(ordered) % 2 else (ordered[half-1] + ordered[half])/2


def latency_percentiles(values):
    sorted_values = sorted(values)
    result = {"n": len(values), "min": min(values), "max": max(values)}
    for name, probability in (("median",.5),("p90",.9),("p95",.95)):
        location = probability*(len(values)-1)
        left, right = math.floor(location), math.ceil(location)
        result[name] = sorted_values[left]*(1-(location-left))+sorted_values[right]*(location-left)
    return result


def close(observed, expected):
    if isinstance(expected, dict):
        require(isinstance(observed, dict) and set(expected) <= set(observed), "summary_keys")
        for key in expected:
            close(observed[key], expected[key])
    elif isinstance(expected, (list, tuple)):
        require(isinstance(observed, list) and len(observed) == len(expected), "summary_shape")
        for one, two in zip(observed, expected):
            close(one, two)
    elif type(expected) is float:
        require(type(observed) in (int, float) and math.isfinite(observed) and abs(observed-expected) <= 1e-9, "summary_number")
    else:
        require(observed == expected, "summary_value")


def load_job(database, identifier):
    require(database.is_file() and not any(p.is_symlink() for p in (database, *database.parents)), "database_source")
    with sqlite3.connect(database.as_uri()+"?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        value = connection.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone()
        require(value is not None, "missing_job")
        rows = [{"ordinal": row["ordinal"], "record": json.loads(row["record"]),
                 "result": json.loads(row["result"]) if row["result"] else None}
                for row in connection.execute("SELECT ordinal,record,result FROM items WHERE job_id=? ORDER BY ordinal", (identifier,))]
        return dict(value), rows


def validate_plan(plan, source_rows):
    require(len(source_rows) == 340 and [row["ordinal"] for row in source_rows] == list(range(340)), "source_row_alignment")
    require(sha(encoded([row["record"] for row in source_rows])) == SOURCE_HASH
            and sha(encoded(source_rows)) == plan["source_logical_sha256"], "source_snapshot_identity")
    metadata, unique = [], {}
    for row in source_rows:
        text = row["record"]["model_input_text"]
        value = {"source_ordinal": row["ordinal"], "input_sha256": sha(text), "characters": len(text),
                 "route_eligible": row["result"]["hypothetical_route"]}
        require(value["input_sha256"] == row["record"]["model_input_hash"] and type(value["route_eligible"]) is bool, "source_input_identity")
        metadata.append(value)
        unique.setdefault(value["input_sha256"], value)
    require(len(unique) == 338 and sum(row["route_eligible"] for row in metadata) == 25, "source_coverage_identity")
    longest = []
    for flag in (True, False):
        pool = [item for item in unique.values() if item["route_eligible"] is flag]
        pool.sort(key=lambda item: (-item["characters"], item["source_ordinal"]))
        require(len(pool) >= 8, "warmup_pool")
        longest.extend(item["source_ordinal"] for item in pool[:8])
    require(plan["source_rows"] == metadata and plan["warmup_ordinals"] == longest, "source_selection_identity")
    indices = [("warmup", index) for index in longest] + [("measured", index) for index in range(340)] + [("cache_tail", index) for index in range(64)]
    expected = [{"ordinal": ordinal, "phase": phase, **metadata[index]} for ordinal, (phase, index) in enumerate(indices)]
    require(plan["events"] == expected, "event_schedule_identity")
    content = "\n".join(encoded({"id": f"event-{ordinal}-{phase}-source-{index}",
                                 "text": source_rows[index]["record"]["model_input_text"]})
                           for ordinal, (phase, index) in enumerate(indices)) + "\n"
    require(sha(content) == plan["payload_sha256"] and len(content.encode()) <= 5*1024**2, "payload_identity")
    return expected


def rss_observation(sample):
    require(sample.get("status") == "observed", "rss_unknown")
    mapping = {}
    for line in sample["raw_ps"].splitlines():
        parts = line.split()
        require(len(parts) == 2 and all(part.isdigit() for part in parts), "rss_parse")
        require(int(parts[0]) not in mapping, "duplicate_rss_pid")
        mapping[int(parts[0])] = int(parts[1])*1024
    require(set(mapping) == {sample["child_pid"], sample["parent_pid"]}, "rss_pid_identity")
    require(mapping[sample["child_pid"]] == sample["child_current_rss_bytes"]
            and mapping[sample["parent_pid"]] == sample["parent_current_rss_bytes"] and min(mapping.values()) > 0, "rss_value_identity")
    return mapping[sample["child_pid"]], mapping[sample["parent_pid"]]


def vector(value, probability=False):
    require(isinstance(value, list) and len(value) == 6, "prediction_shape")
    require(all(type(number) in (int, float) and math.isfinite(number) and 0 <= number <= 1 for number in value), "prediction_range")
    if not probability:
        require(all(type(number) is int and number in (0, 1) for number in value), "prediction_binary")
    return value


def recompute_job(rows, events, mode, original, m3_reference):
    require(len(rows) == 420 and [row["ordinal"] for row in rows] == list(range(420)), "event_ordinal_alignment")
    groups = {phase: {"cost": {key: 0 for key in COSTS}, "child": [], "parent": [], "latency": []} for phase in PHASES}
    seen_first, seen_third, cumulative, pids, parent_pids = set(), set(), {key: 0 for key in COSTS}, set(), set()
    peak_mlx = 0
    for row, event in zip(rows, events):
        record, result = row["record"], row["result"]
        require(isinstance(result, dict), "missing_result")
        require(sha(record["model_input_text"]) == record["model_input_hash"] == event["input_sha256"], "model_input_changed")
        require(record["source_payload_raw"]["id"] == f"event-{event['ordinal']}-{event['phase']}-source-{event['source_ordinal']}", "occurrence_identity")
        first = vector(result["m1_probabilities"], True)
        first_decision = vector(result["m1_prediction"])
        baseline = original[event["source_ordinal"]]["result"]
        require(max(abs(a-b) for a,b in zip(first, baseline["m1_probabilities"])) <= 1e-6
                and first_decision == baseline["m1_prediction"], "m1_replay_mismatch")
        require(result["hypothetical_route"] is event["route_eligible"], "route_replay_mismatch")
        routed = event["route_eligible"] and mode != "m1_only"
        require(result["route_requested"] is routed, "requested_route_mismatch")
        hashed = event["input_sha256"]
        cost = {key: 0 for key in COSTS}
        cost.update(m1_attempts=int(hashed not in seen_first), m1_cache_hit=int(hashed in seen_first))
        seen_first.add(hashed)
        use_third, fallback = False, None
        if routed:
            if hashed in seen_third:
                cost["m3_cache_hit"], use_third = 1, True
            elif mode == "demo" and cumulative["m3_attempts"] >= 20:
                fallback = "m3_budget_exhausted"
            else:
                cost["m3_attempts"] = cost["m3_succeeded"] = 1
                seen_third.add(hashed)
                use_third = True
        require(result["used_path"] == ("m3" if use_third else "m1") and result.get("fallback_reason") == fallback, "mode_or_runtime_failure")
        require(result.get("fallback") is bool(fallback), "fallback_flag")
        selected = first_decision
        if use_third:
            third = vector(result["m3_probabilities"], True)
            third_decision = vector(result["m3_prediction"])
            if hashed not in m3_reference:
                m3_reference[hashed] = (third, third_decision)
            reference, decisions = m3_reference[hashed]
            require(max(abs(a-b) for a,b in zip(third, reference)) <= 1e-6 and third_decision == decisions, "m3_replay_mismatch")
            selected = third_decision
        else:
            require(result["m3_probabilities"] is None and result["m3_prediction"] is None, "unrequested_m3_output")
        require(vector(result["prediction"]) == selected and result["neutral"] is (not any(selected)), "final_prediction_mismatch")
        bucket = groups[event["phase"]]
        for key in COSTS:
            require(type(result["counters"].get(key)) is int and result["counters"][key] == cost[key], "component_cost_mismatch")
            cumulative[key] += cost[key]
            bucket["cost"][key] += cost[key]
        require(result["cumulative_counters"] == cumulative, "cumulative_cost_mismatch")
        child, parent = rss_observation(result["telemetry"])
        pids.add(result["telemetry"]["child_pid"]); parent_pids.add(result["telemetry"]["parent_pid"])
        bucket["child"].append(child); bucket["parent"].append(parent)
        latency = result["latency_ms"]
        require(type(latency) in (int, float) and math.isfinite(latency) and latency >= 0, "invalid_latency")
        bucket["latency"].append(latency)
        peak_mlx = max(peak_mlx, result["resources"]["mlx_peak_bytes"])
    require(len(pids) == len(parent_pids) == 1, "single_child_process_contract")
    summary = {"phases": {}, "schema_valid": 420, "peak_child_rss_bytes": max(max(group["child"]) for group in groups.values()),
               "peak_parent_rss_bytes": max(max(group["parent"]) for group in groups.values()), "mlx_peak_bytes": peak_mlx}
    for phase, bucket in groups.items():
        summary["phases"][phase] = {"events": len(bucket["latency"]), "cost": bucket["cost"],
                                     "mean_item_ms": sum(bucket["latency"])/len(bucket["latency"]), "median_item_ms": median(bucket["latency"]),
                                     "child_median_bytes": median(bucket["child"]), "parent_median_bytes": median(bucket["parent"]),
                                     "latency_ms": latency_percentiles(bucket["latency"])}
    for process in ("child", "parent"):
        values = groups["measured"][process]
        summary[process+"_plateau_ratio"] = median(values[-85:])/median(values[:85])
    return summary, groups, next(iter(pids)), next(iter(parent_pids))


def system_summary(samples):
    unknown = critical = warnings = invalid_intervals = streak = longest = 0
    deltas, rates = [], []
    for index, sample in enumerate(samples):
        if sample.get("status") != "observed":
            unknown += 1
            streak = 0
            continue
        require(sample["pressure_raw"].strip() in {"1", "2", "4"} and int(sample["pressure_raw"].strip()) == sample["pressure_level"], "pressure_raw_mismatch")
        raw = sample["vm_stat_raw"]
        page = int(re.search(r"page size of (\d+) bytes", raw)[1])
        incoming = int(re.search(r"^Swapins:\s*(\d+)", raw, re.MULTILINE)[1])
        outgoing = int(re.search(r"^Swapouts:\s*(\d+)", raw, re.MULTILINE)[1])
        require((page, incoming, outgoing) == (sample["page_size"], sample["swapins"], sample["swapouts"]), "swap_raw_mismatch")
        critical += sample["pressure_level"] == 4
        warnings += sample["pressure_level"] == 2
        if not index:
            continue
        previous = samples[index-1]
        interval = sample["monotonic"]-previous["monotonic"]
        if (previous.get("status") != "observed" or not 0 < interval <= 3 or page != previous["page_size"]
                or incoming < previous["swapins"] or outgoing < previous["swapouts"]):
            invalid_intervals += 1
            streak = 0
            continue
        delta = ((incoming-previous["swapins"])+(outgoing-previous["swapouts"]))*page
        rate = delta/interval
        deltas.append(delta); rates.append(rate)
        streak = streak+1 if rate >= 100*1024**2 else 0
        longest = max(longest, streak)
    return {"samples": len(samples), "unknown_samples": unknown, "critical_samples": critical, "warning_samples": warnings,
            "invalid_intervals": invalid_intervals, "swap_delta_bytes": sum(deltas), "maximum_swap_bytes_per_second": max(rates) if rates else None,
            "longest_thrashing_intervals": longest, "thrashing": longest >= 3,
            "gate_passed": len(samples) >= 2 and unknown == critical == invalid_intervals == 0 and longest < 3,
            "initial_swap_occupancy_used_as_failure": False}


def analyze(plan, run, bundles, source_rows, samples):
    events = validate_plan(plan, source_rows)
    entries = run["jobs"]
    require(len(entries) <= 36 and len({entry["id"] for entry in entries}) == len(entries), "job_count_identity")
    summaries, processes, parents, pooled, third_reference = [], set(), set(), {}, {}
    successful = 0
    for index, entry in enumerate(entries):
        require(entry["mode"] == MODES[index % 3] and entry["round"] == index//3+1, "job_order")
        job, rows = bundles[entry["id"]]
        if job["state"] not in {"completed", "completed_with_fallback"}:
            continue
        require(len(rows) == job["total_items"] == job["completed_items"] == 420, "job_event_completion")
        require(sha(encoded([row["record"] for row in rows])) == job["snapshot_hash"] == entry["snapshot_hash"], "job_snapshot_identity")
        summary, groups, child, parent = recompute_job(rows, events, entry["mode"], source_rows, third_reference)
        close(entry["summary"], summary)
        close(entry["elapsed_seconds"], entry["ended_monotonic"]-entry["started_monotonic"])
        require(child not in processes, "child_process_reused")
        processes.add(child); parents.add(parent)
        for phase in PHASES:
            for process in ("child", "parent"):
                pooled[(entry["mode"], entry["round"], phase, process)] = groups[phase][process]
        summaries.append({"id": entry["id"], "round": entry["round"], "mode": entry["mode"], "elapsed_seconds": entry["elapsed_seconds"], **summary})
        successful += 1
    cross = []
    if successful == 36:
        for mode in MODES:
            for phase in PHASES:
                item = {"mode": mode, "phase": phase, "primary": phase == "measured"}
                for process in ("child", "parent"):
                    first = [value for round_index in (1,2,3) for value in pooled[(mode,round_index,phase,process)]]
                    last = [value for round_index in (10,11,12) for value in pooled[(mode,round_index,phase,process)]]
                    item[process+"_ratio"] = median(last)/median(first)
                cross.append(item)
    system = system_summary(samples)
    require(len(parents) <= 1, "api_process_changed")
    hard_memory = all(item["peak_child_rss_bytes"] <= 12*1024**3 and item["peak_parent_rss_bytes"] <= 1024**3
                      and item["mlx_peak_bytes"] <= 10_000_000_000 for item in summaries)
    within = successful == 36 and all(item["child_plateau_ratio"] <= 1.05 for item in summaries)
    between = successful == 36 and all(item["child_ratio"] <= 1.05 for item in cross if item["primary"])
    base_gate = (run["status"] == "Completed" and not run["failure_code"] and run["unhandled_errors"] == 0 and successful/36 >= .995 and system["gate_passed"]
                 and hard_memory and run["elapsed_seconds"] <= 3600 and all(item["phases"]["measured"]["cost"]["m1_attempts"] > 0 for item in summaries))
    return {"planned_jobs": 36, "completed_jobs": successful, "completion_rate": successful/36,
            "unhandled_errors": run["unhandled_errors"],
            "planned_events": 15120, "verified_events": successful*420, "schema_valid_rate_on_verified_events": 1.0 if successful else None,
            "m3_distinct_inputs_observed": len(third_reference), "jobs": summaries, "cross_job_plateau": cross, "system": system,
            "gates": {"base": base_gate, "within_job_child_plateau": within, "cross_job_measured_child_plateau": between},
            "operational_state": "safe-to-continue" if base_gate else "stop-required",
            "soak_gate_passed": base_gate and within and between,
            "claim_boundary": "Finite 36-job replay study only; no SLA or external-gold claim. Parent RSS ratios descriptive; system pressure includes other processes."}


def main():
    target = RUN / "verification.json"
    require(not target.exists() and not any(path.is_symlink() for path in (target, *target.parents)), "verification_exists_or_symlink")
    paths = [RUN/"plan.json", RUN/"run.json", RUN/"system-samples.jsonl", RUN/"bench/jobs.sqlite3", RUN/"run-claim.json", RUN/"stdout.log"]
    before = {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in paths}
    result = {"experiment_id": "EXP-077", "status": "Failed", "verified_at": datetime.now(timezone.utc).isoformat(),
              "source_hashes": before, "verifier_sha256": sha(Path(__file__).read_bytes()), "models_loaded": False,
              "producer_numerical_helpers_imported": False, "gold_accessed": False}
    try:
        plan, run = json.loads(paths[0].read_text()), json.loads(paths[1].read_text())
        claim = json.loads(paths[4].read_text())
        require(sha(paths[0].read_bytes()) == run["plan_sha256"] and plan["source_job"] == SOURCE_JOB, "plan_binding")
        require(plan["rounds"] == 12 and plan["modes"] == list(MODES) and plan["planned_jobs"] == 36
                and plan["planned_events"] == 15120, "planned_workload_contract")
        require(sha(paths[2].read_bytes()) == run["system_samples_sha256"], "system_sample_binding")
        require(sha(paths[5].read_bytes()) == run["stdout_sha256"], "stdout_binding")
        require(claim["environment"] == run["environment"] and claim["git_dirty"] == bool(claim["git_status_porcelain"])
                and claim["git_status_porcelain"] == run["git_status_porcelain"], "environment_claim_binding")
        environment = run["environment"]
        lock = ROOT/environment["requirements_lock"]["path"]
        require(sha(lock.read_bytes()) == environment["requirements_lock"]["sha256"] == plan["sources"]["requirements-lock.txt"], "requirements_lock_binding")
        require(environment["website"]["packages"] == environment["requirements_lock"]["packages"], "website_environment_binding")
        model_config = ROOT.parent/environment["model_config"]["path"]
        require(sha(model_config.read_bytes()) == environment["model_config"]["sha256"]
                and json.loads(model_config.read_text())["environment"] == environment["model_runtime"], "model_environment_binding")
        require(environment["hardware"]["physical_memory_bytes"] > 0 and environment["hardware"]["logical_cpus"] > 0
                and environment["hardware"]["cpu_model"] and environment["website"]["platform"], "hardware_metadata_binding")
        close(run["elapsed_seconds"], run["ended_monotonic"]-run["started_monotonic"])
        require(all(sha((ROOT/name).read_bytes()) == hashed for name,hashed in plan["sources"].items()), "implementation_identity")
        protocol = ROOT.parent/"experiments/stack-overflow-emotion-gold/protocols/exp-077-runtime-soak-v2.md"
        require(sha(protocol.read_bytes()) == plan["protocol_sha256"], "protocol_identity")
        _, source_rows = load_job(ROOT/"private/jobs.sqlite3", SOURCE_JOB)
        require(sha((ROOT/"private/validation/exp-076/attempt-3/verification.json").read_bytes()) == plan["source_verification_sha256"], "source_verification_identity")
        bundles = {entry["id"]: load_job(paths[3], entry["id"]) for entry in run["jobs"]}
        samples = [json.loads(line) for line in paths[2].read_text().splitlines() if line]
        result.update(analyze(plan, run, bundles, source_rows, samples))
        require(all(sha(path.read_bytes()) == before[str(path.relative_to(ROOT))] for path in paths), "artifact_changed")
        result.update(status="Passed", exp077_complete=run["status"] == "Completed" and result["gates"]["base"],
                      conclusion="stable_within_registered_bounds" if result["soak_gate_passed"] else "registered_runtime_gate_not_met")
    except Exception as error:
        result.update(error_code=str(error) if isinstance(error, ValueError) else type(error).__name__, exp077_complete=False, operational_state="stop-required")
    descriptor = os.open(target, os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)+"\n")
    print(json.dumps({key: result.get(key) for key in ("status", "exp077_complete", "soak_gate_passed", "conclusion")}))
    return 0 if result["status"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
