"""EXP-082 observer: run the original bridge, without replacing its inference.

Only the two hash-pinned Python files below are traced. No frame arguments,
return values, exception strings, model arrays, or input text enter the journal.
"""
from __future__ import annotations

import dis
import hashlib
import json
import os
from pathlib import Path
import resource
import stat
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "topicweb/inference_process.py"
RUNTIME = ROOT.parent / "experiments/stack-overflow-emotion-gold/oof-router/runtime_exp066.py"
STAGE_PATH = ROOT / "private/validation/exp-082/attempt-1/stages.jsonl"
SOURCE_HASHES = {
    BRIDGE: "45690716a8cd25688a1d7f64eba437acf75dc90cf7caf478c3a38a73335f1ddd",
    RUNTIME: "4cd1c226d002e713c324bda61dcad841434af25db2bd7ccf2b04742a3f27e689",
}

# Keys are exact (filename, qualified function name, definition line).
ENGINE = (str(BRIDGE), "build_real_engine", 378)
REQUEST = (str(BRIDGE), "JobInference.predict", 252)
FACTORY = (str(BRIDGE), "build_real_engine.<locals>.m3_factory", 389)
M3_INIT = (str(RUNTIME), "MlxM3Backend.__init__", 229)
M3_PREDICT = (str(RUNTIME), "MlxM3Backend.predict_probabilities", 323)
FUNCTION_STAGES = {
    ENGINE: "engine_build",
    REQUEST: "request_predict",
    FACTORY: "m3_factory",
    (str(RUNTIME), "TorchM1Backend.__init__", 144): "m1_load",
    (str(RUNTIME), "TorchM1Backend.predict_probabilities", 168): "m1_predict",
    M3_INIT: "m3_backend_init",
    M3_PREDICT: "m3_predict",
}
# A line event occurs BEFORE that original line executes. The end at the next
# line means the preceding call returned, not that observation evaluated it.
LINE_ACTIONS = {
    FACTORY: {
        390: (("begin", "mlx_import"),),
        392: (("end", "mlx_import"),),
        395: (("point", "mlx_limits_configured"),),
    },
    M3_INIT: {
        244: (("begin", "adapter_head_numpy_load"),),
        246: (("end", "adapter_head_numpy_load"),),
        257: (("begin", "base_load"),),
        258: (("end", "base_load"),),
        275: (("begin", "lora_setup"),),
        316: (("end", "lora_setup"), ("begin", "adapter_load")),
        317: (("end", "adapter_load"), ("begin", "head_load")),
        318: (("end", "head_load"),),
        321: (("begin", "adapter_head_eval"),),
    },
    M3_PREDICT: {
        324: (("begin", "m3_tokenization"),),
        325: (("end", "m3_tokenization"), ("begin", "first_forward")),
        329: (("end", "first_forward"),),
    },
}


class ObservationError(RuntimeError):
    """Fixed generic failure, never a library exception or input string."""


