#!/usr/bin/env python3
"""Build the private paired-view Weibo EClass dataset and public aggregates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import itertools
import json
import os
import random
import re
import secrets
import shutil
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


csv.field_size_limit(16 * 1024 * 1024)

PROTOCOL_ID = "DATA-WEIBO-TASK-V1"
SCHEMA_VERSION = "weibo-eclass-paired-v1"
FROZEN_DATE = "2026-08-08"
SEED = 20260808
SOURCE_REVISION = "d385f8cdc7e7ab9ca1ec62b8202c664a5ba651f3"
EXPECTED_SOURCE_SHA256 = "cd31ced8f9a4034c83065099061a23df3b402797841d8ff120c459da55251793"
SPLIT_FRACTIONS = {"train": 0.70, "validation": 0.15, "test": 0.15}
NEAR_DUPLICATE_THRESHOLD = 0.90

LABEL_MAP = {
    "快乐": "joy",
    "悲伤": "sadness",
    "愤怒": "anger",
    "正面": "positive",
    "负面": "negative",
    "中性": "neutral",
    "No_emotion": "no_emotion",
}
LABEL_ORDER = (
    "joy",
    "sadness",
    "anger",
    "positive",
    "negative",
    "neutral",
    "no_emotion",
)
CAUSE_LABELS = {"Y", "N"}
MARKERS = (
    "beg_preclause",
    "end_preclause",
    "beg_curclause",
    "end_curclause",
    "beg_sufclause",
    "end_sufclause",
)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_SOURCE = PROJECT_ROOT / "data/weibo-emotion-corpus/official/emotion_classification.tsv"
DEFAULT_PRIVATE_ROOT = PROJECT_ROOT / "data/weibo-emotion-corpus/derived-private/eclass-v1"
DEFAULT_PUBLIC_REPORT = SCRIPT_DIR / "reports/data-weibo-eclass-v1.json"
DEFAULT_PUBLIC_MANIFEST = PROJECT_ROOT / "data/weibo-emotion-corpus/eclass-v1.manifest.json"

URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"@[\w\-\u4e00-\u9fff]+", re.UNICODE)
SOURCE_ID_RE = re.compile(r"^(.+)-(\d+)$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def physical_line_count(path: Path) -> int:
    count = 0
    last = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            count += chunk.count(b"\n")
            last = chunk[-1:]
    return count + int(path.stat().st_size > 0 and last != b"\n")


def sanitize_text(tokens: Iterable[str]) -> str:
    text = unicodedata.normalize("NFKC", "".join(tokens))
    text = URL_RE.sub("<URL>", text)
    text = MENTION_RE.sub("<USER>", text)
    return re.sub(r"\s+", " ", text).strip()


def target_key(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text).lower())


def parse_source_identity(source_id: str) -> tuple[str, int] | None:
    match = SOURCE_ID_RE.fullmatch(source_id)
    if not match:
        return None
    return match.group(1), int(match.group(2))


def parse_eclass_row(row: list[str], logical_index: int) -> tuple[dict[str, Any] | None, str | None]:
    if len(row) < 2:
        return None, "missing_label"
    identity = parse_source_identity(row[0])
    if identity is None:
        return None, "invalid_source_id"
    if any(row.count(marker) != 1 for marker in MARKERS):
        return None, "marker_multiplicity"
    positions = [row.index(marker) for marker in MARKERS]
    if positions != sorted(positions):
        return None, "marker_order"
    group_source_id, sequence = identity
    prev_tokens = tuple(row[positions[0] + 1 : positions[1]])
    target_tokens = tuple(row[positions[2] + 1 : positions[3]])
    suffix_tokens = tuple(row[positions[4] + 1 : positions[5]])
    return {
        "source_id": row[0],
        "source_group_id": group_source_id,
        "sequence": sequence,
        "logical_index": logical_index,
        "upstream_label": row[1],
        "prev_tokens": prev_tokens,
        "target_tokens": target_tokens,
        "suffix_tokens": suffix_tokens,
    }, None


def group_is_consistent(records: list[dict[str, Any]]) -> bool:
    ordered = sorted(records, key=lambda record: record["sequence"])
    if not ordered:
        return False
    sequences = [record["sequence"] for record in ordered]
    if sequences != list(range(sequences[0], sequences[-1] + 1)):
        return False
    if ordered[0]["prev_tokens"] or ordered[-1]["suffix_tokens"]:
        return False
    for left, right in zip(ordered, ordered[1:]):
        if left["target_tokens"] != right["prev_tokens"]:
            return False
        if left["suffix_tokens"] != right["target_tokens"]:
            return False
    return True


class UnionFind:
    def __init__(self, values: Iterable[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        low, high = sorted((left_root, right_root))
        self.parent[high] = low


def char_ngrams(text: str, width: int = 3) -> frozenset[str]:
    if len(text) < width:
        return frozenset(text)
    return frozenset(text[index : index + width] for index in range(len(text) - width + 1))


def simhash64(features: Iterable[str]) -> int:
    features = tuple(features)
    if not features:
        return 0
    scores = [0] * 64
    for feature in features:
        value = int.from_bytes(hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest(), "big")
        for bit in range(64):
            scores[bit] += 1 if value & (1 << bit) else -1
    return sum(1 << bit for bit, score in enumerate(scores) if score >= 0)


def near_duplicate_pairs(keys: Iterable[str]) -> tuple[list[tuple[str, str, float]], int]:
    ordered = sorted(set(keys))
    grams = [char_ngrams(value) for value in ordered]
    hashes = [simhash64(value) for value in grams]
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, value in enumerate(hashes):
        for band in range(4):
            buckets[(band, (value >> (band * 16)) & 0xFFFF)].append(index)
    candidates: set[tuple[int, int]] = set()
    for indices in buckets.values():
        for left, right in itertools.combinations(indices, 2):
            candidates.add((left, right))
    matches: list[tuple[str, str, float]] = []
    for left, right in sorted(candidates):
        left_text, right_text = ordered[left], ordered[right]
        if min(len(left_text), len(right_text)) / max(len(left_text), len(right_text), 1) < 0.8:
            continue
        union = grams[left] | grams[right]
        similarity = len(grams[left] & grams[right]) / len(union) if union else 1.0
        if similarity >= NEAR_DUPLICATE_THRESHOLD:
            matches.append((left_text, right_text, round(similarity, 6)))
    return matches, len(candidates)


def select_canonical(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record["target_key"], record["label"])].append(record)
    selected = [
        min(values, key=lambda value: (not value["context_available"], value["logical_index"]))
        for values in grouped.values()
    ]
    return sorted(selected, key=lambda value: value["logical_index"])


def component_fingerprint(records: list[dict[str, Any]]) -> str:
    groups = sorted({record["source_group_id"] for record in records})
    return hashlib.sha256("\n".join(groups).encode("utf-8")).hexdigest()


def allocation_cost(
    row_count: int,
    strata: Counter[str],
    target_rows: float,
    target_strata: dict[str, float],
) -> float:
    cost = 2.0 * ((row_count - target_rows) / max(target_rows, 1.0)) ** 2
    for name, target in target_strata.items():
        if name in {"__context_available__", "__context_missing__"}:
            weight = 128.0
        elif name == "__ambiguous_target__":
            weight = 128.0
        else:
            weight = 1.0
        cost += weight * ((strata[name] - target) / max(target, 3.0)) ** 2
    return cost


def allocate_splits(components: list[dict[str, Any]]) -> dict[str, str]:
    all_records = [record for component in components for record in component["records"]]
    total_rows = len(all_records)
    strata_names = list(LABEL_ORDER) + [
        "__context_available__",
        "__context_missing__",
        "__ambiguous_target__",
    ]
    total_strata = Counter(record["label"] for record in all_records)
    total_strata["__context_available__"] = sum(record["context_available"] for record in all_records)
    total_strata["__context_missing__"] = sum(not record["context_available"] for record in all_records)
    total_strata["__ambiguous_target__"] = sum(record["ambiguous_target"] for record in all_records)
    remaining = {component["fingerprint"]: component for component in components}
    assignments: dict[str, str] = {}

    for split_name in ("validation", "test"):
        fraction = SPLIT_FRACTIONS[split_name]
        target_rows = total_rows * fraction
        target_strata = {name: total_strata[name] * fraction for name in strata_names}
        current_rows = 0
        current_strata: Counter[str] = Counter()
        while remaining and current_rows < target_rows:
            before = allocation_cost(current_rows, current_strata, target_rows, target_strata)
            best: tuple[float, int, str, dict[str, Any]] | None = None
            for component in remaining.values():
                after_rows = current_rows + component["row_count"]
                after_strata = current_strata + component["strata"]
                gain = before - allocation_cost(after_rows, after_strata, target_rows, target_strata)
                overflow = max(0.0, after_rows - target_rows - 10.0)
                gain -= 20.0 * (overflow / max(target_rows, 1.0)) ** 2
                tie = hashlib.sha256(
                    f"{SEED}:{split_name}:{component['fingerprint']}".encode("ascii")
                ).hexdigest()
                candidate = (gain, -component["row_count"], tie, component)
                if best is None or candidate[:3] > best[:3]:
                    best = candidate
            if best is None:
                raise RuntimeError(f"Unable to allocate {split_name}")
            chosen = best[3]
            assignments[chosen["fingerprint"]] = split_name
            current_rows += chosen["row_count"]
            current_strata.update(chosen["strata"])
            del remaining[chosen["fingerprint"]]

    for fingerprint in remaining:
        assignments[fingerprint] = "train"
    return refine_assignments(components, assignments, total_strata, total_rows, strata_names)


def refine_assignments(
    components: list[dict[str, Any]],
    assignments: dict[str, str],
    total_strata: Counter[str],
    total_rows: int,
    strata_names: list[str],
) -> dict[str, str]:
    states: dict[str, dict[str, Any]] = {
        split: {"rows": 0, "strata": Counter()} for split in SPLIT_FRACTIONS
    }
    for component in components:
        split = assignments[component["fingerprint"]]
        states[split]["rows"] += component["row_count"]
        states[split]["strata"].update(component["strata"])

    def state_cost(split: str, rows: int, strata: Counter[str]) -> float:
        fraction = SPLIT_FRACTIONS[split]
        target_rows = total_rows * fraction
        target_strata = {name: total_strata[name] * fraction for name in strata_names}
        row_cost = 512.0 * ((rows - target_rows) / max(target_rows, 1.0)) ** 2
        strata_cost = allocation_cost(rows, strata, target_rows, target_strata)
        return row_cost + strata_cost

    def swapped_strata(
        current: Counter[str], remove: Counter[str], add: Counter[str]
    ) -> Counter[str]:
        value = current.copy()
        value.subtract(remove)
        value.update(add)
        return value

    rng = random.Random(SEED)
    iterations = min(350_000, max(20_000, len(components) * 125))
    for _ in range(iterations):
        left, right = rng.sample(components, 2)
        left_split = assignments[left["fingerprint"]]
        right_split = assignments[right["fingerprint"]]
        if left_split == right_split:
            continue
        before = state_cost(
            left_split, states[left_split]["rows"], states[left_split]["strata"]
        ) + state_cost(
            right_split, states[right_split]["rows"], states[right_split]["strata"]
        )
        left_rows = states[left_split]["rows"] - left["row_count"] + right["row_count"]
        right_rows = states[right_split]["rows"] - right["row_count"] + left["row_count"]
        left_strata = swapped_strata(
            states[left_split]["strata"], left["strata"], right["strata"]
        )
        right_strata = swapped_strata(
            states[right_split]["strata"], right["strata"], left["strata"]
        )
        after = state_cost(left_split, left_rows, left_strata) + state_cost(
            right_split, right_rows, right_strata
        )
        if after + 1e-12 >= before:
            continue
        assignments[left["fingerprint"]] = right_split
        assignments[right["fingerprint"]] = left_split
        states[left_split] = {"rows": left_rows, "strata": left_strata}
        states[right_split] = {"rows": right_rows, "strata": right_strata}
    return assignments


def hmac_id(key: bytes, namespace: str, value: str) -> str:
    digest = hmac.new(key, f"{namespace}:{value}".encode("utf-8"), hashlib.sha256).hexdigest()[:20]
    return f"{namespace}-{digest}"


def assert_split_acceptance(
    split_records: dict[str, list[dict[str, Any]]], all_records: list[dict[str, Any]]
) -> None:
    total_rows = len(all_records)
    total_labels = Counter(record["label"] for record in all_records)
    total_slices = {
        "context_available": sum(record["context_available"] for record in all_records),
        "context_missing": sum(not record["context_available"] for record in all_records),
        "ambiguous_target": sum(record["ambiguous_target"] for record in all_records),
    }
    failures: dict[str, float] = {}
    for split, fraction in SPLIT_FRACTIONS.items():
        records = split_records[split]
        failures[f"rows:{split}"] = abs(len(records) / total_rows - fraction)
        labels = Counter(record["label"] for record in records)
        if set(labels) != set(LABEL_ORDER):
            raise RuntimeError(f"Missing label in {split} split")
        for label in LABEL_ORDER:
            failures[f"label:{split}:{label}"] = abs(labels[label] / total_labels[label] - fraction)
        slice_counts = {
            "context_available": sum(record["context_available"] for record in records),
            "context_missing": sum(not record["context_available"] for record in records),
            "ambiguous_target": sum(record["ambiguous_target"] for record in records),
        }
        for name, count in slice_counts.items():
            failures[f"slice:{split}:{name}"] = abs(count / max(total_slices[name], 1) - fraction)
    row_error = max(value for name, value in failures.items() if name.startswith("rows:"))
    label_error = max(value for name, value in failures.items() if name.startswith("label:"))
    slice_error = max(value for name, value in failures.items() if name.startswith("slice:"))
    if row_error > 0.005 or label_error > 0.05 or slice_error > 0.03:
        raise RuntimeError(
            "Split acceptance failed: "
            f"row_error={row_error:.6f}, label_error={label_error:.6f}, "
            f"slice_error={slice_error:.6f}"
        )


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def numeric_summary(values: Iterable[int]) -> dict[str, int | float]:
    ordered = sorted(values)
    if not ordered:
        return {"min": 0, "median": 0, "mean": 0, "p95": 0, "max": 0}
    return {
        "min": ordered[0],
        "median": round(statistics.median(ordered), 6),
        "mean": round(statistics.fmean(ordered), 6),
        "p95": ordered[min(len(ordered) - 1, int(0.95 * (len(ordered) - 1)))],
        "max": ordered[-1],
    }


def file_record(path: Path) -> dict[str, Any]:
    return {"path": relative(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def build(source: Path, private_root: Path, public_report: Path, public_manifest: Path) -> dict[str, Any]:
    source_sha = sha256_file(source)
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(f"Source SHA-256 mismatch: {source_sha}")
    if private_root.exists():
        raise FileExistsError(f"Refusing to overwrite immutable private output: {private_root}")

    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))

    scaffold_rows = 0
    raw_eclass_rows = 0
    parsed_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    failed_groups: set[str] = set()
    parse_failures: Counter[str] = Counter()
    upstream_labels: Counter[str] = Counter()

    for logical_index, row in enumerate(rows):
        if len(row) > 1 and row[1] in CAUSE_LABELS:
            scaffold_rows += 1
            continue
        raw_eclass_rows += 1
        if len(row) > 1:
            upstream_labels[row[1]] += 1
        parsed, error = parse_eclass_row(row, logical_index)
        if error:
            parse_failures[error] += 1
            identity = parse_source_identity(row[0]) if row else None
            failed_groups.add(identity[0] if identity else f"__invalid__{logical_index}")
            continue
        assert parsed is not None
        parsed_by_group[parsed["source_group_id"]].append(parsed)

    inconsistent_groups = {
        group_id for group_id, records in parsed_by_group.items() if not group_is_consistent(records)
    }
    failed_groups.update(inconsistent_groups)

    exclusions: Counter[str] = Counter()
    eligible: list[dict[str, Any]] = []
    for group_id, records in parsed_by_group.items():
        if group_id in failed_groups:
            exclusions["structure_failure_group"] += len(records)
            continue
        for record in records:
            upstream_label = record["upstream_label"]
            if upstream_label == "恐惧":
                exclusions["fear"] += 1
                continue
            if upstream_label not in LABEL_MAP:
                exclusions["composite_or_unknown"] += 1
                continue
            previous = sanitize_text(record["prev_tokens"])
            target = sanitize_text(record["target_tokens"])
            if not target:
                raise RuntimeError("Healthy primary-label EClass row has an empty target")
            eligible.append(
                {
                    **record,
                    "label": LABEL_MAP[upstream_label],
                    "previous": previous or None,
                    "target": target,
                    "target_key": target_key(target),
                    "context_available": bool(previous),
                }
            )
    exclusions["structure_failure_group"] += raw_eclass_rows - sum(
        len(records) for records in parsed_by_group.values()
    )

    by_target_label: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in eligible:
        by_target_label[(record["target_key"], record["label"])].append(record)
        by_target[record["target_key"]].append(record)

    canonical = select_canonical(eligible)
    target_label_count = Counter(record["target_key"] for record in canonical)
    for record in canonical:
        record["ambiguous_target"] = target_label_count[record["target_key"]] > 1

    groups = sorted({record["source_group_id"] for record in canonical})
    union_find = UnionFind(groups)
    canonical_by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in canonical:
        canonical_by_target[record["target_key"]].append(record)
    for records in canonical_by_target.values():
        first_group = records[0]["source_group_id"]
        for record in records[1:]:
            union_find.union(first_group, record["source_group_id"])

    near_pairs, near_candidate_count = near_duplicate_pairs(canonical_by_target)
    for left_key, right_key, _ in near_pairs:
        left_group = canonical_by_target[left_key][0]["source_group_id"]
        right_group = canonical_by_target[right_key][0]["source_group_id"]
        union_find.union(left_group, right_group)

    records_by_component: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in canonical:
        records_by_component[union_find.find(record["source_group_id"])].append(record)
    components: list[dict[str, Any]] = []
    for records in records_by_component.values():
        strata = Counter(record["label"] for record in records)
        strata["__context_available__"] = sum(record["context_available"] for record in records)
        strata["__context_missing__"] = sum(not record["context_available"] for record in records)
        strata["__ambiguous_target__"] = sum(record["ambiguous_target"] for record in records)
        components.append(
            {
                "fingerprint": component_fingerprint(records),
                "records": records,
                "row_count": len(records),
                "strata": strata,
            }
        )

    assignments = allocate_splits(components)
    split_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for component in components:
        split = assignments[component["fingerprint"]]
        for record in component["records"]:
            record["split"] = split
            split_records[split].append(record)
    assert_split_acceptance(split_records, canonical)

    temporary_root = private_root.with_name(f".{private_root.name}.tmp-{os.getpid()}")
    if temporary_root.exists():
        shutil.rmtree(temporary_root)
    temporary_root.mkdir(parents=True)
    key = secrets.token_bytes(32)
    key_path = temporary_root / "id-key.bin"
    key_path.write_bytes(key)
    key_path.chmod(0o600)

    def public_record(record: dict[str, Any], *, include_label: bool) -> dict[str, Any]:
        sample_id = hmac_id(key, "sample", record["source_id"])
        group_id = hmac_id(key, "group", record["source_group_id"])
        value: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "protocol_id": PROTOCOL_ID,
            "sample_id": sample_id,
            "group_id": group_id,
            "context_available": record["context_available"],
            "ambiguous_target": record["ambiguous_target"],
            "views": {
                "previous_context": {"previous": record["previous"], "target": record["target"]},
                "target_only": {"target": record["target"]},
            },
        }
        if include_label:
            value["label"] = record["label"]
        return value

    train_output = sorted(
        (public_record(record, include_label=True) for record in split_records["train"]),
        key=lambda value: value["sample_id"],
    )
    validation_output = sorted(
        (public_record(record, include_label=True) for record in split_records["validation"]),
        key=lambda value: value["sample_id"],
    )
    test_output = sorted(
        (public_record(record, include_label=False) for record in split_records["test"]),
        key=lambda value: value["sample_id"],
    )
    test_labels = sorted(
        (
            {
                "schema_version": "weibo-eclass-test-label-v1",
                "protocol_id": PROTOCOL_ID,
                "sample_id": hmac_id(key, "sample", record["source_id"]),
                "label": record["label"],
            }
            for record in split_records["test"]
        ),
        key=lambda value: value["sample_id"],
    )
    near_output = [
        {
            "left_key_id": hmac_id(key, "target", left),
            "right_key_id": hmac_id(key, "target", right),
            "jaccard": score,
        }
        for left, right, score in near_pairs
    ]

    output_paths = {
        "train": temporary_root / "train.jsonl",
        "validation": temporary_root / "validation.jsonl",
        "test_inputs": temporary_root / "test.inputs.jsonl",
        "test_labels": temporary_root / "test.labels.sealed.jsonl",
        "near_duplicates": temporary_root / "near-duplicate-candidates.jsonl",
    }
    write_jsonl(output_paths["train"], train_output)
    write_jsonl(output_paths["validation"], validation_output)
    write_jsonl(output_paths["test_inputs"], test_output)
    write_jsonl(output_paths["test_labels"], test_labels)
    write_jsonl(output_paths["near_duplicates"], near_output)

    split_summary: dict[str, Any] = {}
    for split_name in ("train", "validation", "test"):
        records = split_records[split_name]
        split_summary[split_name] = {
            "rows": len(records),
            "row_fraction": round(len(records) / len(canonical), 6),
            "groups": len({record["source_group_id"] for record in records}),
            "components": sum(assignments[value["fingerprint"]] == split_name for value in components),
            "context_available": sum(record["context_available"] for record in records),
            "context_missing": sum(not record["context_available"] for record in records),
            "ambiguous_target_rows": sum(record["ambiguous_target"] for record in records),
            "label_counts": dict(sorted(Counter(record["label"] for record in records).items())),
        }

    private_manifest = {
        "schema_version": "weibo-eclass-private-manifest-v1",
        "protocol_id": PROTOCOL_ID,
        "frozen_date": FROZEN_DATE,
        "source_sha256": source_sha,
        "source_revision": SOURCE_REVISION,
        "split_seed": SEED,
        "label_order": list(LABEL_ORDER),
        "counts": {
            "logical_rows": len(rows),
            "scaffold_rows": scaffold_rows,
            "raw_eclass_rows": raw_eclass_rows,
            "healthy_primary_rows_before_dedup": len(eligible),
            "canonical_rows": len(canonical),
            "source_groups_retained": len(groups),
            "leakage_components": len(components),
        },
        "split_summary": split_summary,
        "test_gate": {"status": "sealed_not_authorized_for_model_access"},
        "id_key_sha256": hashlib.sha256(key).hexdigest(),
    }
    write_json(temporary_root / "private-manifest.json", private_manifest)
    temporary_root.replace(private_root)

    private_artifacts = {
        name: file_record(private_root / path.name) for name, path in output_paths.items()
    }
    private_artifacts["private_manifest"] = file_record(private_root / "private-manifest.json")

    final_label_counts = dict(sorted(Counter(record["label"] for record in canonical).items()))
    conflicting_targets = sum(
        len({record["label"] for record in records}) > 1 for records in by_target.values()
    )
    report = {
        "schema_version": "weibo-eclass-construction-report-v1",
        "protocol_id": PROTOCOL_ID,
        "status": "constructed_awaiting_independent_verification",
        "frozen_date": FROZEN_DATE,
        "source": {
            "repository": "https://github.com/wjhou/Weibo-Emotion-Corpus",
            "revision": SOURCE_REVISION,
            "license": "Apache-2.0",
            "file": file_record(source),
            "physical_lines": physical_line_count(source),
            "logical_rows": len(rows),
        },
        "task": {
            "type": "single_label_clause_emotion_classification",
            "labels": list(LABEL_ORDER),
            "views": ["target_only", "previous_context"],
            "future_context_used": False,
            "previous_context_semantics": "immediately preceding clause in the released multi-user group",
        },
        "parsing": {
            "scaffold_rows_excluded": scaffold_rows,
            "raw_eclass_rows": raw_eclass_rows,
            "parse_failure_counts": dict(sorted(parse_failures.items())),
            "failed_source_groups": len(failed_groups),
            "upstream_label_counts": dict(sorted(upstream_labels.items())),
            "exclusion_counts": dict(sorted(exclusions.items())),
        },
        "deduplication": {
            "eligible_rows_before_dedup": len(eligible),
            "normalized_target_keys": len(by_target),
            "target_label_pairs": len(by_target_label),
            "canonical_rows": len(canonical),
            "collapsed_same_target_label_rows": len(eligible) - len(canonical),
            "multi_label_target_keys": conflicting_targets,
            "ambiguous_target_rows_retained": sum(record["ambiguous_target"] for record in canonical),
            "near_duplicate_method": "char_trigram_simhash_lsh_then_jaccard",
            "near_duplicate_threshold": NEAR_DUPLICATE_THRESHOLD,
            "near_duplicate_candidate_pairs": near_candidate_count,
            "near_duplicate_matches": len(near_pairs),
            "claim_boundary": "lexical near-duplicate audit, not semantic equivalence",
        },
        "retained": {
            "rows": len(canonical),
            "source_groups": len(groups),
            "leakage_components": len(components),
            "label_counts": final_label_counts,
            "context_available": sum(record["context_available"] for record in canonical),
            "context_missing": sum(not record["context_available"] for record in canonical),
            "target_length_codepoints": numeric_summary(len(record["target"]) for record in canonical),
            "previous_length_codepoints_when_available": numeric_summary(
                len(record["previous"]) for record in canonical if record["previous"]
            ),
        },
        "split": {
            "seed": SEED,
            "target_fractions": SPLIT_FRACTIONS,
            "unit": "source_group_and_duplicate_bound_leakage_component",
            "stratified_dimensions": list(LABEL_ORDER)
            + ["context_available", "context_missing", "ambiguous_target"],
            "summary_without_test_label_distribution": {
                name: {key: value for key, value in summary.items() if key != "label_counts"}
                for name, summary in split_summary.items()
            },
        },
        "test_gate": {
            "status": "sealed_not_authorized_for_model_access",
            "inputs_contain_gold_labels": False,
            "labels_gitignored": True,
            "test_inputs_sha256": private_artifacts["test_inputs"]["sha256"],
            "test_labels_sha256": private_artifacts["test_labels"]["sha256"],
        },
        "private_artifacts": private_artifacts,
        "limitations": [
            "PrevCL is adjacent released context, not a verified reply parent or complete thread.",
            "The source is Chinese microblog data rather than a broad modern forum sample.",
            "Fear and composite labels are excluded from the frozen seven-class primary task.",
            "Near-duplicate detection is lexical and approximate; it does not establish semantic identity.",
            "The held-out split differs from the source paper's five-fold cross-validation protocol.",
        ],
    }
    write_json(public_report, report)

    manifest = {
        "schema_version": "weibo-eclass-task-manifest-v1",
        "protocol_id": PROTOCOL_ID,
        "status": "constructed_awaiting_independent_verification",
        "source": {
            "revision": SOURCE_REVISION,
            "sha256": source_sha,
            "license": "Apache-2.0",
        },
        "private_root": relative(private_root),
        "public_report": file_record(public_report),
        "private_artifacts": private_artifacts,
        "counts": {
            "retained_rows": len(canonical),
            "source_groups": len(groups),
            "leakage_components": len(components),
            "split_rows": {name: summary["rows"] for name, summary in split_summary.items()},
        },
        "test_gate": report["test_gate"],
    }
    write_json(public_manifest, manifest)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--private-root", type=Path, default=DEFAULT_PRIVATE_ROOT)
    parser.add_argument("--public-report", type=Path, default=DEFAULT_PUBLIC_REPORT)
    parser.add_argument("--public-manifest", type=Path, default=DEFAULT_PUBLIC_MANIFEST)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = build(
            args.source.resolve(),
            args.private_root.resolve(),
            args.public_report.resolve(),
            args.public_manifest.resolve(),
        )
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "protocol_id": PROTOCOL_ID,
                "status": report["status"],
                "retained_rows": report["retained"]["rows"],
                "split_rows": {
                    name: value["rows"]
                    for name, value in report["split"]["summary_without_test_label_distribution"].items()
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
