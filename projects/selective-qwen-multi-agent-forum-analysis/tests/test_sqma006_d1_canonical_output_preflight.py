#!/usr/bin/env python3

from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "sqma-006-d1-canonical-output-preflight.json"
RUNNER_PATH = PROJECT_ROOT / "scripts" / "run_sqma006_d1_canonical_output_preflight.py"
VERIFIER_PATH = PROJECT_ROOT / "scripts" / "verify_sqma006_d1_canonical_output_preflight.py"
PROTOCOL_PATH = PROJECT_ROOT / "protocols" / "sqma-006-d1-canonical-output-preflight.md"
V3_VALIDATOR_PATH = PROJECT_ROOT / "scripts" / "validate_agent_output_v3.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = load_module("sqma006_runner_for_tests", RUNNER_PATH)
VERIFIER = load_module("sqma006_verifier_for_tests", VERIFIER_PATH)
V3_VALIDATOR = load_module("sqma006_v3_validator_for_tests", V3_VALIDATOR_PATH)
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def source_rows(count: int = 70):
    rows = [
        {
            "schema_version": "sqma-gold-free-inference-snapshot-v1",
            "protocol_id": "SQMA-SCOPED-INPUT-V1",
            "sample_id": f"row-{index}", "component_id": f"group-{index}",
            "fold_id": index % 3, "source_ordinal": index + 10,
            "text": f"technical text {index}",
        }
        for index in range(count)
    ]
    rows.append(
        {
            **rows[0], "sample_id": "row-0-earlier", "source_ordinal": 1,
            "text": "earlier representative",
        }
    )
    return rows


class FakeCanonicalizer:
    ONTOLOGY = {
        "label_order": list(RUNNER.LABEL_ORDER),
        "instruction": "synthetic ontology",
    }

    @staticmethod
    def validation_result(role: str, raw_output: str, context):
        value = {"role": role, "evidence_spans": ["text"] if role in {"evidence", "single"} else []}
        return {
            "raw_valid": False,
            "canonical_valid": True,
            "canonical_json": "{}",
            "value": value,
            "error_code": None,
            "error_path": None,
        }

    @staticmethod
    def final_labels_from_validated(role: str, value):
        return ["joy"] if role in {"judge", "single"} else []

    @staticmethod
    def diagnostics_from_raw(role: str, raw_output: str, context):
        return {
            "out_of_ontology_labels": 0,
            "evidence_spans_total": 1,
            "evidence_spans_exact": 1,
        }


def selected_rows():
    selected, excluded = RUNNER.select_fresh_rows(source_rows(), expected_components=None)
    return selected, excluded


def synthetic_calls(selected):
    calls = []
    s3_outputs = {rank: {} for rank in range(32)}
    for ordinal, slot in enumerate(RUNNER.planned_call_slots(selected)):
        row = selected[slot["selection_rank"]]
        role = slot["role"]
        analysis_text = row["text"]
        context = {"analysis_text": analysis_text, "ontology": FakeCanonicalizer.ONTOLOGY}
        if slot["system_id"] == "S3" and role in {"critic", "judge"}:
            context["evidence"] = s3_outputs[slot["selection_rank"]].get(
                "evidence", VERIFIER.fallback_evidence()
            )
        if slot["system_id"] == "S3" and role == "judge":
            context["critic"] = s3_outputs[slot["selection_rank"]].get(
                "critic", VERIFIER.fallback_critic()
            )
        raw_output = f"recoverable:{role}"
        assessment = RUNNER.assessment_from_v3(
            FakeCanonicalizer, role, raw_output, context, token_cap_hit=False
        )
        if slot["system_id"] == "S3":
            s3_outputs[slot["selection_rank"]][role] = assessment["canonical_output"]
        calls.append(
            {
                "schema_version": "sqma-006-call-v1", "call_ordinal": ordinal,
                **slot,
                "sample_id": row["sample_id"], "component_id": row["component_id"],
                "source_ordinal": row["source_ordinal"],
                "seed": RUNNER.seed_for(
                    RUNNER.GENERATION_NAMESPACE, slot["system_id"], row["sample_id"],
                    role, slot["call_index"],
                ),
                "analysis_text": analysis_text,
                "analysis_text_sha256": hashlib.sha256(analysis_text.encode()).hexdigest(),
                "text_meta": {
                    "original_sha256": hashlib.sha256(row["text"].encode()).hexdigest(),
                    "analysis_sha256": hashlib.sha256(analysis_text.encode()).hexdigest(),
                    "original_token_count": 3, "analysis_token_count": 3,
                    "was_truncated": False, "model_free_truncation_replay": True,
                },
                "context_sha256": RUNNER.canonical_digest(context),
                "messages_sha256": "a" * 64, "prompt_ids_sha256": "b" * 64,
                "terminal": True, "finish_reason": "stop", "token_cap_hit": False,
                "raw_output": raw_output,
                "raw_output_sha256": hashlib.sha256(raw_output.encode()).hexdigest(),
                **assessment,
                "prefill_tokens": 100, "generated_tokens": 1,
                "latency_seconds": 1.0,
            }
        )
    return calls


