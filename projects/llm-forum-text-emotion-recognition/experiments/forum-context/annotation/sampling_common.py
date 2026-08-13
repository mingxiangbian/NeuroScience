#!/usr/bin/env python3
"""Shared metadata-only primitives for the IAC annotation sampling pilot."""

from __future__ import annotations

import gzip
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Mapping, Sequence


PROTOCOL_ID = "DATA-FCTX-SAMPLE-V1"
SEED = "07f4b8c18479c240af5354cc1d316fb8"

EXPECTED_CLEANING_SHA256 = (
    "b1f3022320980c96c5353be16401764a78e0bc40ebb21d71399fe4efcb05fcc7"
)
EXPECTED_DEDUP_SHA256 = (
    "13a5266a12f9574f073c3c7ce72e785e7d019573961507e1b0631f0a50bd7d4f"
)
EXPECTED_LABEL_PROTOCOL_SHA256 = (
    "0de4bf6243f223ea1a72b3fa48867b59abf6cd19ff95104ff53d00856b0d376a"
)
EXPECTED_SOURCE_SHA256 = (
    "e26e6d27a5fc88ee5837b3838f099f8268d42fe50fbbd9cd88b66dfe7744dd9c"
)

PRIMARY_LANES: tuple[tuple[str, int], ...] = (
    ("representative", 80),
    ("diag_sarcasm", 10),
    ("diag_hostility_affect", 10),
    ("diag_short_context", 10),
    ("diag_distinct_quote", 10),
)
RESERVE_LANES: tuple[tuple[str, int], ...] = (
    ("representative", 20),
    ("diag_sarcasm", 10),
    ("diag_hostility_affect", 10),
    ("diag_short_context", 10),
    ("diag_distinct_quote", 10),
)

INSERT_PREFIX = b"INSERT INTO `"
SELECTED_RAW_COLUMNS: Mapping[str, frozenset[int]] = {
    "discussion_topic": frozenset({0}),
    "mturk_2010_qr_entry": frozenset({0, 1, 2, 3, 4}),
    "mturk_2010_qr_task1_average_response": frozenset(
        {0, 1, 2, 5, 7, 9, 11}
    ),
}


@dataclass(frozen=True)
class TargetWeakSignal:
    linked_rows: int
    sarcasm: bool
    hostility_affect: bool


@dataclass(frozen=True)
class WeakMetadata:
    targets: Mapping[tuple[int, int], TargetWeakSignal]
    topic_discussions: frozenset[int]
    stats: Mapping[str, int]


@dataclass(frozen=True)
class Candidate:
    sample_uid: str
    thread_uid: str
    review_cluster_uid: str | None
    target_word_count: int
    target_has_quote: bool
    total_flag_count: int
    severe_flag_count: int
    topic_linked: bool
    qr_annotated: bool
    diag_sarcasm: bool
    diag_hostility_affect: bool
    diag_short_context: bool
    diag_distinct_quote: bool


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rank_digest(lane: str, sample_uid: str) -> str:
    payload = f"{PROTOCOL_ID}\n{SEED}\n{lane}\n{sample_uid}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_frozen_hashes(
    *,
    cleaning_db: Path,
    dedup_db: Path,
    source: Path,
    label_protocol: Path,
) -> dict[str, str]:
    actual = {
        "cleaning_database": sha256_file(cleaning_db),
        "dedup_database": sha256_file(dedup_db),
        "source_dump": sha256_file(source),
        "label_protocol": sha256_file(label_protocol),
    }
    expected = {
        "cleaning_database": EXPECTED_CLEANING_SHA256,
        "dedup_database": EXPECTED_DEDUP_SHA256,
        "source_dump": EXPECTED_SOURCE_SHA256,
        "label_protocol": EXPECTED_LABEL_PROTOCOL_SHA256,
    }
    mismatches = [
        name for name, expected_hash in expected.items() if actual[name] != expected_hash
    ]
    if mismatches:
        raise ValueError(f"frozen input hash mismatch: {', '.join(mismatches)}")
    return actual


