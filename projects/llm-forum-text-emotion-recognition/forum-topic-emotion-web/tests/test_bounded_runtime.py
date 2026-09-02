"""EXP-079 offline ownership, readiness, lifecycle and input-contract checks."""
import importlib.util
import json
import sqlite3
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import bounded_runtime_support as support
import run_bounded_runtime as runner


START="Mon Aug 31 10:00:00 2026"
PARENT={"pid":100,"ppid":1,"comm":"python3.12","start_time":START,"process_key":"100|"+START}


def line(pid,ppid,rss=1000,comm="python3.11",start=START):
    return f"{pid} {ppid} {rss} {start} {comm}"


def observation(index,*,pressure=1,swap=1000000,models=None):
    return {"index":index,"started_monotonic":index*1.2,"monotonic":index*1.2+.2,"disk_free_bytes":1024**4,
            "system":{"status":"observed","monotonic":index*1.2+.1,"pressure_level":pressure,
                      "page_size":4096,"swapins":swap,"swapouts":swap},
            "processes":{"status":"observed","parent":{"pid":100,"current_rss_bytes":1000000},"models":models or [],
                         "orphan_models":[],"seen_model_keys":[],"absent_model_keys":[]}}


def source_rows():
    rows=[]
    for index in range(340):
        value=index if index<338 else index-238
        text=f"Synthetic technical input {value}"
        rows.append({"ordinal":index,"record":{"model_input_text":text,"model_input_hash":support.digest(text)},
                     "result":{"hypothetical_route":value<25}})
    return rows


