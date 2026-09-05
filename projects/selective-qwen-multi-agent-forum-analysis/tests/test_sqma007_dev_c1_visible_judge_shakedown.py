#!/usr/bin/env python3

from __future__ import annotations

import ast
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "sqma-007-dev-c1-visible-judge-shakedown.json"
RUNNER_PATH = PROJECT_ROOT / "scripts" / "run_sqma007_dev_c1_visible_judge_shakedown.py"
VERIFIER_PATH = PROJECT_ROOT / "scripts" / "verify_sqma007_dev_c1_visible_judge_shakedown.py"
V4_PATH = PROJECT_ROOT / "scripts" / "validate_agent_output_v4.py"
PROTOCOL_PATH = PROJECT_ROOT / "protocols" / "sqma-007-dev-c1-visible-judge-shakedown.md"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module); return module


RUNNER = load("sqma007_runner_test", RUNNER_PATH)
VERIFIER = load("sqma007_verifier_test", VERIFIER_PATH)
V4 = load("sqma007_v4_test", V4_PATH)
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def rows(count: int = 90):
    return [
        {
            "schema_version": "sqma-gold-free-inference-snapshot-v1",
            "protocol_id": "SQMA-SCOPED-INPUT-V1", "sample_id": f"row-{index}",
            "component_id": f"component-{index}", "fold_id": index % 3,
            "source_ordinal": index, "text": f"technical text {index}",
        }
        for index in range(count)
    ]


def valid_slots(reference: int | None = None):
    value = {label: [] for label in RUNNER.LABEL_ORDER}
    if reference is not None:
        value["joy"] = [reference]
    return value


def synthetic_calls(selected, *, role_valid: bool = True):
    calls = []
    for slot in RUNNER.planned_call_slots(selected):
        role = slot["role"]
        call = {
            **slot, "terminal": True, "token_cap_hit": False,
            "unhandled_failure": False, "latency_seconds": 1.0,
            "canonical_valid": role_valid if role in {"evidence", "critic"} else True,
        }
        if role == "judge":
            raw = json.dumps(valid_slots(), separators=(",", ":"))
            call.update(
                {
                    "raw_output": raw, "allowed_evidence_ids": [],
                    "judge_contract": RUNNER.judge_contract_diagnostics(raw, []),
                }
            )
        calls.append(call)
    return calls


def import_roots(path: Path):
    roots = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import): roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module: roots.add(node.module.split(".", 1)[0])
    return roots


