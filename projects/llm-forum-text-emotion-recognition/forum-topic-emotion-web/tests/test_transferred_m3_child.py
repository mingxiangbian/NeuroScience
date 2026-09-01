"""Synthetic receipt replay only, also executable under frozen Python 3.11."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("exp084_child_tested", ROOT / "scripts/transferred_m3_child.py")
CHILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHILD)
# This module's top-level implementation imports only NumPy, never a model.
RUNTIME_SPEC = importlib.util.spec_from_file_location("exp084_test_frozen_runtime", CHILD.OBSERVER.RUNTIME)
RUNTIME = importlib.util.module_from_spec(RUNTIME_SPEC)
sys.modules[RUNTIME_SPEC.name] = RUNTIME
RUNTIME_SPEC.loader.exec_module(RUNTIME)
BASE_FP = "a" * 64
INIT = {"op": "init", "mode": "research", "max_qwen_calls": 1, "audit_rate": 0, "seed": 42}


class Journal:
    def __init__(self, *args):
        self.events = []

    def emit(self, kind, stage, ordinal, memory):
        self.events.append({"kind": kind, "stage": stage, "ordinal": ordinal, "memory": memory})

    def close(self):
        pass


class Bundle:
    m1_threshold = .5
    m3_threshold = .5

    def route(self, features):
        return features, float(features[0]), bool(features[0] >= .5)


class Guard:
    def check(self):
        return {"peak_rss_bytes": 0, "mlx_peak_bytes": 0, "elapsed_seconds": 0}


def traced(trace, function, *args):
    previous = sys.gettrace()
    try:
        sys.settrace(trace)
        return function(*args)
    finally:
        sys.settrace(previous)


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.path = self.root / "transfer.json"
        self.texts = [f"synthetic transfer input {index}" for index in range(7)]
        self.entries = [{"ordinal": index, "input_sha256": CHILD.sha(text),
                         "m1_probabilities": [.75 if index == 6 else .125, .25, .375, .125, .25, .375],
                         "tokenlengths": {"m1": {"input_tokens": 400 if index == 6 else 12,
                                                  "used_tokens": 256 if index == 6 else 12, "truncated": index == 6}},
                         "source_result_sha256": CHILD.sha(f"synthetic source row {index}")}
                        for index, text in enumerate(self.texts)]
        self.value = {"experiment_id": "EXP-084", "attempt": 1, "source_job_id": "exp084-m1-prelude",
                      "source_phase": "m1_prelude", "source_results_path": CHILD.SOURCE_RESULTS_PATH,
                      "source_results_sha256": "b" * 64, "source_results_count": 340,
                      "fingerprint": BASE_FP, "entries": self.entries}
        self.path_patch = patch.object(CHILD, "TRANSFER_PATH", self.path)
        self.path_patch.start()
        self.env_patch = patch.dict(os.environ, {})
        self.env_patch.start()
        self.save()

    def tearDown(self):
        self.env_patch.stop()
        self.path_patch.stop()
        self.temp.cleanup()

    def save(self, value=None):
        self.path.write_text(json.dumps(self.value if value is None else value, allow_nan=True))
        self.path.chmod(0o600)
        os.environ["TOPICWEB_EXP084_TRANSFER_SHA256"] = CHILD.sha(self.path.read_bytes())

    def request(self, index):
        return {"op": "predict", "item_id": str(index), "text": self.texts[index], "model_input_hash": self.entries[index]["input_sha256"]}

    def engine(self):
        transfer, cache, fingerprint, digest, _ = CHILD.load_transfer(BASE_FP)
        m3 = SimpleNamespace(predict_probabilities=Mock(return_value=np.array([.25, .75, .125, .375, .25, .125], dtype=np.float32)))
        engine = CHILD.TransferEngine(INIT, runtime=RUNTIME, bundle=Bundle(), m1=None,
                                      m3_factory=lambda: m3, fingerprint=fingerprint, guard=Guard(),
                                      metadata=lambda *args: {"input_tokens": 20, "used_tokens": 20, "truncated": False})
        engine.m1_cache = cache
        engine.base_fingerprint, engine.transfer_sha = BASE_FP, digest
        engine.input_hashes = [row["input_sha256"] for row in transfer["entries"]]
        engine.trace = SimpleNamespace(m1_backend_calls=0)
        return engine, m3

    def test_exact_float32_cache_token_metadata_and_strategy_fingerprint(self):
        transfer, cache, fingerprint, digest, state = CHILD.load_transfer(BASE_FP)
        self.assertEqual(fingerprint, CHILD.sha(CHILD.canonical({"base_fingerprint": BASE_FP, "strategy": CHILD.STRATEGY, "transfer_sha256": digest})))
        self.assertEqual(len(cache), 7)
        self.assertEqual(state, CHILD.bridge._file_state(self.path))
        probability, used, metadata = cache[fingerprint + ":" + self.entries[6]["input_sha256"]]
        self.assertEqual(probability.dtype, np.float32)
        self.assertFalse(probability.flags.writeable)
        self.assertEqual(used, 256)
        self.assertEqual(metadata, self.entries[6]["tokenlengths"]["m1"])
        self.assertEqual(transfer["entries"], self.entries)

    def test_invalid_transfer_is_rejected_before_cache(self):
        changes = [
            lambda v: v.update(source_results_count=7),
            lambda v: v.update(source_results_path="private/another-run/results.jsonl"),
            lambda v: v.update(fingerprint="c" * 64),
            lambda v: v["entries"].pop(),
            lambda v: v["entries"][0].update(ordinal=True),
            lambda v: v["entries"][0].update(extra="not allowed"),
            lambda v: v["entries"][0].update(m1_probabilities=[.1] * 6),
            lambda v: v["entries"][0].update(m1_probabilities=[float("nan")] * 6),
            lambda v: v["entries"][0].update(m1_probabilities=[True] * 6),
            lambda v: v["entries"][0]["tokenlengths"]["m1"].update(used_tokens=0),
            lambda v: v["entries"][6]["tokenlengths"]["m1"].update(used_tokens=255),
            lambda v: v["entries"][6]["tokenlengths"]["m1"].update(truncated=False),
            lambda v: v["entries"][1].update(input_sha256=v["entries"][0]["input_sha256"]),
        ]
        for mutate in changes:
            with self.subTest(mutation=changes.index(mutate)):
                value = copy.deepcopy(self.value)
                mutate(value)
                self.save(value)
                with self.assertRaises(CHILD.bridge.InferenceError):
                    CHILD.load_transfer(BASE_FP)

    def test_file_hash_and_private_mode_are_required(self):
        os.environ["TOPICWEB_EXP084_TRANSFER_SHA256"] = "0" * 64
        with self.assertRaisesRegex(CHILD.bridge.InferenceError, "transfer_identity_drift"):
            CHILD.load_transfer(BASE_FP)
        self.save()
        self.path.chmod(0o644)
        with self.assertRaisesRegex(CHILD.bridge.InferenceError, "transfer_file_mode"):
            CHILD.load_transfer(BASE_FP)

    def test_original_route_and_predictions_match_without_second_m1_forward(self):
        replay, m3 = self.engine()
        indexed = {text: row for text, row in zip(self.texts, self.entries)}
        m1 = SimpleNamespace(predict_probabilities=Mock(side_effect=lambda text: (
            np.array(indexed[text]["m1_probabilities"], dtype=np.float32), indexed[text]["tokenlengths"]["m1"]["used_tokens"])))
        original = CHILD.bridge.JobInference(INIT, runtime=RUNTIME, bundle=Bundle(), m1=m1,
                                             m3_factory=lambda: m3, fingerprint=BASE_FP, guard=Guard(),
                                             metadata=lambda backend, text, kind, actual: indexed[text]["tokenlengths"]["m1"] if kind == "m1" else {"input_tokens": 20, "used_tokens": 20, "truncated": False})
        for index in range(7):
            actual = replay.predict(self.request(index))["result"]
            reference = original.predict(self.request(index))["result"]
            for field in ("prediction", "m1_prediction", "m3_prediction", "m1_probabilities", "m3_probabilities",
                          "route_score", "route_requested", "route_eligible", "hypothetical_route", "m1_entropy",
                          "threshold_margin", "tokenlengths", "truncflags", "used_path", "neutral"):
                self.assertEqual(actual[field], reference[field], field)
            self.assertEqual(actual["counters"]["m1_attempts"], 0)
            self.assertEqual(actual["counters"]["m1_cache_hit"], 1)
            self.assertTrue(actual["prelude_transfer_reuse"])
            self.assertEqual(actual["m1_execution_origin"], "current_run_m1_prelude_receipt")
        self.assertEqual(m1.predict_probabilities.call_count, 7)
        self.assertEqual(replay.totals["m1_attempts"], 0)
        self.assertEqual(replay.totals["m1_cache_hit"], 7)
        self.assertEqual(replay.totals["m3_attempts"], 1)
        self.assertIsNone(replay.m1)

    def test_cache_miss_does_not_increment_attempt_or_repeat_previous_receipt_cost(self):
        engine, _ = self.engine()
        engine.predict(self.request(0))
        engine.m1_cache.pop(engine.fingerprint + ":" + self.entries[1]["input_sha256"])
        with self.assertRaisesRegex(CHILD.bridge.InferenceError, "m1_cache_miss_forbidden"):
            engine.predict(self.request(1))
        self.assertEqual(engine.totals["m1_cache_hit"], 1)
        self.assertEqual(engine.totals["m1_attempts"], 0)
        self.assertTrue(all(value == 0 for value in engine.last_counters.values()))
        self.assertEqual(engine.item_ids, {"0"})

    def test_unknown_order_or_text_cannot_fall_back_to_m1(self):
        engine, _ = self.engine()
        with self.assertRaisesRegex(CHILD.bridge.InferenceError, "transfer_request_order"):
            engine.predict(self.request(1))
        request = self.request(0)
        request["text"] = "different synthetic input"
        with self.assertRaisesRegex(CHILD.bridge.InferenceError, "transfer_input_mismatch"):
            engine.predict(request)
        self.assertEqual(engine.totals["m1_attempts"], 0)
        self.assertEqual(engine.totals["m1_cache_hit"], 0)

    def test_ready_proves_absence_and_is_create_only(self):
        engine, _ = self.engine()
        path = self.root / "m3-ready.json"
        with patch.object(CHILD, "READY_PATH", path):
            ready = engine.ready()
            with self.assertRaises(FileExistsError):
                engine.ready()
        proof = json.loads(path.read_text())
        self.assertEqual(ready["modelstatus"]["m1"], "receipt_replay_not_loaded")
        self.assertEqual(proof["modelstatus"], ready["modelstatus"])
        self.assertTrue(proof["m1_instance_absent"])
        self.assertEqual(proof["cache_input_sha256s"], engine.input_hashes)
        self.assertEqual(proof["m1_backend_calls"], 0)
        self.assertEqual(proof["fingerprint"], engine.fingerprint)
        self.assertNotIn(self.texts[0], path.read_text())

    def test_factory_does_not_instantiate_m1_or_m3_and_requires_trace_guard(self):
        identity = SimpleNamespace(resolve=lambda value: value, unchanged=Mock())
        assets = {name: {"path": name} for name in ("bundle_manifest", "bundle_parameters")}
        config = {"runtime_assets": assets, "implementation": {"runtime": {"path": "synthetic-runtime"}}}
        runtime = SimpleNamespace(load_bundle=lambda *args: Bundle(), TorchM1Backend=Mock(side_effect=AssertionError("forbidden")))
        trace = CHILD.TransferTrace(Journal())
        with patch.object(CHILD.bridge, "verified_assets", return_value=(config, identity, BASE_FP)), \
                patch.object(CHILD.bridge, "_load_runtime", return_value=runtime):
            engine = traced(trace, CHILD.build_engine, INIT)
            with self.assertRaisesRegex(CHILD.bridge.InferenceError, "m1_call_guard_missing"):
                CHILD.build_engine(INIT)
        self.assertIsNone(engine.m1)
        self.assertIsNone(engine.m3)
        runtime.TorchM1Backend.assert_not_called()
        self.assertEqual([event["stage"] for event in trace.journal.events], ["engine_build", "engine_build"])


class TraceTests(unittest.TestCase):
    def test_frozen_m1_calls_are_blocked_before_import_or_body(self):
        for function, args in ((RUNTIME.TorchM1Backend.__init__, (object(), Path("synthetic-unused"))),
                               (RUNTIME.TorchM1Backend.predict_probabilities, (object(), "synthetic-unused"))):
            trace = CHILD.TransferTrace(Journal())
            with self.assertRaisesRegex(CHILD.bridge.InferenceError, "m1_backend_forbidden"):
                traced(trace, function, *args)
            self.assertEqual(trace.m1_backend_calls, 1)
            self.assertEqual(trace.journal.events, [])
        self.assertNotIn("torch", sys.modules)

    def test_new_factory_profile_preserves_limit_order_and_backend_arguments(self):
        calls = []
        mx = ModuleType("mlx.core")
        mx.set_memory_limit = lambda value: calls.append(("memory_limit", value))
        mx.set_cache_limit = lambda value: calls.append(("cache_limit", value))
        def getter():
            self.assertGreaterEqual(len(calls), 2)
            return 0
        mx.get_active_memory = mx.get_cache_memory = mx.get_peak_memory = getter
        package = ModuleType("mlx")
        package.core = mx
        backend = object()
        runtime = SimpleNamespace(MlxM3Backend=Mock(return_value=backend))
        identity = SimpleNamespace(resolve=lambda value: value, unchanged=Mock())
        assets = {"m3_base_root": "base", "m3_adapter": {"path": "adapter"},
                  "m3_head": {"path": "head"}, "m3_prompt": {"path": "prompt"}}
        trace = CHILD.TransferTrace(Journal())
        trace.ordinal = 6
        with patch.dict(sys.modules, {"mlx": package, "mlx.core": mx}):
            self.assertIs(traced(trace, CHILD.construct_m3, runtime, identity, assets, Guard()), backend)
        self.assertEqual(calls, [("memory_limit", 10_000_000_000), ("cache_limit", 512 * 1024**2)])
        runtime.MlxM3Backend.assert_called_once_with("base", "adapter", "head", "prompt", max_length=384)
        self.assertEqual([(event["kind"], event["stage"]) for event in trace.journal.events],
                         [("begin", "m3_factory"), ("begin", "mlx_import"), ("end", "mlx_import"),
                          ("point", "mlx_limits_configured"), ("end", "m3_factory")])
        self.assertTrue(all(event["memory"]["mlx_status"] == "not_sampled" for event in trace.journal.events[:3]))
        self.assertTrue(all(event["memory"]["mlx_status"] == "observed" for event in trace.journal.events[3:]))

    def test_main_passes_factory_explicitly_and_restores_original_serve(self):
        serve = Mock(return_value=0)
        def main():
            return CHILD.bridge.serve("synthetic-input-stream", "synthetic-output-stream")
        with patch.object(CHILD.bridge, "main", main), patch.object(CHILD.bridge, "serve", serve), \
                patch.object(CHILD.OBSERVER, "StageJournal", Journal), \
                patch.dict(os.environ, {"TOPICWEB_EXP084_STAGE_PATH": str(CHILD.STAGE_PATH)}):
            self.assertEqual(CHILD.main(), 0)
            self.assertIs(CHILD.bridge.serve, serve)
        serve.assert_called_once_with("synthetic-input-stream", "synthetic-output-stream", factory=CHILD.build_engine)
        self.assertIsNone(sys.gettrace())

    def test_actual_phase_python_runs_synthetic_suite_without_models(self):
        if sys.version_info[:2] == (3, 11):
            self.assertEqual(sys.version_info[:3], (3, 11, 15))
            self.assertFalse(any(name.split(".")[0] in {"mlx", "torch", "transformers", "mlx_lm"} for name in sys.modules))
            return
        result = subprocess.run(["/Users/phoenix/miniconda3/envs/phase-a-runtime/bin/python", "-I", "-B", str(Path(__file__).resolve())],
                                capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
