#!/usr/bin/env python3
"""Synthetic contract tests for the EXP-071 producer and independent verifier."""

from __future__ import annotations

import ast
import copy
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import inspect
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock
import zipfile


sys.dont_write_bytecode = True
TEST_DIR = Path(__file__).resolve().parent
MODULE_DIR = TEST_DIR.parent
RUNNER_PATH = MODULE_DIR / "run_exp071_drift.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp071_drift.py"


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


NUMPY_BEFORE_RUNNER = "numpy" in sys.modules
runner = load_module("exp071_runner_under_test", RUNNER_PATH)
NUMPY_AFTER_RUNNER = "numpy" in sys.modules

import numpy as np  # noqa: E402  synthetic values only


verifier = load_module("exp071_verifier_under_test", VERIFIER_PATH)


def attempt2_config() -> dict:
    value = runner.load_config(
        runner.ATTEMPT1_STATIC_CONFIG, expected_kind="static", allow_tbd=True
    )
    value = copy.deepcopy(value)
    value["schema_version"] = "exp-071-representation-drift-preflight-config-v2"
    value["attempt_id"] = "preflight-attempt-2"
    value["incident"] = copy.deepcopy(runner.INCIDENT_001)
    value["outputs"]["preflight_public_root"] = (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
        "exp-071-representation-drift/preflight-attempt-2"
    )
    value["outputs"]["preflight_private_root"] = (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
        "exp-071-representation-drift/preflight-attempt-2"
    )
    return value


class JsonAndImportBoundaryTests(unittest.TestCase):
    def test_runner_top_level_does_not_import_numeric_stack(self) -> None:
        self.assertFalse(NUMPY_BEFORE_RUNNER)
        self.assertFalse(NUMPY_AFTER_RUNNER)
        tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
        forbidden = {"numpy", "scipy", "sklearn", "mlx", "mlx_lm", "torch", "transformers"}
        observed = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                observed.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                observed.add(node.module.split(".")[0])
        self.assertFalse(observed & forbidden)

    def test_static_and_initialize_contain_no_value_loader(self) -> None:
        for function in (runner.static_stage, runner.initialize_stage):
            source = inspect.getsource(function)
            self.assertNotIn("np.load", source)
            self.assertNotIn("import numpy", source)
            self.assertNotIn("_load_ap5_deltas", source)
            self.assertNotIn("_load_row_contract", source)

    def test_strict_json_rejects_duplicates_and_nonfinite(self) -> None:
        with self.assertRaises(ValueError):
            runner.strict_json_bytes(b'{"a":1,"a":2}')
        with self.assertRaises(ValueError):
            runner.strict_json_bytes(b'{"a":NaN}')

    def test_canonical_json_matches_independent_verifier(self) -> None:
        value = {"z": [1, True, None], "a": "component-disjoint"}
        self.assertEqual(runner.canonical_json_bytes(value), verifier.canonical_json_bytes(value))

    def test_selective_parser_skips_forbidden_numeric_value(self) -> None:
        payload = b'{"status":"Passed","forbidden":1e999999,"tail":{"x":true}}'
        values, captures = runner.selective_json_scalars(payload, [("status",)])
        self.assertEqual(values, {("status",): "Passed"})
        self.assertEqual(captures, {})

    def test_selective_parser_extracts_only_allowlisted_probe_path_and_raw_results(self) -> None:
        results = {"main_contrasts": {"m3-s42:H-1": {"delta": {"five_label_macro_ap": 0.25}}, "private": 1e300}}
        payload = runner.canonical_json_bytes({"other": [1, 2], "results": results})
        allowed = ("results", "main_contrasts", "m3-s42:H-1", "delta", "five_label_macro_ap")
        values, captures = runner.selective_json_scalars(
            payload, [allowed], capture_paths=[("results",)]
        )
        self.assertEqual(values[allowed], 0.25)
        self.assertEqual(
            runner.bytes_sha256(captures[("results",)] + b"\n"),
            runner.bytes_sha256(runner.canonical_json_bytes(results)),
        )

    def test_selective_parser_rejects_duplicate_relevant_key(self) -> None:
        with self.assertRaises(ValueError):
            runner.selective_json_scalars(b'{"status":"Passed","status":"Failed"}', [("status",)])

    def test_independent_selector_exact_path_raw_span_and_forbidden_skip(self) -> None:
        results = {
            "main_contrasts": {
                "m3-s42:H-1": {"delta": {"five_label_macro_ap": 0.125}},
                "forbidden": 1e300,
            }
        }
        payload = verifier.canonical_json_bytes({"results": results, "tail": True})
        path = ("results", "main_contrasts", "m3-s42:H-1", "delta", "five_label_macro_ap")
        values, spans = verifier.select_json_scalars(payload, [path])
        self.assertEqual(values, {path: 0.125})
        self.assertEqual(
            verifier.bytes_sha256(spans[("results",)] + b"\n"),
            verifier.bytes_sha256(verifier.canonical_json_bytes(results)),
        )

    def test_independent_selector_rejects_duplicate_relevant_key(self) -> None:
        payload = b'{"results":{"x":1,"x":2}}'
        with self.assertRaises(ValueError):
            verifier.select_json_scalars(payload, [("results", "x")])


