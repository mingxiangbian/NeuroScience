from __future__ import annotations

import ast
import copy
import importlib.util
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp060_router.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp060_router.py"
FORMAL_CONFIG = MODULE_DIR / "configs" / "exp-060-pre-qwen-router.json"

EXPECTED_FEATURE_NAMES = (
    "m1_probability_love",
    "m1_probability_joy",
    "m1_probability_surprise",
    "m1_probability_anger",
    "m1_probability_sadness",
    "m1_probability_fear",
    "m1_mean_binary_entropy",
    "m1_max_binary_entropy",
    "m1_minimum_threshold_margin",
    "m1_predicted_cardinality",
    "m1_highest_probability",
    "m1_lowest_probability",
    "character_length",
    "m1_token_length",
)

EXPECTED_THRESHOLD_SELECTION_ORDER = (
    "highest_six_label_macro_f1",
    "lowest_hamming_loss",
    "closest_to_0_5",
    "lower_threshold",
)

FORBIDDEN_PUBLIC_KEYS = (
    "sample_id",
    "sample_ids",
    "component_id",
    "component_ids",
    "fold_id",
    "fold_ids",
    "gold",
    "logit",
    "logits",
    "probability",
    "probabilities",
    "feature",
    "features",
    "feature_matrix",
    "target",
    "targets",
    "router_targets",
    "route_score",
    "route_scores",
    "route_mask",
    "route_masks",
    "prediction",
    "predictions",
    "raw_text",
    "text",
)


def synthetic_analysis_config() -> dict:
    return {
        "cross_fitting": {"outer_fold_ids": [0, 1, 2, 3, 4]},
        "thresholds": {
            "grid_start": 0.05,
            "grid_end": 0.95,
            "grid_step": 0.01,
            "numeric_tolerance": 1e-12,
        },
        "router": {
            "logistic_regression": {
                "penalty": "l2",
                "C": 1.0,
                "class_weight": "balanced",
                "solver": "liblinear",
                "max_iter": 1000,
                "random_state": 42,
            }
        },
        "call_rates": [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0],
        "gate": {
            "maximum_actual_qwen_call_rate": 0.2,
            "minimum_six_label_macro_f1_gain": 0.01,
            "minimum_five_label_macro_f1_gain": -0.005,
            "maximum_hamming_loss_increase": 1e-12,
            "minimum_one_non_surprise_label_f1_gain": 0.005,
        },
    }


def synthetic_replication_identity_config(experiment_id: str = "EXP-061") -> dict:
    seed = {"EXP-061": 43, "EXP-062": 44}[experiment_id]
    run_id = f"exp-{int(experiment_id[-3:]):03d}-seed-{seed}-router-replication"
    base = "experiments/stack-overflow-emotion-gold/oof-router"
    public_attempt = f"{base}/runs/{run_id}/attempt-1"
    private_attempt = f"{base}/private/{run_id}/attempt-1"

    def record(path: str) -> dict:
        return {"path": path, "bytes": 1, "sha256": "a" * 64}

    return {
        "schema_version": "exp-router-replication-config-v2",
        "experiment_id": experiment_id,
        "rq_id": "RQ-S3",
        "tier": "Major",
        "stage": "pre-qwen-router-replication",
        "run_id": run_id,
        "attempt_id": "attempt-1",
        "seed_contract": {
            "model_seed": seed,
            "python_seed": seed,
            "numpy_seed": seed,
            "torch_seed": seed,
            "m1_batch_seed": seed,
            "m3_head_seed": seed,
            "m3_batch_seed": seed,
            "m3_lora_seed": seed + 100000,
        },
        "authorization": {"model_seed": seed},
        "data": {"upstream_seed": seed},
        "outputs": {
            "public_namespace": f"{base}/runs/{run_id}",
            "public_attempt_dir": public_attempt,
            "private_namespace": f"{base}/private/{run_id}",
            "private_attempt_dir": private_attempt,
            "selection_record": f"{base}/runs/{run_id}/selected-attempt.json",
        },
        "input": {"paired_oof": record(f"{private_attempt}/paired-oof.npz")},
        "prerequisites": {
            "oof_verification": record(f"{public_attempt}/verification.json"),
            "exp059_run": record(f"{public_attempt}/calibration/run.json"),
            "exp059_verification": record(f"{public_attempt}/calibration/verification.json"),
            "exp059_calibration_parameters": record(
                f"{public_attempt}/calibration/calibration-parameters.json"
            ),
        },
    }


def synthetic_analysis_data(rows: int = 100) -> dict[str, np.ndarray]:
    if rows != 100:
        raise ValueError("The nested contract fixture is frozen at 100 rows")
    fold_ids = np.tile(np.asarray([4, 0, 3, 1, 2], dtype=np.int8), 20)
    sample_ids = np.asarray([f"synthetic-row-{index:03d}" for index in range(rows)])
    component_ids = np.empty(rows, dtype="<U32")
    seen_per_fold = {fold: 0 for fold in range(5)}
    for index, fold in enumerate(fold_ids.tolist()):
        occurrence = seen_per_fold[int(fold)]
        component_ids[index] = f"synthetic-component-{fold}-{occurrence // 2:02d}"
        seen_per_fold[int(fold)] += 1

    gold = np.zeros((rows, 6), dtype=np.uint8)
    gold[np.arange(rows), np.arange(rows) % 6] = 1
    m1_prediction = gold.copy()
    m3_prediction = gold.copy()
    for index in range(rows):
        if index % 2:
            m1_prediction[index, (index + 1) % 6] ^= 1
        else:
            m3_prediction[index, (index + 2) % 6] ^= 1
    return {
        "sample_ids": sample_ids,
        "component_ids": component_ids,
        "fold_ids": fold_ids,
        "gold": gold,
        "m1_logits": np.where(m1_prediction == 1, 10.0, -10.0),
        "m3_logits": np.where(m3_prediction == 1, 10.0, -10.0),
        "character_lengths": np.arange(100, 100 + rows, dtype=np.int32),
        "m1_token_lengths": np.arange(20, 20 + rows, dtype=np.int32),
    }


def sentinel_analysis_data() -> dict[str, np.ndarray]:
    """Return the synthetic fixture with a unique, prediction-preserving row sentinel."""
    data = synthetic_analysis_data()
    row_offsets = np.arange(len(data["gold"]), dtype=np.float64)[:, None] * 0.001
    m1_sign = np.where(data["m1_logits"] >= 0.0, 1.0, -1.0)
    m3_sign = np.where(data["m3_logits"] >= 0.0, 1.0, -1.0)
    data["m1_logits"] = m1_sign * (5.0 + row_offsets)
    data["m3_logits"] = m3_sign * (7.0 + row_offsets)
    return data


def row_indices_from_character_lengths(values: np.ndarray) -> tuple[int, ...]:
    indices = np.rint(np.asarray(values, dtype=np.float64) - 100.0).astype(np.int64)
    return tuple(int(value) for value in indices.tolist())


def load_module(name: str, path: Path):
    if not path.is_file():
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_module("exp060_router_under_test", RUNNER_PATH)
verifier = load_module("exp060_verifier_under_test", VERIFIER_PATH)


