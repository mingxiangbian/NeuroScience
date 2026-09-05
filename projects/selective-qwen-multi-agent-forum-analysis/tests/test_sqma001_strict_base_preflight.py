from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
CONFIG_PATH = PROJECT_ROOT / "configs" / "sqma-001-strict-base-readiness-preflight.json"
sys.path.insert(0, str(SCRIPTS_ROOT))

import strict_base_contract as contract  # noqa: E402
import run_sqma001_strict_base_preflight as runner  # noqa: E402
import verify_sqma001_strict_base_preflight as verifier  # noqa: E402


FORBIDDEN_MODEL_IMPORTS = {"mlx", "mlx_lm", "numpy", "torch", "transformers"}


def load_config() -> dict[str, object]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def registered_config() -> dict[str, object]:
    value = load_config()
    for section in ("implementation", "prerequisites"):
        for record in value[section].values():
            if record["sha256"] == "TO_BE_REGISTERED":
                record["sha256"] = "0" * 64
                record["bytes"] = 1
    return value


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


class Sqma001StrictBasePreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.original_contract = runner.contract
        runner.contract = contract

    @classmethod
    def tearDownClass(cls) -> None:
        runner.contract = cls.original_contract

    def test_authorization_drift_is_rejected_by_runner_and_verifier(self) -> None:
        changed = registered_config()
        changed["authorization"]["training"] = True
        with self.assertRaisesRegex(runner.PreflightError, "authorization drift"):
            runner.validate_preimport_config(changed)
        with self.assertRaisesRegex(verifier.VerificationError, "authorization drift"):
            verifier.validate_config(changed, contract)

    def test_fold4_overlap_wildcard_and_plan_order_drift_are_rejected(self) -> None:
        base = load_config()["data"]["full_fit_plan"]

        fold4 = deepcopy(base)
        fold4[0]["train_folds"] = [1, 2, 4]
        with self.assertRaisesRegex(runner.PreflightError, "forbidden fold 4"):
            runner.parse_fit_plan(fold4)

        overlap = deepcopy(base)
        overlap[0]["train_folds"] = [0, 1, 2]
        with self.assertRaisesRegex(runner.PreflightError, "overlap"):
            runner.parse_fit_plan(overlap)

        wildcard = deepcopy(base)
        wildcard[0]["train_folds"] = [1, "*"]
        with self.assertRaisesRegex(runner.PreflightError, "invalid fold type"):
            runner.parse_fit_plan(wildcard)

        reordered = list(reversed(deepcopy(base)))
        with self.assertRaisesRegex(runner.PreflightError, "order"):
            runner.parse_fit_plan(reordered)

    def test_existing_empty_nonempty_and_symlink_output_targets_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            runs = repo / "runs"
            runs.mkdir()

            empty = runs / "empty"
            empty.mkdir()
            with self.assertRaisesRegex(runner.PreflightError, "already exists"):
                runner.validate_output_target(repo, empty, 0)

            nonempty = runs / "nonempty"
            nonempty.mkdir()
            (nonempty / "run.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(runner.PreflightError, "already exists"):
                runner.validate_output_target(repo, nonempty, 0)

            real = runs / "real"
            real.mkdir()
            symlink = runs / "attempt-link"
            symlink.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(runner.PreflightError, "already exists"):
                runner.validate_output_target(repo, symlink, 0)

            ancestor_link = runs / "ancestor-link"
            ancestor_link.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(runner.PreflightError, "symlink"):
                runner.validate_output_target(repo, ancestor_link / "attempt", 0)

    def test_missing_output_target_under_regular_ancestor_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            runs = repo / "runs"
            runs.mkdir()
            observed = runner.validate_output_target(repo, runs / "attempt", 0)
            self.assertGreaterEqual(observed, 0)
            self.assertFalse((runs / "attempt").exists())

    def test_private_source_access_flag_drift_is_rejected(self) -> None:
        for field, drift in (
            ("paths_resolved_or_opened", True),
            ("bytes_hashed_by_sqma001", True),
            ("rows_parsed", True),
            ("identity_source", "opened_private_source"),
            ("next_gate", "formal_training"),
        ):
            with self.subTest(field=field):
                changed = registered_config()
                changed["private_source_contract"][field] = drift
                with self.assertRaisesRegex(runner.PreflightError, "private source"):
                    runner.validate_config_contract(changed)

    def test_heldout_gold_and_first_stage_fold_drift_are_rejected(self) -> None:
        heldout_gold = registered_config()
        heldout_gold["snapshot_contract"]["heldout_logits_contains_gold"] = True
        with self.assertRaisesRegex(runner.PreflightError, "heldout gold"):
            runner.validate_config_contract(heldout_gold)
        with self.assertRaisesRegex(verifier.VerificationError, "heldout gold"):
            verifier.validate_config(heldout_gold, contract)

        leaked_fold = registered_config()
        leaked_fold["snapshot_contract"]["first_stage_output_folds"] = [0, 1, 2, 3]
        with self.assertRaisesRegex(runner.PreflightError, "snapshot fold drift"):
            runner.validate_config_contract(leaked_fold)

    def test_public_sensitive_values_are_rejected(self) -> None:
        sensitive_values = (
            {"sample_ids": ["sample-secret"]},
            {"nested": {"component_id": "component-secret"}},
            {"nested": {"gold": [[1, 0, 0, 0, 0, 0]]}},
            {"nested": {"logits": [0.1]}} ,
            {"safe_key": "sample-secret"},
        )
        for value in sensitive_values:
            with self.subTest(value=value):
                with self.assertRaises(contract.ContractError):
                    contract.assert_public_safe(value)
                self.assertTrue(verifier.sensitive_paths(value))

    def test_runner_verifier_and_contract_ast_have_no_model_framework_imports(self) -> None:
        paths = (
            SCRIPTS_ROOT / "strict_base_contract.py",
            SCRIPTS_ROOT / "run_sqma001_strict_base_preflight.py",
            SCRIPTS_ROOT / "verify_sqma001_strict_base_preflight.py",
        )
        for path in paths:
            with self.subTest(path=path.name):
                self.assertFalse(imported_roots(path) & FORBIDDEN_MODEL_IMPORTS)

    def test_verifier_ast_does_not_import_runner(self) -> None:
        roots = imported_roots(SCRIPTS_ROOT / "verify_sqma001_strict_base_preflight.py")
        self.assertNotIn("run_sqma001_strict_base_preflight", roots)

    def test_artifact_record_requires_exact_path_and_registered_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary).resolve()
            artifact = repo / "artifact.txt"
            artifact.write_text("frozen", encoding="utf-8")
            record = {
                "path": "artifact.txt",
                "bytes": artifact.stat().st_size,
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            }
            self.assertEqual(
                runner.validate_artifact_record(repo, "fixture", record, "artifact.txt"),
                record,
            )

            wrong_path = dict(record, path="other.txt")
            with self.assertRaisesRegex(runner.PreflightError, "path drift"):
                runner.validate_artifact_record(repo, "fixture", wrong_path, "artifact.txt")

            placeholder = dict(record, sha256="TO_BE_REGISTERED")
            with self.assertRaisesRegex(runner.PreflightError, "SHA-256"):
                runner.validate_artifact_record(repo, "fixture", placeholder, "artifact.txt")

    def test_verifier_rejects_registered_config_placeholders(self) -> None:
        changed = registered_config()
        changed["implementation"]["runner"]["bytes"] = 0
        changed["implementation"]["runner"]["sha256"] = "TO_BE_REGISTERED"
        with self.assertRaisesRegex(verifier.VerificationError, "unregistered source"):
            verifier.validate_config(changed, contract)


if __name__ == "__main__":
    unittest.main()
