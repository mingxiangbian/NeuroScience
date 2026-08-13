#!/usr/bin/env python3
"""Build a private, auditable IAC 2.0 parent-target candidate database."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import html
import json
import math
import os
import re
import secrets
import sqlite3
import sys
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Iterator, Sequence


FORUM_CONTEXT_DIR = Path(__file__).resolve().parents[1]
if str(FORUM_CONTEXT_DIR) not in sys.path:
    sys.path.insert(0, str(FORUM_CONTEXT_DIR))

from audit_iac2_source import iter_insert_rows  # noqa: E402


SCHEMA_VERSION = "2"
PIPELINE_ID = "DATA-FCTX-CLEAN-V2"
WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*")
HTML_TAG_RE = re.compile(r"</?[A-Za-z][^>]{0,200}>")
HTML_BLOCKQUOTE_RE = re.compile(r"<\s*blockquote\b", re.IGNORECASE)
EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\[\]]+")
IP_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
MENTION_RE = re.compile(r"(?<![\w@])@[A-Za-z0-9_]{1,32}\b")
REPEATED_CHARACTER_RE = re.compile(r"([^\s])\1{5,}", re.IGNORECASE)
SIGNATURE_RE = re.compile(r"(?:^|\n)\s*(?:--+|__+)\s*(?:\n|$)")
MARKER_RE = re.compile(r"\[\[(?:/?QUOTE|URL|EMAIL|IP|MENTION)\]\]")
QUOTE_MARKER_RE = re.compile(r"\[\[QUOTE\]\]")
PLACEHOLDERS = {
    "[deleted]",
    "[removed]",
    "deleted",
    "removed",
    "n/a",
    "none",
}
BLOCK_TAGS = {
    "address",
    "blockquote",
    "br",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "p",
    "pre",
    "table",
    "tr",
}


class VisibleTextParser(HTMLParser):
    """Extract visible text while retaining coarse block boundaries."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del attrs
        lowered = tag.casefold()
        if lowered in {"script", "style"}:
            self.hidden_depth += 1
            return
        if not self.hidden_depth and lowered in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered in {"script", "style"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)
            return
        if not self.hidden_depth and lowered in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


@dataclass(frozen=True)
class QuoteRecord:
    quote_index: int
    parent_quote_index: int | None
    text_offset: int | None
    quote_raw_bytes: bytes | None
    truncated: int | None = None
    altered: int | None = None


@dataclass(frozen=True)
class QuoteViews:
    model_full_source: str
    model_body_source: str
    offset_status_counts: Counter[str]
    text_status_counts: Counter[str]
    quote_text_char_count: int
    inserted_top_level_count: int
    inserted_nested_count: int


