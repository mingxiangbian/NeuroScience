from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

import numpy as np


ERROR_ANALYSIS_DIR = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = (
    ERROR_ANALYSIS_DIR.parent
    / "protocols"
    / "exp-055-m1-m3-validation-error-analysis.md"
)
CONFIG_PATH = ERROR_ANALYSIS_DIR / "configs" / "exp-055-m1-m3-validation-error-analysis.json"


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ERROR_ANALYSIS_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


analyzer = load_module("exp055_analyzer", "analyze_exp055.py")
verifier = load_module("exp055_verifier", "verify_exp055.py")
finalizer = load_module("exp055_finalizer", "finalize_exp055.py")


class MetricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gold = np.asarray(
            [
                [1, 0, 0, 0, 0, 0],
                [0, 1, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0],
                [0, 0, 0, 1, 1, 0],
            ],
            dtype=np.uint8,
        )
        self.predicted = np.asarray(
            [
                [1, 0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0],
                [0, 0, 0, 1, 0, 0],
                [0, 0, 0, 1, 0, 0],
            ],
            dtype=np.uint8,
        )

    def test_metric_bundle_matches_hand_calculation(self) -> None:
        metrics = analyzer.metric_bundle(self.gold, self.predicted)
        self.assertAlmostEqual(metrics["macro_f1"], 5 / 18)
        self.assertAlmostEqual(metrics["micro_f1"], 4 / 7)
        self.assertAlmostEqual(metrics["weighted_f1"], 5 / 12)
        self.assertAlmostEqual(metrics["subset_accuracy"], 1 / 4)
        self.assertAlmostEqual(metrics["samples_f1_zero_division_0"], 5 / 12)
        self.assertAlmostEqual(metrics["hamming_loss"], 1 / 8)
        self.assertAlmostEqual(metrics["five_label_macro_f1_without_surprise"], 1 / 3)
        self.assertEqual(metrics["per_label"]["anger"]["tp"], 1)
        self.assertEqual(metrics["per_label"]["anger"]["fp"], 1)
        self.assertAlmostEqual(metrics["per_label"]["anger"]["f1"], 2 / 3)

    def test_independent_verifier_matches_analyzer_metrics(self) -> None:
        prepared = analyzer.metric_bundle(self.gold, self.predicted)
        checked = verifier.metrics(self.gold, self.predicted)
        for key in (
            "macro_f1",
            "macro_precision",
            "macro_recall",
            "micro_f1",
            "weighted_f1",
            "subset_accuracy",
            "samples_f1_zero_division_0",
            "hamming_loss",
            "five_label_macro_f1_without_surprise",
        ):
            self.assertAlmostEqual(prepared[key], checked[key])
        self.assertEqual(prepared["per_label"], checked["per_label"])

    def test_mean_std_uses_sample_standard_deviation(self) -> None:
        summary = analyzer.mean_std([1.0, 2.0, 3.0])
        self.assertEqual(summary["values"], [1.0, 2.0, 3.0])
        self.assertEqual(summary["mean"], 2.0)
        self.assertEqual(summary["sample_std"], 1.0)


