"""Opt-in, read-only local memory observations; never accepts model text."""
from __future__ import annotations

from datetime import datetime, timezone
import os
import re
import subprocess
import time


def _command(arguments):
    return subprocess.run(arguments, capture_output=True, text=True, timeout=2, check=True).stdout


def current_rss(child_pid, parent_pid=None, command=_command):
    parent_pid = os.getpid() if parent_pid is None else parent_pid
    started = time.monotonic()
    sample = {"status": "unknown", "sampled_at": datetime.now(timezone.utc).isoformat(),
              "monotonic": time.monotonic(), "child_pid": child_pid, "parent_pid": parent_pid,
              "child_current_rss_bytes": None, "parent_current_rss_bytes": None, "raw_ps": None}
    try:
        if any(type(pid) is not int or pid <= 0 for pid in (child_pid, parent_pid)):
            raise ValueError("invalid_pid")
        raw = command(["/bin/ps", "-o", "pid=,rss=", "-p", f"{child_pid},{parent_pid}"])
        sample["raw_ps"] = raw
        parsed = {}
        for line in raw.splitlines():
            match = re.fullmatch(r"\s*(\d+)\s+(\d+)\s*", line)
            if not match or int(match[1]) in parsed:
                raise ValueError("invalid_rss_response")
            parsed[int(match[1])] = int(match[2]) * 1024
        if set(parsed) != {child_pid, parent_pid} or min(parsed.values()) <= 0:
            raise ValueError("missing_rss")
        sample.update(status="observed", child_current_rss_bytes=parsed[child_pid], parent_current_rss_bytes=parsed[parent_pid])
    except Exception as error:
        sample["error_type"] = type(error).__name__
    sample.update(monotonic=time.monotonic(), sampled_at=datetime.now(timezone.utc).isoformat())
    sample["sampling_seconds"] = sample["monotonic"] - started
    return sample


def system_memory(command=_command):
    started = time.monotonic()
    sample = {"status": "unknown", "sampled_at": datetime.now(timezone.utc).isoformat(),
              "monotonic": time.monotonic(), "pressure_level": None, "page_size": None,
              "swapins": None, "swapouts": None, "pressure_raw": None, "vm_stat_raw": None}
    try:
        pressure = command(["/usr/sbin/sysctl", "-n", "kern.memorystatus_vm_pressure_level"])
        sample["pressure_raw"] = pressure
        raw = command(["/usr/bin/vm_stat"])
        sample.update(pressure_raw=pressure, vm_stat_raw=raw)
        level = int(pressure.strip())
        page = re.search(r"page size of (\d+) bytes", raw)
        incoming = re.search(r"^Swapins:\s*(\d+)\.?\s*$", raw, re.MULTILINE)
        outgoing = re.search(r"^Swapouts:\s*(\d+)\.?\s*$", raw, re.MULTILINE)
        if level not in (1, 2, 4) or not page or not incoming or not outgoing or int(page[1]) <= 0:
            raise ValueError("unsupported_memory_observation")
        sample.update(status="observed", pressure_level=level, page_size=int(page[1]), swapins=int(incoming[1]), swapouts=int(outgoing[1]))
    except Exception as error:
        sample["error_type"] = type(error).__name__
    sample.update(monotonic=time.monotonic(), sampled_at=datetime.now(timezone.utc).isoformat())
    sample["sampling_seconds"] = sample["monotonic"] - started
    return sample