@dataclass(frozen=True)
class PostResult:
    model_full: str | None
    model_body: str | None
    dedup_body: str | None
    body_sha256: str | None
    raw_char_count: int
    body_char_count: int
    word_count: int
    quote_char_count: int
    quote_ratio: float
    hard_reason: str | None
    soft_flags: tuple[str, ...]
    quote_offset_status_counts: Counter[str]
    quote_text_status_counts: Counter[str]
    inserted_top_level_quotes: int
    inserted_nested_quotes: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-db", type=Path, required=True)
    parser.add_argument("--id-key", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def decode_bytes(value: bytes | None) -> tuple[str, bool]:
    if value is None:
        return "", False
    decoded = value.decode("utf-8", errors="replace")
    return decoded, "\ufffd" in decoded


def as_int(value: bytes | None) -> int | None:
    return None if value is None else int(value)


def strip_html(value: str) -> str:
    if not HTML_TAG_RE.search(value):
        return html.unescape(value)
    parser = VisibleTextParser()
    try:
        parser.feed(value)
        parser.close()
        return parser.text()
    except Exception:
        return html.unescape(value)


def _replace_ip(match: re.Match[str]) -> str:
    parts = match.group(0).split(".")
    if all(0 <= int(part) <= 255 for part in parts):
        return "[[IP]]"
    return match.group(0)


def normalize_model_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    value = strip_html(value)
    value = "".join(
        character
        if character in "\n\t" or unicodedata.category(character) != "Cc"
        else " "
        for character in value
    )
    value = EMAIL_RE.sub("[[EMAIL]]", value)
    value = URL_RE.sub("[[URL]]", value)
    value = IP_RE.sub(_replace_ip, value)
    value = MENTION_RE.sub("[[MENTION]]", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t\f\v]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def normalize_dedup_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", value).strip()


def make_uid(key: bytes, kind: str, *parts: int) -> str:
    payload = ":".join([kind, *(str(part) for part in parts)]).encode("ascii")
    digest = hmac.new(key, payload, hashlib.sha256).hexdigest()
    prefixes = {"thread": "thr", "post": "pst", "sample": "smp"}
    return f"{prefixes[kind]}_{digest}"


def derive_quote_views(raw_text: str, quotes: Sequence[QuoteRecord]) -> QuoteViews:
    nodes = {quote.quote_index: quote for quote in quotes}
    decoded: dict[int, str] = {}
    text_status_counts: Counter[str] = Counter()
    for quote in quotes:
        if quote.quote_raw_bytes is None:
            decoded[quote.quote_index] = ""
            text_status_counts["missing"] += 1
            continue
        quote_text, had_replacement = decode_bytes(quote.quote_raw_bytes)
        decoded[quote.quote_index] = quote_text
        text_status_counts["empty" if not quote_text else "present"] += 1
        if had_replacement:
            text_status_counts["decode_replacement"] += 1

    cycle_indices: set[int] = set()
    for quote_index in nodes:
        path: list[int] = []
        positions: dict[int, int] = {}
        current: int | None = quote_index
        while current is not None and current in nodes:
            if current in positions:
                cycle_indices.update(path[positions[current] :])
                break
            positions[current] = len(path)
            path.append(current)
            current = nodes[current].parent_quote_index

    offset_status: dict[int, str] = {}
    offset_status_counts: Counter[str] = Counter()
    for quote in quotes:
        if quote.quote_index in cycle_indices:
            status = "cycle"
        elif quote.text_offset is None:
            status = "missing_offset"
        elif quote.parent_quote_index is None:
            status = (
                "valid_top_level"
                if 0 <= quote.text_offset <= len(raw_text)
                else "out_of_bounds"
            )
        elif quote.parent_quote_index not in nodes:
            status = "missing_parent"
        else:
            parent_text = decoded[quote.parent_quote_index]
            status = (
                "valid_nested"
                if 0 <= quote.text_offset <= len(parent_text)
                else "out_of_bounds"
            )
        offset_status[quote.quote_index] = status
        offset_status_counts[status] += 1

    children: dict[int, list[QuoteRecord]] = {}
    top_level: list[QuoteRecord] = []
    for quote in quotes:
        status = offset_status[quote.quote_index]
        if status == "valid_top_level":
            top_level.append(quote)
        elif status == "valid_nested" and quote.parent_quote_index is not None:
            children.setdefault(quote.parent_quote_index, []).append(quote)

    rendered_cache: dict[int, tuple[str, int, int]] = {}

    def render_quote(quote_index: int, stack: frozenset[int]) -> tuple[str, int, int]:
        if quote_index in rendered_cache:
            return rendered_cache[quote_index]
        if quote_index in stack:
            return decoded[quote_index], len(decoded[quote_index]), 0

        base = decoded[quote_index]
        nested_count = 0
        quote_char_count = len(base)
        parts: list[str] = []
        cursor = 0
        for child in sorted(
            children.get(quote_index, []),
            key=lambda item: (item.text_offset if item.text_offset is not None else -1, item.quote_index),
        ):
            offset = child.text_offset
            if offset is None:
                continue
            child_text, child_chars, child_nested = render_quote(
                child.quote_index, stack | {quote_index}
            )
            parts.append(base[cursor:offset])
            parts.extend(("\n[[QUOTE]]\n", child_text, "\n[[/QUOTE]]\n"))
            cursor = offset
            nested_count += 1 + child_nested
            quote_char_count += child_chars
        parts.append(base[cursor:])
        result = ("".join(parts), quote_char_count, nested_count)
        rendered_cache[quote_index] = result
        return result

    full_parts: list[str] = []
    body_parts: list[str] = []
    cursor = 0
    quote_text_char_count = 0
    inserted_nested_count = 0
    for quote in sorted(
        top_level,
        key=lambda item: (item.text_offset if item.text_offset is not None else -1, item.quote_index),
    ):
        offset = quote.text_offset
        if offset is None:
            continue
        quote_text, quote_chars, nested_count = render_quote(quote.quote_index, frozenset())
        prefix = raw_text[cursor:offset]
        full_parts.extend((prefix, "\n[[QUOTE]]\n", quote_text, "\n[[/QUOTE]]\n"))
        body_parts.extend((prefix, "\n[[QUOTE]]\n"))
        cursor = offset
        quote_text_char_count += quote_chars
        inserted_nested_count += nested_count
    full_parts.append(raw_text[cursor:])
    body_parts.append(raw_text[cursor:])

    return QuoteViews(
        model_full_source="".join(full_parts),
        model_body_source="".join(body_parts),
        offset_status_counts=offset_status_counts,
        text_status_counts=text_status_counts,
        quote_text_char_count=quote_text_char_count,
        inserted_top_level_count=len(top_level),
        inserted_nested_count=inserted_nested_count,
    )


def _url_only(value: str) -> bool:
    if "[[URL]]" not in value:
        return False
    without_markers = MARKER_RE.sub("", value)
    return not any(character.isalnum() for character in without_markers)


def _low_latin_ratio(value: str) -> bool:
    letters = [character for character in value if character.isalpha()]
    if len(letters) < 20:
        return False
    latin = sum("LATIN" in unicodedata.name(character, "") for character in letters)
    return latin / len(letters) < 0.5


def _all_caps(value: str) -> bool:
    cased = [character for character in value if character.isalpha() and character.isascii()]
    if len(cased) < 10:
        return False
    return sum(character.isupper() for character in cased) / len(cased) >= 0.8


def evaluate_post(
    raw_bytes: bytes | None,
    quotes: Sequence[QuoteRecord],
) -> PostResult:
    if raw_bytes is None:
        return PostResult(
            model_full=None,
            model_body=None,
            dedup_body=None,
            body_sha256=None,
            raw_char_count=0,
            body_char_count=0,
            word_count=0,
            quote_char_count=0,
            quote_ratio=0.0,
            hard_reason="missing_text",
            soft_flags=(),
            quote_offset_status_counts=Counter(),
            quote_text_status_counts=Counter(),
            inserted_top_level_quotes=0,
            inserted_nested_quotes=0,
        )

    raw_text, had_replacement = decode_bytes(raw_bytes)
    quote_views = derive_quote_views(raw_text, quotes)
    model_full = normalize_model_text(quote_views.model_full_source)
    model_body = normalize_model_text(quote_views.model_body_source)
    dedup_body = normalize_dedup_text(model_body)
    word_count = len(WORD_RE.findall(model_body))
    raw_chars = len(raw_text.strip())
    quote_ratio = quote_views.quote_text_char_count / max(
        raw_chars + quote_views.quote_text_char_count, 1
    )

    hard_reason: str | None = None
    if not model_body:
        hard_reason = "empty"
    elif dedup_body in PLACEHOLDERS:
        hard_reason = "placeholder"
    elif "[[QUOTE]]" in model_body and not QUOTE_MARKER_RE.sub("", model_body).strip():
        hard_reason = "quote_only"

    flags: set[str] = set()
    if word_count < 3:
        flags.add("short")
    if word_count > 512:
        flags.add("long")
    if quote_views.quote_text_char_count and quote_ratio >= 0.5:
        flags.add("quote_heavy")
    if _url_only(model_body):
        flags.add("url_only")
    if HTML_TAG_RE.search(raw_text):
        flags.add("html_present")
    if had_replacement:
        flags.add("decode_replacement")
    if _low_latin_ratio(model_body):
        flags.add("low_latin_ratio")
    if _all_caps(model_body):
        flags.add("all_caps")
    if REPEATED_CHARACTER_RE.search(model_body):
        flags.add("repeated_character")
    if SIGNATURE_RE.search(raw_text):
        flags.add("possible_signature")
    if word_count == 0:
        flags.add("no_lexical_tokens")
    valid_offsets = (
        quote_views.offset_status_counts["valid_top_level"]
        + quote_views.offset_status_counts["valid_nested"]
    )
    if sum(quote_views.offset_status_counts.values()) > valid_offsets:
        flags.add("quote_structure_unverified")
    if quote_views.text_status_counts["missing"]:
        flags.add("quote_text_missing")
    if quote_views.text_status_counts["decode_replacement"]:
        flags.add("quote_decode_replacement")
    if HTML_BLOCKQUOTE_RE.search(raw_text) and not quote_views.inserted_top_level_count:
        flags.add("html_quote_unstructured")

    return PostResult(
        model_full=model_full,
        model_body=model_body,
        dedup_body=dedup_body,
        body_sha256=sha256_text(dedup_body),
        raw_char_count=len(raw_text),
        body_char_count=len(model_body),
        word_count=word_count,
        quote_char_count=quote_views.quote_text_char_count,
        quote_ratio=quote_ratio,
        hard_reason=hard_reason,
        soft_flags=tuple(sorted(flags)),
        quote_offset_status_counts=quote_views.offset_status_counts,
        quote_text_status_counts=quote_views.text_status_counts,
        inserted_top_level_quotes=quote_views.inserted_top_level_count,
        inserted_nested_quotes=quote_views.inserted_nested_count,
    )


def ensure_private_key(path: Path) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        key = path.read_bytes()
        if len(key) != 32:
            raise ValueError(f"existing ID key must contain exactly 32 bytes: {path}")
        if path.stat().st_mode & 0o077:
            raise PermissionError(f"existing ID key permissions are broader than 0600: {path}")
        return key

    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        key = secrets.token_bytes(32)
        os.write(descriptor, key)
    finally:
        os.close(descriptor)
    return key


def initialize_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute("PRAGMA temp_store=FILE")
    connection.execute("PRAGMA cache_size=-200000")
    connection.executescript(
        """
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE discussions (
            source_discussion_id INTEGER PRIMARY KEY,
            thread_uid TEXT NOT NULL UNIQUE,
            title_raw BLOB,
            title_model TEXT NOT NULL,
            title_dedup TEXT NOT NULL
        );

        CREATE TABLE source_posts (
            source_discussion_id INTEGER NOT NULL,
            source_post_id INTEGER NOT NULL,
            post_uid TEXT NOT NULL UNIQUE,
            creation_date TEXT,
            parent_post_id INTEGER,
            parent_missing INTEGER NOT NULL,
            text_id INTEGER NOT NULL,
            PRIMARY KEY (source_discussion_id, source_post_id)
        );

        CREATE TABLE source_quotes (
            quote_row_id INTEGER PRIMARY KEY,
            source_discussion_id INTEGER NOT NULL,
            source_post_id INTEGER NOT NULL,
            quote_index INTEGER,
            parent_quote_index INTEGER,
            text_offset INTEGER,
            text_id INTEGER,
            quote_source_discussion_id INTEGER,
            quote_source_post_id INTEGER,
            source_start INTEGER,
            source_end INTEGER,
            truncated INTEGER,
            altered INTEGER
        );

        CREATE TABLE post_texts (
            text_id INTEGER PRIMARY KEY,
            raw_bytes BLOB NOT NULL,
            decoded_sha256 TEXT NOT NULL,
            had_decode_replacement INTEGER NOT NULL
        );

        CREATE TABLE quote_texts (
            text_id INTEGER PRIMARY KEY,
            raw_bytes BLOB NOT NULL,
            decoded_sha256 TEXT NOT NULL,
            had_decode_replacement INTEGER NOT NULL
        );

        CREATE TABLE cleaned_posts (
            source_discussion_id INTEGER NOT NULL,
            source_post_id INTEGER NOT NULL,
            post_uid TEXT NOT NULL UNIQUE,
            model_full TEXT,
            model_body TEXT,
            dedup_body TEXT,
            body_sha256 TEXT,
            raw_char_count INTEGER NOT NULL,
            body_char_count INTEGER NOT NULL,
            word_count INTEGER NOT NULL,
            quote_char_count INTEGER NOT NULL,
            quote_ratio REAL NOT NULL,
            hard_reason TEXT,
            soft_flags_json TEXT NOT NULL,
            PRIMARY KEY (source_discussion_id, source_post_id)
        );

        CREATE TABLE post_soft_flags (
            source_discussion_id INTEGER NOT NULL,
            source_post_id INTEGER NOT NULL,
            flag TEXT NOT NULL,
            PRIMARY KEY (source_discussion_id, source_post_id, flag)
        );

        CREATE TABLE quote_reconstruction_stats (
            source_discussion_id INTEGER NOT NULL,
            source_post_id INTEGER NOT NULL,
            valid_top_level_count INTEGER NOT NULL,
            valid_nested_count INTEGER NOT NULL,
            missing_offset_count INTEGER NOT NULL,
            missing_parent_count INTEGER NOT NULL,
            out_of_bounds_count INTEGER NOT NULL,
            cycle_count INTEGER NOT NULL,
            quote_text_present_count INTEGER NOT NULL,
            quote_text_empty_count INTEGER NOT NULL,
            quote_text_missing_count INTEGER NOT NULL,
            quote_decode_replacement_count INTEGER NOT NULL,
            quote_text_char_count INTEGER NOT NULL,
            inserted_top_level_count INTEGER NOT NULL,
            inserted_nested_count INTEGER NOT NULL,
            PRIMARY KEY (source_discussion_id, source_post_id)
        );

        CREATE TABLE candidate_pairs (
            sample_uid TEXT PRIMARY KEY,
            thread_uid TEXT NOT NULL,
            source_discussion_id INTEGER NOT NULL,
            target_source_post_id INTEGER NOT NULL,
            parent_source_post_id INTEGER NOT NULL,
            target_post_uid TEXT NOT NULL,
            parent_post_uid TEXT,
            eligible INTEGER NOT NULL,
            hard_reasons_json TEXT NOT NULL,
            soft_flags_json TEXT NOT NULL,
            target_body_sha256 TEXT,
            parent_body_sha256 TEXT,
            pair_sha256 TEXT,
            target_duplicate_count INTEGER NOT NULL DEFAULT 0,
            pair_duplicate_count INTEGER NOT NULL DEFAULT 0,
            target_context_count INTEGER NOT NULL DEFAULT 0,
            context_variant INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE candidate_hard_reasons (
            sample_uid TEXT NOT NULL,
            reason TEXT NOT NULL,
            PRIMARY KEY (sample_uid, reason)
        );

        CREATE TABLE candidate_soft_flags (
            sample_uid TEXT NOT NULL,
            flag TEXT NOT NULL,
            PRIMARY KEY (sample_uid, flag)
        );

        CREATE TABLE exact_duplicate_clusters (
            cluster_kind TEXT NOT NULL,
            cluster_sha256 TEXT NOT NULL,
            member_count INTEGER NOT NULL,
            distinct_context_count INTEGER,
            PRIMARY KEY (cluster_kind, cluster_sha256)
        );
        """
    )
    return connection


def ingest_source(
    connection: sqlite3.Connection,
    source: Path,
    key: bytes,
) -> Counter[str]:
    wanted_tables = {"discussion", "post", "quote", "text"}
    counts: Counter[str] = Counter()
    post_text_ids: set[int] = set()
    quote_text_ids: set[int] = set()
    quote_row_id = 0

    connection.execute("BEGIN")
    for table, row in iter_insert_rows(source, wanted_tables):
        counts[table] += 1
        if table == "discussion":
            discussion_id = int(row[0])
            raw_title = row[2] or b""
            title, _ = decode_bytes(raw_title)
            model_title = normalize_model_text(title)
            connection.execute(
                "INSERT INTO discussions VALUES (?, ?, ?, ?, ?)",
                (
                    discussion_id,
                    make_uid(key, "thread", discussion_id),
                    sqlite3.Binary(raw_title),
                    model_title,
                    normalize_dedup_text(model_title),
                ),
            )
        elif table == "post":
            discussion_id = int(row[0])
            post_id = int(row[1])
            text_id = int(row[6])
            post_text_ids.add(text_id)
            connection.execute(
                "INSERT INTO source_posts VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    discussion_id,
                    post_id,
                    make_uid(key, "post", discussion_id, post_id),
                    decode_bytes(row[3])[0] or None,
                    as_int(row[4]),
                    int(row[5]),
                    text_id,
                ),
            )
        elif table == "quote":
            quote_row_id += 1
            text_id = as_int(row[5])
            if text_id is not None:
                quote_text_ids.add(text_id)
            connection.execute(
                "INSERT INTO source_quotes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    quote_row_id,
                    int(row[0]),
                    int(row[1]),
                    as_int(row[2]),
                    as_int(row[3]),
                    as_int(row[4]),
                    text_id,
                    as_int(row[6]),
                    as_int(row[7]),
                    as_int(row[8]),
                    as_int(row[9]),
                    as_int(row[10]),
                    as_int(row[11]),
                ),
            )
        elif table == "text":
            text_id = int(row[0])
            if text_id not in post_text_ids and text_id not in quote_text_ids:
                continue
            raw_bytes = row[1] or b""
            decoded, had_replacement = decode_bytes(raw_bytes)
            decoded_hash = sha256_text(decoded)
            if text_id in post_text_ids:
                connection.execute(
                    "INSERT INTO post_texts VALUES (?, ?, ?, ?)",
                    (
                        text_id,
                        sqlite3.Binary(raw_bytes),
                        decoded_hash,
                        int(had_replacement),
                    ),
                )
            if text_id in quote_text_ids:
                connection.execute(
                    "INSERT INTO quote_texts VALUES (?, ?, ?, ?)",
                    (
                        text_id,
                        sqlite3.Binary(raw_bytes),
                        decoded_hash,
                        int(had_replacement),
                    ),
                )

        total = sum(counts.values())
        if total and total % 250000 == 0:
            print(f"ingest rows: {total:,}", flush=True)

    connection.commit()

    expected_post_texts = connection.execute(
        "SELECT COUNT(DISTINCT text_id) FROM source_posts"
    ).fetchone()[0]
    stored_post_texts = connection.execute("SELECT COUNT(*) FROM post_texts").fetchone()[0]
    expected_quote_texts = connection.execute(
        "SELECT COUNT(DISTINCT text_id) FROM source_quotes WHERE text_id IS NOT NULL"
    ).fetchone()[0]
    stored_quote_texts = connection.execute(
        "SELECT COUNT(*) FROM quote_texts"
    ).fetchone()[0]
    if stored_post_texts != expected_post_texts:
        raise ValueError(
            f"post text coverage mismatch: expected {expected_post_texts}, got {stored_post_texts}"
        )
    if stored_quote_texts != expected_quote_texts:
        raise ValueError(
            f"quote text coverage mismatch: expected {expected_quote_texts}, got {stored_quote_texts}"
        )

    connection.executescript(
        """
        CREATE INDEX source_posts_parent_idx
            ON source_posts(source_discussion_id, parent_post_id);
        CREATE INDEX source_quotes_post_idx
            ON source_quotes(source_discussion_id, source_post_id, quote_index);
        """
    )
    return counts


