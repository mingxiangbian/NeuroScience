from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest


MODULE_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = load_module("build_exp058_fold_manifest", MODULE_ROOT / "build_exp058_fold_manifest.py")
VERIFIER = load_module("verify_exp058_fold_manifest", MODULE_ROOT / "verify_exp058_fold_manifest.py")


def synthetic_rows() -> list[dict]:
    rows: list[dict] = []
    for index in range(100):
        if index < 20:
            component_index = index // 2
        else:
            component_index = index - 10
        selected = [0] * 6
        if index % 11 != 0:
            selected[index % 6] = 1
        if index % 13 == 0 and index % 11 != 0:
            selected[(index + 2) % 6] = 1
        rows.append(
            {
                "schema_version": "synthetic",
                "protocol_id": "SYNTHETIC",
                "sample_id": f"sample-{index:024x}",
                "component_id": f"component-{component_index:024x}",
                "labels": selected,
                "neutral": sum(selected) == 0,
                "label_cardinality": sum(selected),
                "text": f"synthetic row {index}",
            }
        )
    return rows


class AllocationTests(unittest.TestCase):
    def test_assignment_is_deterministic_exact_and_component_disjoint(self) -> None:
        rows = synthetic_rows()
        components = BUILDER.build_components(rows)
        first = BUILDER.allocate_components(components, fold_count=5, seed=20260816)
        second = BUILDER.allocate_components(components, fold_count=5, seed=20260816)
        self.assertEqual(first, second)
        summary = BUILDER.fold_summary(components, first, 5)
        self.assertEqual([summary["folds"][str(i)]["rows"] for i in range(5)], [20] * 5)
        self.assertEqual(len(first), 90)
        for component in components:
            folds = {first[component["component_id"]] for _ in component["rows"]}
            self.assertEqual(len(folds), 1)

    def test_train_validation_rejects_nonbinary_label_vector(self) -> None:
        rows = synthetic_rows()
        rows[1]["labels"] = [0, 0, 0, 0, 0, 2]
        with self.assertRaisesRegex(ValueError, "Invalid labels"):
            BUILDER.validate_train_rows(rows, {"data": {"expected_rows": 100}})

    def test_acceptance_rejects_rare_label_starvation(self) -> None:
        summary = {
            "folds": {
                str(index): {
                    "rows": 20,
                    "label_counts": {label: (0 if index == 0 else 5) for label in BUILDER.LABEL_ORDER},
                }
                for index in range(5)
            },
            "totals": {
                "rows": 100,
                "components": 100,
                "conflicting_duplicate_components": 0,
            },
            "maximum_label_allocation_error": 0.2,
        }
        config = {
            "acceptance_gates": {
                "rows_per_fold": 20,
                "surprise_min": 1,
                "surprise_max": 10,
                "expected_rows": 100,
                "expected_components": 100,
                "expected_conflicting_components": 0,
                "maximum_label_allocation_error": 0.25,
            }
        }
        with self.assertRaisesRegex(RuntimeError, "missing a label"):
            BUILDER.assert_acceptance(summary, config)


class PrivacyAndIndependenceTests(unittest.TestCase):
    def test_private_jsonl_is_mode_0600(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private" / "rows.jsonl"
            BUILDER.write_jsonl(path, [{"sample_id": "sample-1"}], private=True)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_public_schema_excludes_sensitive_fields(self) -> None:
        self.assertFalse(
            {"text", "labels", "neutral", "label_cardinality", "logits"}
            & set(BUILDER.PUBLIC_FIELDS)
        )

    def test_verifier_is_independent_of_builder_and_model_libraries(self) -> None:
        verifier_path = MODULE_ROOT / "verify_exp058_fold_manifest.py"
        roots = VERIFIER.imported_roots(verifier_path)
        self.assertFalse(roots & VERIFIER.FORBIDDEN_MODEL_IMPORTS)
        self.assertNotIn("build_exp058_fold_manifest", roots)


if __name__ == "__main__":
    unittest.main()
