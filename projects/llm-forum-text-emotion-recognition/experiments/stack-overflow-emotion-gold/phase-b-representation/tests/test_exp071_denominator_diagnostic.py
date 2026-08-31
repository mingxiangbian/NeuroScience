#!/usr/bin/env python3
"""Self-contained synthetic tests; no experiment source values are read."""

from __future__ import annotations

import ast
from contextlib import ExitStack, nullcontext, redirect_stdout
import copy
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.dont_write_bytecode = True
MODULE_DIR = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_module("denominator_producer_test", MODULE_DIR / "run_exp071_denominator_diagnostic.py")
NUMPY_IMPORTED_BY_RUNNER = "numpy" in sys.modules
verifier = load_module("denominator_verifier_test", MODULE_DIR / "verify_exp071_denominator_diagnostic.py")
import numpy as np


FORBIDDEN = ["ap5_probe_metrics", "labels", "component_codes", "component_ids", "sample_ids", "probabilities", "predictions", "private_probe_artifacts", "train_text", "raw_text", "model", "adapter", "tokenizer", "forward", "validation", "test", "test_gate", "exp069_smoke_representation_values", "outer_train_representation_values", "other_drift_metrics"]


def synthetic_config(kind):
    static = kind == "static"
    config = {
        "schema_version": f"exp-071-denominator-diagnostic-{'preflight' if static else 'formal'}-config-v1",
        "experiment_id": runner.EXPERIMENT_ID, "diagnostic_id": runner.DIAGNOSTIC_ID,
        "rq_id": "RQ-S4.2", "tier": "Minor technical failure diagnostic", "registered_at": "2026-08-30",
        "method_protocol": copy.deepcopy(runner.PROTOCOL_RECORD),
        "implementation": {name: {"path": path, "bytes": 1, "mode": "0644", "sha256": "a" * 64, "status": "Frozen"} for name, path in runner.IMPLEMENTATION_PATHS.items()},
        "incident": {"synthetic_incident": True}, "source": {"synthetic_source": True}, "method": {"synthetic_method": True},
        "environment": copy.deepcopy(runner.SAFE.EXPECTED_ENVIRONMENT), "resources": copy.deepcopy(runner.RESOURCES),
        "run_id": "exp-071-denominator-diagnostic" + ("-preflight" if static else ""),
        "attempt_id": "denominator-diagnostic" + ("-preflight" if static else "") + "-attempt-1",
        "stage": "no-result-preflight" if static else "formal-diagnostic",
        "authorization": runner.expected_authorization(kind), "outputs": runner.expected_outputs(kind),
        "claim_boundary": runner.STATIC_CLAIM if static else runner.DIAGNOSTIC_CLAIM,
    }
    if static:
        config["access"] = {"static_may_read": ["bound_artifact_bytes_for_identity", "config_and_terminal_metadata", "npy_npz_headers", "filesystem_modes_and_inventory", "package_metadata", "synthetic_fixtures"], "static_must_not_read": ["representation_values", "row_contract_values", *FORBIDDEN], "formal_root_creation": False}
    else:
        config["access"] = {"formal_may_read_after_activation": ["bound_representation_heldout_slices_until_first_denominator_failure", "row_contract_ordinal_and_fold_id_values", "bound_metadata_and_artifact_bytes_for_identity"], "formal_must_not_read": FORBIDDEN.copy(), "formal_model_load": False, "formal_forward": False, "formal_source_mutation": False, "currently_authorized": True}
        config["preflight"] = {key: {"path": key + ".json", "bytes": 1, "mode": "0644", "sha256": "b" * 64} for key in ("config", "static_run", "static_verification", "no_result_completion")}
        config["preflight"].update({"required_statuses": {"static_run": "CompletedAwaitingVerification", "static_verification": "Passed", "no_result_completion": "Complete"}, "diagnostic_execution_authorized_by_preflight": True})
    return config