def _quote_iterator(connection: sqlite3.Connection) -> Iterator[tuple[tuple[int, int], QuoteRecord]]:
    query = """
        SELECT q.source_discussion_id,
               q.source_post_id,
               q.quote_index,
               q.parent_quote_index,
               q.text_offset,
               t.raw_bytes,
               q.truncated,
               q.altered
        FROM source_quotes AS q
        LEFT JOIN quote_texts AS t ON t.text_id = q.text_id
        ORDER BY q.source_discussion_id, q.source_post_id, q.quote_index, q.quote_row_id
    """
    for row in connection.execute(query):
        quote_bytes = bytes(row[5]) if row[5] is not None else None
        yield (row[0], row[1]), QuoteRecord(
            quote_index=row[2],
            parent_quote_index=row[3],
            text_offset=row[4],
            quote_raw_bytes=quote_bytes,
            truncated=row[6],
            altered=row[7],
        )


def clean_posts(connection: sqlite3.Connection) -> None:
    quote_stream = _quote_iterator(connection)
    current_quote = next(quote_stream, None)
    cleaned_batch: list[tuple[object, ...]] = []
    flag_batch: list[tuple[int, int, str]] = []
    reconstruction_batch: list[tuple[int, ...]] = []
    processed = 0

    query = """
        SELECT p.source_discussion_id,
               p.source_post_id,
               p.post_uid,
               t.raw_bytes
        FROM source_posts AS p
        LEFT JOIN post_texts AS t ON t.text_id = p.text_id
        ORDER BY p.source_discussion_id, p.source_post_id
    """
    cursor = connection.execute(query)
    connection.execute("BEGIN")
    for discussion_id, post_id, post_uid, raw_bytes in cursor:
        key = (discussion_id, post_id)
        quotes: list[QuoteRecord] = []
        while current_quote is not None and current_quote[0] < key:
            current_quote = next(quote_stream, None)
        while current_quote is not None and current_quote[0] == key:
            quotes.append(current_quote[1])
            current_quote = next(quote_stream, None)

        material = bytes(raw_bytes) if raw_bytes is not None else None
        result = evaluate_post(material, quotes)
        cleaned_batch.append(
            (
                discussion_id,
                post_id,
                post_uid,
                result.model_full,
                result.model_body,
                result.dedup_body,
                result.body_sha256,
                result.raw_char_count,
                result.body_char_count,
                result.word_count,
                result.quote_char_count,
                result.quote_ratio,
                result.hard_reason,
                json.dumps(result.soft_flags, ensure_ascii=True),
            )
        )
        flag_batch.extend((discussion_id, post_id, flag) for flag in result.soft_flags)
        reconstruction_batch.append(
            (
                discussion_id,
                post_id,
                result.quote_offset_status_counts["valid_top_level"],
                result.quote_offset_status_counts["valid_nested"],
                result.quote_offset_status_counts["missing_offset"],
                result.quote_offset_status_counts["missing_parent"],
                result.quote_offset_status_counts["out_of_bounds"],
                result.quote_offset_status_counts["cycle"],
                result.quote_text_status_counts["present"],
                result.quote_text_status_counts["empty"],
                result.quote_text_status_counts["missing"],
                result.quote_text_status_counts["decode_replacement"],
                result.quote_char_count,
                result.inserted_top_level_quotes,
                result.inserted_nested_quotes,
            )
        )
        processed += 1

        if len(cleaned_batch) >= 2000:
            _flush_cleaned_batches(
                connection, cleaned_batch, flag_batch, reconstruction_batch
            )
            cleaned_batch.clear()
            flag_batch.clear()
            reconstruction_batch.clear()
        if processed % 50000 == 0:
            print(f"cleaned posts: {processed:,}", flush=True)

    _flush_cleaned_batches(connection, cleaned_batch, flag_batch, reconstruction_batch)
    connection.commit()


