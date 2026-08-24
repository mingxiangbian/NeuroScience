#!/usr/bin/env python3
"""Synthetic and pre-science integration tests for Incident-002 Attempt 3."""

from __future__ import annotations

import ast
import copy
from datetime import timedelta
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock


TEST_PATH = Path(__file__).resolve()
SCRIPT_DIR = TEST_PATH.parents[1]
PROJECT_ROOT = SCRIPT_DIR.parents[2]
RECOVERY_PATH = SCRIPT_DIR / "verify_exp060_router_attempt3.py"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import verify_exp060_router_attempt2 as incident1
import verify_exp060_router_attempt3 as recovery


ATTEMPT2_FROZEN = {
    "protocol": (
        PROJECT_ROOT
        / "experiments/stack-overflow-emotion-gold/protocols/exp-061-exp060-final-verification-attempt-2-amendment.md",
        17147,
        "ea24de2ac3d55528c4b516fc678bd89b3997e77642809c20d102734006e68171",
    ),
    "config": (
        PROJECT_ROOT / incident1.AMENDMENT_CONFIG_REL,
        14452,
        "58c7d3861a32020081220256e6bbe3d54559c67220dbdbc72d77bc3a83164be2",
    ),
    "verifier": (
        PROJECT_ROOT / recovery.INCIDENT1_VERIFIER_REL,
        89797,
        "51bb8c4b1942a626eca826933da597177085abe74c7b68c1aee7bfb3c30cfa5b",
    ),
    "tests": (
        PROJECT_ROOT / recovery.INCIDENT1_TESTS_REL,
        36562,
        "b18b222c8522bea209acfa8aa7d08205adfb32d43dc2734f4aaefcdd1e330084",
    ),
    "finalizer": (
        PROJECT_ROOT / recovery.INCIDENT1_FINALIZER_REL,
        66804,
        "deb2f291fea0901f5e60e5a4863b18491a4888d3bcc3a1463642ae8f85a8fbd9",
    ),
    "finalizer_tests": (
        PROJECT_ROOT / recovery.INCIDENT1_FINALIZER_TESTS_REL,
        41041,
        "ff44dc0c37881a61c7efb1a2f3d82893c49f9030fdfdfa9a19b1520ec73f26cd",
    ),
}


def mirror_metadata(overlay: bool, token: str) -> dict[str, object]:
    manifest = incident1.expected_mirror_copy_manifest()
    return {
        "fresh_project_root": True,
        "project_root_mode": "0o700",
        "canonical_layout": True,
        "copy_only": True,
        "copied_file_count": 30,
        "copy_manifest_sha256": recovery.canonical_digest(manifest),
        "no_symlinks": True,
        "no_hardlinks": True,
        "instance_token_sha256": token,
        "overlay_enabled": overlay,
        "overlay_load_count": 1 if overlay else 0,
        "matching_sha_load_count": 2 if overlay else 0,
        "overlay_input_sha256": (
            incident1.EXPECTED_IMMUTABLE[recovery.FORMAL_CONFIG_REL][1]
            if overlay
            else None
        ),
        "cleaned": True,
    }


def passed_checks() -> list[dict[str, object]]:
    original = incident1.load_json(
        incident1.require_expected(incident1.ORIGINAL_VERIFICATION_REL)
    )
    rows = copy.deepcopy(original["checks"])
    for row in rows:
        row["passed"] = True
    return rows


def mirror_a_checks() -> list[dict[str, object]]:
    rows = passed_checks()
    for row in rows:
        if row["name"] == "config.router":
            row["passed"] = False
    return rows


