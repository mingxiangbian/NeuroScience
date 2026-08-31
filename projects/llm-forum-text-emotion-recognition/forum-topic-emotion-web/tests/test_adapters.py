"""Source contract tests use synthetic fixtures only; they never access a forum."""

import hashlib
import gzip
import io
import json
import unittest
import zlib
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from topicweb import adapters


START = 1735689600
QUERY = {
    "site": "stackoverflow", "query": "", "tags": "python",
    "from_utc": "2025-01-01T00:00:00Z", "to_utc": "2025-01-02T00:00:00Z",
    "max_questions": 100, "max_items": 500,
    "include_questions": True, "include_answers": True, "include_comments": True,
}


def item(kind, identifier, text="`x` <b>GOOD</b>\n  ", **kwargs):
    return {f"{kind}_id": identifier, "creation_date": START + 10,
            "body_markdown": text, **kwargs}


def wrapper(items, has_more=False, quota=100, **kwargs):
    return {"items": items, "has_more": has_more, "quota_remaining": quota, **kwargs}


class UploadTests(unittest.TestCase):
    def test_original_input_and_upload_traceability(self):
        value = 'GOOD\n  Code `x` <b>literal</b> '
        raw = json.dumps([{"text": value, "id": "a", "labels": [1, 0], "context": "not input"}])
        records, manifest = adapters.parse_upload(raw, "json", filename="folder/source.json")
        self.assertEqual(records[0]["model_input_text"], value)
        self.assertEqual(records[0]["model_input_hash"], hashlib.sha256(value.encode()).hexdigest())
        self.assertEqual(records[0]["provenance"]["file_sha256"], hashlib.sha256(raw.encode()).hexdigest())
        self.assertEqual(records[0]["provenance"]["row_number"], 1)
        self.assertEqual(records[0]["provenance"]["filename"], "source.json")
        self.assertIsNone(records[0]["source_url"])
        self.assertNotIn("labels", records[0]["source_payload_raw"])
        self.assertNotIn("context", records[0]["source_payload_raw"])
        self.assertEqual(manifest["source_link_count"], 0)
        self.assertFalse(manifest["labels_used"])

    def test_normalized_groups_do_not_alias_exact_input(self):
        records, _ = adapters.parse_upload('[{"text":"GOOD"},{"text":"good"},{"text":"GOOD"}]', "json")
        self.assertEqual(records[0]["dedup_hash"], records[1]["dedup_hash"])
        self.assertNotEqual(records[0]["model_input_hash"], records[1]["model_input_hash"])
        self.assertEqual(records[0]["model_input_hash"], records[2]["model_input_hash"])
        self.assertEqual(len({row["record_id"] for row in records}), 3)

    def test_multiline_csv_and_jsonl_keep_row_provenance(self):
        rows, _ = adapters.parse_upload('text,id\n"first\nsecond",1\nthird,2\n', "csv")
        self.assertEqual(rows[0]["model_input_text"], "first\nsecond")
        self.assertEqual([row["provenance"]["line_number"] for row in rows], [2, 4])
        rows, _ = adapters.parse_upload('\n{"message":" a "}\n\n{"message":"b"}', "jsonl", "message")
        self.assertEqual([row["provenance"]["line_number"] for row in rows], [2, 4])
        self.assertEqual(rows[0]["model_input_text"], " a ")

    def test_upload_limits_and_malformed_inputs(self):
        bad = [("x" * (adapters.MAX_UPLOAD_BYTES + 1), "json"),
               (json.dumps([{"text": "x"}] * 501), "json"),
               (json.dumps([{"text": "x" * (adapters.MAX_TEXT_BYTES + 1)}]), "json"),
               ('[{"text":" "}]', "json"), ('{"text":"x"}', "json"),
               ('[{"text":1}]', "json"), ('text,text\nx,x', "csv"),
               ('[{"text":"first","text":"second"}]', "json"),
               ('[{"text":"x","labels":NaN}]', "json"),
               ('text\nx,extra', "csv"), ('not json', "jsonl"), ("", "jsonl")]
        for content, format in bad:
            with self.subTest(format=format, length=len(content)):
                with self.assertRaises(adapters.SourceError):
                    adapters.parse_upload(content, format)

    def test_optional_dates_urls_are_validated(self):
        rows, _ = adapters.parse_upload('[{"text":"x","created_at":"2025-01-01T08:00:00+08:00"}]', "json")
        self.assertEqual(rows[0]["created_at"], "2025-01-01T00:00:00Z")
        for fields in [{"created_at": "2025-01-01"}, {"url": "javascript:alert(1)"},
                       {"url": "https://user:pass@example.org"}, {"id": {"nested": "x"}}]:
            with self.subTest(fields=fields), self.assertRaises(adapters.SourceError):
                adapters.parse_upload(json.dumps([{"text": "x", **fields}]), "json")


