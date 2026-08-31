from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp069_base_smoke_attempt3.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp069_base_smoke_attempt3.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load("exp069_attempt3_runner_tests", RUNNER_PATH)
VERIFIER = load("exp069_attempt3_verifier_tests", VERIFIER_PATH)


class Exp069BaseSmokeAttempt3Tests(unittest.TestCase):
    def test_config_is_base_only(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        self.assertTrue(config["authorization"]["base_smoke_authorized"])
        self.assertFalse(config["authorization"]["fold_smoke_authorized"])
        self.assertFalse(config["authorization"]["assemble_authorized"])
        self.assertFalse(config["authorization"]["training_authorized"])
        self.assertFalse(config["authorization"]["validation_access"])
        self.assertFalse(config["authorization"]["test_access"])

    def test_attempt2_failure_lineage_is_exact(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        consumer, _ = RUNNER.require_inputs(config)
        self.assertEqual(consumer.ATTEMPT_ID, "attempt-2-base-smoke")
        failure = RUNNER.strict_json(
            RUNNER.require_record(config["parent_failure"]["run"])
        )
        self.assertEqual(failure["status"], "Failed")
        self.assertEqual(failure["error_type"], "FileNotFoundError")

    def test_directory_adapter_is_exactly_scoped(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        consumer, source_config = RUNNER.require_inputs(config)
        source = consumer.load_source_runner(source_config)
        parent = source.strict_json(source.require_record(source_config["parent_static"]["config"]))
        base_relative = parent["model"]["base_path"]
        with self.assertRaises(FileNotFoundError):
            source.resolve_project(base_relative)
        RUNNER.install_directory_adapter(consumer, source_config)
        adapted = consumer.load_source_runner(source_config)
        self.assertTrue(adapted.resolve_project(base_relative).is_dir())
        prompt_relative = parent["model"]["prompt"]["path"]
        self.assertTrue(adapted.resolve_project(prompt_relative).is_file())

    def test_verifier_wrapper_has_no_model_imports(self) -> None:
        tree = ast.parse(VERIFIER_PATH.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertFalse({"mlx", "mlx_lm", "torch", "transformers", "safetensors"} & imports)

    def test_output_roots_are_fresh(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        source_config = RUNNER.strict_json(
            RUNNER.require_record(config["parent_failure"]["config"])
        )
        view = RUNNER.continuation_view(config, source_config)
        self.assertEqual(view["outputs"], config["outputs"])
        self.assertFalse(RUNNER.resolve_project(config["outputs"]["public_root"], must_exist=False).exists())
        self.assertFalse(RUNNER.resolve_project(config["outputs"]["private_root"], must_exist=False).exists())

    def test_unchanged_contract_drift_is_rejected(self) -> None:
        config = RUNNER.load_config(RUNNER.DEFAULT_CONFIG)
        changed = dict(config)
        changed["smoke"] = dict(config["smoke"])
        changed["smoke"]["m2_hf_atol"] = 0.1
        with self.assertRaises(ValueError):
            RUNNER.require_inputs(changed)


if __name__ == "__main__":
    unittest.main()
