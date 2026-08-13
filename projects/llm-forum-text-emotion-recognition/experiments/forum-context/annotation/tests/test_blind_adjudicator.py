from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ANNOTATION_DIR = Path(__file__).resolve().parents[1]
ADJUDICATOR_DIR = ANNOTATION_DIR / "blind_adjudicator"
sys.path.insert(0, str(ANNOTATION_DIR))

from blind_adjudicator.core import (  # noqa: E402
    AdjudicationConflict,
    AdjudicationError,
    BlindAdjudicationStore,
    CASE_SCHEMA_VERSION,
    PROTOCOL_ID,
    canonical_case_sha256,
)
from blind_adjudicator.server import (  # noqa: E402
    AdjudicationRequestHandler,
    LocalAdjudicationServer,
    parse_args,
)
import build_blind_adjudication_v1 as builder  # noqa: E402


def labeled(emotion: str, other: str | None = None) -> dict:
    return {
        "status": "labeled",
        "primary_emotion": emotion,
        "other_emotion_text": other,
    }


def non_labeled(status: str) -> dict:
    return {
        "status": status,
        "primary_emotion": None,
        "other_emotion_text": None,
    }


def make_case(index: int) -> dict:
    case = {
        "schema_version": CASE_SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "blind_case_id": f"{index:03d}",
        "content": {
            "discussion_title": f"PRIVATE_TITLE_{index}",
            "direct_parent_body": f"PRIVATE_PARENT_{index}",
            "target_quotes": [f"PRIVATE_QUOTE_{index}"],
            "target_full_with_quotes": f"PRIVATE_TARGET_{index}",
        },
        "candidates": [
            {"alias": "candidate_a", "decision": labeled("frustration")},
            {"alias": "candidate_b", "decision": labeled("anger")},
            {"alias": "candidate_c", "decision": non_labeled("unclear")},
        ],
    }
    case["case_sha256"] = canonical_case_sha256(case)
    return case


def phase_one_judgment() -> dict:
    return {
        "emotion_presence": "clear_emotion",
        "stance": "oppose",
        "unit_validity": "valid_single_unit",
        "independent_decision": labeled("frustration"),
        "confidence": "medium",
        "note": None,
    }


def phase_two_judgment() -> dict:
    return {
        "candidate_assessments": {
            "candidate_a": "supported",
            "candidate_b": "acceptable_but_not_primary",
            "candidate_c": "unsupported",
        },
        "resolution": "final_decision",
        "final_decision": labeled("frustration"),
        "primary_reason": "anger_vs_frustration",
        "note": None,
    }


class StoreFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.bundle = self.root / "bundle.jsonl"
        self.records = self.root / "records"
        self.bundle.write_text(
            "".join(
                json.dumps(make_case(index), ensure_ascii=False) + "\n"
                for index in range(1, 3)
            ),
            encoding="utf-8",
        )
        self.bundle.chmod(0o600)
        self.store = BlindAdjudicationStore(
            self.bundle,
            self.records,
            expected_total=2,
            dataset_mode="synthetic",
        )

    def tearDown(self) -> None:
        self.store.close()
        self.temporary.cleanup()


