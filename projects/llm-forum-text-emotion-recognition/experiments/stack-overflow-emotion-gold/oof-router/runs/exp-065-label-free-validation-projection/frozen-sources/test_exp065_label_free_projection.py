from __future__ import annotations

import ast
from io import BytesIO
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp065_label_free_projection.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp065_label_free_projection.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load("exp065_runner_tests", RUNNER_PATH)
VERIFIER = load("exp065_verifier_tests", VERIFIER_PATH)


def synthetic_rows(label_value: int) -> list[dict]:
    return [
        {
            "schema_version": "synthetic-v1",
            "protocol_id": "synthetic",
            "sample_id": f"sample-{index}",
            "component_id": f"component-{index // 2}",
            "text": f"synthetic text {index}",
            "labels": [label_value],
            "neutral": bool(label_value),
            "label_cardinality": 1 + label_value,
        }
        for index in range(720)
    ]


class Exp065LabelFreeProjectionTests(unittest.TestCase):
    def test_fixed_ordinals_are_exact_and_strict(self) -> None:
        expected = np.asarray(
            [0, 23, 46, 70, 93, 116, 139, 162, 186, 209, 232, 255, 278, 302,
             325, 348, 371, 394, 417, 441, 464, 487, 510, 533, 557, 580, 603,
             626, 649, 673, 696, 719],
            dtype=np.int16,
        )
        self.assertTrue(np.array_equal(RUNNER.replay_ordinals(), expected))
        self.assertTrue(np.array_equal(VERIFIER.fixed_ordinals(), expected))
        self.assertEqual(RUNNER.replay_ordinals().dtype.str, "<i2")

    def test_dense_groups_follow_first_appearance(self) -> None:
        projected = RUNNER.project_rows(synthetic_rows(0))
        self.assertEqual(len(projected), 720)
        self.assertEqual(projected[0]["opaque_component_group"], 0)
        self.assertEqual(projected[1]["opaque_component_group"], 0)
        self.assertEqual(projected[2]["opaque_component_group"], 1)
        self.assertEqual(projected[-1]["opaque_component_group"], 359)
        self.assertEqual([row["ordinal"] for row in projected], list(range(720)))
        self.assertTrue(all(set(row) == RUNNER.PROJECTION_KEYS for row in projected))

    def test_label_poisoning_does_not_change_projection(self) -> None:
        first = RUNNER.projection_jsonl_bytes(RUNNER.project_rows(synthetic_rows(0)))
        second = RUNNER.projection_jsonl_bytes(RUNNER.project_rows(synthetic_rows(1)))
        self.assertEqual(first, second)
        observed = [json.loads(line) for line in first.decode("utf-8").splitlines()]
        self.assertTrue(all("labels" not in row and "sample_id" not in row for row in observed))

    def test_selected_epoch_uses_one_based_minus_one(self) -> None:
        stack = np.zeros((2, 720, 6), dtype=np.float32)
        stack[0] = np.float32(0.25)
        stack[1] = np.float32(0.75)
        ordinals = RUNNER.replay_ordinals()
        selected = RUNNER.selected_probabilities(stack, 2, ordinals)
        expected = VERIFIER.selected_slice(stack, 2, ordinals)
        self.assertTrue(np.array_equal(selected, expected))
        self.assertTrue(np.all(selected == np.float32(0.75)))
        with self.assertRaises(ValueError):
            RUNNER.selected_probabilities(stack, 0, ordinals)
        with self.assertRaises(ValueError):
            VERIFIER.selected_slice(stack, 3, ordinals)

    def test_selected_probability_range_is_enforced(self) -> None:
        stack = np.zeros((1, 720, 6), dtype=np.float32)
        stack[0, 0, 0] = np.float32(1.1)
        with self.assertRaises(ValueError):
            RUNNER.selected_probabilities(stack, 1, RUNNER.replay_ordinals())

    def test_replay_npz_exact_schema_and_no_extra_arrays(self) -> None:
        arrays = {
            "ordinal": RUNNER.replay_ordinals(),
            "m1_probabilities": np.zeros((32, 6), dtype="<f4"),
            "m3_probabilities": np.ones((32, 6), dtype="<f4"),
        }
        payload = RUNNER.replay_npz_bytes(arrays)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "replay.npz"
            path.write_bytes(payload)
            self.assertEqual(RUNNER.npz_schema(path), RUNNER.REPLAY_SCHEMA)
            with np.load(BytesIO(payload), allow_pickle=False) as archive:
                self.assertEqual(set(archive.files), set(RUNNER.REPLAY_SCHEMA))

    def test_projection_jsonl_is_canonical_utf8_with_terminal_lf(self) -> None:
        payload = RUNNER.projection_jsonl_bytes(RUNNER.project_rows(synthetic_rows(0)))
        self.assertTrue(payload.endswith(b"\n"))
        self.assertEqual(len(payload.decode("utf-8").splitlines()), 720)
        first = payload.decode("utf-8").splitlines()[0]
        self.assertEqual(first, '{"opaque_component_group":0,"ordinal":0,"text":"synthetic text 0"}')

    def test_create_once_refuses_overwrite_and_sets_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "projection.jsonl"
            RUNNER._create(path, b"first\n", 0o600)
            with self.assertRaises(FileExistsError):
                RUNNER._create(path, b"second\n", 0o600)
            self.assertEqual(path.read_bytes(), b"first\n")
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_public_privacy_scanner(self) -> None:
        self.assertEqual(RUNNER.public_sensitive_paths({"status": "ok"}), [])
        self.assertTrue(RUNNER.public_sensitive_paths({"text": "forbidden"}))
        self.assertTrue(VERIFIER.public_sensitive_paths({"ordinal": 1}))

    def test_runner_and_verifier_do_not_index_forbidden_values(self) -> None:
        forbidden = {"labels", "neutral", "label_cardinality", "gold", "fixed_predictions", "shared_threshold_predictions"}
        for path in (RUNNER_PATH, VERIFIER_PATH):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            indexed: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                    indexed.add(node.slice.value)
            self.assertFalse(indexed & forbidden, f"{path.name}: {indexed & forbidden}")

    def test_verifier_is_independent(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import run_exp065", source)
        self.assertNotIn("from run_exp065", source)

    def test_frozen_config_and_source_headers(self) -> None:
        config, sources = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        self.assertEqual(config["experiment_id"], "EXP-065")
        self.assertEqual(config["replay"]["m1_selected_epoch"], 4)
        self.assertEqual(config["replay"]["m3_selected_epoch"], 2)
        self.assertEqual(RUNNER.npz_schema(sources["m1_probabilities"]), RUNNER.M1_SCHEMA)
        self.assertEqual(RUNNER.npz_schema(sources["m3_probabilities"]), RUNNER.M3_SCHEMA)


if __name__ == "__main__":
    unittest.main()
