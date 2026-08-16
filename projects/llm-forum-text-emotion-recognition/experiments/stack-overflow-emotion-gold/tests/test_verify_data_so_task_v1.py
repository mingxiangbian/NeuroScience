from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "verify_data_so_task_v1.py"
SPEC = importlib.util.spec_from_file_location("verify_data_so_task_v1", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class IndependentVerifierUnitTests(unittest.TestCase):
    def test_independent_id_matches_frozen_shape(self) -> None:
        value = {"coordinate": ("B", "Third", 9), "text": "example"}
        sample_id = MODULE.independent_id("sample", value)
        self.assertRegex(sample_id, MODULE.SAMPLE_ID_RE)
        self.assertEqual(sample_id, MODULE.independent_id("sample", value))

    def test_recursive_scan_finds_nested_row_fields(self) -> None:
        value = {"aggregate": [{"safe": 1, "text": "leak"}]}
        self.assertIn("text", MODULE.recursive_keys(value))
        self.assertIn("leak", MODULE.recursive_strings(value))

    def test_disjoint_set_is_transitive(self) -> None:
        value = MODULE.DisjointSet(5)
        value.join(1, 2)
        value.join(2, 4)
        self.assertEqual(value.root(1), value.root(4))
        self.assertNotEqual(value.root(0), value.root(4))

    def test_component_bucket_is_structural(self) -> None:
        self.assertEqual(
            MODULE.component_bucket({"size": 4, "conflicting": False}),
            "duplicate-size-4",
        )
        self.assertEqual(
            MODULE.component_bucket({"size": 2, "conflicting": True}),
            "duplicate-conflict-size-2",
        )


if __name__ == "__main__":
    unittest.main()
