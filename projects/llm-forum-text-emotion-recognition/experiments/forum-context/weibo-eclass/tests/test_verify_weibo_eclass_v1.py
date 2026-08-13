from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "verify_weibo_eclass_v1.py"
SPEC = importlib.util.spec_from_file_location("verify_weibo_eclass_v1", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class IndependentVerifierUnitTests(unittest.TestCase):
    def test_recursive_key_scan_finds_row_level_keys(self) -> None:
        value = {"aggregate": [{"sample_id": "private", "count": 1}]}
        self.assertIn("sample_id", MODULE.recursive_keys(value))

    def test_private_ids_are_namespaced_and_stable(self) -> None:
        key = b"x" * 32
        first = MODULE.private_id(key, "sample", "12-4")
        second = MODULE.private_id(key, "sample", "12-4")
        group = MODULE.private_id(key, "group", "12")
        self.assertEqual(first, second)
        self.assertRegex(first, MODULE.SAMPLE_ID_RE)
        self.assertRegex(group, MODULE.GROUP_ID_RE)
        self.assertNotEqual(first, group)

    def test_clause_group_requires_exact_chain(self) -> None:
        records = [
            {"sequence": 8, "prev": (), "target": ("a",), "suffix": ("b",)},
            {"sequence": 9, "prev": ("a",), "target": ("b",), "suffix": ()},
        ]
        self.assertTrue(MODULE.healthy(records))
        records[1]["sequence"] = 10
        self.assertFalse(MODULE.healthy(records))


if __name__ == "__main__":
    unittest.main()
