"""Synthetic-only EXP-072 tests. No project data, checkpoints, or MLX loads."""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

MODULE = Path(__file__).resolve().parents[1] / "run_exp072_ablation.py"
spec = importlib.util.spec_from_file_location("exp072_under_test", MODULE)
r = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(r)
helper_spec = importlib.util.spec_from_file_location("exp072_synthetic_selector", MODULE.parent / "verify_exp071_drift.py")
h = importlib.util.module_from_spec(helper_spec)
assert helper_spec.loader is not None
helper_spec.loader.exec_module(h)


class LoRALinear:
    def __init__(self):
        self.scale = 20.0
        self.dropout = SimpleNamespace(_p_1=1.0)
        self.lora_a = np.arange(16, dtype=np.float32).reshape(2, 8)
        self.lora_b = np.arange(16, dtype=np.float32).reshape(8, 2)


class FakeModel:
    def __init__(self):
        self.modules = [(f"model.layers.{block}.{name}", LoRALinear())
                        for block in range(20, 36) for name in r.MODULES]

    def named_modules(self):
        return list(self.modules)


class SyntheticFiles(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="exp072-synthetic-")
        self.root = Path(self.temporary.name)
        self.root_patch = patch.object(r, "PROJECT_ROOT", self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temporary.cleanup()

    def write(self, relative, value, private=False):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        return r.create_json_once(path, value, private=private)

    def test_atomic_no_clobber_and_modes(self):
        path = self.root / "result.json"
        first = r.create_json_once(path, {"x": 1})
        self.assertEqual(first["mode"], "0644")
        with self.assertRaises(FileExistsError):
            r.create_json_once(path, {"x": 2})
        self.assertEqual(r.strict_json(path), {"x": 1})
        self.assertEqual(r.create_json_once(self.root / "private.json", {}, private=True)["mode"], "0600")
        self.assertFalse(list(self.root.glob("*.tmp")))

    def test_symlink_hardlink_and_traversal_rejected(self):
        self.write("file.json", {})
        (self.root / "link.json").symlink_to(self.root / "file.json")
        with self.assertRaises(ValueError):
            r.artifact(self.root / "link.json")
        os.link(self.root / "file.json", self.root / "second.json")
        with self.assertRaises(ValueError):
            r.artifact(self.root / "file.json")
        for relative in ("../file", "/tmp/file", "a/../file", "a//file"):
            with self.assertRaises(ValueError):
                r.resolve_project(relative, must_exist=False)

    def test_strict_json_duplicate_nonfinite(self):
        for index, payload in enumerate((b'{"x":1,"x":2}', b'{"x":NaN}')):
            path = self.root / f"bad-{index}.json"
            r.create_bytes_once(path, payload, private=False)
            with self.assertRaises(ValueError):
                r.strict_json(path)
        with self.assertRaises(ValueError):
            r.canonical_json_bytes({"x": float("inf")})

    def test_four_field_record_exact(self):
        record = self.write("source.json", {})
        self.assertEqual(r.require_record(record), self.root / "source.json")
        for update in ({"status": "Passed"}, {"bytes": 999}, {"mode": "0600"}):
            with self.assertRaises(ValueError):
                r.require_record({**record, **update})

    def test_persistent_flock_and_single_inode(self):
        relative = "locks/heavy.lock"
        with r.file_lock(relative):
            inode = (self.root / relative).stat().st_ino
            with self.assertRaises(BlockingIOError):
                with r.file_lock(relative):
                    pass
        self.assertTrue((self.root / relative).exists())
        with r.file_lock(relative):
            self.assertEqual((self.root / relative).stat().st_ino, inode)

    def test_compressed_npz_only_named_members(self):
        path = self.root / "source.npz"
        payload = io.BytesIO()
        np.save(payload, np.arange(5, dtype=np.int32), allow_pickle=False)
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("ordinal.npy", payload.getvalue())
            archive.writestr("gold.npy", b"not an NPY; must never be opened")
        r.create_bytes_once(path, archive_bytes.getvalue(), private=True)
        result = r.read_npz_members(path, ["ordinal"])
        np.testing.assert_array_equal(result["ordinal"], np.arange(5, dtype=np.int32))
        with self.assertRaises(ValueError):
            r.read_npz_members(path, ["gold"])

    def test_npz_duplicate_and_object_selected_rejected(self):
        object_bytes = io.BytesIO()
        np.save(object_bytes, np.array([{}], dtype=object), allow_pickle=True)
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            archive.writestr("ordinal.npy", object_bytes.getvalue())
        path = self.root / "object.npz"
        r.create_bytes_once(path, payload.getvalue(), private=True)
        with self.assertRaises(ValueError):
            r.read_npz_members(path, ["ordinal"])

    def test_selected_text_skips_gold_and_unselected_rows(self):
        # Unselected rows deliberately are not JSON. Only the selected line is parsed.
        line = {"sample_id": "synthetic-2", "labels": ["never materialize"], "text": "heldout synthetic",
                "nested": {"gold": [{"labels": "secret"}]}}
        path = self.root / "train.jsonl"
        r.create_bytes_once(path, b"unselected\n" + r.canonical_json_bytes(line) + b"unselected\n", private=True)
        calls = []
        def selector(payload, names):
            calls.append(names)
            return h.select_json_scalars(payload, names)
        rows = r.load_selected_text(path, [1], selector, expected_rows=3)
        self.assertEqual(rows, [{"ordinal": 1, "sample_id": "synthetic-2", "text": "heldout synthetic"}])
        self.assertEqual(calls, [[("sample_id",), ("text",)]])
        with self.assertRaises(ValueError):
            r.load_selected_text(path, [1, 1], selector, expected_rows=3)

    def test_row_contract_only_ordinal_fold(self):
        payload = io.BytesIO()
        np.savez_compressed(payload, ordinal=np.arange(3360, dtype=np.int32),
                            fold_id=np.repeat(np.arange(5, dtype=np.int8), 672),
                            component_code=np.array([{}], dtype=object))
        path = self.root / "rows.npz"
        r.create_bytes_once(path, payload.getvalue(), private=True)
        ordinal, folds = r.load_row_contract(path)
        self.assertEqual(ordinal.shape, (3360,))
        self.assertEqual(np.unique(folds).tolist(), list(range(5)))

    def test_budget_stops_before_limit_exceeded_continues(self):
        import time
        with patch.object(r, "_peak_rss", return_value=1):
            self.assertGreaterEqual(r.check_budget(time.monotonic(), self.root)["wall_seconds"], 0)
            with self.assertRaises(RuntimeError):
                r.check_budget(time.monotonic(), self.root, mlx_bytes=10_000_000_001)
            with self.assertRaises(RuntimeError):
                r.check_budget(time.monotonic() - 3601, self.root, worker=True)


class Contracts(unittest.TestCase):
    def test_worker_plan_exact_order_and_coverage(self):
        workers = r.expected_workers()
        self.assertEqual(len(workers), 70)
        self.assertEqual(len({value["worker_id"] for value in workers}), 70)
        self.assertEqual([value["condition"] for value in workers[:15]], ["A0"] * 15)
        self.assertNotIn("A0", [value["condition"] for value in workers[15:]])
        self.assertEqual(sum(value["seed"] == 42 for value in workers), 30)
        self.assertEqual(sum(value["seed"] == 43 for value in workers), 20)
        self.assertEqual(sum(value["seed"] == 44 for value in workers), 20)
        self.assertTrue(all(value["seed"] == 42 for value in workers if value["condition"] in {"A4", "A5"}))
        self.assertEqual(workers[0]["worker_id"], "s42-f0-A0")
        self.assertEqual(workers[14]["worker_id"], "s44-f4-A0")

    def test_scale_mask_counts_and_disjoint_depth(self):
        for condition, count in {"A0": 0, "A1": 112, "A2": 64, "A3": 48, "A4": 56, "A5": 56}.items():
            values = r.scale_map(condition)
            self.assertEqual(len(values), 112)
            self.assertEqual(sum(value["scale"] == 0 for value in values), count)
        lower = {(v["block"], v["module"]) for v in r.scale_map("A4") if v["scale"] == 0}
        upper = {(v["block"], v["module"]) for v in r.scale_map("A5") if v["scale"] == 0}
        self.assertFalse(lower & upper)
        self.assertEqual(len(lower | upper), 112)
        with self.assertRaises(ValueError):
            r.scale_map("best")

    def test_scale_only_no_tensor_mutation(self):
        model = FakeModel()
        before = [(module.lora_a.copy(), module.lora_b.copy()) for _, module in model.modules]
        self.assertEqual(r.apply_scale_map(model, "A2", apply=True), r.digest(r.scale_map("A2")))
        r.apply_scale_map(model, "A2", apply=False)
        for (_, module), (a, b) in zip(model.modules, before):
            np.testing.assert_array_equal(module.lora_a, a)
            np.testing.assert_array_equal(module.lora_b, b)
        model.modules[0][1].scale = 20.0
        with self.assertRaises(ValueError):
            r.apply_scale_map(model, "A2", apply=False)

    def test_scale_inventory_rank_dropout_initial_drift(self):
        model = FakeModel()
        model.modules.pop()
        with self.assertRaises(ValueError):
            r.apply_scale_map(model, "A0", apply=True)
        model = FakeModel()
        model.modules[0][1].dropout._p_1 = 0.9
        with self.assertRaises(ValueError):
            r.apply_scale_map(model, "A1", apply=True)
        model = FakeModel()
        model.modules[0][1].scale = 0.0
        with self.assertRaises(ValueError):
            r.apply_scale_map(model, "A1", apply=True)

    def test_a0_float32_frozen_absolute_tolerance(self):
        reference = np.zeros((672, 6), dtype=np.float32)
        observed = np.full_like(reference, 1e-6)
        result = r.replay_check(observed, reference)
        self.assertEqual(result["checked_rows"], 672)
        self.assertEqual(result["rtol"], 0.0)
        for value in (np.full_like(reference, 1.1e-5), np.full_like(reference, np.nan),
                      observed.astype(np.float64)):
            with self.assertRaises(ValueError):
                r.replay_check(value, reference)
        # Large base magnitude does not enable relative-error tolerance.
        with self.assertRaises(ValueError):
            r.replay_check(np.full_like(reference, 1000.1), np.full_like(reference, 1000.0))

    def test_import_has_no_numpy_mlx(self):
        code = ("import importlib.util,sys; "
                f"s=importlib.util.spec_from_file_location('runner',{str(MODULE)!r}); "
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m); "
                "assert 'numpy' not in sys.modules; assert 'mlx' not in sys.modules;print('ok')")
        result = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_metadata_call_graph_no_science_or_recursive_old_snapshot(self):
        tree = ast.parse(MODULE.read_text())
        functions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name in ("load_config", "metadata_gate", "require_environment"):
            source = ast.get_source_segment(MODULE.read_text(), functions[name])
            for forbidden in ("import numpy", "import mlx", "read_npz_members", "load_selected_text",
                              "source_identity_snapshot", "require_source_snapshot", "_load_train_rows", "load_selected_train_rows"):
                self.assertNotIn(forbidden, source)
        worker = ast.get_source_segment(MODULE.read_text(), functions["worker"])
        self.assertLess(worker.index("_worker_prefix("), worker.index("import numpy"))
        self.assertLess(worker.index("metadata_gate("), worker.index("import numpy"))
        self.assertNotIn("fold_manifest_private", worker)
        self.assertNotIn("m3_raw_thresholds", worker)


