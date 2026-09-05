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
VERIFIER_PATH = PROJECT_ROOT / "scripts" / "verify_sqma005_agent_tune_comparison.py"
SCORER_PATH = PROJECT_ROOT / "scripts" / "score_sqma005_agent_tune_comparison.py"
VALIDATOR_PATH = PROJECT_ROOT / "scripts" / "validate_agent_output_v2.py"
BUNDLE_PATH = PROJECT_ROOT / "prompts" / "agent-bundle-v2-classifier-free.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


VERIFIER = load_module("sqma005_verifier_for_tests", VERIFIER_PATH)
SCORER = load_module("sqma005_scorer_for_verifier_tests", SCORER_PATH)
VALIDATOR = load_module("sqma005_validator_for_verifier_tests", VALIDATOR_PATH)
BUNDLE = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))


ANGER_EVIDENCE = {
    "schema_version": "evidence-appraisal-v2",
    "candidate_emotions": ["anger"],
    "evidence_spans": ["angry"],
    "expression_type": "explicit",
    "insufficient_evidence": False,
    "appraisal": {
        "goal_obstruction": "present", "responsibility": "situational",
        "control": "low", "certainty": "high", "expectation_violation": "present",
        "loss_or_threat": "none",
    },
}
ANGER_CRITIC = {
    "schema_version": "pragmatics-critic-v2", "reading": "emotion",
    "negation": "none", "sarcasm": "unlikely", "emotion_evidence": "sufficient",
    "recommended_emotions": ["anger"], "challenged_emotions": [], "warning_flags": [],
}
ANGER_JUDGE = {
    "schema_version": "judge-v2", "action": "decide_labels", "emotions": ["anger"],
    "evidence_refs": [0], "reason_flags": ["evidence_supported"],
}
ANGER_SINGLE = {
    "schema_version": "single-agent-v2", "evidence_appraisal": ANGER_EVIDENCE,
    "pragmatics": ANGER_CRITIC, "decision": ANGER_JUDGE,
}


def input_row():
    return {
        "schema_version": "sqma-gold-free-inference-snapshot-v1",
        "protocol_id": "SQMA-SCOPED-INPUT-V1",
        "sample_id": "row-a", "component_id": "group-a", "fold_id": 3,
        "source_ordinal": 4, "text": "I am angry.",
    }