class BlindAdjudicationStoreTests(StoreFixture):
    def test_phase_one_response_contains_no_candidates(self) -> None:
        response = self.store.current()
        serialized = json.dumps(response)

        self.assertEqual(response["stage"], "phase_1")
        self.assertNotIn("candidates", response)
        self.assertNotIn("candidate_a", serialized)
        self.assertNotIn("model_01", serialized)
        self.assertNotIn("source", serialized)

    def test_phase_one_lock_reveals_only_anonymous_candidates(self) -> None:
        current = self.store.current()
        response = self.store.submit_phase_1(
            current["case_id"], phase_one_judgment()
        )
        serialized = json.dumps(response)

        self.assertEqual(response["stage"], "phase_2")
        self.assertTrue(response["phase_1_locked"])
        self.assertEqual(
            [candidate["alias"] for candidate in response["candidates"]],
            ["candidate_a", "candidate_b", "candidate_c"],
        )
        self.assertNotIn("model_01", serialized)
        self.assertNotIn("model_02", serialized)
        self.assertNotIn("sample_uid", serialized)
        with self.assertRaisesRegex(AdjudicationConflict, "already locked"):
            self.store.submit_phase_1(current["case_id"], phase_one_judgment())

    def test_phase_two_completion_is_atomic_and_resumable(self) -> None:
        first = self.store.current()
        self.store.submit_phase_1(first["case_id"], phase_one_judgment())
        next_state = self.store.submit_phase_2(
            first["case_id"], phase_two_judgment()
        )

        self.assertEqual(next_state["case_id"], "002")
        self.assertEqual(next_state["stage"], "phase_1")
        record_path = self.records / "001.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual(
            record["phase_2"]["final_decision"]["primary_emotion"],
            "frustration",
        )
        self.assertIsNotNone(record["completed_at"])
        self.assertEqual(os.stat(record_path).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(self.records).st_mode & 0o777, 0o700)

        replacement = BlindAdjudicationStore(
            self.bundle,
            self.records,
            expected_total=2,
            dataset_mode="synthetic",
        )
        try:
            resumed = replacement.current()
            self.assertEqual(resumed["case_id"], "002")
            self.assertEqual(resumed["stage"], "phase_1")
        finally:
            replacement.close()

    def test_no_stable_gold_requires_note(self) -> None:
        first = self.store.current()
        self.store.submit_phase_1(first["case_id"], phase_one_judgment())
        judgment = phase_two_judgment()
        judgment.update(
            {
                "resolution": "no_stable_gold",
                "final_decision": None,
                "primary_reason": "multi_segment_or_mixed",
                "note": None,
            }
        )
        with self.assertRaisesRegex(AdjudicationError, "requires a note"):
            self.store.submit_phase_2(first["case_id"], judgment)

    def test_session_limit_stops_after_completed_case(self) -> None:
        self.store.session_limit = 1
        first = self.store.current()
        self.store.submit_phase_1(first["case_id"], phase_one_judgment())
        state = self.store.submit_phase_2(first["case_id"], phase_two_judgment())

        self.assertEqual(state["state"], "session_break")
        resumed = self.store.start_session()
        self.assertEqual(resumed["case_id"], "002")