def _flush_cleaned_batches(
    connection: sqlite3.Connection,
    cleaned_batch: Sequence[tuple[object, ...]],
    flag_batch: Sequence[tuple[int, int, str]],
    reconstruction_batch: Sequence[tuple[int, ...]],
) -> None:
    if cleaned_batch:
        connection.executemany(
            "INSERT INTO cleaned_posts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            cleaned_batch,
        )
    if flag_batch:
        connection.executemany("INSERT INTO post_soft_flags VALUES (?, ?, ?)", flag_batch)
    if reconstruction_batch:
        connection.executemany(
            "INSERT INTO quote_reconstruction_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            reconstruction_batch,
        )


def build_candidates(connection: sqlite3.Connection, key: bytes) -> None:
    query = """
        SELECT t.source_discussion_id,
               t.source_post_id,
               t.post_uid,
               t.creation_date,
               t.parent_post_id,
               t.parent_missing,
               d.thread_uid,
               tc.hard_reason,
               tc.soft_flags_json,
               tc.body_sha256,
               p.source_post_id,
               p.post_uid,
               p.creation_date,
               pc.hard_reason,
               pc.soft_flags_json,
               pc.body_sha256
        FROM source_posts AS t
        JOIN discussions AS d
          ON d.source_discussion_id = t.source_discussion_id
        LEFT JOIN cleaned_posts AS tc
          ON tc.source_discussion_id = t.source_discussion_id
         AND tc.source_post_id = t.source_post_id
        LEFT JOIN source_posts AS p
          ON p.source_discussion_id = t.source_discussion_id
         AND p.source_post_id = t.parent_post_id
        LEFT JOIN cleaned_posts AS pc
          ON pc.source_discussion_id = p.source_discussion_id
         AND pc.source_post_id = p.source_post_id
        WHERE t.parent_post_id IS NOT NULL
        ORDER BY t.source_discussion_id, t.source_post_id
    """
    pair_batch: list[tuple[object, ...]] = []
    hard_batch: list[tuple[str, str]] = []
    soft_batch: list[tuple[str, str]] = []
    processed = 0

    connection.execute("BEGIN")
    for row in connection.execute(query):
        (
            discussion_id,
            target_id,
            target_uid,
            target_date,
            declared_parent_id,
            parent_missing,
            thread_uid,
            target_hard,
            target_soft_json,
            target_hash,
            resolved_parent_id,
            parent_uid,
            parent_date,
            parent_hard,
            parent_soft_json,
            parent_hash,
        ) = row

        hard_reasons: list[str] = []
        if target_hard:
            hard_reasons.append(f"target_{target_hard}")
        if parent_missing or resolved_parent_id is None:
            hard_reasons.append("parent_unresolved")
        elif parent_hard:
            hard_reasons.append(f"parent_{parent_hard}")

        soft_flags = {
            *(f"target_{flag}" for flag in json.loads(target_soft_json or "[]")),
        }
        if resolved_parent_id is not None:
            soft_flags.update(
                f"parent_{flag}" for flag in json.loads(parent_soft_json or "[]")
            )
        if target_date and parent_date and target_date < parent_date:
            soft_flags.add("timestamp_nonmonotonic")

        sample_uid = make_uid(
            key,
            "sample",
            discussion_id,
            target_id,
            declared_parent_id,
        )
        pair_hash = (
            sha256_text(f"{parent_hash}\0{target_hash}")
            if target_hash and parent_hash
            else None
        )
        hard_reasons = sorted(set(hard_reasons))
        soft_flags_sorted = sorted(soft_flags)
        pair_batch.append(
            (
                sample_uid,
                thread_uid,
                discussion_id,
                target_id,
                declared_parent_id,
                target_uid,
                parent_uid,
                int(not hard_reasons),
                json.dumps(hard_reasons, ensure_ascii=True),
                json.dumps(soft_flags_sorted, ensure_ascii=True),
                target_hash,
                parent_hash,
                pair_hash,
                0,
                0,
                0,
                0,
            )
        )
        hard_batch.extend((sample_uid, reason) for reason in hard_reasons)
        soft_batch.extend((sample_uid, flag) for flag in soft_flags_sorted)
        processed += 1

        if len(pair_batch) >= 2000:
            _flush_candidate_batches(connection, pair_batch, hard_batch, soft_batch)
            pair_batch.clear()
            hard_batch.clear()
            soft_batch.clear()
        if processed % 50000 == 0:
            print(f"candidate pairs: {processed:,}", flush=True)

    _flush_candidate_batches(connection, pair_batch, hard_batch, soft_batch)
    connection.commit()
    connection.executescript(
        """
        CREATE INDEX candidate_target_hash_idx
            ON candidate_pairs(target_body_sha256) WHERE eligible = 1;
        CREATE INDEX candidate_pair_hash_idx
            ON candidate_pairs(pair_sha256) WHERE eligible = 1;
        CREATE INDEX candidate_eligible_idx ON candidate_pairs(eligible);

        CREATE TEMP TABLE target_aggregate AS
        SELECT target_body_sha256 AS cluster_sha256,
               COUNT(*) AS member_count,
               COUNT(DISTINCT parent_body_sha256) AS distinct_context_count
        FROM candidate_pairs
        WHERE eligible = 1 AND target_body_sha256 IS NOT NULL
        GROUP BY target_body_sha256;
        CREATE UNIQUE INDEX target_aggregate_idx
            ON target_aggregate(cluster_sha256);

        CREATE TEMP TABLE pair_aggregate AS
        SELECT pair_sha256 AS cluster_sha256,
               COUNT(*) AS member_count
        FROM candidate_pairs
        WHERE eligible = 1 AND pair_sha256 IS NOT NULL
        GROUP BY pair_sha256;
        CREATE UNIQUE INDEX pair_aggregate_idx
            ON pair_aggregate(cluster_sha256);

        UPDATE candidate_pairs
        SET target_duplicate_count = COALESCE((
                SELECT member_count FROM target_aggregate
                WHERE cluster_sha256 = candidate_pairs.target_body_sha256
            ), 0),
            target_context_count = COALESCE((
                SELECT distinct_context_count FROM target_aggregate
                WHERE cluster_sha256 = candidate_pairs.target_body_sha256
            ), 0),
            pair_duplicate_count = COALESCE((
                SELECT member_count FROM pair_aggregate
                WHERE cluster_sha256 = candidate_pairs.pair_sha256
            ), 0)
        WHERE eligible = 1;

        UPDATE candidate_pairs
        SET context_variant = CASE WHEN target_context_count > 1 THEN 1 ELSE 0 END
        WHERE eligible = 1;

        INSERT INTO exact_duplicate_clusters
        SELECT 'target', cluster_sha256, member_count, distinct_context_count
        FROM target_aggregate
        WHERE member_count > 1;

        INSERT INTO exact_duplicate_clusters
        SELECT 'pair', cluster_sha256, member_count, NULL
        FROM pair_aggregate
        WHERE member_count > 1;
        """
    )


