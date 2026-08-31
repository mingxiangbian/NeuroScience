"""Synthetic-only EXP-074 branch, source-chain and lifecycle tests."""
from contextlib import ExitStack, contextmanager, nullcontext
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
MODULE_DIR = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, MODULE_DIR / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


RUN = module("exp074_test_producer", "run_exp074_synthesis.py")
VERIFY = module("exp074_test_independent", "verify_exp074_synthesis.py")


def probe_result(passes=(True, True), zero_delta=False, zero_lower=False):
    contrasts, votes = {}, {}
    for seed, passed in zip((43, 44), passes):
        detail = {}
        for point in ("H27", "HF"):
            delta = 0.0 if zero_delta else 0.02
            lower = 0.0 if zero_lower else 0.01 if passed else -0.01
            interval = [lower, 0.03]
            contrasts[f"m3-s{seed}:{point}"] = {"delta": {"five_label_macro_ap": delta}, "bootstrap_delta_intervals": {"five_label_macro_ap": interval}}
            detail[point] = {"delta": delta, "interval": interval, "passed": delta > 0 and lower > 0}
        votes[str(seed)] = {"passed": all(item["passed"] for item in detail.values()), "points": detail}
    count = sum(item["passed"] for item in votes.values())
    return {"main_metrics": {}, "main_contrasts": contrasts, "seed_votes": votes, "negative_control_failure": False, "representation_state": count, "representation_state_label": RUN.REPRESENTATION_STATES[count]}


def ablation_result(d_values=(0.02, 0.02)):
    conditions = {}
    for key in RUN.ABLATION_ORDER:
        seed, condition = key.split(":")
        delta = -d_values[int(seed[1:]) - 43] if seed in {"s43", "s44"} and condition == "A2" else 0.0
        conditions[key] = {"metrics": {"rows": 3360, "five_label_macro_f1": 0.5 + delta}, "delta_from_full": {"five_label_macro_f1": delta}}
    return {"condition_order": list(RUN.ABLATION_ORDER), "conditions": conditions}


def geometry_result():
    conditions = {}
    for condition in RUN.GEOMETRY_ORDER:
        missing = condition == "s42:H-1"
        conditions[condition] = {"linear_cka": {"per_fold": [None] * 5 if missing else [0.9] * 5, "reason_by_fold": ["zero_centered_variance"] * 5 if missing else [None] * 5, "mean": None if missing else 0.9, "sample_sd": None if missing else 0.0, "n_defined": 0 if missing else 5, "reason": "undefined_fold_cka" if missing else None}}
    return {"condition_order": list(RUN.GEOMETRY_ORDER), "conditions": conditions, "seed42_spearman": {"point_order": list(RUN.POINTS), "n": 9, "rho": None, "reason": "undefined_cka_input"}}


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        root = Path(directory).resolve()
        for current in (RUN, VERIFY):
            stack.enter_context(patch.object(current, "PROJECT_ROOT", root))
            stack.enter_context(patch.object(current.SAFE, "PROJECT_ROOT", root))
            stack.enter_context(patch.object(current, "frozen_files", side_effect=lambda path, config: RUN.artifact(path)))
            stack.enter_context(patch.object(current, "synthesis_lock", side_effect=nullcontext))
        def execution(path, started, ended):
            return {"started_at_utc": started, "ended_at_utc": ended, "command": [str(Path(sys.executable).resolve()), RUN.IMPLEMENTATION_PATHS["runner"], "--config", path.relative_to(root).as_posix()], "cwd": ".", "git_commit": "1" * 40, "git_dirty": True}
        stack.enter_context(patch.object(RUN, "execution", side_effect=execution))
        source, inputs = {}, {}
        def save(name, value):
            if name in ("geometry_verification", "ablation_verification"):
                value["source_unchanged"] = True
            path = root / RUN.BASE / "runs/synthetic-sources" / (name + ".json")
            path.parent.mkdir(parents=True, exist_ok=True)
            RUN.write_once(path, RUN.canonical_json_bytes(value))
            source[name], inputs[name] = RUN.artifact(path), value
        probe, geometry, ablation = probe_result(), geometry_result(), ablation_result()
        save("probe", {"experiment_id": "EXP-070", "status": "CompletedAwaitingVerification", "results": probe})
        # Mirrors the actual EXP-070 verification-attempt-2 recovery metadata.
        # It has source_probe, not run; completion only points to verification.
        save("probe_verification", {"experiment_id": "EXP-070", "status": "Passed", "failed_count": 0, "source_probe": source["probe"], "source_snapshot_unchanged": True, "source_mutated": False, "source_snapshot_sha256": "c" * 64, "results_sha256": RUN.digest(probe), "negative_control_failure": False, "representation_state": probe["representation_state"], "representation_state_label": probe["representation_state_label"]})
        save("probe_completion", {"experiment_id": "EXP-070", "status": "Complete", "formal_probe_complete": True, "exp070_complete": True, "verification": source["probe_verification"], "source_mutated": False, "source_snapshot_sha256": "c" * 64, "negative_control_failure": False, "representation_state_assignment_valid": True, "representation_state": probe["representation_state"], "representation_state_label": probe["representation_state_label"]})
        save("geometry_run", {"experiment_id": "EXP-075", "status": "Analyzed", "method": {"post_diagnostic": True}, "results": geometry})
        save("geometry_verification", {"experiment_id": "EXP-075", "status": "Passed", "failed_count": 0, "complete": True, "exp075_complete": True, "exp071_complete": False, "run": source["geometry_run"], "results_sha256": RUN.digest(geometry)})
        save("ablation_score", {"experiment_id": "EXP-072", "status": "ScoredAwaitingVerification", "results": ablation, "results_sha256": RUN.digest(ablation)})
        save("ablation_verification", {"experiment_id": "EXP-072", "status": "Passed", "complete": True, "exp072_complete": True, "score": source["ablation_score"], "results_sha256": RUN.digest(ablation)})
        record = lambda path: {"path": path, "bytes": 1, "mode": "0644", "sha256": "a" * 64}
        config = {"experiment_id": "EXP-074", "protocol": record(RUN.PROTOCOL_PATH), "implementation": {name: record(path) for name, path in RUN.IMPLEMENTATION_PATHS.items()}, "source": source, "outputs": deepcopy(RUN.OUTPUTS), "resources": deepcopy(RUN.RESOURCES)}
        config_path = root / "synthetic-config.json"
        RUN.write_once(config_path, RUN.canonical_json_bytes(config))
        yield root, config_path, config, inputs


