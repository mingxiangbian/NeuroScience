"""Offline EXP-077 workload/telemetry/accounting checks; no model or API calls."""
import copy
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from topicweb import telemetry
from topicweb.worker import ProcessRunner, WorkerError

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


RUNNER, VERIFIER = module("run_soak"), module("verify_soak")


def source_fixture():
    rows = []
    for index in range(340):
        identity = index if index < 338 else index-338
        text = f"Synthetic technical record {identity}: " + "x"*(identity % 31)
        rows.append({"ordinal": index, "record": {"model_input_text": text, "model_input_hash": RUNNER.digest(text)},
                     "result": {"hypothetical_route": identity < 23, "m1_probabilities": [.7,.1,.1,.1,.1,.1],
                                "m1_prediction": [1,0,0,0,0,0]}})
    return rows


def sample(seconds, *, swap=1_000_000, pressure=1):
    return {"status": "observed", "monotonic": seconds, "pressure_level": pressure, "pressure_raw": str(pressure)+"\n",
            "page_size": 4096, "swapins": swap, "swapouts": swap,
            "vm_stat_raw": f"Mach Virtual Memory Statistics: (page size of 4096 bytes)\nSwapins: {swap}.\nSwapouts: {swap}.\n"}


def fake_job(source, events, mode, child_pid=1001, growth=False):
    seen1, seen3, cumulative, rows = set(), set(), {key: 0 for key in RUNNER.COSTS}, []
    for event in events:
        original = source[event["source_ordinal"]]
        hashed = event["input_sha256"]
        requested = event["route_eligible"] and mode != "m1_only"
        costs = {key: 0 for key in RUNNER.COSTS}
        costs.update(m1_attempts=int(hashed not in seen1), m1_cache_hit=int(hashed in seen1))
        seen1.add(hashed)
        used, fallback = False, None
        if requested:
            if hashed in seen3:
                costs["m3_cache_hit"], used = 1, True
            elif mode == "demo" and cumulative["m3_attempts"] >= 20:
                fallback = "m3_budget_exhausted"
            else:
                costs["m3_attempts"] = costs["m3_succeeded"] = 1
                seen3.add(hashed)
                used = True
        for key in costs:
            cumulative[key] += costs[key]
        rss_kb = 1_100_000 if growth and 271 <= event["ordinal"] < 356 else 1_000_000
        observed = telemetry.current_rss(child_pid, 999, lambda _: f"{child_pid} {rss_kb}\n999 100000\n")
        prediction = [0,1,0,0,0,0] if used else [1,0,0,0,0,0]
        result = {"prediction": prediction, "m1_prediction": [1,0,0,0,0,0], "m3_prediction": [0,1,0,0,0,0] if used else None,
                  "m1_probabilities": [.7,.1,.1,.1,.1,.1], "m3_probabilities": [.1,.9,.1,.1,.1,.1] if used else None,
                  "neutral": False, "used_path": "m3" if used else "m1", "route_requested": requested,
                  "hypothetical_route": event["route_eligible"], "fallback": bool(fallback), "fallback_reason": fallback,
                  "counters": costs, "cumulative_counters": dict(cumulative), "telemetry": observed,
                  "resources": {"mlx_peak_bytes": 8_000_000_000 if used else 0}, "latency_ms": 1.0}
        record = {"model_input_text": original["record"]["model_input_text"], "model_input_hash": hashed,
                  "source_payload_raw": {"id": f"event-{event['ordinal']}-{event['phase']}-source-{event['source_ordinal']}"}}
        rows.append({"ordinal": event["ordinal"], "record": record, "result": result})
    return rows


