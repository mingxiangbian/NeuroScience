from __future__ import annotations

import ast
from copy import deepcopy
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"
CONFIG = PROJECT_ROOT / "configs" / "sqma-002-dev-scoped-input-materialization.json"
sys.path.insert(0, str(SCRIPTS))

import scoped_input_contract as contract  # noqa: E402
import run_sqma002_scoped_input as runner  # noqa: E402
import verify_sqma002_scoped_input as verifier  # noqa: E402


FORBIDDEN_IMPORTS = {"mlx", "mlx_lm", "torch", "transformers"}


def config_value() -> dict[str, object]:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def registered_config() -> dict[str, object]:
    value = config_value()
    for record in value["implementation"].values():
        if record["sha256"] == "TO_BE_REGISTERED":
            record["sha256"] = "0" * 64
            record["bytes"] = 1
    return value


def import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


class Sqma002IntegrationContractTests(unittest.TestCase):
    def test_registered_config_contract_passes_without_opening_sources(self) -> None:
        value = registered_config()
        runner.validate_config(value, contract)
        verifier.validate_config(value, contract)

    def test_authorization_and_decode_scope_drift_fail_closed(self) -> None:
        for field, drift in (
            ("model_loading", True),
            ("training", True),
            ("decode_private_rows_for_fold3", True),
            ("decode_private_rows_for_fold4", True),
        ):
            with self.subTest(field=field):
                changed = registered_config()
                changed["authorization"][field] = drift
                with self.assertRaises((runner.MaterializationError, verifier.VerificationError)):
                    runner.validate_config(changed, contract)

    def test_fold3_fold4_output_and_gold_free_drift_are_rejected(self) -> None:
        leaked = registered_config()
        leaked["folds"]["fold3_output_rows"] = 1
        with self.assertRaises(runner.MaterializationError):
            runner.validate_config(leaked, contract)
        leaked = registered_config()
        leaked["snapshot_contract"]["scopes"].append("fold-4")
        with self.assertRaises(runner.MaterializationError):
            runner.validate_config(leaked, contract)

    def test_output_target_existing_and_symlink_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            public = root / "runs" / "attempt-1"
            private = root / "private" / "attempt-1"
            public.parent.mkdir()
            private.parent.mkdir()
            public.mkdir()
            with self.assertRaises(runner.MaterializationError):
                runner.validate_output_targets(root, public, private, 0)
            public.rmdir()
            target = root / "target"
            target.mkdir()
            private.symlink_to(target, target_is_directory=True)
            with self.assertRaises(runner.MaterializationError):
                runner.validate_output_targets(root, public, private, 0)

    def test_private_source_mode_and_symlink_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.jsonl"
            source.write_text("{}\n", encoding="utf-8")
            source.chmod(0o644)
            with self.assertRaises(runner.MaterializationError):
                runner.require_regular_source(source, "fixture", mode="0600")
            source.chmod(0o600)
            runner.require_regular_source(source, "fixture", mode="0600")
            link = root / "link.jsonl"
            link.symlink_to(source)
            with self.assertRaises(runner.MaterializationError):
                runner.require_regular_source(link, "fixture", mode="0600")

    def test_private_inventory_rejects_extra_and_wrong_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            expected = ["fold-0/train-capable.jsonl"]
            fold = root / "fold-0"
            fold.mkdir(mode=0o700)
            item = fold / "train-capable.jsonl"
            item.write_text("{}\n", encoding="utf-8")
            item.chmod(0o600)
            self.assertGreater(runner.verify_private_inventory(root, expected), 0)
            extra = root / "temp.tmp"
            extra.write_text("x", encoding="utf-8")
            extra.chmod(0o600)
            with self.assertRaises(runner.MaterializationError):
                runner.verify_private_inventory(root, expected)

    def test_public_privacy_rejects_ids_text_gold_and_private_path(self) -> None:
        private_path = "/secret/private/snapshot.jsonl"
        for value in (
            {"sample_ids": ["sample-secret"]},
            {"nested": {"text": "secret"}},
            {"nested": {"gold": [[1, 0, 0, 0, 0, 0]]}},
            {"path": private_path},
        ):
            with self.subTest(value=value):
                with self.assertRaises((contract.ContractError, verifier.VerificationError)):
                    verifier.public_safe(contract, value, private_path)

    def test_duplicate_json_keys_are_rejected_by_verifier(self) -> None:
        with self.assertRaises(verifier.VerificationError):
            verifier.decode_json('{"a":1,"a":2}', "fixture")

    def test_runner_verifier_ast_has_no_model_framework_import_and_verifier_no_runner(self) -> None:
        runner_roots = import_roots(SCRIPTS / "run_sqma002_scoped_input.py")
        verifier_roots = import_roots(SCRIPTS / "verify_sqma002_scoped_input.py")
        self.assertFalse(runner_roots & FORBIDDEN_IMPORTS)
        self.assertFalse(verifier_roots & FORBIDDEN_IMPORTS)
        self.assertNotIn("run_sqma002_scoped_input", verifier_roots)

    def test_verifier_rejects_unregistered_implementation(self) -> None:
        changed = registered_config()
        changed["implementation"]["verifier"] = {
            "path": changed["implementation"]["verifier"]["path"],
            "bytes": 0,
            "sha256": "TO_BE_REGISTERED",
        }
        with self.assertRaises(verifier.VerificationError):
            verifier.validate_file_records(Path(__file__).resolve().parents[3], changed)


if __name__ == "__main__":
    unittest.main()
