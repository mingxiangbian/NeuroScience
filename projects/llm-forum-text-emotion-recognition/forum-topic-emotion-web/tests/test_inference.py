"""Synthetic bridge tests: no model, label, projection, or dataset is loaded."""

import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from topicweb import inference_process as bridge


RUNTIME_PATH = bridge.PROJECT_ROOT / "experiments/stack-overflow-emotion-gold/oof-router/runtime_exp066.py"
RUNTIME = bridge._load_runtime(RUNTIME_PATH)


def init(mode="research", budget=2):
    return {"op": "init", "mode": mode, "max_qwen_calls": budget, "audit_rate": 0, "seed": 42}


def request(text="Synthetic technical input", item_id="row1"):
    return {"op": "predict", "item_id": item_id, "text": text, "model_input_hash": bridge.text_hash(text)}


class M1:
    def __init__(self):
        self.calls = 0

    def predict_probabilities(self, text):
        self.calls += 1
        return np.asarray([.7, .2, .1, .3, .4, .05], dtype=np.float32), 8


class M3:
    def __init__(self, failure=False, invalid=False):
        self.calls = 0
        self.failure = failure
        self.invalid = invalid

    def predict_probabilities(self, text):
        self.calls += 1
        if self.failure:
            raise RuntimeError("secret text MUST NOT escape")
        return np.asarray([.1, .9, .1, .3, .2, .4] if not self.invalid else [np.nan] * 6, dtype=np.float32)


class Guard:
    def __init__(self, failure=False):
        self.failure = failure

    def check(self):
        if self.failure:
            raise bridge.InferenceError("resource_limit_exceeded")
        return {"peak_rss_bytes": 1, "mlx_peak_bytes": 0, "elapsed_seconds": .01}


def engine(mode="research", budget=2, routed=True, failure=False, invalid=False):
    bundle = RUNTIME.RouterBundle({
        "labels": list(RUNTIME.LABEL_ORDER), "features": list(RUNTIME.FEATURE_NAMES),
        "thresholds": {"m1": .6, "m3": .8}, "operating_point": {"cutoff": .5},
    }, {"scaler_mean": np.zeros(14), "scaler_var": np.ones(14), "scaler_scale": np.ones(14),
        "classes": np.asarray([0, 1]), "coef": np.zeros((1, 14)),
        "intercept": np.asarray([100 if routed else -100])})
    first, third = M1(), M3(failure, invalid)
    factories = []
    def factory():
        factories.append(1)
        return third
    result = bridge.JobInference(
        init(mode, budget), runtime=RUNTIME, bundle=bundle, m1=first,
        m3_factory=factory, fingerprint="synthetic-fingerprint", guard=Guard(),
        metadata=lambda _, text, kind, actual: {"input_tokens": actual or 10,
                                               "used_tokens": actual or 10, "truncated": False},
    )
    result.test_m3, result.test_factories = third, factories
    return result