class TelemetryTests(unittest.TestCase):
    def test_current_rss_uses_ps_not_high_water_mark(self):
        observed = telemetry.current_rss(10, 20, lambda argv: "10 1200\n20 800\n")
        self.assertEqual(observed["child_current_rss_bytes"], 1200*1024)
        self.assertEqual(observed["parent_current_rss_bytes"], 800*1024)
        self.assertEqual(VERIFIER.rss_observation(observed), (1200*1024,800*1024))

    def test_unknown_telemetry_remains_null(self):
        observed = telemetry.current_rss(10, 20, lambda _: "10 1200\n")
        self.assertEqual(observed["status"], "unknown")
        self.assertIsNone(observed["child_current_rss_bytes"])
        self.assertIsNone(observed["parent_current_rss_bytes"])
        system = telemetry.system_memory(lambda _: (_ for _ in ()).throw(PermissionError()))
        self.assertEqual(system["status"], "unknown")
        self.assertIsNone(system["pressure_level"])

    def test_system_fields_parse_without_initial_swap_failure(self):
        raw = sample(0)
        observed = telemetry.system_memory(lambda argv: raw["pressure_raw"] if argv[0].endswith("sysctl") else raw["vm_stat_raw"])
        self.assertEqual(observed["swapins"], 1_000_000)
        rows = [sample(number) for number in (0,1,2,3)]
        self.assertIsNone(RUNNER.system_stop(rows))
        result = VERIFIER.system_summary(rows)
        self.assertTrue(result["gate_passed"])
        self.assertEqual(result["swap_delta_bytes"], 0)

    def test_real_interval_rate_and_three_interval_thrashing(self):
        # Combined in/out delta = 100 MiB each second, regardless of initial counters.
        rows = [sample(index, swap=1_000_000+index*12800) for index in range(4)]
        self.assertEqual(RUNNER.system_stop(rows), "swap_thrashing")
        self.assertTrue(VERIFIER.system_summary(rows)["thrashing"])
        self.assertIsNone(RUNNER.system_stop(rows[:3]))

    def test_normal_scheduling_jitter_is_not_missing_telemetry(self):
        rows = [sample(number) for number in (0,1.25,2.5,3.75)]
        self.assertIsNone(RUNNER.system_stop(rows))
        self.assertTrue(VERIFIER.system_summary(rows)["gate_passed"])
        self.assertEqual(RUNNER.system_stop([sample(0),sample(3.01)]), "system_interval_unknown")

    def test_pressure_critical_and_unknown_stop(self):
        self.assertEqual(RUNNER.system_stop([sample(0,pressure=4)]), "critical_memory_pressure")
        self.assertEqual(RUNNER.system_stop([{"status":"unknown"}]), "system_telemetry_unknown")

    def test_worker_hook_opt_in_and_parent_limit(self):
        process = ProcessRunner.__new__(ProcessRunner)
        process.process = SimpleNamespace(pid=10)
        process._send = lambda _: None
        process._read = lambda: {"type":"result", "item_id":"0", "result":{"cumulative_counters":{}}}
        record = {"model_input_text":"synthetic", "model_input_hash":"x"}
        with patch.dict(os.environ, {"TOPICWEB_TELEMETRY":"0"}), patch.object(telemetry,"current_rss") as capture:
            self.assertNotIn("telemetry", process.predict(0,record))
            capture.assert_not_called()
        observed = telemetry.current_rss(10,20,lambda _:"10 100\n20 2000000\n")
        with patch.dict(os.environ, {"TOPICWEB_TELEMETRY":"1"}), patch.object(telemetry,"current_rss", return_value=observed):
            with self.assertRaisesRegex(WorkerError,"current_rss_limit"):
                process.predict(0,record)