class FrozenMethodTests(unittest.TestCase):
    def test_attempt1_contract_remains_accepted_without_incident(self) -> None:
        value = runner.load_config(runner.ATTEMPT1_STATIC_CONFIG, expected_kind="static")
        self.assertEqual(value["attempt_id"], "preflight-attempt-1")
        self.assertNotIn("incident", value)

    def test_attempt2_schema_run_id_incident_and_fresh_roots(self) -> None:
        value = attempt2_config()
        runner._validate_config_exact(value, "static", allow_tbd=True)
        self.assertEqual(value["run_id"], "exp-071-representation-drift-preflight")
        self.assertEqual(value["attempt_id"], "preflight-attempt-2")
        self.assertEqual(value["incident"], runner.INCIDENT_001)
        self.assertTrue(value["outputs"]["preflight_public_root"].endswith("preflight-attempt-2"))
        self.assertTrue(value["outputs"]["preflight_private_root"].endswith("preflight-attempt-2"))
        self.assertEqual(verifier._static_attempt(value), 2)

    def test_attempt2_incident_exact_schema_and_values_reject_tamper(self) -> None:
        value = attempt2_config()
        mutations = (
            ("id", "other"),
            ("failed_config", {**runner.INCIDENT_001["failed_config"], "bytes": 1}),
            ("failure_artifact", {**runner.INCIDENT_001["failure_artifact"], "sha256": "0" * 64}),
            ("root_cause", "other"),
            ("recovery_scope", "other"),
        )
        for key, replacement in mutations:
            changed = copy.deepcopy(value)
            changed["incident"][key] = replacement
            with self.assertRaises(ValueError, msg=key):
                runner._validate_config_exact(changed, "static", allow_tbd=True)
        changed = copy.deepcopy(value)
        changed["incident"]["extra"] = True
        with self.assertRaises(ValueError):
            runner._validate_config_exact(changed, "static", allow_tbd=True)

    def test_main_resolves_explicit_relative_config_before_dispatch(self) -> None:
        relative = Path("relative-config.json")
        expected = relative.resolve()
        with mock.patch.object(
            runner, "static_stage", return_value={"status": "CompletedAwaitingVerification"}
        ) as stage, redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(["--stage", "static", "--config", str(relative)]), 0)
        stage.assert_called_once_with(expected)

    def test_main_resolves_default_config_before_dispatch(self) -> None:
        relative = Path("default-attempt-2.json")
        expected = relative.resolve()
        with mock.patch.object(runner, "DEFAULT_STATIC_CONFIG", relative), mock.patch.object(
            runner, "static_stage", return_value={"status": "CompletedAwaitingVerification"}
        ) as stage, redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(["--stage", "static"]), 0)
        stage.assert_called_once_with(expected)

    def test_configs_share_final_method_digest(self) -> None:
        preflight = runner.load_config(
            runner.ATTEMPT1_STATIC_CONFIG, expected_kind="static", allow_tbd=True
        )
        formal = runner.load_config(
            runner.DEFAULT_FORMAL_CONFIG, expected_kind="formal", allow_tbd=True
        )
        expected = "f428523680acd2dd130bb78ac3bcdebbceec2b64ced18730e936323e685cc210"
        self.assertEqual(runner.method_sha256(preflight), expected)
        self.assertEqual(runner.method_sha256(formal), expected)
        self.assertEqual(verifier.method_sha256(preflight), expected)

    def test_condition_and_sanity_inventory(self) -> None:
        self.assertEqual(len(runner.CONDITION_ORDER), 15)
        self.assertEqual(len(runner.SANITY_CONDITIONS), 6)
        self.assertEqual(runner.CONDITION_ORDER[:9], tuple(f"s42:{p}" for p in runner.ALL_POINTS))

    def test_source_contract_digest_is_frozen_before_io(self) -> None:
        config = runner.load_config(
            runner.ATTEMPT1_STATIC_CONFIG, expected_kind="static", allow_tbd=True
        )
        self.assertEqual(
            runner.bytes_sha256(runner.canonical_json_bytes(config["source"])),
            runner.EXPECTED_SOURCE_SHA256,
        )

    def test_cli_has_only_frozen_stages(self) -> None:
        parser = runner.build_parser()
        for stage in ("static", "initialize", "analyze"):
            self.assertEqual(parser.parse_args(["--stage", stage]).stage, stage)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["--stage", "fit-fold"])

    def test_static_formal_cross_binding_rejects_tamper_in_both_implementations(self) -> None:
        static = runner.load_config(
            runner.ATTEMPT1_STATIC_CONFIG, expected_kind="static", allow_tbd=True
        )
        formal = runner.load_config(
            runner.DEFAULT_FORMAL_CONFIG, expected_kind="formal", allow_tbd=True
        )
        runner.validate_static_formal_contracts(static, formal)
        verifier.validate_static_formal_contracts(static, formal)
        mutations = (
            ("source", "phase_b_decision", "sha256"),
            ("environment", "python_version"),
            ("resources", "runner_wall_seconds"),
            ("outputs", "formal_public_root"),
        )
        for path in mutations:
            changed = copy.deepcopy(formal)
            target = changed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = "tampered" if not isinstance(target[path[-1]], int) else -1
            with self.assertRaises(ValueError, msg=str(path)):
                runner.validate_static_formal_contracts(static, changed)
            with self.assertRaises(ValueError, msg=str(path)):
                verifier.validate_static_formal_contracts(static, changed)

    def test_matrix_plan_rejects_seed43_shape_and_point_tamper(self) -> None:
        config = runner.load_config(
            runner.ATTEMPT1_STATIC_CONFIG, expected_kind="static", allow_tbd=True
        )
        runner.validate_matrix_plan(config["source"])
        verifier.validate_matrix_plan(config)
        for key, value in (("shape", [3360, 9, 2560]), ("points", list(runner.ALL_POINTS))):
            changed = copy.deepcopy(config)
            changed["source"]["matrices"][6][key] = value
            with self.assertRaises(ValueError):
                runner.validate_matrix_plan(changed["source"])
            with self.assertRaises(ValueError):
                verifier.validate_matrix_plan(changed)
        changed = copy.deepcopy(config)
        changed["source"]["matrices"][6]["artifact"]["path"] = "unexpected.npy"
        with self.assertRaises(ValueError):
            runner.validate_matrix_plan(changed["source"])

    def test_exact_config_gate_rejects_identity_resource_output_access_claim_and_source_tamper(self) -> None:
        config = runner.load_config(
            runner.ATTEMPT1_STATIC_CONFIG, expected_kind="static", allow_tbd=True
        )
        mutations = [
            (("run_id",), "other"),
            (("resources", "runner_wall_seconds"), 7201),
            (("outputs", "formal_public_root"), "elsewhere"),
            (("authorization", "model_loading_authorized"), True),
            (("access", "formal_root_creation"), True),
            (("claim_boundary",), config["claim_boundary"] + " widened"),
            (("source", "matrix_root"), "elsewhere"),
            (("implementation", "runner", "path"), "replacement.py"),
        ]
        for path, replacement in mutations:
            changed = copy.deepcopy(config)
            target = changed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = replacement
            with self.assertRaises((ValueError, PermissionError, EnvironmentError), msg=str(path)):
                runner._validate_config_exact(changed, "static", allow_tbd=True)

    def test_implementation_paths_reject_all_substitutes(self) -> None:
        config = runner.load_config(
            runner.ATTEMPT1_STATIC_CONFIG, expected_kind="static", allow_tbd=True
        )
        runner.validate_implementation_paths(config["implementation"])
        verifier.validate_implementation_paths(config["implementation"])
        for name in ("runner", "verifier", "tests"):
            changed = copy.deepcopy(config["implementation"])
            changed[name]["path"] = f"replacement/{name}.py"
            with self.assertRaises(ValueError):
                runner.validate_implementation_paths(changed)
            with self.assertRaises(ValueError):
                verifier.validate_implementation_paths(changed)

    def test_preflight_payload_replay_rejects_status_chain_and_snapshot_tamper(self) -> None:
        run_record = {"path": "static.json", "bytes": 1, "mode": "0644", "sha256": "1" * 64}
        verification_record = {
            "path": "static-verification.json",
            "bytes": 1,
            "mode": "0644",
            "sha256": "2" * 64,
        }
        completion_record = {
            "path": "no-result-complete.json",
            "bytes": 1,
            "mode": "0644",
            "sha256": "3" * 64,
        }
        input_record = {
            "logical_name": "input-contract-manifest.json",
            "bytes": 1,
            "mode": "0600",
            "sha256": "4" * 64,
        }
        preflight = {
            "static_run": run_record,
            "static_verification": verification_record,
            "no_result_completion": completion_record,
            "required_statuses": {
                "static_run": "CompletedAwaitingVerification",
                "static_verification": "Passed",
                "no_result_completion": "Complete",
            },
            "formal_execution_authorized_by_preflight": True,
        }
        static_config = {"claim_boundary": "frozen static boundary"}
        run = {
            "status": "CompletedAwaitingVerification",
            "method_sha256": runner.METHOD_SHA256,
            "source_snapshot_sha256": "a" * 64,
        }
        verification = {
            "status": "Passed",
            "passed_count": 1,
            "failed_count": 0,
            "run": run_record,
            "input_contract": input_record,
            "method_sha256": runner.METHOD_SHA256,
            "source_snapshot_sha256": "a" * 64,
            "representation_values_read": False,
            "probe_metric_values_read": False,
            "formal_root_created": False,
            "formal_execution_authorized": False,
        }
        completion = {
            "status": "Complete",
            "run": run_record,
            "verification": verification_record,
            "input_contract": input_record,
            "method_sha256": runner.METHOD_SHA256,
            "source_snapshot_sha256": "a" * 64,
            "representation_values_read": False,
            "probe_metric_values_read": False,
            "formal_execution_authorized": True,
            "exp071_complete": False,
            "exp072_authorized": False,
            "claim_boundary": static_config["claim_boundary"],
        }
        arguments = (
            preflight,
            static_config,
            run,
            verification,
            completion,
            run_record,
            verification_record,
            completion_record,
        )
        runner.validate_preflight_payloads(*arguments)
        mutations = (
            (0, "required_statuses", {"static_run": "Wrong"}),
            (3, "failed_count", 1),
            (4, "run", {**run_record, "sha256": "9" * 64}),
            (4, "source_snapshot_sha256", "b" * 64),
        )
        for argument_index, key, replacement in mutations:
            changed = [copy.deepcopy(item) for item in arguments]
            changed[argument_index][key] = replacement
            with self.assertRaises((ValueError, PermissionError), msg=f"{argument_index}:{key}"):
                runner.validate_preflight_payloads(*changed)

    def test_static_and_formal_snapshot_algorithm_excludes_preflight_chain(self) -> None:
        record = {"path": "source.json", "bytes": 1, "mode": "0644", "sha256": "a" * 64}
        static = {
            "stage": "no-result-preflight",
            "method_protocol": record,
            "implementation": {"runner": record},
            "source": {"anchor": record},
        }
        formal = copy.deepcopy(static)
        formal["stage"] = "formal"
        formal["preflight"] = {"completion": {**record, "path": "preflight.json"}}

        def fake_require(item):
            return Path(item["path"])

        def fake_artifact(path):
            return {"path": str(path), "bytes": 1, "mode": "0644", "sha256": "a" * 64}

        with mock.patch.object(runner, "require_record", side_effect=fake_require), mock.patch.object(
            runner, "artifact", side_effect=fake_artifact
        ):
            self.assertEqual(
                runner.source_identity_snapshot(static), runner.source_identity_snapshot(formal)
            )


