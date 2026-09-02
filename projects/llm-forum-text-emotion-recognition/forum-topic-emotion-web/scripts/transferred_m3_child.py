"""EXP-084: unchanged router/M3 consuming this run's sealed M1 receipts."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from topicweb import inference_process as bridge

RUN = ROOT / "private/validation/exp-084/attempt-1"
TRANSFER_PATH = RUN / "transfer.json"
STAGE_PATH = RUN / "stages.jsonl"
READY_PATH = RUN / "m3-ready.json"
OBSERVER_PATH = ROOT / "scripts/diagnostic_m3_child.py"
OBSERVER_SHA256 = "6dc0da353b1f2d9da48151c5d6068279e5ed3bec2e6516e212bb098248548740"
STRATEGY = "m1-receipt-transfer-v1"
SOURCE_RESULTS_PATH = "private/validation/exp-084/attempt-1/m1-results.jsonl"


def require(condition, code):
    if not condition:
        raise bridge.InferenceError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def hexhash(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def load_observer():
    require(not any(path.is_symlink() for path in (OBSERVER_PATH, *OBSERVER_PATH.parents))
            and OBSERVER_PATH.is_file() and sha(OBSERVER_PATH.read_bytes()) == OBSERVER_SHA256,
            "inherited_observer_identity")
    spec = importlib.util.spec_from_file_location("exp084_inherited_observer", OBSERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_transfer(expected_fingerprint):
    import numpy as np

    expected_sha = os.environ.get("TOPICWEB_EXP084_TRANSFER_SHA256")
    require(hexhash(expected_sha), "transfer_hash_missing")
    require(not any(path.is_symlink() for path in (TRANSFER_PATH, *TRANSFER_PATH.parents)), "transfer_path_identity")
    before = bridge._file_state(TRANSFER_PATH)
    require(stat.S_ISREG(before[4]) and stat.S_IMODE(before[4]) == 0o600, "transfer_file_mode")
    raw = TRANSFER_PATH.read_bytes()
    require(sha(raw) == expected_sha and bridge._file_state(TRANSFER_PATH) == before, "transfer_identity_drift")
    value = bridge._json(raw.decode("utf-8"))
    require(set(value) == {"experiment_id", "attempt", "source_job_id", "source_phase", "source_results_path",
                           "source_results_sha256", "source_results_count", "fingerprint", "entries"}, "transfer_schema")
    require(value["experiment_id"] == "EXP-084" and type(value["attempt"]) is int and value["attempt"] == 1
            and value["source_job_id"] == "exp084-m1-prelude" and value["source_phase"] == "m1_prelude"
            and value["source_results_path"] == SOURCE_RESULTS_PATH
            and type(value["source_results_count"]) is int and value["source_results_count"] == 340
            and hexhash(value["source_results_sha256"]) and value["fingerprint"] == expected_fingerprint,
            "transfer_source_contract")
    entries = value["entries"]
    require(isinstance(entries, list) and len(entries) == 7, "transfer_entry_count")
    cache = {}
    fingerprint = sha(canonical({"base_fingerprint": expected_fingerprint, "strategy": STRATEGY, "transfer_sha256": expected_sha}))
    for ordinal, entry in enumerate(entries):
        require(isinstance(entry, dict) and set(entry) == {"ordinal", "input_sha256", "m1_probabilities", "tokenlengths", "source_result_sha256"}
                and type(entry["ordinal"]) is int and entry["ordinal"] == ordinal
                and hexhash(entry["input_sha256"]) and hexhash(entry["source_result_sha256"]), "transfer_entry_schema")
        probabilities = entry["m1_probabilities"]
        require(isinstance(probabilities, list) and len(probabilities) == 6
                and all(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1 for value in probabilities),
                "transfer_probabilities_invalid")
        array = np.ascontiguousarray(probabilities, dtype=np.float32)
        require(array.tolist() == probabilities, "transfer_float32_not_lossless")
        array.setflags(write=False)
        tokens = entry["tokenlengths"]
        require(isinstance(tokens, dict) and set(tokens) == {"m1"} and isinstance(tokens["m1"], dict)
                and set(tokens["m1"]) == {"input_tokens", "used_tokens", "truncated"}, "transfer_tokens_schema")
        metadata = tokens["m1"]
        full, used = metadata["input_tokens"], metadata["used_tokens"]
        require(type(full) is int and type(used) is int and 1 <= used <= 256 and full >= used
                and used == min(full, 256) and type(metadata["truncated"]) is bool
                and metadata["truncated"] == (full > used), "transfer_tokens_invalid")
        key = fingerprint + ":" + entry["input_sha256"]
        require(key not in cache, "transfer_duplicate_input")
        cache[key] = (array, used, dict(metadata))
    return value, cache, fingerprint, expected_sha, before


def write_ready(proof):
    require(not any(path.is_symlink() for path in (READY_PATH, *READY_PATH.parents)), "ready_path_identity")
    descriptor = os.open(READY_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(canonical(proof) + "\n")
        output.flush()
        os.fsync(output.fileno())


class TransferEngine(bridge.JobInference):
    def ready(self):
        require(self.m1 is None and self.trace.m1_backend_calls == 0 and len(self.m1_cache) == 7, "m1_absence_not_proven")
        proof = {"experiment_id": "EXP-084", "pid": os.getpid(), "monotonic": time.monotonic(),
                 "transfer_sha256": self.transfer_sha, "cache_entries": len(self.m1_cache),
                 "cache_input_sha256s": self.input_hashes, "m1_instance_absent": True,
                 "m1_backend_calls": self.trace.m1_backend_calls, "fingerprint": self.fingerprint,
                 "base_fingerprint": self.base_fingerprint, "strategy": STRATEGY,
                 "modelstatus": {"m1": "receipt_replay_not_loaded", "m3": "not_loaded", "mode": self.mode}}
        write_ready(proof)
        value = super().ready()
        value["modelstatus"] = proof["modelstatus"]
        value.update(m1_instance_absent=True, base_fingerprint=self.base_fingerprint,
                     transfer_sha256=self.transfer_sha, cache_entries=7, cache_scope="current_run_m1_receipt_transfer")
        return value

    def predict(self, request):
        # Refuse a miss BEFORE original predict increments an attempted M1 call.
        self.last_counters = {name: 0 for name in self.totals}
        require(self.m1 is None and self.trace.m1_backend_calls == 0, "m1_absence_not_proven")
        ordinal = len(self.item_ids)
        require(ordinal < 7 and isinstance(request, dict) and request.get("item_id") == str(ordinal), "transfer_request_order")
        text = request.get("text")
        require(isinstance(text, str) and request.get("model_input_hash") == self.input_hashes[ordinal]
                and bridge.text_hash(text) == self.input_hashes[ordinal], "transfer_input_mismatch")
        require(self.fingerprint + ":" + self.input_hashes[ordinal] in self.m1_cache, "m1_cache_miss_forbidden")
        response = super().predict(request)
        response["result"].update(prelude_transfer_reuse=True, m1_execution_origin="current_run_m1_prelude_receipt")
        return response


def construct_m3(runtime, identity, assets, guard):
    import mlx.core as mx

    guard.mx = mx
    mx.set_memory_limit(bridge.MAX_MLX_BYTES)
    mx.set_cache_limit(512 * 1024**2)
    backend = runtime.MlxM3Backend(
        identity.resolve(assets["m3_base_root"]),
        identity.resolve(assets["m3_adapter"]["path"]),
        identity.resolve(assets["m3_head"]["path"]),
        identity.resolve(assets["m3_prompt"]["path"]), max_length=384,
    )
    guard.check()
    identity.unchanged()
    return backend


def build_engine(init):
    bridge.validate_init(init)
    require(init["mode"] == "research" and init["max_qwen_calls"] == 1, "transfer_init_contract")
    guard = bridge.ResourceGuard()
    config, identity, base_fingerprint = bridge.verified_assets()
    runtime = bridge._load_runtime(identity.resolve(config["implementation"]["runtime"]["path"]))
    assets = config["runtime_assets"]
    bundle = runtime.load_bundle(identity.resolve(assets["bundle_manifest"]["path"]), identity.resolve(assets["bundle_parameters"]["path"]))
    transfer, cache, fingerprint, transfer_sha, transfer_state = load_transfer(base_fingerprint)
    def unchanged():
        identity.unchanged()
        require(bridge._file_state(TRANSFER_PATH) == transfer_state, "transfer_identity_drift")
    engine = TransferEngine(init, runtime=runtime, bundle=bundle, m1=None,
                            m3_factory=lambda: construct_m3(runtime, identity, assets, guard),
                            fingerprint=fingerprint, guard=guard, identity_check=unchanged)
    engine.m1_cache = cache
    engine.base_fingerprint, engine.transfer_sha = base_fingerprint, transfer_sha
    engine.input_hashes = [entry["input_sha256"] for entry in transfer["entries"]]
    engine.trace = sys.gettrace()
    require(isinstance(engine.trace, TransferTrace) and engine.trace.m1_backend_calls == 0, "m1_call_guard_missing")
    unchanged()
    guard.check()
    return engine


OBSERVER = load_observer()


def code_key(function):
    code = function.__code__
    return code.co_filename, code.co_qualname, code.co_firstlineno


class TransferTrace(OBSERVER.StageTrace):
    def __init__(self, journal, memory=None):
        functions = {key: value for key, value in OBSERVER.FUNCTION_STAGES.items()
                     if value not in {"engine_build", "m3_factory", "m1_load", "m1_predict"}}
        functions.update({code_key(build_engine): "engine_build", code_key(construct_m3): "m3_factory"})
        lines = {key: value for key, value in OBSERVER.LINE_ACTIONS.items() if key != OBSERVER.FACTORY}
        first = construct_m3.__code__.co_firstlineno
        lines[code_key(construct_m3)] = {
            first + 1: (("begin", "mlx_import"),),
            first + 3: (("end", "mlx_import"),),
            first + 6: (("point", "mlx_limits_configured"),),
        }
        super().__init__(journal, memory=memory, functions=functions, lines=lines)
        self.forbidden = {key for key, value in OBSERVER.FUNCTION_STAGES.items() if value in {"m1_load", "m1_predict"}}
        self.m1_backend_calls = 0

    def __call__(self, frame, event, arg):
        if event == "call":
            code = frame.f_code
            if (code.co_filename, code.co_qualname, code.co_firstlineno) in self.forbidden:
                self.m1_backend_calls += 1
                raise bridge.InferenceError("m1_backend_forbidden")
        return super().__call__(frame, event, arg)


def main():
    journal = None
    previous_trace, original_serve = sys.gettrace(), bridge.serve
    try:
        require(previous_trace is None, "diagnostic_existing_trace")
        require(os.environ.get("TOPICWEB_EXP084_STAGE_PATH") == str(STAGE_PATH), "diagnostic_journal_path")
        OBSERVER.check_sources()
        journal = OBSERVER.StageJournal(STAGE_PATH)
        trace = TransferTrace(journal)
        # main still supplies original offline policy, output isolation and locks;
        # explicitly pass the new factory, avoiding serve's bound old default.
        bridge.serve = lambda input_stream, output: original_serve(input_stream, output, factory=build_engine)
        sys.settrace(trace)
        return bridge.main()
    except Exception:
        os.write(2, b"EXP084 transferred M3 child failed\n")
        return 1
    finally:
        sys.settrace(previous_trace)
        bridge.serve = original_serve
        if journal is not None:
            journal.close()


if __name__ == "__main__":
    raise SystemExit(main())