class MathAndOrderTests(unittest.TestCase):
    def test_import_has_no_numpy_or_model_side_effect(self):
        self.assertFalse(NUMPY_IMPORTED_BY_RUNNER)
        tree = ast.parse((MODULE_DIR / "run_exp071_denominator_diagnostic.py").read_text())
        modules = {alias.name.split(".")[0] for node in tree.body if isinstance(node, ast.Import) for alias in node.names}
        self.assertFalse(modules & {"numpy", "scipy", "torch", "mlx", "transformers"})

    def test_scalar_categories_and_negative_zero(self):
        for value, expected in ((0.0, "zero"), (-0.0, "zero"), (2.0, "finite_positive"), (float("nan"), "nonfinite"), (float("inf"), "nonfinite"), (-float("inf"), "nonfinite")):
            self.assertEqual(runner.classify_nonnegative(value), expected)
            self.assertEqual(verifier.classify_nonnegative(value), expected)
        with self.assertRaises(ValueError):
            runner.classify_nonnegative(-1.0)

    def test_constant_pair_is_zero_zero_zero(self):
        x = np.ones((4, 3))
        expected = {"norm_x": "zero", "norm_z": "zero", "denominator": "zero"}
        self.assertEqual(runner.denominator_categories(x, x), expected)
        self.assertEqual(verifier.denominator_categories(x, x), expected)

    def test_one_constant_pair_keeps_three_categories(self):
        x, z = np.ones((4, 3)), np.arange(12, dtype=np.float64).reshape(4, 3)
        expected = {"norm_x": "zero", "norm_z": "finite_positive", "denominator": "zero"}
        self.assertEqual(runner.denominator_categories(x, z), expected)
        self.assertEqual(verifier.denominator_categories(x, z), expected)

    def test_finite_varying_pair_is_positive(self):
        x = np.arange(12, dtype=np.float64).reshape(4, 3)
        expected = {key: "finite_positive" for key in ("norm_x", "norm_z", "denominator")}
        self.assertEqual(runner.denominator_categories(x, x * 2), expected)
        self.assertEqual(verifier.denominator_categories(x, x * 2), expected)

    def test_finite_overflow_is_nonfinite_without_exact_values(self):
        x = np.asarray([[1e200, 1e200], [-1e200, -1e200]])
        expected = {key: "nonfinite" for key in ("norm_x", "norm_z", "denominator")}
        self.assertEqual(runner.denominator_categories(x, x), expected)
        self.assertEqual(verifier.denominator_categories(x, x), expected)

    def test_nonfinite_input_is_unexpected_failure(self):
        x = np.asarray([[1.0, np.nan], [2.0, 3.0]])
        with self.assertRaises(ValueError):
            runner.denominator_categories(x, x)
        with self.assertRaises(ValueError):
            verifier.denominator_categories(x, x)

    def test_original_order_and_early_stop(self):
        parts = [np.asarray([2 * f, 2 * f + 1]) for f in range(5)]
        calls, checks = [], []
        def pair(condition, fold, rows):
            calls.append((condition, fold, rows.tolist()))
            x = np.ones((2, 2)) if len(calls) == 7 else np.asarray([[1., 2.], [3., 4.]])
            return x, x
        value = runner.first_denominator_failure(parts, pair, budget_check=lambda: checks.append(True))
        self.assertEqual(value["condition"], "s42:H7")
        self.assertEqual(value["fold"], 1)
        self.assertEqual(value["pairs_examined"], 7)
        self.assertEqual(len(calls), 7)
        self.assertEqual(len(checks), 7)
        for _, fold, rows in calls:
            self.assertEqual(rows, parts[fold].tolist())

    def test_all_75_positive_is_failed_not_localization(self):
        parts = [np.asarray([0, 1])] * 5
        x = np.asarray([[1., 2.], [3., 4.]])
        calls = []
        def pair(*args):
            calls.append(args)
            return x, x
        with self.assertRaisesRegex(RuntimeError, "failure_not_reproduced"):
            runner.first_denominator_failure(parts, pair)
        self.assertEqual(len(calls), 75)


