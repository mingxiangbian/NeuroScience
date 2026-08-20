from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1]
FINALIZER_PATH = MODULE_DIR / "finalize_router_replication_attempt.py"


def load_module():
    spec = importlib.util.spec_from_file_location("router_replication_finalizer_under_test", FINALIZER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(FINALIZER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


finalizer = load_module()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def write_payload(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def synthetic_attempt(root: Path, *, experiment_id: str = "EXP-061", passed: bool = True):
    seed, run_id = finalizer.REGISTERED[experiment_id]
    attempt_id = "attempt-1"
    script_dir = root / "experiments" / "stack-overflow-emotion-gold" / "oof-router"
    public_attempt = script_dir / "runs" / run_id / attempt_id
    private_attempt = script_dir / "private" / run_id / attempt_id
    config_dir = script_dir / "configs"
    public_attempt.mkdir(parents=True)
    private_attempt.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    write_payload(script_dir / "finalize_router_replication_attempt.py", "# frozen finalizer\n")
    identity = {
        "experiment_id": experiment_id,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "model_seed": seed,
        "seed_contract": finalizer.expected_seed_contract(seed),
    }

    oof_config = config_dir / f"{experiment_id.lower()}-oof.json"
    cal_config = config_dir / f"{experiment_id.lower()}-calibration.json"
    router_config = config_dir / f"{experiment_id.lower()}-router.json"
    for path in (oof_config, cal_config, router_config):
        write_payload(path, "{}\n")

    oof_run = public_attempt / "run.json"
    oof_summary = public_attempt / "paired-oof-summary.json"
    oof_verification = public_attempt / "verification.json"
    paired = private_attempt / "paired-oof.npz"
    write_json(oof_run, {**identity, "status": "CompletedAwaitingVerification"})
    write_json(oof_summary, {"schema_version": "synthetic-summary"})
    write_payload(paired, "synthetic paired bytes\n")
    write_json(
        oof_verification,
        {
            **identity,
            "status": "Passed",
            "failed_count": 0,
            "verified_artifacts": {
                "config": finalizer.artifact(oof_config, root),
                "run": finalizer.artifact(oof_run, root),
                "summary": finalizer.artifact(oof_summary, root),
                "paired_oof_private": finalizer.artifact(paired, root),
            },
        },
    )
    oof_completion = {
        "schema_version": "exp-oof-completion-v2",
        **identity,
        "config": finalizer.artifact(oof_config, root),
        "status": "Complete",
        "artifacts": {
            "run": finalizer.artifact(oof_run, root),
            "summary": finalizer.artifact(oof_summary, root),
            "final_verification": finalizer.artifact(oof_verification, root),
            "paired_oof_private": finalizer.artifact(paired, root),
        },
    }
    write_json(public_attempt / "oof-complete.json", oof_completion)

    calibration_dir = public_attempt / "calibration"
    cal_run = calibration_dir / "run.json"
    cal_verification = calibration_dir / "verification.json"
    cal_parameters = calibration_dir / "calibration-parameters.json"
    calibration_identity = {
        "experiment_id": "EXP-059",
        "replication_parent_experiment_id": experiment_id,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "model_seed": seed,
        "seed_contract": finalizer.expected_seed_contract(seed),
    }
    write_json(
        cal_run, {**calibration_identity, "status": "CompletedAwaitingVerification"}
    )
    write_json(cal_parameters, {**calibration_identity, "families": {}})
    write_json(
        cal_verification,
        {
            **calibration_identity,
            "status": "Passed",
            "failed_count": 0,
            "verified_artifacts": {
                "config": finalizer.artifact(cal_config, root),
                "run": finalizer.artifact(cal_run, root),
                "calibration_parameters": finalizer.artifact(cal_parameters, root),
            },
        },
    )
    calibration_completion = {
        "schema_version": "exp-059-calibration-completion-v2",
        **calibration_identity,
        "status": "Complete",
        "artifacts": {
            "config": finalizer.artifact(cal_config, root),
            "exp059_run": finalizer.artifact(cal_run, root),
            "exp059_verification": finalizer.artifact(cal_verification, root),
            "exp059_calibration_parameters": finalizer.artifact(cal_parameters, root),
        },
    }
    write_json(public_attempt / "calibration-complete.json", calibration_completion)

    router_dir = public_attempt / "router"
    private_router_dir = private_attempt / "router"
    router_run = router_dir / "run.json"
    router_verification = router_dir / "verification.json"
    selected_operating_point = router_dir / "selected-operating-point.json"
    private_router = private_router_dir / "router-oof.npz"
    write_payload(private_router, "synthetic router bytes\n")
    candidate = {"target_call_rate": 0.15, "actual_call_rate": 0.149}
    selected_value = {
        "schema_version": "exp-router-selected-operating-point-v2",
        **identity,
        "primary_policy": "logistic_router",
        "primary_nominal_call_rate": 0.15,
        "policies": {
            "logistic_router": {
                "candidate": candidate,
                "passed": passed,
                "evidence_role": "primary",
            },
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
        },
        "overall": {
            "decision": "Pass" if passed else "Fail",
            "selected_policy": "logistic_router",
            "selected_candidate": candidate,
        },
    }
    write_json(selected_operating_point, selected_value)
    write_json(
        router_run,
        {
            **identity,
            "status": "CompletedAwaitingVerification",
            "decision": "Pass" if passed else "Fail",
            "public_outputs": {
                "selected_operating_point_json": finalizer.artifact(
                    selected_operating_point, root
                )
            },
        },
    )
    write_json(
        router_verification,
        {
            **identity,
            "status": "Passed",
            "failed_count": 0,
            "verified_artifacts": {
                "config": finalizer.artifact(router_config, root),
                "run": finalizer.artifact(router_run, root),
                "private_router_oof": finalizer.artifact(private_router, root),
            },
        },
    )
    router_completion = {
        "schema_version": "exp-router-completion-v2",
        **identity,
        "status": "Complete",
        "primary_gate_passed": passed,
        "decision": "Pass" if passed else "Fail",
        "artifacts": {
            "config": finalizer.artifact(router_config, root),
            "run": finalizer.artifact(router_run, root),
            "final_verification": finalizer.artifact(router_verification, root),
            "selected_operating_point": finalizer.artifact(selected_operating_point, root),
            "private_router_oof": finalizer.artifact(private_router, root),
        },
    }
    write_json(router_dir / "router-complete.json", router_completion)
    return script_dir, public_attempt, private_attempt


def refresh_selected_bindings(root: Path, public_attempt: Path) -> None:
    """Refresh every public record that legitimately binds the selected-point bytes."""
    router_dir = public_attempt / "router"
    selected_path = router_dir / "selected-operating-point.json"
    run_path = router_dir / "run.json"
    verification_path = router_dir / "verification.json"
    completion_path = router_dir / "router-complete.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["public_outputs"]["selected_operating_point_json"] = finalizer.artifact(
        selected_path, root
    )
    write_json(run_path, run)
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    verification["verified_artifacts"]["run"] = finalizer.artifact(run_path, root)
    write_json(verification_path, verification)
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    completion["artifacts"]["run"] = finalizer.artifact(run_path, root)
    completion["artifacts"]["final_verification"] = finalizer.artifact(
        verification_path, root
    )
    completion["artifacts"]["selected_operating_point"] = finalizer.artifact(
        selected_path, root
    )
    write_json(completion_path, completion)


class RouterReplicationFinalizerTests(unittest.TestCase):
    def test_pass_and_fail_attempts_are_selected_without_cross_seed_decision(self) -> None:
        for passed in (True, False):
            with self.subTest(passed=passed), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                script_dir, _public, _private = synthetic_attempt(root, passed=passed)
                selection = finalizer.finalize_attempt(
                    "EXP-061", "attempt-1", script_dir=script_dir, project_root=root
                )
                self.assertEqual(selection["decision"], "Pass" if passed else "Fail")
                self.assertEqual(selection["primary_gate_passed"], passed)
                self.assertIn("EXP-063 alone", selection["claim_boundary"])
                self.assertEqual(set(selection["completions"]), set(finalizer.STAGES))

    def test_selection_is_atomic_and_single_use(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script_dir, _public, _private = synthetic_attempt(root)
            finalizer.finalize_attempt(
                "EXP-061", "attempt-1", script_dir=script_dir, project_root=root
            )
            with self.assertRaises(FileExistsError):
                finalizer.finalize_attempt(
                    "EXP-061", "attempt-1", script_dir=script_dir, project_root=root
                )

    def test_tampered_stage_artifact_hash_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script_dir, public_attempt, _private = synthetic_attempt(root)
            (public_attempt / "calibration" / "run.json").write_text("tampered\n")
            with self.assertRaisesRegex(ValueError, "Artifact record drift"):
                finalizer.validate_attempt(
                    "EXP-061", "attempt-1", script_dir=script_dir, project_root=root
                )

    def test_calibration_parent_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script_dir, public_attempt, _private = synthetic_attempt(root)
            path = public_attempt / "calibration-complete.json"
            value = json.loads(path.read_text())
            value["replication_parent_experiment_id"] = "EXP-062"
            write_json(path, value)
            with self.assertRaisesRegex(ValueError, "parent identity"):
                finalizer.validate_attempt(
                    "EXP-061", "attempt-1", script_dir=script_dir, project_root=root
                )

    def test_router_decision_tamper_is_rejected_for_both_directions(self) -> None:
        for passed, decision in ((True, "Fail"), (False, "Pass")):
            with self.subTest(passed=passed), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                script_dir, public_attempt, _private = synthetic_attempt(root, passed=passed)
                path = public_attempt / "router" / "router-complete.json"
                value = json.loads(path.read_text())
                value["decision"] = decision
                write_json(path, value)
                with self.assertRaisesRegex(ValueError, "verified frozen primary gate"):
                    finalizer.validate_attempt(
                        "EXP-061", "attempt-1", script_dir=script_dir, project_root=root
                    )

    def test_selected_point_identity_inventory_and_heuristic_role_tamper_is_rejected(self) -> None:
        mutations = {
            "schema": lambda selected: selected.__setitem__("schema_version", "tampered"),
            "experiment": lambda selected: selected.__setitem__("experiment_id", "EXP-062"),
            "run": lambda selected: selected.__setitem__("run_id", "wrong-run"),
            "attempt": lambda selected: selected.__setitem__("attempt_id", "attempt-99"),
            "seed": lambda selected: selected.__setitem__("model_seed", 44),
            "missing_policy": lambda selected: selected["policies"].pop("m1_max_entropy"),
            "heuristic_role": lambda selected: selected["policies"]["m1_max_entropy"].__setitem__(
                "evidence_role", "primary"
            ),
            "heuristic_pass": lambda selected: selected["policies"]["m1_threshold_proximity"].__setitem__(
                "passed", True
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                script_dir, public_attempt, _private = synthetic_attempt(root)
                selected_path = public_attempt / "router" / "selected-operating-point.json"
                selected = json.loads(selected_path.read_text(encoding="utf-8"))
                mutate(selected)
                write_json(selected_path, selected)
                refresh_selected_bindings(root, public_attempt)
                with self.assertRaisesRegex(
                    ValueError, "verified frozen primary gate"
                ):
                    finalizer.validate_attempt(
                        "EXP-061", "attempt-1", script_dir=script_dir, project_root=root
                    )

    def test_broken_symlink_completion_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script_dir, public_attempt, _private = synthetic_attempt(root)
            path = public_attempt / "router" / "router-complete.json"
            path.unlink()
            path.symlink_to(public_attempt / "missing.json")
            with self.assertRaisesRegex(ValueError, "Symlink path component"):
                finalizer.validate_attempt(
                    "EXP-061", "attempt-1", script_dir=script_dir, project_root=root
                )

    def test_source_has_no_runner_or_verifier_import(self) -> None:
        source = FINALIZER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("run_exp0", source)
        self.assertNotIn("verify_exp0", source)


if __name__ == "__main__":
    unittest.main()
