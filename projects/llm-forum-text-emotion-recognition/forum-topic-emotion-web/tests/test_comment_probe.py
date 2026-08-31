"""Offline field-probe fixtures; no real API request or model is executed."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("comment_field_probe", ROOT / "scripts/probe_comment_fields.py")
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)
FIELDS = {"question.body_markdown", "answer.body_markdown", "comment.body_markdown",
          "comment.comment_id", "comment.post_id", "comment.creation_date",
          ".items", ".has_more", ".quota_remaining", ".backoff"}
NEW_FILTER = "fixture_new_filter"


def wrapper(items, quota=100, backoff=0):
    return {"items": items, "quota_remaining": quota, "has_more": False, "backoff": backoff}


def fixtures(all_old_markdown=False):
    comments = [{"comment_id": 501 + index, "post_id": 1001 + index,
                 "creation_date": PROBE.FROM_SECONDS + index + 10,
                 "body_markdown": f"**field fixture {index}**  ä",
                 "body": f"<b>field fixture {index}</b>  ä", "owner": {"display_name": "do-not-save-author"}}
                for index in range(3)]
    old = copy.deepcopy(comments)
    for row in old:
        row.pop("body")
    if not all_old_markdown:
        old[0].pop("body_markdown")
        old[2].pop("body_markdown")
    return [
        wrapper([{"filter": PROBE.OLD_FILTER_ID, "filter_type": "unsafe", "included_fields": sorted(FIELDS)}]),
        wrapper([{"filter": NEW_FILTER, "filter_type": "unsafe", "included_fields": sorted(FIELDS | {"comment.body"})}]),
        wrapper(copy.deepcopy(old)), wrapper(old), wrapper(comments),
    ]


class Clock:
    def __init__(self):
        self.value = 0.0
        self.waits = []
    def __call__(self):
        return self.value
    def sleep(self, duration):
        self.waits.append(duration)
        self.value += duration


class FakeAPI:
    def __init__(self, payloads, clock=None, duration=0):
        self.payloads = copy.deepcopy(payloads)
        self.clock = clock
        self.duration = duration
        self.calls = []
    def __call__(self, url, host, *, response_metadata):
        self.calls.append((url, host, self.clock() if self.clock else 0))
        if self.clock:
            self.clock.value += self.duration
        value = self.payloads[len(self.calls) - 1]
        encoded = json.dumps(value, ensure_ascii=False).encode()
        response_metadata.update(stage="read", http_status=200, response_bytes=len(encoded),
                                 content_encoding="identity", response_sha256=hashlib.sha256(encoded).hexdigest())
        return value


class CommentProbeTests(unittest.TestCase):
    def run_fixture(self, payloads=None, clock=None, duration=0):
        clock = clock or Clock()
        api = FakeAPI(payloads or fixtures(), clock, duration)
        result = PROBE.run_probe("a" * 64, "b" * 64, get_json=api, clock=clock, sleeper=clock.sleep)
        return result, api, clock

    def test_exact_five_requests_and_metadata_only_three_id_comparison(self):
        result, api, _ = self.run_fixture()
        self.assertEqual(result["status"], "Passed")
        self.assertEqual(len(api.calls), 5)
        self.assertEqual(result["old_filter_id"], PROBE.OLD_FILTER_ID)
        self.assertEqual(result["new_filter_id"], NEW_FILTER)
        self.assertEqual(set(result["new_included_fields"]), set(result["old_included_fields"]) | {"comment.body"})
        self.assertEqual(result["old_comment_ids"], [501, 502, 503])
        self.assertEqual(result["new_comment_ids"], result["discovered_comment_ids"])
        self.assertTrue(result["matched_identity"])
        self.assertEqual(result["old_missing_markdown_count"], 2)
        self.assertTrue(result["dependency_reproduced"])
        for row in result["rows"]:
            self.assertTrue(row["new_has_body"] and row["new_has_markdown"])
            self.assertEqual(row["markdown_sha256"], row["new_markdown_sha256"])
            self.assertGreater(row["markdown_bytes"], 0)
            self.assertGreater(row["new_body_bytes"], 0)
            if row["old_has_markdown"]:
                self.assertEqual(row["old_markdown_sha256"], row["new_markdown_sha256"])
            else:
                self.assertIsNone(row["old_markdown_sha256"])
        encoded = json.dumps(result)
        self.assertNotIn("**field fixture", encoded)
        self.assertNotIn("<b>", encoded)
        self.assertNotIn("do-not-save-author", encoded)
        self.assertNotIn("https://", encoded)
        query = parse_qs(urlparse(api.calls[1][0]).query)
        self.assertEqual(query, {"base": [PROBE.OLD_FILTER_ID], "include": ["comment.body"], "unsafe": ["true"]})
        discovery = parse_qs(urlparse(api.calls[2][0]).query)
        self.assertEqual(discovery["pagesize"], ["3"])
        self.assertEqual(discovery["todate"], [str(PROBE.TO_SECONDS - 1)])
        self.assertNotIn("tagged", discovery)
        self.assertEqual(urlsplit(api.calls[3][0]).path, "/2.3/comments/501;502;503")
        self.assertEqual(urlsplit(api.calls[4][0]).path, urlsplit(api.calls[3][0]).path)

    def test_old_complete_markdown_passes_without_dependency_claim(self):
        result, _, _ = self.run_fixture(fixtures(all_old_markdown=True))
        self.assertEqual(result["status"], "Passed")
        self.assertFalse(result["dependency_reproduced"])
        self.assertEqual(result["old_missing_markdown_count"], 0)
        self.assertEqual(result["dependency_statement"], "old_missing_not_reproduced_on_fixture")

    def test_id_matching_does_not_depend_on_array_order(self):
        payloads = fixtures()
        payloads[3]["items"].reverse()
        payloads[4]["items"] = payloads[4]["items"][1:] + payloads[4]["items"][:1]
        result, _, _ = self.run_fixture(payloads)
        self.assertEqual(result["status"], "Passed")
        self.assertEqual([row["comment_id"] for row in result["rows"]], [501, 502, 503])

    def test_filter_change_is_exact_and_stops_before_comments(self):
        for index, change, code in [
            (0, lambda row: row.update(filter_type="safe"), "field_probe_filter_contract"),
            (1, lambda row: row["included_fields"].append("comment.score"), "field_probe_new_filter_fields"),
            (1, lambda row: row["included_fields"].remove("comment.body"), "field_probe_new_filter_fields"),
        ]:
            payloads = fixtures()
            change(payloads[index]["items"][0])
            result, api, _ = self.run_fixture(payloads)
            self.assertEqual(result["status"], "Failed")
            self.assertEqual(result["error_code"], code)
            self.assertEqual(len(api.calls), index + 1)

    def test_opaque_filter_printable_punctuation_is_url_encoded(self):
        payloads = fixtures()
        identifier = "!new:filter/@+[]{}=$,"
        payloads[1]["items"][0]["filter"] = identifier
        result, api, _ = self.run_fixture(payloads)
        self.assertEqual(result["status"], "Passed")
        self.assertEqual(result["new_filter_id"], identifier)
        self.assertEqual(parse_qs(urlparse(api.calls[4][0]).query)["filter"], [identifier])

    def test_requires_exactly_three_distinct_comments_in_window(self):
        for change in [lambda rows: rows.pop(), lambda rows: rows.append(copy.deepcopy(rows[0])),
                       lambda rows: rows[0].update(creation_date=PROBE.TO_SECONDS)]:
            payloads = fixtures()
            change(payloads[2]["items"])
            result, api, _ = self.run_fixture(payloads)
            self.assertEqual(result["status"], "Failed")
            self.assertEqual(len(api.calls), 3)

    def test_old_new_identity_and_existing_markdown_must_match(self):
        changes = [({"post_id": 2222}, "field_probe_comment_identity_changed"),
                   ({"creation_date": PROBE.FROM_SECONDS + 99}, "field_probe_comment_identity_changed"),
                   ({"comment_id": 999}, "field_probe_same_ids_required"),
                   ({"body_markdown": "different exact text"}, "field_probe_existing_markdown_changed")]
        for change, code in changes:
            payloads = fixtures(all_old_markdown=True)
            payloads[4]["items"][0].update(change)
            result, api, _ = self.run_fixture(payloads)
            self.assertEqual(result["status"], "Failed")
            self.assertEqual(result["error_code"], code)
            self.assertEqual(len(api.calls), 5)

    def test_new_fields_must_be_present_and_nonempty(self):
        for change in [lambda row: row.pop("body_markdown"), lambda row: row.update(body=""),
                       lambda row: row.update(body_markdown=None), lambda row: row.update(body=1)]:
            payloads = fixtures()
            change(payloads[4]["items"][0])
            result, _, _ = self.run_fixture(payloads)
            self.assertEqual(result["status"], "Failed")
            self.assertEqual(result["error_code"], "field_probe_new_fields_missing")

    def test_backoff_waits_before_any_next_method_and_quota_zero_stops(self):
        payloads = fixtures()
        payloads[0]["backoff"] = 2
        result, api, clock = self.run_fixture(payloads)
        self.assertEqual(result["status"], "Passed")
        self.assertGreaterEqual(api.calls[1][2] - api.calls[0][2], 2)
        self.assertAlmostEqual(sum(clock.waits), 2)
        payloads = fixtures()
        payloads[1]["quota_remaining"] = 0
        result, api, _ = self.run_fixture(payloads)
        self.assertEqual(result["error_code"], "field_probe_quota_exhausted")
        self.assertEqual(len(api.calls), 2)

    def test_time_budget_stops_without_retry(self):
        payloads = fixtures()
        payloads[0]["backoff"] = 120
        result, api, _ = self.run_fixture(payloads)
        self.assertEqual(result["error_code"], "field_probe_time_limit")
        self.assertEqual(len(api.calls), 1)
        result, api, _ = self.run_fixture(duration=31)
        self.assertEqual(result["error_code"], "field_probe_time_limit")
        self.assertEqual(len(api.calls), 4)

    def test_network_failure_never_echoes_exception_or_retries(self):
        calls = []
        marker = "private original text query and token"
        def fail(*args, **kwargs):
            calls.append(1)
            raise PROBE.adapters.SourceError(marker, code="source_network_error",
                                              metadata={"stage": "request", "exception_type": "URLError", "token": marker})
        result = PROBE.run_probe("a" * 64, "b" * 64, get_json=fail)
        self.assertEqual(result["status"], "Failed")
        self.assertEqual(result["error_code"], "source_network_error")
        self.assertEqual(len(calls), 1)
        self.assertNotIn(marker, json.dumps(result))

    def test_terminal_is_0600_create_only_and_contains_real_source_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary = Path(temporary).resolve()
            protocol = temporary / "protocol.md"
            with protocol.open("x") as output:
                output.write("Synthetic protocol for offline test")
            target = Path(temporary) / "run/field-probe.json"
            api = FakeAPI(fixtures())
            result = PROBE.record_probe(protocol, target, get_json=api)
            self.assertEqual(result["status"], "Passed")
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            self.assertEqual(result["protocol_sha256"], hashlib.sha256(protocol.read_bytes()).hexdigest())
            self.assertEqual(result["script_sha256"], hashlib.sha256(Path(PROBE.__file__).read_bytes()).hexdigest())
            original = target.read_bytes()
            with self.assertRaises(FileExistsError):
                PROBE.record_probe(protocol, target, get_json=api)
            self.assertEqual(len(api.calls), 5)
            self.assertEqual(target.read_bytes(), original)
            link = Path(temporary) / "symlink"
            os.symlink(target.parent, link)
            with self.assertRaises(PROBE.ProbeError):
                PROBE.record_probe(protocol, link / "different.json", get_json=api)


if __name__ == "__main__":
    unittest.main()
