#!/usr/bin/env python3

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "scripts" / "validate_agent_output_v3.py"
PROMPT_PATH = PROJECT_ROOT / "prompts" / "agent-bundle-v3-classifier-free.json"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "agent-output-v3.schema.json"
SPEC = importlib.util.spec_from_file_location("validate_agent_output_v3", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


TEXT = "I am frustrated by this failure, but the workaround now works."
ONTOLOGY = {
    "label_order": list(VALIDATOR.LABEL_ORDER),
    "instruction": VALIDATOR.ONTOLOGY_INSTRUCTION,
}
EVIDENCE = {
    "schema_version": "evidence-v3",
    "candidate_emotions": ["anger"],
    "evidence_spans": ["frustrated"],
    "insufficient_evidence": False,
}
CRITIC = {
    "schema_version": "critic-v3",
    "recommended_emotions": ["anger"],
    "challenged_emotions": [],
    "warning_flags": ["implicit_emotion"],
}
JUDGE = {
    "schema_version": "judge-v3",
    "emotions": ["anger"],
    "evidence_refs": [0],
}
SINGLE = {
    "schema_version": "single-v3",
    "emotions": ["anger"],
    "evidence_spans": ["frustrated"],
}


def raw(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def context(role: str) -> dict[str, object]:
    value: dict[str, object] = {"analysis_text": TEXT, "ontology": ONTOLOGY}
    if role in {"critic", "judge"}:
        value["evidence"] = EVIDENCE
    if role == "judge":
        value["critic"] = CRITIC
    return value


class MinimalV3ValidatorTests(unittest.TestCase):
    def test_all_four_minimal_outputs_validate(self) -> None:
        for role, value in (
            ("evidence", EVIDENCE),
            ("critic", CRITIC),
            ("judge", JUDGE),
            ("single", SINGLE),
        ):
            self.assertEqual(VALIDATOR.validate_output(role, raw(value), context(role)), value)

    def test_bare_and_exact_json_fence_have_separate_status(self) -> None:
        bare = VALIDATOR.validation_result("single", "  " + raw(SINGLE) + "\n", context("single"))
        self.assertTrue(bare["raw_valid"])
        self.assertTrue(bare["canonical_valid"])
        fenced = VALIDATOR.validation_result(
            "single", " \n```json\n" + raw(SINGLE) + "\n```\n", context("single")
        )
        self.assertFalse(fenced["raw_valid"])
        self.assertTrue(fenced["canonical_valid"])
        self.assertEqual(json.loads(fenced["canonical_json"]), SINGLE)

    def test_natural_language_wrappers_and_multiple_objects_are_rejected(self) -> None:
        for value in (
            "Here is the result: " + raw(SINGLE),
            raw(SINGLE) + " done",
            raw(SINGLE) + raw(SINGLE),
            "```JSON\n" + raw(SINGLE) + "\n```",
            "```json\n```json\n" + raw(SINGLE) + "\n```\n```",
        ):
            self.assertFalse(
                VALIDATOR.validation_result("single", value, context("single"))["canonical_valid"]
            )

    def test_nonstandard_or_incomplete_json_is_rejected(self) -> None:
        invalid_values = (
            '{"schema_version":"single-v3","emotions":[],"emotions":[],"evidence_spans":[]}',
            '{"schema_version":"single-v3","emotions":[NaN],"evidence_spans":[]}',
            "{'schema_version':'single-v3','emotions':[],'evidence_spans':[]}",
            '{"schema_version":"single-v3","emotions":[],"evidence_spans":[],}',
            '{"schema_version":"single-v3","emotions":[]',
        )
        for value in invalid_values:
            result = VALIDATOR.validation_result("single", value, context("single"))
            self.assertFalse(result["raw_valid"])
            self.assertFalse(result["canonical_valid"])

    def test_canonicalizer_does_not_repair_values_types_or_keys(self) -> None:
        wrong_order = deepcopy(SINGLE)
        wrong_order["emotions"] = ["anger", "joy"]
        canonical = VALIDATOR.canonicalize_output(raw(wrong_order))
        self.assertEqual(json.loads(canonical)["emotions"], ["anger", "joy"])
        self.assertEqual(
            VALIDATOR.validation_result("single", raw(wrong_order), context("single"))["error_code"],
            "label_order",
        )

        wrong_type = deepcopy(SINGLE)
        wrong_type["evidence_spans"] = [{"text": "frustrated"}]
        self.assertEqual(
            json.loads(VALIDATOR.canonicalize_output(raw(wrong_type)))["evidence_spans"],
            [{"text": "frustrated"}],
        )
        self.assertEqual(
            VALIDATOR.validation_result("single", raw(wrong_type), context("single"))["error_code"],
            "evidence_type",
        )

        extra = {**SINGLE, "reason": "unsupported"}
        self.assertEqual(
            VALIDATOR.validation_result("single", raw(extra), context("single"))["error_code"],
            "object_keys",
        )

    def test_syntax_diagnostics_capture_combined_errors_without_changing_gate(self) -> None:
        combined = {
            "schema_version": "evidence-v3",
            "candidate_emotions": ["annoyance"],
            "evidence_spans": ["fabricated span", {"text": "frustrated"}],
            "insufficient_evidence": False,
            "extra": "not allowed",
        }
        wrapped = "```json\n" + raw(combined) + "\n```"
        gate = VALIDATOR.validation_result("evidence", wrapped, context("evidence"))
        diagnostics = VALIDATOR.diagnostics_from_raw(
            "evidence", wrapped, context("evidence")
        )
        self.assertFalse(gate["raw_valid"])
        self.assertFalse(gate["canonical_valid"])
        self.assertEqual(
            diagnostics,
            {
                "out_of_ontology_labels": 1,
                "evidence_spans_total": 2,
                "evidence_spans_exact": 0,
            },
        )

    def test_syntax_diagnostics_scan_each_role_specific_field(self) -> None:
        critic = {
            "schema_version": "critic-v3",
            "recommended_emotions": ["annoyance"],
            "challenged_emotions": ["confusion"],
            "warning_flags": [],
        }
        judge = {
            "schema_version": "judge-v3",
            "emotions": ["annoyance"],
            "evidence_refs": [],
        }
        single = {
            "schema_version": "single-v3",
            "emotions": ["annoyance"],
            "evidence_spans": ["frustrated", "fabricated", {"text": "frustrated"}],
        }
        self.assertEqual(
            VALIDATOR.diagnostics_from_raw("critic", raw(critic), context("critic")),
            {
                "out_of_ontology_labels": 2,
                "evidence_spans_total": 0,
                "evidence_spans_exact": 0,
            },
        )
        self.assertEqual(
            VALIDATOR.diagnostics_from_raw("judge", raw(judge), context("judge"))[
                "out_of_ontology_labels"
            ],
            1,
        )
        self.assertEqual(
            VALIDATOR.diagnostics_from_raw("single", raw(single), context("single")),
            {
                "out_of_ontology_labels": 1,
                "evidence_spans_total": 3,
                "evidence_spans_exact": 1,
            },
        )

        self.assertEqual(
            VALIDATOR.diagnostics_from_raw(
                "evidence", "not parseable", context("evidence")
            ),
            {
                "out_of_ontology_labels": 0,
                "evidence_spans_total": 0,
                "evidence_spans_exact": 0,
            },
        )

    def test_label_evidence_and_reference_constraints_are_strict(self) -> None:
        bad_label = deepcopy(EVIDENCE)
        bad_label["candidate_emotions"] = ["annoyance"]
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "label_item"):
            VALIDATOR.validate_output("evidence", raw(bad_label), context("evidence"))

        bad_span = deepcopy(EVIDENCE)
        bad_span["evidence_spans"] = ["not in source"]
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "evidence_substring"):
            VALIDATOR.validate_output("evidence", raw(bad_span), context("evidence"))

        no_span = deepcopy(EVIDENCE)
        no_span["evidence_spans"] = []
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "labels_without_evidence"):
            VALIDATOR.validate_output("evidence", raw(no_span), context("evidence"))

        bad_ref = deepcopy(JUDGE)
        bad_ref["evidence_refs"] = [1]
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "reference_range"):
            VALIDATOR.validate_output("judge", raw(bad_ref), context("judge"))

    def test_critic_arrays_must_be_disjoint(self) -> None:
        value = deepcopy(CRITIC)
        value["challenged_emotions"] = ["anger"]
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "critic_overlap"):
            VALIDATOR.validate_output("critic", raw(value), context("critic"))

    def test_context_allowlist_rejects_classifier_or_gold_fields(self) -> None:
        for key in ("classifier_result", "gold"):
            value = context("single")
            value[key] = []
            with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "object_keys"):
                VALIDATOR.validate_output("single", raw(SINGLE), value)

    def test_invalid_final_output_and_even_vote_tie_resolve_empty(self) -> None:
        self.assertEqual(VALIDATOR.final_labels_or_empty("single", "not json", context("single")), [])
        self.assertEqual(VALIDATOR.aggregate_label_votes([["anger"], []]), [])
        self.assertEqual(
            VALIDATOR.aggregate_label_votes([["joy", "anger"], ["anger"], None]),
            ["anger"],
        )

    def test_prompt_and_schema_expose_only_four_minimal_outputs(self) -> None:
        prompt = json.loads(PROMPT_PATH.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(set(prompt["roles"]), {"evidence", "critic", "judge", "single"})
        self.assertEqual(
            set(schema["$defs"]["Evidence"]["properties"]),
            {"schema_version", "candidate_emotions", "evidence_spans", "insufficient_evidence"},
        )
        self.assertEqual(
            set(schema["$defs"]["Critic"]["properties"]),
            {"schema_version", "recommended_emotions", "challenged_emotions", "warning_flags"},
        )
        self.assertEqual(
            set(schema["$defs"]["Judge"]["properties"]),
            {"schema_version", "emotions", "evidence_refs"},
        )
        self.assertEqual(
            set(schema["$defs"]["Single"]["properties"]),
            {"schema_version", "emotions", "evidence_spans"},
        )
        self.assertEqual(prompt["canonicalization"]["natural_language_prefix_or_suffix"], "reject")
        critic_system = prompt["roles"]["critic"]["system"]
        for warning_flag in VALIDATOR.WARNING_FLAGS:
            self.assertIn(warning_flag, critic_system)

        examples = prompt["format_examples"]
        neutral_evidence = examples["evidence"]
        neutral_critic = examples["critic"]
        neutral_contexts = {
            "evidence": {"analysis_text": TEXT, "ontology": ONTOLOGY},
            "critic": {
                "analysis_text": TEXT,
                "ontology": ONTOLOGY,
                "evidence": neutral_evidence,
            },
            "judge": {
                "analysis_text": TEXT,
                "ontology": ONTOLOGY,
                "evidence": neutral_evidence,
                "critic": neutral_critic,
            },
            "single": {"analysis_text": TEXT, "ontology": ONTOLOGY},
        }
        for role, example in examples.items():
            self.assertEqual(
                VALIDATOR.validate_output(role, raw(example), neutral_contexts[role]),
                example,
            )


if __name__ == "__main__":
    unittest.main()
