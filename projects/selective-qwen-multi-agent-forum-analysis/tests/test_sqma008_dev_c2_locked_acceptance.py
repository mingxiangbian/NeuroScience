#!/usr/bin/env python3

from __future__ import annotations

import ast
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "sqma-008-dev-c2-locked-acceptance.json"
RUNNER_PATH = PROJECT_ROOT / "scripts" / "run_sqma008_dev_c2_locked_acceptance.py"
VERIFIER_PATH = PROJECT_ROOT / "scripts" / "verify_sqma008_dev_c2_locked_acceptance.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module); return module


RUNNER = load("sqma008_runner_test", RUNNER_PATH)
VERIFIER = load("sqma008_verifier_test", VERIFIER_PATH)
CONFIG = json.loads(CONFIG_PATH.read_text())


def source_rows(count: int = 120):
    return [
        {
            "schema_version": "sqma-gold-free-inference-snapshot-v1",
            "protocol_id": "SQMA-SCOPED-INPUT-V1", "sample_id": f"row-{index}",
            "component_id": f"component-{index}", "fold_id": index % 3,
            "source_ordinal": index, "text": f"technical text {index}",
        }
        for index in range(count)
    ]


def slots(reference_values=None):
    value = {label: [] for label in RUNNER.LABEL_ORDER}
    if reference_values is not None: value["joy"] = list(reference_values)
    return value


def synthetic_calls(selected):
    result = []
    for slot in RUNNER.planned_call_slots(selected):
        call = {**slot, "terminal": True, "token_cap_hit": False, "unhandled_failure": False, "latency_seconds": 1.0, "canonical_valid": True}
        if slot["role"] == "judge":
            raw = json.dumps(slots(), separators=(",", ":"))
            call.update({"raw_output": raw, "allowed_evidence_ids": [], "judge_contract": RUNNER.judge_diagnostics(raw, [])})
        result.append(call)
    return result


def imports(path: Path):
    roots = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import): roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module: roots.add(node.module.split(".", 1)[0])
    return roots


def sealed_contract_fixture():
    records = {
        "config_record": {"path": "config.json", "bytes": 10, "sha256": "a" * 64},
        "claim_record": {"path": "run-claim.json", "bytes": 11, "sha256": "b" * 64},
        "selection_record": {"path": "selection.json", "bytes": 12, "sha256": "c" * 64},
        "calls_record": {"path": "calls.jsonl", "bytes": 13, "sha256": "d" * 64},
        "manifest_record": {"path": "private-manifest.json", "bytes": 14, "sha256": "e" * 64},
    }
    model = {
        "repo_id": "Qwen/Qwen3-4B", "revision": "frozen",
        "manifest_sha256": "f" * 64, "file_count": 9,
        "total_bytes": 8056445038, "adapter": None,
    }
    input_hashes = [record["sha256"] for record in CONFIG["inputs"]["gold_free_snapshots"]]
    claim = {
        "schema_version": "sqma-008-run-claim-v1", "experiment_id": "SQMA-008",
        "status": "ClaimedBeforeLockedInputOrModelLoad",
        "claimed_at_utc": "2026-09-04T00:00:00Z", "config": records["config_record"],
        "locked_rows": 24, "planned_calls": 72, "gold_access": False,
        "classifier_access": False, "locked_raw_human_access": False,
        "next_gate": "locked_c2_producer",
    }
    run = {
        "schema_version": "sqma-008-run-v1", "experiment_id": "SQMA-008",
        "status": "CompletedAwaitingVerification",
        "selection": {"components": 24, "locked": 24, "prior_excluded": 80},
        "calls": {"physical": 72, "by_role": {"evidence": 24, "critic": 24, "judge": 24}},
        "acceptance_gate": {}, "acceptance_checks": {}, "acceptance_passed": True,
        "resources": {
            "wall_seconds": 10.0, "peak_rss_bytes": 1000, "mlx_peak_bytes": 2000,
            "generated_tokens": 72, "model_load_seconds": 2.0,
            "private_output_bytes": 100,
            "free_disk_bytes_before": CONFIG["resources"]["minimum_free_disk_bytes"],
            "critical_memory_events": 0, "oom_or_kill_events": 0,
            "orphan_processes_after_exit": 0,
        },
        "identities": {
            "config": records["config_record"], "run_claim": records["claim_record"],
            "model": model, "selection_sha256": records["selection_record"]["sha256"],
            "calls_sha256": records["calls_record"]["sha256"],
            "manifest_sha256": records["manifest_record"]["sha256"],
        },
        "access": dict(VERIFIER.FROZEN_RUN_ACCESS),
        "next_gate": "independent_verification",
    }
    manifest = {
        "schema_version": "sqma-008-private-manifest-v1", "experiment_id": "SQMA-008",
        "status": "SealedAwaitingVerification", "input_snapshot_sha256": input_hashes,
        "selection": records["selection_record"], "calls_artifact": records["calls_record"],
        "model_identity": model, "access": dict(VERIFIER.FROZEN_RUN_ACCESS),
        "acceptance_passed": True, "next_gate": "independent_verification",
    }
    records.update(
        {
            "expected_model": model, "input_hashes": input_hashes,
            "generated_sum": 72, "private_bytes": 100, "public_bytes": 100,
        }
    )
    return claim, run, manifest, records


