from __future__ import annotations

import ast
from contextlib import ExitStack
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]
RECOVERY_PATH = MODULE_DIR / "verify_exp060_router_preflight_attempt2.py"
PROTOCOL_SOURCE = (
    MODULE_DIR.parent
    / "protocols/exp-062-exp060-router-preflight-verification-attempt-2-incident-003.md"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recovery = load_module("incident003_attempt2_under_test", RECOVERY_PATH)


def write_bytes(path: Path, payload: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    os.chmod(path, mode)


def write_json(path: Path, value: object, mode: int = 0o644) -> None:
    write_bytes(path, recovery._json_bytes(value), mode)


def record(project: Path, path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "path": str(path.relative_to(project)),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def make_paired(path: Path) -> None:
    rows = 3360
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    np.savez_compressed(
        path,
        sample_ids=np.asarray([f"s{index:030d}" for index in range(rows)], dtype="<U31"),
        component_ids=np.asarray([f"c{index:033d}" for index in range(rows)], dtype="<U34"),
        fold_ids=(np.arange(rows) % 5).astype(np.int8),
        gold=np.zeros((rows, 6), dtype=np.uint8),
        m1_logits=np.zeros((rows, 6), dtype=np.float32),
        m3_logits=np.zeros((rows, 6), dtype=np.float32),
        character_lengths=np.ones(rows, dtype=np.int32),
        m1_token_lengths=np.ones(rows, dtype=np.int32),
        m3_token_lengths=np.ones(rows, dtype=np.int32),
        m1_fold_run_sha256=np.asarray(["a" * 64] * rows, dtype="<U64"),
        m3_fold_run_sha256=np.asarray(["b" * 64] * rows, dtype="<U64"),
    )
    os.chmod(path, 0o600)


def fake_original_source(variant: str = "passed") -> bytes:
    check_names = repr(recovery.ORIGINAL_CHECK_NAMES)
    claim_keys = repr(sorted(recovery.EXECUTION_CLAIM_KEYS))
    return f'''from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
CHECK_NAMES = {check_names}
CLAIM_KEYS = {claim_keys}
VARIANT = {variant!r}

def _display(path):
    return str(Path(path).resolve().relative_to(PROJECT_ROOT.resolve()))

def _artifact(path):
    path = Path(path)
    payload = path.read_bytes()
    return {{"path": _display(path), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}}

def _create_bytes_once(path, payload, mode=0o644):
    raise AssertionError("physical canonical writer must be captured")

def _assert_replication_preflight_tree(run_dir, config, *, verified):
    expected = {{"run.json", "preflight-contract.json", "frozen-sources"}}
    if verified:
        expected |= {{"verification.json", "VERIFICATION-SUMMARY.md"}}
    if {{entry.name for entry in os.scandir(run_dir)}} != expected:
        raise ValueError("synthetic physical tree drift")
    return run_dir / "run.json", run_dir / "preflight-contract.json", run_dir / "frozen-sources"

def _run_child_test():
    return REPO_ROOT

def _summary(candidate):
    return (
        "# Seed-44 EXP-060 No-Result Preflight Verification\\n\\n"
        "- Status: `Passed`\\n"
        f"- Checks: `{{len(candidate['checks'])}}/{{len(candidate['checks'])}}`\\n"
        "- Independent verifier imported the runner: `false`\\n"
        "- Feature/target/router/metric/bootstrap computation: `false`\\n"
        "- Formal router execution remains separately authorized.\\n"
    ).encode("utf-8")

def verify_replication_preflight(config_path):
    _run_child_test()
    config_path = Path(config_path)
    config = json.loads(config_path.read_text())
    outputs = config["outputs"]
    run_dir = PROJECT_ROOT / outputs["public_attempt_dir"] / "router-preflight"
    run_path, contract_path, _ = _assert_replication_preflight_tree(run_dir, config, verified=False)
    run = json.loads(run_path.read_text())
    if VARIANT == "error":
        raise ValueError("synthetic original failure")
    if VARIANT == "baseexception":
        raise KeyboardInterrupt("synthetic control")
    rows = [{{"name": name, "passed": True, "detail": None}} for name in CHECK_NAMES]
    if VARIANT == "failed_check":
        rows[0]["passed"] = False
    formal_names = ("protocol", "runner", "verifier", "tests", "runner_launcher", "verifier_launcher", "launcher_tests")
    candidate = {{
        "schema_version": "exp-router-replication-preflight-verification-v1",
        "experiment_id": "EXP-060",
        "replication_parent_experiment_id": "EXP-062",
        "run_id": "exp-062-seed-44-router-replication",
        "attempt_id": "attempt-1",
        "model_seed": 44,
        "seed_contract": {recovery.SEED_CONTRACT!r},
        "rq_id": "RQ-S3",
        "scope": "preflight",
        "verified_at_utc": "2026-08-24T00:00:03+00:00",
        "status": "Passed",
        "passed_count": 20,
        "failed_count": 0,
        "checks": rows,
        "independent": True,
        "runner_imported": False,
        "execution_claims": {{name: False for name in CLAIM_KEYS}},
        "verified_artifacts": {{
            "config": _artifact(config_path),
            "run": _artifact(run_path),
            "contract": _artifact(contract_path),
            "input": run["input"],
            "upstreams": run["upstreams"],
            "frozen_sources": run["source_artifacts"],
            "formal_sources": {{name: run["source_artifacts"][name] for name in formal_names}},
        }},
        "resources": {{
            "wall_seconds": 1.0,
            "peak_process_rss_gb": 0.1,
            "api_cost_usd": 0,
            "gpu_cost_usd": 0,
            "model_forward_runs": 0,
        }},
        "claim_boundary": "Verified seed-44 no-result router preflight only; formal routing remains separately authorized.",
    }}
    json_payload = (json.dumps(candidate, indent=2, sort_keys=True, ensure_ascii=True) + "\\n").encode()
    verification_path = run_dir / "verification.json"
    summary_path = run_dir / "VERIFICATION-SUMMARY.md"
    first_path = summary_path if VARIANT == "wrong_path" else verification_path
    _create_bytes_once(first_path, json_payload, 0o644)
    _create_bytes_once(summary_path, _summary(candidate), 0o644)
    if VARIANT == "extra_writer":
        _create_bytes_once(run_dir / "extra.json", b"extra", 0o644)
    if VARIANT != "skip_virtual":
        _assert_replication_preflight_tree(run_dir, config, verified=True)
    if VARIANT == "stderr":
        import sys
        print("forbidden", file=sys.stderr)
    print(json.dumps({{"status": "Passed", "passed": 20, "failed": 0}}, sort_keys=True))
    return 0
'''.encode("utf-8")


class SyntheticContext:
    def __init__(self, variant: str = "passed") -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.project = self.root / "project"
        self.script = self.project / "experiments/stack-overflow-emotion-gold/oof-router"
        self.protocols = self.project / "experiments/stack-overflow-emotion-gold/protocols"
        self.configs = self.script / "configs"
        self.public_attempt = self.script / "runs" / recovery.RUN_ID / recovery.ATTEMPT_ID
        self.private_attempt = self.script / "private" / recovery.RUN_ID / recovery.ATTEMPT_ID
        self.attempt1_root = self.public_attempt / "router-preflight"
        self.attempt2_root = self.public_attempt / "router-preflight-verification-attempt-2"
        self.original_config = self.configs / "exp-062-seed-44-router-replication-router-preflight-attempt-1.json"
        self.original_run = self.attempt1_root / "run.json"
        self.original_contract = self.attempt1_root / "preflight-contract.json"
        self.frozen_dir = self.attempt1_root / "frozen-sources"
        self.original_live_verifier = self.script / "verify_exp060_router_preflight.py"
        self.original_frozen_verifier = self.frozen_dir / "verify_exp060_router_preflight.py"
        self.recovery_verifier = self.script / RECOVERY_PATH.name
        self.recovery_tests = self.script / "tests" / Path(__file__).name
        self.protocol = self.protocols / PROTOCOL_SOURCE.name
        self.incident_config = self.configs / recovery.CONFIG_NAME
        self.formal_config = self.configs / "exp-062-seed-44-router-replication-router-formal-attempt-1.json"
        self.stack = ExitStack()
        self._create_layout(variant)
        self._patch_module()
        self._create_incident_config()

    def close(self) -> None:
        self.stack.close()
        self.temporary.cleanup()

    def _mkdir(self, path: Path, mode: int) -> None:
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, mode)

    def _create_layout(self, variant: str) -> None:
        for directory, mode in (
            (self.configs, 0o755),
            (self.public_attempt, 0o755),
            (self.private_attempt, 0o700),
            (self.attempt1_root, 0o755),
            (self.frozen_dir, 0o755),
        ):
            self._mkdir(directory, mode)
        write_bytes(self.recovery_verifier, RECOVERY_PATH.read_bytes())
        write_bytes(self.recovery_tests, Path(__file__).read_bytes())
        write_bytes(self.protocol, PROTOCOL_SOURCE.read_bytes())

        paired = self.private_attempt / "paired-oof.npz"
        make_paired(paired)
        self.input_record = record(self.project, paired)
        calibration = self.public_attempt / "calibration"
        upstream_paths = {
            "oof_verification": self.public_attempt / "verification.json",
            "oof_completion": self.public_attempt / "oof-complete.json",
            "exp059_run": calibration / "run.json",
            "exp059_verification": calibration / "verification.json",
            "exp059_calibration_parameters": calibration / "calibration-parameters.json",
            "exp059_calibration_completion": self.public_attempt / "calibration-complete.json",
        }
        for name, path in upstream_paths.items():
            write_json(path, {"name": name, "status": "Passed"})
        self.upstreams = {name: record(self.project, path) for name, path in upstream_paths.items()}

        source_names = {
            "protocol": "exp-060-pre-qwen-deployable-router.md",
            "preflight_runner": "run_exp060_router_preflight.py",
            "preflight_verifier": "verify_exp060_router_preflight.py",
            "preflight_tests": "test_exp060_router_preflight.py",
            "runner": "run_exp060_router.py",
            "verifier": "verify_exp060_router.py",
            "tests": "test_exp060_router.py",
            "runner_launcher": "run_exp060_router_v3.py",
            "verifier_launcher": "verify_exp060_router_v3.py",
            "launcher_tests": "test_exp060_router_v3.py",
        }
        fake_source = fake_original_source(variant)
        live_implementation: dict[str, dict[str, object]] = {}
        for key, name in source_names.items():
            live = self.script / name
            payload = fake_source if key == "preflight_verifier" else f"# {{key}}\n".encode()
            write_bytes(live, payload)
            live_implementation[key] = record(self.project, live)
        self.original_live_verifier = self.script / source_names["preflight_verifier"]
        original_config = {
            "schema_version": "exp-router-replication-preflight-config-v1",
            "experiment_id": "EXP-060",
            "replication_parent_experiment_id": "EXP-062",
            "run_id": recovery.RUN_ID,
            "attempt_id": recovery.ATTEMPT_ID,
            "model_seed": 44,
            "seed_contract": copy.deepcopy(recovery.SEED_CONTRACT),
            "authorization": {
                "no_result_preflight": True,
                "formal_router_training": False,
                "formal_result_computation": False,
                "validation_access": False,
                "test_access": False,
                "model_loading_or_forward": False,
                "raw_text_access": False,
            },
            "implementation": live_implementation,
            "input": {"paired_oof": self.input_record},
            "prerequisites": self.upstreams,
            "outputs": {
                "public_attempt_dir": str(self.public_attempt.relative_to(self.project)),
            },
        }
        write_json(self.original_config, original_config)

        frozen_config = self.frozen_dir / "config.json"
        write_bytes(frozen_config, self.original_config.read_bytes())
        source_artifacts: dict[str, dict[str, object]] = {"config": record(self.project, frozen_config)}
        for key, name in source_names.items():
            live = self.project / live_implementation[key]["path"]
            frozen = self.frozen_dir / name
            write_bytes(frozen, live.read_bytes())
            source_artifacts[key] = record(self.project, frozen)
        self.original_frozen_verifier = self.frozen_dir / source_names["preflight_verifier"]

        check_rows = [
            {"name": name, "passed": True, "detail": None}
            for name in recovery.RUN_CHECK_NAMES
        ]
        self.contract_payload = {
            "schema_version": "exp-router-replication-preflight-contract-v1",
            "experiment_id": "EXP-060",
            "replication_parent_experiment_id": "EXP-062",
            "run_id": recovery.RUN_ID,
            "attempt_id": recovery.ATTEMPT_ID,
            "model_seed": 44,
            "seed_contract": copy.deepcopy(recovery.SEED_CONTRACT),
            "result_bearing": False,
            "input_schema": [
                {"array_name": name, **details}
                for name, details in sorted(recovery.EXPECTED_HEADER.items())
            ],
            "feature_count": 14,
            "nested_cross_fitting_required": True,
            "policies": [
                "m1_only", "m3_only", "m1_max_entropy",
                "m1_threshold_proximity", "logistic_router",
            ],
            "deployable_policy_order": [
                "m1_max_entropy", "m1_threshold_proximity", "logistic_router"
            ],
            "formal_router_training_authorized": False,
            "formal_result_computation_authorized": False,
            "validation_access": False,
            "test_access": False,
            "raw_text_access": False,
            "model_loading_or_forward": False,
        }
        write_json(self.original_contract, self.contract_payload)
        self.run_payload = {
            "schema_version": "exp-router-replication-preflight-run-v1",
            "experiment_id": "EXP-060",
            "replication_parent_experiment_id": "EXP-062",
            "run_id": recovery.RUN_ID,
            "attempt_id": recovery.ATTEMPT_ID,
            "model_seed": 44,
            "seed_contract": copy.deepcopy(recovery.SEED_CONTRACT),
            "status": "CompletedAwaitingVerification",
            "checks": check_rows,
            "check_count": 27,
            "passed_count": 27,
            "failed_count": 0,
            "resources": {
                "wall_seconds": 1.0,
                "peak_process_rss_gb": 0.1,
                "api_cost_usd": 0,
                "gpu_cost_usd": 0,
                "model_forward_runs": 0,
            },
            "execution_claims": {name: False for name in recovery.EXECUTION_CLAIM_KEYS},
            "source_artifacts": source_artifacts,
            "input": self.input_record,
            "upstreams": self.upstreams,
        }
        write_json(self.original_run, self.run_payload)
        self.source_artifacts = source_artifacts

    def _patch_module(self) -> None:
        values = {
            "PROJECT_ROOT": self.project,
            "REPO_ROOT": self.root,
            "SCRIPT_DIR": self.script,
            "CONFIGS_DIR": self.configs,
            "DEFAULT_CONFIG": self.incident_config,
            "PROTOCOL_PATH": self.protocol,
            "RECOVERY_TESTS_PATH": self.recovery_tests,
            "ORIGINAL_LIVE_VERIFIER": self.original_live_verifier,
            "ATTEMPT_PUBLIC": self.public_attempt,
            "ATTEMPT_PRIVATE": self.private_attempt,
            "ATTEMPT1_ROOT": self.attempt1_root,
            "ATTEMPT2_ROOT": self.attempt2_root,
            "ORIGINAL_CONFIG": self.original_config,
            "ORIGINAL_RUN": self.original_run,
            "ORIGINAL_CONTRACT": self.original_contract,
            "ORIGINAL_FROZEN_VERIFIER": self.original_frozen_verifier,
            "CANONICAL_VERIFICATION": self.attempt1_root / "verification.json",
            "CANONICAL_SUMMARY": self.attempt1_root / "VERIFICATION-SUMMARY.md",
            "FORMAL_CONFIG": self.formal_config,
            "FORMAL_PUBLIC": self.public_attempt / "router",
            "FORMAL_PRIVATE": self.private_attempt / "router",
            "SELECTION": self.script / "runs" / recovery.RUN_ID / "selected-attempt.json",
            "ORIGINAL_VERIFIER_BYTES": self.original_live_verifier.stat().st_size,
            "ORIGINAL_VERIFIER_SHA256": hashlib.sha256(self.original_live_verifier.read_bytes()).hexdigest(),
            "ORIGINAL_CONFIG_SHA256": hashlib.sha256(self.original_config.read_bytes()).hexdigest(),
            "ORIGINAL_RUN_SHA256": hashlib.sha256(self.original_run.read_bytes()).hexdigest(),
            "ORIGINAL_CONTRACT_SHA256": hashlib.sha256(self.original_contract.read_bytes()).hexdigest(),
        }
        for name, value in values.items():
            self.stack.enter_context(mock.patch.object(recovery, name, value))
        self.stack.enter_context(mock.patch.object(recovery, "__file__", str(self.recovery_verifier)))

    def _create_incident_config(self) -> None:
        implementation = {
            "protocol": record(self.project, self.protocol),
            "verifier": record(self.project, self.recovery_verifier),
            "tests": record(self.project, self.recovery_tests),
        }
        outputs = {
            name: str(path.relative_to(self.project))
            for name, path in recovery._output_paths().items()
        }
        config = {
            "schema_version": recovery.SCHEMA_CONFIG,
            "incident_id": "003",
            "experiment_id": "EXP-060",
            "replication_parent_experiment_id": "EXP-062",
            "run_id": recovery.RUN_ID,
            "attempt_id": recovery.ATTEMPT_ID,
            "model_seed": 44,
            "seed_contract": copy.deepcopy(recovery.SEED_CONTRACT),
            "rq_id": "RQ-S3",
            "registered_at": "2026-08-24",
            "authorization": {
                "basis": recovery.AUTHORIZATION_BASIS,
                **copy.deepcopy(recovery.AUTHORIZATION),
            },
            "predecessor": {
                "failure": {
                    "verification_attempt": 1,
                    "outcome": "TerminalFailureNoSidecars",
                    "failure_stage": "child_test_preflight",
                    "failure_code": "missing_repo_root",
                    "exception_type": "NameError",
                    "exit_code": 1,
                    "canonical_verification_absent": True,
                    "canonical_summary_absent": True,
                },
                "config": record(self.project, self.original_config),
                "run": record(self.project, self.original_run),
                "contract": record(self.project, self.original_contract),
                "frozen_verifier": record(self.project, self.original_frozen_verifier),
                "source_artifacts": copy.deepcopy(self.source_artifacts),
                "upstreams": copy.deepcopy(self.upstreams),
                "input": copy.deepcopy(self.input_record),
            },
            "implementation": implementation,
            "outputs": outputs,
            "resources": copy.deepcopy(recovery.RESOURCE_CONTRACT),
            "privacy": {
                "public_sensitive_keys": sorted(recovery.PUBLIC_SENSITIVE_KEYS),
                "private_values_loaded": False,
                "np_load_allowed": False,
            },
            "claim_boundary": recovery.CLAIM_BOUNDARY,
            "commands": {
                "verify_attempt_2": (
                    "/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python "
                    f"projects/llm-forum-text-emotion-recognition/experiments/"
                    f"stack-overflow-emotion-gold/oof-router/{self.recovery_verifier.name} --config "
                    f"projects/llm-forum-text-emotion-recognition/experiments/"
                    f"stack-overflow-emotion-gold/oof-router/configs/{recovery.CONFIG_NAME}"
                )
            },
        }
        write_json(self.incident_config, config)

    def config(self) -> dict:
        return json.loads(self.incident_config.read_text())


class Incident003Attempt2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = SyntheticContext()

    def tearDown(self) -> None:
        self.context.close()

    def reset(self, variant: str) -> None:
        self.context.close()
        self.context = SyntheticContext(variant)

    def test_happy_path_passed_separate_namespace_and_immutability(self) -> None:
        before = recovery._state_snapshot(self.context.config())
        prior = os.umask(0o077)
        try:
            value = recovery.run_attempt2(self.context.incident_config)
        finally:
            os.umask(prior)
        self.assertEqual(value["status"], "Passed")
        self.assertEqual(value["passed_count"], 16)
        self.assertFalse(value["formal_gate_authorized"])
        self.assertEqual(recovery._state_snapshot(self.context.config()), before)
        paths = recovery._output_paths()
        self.assertEqual(
            {entry.name for entry in os.scandir(paths["root"])},
            {
                "verification-attempt-2-claim.json",
                "attempt-1-failure-seal.json",
                "verification.json",
                "VERIFICATION-SUMMARY.md",
                "verification-attempt-2-terminal.json",
                "frozen-sources",
            },
        )
        for name in ("claim", "attempt1_failure", "passed", "passed_summary", "terminal"):
            metadata = os.lstat(paths[name])
            self.assertEqual(stat.S_IMODE(metadata.st_mode), 0o644)
            self.assertEqual(metadata.st_nlink, 1)
        self.assertFalse(os.path.lexists(recovery.CANONICAL_VERIFICATION))
        self.assertFalse(os.path.lexists(recovery.CANONICAL_SUMMARY))
        self.assertFalse(os.path.lexists(recovery.FORMAL_CONFIG))
        terminal = json.loads(paths["terminal"].read_text())
        self.assertEqual(terminal["status"], "Complete")
        self.assertFalse(terminal["formal_gate_authorized"])
        self.assertEqual(
            terminal["terminal_state_sha256"],
            value["physical_invariants"]["before_sha256"],
        )
        self.assertEqual(
            terminal["terminal_state_sha256"],
            value["physical_invariants"]["after_sha256"],
        )
        self.assertGreaterEqual(
            terminal["terminal_resources"]["wall_seconds"],
            value["resources"]["wall_seconds"],
        )
        self.assertGreaterEqual(
            terminal["terminal_resources"]["peak_process_rss_gb"],
            value["resources"]["peak_process_rss_gb"],
        )
        claim = json.loads(paths["claim"].read_text())
        self.assertEqual(
            claim["incident_config"]["sha256"],
            claim["expected_frozen_sources"]["config"]["sha256"],
        )

    def test_unpatched_original_reproduces_missing_repo_root(self) -> None:
        module = recovery._load_original_module(self.context.config())
        self.assertFalse(hasattr(module, "REPO_ROOT"))
        with self.assertRaises(NameError):
            module._run_child_test()

    def test_summary_oracle_is_derived_from_frozen_production_source(self) -> None:
        original_path = MODULE_DIR / "verify_exp060_router_preflight.py"
        tree = ast.parse(original_path.read_text())
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "verify_replication_preflight"
        )
        assignment = next(
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "summary" for target in node.targets)
        )
        expression = ast.fix_missing_locations(ast.Expression(assignment.value))
        expected = eval(
            compile(expression, str(original_path), "eval"),
            {"checks": SimpleNamespace(rows=[None] * 20)},
        )
        candidate = {"checks": [None] * 20}
        self.assertEqual(recovery._original_summary(candidate), expected)

    def test_rerun_is_rejected_after_passed_claim(self) -> None:
        recovery.run_attempt2(self.context.incident_config)
        with self.assertRaises(FileExistsError):
            recovery.run_attempt2(self.context.incident_config)

    def test_losing_root_claim_race_never_writes_into_winner_root(self) -> None:
        real_mkdir = os.mkdir

        def competitor_wins(path: Path, mode: int = 0o777, *args, **kwargs):
            if Path(path) == recovery.ATTEMPT2_ROOT:
                real_mkdir(path, mode)
                raise FileExistsError("synthetic competing claimant")
            return real_mkdir(path, mode, *args, **kwargs)

        with mock.patch.object(recovery.os, "mkdir", side_effect=competitor_wins), \
             self.assertRaises(FileExistsError):
            recovery.run_attempt2(self.context.incident_config)
        self.assertTrue(recovery.ATTEMPT2_ROOT.is_dir())
        self.assertEqual(list(os.scandir(recovery.ATTEMPT2_ROOT)), [])
        self.assertFalse(os.path.lexists(recovery._output_paths()["failed"]))

    def test_clean_failure_is_sealed_and_no_retry(self) -> None:
        self.reset("error")
        with self.assertRaises(recovery.Attempt2TerminalFailure) as observed:
            recovery.run_attempt2(self.context.incident_config)
        self.assertEqual(observed.exception.payload["status"], "Failed")
        self.assertEqual(
            observed.exception.payload["completed_checks"],
            list(recovery.RECOVERY_CHECK_NAMES[:6]),
        )
        paths = recovery._output_paths()
        self.assertTrue(paths["failed"].is_file())
        self.assertTrue(paths["failed_summary"].is_file())
        self.assertFalse(os.path.lexists(paths["passed"]))
        with self.assertRaises(FileExistsError):
            recovery.run_attempt2(self.context.incident_config)

    def test_candidate_tamper_wrong_path_extra_writer_and_virtual_skip_fail(self) -> None:
        for variant in ("failed_check", "wrong_path", "extra_writer", "skip_virtual", "stderr"):
            with self.subTest(variant=variant):
                self.reset(variant)
                with self.assertRaises(recovery.Attempt2TerminalFailure):
                    recovery.run_attempt2(self.context.incident_config)
                self.assertTrue(recovery._output_paths()["failed"].is_file())
                self.assertFalse(os.path.lexists(recovery.CANONICAL_VERIFICATION))

    def test_baseexception_leaves_claimed_incomplete_terminal(self) -> None:
        self.reset("baseexception")
        with self.assertRaises(KeyboardInterrupt):
            recovery.run_attempt2(self.context.incident_config)
        paths = recovery._output_paths()
        self.assertTrue(paths["root"].is_dir())
        self.assertTrue(paths["claim"].is_file())
        self.assertFalse(os.path.lexists(paths["failed"]))
        with self.assertRaises(FileExistsError):
            recovery.run_attempt2(self.context.incident_config)

    def test_baseexception_after_passed_postcheck_has_no_success_seal(self) -> None:
        real_snapshot = recovery._state_snapshot
        calls = 0

        def interrupt_terminal_snapshot(config: dict):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise KeyboardInterrupt("synthetic terminal audit interruption")
            return real_snapshot(config)

        with mock.patch.object(
            recovery, "_state_snapshot", side_effect=interrupt_terminal_snapshot
        ), self.assertRaises(KeyboardInterrupt):
            recovery.run_attempt2(self.context.incident_config)
        paths = recovery._output_paths()
        self.assertTrue(paths["passed"].is_file())
        self.assertTrue(paths["passed_summary"].is_file())
        self.assertFalse(os.path.lexists(paths["terminal"]))
        self.assertFalse(os.path.lexists(paths["failed"]))
        with self.assertRaises(FileExistsError):
            recovery.run_attempt2(self.context.incident_config)

    def test_passed_summary_failure_adds_authoritative_failure_json(self) -> None:
        real_write = recovery._create_bytes_once

        def fail_summary(path: Path, payload: bytes) -> None:
            if Path(path) == recovery._output_paths()["passed_summary"]:
                raise OSError("synthetic summary failure")
            real_write(path, payload)

        with mock.patch.object(recovery, "_create_bytes_once", side_effect=fail_summary), \
             self.assertRaises(recovery.Attempt2TerminalFailure):
            recovery.run_attempt2(self.context.incident_config)
        paths = recovery._output_paths()
        self.assertTrue(paths["passed"].is_file())
        self.assertTrue(paths["failed"].is_file())
        self.assertFalse(os.path.lexists(paths["passed_summary"]))

    def test_failure_summary_failure_leaves_authoritative_json(self) -> None:
        self.reset("error")
        real_write = recovery._create_bytes_once

        def fail_failure_summary(path: Path, payload: bytes) -> None:
            if Path(path) == recovery._output_paths()["failed_summary"]:
                raise OSError("synthetic failure summary")
            real_write(path, payload)

        with mock.patch.object(recovery, "_create_bytes_once", side_effect=fail_failure_summary), \
             self.assertRaises(recovery.Attempt2TerminalFailure):
            recovery.run_attempt2(self.context.incident_config)
        paths = recovery._output_paths()
        self.assertTrue(paths["failed"].is_file())
        self.assertFalse(os.path.lexists(paths["failed_summary"]))

    def test_failure_seal_rejects_concurrent_formal_output(self) -> None:
        self.reset("error")
        real_seal = recovery._seal_failure

        def create_formal_then_seal(*args, **kwargs):
            write_json(recovery.FORMAL_CONFIG, {"forbidden": True})
            return real_seal(*args, **kwargs)

        with mock.patch.object(recovery, "_seal_failure", side_effect=create_formal_then_seal), \
             self.assertRaisesRegex(ValueError, "Formal/downstream"):
            recovery.run_attempt2(self.context.incident_config)
        self.assertTrue(recovery._output_paths()["failed"].is_file())

    def test_partial_file_write_is_terminal_and_retry_rejected(self) -> None:
        directory = self.context.root / "partial"
        directory.mkdir(mode=0o755)
        target = directory / "terminal.json"
        real_write = os.write
        calls = 0

        def partial(descriptor: int, payload) -> int:
            nonlocal calls
            calls += 1
            if calls == 1:
                amount = max(1, len(payload) // 2)
                return real_write(descriptor, payload[:amount])
            raise OSError("synthetic partial write")

        with mock.patch.object(recovery.os, "write", side_effect=partial), \
             self.assertRaises(OSError):
            recovery._create_bytes_once(target, b"abcdef")
        self.assertTrue(os.path.lexists(target))
        with self.assertRaises(FileExistsError):
            recovery._create_bytes_once(target, b"retry")

    def test_claim_partial_failure_is_terminal(self) -> None:
        real_json = recovery._create_json_once

        def fail_failure_seal(path: Path, value: object) -> None:
            if Path(path) == recovery._output_paths()["attempt1_failure"]:
                raise OSError("synthetic claim failure")
            real_json(path, value)

        with mock.patch.object(recovery, "_create_json_once", side_effect=fail_failure_seal), \
             self.assertRaises(recovery.Attempt2TerminalFailure):
            recovery.run_attempt2(self.context.incident_config)
        self.assertTrue(recovery._output_paths()["root"].is_dir())
        self.assertTrue(recovery._output_paths()["claim"].is_file())
        self.assertTrue(recovery._output_paths()["failed"].is_file())

    def test_symlink_and_hardlink_input_fail_before_claim(self) -> None:
        config = self.context.config()
        input_path = self.context.project / config["predecessor"]["input"]["path"]
        os.link(input_path, input_path.with_name("second-link.npz"))
        with self.assertRaises((ValueError, PermissionError)):
            recovery.load_config(self.context.incident_config)
        self.assertFalse(os.path.lexists(self.context.attempt2_root))
        self.reset("passed")
        target = self.context.incident_config
        target.unlink()
        target.symlink_to(target.with_name("missing.json"))
        with self.assertRaises((ValueError, FileNotFoundError)):
            recovery.load_config(target)

    def test_private_header_uses_held_record_bytes_not_path_reopen(self) -> None:
        config = self.context.config()
        input_path, payload = recovery._require_record(
            config["predecessor"]["input"], 0o600
        )
        write_bytes(input_path, b"swapped-after-held-read", 0o600)
        self.assertEqual(recovery._npz_header(payload), recovery.EXPECTED_HEADER)

    def test_outer_resource_failure_is_terminal(self) -> None:
        with mock.patch.object(recovery, "_peak_rss_gb", return_value=3.0), \
             self.assertRaises(recovery.Attempt2TerminalFailure):
            recovery.run_attempt2(self.context.incident_config)
        self.assertTrue(recovery._output_paths()["failed"].is_file())

    def test_terminal_state_audit_detects_postcheck_mutation(self) -> None:
        for mutation in ("attempt1", "upstream", "private", "pyc"):
            with self.subTest(mutation=mutation):
                self.reset("passed")
                real_postcheck = recovery._postcheck_passed

                def mutate_after_postcheck(value: dict) -> None:
                    real_postcheck(value)
                    config = self.context.config()
                    if mutation == "attempt1":
                        os.chmod(recovery.ORIGINAL_RUN, 0o600)
                    elif mutation == "upstream":
                        upstream = next(iter(config["predecessor"]["upstreams"].values()))
                        path = recovery.PROJECT_ROOT / upstream["path"]
                        write_json(path, {"drift": True})
                    elif mutation == "private":
                        path = recovery.PROJECT_ROOT / config["predecessor"]["input"]["path"]
                        os.chmod(path, 0o400)
                    else:
                        pyc = recovery.SCRIPT_DIR / "__pycache__/terminal-drift.pyc"
                        write_bytes(pyc, b"drift")

                with mock.patch.object(
                    recovery, "_postcheck_passed", side_effect=mutate_after_postcheck
                ), self.assertRaises(recovery.Attempt2TerminalFailure) as observed:
                    recovery.run_attempt2(self.context.incident_config)
                self.assertEqual(
                    observed.exception.payload["failure_stage"], "final_state_audit"
                )
                self.assertEqual(
                    observed.exception.payload["failure_code"], "terminal_state_drift"
                )
                self.assertTrue(recovery._output_paths()["passed"].is_file())
                self.assertTrue(recovery._output_paths()["failed"].is_file())
                self.assertFalse(os.path.lexists(recovery._output_paths()["terminal"]))

    def test_terminal_resource_audit_includes_publish_and_postcheck(self) -> None:
        with mock.patch.object(
            recovery, "_peak_rss_gb", side_effect=[0.1, 3.0, 3.0]
        ), self.assertRaises(recovery.Attempt2TerminalFailure) as observed:
            recovery.run_attempt2(self.context.incident_config)
        self.assertEqual(
            observed.exception.payload["failure_stage"], "final_resource_audit"
        )
        self.assertEqual(
            observed.exception.payload["failure_code"],
            "terminal_resource_budget_exceeded",
        )
        self.assertTrue(recovery._output_paths()["passed"].is_file())
        self.assertTrue(recovery._output_paths()["failed"].is_file())
        self.assertFalse(os.path.lexists(recovery._output_paths()["terminal"]))

    def test_terminal_success_seal_write_failure_is_authoritative_failed(self) -> None:
        real_json = recovery._create_json_once

        def fail_terminal(path: Path, value: object) -> None:
            if Path(path) == recovery._output_paths()["terminal"]:
                raise OSError("synthetic terminal seal failure")
            real_json(path, value)

        with mock.patch.object(recovery, "_create_json_once", side_effect=fail_terminal), \
             self.assertRaises(recovery.Attempt2TerminalFailure) as observed:
            recovery.run_attempt2(self.context.incident_config)
        self.assertEqual(observed.exception.payload["failure_stage"], "terminal_seal")
        self.assertEqual(
            observed.exception.payload["failure_code"],
            "terminal_success_seal_failure",
        )
        paths = recovery._output_paths()
        self.assertTrue(paths["passed"].is_file())
        self.assertTrue(paths["failed"].is_file())
        self.assertFalse(os.path.lexists(paths["terminal"]))

    def test_terminal_success_postcheck_failure_is_authoritative_failed(self) -> None:
        with mock.patch.object(
            recovery,
            "_postcheck_terminal",
            side_effect=ValueError("synthetic terminal postcheck failure"),
        ), self.assertRaises(recovery.Attempt2TerminalFailure) as observed:
            recovery.run_attempt2(self.context.incident_config)
        self.assertEqual(observed.exception.payload["failure_stage"], "terminal_postcheck")
        self.assertEqual(
            observed.exception.payload["failure_code"],
            "terminal_success_postcheck_failure",
        )
        paths = recovery._output_paths()
        self.assertTrue(paths["terminal"].is_file())
        self.assertTrue(paths["failed"].is_file())

    def test_held_bytes_execute_after_live_path_swap(self) -> None:
        real_read = recovery._secure_read

        def swap_after_read(path: Path, mode: int):
            result = real_read(path, mode)
            if Path(path) == recovery.ORIGINAL_LIVE_VERIFIER:
                write_bytes(Path(path), b"raise RuntimeError('swapped')\n")
            return result

        with mock.patch.object(recovery, "_secure_read", side_effect=swap_after_read):
            module = recovery._load_original_module(self.context.config())
        self.assertTrue(hasattr(module, "verify_replication_preflight"))

    def test_secure_read_mode_race_fails(self) -> None:
        observed = os.stat(self.context.incident_config)
        bad = SimpleNamespace(
            st_dev=observed.st_dev,
            st_ino=observed.st_ino,
            st_mode=stat.S_IFREG | 0o600,
            st_nlink=1,
            st_size=observed.st_size,
            st_mtime_ns=observed.st_mtime_ns,
            st_ctime_ns=observed.st_ctime_ns,
        )
        with mock.patch.object(recovery.os, "fstat", return_value=bad), \
             self.assertRaises(ValueError):
            recovery._secure_read(self.context.incident_config, 0o644)

    def test_ast_patch_surface_no_runner_np_load_or_create_true(self) -> None:
        source = RECOVERY_PATH.read_text()
        tree = ast.parse(source)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        self.assertFalse(any("run_exp060_router" in name for name in imports))
        self.assertNotIn("np.load", source)
        self.assertNotIn("create=True", source)
        test_tree = ast.parse(Path(__file__).read_text())
        self.assertFalse(
            any(
                keyword.arg == "create"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for call in ast.walk(test_tree)
                if isinstance(call, ast.Call)
                for keyword in call.keywords
            )
        )
        claim_function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_claim_payload"
        )
        self.assertNotIn("artifact(", ast.unparse(claim_function))
        header_function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_npz_header"
        )
        self.assertIn("io.BytesIO(payload)", ast.unparse(header_function))
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "run_attempt2"
        )
        stores = {
            node.attr
            for node in ast.walk(function)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "module"
            and isinstance(node.ctx, (ast.Store, ast.Del))
        }
        self.assertEqual(
            stores,
            {"REPO_ROOT", "_create_bytes_once", "_assert_replication_preflight_tree"},
        )
        original = recovery._load_original_module(self.context.config())
        self.assertFalse(hasattr(original, "REPO_ROOT"))

    def test_config_schema_path_and_authorization_are_strict(self) -> None:
        config = self.context.config()
        config["authorization"]["verification_attempt_2"] = False
        write_json(self.context.incident_config, config)
        with self.assertRaises(PermissionError):
            recovery.load_config(self.context.incident_config)
        self.reset("passed")
        config = self.context.config()
        config["authorization"]["basis"] = "x"
        write_json(self.context.incident_config, config)
        with self.assertRaises(ValueError):
            recovery.load_config(self.context.incident_config)


if __name__ == "__main__":
    unittest.main()
