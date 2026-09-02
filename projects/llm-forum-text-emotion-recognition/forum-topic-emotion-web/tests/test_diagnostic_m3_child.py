"""Only synthetic Python frames and fake memory getters; no model imports."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("diagnostic_m3_child", ROOT / "scripts/diagnostic_m3_child.py")
CHILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHILD)


class ListJournal:
    def __init__(self):
        self.events = []

    def emit(self, kind, stage, ordinal, memory):
        self.events.append({"kind": kind, "stage": stage, "item_ordinal": ordinal, "memory": memory})


def synthetic(source):
    scope = {}
    exec(compile(source, "synthetic-exp082.py", "exec"), scope)
    return scope


def key(function):
    code = function.__code__
    return code.co_filename, code.co_qualname, code.co_firstlineno


def run_trace(trace, function, *args):
    prior = sys.gettrace()
    try:
        sys.settrace(trace)
        return function(*args)
    finally:
        sys.settrace(prior)


class TraceTests(unittest.TestCase):
    def test_nested_stages_seven_ordinals_and_no_locals_or_values(self):
        scope = synthetic("def predict(secret):\n    return backend(secret)\ndef backend(secret):\n    return [0.123, secret]\n")
        journal = ListJournal()
        trace = CHILD.StageTrace(journal, functions={key(scope["predict"]): "request_predict",
                                                    key(scope["backend"]): "m1_predict"}, lines={})
        for index in range(7):
            self.assertEqual(run_trace(trace, scope["predict"], "DO-NOT-LOG"), [0.123, "DO-NOT-LOG"])
            current = journal.events[index * 5:(index + 1) * 5]
            self.assertEqual([(row["kind"], row["stage"]) for row in current],
                             [("begin", "request_predict"), ("begin", "m1_predict"),
                              ("end", "m1_predict"), ("end", "request_predict"), ("point", "predict_complete")])
            self.assertEqual({row["item_ordinal"] for row in current}, {index})
        self.assertIsNone(trace.ordinal)
        self.assertFalse(trace.frames)
        self.assertNotIn("DO-NOT-LOG", json.dumps(journal.events))
        self.assertNotIn("0.123", json.dumps(journal.events))
        with self.assertRaises(CHILD.ObservationError):
            run_trace(trace, scope["predict"], "DO-NOT-LOG")

    def test_unwind_none_and_finally_are_error_not_success(self):
        for source in (
            "def run():\n    raise ValueError('PRIVATE-ERROR')\n",
            "def run():\n    try:\n        raise ValueError('PRIVATE-ERROR')\n    finally:\n        a = 3\n",
        ):
            function = synthetic(source)["run"]
            journal = ListJournal()
            trace = CHILD.StageTrace(journal, functions={key(function): "request_predict"},
                                     lines={key(function): {2: (("begin", "base_load"),)}})
            with self.assertRaises(ValueError):
                run_trace(trace, function)
            self.assertEqual([(row["kind"], row["stage"]) for row in journal.events],
                             [("begin", "request_predict"), ("begin", "base_load"),
                              ("error", "base_load"), ("error", "request_predict")])
            self.assertNotIn("PRIVATE-ERROR", json.dumps(journal.events))
            self.assertIsNone(trace.ordinal)

    def test_normal_none_and_handled_exception_end_successfully(self):
        for source in ("def run():\n    pass\n",
                       "def run():\n    try:\n        raise ValueError()\n    except ValueError:\n        pass\n"):
            function = synthetic(source)["run"]
            journal = ListJournal()
            trace = CHILD.StageTrace(journal, functions={key(function): "m1_load"}, lines={})
            self.assertIsNone(run_trace(trace, function))
            self.assertEqual([row["kind"] for row in journal.events], ["begin", "end"])

    def test_line_regions_and_getters_start_only_after_limit_marker(self):
        scope = synthetic("def run():\n    a = 1\n    a = 2\n    a = 3\n    return None\n")
        function = scope["run"]
        calls = []
        def getter(value):
            calls.append(value)
            return value
        fake = SimpleNamespace(get_active_memory=lambda: getter(10), get_cache_memory=lambda: getter(20),
                               get_peak_memory=lambda: getter(30))
        journal = ListJournal()
        trace = CHILD.StageTrace(journal, functions={key(function): "m3_factory"}, lines={key(function): {
            2: (("begin", "base_load"),),
            3: (("end", "base_load"), ("point", "mlx_limits_configured")),
            4: (("begin", "adapter_head_eval"),),
        }})
        with patch.dict(sys.modules, {"mlx.core": fake}):
            run_trace(trace, function)
        before, after = journal.events[:3], journal.events[3:]
        self.assertTrue(all(row["memory"]["mlx_status"] == "not_sampled" for row in before))
        self.assertTrue(all(row["memory"]["mlx_status"] == "observed" for row in after))
        self.assertEqual(len(calls), 3 * len(after))
        self.assertEqual([(row["kind"], row["stage"]) for row in journal.events[-2:]],
                         [("end", "adapter_head_eval"), ("end", "m3_factory")])

    def test_unobserved_or_failed_memory_is_null_not_zero(self):
        observer = CHILD.MemoryObserver()
        with patch.dict(sys.modules, {"mlx.core": None}):
            self.assertEqual(observer.read()["mlx_status"], "not_loaded")
        observer.limits_configured = True
        for fake in (SimpleNamespace(), SimpleNamespace(get_active_memory=lambda: -1,
                     get_cache_memory=lambda: 0, get_peak_memory=lambda: 0)):
            with patch.dict(sys.modules, {"mlx.core": fake}):
                result = observer.read()
            self.assertEqual(result["mlx_status"], "not_sampled")
            self.assertTrue(all(result[name] is None for name in ("active_bytes", "cache_bytes", "peak_bytes")))

    def test_trace_ignores_other_filename_and_unregistered_function(self):
        function = synthetic("def run():\n    return 'unrelated'\n")["run"]
        journal = ListJournal()
        trace = CHILD.StageTrace(journal)
        self.assertEqual(run_trace(trace, function), "unrelated")
        self.assertEqual(journal.events, [])

    def test_observed_resource_breach_is_recorded_before_original_step(self):
        for changes in ({"rss_peak_bytes": 12 * 1024**3 + 1},
                        {"mlx_status": "observed", "active_bytes": 1,
                         "cache_bytes": 0, "peak_bytes": 10_000_000_001}):
            scope = synthetic("def run():\n    executed.append(True)\n")
            scope["executed"] = []
            snapshot = {"rss_peak_bytes": 1000, "mlx_status": "not_loaded",
                        "active_bytes": None, "cache_bytes": None, "peak_bytes": None}
            snapshot.update(changes)
            journal = ListJournal()
            memory = SimpleNamespace(read=lambda: snapshot)
            trace = CHILD.StageTrace(journal, memory=memory,
                                     functions={key(scope["run"]): "engine_build"}, lines={})
            with self.assertRaisesRegex(CHILD.ObservationError, "^diagnostic_resource_limit$"):
                run_trace(trace, scope["run"])
            self.assertEqual(len(journal.events), 1)
            self.assertEqual(journal.events[0]["memory"], snapshot)
            self.assertEqual(scope["executed"], [])

    def test_after_limits_failed_getters_are_recorded_and_stop_before_next_step(self):
        scope = synthetic("def run():\n    executed.append(True)\n")
        scope["executed"] = []
        memory = CHILD.MemoryObserver()
        memory.limits_configured = True
        journal = ListJournal()
        trace = CHILD.StageTrace(journal, memory=memory,
                                 functions={key(scope["run"]): "m3_backend_init"}, lines={})
        with patch.dict(sys.modules, {"mlx.core": SimpleNamespace()}):
            with self.assertRaisesRegex(CHILD.ObservationError, "^diagnostic_memory_unknown$"):
                run_trace(trace, scope["run"])
        self.assertEqual(len(journal.events), 1)
        self.assertEqual(journal.events[0]["memory"]["mlx_status"], "not_sampled")
        self.assertTrue(all(journal.events[0]["memory"][name] is None
                            for name in ("active_bytes", "cache_bytes", "peak_bytes")))
        self.assertEqual(scope["executed"], [])


class JournalTests(unittest.TestCase):
    def test_existing_private_empty_file_complete_records_and_fsync(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp).resolve() / "stages.jsonl"
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            journal = CHILD.StageJournal(path)
            with patch.object(CHILD.os, "fsync", wraps=os.fsync) as synced:
                journal.emit("begin", "engine_build", None, CHILD.MemoryObserver().read())
                journal.emit("end", "engine_build", None, CHILD.MemoryObserver().read())
                self.assertEqual(synced.call_count, 2)
            journal.close()
            raw = path.read_bytes()
            self.assertTrue(raw.endswith(b"\n"))
            rows = [json.loads(line) for line in raw.splitlines()]
            self.assertEqual([row["seq"] for row in rows], [0, 1])
            self.assertEqual(set(rows[0]), {"seq", "pid", "monotonic", "kind", "stage", "item_ordinal", "memory"})
            self.assertEqual(set(rows[0]["memory"]), {"rss_peak_bytes", "mlx_status", "active_bytes", "cache_bytes", "peak_bytes"})
            with self.assertRaises(CHILD.ObservationError):
                CHILD.StageJournal(path)

    def test_rejects_missing_symlink_directory_and_nonprivate_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            with self.assertRaises(FileNotFoundError):
                CHILD.StageJournal(root / "missing.jsonl")
            target = root / "target.jsonl"
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.close(fd)
            target.chmod(0o644)
            link = root / "link.jsonl"
            link.symlink_to(target)
            for path in (target, link, root):
                with self.assertRaises(CHILD.ObservationError):
                    CHILD.StageJournal(path)


class FrozenMappingTests(unittest.TestCase):
    def test_hashes_and_exact_function_keys_match_python_source_without_import(self):
        CHILD.check_sources()
        found = set()
        def walk(node, path, prefix=""):
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    qualname = prefix + item.name
                    if isinstance(item, ast.FunctionDef):
                        found.add((str(path), qualname, item.lineno))
                    walk(item, path, qualname + (".<locals>." if isinstance(item, ast.FunctionDef) else "."))
                else:
                    walk(item, path, prefix)
        for path in CHILD.SOURCE_HASHES:
            walk(ast.parse(path.read_text()), path)
        self.assertTrue(set(CHILD.FUNCTION_STAGES) <= found)
        bridge = CHILD.BRIDGE.read_text().splitlines()
        self.assertIn("mx.set_memory_limit", bridge[392])
        self.assertIn("mx.set_cache_limit", bridge[393])
        self.assertIn("runtime.MlxM3Backend", bridge[394])
        runtime = CHILD.RUNTIME.read_text().splitlines()
        self.assertIn("lazy=False", runtime[256])
        self.assertIn("linear_to_lora_layers", runtime[274])
        self.assertIn("mx.eval(*parameters)", runtime[320])
        self.assertIn("self._mx.eval(logits)", runtime[327])

    def test_actual_phase_python_runs_only_the_same_synthetic_stdlib_tests(self):
        if sys.version_info[:2] == (3, 11):
            self.assertEqual(sys.version_info[:3], (3, 11, 15))
            self.assertFalse(any(name.split(".")[0] in {"mlx", "torch", "transformers", "mlx_lm"}
                                 for name in sys.modules))
            return
        result = subprocess.run(
            ["/Users/phoenix/miniconda3/envs/phase-a-runtime/bin/python", "-I", "-B", str(Path(__file__).resolve())],
            capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
