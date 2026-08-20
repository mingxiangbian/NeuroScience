from __future__ import annotations

import ast
from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest

import numpy as np


try:
    import scipy.optimize  # noqa: F401
except ModuleNotFoundError:
    scipy_module = types.ModuleType("scipy")
    optimize_module = types.ModuleType("scipy.optimize")

    def unavailable_minimize_scalar(*args, **kwargs):
        raise RuntimeError("SciPy is intentionally unavailable in synthetic contract tests")

    optimize_module.minimize_scalar = unavailable_minimize_scalar
    scipy_module.optimize = optimize_module
    sys.modules["scipy"] = scipy_module
    sys.modules["scipy.optimize"] = optimize_module


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp059_calibration.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp059_calibration.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_module("exp059_runner_under_test", RUNNER_PATH)
verifier = load_module("exp059_verifier_under_test", VERIFIER_PATH)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def record(root: Path, path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "path": str(path.relative_to(root)),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


@contextmanager
def synthetic_project():
    with tempfile.TemporaryDirectory(prefix="exp059-contract-") as temporary:
        root = Path(temporary)
        old_runner_root = runner.PROJECT_ROOT
        old_verifier_root = verifier.PROJECT_ROOT
        runner.PROJECT_ROOT = root
        verifier.PROJECT_ROOT = root
        try:
            yield root
        finally:
            runner.PROJECT_ROOT = old_runner_root
            verifier.PROJECT_ROOT = old_verifier_root


def synthetic_config(
    root: Path,
    parent: str = "EXP-061",
    attempt_id: str = "attempt-1",
    *,
    formal: bool = False,
) -> tuple[Path, dict[str, object]]:
    registration = runner.REPLICATIONS[parent]
    model_seed = registration["model_seed"]
    run_id = registration["run_id"]
    public_namespace = Path(
        f"experiments/stack-overflow-emotion-gold/oof-router/runs/{run_id}"
    )
    private_namespace = Path(
        f"experiments/stack-overflow-emotion-gold/oof-router/private/{run_id}"
    )
    outputs = {
        "public_namespace": str(public_namespace),
        "public_attempt_dir": str(public_namespace / attempt_id),
        "private_namespace": str(private_namespace),
        "private_attempt_dir": str(private_namespace / attempt_id),
        "selection_record": str(public_namespace / "selected-attempt.json"),
    }
    public_attempt = root / public_namespace / attempt_id
    private_attempt = root / private_namespace / attempt_id
    public_attempt.mkdir(parents=True)
    private_attempt.mkdir(parents=True)

    paired_path = private_attempt / "paired-oof.npz"
    paired_path.write_bytes(b"synthetic paired OOF placeholder; no array values")
    paired_record = record(root, paired_path)
    seed_contract = runner.expected_seed_contract(model_seed)
    oof_identity = {
        "experiment_id": parent,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "model_seed": model_seed,
        "seed_contract": seed_contract,
    }
    oof_config_path = root / "synthetic-configs" / f"{parent.lower()}-{attempt_id}-oof.json"
    oof_stage = "paired-m1-m3-oof-production"
    oof_config = {
        "schema_version": "exp-oof-production-config-v2",
        "experiment_id": parent,
        "rq_id": "RQ-S3",
        "tier": "Major",
        "stage": oof_stage,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "authorization": {},
        "execution": {},
        "seed_contract": seed_contract,
        "data": {"train": paired_record},
        "implementation": {},
        "prerequisites": {"fold_manifest": paired_record},
        "outputs": outputs,
        "initialization": {},
        "m1": {},
        "m3": {},
        "resources": copy.deepcopy(runner.OOF_FROZEN_RESOURCES),
    }
    write_json(oof_config_path, oof_config)
    oof_config_record = record(root, oof_config_path)
    cli_identity = {
        "model_seed": model_seed,
        "run_id": run_id,
        "output_root": outputs["public_attempt_dir"],
        "expected_fold_manifest_sha256": paired_record["sha256"],
        "expected_data_manifest_sha256": paired_record["sha256"],
    }
    seed_digest = runner.canonical_digest(seed_contract)
    oof_summary_path = public_attempt / "paired-oof-summary.json"
    write_json(oof_summary_path, {"status": "CompletedAwaitingVerification"})
    oof_run_path = public_attempt / "run.json"
    write_json(
        oof_run_path,
        {
            "schema_version": "exp-oof-production-run-v2",
            **oof_identity,
            "stage": oof_stage,
            "config": oof_config_record,
            "cli_identity": cli_identity,
            "seed_contract_sha256": seed_digest,
            "status": "CompletedAwaitingVerification",
            "artifacts": {
                "paired_oof_private": paired_record,
                "paired_oof_summary": record(root, oof_summary_path),
            },
        },
    )
    fold_runs = {family: {} for family in ("m1", "m3")}
    fold_verifications = {family: {} for family in ("m1", "m3")}
    for family in ("m1", "m3"):
        for fold_id in range(5):
            fold_dir = public_attempt / f"fold-{fold_id}" / family
            fold_run = fold_dir / "run.json"
            fold_verification = fold_dir / "verification.json"
            write_json(fold_run, {"family": family, "fold_id": fold_id})
            write_json(fold_verification, {"status": "Passed"})
            fold_runs[family][str(fold_id)] = record(root, fold_run)
            fold_verifications[family][str(fold_id)] = record(root, fold_verification)
    oof_checks = [
        {"name": name, "passed": True, "detail": None}
        for name in sorted(runner.OOF_FINAL_REQUIRED_CHECKS)
    ]
    oof_verification_path = public_attempt / "verification.json"
    write_json(
        oof_verification_path,
        {
            "schema_version": "exp-oof-final-verification-v2",
            **oof_identity,
            "stage": oof_stage,
            "scope": "final",
            "status": "Passed",
            "verified_at_utc": "2026-08-17T00:00:00+00:00",
            "check_count": len(oof_checks),
            "passed_count": len(oof_checks),
            "failed_count": 0,
            "checks": oof_checks,
            "config": oof_config_record,
            "cli_identity": cli_identity,
            "independence": {
                "runner_imported": False,
                "model_libraries_imported": False,
                "all_fold_tables_recomputed": True,
                "paired_table_recomputed": True,
            },
            "verified_artifacts": {
                "config": oof_config_record,
                "run": record(root, oof_run_path),
                "summary": record(root, oof_summary_path),
                "paired_oof_private": paired_record,
                "fold_runs": fold_runs,
                "fold_verifications": fold_verifications,
            },
            "claim_boundary": "Verified paired train OOF logits only; calibration and routing remain separate experiments.",
        },
    )
    oof_completion_path = public_attempt / "oof-complete.json"
    write_json(
        oof_completion_path,
        {
            **oof_identity,
            "schema_version": "exp-oof-completion-v2",
            "stage": oof_stage,
            "seed_contract_sha256": seed_digest,
            "status": "Complete",
            "completed_at_utc": "2026-08-17T00:00:01+00:00",
            "config": oof_config_record,
            "cli_identity": cli_identity,
            "artifacts": {
                "run": record(root, oof_run_path),
                "summary": record(root, oof_summary_path),
                "final_verification": record(root, oof_verification_path),
                "paired_oof_private": paired_record,
            },
            "next_gate": "Seed-specific EXP-059 and identity-nested EXP-060 must pass before namespace selection.",
            "claim_boundary": "Completes one verified train-only paired OOF stage; this is not final pipeline selection.",
        },
    )

    implementation = {}
    for name, relative in runner.CANONICAL_IMPLEMENTATION_PATHS.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"synthetic {name}\n", encoding="utf-8")
        implementation[name] = record(root, path)

    prerequisites = {
        "oof_run": record(root, oof_run_path),
        "oof_verification": record(root, oof_verification_path),
        "oof_completion": record(root, oof_completion_path),
    }
    exp059_identity = {
        "experiment_id": "EXP-059",
        "replication_parent_experiment_id": parent,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "model_seed": model_seed,
        "seed_contract": seed_contract,
    }
    config = {
        "schema_version": runner.CONFIG_V2_SCHEMA,
        **exp059_identity,
        "rq_id": "RQ-S3",
        "stage": "calibration-selective-preflight",
        "tier": "Major",
        "implementation": implementation,
        "prerequisites": prerequisites,
        "input": {"paired_oof": paired_record},
        "outputs": outputs,
        "data": {
            "protocol_id": "DATA-SO-TASK-V1",
            "split": "train-oof",
            "rows": 3360,
            "label_order": list(runner.LABEL_ORDER),
        },
        "cross_fitting": {
            "fold_ids": [0, 1, 2, 3, 4],
            "meta_train_folds": 4,
            "heldout_folds": 1,
            "reuse_exp058_duplicate_component_partition": True,
        },
        "calibration": {
            "method": "one_scalar_temperature_per_family",
            "temperature_bounds": [0.05, 20.0],
            "optimizer_parameter": "log_temperature",
            "optimizer_tolerance": 1e-12,
            "optimizer_max_iterations": 1000,
            "ece_bins": 15,
            "minimum_nll_improvement": 1e-6,
            "maximum_brier_worsening": 1e-6,
        },
        "thresholds": {
            "scope": "one_global_threshold_per_family_pipeline_and_meta_fold",
            "grid": [round(0.05 + index * 0.01, 2) for index in range(91)],
            "tie_tolerance": 1e-12,
            "selection_order": [
                "highest_macro_f1",
                "lowest_hamming_loss",
                "closest_to_0_5",
                "lower_threshold",
            ],
        },
        "selective_prediction": {
            "methods": ["mean_entropy", "max_entropy", "margin"],
            "coverages": [1.0, 0.95, 0.9, 0.8, 0.7, 0.6],
            "random_repetitions": 100,
            "random_seed": 20260817,
            "gate_minimum_coverage": 0.8,
            "gate_hamming_relative_reduction": 0.2,
            "gate_max_five_label_macro_drop": 0.01,
            "gate_min_non_surprise_retention": 0.5,
        },
        "oracle": {
            "selection_unit": "whole_six_bit_vector",
            "tie_policy": "m1",
            "minimum_macro_gain": 0.01,
        },
        "bootstrap": {
            "unit": "duplicate_component",
            "repetitions": 2000,
            "seed": 20260817,
            "interval": "percentile_95",
        },
        "authorization": {
            "preflight": True,
            "formal_analysis": False,
            "validation_access": False,
            "test_access": False,
            "model_loading_or_forward": False,
            "router_training": False,
        },
        "resources": {
            "formal_wall_seconds": 1800,
            "verification_wall_seconds": 1800,
            "peak_memory_gb": 4.0,
            "api_cost_usd": 0,
        },
    }
    if formal:
        preflight_dir = public_attempt / "calibration-preflight"
        preflight_run = preflight_dir / "run.json"
        preflight_verification = preflight_dir / "verification.json"
        preflight_config = (
            root
            / "synthetic-configs"
            / f"{parent.lower()}-{attempt_id}-preflight.json"
        )
        write_json(preflight_config, config)
        preflight_config_record = record(root, preflight_config)
        frozen_dir = preflight_dir / "frozen-sources"
        frozen_dir.mkdir(parents=True)
        (frozen_dir / "config.json").write_bytes(preflight_config.read_bytes())
        frozen_records = {"config": record(root, frozen_dir / "config.json")}
        for name, source_record in implementation.items():
            source_path = root / source_record["path"]
            frozen_path = frozen_dir / source_path.name
            frozen_path.write_bytes(source_path.read_bytes())
            frozen_records[name] = record(root, frozen_path)
        write_json(
            preflight_run,
            {
                "schema_version": "exp-059-preflight-run-v2",
                **exp059_identity,
                "rq_id": "RQ-S3",
                "status": "CompletedAwaitingVerification",
                "input": paired_record,
                "config": preflight_config_record,
                "frozen_sources": frozen_records,
            },
        )
        preflight_checks = [
            {"name": name, "passed": True, "detail": None}
            for name in sorted(verifier.PREFLIGHT_VERIFICATION_REQUIRED_CHECKS)
        ]
        preflight_verification_value = {
            "schema_version": "exp-059-verification-v2",
            **exp059_identity,
            "rq_id": "RQ-S3",
            "scope": "preflight",
            "status": "Passed",
            "verified_at_utc": "2026-08-17T00:00:02+00:00",
            "passed_count": len(preflight_checks),
            "failed_count": 0,
            "checks": preflight_checks,
            "resources": {
                "wall_seconds": 0.1,
                "peak_process_rss_gb": 0.1,
                "api_cost_usd": 0,
            },
            "config": preflight_config_record,
            "verified_artifacts": {
                "config": preflight_config_record,
                "run": record(root, preflight_run),
                "paired_oof": paired_record,
            },
        }
        write_json(preflight_verification, preflight_verification_value)
        (preflight_dir / "VERIFICATION-SUMMARY.md").write_text(
            verifier.render_summary(preflight_verification_value), encoding="utf-8"
        )
        config["prerequisites"].update(
            {
                "preflight_run": record(root, preflight_run),
                "preflight_verification": record(root, preflight_verification),
            }
        )
        config["stage"] = "cross-fitted-calibration-selective-prediction"
        config["authorization"]["formal_analysis"] = True
    config_path = root / "synthetic-configs" / f"{parent.lower()}-{attempt_id}.json"
    write_json(config_path, config)
    return config_path, config


