#!/usr/bin/env python3

from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "sqma-003-classifier-free-agent-preflight.json"
PROMPT_PATH = PROJECT_ROOT / "prompts" / "agent-bundle-v1-classifier-free.json"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "agent-output-v2.schema.json"
VALIDATOR_PATH = PROJECT_ROOT / "scripts" / "validate_agent_output_v2.py"
RUNNER_PATH = PROJECT_ROOT / "scripts" / "run_sqma003_agent_preflight.py"
VERIFIER_PATH = PROJECT_ROOT / "scripts" / "verify_sqma003_agent_preflight.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_module("validate_agent_output_v2_for_sqma003_tests", VALIDATOR_PATH)
RUNNER = load_module("run_sqma003_agent_preflight_for_tests", RUNNER_PATH)
VERIFIER = load_module("verify_sqma003_agent_preflight_for_tests", VERIFIER_PATH)
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
PROMPT = json.loads(PROMPT_PATH.read_text(encoding="utf-8"))

TEXT = "I wasted the morning on this failure, but the workaround finally helped."
ONTOLOGY = {
    "label_order": list(VALIDATOR.LABEL_ORDER),
    "instruction": VALIDATOR.ONTOLOGY_INSTRUCTION,
}
EVIDENCE = {
    "schema_version": "evidence-appraisal-v2",
    "candidate_emotions": ["anger"],
    "evidence_spans": ["wasted the morning"],
    "expression_type": "implicit",
    "insufficient_evidence": False,
    "appraisal": {
        "goal_obstruction": "present",
        "responsibility": "situational",
        "control": "low",
        "certainty": "high",
        "expectation_violation": "present",
        "loss_or_threat": "loss",
    },
}
CRITIC = {
    "schema_version": "pragmatics-critic-v2",
    "reading": "emotion",
    "negation": "none",
    "sarcasm": "unlikely",
    "emotion_evidence": "sufficient",
    "recommended_emotions": ["anger"],
    "challenged_emotions": [],
    "warning_flags": ["implicit_emotion"],
}
JUDGE = {
    "schema_version": "judge-v2",
    "action": "decide_labels",
    "emotions": ["anger"],
    "evidence_refs": [0],
    "reason_flags": ["evidence_supported"],
}


