from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_oof_replication_preflight.py"
VERIFIER_PATH = MODULE_DIR / "verify_oof_replication_preflight.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_module("oof_replication_preflight_runner_under_test", RUNNER_PATH)
verifier = load_module("oof_replication_preflight_verifier_under_test", VERIFIER_PATH)


def record(name: str) -> dict[str, object]:
    return {"path": f"synthetic/{name}", "bytes": 1, "sha256": "1" * 64}


def config_for(module, experiment_id: str = "EXP-061") -> dict[str, object]:
    identity = module.IDENTITIES[experiment_id]
    seed = identity["seed"]
    preflight_attempt = "attempt-2"
    formal_attempt = "attempt-1"
    return {
        "schema_version": module.CONFIG_SCHEMA,
        "experiment_id": experiment_id,
        "rq_id": module.RQ_ID,
        "tier": "Major",
        "stage": module.STAGE,
        "run_id": identity["preflight_run_id"],
        "formal_run_id": identity["formal_run_id"],
        "attempt_id": preflight_attempt,
        "formal_attempt_id": formal_attempt,
        "authorization": {"model_seed": seed, **module.AUTHORIZATION_TEMPLATE},
        "execution": {
            "model_seed": seed,
            **module.V2_EXECUTION,
        },
        "seed_contract": module.expected_seed_contract(seed),
        "data": {
            "train": {
                "path": module.FROZEN_TRAIN_PATH,
                "bytes": 1,
                "sha256": module.FROZEN_TRAIN_SHA256,
            },
            "protocol_id": "DATA-SO-TASK-V1",
            "label_order": list(module.LABELS),
        },
        "implementation": {
            "protocol": {
                "path": module.FORMAL_PROTOCOL_PATHS[experiment_id],
                "bytes": 1,
                "sha256": "1" * 64,
            },
            **{
                name: {"path": path, "bytes": 1, "sha256": "1" * 64}
                for name, path in module.FORMAL_IMPLEMENTATION_PATHS.items()
            },
        },
        "preflight_implementation": {
            name: {"path": path, "bytes": 1, "sha256": "1" * 64}
            for name, path in module.PREFLIGHT_IMPLEMENTATION_PATHS.items()
        },
        "prerequisites": {
            **{
                name: record(f"prerequisite-{name}")
                for name in module.PREREQUISITE_KEYS
            },
            "fold_manifest": {
                "path": module.FROZEN_FOLD_MANIFEST_PATH,
                "bytes": 1,
                "sha256": module.FROZEN_FOLD_MANIFEST_SHA256,
            },
            "shared_config": {
                "path": module.FROZEN_SHARED_CONFIG_PATH,
                "bytes": module.FROZEN_SHARED_CONFIG_BYTES,
                "sha256": module.FROZEN_SHARED_CONFIG_SHA256,
            },
        },
        "outputs": module.expected_outputs(identity["preflight_run_id"], preflight_attempt),
        "formal_outputs": module.expected_outputs(identity["formal_run_id"], formal_attempt),
        "m1": copy.deepcopy(module.V2_M1),
        "m3": copy.deepcopy(module.V2_M3),
        "resources": copy.deepcopy(module.V2_RESOURCES),
    }


def synthetic_fold(module, seed: int) -> tuple[dict[str, object], dict[str, object]]:
    seeded = lambda field: module.canonical_digest({"seed": seed, "field": field})
    base = "a" * 64
    manifest = "b" * 64
    m1_rng = module.m1_rng_state_digest(module.expected_seed_contract(seed))
    m1 = {
        "model_seed": seed,
        "base_asset_manifest_sha256": base,
        "fold_manifest_sha256": manifest,
        "m1_classifier_init_sha256": seeded("m1_classifier"),
        "m1_rng_state_digest": m1_rng,
        "m1_initialization_state_sha256": module.initialization_state_sha256(
            "m1",
            {"m1_classifier_init_sha256": seeded("m1_classifier"), "m1_rng_state_digest": m1_rng},
        ),
        "m1_batch_order_sha256": seeded("m1_batch"),
    }
    m3_rng = module.m3_rng_state_digest(module.expected_seed_contract(seed))
    m3_state_input = {
        "m3_lora_a_init_sha256": seeded("m3_lora_a"),
        "m3_lora_b_init_sha256": "f" * 64,
        "m3_lora_combined_init_sha256": seeded("m3_lora_combined"),
        "m3_classifier_head_init_sha256": seeded("m3_head"),
        "m3_base_sentinel_sha256": "3" * 64,
        "m3_rng_state_digest": m3_rng,
    }
    m3 = {
        "model_seed": seed,
        "base_asset_manifest_sha256": base,
        "fold_manifest_sha256": manifest,
        **m3_state_input,
        "m3_initialization_state_sha256": module.initialization_state_sha256(
            "m3", m3_state_input
        ),
        "m3_batch_order_sha256": seeded("m3_batch"),
        "m3_lora_b_zero_initialized": True,
    }
    return m1, m3


