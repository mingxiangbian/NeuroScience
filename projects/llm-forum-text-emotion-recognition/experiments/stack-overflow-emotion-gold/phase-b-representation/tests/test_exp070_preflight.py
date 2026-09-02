from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp070_preflight.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp070_preflight.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load("exp070_preflight_runner_tests", RUNNER_PATH)
VERIFIER = load("exp070_preflight_verifier_tests", VERIFIER_PATH)


class Exp070PreflightTests(unittest.TestCase):
    def test_scope_authorizes_no_result_preflight_only(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        self.assertTrue(config["authorization"]["no_result_preflight"])
        for key in (
            "formal_extraction",
            "model_loading",
            "forward",
            "real_probe_fitting",
            "threshold_selection",
            "bootstrap",
            "performance_metrics",
            "formal_completion",
            "exp071",
        ):
            self.assertFalse(config["authorization"][key])

    def test_parent_and_implementation_records_match(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        RUNNER.require_config_records(config)

    def test_smoke_fixtures_are_not_formal_probe_inputs(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        self.assertFalse(config["representation"]["smoke_rows_usable_for_fitting"])
        self.assertEqual(config["representation"]["rows"], 3360)
        self.assertEqual(config["representation"]["base_matrices"], 1)
        self.assertEqual(config["representation"]["m3_matrices"], 15)
        self.assertEqual(
            config["representation"]["transient_pre_lora_points_for_confirmation_seeds"],
            ["H-1", "H7", "H15"],
        )

    def test_representation_byte_budget_is_exact(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        point_matrices = 9 + 5 * 9 + 10 * 3
        expected = point_matrices * 3360 * 2560 * 4
        self.assertEqual(point_matrices, 84)
        self.assertEqual(expected, 2_890_137_600)
        self.assertEqual(config["representation"]["raw_bytes"], expected)
        self.assertLess(expected, config["resources"]["private_disk_budget_bytes"])

    def test_nested_fold_scope_is_component_preserving(self) -> None:
        folds = set(range(5))
        for outer in folds:
            outer_train = folds - {outer}
            for inner in outer_train:
                fit_folds = outer_train - {inner}
                self.assertEqual(len(fit_folds), 3)
                self.assertNotIn(outer, fit_folds)
                self.assertNotIn(inner, fit_folds)

    def test_threshold_grid_and_tie_order_are_frozen(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        threshold = config["threshold"]
        grid = [round(threshold["grid_start"] + index * threshold["grid_step"], 12) for index in range(91)]
        self.assertEqual(grid[0], 0.05)
        self.assertEqual(grid[-1], 0.95)
        self.assertEqual(len(grid), threshold["grid_count"])
        self.assertEqual(threshold["prediction_rule"], "probability_gte_threshold")
        self.assertEqual(threshold["comparison_tolerance"], 1e-12)
        self.assertEqual(threshold["zero_division"], 0)
        self.assertEqual(
            threshold["selection_order"],
            [
                "highest_five_label_macro_f1",
                "lowest_six_label_hamming_loss_within_1e-12",
                "closest_to_0_5",
                "lower_threshold",
            ],
        )

    def test_shuffle_preserves_complete_label_rows(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        self.assertEqual(
            config["label_shuffle"]["contrast"],
            "3360_row_OOF_five_label_macro_AP_M3_shuffled_r_minus_Frozen_shuffled_r",
        )
        labels = np.asarray(
            [[1, 0, 0, 0, 0, 0], [0, 1, 1, 0, 0, 0], [0, 0, 0, 1, 1, 0], [0, 0, 0, 0, 0, 1]],
            dtype=np.uint8,
        )
        rng = np.random.default_rng(np.random.SeedSequence([2026082711, 2]))
        shuffled = labels[rng.permutation(len(labels))]
        self.assertEqual(sorted(map(tuple, shuffled.tolist())), sorted(map(tuple, labels.tolist())))
        self.assertEqual(shuffled.sum(axis=0).tolist(), labels.sum(axis=0).tolist())
        self.assertEqual(sorted(shuffled.sum(axis=1).tolist()), sorted(labels.sum(axis=1).tolist()))

    def test_component_bootstrap_keeps_group_rows_together(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        self.assertEqual(config["bootstrap"]["validity_labels"], "all_six_positive_and_negative")
        self.assertEqual(config["bootstrap"]["invalid_replicate"], "stop_without_redraw")
        components = {"a": [0, 1], "b": [2], "c": [3, 4, 5]}
        rng = np.random.Generator(np.random.PCG64(2026082701))
        draws = rng.choice(sorted(components), size=len(components), replace=True)
        rows = [row for component in draws for row in components[component]]
        cursor = 0
        for component in draws:
            block = components[component]
            self.assertEqual(rows[cursor : cursor + len(block)], block)
            cursor += len(block)

    def test_synthetic_probe_is_deterministic(self) -> None:
        features = np.asarray(
            [[-2.0, -1.0], [-1.0, -2.0], [1.0, 2.0], [2.0, 1.0], [-1.5, 1.5], [1.5, -1.5]],
            dtype=np.float64,
        )
        labels = np.asarray(
            [
                [0, 0, 0, 0, 1, 1],
                [0, 0, 1, 0, 1, 0],
                [1, 1, 0, 1, 0, 0],
                [1, 1, 1, 1, 0, 1],
                [0, 1, 0, 1, 1, 0],
                [1, 0, 1, 0, 0, 1],
            ],
            dtype=np.uint8,
        )
        scaled = StandardScaler(with_mean=True, with_std=True).fit_transform(features)
        outputs = []
        for column in range(6):
            model = LogisticRegression(
                penalty="l2",
                dual=False,
                C=1.0,
                solver="liblinear",
                class_weight=None,
                fit_intercept=True,
                intercept_scaling=1.0,
                tol=1e-4,
                max_iter=2000,
                random_state=42,
            )
            outputs.append(model.fit(scaled, labels[:, column]).predict_proba(scaled)[:, 1])
        first = np.column_stack(outputs)
        second = np.column_stack(
            [
                LogisticRegression(
                    penalty="l2",
                    dual=False,
                    C=1.0,
                    solver="liblinear",
                    class_weight=None,
                    fit_intercept=True,
                    intercept_scaling=1.0,
                    tol=1e-4,
                    max_iter=2000,
                    random_state=42,
                ).fit(scaled, labels[:, column]).predict_proba(scaled)[:, 1]
                for column in range(6)
            ]
        )
        np.testing.assert_array_equal(first, second)

    def test_npz_header_reader_does_not_load_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.npz"
            np.savez(path, ordinal=np.arange(3, dtype=np.int32), hf=np.zeros((3, 4), dtype=np.float32))
            headers = RUNNER.npz_headers(path)
            self.assertEqual(headers["ordinal"]["dtype"], "<i4")
            self.assertEqual(headers["ordinal"]["shape"], [3])
            self.assertEqual(headers["hf"]["dtype"], "<f4")
            self.assertEqual(headers["hf"]["shape"], [3, 4])

    def test_inventory_rejects_special_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fifo = root / "unexpected.fifo"
            os.mkfifo(fifo)
            with self.assertRaises(PermissionError):
                RUNNER.inventory(root)

    def test_json_writer_is_no_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            RUNNER.create_json_once(path, {"status": "first"})
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                RUNNER.create_json_once(path, {"status": "second"})
            self.assertEqual(path.read_bytes(), before)

    def test_runner_and_verifier_have_no_forbidden_imports(self) -> None:
        for path in (RUNNER_PATH, VERIFIER_PATH):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module.split(".")[0])
            self.assertFalse(RUNNER.FORBIDDEN_MODULES & imports)

    def test_output_namespaces_are_separate(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        outputs = config["outputs"]
        self.assertNotEqual(outputs["public_root"], outputs["formal_public_root"])
        self.assertNotEqual(outputs["private_root"], outputs["formal_private_root"])
        self.assertEqual(
            outputs["public_allowlist"],
            ["static.json", "static-verification.json", "no-result-complete.json"],
        )
        self.assertEqual(outputs["private_allowlist"], ["input-contract-manifest.json"])

    def test_private_ignore_rule_is_frozen(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        gitignore = RUNNER.require_record(config["privacy"]["gitignore"])
        self.assertIn(config["privacy"]["required_rule"], gitignore.read_text().splitlines())


if __name__ == "__main__":
    unittest.main()