class SamplingTests(unittest.TestCase):
    def test_case_ids_and_ranks_are_deterministic_and_pseudonymous(self) -> None:
        first = analyzer.case_id("raw-sample-id")
        self.assertEqual(first, analyzer.case_id("raw-sample-id"))
        self.assertNotEqual(first, analyzer.case_id("different-id"))
        self.assertTrue(first.startswith("case-"))
        self.assertEqual(len(first), 21)
        self.assertEqual(
            analyzer.deterministic_rank("role", "sample"),
            analyzer.deterministic_rank("role", "sample"),
        )
        self.assertNotEqual(
            analyzer.deterministic_rank("role", "sample"),
            analyzer.deterministic_rank("other-role", "sample"),
        )

    def test_label_names_preserve_frozen_order_and_neutral(self) -> None:
        self.assertEqual(analyzer.label_names(np.zeros(6, dtype=np.uint8)), "neutral")
        vector = np.asarray([1, 0, 0, 1, 0, 1], dtype=np.uint8)
        self.assertEqual(analyzer.label_names(vector), "love;anger;fear")
        self.assertEqual(analyzer.gold_stratum(vector), "love;anger;fear")

    def test_role_sampling_respects_used_rows_and_first_pass_stratum_cap(self) -> None:
        sample_ids = [f"sample-{index}" for index in range(7)]
        gold = np.asarray(
            [
                [1, 0, 0, 0, 0, 0],
                [1, 0, 0, 0, 0, 0],
                [1, 0, 0, 0, 0, 0],
                [0, 1, 0, 0, 0, 0],
                [0, 1, 0, 0, 0, 0],
                [0, 0, 0, 1, 0, 0],
                [0, 0, 0, 1, 0, 0],
            ],
            dtype=np.uint8,
        )
        selected = analyzer.select_role(
            "test-role", list(range(7)), 5, sample_ids, gold, {0}
        )
        self.assertEqual(len(selected), 5)
        self.assertEqual(len(set(selected)), 5)
        self.assertNotIn(0, selected)
        strata = Counter(analyzer.gold_stratum(gold[index]) for index in selected)
        self.assertTrue(all(count <= 2 for count in strata.values()))

    def test_component_bootstrap_is_deterministic_and_zero_for_identical_oracle(self) -> None:
        gold = np.asarray(
            [
                [1, 0, 0, 0, 0, 0],
                [0, 1, 0, 0, 0, 0],
                [0, 0, 0, 1, 0, 0],
                [0, 0, 0, 0, 1, 0],
            ],
            dtype=np.uint8,
        )
        predicted = gold.copy()
        kwargs = {
            "gold": gold,
            "m1": predicted,
            "oracle": predicted,
            "component_ids": ["a", "a", "b", "c"],
            "seed": 42,
            "condition": "shared_threshold",
            "replicates": 50,
        }
        first = analyzer.component_bootstrap(**kwargs)
        second = analyzer.component_bootstrap(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(first["six_label_delta_ci95"], [0.0, 0.0])
        self.assertEqual(first["five_label_delta_ci95"], [0.0, 0.0])


class BoundaryTests(unittest.TestCase):
    def test_config_binds_frozen_validation_sources_and_seals_other_actions(self) -> None:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(config["experiment_id"], "EXP-055")
        self.assertEqual(config["source_splits"], ["validation"])
        for key in (
            "training_authorized",
            "inference_authorized",
            "test_access",
            "exp054_authorized",
            "test_ready",
        ):
            self.assertIs(config[key], False)
        self.assertTrue(config["validation"]["path"].endswith("validation.jsonl"))
        self.assertEqual([row["seed"] for row in config["sources"]["m1"]], [42, 43, 44])
        self.assertEqual([row["seed"] for row in config["sources"]["m3"]], [42, 43, 44])

        records = [config["validation"], config["protocol"]]
        records.extend(config["implementation"].values())
        records.extend(config["upstream_aggregates"])
        for family in ("m1", "m3"):
            for source in config["sources"][family]:
                records.extend((source["predictions"], source["verification"]))
        for record in records:
            path = analyzer.resolve(record["path"])
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.stat().st_size, record["bytes"], path)
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"], path
            )

    def test_protocol_freezes_validation_only_scope_and_sampling_budget(self) -> None:
        protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
        self.assertIn("validation", protocol.lower())
        self.assertIn("test", protocol.lower())
        self.assertIn("48", protocol)
        self.assertIn("tie", protocol.lower())
        self.assertIn("M1", protocol)
        self.assertIn("one reviewer", protocol.lower())

    def test_verifier_does_not_import_analysis_or_finalizer_modules(self) -> None:
        tree = ast.parse((ERROR_ANALYSIS_DIR / "verify_exp055.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertNotIn("analyze_exp055", imported)
        self.assertNotIn("finalize_exp055", imported)

    def test_finalizer_keeps_single_reviewer_and_fixed_taxonomy(self) -> None:
        self.assertIn("annotation_or_data_uncertainty", finalizer.ALLOWED_SOURCES)
        self.assertIn("missing_forum_context", finalizer.ALLOWED_SOURCES)
        self.assertIn("sarcasm_or_irony", finalizer.ALLOWED_FLAGS)
        self.assertIn("low_support_surprise", finalizer.ALLOWED_FLAGS)
        self.assertNotIn("free_text_note", finalizer.ALLOWED_FLAGS)

    def test_final_report_is_result_conditioned_and_writes_summary(self) -> None:
        source = (ERROR_ANALYSIS_DIR / "finalize_exp055.py").read_text(encoding="utf-8")
        self.assertNotIn("M3's six-label advantage does not extend", source)
        self.assertIn('write_json(run_dir / "summary.json", summary)', source)
        verifier_source = (ERROR_ANALYSIS_DIR / "verify_exp055.py").read_text(encoding="utf-8")
        self.assertIn('summary = load_json(run_dir / "summary.json")', verifier_source)

    def test_frozen_labels_match_across_analyzer_and_verifier(self) -> None:
        expected = ("love", "joy", "surprise", "anger", "sadness", "fear")
        self.assertEqual(analyzer.LABELS, expected)
        self.assertEqual(verifier.LABELS, expected)
        self.assertEqual(analyzer.SURPRISE_INDEX, 2)
        self.assertEqual(verifier.SURPRISE_INDEX, 2)


if __name__ == "__main__":
    unittest.main()