class OofReplicationPreflightSyntheticTests(unittest.TestCase):
    def test_seed_43_and_44_identity_contracts_are_exact(self) -> None:
        for module in (runner, verifier):
            for experiment_id, seed in (("EXP-061", 43), ("EXP-062", 44)):
                config = config_for(module, experiment_id)
                identity = module.validate_identity(config)
                self.assertEqual(identity["seed"], seed)
                self.assertEqual(config["seed_contract"]["m3_lora_seed"], seed + 100000)

    def test_seed_or_output_path_drift_is_rejected(self) -> None:
        for module in (runner, verifier):
            wrong_seed = config_for(module)
            wrong_seed["seed_contract"]["torch_seed"] = 44
            with self.assertRaises(ValueError):
                module.validate_identity(wrong_seed)

            wrong_path = config_for(module)
            wrong_path["formal_outputs"]["public_attempt_dir"] += "-other"
            with self.assertRaises(ValueError):
                module.validate_identity(wrong_path)

    def test_rng_and_initialization_digests_change_across_seeds(self) -> None:
        for module in (runner, verifier):
            contract_43 = module.expected_seed_contract(43)
            contract_44 = module.expected_seed_contract(44)
            self.assertNotEqual(
                module.m1_rng_state_digest(contract_43), module.m1_rng_state_digest(contract_44)
            )
            self.assertNotEqual(
                module.m3_rng_state_digest(contract_43), module.m3_rng_state_digest(contract_44)
            )

    def test_sample_order_digest_is_order_sensitive_and_requires_permutations(self) -> None:
        ids = ["row-a", "row-b", "row-c"]
        for module in (runner, verifier):
            first = module.sample_order_digest(ids, [[0, 1, 2], [2, 1, 0]])
            second = module.sample_order_digest(ids, [[2, 1, 0], [0, 1, 2]])
            self.assertNotEqual(first, second)
            with self.assertRaises(ValueError):
                module.sample_order_digest(ids, [[0, 0, 2]])

    def test_manifest_matches_formal_expected_by_fold_schema(self) -> None:
        for module in (runner, verifier):
            config = config_for(module)
            m1, m3 = synthetic_fold(module, 43)
            fold = module.assemble_fold(m1, m3)
            manifest = module.assemble_manifest(
                config, {str(fold_id): copy.deepcopy(fold) for fold_id in range(5)}
            )
            self.assertEqual(manifest["run_id"], config["formal_run_id"])
            self.assertEqual(manifest["attempt_id"], config["formal_attempt_id"])
            self.assertEqual(manifest["schema_version"], "exp-oof-initialization-manifest-v1")
            self.assertTrue(manifest["cross_seed_gate"]["required_before_formal_training"])
            expected_by_fold = {
                fold_id: {
                    key: value
                    for key, value in values.items()
                    if key != "m3_lora_b_zero_initialized"
                }
                for fold_id, values in manifest["folds"].items()
            }
            self.assertEqual(set(expected_by_fold), {str(index) for index in range(5)})
            for values in expected_by_fold.values():
                self.assertEqual(set(values), {"model_seed", *module.INIT_HASH_FIELDS})

    def test_exact_scientific_and_frozen_source_contracts_reject_drift(self) -> None:
        for module in (runner, verifier):
            config = config_for(module)
            config["m1"]["batch_size"] = 8
            with self.assertRaisesRegex(ValueError, "M1/M3"):
                module.validate_identity(config)

    def test_every_formal_and_preflight_implementation_path_substitution_is_rejected(self) -> None:
        for module in (runner, verifier):
            for experiment_id in ("EXP-061", "EXP-062"):
                baseline = config_for(module, experiment_id)
                for section, keys in (
                    ("implementation", module.FORMAL_IMPLEMENTATION_KEYS),
                    ("preflight_implementation", module.PREFLIGHT_IMPLEMENTATION_KEYS),
                ):
                    for key in keys:
                        changed = copy.deepcopy(baseline)
                        changed[section][key]["path"] = f"synthetic/decoy-{section}-{key}"
                        with self.subTest(
                            module=module.__name__, experiment=experiment_id,
                            section=section, key=key,
                        ):
                            with self.assertRaisesRegex(
                                ValueError, f"{section}\\.{key} canonical path"
                            ):
                                module.validate_identity(changed)
            config = config_for(module)
            config["data"]["train"]["path"] = "data/validation.jsonl"
            with self.assertRaisesRegex(PermissionError, "frozen EXP-058"):
                module.validate_identity(config)

    def test_cross_seed_gate_requires_seed_sensitive_initialization(self) -> None:
        configs = {
            experiment_id: config_for(verifier, experiment_id)
            for experiment_id in ("EXP-061", "EXP-062")
        }
        bundles = {}
        for experiment_id, seed in (("EXP-061", 43), ("EXP-062", 44)):
            m1, m3 = synthetic_fold(verifier, seed)
            fold = verifier.assemble_fold(m1, m3)
            manifest = verifier.assemble_manifest(
                configs[experiment_id],
                {str(index): copy.deepcopy(fold) for index in range(5)},
            )
            bundles[experiment_id] = {
                "manifest": manifest,
                "manifest_record": record(f"{experiment_id}-manifest"),
                "verification_record": record(f"{experiment_id}-verification"),
            }
        report = verifier.build_cross_seed_report(configs, bundles)
        self.assertEqual(report["status"], "Passed")
        self.assertEqual(report["failed_count"], 0)
        self.assertEqual(set(report["members"]), {"EXP-061", "EXP-062"})

        broken = copy.deepcopy(bundles)
        broken["EXP-062"]["manifest"]["folds"]["0"]["m1_classifier_init_sha256"] = (
            broken["EXP-061"]["manifest"]["folds"]["0"]["m1_classifier_init_sha256"]
        )
        failed = verifier.build_cross_seed_report(configs, broken)
        self.assertEqual(failed["status"], "Failed")
        self.assertIn("fold_0_seed_sensitive_initialization", failed["failed_checks"])

    def test_public_allowlist_rejects_extra_csv_and_failure_seals_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            script_dir = root / "experiments" / "stack-overflow-emotion-gold" / "oof-router"
            script_dir.mkdir(parents=True)
            with (
                mock.patch.object(runner, "PROJECT_ROOT", root),
                mock.patch.object(runner, "SCRIPT_DIR", script_dir),
                mock.patch.object(runner, "PUBLIC_RUNS_ROOT", script_dir / "runs"),
                mock.patch.object(runner, "PRIVATE_RUNS_ROOT", script_dir / "private"),
            ):
                config = config_for(runner)
                run_dir = runner.preflight_run_dir(config)
                run_dir.mkdir(parents=True)
                runner.record_initialization_failure(config, "m1", 0, RuntimeError("synthetic"))
                with self.assertRaisesRegex(RuntimeError, "sealed"):
                    runner.assert_attempt_unsealed(config)
                original = (run_dir / "failure.json").read_bytes()
                runner.record_initialization_failure(config, "m1", 0, RuntimeError("replacement"))
                self.assertEqual((run_dir / "failure.json").read_bytes(), original)
                (run_dir / "extra.csv").write_text("forbidden\n")
                self.assertTrue(
                    any(item == "unexpected:extra.csv" for item in runner.public_artifact_violations(config))
                )

    def test_broken_symlink_input_record_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "broken.json").symlink_to(root / "missing.json")
            for module in (runner, verifier):
                with mock.patch.object(module, "PROJECT_ROOT", root):
                    with self.assertRaises((ValueError, FileNotFoundError)):
                        module.require_record(
                            {"path": "broken.json", "bytes": 1, "sha256": "1" * 64},
                            "synthetic",
                        )

    def test_full_load_binds_canonical_implementation_and_live_self(self) -> None:
        for module in (runner, verifier):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                script_dir = root / "experiments" / "stack-overflow-emotion-gold" / "oof-router"
                script_dir.mkdir(parents=True)
                with (
                    mock.patch.object(module, "PROJECT_ROOT", root),
                    mock.patch.object(module, "SCRIPT_DIR", script_dir),
                    mock.patch.object(module, "PUBLIC_RUNS_ROOT", script_dir / "runs"),
                    mock.patch.object(module, "PRIVATE_RUNS_ROOT", script_dir / "private"),
                ):
                    config = config_for(module)

                    def create(relative: str, content: str) -> dict[str, object]:
                        path = root / relative
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(content)
                        return {
                            "path": relative,
                            "bytes": path.stat().st_size,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        }

                    formal_paths = {
                        "protocol": module.FORMAL_PROTOCOL_PATHS[config["experiment_id"]],
                        **module.FORMAL_IMPLEMENTATION_PATHS,
                    }
                    config["implementation"] = {
                        name: create(path, f"formal {name}\n")
                        for name, path in formal_paths.items()
                    }
                    config["preflight_implementation"] = {
                        name: create(path, f"preflight {name}\n")
                        for name, path in module.PREFLIGHT_IMPLEMENTATION_PATHS.items()
                    }
                    train_record = create(module.FROZEN_TRAIN_PATH, "synthetic train\n")
                    fold_record = create(
                        module.FROZEN_FOLD_MANIFEST_PATH, "synthetic fold manifest\n"
                    )
                    shared_record = create(module.FROZEN_SHARED_CONFIG_PATH, "{}\n")
                    config["data"]["train"] = train_record
                    config["prerequisites"].update(
                        {
                            "shared_config": shared_record,
                            "fold_manifest": fold_record,
                            "consumer_contract": create(
                                "synthetic/consumer.json", "{}\n"
                            ),
                            "fold_verification": create(
                                "synthetic/fold-verification.json", "{}\n"
                            ),
                        }
                    )
                    config_path = root / "preflight-config.json"
                    config_path.write_text(json.dumps(config, sort_keys=True))
                    live_attribute = (
                        "LIVE_PREFLIGHT_RUNNER_PATH"
                        if module is runner
                        else "LIVE_PREFLIGHT_VERIFIER_PATH"
                    )
                    live_key = "runner" if module is runner else "verifier"
                    canonical_live = root / module.PREFLIGHT_IMPLEMENTATION_PATHS[live_key]
                    with (
                        mock.patch.object(module, "FROZEN_TRAIN_SHA256", train_record["sha256"]),
                        mock.patch.object(module, "FROZEN_FOLD_MANIFEST_SHA256", fold_record["sha256"]),
                        mock.patch.object(module, "FROZEN_SHARED_CONFIG_BYTES", shared_record["bytes"]),
                        mock.patch.object(module, "FROZEN_SHARED_CONFIG_SHA256", shared_record["sha256"]),
                        mock.patch.object(module, live_attribute, canonical_live),
                    ):
                        loaded = module.load_config(config_path)
                    self.assertEqual(loaded["experiment_id"], "EXP-061")

                    decoy_live = root / "synthetic" / "decoy-live.py"
                    decoy_live.write_text("decoy\n")
                    with (
                        mock.patch.object(module, "FROZEN_TRAIN_SHA256", train_record["sha256"]),
                        mock.patch.object(module, "FROZEN_FOLD_MANIFEST_SHA256", fold_record["sha256"]),
                        mock.patch.object(module, "FROZEN_SHARED_CONFIG_BYTES", shared_record["bytes"]),
                        mock.patch.object(module, "FROZEN_SHARED_CONFIG_SHA256", shared_record["sha256"]),
                        mock.patch.object(module, live_attribute, decoy_live),
                    ):
                        with self.assertRaisesRegex(ValueError, "live .* artifact"):
                            module.load_config(config_path)

    def test_lora_b_must_be_independently_confirmed_zero(self) -> None:
        for module in (runner, verifier):
            m1, m3 = synthetic_fold(module, 43)
            m3["m3_lora_b_zero_initialized"] = False
            with self.assertRaises(ValueError):
                module.assemble_fold(m1, m3)

    def test_verifier_has_no_runner_import(self) -> None:
        tree = ast.parse(VERIFIER_PATH.read_text(encoding="utf-8"))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        self.assertFalse(any("run_oof_replication_preflight" in name for name in imports))
        self.assertFalse(any("run_exp058_oof_production" in name for name in imports))

    def test_modules_have_no_eager_ml_runtime_imports(self) -> None:
        forbidden = {"torch", "numpy", "transformers", "mlx", "mlx_lm"}
        for path in (RUNNER_PATH, VERIFIER_PATH):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            top_imports: set[str] = set()
            for node in tree.body:
                if isinstance(node, ast.Import):
                    top_imports.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    top_imports.add(node.module.split(".")[0])
            self.assertFalse(top_imports & forbidden)

    def test_initialization_observers_contain_no_training_or_forward_calls(self) -> None:
        forbidden_fragments = (
            ".backward(",
            ".step(",
            "optimizer",
            ".logits",
            "tokenizer(",
            "wrapper(",
        )
        for module in (runner, verifier):
            for function in (
                module.observe_m1_initialization,
                module.observe_m3_initialization,
            ):
                source = inspect.getsource(function)
                for fragment in forbidden_fragments:
                    self.assertNotIn(fragment, source, (module.__name__, function.__name__, fragment))


if __name__ == "__main__":
    unittest.main()
