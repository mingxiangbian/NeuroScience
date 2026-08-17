from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import statistics
import sys
import unittest
from pathlib import Path


ANALYSIS_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = (
    ANALYSIS_DIR / "configs" / "exp-057-read-only-result-synthesis-attempt-2.json"
)
PROTOCOL_PATH = (
    ANALYSIS_DIR.parent / "protocols" / "exp-057-read-only-result-synthesis.md"
)


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ANALYSIS_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


analyzer = load_module("exp057_analyzer", "analyze_exp057.py")
verifier = load_module("exp057_verifier", "verify_exp057.py")


class PureFunctionTests(unittest.TestCase):
    def test_mean_std_uses_sample_standard_deviation(self) -> None:
        result = analyzer.mean_std([1.0, 2.0, 3.0])
        self.assertEqual(result["mean"], 2.0)
        self.assertEqual(result["sample_std"], 1.0)
        self.assertEqual(result["n"], 3)
        self.assertEqual(result["values"], [1.0, 2.0, 3.0])

    def test_verifier_mean_std_is_independent_and_equivalent(self) -> None:
        values = [0.1, 0.2, 0.4]
        mean, sample_std = verifier.mean_std(values)
        self.assertAlmostEqual(mean, statistics.fmean(values))
        self.assertAlmostEqual(sample_std, statistics.stdev(values))
        prepared = analyzer.mean_std(values)
        self.assertAlmostEqual(mean, prepared["mean"])
        self.assertAlmostEqual(sample_std, prepared["sample_std"])

    def test_expected_scope_is_frozen(self) -> None:
        self.assertEqual(analyzer.FAMILIES, ("m1", "m2", "m3", "m4"))
        self.assertEqual(analyzer.SEEDS, (42, 43, 44))
        self.assertEqual(
            analyzer.LABELS,
            ("love", "joy", "surprise", "anger", "sadness", "fear"),
        )
        self.assertEqual(analyzer.FAMILIES, verifier.FAMILIES)
        self.assertEqual(analyzer.SEEDS, verifier.SEEDS)
        self.assertEqual(analyzer.LABELS, verifier.LABELS)

    def test_validation_extractor_handles_m4_generation_fields(self) -> None:
        payload = {
            "metrics": {"macro_f1": {"mean": 0.5, "sample_std": 0.1}},
            "generation": {
                "empty_prediction_rate": {"mean": 0.2, "sample_std": 0.01},
                "predicted_label_cardinality_mean": {"mean": 0.8, "sample_std": 0.02},
            },
        }
        node = verifier.validation_node(payload, "m4")
        self.assertEqual(node["macro_f1"]["mean"], 0.5)
        self.assertEqual(node["empty_prediction_rate"]["mean"], 0.2)
        self.assertEqual(node["predicted_label_cardinality_mean"]["mean"], 0.8)

    def test_validation_extractor_converts_empty_rows_to_rate(self) -> None:
        payload = {
            "aggregate": {
                "metrics": {
                    "shared_threshold": {
                        "empty_prediction_rows": {
                            "values": [72, 144, 216],
                        }
                    }
                }
            }
        }
        node = analyzer.validation_metric_node(payload, "m1")
        self.assertAlmostEqual(node["empty_prediction_rate"]["mean"], 0.2)
        self.assertAlmostEqual(node["empty_prediction_rate"]["sample_std"], 0.1)
        checked = verifier.validation_node(payload, "m1")
        self.assertAlmostEqual(checked["empty_prediction_rate"]["mean"], 0.2)
        self.assertAlmostEqual(checked["empty_prediction_rate"]["sample_std"], 0.1)

    def test_claims_keep_causal_and_mechanism_boundaries(self) -> None:
        rows = [
            {"contrast": name}
            for name in analyzer.EXPECTED_CONTRASTS
        ]
        claims = analyzer.build_claims(rows)
        self.assertEqual(len(claims), 5)
        text = " ".join(row["claim"] + " " + row["basis"] for row in claims).lower()
        self.assertIn("generation itself", text)
        self.assertIn("mechanism", text)
        self.assertIn("cross zero", text)


class BoundaryTests(unittest.TestCase):
    def test_config_freezes_read_only_sources(self) -> None:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(config["experiment_id"], "EXP-057")
        self.assertEqual(config["tier"], "Major")
        for key in (
            "training_authorized",
            "inference_authorized",
            "private_prediction_access_authorized",
            "test_label_access_authorized",
            "selection_or_tuning_authorized",
        ):
            self.assertIs(config[key], False)
        self.assertEqual(set(config["sources"]), {
            "exp051_aggregate", "exp051_verification",
            "exp052_aggregate", "exp052_verification",
            "exp053_aggregate", "exp053_verification",
            "exp054_aggregate", "exp054_verification",
            "exp055_summary", "exp055_verification",
            "exp056_results", "exp056_verification",
        })
        for record in config["sources"].values():
            lowered = record["path"].lower()
            self.assertNotIn("derived-private", lowered)
            self.assertNotIn("/private/", lowered)
            self.assertFalse(lowered.endswith(".npz"))
            path = analyzer.resolve(record["path"])
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.stat().st_size, record["bytes"], path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"], path)

    def test_implementation_and_protocol_hashes_are_bound(self) -> None:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        for record in config["implementation"].values():
            path = analyzer.resolve(record["path"])
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.stat().st_size, record["bytes"], path)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"], path)

    def test_protocol_states_consumed_test_and_no_new_analysis(self) -> None:
        protocol = PROTOCOL_PATH.read_text(encoding="utf-8").lower()
        self.assertIn("post-test", protocol)
        self.assertIn("does not", protocol)
        self.assertIn("test labels", protocol)
        self.assertIn("private", protocol)
        self.assertIn("seven test positives", protocol)
        self.assertIn("mechanism", protocol)

    def test_verifier_does_not_import_analyzer(self) -> None:
        tree = ast.parse((ANALYSIS_DIR / "verify_exp057.py").read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertNotIn("analyze_exp057", imported)
        self.assertNotIn("exp057_analyzer", imported)

    def test_analyzer_has_no_training_or_inference_dependencies(self) -> None:
        source = (ANALYSIS_DIR / "analyze_exp057.py").read_text(encoding="utf-8")
        for package in ("torch", "transformers", "mlx", "numpy", "sklearn"):
            self.assertNotIn(f"import {package}", source)
            self.assertNotIn(f"from {package}", source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("requests", source)


if __name__ == "__main__":
    unittest.main()
