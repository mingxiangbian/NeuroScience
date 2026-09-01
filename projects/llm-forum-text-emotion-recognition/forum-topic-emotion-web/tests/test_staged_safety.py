"""Synthetic OS snapshots only; never sample the real machine or run a model."""
from unittest.mock import Mock, patch

import pytest

from topicweb.staged_safety import SafetyError, SafetyMonitor, process_snapshot, safety_reason, swap_rate
from topicweb.worker import Revoked

MIB = 1024**2


def process(pid=100, ppid=1, comm="python", minute=0, rss=MIB):
    start=f"Mon Aug 31 10:{minute:02d}:00 2026"
    return {"pid":pid,"ppid":ppid,"comm":comm,"start_time":start,"process_key":f"{pid}|{start}","current_rss_bytes":rss}


def raw(*rows):
    return "\n".join(f"{r['pid']} {r['ppid']} {r['current_rss_bytes']//1024} {r['start_time']} /synthetic/{r['comm']}" for r in rows)+"\n"


def system(when, pressure=1, pages=0):
    return {"status":"observed","monotonic":when,"pressure_level":pressure,"pressure_raw":str(pressure),
            "page_size":4096,"swapins":pages,"swapouts":0,
            "vm_stat_raw":f"Mach Virtual Memory Statistics: (page size of 4096 bytes)\nSwapins: {pages}.\nSwapouts: 0.\n"}


def sample(index, when, pressure=1, pages=0, seen=()):
    parent=process()
    return {"index":index,"started_monotonic":when-.1,"monotonic":when,"system":system(when,pressure,pages),
            "disk_free_bytes":2*1024*MIB,"processes":process_snapshot(parent,set(seen),lambda _:raw(parent))}


def test_owned_python_aux_renamed_and_orphan_partitions():
    parent, worker, aux=process(),process(201,100),process(202,201)
    unknown=process(999,1)
    seen={worker["process_key"],aux["process_key"]}
    first=process_snapshot(parent,set(),lambda _:raw(parent,worker,aux,unknown))
    assert len(first["inference_workers"])==len(first["auxiliary_processes"])==1
    assert len(first["selected_ps"])==3 and all("999" not in row for row in first["selected_ps"])
    renamed={**worker,"comm":"renamed"}
    second=process_snapshot(parent,seen,lambda _:raw(parent,renamed,aux))
    assert second["tracked_other"]==[renamed] and len(second["inference_workers"])==1
    orphan={**aux,"ppid":1,"comm":"renamed"}
    third=process_snapshot(parent,seen,lambda _:raw(parent,orphan))
    assert third["orphan_models"]==[orphan] and third["absent_model_keys"]==[worker["process_key"]]
    row=sample(1,1.)
    row["processes"]=third
    assert safety_reason([row])=="owned_orphan_detected"


def test_pid_reuse_does_not_revive_an_old_birth():
    parent, old, new=process(),process(201,100),process(201,100,minute=1)
    result=process_snapshot(parent,{old["process_key"]},lambda _:raw(parent,new))
    assert result["absent_model_keys"]==[old["process_key"]]
    assert set(result["seen_model_keys"])=={old["process_key"],new["process_key"]}


def test_identify_fallback_requires_current_phase_sample_and_parent(tmp_path):
    monitor=SafetyMonitor(tmp_path,service=process(),command=Mock(side_effect=RuntimeError("synthetic")))
    old=sample(0,1.)
    old["processes"]["models"]=[process(201,100)]
    monitor.samples.append(old)
    with pytest.raises(SafetyError,match="process_birth_unobserved"):
        monitor.identify(201,not_before=10.)
    current=sample(1,12.)
    current["processes"]["models"]=[process(201,999,minute=1)]
    monitor.samples.append(current)
    with pytest.raises(SafetyError): monitor.identify(201,not_before=10.)
    current["processes"]["models"][0]["ppid"]=100
    assert monitor.identify(201,not_before=10.)["process_key"]==process(201,100,minute=1)["process_key"]