class SynthesisTests(unittest.TestCase):
    def test_representation_all_three_states_and_strict_zero_boundaries(self):
        for flags, expected in (((True, True), 2), ((True, False), 1), ((False, False), 0)):
            source = probe_result(flags)
            for current in (RUN, VERIFY):
                result = current.representation_state(source)
                self.assertEqual(result["passed_seeds"], expected)
                self.assertEqual(result["state"], RUN.REPRESENTATION_STATES[expected])
        for source in (probe_result(zero_delta=True), probe_result(zero_lower=True)):
            self.assertEqual(RUN.representation_state(source)["passed_seeds"], 0)
            self.assertEqual(VERIFY.representation_state(source)["passed_seeds"], 0)

    def test_original_vote_or_negative_control_drift_rejected(self):
        for mutate in (lambda source: source.update(negative_control_failure=True), lambda source: source.update(representation_state=0), lambda source: source["seed_votes"]["43"].update(passed=False)):
            value = probe_result()
            mutate(value)
            for current in (RUN, VERIFY):
                with self.assertRaises(ValueError):
                    current.representation_state(value)

    def test_functional_states_sign_threshold_and_disagreement(self):
        for values, expected in (((0.01, 0.02), "Stable Attention-dominant dependency"), ((-0.01, -0.02), "Stable MLP-dominant dependency"), ((0.009, 0.02), "Both contribute / no stable dominance"), ((0.02, -0.02), "Both contribute / no stable dominance")):
            source = ablation_result(values)
            self.assertEqual(RUN.functional_state(source)["state"], expected)
            self.assertEqual(VERIFY.functional_state(source)["state"], expected)
            self.assertEqual(RUN.functional_state(source), VERIFY.functional_state(source))

    def test_bad_functional_delta_and_missing_condition_fail(self):
        for value in (float("nan"), 0.25):
            changed = ablation_result()
            changed["conditions"]["s43:A2"]["delta_from_full"]["five_label_macro_f1"] = value
            for current in (RUN, VERIFY):
                with self.assertRaises(ValueError):
                    current.functional_state(changed)
        changed = ablation_result()
        del changed["conditions"]["s44:A3"]
        with self.assertRaises(ValueError):
            RUN.functional_state(changed)

    def test_null_geometry_is_retained_and_never_eight_point(self):
        with fixture() as (_, _, config, inputs):
            left = RUN.make_summary(inputs, config["source"])
            right = VERIFY.make_summary(inputs, config["source"])
            self.assertEqual(left, right)
            self.assertIsNone(left["geometry"]["seed42_spearman"]["rho"])
            self.assertEqual(left["history_and_scope"]["exp071"], "Failed")
            self.assertNotIn("threshold_indices_by_outer_fold", left["probe"])
            changed = geometry_result()
            changed["seed42_spearman"]["n"] = 8
            for current in (RUN, VERIFY):
                with self.assertRaises(ValueError):
                    current.validate_geometry(changed)

    def test_full_temp_public_artifact_interoperability_and_no_clobber(self):
        with fixture() as (root, path, config, inputs):
            result = RUN.run(path)
            public = root / config["outputs"]["public_root"]
            self.assertEqual(result["status"], "SynthesizedAwaitingVerification")
            expected = VERIFY.make_summary(VERIFY.load_inputs(config), config["source"])
            VERIFY.validate_payload(path, config, expected)
            verified = VERIFY.verify(path)
            self.assertTrue(verified["complete"])
            self.assertTrue(verified["phase_b_minimum_complete"])
            self.assertFalse(verified["exp071_complete"])
            files = {item: item.read_bytes() for item in public.iterdir()}
            with self.assertRaises(FileExistsError):
                RUN.run(path)
            with self.assertRaises(ValueError):
                VERIFY.verify(path)
            self.assertTrue(all(item.read_bytes() == payload for item, payload in files.items()))
            self.assertEqual({item.name for item in public.iterdir()}, {"run.json", "summary.json", "stdout.log", "verification.json"})

    def test_source_hash_and_verification_chain_tamper_fail(self):
        with fixture() as (root, _, config, inputs):
            for current in (RUN, VERIFY):
                self.assertEqual(current.load_inputs(config), inputs)
                current.validate_probe_metadata(inputs["probe"], inputs["probe_verification"], inputs["probe_completion"], config["source"])
                legacy = deepcopy(inputs["probe_verification"])
                legacy["run"] = legacy.pop("source_probe")
                legacy["source_unchanged"] = legacy.pop("source_snapshot_unchanged")
                with self.assertRaises(ValueError):
                    current.validate_probe_metadata(inputs["probe"], legacy, inputs["probe_completion"], config["source"])
                mismatched = deepcopy(inputs["probe_completion"])
                mismatched["source_snapshot_sha256"] = "d" * 64
                with self.assertRaises(ValueError):
                    current.validate_probe_metadata(inputs["probe"], inputs["probe_verification"], mismatched, config["source"])
                bad = deepcopy(config)
                bad["source"]["probe"]["sha256"] = "b" * 64
                with self.assertRaises(ValueError):
                    current.load_inputs(bad)
            target = root / config["source"]["ablation_verification"]["path"]
            changed = deepcopy(inputs["ablation_verification"])
            changed["complete"] = False
            target.write_bytes(RUN.canonical_json_bytes(changed))
            config["source"]["ablation_verification"] = RUN.artifact(target)
            for current in (RUN, VERIFY):
                with self.assertRaises(ValueError):
                    current.load_inputs(config)

    def test_config_private_path_and_public_rowwise_guard(self):
        with fixture() as (_, _, config, _):
            for current in (RUN, VERIFY):
                current.validate_config(config)
                changed = deepcopy(config)
                changed["source"]["probe"]["path"] = RUN.BASE + "private/probe.json"
                with self.assertRaises(ValueError):
                    current.validate_config(changed)
                for payload in ({"value": list(range(672))}, {"sample_id": "private"}, {"path": "/Users/private/source"}):
                    with self.assertRaises(ValueError):
                        current.public_ok(payload)

    def test_summary_tamper_rejected_without_scientific_access(self):
        with fixture() as (root, path, config, _):
            RUN.run(path)
            target = root / config["outputs"]["public_root"] / "summary.json"
            altered = json.loads(target.read_bytes())
            altered["functional_dependency"]["state"] = "Stable MLP-dominant dependency"
            target.write_bytes(RUN.canonical_json_bytes(altered))
            with self.assertRaises(ValueError):
                VERIFY.verify(path)

    def test_cli_path_resolution_and_import_without_arrays(self):
        with patch.object(RUN, "run", return_value={"status": "SynthesizedAwaitingVerification"}) as call, patch("builtins.print"):
            self.assertEqual(RUN.main(["--config", "relative-config.json"]), 0)
        self.assertEqual(call.call_args.args[0], Path("relative-config.json").resolve())
        source = "import importlib.util,sys; s=importlib.util.spec_from_file_location('v',sys.argv[1]); m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.no_compute_import()"
        result = subprocess.run([sys.executable, "-B", "-c", source, str(MODULE_DIR / "verify_exp074_synthesis.py")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_atomic_writer_rejects_existing_file_and_cleans_own_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            RUN.write_once(path, b"sealed\n")
            with self.assertRaises(FileExistsError):
                RUN.write_once(path, b"overwrite\n")
            self.assertEqual(path.read_bytes(), b"sealed\n")
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)
            with patch.object(RUN.os, "link", side_effect=FileExistsError("synthetic race")):
                with self.assertRaises(FileExistsError):
                    RUN.write_once(path.parent / "race.json", b"not published\n")
            self.assertEqual({entry.name for entry in path.parent.iterdir()}, {"result.json"})

    def test_wall_rss_and_output_budgets_fail_closed(self):
        for current in (RUN, VERIFY):
            with patch.object(current.time, "monotonic", return_value=3601), patch.object(current, "peak_rss", return_value=1):
                with self.assertRaises(RuntimeError):
                    current.budget(0)
            with patch.object(current.time, "monotonic", return_value=1), patch.object(current, "peak_rss", return_value=2 ** 30 + 1):
                with self.assertRaises(RuntimeError):
                    current.budget(0)


if __name__ == "__main__":
    unittest.main()