class StackExchangeTests(unittest.TestCase):
    def setUp(self):
        self.filter_patch = patch.object(adapters, "STACKEXCHANGE_FILTER_ID", "fixture-filter")
        self.filter_patch.start()
        self.addCleanup(self.filter_patch.stop)

    def test_question_cohort_raw_input_and_all_object_types(self):
        q = item("question", 10)
        a = item("answer", 20, question_id=10)
        c = item("comment", 30, post_id=20)
        callbacks = []
        with patch.object(adapters, "_get_json", side_effect=[wrapper([q]), wrapper([a]), wrapper([c])]) as getter:
            records, manifest = adapters.fetch_stackexchange(dict(QUERY), progress=callbacks.append)
        self.assertEqual([row["object_type"] for row in records], ["question", "answer", "comment"])
        self.assertEqual(records[0]["model_input_text"], q["body_markdown"])
        self.assertEqual(len({row["record_id"] for row in records}), 3)
        self.assertEqual(len({row["model_input_hash"] for row in records}), 1)
        self.assertEqual([row["thread_id"] for row in records], ["10", "10", "10"])
        self.assertEqual(records[1]["parent_object_id"], "10")
        self.assertEqual(records[2]["parent_object_id"], "20")
        self.assertEqual(manifest["counts_by_type"], {"question": 1, "answer": 1, "comment": 1})
        self.assertEqual(manifest["stop_reason"], "complete")
        self.assertEqual(manifest["filter_id"], "fixture-filter")
        for call in getter.call_args_list:
            parsed = urlparse(call.args[0])
            query = parse_qs(parsed.query)
            self.assertEqual(parsed.hostname, "api.stackexchange.com")
            self.assertEqual(query["sort"], ["creation"])
            self.assertEqual(query["order"], ["asc"])
            self.assertEqual(query["fromdate"], [str(START)])
            self.assertEqual(query["todate"], [str(START + 86400 - 1)])
        self.assertEqual(manifest["window_bounds"], "start_inclusive_end_exclusive")
        self.assertEqual(len(callbacks), 6)
        self.assertEqual([value["source_stage"] for value in callbacks],
                         ["request_started", "response_received"] * 3)
        self.assertEqual([value["request_count"] for value in callbacks], [1, 1, 2, 2, 3, 3])

    def test_question_pagination_deduplicates_source_identity_not_text(self):
        responses = [wrapper([item("question", 10)], True),
                     wrapper([item("question", 10), item("question", 11)])]
        with patch.object(adapters, "_get_json", side_effect=responses):
            records, manifest = adapters.fetch_stackexchange({**QUERY, "include_answers": False, "include_comments": False})
        self.assertEqual(len(records), 2)
        self.assertEqual(manifest["duplicate_source_ids"], 1)
        self.assertEqual(manifest["selected_question_count"], 2)
        self.assertEqual(manifest["record_count"], 2)

    def test_question_limit_is_explicit_and_selected_cohort_still_gets_children(self):
        with patch.object(adapters, "_get_json", side_effect=[
            wrapper([item("question", 10), item("question", 11)], True),
            wrapper([item("answer", 20, question_id=10)]), wrapper([]),
        ]) as getter:
            records, manifest = adapters.fetch_stackexchange({**QUERY, "max_questions": 1})
        self.assertEqual(len(records), 2)
        self.assertEqual(manifest["stop_reason"], "question_limit")
        self.assertFalse(manifest["sampling_complete"])
        self.assertIn("questions/10/answers", getter.call_args_list[1].args[0])

    def test_item_limit_and_quota_limit_never_start_extra_requests(self):
        with patch.object(adapters, "_get_json", return_value=wrapper([item("question", 10), item("question", 11)])) as getter:
            records, manifest = adapters.fetch_stackexchange({**QUERY, "max_items": 1})
        self.assertEqual(len(records), 1)
        self.assertEqual(manifest["stop_reason"], "item_limit")
        self.assertEqual(getter.call_count, 1)
        with patch.object(adapters, "_get_json", return_value=wrapper([item("question", 10)], quota=0)) as getter:
            records, manifest = adapters.fetch_stackexchange(QUERY)
        self.assertEqual(len(records), 1)
        self.assertEqual(manifest["stop_reason"], "quota_exhausted")
        self.assertEqual(getter.call_count, 1)

    def test_comments_include_answer_parents_when_answer_output_disabled(self):
        with patch.object(adapters, "_get_json", side_effect=[wrapper([item("question", 10)]),
            wrapper([item("answer", 20, question_id=10)]), wrapper([item("comment", 30, post_id=20)])]) as getter:
            records, _ = adapters.fetch_stackexchange({**QUERY, "include_answers": False})
        self.assertEqual([row["object_type"] for row in records], ["question", "comment"])
        self.assertIn("posts/10;20/comments", getter.call_args_list[-1].args[0])

    def test_cancellation_request_budget_and_time_budget(self):
        with patch.object(adapters, "_get_json") as getter:
            records, manifest = adapters.fetch_stackexchange(QUERY, cancelled=lambda: True)
        self.assertEqual(records, [])
        self.assertEqual(manifest["stop_reason"], "cancelled")
        getter.assert_not_called()
        with patch.object(adapters, "MAX_REQUESTS", 1), patch.object(adapters, "_get_json", return_value=wrapper([item("question", 10)], True)) as getter:
            _, manifest = adapters.fetch_stackexchange(QUERY)
        self.assertEqual(manifest["stop_reason"], "max_requests")
        self.assertEqual(getter.call_count, 1)
        with patch.object(adapters, "MAX_FETCH_SECONDS", 0), patch.object(adapters, "_get_json") as getter:
            _, manifest = adapters.fetch_stackexchange(QUERY)
        self.assertEqual(manifest["stop_reason"], "time_limit")
        getter.assert_not_called()

    def test_backoff_wait_is_cancellable(self):
        with patch.object(adapters, "_get_json", return_value=wrapper([item("question", 10)], True, backoff=30)) as getter:
            cancelled = lambda: getter.call_count > 0
            records, manifest = adapters.fetch_stackexchange(QUERY, cancelled=cancelled)
        self.assertEqual(len(records), 1)
        self.assertEqual(manifest["stop_reason"], "cancelled")
        self.assertEqual(getter.call_count, 1)

    def test_missing_raw_or_wrong_parent_is_failure(self):
        missing = item("question", 10)
        del missing["body_markdown"]
        progress = []
        with patch.object(adapters, "_get_json", return_value=wrapper([missing])), self.assertRaises(adapters.SourceError) as caught:
            adapters.fetch_stackexchange(QUERY, progress=progress.append)
        self.assertEqual(caught.exception.code, "source_body_markdown_missing")
        self.assertEqual(caught.exception.metadata, {"stage": "record", "request_count": 1,
                                                   "page": 1, "record_count": 0, "endpoint_kind": "search"})
        self.assertEqual([value["source_stage"] for value in progress], ["request_started", "response_received"])
        self.assertEqual(progress[-1]["returned_count"], 1)
        self.assertEqual(progress[-1]["record_count"], 0)
        with patch.object(adapters, "_get_json", side_effect=[wrapper([item("question", 10)]), wrapper([item("answer", 20, question_id=99)])]), self.assertRaises(adapters.SourceError):
            adapters.fetch_stackexchange(QUERY)

    def test_comment_html_cannot_replace_or_modify_native_markdown(self):
        markdown = "Keep `x < y` & original spacing.  \n"
        html = "<script>do-not-use-as-input</script> unrelated HTML-only content"
        comment = item("comment", 30, text=markdown, post_id=10, body=html)
        query = {**QUERY, "include_questions": False, "include_answers": False}
        responses = [wrapper([item("question", 10)]), wrapper([]), wrapper([comment])]
        with patch.object(adapters, "_get_json", side_effect=responses):
            records, _ = adapters.fetch_stackexchange(query)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["model_input_text"], markdown)
        self.assertEqual(records[0]["model_input_hash"], hashlib.sha256(markdown.encode("utf-8")).hexdigest())
        self.assertNotIn("body", records[0]["source_payload_raw"])
        self.assertNotIn(html, json.dumps(records, ensure_ascii=False))
        comment.pop("body_markdown")
        responses = [wrapper([item("question", 10)]), wrapper([]), wrapper([comment])]
        with patch.object(adapters, "_get_json", side_effect=responses), self.assertRaises(adapters.SourceError) as caught:
            adapters.fetch_stackexchange(query)
        self.assertEqual(caught.exception.code, "source_body_markdown_missing")
        self.assertEqual(caught.exception.metadata["endpoint_kind"], "comments")
        self.assertEqual(caught.exception.metadata["request_count"], 3)
        self.assertEqual(caught.exception.metadata["record_count"], 0)

    def test_request_errors_retain_safe_request_location(self):
        marker = "secret query/token/original text"
        failure = adapters.SourceError(marker, code="source_network_error",
                                       metadata={"stage": "request", "exception_type": "URLError", "query": marker})
        progress = []
        with patch.object(adapters, "_get_json", side_effect=failure), self.assertRaises(adapters.SourceError) as caught:
            adapters.fetch_stackexchange(QUERY, progress=progress.append)
        self.assertEqual(caught.exception.code, "source_network_error")
        self.assertEqual(caught.exception.metadata["request_count"], 1)
        self.assertEqual(caught.exception.metadata["page"], 1)
        self.assertEqual(caught.exception.metadata["endpoint_kind"], "search")
        self.assertEqual(progress[0]["source_stage"], "request_started")
        self.assertNotIn(marker, json.dumps({"progress": progress, "error": caught.exception.metadata}))

    def test_api_error_and_wrapper_error_are_distinct_and_do_not_echo_values(self):
        marker = "do not publish this API message"
        for data, code in [({"error_id": 400, "error_message": marker}, "source_api_error"),
                           ({"items": [], "has_more": False, "quota_remaining": marker}, "source_wrapper_error")]:
            progress = []
            with self.subTest(code=code), patch.object(adapters, "_get_json", return_value=data), self.assertRaises(adapters.SourceError) as caught:
                adapters.fetch_stackexchange(QUERY, progress=progress.append)
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(caught.exception.metadata["stage"], "wrapper")
            self.assertEqual(progress[-1]["source_stage"], "response_received")
            self.assertNotIn(marker, json.dumps({"progress": progress, "error": caught.exception.metadata}))

    def test_outside_window_is_not_silently_included(self):
        q = item("question", 10, creation_date=START - 1)
        with patch.object(adapters, "_get_json", return_value=wrapper([q])):
            records, manifest = adapters.fetch_stackexchange(QUERY)
        self.assertEqual(records, [])
        self.assertEqual(manifest["outside_window_count"], 1)

    def test_exact_window_start_is_included_and_end_is_excluded(self):
        questions = [item("question", 10, creation_date=START),
                     item("question", 11, creation_date=START + 86400 - 1),
                     item("question", 12, creation_date=START + 86400)]
        with patch.object(adapters, "_get_json", return_value=wrapper(questions)) as getter:
            records, manifest = adapters.fetch_stackexchange({**QUERY, "include_answers": False, "include_comments": False})
        self.assertEqual([record["source_object_id"] for record in records], ["10", "11"])
        self.assertEqual(manifest["outside_window_count"], 1)
        self.assertEqual(manifest["window_bounds"], "start_inclusive_end_exclusive")
        sent = parse_qs(urlparse(getter.call_args.args[0]).query)
        self.assertEqual(sent["fromdate"], [str(START)])
        self.assertEqual(sent["todate"], [str(START + 86400 - 1)])

    def test_unreviewed_filter_and_invalid_requests_do_not_use_network(self):
        with patch.object(adapters, "STACKEXCHANGE_FILTER_ID", None), patch.object(adapters, "_get_json") as getter:
            with self.assertRaises(adapters.SourceError):
                adapters.fetch_stackexchange(QUERY)
            getter.assert_not_called()
        for fields in [{"site": "math"}, {"max_items": 501}, {"max_questions": True},
                       {"from_utc": "2025-01-01"}, {"include_answers": "false"},
                       {"tags": "", "query": ""}]:
            with self.subTest(fields=fields), patch.object(adapters, "_get_json") as getter:
                with self.assertRaises(adapters.SourceError):
                    adapters.fetch_stackexchange({**QUERY, **fields})
                getter.assert_not_called()


