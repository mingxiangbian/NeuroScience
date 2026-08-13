#!/usr/bin/env python3
"""Independently verify DATA-WEIBO-TASK-V1 without importing the builder."""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import itertools
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


csv.field_size_limit(16 * 1024 * 1024)

PROTOCOL_ID = "DATA-WEIBO-TASK-V1"
EXPECTED_SOURCE_SHA256 = "cd31ced8f9a4034c83065099061a23df3b402797841d8ff120c459da55251793"
EXPECTED_FRACTIONS = {"train": 0.70, "validation": 0.15, "test": 0.15}
NEAR_THRESHOLD = 0.90
LABEL_MAP = {
    "快乐": "joy",
    "悲伤": "sadness",
    "愤怒": "anger",
    "正面": "positive",
    "负面": "negative",
    "中性": "neutral",
    "No_emotion": "no_emotion",
}
LABELS = set(LABEL_MAP.values())
CAUSE_LABELS = {"Y", "N"}
MARKERS = (
    "beg_preclause",
    "end_preclause",
    "beg_curclause",
    "end_curclause",
    "beg_sufclause",
    "end_sufclause",
)
SOURCE_ID_RE = re.compile(r"^(.+)-(\d+)$")
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"@[\w\-\u4e00-\u9fff]+", re.UNICODE)
SAMPLE_ID_RE = re.compile(r"^sample-[0-9a-f]{20}$")
GROUP_ID_RE = re.compile(r"^group-[0-9a-f]{20}$")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_SOURCE = PROJECT_ROOT / "data/weibo-emotion-corpus/official/emotion_classification.tsv"
DEFAULT_PRIVATE_ROOT = PROJECT_ROOT / "data/weibo-emotion-corpus/derived-private/eclass-v1"
DEFAULT_PUBLIC_REPORT = SCRIPT_DIR / "reports/data-weibo-eclass-v1.json"
DEFAULT_PUBLIC_MANIFEST = PROJECT_ROOT / "data/weibo-emotion-corpus/eclass-v1.manifest.json"
DEFAULT_VERIFICATION_REPORT = SCRIPT_DIR / "reports/data-weibo-eclass-v1-verification.json"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def sanitize(tokens: Iterable[str]) -> str:
    value = unicodedata.normalize("NFKC", "".join(tokens))
    value = URL_RE.sub("<URL>", value)
    value = MENTION_RE.sub("<USER>", value)
    return re.sub(r"\s+", " ", value).strip()


def normalized_target(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value).lower())


def identity(value: str) -> tuple[str, int] | None:
    match = SOURCE_ID_RE.fullmatch(value)
    return (match.group(1), int(match.group(2))) if match else None


def parse_row(row: list[str], index: int) -> tuple[dict[str, Any] | None, str | None]:
    if len(row) < 2:
        return None, "missing_label"
    source_identity = identity(row[0])
    if source_identity is None:
        return None, "invalid_source_id"
    if any(row.count(marker) != 1 for marker in MARKERS):
        return None, "marker_multiplicity"
    positions = [row.index(marker) for marker in MARKERS]
    if positions != sorted(positions):
        return None, "marker_order"
    return {
        "source_id": row[0],
        "source_group": source_identity[0],
        "sequence": source_identity[1],
        "index": index,
        "upstream_label": row[1],
        "prev": tuple(row[positions[0] + 1 : positions[1]]),
        "target": tuple(row[positions[2] + 1 : positions[3]]),
        "suffix": tuple(row[positions[4] + 1 : positions[5]]),
    }, None


def healthy(records: list[dict[str, Any]]) -> bool:
    ordered = sorted(records, key=lambda value: value["sequence"])
    if not ordered:
        return False
    sequence = [value["sequence"] for value in ordered]
    if sequence != list(range(sequence[0], sequence[-1] + 1)):
        return False
    if ordered[0]["prev"] or ordered[-1]["suffix"]:
        return False
    return all(
        left["target"] == right["prev"] and left["suffix"] == right["target"]
        for left, right in zip(ordered, ordered[1:])
    )


def private_id(key: bytes, namespace: str, value: str) -> str:
    value_digest = hmac.new(
        key, f"{namespace}:{value}".encode("utf-8"), hashlib.sha256
    ).hexdigest()[:20]
    return f"{namespace}-{value_digest}"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"Blank JSONL line in {path}:{line_number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Non-object JSONL record in {path}:{line_number}")
            values.append(value)
    return values


