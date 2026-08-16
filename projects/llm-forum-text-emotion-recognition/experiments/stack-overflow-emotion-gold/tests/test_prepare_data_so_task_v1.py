from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "prepare_data_so_task_v1.py"
SPEC = importlib.util.spec_from_file_location("prepare_data_so_task_v1", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CellParsingTests(unittest.TestCase):
    def test_rater_mark_is_case_insensitive(self) -> None:
        self.assertTrue(MODULE.marked("X"))
        self.assertTrue(MODULE.marked(" x "))
        self.assertFalse(MODULE.marked(None))
        self.assertFalse(MODULE.marked(""))

    def test_rater_mark_rejects_unknown_token(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.marked("yes")

    def test_gold_token_must_match_label(self) -> None:
        self.assertTrue(MODULE.gold_present(" LOVE ", "love"))
        self.assertFalse(MODULE.gold_present(None, "love"))
        with self.assertRaises(ValueError):
            MODULE.gold_present("JOY", "love")


class IdentityAndDuplicateTests(unittest.TestCase):
    def test_duplicate_normalization_is_conservative(self) -> None:
        self.assertEqual(
            MODULE.normalized_text("  Fullwidth：Ａ\nB  "),
            MODULE.normalized_text("fullwidth:A b"),
        )
        self.assertNotEqual(
            MODULE.normalized_text("answer one"),
            MODULE.normalized_text("answer two"),
        )

    def test_opaque_ids_are_stable_and_namespaced(self) -> None:
        value = {"coordinate": ("A", "Second", 7), "text": "hello"}
        first = MODULE.opaque_id("sample", value)
        second = MODULE.opaque_id("sample", value)
        component = MODULE.opaque_id("component", [first])
        self.assertEqual(first, second)
        self.assertRegex(first, r"^sample-[0-9a-f]{24}$")
        self.assertRegex(component, r"^component-[0-9a-f]{24}$")
        self.assertNotEqual(first, component)

    def test_union_find_connects_transitive_duplicates(self) -> None:
        value = MODULE.UnionFind(range(4))
        value.union(0, 1)
        value.union(1, 2)
        self.assertEqual(value.find(0), value.find(2))
        self.assertNotEqual(value.find(0), value.find(3))

    def test_component_bucket_distinguishes_conflicts(self) -> None:
        self.assertEqual(
            MODULE.allocation_bucket({"row_count": 1, "conflicting_labels": False}),
            "singleton",
        )
        self.assertEqual(
            MODULE.allocation_bucket({"row_count": 2, "conflicting_labels": True}),
            "duplicate-conflict-size-2",
        )


if __name__ == "__main__":
    unittest.main()