class PredictionTests(unittest.TestCase):
    def test_real_frozen_feature_and_route_formula_is_reused(self):
        value = engine().predict(request())["result"]
        self.assertEqual(value["used_path"], "m3")
        self.assertEqual(value["prediction6"], [0, 1, 0, 0, 0, 0])
        self.assertEqual(value["prediction"], value["prediction6"])
        self.assertEqual(value["m1_prediction"], [1, 0, 0, 0, 0, 0])
        self.assertEqual(value["m3_prediction"], [0, 1, 0, 0, 0, 0])
        self.assertEqual(value["labels"], ["joy"])
        self.assertEqual(value["counters"]["m3_succeeded"], 1)

    def test_unrouted_does_not_initialize_m3(self):
        runtime = engine(routed=False)
        value = runtime.predict(request())["result"]
        self.assertEqual(runtime.test_factories, [])
        self.assertFalse(value["route_requested"])
        self.assertEqual(value["used_path"], "m1")

    def test_m1_only_reports_hypothetical_route_without_m3(self):
        runtime = engine(mode="m1_only", budget=0)
        value = runtime.predict(request())["result"]
        self.assertTrue(value["hypothetical_route"])
        self.assertFalse(value["route_requested"])
        self.assertFalse(value["fallback"])
        self.assertIsNone(value["m3_prediction"])
        self.assertEqual(runtime.test_factories, [])

    def test_m3_load_once_for_distinct_inputs(self):
        runtime = engine()
        runtime.predict(request("alpha", "one"))
        runtime.predict(request("beta", "two"))
        self.assertEqual(len(runtime.test_factories), 1)
        self.assertEqual(runtime.test_m3.calls, 2)

    def test_exact_cache_precedes_budget_gate(self):
        runtime = engine(budget=1)
        runtime.predict(request("same", "one"))
        value = runtime.predict(request("same", "two"))["result"]
        self.assertTrue(value["cache_hit"])
        self.assertEqual(value["counters"]["m3_attempts"], 0)
        self.assertEqual(value["counters"]["m3_cache_hit"], 1)
        self.assertEqual(runtime.m1.calls, 1)
        self.assertEqual(runtime.test_m3.calls, 1)

    def test_case_and_whitespace_are_not_normalized_for_cache(self):
        runtime = engine(budget=4)
        for index, text in enumerate(("GOOD", "good", " good", "good  ")):
            runtime.predict(request(text, str(index)))
        self.assertEqual(runtime.m1.calls, 4)
        self.assertEqual(runtime.test_m3.calls, 4)

    def test_cache_is_job_scoped(self):
        first, second = engine(), engine()
        first.predict(request())
        second.predict(request())
        self.assertEqual(second.m1.calls, 1)
        self.assertEqual(second.test_m3.calls, 1)

    def test_research_budget_exhaustion_is_fatal(self):
        runtime = engine(budget=0)
        with self.assertRaisesRegex(bridge.InferenceError, "m3_budget_exhausted"):
            runtime.predict(request())
        self.assertEqual(runtime.test_factories, [])

    def test_demo_budget_exhaustion_keeps_original_m1_forward(self):
        runtime = engine(mode="demo", budget=0)
        value = runtime.predict(request())["result"]
        self.assertEqual(runtime.m1.calls, 1)
        self.assertEqual(value["fallback_reason"], "m3_budget_exhausted")
        self.assertEqual(value["prediction6"], value["m1_prediction"])

    def test_research_m3_failure_is_fatal_and_counted(self):
        runtime = engine(failure=True)
        with self.assertRaisesRegex(bridge.InferenceError, "m3_runtime_failure"):
            runtime.predict(request())
        self.assertEqual(runtime.totals["m3_attempts"], 1)
        self.assertEqual(runtime.totals["m1_attempts"], 1)

    def test_demo_failure_not_cached_or_retried_and_no_second_m1(self):
        runtime = engine(mode="demo", failure=True)
        first = runtime.predict(request("one", "one"))["result"]
        second = runtime.predict(request("two", "two"))["result"]
        self.assertEqual(runtime.m1.calls, 2)
        self.assertEqual(first["fallback_reason"], "m3_runtime_failure")
        self.assertEqual(second["fallback_reason"], "m3_unavailable")
        self.assertEqual(runtime.test_m3.calls, 1)
        self.assertEqual(runtime.m3_cache, {})

    def test_nonfinite_model_output_stops_even_demo(self):
        with self.assertRaisesRegex(bridge.InferenceError, "model_output_invalid"):
            engine(mode="demo", invalid=True).predict(request())

    def test_m1_invalid_probabilities_and_lengths_are_rejected_before_cache(self):
        cases = [(np.zeros(5), 8), (np.full(6, np.nan), 8), (np.full(6, np.inf), 8),
                 (np.full(6, -1e-10), 8), (np.full(6, 1 + 1e-10), 8),
                 (np.zeros(6), 0), (np.zeros(6), 257), (np.zeros(6), True)]
        for probabilities, length in cases:
            with self.subTest(length=length, probabilities=probabilities):
                runtime = engine(mode="demo")
                runtime.m1.predict_probabilities = lambda _: (probabilities, length)
                with self.assertRaisesRegex(bridge.InferenceError, "model_output_invalid"):
                    runtime.predict(request())
                self.assertEqual(runtime.m1_cache, {})
                self.assertEqual(runtime.test_factories, [])
                self.assertEqual(runtime.totals["m1_attempts"], 1)

    def test_m3_initialization_failure_consumes_attempt(self):
        runtime = engine(mode="demo")
        runtime.m3_factory = lambda: (_ for _ in ()).throw(RuntimeError("private detail"))
        value = runtime.predict(request())["result"]
        self.assertEqual(value["counters"]["m3_attempts"], 1)
        self.assertEqual(value["counters"]["m3_succeeded"], 0)
        self.assertTrue(value["fallback"])

    def test_resource_or_source_drift_never_falls_back(self):
        runtime = engine(mode="demo")
        runtime.guard = Guard(True)
        with self.assertRaisesRegex(bridge.InferenceError, "resource_limit_exceeded"):
            runtime.predict(request())
        runtime.guard = Guard()
        runtime.identity_check = lambda: (_ for _ in ()).throw(bridge.InferenceError("source_identity_drift"))
        with self.assertRaisesRegex(bridge.InferenceError, "source_identity_drift"):
            runtime.predict(request())

    def test_bad_hash_duplicate_and_oversize_rejected(self):
        runtime = engine()
        bad = request()
        bad["model_input_hash"] = "0" * 64
        with self.assertRaisesRegex(bridge.InferenceError, "invalid_input"):
            runtime.predict(bad)
        runtime.predict(request())
        with self.assertRaisesRegex(bridge.InferenceError, "duplicate_item_id"):
            runtime.predict(request())
        with self.assertRaisesRegex(bridge.InferenceError, "invalid_input"):
            runtime.predict(request("x" * (bridge.MAX_TEXT_BYTES + 1), "large"))

    def test_item_limit(self):
        runtime = engine(mode="m1_only")
        with patch.object(bridge, "MAX_ITEMS", 1):
            runtime.predict(request())
            with self.assertRaisesRegex(bridge.InferenceError, "item_limit_exceeded"):
                runtime.predict(request(item_id="row2"))