class ConfigAndIoTests(unittest.TestCase):
    def test_self_contained_config_gate_and_access_tamper(self):
        for kind in ("static", "diagnostic"):
            config = synthetic_config(kind)
            with mock.patch.multiple(runner, METHOD_SHA256=runner.digest(config["method"]), SOURCE_SHA256=runner.digest(config["source"]), INCIDENT_SHA256=runner.digest(config["incident"])):
                runner.validate_config(config, kind)
                changed = copy.deepcopy(config)
                access_key = "static_may_read" if kind == "static" else "formal_may_read_after_activation"
                changed["access"][access_key].append("ap5")
                with self.assertRaises(PermissionError):
                    runner.validate_config(changed, kind)
                with self.assertRaises(ValueError):
                    runner.validate_config(config, "other")

    def test_preflight_records_are_four_field_only(self):
        config = synthetic_config("diagnostic")
        config["preflight"]["static_run"]["status"] = "Passed"
        with mock.patch.multiple(runner, METHOD_SHA256=runner.digest(config["method"]), SOURCE_SHA256=runner.digest(config["source"]), INCIDENT_SHA256=runner.digest(config["incident"])):
            with self.assertRaises(ValueError):
                runner.validate_config(config, "diagnostic")

    def test_cli_resolves_explicit_and_default_paths(self):
        for arguments in (["--stage", "static", "--config", "relative.json"], ["--stage", "static"]):
            with mock.patch.object(runner, "DEFAULT_STATIC_CONFIG", Path("default.json")), mock.patch.object(runner, "static_stage", return_value={"status": "ok"}) as stage, redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(arguments), 0)
                self.assertTrue(stage.call_args.args[0].is_absolute())

    def test_atomic_json_no_clobber_no_temporary(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "record.json"
            runner.create_json_once(path, {"status": "Sealed"}, private=True)
            with self.assertRaises(FileExistsError):
                runner.create_json_once(path, {"status": "other"}, private=True)
            self.assertEqual([p.name for p in Path(folder).iterdir()], ["record.json"])
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_localization_and_public_term_privacy(self):
        good = {"condition": "s42:H-1", "fold": 0, "pairs_examined": 1, "norm_x": "zero", "norm_z": "zero", "denominator": "zero"}
        runner.validate_localization(good)
        verifier.validate_localization(good)
        for changed in ({**good, "norm_x": 0.0}, {**good, "pairs_examined": 2}):
            with self.assertRaises(ValueError):
                runner.validate_localization(changed)
        with self.assertRaises(ValueError):
            runner.validate_public_payload({"path": "/Users/private/data"})
        runner.validate_public_payload({"execution": {"command": [runner.SAFE.EXPECTED_ENVIRONMENT["python_executable"]]}})


class LifecycleIntegrationTests(unittest.TestCase):
    def test_synthetic_producer_payloads_are_consumed_by_independent_verifier(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            root = Path(folder)
            paths = {(True, False): root / "static-public", (True, True): root / "static-private", (False, False): root / "formal-public", (False, True): root / "formal-private"}
            static, active = synthetic_config("static"), synthetic_config("diagnostic")
            static_path, active_path, test_path = root / "static-config.json", root / "active-config.json", root / "synthetic-test.py"
            runner.create_json_once(static_path, static)
            test_path.write_text("synthetic\n")
            def fake_artifact(path, *, logical_name=None):
                p = Path(path)
                value = {"bytes": p.stat().st_size, "mode": f"{stat.S_IMODE(p.stat().st_mode):04o}", "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                value["logical_name" if logical_name else "path"] = logical_name or p.name
                return value
            snapshot = {"artifact_count": 1, "artifacts": [{"path": "synthetic-source", "bytes": 1, "mode": "0600", "sha256": "a" * 64}], "sha256": "b" * 64}
            headers = {"matrix_headers": [{"worker_id": "base", "shape": [2, 1, 2]}], "row_contract_headers": {"member_order": ["ordinal", "fold_id", "component_code"], "members": {}}}
            synthetic = {"status": "Passed", "tests_run": 1, "test_artifact": fake_artifact(test_path), "command_sha256": "c" * 64}
            stack.enter_context(mock.patch.object(runner, "artifact", side_effect=fake_artifact))
            stack.enter_context(mock.patch.object(verifier, "artifact", side_effect=fake_artifact))
            stack.enter_context(mock.patch.object(runner, "_root", side_effect=lambda config, private, static: paths[(static, private)]))
            stack.enter_context(mock.patch.object(verifier, "_root", side_effect=lambda config, kind, private: paths[(kind == "static", private)]))
            stack.enter_context(mock.patch.object(runner, "load_config", side_effect=lambda path, kind: static if kind == "static" else active))
            stack.enter_context(mock.patch.object(runner, "require_implementation"))
            stack.enter_context(mock.patch.object(runner, "source_identity_snapshot", return_value=snapshot))
            inspect = stack.enter_context(mock.patch.object(runner, "inspect_sources", return_value=(headers["matrix_headers"], headers["row_contract_headers"])))
            stack.enter_context(mock.patch.object(runner.SAFE, "_require_static_import_boundary"))
            stack.enter_context(mock.patch.object(runner.SAFE, "_environment_record"))
            stack.enter_context(mock.patch.object(runner.SAFE, "_require_private_ignore"))
            stack.enter_context(mock.patch.object(runner.SAFE, "run_synthetic_tests", return_value=synthetic))
            stack.enter_context(mock.patch.object(runner.SAFE.shutil, "disk_usage", return_value=SimpleNamespace(free=2**32)))
            stack.enter_context(mock.patch.object(runner, "diagnostic_lock", side_effect=lambda: nullcontext()))
            runner.static_stage(static_path)
            run_path, input_path = verifier._validate_static_payloads(static_path, static, snapshot, headers, synthetic)
            verification_path = paths[(True, False)] / "static-verification.json"
            completion_path = paths[(True, False)] / "no-result-complete.json"
            verification = verifier._static_verification_payload(static_path, static, snapshot, run_path, input_path, synthetic)
            runner.create_json_once(verification_path, verification)
            completion = verifier._static_completion_payload(static_path, static, snapshot, run_path, input_path, verification_path)
            runner.create_json_once(completion_path, completion)
            active["preflight"] = {"config": fake_artifact(static_path), "static_run": fake_artifact(run_path), "static_verification": fake_artifact(verification_path), "no_result_completion": fake_artifact(completion_path), "required_statuses": {"static_run": "CompletedAwaitingVerification", "static_verification": "Passed", "no_result_completion": "Complete"}, "diagnostic_execution_authorized_by_preflight": True}
            runner.create_json_once(active_path, active)
            stack.enter_context(mock.patch.object(runner, "require_preflight", return_value=(static, completion)))
            runner.initialize_stage(active_path)
            parts = [np.asarray([0, 1])] * 5
            stack.enter_context(mock.patch.object(runner, "load_partitions", return_value=parts))
            stack.enter_context(mock.patch.object(runner, "source_pair_loader", return_value=lambda *args: (np.ones((2, 2)), np.ones((2, 2)))))
            execution = {"started_at_utc": "2026-08-30T00:00:00Z", "ended_at_utc": "2026-08-30T00:00:01Z", "command": [active["environment"]["python_executable"], runner.IMPLEMENTATION_PATHS["runner"], "--stage", "diagnose", "--config", active["outputs"]["active_config_path"]], "cwd": ".", "git_commit": "d" * 40, "git_dirty": True}
            stack.enter_context(mock.patch.object(runner, "execution_record", return_value=execution))
            report = runner.diagnose_stage(active_path)
            self.assertEqual(report["localization"]["pairs_examined"], 1)
            manifest, checked = verifier._validate_diagnostic_payloads(active_path, active, snapshot, headers, completion_path)
            self.assertEqual(checked, report)
            self.assertEqual(set(paths[(False, True)].iterdir()), {paths[(False, True)] / "input-manifest.json", paths[(False, True)] / "diagnostic-manifest.json"})
            self.assertGreaterEqual(inspect.call_count, 3)
            self.assertNotIn("geometry", str(manifest.keys()))
            diagnostic_verification_path = paths[(False, False)] / "verification.json"
            diagnostic_verification = verifier._diagnostic_verification_payload(active_path, active, snapshot, completion_path, report["localization"])
            runner.create_json_once(diagnostic_verification_path, diagnostic_verification)
            self.assertEqual(diagnostic_verification, verifier._diagnostic_verification_payload(active_path, active, snapshot, completion_path, report["localization"]))
            diagnostic_completion = verifier._diagnostic_completion_payload(active_path, active, snapshot, diagnostic_verification_path, report["localization"])
            runner.create_json_once(paths[(False, False)] / "diagnostic-complete.json", diagnostic_completion)
            self.assertEqual(diagnostic_completion, verifier._diagnostic_completion_payload(active_path, active, snapshot, diagnostic_verification_path, report["localization"]))
            self.assertTrue(diagnostic_completion["diagnostic_complete"])
            self.assertFalse(diagnostic_completion["exp071_complete"])
            changed = copy.deepcopy(report)
            changed["localization"]["norm_x"] = 0.0
            (paths[(False, False)] / "run.json").write_bytes(runner.canonical_json_bytes(changed))
            with self.assertRaises(ValueError):
                verifier._validate_diagnostic_payloads(active_path, active, snapshot, headers, completion_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
