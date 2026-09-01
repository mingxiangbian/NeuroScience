"""Synthetic independent EXP-085 accounting and semantic regression tests."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import unicodedata
import sqlite3
import hashlib

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/verify_staged_runtime.py"
SPEC = importlib.util.spec_from_file_location("exp085_checker_tested", SCRIPT)
V = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V)


def router():
    return {"labels": list(V.LABELS), "features": V.FEATURES, "classes": [0, 1],
            "scaler_mean": [.5] + [0] * 13, "scaler_scale": [1] * 14,
            "coef": [4] + [0] * 13, "intercept": 0, "m1_threshold": .31, "m3_threshold": .31, "cutoff": .5,
            "base_fingerprint": "f" * 64}


def fixture(mode="research", phase="m3"):
    records, rows, seen, m3_count = [], [], set(), 0
    totals = {name: 0 for name in V.COSTS}
    for i in range(340):
        origin = i if i < 338 else i - 338
        text = f"synthetic item {origin}"
        record = {"model_input_text": text, "model_input_hash": V.sha(text)}
        records.append(record)
        eligible = 6 <= origin <= 30
        p1 = [.75 if eligible else .125, .25, .375, .125, .25, .375]
        tokens = {"input_tokens": 12, "used_tokens": 12, "truncated": False}
        calc = V.recompute_route(p1, len(text), tokens, router())
        requested = phase == "m3" and eligible
        available = requested and m3_count < V.BUDGETS[mode]
        fallback = "m3_budget_exhausted" if requested and not available else None
        p3 = [.25, .75, .125, .375, .25, .125] if available else None
        d1 = [int(p >= .31) for p in p1]
        d3 = [int(p >= .31) for p in p3] if p3 is not None else None
        pred = d3 if available else d1
        labels = [name for name, bit in zip(V.LABELS, pred) if bit]
        counters = {name: 0 for name in V.COSTS}
        counters.update(m1_attempts=int(phase == "m1" and origin not in seen),
                        m1_cache_hit=int(phase == "m3" or origin in seen),
                        m3_attempts=int(available), m3_succeeded=int(available))
        seen.add(origin)
        m3_count += available
        totals = {name: totals[name] + counters[name] for name in V.COSTS}
        result = {"m1_probabilities": p1, "m3_probabilities": p3, "m1_prediction": d1, "m3_prediction": d3,
                  "prediction": pred, "prediction6": pred, "labels": labels, "active_labels": labels,
                  "neutral": not labels, "used_path": "m3" if available else "m1", "actual_model": "m3" if available else "m1",
                  "route_requested": requested, "routed": requested, "route_eligible": eligible, "hypothetical_route": eligible,
                  "fallback_reason": fallback, "fallback": bool(fallback), "degraded": bool(fallback),
                  "route_score": calc["score"], "m1_entropy": calc["features"][6], "threshold_margin": calc["features"][8],
                  "tokenlengths": {"m1": tokens, "m3": {"input_tokens": 24, "used_tokens": 24, "truncated": False} if available else None},
                  "truncflags": {"m1": False, "m3": False if available else None},
                  "counters": {**counters, "fallback_reason": fallback}, "cumulative_counters": dict(totals), "fingerprint": "f" * 64}
        result["cache_hit"] = bool(counters["m1_cache_hit"] and (not requested or counters["m3_cache_hit"]))
        if phase == "m3":
            result.update(prelude_transfer_reuse=True, m1_execution_origin="current_job_m1_receipt")
        rows.append({"logical_job_id": "synthetic-job", "phase_id": f"synthetic-job:{phase}", "ordinal": i,
                     "input_sha256": record["model_input_hash"], "result": result})
    return records, rows


@pytest.mark.parametrize("mode,expected_m3,fallback", [("research", 25, 0), ("demo", 20, 5)])
def test_replay_cost_is_not_duplicate_cache_or_m1_work(mode, expected_m3, fallback):
    records, rows = fixture(mode)
    result = V.recompute_cost(records, rows, mode=mode, budget=V.BUDGETS[mode], phase="m3", complete=True)
    assert result["accounting"]["actual_m1_forward_attempts"] == 0
    assert result["accounting"]["within_phase_duplicate_cache_hits"] == 0
    assert result["accounting"]["prelude_transfer_reuse"] == 340
    assert result["accounting"]["m3_attempts"] == expected_m3
    assert result["raw_phase_counters"]["m1_cache_hit"] == 340
    assert sum(result["fallbacks"].values()) == fallback


def test_m1_cost_338_plus_two_and_partial_is_unknown():
    records, rows = fixture("m1_only", "m1")
    result = V.recompute_cost(records, rows, mode="m1_only", budget=0, phase="m1", complete=True)
    assert result["accounting"]["actual_m1_forward_attempts"] == 338
    assert result["accounting"]["within_phase_duplicate_cache_hits"] == 2
    partial = V.recompute_cost(records, rows[:6], mode="m1_only", budget=0, phase="m1")
    assert partial["unacknowledged_attempts"] is None and not partial["cost_complete"]
    with pytest.raises(V.B.VerificationError, match="partial_phase"):
        V.recompute_cost(records, rows[:6], mode="m1_only", budget=0, phase="m1", complete=True)


def test_cost_tampering_or_missing_prefix_is_rejected():
    records, rows = fixture()
    rows[0]["result"]["counters"]["m1_attempts"] = 1
    with pytest.raises(V.B.VerificationError, match="phase_cost"):
        V.recompute_cost(records, rows, mode="research", budget=500, phase="m3")
    with pytest.raises(V.B.VerificationError, match="receipt_prefix"):
        V.recompute_cost(records, rows[1:], mode="research", budget=500, phase="m3")


def test_independent_semantics_and_only_one_historical_m3_reference():
    records, prelude = fixture("m1_only", "m1")
    _, rows = fixture()
    sources = [row["result"] for row in prelude]
    summary = V.functional_comparison(records, rows, router(), mode="research", budget=500, phase="m3",
                                      source_results=sources, prelude=prelude, known_m3={6: rows[6]["result"]})
    assert summary["verified_receipts"] == 340 and summary["historical_m3_reference_ordinals"] == [6]
    with pytest.raises(V.B.VerificationError, match="unproven_historical"):
        V.functional_comparison(records, rows, router(), mode="research", budget=500, phase="m3",
                                source_results=sources, prelude=prelude, known_m3={7: rows[7]["result"]})


@pytest.mark.parametrize("mutate", [
    lambda row: row.update(route_score=.99),
    lambda row: row["tokenlengths"]["m1"].update(used_tokens=11),
    lambda row: row.update(prediction=[0] * 6),
    lambda row: row.update(m1_probabilities=[.1] * 6),
])
def test_functional_drift_fails(mutate):
    records, prelude = fixture("m1_only", "m1")
    _, rows = fixture()
    mutate(rows[0]["result"])
    with pytest.raises((V.B.VerificationError, V.LOCAL.VerificationError)):
        V.functional_comparison(records, rows, router(), mode="research", budget=500, phase="m3",
                                source_results=[row["result"] for row in prelude], prelude=prelude)


def test_round_comparisons_do_not_claim_old_m3_parity():
    _, rows = fixture()
    baseline = {}
    assert V.compare_m3_repetitions(rows, baseline)["first_observed_inputs"] == 25
    assert V.compare_m3_repetitions(rows, baseline)["compared_occurrences"] == 25
    changed = copy.deepcopy(rows)
    changed[8]["result"]["m3_probabilities"][0] = .5
    with pytest.raises(V.B.VerificationError, match="m3_repeat_probability"):
        V.compare_m3_repetitions(changed, baseline)


def test_transfer_binds_current_phase_and_all340_with338_cache_groups():
    _, rows = fixture("m1_only", "m1")
    transfer = {"base_fingerprint": "f" * 64, "entries": [
        {"ordinal": row["ordinal"], "input_sha256": row["input_sha256"], "m1_probabilities": row["result"]["m1_probabilities"],
         "tokenlengths": {"m1": row["result"]["tokenlengths"]["m1"]}} for row in rows]}
    envelope = {"logical_job_id": "synthetic-job", "phase_id": "synthetic-job:m3", "transfer": transfer,
                "transfer_sha256": V.sha(V.LOCAL.canonical(transfer)), "m1_receipts_sha256": V.receipt_digest(rows)}
    result = V.check_transfer(envelope, rows, logical_job_id="synthetic-job", phase_id="synthetic-job:m3", m1_phase_id="synthetic-job:m1")
    assert result["transfer_items"] == 340 and result["cache_entries"] == 338
    envelope["m1_receipts_sha256"] = "0" * 64
    with pytest.raises(V.B.VerificationError, match="current_receipt_digest"):
        V.check_transfer(envelope, rows, logical_job_id="synthetic-job", phase_id="synthetic-job:m3", m1_phase_id="synthetic-job:m1")


@pytest.mark.parametrize("bad", [None, "missing", "duplicate", "symlink"])
def test_parent_archive_uses_frozen_contents_not_changed_live_sources(tmp_path, bad):
    content = {f"scripts/source{i}.py": f"old{i}".encode() for i in range(39)}
    plan = {"sources": {name: V.sha(value) for name, value in content.items()}, "protocol": {"sha256": V.sha("protocol")}}
    content["protocol.md"] = b"protocol"
    path = tmp_path / "archive.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        for name, raw in content.items():
            if bad == "missing" and name == "protocol.md":
                continue
            entry = tarfile.TarInfo(name)
            entry.size = len(raw)
            if bad == "symlink" and name == "protocol.md":
                entry.type, entry.linkname, entry.size = tarfile.SYMTYPE, "outside", 0
            archive.addfile(entry, io.BytesIO(raw))
            if bad == "duplicate" and name == "protocol.md":
                archive.addfile(entry, io.BytesIO(raw))
    path.chmod(0o600)
    run = {"status": "Completed"}
    verification = {"status": "Passed", "diagnostic_completed": True, "safety": {"gate_passed": True}}
    if bad:
        with pytest.raises(V.B.VerificationError):
            V.check_parent_archive(path, V.sha(path.read_bytes()), plan, run, verification)
    else:
        summary = V.check_parent_archive(path, V.sha(path.read_bytes()), plan, run, verification)
        assert summary["members"] == 40 and summary["old_sources_checked_in_archive"]


def test_partial_final_cumulative_includes_all_precomputed_m1_work():
    records, prelude = fixture("m1_only", "m1")
    _, replay = fixture()
    final_rows = [{"ordinal": i, "record": record, "result": None} for i, record in enumerate(records)]
    for i in range(6):
        value = copy.deepcopy(replay[i]["result"])
        value["staged_raw_counters"] = dict(value["counters"])
        value["staged_counter_scope"] = "physical_job_cumulative"
        value["staged_latency_scope"] = "phase_response_only_m1_prepass_excluded"
        value["cache_hit"] = False
        for key in ("m1_attempts", "m1_cache_hit"):
            value["counters"][key] = prelude[i]["result"]["counters"][key]
            value["cumulative_counters"][key] = prelude[-1]["result"]["cumulative_counters"][key]
        final_rows[i]["result"] = value
    result = V.check_final_results(records, final_rows, prelude, replay[:6], mode="research", phase1_complete=True)
    assert result["final_acknowledged_items"] == 6
    assert final_rows[5]["result"]["cumulative_counters"]["m1_attempts"] == 338
    final_rows[5]["result"]["cumulative_counters"]["m1_attempts"] = 6
    with pytest.raises(V.B.VerificationError, match="physical_job_cumulative"):
        V.check_final_results(records, final_rows, prelude, replay[:6], mode="research", phase1_complete=True)


def test_true_ready_requires_unloaded_m1_and_338_unique_entries():
    transfer = {"fingerprint": "a" * 64, "base_fingerprint": "b" * 64, "transfer_sha256": "c" * 64}
    value = {"type": "ready", **transfer, "strategy": V.STRATEGY, "transfer_items": 340, "cache_entries": 338,
             "m1_instance_absent": True, "modelstatus": {"m1": "receipt_replay_not_loaded", "m3": "not_loaded", "mode": "research"},
             "cache_scope": "job_m1_receipt_transfer", "audit_rate": 0}
    V.check_ready(value, transfer, mode="research")
    value["modelstatus"]["m1"] = "loaded"
    with pytest.raises(V.B.VerificationError, match="staged_ready_identity"):
        V.check_ready(value, transfer, mode="research")


def analysis_bundle(monkeypatch, job_count=9, uuid_ids=False):
    records, source_receipts = fixture("m1_only", "m1")
    for index, record in enumerate(records):
        identity = ["upload", "upload", "row", str(index)]
        record.update(source=identity[0], site=identity[1], object_type=identity[2], source_object_id=identity[3],
                      record_id=V.sha(json.dumps(identity, ensure_ascii=False, separators=(",", ":"))),
                      dedup_hash=V.sha(" ".join(unicodedata.normalize("NFKC", record["model_input_text"]).casefold().split())),
                      created_at="2026-08-23T00:00:00Z")
    source = [{"ordinal": i, "record": record, "result": source_receipts[i]["result"]} for i, record in enumerate(records)]
    snapshot, logical_hash = V.LOCAL.check_records(records), V.sha(V.LOCAL.canonical(source))
    monkeypatch.setattr(V, "SOURCE_SNAPSHOT", snapshot)
    monkeypatch.setattr(V.B, "SOURCE_HASH", snapshot)
    monkeypatch.setattr(V, "SOURCE_LOGICAL", logical_hash)
    metadata = [{"ordinal": i, "input_sha256": row["record"]["model_input_hash"], "route_eligible": row["result"]["hypothetical_route"]}
                for i, row in enumerate(source)]
    plan = {"experiment_id": "EXP-085", "attempt": 2, "tier": "Major", "rq": "RQ-S3", "rounds": 3,
            "modes": list(V.MODES), "planned_jobs": 9, "planned_events": 3060, "events_per_job": 340,
            "max_seconds": 1800, "work_seconds": 1770, "cleanup_seconds": 15,
            "source_job": V.SOURCE_JOB, "source_snapshot_sha256": snapshot, "source_logical_sha256": logical_hash, "source_rows": metadata}
    def process(pid, parent):
        return {"pid": pid, "ppid": parent, "current_rss_bytes": 1024**2, "start_time": "Mon Aug 31 10:00:00 2026",
                "process_key": f"{pid}|Mon Aug 31 10:00:00 2026", "comm": "Python"}
    def ps(row):
        return f"{row['pid']} {row['ppid']} 1024 {row['start_time']} /usr/bin/Python"
    service = {**process(100, 1), "experiment_id": "EXP-085", "port": 8789}
    samples, events, runtime, phases, receipts, transfers, logical, jobs, dashboards, seen = [], [], [], [], [], [], [], {}, {}, set()
    def sample(models=(), phase_id=None):
        index, clock = len(samples), len(samples) * 1.2
        live = {row["process_key"] for row in models}
        seen.update(live)
        samples.append({"index": index, "job_id": phase_id, "started_monotonic": clock, "monotonic": clock + .2,
            "system": {"status": "observed", "monotonic": clock + .1, "pressure_level": 1, "pressure_raw": "1\n",
                       "page_size": 4096, "swapins": 1, "swapouts": 2,
                       "vm_stat_raw": "Mach Virtual Memory Statistics: (page size of 4096 bytes)\nSwapins: 1.\nSwapouts: 2.\n"},
            "disk_free_bytes": 1024**3, "processes": {"status": "observed", "parent": process(100, 1),
                       "models": list(models), "orphan_models": [], "seen_model_keys": sorted(seen),
                       "absent_model_keys": sorted(seen - live), "selected_ps": [ps(service), *(ps(row) for row in models)]}})
        return index
    sample()
    known_m3 = None
    for number in range(job_count):
        mode, identifier = V.MODES[number % 3], f"{number+1:032x}" if uuid_ids else f"job{number}"
        selected, prelude, phase_ids = [], [], []
        physical = {name: 0 for name in V.COSTS}
        reuse = 0
        logical_start = samples[-1]["monotonic"]
        for stage in (["m1"] if mode == "m1_only" else ["m1", "m3"]):
            phase_id = identifier + ":" + stage
            phase_ids.append(phase_id)
            ready_start = samples[-1]["monotonic"] + .01
            indices = [sample() for _ in range(10)]
            ready_end = samples[-1]["monotonic"] + .005
            start = ready_end + .01
            model = process(201 + len(phases), 100)
            _, rows = fixture("m1_only" if stage == "m1" else mode, stage)
            for row in rows:
                row.update(logical_job_id=identifier, phase_id=phase_id)
                value = row["result"]
                value["latency_ms"] = 1.
                value["resources"] = {"peak_rss_bytes": 1024**2, "mlx_peak_bytes": 0 if stage == "m1" else 1024**2}
                value["telemetry"] = {"status": "observed", "monotonic": start + 1 + row["ordinal"] * .001,
                    "child_pid": model["pid"], "parent_pid": 100, "child_current_rss_bytes": 1024**2,
                    "parent_current_rss_bytes": 1024**2, "raw_ps": f"{model['pid']} 1024\n100 1024\n"}
            ready = {"type": "ready", "fingerprint": "f" * 64, "modelstatus": {"m1": "loaded", "m3": "not_loaded", "mode": "m1_only"},
                     "cache_scope": "job_exact_input_components", "audit_rate": 0}
            if stage == "m3":
                transfer = {"base_fingerprint": "f" * 64, "entries": [{"ordinal": row["ordinal"], "input_sha256": row["input_sha256"],
                    "m1_probabilities": row["result"]["m1_probabilities"], "tokenlengths": {"m1": row["result"]["tokenlengths"]["m1"]}} for row in prelude]}
                envelope = {"logical_job_id": identifier, "phase_id": phase_id, "transfer": transfer,
                            "transfer_sha256": V.sha(V.LOCAL.canonical(transfer)), "m1_receipts_sha256": V.receipt_digest(prelude)}
                transfers.append(envelope)
                info = V.check_transfer(envelope, prelude, logical_job_id=identifier, phase_id=phase_id, m1_phase_id=identifier+":m1")
                ready = {"type": "ready", **info, "strategy": V.STRATEGY, "m1_instance_absent": True,
                         "modelstatus": {"m1": "receipt_replay_not_loaded", "m3": "not_loaded", "mode": mode},
                         "cache_scope": "job_m1_receipt_transfer", "audit_rate": 0}
                for row in rows:
                    row["result"]["fingerprint"] = info["fingerprint"]
                selected_ordinals = [i for i in range(340) if rows[i]["result"]["m3_probabilities"] is not None]
                for k, ordinal in enumerate(selected_ordinals):
                    names = ["m3_load", "m3_forward"] if k == 0 else ["m3_forward"]
                    for name in names:
                        for kind in ("begin", "end"):
                            counters = {key: 0 for key in V.COSTS}
                            counters.update(m1_cache_hit=ordinal+1, m3_attempts=k+1, m3_succeeded=k)
                            runtime.append({"type": "staged_progress", "logical_job_id": identifier, "phase_id": phase_id,
                                            "stage": name, "kind": kind, "ordinal": ordinal,
                                            "cumulative_counters": counters, "resources": rows[ordinal]["result"]["resources"]})
            def event(kind, clock, code=None):
                value = {"type": kind, "logical_job_id": identifier, "phase_id": phase_id, "job_id": phase_id,
                         "pid": None if kind == "constructor_started" else model["pid"],
                         "process_key": None if kind == "constructor_started" else model["process_key"],
                         "returncode": code, "normal_exit": kind == "final_gate_passed", "monotonic": clock}
                if kind == "ready": value["ready"] = ready
                events.append(value)
            event("constructor_started", start + .01); event("ready", start + .05)
            sample([model], phase_id); sample([model], phase_id)
            exit_clock = samples[-1]["monotonic"] + .05
            event("process_exit", exit_clock, 0); event("final_gate_passed", exit_clock + .01, 0)
            absence = sample()
            phase = {"id": phase_id, "phase_id": phase_id, "logical_job_id": identifier, "phase": stage,
                     "mode": "m1_only" if stage == "m1" else mode, "status": "completed", "total_items": 340,
                     "completed_items": 340, "normal_exit": True, "cost_complete": True,
                     "started_monotonic": start, "ended_monotonic": samples[-1]["monotonic"] + .005,
                     "readiness_started_monotonic": ready_start, "readiness_ended_monotonic": ready_end, "readiness_indices": indices,
                     "exit_observation": {"sample_index": absence, "absent_model_keys": sorted(seen)}}
            phases.append(phase); runtime.append({"type": "phase_terminal", **phase}); receipts.extend(rows)
            if stage == "m1":
                prelude = rows
                physical.update(rows[-1]["result"]["cumulative_counters"])
                selected = copy.deepcopy(rows)
            else:
                selected = copy.deepcopy(rows)
                if known_m3 is None: known_m3 = {6: rows[6]["result"]}
                for row in selected:
                    value, first = row["result"], prelude[row["ordinal"]]["result"]
                    value["staged_raw_counters"] = {key: value["counters"][key] for key in V.COSTS}
                    value["staged_counter_scope"] = "physical_job_cumulative"
                    value["staged_latency_scope"] = "phase_response_only_m1_prepass_excluded"
                    value["cache_hit"] = bool(first["counters"]["m1_cache_hit"] and (not value["route_requested"] or value["counters"]["m3_cache_hit"]))
                    for key in ("m1_attempts", "m1_cache_hit"):
                        value["counters"][key] = first["counters"][key]
                        value["cumulative_counters"][key] = physical[key]
                for key in V.COSTS:
                    if key not in {"m1_attempts", "m1_cache_hit"}: physical[key] = rows[-1]["result"]["cumulative_counters"][key]
                reuse = 340
        state = "completed_with_fallback" if mode == "demo" else "completed"
        progress = {"staged_execution": {"strategy": V.STRATEGY, "stage": "completed",
                    "phase_completed_items": 340, "phase_total_items": 340, "cumulative_counters": physical,
                    "cost_complete": True, "cost_scope": "completed_job", "prelude_transfer_reuses": reuse, "unacknowledged_attempts": 0}}
        items = [{"ordinal": i, "record": record, "result": selected[i]["result"]} for i, record in enumerate(records)]
        job = {"id": identifier, "mode": mode, "state": state, "total_items": 340, "completed_items": 340, "snapshot_hash": snapshot,
               "request": {"source": "upload", "mode": mode, "max_qwen_calls": V.BUDGETS[mode], "audit_rate": 0}, "progress": progress, "items": items}
        dashboard = V.B.recalculate_aggregate(records, [row["result"] for row in items], mode, physical)
        dashboard["derived"] = V.B.DERIVED.recalculate_derived(records, [row["result"] for row in items])
        dashboard["routing"].update(cost_scope="staged_job_cumulative", cost_complete=True, prelude_transfer_reuses=reuse)
        job["dashboard"] = dashboard
        jobs[identifier], dashboards[identifier] = job, dashboard
        logical.append({"id": identifier, "round": number//3+1, "mode": mode, "budget": V.BUDGETS[mode], "status": state,
                        "completed_items": 340, "total_items": 340, "snapshot_hash": snapshot,
                        "started_monotonic": logical_start, "ended_monotonic": phases[-1]["ended_monotonic"], "phase_ids": phase_ids})
    run = {"experiment_id": "EXP-085", "attempt": 2, "tier": "Major", "planned_jobs": 9, "planned_events": 3060,
           "status": "Completed" if job_count == 9 else "Stopped", "failure_code": None if job_count == 9 else "synthetic_stop",
           "started_monotonic": 0., "ended_monotonic": samples[-1]["monotonic"]+.05,
           "elapsed_seconds": samples[-1]["monotonic"]+.05, "logical_jobs": logical, "phases": phases}
    return [plan, run, source, jobs, receipts, transfers, samples, events, runtime, service, router(), known_m3 or {}, dashboards]


def test_complete_nine_jobs_fifteen_phases_and_5100_receipts(monkeypatch):
    value = V.analyze(*analysis_bundle(monkeypatch))
    assert value["exp085_complete"] and value["safety"]["gate_passed"]
    assert value["verified_final_items"] == 3060 and value["verified_phase_receipts"] == 5100
    assert value["receipt_accounting_lower_bound"]["actual_m1_forward_attempts"] == 3042
    assert value["receipt_accounting_lower_bound"]["m3_attempts"] == 135
    assert value["receipt_accounting_lower_bound"]["prelude_transfer_reuse"] == 2040
    assert value["observed_unique_m3_inputs"] == 25


def test_valid_stopped_prefix_is_not_nine_job_completion(monkeypatch):
    value = V.analyze(*analysis_bundle(monkeypatch, 1))
    assert not value["exp085_complete"] and value["operational_state"] == "stop-required"
    assert value["completed_jobs"] == 1 and value["unacknowledged_attempts"] is None


def test_complete_attempt2_requires_closed_m3_load_and_forward_progress(monkeypatch):
    bundle = analysis_bundle(monkeypatch)
    value = V.analyze(*bundle)
    assert value["exp085_complete"]
    markers = bundle[8]
    index = next(i for i, row in enumerate(markers) if row.get("type") == "staged_progress"
                 and row.get("stage") == "m3_load" and row.get("kind") == "end")
    markers.pop(index)
    with pytest.raises(V.B.VerificationError, match="stage"):
        V.analyze(*bundle)


@pytest.mark.parametrize("mutation", ["critical", "base_fingerprint", "dashboard", "physical_cost"])
def test_full_sequence_cannot_hide_resource_or_semantic_failures(monkeypatch, mutation):
    bundle = analysis_bundle(monkeypatch)
    if mutation == "critical":
        bundle[6][15]["system"].update(pressure_level=4, pressure_raw="4\n")
        value = V.analyze(*bundle)
        assert not value["exp085_complete"] and not value["safety"]["gate_passed"]
        return
    if mutation == "base_fingerprint": bundle[7][1]["ready"]["fingerprint"] = "a"*64
    if mutation == "dashboard": bundle[-1]["job0"]["summary"]["successful_items"] = 339
    if mutation == "physical_cost": bundle[3]["job1"]["progress"]["staged_execution"]["cumulative_counters"]["m1_attempts"] = 6
    with pytest.raises((V.B.VerificationError, V.LOCAL.VerificationError)):
        V.analyze(*bundle)


def test_failure_counter_receipt_is_kept_as_known_lower_bound(monkeypatch):
    records, rows = fixture()
    _, originals = fixture("m1_only", "m1")
    values = {key: 0 for key in V.COSTS}
    values.update(m1_cache_hit=7, m3_attempts=1)
    event = {"type": "failure_cost", "phase_id": "job:m3", "error_code": "resource_limit_exceeded", "cumulative_counters": values}
    phase = {"id": "job:m3", "phase": "m3", "status": "failed"}
    report = V.runtime_progress([event], phase, rows[:6], [row["result"] for row in originals], 500)
    assert report["raw_counter_lower_bound"]["m3_attempts"] == 1
    assert report["raw_counter_lower_bound"]["m1_cache_hit"] == 7
    assert report["acknowledged_failure_counter_events"] == 1


def test_cancelled_partial_missing_api_retains_two_cost_scopes():
    records, rows = fixture("m1_only", "m1")
    items = [{"ordinal": i, "record": {**record, "object_type": "row", "dedup_hash": record["model_input_hash"]},
              "result": rows[i]["result"] if i < 6 else None} for i, record in enumerate(records)]
    for row in items[:6]: row["result"]["latency_ms"] = 1.
    known = {key: 0 for key in V.COSTS}; known["m1_attempts"] = 7
    stored = {**known, "m1_attempts": 6}
    job = {"mode": "m1_only", "items": items, "progress": {"staged_execution": {
        "strategy": V.STRATEGY, "cumulative_counters": stored, "prelude_transfer_reuses": 0,
        "cost_complete": False, "cost_scope": "job_cumulative_lower_bound", "unacknowledged_attempts": None}}}
    checked = V.check_dashboard(job, known, 0, complete=False)
    assert checked["api_dashboard"] == "not_observed_partial"
    assert checked["not_published_counter_delta"]["m1_attempts"] == 1
    assert checked["stored_counter_lower_bound"]["m1_attempts"] == 6


def test_model_free_cli_roundtrip_reads_sealed_db_and_all_artifacts(monkeypatch, tmp_path):
    bundle = analysis_bundle(monkeypatch, uuid_ids=True)
    plan, run, source, jobs, receipts, transfers, samples, events, runtime, service, fitted, references, dashboards = bundle
    root = tmp_path.resolve()
    run_dir = root / "private/validation/exp-085/attempt-2"
    (run_dir / "bench").mkdir(parents=True)
    (run_dir / "results").mkdir()
    (run_dir / "dashboards").mkdir()
    monkeypatch.setattr(V, "ROOT", root)
    monkeypatch.setattr(V, "RUN", run_dir)
    monkeypatch.setattr(V, "check_bindings", lambda *args: (references, {"members": 40}, {"verification_status": "Failed"}))
    monkeypatch.setattr(V, "load_router", lambda *args: fitted)
    def save(path, value):
        path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
        path.chmod(0o600)
    def database(path, entries):
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE jobs(id,mode,state,snapshot_hash,total_items,completed_items,request,progress,manifest,dashboard)")
            connection.execute("CREATE TABLE items(job_id,ordinal,record,result)")
            for job in entries:
                connection.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)", (job["id"], job.get("mode", "m1_only"), job["state"], job["snapshot_hash"],
                    340, job["completed_items"], json.dumps(job.get("request", {})), json.dumps(job.get("progress", {})), "{}", json.dumps(job.get("dashboard"))))
                for row in job["items"]:
                    connection.execute("INSERT INTO items VALUES(?,?,?,?)", (job["id"], row["ordinal"], json.dumps(row["record"]), json.dumps(row["result"])))
        path.chmod(0o600)
    database(root / "private/jobs.sqlite3", [{"id": V.SOURCE_JOB, "state": "completed", "snapshot_hash": V.SOURCE_SNAPSHOT,
                                             "completed_items": 340, "items": source}])
    database(run_dir / "bench/jobs.sqlite3", jobs.values())
    payload = "".join(V.LOCAL.canonical({"id": f"source-{row['ordinal']}", "text": row["record"]["model_input_text"]}) + "\n" for row in source)
    plan.update(payload_sha256=V.sha(payload), payload_bytes=len(payload.encode()), sources={})
    artifacts = []
    for name, value in (("plan.json", plan), ("run-claim.json", {}), ("service.json", service)):
        save(run_dir / name, value); artifacts.append(run_dir / name)
    (run_dir / "stdout.log").write_text(""); (run_dir / "stdout.log").chmod(0o600); artifacts.append(run_dir / "stdout.log")
    journal_rows = {"phase_receipt": receipts, "transfer": transfers, "sample": samples, "process_event": events, "runtime_event": runtime}
    for kind, name in V.JOURNALS.items():
        path = run_dir / name
        path.write_text("".join(V.LOCAL.canonical(row) + "\n" for row in journal_rows[kind]))
        path.chmod(0o600); artifacts.append(path)
    for entry in run["logical_jobs"]:
        identifier, job = entry["id"], jobs[entry["id"]]
        entry["results_path"] = str((run_dir / "results" / (identifier + ".json")).relative_to(root))
        entry["dashboard_path"] = str((run_dir / "dashboards" / (identifier + ".json")).relative_to(root))
        artifact = {"id": identifier, "snapshot_hash": job["snapshot_hash"], "items": [
            {"ordinal": row["ordinal"], "input_sha256": row["record"]["model_input_hash"], "result": row["result"]} for row in job["items"]]}
        save(root / entry["results_path"], artifact); artifacts.append(root / entry["results_path"])
        save(root / entry["dashboard_path"], dashboards[identifier]); artifacts.append(root / entry["dashboard_path"])
    artifacts.append(run_dir / "bench/jobs.sqlite3")
    run.update(bench_database=str((run_dir / "bench/jobs.sqlite3").relative_to(root)),
               journal_counts={kind: len(rows) for kind, rows in journal_rows.items()},
               source_hashes={str(path.relative_to(root)): V.sha(path.read_bytes()) for path in artifacts})
    save(run_dir / "run.json", run)
    assert V.main() == 0
    verification = V.LOCAL.strict_json((run_dir / "verification.json").read_text())
    assert verification["status"] == "Passed" and verification["exp085_complete"]
    assert verification["verified_final_items"] == 3060 and verification["verified_phase_receipts"] == 5100
    assert (run_dir / "verification.json").stat().st_mode & 0o777 == 0o600
    with pytest.raises(V.B.VerificationError, match="verification_exists"):
        V.main()


def previous_fixture(monkeypatch, tmp_path, mutation=None):
    root = tmp_path.resolve()
    directory = root / "private/validation/exp-085/attempt-1"
    directory.mkdir(parents=True)
    sources = {f"scripts/frozen-{i}.py": V.sha(f"source-{i}") for i in range(32)}
    documents = {
        "plan": {"experiment_id": "EXP-085", "attempt": 1, "sources": sources,
                 "protocol": {"path": "old-protocol.md", "sha256": V.sha("old protocol")}},
        "run": {"experiment_id": "EXP-085", "attempt": 1, "status": "Stopped", "failure_code": "staged_internal_error"},
        "verification": {"experiment_id": "EXP-085", "attempt": 1, "status": "Failed", "error_code": "staged_lower_bound_range",
                         "exp085_complete": False, "operational_state": "stop-required"},
    }
    if mutation == "run": documents["run"]["status"] = "Completed"
    if mutation == "verification": documents["verification"]["error_code"] = "another_failure"
    hashes = {}
    for name, value in documents.items():
        path = directory / (name + ".json")
        path.write_text(json.dumps(value, sort_keys=True) + "\n"); path.chmod(0o600)
        hashes[name] = V.sha(path.read_bytes())
    archive = directory / "frozen-code.tar.gz"
    with tarfile.open(archive, "w:gz") as stream:
        for name, expected in {**sources, "protocol.md": V.sha("old protocol")}.items():
            payload = ("corrupt" if mutation == "archive" and name == "protocol.md"
                       else "old protocol" if name == "protocol.md" else f"source-{int(name.split('-')[-1][:-3])}").encode()
            entry = tarfile.TarInfo(name); entry.size = len(payload)
            stream.addfile(entry, io.BytesIO(payload))
    archive.chmod(0o600)
    monkeypatch.setattr(V, "ROOT", root)
    monkeypatch.setattr(V, "PREVIOUS_HASHES", hashes)
    monkeypatch.setattr(V, "PREVIOUS_ARCHIVE_SHA256", V.sha(archive.read_bytes()))
    previous = {name: {"path": f"private/validation/exp-085/attempt-1/{name}.json", "sha256": digest}
                for name, digest in hashes.items()}
    previous["archive"] = {"path": "private/validation/exp-085/attempt-1/frozen-code.tar.gz",
                           "sha256": V.PREVIOUS_ARCHIVE_SHA256, "members": 33}
    return {"previous_attempt": previous}


def test_attempt2_binds_failed_attempt1_as_lineage_not_model_reference(monkeypatch, tmp_path):
    summary = V.check_previous_attempt(previous_fixture(monkeypatch, tmp_path))
    assert summary["run_status"] == "Stopped" and summary["run_failure_code"] == "staged_internal_error"
    assert summary["verification_status"] == "Failed" and summary["verification_error_code"] == "staged_lower_bound_range"
    assert summary["archive_members"] == 33 and not summary["exp085_complete"]
    assert "not_model_input" in summary["reference_scope"]


@pytest.mark.parametrize("mutation,code", [("run", "previous_run_terminal"),
                                             ("verification", "previous_verification_terminal"),
                                             ("archive", "previous_archive_sources")])
def test_wrong_attempt1_terminal_or_archive_cannot_authorize_attempt2(monkeypatch, tmp_path, mutation, code):
    with pytest.raises(V.B.VerificationError, match=code):
        V.check_previous_attempt(previous_fixture(monkeypatch, tmp_path, mutation))


def test_attempt1_binding_hash_or_extra_field_is_rejected(monkeypatch, tmp_path):
    plan = previous_fixture(monkeypatch, tmp_path)
    plan["previous_attempt"]["run"]["sha256"] = "0" * 64
    with pytest.raises(V.B.VerificationError, match="previous_attempt_binding"):
        V.check_previous_attempt(plan)
    plan = previous_fixture(monkeypatch, tmp_path / "second")
    plan["previous_attempt"]["predictions"] = {"path": "forbidden", "sha256": "0" * 64}
    with pytest.raises(V.B.VerificationError, match="previous_archive_binding"):
        V.check_previous_attempt(plan)


def test_attempt1_lineage_reader_opens_only_three_documents_and_archive(monkeypatch, tmp_path):
    plan = previous_fixture(monkeypatch, tmp_path)
    opened = []
    original = V.B.regular_file
    def observed(path):
        opened.append(Path(path).name)
        return original(path)
    monkeypatch.setattr(V.B, "regular_file", observed)
    V.check_previous_attempt(plan)
    assert set(opened) == {"plan.json", "run.json", "verification.json", "frozen-code.tar.gz"}
    assert not {"phase-receipts.jsonl", "runtime-events.jsonl", "results.json", "jobs.sqlite3"}.intersection(opened)
