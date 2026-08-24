from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp058_oof_production.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp058_oof_production.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_module("exp058_oof_production_under_test", RUNNER_PATH)
verifier = load_module("exp058_oof_verifier_under_test", VERIFIER_PATH)


def digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def record(root: Path, path: Path) -> dict[str, object]:
    return {
        "path": str(path.relative_to(root)),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def synthetic_v2(module, experiment_id: str = "EXP-061") -> dict[str, object]:
    seed, run_name = {
        "EXP-061": (43, "exp-061-seed-43-router-replication"),
        "EXP-062": (44, "exp-062-seed-44-router-replication"),
    }[experiment_id]
    attempt = "attempt-1"
    base = module.display_path(module.SCRIPT_DIR)
    base_asset = digest("base-assets")
    fold_manifest = digest("fold-manifest")
    expected_by_fold = {}
    for fold_id in range(5):
        values = {field: digest(f"{seed}:{fold_id}:{field}") for field in module.INIT_HASH_FIELDS}
        values["base_asset_manifest_sha256"] = base_asset
        values["fold_manifest_sha256"] = fold_manifest
        values["m1_rng_state_digest"] = module.canonical_digest(
            {
                "python_seed": seed,
                "numpy_seed": seed,
                "torch_seed": seed,
                "m1_batch_seed": seed,
            }
        )
        values["m3_rng_state_digest"] = module.canonical_digest(
            {
                "m3_head_seed": seed,
                "m3_batch_seed": seed,
                "m3_lora_seed": seed + 100000,
            }
        )
        values["m1_initialization_state_sha256"] = module.initialization_state_sha256(
            "m1",
            {
                "m1_classifier_init_sha256": values["m1_classifier_init_sha256"],
                "m1_rng_state_digest": values["m1_rng_state_digest"],
            },
        )
        values["m3_initialization_state_sha256"] = module.initialization_state_sha256(
            "m3",
            {
                "m3_lora_a_init_sha256": values["m3_lora_a_init_sha256"],
                "m3_lora_b_init_sha256": values["m3_lora_b_init_sha256"],
                "m3_lora_combined_init_sha256": values["m3_lora_combined_init_sha256"],
                "m3_classifier_head_init_sha256": values["m3_classifier_head_init_sha256"],
                "m3_base_sentinel_sha256": values["m3_base_sentinel_sha256"],
                "m3_rng_state_digest": values["m3_rng_state_digest"],
            },
        )
        expected_by_fold[str(fold_id)] = {"model_seed": seed, **values}
    return {
        "schema_version": module.CONFIG_V2_SCHEMA,
        "experiment_id": experiment_id,
        "rq_id": "RQ-S3",
        "tier": "Major",
        "stage": "paired-m1-m3-oof-production",
        "run_id": run_name,
        "attempt_id": attempt,
        "authorization": {
            "authorized_at": "2026-08-17T00:00:00+00:00",
            "basis": "synthetic contract test",
            "fold_ids": [0, 1, 2, 3, 4],
            "model_seed": seed,
            "assembly": True,
            "full_oof_training": True,
            "heldout_forward": True,
            "model_loading": True,
            "calibration": False,
            "metrics": False,
            "oracle_analysis": False,
            "router_training": False,
            "test_access": False,
            "validation_access": False,
            "cross_seed_initialization_verification_sha256": digest("cross-seed-gate"),
        },
        "execution": {
            "model_seed": seed,
            **module.V2_EXECUTION,
        },
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
        "outputs": {
            "public_namespace": f"{base}/runs/{run_name}",
            "public_attempt_dir": f"{base}/runs/{run_name}/{attempt}",
            "private_namespace": f"{base}/private/{run_name}",
            "private_attempt_dir": f"{base}/private/{run_name}/{attempt}",
            "selection_record": f"{base}/runs/{run_name}/selected-attempt.json",
        },
        "initialization": {
            "base_asset_manifest_sha256": base_asset,
            "expected_by_fold": expected_by_fold,
        },
        "implementation": {
            "protocol": {
                "path": module.V2_PROTOCOL_PATHS[experiment_id],
                "bytes": 1,
                "sha256": digest(f"{experiment_id}:protocol"),
            },
            **{
                key: {
                    "path": path,
                    "bytes": 1,
                    "sha256": digest(key),
                }
                for key, path in module.V2_IMPLEMENTATION_PATHS.items()
            },
        },
        "prerequisites": {
            **{
                key: {"path": f"synthetic/{key}.json", "bytes": 1, "sha256": digest(key)}
                for key in module.V2_PREREQUISITE_KEYS
            },
            "shared_config": {
                "path": module.FROZEN_SHARED_CONFIG_PATH,
                "bytes": module.FROZEN_SHARED_CONFIG_BYTES,
                "sha256": module.FROZEN_SHARED_CONFIG_SHA256,
            },
            "fold_manifest": {
                "path": module.FROZEN_FOLD_MANIFEST_PATH,
                "bytes": 1,
                "sha256": fold_manifest,
            },
            "cross_seed_initialization_verification": {
                "path": "synthetic/cross-seed.json",
                "bytes": 1,
                "sha256": digest("cross-seed-gate"),
            },
        },
        "data": {
            "train": {
                "path": module.FROZEN_TRAIN_PATH,
                "bytes": 1,
                "sha256": module.FROZEN_TRAIN_SHA256,
            },
            "protocol_id": "DATA-SO-TASK-V1",
            "label_order": list(module.LABELS),
        },
        "m1": copy.deepcopy(module.V2_M1),
        "m3": copy.deepcopy(module.V2_M3),
        "resources": copy.deepcopy(module.V2_RESOURCES),
    }


class OOFProductionSyntheticContractTests(unittest.TestCase):
    def test_seed_43_and_44_dynamic_identities_pass_both_implementations(self) -> None:
        for experiment_id, seed in (("EXP-061", 43), ("EXP-062", 44)):
            for module in (runner, verifier):
                config = synthetic_v2(module, experiment_id)
                module.validate_v2_identity(config)
                self.assertEqual(module.model_seed(config), seed)
                self.assertEqual(module.seed_contract(config)["m3_lora_seed"], seed + 100000)

    def test_seed_contract_drift_is_rejected(self) -> None:
        for module in (runner, verifier):
            config = synthetic_v2(module)
            config["seed_contract"]["m3_lora_seed"] = 43
            with self.assertRaisesRegex(ValueError, "seed contract"):
                module.validate_v2_identity(config)

    def test_v2_exact_top_level_and_scientific_contract_reject_drift(self) -> None:
        for module in (runner, verifier):
            extra = synthetic_v2(module)
            extra["unexpected"] = True
            with self.assertRaisesRegex(ValueError, "top-level"):
                module.validate_v2_identity(extra)
            changed = synthetic_v2(module)
            changed["m3"]["expected_insertion_points"] = 111
            with self.assertRaisesRegex(ValueError, "scientific contract"):
                module.validate_v2_identity(changed)

    def test_every_v2_implementation_path_substitution_is_rejected(self) -> None:
        for module in (runner, verifier):
            for experiment_id in ("EXP-061", "EXP-062"):
                baseline = synthetic_v2(module, experiment_id)
                for key in module.V2_IMPLEMENTATION_KEYS:
                    changed = copy.deepcopy(baseline)
                    changed["implementation"][key]["path"] = f"synthetic/decoy-{key}"
                    with self.subTest(module=module.__name__, experiment=experiment_id, key=key):
                        with self.assertRaisesRegex(ValueError, f"implementation\\.{key} canonical path"):
                            module.validate_v2_identity(changed)

    def test_attempt_and_output_paths_are_exactly_derived(self) -> None:
        for module in (runner, verifier):
            bad_attempt = synthetic_v2(module)
            bad_attempt["attempt_id"] = "attempt-0"
            with self.assertRaisesRegex(ValueError, "attempt_id"):
                module.validate_v2_identity(bad_attempt)
            redirected = synthetic_v2(module)
            redirected["outputs"]["public_attempt_dir"] += "-copy"
            with self.assertRaisesRegex(ValueError, "canonical derived paths"):
                module.validate_v2_identity(redirected)

    def test_v2_cli_identity_is_required_and_cannot_override_config(self) -> None:
        for module in (runner, verifier):
            config = synthetic_v2(module)
            with self.assertRaisesRegex(PermissionError, "CLI identity"):
                module.bind_cli_identity(
                    config,
                    cli_model_seed=None,
                    cli_run_id=None,
                    cli_output_root=None,
                    cli_fold_manifest_sha256=None,
                    cli_data_manifest_sha256=None,
                )
            expected = module.expected_cli_identity(config)
            module.bind_cli_identity(
                config,
                cli_model_seed=expected["model_seed"],
                cli_run_id=expected["run_id"],
                cli_output_root=Path(expected["output_root"]),
                cli_fold_manifest_sha256=expected["expected_fold_manifest_sha256"],
                cli_data_manifest_sha256=expected["expected_data_manifest_sha256"],
            )
            self.assertEqual(config["_cli_identity"], expected)
            drift = synthetic_v2(module)
            with self.assertRaisesRegex(ValueError, "exactly match"):
                module.bind_cli_identity(
                    drift,
                    cli_model_seed=44,
                    cli_run_id=module.expected_cli_identity(drift)["run_id"],
                    cli_output_root=Path(module.expected_cli_identity(drift)["output_root"]),
                    cli_fold_manifest_sha256=module.expected_cli_identity(drift)["expected_fold_manifest_sha256"],
                    cli_data_manifest_sha256=module.expected_cli_identity(drift)["expected_data_manifest_sha256"],
                )

    def test_m3_shared_mutex_is_nonblocking_and_precedes_attempt_mutation(self) -> None:
        config = synthetic_v2(runner)
        with mock.patch.object(runner, "begin_fold") as begin_fold:
            with self.assertRaisesRegex(PermissionError, "shared workload mutex"):
                runner.run_m3_fold(config, 0, None)
            begin_fold.assert_not_called()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with mock.patch.object(runner, "PROJECT_ROOT", root):
                with runner.heavy_research_workload_mutex(config, 0) as metadata:
                    self.assertTrue(runner.valid_m3_lock_metadata(metadata, config, 0))
                    self.assertTrue(verifier.valid_m3_lock_metadata(metadata, synthetic_v2(verifier), 0))
                    with self.assertRaisesRegex(RuntimeError, "already owned"):
                        with runner.heavy_research_workload_mutex(config, 1):
                            self.fail("contended mutex must never be acquired")
                    public_attempt = runner.resolve_output(config["outputs"]["public_attempt_dir"])
                    self.assertFalse(runner.lexists(public_attempt))
                lock_path = runner.resolve_output(runner.HEAVY_WORKLOAD_LOCK_PATH)
                self.assertEqual(lock_path.stat().st_mode & 0o777, 0o600)

    def test_placeholder_initialization_digest_is_rejected(self) -> None:
        for module in (runner, verifier):
            config = synthetic_v2(module)
            config["initialization"]["expected_by_fold"]["0"][
                "m1_classifier_init_sha256"
            ] = "0" * 64
            with self.assertRaisesRegex(ValueError, "non-placeholder"):
                module.validate_v2_identity(config)

    def test_validation_or_test_path_cannot_replace_frozen_train(self) -> None:
        for module in (runner, verifier):
            config = synthetic_v2(module)
            config["data"]["train"] = {
                "path": module.FROZEN_TRAIN_PATH,
                "bytes": 1,
                "sha256": module.FROZEN_TRAIN_SHA256,
            }
            config["prerequisites"]["fold_manifest"] = {
                "path": module.FROZEN_FOLD_MANIFEST_PATH,
                "bytes": 1,
                "sha256": module.FROZEN_FOLD_MANIFEST_SHA256,
            }
            for expected in config["initialization"]["expected_by_fold"].values():
                expected["fold_manifest_sha256"] = module.FROZEN_FOLD_MANIFEST_SHA256
            module.verify_v2_frozen_data_identity(config)
            config["data"]["train"]["path"] = "data/stack-overflow-emotion-gold/validation.jsonl"
            with self.assertRaisesRegex(PermissionError, "frozen EXP-058 train"):
                module.verify_v2_frozen_data_identity(config)

    def test_seed_and_initialization_state_digests_change(self) -> None:
        config_43 = synthetic_v2(runner, "EXP-061")
        config_44 = synthetic_v2(runner, "EXP-062")
        self.assertNotEqual(runner.m1_rng_state_digest(config_43), runner.m1_rng_state_digest(config_44))
        self.assertNotEqual(runner.m3_rng_state_digest(config_43), runner.m3_rng_state_digest(config_44))
        self.assertNotEqual(
            config_43["initialization"]["expected_by_fold"]["0"]["m1_classifier_init_sha256"],
            config_44["initialization"]["expected_by_fold"]["0"]["m1_classifier_init_sha256"],
        )

    def test_output_resolver_rejects_symlink_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.mkdir()
            (root / "linked").symlink_to(target, target_is_directory=True)
            for module in (runner, verifier):
                with mock.patch.object(module, "PROJECT_ROOT", root):
                    with self.assertRaisesRegex(ValueError, "symlink"):
                        module.resolve_output("linked/attempt-1")

    def test_artifact_records_reject_broken_symlink_and_old_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            current = root / "current"
            old = root / "old"
            current.mkdir()
            old.mkdir()
            old_file = old / "artifact.json"
            old_file.write_text("{}")
            broken = root / "broken.json"
            broken.symlink_to(root / "missing.json")
            for module in (runner, verifier):
                with mock.patch.object(module, "PROJECT_ROOT", root):
                    with self.assertRaises((ValueError, FileNotFoundError)):
                        module.require_record(
                            {"path": "broken.json", "bytes": 1, "sha256": digest("missing")}
                        )
                    with self.assertRaisesRegex(ValueError, "current attempt"):
                        module.require_record_within(record(root, old_file), current)

    def test_public_allowlist_rejects_extra_json_csv_and_npz(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            script_dir = root / "experiments" / "stack-overflow-emotion-gold" / "oof-router"
            script_dir.mkdir(parents=True)
            for module in (runner, verifier):
                with (
                    mock.patch.object(module, "PROJECT_ROOT", root),
                    mock.patch.object(module, "SCRIPT_DIR", script_dir),
                ):
                    config = synthetic_v2(module)
                    attempt = module.resolve_output(config["outputs"]["public_attempt_dir"])
                    attempt.mkdir(parents=True, exist_ok=True)
                    (attempt / "extra-dir").mkdir()
                    for name in ("extra.json", "extra.csv", "extra.npz"):
                        (attempt / name).write_bytes(b"{}")
                    violations = module.public_artifact_violations(config)
                    self.assertTrue(any("extra-dir" in item for item in violations))
                    self.assertTrue(any("extra.json" in item for item in violations))
                    self.assertTrue(any("extra.csv" in item for item in violations))
                    self.assertTrue(any("extra.npz" in item for item in violations))
                    (attempt / "extra-dir").rmdir()
                    for child in attempt.iterdir():
                        child.unlink()

    def test_completion_creation_is_atomic_and_single_use(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "oof-complete.json"
            runner.create_json_once(path, {"status": "Complete"})
            self.assertEqual(json.loads(path.read_text()), {"status": "Complete"})
            with self.assertRaises(FileExistsError):
                runner.create_json_once(path, {"status": "replacement"})
            self.assertEqual(json.loads(path.read_text()), {"status": "Complete"})

    def test_oof_completion_never_creates_final_pipeline_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            script_dir = root / "experiments" / "stack-overflow-emotion-gold" / "oof-router"
            script_dir.mkdir(parents=True)
            with (
                mock.patch.object(runner, "PROJECT_ROOT", root),
                mock.patch.object(runner, "SCRIPT_DIR", script_dir),
            ):
                config = synthetic_v2(runner)
                config_path = root / "formal-config.json"
                config_path.write_text(json.dumps(config, sort_keys=True))
                config["_config_path"] = str(config_path)
                config["_config_sha256"] = hashlib.sha256(config_path.read_bytes()).hexdigest()
                expected_cli = runner.expected_cli_identity(config)
                runner.bind_cli_identity(
                    config,
                    cli_model_seed=expected_cli["model_seed"],
                    cli_run_id=expected_cli["run_id"],
                    cli_output_root=Path(expected_cli["output_root"]),
                    cli_fold_manifest_sha256=expected_cli["expected_fold_manifest_sha256"],
                    cli_data_manifest_sha256=expected_cli["expected_data_manifest_sha256"],
                )
                public_attempt = runner.resolve_output(config["outputs"]["public_attempt_dir"])
                private_attempt = runner.resolve_output(config["outputs"]["private_attempt_dir"])
                public_attempt.mkdir(parents=True)
                private_attempt.mkdir(parents=True)
                paired_path = private_attempt / "paired-oof.npz"
                paired_path.write_bytes(b"synthetic-paired-oof")
                paired_record = runner.artifact(paired_path)
                identity = runner.identity_provenance(config)
                run_path = public_attempt / "run.json"
                run_path.write_text(
                    json.dumps(
                        {
                            "schema_version": "exp-oof-production-run-v2",
                            **identity,
                            "status": "CompletedAwaitingVerification",
                            "artifacts": {"paired_oof_private": paired_record},
                        },
                        sort_keys=True,
                    )
                )
                summary_path = public_attempt / "paired-oof-summary.json"
                summary_path.write_text(json.dumps({
                    "schema_version": "exp-paired-oof-summary-v2",
                    **identity,
                    "status": "CompletedAwaitingVerification",
                }))
                verification_path = public_attempt / "verification.json"
                verification_path.write_text(
                    json.dumps(
                        {
                            "schema_version": "exp-oof-final-verification-v2",
                            **identity,
                            "scope": "final",
                            "status": "Passed",
                            "failed_count": 0,
                            "verified_artifacts": {
                                "config": runner.artifact(config_path),
                                "run": runner.artifact(run_path),
                                "summary": runner.artifact(summary_path),
                                "paired_oof_private": paired_record,
                            },
                        },
                        sort_keys=True,
                    )
                )
                original_summary = summary_path.read_bytes()
                summary_path.write_text(json.dumps({
                    "schema_version": "exp-paired-oof-summary-v2",
                    **identity,
                    "status": "TamperedAfterVerification",
                }))
                with self.assertRaisesRegex(RuntimeError, "Passed final OOF verification"):
                    runner.complete_oof_attempt(config_path, config)
                self.assertFalse((public_attempt / "oof-complete.json").exists())
                summary_path.write_bytes(original_summary)
                completion = runner.complete_oof_attempt(config_path, config)
                self.assertEqual(completion["status"], "Complete")
                self.assertEqual(completion["config"], runner.artifact(config_path))
                self.assertTrue((public_attempt / "oof-complete.json").is_file())
                self.assertFalse(runner.selection_record_path(config).exists())
                with (
                    mock.patch.object(verifier, "PROJECT_ROOT", root),
                    mock.patch.object(verifier, "SCRIPT_DIR", script_dir),
                ):
                    verified = verifier.verify_completion(config_path, config)
                self.assertEqual(verified["status"], "Passed")
                with self.assertRaises(FileExistsError):
                    runner.complete_oof_attempt(config_path, config)

    def test_full_v2_config_loads_from_synthetic_public_artifacts(self) -> None:
        for module in (runner, verifier):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                script_dir = root / "experiments" / "stack-overflow-emotion-gold" / "oof-router"
                artifacts = root / "synthetic-artifacts"
                script_dir.mkdir(parents=True)
                artifacts.mkdir()
                with (
                    mock.patch.object(module, "PROJECT_ROOT", root),
                    mock.patch.object(module, "SCRIPT_DIR", script_dir),
                ):
                    config = synthetic_v2(module)
                    implementation = {}
                    implementation_paths = {
                        "protocol": module.V2_PROTOCOL_PATHS[config["experiment_id"]],
                        **module.V2_IMPLEMENTATION_PATHS,
                    }
                    for key, relative_path in implementation_paths.items():
                        path = root / relative_path
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(f"synthetic {key}\n")
                        implementation[key] = record(root, path)
                    shared_path = root / module.FROZEN_SHARED_CONFIG_PATH
                    shared_path.parent.mkdir(parents=True, exist_ok=True)
                    shared = {
                        "data": {"test_status": "sealed_not_authorized_for_model_access"},
                        "models": {
                            "m1": {"manifest_sha256": digest("m1-assets")},
                            "qwen_shared": {"manifest_sha256": digest("m3-assets")},
                        },
                    }
                    shared_path.write_text(json.dumps(shared))
                    shared_record = record(root, shared_path)
                    base_asset = module.base_asset_manifest_sha256(shared)
                    fold_path = root / module.FROZEN_FOLD_MANIFEST_PATH
                    fold_path.parent.mkdir(parents=True, exist_ok=True)
                    fold_path.write_text("synthetic-fold-manifest\n")
                    fold_hash = hashlib.sha256(fold_path.read_bytes()).hexdigest()
                    for expected in config["initialization"]["expected_by_fold"].values():
                        expected["base_asset_manifest_sha256"] = base_asset
                        expected["fold_manifest_sha256"] = fold_hash
                    config["initialization"]["base_asset_manifest_sha256"] = base_asset
                    consumer_path = artifacts / "consumer.json"
                    consumer_path.write_text(
                        json.dumps(
                            {
                                "fold_manifest_sha256": fold_hash,
                                "forbidden_splits": ["validation", "test"],
                            }
                        )
                    )
                    fold_verification_path = artifacts / "fold-verification.json"
                    fold_verification_path.write_text(
                        json.dumps({"status": "Passed", "failed_count": 0})
                    )
                    train_path = root / module.FROZEN_TRAIN_PATH
                    train_path.parent.mkdir(parents=True, exist_ok=True)
                    train_path.write_text("synthetic-train-never-read\n")
                    config["implementation"] = implementation
                    config["prerequisites"].update(
                        {
                            "shared_config": shared_record,
                            "fold_manifest": record(root, fold_path),
                            "consumer_contract": record(root, consumer_path),
                            "fold_verification": record(root, fold_verification_path),
                        }
                    )
                    config["data"] = {
                        "train": record(root, train_path),
                        "protocol_id": "DATA-SO-TASK-V1",
                        "label_order": list(module.LABELS),
                    }
                    scientific_digest = module.shared_scientific_contract_sha256(config)
                    initialization_path = artifacts / "initialization.json"
                    initialization = {
                        "schema_version": "exp-oof-initialization-manifest-v1",
                        "experiment_id": config["experiment_id"],
                        "run_id": config["run_id"],
                        "attempt_id": config["attempt_id"],
                        "model_seed": config["execution"]["model_seed"],
                        "seed_contract": config["seed_contract"],
                        "base_asset_manifest_sha256": base_asset,
                        "fold_manifest_sha256": fold_hash,
                        "shared_scientific_contract_sha256": scientific_digest,
                        "cross_seed_gate": {
                            "required_before_formal_training": True,
                            "status": "Pending",
                            "verification_schema": "exp-oof-cross-seed-initialization-verification-v1",
                        },
                        "folds": {
                            key: {**value, "m3_lora_b_zero_initialized": True}
                            for key, value in config["initialization"]["expected_by_fold"].items()
                        },
                    }
                    initialization_path.write_text(json.dumps(initialization, sort_keys=True))
                    initialization_record = record(root, initialization_path)
                    initialization_verification_path = artifacts / "initialization-verification.json"
                    initialization_verification_path.write_text(
                        json.dumps(
                            {
                                "status": "Passed",
                                "failed_count": 0,
                                "experiment_id": config["experiment_id"],
                                "run_id": config["run_id"],
                                "attempt_id": config["attempt_id"],
                                "model_seed": config["execution"]["model_seed"],
                                "seed_contract": config["seed_contract"],
                                "shared_scientific_contract_sha256": scientific_digest,
                                "verified_artifacts": {
                                    "initialization_manifest": initialization_record
                                },
                            }
                        )
                    )
                    initialization_verification_record = record(
                        root, initialization_verification_path
                    )
                    cross_path = artifacts / "cross-seed.json"
                    cross_path.write_text(
                        json.dumps(
                            {
                                "schema_version": "exp-oof-cross-seed-initialization-verification-v1",
                                "status": "Passed",
                                "failed_count": 0,
                                "shared_scientific_contract_sha256": scientific_digest,
                                "base_asset_manifest_sha256": base_asset,
                                "fold_manifest_sha256": fold_hash,
                                "members": {
                                    config["experiment_id"]: {
                                        "model_seed": config["execution"]["model_seed"],
                                        "formal_run_id": config["run_id"],
                                        "formal_attempt_id": config["attempt_id"],
                                        "initialization_manifest": initialization_record,
                                        "initialization_verification": initialization_verification_record,
                                    }
                                },
                            },
                            sort_keys=True,
                        )
                    )
                    cross_record = record(root, cross_path)
                    config["prerequisites"].update(
                        {
                            "initialization_manifest": initialization_record,
                            "initialization_verification": initialization_verification_record,
                            "cross_seed_initialization_verification": cross_record,
                        }
                    )
                    config["authorization"][
                        "cross_seed_initialization_verification_sha256"
                    ] = cross_record["sha256"]
                    config_path = root / "formal-config.json"
                    config_path.write_text(json.dumps(config, sort_keys=True))
                    live_attribute = (
                        "LIVE_RUNNER_PATH" if module is runner else "LIVE_VERIFIER_PATH"
                    )
                    live_key = "runner" if module is runner else "verifier"
                    with (
                        mock.patch.object(module, "FROZEN_TRAIN_SHA256", record(root, train_path)["sha256"]),
                        mock.patch.object(module, "FROZEN_FOLD_MANIFEST_SHA256", fold_hash),
                        mock.patch.object(module, "FROZEN_SHARED_CONFIG_BYTES", shared_record["bytes"]),
                        mock.patch.object(module, "FROZEN_SHARED_CONFIG_SHA256", shared_record["sha256"]),
                        mock.patch.object(
                            module,
                            live_attribute,
                            root / implementation_paths[live_key],
                        ),
                    ):
                        loaded = module.load_config(config_path)
                    self.assertEqual(loaded["experiment_id"], "EXP-061")
                    self.assertEqual(loaded["execution"]["model_seed"], 43)

                    decoy_live = root / "synthetic-artifacts" / "decoy-live.py"
                    decoy_live.write_text("decoy\n")
                    with (
                        mock.patch.object(module, "FROZEN_TRAIN_SHA256", record(root, train_path)["sha256"]),
                        mock.patch.object(module, "FROZEN_FOLD_MANIFEST_SHA256", fold_hash),
                        mock.patch.object(module, "FROZEN_SHARED_CONFIG_BYTES", shared_record["bytes"]),
                        mock.patch.object(module, "FROZEN_SHARED_CONFIG_SHA256", shared_record["sha256"]),
                        mock.patch.object(module, live_attribute, decoy_live),
                    ):
                        with self.assertRaisesRegex(ValueError, "live .* artifact"):
                            module.load_config(config_path)

    def test_legacy_source_drift_falls_back_only_to_verified_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public = root / "runs" / "exp-058-paired-oof-production"
            private = root / "private" / "exp-058-paired-oof-production"
            frozen = public / "frozen-sources"
            frozen.mkdir(parents=True)
            private.mkdir(parents=True)
            live_source = root / "live-runner.py"
            live_source.write_text("new-source\n")
            old_source = frozen / "runner.py"
            old_source.write_text("old-source\n")
            prerequisite = root / "prerequisite.json"
            prerequisite.write_text("{}\n")
            train = root / "train.jsonl"
            train.write_text("synthetic\n")
            config_path = root / "config.json"
            expected_old = {
                "path": str(live_source.relative_to(root)),
                "bytes": old_source.stat().st_size,
                "sha256": hashlib.sha256(old_source.read_bytes()).hexdigest(),
            }
            config = {
                "schema_version": runner.LEGACY_CONFIG_SCHEMA,
                "experiment_id": runner.LEGACY_EXPERIMENT_ID,
                "tier": "Major",
                "stage": runner.LEGACY_STAGE,
                "authorization": {
                    "fold_ids": [0, 1, 2, 3, 4],
                    "model_seed": 42,
                    "assembly": True,
                    "full_oof_training": True,
                    "heldout_forward": True,
                    "model_loading": True,
                    "calibration": False,
                    "metrics": False,
                    "oracle_analysis": False,
                    "router_training": False,
                    "test_access": False,
                    "validation_access": False,
                },
                "execution": {
                    "fold_ids": [0, 1, 2, 3, 4],
                    "m1_epochs": 4,
                    "m3_epochs": 2,
                },
                "implementation": {"runner": expected_old},
                "prerequisites": {"synthetic": record(root, prerequisite)},
                "data": {"train": record(root, train)},
                "outputs": {
                    "public_run_dir": str(public.relative_to(root)),
                    "private_run_dir": str(private.relative_to(root)),
                },
            }
            config_path.write_text(json.dumps(config, sort_keys=True))
            frozen_config = frozen / "config.json"
            frozen_config.write_bytes(config_path.read_bytes())

            for module in (runner, verifier):
                frozen_records = {
                    "config": record(root, frozen_config),
                    "runner": record(root, old_source),
                }
                (public / "run.json").write_text(
                    json.dumps(
                        {
                            "experiment_id": module.LEGACY_EXPERIMENT_ID,
                            "stage": module.LEGACY_STAGE,
                            "status": "CompletedAwaitingVerification",
                            "frozen_sources": frozen_records,
                        }
                    )
                )
                (public / "verification.json").write_text(
                    json.dumps({"status": "Passed", "failed_count": 0})
                )
                with (
                    mock.patch.object(module, "PROJECT_ROOT", root),
                    mock.patch.object(module, "LEGACY_PUBLIC_RUN", public),
                    mock.patch.object(module, "LEGACY_PRIVATE_RUN", private),
                ):
                    loaded = module.load_config(config_path)
                self.assertTrue(loaded["_legacy_frozen_source_fallback"])
                if module is runner:
                    self.assertTrue(loaded["_archive_only"])

    def test_runner_has_no_top_level_model_library_imports(self) -> None:
        tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
        imports = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[0])
        self.assertFalse({"mlx", "mlx_lm", "numpy", "torch", "transformers"} & set(imports))

    def test_verifier_imports_no_model_libraries_or_runner(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        import_roots = {name.split(".")[0] for name in imports}
        self.assertFalse({"mlx", "mlx_lm", "torch", "transformers"} & import_roots)
        self.assertFalse(
            any(name.endswith("run_exp058_oof_production") for name in imports)
        )


if __name__ == "__main__":
    unittest.main()
