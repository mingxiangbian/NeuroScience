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
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_LAUNCHER_PATH = MODULE_DIR / "run_exp060_router_v3.py"
VERIFIER_LAUNCHER_PATH = MODULE_DIR / "verify_exp060_router_v3.py"
BASE_RUNNER_PATH = MODULE_DIR / "run_exp060_router.py"
BASE_VERIFIER_PATH = MODULE_DIR / "verify_exp060_router.py"
BASE_TESTS_PATH = MODULE_DIR / "tests/test_exp060_router.py"
PROTOCOL_PATH = MODULE_DIR.parent / "protocols/exp-060-pre-qwen-deployable-router.md"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load_module("exp060_router_v3_runner_tests", RUNNER_LAUNCHER_PATH)
VERIFIER = load_module("exp060_router_v3_verifier_tests", VERIFIER_LAUNCHER_PATH)


def write_bytes(path: Path, payload: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    path.chmod(mode)


def write_json(path: Path, value: object, mode: int = 0o644) -> None:
    write_bytes(
        path,
        (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode(),
        mode,
    )


class SyntheticContract:
    def __init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.project = self.root / "project"
        self.script = (
            self.project
            / "experiments/stack-overflow-emotion-gold/oof-router"
        )
        self.configs = self.script / "configs"
        self.formal_config_path = (
            self.configs
            / "exp-062-seed-44-router-replication-router-formal-attempt-1.json"
        )
        self.stack = ExitStack()
        self._create_layout()
        self._patch_launchers()
        self._build_contract()

    def close(self) -> None:
        self.stack.close()
        self.temporary.cleanup()

    def _mkdir(self, path: Path, mode: int) -> None:
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(mode)

    def _copy(self, source: Path, target: Path) -> None:
        write_bytes(target, source.read_bytes(), 0o644)

    def _create_layout(self) -> None:
        self._mkdir(self.configs, 0o755)
        protocol = (
            self.project
            / "experiments/stack-overflow-emotion-gold/protocols/exp-060-pre-qwen-deployable-router.md"
        )
        sources = {
            protocol: PROTOCOL_PATH,
            self.script / "run_exp060_router.py": BASE_RUNNER_PATH,
            self.script / "verify_exp060_router.py": BASE_VERIFIER_PATH,
            self.script / "tests/test_exp060_router.py": BASE_TESTS_PATH,
            self.script / "run_exp060_router_v3.py": RUNNER_LAUNCHER_PATH,
            self.script / "verify_exp060_router_v3.py": VERIFIER_LAUNCHER_PATH,
            self.script / "tests/test_exp060_router_v3.py": Path(__file__),
            self.script / "run_exp060_router_preflight.py": MODULE_DIR / "run_exp060_router_preflight.py",
            self.script / "verify_exp060_router_preflight.py": MODULE_DIR / "verify_exp060_router_preflight.py",
            self.script / "tests/test_exp060_router_preflight.py": MODULE_DIR / "tests/test_exp060_router_preflight.py",
        }
        for target, source in sources.items():
            self._copy(source, target)

    def _patch_launchers(self) -> None:
        common = {
            "PROJECT_ROOT": self.project,
            "REPO_ROOT": self.root,
            "SCRIPT_DIR": self.script,
            "CONFIGS_DIR": self.configs,
            "BASE_RUNNER_PATH": self.script / "run_exp060_router.py",
            "BASE_VERIFIER_PATH": self.script / "verify_exp060_router.py",
            "BASE_TESTS_PATH": self.script / "tests/test_exp060_router.py",
            "VERIFIER_LAUNCHER_PATH": self.script / "verify_exp060_router_v3.py",
            "LAUNCHER_TESTS_PATH": self.script / "tests/test_exp060_router_v3.py",
            "PROTOCOL_PATH": (
                self.project
                / "experiments/stack-overflow-emotion-gold/protocols/exp-060-pre-qwen-deployable-router.md"
            ),
        }
        for module in (RUNNER, VERIFIER):
            for name, value in common.items():
                self.stack.enter_context(mock.patch.object(module, name, value))
        self.stack.enter_context(
            mock.patch.object(
                VERIFIER,
                "RUNNER_LAUNCHER_PATH",
                self.script / "run_exp060_router_v3.py",
            )
        )
        self.stack.enter_context(
            mock.patch.object(RUNNER, "__file__", str(self.script / "run_exp060_router_v3.py"))
        )
        self.stack.enter_context(
            mock.patch.object(VERIFIER, "__file__", str(self.script / "verify_exp060_router_v3.py"))
        )

    def record(self, path: Path) -> dict[str, object]:
        payload = path.read_bytes()
        return {
            "path": str(path.relative_to(self.project)),
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }

    def _identity(self, experiment_id: str, *, parent: str | None = None) -> dict[str, object]:
        value: dict[str, object] = {
            "experiment_id": experiment_id,
            "run_id": RUNNER.RUN_ID,
            "attempt_id": RUNNER.ATTEMPT_ID,
            "model_seed": RUNNER.MODEL_SEED,
            "seed_contract": copy.deepcopy(RUNNER.SEED_CONTRACT),
        }
        if parent is not None:
            value["replication_parent_experiment_id"] = parent
        return value

    def _write_upstreams(self, paired: dict[str, object], public_attempt: Path) -> dict[str, dict[str, object]]:
        calibration = public_attempt / "calibration"
        values = {
            "oof_verification": {
                **self._identity("EXP-062"),
                "status": "Passed",
                "failed_count": 0,
                "verified_artifacts": {"paired_oof_private": paired},
            },
            "oof_completion": {**self._identity("EXP-062"), "status": "Complete"},
            "exp059_run": {
                **self._identity("EXP-059", parent="EXP-062"),
                "status": "CompletedAwaitingVerification",
            },
            "exp059_verification": {
                **self._identity("EXP-059", parent="EXP-062"),
                "status": "Passed",
                "failed_count": 0,
            },
            "exp059_calibration_parameters": {
                **self._identity("EXP-059", parent="EXP-062"),
                "router_replication_calibration": copy.deepcopy(RUNNER.REPLICATION_CALIBRATION),
            },
            "exp059_calibration_completion": {
                **self._identity("EXP-059", parent="EXP-062"),
                "status": "Complete",
            },
        }
        paths = {
            "oof_verification": public_attempt / "verification.json",
            "oof_completion": public_attempt / "oof-complete.json",
            "exp059_run": calibration / "run.json",
            "exp059_verification": calibration / "verification.json",
            "exp059_calibration_parameters": calibration / "calibration-parameters.json",
            "exp059_calibration_completion": public_attempt / "calibration-complete.json",
        }
        for name, path in paths.items():
            write_json(path, values[name])
        return {name: self.record(path) for name, path in paths.items()}

    def _build_contract(self) -> None:
        outputs = RUNNER._expected_outputs()
        self.outputs = outputs
        public_attempt = self.project / outputs["public_attempt_dir"]
        private_attempt = self.project / outputs["private_attempt_dir"]
        self._mkdir(public_attempt, 0o755)
        self._mkdir(private_attempt, 0o700)
        paired_path = private_attempt / "paired-oof.npz"
        write_bytes(paired_path, b"header-only-synthetic-npz", 0o600)
        paired = self.record(paired_path)
        upstreams = self._write_upstreams(paired, public_attempt)

        formal_paths = {
            "protocol": self.project / "experiments/stack-overflow-emotion-gold/protocols/exp-060-pre-qwen-deployable-router.md",
            "runner": self.script / "run_exp060_router.py",
            "verifier": self.script / "verify_exp060_router.py",
            "tests": self.script / "tests/test_exp060_router.py",
            "runner_launcher": self.script / "run_exp060_router_v3.py",
            "verifier_launcher": self.script / "verify_exp060_router_v3.py",
            "launcher_tests": self.script / "tests/test_exp060_router_v3.py",
        }
        formal_implementation = {name: self.record(path) for name, path in formal_paths.items()}
        preflight_paths = {
            "protocol": formal_paths["protocol"],
            "preflight_runner": self.script / "run_exp060_router_preflight.py",
            "preflight_verifier": self.script / "verify_exp060_router_preflight.py",
            "preflight_tests": self.script / "tests/test_exp060_router_preflight.py",
            **{name: path for name, path in formal_paths.items() if name != "protocol"},
        }
        preflight_implementation = {
            name: self.record(path) for name, path in preflight_paths.items()
        }
        preflight = {
            "schema_version": RUNNER.PREFLIGHT_CONFIG_SCHEMA,
            "experiment_id": "EXP-060",
            "replication_parent_experiment_id": "EXP-062",
            "run_id": RUNNER.RUN_ID,
            "attempt_id": RUNNER.ATTEMPT_ID,
            "model_seed": 44,
            "seed_contract": copy.deepcopy(RUNNER.SEED_CONTRACT),
            "rq_id": RUNNER.RQ_ID,
            "tier": "Major infrastructure preflight",
            "stage": RUNNER.PREFLIGHT_STAGE,
            "registered_at": "2026-08-24",
            "authorization": {
                "basis": "synthetic",
                "model_seed": 44,
                "no_result_preflight": True,
                "formal_router_training": False,
                "formal_result_computation": False,
                "validation_access": False,
                "test_access": False,
                "model_loading_or_forward": False,
                "raw_text_access": False,
            },
            "provenance": copy.deepcopy(RUNNER.EXPECTED_PROVENANCE),
            "path_bases": copy.deepcopy(RUNNER.EXPECTED_PATH_BASES),
            "artifact_contract": copy.deepcopy(RUNNER.PREFLIGHT_ARTIFACT_CONTRACT),
            "runtime": copy.deepcopy(RUNNER.EXPECTED_RUNTIME),
            "implementation": preflight_implementation,
            "prerequisites": upstreams,
            "input": {"paired_oof": paired},
            "outputs": outputs,
            "data": copy.deepcopy(RUNNER.EXPECTED_DATA),
            "cross_fitting": copy.deepcopy(RUNNER.EXPECTED_CROSS_FITTING),
            "thresholds": copy.deepcopy(RUNNER.EXPECTED_THRESHOLDS),
            "target_contract": copy.deepcopy(RUNNER.EXPECTED_TARGET_CONTRACT),
            "feature_contract": copy.deepcopy(RUNNER.EXPECTED_FEATURE_CONTRACT),
            "router": copy.deepcopy(RUNNER.EXPECTED_ROUTER),
            "call_rates": copy.deepcopy(RUNNER.EXPECTED_CALL_RATES),
            "gate": copy.deepcopy(RUNNER.EXPECTED_GATE),
            "risk_coverage": copy.deepcopy(RUNNER.EXPECTED_RISK_COVERAGE),
            "bootstrap": copy.deepcopy(RUNNER.EXPECTED_BOOTSTRAP),
            "resources": copy.deepcopy(RUNNER.PREFLIGHT_RESOURCE_CONTRACT),
            "claim_boundary": RUNNER.PREFLIGHT_CLAIM_BOUNDARY,
            "commands": {},
        }
        preflight_config_path = (
            self.configs
            / "exp-062-seed-44-router-replication-router-preflight-attempt-1.json"
        )
        self.preflight_config_path = preflight_config_path
        write_json(preflight_config_path, preflight)

        preflight_dir = public_attempt / "router-preflight"
        self.preflight_dir = preflight_dir
        frozen_dir = preflight_dir / "frozen-sources"
        self._mkdir(frozen_dir, 0o755)
        frozen_paths: dict[str, Path] = {"config": frozen_dir / "config.json"}
        self.preflight_frozen_config_path = frozen_paths["config"]
        self._copy(preflight_config_path, frozen_paths["config"])
        for name, source in preflight_paths.items():
            target = frozen_dir / source.name
            self._copy(source, target)
            frozen_paths[name] = target
        frozen_sources = {name: self.record(path) for name, path in frozen_paths.items()}

        identity = {
            "experiment_id": "EXP-060",
            "replication_parent_experiment_id": "EXP-062",
            "run_id": RUNNER.RUN_ID,
            "attempt_id": RUNNER.ATTEMPT_ID,
            "model_seed": 44,
            "seed_contract": copy.deepcopy(RUNNER.SEED_CONTRACT),
            "rq_id": RUNNER.RQ_ID,
            "stage": RUNNER.PREFLIGHT_STAGE,
        }
        contract = {
            "schema_version": RUNNER.PREFLIGHT_CONTRACT_SCHEMA,
            **identity,
            "result_bearing": False,
            "data_scope": "DATA-SO-TASK-V1 train-OOF header and frozen public records only",
            "input_schema": [
                {"array_name": name, **details}
                for name, details in sorted(RUNNER.EXPECTED_INPUT_SCHEMA.items())
            ],
            "ordered_model_features": copy.deepcopy(
                RUNNER.EXPECTED_FEATURE_CONTRACT["ordered_features"]
            ),
            "feature_count": 14,
            "prohibited_runtime_feature_classes": [
                "m3_", "gold", "oracle", "sample_id", "component_id", "fold_id",
                "raw_text", "validation", "test",
            ],
            "nested_cross_fitting_required": True,
            "router_replication_calibration": copy.deepcopy(RUNNER.REPLICATION_CALIBRATION),
            "policies": list(RUNNER.POLICIES),
            "deployable_policy_order": list(RUNNER.DEPLOYABLE_POLICIES),
            "formal_router_training_authorized": False,
            "formal_result_computation_authorized": False,
            "validation_access": False,
            "test_access": False,
            "raw_text_access": False,
            "model_loading_or_forward": False,
            "resource_contract": copy.deepcopy(preflight["resources"]),
            "claim_boundary": RUNNER.PREFLIGHT_CLAIM_BOUNDARY,
        }
        contract_path = preflight_dir / "preflight-contract.json"
        self.preflight_contract_path = contract_path
        write_json(contract_path, contract)
        run_checks = [
            {"name": name, "passed": True, "detail": None}
            for name in RUNNER.PREFLIGHT_RUN_CHECK_NAMES
        ]
        verification_checks = [
            {"name": name, "passed": True, "detail": None}
            for name in RUNNER.PREFLIGHT_VERIFICATION_CHECK_NAMES
        ]
        runtime_resources = {
            "wall_seconds": 0.01,
            "peak_process_rss_gb": 0.01,
            "api_cost_usd": 0,
            "gpu_cost_usd": 0,
            "model_forward_runs": 0,
        }
        claims = {name: False for name in RUNNER.EXECUTION_CLAIMS}
        run = {
            "schema_version": RUNNER.PREFLIGHT_RUN_SCHEMA,
            **identity,
            "tier": "Major infrastructure preflight",
            "status": "CompletedAwaitingVerification",
            "started_at_utc": "2026-08-24T00:00:00+00:00",
            "completed_at_utc": "2026-08-24T00:00:01+00:00",
            "config": self.record(preflight_config_path),
            "upstreams": upstreams,
            "input": paired,
            "source_artifacts": frozen_sources,
            "contract": self.record(contract_path),
            "check_count": len(run_checks),
            "passed_count": len(run_checks),
            "failed_count": 0,
            "checks": run_checks,
            "resources": runtime_resources,
            "execution_claims": claims,
            "claim_boundary": RUNNER.PREFLIGHT_CLAIM_BOUNDARY,
        }
        run_path = preflight_dir / "run.json"
        self.preflight_run_path = run_path
        write_json(run_path, run)
        formal_sources = {
            name: frozen_sources[name] for name in RUNNER.FORMAL_IMPLEMENTATION_KEYS
        }
        verification = {
            "schema_version": RUNNER.PREFLIGHT_VERIFICATION_SCHEMA,
            "experiment_id": "EXP-060",
            "replication_parent_experiment_id": "EXP-062",
            "run_id": RUNNER.RUN_ID,
            "attempt_id": RUNNER.ATTEMPT_ID,
            "model_seed": 44,
            "seed_contract": copy.deepcopy(RUNNER.SEED_CONTRACT),
            "rq_id": RUNNER.RQ_ID,
            "scope": "preflight",
            "verified_at_utc": "2026-08-24T00:00:02+00:00",
            "status": "Passed",
            "passed_count": len(verification_checks),
            "failed_count": 0,
            "checks": verification_checks,
            "independent": True,
            "runner_imported": False,
            "execution_claims": claims,
            "verified_artifacts": {
                "config": self.record(preflight_config_path),
                "run": self.record(run_path),
                "contract": self.record(contract_path),
                "input": paired,
                "upstreams": upstreams,
                "frozen_sources": frozen_sources,
                "formal_sources": formal_sources,
            },
            "resources": runtime_resources,
            "claim_boundary": (
                "Verified seed-44 no-result router preflight only; "
                "formal routing remains separately authorized."
            ),
        }
        verification_path = preflight_dir / "verification.json"
        write_json(verification_path, verification)
        write_bytes(preflight_dir / "VERIFICATION-SUMMARY.md", b"synthetic passed\n", 0o644)
        self.preflight_verification_path = verification_path

        python_executable = RUNNER.EXPECTED_RUNTIME["python_executable"]
        config_argument = str(self.formal_config_path.relative_to(self.root))
        runner_argument = str((self.script / "run_exp060_router_v3.py").relative_to(self.root))
        verifier_argument = str((self.script / "verify_exp060_router_v3.py").relative_to(self.root))
        commands = {
            "run": " ".join(
                [python_executable, runner_argument, "--config", config_argument, "--stage", "run"]
            ),
            "verify_final": " ".join(
                [python_executable, verifier_argument, "--config", config_argument, "--scope", "final"]
            ),
            "complete": " ".join(
                [python_executable, runner_argument, "--config", config_argument, "--stage", "complete"]
            ),
            "verify_completion": " ".join(
                [
                    python_executable, verifier_argument, "--config", config_argument,
                    "--scope", "completion",
                ]
            ),
        }
        formal = {key: {} for key in RUNNER.FORMAL_TOP_KEYS}
        formal.update(
            {
                "schema_version": RUNNER.FORMAL_CONFIG_SCHEMA,
                "experiment_id": "EXP-062",
                "run_id": RUNNER.RUN_ID,
                "attempt_id": RUNNER.ATTEMPT_ID,
                "seed_contract": copy.deepcopy(RUNNER.SEED_CONTRACT),
                "rq_id": RUNNER.RQ_ID,
                "tier": "Major system experiment",
                "stage": RUNNER.FORMAL_STAGE,
                "registered_at": "2026-08-24",
                "authorization": {
                    "basis": "synthetic",
                    "model_seed": 44,
                    "formal_router_training": True,
                    "formal_result_computation": True,
                    "validation_access": False,
                    "test_access": False,
                    "model_loading_or_forward": False,
                    "raw_text_access": False,
                },
                "provenance": copy.deepcopy(RUNNER.EXPECTED_PROVENANCE),
                "path_bases": copy.deepcopy(RUNNER.EXPECTED_PATH_BASES),
                "artifact_contract": copy.deepcopy(RUNNER.FORMAL_ARTIFACT_CONTRACT),
                "runtime": copy.deepcopy(RUNNER.EXPECTED_RUNTIME),
                "implementation": formal_implementation,
                "prerequisites": {
                    "oof_verification": upstreams["oof_verification"],
                    "exp059_run": upstreams["exp059_run"],
                    "exp059_verification": upstreams["exp059_verification"],
                    "exp059_calibration_parameters": upstreams["exp059_calibration_parameters"],
                    "exp060_preflight_verification": self.record(verification_path),
                },
                "input": {"paired_oof": paired},
                "outputs": outputs,
                "data": copy.deepcopy(RUNNER.EXPECTED_DATA),
                "cross_fitting": copy.deepcopy(RUNNER.EXPECTED_CROSS_FITTING),
                "thresholds": copy.deepcopy(RUNNER.EXPECTED_THRESHOLDS),
                "target_contract": copy.deepcopy(RUNNER.EXPECTED_TARGET_CONTRACT),
                "feature_contract": copy.deepcopy(RUNNER.EXPECTED_FEATURE_CONTRACT),
                "router": copy.deepcopy(RUNNER.EXPECTED_ROUTER),
                "call_rates": copy.deepcopy(RUNNER.EXPECTED_CALL_RATES),
                "gate": copy.deepcopy(RUNNER.EXPECTED_GATE),
                "risk_coverage": copy.deepcopy(RUNNER.EXPECTED_RISK_COVERAGE),
                "bootstrap": copy.deepcopy(RUNNER.EXPECTED_BOOTSTRAP),
                "resources": copy.deepcopy(RUNNER.FORMAL_RESOURCE_CONTRACT),
                "claim_boundary": RUNNER.FORMAL_CLAIM_BOUNDARY,
                "commands": commands,
            }
        )
        write_json(self.formal_config_path, formal)

    def read_formal(self) -> dict:
        return json.loads(self.formal_config_path.read_text())

    def write_formal(self, value: dict) -> None:
        write_json(self.formal_config_path, value)

    def mutate_preflight_verification(self, mutate) -> None:
        value = json.loads(self.preflight_verification_path.read_text())
        mutate(value)
        write_json(self.preflight_verification_path, value)
        formal = self.read_formal()
        formal["prerequisites"]["exp060_preflight_verification"] = self.record(
            self.preflight_verification_path
        )
        self.write_formal(formal)

    def _refresh_formal_preflight_record(self) -> None:
        formal = self.read_formal()
        formal["prerequisites"]["exp060_preflight_verification"] = self.record(
            self.preflight_verification_path
        )
        self.write_formal(formal)

    def mutate_preflight_run(self, mutate) -> None:
        run = json.loads(self.preflight_run_path.read_text())
        mutate(run)
        write_json(self.preflight_run_path, run)
        verification = json.loads(self.preflight_verification_path.read_text())
        verification["verified_artifacts"]["run"] = self.record(self.preflight_run_path)
        write_json(self.preflight_verification_path, verification)
        self._refresh_formal_preflight_record()

    def mutate_preflight_contract(self, mutate) -> None:
        contract = json.loads(self.preflight_contract_path.read_text())
        mutate(contract)
        write_json(self.preflight_contract_path, contract)
        run = json.loads(self.preflight_run_path.read_text())
        run["contract"] = self.record(self.preflight_contract_path)
        write_json(self.preflight_run_path, run)
        verification = json.loads(self.preflight_verification_path.read_text())
        verification["verified_artifacts"]["contract"] = self.record(
            self.preflight_contract_path
        )
        verification["verified_artifacts"]["run"] = self.record(self.preflight_run_path)
        write_json(self.preflight_verification_path, verification)
        self._refresh_formal_preflight_record()

    def mutate_preflight_config(self, mutate) -> None:
        preflight = json.loads(self.preflight_config_path.read_text())
        mutate(preflight)
        write_json(self.preflight_config_path, preflight)
        write_bytes(
            self.preflight_frozen_config_path,
            self.preflight_config_path.read_bytes(),
            0o644,
        )
        run = json.loads(self.preflight_run_path.read_text())
        run["config"] = self.record(self.preflight_config_path)
        run["source_artifacts"]["config"] = self.record(
            self.preflight_frozen_config_path
        )
        write_json(self.preflight_run_path, run)
        verification = json.loads(self.preflight_verification_path.read_text())
        verification["verified_artifacts"]["config"] = self.record(
            self.preflight_config_path
        )
        verification["verified_artifacts"]["run"] = self.record(
            self.preflight_run_path
        )
        verification["verified_artifacts"]["frozen_sources"]["config"] = self.record(
            self.preflight_frozen_config_path
        )
        write_json(self.preflight_verification_path, verification)
        self._refresh_formal_preflight_record()

    def create_router_tree(self) -> None:
        config = self.read_formal()
        public = self.project / self.outputs["public_attempt_dir"] / "router"
        private = self.project / self.outputs["private_attempt_dir"] / "router"
        public.mkdir(mode=0o755)
        private.mkdir(mode=0o700)
        for name in RUNNER.PUBLIC_ROOT_NAMES - {"frozen-sources"}:
            (public / name).write_text("synthetic\n")
        frozen = public / "frozen-sources"
        frozen.mkdir(mode=0o755)
        (frozen / "config.json").write_bytes(self.formal_config_path.read_bytes())
        for record in config["implementation"].values():
            source = self.project / record["path"]
            (frozen / source.name).write_bytes(source.read_bytes())
        write_bytes(private / "router-oof.npz", b"private-synthetic", 0o600)


class FakeRunner:
    def __init__(self, contract: SyntheticContract) -> None:
        self.contract = contract
        self.REPLICATION_CONFIG_SCHEMA = "exp-router-replication-config-v2"
        self.REPLICATION_REQUIRED_PREREQUISITES = {"old"}
        self.load_calls = 0
        self.run_calls = 0
        self.complete_calls = 0

    def load_config(self, path: Path) -> dict:
        self.load_calls += 1
        return json.loads(path.read_text())

    def formal_run(self, _path: Path, _config: dict) -> dict:
        self.run_calls += 1
        self.contract.create_router_tree()
        return {"status": "CompletedAwaitingVerification"}

    def complete_router_attempt(self, _path: Path, _config: dict) -> dict:
        self.complete_calls += 1
        raise AssertionError("not expected")


class FakeVerifier:
    def __init__(self, contract: SyntheticContract) -> None:
        self.contract = contract
        self.REPLICATION_CONFIG_SCHEMA = "exp-router-replication-config-v2"
        self.REPLICATION_REQUIRED_PREREQUISITES = {"old"}
        self.atomic_json = object()
        self.write_summary = object()
        self.verify_calls = 0
        self.completion_calls = 0

    def verify(self, _path: Path) -> dict:
        self.verify_calls += 1
        result = {
            "experiment_id": "EXP-062",
            "status": "Passed",
            "passed_count": 1,
            "failed_count": 0,
            "checks": [{"name": "synthetic", "passed": True, "detail": None}],
            "claim_boundary": "synthetic",
        }
        run_dir = self.contract.project / self.contract.outputs["public_attempt_dir"] / "router"
        self.atomic_json(run_dir / "verification.json", result)
        self.write_summary(run_dir / "VERIFICATION-SUMMARY.md", result)
        return result

    def verify_completion(self, _path: Path) -> dict:
        self.completion_calls += 1
        return {"status": "Passed", "passed_count": 1, "failed_count": 0}


class Exp060RouterV3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = SyntheticContract()

    def tearDown(self) -> None:
        self.contract.close()

    def test_deep_contract_passes_in_both_independent_launchers(self) -> None:
        runner_path, runner_config = RUNNER.validate_launch_contract(
            self.contract.formal_config_path
        )
        verifier_path, verifier_config = VERIFIER.validate_launch_contract(
            self.contract.formal_config_path
        )
        self.assertEqual(runner_path, verifier_path)
        self.assertEqual(runner_config, verifier_config)

    def test_runner_calls_frozen_base_once_and_enforces_umask_modes(self) -> None:
        fake = FakeRunner(self.contract)
        original_schema = fake.REPLICATION_CONFIG_SCHEMA
        original_prerequisites = fake.REPLICATION_REQUIRED_PREREQUISITES
        prior = os.umask(0o077)
        try:
            result = RUNNER.execute(
                self.contract.formal_config_path, "run", base_module=fake
            )
            observed = os.umask(0o077)
            self.assertEqual(observed, 0o077)
        finally:
            os.umask(prior)
        self.assertEqual(result["status"], "CompletedAwaitingVerification")
        self.assertEqual((fake.load_calls, fake.run_calls, fake.complete_calls), (1, 1, 0))
        self.assertEqual(fake.REPLICATION_CONFIG_SCHEMA, original_schema)
        self.assertIs(fake.REPLICATION_REQUIRED_PREREQUISITES, original_prerequisites)

    def test_verifier_calls_once_writes_0644_and_restores_overrides(self) -> None:
        runner = FakeRunner(self.contract)
        RUNNER.execute(self.contract.formal_config_path, "run", base_module=runner)
        fake = FakeVerifier(self.contract)
        originals = (
            fake.REPLICATION_CONFIG_SCHEMA,
            fake.REPLICATION_REQUIRED_PREREQUISITES,
            fake.atomic_json,
            fake.write_summary,
        )
        prior = os.umask(0o077)
        try:
            result = VERIFIER.execute(
                self.contract.formal_config_path, "final", base_module=fake
            )
        finally:
            os.umask(prior)
        self.assertEqual(result["status"], "Passed")
        self.assertEqual((fake.verify_calls, fake.completion_calls), (1, 0))
        self.assertEqual(fake.REPLICATION_CONFIG_SCHEMA, originals[0])
        self.assertIs(fake.REPLICATION_REQUIRED_PREREQUISITES, originals[1])
        self.assertIs(fake.atomic_json, originals[2])
        self.assertIs(fake.write_summary, originals[3])
        run_dir = self.contract.project / self.contract.outputs["public_attempt_dir"] / "router"
        for name in ("verification.json", "VERIFICATION-SUMMARY.md"):
            metadata = os.lstat(run_dir / name)
            self.assertEqual(stat.S_IMODE(metadata.st_mode), 0o644)
            self.assertEqual(metadata.st_nlink, 1)

    def test_completion_branches_each_call_frozen_base_once(self) -> None:
        RUNNER.execute(
            self.contract.formal_config_path, "run", base_module=FakeRunner(self.contract)
        )
        run_dir = (
            self.contract.project
            / self.contract.outputs["public_attempt_dir"]
            / "router"
        )
        write_bytes(run_dir / "verification.json", b"{}\n", 0o644)
        write_bytes(run_dir / "VERIFICATION-SUMMARY.md", b"Passed\n", 0o644)
        complete_base = FakeRunner(self.contract)

        def complete(_path: Path, _config: dict) -> dict:
            complete_base.complete_calls += 1
            write_bytes(run_dir / "router-complete.json", b"{}\n", 0o644)
            return {"status": "Complete"}

        complete_base.complete_router_attempt = complete
        complete_base.formal_run = lambda *_args: (_ for _ in ()).throw(
            AssertionError("run branch not expected")
        )
        result = RUNNER.execute(
            self.contract.formal_config_path, "complete", base_module=complete_base
        )
        self.assertEqual(result["status"], "Complete")
        self.assertEqual((complete_base.load_calls, complete_base.complete_calls), (1, 1))
        verifier = FakeVerifier(self.contract)
        completion_result = VERIFIER.execute(
            self.contract.formal_config_path, "completion", base_module=verifier
        )
        self.assertEqual(completion_result["status"], "Passed")
        self.assertEqual((verifier.verify_calls, verifier.completion_calls), (0, 1))

    def test_runner_restores_globals_and_umask_after_baseexception(self) -> None:
        fake = FakeRunner(self.contract)
        original_schema = fake.REPLICATION_CONFIG_SCHEMA
        original_prerequisites = fake.REPLICATION_REQUIRED_PREREQUISITES

        def explode(_path: Path) -> dict:
            raise KeyboardInterrupt("synthetic")

        fake.load_config = explode
        prior = os.umask(0o077)
        try:
            with self.assertRaises(KeyboardInterrupt):
                RUNNER.execute(self.contract.formal_config_path, "run", base_module=fake)
            observed = os.umask(0o077)
            self.assertEqual(observed, 0o077)
        finally:
            os.umask(prior)
        self.assertEqual(fake.REPLICATION_CONFIG_SCHEMA, original_schema)
        self.assertIs(fake.REPLICATION_REQUIRED_PREREQUISITES, original_prerequisites)

    def test_verifier_restores_all_four_globals_after_baseexception(self) -> None:
        fake = FakeVerifier(self.contract)
        originals = (
            fake.REPLICATION_CONFIG_SCHEMA,
            fake.REPLICATION_REQUIRED_PREREQUISITES,
            fake.atomic_json,
            fake.write_summary,
        )

        def explode(_path: Path) -> dict:
            raise KeyboardInterrupt("synthetic")

        fake.verify = explode
        with self.assertRaises(KeyboardInterrupt):
            VERIFIER.execute(self.contract.formal_config_path, "final", base_module=fake)
        self.assertEqual(fake.REPLICATION_CONFIG_SCHEMA, originals[0])
        self.assertIs(fake.REPLICATION_REQUIRED_PREREQUISITES, originals[1])
        self.assertIs(fake.atomic_json, originals[2])
        self.assertIs(fake.write_summary, originals[3])

    def test_policy_five_and_deployable_three_are_both_strict(self) -> None:
        for field in ("policies", "deployable_policy_order"):
            with self.subTest(field=field):
                value = self.contract.read_formal()
                value["router"][field] = list(reversed(value["router"][field]))
                self.contract.write_formal(value)
                with self.assertRaisesRegex(ValueError, "policy"):
                    RUNNER.validate_launch_contract(self.contract.formal_config_path)
                self.contract.close()
                self.contract = SyntheticContract()

    def test_formal_commands_must_use_v3_launchers(self) -> None:
        value = self.contract.read_formal()
        value["commands"]["run"] = value["commands"]["run"].replace(
            "run_exp060_router_v3.py", "run_exp060_router.py"
        )
        self.contract.write_formal(value)
        with self.assertRaisesRegex(ValueError, "command"):
            RUNNER.validate_launch_contract(self.contract.formal_config_path)

    def test_execute_rejects_wrong_python_environment_before_base_import(self) -> None:
        fake = FakeRunner(self.contract)
        with (
            mock.patch.object(RUNNER.sys, "executable", "/nonexistent/seed44-python"),
            self.assertRaisesRegex(PermissionError, "Python environment"),
        ):
            RUNNER.execute(self.contract.formal_config_path, "run", base_module=fake)
        self.assertEqual(fake.load_calls, 0)

    def test_execute_rejects_dependency_version_drift_before_base_import(self) -> None:
        fake = FakeRunner(self.contract)
        with (
            mock.patch.object(RUNNER.importlib.metadata, "version", return_value="0.0"),
            self.assertRaisesRegex(PermissionError, "dependency version drift"),
        ):
            RUNNER.execute(self.contract.formal_config_path, "run", base_module=fake)
        self.assertEqual(fake.load_calls, 0)

    def test_preflight_status_and_resource_budget_are_deeply_bound(self) -> None:
        self.contract.mutate_preflight_verification(
            lambda value: value.__setitem__("status", "Failed")
        )
        with self.assertRaisesRegex(ValueError, "status"):
            RUNNER.validate_launch_contract(self.contract.formal_config_path)
        self.contract.close()
        self.contract = SyntheticContract()
        self.contract.mutate_preflight_verification(
            lambda value: value["resources"].__setitem__("wall_seconds", 301.0)
        )
        with self.assertRaisesRegex(ValueError, "resource"):
            VERIFIER.validate_launch_contract(self.contract.formal_config_path)

    def test_exact_preflight_checks_header_and_typed_run_resources(self) -> None:
        self.contract.mutate_preflight_verification(
            lambda value: value["checks"][0].__setitem__("name", "wrong.first.check")
        )
        with self.assertRaisesRegex(ValueError, "check-name"):
            RUNNER.validate_launch_contract(self.contract.formal_config_path)
        self.contract.close()
        self.contract = SyntheticContract()
        self.contract.mutate_preflight_run(
            lambda value: value["resources"].__setitem__("peak_process_rss_gb", False)
        )
        with self.assertRaisesRegex(ValueError, "run resource"):
            VERIFIER.validate_launch_contract(self.contract.formal_config_path)
        self.contract.close()
        self.contract = SyntheticContract()
        self.contract.mutate_preflight_contract(
            lambda value: value["input_schema"].pop()
        )
        with self.assertRaisesRegex(ValueError, "11-array"):
            RUNNER.validate_launch_contract(self.contract.formal_config_path)

    def test_formal_science_governance_and_numeric_types_are_exact(self) -> None:
        value = self.contract.read_formal()
        value["resources"]["api_cost_usd"] = False
        self.contract.write_formal(value)
        with self.assertRaisesRegex(ValueError, "resource"):
            RUNNER.validate_launch_contract(self.contract.formal_config_path)
        self.contract.close()
        self.contract = SyntheticContract()
        value = self.contract.read_formal()
        value["gate"]["minimum_six_label_macro_f1_gain"] = 999.0
        self.contract.write_formal(value)
        with self.assertRaisesRegex(ValueError, "governance/science"):
            VERIFIER.validate_launch_contract(self.contract.formal_config_path)

    def test_authorization_model_seed_rejects_float_and_bool_in_both_scopes(self) -> None:
        cases = (
            ("preflight", 44.0),
            ("preflight", True),
            ("formal", 44.0),
            ("formal", True),
        )
        for index, (scope, bad_seed) in enumerate(cases):
            if index:
                self.contract.close()
                self.contract = SyntheticContract()
            with self.subTest(scope=scope, bad_seed=bad_seed):
                if scope == "preflight":
                    self.contract.mutate_preflight_config(
                        lambda value: value["authorization"].__setitem__(
                            "model_seed", bad_seed
                        )
                    )
                else:
                    formal = self.contract.read_formal()
                    formal["authorization"]["model_seed"] = bad_seed
                    self.contract.write_formal(formal)
                for module in (RUNNER, VERIFIER):
                    with self.assertRaises(PermissionError):
                        module.validate_launch_contract(
                            self.contract.formal_config_path
                        )

    def test_preflight_public_privacy_is_recomputed(self) -> None:
        self.contract.mutate_preflight_verification(
            lambda value: value["checks"][0].__setitem__(
                "detail", {"route_scores": [0.1, 0.2]}
            )
        )
        with self.assertRaisesRegex(ValueError, "privacy"):
            RUNNER.validate_launch_contract(self.contract.formal_config_path)

    def test_hardlink_and_symlink_inputs_fail_closed(self) -> None:
        formal = self.contract.read_formal()
        paired = self.contract.project / formal["input"]["paired_oof"]["path"]
        os.link(paired, paired.with_name("second-link.npz"))
        with self.assertRaisesRegex(ValueError, "one-link"):
            RUNNER.validate_launch_contract(self.contract.formal_config_path)
        self.contract.close()
        self.contract = SyntheticContract()
        target = self.contract.formal_config_path
        target.unlink()
        target.symlink_to(target.with_name("missing.json"))
        with self.assertRaises((ValueError, FileNotFoundError)):
            VERIFIER.validate_launch_contract(target)

    def test_sidecar_partial_failure_is_terminal_and_not_cleaned(self) -> None:
        directory = self.contract.root / "sidecars"
        directory.mkdir(mode=0o755)
        target = directory / "verification.json"
        original_write = os.write
        calls = 0

        def fail_after_partial(descriptor: int, payload) -> int:
            nonlocal calls
            calls += 1
            if calls == 1:
                amount = max(1, len(payload) // 2)
                return original_write(descriptor, payload[:amount])
            raise OSError("synthetic partial failure")

        with mock.patch.object(VERIFIER.os, "write", side_effect=fail_after_partial):
            with self.assertRaises(OSError):
                VERIFIER._write_once(target, b"abcdef")
        self.assertTrue(os.path.lexists(target))
        with self.assertRaises(FileExistsError):
            VERIFIER._write_once(target, b"retry forbidden")

    def test_failed_verification_is_sealed_and_not_retried(self) -> None:
        RUNNER.execute(
            self.contract.formal_config_path, "run", base_module=FakeRunner(self.contract)
        )
        fake = FakeVerifier(self.contract)

        def failed(_path: Path) -> dict:
            fake.verify_calls += 1
            result = {
                "experiment_id": "EXP-062",
                "status": "Failed",
                "passed_count": 0,
                "failed_count": 1,
                "checks": [{"name": "synthetic.failed", "passed": False, "detail": None}],
                "claim_boundary": "synthetic",
            }
            run_dir = (
                self.contract.project
                / self.contract.outputs["public_attempt_dir"]
                / "router"
            )
            fake.atomic_json(run_dir / "verification.json", result)
            fake.write_summary(run_dir / "VERIFICATION-SUMMARY.md", result)
            return result

        fake.verify = failed
        result = VERIFIER.execute(
            self.contract.formal_config_path, "final", base_module=fake
        )
        self.assertEqual(result["status"], "Failed")
        with self.assertRaises(FileExistsError):
            VERIFIER.execute(self.contract.formal_config_path, "final", base_module=fake)

    def test_public_fd_normalization_preserves_bytes_inode_and_private_tree(self) -> None:
        fake = FakeRunner(self.contract)
        original = fake.formal_run
        observed: dict[str, object] = {}

        def restrictive(path: Path, config: dict) -> dict:
            result = original(path, config)
            public = (
                self.contract.project
                / self.contract.outputs["public_attempt_dir"]
                / "router"
            )
            private = (
                self.contract.project
                / self.contract.outputs["private_attempt_dir"]
                / "router"
            )
            target = public / "REPORT.md"
            os.chmod(target, 0o600)
            os.chmod(public / "frozen-sources", 0o700)
            metadata = os.lstat(target)
            observed["public"] = (
                metadata.st_ino, hashlib.sha256(target.read_bytes()).hexdigest()
            )
            observed["private"] = RUNNER._private_snapshot(private)
            return result

        fake.formal_run = restrictive
        RUNNER.execute(self.contract.formal_config_path, "run", base_module=fake)
        public = (
            self.contract.project
            / self.contract.outputs["public_attempt_dir"]
            / "router"
        )
        target = public / "REPORT.md"
        metadata = os.lstat(target)
        self.assertEqual(stat.S_IMODE(metadata.st_mode), 0o644)
        self.assertEqual(
            (metadata.st_ino, hashlib.sha256(target.read_bytes()).hexdigest()),
            observed["public"],
        )
        private = (
            self.contract.project
            / self.contract.outputs["private_attempt_dir"]
            / "router"
        )
        self.assertEqual(RUNNER._private_snapshot(private), observed["private"])

    def test_unexpected_nested_public_entry_fails_before_any_mode_or_byte_mutation(self) -> None:
        for module in (RUNNER, VERIFIER):
            with self.subTest(module=module.__name__):
                self.contract.create_router_tree()
                public = (
                    self.contract.project
                    / self.contract.outputs["public_attempt_dir"]
                    / "router"
                )
                frozen = public / "frozen-sources"
                report = public / "REPORT.md"
                os.chmod(public, 0o700)
                os.chmod(frozen, 0o700)
                os.chmod(report, 0o600)
                nested = frozen / "unexpected"
                nested.mkdir(mode=0o711)
                write_bytes(nested / "payload.bin", b"must-stay-identical", 0o600)
                before = {
                    "public_mode": stat.S_IMODE(os.lstat(public).st_mode),
                    "frozen_mode": stat.S_IMODE(os.lstat(frozen).st_mode),
                    "report_mode": stat.S_IMODE(os.lstat(report).st_mode),
                    "report_bytes": report.read_bytes(),
                    "nested_mode": stat.S_IMODE(os.lstat(nested).st_mode),
                    "nested_bytes": (nested / "payload.bin").read_bytes(),
                }
                config = self.contract.read_formal()
                frozen_names = {
                    "config.json",
                    *(Path(record["path"]).name for record in config["implementation"].values()),
                }
                with self.assertRaisesRegex(ValueError, "frozen-source manifest"):
                    module._normalize_public_tree(
                        public, set(module.PUBLIC_ROOT_NAMES), frozen_names
                    )
                after = {
                    "public_mode": stat.S_IMODE(os.lstat(public).st_mode),
                    "frozen_mode": stat.S_IMODE(os.lstat(frozen).st_mode),
                    "report_mode": stat.S_IMODE(os.lstat(report).st_mode),
                    "report_bytes": report.read_bytes(),
                    "nested_mode": stat.S_IMODE(os.lstat(nested).st_mode),
                    "nested_bytes": (nested / "payload.bin").read_bytes(),
                }
                self.assertEqual(after, before)
                self.contract.close()
                self.contract = SyntheticContract()

    def test_expected_public_name_with_directory_type_fails_before_normalization(self) -> None:
        for module in (RUNNER, VERIFIER):
            with self.subTest(module=module.__name__):
                self.contract.create_router_tree()
                public = (
                    self.contract.project
                    / self.contract.outputs["public_attempt_dir"]
                    / "router"
                )
                frozen = public / "frozen-sources"
                report = public / "REPORT.md"
                report.unlink()
                report.mkdir(mode=0o711)
                os.chmod(public, 0o700)
                os.chmod(frozen, 0o700)
                before = (
                    stat.S_IMODE(os.lstat(public).st_mode),
                    stat.S_IMODE(os.lstat(frozen).st_mode),
                    stat.S_IMODE(os.lstat(report).st_mode),
                )
                config = self.contract.read_formal()
                frozen_names = {
                    "config.json",
                    *(Path(record["path"]).name for record in config["implementation"].values()),
                }
                with self.assertRaisesRegex(ValueError, "not regular"):
                    module._normalize_public_tree(
                        public, set(module.PUBLIC_ROOT_NAMES), frozen_names
                    )
                after = (
                    stat.S_IMODE(os.lstat(public).st_mode),
                    stat.S_IMODE(os.lstat(frozen).st_mode),
                    stat.S_IMODE(os.lstat(report).st_mode),
                )
                self.assertEqual(after, before)
                self.contract.close()
                self.contract = SyntheticContract()

    def test_outer_budget_covers_validation_base_and_postcheck(self) -> None:
        fake = FakeRunner(self.contract)
        with (
            mock.patch.object(RUNNER.time, "monotonic", side_effect=[0.0, 1801.0]),
            mock.patch.object(RUNNER, "_peak_rss_gb", return_value=0.1),
            self.assertRaisesRegex(RuntimeError, "Outer governed runner budget"),
        ):
            RUNNER.execute(self.contract.formal_config_path, "run", base_module=fake)

    def test_verifier_outer_budget_covers_validation_base_and_postcheck(self) -> None:
        RUNNER.execute(
            self.contract.formal_config_path, "run", base_module=FakeRunner(self.contract)
        )
        fake = FakeVerifier(self.contract)
        with (
            mock.patch.object(VERIFIER.time, "monotonic", side_effect=[0.0, 1801.0]),
            mock.patch.object(VERIFIER, "_peak_rss_gb", return_value=0.1),
            self.assertRaisesRegex(RuntimeError, "Outer governed verifier budget"),
        ):
            VERIFIER.execute(self.contract.formal_config_path, "final", base_module=fake)

    def test_verifier_has_no_runner_import_or_science_runtime(self) -> None:
        verifier_source = VERIFIER_LAUNCHER_PATH.read_text()
        tree = ast.parse(verifier_source)
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
        self.assertNotIn("numpy", imports)
        load_function = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_load_base_verifier"
        )
        self.assertNotIn("BASE_RUNNER_PATH", ast.unparse(load_function))
        runner_source = RUNNER_LAUNCHER_PATH.read_text()
        self.assertNotIn("np.load", runner_source)

    def test_base_patch_surface_is_exact_and_governance_only(self) -> None:
        def stored_base_attributes(path: Path) -> set[str]:
            tree = ast.parse(path.read_text())
            return {
                node.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "base"
                and isinstance(node.ctx, ast.Store)
            }

        self.assertEqual(
            stored_base_attributes(RUNNER_LAUNCHER_PATH),
            {"REPLICATION_CONFIG_SCHEMA", "REPLICATION_REQUIRED_PREREQUISITES"},
        )
        self.assertEqual(
            stored_base_attributes(VERIFIER_LAUNCHER_PATH),
            {
                "REPLICATION_CONFIG_SCHEMA",
                "REPLICATION_REQUIRED_PREREQUISITES",
                "atomic_json",
                "write_summary",
            },
        )

    def test_base_files_are_archive_exact_and_direct_base_rejects_v3(self) -> None:
        expected = {
            BASE_RUNNER_PATH: RUNNER.BASE_RUNNER_SHA256,
            BASE_VERIFIER_PATH: RUNNER.BASE_VERIFIER_SHA256,
            BASE_TESTS_PATH: RUNNER.BASE_TESTS_SHA256,
        }
        for path, digest in expected.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        base_runner = load_module("exp060_base_runner_direct_reject", BASE_RUNNER_PATH)
        minimal = self.contract.root / "direct-v3.json"
        write_json(minimal, {"schema_version": RUNNER.FORMAL_CONFIG_SCHEMA})
        with self.assertRaisesRegex(ValueError, "Unexpected router config schema"):
            base_runner.load_config(minimal)
        base_verifier = load_module("exp060_base_verifier_direct_reject", BASE_VERIFIER_PATH)
        verifier_script = self.contract.root / "direct-verifier"
        verifier_config = verifier_script / "configs/direct-v3.json"
        write_json(verifier_config, {"schema_version": RUNNER.FORMAL_CONFIG_SCHEMA})
        with (
            mock.patch.object(base_verifier, "SCRIPT_DIR", verifier_script),
            mock.patch.object(base_verifier, "PROJECT_ROOT", self.contract.root),
            self.assertRaisesRegex(ValueError, "Unexpected router config schema"),
        ):
            base_verifier.verify(verifier_config)

    def test_exact_base_imports_do_not_create_hidden_bytecode(self) -> None:
        config = self.contract.read_formal()
        RUNNER._load_base_runner(config)
        VERIFIER._load_base_verifier(config)
        self.assertEqual(list(self.contract.script.rglob("__pycache__")), [])

    def test_verified_base_bytes_are_executed_even_if_path_is_swapped_after_read(self) -> None:
        config = self.contract.read_formal()
        base_path = self.contract.script / "run_exp060_router.py"
        original_secure_read = RUNNER._secure_read
        swapped = False

        def read_then_swap(path: Path, expected_mode=None):
            nonlocal swapped
            result = original_secure_read(path, expected_mode)
            if Path(path) == base_path and not swapped:
                replacement = base_path.with_name("malicious-replacement.py")
                write_bytes(
                    replacement,
                    b'REPLICATION_CONFIG_SCHEMA="malicious"\n'
                    b'REPLICATION_REQUIRED_PREREQUISITES=set()\n',
                    0o644,
                )
                os.replace(replacement, base_path)
                swapped = True
            return result

        with mock.patch.object(RUNNER, "_secure_read", side_effect=read_then_swap):
            module = RUNNER._load_base_runner(config)
        self.assertTrue(swapped)
        self.assertEqual(module.REPLICATION_CONFIG_SCHEMA, "exp-router-replication-config-v2")

    def test_secure_read_rejects_mode_race_at_opened_fd(self) -> None:
        target = self.contract.formal_config_path
        real_fstat = RUNNER.os.fstat

        def drifted_fstat(descriptor: int):
            observed = real_fstat(descriptor)
            values = {
                name: getattr(observed, name)
                for name in (
                    "st_dev", "st_ino", "st_mode", "st_nlink", "st_size",
                    "st_mtime_ns", "st_ctime_ns",
                )
            }
            values["st_mode"] = (values["st_mode"] & ~0o777) | 0o600
            return SimpleNamespace(**values)

        with (
            mock.patch.object(RUNNER.os, "fstat", side_effect=drifted_fstat),
            self.assertRaises(PermissionError),
        ):
            RUNNER._secure_read(target, 0o644)


if __name__ == "__main__":
    unittest.main()
