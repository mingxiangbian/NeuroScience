"""Source-free EXP-075 science, access, publication and interoperability tests."""

from contextlib import ExitStack, contextmanager, nullcontext
from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

sys.dont_write_bytecode = True
import numpy as np

MODULE_DIR = Path(__file__).resolve().parents[1]


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, MODULE_DIR / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


RUN = load_module("exp075_test_producer", "run_exp075_geometry.py")
VERIFY = load_module("exp075_test_verifier", "verify_exp075_geometry.py")


def synthetic_config():
    record = lambda path: {"path": path, "bytes": 1, "mode": "0644", "sha256": "a" * 64}
    return {"experiment_id": "EXP-075", "parent_config": deepcopy(RUN.PARENT_RECORD),
            "protocol": record(RUN.PROTOCOL_PATH), "implementation": {key: record(path) for key, path in RUN.IMPLEMENTATION_PATHS.items()},
            "outputs": deepcopy(RUN.OUTPUTS), "resources": deepcopy(RUN.RESOURCES), "environment": deepcopy(RUN.SAFE.ENVIRONMENT), "method": deepcopy(RUN.METHOD)}


def synthetic_geometry():
    arrays = {name: np.zeros(record["shape"], dtype=record["dtype"]) for name, record in RUN.NPZ_MEMBERS.items()}
    arrays["heldout_ordinals"][:] = np.arange(3360, dtype=np.int32).reshape(5, 672)
    cka = [[0.9] * 5 for _ in range(15)]
    reasons = [[None] * 5 for _ in range(15)]
    cka[0] = [None] * 5
    reasons[0] = ["zero_centered_variance"] * 5
    return arrays, cka, reasons, list(np.linspace(-0.2, 0.2, 9))


