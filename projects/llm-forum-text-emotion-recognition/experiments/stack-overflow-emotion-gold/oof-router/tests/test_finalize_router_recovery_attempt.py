from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1]
FINALIZER_PATH = MODULE_DIR / "finalize_router_replication_attempt.py"
BASE_TEST_PATH = MODULE_DIR / "tests" / "test_finalize_router_replication_attempt.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


finalizer = load(FINALIZER_PATH, "router_recovery_finalizer_under_test")
base_tests = load(BASE_TEST_PATH, "router_recovery_base_fixture")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def write_payload(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def record(path: Path, root: Path) -> dict:
    return finalizer.artifact(path, root)


def build_checks() -> tuple[list[dict], list[dict], list[dict]]:
    failure_names = sorted(finalizer.RECOVERY_ATTEMPT1_FAILURES)
    filler = [f"synthetic.check.{index:04d}" for index in range(4434 - len(failure_names))]
    names = [*failure_names, *filler]
    original = [
        {"name": name, "passed": name not in finalizer.RECOVERY_ATTEMPT1_FAILURES, "detail": None}
        for name in names
    ]
    mirror_a = copy.deepcopy(original)
    for row in mirror_a:
        if row["name"].startswith("permissions.public"):
            row["passed"] = True
    mirror_b = copy.deepcopy(mirror_a)
    for row in mirror_b:
        row["passed"] = True
    return original, mirror_a, mirror_b


def mirror_metadata(
    token: str, overlay: bool, config_sha: str, copy_manifest: list[dict]
) -> dict:
    return {
        "fresh_project_root": True,
        "project_root_mode": "0o700",
        "canonical_layout": True,
        "copy_only": True,
        "copied_file_count": len(copy_manifest),
        "copy_manifest_sha256": finalizer.canonical_digest(copy_manifest),
        "no_symlinks": True,
        "no_hardlinks": True,
        "instance_token_sha256": token,
        "overlay_enabled": overlay,
        "overlay_load_count": 1 if overlay else 0,
        "matching_sha_load_count": 2 if overlay else 0,
        "overlay_input_sha256": config_sha if overlay else None,
        "cleaned": True,
    }


def upgrade_to_recovery(
    root: Path, script_dir: Path, public_attempt: Path, private_attempt: Path
) -> Path:
    router_dir = public_attempt / "router"
    private_router_dir = private_attempt / "router"
    config_path = script_dir / (
        "configs/exp-061-seed-43-router-replication-router-formal-attempt-1.json"
    )
    run_path = router_dir / "run.json"
    selected_path = router_dir / "selected-operating-point.json"
    private_router = private_router_dir / "router-oof.npz"
    paired = private_attempt / "paired-oof.npz"
    canonical_runner = script_dir / "run_exp060_router.py"
    write_payload(canonical_runner, "synthetic canonical router runner\n")
    identity = {
        "experiment_id": "EXP-061",
        "run_id": finalizer.REGISTERED["EXP-061"][1],
        "attempt_id": "attempt-1",
        "model_seed": 43,
        "seed_contract": finalizer.expected_seed_contract(43),
    }

    write_json(
        config_path,
        {
            "schema_version": "exp-router-replication-config-v2",
            **identity,
            "rq_id": finalizer.RECOVERY_RQ_ID,
            "stage": finalizer.RECOVERY_STAGE,
            "router": {
                "policies": list(finalizer.DEPLOYABLE_POLICIES),
                "deployable_policy_order": list(finalizer.DEPLOYABLE_POLICIES),
            },
            "implementation": {"runner": record(canonical_runner, root)},
        },
    )
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["rq_id"] = finalizer.RECOVERY_RQ_ID
    run["stage"] = finalizer.RECOVERY_STAGE
    run["seed_contract"] = identity["seed_contract"]
    run["config"] = record(config_path, root)
    run["public_outputs"]["selected_operating_point_json"] = record(selected_path, root)
    write_json(run_path, run)

    public_files = (
        "REPORT.md",
        "bootstrap.json",
        "call-rate-performance.csv",
        "call-rate-performance.png",
        "feature-contract.json",
        "fold-summary.csv",
        "policy-comparisons.csv",
        "positive-label-retention.csv",
        "random-routing.csv",
        "routed-risk-coverage.csv",
        "routed-risk-coverage.png",
        "router-discrimination.json",
    )
    for name in public_files:
        write_payload(router_dir / name, f"synthetic {name}\n")
    frozen_dir = router_dir / "frozen-sources"
    frozen_names = (
        "config.json",
        "exp-060-pre-qwen-deployable-router.md",
        "run_exp060_router.py",
        "test_exp060_router.py",
        "verify_exp060_router.py",
    )
    for name in frozen_names:
        payload = (
            canonical_runner.read_text(encoding="utf-8")
            if name == "run_exp060_router.py"
            else f"synthetic frozen {name}\n"
        )
        write_payload(frozen_dir / name, payload)
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["frozen_sources"] = {
        "config": record(frozen_dir / "config.json", root),
        "protocol": record(
            frozen_dir / "exp-060-pre-qwen-deployable-router.md", root
        ),
        "runner": record(frozen_dir / "run_exp060_router.py", root),
        "tests": record(frozen_dir / "test_exp060_router.py", root),
        "verifier": record(frozen_dir / "verify_exp060_router.py", root),
    }
    write_json(run_path, run)

    os.chmod(router_dir, 0o755)
    os.chmod(frozen_dir, 0o755)
    for name in (*public_files, "run.json", "selected-operating-point.json"):
        os.chmod(router_dir / name, 0o644)
    os.chmod(private_attempt.parent, 0o700)
    os.chmod(private_attempt, 0o700)
    os.chmod(paired, 0o600)
    os.chmod(private_router_dir, 0o700)
    os.chmod(private_router, 0o600)

    expected_verified = {
        "config": record(config_path, root),
        "run": record(run_path, root),
        "input": record(paired, root),
        "private_router_oof": record(private_router, root),
    }
    split = {
        "accessed_splits": ["train-oof"],
        "validation_accessed": False,
        "test_inputs_accessed": False,
        "test_labels_accessed": False,
        "raw_text_accessed": False,
        "model_loaded_or_forward_run": False,
    }
    independence = {
        "runner_imported": False,
        "raw_exp058_recomputation": True,
        "nested_thresholds_recomputed": True,
        "scalers_and_routers_refit": True,
        "public_and_private_outputs_recomputed": True,
    }
    original_checks, checks_a, checks_b = build_checks()
    original_path = router_dir / "verification.json"
    original = {
        "schema_version": "exp-router-formal-verification-v2",
        **identity,
        "rq_id": "RQ-S3",
        "stage": finalizer.RECOVERY_STAGE,
        "scope": "final",
        "status": "Failed",
        "verified_at_utc": "2026-08-21T00:00:00+00:00",
        "passed_count": 4417,
        "failed_count": 17,
        "checks": original_checks,
        "independence": independence,
        "verified_artifacts": expected_verified,
        "split_access": split,
    }
    write_json(original_path, original)
    original_summary = router_dir / "VERIFICATION-SUMMARY.md"
    write_payload(original_summary, "synthetic original Failed summary\n")

    protocol = (
        root
        / "experiments/stack-overflow-emotion-gold/protocols/"
        "exp-061-exp060-final-verification-attempt-2-amendment.md"
    )
    base_verifier = script_dir / "verify_exp060_router.py"
    recovery_verifier = script_dir / "verify_exp060_router_attempt2.py"
    recovery_tests = script_dir / "tests/test_exp060_router_attempt2.py"
    finalizer_tests = script_dir / "tests/test_finalize_router_recovery_attempt.py"
    write_payload(protocol, "synthetic recovery protocol\n")
    write_payload(base_verifier, "import json\n")
    write_payload(recovery_verifier, "import json\n")
    write_payload(recovery_tests, "# synthetic recovery tests\n")
    write_payload(finalizer_tests, "# synthetic finalizer recovery tests\n")

    target = {
        "formal_config": record(config_path, root),
        "run": record(run_path, root),
        "selected_operating_point": record(selected_path, root),
        "paired_oof": record(paired, root),
        "private_router_oof": record(private_router, root),
        "attempt_1_failed_verification": record(original_path, root),
        "attempt_1_failed_summary": record(original_summary, root),
    }
    pre_manifest = []
    after_manifest = []
    for relative, kind, before_mode, after_mode in finalizer.RECOVERY_MODE_PATHS:
        path = public_attempt / relative
        row = {
            "path": finalizer.display_path(path, root),
            "type": kind,
            "before_mode": f"0o{before_mode:o}",
            "after_mode": f"0o{after_mode:o}",
        }
        if kind == "file":
            row.update({"bytes": path.stat().st_size, "sha256": finalizer.sha256(path)})
        pre_manifest.append(row)
        after_manifest.append(
            {**row, "observed_mode": f"0o{after_mode:o}", "matches_expected": True}
        )
    tree = finalizer.recovery_public_tree_digest(router_dir, root)
    private_rows = [target["paired_oof"], target["private_router_oof"]]
    private_mode_specs = (
        (private_attempt.parent, "directory", 0o700),
        (private_attempt, "directory", 0o700),
        (paired, "file", 0o600),
        (private_router_dir, "directory", 0o700),
        (private_router, "file", 0o600),
    )
    private_invariant = {
        "artifact_count": 2,
        "sha256": finalizer.canonical_digest(private_rows),
        "artifacts": private_rows,
        "modes": [
            {
                "path": finalizer.display_path(path, root),
                "type": kind,
                "expected_mode": f"0o{mode:o}",
                "observed_mode": f"0o{mode:o}",
                "matches_expected": True,
            }
            for path, kind, mode in private_mode_specs
        ],
    }
    overlay = {
        "operation": "replace",
        "json_pointer": "/router/policies",
        "match_input_sha256": target["formal_config"]["sha256"],
        "before": list(finalizer.DEPLOYABLE_POLICIES),
        "after": list(finalizer.RECOVERY_FULL_POLICIES),
        "deployable_policy_order_unchanged": list(finalizer.DEPLOYABLE_POLICIES),
        "recursive_diff": [
            {
                "path": "$.router.policies",
                "before": list(finalizer.DEPLOYABLE_POLICIES),
                "after": list(finalizer.RECOVERY_FULL_POLICIES),
            }
        ],
        "maximum_changed_nodes": 1,
    }
    attempt2_path = router_dir / "verification-attempt-2.json"
    attempt2_summary = router_dir / "VERIFICATION-SUMMARY-ATTEMPT-2.md"
    completion_path = router_dir / "router-complete.json"
    selection_path = public_attempt.parent / "selected-attempt.json"
    implementation = {
        "amendment_protocol": record(protocol, root),
        "base_verifier": record(base_verifier, root),
        "recovery_verifier": record(recovery_verifier, root),
        "recovery_tests": record(recovery_tests, root),
        "finalizer": record(script_dir / "finalize_router_replication_attempt.py", root),
        "finalizer_tests": record(finalizer_tests, root),
    }
    amendment = {
        "schema_version": "exp-router-verification-attempt-2-amendment-config-v1",
        "experiment_id": identity["experiment_id"],
        "run_id": identity["run_id"],
        "attempt_id": identity["attempt_id"],
        "model_seed": identity["model_seed"],
        "incident_id": "001",
        "authorization": {
            "verification_attempt": 2,
            "public_mode_metadata_repair": True,
            "scientific_analysis_rerun": False,
            "private_artifact_mutation": False,
            "validation_access": False,
            "test_access": False,
            "model_loading_or_forward": False,
            "raw_text_access": False,
            "seed44_execution": False,
        },
        "implementation": implementation,
        "target": target,
        "clerical_overlay": overlay,
        "public_mode_normalization": {
            "path_count": 16,
            "pre_manifest": pre_manifest,
            "content_tree_digest_algorithm": finalizer.RECOVERY_TREE_DIGEST_ALGORITHM,
            "content_tree_before": tree,
        },
        "private_invariant": private_invariant,
        "outputs": {
            "verification": finalizer.display_path(attempt2_path, root),
            "summary": finalizer.display_path(attempt2_summary, root),
            "completion": finalizer.display_path(completion_path, root),
            "selection": finalizer.display_path(selection_path, root),
        },
        "commands": {
            scope: (
                finalizer.RECOVERY_PYTHON
                + " experiments/stack-overflow-emotion-gold/oof-router/"
                "verify_exp060_router_attempt2.py --scope "
                + scope
            )
            for scope in ("normalize", "final", "complete", "completion")
        },
    }
    amendment_path = (
        script_dir
        / "configs/exp-061-seed-43-router-replication-router-verification-attempt-2-amendment.json"
    )
    write_json(amendment_path, amendment)

    copy_manifest = finalizer.recovery_mirror_copy_manifest(
        json.loads(config_path.read_text(encoding="utf-8")),
        json.loads(run_path.read_text(encoding="utf-8")),
        formal_config_path=config_path,
        run_path=run_path,
        base_verifier_path=base_verifier,
        canonical_runner_path=script_dir / "run_exp060_router.py",
        project_root=root,
    )
    metadata_a = mirror_metadata(
        "1" * 64, False, target["formal_config"]["sha256"], copy_manifest
    )
    metadata_b = mirror_metadata(
        "2" * 64, True, target["formal_config"]["sha256"], copy_manifest
    )
    recovery_rows = [
        {"name": name, "passed": True, "detail": None}
        for name in finalizer.RECOVERY_CHECK_NAMES
    ]
    attempt2 = {
        "schema_version": "exp-router-formal-verification-attempt-2-v1",
        **identity,
        "rq_id": "RQ-S3",
        "stage": finalizer.RECOVERY_STAGE,
        "scope": "final",
        "verification_attempt": 2,
        "status": "Passed",
        "runner_imported": False,
        "verified_at_utc": "2026-08-21T00:00:01+00:00",
        "passed_count": 4434,
        "failed_count": 0,
        "checks": checks_b,
        "independence": copy.deepcopy(finalizer.RECOVERY_ATTEMPT2_INDEPENDENCE),
        "verified_artifacts": expected_verified,
        "split_access": split,
        "recovery": {
            "schema_version": "exp-router-verification-recovery-evidence-v1",
            "incident_id": "001",
            "classification": "clerical_config_misencoding",
            "amendment_config": record(amendment_path, root),
            "amendment_protocol": implementation["amendment_protocol"],
            "original_failed_verification": target["attempt_1_failed_verification"],
            "original_failed_summary": target["attempt_1_failed_summary"],
            "base_verifier": implementation["base_verifier"],
            "recovery_verifier": implementation["recovery_verifier"],
            "overlay": {**overlay, "applied_load_count": 1},
            "mode_normalization": {
                "path_count": 16,
                "content_tree_digest_algorithm": finalizer.RECOVERY_TREE_DIGEST_ALGORITHM,
                "before": pre_manifest,
                "after": after_manifest,
                "content_tree_before": tree,
                "content_tree_after": tree,
                "private_before": private_invariant,
                "private_after": private_invariant,
            },
            "recomputation": {
                "mirror_a": {
                    "role": "unchanged_config_control",
                    "status": "Failed",
                    "passed_count": 4433,
                    "failed_count": 1,
                    "checks": checks_a,
                    "independence": independence,
                    "verified_artifacts": expected_verified,
                    "split_access": split,
                    "mirror": metadata_a,
                },
                "mirror_b": {
                    "role": "sha_bound_overlay_recovery",
                    "status": "Passed",
                    "passed_count": 4434,
                    "failed_count": 0,
                    "checks_location": "$.checks",
                    "checks_sha256": finalizer.canonical_digest(checks_b),
                    "independence": independence,
                    "verified_artifacts": expected_verified,
                    "split_access": split,
                    "mirror": metadata_b,
                },
                "check_name_order_sha256": finalizer.canonical_digest(
                    [row["name"] for row in checks_b]
                ),
            },
            "recovery_checks": recovery_rows,
        },
        "claim_boundary": finalizer.RECOVERY_ATTEMPT2_CLAIM_BOUNDARY,
    }
    write_json(attempt2_path, attempt2)
    write_payload(
        attempt2_summary,
        finalizer.render_recovery_summary(attempt2).decode("utf-8"),
    )
    lineage = {
        "incident_id": "001",
        "original_failed_verification": target["attempt_1_failed_verification"],
        "original_failed_summary": target["attempt_1_failed_summary"],
        "amendment_config": record(amendment_path, root),
        "amendment_protocol": implementation["amendment_protocol"],
        "passed_verification": record(attempt2_path, root),
        "passed_summary": record(attempt2_summary, root),
    }
    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    completion = {
        "schema_version": "exp-router-completion-v2",
        **identity,
        "stage": finalizer.RECOVERY_STAGE,
        "status": "Complete",
        "completed_at_utc": "2026-08-21T00:00:02+00:00",
        "decision": selected["overall"]["decision"],
        "primary_gate_passed": selected["policies"]["logistic_router"]["passed"],
        "verification_attempt": 2,
        "recovery_lineage": lineage,
        "artifacts": {
            "config": target["formal_config"],
            "run": target["run"],
            "selected_operating_point": target["selected_operating_point"],
            "final_verification": record(attempt2_path, root),
            "private_router_oof": target["private_router_oof"],
        },
        "next_gate": finalizer.RECOVERY_COMPLETION_NEXT_GATE,
        "claim_boundary": finalizer.RECOVERY_COMPLETION_CLAIM_BOUNDARY,
    }
    write_json(completion_path, completion)
    return attempt2_path


def refresh_attempt2_completion(root: Path, public_attempt: Path) -> None:
    attempt2_path = public_attempt / "router/verification-attempt-2.json"
    completion_path = public_attempt / "router/router-complete.json"
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    current = record(attempt2_path, root)
    completion["artifacts"]["final_verification"] = current
    completion["recovery_lineage"]["passed_verification"] = current
    write_json(completion_path, completion)


class RouterRecoveryFinalizerTests(unittest.TestCase):
    def test_finalizer_output_is_0644_under_restrictive_umask(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "selected-attempt.json"
            previous = os.umask(0o077)
            try:
                finalizer.create_json_once(path, {"status": "Selected"})
            finally:
                os.umask(previous)
            observed = os.lstat(path)
            self.assertTrue(stat.S_ISREG(observed.st_mode))
            self.assertEqual(observed.st_mode & 0o777, 0o644)
            self.assertEqual(observed.st_nlink, 1)

    def test_exact_recovery_is_selected_with_failed_to_passed_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script_dir, public_attempt, private_attempt = base_tests.synthetic_attempt(root)
            upgrade_to_recovery(root, script_dir, public_attempt, private_attempt)
            selection, _completions, _paths = finalizer.validate_attempt(
                "EXP-061",
                "attempt-1",
                script_dir=script_dir,
                project_root=root,
            )
            self.assertEqual(selection["recovery_lineage"]["incident_id"], "001")
            self.assertTrue(
                selection["recovery_lineage"]["original_failed_verification"]["path"].endswith(
                    "/verification.json"
                )
            )
            self.assertTrue(
                selection["recovery_lineage"]["passed_verification"]["path"].endswith(
                    "/verification-attempt-2.json"
                )
            )
            self.assertTrue(
                selection["recovery_lineage"]["passed_summary"]["path"].endswith(
                    "/VERIFICATION-SUMMARY-ATTEMPT-2.md"
                )
            )

    def test_attempt2_check_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script_dir, public_attempt, private_attempt = base_tests.synthetic_attempt(root)
            path = upgrade_to_recovery(root, script_dir, public_attempt, private_attempt)
            value = json.loads(path.read_text(encoding="utf-8"))
            value["checks"][10]["passed"] = False
            write_json(path, value)
            refresh_attempt2_completion(root, public_attempt)
            with self.assertRaises(ValueError):
                finalizer.validate_attempt(
                    "EXP-061", "attempt-1", script_dir=script_dir, project_root=root
                )

    def test_all_frozen_sensitive_keys_in_check_detail_are_rejected_after_rehash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script_dir, public_attempt, private_attempt = base_tests.synthetic_attempt(root)
            path = upgrade_to_recovery(root, script_dir, public_attempt, private_attempt)
            expected = {
                "component_id", "component_ids", "feature_matrix", "features",
                "fold_id", "fold_ids", "gold", "logit", "logits", "prediction",
                "predictions", "probability", "probabilities", "feature",
                "router_targets", "route_mask", "route_masks", "route_score",
                "route_scores", "sample_id", "sample_ids", "target", "targets",
                "raw_text", "text",
            }
            self.assertEqual(finalizer.PUBLIC_SENSITIVE_KEYS, expected)
            original = json.loads(path.read_text(encoding="utf-8"))
            for key in sorted(expected):
                with self.subTest(key=key):
                    value = copy.deepcopy(original)
                    value["checks"][10]["detail"] = {key: "private-row"}
                    value["recovery"]["recomputation"]["mirror_b"][
                        "checks_sha256"
                    ] = finalizer.canonical_digest(value["checks"])
                    write_json(path, value)
                    refresh_attempt2_completion(root, public_attempt)
                    with self.assertRaises(ValueError):
                        finalizer.validate_attempt(
                            "EXP-061",
                            "attempt-1",
                            script_dir=script_dir,
                            project_root=root,
                        )

    def test_artifact_record_types_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "artifact.json"
            write_json(path, {"ok": True})
            valid = record(path, root)
            for key, bad_value in (
                ("path", 7),
                ("bytes", False),
                ("bytes", -1),
                ("sha256", valid["sha256"].upper()),
            ):
                with self.subTest(key=key, bad_value=bad_value):
                    tampered = copy.deepcopy(valid)
                    tampered[key] = bad_value
                    with self.assertRaises(ValueError):
                        finalizer.require_record(tampered, root)

    def test_bool_counts_and_nonexact_check_rows_are_rejected(self) -> None:
        mutations = (
            lambda item: item.__setitem__("failed_count", False),
            lambda item: item["checks"][0].__setitem__("passed", 1),
            lambda item: item["checks"][0].__setitem__("extra", None),
            lambda item: item["recovery"]["recomputation"]["mirror_a"].__setitem__(
                "passed_count", True
            ),
            lambda item: item["recovery"]["recomputation"]["mirror_a"]["checks"][
                0
            ].pop("detail"),
            lambda item: item["recovery"]["recomputation"]["mirror_a"]["mirror"].__setitem__(
                "overlay_load_count", False
            ),
            lambda item: item["independence"].__setitem__("fresh_mirror_a", 1),
            lambda item: item["recovery"]["overlay"].__setitem__(
                "applied_load_count", True
            ),
            lambda item: item["recovery"]["recovery_checks"][0].__setitem__(
                "passed", 1
            ),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate.__code__.co_firstlineno):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    script_dir, public_attempt, private_attempt = base_tests.synthetic_attempt(root)
                    path = upgrade_to_recovery(
                        root, script_dir, public_attempt, private_attempt
                    )
                    value = json.loads(path.read_text(encoding="utf-8"))
                    mutate(value)
                    write_json(path, value)
                    refresh_attempt2_completion(root, public_attempt)
                    with self.assertRaises(ValueError):
                        finalizer.validate_attempt(
                            "EXP-061",
                            "attempt-1",
                            script_dir=script_dir,
                            project_root=root,
                        )

    def test_attempt2_independence_inventory_tamper_is_rejected(self) -> None:
        mutations = (
            lambda value: value["independence"].pop("fresh_mirror_a"),
            lambda value: value["independence"].__setitem__("arbitrary", True),
            lambda value: value["independence"].__setitem__("fresh_mirror_a", False),
            lambda value: value.__setitem__("independence", {"arbitrary": True}),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate.__code__.co_firstlineno):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    script_dir, public_attempt, private_attempt = base_tests.synthetic_attempt(root)
                    path = upgrade_to_recovery(
                        root, script_dir, public_attempt, private_attempt
                    )
                    value = json.loads(path.read_text(encoding="utf-8"))
                    mutate(value)
                    write_json(path, value)
                    refresh_attempt2_completion(root, public_attempt)
                    with self.assertRaises(ValueError):
                        finalizer.validate_attempt(
                            "EXP-061",
                            "attempt-1",
                            script_dir=script_dir,
                            project_root=root,
                        )

    def test_attempt2_identity_claim_and_timestamp_tamper_are_rejected(self) -> None:
        mutations = (
            lambda item: item.__setitem__("rq_id", "WRONG"),
            lambda item: item.__setitem__("stage", "WRONG"),
            lambda item: item.__setitem__("seed_contract", {"model_seed": 43}),
            lambda item: item.__setitem__("claim_boundary", "WRONG"),
            lambda item: item.__setitem__("verified_at_utc", "2026-08-21"),
            lambda item: item.__setitem__(
                "verified_at_utc", "2026-08-21T00:00:03+00:00"
            ),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate.__code__.co_firstlineno):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    script_dir, public_attempt, private_attempt = base_tests.synthetic_attempt(root)
                    path = upgrade_to_recovery(
                        root, script_dir, public_attempt, private_attempt
                    )
                    value = json.loads(path.read_text(encoding="utf-8"))
                    mutate(value)
                    write_json(path, value)
                    refresh_attempt2_completion(root, public_attempt)
                    with self.assertRaises(ValueError):
                        finalizer.validate_attempt(
                            "EXP-061",
                            "attempt-1",
                            script_dir=script_dir,
                            project_root=root,
                        )

    def test_mirror_copy_manifest_metadata_tamper_is_rejected(self) -> None:
        mutations = (
            lambda metadata: metadata.__setitem__("copied_file_count", 20),
            lambda metadata: metadata.__setitem__("copied_file_count", 24),
            lambda metadata: metadata.__setitem__("copy_manifest_sha256", "b" * 64),
            lambda metadata: metadata.__setitem__("arbitrary", True),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate.__code__.co_firstlineno):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    script_dir, public_attempt, private_attempt = base_tests.synthetic_attempt(root)
                    path = upgrade_to_recovery(
                        root, script_dir, public_attempt, private_attempt
                    )
                    value = json.loads(path.read_text(encoding="utf-8"))
                    metadata = value["recovery"]["recomputation"]["mirror_a"]["mirror"]
                    mutate(metadata)
                    write_json(path, value)
                    refresh_attempt2_completion(root, public_attempt)
                    with self.assertRaises(ValueError):
                        finalizer.validate_attempt(
                            "EXP-061",
                            "attempt-1",
                            script_dir=script_dir,
                            project_root=root,
                        )

    def test_attempt2_nested_schema_tamper_is_rejected(self) -> None:
        mutations = (
            lambda item: item["recovery"]["mode_normalization"].__setitem__(
                "arbitrary", True
            ),
            lambda item: item["recovery"]["recomputation"].__setitem__(
                "arbitrary", True
            ),
            lambda item: item["recovery"]["recomputation"]["mirror_a"].__setitem__(
                "arbitrary", True
            ),
            lambda item: item["recovery"]["recomputation"]["mirror_b"].__setitem__(
                "arbitrary", True
            ),
            lambda item: item["recovery"]["recovery_checks"][0].__setitem__(
                "detail", "not-null"
            ),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate.__code__.co_firstlineno):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    script_dir, public_attempt, private_attempt = base_tests.synthetic_attempt(root)
                    path = upgrade_to_recovery(
                        root, script_dir, public_attempt, private_attempt
                    )
                    value = json.loads(path.read_text(encoding="utf-8"))
                    mutate(value)
                    write_json(path, value)
                    refresh_attempt2_completion(root, public_attempt)
                    with self.assertRaises(ValueError):
                        finalizer.validate_attempt(
                            "EXP-061",
                            "attempt-1",
                            script_dir=script_dir,
                            project_root=root,
                        )

    def test_recovery_completion_contract_tamper_is_rejected(self) -> None:
        mutations = (
            lambda item: item.__setitem__("stage", "WRONG"),
            lambda item: item.__setitem__("claim_boundary", "WRONG"),
            lambda item: item.__setitem__("next_gate", "WRONG"),
            lambda item: item.__setitem__("completed_at_utc", "2026-08-21"),
            lambda item: item.__setitem__(
                "completed_at_utc", "2026-08-21T00:00:00+00:00"
            ),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate.__code__.co_firstlineno):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    script_dir, public_attempt, private_attempt = base_tests.synthetic_attempt(root)
                    upgrade_to_recovery(root, script_dir, public_attempt, private_attempt)
                    completion_path = public_attempt / "router/router-complete.json"
                    completion = json.loads(completion_path.read_text(encoding="utf-8"))
                    mutate(completion)
                    write_json(completion_path, completion)
                    with self.assertRaises(ValueError):
                        finalizer.validate_attempt(
                            "EXP-061",
                            "attempt-1",
                            script_dir=script_dir,
                            project_root=root,
                        )

    def test_attempt2_summary_content_and_mode_tamper_are_rejected(self) -> None:
        for tamper_kind in ("content", "mode"):
            with self.subTest(tamper=tamper_kind):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    script_dir, public_attempt, private_attempt = base_tests.synthetic_attempt(root)
                    upgrade_to_recovery(root, script_dir, public_attempt, private_attempt)
                    summary = public_attempt / "router" / finalizer.RECOVERY_SUMMARY_NAME
                    if tamper_kind == "content":
                        summary.write_text("tampered summary\n", encoding="utf-8")
                        completion_path = public_attempt / "router/router-complete.json"
                        completion = json.loads(completion_path.read_text(encoding="utf-8"))
                        completion["recovery_lineage"]["passed_summary"] = record(
                            summary, root
                        )
                        write_json(completion_path, completion)
                    else:
                        os.chmod(summary, 0o600)
                    with self.assertRaises(ValueError):
                        finalizer.validate_attempt(
                            "EXP-061",
                            "attempt-1",
                            script_dir=script_dir,
                            project_root=root,
                        )

    def test_tree_digest_excludes_only_exact_router_root_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            router = root / "router"
            nested = router / "frozen-sources/verification-attempt-2.json"
            root_sidecar = router / finalizer.RECOVERY_VERIFICATION_NAME
            nested.parent.mkdir(parents=True)
            nested.write_text("nested-a\n", encoding="utf-8")
            root_sidecar.write_text("root-a\n", encoding="utf-8")
            before = finalizer.recovery_public_tree_digest(router, root)
            root_sidecar.write_text("root-b\n", encoding="utf-8")
            self.assertEqual(
                finalizer.recovery_public_tree_digest(router, root), before
            )
            nested.write_text("nested-b\n", encoding="utf-8")
            self.assertNotEqual(
                finalizer.recovery_public_tree_digest(router, root), before
            )

    def test_live_mode_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script_dir, public_attempt, private_attempt = base_tests.synthetic_attempt(root)
            upgrade_to_recovery(root, script_dir, public_attempt, private_attempt)
            os.chmod(public_attempt / "router/run.json", 0o600)
            with self.assertRaises(ValueError):
                finalizer.validate_attempt(
                    "EXP-061", "attempt-1", script_dir=script_dir, project_root=root
                )

    def test_post_normalization_public_hardlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script_dir, public_attempt, private_attempt = base_tests.synthetic_attempt(root)
            upgrade_to_recovery(root, script_dir, public_attempt, private_attempt)
            os.link(public_attempt / "router/run.json", root / "outside-router-hardlink")
            with self.assertRaises(ValueError):
                finalizer.validate_attempt(
                    "EXP-061", "attempt-1", script_dir=script_dir, project_root=root
                )

    def test_recovery_governance_sidecar_mode_and_hardlink_tamper_are_rejected(self) -> None:
        relative_paths = (
            Path("router/verification-attempt-2.json"),
            Path("router/VERIFICATION-SUMMARY-ATTEMPT-2.md"),
            Path("router/router-complete.json"),
        )
        for relative in relative_paths:
            for tamper in ("mode", "hardlink"):
                with self.subTest(relative=str(relative), tamper=tamper):
                    with tempfile.TemporaryDirectory() as temporary:
                        root = Path(temporary)
                        script_dir, public_attempt, private_attempt = (
                            base_tests.synthetic_attempt(root)
                        )
                        upgrade_to_recovery(
                            root, script_dir, public_attempt, private_attempt
                        )
                        target = public_attempt / relative
                        if tamper == "mode":
                            os.chmod(target, 0o600)
                        else:
                            os.link(target, root / f"hardlink-{target.name}")
                        with self.assertRaises(ValueError):
                            finalizer.validate_attempt(
                                "EXP-061",
                                "attempt-1",
                                script_dir=script_dir,
                                project_root=root,
                            )

    def test_recovery_is_restricted_to_exp061_attempt1(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script_dir, public_attempt, _private_attempt = base_tests.synthetic_attempt(
                root, experiment_id="EXP-062"
            )
            standard = public_attempt / "router/verification.json"
            attempt2 = public_attempt / "router/verification-attempt-2.json"
            attempt2.write_bytes(standard.read_bytes())
            completion_path = public_attempt / "router/router-complete.json"
            completion = json.loads(completion_path.read_text(encoding="utf-8"))
            completion["verification_attempt"] = 2
            completion["artifacts"]["final_verification"] = record(attempt2, root)
            write_json(completion_path, completion)
            with self.assertRaises(PermissionError):
                finalizer.validate_attempt(
                    "EXP-062", "attempt-1", script_dir=script_dir, project_root=root
                )


if __name__ == "__main__":
    unittest.main()