def _scan_mysql_string(
    data: bytes, start: int, *, capture: bool
) -> tuple[bytes | None, int]:
    output = bytearray() if capture else None
    index = start + 1
    escapes = {
        ord("0"): 0,
        ord("b"): 8,
        ord("n"): 10,
        ord("r"): 13,
        ord("t"): 9,
        ord("Z"): 26,
    }
    while index < len(data):
        current = data[index]
        if current == ord("\\"):
            index += 1
            if index >= len(data):
                raise ValueError("unterminated MySQL escape")
            if output is not None:
                output.append(escapes.get(data[index], data[index]))
            index += 1
            continue
        if current == ord("'"):
            if index + 1 < len(data) and data[index + 1] == ord("'"):
                if output is not None:
                    output.append(ord("'"))
                index += 2
                continue
            return (bytes(output) if output is not None else None), index + 1
        if output is not None:
            output.append(current)
        index += 1
    raise ValueError("unterminated MySQL string")


def _parse_selected_values(
    data: bytes, selected_columns: frozenset[int]
) -> Iterator[dict[int, bytes | None]]:
    index = 0
    length = len(data)
    while index < length:
        while index < length and data[index] in b" \t\r\n,;":
            index += 1
        if index >= length:
            return
        if data[index] != ord("("):
            raise ValueError(f"expected row at byte {index}")
        index += 1
        column = 0
        selected: dict[int, bytes | None] = {}
        while index < length:
            capture = column in selected_columns
            if data[index] == ord("'"):
                value, index = _scan_mysql_string(data, index, capture=capture)
                if capture:
                    selected[column] = value
            else:
                start = index
                while index < length and data[index] not in b",)":
                    index += 1
                if capture:
                    token = data[start:index].strip()
                    selected[column] = None if token == b"NULL" else token
            if index >= length:
                raise ValueError("unterminated MySQL row")
            column += 1
            if data[index] == ord(","):
                index += 1
                continue
            if data[index] == ord(")"):
                index += 1
                yield selected
                break
            raise ValueError(f"unexpected byte {data[index:index + 1]!r}")


def iter_selected_insert_rows(
    path: Path,
    selected_columns: Mapping[str, frozenset[int]] = SELECTED_RAW_COLUMNS,
) -> Iterator[tuple[str, dict[int, bytes | None]]]:
    """Yield selected numeric/linkage fields without retaining forum text fields."""

    with gzip.open(path, "rb") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.startswith(INSERT_PREFIX):
                continue
            table_end = line.find(b"`", len(INSERT_PREFIX))
            if table_end < 0:
                raise ValueError(f"invalid INSERT header at line {line_number}")
            table = line[len(INSERT_PREFIX) : table_end].decode("ascii")
            wanted = selected_columns.get(table)
            if wanted is None:
                continue
            marker = b" VALUES "
            values_start = line.find(marker, table_end)
            if values_start < 0:
                raise ValueError(f"missing VALUES at line {line_number}")
            payload = line[values_start + len(marker) :]
            for row in _parse_selected_values(payload, wanted):
                yield table, row


def _as_int(value: bytes | None) -> int | None:
    return None if value is None else int(value)


def _as_float(value: bytes | None) -> float:
    if value is None:
        raise ValueError("required numeric metadata is NULL")
    return float(value)


