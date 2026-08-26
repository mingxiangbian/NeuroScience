from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))
RUNTIME_PATH = MODULE_DIR / "runtime_exp066.py"
RUNNER_PATH = MODULE_DIR / "run_exp066_runtime_parity.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp066_runtime_parity.py"
FINALIZER_PATH = MODULE_DIR / "finalize_exp066_cli.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNTIME = load("exp066_runtime_tests", RUNTIME_PATH)
RUNNER = load("exp066_runner_tests", RUNNER_PATH)
FINALIZER = load("exp066_finalizer_tests", FINALIZER_PATH)


class FakeM1:
    def __init__(self, probabilities: list[float], token_length: int = 8) -> None:
        self.probabilities = np.asarray(probabilities, dtype=np.float32)
        self.token_length = token_length
        self.calls = 0

    def predict_probabilities(self, text: str):
        self.calls += 1
        return self.probabilities.copy(), self.token_length


class FakeM3:
    def __init__(self, probabilities: list[float]) -> None:
        self.probabilities = np.asarray(probabilities, dtype=np.float32)
        self.calls = 0

    def predict_probabilities(self, text: str):
        self.calls += 1
        return self.probabilities.copy()


def bundle(intercept: float) -> RUNTIME.RouterBundle:
    manifest = {
        "labels": list(RUNTIME.LABEL_ORDER),
        "features": list(RUNTIME.FEATURE_NAMES),
        "thresholds": {"m1": 0.5, "m3": 0.5},
        "operating_point": {"cutoff": 0.5},
    }
    arrays = {
        "scaler_mean": np.zeros(14, dtype=np.float64),
        "scaler_var": np.ones(14, dtype=np.float64),
        "scaler_scale": np.ones(14, dtype=np.float64),
        "classes": np.asarray([0, 1], dtype=np.int64),
        "coef": np.zeros((1, 14), dtype=np.float64),
        "intercept": np.asarray([intercept], dtype=np.float64),
    }
    return RUNTIME.RouterBundle(manifest, arrays)


