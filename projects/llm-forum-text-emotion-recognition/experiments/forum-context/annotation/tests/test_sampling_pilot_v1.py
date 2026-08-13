#!/usr/bin/env python3

from __future__ import annotations

import gzip
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


ANNOTATION_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANNOTATION_DIR))

import sample_iac2_pilot_v1 as sampler  # noqa: E402
import sampling_common as common  # noqa: E402
import verify_sampling_pilot_v1 as verifier  # noqa: E402


def candidate(
    index: int,
    *,
    thread: int | None = None,
    cluster: int | None = None,
    sarcasm: bool = False,
    hostility: bool = False,
    short: bool = False,
    quote: bool = False,
) -> common.Candidate:
    return common.Candidate(
        sample_uid=f"smp_{index:064x}",
        thread_uid=f"thr_{(thread if thread is not None else index):064x}",
        review_cluster_uid=(
            None if cluster is None else f"rvc_{cluster:064x}"
        ),
        target_word_count=2 if short else 10,
        target_has_quote=quote,
        total_flag_count=int(short),
        severe_flag_count=0,
        topic_linked=index % 2 == 0,
        qr_annotated=sarcasm or hostility,
        diag_sarcasm=sarcasm,
        diag_hostility_affect=hostility,
        diag_short_context=short,
        diag_distinct_quote=quote,
    )


class SelectiveParserTests(unittest.TestCase):
    def test_unselected_forum_text_is_not_returned(self) -> None:
        payload = (
            b"(1,2,3,4,5,6,'private, quote with \\'escape\\'',"
            b"'private response',NULL,'topic');"
        )
        rows = list(common._parse_selected_values(payload, frozenset({0, 1, 2, 3, 4})))
        self.assertEqual(rows, [{0: b"1", 1: b"2", 2: b"3", 3: b"4", 4: b"5"}])
        self.assertNotIn(b"private", repr(rows).encode("utf-8"))

    def test_weak_metadata_uses_only_linkage_and_scores(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "synthetic.sql.gz"
            dump = "".join(
                (
                    "INSERT INTO `discussion_topic` VALUES (3,9);\n",
                    "INSERT INTO `mturk_2010_qr_entry` VALUES "
                    "(1,2,3,4,0,20,'private quote','private response',NULL,'topic');\n",
                    "INSERT INTO `mturk_2010_qr_task1_average_response` VALUES "
                    "(1,2,5,0,0,-3,0,-2,0,1,0,0.6,0.3,0.1);\n",
                )
            )
            with gzip.open(source, "wb") as handle:
                handle.write(dump.encode("utf-8"))
            weak = common.load_weak_metadata(source)
        self.assertEqual(weak.topic_discussions, frozenset({3}))
        signal = weak.targets[(3, 4)]
        self.assertTrue(signal.sarcasm)
        self.assertTrue(signal.hostility_affect)
        self.assertNotIn("private", repr(weak))


class DeterministicSelectionTests(unittest.TestCase):
    def test_rank_matches_frozen_formula(self) -> None:
        sample_uid = "smp_" + "1" * 64
        payload = (
            f"{common.PROTOCOL_ID}\n{common.SEED}\nrepresentative\n{sample_uid}"
        ).encode("utf-8")
        self.assertEqual(
            common.rank_digest("representative", sample_uid),
            hashlib.sha256(payload).hexdigest(),
        )

    def test_sampler_enforces_thread_and_cluster_uniqueness(self) -> None:
        candidates = [
            candidate(1, thread=1),
            candidate(2, thread=1),
            candidate(3, cluster=7),
            candidate(4, cluster=7),
            candidate(5),
        ]
        selected, audit = sampler.select_lane(
            candidates,
            role="primary",
            lane="representative",
            rank_lane="representative",
            quota=3,
            predicate=lambda value: True,
            state=sampler.SelectionState(),
        )
        self.assertEqual(audit["status"], "passed")
        self.assertEqual(len({row.candidate.thread_uid for row in selected}), 3)
        clusters = [
            row.candidate.review_cluster_uid
            for row in selected
            if row.candidate.review_cluster_uid is not None
        ]
        self.assertEqual(len(clusters), len(set(clusters)))

    def test_verifier_replay_matches_sampler_order(self) -> None:
        candidates = [candidate(index, sarcasm=index % 2 == 0) for index in range(20)]
        state = sampler.SelectionState()
        selected, _ = sampler.select_lane(
            candidates,
            role="primary",
            lane="diag_sarcasm",
            rank_lane="diag_sarcasm",
            quota=5,
            predicate=common.predicate_for_lane("diag_sarcasm"),
            state=state,
        )
        replayed = verifier.replay_lane(
            candidates,
            lane="diag_sarcasm",
            rank_lane="diag_sarcasm",
            quota=5,
            predicate=common.predicate_for_lane("diag_sarcasm"),
            used_samples=set(),
            used_threads=set(),
            used_clusters=set(),
        )
        self.assertEqual(
            [row.candidate.sample_uid for row in selected],
            [row.sample_uid for row in replayed],
        )

    def test_frozen_budgets_sum_to_protocol_totals(self) -> None:
        self.assertEqual(sum(quota for _, quota in common.PRIMARY_LANES), 120)
        self.assertEqual(sum(quota for _, quota in common.RESERVE_LANES), 60)


class PublicPrivacyTests(unittest.TestCase):
    def test_public_payload_scan_rejects_identifiers(self) -> None:
        value = {"nested": {"sample_uid": "smp_" + "a" * 64}}
        violations = verifier.public_payload_violations(value)
        self.assertEqual(len(violations), 2)

    def test_public_payload_scan_accepts_aggregate_report_shape(self) -> None:
        value = {
            "candidate_rows": 403183,
            "privacy": {"forum_text_emitted": False},
            "sha256": "a" * 64,
        }
        self.assertEqual(verifier.public_payload_violations(value), [])


if __name__ == "__main__":
    unittest.main()