class SQMA007C1Tests(unittest.TestCase):
    def test_config_is_frozen_execution_ready(self) -> None:
        RUNNER.validate_static_config(CONFIG)
        result = VERIFIER.validate_static_config(CONFIG)
        self.assertTrue(result["execution_authorized"])
        self.assertFalse(RUNNER.contains_placeholder(CONFIG["implementation"]))
        self.assertEqual(CONFIG["selection"]["locked_rows"], 0)

    def test_three_selection_sets_are_deterministic_and_disjoint(self) -> None:
        selected, old_ids, sqma006_ids = RUNNER.select_c1_rows(rows(), expected_components=None)
        verified, old_verified, sqma006_verified = VERIFIER.select_c1_rows(rows(), expected_components=None)
        self.assertEqual((selected, old_ids, sqma006_ids), (verified, old_verified, sqma006_verified))
        c1_ids = {row["component_id"] for row in selected}
        self.assertEqual((len(old_ids), len(sqma006_ids), len(c1_ids)), (32, 32, 16))
        self.assertFalse(old_ids & sqma006_ids or old_ids & c1_ids or sqma006_ids & c1_ids)
        self.assertEqual({row["selection_stratum"] for row in selected}, {"visible_shakedown"})

    def test_fold3_is_rejected(self) -> None:
        values = rows(); values[0]["fold_id"] = 3
        with self.assertRaises(RUNNER.C1DesignError): RUNNER.select_c1_rows(values, expected_components=None)
        with self.assertRaises(VERIFIER.C1VerificationError): VERIFIER.select_c1_rows(values, expected_components=None)

    def test_call_plan_is_48_and_judge_is_greedy(self) -> None:
        selected, _, _ = RUNNER.select_c1_rows(rows(), expected_components=None)
        slots = RUNNER.planned_call_slots(selected)
        self.assertEqual(slots, VERIFIER.expected_slots(selected))
        self.assertEqual(len(slots), 48)
        self.assertEqual([slot["role"] for slot in slots[:3]], ["evidence", "critic", "judge"])
        self.assertTrue(all(slot["temperature"] == 0.0 for slot in slots if slot["role"] == "judge"))
        self.assertTrue(all(slot["temperature"] == 0.6 for slot in slots if slot["role"] != "judge"))

    def test_judge_fixed_slots_and_v4_renderer_agree(self) -> None:
        context = {
            "analysis_text": "technical text", "ontology": V4.ONTOLOGY,
            "evidence": {"schema_version": "evidence-v3", "candidate_emotions": ["joy"], "evidence_spans": ["text"], "insufficient_evidence": False},
            "critic": {"schema_version": "critic-v3", "recommended_emotions": ["joy"], "challenged_emotions": [], "warning_flags": []},
            "allowed_evidence_ids": [0],
        }
        raw = json.dumps(valid_slots(0), separators=(",", ":"))
        diagnostic = RUNNER.judge_contract_diagnostics(raw, [0])
        self.assertEqual(diagnostic, VERIFIER.judge_contract_diagnostics(raw, [0]))
        self.assertTrue(diagnostic["rendered_valid"])
        self.assertEqual(diagnostic["rendered_labels"], ["joy"])
        self.assertEqual(V4.judge_contract_result(raw, context)["derived_labels"], ["joy"])
        fenced = f"```json\n{raw}\n```"
        self.assertFalse(RUNNER.judge_contract_diagnostics(fenced, [0])["raw_json_parse"])
        self.assertTrue(RUNNER.judge_contract_diagnostics(fenced, [0])["rendered_valid"])

    def test_reference_normalization_is_report_only(self) -> None:
        selected, _, _ = RUNNER.select_c1_rows(rows(), expected_components=None)
        calls = synthetic_calls(selected)
        judge = next(call for call in calls if call["role"] == "judge")
        value = valid_slots(); value["joy"] = [1, 0, 1]
        judge["raw_output"] = json.dumps(value, separators=(",", ":"))
        judge["allowed_evidence_ids"] = [0, 1]
        judge["judge_contract"] = RUNNER.judge_contract_diagnostics(
            judge["raw_output"], judge["allowed_evidence_ids"]
        )
        metrics = RUNNER.derive_gate1(calls, selected, model_load_seconds=0)
        self.assertEqual(metrics["reference_normalization_events_report_only"], 1)
        self.assertEqual(metrics["duplicate_references_removed_report_only"], 1)
        self.assertEqual(metrics["reference_order_normalized_slots_report_only"], 1)
        self.assertTrue(RUNNER.gate1_passes(metrics))

    def test_judge_contract_rejects_each_forbidden_shape(self) -> None:
        cases = []
        extra = valid_slots(); extra["schema_version"] = "judge"
        missing = valid_slots(); missing.pop("fear")
        non_array = valid_slots(); non_array["joy"] = 0
        string_ref = valid_slots(); string_ref["joy"] = ["0"]
        disallowed = valid_slots(); disallowed["joy"] = [1]
        cases.extend([(extra, []), (missing, []), (non_array, []), (string_ref, [0]), (disallowed, [0])])
        for value, allowed in cases:
            raw = json.dumps(value, separators=(",", ":"))
            with self.subTest(value=value):
                self.assertFalse(RUNNER.judge_contract_diagnostics(raw, allowed)["rendered_valid"])
        prefixed = "answer: " + json.dumps(valid_slots())
        self.assertFalse(RUNNER.judge_contract_diagnostics(prefixed, [])["raw_json_parse"])

    def test_evidence_critic_invalidity_is_report_only(self) -> None:
        selected, _, _ = RUNNER.select_c1_rows(rows(), expected_components=None)
        calls = synthetic_calls(selected, role_valid=False)
        runner_metrics = RUNNER.derive_gate1(calls, selected, model_load_seconds=1)
        verifier_metrics = VERIFIER.derive_gate1(calls, selected, model_load_seconds=1)
        self.assertEqual(runner_metrics, verifier_metrics)
        self.assertEqual(runner_metrics["evidence_canonical_valid_rate_report_only"], 0.0)
        self.assertEqual(runner_metrics["critic_canonical_valid_rate_report_only"], 0.0)
        self.assertTrue(RUNNER.gate1_passes(runner_metrics))

    def test_one_judge_contract_error_fails_to_constrained_decoding_decision(self) -> None:
        selected, _, _ = RUNNER.select_c1_rows(rows(), expected_components=None)
        calls = synthetic_calls(selected)
        judge = next(call for call in calls if call["role"] == "judge")
        judge["raw_output"] = json.dumps({"joy": []})
        judge["judge_contract"] = RUNNER.judge_contract_diagnostics(judge["raw_output"], [])
        metrics = RUNNER.derive_gate1(calls, selected, model_load_seconds=0)
        self.assertFalse(RUNNER.gate1_passes(metrics))
        self.assertEqual(CONFIG["failure_policy"]["next_decision"], "constrained_decoding_decision")
        self.assertFalse(CONFIG["failure_policy"]["automatic_prompt_revision"])

    def test_contexts_and_execution_prompt_sources_are_separate(self) -> None:
        self.assertEqual(CONFIG["role_context_allowlist"], RUNNER.ROLE_CONTEXT_ALLOWLIST)
        self.assertNotIn("gold", json.dumps(CONFIG["role_context_allowlist"]).lower())
        self.assertNotEqual(
            CONFIG["implementation"]["evidence_critic_prompt_v3"]["path"],
            CONFIG["implementation"]["judge_prompt_v4"]["path"],
        )

    def test_execution_config_mutations_fail_in_both_consumers(self) -> None:
        mutations = {
            "private_root": lambda value: value["inputs"].__setitem__(
                "private_root", "projects/selective-qwen-multi-agent-forum-analysis/runs/not-private"
            ),
            "private_attempt_in_runs": lambda value: value["outputs"].__setitem__(
                "private_attempt_dir", "projects/selective-qwen-multi-agent-forum-analysis/runs/sqma-007/bad"
            ),
            "model_repo": lambda value: value["model"].__setitem__("repo_id", "Qwen/other"),
            "judge_temperature": lambda value: value["generation"]["judge"].__setitem__("temperature", 0.1),
            "evidence_temperature": lambda value: value["generation"]["evidence"].__setitem__("temperature", 0.5),
            "critic_temperature": lambda value: value["generation"]["critic"].__setitem__("temperature", 0.5),
            "rss_cap": lambda value: value["resources"].__setitem__(
                "maximum_process_rss_bytes", value["resources"]["maximum_process_rss_bytes"] + 1
            ),
            "private_inventory": lambda value: value["outputs"].__setitem__(
                "private_allowed_files", ["selection.json", "calls.jsonl"]
            ),
            "prompt_path": lambda value: value["implementation"]["judge_prompt_v4"].__setitem__(
                "path", "projects/selective-qwen-multi-agent-forum-analysis/prompts/other.json"
            ),
        }
        for name, mutation in mutations.items():
            for module, error in (
                (RUNNER, RUNNER.C1DesignError),
                (VERIFIER, VERIFIER.C1VerificationError),
            ):
                changed = deepcopy(CONFIG); mutation(changed)
                with self.subTest(name=name, module=module.__name__), self.assertRaises(error):
                    module.validate_static_config(changed)

    def test_runner_blocks_and_verifier_is_independent(self) -> None:
        with self.assertRaises(RUNNER.C1DesignError):
            RUNNER.assert_execution_ready({"authorization": {"execution_authorized": False}})
        roots = import_roots(VERIFIER_PATH)
        self.assertFalse(roots & {"mlx", "mlx_lm", "torch", "transformers"})
        self.assertNotIn("import run_sqma007_dev_c1_visible_judge_shakedown", VERIFIER_PATH.read_text())
        protocol = PROTOCOL_PATH.read_text()
        self.assertIn("C1 内容可被查看", protocol)
        self.assertIn("constrained_decoding_decision", protocol)


if __name__ == "__main__":
    unittest.main()
