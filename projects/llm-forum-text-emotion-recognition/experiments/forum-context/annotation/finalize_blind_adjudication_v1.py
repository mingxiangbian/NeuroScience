#!/usr/bin/env python3
"""Seal the completed blind adjudication and publish aggregate diagnostics."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import tarfile
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from blind_adjudicator.core import (
    CANDIDATE_ALIASES,
    DEFAULT_ADJUDICATOR_UID,
    DEFAULT_SESSION_LIMIT,
    PROTOCOL_ID,
    BlindAdjudicationStore,
)


EXPECTED_CASES = 40
SOURCES = ("human", "model_01", "model_02")
MAP_SCHEMA_VERSION = "source-blind-adjudication-map-v1"
MAP_FIELDS = {
    "schema_version",
    "protocol_id",
    "blind_case_id",
    "case_sha256",
    "annotation_order",
    "sample_uid",
    "view_sha256",
    "lane",
    "stratum",
    "selection_rank",
    "presentation_rank",
    "alias_to_source",
}
STRATUM_ORDER = (
    "stance_candidate",
    "all_three_different",
    "model_boundary_conflict",
    "human_context_shift",
    "all_three_equal_control",
)
FORBIDDEN_PUBLIC_KEYS = {
    "annotation_order",
    "blind_case_id",
    "case_sha256",
    "content",
    "direct_parent_body",
    "discussion_title",
    "lane",
    "note",
    "presentation_rank",
    "sample_uid",
    "selection_rank",
    "target_full_with_quotes",
    "target_quotes",
    "view_sha256",
    "alias_to_source",
}


def parse_args() -> argparse.Namespace:
    annotation_dir = Path(__file__).resolve().parent
    project_root = annotation_dir.parents[2]
    pilot_root = project_root / "data/iac2/annotations/pilot-v1"
    diagnostic_root = pilot_root / "adjudication/diagnostic-v1"
    parser = argparse.ArgumentParser(
        description="Finalize DATA-FCTX-ADJ-DIAG-V1 after all 40 cases are locked."
    )
    parser.add_argument("--diagnostic-root", type=Path, default=diagnostic_root)
    parser.add_argument(
        "--bundle-report",
        type=Path,
        default=annotation_dir / "reports/blind-adjudication-bundle-v1.json",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=pilot_root
        / "checkpoints/blind-adjudication-diagnostic-v1-complete.tar.gz",
    )
    parser.add_argument(
        "--private-seal",
        type=Path,
        default=pilot_root
        / "checkpoints/blind-adjudication-diagnostic-v1-seal.json",
    )
    parser.add_argument(
        "--public-json",
        type=Path,
        default=annotation_dir / "reports/blind-adjudication-results-v1.json",
    )
    parser.add_argument(
        "--public-markdown",
        type=Path,
        default=annotation_dir / "reports/blind-adjudication-results-v1.md",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected an object in {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            raise ValueError(f"blank row in {path.name}:{line_number}")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"non-object row in {path.name}:{line_number}")
        rows.append(value)
    return rows


def write_bytes_once(path: Path, value: bytes, mode: int) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        os.chmod(path, mode)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def write_json_once(path: Path, value: object, mode: int) -> None:
    encoded = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True).encode(
        "utf-8"
    ) + b"\n"
    write_bytes_once(path, encoded, mode)


def decision_key(decision: Mapping[str, Any]) -> str:
    status = str(decision["status"])
    if status != "labeled":
        return status
    emotion = str(decision["primary_emotion"])
    if emotion == "other_emotion":
        other = decision.get("other_emotion_text")
        if not isinstance(other, str) or not other.strip():
            raise ValueError("other_emotion decision has no atomic name")
        return f"other_emotion:{' '.join(other.casefold().split())}"
    return emotion


def rate(count: int, total: int) -> float:
    return round(count / total, 6) if total else 0.0


def sorted_counts(counter: Mapping[str, int]) -> dict[str, int]:
    return {key: int(counter[key]) for key in sorted(counter)}


def load_complete_rows(
    diagnostic_root: Path,
    bundle_report_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    bundle_path = diagnostic_root / "bundle.jsonl"
    source_map_path = diagnostic_root / "source-map.jsonl"
    manifest_path = diagnostic_root / "manifest.json"
    records_dir = diagnostic_root / "records"
    session_log_path = records_dir / "session-log.jsonl"
    required = (
        bundle_path,
        source_map_path,
        manifest_path,
        records_dir,
        session_log_path,
        bundle_report_path,
    )
    for path in required:
        if not path.exists() or path.is_symlink():
            raise ValueError(f"required private input is unavailable: {path}")

    bundle = read_jsonl(bundle_path)
    source_map = read_jsonl(source_map_path)
    manifest = read_json(manifest_path)
    bundle_report = read_json(bundle_report_path)
    if len(bundle) != EXPECTED_CASES or len(source_map) != EXPECTED_CASES:
        raise ValueError("blind bundle and source map must each contain 40 rows")
    if manifest.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("manifest protocol mismatch")
    if manifest.get("selected_cases") != EXPECTED_CASES:
        raise ValueError("manifest selected-case count mismatch")
    if manifest.get("outputs", {}).get("bundle", {}).get("sha256") != sha256_file(
        bundle_path
    ):
        raise ValueError("bundle hash does not match manifest")
    if manifest.get("outputs", {}).get("source_map", {}).get(
        "sha256"
    ) != sha256_file(source_map_path):
        raise ValueError("source-map hash does not match manifest")
    if bundle_report.get("status") != "prepared_not_adjudicated":
        raise ValueError("bundle report status is not the frozen prepared state")

    validator = object.__new__(BlindAdjudicationStore)
    validator.adjudicator_uid = DEFAULT_ADJUDICATOR_UID
    joined: list[dict[str, Any]] = []
    record_hashes: list[dict[str, str]] = []
    for index, (case, mapping) in enumerate(zip(bundle, source_map, strict=True), 1):
        expected_id = f"{index:03d}"
        validator._validate_case(case, index)
        if case["blind_case_id"] != expected_id:
            raise ValueError("bundle case IDs are not contiguous")
        if set(mapping) != MAP_FIELDS:
            raise ValueError(f"source-map fields mismatch for case {expected_id}")
        if mapping["schema_version"] != MAP_SCHEMA_VERSION:
            raise ValueError(f"source-map schema mismatch for case {expected_id}")
        if mapping["protocol_id"] != PROTOCOL_ID:
            raise ValueError(f"source-map protocol mismatch for case {expected_id}")
        if mapping["blind_case_id"] != expected_id:
            raise ValueError(f"source-map order mismatch for case {expected_id}")
        if mapping["case_sha256"] != case["case_sha256"]:
            raise ValueError(f"source-map case hash mismatch for case {expected_id}")
        aliases = mapping["alias_to_source"]
        if not isinstance(aliases, dict) or tuple(aliases) != CANDIDATE_ALIASES:
            raise ValueError(f"source aliases mismatch for case {expected_id}")
        if set(aliases.values()) != set(SOURCES):
            raise ValueError(f"source permutation mismatch for case {expected_id}")
        if mapping["stratum"] not in STRATUM_ORDER:
            raise ValueError(f"unknown stratum for case {expected_id}")

        record_path = records_dir / f"{expected_id}.json"
        if not record_path.is_file() or record_path.is_symlink():
            raise ValueError(f"missing adjudication record {expected_id}")
        record = read_json(record_path)
        validator._validate_record(record, case)
        if record["phase_1"] is None or record["phase_2"] is None:
            raise ValueError(f"incomplete adjudication record {expected_id}")
        if record["completed_at"] is None:
            raise ValueError(f"record {expected_id} has no completion timestamp")
        record_hashes.append(
            {"blind_case_id": expected_id, "sha256": sha256_file(record_path)}
        )
        joined.append({"case": case, "mapping": mapping, "record": record})

    unexpected = sorted(
        path.name
        for path in records_dir.glob("*.json")
        if path.stem not in {f"{index:03d}" for index in range(1, 41)}
    )
    if unexpected:
        raise ValueError(f"unexpected adjudication records: {', '.join(unexpected)}")

    session = validate_session_log(read_jsonl(session_log_path))
    composite = sha256_bytes(
        b"".join(
            f"{item['blind_case_id']}\0{item['sha256']}\n".encode("ascii")
            for item in record_hashes
        )
    )
    verification = {
        "bundle_sha256": sha256_file(bundle_path),
        "source_map_sha256": sha256_file(source_map_path),
        "manifest_sha256": sha256_file(manifest_path),
        "session_log_sha256": sha256_file(session_log_path),
        "record_hashes": record_hashes,
        "records_composite_sha256": composite,
        "session": session,
    }
    return joined, verification


def validate_session_log(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        raise ValueError("session log is empty")
    completion_by_session: Counter[str] = Counter()
    completed_cases: list[str] = []
    phase_1_cases: list[str] = []
    started_sessions: set[str] = set()
    for event in events:
        if event.get("protocol_id") != PROTOCOL_ID:
            raise ValueError("session event protocol mismatch")
        event_name = event.get("event")
        session_uid = event.get("session_uid")
        if not isinstance(session_uid, str) or not session_uid:
            raise ValueError("session event has no session UID")
        if event_name == "session_started":
            started_sessions.add(session_uid)
        elif event_name == "phase_1_locked":
            phase_1_cases.append(str(event.get("case_id")))
        elif event_name == "case_completed":
            completed_cases.append(str(event.get("case_id")))
            completion_by_session[session_uid] += 1
        elif event_name != "session_ended":
            raise ValueError(f"unknown session event: {event_name!r}")

    expected_ids = {f"{index:03d}" for index in range(1, EXPECTED_CASES + 1)}
    if set(phase_1_cases) != expected_ids or len(phase_1_cases) != EXPECTED_CASES:
        raise ValueError("session log does not contain 40 unique Phase 1 locks")
    if set(completed_cases) != expected_ids or len(completed_cases) != EXPECTED_CASES:
        raise ValueError("session log does not contain 40 unique completions")
    if not set(completion_by_session).issubset(started_sessions):
        raise ValueError("a completion references an unstarted session")
    maximum = max(completion_by_session.values(), default=0)
    if maximum > DEFAULT_SESSION_LIMIT:
        raise ValueError("continuous-session limit was exceeded")
    return {
        "session_count": len(completion_by_session),
        "completed_cases": len(completed_cases),
        "completed_per_session": sorted(completion_by_session.values()),
        "maximum_completed_in_one_session": maximum,
        "session_limit": DEFAULT_SESSION_LIMIT,
        "session_limit_passed": True,
    }


def analyze_rows(rows: list[dict[str, Any]], session: Mapping[str, Any]) -> dict[str, Any]:
    assessments = {source: Counter() for source in SOURCES}
    unsupported_reasons = {source: Counter() for source in SOURCES}
    phase_1_by_stratum: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: {
            "emotion_presence": Counter(),
            "stance": Counter(),
            "unit_validity": Counter(),
        }
    )
    stratum_totals = Counter()
    resolution_counts = Counter()
    final_outcome_statuses = Counter()
    final_cases = 0
    final_unchanged = 0
    final_changed = 0
    control_total = 0
    control_all_favorable = 0
    control_any_unsupported = 0
    control_final_matches = 0
    control_no_stable = 0

    for row in rows:
        case = row["case"]
        mapping = row["mapping"]
        record = row["record"]
        phase_1 = record["phase_1"]
        phase_2 = record["phase_2"]
        stratum = mapping["stratum"]
        stratum_totals[stratum] += 1
        for field in ("emotion_presence", "stance", "unit_validity"):
            phase_1_by_stratum[stratum][field][str(phase_1[field])] += 1

        for alias, assessment in phase_2["candidate_assessments"].items():
            source = mapping["alias_to_source"][alias]
            assessments[source][assessment] += 1
            if assessment == "unsupported":
                unsupported_reasons[source][phase_2["primary_reason"]] += 1

        resolution = phase_2["resolution"]
        resolution_counts[resolution] += 1
        if resolution == "final_decision":
            final_cases += 1
            final_outcome_statuses[phase_2["final_decision"]["status"]] += 1
            if decision_key(phase_1["independent_decision"]) == decision_key(
                phase_2["final_decision"]
            ):
                final_unchanged += 1
            else:
                final_changed += 1
        else:
            final_outcome_statuses["no_stable_gold"] += 1

        if stratum == "all_three_equal_control":
            control_total += 1
            values = list(phase_2["candidate_assessments"].values())
            favorable = {"supported", "acceptable_but_not_primary"}
            if all(value in favorable for value in values):
                control_all_favorable += 1
            if "unsupported" in values:
                control_any_unsupported += 1
            candidate_keys = {
                decision_key(candidate["decision"])
                for candidate in case["candidates"]
            }
            if len(candidate_keys) != 1:
                raise ValueError("all-three-equal control is not actually equal")
            if resolution == "no_stable_gold":
                control_no_stable += 1
            elif decision_key(phase_2["final_decision"]) in candidate_keys:
                control_final_matches += 1

    source_metrics: dict[str, Any] = {}
    reason_metrics: dict[str, Any] = {}
    for source in SOURCES:
        total = sum(assessments[source].values())
        if total != len(rows):
            raise ValueError(f"source {source} does not have one assessment per case")
        strict = assessments[source]["supported"]
        broad = strict + assessments[source]["acceptable_but_not_primary"]
        unsupported = assessments[source]["unsupported"]
        source_metrics[source] = {
            "cases": total,
            "assessment_counts": sorted_counts(assessments[source]),
            "strict_supported_rate": rate(strict, total),
            "supported_or_acceptable_rate": rate(broad, total),
            "unsupported_rate": rate(unsupported, total),
        }
        reason_metrics[source] = sorted_counts(unsupported_reasons[source])

    strata: dict[str, Any] = {}
    for stratum in STRATUM_ORDER:
        strata[stratum] = {
            "cases": stratum_totals[stratum],
            **{
                field: sorted_counts(phase_1_by_stratum[stratum][field])
                for field in ("emotion_presence", "stance", "unit_validity")
            },
        }

    return {
        "candidate_assessment_by_source": source_metrics,
        "unsupported_reason_by_source": reason_metrics,
        "resolution": {
            "counts": sorted_counts(resolution_counts),
            "final_outcome_status_counts": sorted_counts(final_outcome_statuses),
            "no_stable_gold_rate": rate(
                resolution_counts["no_stable_gold"], len(rows)
            ),
        },
        "independent_to_final": {
            "final_decision_cases": final_cases,
            "unchanged": final_unchanged,
            "changed": final_changed,
            "changed_rate_among_final_decisions": rate(final_changed, final_cases),
        },
        "phase_1_diagnosis_by_frozen_stratum": strata,
        "all_three_equal_controls": {
            "cases": control_total,
            "all_candidates_supported_or_acceptable": control_all_favorable,
            "any_candidate_unsupported": control_any_unsupported,
            "final_matches_unanimous_candidate": control_final_matches,
            "no_stable_gold": control_no_stable,
        },
        "session_discipline": dict(session),
    }


def public_violations(value: object, path: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_PUBLIC_KEYS:
                violations.append(f"{path}.{key}: forbidden public key")
            violations.extend(public_violations(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(public_violations(child, f"{path}[{index}]"))
    return violations


def checkpoint_members(diagnostic_root: Path) -> list[Path]:
    members = [
        diagnostic_root / "bundle.jsonl",
        diagnostic_root / "manifest.json",
        diagnostic_root / "source-map.jsonl",
    ]
    members.extend(sorted((diagnostic_root / "records").glob("*.json")))
    members.append(diagnostic_root / "records/session-log.jsonl")
    if len(members) != EXPECTED_CASES + 4:
        raise ValueError("checkpoint member count is not 44")
    if any(not path.is_file() or path.is_symlink() for path in members):
        raise ValueError("checkpoint contains a missing file or symlink")
    return members


def create_deterministic_checkpoint(
    diagnostic_root: Path,
    output_path: Path,
) -> None:
    members = checkpoint_members(diagnostic_root)
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(output_path.parent, 0o700)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    try:
        with temporary.open("wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as zipped:
                with tarfile.open(fileobj=zipped, mode="w") as archive:
                    for path in members:
                        data = path.read_bytes()
                        info = tarfile.TarInfo(path.relative_to(diagnostic_root).as_posix())
                        info.size = len(data)
                        info.mode = 0o400
                        info.mtime = 0
                        info.uid = 0
                        info.gid = 0
                        info.uname = ""
                        info.gname = ""
                        archive.addfile(info, fileobj=io.BytesIO(data))
            raw.flush()
            os.fsync(raw.fileno())
        os.chmod(temporary, 0o400)
        os.replace(temporary, output_path)
        os.chmod(output_path, 0o400)
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise

def seal_private_tree(diagnostic_root: Path) -> None:
    for path in checkpoint_members(diagnostic_root):
        os.chmod(path, 0o400)
    os.chmod(diagnostic_root / "records", 0o500)
    os.chmod(diagnostic_root, 0o500)


def markdown_report(report: Mapping[str, Any]) -> str:
    analysis = report["analysis"]
    lines = [
        "# Source-blind diagnostic adjudication results",
        "",
        f"- Protocol: `{report['protocol_id']}`",
        f"- Status: `{report['status']}`",
        f"- Completed cases: {report['completion']['completed_cases']}/40",
        "- Scope: same-author source-blind diagnostic adjudication, not formal gold or IAA.",
        "",
        "## Candidate assessment after source unblinding",
        "",
        "| Source | Supported | Acceptable | Unsupported | Undecidable | Strict support | Support or acceptable |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for source in SOURCES:
        metric = analysis["candidate_assessment_by_source"][source]
        counts = metric["assessment_counts"]
        lines.append(
            "| {source} | {supported} | {acceptable} | {unsupported} | "
            "{undecidable} | {strict:.1%} | {broad:.1%} |".format(
                source=source,
                supported=counts.get("supported", 0),
                acceptable=counts.get("acceptable_but_not_primary", 0),
                unsupported=counts.get("unsupported", 0),
                undecidable=counts.get("undecidable", 0),
                strict=metric["strict_supported_rate"],
                broad=metric["supported_or_acceptable_rate"],
            )
        )

    resolution = analysis["resolution"]
    stability = analysis["independent_to_final"]
    session = analysis["session_discipline"]
    controls = analysis["all_three_equal_controls"]
    lines.extend(
        [
            "",
            "## Decision stability",
            "",
            f"- Final decisions: {stability['final_decision_cases']}",
            f"- Independent decision retained: {stability['unchanged']}",
            f"- Independent decision changed: {stability['changed']} "
            f"({stability['changed_rate_among_final_decisions']:.1%} of final decisions)",
            f"- No stable gold: {resolution['counts'].get('no_stable_gold', 0)} "
            f"({resolution['no_stable_gold_rate']:.1%})",
            "- Final outcome statuses: "
            f"{json.dumps(resolution['final_outcome_status_counts'], sort_keys=True)}",
            "",
            "## Unsupported-candidate reasons",
            "",
        ]
    )
    for source in SOURCES:
        reasons = analysis["unsupported_reason_by_source"][source]
        rendered = ", ".join(f"`{key}` {value}" for key, value in reasons.items())
        lines.append(f"- `{source}`: {rendered or 'none'}")

    lines.extend(
        [
            "",
            "## Frozen-stratum Phase 1 diagnosis",
            "",
        ]
    )
    for stratum in STRATUM_ORDER:
        item = analysis["phase_1_diagnosis_by_frozen_stratum"][stratum]
        lines.append(
            f"- `{stratum}` ({item['cases']}): emotion_presence="
            f"{json.dumps(item['emotion_presence'], sort_keys=True)}; stance="
            f"{json.dumps(item['stance'], sort_keys=True)}; unit_validity="
            f"{json.dumps(item['unit_validity'], sort_keys=True)}"
        )

    lines.extend(
        [
            "",
            "## Controls and execution",
            "",
            f"- All-equal controls: {controls['cases']}; all candidates supported or "
            f"acceptable in {controls['all_candidates_supported_or_acceptable']}; "
            f"any candidate unsupported in {controls['any_candidate_unsupported']}.",
            f"- Final decision matched the unanimous control candidate in "
            f"{controls['final_matches_unanimous_candidate']} cases; no stable gold in "
            f"{controls['no_stable_gold']}.",
            f"- Sessions: {session['session_count']}; completed per session: "
            f"{session['completed_per_session']}; maximum: "
            f"{session['maximum_completed_in_one_session']}/{session['session_limit']}.",
            "",
            "## Claim boundary",
            "",
            "These figures measure how the same project author judged anonymized candidate "
            "decisions after an independent first phase. They are not model accuracy, "
            "inter-annotator agreement, a reliability estimate, or a formal gold dataset.",
            "The 40 cases are deliberately disagreement-enriched and include only two "
            "all-equal controls, so source-level rates cannot estimate performance on all "
            "120 pilot cases or on the wider IAC2 corpus.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    outputs = (
        args.checkpoint,
        args.private_seal,
        args.public_json,
        args.public_markdown,
    )
    existing = [path for path in outputs if path.exists()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite finalization outputs: "
            + ", ".join(str(path) for path in existing)
        )

    rows, verification = load_complete_rows(
        args.diagnostic_root,
        args.bundle_report,
    )
    analysis = analyze_rows(rows, verification["session"])
    completed_at_values = sorted(row["record"]["completed_at"] for row in rows)
    generated_at = utc_now()
    public_report = {
        "schema_version": "blind-adjudication-results-v1",
        "protocol_id": PROTOCOL_ID,
        "status": "completed_and_aggregate_unblinded",
        "generated_at_utc": generated_at,
        "completion": {
            "completed_cases": len(rows),
            "first_completed_at": completed_at_values[0],
            "last_completed_at": completed_at_values[-1],
            "phase_1_complete": len(rows),
            "phase_2_complete": len(rows),
        },
        "input_verification": {
            "bundle_hash": "passed",
            "source_map_hash": "passed",
            "record_case_hashes": "passed",
            "record_completeness": "passed",
            "session_log": "passed",
            "records_composite_sha256": verification[
                "records_composite_sha256"
            ],
        },
        "analysis": analysis,
        "sampling_boundary": {
            "design": "disagreement_enriched_stratified_diagnostic",
            "all_equal_control_cases": 2,
            "representative_sample": False,
        },
        "privacy": {
            "forum_text_emitted": False,
            "private_identifiers_emitted": False,
            "per_case_labels_emitted": False,
            "per_case_source_mapping_emitted": False,
        },
        "claim_boundary": {
            "creates_formal_gold": False,
            "is_independent_reannotation": False,
            "supports_inter_annotator_agreement": False,
            "supports_model_accuracy_claims": False,
            "supports_population_performance_claims": False,
            "source_unblinded_for_aggregate_analysis": True,
        },
    }
    violations = public_violations(public_report)
    if violations:
        raise ValueError("public privacy validation failed: " + "; ".join(violations))

    create_deterministic_checkpoint(args.diagnostic_root, args.checkpoint)
    checkpoint_hash = sha256_file(args.checkpoint)
    private_seal = {
        "schema_version": "blind-adjudication-seal-v1",
        "protocol_id": PROTOCOL_ID,
        "sealed_at_utc": generated_at,
        "scope": "complete_source_blind_diagnostic_adjudication",
        "completion": public_report["completion"],
        "inputs": {
            "bundle_sha256": verification["bundle_sha256"],
            "source_map_sha256": verification["source_map_sha256"],
            "manifest_sha256": verification["manifest_sha256"],
            "session_log_sha256": verification["session_log_sha256"],
            "records_composite_sha256": verification[
                "records_composite_sha256"
            ],
            "record_hashes": verification["record_hashes"],
        },
        "checkpoint": {
            "bytes": args.checkpoint.stat().st_size,
            "sha256": checkpoint_hash,
        },
        "filesystem_seal": {
            "private_file_mode": "0400",
            "diagnostic_directory_mode": "0500",
        },
    }
    write_json_once(args.private_seal, private_seal, 0o400)
    public_report["private_checkpoint_verification"] = {
        "checkpoint_sha256": checkpoint_hash,
        "private_seal_sha256": sha256_file(args.private_seal),
    }
    if public_violations(public_report):
        raise ValueError("checkpoint metadata violated the public privacy boundary")
    write_json_once(args.public_json, public_report, 0o644)
    write_bytes_once(
        args.public_markdown,
        markdown_report(public_report).encode("utf-8"),
        0o644,
    )
    seal_private_tree(args.diagnostic_root)

    print(
        json.dumps(
            {
                "status": public_report["status"],
                "completed_cases": len(rows),
                "checkpoint_sha256": checkpoint_hash,
                "privacy_violations": 0,
                "session_limit_passed": analysis["session_discipline"][
                    "session_limit_passed"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