class WorkloadTests(unittest.TestCase):
    def test_major_environment_metadata_reads_no_model_backend(self):
        calls=[]
        expected=json.loads(RUNNER.MODEL_CONFIG.read_text())["environment"]
        def metadata_command(arguments, env=None):
            calls.append(arguments)
            if "-c" in arguments:
                self.assertIn("importlib.metadata",arguments[arguments.index("-c")+1])
                self.assertNotIn("import torch",arguments[arguments.index("-c")+1])
                self.assertNotIn("import mlx",arguments[arguments.index("-c")+1])
                self.assertEqual(env["HF_HUB_OFFLINE"],"1")
                return json.dumps(expected)
            return "34359738368\n" if arguments[-1]=="hw.memsize" else "Synthetic CPU\n"
        result=RUNNER.environment_metadata(metadata_command)
        self.assertEqual(result["model_runtime"],expected)
        self.assertEqual(result["website"]["packages"],result["requirements_lock"]["packages"])
        self.assertEqual(result["hardware"]["physical_memory_bytes"],34359738368)
        self.assertEqual(len(calls),3)

    def test_fixed_traffic_dedup_and_phase_sizes(self):
        original = source_fixture()
        plan, content = RUNNER.traffic_plan(original)
        self.assertEqual(len(plan["events"]),420)
        self.assertEqual(len(set(plan["warmup_ordinals"])),16)
        self.assertEqual([sum(event["phase"]==phase for event in plan["events"]) for phase in RUNNER.PHASES],[16,340,64])
        self.assertEqual(plan["payload_sha256"],RUNNER.digest(content))
        plan["source_logical_sha256"] = RUNNER.digest(RUNNER.canonical(original))
        source_hash = RUNNER.digest(RUNNER.canonical([row["record"] for row in original]))
        with patch.object(VERIFIER,"SOURCE_HASH",source_hash):
            self.assertEqual(VERIFIER.validate_plan(plan,original),plan["events"])

    def test_latency_quantiles_are_linear_and_independently_recomputed(self):
        expected={"n":4,"min":0.,"median":15.,"p90":27.,"p95":28.5,"max":30.}
        VERIFIER.close(RUNNER.latency_distribution([0.,10.,20.,30.]),expected)
        VERIFIER.close(VERIFIER.latency_percentiles([0.,10.,20.,30.]),expected)

    def test_real_measured_calls_and_demo_budget_include_warmup(self):
        original = source_fixture()
        plan,_ = RUNNER.traffic_plan(original)
        for mode in RUNNER.MODES:
            rows = fake_job(original,plan["events"],mode)
            summary = RUNNER.job_summary(rows,plan["events"])
            independent,_,_,_ = VERIFIER.recompute_job(rows,plan["events"],mode,original,{})
            VERIFIER.close(summary,independent)
            self.assertEqual(summary["phases"]["measured"]["cost"]["m1_attempts"],322)
            self.assertEqual(summary["phases"]["cache_tail"]["cost"]["m1_attempts"],0)
            if mode == "demo":
                self.assertEqual(sum(phase["cost"]["m3_attempts"] for phase in summary["phases"].values()),20)

    def test_plateau_failure_is_retained_not_fixed(self):
        original = source_fixture()
        plan,_=RUNNER.traffic_plan(original)
        rows=fake_job(original,plan["events"],"m1_only",growth=True)
        summary=RUNNER.job_summary(rows,plan["events"])
        self.assertEqual(summary["child_plateau_ratio"],1.1)
        independent,_,_,_=VERIFIER.recompute_job(rows,plan["events"],"m1_only",original,{})
        self.assertEqual(independent["child_plateau_ratio"],1.1)

    def test_runtime_failure_not_confused_with_budget_fallback(self):
        original=source_fixture(); plan,_=RUNNER.traffic_plan(original)
        rows=fake_job(original,plan["events"],"demo")
        rows[0]["result"]["fallback_reason"]="m3_runtime_failure"
        with self.assertRaisesRegex(RuntimeError,"model_runtime_unstable"):
            RUNNER.job_summary(rows,plan["events"])

    def test_replay_cost_and_raw_rss_tampering_rejected(self):
        original=source_fixture(); plan,_=RUNNER.traffic_plan(original)
        for change in ("probability","cache","rss"):
            rows=fake_job(original,plan["events"],"research")
            if change=="probability": rows[0]["result"]["m1_probabilities"][0]=.8
            if change=="cache": rows[0]["result"]["counters"]["m1_cache_hit"]=1
            if change=="rss": rows[0]["result"]["telemetry"]["child_current_rss_bytes"]+=1024
            with self.assertRaises(ValueError): VERIFIER.recompute_job(rows,plan["events"],"research",original,{})

    def test_full_36_job_gate_and_cross_job_measured_only(self):
        original=source_fixture(); plan,_=RUNNER.traffic_plan(original)
        plan["source_logical_sha256"]=RUNNER.digest(RUNNER.canonical(original))
        entries,bundles=[],{}
        for index in range(36):
            mode=RUNNER.MODES[index%3]; identifier=f"fake-{index}"
            rows=fake_job(original,plan["events"],mode,1001+index,growth=index==0)
            fingerprint=RUNNER.digest(RUNNER.canonical([row["record"] for row in rows]))
            status="completed_with_fallback" if any(row["result"]["fallback"] for row in rows) else "completed"
            entry={"id":identifier,"mode":mode,"round":index//3+1,"snapshot_hash":fingerprint,"summary":RUNNER.job_summary(rows,plan["events"]),
                   "started_monotonic":index*2.,"ended_monotonic":index*2.+1.,"elapsed_seconds":1.}
            entries.append(entry)
            bundles[identifier]=({"state":status,"total_items":420,"completed_items":420,"snapshot_hash":fingerprint},rows)
        report={"jobs":entries,"status":"Completed","failure_code":None,"unhandled_errors":0,"elapsed_seconds":120}
        source_hash=RUNNER.digest(RUNNER.canonical([row["record"] for row in original]))
        with patch.object(VERIFIER,"SOURCE_HASH",source_hash):
            verdict=VERIFIER.analyze(plan,report,bundles,original,[sample(index) for index in range(4)])
        self.assertTrue(verdict["gates"]["base"])
        self.assertFalse(verdict["gates"]["within_job_child_plateau"])
        self.assertFalse(verdict["soak_gate_passed"])
        self.assertEqual(sum(row["primary"] for row in verdict["cross_job_plateau"]),3)
        self.assertEqual(verdict["verified_events"],15120)


if __name__ == "__main__":
    unittest.main()