def load_weak_metadata(source: Path) -> WeakMetadata:
    entries: dict[tuple[int, int], tuple[int, int, int | None]] = {}
    averages: dict[tuple[int, int], tuple[int, float, float, float, float]] = {}
    topic_discussions: set[int] = set()
    counts = {
        "discussion_topic_rows": 0,
        "qr_entry_rows": 0,
        "qr_entry_rows_with_target": 0,
        "qr_average_rows": 0,
        "qr_joined_rows": 0,
        "qr_orphan_average_rows": 0,
        "qr_conflicting_entry_keys": 0,
        "qr_conflicting_average_keys": 0,
    }

    for table, row in iter_selected_insert_rows(source):
        if table == "discussion_topic":
            discussion_id = _as_int(row[0])
            if discussion_id is not None:
                topic_discussions.add(discussion_id)
            counts["discussion_topic_rows"] += 1
            continue

        key = (_as_int(row[0]), _as_int(row[1]))
        if key[0] is None or key[1] is None:
            raise ValueError(f"NULL QR key in {table}")
        typed_key = (int(key[0]), int(key[1]))

        if table == "mturk_2010_qr_entry":
            counts["qr_entry_rows"] += 1
            discussion_id = _as_int(row[2])
            post_id = _as_int(row[3])
            quote_index = _as_int(row[4])
            if discussion_id is None or post_id is None:
                continue
            value = (discussion_id, post_id, quote_index)
            previous = entries.get(typed_key)
            if previous is not None and previous != value:
                counts["qr_conflicting_entry_keys"] += 1
            entries[typed_key] = value
            counts["qr_entry_rows_with_target"] += 1
            continue

        if table == "mturk_2010_qr_task1_average_response":
            counts["qr_average_rows"] += 1
            value = (
                int(_as_float(row[2])),
                _as_float(row[5]),
                _as_float(row[7]),
                _as_float(row[9]),
                _as_float(row[11]),
            )
            previous = averages.get(typed_key)
            if previous is not None and previous != value:
                counts["qr_conflicting_average_keys"] += 1
            averages[typed_key] = value

    target_rows: dict[tuple[int, int], list[tuple[int, float, float, float, float]]] = {}
    for key, average in averages.items():
        entry = entries.get(key)
        if entry is None:
            counts["qr_orphan_average_rows"] += 1
            continue
        target_rows.setdefault((entry[0], entry[1]), []).append(average)
        counts["qr_joined_rows"] += 1

    targets: dict[tuple[int, int], TargetWeakSignal] = {}
    for target, rows in target_rows.items():
        eligible_rows = [row for row in rows if row[0] >= 3]
        targets[target] = TargetWeakSignal(
            linked_rows=len(rows),
            sarcasm=any(row[4] >= 0.5 for row in eligible_rows),
            hostility_affect=any(
                row[1] <= -2 or row[2] <= -2 or row[3] <= -2
                for row in eligible_rows
            ),
        )

    counts.update(
        {
            "qr_unique_annotated_targets": len(targets),
            "qr_sarcasm_eligible_targets": sum(
                signal.sarcasm for signal in targets.values()
            ),
            "qr_hostility_affect_eligible_targets": sum(
                signal.hostility_affect for signal in targets.values()
            ),
            "topic_linked_discussions": len(topic_discussions),
        }
    )
    if counts["qr_conflicting_entry_keys"] or counts["qr_conflicting_average_keys"]:
        raise ValueError("conflicting QR metadata keys")
    return WeakMetadata(
        targets=targets,
        topic_discussions=frozenset(topic_discussions),
        stats=counts,
    )