class Exp060RouterContractTests(unittest.TestCase):
    def test_replication_identity_and_attempt_paths_bind_seed_43_and_44(self) -> None:
        for experiment_id, seed in (("EXP-061", 43), ("EXP-062", 44)):
            with self.subTest(experiment_id=experiment_id):
                config = synthetic_replication_identity_config(experiment_id)
                runner.validate_replication_identity(config)
                verifier.validate_replication_identity(config)
                self.assertEqual(runner.model_seed(config), seed)
                public_router, private_router = runner._output_paths(config)
                self.assertEqual(public_router.name, "router")
                self.assertEqual(private_router.name, "router")
                self.assertEqual(public_router.parent.name, "attempt-1")
                self.assertEqual(private_router.parent.name, "attempt-1")

    def test_replication_identity_rejects_seed_path_attempt_and_oracle_drift(self) -> None:
        mutations = []
        wrong_seed = synthetic_replication_identity_config()
        wrong_seed["seed_contract"]["model_seed"] = 44
        mutations.append(wrong_seed)
        wrong_attempt = synthetic_replication_identity_config()
        wrong_attempt["attempt_id"] = "attempt-0"
        mutations.append(wrong_attempt)
        wrong_input = synthetic_replication_identity_config()
        wrong_input["input"]["paired_oof"]["path"] = "private/prior-seed/paired-oof.npz"
        mutations.append(wrong_input)
        extra_input = synthetic_replication_identity_config()
        extra_input["input"]["prior_seed_artifact"] = {
            "path": "prior-seed.npz", "bytes": 1, "sha256": "b" * 64
        }
        mutations.append(extra_input)
        unrelated_prerequisite = synthetic_replication_identity_config()
        unrelated_prerequisite["prerequisites"]["oof_verification"]["path"] = (
            "experiments/stack-overflow-emotion-gold/oof-router/runs/"
            "unrelated-attempt/verification.json"
        )
        mutations.append(unrelated_prerequisite)
        oracle = synthetic_replication_identity_config()
        oracle["prerequisites"]["exp059_oracle_summary"] = {
            "path": "oracle.json", "bytes": 1, "sha256": "b" * 64
        }
        mutations.append(oracle)
        for index, config in enumerate(mutations):
            with self.subTest(index=index):
                with self.assertRaises((ValueError, PermissionError)):
                    runner.validate_replication_identity(config)
                with self.assertRaises((ValueError, PermissionError)):
                    verifier.validate_replication_identity(config)

    def test_replication_temperature_diagnostic_cannot_change_or_block_identity_router(self) -> None:
        config = synthetic_replication_identity_config()
        identity = {
            "experiment_id": "EXP-061",
            "run_id": "exp-061-seed-43-router-replication",
            "attempt_id": "attempt-1",
            "model_seed": 43,
        }
        paired = config["input"]["paired_oof"]
        oof_verification = {
            **identity,
            "status": "Passed",
            "failed_count": 0,
            "verified_artifacts": {"paired_oof_private": paired},
        }
        exp059_run = {**identity, "status": "CompletedAwaitingVerification"}
        exp059_verification = {**identity, "status": "Passed", "failed_count": 0}
        calibration = {
            **identity,
            "router_replication_calibration": copy.deepcopy(
                runner.REPLICATION_CALIBRATION_CONTRACT
            ),
            "families": {
                "m1": {
                    "selected_calibrator": "temperature",
                    "final_temperature": 1.25,
                },
                "m3": {
                    "selected_calibrator": "identity",
                    "final_temperature": 1.0,
                },
            },
        }
        with mock.patch.object(
            runner,
            "_load_frozen_json",
            side_effect=[
                oof_verification,
                exp059_run,
                exp059_verification,
                calibration,
            ],
        ):
            runner._validate_upstream_semantics(config)
        self.assertTrue(runner.replication_calibration_contract_matches(calibration))
        self.assertTrue(verifier.replication_calibration_contract_matches(calibration))

        drifted = copy.deepcopy(calibration)
        drifted["router_replication_calibration"]["temperature"] = 1.25
        self.assertFalse(runner.replication_calibration_contract_matches(drifted))
        self.assertFalse(verifier.replication_calibration_contract_matches(drifted))
        with mock.patch.object(
            runner,
            "_load_frozen_json",
            side_effect=[
                oof_verification,
                exp059_run,
                exp059_verification,
                drifted,
            ],
        ), self.assertRaisesRegex(ValueError, "identity-probability contract"):
            runner._validate_upstream_semantics(config)

    def test_replication_uses_raw_logit_sigmoid_and_only_logistic_at_nominal_15_percent(self) -> None:
        config = synthetic_analysis_config()
        config.update({
            "schema_version": "exp-router-replication-config-v2",
            "experiment_id": "EXP-061",
            "run_id": "exp-061-seed-43-router-replication",
            "attempt_id": "attempt-1",
            "seed_contract": {"model_seed": 43},
        })
        data = synthetic_analysis_data()
        with mock.patch.object(runner, "stable_sigmoid", wraps=runner.stable_sigmoid) as sigmoid:
            analysis = runner.analyze_arrays(data, config)
        self.assertEqual(sigmoid.call_count, 2)
        np.testing.assert_array_equal(sigmoid.call_args_list[0].args[0], data["m1_logits"])
        np.testing.assert_array_equal(sigmoid.call_args_list[1].args[0], data["m3_logits"])
        selected = analysis["selected"]
        independently_recomputed = verifier.build_expected_state(data, config)
        self.assertEqual(selected, independently_recomputed["selected"])
        for name in ("features", "nested_m1_thresholds", "nested_m3_thresholds", "route_scores", "route_masks"):
            np.testing.assert_allclose(
                analysis["private_arrays"][name],
                independently_recomputed["private_arrays"][name],
            )
        self.assertEqual(selected["overall"]["selected_policy"], "logistic_router")
        for policy, record in selected["policies"].items():
            self.assertEqual(record["candidate"]["target_call_rate"], 0.15)
            self.assertEqual(record["evidence_role"], "primary" if policy == "logistic_router" else "descriptive_only")
            if policy != "logistic_router":
                self.assertFalse(record["passed"])

        failing_config = copy.deepcopy(config)
        failing_config["gate"]["minimum_six_label_macro_f1_gain"] = 2.0
        failed = runner.analyze_arrays(data, failing_config)["selected"]
        independently_failed = verifier.build_expected_state(data, failing_config)["selected"]
        self.assertEqual(failed, independently_failed)
        self.assertEqual(failed["overall"]["decision"], "Fail")
        self.assertEqual(failed["overall"]["selected_policy"], "logistic_router")
        self.assertEqual(
            failed["overall"]["selected_candidate"],
            failed["policies"]["logistic_router"]["candidate"],
        )

    def test_hamming_gate_uses_exact_one_e_minus_twelve_boundary(self) -> None:
        baseline = {
            "macro_f1": 0.5,
            "five_label_macro_f1": 0.5,
            "hamming_loss": 0.0,
            "per_label": {label: {"f1": 0.5} for label in runner.LABEL_ORDER},
        }
        candidate = {
            "actual_call_rate": 0.15,
            "macro_f1": 0.6,
            "five_label_macro_f1": 0.6,
            "hamming_loss": 1e-12,
            **{f"f1_{label}": 0.6 for label in runner.LABEL_ORDER},
        }
        config = synthetic_analysis_config()
        _, gates, _ = runner._gate_candidate(candidate, baseline, config)
        self.assertTrue(gates["hamming_loss_not_worse"])
        candidate["hamming_loss"] = 1.1e-12
        _, gates, _ = runner._gate_candidate(candidate, baseline, config)
        self.assertFalse(gates["hamming_loss_not_worse"])

    def test_sealed_exp060_runner_is_archive_only(self) -> None:
        config = runner.load_config(FORMAL_CONFIG)
        self.assertTrue(config["_archive_only"])
        with self.assertRaisesRegex(PermissionError, "archive-only"):
            runner.formal_run(FORMAL_CONFIG, config)
        with self.assertRaisesRegex(FileExistsError, "append-only"):
            verifier.verify(FORMAL_CONFIG)

    def test_replication_completion_binds_primary_vote_without_selecting_attempt(self) -> None:
        config = synthetic_replication_identity_config()
        identity = {
            "experiment_id": "EXP-061",
            "run_id": "exp-061-seed-43-router-replication",
            "attempt_id": "attempt-1",
            "model_seed": 43,
        }
        for primary_gate_passed in (True, False):
            with self.subTest(primary_gate_passed=primary_gate_passed), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                public_attempt = root / "public-attempt"
                private_attempt = root / "private-attempt"
                run_dir = public_attempt / "router"
                private_dir = private_attempt / "router"
                run_dir.mkdir(parents=True)
                private_dir.mkdir(parents=True)
                selection_path = root / "selected-attempt.json"
                config_path = root / "config.json"
                config_path.write_text(json.dumps(config), encoding="utf-8")
                private_path = private_dir / "router-oof.npz"
                private_path.write_bytes(b"synthetic-private-router")

                decision = "Pass" if primary_gate_passed else "Fail"
                primary_candidate = {"target_call_rate": 0.15, "macro_f1": 0.6}
                selected = {
                    "schema_version": "exp-router-selected-operating-point-v2",
                    **identity,
                    "primary_policy": "logistic_router",
                    "primary_nominal_call_rate": 0.15,
                    "baseline": {},
                    "policies": {
                        "m1_max_entropy": {
                            "candidate": {"target_call_rate": 0.15},
                            "passed": False,
                            "evidence_role": "descriptive_only",
                        },
                        "m1_threshold_proximity": {
                            "candidate": {"target_call_rate": 0.15},
                            "passed": False,
                            "evidence_role": "descriptive_only",
                        },
                        "logistic_router": {
                            "candidate": primary_candidate,
                            "passed": primary_gate_passed,
                            "evidence_role": "primary",
                        },
                    },
                    "overall": {
                        "decision": decision,
                        "selected_policy": "logistic_router",
                        "selected_candidate": primary_candidate,
                    },
                }
                selected_path = run_dir / "selected-operating-point.json"
                selected_path.write_text(json.dumps(selected), encoding="utf-8")
                run = {
                    **identity,
                    "status": "CompletedAwaitingVerification",
                    "decision": decision,
                    "public_outputs": {
                        "selected_operating_point_json": runner.artifact(selected_path)
                    },
                }
                run_path = run_dir / "run.json"
                run_path.write_text(json.dumps(run), encoding="utf-8")
                verification = {
                    **identity,
                    "status": "Passed",
                    "failed_count": 0,
                    "verified_artifacts": {
                        "config": runner.artifact(config_path),
                        "run": runner.artifact(run_path),
                        "private_router_oof": runner.artifact(private_path),
                    },
                }
                verification_path = run_dir / "verification.json"
                verification_path.write_text(json.dumps(verification), encoding="utf-8")

                with (
                    mock.patch.object(runner, "_output_paths", return_value=(run_dir, private_dir)),
                    mock.patch.object(
                        runner,
                        "_expected_replication_outputs",
                        return_value={"selection_record": "synthetic-selection"},
                    ),
                    mock.patch.object(
                        runner,
                        "resolve_output",
                        side_effect=lambda value: selection_path
                        if value == "synthetic-selection"
                        else Path(value),
                    ),
                ):
                    completion = runner.complete_router_attempt(config_path, config)
                self.assertEqual(completion["decision"], decision)
                self.assertIs(completion["primary_gate_passed"], primary_gate_passed)
                self.assertFalse(selection_path.exists())

                verifier_outputs = {
                    "public_attempt_dir": "synthetic-public-attempt",
                    "private_attempt_dir": "synthetic-private-attempt",
                    "selection_record": "synthetic-selection",
                }
                resolved = {
                    "synthetic-public-attempt": public_attempt,
                    "synthetic-private-attempt": private_attempt,
                    "synthetic-selection": selection_path,
                }
                verifier_patches = (
                    mock.patch.object(
                        verifier, "require_canonical_config_path", return_value=config_path
                    ),
                    mock.patch.object(verifier, "validate_replication_identity"),
                    mock.patch.object(
                        verifier,
                        "expected_replication_outputs",
                        return_value=verifier_outputs,
                    ),
                    mock.patch.object(
                        verifier, "resolve_output", side_effect=lambda value: resolved[value]
                    ),
                )
                with verifier_patches[0], verifier_patches[1], verifier_patches[2], verifier_patches[3]:
                    completion_verification = verifier.verify_completion(config_path)
                self.assertEqual(completion_verification["status"], "Passed")

                completion_path = run_dir / "router-complete.json"
                original_completion = completion_path.read_text(encoding="utf-8")
                original_selected = selected_path.read_text(encoding="utf-8")
                tamper_cases = {
                    "decision": (
                        completion_path,
                        {
                            **json.loads(original_completion),
                            "decision": "Fail" if decision == "Pass" else "Pass",
                        },
                    ),
                    "primary_gate_passed": (
                        completion_path,
                        {
                            **json.loads(original_completion),
                            "primary_gate_passed": not primary_gate_passed,
                        },
                    ),
                    "selected_operating_point": (
                        selected_path,
                        {
                            **json.loads(original_selected),
                            "primary_nominal_call_rate": 0.2,
                        },
                    ),
                }
                for tamper_name, (tamper_path, tampered) in tamper_cases.items():
                    with self.subTest(
                        primary_gate_passed=primary_gate_passed,
                        tamper=tamper_name,
                    ):
                        completion_path.write_text(original_completion, encoding="utf-8")
                        selected_path.write_text(original_selected, encoding="utf-8")
                        tamper_path.write_text(json.dumps(tampered), encoding="utf-8")
                        with (
                            mock.patch.object(
                                verifier,
                                "require_canonical_config_path",
                                return_value=config_path,
                            ),
                            mock.patch.object(verifier, "validate_replication_identity"),
                            mock.patch.object(
                                verifier,
                                "expected_replication_outputs",
                                return_value=verifier_outputs,
                            ),
                            mock.patch.object(
                                verifier,
                                "resolve_output",
                                side_effect=lambda value: resolved[value],
                            ),
                            self.assertRaises(
                                (RuntimeError, ValueError),
                            ),
                        ):
                            verifier.verify_completion(config_path)

    def test_public_api_signatures_and_feature_order_are_frozen(self) -> None:
        expected_parameters = {
            "stable_sigmoid": ("values",),
            "classification_metrics": ("gold", "prediction"),
            "select_threshold": ("probabilities", "gold", "grid"),
            "build_pre_qwen_features": (
                "m1_probabilities",
                "m1_thresholds",
                "character_lengths",
                "m1_token_lengths",
            ),
            "build_router_target": ("m1_prediction", "m3_prediction", "gold"),
            "score_cutoff": ("meta_train_scores", "target_rate"),
            "apply_score_cutoff": ("scores", "cutoff"),
            "component_aware_random_mask": ("component_ids", "target_count", "seed"),
            "safe_router_metrics": ("target", "scores", "route_mask"),
            "choose_candidate": ("rows", "maximum_call_rate"),
            "routed_uncertainty_scores": (
                "route_mask",
                "m1_probabilities",
                "m3_probabilities",
                "m1_thresholds",
                "m3_thresholds",
            ),
            "public_sensitive_paths": ("value", "prefix"),
        }
        for name, parameters in expected_parameters.items():
            with self.subTest(name=name):
                function = getattr(runner, name)
                self.assertEqual(tuple(inspect.signature(function).parameters), parameters)
        self.assertEqual(runner.FEATURE_NAMES, EXPECTED_FEATURE_NAMES)

    def test_stable_sigmoid_is_finite_monotonic_and_symmetric(self) -> None:
        values = np.asarray([-1000.0, -2.0, 0.0, 2.0, 1000.0])
        probabilities = runner.stable_sigmoid(values)
        self.assertTrue(np.all(np.isfinite(probabilities)))
        self.assertTrue(np.all(np.diff(probabilities) >= 0.0))
        self.assertEqual(float(probabilities[2]), 0.5)
        np.testing.assert_allclose(probabilities[1], 1.0 - probabilities[3], atol=1e-15)
        self.assertLessEqual(float(probabilities[0]), 1e-15)
        self.assertGreaterEqual(float(probabilities[-1]), 1.0 - 1e-15)

    def test_classification_metrics_freeze_six_and_five_label_views(self) -> None:
        gold = np.eye(6, dtype=np.uint8)
        metrics = runner.classification_metrics(gold, gold.copy())
        self.assertEqual(metrics["rows"], 6)
        self.assertEqual(metrics["macro_f1"], 1.0)
        self.assertEqual(metrics["five_label_macro_f1"], 1.0)
        self.assertEqual(metrics["micro_f1"], 1.0)
        self.assertEqual(metrics["hamming_loss"], 0.0)
        self.assertEqual(metrics["subset_accuracy"], 1.0)
        self.assertEqual(tuple(metrics["per_label"]), ("love", "joy", "surprise", "anger", "sadness", "fear"))

    def test_select_threshold_uses_macro_then_hamming_then_distance_then_lower(self) -> None:
        probabilities = np.zeros((1, 6), dtype=np.float64)
        gold = np.zeros((1, 6), dtype=np.uint8)

        def select(grid, metric_rows):
            remaining = iter(metric_rows)
            original = runner.classification_metrics
            try:
                runner.classification_metrics = lambda _gold, _prediction: next(remaining)
                return runner.select_threshold(probabilities, gold, grid)
            finally:
                runner.classification_metrics = original

        macro_winner = select(
            [0.4, 0.5],
            [
                {"macro_f1": 0.8, "hamming_loss": 0.2},
                {"macro_f1": 0.7, "hamming_loss": 0.0},
            ],
        )
        self.assertEqual(macro_winner["threshold"], 0.4)

        hamming_winner = select(
            [0.4, 0.5],
            [
                {"macro_f1": 0.8, "hamming_loss": 0.2},
                {"macro_f1": 0.8, "hamming_loss": 0.1},
            ],
        )
        self.assertEqual(hamming_winner["threshold"], 0.5)

        lower_equidistant_winner = select(
            [0.4, 0.6],
            [
                {"macro_f1": 0.8, "hamming_loss": 0.1},
                {"macro_f1": 0.8, "hamming_loss": 0.1},
            ],
        )
        self.assertEqual(lower_equidistant_winner["threshold"], 0.4)

    def test_select_threshold_uses_one_e_minus_twelve_tolerance(self) -> None:
        probabilities = np.zeros((1, 6), dtype=np.float64)
        gold = np.zeros((1, 6), dtype=np.uint8)

        def run(second_macro: float) -> float:
            remaining = iter(
                [
                    {"macro_f1": 0.8, "hamming_loss": 0.2},
                    {"macro_f1": second_macro, "hamming_loss": 0.1},
                ]
            )
            original = runner.classification_metrics
            try:
                runner.classification_metrics = lambda _gold, _prediction: next(remaining)
                return float(runner.select_threshold(probabilities, gold, [0.4, 0.6])["threshold"])
            finally:
                runner.classification_metrics = original

        self.assertEqual(run(0.8 - 0.5e-12), 0.6)
        self.assertEqual(run(0.8 - 2.0e-12), 0.4)

    def test_select_threshold_prefers_closest_to_half_before_lower_threshold(self) -> None:
        probabilities = np.zeros((1, 6), dtype=np.float64)
        gold = np.zeros((1, 6), dtype=np.uint8)
        remaining = iter(
            [
                {"macro_f1": 0.8, "hamming_loss": 0.1},
                {"macro_f1": 0.8, "hamming_loss": 0.1},
            ]
        )
        original = runner.classification_metrics
        try:
            runner.classification_metrics = lambda _gold, _prediction: next(remaining)
            selected = runner.select_threshold(probabilities, gold, [0.3, 0.4])
        finally:
            runner.classification_metrics = original
        self.assertEqual(selected["threshold"], 0.4)

    def test_select_threshold_uses_one_e_minus_twelve_hamming_tolerance(self) -> None:
        probabilities = np.zeros((1, 6), dtype=np.float64)
        gold = np.zeros((1, 6), dtype=np.uint8)

        def run(second_hamming: float) -> float:
            remaining = iter(
                [
                    {"macro_f1": 0.8, "hamming_loss": 0.1},
                    {"macro_f1": 0.8, "hamming_loss": second_hamming},
                ]
            )
            original = runner.classification_metrics
            try:
                runner.classification_metrics = lambda _gold, _prediction: next(remaining)
                return float(runner.select_threshold(probabilities, gold, [0.2, 0.4])["threshold"])
            finally:
                runner.classification_metrics = original

        self.assertEqual(run(0.1 + 0.5e-12), 0.4)
        self.assertEqual(run(0.1 + 2.0e-12), 0.2)

    def test_feature_builder_freezes_values_dtype_and_column_order(self) -> None:
        probabilities = np.asarray(
            [
                [0.9, 0.2, 0.1, 0.4, 0.3, 0.05],
                [0.1, 0.8, 0.2, 0.3, 0.4, 0.6],
            ],
            dtype=np.float64,
        )
        thresholds = np.asarray([0.31, 0.32])
        matrix, names = runner.build_pre_qwen_features(
            probabilities,
            thresholds,
            np.asarray([120, 240], dtype=np.int32),
            np.asarray([30, 60], dtype=np.int32),
        )
        entropy = -(probabilities * np.log(probabilities) + (1.0 - probabilities) * np.log1p(-probabilities))
        expected = np.column_stack(
            [
                probabilities,
                np.mean(entropy, axis=1),
                np.max(entropy, axis=1),
                np.min(np.abs(probabilities - thresholds[:, None]), axis=1),
                np.sum(probabilities >= thresholds[:, None], axis=1),
                np.max(probabilities, axis=1),
                np.min(probabilities, axis=1),
                [120.0, 240.0],
                [30.0, 60.0],
            ]
        )
        self.assertEqual(names, EXPECTED_FEATURE_NAMES)
        self.assertEqual(matrix.shape, (2, 14))
        self.assertEqual(matrix.dtype, np.dtype("float64"))
        np.testing.assert_allclose(matrix, expected, atol=1e-15)

    def test_router_target_uses_whole_vector_and_ties_choose_m1(self) -> None:
        gold = np.asarray(
            [
                [1, 0, 0, 1, 0, 0],
                [1, 1, 0, 0, 0, 0],
                [0, 0, 0, 0, 0, 0],
            ],
            dtype=np.uint8,
        )
        m1 = np.asarray(
            [
                [1, 0, 0, 1, 0, 0],
                [1, 0, 0, 0, 0, 0],
                [1, 0, 0, 0, 0, 0],
            ],
            dtype=np.uint8,
        )
        m3 = np.asarray(
            [
                [1, 0, 0, 1, 0, 0],
                [1, 1, 0, 0, 0, 0],
                [0, 1, 0, 0, 0, 0],
            ],
            dtype=np.uint8,
        )
        np.testing.assert_array_equal(runner.build_router_target(m1, m3, gold), [0, 1, 0])

    def test_score_cutoff_is_train_only_and_routes_all_heldout_ties(self) -> None:
        train_scores = np.asarray([0.1, 0.4, 0.4, 0.4])
        cutoff = runner.score_cutoff(train_scores, 0.25)
        self.assertEqual(cutoff, 0.4)
        heldout = np.asarray([0.39, 0.4, 0.4, 0.41])
        np.testing.assert_array_equal(runner.apply_score_cutoff(heldout, cutoff), [0, 1, 1, 1])
        np.testing.assert_array_equal(
            runner.apply_score_cutoff(np.asarray([-100.0, 100.0]), cutoff),
            [0, 1],
        )

    def test_component_random_mask_uses_nearest_subset_sum_and_lower_tie(self) -> None:
        equal_distance = runner.component_aware_random_mask(
            np.asarray(["a", "a", "b", "b"]), target_count=1, seed=7
        )
        self.assertEqual(int(np.sum(equal_distance)), 0)

        nearest = runner.component_aware_random_mask(
            np.asarray(["a", "a", "b", "b", "b"]), target_count=4, seed=7
        )
        self.assertEqual(int(np.sum(nearest)), 3)
        for component in ("a", "b"):
            values = nearest[np.asarray(["a", "a", "b", "b", "b"]) == component]
            self.assertEqual(len(np.unique(values)), 1)

        components = np.asarray(["a", "b", "b", "c", "c", "c"])
        first = runner.component_aware_random_mask(components, target_count=3, seed=42)
        second = runner.component_aware_random_mask(components, target_count=3, seed=42)
        np.testing.assert_array_equal(first, second)
        self.assertEqual(int(np.sum(first)), 3)

    def test_component_bootstrap_samples_whole_components_with_replacement(self) -> None:
        component_ids = np.asarray(["a", "a", "b", "c", "c", "c"])
        groups = runner.component_groups(component_ids)
        self.assertEqual([group.tolist() for group in groups], [[0, 1], [2], [3, 4, 5]])

        first = runner.component_bootstrap_indices(groups, np.random.default_rng(0))
        second = runner.component_bootstrap_indices(groups, np.random.default_rng(0))
        np.testing.assert_array_equal(first, second)
        np.testing.assert_array_equal(first, [3, 4, 5, 2, 2])

        # Seed 0 samples components c, b, b.  Every c row appears together, while
        # the repeated b component contributes its row twice.
        self.assertEqual(first.tolist().count(2), 2)
        self.assertEqual([first.tolist().count(index) for index in (3, 4, 5)], [1, 1, 1])

    def test_analyze_arrays_runs_five_fold_nested_cross_fitting_in_source_order(self) -> None:
        data = synthetic_analysis_data()
        feature_calls: list[np.ndarray] = []
        original_builder = runner.build_pre_qwen_features

        def tracking_builder(
            m1_probabilities,
            m1_thresholds,
            character_lengths,
            m1_token_lengths,
        ):
            feature_calls.append(np.asarray(character_lengths).copy())
            return original_builder(
                m1_probabilities,
                m1_thresholds,
                character_lengths,
                m1_token_lengths,
            )

        with mock.patch.object(runner, "build_pre_qwen_features", side_effect=tracking_builder):
            analysis = runner.analyze_arrays(data, synthetic_analysis_config())

        arrays = analysis["private_arrays"]
        self.assertEqual(arrays["features"].shape, (100, 14))
        self.assertEqual(arrays["router_targets"].shape, (100,))
        self.assertEqual(arrays["m1_thresholds"].shape, (100,))
        self.assertEqual(arrays["m3_thresholds"].shape, (100,))
        self.assertEqual(arrays["m1_predictions"].shape, (100, 6))
        self.assertEqual(arrays["m3_predictions"].shape, (100, 6))
        self.assertEqual(arrays["route_scores"].shape, (3, 100))
        self.assertEqual(arrays["route_masks"].shape, (3, 8, 100))
        self.assertEqual(arrays["score_cutoffs"].shape, (3, 8, 5))
        self.assertTrue(np.all(np.isposinf(arrays["score_cutoffs"][:, 0, :])))
        self.assertTrue(np.all(np.isneginf(arrays["score_cutoffs"][:, -1, :])))
        self.assertTrue(np.all(np.isfinite(arrays["score_cutoffs"][:, 1:-1, :])))
        self.assertEqual(len(analysis["call_rows"]), 26)
        self.assertEqual(len(analysis["fold_rows"]), 5)

        for name in ("nested_m1_thresholds", "nested_m3_thresholds"):
            nested = arrays[name]
            self.assertEqual(nested.shape, (5, 5))
            self.assertTrue(np.all(np.isfinite(np.diag(nested))))
            self.assertTrue(np.all(np.isfinite(nested[~np.eye(5, dtype=bool)])))

        # Each outer loop makes four inner-heldout feature calls followed by one
        # outer-heldout call.  The five outer calls must cover every source row
        # exactly once, and must correspond to the declared outer-fold order.
        self.assertEqual(len(feature_calls), 25)
        outer_calls = feature_calls[4::5]
        self.assertEqual(len(outer_calls), 5)
        for outer_fold, observed_lengths in enumerate(outer_calls):
            np.testing.assert_array_equal(
                observed_lengths,
                data["character_lengths"][data["fold_ids"] == outer_fold],
            )
        outer_writeback_lengths = np.concatenate(outer_calls)
        self.assertEqual(len(np.unique(outer_writeback_lengths)), 100)
        np.testing.assert_array_equal(
            np.sort(outer_writeback_lengths), np.sort(data["character_lengths"])
        )

        np.testing.assert_array_equal(arrays["sample_ids"], data["sample_ids"])
        np.testing.assert_array_equal(arrays["component_ids"], data["component_ids"])
        np.testing.assert_array_equal(arrays["fold_ids"], data["fold_ids"])
        np.testing.assert_array_equal(arrays["gold"], data["gold"])
        np.testing.assert_array_equal(arrays["router_targets"], np.arange(100) % 2)
        np.testing.assert_array_equal(arrays["features"][:, 12], data["character_lengths"])
        np.testing.assert_array_equal(arrays["features"][:, 13], data["m1_token_lengths"])
        for row in analysis["fold_rows"]:
            self.assertEqual(row["router_train_rows"], 80)
            self.assertEqual(row["heldout_rows"], 20)
            self.assertGreater(row["router_train_target_positive"], 0)
            self.assertLess(row["router_train_target_positive"], row["router_train_rows"])

    def test_nested_threshold_fit_scopes_exclude_inner_and_outer_heldout_rows(self) -> None:
        data = sentinel_analysis_data()
        folds = data["fold_ids"]
        m1_probabilities = runner.stable_sigmoid(data["m1_logits"])
        m3_probabilities = runner.stable_sigmoid(data["m3_logits"])
        m1_lookup = {
            float(value): index for index, value in enumerate(m1_probabilities[:, 0].tolist())
        }
        m3_lookup = {
            float(value): index for index, value in enumerate(m3_probabilities[:, 0].tolist())
        }
        threshold_calls: list[tuple[str, tuple[int, ...]]] = []

        def tracking_threshold(probabilities, _gold, _grid):
            first_column = np.asarray(probabilities, dtype=np.float64)[:, 0]
            if all(float(value) in m1_lookup for value in first_column.tolist()):
                family = "m1"
                lookup = m1_lookup
            elif all(float(value) in m3_lookup for value in first_column.tolist()):
                family = "m3"
                lookup = m3_lookup
            else:
                raise AssertionError("Threshold input mixed M1/M3 rows or lost row sentinels")
            indices = tuple(lookup[float(value)] for value in first_column.tolist())
            threshold_calls.append((family, indices))
            return {"threshold": 0.5, "macro_f1": 0.0, "hamming_loss": 0.0}

        with mock.patch.object(runner, "select_threshold", side_effect=tracking_threshold):
            runner.analyze_arrays(data, synthetic_analysis_config())

        expected_calls: list[tuple[str, tuple[int, ...]]] = []
        for outer_fold in range(5):
            for inner_fold in range(5):
                if inner_fold == outer_fold:
                    continue
                expected_indices = tuple(
                    np.flatnonzero((folds != outer_fold) & (folds != inner_fold)).tolist()
                )
                self.assertEqual(len(expected_indices), 60)
                self.assertEqual(
                    set(folds[np.asarray(expected_indices, dtype=np.int64)].tolist()),
                    set(range(5)) - {outer_fold, inner_fold},
                )
                expected_calls.extend((("m1", expected_indices), ("m3", expected_indices)))
            outer_train_indices = tuple(np.flatnonzero(folds != outer_fold).tolist())
            self.assertEqual(len(outer_train_indices), 80)
            expected_calls.extend((("m1", outer_train_indices), ("m3", outer_train_indices)))

        self.assertEqual(threshold_calls, expected_calls)

    def test_scaler_router_and_cutoff_receive_outer_train_rows_only(self) -> None:
        data = sentinel_analysis_data()
        folds = data["fold_ids"]
        original_builder = runner.build_pre_qwen_features
        original_cutoff = runner.score_cutoff
        scaled_row_ids: dict[int, tuple[int, ...]] = {}
        scaler_fit_calls: list[tuple[int, ...]] = []
        scaler_transform_calls: list[tuple[int, ...]] = []
        router_fit_calls: list[tuple[int, ...]] = []
        router_score_calls: list[tuple[int, ...]] = []
        cutoff_calls: list[tuple[str, float, tuple[int, ...]]] = []

        def fixed_threshold(_probabilities, _gold, _grid):
            return {"threshold": 0.5, "macro_f1": 0.0, "hamming_loss": 0.0}

        def sentinel_builder(
            m1_probabilities,
            m1_thresholds,
            character_lengths,
            m1_token_lengths,
        ):
            matrix, names = original_builder(
                m1_probabilities,
                m1_thresholds,
                character_lengths,
                m1_token_lengths,
            )
            indices = np.asarray(
                row_indices_from_character_lengths(character_lengths), dtype=np.float64
            )
            matrix = matrix.copy()
            matrix[:, 7] = 1.0 + indices * 0.001
            matrix[:, 8] = 10.0 + indices * 0.001
            return matrix, names

        class TrackingScaler:
            def fit_transform(self, matrix):
                rows = row_indices_from_character_lengths(np.asarray(matrix)[:, 12])
                scaler_fit_calls.append(rows)
                values = np.asarray(matrix, dtype=np.float64)
                self.mean_ = np.mean(values, axis=0)
                self.scale_ = np.std(values, axis=0)
                self.scale_[self.scale_ == 0.0] = 1.0
                result = (values - self.mean_) / self.scale_
                scaled_row_ids[id(result)] = rows
                return result

            def transform(self, matrix):
                rows = row_indices_from_character_lengths(np.asarray(matrix)[:, 12])
                scaler_transform_calls.append(rows)
                result = (np.asarray(matrix, dtype=np.float64) - self.mean_) / self.scale_
                scaled_row_ids[id(result)] = rows
                return result

        class TrackingRouter:
            def __init__(self, **_kwargs):
                self.n_iter_ = np.asarray([1], dtype=np.int32)
                self.coef_ = np.zeros((1, len(runner.FEATURE_NAMES)), dtype=np.float64)
                self.intercept_ = np.zeros(1, dtype=np.float64)

            def fit(self, matrix, target):
                rows = scaled_row_ids[id(matrix)]
                self_outer = set(int(folds[index]) for index in rows)
                if len(rows) != len(target) or len(self_outer) != 4:
                    raise AssertionError("Router fit did not receive one four-fold training partition")
                router_fit_calls.append(rows)
                return self

            def predict_proba(self, matrix):
                rows = scaled_row_ids[id(matrix)]
                router_score_calls.append(rows)
                positive = 0.6 + np.asarray(rows, dtype=np.float64) * 0.001
                return np.column_stack([1.0 - positive, positive])

        def tracking_cutoff(scores, target_rate):
            values = np.asarray(scores, dtype=np.float64)
            if np.all((values >= 1.0) & (values < 1.1)):
                policy = "m1_max_entropy"
                indices = np.rint((values - 1.0) * 1000.0).astype(np.int64)
            elif np.all((values <= -10.0) & (values > -10.1)):
                policy = "m1_threshold_proximity"
                indices = np.rint((-values - 10.0) * 1000.0).astype(np.int64)
            elif np.all((values >= 0.6) & (values < 0.7)):
                policy = "logistic_router"
                indices = np.rint((values - 0.6) * 1000.0).astype(np.int64)
            else:
                raise AssertionError("Cutoff input did not preserve its train-row sentinel")
            cutoff_calls.append(
                (policy, float(target_rate), tuple(int(value) for value in indices.tolist()))
            )
            return original_cutoff(values, target_rate)

        with (
            mock.patch.object(runner, "select_threshold", side_effect=fixed_threshold),
            mock.patch.object(runner, "build_pre_qwen_features", side_effect=sentinel_builder),
            mock.patch.object(runner, "StandardScaler", TrackingScaler),
            mock.patch.object(runner, "LogisticRegression", TrackingRouter),
            mock.patch.object(runner, "score_cutoff", side_effect=tracking_cutoff),
        ):
            runner.analyze_arrays(data, synthetic_analysis_config())

        self.assertEqual(len(scaler_fit_calls), 5)
        self.assertEqual(len(scaler_transform_calls), 5)
        self.assertEqual(len(router_fit_calls), 5)
        self.assertEqual(len(router_score_calls), 10)
        self.assertEqual(len(cutoff_calls), 5 * 3 * 8)
        cutoff_position = 0
        for outer_fold in range(5):
            expected_train = set(np.flatnonzero(folds != outer_fold).tolist())
            expected_heldout = tuple(np.flatnonzero(folds == outer_fold).tolist())
            for observed in (scaler_fit_calls[outer_fold], router_fit_calls[outer_fold]):
                self.assertEqual(len(observed), 80)
                self.assertEqual(set(observed), expected_train)
                self.assertTrue(set(observed).isdisjoint(expected_heldout))
            self.assertEqual(scaler_transform_calls[outer_fold], expected_heldout)
            self.assertEqual(set(router_score_calls[2 * outer_fold]), expected_train)
            self.assertEqual(router_score_calls[2 * outer_fold + 1], expected_heldout)
            for policy in runner.POLICY_ORDER:
                for target_rate in synthetic_analysis_config()["call_rates"]:
                    observed_policy, observed_rate, observed_rows = cutoff_calls[cutoff_position]
                    cutoff_position += 1
                    self.assertEqual(observed_policy, policy)
                    self.assertEqual(observed_rate, target_rate)
                    self.assertEqual(len(observed_rows), 80)
                    self.assertEqual(set(observed_rows), expected_train)
                    self.assertTrue(set(observed_rows).isdisjoint(expected_heldout))

    def test_outer_router_train_single_class_stops_before_fitting(self) -> None:
        data = synthetic_analysis_data()
        data["m3_logits"] = data["m1_logits"].copy()
        with self.assertRaisesRegex(RuntimeError, "Outer fold 0.*single-class"):
            runner.analyze_arrays(data, synthetic_analysis_config())

    def test_unexpected_infinite_router_parameter_fails_stop(self) -> None:
        data = synthetic_analysis_data()

        class InfiniteParameterRouter:
            def __init__(self, **_kwargs):
                self.n_iter_ = np.asarray([1], dtype=np.int32)
                self.coef_ = np.zeros((1, len(runner.FEATURE_NAMES)), dtype=np.float64)
                self.intercept_ = np.zeros(1, dtype=np.float64)

            def fit(self, _matrix, _target):
                self.coef_[0, 0] = np.inf
                return self

            def predict_proba(self, matrix):
                positive = np.full(len(matrix), 0.5, dtype=np.float64)
                return np.column_stack([1.0 - positive, positive])

        with (
            mock.patch.object(runner, "LogisticRegression", InfiniteParameterRouter),
            self.assertRaisesRegex(RuntimeError, "Non-finite"),
        ):
            runner.analyze_arrays(data, synthetic_analysis_config())

    def test_safe_router_metrics_returns_none_auc_for_single_class_target(self) -> None:
        scores = np.asarray([0.1, 0.2, 0.3, 0.4])
        route_mask = np.asarray([0, 1, 0, 1], dtype=np.uint8)
        for value in (0, 1):
            with self.subTest(value=value):
                metrics = runner.safe_router_metrics(
                    np.full(4, value, dtype=np.uint8), scores, route_mask
                )
                self.assertIsNone(metrics["pr_auc"])
                self.assertIsNone(metrics["roc_auc"])
                self.assertEqual(metrics["target_prevalence"], float(value))

    def test_choose_candidate_freezes_filter_and_tie_order(self) -> None:
        rows = [
            {"id": "over-budget", "six_label_macro_f1": 1.0, "hamming_loss": 0.0, "actual_call_rate": 0.21, "target_call_rate": 0.05},
            {"id": "macro", "six_label_macro_f1": 0.80, "hamming_loss": 0.01, "actual_call_rate": 0.10, "target_call_rate": 0.10},
            {"id": "hamming", "six_label_macro_f1": 0.81, "hamming_loss": 0.20, "actual_call_rate": 0.10, "target_call_rate": 0.10},
            {"id": "actual-rate", "six_label_macro_f1": 0.81, "hamming_loss": 0.10, "actual_call_rate": 0.18, "target_call_rate": 0.15},
            {"id": "target-rate", "six_label_macro_f1": 0.81, "hamming_loss": 0.10, "actual_call_rate": 0.15, "target_call_rate": 0.10},
            {"id": "winner", "six_label_macro_f1": 0.81, "hamming_loss": 0.10, "actual_call_rate": 0.15, "target_call_rate": 0.05},
        ]
        self.assertEqual(runner.choose_candidate(rows, 0.20)["id"], "winner")
        self.assertIsNone(runner.choose_candidate(rows, 0.0))

    def test_routed_uncertainty_uses_final_selected_family_and_nested_threshold(self) -> None:
        route_mask = np.asarray([0, 1], dtype=np.uint8)
        m1 = np.asarray([[0.9, 0.2], [0.8, 0.3]], dtype=np.float64)
        m3 = np.asarray([[0.6, 0.4], [0.55, 0.45]], dtype=np.float64)
        m1_thresholds = np.asarray([0.5, 0.7])
        m3_thresholds = np.asarray([0.4, 0.5])
        scores = runner.routed_uncertainty_scores(
            route_mask, m1, m3, m1_thresholds, m3_thresholds
        )
        selected = np.asarray([[0.9, 0.2], [0.55, 0.45]])
        selected_thresholds = np.asarray([0.5, 0.5])
        entropy = -(selected * np.log(selected) + (1.0 - selected) * np.log1p(-selected))
        np.testing.assert_allclose(scores["mean_entropy"], np.mean(entropy, axis=1))
        np.testing.assert_allclose(scores["max_entropy"], np.max(entropy, axis=1))
        np.testing.assert_allclose(
            scores["margin"],
            -np.min(np.abs(selected - selected_thresholds[:, None]), axis=1),
        )

    def test_public_privacy_scanner_allows_contracts_but_rejects_row_values(self) -> None:
        safe = {
            "feature_contract": {"ordered_features": list(EXPECTED_FEATURE_NAMES)},
            "input_schema": [
                {"array_name": "sample_ids", "dtype": "<U31", "shape": [3360]}
            ],
        }
        self.assertEqual(runner.public_sensitive_paths(safe), [])
        self.assertEqual(set(runner.PUBLIC_SENSITIVE_KEYS), set(FORBIDDEN_PUBLIC_KEYS))
        for key in FORBIDDEN_PUBLIC_KEYS:
            with self.subTest(key=key):
                unsafe = {"public": {"nested": {key: ["row-level-value"]}}}
                self.assertEqual(
                    runner.public_sensitive_paths(unsafe),
                    [f"$.public.nested.{key}"],
                )

    def test_verifier_ast_does_not_import_or_dynamically_load_runner(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: list[str] = []
        forbidden_calls: list[str] = []
        runner_references: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {
                    "__import__",
                    "compile",
                    "eval",
                    "exec",
                    "SourceFileLoader",
                }:
                    forbidden_calls.append(node.func.id)
                elif isinstance(node.func, ast.Attribute) and node.func.attr in {
                    "exec_module",
                    "import_module",
                    "run_module",
                    "run_path",
                    "SourceFileLoader",
                    "spec_from_file_location",
                }:
                    forbidden_calls.append(node.func.attr)
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and "run_exp060_router" in node.value
            ):
                runner_references.append(node.value)
        self.assertFalse(any(name.endswith("run_exp060_router") for name in imported))
        self.assertFalse(
            any(name.split(".", 1)[0] in {"importlib", "runpy", "subprocess"} for name in imported)
        )
        self.assertEqual(forbidden_calls, [])
        self.assertEqual(runner_references, [])

    @unittest.skipUnless(FORMAL_CONFIG.is_file(), "formal EXP-060 config not present yet")
    def test_formal_config_freezes_authorization_and_complete_contracts(self) -> None:
        config = json.loads(FORMAL_CONFIG.read_text(encoding="utf-8"))
        for section in (
            "authorization",
            "input",
            "data",
            "cross_fitting",
            "thresholds",
            "target_contract",
            "feature_contract",
            "router",
            "call_rates",
            "gate",
            "bootstrap",
            "outputs",
        ):
            self.assertIn(section, config)

        authorization = config["authorization"]
        self.assertTrue(authorization["formal_router_training"])
        self.assertTrue(authorization["formal_result_computation"])
        for key in (
            "validation_access",
            "test_access",
            "model_loading_or_forward",
            "raw_text_access",
        ):
            self.assertFalse(authorization[key], key)

        self.assertEqual(config["cross_fitting"]["outer_fold_ids"], [0, 1, 2, 3, 4])
        self.assertEqual(config["cross_fitting"]["outer_router_train_folds"], 4)
        self.assertEqual(config["cross_fitting"]["outer_router_heldout_folds"], 1)
        self.assertEqual(config["cross_fitting"]["nested_router_train_threshold_folds"], 3)
        self.assertEqual(config["cross_fitting"]["outer_heldout_threshold_folds"], 4)
        self.assertTrue(config["cross_fitting"]["nested_threshold_recomputation"])
        self.assertTrue(config["cross_fitting"]["reuse_exp058_duplicate_component_partition"])
        self.assertTrue(config["cross_fitting"]["restore_exp058_source_order"])

        self.assertEqual(config["data"]["protocol_id"], "DATA-SO-TASK-V1")
        self.assertEqual(config["data"]["split"], "train-oof")
        self.assertEqual(config["data"]["rows"], 3360)
        self.assertEqual(config["data"]["duplicate_components"], 3277)
        self.assertEqual(
            config["data"]["label_order"],
            ["love", "joy", "surprise", "anger", "sadness", "fear"],
        )

        self.assertEqual(tuple(config["feature_contract"]["ordered_features"]), EXPECTED_FEATURE_NAMES)
        self.assertEqual(config["feature_contract"]["feature_count"], 14)
        self.assertEqual(
            config["feature_contract"]["scaler"],
            "StandardScaler_fit_inside_outer_router_train",
        )
        self.assertEqual(
            config["feature_contract"]["forbidden_runtime_feature_classes"],
            [
                "all_m3_values",
                "gold_or_correctness",
                "oracle_or_model_disagreement",
                "sample_component_or_fold_ids",
                "raw_text",
                "validation_or_test_statistics",
            ],
        )
        self.assertFalse(config["feature_contract"]["m1_raw_logits_included"])
        self.assertFalse(config["feature_contract"]["m3_token_length_included"])

        self.assertEqual(config["thresholds"]["calibrator"], "identity_for_m1_and_m3")
        self.assertEqual(config["thresholds"]["grid_start"], 0.05)
        self.assertEqual(config["thresholds"]["grid_end"], 0.95)
        self.assertEqual(config["thresholds"]["grid_step"], 0.01)
        threshold_grid = [
            round(config["thresholds"]["grid_start"] + index * config["thresholds"]["grid_step"], 12)
            for index in range(91)
        ]
        self.assertEqual(threshold_grid, [round(0.05 + index * 0.01, 12) for index in range(91)])
        self.assertEqual(
            tuple(config["thresholds"]["selection_order"]),
            EXPECTED_THRESHOLD_SELECTION_ORDER,
        )
        self.assertEqual(config["thresholds"]["numeric_tolerance"], 1e-12)

        self.assertEqual(config["target_contract"]["unit"], "whole_six_bit_vector")
        self.assertEqual(
            config["target_contract"]["positive"],
            "m3_row_hamming_loss_strictly_lower_than_m1",
        )
        self.assertEqual(config["target_contract"]["tie_policy"], "m1")
        self.assertTrue(config["target_contract"]["gold_is_training_outcome_only"])
        self.assertTrue(config["target_contract"]["m3_is_training_outcome_only"])
        self.assertFalse(config["target_contract"]["exp059_oracle_array_used_as_formal_target"])

        self.assertEqual(
            config["router"]["policies"],
            [
                "m1_only",
                "m3_only",
                "m1_max_entropy",
                "m1_threshold_proximity",
                "logistic_router",
            ],
        )
        self.assertFalse(config["router"]["hyperparameter_search"])
        self.assertEqual(
            config["router"]["logistic_regression"],
            {
                "penalty": "l2",
                "C": 1.0,
                "class_weight": "balanced",
                "solver": "liblinear",
                "max_iter": 1000,
                "random_state": 42,
            },
        )
        self.assertEqual(config["router"]["random_routing_repetitions"], 100)
        self.assertEqual(config["router"]["random_routing_seed"], 20260817)

        self.assertEqual(config["call_rates"], [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0])
        self.assertEqual(config["gate"]["maximum_actual_qwen_call_rate"], 0.2)
        self.assertEqual(config["gate"]["minimum_six_label_macro_f1_gain"], 0.01)
        self.assertEqual(config["gate"]["minimum_five_label_macro_f1_gain"], -0.005)
        self.assertEqual(config["gate"]["maximum_hamming_loss_increase"], 1e-12)
        self.assertEqual(config["gate"]["minimum_one_non_surprise_label_f1_gain"], 0.005)
        self.assertEqual(
            config["gate"]["candidate_tie_order"],
            [
                "highest_six_label_macro_f1",
                "lowest_hamming_loss",
                "lower_actual_call_rate",
                "lower_target_call_rate",
            ],
        )
        self.assertEqual(
            config["gate"]["deployable_policy_passes_if_any_of"],
            ["m1_max_entropy", "m1_threshold_proximity", "logistic_router"],
        )
        self.assertTrue(config["gate"]["point_estimate_determines_development_gate"])
        self.assertTrue(config["gate"]["bootstrap_interval_determines_stability_claim"])

        self.assertEqual(config["bootstrap"]["repetitions"], 2000)
        self.assertEqual(config["bootstrap"]["unit"], "duplicate_component")
        self.assertEqual(config["bootstrap"]["seed"], 20260817)
        self.assertEqual(config["bootstrap"]["interval"], "percentile_95")

        paired = config["input"]["paired_oof"]
        self.assertEqual(
            paired["path"],
            "experiments/stack-overflow-emotion-gold/oof-router/private/"
            "exp-058-paired-oof-production/paired-oof.npz",
        )
        self.assertEqual(
            paired["sha256"],
            "e8d2efde7ca62b3f09519390a6305d09ba0f3ea1dfbecbe8a11dbe4ffd482bfc",
        )
        self.assertGreater(paired["bytes"], 0)
        for section in ("implementation", "prerequisites", "input"):
            for record in runner.iter_records(config[section]):
                self.assertGreater(record["bytes"], 0)
                self.assertEqual(len(record["sha256"]), 64)

        self.assertEqual(
            config["outputs"]["formal_run_dir"], runner.EXPECTED_PUBLIC_RUN_DIR
        )
        self.assertEqual(
            config["outputs"]["formal_private_dir"], runner.EXPECTED_PRIVATE_RUN_DIR
        )


if __name__ == "__main__":
    unittest.main()
