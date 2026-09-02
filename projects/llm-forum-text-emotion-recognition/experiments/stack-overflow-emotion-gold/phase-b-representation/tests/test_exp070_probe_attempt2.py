#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
import inspect
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import importlib.util


MODULE_DIR = Path(__file__).resolve().parent.parent
RECOVERY_PATH = MODULE_DIR / "verify_exp070_probe_attempt2.py"
SOURCE_VERIFIER_PATH = MODULE_DIR / "verify_exp070_probe.py"
SOURCE_CONFIG_PATH = MODULE_DIR / "configs" / "exp-070-formal-probe.json"
RECOVERY_CONFIG_PATH = (
    MODULE_DIR / "configs" / "exp-070-formal-probe-verification-attempt-2.json"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RECOVERY = load_module("exp070_probe_attempt2_under_test", RECOVERY_PATH)
SOURCE = load_module("exp070_probe_frozen_verifier_under_test", SOURCE_VERIFIER_PATH)
SOURCE_CLAIM_BOUNDARY = json.loads(SOURCE_CONFIG_PATH.read_text(encoding="utf-8"))[
    "claim_boundary"
]


def safe_payload(**extra):
    return {"claim_boundary": SOURCE_CLAIM_BOUNDARY, "status": "Passed", **extra}


class Exp070ProbeAttempt2Tests(unittest.TestCase):
    def test_01_original_predicate_reproduces_exact_false_positive(self) -> None:
        self.assertEqual(
            RECOVERY.bytes_sha256(SOURCE_CLAIM_BOUNDARY.encode("utf-8")),
            RECOVERY.EXPECTED_SOURCE_CLAIM_BOUNDARY_SHA256,
        )
        self.assertTrue(SOURCE._public_sensitive(SOURCE_CLAIM_BOUNDARY))
        self.assertEqual(SOURCE_CLAIM_BOUNDARY.lower().count("component-"), 1)
        self.assertFalse(
            any(
                marker in SOURCE_CLAIM_BOUNDARY.lower()
                for marker in (
                    "/users/",
                    "phase-b-representation/private/",
                    "sample-",
                )
            )
        )

    def test_02_adapter_allows_only_exact_root_claim_boundary(self) -> None:
        original = SOURCE._public_sensitive
        with RECOVERY.patched_public_privacy(SOURCE, SOURCE_CLAIM_BOUNDARY):
            self.assertFalse(SOURCE._public_sensitive(safe_payload(interval=[0.1, 0.2])))
            self.assertTrue(
                SOURCE._public_sensitive(
                    {"note": SOURCE_CLAIM_BOUNDARY, "claim_boundary": "safe"}
                )
            )
            self.assertTrue(
                SOURCE._public_sensitive(
                    {
                        "claim_boundary": SOURCE_CLAIM_BOUNDARY,
                        "meta": {"claim_boundary": SOURCE_CLAIM_BOUNDARY},
                    }
                )
            )
            self.assertTrue(SOURCE._public_sensitive([SOURCE_CLAIM_BOUNDARY]))
        self.assertIs(SOURCE._public_sensitive, original)

    def test_03_adapter_rejects_boundary_value_and_type_drift(self) -> None:
        variants = (
            {},
            {"claim_boundary": None},
            {"claim_boundary": [SOURCE_CLAIM_BOUNDARY]},
            {"claim_boundary": SOURCE_CLAIM_BOUNDARY + " "},
            {"claim_boundary": " " + SOURCE_CLAIM_BOUNDARY},
            {"claim_boundary": SOURCE_CLAIM_BOUNDARY.replace("component-disjoint", "component-0001")},
        )
        with RECOVERY.patched_public_privacy(SOURCE, SOURCE_CLAIM_BOUNDARY):
            for value in variants:
                with self.subTest(value_type=type(value.get("claim_boundary")).__name__):
                    self.assertTrue(SOURCE._public_sensitive(value))

    def test_04_adapter_retains_string_marker_rejections(self) -> None:
        markers = (
            "component-0001",
            "component-abc",
            "sample-0001",
            "/Users/phoenix/private.json",
            "phase-b-representation/private/secret.json",
        )
        with RECOVERY.patched_public_privacy(SOURCE, SOURCE_CLAIM_BOUNDARY):
            for marker in markers:
                with self.subTest(marker=marker):
                    self.assertTrue(
                        SOURCE._public_sensitive(safe_payload(note=marker))
                    )

    def test_05_adapter_retains_forbidden_keys_and_long_list_rejections(self) -> None:
        forbidden = (
            "labels",
            "probabilities",
            "predictions",
            "sample_ids",
            "component_ids",
            "fold_ids",
            "row_identity",
            "permutation_sha256",
        )
        with RECOVERY.patched_public_privacy(SOURCE, SOURCE_CLAIM_BOUNDARY):
            for key in forbidden:
                with self.subTest(key=key, depth="root"):
                    self.assertTrue(SOURCE._public_sensitive(safe_payload(**{key: []})))
                with self.subTest(key=key, depth="nested"):
                    self.assertTrue(
                        SOURCE._public_sensitive(safe_payload(meta={key: []}))
                    )
            self.assertTrue(
                SOURCE._public_sensitive(safe_payload(payload=list(range(672))))
            )
            self.assertFalse(
                SOURCE._public_sensitive(safe_payload(payload=list(range(671))))
            )
            self.assertFalse(SOURCE._public_sensitive(safe_payload(interval=[0.1, 0.2])))

    def test_06_privacy_patch_restores_after_exception(self) -> None:
        original = SOURCE._public_sensitive
        with self.assertRaisesRegex(RuntimeError, "synthetic stop"):
            with RECOVERY.patched_public_privacy(SOURCE, SOURCE_CLAIM_BOUNDARY):
                self.assertIsNot(SOURCE._public_sensitive, original)
                raise RuntimeError("synthetic stop")
        self.assertIs(SOURCE._public_sensitive, original)

    def test_07_config_schema_and_contract_are_fail_closed(self) -> None:
        config = json.loads(RECOVERY_CONFIG_PATH.read_text(encoding="utf-8"))
        RECOVERY.validate_config(config)
        nonself = {key: value for key, value in config.items() if key != "implementation"}
        self.assertEqual(
            RECOVERY.bytes_sha256(RECOVERY.canonical_json_bytes(nonself)),
            RECOVERY.EXPECTED_NONSELF_CONFIG_SHA256,
        )
        bound = deepcopy(config)
        bound["implementation"] = {
            "protocol": dict(RECOVERY.EXPECTED_PROTOCOL_RECORD),
            "verifier": RECOVERY.artifact(RECOVERY_PATH),
            "tests": dict(RECOVERY.EXPECTED_TESTS_RECORD),
        }
        implementation_paths = RECOVERY.require_implementation_records(bound)
        self.assertEqual(
            implementation_paths["implementation_protocol"].resolve(),
            RECOVERY.DEFAULT_PROTOCOL.resolve(),
        )
        self.assertEqual(
            implementation_paths["implementation_tests"].resolve(),
            RECOVERY.DEFAULT_TESTS.resolve(),
        )
        alternate = deepcopy(bound)
        alternate["implementation"]["protocol"] = {
            **RECOVERY.EXPECTED_PROTOCOL_RECORD,
            "path": "experiments/stack-overflow-emotion-gold/protocols/alternate.md",
        }
        with (
            patch.object(
                RECOVERY,
                "require_record",
                return_value=RECOVERY.DEFAULT_PROTOCOL,
            ),
            self.assertRaisesRegex(ValueError, "protocol binding drift"),
        ):
            RECOVERY.require_implementation_records(alternate)
        for mutation in (
            lambda value: value["scope"].__setitem__("probe_refit", True),
            lambda value: value["privacy_contract"].__setitem__(
                "long_list_minimum", 673
            ),
            lambda value: value["authorization"].__setitem__(
                "representation_values", True
            ),
            lambda value: value["outputs"]["static_allowlist"].append("extra.json"),
        ):
            drifted = deepcopy(config)
            mutation(drifted)
            with self.subTest(mutation=mutation.__code__.co_firstlineno):
                with self.assertRaises((ValueError, PermissionError)):
                    RECOVERY.validate_config(drifted)

    def test_08_strict_json_rejects_duplicate_keys_and_nonfinite_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            RECOVERY.strict_json_bytes(b'{"claim_boundary":"a","claim_boundary":"b"}\n')
        with self.assertRaisesRegex(ValueError, "Non-finite JSON constant"):
            RECOVERY.strict_json_bytes(b'{"value":NaN}\n')

    def test_09_static_payloads_preserve_no_value_boundary(self) -> None:
        config = json.loads(RECOVERY_CONFIG_PATH.read_text(encoding="utf-8"))
        source = {"snapshot_sha256": "s" * 64}
        tests = {
            "test_artifact": {
                "path": "tests/test.py",
                "bytes": 1,
                "mode": "0644",
                "sha256": "t" * 64,
            },
            "tests_run": RECOVERY.SYNTHETIC_TEST_COUNT,
            "status": "Passed",
            "command_sha256": "c" * 64,
        }
        paths = {
            "input_manifest": Path("input-manifest.json"),
            "probe_manifest": Path("probe-manifest.json"),
        }

        def fake_artifact(path: Path, *, logical_name=None):
            record = {"bytes": 1, "mode": "0644", "sha256": "a" * 64}
            if logical_name is None:
                record["path"] = path.name
            else:
                record["logical_name"] = logical_name
            return record

        with patch.object(RECOVERY, "artifact", side_effect=fake_artifact):
            verification = RECOVERY.build_static_verification(
                Path("config.json"), config, paths, source, tests
            )
            completion = RECOVERY.build_static_completion(
                Path("config.json"),
                config,
                Path("static-verification.json"),
                source["snapshot_sha256"],
            )
        access = verification["access"]
        self.assertFalse(access["source_run_results_parsed"])
        self.assertFalse(access["label_values_read"])
        self.assertFalse(access["sealed_probability_values_read"])
        self.assertFalse(access["representation_values_read"])
        self.assertFalse(access["thresholds_recomputed"])
        self.assertFalse(access["metrics_recomputed"])
        self.assertFalse(access["bootstrap_recomputed"])
        self.assertFalse(completion["performance_metrics_computed"])
        self.assertFalse(SOURCE._public_sensitive(verification))
        self.assertFalse(SOURCE._public_sensitive(completion))
        static_source = "\n".join(
            (
                inspect.getsource(RECOVERY.validate_source_identity_only),
                inspect.getsource(RECOVERY.no_result_audit),
                inspect.getsource(RECOVERY.verify_static),
            )
        )
        for forbidden_call in (
            "load_labels(",
            "recompute_results(",
            "prevalidate_fold_structures(",
            "load(\"numpy\"",
        ):
            self.assertNotIn(forbidden_call, static_source)

        source_verification = {
            "status": "Passed",
            "failed_count": 0,
            "probe_refit": False,
            "runner_imported": False,
            "model_libraries_imported": False,
            "checks": [],
            "results_sha256": "r" * 64,
            "negative_control_failure": False,
            "representation_state": 2,
            "representation_state_label": "Representation effect replicated",
            "access": {
                "representation_values_read": False,
                "probe_refit": False,
                "validation_accessed": False,
                "test_accessed": False,
                "model_loaded": False,
                "forward_executed": False,
            },
        }
        replay = {
            "source_verification": source_verification,
            "source_report_resources": {"aggregate_elapsed_seconds": 1.0},
            "elapsed_seconds": 10.0,
            "peak_rss_bytes": 100,
        }
        recovery_source = {
            "snapshot_sha256": "s" * 64,
            "source_boundary": SOURCE_CLAIM_BOUNDARY,
        }
        with (
            patch.object(RECOVERY, "artifact", side_effect=fake_artifact),
            patch.object(RECOVERY, "resolve_project", return_value=Path("probe-manifest.json")),
        ):
            first = RECOVERY.build_recovery_verification(
                Path("config.json"), config, recovery_source, Path("claim.json"), replay
            )
            drifted_runtime = dict(replay, elapsed_seconds=20.0, peak_rss_bytes=200)
            second = RECOVERY.build_recovery_verification(
                Path("config.json"),
                config,
                recovery_source,
                Path("claim.json"),
                drifted_runtime,
            )
        self.assertEqual(first, second)

    def test_10_formal_prefix_is_fresh_append_only_and_stage_separated(self) -> None:
        claim = {"schema_version": "claim-v1", "status": "Claimed"}
        verification = {
            "schema_version": "verification-v1",
            "status": "Passed",
            "failed_count": 0,
        }
        completion = {"schema_version": "completion-v1", "status": "Complete"}
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "source"
            source.mkdir()
            source_file = source / "probe.json"
            source_file.write_bytes(b"immutable\n")
            source_before = source_file.read_bytes()
            root = base / "recovery"
            claim_path, verification_path, completion_path = RECOVERY.prepare_formal_prefix(
                root, claim, complete=False
            )
            self.assertEqual(RECOVERY.inventory(root), {"source-snapshot-claim.json"})
            RECOVERY.create_json_once(verification_path, verification)
            with self.assertRaisesRegex(RuntimeError, "existing verification"):
                RECOVERY.prepare_formal_prefix(root, claim, complete=False)
            self.assertFalse(completion_path.exists())
            RECOVERY.prepare_formal_prefix(root, claim, complete=True)
            RECOVERY.create_json_once(completion_path, completion)
            self.assertEqual(
                RECOVERY.inventory(root),
                {"source-snapshot-claim.json", "verification.json", "probe-complete.json"},
            )
            self.assertEqual(RECOVERY.directory_inventory(root), set())
            with self.assertRaisesRegex(RuntimeError, "existing verification"):
                RECOVERY.prepare_formal_prefix(root, claim, complete=False)
            self.assertEqual(source_file.read_bytes(), source_before)
            self.assertTrue(claim_path.exists())

    def test_11_formal_prefix_rejects_clobber_and_complete_without_pass(self) -> None:
        claim = {"schema_version": "claim-v1", "status": "Claimed"}
        inventory_cases = (
            ("source-public", {"run-claim.json", "probe.json"}, set()),
            (
                "source-private",
                {"input-manifest.json", "probe-manifest.json", "folds/f0.json"},
                {"folds"},
            ),
            ("static-prefix", {"static-verification.json"}, set()),
            (
                "static-terminal",
                {"static-verification.json", "no-result-complete.json"},
                set(),
            ),
            ("recovery-prefix", {"source-snapshot-claim.json"}, set()),
            (
                "recovery-verified",
                {"source-snapshot-claim.json", "verification.json"},
                set(),
            ),
            (
                "recovery-terminal",
                {
                    "source-snapshot-claim.json",
                    "verification.json",
                    "probe-complete.json",
                },
                set(),
            ),
        )
        for name, files, directories in inventory_cases:
            with self.subTest(root=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / name
                root.mkdir()
                for relative in directories:
                    (root / relative).mkdir(parents=True, exist_ok=True)
                for relative in files:
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("{}\n", encoding="utf-8")
                RECOVERY.require_exact_inventory(
                    root, files, expected_directories=directories
                )
                (root / "unexpected-empty-directory").mkdir()
                with self.assertRaisesRegex(ValueError, "directory inventory drift"):
                    RECOVERY.require_exact_inventory(
                        root, files, expected_directories=directories
                    )

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            public = base / "source-public"
            private = base / "source-private"
            public.mkdir(mode=0o755)
            private.mkdir(mode=0o700)
            folds = private / "folds"
            folds.mkdir(mode=0o700)
            (public / "run-claim.json").write_text("{}\n", encoding="utf-8")
            (public / "probe.json").write_text(
                '{"status":"CompletedAwaitingVerification"}\n', encoding="utf-8"
            )
            (private / "input-manifest.json").write_text("{}\n", encoding="utf-8")
            (private / "probe-manifest.json").write_text("{}\n", encoding="utf-8")
            for relative in RECOVERY._expected_fold_names():
                path = private / relative
                path.write_text("{}\n", encoding="utf-8")
            for path in private.rglob("*"):
                if path.is_file():
                    os.chmod(path, 0o600)
            formal_config_path = base / "formal-config.json"
            source_config = {
                "implementation": {
                    "protocol": {"path": "source-protocol", "bytes": 1, "mode": "0644", "sha256": "a" * 64},
                    "runner": {"path": "source-runner", "bytes": 1, "mode": "0644", "sha256": "b" * 64},
                    "verifier": {"path": "source-verifier", "bytes": 1, "mode": "0644", "sha256": "c" * 64},
                    "tests": {"path": "source-tests", "bytes": 1, "mode": "0644", "sha256": "d" * 64},
                },
                "claim_boundary": SOURCE_CLAIM_BOUNDARY,
                "outputs": {
                    "formal_public_root": RECOVERY.SOURCE_PUBLIC_ROOT,
                    "formal_private_root": RECOVERY.SOURCE_PRIVATE_ROOT,
                    "formal_public_awaiting_verification_allowlist": [
                        "run-claim.json",
                        "probe.json",
                    ],
                    "formal_private_success_allowlist": [
                        "input-manifest.json",
                        *RECOVERY._expected_fold_names(),
                        "probe-manifest.json",
                    ],
                },
            }
            formal_config_path.write_text(json.dumps(source_config), encoding="utf-8")

            def local_record(path):
                return {
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "mode": RECOVERY.file_mode(path),
                    "sha256": RECOVERY.sha256(path),
                }

            source_config_record = deepcopy(json.loads(RECOVERY_CONFIG_PATH.read_text()))
            source_config_record["source_snapshot"].update(
                {
                    "formal_protocol": source_config["implementation"]["protocol"],
                    "source_runner": source_config["implementation"]["runner"],
                    "source_verifier": source_config["implementation"]["verifier"],
                    "source_tests": source_config["implementation"]["tests"],
                    "run_claim": local_record(public / "run-claim.json"),
                    "probe": local_record(public / "probe.json"),
                    "input_manifest": local_record(private / "input-manifest.json"),
                    "probe_manifest": local_record(private / "probe-manifest.json"),
                    "fold_artifacts": [
                        {
                            "logical_name": relative,
                            **local_record(private / relative),
                        }
                        for relative in RECOVERY._expected_fold_names()
                    ],
                }
            )
            paths = {
                "formal_config": formal_config_path,
                "probe": public / "probe.json",
            }

            def local_artifact(path, *, logical_name=None):
                record = local_record(path)
                if logical_name is None:
                    return record
                record.pop("path")
                record["logical_name"] = logical_name
                return record

            def local_resolve(relative, *, must_exist=True):
                if relative == RECOVERY.SOURCE_PUBLIC_ROOT:
                    return public
                if relative == RECOVERY.SOURCE_PRIVATE_ROOT:
                    return private
                raise AssertionError(relative)

            with (
                patch.object(RECOVERY, "artifact", side_effect=local_artifact),
                patch.object(RECOVERY, "resolve_project", side_effect=local_resolve),
            ):
                RECOVERY.validate_source_identity_only(source_config_record, paths)
                public_extra = public / "unexpected-empty-directory"
                public_extra.mkdir()
                with self.assertRaisesRegex(ValueError, "inventory drift"):
                    RECOVERY.validate_source_identity_only(source_config_record, paths)
                public_extra.rmdir()
                private_extra = private / "unexpected-empty-directory"
                private_extra.mkdir()
                with self.assertRaisesRegex(ValueError, "inventory drift"):
                    RECOVERY.validate_source_identity_only(source_config_record, paths)

        static_config = {"outputs": {"static_public_root": RECOVERY.STATIC_PUBLIC_ROOT}}
        static_verification = {"status": "Passed"}
        static_source = {"snapshot_sha256": "s" * 64}
        static_verifier = types.SimpleNamespace(_public_sensitive=lambda _value: False)
        for name, files, complete, entrypoint in (
            ("static-prefix", {"static-verification.json"}, False, "verify"),
            (
                "static-terminal",
                {"static-verification.json", "no-result-complete.json"},
                True,
                "verify",
            ),
            (
                "static-completion-consumer",
                {"static-verification.json", "no-result-complete.json"},
                True,
                "complete",
            ),
        ):
            with self.subTest(static_entrypoint=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / name
                root.mkdir()
                for filename in files:
                    (root / filename).write_text("{}\n", encoding="utf-8")
                (root / "unexpected-empty-directory").mkdir()
                with (
                    patch.object(RECOVERY, "load_config", return_value=static_config),
                    patch.object(
                        RECOVERY,
                        "no_result_audit",
                        return_value=(
                            static_verification,
                            static_source,
                            static_verifier,
                            {},
                        ),
                    ),
                    patch.object(RECOVERY, "resolve_project", return_value=root),
                ):
                    if entrypoint == "verify":
                        with self.assertRaisesRegex(
                            FileExistsError, "nested directory"
                        ):
                            RECOVERY.verify_static(Path("config.json"), complete=complete)
                    else:
                        with self.assertRaisesRegex(ValueError, "inventory drift"):
                            RECOVERY.require_static_completion(
                                Path("config.json"), static_config
                            )

        recovery_config = {
            "outputs": {"recovery_public_root": RECOVERY.RECOVERY_PUBLIC_ROOT}
        }
        recovery_source = {
            "source_boundary": SOURCE_CLAIM_BOUNDARY,
            "snapshot_sha256": "s" * 64,
        }
        recovery_claim = {
            "status": "Claimed",
            "claim_boundary": SOURCE_CLAIM_BOUNDARY,
        }
        recovery_verifier = types.SimpleNamespace(
            _public_sensitive=lambda _value: False
        )
        for name, files in (
            (
                "recovery-verified-entrypoint",
                {"source-snapshot-claim.json", "verification.json"},
            ),
            (
                "recovery-terminal-entrypoint",
                {
                    "source-snapshot-claim.json",
                    "verification.json",
                    "probe-complete.json",
                },
            ),
        ):
            with self.subTest(recovery_entrypoint=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / name
                root.mkdir()
                for filename in files:
                    value = (
                        recovery_claim
                        if filename == "source-snapshot-claim.json"
                        else {"status": "Passed", "failed_count": 0}
                    )
                    RECOVERY.create_json_once(root / filename, value)
                (root / "unexpected-empty-directory").mkdir()
                with (
                    patch.object(RECOVERY, "load_config", return_value=recovery_config),
                    patch.object(
                        RECOVERY,
                        "require_static_completion",
                        return_value=(
                            {},
                            recovery_source,
                            recovery_verifier,
                            {},
                            Path("static-completion.json"),
                        ),
                    ),
                    patch.object(RECOVERY, "resolve_project", return_value=root),
                    patch.object(
                        RECOVERY, "build_snapshot_claim", return_value=recovery_claim
                    ),
                    patch.object(RECOVERY, "run_source_replay") as replay,
                    self.assertRaisesRegex(FileExistsError, "nested directory"),
                ):
                    RECOVERY.verify_formal(Path("config.json"), complete=True)
                replay.assert_not_called()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "new"
            with self.assertRaisesRegex(RuntimeError, "requires Passed"):
                RECOVERY.prepare_formal_prefix(root, claim, complete=True)
            root.mkdir()
            (root / "alien.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "not an exact prefix"):
                RECOVERY.prepare_formal_prefix(root, claim, complete=False)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "empty-directory-drift"
            root.mkdir()
            (root / "unexpected").mkdir()
            with self.assertRaisesRegex(FileExistsError, "nested directory"):
                RECOVERY.prepare_formal_prefix(root, claim, complete=False)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "failed"
            claim_path, verification_path, _completion_path = RECOVERY.prepare_formal_prefix(
                root, claim, complete=False
            )
            self.assertTrue(claim_path.exists())
            RECOVERY.create_json_once(
                verification_path,
                {"schema_version": "failure-v1", "status": "Failed", "failed_count": 1},
            )
            with self.assertRaisesRegex(RuntimeError, "Passed recovery prefix"):
                RECOVERY.prepare_formal_prefix(root, claim, complete=True)

    def test_12_source_write_guards_imports_and_stage_surface(self) -> None:
        calls = []

        def original_create(path, value):
            calls.append((path, value))

        def original_artifact(path, *, logical_name=None):
            return {"path": str(path), "logical_name": logical_name}

        fake = types.SimpleNamespace(
            create_json_once=original_create,
            artifact=original_artifact,
            canonical_json_bytes=RECOVERY.canonical_json_bytes,
        )
        with self.assertRaisesRegex(PermissionError, "attempted to write"):
            with RECOVERY.blocked_source_writes(fake):
                fake.create_json_once(Path("source/verification.json"), {})
        self.assertIs(fake.create_json_once, original_create)
        self.assertEqual(calls, [])
        virtual_verification = (
            RECOVERY.PROJECT_ROOT / "synthetic-source" / "verification.json"
        )
        with RECOVERY.in_memory_artifact(
            fake, virtual_verification, {"status": "Passed"}
        ):
            record = fake.artifact(virtual_verification)
            self.assertEqual(record["mode"], "0644")
        self.assertIs(fake.artifact, original_artifact)
        replay_source = inspect.getsource(RECOVERY.run_source_replay)
        self.assertNotIn("verify_formal(", replay_source)
        self.assertNotIn("create_json_once(", replay_source)
        self.assertFalse(RECOVERY._has_attribute_call(RECOVERY_PATH, "fit"))
        self.assertFalse(RECOVERY._has_attribute_call(SOURCE_VERIFIER_PATH, "fit"))
        for stage in (
            "static-verify",
            "static-complete",
            "formal-verify",
            "formal-complete",
        ):
            self.assertEqual(RECOVERY.parse_args(["--stage", stage]).stage, stage)
        self.assertFalse(
            {name.split(".")[0] for name in os.sys.modules}
            & RECOVERY.FORBIDDEN_MODEL_MODULES
        )
        thread_environment = {
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
        runtime = {
            "python_executable": os.sys.executable,
            "python_version": RECOVERY.platform.python_version(),
            "architecture": RECOVERY.platform.machine(),
            "thread_environment": thread_environment,
            "packages": {
                "numpy": "1.0",
                "scikit-learn": "2.0",
                "scipy": "3.0",
                "joblib": "4.0",
            },
        }
        observed_packages = dict(runtime["packages"])
        with (
            patch.dict(
                os.environ,
                {"PYTHONNOUSERSITE": "1", **thread_environment},
            ),
            patch.object(
                RECOVERY.importlib.metadata,
                "version",
                side_effect=lambda name: observed_packages[name],
            ),
        ):
            self.assertEqual(
                RECOVERY.require_static_runtime({"environment": runtime}), runtime
            )
            drifted_runtime = dict(runtime, python_version="0.0.0")
            with self.assertRaisesRegex(RuntimeError, "runtime identity drift"):
                RECOVERY.require_static_runtime({"environment": drifted_runtime})
            for field, drift in (
                ("python_executable", "/missing/frozen-python"),
                ("architecture", "wrong-architecture"),
            ):
                drifted_identity = dict(runtime, **{field: drift})
                with self.subTest(runtime_field=field), self.assertRaisesRegex(
                    RuntimeError, "runtime identity drift"
                ):
                    RECOVERY.require_static_runtime(
                        {"environment": drifted_identity}
                    )
            for variable in thread_environment:
                with (
                    self.subTest(thread_variable=variable),
                    patch.dict(os.environ, {variable: "0"}),
                    self.assertRaisesRegex(RuntimeError, "thread environment drift"),
                ):
                    RECOVERY.require_static_runtime({"environment": runtime})
            for package in observed_packages:
                drifted_packages = deepcopy(runtime)
                drifted_packages["packages"][package] = "9.9"
                with self.subTest(package=package), self.assertRaisesRegex(
                    RuntimeError, "package identity drift"
                ):
                    RECOVERY.require_static_runtime(
                        {"environment": drifted_packages}
                    )
            for contract_drift in ("missing", "extra"):
                drifted_contract = deepcopy(runtime)
                if contract_drift == "missing":
                    del drifted_contract["packages"]["joblib"]
                else:
                    drifted_contract["packages"]["extra"] = "1.0"
                with self.subTest(package_contract=contract_drift), self.assertRaisesRegex(
                    RuntimeError, "package contract drift"
                ):
                    RECOVERY.require_static_runtime(
                        {"environment": drifted_contract}
                    )
            with (
                patch.object(
                    RECOVERY.importlib.metadata,
                    "version",
                    side_effect=RECOVERY.importlib.metadata.PackageNotFoundError("numpy"),
                ),
                self.assertRaisesRegex(RuntimeError, "package identity drift"),
            ):
                RECOVERY.require_static_runtime({"environment": runtime})
        with patch.dict(
            os.environ,
            {"PYTHONNOUSERSITE": "0", **thread_environment},
        ):
            with self.assertRaisesRegex(RuntimeError, "runtime identity drift"):
                RECOVERY.require_static_runtime({"environment": runtime})

        config = json.loads(RECOVERY_CONFIG_PATH.read_text(encoding="utf-8"))
        for index, key in enumerate(("protocol", "verifier", "tests"), start=1):
            config["implementation"][key] = {
                "path": f"synthetic/{key}.py",
                "bytes": index,
                "mode": "0644",
                "sha256": str(index) * 64,
            }
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            config_path = base / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            static_root = base / "static"
            formal_root = base / "formal"

            def fake_resolve(relative, *, must_exist=True):
                if relative == RECOVERY.STATIC_PUBLIC_ROOT:
                    return static_root
                if relative == RECOVERY.RECOVERY_PUBLIC_ROOT:
                    return formal_root
                raise AssertionError(relative)

            def fake_require_record(record):
                path = record["path"]
                if path.endswith("verify_exp070_probe.py"):
                    return SOURCE_VERIFIER_PATH
                if path.endswith("exp-070-formal-probe.json"):
                    return SOURCE_CONFIG_PATH
                raise AssertionError(path)

            def safe_artifact(path, *, logical_name=None):
                value = {"bytes": 1, "mode": "0644", "sha256": "a" * 64}
                if logical_name is None:
                    value["path"] = path.name
                else:
                    value["logical_name"] = logical_name
                return value

            with (
                patch.object(RECOVERY, "DEFAULT_CONFIG", config_path),
                patch.object(RECOVERY, "resolve_project", side_effect=fake_resolve),
                patch.object(RECOVERY, "require_record", side_effect=fake_require_record),
                patch.object(RECOVERY, "require_implementation_records", return_value={}),
                patch.object(RECOVERY, "artifact", side_effect=safe_artifact),
            ):
                RECOVERY.ensure_public_root(static_root)
                static_empty = static_root / "unexpected-empty-directory"
                static_empty.mkdir()
                RECOVERY.record_recovery_failure(
                    "static-verify", config_path, RuntimeError("synthetic static failure")
                )
                self.assertFalse((static_root / "static-verification.json").exists())
                static_empty.rmdir()
                RECOVERY.record_recovery_failure(
                    "static-verify", config_path, RuntimeError("synthetic static failure")
                )
                static_failure = RECOVERY.require_canonical_json(
                    static_root / "static-verification.json"
                )
                self.assertEqual(static_failure["status"], "Failed")
                self.assertFalse(static_failure["formal_verification_authorized"])

                RECOVERY.ensure_public_root(formal_root)
                claim = {"status": "Claimed", "config": safe_artifact(config_path)}
                RECOVERY.create_json_once(
                    formal_root / "source-snapshot-claim.json", claim
                )
                formal_empty = formal_root / "unexpected-empty-directory"
                formal_empty.mkdir()
                RECOVERY.record_recovery_failure(
                    "formal-verify", config_path, RuntimeError("synthetic formal failure")
                )
                self.assertFalse((formal_root / "verification.json").exists())
                formal_empty.rmdir()
                RECOVERY.record_recovery_failure(
                    "formal-verify", config_path, RuntimeError("synthetic formal failure")
                )
                formal_failure = RECOVERY.require_canonical_json(
                    formal_root / "verification.json"
                )
                self.assertEqual(formal_failure["status"], "Failed")
                self.assertFalse(formal_failure["formal_probe_complete"])
                self.assertFalse(formal_failure["recovery_wrote_source"])
                self.assertNotIn("source_mutated", formal_failure)
                self.assertFalse((formal_root / "probe-complete.json").exists())


if __name__ == "__main__":
    unittest.main()
