from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp063_router_replication_synthesis.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp063_router_replication_synthesis.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load("exp063_runner_tests", RUNNER_PATH)
VERIFIER = load("exp063_verifier_tests", VERIFIER_PATH)


class Exp063SynthesisTests(unittest.TestCase):
    def test_independent_recomputation_is_exact(self) -> None:
        observed = RUNNER.compute_synthesis()
        expected = VERIFIER.compute_expected()
        self.assertTrue(VERIFIER._typed_equal(observed, expected))

    def test_frozen_two_vote_decision(self) -> None:
        value = RUNNER.compute_synthesis()
        self.assertEqual([row["model_seed"] for row in value["votes"]], [43, 44])
        self.assertTrue(all(row["primary_gate_passed"] for row in value["votes"]))
        self.assertEqual(value["decision"]["pass_count"], 2)
        self.assertEqual(value["decision"]["result"], "2/2 pass")
        self.assertFalse(value["discovery_background"]["vote_eligible"])

    def test_public_aggregate_privacy_boundary(self) -> None:
        value = RUNNER.compute_synthesis()
        self.assertFalse(VERIFIER._privacy(value))
        self.assertTrue(value["execution_claims"]["aggregate_public_only"])
        self.assertFalse(value["execution_claims"]["private_accessed"])
        with self.assertRaises(PermissionError):
            RUNNER._resolve_public(Path("experiments/private/rows.json"))
        with self.assertRaises(PermissionError):
            VERIFIER._resolve_public(Path("experiments/test/results.json"))

    def test_verifier_does_not_import_runner(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import run_exp063", source)
        self.assertNotIn("from run_exp063", source)


if __name__ == "__main__":
    unittest.main()