class Exp066RuntimeTests(unittest.TestCase):
    def test_feature_order_and_values(self) -> None:
        probabilities = np.asarray([0.1, 0.2, 0.3, 0.4, 0.5, 0.6], dtype=np.float32)
        features = RUNTIME.build_features(probabilities, 0.5, 12, 8)
        self.assertEqual(features.shape, (14,))
        self.assertTrue(np.allclose(features[:6], probabilities, rtol=0.0, atol=0.0))
        self.assertEqual(features[8], 0.0)
        self.assertEqual(features[9], 2.0)
        self.assertEqual(features[12], 12.0)
        self.assertEqual(features[13], 8.0)

    def test_allow_qwen_false_never_calls_m3(self) -> None:
        m1 = FakeM1([0.9, 0.1, 0.1, 0.1, 0.1, 0.1])
        m3 = FakeM3([0.1, 0.9, 0.1, 0.1, 0.1, 0.1])
        runtime = RUNTIME.PhaseARuntime(bundle(100.0), m1, m3)
        result = runtime.predict("text", allow_qwen=False)
        self.assertEqual(result["used_path"], "m1")
        self.assertEqual(m3.calls, 0)
        self.assertNotIn("diagnostics", result)

    def test_route_to_m3_and_label_order(self) -> None:
        m1 = FakeM1([0.9, 0.1, 0.1, 0.1, 0.1, 0.1])
        m3 = FakeM3([0.1, 0.9, 0.1, 0.1, 0.1, 0.1])
        runtime = RUNTIME.PhaseARuntime(bundle(100.0), m1, m3)
        result = runtime.predict("text", allow_qwen=True)
        self.assertEqual(result["used_path"], "m3")
        self.assertEqual(result["active_labels"], ["joy"])
        self.assertEqual(result["prediction"], [0, 1, 0, 0, 0, 0])
        self.assertFalse(result["neutral"])
        self.assertFalse(result["degraded"])
        self.assertEqual(m3.calls, 1)

    def test_low_route_neutral_and_parity_force(self) -> None:
        m1 = FakeM1([0.1] * 6)
        m3 = FakeM3([0.9] + [0.1] * 5)
        runtime = RUNTIME.PhaseARuntime(bundle(-100.0), m1, m3)
        result = runtime.predict("text", allow_qwen=True)
        self.assertEqual(result["used_path"], "m1")
        self.assertTrue(result["neutral"])
        self.assertEqual(m3.calls, 0)
        parity = runtime.parity_record("text")
        self.assertEqual(m3.calls, 1)
        self.assertEqual(parity["selected_path"], 0)
        self.assertIsNotNone(parity["m3_probabilities"])

    def test_diagnostics_are_opt_in(self) -> None:
        runtime = RUNTIME.PhaseARuntime(
            bundle(-100.0), FakeM1([0.1] * 6), FakeM3([0.9] * 6)
        )
        plain = runtime.predict("text")
        detailed = runtime.predict("text", include_diagnostics=True)
        self.assertNotIn("diagnostics", plain)
        self.assertIn("diagnostics", detailed)
        self.assertEqual(len(detailed["diagnostics"]["features"]), 14)

    def test_predict_input_and_flag_types_are_strict(self) -> None:
        runtime = RUNTIME.PhaseARuntime(
            bundle(-100.0), FakeM1([0.1] * 6), FakeM3([0.9] * 6)
        )
        with self.assertRaises(TypeError):
            runtime.predict(b"bytes")
        with self.assertRaises(TypeError):
            runtime.predict("text", allow_qwen=1)

    def test_runtime_makes_no_persistent_writes(self) -> None:
        runtime = RUNTIME.PhaseARuntime(
            bundle(-100.0), FakeM1([0.1] * 6), FakeM3([0.9] * 6)
        )
        with tempfile.TemporaryDirectory() as directory:
            before = set(Path(directory).iterdir())
            previous = Path.cwd()
            try:
                os.chdir(directory)
                runtime.predict("ordinary request")
            finally:
                os.chdir(previous)
            self.assertEqual(set(Path(directory).iterdir()), before)

    def test_output_schema_and_public_privacy(self) -> None:
        self.assertEqual(len(RUNNER.PARITY_SCHEMA), 14)
        self.assertEqual(RUNNER.public_sensitive_paths({"status": "ok"}), [])
        self.assertTrue(RUNNER.public_sensitive_paths({"route_score": [0.5]}))

    def test_verifier_is_independent(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import runtime_exp066", source)
        self.assertNotIn("from runtime_exp066", source)
        self.assertNotIn("import run_exp066", source)
        self.assertNotIn("from run_exp066", source)

    def test_cli_validator_requires_completion_gate_and_thin_delegation(self) -> None:
        valid = (
            "import argparse\nimport json\nimport runtime_exp066\n"
            "COMPLETION = 'runtime-complete.json'\nstatus = 'Complete'\n"
            "args = argparse.Namespace(allow_qwen=True)\n"
            "runtime = None\nruntime.predict('x', allow_qwen=args.allow_qwen, include_diagnostics=False)\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cli.py"
            path.write_text(valid, encoding="utf-8")
            FINALIZER.validate_cli(path)
            path.write_text(valid + "open('x','w')\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                FINALIZER.validate_cli(path)

    def test_frozen_config_identity_without_model_load(self) -> None:
        config = json.loads(RUNNER.DEFAULT_CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["experiment_id"], "EXP-066")
        self.assertEqual(config["environment"], RUNNER.environment_identity())
        self.assertEqual(config["parity"]["m1_probability_atol"], 1e-5)
        self.assertEqual(config["parity"]["m3_probability_atol"], 1e-5)


if __name__ == "__main__":
    unittest.main()
