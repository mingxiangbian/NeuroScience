#!/usr/bin/env python3

from __future__ import annotations

from copy import deepcopy
import importlib.util
import inspect
import json
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "scripts" / "validate_agent_output_v5.py"
PROMPT_PATH = PROJECT_ROOT / "prompts" / "agent-bundle-v5-judge-restricted-choice.json"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "agent-output-v5-judge-restricted-choice.schema.json"
SPEC = importlib.util.spec_from_file_location("validate_agent_output_v5", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class FakeTokenizer:
    def __init__(self, mapping=None, decoded=None):
        self.mapping = mapping or {"A": [10], "B": [11], "C": [12], "D": [13]}
        self.decoded = decoded or {10: "A", 11: "B", 12: "C", 13: "D"}

    def encode(self, value, *, add_special_tokens):
        assert add_special_tokens is False
        return list(self.mapping[value])

    def decode(self, token_ids, *, skip_special_tokens):
        assert skip_special_tokens is False
        return self.decoded[token_ids[0]]


def token_seal(tokenizer=None, eos=()):
    return VALIDATOR.build_token_seal(
        tokenizer or FakeTokenizer(),
        tokenizer_sha256="a" * 64,
        chat_template_sha256="b" * 64,
        eos_token_ids=eos,
    )


TEXT = "I am frustrated and afraid this will fail."
EVIDENCE = {
    "schema_version": "evidence-v3",
    "candidate_emotions": ["anger", "fear"],
    "evidence_spans": ["frustrated", "afraid", "fail"],
    "insufficient_evidence": False,
}
CRITIC = {
    "schema_version": "critic-v3",
    "recommended_emotions": ["anger", "fear"],
    "challenged_emotions": [],
    "warning_flags": [],
}


def context(seal, *, target="anger", allowed=None):
    allowed = [0, 1, 2] if allowed is None else allowed
    return {
        "analysis_text": TEXT,
        "ontology": deepcopy(VALIDATOR.ONTOLOGY),
        "evidence": EVIDENCE,
        "critic": CRITIC,
        "target_label": target,
        "allowed_evidence_ids": allowed,
        "option_mapping": VALIDATOR.build_candidate_mapping(allowed, seal),
    }


def terminal(token):
    return {
        "response_count": 1,
        "token": token,
        "generation_tokens": 1,
        "finish_reason": "length",
    }


class RestrictedJudgeV3Tests(unittest.TestCase):
    def test_option_token_seal_requires_four_unique_single_tokens(self) -> None:
        seal = token_seal()
        self.assertEqual(
            [entry["symbol"] for entry in seal["symbols"]],
            ["A", "B", "C", "D"],
        )
        self.assertEqual(
            [entry["token_id"] for entry in seal["symbols"]],
            [10, 11, 12, 13],
        )
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "option_not_single_token"):
            token_seal(FakeTokenizer(mapping={"A": [10, 20], "B": [11], "C": [12], "D": [13]}))
        duplicate = deepcopy(seal)
        duplicate["symbols"][1]["token_id"] = 10
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "option_token_identity"):
            VALIDATOR.validate_token_seal(duplicate)
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "option_is_eos"):
            token_seal(eos=(10,))
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "option_decode_drift"):
            token_seal(FakeTokenizer(decoded={10: " A", 11: "B", 12: "C", 13: "D"}))

    def test_candidate_mapping_is_none_then_at_most_three_evidence_ids(self) -> None:
        seal = token_seal()
        empty = VALIDATOR.build_candidate_mapping([], seal)
        self.assertEqual(empty, [{"symbol": "A", "token_id": 10, "evidence_id": None}])
        full = VALIDATOR.build_candidate_mapping([0, 1, 2], seal)
        self.assertEqual(
            [(item["symbol"], item["evidence_id"]) for item in full],
            [("A", None), ("B", 0), ("C", 1), ("D", 2)],
        )
        for invalid in ([1], [0, 2], [0, 1, 2, 3], [False]):
            with self.assertRaises(VALIDATOR.AgentOutputError):
                VALIDATOR.build_candidate_mapping(invalid, seal)

    def test_judge_context_requires_exact_dynamic_mapping(self) -> None:
        seal = token_seal()
        value, mapping = VALIDATOR.validate_judge_context(context(seal), seal)
        self.assertEqual(value["target_label"], "anger")
        self.assertEqual(mapping, value["option_mapping"])
        changed = context(seal)
        changed["option_mapping"][1]["evidence_id"] = 2
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "candidate_mapping"):
            VALIDATOR.validate_judge_context(changed, seal)
        changed = context(seal, target="neutral")
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "target_label"):
            VALIDATOR.validate_judge_context(changed, seal)

    def test_terminal_uses_token_and_expects_intentional_length_finish(self) -> None:
        seal = token_seal()
        mapping = VALIDATOR.build_candidate_mapping([0, 1, 2], seal)
        self.assertEqual(
            VALIDATOR.choice_from_terminal(terminal(12), mapping),
            {"symbol": "C", "token_id": 12, "evidence_id": 1},
        )
        mutations = (
            {**terminal(12), "response_count": 2},
            {**terminal(12), "generation_tokens": 2},
            {**terminal(12), "finish_reason": "stop"},
            {**terminal(12), "token": 99},
            {**terminal(12), "token": "12"},
        )
        for value in mutations:
            with self.assertRaises(VALIDATOR.AgentOutputError):
                VALIDATOR.choice_from_terminal(value, mapping)

    def test_six_single_token_choices_assemble_fixed_slots_and_labels(self) -> None:
        seal = token_seal()
        tokens = {
            "love": terminal(10),
            "joy": terminal(11),
            "surprise": terminal(10),
            "anger": terminal(13),
            "sadness": terminal(10),
            "fear": terminal(12),
        }
        result = VALIDATOR.assemble_judge_slots(
            tokens, allowed_evidence_ids=[0, 1, 2], token_seal=seal
        )
        self.assertTrue(result["raw_contract_valid"])
        self.assertTrue(result["rendered_contract_valid"])
        self.assertEqual(result["derived_labels"], ["joy", "anger", "fear"])
        self.assertEqual(result["per_label_refs"]["joy"], [0])
        self.assertEqual(result["per_label_refs"]["anger"], [2])
        self.assertEqual(result["per_label_refs"]["fear"], [1])
        self.assertEqual(result["diagnostics"]["selection_calls"], 6)
        self.assertEqual(result["diagnostics"]["illegal_reference_ids_constructed"], 0)

    def test_missing_label_call_or_illegal_token_fails_without_repair(self) -> None:
        seal = token_seal()
        values = {label: terminal(10) for label in VALIDATOR.LABEL_ORDER}
        del values["fear"]
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "label_call_inventory"):
            VALIDATOR.assemble_judge_slots(values, allowed_evidence_ids=[0], token_seal=seal)
        values["fear"] = terminal(13)
        with self.assertRaisesRegex(VALIDATOR.AgentOutputError, "masked_token_escape"):
            VALIDATOR.assemble_judge_slots(values, allowed_evidence_ids=[0], token_seal=seal)

    def test_python_reference_mask_keeps_only_current_candidate_tokens(self) -> None:
        logits = [0.1, 0.2, 9.0, 0.4, 0.5]
        first = VALIDATOR.python_mask_logits(logits, [0, 1])
        second = VALIDATOR.python_mask_logits(logits, [3, 4])
        self.assertEqual(first[:2], [0.1, 0.2])
        self.assertEqual(second[3:], [0.4, 0.5])
        self.assertEqual(first[2:], [-float("inf")] * 3)
        self.assertEqual(second[:3], [-float("inf")] * 3)

    def test_fresh_processors_capture_only_their_immutable_candidate_tuple(self) -> None:
        fake_mx = object()
        first = VALIDATOR.make_stateless_mlx_logits_processor(fake_mx, [10, 11])
        second = VALIDATOR.make_stateless_mlx_logits_processor(fake_mx, [10, 12, 13])
        self.assertIsNot(first, second)
        self.assertEqual(inspect.getclosurevars(first).nonlocals["allowed"], (10, 11))
        self.assertEqual(inspect.getclosurevars(second).nonlocals["allowed"], (10, 12, 13))

    def test_evidence_and_critic_remain_hash_pinned_v3_contracts(self) -> None:
        evidence_context = {"analysis_text": TEXT, "ontology": deepcopy(VALIDATOR.ONTOLOGY)}
        critic_context = {**evidence_context, "evidence": EVIDENCE}
        self.assertEqual(
            VALIDATOR.validate_evidence(json.dumps(EVIDENCE), evidence_context), EVIDENCE
        )
        self.assertEqual(
            VALIDATOR.validate_critic(json.dumps(CRITIC), critic_context), CRITIC
        )
        self.assertEqual(VALIDATOR._sha256(VALIDATOR.V3_VALIDATOR_PATH), VALIDATOR.V3_VALIDATOR_SHA256)

    def test_prompt_and_schema_freeze_api_cost_and_fairness_boundary(self) -> None:
        prompt = json.loads(PROMPT_PATH.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        runtime = prompt["runtime_api"]
        options = prompt["option_token_contract"]
        self.assertEqual(options["symbols"], ["A", "B", "C", "D"])
        self.assertTrue(options["runtime_token_ids_must_be_recomputed_from_the_hash_pinned_tokenizer"])
        self.assertTrue(options["public_or_previous_token_ids_are_not_trusted"])
        self.assertEqual(runtime["required_version"], "0.31.3")
        self.assertEqual(runtime["max_tokens"], 1)
        self.assertEqual(runtime["expected_finish_reason"], "length")
        self.assertEqual(runtime["selected_token_source"], "final_generation_response.token")
        self.assertFalse(runtime["processor_mutable_state"])
        self.assertIsNone(runtime["prompt_cache"])
        self.assertTrue(runtime["mlx_0_31_3_internal_unused_next_token_lookahead"])
        self.assertTrue(runtime["logits_processor_may_be_invoked_more_than_once"])
        self.assertTrue(runtime["fresh_processor_is_stateless_across_all_internal_invocations"])
        self.assertFalse(runtime["exact_model_decode_forward_steps_per_label_claimed"])
        fairness = prompt["cost_and_fairness"]
        self.assertEqual(fairness["judge_model_calls_per_row"], 6)
        self.assertTrue(fairness["not_call_matched_to_one_call_judge"])
        self.assertTrue(
            fairness["cannot_replace_one_call_judge_in_matched_comparison_without_a_six_call_control"]
        )
        self.assertTrue(
            fairness["generation_token_count_does_not_include_all_internal_lookahead_compute"]
        )
        self.assertTrue(fairness["measured_wall_time_and_peak_resources_are_required"])
        slots = schema["$defs"]["JudgeRestrictedSlots"]
        self.assertEqual(set(slots["properties"]), set(VALIDATOR.LABEL_ORDER))
        self.assertEqual(
            schema["$defs"]["SelectedEvidenceReference"]["maxItems"], 1
        )


if __name__ == "__main__":
    unittest.main()