class OwnershipTests(unittest.TestCase):
    def test_known_changed_comm_is_retained_without_guessing_process_state(self):
        seen={"101|"+START,"102|"+START}
        raw="\n".join((line(100,1,comm="python3.12"),line(101,100,comm="changed-name"),line(102,101)))
        process=support.process_snapshot(PARENT,seen,lambda _:raw)
        self.assertEqual(process["status"],"observed")
        self.assertEqual([row["pid"] for row in process["models"]],[102])
        self.assertEqual([row["pid"] for row in process["tracked_other"]],[101])
        self.assertEqual(process["tracked_other"][0]["comm"],"changed-name")
        self.assertEqual([row["pid"] for row in process["inference_workers"]],[101])
        self.assertEqual([row["pid"] for row in process["auxiliary_processes"]],[102])
        self.assertEqual(len(process["selected_ps"]),3)
        self.assertEqual(process["absent_model_keys"],[])
        live={row["process_key"] for kind in ("models","tracked_other","orphan_models") for row in process[kind]}
        self.assertEqual(live|set(process["absent_model_keys"]),seen)

    def test_retained_changed_comm_does_not_bypass_worker_rss_or_quiet_gates(self):
        seen={"101|"+START}
        process=support.process_snapshot(PARENT,seen,lambda _:"\n".join((line(100,1,comm="python3.12"),line(101,100,comm="changed-name"),line(102,100))))
        sample=observation(0);sample["processes"]=process
        self.assertEqual(support.safety_reason([sample]),"concurrent_model_processes")
        process=support.process_snapshot(PARENT,{"101|"+START},lambda _:line(100,1,comm="python3.12")+"\n"+line(101,100,rss=12*1024**2+1,comm="changed-name"))
        sample["processes"]=process
        self.assertEqual(support.safety_reason([sample]),"child_rss_limit")
        rows=[observation(index) for index in range(10)]
        rows[-1]["processes"]=process
        self.assertIsNone(support.quiet_indices(rows))

    def test_changed_auxiliary_is_retained_then_absent_and_reused_pid_is_not_retained(self):
        seen={"101|"+START,"102|"+START}
        raw="\n".join((line(100,1,comm="python3.12"),line(101,100),line(102,101,comm="aux-new-name")))
        live=support.process_snapshot(PARENT,seen,lambda _:raw)
        self.assertEqual([row["pid"] for row in live["tracked_other"]],[102])
        self.assertEqual([row["pid"] for row in live["auxiliary_processes"]],[102])
        orphan=support.process_snapshot(PARENT,seen,lambda _:line(100,1,comm="python3.12")+"\n"+line(102,1,comm="aux-new-name"))
        self.assertEqual([row["pid"] for row in orphan["orphan_models"]],[102])
        raw=line(100,1,comm="python3.12")+"\n"+line(102,1,comm="other-private-program",start="Mon Aug 31 11:00:00 2026")
        gone=support.process_snapshot(PARENT,seen,lambda _:raw)
        self.assertEqual(gone["absent_model_keys"],sorted(seen))
        self.assertFalse(gone["tracked_other"])
        self.assertNotIn("other-private-program",json.dumps(gone))

    def test_one_direct_worker_and_internal_python_descendant_are_not_two_workers(self):
        raw="\n".join((line(100,1,comm="python3.12"),line(101,100),line(102,101,rss=12928)))
        process=support.process_snapshot(PARENT,set(),lambda _:raw)
        self.assertEqual([row["pid"] for row in process["models"]],[101,102])
        self.assertEqual([row["pid"] for row in process["inference_workers"]],[101])
        self.assertEqual([row["pid"] for row in process["auxiliary_processes"]],[102])
        sample=observation(0);sample["processes"]=process
        self.assertIsNone(support.safety_reason([sample]))

    def test_two_direct_workers_still_fail_from_ppid_even_if_roles_are_wrong(self):
        raw="\n".join((line(100,1,comm="python3.12"),line(101,100),line(102,100)))
        process=support.process_snapshot(PARENT,set(),lambda _:raw)
        process["inference_workers"]=[]
        sample=observation(0);sample["processes"]=process
        self.assertEqual(support.safety_reason([sample]),"concurrent_model_processes")

    def test_auxiliary_rss_and_orphan_are_not_exempted(self):
        seen=set()
        process=support.process_snapshot(PARENT,seen,lambda _:"\n".join((line(100,1,comm="python3.12"),line(101,100),line(102,101,rss=12*1024**2+1))))
        sample=observation(0);sample["processes"]=process
        self.assertEqual(support.safety_reason([sample]),"child_rss_limit")
        orphan=support.process_snapshot(PARENT,seen,lambda _:line(100,1,comm="python3.12")+"\n"+line(102,1))
        sample["processes"]=orphan
        self.assertEqual(support.safety_reason([sample]),"owned_orphan_detected")
        self.assertIn("102|"+START,orphan["seen_model_keys"])
        self.assertNotIn("102|"+START,orphan["absent_model_keys"])

    def test_auxiliary_must_exit_before_absence_can_be_confirmed(self):
        seen={"101|"+START,"102|"+START}
        orphan=support.process_snapshot(PARENT,seen,lambda _:line(100,1,comm="python3.12")+"\n"+line(102,1))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory).resolve()/"events.jsonl"
            path.write_text(json.dumps({"pid":101,"process_key":"101|"+START})+"\n")
            monitor=SimpleNamespace(samples=[{"index":0,"processes":orphan}],events_path=path,updated=threading.Condition())
            with self.assertRaisesRegex(support.SupportError,"owned_process_exit_unconfirmed"):
                support.wait_absent(monitor,-1,time.monotonic()+.01,.01)
            absent=support.process_snapshot(PARENT,seen,lambda _:line(100,1,comm="python3.12"))
            monitor.samples=[{"index":1,"processes":absent}]
            self.assertEqual(support.wait_absent(monitor,0,time.monotonic()+.1,.1)["absent_model_keys"],sorted(seen))

    def test_only_owned_python_and_parent_are_persisted(self):
        raw="\n".join((line(100,1,comm="python3.12"),line(101,100),line(102,100,comm="ps"),
                        line(900,1,comm="sensitive_other_application")))
        seen=set(); result=support.process_snapshot(PARENT,seen,lambda _:raw)
        self.assertEqual(result["status"],"observed")
        self.assertEqual([row["pid"] for row in result["models"]],[101])
        self.assertNotIn("sensitive_other_application",json.dumps(result))
        self.assertNotIn("102 ",json.dumps(result))
        self.assertEqual(seen,{"101|"+START})

    def test_seen_orphan_and_later_absence_are_explicit(self):
        seen={"101|"+START}
        orphan=support.process_snapshot(PARENT,seen,lambda _:line(100,1,comm="python3.12")+"\n"+line(101,1))
        self.assertEqual(len(orphan["orphan_models"]),1)
        absent=support.process_snapshot(PARENT,seen,lambda _:line(100,1,comm="python3.12"))
        self.assertEqual(absent["absent_model_keys"],["101|"+START])

    def test_pid_reuse_is_not_misattributed_to_other_application(self):
        raw=line(100,1,comm="python3.12")+"\n"+line(101,1,comm="other_private_app",start="Mon Aug 31 11:00:00 2026")
        result=support.process_snapshot(PARENT,{"101|"+START},lambda _:raw)
        self.assertEqual(result["absent_model_keys"],["101|"+START])
        self.assertFalse(result["orphan_models"])
        self.assertNotIn("other_private_app",json.dumps(result))

    def test_service_reuse_or_failed_ps_is_unknown(self):
        raw=line(100,1,comm="python3.12",start="Mon Aug 31 11:00:00 2026")
        self.assertEqual(support.process_snapshot(PARENT,set(),lambda _:raw)["status"],"unknown")
        result=support.process_snapshot(PARENT,set(),lambda _:(_ for _ in ()).throw(PermissionError()))
        self.assertEqual(result["status"],"unknown")
        self.assertIsNone(result["parent"])


