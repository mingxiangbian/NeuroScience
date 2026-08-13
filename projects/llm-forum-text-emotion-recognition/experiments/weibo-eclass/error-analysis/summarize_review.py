#!/usr/bin/env python3
"""Validate EXP-048 coding and finalize its public report."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import analyze_frozen_dev_errors as analysis


DEFAULT_CONFIG = analysis.DEFAULT_CONFIG


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def validate_annotations(
    manifest: list[dict[str, str]],
    annotations: list[dict[str, str]],
    config: dict[str, Any],
) -> None:
    if not manifest or len(manifest) != len(annotations):
        raise ValueError("Manifest and annotation rows differ")
    identity_fields = ["sample_rank", "case_id", "role", "gold_label"]
    if [[row[field] for field in identity_fields] for row in manifest] != [
        [row[field] for field in identity_fields] for row in annotations
    ]:
        raise ValueError("Annotation identities differ from frozen sample manifest")
    forbidden = {
        "sample_id",
        "group_id",
        "text",
        "target",
        "previous",
        "raw_output",
        "reasoning",
        "note",
        "notes",
        "rationale",
    }
    if forbidden & set(manifest[0]) or forbidden & set(annotations[0]):
        raise ValueError("A public qualitative table contains a private column")

    allowed_flags = set(config["annotation"]["allowed_evidence_flags"])
    allowed_sources = set(config["annotation"]["allowed_primary_sources"])
    allowed_confidence = set(config["annotation"]["confidence_levels"])
    long_tail_by_case = {row["case_id"]: row["long_tail"] == "true" for row in manifest}
    for row in annotations:
        flags = row["evidence_flags"].split("|") if row["evidence_flags"] else []
        if not flags or len(flags) != len(set(flags)) or not set(flags) <= allowed_flags:
            raise ValueError(f"Invalid evidence flags for {row['case_id']}")
        if "none_observed" in flags and len(flags) != 1:
            raise ValueError(f"none_observed must stand alone for {row['case_id']}")
        if ("long_tail_class" in flags) != long_tail_by_case[row["case_id"]]:
            raise ValueError(f"Long-tail flag mismatch for {row['case_id']}")
        if row["primary_possible_source"] not in allowed_sources:
            raise ValueError(f"Invalid primary source for {row['case_id']}")
        if row["reviewer_confidence"] not in allowed_confidence:
            raise ValueError(f"Invalid reviewer confidence for {row['case_id']}")


def count_annotations(
    annotations: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output: list[dict[str, Any]] = []

    def add(dimension: str, group: str, values: list[str], denominator: int) -> None:
        for value, count in sorted(Counter(values).items()):
            output.append(
                {
                    "dimension": dimension,
                    "group": group,
                    "value": value,
                    "count": count,
                    "denominator": denominator,
                    "proportion": analysis.fmt(count / denominator),
                }
            )

    flags = [flag for row in annotations for flag in row["evidence_flags"].split("|")]
    add("evidence_flag", "ALL", flags, len(annotations))
    add(
        "primary_possible_source",
        "ALL",
        [row["primary_possible_source"] for row in annotations],
        len(annotations),
    )
    add(
        "reviewer_confidence",
        "ALL",
        [row["reviewer_confidence"] for row in annotations],
        len(annotations),
    )
    add("role", "ALL", [row["role"] for row in annotations], len(annotations))
    roles = sorted({row["role"] for row in annotations})
    for role in roles:
        subset = [row for row in annotations if row["role"] == role]
        add(
            "evidence_flag_by_role",
            role,
            [flag for row in subset for flag in row["evidence_flags"].split("|")],
            len(subset),
        )
        add(
            "primary_source_by_role",
            role,
            [row["primary_possible_source"] for row in subset],
            len(subset),
        )
    return output, {
        "annotation_count": len(annotations),
        "evidence_flag_counts": dict(sorted(Counter(flags).items())),
        "primary_possible_source_counts": dict(
            sorted(Counter(row["primary_possible_source"] for row in annotations).items())
        ),
        "reviewer_confidence_counts": dict(
            sorted(Counter(row["reviewer_confidence"] for row in annotations).items())
        ),
        "role_counts": dict(sorted(Counter(row["role"] for row in annotations).items())),
    }


def mean_slice(
    rows: list[dict[str, str]], condition_id: str, slice_id: str, metric: str
) -> float:
    values = [
        float(row[metric])
        for row in rows
        if row["condition_id"] == condition_id and row["slice"] == slice_id
    ]
    if not values:
        raise ValueError(f"Missing slice {condition_id}/{slice_id}/{metric}")
    return statistics.fmean(values)


def transition_counts(rows: list[dict[str, str]], comparison_id: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        if row["comparison_id"] == comparison_id:
            counts[row["transition"]] += int(row["row_count"])
    return counts


def render_report(
    aggregate: dict[str, Any],
    attribution: dict[str, Any],
    class_gap: list[dict[str, str]],
    confusion: list[dict[str, str]],
    slices: list[dict[str, str]],
    transitions: list[dict[str, str]],
    agreement: list[dict[str, str]],
    qualitative: dict[str, Any],
) -> str:
    summaries = aggregate["conditions"]
    ref = summaries["reference"]
    lora = summaries["lora"]
    encoder = summaries["encoder"]
    encoder_to_lora = transition_counts(transitions, "encoder_to_lora")
    reference_to_lora = transition_counts(transitions, "reference_to_lora")
    worst_gaps = sorted(class_gap, key=lambda row: float(row["lora_minus_encoder_f1"]))[:4]
    best_gaps = sorted(class_gap, key=lambda row: -float(row["lora_minus_encoder_f1"]))[:3]

    def top_confusions(condition_id: str, limit: int = 5) -> list[dict[str, str]]:
        rows = [row for row in confusion if row["condition_id"] == condition_id]
        return sorted(rows, key=lambda row: -float(row["count_mean"]))[:limit]

    lora_agreement = [row for row in agreement if row["condition_id"] == "lora"]
    encoder_agreement = [row for row in agreement if row["condition_id"] == "encoder"]
    failed = attribution["slices"]["reference_output_failed"]
    valid = attribution["slices"]["reference_output_valid"]
    lines = [
        "# EXP-048 Frozen Weibo EClass Dev Error Analysis",
        "",
        "Status: `Completed; verification pending`",
        "",
        "## 范围",
        "",
        "本报告只分析 EXP-042 与 EXP-047 已冻结的 1,272 条 validation 预测。没有重新训练、",
        "推理、改 prompt、选 checkpoint 或读取 sealed test。定性部分使用在读原文前冻结的",
        f"{qualitative['annotation_count']} 条匿名案例；其计数不能外推为 validation 总体发生率。",
        "",
        "## 整体结果",
        "",
        "| Condition | Accuracy | Macro-P | Macro-R | Macro-F1 | Weighted-F1 | Failed output |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| Matched no-adapter reference | {ref['accuracy_mean']:.3f} | {ref['macro_precision_mean']:.3f} | {ref['macro_recall_mean']:.3f} | {ref['macro_f1_mean']:.3f} | {ref['weighted_f1_mean']:.3f} | {ref['failed_output_rate_mean']:.3f} |",
        f"| Qwen3-4B LoRA, 3-seed mean | {lora['accuracy_mean']:.3f} | {lora['macro_precision_mean']:.3f} | {lora['macro_recall_mean']:.3f} | {lora['macro_f1_mean']:.3f} | {lora['weighted_f1_mean']:.3f} | {lora['failed_output_rate_mean']:.3f} |",
        f"| Chinese encoder, 3-seed mean | {encoder['accuracy_mean']:.3f} | {encoder['macro_precision_mean']:.3f} | {encoder['macro_recall_mean']:.3f} | {encoder['macro_f1_mean']:.3f} | {encoder['weighted_f1_mean']:.3f} | {encoder['failed_output_rate_mean']:.3f} |",
        "",
        f"LoRA 相对 matched reference 的 Macro-F1 提高 `{lora['macro_f1_mean'] - ref['macro_f1_mean']:+.3f}`，",
        f"但仍比 encoder 低 `{lora['macro_f1_mean'] - encoder['macro_f1_mean']:+.3f}`。Accuracy 上 LoRA",
        f"与 encoder 的差为 `{lora['accuracy_mean'] - encoder['accuracy_mean']:+.3f}`，说明两者总体",
        "命中率接近，但少数类表现和跨 seed 稳定性不同。",
        "",
        "## 格式恢复与分类收益",
        "",
        f"Reference 有 `{failed['rows']}` 条输出失败，其中包括无效 parse 或 likely-truncated；",
        f"该 slice 的 reference Accuracy 为 `{failed['reference_accuracy']:.3f}`，LoRA 三 seed 均值为",
        f"`{failed['lora_accuracy_mean']:.3f}`。其中 `{attribution['failed_output_stable_lora_recoveries']}` 条",
        "被 3/3 LoRA seed 稳定恢复。",
        "",
        f"在剩余 `{valid['rows']}` 条 reference 输出有效的样本上，LoRA Accuracy 仍从",
        f"`{valid['reference_accuracy']:.3f}` 提高到 `{valid['lora_accuracy_mean']:.3f}`，Macro-F1 从",
        f"`{valid['reference_macro_f1']:.3f}` 提高到 `{valid['lora_macro_f1_mean']:.3f}`；并有",
        f"`{attribution['valid_reference_stable_lora_recoveries']}` 条有效但错误的 reference 结果被",
        "3/3 LoRA seed 稳定恢复。因此，EXP-047 的提升不只是消除 116 条格式失败。",
        "",
        f"从 Accuracy 的加性分解看，failed-output slice 贡献 `{failed['weighted_accuracy_delta_contribution']:+.3f}`，",
        f"valid-output slice 贡献 `{valid['weighted_accuracy_delta_contribution']:+.3f}`，合计",
        f"`{attribution['additive_contribution_check']:+.3f}`。Macro-F1 不可这样相加，本报告不作",
        "伪分解。failed-output 行上的恢复也同时可能包含标签变化，不能被写成纯格式因果效应。",
        "",
        "## LoRA 与 encoder 的剩余差距",
        "",
        "LoRA 相对 encoder 的最大逐类 F1 劣势：",
        "",
        "| Label | Support | LoRA F1 | Encoder F1 | LoRA - Encoder |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in worst_gaps:
        lines.append(
            f"| {row['label']} | {row['support']} | {float(row['lora_f1_mean']):.3f} | {float(row['encoder_f1_mean']):.3f} | {float(row['lora_minus_encoder_f1']):+.3f} |"
        )
    lines.extend(
        [
            "",
            "LoRA 相对 encoder 的优势或最小劣势：",
            "",
            "| Label | Support | LoRA F1 | Encoder F1 | LoRA - Encoder |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in best_gaps:
        lines.append(
            f"| {row['label']} | {row['support']} | {float(row['lora_f1_mean']):.3f} | {float(row['encoder_f1_mean']):.3f} | {float(row['lora_minus_encoder_f1']):+.3f} |"
        )
    lines.extend(
        [
            "",
            "最常见的 LoRA 错误对：",
            "",
            "| Gold -> prediction | Mean count across seeds |",
            "| --- | ---: |",
        ]
    )
    for row in top_confusions("lora"):
        lines.append(f"| {row['gold']} -> {row['prediction']} | {float(row['count_mean']):.1f} |")
    lines.extend(
        [
            "",
            "`no_emotion` 是 881/1,272 的多数类，因此大量 minority -> no_emotion 混淆会让",
            "Accuracy 看起来仍高，却显著压低 Macro-F1。是否属于 `no_emotion`、`neutral`、",
            "`positive/negative` 或具体情绪的边界也不是纯粹的情绪极性判断。",
            "",
            "关键切片的三 seed Macro-F1 均值：",
            "",
            "| Slice | LoRA | Encoder | LoRA - Encoder |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for slice_id in ["no_emotion", "emotion_label", "long_tail_label", "ambiguous_target", "unambiguous_target"]:
        lora_value = mean_slice(slices, "lora", slice_id, "macro_f1")
        encoder_value = mean_slice(slices, "encoder", slice_id, "macro_f1")
        lines.append(f"| `{slice_id}` | {lora_value:.3f} | {encoder_value:.3f} | {lora_value - encoder_value:+.3f} |")
    lines.extend(
        [
            "",
            "单类或小切片上的 Macro-F1 会包含许多零 support 类，主要用于相同 slice 上的配对",
            "描述，不应当作独立 benchmark。",
            "",
            "## 跨 seed 与跨模型转移",
            "",
            f"相对 encoder，LoRA 有 `{encoder_to_lora['stable_recovery']}` 条 0/3 -> 3/3 稳定恢复，",
            f"也有 `{encoder_to_lora['stable_regression']}` 条 3/3 -> 0/3 稳定回退。相对 reference，",
            f"对应数字为 `{reference_to_lora['stable_recovery']}` 与 `{reference_to_lora['stable_regression']}`。",
            "这说明 LoRA 不是把 encoder 的决策整体复制过来，而是形成了不同的错误结构。",
            "",
            f"LoRA seed 两两最终标签一致率均值为 `{statistics.fmean(float(row['exact_prediction_agreement']) for row in lora_agreement):.3f}`，",
            f"encoder 为 `{statistics.fmean(float(row['exact_prediction_agreement']) for row in encoder_agreement):.3f}`。",
            "少数类 support 小，三组 LoRA seed 的逐类波动不能忽略；论文应继续报告 mean +/- SD，",
            "不能只展示 seed 44。",
            "",
            "## 定性编码",
            "",
            f"共审阅 `{qualitative['annotation_count']}` 条预先抽取案例。Evidence flags 可以重叠：",
            "",
            "| Possible factor | Cases |",
            "| --- | ---: |",
        ]
    )
    for flag, count in sorted(qualitative["evidence_flag_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| `{flag}` | {count} |")
    lines.extend(["", "| Primary possible source | Cases |", "| --- | ---: |"])
    for source, count in sorted(qualitative["primary_possible_source_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| `{source}` | {count} |")
    lines.extend(
        [
            "",
            "定性代码只表达一位审阅者对所选案例的可能解释。它不能更改数据集标签，也不能证明",
            "模型内部采用了某种情绪机制。尤其 `ambiguous_target` 是上游结构化标志，而",
            "`annotation_ambiguity` 是本次人工判断，两者不可互换。",
            "",
            "## 结论与边界",
            "",
            "1. LoRA 的提升同时包含格式/可用输出恢复和有效 reference 行上的真实标签行为改善。",
            "2. LoRA 与 encoder 的 Accuracy 接近，但 Macro-F1 仍低，差距集中在少数类和类别边界。",
            "3. 三 seed 的错误并不完全稳定，最终论文必须保留波动与逐类指标。",
            "4. 本次结果只支持行为层错误解释，不支持 hidden-state 或人类情绪机制结论。",
            "",
            "EXP-048 不授权据此修改模型或访问 test。下一步应基于已冻结 validation 证据形成",
            "TEST-READY 候选清单；若要新增消融或迁移，必须先登记新的实验。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = analysis.read_json(args.config.resolve())
    output_dir = analysis.project_path(config["output_dir"])
    final_targets = [
        output_dir / "qualitative_counts.csv",
        output_dir / "qualitative_summary.json",
        output_dir / "REPORT.md",
        output_dir / "manual_review.json",
    ]
    if any(path.exists() for path in final_targets):
        raise FileExistsError("A final review output already exists")
    run_path = output_dir / "run.json"
    run = analysis.read_json(run_path)
    if run.get("status") != "AwaitingManualReview" or run.get("test_accessed"):
        raise ValueError("EXP-048 is not ready for manual-review finalization")

    manifest = load_csv(output_dir / "sample_manifest.csv")
    annotations = load_csv(output_dir / "manual_annotations.csv")
    validate_annotations(manifest, annotations, config)
    count_rows, summary = count_annotations(annotations)
    analysis.write_csv(
        output_dir / "qualitative_counts.csv",
        ["dimension", "group", "value", "count", "denominator", "proportion"],
        count_rows,
    )
    analysis.write_json(output_dir / "qualitative_summary.json", summary)

    aggregate = analysis.read_json(output_dir / "aggregate_summary.json")
    attribution = analysis.read_json(output_dir / "format_attribution.json")
    report = render_report(
        aggregate,
        attribution,
        load_csv(output_dir / "class_gap.csv"),
        load_csv(output_dir / "confusion_pairs.csv"),
        load_csv(output_dir / "slice_metrics.csv"),
        load_csv(output_dir / "pairwise_transitions.csv"),
        load_csv(output_dir / "seed_agreement.csv"),
        summary,
    )
    (output_dir / "REPORT.md").write_text(report, encoding="utf-8")
    review = {
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": config["experiment_id"],
        "qualitative_summary": summary,
        "reviewer_count": 1,
        "sampling_boundary": "stratified purposive sample; not a prevalence estimate",
        "status": "Completed",
    }
    analysis.write_json(output_dir / "manual_review.json", review)

    run["status"] = "CompletedAwaitingVerification"
    run["reviewed_rows"] = len(annotations)
    run["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    run["artifacts"] = {
        path.name: analysis.artifact_record(path)
        for path in sorted(output_dir.iterdir())
        if path.is_file() and path.name != "run.json"
    }
    analysis.write_json(run_path, run)
    print(json.dumps({"experiment_id": config["experiment_id"], "reviewed_rows": len(annotations), "status": run["status"]}, indent=2))


if __name__ == "__main__":
    main()
