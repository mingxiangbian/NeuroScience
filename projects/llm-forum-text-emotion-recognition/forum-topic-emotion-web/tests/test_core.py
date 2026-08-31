import unittest
import json
from topicweb.core import ValidationError, aggregate, extended_views, make_record, validate_request


def record(text="same", source_id="1", created_at=None):
    return make_record(source="upload", site="upload", object_type="row",
                       source_object_id=source_id, model_input_text=text, created_at=created_at)


def prediction(values):
    return {"prediction": values, "used_path": "m1", "m1_probabilities": [.1] * 6,
            "counters": {"m1_attempts": 1}, "m1_prediction": values}


class CoreTests(unittest.TestCase):
    def test_exact_hash_and_normalized_hash_are_distinct_contracts(self):
        a, b = record("Ａ  B"), record("a b", "2")
        self.assertNotEqual(a["model_input_hash"], b["model_input_hash"])
        self.assertEqual(a["dedup_hash"], b["dedup_hash"])
        self.assertNotEqual(a["record_id"], b["record_id"])
        self.assertEqual(a["model_input_text"], "Ａ  B")

    def test_identical_text_occurrences_remain_separate(self):
        records = [record(), record(source_id="2")]
        result = aggregate(records, [prediction([1, 1, 0, 0, 0, 0])] * 2)
        self.assertEqual(result["summary"]["eligible_items"], 2)
        self.assertEqual(result["summary"]["exact_input_groups"], 1)
        self.assertEqual(result["emotions"][0]["count"], 2)
        self.assertEqual(result["emotions"][0]["positive_share"], .5)

    def test_missing_is_not_neutral_and_no_date_fabrication(self):
        result = aggregate([record(), record(source_id="2")], [prediction([0]*6), None])
        self.assertEqual(result["summary"]["coverage"], .5)
        self.assertEqual(result["summary"]["neutral_rate"], 1)
        self.assertEqual(result["summary"]["missing_predictions"], 1)
        self.assertIsNone(result["emotions"][0]["positive_share"])
        self.assertEqual(result["daily"], [])

    def test_empty_denominators_null(self):
        result = aggregate([], [])
        self.assertIsNone(result["summary"]["coverage"])
        self.assertIsNone(result["emotions"][0]["prevalence"])
        self.assertIsNone(result["routing"]["paired_disagreement"])

    def test_utc_and_frozen_decisions(self):
        row = record(created_at="2026-08-24T00:30:00+08:00")
        p = prediction([1, 0, 0, 0, 0, 0])
        p.update(m3_prediction=[0]*6, m3_probabilities=[.6]*6)
        result = aggregate([row], [p])
        self.assertEqual(result["daily"][0]["date"], "2026-08-23")
        self.assertEqual(result["routing"]["paired_disagreement"], 1)

    def test_shape_fails_closed(self):
        with self.assertRaises(ValidationError):
            aggregate([record()], [])
        with self.assertRaises(ValidationError):
            aggregate([record()], [{"prediction": [0]*5}])

    def test_text_and_url_boundaries(self):
        for text in ("", "   ", "x" * 65537):
            with self.assertRaises(ValidationError):
                record(text)
        with self.assertRaises(ValidationError):
            make_record(source="upload", site="upload", object_type="row", source_object_id="1",
                        model_input_text="text", source_url="javascript:alert(1)")

    def test_research_does_not_inherit_demo_budget(self):
        payload = {"source": "upload", "mode": "research", "max_qwen_calls": 0,
                   "upload": {"format": "jsonl", "content": '{"text":"hello"}'}}
        self.assertEqual(validate_request(payload)["max_qwen_calls"], 500)
        payload["mode"] = "demo"
        self.assertEqual(validate_request(payload)["max_qwen_calls"], 0)

    def test_unknown_site_and_audit_fail_closed(self):
        with self.assertRaises(ValidationError):
            validate_request({"source": "discourse"})
        with self.assertRaises(ValidationError):
            validate_request({"audit_rate": .1})

    def test_discourse_only_accepts_reviewed_category_without_search_or_dates(self):
        payload = {"source": "discourse", "query": {"site": "discuss.python.org", "category_id": 7}}
        self.assertEqual(validate_request(payload)["query"], {"site": "discuss.python.org", "category_id": 7, "max_topics": 100, "max_items": 400})
        for changes in ({"site": "other.example"}, {"category_id": 8}, {"category_id": True}, {"query": "python"}, {"from_utc": "2026-08-01T00:00:00Z"}, {"topic_url": "https://discuss.python.org/t/1"}):
            with self.assertRaises(ValidationError):
                validate_request({**payload, "query": {**payload["query"], **changes}})

    def test_derived_does_not_change_legacy_object_metrics_or_inputs(self):
        records = [record("same", "1", "2026-08-24T01:00:00Z"), record("same", "2", "2026-08-24T02:00:00Z"), record("other", "3")]
        results = [prediction([1, 0, 0, 0, 0, 0]), prediction([0, 1, 0, 0, 0, 0]), None]
        before = json.dumps([records, results, aggregate(records, results)], sort_keys=True)
        derived = extended_views(records, results)
        self.assertEqual(before, json.dumps([records, results, aggregate(records, results)], sort_keys=True))
        legacy = aggregate(records, results)
        objects = derived["views"]["object_weighted"]
        self.assertEqual(objects["emotions"], legacy["emotions"])
        self.assertEqual(objects["summary"]["successful_units"], legacy["summary"]["successful_items"])
        self.assertEqual(objects["summary"]["neutral_rate"], legacy["summary"]["neutral_rate"])
        self.assertNotIn("derived", legacy)

    def test_unique_weights_average_successful_occurrences_not_or(self):
        records = [record("Ａ  B", "1"), record("a b", "2"), record("a b", "3"), record("other", "4"), record("missing", "5")]
        results = [prediction([1, 0, 0, 0, 0, 0]), prediction([0, 1, 0, 0, 0, 0]), None, prediction([1, 1, 0, 0, 0, 0]), None]
        data = extended_views(records, results)
        unique = data["views"]["normalized_unique_text"]
        self.assertEqual(unique["summary"]["eligible_units"], 3)
        self.assertEqual(unique["summary"]["successful_units"], 2)
        self.assertEqual(unique["summary"]["coverage"], 2/3)
        self.assertEqual(unique["summary"]["successful_occurrences"], 3)
        self.assertEqual(unique["summary"]["mixed_prediction_groups"], 1)
        self.assertEqual(unique["summary"]["partially_predicted_groups"], 1)
        self.assertEqual(unique["emotions"][0]["count"], 1.5)
        self.assertEqual(unique["emotions"][0]["prevalence"], .75)
        self.assertEqual(unique["emotions"][0]["positive_share"], .5)
        self.assertEqual(data["diagnostics"]["successful_items"], 3)
        self.assertEqual(data["diagnostics"]["coverage"], 3/5)

    def test_daily_and_utc_monday_weekly_grouping_are_bucket_local(self):
        records = [record("same", "1", "2026-08-24T00:30:00+08:00"),
                   record("same", "2", "2026-08-24T01:00:00Z"),
                   record("same", "3", "2026-08-25T01:00:00Z"), record("undated", "4")]
        results = [prediction([1, 0, 0, 0, 0, 0]), prediction([0, 1, 0, 0, 0, 0]), prediction([0]*6), prediction([1]*6)]
        data = extended_views(records, results)
        trends = data["views"]["normalized_unique_text"]["trends"]
        self.assertEqual([row["date"] for row in trends["daily"]], ["2026-08-23", "2026-08-24", "2026-08-25"])
        self.assertEqual([row["date"] for row in trends["weekly"]], ["2026-08-17", "2026-08-24"])
        self.assertEqual(trends["weekly"][1]["summary"]["successful_units"], 1)
        self.assertEqual(trends["weekly"][1]["emotions"][1]["count"], .5)
        self.assertEqual(trends["weekly"][1]["summary"]["neutral_rate"], .5)
        self.assertEqual(data["diagnostics"]["undated_items"], 1)
        self.assertEqual(len(trends["daily"][0]["emotions"]), 6)

    def test_diagnostics_do_not_confuse_hypothetical_routes_with_calls(self):
        result = prediction([1, 1, 0, 0, 0, 0])
        result.update(route_requested=False, hypothetical_route=True, threshold_margin=.2,
                      tokenlengths={"m1": {"input_tokens": 700, "used_tokens": 512, "truncated": True}, "m3": None})
        diagnostics = extended_views([record()], [result])["diagnostics"]
        self.assertEqual(diagnostics["routing"]["actual_rate"], 0)
        self.assertEqual(diagnostics["routing"]["hypothetical_rate"], 1)
        self.assertEqual(diagnostics["routing"]["m3_used"], 0)
        self.assertEqual(diagnostics["cardinality"]["mean"], 2)
        self.assertEqual(diagnostics["cardinality"]["counts"], [0, 0, 1, 0, 0, 0, 0])
        self.assertEqual(diagnostics["m1_threshold_margin"]["mean"], .2)
        self.assertEqual(diagnostics["tokenlengths"]["m1"]["truncated_rate"], 1)
        self.assertIsNone(diagnostics["tokenlengths"]["m3"]["truncated_rate"])
        self.assertEqual(diagnostics["tokenlengths"]["m3"]["used_tokens"]["n"], 0)

    def test_derived_missing_predictions_do_not_become_zero_rates(self):
        data = extended_views([record(created_at="2026-08-24T00:00:00Z")], [None])
        for view in data["views"].values():
            self.assertEqual(view["summary"]["eligible_units"], 1)
            self.assertIsNone(view["emotions"][0]["prevalence"])
            self.assertIsNone(view["trends"]["weekly"][0]["emotions"][0]["positive_share"])
        empty = extended_views([], [])
        self.assertEqual(empty["views"]["object_weighted"]["trends"]["daily"], [])
        self.assertIsNone(empty["diagnostics"]["cardinality"]["mean"])

    def test_type_and_observed_route_strata_group_locally(self):
        records = [record("same", "1"), record("SAME", "2"), record("same", "3"), record("other", "4")]
        for row, kind in zip(records, ("question", "comment", "comment", "question")):
            row["object_type"] = kind
        results = [dict(prediction([1, 0, 0, 0, 0, 0]), route_requested=True),
                   dict(prediction([0, 1, 0, 0, 0, 0]), route_requested=False), None,
                   prediction([0, 0, 0, 0, 0, 1])]
        data = extended_views(records, results)
        unique = data["views"]["normalized_unique_text"]
        self.assertEqual(unique["emotions"][0]["count"], .5)
        types = unique["strata"]["object_type"]
        self.assertEqual([row["group"] for row in types], ["comment", "question"])
        self.assertEqual(types[0]["summary"]["successful_units"], 1)
        self.assertEqual(types[0]["emotions"][1]["prevalence"], 1)
        routes = unique["strata"]["route_requested"]
        self.assertEqual([row["group"] for row in routes], ["false", "true", "unknown"])
        self.assertEqual(routes[1]["emotions"][0]["prevalence"], 1)
        self.assertEqual(routes[2]["summary"]["eligible_units"], 2)
        self.assertEqual(routes[2]["summary"]["successful_units"], 1)
        self.assertEqual(routes[2]["emotions"][5]["positive_share"], 1)
        self.assertEqual(data["diagnostics"]["routing"]["actual_known_n"], 2)
        empty = extended_views([], [])["views"]["object_weighted"]["strata"]["route_requested"]
        self.assertEqual([row["group"] for row in empty], ["false", "true", "unknown"])
        self.assertTrue(all(row["summary"]["eligible_units"] == 0 and row["emotions"][0]["prevalence"] is None for row in empty))


if __name__ == "__main__":
    unittest.main()
