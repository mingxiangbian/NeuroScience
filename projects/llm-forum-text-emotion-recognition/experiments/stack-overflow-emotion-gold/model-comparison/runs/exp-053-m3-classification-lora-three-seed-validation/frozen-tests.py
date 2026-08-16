from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[2]
PROTOCOL = (
    PROJECT_ROOT
    / "experiments/stack-overflow-emotion-gold/protocols/exp-053-m3-three-seed-aggregate-authorization.md"
)
RUNNER = ROOT / "aggregate_exp053_m3.py"
VERIFIER = ROOT / "verify_exp053_aggregate.py"
CONFIG = ROOT / "configs/exp-053-m3-three-seed-aggregate.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = load_module("aggregate_exp053_m3", RUNNER)
verifier = load_module("verify_exp053_aggregate", VERIFIER)


class AggregateContractTests(unittest.TestCase):
    def test_protocol_freezes_scope_statistics_and_boundaries(self):
        normalized = " ".join(PROTOCOL.read_text(encoding="utf-8").split())
        for required in (
            "arithmetic mean",
            "sample standard deviation",
            "No pooled predictions",
            "no p-value",
            "Cross-model resource comparison is not authorized",
            "Stack Overflow test remains sealed",
            "EXP-054 M4",
            "error analysis",
        ):
            self.assertIn(required, normalized)

    def test_config_authorizes_only_read_only_m3_aggregate(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        authorization = config["authorization"]
        self.assertEqual(authorization["seeds"], [42, 43, 44])
        self.assertTrue(authorization["m3_aggregate_authorized"])
        self.assertFalse(authorization["m3_training_authorized"])
        self.assertFalse(authorization["test_access"])
        self.assertFalse(authorization["test_ready"])
        self.assertFalse(authorization["m4_authorized"])
        self.assertFalse(authorization["error_analysis_authorized"])
        self.assertFalse(authorization["read_private_artifacts"])

    def test_config_binds_successful_seed42_attempt_and_seed44_correction(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        seed42, _, seed44 = config["m3_sources"]
        self.assertTrue(seed42["verification"]["path"].endswith("verification-attempt-2.json"))
        self.assertEqual(seed42["verification"]["check_count"], 148)
        self.assertIn("prior_failed_verification", seed42)
        self.assertIn("documentation_correction", seed44)
        self.assertTrue(
            seed44["documentation_correction"]["path"].endswith("seed-44/CORRECTION.md")
        )

    def test_method_keeps_comparisons_descriptive(self):
        method = json.loads(CONFIG.read_text(encoding="utf-8"))["method"]
        self.assertEqual(method["paired_references"], ["EXP-051", "EXP-052"])
        self.assertTrue(method["pair_by_seed"])
        self.assertFalse(method["pool_predictions_across_seeds"])
        self.assertFalse(method["inferential_test"])
        self.assertTrue(method["aggregate_m3_resources"])
        self.assertFalse(method["cross_model_resource_comparison"])

    def test_scalar_summary_uses_sample_standard_deviation(self):
        summary = runner.scalar_summary([1.0, 2.0, 3.0])
        self.assertEqual(summary, {"values": [1.0, 2.0, 3.0], "mean": 2.0, "sample_std": 1.0, "n": 3})

    def test_independent_formula_matches_known_values(self):
        summary = verifier.independent_summary([1.0, 2.0, 3.0])
        self.assertEqual(summary, {"values": [1.0, 2.0, 3.0], "mean": 2.0, "sample_std": 1.0, "n": 3})

    def test_summary_rejects_non_three_seed_input(self):
        with self.assertRaises(ValueError):
            runner.scalar_summary([1.0, 2.0])
        with self.assertRaises(ValueError):
            verifier.independent_summary([1.0, 2.0])

    def test_runner_uses_only_explicit_public_sources(self):
        source = RUNNER.read_text(encoding="utf-8")
        self.assertNotIn("rglob(", source)
        self.assertNotIn(".glob(", source)
        self.assertNotIn("predictions.csv", source)
        self.assertNotIn("probabilities.npy", source)
        self.assertIn('config["m3_sources"]', source)
        config_text = CONFIG.read_text(encoding="utf-8")
        self.assertNotIn("/private/", config_text)
        self.assertNotIn("validation-predictions", config_text)

    def test_verifier_is_independent_of_runner_implementation(self):
        source = VERIFIER.read_text(encoding="utf-8")
        self.assertNotIn("import aggregate_exp053_m3", source)
        self.assertNotIn("from aggregate_exp053_m3", source)
        self.assertIn("def independent_summary", source)
        self.assertIn("def independently_aggregate", source)

    def test_report_language_keeps_claim_and_stage_boundaries(self):
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn("validation-only M3 family result", source)
        self.assertIn("descriptive for three seed-matched runs", source)
        self.assertIn("not a cross-model cost comparison", source)
        self.assertIn("seven validation positives", source)
        self.assertIn("Test, TEST-READY, EXP-054 and error analysis remain sealed", source)


if __name__ == "__main__":
    unittest.main()
