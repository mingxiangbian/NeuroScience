from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ANNOTATION_DIR = Path(__file__).resolve().parents[1]
ANNOTATOR_DIR = ANNOTATION_DIR / "human_annotator"
sys.path.insert(0, str(ANNOTATOR_DIR))

from core import AnnotationConflict, AnnotationError, AnnotationStore  # noqa: E402
from server import (  # noqa: E402
    AnnotationRequestHandler,
    LocalAnnotationServer,
)


def make_view(index: int) -> dict:
    suffix = f"{index:064x}"
    return {
        "schema_version": "annotation-view-v1",
        "protocol_id": "DATA-FCTX-LABEL-V1",
        "dataset": {
            "name": "IAC 2.0",
            "subset": "4forums",
            "cleaning_pipeline_id": "DATA-FCTX-CLEAN-V2",
            "dedup_pipeline_id": "DATA-FCTX-DEDUP-V2",
        },
        "ids": {
            "sample_uid": f"smp_{suffix}",
            "thread_uid": f"thr_{suffix}",
            "parent_uid": f"pst_{suffix}",
            "target_uid": f"pst_{(index + 100):064x}",
        },
        "context": {
            "discussion_title": f"PRIVATE_TITLE_{index}",
            "direct_parent_body": f"PRIVATE_PARENT_{index}",
            "target_quotes": [
                {
                    "quote_index": 0,
                    "text": f"PRIVATE_QUOTE_{index}",
                    "source_relation": "direct_parent",
                    "truncated": False,
                    "altered": False,
                }
            ],
        },
        "target": {
            "body": f"PUBLIC_TARGET_{index}\n[[QUOTE]]\nReply body.",
            "full_with_quotes": (
                f"PUBLIC_TARGET_{index}\n[[QUOTE]]\nPRIVATE_QUOTE_{index}"
                "\n[[/QUOTE]]\nReply body."
            ),
        },
        "display_contract": {
            "stage_a": "target.body",
            "stage_b": "context+target",
            "stage_a_locked_before_stage_b": True,
            "future_replies_included": False,
            "ancestor_chain_included": False,
        },
    }


def stage_a_decision() -> dict:
    return {
        "status": "labeled",
        "primary_emotion": "frustration",
        "other_emotion_text": None,
        "confidence": "medium",
        "note": None,
    }


def stage_b_decision() -> dict:
    return {
        "status": "labeled",
        "primary_emotion": "anger",
        "other_emotion_text": None,
        "confidence": "high",
        "sarcasm": "absent",
        "mixed_emotion": False,
        "context_sufficiency": "sufficient",
        "note": "Context resolves the target stance.",
    }


class StoreFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.views = self.root / "views"
        self.records = self.root / "records"
        self.views.mkdir()
        for index in range(1, 3):
            (self.views / f"{index:04d}.json").write_text(
                json.dumps(make_view(index), ensure_ascii=False), encoding="utf-8"
            )
        self.store = AnnotationStore(
            self.views,
            self.records,
            expected_total=2,
            dataset_mode="synthetic",
        )

    def tearDown(self) -> None:
        self.store.close()
        self.temporary.cleanup()


