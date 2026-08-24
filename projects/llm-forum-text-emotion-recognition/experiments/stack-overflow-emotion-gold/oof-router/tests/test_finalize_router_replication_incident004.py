from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1]
FINALIZER_PATH = MODULE_DIR / "finalize_router_replication_incident004.py"


def load_module():
    spec = importlib.util.spec_from_file_location("incident004_finalizer_tests", FINALIZER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(FINALIZER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FINALIZER = load_module()


class Incident004FinalizerTests(unittest.TestCase):
    def test_live_prerequisites_and_selection_build(self) -> None:
        value = FINALIZER.build_selection()
        self.assertEqual(value["status"], "Selected")
        self.assertEqual(value["decision"], "Pass")
        self.assertEqual(value["verification_attempt"], 2)
        self.assertEqual(set(value["formal_governance"]), {
            "run", "final", "complete", "completion",
        })

    def test_payload_tamper_is_rejected(self) -> None:
        value = FINALIZER.build_selection()
        mutations = (
            lambda row: row.__setitem__("model_seed", 43),
            lambda row: row.__setitem__("decision", "Fail"),
            lambda row: row["completions"]["router"].__setitem__("sha256", "0" * 64),
            lambda row: row["incident_004"].pop("recovery_wrapper"),
        )
        for mutation in mutations:
            candidate = copy.deepcopy(value)
            mutation(candidate)
            with self.subTest(candidate=candidate.get("decision")):
                with self.assertRaises(ValueError):
                    FINALIZER.validate_selection(candidate, require_live_selection=False)

    def test_no_clobber_writer_uses_regular_0644(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "selection.json"
            FINALIZER.create_json_once(path, {"status": "Selected"})
            metadata = os.lstat(path)
            self.assertTrue(stat.S_ISREG(metadata.st_mode))
            self.assertEqual(stat.S_IMODE(metadata.st_mode), 0o644)
            self.assertEqual(metadata.st_nlink, 1)
            self.assertEqual(json.loads(path.read_text()), {"status": "Selected"})
            with self.assertRaises(FileExistsError):
                FINALIZER.create_json_once(path, {"status": "Other"})

    def test_source_does_not_delete_or_overwrite(self) -> None:
        source = FINALIZER_PATH.read_text(encoding="utf-8")
        for forbidden in ("unlink(", "remove(", "replace(", "rename(", "rmtree("):
            self.assertNotIn(forbidden, source)
        self.assertIn("os.O_EXCL", source)


if __name__ == "__main__":
    unittest.main()

