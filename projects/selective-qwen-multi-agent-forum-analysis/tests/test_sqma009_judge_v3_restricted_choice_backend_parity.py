#!/usr/bin/env python3

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = PROJECT_ROOT / "scripts" / "run_sqma009_judge_v3_restricted_choice_backend_parity.py"
VERIFIER_PATH = PROJECT_ROOT / "scripts" / "verify_sqma009_judge_v3_restricted_choice_backend_parity.py"
V5_PATH = PROJECT_ROOT / "scripts" / "validate_agent_output_v5.py"
CONFIG_PATH = PROJECT_ROOT / "configs" / "sqma-009-judge-v3-restricted-choice-backend-parity.json"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module); return module


RUNNER = load("sqma009_runner_test", RUNNER_PATH)
VERIFIER = load("sqma009_verifier_test", VERIFIER_PATH)
V5 = load("sqma009_v5_test", V5_PATH)


class FakeTokenizer:
    ids = {"A": 1, "B": 2, "C": 3, "D": 4}

    def encode(self, symbol, add_special_tokens=False):
        return [self.ids[symbol]]

    def decode(self, token_ids, skip_special_tokens=False):
        reverse = {value: key for key, value in self.ids.items()}
        return reverse[token_ids[0]]


def token_seal():
    return V5.build_token_seal(
        FakeTokenizer(), tokenizer_sha256="a" * 64,
        chat_template_sha256="b" * 64, eos_token_ids=[99],
    )


def replay_rows(ordinary=None):
    ordinary = [] if ordinary is None else ordinary
    evidence = {"schema_version": "evidence-v3", "candidate_emotions": ["joy"], "evidence_spans": ["happy"], "insufficient_evidence": False}
    critic = {"schema_version": "critic-v3", "recommended_emotions": ["joy"], "challenged_emotions": [], "warning_flags": []}
    return [
        {
            "row_ordinal": index, "selection_rank": index,
            "sample_id": f"row-{index}", "component_id": f"component-{index}",
            "source_ordinal": index, "analysis_text": "happy technical text",
            "evidence": evidence, "critic": critic, "allowed_evidence_ids": [0],
            "ordinary_v2_labels": list(ordinary),
        }
        for index in range(16)
    ]


def calls_for(rows, seal, choose_symbol="A"):
    mapping = V5.build_candidate_mapping([0], seal)
    token = next(item["token_id"] for item in mapping if item["symbol"] == choose_symbol)
    evidence_id = next(item["evidence_id"] for item in mapping if item["symbol"] == choose_symbol)
    calls = []
    for expected in RUNNER.planned_calls(rows):
        row = rows[expected["row_ordinal"]]
        context = RUNNER.judge_context(row, expected["target_label"], mapping, V5.ONTOLOGY)
        calls.append(
            {
                "schema_version": "sqma-009-call-v1", **expected,
                "analysis_text_sha256": RUNNER.text_sha256(row["analysis_text"]),
                "context_sha256": RUNNER.canonical_digest(context),
                "messages_sha256": "c" * 64, "prompt_ids_sha256": "d" * 64,
                "candidate_mapping": mapping,
                "allowed_token_ids": [item["token_id"] for item in mapping],
                "processor_instance_id": f"processor-{expected['call_ordinal']}",
                "processor_invocations": 2, "response_count": 1,
                "response_token": token, "generated_tokens": 1,
                "finish_reason": "length", "generated_text_sha256": "e" * 64,
                "selected_symbol": choose_symbol, "selected_evidence_id": evidence_id,
                "terminal_valid": True, "selected_token_allowed": True,
                "selected_eos_token": False, "post_mask_valid": True,
                "prefill_tokens": 100,
                "latency_seconds": 0.1, "mlx_peak_bytes": 1000,
            }
        )
    return calls


def import_roots(path: Path):
    roots = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import): roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module: roots.add(node.module.split(".", 1)[0])
    return roots


