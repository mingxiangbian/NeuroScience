#!/usr/bin/env python3
"""Validate the frozen EXP-035 review and create public audit artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]


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


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def artifact_record(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "sha256": sha256_file(path),
    }


def validate_implementation(config: dict[str, Any]) -> None:
    for name, spec in config["implementation"].items():
        path = resolve_project_path(spec["path"])
        if sha256_file(path) != spec["sha256"]:
            raise RuntimeError(f"Implementation hash changed: {name}")


def parse_context_triggers(value: str, allowed: set[str]) -> list[str]:
    triggers = value.split(";")
    if not value or any(not trigger for trigger in triggers):
        raise RuntimeError("context_trigger is blank or malformed")
    if len(triggers) != len(set(triggers)) or not set(triggers) <= allowed:
        raise RuntimeError(f"Invalid context_trigger: {value}")
    if "none" in triggers and len(triggers) != 1:
        raise RuntimeError("context_trigger=none cannot be combined with another trigger")
    return triggers


def validate_review(
    manifest: list[dict[str, str]],
    review: list[dict[str, str]],
    coding: dict[str, list[str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(manifest) != len(review) or [row["sample_id"] for row in manifest] != [
        row["sample_id"] for row in review
    ]:
        raise RuntimeError("Manual review does not match the frozen sample order")

    public_rows: list[dict[str, Any]] = []
    field_counts = {
        field: Counter() for field in coding if field != "context_trigger"
    }
    context_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    for sample, annotation in zip(manifest, review, strict=True):
        for field, allowed_values in coding.items():
            if field == "context_trigger":
                continue
            value = annotation[field]
            if value not in allowed_values:
                raise RuntimeError(
                    f"Invalid {field} for {annotation['sample_id']}: {value!r}"
                )
            field_counts[field][value] += 1
        triggers = parse_context_triggers(
            annotation["context_trigger"], set(coding["context_trigger"])
        )
        context_counts.update(triggers)
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

    reviewed_rows = len(public_rows)
    context_likely = field_counts["standalone_decidability"]["context_likely_needed"]
    summary = {
        "annotation_rows": reviewed_rows,
        "coding_counts": {
            field: dict(sorted(counts.items()))
            for field, counts in sorted(field_counts.items())
        },
        "context_likely_needed_rate_in_purposive_sample": context_likely / reviewed_rows,
        "context_likely_needed_rows": context_likely,
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
        finding = (
            "同一标注者直接共选 neutral 与情绪并非少数，因此不能主要归因于跨标注者聚合。"
        )
        action = (
            "下一步优先做训练暴露与目标可学习性诊断，再决定是否调整监督目标或模型容量。"
        )

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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--config-sha256", required=True)
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    if sha256_file(config_path) != args.config_sha256:
        raise RuntimeError("Config SHA-256 mismatch")
    config = read_json(config_path)
    validate_implementation(config)
    run_dir = resolve_project_path(config["outputs"]["run_dir"])
    aggregate = read_json(run_dir / "aggregate-summary.json")
    manifest = read_csv(run_dir / "sample-manifest.csv")
    review_path = run_dir / "private" / "manual-review.private.csv"
    review = read_csv(review_path)

    output_paths = [
        run_dir / "manual-annotations.csv",
        run_dir / "qualitative-summary.json",
        run_dir / "REPORT.md",
        run_dir / "completion.json",
    ]
    if any(path.exists() for path in output_paths):
        raise RuntimeError("EXP-035 finalization output already exists")

    public_rows, qualitative = validate_review(manifest, review, config["coding"])
    write_csv(
        run_dir / "manual-annotations.csv",
        public_rows,
        [
            "sample_id",
            "sample_role",
            "source_train_row",
            "aggregation_only",
            "gold_cardinality",
            "standalone_decidability",
            "label_coherence",
            "context_trigger",
            "annotation_interpretation",
            "reviewer_confidence",
        ],
    )
    write_json(run_dir / "qualitative-summary.json", qualitative)
    (run_dir / "REPORT.md").write_text(
        render_report(aggregate, qualitative), encoding="utf-8"
    )
    completion = {
        "artifacts": {
            name: artifact_record(run_dir / name)
            for name in [
                "REPORT.md",
                "manual-annotations.csv",
                "qualitative-summary.json",
            ]
        },
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": {
            "path": str(config_path.relative_to(PROJECT_ROOT)),
            "sha256": args.config_sha256,
        },
        "experiment_id": config["experiment_id"],
        "private_review": artifact_record(review_path),
        "reviewed_rows": len(public_rows),
        "status": "CompletedAwaitingVerification",
        "test_accessed": False,
    }
    write_json(run_dir / "completion.json", completion)
    print(
        json.dumps(
            {
                "experiment_id": config["experiment_id"],
                "reviewed_rows": len(public_rows),
                "status": completion["status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
