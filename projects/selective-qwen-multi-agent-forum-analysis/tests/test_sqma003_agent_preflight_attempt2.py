#!/usr/bin/env python3

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WRAPPER_PATH = PROJECT_ROOT / "scripts/verify_sqma003_agent_preflight_attempt2.py"


def load_wrapper():
    name = "sqma003_attempt2_verifier_wrapper_for_tests"
    spec = importlib.util.spec_from_file_location(name, WRAPPER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


WRAPPER = load_wrapper()


def import_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


class Sqma003Attempt2VerifierTests(unittest.TestCase):
    def test_all_mutable_identities_are_fixed_to_attempt2(self) -> None:
        self.assertEqual(
            WRAPPER.ATTEMPT2_CONFIG.name,
            "sqma-003-classifier-free-agent-preflight-attempt-2.json",
        )
        self.assertTrue(WRAPPER.ATTEMPT2_PUBLIC_RELATIVE.endswith("/attempt-2"))
        self.assertTrue(WRAPPER.ATTEMPT2_PRIVATE_RELATIVE.endswith("/attempt-2"))
        self.assertIn("attempt2.py", WRAPPER.ATTEMPT2_RUNNER_RELATIVE)
        self.assertIn("attempt2.py", WRAPPER.ATTEMPT2_VERIFIER_RELATIVE)
        self.assertTrue(WRAPPER.ATTEMPT2_PROMPT_RELATIVE.endswith("agent-bundle-v2-classifier-free.json"))

    def test_wrapper_imports_neither_runner_nor_model_framework(self) -> None:
        roots = import_roots(WRAPPER_PATH)
        self.assertNotIn("run_sqma003_agent_preflight", roots)
        self.assertNotIn("run_sqma003_agent_preflight_attempt2", roots)
        self.assertFalse(roots & {"mlx", "mlx_lm", "torch", "transformers"})

    def test_attempt1_private_namespace_is_absent(self) -> None:
        source = WRAPPER_PATH.read_text(encoding="utf-8")
        forbidden = "/private/" + "sqma-003-classifier-free-agent-preflight/" + "attempt-1"
        self.assertNotIn(forbidden, source)
        self.assertNotIn("calls.jsonl", source)
        self.assertNotIn("selection.json", source)

    def test_base_verifier_is_hash_pinned_and_model_free(self) -> None:
        self.assertEqual(len(WRAPPER.BASE_VERIFIER_SHA256), 64)
        self.assertEqual(WRAPPER.sha256(WRAPPER.BASE_VERIFIER), WRAPPER.BASE_VERIFIER_SHA256)
        roots = import_roots(WRAPPER.BASE_VERIFIER)
        self.assertNotIn("run_sqma003_agent_preflight", roots)
        self.assertFalse(roots & {"mlx", "mlx_lm", "torch", "transformers"})

    def test_missing_attempt2_config_fails_without_opening_private_output(self) -> None:
        if WRAPPER.ATTEMPT2_CONFIG.exists():
            self.skipTest("attempt-2 config is now present")
        with self.assertRaises(WRAPPER.Attempt2VerificationError):
            WRAPPER.validate_attempt2_config(WRAPPER.ATTEMPT2_CONFIG)


if __name__ == "__main__":
    unittest.main()