class ScienceTests(unittest.TestCase):
    def setUp(self):
        self.x = np.random.default_rng(75).normal(size=(17, 11)) + 2
        self.z = self.x + np.random.default_rng(76).normal(size=(17, 11)) * 0.2

    def test_normal_domain_exact_old_and_independent_parity(self):
        actual = RUN.compute_geometry_pair(self.x, self.z)
        old = RUN.SAFE.compute_geometry_pair(self.x, self.z)
        other = VERIFY.compute_geometry_pair(self.x, self.z)
        for index in (0, 1):
            np.testing.assert_allclose(actual[index], old[index], rtol=0, atol=1e-12)
            np.testing.assert_allclose(actual[index], other[index], rtol=0, atol=1e-12)
        for index in (2, 3):
            self.assertAlmostEqual(actual[index], old[index], places=12)
            self.assertAlmostEqual(actual[index], other[index], places=12)
        self.assertIsNone(actual[4])

    def test_exact_zero_centered_variance_only_is_nullable(self):
        constant = np.ones_like(self.x)
        for x, z in ((constant, constant), (constant, self.z), (self.x, constant)):
            for module in (RUN, VERIFY):
                values = module.compute_geometry_pair(x, z)
                self.assertIsNone(values[2])
                self.assertEqual(values[4], "zero_centered_variance")
                self.assertTrue(np.all(np.isfinite(values[0])))
                self.assertTrue(np.all(np.isfinite(values[1])))

    def test_zero_row_vector_fails_even_if_centered_zero(self):
        for module in (RUN, VERIFY):
            with self.assertRaises(ValueError):
                module.compute_geometry_pair(np.zeros_like(self.x), self.z)

    def test_nonfinite_input_and_centering_overflow_fail(self):
        for scale in (math.inf, math.nan, 1e308):
            for module in (RUN, VERIFY):
                with np.errstate(all="ignore"), self.assertRaises(ValueError):
                    module.compute_geometry_pair(np.full_like(self.x, scale), self.z)

    def test_nonzero_centered_squared_norm_underflow_fails(self):
        for module in (RUN, VERIFY):
            with self.assertRaises(ValueError):
                module.linear_cka_nullable(self.x * 1e-100, self.z * 1e-100)

    def test_positive_norm_product_underflow_fails(self):
        for module in (RUN, VERIFY):
            with self.assertRaises(ValueError):
                module.linear_cka_nullable(self.x * 1e-50, self.z * 1e-50)

    def test_valid_zero_side_does_not_mask_other_side_underflow(self):
        for module in (RUN, VERIFY):
            for x, z in ((np.ones_like(self.x), self.z * 1e-100), (self.x * 1e-100, np.ones_like(self.z))):
                with self.assertRaises(ValueError):
                    module.linear_cka_nullable(x, z)

    def test_frozen_relative_l2_denominator_and_cosine(self):
        cosine, relative, cka, maximum, reason = RUN.compute_geometry_pair(self.x, 2 * self.x)
        np.testing.assert_allclose(relative, 1, rtol=0, atol=1e-12)
        np.testing.assert_allclose(cosine, 0, rtol=0, atol=1e-12)
        self.assertAlmostEqual(cka, 1, places=12)
        self.assertEqual(maximum, float(np.max(np.abs(self.x))))
        self.assertIsNone(reason)

    def test_all_five_or_null_no_nanmean(self):
        full = RUN.aggregate_cka([0.1, 0.2, 0.3, 0.4, 0.5], [None] * 5)
        self.assertAlmostEqual(full["mean"], 0.3)
        self.assertAlmostEqual(full["sample_sd"], float(np.std([0.1, 0.2, 0.3, 0.4, 0.5], ddof=1)))
        missing = RUN.aggregate_cka([None, 0.2, 0.3, 0.4, 0.5], ["zero_centered_variance", None, None, None, None])
        self.assertIsNone(missing["mean"])
        self.assertIsNone(missing["sample_sd"])
        self.assertEqual(missing["n_defined"], 4)
        with self.assertRaises(ValueError):
            RUN.aggregate_cka([None] * 5, [None] * 5)

    def test_spearman_fixed_nine_and_ties(self):
        values = [0.1, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        actual = RUN.fixed_nine_spearman(values, values)
        self.assertAlmostEqual(actual["rho"], -1)
        self.assertEqual(RUN.fixed_nine_spearman([None] + values[1:], values), {"rho": None, "reason": "undefined_cka_input"})
        self.assertEqual(RUN.fixed_nine_spearman([0.5] * 9, values), {"rho": None, "reason": "constant_vector"})
        with self.assertRaises(ValueError):
            RUN.fixed_nine_spearman(values[:8], values[:8])
        np.testing.assert_array_equal(RUN.average_ranks([1, 1, 3]), [1.5, 1.5, 3])

    def test_results_nullable_sanity_and_independent_parity(self):
        arrays, cka, reasons, ap5 = synthetic_geometry()
        actual = RUN.build_results(arrays, cka, reasons, ap5)
        self.assertTrue(VERIFY.recursive_close(actual, VERIFY.build_results(arrays, cka, reasons, ap5)))
        self.assertEqual(actual["seed42_spearman"]["n"], 9)
        self.assertIsNone(actual["seed42_spearman"]["rho"])
        self.assertEqual(set(actual["pre_lora_sanity"]["conditions"]), RUN.SANITY_CONDITIONS)
        self.assertNotIn(b"NaN", RUN.canonical_json_bytes(actual))
        arrays["max_abs_difference"][0, 2] = 1.1e-5
        for module in (RUN, VERIFY):
            with self.assertRaises(ValueError):
                module.build_results(arrays, cka, reasons, ap5)

    def test_pooled_quantiles_not_average_fold_quantiles(self):
        arrays, cka, reasons, ap5 = synthetic_geometry()
        arrays["cosine_distance"][0] = np.repeat(np.arange(5) / 10, 672)
        result = RUN.build_results(arrays, cka, reasons, ap5)["conditions"]["s42:H-1"]
        self.assertAlmostEqual(result["pooled_distance_statistics"]["cosine_distance"]["p90"], 0.4)
        self.assertAlmostEqual(np.mean([fold["cosine_distance"]["p90"] for fold in result["per_fold_distance_statistics"]]), 0.2)


class ContractTests(unittest.TestCase):
    def test_config_exact_gates_and_four_field_records(self):
        original = synthetic_config()
        for module in (RUN, VERIFY):
            module.validate_config(original)
            for field in ("method", "resources", "environment", "outputs", "parent_config"):
                changed = deepcopy(original)
                changed[field]["unexpected"] = True
                with self.assertRaises(ValueError):
                    module.validate_config(changed)
            for name in RUN.IMPLEMENTATION_PATHS:
                changed = deepcopy(original)
                changed["implementation"][name]["path"] = "alternate.py"
                with self.assertRaises(ValueError):
                    module.validate_config(changed)
            changed = deepcopy(original)
            changed["implementation"]["runner"]["status"] = "TBD"
            with self.assertRaises(ValueError):
                module.validate_config(changed)

    def test_cli_resolves_relative_path_before_stage(self):
        with patch.object(RUN, "run", return_value={"status": "Analyzed"}) as call, patch("builtins.print"):
            self.assertEqual(RUN.main(["--config", "relative-config.json", "run"]), 0)
        self.assertEqual(call.call_args.args[0], Path("relative-config.json").resolve())

    def test_top_level_import_does_not_import_numpy(self):
        source = "import importlib.util,sys; p=sys.argv[1]; s=importlib.util.spec_from_file_location('isolated',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); assert 'numpy' not in sys.modules; assert 'mlx' not in sys.modules"
        result = subprocess.run([sys.executable, "-B", "-c", source, str(MODULE_DIR / "run_exp075_geometry.py")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_atomic_no_clobber_and_no_partial_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "record.json"
            RUN.create_json_once(path, {"safe": True}, private=True)
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                RUN.create_json_once(path, {"changed": True})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            def fail(handle):
                handle.write(b"partial")
                raise RuntimeError("synthetic")
            with self.assertRaises(RuntimeError):
                RUN._atomic_once(root / "failed.json", fail, mode=0o644)
            self.assertEqual({p.name for p in root.iterdir()}, {"record.json"})

    def test_npz_exact_uncompressed_members_and_independent_validation(self):
        arrays, _, _, _ = synthetic_geometry()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "geometry.npz"
            RUN.save_geometry_once(path, arrays)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(archive.namelist(), [name + ".npy" for name in RUN.NPZ_ORDER])
                self.assertTrue(all(item.compress_type == zipfile.ZIP_STORED for item in archive.infolist()))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            VERIFY.validate_npz(path, arrays)
            with self.assertRaises(FileExistsError):
                RUN.save_geometry_once(path, arrays)

    def test_public_privacy_rejects_rowwise_and_private_paths(self):
        for module in (RUN, VERIFY):
            module.validate_public_payload({"access": RUN.ACCESS})
            for item in ({"value": list(range(672))}, {"value": "/Users/private/data"}, {"value": "phase-b-representation/private/a"}, {"sample_id": "synthetic"}):
                with self.assertRaises(ValueError):
                    module.validate_public_payload(item)
            module.validate_public_payload({"execution": {"command": [RUN.SAFE.ENVIRONMENT["python_executable"]]}})

    def test_persistent_lock_reuses_and_contention_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guard.lock"
            with RUN.SAFE._file_mutex(path, "synthetic"):
                with self.assertRaises(RuntimeError):
                    with RUN.SAFE._file_mutex(path, "synthetic"):
                        self.fail("lock contention accepted")
            self.assertTrue(path.is_file())
            with RUN.SAFE._file_mutex(path, "synthetic"):
                pass

    def test_budget_exhaustion_fails(self):
        with patch.object(RUN.time, "monotonic", return_value=8000), patch.object(RUN, "_peak_rss_bytes", return_value=1):
            with self.assertRaises(RuntimeError):
                RUN.budget_check(0)
        with patch.object(RUN.time, "monotonic", return_value=1), patch.object(RUN, "_peak_rss_bytes", return_value=RUN.RESOURCES["max_peak_rss_bytes"] + 1):
            with self.assertRaises(RuntimeError):
                RUN.budget_check(0)


class LoopTests(unittest.TestCase):
    def test_exact_75_pairs_heldout_only_order_without_source_values(self):
        ordinal = np.arange(3360, dtype=np.int32)
        fold_ids = np.arange(3360, dtype=np.int32) % 5
        rows_by_fold = [np.flatnonzero(fold_ids == fold) for fold in range(5)]
        selected, events = [], []
        class Matrix:
            def __init__(self, worker):
                self.worker = worker
            def __getitem__(self, key):
                rows, point, tail = key
                selected.append((self.worker, rows.copy(), point))
                if self.worker != "base":
                    np.testing.assert_array_equal(rows, rows_by_fold[int(self.worker[-1])])
                return np.broadcast_to(np.ones(2560), (672, 2560))
        workers = ["base"] + [f"m3-s{seed}-f{fold}" for seed in (42, 43, 44) for fold in range(5)]
        matrices = {worker: Matrix(worker) for worker in workers}
        points = {worker: {point: index for index, point in enumerate(RUN.ALL_POINTS if worker == "base" or "s42" in worker else RUN.CONFIRMATION_POINTS)} for worker in workers}
        with patch.object(RUN.SAFE, "_load_row_contract_values", return_value=(ordinal, fold_ids, rows_by_fold)), patch.object(RUN.SAFE, "_matrix_map", return_value=matrices), patch.object(RUN.SAFE, "_matrix_point_indices", return_value=points), patch.object(RUN.SAFE, "_load_probe_deltas", return_value=[0.1] * 9) as ap5, patch.object(RUN, "budget_check") as budget, patch.object(RUN, "compute_geometry_pair", return_value=(np.zeros(672), np.zeros(672), None, 0.0, "zero_centered_variance")):
            arrays, results = RUN.compute_geometry({}, 0, events.append)
        self.assertEqual([(event["condition"], event["fold"]) for event in events], [(condition, fold) for condition in RUN.CONDITION_ORDER for fold in range(5)])
        self.assertEqual(len(selected), 150)
        self.assertEqual(budget.call_count, 76)
        self.assertEqual(ap5.call_count, 1)
        np.testing.assert_array_equal(arrays["heldout_ordinals"], np.stack(rows_by_fold))
        self.assertEqual(results["seed42_spearman"]["reason"], "undefined_cka_input")


class LifecycleTests(unittest.TestCase):
    @contextmanager
    def synthetic_run_environment(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory).resolve()
            config_path = root / "synthetic-config.json"
            config = synthetic_config()
            RUN.create_json_once(config_path, config)
            snapshot = {"artifact_count": 0, "artifacts": [], "sha256": RUN.digest([])}
            arrays, cka, reasons, ap5 = synthetic_geometry()
            results = RUN.build_results(arrays, cka, reasons, ap5)
            def compute(parent, started, progress):
                for condition in RUN.CONDITION_ORDER:
                    values = results["conditions"][condition]["linear_cka"]["per_fold"]
                    for fold in RUN.FOLDS:
                        progress({"event": "pair_complete", "condition": condition, "fold": fold, "cka_defined": values[fold] is not None})
                return arrays, results
            def execution(path, current_config, started, ended):
                return {"started_at_utc": started, "ended_at_utc": ended, "command": [current_config["environment"]["python_executable"], RUN.IMPLEMENTATION_PATHS["runner"], "--config", path.relative_to(root).as_posix(), "run"], "cwd": ".", "git_commit": "1" * 40, "git_dirty": True}
            for module in (RUN, VERIFY):
                stack.enter_context(patch.object(module, "PROJECT_ROOT", root))
                stack.enter_context(patch.object(module.SAFE, "PROJECT_ROOT", root))
                stack.enter_context(patch.object(module, "require_frozen_files", return_value={"synthetic": True}))
                stack.enter_context(patch.object(module.SAFE, "require_parent_statuses"))
                stack.enter_context(patch.object(module.SAFE, "source_identity_snapshot", return_value=deepcopy(snapshot)))
                stack.enter_context(patch.object(module.SAFE, "matrix_headers", return_value=[]))
                stack.enter_context(patch.object(module.SAFE, "row_contract_headers", return_value={}))
                stack.enter_context(patch.object(module, "_peak_rss_bytes", return_value=1048576))
            stack.enter_context(patch.object(RUN, "producer_lock", side_effect=nullcontext))
            stack.enter_context(patch.object(VERIFY, "verification_lock", side_effect=nullcontext))
            stack.enter_context(patch.object(VERIFY, "_no_producer_or_model_import"))
            stack.enter_context(patch.object(RUN, "compute_geometry", side_effect=compute))
            stack.enter_context(patch.object(VERIFY, "recompute_geometry", return_value=(arrays, results)))
            stack.enter_context(patch.object(RUN, "_execution", side_effect=execution))
            stack.enter_context(patch.object(RUN.shutil, "disk_usage", return_value=Mock(free=2 * RUN.RESOURCES["min_free_bytes"])))
            yield root, config_path, config, snapshot, arrays, results

    def test_one_shot_producer_to_independent_verifier_and_no_retry(self):
        with self.synthetic_run_environment() as (root, path, config, snapshot, arrays, results):
            actual = RUN.run(path)
            public, private = root / config["outputs"]["public_root"], root / config["outputs"]["private_root"]
            self.assertEqual(actual["results"], results)
            validated, manifest = VERIFY.validate_payloads(path, config, snapshot)
            self.assertEqual(validated, actual)
            self.assertEqual(manifest["source_before"], manifest["source_after"])
            self.assertEqual(manifest["member_order"], list(RUN.NPZ_ORDER))
            VERIFY.validate_npz(private / "geometry.npz", arrays)
            verification = VERIFY.verify(path)
            self.assertEqual(verification["status"], "Passed")
            self.assertTrue(verification["complete"])
            self.assertTrue(verification["exp075_complete"])
            self.assertFalse(verification["exp071_complete"])
            sealed = {p: p.read_bytes() for p in [*public.iterdir(), *private.iterdir()]}
            with self.assertRaises(FileExistsError):
                RUN.run(path)
            with self.assertRaises(ValueError):
                VERIFY.verify(path)
            self.assertTrue(all(p.read_bytes() == payload for p, payload in sealed.items()))

    def test_pre_value_gate_failure_has_no_array_access(self):
        with self.synthetic_run_environment() as (root, path, config, *_):
            with patch.object(RUN.SAFE, "matrix_headers", side_effect=ValueError("synthetic_header_drift")), patch.object(RUN, "compute_geometry") as compute:
                with self.assertRaises(ValueError):
                    RUN.run(path)
                compute.assert_not_called()
            self.assertFalse((root / config["outputs"]["public_root"]).exists())

    def test_failure_is_append_only_and_does_not_publish_success(self):
        with self.synthetic_run_environment() as (root, path, config, *_):
            with patch.object(RUN, "compute_geometry", side_effect=ValueError("forbidden raw payload must not leak")):
                with self.assertRaises(ValueError):
                    RUN.run(path)
            public = root / config["outputs"]["public_root"]
            self.assertEqual({p.name for p in public.iterdir()}, {"stdout.log", "failure.json"})
            failure = RUN.SAFE.strict_json(public / "failure.json")
            self.assertEqual(failure["status"], "Failed")
            self.assertFalse(failure["retry_authorized"])
            self.assertNotIn("forbidden", (public / "failure.json").read_text())
            with self.assertRaises(FileExistsError):
                RUN.run(path)

    def test_source_mutation_prevents_success_publication(self):
        with self.synthetic_run_environment() as (root, path, config, snapshot, *_):
            changed = deepcopy(snapshot)
            changed["sha256"] = "b" * 64
            with patch.object(RUN.SAFE, "source_identity_snapshot", side_effect=[snapshot, changed]):
                with self.assertRaises(ValueError):
                    RUN.run(path)
            public = root / config["outputs"]["public_root"]
            self.assertFalse((public / "run.json").exists())
            self.assertTrue((public / "failure.json").exists())

    def test_verifier_rejects_output_tamper_without_overwrite(self):
        with self.synthetic_run_environment() as (root, path, config, snapshot, *_):
            RUN.run(path)
            public = root / config["outputs"]["public_root"]
            run_path = public / "run.json"
            original = run_path.read_bytes()
            # This is an owned temporary synthetic fixture, never a frozen source.
            altered = json.loads(original)
            altered["results"]["conditions"]["s42:H-1"]["linear_cka"]["n_defined"] = 5
            run_path.write_bytes(RUN.canonical_json_bytes(altered))
            with self.assertRaises(ValueError):
                VERIFY.validate_payloads(path, config, snapshot)
            self.assertFalse((public / "verification.json").exists())


if __name__ == "__main__":
    unittest.main()
