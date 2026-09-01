"""Synthetic EXP-079 verification fixtures; never load models or a real database."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import statistics
from unittest.mock import patch

import pytest

from topicweb.core import aggregate, extended_views, make_record

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("test_exp079_verifier", ROOT / "scripts/verify_bounded_runtime.py")
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)
MIB = 1024**2


def source_rows():
    rows = []
    for index in range(340):
        unique = index if index < 338 else index-313
        text = f"Bounded synthetic technical input {unique}."
        record = make_record(source="stackexchange", site="stackoverflow", object_type="question",
                             source_object_id=str(1000+index), model_input_text=text,
                             source_payload_raw={"body_markdown": text})
        rows.append({"ordinal": index, "record": record,
                     "result": {"m1_probabilities": [.7, .2, .1, .1, .1, .1], "m1_prediction": [1, 0, 0, 0, 0, 0],
                                "hypothetical_route": unique < 25}})
    return rows


def process(pid, parent=100, minute=0, rss=2*MIB):
    started = f"Mon Aug 31 10:{minute:02d}:00 2026"
    return {"pid": pid, "ppid": parent, "current_rss_bytes": rss, "start_time": started,
            "process_key": f"{pid}|{started}", "comm": "Python"}


def raw_process(row):
    return f" {row['pid']} {row['ppid']} {row['current_rss_bytes']//1024} {row['start_time']} /usr/bin/Python"


def fixture(count=9):
    original = source_rows()
    snapshot = VERIFY.sha(VERIFY.canonical([row["record"] for row in original]))
    payload = "\n".join(VERIFY.canonical({"id": f"source-{row['ordinal']}", "text": row["record"]["model_input_text"]}) for row in original)+"\n"
    payload_hash = VERIFY.sha(payload)
    plan = {"experiment_id": "EXP-079", "attempt": 3, "source_job": VERIFY.SOURCE_JOB, "source_snapshot_sha256": snapshot,
            "previous_attempt_archive_sha256": VERIFY.PREVIOUS_ARCHIVE_HASH,
            "previous_attempt_verification_sha256": VERIFY.PREVIOUS_VERIFICATION_HASH,
            "source_verification_sha256": VERIFY.SOURCE_VERIFICATION_HASH,
            "source_rows": [{"ordinal": row["ordinal"], "input_sha256": row["record"]["model_input_hash"], "route_eligible": row["result"]["hypothetical_route"]} for row in original],
            "source_logical_sha256": VERIFY.sha(VERIFY.canonical(original)), "payload_sha256": payload_hash,
            "rounds": 3, "modes": list(VERIFY.MODES), "planned_jobs": 9, "events_per_job": 340, "planned_events": 3060,
            "max_seconds": 1800, "max_readiness_seconds": 60, "readiness_samples": 10}
    service = {**process(100, 1, rss=MIB), "experiment_id": "EXP-079", "port": 8789}
    samples, events, entries, attempts, jobs, seen = [], [], [], [], {}, set()

    def sample(models=(), job_id=None, pressure=1):
        index = len(samples)
        started = index * 1.2
        seen.update(row["process_key"] for row in models)
        live = {row["process_key"] for row in models}
        samples.append({"index": index, "job_id": job_id, "started_monotonic": started, "monotonic": started+.2,
                        "system": {"status": "observed", "monotonic": started+.1, "pressure_level": pressure,
                                   "pressure_raw": str(pressure)+"\n", "page_size": 4096, "swapins": 1000, "swapouts": 2000,
                                   "vm_stat_raw": "Mach Virtual Memory Statistics: (page size of 4096 bytes)\nSwapins: 1000.\nSwapouts: 2000.\n"},
                        "disk_free_bytes": 2*1024*MIB,
                        "processes": {"status": "observed", "parent": {key: service[key] for key in ("pid", "ppid", "current_rss_bytes", "start_time", "process_key", "comm")},
                                      "models": list(models), "orphan_models": [], "seen_model_keys": sorted(seen),
                                      "absent_model_keys": sorted(seen-live), "selected_ps": [raw_process(service), *(raw_process(row) for row in models)]}})
        return index

    sample()
    for number in range(count):
        mode, round_index, identifier = VERIFY.MODES[number % 3], number//3+1, f"fixture-job-{number}"
        ready_start = samples[-1]["monotonic"]+.05
        indices = [sample() for _ in range(10)]
        ready_end = samples[-1]["monotonic"]+.005
        start = ready_end+.01
        model = process(201+number, minute=number+1)
        def event(kind, when, code=None, normal=False):
            events.append({"type": kind, "job_id": identifier, "pid": None if kind == "constructor_started" else model["pid"],
                           "process_key": None if kind == "constructor_started" else model["process_key"],
                           "monotonic": when, "returncode": code, "normal_exit": normal})
        event("constructor_started", start+.01)
        event("ready", start+.05)
        sample([model], identifier); sample([model], identifier)
        exit_time = samples[-1]["monotonic"]+.05
        event("process_exit", exit_time, 0); event("final_gate_passed", exit_time+.01, 0, True)
        end = exit_time+.02
        absent_index = sample()
        records, results, cumulative, seen_inputs, seen_third = [], [], {key: 0 for key in VERIFY.COSTS}, set(), set()
        for index, old in enumerate(original):
            text, hashed = old["record"]["model_input_text"], old["record"]["model_input_hash"]
            record = make_record(source="upload", site="upload", object_type="row", source_object_id=f"{payload_hash}:{index+1}",
                                 model_input_text=text, source_payload_raw={"id": f"source-{index}", "text": text},
                                 provenance={"file_sha256": payload_hash, "filename": "exp079-snapshot.jsonl", "row_number": index+1})
            requested = old["result"]["hypothetical_route"] and mode != "m1_only"
            costs = {key: 0 for key in VERIFY.COSTS}
            costs["m1_attempts"], costs["m1_cache_hit"] = int(hashed not in seen_inputs), int(hashed in seen_inputs)
            seen_inputs.add(hashed)
            third, fallback = False, None
            if requested:
                if mode == "demo" and cumulative["m3_attempts"] >= 20:
                    fallback = "m3_budget_exhausted"
                else:
                    third = True
                    costs["m3_attempts"] = costs["m3_succeeded"] = int(hashed not in seen_third)
                    costs["m3_cache_hit"] = int(hashed in seen_third)
                    seen_third.add(hashed)
            for key in VERIFY.COSTS:
                cumulative[key] += costs[key]
            selected = [0, 1, 0, 0, 0, 0] if third else [1, 0, 0, 0, 0, 0]
            result = {"prediction": selected, "active_labels": ["joy" if third else "love"], "neutral": False,
                      "m1_probabilities": old["result"]["m1_probabilities"], "m1_prediction": old["result"]["m1_prediction"],
                      "m3_probabilities": [.1, .8, .1, .1, .1, .1] if third else None,
                      "m3_prediction": [0, 1, 0, 0, 0, 0] if third else None,
                      "hypothetical_route": old["result"]["hypothetical_route"], "route_requested": requested,
                      "used_path": "m3" if third else "m1", "fallback": bool(fallback), "fallback_reason": fallback,
                      "counters": {**costs, "fallback_reason": fallback}, "cumulative_counters": dict(cumulative),
                      "latency_ms": 1.0, "fingerprint": "f"*64,
                      "resources": {"peak_rss_bytes": 3*MIB, "mlx_peak_bytes": 4*MIB if third else 0},
                      "telemetry": {"status": "observed", "monotonic": start+1+index*.001,
                                    "child_pid": model["pid"], "parent_pid": 100,
                                    "child_current_rss_bytes": 2*MIB, "parent_current_rss_bytes": MIB,
                                    "raw_ps": f"{model['pid']} 2048\n100 1024\n"}}
            records.append(record); results.append(result)
        dashboard = aggregate(records, results, {}, mode)
        dashboard["derived"] = extended_views(records, results)
        job_snapshot = VERIFY.sha(VERIFY.canonical(records))
        job = {"id": identifier, "mode": mode, "state": "completed_with_fallback" if mode == "demo" else "completed",
               "error_code": None, "total_items": 340, "completed_items": 340, "snapshot_hash": job_snapshot,
               "request": {"source": "upload", "mode": mode, "max_qwen_calls": {"m1_only": 0, "research": 500, "demo": 20}[mode], "audit_rate": 0, "seed": 42},
               "progress": {}, "manifest": {"file_sha256": payload_hash, "filename": "exp079-snapshot.jsonl"}, "dashboard": dashboard,
               "items": [{"ordinal": i, "record": record, "result": result} for i, (record, result) in enumerate(zip(records, results))]}
        jobs[identifier] = job
        summary = {"events": 340, "schema_valid": 340, "cost": dict(cumulative), "fallback_count": 5 if mode == "demo" else 0,
                   "latency_ms": {"n": 340, "min": 1., "median": 1., "p90": 1., "p95": 1., "max": 1.},
                   "child_current_rss_median_bytes": 2*MIB, "child_current_rss_peak_bytes": 2*MIB,
                   "parent_current_rss_peak_bytes": MIB, "child_reported_peak_rss_bytes": 3*MIB,
                   "mlx_peak_bytes": 0 if mode == "m1_only" else 4*MIB, "child_first85_last85_ratio": 1.0}
        entries.append({"id": identifier, "round": round_index, "mode": mode, "status": job["state"],
                        "started_monotonic": start, "ended_monotonic": end, "elapsed_seconds": end-start,
                        "readiness_started_monotonic": ready_start, "readiness_ended_monotonic": ready_end, "readiness_indices": indices,
                        "snapshot_hash": job_snapshot, "total_items": 340, "completed_items": 340, "summary": summary,
                        "normal_exit": True, "cost_complete": True,
                        "exit_observation": {"sample_index": absent_index, "absent_model_keys": sorted(seen)}})
        attempts.append({"round": round_index, "mode": mode, "status": "Ready", "readiness_indices": indices,
                         "observed_sample_indices": indices, "started_monotonic": ready_start, "ended_monotonic": ready_end})
    run = {"experiment_id": "EXP-079", "status": "Completed" if count == 9 else "Stopped", "planned_jobs": 9, "planned_events": 3060,
           "jobs": entries, "readiness_attempts": attempts, "completed_jobs": count, "failure_code": None if count == 9 else "fixture_stop",
           "unhandled_errors": 0, "driver_unhandled_errors": 0, "worker_unhandled_errors": 0,
           "started_monotonic": 0., "ended_monotonic": samples[-1]["monotonic"]+.05,
           "elapsed_seconds": samples[-1]["monotonic"]+.05}
    return plan, run, jobs, original, samples, events, service


def analyze(bundle):
    with patch.object(VERIFY, "SOURCE_HASH", bundle[0]["source_snapshot_sha256"]):
        return VERIFY.analyze(*bundle)


def test_all_nine_jobs_independently_verify_modes_replay_and_safety():
    report = analyze(fixture())
    assert report["exp079_complete"] is True and report["operational_state"] == "safe-to-continue"
    assert report["verified_acknowledged_events"] == 3060
    assert report["completed_jobs_by_mode"] == {"m1_only": 3, "research": 3, "demo": 3}
    assert [job["cost"]["m3_attempts"] for job in report["jobs"]] == [0, 25, 20]*3
    assert report["m3_distinct_inputs_with_results"] == 25
    assert all(job["m1_max_abs_difference"] == 0 for job in report["jobs"])


def test_source_order_payload_and_route_metadata_cannot_drift():
    for mutation in ("order", "payload", "route"):
        bundle = fixture(1)
        if mutation == "order": bundle[2]["fixture-job-0"]["items"].reverse()
        elif mutation == "payload": bundle[0]["payload_sha256"] = "0"*64
        else: bundle[0]["source_rows"][0]["route_eligible"] = False
        with pytest.raises(ValueError): analyze(bundle)


def test_m1_and_cross_round_m3_probability_drift_is_rejected():
    bundle = fixture()
    bundle[2]["fixture-job-0"]["items"][0]["result"]["m1_probabilities"] = [.6, .2, .1, .1, .1, .1]
    with pytest.raises(ValueError, match="m1_replay_mismatch"): analyze(bundle)
    bundle = fixture()
    bundle[2]["fixture-job-4"]["items"][0]["result"]["m3_probabilities"] = [.1, .7, .1, .1, .1, .1]
    with pytest.raises(ValueError, match="m3_replay_mismatch"): analyze(bundle)


def test_demo_budget_and_source_partial_cost_are_not_fabricated():
    bundle = fixture(2)
    entry, job = bundle[1]["jobs"][-1], bundle[2]["fixture-job-1"]
    job.update(state="cancelled", completed_items=0, dashboard=None)
    for row in job["items"]: row["result"] = None
    entry.update(status="cancelled", completed_items=0, summary=None, cost_complete=False, normal_exit=False,
                 acknowledged_results=0, acknowledged_cost_lower_bound={key: 0 for key in VERIFY.COSTS}, unacknowledged_attempts=None)
    bundle[1].update(completed_jobs=1, failure_code="critical_memory_pressure")
    bundle[5][:] = [event for event in bundle[5] if not (event["job_id"] == entry["id"] and event["type"] == "final_gate_passed")]
    for event in bundle[5]:
        if event["job_id"] == entry["id"] and event["type"] == "process_exit": event["returncode"] = -15
    report = analyze(bundle)
    assert report["exp079_complete"] is False and report["completed_jobs_by_mode"]["m1_only"] == 1
    partial = report["jobs"][-1]
    assert partial["cost"] is None and partial["cost_complete"] is False
    assert partial["mlx_peak_bytes"] is None and partial["m3_max_abs_difference"] is None
    assert report["operational_state"] == "stop-required"


def test_no_jobs_stopped_can_be_audited_without_missing_summary():
    report = analyze(fixture(0))
    assert report["submitted_jobs"] == report["completed_jobs"] == 0
    assert report["exp079_complete"] is False
    assert report["jobs"] == [] and report["cross_job_plateau"][0]["round3_over_round1"] is None


def test_monitor_unknown_or_critical_prevents_operational_pass():
    for kind in ("critical", "unknown"):
        bundle = fixture()
        if kind == "critical": bundle[4][-1]["system"].update(pressure_level=4, pressure_raw="4\n")
        else: bundle[4][-1]["system"].update(status="unknown", pressure_level=None, pressure_raw=None)
        report = analyze(bundle)
        assert report["exp079_complete"] is False and report["safety"]["system"]["gate_passed"] is False


def test_quiet_window_requires_ten_normal_low_swap_samples():
    bundle = fixture(1)
    index = bundle[1]["jobs"][0]["readiness_indices"][3]
    bundle[4][index]["system"].update(pressure_level=2, pressure_raw="2\n")
    assert analyze(bundle)["safety"]["readiness_gate"] is False


def test_previous_job_quiet_window_cannot_be_reused():
    bundle = fixture(2)
    first, second = bundle[1]["jobs"]
    second.update(readiness_indices=first["readiness_indices"], readiness_started_monotonic=first["readiness_started_monotonic"], readiness_ended_monotonic=first["readiness_ended_monotonic"])
    bundle[1]["readiness_attempts"][1].update(readiness_indices=first["readiness_indices"], observed_sample_indices=first["readiness_indices"],
                                                started_monotonic=first["readiness_started_monotonic"], ended_monotonic=first["readiness_ended_monotonic"])
    assert analyze(bundle)["safety"]["readiness_gate"] is False
    bundle = fixture(1)
    bundle[1]["jobs"][0]["readiness_indices"] = bundle[1]["jobs"][0]["readiness_indices"][:-1]
    bundle[1]["readiness_attempts"][0]["readiness_indices"] = bundle[1]["jobs"][0]["readiness_indices"]
    assert analyze(bundle)["safety"]["readiness_gate"] is False


def test_raw_ps_and_system_counter_tampering_fail_independently():
    bundle = fixture(1)
    bundle[4][0]["processes"]["parent"]["current_rss_bytes"] += 1
    with pytest.raises(ValueError, match="process_raw_identity"): analyze(bundle)
    bundle = fixture(1)
    bundle[4][0]["system"]["swapins"] += 1
    with pytest.raises(ValueError, match="system_raw_identity"): analyze(bundle)


def test_reaping_pid_without_original_final_gate_is_not_success():
    bundle = fixture()
    bundle[5][:] = [event for event in bundle[5] if not (event["job_id"] == "fixture-job-0" and event["type"] == "final_gate_passed")]
    report = analyze(bundle)
    assert report["exp079_complete"] is False and report["safety"]["exit_gate"] is False


def test_sleep_cadence_and_disk_limit_are_safety_gates():
    bundle = fixture()
    bundle[4][1]["started_monotonic"] = bundle[4][0]["monotonic"]+.5
    assert analyze(bundle)["safety"]["cadence_invalid_intervals"] == 1
    bundle = fixture()
    bundle[4][-1]["disk_free_bytes"] = 511*MIB
    assert analyze(bundle)["safety"]["resource_violation_count"] == 1


def test_swap_uses_real_intervals_and_does_not_count_initial_occupancy():
    samples = []
    for index in range(4):
        incoming = 1000000 + index*25600
        samples.append({"status": "observed", "monotonic": float(index), "pressure_level": 1, "pressure_raw": "1\n",
                        "page_size": 4096, "swapins": incoming, "swapouts": 1000000,
                        "vm_stat_raw": f"page size of 4096 bytes\nSwapins: {incoming}.\nSwapouts: 1000000.\n"})
    report = VERIFY.system_summary(samples)
    assert report["thrashing"] is True and report["maximum_swap_bytes_per_second"] == 100*MIB
    assert report["initial_swap_occupancy_used_as_failure"] is False
    assert VERIFY.system_summary(samples[:1])["maximum_swap_bytes_per_second"] is None


def test_latency_quantiles_and_create_only_terminal(tmp_path):
    assert VERIFY.latency_distribution([1, 2, 3, 4]) == {"n": 4, "min": 1, "max": 4, "median": 2.5, "p90": 3.7, "p95": 3.8499999999999996}
    target = tmp_path/"verification.json"
    target.write_text("keep historical terminal")
    with patch.object(VERIFY, "RUN", tmp_path), pytest.raises(ValueError, match="verification_exists_or_symlink"):
        VERIFY.main()
    assert target.read_text() == "keep historical terminal"


def test_ready_but_zero_candidate_lost_post_ack_is_partial_not_keyerror():
    bundle = fixture(1)
    bundle[1].update(jobs=[], completed_jobs=0, failure_code="submission_identity_unconfirmed")
    bundle[2].clear(); bundle[5].clear(); del bundle[4][11:]
    bundle[1]["cleanup"] = {"normal_exit": False, "terminal_confirmed": False, "models_absent_confirmed": False,
                            "submission_recovery": {"candidate_count": 0}, "error_code": "submission_identity_unconfirmed",
                            "started_monotonic": 13., "ended_monotonic": 13.1, "max_seconds": 15}
    report = analyze(bundle)
    assert report["submitted_jobs"] == 0 and report["exp079_complete"] is False


def test_lost_ack_log_only_allows_explicit_cancel_recovery():
    bundle = fixture(1)
    final = copy.deepcopy(bundle[1]["jobs"][0])
    final.update(status="cancelled", summary=None, cost_complete=False, normal_exit=False,
                 http_submission_acknowledged=False, recovered_for_cancellation_only=True)
    first = {**final, "status": "submission_ack_lost"}
    VERIFY.check_job_log([first, final], [final])
    first["recovered_for_cancellation_only"] = False
    with pytest.raises(ValueError, match="lost_ack_log_contract"):
        VERIFY.check_job_log([first, final], [final])


def test_fast_constructor_exit_can_be_seen_from_bound_event_and_later_absence():
    bundle = fixture(1)
    job, entry = bundle[2]["fixture-job-0"], bundle[1]["jobs"][0]
    job.update(state="failed", completed_items=0, dashboard=None)
    for row in job["items"]: row["result"] = None
    entry.update(status="failed", completed_items=0, summary=None, cost_complete=False, normal_exit=False)
    bundle[1].update(completed_jobs=0)
    bundle[5][:] = [event for event in bundle[5] if event["type"] in {"constructor_started", "process_exit"}]
    bundle[5][-1]["returncode"] = 1
    for sample in bundle[4][11:13]:
        value = sample["processes"]
        value.update(models=[], selected_ps=[raw_process(value["parent"])], seen_model_keys=[], absent_model_keys=[])
    report = analyze(bundle)
    assert report["safety"]["exits"][0]["absence_observed"] is True
    assert report["jobs"][0]["cost"] is None and report["exp079_complete"] is False


def add_python_descendant(bundle, *, direct=False, rss=13*MIB, survives=False, orphan=False):
    service = bundle[6]
    root_pid = bundle[4][11]["processes"]["models"][0]["pid"]
    extra = process(902, service["pid"] if direct else root_pid, minute=31, rss=rss)
    for sample in bundle[4][11:]:
        data = sample["processes"]
        seen = set(data["seen_model_keys"]) | {extra["process_key"]}
        if sample["index"] <= 12:
            data["models"].append(dict(extra))
        elif sample["index"] == 13 and survives:
            # Its identity survives the worker and is adopted by the API parent.
            data["models"].append({**extra, "ppid": service["pid"]})
        elif sample["index"] == 13 and orphan:
            data["orphan_models"].append({**extra, "ppid": 1})
        live = {row["process_key"] for row in [*data["models"], *data["orphan_models"]]}
        data["seen_model_keys"], data["absent_model_keys"] = sorted(seen), sorted(seen-live)
        data["selected_ps"] = [raw_process(row) for row in [data["parent"], *data["models"], *data["orphan_models"]]]
        data["inference_workers"] = [row for row in data["models"] if row["ppid"] == service["pid"]]
        data["auxiliary_processes"] = [row for row in data["models"] if row["ppid"] != service["pid"]]
    for entry in bundle[1]["jobs"]:
        observation = entry["exit_observation"]
        observation["absent_model_keys"] = bundle[4][observation["sample_index"]]["processes"]["absent_model_keys"]
    return extra["process_key"]


def test_one_direct_worker_with_auxiliary_is_not_two_workers():
    bundle = fixture()
    key = add_python_descendant(bundle)
    report = analyze(bundle)
    process_report = report["safety"]["processes"]
    assert report["exp079_complete"] is True
    assert process_report["maximum_inference_workers"] == 1
    assert process_report["maximum_auxiliary_processes"] == 1
    assert process_report["samples_with_auxiliary_processes"] == 2
    assert process_report["multiple_inference_worker_samples"] == 0
    assert key in process_report["seen_process_keys"] and process_report["all_seen_absent_at_end"] is True
    assert process_report["auxiliary_role_claim"] == "ownership_only_specific_library_role_unconfirmed"


def test_two_direct_workers_still_fail_concurrency_gate():
    bundle = fixture()
    add_python_descendant(bundle, direct=True)
    report = analyze(bundle)
    assert report["exp079_complete"] is False
    assert report["safety"]["processes"]["multiple_inference_worker_samples"] == 2
    assert report["safety"]["processes"]["maximum_inference_workers"] == 2


def test_auxiliary_resource_limit_is_not_excluded():
    bundle = fixture()
    add_python_descendant(bundle, rss=13*1024*MIB)
    report = analyze(bundle)
    assert report["exp079_complete"] is False
    assert report["safety"]["resource_violation_count"] == 2
    assert report["safety"]["processes"]["multiple_inference_worker_samples"] == 0


def test_auxiliary_identity_still_alive_prevents_exit_confirmation():
    bundle = fixture(1)
    key = add_python_descendant(bundle, survives=True)
    report = analyze(bundle)
    assert key in report["safety"]["processes"]["seen_process_keys"]
    assert report["safety"]["exit_gate"] is False
    assert report["safety"]["processes"]["all_seen_absent_at_end"] is False


def test_auxiliary_orphan_still_stops_pipeline():
    bundle = fixture(1)
    add_python_descendant(bundle, orphan=True)
    report = analyze(bundle)
    assert report["safety"]["gate_passed"] is False
    assert report["safety"]["processes"]["orphan_observations"] == 1


def test_declared_roles_cannot_override_observed_ppid():
    bundle = fixture(1)
    add_python_descendant(bundle, direct=True)
    bundle[4][11]["processes"]["inference_workers"] = []
    with pytest.raises(ValueError, match="process_role_mismatch"):
        analyze(bundle)


def retain_renamed_root(bundle, index, *, rss=0):
    data = bundle[4][index]["processes"]
    root = dict(bundle[4][11]["processes"]["inference_workers"][0]) if "inference_workers" in bundle[4][11]["processes"] else dict(bundle[4][11]["processes"]["models"][0])
    root.update(comm="(python)", current_rss_bytes=rss)
    data["models"] = [row for row in data["models"] if row["pid"] != root["pid"]]
    data["tracked_other"] = [root]
    retained = [*data["models"], *data["tracked_other"]]
    data["inference_workers"] = [row for row in retained if row["ppid"] == bundle[6]["pid"]]
    data["auxiliary_processes"] = [row for row in retained if row["ppid"] != bundle[6]["pid"]]
    live = {row["process_key"] for row in [*retained, *data["orphan_models"]]}
    data["absent_model_keys"] = sorted(set(data["seen_model_keys"])-live)
    data["selected_ps"] = [f"{row['pid']} {row['ppid']} {row['current_rss_bytes']//1024} {row['start_time']} {row['comm']}"
                           for row in [data["parent"], *retained, *data["orphan_models"]]]
    return root


def test_saved_non_python_comm_row_preserves_exit_overlap_identity():
    bundle = fixture()
    add_python_descendant(bundle)
    root = retain_renamed_root(bundle, 12)
    parsed = VERIFY.parse_processes(bundle[4][12]["processes"], bundle[6])
    assert root["process_key"] in parsed["live"] and root["process_key"] not in parsed["absent"]
    assert len(parsed["inference_workers"]) == len(parsed["auxiliary_processes"]) == 1
    report = analyze(bundle)
    assert report["exp079_complete"] is True
    assert report["safety"]["processes"]["samples_with_tracked_other"] == 1


def test_unrecorded_seen_pid_gap_is_not_repaired_from_later_absence():
    bundle = fixture(1)
    sample = bundle[4][12]["processes"]
    sample.update(models=[], tracked_other=[], inference_workers=[], auxiliary_processes=[], selected_ps=[raw_process(sample["parent"])])
    assert bundle[4][13]["processes"]["seen_model_keys"] == bundle[4][13]["processes"]["absent_model_keys"]
    with pytest.raises(ValueError, match="process_absence_identity"):
        analyze(bundle)


def test_tracked_other_row_keeps_resource_limit():
    bundle = fixture()
    retain_renamed_root(bundle, 12, rss=13*1024*MIB)
    report = analyze(bundle)
    assert report["exp079_complete"] is False
    assert report["safety"]["resource_violation_count"] == 1


def test_zero_rss_tracked_other_is_not_treated_as_exited():
    bundle = fixture(1)
    retain_renamed_root(bundle, 13)
    bundle[1]["jobs"][0]["exit_observation"]["absent_model_keys"] = bundle[4][13]["processes"]["absent_model_keys"]
    report = analyze(bundle)
    assert report["safety"]["exit_gate"] is False
    assert report["safety"]["processes"]["all_seen_absent_at_end"] is False


def write_database(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE jobs(id TEXT, mode TEXT, state TEXT, total_items INTEGER, completed_items INTEGER, snapshot_hash TEXT, request TEXT, progress TEXT, manifest TEXT, dashboard TEXT)")
        db.execute("CREATE TABLE items(job_id TEXT, ordinal INTEGER, record TEXT, result TEXT)")
        for job in values:
            db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)", (job["id"], job.get("mode", "m1_only"), job["state"], job.get("total_items", 340), job.get("completed_items", 340), job["snapshot_hash"],
                       *(VERIFY.canonical(job.get(key, {})) if job.get(key) is not None else None for key in ("request", "progress", "manifest", "dashboard"))))
            db.executemany("INSERT INTO items VALUES(?,?,?,?)", [(job["id"], row["ordinal"], VERIFY.canonical(row["record"]), VERIFY.canonical(row["result"]) if row["result"] is not None else None) for row in job["items"]])


@pytest.mark.parametrize("count", [0, 9])
def test_main_cli_audits_complete_or_zero_job_stop_create_only(tmp_path, capsys, count):
    base = tmp_path/"project"
    web = base/"web"
    target = web/"private/validation/exp-079/attempt-3"
    target.mkdir(parents=True)
    bundle = fixture(count)
    plan, run, jobs, original, samples, events, service = bundle
    service.update(root=str(web), bench_root=str(target/"bench"))
    parent = web/"private/validation/exp-076/attempt-3/verification.json"
    parent.parent.mkdir(parents=True)
    parent.write_text(VERIFY.canonical({"status": "Passed", "exp076_verified": True}))
    parent_hash = VERIFY.sha(parent.read_bytes())
    plan["source_verification_sha256"] = parent_hash
    source = {"id": VERIFY.SOURCE_JOB, "state": "completed", "snapshot_hash": plan["source_snapshot_sha256"], "items": original}
    write_database(web/"private/jobs.sqlite3", [source])
    write_database(target/"bench/jobs.sqlite3", list(jobs.values()))
    code = web/"scripts/verify_bounded_runtime.py"
    code.parent.mkdir(parents=True); code.write_text("# synthetic dependency fixture\n")
    plan["sources"] = {"scripts/verify_bounded_runtime.py": VERIFY.sha(code.read_bytes())}
    protocols = base/"experiments/stack-overflow-emotion-gold/protocols"
    protocols.mkdir(parents=True)
    for filename, field in (("exp-079-bounded-runtime-acceptance.md", "protocol_sha256"), ("dec-phase-c1-bounded-operational-validation-v1.md", "decision_sha256"), ("exp-079-observer-correction-attempt-2.md", "correction_sha256"), ("exp-079-reduced-background-attempt-3.md", "reduced_background_sha256")):
        (protocols/filename).write_text("Synthetic pre-registered protocol fixture\n")
        plan[field] = VERIFY.sha((protocols/filename).read_bytes())
    previous = web/"private/validation/exp-079/attempt-2"
    previous.mkdir(parents=True)
    (previous/"frozen-code.tar.gz").write_bytes(b"Synthetic frozen code archive fixture")
    (previous/"verification.json").write_text(VERIFY.canonical({"status": "Failed", "exp079_complete": False}))
    archive_hash = VERIFY.sha((previous/"frozen-code.tar.gz").read_bytes())
    verification_hash = VERIFY.sha((previous/"verification.json").read_bytes())
    plan.update(previous_attempt_archive_sha256=archive_hash, previous_attempt_verification_sha256=verification_hash)
    (target/"service.json").write_text(VERIFY.canonical(service))
    plan["service_sha256"] = VERIFY.sha((target/"service.json").read_bytes())
    (target/"plan.json").write_text(VERIFY.canonical(plan))
    claim = {"plan_sha256": VERIFY.sha((target/"plan.json").read_bytes())}
    (target/"run-claim.json").write_text(VERIFY.canonical(claim))
    logs = []
    for entry in run["jobs"]:
        logs.extend([{**{key: entry[key] for key in ("id", "round", "mode", "started_monotonic", "readiness_indices")},
                      "status": "submitted", "summary": None, "cost_complete": False}, entry])
    for filename, data in (("samples.jsonl", samples), ("process-events.jsonl", events), ("jobs.jsonl", logs)):
        (target/filename).write_text("".join(VERIFY.canonical(row)+"\n" for row in data))
    (target/"stdout.log").write_text("Synthetic stop fixture\n")
    run.update(plan_sha256=claim["plan_sha256"], samples_sha256=VERIFY.sha((target/"samples.jsonl").read_bytes()),
               process_events_sha256=VERIFY.sha((target/"process-events.jsonl").read_bytes()), jobs_sha256=VERIFY.sha((target/"jobs.jsonl").read_bytes()),
               stdout_sha256=VERIFY.sha((target/"stdout.log").read_bytes()), service_sha256=plan["service_sha256"])
    (target/"run.json").write_text(VERIFY.canonical(run))
    before = {path: path.read_bytes() for path in target.rglob("*") if path.is_file()}
    before.update({path: path.read_bytes() for path in previous.iterdir() if path.is_file()})
    with patch.object(VERIFY, "ROOT", web), patch.object(VERIFY, "RUN", target), patch.object(VERIFY, "SOURCE_HASH", plan["source_snapshot_sha256"]), patch.object(VERIFY, "SOURCE_VERIFICATION_HASH", parent_hash), patch.object(VERIFY, "PREVIOUS_ARCHIVE_HASH", archive_hash), patch.object(VERIFY, "PREVIOUS_VERIFICATION_HASH", verification_hash), patch.object(VERIFY, "DEPENDENCIES", set(plan["sources"])), patch.object(VERIFY, "service_absent", return_value=True), patch.object(VERIFY, "check_environment"):
        assert VERIFY.main() == 0
        report = json.loads((target/"verification.json").read_text())
        assert report["status"] == "Passed" and report["exp079_complete"] is (count == 9)
        assert report["operational_state"] == ("safe-to-continue" if count == 9 else "stop-required") and report["submitted_jobs"] == count
        assert report["models_loaded"] is False and report["producer_numerical_helpers_imported"] is False
        assert report["attempt"] == 3
        assert "private/validation/exp-079/attempt-3/run.json" in report["source_hashes"]
        with pytest.raises(ValueError, match="verification_exists_or_symlink"): VERIFY.main()
    assert all(path.read_bytes() == value for path, value in before.items())
    assert ("safe-to-continue" if count == 9 else "stop-required") in capsys.readouterr().out