def char_ngrams(text: str) -> frozenset[str]:
    return frozenset(text if len(text) < 3 else (text[index : index + 3] for index in range(len(text) - 2)))


def simhash(features: Iterable[str]) -> int:
    values = tuple(features)
    if not values:
        return 0
    scores = [0] * 64
    for feature in values:
        number = int.from_bytes(hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest(), "big")
        for bit in range(64):
            scores[bit] += 1 if number & (1 << bit) else -1
    return sum(1 << bit for bit, score in enumerate(scores) if score >= 0)


def recompute_near_pairs(keys: Iterable[str]) -> tuple[set[tuple[str, str]], int]:
    ordered = sorted(set(keys))
    grams = [char_ngrams(value) for value in ordered]
    hashes = [simhash(value) for value in grams]
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, value in enumerate(hashes):
        for band in range(4):
            buckets[(band, (value >> (band * 16)) & 0xFFFF)].append(index)
    candidates: set[tuple[int, int]] = set()
    for indices in buckets.values():
        candidates.update(itertools.combinations(indices, 2))
    matches: set[tuple[str, str]] = set()
    for left, right in candidates:
        left_text, right_text = ordered[left], ordered[right]
        if min(len(left_text), len(right_text)) / max(len(left_text), len(right_text), 1) < 0.8:
            continue
        union = grams[left] | grams[right]
        similarity = len(grams[left] & grams[right]) / len(union) if union else 1.0
        if similarity >= NEAR_THRESHOLD:
            matches.add(tuple(sorted((left_text, right_text))))
    return matches, len(candidates)


