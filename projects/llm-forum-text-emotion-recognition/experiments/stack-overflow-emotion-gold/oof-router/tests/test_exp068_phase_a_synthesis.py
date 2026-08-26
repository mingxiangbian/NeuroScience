from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp068_phase_a_synthesis.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp068_phase_a_synthesis.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load("exp068_runner_tests", RUNNER_PATH)


class Exp068PhaseASynthesisTests(unittest.TestCase):
    def test_verified_state_requires_complete_benchmark_and_gates(self) -> None:
        result = RUNNER.decide(True, True, True, "Moderate", True)
        self.assertEqual(result["state"], "Verified local development inference prototype")
        self.assertTrue(result["deployment_efficiency_claim_supported"])

    def test_research_demo_state_requires_completed_benchmark(self) -> None:
        result = RUNNER.decide(True, True, True, "Insufficient", False)
        self.assertEqual(result["state"], "Retained as research demo")
        self.assertTrue(result["verified_headless_cli_research_demo"])
        self.assertFalse(result["deployment_efficiency_claim_supported"])

    def test_incomplete_benchmark_forces_failed_or_incomplete(self) -> None:
        result = RUNNER.decide(True, True, False, None, False)
        self.assertEqual(result["state"], "Failed or incomplete")
        self.assertTrue(result["verified_headless_cli_research_demo"])
        self.assertFalse(result["formal_efficiency_benchmark_complete"])

    def test_public_resolver_rejects_private_paths(self) -> None:
        with self.assertRaises(PermissionError):
            RUNNER._resolve_public("experiments/private/value.json")

    def test_public_privacy_scanner(self) -> None:
        self.assertEqual(RUNNER.public_sensitive_paths({"status": "ok"}), [])
        self.assertTrue(RUNNER.public_sensitive_paths({"timing_rows": []}))

    def test_create_once_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "value.json"
            RUNNER._create(path, b"{}\n")
            with self.assertRaises(FileExistsError):
                RUNNER._create(path, b"{}\n")
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o644)

    def test_verifier_is_independent(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import run_exp068", source)
        self.assertNotIn("from run_exp068", source)

    def test_frozen_current_decision(self) -> None:
        config = json.loads(RUNNER.DEFAULT_CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["experiment_id"], "EXP-068")
        self.assertEqual(config["decision_rules"]["expected_current_state"], "Failed or incomplete")


if __name__ == "__main__":
    unittest.main()
