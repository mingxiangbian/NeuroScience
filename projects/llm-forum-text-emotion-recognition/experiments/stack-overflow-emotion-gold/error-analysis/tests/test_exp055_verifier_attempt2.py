from __future__ import annotations

import ast
import hashlib
import json
import re
import unittest
from pathlib import Path


ERROR_ANALYSIS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[6]
AUTHORIZATION = (
    ERROR_ANALYSIS_DIR
    / "configs"
    / "exp-055-verification-attempt-2.json"
)
RUN_DIR = (
    ERROR_ANALYSIS_DIR
    / "runs"
    / "exp-055-m1-m3-validation-error-analysis"
)


class Attempt2VerifierTests(unittest.TestCase):
    def test_authorization_binds_base_config_verifier_and_amendment(self) -> None:
        authorization = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
        self.assertEqual(authorization["verification_attempt"], 2)
        self.assertEqual(
            authorization["permitted_correction"],
            "report_whitespace_normalization_only",
        )
        self.assertIs(authorization["scientific_artifact_changes_authorized"], False)
        for name in ("base_config", "verifier", "amendment"):
            record = authorization[name]
            path = REPO_ROOT / record["path"]
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.stat().st_size, record["bytes"], path)
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"], path
            )

    def test_attempt2_remains_independent(self) -> None:
        source = (ERROR_ANALYSIS_DIR / "verify_exp055_attempt2.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertNotIn("analyze_exp055", imported)
        self.assertNotIn("finalize_exp055", imported)

    def test_only_whitespace_normalization_is_needed_for_report_boundary(self) -> None:
        report = (RUN_DIR / "REPORT.md").read_text(encoding="utf-8")
        self.assertNotIn("access test", report)
        normalized = re.sub(r"\s+", " ", report)
        self.assertIn("did not", normalized)
        self.assertIn("access test", normalized)


if __name__ == "__main__":
    unittest.main()
