"""Source-free EXP-072 scorer -> independent verifier integration."""
from contextlib import ExitStack, nullcontext
import copy
import importlib.util
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile

import numpy as np


HERE = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


RUN = module("exp072_fixture_runner", "run_exp072_ablation.py")
SCORE = module("exp072_fixture_scorer", "score_exp072_ablation.py")
VERIFY = module("exp072_fixture_verifier", "verify_exp072_ablation.py")
SELECTOR = module("exp072_fixture_selector", "verify_exp071_drift.py")


def npz_bytes(arrays, *, poison=False):
    buffer = io.BytesIO()
    if not poison:
        np.savez(buffer, **arrays)
    else:
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, value in arrays.items():
                member = io.BytesIO()
                np.save(member, value, allow_pickle=False)
                archive.writestr(name + ".npy", member.getvalue())
            archive.writestr("forbidden_labels_text_component.npy", b"NOT AN NPY: MUST NEVER DECODE")
    return buffer.getvalue()


class Fixture:
    """Real 70-worker seal; only environment and parent metadata are synthetic."""
    def __enter__(self):
        self.stack = ExitStack()
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.stack.enter_context(mock.patch.object(RUN, "PROJECT_ROOT", self.root))
        self.stack.enter_context(mock.patch.object(VERIFY, "PROJECT_ROOT", self.root))
        self.config = {
            "environment": {"python_executable": sys.executable},
            "resources": dict(RUN.DEFAULT_RESOURCES), "method": {"synthetic": True},
            "outputs": {"public_root": f"{RUN.PREFIX}/runs/{RUN.RUN_ID}/{RUN.ATTEMPT_ID}",
                        "private_root": f"{RUN.PREFIX}/private/{RUN.RUN_ID}/{RUN.ATTEMPT_ID}"},
            "implementation": {"verifier": {"fixture_self": True}},
            "source": {"helpers": {"selective_json": {"fixture_parser": True}}},
        }
        self.public, self.private = RUN.roots(self.config)
        for root, mode in ((self.public, 0o755), (self.private, 0o700)):
            root.mkdir(parents=True, mode=mode)
            (root / "workers").mkdir(mode=mode)
            root.chmod(mode)
        self.sources = self.root / "fixture-sources"
        self.sources.mkdir(mode=0o700)
        self.folds = (np.arange(3360) % 5).astype(np.int8)
        self.ids = [f"synthetic-{index:04d}" for index in range(3360)]
        self.gold = ((np.arange(3360)[:, None] + np.arange(6)[None, :]) % 3 == 0).astype(np.uint8)
        self.logits = {}
        for seed, condition in VERIFY.CONDITIONS:
            base = ((np.arange(3360)[:, None] * 3 + np.arange(6)[None, :] + seed) % 17 - 8) / 4
            self.logits[f"s{seed}:{condition}"] = (base + int(condition[1]) / 10).astype(np.float32)
        self.metadata = {"original_config": {"data": {}}, "exp069_manifest": {"m3_sources": []}}
        self.references = {}
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def write(self, path, payload, *, private=True):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        path.chmod(0o600 if private else 0o644)
        return RUN.artifact(path)

    def json(self, path, payload, *, private=True):
        return self.write(path, RUN.canonical_json_bytes(payload), private=private)

    def build(self, *, reference_delta=0.0):
        public_rows = [{"sample_id": sid, "fold_id": int(fold), "component_code": "UNREAD"}
                       for sid, fold in zip(self.ids, self.folds, strict=True)]
        private_rows = [{"sample_id": sid, "fold_id": int(fold), "labels": row.tolist(), "component_code": "UNREAD"}
                        for sid, fold, row in zip(self.ids, self.folds, self.gold, strict=True)]
        data = self.metadata["original_config"]["data"]
        data["fold_manifest_public"] = self.write(self.sources / "fold-public.jsonl", b"".join(RUN.canonical_json_bytes(row) for row in public_rows), private=False)
        data["fold_manifest_private"] = self.write(self.sources / "fold-private.jsonl", b"".join(RUN.canonical_json_bytes(row) for row in private_rows))
        source = self.config["source"]
        source["exp070_row_contract"] = self.write(self.sources / "rows.npz", npz_bytes({"ordinal": np.arange(3360, dtype=np.int32), "fold_id": self.folds}, poison=True))
        source["thresholds"] = []
        for seed in (42, 43, 44):
            threshold = self.write(self.sources / f"threshold-{seed}.npz", npz_bytes({"fold_ids": self.folds, "m3_raw_thresholds": np.full(3360, 0.5, dtype=np.float64)}, poison=True))
            source["thresholds"].append({"seed": seed, "allowed_members": ["fold_ids", "m3_raw_thresholds"], "artifact": threshold})
            for fold in range(5):
                ordinals = np.flatnonzero(self.folds == fold)
                ids = np.asarray([self.ids[index] for index in ordinals])[::-1]
                logits = self.logits[f"s{seed}:A0"][ordinals][::-1].copy()
                if seed == 42 and fold == 0:
                    logits[0, 0] += np.float32(reference_delta)
                heldout = self.write(self.sources / f"s{seed}-f{fold}-reference.npz", npz_bytes({"sample_ids": ids, "fold_ids": self.folds[ordinals], "logits": logits}, poison=True))
                record = {"seed": seed, "fold": fold, "heldout_logits": heldout,
                          "adapter": self.write(self.sources / f"s{seed}-f{fold}-adapter.bin", b"synthetic adapter"),
                          "head": self.write(self.sources / f"s{seed}-f{fold}-head.bin", b"synthetic head")}
                self.metadata["exp069_manifest"]["m3_sources"].append(record)
        self.config_path = self.root / "fixture-config.json"
        self.config_record = self.json(self.config_path, self.config, private=False)
        snapshot = {path.relative_to(self.root).as_posix(): RUN.artifact(path) for path in sorted(self.sources.iterdir())}
        self.metadata.update(source_snapshot=snapshot, source_snapshot_sha256=RUN.digest(snapshot))
        self.json(self.private / "input-manifest.json", {
            "schema_version": "exp-072-input-manifest-v1", **VERIFY._common(), "status": "Frozen",
            "config": self.config_record, "source_snapshot": snapshot, "source_snapshot_sha256": RUN.digest(snapshot),
            "method_sha256": RUN.digest(self.config["method"]), "worker_plan": RUN.expected_workers(),
            "fold_sources": self.metadata["exp069_manifest"]["m3_sources"], "access": dict(RUN.METADATA_ACCESS)})
        claim = {"schema_version": "exp-072-run-claim-v1", **VERIFY._common(), "status": "Running", "tier": "Major", "rq_id": "RQ-S4.3", "stage": "run",
                 "config": self.config_record, "input_manifest": RUN.artifact(self.private / "input-manifest.json"),
                 "environment": self.config["environment"], "resources": self.config["resources"], "access": dict(RUN.METADATA_ACCESS),
                 "started_at": "2026-08-30T00:00:00+00:00", "command": [sys.executable, str(self.root / VERIFY.RUNNER_PATH), "--stage", "run", "--config", str(self.config_path)],
                 "cwd": str(self.root), "git": {"commit": "a" * 40, "dirty": True}, "scheduler_pid": 123}
        self.json(self.public / "run-claim.json", claim, private=False)
        workers = {}
        for spec in RUN.expected_workers():
            wid, seed, fold, condition = (spec[key] for key in ("worker_id", "seed", "fold", "condition"))
            ordinals = np.flatnonzero(self.folds == fold).astype(np.int32)
            output = self.write(self.private / "workers" / f"{wid}.npz", npz_bytes({"ordinal": ordinals, "fold_id": self.folds[ordinals], "logits": self.logits[f"s{seed}:{condition}"][ordinals]}))
            original = next(row for row in self.metadata["exp069_manifest"]["m3_sources"] if row["seed"] == seed and row["fold"] == fold)
            source_identity = {name: original[key] for name, key in (("adapter", "adapter"), ("head", "head"), ("heldout", "heldout_logits"))}
            replay = {"required": condition == "A0", "checked_rows": 672 if condition == "A0" else 0,
                      "max_abs_error": 0.0 if condition == "A0" else None, "atol": 1e-5, "rtol": 0.0}
            worker = {"schema_version": "exp-072-worker-private-v1", **VERIFY._common(), **spec, "status": "Completed", "config": self.config_record,
                      "input_manifest": RUN.artifact(self.private / "input-manifest.json"), "output": output,
                      "row_order_sha256": RUN.array_sha256(ordinals), "fold_id_sha256": RUN.array_sha256(self.folds[ordinals]),
                      "sample_id_order_sha256": RUN.string_digest([self.ids[index] for index in ordinals]), "token_stream_sha256": "b" * 64,
                      "source_before": source_identity, "source_after": source_identity,
                      "tensor_before": {"adapter": "c" * 64, "head": "d" * 64, "base_sentinel": "e" * 64},
                      "tensor_after": {"adapter": "c" * 64, "head": "d" * 64, "base_sentinel": "e" * 64},
                      "scale_map_sha256": RUN.digest(RUN.scale_map(condition)), "disabled_modules": sum(row["scale"] == 0 for row in RUN.scale_map(condition)),
                      "rows": 672, "replay": replay, "resources": {"wall_seconds": 1.0, "peak_mlx_bytes": 64, "peak_rss_bytes": 1024}, "access": dict(RUN.INFERENCE_ACCESS)}
            private_record = self.json(self.private / "workers" / f"{wid}.json", worker)
            public_worker = {"schema_version": "exp-072-worker-public-v1", **VERIFY._common(), **spec,
                             "status": "Completed", "rows": 672, "output_sha256": output["sha256"], "manifest_sha256": private_record["sha256"],
                             **{key: worker[key] for key in ("replay", "disabled_modules", "scale_map_sha256", "resources", "access")}}
            public_record = self.json(self.public / "workers" / f"{wid}.json", public_worker, private=False)
            workers[wid] = {"public": public_record, "manifest": private_record, "logits": output}
        manifest = RUN.build_prediction_manifest(self.config_path, self.config, workers)
        manifest_record = self.json(self.private / "prediction-manifest.json", manifest)
        seal = RUN.build_prediction_seal(self.config_path, manifest_record, workers)
        seal_record = self.json(self.public / "prediction-seal.json", seal, private=False)
        run = {"schema_version": "exp-072-inference-run-v1", **VERIFY._common(), "tier": "Major", "rq_id": "RQ-S4.3", "stage": "run", "status": "CompletedAwaitingScore",
               **{key: claim[key] for key in ("started_at", "command", "cwd", "git", "config")}, "finished_at": "2026-08-30T00:01:00+00:00",
               "run_claim": RUN.artifact(self.public / "run-claim.json"), "prediction_seal": seal_record,
               "worker_count": 70, "a0_worker_count": 15, "total_forward_rows": 47040, "dataset": "DATA-SO-TASK-V1", "split": "train_oof", "rows": 3360,
               "labels": list(VERIFY.LABELS), "method": self.config["method"], "source_snapshot_sha256": RUN.digest(snapshot), "environment": self.config["environment"],
               "resources": {"wall_seconds": 60.0, "peak_mlx_bytes": 64, "peak_rss_bytes": 1024}, "access": dict(RUN.INFERENCE_ACCESS),
               "metrics": None, "warnings": [], "exception": None, "exp072_complete": False}
        self.json(self.public / "run.json", run, private=False)
        events = []
        for index, spec in enumerate(RUN.expected_workers(), 1):
            events.extend([{"event": "worker_started", "worker_id": spec["worker_id"]}, {"event": "worker_completed", "worker_id": spec["worker_id"], "completed_workers": index}])
        events.append({"event": "predictions_sealed", "worker_count": 70})
        self.write(self.public / "stdout.log", b"".join(RUN.canonical_json_bytes(event) for event in events), private=False)
        original_require_record = RUN.require_record
        def require_record(record):
            return Path(VERIFY.__file__).resolve() if record == {"fixture_self": True} else original_require_record(record)
        for target, name, replacement in (
            (RUN, "require_record", require_record), (RUN, "load_config", lambda path: self.config),
            (RUN, "metadata_gate", lambda *args: copy.deepcopy(self.metadata)),
            (RUN, "_import_record", lambda *args: SELECTOR), (RUN, "file_lock", lambda *args: nullcontext()),
            (SCORE, "load_runner", lambda *args: RUN), (VERIFY, "load_runner", lambda *args: RUN),
            (VERIFY, "_no_model_or_scorer_import", lambda: None),
        ):
            self.stack.enter_context(mock.patch.object(target, name, replacement))
        self.stack.enter_context(mock.patch.object(VERIFY.shutil, "disk_usage", return_value=SimpleNamespace(free=100 * 1024**3)))
        return self

    def score(self):
        return SCORE.score(self.config_path)


