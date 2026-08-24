from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock


MODULE_DIR = Path(__file__).resolve().parents[1]
RECOVERY_PATH = MODULE_DIR / "verify_exp060_router_attempt2.py"


def load_module():
    spec = importlib.util.spec_from_file_location("exp060_attempt2_under_test", RECOVERY_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(RECOVERY_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recovery = load_module()


def frozen_after_manifest(config: dict) -> list[dict]:
    rows = []
    for frozen in config["public_mode_normalization"]["pre_manifest"]:
        row = copy.deepcopy(frozen)
        row["observed_mode"] = row["after_mode"]
        row["matches_expected"] = True
        rows.append(row)
    return rows


def mirror_metadata(token: str, *, overlay: bool) -> dict:
    manifest = recovery.expected_mirror_copy_manifest()
    return {
        "fresh_project_root": True,
        "project_root_mode": "0o700",
        "canonical_layout": True,
        "copy_only": True,
        "copied_file_count": len(manifest),
        "copy_manifest_sha256": recovery.canonical_digest(manifest),
        "no_symlinks": True,
        "no_hardlinks": True,
        "instance_token_sha256": token,
        "overlay_enabled": overlay,
        "overlay_load_count": 1 if overlay else 0,
        "matching_sha_load_count": 2 if overlay else 0,
        "overlay_input_sha256": (
            recovery.EXPECTED_IMMUTABLE[recovery.FORMAL_CONFIG_REL][1]
            if overlay
            else None
        ),
        "cleaned": True,
    }


def valid_attempt2_fixture() -> tuple[dict, list[dict]]:
    amendment_path, amendment = recovery.load_amendment_config()
    original = recovery.load_json(recovery.require_expected(recovery.ORIGINAL_VERIFICATION_REL))
    checks_a = copy.deepcopy(original["checks"])
    for row in checks_a:
        if row["name"].startswith("permissions.public"):
            row["passed"] = True
    checks_b = copy.deepcopy(checks_a)
    for row in checks_b:
        row["passed"] = True
    expected_verified = recovery.expected_verified_artifacts()
    metadata_a = mirror_metadata("1" * 64, overlay=False)
    metadata_b = mirror_metadata("2" * 64, overlay=True)
    after = frozen_after_manifest(amendment)
    base_independence = copy.deepcopy(original["independence"])
    split = copy.deepcopy(original["split_access"])
    recovery_rows = [
        recovery.check(name, True) for name in recovery.expected_recovery_check_names()
    ]
    value = {
        "schema_version": "exp-router-formal-verification-attempt-2-v1",
        "experiment_id": recovery.EXPERIMENT_ID,
        "rq_id": original["rq_id"],
        "stage": original["stage"],
        "run_id": recovery.RUN_ID,
        "attempt_id": recovery.ATTEMPT_ID,
        "model_seed": recovery.MODEL_SEED,
        "seed_contract": original["seed_contract"],
        "scope": "final",
        "verification_attempt": 2,
        "status": "Passed",
        "runner_imported": False,
        "verified_at_utc": "2026-08-21T03:00:00+00:00",
        "passed_count": 4434,
        "failed_count": 0,
        "checks": checks_b,
        "independence": copy.deepcopy(recovery.ATTEMPT2_INDEPENDENCE),
        "verified_artifacts": expected_verified,
        "split_access": split,
        "recovery": {
            "schema_version": "exp-router-verification-recovery-evidence-v1",
            "incident_id": "001",
            "classification": "clerical_config_misencoding",
            "amendment_config": recovery.artifact(amendment_path),
            "amendment_protocol": recovery.artifact(
                recovery.require_record(amendment["implementation"]["amendment_protocol"])
            ),
            "original_failed_verification": recovery.artifact(
                recovery.require_expected(recovery.ORIGINAL_VERIFICATION_REL)
            ),
            "original_failed_summary": recovery.artifact(
                recovery.require_expected(recovery.ORIGINAL_SUMMARY_REL)
            ),
            "base_verifier": recovery.artifact(
                recovery.require_expected(recovery.CANONICAL_VERIFIER_REL)
            ),
            "recovery_verifier": recovery.artifact(RECOVERY_PATH),
            "overlay": {**amendment["clerical_overlay"], "applied_load_count": 1},
            "mode_normalization": {
                "path_count": 16,
                "content_tree_digest_algorithm": recovery.PUBLIC_TREE_DIGEST_ALGORITHM,
                "before": amendment["public_mode_normalization"]["pre_manifest"],
                "after": after,
                "content_tree_before": amendment["public_mode_normalization"]["content_tree_before"],
                "content_tree_after": recovery.file_tree_digest(
                    recovery.resolve_relative(recovery.ROUTER_REL)
                ),
                "private_before": amendment["private_invariant"],
                "private_after": recovery.private_artifact_digest(),
            },
            "recomputation": {
                "mirror_a": {
                    "role": "unchanged_config_control",
                    "status": "Failed",
                    "passed_count": 4433,
                    "failed_count": 1,
                    "checks": checks_a,
                    "independence": base_independence,
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
                    "checks_sha256": recovery.canonical_digest(checks_b),
                    "independence": base_independence,
                    "verified_artifacts": expected_verified,
                    "split_access": split,
                    "mirror": metadata_b,
                },
                "check_name_order_sha256": recovery.canonical_digest(
                    [row["name"] for row in checks_b]
                ),
            },
            "recovery_checks": recovery_rows,
        },
        "claim_boundary": recovery.ATTEMPT2_CLAIM_BOUNDARY,
    }
    return value, after


class Attempt2RecoveryTests(unittest.TestCase):
    def test_amendment_config_freezes_unique_overlay_and_exact_modes(self) -> None:
        _path, config = recovery.load_amendment_config()
        original = recovery.load_json(recovery.require_expected(recovery.FORMAL_CONFIG_REL))
        effective = copy.deepcopy(original)
        effective["router"]["policies"] = list(recovery.FULL_POLICY_ORDER)
        self.assertEqual(config["clerical_overlay"]["recursive_diff"], recovery.recursive_diff(original, effective))
        self.assertEqual(len(config["clerical_overlay"]["recursive_diff"]), 1)
        self.assertEqual(config["public_mode_normalization"]["path_count"], 16)
        self.assertEqual(config["public_mode_normalization"]["pre_manifest"], recovery.frozen_mode_manifest())
        self.assertTrue(
            all(
                command.startswith(recovery.RECOVERY_PYTHON + " ")
                for command in config["commands"].values()
            )
        )

    def test_json_proxy_overlays_only_exact_config_bytes(self) -> None:
        path = recovery.require_expected(recovery.FORMAL_CONFIG_REL)
        payload = path.read_text(encoding="utf-8")
        proxy = recovery.JsonOverlayProxy(json, recovery.sha256(path))
        effective = proxy.loads(payload)
        self.assertEqual(effective["router"]["policies"], list(recovery.FULL_POLICY_ORDER))
        self.assertEqual(effective["router"]["deployable_policy_order"], list(recovery.DEPLOYABLE_POLICY_ORDER))
        self.assertEqual(proxy.overlay_load_count, 1)
        changed_bytes = payload + "\n"
        unchanged = proxy.loads(changed_bytes)
        self.assertEqual(unchanged["router"]["policies"], list(recovery.DEPLOYABLE_POLICY_ORDER))
        self.assertEqual(proxy.overlay_load_count, 1)
        duplicate = proxy.loads(payload)
        self.assertEqual(duplicate["router"]["policies"], list(recovery.DEPLOYABLE_POLICY_ORDER))
        self.assertEqual(proxy.matching_sha_load_count, 2)
        self.assertEqual(proxy.overlay_load_count, 1)

    def test_recovery_and_base_verifier_do_not_import_runner(self) -> None:
        recovery.assert_no_runner_import(RECOVERY_PATH)
        recovery.assert_no_runner_import(recovery.require_expected(recovery.CANONICAL_VERIFIER_REL))
        source = RECOVERY_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertFalse(
            any(
                isinstance(node, (ast.Import, ast.ImportFrom))
                and "run_exp060_router" in ast.unparse(node)
                for node in ast.walk(tree)
            )
        )

    def test_final_refuses_unnormalized_tree_before_any_mirror(self) -> None:
        with mock.patch.object(recovery, "run_fresh_mirror") as run_mirror:
            with self.assertRaises(PermissionError):
                recovery.build_attempt2_result()
        run_mirror.assert_not_called()

    def test_strict_attempt2_schema_accepts_only_full_recovery(self) -> None:
        value, after = valid_attempt2_fixture()
        with mock.patch.object(recovery, "mode_manifest", return_value=after):
            recovery.validate_attempt2_result(value, verify_artifact_record=False)
            tampered = copy.deepcopy(value)
            tampered["checks"][100]["passed"] = False
            with self.assertRaises(ValueError):
                recovery.validate_attempt2_result(tampered, verify_artifact_record=False)

            independence_tampers = []
            missing = copy.deepcopy(value)
            missing["independence"].pop("fresh_mirror_a")
            independence_tampers.append(missing)
            extra = copy.deepcopy(value)
            extra["independence"]["arbitrary"] = True
            independence_tampers.append(extra)
            false_value = copy.deepcopy(value)
            false_value["independence"]["fresh_mirror_a"] = False
            independence_tampers.append(false_value)
            arbitrary = copy.deepcopy(value)
            arbitrary["independence"] = {"arbitrary": True}
            independence_tampers.append(arbitrary)
            for independence_tamper in independence_tampers:
                with self.assertRaises(ValueError):
                    recovery.validate_attempt2_result(
                        independence_tamper, verify_artifact_record=False
                    )

    def test_base_recomputation_contract_is_exact(self) -> None:
        value, _after = valid_attempt2_fixture()
        mirror_a = copy.deepcopy(value["recovery"]["recomputation"]["mirror_a"])
        mirror_a.update(
            {
                "schema_version": "exp-router-formal-verification-v2",
                "scope": "final",
                "rq_id": recovery.RQ_ID,
                "stage": recovery.ROUTER_STAGE,
                "experiment_id": recovery.EXPERIMENT_ID,
                "run_id": recovery.RUN_ID,
                "attempt_id": recovery.ATTEMPT_ID,
                "model_seed": recovery.MODEL_SEED,
            }
        )
        mirror_b = copy.deepcopy(mirror_a)
        mirror_b["status"] = "Passed"
        mirror_b["passed_count"] = 4434
        mirror_b["failed_count"] = 0
        mirror_b["checks"] = copy.deepcopy(value["checks"])
        recovery.validate_base_recomputation(mirror_a, overlay=False)
        recovery.validate_base_recomputation(mirror_b, overlay=True)
        mirror_b["checks"][0]["name"] = "renamed"
        with self.assertRaises(ValueError):
            recovery.validate_base_recomputation(mirror_b, overlay=True)

    def test_mirror_copy_manifest_metadata_tamper_is_rejected(self) -> None:
        value, after = valid_attempt2_fixture()
        mutations = (
            lambda metadata: metadata.__setitem__("copied_file_count", 20),
            lambda metadata: metadata.__setitem__("copied_file_count", 24),
            lambda metadata: metadata.__setitem__("copy_manifest_sha256", "b" * 64),
            lambda metadata: metadata.__setitem__("arbitrary", True),
        )
        with mock.patch.object(recovery, "mode_manifest", return_value=after):
            for mutate in mutations:
                with self.subTest(mutation=mutate.__code__.co_firstlineno):
                    tampered = copy.deepcopy(value)
                    mutate(tampered["recovery"]["recomputation"]["mirror_a"]["mirror"])
                    with self.assertRaises(ValueError):
                        recovery.validate_attempt2_result(
                            tampered, verify_artifact_record=False
                        )

    def test_attempt2_identity_claim_and_timestamp_tamper_are_rejected(self) -> None:
        value, after = valid_attempt2_fixture()
        with mock.patch.object(recovery, "mode_manifest", return_value=after):
            mutations = (
                lambda item: item.__setitem__("rq_id", "WRONG"),
                lambda item: item.__setitem__("stage", "WRONG"),
                lambda item: item.__setitem__("seed_contract", {"model_seed": 43}),
                lambda item: item.__setitem__("claim_boundary", "WRONG"),
                lambda item: item.__setitem__("verified_at_utc", "2026-08-21"),
                lambda item: item.__setitem__(
                    "verified_at_utc", "2026-08-21T01:00:00+00:00"
                ),
            )
            for mutate in mutations:
                with self.subTest(mutation=mutate.__code__.co_firstlineno):
                    tampered = copy.deepcopy(value)
                    mutate(tampered)
                    with self.assertRaises(ValueError):
                        recovery.validate_attempt2_result(
                            tampered, verify_artifact_record=False
                        )

    def test_attempt2_nested_schema_tamper_is_rejected(self) -> None:
        value, after = valid_attempt2_fixture()
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
        with mock.patch.object(recovery, "mode_manifest", return_value=after):
            for mutate in mutations:
                with self.subTest(mutation=mutate.__code__.co_firstlineno):
                    tampered = copy.deepcopy(value)
                    mutate(tampered)
                    with self.assertRaises(ValueError):
                        recovery.validate_attempt2_result(
                            tampered, verify_artifact_record=False
                        )

    def test_amendment_incident_and_artifact_record_schema_are_exact(self) -> None:
        amendment_path = recovery.resolve_relative(recovery.AMENDMENT_CONFIG_REL)
        original_load_json = recovery.load_json

        def tampered_load_json(path: Path) -> dict:
            value = original_load_json(path)
            if path == amendment_path:
                value = copy.deepcopy(value)
                value["incident_id"] = "WRONG"
            return value

        with mock.patch.object(recovery, "load_json", side_effect=tampered_load_json):
            with self.assertRaises(ValueError):
                recovery.load_amendment_config()
        record = recovery.artifact(recovery.require_expected(recovery.FORMAL_CONFIG_REL))
        record["arbitrary"] = True
        with self.assertRaises(ValueError):
            recovery.require_record(record)
        valid = recovery.artifact(recovery.require_expected(recovery.FORMAL_CONFIG_REL))
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
                    recovery.require_record(tampered)

    def test_sensitive_key_inventory_matches_frozen_base_and_each_key_is_rejected(self) -> None:
        expected = {
            "component_id", "component_ids", "feature_matrix", "features",
            "fold_id", "fold_ids", "gold", "logit", "logits", "prediction",
            "predictions", "probability", "probabilities", "feature",
            "router_targets", "route_mask", "route_masks", "route_score",
            "route_scores", "sample_id", "sample_ids", "target", "targets",
            "raw_text", "text",
        }
        self.assertEqual(recovery.PUBLIC_SENSITIVE_KEYS, expected)
        value, after = valid_attempt2_fixture()
        with mock.patch.object(recovery, "mode_manifest", return_value=after):
            for key in sorted(expected):
                with self.subTest(key=key):
                    value["checks"][0]["detail"] = {key: "row-level"}
                    value["recovery"]["recomputation"]["mirror_b"][
                        "checks_sha256"
                    ] = recovery.canonical_digest(value["checks"])
                    with self.assertRaises(ValueError):
                        recovery.validate_attempt2_result(
                            value, verify_artifact_record=False
                        )
            value["checks"][0]["detail"] = None

    def test_bool_counts_and_nonexact_check_rows_are_rejected(self) -> None:
        value, after = valid_attempt2_fixture()
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
        with mock.patch.object(recovery, "mode_manifest", return_value=after):
            for mutate in mutations:
                with self.subTest(mutation=mutate.__code__.co_firstlineno):
                    tampered = copy.deepcopy(value)
                    mutate(tampered)
                    with self.assertRaises(ValueError):
                        recovery.validate_attempt2_result(
                            tampered, verify_artifact_record=False
                        )

    def test_final_preflight_requires_all_governance_outputs_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original_root = recovery.PROJECT_ROOT
            try:
                recovery.PROJECT_ROOT = root
                for relative in (
                    recovery.ATTEMPT2_VERIFICATION_REL,
                    recovery.ATTEMPT2_SUMMARY_REL,
                    recovery.COMPLETION_REL,
                    recovery.SELECTION_REL,
                ):
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("existing\n", encoding="utf-8")
                    with self.subTest(relative=str(relative)):
                        with self.assertRaises(FileExistsError):
                            recovery.attempt2_preflight()
                    path.unlink()
            finally:
                recovery.PROJECT_ROOT = original_root

    def test_normalizer_changes_only_synthetic_exact_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original_root = recovery.PROJECT_ROOT
            try:
                recovery.PROJECT_ROOT = root
                for relative, kind, before_mode, _after_mode in recovery.MODE_REPAIRS:
                    path = root / relative
                    if kind == "directory":
                        path.mkdir(parents=True, exist_ok=True)
                    else:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(str(relative).encode("utf-8"))
                    os.chmod(path, before_mode)
                tree = recovery.file_tree_digest(root / recovery.ROUTER_REL)
                synthetic_private = {
                    "synthetic": True,
                    "modes": [{"matches_expected": True}],
                }
                config = {
                    "public_mode_normalization": {
                        "content_tree_before": tree,
                        "pre_manifest": recovery.frozen_mode_manifest(),
                    },
                    "private_invariant": synthetic_private,
                }
                frozen_failure = {"verification": {"sha256": "a"}, "summary": {"sha256": "b"}}
                with (
                    mock.patch.object(recovery, "load_amendment_config", return_value=(root / "amendment.json", config)),
                    mock.patch.object(recovery, "private_artifact_digest", return_value=synthetic_private),
                    mock.patch.object(recovery, "failure_snapshots", return_value=frozen_failure),
                    mock.patch.object(recovery, "exact_attempt1_failure_bound", return_value=True),
                ):
                    result = recovery.normalize_public_modes()
                self.assertEqual(result["target_count"], 16)
                self.assertEqual(len(result["fd_preflight"]), 16)
                self.assertTrue(
                    all(row["link_count"] >= 1 for row in result["fd_preflight"])
                )
                self.assertTrue(all(row["matches_expected"] for row in result["before"]))
                self.assertTrue(all(row["matches_expected"] for row in result["after"]))
                self.assertEqual(result["content_tree_before"], result["content_tree_after"])
            finally:
                recovery.PROJECT_ROOT = original_root

    def test_fd_preflight_rejects_same_byte_path_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target.json"
            replacement = root / "replacement.json"
            payload = b'{"frozen":true}\n'
            target.write_bytes(payload)
            replacement.write_bytes(payload)
            os.chmod(target, 0o600)
            os.chmod(replacement, 0o600)
            descriptor = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                observed = os.fstat(descriptor)
                opened = [
                    {
                        "descriptor": descriptor,
                        "after_mode": 0o644,
                        "before_mode": 0o600,
                        "path": target,
                        "relative": "target.json",
                        "identity": (observed.st_dev, observed.st_ino),
                        "kind": "file",
                    }
                ]
                manifest = [
                    {
                        "path": "target.json",
                        "type": "file",
                        "before_mode": "0o600",
                        "after_mode": "0o644",
                        "bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                ]
                os.replace(replacement, target)
                with self.assertRaises(PermissionError):
                    recovery.verify_opened_mode_preflight(opened, manifest)
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(os.fstat(descriptor).st_mode), 0o600)
            finally:
                os.close(descriptor)

    def test_post_normalization_hardlink_is_rejected_before_mirror_a(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original_root = recovery.PROJECT_ROOT
            try:
                recovery.PROJECT_ROOT = root
                first_file = None
                for relative, kind, _before_mode, after_mode in recovery.MODE_REPAIRS:
                    path = root / relative
                    if kind == "directory":
                        path.mkdir(parents=True, exist_ok=True)
                    else:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(str(relative).encode("utf-8"))
                        first_file = first_file or path
                    os.chmod(path, after_mode)
                self.assertIsNotNone(first_file)
                os.link(first_file, root / "outside-router-hardlink")
                tree = recovery.file_tree_digest(root / recovery.ROUTER_REL)
                private = {"modes": [{"matches_expected": True}]}
                amendment = {
                    "public_mode_normalization": {"content_tree_before": tree},
                    "private_invariant": private,
                }
                with (
                    mock.patch.object(
                        recovery,
                        "load_amendment_config",
                        return_value=(root / "amendment.json", amendment),
                    ),
                    mock.patch.object(recovery, "assert_no_runner_import"),
                    mock.patch.object(
                        recovery, "require_expected", return_value=root / "synthetic"
                    ),
                    mock.patch.object(recovery, "require_canonical_runner_binding"),
                    mock.patch.object(recovery, "failure_snapshots", return_value={}),
                    mock.patch.object(
                        recovery, "private_artifact_digest", return_value=private
                    ),
                    mock.patch.object(
                        recovery, "exact_attempt1_failure_bound", return_value=True
                    ),
                ):
                    with self.assertRaises(PermissionError):
                        recovery.attempt2_preflight()
            finally:
                recovery.PROJECT_ROOT = original_root

    def test_mirror_inventory_excludes_governance_sidecars(self) -> None:
        paths = set(recovery.mirror_source_relatives())
        self.assertNotIn(recovery.ORIGINAL_VERIFICATION_REL, paths)
        self.assertNotIn(recovery.ORIGINAL_SUMMARY_REL, paths)
        self.assertNotIn(recovery.ATTEMPT2_VERIFICATION_REL, paths)
        self.assertNotIn(recovery.COMPLETION_REL, paths)
        self.assertIn(recovery.FORMAL_CONFIG_REL, paths)
        self.assertIn(recovery.CANONICAL_VERIFIER_REL, paths)

    def test_tree_digest_excludes_only_exact_router_root_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested = root / "frozen-sources/verification-attempt-2.json"
            root_sidecar = root / "verification-attempt-2.json"
            nested.parent.mkdir(parents=True)
            nested.write_text("nested-a\n", encoding="utf-8")
            root_sidecar.write_text("root-a\n", encoding="utf-8")
            before = recovery.file_tree_digest(root)
            root_sidecar.write_text("root-b\n", encoding="utf-8")
            self.assertEqual(recovery.file_tree_digest(root), before)
            nested.write_text("nested-b\n", encoding="utf-8")
            self.assertNotEqual(recovery.file_tree_digest(root), before)

    def test_attempt2_summary_is_exact_and_mode_bound(self) -> None:
        value, _after = valid_attempt2_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original_root = recovery.PROJECT_ROOT
            try:
                recovery.PROJECT_ROOT = root
                summary = root / recovery.ATTEMPT2_SUMMARY_REL
                summary.parent.mkdir(parents=True)
                summary.write_bytes(recovery.expected_summary_payload(value))
                os.chmod(summary, 0o644)
                record = recovery.require_attempt2_summary(value)
                self.assertEqual(record["path"], str(recovery.ATTEMPT2_SUMMARY_REL))
                summary.write_text("tampered\n", encoding="utf-8")
                with self.assertRaises(ValueError):
                    recovery.require_attempt2_summary(value)
            finally:
                recovery.PROJECT_ROOT = original_root

    def test_deterministic_final_failure_is_sealed_and_not_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original_root = recovery.PROJECT_ROOT
            try:
                recovery.PROJECT_ROOT = root
                router = root / recovery.ROUTER_REL
                router.mkdir(parents=True)
                previous = os.umask(0o077)
                try:
                    with (
                        mock.patch.object(recovery, "attempt2_preflight", return_value={}),
                        mock.patch.object(
                            recovery,
                            "build_attempt2_result",
                            side_effect=ValueError("private diagnostic must not be recorded"),
                        ),
                    ):
                        result = recovery.run_final()
                finally:
                    os.umask(previous)
                recovery.validate_failed_attempt2_result(result)
                verification = root / recovery.ATTEMPT2_VERIFICATION_REL
                summary = root / recovery.ATTEMPT2_SUMMARY_REL
                self.assertTrue(verification.is_file())
                self.assertTrue(summary.is_file())
                for sidecar in (verification, summary):
                    observed = os.lstat(sidecar)
                    self.assertTrue(stat.S_ISREG(observed.st_mode))
                    self.assertEqual(stat.S_IMODE(observed.st_mode), 0o644)
                    self.assertEqual(observed.st_nlink, 1)
                self.assertEqual(summary.read_bytes(), recovery.expected_summary_payload(result))
                self.assertNotIn("private diagnostic", verification.read_text(encoding="utf-8"))
                self.assertNotIn("private diagnostic", summary.read_text(encoding="utf-8"))
                with self.assertRaises(FileExistsError):
                    recovery.run_final()
            finally:
                recovery.PROJECT_ROOT = original_root

    def test_failure_summary_write_error_leaves_json_terminal_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original_root = recovery.PROJECT_ROOT
            original_create_once = recovery.create_once
            try:
                recovery.PROJECT_ROOT = root
                (root / recovery.ROUTER_REL).mkdir(parents=True)

                def fail_summary(path: Path, payload: bytes, mode: int = 0o644) -> None:
                    if path.name == recovery.ATTEMPT2_SUMMARY_REL.name:
                        raise OSError("synthetic summary write failure")
                    original_create_once(path, payload, mode)

                with (
                    mock.patch.object(recovery, "attempt2_preflight", return_value={}),
                    mock.patch.object(
                        recovery,
                        "build_attempt2_result",
                        side_effect=ValueError("synthetic deterministic failure"),
                    ),
                    mock.patch.object(recovery, "create_once", side_effect=fail_summary),
                ):
                    with self.assertRaises(OSError):
                        recovery.run_final()
                self.assertTrue(
                    (root / recovery.ATTEMPT2_VERIFICATION_REL).is_file()
                )
                self.assertFalse((root / recovery.ATTEMPT2_SUMMARY_REL).exists())
                with self.assertRaises(FileExistsError):
                    recovery.run_final()
            finally:
                recovery.PROJECT_ROOT = original_root

    def test_final_does_not_swallow_process_control_exceptions(self) -> None:
        for raised in (KeyboardInterrupt(), SystemExit(17)):
            with self.subTest(exception=type(raised).__name__):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    original_root = recovery.PROJECT_ROOT
                    try:
                        recovery.PROJECT_ROOT = root
                        (root / recovery.ROUTER_REL).mkdir(parents=True)
                        with (
                            mock.patch.object(
                                recovery, "attempt2_preflight", return_value={}
                            ),
                            mock.patch.object(
                                recovery,
                                "build_attempt2_result",
                                side_effect=raised,
                            ),
                        ):
                            with self.assertRaises(type(raised)):
                                recovery.run_final()
                        self.assertFalse(
                            (root / recovery.ATTEMPT2_VERIFICATION_REL).exists()
                        )
                        self.assertFalse((root / recovery.ATTEMPT2_SUMMARY_REL).exists())
                    finally:
                        recovery.PROJECT_ROOT = original_root

    def test_append_only_writer_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original_root = recovery.PROJECT_ROOT
            try:
                recovery.PROJECT_ROOT = root
                (root / recovery.ROUTER_REL).mkdir(parents=True)
                value = {"status": "Passed", "claim_boundary": "synthetic", "checks": []}
                previous = os.umask(0o077)
                try:
                    recovery.write_attempt2(value)
                    recovery.create_once(
                        root / recovery.COMPLETION_REL, b'{"status":"Complete"}\n'
                    )
                finally:
                    os.umask(previous)
                for relative in (
                    recovery.ATTEMPT2_VERIFICATION_REL,
                    recovery.ATTEMPT2_SUMMARY_REL,
                    recovery.COMPLETION_REL,
                ):
                    observed = os.lstat(root / relative)
                    self.assertTrue(stat.S_ISREG(observed.st_mode))
                    self.assertEqual(stat.S_IMODE(observed.st_mode), 0o644)
                    self.assertEqual(observed.st_nlink, 1)
                with self.assertRaises(FileExistsError):
                    recovery.write_attempt2(value)
            finally:
                recovery.PROJECT_ROOT = original_root

    def test_frozen_incident_artifacts_are_unchanged(self) -> None:
        for relative in recovery.EXPECTED_IMMUTABLE:
            recovery.require_expected(relative)


if __name__ == "__main__":
    unittest.main()
