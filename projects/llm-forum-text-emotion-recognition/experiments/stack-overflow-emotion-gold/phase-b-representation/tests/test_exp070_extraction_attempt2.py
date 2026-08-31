from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import tempfile
import unittest

import numpy as np


MODULE_DIR = Path(__file__).resolve().parents[1]
VERIFIER_PATH = MODULE_DIR / "verify_exp070_extraction_attempt2.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFIER = load("exp070_extraction_verification_attempt2_tests", VERIFIER_PATH)


class Exp070ExtractionVerificationAttempt2Tests(unittest.TestCase):
    def test_scope_is_append_only_model_free_verification(self) -> None:
        config = VERIFIER.load_config(VERIFIER.DEFAULT_CONFIG)
        self.assertEqual(
            config["scope"],
            {
                "verification_only": True,
                "model_rerun": False,
                "worker_rerun": False,
                "assemble_rerun": False,
                "source_mutation": False,
                "probe_consumer": False,
                "exp071": False,
            },
        )
        forbidden = {
            "model_loading", "forward", "training", "worker_rerun", "assemble_rerun",
            "train_text", "train_labels", "heldout_gold", "validation", "test",
            "probe_fitting", "threshold_selection", "label_shuffle", "bootstrap",
            "performance_metrics", "exp071",
        }
        self.assertTrue(all(config["authorization"][key] is False for key in forbidden))

    def test_frozen_records_and_incident_evidence_match(self) -> None:
        config = VERIFIER.load_config(VERIFIER.DEFAULT_CONFIG)
        VERIFIER.require_config_records(config)
        VERIFIER.validate_incident(config)

    def test_fold0_observation_is_disclosed_before_freeze(self) -> None:
        config = VERIFIER.load_config(VERIFIER.DEFAULT_CONFIG)
        observed = config["incident_evidence"]["observed_before_freeze"]
        self.assertTrue(observed["float64_result_observed_before_rule_freeze"])
        self.assertEqual(observed["remaining_workers_float64_unobserved_at_freeze"], 14)
        self.assertEqual(observed["fold0_runner_mlx_max_abs"], 0.0)
        self.assertEqual(observed["fold0_pre_lora_max_abs"], 0.0)
        self.assertGreater(observed["fold0_numpy_float32_max_abs"], 1e-5)
        self.assertEqual(observed["fold0_numpy_float32_count_gt_atol"], 1)
        self.assertLessEqual(observed["fold0_numpy_float64_max_abs"], 1e-5)

    def test_digest_schemes_are_recorded_but_not_compared(self) -> None:
        config = VERIFIER.load_config(VERIFIER.DEFAULT_CONFIG)
        observed = config["incident_evidence"]["observed_before_freeze"]
        self.assertTrue(observed["token_digest_values_observed_different"])
        base = VERIFIER.strict_json(
            VERIFIER.require_record(config["incident_evidence"]["base_worker"])
        )
        m2 = VERIFIER.strict_json(
            VERIFIER.require_record(config["incident_evidence"]["m2_metadata"])
        )
        self.assertNotEqual(base["token_id_stream_sha256"], m2["token_id_stream_sha256"])
        self.assertFalse(config["numeric_contract"]["base_legacy_m2_digest_equality_required"])
        self.assertTrue(config["numeric_contract"]["cross_worker_token_digest_required"])
        tracked = (
            VERIFIER.DEFAULT_CONFIG.read_text(encoding="utf-8")
            + VERIFIER.require_record(config["implementation"]["protocol"]).read_text(encoding="utf-8")
        )
        self.assertNotIn(base["token_id_stream_sha256"], tracked)
        self.assertNotIn(m2["token_id_stream_sha256"], tracked)

    def test_source_transform_has_exact_two_corrections(self) -> None:
        config = VERIFIER.load_config(VERIFIER.DEFAULT_CONFIG)
        source_path = VERIFIER.require_record(config["source_snapshot"]["source_verifier"])
        source = source_path.read_text(encoding="utf-8")
        self.assertEqual(source.count("EXP-070 base token-stream digest drift"), 1)
        self.assertEqual(
            source.count('if worker["token_id_stream_sha256"] != token_digest:'),
            1,
        )
        transformed, digest = VERIFIER.transform_source_verifier(source_path)
        self.assertEqual(len(digest), 64)
        self.assertEqual(transformed.INDEPENDENT_AFFINE_DIAGNOSTICS, [])
        names = set(transformed.independent_heldout_error.__code__.co_names)
        self.assertIn("INDEPENDENT_AFFINE_DIAGNOSTICS", names)
        self.assertIn("float64", names)
        constants = set()
        for value in transformed.independent_heldout_error.__code__.co_consts:
            if isinstance(value, str):
                constants.add(value)
            elif isinstance(value, tuple):
                constants.update(item for item in value if isinstance(item, str))
        self.assertTrue(
            {
                "worker_id", "runner_mlx_max_abs", "numpy_float32_max_abs",
                "numpy_float64_max_abs",
            }.issubset(constants)
        )
        self.assertNotIn(
            "EXP-070 base token-stream digest drift",
            transformed.validate_all_workers.__code__.co_consts,
        )

    def test_float64_rule_keeps_original_tolerance_and_no_fallback(self) -> None:
        config = VERIFIER.load_config(VERIFIER.DEFAULT_CONFIG)
        numeric = config["numeric_contract"]
        self.assertEqual(numeric["rtol"], 0.0)
        self.assertEqual(numeric["atol"], 1e-5)
        self.assertFalse(numeric["float64_result_cast_back"])
        self.assertTrue(numeric["no_fallback_dtype_operator_or_tolerance"])
        x = np.asarray([[1.5, -2.0, 3.25]], dtype=np.float32)
        weight = np.asarray([[0.5, 4.0, -1.0]], dtype=np.float32)
        bias = np.asarray([0.125], dtype=np.float32)
        observed = x.astype(np.float64) @ weight.astype(np.float64).T + bias.astype(np.float64)
        expected = np.asarray([[-10.375]], dtype=np.float64)
        np.testing.assert_array_equal(observed, expected)

    def test_snapshot_digest_detects_source_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / "public"
            private = root / "private"
            public.mkdir()
            private.mkdir()
            (public / "run.json").write_bytes(b"one")
            (private / "matrix.bin").write_bytes(b"two")
            before = VERIFIER.snapshot_digest(public, private)
            (private / "matrix.bin").write_bytes(b"three")
            after = VERIFIER.snapshot_digest(public, private)
            self.assertNotEqual(before, after)

    def test_claim_is_created_before_transformed_replay(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        verify_start = source.index("def verify(")
        body = source[verify_start : source.index("def record_failure", verify_start)]
        self.assertLess(
            body.index("create_json_once(claim_path, claim)"),
            body.index("run_transformed_replay(config)"),
        )
        self.assertLess(
            body.index("validate_source_ready(config)"),
            body.index("recovery.mkdir"),
        )

    def test_passed_verification_prefix_can_resume_completion(self) -> None:
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        self.assertIn("def resume_passed_verification_completion", source)
        resume_start = source.index("def resume_passed_verification_completion")
        resume_body = source[resume_start : source.index("def verify(", resume_start)]
        self.assertIn("run_transformed_replay(config)", resume_body)
        self.assertIn("build_recovery_verification", resume_body)
        self.assertIn("require_exact_passed_verification", resume_body)
        verify_start = source.index("def verify(")
        body = source[verify_start : source.index("def record_failure", verify_start)]
        self.assertIn("return resume_passed_verification_completion", body)

    def test_exact_passed_verification_rejects_tampering(self) -> None:
        expected = {
            "status": "Passed",
            "access": {"heldout_gold_read": False},
            "worker_parity_diagnostics": [
                {
                    "worker_id": "m3-s42-f0",
                    "runner_mlx_max_abs": 0.0,
                    "numpy_float32_max_abs": 1.049041748046875e-5,
                    "numpy_float64_max_abs": 2.086469194750862e-6,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "verification.json"
            VERIFIER.create_json_once(path, expected)
            VERIFIER.require_exact_passed_verification(path, expected)
            tampered = dict(expected)
            tampered["access"] = {"heldout_gold_read": True}
            path.write_bytes(VERIFIER.canonical_json_bytes(tampered))
            with self.assertRaisesRegex(ValueError, "existing Passed verification drift"):
                VERIFIER.require_exact_passed_verification(path, expected)

    def test_recovery_output_root_is_fresh_and_separate(self) -> None:
        config = VERIFIER.load_config(VERIFIER.DEFAULT_CONFIG)
        self.assertEqual(config["outputs"]["recovery_public_root"], VERIFIER.RECOVERY_PUBLIC_ROOT)
        self.assertNotEqual(
            config["outputs"]["recovery_public_root"],
            config["future_snapshot"]["source_public_root"],
        )
        self.assertEqual(
            config["outputs"]["allowlist"],
            ["source-snapshot-claim.json", "verification.json", "extraction-complete.json"],
        )

    def test_verifier_has_no_model_runner_or_probe_import(self) -> None:
        tree = ast.parse(VERIFIER_PATH.read_text(encoding="utf-8"))
        imports = set()
        fit_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "fit"
            ):
                fit_calls.append(node)
        self.assertFalse({"mlx", "mlx_lm", "torch", "transformers", "sklearn"} & imports)
        self.assertEqual(fit_calls, [])
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import run_exp070_extraction", source)


if __name__ == "__main__":
    unittest.main()
