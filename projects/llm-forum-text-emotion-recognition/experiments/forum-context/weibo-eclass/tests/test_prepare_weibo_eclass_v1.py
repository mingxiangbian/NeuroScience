from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "prepare_weibo_eclass_v1.py"
SPEC = importlib.util.spec_from_file_location("prepare_weibo_eclass_v1", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def row(source_id: str = "12-4", label: str = "快乐") -> list[str]:
    return [
        source_id,
        label,
        "beg_preclause",
        "前文",
        "end_preclause",
        "beg_curclause",
        "目标",
        "end_curclause",
        "beg_sufclause",
        "后文",
        "end_sufclause",
    ]


class ParserTests(unittest.TestCase):
    def test_parse_valid_eclass_row(self) -> None:
        parsed, error = MODULE.parse_eclass_row(row(), 7)
        self.assertIsNone(error)
        self.assertEqual(parsed["source_group_id"], "12")
        self.assertEqual(parsed["sequence"], 4)
        self.assertEqual(parsed["target_tokens"], ("目标",))

    def test_rejects_missing_marker(self) -> None:
        value = row()
        value.remove("end_curclause")
        parsed, error = MODULE.parse_eclass_row(value, 0)
        self.assertIsNone(parsed)
        self.assertEqual(error, "marker_multiplicity")

    def test_group_continuity(self) -> None:
        records = [
            {
                "sequence": 3,
                "prev_tokens": (),
                "target_tokens": ("甲",),
                "suffix_tokens": ("乙",),
            },
            {
                "sequence": 4,
                "prev_tokens": ("甲",),
                "target_tokens": ("乙",),
                "suffix_tokens": (),
            },
        ]
        self.assertTrue(MODULE.group_is_consistent(records))
        records[1]["prev_tokens"] = ("不一致",)
        self.assertFalse(MODULE.group_is_consistent(records))


class TransformationTests(unittest.TestCase):
    def test_sanitize_redacts_url_and_mention(self) -> None:
        value = MODULE.sanitize_text(("@someone", " 看 ", "https://example.com/a"))
        self.assertEqual(value, "<USER> 看 <URL>")

    def test_neutral_and_no_emotion_are_distinct(self) -> None:
        self.assertEqual(MODULE.LABEL_MAP["中性"], "neutral")
        self.assertEqual(MODULE.LABEL_MAP["No_emotion"], "no_emotion")
        self.assertNotEqual(MODULE.LABEL_MAP["中性"], MODULE.LABEL_MAP["No_emotion"])

    def test_canonical_prefers_available_context_per_target_label(self) -> None:
        records = [
            {
                "target_key": "相同",
                "label": "joy",
                "context_available": False,
                "logical_index": 1,
            },
            {
                "target_key": "相同",
                "label": "joy",
                "context_available": True,
                "logical_index": 9,
            },
            {
                "target_key": "相同",
                "label": "anger",
                "context_available": True,
                "logical_index": 10,
            },
        ]
        selected = MODULE.select_canonical(records)
        self.assertEqual(len(selected), 2)
        self.assertEqual({value["label"] for value in selected}, {"joy", "anger"})
        joy = next(value for value in selected if value["label"] == "joy")
        self.assertEqual(joy["logical_index"], 9)


class SplitTests(unittest.TestCase):
    def test_component_allocator_is_deterministic_and_balanced(self) -> None:
        components = []
        labels = list(MODULE.LABEL_ORDER)
        for index in range(140):
            label = labels[index % len(labels)]
            record = {
                "label": label,
                "context_available": index % 3 != 0,
                "ambiguous_target": index % 11 == 0,
            }
            strata = MODULE.Counter({label: 1})
            strata["__context_available__"] = int(record["context_available"])
            strata["__context_missing__"] = int(not record["context_available"])
            strata["__ambiguous_target__"] = int(record["ambiguous_target"])
            components.append(
                {
                    "fingerprint": f"{index:064x}",
                    "records": [record],
                    "row_count": 1,
                    "strata": strata,
                }
            )
        first = MODULE.allocate_splits(components)
        second = MODULE.allocate_splits(components)
        self.assertEqual(first, second)
        counts = MODULE.Counter(first.values())
        self.assertEqual(counts["train"], 98)
        self.assertEqual(counts["validation"], 21)
        self.assertEqual(counts["test"], 21)


if __name__ == "__main__":
    unittest.main()