def _flush_candidate_batches(
    connection: sqlite3.Connection,
    pair_batch: Sequence[tuple[object, ...]],
    hard_batch: Sequence[tuple[str, str]],
    soft_batch: Sequence[tuple[str, str]],
) -> None:
    if pair_batch:
        connection.executemany(
            "INSERT INTO candidate_pairs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            pair_batch,
        )
    if hard_batch:
        connection.executemany(
            "INSERT INTO candidate_hard_reasons VALUES (?, ?)", hard_batch
        )
    if soft_batch:
        connection.executemany(
            "INSERT INTO candidate_soft_flags VALUES (?, ?)", soft_batch
        )


def nearest_rank_quantiles(values: Iterable[int]) -> dict[str, int | None]:
    ordered = sorted(values)
    if not ordered:
        return {key: None for key in ("min", "p25", "p50", "p75", "p95", "p99", "max")}

    def at(probability: float) -> int:
        index = max(0, math.ceil(probability * len(ordered)) - 1)
        return ordered[min(index, len(ordered) - 1)]

    return {
        "min": ordered[0],
        "p25": at(0.25),
        "p50": at(0.50),
        "p75": at(0.75),
        "p95": at(0.95),
        "p99": at(0.99),
        "max": ordered[-1],
    }


def count_map(connection: sqlite3.Connection, query: str) -> dict[str, int]:
    return {str(key): int(value) for key, value in connection.execute(query)}