def populate_synthetic_final_bundle(
    root: Path,
    config_path: Path,
    config: dict[str, object],
) -> tuple[dict[str, Path], dict[str, object]]:
    paths = verifier.output_paths(config)
    run_dir = paths["public_calibration"]
    private_dir = paths["private_calibration"]
    frozen_dir = run_dir / "frozen-sources"
    frozen_dir.mkdir(parents=True)
    private_dir.mkdir(parents=True, mode=0o700)
    private_path = private_dir / "cross-fitted-calibration.npz"
    private_path.write_bytes(b"synthetic private calibration")
    private_path.chmod(0o600)
    private_dir.chmod(0o700)

    (frozen_dir / "config.json").write_bytes(config_path.read_bytes())
    for source in config["implementation"].values():
        source_path = root / source["path"]
        (frozen_dir / source_path.name).write_bytes(source_path.read_bytes())

    router_contract = {
        "calibrator": "identity",
        "temperature": 1.0,
        "probability_source": "direct_sigmoid_of_raw_oof_logits",
        "role": "frozen_exp060_replication_only",
    }
    write_json(
        run_dir / "calibration-parameters.json",
        {
            **verifier.identity_provenance(config),
            "router_replication_calibration": router_contract,
            "families": {},
        },
    )
    for filename in (
        "abstention-gates.json",
        "bootstrap.json",
        "calibration-metrics.json",
        "classification-metrics.json",
        "oracle-summary.json",
    ):
        write_json(run_dir / filename, {})
    for filename in (
        "REPORT.md",
        "reliability-bins.csv",
        "risk-coverage.csv",
        "label-retention.csv",
        "random-rejection.csv",
        "reliability-diagram.png",
        "risk-coverage-curve.png",
    ):
        (run_dir / filename).write_bytes(f"synthetic {filename}\n".encode())

    config_record = verifier.artifact(config_path)
    public_records = verifier.expected_public_output_records(run_dir)
    frozen_records = verifier.expected_frozen_source_records(
        run_dir, config, config_record
    )
    input_path = root / config["input"]["paired_oof"]["path"]
    run_path = run_dir / "run.json"
    write_json(
        run_path,
        {
            "schema_version": "exp-059-formal-run-v2",
            **verifier.identity_provenance(config),
            "rq_id": "RQ-S3",
            "status": "CompletedAwaitingVerification",
            "config": config_record,
            "input_before": verifier.artifact(input_path),
            "input_sha256_after": verifier.sha256(input_path),
            "private_output": verifier.artifact(private_path),
            "public_outputs": public_records,
            "frozen_sources": frozen_records,
            "model_loading_or_forward_performed": False,
            "router_training_performed": False,
            "temperature_adoption_role": "diagnostic_only",
            "router_replication_calibration": router_contract,
            "split_access": {
                "accessed_splits": ["train-oof"],
                "validation_accessed": False,
                "test_inputs_accessed": False,
                "test_labels_accessed": False,
            },
        },
    )
    checks = [
        {"name": name, "passed": True, "detail": None}
        for name in sorted(verifier.FINAL_COMPLETION_REQUIRED_CHECKS)
    ]
    verification = {
        "schema_version": "exp-059-verification-v2",
        **verifier.identity_provenance(config),
        "rq_id": "RQ-S3",
        "scope": "final",
        "status": "Passed",
        "verified_at_utc": "2026-08-17T00:00:00+00:00",
        "passed_count": len(checks),
        "failed_count": 0,
        "checks": checks,
        "resources": {
            "wall_seconds": 1.0,
            "peak_process_rss_gb": 0.1,
            "api_cost_usd": 0,
        },
        "config": config_record,
        "verified_artifacts": {
            "config": config_record,
            "run": verifier.artifact(run_path),
            "calibration_parameters": verifier.artifact(
                run_dir / "calibration-parameters.json"
            ),
            "paired_oof": verifier.artifact(input_path),
            "private_output": verifier.artifact(private_path),
            "public_outputs": public_records,
            "frozen_sources": frozen_records,
        },
    }
    write_json(run_dir / "verification.json", verification)
    (run_dir / "VERIFICATION-SUMMARY.md").write_text(
        verifier.render_summary(verification), encoding="utf-8"
    )
    return paths, verification


