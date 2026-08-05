#!/usr/bin/env python3
"""Independently recompute and verify all EXP-035 audit artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = PROJECT_ROOT.parents[1]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def artifact_record(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "sha256": sha256_file(path),
    }


def assert_csv(path: Path, expected: Iterable[dict[str, Any]]) -> None:
    normalized = [{key: str(value) for key, value in row.items()} for row in expected]
    if read_csv(path) != normalized:
        raise RuntimeError(f"Recomputed CSV differs: {path}")


def load_frozen_targets(config: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    selection = config["selection"]
    train_path = resolve_project_path(selection["train_path"])
    labels_path = resolve_project_path(selection["labels_path"])
    test_path = resolve_project_path(selection["simplified_test_path"])
    if test_path.exists():
        raise RuntimeError("Simplified test.tsv exists during verification")
    if sha256_file(train_path) != selection["train_sha256"]:
        raise RuntimeError("Frozen train hash changed")
    if sha256_file(labels_path) != selection["labels_sha256"]:
        raise RuntimeError("Frozen label hash changed")
    labels = labels_path.read_text(encoding="utf-8").splitlines()
    if labels != config["labels"]:
        raise RuntimeError("Label order changed")

    targets: list[dict[str, Any]] = []
    with train_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row_number, row in enumerate(reader, start=1):
            if len(row) != 3:
                raise RuntimeError(f"Malformed train row {row_number}")
            text, encoded_labels, comment_id = row
            label_ids = [int(value) for value in encoded_labels.split(",")]
            if 27 in label_ids and len(label_ids) > 1:
                targets.append(
                    {
                        "comment_id": comment_id,
                        "example_hash": sha256_text(comment_id),
                        "gold_label_ids": label_ids,
                        "gold_labels": [labels[index] for index in label_ids],
                        "source_train_row": row_number,
                        "text": text,
                        "text_sha256": sha256_text(text),
                    }
                )
    row_hash = sha256_text(
        ",".join(str(target["source_train_row"]) for target in targets)
    )
    if len(targets) != selection["expected_rows"] or row_hash != selection["source_train_rows_sha256"]:
        raise RuntimeError("Frozen train selection changed")
    return labels, targets


def validate_private_records(
    path: Path,
    targets: list[dict[str, Any]],
    labels: list[str],
    source_names: set[str],
) -> list[dict[str, Any]]:
    records = read_jsonl(path)
    target_by_id = {target["comment_id"]: target for target in targets}
    seen_pairs: set[tuple[str, str]] = set()
    observed_ids: set[str] = set()
    expected_keys = {
        "comment_id",
        "example_hash",
        "labels",
        "rater_hash",
        "source_file",
        "source_line",
        "source_train_row",
        "text_sha256",
        "unclear",
    }
    for record in records:
        if set(record) != expected_keys:
            raise RuntimeError("Private annotation schema differs")
        target = target_by_id.get(record["comment_id"])
        if target is None:
            raise RuntimeError("Non-allowlisted raw annotation was persisted")
        if (
            record["example_hash"] != target["example_hash"]
            or record["source_train_row"] != target["source_train_row"]
            or record["text_sha256"] != target["text_sha256"]
        ):
            raise RuntimeError("Private annotation join fields differ")
        if (
            len(record["labels"]) != len(labels)
            or any(value not in {0, 1} for value in record["labels"])
            or record["source_file"] not in source_names
            or int(record["source_line"]) < 2
            or not isinstance(record["unclear"], bool)
            or len(record["rater_hash"]) != 64
        ):
            raise RuntimeError("Private annotation value is invalid")
        pair = (record["comment_id"], record["rater_hash"])
        if pair in seen_pairs:
            raise RuntimeError("Duplicate comment/rater pair")
        seen_pairs.add(pair)
        observed_ids.add(record["comment_id"])
    if observed_ids != set(target_by_id):
        raise RuntimeError("Private annotations do not cover the frozen target IDs")
    return records


def recompute_quantitative(
    targets: list[dict[str, Any]],
    records: list[dict[str, Any]],
    labels: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_id[record["comment_id"]].append(record)
    row_audit: list[dict[str, Any]] = []
    rater_counts: Counter[int] = Counter()
    unclear_counts: Counter[int] = Counter()
    neutral_counts: Counter[int] = Counter()
    coselection_counts: Counter[int] = Counter()
    patterns: Counter[tuple[int, int, int, int, int]] = Counter()
    per_emotion: dict[str, Counter[str]] = defaultdict(Counter)

    for target in targets:
        annotations = by_id[target["comment_id"]]
        votes = [sum(row["labels"][index] for row in annotations) for index in range(len(labels))]
        derived_ids = [index for index, count in enumerate(votes) if count >= 2]
        if derived_ids != target["gold_label_ids"]:
            raise RuntimeError("Official >=2 vote threshold does not reproduce a target")
        same_rater = sum(
            row["labels"][27] == 1 and sum(row["labels"][:27]) > 0
            for row in annotations
        )
        unclear = sum(row["unclear"] for row in annotations)
        rater_count = len(annotations)
        neutral_votes = votes[27]
        max_emotion_votes = max(
            votes[index] for index in target["gold_label_ids"] if index != 27
        )
        aggregation_only = same_rater == 0
        row = {
            "aggregation_only": aggregation_only,
            "derived_labels_match": True,
            "example_hash": target["example_hash"],
            "gold_cardinality": len(target["gold_label_ids"]),
            "gold_label_ids": "|".join(str(value) for value in target["gold_label_ids"]),
            "gold_labels": "|".join(target["gold_labels"]),
            "max_emotion_votes": max_emotion_votes,
            "neutral_votes": neutral_votes,
            "rater_count": rater_count,
            "same_rater_coselection_count": same_rater,
            "source_train_row": target["source_train_row"],
            "unclear_count": unclear,
        }
        row_audit.append(row)
        rater_counts[rater_count] += 1
        unclear_counts[unclear] += 1
        neutral_counts[neutral_votes] += 1
        coselection_counts[same_rater] += 1
        patterns[(rater_count, neutral_votes, max_emotion_votes, same_rater, unclear)] += 1
        for label_id in target["gold_label_ids"]:
            if label_id == 27:
                continue
            counts = per_emotion[labels[label_id]]
            counts["rows"] += 1
            counts["aggregation_only_rows"] += aggregation_only
            counts["same_rater_coselection_rows"] += not aggregation_only
            counts["any_unclear_rows"] += unclear > 0

    rows = len(row_audit)
    aggregation_only_rows = sum(row["aggregation_only"] for row in row_audit)
    same_rater_rows = rows - aggregation_only_rows
    any_unclear_rows = sum(row["unclear_count"] > 0 for row in row_audit)
    summary = {
        "aggregation_only_rate": aggregation_only_rows / rows,
        "aggregation_only_rows": aggregation_only_rows,
        "any_unclear_rate": any_unclear_rows / rows,
        "any_unclear_rows": any_unclear_rows,
        "decision": (
            "annotation_aggregation_is_primary_for_target_structure"
            if aggregation_only_rows / rows > 0.5
            else "same_rater_coselection_is_not_a_minority"
        ),
        "duplicate_comment_rater_pairs": 0,
        "neutral_vote_distribution": {str(key): value for key, value in sorted(neutral_counts.items())},
        "official_threshold_reproduction_mismatches": 0,
        "rater_count_distribution": {str(key): value for key, value in sorted(rater_counts.items())},
        "rows": rows,
        "same_rater_coselection_count_distribution": {
            str(key): value for key, value in sorted(coselection_counts.items())
        },
        "same_rater_coselection_rate": same_rater_rows / rows,
        "same_rater_coselection_rows": same_rater_rows,
        "transport_boundary": {
            "nonmatching_raw_records_persisted": 0,
            "raw_archive_objects_streamed": 3,
            "simplified_dev_accessed": False,
            "simplified_test_accessed": False,
            "simplified_test_exists": False,
            "train_allowlist_only_persisted": True,
        },
        "unclear_count_distribution": {str(key): value for key, value in sorted(unclear_counts.items())},
    }
    pattern_rows = [
        {
            "count": count,
            "max_emotion_votes": key[2],
            "neutral_votes": key[1],
            "rater_count": key[0],
            "same_rater_coselection_count": key[3],
            "unclear_count": key[4],
        }
        for key, count in sorted(patterns.items())
    ]
    emotion_rows = []
    for emotion, counts in sorted(per_emotion.items()):
        emotion_rows.append(
            {
                "aggregation_only_rate": counts["aggregation_only_rows"] / counts["rows"],
                "aggregation_only_rows": counts["aggregation_only_rows"],
                "any_unclear_rows": counts["any_unclear_rows"],
                "emotion": emotion,
                "rows": counts["rows"],
                "same_rater_coselection_rows": counts["same_rater_coselection_rows"],
            }
        )
    return row_audit, summary, emotion_rows, pattern_rows


def recompute_sample(
    row_audit: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_rows: set[int] = set()
    maximum = config["qualitative_sample"]["maximum_rows"]

    def eligible(role: str, row: dict[str, Any]) -> bool:
        return {
            "aggregation_only": bool(row["aggregation_only"]),
            "same_rater_coselection": int(row["same_rater_coselection_count"]) > 0,
            "any_unclear": int(row["unclear_count"]) > 0,
            "gold_cardinality_at_least_3": int(row["gold_cardinality"]) >= 3,
            "residual_fill": True,
        }[role]

    for spec in config["qualitative_sample"]["roles"]:
        role = spec["name"]
        limit = maximum if spec["limit"] is None else spec["limit"]
        candidates = [
            row
            for row in row_audit
            if row["source_train_row"] not in selected_rows and eligible(role, row)
        ]
        candidates.sort(
            key=lambda row: sha256_text(
                f"{config['qualitative_sample']['ranking_salt']}:{role}:{row['source_train_row']}"
            )
        )
        for row in candidates[: min(limit, maximum - len(selected))]:
            selected_rows.add(row["source_train_row"])
            selected.append({**row, "sample_role": role})
        if len(selected) == maximum:
            break
    for index, row in enumerate(selected, start=1):
        row["sample_id"] = f"EXP-035-S{index:03d}"
    return selected


def recompute_qualitative(
    manifest: list[dict[str, str]],
    private_review: list[dict[str, str]],
    coding: dict[str, list[str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if [row["sample_id"] for row in manifest] != [row["sample_id"] for row in private_review]:
        raise RuntimeError("Manual review order differs")
    public_rows: list[dict[str, Any]] = []
    field_counts = {field: Counter() for field in coding if field != "context_trigger"}
    context_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    for sample, annotation in zip(manifest, private_review, strict=True):
        for field, allowed in coding.items():
            value = annotation[field]
            if field == "context_trigger":
                triggers = value.split(";")
                if (
                    not value
                    or len(triggers) != len(set(triggers))
                    or not set(triggers) <= set(allowed)
                    or ("none" in triggers and len(triggers) != 1)
                ):
                    raise RuntimeError("Invalid context trigger in private review")
                context_counts.update(triggers)
            else:
                if value not in allowed:
                    raise RuntimeError(f"Invalid {field} in private review")
                field_counts[field][value] += 1
        role_counts[sample["sample_role"]] += 1
        public_rows.append(
            {
                "aggregation_only": sample["aggregation_only"],
                "annotation_interpretation": annotation["annotation_interpretation"],
                "context_trigger": annotation["context_trigger"],
                "gold_cardinality": sample["gold_cardinality"],
                "label_coherence": annotation["label_coherence"],
                "reviewer_confidence": annotation["reviewer_confidence"],
                "sample_id": sample["sample_id"],
                "sample_role": sample["sample_role"],
                "source_train_row": sample["source_train_row"],
                "standalone_decidability": annotation["standalone_decidability"],
            }
        )
    reviewed = len(public_rows)
    context_rows = field_counts["standalone_decidability"]["context_likely_needed"]
    summary = {
        "annotation_rows": reviewed,
        "coding_counts": {
            field: dict(sorted(counts.items())) for field, counts in sorted(field_counts.items())
        },
        "context_likely_needed_rate_in_purposive_sample": context_rows / reviewed,
        "context_likely_needed_rows": context_rows,
        "context_trigger_counts": dict(sorted(context_counts.items())),
        "private_notes_published": False,
        "sample_role_counts": dict(sorted(role_counts.items())),
        "sampling_inference_boundary": (
            "Purposive frozen sample; qualitative proportions are descriptive and are "
            "not population estimates."
        ),
    }
    return public_rows, summary


def render_report(aggregate: dict[str, Any], qualitative: dict[str, Any]) -> str:
    rows = aggregate["rows"]
    aggregation_rows = aggregate["aggregation_only_rows"]
    same_rater_rows = aggregate["same_rater_coselection_rows"]
    unclear_rows = aggregate["any_unclear_rows"]
    reviewed = qualitative["annotation_rows"]
    context_rows = qualitative["context_likely_needed_rows"]
    if aggregate["decision"] == "annotation_aggregation_is_primary_for_target_structure":
        finding = (
            "`neutral + emotion` 多数是跨标注者投票经 `>=2` 阈值聚合后形成，"
            "而不是某位标注者在同一次标注中同时选择 neutral 和情绪。"
        )
        action = (
            "暂不把继续换 seed 或直接重训视为首选。先把 official hard target 与"
            "聚合分歧感知的目标设计登记为后续受控对照；现有官方标签基线保持冻结。"
        )
    else:
        finding = "同一标注者直接共选 neutral 与情绪并非少数，因此不能主要归因于跨标注者聚合。"
        action = "下一步优先做训练暴露与目标可学习性诊断，再决定是否调整监督目标或模型容量。"
    return f"""# EXP-035 GoEmotions 数据与标注审计

