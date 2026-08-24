from __future__ import annotations

import ast
from contextlib import ExitStack
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp060_router_v4_incident003.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp060_router_v4_incident003.py"
V3_RUNNER_PATH = MODULE_DIR / "run_exp060_router_v3.py"
V3_VERIFIER_PATH = MODULE_DIR / "verify_exp060_router_v3.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load_module("exp060_router_v4_incident003_runner_tests", RUNNER_PATH)
VERIFIER = load_module("exp060_router_v4_incident003_verifier_tests", VERIFIER_PATH)
V3_RUNNER = load_module("exp060_router_v3_runner_direct_reject", V3_RUNNER_PATH)
V3_VERIFIER = load_module("exp060_router_v3_verifier_direct_reject", V3_VERIFIER_PATH)


class FutureConfigFixture:
    """A temporary config only; all governed evidence remains read-only in place."""

    def __init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.configs = self.root / "configs"
        self.configs.mkdir(mode=0o755)
        self.path = self.configs / RUNNER.FORMAL_CONFIG_NAME
        self.stack = ExitStack()
        for module in (RUNNER, VERIFIER):
            self.stack.enter_context(mock.patch.object(module, "CONFIGS_DIR", self.configs))
            # A common lexical root keeps command construction deterministic while
            # the artifact records continue to resolve against the real project.
            self.stack.enter_context(mock.patch.object(module, "REPO_ROOT", Path("/")))
        self.v3 = RUNNER._load_verified_v3()
        self.value = self._build()
        self.write()

    def close(self) -> None:
        self.stack.close()
        self.temporary.cleanup()

    @staticmethod
    def record(path: Path, mode: int = 0o644) -> dict[str, object]:
        return RUNNER._record(path, mode)

    def _build(self) -> dict:
        v3 = self.v3
        implementation_paths = {
            "protocol": RUNNER.PROTOCOL_PATH,
            "runner": RUNNER.BASE_RUNNER_PATH,
            "verifier": RUNNER.BASE_VERIFIER_PATH,
            "tests": RUNNER.BASE_TESTS_PATH,
            "runner_launcher": RUNNER.V3_LIVE_PATH,
            "verifier_launcher": RUNNER.V3_VERIFIER_PATH,
            "launcher_tests": RUNNER.V3_TESTS_PATH,
            "incident_protocol": RUNNER.INCIDENT_PROTOCOL_PATH,
            "incident_runner_launcher": RUNNER.V4_RUNNER_PATH,
            "incident_verifier_launcher": RUNNER.V4_VERIFIER_PATH,
            "incident_launcher_tests": RUNNER.V4_TESTS_PATH,
        }
        implementation = {
            name: self.record(path) for name, path in implementation_paths.items()
        }
        prerequisites = {
            "oof_verification": self.record(RUNNER.PUBLIC_ATTEMPT / "verification.json"),
            "exp059_run": self.record(RUNNER.PUBLIC_ATTEMPT / "calibration/run.json"),
            "exp059_verification": self.record(
                RUNNER.PUBLIC_ATTEMPT / "calibration/verification.json"
            ),
            "exp059_calibration_parameters": self.record(
                RUNNER.PUBLIC_ATTEMPT / "calibration/calibration-parameters.json"
            ),
            "exp060_preflight_verification": self.record(
                RUNNER.ATTEMPT2_ROOT / "verification.json"
            ),
        }
        paired = self.record(RUNNER.PRIVATE_ATTEMPT / "paired-oof.npz", 0o600)
        attempt1 = {
            "config": self.record(RUNNER.FIXED_ARTIFACTS["attempt1_config"][0]),
            "run": self.record(RUNNER.FIXED_ARTIFACTS["attempt1_run"][0]),
            "contract": self.record(RUNNER.FIXED_ARTIFACTS["attempt1_contract"][0]),
            "frozen_verifier": self.record(
                RUNNER.FIXED_ARTIFACTS["attempt1_frozen_verifier"][0]
            ),
            "failure_seal": self.record(
                RUNNER.FIXED_ARTIFACTS["attempt1_failure"][0]
            ),
        }
        frozen_sources = {
            name: self.record(RUNNER.ATTEMPT2_FROZEN / row[0])
            for name, row in RUNNER.RECOVERY_FROZEN_EXPECTED.items()
        }
        attempt2 = {
            "incident_config": self.record(RUNNER.FIXED_ARTIFACTS["incident_config"][0]),
            "claim": self.record(RUNNER.FIXED_ARTIFACTS["claim"][0]),
            "verification": self.record(
                RUNNER.FIXED_ARTIFACTS["attempt2_verification"][0]
            ),
            "summary": self.record(RUNNER.FIXED_ARTIFACTS["attempt2_summary"][0]),
            "terminal": self.record(RUNNER.FIXED_ARTIFACTS["attempt2_terminal"][0]),
            "frozen_sources": frozen_sources,
        }
        commands = {
            name: shlex.join(tokens)
            for name, tokens in RUNNER._expected_commands(
                self.path, v3.EXPECTED_RUNTIME["python_executable"]
            ).items()
        }
        config = {name: {} for name in v3.FORMAL_TOP_KEYS}
        config.update(
            {
                "schema_version": RUNNER.V4_CONFIG_SCHEMA,
                "experiment_id": v3.FORMAL_EXPERIMENT_ID,
                "run_id": RUNNER.RUN_ID,
                "attempt_id": RUNNER.ATTEMPT_ID,
                "seed_contract": copy.deepcopy(v3.SEED_CONTRACT),
                "rq_id": RUNNER.RQ_ID,
                "tier": "Major system experiment",
                "stage": v3.FORMAL_STAGE,
                "registered_at": "2026-08-24",
                "authorization": {
                    "basis": RUNNER.FORMAL_AUTHORIZATION_BASIS,
                    "model_seed": 44,
                    "formal_router_training": True,
                    "formal_result_computation": True,
                    "validation_access": False,
                    "test_access": False,
                    "model_loading_or_forward": False,
                    "raw_text_access": False,
                },
                "provenance": copy.deepcopy(v3.EXPECTED_PROVENANCE),
                "path_bases": copy.deepcopy(v3.EXPECTED_PATH_BASES),
                "artifact_contract": copy.deepcopy(v3.FORMAL_ARTIFACT_CONTRACT),
                "runtime": copy.deepcopy(v3.EXPECTED_RUNTIME),
                "implementation": implementation,
                "prerequisites": prerequisites,
                "input": {"paired_oof": paired},
                "outputs": copy.deepcopy(v3._expected_outputs()),
                "data": copy.deepcopy(v3.EXPECTED_DATA),
                "cross_fitting": copy.deepcopy(v3.EXPECTED_CROSS_FITTING),
                "thresholds": copy.deepcopy(v3.EXPECTED_THRESHOLDS),
                "target_contract": copy.deepcopy(v3.EXPECTED_TARGET_CONTRACT),
                "feature_contract": copy.deepcopy(v3.EXPECTED_FEATURE_CONTRACT),
                "router": copy.deepcopy(v3.EXPECTED_ROUTER),
                "call_rates": copy.deepcopy(v3.EXPECTED_CALL_RATES),
                "gate": copy.deepcopy(v3.EXPECTED_GATE),
                "risk_coverage": copy.deepcopy(v3.EXPECTED_RISK_COVERAGE),
                "bootstrap": copy.deepcopy(v3.EXPECTED_BOOTSTRAP),
                "resources": copy.deepcopy(v3.FORMAL_RESOURCE_CONTRACT),
                "claim_boundary": v3.FORMAL_CLAIM_BOUNDARY,
                "commands": commands,
                "preflight_recovery": {
                    "incident_id": "003",
                    "attempt_1": attempt1,
                    "attempt_2": attempt2,
                    "canonical_attempt_1_sidecars_absent": True,
                    "formal_gate_authorized": False,
                },
            }
        )
        return config

    def write(self) -> None:
        self.path.write_text(
            json.dumps(self.value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        self.path.chmod(0o644)

    def mutate(self, callback) -> None:
        callback(self.value)
        self.write()


class FakeV3:
    def __init__(
        self,
        raises: BaseException | None = None,
        result: dict[str, object] | None = None,
    ) -> None:
        self.FORMAL_CONFIG_SCHEMA = "exp-router-replication-config-v3"
        self.validate_launch_contract = self.original_validator
        self.raises = raises
        self.result = result
        self.calls = 0

    @staticmethod
    def original_validator(_path):
        raise AssertionError("original validator should be patched")

    def execute(self, path, operation):
        self.calls += 1
        if self.FORMAL_CONFIG_SCHEMA != RUNNER.V4_CONFIG_SCHEMA:
            raise AssertionError("schema was not patched")
        self.validate_launch_contract(path)
        self.validate_launch_contract(path)
        if self.raises is not None:
            raise self.raises
        if self.result is not None:
            return self.result
        if operation == "run":
            return {"status": "CompletedAwaitingVerification"}
        if operation == "complete":
            return {"status": "Complete"}
        return {
            "status": "Passed",
            "passed_count": 1,
            "failed_count": 0,
            "checks": [{"name": "synthetic", "passed": True, "detail": None}],
        }


class Exp060RouterV4Incident003Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = FutureConfigFixture()

    def tearDown(self) -> None:
        self.fixture.close()

    def test_live_recovery_contract_passes_both_independent_adapters(self) -> None:
        runner_path, runner_config = RUNNER.validate_launch_contract(
            self.fixture.path, RUNNER._load_verified_v3()
        )
        verifier_path, verifier_config = VERIFIER.validate_launch_contract(
            self.fixture.path, VERIFIER._load_verified_v3()
        )
        self.assertEqual(runner_path, self.fixture.path)
        self.assertEqual(verifier_path, self.fixture.path)
        self.assertEqual(runner_config, verifier_config)
        self.assertEqual(len(runner_config["implementation"]), 11)
        self.assertEqual(len(runner_config["prerequisites"]), 5)

    def test_direct_v3_launchers_reject_v4_config(self) -> None:
        for module in (V3_RUNNER, V3_VERIFIER):
            with (
                mock.patch.object(module, "CONFIGS_DIR", self.fixture.configs),
                mock.patch.object(module, "FORMAL_CONFIG_NAME", self.fixture.path.name),
            ):
                with self.assertRaisesRegex(ValueError, "top-level schema drift"):
                    module.validate_launch_contract(self.fixture.path)

    def test_v3_live_and_attempt1_frozen_bytes_are_exact(self) -> None:
        runner = RUNNER._load_verified_v3()
        verifier = VERIFIER._load_verified_v3()
        self.assertEqual(runner.FORMAL_CONFIG_SCHEMA, RUNNER.V3_CONFIG_SCHEMA)
        self.assertEqual(verifier.FORMAL_CONFIG_SCHEMA, VERIFIER.V3_CONFIG_SCHEMA)

    def test_v3_loader_rejects_byte_path_and_link_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            live = root / "live.py"
            frozen = root / "frozen.py"
            shutil.copyfile(RUNNER.V3_LIVE_PATH, live)
            shutil.copyfile(RUNNER.V3_FROZEN_PATH, frozen)
            live.chmod(0o644)
            frozen.chmod(0o644)
            frozen.write_bytes(frozen.read_bytes() + b"\n")
            with (
                mock.patch.object(RUNNER, "V3_LIVE_PATH", live),
                mock.patch.object(RUNNER, "V3_FROZEN_PATH", frozen),
            ):
                with self.assertRaises(ValueError):
                    RUNNER._load_verified_v3()
            frozen.write_bytes(live.read_bytes())
            os.link(frozen, root / "hardlink.py")
            with (
                mock.patch.object(RUNNER, "V3_LIVE_PATH", live),
                mock.patch.object(RUNNER, "V3_FROZEN_PATH", frozen),
            ):
                with self.assertRaises(PermissionError):
                    RUNNER._load_verified_v3()

    def test_v3_loader_rejects_mode_symlink_and_held_inode_swap(self) -> None:
        for module in (RUNNER, VERIFIER):
            source = module.V3_LIVE_PATH
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                live = root / "live.py"
                frozen = root / "frozen.py"
                shutil.copyfile(source, live)
                shutil.copyfile(source, frozen)
                live.chmod(0o600)
                frozen.chmod(0o644)
                with (
                    mock.patch.object(module, "V3_LIVE_PATH", live),
                    mock.patch.object(module, "V3_FROZEN_PATH", frozen),
                ):
                    with self.assertRaises(PermissionError):
                        module._load_verified_v3()

            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                target = root / "target"
                target.mkdir()
                live = target / "live.py"
                frozen = target / "frozen.py"
                shutil.copyfile(source, live)
                shutil.copyfile(source, frozen)
                live.chmod(0o644)
                frozen.chmod(0o644)
                link = root / "linked"
                os.symlink(target, link)
                with (
                    mock.patch.object(module, "V3_LIVE_PATH", link / "live.py"),
                    mock.patch.object(module, "V3_FROZEN_PATH", frozen),
                ):
                    with self.assertRaises(ValueError):
                        module._load_verified_v3()

            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                live = root / "live.py"
                frozen = root / "frozen.py"
                replacement = root / "replacement.py"
                for path in (live, frozen, replacement):
                    shutil.copyfile(source, path)
                    path.chmod(0o644)
                real_read = module._read_descriptor
                calls = 0

                def swapping_read(descriptor):
                    nonlocal calls
                    payload = real_read(descriptor)
                    calls += 1
                    if calls == 1:
                        os.replace(replacement, live)
                    return payload

                with (
                    mock.patch.object(module, "V3_LIVE_PATH", live),
                    mock.patch.object(module, "V3_FROZEN_PATH", frozen),
                    mock.patch.object(
                        module, "_read_descriptor", side_effect=swapping_read
                    ),
                ):
                    with self.assertRaisesRegex(ValueError, "changed while held"):
                        module._load_verified_v3()

    def test_exact_two_patch_and_exact_once_call_success(self) -> None:
        for module, operation in ((RUNNER, "run"), (VERIFIER, "final")):
            fake = FakeV3()
            original = fake.validate_launch_contract
            with (
                mock.patch.object(module, "_load_verified_v3", return_value=fake),
                mock.patch.object(
                    module,
                    "validate_launch_contract",
                    return_value=(self.fixture.path, self.fixture.value),
                ),
                mock.patch.object(module, "_immutable_snapshot", return_value={"stable": True}),
                mock.patch.object(module, "_stage_state"),
                mock.patch.object(module, "_governance_precheck"),
                mock.patch.object(module, "_claim_scope", return_value=self.fixture.path),
                mock.patch.object(module, "_seal_scope_success"),
                mock.patch.object(module, "_seal_scope_failure"),
                mock.patch.object(module, "_governance_manifest_through"),
                mock.patch.object(module, "_validate_completed_stage"),
                mock.patch.object(module, "_peak_rss_gb", return_value=0.1),
            ):
                result = module.execute(self.fixture.path, operation)
            self.assertEqual(result["status"], module._expected_result_status(operation))
            self.assertEqual(fake.calls, 1)
            self.assertEqual(fake.FORMAL_CONFIG_SCHEMA, "exp-router-replication-config-v3")
            self.assertIs(fake.validate_launch_contract, original)

    def test_baseexception_restores_both_patches_and_stops(self) -> None:
        for module, operation in ((RUNNER, "run"), (VERIFIER, "final")):
            fake = FakeV3(KeyboardInterrupt())
            original = fake.validate_launch_contract
            with (
                mock.patch.object(module, "_load_verified_v3", return_value=fake),
                mock.patch.object(
                    module,
                    "validate_launch_contract",
                    return_value=(self.fixture.path, self.fixture.value),
                ),
                mock.patch.object(module, "_immutable_snapshot", return_value={}),
                mock.patch.object(module, "_stage_state"),
                mock.patch.object(module, "_governance_precheck"),
                mock.patch.object(module, "_claim_scope", return_value=self.fixture.path),
                mock.patch.object(module, "_seal_scope_failure"),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    module.execute(self.fixture.path, operation)
            self.assertEqual(fake.calls, 1)
            self.assertEqual(fake.FORMAL_CONFIG_SCHEMA, "exp-router-replication-config-v3")
            self.assertIs(fake.validate_launch_contract, original)

    def test_outer_budget_failure_is_terminal_nonzero(self) -> None:
        fake = FakeV3()
        with (
            mock.patch.object(RUNNER, "_load_verified_v3", return_value=fake),
            mock.patch.object(
                RUNNER,
                "validate_launch_contract",
                return_value=(self.fixture.path, self.fixture.value),
            ),
            mock.patch.object(RUNNER, "_immutable_snapshot", return_value={}),
            mock.patch.object(RUNNER, "_stage_state"),
            mock.patch.object(RUNNER, "_governance_precheck"),
            mock.patch.object(RUNNER, "_claim_scope", return_value=self.fixture.path),
            mock.patch.object(RUNNER, "_seal_scope_success"),
            mock.patch.object(RUNNER, "_seal_scope_failure"),
            mock.patch.object(RUNNER, "_validate_completed_stage"),
            mock.patch.object(RUNNER.time, "monotonic", side_effect=[0.0, 1800.1]),
            mock.patch.object(RUNNER, "_peak_rss_gb", return_value=0.1),
        ):
            with self.assertRaisesRegex(RuntimeError, "outer runner budget exceeded"):
                RUNNER.execute(self.fixture.path, "run")
        self.assertEqual(fake.calls, 1)

    def test_exact_schema_identity_authorization_and_typed_numbers(self) -> None:
        mutations = (
            lambda value: value.update(extra=True),
            lambda value: value.__setitem__("schema_version", "wrong"),
            lambda value: value.__setitem__("run_id", "wrong"),
            lambda value: value["authorization"].__setitem__("model_seed", 44.0),
            lambda value: value["authorization"].__setitem__("model_seed", True),
            lambda value: value["authorization"].__setitem__("basis", "x"),
            lambda value: value["resources"].__setitem__("peak_memory_gb", float("nan")),
            lambda value: value["router"].__setitem__("policies", value["router"]["policies"][:3]),
            lambda value: value["router"].__setitem__("deployable_policy_order", value["router"]["deployable_policy_order"][:2]),
        )
        original = copy.deepcopy(self.fixture.value)
        for mutation in mutations:
            self.fixture.value = copy.deepcopy(original)
            mutation(self.fixture.value)
            self.fixture.write()
            for module in (RUNNER, VERIFIER):
                with self.assertRaises((ValueError, PermissionError)):
                    module.validate_launch_contract(self.fixture.path, module._load_verified_v3())

    def test_exact11_exact5_paths_commands_and_privacy(self) -> None:
        mutations = (
            lambda value: value["implementation"].pop("incident_launcher_tests"),
            lambda value: value["prerequisites"].__setitem__("sixth", value["prerequisites"]["oof_verification"]),
            lambda value: value["commands"].__setitem__("run", value["commands"]["run"] + " --extra"),
            lambda value: value["preflight_recovery"].__setitem__("formal_gate_authorized", True),
            lambda value: value["preflight_recovery"].__setitem__("sample_ids", []),
        )
        original = copy.deepcopy(self.fixture.value)
        for mutation in mutations:
            self.fixture.value = copy.deepcopy(original)
            mutation(self.fixture.value)
            self.fixture.write()
            for module in (RUNNER, VERIFIER):
                with self.assertRaises((ValueError, PermissionError)):
                    module.validate_launch_contract(self.fixture.path, module._load_verified_v3())

    def test_recovery_terminal_failure_and_canonical_absence_tamper(self) -> None:
        original = copy.deepcopy(self.fixture.value)
        mutations = (
            lambda value: value["preflight_recovery"]["attempt_2"].pop("terminal"),
            lambda value: value["preflight_recovery"]["attempt_1"]["failure_seal"].__setitem__("sha256", "0" * 64),
            lambda value: value["prerequisites"].__setitem__(
                "exp060_preflight_verification",
                value["preflight_recovery"]["attempt_2"]["terminal"],
            ),
        )
        for mutation in mutations:
            self.fixture.value = copy.deepcopy(original)
            mutation(self.fixture.value)
            self.fixture.write()
            for module in (RUNNER, VERIFIER):
                with self.assertRaises((ValueError, PermissionError)):
                    module.validate_launch_contract(self.fixture.path, module._load_verified_v3())
        self.fixture.value = original
        self.fixture.write()
        for module in (RUNNER, VERIFIER):
            for forbidden in (
                module.CANONICAL_ATTEMPT1_VERIFICATION,
                module.ATTEMPT2_ROOT / "attempt-2-failure.json",
            ):
                real_lexists = os.path.lexists

                def fake_lexists(path, *, forbidden=forbidden):
                    return Path(path) == forbidden or real_lexists(path)

                with mock.patch.object(module.os.path, "lexists", side_effect=fake_lexists):
                    with self.assertRaises(FileExistsError):
                        module.validate_launch_contract(
                            self.fixture.path, module._load_verified_v3()
                        )

    def test_nested_passed_and_terminal_semantics_are_recomputed(self) -> None:
        for module in (RUNNER, VERIFIER):
            real_fixed = module._fixed_record if module is RUNNER else module._fixed
            patch_name = "_fixed_record" if module is RUNNER else "_fixed"
            cases = (
                (
                    "attempt1_failure",
                    lambda value: value.__setitem__("schema_version", "wrong"),
                ),
                (
                    "attempt2_terminal",
                    lambda value: value.__setitem__("status", "Wrong"),
                ),
                (
                    "attempt2_terminal",
                    lambda value: value.__setitem__("schema_version", "wrong"),
                ),
                (
                    "attempt2_terminal",
                    lambda value: value.__setitem__("terminal_state_sha256", "0" * 64),
                ),
                (
                    "attempt2_verification",
                    lambda value: value["checks"].__setitem__(0, value["checks"][1]),
                ),
                (
                    "attempt2_verification",
                    lambda value: value.__setitem__("schema_version", "wrong"),
                ),
                (
                    "attempt2_verification",
                    lambda value: value["resources"].__setitem__("wall_seconds", float("nan")),
                ),
                (
                    "attempt2_verification",
                    lambda value: value["captured_candidate"].__setitem__(
                        "summary_sha256", "0" * 64
                    ),
                ),
                (
                    "claim",
                    lambda value: value.__setitem__("formal_gate_authorized", True),
                ),
            )
            for target, mutate in cases:
                def tampered(name, *, target=target, mutate=mutate, real_fixed=real_fixed):
                    record, payload = real_fixed(name)
                    if name == target:
                        value = json.loads(payload)
                        mutate(value)
                        payload = (
                            json.dumps(value, indent=2, sort_keys=True) + "\n"
                        ).encode()
                    return record, payload

                with mock.patch.object(module, patch_name, side_effect=tampered):
                    with self.assertRaises(ValueError):
                        module.validate_launch_contract(
                            self.fixture.path, module._load_verified_v3()
                        )

    def test_recovery_terminal_state_digest_is_independently_recomputed(self) -> None:
        for module in (RUNNER, VERIFIER):
            with mock.patch.object(
                module,
                "_recovery_terminal_state_snapshot",
                return_value={"attempt1_root": "synthetic-drift"},
            ):
                with self.assertRaisesRegex(ValueError, "terminal state no longer reproduces"):
                    module.validate_launch_contract(
                        self.fixture.path, module._load_verified_v3()
                    )

    def test_adapter_accepts_only_claimed_symmetric_formal_transition(self) -> None:
        for module in (RUNNER, VERIFIER):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                public_attempt = root / "public-attempt"
                private_attempt = root / "private-attempt"
                governance = public_attempt / "router-formal-consumer-v4"
                public_attempt.mkdir(mode=0o755)
                private_attempt.mkdir(mode=0o700)
                real_record = module._record

                def record(path, mode=0o644):
                    candidate = Path(path)
                    if candidate == self.fixture.path or candidate.is_relative_to(root):
                        payload = candidate.read_bytes()
                        return {
                            "path": str(candidate.resolve()),
                            "bytes": len(payload),
                            "sha256": hashlib.sha256(payload).hexdigest(),
                        }
                    return real_record(candidate, mode)

                snapshot = mock.Mock(
                    wraps=module._recovery_terminal_state_snapshot
                )
                with (
                    mock.patch.object(module, "PUBLIC_ATTEMPT", public_attempt),
                    mock.patch.object(module, "PRIVATE_ATTEMPT", private_attempt),
                    mock.patch.object(module, "GOVERNANCE_DIR", governance),
                    mock.patch.object(module, "CONFIGS_DIR", self.fixture.configs),
                    mock.patch.object(module, "_record", side_effect=record),
                    mock.patch.object(
                        module, "_recovery_terminal_state_snapshot", snapshot
                    ),
                ):
                    module._validate_recovery_terminal_phase(
                        self.fixture.value, json.loads(
                            module.FIXED_ARTIFACTS["incident_config"][0].read_text()
                        )
                    )
                    module._claim_scope("run", self.fixture.path, self.fixture.value)
                    module._validate_recovery_terminal_phase(
                        self.fixture.value, json.loads(
                            module.FIXED_ARTIFACTS["incident_config"][0].read_text()
                        )
                    )
                    (public_attempt / "router").mkdir(mode=0o755)
                    (private_attempt / "router").mkdir(mode=0o700)
                    module._validate_recovery_terminal_phase(
                        self.fixture.value, json.loads(
                            module.FIXED_ARTIFACTS["incident_config"][0].read_text()
                        )
                    )
                    self.assertEqual(snapshot.call_count, 2)

    def test_failed_verifier_result_is_nonzero_and_failure_sealed(self) -> None:
        fake = FakeV3(
            result={
                "status": "Failed",
                "passed_count": 0,
                "failed_count": 1,
                "checks": [{"name": "synthetic", "passed": False, "detail": None}],
            }
        )
        failure = mock.Mock()
        success = mock.Mock()
        with (
            mock.patch.object(VERIFIER, "_load_verified_v3", return_value=fake),
            mock.patch.object(
                VERIFIER,
                "validate_launch_contract",
                return_value=(self.fixture.path, self.fixture.value),
            ),
            mock.patch.object(VERIFIER, "_immutable_snapshot", return_value={}),
            mock.patch.object(VERIFIER, "_stage_state"),
            mock.patch.object(VERIFIER, "_governance_precheck"),
            mock.patch.object(
                VERIFIER, "_claim_scope", return_value=self.fixture.path
            ),
            mock.patch.object(VERIFIER, "_seal_scope_success", success),
            mock.patch.object(VERIFIER, "_seal_scope_failure", failure),
        ):
            with self.assertRaisesRegex(RuntimeError, "non-success status"):
                VERIFIER.execute(self.fixture.path, "final")
        self.assertEqual(fake.calls, 1)
        failure.assert_called_once()
        success.assert_not_called()
        with (
            mock.patch.object(
                VERIFIER,
                "parse_args",
                return_value=SimpleNamespace(config=self.fixture.path, scope="final"),
            ),
            mock.patch.object(VERIFIER, "execute", return_value={"status": "Failed"}),
        ):
            with self.assertRaises(SystemExit) as stopped:
                VERIFIER.main()
        self.assertEqual(stopped.exception.code, 1)

    def test_post_state_exception_restores_patch_and_seals_failure(self) -> None:
        for module, operation in ((RUNNER, "run"), (VERIFIER, "final")):
            fake = FakeV3()
            original = fake.validate_launch_contract
            failure = mock.Mock()
            with (
                mock.patch.object(module, "_load_verified_v3", return_value=fake),
                mock.patch.object(
                    module,
                    "validate_launch_contract",
                    return_value=(self.fixture.path, self.fixture.value),
                ),
                mock.patch.object(
                    module,
                    "_immutable_snapshot",
                    side_effect=[{"state": "before"}, {"state": "after"}],
                ),
                mock.patch.object(module, "_stage_state"),
                mock.patch.object(module, "_governance_precheck"),
                mock.patch.object(
                    module, "_claim_scope", return_value=self.fixture.path
                ),
                mock.patch.object(module, "_seal_scope_failure", failure),
            ):
                with self.assertRaisesRegex(RuntimeError, "Immutable Incident"):
                    module.execute(self.fixture.path, operation)
            self.assertEqual(fake.calls, 1)
            self.assertEqual(fake.FORMAL_CONFIG_SCHEMA, "exp-router-replication-config-v3")
            self.assertIs(fake.validate_launch_contract, original)
            failure.assert_called_once()

    def test_terminal_postaudit_failure_appends_failure_after_complete(self) -> None:
        for module, operation in ((RUNNER, "run"), (VERIFIER, "final")):
            fake = FakeV3()
            events: list[str] = []

            def success(*_args, **_kwargs):
                events.append("complete")

            def failure(*_args, **_kwargs):
                events.append("failed")

            with (
                mock.patch.object(module, "_load_verified_v3", return_value=fake),
                mock.patch.object(
                    module,
                    "validate_launch_contract",
                    return_value=(self.fixture.path, self.fixture.value),
                ),
                mock.patch.object(module, "_immutable_snapshot", return_value={"stable": True}),
                mock.patch.object(module, "_stage_state"),
                mock.patch.object(module, "_governance_precheck"),
                mock.patch.object(
                    module, "_claim_scope", return_value=self.fixture.path
                ),
                mock.patch.object(module, "_seal_scope_success", side_effect=success),
                mock.patch.object(module, "_seal_scope_failure", side_effect=failure),
                mock.patch.object(module, "_governance_manifest_through"),
                mock.patch.object(
                    module,
                    "_validate_completed_stage",
                    side_effect=RuntimeError("synthetic terminal audit failure"),
                ),
                mock.patch.object(module, "_peak_rss_gb", return_value=0.1),
            ):
                with self.assertRaisesRegex(RuntimeError, "terminal audit failure"):
                    module.execute(self.fixture.path, operation)
            self.assertEqual(events, ["complete", "failed"])

    def test_durable_stage_seals_gate_retry_and_next_scope(self) -> None:
        for module in (RUNNER, VERIFIER):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                root.chmod(0o755)
                governance = root / "governance"
                config_path = root / "config.json"
                config_path.write_text("{}\n")
                config_path.chmod(0o644)
                config = {"claim_boundary": self.fixture.value["claim_boundary"]}

                def record(path, mode=0o644):
                    payload = Path(path).read_bytes()
                    return {
                        "path": str(Path(path).resolve()),
                        "bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }

                with (
                    mock.patch.object(module, "GOVERNANCE_DIR", governance),
                    mock.patch.object(module, "_record", side_effect=record),
                    mock.patch.object(module, "_immutable_snapshot", return_value={"immutable": True}),
                ):
                    module._governance_precheck("run", config_path, config)
                    claim = module._claim_scope("run", config_path, config)
                    stable = {"immutable": True}
                    resources = {
                        "wall_seconds": 0.1,
                        "peak_process_rss_gb": 0.1,
                        "api_cost_usd": 0,
                        "gpu_cost_usd": 0,
                        "model_forward_runs": 0,
                    }
                    module._seal_scope_success(
                        "run", config_path, config, claim, stable, stable, resources
                    )
                    module._validate_completed_stage("run", config_path, config)
                    module._governance_precheck("final", config_path, config)
                    with self.assertRaises(FileExistsError):
                        module._governance_precheck("run", config_path, config)
                    terminal_path = module._stage_path("run", "terminal")
                    terminal = json.loads(terminal_path.read_text())
                    terminal["immutable_before_sha256"] = "f" * 64
                    terminal["immutable_after_sha256"] = "f" * 64
                    terminal_path.write_text(
                        json.dumps(terminal, indent=2, sort_keys=True) + "\n"
                    )
                    terminal_path.chmod(0o644)
                    with self.assertRaises(ValueError):
                        module._governance_precheck("final", config_path, config)

            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                root.chmod(0o755)
                governance = root / "governance"
                config_path = root / "config.json"
                config_path.write_text("{}\n")
                config_path.chmod(0o644)
                config = {"claim_boundary": self.fixture.value["claim_boundary"]}

                def record_failure(path, mode=0o644):
                    payload = Path(path).read_bytes()
                    return {
                        "path": str(Path(path).resolve()),
                        "bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }

                with (
                    mock.patch.object(module, "GOVERNANCE_DIR", governance),
                    mock.patch.object(module, "_record", side_effect=record_failure),
                    mock.patch.object(module, "_immutable_snapshot", return_value={"immutable": True}),
                ):
                    module._governance_precheck("run", config_path, config)
                    claim = module._claim_scope("run", config_path, config)
                    module._seal_scope_failure(
                        "run", claim, RuntimeError("synthetic"), time.monotonic()
                    )
                    self.assertTrue(module._stage_path("run", "failure").exists())
                    with self.assertRaises((ValueError, PermissionError)):
                        module._governance_precheck("final", config_path, config)

            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                root.chmod(0o755)
                governance = root / "governance"
                config_path = root / "config.json"
                config_path.write_text("{}\n")
                config_path.chmod(0o644)
                config = {"claim_boundary": self.fixture.value["claim_boundary"]}

                def coexist_record(path, mode=0o644):
                    payload = Path(path).read_bytes()
                    return {
                        "path": str(Path(path).resolve()),
                        "bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }

                with (
                    mock.patch.object(module, "GOVERNANCE_DIR", governance),
                    mock.patch.object(module, "_record", side_effect=coexist_record),
                    mock.patch.object(
                        module, "_immutable_snapshot", return_value={"immutable": True}
                    ),
                ):
                    claim = module._claim_scope("run", config_path, config)
                    stable = {"immutable": True}
                    resources = {
                        "wall_seconds": 0.1,
                        "peak_process_rss_gb": 0.1,
                        "api_cost_usd": 0,
                        "gpu_cost_usd": 0,
                        "model_forward_runs": 0,
                    }
                    module._seal_scope_success(
                        "run", config_path, config, claim, stable, stable, resources
                    )
                    module._seal_scope_failure(
                        "run", claim, RuntimeError("post-audit"), time.monotonic()
                    )
                    self.assertTrue(module._stage_path("run", "terminal").exists())
                    self.assertTrue(module._stage_path("run", "failure").exists())
                    with self.assertRaises((ValueError, PermissionError)):
                        module._governance_precheck("final", config_path, config)

    def test_root_only_partial_claim_is_terminal_incomplete(self) -> None:
        for module in (RUNNER, VERIFIER):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                root.chmod(0o755)
                governance = root / "governance"
                config_path = root / "config.json"
                config_path.write_text("{}\n")
                config_path.chmod(0o644)
                config = {"claim_boundary": self.fixture.value["claim_boundary"]}
                with (
                    mock.patch.object(module, "GOVERNANCE_DIR", governance),
                    mock.patch.object(
                        module,
                        "_record",
                        return_value={"path": "synthetic", "bytes": 3, "sha256": "0" * 64},
                    ),
                    mock.patch.object(
                        module,
                        "_create_json_once",
                        side_effect=OSError("synthetic claim write failure"),
                    ),
                ):
                    with self.assertRaises(OSError):
                        module._claim_scope("run", config_path, config)
                    self.assertTrue(governance.is_dir())
                    with self.assertRaises(FileExistsError):
                        module._governance_precheck("run", config_path, config)

    def test_governance_writer_is_no_clobber_0644_under_umask077(self) -> None:
        for module in (RUNNER, VERIFIER):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                root.chmod(0o755)
                governance = root / "governance"
                with mock.patch.object(module, "GOVERNANCE_DIR", governance):
                    previous = os.umask(0o077)
                    try:
                        module._create_directory_once(governance)
                        target = governance / "seal.json"
                        module._create_json_once(target, {"status": "synthetic"})
                    finally:
                        os.umask(previous)
                    metadata = os.lstat(target)
                    self.assertTrue(stat.S_ISREG(metadata.st_mode))
                    self.assertEqual(metadata.st_nlink, 1)
                    self.assertEqual(stat.S_IMODE(metadata.st_mode), 0o644)
                    with self.assertRaises(FileExistsError):
                        module._create_json_once(target, {"status": "overwrite"})
                    os.link(target, governance / "hardlink.json")
                    with self.assertRaises(PermissionError):
                        module._secure_read(target, 0o644)

    def test_immutable_snapshot_detects_metadata_or_content_change(self) -> None:
        before = RUNNER._immutable_snapshot(self.fixture.path, self.fixture.value)
        self.fixture.path.chmod(0o600)
        with self.assertRaises(PermissionError):
            RUNNER._immutable_snapshot(self.fixture.path, self.fixture.value)
        self.fixture.path.chmod(0o644)
        after = RUNNER._immutable_snapshot(self.fixture.path, self.fixture.value)
        self.assertNotEqual(before, after)

    def test_stage_transition_allowlists_are_exact(self) -> None:
        run_before = (False, False, False, False, False, False)
        final_before = (True, True, False, False, False, False)
        completion = (True, True, True, True, True, False)
        for module, operation, before, expected in (
            (RUNNER, "run", True, run_before),
            (VERIFIER, "final", True, final_before),
            (VERIFIER, "completion", True, completion),
        ):
            with mock.patch.object(module.os.path, "lexists", side_effect=list(expected)):
                self.assertEqual(module._stage_state(operation, before=before), expected)

    def test_source_ast_has_exact_patch_surface_and_governance_only_writes(self) -> None:
        for path in (RUNNER_PATH, VERIFIER_PATH):
            source = path.read_text()
            tree = ast.parse(source)
            calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
            self.assertFalse(
                any(
                    isinstance(call.func, ast.Attribute)
                    and call.func.attr == "load"
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id in {"np", "numpy"}
                    for call in calls
                )
            )
            execute_functions = [
                node for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "execute"
            ]
            self.assertEqual(len(execute_functions), 1)
            execute_calls = [
                call for call in ast.walk(execute_functions[0])
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "v3"
                and call.func.attr == "execute"
            ]
            self.assertEqual(len(execute_calls), 1)
            patched_attrs = {
                target.attr
                for node in ast.walk(execute_functions[0])
                if isinstance(node, ast.Assign)
                for target in node.targets
                if isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "v3"
            }
            self.assertEqual(
                patched_attrs, {"FORMAL_CONFIG_SCHEMA", "validate_launch_contract"}
            )
            write_primitives = {"write", "mkdir", "fchmod", "fsync"}
            for function in (
                node for node in tree.body if isinstance(node, ast.FunctionDef)
            ):
                writes = [
                    call
                    for call in ast.walk(function)
                    if isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "os"
                    and call.func.attr in write_primitives
                ]
                if function.name not in {"_create_directory_once", "_create_json_once"}:
                    self.assertEqual(writes, [], function.name)
        verifier_tree = ast.parse(VERIFIER_PATH.read_text())
        imported = {
            alias.name
            for node in ast.walk(verifier_tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module or ""
            for node in ast.walk(verifier_tree)
            if isinstance(node, ast.ImportFrom)
        }
        self.assertFalse(any("run_exp060_router" in name for name in imported))

    def test_production_config_and_formal_outputs_remain_absent(self) -> None:
        for module in (RUNNER, VERIFIER):
            production_config = MODULE_DIR / "configs" / module.FORMAL_CONFIG_NAME
            self.assertFalse(os.path.lexists(production_config))
            self.assertFalse(os.path.lexists(module.PUBLIC_ATTEMPT / "router"))
            self.assertFalse(os.path.lexists(module.PRIVATE_ATTEMPT / "router"))
            self.assertFalse(os.path.lexists(module.SELECTION_PATH))
            self.assertFalse(
                os.path.lexists(
                    MODULE_DIR
                    / "runs"
                    / module.RUN_ID
                    / module.ATTEMPT_ID
                    / "router-formal-consumer-v4"
                )
            )

    def test_restrictive_umask_and_exact4_source_modes_do_not_change_validation(self) -> None:
        protocol = MODULE_DIR.parent / (
            "protocols/exp-062-exp060-router-formal-consumer-incident-003.md"
        )
        for path in (protocol, RUNNER_PATH, VERIFIER_PATH, Path(__file__)):
            metadata = os.lstat(path)
            self.assertTrue(stat.S_ISREG(metadata.st_mode))
            self.assertEqual(metadata.st_nlink, 1)
            self.assertEqual(stat.S_IMODE(metadata.st_mode), 0o644)
        previous = os.umask(0o077)
        try:
            for module in (RUNNER, VERIFIER):
                module.validate_launch_contract(
                    self.fixture.path, module._load_verified_v3()
                )
        finally:
            os.umask(previous)


if __name__ == "__main__":
    unittest.main()
