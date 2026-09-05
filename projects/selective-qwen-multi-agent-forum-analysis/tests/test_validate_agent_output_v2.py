#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "scripts" / "validate_agent_output_v2.py"
PROMPT_PATH = PROJECT_ROOT / "prompts" / "agent-bundle-v1-classifier-free.json"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "agent-output-v2.schema.json"
SPEC = importlib.util.spec_from_file_location("validate_agent_output_v2", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


TEXT = "I have wasted the entire morning, but the workaround finally helped."
ONTOLOGY = {
    "label_order": list(VALIDATOR.LABEL_ORDER),
    "instruction": VALIDATOR.ONTOLOGY_INSTRUCTION,
}
EVIDENCE = {
    "schema_version": "evidence-appraisal-v2",
    "candidate_emotions": ["anger"],
    "evidence_spans": ["wasted the entire morning"],
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


def single(decision: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "schema_version": "single-agent-v2",
        "evidence_appraisal": EVIDENCE,
        "pragmatics": CRITIC,
        "decision": decision or JUDGE,
    }


class AgentOutputV2ValidatorTests(unittest.TestCase):
    def test_valid_role_and_single_outputs(self) -> None:
        self.assertEqual(
            VALIDATOR.validate_output("evidence_appraisal", raw(EVIDENCE), context("evidence_appraisal")),
            EVIDENCE,
        )
        self.assertEqual(
            VALIDATOR.validate_output("pragmatics_critic", raw(CRITIC), context("pragmatics_critic")),
            CRITIC,
        )
        self.assertEqual(
            VALIDATOR.validate_output("judge", raw(JUDGE), context("judge")), JUDGE
        )
        value = single()
        self.assertEqual(
            VALIDATOR.validate_output("single_agent", raw(value), context("single_agent")), value
        )
        self.assertEqual(
            VALIDATOR.final_labels_or_empty("single_agent", raw(value), context("single_agent")),
            ["anger"],
        )

    def test_context_rejects_any_unlisted_external_information(self) -> None:
        value = context("single_agent")
        value["model_predictions"] = ["anger"]
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "object_keys"):
            VALIDATOR.validate_output("single_agent", raw(single()), value)

    def test_nonempty_decision_requires_valid_evidence_reference(self) -> None:
        no_ref = dict(JUDGE)
        no_ref["evidence_refs"] = []
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "decision_without_evidence"):
            VALIDATOR.validate_output("judge", raw(no_ref), context("judge"))
        bad_ref = dict(JUDGE)
        bad_ref["evidence_refs"] = [1]
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "evidence_ref_range"):
            VALIDATOR.validate_output("judge", raw(bad_ref), context("judge"))

    def test_empty_decision_and_abstention_resolve_to_empty(self) -> None:
        empty_decision = dict(JUDGE)
        empty_decision.update(
            {"emotions": [], "evidence_refs": [], "reason_flags": ["no_target_emotion"]}
        )
        self.assertEqual(
            VALIDATOR.final_labels_or_empty("judge", raw(empty_decision), context("judge")), []
        )
        abstain = dict(JUDGE)
        abstain.update(
            {
                "action": "abstain",
                "emotions": [],
                "evidence_refs": [],
                "reason_flags": ["insufficient_evidence"],
            }
        )
        self.assertEqual(
            VALIDATOR.validate_output("judge", raw(abstain), context("judge")), abstain
        )
        self.assertEqual(
            VALIDATOR.final_labels_or_empty("judge", raw(abstain), context("judge")), []
        )

    def test_invalid_final_output_resolves_to_empty(self) -> None:
        invalid = dict(JUDGE)
        invalid["action"] = "unsupported"
        self.assertEqual(
            VALIDATOR.final_labels_or_empty("judge", raw(invalid), context("judge")), []
        )
        self.assertEqual(
            VALIDATOR.final_labels_or_empty("single_agent", "not-json", context("single_agent")),
            [],
        )

    def test_strict_majority_and_even_tie_make_tied_label_absent(self) -> None:
        self.assertEqual(
            VALIDATOR.aggregate_label_votes([("anger",)]),
            ["anger"],
        )
        self.assertEqual(VALIDATOR.aggregate_label_votes([("anger",), ()]), [])
        self.assertEqual(
            VALIDATOR.aggregate_label_votes([("joy", "anger"), ("anger",), None]),
            ["anger"],
        )
        abstain = dict(JUDGE)
        abstain.update({"action": "abstain", "emotions": [], "evidence_refs": []})
        calls = [raw(single()), raw(single(abstain))]
        self.assertEqual(VALIDATOR.aggregate_single_agent_calls(calls, context("single_agent")), [])
        self.assertEqual(
            VALIDATOR.aggregate_single_agent_calls(
                [raw(single()), "not-json"], context("single_agent")
            ),
            [],
        )

    def test_evidence_label_order_and_critic_overlap_are_strict(self) -> None:
        evidence = dict(EVIDENCE)
        evidence["evidence_spans"] = ["not in the text"]
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "evidence_substring"):
            VALIDATOR.validate_output(
                "evidence_appraisal", raw(evidence), context("evidence_appraisal")
            )
        evidence = dict(EVIDENCE)
        evidence["candidate_emotions"] = ["anger", "joy"]
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "label_order"):
            VALIDATOR.validate_output(
                "evidence_appraisal", raw(evidence), context("evidence_appraisal")
            )
        critic = dict(CRITIC)
        critic["challenged_emotions"] = ["anger"]
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "critic_emotion_overlap"):
            VALIDATOR.validate_output("pragmatics_critic", raw(critic), context("pragmatics_critic"))

    def test_new_prompt_schema_and_validator_omit_old_dependency_tokens(self) -> None:
        prompt = json.loads(PROMPT_PATH.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        sources = [
            PROMPT_PATH.read_text(encoding="utf-8"),
            SCHEMA_PATH.read_text(encoding="utf-8"),
            MODULE_PATH.read_text(encoding="utf-8"),
        ]
        forbidden = ("classifier" + "_result", "S" + "0", "accept" + "_baseline")
        for source in sources:
            self.assertFalse(any(token in source for token in forbidden))
        self.assertEqual(prompt["information_contract"]["external_fields"], ["analysis_text", "ontology"])
        self.assertEqual(prompt["ontology"]["instruction"], VALIDATOR.ONTOLOGY_INSTRUCTION)
        self.assertEqual(
            schema["$defs"]["Judge"]["properties"]["action"]["enum"],
            ["decide_labels", "abstain"],
        )
        self.assertEqual(prompt["self_consistency"]["even_k_tie_rule"], "label_absent")


if __name__ == "__main__":
    unittest.main()