def check_sources() -> None:
    for path, expected in SOURCE_HASHES.items():
        info = path.lstat()
        if (path.is_symlink() or not stat.S_ISREG(info.st_mode)
                or stat.S_IMODE(info.st_mode) != 0o644
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
            raise ObservationError("diagnostic_source_identity")


class StageJournal:
    """Append to the parent's empty, existing private file; never create it."""

    def __init__(self, path: Path):
        if not path.is_absolute() or any(part.is_symlink() for part in (path, *path.parents)):
            raise ObservationError("diagnostic_journal_identity")
        before = path.lstat()
        if (not stat.S_ISREG(before.st_mode) or stat.S_IMODE(before.st_mode) != 0o600
                or before.st_size != 0 or before.st_nlink != 1):
            raise ObservationError("diagnostic_journal_identity")
        self.fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_CLOEXEC)
        after = os.fstat(self.fd)
        if ((before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
                or not stat.S_ISREG(after.st_mode) or stat.S_IMODE(after.st_mode) != 0o600
                or after.st_size != 0 or after.st_nlink != 1):
            os.close(self.fd)
            raise ObservationError("diagnostic_journal_identity")
        self.seq = 0

    def emit(self, kind: str, stage: str, ordinal: int | None, memory: dict) -> None:
        event = {"seq": self.seq, "pid": os.getpid(), "monotonic": time.monotonic(),
                 "kind": kind, "stage": stage, "item_ordinal": ordinal, "memory": memory}
        data = (json.dumps(event, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        while data:
            written = os.write(self.fd, data)
            if written <= 0:
                raise ObservationError("diagnostic_journal_write")
            data = data[written:]
        os.fsync(self.fd)
        self.seq += 1

    def close(self) -> None:
        os.close(self.fd)


class MemoryObserver:
    def __init__(self):
        self.limits_configured = False

    def read(self) -> dict:
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        result = {"rss_peak_bytes": int(rss if sys.platform == "darwin" else rss * 1024),
                  "mlx_status": "not_loaded", "active_bytes": None,
                  "cache_bytes": None, "peak_bytes": None}
        # Looking in sys.modules does not import or initialize MLX.
        mx = sys.modules.get("mlx.core")
        if mx is None:
            return result
        result["mlx_status"] = "not_sampled"
        if not self.limits_configured:
            return result
        try:
            values = [mx.get_active_memory(), mx.get_cache_memory(), mx.get_peak_memory()]
            if any(type(value) is not int or value < 0 for value in values):
                return result
        except Exception:
            # A missing counter is unknown, never an observed zero.
            return result
        result.update(mlx_status="observed", active_bytes=values[0],
                      cache_bytes=values[1], peak_bytes=values[2])
        return result


class StageTrace:
    def __init__(self, journal, memory=None, functions=None, lines=None):
        self.journal = journal
        self.memory = memory if memory is not None else MemoryObserver()
        self.functions = FUNCTION_STAGES if functions is None else functions
        self.lines = LINE_ACTIONS if lines is None else lines
        self.filenames = {key[0] for key in self.functions}
        self.frames = {}
        self.ordinal = None
        self.request_count = 0

    def emit(self, kind: str, stage: str) -> None:
        memory = self.memory.read()
        self.journal.emit(kind, stage, self.ordinal, memory)
        # Preserve the observed fact before interrupting the next original step.
        if (memory["rss_peak_bytes"] > 12 * 1024**3
                or (memory["mlx_status"] == "observed" and memory["peak_bytes"] > 10_000_000_000)):
            raise ObservationError("diagnostic_resource_limit")
        if getattr(self.memory, "limits_configured", False) and memory["mlx_status"] != "observed":
            raise ObservationError("diagnostic_memory_unknown")

    def __call__(self, frame, event, _arg):
        if event == "call":
            code = frame.f_code
            if code.co_filename not in self.filenames:
                return None
            key = (code.co_filename, code.co_qualname, code.co_firstlineno)
            stage = self.functions.get(key)
            if stage is None:
                return None
            if stage == "request_predict":
                if self.ordinal is not None or self.request_count >= 7:
                    raise ObservationError("diagnostic_request_count")
                # Parent fixes item IDs and order; no input/frame locals are read.
                self.ordinal = self.request_count
                self.request_count += 1
            self.frames[id(frame)] = {"key": key, "open": [stage], "visited": set()}
            self.emit("begin", stage)
            return self
        state = self.frames.get(id(frame))
        if state is None:
            return None
        if event == "line" and frame.f_lineno not in state["visited"]:
            state["visited"].add(frame.f_lineno)
            for kind, stage in self.lines.get(state["key"], {}).get(frame.f_lineno, ()):
                if kind == "begin":
                    state["open"].append(stage)
                elif kind == "end":
                    if state["open"][-1] != stage:
                        raise ObservationError("diagnostic_stage_order")
                    state["open"].pop()
                elif stage == "mlx_limits_configured":
                    self.memory.limits_configured = True
                self.emit(kind, stage)
        elif event == "return":
            # Python also reports return(None) when unwinding an exception.
            # Inspect the instruction, NEVER the return value or exception/locals.
            opcode = dis.opname[frame.f_code.co_code[frame.f_lasti]]
            normal = opcode in {"RETURN_VALUE", "RETURN_CONST"}
            stage = state["open"][0]
            for opened in reversed(state["open"]):
                self.emit("end" if normal else "error", opened)
            self.frames.pop(id(frame))
            if stage == "request_predict":
                if normal:
                    self.emit("point", "predict_complete")
                self.ordinal = None
        return self


def main() -> int:
    journal = None
    prior_trace = sys.gettrace()
    try:
        if prior_trace is not None:
            raise ObservationError("diagnostic_existing_trace")
        stage_path = Path(os.environ["TOPICWEB_EXP082_STAGE_PATH"])
        if stage_path != STAGE_PATH or not stage_path.is_absolute():
            raise ObservationError("diagnostic_journal_path")
        check_sources()
        journal = StageJournal(stage_path)
        sys.path.insert(0, str(ROOT))
        from topicweb import inference_process
        sys.settrace(StageTrace(journal))
        return inference_process.main()
    except Exception:
        # Before the original bridge redirects output, this is still text-free.
        os.write(2, b"EXP082 diagnostic observer failed\n")
        return 1
    finally:
        sys.settrace(prior_trace)
        if journal is not None:
            journal.close()


if __name__ == "__main__":
    raise SystemExit(main())
