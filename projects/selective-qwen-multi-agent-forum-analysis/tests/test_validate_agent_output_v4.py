#!/usr/bin/env python3

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "scripts" / "validate_agent_output_v4.py"
PROMPT_PATH = PROJECT_ROOT / "prompts" / "agent-bundle-v4-judge-evidence-slots.json"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "agent-output-v4-judge-evidence-slots.schema.json"
V3_PROMPT_PATH = PROJECT_ROOT / "prompts" / "agent-bundle-v3-classifier-free.json"
SPEC = importlib.util.spec_from_file_location("validate_agent_output_v4", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


TEXT = "I am frustrated, disappointed, and afraid this will fail."
ONTOLOGY = deepcopy(VALIDATOR.ONTOLOGY)
EVIDENCE = {
    "schema_version": "evidence-v3",
    "candidate_emotions": ["anger", "sadness", "fear"],
    "evidence_spans": ["frustrated", "disappointed", "afraid"],
    "insufficient_evidence": False,
}
CRITIC = {
    "schema_version": "critic-v3",
    "recommended_emotions": ["anger", "sadness", "fear"],
    "challenged_emotions": [],
    "warning_flags": ["multi_label_underprediction"],
}
SLOTS = {
    "love": [],
    "joy": [2, 0, 2],
    "surprise": [],
    "anger": [1],
    "sadness": [],
    "fear": [],
}


def raw(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def context() -> dict[str, object]:
    return {
        "analysis_text": TEXT,
        "ontology": ONTOLOGY,
        "evidence": EVIDENCE,
        "critic": CRITIC,
        "allowed_evidence_ids": [0, 1, 2],
    }


class JudgeEvidenceSlotContractTests(unittest.TestCase):
    def test_v3_evidence_and_critic_are_hash_pinned_and_reused(self) -> None:
        evidence_context = {"analysis_text": TEXT, "ontology": ONTOLOGY}
        critic_context = {**evidence_context, "evidence": EVIDENCE}
        self.assertEqual(VALIDATOR.validate_evidence(raw(EVIDENCE), evidence_context), EVIDENCE)
        self.assertEqual(VALIDATOR.validate_critic(raw(CRITIC), critic_context), CRITIC)
        self.assertEqual(VALIDATOR._sha256(VALIDATOR.V3_VALIDATOR_PATH), VALIDATOR.V3_VALIDATOR_SHA256)

    def test_bare_slots_derive_labels_and_normalize_references(self) -> None:
        result = VALIDATOR.judge_contract_result(raw(SLOTS), context())
        self.assertTrue(result["raw_contract_valid"])
        self.assertTrue(result["rendered_contract_valid"])
        self.assertEqual(result["derived_labels"], ["joy", "anger"])
        self.assertEqual(result["per_label_refs"]["joy"], [0, 2])
        self.assertEqual(result["per_label_refs"]["anger"], [1])
        self.assertEqual(result["diagnostics"]["reference_normalization_events"], 1)
        self.assertEqual(result["diagnostics"]["duplicate_references_removed"], 1)
        self.assertEqual(result["diagnostics"]["reference_order_normalized_slots"], 1)

    def test_exact_json_fence_is_rendered_but_not_raw_contract_valid(self) -> None:
        result = VALIDATOR.judge_contract_result(
            " \n```json\n" + raw(SLOTS) + "\n```\n", context()
        )
        self.assertFalse(result["raw_contract_valid"])
        self.assertTrue(result["rendered_contract_valid"])
        self.assertTrue(result["diagnostics"]["used_json_fence"])

    def test_missing_extra_or_mapped_label_keys_are_not_repaired(self) -> None:
        missing = dict(SLOTS)
        del missing["fear"]
        extra = {**SLOTS, "neutral": []}
        mapped = dict(SLOTS)
        mapped["angry"] = mapped.pop("anger")
        for value in (missing, extra, mapped):
            result = VALIDATOR.judge_contract_result(raw(value), context())
            self.assertFalse(result["rendered_contract_valid"])
            self.assertEqual(result["derived_labels"], [])
            self.assertEqual(result["per_label_refs"], {})
            self.assertEqual(result["diagnostics"]["error_code"], "judge_keys")

    def test_noninteger_references_are_rejected_without_coercion(self) -> None:
        for invalid in ("1", True, 1.0, {"id": 1}):
            value = deepcopy(SLOTS)
            value["anger"] = [invalid]
            result = VALIDATOR.judge_contract_result(raw(value), context())
            self.assertFalse(result["rendered_contract_valid"])
            self.assertEqual(result["diagnostics"]["error_code"], "reference_type")

    def test_out_of_range_reference_is_not_dropped_or_replaced(self) -> None:
        for invalid in (-1, 3):
            value = deepcopy(SLOTS)
            value["anger"] = [invalid]
            result = VALIDATOR.judge_contract_result(raw(value), context())
            self.assertFalse(result["rendered_contract_valid"])
            self.assertEqual(result["diagnostics"]["error_code"], "reference_range")

    def test_context_allowed_ids_must_equal_dynamic_evidence_range(self) -> None:
        for invalid in ([0, 2], [0, 1, 2, 3], ["0", 1, 2]):
            value = context()
            value["allowed_evidence_ids"] = invalid
            result = VALIDATOR.judge_contract_result(raw(SLOTS), value)
            self.assertFalse(result["rendered_contract_valid"])
            self.assertIn(
                result["diagnostics"]["error_code"],
                {"allowed_evidence_ids_type", "allowed_evidence_ids_drift"},
            )

    def test_sort_and_dedupe_never_changes_slot_emptiness(self) -> None:
        value = {label: [] for label in VALIDATOR.LABEL_ORDER}
        value["fear"] = [2, 2]
        result = VALIDATOR.judge_contract_result(raw(value), context())
        self.assertTrue(result["rendered_contract_valid"])
        self.assertEqual(result["per_label_refs"]["fear"], [2])
        self.assertEqual(result["derived_labels"], ["fear"])
        self.assertTrue(all(not result["per_label_refs"][label] for label in VALIDATOR.LABEL_ORDER[:-1]))

    def test_empty_allowed_ids_require_all_slots_empty(self) -> None:
        empty_evidence = {
            "schema_version": "evidence-v3",
            "candidate_emotions": [],
            "evidence_spans": [],
            "insufficient_evidence": True,
        }
        empty_critic = {
            "schema_version": "critic-v3",
            "recommended_emotions": [],
            "challenged_emotions": [],
            "warning_flags": [],
        }
        empty_context = {
            "analysis_text": TEXT,
            "ontology": ONTOLOGY,
            "evidence": empty_evidence,
            "critic": empty_critic,
            "allowed_evidence_ids": [],
        }
        empty_slots = {label: [] for label in VALIDATOR.LABEL_ORDER}
        self.assertEqual(
            VALIDATOR.judge_contract_result(raw(empty_slots), empty_context)["derived_labels"],
            [],
        )
        nonempty = dict(empty_slots)
        nonempty["anger"] = [0]
        self.assertFalse(
            VALIDATOR.judge_contract_result(raw(nonempty), empty_context)[
                "rendered_contract_valid"
            ]
        )

    def test_natural_language_or_multiple_objects_are_rejected(self) -> None:
        for value in (
            "Result: " + raw(SLOTS),
            raw(SLOTS) + " done",
            raw(SLOTS) + raw(SLOTS),
        ):
            self.assertFalse(
                VALIDATOR.judge_contract_result(value, context())["rendered_contract_valid"]
            )

    def test_prompt_and_schema_freeze_six_keys_and_dynamic_ids(self) -> None:
        prompt = json.loads(PROMPT_PATH.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        judge = schema["$defs"]["JudgeEvidenceSlots"]
        self.assertEqual(set(judge["required"]), set(VALIDATOR.LABEL_ORDER))
        self.assertEqual(set(judge["properties"]), set(VALIDATOR.LABEL_ORDER))
        self.assertNotIn("schema_version", judge["properties"])
        self.assertIn("allowed_evidence_ids", prompt["roles"]["judge"]["visible_fields"])
        self.assertIn("range(len(evidence.evidence_spans))", prompt["roles"]["judge"]["system"])

    def test_execution_prompt_sources_pin_v3_and_render_only_judge_from_v4(self) -> None:
        prompt = json.loads(PROMPT_PATH.read_text(encoding="utf-8"))
        dependency = prompt["frozen_v3_dependencies"]
        actual_hash = VALIDATOR._sha256(V3_PROMPT_PATH)
        self.assertEqual(dependency["prompt_bytes"], V3_PROMPT_PATH.stat().st_size)
        self.assertEqual(dependency["prompt_sha256"], actual_hash)
        self.assertEqual(
            actual_hash,
            "e224ea59e140ae60a56084fffcafbd785accf465df6e666345a6a5b91d9b2ff6",
        )
        sources = prompt["execution_prompt_source"]
        for role in ("evidence", "critic"):
            self.assertEqual(sources[role]["bundle"], dependency["prompt_path"])
            self.assertEqual(sources[role]["bundle_sha256"], dependency["prompt_sha256"])
            self.assertEqual(sources[role]["role"], role)
            self.assertFalse(prompt["upstream_role_metadata"][role]["render_from_this_bundle"])
            self.assertNotIn("system", prompt["upstream_role_metadata"][role])
        self.assertEqual(sources["judge"], {"bundle": "this_bundle", "role": "judge"})
        self.assertEqual(set(prompt["roles"]), {"judge"})


if __name__ == "__main__":
    unittest.main()