class IndependentScoringTests(unittest.TestCase):
    def test_worker_order_and_independent_masks(self):
        self.assertEqual(VERIFY.expected_workers(), RUN.expected_workers())
        self.assertEqual(len(VERIFY.expected_workers()), 70)
        self.assertTrue(all(row["condition"] == "A0" for row in VERIFY.expected_workers()[:15]))
        for condition, count in zip(("A0", "A1", "A2", "A3", "A4", "A5"), (0, 112, 64, 48, 56, 56)):
            mask = VERIFY.scale_map(condition)
            self.assertEqual(mask, RUN.scale_map(condition))
            self.assertEqual(sum(row["scale"] == 0 for row in mask), count)

    def test_independent_metric_formulas_and_sigmoid(self):
        gold = np.array([[1, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0]], dtype=np.uint8)
        prediction = np.array([[1, 0, 1, 0, 0, 0], [0, 0, 0, 0, 0, 0]], dtype=np.uint8)
        value = VERIFY.classification(gold, prediction)
        self.assertEqual(value["six_label_macro_f1"], 1 / 6)
        self.assertEqual(value["five_label_macro_f1"], 1 / 5)
        self.assertEqual(value["micro_f1"], 2 / 3)
        self.assertEqual(value["weighted_f1"], 1.0)
        self.assertEqual(value["hamming_loss"], 1 / 12)
        self.assertEqual(value["subset_accuracy"], 0.5)
        np.testing.assert_array_equal(VERIFY.sigmoid([-1000.0, 0.0, 1000.0]), [0.0, 0.5, 1.0])
        with self.assertRaises(ValueError):
            VERIFY.sigmoid([float("nan")])

    def test_scored_terminal_source_free_integration(self):
        with Fixture() as fixture:
            fixture.build()
            original_read = RUN.read_npz_members
            calls = []
            def read(path, names):
                calls.append((path.name, tuple(names)))
                return original_read(path, names)
            with mock.patch.object(RUN, "read_npz_members", side_effect=read):
                score = fixture.score()
                with mock.patch.object(VERIFY, "load_gold_after_gate", wraps=VERIFY.load_gold_after_gate) as labels:
                    result = VERIFY.verify(fixture.config_path)
                    self.assertEqual(labels.call_args.args[-1]["a0_replays_validated"], 15)
                    self.assertEqual(labels.call_args.args[-1]["workers_validated"], 70)
            self.assertEqual(result["status"], "Passed")
            self.assertTrue(result["complete"] and result["exp072_complete"] and result["source_unchanged"])
            self.assertEqual(result["score"], RUN.artifact(fixture.public / "score.json"))
            self.assertEqual(result["results_sha256"], RUN.digest(score["results"]))
            self.assertEqual(result["a0_replay_max_abs_error"], 0.0)
            self.assertEqual(stat.S_IMODE((fixture.public / "verification.json").stat().st_mode), 0o644)
            self.assertEqual(stat.S_IMODE((fixture.private / "scored-predictions.npz").stat().st_mode), 0o600)
            self.assertTrue(all(names == ("fold_ids", "m3_raw_thresholds") for name, names in calls if name.startswith("threshold-")))
            self.assertEqual(sum(name.endswith("-reference.npz") for name, _ in calls), 15)
            self.assertTrue(all(names == ("sample_ids", "fold_ids", "logits") for name, names in calls if name.endswith("-reference.npz")))
            with self.assertRaises(ValueError):
                VERIFY.verify(fixture.config_path)

    def test_a0_replay_failure_precedes_gold(self):
        with Fixture() as fixture:
            fixture.build(reference_delta=0.001)
            fixture.score()
            with mock.patch.object(VERIFY, "load_gold_after_gate") as labels:
                with self.assertRaisesRegex(ValueError, "independent full A0 replay"):
                    VERIFY.verify(fixture.config_path)
                labels.assert_not_called()

    def test_failed_prefix_precedes_values_and_labels(self):
        with Fixture() as fixture:
            fixture.build()
            fixture.score()
            fixture.json(fixture.public / "failure.json", {"status": "Failed"}, private=False)
            with mock.patch.object(VERIFY, "load_prediction_sources") as values, mock.patch.object(VERIFY, "load_gold_after_gate") as labels:
                with self.assertRaisesRegex(ValueError, "unexpected output prefix"):
                    VERIFY.verify(fixture.config_path)
                values.assert_not_called()
                labels.assert_not_called()

    def test_private_prediction_tamper_is_recomputed(self):
        with Fixture() as fixture:
            fixture.build()
            report = fixture.score()
            path = fixture.private / "scored-predictions.npz"
            with np.load(path, allow_pickle=False) as archive:
                arrays = {name: archive[name] for name in archive.files}
            arrays["s42_A1_prediction"][0, 0] ^= 1
            report["scored_predictions"] = fixture.write(path, npz_bytes(arrays))
            fixture.json(fixture.public / "score.json", report, private=False)
            with self.assertRaisesRegex(ValueError, "prediction value mismatch"):
                VERIFY.verify(fixture.config_path)

    def test_public_extra_key_or_mode_is_rejected(self):
        with Fixture() as fixture:
            fixture.build()
            fixture.score()
            path = fixture.public / "workers" / "s42-f0-A0.json"
            path.chmod(0o600)
            with self.assertRaisesRegex(ValueError, "mode drift"):
                VERIFY.verify(fixture.config_path)

    def test_failure_is_private_detail_public_hash_and_no_retry(self):
        with Fixture() as fixture:
            fixture.build()
            fixture.score()
            VERIFY._record_failure(fixture.config_path, ValueError("synthetic private detail"))
            public = RUN.strict_json(fixture.public / "verification.json")
            detail = fixture.private / "verification-failure.json"
            self.assertEqual(public["status"], "Failed")
            self.assertFalse(public["complete"] or public["automatic_retry"])
            self.assertNotIn("synthetic private detail", json.dumps(public))
            self.assertEqual(public["private_failure_sha256"], RUN.artifact(detail)["sha256"])
            self.assertEqual(stat.S_IMODE(detail.stat().st_mode), 0o600)
            before = (fixture.public / "verification.json").read_bytes()
            VERIFY._record_failure(fixture.config_path, ValueError("another error"))
            self.assertEqual((fixture.public / "verification.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