def recursive_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        found.update(value)
        for nested in value.values():
            found.update(recursive_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            found.update(recursive_keys(nested))
    return found


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_record(path: Path) -> dict[str, Any]:
    try:
        display = path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        display = str(path.resolve())
    return {"path": display, "bytes": path.stat().st_size, "sha256": digest(path)}


class Checks:
    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []

    def add(self, name: str, passed: bool, detail: Any = None) -> None:
        self.results.append({"name": name, "passed": bool(passed), "detail": detail})

    @property
    def failures(self) -> list[dict[str, Any]]:
        return [value for value in self.results if not value["passed"]]


def verify(
    source: Path,
    private_root: Path,
    public_report_path: Path,
    public_manifest_path: Path,
    verification_report_path: Path,
) -> dict[str, Any]:
    checks = Checks()
    checks.add("source_sha256", digest(source) == EXPECTED_SOURCE_SHA256, digest(source))

    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    scaffold = 0
    raw_eclass = 0
    parsed_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    bad_groups: set[str] = set()
    parse_failures: Counter[str] = Counter()
    raw_labels: Counter[str] = Counter()
    for index, row in enumerate(rows):
        if len(row) > 1 and row[1] in CAUSE_LABELS:
            scaffold += 1
            continue
        raw_eclass += 1
        if len(row) > 1:
            raw_labels[row[1]] += 1
        parsed, error = parse_row(row, index)
        if error:
            parse_failures[error] += 1
            source_identity = identity(row[0]) if row else None
            bad_groups.add(source_identity[0] if source_identity else f"__invalid__{index}")
        else:
            assert parsed is not None
            parsed_by_group[parsed["source_group"]].append(parsed)
    bad_groups.update(group for group, records in parsed_by_group.items() if not healthy(records))

    eligible: list[dict[str, Any]] = []
    exclusion_counts: Counter[str] = Counter()
    for group, records in parsed_by_group.items():
        if group in bad_groups:
            exclusion_counts["structure_failure_group"] += len(records)
            continue
        for record in records:
            label = record["upstream_label"]
            if label == "恐惧":
                exclusion_counts["fear"] += 1
                continue
            if label not in LABEL_MAP:
                exclusion_counts["composite_or_unknown"] += 1
                continue
            previous = sanitize(record["prev"])
            target = sanitize(record["target"])
            eligible.append(
                {
                    **record,
                    "label": LABEL_MAP[label],
                    "previous": previous or None,
                    "target_text": target,
                    "target_key": normalized_target(target),
                    "context_available": bool(previous),
                }
            )
    exclusion_counts["structure_failure_group"] += raw_eclass - sum(
        len(records) for records in parsed_by_group.values()
    )
    checks.add("all_expected_labels_only", all(value["label"] in LABELS for value in eligible))
    checks.add("nonempty_targets", all(value["target_text"] for value in eligible))

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in eligible:
        grouped[(record["target_key"], record["label"])].append(record)
    expected: list[dict[str, Any]] = []
    for records in grouped.values():
        expected.append(min(records, key=lambda value: (not value["context_available"], value["index"])))
    key_counts = Counter(value["target_key"] for value in expected)
    for value in expected:
        value["ambiguous_target"] = key_counts[value["target_key"]] > 1

    key_path = private_root / "id-key.bin"
    key = key_path.read_bytes()
    checks.add("hmac_key_size", len(key) == 32, len(key))
    expected_by_id: dict[str, dict[str, Any]] = {}
    for value in expected:
        sample_id = private_id(key, "sample", value["source_id"])
        expected_by_id[sample_id] = {
            "group_id": private_id(key, "group", value["source_group"]),
            "label": value["label"],
            "previous": value["previous"],
            "target": value["target_text"],
            "target_key": value["target_key"],
            "context_available": value["context_available"],
            "ambiguous_target": value["ambiguous_target"],
        }

    train = load_jsonl(private_root / "train.jsonl")
    validation = load_jsonl(private_root / "validation.jsonl")
    test_inputs = load_jsonl(private_root / "test.inputs.jsonl")
    test_labels = load_jsonl(private_root / "test.labels.sealed.jsonl")
    near_private = load_jsonl(private_root / "near-duplicate-candidates.jsonl")
    label_by_test_id = {value["sample_id"]: value["label"] for value in test_labels}
    checks.add("test_label_ids_unique", len(label_by_test_id) == len(test_labels))
    checks.add(
        "test_input_label_ids_match",
        {value["sample_id"] for value in test_inputs} == set(label_by_test_id),
    )
    checks.add("test_inputs_do_not_contain_label", all("label" not in value for value in test_inputs))
    checks.add(
        "sealed_labels_minimal_schema",
        all(set(value) == {"schema_version", "protocol_id", "sample_id", "label"} for value in test_labels),
    )

    actual: dict[str, tuple[str, dict[str, Any]]] = {}
    invalid_sample_id_count = 0
    duplicate_sample_id_count = 0
    for split, values in (("train", train), ("validation", validation), ("test", test_inputs)):
        for value in values:
            sample_id = value.get("sample_id")
            invalid_sample_id_count += int(not SAMPLE_ID_RE.fullmatch(str(sample_id)))
            if sample_id in actual:
                duplicate_sample_id_count += 1
            actual[sample_id] = (split, value)
    checks.add("sample_id_format", invalid_sample_id_count == 0, invalid_sample_id_count)
    checks.add("sample_ids_unique", duplicate_sample_id_count == 0, duplicate_sample_id_count)
    checks.add("record_set_exact", set(actual) == set(expected_by_id), {
        "expected": len(expected_by_id), "actual": len(actual)
    })

    field_mismatches = 0
    group_splits: dict[str, set[str]] = defaultdict(set)
    target_splits: dict[str, set[str]] = defaultdict(set)
    split_labels: dict[str, Counter[str]] = defaultdict(Counter)
    split_context: Counter[str] = Counter()
    split_context_missing: Counter[str] = Counter()
    split_ambiguous: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    for sample_id, (split, value) in actual.items():
        expected_value = expected_by_id.get(sample_id)
        if expected_value is None:
            field_mismatches += 1
            continue
        views = value.get("views", {})
        previous_view = views.get("previous_context", {})
        target_view = views.get("target_only", {})
        actual_label = label_by_test_id.get(sample_id) if split == "test" else value.get("label")
        observed = {
            "group_id": value.get("group_id"),
            "label": actual_label,
            "previous": previous_view.get("previous"),
            "target": previous_view.get("target"),
            "target_only": target_view.get("target"),
            "context_available": value.get("context_available"),
            "ambiguous_target": value.get("ambiguous_target"),
        }
        reference = {
            "group_id": expected_value["group_id"],
            "label": expected_value["label"],
            "previous": expected_value["previous"],
            "target": expected_value["target"],
            "target_only": expected_value["target"],
            "context_available": expected_value["context_available"],
            "ambiguous_target": expected_value["ambiguous_target"],
        }
        field_mismatches += int(observed != reference)
        group_splits[expected_value["group_id"]].add(split)
        target_splits[expected_value["target_key"]].add(split)
        split_labels[split][actual_label] += 1
        split_context[split] += int(bool(value.get("context_available")))
        split_context_missing[split] += int(not bool(value.get("context_available")))
        split_ambiguous[split] += int(bool(value.get("ambiguous_target")))
        split_counts[split] += 1
        if not GROUP_ID_RE.fullmatch(str(value.get("group_id"))):
            field_mismatches += 1
    checks.add("all_record_fields_exact", field_mismatches == 0, field_mismatches)
    checks.add("source_groups_do_not_cross_splits", all(len(value) == 1 for value in group_splits.values()))
    checks.add("normalized_targets_do_not_cross_splits", all(len(value) == 1 for value in target_splits.values()))

    total = len(expected_by_id)
    ratio_errors = {
        split: abs(split_counts[split] / total - fraction)
        for split, fraction in EXPECTED_FRACTIONS.items()
    }
    checks.add("split_row_ratio_tolerance", max(ratio_errors.values()) <= 0.005, ratio_errors)
    checks.add(
        "all_labels_present_in_each_split",
        all(set(split_labels[split]) == LABELS for split in EXPECTED_FRACTIONS),
        {split: sorted(split_labels[split]) for split in EXPECTED_FRACTIONS},
    )
    total_labels = Counter(value["label"] for value in expected_by_id.values())
    label_fraction_error: dict[str, float] = {}
    for split, target_fraction in EXPECTED_FRACTIONS.items():
        for label in LABELS:
            observed = split_labels[split][label] / total_labels[label]
            label_fraction_error[f"{split}:{label}"] = abs(observed - target_fraction)
    checks.add(
        "label_allocation_tolerance",
        max(label_fraction_error.values(), default=0.0) <= 0.05,
        {"max_absolute_error": round(max(label_fraction_error.values(), default=0.0), 6)},
    )
    total_context = sum(split_context.values())
    total_context_missing = sum(split_context_missing.values())
    total_ambiguous = sum(split_ambiguous.values())
    slice_fraction_error: dict[str, float] = {}
    for split, target_fraction in EXPECTED_FRACTIONS.items():
        slice_fraction_error[f"{split}:context_available"] = abs(
            split_context[split] / max(total_context, 1) - target_fraction
        )
        slice_fraction_error[f"{split}:context_missing"] = abs(
            split_context_missing[split] / max(total_context_missing, 1) - target_fraction
        )
        slice_fraction_error[f"{split}:ambiguous_target"] = abs(
            split_ambiguous[split] / max(total_ambiguous, 1) - target_fraction
        )
    checks.add(
        "context_and_ambiguity_allocation_tolerance",
        max(slice_fraction_error.values(), default=0.0) <= 0.03,
        {"max_absolute_error": round(max(slice_fraction_error.values(), default=0.0), 6)},
    )

    near_pairs, candidate_count = recompute_near_pairs(value["target_key"] for value in expected_by_id.values())
    checks.add("near_candidate_count_recomputed", candidate_count >= len(near_pairs), candidate_count)
    near_cross_split = 0
    for left, right in near_pairs:
        if target_splits[left] != target_splits[right]:
            near_cross_split += 1
    checks.add("near_duplicate_pairs_do_not_cross_splits", near_cross_split == 0, near_cross_split)
    checks.add("near_private_row_count", len(near_private) == len(near_pairs), {
        "expected": len(near_pairs), "actual": len(near_private)
    })

    public_report = json.loads(public_report_path.read_text(encoding="utf-8"))
    public_manifest = json.loads(public_manifest_path.read_text(encoding="utf-8"))
    checks.add("public_protocol_ids", public_report.get("protocol_id") == PROTOCOL_ID and public_manifest.get("protocol_id") == PROTOCOL_ID)
    checks.add("public_retained_count", public_report.get("retained", {}).get("rows") == total, total)
    checks.add(
        "public_source_counts",
        public_report.get("source", {}).get("logical_rows") == len(rows)
        and public_report.get("parsing", {}).get("scaffold_rows_excluded") == scaffold
        and public_report.get("parsing", {}).get("raw_eclass_rows") == raw_eclass,
    )
    checks.add(
        "public_exclusion_counts",
        public_report.get("parsing", {}).get("exclusion_counts") == dict(sorted(exclusion_counts.items())),
        dict(exclusion_counts),
    )
    forbidden_public_keys = {"sample_id", "group_id", "source_id", "source_group_id", "previous", "target", "label"}
    checks.add(
        "public_reports_have_no_row_level_keys",
        not (recursive_keys(public_report) | recursive_keys(public_manifest)) & forbidden_public_keys,
    )

    artifact_map = {
        "train": private_root / "train.jsonl",
        "validation": private_root / "validation.jsonl",
        "test_inputs": private_root / "test.inputs.jsonl",
        "test_labels": private_root / "test.labels.sealed.jsonl",
        "near_duplicates": private_root / "near-duplicate-candidates.jsonl",
        "private_manifest": private_root / "private-manifest.json",
    }
    manifest_artifacts = public_manifest.get("private_artifacts", {})
    for name, path in artifact_map.items():
        checks.add(
            f"artifact_hash:{name}",
            manifest_artifacts.get(name, {}).get("sha256") == digest(path),
            digest(path),
        )

    # Always test the frozen production boundary, even when verifying a /tmp preflight build.
    ignore_probe = DEFAULT_PRIVATE_ROOT / "__git_ignore_probe__.txt"
    ignore_result = subprocess.run(
        ["git", "check-ignore", "-q", str(ignore_probe)],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
    )
    checks.add("private_root_gitignored", ignore_result.returncode == 0, ignore_result.returncode)

    verification = {
        "schema_version": "weibo-eclass-verification-report-v1",
        "protocol_id": PROTOCOL_ID,
        "status": "verified" if not checks.failures else "failed",
        "checks_total": len(checks.results),
        "checks_passed": len(checks.results) - len(checks.failures),
        "checks_failed": len(checks.failures),
        "failures": checks.failures,
        "aggregate": {
            "logical_rows": len(rows),
            "scaffold_rows": scaffold,
            "raw_eclass_rows": raw_eclass,
            "parse_failure_counts": dict(sorted(parse_failures.items())),
            "failed_groups": len(bad_groups),
            "eligible_rows_before_dedup": len(eligible),
            "retained_rows": total,
            "retained_label_counts": dict(sorted(total_labels.items())),
            "split_rows": dict(sorted(split_counts.items())),
            "split_context_available": dict(sorted(split_context.items())),
            "split_context_missing": dict(sorted(split_context_missing.items())),
            "split_ambiguous_target": dict(sorted(split_ambiguous.items())),
            "near_duplicate_matches": len(near_pairs),
            "max_label_allocation_error": round(max(label_fraction_error.values(), default=0.0), 6),
            "max_context_or_ambiguity_allocation_error": round(
                max(slice_fraction_error.values(), default=0.0), 6
            ),
        },
        "claim_boundary": "This verifies data construction and sealing only; no model result was produced or inspected.",
    }
    write_json(verification_report_path, verification)

    if verification["status"] == "verified":
        public_manifest["status"] = "verified"
        public_manifest["verification_report"] = file_record(verification_report_path)
        write_json(public_manifest_path, public_manifest)
    return verification


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--private-root", type=Path, default=DEFAULT_PRIVATE_ROOT)
    parser.add_argument("--public-report", type=Path, default=DEFAULT_PUBLIC_REPORT)
    parser.add_argument("--public-manifest", type=Path, default=DEFAULT_PUBLIC_MANIFEST)
    parser.add_argument("--verification-report", type=Path, default=DEFAULT_VERIFICATION_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = verify(
            args.source.resolve(),
            args.private_root.resolve(),
            args.public_report.resolve(),
            args.public_manifest.resolve(),
            args.verification_report.resolve(),
        )
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps({
        "protocol_id": PROTOCOL_ID,
        "status": result["status"],
        "checks_passed": result["checks_passed"],
        "checks_total": result["checks_total"],
    }, sort_keys=True))
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
