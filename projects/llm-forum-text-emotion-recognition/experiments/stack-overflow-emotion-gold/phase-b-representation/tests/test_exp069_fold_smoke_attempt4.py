from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp069_fold_smoke_attempt4.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp069_fold_smoke_attempt4.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load("exp069_attempt4_runner_tests", RUNNER_PATH)
VERIFIER = load("exp069_attempt4_verifier_tests", VERIFIER_PATH)


class Exp069FoldSmokeAttempt4Tests(unittest.TestCase):
    def test_scope_is_fold_and_assemble_only(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        self.assertEqual(
            config["scope"],
            {"base_smoke": False, "fold_smoke": True, "assemble": True, "exp070": False},
        )
        self.assertTrue(config["authorization"]["smoke_execution_authorized"])
        self.assertFalse(config["authorization"]["training_authorized"])
        self.assertFalse(config["authorization"]["validation_access"])
        self.assertFalse(config["authorization"]["test_access"])

    def test_parent_static_and_base_are_verified(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        RUNNER.require_records(config)
        base = RUNNER.strict_json(RUNNER.require_record(config["parent_base"]["completion"]))
        static = RUNNER.strict_json(
            RUNNER.require_record(config["parent_static"]["static_verification"])
        )
        self.assertEqual(base["status"], "Complete")
        self.assertTrue(base["base_smoke_complete"])
        self.assertFalse(base["exp069_complete"])
        self.assertEqual(static["status"], "Passed")
        self.assertEqual(static["passed_count"], 14)

    def test_continuation_view_preserves_scientific_contract(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        parent = RUNNER.strict_json(RUNNER.require_record(config["parent_static"]["config"]))
        view = RUNNER.continuation_view(config, parent)
        for key in ("data", "model", "m2_cache", "m3_lineage"):
            self.assertEqual(view[key], parent[key])
        self.assertEqual(view["attempt_id"], "attempt-4-fold-smoke")
        self.assertEqual(view["outputs"]["public_root"], config["outputs"]["public_root"])
        self.assertEqual(view["outputs"]["private_root"], config["outputs"]["private_root"])
        self.assertEqual(view["outputs"]["heavy_lock"], parent["outputs"]["heavy_lock"])

    def test_worker_order_is_exact(self) -> None:
        self.assertEqual(
            [(seed, fold) for seed in RUNNER.SEEDS for fold in RUNNER.FOLDS],
            [(seed, fold) for seed in (42, 43, 44) for fold in range(5)],
        )

    def test_atomic_copy_preserves_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            target = root / "target"
            source.write_bytes(b"frozen")
            RUNNER.atomic_copy(source, target, mode=0o600)
            self.assertEqual(target.read_bytes(), b"frozen")
            self.assertEqual(os.stat(target).st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                RUNNER.atomic_copy(source, target, mode=0o600)

    def test_future_seed_symlink_is_rejected_before_worker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / "public"
            private = root / "private"
            target = root / "outside"
            public.mkdir()
            private.mkdir(mode=0o700)
            target.mkdir()
            for name in ("static.json", "static-verification.json", "run-claim.json"):
                (public / name).write_text("{}", encoding="utf-8")
            for name in ("input-manifest.json", "base.npz", "base-worker.json"):
                (private / name).write_text("frozen", encoding="utf-8")
            (private / "seed-42").symlink_to(target, target_is_directory=True)

            class Source:
                @staticmethod
                def public_root(_view):
                    return public

                @staticmethod
                def private_root(_view):
                    return private

            with self.assertRaises(PermissionError):
                RUNNER.completed_prefix({}, Source(), {})

    def test_verifier_wrapper_has_no_model_imports(self) -> None:
        tree = ast.parse(VERIFIER_PATH.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertFalse({"mlx", "mlx_lm", "torch", "transformers", "safetensors"} & imports)

    def test_output_root_contract_is_fixed(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        self.assertEqual(config["outputs"]["public_root"], RUNNER.PUBLIC_ROOT)
        self.assertEqual(config["outputs"]["private_root"], RUNNER.PRIVATE_ROOT)
        self.assertNotEqual(
            config["outputs"]["public_root"],
            config["parent_base"]["run"]["path"].rsplit("/", 1)[0],
        )


if __name__ == "__main__":
    unittest.main()
