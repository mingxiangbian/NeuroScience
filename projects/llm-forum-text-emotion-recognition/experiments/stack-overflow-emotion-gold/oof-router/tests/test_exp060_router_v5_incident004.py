from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


MODULE_DIR = Path(__file__).resolve().parents[1]
RECOVERY_PATH = MODULE_DIR / "verify_exp060_router_v5_incident004.py"


def load_module():
    spec = importlib.util.spec_from_file_location("exp060_incident004_tests", RECOVERY_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(RECOVERY_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RECOVERY = load_module()


class Incident004RecoveryTests(unittest.TestCase):
    def test_live_snapshot_parity_reproduces_run_seal(self) -> None:
        runner, verifier, canonical, config, digest = RECOVERY._prepare(
            RECOVERY.CONFIG_PATH
        )
        normalized = RECOVERY.normalize_snapshot(
            verifier._immutable_snapshot(canonical, config), config
        )
        expected = runner._immutable_snapshot(canonical, config)
        self.assertTrue(RECOVERY._typed_equal(normalized, expected))
        self.assertEqual(
            digest,
            "2538d77098d13ab0ebeef7c0ed12e9cdd76a116f5126dbd256080f4b9d07ba2f",
        )

    def test_normalizer_rejects_missing_extra_and_collision_keys(self) -> None:
        runner, verifier, canonical, config, _ = RECOVERY._prepare(RECOVERY.CONFIG_PATH)
        raw = verifier._immutable_snapshot(canonical, config)
        for mutation in ("missing", "extra", "collision"):
            candidate = copy.deepcopy(raw)
            if mutation == "missing":
                candidate.pop("input")
            elif mutation == "extra":
                candidate["unexpected"] = None
            else:
                candidate["input.paired_oof"] = candidate["input"]
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(ValueError, "inventory drift"):
                    RECOVERY.normalize_snapshot(candidate, config)
        self.assertIsNotNone(runner)

    def test_loaded_execution_patches_only_snapshot_and_restores(self) -> None:
        runner, verifier, canonical, config, _ = RECOVERY._prepare(RECOVERY.CONFIG_PATH)
        original_snapshot = verifier._immutable_snapshot
        calls = 0

        def fake_execute(path, scope):
            nonlocal calls
            calls += 1
            self.assertEqual(path, canonical)
            self.assertEqual(scope, "final")
            observed = verifier._immutable_snapshot(path, config)
            expected = runner._immutable_snapshot(path, config)
            self.assertTrue(RECOVERY._typed_equal(observed, expected))
            return {
                "status": "Passed",
                "passed_count": 1,
                "failed_count": 0,
                "checks": [{"name": "synthetic", "passed": True, "detail": None}],
            }

        verifier.execute = fake_execute
        result = RECOVERY._execute_loaded(
            runner, verifier, canonical, config, "final"
        )
        self.assertEqual(result["status"], "Passed")
        self.assertEqual(calls, 1)
        self.assertIs(verifier._immutable_snapshot, original_snapshot)

    def test_baseexception_restores_snapshot_patch(self) -> None:
        runner, verifier, canonical, config, _ = RECOVERY._prepare(RECOVERY.CONFIG_PATH)
        original_snapshot = verifier._immutable_snapshot

        def interrupted(path, scope):
            verifier._immutable_snapshot(path, config)
            raise KeyboardInterrupt

        verifier.execute = interrupted
        with self.assertRaises(KeyboardInterrupt):
            RECOVERY._execute_loaded(runner, verifier, canonical, config, "final")
        self.assertIs(verifier._immutable_snapshot, original_snapshot)

    def test_wrapper_has_no_runner_execute_or_selection_scope(self) -> None:
        source = RECOVERY_PATH.read_text(encoding="utf-8")
        self.assertNotIn("runner.execute", source)
        self.assertNotIn('"selection"', source)
        self.assertEqual(set(RECOVERY.parse_args.__annotations__), {"return"})


if __name__ == "__main__":
    unittest.main()