class DiscourseTests(unittest.TestCase):
    query = {"site": "discuss.python.org", "category_id": 7, "max_topics": 100, "max_items": 400}

    def setUp(self):
        interval = patch.object(adapters, "DISCOURSE_MIN_INTERVAL", 0)
        interval.start()
        self.addCleanup(interval.stop)

    @staticmethod
    def topic(identifier=10, **kwargs):
        return {"id": identifier, "category_id": 7, "archetype": "regular", "visible": True,
                "pinned": False, "created_at": f"2026-08-{identifier:02d}T00:00:00Z", **kwargs}

    @staticmethod
    def post(identifier, number, topic_id=10, **kwargs):
        return {"id": identifier, "topic_id": topic_id, "post_number": number, "post_type": 1,
                "raw": "`x < y`  exact raw\n", "cooked": "<p>different HTML</p>",
                "created_at": "2026-08-10T00:00:00Z", "updated_at": "2026-08-10T00:01:00Z",
                "username": "fixture_author", "user_id": 88, "hidden": False, **kwargs}

    @staticmethod
    def listing(topics, more=None):
        return {"topic_list": {"topics": topics, "more_topics_url": more}}

    def view(self, posts, stream=None, topic_id=10):
        return {**self.topic(topic_id), "post_stream": {"posts": posts,
                                                       "stream": stream if stream is not None else [row["id"] for row in posts]}}

    def test_reviewed_category_native_raw_identity_and_attribution(self):
        first = self.post(1001, 1)
        second = self.post(1002, 2, reply_to_post_number=1)
        with patch.object(adapters, "_get_json", side_effect=[self.listing([self.topic()]), self.view([first, second])]) as getter:
            rows, manifest = adapters.fetch_discourse(self.query)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["model_input_text"], first["raw"])
        self.assertEqual(rows[0]["model_input_hash"], hashlib.sha256(first["raw"].encode()).hexdigest())
        self.assertEqual(rows[0]["model_input_hash"], rows[1]["model_input_hash"])
        self.assertNotEqual(rows[0]["record_id"], rows[1]["record_id"])
        self.assertEqual(rows[1]["parent_object_id"], "1001")
        self.assertEqual(rows[1]["thread_id"], "10")
        self.assertEqual(rows[0]["content_license"], "CC BY-NC-SA 3.0")
        self.assertEqual(rows[0]["author_display_name"], "fixture_author")
        self.assertEqual(rows[0]["source_url"], "https://discuss.python.org/t/10/1")
        self.assertNotIn("cooked", rows[0]["source_payload_raw"])
        self.assertEqual(manifest["window_bounds"], "not_a_time_window")
        self.assertEqual(manifest["topic_ids"], [10])
        self.assertEqual(manifest["record_count"], 2)
        self.assertTrue(manifest["collection_complete"])
        self.assertFalse(manifest["sampling_complete"])
        for call in getter.call_args_list:
            self.assertEqual(urlparse(call.args[0]).hostname, "discuss.python.org")
        query = parse_qs(urlparse(getter.call_args_list[0].args[0]).query)
        self.assertEqual(query, {"order": ["created"], "ascending": ["false"], "page": ["0"]})

    def test_batches_follow_stream_order_and_missing_ids_are_explicit(self):
        posts = [self.post(1001, 1), self.post(1003, 3)]
        responses = [self.listing([self.topic()]), self.view(posts[:1], [1001, 1002, 1003]),
                     {"id": 10, "post_stream": {"posts": posts[1:]}}]
        with patch.object(adapters, "_get_json", side_effect=responses) as getter:
            rows, manifest = adapters.fetch_discourse(self.query)
        self.assertEqual([row["source_object_id"] for row in rows], ["1001", "1003"])
        self.assertEqual(manifest["unavailable_post_ids"], [1002])
        self.assertEqual(manifest["exclusions"]["unavailable_stream_ids"], 1)
        self.assertFalse(manifest["collection_complete"])
        query = parse_qs(urlparse(getter.call_args_list[-1].args[0]).query)
        self.assertEqual(query["post_ids[]"], ["1002", "1003"])
        self.assertEqual(query["include_raw"], ["true"])
        self.assertEqual(query["asc"], ["true"])

    def test_pinned_system_deleted_and_nonregular_are_counted(self):
        posts = [self.post(1001, 1, username="system", user_id=-1, raw=None),
                 self.post(1002, 2, deleted_at="2026-08-11T00:00:00Z", raw=None),
                 self.post(1003, 3, post_type=3, raw=None), self.post(1004, 4)]
        responses = [self.listing([self.topic(20, pinned=True), self.topic()]), self.view(posts)]
        with patch.object(adapters, "_get_json", side_effect=responses) as getter:
            rows, manifest = adapters.fetch_discourse(self.query)
        self.assertEqual(len(rows), 1)
        self.assertEqual(getter.call_count, 2)
        self.assertEqual(manifest["exclusions"]["pinned_topics"], 1)
        self.assertEqual(manifest["exclusions"]["system_posts"], 1)
        self.assertEqual(manifest["exclusions"]["deleted_or_hidden_posts"], 1)
        self.assertEqual(manifest["exclusions"]["nonregular_posts"], 1)

    def test_missing_raw_never_falls_back_to_cooked(self):
        posts = [self.post(1001, 1, raw=None, cooked="<p>must never be an input fallback</p>")]
        with patch.object(adapters, "_get_json", side_effect=[self.listing([self.topic()]), self.view(posts)]), self.assertRaises(adapters.SourceError) as caught:
            adapters.fetch_discourse(self.query)
        self.assertEqual(caught.exception.code, "source_raw_missing")
        self.assertEqual(caught.exception.metadata["record_count"], 0)

    def test_item_cap_marks_clipped_topic_not_complete(self):
        posts = [self.post(1001, 1), self.post(1002, 2)]
        with patch.object(adapters, "_get_json", side_effect=[self.listing([self.topic()]), self.view(posts)]) as getter:
            rows, manifest = adapters.fetch_discourse({**self.query, "max_items": 1})
        self.assertEqual(len(rows), 1)
        self.assertEqual(manifest["stop_reason"], "item_limit")
        self.assertEqual(manifest["truncated_topic_ids"], [10])
        self.assertFalse(manifest["collection_complete"])
        self.assertEqual(getter.call_count, 2)

    def test_pagination_and_topic_limit_have_no_search_or_arbitrary_urls(self):
        first, second = self.topic(10), self.topic(9)
        responses = [self.listing([first], "https://untrusted.invalid/not-followed"), self.view([self.post(1001, 1)]),
                     self.listing([first, second]), self.view([self.post(2001, 1, topic_id=9)], topic_id=9)]
        with patch.object(adapters, "_get_json", side_effect=responses) as getter:
            rows, manifest = adapters.fetch_discourse(self.query)
        self.assertEqual(len(rows), 2)
        self.assertEqual(manifest["exclusions"]["duplicate_topics"], 1)
        self.assertEqual(parse_qs(urlparse(getter.call_args_list[2].args[0]).query)["page"], ["1"])
        for call in getter.call_args_list:
            self.assertEqual(urlparse(call.args[0]).hostname, "discuss.python.org")
            self.assertNotIn("/search", call.args[0])
        with patch.object(adapters, "_get_json", side_effect=responses[:2]):
            _, manifest = adapters.fetch_discourse({**self.query, "max_topics": 1})
        self.assertEqual(manifest["stop_reason"], "topic_limit")

    def test_unreviewed_queries_and_changed_public_identity_fail(self):
        for change in ({"site": "discourse.julialang.org"}, {"category_id": 9}, {"topic_url": "https://evil.invalid/t/1"},
                       {"query": "search"}, {"max_items": 501}, {"max_topics": 101}):
            with self.subTest(change=change), patch.object(adapters, "_get_json") as getter, self.assertRaises(adapters.SourceError):
                adapters.fetch_discourse({**self.query, **change})
            getter.assert_not_called()
        changed = self.view([self.post(1001, 1)])
        changed["archetype"] = "private_message"
        with patch.object(adapters, "_get_json", side_effect=[self.listing([self.topic()]), changed]), self.assertRaises(adapters.SourceError):
            adapters.fetch_discourse(self.query)

    def test_http_denial_limits_and_cancellation_do_not_retry(self):
        for status in (403, 429):
            error = adapters.SourceError("denied", code="source_http_error", metadata={"stage": "http", "http_status": status})
            with patch.object(adapters, "_get_json", side_effect=error) as getter, self.assertRaises(adapters.SourceError) as caught:
                adapters.fetch_discourse(self.query)
            self.assertEqual(caught.exception.metadata["http_status"], status)
            self.assertEqual(getter.call_count, 1)
        with patch.object(adapters, "DISCOURSE_MAX_REQUESTS", 1), patch.object(adapters, "_get_json", return_value=self.listing([self.topic()])) as getter, self.assertRaises(adapters.SourceError) as caught:
            adapters.fetch_discourse(self.query)
        self.assertEqual(caught.exception.code, "source_resource_limit")
        self.assertEqual(getter.call_count, 1)
        with patch.object(adapters, "_get_json") as getter, self.assertRaises(adapters.SourceError):
            adapters.fetch_discourse(self.query, cancelled=lambda: True)
        getter.assert_not_called()

    def test_minimum_interval_and_backoff_are_enforced(self):
        clock = [0.0]
        request_times = []
        responses = [self.listing([self.topic()]), self.view([self.post(1001, 1)])]
        responses[0]["backoff"] = 2
        def get(*args, **kwargs):
            request_times.append(clock[0])
            return responses[len(request_times) - 1]
        def sleep(seconds):
            clock[0] += seconds
        with patch.object(adapters, "DISCOURSE_MIN_INTERVAL", 1), patch.object(adapters.time, "monotonic", side_effect=lambda: clock[0]), patch.object(adapters.time, "sleep", side_effect=sleep), patch.object(adapters, "_get_json", side_effect=get):
            adapters.fetch_discourse(self.query)
        self.assertGreaterEqual(request_times[1] - request_times[0], 2)


