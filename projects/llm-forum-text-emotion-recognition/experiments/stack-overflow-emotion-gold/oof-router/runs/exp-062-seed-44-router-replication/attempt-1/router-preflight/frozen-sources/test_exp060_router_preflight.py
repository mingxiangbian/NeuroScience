from __future__ import annotations

import ast
from contextlib import ExitStack, contextmanager
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp060_router_preflight.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp060_router_preflight.py"
BASE = Path("experiments/stack-overflow-emotion-gold/oof-router")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_module("exp060_preflight_runner_under_test", RUNNER_PATH)
verifier = load_module("exp060_preflight_verifier_under_test", VERIFIER_PATH)


def write_json(path: Path, value: object, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.chmod(path, mode)


def file_record(root: Path, path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "path": str(path.relative_to(root)),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def write_source(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    os.chmod(path, 0o644)


def identity(experiment_id: str) -> dict[str, object]:
    return {
        "experiment_id": experiment_id,
        "run_id": runner.REPLICATION_RUN_ID,
        "attempt_id": runner.REPLICATION_ATTEMPT_ID,
        "model_seed": 44,
        "seed_contract": runner.expected_seed_contract(),
    }


def exp059_identity() -> dict[str, object]:
    return {
        "experiment_id": "EXP-059",
        "replication_parent_experiment_id": "EXP-062",
        "run_id": runner.REPLICATION_RUN_ID,
        "attempt_id": runner.REPLICATION_ATTEMPT_ID,
        "model_seed": 44,
        "seed_contract": runner.expected_seed_contract(),
    }


def make_paired(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    rows = 3360
    np.savez_compressed(
        path,
        sample_ids=np.asarray([f"s{index:030d}" for index in range(rows)], dtype="<U31"),
        component_ids=np.asarray([f"c{index:033d}" for index in range(rows)], dtype="<U34"),
        fold_ids=(np.arange(rows) % 5).astype(np.int8),
        gold=np.zeros((rows, 6), dtype=np.uint8),
        m1_logits=np.zeros((rows, 6), dtype=np.float32),
        m3_logits=np.zeros((rows, 6), dtype=np.float32),
        character_lengths=np.ones(rows, dtype=np.int32),
        m1_token_lengths=np.ones(rows, dtype=np.int32),
        m3_token_lengths=np.ones(rows, dtype=np.int32),
        m1_fold_run_sha256=np.asarray(["a" * 64] * rows, dtype="<U64"),
        m3_fold_run_sha256=np.asarray(["b" * 64] * rows, dtype="<U64"),
    )
    os.chmod(path, 0o600)


def make_upstreams(root: Path, paired_record: dict[str, object]) -> dict[str, dict]:
    attempt = root / BASE / "runs" / runner.REPLICATION_RUN_ID / "attempt-1"
    placeholder = dict(paired_record)
    oof_config = dict(placeholder)
    oof_summary = dict(placeholder)
    oof_run_path = attempt / "run.json"
    oof_run = {key: None for key in runner.OOF_RUN_KEYS}
    oof_run.update(
        {
            "schema_version": "exp-oof-production-run-v2",
            **identity("EXP-062"),
            "rq_id": "RQ-S3",
            "stage": "paired-m1-m3-oof-production",
            "status": "CompletedAwaitingVerification",
            "config": oof_config,
            "artifacts": {
                "paired_oof_private": paired_record,
                "paired_oof_summary": oof_summary,
                "partition_contract_private": placeholder,
            },
        }
    )
    write_json(oof_run_path, oof_run)
    oof_run_record = file_record(root, oof_run_path)
    fold_records = {
        family: {str(index): dict(placeholder) for index in range(5)}
        for family in ("m1", "m3")
    }
    oof_verified = {
        "config": oof_config,
        "fold_runs": copy.deepcopy(fold_records),
        "fold_verifications": copy.deepcopy(fold_records),
        "paired_oof_private": paired_record,
        "run": oof_run_record,
        "summary": oof_summary,
    }
    oof_checks = [{"name": "synthetic-oof", "passed": True, "detail": None}]
    oof_verification = {key: None for key in runner.OOF_VERIFICATION_KEYS}
    oof_verification.update(
        {
            "schema_version": "exp-oof-final-verification-v2",
            **identity("EXP-062"),
            "stage": "paired-m1-m3-oof-production",
            "scope": "final",
            "status": "Passed",
            "check_count": len(oof_checks),
            "passed_count": len(oof_checks),
            "failed_count": 0,
            "checks": oof_checks,
            "independence": {
                "all_fold_tables_recomputed": True,
                "model_libraries_imported": False,
                "paired_table_recomputed": True,
                "runner_imported": False,
            },
            "verified_artifacts": oof_verified,
        }
    )
    oof_verification_path = attempt / "verification.json"
    write_json(oof_verification_path, oof_verification)
    oof_verification_record = file_record(root, oof_verification_path)
    oof_completion = {key: None for key in runner.OOF_COMPLETION_KEYS}
    oof_completion.update(
        {
            "schema_version": "exp-oof-completion-v2",
            **identity("EXP-062"),
            "stage": "paired-m1-m3-oof-production",
            "status": "Complete",
            "config": oof_config,
            "artifacts": {
                "run": oof_run_record,
                "summary": oof_summary,
                "final_verification": oof_verification_record,
                "paired_oof_private": paired_record,
            },
        }
    )
    oof_completion_path = attempt / "oof-complete.json"
    write_json(oof_completion_path, oof_completion)

    calibration_dir = attempt / "calibration"
    frozen_sources = {
        name: dict(placeholder) for name in ("config", "protocol", "runner", "verifier", "tests")
    }
    public_outputs = {name: dict(placeholder) for name in runner.EXP059_PUBLIC_OUTPUT_KEYS}
    exp059_config = dict(placeholder)
    private_calibration = dict(placeholder)
    exp059_run = {key: None for key in runner.EXP059_RUN_KEYS}
    exp059_run.update(
        {
            "schema_version": "exp-059-formal-run-v2",
            **exp059_identity(),
            "rq_id": "RQ-S3",
            "stage": "cross-fitted-calibration-selective-prediction",
            "status": "CompletedAwaitingVerification",
            "rows": 3360,
            "folds": 5,
            "component_count": 3277,
            "config": exp059_config,
            "input_before": paired_record,
            "input_sha256_after": paired_record["sha256"],
            "calibration_performed": True,
            "oracle_analysis_performed": True,
            "performance_metrics_computed": True,
            "selective_prediction_performed": True,
            "model_loading_or_forward_performed": False,
            "router_training_performed": False,
            "router_replication_calibration": dict(runner.REPLICATION_CALIBRATION_CONTRACT),
            "resources": {
                "wall_seconds": 1.0,
                "peak_process_rss_gb": 0.1,
                "api_cost_usd": 0,
            },
            "frozen_sources": frozen_sources,
            "public_outputs": public_outputs,
            "private_output": private_calibration,
            "split_access": {
                "accessed_splits": ["train-oof"],
                "validation_accessed": False,
                "test_inputs_accessed": False,
                "test_labels_accessed": False,
            },
        }
    )
    write_json(
        calibration_dir / "run.json",
        exp059_run,
    )
    exp059_run_path = calibration_dir / "run.json"
    exp059_run_record = file_record(root, exp059_run_path)
    parameters_path = calibration_dir / "calibration-parameters.json"
    write_json(
        parameters_path,
        {
            **exp059_identity(),
            "families": {
                "m1": {
                    "final_global_threshold": [], "final_temperature": 1.0,
                    "fold_fits": [], "full_oof_temperature_fit": {},
                    "selected_calibrator": "identity",
                },
                "m3": {
                    "final_global_threshold": [], "final_temperature": 1.18,
                    "fold_fits": [], "full_oof_temperature_fit": {},
                    "selected_calibrator": "temperature",
                },
            },
            "router_replication_calibration": dict(runner.REPLICATION_CALIBRATION_CONTRACT),
        },
    )
    parameters_record = file_record(root, parameters_path)
    exp059_checks = [{"name": "synthetic-exp059", "passed": True, "detail": None}]
    exp059_verified = {
        "calibration_parameters": parameters_record,
        "config": exp059_config,
        "frozen_sources": frozen_sources,
        "paired_oof": paired_record,
        "private_output": private_calibration,
        "public_outputs": public_outputs,
        "run": exp059_run_record,
    }
    exp059_verification = {key: None for key in runner.EXP059_VERIFICATION_KEYS}
    exp059_verification.update(
        {
            "schema_version": "exp-059-verification-v2",
            **exp059_identity(),
            "rq_id": "RQ-S3",
            "scope": "final",
            "status": "Passed",
            "passed_count": len(exp059_checks),
            "failed_count": 0,
            "checks": exp059_checks,
            "resources": {
                "wall_seconds": 1.0,
                "peak_process_rss_gb": 0.1,
                "api_cost_usd": 0,
            },
            "verified_artifacts": exp059_verified,
        }
    )
    exp059_verification_path = calibration_dir / "verification.json"
    write_json(exp059_verification_path, exp059_verification)
    exp059_verification_record = file_record(root, exp059_verification_path)
    exp059_completion = {key: None for key in runner.EXP059_COMPLETION_KEYS}
    exp059_completion.update(
        {
            "schema_version": "exp-059-calibration-completion-v2",
            **exp059_identity(),
            "status": "Complete",
            "artifacts": {
                "config": exp059_config,
                "exp059_run": exp059_run_record,
                "exp059_verification": exp059_verification_record,
                "exp059_calibration_parameters": parameters_record,
                "exp059_verification_summary": dict(placeholder),
                "frozen_sources": frozen_sources,
                "paired_oof_private": paired_record,
                "private_calibration": private_calibration,
                "public_outputs": public_outputs,
            },
        }
    )
    exp059_completion_path = attempt / "calibration-complete.json"
    write_json(exp059_completion_path, exp059_completion)
    return {
        "oof_verification": oof_verification_record,
        "oof_completion": file_record(root, oof_completion_path),
        "exp059_run": exp059_run_record,
        "exp059_verification": exp059_verification_record,
        "exp059_calibration_parameters": parameters_record,
        "exp059_calibration_completion": file_record(root, exp059_completion_path),
    }


def make_config(root: Path) -> tuple[Path, dict]:
    router_dir = root / BASE
    tests_dir = router_dir / "tests"
    protocol_dir = root / "experiments/stack-overflow-emotion-gold/protocols"
    paths = {
        "protocol": protocol_dir / "exp-060-pre-qwen-deployable-router.md",
        "preflight_runner": router_dir / "run_exp060_router_preflight.py",
        "preflight_verifier": router_dir / "verify_exp060_router_preflight.py",
        "preflight_tests": tests_dir / "test_exp060_router_preflight.py",
        "runner": router_dir / "run_exp060_router.py",
        "verifier": router_dir / "verify_exp060_router.py",
        "tests": tests_dir / "test_exp060_router.py",
        "runner_launcher": router_dir / "run_exp060_router_v3.py",
        "verifier_launcher": router_dir / "verify_exp060_router_v3.py",
        "launcher_tests": tests_dir / "test_exp060_router_v3.py",
    }
    write_source(paths["preflight_runner"], "# preflight runner\n")
    write_source(paths["preflight_verifier"], "# independent preflight verifier\n")
    write_source(paths["preflight_tests"], "raise SystemExit(0)\n")
    write_source(paths["runner"], (MODULE_DIR / "run_exp060_router.py").read_text())
    write_source(paths["verifier"], (MODULE_DIR / "verify_exp060_router.py").read_text())
    write_source(paths["tests"], (MODULE_DIR / "tests/test_exp060_router.py").read_text())
    write_source(paths["runner_launcher"], "# seed44 runner governance launcher\n")
    write_source(paths["verifier_launcher"], "# seed44 verifier governance launcher\n")
    write_source(paths["launcher_tests"], "raise SystemExit(0)\n")
    write_source(paths["protocol"], "# frozen protocol\n")
    implementation = {name: file_record(root, path) for name, path in paths.items()}
    outputs = runner.expected_replication_outputs()
    public_attempt = root / outputs["public_attempt_dir"]
    private_attempt = root / outputs["private_attempt_dir"]
    public_attempt.mkdir(parents=True)
    private_attempt.mkdir(parents=True)
    os.chmod(root / outputs["public_namespace"], 0o755)
    os.chmod(public_attempt, 0o755)
    os.chmod(root / outputs["private_namespace"], 0o700)
    os.chmod(private_attempt, 0o700)
    paired = private_attempt / "paired-oof.npz"
    make_paired(paired)
    paired_record = file_record(root, paired)
    config = {
        "schema_version": runner.REPLICATION_PREFLIGHT_SCHEMA,
        "experiment_id": "EXP-060",
        "replication_parent_experiment_id": "EXP-062",
        "run_id": runner.REPLICATION_RUN_ID,
        "attempt_id": "attempt-1",
        "model_seed": 44,
        "seed_contract": runner.expected_seed_contract(),
        "rq_id": "RQ-S3",
        "tier": "Major infrastructure preflight",
        "stage": runner.REPLICATION_STAGE,
        "registered_at": runner.REPLICATION_REGISTERED_AT,
        "authorization": {
            "basis": "synthetic",
            "model_seed": 44,
            "no_result_preflight": True,
            "formal_router_training": False,
            "formal_result_computation": False,
            "validation_access": False,
            "test_access": False,
            "model_loading_or_forward": False,
            "raw_text_access": False,
        },
        "provenance": dict(runner.REPLICATION_PROVENANCE),
        "path_bases": dict(runner.REPLICATION_PATH_BASES),
        "artifact_contract": dict(runner.REPLICATION_ARTIFACT_CONTRACT),
        "runtime": dict(runner.REPLICATION_RUNTIME),
        "implementation": implementation,
        "prerequisites": make_upstreams(root, paired_record),
        "input": {"paired_oof": paired_record},
        "outputs": outputs,
        "data": {
            "protocol_id": "DATA-SO-TASK-V1",
            "split": "train-oof",
            "rows": 3360,
            "duplicate_components": 3277,
            "upstream_seed": 44,
            "source_order_sha256": "c9e4bd1eb2bdbb33c833234754c493b8818aa6c610acaf88659ae74fa94848a3",
            "label_order": list(runner.LABEL_ORDER),
        },
        "cross_fitting": {
            "outer_fold_ids": [0, 1, 2, 3, 4],
            "outer_router_train_folds": 4,
            "outer_router_heldout_folds": 1,
            "nested_threshold_recomputation": True,
            "nested_router_train_threshold_folds": 3,
            "outer_heldout_threshold_folds": 4,
            "reuse_exp058_duplicate_component_partition": True,
            "restore_exp058_source_order": True,
        },
        "thresholds": {
            "calibrator": "identity_for_m1_and_m3",
            "probability_source": "direct_sigmoid_of_raw_oof_logits",
            "grid_start": 0.05,
            "grid_end": 0.95,
            "grid_step": 0.01,
            "selection_order": [
                "highest_six_label_macro_f1", "lowest_hamming_loss",
                "closest_to_0_5", "lower_threshold",
            ],
            "numeric_tolerance": 1e-12,
        },
        "target_contract": {
            "unit": "whole_six_bit_vector",
            "positive": "m3_row_hamming_loss_strictly_lower_than_m1",
            "tie_policy": "m1",
            "gold_is_training_outcome_only": True,
            "m3_is_training_outcome_only": True,
            "exp059_oracle_array_used_as_formal_target": False,
        },
        "feature_contract": {
            "ordered_features": list(runner.FEATURE_NAMES),
            "feature_count": 14,
            "scaler": "StandardScaler_fit_inside_outer_router_train",
            "m1_raw_logits_included": False,
            "m3_token_length_included": False,
        },
        "router": {
            "policies": list(runner.POLICY_ORDER),
            "deployable_policy_order": list(runner.DEPLOYABLE_POLICY_ORDER),
            "logistic_regression": {
                "penalty": "l2", "C": 1.0, "class_weight": "balanced",
                "solver": "liblinear", "max_iter": 1000, "random_state": 42,
            },
            "hyperparameter_search": False,
            "random_routing_repetitions": 100,
            "random_routing_seed": 20260817,
        },
        "call_rates": [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0],
        "gate": {
            "primary_policy": "logistic_router",
            "primary_nominal_call_rate": 0.15,
            "replication_pass_rule": "primary_policy_only",
            "maximum_hamming_loss_increase": 1e-12,
        },
        "risk_coverage": copy.deepcopy(runner.REPLICATION_RISK_COVERAGE),
        "bootstrap": {
            "unit": "duplicate_component",
            "repetitions": 2000,
            "seed": 20260817,
            "interval": "percentile_95",
        },
        "resources": dict(runner.REPLICATION_RESOURCE_CONTRACT),
        "claim_boundary": runner.REPLICATION_CLAIM_BOUNDARY,
        "commands": dict(runner.REPLICATION_COMMANDS),
    }
    config_path = root / BASE / "configs" / runner.REPLICATION_CONFIG_NAME
    write_json(config_path, config)
    return config_path, config


@contextmanager
def patched_roots(root: Path):
    script_dir = root / BASE
    with ExitStack() as stack:
        for module in (runner, verifier):
            stack.enter_context(mock.patch.object(module, "PROJECT_ROOT", root))
            stack.enter_context(mock.patch.object(module, "REPO_ROOT", root, create=True))
            stack.enter_context(mock.patch.object(module, "SCRIPT_DIR", script_dir))
            stack.enter_context(mock.patch.object(module, "OOF_EXPECTED_CHECK_COUNT", 1))
            stack.enter_context(mock.patch.object(module, "EXP059_EXPECTED_CHECK_COUNT", 1))
        yield


def successful_child(*args, **kwargs):
    return type("Result", (), {"returncode": 0, "stdout": "OK", "stderr": ""})()


class Exp060PreflightContractTests(unittest.TestCase):
    def test_frozen_inventory_constants_match_independent_verifier(self) -> None:
        self.assertEqual(runner.OOF_EXPECTED_CHECK_COUNT, 27034)
        self.assertEqual(verifier.OOF_EXPECTED_CHECK_COUNT, 27034)
        self.assertEqual(runner.EXP059_EXPECTED_CHECK_COUNT, 4683)
        self.assertEqual(verifier.EXP059_EXPECTED_CHECK_COUNT, 4683)
        self.assertEqual(runner.RUN_REQUIRED_CHECK_NAMES, verifier.RUN_REQUIRED_CHECK_NAMES)
        self.assertEqual(
            runner.BASE_FORMAL_SOURCE_SHA256,
            {
                "runner": "873d53f45d587918b7c1b466a93b8da0b397732baa072af1b43e50a16150dc65",
                "verifier": "920f6565bd378c8f7cfe415a78e505123336602fb228dad95771fcc14e471b15",
                "tests": "4e6572f996fecd81f8715f808f1fdd44a5ae4d351813e605936478a97e86ddff",
            },
        )
        self.assertEqual(runner.BASE_FORMAL_SOURCE_SHA256, verifier.BASE_FORMAL_SOURCE_SHA256)
        self.assertEqual(
            len(verifier.VERIFICATION_REQUIRED_CHECK_NAMES),
            len(set(verifier.VERIFICATION_REQUIRED_CHECK_NAMES)),
        )

    def test_feature_builder_has_only_pre_qwen_inputs(self) -> None:
        import inspect

        self.assertEqual(
            tuple(inspect.signature(runner.build_pre_qwen_features).parameters),
            ("m1_probabilities", "m1_thresholds", "character_lengths", "m1_token_lengths"),
        )

    def test_feature_builder_freezes_shape_and_order(self) -> None:
        probabilities = np.asarray(
            [[0.9, 0.2, 0.1, 0.4, 0.3, 0.05], [0.1, 0.8, 0.2, 0.3, 0.4, 0.6]]
        )
        matrix, names = runner.build_pre_qwen_features(
            probabilities, np.asarray([0.31, 0.32]), np.asarray([120, 240]),
            np.asarray([30, 60]),
        )
        self.assertEqual(matrix.shape, (2, 14))
        self.assertEqual(names, runner.FEATURE_NAMES)
        np.testing.assert_allclose(matrix[:, :6], probabilities)

    def test_router_target_uses_whole_vector_and_ties_choose_m1(self) -> None:
        gold = np.asarray([[1, 0], [1, 1], [0, 0]], dtype=np.uint8)
        m1 = np.asarray([[1, 0], [1, 0], [0, 1]], dtype=np.uint8)
        m3 = np.asarray([[1, 0], [1, 1], [1, 0]], dtype=np.uint8)
        np.testing.assert_array_equal(runner.build_router_target(m1, m3, gold), [0, 1, 0])

    def test_full_synthetic_preflight_and_independent_verifier_under_umask077(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patched_roots(root):
                config_path, _ = make_config(root)
                old_umask = os.umask(0o077)
                try:
                    with mock.patch.object(
                             runner.subprocess, "run", side_effect=successful_child
                         ) as child_run, \
                         mock.patch.object(
                             runner, "git_metadata",
                             return_value={"commit": "a" * 40, "dirty": False, "dirty_path_count": 0},
                         ), \
                         mock.patch.object(runner.np, "load", side_effect=AssertionError("np.load")), \
                         mock.patch.object(verifier.np, "load", side_effect=AssertionError("np.load")):
                        self.assertEqual(runner.run_preflight(config_path), 0)
                        self.assertEqual(verifier.verify(config_path), 0)
                        self.assertEqual(child_run.call_count, 6)
                        for call in child_run.call_args_list:
                            command = call.args[0]
                            self.assertEqual(command[1], "-B")
                            self.assertEqual(call.kwargs["timeout"], 60)
                            self.assertEqual(
                                call.kwargs["env"]["PYTHONDONTWRITEBYTECODE"], "1"
                            )
                finally:
                    os.umask(old_umask)
                preflight = root / runner.expected_replication_outputs()["public_attempt_dir"] / "router-preflight"
                for directory in (preflight, preflight / "frozen-sources"):
                    self.assertEqual(stat.S_IMODE(os.lstat(directory).st_mode), 0o755)
                for path in preflight.rglob("*"):
                    if path.is_file():
                        observed = os.lstat(path)
                        self.assertEqual(stat.S_IMODE(observed.st_mode), 0o644)
                        self.assertEqual(observed.st_nlink, 1)
                verification = json.loads((preflight / "verification.json").read_text())
                self.assertEqual(verification["status"], "Passed")
                self.assertEqual(set(verification), verifier.REPLICATION_VERIFICATION_KEYS)
                self.assertEqual(
                    [row["name"] for row in verification["checks"]],
                    list(verifier.VERIFICATION_REQUIRED_CHECK_NAMES),
                )
                self.assertEqual(
                    set(verification["verified_artifacts"]),
                    {"config", "run", "contract", "input", "upstreams", "frozen_sources", "formal_sources"},
                )
                self.assertEqual(
                    set(verification["verified_artifacts"]["formal_sources"]),
                    set(runner.FORMAL_IMPLEMENTATION_KEYS),
                )
                self.assertEqual(
                    set(verification["verified_artifacts"]["frozen_sources"]),
                    {"config", *runner.REPLICATION_IMPLEMENTATION_KEYS},
                )

    def test_identity_policy_and_router_calibration_mutations_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patched_roots(root):
                config_path, config = make_config(root)
                self.assertEqual(
                    set(config["implementation"]), runner.REPLICATION_IMPLEMENTATION_KEYS
                )
                wrong_identity = copy.deepcopy(config)
                wrong_identity["model_seed"] = 43
                wrong_policies = copy.deepcopy(config)
                wrong_policies["router"]["policies"] = list(runner.DEPLOYABLE_POLICY_ORDER)
                wrong_deployable = copy.deepcopy(config)
                wrong_deployable["router"]["deployable_policy_order"] = list(runner.POLICY_ORDER)
                wrong_governance = copy.deepcopy(config)
                wrong_governance["commands"]["preflight"] += " --unexpected"
                extra_data_key = copy.deepcopy(config)
                extra_data_key["data"]["unexpected"] = True
                missing_launcher = copy.deepcopy(config)
                missing_launcher["implementation"].pop("runner_launcher")
                extra_source = copy.deepcopy(config)
                extra_source["implementation"]["unexpected"] = config["implementation"]["protocol"]
                wrong_launcher_path = copy.deepcopy(config)
                wrong_launcher_path["implementation"]["runner_launcher"]["path"] = (
                    "experiments/stack-overflow-emotion-gold/oof-router/"
                    "run_exp060_router_seed44.py"
                )
                for mutated in (
                    wrong_identity,
                    wrong_policies,
                    wrong_deployable,
                    wrong_governance,
                    extra_data_key,
                    missing_launcher,
                    extra_source,
                    wrong_launcher_path,
                ):
                    for validator in (
                        runner.validate_replication_config,
                        verifier.validate_replication_config,
                    ):
                        with self.assertRaises((ValueError, PermissionError)):
                            validator(config_path, mutated)
                parameter_path = root / config["prerequisites"]["exp059_calibration_parameters"]["path"]
                parameter = json.loads(parameter_path.read_text())
                parameter["router_replication_calibration"]["temperature"] = 1.18
                write_json(parameter_path, parameter)
                config["prerequisites"]["exp059_calibration_parameters"] = file_record(root, parameter_path)
                for validator in (
                    runner.validate_replication_config,
                    verifier.validate_replication_config,
                ):
                    with self.assertRaises(ValueError):
                        validator(config_path, config)

    def test_upstream_exact_schema_and_check_inventory_fail_closed(self) -> None:
        for target in ("oof_verification", "exp059_run"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with patched_roots(root):
                    config_path, config = make_config(root)
                    for validator in (
                        runner.validate_replication_config,
                        verifier.validate_replication_config,
                    ):
                        validator(config_path, config)
                    target_path = root / config["prerequisites"][target]["path"]
                    payload = json.loads(target_path.read_text())
                    if target == "oof_verification":
                        payload["checks"] = []
                        payload["check_count"] = 0
                        payload["passed_count"] = 0
                    else:
                        payload["unexpected"] = True
                    write_json(target_path, payload)
                    config["prerequisites"][target] = file_record(root, target_path)
                    for validator in (
                        runner.validate_replication_config,
                        verifier.validate_replication_config,
                    ):
                        with self.assertRaises(ValueError):
                            validator(config_path, config)
        duplicate = [
            {"name": "duplicate", "passed": True, "detail": None},
            {"name": "duplicate", "passed": True, "detail": None},
        ]
        payload = {"checks": duplicate, "passed_count": 2, "failed_count": 0}
        self.assertFalse(
            runner._passed_checks_exact(payload, has_check_count=False, expected_count=2)
        )
        self.assertFalse(
            verifier._passed_checks_exact(payload, has_check_count=False, expected_count=2)
        )

    def test_frozen_base_hash_drift_is_rejected_by_both_validators(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patched_roots(root):
                config_path, config = make_config(root)
                base_runner = root / config["implementation"]["runner"]["path"]
                base_runner.write_text(base_runner.read_text() + "\n# drift\n", encoding="utf-8")
                os.chmod(base_runner, 0o644)
                config["implementation"]["runner"] = file_record(root, base_runner)
                for validator in (
                    runner.validate_replication_config,
                    verifier.validate_replication_config,
                ):
                    with self.assertRaises(ValueError):
                        validator(config_path, config)

    def test_typed_resources_runtime_and_identity_calibration_fail_closed(self) -> None:
        valid_resources = {
            "wall_seconds": 1.0,
            "peak_process_rss_gb": 0.1,
            "api_cost_usd": 0,
            "gpu_cost_usd": 0,
            "model_forward_runs": 0,
        }
        for field, bad in (
            ("api_cost_usd", False),
            ("wall_seconds", float("nan")),
            ("peak_process_rss_gb", -0.1),
        ):
            value = dict(valid_resources)
            value[field] = bad
            self.assertFalse(
                runner._runtime_resource_record_exact(
                    value, wall_budget=300.0, memory_budget=2.0
                )
            )
            self.assertFalse(
                verifier._runtime_resource_record_exact(
                    value, wall_budget=300.0, memory_budget=2.0
                )
            )
        self.assertFalse(
            runner._replication_calibration_exact(
                {**runner.REPLICATION_CALIBRATION_CONTRACT, "temperature": True}
            )
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patched_roots(root):
                config_path, config = make_config(root)
                bad_cost = copy.deepcopy(config)
                bad_cost["resources"]["api_cost_usd"] = False
                fake_runtime = copy.deepcopy(config)
                fake_runtime["runtime"]["python_executable"] = "/fake/python"
                float_seed = copy.deepcopy(config)
                float_seed["model_seed"] = 44.0
                for mutated in (bad_cost, fake_runtime, float_seed):
                    for validator in (
                        runner.validate_replication_config,
                        verifier.validate_replication_config,
                    ):
                        with self.assertRaises((ValueError, PermissionError)):
                            validator(config_path, mutated)
                exp059_run_path = root / config["prerequisites"]["exp059_run"]["path"]
                exp059_run = json.loads(exp059_run_path.read_text())
                exp059_run["router_replication_calibration"]["temperature"] = True
                write_json(exp059_run_path, exp059_run)
                config["prerequisites"]["exp059_run"] = file_record(root, exp059_run_path)
                for validator in (
                    runner.validate_replication_config,
                    verifier.validate_replication_config,
                ):
                    with self.assertRaises(ValueError):
                        validator(config_path, config)

    def test_peak_rss_uses_normalized_max_of_self_and_children(self) -> None:
        def usage(kind: int):
            return SimpleNamespace(
                ru_maxrss=100_000_000 if kind == resource.RUSAGE_SELF else 3_000_000_000
            )

        import resource

        with mock.patch.object(runner.platform, "system", return_value="Darwin"), \
             mock.patch.object(runner.resource, "getrusage", side_effect=usage):
            observed = runner.peak_rss_gb()
            self.assertEqual(observed, 3.0)
            self.assertEqual(verifier.peak_rss_gb(), 3.0)
            self.assertFalse(
                runner._runtime_resource_record_exact(
                    {
                        "wall_seconds": 1.0,
                        "peak_process_rss_gb": observed,
                        "api_cost_usd": 0,
                        "gpu_cost_usd": 0,
                        "model_forward_runs": 0,
                    },
                    wall_budget=300.0,
                    memory_budget=2.0,
                )
            )

    def test_child_test_timeout_no_bytecode_and_pyc_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patched_roots(root):
                _, config = make_config(root)
                test_path = root / config["implementation"]["preflight_tests"]["path"]
                with mock.patch.object(
                    runner.subprocess, "run", side_effect=successful_child
                ) as child_run:
                    result = runner._run_child_test(test_path)
                self.assertTrue(runner._child_test_result_exact(result, test_path))
                command = child_run.call_args.args[0]
                self.assertEqual(command, [os.path.realpath(sys.executable), "-B", str(test_path)])
                self.assertEqual(child_run.call_args.kwargs["timeout"], 60)
                self.assertEqual(
                    child_run.call_args.kwargs["env"]["PYTHONDONTWRITEBYTECODE"], "1"
                )

                def create_pyc(*args, **kwargs):
                    pyc = root / BASE / "__pycache__/forbidden.pyc"
                    pyc.parent.mkdir(parents=True, exist_ok=True)
                    pyc.write_bytes(b"pyc")
                    os.chmod(pyc, 0o644)
                    return successful_child(*args, **kwargs)

                with mock.patch.object(runner.subprocess, "run", side_effect=create_pyc), \
                     self.assertRaisesRegex(RuntimeError, "bytecode"):
                    runner._run_child_test(test_path)
                with mock.patch.object(runner, "CHILD_TEST_TIMEOUT_SECONDS", 301), \
                     mock.patch.object(runner.subprocess, "run") as forbidden, \
                     self.assertRaisesRegex(ValueError, "timeout"):
                    runner._run_child_test(test_path)
                forbidden.assert_not_called()

    def test_verifier_reruns_child_tests_and_rejects_independent_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patched_roots(root):
                config_path, _ = make_config(root)
                with mock.patch.object(
                    runner.subprocess, "run", side_effect=successful_child
                ), mock.patch.object(
                    runner,
                    "git_metadata",
                    return_value={"commit": "a" * 40, "dirty": False, "dirty_path_count": 0},
                ):
                    self.assertEqual(runner.run_preflight(config_path), 0)

                failed = type(
                    "Result", (), {"returncode": 1, "stdout": "", "stderr": "independent"}
                )()
                with mock.patch.object(
                    verifier.subprocess, "run", return_value=failed
                ) as independent, self.assertRaisesRegex(RuntimeError, "formal_source_contract"):
                    verifier.verify(config_path)
                self.assertEqual(independent.call_count, 3)
                preflight = root / runner.expected_replication_outputs()["public_attempt_dir"] / "router-preflight"
                self.assertFalse(os.path.lexists(preflight / "verification.json"))
                self.assertFalse(os.path.lexists(preflight / "VERIFICATION-SUMMARY.md"))

    def test_secure_read_rechecks_opened_mode_and_ctime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "record.json"
            write_json(path, {"ok": True})
            observed = os.stat(path)

            def metadata(*, mode: int, ctime_ns: int):
                return SimpleNamespace(
                    st_mode=mode,
                    st_nlink=observed.st_nlink,
                    st_dev=observed.st_dev,
                    st_ino=observed.st_ino,
                    st_size=observed.st_size,
                    st_mtime_ns=observed.st_mtime_ns,
                    st_ctime_ns=ctime_ns,
                )

            bad_mode = metadata(mode=stat.S_IFREG | 0o600, ctime_ns=observed.st_ctime_ns)
            for module in (runner, verifier):
                with mock.patch.object(module.os, "fstat", return_value=bad_mode), \
                     self.assertRaisesRegex(ValueError, "mode"):
                    module._secure_read_bytes(path, mode=0o644)
            opened = metadata(mode=stat.S_IFREG | 0o644, ctime_ns=observed.st_ctime_ns)
            changed = metadata(mode=stat.S_IFREG | 0o644, ctime_ns=observed.st_ctime_ns + 1)
            with mock.patch.object(runner.os, "fstat", side_effect=[opened, changed]), \
                 self.assertRaisesRegex(ValueError, "changed"):
                runner._secure_read_bytes(path, mode=0o644)

    def test_npz_extra_member_symlink_hardlink_and_rerun_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patched_roots(root):
                config_path, config = make_config(root)
                paired = root / config["input"]["paired_oof"]["path"]
                with zipfile.ZipFile(paired, "a") as archive:
                    archive.writestr("extra.npy", b"forbidden")
                with self.assertRaises(ValueError):
                    runner.npz_header_schema_strict(paired)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patched_roots(root):
                config_path, config = make_config(root)
                hardlink = config_path.with_suffix(".hardlink")
                os.link(config_path, hardlink)
                with self.assertRaises(ValueError):
                    runner.validate_replication_config(config_path, config)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patched_roots(root):
                config_path, _ = make_config(root)
                preflight = root / runner.expected_replication_outputs()["public_attempt_dir"] / "router-preflight"
                os.symlink("missing", preflight)
                with self.assertRaises((FileExistsError, ValueError)):
                    runner.run_preflight(config_path)

    def test_partial_write_is_terminal_and_retry_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patched_roots(root):
                config_path, _ = make_config(root)
                original = runner._create_bytes_once
                calls = 0

                def fail_second(path, payload, mode=0o644):
                    nonlocal calls
                    calls += 1
                    if calls == 2:
                        raise OSError("synthetic partial write")
                    return original(path, payload, mode)

                with mock.patch.object(runner.subprocess, "run", side_effect=successful_child), \
                     mock.patch.object(
                         runner, "git_metadata",
                         return_value={"commit": "a" * 40, "dirty": False, "dirty_path_count": 0},
                     ), \
                     mock.patch.object(runner, "_create_bytes_once", side_effect=fail_second):
                    with self.assertRaises(OSError):
                        runner.run_preflight(config_path)
                with self.assertRaises(FileExistsError):
                    runner.run_preflight(config_path)

    def test_legacy_archive_is_read_only_after_live_source_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patched_roots(root):
                run_dir = root / "legacy-preflight"
                run_dir.mkdir()
                write_json(run_dir / "run.json", {"status": "Completed"})
                write_json(run_dir / "preflight-contract.json", {})
                write_json(run_dir / "verification.json", {"status": "Passed"})
                (run_dir / "VERIFICATION-SUMMARY.md").write_text("Passed\n")
                config_path = root / "legacy.json"
                write_json(
                    config_path,
                    {
                        "schema_version": "exp-060-router-preflight-config-v1",
                        "experiment_id": "EXP-060",
                        "rq_id": "RQ-S3",
                        "data": {"label_order": list(runner.LABEL_ORDER)},
                        "outputs": {
                            "preflight_run_dir": str(run_dir.relative_to(root)),
                            "formal_run_dir": "formal",
                            "formal_private_dir": "private",
                        },
                    },
                )
                with self.assertRaises(PermissionError):
                    runner.run_preflight(config_path)
                self.assertEqual(verifier.verify(config_path), 0)

    def test_verifier_does_not_import_or_execute_runner(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = []
        forbidden_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec", "compile", "__import__"}:
                    forbidden_calls.append(node.func.id)
                elif isinstance(node.func, ast.Attribute) and node.func.attr in {
                    "exec_module", "import_module", "run_module", "run_path"
                }:
                    forbidden_calls.append(node.func.attr)
        self.assertFalse(any(name.endswith("run_exp060_router_preflight") for name in imports))
        self.assertEqual(forbidden_calls, [])


if __name__ == "__main__":
    unittest.main()
