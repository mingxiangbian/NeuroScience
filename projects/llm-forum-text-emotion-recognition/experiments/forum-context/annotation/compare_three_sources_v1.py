#!/usr/bin/env python3
"""Compare Human Pass 1 with two sealed model annotation sets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


PROTOCOL_ID = "DATA-FCTX-LABEL-V1"
AMENDMENT = (
    "data-annotation-sampling-pilot-v1-amendment-2026-08-07-direct-comparison"
)
EXPECTED_ROWS = 120
STAGES = {"stage_a": "target_only", "stage_b": "contextual"}
SOURCES = ("human", "model_01", "model_02")
PAIR_NAMES = (
    ("human__model_01", "human", "model_01"),
    ("human__model_02", "human", "model_02"),
    ("model_01__model_02", "model_01", "model_02"),
)
LABELS = {
    "anger",
    "frustration",
    "disappointment",
    "sadness",
    "fear",
    "joy",
    "surprise",
    "confusion",
    "disgust",
    "cynicism",
    "neutral",
    "other_emotion",
}
STATUSES = {"labeled", "unclear", "unusable"}
CONFIDENCES = {"low", "medium", "high"}
SARCASM_VALUES = {"present", "absent", "uncertain", None}
CONTEXT_VALUES = {"sufficient", "insufficient", "uncertain", None}
HMAC_ID_RE = re.compile(r"\b(?:smp|thr|pst|rvc)_[0-9a-f]{64}\b")
PRIVATE_PUBLIC_KEYS = {
    "sample_uid",
    "view_sha256",
    "annotation_order",
    "note",
    "other_emotion_text",
    "text",
    "context",
    "target",
}


def parse_args() -> argparse.Namespace:
    annotation_dir = Path(__file__).resolve().parent
    project_root = annotation_dir.parents[2]
    private_root = project_root / "data/iac2/annotations/pilot-v1"
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", type=Path, default=private_root)
    parser.add_argument(
        "--seal-report",
        type=Path,
        default=annotation_dir / "reports/model-output-seal-v1.json",
    )
    parser.add_argument(
        "--public-output",
        type=Path,
        default=annotation_dir / "reports/three-source-comparison-v1.json",
    )
    parser.add_argument(
        "--private-output",
        type=Path,
        default=(
            private_root
            / "comparisons/three-source-v1/three-source-disagreements-v1.jsonl"
        ),
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line:
            raise ValueError(f"blank row in {path.name}:{line_number}")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"non-object row in {path.name}:{line_number}")
        rows.append(value)
    return rows


def write_json(path: Path, value: object, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, mode)
    os.replace(temporary, path)
    os.chmod(path, mode)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]], mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
    os.chmod(temporary, mode)
    os.replace(temporary, path)
    os.chmod(path, mode)


def normalize_other(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("other_emotion requires non-empty other_emotion_text")
    return " ".join(value.casefold().split())


def validate_decision(decision: Any, *, contextual: bool) -> dict[str, Any]:
    if not isinstance(decision, dict):
        raise ValueError("decision is not an object")
    status = decision.get("status")
    if status not in STATUSES:
        raise ValueError(f"invalid status: {status!r}")
    confidence = decision.get("confidence")
    if confidence not in CONFIDENCES:
        raise ValueError(f"invalid confidence: {confidence!r}")
    emotion = decision.get("primary_emotion")
    other = decision.get("other_emotion_text")
    if status == "labeled":
        if emotion not in LABELS:
            raise ValueError(f"invalid emotion: {emotion!r}")
        if emotion == "other_emotion":
            normalize_other(other)
        elif other is not None:
            raise ValueError("non-other label has other_emotion_text")
    elif emotion is not None or other is not None:
        raise ValueError("non-labeled decision contains emotion")
    if contextual:
        sarcasm = decision.get("sarcasm")
        mixed = decision.get("mixed_emotion")
        context_sufficiency = decision.get("context_sufficiency")
        if status == "unusable":
            if any(value is not None for value in (sarcasm, mixed, context_sufficiency)):
                raise ValueError("unusable contextual decision has diagnostics")
        else:
            if sarcasm not in SARCASM_VALUES - {None}:
                raise ValueError(f"invalid sarcasm value: {sarcasm!r}")
            if not isinstance(mixed, bool):
                raise ValueError("mixed_emotion is not boolean")
            if context_sufficiency not in CONTEXT_VALUES - {None}:
                raise ValueError(
                    f"invalid context_sufficiency: {context_sufficiency!r}"
                )
    return decision


def exact_key(decision: Mapping[str, Any]) -> str:
    status = str(decision["status"])
    if status != "labeled":
        return status
    emotion = str(decision["primary_emotion"])
    if emotion == "other_emotion":
        return f"other_emotion:{normalize_other(decision.get('other_emotion_text'))}"
    return emotion


def public_key(decision: Mapping[str, Any]) -> str:
    key = exact_key(decision)
    return "other_emotion" if key.startswith("other_emotion:") else key


def rate(count: int, total: int) -> float:
    return round(count / total, 6) if total else 0.0


def pair_metrics(rows: list[dict[str, Any]], left: str, right: str) -> dict[str, Any]:
    agree = 0
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    focal = Counter()
    for row in rows:
        left_decision = row["decisions"][left]
        right_decision = row["decisions"][right]
        left_exact = exact_key(left_decision)
        right_exact = exact_key(right_decision)
        if left_exact == right_exact:
            agree += 1
        left_public = public_key(left_decision)
        right_public = public_key(right_decision)
        confusion[left_public][right_public] += 1
        unordered = frozenset((left_public, right_public))
        if unordered == frozenset(("neutral", "unclear")):
            focal["neutral_vs_unclear"] += 1
        if unordered == frozenset(("anger", "frustration")):
            focal["anger_vs_frustration"] += 1
    total = len(rows)
    return {
        "agree": agree,
        "disagree": total - agree,
        "agreement_rate": rate(agree, total),
        "focal_disagreements": dict(sorted(focal.items())),
        "confusion_rows_left_columns_right": {
            key: dict(sorted(values.items()))
            for key, values in sorted(confusion.items())
        },
    }


def three_way_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    patterns = Counter()
    for row in rows:
        human = exact_key(row["decisions"]["human"])
        model_01 = exact_key(row["decisions"]["model_01"])
        model_02 = exact_key(row["decisions"]["model_02"])
        if human == model_01 == model_02:
            patterns["all_three_equal"] += 1
        elif model_01 == model_02:
            patterns["models_equal_human_differs"] += 1
        elif human == model_01:
            patterns["human_model_01_equal_model_02_differs"] += 1
        elif human == model_02:
            patterns["human_model_02_equal_model_01_differs"] += 1
        else:
            patterns["all_three_different"] += 1
    total = len(rows)
    result = dict(sorted(patterns.items()))
    result["all_three_equal_rate"] = rate(patterns["all_three_equal"], total)
    return result


def distribution(rows: list[dict[str, Any]], source: str, field: str) -> dict[str, int]:
    values = Counter()
    for row in rows:
        decision = row["decisions"][source]
        if field == "decision":
            value: Any = public_key(decision)
        else:
            value = decision.get(field)
        values["null" if value is None else str(value).lower()] += 1
    return dict(sorted(values.items()))


def group_metrics(rows: list[dict[str, Any]], stage: str) -> dict[str, Any]:
    stage_rows = [{"decisions": row[stage]} for row in rows]
    return {
        "rows": len(rows),
        "three_way": three_way_metrics(stage_rows),
        "pairwise": {
            name: pair_metrics(stage_rows, left, right)
            for name, left, right in PAIR_NAMES
        },
        "decision_distribution": {
            source: distribution(stage_rows, source, "decision")
            for source in SOURCES
        },
        "confidence_distribution": {
            source: distribution(stage_rows, source, "confidence")
            for source in SOURCES
        },
    }


def diagnostic_agreement(
    rows: list[dict[str, Any]], field: str
) -> dict[str, Any]:
    pairwise: dict[str, Any] = {}
    for name, left, right in PAIR_NAMES:
        agree = sum(
            row["decisions"][left].get(field)
            == row["decisions"][right].get(field)
            for row in rows
        )
        pairwise[name] = {
            "agree": agree,
            "disagree": len(rows) - agree,
            "agreement_rate": rate(agree, len(rows)),
        }
    all_three = sum(
        len({row["decisions"][source].get(field) for source in SOURCES}) == 1
        for row in rows
    )
    return {
        "three_way_exact": all_three,
        "three_way_exact_rate": rate(all_three, len(rows)),
        "pairwise": pairwise,
        "distribution": {
            source: distribution(rows, source, field) for source in SOURCES
        },
    }


def transition_metrics(rows: list[dict[str, Any]], source: str) -> dict[str, Any]:
    outcomes = Counter()
    for row in rows:
        before = row["stage_a"][source]
        after = row["stage_b"][source]
        if exact_key(before) == exact_key(after):
            outcomes["unchanged"] += 1
        elif before["status"] == "unclear" and after["status"] == "labeled":
            outcomes["resolved_from_unclear"] += 1
        elif before["status"] == "labeled" and after["status"] == "unclear":
            outcomes["became_unclear"] += 1
        elif before["status"] == after["status"] == "labeled":
            outcomes["label_changed"] += 1
        else:
            outcomes["other_status_change"] += 1
    outcomes["changed_total"] = len(rows) - outcomes["unchanged"]
    outcomes["changed_rate"] = rate(outcomes["changed_total"], len(rows))
    return dict(sorted(outcomes.items()))


def groups(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result = {"all_primary": rows}
    result["representative"] = [row for row in rows if row["lane"] == "representative"]
    diagnostic = [row for row in rows if row["lane"] != "representative"]
    result["diagnostic_all"] = diagnostic
    for lane in sorted({row["lane"] for row in diagnostic}):
        result[lane] = [row for row in diagnostic if row["lane"] == lane]
    return result


def public_violations(value: object, path: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in PRIVATE_PUBLIC_KEYS:
                violations.append(child_path)
            violations.extend(public_violations(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(public_violations(child, f"{path}[{index}]"))
    elif isinstance(value, str) and HMAC_ID_RE.search(value):
        violations.append(f"HMAC identifier at {path}")
    return sorted(set(violations))


def validate_model_hashes(
    model_dir: Path, seal_report: Mapping[str, Any]
) -> dict[tuple[str, str], Path]:
    paths: dict[tuple[str, str], Path] = {}
    for entry in seal_report["outputs"]:
        path = model_dir / entry["filename"]
        actual = sha256_file(path)
        if actual != entry["sha256"]:
            raise ValueError(f"sealed hash mismatch for {path.name}")
        key = (entry["model_slot"], str(entry["stage"]).lower())
        paths[key] = path
    expected = {
        ("model_01", "a"),
        ("model_01", "b"),
        ("model_02", "a"),
        ("model_02", "b"),
    }
    if set(paths) != expected:
        raise ValueError("seal report does not contain four expected model outputs")
    return paths


def load_model_rows(path: Path, *, contextual: bool) -> dict[int, dict[str, Any]]:
    rows = read_jsonl(path)
    if len(rows) != EXPECTED_ROWS:
        raise ValueError(f"expected {EXPECTED_ROWS} rows in {path.name}")
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        order = row.get("annotation_order")
        if not isinstance(order, int) or order in result:
            raise ValueError(f"invalid or duplicate annotation_order in {path.name}")
        validate_decision(row.get("decision"), contextual=contextual)
        result[order] = row
    return result


def build_rows(
    private_root: Path, model_paths: Mapping[tuple[str, str], Path]
) -> list[dict[str, Any]]:
    manifests = read_jsonl(private_root / "sampling-manifest.jsonl")
    if len(manifests) != EXPECTED_ROWS:
        raise ValueError("sampling manifest does not contain 120 rows")
    manifest_by_order = {row["annotation_order"]: row for row in manifests}
    if len(manifest_by_order) != EXPECTED_ROWS:
        raise ValueError("duplicate annotation_order in sampling manifest")

    human_by_uid: dict[str, dict[str, Any]] = {}
    record_paths = sorted((private_root / "records/human-pass-1").glob("[0-9][0-9][0-9][0-9].json"))
    if len(record_paths) != EXPECTED_ROWS:
        raise ValueError("human record directory does not contain 120 records")
    for path in record_paths:
        record = read_object(path)
        if record.get("completed_at") is None:
            raise ValueError(f"incomplete human record: {path.name}")
        uid = record.get("sample_uid")
        if not isinstance(uid, str) or uid in human_by_uid:
            raise ValueError("invalid or duplicate human sample_uid")
        validate_decision(record.get("target_only"), contextual=False)
        validate_decision(record.get("contextual"), contextual=True)
        human_by_uid[uid] = record

    model_rows = {
        (model, stage): load_model_rows(
            model_paths[(model, stage)], contextual=stage == "b"
        )
        for model in ("model_01", "model_02")
        for stage in ("a", "b")
    }

    combined: list[dict[str, Any]] = []
    for order in range(1, EXPECTED_ROWS + 1):
        manifest = manifest_by_order.get(order)
        if manifest is None or manifest.get("role") != "primary":
            raise ValueError(f"missing primary manifest row {order}")
        uid = manifest["sample_uid"]
        human = human_by_uid.get(uid)
        if human is None:
            raise ValueError(f"missing human row for annotation order {order}")
        identity = (uid, human["view_sha256"])
        for key, indexed in model_rows.items():
            model_row = indexed.get(order)
            if model_row is None:
                raise ValueError(f"missing model row {key} order {order}")
            if (model_row.get("sample_uid"), model_row.get("view_sha256")) != identity:
                raise ValueError(f"identity mismatch at order {order} for {key}")
        combined.append(
            {
                "annotation_order": order,
                "sample_uid": uid,
                "view_sha256": human["view_sha256"],
                "lane": manifest["lane"],
                "stage_a": {
                    "human": human["target_only"],
                    "model_01": model_rows[("model_01", "a")][order]["decision"],
                    "model_02": model_rows[("model_02", "a")][order]["decision"],
                },
                "stage_b": {
                    "human": human["contextual"],
                    "model_01": model_rows[("model_01", "b")][order]["decision"],
                    "model_02": model_rows[("model_02", "b")][order]["decision"],
                },
            }
        )
    return combined


def disagreement_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        patterns = {}
        disagrees = False
        for stage in STAGES:
            decisions = row[stage]
            keys = {source: exact_key(decisions[source]) for source in SOURCES}
            patterns[stage] = keys
            disagrees = disagrees or len(set(keys.values())) > 1
        if disagrees:
            result.append(
                {
                    "schema_version": "three-source-disagreement-v1",
                    "protocol_id": PROTOCOL_ID,
                    "amendment": AMENDMENT,
                    "annotation_order": row["annotation_order"],
                    "sample_uid": row["sample_uid"],
                    "view_sha256": row["view_sha256"],
                    "lane": row["lane"],
                    "stage_a": row["stage_a"],
                    "stage_b": row["stage_b"],
                    "exact_keys": patterns,
                    "adjudication": None,
                }
            )
    return result


def build_public_report(
    rows: list[dict[str, Any]],
    model_paths: Mapping[tuple[str, str], Path],
    private_output: Path,
) -> dict[str, Any]:
    row_groups = groups(rows)
    report: dict[str, Any] = {
        "schema_version": "three-source-comparison-v1",
        "protocol_id": PROTOCOL_ID,
        "amendment": AMENDMENT,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "human_source": "single_human_pass_1",
            "model_sources": ["model_01", "model_02"],
            "primary_cases": len(rows),
            "representative_cases": len(row_groups["representative"]),
            "diagnostic_cases": len(row_groups["diagnostic_all"]),
            "blind_repeats": "waived_by_amendment",
        },
        "input_verification": {
            "model_outputs": {
                f"{model}_{stage}": {
                    "filename": path.name,
                    "sha256": sha256_file(path),
                    "rows": EXPECTED_ROWS,
                }
                for (model, stage), path in sorted(model_paths.items())
            },
            "identity_mapping": "passed",
            "decision_contract": "passed",
        },
        "stage_a": {
            name: group_metrics(group_rows, "stage_a")
            for name, group_rows in row_groups.items()
        },
        "stage_b": {
            name: group_metrics(group_rows, "stage_b")
            for name, group_rows in row_groups.items()
        },
        "context_transitions": {
            name: {
                source: transition_metrics(group_rows, source) for source in SOURCES
            }
            for name, group_rows in row_groups.items()
        },
        "stage_b_diagnostics": {
            name: {
                field: diagnostic_agreement(
                    [{"decisions": row["stage_b"]} for row in group_rows],
                    field,
                )
                for field in ("sarcasm", "mixed_emotion", "context_sufficiency")
            }
            for name, group_rows in row_groups.items()
        },
        "private_disagreement_sidecar": {
            "filename": private_output.name,
            "rows": 0,
            "sha256": "pending",
            "contains_forum_text": False,
            "gitignored_required": True,
        },
        "claim_boundary": {
            "inter_annotator_agreement": False,
            "majority_vote_defines_gold": False,
            "representative_prevalence_source": "representative group only",
            "formal_ontology_acceptance": False,
        },
        "privacy": {
            "forum_text_emitted": False,
            "private_identifiers_emitted": False,
            "per_sample_labels_emitted": False,
            "other_emotion_proposals_emitted": False,
        },
    }
    return report


def main() -> int:
    args = parse_args()
    seal_report = read_object(args.seal_report)
    model_paths = validate_model_hashes(
        args.private_root / "model-outputs", seal_report
    )
    rows = build_rows(args.private_root, model_paths)
    private_rows = disagreement_rows(rows)
    write_jsonl(args.private_output, private_rows, 0o600)

    report = build_public_report(rows, model_paths, args.private_output)
    report["private_disagreement_sidecar"].update(
        {
            "rows": len(private_rows),
            "sha256": sha256_file(args.private_output),
        }
    )
    violations = public_violations(report)
    if violations:
        raise ValueError(f"public report privacy violations: {violations}")
    write_json(args.public_output, report, 0o644)
    print(
        json.dumps(
            {
                "public_output": str(args.public_output),
                "private_output": str(args.private_output),
                "rows": len(rows),
                "disagreement_rows": len(private_rows),
                "privacy_violations": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