class ReadinessTests(unittest.TestCase):
    def test_ten_normal_no_child_quiet_samples_required(self):
        rows=[observation(index) for index in range(10)]
        self.assertEqual(support.quiet_indices(rows),list(range(10)))
        self.assertIsNone(support.quiet_indices(rows[:9]))
        self.assertIsNone(support.quiet_indices(rows,after_index=0))
        for change in ("warning","model","not_absent","swap"):
            altered=[observation(index) for index in range(10)]
            if change=="warning": altered[5]["system"]["pressure_level"]=2
            if change=="model": altered[5]["processes"]["models"]=[{}]
            if change=="not_absent": altered[5]["processes"]["seen_model_keys"]=["101|"+START]
            if change=="swap": altered[5]["system"]["swapouts"]+=100000
            self.assertIsNone(support.quiet_indices(altered))

    def test_baseline_swap_occupancy_not_failure_but_thrashing_is(self):
        rows=[observation(index) for index in range(4)]
        self.assertIsNone(support.safety_reason(rows))
        for index,row in enumerate(rows):
            row["system"]["swapouts"]+=index*40000
        self.assertEqual(support.safety_reason(rows),"swap_thrashing")

    def test_unknown_critical_orphan_and_limits_stop(self):
        critical=observation(0,pressure=4)
        self.assertEqual(support.safety_reason([critical]),"critical_memory_pressure")
        unknown=observation(0);unknown["processes"]["status"]="unknown"
        self.assertEqual(support.safety_reason([unknown]),"monitoring_unknown")
        orphan=observation(0);orphan["processes"]["orphan_models"]=[{}]
        self.assertEqual(support.safety_reason([orphan]),"owned_orphan_detected")
        parent=observation(0);parent["processes"]["parent"]["current_rss_bytes"]=1024**3+1
        self.assertEqual(support.safety_reason([parent]),"parent_rss_limit")

    def test_sampler_waits_after_completed_observation_without_catchup(self):
        clock=[0.0]
        class Stop:
            count=0
            def is_set(self): return self.count>=2
            def wait(self,seconds):
                self.count+=1;clock[0]+=seconds
        def system():
            clock[0]+=.1
            return {"status":"observed","monotonic":clock[0],"pressure_level":1,"page_size":4096,"swapins":100000,"swapouts":100000}
        def processes(service,seen):
            clock[0]+=.1
            return observation(0)["processes"]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();(root/"process-events.jsonl").write_text("")
            monitor=support.Monitor(root/"samples.jsonl",{**PARENT,"bench_root":str(root/"bench")},system=system,processes=processes,clock=lambda:clock[0])
            monitor.stopped=Stop()
            monitor._loop()
            self.assertEqual(len(monitor.samples),2)
            self.assertGreaterEqual(monitor.samples[1]["started_monotonic"],monitor.samples[0]["monotonic"]+1)


class LifecycleTests(unittest.TestCase):
    def test_event_seen_key_survives_short_process_and_incomplete_tail_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory).resolve()/"events.jsonl"
            path.write_text(json.dumps({"pid":101,"process_key":"101|"+START})+"\n"+'{"pid":')
            keys,unknown=support.recorded_process_keys(path)
            self.assertEqual(keys,{"101|"+START});self.assertFalse(unknown)
            observed=support.process_snapshot(PARENT,keys,lambda _:line(100,1,comm="python3.12"))
            self.assertEqual(observed["absent_model_keys"],["101|"+START])
            path.write_text(json.dumps({"pid":101,"process_key":None})+"\n")
            self.assertTrue(support.recorded_process_keys(path)[1])

    class FakeRunner:
        def __init__(self,job,fail=False,**kwargs):
            self.process=SimpleNamespace(pid=101,returncode=None)
            if fail: raise RuntimeError("synthetic constructor failure")
        def close(self):
            if self.process.returncode is None:self.process.returncode=-15
        def finish(self):
            self.process.returncode=0;self.close()

    def test_normal_exit_requires_real_final_gate_event(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory).resolve()/"events.jsonl";target.write_text("")
            with patch.object(support,"ProcessRunner",self.FakeRunner),patch.object(support,"process_identity",return_value={"process_key":"101|"+START}):
                factory=support.make_runner_factory(target); worker=factory({"id":"job"});worker.finish()
            rows=[json.loads(line) for line in target.read_text().splitlines()]
            self.assertEqual([row["type"] for row in rows],["constructor_started","ready","process_exit","final_gate_passed"])
            self.assertEqual(rows[-1]["returncode"],0)
            self.assertTrue(rows[-1]["normal_exit"])
            self.assertFalse(rows[-2]["normal_exit"])

    def test_cancellation_even_exit_zero_is_not_a_normal_final_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory).resolve()/"events.jsonl";target.write_text("")
            with patch.object(support,"ProcessRunner",self.FakeRunner),patch.object(support,"process_identity",return_value={"process_key":"101|"+START}):
                worker=support.make_runner_factory(target)({"id":"job"});worker.process.returncode=0;worker.close()
            rows=[json.loads(line) for line in target.read_text().splitlines()]
            self.assertNotIn("final_gate_passed",[row["type"] for row in rows])
            self.assertFalse(rows[-1]["normal_exit"])

    def test_constructor_failure_is_owned_and_closed_before_first_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory).resolve()/"events.jsonl";target.write_text("")
            with patch.object(support,"ProcessRunner",self.FakeRunner),patch.object(support,"process_identity",return_value={"process_key":"101|"+START}):
                with self.assertRaises(RuntimeError):support.make_runner_factory(target)({"id":"job"},fail=True)
            rows=[json.loads(line) for line in target.read_text().splitlines()]
            self.assertEqual([row["type"] for row in rows],["constructor_started","process_exit"])
            self.assertEqual(rows[-1]["returncode"],-15)


