#!/usr/bin/env python3
"""Run the metadata-only DATA-FCTX-SAMPLE-V1 sampling preflight."""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from sampling_common import (
    PRIMARY_LANES,
    PROTOCOL_ID,
    RESERVE_LANES,
    SEED,
    Candidate,
    load_candidates,
    load_weak_metadata,
    predicate_for_lane,
    rank_digest,
    sha256_file,
    summarize_candidates,
    verify_frozen_hashes,
)


SCHEMA_VERSION = "1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--cleaning-db", type=Path, required=True)
    parser.add_argument("--dedup-db", type=Path, required=True)
    parser.add_argument("--sampling-protocol", type=Path, required=True)
    parser.add_argument("--label-protocol", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


@dataclass
class SelectionState:
    sample_uids: set[str] = field(default_factory=set)
    thread_uids: set[str] = field(default_factory=set)
    review_cluster_uids: set[str] = field(default_factory=set)

    def conflict(self, candidate: Candidate) -> str | None:
        if candidate.sample_uid in self.sample_uids:
            return "sample"
        if candidate.thread_uid in self.thread_uids:
            return "thread"
        cluster = candidate.review_cluster_uid
        if cluster is not None and cluster in self.review_cluster_uids:
            return "review_cluster"
        return None

    def add(self, candidate: Candidate) -> None:
        self.sample_uids.add(candidate.sample_uid)
        self.thread_uids.add(candidate.thread_uid)
        if candidate.review_cluster_uid is not None:
            self.review_cluster_uids.add(candidate.review_cluster_uid)


@dataclass(frozen=True)
class Picked:
    role: str
    lane: str
    lane_position: int
    rank_lane: str
    candidate: Candidate


def select_lane(
    candidates: Sequence[Candidate],
    *,
    role: str,
    lane: str,
    rank_lane: str,
    quota: int,
    predicate: Callable[[Candidate], bool],
    state: SelectionState,
) -> tuple[list[Picked], dict[str, object]]:
    eligible = [candidate for candidate in candidates if predicate(candidate)]
    eligible.sort(key=lambda candidate: rank_digest(rank_lane, candidate.sample_uid))
    conflicts: Counter[str] = Counter()
    examined = 0
    selected: list[Picked] = []
    for candidate in eligible:
        examined += 1
        conflict = state.conflict(candidate)
        if conflict is not None:
            conflicts[conflict] += 1
            continue
        state.add(candidate)
        selected.append(
            Picked(
                role=role,
                lane=lane,
                lane_position=len(selected) + 1,
                rank_lane=rank_lane,
                candidate=candidate,
            )
        )
        if len(selected) == quota:
            break
    audit = {
        "quota": quota,
        "qualifying_candidates": len(eligible),
        "ranked_candidates_examined": examined,
        "selected": len(selected),
        "conflicts_before_quota": dict(sorted(conflicts.items())),
        "status": "passed" if len(selected) == quota else "blocked",
    }
    return selected, audit


def manifest_record(picked: Picked, annotation_order: int | None) -> dict[str, object]:
    candidate = picked.candidate
    return {
        "schema_version": SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "role": picked.role,
        "lane": picked.lane,
        "lane_position": picked.lane_position,
        "sample_uid": candidate.sample_uid,
        "thread_uid": candidate.thread_uid,
        "review_cluster_uid": candidate.review_cluster_uid,
        "selection_rank_sha256": rank_digest(
            picked.rank_lane, candidate.sample_uid
        ),
        "annotation_order": annotation_order,
    }


def _write_private_jsonl(path: Path, records: Sequence[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def _write_public_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _is_gitignored(repo_root: Path, path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(path.resolve())],
        cwd=repo_root,
        check=False,
    )
    return result.returncode == 0


def _mode(path: Path) -> str:
    return oct(stat.S_IMODE(path.stat().st_mode))


def run(args: argparse.Namespace) -> dict[str, object]:
    report_path = args.report.resolve()
    private_dir = args.private_dir.resolve()
    sampling_manifest = private_dir / "sampling-manifest.jsonl"
    reserve_manifest = private_dir / "reserve-manifest.jsonl"
    repeat_manifest = private_dir / "repeat-manifest.jsonl"

    for output in (sampling_manifest, reserve_manifest):
        if output.exists() and not args.replace:
            raise FileExistsError(f"private output already exists: {output.name}")
    if repeat_manifest.exists():
        raise FileExistsError(
            "repeat manifest already exists; repeats are deferred until replacements finish"
        )
    if not _is_gitignored(args.repo_root.resolve(), sampling_manifest):
        raise ValueError("private sampling manifest is not gitignored")
    if not _is_gitignored(args.repo_root.resolve(), reserve_manifest):
        raise ValueError("private reserve manifest is not gitignored")

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

    pool_capacities = {
        lane: sum(predicate_for_lane(lane)(candidate) for candidate in candidates)
        for lane, _ in PRIMARY_LANES
    }
    state = SelectionState()
    primary: list[Picked] = []
    primary_audits: dict[str, object] = {}
    blocked_reasons: list[str] = []

    for lane, quota in PRIMARY_LANES:
        selected, audit = select_lane(
            candidates,
            role="primary",
            lane=lane,
            rank_lane=lane,
            quota=quota,
            predicate=predicate_for_lane(lane),
            state=state,
        )
        primary.extend(selected)
        primary_audits[lane] = audit
        if audit["status"] != "passed":
            blocked_reasons.append(f"primary lane {lane} did not meet quota")
            break

    reserves: list[Picked] = []
    reserve_audits: dict[str, object] = {}
    if not blocked_reasons:
        for lane, quota in RESERVE_LANES:
            rank_lane = f"{lane}_reserve"
            selected, audit = select_lane(
                candidates,
                role="reserve",
                lane=lane,
                rank_lane=rank_lane,
                quota=quota,
                predicate=predicate_for_lane(lane),
                state=state,
            )
            reserves.extend(selected)
            reserve_audits[lane] = audit
            if audit["status"] != "passed":
                blocked_reasons.append(f"reserve lane {lane} did not meet quota")
                break

    if candidate_build["candidate_rows"] != 403183:
        blocked_reasons.append("candidate frame does not contain 403183 rows")
    if candidate_build["unreconstructible_rows"] != 0:
        blocked_reasons.append("candidate frame contains unreconstructible views")
    if candidate_build["short_flag_mismatches"] != 0:
        blocked_reasons.append("target_short flag differs from frozen word-count rule")
    if len(primary) != 120:
        blocked_reasons.append("primary selection does not contain 120 rows")
    if len(reserves) != 60:
        blocked_reasons.append("reserve selection does not contain 60 rows")

    status_value = "passed" if not blocked_reasons else "blocked"
    private_artifacts: dict[str, object] = {
        "sampling_manifest": None,
        "reserve_manifest": None,
        "repeat_manifest": {
            "status": "deferred_until_120_analyzable_cases",
            "planned_rows": 24,
        },
    }

    selected_characteristics = {
        lane: summarize_candidates(
            [picked.candidate for picked in primary if picked.lane == lane]
        )
        for lane, _ in PRIMARY_LANES
    }

    if status_value == "passed":
        ordered_primary = sorted(
            primary,
            key=lambda picked: rank_digest(
                "annotation_order", picked.candidate.sample_uid
            ),
        )
        annotation_positions = {
            picked.candidate.sample_uid: index
            for index, picked in enumerate(ordered_primary, start=1)
        }
        primary_records = [
            manifest_record(
                picked, annotation_positions[picked.candidate.sample_uid]
            )
            for picked in ordered_primary
        ]
        reserve_records = [manifest_record(picked, None) for picked in reserves]
        _write_private_jsonl(sampling_manifest, primary_records)
        _write_private_jsonl(reserve_manifest, reserve_records)
        private_artifacts = {
            "sampling_manifest": {
                "filename": sampling_manifest.name,
                "rows": len(primary_records),
                "sha256": sha256_file(sampling_manifest),
                "mode": _mode(sampling_manifest),
                "gitignored": _is_gitignored(args.repo_root.resolve(), sampling_manifest),
            },
            "reserve_manifest": {
                "filename": reserve_manifest.name,
                "rows": len(reserve_records),
                "sha256": sha256_file(reserve_manifest),
                "mode": _mode(reserve_manifest),
                "gitignored": _is_gitignored(args.repo_root.resolve(), reserve_manifest),
            },
            "repeat_manifest": {
                "status": "deferred_until_120_analyzable_cases",
                "planned_rows": 24,
            },
        }

    all_unique = primary + reserves
    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status_value,
        "blocked_reasons": blocked_reasons,
        "inputs": {
            "source": {
                "filename": args.source.name,
                "sha256": input_hashes["source_dump"],
            },
            "cleaning_database": {
                "filename": args.cleaning_db.name,
                "sha256": input_hashes["cleaning_database"],
            },
            "dedup_database": {
                "filename": args.dedup_db.name,
                "sha256": input_hashes["dedup_database"],
            },
            "sampling_protocol": {
                "filename": args.sampling_protocol.name,
                "sha256": sha256_file(args.sampling_protocol),
            },
            "label_protocol": {
                "filename": args.label_protocol.name,
                "sha256": input_hashes["label_protocol"],
            },
        },
        "implementation": {
            "script": Path(__file__).name,
            "script_sha256": sha256_file(Path(__file__)),
            "common_module": "sampling_common.py",
            "common_module_sha256": sha256_file(Path(__file__).with_name("sampling_common.py")),
            "seed": SEED,
            "rank_formula": "SHA256(protocol_id\\nseed\\nlane\\nsample_uid)",
        },
        "candidate_frame": {
            **candidate_build,
            "characteristics": summarize_candidates(candidates),
            "diagnostic_pool_capacities": pool_capacities,
        },
        "weak_metadata": dict(weak.stats),
        "selection": {
            "primary": primary_audits,
            "reserves": reserve_audits,
            "primary_rows": len(primary),
            "reserve_rows": len(reserves),
            "unique_samples_across_primary_and_reserve": len(
                {picked.candidate.sample_uid for picked in all_unique}
            ),
            "unique_threads_across_primary_and_reserve": len(
                {picked.candidate.thread_uid for picked in all_unique}
            ),
            "non_null_review_cluster_rows": sum(
                picked.candidate.review_cluster_uid is not None
                for picked in all_unique
            ),
            "unique_non_null_review_clusters": len(
                {
                    picked.candidate.review_cluster_uid
                    for picked in all_unique
                    if picked.candidate.review_cluster_uid is not None
                }
            ),
            "selected_characteristics_by_primary_lane": selected_characteristics,
        },
        "blind_repeat_plan": {
            "status": "deferred_until_after_unusable_replacements",
            "representative": 16,
            "each_diagnostic_lane": 2,
            "total": 24,
            "minimum_washout_hours": 72,
        },
        "private_artifacts": private_artifacts,
        "privacy": {
            "forum_text_emitted": False,
            "presented_quote_or_response_retained": False,
            "source_ids_emitted": False,
            "hmac_ids_emitted_in_public_report": False,
            "per_sample_labels_emitted": False,
            "external_services_used": False,
        },
    }
    _write_public_json(report_path, report)
    return report


def main() -> None:
    report = run(parse_args())
    print(
        json.dumps(
            {
                "status": report["status"],
                "candidate_rows": report["candidate_frame"]["candidate_rows"],
                "primary_rows": report["selection"]["primary_rows"],
                "reserve_rows": report["selection"]["reserve_rows"],
            },
            sort_keys=True,
        )
    )
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
