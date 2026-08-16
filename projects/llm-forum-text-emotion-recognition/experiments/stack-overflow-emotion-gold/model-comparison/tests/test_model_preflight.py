from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, MODULE_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = load_module("so_preflight_runner", "run_preflight.py")
parser = load_module("so_strict_parser", "strict_multilabel_parser.py")
verifier = load_module("so_preflight_verifier", "verify_preflight.py")


class StrictParserTests(unittest.TestCase):
    def test_accepts_only_canonical_json(self):
        cases = {
            '{"emotions":[]}': (True, None),
            '{"emotions":["love","anger"]}': (True, None),
            ' {"emotions":[]}': (False, "outer_whitespace_or_empty"),
            '{"emotions": ["love"]}': (False, "noncanonical_json"),
            '{"emotions":["anger","love"]}': (False, "noncanonical_order"),
            '{"emotions":["love","love"]}': (False, "duplicate_label"),
            '{"emotions":["neutral"]}': (False, "unknown_label"),
            '{"emotions":[1]}': (False, "emotions_not_string_list"),
            '{"emotions":[],"note":"x"}': (False, "schema_keys"),
            'anger': (False, "invalid_json"),
            '': (False, "outer_whitespace_or_empty"),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                observed = parser.parse_output(raw)
                self.assertEqual((observed["valid"], observed["error"]), expected)
                self.assertEqual(observed, verifier.strict_parse(raw))

    def test_canonical_target_follows_frozen_order(self):
        self.assertEqual(
            parser.canonical_target([1, 0, 0, 1, 0, 1]),
            '{"emotions":["love","anger","fear"]}',
        )
        with self.assertRaises(ValueError):
            parser.canonical_target([1, 0])


class SelectionTests(unittest.TestCase):
    @staticmethod
    def rows():
        rows = []
        for label_index in range(6):
            for copy in range(3):
                labels = [0] * 6
                labels[label_index] = 1
                rows.append(
                    {
                        "sample_id": f"positive-{label_index}-{copy}",
                        "component_id": f"component-positive-{label_index}-{copy}",
                        "labels": labels,
                        "label_cardinality": 1,
                        "neutral": False,
                    }
                )
        for index in range(8):
            rows.append(
                {
                    "sample_id": f"neutral-{index}",
                    "component_id": f"component-neutral-{index}",
                    "labels": [0] * 6,
                    "label_cardinality": 0,
                    "neutral": True,
                }
            )
        for index in range(8):
            labels = [0] * 6
            labels[index % 6] = 1
            labels[(index + 1) % 6] = 1
            rows.append(
                {
                    "sample_id": f"multi-{index}",
                    "component_id": f"component-multi-{index}",
                    "labels": labels,
                    "label_cardinality": 2,
                    "neutral": False,
                }
            )
        return rows

    def test_selection_is_deterministic_covered_and_independently_reproduced(self):
        config = {
            "data": {"labels": list(parser.DEFAULT_LABELS)},
            "preflight": {"selection_namespace": "unit-test-v1", "sample_rows": 24},
        }
        first = runner.select_smoke_rows(self.rows(), config)
        second = runner.select_smoke_rows(list(reversed(self.rows())), config)
        independent = verifier.independently_select(self.rows(), config)
        self.assertEqual([row["sample_id"] for row in first], [row["sample_id"] for row in second])
        self.assertEqual([row["sample_id"] for row in first], [row["sample_id"] for row in independent])
        self.assertEqual(len(first), 24)
        self.assertGreaterEqual(sum(row["neutral"] for row in first), 4)
        self.assertGreaterEqual(sum(row["label_cardinality"] == 2 for row in first), 4)
        for index in range(6):
            positives = sum(row["labels"][index] for row in first)
            self.assertGreaterEqual(positives, 2)
            self.assertLess(positives, len(first))

    def test_numeric_summary_contract(self):
        values = list(range(1, 101))
        expected = {"min": 1, "p50": 51, "p95": 96, "p99": 100, "max": 100}
        self.assertEqual(runner.numeric_summary(values), expected)
        self.assertEqual(verifier.numeric_summary(values), expected)


class FrozenContractTests(unittest.TestCase):
    def test_config_and_prompt_hashes(self):
        config_path = MODULE_DIR / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["preflight"]["experiment_id"], "EXP-050")
        self.assertFalse(config["preflight"]["validation_access"])
        self.assertFalse(config["preflight"]["test_access"])
        self.assertFalse(config["formal_execution_authorized"])
        self.assertEqual(runner.sha256(MODULE_DIR / "prompt-v1.json"), config["prompt"]["sha256"])

    def test_runner_has_explicit_train_only_access(self):
        audit = verifier.source_access_audit(MODULE_DIR / "run_preflight.py")
        self.assertTrue(all(audit.values()), audit)

    def test_m2_hashes_the_head_in_the_same_scope_as_m3(self):
        source = (MODULE_DIR / "run_preflight.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(
            source.count("mlx_tensor_digest(mlx_trainable(head))"),
            4,
        )


if __name__ == "__main__":
    unittest.main()