class AnnotationStoreTests(StoreFixture):
    def test_stage_a_response_does_not_serialize_context(self) -> None:
        response = self.store.current()

        self.assertEqual(response["stage"], "A")
        self.assertNotIn("context", response)
        self.assertNotIn("target_full_with_quotes", response)
        serialized = json.dumps(response)
        self.assertNotIn("PRIVATE_TITLE_1", serialized)
        self.assertNotIn("PRIVATE_PARENT_1", serialized)
        self.assertNotIn("PRIVATE_QUOTE_1", serialized)
        self.assertIn("[quoted text omitted]", response["target_body"])
        self.assertNotIn("[[QUOTE]]", response["target_body"])

    def test_stage_a_is_locked_before_context_is_returned(self) -> None:
        stage_a = self.store.current()
        stage_b = self.store.submit_stage_a(stage_a["case_id"], stage_a_decision())

        self.assertEqual(stage_b["stage"], "B")
        self.assertTrue(stage_b["stage_a_locked"])
        self.assertEqual(stage_b["context"]["discussion_title"], "PRIVATE_TITLE_1")
        self.assertNotIn("target_only", stage_b)
        self.assertNotIn("frustration", json.dumps(stage_b))

        with self.assertRaisesRegex(AnnotationConflict, "already locked"):
            self.store.submit_stage_a(stage_a["case_id"], stage_a_decision())

    def test_stage_b_completion_is_atomic_and_advances(self) -> None:
        first = self.store.current()
        self.store.submit_stage_a(first["case_id"], stage_a_decision())
        next_state = self.store.submit_stage_b(first["case_id"], stage_b_decision())

        self.assertEqual(next_state["stage"], "A")
        self.assertEqual(next_state["case_id"], "0002")
        record_path = self.records / "0001.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual(record["target_only"]["primary_emotion"], "frustration")
        self.assertEqual(record["contextual"]["primary_emotion"], "anger")
        self.assertIsNotNone(record["completed_at"])
        self.assertEqual(os.stat(record_path).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(self.records).st_mode & 0o777, 0o700)

        session_log = (self.records / "session-log.jsonl").read_text(encoding="utf-8")
        self.assertIn("stage_a_locked", session_log)
        self.assertIn("case_completed", session_log)
        self.assertNotIn("frustration", session_log)
        self.assertNotIn("PRIVATE_", session_log)

    def test_unusable_requires_note_and_clears_context_diagnostics(self) -> None:
        first = self.store.current()
        self.store.submit_stage_a(first["case_id"], stage_a_decision())
        invalid = {
            "status": "unusable",
            "primary_emotion": None,
            "other_emotion_text": None,
            "confidence": "low",
            "sarcasm": None,
            "mixed_emotion": None,
            "context_sufficiency": None,
            "note": None,
        }
        with self.assertRaisesRegex(AnnotationError, "require a note"):
            self.store.submit_stage_b(first["case_id"], invalid)

        valid = {**invalid, "note": "The target text is corrupted."}
        state = self.store.submit_stage_b(first["case_id"], valid)
        self.assertEqual(state["case_id"], "0002")

    def test_session_limit_stops_before_serving_another_case(self) -> None:
        self.store.session_limit = 1
        first = self.store.current()
        self.store.submit_stage_a(first["case_id"], stage_a_decision())
        state = self.store.submit_stage_b(first["case_id"], stage_b_decision())

        self.assertEqual(state["state"], "session_break")
        resumed = self.store.start_session()
        self.assertEqual(resumed["case_id"], "0002")


class AnnotationHTTPTests(StoreFixture):
    def setUp(self) -> None:
        super().setUp()
        self.static_dir = ANNOTATOR_DIR / "static"
        self.server = LocalAnnotationServer(
            ("127.0.0.1", 0),
            AnnotationRequestHandler,
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
                headers["X-Annotation-Token"] = "test-token"
        request = Request(self.base_url + path, data=data, headers=headers)
        return urlopen(request, timeout=2)

    def test_http_stage_gate_and_security_headers(self) -> None:
        with self.request("/api/current") as response:
            raw = response.read().decode("utf-8")
            stage_a = json.loads(raw)
            self.assertEqual(stage_a["stage"], "A")
            self.assertNotIn("PRIVATE_PARENT_1", raw)
            self.assertEqual(response.headers["Cache-Control"], "no-store, max-age=0")
            self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])

        with self.request(
            "/api/stage-a",
            body={"case_id": stage_a["case_id"], "decision": stage_a_decision()},
        ) as response:
            stage_b = json.loads(response.read().decode("utf-8"))
            self.assertEqual(stage_b["stage"], "B")
            self.assertEqual(stage_b["context"]["direct_parent_body"], "PRIVATE_PARENT_1")

    def test_http_rejects_missing_token_and_unknown_static_paths(self) -> None:
        stage_a = json.loads(self.request("/api/current").read().decode("utf-8"))
        with self.assertRaises(HTTPError) as missing_token:
            self.request(
                "/api/stage-a",
                body={"case_id": stage_a["case_id"], "decision": stage_a_decision()},
                token=False,
            )
        try:
            self.assertEqual(missing_token.exception.code, 403)
        finally:
            missing_token.exception.close()

        with self.assertRaises(HTTPError) as traversal:
            self.request("/%2e%2e/%2e%2e/etc/passwd")
        try:
            self.assertEqual(traversal.exception.code, 404)
        finally:
            traversal.exception.close()

    def test_static_bundle_has_no_external_assets_or_model_data_route(self) -> None:
        for filename in ("index.html", "styles.css", "app.js"):
            content = (self.static_dir / filename).read_text(encoding="utf-8")
            self.assertNotIn("https://", content)
            self.assertNotIn("http://", content)
        server_source = (ANNOTATOR_DIR / "server.py").read_text(encoding="utf-8")
        self.assertNotIn("model-outputs", server_source)
        self.assertNotIn("model_outputs", server_source)


if __name__ == "__main__":
    unittest.main()