def valid_attempt3_fixture() -> dict[str, object]:
    config_path, config = recovery.load_incident2_config()
    formal = incident1.load_json(incident1.require_expected(recovery.FORMAL_CONFIG_REL))
    checks = passed_checks()
    attempt2, _records = recovery.require_attempt2_failure()
    verified_at = (
        recovery.canonical_utc_datetime(attempt2["verified_at_utc"])
        + timedelta(seconds=1)
    ).isoformat()
    metadata_a = mirror_metadata(False, "a" * 64)
    metadata_b = mirror_metadata(True, "b" * 64)
    base_independence = {
        "runner_imported": False,
        "raw_exp058_recomputation": True,
        "nested_thresholds_recomputed": True,
        "scalers_and_routers_refit": True,
        "public_and_private_outputs_recomputed": True,
    }
    split = {
        "accessed_splits": ["train-oof"],
        "validation_accessed": False,
        "test_inputs_accessed": False,
        "test_labels_accessed": False,
        "raw_text_accessed": False,
        "model_loaded_or_forward_run": False,
    }
    verified = incident1.expected_verified_artifacts()
    recovery_checks = [
        {"name": name, "passed": True, "detail": None}
        for name in recovery.ATTEMPT3_RECOVERY_CHECK_NAMES
    ]
    return {
        "schema_version": "exp-router-formal-verification-attempt-3-v1",
        "experiment_id": recovery.EXPERIMENT_ID,
        "rq_id": recovery.RQ_ID,
        "stage": recovery.ROUTER_STAGE,
        "run_id": recovery.RUN_ID,
        "attempt_id": recovery.ATTEMPT_ID,
        "model_seed": recovery.MODEL_SEED,
        "seed_contract": formal["seed_contract"],
        "scope": "final",
        "verification_attempt": 3,
        "status": "Passed",
        "runner_imported": False,
        "verified_at_utc": verified_at,
        "passed_count": 4434,
        "failed_count": 0,
        "checks": checks,
        "independence": copy.deepcopy(recovery.ATTEMPT3_INDEPENDENCE),
        "verified_artifacts": verified,
        "split_access": split,
        "recovery": {
            "schema_version": "exp-router-verification-recovery-attempt-3-v1",
            "incident_id": "002",
            "predecessor_incident_id": "001",
            "classification": "fresh_mirror_path_canonicalization",
            "amendment_config": recovery.artifact(config_path),
            "amendment_protocol": config["implementation"]["amendment_protocol"],
            "incident_001": config["lineage"]["incident_001"],
            "attempt_1_failed": config["lineage"]["attempt_1"],
            "attempt_2_failed": config["lineage"]["attempt_2"],
            "base_verifier": config["implementation"]["base_verifier"],
            "recovery_verifier": config["implementation"]["recovery_verifier"],
            "path_canonicalization": {
                "loaded_verifier_project_root_used": True,
                "config_argument": "module.PROJECT_ROOT / FORMAL_CONFIG_REL",
                "semantic_change_count": 1,
            },
            "overlay": {**config["clerical_overlay"], "applied_load_count": 1},
            "public_state": {
                **config["public_state"],
                "observed_content_tree": config["public_state"]["content_tree"],
            },
            "private_state": {
                "before": config["private_invariant"],
                "after": config["private_invariant"],
            },
            "recomputation": {
                "mirror_a": {
                    "role": "unchanged_config_control",
                    "status": "Failed",
                    "passed_count": 4433,
                    "failed_count": 1,
                    "checks": mirror_a_checks(),
                    "independence": base_independence,
                    "verified_artifacts": verified,
                    "split_access": split,
                    "mirror": metadata_a,
                },
                "mirror_b": {
                    "role": "sha_bound_overlay_recovery",
                    "status": "Passed",
                    "passed_count": 4434,
                    "failed_count": 0,
                    "checks_location": "$.checks",
                    "checks_sha256": recovery.canonical_digest(checks),
                    "independence": base_independence,
                    "verified_artifacts": verified,
                    "split_access": split,
                    "mirror": metadata_b,
                },
                "check_name_order_sha256": recovery.canonical_digest(
                    [row["name"] for row in checks]
                ),
            },
            "recovery_checks": recovery_checks,
        },
        "claim_boundary": recovery.ATTEMPT3_CLAIM_BOUNDARY,
    }