class ProtocolTests(unittest.TestCase):
    def test_runtime_import_registers_module_without_constructing_models(self):
        self.assertIs(sys.modules[RUNTIME.__name__], RUNTIME)
        self.assertTrue(callable(RUNTIME.TorchM1Backend))
        self.assertTrue(callable(RUNTIME.MlxM3Backend))

    def test_ready_result_and_close_jsonl(self):
        lines = [init(), request(), {"op": "close"}, request("ignored", "two")]
        output = io.StringIO()
        status = bridge.serve(io.StringIO("\n".join(map(json.dumps, lines))), output, lambda _: engine())
        records = [json.loads(row) for row in output.getvalue().splitlines()]
        self.assertEqual(status, 0)
        self.assertEqual([row["type"] for row in records], ["ready", "result"])

    def test_failure_safe_error_and_exit_nonzero(self):
        output = io.StringIO()
        status = bridge.serve(io.StringIO(json.dumps(init()) + "\n" + json.dumps(request())), output, lambda _: engine(failure=True))
        self.assertEqual(status, 1)
        self.assertNotIn("secret", output.getvalue())
        final = json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(final["code"], "m3_runtime_failure")
        self.assertEqual(final["counters"]["m3_attempts"], 1)

    def test_invalid_init_and_nonzero_audit_never_build_model(self):
        for invalid in ({**init(), "audit_rate": .1}, {**init(), "seed": 43}, {**init(), "max_qwen_calls": True}):
            output = io.StringIO()
            with patch.object(bridge, "build_real_engine") as model:
                status = bridge.serve(io.StringIO(json.dumps(invalid)), output, model)
            self.assertEqual(status, 1)
            model.assert_not_called()

    def test_duplicate_keys_and_nan_rejected(self):
        for raw in ('{"op":"init","op":"init"}', '{"audit_rate":NaN}'):
            with self.assertRaises(bridge.InferenceError):
                bridge._json(raw)

    def test_eof_runs_final_identity_and_resource_checks(self):
        for failure in ("identity", "resource"):
            runtime = engine()
            if failure == "identity":
                runtime.identity_check = lambda: (_ for _ in ()).throw(bridge.InferenceError("source_identity_drift"))
                code = "source_identity_drift"
            else:
                runtime.guard = Guard(True)
                code = "resource_limit_exceeded"
            output = io.StringIO()
            status = bridge.serve(io.StringIO(json.dumps(init()) + "\n"), output, lambda _: runtime)
            self.assertEqual(status, 1)
            self.assertEqual(json.loads(output.getvalue().splitlines()[-1])["code"], code)


