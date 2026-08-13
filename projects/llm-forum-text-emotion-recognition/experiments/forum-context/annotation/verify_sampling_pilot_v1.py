#!/usr/bin/env python3
"""Independently replay and verify DATA-FCTX-SAMPLE-V1 metadata selection."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from sampling_common import (
    PRIMARY_LANES,
    PROTOCOL_ID,
    RESERVE_LANES,
    Candidate,
    load_candidates,
    load_weak_metadata,
    predicate_for_lane,
    rank_digest,
    sha256_file,
    verify_frozen_hashes,
)


HMAC_ID_RE = re.compile(r"\b[a-z]{3}_[0-9a-f]{64}\b")
FORBIDDEN_PUBLIC_KEYS = {
    "sample_uid",
    "thread_uid",
    "review_cluster_uid",
    "source_discussion_id",
    "target_source_post_id",
    "parent_source_post_id",
    "author_id",
    "username",
    "presented_quote",
    "presented_response",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--cleaning-db", type=Path, required=True)
    parser.add_argument("--dedup-db", type=Path, required=True)
    parser.add_argument("--sampling-protocol", type=Path, required=True)
    parser.add_argument("--label-protocol", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--preflight-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                raise ValueError(f"blank JSONL row in {path.name}:{line_number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"non-object JSONL row in {path.name}:{line_number}")
            records.append(value)
    return records


def is_gitignored(repo_root: Path, path: Path) -> bool:
    return (
        subprocess.run(
            ["git", "check-ignore", "-q", str(path.resolve())],
            cwd=repo_root,
            check=False,
        ).returncode
        == 0
    )


def public_payload_violations(value: object, path: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_PUBLIC_KEYS:
                violations.append(f"forbidden key at {child_path}")
            violations.extend(public_payload_violations(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(public_payload_violations(child, f"{path}[{index}]"))
    elif isinstance(value, str) and HMAC_ID_RE.search(value):
        violations.append(f"HMAC-like identifier at {path}")
    return violations


def replay_lane(
    candidates: Sequence[Candidate],
    *,
    lane: str,
    rank_lane: str,
    quota: int,
    predicate: Callable[[Candidate], bool],
    used_samples: set[str],
    used_threads: set[str],
    used_clusters: set[str],
) -> list[Candidate]:
    ranked = sorted(
        (candidate for candidate in candidates if predicate(candidate)),
        key=lambda candidate: rank_digest(rank_lane, candidate.sample_uid),
    )
    selected: list[Candidate] = []
    for candidate in ranked:
        if candidate.sample_uid in used_samples:
            continue
        if candidate.thread_uid in used_threads:
            continue
        cluster = candidate.review_cluster_uid
        if cluster is not None and cluster in used_clusters:
            continue
        selected.append(candidate)
        used_samples.add(candidate.sample_uid)
        used_threads.add(candidate.thread_uid)
        if cluster is not None:
            used_clusters.add(cluster)
        if len(selected) == quota:
            return selected
    return selected


def group_manifest(
    records: Sequence[dict[str, object]], role: str
) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for record in records:
        if record.get("role") != role:
            continue
        lane = str(record.get("lane"))
        grouped.setdefault(lane, []).append(record)
    for rows in grouped.values():
        rows.sort(key=lambda row: int(row["lane_position"]))
    return grouped


def verify(args: argparse.Namespace) -> dict[str, object]:
    private_dir = args.private_dir.resolve()
    sampling_manifest = private_dir / "sampling-manifest.jsonl"
    reserve_manifest = private_dir / "reserve-manifest.jsonl"
    repeat_manifest = private_dir / "repeat-manifest.jsonl"
    preflight = json.loads(args.preflight_report.read_text(encoding="utf-8"))
    primary_records = read_jsonl(sampling_manifest)
    reserve_records = read_jsonl(reserve_manifest)

    checks: list[dict[str, object]] = []
    mismatches: list[str] = []

    def check(name: str, condition: bool, detail: str) -> None:
        checks.append(
            {"name": name, "status": "passed" if condition else "failed", "detail": detail}
        )
        if not condition:
            mismatches.append(name)

    input_hashes = verify_frozen_hashes(
        cleaning_db=args.cleaning_db,
        dedup_db=args.dedup_db,
        source=args.source,
        label_protocol=args.label_protocol,
    )
    weak = load_weak_metadata(args.source)
    candidates, candidate_build = load_candidates(
        args.cleaning_db, args.dedup_db, weak
    )
    candidate_map = {candidate.sample_uid: candidate for candidate in candidates}

    check("preflight status", preflight.get("status") == "passed", "must be passed")
    check(
        "protocol identity",
        preflight.get("protocol_id") == PROTOCOL_ID,
        PROTOCOL_ID,
    )
    check(
        "sampling protocol hash",
        preflight["inputs"]["sampling_protocol"]["sha256"]
        == sha256_file(args.sampling_protocol),
        "SHA-256",
    )
    for report_key, actual_key in (
        ("source", "source_dump"),
        ("cleaning_database", "cleaning_database"),
        ("dedup_database", "dedup_database"),
        ("label_protocol", "label_protocol"),
    ):
        check(
            f"input hash {report_key}",
            preflight["inputs"][report_key]["sha256"] == input_hashes[actual_key],
            "SHA-256",
        )

    check(
        "candidate frame count",
        len(candidates) == 403183 and candidate_build["candidate_rows"] == 403183,
        f"rows={len(candidates)}",
    )
    check(
        "candidate view reconstruction",
        candidate_build["unreconstructible_rows"] == 0,
        f"unreconstructible={candidate_build['unreconstructible_rows']}",
    )
    check(
        "short flag rule",
        candidate_build["short_flag_mismatches"] == 0,
        f"mismatches={candidate_build['short_flag_mismatches']}",
    )

    expected_primary: dict[str, list[Candidate]] = {}
    expected_reserve: dict[str, list[Candidate]] = {}
    used_samples: set[str] = set()
    used_threads: set[str] = set()
    used_clusters: set[str] = set()
    for lane, quota in PRIMARY_LANES:
        expected_primary[lane] = replay_lane(
            candidates,
            lane=lane,
            rank_lane=lane,
            quota=quota,
            predicate=predicate_for_lane(lane),
            used_samples=used_samples,
            used_threads=used_threads,
            used_clusters=used_clusters,
        )
    for lane, quota in RESERVE_LANES:
        expected_reserve[lane] = replay_lane(
            candidates,
            lane=lane,
            rank_lane=f"{lane}_reserve",
            quota=quota,
            predicate=predicate_for_lane(lane),
            used_samples=used_samples,
            used_threads=used_threads,
            used_clusters=used_clusters,
        )

    actual_primary = group_manifest(primary_records, "primary")
    actual_reserve = group_manifest(reserve_records, "reserve")
    for lane, quota in PRIMARY_LANES:
        actual = actual_primary.get(lane, [])
        expected = expected_primary[lane]
        check(
            f"primary quota {lane}",
            len(actual) == quota and len(expected) == quota,
            f"rows={len(actual)} expected={quota}",
        )
        check(
            f"primary deterministic replay {lane}",
            [row.get("sample_uid") for row in actual]
            == [candidate.sample_uid for candidate in expected],
            "ordered sample sequence",
        )
    for lane, quota in RESERVE_LANES:
        actual = actual_reserve.get(lane, [])
        expected = expected_reserve[lane]
        check(
            f"reserve quota {lane}",
            len(actual) == quota and len(expected) == quota,
            f"rows={len(actual)} expected={quota}",
        )
        check(
            f"reserve deterministic replay {lane}",
            [row.get("sample_uid") for row in actual]
            == [candidate.sample_uid for candidate in expected],
            "ordered sample sequence",
        )

    all_records = primary_records + reserve_records
    manifest_samples = [str(record.get("sample_uid")) for record in all_records]
    manifest_threads = [str(record.get("thread_uid")) for record in all_records]
    manifest_clusters = [
        str(record["review_cluster_uid"])
        for record in all_records
        if record.get("review_cluster_uid") is not None
    ]
    check("primary manifest rows", len(primary_records) == 120, "rows=120")
    check("reserve manifest rows", len(reserve_records) == 60, "rows=60")
    check(
        "global sample uniqueness",
        len(manifest_samples) == len(set(manifest_samples)) == 180,
        "unique=180",
    )
    check(
        "global thread uniqueness",
        len(manifest_threads) == len(set(manifest_threads)) == 180,
        "unique=180",
    )
    check(
        "global review-cluster uniqueness",
        len(manifest_clusters) == len(set(manifest_clusters)),
        f"non_null={len(manifest_clusters)}",
    )
    check(
        "all manifest samples in candidate frame",
        all(sample_uid in candidate_map for sample_uid in manifest_samples),
        "candidate membership",
    )

    manifest_field_mismatches = 0
    for record in all_records:
        sample_uid = str(record.get("sample_uid"))
        candidate = candidate_map.get(sample_uid)
        if candidate is None:
            manifest_field_mismatches += 1
            continue
        rank_lane = (
            str(record["lane"])
            if record["role"] == "primary"
            else f"{record['lane']}_reserve"
        )
        if record.get("protocol_id") != PROTOCOL_ID:
            manifest_field_mismatches += 1
        if record.get("thread_uid") != candidate.thread_uid:
            manifest_field_mismatches += 1
        if record.get("review_cluster_uid") != candidate.review_cluster_uid:
            manifest_field_mismatches += 1
        if record.get("selection_rank_sha256") != rank_digest(rank_lane, sample_uid):
            manifest_field_mismatches += 1
        if not predicate_for_lane(str(record["lane"]))(candidate):
            manifest_field_mismatches += 1
    check(
        "manifest field and lane eligibility",
        manifest_field_mismatches == 0,
        f"mismatches={manifest_field_mismatches}",
    )

    ordered_primary = sorted(
        primary_records,
        key=lambda record: rank_digest("annotation_order", str(record["sample_uid"])),
    )
    annotation_order_mismatches = sum(
        int(record.get("annotation_order", -1)) != index
        for index, record in enumerate(ordered_primary, start=1)
    )
    annotation_order_mismatches += sum(
        record.get("annotation_order") is not None for record in reserve_records
    )
    check(
        "annotation order",
        annotation_order_mismatches == 0,
        f"mismatches={annotation_order_mismatches}",
    )

    check(
        "sampling manifest hash",
        preflight["private_artifacts"]["sampling_manifest"]["sha256"]
        == sha256_file(sampling_manifest),
        "SHA-256",
    )
    check(
        "reserve manifest hash",
        preflight["private_artifacts"]["reserve_manifest"]["sha256"]
        == sha256_file(reserve_manifest),
        "SHA-256",
    )
    check(
        "private file modes",
        stat.S_IMODE(sampling_manifest.stat().st_mode) == 0o600
        and stat.S_IMODE(reserve_manifest.stat().st_mode) == 0o600,
        "mode=0600",
    )
    check(
        "private artifacts gitignored",
        is_gitignored(args.repo_root.resolve(), sampling_manifest)
        and is_gitignored(args.repo_root.resolve(), reserve_manifest),
        "git check-ignore",
    )
    check(
        "repeat manifest deferred",
        not repeat_manifest.exists(),
        "not created before replacements",
    )

    preflight_privacy_violations = public_payload_violations(preflight)
    check(
        "preflight public payload privacy",
        not preflight_privacy_violations,
        f"violations={len(preflight_privacy_violations)}",
    )
    privacy_claims = preflight.get("privacy", {})
    check(
        "preflight privacy claims",
        all(
            privacy_claims.get(key) is False
            for key in (
                "forum_text_emitted",
                "presented_quote_or_response_retained",
                "source_ids_emitted",
                "hmac_ids_emitted_in_public_report",
                "per_sample_labels_emitted",
                "external_services_used",
            )
        ),
        "all emission/service flags false",
    )

    result: dict[str, object] = {
        "schema_version": "1",
        "protocol_id": PROTOCOL_ID,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if not mismatches else "failed",
        "inputs": {
            "source_filename": args.source.name,
            "source_sha256": input_hashes["source_dump"],
            "cleaning_database_filename": args.cleaning_db.name,
            "cleaning_database_sha256": input_hashes["cleaning_database"],
            "dedup_database_filename": args.dedup_db.name,
            "dedup_database_sha256": input_hashes["dedup_database"],
            "sampling_protocol_filename": args.sampling_protocol.name,
            "sampling_protocol_sha256": sha256_file(args.sampling_protocol),
            "label_protocol_filename": args.label_protocol.name,
            "label_protocol_sha256": input_hashes["label_protocol"],
            "preflight_report_filename": args.preflight_report.name,
            "preflight_report_sha256": sha256_file(args.preflight_report),
            "sampling_manifest_filename": sampling_manifest.name,
            "sampling_manifest_sha256": sha256_file(sampling_manifest),
            "reserve_manifest_filename": reserve_manifest.name,
            "reserve_manifest_sha256": sha256_file(reserve_manifest),
            "verification_script_sha256": sha256_file(Path(__file__)),
        },
        "aggregate": {
            "candidate_rows": len(candidates),
            "primary_rows": len(primary_records),
            "reserve_rows": len(reserve_records),
            "unique_threads": len(set(manifest_threads)),
            "non_null_review_cluster_rows": len(manifest_clusters),
        },
        "checks": checks,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "public_payload_violations": preflight_privacy_violations,
        "privacy": {
            "forum_text_emitted": False,
            "source_or_hmac_ids_emitted": False,
            "per_sample_records_emitted": False,
            "external_services_used": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    temporary.write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, args.output)
    return result


def main() -> None:
    result = verify(parse_args())
    print(
        json.dumps(
            {
                "status": result["status"],
                "checks": len(result["checks"]),
                "mismatch_count": result["mismatch_count"],
            },
            sort_keys=True,
        )
    )
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