class BlindAdjudicationHTTPTests(StoreFixture):
    def setUp(self) -> None:
        super().setUp()
        self.static_dir = ADJUDICATOR_DIR / "static"
        self.server = LocalAdjudicationServer(
            ("127.0.0.1", 0),
            AdjudicationRequestHandler,
            store=self.store,
            static_dir=self.static_dir,
            csrf_token="test-token",
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        super().tearDown()

    def request(self, path: str, *, body: dict | None = None, token: bool = True):
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
            headers["Origin"] = self.base_url
            if token:
                headers["X-Adjudication-Token"] = "test-token"
        request = Request(self.base_url + path, data=data, headers=headers)
        return urlopen(request, timeout=2)

    def test_http_phase_gate_and_security_headers(self) -> None:
        with self.request("/api/current") as response:
            raw = response.read().decode("utf-8")
            phase_one = json.loads(raw)
            self.assertEqual(phase_one["stage"], "phase_1")
            self.assertNotIn("candidate_a", raw)
            self.assertEqual(response.headers["Cache-Control"], "no-store, max-age=0")
            self.assertIn(
                "default-src 'self'", response.headers["Content-Security-Policy"]
            )

        with self.request(
            "/api/phase-1",
            body={
                "case_id": phase_one["case_id"],
                "judgment": phase_one_judgment(),
            },
        ) as response:
            phase_two = json.loads(response.read().decode("utf-8"))
            self.assertEqual(phase_two["stage"], "phase_2")
            self.assertEqual(len(phase_two["candidates"]), 3)

    def test_http_rejects_missing_token_and_unknown_paths(self) -> None:
        phase_one = json.loads(self.request("/api/current").read().decode("utf-8"))
        with self.assertRaises(HTTPError) as missing_token:
            self.request(
                "/api/phase-1",
                body={
                    "case_id": phase_one["case_id"],
                    "judgment": phase_one_judgment(),
                },
                token=False,
            )
        try:
            self.assertEqual(missing_token.exception.code, 403)
        finally:
            missing_token.exception.close()

        with self.assertRaises(HTTPError) as traversal:
            self.request("/%2e%2e/%2e%2e/source-map.jsonl")
        try:
            self.assertEqual(traversal.exception.code, 404)
        finally:
            traversal.exception.close()

    def test_static_and_server_have_no_source_mapping_route(self) -> None:
        for filename in ("index.html", "styles.css", "app.js"):
            content = (self.static_dir / filename).read_text(encoding="utf-8")
            self.assertNotIn("https://", content)
            self.assertNotIn("http://", content)
            self.assertNotIn("model_01", content)
            self.assertNotIn("model_02", content)
        server_source = (ADJUDICATOR_DIR / "server.py").read_text(encoding="utf-8")
        self.assertNotIn("source-map", server_source)
        self.assertNotIn("source_map", server_source)


def make_builder_row(index: int, stage_a: dict, human: dict, model_01: dict, model_02: dict) -> dict:
    suffix = f"{index:064x}"
    return {
        "annotation_order": index,
        "sample_uid": f"smp_{suffix}",
        "view_sha256": "0" * 64,
        "lane": "representative",
        "stage_a": {
            "human": stage_a,
            "model_01": stage_a,
            "model_02": stage_a,
        },
        "stage_b": {
            "human": human,
            "model_01": model_01,
            "model_02": model_02,
        },
    }


def synthetic_builder_rows() -> list[dict]:
    rows = []
    index = 1
    for _ in range(15):
        human = labeled("other_emotion", "disapproval")
        rows.append(make_builder_row(index, human, human, labeled("neutral"), labeled("neutral")))
        index += 1
    for _ in range(10):
        rows.append(
            make_builder_row(
                index,
                labeled("anger"),
                labeled("anger"),
                labeled("frustration"),
                labeled("neutral"),
            )
        )
        index += 1
    for _ in range(8):
        rows.append(
            make_builder_row(
                index,
                labeled("anger"),
                labeled("anger"),
                labeled("anger"),
                labeled("frustration"),
            )
        )
        index += 1
    for _ in range(5):
        rows.append(
            make_builder_row(
                index,
                labeled("neutral"),
                labeled("joy"),
                labeled("joy"),
                labeled("joy"),
            )
        )
        index += 1
    for _ in range(2):
        rows.append(
            make_builder_row(
                index,
                labeled("sadness"),
                labeled("sadness"),
                labeled("sadness"),
                labeled("sadness"),
            )
        )
        index += 1
    while index <= 120:
        rows.append(
            make_builder_row(
                index,
                labeled("neutral"),
                labeled("neutral"),
                labeled("neutral"),
                labeled("neutral"),
            )
        )
        index += 1
    return rows


class BlindBundleBuilderTests(unittest.TestCase):
    def test_selection_fills_frozen_strata_without_duplicates(self) -> None:
        selected = builder.select_rows(synthetic_builder_rows(), "test-seed")
        counts = Counter(item["stratum"] for item in selected)

        self.assertEqual(len(selected), 40)
        self.assertEqual(
            counts,
            {
                "stance_candidate": 15,
                "all_three_different": 10,
                "model_boundary_conflict": 8,
                "human_context_shift": 5,
                "all_three_equal_control": 2,
            },
        )
        self.assertEqual(
            len({item["row"]["sample_uid"] for item in selected}),
            40,
        )
        self.assertEqual(
            [item["row"]["sample_uid"] for item in selected],
            [
                item["row"]["sample_uid"]
                for item in builder.select_rows(synthetic_builder_rows(), "test-seed")
            ],
        )

    def test_candidate_permutation_cycle_is_balanced(self) -> None:
        permutations = builder.balanced_source_permutations("test-seed")
        counts = {
            alias: Counter() for alias in ("candidate_a", "candidate_b", "candidate_c")
        }
        for position in range(40):
            source_order = permutations[position % 6]
            for alias, source in zip(counts, source_order, strict=True):
                counts[alias][source] += 1

        for source in ("human", "model_01", "model_02"):
            position_counts = [counts[alias][source] for alias in counts]
            self.assertLessEqual(max(position_counts) - min(position_counts), 1)

    def test_server_cli_defaults_parse(self) -> None:
        original_argv = sys.argv
        try:
            sys.argv = ["server.py"]
            args = parse_args()
        finally:
            sys.argv = original_argv
        self.assertEqual(args.port, 8766)
        self.assertEqual(args.adjudicator_uid, "ann_primary_human")


if __name__ == "__main__":
    unittest.main()