def test_sampling_retains_global_indices_seen_and_no_files(tmp_path):
    clock=[1.]
    worker=process(201,100)
    table=[raw(process(),worker)]
    monitor=SafetyMonitor(tmp_path,service=process(),clock=lambda:clock[0],system=lambda:system(clock[0]),
                          command=lambda _:table[0],disk_free=lambda:2*1024*MIB,history_limit=16)
    for index in range(30):
        if index==1: table[0]=raw(process(),{**worker,"comm":"renamed"})
        if index==2: table[0]=raw(process())
        monitor.sample_once()
        clock[0]+=1.1
    assert monitor.index==30 and len(monitor.samples)==16
    assert monitor.samples[0]["index"]==14 and monitor.samples[-1]["index"]==29
    assert monitor.seen=={worker["process_key"]}
    assert monitor.samples[-1]["processes"]["absent_model_keys"]==[worker["process_key"]]
    assert list(tmp_path.iterdir())==[]


def test_thrashing_warning_unknown_and_resource_gates():
    rows=[sample(i,i+1.,pages=i*30000) for i in range(4)]
    assert swap_rate(rows[0],rows[1])==122880000
    assert safety_reason(rows)=="swap_thrashing"
    rows[0]["system"]["status"]="unknown"
    assert safety_reason(rows)=="system_interval_unknown"
    assert safety_reason([sample(0,1.,pressure=2)]) is None
    assert safety_reason([sample(0,1.,pressure=4)])=="critical_memory_pressure"
    row=sample(0,1.)
    row["processes"]["parent"]["current_rss_bytes"]=1024*MIB+1
    assert safety_reason([row])=="parent_rss_limit"
    row=sample(0,1.)
    row["disk_free_bytes"]=512*MIB-1
    assert safety_reason([row])=="disk_budget_exceeded"


def test_quiet_requires_ten_new_samples_not_previous_window(tmp_path):
    clock=[20.]
    monitor=SafetyMonitor(tmp_path,service=process(),clock=lambda:clock[0])
    monitor.samples.extend(sample(i,clock[0]-(109-i)*1.1) for i in range(100,110))
    count=[0]
    def feed(timeout=None):
        count[0]+=1; clock[0]+=1.1
        monitor.samples.append(sample(109+count[0],clock[0]))
    with patch.object(monitor.updated,"wait",side_effect=feed):
        assert monitor.wait_ready(80.)==list(range(110,120))
    assert count[0]==10
    with pytest.raises(Revoked): monitor.wait_ready(80.,lambda:True)
    assert monitor.reason is None


def test_wait_absent_requires_fresh_sample_and_latest_known_event(tmp_path):
    clock=[10.]
    monitor=SafetyMonitor(tmp_path,service=process(),clock=lambda:clock[0])
    first,second=process(201,100)["process_key"],process(202,100)["process_key"]
    monitor.seen.update((first,second))
    monitor.samples.append(sample(3,10.,seen=(first,)))
    def feed(timeout=None):
        clock[0]+=1.1
        monitor.samples.append(sample(4,clock[0],seen=(first,second)))
    monitor.reason="critical_memory_pressure"
    with patch.object(monitor.updated,"wait",side_effect=feed):
        value=monitor.wait_absent(3,20.)
    assert value=={"sample_index":4,"absent_model_keys":sorted((first,second))}


def test_resource_unknown_and_observer_failure_latch(tmp_path):
    blocked=[]
    monitor=SafetyMonitor(tmp_path,service=process(),on_block=blocked.append)
    monitor.observe_resources({"peak_rss_bytes":1,"mlx_peak_bytes":1,"elapsed_seconds":float("nan")})
    assert blocked==["model_resource_unknown"]
    monitor.observe_resources({"peak_rss_bytes":1,"mlx_peak_bytes":1,"elapsed_seconds":0})
    assert monitor.reason=="model_resource_unknown"
    monitor=SafetyMonitor(tmp_path,service=process(),observer=Mock(side_effect=RuntimeError("private synthetic error")))
    monitor.emit("runtime_event",{"type":"synthetic"})
    assert monitor.reason=="observer_callback_failed"


def test_finish_stops_thread_and_reports_false_when_absence_unconfirmed(tmp_path):
    output=[]
    monitor=SafetyMonitor(tmp_path,service=process(),observer=lambda kind,payload:output.append((kind,payload)))
    monitor.thread=Mock()
    monitor.thread.is_alive.return_value=False
    with patch.object(monitor,"wait_absent",side_effect=SafetyError("owned_process_exit_unconfirmed")):
        with pytest.raises(SafetyError): monitor.finish()
    assert monitor.stopped.is_set() and monitor.thread.join.called
    assert output[-1][1]["type"]=="monitor_terminal" and output[-1][1]["all_seen_absent"] is False
