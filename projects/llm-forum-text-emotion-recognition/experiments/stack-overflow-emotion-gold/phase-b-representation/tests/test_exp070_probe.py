from __future__ import annotations

import ast
from contextlib import contextmanager
import importlib.util
import inspect
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp070_probe.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp070_probe.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load("exp070_probe_runner_tests", RUNNER_PATH)
VERIFIER = load("exp070_probe_verifier_tests", VERIFIER_PATH)


class Exp070ProbeTests(unittest.TestCase):
    def test_frozen_inventory_reuses_base_and_counts_all_fits(self) -> None:
        self.assertEqual(len(RUNNER.MAIN_KEYS), 24)
        self.assertEqual(len(RUNNER.SHUFFLE_KEYS), 24)
        self.assertEqual(
            [key for key in RUNNER.MAIN_KEYS if key.startswith("frozen:")],
            [f"frozen:{point}" for point in RUNNER.ALL_POINTS],
        )
        self.assertEqual(
            [key for key in RUNNER.MAIN_KEYS if key.startswith("m3-s43:")],
            [f"m3-s43:{point}" for point in RUNNER.CONFIRMATION_POINTS],
        )
        self.assertEqual(
            [key for key in RUNNER.MAIN_KEYS if key.startswith("m3-s44:")],
            [f"m3-s44:{point}" for point in RUNNER.CONFIRMATION_POINTS],
        )
        self.assertEqual(RUNNER.MAIN_FITS_PER_FOLD, 720)
        self.assertEqual(RUNNER.SHUFFLE_FITS_PER_FOLD, 144)
        self.assertEqual(RUNNER.TOTAL_MAIN_FITS, 3600)
        self.assertEqual(RUNNER.TOTAL_SHUFFLE_FITS, 720)
        self.assertEqual(RUNNER.TOTAL_BINARY_FITS, 4320)

    def test_outer_fold_worker_mapping_and_point_axes_are_frozen(self) -> None:
        for seed in (42, 43, 44):
            for outer_fold in RUNNER.FOLDS:
                worker = f"m3-s{seed}-f{outer_fold}"
                self.assertEqual(worker, f"m3-s{seed}-f{outer_fold}")
                self.assertIn(worker, RUNNER.WORKER_IDS)
        self.assertEqual(RUNNER.CONFIRMATION_POINTS, ("H19", "H27", "HF"))
        self.assertEqual(RUNNER.VOTING_POINTS, ("H27", "HF"))
        self.assertEqual(RUNNER.PRE_LORA_POINTS, ("H-1", "H7", "H15", "H19"))

    def test_condition_mapping_never_substitutes_an_inner_fold_worker(self) -> None:
        for outer_fold in RUNNER.FOLDS:
            self.assertEqual(
                RUNNER._condition_worker_and_point("frozen:HF", outer_fold),
                ("base", "HF"),
            )
            for seed in (42, 43, 44):
                self.assertEqual(
                    RUNNER._condition_worker_and_point(f"m3-s{seed}:HF", outer_fold),
                    (f"m3-s{seed}-f{outer_fold}", "HF"),
                )
        with self.assertRaisesRegex(ValueError, "condition-point drift"):
            RUNNER._condition_worker_and_point("m3-s44:H20", 0)

    def test_nested_split_has_exact_sizes_and_one_inner_oof_prediction_per_row(self) -> None:
        fold_ids = np.repeat(np.arange(5, dtype=np.int8), 672)
        outer_fold = 2
        outer_train_ordinals = np.flatnonzero(fold_ids != outer_fold).astype(np.int32)
        outer_labels = np.tile(
            np.asarray([[0, 1, 0, 1, 0, 1], [1, 0, 1, 0, 1, 0]], dtype=np.uint8),
            (1344, 1),
        )
        representation = np.zeros((3360, 2560), dtype=np.float64)
        representation[:, 0] = np.arange(3360, dtype=np.float64)
        calls: list[tuple[int, int]] = []

        def fake_fit(train_x, train_y, predict_x):
            self.assertEqual(train_y.shape, (train_x.shape[0], 6))
            self.assertTrue(np.all(np.isin(train_y, (0, 1))))
            calls.append((train_x.shape[0], predict_x.shape[0]))
            probabilities = np.repeat((predict_x[:, :1] / 3360.0), 6, axis=1)
            return probabilities, np.ones(6, dtype=np.int32)

        with (
            patch.object(RUNNER, "_fit_six_binary", side_effect=fake_fit),
            patch.object(RUNNER, "select_threshold_index", return_value=50) as selector,
        ):
            inner, heldout, threshold, iterations, fits = RUNNER._fit_main_condition(
                representation,
                fold_ids,
                outer_fold,
                outer_train_ordinals,
                outer_labels,
            )
        self.assertEqual(calls, [(2016, 672)] * 4 + [(2688, 672)])
        self.assertEqual(selector.call_args.args[0].shape, (2688, 6))
        self.assertEqual(selector.call_args.args[1].shape, (2688, 6))
        np.testing.assert_allclose(inner[:, 0], outer_train_ordinals / 3360.0)
        np.testing.assert_allclose(
            heldout[:, 0], np.flatnonzero(fold_ids == outer_fold) / 3360.0
        )
        self.assertEqual(threshold, 50)
        np.testing.assert_array_equal(iterations, np.ones((5, 6), dtype=np.int32))
        self.assertEqual(fits, 30)

    def test_outer_train_loader_leaves_heldout_label_lines_opaque(self) -> None:
        public_rows = []
        private_lines = []
        for ordinal in range(3360):
            fold = ordinal // 672
            public = {
                "schema_version": "exp-058-fold-row-v1",
                "protocol_id": "DATA-SO-TASK-V1",
                "experiment_id": "EXP-058",
                "sample_id": f"sample-{ordinal}",
                "component_id": f"component-{ordinal}",
                "fold_id": fold,
            }
            public_rows.append(public)
            if fold == 0:
                private_lines.append(b"THIS HELDOUT LINE IS DELIBERATELY NOT JSON\n")
            else:
                value = {
                    **public,
                    "labels": [ordinal % 2] * 6,
                    "neutral": ordinal % 2 == 0,
                    "label_cardinality": 0 if ordinal % 2 == 0 else 6,
                }
                private_lines.append(RUNNER.canonical_json_bytes(value))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fold-manifest.private.jsonl"
            path.write_bytes(b"".join(private_lines))
            with patch.object(RUNNER, "require_record", return_value=path):
                ordinals, labels = RUNNER.load_outer_train_labels(0, public_rows)
        self.assertEqual(ordinals.shape, (2688,))
        self.assertEqual(labels.shape, (2688, 6))
        self.assertTrue(np.all(ordinals >= 672))

    def test_method_contract_rejects_any_drift(self) -> None:
        exact = {
            "method": {
                "labels": list(RUNNER.LABELS),
                "threshold": {"integer_indices": list(RUNNER.THRESHOLD_INDICES)},
            }
        }
        expected_digest = RUNNER.config_method_sha256(exact)
        with patch.object(RUNNER, "EXPECTED_CONFIG_METHOD_NORMALIZED_SHA256", expected_digest):
            RUNNER.validate_method_contract(exact)
        drifted = {"method": dict(exact["method"])}
        drifted["method"]["threshold"] = dict(exact["method"]["threshold"])
        drifted["method"]["threshold"]["prediction_rule"] = "probability_gt_threshold"
        with (
            patch.object(RUNNER, "EXPECTED_CONFIG_METHOD_NORMALIZED_SHA256", expected_digest),
            self.assertRaisesRegex(ValueError, "method drift"),
        ):
            RUNNER.validate_method_contract(drifted)

    def test_threshold_integer_grid_and_adversarial_tie_order(self) -> None:
        self.assertEqual(RUNNER.THRESHOLD_INDICES, tuple(range(5, 96)))

        def choose(values: dict[int, tuple[float, float]]) -> int:
            def objective(_labels, _probabilities, index):
                return values.get(index, (-1.0, 1.0))

            with patch.object(RUNNER, "threshold_objectives", side_effect=objective):
                return RUNNER.select_threshold_index(None, None)

        self.assertEqual(choose({10: (0.8, 0.4), 90: (0.7, 0.1)}), 10)
        self.assertEqual(choose({10: (0.8, 0.4), 90: (0.8, 0.1)}), 90)
        self.assertEqual(choose({10: (0.8, 0.1), 48: (0.8, 0.1)}), 48)
        self.assertEqual(choose({48: (0.8, 0.1), 52: (0.8, 0.1)}), 48)

        labels = np.tile(
            np.asarray([[1, 1, 1, 1, 1, 1], [0, 0, 0, 0, 0, 0]], dtype=np.uint8),
            (2, 1),
        )
        probabilities = np.tile(
            np.asarray([[0.50] * 6, [0.49] * 6], dtype=np.float64),
            (2, 1),
        )
        five_f1, hamming = RUNNER.threshold_objectives(labels, probabilities, 50)
        self.assertEqual(five_f1, 1.0)
        self.assertEqual(hamming, 0.0)

    @staticmethod
    def synthetic_probe_inputs() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        rng = np.random.default_rng(20260828)
        train_x = rng.normal(size=(12, 2560)).astype(np.float64)
        predict_x = rng.normal(size=(3, 2560)).astype(np.float64)
        labels = np.tile(
            np.asarray([[0, 1, 0, 1, 0, 1], [1, 0, 1, 0, 1, 0]], dtype=np.uint8),
            (6, 1),
        )
        return train_x, labels, predict_x

    def test_probe_uses_positive_class_column_and_rejects_class_identity_drift(self) -> None:
        train_x, labels, predict_x = self.synthetic_probe_inputs()

        class FakeModel:
            def __init__(self, **_kwargs):
                self.classes_ = np.asarray([0, 1])
                self.n_iter_ = np.asarray([7], dtype=np.int32)
                self.coef_ = np.zeros((1, 2560), dtype=np.float64)
                self.intercept_ = np.zeros(1, dtype=np.float64)

            def fit(self, _x, _y):
                return self

            def predict_proba(self, x):
                return np.column_stack(
                    [np.full(x.shape[0], 0.75), np.full(x.shape[0], 0.25)]
                )

        with patch("sklearn.linear_model.LogisticRegression", FakeModel):
            probabilities, iterations = RUNNER._fit_six_binary(train_x, labels, predict_x)
        np.testing.assert_array_equal(probabilities, np.full((3, 6), 0.25))
        np.testing.assert_array_equal(iterations, np.full(6, 7, dtype=np.int32))

        class ReversedFakeModel(FakeModel):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.classes_ = np.asarray([1, 0])

        with (
            patch("sklearn.linear_model.LogisticRegression", ReversedFakeModel),
            self.assertRaisesRegex(ValueError, "positive-class identity drift"),
        ):
            RUNNER._fit_six_binary(train_x, labels, predict_x)

    def test_probe_stops_on_convergence_single_class_and_nonfinite_inputs(self) -> None:
        from sklearn.exceptions import ConvergenceWarning
        import warnings

        train_x, labels, predict_x = self.synthetic_probe_inputs()

        class WarningModel:
            def __init__(self, **_kwargs):
                self.classes_ = np.asarray([0, 1])
                self.n_iter_ = np.asarray([1], dtype=np.int32)
                self.coef_ = np.zeros((1, 2560), dtype=np.float64)
                self.intercept_ = np.zeros(1, dtype=np.float64)

            def fit(self, _x, _y):
                warnings.warn("synthetic convergence", ConvergenceWarning)
                return self

        with (
            patch("sklearn.linear_model.LogisticRegression", WarningModel),
            self.assertRaises(ConvergenceWarning),
        ):
            RUNNER._fit_six_binary(train_x, labels, predict_x)

        single_class = labels.copy()
        single_class[:, 4] = 0
        with self.assertRaisesRegex(ValueError, "single-class fit partition"):
            RUNNER._fit_six_binary(train_x, single_class, predict_x)

        nonfinite = train_x.copy()
        nonfinite[0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "fit input drift"):
            RUNNER._fit_six_binary(nonfinite, labels, predict_x)

    def test_shuffle_is_complete_row_deterministic_shared_and_digest_bound(self) -> None:
        seed = RUNNER.SHUFFLE_SEEDS[1]
        outer_fold = 3
        first = RUNNER.build_shuffle_permutation(2688, seed, outer_fold)
        second = RUNNER.build_shuffle_permutation(2688, seed, outer_fold)
        expected_rng = np.random.Generator(
            np.random.PCG64(np.random.SeedSequence([seed, outer_fold]))
        )
        expected = np.asarray(expected_rng.permutation(2688), dtype=np.int64)
        np.testing.assert_array_equal(first, second)
        np.testing.assert_array_equal(first, expected)
        digest = RUNNER.bytes_sha256(np.ascontiguousarray(first).tobytes(order="C"))
        self.assertEqual(
            digest,
            RUNNER.bytes_sha256(np.ascontiguousarray(second).tobytes(order="C")),
        )

        labels = np.arange(2688 * 6, dtype=np.int64).reshape(2688, 6)
        shuffled_a = labels[first]
        shuffled_b = labels[first]
        np.testing.assert_array_equal(shuffled_a, shuffled_b)
        self.assertEqual(
            sorted(map(tuple, shuffled_a.tolist())), sorted(map(tuple, labels.tolist()))
        )
        with self.assertRaisesRegex(ValueError, "shuffle request drift"):
            RUNNER.build_shuffle_permutation(2687, seed, outer_fold)

    def test_bootstrap_traversal_digest_and_component_multiplicity_are_deterministic(self) -> None:
        fold_ids: list[int] = []
        component_ids: list[str] = []
        labels: list[list[int]] = []
        for fold in RUNNER.FOLDS:
            for suffix in ("a", "b"):
                component_ids.extend([f"f{fold}-{suffix}", f"f{fold}-{suffix}"])
                fold_ids.extend([fold, fold])
                labels.extend([[0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1]])
        fold_array = np.asarray(fold_ids, dtype=np.int8)
        truth = np.asarray(labels, dtype=np.uint8)
        first_plan, first_digest = RUNNER.build_bootstrap_plan(
            fold_array, component_ids, truth, replicates=5
        )
        second_plan, second_digest = RUNNER.build_bootstrap_plan(
            fold_array, component_ids, truth, replicates=5
        )
        self.assertEqual(first_digest, second_digest)
        self.assertEqual(len(first_digest), 64)
        self.assertEqual(len(first_plan), 5)
        for left, right in zip(first_plan, second_plan, strict=True):
            np.testing.assert_array_equal(left, right)
            self.assertEqual(left.dtype, np.int32)
            self.assertEqual(left.shape, (20,))
            for fold in RUNNER.FOLDS:
                block = left[fold * 4 : (fold + 1) * 4]
                for pair in (block[:2], block[2:]):
                    self.assertEqual(component_ids[int(pair[0])], component_ids[int(pair[1])])
                    self.assertLess(int(pair[0]), int(pair[1]))
        self.assertTrue(
            any(
                any(
                    np.array_equal(rows[fold * 4 : fold * 4 + 2], rows[fold * 4 + 2 : fold * 4 + 4])
                    for fold in RUNNER.FOLDS
                )
                for rows in first_plan
            )
        )

    def test_bootstrap_stops_on_component_leakage_or_invalid_replicate(self) -> None:
        fold_ids = np.repeat(np.arange(5, dtype=np.int8), 2)
        labels = np.tile(
            np.asarray([[0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1]], dtype=np.uint8),
            (5, 1),
        )
        leaking_components = ["shared", "c-1", "shared"] + [
            f"c-{index}" for index in range(3, 10)
        ]
        with self.assertRaisesRegex(ValueError, "component leakage"):
            RUNNER.build_bootstrap_plan(
                fold_ids, leaking_components, labels, replicates=1
            )

        components = [f"c-{index}" for index in range(10)]
        invalid = labels.copy()
        invalid[:, 5] = 0
        with self.assertRaisesRegex(ValueError, "invalid bootstrap replicate"):
            RUNNER.build_bootstrap_plan(fold_ids, components, invalid, replicates=1)

    def test_percentile_interval_matches_numpy_linear_reference(self) -> None:
        labels = np.zeros((6, 6), dtype=np.uint8)
        left = np.arange(36, dtype=np.float64).reshape(6, 6) / 36.0
        right = np.flip(left, axis=0).copy()
        plan = [
            np.asarray([0, 1, 2], dtype=np.int32),
            np.asarray([1, 2, 3], dtype=np.int32),
            np.asarray([2, 3, 4], dtype=np.int32),
            np.asarray([3, 4, 5], dtype=np.int32),
        ]

        def fake_ap(_labels, probabilities):
            return {"five_label_macro_ap": float(np.mean(probabilities))}

        values = [float(np.mean(left[rows]) - np.mean(right[rows])) for rows in plan]
        expected = [
            float(np.percentile(values, 2.5, method="linear")),
            float(np.percentile(values, 97.5, method="linear")),
        ]
        with patch.object(RUNNER, "ap_bundle", side_effect=fake_ap):
            observed = RUNNER.bootstrap_ap5_delta_interval(labels, left, right, plan)
        np.testing.assert_array_equal(observed, expected)

    def test_metric_api_is_exact_and_fail_closed(self) -> None:
        labels = np.asarray(
            [
                [0, 1, 0, 1, 0, 1],
                [1, 0, 1, 0, 1, 0],
                [0, 1, 1, 0, 0, 1],
                [1, 0, 0, 1, 1, 0],
            ],
            dtype=np.uint8,
        )
        probabilities = labels.astype(np.float64) * 0.8 + (1 - labels) * 0.2
        metrics = RUNNER.metric_bundle(labels, probabilities, labels.copy())
        self.assertEqual(
            set(metrics),
            {
                "five_label_macro_ap",
                "six_label_macro_ap",
                "six_label_macro_f1",
                "five_label_macro_f1",
                "micro_ap",
                "micro_f1",
                "hamming_loss",
                "subset_accuracy",
                "per_label_ap",
                "per_label_f1",
            },
        )
        for key in (
            "five_label_macro_ap",
            "six_label_macro_ap",
            "six_label_macro_f1",
            "five_label_macro_f1",
            "micro_ap",
            "micro_f1",
            "subset_accuracy",
        ):
            self.assertEqual(metrics[key], 1.0)
        self.assertEqual(metrics["hamming_loss"], 0.0)
        self.assertEqual(set(metrics["per_label_ap"]), set(RUNNER.LABELS))
        self.assertEqual(set(metrics["per_label_f1"]), set(RUNNER.LABELS))

        nonfinite = probabilities.copy()
        nonfinite[0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "metric probability drift"):
            RUNNER.metric_bundle(labels, nonfinite, labels)
        with self.assertRaisesRegex(ValueError, "metric input shape drift"):
            RUNNER.metric_bundle(labels[:, :5], probabilities[:, :5], labels[:, :5])

    def test_h19_is_descriptive_and_not_a_terminal_probability_gate(self) -> None:
        self.assertNotIn("_pre_lora_probability_gate", RUNNER.__dict__)
        contrasts = {
            f"m3-s43:{point}": {
                "delta": {"five_label_macro_ap": 0.01},
                "bootstrap_delta_intervals": {
                    "five_label_macro_ap": [0.001, 0.02]
                },
            }
            for point in RUNNER.VOTING_POINTS
        }
        passed, detail = RUNNER._seed_pass(contrasts, 43)
        self.assertTrue(passed)
        self.assertEqual(set(detail), set(RUNNER.VOTING_POINTS))

    def test_initialize_records_resources_and_seals_both_roots(self) -> None:
        config = {
            "run_id": "synthetic-formal",
            "attempt_id": "attempt-1",
            "claim_boundary": "synthetic only",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.json"
            config_path.write_text("{}\n", encoding="utf-8")
            static_completion = root / "static-complete.json"
            static_completion.write_text("{}\n", encoding="utf-8")
            public = root / "public"
            private = root / "private"
            snapshot = {"sha256": "source", "inventory": {}}
            def fake_artifact(path, logical_name=None):
                return {
                    **({"logical_name": logical_name} if logical_name else {"path": Path(path).name}),
                    "bytes": Path(path).stat().st_size,
                    "mode": "0600" if logical_name else "0644",
                    "sha256": "1" * 64,
                }
            with (
                patch.object(RUNNER, "load_config", return_value=config),
                patch.object(RUNNER, "require_implementation_records"),
                patch.object(RUNNER, "_authorization"),
                patch.object(RUNNER, "_access_contract"),
                patch.object(RUNNER, "_formal_static_completion", return_value=static_completion),
                patch.object(RUNNER, "require_environment", return_value={"runtime": "ok"}),
                patch.object(RUNNER, "_free_disk_gate", return_value=999),
                patch.object(
                    RUNNER,
                    "require_frozen_sources",
                    return_value={"source_snapshot_sha256": "source"},
                ),
                patch.object(RUNNER, "source_identity_snapshot", side_effect=[snapshot, snapshot]),
                patch.object(RUNNER, "public_root", return_value=public),
                patch.object(RUNNER, "private_root", return_value=private),
                patch.object(RUNNER, "artifact", side_effect=fake_artifact),
                patch.object(
                    RUNNER,
                    "_config_record",
                    return_value={"path": "synthetic/config.json", "bytes": 3, "mode": "0644", "sha256": "0" * 64},
                ),
                patch.object(RUNNER, "config_method_sha256", return_value="method"),
                patch.object(
                    RUNNER,
                    "_assert_resource_use",
                    return_value={"elapsed_seconds": 0.1, "peak_rss_bytes": 1024},
                ),
            ):
                claim = RUNNER.initialize_stage(config_path)
            self.assertEqual(claim["status"], "Initialized")
            private_manifest = RUNNER.strict_json(private / "input-manifest.json")
            self.assertEqual(
                private_manifest["resources"],
                {"elapsed_seconds": 0.1, "peak_rss_bytes": 1024, "free_disk_bytes": 999},
            )
            self.assertTrue((public / "run-claim.json").is_file())

    def test_lock_contention_is_a_no_state_refusal(self) -> None:
        @contextmanager
        def busy_lock():
            raise RUNNER.ProbeLockBusy("busy")
            yield

        with (
            patch.object(RUNNER, "exclusive_probe_lock", busy_lock),
            patch.object(RUNNER, "_write_terminal_failure") as failure,
        ):
            status = RUNNER.main(["--stage", "initialize"])
        self.assertEqual(status, 2)
        failure.assert_not_called()

    def test_formal_static_chain_rejects_forged_or_unfrozen_parent(self) -> None:
        with self.assertRaisesRegex(ValueError, "formal static binding drift"):
            RUNNER._formal_static_completion(
                {"preflight": {"no_result_completion": {"status": "Complete"}}}
            )
        placeholder = {
            "config": {"bytes": 0, "sha256": "TBD"},
            "static_run": {"bytes": 1, "sha256": "a" * 64},
            "static_verification": {"bytes": 1, "sha256": "b" * 64},
            "no_result_completion": {"bytes": 1, "sha256": "c" * 64},
            "required_statuses": {
                "static_run": "CompletedAwaitingVerification",
                "static_verification": "Passed",
                "no_result_completion": "Complete",
            },
            "formal_probe_authorized_by_preflight": True,
        }
        with self.assertRaisesRegex(ValueError, "identity is not frozen"):
            RUNNER._formal_static_completion({"preflight": placeholder})

    def test_independent_verifier_helpers_match_runner_on_synthetic_values(self) -> None:
        labels = np.asarray(
            [[0, 1, 0, 1, 0, 1], [1, 0, 1, 0, 1, 0]] * 4,
            dtype=np.uint8,
        )
        probabilities = labels.astype(np.float64) * 0.7 + 0.15
        self.assertEqual(
            RUNNER.select_threshold_index(labels, probabilities),
            VERIFIER.select_threshold_index(labels, probabilities),
        )
        self.assertEqual(
            RUNNER.metric_bundle(labels, probabilities, labels),
            VERIFIER.metric_bundle(labels, probabilities, labels),
        )
        np.testing.assert_array_equal(
            RUNNER.build_shuffle_permutation(2688, RUNNER.SHUFFLE_SEEDS[0], 2),
            VERIFIER.shuffle_permutation(2, VERIFIER.SHUFFLE_SEEDS[0]),
        )

    def test_verifier_source_is_independent_and_public_privacy_fails_closed(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertNotIn("run_exp070_probe", imports)
        self.assertNotIn(".fit(", source)
        self.assertTrue(VERIFIER._public_sensitive({"labels": [0, 1]}))
        self.assertTrue(VERIFIER._public_sensitive({"payload": list(range(672))}))
        self.assertFalse(VERIFIER._public_sensitive({"interval": [0.1, 0.2]}))

    def test_verifier_static_payloads_bind_synthetic_test_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.json"
            run_path = root / "static.json"
            input_path = root / "input.json"
            verification_path = root / "verification.json"
            for path in (config_path, run_path, input_path):
                path.write_text("{}\n", encoding="utf-8")
            fake_artifact = lambda path, logical_name=None: {
                **({"logical_name": logical_name} if logical_name else {"path": path.name}),
                "bytes": path.stat().st_size,
                "mode": "0644",
                "sha256": "d" * 64,
            }
            config = {"run_id": "static", "attempt_id": "a1", "claim_boundary": "synthetic"}
            tests = {
                "test_artifact": {"path": "tests.py", "bytes": 1, "mode": "0644", "sha256": "e" * 64},
                "tests_run": 34,
                "status": "Passed",
                "command_sha256": "f" * 64,
            }
            with patch.object(VERIFIER, "artifact", side_effect=fake_artifact):
                verification = VERIFIER._static_verification(
                    config_path,
                    config,
                    run_path,
                    input_path,
                    {"sha256": "s" * 64},
                    tests,
                )
                verification_path.write_bytes(VERIFIER.canonical_json_bytes(verification))
                completion = VERIFIER._static_completion(
                    config,
                    run_path,
                    input_path,
                    verification_path,
                    tests,
                )
            self.assertEqual(verification["synthetic_tests"], tests)
            self.assertEqual(completion["synthetic_tests"], tests)
            self.assertTrue(completion["formal_probe_authorized"])

    def test_stage_authorization_and_access_are_fail_closed(self) -> None:
        formal_keys = (
            "initialize",
            "fit_folds",
            "assemble",
            "representation_values",
            "label_source_rows",
            "label_values",
            "outer_train_label_use",
            "outer_heldout_label_use_after_fold_seals",
            "probe_fitting",
            "threshold_selection",
            "label_shuffle",
            "bootstrap",
            "performance_metrics",
            "final_verification",
            "formal_completion",
        )
        static_authorization = {key: False for key in formal_keys}
        static_authorization.update(
            {
                "static_preflight": True,
                "model_loading": False,
                "forward": False,
                "source_mutation": False,
                "validation": False,
                "test": False,
                "exp071": False,
            }
        )
        RUNNER._authorization({"authorization": static_authorization}, formal=False)
        overauthorized = dict(static_authorization)
        overauthorized["probe_fitting"] = True
        with self.assertRaisesRegex(PermissionError, "over-authorizes"):
            RUNNER._authorization({"authorization": overauthorized}, formal=False)

        formal_authorization = dict(static_authorization)
        formal_authorization.update({key: True for key in formal_keys})
        formal_authorization["static_preflight"] = False
        RUNNER._authorization({"authorization": formal_authorization}, formal=True)
        formal_authorization["model_loading"] = True
        with self.assertRaisesRegex(PermissionError, "forbidden authorization"):
            RUNNER._authorization({"authorization": formal_authorization}, formal=True)

        static_access = {
            key: False
            for key in (
                "train_jsonl_accessed",
                "train_text_read",
                "model_loaded",
                "forward_executed",
                "validation_accessed",
                "test_accessed",
                "representation_array_values_read",
                "label_source_rows_parsed",
                "label_values_read",
                "real_probe_fitted",
                "threshold_selected",
                "shuffle_executed",
                "bootstrap_executed",
                "performance_metrics_computed",
            )
        }
        RUNNER._access_contract({"access": static_access}, formal=False)
        static_access["validation_accessed"] = True
        with self.assertRaisesRegex(PermissionError, "Forbidden"):
            RUNNER._access_contract({"access": static_access}, formal=False)

    def test_npy_header_reader_reads_only_synthetic_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "representations.npy"
            np.save(path, np.zeros((7, 3, 11), dtype=np.float32), allow_pickle=False)
            self.assertEqual(
                RUNNER.read_npy_header(path),
                {"dtype": "<f4", "fortran_order": False, "shape": [7, 3, 11]},
            )
            payload = bytearray(path.read_bytes())
            payload[:6] = b"BROKEN"
            broken = Path(directory) / "broken.npy"
            broken.write_bytes(payload)
            with self.assertRaisesRegex(ValueError, "Invalid NPY magic"):
                RUNNER.read_npy_header(broken)

    def test_json_writer_is_no_clobber_and_enforces_modes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / "public.json"
            private = root / "private.json"
            with patch.object(RUNNER, "PROJECT_ROOT", root):
                RUNNER.create_json_once(public, {"status": "first"}, private=False)
                RUNNER.create_json_once(private, {"status": "first"}, private=True)
            self.assertEqual(os.stat(public).st_mode & 0o777, 0o644)
            self.assertEqual(os.stat(private).st_mode & 0o777, 0o600)
            before = public.read_bytes()
            with (
                patch.object(RUNNER, "PROJECT_ROOT", root),
                self.assertRaises(FileExistsError),
            ):
                RUNNER.create_json_once(public, {"status": "second"}, private=False)
            self.assertEqual(public.read_bytes(), before)

    def test_npz_writer_is_private_atomic_and_no_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fold.npz"
            RUNNER._write_npz_once(path, {"value": np.arange(4, dtype=np.int32)})
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertFalse(path.with_name("fold.npz.part").exists())
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                RUNNER._write_npz_once(path, {"value": np.arange(5, dtype=np.int32)})
            self.assertEqual(path.read_bytes(), before)

    def test_fold_bundle_schema_uses_one_integer_threshold_index_per_condition(self) -> None:
        arrays = {
            "outer_train_ordinals": np.arange(2688, dtype=np.int32),
            "outer_heldout_ordinals": np.arange(2688, 3360, dtype=np.int32),
            "main_inner_oof_probability": np.zeros((24, 2688, 6), dtype=np.float64),
            "main_outer_heldout_probability": np.zeros((24, 672, 6), dtype=np.float64),
            "main_threshold_index": np.full(24, 50, dtype=np.int16),
            "main_n_iter": np.ones((24, 5, 6), dtype=np.int32),
            "shuffle_outer_heldout_probability": np.zeros(
                (3, 8, 672, 6), dtype=np.float64
            ),
            "shuffle_n_iter": np.ones((3, 8, 6), dtype=np.int32),
        }
        self.assertEqual(set(arrays), RUNNER._bundle_expected_arrays())
        self.assertEqual(arrays["main_threshold_index"].shape, (24,))
        self.assertEqual(arrays["main_threshold_index"].dtype, np.int16)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "f0.npz"
            RUNNER._write_npz_once(path, arrays)
            RUNNER.validate_fold_bundle(path, 0)

    def test_directory_contract_rejects_mode_and_symlink_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / "public"
            private = root / "private"
            RUNNER.ensure_new_directory(public, private=False)
            RUNNER.ensure_new_directory(private, private=True)
            self.assertEqual(os.stat(public).st_mode & 0o777, 0o755)
            self.assertEqual(os.stat(private).st_mode & 0o777, 0o700)
            RUNNER.require_safe_directory(public, private=False)
            RUNNER.require_safe_directory(private, private=True)
            os.chmod(private, 0o755)
            with self.assertRaisesRegex(PermissionError, "mode drift"):
                RUNNER.require_safe_directory(private, private=True)
            os.chmod(private, 0o700)
            (private / "link").symlink_to(public)
            with self.assertRaisesRegex(PermissionError, "symlink"):
                RUNNER.require_safe_directory(private, private=True)

    def test_resource_contract_rejects_fit_inventory_drift(self) -> None:
        resources = {
            "maximum_concurrent_probe_workers": 1,
            "maximum_binary_probe_fits": 4320,
            "formal_wall_seconds": 43200,
            "probe_peak_rss_bytes": 8589934592,
            "consumer_private_budget_bytes": 536870912,
            "threads_per_library": 1,
            "api_cost_usd": 0,
        }
        RUNNER._resource_contract({"resources": resources})
        drifted = dict(resources)
        drifted["maximum_binary_probe_fits"] = 4319
        with self.assertRaisesRegex(ValueError, "Resource contract drift"):
            RUNNER._resource_contract({"resources": drifted})

    def test_source_snapshot_detects_synthetic_identity_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.bin"
            path.write_bytes(b"frozen")
            before = RUNNER.artifact(path, logical_name="source.bin")
            path.write_bytes(b"drifted")
            after = RUNNER.artifact(path, logical_name="source.bin")
            self.assertNotEqual(before, after)

    def test_static_stage_refuses_clobber_before_any_source_value_access(self) -> None:
        synthetic_config = {
            "run_id": "synthetic",
            "attempt_id": "attempt-1",
            "claim_boundary": "synthetic only",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / "public"
            private = root / "private"
            public.mkdir()
            with (
                patch.object(RUNNER, "load_config", return_value=synthetic_config),
                patch.object(RUNNER, "_authorization"),
                patch.object(RUNNER, "_access_contract"),
                patch.object(RUNNER, "require_environment", return_value={}),
                patch.object(RUNNER, "_free_disk_gate", return_value=1),
                patch.object(RUNNER, "public_root", return_value=public),
                patch.object(RUNNER, "private_root", return_value=private),
                patch.object(RUNNER, "source_identity_snapshot") as snapshot,
                patch.object(RUNNER, "require_frozen_sources") as sources,
                self.assertRaisesRegex(FileExistsError, "output root already exists"),
            ):
                RUNNER.static_stage(Path("synthetic.json"))
            snapshot.assert_not_called()
            sources.assert_not_called()

    def test_static_stage_stops_on_source_drift_without_creating_outputs(self) -> None:
        synthetic_config = {
            "run_id": "synthetic",
            "attempt_id": "attempt-1",
            "claim_boundary": "synthetic only",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / "public"
            private = root / "private"
            with (
                patch.object(RUNNER, "load_config", return_value=synthetic_config),
                patch.object(RUNNER, "_authorization"),
                patch.object(RUNNER, "_access_contract"),
                patch.object(RUNNER, "require_environment", return_value={}),
                patch.object(RUNNER, "_free_disk_gate", return_value=1),
                patch.object(RUNNER, "public_root", return_value=public),
                patch.object(RUNNER, "private_root", return_value=private),
                patch.object(
                    RUNNER,
                    "source_identity_snapshot",
                    side_effect=[{"sha256": "before"}, {"sha256": "after"}],
                ),
                patch.object(RUNNER, "require_frozen_sources", return_value={}),
                self.assertRaisesRegex(ValueError, "snapshot changed"),
            ):
                RUNNER.static_stage(Path("synthetic.json"))
            self.assertFalse(public.exists())
            self.assertFalse(private.exists())

    def test_fold_prefix_accepts_only_an_exact_sealed_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / "public"
            private = root / "private"
            RUNNER.ensure_new_directory(public, private=False)
            RUNNER.ensure_new_directory(private, private=True)
            (public / "run-claim.json").write_text("{}\n", encoding="utf-8")
            (private / "input-manifest.json").write_text("{}\n", encoding="utf-8")
            os.chmod(private / "input-manifest.json", 0o600)
            folds = private / "folds"
            folds.mkdir(mode=0o700)
            os.chmod(folds, 0o700)
            with (
                patch.object(RUNNER, "public_root", return_value=public),
                patch.object(RUNNER, "private_root", return_value=private),
            ):
                self.assertEqual(RUNNER.validate_fold_prefix({}, 0), [])
                (folds / "f1.npz.part").write_bytes(b"orphan")
                with self.assertRaisesRegex(ValueError, "prefix/inventory drift"):
                    RUNNER.validate_fold_prefix({}, 0)

    def test_negative_control_failure_overrides_representation_state(self) -> None:
        main_contrasts = {}
        for seed in (43, 44):
            for point in RUNNER.VOTING_POINTS:
                main_contrasts[f"m3-s{seed}:{point}"] = {
                    "delta": {"five_label_macro_ap": 0.02},
                    "bootstrap_delta_intervals": {
                        "five_label_macro_ap": [0.01, 0.03]
                    },
                }
            passed, detail = RUNNER._seed_pass(main_contrasts, seed)
            self.assertTrue(passed)
            self.assertTrue(all(value["passed"] for value in detail.values()))

        control_contrasts = {}
        shuffle_seed = RUNNER.SHUFFLE_SEEDS[0]
        for seed in (43, 44):
            for point in RUNNER.VOTING_POINTS:
                control_contrasts[f"shuffle-{shuffle_seed}|m3-s{seed}:{point}"] = {
                    "delta_five_label_macro_ap": 0.02,
                    "bootstrap_delta_interval": [0.01, 0.03],
                }
            passed, _detail = RUNNER._control_seed_pass(
                control_contrasts, shuffle_seed, seed
            )
            self.assertTrue(passed)
        self.assertIn(
            "representation_state = None if negative_control_failure else passed_seeds",
            inspect.getsource(RUNNER.assemble_stage),
        )

    def test_public_report_ast_exposes_only_aggregate_result_keys(self) -> None:
        tree = ast.parse(inspect.getsource(RUNNER.assemble_stage))

        def assigned_dict_keys(name: str) -> set[str]:
            matches: list[ast.Dict] = []
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                    continue
                target = node.targets[0]
                if isinstance(target, ast.Name) and target.id == name and isinstance(node.value, ast.Dict):
                    matches.append(node.value)
            self.assertEqual(len(matches), 1)
            return {
                key.value
                for key in matches[0].keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }

        aggregate_keys = assigned_dict_keys("aggregate_results")
        report_keys = assigned_dict_keys("report")
        self.assertEqual(
            aggregate_keys,
            {
                "threshold_indices_by_outer_fold",
                "main_metrics",
                "main_contrasts",
                "seed_votes",
                "control_metrics",
                "control_contrasts",
                "control_votes",
                "negative_control_failure",
                "representation_state",
                "representation_state_label",
            },
        )
        self.assertTrue({"results", "counts", "resources", "access"} <= report_keys)
        forbidden = {
            "sample_ids",
            "component_ids",
            "fold_ids",
            "labels",
            "probabilities",
            "predictions",
            "coefficients",
            "scalers",
            "permutations",
            "bootstrap_plan",
        }
        self.assertFalse(forbidden & aggregate_keys)
        self.assertFalse(forbidden & report_keys)


if __name__ == "__main__":
    unittest.main()
