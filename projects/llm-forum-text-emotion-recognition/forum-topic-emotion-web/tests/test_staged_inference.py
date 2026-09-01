"""Production staged protocol checks using only synthetic backends/receipts."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from topicweb import staged_inference as staged

RUNTIME_PATH = ROOT.parent / "experiments/stack-overflow-emotion-gold/oof-router/runtime_exp066.py"
SPEC = importlib.util.spec_from_file_location("staged_test_numeric_runtime", RUNTIME_PATH)
RUNTIME = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNTIME
SPEC.loader.exec_module(RUNTIME)
BASE_FP = "a" * 64


def init(mode="research", maximum=500):
    return {"op": "init", "mode": mode, "max_qwen_calls": maximum, "audit_rate": 0, "seed": 42}


def transfer(texts, eligible=True):
    return {"base_fingerprint": BASE_FP, "entries": [
        {"ordinal": index, "input_sha256": staged.digest(text),
         "m1_probabilities": [.75 if eligible else .125, .25, .125, .375, .25, .125],
         "tokenlengths": {"m1": {"input_tokens": 12, "used_tokens": 12, "truncated": False}}}
        for index, text in enumerate(texts)]}


def request(text, index):
    return {"op": "predict", "item_id": str(index), "text": text, "model_input_hash": staged.digest(text)}


class Bundle:
    m1_threshold = .5
    m3_threshold = .5

    def route(self, features):
        return features, float(features[0]), bool(features[0] >= .5)


class Guard:
    def __init__(self):
        self.mx = None

    def snapshot(self):
        return {"peak_rss_bytes": 1024, "mlx_peak_bytes": self.mx.get_peak_memory() if self.mx else 0, "elapsed_seconds": 0.0}

    def check(self):
        return self.snapshot()


def engine(texts, *, mode="research", maximum=500, eligible=True, fail_text=None):
    document = transfer(texts, eligible)
    digest = staged.digest(staged.canonical(document))
    cache, hashes, fingerprint = staged.decode_transfer(document, digest, BASE_FP)
    events = []
    def predict(text):
        if text == fail_text:
            raise RuntimeError("SYNTHETIC PRIVATE ERROR")
        return np.asarray([.25, .75, .125, .25, .125, .375], dtype=np.float32)
    backend = SimpleNamespace(predict_probabilities=Mock(side_effect=predict), tokenizer=None, prompt={}, max_length=384)
    result = staged.StagedEngine(init(mode, maximum), runtime=RUNTIME, bundle=Bundle(), m1=None,
                                 m3_factory=lambda: staged.ObservedM3(backend, result), fingerprint=fingerprint,
                                 guard=Guard(), metadata=lambda *args: {"input_tokens": 20, "used_tokens": 20, "truncated": False})
    result.m1_cache, result.input_hashes = cache, hashes
    result.base_fingerprint, result.transfer_sha256 = BASE_FP, digest
    result.current_ordinal, result.emit_progress = None, events.append
    return result, backend, events


class TransferTests(unittest.TestCase):
    def test_500_is_allowed_and_duplicate_cache_is_consistent(self):
        texts = ["same synthetic input"] * 500
        value, backend, events = engine(texts, eligible=False)
        ready = value.ready()
        self.assertEqual(ready["transfer_items"], 500)
        self.assertEqual(ready["cache_entries"], 1)
        for ordinal, text in enumerate(texts):
            response = value.predict(request(text, ordinal))["result"]
            self.assertEqual(response["counters"]["m1_attempts"], 0)
            self.assertEqual(response["counters"]["m1_cache_hit"], 1)
        self.assertEqual(value.totals["m1_cache_hit"], 500)
        backend.predict_probabilities.assert_not_called()
        self.assertFalse(events)
        with self.assertRaisesRegex(staged.bridge.InferenceError, "transfer_request_order"):
            value.predict(request(texts[0], 500))

    def test_empty_or_501_items_are_rejected(self):
        for count in (0, 501):
            document = transfer(["synthetic"] * count)
            with self.assertRaisesRegex(staged.bridge.InferenceError, "transfer_item_limit"):
                staged.decode_transfer(document, staged.digest(staged.canonical(document)), BASE_FP)

    def test_duplicate_probabilities_or_tokens_must_match(self):
        for mutate in (lambda entry: entry["m1_probabilities"].__setitem__(0, .25),
                       lambda entry: entry["tokenlengths"]["m1"].update(input_tokens=13, used_tokens=13)):
            document = transfer(["synthetic", "synthetic"])
            mutate(document["entries"][1])
            with self.assertRaisesRegex(staged.bridge.InferenceError, "transfer_duplicate_inconsistent"):
                staged.decode_transfer(document, staged.digest(staged.canonical(document)), BASE_FP)

    def test_hash_float32_and_token_identity_are_strict(self):
        changes = [lambda value: value.update(base_fingerprint="b" * 64),
                   lambda value: value["entries"][0].update(ordinal=True),
                   lambda value: value["entries"][0].update(m1_probabilities=[.1] * 6),
                   lambda value: value["entries"][0].update(m1_probabilities=[True] * 6),
                   lambda value: value["entries"][0]["tokenlengths"]["m1"].update(truncated=True)]
        for mutate in changes:
            document = transfer(["synthetic"])
            mutate(document)
            with self.assertRaises(staged.bridge.InferenceError):
                staged.decode_transfer(document, staged.digest(staged.canonical(document)), BASE_FP)
        document = transfer(["synthetic"])
        with self.assertRaisesRegex(staged.bridge.InferenceError, "transfer_hash_mismatch"):
            staged.decode_transfer(document, "0" * 64, BASE_FP)

    def test_cache_miss_stops_before_m1_attempt_or_borrowing_previous_cost(self):
        value, backend, _ = engine(["a", "b"], eligible=False)
        value.predict(request("a", 0))
        value.m1_cache.clear()
        with self.assertRaisesRegex(staged.bridge.InferenceError, "m1_cache_miss_forbidden"):
            value.predict(request("b", 1))
        self.assertEqual(value.totals["m1_attempts"], 0)
        self.assertEqual(value.totals["m1_cache_hit"], 1)
        self.assertTrue(all(count == 0 for count in value.last_counters.values()))
        backend.predict_probabilities.assert_not_called()

    def test_exact_order_and_text_are_required(self):
        value, _, _ = engine(["a"])
        with self.assertRaisesRegex(staged.bridge.InferenceError, "transfer_request_order"):
            value.predict(request("a", 1))
        with self.assertRaisesRegex(staged.bridge.InferenceError, "transfer_input_mismatch"):
            value.predict(request("different", 0))
        self.assertEqual(value.totals["m1_attempts"], 0)


class PolicyTests(unittest.TestCase):
    def test_demo_zero_budget_falls_back_without_loading_m3(self):
        value, backend, events = engine(["a", "a"], mode="demo", maximum=0)
        for index in range(2):
            result = value.predict(request("a", index))["result"]
            self.assertEqual(result["fallback_reason"], "m3_budget_exhausted")
            self.assertEqual(result["used_path"], "m1")
        self.assertEqual(value.totals["m3_attempts"], 0)
        self.assertIsNone(value.m3)
        backend.predict_probabilities.assert_not_called()
        self.assertFalse(events)

    def test_research_zero_budget_does_not_degrade_to_m1(self):
        value, backend, _ = engine(["a"], maximum=0)
        with self.assertRaisesRegex(staged.bridge.InferenceError, "m3_budget_exhausted"):
            value.predict(request("a", 0))
        backend.predict_probabilities.assert_not_called()

    def test_cache_precedes_exhausted_budget_for_both_modes(self):
        for mode in ("research", "demo"):
            value, backend, events = engine(["a", "a"], mode=mode, maximum=1)
            first = value.predict(request("a", 0))["result"]
            duplicate = value.predict(request("a", 1))["result"]
            self.assertEqual(first["prediction"], duplicate["prediction"])
            self.assertEqual(duplicate["used_path"], "m3")
            self.assertEqual(duplicate["counters"]["m3_cache_hit"], 1)
            self.assertEqual(value.totals["m3_attempts"], 1)
            backend.predict_probabilities.assert_called_once()
            self.assertEqual([event["kind"] for event in events], ["begin", "end"])

    def test_demo_runtime_failure_then_cached_success_then_unavailable(self):
        value, backend, events = engine(["a", "b", "a", "c"], mode="demo", maximum=2, fail_text="b")
        results = [value.predict(request(text, index))["result"] for index, text in enumerate(["a", "b", "a", "c"])]
        self.assertEqual([row["fallback_reason"] for row in results], [None, "m3_runtime_failure", None, "m3_unavailable"])
        self.assertEqual(results[2]["counters"]["m3_cache_hit"], 1)
        self.assertEqual(value.totals["m3_attempts"], 2)
        self.assertEqual(backend.predict_probabilities.call_count, 2)
        self.assertEqual([event["kind"] for event in events], ["begin", "end", "begin"])
        self.assertNotIn("SYNTHETIC PRIVATE ERROR", json.dumps(events))

    def test_research_runtime_failure_is_terminal(self):
        value, _, events = engine(["a"], fail_text="a")
        with self.assertRaisesRegex(staged.bridge.InferenceError, "m3_runtime_failure"):
            value.predict(request("a", 0))
        self.assertEqual(value.totals["m3_attempts"], 1)
        self.assertEqual([event["kind"] for event in events], ["begin"])


class ProtocolTests(unittest.TestCase):
    def test_envelope_normalized_first_line_then_original_jsonl_protocol(self):
        texts = ["synthetic raw text"]
        document = transfer(texts)
        envelope = {**init(), "transfer": document, "transfer_sha256": staged.digest(staged.canonical(document))}
        output, calls = io.StringIO(), []
        def factory(normalized, received, digest, progress):
            self.assertEqual(normalized, init())
            self.assertEqual(received, document)
            calls.append(digest)
            value, _, _ = engine(texts)
            value.emit_progress = progress
            return value
        source = io.StringIO(json.dumps(envelope) + "\n" + json.dumps(request(texts[0], 0)) + "\n" + '{"op":"close"}\n')
        self.assertEqual(staged.serve(source, output, factory), 0)
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([row["type"] for row in rows], ["ready", "staged_progress", "staged_progress", "result"])
        self.assertEqual(rows[0]["modelstatus"]["m1"], "receipt_replay_not_loaded")
        self.assertTrue(rows[0]["m1_instance_absent"])
        self.assertEqual(rows[-1]["result"]["m1_execution_origin"], "current_job_m1_receipt")
        self.assertNotIn(texts[0], output.getvalue())
        self.assertEqual(len(calls), 1)
        for progress in rows[1:3]:
            self.assertEqual(set(progress), {"type", "stage", "kind", "ordinal", "cumulative_counters", "resources"})
            self.assertEqual(progress["cumulative_counters"]["m1_attempts"], 0)
            self.assertEqual(progress["cumulative_counters"]["m3_attempts"], 1)

    def test_invalid_mode_budget_and_oversized_envelope_load_no_model(self):
        document = transfer(["a"])
        for settings in (init("m1_only"), init(maximum=501), init(maximum=-1), init(maximum=True)):
            output, factory = io.StringIO(), Mock()
            value = {**settings, "transfer": document, "transfer_sha256": staged.digest(staged.canonical(document))}
            self.assertEqual(staged.serve(io.StringIO(json.dumps(value) + "\n"), output, factory), 1)
            factory.assert_not_called()
            self.assertEqual(json.loads(output.getvalue())["type"], "error")
        output, factory = io.StringIO(), Mock()
        self.assertEqual(staged.serve(io.StringIO("x" * (staged.bridge.MAX_LINE_BYTES + 1)), output, factory), 1)
        factory.assert_not_called()

    def test_real_factory_is_lazy_and_has_no_m1_backend(self):
        calls, progress = [], []
        mx = ModuleType("mlx.core")
        mx.set_memory_limit = lambda amount: calls.append(("memory", amount))
        mx.set_cache_limit = lambda amount: calls.append(("cache", amount))
        mx.get_peak_memory = lambda: 0
        package = ModuleType("mlx")
        package.core = mx
        backend = SimpleNamespace(tokenizer=SimpleNamespace(apply_chat_template=lambda *args, **kwargs: [1, 2]),
                                  prompt={"system": "synthetic", "user_prefix": "", "user_suffix": ""}, max_length=384,
                                  predict_probabilities=Mock(return_value=np.array([.25, .75, .125, .25, .125, .375], dtype=np.float32)))
        runtime = SimpleNamespace(load_bundle=lambda *args: Bundle(), build_features=RUNTIME.build_features, LABEL_ORDER=RUNTIME.LABEL_ORDER,
                                  qwen_prompt_ids=lambda *args: [1, 2], MlxM3Backend=Mock(return_value=backend),
                                  TorchM1Backend=Mock(side_effect=AssertionError("must not load M1")))
        identity = SimpleNamespace(resolve=lambda path: path, unchanged=Mock())
        assets = {name: {"path": name} for name in ("bundle_manifest", "bundle_parameters", "m3_adapter", "m3_head", "m3_prompt")}
        assets["m3_base_root"] = "base"
        config = {"runtime_assets": assets, "implementation": {"runtime": {"path": "synthetic-runtime"}}}
        document = transfer(["a"])
        with patch.object(staged.bridge, "verified_assets", return_value=(config, identity, BASE_FP)), \
                patch.object(staged.bridge, "_load_runtime", return_value=runtime), patch.object(staged.bridge, "ResourceGuard", Guard), \
                patch.dict(sys.modules, {"mlx": package, "mlx.core": mx}):
            value = staged.build_engine(init(maximum=1), document, staged.digest(staged.canonical(document)), progress.append)
            self.assertIsNone(value.m1)
            self.assertIsNone(value.m3)
            runtime.MlxM3Backend.assert_not_called()
            result = value.predict(request("a", 0))["result"]
        runtime.TorchM1Backend.assert_not_called()
        runtime.MlxM3Backend.assert_called_once_with("base", "m3_adapter", "m3_head", "m3_prompt", max_length=384)
        self.assertEqual(calls, [("memory", 10_000_000_000), ("cache", 512 * 1024**2)])
        self.assertEqual([(row["stage"], row["kind"]) for row in progress],
                         [("m3_load", "begin"), ("m3_load", "end"), ("m3_forward", "begin"), ("m3_forward", "end")])
        self.assertEqual(result["counters"]["m1_attempts"], 0)
        self.assertEqual(result["counters"]["m3_succeeded"], 1)

    def test_main_preserves_original_main_and_restores_serve(self):
        original = staged.bridge.serve
        def fake_main():
            self.assertIs(staged.bridge.serve, staged.serve)
            return 0
        with patch.object(staged.bridge, "main", fake_main):
            self.assertEqual(staged.main(), 0)
        self.assertIs(staged.bridge.serve, original)

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