class SQMA008LockedAcceptanceTests(unittest.TestCase):
    def test_config_authorization_matches_design_profile(self) -> None:
        RUNNER.validate_static_config(CONFIG)
        result = VERIFIER.validate_static_config(CONFIG)
        enabled = {"execution_authorized", "private_input_access", "model_loading", "generation"}
        if CONFIG["design_status"] == "StaticDesignAwaitingImplementationPinning":
            self.assertTrue(all(value is False for value in CONFIG["authorization"].values()))
        elif CONFIG["design_status"] == "FrozenReady":
            self.assertTrue(all(CONFIG["authorization"][key] is True for key in enabled))
            self.assertTrue(
                all(
                    value is False
                    for key, value in CONFIG["authorization"].items()
                    if key not in enabled
                )
            )
        else:
            self.fail(f"unexpected design profile: {CONFIG['design_status']}")
        self.assertIs(
            result["execution_authorized"],
            CONFIG["authorization"]["execution_authorized"],
        )
        self.assertFalse(RUNNER.contains_placeholder(CONFIG))
        self.assertFalse(CONFIG["authorization"]["automatic_next_stage"])

    def test_four_selection_segments_are_disjoint(self) -> None:
        selected, prior = RUNNER.select_c2_rows(source_rows(), expected_components=None)
        verified, verifier_prior = VERIFIER.select_c2_rows(source_rows(), expected_components=None)
        self.assertEqual((selected, prior), (verified, verifier_prior))
        sets = [*prior, {row["component_id"] for row in selected}]
        self.assertEqual([len(value) for value in sets], [32, 32, 16, 24])
        for index, value in enumerate(sets):
            self.assertFalse(value & set().union(*sets[:index], *sets[index + 1 :]))
        self.assertEqual({row["selection_stratum"] for row in selected}, {"locked_acceptance"})

    def test_heldout_fold_rejected(self) -> None:
        values = source_rows(); values[0]["fold_id"] = 4
        with self.assertRaises(RUNNER.C2AcceptanceError): RUNNER.select_c2_rows(values, expected_components=None)
        with self.assertRaises(VERIFIER.C2VerificationError): VERIFIER.select_c2_rows(values, expected_components=None)

    def test_call_plan_is_exactly_72_s3_calls(self) -> None:
        selected, _ = RUNNER.select_c2_rows(source_rows(), expected_components=None)
        plan = RUNNER.planned_call_slots(selected)
        self.assertEqual(plan, VERIFIER.expected_slots(selected))
        self.assertEqual(len(plan), 72)
        self.assertEqual([call["role"] for call in plan[:3]], ["evidence", "critic", "judge"])
        self.assertTrue(all(call["selection_stratum"] == "locked_acceptance" for call in plan))
        self.assertEqual(RUNNER.GENERATION_NAMESPACE, "SQMA-008-dev-c2-generation-v1")
        self.assertEqual(VERIFIER.GENERATION_NAMESPACE, RUNNER.GENERATION_NAMESPACE)
        self.assertNotEqual(
            RUNNER.seed_for("S3", "sample-x", "judge", 2),
            int.from_bytes(
                __import__("hashlib").sha256(
                    b"SQMA-007-dev-c1-generation-v1|S3|sample-x|judge|2"
                ).digest()[:4],
                "big",
            ),
        )

    def test_gate_allows_one_fallback_but_not_two(self) -> None:
        selected, _ = RUNNER.select_c2_rows(source_rows(), expected_components=None)
        calls = synthetic_calls(selected)
        first = next(call for call in calls if call["selection_rank"] == 0 and call["role"] == "evidence")
        first["canonical_valid"] = False
        one = RUNNER.derive_acceptance_metrics(calls, selected, model_load_seconds=0)
        self.assertAlmostEqual(one["evidence_validator_valid_rate"], 23 / 24)
        self.assertEqual(one["system_fallback_rows"], 1)
        self.assertTrue(RUNNER.acceptance_passes(one))
        second = next(call for call in calls if call["selection_rank"] == 1 and call["role"] == "evidence")
        second["canonical_valid"] = False
        two = RUNNER.derive_acceptance_metrics(calls, selected, model_load_seconds=0)
        self.assertFalse(RUNNER.acceptance_passes(two))

    def test_any_judge_contract_error_fails(self) -> None:
        selected, _ = RUNNER.select_c2_rows(source_rows(), expected_components=None)
        calls = synthetic_calls(selected); judge = next(call for call in calls if call["role"] == "judge")
        judge["raw_output"] = json.dumps({"joy": []}); judge["judge_contract"] = RUNNER.judge_diagnostics(judge["raw_output"], [])
        metrics = RUNNER.derive_acceptance_metrics(calls, selected, model_load_seconds=0)
        self.assertEqual(metrics["contract_errors"], 1)
        self.assertFalse(RUNNER.acceptance_passes(metrics))

    def test_fence_can_render_but_fails_raw_gate(self) -> None:
        raw = "```json\n" + json.dumps(slots(), separators=(",", ":")) + "\n```"
        diagnostic = RUNNER.judge_diagnostics(raw, [])
        self.assertTrue(diagnostic["rendered_valid"])
        self.assertFalse(diagnostic["raw_json_parse"])
        selected, _ = RUNNER.select_c2_rows(source_rows(), expected_components=None)
        calls = synthetic_calls(selected); judge = next(call for call in calls if call["role"] == "judge")
        judge.update({"raw_output": raw, "judge_contract": diagnostic})
        self.assertFalse(RUNNER.acceptance_passes(RUNNER.derive_acceptance_metrics(calls, selected, model_load_seconds=0)))

    def test_normalization_is_report_only(self) -> None:
        selected, _ = RUNNER.select_c2_rows(source_rows(), expected_components=None)
        calls = synthetic_calls(selected); judge = next(call for call in calls if call["role"] == "judge")
        raw = json.dumps(slots([1, 0, 1]), separators=(",", ":")); diagnostic = RUNNER.judge_diagnostics(raw, [0, 1])
        judge.update({"raw_output": raw, "allowed_evidence_ids": [0, 1], "judge_contract": diagnostic})
        metrics = RUNNER.derive_acceptance_metrics(calls, selected, model_load_seconds=0)
        self.assertEqual(metrics["reference_normalization_events_report_only"], 1)
        self.assertEqual(metrics["duplicate_references_removed_report_only"], 1)
        self.assertEqual(metrics["reference_order_normalized_slots_report_only"], 1)
        self.assertTrue(RUNNER.acceptance_passes(metrics))

    def test_public_aggregate_has_no_locked_rows(self) -> None:
        selected, _ = RUNNER.select_c2_rows(source_rows(), expected_components=None)
        metrics = RUNNER.derive_acceptance_metrics(synthetic_calls(selected), selected, model_load_seconds=0)
        payload = RUNNER.public_run_payload(metrics, {"wall_seconds": 10}, {"config_sha256": "a" * 64})
        self.assertFalse(RUNNER.public_sensitive_paths(payload))
        self.assertTrue(RUNNER.public_sensitive_paths({"raw_output": "locked"}))

    def test_verifier_writes_only_a_pass_terminal(self) -> None:
        verification = {"status": "Passed", "gate": {"rows": 24}}
        complete = {"sqma008_complete": True}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            VERIFIER.write_pass_only(root, verification, complete)
            self.assertTrue((root / "verification.json").is_file())
            self.assertTrue((root / "complete.json").is_file())
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(VERIFIER.C2VerificationError):
                VERIFIER.write_pass_only(Path(directory), {"status": "Failed"}, complete)

    def test_sealed_contract_rejects_terminal_and_identity_tampering(self) -> None:
        claim, run, manifest, records = sealed_contract_fixture()
        VERIFIER.validate_sealed_contract(CONFIG, claim, run, manifest, **records)
        mutations = {
            "failed_status": lambda c, r, m: r.__setitem__("status", "Failed"),
            "wrong_next": lambda c, r, m: r.__setitem__("next_gate", "wrong"),
            "gold_true": lambda c, r, m: r["access"].__setitem__("gold_accessed", True),
            "resource_overcap": lambda c, r, m: r["resources"].__setitem__(
                "peak_rss_bytes", CONFIG["resources"]["maximum_process_rss_bytes"] + 1
            ),
            "claim_drift": lambda c, r, m: c.__setitem__("planned_calls", 71),
            "manifest_drift": lambda c, r, m: m.__setitem__("status", "Failed"),
        }
        for name, mutation in mutations.items():
            changed_claim = deepcopy(claim)
            changed_run = deepcopy(run)
            changed_manifest = deepcopy(manifest)
            mutation(changed_claim, changed_run, changed_manifest)
            with self.subTest(name=name), self.assertRaises(VERIFIER.C2VerificationError):
                VERIFIER.validate_sealed_contract(
                    CONFIG, changed_claim, changed_run, changed_manifest, **records
                )

    def test_config_pin_mutations_are_rejected_by_both_consumers(self) -> None:
        mutations = [
            lambda value: value["inputs"].__setitem__("private_root", "runs/bad"),
            lambda value: value["outputs"].__setitem__("private_attempt_dir", "projects/selective-qwen-multi-agent-forum-analysis/runs/bad"),
            lambda value: value["frozen_c1_method"]["model"].__setitem__("repo_id", "Qwen/other"),
            lambda value: value["frozen_c1_method"]["generation"]["judge"].__setitem__("temperature", 0.1),
            lambda value: value["frozen_c1_method"]["generation"]["evidence"].__setitem__("temperature", 0.5),
            lambda value: value["frozen_c1_method"]["generation"]["critic"].__setitem__("temperature", 0.5),
            lambda value: value["frozen_c1_method"]["generation"].__setitem__("seed_namespace", "wrong"),
            lambda value: value["resources"].__setitem__("maximum_process_rss_bytes", 1),
            lambda value: value["outputs"].__setitem__("private_allowed_files", []),
            lambda value: value["implementation"]["prompt_bundle"].__setitem__("path", "prompts/wrong.json"),
            lambda value: value["prerequisites"]["sqma007_complete"].__setitem__("sha256", "0" * 64),
        ]
        ready = deepcopy(CONFIG)
        ready["design_status"] = "FrozenReady"
        ready["next_gate"] = "execute_locked_c2"
        for key in ("execution_authorized", "private_input_access", "model_loading", "generation"):
            ready["authorization"][key] = True
        profiles = (CONFIG, ready)
        for profile in profiles:
            RUNNER.validate_static_config(profile)
            VERIFIER.validate_static_config(profile)
            for mutation in mutations:
                for module, error in ((RUNNER, RUNNER.C2AcceptanceError), (VERIFIER, VERIFIER.C2VerificationError)):
                    changed = deepcopy(profile); mutation(changed)
                    with self.subTest(profile=profile["design_status"], module=module.__name__), self.assertRaises(error):
                        module.validate_static_config(changed)

    def test_verifier_is_model_and_runner_independent(self) -> None:
        roots = imports(VERIFIER_PATH)
        self.assertFalse(roots & {"mlx", "mlx_lm", "torch", "transformers"})
        self.assertNotIn("import run_sqma008_dev_c2_locked_acceptance", VERIFIER_PATH.read_text())


if __name__ == "__main__":
    unittest.main()
