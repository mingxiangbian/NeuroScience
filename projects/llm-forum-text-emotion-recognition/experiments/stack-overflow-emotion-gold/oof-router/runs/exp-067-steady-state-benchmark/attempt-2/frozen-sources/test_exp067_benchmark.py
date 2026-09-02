from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))
WORKER_PATH = MODULE_DIR / "worker_exp067_benchmark.py"
RUNNER_PATH = MODULE_DIR / "run_exp067_benchmark.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp067_benchmark.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WORKER = load("exp067_worker_tests", WORKER_PATH)
RUNNER = load("exp067_runner_tests", RUNNER_PATH)


class FakeBundle:
    m1_threshold = 0.5
    m3_threshold = 0.5

    def __init__(self, route: bool) -> None:
        self.value = route

    def route(self, feature):
        return np.zeros(14), 0.9 if self.value else 0.1, self.value


class Exp067BenchmarkTests(unittest.TestCase):
    def test_latin_order_is_exact(self) -> None:
        self.assertEqual(
            RUNNER.LATIN_ORDER,
            (
                (1, "B0"), (1, "B1"), (1, "B2"),
                (2, "B1"), (2, "B2"), (2, "B0"),
                (3, "B2"), (3, "B0"), (3, "B1"),
            ),
        )
        self.assertEqual(len(set(RUNNER.LATIN_ORDER)), 9)

    def test_hierarchical_bootstrap_constant_half_latency(self) -> None:
        b1 = np.full((3, 6), 100.0)
        b2 = np.full((3, 6), 50.0)
        groups = np.asarray([0, 0, 1, 2, 3, 3], dtype=np.int16)
        result = RUNNER.hierarchical_bootstrap(b1, b2, groups, 100, 20260824)
        self.assertTrue(np.allclose(result["reduction_ci95"], [0.5, 0.5]))
        self.assertTrue(result["p95_difference_ns_ci95"][1] < 0)

    def test_hierarchical_bootstrap_is_deterministic(self) -> None:
        b1 = np.arange(1, 19, dtype=np.float64).reshape(3, 6) + 100
        b2 = b1 * 0.8
        groups = np.asarray([0, 0, 1, 2, 3, 3], dtype=np.int16)
        left = RUNNER.hierarchical_bootstrap(b1, b2, groups, 50, 20260824)
        right = RUNNER.hierarchical_bootstrap(b1, b2, groups, 50, 20260824)
        self.assertEqual(left, right)

    def test_memory_gate_pass_and_rss_fail(self) -> None:
        samples = []
        for index in range(4):
            samples.append(
                {
                    "timestamp_ns": index * 1_000_000_000,
                    "phase": 0,
                    "rss_bytes": 100,
                    "pressure_code": 0,
                    "pageouts_bytes": 0,
                    "swapouts_bytes": 0,
                    "page_size": 16384,
                }
            )
        for index in range(4, 8):
            samples.append(
                {
                    "timestamp_ns": index * 1_000_000_000,
                    "phase": 3,
                    "rss_bytes": 105,
                    "pressure_code": 0,
                    "pageouts_bytes": 0,
                    "swapouts_bytes": 0,
                    "page_size": 16384,
                }
            )
        for index in range(8, 11):
            samples.append(
                {
                    "timestamp_ns": index * 1_000_000_000,
                    "phase": 2,
                    "rss_bytes": 100,
                    "pressure_code": 0,
                    "pageouts_bytes": 0,
                    "swapouts_bytes": 0,
                    "page_size": 16384,
                }
            )
        for index in range(11, 14):
            samples.append(
                {
                    "timestamp_ns": index * 1_000_000_000,
                    "phase": 4,
                    "rss_bytes": 109,
                    "pressure_code": 0,
                    "pageouts_bytes": 0,
                    "swapouts_bytes": 0,
                    "page_size": 16384,
                }
            )
        passed = WORKER.memory_gate(samples)
        for row in samples[-3:]:
            row["rss_bytes"] = 111
        failed = WORKER.memory_gate(samples)
        self.assertTrue(passed["passed"])
        self.assertFalse(failed["passed"])

    def test_timed_row_mode_invariants_with_fake_parts(self) -> None:
        probability_m1 = np.asarray([0.9, 0.1, 0.1, 0.1, 0.1, 0.1], dtype=np.float32)
        probability_m3 = np.asarray([0.1, 0.9, 0.1, 0.1, 0.1, 0.1], dtype=np.float32)
        with mock.patch.object(WORKER, "m1_parts", return_value=(100, 200, probability_m1, 8)), mock.patch.object(
            WORKER, "m3_parts", return_value=(100, 300, probability_m3, 16)
        ):
            b0 = WORKER.timed_row("B0", "text", FakeBundle(False), object(), object())
            b1 = WORKER.timed_row("B1", "text", FakeBundle(False), object(), object())
            b2 = WORKER.timed_row("B2", "text", FakeBundle(True), object(), object())
        self.assertEqual((b0["route_mask"], b0["selected_path"]), (0, 0))
        self.assertEqual((b1["route_mask"], b1["selected_path"]), (0, 1))
        self.assertEqual((b2["route_mask"], b2["selected_path"]), (1, 1))
        self.assertEqual(b0["m3_inference_ns"], 0)
        self.assertEqual(b1["m1_inference_ns"], 0)
        self.assertGreater(b2["feature_router_ns"], 0)

    def test_vm_sampler_returns_numeric_private_values(self) -> None:
        class Result:
            def __init__(self, stdout: str) -> None:
                self.stdout = stdout

        def fake_run(command, **kwargs):
            if command[0] == "/usr/bin/memory_pressure":
                return Result("System-wide memory free percentage: 77%\n")
            if command[0] == "/usr/bin/vm_stat":
                return Result(
                    "Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
                    "Pages occupied by compressor: 10.\nPageouts: 2.\nSwapouts: 3.\n"
                )
            return Result("1024\n")

        with mock.patch.object(WORKER.subprocess, "run", side_effect=fake_run):
            value = WORKER._vm_sample()
        self.assertGreater(value["rss_bytes"], 0)
        self.assertIn(value["pressure_code"], (0, 1, 2))
        self.assertGreater(value["page_size"], 0)

    def test_public_privacy_scanner(self) -> None:
        self.assertEqual(RUNNER.public_sensitive_paths({"status": "ok"}), [])
        self.assertTrue(RUNNER.public_sensitive_paths({"route_mask": [1]}))

    def test_create_once_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "value.json"
            RUNNER._create(path, b"{}\n", 0o600)
            with self.assertRaises(FileExistsError):
                RUNNER._create(path, b"{}\n", 0o600)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_verifier_is_independent(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "import run_exp067", "from run_exp067", "import worker_exp067",
            "from worker_exp067", "import runtime_exp066", "from runtime_exp066",
        ):
            self.assertNotIn(forbidden, source)

    def test_frozen_config_without_model_load(self) -> None:
        config = json.loads(RUNNER.DEFAULT_CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["experiment_id"], "EXP-067")
        self.assertEqual(config["attempt_id"], "attempt-2")
        self.assertEqual(config["environment"], RUNNER.environment_identity())
        self.assertEqual(config["benchmark"]["worker_count"], 9)
        self.assertEqual(config["bootstrap"]["repetitions"], 10000)


if __name__ == "__main__":
    unittest.main()
