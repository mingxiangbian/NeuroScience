"""M1-receipt replay with the unchanged, lazy M3 backend in a fresh process.

The first JSONL init carries a bounded transfer, not text or a temporary file.
Final component accounting is merged with the first phase by the parent.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

from . import inference_process as bridge

STRATEGY = "m1-receipt-transfer-v1"
BASE_SERVE = bridge.serve


def require(condition, code):
    if not condition:
        raise bridge.InferenceError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hexhash(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def decode_transfer(transfer, transfer_sha256, base_fingerprint):
    import numpy as np

    require(isinstance(transfer, dict) and set(transfer) == {"base_fingerprint", "entries"}, "transfer_schema")
    require(hexhash(transfer_sha256) and digest(canonical(transfer)) == transfer_sha256, "transfer_hash_mismatch")
    require(transfer["base_fingerprint"] == base_fingerprint and hexhash(base_fingerprint), "transfer_fingerprint_mismatch")
    entries = transfer["entries"]
    require(isinstance(entries, list) and 1 <= len(entries) <= bridge.MAX_ITEMS, "transfer_item_limit")
    fingerprint = digest(canonical({"base_fingerprint": base_fingerprint, "strategy": STRATEGY, "transfer_sha256": transfer_sha256}))
    cache, input_hashes = {}, []
    for ordinal, entry in enumerate(entries):
        require(isinstance(entry, dict) and set(entry) == {"ordinal", "input_sha256", "m1_probabilities", "tokenlengths"}
                and type(entry["ordinal"]) is int and entry["ordinal"] == ordinal and hexhash(entry["input_sha256"]), "transfer_entry_schema")
        probabilities = entry["m1_probabilities"]
        require(isinstance(probabilities, list) and len(probabilities) == 6
                and all(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1 for value in probabilities), "transfer_probabilities_invalid")
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
        if key in cache:
            previous, previous_used, previous_metadata = cache[key]
            require(np.array_equal(array, previous) and used == previous_used and metadata == previous_metadata, "transfer_duplicate_inconsistent")
        else:
            cache[key] = (array, used, dict(metadata))
        input_hashes.append(entry["input_sha256"])
    return cache, input_hashes, fingerprint


class StagedEngine(bridge.JobInference):
    def ready(self):
        require(self.m1 is None, "m1_instance_forbidden")
        value = super().ready()
        value["modelstatus"]["m1"] = "receipt_replay_not_loaded"
        value.update(m1_instance_absent=True, base_fingerprint=self.base_fingerprint,
                     transfer_sha256=self.transfer_sha256, transfer_items=len(self.input_hashes),
                     cache_entries=len(self.m1_cache), cache_scope="job_m1_receipt_transfer", strategy=STRATEGY)
        return value

    def predict(self, request):
        self.last_counters = {name: 0 for name in self.totals}
        require(self.m1 is None, "m1_instance_forbidden")
        ordinal = len(self.item_ids)
        require(ordinal < len(self.input_hashes) and isinstance(request, dict)
                and request.get("item_id") == str(ordinal), "transfer_request_order")
        text = request.get("text")
        require(isinstance(text, str) and request.get("model_input_hash") == self.input_hashes[ordinal]
                and bridge.text_hash(text) == self.input_hashes[ordinal], "transfer_input_mismatch")
        require(self.fingerprint + ":" + self.input_hashes[ordinal] in self.m1_cache, "m1_cache_miss_forbidden")
        self.current_ordinal = ordinal
        response = super().predict(request)
        response["result"].update(prelude_transfer_reuse=True, m1_execution_origin="current_job_m1_receipt")
        return response

    def progress(self, stage, kind):
        # Only fixed metadata reaches the protocol output; never args/errors/text.
        require(stage in {"m3_load", "m3_forward"} and kind in {"begin", "end"}, "invalid_progress_stage")
        self.emit_progress({"type": "staged_progress", "stage": stage, "kind": kind,
                            "ordinal": self.current_ordinal, "cumulative_counters": dict(self.totals),
                            "resources": self.guard.snapshot()})


class ObservedM3:
    def __init__(self, backend, engine):
        self.backend, self.engine = backend, engine
        self.tokenizer, self.prompt, self.max_length = backend.tokenizer, backend.prompt, backend.max_length

    def predict_probabilities(self, text):
        self.engine.progress("m3_forward", "begin")
        probabilities = self.backend.predict_probabilities(text)
        self.engine.progress("m3_forward", "end")
        return probabilities


def build_engine(init, transfer, transfer_sha256, emit_progress):
    bridge.validate_init(init)
    require(init["mode"] in {"research", "demo"}, "staged_mode_invalid")
    guard = bridge.ResourceGuard()
    config, identity, base_fingerprint = bridge.verified_assets()
    runtime = bridge._load_runtime(identity.resolve(config["implementation"]["runtime"]["path"]))
    assets = config["runtime_assets"]
    bundle = runtime.load_bundle(identity.resolve(assets["bundle_manifest"]["path"]), identity.resolve(assets["bundle_parameters"]["path"]))
    cache, input_hashes, fingerprint = decode_transfer(transfer, transfer_sha256, base_fingerprint)

    def m3_factory():
        engine.progress("m3_load", "begin")
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
        engine.progress("m3_load", "end")
        return ObservedM3(backend, engine)

    engine = StagedEngine(init, runtime=runtime, bundle=bundle, m1=None, m3_factory=m3_factory,
                          fingerprint=fingerprint, guard=guard, identity_check=identity.unchanged)
    engine.m1_cache, engine.input_hashes = cache, input_hashes
    engine.base_fingerprint, engine.transfer_sha256 = base_fingerprint, transfer_sha256
    engine.current_ordinal = None
    engine.emit_progress = emit_progress
    identity.unchanged()
    guard.check()
    return engine


class FirstLine:
    def __init__(self, line, stream):
        self.line, self.stream = line, stream

    def readline(self, limit=-1):
        if self.line is not None:
            line, self.line = self.line, None
            return line
        return self.stream.readline(limit)


def serve(input_stream, output, factory=build_engine):
    try:
        line = input_stream.readline(bridge.MAX_LINE_BYTES + 1)
        require(line and len(line.encode("utf-8")) <= bridge.MAX_LINE_BYTES, "invalid_init")
        envelope = bridge._json(line)
        require(set(envelope) == {"op", "mode", "max_qwen_calls", "audit_rate", "seed", "transfer", "transfer_sha256"}, "staged_init_schema")
        init = {key: envelope[key] for key in ("op", "mode", "max_qwen_calls", "audit_rate", "seed")}
        bridge.validate_init(init)
        require(init["mode"] in {"research", "demo"}, "staged_mode_invalid")
        def emit_progress(value):
            output.write(canonical(value) + "\n")
            output.flush()
        return BASE_SERVE(FirstLine(canonical(init) + "\n", input_stream), output,
                          factory=lambda normalized: factory(normalized, envelope["transfer"], envelope["transfer_sha256"], emit_progress))
    except Exception as error:
        code = error.code if isinstance(error, bridge.InferenceError) else "staged_initialization_failed"
        output.write(canonical({"type": "error", "item_id": None, "code": code}) + "\n")
        output.flush()
        return 1


def main():
    original_serve = bridge.serve
    try:
        bridge.serve = serve
        return bridge.main()
    finally:
        bridge.serve = original_serve


if __name__ == "__main__":
    raise SystemExit(main())