class InputTests(unittest.TestCase):
    def test_lost_post_ack_recovers_only_matching_unique_job_for_cancel(self):
        with tempfile.TemporaryDirectory() as directory:
            database=Path(directory).resolve()/"jobs.sqlite3"
            with sqlite3.connect(database) as db:
                db.execute("CREATE TABLE jobs(id TEXT,name TEXT,source TEXT,mode TEXT,total_items INTEGER,manifest TEXT,state TEXT)")
            known=runner.known_job_ids(database)
            def lost_ack_post():
                with sqlite3.connect(database) as db:
                    db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?)",("new","EXP-079 round 1 research","upload","research",340,
                               json.dumps({"file_sha256":"pinned","filename":"exp079-snapshot.jsonl"}),"inferencing"))
                raise TimeoutError("synthetic lost response")
            with self.assertRaises(TimeoutError):lost_ack_post()
            found=runner.recover_unacknowledged_submission(database,known,"research","pinned","EXP-079 round 1 research")
            self.assertEqual(found["status"],"identified_for_cancellation")
            self.assertEqual(found["id"],"new")
            wrong=runner.recover_unacknowledged_submission(database,known,"research","different","EXP-079 round 1 research")
            self.assertEqual(wrong["status"],"unconfirmed")
            with sqlite3.connect(database) as db:
                db.execute("INSERT INTO jobs SELECT 'other',name,source,mode,total_items,manifest,state FROM jobs")
            ambiguous=runner.recover_unacknowledged_submission(database,known,"research","pinned","EXP-079 round 1 research")
            self.assertEqual(ambiguous["status"],"unconfirmed")
            self.assertEqual(ambiguous["candidate_count"],2)

    def test_worker_unhandled_exception_is_not_lost_in_driver_support_error(self):
        self.assertEqual(runner.error_counts([{"error_code":"worker_failed"}],0),
                         {"unhandled_errors":1,"driver_unhandled_errors":0,"worker_unhandled_errors":1})
        self.assertEqual(runner.error_counts([{"error_code":None}],0)["unhandled_errors"],0)

    def test_original_order_no_warmup_and_no_added_rows(self):
        rows=source_rows();plan,payload=runner.make_plan(rows)
        self.assertEqual(len(plan["source_rows"]),340)
        self.assertEqual(plan["planned_jobs"],9)
        self.assertEqual(plan["planned_events"],3060)
        self.assertEqual(plan["attempt"],3)
        self.assertEqual(runner.RUN.name,"attempt-3")
        decoded=[json.loads(line) for line in payload.splitlines()]
        self.assertEqual([row["text"] for row in decoded],[row["record"]["model_input_text"] for row in rows])
        self.assertEqual(plan["payload_sha256"],support.digest(payload))
        self.assertNotIn("warmup_ordinals",plan)

    def test_changed_snapshot_shape_and_route_contract_fail(self):
        with self.assertRaises(support.SupportError):runner.make_plan(source_rows()[:-1])
        rows=source_rows();rows[0]["result"]["hypothetical_route"]=False
        with self.assertRaises(support.SupportError):runner.make_plan(rows)

    def test_dependency_list_excludes_future_experiments(self):
        self.assertIn("scripts/verify_local.py",support.DEPENDS)
        self.assertIn("scripts/verify_discourse_validation.py",support.DEPENDS)
        self.assertNotIn("scripts/closeout_bounded_operational.py",support.DEPENDS)
        self.assertNotIn("scripts/run_discourse_formal.py",support.DEPENDS)


if __name__=="__main__":unittest.main()
