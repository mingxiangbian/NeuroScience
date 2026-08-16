from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[2]
PROTOCOL = (
    PROJECT_ROOT
    / "experiments/stack-overflow-emotion-gold/protocols/exp-052-m2-three-seed-aggregate-authorization.md"
)
RUNNER = ROOT / "aggregate_exp052_m2.py"
VERIFIER = ROOT / "verify_exp052_aggregate.py"
CONFIG = ROOT / "configs/exp-052-m2-three-seed-aggregate.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = load_module("aggregate_exp052_m2", RUNNER)
verifier = load_module("verify_exp052_aggregate", VERIFIER)


class AggregateContractTests(unittest.TestCase):
    def test_protocol_freezes_scope_and_statistics(self):
        text = PROTOCOL.read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        for required in (
            "arithmetic mean",
            "sample standard deviation",
            "No pooled predictions",
            "no p-value",
            "Resource measurements are reported per seed only",
            "Stack Overflow test remains sealed",
            "EXP-053 M3",
            "EXP-054 M4",
        ):
            self.assertIn(required, normalized)

    def test_config_authorizes_only_read_only_aggregate(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["authorization"]["seeds"], [42, 43, 44])
        self.assertFalse(config["authorization"]["test_access"])
        self.assertFalse(config["authorization"]["test_ready"])
        self.assertFalse(config["authorization"]["m3_authorized"])
        self.assertFalse(config["authorization"]["m4_authorized"])
        self.assertFalse(config["authorization"]["read_private_artifacts"])
        self.assertFalse(config["method"]["pool_predictions_across_seeds"])
        self.assertFalse(config["method"]["inferential_test"])
        self.assertFalse(config["method"]["aggregate_resources"])

    def test_scalar_summary_uses_sample_standard_deviation(self):
        summary = runner.scalar_summary([1.0, 2.0, 3.0])
        self.assertEqual(summary["mean"], 2.0)
        self.assertEqual(summary["sample_std"], 1.0)
        self.assertEqual(summary["n"], 3)

    def test_independent_formula_matches_known_values(self):
        summary = verifier.independent_summary([1.0, 2.0, 3.0])
        self.assertEqual(summary["mean"], 2.0)
        self.assertEqual(summary["sample_std"], 1.0)
        self.assertEqual(summary["n"], 3)

    def test_summary_rejects_non_three_seed_input(self):
        with self.assertRaises(ValueError):
            runner.scalar_summary([1.0, 2.0])
        with self.assertRaises(ValueError):
            verifier.independent_summary([1.0, 2.0])

    def test_runner_uses_explicit_sources_without_recursive_discovery(self):
        source = RUNNER.read_text(encoding="utf-8")
        self.assertNotIn("rglob(", source)
        self.assertNotIn(".glob(", source)
        self.assertNotIn("predictions.csv", source)
        self.assertNotIn("probabilities.npy", source)
        self.assertIn('config["m2_sources"]', source)

    def test_verifier_is_independent_of_runner_implementation(self):
        source = VERIFIER.read_text(encoding="utf-8")
        self.assertNotIn("import aggregate_exp052_m2", source)
        self.assertNotIn("from aggregate_exp052_m2", source)
        self.assertIn("def independent_summary", source)
        self.assertIn("def independently_aggregate", source)

    def test_report_language_keeps_inference_and_resource_boundaries(self):
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn("descriptive for three matched seeds", source)
        self.assertIn("not averaged into a family cost", source)
        self.assertIn("Test, TEST-READY, EXP-053 and EXP-054 remain sealed", source)


if __name__ == "__main__":
    unittest.main()