## 结论

{finding}

- 审计范围：冻结 train 中全部 {rows:,} 条 `neutral + emotion` 样本。
- 仅由跨标注者聚合形成：{aggregation_rows:,}/{rows:,}（{aggregation_rows / rows:.2%}）。
- 至少一位标注者直接共选：{same_rater_rows:,}/{rows:,}（{same_rater_rows / rows:.2%}）。
- 含 `example_very_unclear` 投票：{unclear_rows:,}/{rows:,}（{unclear_rows / rows:.2%}）。
- 官方 `>=2` 票聚合复现不一致：{aggregate['official_threshold_reproduction_mismatches']} 条。

## 文本复核

按预注册规则抽取并复核 {reviewed} 条文本，其中 {context_rows} 条被编码为
`context_likely_needed`。该样本是为覆盖不同标注结构而做的目的性抽样，这一比例只描述
复核样本，不能外推到全部 1,396 条数据。

公开文件只保留匿名样本号、训练行号和编码结果；原文、上游 comment ID、rater ID 与
自由文本笔记均保存在 gitignored 私有目录。

## 对当前实验的含义

{action}

这项审计解释的是监督标签如何形成，不证明模型容量足够，也不证明上下文无关。它把
“标签聚合问题”“单条文本上下文不足”和“模型学习能力不足”拆成了三个后续可检验因素。

