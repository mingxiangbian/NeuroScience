"""Read-only, owned-process monitoring and append-only experiment support."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from run_soak import canonical, digest, environment_metadata, once, read_job
from topicweb.telemetry import system_memory
from topicweb.worker import ProcessRunner

PRODUCTION_DEPENDS = (
    "requirements.txt", "requirements-lock.txt", "start.py", "topicweb/__init__.py",
    "topicweb/app.py", "topicweb/core.py", "topicweb/adapters.py", "topicweb/store.py",
    "topicweb/worker.py", "topicweb/inference_process.py", "topicweb/telemetry.py",
    "static/index.html", "static/app.js", "static/app.css",
)
DEPENDS = PRODUCTION_DEPENDS + (
    "scripts/run_soak.py", "scripts/bounded_runtime_support.py", "scripts/run_bounded_runtime.py",
    "scripts/verify_bounded_runtime.py", "tests/test_bounded_runtime.py", "tests/test_verify_bounded_runtime.py",
    "scripts/verify_local.py", "scripts/verify_discourse_validation.py",
)


class SupportError(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise SupportError(code)


def now():
    return datetime.now(timezone.utc).isoformat()


def _ps(arguments):
    return subprocess.run(arguments, capture_output=True, text=True, timeout=2, check=True,
                          env={**os.environ, "LC_ALL": "C"}).stdout


def parse_processes(raw):
    rows = {}
    for line in raw.splitlines():
        parts = line.split(None, 8)
        require(len(parts) == 9 and all(part.isdigit() for part in parts[:3]), "process_table_unknown")
        pid, parent, rss = map(int, parts[:3])
        require(pid not in rows, "process_table_duplicate")
        started = " ".join(parts[3:8])
        datetime.strptime(started, "%a %b %d %H:%M:%S %Y")
        rows[pid] = {"pid": pid, "ppid": parent, "current_rss_bytes": rss*1024,
                     "start_time": started, "process_key": f"{pid}|{started}",
                     "comm": Path(parts[8]).name, "raw": line}
    return rows


def process_identity(pid, command=_ps):
    rows = parse_processes(command(["/bin/ps", "-p", str(pid), "-o", "pid=,ppid=,rss=,lstart=,comm="]))
    require(pid in rows, "process_identity_unavailable")
    return rows[pid]


def process_snapshot(service, seen, command=_ps):
    """The complete process table stays in memory; only owned rows are returned."""
    result = {"status": "unknown", "parent": None, "models": [], "tracked_other": [], "inference_workers": [], "auxiliary_processes": [], "orphan_models": [],
              "seen_model_keys": sorted(seen), "absent_model_keys": [], "selected_ps": []}
    try:
        table = parse_processes(command(["/bin/ps", "-axo", "pid=,ppid=,rss=,lstart=,comm="]))
        parent = table.get(service["pid"])
        require(parent is not None and parent["process_key"] == service["process_key"]
                and parent["comm"] == service["comm"], "service_identity_drift")
        owned = {service["pid"]}
        while True:
            extra = {pid for pid, row in table.items() if row["ppid"] in owned} - owned
            if not extra:
                break
            owned.update(extra)
        models = [row for pid, row in table.items() if pid in owned and pid != service["pid"]
                  and row["comm"].lower().startswith("python")]
        seen.update(row["process_key"] for row in models)
        current = {row["process_key"]: row for row in table.values()}
        orphans = [current[key] for key in sorted(seen) if key in current and current[key]["pid"] not in owned]
        python_keys={row["process_key"] for row in models}
        tracked=[current[key] for key in sorted(seen) if key in current and current[key]["pid"] in owned
                 and current[key]["pid"]!=service["pid"] and key not in python_keys]
        retained_owned=[*models,*tracked]
        live={row["process_key"] for row in [*retained_owned,*orphans]}
        absent=seen-set(current)
        require(len(live)==len(retained_owned)+len(orphans) and not live.intersection(absent)
                and live|absent==seen,"known_process_partition_unknown")
        selected = [parent, *retained_owned, *orphans]
        result.update(status="observed", parent={key:value for key,value in parent.items() if key != "raw"},
                      models=[{key:value for key,value in row.items() if key != "raw"} for row in models],
                      tracked_other=[{key:value for key,value in row.items() if key != "raw"} for row in tracked],
                      inference_workers=[{key:value for key,value in row.items() if key != "raw"} for row in retained_owned if row["ppid"]==service["pid"]],
                      auxiliary_processes=[{key:value for key,value in row.items() if key != "raw"} for row in retained_owned if row["ppid"]!=service["pid"]],
                      orphan_models=[{key:value for key,value in row.items() if key != "raw"} for row in orphans],
                      seen_model_keys=sorted(seen), absent_model_keys=sorted(absent),
                      selected_ps=[row["raw"] for row in selected])
    except Exception as error:
        result["error_type"] = type(error).__name__
    return result


def swap_rate(previous, current):
    first, last = previous["system"], current["system"]
    if first.get("status") != "observed" or last.get("status") != "observed":
        return None
    delta = last["monotonic"]-first["monotonic"]
    if not 0 < delta <= 3 or first["page_size"] != last["page_size"]:
        return None
    incoming, outgoing = last["swapins"]-first["swapins"], last["swapouts"]-first["swapouts"]
    if incoming < 0 or outgoing < 0:
        return None
    return (incoming+outgoing)*last["page_size"]/delta


def safety_reason(samples):
    row = samples[-1]
    system, processes = row["system"], row["processes"]
    if system.get("status") != "observed" or processes.get("status") != "observed":
        return "monitoring_unknown"
    if system["pressure_level"] == 4:
        return "critical_memory_pressure"
    if processes["orphan_models"]:
        return "owned_orphan_detected"
    retained_owned=[*processes["models"],*processes.get("tracked_other",[])]
    if sum(model["ppid"]==processes["parent"]["pid"] for model in retained_owned) > 1:
        return "concurrent_model_processes"
    if processes["parent"]["current_rss_bytes"] > 1024**3:
        return "parent_rss_limit"
    if any(model["current_rss_bytes"] > 12*1024**3 for model in retained_owned):
        return "child_rss_limit"
    if row["disk_free_bytes"] < 512*1024**2:
        return "disk_budget_exceeded"
    if len(samples) > 1 and swap_rate(samples[-2], row) is None:
        return "system_interval_unknown"
    if len(samples) >= 4:
        rates = [swap_rate(first,last) for first,last in zip(samples[-4:-1],samples[-3:])]
        if all(rate is not None and rate >= 100*1024**2 for rate in rates):
            return "swap_thrashing"
    return None


def quiet_indices(samples, after_index=-1):
    if len(samples) < 10:
        return None
    window = samples[-10:]
    if window[0]["index"] <= after_index:
        return None
    for row in window:
        process = row["processes"]
        if (row["system"].get("status") != "observed" or row["system"]["pressure_level"] != 1
                or process.get("status") != "observed" or process["models"] or process.get("tracked_other",[]) or process["orphan_models"]
                or process["seen_model_keys"] != process["absent_model_keys"]):
            return None
    if any((rate := swap_rate(first,last)) is None or rate >= 10*1024**2 for first,last in zip(window,window[1:])):
        return None
    return [row["index"] for row in window]


def recorded_process_keys(path):
    keys,unknown=set(),False
    for line in Path(path).read_text().splitlines(keepends=True):
        if not line.endswith("\n"):
            continue
        event=json.loads(line)
        pid,key=event.get("pid"),event.get("process_key")
        if pid is None:
            require(key is None,"event_birth_identity_invalid")
            continue
        if key is None:
            unknown=True
            continue
        require(type(pid)is int and isinstance(key,str) and key.startswith(f"{pid}|"),"event_birth_identity_invalid")
        datetime.strptime(key.split("|",1)[1],"%a %b %d %H:%M:%S %Y")
        keys.add(key)
    return keys,unknown


class Monitor:
    def __init__(self, path, service, *, system=system_memory, processes=process_snapshot, clock=time.monotonic):
        self.path, self.service = Path(path), service
        self.events_path=Path(service["bench_root"]).parent/"process-events.jsonl"
        self.system, self.processes, self.clock = system, processes, clock
        self.samples, self.seen, self.reason, self.job_id = [], set(), None, None
        self.stopped, self.updated = threading.Event(), threading.Condition()
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def set_job(self, identifier):
        self.job_id = identifier

    def _loop(self):
        try:
            with self.path.open("x") as output:
                while not self.stopped.is_set():
                    started = self.clock()
                    system=self.system()
                    keys,unknown_birth=recorded_process_keys(self.events_path)
                    self.seen.update(keys)
                    processes=self.processes(self.service,self.seen)
                    if unknown_birth:
                        processes.update(status="unknown",error_type="UnobservedBirthIdentity")
                    row = {"index": len(self.samples), "job_id": self.job_id, "started_monotonic": started,
                           "system": system, "processes": processes,
                           "disk_free_bytes": shutil.disk_usage(self.path.parent).free}
                    row.update(monotonic=self.clock(), sampled_at=now())
                    with self.updated:
                        self.samples.append(row)
                        self.reason = self.reason or safety_reason(self.samples)
                        output.write(canonical(row)+"\n"); output.flush()
                        self.updated.notify_all()
                    self.stopped.wait(1.0)
        except Exception:
            with self.updated:
                self.reason = self.reason or "monitoring_failed"
                self.updated.notify_all()

    def start(self):
        self.thread.start()
        with self.updated:
            self.updated.wait_for(lambda: bool(self.samples) or self.reason, timeout=7)
        require(self.samples or self.reason, "monitor_start_timeout")

    def finish(self):
        self.stopped.set(); self.thread.join(timeout=7)
        require(not self.thread.is_alive(), "monitor_shutdown_timeout")


def wait_ready(monitor, deadline, timeout=60):
    boundary = monitor.samples[-1]["index"] if monitor.samples else -1
    end = min(deadline, time.monotonic()+timeout)
    while time.monotonic() < end:
        require(not monitor.reason, monitor.reason or "monitoring_failed")
        with monitor.updated:
            indices = quiet_indices(monitor.samples,boundary)
            if indices:
                return indices
            monitor.updated.wait(timeout=min(1,max(0,end-time.monotonic())))
    raise SupportError("quiet_window_not_ready")


def wait_absent(monitor, after_index, deadline, timeout=15):
    end = min(deadline,time.monotonic()+timeout)
    while time.monotonic() < end:
        with monitor.updated:
            if monitor.samples:
                row = monitor.samples[-1]
                process = row["processes"]
                known,unknown_birth=recorded_process_keys(monitor.events_path)
                if (row["index"] > after_index and process.get("status") == "observed" and not process["models"]
                        and not process.get("tracked_other",[]) and not process["orphan_models"] and process["seen_model_keys"] == process["absent_model_keys"]
                        and not unknown_birth and known <= set(process["absent_model_keys"])):
                    return {"sample_index":row["index"], "absent_model_keys":process["absent_model_keys"]}
            monitor.updated.wait(timeout=min(1,max(0,end-time.monotonic())))
    raise SupportError("owned_process_exit_unconfirmed")


def cancel_and_confirm(job_id, api, monitor, timeout=15):
    started=time.monotonic()
    deadline, initial = started+timeout, monitor.samples[-1]["index"] if monitor.samples else -1
    result = {"job_id":job_id,"normal_exit":False,"terminal_confirmed":False,"models_absent_confirmed":False,"exit_observation":None,
              "started_monotonic":started,"max_seconds":timeout}
    try:
        api(f"jobs/{job_id}/cancel",{},timeout=max(.01,deadline-time.monotonic()))
        while time.monotonic() < deadline:
            job = api("jobs/"+job_id,timeout=max(.01,deadline-time.monotonic()))["job"]
            if job["state"] in {"completed","completed_with_fallback","failed","cancelled"}:
                result.update(terminal_confirmed=True, job_state=job["state"], completed_items=job["completed_items"],total_items=job["total_items"])
                break
            time.sleep(.2)
        result["exit_observation"] = wait_absent(monitor,initial,deadline,timeout)
        result["models_absent_confirmed"] = True
    except Exception as error:
        result["error_code"] = str(error) if isinstance(error,SupportError) else type(error).__name__
    result["ended_monotonic"]=time.monotonic()
    return result


def load_service(run_dir, port):
    path = Path(run_dir)/"service.json"
    require(not any(p.is_symlink() for p in (path,*path.parents)), "service_path_symlink")
    service = json.loads(path.read_text())
    require(service["root"] == str(ROOT) and service["bench_root"] == str(Path(run_dir)/"bench") and service["port"] == port, "service_identity_contract")
    require(process_identity(service["pid"])["process_key"] == service["process_key"], "service_process_changed")
    return service


def make_runner_factory(events_path):
    def event(kind, owner, returncode=None, normal=False):
        value = {"type":kind,"job_id":owner.job_id,"pid":getattr(getattr(owner,"process",None),"pid",None),
                 "process_key":owner.process_key,"monotonic":time.monotonic(),"at":now(),"returncode":returncode,"normal_exit":normal}
        with Path(events_path).open("a") as output:
            output.write(canonical(value)+"\n");output.flush()
    class ObservedRunner(ProcessRunner):
        def __init__(self,job,**kwargs):
            self.job_id, self.process_key, self.exit_recorded = job["id"],None,False
            event("constructor_started",self)
            try:
                super().__init__(job,**kwargs)
                self.process_key = process_identity(self.process.pid)["process_key"]
                event("ready",self)
            except BaseException:
                self.close()
                raise
        def close(self):
            process = getattr(self,"process",None)
            if process is not None and self.process_key is None:
                try:
                    self.process_key = process_identity(process.pid)["process_key"]
                except Exception:
                    pass
            super().close()
            if process is not None and process.returncode is not None and not self.exit_recorded:
                event("process_exit",self,process.returncode)
                self.exit_recorded = True
        def finish(self):
            super().finish()
            event("final_gate_passed",self,self.process.returncode,True)
    return ObservedRunner


def serve_app(run_dir,experiment_id,port):
    run_dir = Path(run_dir)
    require(not any(p.is_symlink() for p in (run_dir,*run_dir.parents)), "service_path_symlink")
    os.umask(0o077);run_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    identity = process_identity(os.getpid())
    identity.pop("raw")
    service = {**identity,"experiment_id":experiment_id,"root":str(ROOT),"bench_root":str(run_dir/"bench"),"port":port,"created_at":now()}
    once(run_dir/"service.json",service)
    with (run_dir/"process-events.jsonl").open("x"):
        pass
    os.environ["TOPICWEB_TELEMETRY"] = "1"
    from topicweb.app import create_app
    import uvicorn
    uvicorn.run(create_app(private_dir=run_dir/"bench",runner_factory=make_runner_factory(run_dir/"process-events.jsonl")),
                host="127.0.0.1",port=port,access_log=False)
    return 0