class Incident002Attempt3Tests(unittest.TestCase):
    def test_attempt2_six_files_and_failed_sidecars_are_frozen(self) -> None:
        for name, (path, size, digest) in ATTEMPT2_FROZEN.items():
            with self.subTest(name=name):
                self.assertEqual(path.stat().st_size, size)
                self.assertEqual(incident1.sha256(path), digest)
        attempt2, records = recovery.require_attempt2_failure()
        self.assertEqual(attempt2["status"], "Failed")
        self.assertEqual(records["verification"]["sha256"], "b30e48e3dadbd3947fd7101606152084ce4746a711618cdded088518ba2f212b")
        self.assertEqual(records["summary"]["sha256"], "b09d9042529b8a65523bcad52c876dcedf37be66db6a462aed1b9f7b2fdac987")

    def test_attempt3_and_base_verifier_do_not_import_runner(self) -> None:
        incident1.assert_no_runner_import(RECOVERY_PATH)
        incident1.assert_no_runner_import(
            incident1.require_expected(incident1.CANONICAL_VERIFIER_REL)
        )
        tree = ast.parse(RECOVERY_PATH.read_text(encoding="utf-8"))
        imported = [
            ast.unparse(node)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        self.assertFalse(any("run_exp060_router" in value for value in imported))

    def test_live_callsite_has_one_canonical_path_fix_and_exact_two_mirrors(self) -> None:
        source = RECOVERY_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        run_mirror = functions["run_fresh_mirror"]
        verify_calls = [
            node
            for node in ast.walk(run_mirror)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "verify"
        ]
        self.assertEqual(len(verify_calls), 1)
        self.assertEqual(
            ast.unparse(verify_calls[0].args[0]),
            "canonical_mirror_config_path(module)",
        )
        assignments = [
            node
            for node in ast.walk(run_mirror)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "project_root"
                for target in node.targets
            )
        ]
        self.assertEqual(len(assignments), 1)
        self.assertEqual(ast.unparse(assignments[0].value), "Path(temporary)")
        build = functions["build_attempt3_result"]
        calls = [
            ast.unparse(node)
            for node in ast.walk(build)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "run_fresh_mirror"
        ]
        self.assertEqual(
            calls,
            [
                "run_fresh_mirror('mirror_a', overlay=False)",
                "run_fresh_mirror('mirror_b', overlay=True)",
            ],
        )
        _config_path, config = recovery.load_incident2_config()
        self.assertTrue(
            incident1.exact_typed_equal(
                config["resource_contract"],
                {
                    "mirror_execution_count": 2,
                    "sequential_order": ["mirror_a", "mirror_b"],
                    "per_mirror_verification_wall_seconds": 1800,
                    "per_mirror_peak_memory_gb": 4.0,
                    "api_cost_usd": 0,
                    "gpu_cost_usd": 0,
                    "model_forward_runs": 0,
                    "outer_budget_extension": False,
                },
            )
        )
        resource_checks = {
            "resource.formal_wall",
            "resource.formal_memory",
            "resource.api_cost",
            "resource.gpu_cost",
            "resource.model_forward_runs",
            "resource.verification_wall",
            "resource.verification_memory",
        }
        self.assertTrue(resource_checks.issubset(incident1.original_check_names()))

    @unittest.skipUnless(
        sys.platform == "darwin" and Path("/var").resolve() != Path("/var"),
        "macOS /var -> /private/var integration regression",
    )
    def test_real_macos_alias_load_and_canonical_config_guard_before_verify(self) -> None:
        before = {
            "attempt1": recovery.attempt1_lineage_records(),
            "attempt2": recovery.attempt2_lineage_records(),
            "tree": recovery.public_tree_digest(),
            "private": incident1.private_artifact_digest(),
        }
        with tempfile.TemporaryDirectory(prefix="exp061-incident002-alias-") as temporary:
            lexical_root = Path(temporary)
            self.assertNotEqual(lexical_root, lexical_root.resolve())
            incident1.copy_regular_file(
                incident1.require_expected(incident1.CANONICAL_VERIFIER_REL),
                lexical_root / incident1.CANONICAL_VERIFIER_REL,
            )
            incident1.copy_regular_file(
                incident1.require_expected(incident1.FORMAL_CONFIG_REL),
                lexical_root / incident1.FORMAL_CONFIG_REL,
            )
            module = incident1.load_mirror_verifier(lexical_root, "incident002_alias")
            lexical_config = lexical_root / incident1.FORMAL_CONFIG_REL
            with self.assertRaisesRegex(ValueError, "direct child"):
                module.require_canonical_config_path(lexical_config)
            canonical_config = recovery.canonical_mirror_config_path(module)
            self.assertEqual(
                module.require_canonical_config_path(canonical_config), canonical_config
            )
            with mock.patch.object(
                module, "verify", side_effect=AssertionError("verify must remain unreachable")
            ) as verify_call, mock.patch.object(
                module.np, "load", side_effect=AssertionError("np.load must remain unreachable")
            ) as np_load:
                self.assertTrue(canonical_config.is_file())
            verify_call.assert_not_called()
            np_load.assert_not_called()
        after = {
            "attempt1": recovery.attempt1_lineage_records(),
            "attempt2": recovery.attempt2_lineage_records(),
            "tree": recovery.public_tree_digest(),
            "private": incident1.private_artifact_digest(),
        }
        self.assertEqual(before, after)
        for relative in (
            recovery.ATTEMPT3_VERIFICATION_REL,
            recovery.ATTEMPT3_SUMMARY_REL,
            recovery.COMPLETION_REL,
            recovery.SELECTION_REL,
        ):
            self.assertFalse(os.path.lexists(recovery.resolve_relative(relative)))

    def test_mirror_inventory_is_exact_and_excludes_all_governance_paths(self) -> None:
        relatives = incident1.mirror_source_relatives()
        forbidden = {
            recovery.ORIGINAL_VERIFICATION_REL,
            recovery.ORIGINAL_SUMMARY_REL,
            recovery.ATTEMPT2_VERIFICATION_REL,
            recovery.ATTEMPT2_SUMMARY_REL,
            recovery.ATTEMPT3_VERIFICATION_REL,
            recovery.ATTEMPT3_SUMMARY_REL,
            recovery.COMPLETION_REL,
            recovery.SELECTION_REL,
        }
        self.assertEqual(len(relatives), 30)
        self.assertFalse(set(relatives) & forbidden)
        self.assertEqual(
            recovery.canonical_digest(incident1.expected_mirror_copy_manifest()),
            "6ee47d1974a88d9b94091423d9c57deeb239065894a6083ebbdf3e283cacfa67",
        )

    def test_strict_passed_attempt3_fixture_and_tampers(self) -> None:
        value = valid_attempt3_fixture()
        recovery.validate_attempt3_result(value)
        mutations = (
            lambda item: item.__setitem__("model_seed", 43.0),
            lambda item: item.__setitem__("verification_attempt", 3.0),
            lambda item: item["seed_contract"].__setitem__("model_seed", 43.0),
            lambda item: item.__setitem__("passed_count", True),
            lambda item: item.__setitem__("failed_count", False),
            lambda item: item["independence"].pop("fresh_mirror_a"),
            lambda item: item["independence"].__setitem__("extra", True),
            lambda item: item["recovery"]["path_canonicalization"].__setitem__(
                "semantic_change_count", 2
            ),
            lambda item: item["recovery"]["recomputation"]["mirror_a"]["mirror"].__setitem__(
                "copied_file_count", 29
            ),
            lambda item: item["recovery"].__setitem__(
                "attempt_2_failed", item["recovery"]["attempt_1_failed"]
            ),
            lambda item: item["checks"][0].__setitem__("name", "renamed"),
        )
        for mutate in mutations:
            with self.subTest(line=mutate.__code__.co_firstlineno):
                tampered = copy.deepcopy(value)
                mutate(tampered)
                with self.assertRaises(ValueError):
                    recovery.validate_attempt3_result(tampered)

    def test_all_sensitive_keys_are_rejected_inside_check_detail(self) -> None:
        value = valid_attempt3_fixture()
        for key in sorted(recovery.PUBLIC_SENSITIVE_KEYS):
            with self.subTest(key=key):
                tampered = copy.deepcopy(value)
                tampered["checks"][0]["detail"] = {"nested": {key: "redacted"}}
                with self.assertRaises(ValueError):
                    recovery.validate_attempt3_result(tampered)

    def test_failure_schema_is_typed_chronological_and_private_safe(self) -> None:
        value = recovery.build_failed_attempt3_result()
        recovery.validate_failed_attempt3_result(value)
        for key, replacement in (("passed_count", False), ("failed_count", True)):
            tampered = copy.deepcopy(value)
            tampered[key] = replacement
            with self.assertRaises(ValueError):
                recovery.validate_failed_attempt3_result(tampered)
        for key, replacement in (("model_seed", 43.0), ("verification_attempt", 3.0)):
            tampered = copy.deepcopy(value)
            tampered[key] = replacement
            with self.assertRaises(ValueError):
                recovery.validate_failed_attempt3_result(tampered)
        tampered = copy.deepcopy(value)
        tampered["checks"][0]["detail"]["sample_ids"] = ["private"]
        with self.assertRaises(ValueError):
            recovery.validate_failed_attempt3_result(tampered)

    def test_json_payload_has_exactly_one_terminal_newline(self) -> None:
        payload = recovery.canonical_json_payload({"status": "synthetic"})
        self.assertTrue(payload.endswith(b"\n"))
        self.assertFalse(payload.endswith(b"\n\n"))
        self.assertEqual(json.loads(payload), {"status": "synthetic"})

    def test_completion_is_strictly_validated_before_immutable_write(self) -> None:
        source = RECOVERY_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        complete = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "complete"
        )
        calls = [
            (node.lineno, ast.unparse(node.func))
            for node in ast.walk(complete)
            if isinstance(node, ast.Call)
        ]
        validation_line = min(
            line for line, name in calls if name == "validate_completion_record"
        )
        write_line = min(
            line for line, name in calls if name == "incident1.create_once"
        )
        self.assertLess(validation_line, write_line)

        verification_time = recovery.utc_now()
        with mock.patch.object(
            recovery,
            "require_passed_attempt3",
            return_value=(
                RECOVERY_PATH,
                {"verified_at_utc": verification_time},
                recovery.artifact(RECOVERY_PATH),
            ),
        ), mock.patch.object(
            recovery,
            "validate_completion_record",
            side_effect=ValueError("synthetic constructor rejection"),
        ) as validate, mock.patch.object(
            recovery.incident1, "create_once"
        ) as writer:
            with self.assertRaisesRegex(ValueError, "synthetic constructor rejection"):
                recovery.complete()
        validate.assert_called_once()
        writer.assert_not_called()
        self.assertFalse(
            os.path.lexists(recovery.resolve_relative(recovery.COMPLETION_REL))
        )

    def test_deterministic_build_failure_seals_and_refuses_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            router = root / "router"
            router.mkdir()
            outputs = {
                recovery.ATTEMPT3_VERIFICATION_REL: router / "verification-attempt-3.json",
                recovery.ATTEMPT3_SUMMARY_REL: router / "VERIFICATION-SUMMARY-ATTEMPT-3.md",
            }
            real_resolve = recovery.resolve_relative

            def resolve_for_test(value: Path | str) -> Path:
                relative = Path(value)
                return outputs.get(relative, real_resolve(relative))

            with (
                mock.patch.object(recovery, "attempt3_preflight", return_value={}),
                mock.patch.object(
                    recovery,
                    "build_attempt3_result",
                    side_effect=ValueError("private diagnostic must not be recorded"),
                ),
                mock.patch.object(recovery, "resolve_relative", side_effect=resolve_for_test),
            ):
                previous = os.umask(0o077)
                try:
                    result = recovery.run_final()
                finally:
                    os.umask(previous)
                self.assertEqual(result["status"], "Failed")
                for path in outputs.values():
                    observed = os.lstat(path)
                    self.assertTrue(stat.S_ISREG(observed.st_mode))
                    self.assertEqual(stat.S_IMODE(observed.st_mode), 0o644)
                    self.assertEqual(observed.st_nlink, 1)
                    self.assertNotIn(
                        "private diagnostic", path.read_text(encoding="utf-8")
                    )
                with self.assertRaises(FileExistsError):
                    recovery.run_final()

    def test_summary_write_failure_leaves_terminal_json_and_no_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            router = root / "router"
            router.mkdir()
            verification = router / "verification-attempt-3.json"
            summary = router / "VERIFICATION-SUMMARY-ATTEMPT-3.md"
            outputs = {
                recovery.ATTEMPT3_VERIFICATION_REL: verification,
                recovery.ATTEMPT3_SUMMARY_REL: summary,
            }
            real_resolve = recovery.resolve_relative
            real_create_once = incident1.create_once

            def resolve_for_test(value: Path | str) -> Path:
                relative = Path(value)
                return outputs.get(relative, real_resolve(relative))

            def fail_summary(path: Path, payload: bytes, mode: int = 0o644) -> None:
                if path == summary:
                    raise OSError("synthetic summary write failure")
                real_create_once(path, payload, mode)

            with (
                mock.patch.object(recovery, "attempt3_preflight", return_value={}),
                mock.patch.object(
                    recovery,
                    "build_attempt3_result",
                    side_effect=ValueError("synthetic deterministic failure"),
                ),
                mock.patch.object(recovery, "resolve_relative", side_effect=resolve_for_test),
                mock.patch.object(incident1, "create_once", side_effect=fail_summary),
            ):
                with self.assertRaises(OSError):
                    recovery.run_final()
                self.assertTrue(verification.is_file())
                self.assertFalse(summary.exists())
                observed = os.lstat(verification)
                self.assertTrue(stat.S_ISREG(observed.st_mode))
                self.assertEqual(stat.S_IMODE(observed.st_mode), 0o644)
                self.assertEqual(observed.st_nlink, 1)
                sealed = json.loads(verification.read_text(encoding="utf-8"))
                recovery.validate_failed_attempt3_result(sealed)
                self.assertFalse(os.path.lexists(real_resolve(recovery.COMPLETION_REL)))
                self.assertFalse(os.path.lexists(real_resolve(recovery.SELECTION_REL)))
                with self.assertRaises(FileExistsError):
                    recovery.run_final()

    def test_process_control_exceptions_are_not_sealed(self) -> None:
        for raised in (KeyboardInterrupt(), SystemExit(19)):
            with self.subTest(kind=type(raised).__name__):
                with mock.patch.object(recovery, "attempt3_preflight", return_value={}), mock.patch.object(
                    recovery, "build_attempt3_result", side_effect=raised
                ):
                    with self.assertRaises(type(raised)):
                        recovery.run_final()


if __name__ == "__main__":
    unittest.main()
