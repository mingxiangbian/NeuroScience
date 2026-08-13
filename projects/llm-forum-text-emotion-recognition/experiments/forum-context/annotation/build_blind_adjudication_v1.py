#!/usr/bin/env python3
"""Build the frozen 40-case source-blind diagnostic adjudication bundle."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from blind_adjudicator.core import (
    CANDIDATE_ALIASES,
    CASE_SCHEMA_VERSION,
    PROTOCOL_ID,
    canonical_case_sha256,
)
from compare_three_sources_v1 import (
    SOURCES,
    build_rows,
    exact_key,
    public_violations,
    read_object,
    sha256_file,
    validate_model_hashes,
    write_json,
    write_jsonl,
)


SELECTION_SEED = "f3b9b141f728d436b42e8fd8464c3c46"
EXPECTED_ROWS = 120
EXPECTED_SELECTED = 40
EXPECTED_HUMAN_CHECKPOINT_SHA256 = (
    "5e03ebbef49ae558db6b6ce426aaf95d3e819949431f4132762868da631ff03a"
)
EXPECTED_DISAGREEMENT_SHA256 = (
    "b85136c226e5e82db43cfaaef2734f0b13e9e7271fde6cdf1c56abe83289720f"
)
BOUNDARY_KEYS = {"anger", "frustration", "neutral", "unclear", "cynicism"}
STRATA: tuple[tuple[str, int, Callable[[dict[str, Any]], bool]], ...] = (
    (
        "stance_candidate",
        15,
        lambda row: exact_key(row["stage_b"]["human"])
        in {"other_emotion:approval", "other_emotion:disapproval"}
        and len({exact_key(row["stage_b"][source]) for source in SOURCES}) > 1,
    ),
    (
        "all_three_different",
        10,
        lambda row: len(
            {exact_key(row["stage_b"][source]) for source in SOURCES}
        )
        == 3,
    ),
    (
        "model_boundary_conflict",
        8,
        lambda row: exact_key(row["stage_b"]["model_01"])
        != exact_key(row["stage_b"]["model_02"])
        and exact_key(row["stage_b"]["model_01"]) in BOUNDARY_KEYS
        and exact_key(row["stage_b"]["model_02"]) in BOUNDARY_KEYS,
    ),
    (
        "human_context_shift",
        5,
        lambda row: exact_key(row["stage_a"]["human"])
        != exact_key(row["stage_b"]["human"]),
    ),
    (
        "all_three_equal_control",
        2,
        lambda row: len(
            {exact_key(row["stage_b"][source]) for source in SOURCES}
        )
        == 1,
    ),
)


def parse_args() -> argparse.Namespace:
    annotation_dir = Path(__file__).resolve().parent
    project_root = annotation_dir.parents[2]
    private_root = project_root / "data/iac2/annotations/pilot-v1"
    parser = argparse.ArgumentParser(
        description="Build DATA-FCTX-ADJ-DIAG-V1 without exposing source identities."
    )
    parser.add_argument("--private-root", type=Path, default=private_root)
    parser.add_argument(
        "--seal-report",
        type=Path,
        default=annotation_dir / "reports/model-output-seal-v1.json",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=private_root / "adjudication/diagnostic-v1",
    )
    parser.add_argument(
        "--public-report",
        type=Path,
        default=annotation_dir / "reports/blind-adjudication-bundle-v1.json",
    )
    return parser.parse_args()


def stable_rank(seed: str, domain: str, value: str) -> str:
    return hashlib.sha256(f"{seed}|{domain}|{value}".encode("utf-8")).hexdigest()


def select_rows(
    rows: list[dict[str, Any]], seed: str = SELECTION_SEED
) -> list[dict[str, Any]]:
    if len(rows) != EXPECTED_ROWS:
        raise ValueError(f"expected {EXPECTED_ROWS} aligned rows")
    selected_uids: set[str] = set()
    selected: list[dict[str, Any]] = []

    for stratum, quota, eligible in STRATA:
        pool = [
            row
            for row in rows
            if row["sample_uid"] not in selected_uids and eligible(row)
        ]
        pool.sort(
            key=lambda row: stable_rank(
                seed,
                f"select|{stratum}",
                row["sample_uid"],
            )
        )
        if len(pool) < quota:
            raise ValueError(
                f"stratum {stratum} has {len(pool)} eligible cases after exclusion; "
                f"requires {quota}"
            )
        for row in pool[:quota]:
            selected_uids.add(row["sample_uid"])
            selected.append(
                {
                    "stratum": stratum,
                    "selection_rank": stable_rank(
                        seed,
                        f"select|{stratum}",
                        row["sample_uid"],
                    ),
                    "presentation_rank": stable_rank(
                        seed, "present", row["sample_uid"]
                    ),
                    "row": row,
                }
            )

    if len(selected) != EXPECTED_SELECTED or len(selected_uids) != EXPECTED_SELECTED:
        raise ValueError("selection did not produce 40 unique cases")
    selected.sort(key=lambda item: item["presentation_rank"])
    return selected


def balanced_source_permutations(
    seed: str = SELECTION_SEED,
) -> list[tuple[str, str, str]]:
    source_permutations = list(itertools.permutations(SOURCES))
    valid_schedules: list[tuple[tuple[str, str, str], ...]] = []
    for schedule in itertools.permutations(source_permutations):
        prefix_counts = {
            alias: Counter() for alias in CANDIDATE_ALIASES
        }
        for source_order in schedule[:4]:
            for alias, source in zip(CANDIDATE_ALIASES, source_order, strict=True):
                prefix_counts[alias][source] += 1
        if all(
            prefix_counts[alias][source] in {1, 2}
            for alias in CANDIDATE_ALIASES
            for source in SOURCES
        ):
            valid_schedules.append(schedule)
    if not valid_schedules:
        raise ValueError("no balanced source permutation schedule exists")
    valid_schedules.sort(
        key=lambda schedule: stable_rank(
            seed,
            "schedule",
            ";".join(",".join(values) for values in schedule),
        )
    )
    return list(valid_schedules[0])


def compact_decision(decision: Mapping[str, Any]) -> dict[str, Any]:
    status = decision["status"]
    primary = decision["primary_emotion"] if status == "labeled" else None
    other: str | None = None
    if status == "labeled" and primary == "other_emotion":
        raw = decision["other_emotion_text"]
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("other_emotion decision has no proposal")
        other = " ".join(raw.casefold().split())
    return {
        "status": status,
        "primary_emotion": primary,
        "other_emotion_text": other,
    }


def canonical_view_sha256(view: dict[str, Any]) -> str:
    encoded = json.dumps(
        view,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_verified_view(private_root: Path, row: Mapping[str, Any]) -> dict[str, Any]:
    path = private_root / "views" / f"{row['annotation_order']:04d}.json"
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"private view unavailable for order {row['annotation_order']}")
    view = read_object(path)
    if canonical_view_sha256(view) != row["view_sha256"]:
        raise ValueError(f"view hash mismatch for order {row['annotation_order']}")
    ids = view.get("ids")
    if not isinstance(ids, dict) or ids.get("sample_uid") != row["sample_uid"]:
        raise ValueError(f"view identity mismatch for order {row['annotation_order']}")
    return view


def view_content(view: Mapping[str, Any]) -> dict[str, Any]:
    context = view["context"]
    target = view["target"]
    quote_texts: list[str] = []
    for quote in context["target_quotes"]:
        if not isinstance(quote, dict) or not isinstance(quote.get("text"), str):
            raise ValueError("target quote does not contain text")
        quote_texts.append(quote["text"])
    return {
        "discussion_title": context["discussion_title"],
        "direct_parent_body": context["direct_parent_body"],
        "target_quotes": quote_texts,
        "target_full_with_quotes": target["full_with_quotes"],
    }


def build_private_rows(
    private_root: Path,
    selected: list[dict[str, Any]],
    seed: str = SELECTION_SEED,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    permutations = balanced_source_permutations(seed)
    bundle_rows: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []

    for position, item in enumerate(selected, 1):
        row = item["row"]
        blind_case_id = f"{position:03d}"
        source_order = permutations[(position - 1) % len(permutations)]
        alias_to_source = dict(zip(CANDIDATE_ALIASES, source_order, strict=True))
        view = load_verified_view(private_root, row)
        case: dict[str, Any] = {
            "schema_version": CASE_SCHEMA_VERSION,
            "protocol_id": PROTOCOL_ID,
            "blind_case_id": blind_case_id,
            "content": view_content(view),
            "candidates": [
                {
                    "alias": alias,
                    "decision": compact_decision(
                        row["stage_b"][alias_to_source[alias]]
                    ),
                }
                for alias in CANDIDATE_ALIASES
            ],
        }
        case["case_sha256"] = canonical_case_sha256(case)
        bundle_rows.append(case)
        mapping_rows.append(
            {
                "schema_version": "source-blind-adjudication-map-v1",
                "protocol_id": PROTOCOL_ID,
                "blind_case_id": blind_case_id,
                "case_sha256": case["case_sha256"],
                "sample_uid": row["sample_uid"],
                "view_sha256": row["view_sha256"],
                "annotation_order": row["annotation_order"],
                "lane": row["lane"],
                "stratum": item["stratum"],
                "selection_rank": item["selection_rank"],
                "presentation_rank": item["presentation_rank"],
                "alias_to_source": alias_to_source,
            }
        )
    return bundle_rows, mapping_rows


def source_position_counts(mapping_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    counts: dict[str, Counter[str]] = {
        alias: Counter() for alias in CANDIDATE_ALIASES
    }
    for row in mapping_rows:
        for alias, source in row["alias_to_source"].items():
            counts[alias][source] += 1
    result = {
        alias: dict(sorted(source_counts.items()))
        for alias, source_counts in counts.items()
    }
    for source in SOURCES:
        positions = [counts[alias][source] for alias in CANDIDATE_ALIASES]
        if max(positions) - min(positions) > 1:
            raise ValueError(f"candidate positions are not balanced for {source}")
    return result


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def ensure_new_outputs(paths: Iterable[Path]) -> None:
    existing = [path for path in paths if path.exists()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite frozen adjudication outputs: "
            + ", ".join(path.name for path in existing)
        )


def main() -> int:
    args = parse_args()
    private_root = args.private_root.resolve()
    output_root = args.output_root.resolve()
    bundle_path = output_root / "bundle.jsonl"
    source_map_path = output_root / "source-map.jsonl"
    private_manifest_path = output_root / "manifest.json"
    records_dir = output_root / "records"
    public_report_path = args.public_report.resolve()

    ensure_new_outputs(
        (bundle_path, source_map_path, private_manifest_path, public_report_path)
    )
    checkpoint_path = (
        private_root
        / "checkpoints/human-pass-1-complete_20260807T194808+0800.tar.gz"
    )
    disagreement_path = (
        private_root
        / "comparisons/three-source-v1/three-source-disagreements-v1.jsonl"
    )
    if sha256_file(checkpoint_path) != EXPECTED_HUMAN_CHECKPOINT_SHA256:
        raise ValueError("Human Pass 1 checkpoint hash mismatch")
    if sha256_file(disagreement_path) != EXPECTED_DISAGREEMENT_SHA256:
        raise ValueError("three-source disagreement sidecar hash mismatch")

    seal_report = read_object(args.seal_report)
    model_paths = validate_model_hashes(private_root / "model-outputs", seal_report)
    rows = build_rows(private_root, model_paths)
    selected = select_rows(rows)
    bundle_rows, mapping_rows = build_private_rows(private_root, selected)
    alias_counts = source_position_counts(mapping_rows)

    output_root.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.chmod(output_root, 0o700)
    records_dir.mkdir(mode=0o700)
    os.chmod(records_dir, 0o700)
    write_jsonl(bundle_path, bundle_rows, 0o600)
    write_jsonl(source_map_path, mapping_rows, 0o600)

    stratum_counts = dict(sorted(Counter(item["stratum"] for item in selected).items()))
    private_manifest = {
        "schema_version": "source-blind-adjudication-manifest-v1",
        "protocol_id": PROTOCOL_ID,
        "generated_at_utc": utc_now(),
        "selection_seed": SELECTION_SEED,
        "selected_cases": len(bundle_rows),
        "stratum_counts": stratum_counts,
        "source_position_counts": alias_counts,
        "inputs": {
            "human_checkpoint_sha256": sha256_file(checkpoint_path),
            "three_source_disagreement_sha256": sha256_file(disagreement_path),
            "model_outputs": {
                f"{model}_{stage}": {
                    "filename": path.name,
                    "sha256": sha256_file(path),
                }
                for (model, stage), path in sorted(model_paths.items())
            },
        },
        "outputs": {
            "bundle": {
                "filename": bundle_path.name,
                "rows": len(bundle_rows),
                "sha256": sha256_file(bundle_path),
            },
            "source_map": {
                "filename": source_map_path.name,
                "rows": len(mapping_rows),
                "sha256": sha256_file(source_map_path),
            },
            "records_directory": records_dir.name,
        },
        "source_unblinded": False,
    }
    write_json(private_manifest_path, private_manifest, 0o600)

    public_report = {
        "schema_version": "source-blind-adjudication-bundle-report-v1",
        "protocol_id": PROTOCOL_ID,
        "generated_at_utc": private_manifest["generated_at_utc"],
        "status": "prepared_not_adjudicated",
        "selection": {
            "seed": SELECTION_SEED,
            "cases": len(bundle_rows),
            "unique_cases": len({row["case_sha256"] for row in bundle_rows}),
            "stratum_counts": stratum_counts,
            "source_positions_balanced_to_within_one": True,
        },
        "input_verification": {
            "human_checkpoint_hash": "passed",
            "model_output_seal_hashes": "passed",
            "three_source_row_alignment": "passed",
            "private_view_hashes": "passed",
            "disagreement_sidecar_hash": "passed",
        },
        "private_outputs": {
            "bundle": {
                "filename": bundle_path.name,
                "rows": len(bundle_rows),
                "sha256": sha256_file(bundle_path),
                "contains_forum_text": True,
                "gitignored_required": True,
            },
            "source_map": {
                "filename": source_map_path.name,
                "rows": len(mapping_rows),
                "sha256": sha256_file(source_map_path),
                "contains_source_mapping": True,
                "gitignored_required": True,
            },
            "manifest": {
                "filename": private_manifest_path.name,
                "sha256": sha256_file(private_manifest_path),
                "gitignored_required": True,
            },
        },
        "privacy": {
            "forum_text_emitted": False,
            "private_identifiers_emitted": False,
            "per_case_source_mapping_emitted": False,
            "per_case_labels_emitted": False,
        },
        "claim_boundary": {
            "creates_formal_gold": False,
            "is_independent_reannotation": False,
            "supports_inter_annotator_agreement": False,
            "source_unblinded": False,
        },
    }
    violations = public_violations(public_report)
    if violations:
        raise ValueError(f"public report privacy violations: {violations}")
    write_json(public_report_path, public_report, 0o644)
    print(
        json.dumps(
            {
                "public_report": str(public_report_path),
                "private_output_root": str(output_root),
                "selected_cases": len(bundle_rows),
                "source_positions_balanced": True,
                "privacy_violations": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