def raw(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def make_calls(*, invalid_evidence: bool = False):
    row = input_row()
    analysis_text = row["text"]
    text_meta = {
        "original_sha256": VERIFIER.text_sha256(row["text"]),
        "analysis_sha256": VERIFIER.text_sha256(analysis_text),
        "original_token_count": 4,
        "analysis_token_count": 4,
        "was_truncated": False,
        "model_free_truncation_replay": True,
    }
    examples = BUNDLE["concrete_output_examples"]
    raw_outputs = [
        "{" if invalid_evidence else raw(ANGER_EVIDENCE),
        raw(ANGER_CRITIC),
        raw(examples["judge"] if invalid_evidence else ANGER_JUDGE),
        raw(ANGER_SINGLE),
        raw(ANGER_SINGLE),
        raw(examples["single_agent"]),
    ]
    contracts = VERIFIER.build_output_contracts(BUNDLE)
    ontology = {"label_order": list(VERIFIER.LABEL_ORDER), "instruction": BUNDLE["ontology"]["instruction"]}
    parsed_roles = {}
    calls = []
    for slot, raw_output in zip(VERIFIER.expected_call_slots(1), raw_outputs, strict=True):
        call_ordinal, row_ordinal, system, role, call_index = slot
        context = {"analysis_text": analysis_text, "ontology": ontology}
        if role in {"pragmatics_critic", "judge"}:
            context["evidence_appraisal"] = parsed_roles.get(
                "evidence_appraisal", VERIFIER.fallback_evidence()
            )
        if role == "judge":
            context["pragmatics_critic"] = parsed_roles.get(
                "pragmatics_critic", VERIFIER.fallback_critic()
            )
        parsed = None
        error_code = None
        try:
            parsed = VALIDATOR.validate_output(role, raw_output, context)
        except VALIDATOR.AgentOutputError as exc:
            error_code = exc.code
        if system == "S3" and parsed is not None:
            parsed_roles[role] = parsed
        labels = (
            VALIDATOR.final_labels_from_validated(role, parsed)
            if parsed is not None and role in {"judge", "single_agent"}
            else []
        )
        abstained = VERIFIER.is_abstained(role, parsed)
        prefill = 200 if system == "S3" else 150
        calls.append(
            {
                "schema_version": "sqma-005-call-v1", "call_ordinal": call_ordinal,
                "row_ordinal": row_ordinal, "sample_id": row["sample_id"],
                "component_id": row["component_id"], "source_ordinal": row["source_ordinal"],
                "system_id": system, "role": role, "call_index": call_index,
                "seed": VERIFIER.seed_for("unit-seed", system, row["sample_id"], role, call_index),
                "analysis_text": analysis_text,
                "analysis_text_sha256": VERIFIER.text_sha256(analysis_text),
                "text_meta": deepcopy(text_meta),
                "context_sha256": VERIFIER.canonical_digest(context),
                "messages_sha256": VERIFIER.canonical_digest(
                    VERIFIER.expected_messages(BUNDLE, contracts, role, context)
                ),
                "prompt_ids_sha256": "a" * 64, "prefill_tokens": prefill,
                "max_new_tokens": VERIFIER.MAX_NEW_TOKENS[role], "finish_reason": "stop",
                "generated_tokens": 10, "latency_seconds": 0.25,
                "prompt_tps": 50.0, "generation_tps": 10.0,
                "mlx_peak_bytes": 1000 + call_ordinal,
                "raw_output_sha256": VERIFIER.text_sha256(raw_output), "raw_output": raw_output,
                "valid": parsed is not None, "error_code": error_code,
                "parsed_output": parsed, "final_labels": labels, "abstained": abstained,
                "token_cap_hit": False,
            }
        )
    return row, calls


def imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


class SQMA005VerifierTests(unittest.TestCase):
    def test_call_order_and_total_are_frozen(self) -> None:
        slots = VERIFIER.expected_call_slots()
        self.assertEqual(len(slots), 4032)
        self.assertEqual(
            slots[:6],
            [
                (0, 0, "S3", "evidence_appraisal", 0),
                (1, 0, "S3", "pragmatics_critic", 1),
                (2, 0, "S3", "judge", 2),
                (3, 0, "single_pool", "single_agent", 0),
                (4, 0, "single_pool", "single_agent", 1),
                (5, 0, "single_pool", "single_agent", 2),
            ],
        )
        self.assertIn("messages_sha256", VERIFIER.CALL_FIELDS)
        self.assertIn("analysis_text", VERIFIER.CALL_FIELDS)
        self.assertIn("text_meta", VERIFIER.CALL_FIELDS)
        self.assertIn("s2b_ceiling_utilization", VERIFIER.SYSTEM_ARRAYS)

    def test_classifier_free_systems_are_reconstructed(self) -> None:
        row, calls = make_calls()
        systems = VERIFIER.reconstruct_systems(
            calls, [row], VALIDATOR, BUNDLE, seed_namespace="unit-seed"
        )
        anger = [0, 0, 0, 1, 0, 0]
        self.assertEqual(systems["s1"], [anger])
        self.assertEqual(systems["s2a"], [anger])
        self.assertEqual(systems["s2b"], [anger])
        self.assertEqual(systems["s3"], [anger])
        self.assertEqual(systems["s2b_k"], [2])
        self.assertAlmostEqual(systems["s2b_ceiling_utilization"][0], 1068 / 1176)

    def test_invalid_upstream_role_uses_sentinel_and_forces_empty_s3(self) -> None:
        row, calls = make_calls(invalid_evidence=True)
        self.assertTrue(calls[2]["valid"], "Judge should still run on the frozen sentinel")
        systems = VERIFIER.reconstruct_systems(
            calls, [row], VALIDATOR, BUNDLE, seed_namespace="unit-seed"
        )
        self.assertEqual(systems["role_valid"], [[0, 1, 1]])
        self.assertEqual(systems["s3"], [[0, 0, 0, 0, 0, 0]])

    def test_replay_detects_text_context_and_token_cap_tampering(self) -> None:
        row, calls = make_calls()
        changed = deepcopy(calls)
        changed[0]["text_meta"]["analysis_sha256"] = "0" * 64
        with self.assertRaisesRegex(VERIFIER.VerificationError, "analysis text identity"):
            VERIFIER.reconstruct_systems(
                changed, [row], VALIDATOR, BUNDLE, seed_namespace="unit-seed"
            )

        changed = deepcopy(calls)
        changed[1]["messages_sha256"] = "0" * 64
        with self.assertRaisesRegex(VERIFIER.VerificationError, "messages digest"):
            VERIFIER.reconstruct_systems(
                changed, [row], VALIDATOR, BUNDLE, seed_namespace="unit-seed"
            )

        changed = deepcopy(calls)
        changed[0]["finish_reason"] = "length"
        changed[0]["token_cap_hit"] = True
        with self.assertRaisesRegex(VERIFIER.VerificationError, "semantic replay"):
            VERIFIER.reconstruct_systems(
                changed, [row], VALIDATOR, BUNDLE, seed_namespace="unit-seed"
            )

    def test_truncation_contract_marks_the_non_recomputed_bpe_boundary(self) -> None:
        row = input_row()
        record = {
            "analysis_text": "I am angry.",
            "analysis_text_sha256": VERIFIER.text_sha256("I am angry."),
            "text_meta": {
                "original_sha256": VERIFIER.text_sha256(row["text"]),
                "analysis_sha256": VERIFIER.text_sha256("I am angry."),
                "original_token_count": 1100, "analysis_token_count": 1024,
                "was_truncated": True, "model_free_truncation_replay": False,
            },
        }
        VERIFIER.validate_text_meta(record, row)
        record["text_meta"]["model_free_truncation_replay"] = True
        with self.assertRaisesRegex(VERIFIER.VerificationError, "truncation replay"):
            VERIFIER.validate_text_meta(record, row)

    def test_s2b_allocation_is_largest_whole_prefix_or_hard_failure(self) -> None:
        self.assertEqual(VERIFIER.choose_s2b_k(1176, 534), 2)
        self.assertEqual(VERIFIER.choose_s2b_k(1500, 500), 3)
        with self.assertRaisesRegex(VERIFIER.VerificationError, "no whole-call"):
            VERIFIER.choose_s2b_k(1000, 400)

    def test_independent_metrics_match_scorer(self) -> None:
        truth = [[1] * 6 for _ in range(4)]
        predictions = {
            "s1": [[0] * 6 for _ in range(4)],
            "s2a": truth,
            "s2b": [[0] * 6 for _ in range(4)],
            "s3": truth,
        }
        components = ["a", "a", "b", "c"]
        verified = VERIFIER.independent_score(truth, predictions, components, replicates=20)
        system_bootstrap, contrast_bootstrap = SCORER.component_bootstrap(
            truth, predictions, components, replicates=20
        )
        scorer_systems = {
            system: {
                "point": SCORER.metric_bundle(truth, predictions[system]),
                "bootstrap": system_bootstrap[system],
            }
            for system in SCORER.SYSTEMS
        }
        self.assertEqual(verified["systems"], scorer_systems)
        self.assertEqual(
            verified["contrasts"]["s3_minus_s2b"]["bootstrap"],
            contrast_bootstrap["s3_minus_s2b"],
        )

    def test_npz_schema_dtype_and_bits_are_exact(self) -> None:
        import numpy as np

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gold.npz"
            np.savez(
                path,
                sample_ids=np.asarray(["row-a"], dtype="<U5"),
                component_ids=np.asarray(["group-a"], dtype="<U7"),
                fold_ids=np.asarray([3], dtype=np.int8),
                source_ordinals=np.asarray([4], dtype=np.int32),
                gold=np.asarray([[0, 0, 0, 1, 0, 0]], dtype=np.uint8),
            )
            arrays = VERIFIER.load_npz(path, VERIFIER.GOLD_ARRAYS, 1)
            self.assertEqual(arrays["gold"].tolist(), [[0, 0, 0, 1, 0, 0]])
            np.savez(
                path,
                sample_ids=np.asarray(["row-a"], dtype="<U5"),
                component_ids=np.asarray(["group-a"], dtype="<U7"),
                fold_ids=np.asarray([3], dtype=np.int8),
                source_ordinals=np.asarray([4], dtype=np.int32),
                gold=np.asarray([[0, 0, 0, 2, 0, 0]], dtype=np.uint8),
            )
            with self.assertRaisesRegex(VERIFIER.VerificationError, "bit"):
                VERIFIER.load_npz(path, VERIFIER.GOLD_ARRAYS, 1)

    def test_manifest_run_cost_and_aggregate_replay(self) -> None:
        _, row_calls = make_calls()
        calls = [deepcopy(call) for _ in range(672) for call in row_calls]
        systems = {
            "s2b_k": [2] * 672,
            "s2b_ceiling_utilization": [1068 / 1176] * 672,
        }
        generated = sum(call["generated_tokens"] for call in calls)
        model = {"repo_id": "Qwen/Qwen3-4B", "revision": "frozen", "adapter": None}
        access = {
            "gold_accessed": False, "classifier_accessed": False,
            "adapter_loaded": False, "model_loaded": True, "training_executed": False,
            "optimizer_executed": False, "network_accessed": False,
            "validation_accessed": False, "test_accessed": False, "fold4_accessed": False,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_seal = root / "input-seal.json"
            calls_path = root / "calls.jsonl"
            systems_path = root / "systems.npz"
            input_seal.write_bytes(b"input-seal")
            calls_path.write_bytes(b"calls")
            systems_path.write_bytes(b"systems")

            def record(path: Path):
                return {
                    "path": path.name, "bytes": path.stat().st_size,
                    "sha256": VERIFIER.sha256(path),
                }

            manifest = {
                "schema_version": "sqma-005-private-manifest-v1",
                "experiment_id": "SQMA-005", "status": "SealedAwaitingScore",
                "input_seal": record(input_seal), "calls_artifact": record(calls_path),
                "systems_artifact": record(systems_path),
                "model_identity": model,
                "prompt_identities": {
                    "bundle_sha256": VERIFIER.sha256(BUNDLE_PATH),
                    "schema_sha256": VERIFIER.sha256(
                        PROJECT_ROOT / "schemas" / "agent-output-v2.schema.json"
                    ),
                    "validator_sha256": VERIFIER.sha256(VALIDATOR_PATH),
                },
                "call_plan": {
                    "rows": 672, "calls_per_row": 6, "physical_calls": 4032,
                    "single_pool_shared": True,
                },
                "aggregate_cost": {
                    "generated_tokens": generated, "s2b_k_counts": {"2": 672},
                },
                "access": access, "score_authorized": False,
                "next_gate": "independent_gold_consumer_scoring",
            }
            run = {
                "schema_version": "sqma-005-producer-run-v1", "experiment_id": "SQMA-005",
                "status": "CompletedAwaitingScore", "model": model, "access": access,
                "calls": {
                    "physical": 4032, "per_row": 6,
                    "system_accounted": {"S1": 672, "S2a": 2016, "S2b": 1344, "S3": 2016},
                },
                "aggregates": VERIFIER.recompute_aggregates(calls, systems),
                "resources": {
                    "generated_tokens": generated,
                    "mlx_peak_bytes": max(call["mlx_peak_bytes"] for call in calls),
                    "critical_memory_events": 0, "oom_or_kill_events": 0,
                    "orphan_processes_after_exit": 0,
                },
            }
            integrity = VERIFIER.validate_manifest_and_run(
                manifest, run, input_seal_path=input_seal, calls_path=calls_path,
                systems_path=systems_path, prompt_bundle_path=BUNDLE_PATH,
                output_schema_path=PROJECT_ROOT / "schemas" / "agent-output-v2.schema.json",
                validator_path=VALIDATOR_PATH, calls=calls, systems=systems,
            )
            self.assertEqual(integrity, {"schema": True, "budget": True, "resource": True})
            manifest["aggregate_cost"]["generated_tokens"] += 1
            with self.assertRaisesRegex(VERIFIER.VerificationError, "generated-token"):
                VERIFIER.validate_manifest_and_run(
                    manifest, run, input_seal_path=input_seal, calls_path=calls_path,
                    systems_path=systems_path, prompt_bundle_path=BUNDLE_PATH,
                    output_schema_path=PROJECT_ROOT / "schemas" / "agent-output-v2.schema.json",
                    validator_path=VALIDATOR_PATH, calls=calls, systems=systems,
                )

    def test_public_privacy_and_independence(self) -> None:
        self.assertFalse(VERIFIER.public_sensitive_paths({"rows": 672, "sha256": "a" * 64}))
        self.assertTrue(VERIFIER.public_sensitive_paths({"nested": {"raw_output": "secret"}}))
        roots = imported_roots(VERIFIER_PATH)
        self.assertFalse(roots & {"mlx", "mlx_lm", "torch", "transformers"})
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("run_sqma005_agent_tune_comparison", source)
        self.assertNotIn("score_sqma005_agent_tune_comparison", source)


if __name__ == "__main__":
    unittest.main()