## 数据边界

- 只以冻结 train ID 作为持久化 allowlist。
- 因官方原始数据以三个完整 CSV 对象发布，下载时流经了全部对象字节；非匹配记录未保存，
  也未向分析阶段暴露字段。
- 未读取简化版 dev 或 test；本机不存在 `data/goemotions/official/test.tsv`。
"""


def verify_source_manifest(
    path: Path, config: dict[str, Any], records: list[dict[str, Any]]
) -> dict[str, Any]:
    manifest = read_json(path)
    if manifest["target_comment_rows"] != config["selection"]["expected_rows"]:
        raise RuntimeError("Source manifest target row count differs")
    if manifest["target_annotation_rows_retained"] != len(records):
        raise RuntimeError("Source manifest retained count differs")
    if manifest["nonmatching_raw_fields_persisted"]:
        raise RuntimeError("Source manifest reports nonmatching raw persistence")
    record_counts = Counter(row["source_file"] for row in records)
    if len(manifest["sources"]) != len(config["raw_sources"]):
        raise RuntimeError("Source manifest object count differs")
    for observed, expected in zip(manifest["sources"], config["raw_sources"], strict=True):
        for key in ["name", "url", "etag", "last_modified", "md5_base64"]:
            if observed[key] != expected[key]:
                raise RuntimeError(f"Source identity differs for {expected['name']}")
        if (
            observed["bytes"] != expected["content_length"]
            or observed["matched_annotation_rows"] != record_counts[expected["name"]]
            or observed["raw_annotation_rows"] <= observed["matched_annotation_rows"]
            or len(observed["sha256"]) != 64
        ):
            raise RuntimeError(f"Source counts differ for {expected['name']}")
    return manifest


def verify_privacy(
    run_dir: Path, targets: list[dict[str, Any]], records: list[dict[str, Any]]
) -> dict[str, Any]:
    private_dir = run_dir / "private"
    private_files = [path for path in private_dir.iterdir() if path.is_file()]
    for path in private_files:
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", str(path)], cwd=REPO_ROOT, check=False
        ).returncode == 0
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(path)],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
        ).returncode == 0
        if not ignored or tracked:
            raise RuntimeError(f"Private artifact boundary failed: {path}")

    public_files = [
        path
        for path in run_dir.iterdir()
        if path.is_file()
        and path.name != "verification.json"
        and path.suffix in {".csv", ".json", ".log", ".md"}
    ]
    payload = "\n".join(path.read_text(encoding="utf-8") for path in public_files)
    leaked_text = [
        target["source_train_row"]
        for target in targets
        if len(target["text"]) >= 12 and target["text"] in payload
    ]
    leaked_ids = [target["source_train_row"] for target in targets if target["comment_id"] in payload]
    leaked_raters = [record["rater_hash"] for record in records if record["rater_hash"] in payload]
    if leaked_text or leaked_ids or leaked_raters:
        raise RuntimeError("Raw text or upstream identifiers leaked into public artifacts")
    forbidden_fields = {"text", "comment_id", "rater_id", "rater_hash", "private_note"}
    for path in run_dir.glob("*.csv"):
        with path.open(encoding="utf-8", newline="") as handle:
            fields = set(csv.DictReader(handle).fieldnames or [])
        if fields & forbidden_fields:
            raise RuntimeError(f"Forbidden public CSV field in {path}")
    return {
        "private_files_checked": len(private_files),
        "public_files_scanned": len(public_files),
        "raw_text_leaks": len(leaked_text),
        "upstream_id_leaks": len(leaked_ids),
        "rater_hash_leaks": len(leaked_raters),
    }


def verify_artifact_records(records: dict[str, dict[str, Any]]) -> int:
    checked = 0
    for spec in records.values():
        path = resolve_project_path(spec["path"])
        if not path.is_file() or artifact_record(path) != spec:
            raise RuntimeError(f"Artifact identity differs: {path}")
        checked += 1
    return checked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    if sha256_file(config_path) != args.config_sha256:
        raise RuntimeError("Config SHA-256 mismatch")
    config = read_json(config_path)
    for name, spec in config["implementation"].items():
        if sha256_file(resolve_project_path(spec["path"])) != spec["sha256"]:
            raise RuntimeError(f"Implementation hash changed: {name}")

    run_dir = resolve_project_path(config["outputs"]["run_dir"])
    verification_path = run_dir / "verification.json"
    if verification_path.exists() and not args.check:
        raise RuntimeError("Verification output already exists")
    if args.check and not verification_path.exists():
        raise RuntimeError("No verification output exists to check")

    labels, targets = load_frozen_targets(config)
    private_records_path = run_dir / "private" / "matched-annotations.private.jsonl"
    records = validate_private_records(
        private_records_path,
        targets,
        labels,
        {source["name"] for source in config["raw_sources"]},
    )
    row_audit, aggregate, emotion_rows, pattern_rows = recompute_quantitative(
        targets, records, labels
    )
    public_row_fields = [
        "source_train_row", "example_hash", "gold_label_ids", "gold_labels",
        "gold_cardinality", "rater_count", "unclear_count", "neutral_votes",
        "max_emotion_votes", "same_rater_coselection_count", "aggregation_only",
        "derived_labels_match",
    ]
    assert_csv(
        run_dir / "row-audit.csv",
        [{field: row[field] for field in public_row_fields} for row in row_audit],
    )
    assert_csv(run_dir / "per-emotion-summary.csv", emotion_rows)
    assert_csv(run_dir / "vote-patterns.csv", pattern_rows)
    if read_json(run_dir / "aggregate-summary.json") != aggregate:
        raise RuntimeError("Recomputed aggregate summary differs")

    sample = recompute_sample(row_audit, config)
    sample_fields = ["sample_id", "sample_role", *public_row_fields]
    assert_csv(
        run_dir / "sample-manifest.csv",
        [{field: row[field] for field in sample_fields} for row in sample],
    )
    manifest = read_csv(run_dir / "sample-manifest.csv")
    private_review = read_csv(run_dir / "private" / "manual-review.private.csv")
    public_annotations, qualitative = recompute_qualitative(
        manifest, private_review, config["coding"]
    )
    assert_csv(run_dir / "manual-annotations.csv", public_annotations)
    if read_json(run_dir / "qualitative-summary.json") != qualitative:
        raise RuntimeError("Recomputed qualitative summary differs")
    if (run_dir / "REPORT.md").read_text(encoding="utf-8") != render_report(aggregate, qualitative):
        raise RuntimeError("REPORT.md does not regenerate exactly")

    source_manifest = verify_source_manifest(run_dir / "source-manifest.json", config, records)
    privacy = verify_privacy(run_dir, targets, records)
    run = read_json(run_dir / "run.json")
    if (
        run["status"] != "Quantitative audit completed; manual review pending"
        or run["accessed_splits"] != ["train"]
        or run["test_boundary"] != aggregate["transport_boundary"]
        or run["result_summary"] != aggregate
    ):
        raise RuntimeError("run.json discipline or result differs")
    run_artifacts_checked = verify_artifact_records(run["artifacts"])
    completion = read_json(run_dir / "completion.json")
    if (
        completion["status"] != "CompletedAwaitingVerification"
        or completion["reviewed_rows"] != len(public_annotations)
        or completion["test_accessed"]
    ):
        raise RuntimeError("Completion record differs")
    completion_artifacts_checked = verify_artifact_records(completion["artifacts"])
    if completion["private_review"] != artifact_record(run_dir / "private" / "manual-review.private.csv"):
        raise RuntimeError("Private review identity differs")

    existing = read_json(verification_path) if args.check else None
    verified_at = existing["verified_at_utc"] if existing else datetime.now(timezone.utc).isoformat()
    verification = {
        "aggregate_rows_recomputed": len(row_audit),
        "completion_artifacts_checked": completion_artifacts_checked,
        "config": artifact_record(config_path),
        "experiment_id": config["experiment_id"],
        "implementation_files_checked": len(config["implementation"]),
        "manual_rows_recomputed": len(public_annotations),
        "max_absolute_numeric_difference": 0.0,
        "privacy": privacy,
        "qualitative_sample_reselected": True,
        "report_regenerated_exactly": True,
        "run_artifacts_checked": run_artifacts_checked,
        "source_manifest": {
            "objects": len(source_manifest["sources"]),
            "retained_annotation_rows": source_manifest["target_annotation_rows_retained"],
            "retained_comment_rows": source_manifest["target_comment_rows"],
        },
        "status": "Verified",
        "test_accessed": False,
        "test_absent": not resolve_project_path(config["selection"]["simplified_test_path"]).exists(),
        "verified_at_utc": verified_at,
        "verifier": artifact_record(Path(__file__).resolve()),
    }
    if args.check:
        if existing != verification:
            raise RuntimeError("Stored verification differs from independent recomputation")
    else:
        write_json(verification_path, verification)
    print(json.dumps({"experiment_id": config["experiment_id"], "status": "Verified"}, sort_keys=True))


if __name__ == "__main__":
    main()
