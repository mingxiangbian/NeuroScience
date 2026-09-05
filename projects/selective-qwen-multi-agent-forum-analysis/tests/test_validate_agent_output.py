#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_agent_output.py"
SPEC = importlib.util.spec_from_file_location("validate_agent_output", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


TEXT = "I have wasted the entire morning, but the workaround finally helped."
CLASSIFIER = {"final_labels": ["anger"], "m1_labels": ["anger"], "m3_labels": None}
EVIDENCE = {
    "schema_version": "evidence-appraisal-v1",
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
    "schema_version": "pragmatics-critic-v1",
    "reading": "emotion",
    "negation": "none",
    "sarcasm": "unlikely",
    "emotion_evidence": "sufficient",
    "recommended_emotions": ["anger"],
    "challenged_emotions": [],
    "warning_flags": ["implicit_emotion"],
}
JUDGE = {
    "schema_version": "judge-v1",
    "action": "accept_baseline",
    "emotions": ["anger"],
    "evidence_refs": [0],
    "reason_flags": ["baseline_supported", "evidence_supported"],
}


def raw(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class AgentOutputValidatorTests(unittest.TestCase):
    def test_valid_role_outputs(self) -> None:
        self.assertEqual(
            VALIDATOR.validate_output("evidence_appraisal", raw(EVIDENCE), {"analysis_text": TEXT}),
            EVIDENCE,
        )
        self.assertEqual(
            VALIDATOR.validate_output("pragmatics_critic", raw(CRITIC), {"analysis_text": TEXT}),
            CRITIC,
        )
        self.assertEqual(
            VALIDATOR.validate_output(
                "judge",
                raw(JUDGE),
                {"analysis_text": TEXT, "classifier_result": CLASSIFIER, "evidence_appraisal": EVIDENCE},
            ),
            JUDGE,
        )

    def test_valid_single_agent(self) -> None:
        value = {
            "schema_version": "single-agent-v1",
            "evidence_appraisal": EVIDENCE,
            "pragmatics": CRITIC,
            "decision": JUDGE,
        }
        self.assertEqual(
            VALIDATOR.validate_output(
                "single_agent",
                raw(value),
                {"analysis_text": TEXT, "classifier_result": CLASSIFIER},
            ),
            value,
        )

    def test_duplicate_json_key_rejected(self) -> None:
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "duplicate_key"):
            VALIDATOR.parse_strict_json('{"schema_version":"judge-v1","schema_version":"judge-v1"}')

    def test_label_order_rejected(self) -> None:
        value = dict(EVIDENCE)
        value["candidate_emotions"] = ["anger", "joy"]
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "label_order"):
            VALIDATOR.validate_output("evidence_appraisal", raw(value), {"analysis_text": TEXT})

    def test_non_substring_evidence_rejected(self) -> None:
        value = dict(EVIDENCE)
        value["evidence_spans"] = ["not present"]
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "evidence_substring"):
            VALIDATOR.validate_output("evidence_appraisal", raw(value), {"analysis_text": TEXT})

    def test_non_string_evidence_rejected_cleanly(self) -> None:
        value = dict(EVIDENCE)
        value["evidence_spans"] = [{}]
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "evidence_length"):
            VALIDATOR.validate_output("evidence_appraisal", raw(value), {"analysis_text": TEXT})

    def test_critic_overlap_rejected(self) -> None:
        value = dict(CRITIC)
        value["challenged_emotions"] = ["anger"]
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "critic_emotion_overlap"):
            VALIDATOR.validate_output("pragmatics_critic", raw(value), {"analysis_text": TEXT})

    def test_judge_accept_mismatch_rejected(self) -> None:
        value = dict(JUDGE)
        value["emotions"] = ["joy"]
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "accept_mismatch"):
            VALIDATOR.validate_output(
                "judge",
                raw(value),
                {"analysis_text": TEXT, "classifier_result": CLASSIFIER, "evidence_appraisal": EVIDENCE},
            )

    def test_judge_bad_reference_rejected(self) -> None:
        value = dict(JUDGE)
        value["evidence_refs"] = [1]
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "evidence_ref_range"):
            VALIDATOR.validate_output(
                "judge",
                raw(value),
                {"analysis_text": TEXT, "classifier_result": CLASSIFIER, "evidence_appraisal": EVIDENCE},
            )

    def test_revision_requires_evidence(self) -> None:
        value = dict(JUDGE)
        value.update({"action": "revise_labels", "emotions": ["sadness"], "evidence_refs": []})
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "revision_without_evidence"):
            VALIDATOR.validate_output(
                "judge",
                raw(value),
                {"analysis_text": TEXT, "classifier_result": CLASSIFIER, "evidence_appraisal": EVIDENCE},
            )

    def test_abstain_is_valid_and_empty(self) -> None:
        value = dict(JUDGE)
        value.update({"action": "abstain", "emotions": [], "evidence_refs": [], "reason_flags": ["insufficient_evidence"]})
        self.assertEqual(
            VALIDATOR.validate_output(
                "judge",
                raw(value),
                {"analysis_text": TEXT, "classifier_result": CLASSIFIER, "evidence_appraisal": EVIDENCE},
            ),
            value,
        )


if __name__ == "__main__":
    unittest.main()
