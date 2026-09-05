#!/usr/bin/env python3

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCORER_PATH = PROJECT_ROOT / "scripts" / "score_sqma005_agent_tune_comparison.py"
SPEC = importlib.util.spec_from_file_location("sqma005_scorer_for_tests", SCORER_PATH)
assert SPEC is not None and SPEC.loader is not None
SCORER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SCORER
SPEC.loader.exec_module(SCORER)


def payloads(rows: int = 6):
    sample_ids = [f"row-{index}" for index in range(rows)]
    component_ids = [f"group-{index // 2}" for index in range(rows)]
    fold_ids = [3] * rows
    ordinals = list(range(rows))
    truth = [[1] * 6 for _ in range(rows)]
    empty = [[0] * 6 for _ in range(rows)]
    gold = {
        "sample_ids": sample_ids,
        "component_ids": component_ids,
        "fold_ids": fold_ids,
        "source_ordinals": ordinals,
        "gold": truth,
    }
    systems = {
        "sample_ids": sample_ids,
        "component_ids": component_ids,
        "fold_ids": fold_ids,
        "source_ordinals": ordinals,
        "s1": empty,
        "s2a": truth,
        "s2b": empty,
        "s3": truth,
        "single_valid": [[1, 1, 1] for _ in range(rows)],
        "role_valid": [[1, 1, 1] for _ in range(rows)],
        "single_abstained": [[0, 0, 0] for _ in range(rows)],
        "judge_abstained": [0] * rows,
        "s2b_k": [2] * rows,
        "s3_ceiling_tokens": [1000] * rows,
        "s2b_ceiling_tokens": [900] * rows,
        "s2b_ceiling_utilization": [0.9] * rows,
        "s3_actual_tokens": [700] * rows,
        "s2b_actual_tokens": [600] * rows,
    }
    return gold, systems


def imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


class SQMA005ScorerTests(unittest.TestCase):
    def test_metrics_bootstrap_and_registered_gate(self) -> None:
        gold, systems = payloads()
        result = SCORER.score_payloads(gold, systems, expected_rows=6, replicates=40)
        self.assertEqual(result["systems"]["s3"]["point"]["six_label_macro_f1"], 1.0)
        self.assertEqual(result["systems"]["s2b"]["point"]["six_label_macro_f1"], 0.0)
        self.assertEqual(result["systems"]["s3"]["point"]["hamming_loss"], 0.0)
        self.assertEqual(set(result["systems"]["s3"]["point"]["per_label"]), set(SCORER.LABEL_ORDER))
        self.assertEqual(result["contrasts"]["s3_minus_s2b"]["bootstrap"]["six_label_macro_f1"]["q05"], 1.0)
        self.assertTrue(result["tune_gate"]["passed"])

    def test_bootstrap_is_component_paired_and_deterministic(self) -> None:
        gold, systems = payloads()
        first = SCORER.score_payloads(gold, systems, expected_rows=6, replicates=25, seed=17)
        second = SCORER.score_payloads(gold, systems, expected_rows=6, replicates=25, seed=17)
        self.assertEqual(first["systems"], second["systems"])
        self.assertEqual(first["contrasts"], second["contrasts"])
        self.assertEqual(first["bootstrap"]["unit"], "duplicate_component_id")
        self.assertTrue(first["bootstrap"]["paired_multiplicities"])

    def test_payload_contract_rejects_leak_identity_and_budget_drift(self) -> None:
        gold, systems = payloads()
        leaked = dict(systems)
        leaked["gold"] = gold["gold"]
        with self.assertRaisesRegex(SCORER.ScoringError, "inventory"):
            SCORER.validate_payloads(gold, leaked, expected_rows=6)

        misordered = {**systems, "source_ordinals": [0, 2, 1, 3, 4, 5]}
        with self.assertRaisesRegex(SCORER.ScoringError, "identity|order"):
            SCORER.validate_payloads(gold, misordered, expected_rows=6)

        bad_utilization = {**systems, "s2b_ceiling_utilization": [0.8] * 6}
        with self.assertRaisesRegex(SCORER.ScoringError, "utilization"):
            SCORER.validate_payloads(gold, bad_utilization, expected_rows=6)

    def test_seal_must_match_actual_sealed_runner_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            systems_path = Path(directory) / "systems.npz"
            systems_path.write_bytes(b"sealed-systems")
            record = {
                "path": "systems.npz",
                "bytes": systems_path.stat().st_size,
                "sha256": SCORER.sha256(systems_path),
            }
            manifest = {
                "schema_version": "sqma-005-private-manifest-v1",
                "experiment_id": "SQMA-005",
                "status": "SealedAwaitingScore",
                "score_authorized": False,
                "next_gate": "independent_gold_consumer_scoring",
                "systems_artifact": record,
                "call_plan": {
                    "rows": 672, "calls_per_row": 6, "physical_calls": 4032,
                    "single_pool_shared": True,
                },
                "aggregate_cost": {"generated_tokens": 10},
                "access": {
                    "gold_accessed": False, "classifier_accessed": False,
                    "adapter_loaded": False, "training_executed": False,
                    "optimizer_executed": False, "network_accessed": False,
                    "validation_accessed": False, "test_accessed": False,
                    "fold4_accessed": False,
                },
            }
            run = {
                "schema_version": "sqma-005-producer-run-v1",
                "experiment_id": "SQMA-005", "status": "CompletedAwaitingScore",
                "calls": {"physical": 4032, "per_row": 6},
                "outputs": {"systems": {**record, "mode": "0600", "gold_present": False}},
                "resources": {
                    "generated_tokens": 10, "critical_memory_events": 0,
                    "oom_or_kill_events": 0, "orphan_processes_after_exit": 0,
                },
            }
            self.assertEqual(
                SCORER.validate_producer_seal(manifest, run, systems_path),
                {"schema": True, "budget": True, "resource": True},
            )
            manifest["status"] = "Running"
            with self.assertRaisesRegex(SCORER.ScoringError, "not sealed"):
                SCORER.validate_producer_seal(manifest, run, systems_path)

    def test_public_score_has_no_row_level_material(self) -> None:
        gold, systems = payloads()
        result = SCORER.score_payloads(gold, systems, expected_rows=6, replicates=5)
        self.assertFalse(SCORER.public_sensitive_paths(result))
        self.assertTrue(SCORER.public_sensitive_paths({"nested": {"gold": [[1] * 6]}}))

    def test_scorer_import_is_model_free_and_does_not_import_producer(self) -> None:
        roots = imported_roots(SCORER_PATH)
        self.assertFalse(roots & {"mlx", "mlx_lm", "torch", "transformers"})
        self.assertNotIn("run_sqma005_agent_tune_comparison", SCORER_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