class Exp059ContractTests(unittest.TestCase):
    def test_runner_and_verifier_consumer_contracts_match(self) -> None:
        self.assertEqual(runner.OOF_FROZEN_RESOURCES, verifier.OOF_FROZEN_RESOURCES)
        self.assertEqual(runner.OOF_CONFIG_KEYS, verifier.OOF_CONFIG_KEYS)
        self.assertEqual(
            runner.OOF_FINAL_REQUIRED_CHECKS,
            verifier.OOF_FINAL_REQUIRED_CHECKS,
        )
        self.assertEqual(runner.PREFLIGHT_CORE_KEYS, verifier.PREFLIGHT_CORE_KEYS)
        self.assertEqual(
            runner.PREFLIGHT_VERIFICATION_REQUIRED_CHECKS,
            verifier.PREFLIGHT_VERIFICATION_REQUIRED_CHECKS,
        )

    def test_threshold_tie_prefers_closest_to_half_then_lower(self) -> None:
        probabilities = np.asarray([[0.0], [0.0]], dtype=np.float64)
        gold = np.asarray([[0], [0]], dtype=np.uint8)

        def one_label_metrics(y, prediction):
            return {"macro_f1": 0.0, "hamming_loss": float(np.mean(y != prediction))}

        original = runner.classification_metrics
        try:
            runner.classification_metrics = one_label_metrics
            selected = runner.select_threshold(probabilities, gold, [0.4, 0.6])
        finally:
            runner.classification_metrics = original
        self.assertEqual(selected["threshold"], 0.4)

    def test_acceptance_mask_rounds_each_fold_independently(self) -> None:
        scores = np.asarray([0.4, 0.1, 0.3, 0.2, 0.8, 0.5, 0.7, 0.6])
        folds = np.asarray([0, 0, 0, 0, 1, 1, 1, 1], dtype=np.int8)
        sample_ids = np.asarray([f"s{index}" for index in range(8)])
        mask = runner.acceptance_mask(scores, folds, sample_ids, 0.5)
        self.assertEqual(int(np.sum(mask[folds == 0])), 2)
        self.assertEqual(int(np.sum(mask[folds == 1])), 2)

    def test_equal_frequency_bins_cover_every_bit_once(self) -> None:
        probabilities = np.linspace(0.01, 0.99, 30).reshape(10, 3)
        gold = (probabilities >= 0.5).astype(np.uint8)
        _, rows = runner.equal_frequency_bins(probabilities, gold, 7)
        self.assertEqual(len(rows), 7)
        self.assertEqual(sum(row["count"] for row in rows), 30)

    def test_seed_43_and_44_contracts_and_attempt_paths(self) -> None:
        with synthetic_project() as root:
            for parent, seed in (("EXP-061", 43), ("EXP-062", 44)):
                _, config = synthetic_config(root, parent, f"attempt-{seed - 42}")
                runner.validate_v2_config(config)
                verifier.validate_v2_config(config)
                self.assertEqual(config["model_seed"], seed)
                self.assertEqual(config["seed_contract"]["m3_lora_seed"], seed + 100_000)
                paths = runner.output_paths(config)
                self.assertEqual(paths["preflight"].name, "calibration-preflight")
                self.assertEqual(paths["public_calibration"].name, "calibration")
                self.assertEqual(paths["private_calibration"].name, "calibration")
                self.assertEqual(paths["completion"].name, "calibration-complete.json")

    def test_synthetic_v2_config_loads_in_runner_and_independent_verifier(self) -> None:
        with synthetic_project() as root:
            config_path, config = synthetic_config(root)
            self.assertEqual(runner.load_config(config_path)["model_seed"], 43)
            self.assertEqual(verifier.load_config(config_path)["model_seed"], 43)
            runner.validate_oof_prerequisites(config)
            self.assertEqual(verifier.oof_prerequisites(config)["completion"]["status"], "Complete")
            formal_path, _ = synthetic_config(root, attempt_id="attempt-2", formal=True)
            self.assertTrue(runner.load_config(formal_path)["authorization"]["formal_analysis"])
            self.assertTrue(verifier.load_config(formal_path)["authorization"]["formal_analysis"])

    def test_legacy_seed_42_source_drift_is_archive_only(self) -> None:
        with synthetic_project() as root:
            archive_relative = Path("experiments/legacy-exp059-seed42")
            archive = root / archive_relative
            frozen = archive / "frozen-sources"
            frozen.mkdir(parents=True)
            live_source = root / "legacy-source.py"
            live_source.write_text("sealed source\n", encoding="utf-8")
            live_record = record(root, live_source)
            config = {
                "schema_version": "exp-059-formal-config-v1",
                "experiment_id": "EXP-059",
                "rq_id": "RQ-S3",
                "implementation": {"runner": live_record},
                "outputs": {
                    "preflight_run_dir": "experiments/legacy-exp059-preflight",
                    "public_run_dir": str(archive_relative),
                    "private_run_dir": "private/legacy-exp059-seed42",
                },
                "data": {"label_order": list(runner.LABEL_ORDER)},
                "authorization": {"validation_access": False, "test_access": False},
            }
            config_path = root / "legacy-config.json"
            write_json(config_path, config)
            (frozen / "config.json").write_bytes(config_path.read_bytes())
            (frozen / "legacy-source.py").write_bytes(live_source.read_bytes())
            frozen_records = {
                "config": record(root, frozen / "config.json"),
                "runner": record(root, frozen / "legacy-source.py"),
            }
            write_json(
                archive / "run.json",
                {
                    "experiment_id": "EXP-059",
                    "status": "CompletedAwaitingVerification",
                    "frozen_sources": frozen_records,
                },
            )
            write_json(
                archive / "verification.json",
                {"experiment_id": "EXP-059", "status": "Passed", "failed_count": 0},
            )
            live_source.write_text("drifted live source\n", encoding="utf-8")
            self.assertTrue(runner.load_config(config_path)["_archive_only"])
            self.assertTrue(verifier.load_config(config_path)["_archive_only"])

    def test_v2_rejects_seed_attempt_input_and_output_drift(self) -> None:
        with synthetic_project() as root:
            _, config = synthetic_config(root)
            mutations = []
            wrong_seed = copy.deepcopy(config)
            wrong_seed["model_seed"] = 44
            mutations.append(wrong_seed)
            wrong_attempt = copy.deepcopy(config)
            wrong_attempt["attempt_id"] = "attempt-0"
            mutations.append(wrong_attempt)
            wrong_input = copy.deepcopy(config)
            wrong_input["input"]["paired_oof"]["path"] = "validation/paired-oof.npz"
            mutations.append(wrong_input)
            wrong_output = copy.deepcopy(config)
            wrong_output["outputs"]["public_attempt_dir"] += "-redirected"
            mutations.append(wrong_output)
            for mutated in mutations:
                with self.assertRaises(ValueError):
                    runner.validate_v2_config(mutated)
                with self.assertRaises(ValueError):
                    verifier.validate_v2_config(mutated)

    def test_v2_rejects_algorithm_random_and_bootstrap_drift(self) -> None:
        with synthetic_project() as root:
            _, config = synthetic_config(root)
            for section, key, value in (
                ("bootstrap", "repetitions", 1999),
                ("bootstrap", "seed", 44),
                ("selective_prediction", "random_seed", 44),
                ("calibration", "optimizer_max_iterations", 999),
                ("thresholds", "grid", [0.5]),
            ):
                mutated = copy.deepcopy(config)
                mutated[section][key] = value
                with self.assertRaises(ValueError):
                    runner.validate_v2_config(mutated)
                with self.assertRaises(ValueError):
                    verifier.validate_v2_config(mutated)

    def test_v2_rejects_resource_implementation_and_schema_drift(self) -> None:
        with synthetic_project() as root:
            _, config = synthetic_config(root)
            mutations = []
            resource_drift = copy.deepcopy(config)
            resource_drift["resources"]["verification_wall_seconds"] = 3600
            mutations.append(resource_drift)
            implementation_drift = copy.deepcopy(config)
            implementation_drift["implementation"]["runner"]["path"] = (
                "synthetic-sources/runner.py"
            )
            mutations.append(implementation_drift)
            extra_key = copy.deepcopy(config)
            extra_key["unregistered_option"] = True
            mutations.append(extra_key)
            for mutated in mutations:
                with self.assertRaises(ValueError):
                    runner.validate_v2_config(mutated)
                with self.assertRaises(ValueError):
                    verifier.validate_v2_config(mutated)

    def test_v2_rejects_oof_parent_identity_drift(self) -> None:
        with synthetic_project() as root:
            _, config = synthetic_config(root)
            oof_run = root / config["prerequisites"]["oof_run"]["path"]
            value = json.loads(oof_run.read_text(encoding="utf-8"))
            value["experiment_id"] = "EXP-062"
            write_json(oof_run, value)
            config["prerequisites"]["oof_run"] = record(root, oof_run)
            with self.assertRaises(ValueError):
                runner.validate_oof_prerequisites(config)
            with self.assertRaises(ValueError):
                verifier.oof_prerequisites(config)

    def test_v2_rejects_oof_transitive_artifact_drift(self) -> None:
        with synthetic_project() as root:
            _, config = synthetic_config(root)
            verification_path = root / config["prerequisites"]["oof_verification"]["path"]
            verification = json.loads(verification_path.read_text(encoding="utf-8"))
            verification["verified_artifacts"]["paired_oof_private"] = {
                **config["input"]["paired_oof"],
                "sha256": "0" * 64,
            }
            write_json(verification_path, verification)
            config["prerequisites"]["oof_verification"] = record(root, verification_path)
            completion_path = root / config["prerequisites"]["oof_completion"]["path"]
            completion = json.loads(completion_path.read_text(encoding="utf-8"))
            completion["artifacts"]["final_verification"] = record(root, verification_path)
            write_json(completion_path, completion)
            config["prerequisites"]["oof_completion"] = record(root, completion_path)
            with self.assertRaises(ValueError):
                runner.validate_oof_prerequisites(config)
            with self.assertRaises(ValueError):
                verifier.oof_prerequisites(config)

    def test_oof_consumer_rejects_minimal_passed_verifier(self) -> None:
        with synthetic_project() as root:
            _, config = synthetic_config(root)
            verification_path = root / config["prerequisites"]["oof_verification"]["path"]
            verification = json.loads(verification_path.read_text(encoding="utf-8"))
            minimal = {
                key: verification[key]
                for key in (
                    "schema_version",
                    "experiment_id",
                    "stage",
                    "run_id",
                    "attempt_id",
                    "model_seed",
                    "seed_contract",
                    "config",
                    "cli_identity",
                    "scope",
                    "status",
                    "failed_count",
                    "verified_artifacts",
                )
            }
            write_json(verification_path, minimal)
            config["prerequisites"]["oof_verification"] = record(root, verification_path)
            completion_path = root / config["prerequisites"]["oof_completion"]["path"]
            completion = json.loads(completion_path.read_text(encoding="utf-8"))
            completion["artifacts"]["final_verification"] = record(root, verification_path)
            write_json(completion_path, completion)
            config["prerequisites"]["oof_completion"] = record(root, completion_path)
            with self.assertRaises(ValueError):
                runner.validate_oof_prerequisites(config)
            with self.assertRaises(ValueError):
                verifier.oof_prerequisites(config)

        with synthetic_project() as root:
            _, config = synthetic_config(root)
            run_path = root / config["prerequisites"]["oof_run"]["path"]
            run = json.loads(run_path.read_text(encoding="utf-8"))
            oof_config_path = root / run["config"]["path"]
            oof_config = json.loads(oof_config_path.read_text(encoding="utf-8"))
            oof_config["resources"]["m3_total_wall_hours"] = 99.0
            write_json(oof_config_path, oof_config)
            run["config"] = record(root, oof_config_path)
            write_json(run_path, run)
            run_record = record(root, run_path)
            verification_path = root / config["prerequisites"]["oof_verification"]["path"]
            verification = json.loads(verification_path.read_text(encoding="utf-8"))
            verification["config"] = run["config"]
            verification["verified_artifacts"]["config"] = run["config"]
            verification["verified_artifacts"]["run"] = run_record
            write_json(verification_path, verification)
            verification_record = record(root, verification_path)
            completion_path = root / config["prerequisites"]["oof_completion"]["path"]
            completion = json.loads(completion_path.read_text(encoding="utf-8"))
            completion["config"] = run["config"]
            completion["artifacts"]["run"] = run_record
            completion["artifacts"]["final_verification"] = verification_record
            write_json(completion_path, completion)
            config["prerequisites"].update(
                {
                    "oof_run": run_record,
                    "oof_verification": verification_record,
                    "oof_completion": record(root, completion_path),
                }
            )
            with self.assertRaises(ValueError):
                runner.validate_oof_prerequisites(config)
            with self.assertRaises(ValueError):
                verifier.oof_prerequisites(config)

    def test_formal_rejects_preflight_verified_input_and_frozen_drift(self) -> None:
        with synthetic_project() as root:
            _, config = synthetic_config(root, formal=True)
            verification_path = root / config["prerequisites"]["preflight_verification"]["path"]
            verification = json.loads(verification_path.read_text(encoding="utf-8"))
            verification["verified_artifacts"]["paired_oof"] = {
                **config["input"]["paired_oof"],
                "sha256": "0" * 64,
            }
            write_json(verification_path, verification)
            config["prerequisites"]["preflight_verification"] = record(
                root, verification_path
            )
            with self.assertRaises(ValueError):
                runner.validate_preflight_prerequisites(config)
            with self.assertRaises(ValueError):
                verifier.preflight_prerequisites(config)

    def test_formal_consumers_reject_minimal_preflight_verification(self) -> None:
        with synthetic_project() as root:
            _, config = synthetic_config(root, formal=True)
            verification_path = root / config["prerequisites"]["preflight_verification"]["path"]
            verification = json.loads(verification_path.read_text(encoding="utf-8"))
            verification["checks"] = [
                {"name": "preflight.identity", "passed": True, "detail": None}
            ]
            verification["passed_count"] = 1
            verification["failed_count"] = 0
            write_json(verification_path, verification)
            config["prerequisites"]["preflight_verification"] = record(
                root, verification_path
            )
            with self.assertRaises(ValueError):
                runner.validate_preflight_prerequisites(config)
            with self.assertRaises(ValueError):
                verifier.preflight_prerequisites(config)

    def test_formal_rejects_arbitrary_frozen_preflight_config(self) -> None:
        with synthetic_project() as root:
            _, config = synthetic_config(root, formal=True)
            run_path = root / config["prerequisites"]["preflight_run"]["path"]
            run = json.loads(run_path.read_text(encoding="utf-8"))
            source_config = root / run["config"]["path"]
            frozen_config = run_path.parent / "frozen-sources" / "config.json"
            arbitrary = {"synthetic": "not a canonical EXP-059 preflight config"}
            write_json(source_config, arbitrary)
            write_json(frozen_config, arbitrary)
            run["config"] = record(root, source_config)
            run["frozen_sources"]["config"] = record(root, frozen_config)
            write_json(run_path, run)
            config["prerequisites"]["preflight_run"] = record(root, run_path)
            verification_path = root / config["prerequisites"]["preflight_verification"]["path"]
            verification = json.loads(verification_path.read_text(encoding="utf-8"))
            verification["config"] = run["config"]
            verification["verified_artifacts"]["config"] = run["config"]
            verification["verified_artifacts"]["run"] = record(root, run_path)
            write_json(verification_path, verification)
            config["prerequisites"]["preflight_verification"] = record(
                root, verification_path
            )
            with self.assertRaises(ValueError):
                runner.validate_preflight_prerequisites(config)
            with self.assertRaises(ValueError):
                verifier.preflight_prerequisites(config)

        with synthetic_project() as root:
            _, config = synthetic_config(root, formal=True)
            run_path = root / config["prerequisites"]["preflight_run"]["path"]
            run = json.loads(run_path.read_text(encoding="utf-8"))
            run["frozen_sources"]["runner"]["sha256"] = "0" * 64
            write_json(run_path, run)
            config["prerequisites"]["preflight_run"] = record(root, run_path)
            verification_path = root / config["prerequisites"]["preflight_verification"]["path"]
            verification = json.loads(verification_path.read_text(encoding="utf-8"))
            verification["verified_artifacts"]["run"] = record(root, run_path)
            write_json(verification_path, verification)
            config["prerequisites"]["preflight_verification"] = record(
                root, verification_path
            )
            with self.assertRaises(ValueError):
                runner.validate_preflight_prerequisites(config)
            with self.assertRaises(ValueError):
                verifier.preflight_prerequisites(config)

    def test_v2_rejects_symlinked_namespace(self) -> None:
        with synthetic_project() as root:
            _, config = synthetic_config(root)
            namespace = root / config["outputs"]["public_namespace"]
            real_namespace = root / "relocated-public-namespace"
            namespace.rename(real_namespace)
            namespace.symlink_to(root / "missing-public-namespace", target_is_directory=True)
            with self.assertRaises(ValueError):
                runner.validate_v2_config(config)
            with self.assertRaises(ValueError):
                verifier.validate_v2_config(config)

    def test_preflight_public_tree_uses_an_exact_allowlist(self) -> None:
        with synthetic_project() as root:
            _, config = synthetic_config(root)
            run_dir = runner.output_paths(config)["preflight"]
            frozen = run_dir / "frozen-sources"
            frozen.mkdir(parents=True)
            (frozen / "config.json").write_text("synthetic\n", encoding="utf-8")
            for source in config["implementation"].values():
                name = Path(source["path"]).name
                (frozen / name).write_text("synthetic\n", encoding="utf-8")
            write_json(run_dir / "run.json", {})
            runner.assert_exact_public_tree(run_dir, config, stage="preflight", verified=False)
            verifier.assert_exact_public_tree(run_dir, config, stage="preflight", verified=False)
            (run_dir / "unexpected.csv").write_text("forbidden\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                runner.assert_exact_public_tree(run_dir, config, stage="preflight", verified=False)
            with self.assertRaises(ValueError):
                verifier.assert_exact_public_tree(run_dir, config, stage="preflight", verified=False)

    def test_temperature_adoption_remains_diagnostic_for_router(self) -> None:
        with synthetic_project() as root:
            _, config = synthetic_config(root)
            adopted = {
                family: {
                    "fold_fits": [{"temperature": 2.0}],
                    "full_fit": {"temperature": 2.5},
                    "temperature_accepted": True,
                    "final_temperature": 2.5,
                    "final_threshold_selection": {"threshold": 0.42},
                }
                for family in runner.FAMILY_ORDER
            }
            document = runner.calibration_parameters_document(config, adopted)
            independent = verifier.calibration_parameters_document(config, adopted)
            self.assertEqual(document, independent)
            self.assertEqual(document["families"]["m1"]["selected_calibrator"], "temperature")
            self.assertEqual(document["families"]["m1"]["final_temperature"], 2.5)
            self.assertEqual(document["router_replication_calibration"], {
                "calibrator": "identity",
                "temperature": 1.0,
                "probability_source": "direct_sigmoid_of_raw_oof_logits",
                "role": "frozen_exp060_replication_only",
            })

    def test_v2_report_names_current_seed_not_seed_42(self) -> None:
        with synthetic_project() as root:
            _, config = synthetic_config(root)
            calibration = {
                "families": {
                    family: {
                        "identity": {"nll": 1.0, "brier": 0.2},
                        "temperature_cross_fitted": {"nll": 0.9, "brier": 0.19},
                        "selected_calibrator": "temperature",
                        "final_temperature": 2.0,
                    }
                    for family in runner.FAMILY_ORDER
                }
            }
            classification = {
                "families": {
                    family: {
                        "selected_cross_fitted_threshold": {
                            "macro_f1": 0.5,
                            "five_label_macro_f1": 0.5,
                            "micro_f1": 0.5,
                            "hamming_loss": 0.2,
                            "subset_accuracy": 0.2,
                        }
                    }
                    for family in runner.FAMILY_ORDER
                }
            }
            gates = {"families": {family: {"passed": False} for family in runner.FAMILY_ORDER}}
            oracle = {
                "m3_selection_rate": 0.1,
                "macro_f1_gain_over_m1": 0.01,
                "five_label_macro_f1_gain_over_m1": 0.01,
                "router_headroom_gate": {"passed": True},
            }
            report = root / "REPORT.md"
            runner.write_report(report, calibration, classification, gates, oracle, {"repetitions": 2000}, config)
            text = report.read_text(encoding="utf-8")
            self.assertIn("seed-43", text)
            self.assertIn("EXP-061", text)
            self.assertIn("diagnostic only", text)
            self.assertIn("`T=1`", text)
            self.assertNotIn("seed-42", text)
            self.assertEqual(
                text,
                verifier.expected_report_text(
                    {
                        "calibration": calibration,
                        "classification": classification,
                        "gates": gates,
                        "oracle": oracle,
                        "bootstrap": {"repetitions": 2000},
                    },
                    config,
                ),
            )

    def test_runner_and_verifier_render_identical_deterministic_figures(self) -> None:
        if importlib.util.find_spec("matplotlib") is None:
            self.skipTest("matplotlib is unavailable in the synthetic test environment")
        with tempfile.TemporaryDirectory(prefix="exp059-figure-contract-") as temporary:
            root = Path(temporary)
            runner_dir = root / "runner"
            verifier_dir = root / "verifier"
            runner_dir.mkdir()
            verifier_dir.mkdir()
            reliability_rows = [
                {
                    "family": family,
                    "pipeline": pipeline,
                    "mean_confidence": 0.5,
                    "empirical_positive_rate": 0.4,
                }
                for family in runner.FAMILY_ORDER
                for pipeline in ("identity", "temperature")
            ]
            risk_rows = [
                {
                    "family": family,
                    "method": method,
                    "actual_coverage": 0.8,
                    "hamming_risk": 0.2,
                }
                for family in runner.FAMILY_ORDER
                for method in runner.METHOD_ORDER
            ]
            random_rows = [
                {
                    "family": family,
                    "metric": "hamming_risk",
                    "actual_coverage": 0.8,
                    "mean": 0.25,
                }
                for family in runner.FAMILY_ORDER
            ]
            runner_figures = runner.make_figures(
                runner_dir, reliability_rows, risk_rows, random_rows
            )
            verifier_figures = verifier.make_expected_figures(
                verifier_dir, reliability_rows, risk_rows, random_rows
            )
            self.assertEqual(
                [hashlib.sha256(path.read_bytes()).hexdigest() for path in runner_figures],
                [hashlib.sha256(path.read_bytes()).hexdigest() for path in verifier_figures],
            )
            self.assertEqual(
                [verifier.png_dimensions(path) for path in runner_figures],
                [(1600, 640), (1600, 640)],
            )

    def test_report_privacy_rejects_sample_and_component_identifiers(self) -> None:
        data = {
            "sample_ids": np.asarray(["PRIVATE-SAMPLE-ALPHA"]),
            "component_ids": np.asarray(["PRIVATE-COMPONENT-BETA"]),
        }
        report = "Aggregate only, except PRIVATE-COMPONENT-BETA leaked here."
        self.assertEqual(
            runner.report_private_identifier_leaks(report, data),
            ["PRIVATE-COMPONENT-BETA"],
        )
        self.assertEqual(
            verifier.report_private_identifier_leaks(report, data),
            ["PRIVATE-COMPONENT-BETA"],
        )

    def test_completion_is_verifier_only_identity_bound_and_write_once(self) -> None:
        with synthetic_project() as root:
            config_path, config = synthetic_config(root, formal=True)
            paths, verification = populate_synthetic_final_bundle(root, config_path, config)
            run_dir = paths["public_calibration"]
            verification_path = run_dir / "verification.json"
            unexpected = run_dir / "unexpected-public.npz"
            unexpected.write_bytes(b"forbidden")
            with self.assertRaises(ValueError):
                runner.assert_exact_public_tree(
                    run_dir, config, stage="calibration", verified=True
                )
            with self.assertRaises(ValueError):
                verifier.assert_exact_public_tree(
                    run_dir, config, stage="calibration", verified=True
                )
            unexpected.unlink()
            verification["verified_artifacts"]["run"]["sha256"] = "0" * 64
            write_json(verification_path, verification)
            with self.assertRaises((RuntimeError, ValueError)):
                verifier.verify_completion(config_path, config)
            self.assertFalse(paths["completion"].exists())
            verification["verified_artifacts"]["run"] = verifier.artifact(
                run_dir / "run.json"
            )
            write_json(verification_path, verification)
            completion = verifier.verify_completion(config_path, config)
            self.assertEqual(completion["experiment_id"], "EXP-059")
            self.assertEqual(completion["replication_parent_experiment_id"], "EXP-061")
            self.assertEqual(set(completion["artifacts"]), {
                "config",
                "exp059_run",
                "exp059_verification",
                "exp059_verification_summary",
                "exp059_calibration_parameters",
                "paired_oof_private",
                "private_calibration",
                "public_outputs",
                "frozen_sources",
            })
            self.assertFalse(paths["selection"].exists())
            self.assertEqual(verifier.verify_completion(config_path, config), completion)

    def test_verification_bundle_resumes_after_json_before_summary(self) -> None:
        with synthetic_project() as root:
            config_path, config = synthetic_config(root)
            bundle = root / "synthetic-verification-bundle"
            bundle.mkdir()
            output = bundle / "verification.json"
            summary = bundle / "VERIFICATION-SUMMARY.md"
            checks = verifier.Checks()
            for name in sorted(verifier.PREFLIGHT_VERIFICATION_REQUIRED_CHECKS):
                checks.add(name, True)
            result = verifier.verification_result(
                "preflight",
                checks,
                config,
                {
                    "wall_seconds": 0.1,
                    "peak_process_rss_gb": 0.1,
                    "api_cost_usd": 0,
                },
            )
            result["config"] = verifier.artifact(config_path)
            result["verified_artifacts"] = {
                "config": verifier.artifact(config_path),
                "run": config["prerequisites"]["oof_run"],
                "paired_oof": config["input"]["paired_oof"],
            }
            write_json(output, result)
            resumed = verifier.resume_verification_bundle(
                output,
                summary,
                config,
                "preflight",
                verifier.artifact(config_path),
            )
            self.assertEqual(resumed, result)
            self.assertEqual(summary.read_text(encoding="utf-8"), verifier.render_summary(result))
            self.assertEqual(
                verifier.resume_verification_bundle(
                    output,
                    summary,
                    config,
                    "preflight",
                    verifier.artifact(config_path),
                ),
                result,
            )

    def test_resume_rejects_minimal_single_check_passed_json(self) -> None:
        with synthetic_project() as root:
            config_path, config = synthetic_config(root)
            bundle = root / "minimal-verification-bundle"
            bundle.mkdir()
            output = bundle / "verification.json"
            summary = bundle / "VERIFICATION-SUMMARY.md"
            checks = verifier.Checks()
            checks.add("preflight.identity", True)
            result = verifier.verification_result(
                "preflight",
                checks,
                config,
                {
                    "wall_seconds": 0.1,
                    "peak_process_rss_gb": 0.1,
                    "api_cost_usd": 0,
                },
            )
            result["config"] = verifier.artifact(config_path)
            result["verified_artifacts"] = {
                "config": verifier.artifact(config_path),
                "run": config["prerequisites"]["oof_run"],
                "paired_oof": config["input"]["paired_oof"],
            }
            write_json(output, result)
            with self.assertRaises(ValueError):
                verifier.resume_verification_bundle(
                    output,
                    summary,
                    config,
                    "preflight",
                    verifier.artifact(config_path),
                )
            self.assertFalse(summary.exists())

    def test_completion_rejects_minimal_pass_and_public_report_mutation(self) -> None:
        with synthetic_project() as root:
            config_path, config = synthetic_config(root, formal=True)
            paths, verification = populate_synthetic_final_bundle(root, config_path, config)
            verification_path = paths["public_calibration"] / "verification.json"
            verification["checks"] = [
                {"name": "run.identity", "passed": True, "detail": None}
            ]
            verification["passed_count"] = 1
            write_json(verification_path, verification)
            (paths["public_calibration"] / "VERIFICATION-SUMMARY.md").write_text(
                verifier.render_summary(verification), encoding="utf-8"
            )
            with self.assertRaises((RuntimeError, ValueError)):
                verifier.verify_completion(config_path, config)

        with synthetic_project() as root:
            config_path, config = synthetic_config(root, formal=True)
            paths, _ = populate_synthetic_final_bundle(root, config_path, config)
            report = paths["public_calibration"] / "REPORT.md"
            report.write_text("mutated after verification\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                verifier.verify_completion(config_path, config)

    def test_verifier_is_independent_and_no_model_libraries_are_imported(self) -> None:
        for path in (RUNNER_PATH, VERIFIER_PATH):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
            self.assertFalse(any(name.split(".")[0] in {"torch", "mlx", "transformers"} for name in imports))
        runner_source = RUNNER_PATH.read_text(encoding="utf-8")
        self.assertFalse(
            any(name.endswith("run_exp059_calibration") for name in imports)
        )
        self.assertNotIn("create_calibration_completion", runner_source)


if __name__ == "__main__":
    unittest.main()