class TokenMetadataTests(unittest.TestCase):
    class Tokenizer:
        def __init__(self, suffix=True):
            self.suffix = suffix
            self.flags = []

        def apply_chat_template(self, messages, **kwargs):
            self.flags.append(kwargs)
            return [999] + [ord(char) for char in messages[1]["content"]] + [998]

        def encode(self, text, **kwargs):
            return [ord(char) for char in text]

        def decode(self, ids, **kwargs):
            if ids and ids[0] == 999:
                return "synthetic" + ("<think>\n\n</think>\n\n" if self.suffix else "wrong suffix")
            return "".join(chr(token) for token in ids)

    def test_qwen_metadata_matches_frozen_prompt_and_truncation(self):
        tokenizer = self.Tokenizer()
        backend = SimpleNamespace(tokenizer=tokenizer, prompt={"system": "s", "user_prefix": "<", "user_suffix": ">"}, max_length=8)
        short = bridge._metadata(backend, "abc", "m3", None, RUNTIME)
        long = bridge._metadata(backend, "abcdefgh", "m3", None, RUNTIME)
        self.assertEqual(short, {"input_tokens": 7, "used_tokens": 7, "truncated": False})
        self.assertEqual(long, {"input_tokens": 12, "used_tokens": 8, "truncated": True})
        self.assertTrue(all(flags == {"tokenize": True, "return_dict": False, "add_generation_prompt": True, "enable_thinking": False} for flags in tokenizer.flags))

    def test_qwen_metadata_preserves_empty_think_suffix_check(self):
        backend = SimpleNamespace(tokenizer=self.Tokenizer(False), prompt={"system": "s", "user_prefix": "<", "user_suffix": ">"}, max_length=8)
        with self.assertRaisesRegex(ValueError, "empty-think suffix drift"):
            bridge._metadata(backend, "abc", "m3", None, RUNTIME)


class IdentityTests(unittest.TestCase):
    def test_hash_mode_stat_and_symlink_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "asset"
            path.write_bytes(b"safe")
            path.chmod(0o600)
            record = {"path": "asset", "bytes": 4, "mode": "0600", "sha256": hashlib.sha256(b"safe").hexdigest()}
            identity = bridge.Identity(root)
            self.assertEqual(identity.check(record), path.resolve())
            path.write_bytes(b"drft")
            with self.assertRaisesRegex(bridge.InferenceError, "source_identity_drift"):
                identity.unchanged()
            with self.assertRaisesRegex(bridge.InferenceError, "source_identity_drift"):
                bridge.Identity(root).check(record)
            (root / "linked").symlink_to(path)
            with self.assertRaisesRegex(bridge.InferenceError, "source_identity_drift"):
                identity.resolve("linked")
            with self.assertRaisesRegex(bridge.InferenceError, "source_identity_drift"):
                identity.resolve("../escape")

    def test_verified_assets_does_not_walk_projection_or_replay(self):
        import inspect
        source = inspect.getsource(bridge.verified_assets)
        self.assertNotIn('assets["projection"]', source)
        self.assertNotIn('assets["replay"]', source)
        self.assertNotIn('assets["projection_manifest"]', source)
        self.assertIn('identity.check(config["implementation"]["runtime"])', source)


if __name__ == "__main__":
    unittest.main()