class NetworkAndDiscourseTests(unittest.TestCase):
    def test_frozen_filter_is_the_reviewed_comment_field_extension(self):
        self.assertEqual(adapters.STACKEXCHANGE_FILTER_ID, "nFzTOPGAOEckIq4PwsL9Jd")
        self.assertEqual(adapters.STACKEXCHANGE_FILTER_SPEC,
                         {"base": "nFzTOPGAOEckIq4Pwr_RZ8", "include": "comment.body", "unsafe": "true"})

    @staticmethod
    def response(data, headers=None):
        class Response(io.BytesIO):
            status = 200
            def geturl(self):
                return "https://api.stackexchange.com/2.3/search/advanced"
        response = Response(data)
        response.headers = headers or {}
        return response

    def decode(self, data, headers=None):
        metadata = {}
        with patch.object(adapters, "build_opener") as opener:
            opener.return_value.open.return_value = self.response(data, headers)
            decoded = adapters._get_json("https://api.stackexchange.com/2.3/search/advanced", "api.stackexchange.com",
                                         response_metadata=metadata)
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header("Accept-encoding"), "gzip, deflate")
            self.assertEqual(opener.return_value.open.call_args.kwargs["timeout"], 15)
        self.assertEqual(metadata["response_bytes"], len(data))
        self.assertEqual(metadata["response_sha256"], hashlib.sha256(data).hexdigest())
        return decoded

    def test_compression_and_plaintext_proxy_contract(self):
        payload = {"items": [{"body_markdown": "`a` <b>literal</b>\n  ä 原文"}], "has_more": False, "quota_remaining": 99}
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        raw_stream = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        raw_deflate = raw_stream.compress(raw) + raw_stream.flush()
        cases = [
            ("gzip", gzip.compress(raw), {"Content-Encoding": "gzip"}),
            ("gzip_no_header", gzip.compress(raw), {}),
            ("gzip_identity", gzip.compress(raw), {"Content-Encoding": "identity"}),
            ("gzip_members", gzip.compress(raw[:10]) + gzip.compress(raw[10:]), {"Content-Encoding": "gzip"}),
            ("zlib_deflate", zlib.compress(raw), {"Content-Encoding": "deflate"}),
            ("raw_deflate", raw_deflate, {"Content-Encoding": "deflate"}),
            ("plain_no_header", raw, {}),
            ("plain_identity", raw, {"Content-Encoding": "identity"}),
            ("proxy_kept_gzip_header", raw, {"Content-Encoding": "gzip"}),
            ("proxy_kept_deflate_header", raw, {"Content-Encoding": "deflate"}),
        ]
        for name, data, headers in cases:
            with self.subTest(name=name):
                self.assertEqual(self.decode(data, headers), payload)

    def test_corrupt_and_unsupported_compression_hard_stops(self):
        raw = b'{"items":[],"has_more":false,"quota_remaining":99}'
        packed = gzip.compress(raw)
        zlib_packed = zlib.compress(raw)
        raw_stream = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        raw_deflate = raw_stream.compress(raw) + raw_stream.flush()
        cases = [(packed[:-1], "gzip"), (packed + b"unexpected trailing bytes", "gzip"),
                 (packed[:-8] + b"\0" * 8, "gzip"), (zlib_packed[:-1], "deflate"),
                 (raw_deflate[:-1], "deflate"), (b"not a gzip stream", "gzip")]
        for data, encoding in cases:
            with self.subTest(encoding=encoding, data_length=len(data)), self.assertRaises(adapters.SourceError) as caught:
                self.decode(data, {"Content-Encoding": encoding})
            self.assertEqual(caught.exception.code, "source_decompression_error")
            self.assertEqual(caught.exception.metadata["stage"], "decompression")
            self.assertEqual(caught.exception.metadata["exception_type"], "ZlibError")
        for encoding in ("br", "gzip, deflate", "secret-header-token"):
            with self.subTest(encoding=encoding), self.assertRaises(adapters.SourceError) as caught:
                self.decode(raw, {"Content-Encoding": encoding})
            self.assertEqual(caught.exception.code, "source_content_encoding_unsupported")
            self.assertEqual(caught.exception.metadata["content_encoding"], "unsupported")
            self.assertNotIn(encoding, json.dumps(caught.exception.metadata))

    def test_decompression_is_bounded_at_exact_2_mib(self):
        prefix, suffix = b'{"pad":"', b'"}'
        exact = prefix + b"x" * (adapters.MAX_RESPONSE_BYTES - len(prefix) - len(suffix)) + suffix
        self.assertEqual(len(exact), adapters.MAX_RESPONSE_BYTES)
        self.assertEqual(len(self.decode(gzip.compress(exact), {"Content-Encoding": "gzip"})["pad"]),
                         adapters.MAX_RESPONSE_BYTES - len(prefix) - len(suffix))
        oversized = prefix + b"x" * (adapters.MAX_RESPONSE_BYTES + 1) + suffix
        raw_stream = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        cases = [(gzip.compress(oversized), "gzip"), (zlib.compress(oversized), "deflate"),
                 (raw_stream.compress(oversized) + raw_stream.flush(), "deflate"),
                 (gzip.compress(exact) + gzip.compress(b"x"), "gzip")]
        for data, encoding in cases:
            with self.subTest(encoding=encoding), self.assertRaises(adapters.SourceError) as caught:
                self.decode(data, {"Content-Encoding": encoding})
            self.assertEqual(caught.exception.code, "source_response_limit")
            self.assertEqual(caught.exception.metadata["stage"], "decompression")

    def test_utf8_json_and_wrapper_failure_codes_are_distinct(self):
        cases = [(b'{"bad":"\xff"}', "source_utf8_error", "utf8"),
                 (b'{"unfinished":', "source_json_error", "json"),
                 (b'{"value":1,"value":2}', "source_json_error", "json"),
                 (b'{"value":NaN}', "source_json_error", "json"),
                 (b"[]", "source_wrapper_error", "wrapper")]
        for data, code, stage in cases:
            with self.subTest(code=code), self.assertRaises(adapters.SourceError) as caught:
                self.decode(data, {"Content-Encoding": "identity"})
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(caught.exception.metadata["stage"], stage)

    def test_http_network_errors_and_metadata_are_public_safe(self):
        marker = "secret-source-query-token-text"
        url = "https://api.stackexchange.com/2.3/search/advanced?q=" + marker
        http_error = HTTPError(url, 429, marker, {"Content-Encoding": "identity"}, io.BytesIO(marker.encode()))
        with patch.object(adapters, "build_opener") as opener, self.assertRaises(adapters.SourceError) as caught:
            opener.return_value.open.side_effect = http_error
            adapters._get_json(url, "api.stackexchange.com")
        self.assertEqual(caught.exception.code, "source_http_error")
        self.assertEqual(caught.exception.metadata["http_status"], 429)
        self.assertEqual(caught.exception.metadata["response_bytes"], len(marker))
        self.assertNotIn(marker, json.dumps(caught.exception.metadata))
        self.assertNotIn(marker, str(caught.exception))
        with patch.object(adapters, "build_opener") as opener, self.assertRaises(adapters.SourceError) as caught:
            opener.return_value.open.side_effect = URLError(marker)
            adapters._get_json(url, "api.stackexchange.com")
        self.assertEqual(caught.exception.code, "source_network_error")
        self.assertEqual(caught.exception.metadata, {"stage": "request", "exception_type": "URLError"})
        error = adapters.SourceError(marker, code=marker, metadata={
            "stage": "request", "exception_type": marker, "query": marker, "url": url,
            "token": marker, "response_body": marker, "http_status": "200", "response_bytes": -1,
            "response_sha256": marker, "content_encoding": marker, "endpoint_kind": marker,
        })
        self.assertEqual(error.code, "source_validation_error")
        self.assertEqual(error.metadata, {"stage": "request"})

    def test_network_allowlist_and_no_redirect(self):
        for url in ("http://api.stackexchange.com/2.3/", "https://evil.example/2.3/",
                    "https://user@api.stackexchange.com/2.3/", "https://api.stackexchange.com:8443/2.3/"):
            with self.subTest(url=url), self.assertRaises(adapters.SourceError):
                adapters._get_json(url, "api.stackexchange.com")
        with self.assertRaises(adapters.SourceError):
            adapters._NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example")

    def test_response_size_is_bounded(self):
        class Response(io.BytesIO):
            headers = {}
            def geturl(self):
                return "https://api.stackexchange.com/2.3/search/advanced"
        with patch.object(adapters, "build_opener") as opener:
            opener.return_value.open.return_value = Response(b"x" * (adapters.MAX_RESPONSE_BYTES + 1))
            with self.assertRaises(adapters.SourceError) as caught:
                adapters._get_json("https://api.stackexchange.com/2.3/search/advanced", "api.stackexchange.com")
        self.assertEqual(caught.exception.code, "source_response_limit")
        self.assertEqual(caught.exception.metadata["response_bytes"], adapters.MAX_RESPONSE_BYTES + 1)

    def test_discourse_rejects_arbitrary_urls_and_requires_reviewed_snapshot(self):
        with self.assertRaises(adapters.SourceError):
            adapters.fetch_discourse({"topic_url": "https://arbitrary.example/t/1"})
        fixture = {"id": 1, "post_stream": {"stream": [2], "posts": [
            {"id": 2, "topic_id": 1, "post_number": 1, "raw": "**raw**\n  text", "created_at": "2025-01-01T00:00:00Z"}]}}
        with self.assertRaises(adapters.SourceError):
            adapters.parse_discourse_snapshot(fixture, topic_url="https://fixture.invalid/t/1")
        with self.assertRaises(adapters.SourceError):
            adapters.parse_discourse_snapshot(fixture, topic_url="https://fixture.invalid/t/99", approved_hosts=("fixture.invalid",))
        records, manifest = adapters.parse_discourse_snapshot(fixture, topic_url="https://fixture.invalid/t/1", approved_hosts=("fixture.invalid",))
        self.assertEqual(records[0]["model_input_text"], "**raw**\n  text")
        self.assertTrue(manifest["sampling_complete"])
        fixture["post_stream"]["stream"].append(3)
        _, manifest = adapters.parse_discourse_snapshot(fixture, topic_url="https://fixture.invalid/t/1", approved_hosts=("fixture.invalid",))
        self.assertEqual(manifest["stop_reason"], "incomplete_snapshot")
        fixture["post_stream"]["posts"][0].pop("raw")
        fixture["post_stream"]["posts"][0]["cooked"] = "<p>cooked</p>"
        with self.assertRaises(adapters.SourceError):
            adapters.parse_discourse_snapshot(fixture, topic_url="https://fixture.invalid/t/1", approved_hosts=("fixture.invalid",))


if __name__ == "__main__":
    unittest.main()