def raw(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def context(role: str) -> dict[str, object]:
    value: dict[str, object] = {"analysis_text": TEXT, "ontology": ONTOLOGY}
    if role in {"pragmatics_critic", "judge"}:
        value["evidence_appraisal"] = EVIDENCE
    if role == "judge":
        value["pragmatics_critic"] = CRITIC
    return value


def single(labels: list[str] | None = None, *, abstain: bool = False) -> dict[str, object]:
    decision = deepcopy(JUDGE)
    if abstain:
        decision.update(
            {
                "action": "abstain",
                "emotions": [],
                "evidence_refs": [],
                "reason_flags": ["insufficient_evidence"],
            }
        )
    elif labels is not None:
        decision["emotions"] = labels
        if not labels:
            decision["evidence_refs"] = []
            decision["reason_flags"] = ["no_target_emotion"]
    return {
        "schema_version": "single-agent-v2",
        "evidence_appraisal": EVIDENCE,
        "pragmatics": CRITIC,
        "decision": decision,
    }


def reference_seed(system_id: str, sample_id: str, role_id: str, call_index: int) -> int:
    namespace = CONFIG["generation"]["seed_namespace"]
    material = f"{namespace}|{system_id}|{sample_id}|{role_id}|{call_index}"
    return int.from_bytes(hashlib.sha256(material.encode("utf-8")).digest()[:4], "big")


def select_components(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    representatives: dict[str, dict[str, object]] = {}
    for row in rows:
        component = str(row["component_id"])
        prior = representatives.get(component)
        if prior is None or int(row["source_ordinal"]) < int(prior["source_ordinal"]):
            representatives[component] = row
    namespace = CONFIG["selection"]["namespace"]
    ranked = sorted(
        representatives.values(),
        key=lambda row: hashlib.sha256(
            f"{namespace}|{row['component_id']}".encode("utf-8")
        ).hexdigest(),
    )
    return ranked[: int(CONFIG["selection"]["components"])]


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def runner_call_record_fields() -> set[str]:
    tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"), filename=str(RUNNER_PATH))
    candidates: list[set[str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "record" for target in node.targets):
            continue
        keys = {
            key.value
            for key in node.value.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
        if "system_id" in keys:
            candidates.append(keys)
    if len(candidates) != 1:
        raise AssertionError(f"expected one runner call record, observed {len(candidates)}")
    return candidates[0]


def locked_gate_passes(metrics: dict[str, float | int]) -> bool:
    gate = CONFIG["pass_gate"]
    return (
        metrics["planned_call_terminal_rate"] >= gate["planned_call_terminal_rate"]
        and metrics["raw_schema_valid_rate_overall"]
        >= gate["raw_schema_valid_rate_overall_minimum"]
        and metrics["raw_schema_valid_rate_per_role"]
        >= gate["raw_schema_valid_rate_per_role_minimum"]
        and metrics["technical_fallback_rows"]
        <= gate["maximum_locked_S3_technical_fallback_rows"]
        and metrics["evidence_exact_substring_rate"]
        >= gate["evidence_exact_substring_rate"]
        and metrics["out_of_ontology_labels"] <= gate["out_of_ontology_labels"]
        and metrics["token_cap_hits"] <= gate["maximum_token_cap_hits"]
        and metrics["mean_modal_exact_label_set_agreement"]
        >= gate["mean_modal_exact_label_set_agreement_minimum"]
    )


class Sqma003AgentPreflightTests(unittest.TestCase):
    def test_config_is_classifier_free_and_forbids_gold_or_base_outputs(self) -> None:
        self.assertTrue(CONFIG["authorization"]["gold_free_dev_input"])
        for field in (
            "gold_access",
            "accuracy_scoring",
            "train_capable_access",
            "consumer_gold_access",
            "fold3_access",
            "fold4_access",
            "validation_access",
            "test_access",
        ):
            self.assertFalse(CONFIG["authorization"][field], field)
        self.assertEqual(
            CONFIG["inputs"]["allowed_fields"],
            [
                "schema_version",
                "protocol_id",
                "sample_id",
                "component_id",
                "fold_id",
                "source_ordinal",
                "text",
            ],
        )
        external = PROMPT["information_contract"]["external_fields"]
        self.assertEqual(external, ["analysis_text", "ontology"])
        self.assertFalse(PROMPT["information_contract"]["model_predictions_visible"])
        self.assertFalse(PROMPT["information_contract"]["gold_visible"])

    def test_classifier_assisted_field_tokens_are_absent_from_method_sources(self) -> None:
        forbidden = ("classifier_result", "m1_labels", "m3_labels", "router_score", "accept_baseline")
        paths = (PROMPT_PATH, SCHEMA_PATH, VALIDATOR_PATH)
        for path in paths:
            source = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertFalse(any(token in source for token in forbidden))

    def test_component_selection_is_deterministic_text_and_order_independent(self) -> None:
        rows: list[dict[str, object]] = []
        for index in range(1963):
            rows.append(
                {
                    "schema_version": "sqma-gold-free-inference-snapshot-v1",
                    "protocol_id": "DATA-SO-TASK-V1",
                    "sample_id": f"sample-{index}-later",
                    "component_id": f"component-{index}",
                    "fold_id": index % 3,
                    "source_ordinal": index * 2 + 1,
                    "text": f"private text {index}",
                }
            )
            if index < 40:
                rows.append(
                {
                    "schema_version": "sqma-gold-free-inference-snapshot-v1",
                    "protocol_id": "DATA-SO-TASK-V1",
                    "sample_id": f"sample-{index}-first",
                    "component_id": f"component-{index}",
                    "fold_id": index % 3,
                    "source_ordinal": index * 2,
                    "text": f"representative {index}",
                }
                )
        selected = RUNNER.select_rows(deepcopy(rows), CONFIG["selection"]["namespace"])
        changed = list(reversed(deepcopy(rows)))
        for row in changed:
            row["text"] = "changed but selection-forbidden text"
        selected_changed = RUNNER.select_rows(changed, CONFIG["selection"]["namespace"])
        reference = select_components(rows)
        self.assertEqual(
            [(row["component_id"], row["source_ordinal"]) for row in selected],
            [(row["component_id"], row["source_ordinal"]) for row in selected_changed],
        )
        self.assertEqual(
            [(row["component_id"], row["source_ordinal"]) for row in selected],
            [(row["component_id"], row["source_ordinal"]) for row in reference],
        )
        self.assertEqual(len(selected), 32)
        self.assertEqual(len({row["component_id"] for row in selected}), 32)
        for row in selected:
            component_index = int(str(row["component_id"]).split("-")[-1])
            if component_index < 40:
                self.assertEqual(int(row["source_ordinal"]) % 2, 0)
        self.assertEqual([row["selection_rank"] for row in selected], list(range(32)))
        self.assertEqual([row["selection_stratum"] for row in selected[:8]], ["shakedown"] * 8)
        self.assertEqual([row["selection_stratum"] for row in selected[8:]], ["locked"] * 24)

    def test_seed_derivation_is_frozen_and_system_specific(self) -> None:
        self.assertEqual(
            RUNNER.seed_for(
                CONFIG["generation"]["seed_namespace"],
                "S3",
                "sample-0001",
                "evidence_appraisal",
                0,
            ),
            1657108407,
        )
        seeds = {
            reference_seed(system, "sample-0001", role, call)
            for system, role, call in (
                ("S3", "evidence_appraisal", 0),
                ("S3", "pragmatics_critic", 0),
                ("single_pool", "single_agent", 0),
                ("single_pool", "single_agent", 1),
                ("provisional_s2b", "single_agent", 0),
            )
        }
        self.assertEqual(len(seeds), 5)
        self.assertTrue(all(0 <= seed <= 0xFFFFFFFF for seed in seeds))

    def test_runner_prompt_rendering_enforces_visible_fields(self) -> None:
        class Tokenizer:
            def __init__(self) -> None:
                self.messages: list[dict[str, str]] | None = None

            def apply_chat_template(self, messages, **kwargs):
                self.messages = messages
                self.kwargs = kwargs
                return [11, 12, 13]

        tokenizer = Tokenizer()
        ids = RUNNER.render_prompt(
            tokenizer,
            PROMPT,
            "judge",
            context("judge"),
        )
        self.assertEqual(ids, [11, 12, 13])
        self.assertEqual(tokenizer.kwargs["enable_thinking"], False)
        rendered = "\n".join(message["content"] for message in tokenizer.messages or [])
        self.assertNotIn("classifier_result", rendered)
        self.assertNotIn("router_score", rendered)

        leaked = context("judge")
        leaked["classifier_result"] = {"final_labels": []}
        with self.assertRaisesRegex(RUNNER.PreflightError, "context allowlist"):
            RUNNER.render_prompt(tokenizer, PROMPT, "judge", leaked)

    def test_visible_fields_and_validator_context_are_role_isolated(self) -> None:
        expected = {
            "evidence_appraisal": ["analysis_text", "ontology"],
            "pragmatics_critic": ["analysis_text", "ontology", "evidence_appraisal"],
            "judge": [
                "analysis_text",
                "ontology",
                "evidence_appraisal",
                "pragmatics_critic",
            ],
            "single_agent": ["analysis_text", "ontology"],
        }
        for role, fields in expected.items():
            with self.subTest(role=role):
                self.assertEqual(PROMPT["roles"][role]["visible_fields"], fields)

        leaked = context("single_agent")
        leaked["classifier_result"] = {"final_labels": ["anger"]}
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "object_keys"):
            VALIDATOR.validate_output("single_agent", raw(single()), leaked)

    def test_self_consistency_strict_majority_invalid_and_even_tie(self) -> None:
        self.assertEqual(
            VALIDATOR.aggregate_label_votes(
                [("anger",), ("joy", "anger"), None]
            ),
            ["anger"],
        )
        self.assertEqual(VALIDATOR.aggregate_label_votes([("anger",), ()]), [])
        calls = [raw(single(["anger"])), raw(single(["anger"])), "not-json"]
        self.assertEqual(
            VALIDATOR.aggregate_single_agent_calls(calls, context("single_agent")),
            ["anger"],
        )
        calls = [raw(single(["anger"])), raw(single([], abstain=True))]
        self.assertEqual(
            VALIDATOR.aggregate_single_agent_calls(calls, context("single_agent")),
            [],
        )

    def test_call_plan_reuses_s1_and_has_exact_physical_cap(self) -> None:
        plan = CONFIG["call_plan"]
        self.assertEqual(plan["S3_calls"], plan["S3_rows"] * plan["S3_calls_per_row"])
        self.assertEqual(
            plan["single_pool_calls"],
            plan["single_pool_rows"] * plan["single_pool_calls_per_row"],
        )
        self.assertEqual(
            plan["provisional_s2b_calls"],
            plan["provisional_s2b_rows"] * plan["provisional_s2b_calls_per_row"],
        )
        self.assertEqual(
            plan["physical_call_cap"],
            plan["S3_calls"] + plan["single_pool_calls"] + plan["provisional_s2b_calls"],
        )
        self.assertEqual(plan["physical_call_cap"], 144)
        self.assertTrue(plan["S1_reuses_first_single_pool_call"])
        self.assertFalse(plan["accuracy_or_method_comparison"])

    def test_invalid_output_evidence_and_locked_pass_gate_are_fail_closed(self) -> None:
        bad_evidence = deepcopy(EVIDENCE)
        bad_evidence["evidence_spans"] = ["not present in analysis text"]
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "evidence_substring"):
            VALIDATOR.validate_output(
                "evidence_appraisal", raw(bad_evidence), context("evidence_appraisal")
            )
        self.assertEqual(
            VALIDATOR.final_labels_or_empty(
                "single_agent", "not-json", context("single_agent")
            ),
            [],
        )

        passing = {
            "planned_call_terminal_rate": 1.0,
            "raw_schema_valid_rate_overall": 0.99,
            "raw_schema_valid_rate_per_role": 0.96,
            "technical_fallback_rows": 1,
            "evidence_exact_substring_rate": 1.0,
            "out_of_ontology_labels": 0,
            "token_cap_hits": 0,
            "mean_modal_exact_label_set_agreement": 0.875,
        }
        self.assertTrue(locked_gate_passes(passing))
        for field, failing_value in (
            ("planned_call_terminal_rate", 0.99),
            ("raw_schema_valid_rate_overall", 0.97),
            ("raw_schema_valid_rate_per_role", 0.94),
            ("technical_fallback_rows", 2),
            ("evidence_exact_substring_rate", 0.99),
            ("out_of_ontology_labels", 1),
            ("token_cap_hits", 1),
            ("mean_modal_exact_label_set_agreement", 0.84),
        ):
            with self.subTest(field=field):
                failed = dict(passing)
                failed[field] = failing_value
                self.assertFalse(locked_gate_passes(failed))

    def test_output_contract_is_exact_relative_and_disjoint(self) -> None:
        outputs = CONFIG["outputs"]
        public = Path(outputs["public_attempt_dir"])
        private = Path(outputs["private_attempt_dir"])
        self.assertFalse(public.is_absolute())
        self.assertFalse(private.is_absolute())
        self.assertNotIn("..", public.parts)
        self.assertNotIn("..", private.parts)
        self.assertNotEqual(public, private)
        self.assertIn("/runs/", f"/{public.as_posix()}/")
        self.assertIn("/private/", f"/{private.as_posix()}/")
        self.assertEqual(
            outputs["public_allowed_files"],
            ["run-claim.json", "run.json", "verification.json", "complete.json"],
        )
        self.assertEqual(
            outputs["private_allowed_files"],
            ["selection.json", "calls.jsonl", "private-manifest.json"],
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            safe = RUNNER.checked_path(root, "runs/attempt-1")
            self.assertEqual(safe, root / "runs/attempt-1")
            with self.assertRaisesRegex(RUNNER.PreflightError, "relative path"):
                RUNNER.checked_path(root, str(root / "absolute"))
            with self.assertRaisesRegex(RUNNER.PreflightError, "escapes root"):
                RUNNER.checked_path(root, "../escape")
            target = root / "target.json"
            target.write_text("{}", encoding="utf-8")
            link = root / "target-link.json"
            link.symlink_to(target)
            with self.assertRaisesRegex(RUNNER.PreflightError, "file type drift"):
                RUNNER.regular(link)

    def test_verifier_ast_is_independent_and_model_free(self) -> None:
        imports = imported_roots(VERIFIER_PATH)
        self.assertNotIn("run_sqma003_agent_preflight", imports)
        self.assertFalse(imports & {"mlx", "mlx_lm", "torch", "transformers"})

    def test_runner_call_record_matches_independent_verifier_schema(self) -> None:
        self.assertEqual(runner_call_record_fields(), set(VERIFIER.CALL_FIELDS))

    def test_runner_has_no_classifier_field_reads_and_verifier_when_available(self) -> None:
        paths = [RUNNER_PATH, VERIFIER_PATH]
        forbidden = ("classifier_result", "m1_labels", "m3_labels", "router_score", "accept_baseline")
        for path in paths:
            with self.subTest(path=path.name):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                accessed: set[str] = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
                        if isinstance(node.slice.value, str):
                            accessed.add(node.slice.value)
                    elif isinstance(node, ast.Attribute):
                        accessed.add(node.attr)
                self.assertFalse(accessed & set(forbidden))

        leaked = {
            "schema_version": "sqma-gold-free-inference-snapshot-v1",
            "protocol_id": "DATA-SO-TASK-V1",
            "sample_id": "sample-a",
            "component_id": "component-a",
            "fold_id": 0,
            "source_ordinal": 0,
            "text": "text",
            "classifier_result": {"final_labels": []},
        }
        rows = []
        for index in range(1963):
            row = dict(leaked)
            row.update(
                {
                    "sample_id": f"sample-{index}",
                    "component_id": f"component-{index}",
                    "source_ordinal": index,
                }
            )
            rows.append(row)
        with self.assertRaisesRegex(RUNNER.PreflightError, "input schema drift"):
            RUNNER.select_rows(rows, CONFIG["selection"]["namespace"])


if __name__ == "__main__":
    unittest.main()