def import_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


class SQMA006StaticDesignTests(unittest.TestCase):
    def test_execution_ready_config_binds_current_files(self) -> None:
        repo_root = PROJECT_ROOT.parents[1]
        for section in ("implementation", "prerequisites"):
            for name, record in CONFIG[section].items():
                if section == "implementation" and name == "grammar_v3":
                    continue
                artifact_path = repo_root / record["path"]
                self.assertTrue(artifact_path.is_file(), name)
                self.assertEqual(artifact_path.stat().st_size, record["bytes"], name)
                self.assertEqual(
                    hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                    record["sha256"],
                    name,
                )

    def test_config_is_frozen_execution_ready(self) -> None:
        RUNNER.validate_static_config(CONFIG)
        verification = VERIFIER.validate_static_config(CONFIG)
        self.assertEqual(verification["status"], "Passed")
        self.assertTrue(verification["execution_authorized"])
        self.assertTrue(verification["v3_identities_resolved"])
        self.assertFalse(RUNNER.contains_placeholder(CONFIG["implementation"]))
        self.assertTrue(CONFIG["authorization"]["private_input_access"])
        self.assertTrue(CONFIG["authorization"]["model_loading"])
        self.assertEqual(CONFIG["experiment_id"], "SQMA-006")

    def test_fresh_selection_recomputes_and_excludes_old_top32(self) -> None:
        rows = source_rows()
        selected, excluded = RUNNER.select_fresh_rows(rows, expected_components=None)
        verifier_selected, verifier_excluded = VERIFIER.select_fresh_rows(
            rows, expected_components=None
        )
        self.assertEqual(excluded, verifier_excluded)
        self.assertEqual(selected, verifier_selected)
        self.assertEqual(len(excluded), 32)
        self.assertEqual(len(selected), 32)
        self.assertFalse(excluded & {row["component_id"] for row in selected})
        chosen_zero = next(
            (row for row in selected if row["component_id"] == "group-0"), None
        )
        if chosen_zero is not None:
            self.assertEqual(chosen_zero["source_ordinal"], 1)
        self.assertEqual([row["selection_stratum"] for row in selected[:8]], ["shakedown"] * 8)
        self.assertEqual([row["selection_stratum"] for row in selected[8:]], ["locked"] * 24)

    def test_heldout_fold_cannot_enter_selection(self) -> None:
        rows = source_rows()
        rows[0]["fold_id"] = 3
        with self.assertRaisesRegex(RUNNER.D1PreflightError, "value"):
            RUNNER.select_fresh_rows(rows, expected_components=None)
        with self.assertRaisesRegex(VERIFIER.D1VerificationError, "held-out"):
            VERIFIER.select_fresh_rows(rows, expected_components=None)

    def test_call_plan_is_exactly_120_without_provisional_system(self) -> None:
        selected, _ = selected_rows()
        runner_slots = RUNNER.planned_call_slots(selected)
        verifier_slots = VERIFIER.expected_slots(selected)
        self.assertEqual(runner_slots, verifier_slots)
        self.assertEqual(len(runner_slots), 120)
        self.assertEqual(sum(slot["system_id"] == "S3" for slot in runner_slots), 96)
        self.assertEqual(sum(slot["system_id"] == "single_pool" for slot in runner_slots), 24)
        self.assertNotIn("provisional_s2b", {slot["system_id"] for slot in runner_slots})
        self.assertEqual(
            {slot["selection_rank"] for slot in runner_slots if slot["system_id"] == "single_pool"},
            set(range(8, 16)),
        )

    def test_four_role_contexts_exclude_gold_and_classifier_outputs(self) -> None:
        expected = {
            "evidence": ["analysis_text", "ontology"],
            "critic": ["analysis_text", "ontology", "evidence"],
            "judge": ["analysis_text", "ontology", "evidence", "critic"],
            "single": ["analysis_text", "ontology"],
        }
        self.assertEqual(CONFIG["role_context_allowlist"], expected)
        self.assertEqual(RUNNER.ROLE_CONTEXT_ALLOWLIST, expected)
        self.assertEqual(VERIFIER.ROLE_CONTEXT_ALLOWLIST, expected)
        encoded = json.dumps(expected).lower()
        for forbidden in ("gold", "classifier", "m1", "m3", "router"):
            self.assertNotIn(forbidden, encoded)

    def test_execution_config_mutations_fail_in_runner_and_verifier(self) -> None:
        mutations = {
            "private_root": lambda value: value["inputs"].__setitem__(
                "private_root", "projects/selective-qwen-multi-agent-forum-analysis/runs/not-private"
            ),
            "private_attempt_in_runs": lambda value: value["outputs"].__setitem__(
                "private_attempt_dir",
                "projects/selective-qwen-multi-agent-forum-analysis/runs/sqma-006-d1-canonical-output-preflight/attempt-1",
            ),
            "model_repo": lambda value: value["model"].__setitem__("repo_id", "Qwen/other"),
            "temperature": lambda value: value["generation"].__setitem__("temperature", 0.7),
            "rss_cap": lambda value: value["resources"].__setitem__(
                "maximum_process_rss_bytes", value["resources"]["maximum_process_rss_bytes"] + 1
            ),
            "private_inventory": lambda value: value["outputs"].__setitem__(
                "private_allowed_files", ["selection.json", "calls.jsonl"]
            ),
            "implementation_path": lambda value: value["implementation"]["runner"].__setitem__(
                "path", "projects/selective-qwen-multi-agent-forum-analysis/scripts/other.py"
            ),
        }
        for name, mutate in mutations.items():
            for module, error in (
                (RUNNER, RUNNER.D1PreflightError),
                (VERIFIER, VERIFIER.D1VerificationError),
            ):
                changed = deepcopy(CONFIG)
                mutate(changed)
                with self.subTest(name=name, module=module.__name__), self.assertRaises(error):
                    module.validate_static_config(changed)

    def test_raw_strict_failure_is_reported_but_not_gated(self) -> None:
        selected, _ = selected_rows()
        calls = synthetic_calls(selected)
        runner_metrics = RUNNER.derive_metrics(calls, selected, model_load_seconds=2.0)
        verifier_metrics = VERIFIER.derive_metrics(calls, selected, model_load_seconds=2.0)
        self.assertEqual(runner_metrics, verifier_metrics)
        self.assertEqual(runner_metrics["raw_strict_valid_rate_report_only"], 0.0)
        self.assertEqual(runner_metrics["canonical_system_output_valid_rate"], 1.0)
        self.assertTrue(RUNNER.gate_passes(runner_metrics))
        self.assertTrue(VERIFIER.gate_passes(verifier_metrics))

    def test_exact_json_fence_is_canonical_valid_but_raw_report_invalid(self) -> None:
        context = {"analysis_text": "technical text", "ontology": V3_VALIDATOR.ONTOLOGY}
        raw_output = (
            "```json\n"
            '{"schema_version":"evidence-v3","candidate_emotions":[],"evidence_spans":[],"insufficient_evidence":true}'
            "\n```"
        )
        runner_result = RUNNER.assessment_from_v3(
            V3_VALIDATOR, "evidence", raw_output, context
        )
        verifier_result = VERIFIER.assessment_from_v3(
            V3_VALIDATOR, "evidence", raw_output, context, token_cap_hit=False
        )
        self.assertEqual(runner_result, verifier_result)
        self.assertFalse(runner_result["raw_strict_valid"])
        self.assertTrue(runner_result["canonical_valid"])

    def test_combined_invalid_output_diagnostics_replay(self) -> None:
        context = {"analysis_text": "technical text", "ontology": V3_VALIDATOR.ONTOLOGY}
        raw_output = json.dumps(
            {
                "schema_version": "single-v3",
                "emotions": ["not-an-ontology-label"],
                "evidence_spans": ["not in the source"],
            },
            separators=(",", ":"),
        )
        runner_result = RUNNER.assessment_from_v3(
            V3_VALIDATOR, "single", raw_output, context
        )
        verifier_result = VERIFIER.assessment_from_v3(
            V3_VALIDATOR, "single", raw_output, context, token_cap_hit=False
        )
        self.assertEqual(runner_result, verifier_result)
        self.assertFalse(runner_result["canonical_valid"])
        self.assertEqual(runner_result["out_of_ontology_labels"], 1)
        self.assertEqual(runner_result["evidence_spans_total"], 1)
        self.assertEqual(runner_result["evidence_spans_exact"], 0)

    def test_one_locked_s3_canonical_failure_is_tolerated_but_two_fail(self) -> None:
        selected, _ = selected_rows()
        calls = synthetic_calls(selected)

        def invalidate(record):
            record["canonical_valid"] = False
            record["canonical_error"] = "canonical_schema"
            record["canonical_output"] = None
            record["final_labels"] = []

        first = next(
            record for record in calls
            if record["selection_rank"] == 8 and record["role"] == "evidence"
        )
        invalidate(first)
        once = RUNNER.derive_metrics(calls, selected, model_load_seconds=0)
        self.assertEqual(once["locked_s3_fallback_rows"], 1)
        self.assertTrue(RUNNER.gate_passes(once))

        second = next(
            record for record in calls
            if record["selection_rank"] == 9 and record["role"] == "evidence"
        )
        invalidate(second)
        twice = RUNNER.derive_metrics(calls, selected, model_load_seconds=0)
        self.assertEqual(twice["locked_s3_fallback_rows"], 2)
        self.assertFalse(RUNNER.gate_passes(twice))
        self.assertFalse(RUNNER.gate_checks(twice)["canonical_overall"])

    def test_independent_v3_replay_detects_canonical_drift(self) -> None:
        selected, _ = selected_rows()
        calls = synthetic_calls(selected)
        VERIFIER.replay_canonical_calls(calls, selected, FakeCanonicalizer)
        calls[0]["canonical_output"] = {"role": "tampered"}
        with self.assertRaisesRegex(VERIFIER.D1VerificationError, "canonical replay"):
            VERIFIER.replay_canonical_calls(calls, selected, FakeCanonicalizer)

    def test_static_runner_stops_before_private_or_model_access(self) -> None:
        with self.assertRaisesRegex(RUNNER.D1PreflightError, "not authorized"):
            RUNNER.assert_execution_ready({"authorization": {"execution_authorized": False}})
        tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
        top_level_roots: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                top_level_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                top_level_roots.add(node.module.split(".", 1)[0])
        self.assertFalse(top_level_roots & {"mlx", "mlx_lm", "torch", "transformers"})

    def test_verifier_is_independent_and_protocol_marks_new_experiment(self) -> None:
        roots = import_roots(VERIFIER_PATH)
        self.assertFalse(roots & {"mlx", "mlx_lm", "torch", "transformers"})
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import run_sqma006_d1_canonical_output_preflight", source)
        protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
        self.assertIn("新实验 `SQMA-006`", protocol)
        self.assertIn("不是 SQMA-003 attempt 3", protocol)
        self.assertIn("Raw strict validity", protocol)
        self.assertEqual(
            CONFIG["implementation"]["grammar_v3"]["mode"],
            "no_native_grammar_exact_json_fence_canonicalizer_v1",
        )
        self.assertEqual(
            CONFIG["implementation"]["grammar_v3"]["implementation"],
            "validate_agent_output_v3.validation_result",
        )
        self.assertNotIn("abstain", protocol.lower())


if __name__ == "__main__":
    unittest.main()
