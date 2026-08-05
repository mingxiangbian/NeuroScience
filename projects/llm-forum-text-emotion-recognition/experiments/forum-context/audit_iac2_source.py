#!/usr/bin/env python3
"""Audit IAC 2.0 MySQL dumps without retaining or emitting forum text."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


INSERT_PREFIX = b"INSERT INTO `"
WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*")
HTML_RE = re.compile(r"<[^>]+>")
PLACEHOLDERS = {
    "[deleted]",
    "[removed]",
    "deleted",
    "removed",
    "n/a",
    "none",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--createdebate", type=Path, required=True)
    parser.add_argument("--convinceme", type=Path, required=True)
    parser.add_argument("--fourforums", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unescape_mysql_string(data: bytes, start: int) -> tuple[bytes, int]:
    result = bytearray()
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
            escaped = data[index]
            result.append(escapes.get(escaped, escaped))
            index += 1
            continue
        if current == ord("'"):
            if index + 1 < len(data) and data[index + 1] == ord("'"):
                result.append(ord("'"))
                index += 2
                continue
            return bytes(result), index + 1
        result.append(current)
        index += 1

    raise ValueError("unterminated MySQL string")


def _parse_insert_values(data: bytes) -> Iterator[list[bytes | None]]:
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
        row: list[bytes | None] = []

        while index < length:
            if data[index] == ord("'"):
                value, index = _unescape_mysql_string(data, index)
                row.append(value)
            else:
                start = index
                while index < length and data[index] not in b",)":
                    index += 1
                token = data[start:index].strip()
                row.append(None if token == b"NULL" else token)

            if index >= length:
                raise ValueError("unterminated MySQL row")
            if data[index] == ord(","):
                index += 1
                continue
            if data[index] == ord(")"):
                index += 1
                yield row
                break
            raise ValueError(f"unexpected byte {data[index:index + 1]!r}")


def iter_insert_rows(
    path: Path, wanted_tables: set[str]
) -> Iterator[tuple[str, list[bytes | None]]]:
    with gzip.open(path, "rb") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.startswith(INSERT_PREFIX):
                continue
            table_end = line.find(b"`", len(INSERT_PREFIX))
            if table_end < 0:
                raise ValueError(f"invalid INSERT header at line {line_number}")
            table = line[len(INSERT_PREFIX) : table_end].decode("ascii")
            if table not in wanted_tables:
                continue
            values_marker = b" VALUES "
            values_start = line.find(values_marker, table_end)
            if values_start < 0:
                raise ValueError(f"missing VALUES at line {line_number}")
            payload = line[values_start + len(values_marker) :]
            for row in _parse_insert_values(payload):
                yield table, row


def as_int(value: bytes | None) -> int | None:
    return None if value is None else int(value)


def as_text(value: bytes | None) -> str:
    return "" if value is None else value.decode("utf-8", errors="replace")


def text_quality(value: bytes | None) -> tuple[int, int, bool, bool, bool]:
    text = as_text(value)
    stripped = text.strip()
    normalized = stripped.casefold()
    chars = len(stripped)
    tokens = len(WORD_RE.findall(stripped))
    placeholder = normalized in PLACEHOLDERS
    html_like = bool(HTML_RE.search(stripped))
    eligible = chars >= 20 and tokens >= 5 and not placeholder
    return chars, tokens, placeholder, html_like, eligible


def quantile(values: list[int], probability: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(probability * len(ordered)) - 1)
    return ordered[index]


def summarize_numeric(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None}
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
    }


def audit_corpus(path: Path, corpus: str) -> dict[str, object]:
    wanted_tables = {
        "author",
        "dataset_metadata",
        "discussion",
        "discussion_topic",
        "post",
        "quote",
        "text",
        "topic",
        "mturk_2010_p123_average_response",
        "mturk_2010_p123_entry",
        "mturk_2010_p123_post",
        "mturk_2010_qr_entry",
        "mturk_2010_qr_task1_average_response",
    }
    table_rows: Counter[str] = Counter()
    metadata_fields: list[str] = []
    selected_metadata: dict[str, str] = {}
    license_metadata: dict[str, str] = {}
    topic_labels: dict[int, str] = {}
    linked_topic_ids: Counter[int] = Counter()
    discussion_post_counts: Counter[int] = Counter()
    posts: dict[tuple[int, int], tuple[int, int | None, int]] = {}
    texts: dict[int, tuple[int, int, bool, bool, bool]] = {}
    response_types: Counter[str] = Counter()
    rebuttal_values: Counter[str] = Counter()
    quote_rows = 0
    quote_source_rows = 0
    quote_source_with_offsets = 0
    quote_same_discussion = 0
    quote_pairs: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    qr_entries: dict[tuple[int, int], tuple[int, int, int]] = {}
    qr_task1_keys: set[tuple[int, int]] = set()
    qr_task1_num_annots: list[float] = []
    qr_task1_emotion_fact: list[float] = []
    qr_task1_attacking_respectful: list[float] = []
    qr_task1_nasty_nice: list[float] = []
    qr_task1_sarcasm_yes: list[float] = []
    p123_posts: dict[tuple[int, int], tuple[int, int]] = {}
    p123_entries: dict[tuple[int, int], tuple[int, int, int]] = {}
    p123_average_keys: set[tuple[int, int]] = set()
    creation_dates: list[str] = []

    for table, row in iter_insert_rows(path, wanted_tables):
        table_rows[table] += 1

        if table == "dataset_metadata":
            field = as_text(row[1]).strip()
            value = as_text(row[2]).strip()
            metadata_fields.append(field)
            if field in {
                "title",
                "version",
                "original publication date",
                "current version date",
                "language tag",
                "synopsis",
                "notes",
            }:
                selected_metadata[field] = value
            if re.search(
                r"\blicen[cs]e\b|\bcopyright\b|\bterms?\b|\busage\b|\buse\b",
                field,
                re.I,
            ):
                license_metadata[field] = value
        elif table == "topic":
            topic_labels[int(row[0])] = as_text(row[1]).strip()
        elif table == "discussion_topic":
            linked_topic_ids[int(row[1])] += 1
        elif table == "post":
            discussion_id = int(row[0])
            post_id = int(row[1])
            parent_post_id = as_int(row[4])
            parent_missing = int(row[5])
            text_id = int(row[6])
            posts[(discussion_id, post_id)] = (
                text_id,
                parent_post_id,
                parent_missing,
            )
            discussion_post_counts[discussion_id] += 1
            creation_dates.append(as_text(row[3]))
            if corpus == "createdebate":
                response_types[as_text(row[9]) or "NULL"] += 1
            elif corpus == "convinceme":
                rebuttal_values[as_text(row[9]) or "NULL"] += 1
        elif table == "quote":
            quote_rows += 1
            discussion_id = int(row[0])
            post_id = int(row[1])
            source_discussion_id = as_int(row[6])
            source_post_id = as_int(row[7])
            if source_discussion_id is not None and source_post_id is not None:
                quote_source_rows += 1
                if source_discussion_id == discussion_id:
                    quote_same_discussion += 1
                if row[8] is not None and row[9] is not None:
                    quote_source_with_offsets += 1
                quote_pairs.add(
                    (
                        (discussion_id, post_id),
                        (source_discussion_id, source_post_id),
                    )
                )
        elif table == "text":
            texts[int(row[0])] = text_quality(row[1])
        elif table == "mturk_2010_qr_entry":
            if row[2] is not None and row[3] is not None and row[4] is not None:
                qr_entries[(int(row[0]), int(row[1]))] = (
                    int(row[2]),
                    int(row[3]),
                    int(row[4]),
                )
        elif table == "mturk_2010_qr_task1_average_response":
            key = (int(row[0]), int(row[1]))
            qr_task1_keys.add(key)
            qr_task1_num_annots.append(float(row[2]))
            qr_task1_attacking_respectful.append(float(row[5]))
            qr_task1_emotion_fact.append(float(row[7]))
            qr_task1_nasty_nice.append(float(row[9]))
            qr_task1_sarcasm_yes.append(float(row[11]))
        elif table == "mturk_2010_p123_post":
            if row[2] is not None and row[3] is not None:
                p123_posts[(int(row[0]), int(row[1]))] = (
                    int(row[2]),
                    int(row[3]),
                )
        elif table == "mturk_2010_p123_entry":
            p123_entries[(int(row[0]), int(row[1]))] = (
                int(row[2]),
                int(row[3]),
                int(row[4]),
            )
        elif table == "mturk_2010_p123_average_response":
            p123_average_keys.add((int(row[0]), int(row[1])))

    parent_nonnull = 0
    parent_missing_flag = 0
    parent_resolved = 0
    parent_resolved_flag_clean = 0
    usable_parent_pairs = 0
    post_text_missing = 0
    post_text_nonempty = 0
    post_text_placeholder = 0
    post_text_html_like = 0
    post_text_minimal_gate = 0

    for (discussion_id, _), (text_id, parent_post_id, parent_missing) in posts.items():
        target_quality = texts.get(text_id)
        if target_quality is None:
            post_text_missing += 1
        else:
            chars, _, placeholder, html_like, eligible = target_quality
            post_text_nonempty += int(chars > 0)
            post_text_placeholder += int(placeholder)
            post_text_html_like += int(html_like)
            post_text_minimal_gate += int(eligible)

        parent_missing_flag += int(parent_missing == 1)
        if parent_post_id is None:
            continue
        parent_nonnull += 1
        parent_key = (discussion_id, parent_post_id)
        parent_record = posts.get(parent_key)
        if parent_record is None:
            continue
        parent_resolved += 1
        if parent_missing == 0:
            parent_resolved_flag_clean += 1
        parent_quality = texts.get(parent_record[0])
        if (
            parent_missing == 0
            and target_quality is not None
            and parent_quality is not None
            and target_quality[4]
            and parent_quality[4]
        ):
            usable_parent_pairs += 1

    quote_pairs_resolved = 0
    usable_quote_pairs = 0
    for target_key, source_key in quote_pairs:
        target = posts.get(target_key)
        source = posts.get(source_key)
        if target is None or source is None:
            continue
        quote_pairs_resolved += 1
        target_quality = texts.get(target[0])
        source_quality = texts.get(source[0])
        if (
            target_quality is not None
            and source_quality is not None
            and target_quality[4]
            and source_quality[4]
        ):
            usable_quote_pairs += 1

    p123_linked_entries = 0
    for triple_id, context_index, response_index in p123_entries.values():
        if (
            (triple_id, context_index) in p123_posts
            and (triple_id, response_index) in p123_posts
        ):
            p123_linked_entries += 1

    discussion_sizes = list(discussion_post_counts.values())
    metadata_fields.sort(key=str.casefold)
    linked_topics = sorted(
        (
            {
                "topic_id": topic_id,
                "label": topic_labels.get(topic_id, "UNKNOWN_TOPIC_ID"),
                "discussions": count,
            }
            for topic_id, count in linked_topic_ids.items()
        ),
        key=lambda item: str(item["label"]).casefold(),
    )
    created_min = min(creation_dates) if creation_dates else None
    created_max = max(creation_dates) if creation_dates else None

    return {
        "artifact": {
            "path_basename": path.name,
            "compressed_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        },
        "table_rows": dict(sorted(table_rows.items())),
        "metadata": {
            "fields": metadata_fields,
            "selected_values": selected_metadata,
            "license_related_entries": license_metadata,
        },
        "scope": {
            "linked_topics": linked_topics,
            "discussions_with_topic_link": sum(linked_topic_ids.values()),
            "topic_link_coverage": (
                sum(linked_topic_ids.values()) / table_rows["discussion"]
                if table_rows["discussion"]
                else None
            ),
            "topic_ontology_size": len(topic_labels),
            "creation_date_min": created_min,
            "creation_date_max": created_max,
        },
        "threads": {
            "discussions": table_rows["discussion"],
            "posts": table_rows["post"],
            "authors": table_rows["author"],
            "discussion_size_posts": {
                "median": quantile(discussion_sizes, 0.5),
                "p90": quantile(discussion_sizes, 0.9),
                "p95": quantile(discussion_sizes, 0.95),
                "max": max(discussion_sizes) if discussion_sizes else None,
            },
        },
        "post_text": {
            "missing_text_row": post_text_missing,
            "nonempty": post_text_nonempty,
            "placeholder": post_text_placeholder,
            "html_like": post_text_html_like,
            "passes_minimal_gate": post_text_minimal_gate,
            "minimal_gate_definition": "at least 20 stripped characters and 5 ASCII word tokens; not a deletion placeholder",
        },
        "parent_links": {
            "parent_id_nonnull": parent_nonnull,
            "parent_missing_flag": parent_missing_flag,
            "resolved_in_same_discussion": parent_resolved,
            "resolved_and_parent_missing_zero": parent_resolved_flag_clean,
            "usable_text_pairs": usable_parent_pairs,
        },
        "quote_links": {
            "quote_rows": quote_rows,
            "source_post_id_nonnull": quote_source_rows,
            "source_offsets_nonnull": quote_source_with_offsets,
            "same_discussion": quote_same_discussion,
            "unique_response_source_pairs": len(quote_pairs),
            "resolved_unique_pairs": quote_pairs_resolved,
            "usable_text_pairs": usable_quote_pairs,
        },
        "argument_relations": {
            "response_type_counts": dict(sorted(response_types.items())),
            "is_rebuttal_counts": dict(sorted(rebuttal_values.items())),
        },
        "fourforums_annotations": {
            "qr_entries_linked_to_post_quote": len(qr_entries),
            "qr_task1_average_rows": len(qr_task1_keys),
            "qr_entries_with_task1_average": len(qr_task1_keys & qr_entries.keys()),
            "qr_task1_num_annotations": summarize_numeric(qr_task1_num_annots),
            "qr_task1_emotion_fact": summarize_numeric(qr_task1_emotion_fact),
            "qr_task1_attacking_respectful": summarize_numeric(
                qr_task1_attacking_respectful
            ),
            "qr_task1_nasty_nice": summarize_numeric(qr_task1_nasty_nice),
            "qr_task1_sarcasm_yes": summarize_numeric(qr_task1_sarcasm_yes),
            "p123_entries": len(p123_entries),
            "p123_entries_with_resolved_context_response": p123_linked_entries,
            "p123_average_rows": len(p123_average_keys),
            "p123_entries_with_average": len(p123_average_keys & p123_entries.keys()),
        },
    }


def main() -> None:
    args = parse_args()
    paths = {
        "createdebate": args.createdebate,
        "convinceme": args.convinceme,
        "fourforums": args.fourforums,
    }
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)

    result = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "privacy": "Aggregate audit only. No forum text, usernames, or source URLs are emitted.",
        "source_release": {
            "official_page": "https://nlds.engineering.ucsc.edu/iac2/",
            "official_drive_folder": "https://drive.google.com/drive/folders/11UMZbpLaLOkxT53vVWUHVJkdyWL1H7Gx",
            "release_dump_date": "2016-05-18",
            "variant": "no_parse",
        },
        "corpora": {
            name: audit_corpus(path, name) for name, path in paths.items()
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
