#!/usr/bin/env python3
"""Pre-formal tests for the standalone Incident-002 Attempt-3 finalizer."""

from __future__ import annotations

import ast
import copy
from datetime import timedelta
import hashlib
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
FINALIZER_PATH = SCRIPT_DIR / "finalize_router_replication_attempt3.py"
GENERIC_FINALIZER_PATH = SCRIPT_DIR / "finalize_router_replication_attempt.py"

spec = importlib.util.spec_from_file_location("incident002_finalizer_tests", FINALIZER_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("Unable to load dedicated Attempt-3 finalizer")
finalizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finalizer)


def dummy_record(name: str) -> dict[str, object]:
    return {
        "path": f"experiments/synthetic/{name}.json",
        "bytes": 1,
        "sha256": "a" * 64,
    }


def synthetic_selection_fixture() -> tuple[
    dict[str, object],
    list[dict[str, object]],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    config = json.loads(
        finalizer.resolve_relative(finalizer.FORMAL_CONFIG_REL).read_text(encoding="utf-8")
    )
    incident2 = json.loads(
        finalizer.resolve_relative(finalizer.INCIDENT2_CONFIG_REL).read_text(encoding="utf-8")
    )
    attempt1 = json.loads(
        finalizer.resolve_relative(finalizer.ATTEMPT1_VERIFICATION_REL).read_text(
            encoding="utf-8"
        )
    )
    attempt2 = json.loads(
        finalizer.resolve_relative(finalizer.ATTEMPT2_VERIFICATION_REL).read_text(
            encoding="utf-8"
        )
    )
    t1 = attempt1["verified_at_utc"]
    t2 = attempt2["verified_at_utc"]
    t3 = (finalizer.timestamp(t2) + timedelta(seconds=1)).isoformat()
    selected_at = (finalizer.timestamp(t3) + timedelta(seconds=1)).isoformat()
    chain = [
        {
            "verification_attempt": 1,
            "status": "Failed",
            "passed_count": 4417,
            "failed_count": 17,
            "verified_at_utc": t1,
            "verification": incident2["lineage"]["attempt_1"]["verification"],
            "summary": incident2["lineage"]["attempt_1"]["summary"],
            "failure_code": None,
            "failure_stage": None,
        },
        {
            "verification_attempt": 2,
            "status": "Failed",
            "passed_count": 0,
            "failed_count": 1,
            "verified_at_utc": t2,
            "verification": incident2["lineage"]["attempt_2"]["verification"],
            "summary": incident2["lineage"]["attempt_2"]["summary"],
            "failure_code": "deterministic_contract_failure",
            "failure_stage": "verification_build",
        },
        {
            "verification_attempt": 3,
            "status": "Passed",
            "passed_count": 4434,
            "failed_count": 0,
            "verified_at_utc": t3,
            "verification": dummy_record("attempt3"),
            "summary": dummy_record("attempt3-summary"),
            "failure_code": None,
            "failure_stage": None,
        },
    ]
    completions = {
        "oof": dummy_record("oof-complete"),
        "calibration": dummy_record("calibration-complete"),
        "router": dummy_record("router-complete"),
    }
    stage_artifacts = {
        "oof": {"run": dummy_record("oof-run")},
        "calibration": {"run": dummy_record("calibration-run")},
        "router": {"run": dummy_record("router-run")},
    }
    lineage = {
        "incident_id": "002",
        "attempt_1_failed": incident2["lineage"]["attempt_1"],
        "incident_001": incident2["lineage"]["incident_001"],
        "attempt_2_failed": incident2["lineage"]["attempt_2"],
        "incident_002_config": finalizer.artifact(
            finalizer.resolve_relative(finalizer.INCIDENT2_CONFIG_REL)
        ),
        "incident_002_protocol": incident2["implementation"]["amendment_protocol"],
        "incident_002_verifier": incident2["implementation"]["recovery_verifier"],
        "incident_002_tests": incident2["implementation"]["recovery_tests"],
        "incident_002_finalizer": incident2["implementation"]["finalizer"],
        "incident_002_finalizer_tests": incident2["implementation"]["finalizer_tests"],
        "attempt_3_passed": chain[2]["verification"],
        "attempt_3_summary": chain[2]["summary"],
    }
    selection = {
        "schema_version": "exp-router-replication-selection-attempt-3-v1",
        "experiment_id": finalizer.EXPERIMENT_ID,
        "run_id": finalizer.RUN_ID,
        "attempt_id": finalizer.ATTEMPT_ID,
        "model_seed": finalizer.MODEL_SEED,
        "seed_contract": config["seed_contract"],
        "status": "Selected",
        "selected_at_utc": selected_at,
        "primary_policy": "logistic_router",
        "primary_nominal_call_rate": 0.15,
        "primary_gate_passed": True,
        "decision": "Pass",
        "verification_attempt": 3,
        "finalizer": finalizer.artifact(FINALIZER_PATH),
        "completions": completions,
        "stage_artifacts": stage_artifacts,
        "attempt_chain": chain,
        "recovery_lineage": lineage,
        "claim_boundary": finalizer.SELECTION_CLAIM_BOUNDARY,
    }
    return selection, chain, completions, stage_artifacts, lineage


class DedicatedAttempt3FinalizerTests(unittest.TestCase):
    def test_finalizer_is_standalone_and_cli_is_exact(self) -> None:
        source = FINALIZER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = [
            ast.unparse(node)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        forbidden = (
            "finalize_router_replication_attempt",
            "verify_exp060_router",
            "run_exp060_router",
        )
        self.assertFalse(any(any(name in item for name in forbidden) for item in imported))
        self.assertIn('choices=(EXPERIMENT_ID,)', source)
        self.assertIn('choices=(ATTEMPT_ID,)', source)

    def test_incident2_config_and_prior_failed_lineage_validate_live(self) -> None:
        _path, config = finalizer.load_config()
        attempt1, records1 = finalizer.validate_attempt1(config)
        attempt2, records2 = finalizer.validate_attempt2(config)
        self.assertEqual(attempt1["status"], "Failed")
        self.assertEqual(attempt1["failed_count"], 17)
        self.assertEqual(attempt2["status"], "Failed")
        self.assertEqual(attempt2["failed_count"], 1)
        self.assertEqual(records1, config["lineage"]["attempt_1"])
        self.assertEqual(records2, config["lineage"]["attempt_2"])
        self.assertEqual(
            finalizer.read_bound(
                finalizer.resolve_relative(finalizer.ATTEMPT1_SUMMARY_REL), 0o600
            ),
            finalizer.expected_attempt1_summary(attempt1),
        )

    def test_oof_and_calibration_completions_are_deeply_bound(self) -> None:
        oof, _oof_record = finalizer.validate_stage_completion(
            "oof", finalizer.OOF_COMPLETION_REL, "exp-oof-completion-v2"
        )
        calibration, _calibration_record = finalizer.validate_stage_completion(
            "calibration",
            finalizer.CALIBRATION_COMPLETION_REL,
            "exp-059-calibration-completion-v2",
        )
        self.assertEqual(oof["status"], "Complete")
        self.assertEqual(calibration["status"], "Complete")
        for relative in (
            finalizer.OOF_COMPLETION_REL,
            finalizer.CALIBRATION_COMPLETION_REL,
        ):
            observed = os.lstat(finalizer.resolve_relative(relative))
            self.assertTrue(stat.S_ISREG(observed.st_mode))
            self.assertEqual(stat.S_IMODE(observed.st_mode), 0o600)
            self.assertEqual(observed.st_nlink, 1)

    def test_stage_completion_identity_and_seed_tampers_are_rejected(self) -> None:
        oof_path = finalizer.resolve_relative(finalizer.OOF_COMPLETION_REL)
        calibration_path = finalizer.resolve_relative(
            finalizer.CALIBRATION_COMPLETION_REL
        )
        oof = json.loads(finalizer.read_bound(oof_path, 0o600))
        calibration = json.loads(finalizer.read_bound(calibration_path, 0o600))
        tampers = (
            (
                "oof_experiment",
                "oof",
                finalizer.OOF_COMPLETION_REL,
                "exp-oof-completion-v2",
                lambda value: value.__setitem__("experiment_id", "WRONG"),
                oof,
            ),
            (
                "calibration_parent",
                "calibration",
                finalizer.CALIBRATION_COMPLETION_REL,
                "exp-059-calibration-completion-v2",
                lambda value: value.__setitem__(
                    "replication_parent_experiment_id", "WRONG"
                ),
                calibration,
            ),
            (
                "oof_seed",
                "oof",
                finalizer.OOF_COMPLETION_REL,
                "exp-oof-completion-v2",
                lambda value: value.__setitem__("seed_contract", {"model_seed": 43}),
                oof,
            ),
        )
        for label, name, relative, schema, mutate, source in tampers:
            with self.subTest(label=label):
                tampered = copy.deepcopy(source)
                mutate(tampered)
                with mock.patch.object(
                    finalizer, "load_bound_json", return_value=tampered
                ):
                    with self.assertRaises(ValueError):
                        finalizer.validate_stage_completion(name, relative, schema)

    def test_stage_passed_verification_and_artifact_binding_tampers_are_rejected(self) -> None:
        cases = []
        for name, relative, schema, verification_key in (
            (
                "oof",
                finalizer.OOF_COMPLETION_REL,
                "exp-oof-completion-v2",
                "final_verification",
            ),
            (
                "calibration",
                finalizer.CALIBRATION_COMPLETION_REL,
                "exp-059-calibration-completion-v2",
                "exp059_verification",
            ),
        ):
            completion = json.loads(
                finalizer.read_bound(finalizer.resolve_relative(relative), 0o600)
            )
            verification_path = finalizer.resolve_relative(
                completion["artifacts"][verification_key]["path"]
            )
            verification = finalizer.load_bound_json(verification_path, 0o600)
            cases.append((name, relative, schema, verification_path, verification))

        original_load_bound_json = finalizer.load_bound_json
        for name, relative, schema, verification_path, source in cases:
            mutations = (
                lambda value: value.__setitem__("status", "Failed"),
                lambda value: value.__setitem__("failed_count", 1),
                lambda value: value.__setitem__("verified_artifacts", {}),
            )
            for mutate in mutations:
                with self.subTest(name=name, line=mutate.__code__.co_firstlineno):
                    tampered = copy.deepcopy(source)
                    mutate(tampered)

                    def selective_load_bound_json(path: Path, mode: int) -> dict:
                        if path.resolve() == verification_path.resolve():
                            return copy.deepcopy(tampered)
                        return original_load_bound_json(path, mode)

                    with mock.patch.object(
                        finalizer, "load_bound_json", selective_load_bound_json
                    ):
                        with self.assertRaises(ValueError):
                            finalizer.validate_stage_completion(name, relative, schema)

    def test_build_selection_stops_before_attempt3_and_writes_nothing(self) -> None:
        self.assertFalse(os.path.lexists(finalizer.resolve_relative(finalizer.ATTEMPT3_VERIFICATION_REL)))
        self.assertFalse(os.path.lexists(finalizer.resolve_relative(finalizer.SELECTION_REL)))
        with self.assertRaises(FileNotFoundError):
            finalizer.build_selection()
        self.assertFalse(os.path.lexists(finalizer.resolve_relative(finalizer.SELECTION_REL)))

    def test_live_exact16_and_private_modes_validate(self) -> None:
        finalizer.validate_modes()

    def test_selection_exact_chain_and_tampers(self) -> None:
        selection, chain, completions, stages, lineage = synthetic_selection_fixture()
        finalizer.validate_selection_payload(
            selection,
            expected_chain=chain,
            expected_completions=completions,
            expected_stage_artifacts=stages,
            expected_lineage=lineage,
        )
        mutations = (
            lambda value: value["attempt_chain"].reverse(),
            lambda value: value["attempt_chain"][1].__setitem__("failed_count", True),
            lambda value: value["attempt_chain"][2].__setitem__("status", "Failed"),
            lambda value: value.__setitem__("model_seed", 43.0),
            lambda value: value["seed_contract"].__setitem__("model_seed", 43.0),
            lambda value: value.__setitem__("verification_attempt", 3.0),
            lambda value: value.__setitem__("verification_attempt", 2),
            lambda value: value["recovery_lineage"].__setitem__("incident_id", "001"),
            lambda value: value.__setitem__("decision", "Fail"),
        )
        for mutate in mutations:
            with self.subTest(line=mutate.__code__.co_firstlineno):
                tampered = copy.deepcopy(selection)
                mutate(tampered)
                with self.assertRaises(ValueError):
                    finalizer.validate_selection_payload(
                        tampered,
                        expected_chain=chain,
                        expected_completions=completions,
                        expected_stage_artifacts=stages,
                        expected_lineage=lineage,
                    )

    def test_selection_privacy_rejects_all_sensitive_keys(self) -> None:
        selection, chain, completions, stages, lineage = synthetic_selection_fixture()
        for key in sorted(finalizer.PUBLIC_SENSITIVE_KEYS):
            with self.subTest(key=key):
                tampered = copy.deepcopy(selection)
                tampered["stage_artifacts"]["router"][key] = "private"
                with self.assertRaises(ValueError):
                    finalizer.validate_selection_payload(
                        tampered,
                        expected_chain=chain,
                        expected_completions=completions,
                        expected_stage_artifacts=stages,
                        expected_lineage=lineage,
                    )

    def test_writer_is_append_only_0644_under_umask077(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "selected-attempt.json"
            previous = os.umask(0o077)
            try:
                finalizer.create_json_once(path, {"status": "Selected"})
            finally:
                os.umask(previous)
            observed = os.lstat(path)
            self.assertTrue(stat.S_ISREG(observed.st_mode))
            self.assertEqual(stat.S_IMODE(observed.st_mode), 0o644)
            self.assertEqual(observed.st_nlink, 1)
            self.assertTrue(path.read_bytes().endswith(b"\n"))
            self.assertFalse(path.read_bytes().endswith(b"\n\n"))
            with self.assertRaises(FileExistsError):
                finalizer.create_json_once(path, {"status": "overwrite"})

    def test_artifact_records_reject_hardlinks_and_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.bin"
            source.write_bytes(b"incident-002")
            with mock.patch.object(finalizer, "PROJECT_ROOT", root):
                record = finalizer.artifact(source)
                os.link(source, root / "hardlink.bin")
                with self.assertRaises(ValueError):
                    finalizer.require_record(record, expected_relative=Path("source.bin"))

                target = root / "target.bin"
                target.write_bytes(b"target")
                symlink = root / "symlink.bin"
                symlink.symlink_to(target)
                symlink_record = {
                    "path": "symlink.bin",
                    "bytes": len(b"target"),
                    "sha256": hashlib.sha256(b"target").hexdigest(),
                }
                with self.assertRaises(ValueError):
                    finalizer.require_record(
                        symlink_record, expected_relative=Path("symlink.bin")
                    )

    def test_old_generic_finalizer_does_not_accept_v3_router_schema(self) -> None:
        source = GENERIC_FINALIZER_PATH.read_text(encoding="utf-8")
        self.assertIn('"schema": "exp-router-completion-v2"', source)
        self.assertNotIn('"schema": "exp-router-completion-v3"', source)
        spec = importlib.util.spec_from_file_location(
            "generic_finalizer_reject_v3", GENERIC_FINALIZER_PATH
        )
        if spec is None or spec.loader is None:
            self.fail("Unable to load old generic finalizer")
        generic = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generic)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public_attempt = root / "public" / "attempt-1"
            private_attempt = root / "private" / "attempt-1"
            router = public_attempt / "router"
            router.mkdir(parents=True)
            private_attempt.mkdir(parents=True)
            completion = router / "router-complete.json"
            completion.write_text(
                json.dumps(
                    {
                        "schema_version": "exp-router-completion-v3",
                        "status": "Complete",
                    }
                ),
                encoding="utf-8",
            )
            expected = {
                "experiment_id": finalizer.EXPERIMENT_ID,
                "run_id": finalizer.RUN_ID,
                "attempt_id": finalizer.ATTEMPT_ID,
                "model_seed": finalizer.MODEL_SEED,
                "seed_contract": {},
            }
            with self.assertRaisesRegex(ValueError, "schema/status drift"):
                generic.validate_completion(
                    "router",
                    completion,
                    expected,
                    project_root=root,
                    public_attempt=public_attempt,
                    private_attempt=private_attempt,
                )


if __name__ == "__main__":
    unittest.main()