def duplicate_summary(connection: sqlite3.Connection, kind: str) -> dict[str, int]:
    row = connection.execute(
        """
        SELECT COUNT(*),
               COALESCE(SUM(member_count), 0),
               COALESCE(MAX(member_count), 1)
        FROM exact_duplicate_clusters
        WHERE cluster_kind = ?
        """,
        (kind,),
    ).fetchone()
    return {
        "clusters_with_multiple_rows": int(row[0]),
        "rows_in_duplicate_clusters": int(row[1]),
        "max_cluster_size": int(row[2]),
    }


def build_aggregate_report(
    connection: sqlite3.Connection,
    source: Path,
    source_sha256: str,
    source_rows: Counter[str],
    script_sha256: str,
    protocol_sha256: str,
    private_db: Path,
    private_db_sha256: str,
    elapsed_seconds: float,
) -> dict[str, object]:
    total_posts = connection.execute("SELECT COUNT(*) FROM source_posts").fetchone()[0]
    root_posts = connection.execute(
        "SELECT COUNT(*) FROM source_posts WHERE parent_post_id IS NULL"
    ).fetchone()[0]
    candidates = connection.execute("SELECT COUNT(*) FROM candidate_pairs").fetchone()[0]
    eligible = connection.execute(
        "SELECT COUNT(*) FROM candidate_pairs WHERE eligible = 1"
    ).fetchone()[0]
    posts_with_quotes = connection.execute(
        """
        SELECT COUNT(*) FROM quote_reconstruction_stats
        WHERE valid_top_level_count + valid_nested_count + missing_offset_count
            + missing_parent_count + out_of_bounds_count + cycle_count > 0
        """
    ).fetchone()[0]
    quote_offset_row = connection.execute(
        """
        SELECT COALESCE(SUM(valid_top_level_count), 0),
               COALESCE(SUM(valid_nested_count), 0),
               COALESCE(SUM(missing_offset_count), 0),
               COALESCE(SUM(missing_parent_count), 0),
               COALESCE(SUM(out_of_bounds_count), 0),
               COALESCE(SUM(cycle_count), 0)
        FROM quote_reconstruction_stats
        """
    ).fetchone()
    quote_text_row = connection.execute(
        """
        SELECT COALESCE(SUM(quote_text_present_count), 0),
               COALESCE(SUM(quote_text_empty_count), 0),
               COALESCE(SUM(quote_text_missing_count), 0),
               COALESCE(SUM(quote_decode_replacement_count), 0),
               COALESCE(SUM(quote_text_char_count), 0),
               COALESCE(SUM(inserted_top_level_count), 0),
               COALESCE(SUM(inserted_nested_count), 0)
        FROM quote_reconstruction_stats
        """
    ).fetchone()
    quote_source_flags = connection.execute(
        """
        SELECT SUM(CASE WHEN truncated = 1 THEN 1 ELSE 0 END),
               SUM(CASE WHEN altered = 1 THEN 1 ELSE 0 END),
               SUM(CASE WHEN quote_source_discussion_id IS NULL
                          OR quote_source_post_id IS NULL THEN 1 ELSE 0 END)
        FROM source_quotes
        """
    ).fetchone()
    target_lengths = (
        row[0]
        for row in connection.execute(
            """
            SELECT c.word_count
            FROM candidate_pairs AS p
            JOIN cleaned_posts AS c
              ON c.source_discussion_id = p.source_discussion_id
             AND c.source_post_id = p.target_source_post_id
            WHERE p.eligible = 1
            """
        )
    )
    parent_lengths = (
        row[0]
        for row in connection.execute(
            """
            SELECT c.word_count
            FROM candidate_pairs AS p
            JOIN cleaned_posts AS c
              ON c.source_discussion_id = p.source_discussion_id
             AND c.source_post_id = p.parent_source_post_id
            WHERE p.eligible = 1
            """
        )
    )
    context_variants = connection.execute(
        "SELECT COUNT(*) FROM candidate_pairs WHERE eligible = 1 AND context_variant = 1"
    ).fetchone()[0]
    distinct_context_variant_targets = connection.execute(
        """
        SELECT COUNT(DISTINCT target_body_sha256)
        FROM candidate_pairs
        WHERE eligible = 1 AND context_variant = 1
        """
    ).fetchone()[0]

    return {
        "schema_version": SCHEMA_VERSION,
        "pipeline_id": PIPELINE_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed_pending_independent_verification",
        "scope": {
            "dataset": "Internet Argument Corpus 2.0",
            "subset": "4forums",
            "candidate_unit": "direct parent-target reply pair",
            "labels_assigned": False,
            "splits_assigned": False,
            "external_services_used": False,
        },
        "source_artifact": {
            "filename": source.name,
            "size_bytes": source.stat().st_size,
            "sha256": source_sha256,
        },
        "implementation": {
            "script_sha256": script_sha256,
            "protocol_sha256": protocol_sha256,
            "elapsed_seconds": round(elapsed_seconds, 3),
        },
        "private_artifact": {
            "filename": private_db.name,
            "size_bytes": private_db.stat().st_size,
            "sha256": private_db_sha256,
            "git_tracking": "forbidden",
        },
        "counts": {
            "source_table_rows": dict(sorted(source_rows.items())),
            "discussions": connection.execute("SELECT COUNT(*) FROM discussions").fetchone()[0],
            "posts": total_posts,
            "root_posts_not_candidates": root_posts,
            "declared_parent_candidates": candidates,
            "eligible_candidates": eligible,
            "excluded_candidates": candidates - eligible,
            "hard_reason_occurrences": count_map(
                connection,
                "SELECT reason, COUNT(*) FROM candidate_hard_reasons GROUP BY reason ORDER BY reason",
            ),
            "soft_flag_occurrences": count_map(
                connection,
                "SELECT flag, COUNT(*) FROM candidate_soft_flags GROUP BY flag ORDER BY flag",
            ),
        },
        "quote_reconstruction": {
            "posts_with_quote_metadata": posts_with_quotes,
            "offset_status_occurrences": {
                "valid_top_level": int(quote_offset_row[0]),
                "valid_nested": int(quote_offset_row[1]),
                "missing_offset": int(quote_offset_row[2]),
                "missing_parent": int(quote_offset_row[3]),
                "out_of_bounds": int(quote_offset_row[4]),
                "cycle": int(quote_offset_row[5]),
            },
            "text_status_occurrences": {
                "present": int(quote_text_row[0]),
                "empty": int(quote_text_row[1]),
                "missing": int(quote_text_row[2]),
                "decode_replacement": int(quote_text_row[3]),
            },
            "inserted": {
                "top_level": int(quote_text_row[5]),
                "nested": int(quote_text_row[6]),
                "quote_text_characters": int(quote_text_row[4]),
            },
            "source_attributes": {
                "truncated": int(quote_source_flags[0]),
                "altered": int(quote_source_flags[1]),
                "source_unresolved": int(quote_source_flags[2]),
            },
        },
        "eligible_word_count_nearest_rank": {
            "target": nearest_rank_quantiles(target_lengths),
            "parent": nearest_rank_quantiles(parent_lengths),
        },
        "exact_duplication": {
            "target": duplicate_summary(connection, "target"),
            "pair": duplicate_summary(connection, "pair"),
            "context_variant_rows": int(context_variants),
            "distinct_context_variant_targets": int(distinct_context_variant_targets),
            "action": "retained_for_later_thread-aware_sampling",
        },
        "thresholds": {
            "short_word_tokens_lt": 3,
            "long_word_tokens_gt": 512,
            "quote_heavy_ratio_gte": 0.5,
            "low_latin_min_letters": 20,
            "low_latin_ratio_lt": 0.5,
            "all_caps_min_ascii_letters": 10,
            "all_caps_ratio_gte": 0.8,
            "repeated_character_run_gte": 6,
        },
        "privacy": {
            "author_table_read": False,
            "discussion_urls_retained": False,
            "public_text_or_titles": False,
            "public_source_ids": False,
            "public_per_sample_ids": False,
            "id_scheme": "private-key HMAC-SHA256",
        },
    }


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def prepare_dataset(args: argparse.Namespace) -> dict[str, object]:
    for path in (args.source, args.protocol):
        if not path.is_file():
            raise FileNotFoundError(path)
    for path in (args.output_db, args.report, args.manifest):
        if path.exists() and not args.replace:
            raise FileExistsError(f"refusing to overwrite without --replace: {path}")

    args.output_db.parent.mkdir(parents=True, exist_ok=True)
    temporary_db = args.output_db.with_name(f".{args.output_db.name}.tmp")
    if temporary_db.exists():
        if not args.replace:
            raise FileExistsError(f"stale temporary database exists: {temporary_db}")
        temporary_db.unlink()

    key = ensure_private_key(args.id_key)
    source_sha256 = sha256_file(args.source)
    script_sha256 = sha256_file(Path(__file__).resolve())
    protocol_sha256 = sha256_file(args.protocol)
    started = time.monotonic()

    connection = initialize_database(temporary_db)
    try:
        connection.executemany(
            "INSERT INTO metadata VALUES (?, ?)",
            (
                ("schema_version", SCHEMA_VERSION),
                ("pipeline_id", PIPELINE_ID),
                ("source_sha256", source_sha256),
                ("script_sha256", script_sha256),
                ("protocol_sha256", protocol_sha256),
            ),
        )
        connection.commit()
        source_rows = ingest_source(connection, args.source, key)
        clean_posts(connection)
        build_candidates(connection, key)
        connection.execute("PRAGMA optimize")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
        connection.commit()
    except Exception:
        connection.close()
        if temporary_db.exists():
            temporary_db.unlink()
        raise
    connection.close()

    os.chmod(temporary_db, 0o600)
    os.replace(temporary_db, args.output_db)
    private_db_sha256 = sha256_file(args.output_db)
    elapsed = time.monotonic() - started

    readonly = sqlite3.connect(f"file:{args.output_db}?mode=ro", uri=True)
    try:
        report = build_aggregate_report(
            readonly,
            args.source,
            source_sha256,
            source_rows,
            script_sha256,
            protocol_sha256,
            args.output_db,
            private_db_sha256,
            elapsed,
        )
    finally:
        readonly.close()
    atomic_write_json(args.report, report)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "pipeline_id": PIPELINE_ID,
        "dataset": "Internet Argument Corpus 2.0",
        "subset": "4forums",
        "generated_at": report["generated_at"],
        "artifact_status": "generated_pending_independent_verification",
        "source": {
            "manifest": "raw-files.json",
            "filename": args.source.name,
            "size_bytes": args.source.stat().st_size,
            "sha256": source_sha256,
        },
        "private_artifact": {
            "filename": args.output_db.name,
            "size_bytes": args.output_db.stat().st_size,
            "sha256": private_db_sha256,
            "git_tracking": "forbidden",
        },
        "protocol": {
            "filename": args.protocol.name,
            "sha256": protocol_sha256,
        },
        "aggregate_report": {
            "filename": args.report.name,
            "sha256": sha256_file(args.report),
        },
        "contains_public_forum_text": False,
        "contains_public_source_or_sample_ids": False,
    }
    atomic_write_json(args.manifest, manifest)
    print(
        json.dumps(
            {
                "status": report["status"],
                "candidates": report["counts"]["declared_parent_candidates"],
                "eligible": report["counts"]["eligible_candidates"],
                "private_db_bytes": report["private_artifact"]["size_bytes"],
            },
            ensure_ascii=True,
        ),
        flush=True,
    )
    return report


def main() -> None:
    prepare_dataset(parse_args())


if __name__ == "__main__":
    main()