class SQMA009Tests(unittest.TestCase):
    def test_counting_processor_wraps_pure_mask(self) -> None:
        base = lambda tokens, logits: V5.python_mask_logits(logits, [1, 3])
        processor = RUNNER.build_counting_processor(base)
        self.assertEqual(processor([], [1.0, 2.0, 3.0, 4.0]), [-float("inf"), 2.0, -float("inf"), 4.0])
        processor([], [0.0] * 4)
        self.assertEqual(processor.invocations, 2)

    def test_token_seal_and_candidate_mapping(self) -> None:
        seal = token_seal(); V5.validate_token_seal(seal)
        mapping = V5.build_candidate_mapping([0, 1], seal)
        self.assertEqual([item["symbol"] for item in mapping], ["A", "B", "C"])
        self.assertEqual([item["evidence_id"] for item in mapping], [None, 0, 1])
        changed = json.loads(json.dumps(seal)); changed["symbols"][1]["token_id"] = changed["symbols"][0]["token_id"]
        with self.assertRaises(V5.AgentOutputError): V5.validate_token_seal(changed)

    def test_96_calls_use_fresh_processors_and_authoritative_tokens(self) -> None:
        seal = token_seal(); rows = replay_rows(); calls = calls_for(rows, seal)
        RUNNER.validate_calls(calls, rows, seal, V5)
        VERIFIER.validate_calls(calls, rows, seal, V5)
        self.assertEqual(len(calls), 96)
        self.assertEqual(len({call["processor_instance_id"] for call in calls}), 96)
        self.assertTrue(all(call["response_count"] == call["generated_tokens"] == 1 for call in calls))
        self.assertTrue(all(call["finish_reason"] == "length" for call in calls))

    def test_selected_token_must_be_allowed(self) -> None:
        seal = token_seal(); rows = replay_rows(); calls = calls_for(rows, seal)
        calls[0]["response_token"] = 99
        with self.assertRaises(V5.AgentOutputError): RUNNER.validate_calls(calls, rows, seal, V5)

    def test_assembly_and_report_only_parity(self) -> None:
        seal = token_seal(); rows = replay_rows(["joy"]); calls = calls_for(rows, seal, "A")
        assemblies = RUNNER.assemble_rows(calls, rows, seal, V5)
        metrics = RUNNER.technical_metrics(calls, assemblies)
        self.assertEqual(metrics, VERIFIER.technical_metrics(calls, assemblies))
        self.assertEqual(metrics["v2_v3_exact_label_set_parity_report_only"], 0.0)
        self.assertTrue(RUNNER.technical_gate(metrics))
        self.assertTrue(VERIFIER.technical_gate(metrics))

    def test_terminal_tampering_fails_gate_or_mapping(self) -> None:
        seal = token_seal(); rows = replay_rows(); calls = calls_for(rows, seal)
        calls[0]["finish_reason"] = "stop"
        with self.assertRaises(V5.AgentOutputError): VERIFIER.validate_calls(calls, rows, seal, V5)

    def test_processor_reuse_is_rejected(self) -> None:
        seal = token_seal(); rows = replay_rows(); calls = calls_for(rows, seal)
        calls[1]["processor_instance_id"] = calls[0]["processor_instance_id"]
        with self.assertRaises(RUNNER.SQMA009Error): RUNNER.validate_calls(calls, rows, seal, V5)

    def test_public_privacy(self) -> None:
        safe = {"calls": 96, "processor_invocations": 192, "parity_rate": 0.5}
        self.assertFalse(RUNNER.public_sensitive_paths(safe))
        self.assertTrue(RUNNER.public_sensitive_paths({"response_token": 1}))

    def test_pass_only_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            VERIFIER.write_pass_only(root, {"status": "Passed"}, {"sqma009_complete": True})
            self.assertTrue((root / "verification.json").is_file())
            self.assertTrue((root / "complete.json").is_file())
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(VERIFIER.SQMA009VerificationError):
                VERIFIER.write_pass_only(Path(directory), {"status": "Failed"}, {"sqma009_complete": True})

    def test_config_pinning_activates_when_config_exists(self) -> None:
        if not CONFIG_PATH.exists():
            self.skipTest("SQMA-009 config not registered yet")
        config = json.loads(CONFIG_PATH.read_text())
        RUNNER.validate_static_config(config); VERIFIER.validate_static_config(config)
        self.assertEqual(config["generation"]["physical_calls"], 96)
        self.assertEqual(config["outputs"]["private_allowed_files"], RUNNER.PRIVATE_ALLOWED)

    def test_verifier_is_model_and_runner_independent(self) -> None:
        roots = import_roots(VERIFIER_PATH)
        self.assertFalse(roots & {"mlx", "mlx_lm", "torch", "transformers"})
        self.assertNotIn("import run_sqma009_judge_v3_restricted_choice_backend_parity", VERIFIER_PATH.read_text())


if __name__ == "__main__":
    unittest.main()