class SealedLifecycle(SyntheticFiles):
    def setUp(self):
        super().setUp()
        self.config_path = self.root / "config.json"
        self.public = self.root / "public"
        self.private = self.root / "private"
        self.config = {"implementation": {key: {} for key in r.IMPLEMENTATION_KEYS},
                       "environment": {"python_executable": sys.executable, "offline_environment": {}},
                       "method": copy.deepcopy(r.DEFAULT_METHOD), "source": {}}
        self.write("config.json", self.config)
        self.root_function = patch.object(r, "roots", return_value=(self.public, self.private))
        self.root_function.start()
        self.addCleanup(self.root_function.stop)
        self.sources = []
        for seed in (42, 43, 44):
            for fold in range(5):
                records = {}
                for key in ("adapter", "head", "heldout_logits"):
                    records[key] = self.write(f"inputs/{seed}-{fold}-{key}.json", {})
                self.sources.append({"seed": seed, "fold": fold, **records})
        record = self.write("sources.json", {"m3_sources": self.sources}, private=True)
        self.config["source"]["exp069_input_manifest"] = record

    def emit_worker(self, worker_spec):
        worker_id = worker_spec["worker_id"]
        out = r.create_bytes_once(self.private / "workers" / f"{worker_id}.npz", b"synthetic sealed logits", private=True)
        source = next(value for value in self.sources if (value["seed"], value["fold"]) == (worker_spec["seed"], worker_spec["fold"]))
        source_records = {name: source[key] for name, key in (("adapter", "adapter"), ("head", "head"), ("heldout", "heldout_logits"))}
        replay = ({"required": True, "checked_rows": 672, "max_abs_error": 0.0, "atol": 1e-5, "rtol": 0.0}
                  if worker_spec["condition"] == "A0" else
                  {"required": False, "checked_rows": 0, "max_abs_error": None, "atol": 1e-5, "rtol": 0.0})
        fingerprint = {key: "a" * 64 for key in ("adapter", "head", "base_sentinel")}
        manifest = {"schema_version": "exp-072-worker-private-v1", **r._common(), **worker_spec,
                    "status": "Completed", "config": r.artifact(self.config_path),
                    "input_manifest": r.artifact(self.private / "input-manifest.json"), "output": out,
                    **{key: "b" * 64 for key in ("row_order_sha256", "fold_id_sha256", "sample_id_order_sha256", "token_stream_sha256")},
                    "source_before": source_records, "source_after": source_records,
                    "tensor_before": fingerprint, "tensor_after": fingerprint,
                    "scale_map_sha256": r.digest(r.scale_map(worker_spec["condition"])),
                    "disabled_modules": sum(value["scale"] == 0 for value in r.scale_map(worker_spec["condition"])),
                    "rows": 672, "replay": replay, "resources": {"wall_seconds": 1.0, "peak_mlx_bytes": 1000, "peak_rss_bytes": 2000},
                    "access": dict(r.INFERENCE_ACCESS)}
        metadata = r.create_json_once(self.private / "workers" / f"{worker_id}.json", manifest, private=True)
        public = {"schema_version": "exp-072-worker-public-v1", **r._common(), **worker_spec,
                  "status": "Completed", "rows": 672, "output_sha256": out["sha256"], "manifest_sha256": metadata["sha256"],
                  "replay": replay, "disabled_modules": manifest["disabled_modules"],
                  "scale_map_sha256": manifest["scale_map_sha256"], "resources": manifest["resources"], "access": dict(r.INFERENCE_ACCESS)}
        r.create_json_once(self.public / "workers" / f"{worker_id}.json", public)

    def test_scheduler_all_a0_before_interventions_and_seal(self):
        order = []
        real_run = subprocess.run
        def child(command, **kwargs):
            if command[0] == "git":
                return real_run(command, **kwargs)
            worker_id = command[-1]
            spec = next(value for value in r.expected_workers() if value["worker_id"] == worker_id)
            if spec["condition"] != "A0":
                self.assertTrue(all(value["worker_id"] in order for value in r.expected_workers()[:15]))
            self.emit_worker(spec)
            order.append(worker_id)
            self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
            self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
            self.assertEqual(len(kwargs["pass_fds"]), 1)
            return SimpleNamespace(returncode=0)
        context = {"source_snapshot": {}, "source_snapshot_sha256": r.digest({}), "exp069_manifest": {"m3_sources": self.sources}}
        with patch.object(r, "metadata_gate", return_value=context), patch.object(r, "_git_identity", return_value={"commit": "synthetic", "dirty": True}), patch.object(r.subprocess, "run", side_effect=child), patch.object(r.shutil, "disk_usage", return_value=SimpleNamespace(free=100 * 1024**3)):
            result = r.run(self.config_path, self.config)
        self.assertEqual(order, [value["worker_id"] for value in r.expected_workers()])
        self.assertEqual(result["status"], "CompletedAwaitingScore")
        seal = r.strict_json(self.public / "prediction-seal.json")
        manifest = r.strict_json(self.private / "prediction-manifest.json")
        self.assertEqual(seal["worker_inventory_sha256"], r.digest(manifest["workers"]))
        self.assertEqual(manifest["worker_count"], 70)
        self.assertFalse(seal["labels_accessed"])
        self.assertFalse(result["exp072_complete"])
        with self.assertRaises(FileExistsError):
            r.run(self.config_path, self.config)

    def test_scheduler_failure_stops_no_seal_no_retry(self):
        called = []
        def child(command, **kwargs):
            worker_id = command[-1]
            called.append(worker_id)
            if len(called) == 2:
                return SimpleNamespace(returncode=1)
            self.emit_worker(r.expected_workers()[0])
            return SimpleNamespace(returncode=0)
        context = {"source_snapshot": {}, "source_snapshot_sha256": r.digest({}), "exp069_manifest": {"m3_sources": self.sources}}
        with patch.object(r, "metadata_gate", return_value=context), patch.object(r, "_git_identity", return_value={"commit": "synthetic", "dirty": True}), patch.object(r.subprocess, "run", side_effect=child), patch.object(r.shutil, "disk_usage", return_value=SimpleNamespace(free=100 * 1024**3)):
            with self.assertRaises(RuntimeError):
                r.run(self.config_path, self.config)
        self.assertEqual(called, ["s42-f0-A0", "s42-f1-A0"])
        self.assertEqual(r.strict_json(self.public / "failure.json")["status"], "Failed")
        self.assertFalse((self.public / "prediction-seal.json").exists())
        self.assertTrue((self.private / "workers/s42-f0-A0.npz").exists())

    def test_worker_public_extras_rejected(self):
        r._mkdir_root(self.public, private=False)
        r._mkdir_root(self.private, private=True)
        r.create_json_once(self.private / "input-manifest.json", {"fold_sources": self.sources}, private=True)
        worker_spec = r.expected_workers()[0]
        self.emit_worker(worker_spec)
        self.assertEqual(set(r.validate_worker(self.config, self.config_path, worker_spec)), {"public", "manifest", "logits"})
        path = self.public / "workers/s42-f0-A0.json"
        value = r.strict_json(path)
        value["text"] = "synthetic forbidden field"
        # Deliberate test corruption, never used for real append-only outputs.
        path.write_bytes(r.canonical_json_bytes(value))
        with self.assertRaises(ValueError):
            r.validate_worker(self.config, self.config_path, worker_spec)

    def test_prediction_manifest_incomplete_rejected(self):
        with self.assertRaises(ValueError):
            r.build_prediction_manifest(self.config_path, self.config, {})
        with self.assertRaises(ValueError):
            r.build_prediction_seal(self.config_path, {}, {})

    def test_real_worker_function_fake_mlx_reference_and_output_integration(self):
        """Exercise worker's actual data path with only synthetic arrays/model APIs."""
        r._mkdir_root(self.public, private=False)
        r._mkdir_root(self.private, private=True)
        worker_spec = r.expected_workers()[0]
        source = self.sources[0]
        train_path = self.root / "train.jsonl"
        rows = [{"sample_id": f"synthetic-{i}", "text": str(i + 1), "labels": ["not decoded"]} for i in range(672)]
        train_record = r.create_bytes_once(train_path, b"".join(r.canonical_json_bytes(row) for row in rows) + b"not decoded\n" * 2688, private=True)
        prompt_record = self.write("prompt.json", {})
        row_bytes = io.BytesIO()
        np.savez_compressed(row_bytes, ordinal=np.arange(3360, dtype=np.int32), fold_id=np.repeat(np.arange(5, dtype=np.int8), 672),
                            component_code=np.array([{}], dtype=object))
        row_record = r.create_bytes_once(self.root / "row-contract.npz", row_bytes.getvalue(), private=True)
        self.config["source"]["exp070_row_contract"] = row_record
        self.config["source"]["helpers"] = {key: {"kind": key} for key in ("exp069", "exp070", "selective_json")}
        (self.root / "base").mkdir()
        context = {"source_snapshot": {}, "source_snapshot_sha256": r.digest({}),
                   "original_config": {"data": {"train": train_record}, "model": {"prompt": prompt_record, "base_path": "base"}},
                   "exp069_manifest": {"m3_sources": self.sources}}
        input_manifest = {"source_snapshot": {}, "source_snapshot_sha256": r.digest({}), "fold_sources": self.sources}
        r.create_json_once(self.private / "input-manifest.json", input_manifest, private=True)
        fake_model = FakeModel()
        adapter = {name + suffix: getattr(module, suffix[1:]) for name, module in fake_model.modules for suffix in (".lora_a", ".lora_b")}
        base = {f"base.{i:02d}.weight": np.arange(12, dtype=np.float32).reshape(3, 4) for i in range(16)}
        fake_model.freeze = lambda: None
        fake_model.eval = lambda: None
        fake_model.load_weights = lambda *a, **kw: None
        fake_model.trainable_parameters = lambda: adapter
        fake_model.parameters = lambda: {**base, **adapter}
        forwards = []
        def hidden(ids):
            forwards.append(int(ids[0, 0]))
            value = np.zeros((1, 1, 2560), dtype=np.float32)
            value[0, 0, 0] = ids[0, 0]
            return value
        fake_model.model = hidden
        weights = np.zeros((6, 2560), dtype=np.float32)
        weights[:, 0] = np.arange(1, 7, dtype=np.float32)
        bias = np.zeros(6, dtype=np.float32)
        class Head:
            def __init__(self, inputs, outputs, bias=True):
                self.weight = weights.copy()
                self.bias = np.zeros(6, dtype=np.float32)
            def __call__(self, value):
                return value @ self.weight.T + self.bias
            def eval(self):
                pass
            def load_weights(self, *args, **kwargs):
                pass
            def parameters(self):
                return {"weight": self.weight, "bias": self.bias}
        mx = ModuleType("mlx.core")
        mx.array, mx.float32, mx.int32 = np.array, np.float32, np.int32
        mx.eval = lambda *values: None
        mx.reset_peak_memory = lambda: None
        mx.get_peak_memory = lambda: 1024
        mx.random = SimpleNamespace(seed=lambda seed: None)
        mlx = ModuleType("mlx")
        mlx.__path__ = []
        mlx.core = mx
        nn = ModuleType("mlx.nn")
        nn.Linear = Head
        utils = ModuleType("mlx.utils")
        utils.tree_flatten = lambda value: list(value.items())
        lm = ModuleType("mlx_lm")
        lm.__path__ = []
        lm.load = lambda path, lazy: (fake_model, object())
        tuner = ModuleType("mlx_lm.tuner")
        tuner.linear_to_lora_layers = lambda *a, **kw: None
        safetensors = ModuleType("safetensors")
        safetensors.__path__ = []
        safe_np = ModuleType("safetensors.numpy")
        safe_np.load_file = lambda path: ({"weight": weights, "bias": bias} if path.endswith("42-0-head.json") else adapter)
        modules = {"mlx": mlx, "mlx.core": mx, "mlx.nn": nn, "mlx.utils": utils, "mlx_lm": lm,
                   "mlx_lm.tuner": tuner, "safetensors": safetensors, "safetensors.numpy": safe_np}
        reference_order = list(reversed(range(672)))
        reference_index = {f"synthetic-{ordinal}": index for index, ordinal in enumerate(reference_order)}
        reference = np.array([[(ordinal + 1) * (j + 1) for j in range(6)] for ordinal in reference_order], dtype=np.float32)
        helper69 = SimpleNamespace(lora_identity=lambda model: r.apply_scale_map(model, "A0", apply=False),
                                   qwen_prompt_ids=lambda tokenizer, prompt, text, limit: ([int(text)], 1, False),
                                   token_stream_digest=lambda pairs: r.digest(pairs))
        helper70 = SimpleNamespace(_load_reference=lambda path, fold: (reference_index, np.zeros(672, dtype=np.int8), reference))
        helpers = {"exp069": helper69, "exp070": helper70, "selective_json": h}
        with patch.object(r, "_worker_prefix", return_value=({}, input_manifest)), patch.object(r, "metadata_gate", return_value=context), patch.object(r, "_import_record", side_effect=lambda record, name: helpers[record["kind"]]), patch.dict(sys.modules, modules):
            public_value = r.worker(self.config_path, self.config, "s42-f0-A0")
        self.assertEqual(forwards, list(range(1, 673)))
        self.assertEqual(public_value["replay"]["max_abs_error"], 0.0)
        arrays = r.read_npz_members(self.private / "workers/s42-f0-A0.npz", ["ordinal", "fold_id", "logits"])
        np.testing.assert_array_equal(arrays["ordinal"], np.arange(672, dtype=np.int32))
        np.testing.assert_array_equal(arrays["logits"], reference[::-1])
        manifest = r.strict_json(self.private / "workers/s42-f0-A0.json")
        self.assertEqual(manifest["sample_id_order_sha256"], r.string_digest([f"synthetic-{i}" for i in range(672)]))
        self.assertEqual(manifest["tensor_before"], manifest["tensor_after"])
        self.assertFalse(manifest["access"]["labels_accessed"])
        r.validate_worker(self.config, self.config_path, worker_spec)


if __name__ == "__main__":
    unittest.main()
