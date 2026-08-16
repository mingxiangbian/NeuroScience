#!/usr/bin/env python3
"""Focused regression tests for EXP-053 verification attempt 2."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_verifier():
    path = ROOT / "verify_exp053_m3_attempt2.py"
    spec = importlib.util.spec_from_file_location("exp053_verifier_attempt2_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verifier = load_verifier()


class VerificationAttempt2Tests(unittest.TestCase):
    def test_actual_verification_schema_passes(self) -> None:
        result = {
            "status": "Passed",
            "check_count": 2,
            "checks": [{"passed": True}, {"passed": True}],
            "failed_checks": [],
        }
        self.assertTrue(verifier.passed_verification(result, 2))

    def test_legacy_or_inconsistent_schema_fails(self) -> None:
        valid = {
            "status": "Passed",
            "check_count": 2,
            "checks": [{"passed": True}, {"passed": True}],
            "failed_checks": [],
        }
        variants = [
            {**valid, "status": "Failed"},
            {**valid, "check_count": 1},
            {**valid, "checks": [{"passed": True}]},
            {**valid, "failed_checks": ["failed"]},
            {"status": "Passed", "checks_passed": 2, "failed_checks": []},
        ]
        self.assertTrue(all(not verifier.passed_verification(item, 2) for item in variants))

    def test_attempt2_uses_append_only_output_names(self) -> None:
        source = (ROOT / "verify_exp053_m3_attempt2.py").read_text(encoding="utf-8")
        self.assertIn('correction["output_filename"]', source)
        self.assertIn('correction["summary_filename"]', source)
        self.assertNotIn('run_dir / "verification.json"', source)


if __name__ == "__main__":
    unittest.main()
