from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = MODULE_DIR / "run_exp070_extraction.py"
VERIFIER_PATH = MODULE_DIR / "verify_exp070_extraction.py"
CONFIG_PATH = MODULE_DIR / "configs" / "exp-070-formal-extraction.json"
NO_RESULT_CONFIG_PATH = MODULE_DIR / "configs" / "exp-070-layerwise-probe-preflight.json"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load("exp070_extraction_runner_tests", RUNNER_PATH)


class Exp070ExtractionTests(unittest.TestCase):
    def config(self) -> dict:
        return RUNNER.strict_json(CONFIG_PATH)

    def test_worker_plan_order_shapes_and_raw_bytes_are_exact(self) -> None:
        config = self.config()
        plan = RUNNER.expected_worker_plan()
        expected_ids = ["base"] + [
            f"m3-s{seed}-f{fold}"
            for seed in (42, 43, 44)
            for fold in range(5)
        ]
        self.assertEqual([item["worker_id"] for item in plan], expected_ids)
        self.assertEqual(config["workers"], plan)
        self.assertEqual(len(plan), 16)
        self.assertEqual(plan[0]["shape"], [3360, 9, 2560])
        self.assertTrue(all(item["shape"] == [3360, 9, 2560] for item in plan[1:6]))
        self.assertTrue(all(item["shape"] == [3360, 3, 2560] for item in plan[6:]))
        self.assertEqual(sum(item["payload_bytes"] for item in plan), 2_890_137_600)
        self.assertEqual(config["extraction"]["raw_payload_bytes"], 2_890_137_600)

    def test_authorization_and_access_history_are_extraction_only(self) -> None:
        config = self.config()
        authorization = config["authorization"]
        for key in ("initialize", "formal_extraction", "model_loading", "forward", "train_text"):
            self.assertTrue(authorization[key])
        for key in (
            "train_label_values",
            "heldout_gold",
            "training",
            "probe_fitting",
            "threshold_selection",
            "label_shuffle",
            "bootstrap",
            "performance_metrics",
            "validation",
            "test",
            "formal_completion",
            "exp071",
        ):
            self.assertFalse(authorization[key])
        self.assertEqual(authorization["historical_heldout_members"], ["sample_ids", "fold_ids", "logits"])
        self.assertEqual(
            config["access_history"],
            {
                "design_time_train_rows_displayed": 2,
                "used_for_method_or_result_selection": False,
                "model_loaded": False,
                "forward_executed": False,
                "metrics_computed": False,
                "validation_accessed": False,
                "test_accessed": False,
                "disposition": "recorded_and_excluded_from_scientific_use",
            },
        )

    def test_row_contract_contains_no_labels(self) -> None:
        rows = []
        for ordinal in range(3360):
            component = ordinal if ordinal < 3277 else ordinal - 3277
            rows.append(
                {
                    "ordinal": ordinal,
                    "sample_id": f"sample-{ordinal:04d}",
                    "component_id": f"component-{component:04d}",
                    "fold_id": ordinal % 5,
                }
            )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(RUNNER, "_load_fold_rows", return_value=rows),
                patch.object(RUNNER, "private_root", return_value=root),
            ):
                record, identity = RUNNER._build_row_contract({}, {})
            self.assertEqual(record["logical_name"], "row-contract.npz")
            self.assertEqual(os.stat(root / "row-contract.npz").st_mode & 0o777, 0o600)
            with np.load(root / "row-contract.npz", allow_pickle=False) as archive:
                self.assertEqual(set(archive.files), {"ordinal", "fold_id", "component_code"})
                self.assertFalse(any("label" in name.lower() for name in archive.files))
                self.assertEqual(archive["ordinal"].dtype, np.int32)
                self.assertEqual(archive["fold_id"].dtype, np.int8)
                self.assertEqual(archive["component_code"].dtype, np.int32)
            self.assertEqual(identity["component_count"], 3277)
            self.assertFalse(any("label" in key.lower() for key in identity))

    @staticmethod
    def _synthetic_chunk(matrix: np.ndarray, start: int, stop: int) -> dict:
        parity_payload = {"max_errors": {"pre_lora": 0.0}, "heldout_rows_checked": 0}
        return {
            "start": start,
            "stop": stop,
            "representation_sha256": RUNNER._chunk_digest(matrix, start, stop),
            "token_sha256": "1" * 64,
            "max_errors": parity_payload["max_errors"],
            "heldout_rows_checked": 0,
            "parity_sha256": RUNNER.bytes_sha256(
                RUNNER.canonical_json_bytes(parity_payload)
            ),
        }

    def test_memmap_progress_resumes_only_a_digest_verified_prefix(self) -> None:
        spec = {
            "worker_id": "base",
            "kind": "base",
            "seed": None,
            "fold": None,
            "points": ["H-1"],
            "shape": [4, 1, 2],
            "payload_bytes": 32,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(RUNNER, "ROWS", 4),
                patch.object(RUNNER, "CHUNK_ROWS", 2),
                patch.object(RUNNER, "worker_dir", side_effect=lambda _config, worker_id: root / worker_id),
            ):
                matrix, progress = RUNNER._prepare_partial({}, spec, "a" * 64)
                matrix[0:2] = np.asarray([[[1.0, 2.0]], [[3.0, 4.0]]], dtype=np.float32)
                matrix.flush()
                progress = dict(progress)
                progress["chunks"] = [self._synthetic_chunk(matrix, 0, 2)]
                progress["next_ordinal"] = 2
                RUNNER.replace_private_json(root / "base" / "progress.json", progress)
                del matrix

                resumed, resumed_progress = RUNNER._prepare_partial({}, spec, "a" * 64)
                self.assertEqual(resumed_progress["next_ordinal"], 2)
                self.assertEqual(resumed_progress["resume_count"], 1)
                np.testing.assert_array_equal(
                    np.asarray(resumed[0:2]),
                    np.asarray([[[1.0, 2.0]], [[3.0, 4.0]]], dtype=np.float32),
                )
                resumed[0, 0, 0] = 99.0
                resumed.flush()
                del resumed
                with self.assertRaisesRegex(ValueError, "committed chunk drift"):
                    RUNNER._prepare_partial({}, spec, "a" * 64)

    def test_memmap_progress_rejects_a_noncontinuous_prefix(self) -> None:
        spec = {
            "worker_id": "base",
            "kind": "base",
            "seed": None,
            "fold": None,
            "points": ["H-1"],
            "shape": [4, 1, 2],
            "payload_bytes": 32,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(RUNNER, "ROWS", 4),
                patch.object(RUNNER, "CHUNK_ROWS", 2),
                patch.object(RUNNER, "worker_dir", side_effect=lambda _config, worker_id: root / worker_id),
            ):
                matrix, progress = RUNNER._prepare_partial({}, spec, "b" * 64)
                matrix[:] = np.arange(8, dtype=np.float32).reshape(4, 1, 2)
                matrix.flush()
                progress = dict(progress)
                progress["chunks"] = [self._synthetic_chunk(matrix, 1, 2)]
                progress["next_ordinal"] = 2
                RUNNER.replace_private_json(root / "base" / "progress.json", progress)
                del matrix
                with self.assertRaisesRegex(ValueError, "committed chunk drift"):
                    RUNNER._prepare_partial({}, spec, "b" * 64)

    def test_json_and_npz_writers_are_no_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path = root / "record.json"
            npz_path = root / "record.npz"
            RUNNER.create_json_once(json_path, {"status": "first"})
            RUNNER.save_npz_once(npz_path, value=np.arange(3, dtype=np.int32))
            json_before = json_path.read_bytes()
            npz_before = npz_path.read_bytes()
            with self.assertRaises(FileExistsError):
                RUNNER.create_json_once(json_path, {"status": "second"})
            with self.assertRaises(FileExistsError):
                RUNNER.save_npz_once(npz_path, value=np.arange(4, dtype=np.int32))
            self.assertEqual(json_path.read_bytes(), json_before)
            self.assertEqual(npz_path.read_bytes(), npz_before)

    def test_worker_turn_rejects_later_worker_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "m3-s42-f0").mkdir()
            with patch.object(
                RUNNER,
                "worker_dir",
                side_effect=lambda _config, worker_id: root / worker_id,
            ):
                with self.assertRaisesRegex(ValueError, "later-worker artifact drift"):
                    RUNNER._require_worker_turn({}, "base", {}, {})

    def test_worker_turn_rejects_out_of_order_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(
                RUNNER,
                "worker_dir",
                side_effect=lambda _config, worker_id: root / worker_id,
            ):
                with self.assertRaisesRegex(ValueError, "invoked out of order"):
                    RUNNER._require_worker_turn({}, "m3-s42-f0", {}, {})

    def test_verifier_ast_has_no_runner_or_model_import(self) -> None:
        tree = ast.parse(VERIFIER_PATH.read_text(encoding="utf-8"))
        imports = set()
        dynamic_imports = set()
        fit_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == "fit":
                    fit_calls.append(node)
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "import_module"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    dynamic_imports.add(node.args[0].value.split(".")[0])
        self.assertNotIn(RUNNER_PATH.stem, imports | dynamic_imports)
        self.assertFalse({"mlx", "mlx_lm", "transformers"} & (imports | dynamic_imports))
        self.assertEqual(fit_calls, [])

    def test_formal_roots_are_separate_from_no_result_roots(self) -> None:
        formal = self.config()["outputs"]
        no_result = RUNNER.strict_json(NO_RESULT_CONFIG_PATH)["outputs"]
        self.assertNotEqual(formal["public_root"], no_result["public_root"])
        self.assertNotEqual(formal["private_root"], no_result["private_root"])
        self.assertNotEqual(formal["public_root"], formal["private_root"])
        self.assertIn("formal-extraction-attempt-1", formal["public_root"])
        self.assertIn("formal-extraction-attempt-1", formal["private_root"])

    def test_extraction_scope_keeps_probe_metrics_validation_and_test_false(self) -> None:
        config = self.config()
        forbidden = {
            "probe_fitting",
            "threshold_selection",
            "label_shuffle",
            "bootstrap",
            "performance_metrics",
            "validation",
            "test",
            "formal_completion",
            "exp071",
        }
        self.assertTrue(all(config["authorization"][key] is False for key in forbidden))
        self.assertIn("no probe fitting", config["claim_boundary"])
        self.assertIn("classification metric", config["claim_boundary"])


if __name__ == "__main__":
    unittest.main()