class HeaderAndAtomicArtifactTests(unittest.TestCase):
    def test_npy_header_is_value_free_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.npy"
            np.save(path, np.arange(12, dtype="<f4").reshape(3, 4), allow_pickle=False)
            header = runner.read_npy_header(path)
            self.assertEqual(header["descr"], "<f4")
            self.assertEqual(header["shape"], [3, 4])
            self.assertFalse(header["fortran_order"])
            self.assertEqual(header["file_bytes"], path.stat().st_size)

    def test_uncompressed_npz_member_order_and_headers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle.npz"
            arrays = {
                "heldout_ordinals": np.zeros((5, 672), dtype="<i4"),
                "cosine_distance": np.zeros((15, 3360), dtype="<f8"),
                "relative_l2_distance": np.zeros((15, 3360), dtype="<f8"),
                "linear_cka": np.ones((15, 5), dtype="<f8"),
                "max_abs_difference": np.zeros((15, 5), dtype="<f8"),
            }
            runner._write_npz_part(path, arrays)
            config = runner.load_config(
                runner.ATTEMPT1_STATIC_CONFIG, expected_kind="static", allow_tbd=True
            )
            headers = runner.validate_geometry_bundle(path, config["method"])
            self.assertEqual(headers["member_order"], list(runner.PRIVATE_MEMBER_ORDER))
            with zipfile.ZipFile(path) as archive:
                self.assertTrue(all(item.compress_type == zipfile.ZIP_STORED for item in archive.infolist()))

    def test_compressed_npz_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "compressed.npz"
            np.savez_compressed(path, heldout_ordinals=np.zeros((1,), dtype="<i4"))
            with self.assertRaises(ValueError):
                runner.read_npz_headers(path)

    def test_atomic_json_is_canonical_private_and_no_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            runner.create_json_once(path, {"b": 2, "a": 1}, private=True)
            self.assertEqual(path.read_bytes(), b'{"a":1,"b":2}\n')
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                runner.create_json_once(path, {"a": 2}, private=True)
            self.assertEqual([item.name for item in Path(directory).iterdir()], ["record.json"])

    def test_atomic_json_link_failure_leaves_no_final_or_temporary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "record.json"
            with mock.patch.object(runner.os, "link", side_effect=OSError("synthetic")):
                with self.assertRaises(OSError):
                    runner.create_json_once(path, {"a": 1}, private=False)
            self.assertFalse(path.exists())
            self.assertEqual(list(root.iterdir()), [])

    def test_commit_part_does_not_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            part = root / "x.part"
            final = root / "x.bin"
            part.write_bytes(b"new")
            final.write_bytes(b"old")
            with self.assertRaises(FileExistsError):
                runner._commit_part(part, final)
            self.assertEqual(final.read_bytes(), b"old")

    def test_exact_inventory_rejects_extra_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            root.mkdir(mode=0o700)
            os.chmod(root, 0o700)
            (root / "expected").write_bytes(b"x")
            os.chmod(root / "expected", 0o600)
            runner.require_exact_inventory(root, ["expected"], private=True)
            (root / "extra").write_bytes(b"x")
            os.chmod(root / "extra", 0o600)
            with self.assertRaises(ValueError):
                runner.require_exact_inventory(root, ["expected"], private=True)


class GeometryFormulaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.x = np.asarray(
            [[1.0, 0.0, 2.0], [0.5, 2.0, -1.0], [2.0, 1.0, 0.5], [-1.0, 1.5, 2.5]],
            dtype=np.float64,
        )

    def assertPairParity(self, x: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
        produced = runner.compute_geometry_pair(x, z)
        independent = verifier.compute_geometry_pair(x, z)
        np.testing.assert_allclose(produced[0], independent[0], rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(produced[1], independent[1], rtol=0.0, atol=1e-12)
        self.assertAlmostEqual(produced[2], independent[2], places=12)
        self.assertAlmostEqual(produced[3], independent[3], places=12)
        return produced

    def test_identical_geometry(self) -> None:
        cosine, relative, cka, maximum = self.assertPairParity(self.x, self.x.copy())
        np.testing.assert_allclose(cosine, 0.0, atol=1e-15)
        np.testing.assert_allclose(relative, 0.0, atol=1e-15)
        self.assertAlmostEqual(cka, 1.0, places=14)
        self.assertEqual(maximum, 0.0)

    def test_positive_scaling_has_unit_cka_and_relative_l2_one(self) -> None:
        cosine, relative, cka, _ = self.assertPairParity(self.x, 2.0 * self.x)
        np.testing.assert_allclose(cosine, 0.0, atol=1e-15)
        np.testing.assert_allclose(relative, 1.0, atol=1e-15)
        self.assertAlmostEqual(cka, 1.0, places=14)

    def test_feature_shift_preserves_cka_but_changes_row_metrics(self) -> None:
        shifted = self.x + np.asarray([4.0, -2.0, 1.0])
        cosine, relative, cka, _ = self.assertPairParity(self.x, shifted)
        self.assertAlmostEqual(cka, 1.0, places=14)
        self.assertGreater(float(np.max(cosine)), 0.0)
        self.assertGreater(float(np.max(relative)), 0.0)

    def test_one_side_row_permutation_changes_cka(self) -> None:
        *_, cka, _ = self.assertPairParity(self.x, self.x[[2, 0, 3, 1]])
        self.assertLess(cka, 1.0)

    def test_zero_row_norm_is_rejected(self) -> None:
        value = self.x.copy()
        value[0] = 0.0
        with self.assertRaises(ValueError):
            runner.compute_geometry_pair(value, self.x)

    def test_constant_centered_geometry_is_rejected(self) -> None:
        value = np.ones((4, 3), dtype=np.float64)
        with self.assertRaises(ValueError):
            runner.compute_geometry_pair(value, value)

    def test_nonfinite_input_is_rejected(self) -> None:
        value = self.x.copy()
        value[0, 0] = np.nan
        with self.assertRaises(ValueError):
            runner.compute_geometry_pair(value, self.x)

    def test_distance_statistics_use_linear_percentiles_and_match_verifier(self) -> None:
        values = np.asarray([0.0, 1.0, 4.0, 9.0], dtype=np.float64)
        produced = runner.distance_statistics(values)
        self.assertEqual(produced, verifier.distance_statistics(values))
        self.assertEqual(produced["median"], 2.5)
        self.assertAlmostEqual(produced["p90"], 7.5, places=14)


class HeldoutAggregationAndSanityTests(unittest.TestCase):
    def test_partitions_are_sorted_complete_and_fold_local(self) -> None:
        ordinal = np.asarray([5, 0, 3, 2, 4, 1], dtype=np.int32)
        fold = np.asarray([0, 0, 1, 1, 2, 2], dtype=np.int8)
        parts = runner.heldout_partitions(ordinal, fold, folds=(0, 1, 2))
        self.assertEqual([item.tolist() for item in parts], [[0, 5], [2, 3], [1, 4]])

    def test_provider_receives_only_current_heldout_ordinals(self) -> None:
        partitions = [np.asarray([2 * fold, 2 * fold + 1], dtype=np.int32) for fold in range(5)]
        calls = []

        def provider(condition, fold, ordinals):
            calls.append((condition, fold, ordinals.copy()))
            base = np.stack([np.asarray([value + 1.0, 1.0, 2.0]) for value in ordinals])
            adapted = base.copy() if condition == "s42:H-1" else 1.1 * base
            return base, adapted

        arrays = runner.compute_geometry_bundle(
            partitions,
            provider,
            condition_order=("s42:H-1", "s42:H20"),
            sanity_conditions=frozenset({"s42:H-1"}),
        )
        self.assertEqual(len(calls), 10)
        for _condition, fold, observed in calls:
            np.testing.assert_array_equal(observed, partitions[fold])
        self.assertEqual(arrays["cosine_distance"].shape, (2, 10))
        np.testing.assert_array_equal(arrays["heldout_ordinals"], np.stack(partitions))

    def test_sanity_gate_uses_float64_maximum_and_stops(self) -> None:
        partitions = [np.asarray([2 * fold, 2 * fold + 1], dtype=np.int32) for fold in range(5)]

        def provider(_condition, _fold, ordinals):
            base = np.stack([np.asarray([value + 1.0, 1.0]) for value in ordinals])
            adapted = base.copy()
            adapted[0, 0] += 1.1e-5
            return base, adapted

        with self.assertRaises(runner.SanityGateError):
            runner.compute_geometry_bundle(
                partitions,
                provider,
                condition_order=("s42:H-1",),
                sanity_conditions=frozenset({"s42:H-1"}),
            )

    def test_pooled_quantile_is_not_average_of_fold_quantiles(self) -> None:
        arrays = {
            "cosine_distance": np.tile(np.asarray([0.0, 100.0, 1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 4.0, 4.0]), (15, 1)),
            "relative_l2_distance": np.tile(np.arange(10, dtype=np.float64), (15, 1)),
            "linear_cka": np.tile(np.linspace(0.90, 0.98, 5), (15, 1)),
            "max_abs_difference": np.zeros((15, 5), dtype=np.float64),
        }
        results = runner.build_results(arrays, np.linspace(-0.1, 0.1, 9))
        first = results["conditions"][runner.CONDITION_ORDER[0]]
        pooled = first["pooled_distance_statistics"]["cosine_distance"]["median"]
        average_fold_medians = np.mean(
            [item["cosine_distance"]["median"] for item in first["per_fold_distance_statistics"]]
        )
        self.assertNotEqual(pooled, average_fold_medians)

    def test_cka_uses_sample_sd(self) -> None:
        arrays = {
            "cosine_distance": np.zeros((15, 10), dtype=np.float64),
            "relative_l2_distance": np.zeros((15, 10), dtype=np.float64),
            "linear_cka": np.tile(np.asarray([0.1, 0.2, 0.3, 0.4, 0.5]), (15, 1)),
            "max_abs_difference": np.zeros((15, 5), dtype=np.float64),
        }
        result = runner.build_results(arrays, np.arange(9, dtype=np.float64))
        observed = result["conditions"][runner.CONDITION_ORDER[0]]["linear_cka"]["sample_sd"]
        self.assertAlmostEqual(observed, float(np.std([0.1, 0.2, 0.3, 0.4, 0.5], ddof=1)))


class SpearmanPrivacyAndLockTests(unittest.TestCase):
    def test_average_tie_ranks_match_verifier(self) -> None:
        values = np.asarray([3.0, 1.0, 1.0, 2.0])
        expected = np.asarray([4.0, 1.5, 1.5, 3.0])
        np.testing.assert_array_equal(runner.average_ranks(values), expected)
        np.testing.assert_array_equal(runner.average_ranks(values), verifier.average_ranks(values))

    def test_defined_spearman_matches_verifier(self) -> None:
        x = np.asarray([1.0, 2.0, 2.0, 4.0])
        y = np.asarray([4.0, 1.0, 1.0, 0.0])
        produced = runner.spearman_description(x, y)
        independent = verifier.spearman_description(x, y)
        self.assertEqual(produced["reason"], independent["reason"])
        self.assertAlmostEqual(produced["rho"], independent["rho"], places=12)

    def test_constant_spearman_is_valid_null(self) -> None:
        value = runner.spearman_description(np.ones(9), np.arange(9))
        self.assertEqual(value, {"rho": None, "reason": "constant_vector"})

    def test_public_privacy_allows_method_term_but_rejects_row_keys(self) -> None:
        runner.validate_public_payload({"claim_boundary": "component-disjoint method", "fold": 0})
        with self.assertRaises(PermissionError):
            runner.validate_public_payload({"component_id": "private"})
        with self.assertRaises(PermissionError):
            runner.validate_public_payload({"private_path": "phase-b-representation/private/x"})

    def test_public_privacy_rejects_row_length_array(self) -> None:
        with self.assertRaises(PermissionError):
            runner.validate_public_payload({"values": [0] * 672})

    def test_persistent_lockfile_is_not_treated_as_active_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "persistent.lock"
            path.write_bytes(b"")
            with runner._file_mutex(path, "synthetic"):
                self.assertTrue(path.exists())
            self.assertTrue(path.exists())

    def test_lock_contention_is_terminal_without_deleting_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "persistent.lock"

            def fake_flock(_descriptor, operation):
                if operation == runner.fcntl.LOCK_EX | runner.fcntl.LOCK_NB:
                    raise BlockingIOError

            with mock.patch.object(runner.fcntl, "flock", side_effect=fake_flock):
                with self.assertRaises(RuntimeError):
                    with runner._file_mutex(path, "synthetic"):
                        pass
            self.assertTrue(path.exists())

    def test_independent_verifier_persistent_lock_and_contention(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "verifier.lock"
            path.write_bytes(b"")
            with verifier._file_mutex(path, "synthetic verifier"):
                self.assertTrue(path.exists())
            self.assertTrue(path.exists())

            def fake_flock(_descriptor, operation):
                if operation == verifier.fcntl.LOCK_EX | verifier.fcntl.LOCK_NB:
                    raise BlockingIOError

            with mock.patch.object(verifier.fcntl, "flock", side_effect=fake_flock):
                with self.assertRaises(RuntimeError):
                    with verifier._file_mutex(path, "synthetic verifier"):
                        pass
            self.assertTrue(path.exists())

    def test_manifest_private_size_reaches_fixed_point(self) -> None:
        base = {"resources": {"elapsed_seconds": 1.0, "peak_rss_bytes": 1, "private_output_bytes": 0, "api_cost_usd": 0}}
        manifest, size = runner._manifest_with_stable_size(base, input_bytes=100, bundle_bytes=200)
        self.assertEqual(size, 300 + len(runner.canonical_json_bytes(manifest)))
        self.assertEqual(manifest["resources"]["private_output_bytes"], size)


if __name__ == "__main__":
    unittest.main(verbosity=2)