def load_candidates(
    cleaning_db: Path, dedup_db: Path, weak: WeakMetadata
) -> tuple[list[Candidate], dict[str, int]]:
    connection = sqlite3.connect(f"file:{cleaning_db}?mode=ro", uri=True)
    connection.execute("PRAGMA query_only = ON")
    connection.execute("ATTACH DATABASE ? AS dedup", (str(dedup_db),))
    try:
        distinct_quote_samples = {
            row[0]
            for row in connection.execute(
                """
                SELECT DISTINCT cp.sample_uid
                FROM candidate_pairs AS cp
                JOIN source_quotes AS q
                  ON q.source_discussion_id = cp.source_discussion_id
                 AND q.source_post_id = cp.target_source_post_id
                WHERE cp.eligible = 1
                  AND q.parent_quote_index IS NULL
                  AND q.text_offset IS NOT NULL
                  AND (
                      q.quote_source_discussion_id IS NULL
                      OR q.quote_source_post_id IS NULL
                      OR q.quote_source_discussion_id != cp.source_discussion_id
                      OR q.quote_source_post_id != cp.parent_source_post_id
                  )
                """
            )
        }
        rows = connection.execute(
            """
            SELECT cp.sample_uid,
                   cp.thread_uid,
                   cp.source_discussion_id,
                   cp.target_source_post_id,
                   cd.review_cluster_uid,
                   target.word_count,
                   target.quote_char_count,
                   cd.total_flag_count,
                   cd.severe_flag_count,
                   EXISTS (
                       SELECT 1
                       FROM candidate_soft_flags AS sf
                       WHERE sf.sample_uid = cp.sample_uid
                         AND sf.flag = 'target_short'
                   ) AS target_short_flag,
                   CASE
                       WHEN discussion.title_model IS NOT NULL
                        AND target.model_body IS NOT NULL
                        AND target.model_full IS NOT NULL
                        AND parent.model_body IS NOT NULL
                       THEN 1 ELSE 0
                   END AS view_reconstructible
            FROM candidate_pairs AS cp
            JOIN dedup.candidate_decisions AS cd
              ON cd.sample_uid = cp.sample_uid
            JOIN cleaned_posts AS target
              ON target.source_discussion_id = cp.source_discussion_id
             AND target.source_post_id = cp.target_source_post_id
            JOIN cleaned_posts AS parent
              ON parent.source_discussion_id = cp.source_discussion_id
             AND parent.source_post_id = cp.parent_source_post_id
            JOIN discussions AS discussion
              ON discussion.source_discussion_id = cp.source_discussion_id
            WHERE cp.eligible = 1
              AND cd.eligible_after_auto_dedup = 1
            ORDER BY cd.candidate_index
            """
        )
        candidates: list[Candidate] = []
        short_flag_mismatches = 0
        unreconstructible = 0
        for row in rows:
            (
                sample_uid,
                thread_uid,
                discussion_id,
                target_post_id,
                review_cluster_uid,
                target_word_count,
                quote_char_count,
                total_flag_count,
                severe_flag_count,
                target_short_flag,
                view_reconstructible,
            ) = row
            if not view_reconstructible:
                unreconstructible += 1
                continue
            short_by_count = int(target_word_count) < 3
            short_by_flag = bool(target_short_flag)
            if short_by_count != short_by_flag:
                short_flag_mismatches += 1
            signal = weak.targets.get((int(discussion_id), int(target_post_id)))
            candidates.append(
                Candidate(
                    sample_uid=str(sample_uid),
                    thread_uid=str(thread_uid),
                    review_cluster_uid=(
                        None if review_cluster_uid is None else str(review_cluster_uid)
                    ),
                    target_word_count=int(target_word_count),
                    target_has_quote=int(quote_char_count) > 0,
                    total_flag_count=int(total_flag_count),
                    severe_flag_count=int(severe_flag_count),
                    topic_linked=int(discussion_id) in weak.topic_discussions,
                    qr_annotated=signal is not None,
                    diag_sarcasm=bool(signal and signal.sarcasm),
                    diag_hostility_affect=bool(
                        signal and signal.hostility_affect
                    ),
                    diag_short_context=short_by_flag,
                    diag_distinct_quote=str(sample_uid) in distinct_quote_samples,
                )
            )
    finally:
        connection.close()

    stats = {
        "candidate_rows": len(candidates),
        "unreconstructible_rows": unreconstructible,
        "short_flag_mismatches": short_flag_mismatches,
        "distinct_quote_candidate_rows": len(distinct_quote_samples),
    }
    return candidates, stats


def predicate_for_lane(lane: str) -> Callable[[Candidate], bool]:
    if lane == "representative":
        return lambda candidate: True
    attribute = {
        "diag_sarcasm": "diag_sarcasm",
        "diag_hostility_affect": "diag_hostility_affect",
        "diag_short_context": "diag_short_context",
        "diag_distinct_quote": "diag_distinct_quote",
    }.get(lane)
    if attribute is None:
        raise KeyError(f"unknown lane: {lane}")
    return lambda candidate: bool(getattr(candidate, attribute))


def nearest_rank(values: Sequence[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(percentile * len(ordered) + 0.999999) - 1))
    return ordered[index]


def summarize_candidates(candidates: Sequence[Candidate]) -> dict[str, object]:
    count = len(candidates)
    return {
        "count": count,
        "topic_linked": sum(candidate.topic_linked for candidate in candidates),
        "target_has_quote": sum(candidate.target_has_quote for candidate in candidates),
        "target_short": sum(candidate.diag_short_context for candidate in candidates),
        "distinct_quote": sum(candidate.diag_distinct_quote for candidate in candidates),
        "qr_annotated": sum(candidate.qr_annotated for candidate in candidates),
        "sarcasm_eligible": sum(candidate.diag_sarcasm for candidate in candidates),
        "hostility_affect_eligible": sum(
            candidate.diag_hostility_affect for candidate in candidates
        ),
        "any_soft_flag": sum(candidate.total_flag_count > 0 for candidate in candidates),
        "any_severe_flag": sum(candidate.severe_flag_count > 0 for candidate in candidates),
        "target_word_count_nearest_rank": {
            "p50": nearest_rank([c.target_word_count for c in candidates], 0.50),
            "p90": nearest_rank([c.target_word_count for c in candidates], 0.90),
            "p95": nearest_rank([c.target_word_count for c in candidates], 0.95),
        },
    }


def canonical_json_sha256(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
