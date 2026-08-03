#!/usr/bin/env python3
"""Validate EXP-030 qualitative coding and build the public report."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import time
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
    labels: list[str],
    support: dict[int, int],
) -> None:
    forbidden_columns = {
        "text",
        "comment",
        "comment_id",
        "content",
        "raw_text",
        "note",
        "notes",
        "rationale",
    }
    if not manifest or not annotations:
        raise ValueError("Missing qualitative rows")
    if forbidden_columns.intersection(manifest[0]) or forbidden_columns.intersection(
        annotations[0]
    ):
        raise ValueError("A public CSV contains a forbidden raw-text column")
    if len(manifest) != len(annotations):
        raise ValueError("Manifest and annotation row counts differ")

    manifest_identity = [
        (row["sample_rank"], row["role"], row["row_number"], row["gold_labels"])
        for row in manifest
    ]
    annotation_identity = [
        (row["sample_rank"], row["role"], row["row_number"], row["gold_labels"])
        for row in annotations
    ]
    if manifest_identity != annotation_identity:
        raise ValueError("Annotation identity or order differs from sample manifest")

    allowed_flags = set(config["annotation"]["allowed_evidence_flags"])
    allowed_sources = set(config["annotation"]["allowed_primary_sources"])
    allowed_confidence = set(config["annotation"]["confidence_levels"])
    long_tail_ids = {
        label_id
        for label_id, count in support.items()
        if count < config["sampling"]["long_tail_support_below"]
    }
    for row in annotations:
        flags = row["evidence_flags"].split("|") if row["evidence_flags"] else []
        if not flags or len(flags) != len(set(flags)):
            raise ValueError(f"Missing or duplicate flags for row {row['row_number']}")
        if not set(flags).issubset(allowed_flags):
            raise ValueError(f"Unknown evidence flag for row {row['row_number']}")
        if row["primary_possible_source"] not in allowed_sources:
            raise ValueError(f"Unknown primary source for row {row['row_number']}")
        if row["reviewer_confidence"] not in allowed_confidence:
            raise ValueError(f"Unknown reviewer confidence for row {row['row_number']}")
        gold_ids = {labels.index(label) for label in row["gold_labels"].split("|")}
        if ("minority_class" in flags) != bool(gold_ids & long_tail_ids):
            raise ValueError(f"Long-tail flag mismatch for row {row['row_number']}")
        if ("label_overlap" in flags) != (len(gold_ids) > 1):
            raise ValueError(f"Multi-label overlap flag mismatch for row {row['row_number']}")


def count_annotations(
    annotations: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add_counts(dimension: str, group: str, values: list[str]) -> None:
        denominator = len(
            annotations if group == "ALL" else [row for row in annotations if row["role"] == group]
        )
        for value, count in sorted(Counter(values).items()):
            rows.append(
                {
                    "dimension": dimension,
                    "group": group,
                    "value": value,
                    "count": count,
                    "denominator": denominator,
                    "proportion": analysis.fmt(count / denominator),
                }
            )

    roles = Counter(row["role"] for row in annotations)
    all_flags = [
        flag for row in annotations for flag in row["evidence_flags"].split("|")
    ]
    add_counts("evidence_flag", "ALL", all_flags)
    add_counts(
        "primary_possible_source",
        "ALL",
        [row["primary_possible_source"] for row in annotations],
    )
    add_counts(
        "reviewer_confidence",
        "ALL",
        [row["reviewer_confidence"] for row in annotations],
    )
    add_counts("role", "ALL", [row["role"] for row in annotations])
    for role in sorted(roles):
        subset = [row for row in annotations if row["role"] == role]
        add_counts(
            "evidence_flag_by_role",
            role,
            [flag for row in subset for flag in row["evidence_flags"].split("|")],
        )
        add_counts(
            "primary_source_by_role",
            role,
            [row["primary_possible_source"] for row in subset],
        )

    summary = {
        "annotation_count": len(annotations),
        "evidence_flag_counts": dict(sorted(Counter(all_flags).items())),
        "primary_possible_source_counts": dict(
            sorted(Counter(row["primary_possible_source"] for row in annotations).items())
        ),
        "reviewer_confidence_counts": dict(
            sorted(Counter(row["reviewer_confidence"] for row in annotations).items())
        ),
        "role_counts": dict(sorted(roles.items())),
    }
    return rows, summary


def grouped_rows(rows: list[dict[str, str]], condition_id: str) -> list[dict[str, str]]:
    return [row for row in rows if row["condition_id"] == condition_id]


def mean_slice(
    slice_rows: list[dict[str, str]], condition_id: str, slice_id: str
) -> dict[str, float]:
    selected = [
        row
        for row in slice_rows
        if row["condition_id"] == condition_id and row["slice"] == slice_id
    ]
    if not selected:
        raise ValueError(f"Missing slice {condition_id}/{slice_id}")
    return {
        "row_count": float(selected[0]["row_count"]),
        "exact": statistics.fmean(float(row["exact_match_accuracy"]) for row in selected),
        "precision": statistics.fmean(float(row["samples_precision"]) for row in selected),
        "recall": statistics.fmean(float(row["samples_recall"]) for row in selected),
        "f1": statistics.fmean(float(row["samples_f1"]) for row in selected),
        "predicted_cardinality": statistics.fmean(
            float(row["predicted_cardinality_mean"]) for row in selected
        ),
    }


def macro_prf(
    per_label_rows: list[dict[str, str]], condition_id: str
) -> tuple[float, float, float]:
    selected = grouped_rows(per_label_rows, condition_id)
    return (
        statistics.fmean(float(row["precision_mean"]) for row in selected),
        statistics.fmean(float(row["recall_mean"]) for row in selected),
        statistics.fmean(float(row["f1_mean"]) for row in selected),
    )


def transition_counts(rows: list[dict[str, str]], comparison_id: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        if row["comparison_id"] == comparison_id:
            counts[row["transition"]] += int(row["row_count"])
    return counts


def top_pairs(
    rows: list[dict[str, str]], condition_id: str, limit: int = 5
) -> list[dict[str, str]]:
    selected = grouped_rows(rows, condition_id)
    return sorted(selected, key=lambda row: -int(row["pair_count"]))[:limit]


def git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=analysis.REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def pct(value: float) -> str:
    return f"{100 * value:.2f}%"


def render_report(
    aggregate: dict[str, Any],
    official: dict[str, Any],
    slice_rows: list[dict[str, str]],
    per_label_rows: list[dict[str, str]],
    pair_rows: list[dict[str, str]],
    transition_rows: list[dict[str, str]],
    qualitative: dict[str, Any],
) -> str:
    condition_names = {
        "exp-020-bert": "EXP-020 BERT",
        "exp-025-frozen-qwen": "EXP-025 frozen Qwen",
        "exp-029-lora-qwen": "EXP-029 LoRA Qwen",
    }
    condition_summary = aggregate["condition_summary"]
    condition_stats: dict[str, dict[str, float]] = {}
    for condition_id in condition_names:
        macro_precision, macro_recall, macro_f1 = macro_prf(per_label_rows, condition_id)
        condition_stats[condition_id] = {
            "macro_precision": macro_precision,
            "macro_recall": macro_recall,
            "macro_f1": macro_f1,
            "exact": condition_summary[condition_id]["exact_match_accuracy_mean"],
            "samples_f1": condition_summary[condition_id]["samples_f1_mean"],
            "cardinality": condition_summary[condition_id]["predicted_cardinality_mean"],
        }

    per_condition_label = {
        condition_id: {row["label"]: row for row in grouped_rows(per_label_rows, condition_id)}
        for condition_id in condition_names
    }
    label_gaps = []
    for label, bert_row in per_condition_label["exp-020-bert"].items():
        lora_row = per_condition_label["exp-029-lora-qwen"][label]
        label_gaps.append(
            {
                "label": label,
                "support": int(bert_row["support"]),
                "bert": float(bert_row["f1_mean"]),
                "lora": float(lora_row["f1_mean"]),
                "gap": float(bert_row["f1_mean"]) - float(lora_row["f1_mean"]),
            }
        )
    bert_advantages = sorted(label_gaps, key=lambda row: (-row["gap"], row["label"]))[:8]
    lora_advantages = sorted(label_gaps, key=lambda row: (row["gap"], row["label"]))[:5]

    bert_to_lora = transition_counts(transition_rows, "bert_to_lora")
    frozen_to_lora = transition_counts(transition_rows, "frozen_qwen_to_lora")
    bert_improved = bert_to_lora["stable_recovery"] + bert_to_lora["higher_correct_rate"]
    bert_worsened = bert_to_lora["stable_regression"] + bert_to_lora["lower_correct_rate"]
    frozen_improved = frozen_to_lora["stable_recovery"] + frozen_to_lora["higher_correct_rate"]
    frozen_worsened = frozen_to_lora["stable_regression"] + frozen_to_lora["lower_correct_rate"]

    lines = [
        "# EXP-030 Frozen GoEmotions Dev Error Analysis",
        "",
        "Status: `Completed; verification pending`",
        "",
        "## 范围",
        "",
        "本报告只分析 EXP-020、EXP-025 和 EXP-029 已冻结的 GoEmotions dev 预测。",
        "没有重新训练、推理、选 seed、调阈值或读取 test。全部 5,426 条 dev 样本进入",
        "定量分析；定性部分使用在读原文前冻结的 48 条匿名样本。",
        "",
        "多 seed 条件中的 `stable correct` 指 3/3 seed 都精确匹配完整标签集合；",
        "`stable wrong` 指 0/3 精确匹配。它们不是 ensemble 指标。",
        "",
        "## 整体行为",
        "",
        "| Condition | Macro-P | Macro-R | Macro-F1 | Exact-match | Samples-F1 | Predicted labels/row |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for condition_id, name in condition_names.items():
        stats = condition_stats[condition_id]
        lines.append(
            f"| {name} | {stats['macro_precision']:.3f} | {stats['macro_recall']:.3f} | "
            f"{stats['macro_f1']:.3f} | {stats['exact']:.3f} | {stats['samples_f1']:.3f} | "
            f"{stats['cardinality']:.3f} |"
        )
    lines.extend(
        [
            "",
            f"Gold 平均每行有 `{aggregate['gold_cardinality_mean']:.3f}` 个标签。LoRA 的严格 "
            f"exact-match (`{condition_stats['exp-029-lora-qwen']['exact']:.3f}`) 高于 BERT "
            f"(`{condition_stats['exp-020-bert']['exact']:.3f}`)，但 Macro-F1 低 "
            f"`{condition_stats['exp-020-bert']['macro_f1'] - condition_stats['exp-029-lora-qwen']['macro_f1']:.3f}`。",
            "这不是矛盾：LoRA 更保守，平均只输出约一个标签，因而在占多数的单标签样本上",
            "更容易得到完整集合正确；Macro-F1 则揭示它对各类别、尤其第二个标签的召回不足。",
            "",
            "## 多标签与输出策略",
            "",
            "| Slice | Rows | BERT exact | Frozen Qwen exact | LoRA exact | BERT samples-F1 | LoRA samples-F1 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for slice_id in [
        "single_label",
        "any_multilabel",
        "neutral_cooccurrence",
        "emotion_only_multilabel",
        "long_tail_label",
    ]:
        bert = mean_slice(slice_rows, "exp-020-bert", slice_id)
        frozen = mean_slice(slice_rows, "exp-025-frozen-qwen", slice_id)
        lora = mean_slice(slice_rows, "exp-029-lora-qwen", slice_id)
        lines.append(
            f"| `{slice_id}` | {int(bert['row_count'])} | {bert['exact']:.3f} | "
            f"{frozen['exact']:.3f} | {lora['exact']:.3f} | {bert['f1']:.3f} | {lora['f1']:.3f} |"
        )
    neutral_rows = aggregate["neutral_cooccurrence_rows"]
    lines.extend(
        [
            "",
            f"冻结的 Qwen decoder 禁止 `neutral` 与情绪标签共现，因此 `{neutral_rows}` 条",
            "gold 共现样本对 EXP-025/029 的 exact-match 在结构上不可达；两者在该 slice 上均为 0。",
            "这些样本没有被删除。该限制最多直接压低约 "
            f"`{neutral_rows / aggregate['row_count']:.3f}` 的总体 exact-match，但不能单独解释",
            "LoRA 的 Macro-F1 差距，因为 Macro-F1 还取决于全部标签的 TP/FP/FN。",
            "",
            "LoRA 每 seed 平均约有 "
            f"`{condition_summary['exp-029-lora-qwen']['error_mode_mean_counts']['underprediction_only']:.1f}` 条",
            "纯漏标错误，却只有 "
            f"`{condition_summary['exp-029-lora-qwen']['error_mode_mean_counts']['overprediction_only']:.1f}` 条",
            "纯多报错误；其主要剩余错误是漏掉第二个标签或用另一个相邻标签替换 gold。",
            "",
            "## 类别差异",
            "",
            "BERT 相对 LoRA 的最大逐类 F1 优势如下：",
            "",
            "| Label | Support | BERT F1 | LoRA F1 | BERT - LoRA |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in bert_advantages:
        lines.append(
            f"| {row['label']} | {row['support']} | {row['bert']:.3f} | {row['lora']:.3f} | {row['gap']:+.3f} |"
        )
    lines.extend(
        [
            "",
            "LoRA 也并非对所有类别都更差；其最大的相对优势为：",
            "",
            "| Label | Support | BERT F1 | LoRA F1 | BERT - LoRA |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in lora_advantages:
        lines.append(
            f"| {row['label']} | {row['support']} | {row['bert']:.3f} | {row['lora']:.3f} | {row['gap']:+.3f} |"
        )
    lines.extend(
        [
            "",
            "这些是同一 dev 上的描述性差异。少数类 support 很小，单类差值不能当作稳定的",
            "总体优劣证据，也不能据此挑 seed。",
            "",
            "最常见的 missed-to-spurious 标签对按 model-run-row 计数如下：",
            "",
            "| Condition | Missed -> spurious | Count |",
            "| --- | --- | ---: |",
        ]
    )
    for condition_id, name in condition_names.items():
        for row in top_pairs(pair_rows, condition_id, 3):
            lines.append(
                f"| {name} | {row['missed_label']} -> {row['spurious_label']} | {row['pair_count']} |"
            )
    lines.extend(
        [
            "",
            "`neutral` 与 approval/annoyance/disapproval/curiosity 等相邻判断频繁互换，说明错误",
            "不仅来自类别频率，也来自表达是否被视为带有情绪，以及细粒度标签边界。",
            "",
            "## 跨模型转移与稳定性",
            "",
            f"相对 BERT，LoRA 有 `{bert_improved}` 条样本的 exact-correct seed 比例提高，",
            f"`{bert_worsened}` 条降低；其中完整 0/3 -> 3/3 恢复 `{bert_to_lora['stable_recovery']}` 条，",
            f"3/3 -> 0/3 回退 `{bert_to_lora['stable_regression']}` 条。",
            "这解释了 LoRA 为何能在总体 exact-match 上领先，但不代表它的类别召回更好。",
            "",
            f"相对 frozen Qwen，LoRA 有 `{frozen_improved}` 条提高、`{frozen_worsened}` 条降低；",
            f"其中稳定恢复 `{frozen_to_lora['stable_recovery']}` 条。LoRA 的收益因此不是只修复 JSON",
            "格式，而是大范围改变了标签行为。",
            "",
            f"三种条件共同稳定判错 `{aggregate['shared_stable_error_rows']}` 条，约占 dev 的 "
            f"`{pct(aggregate['shared_stable_error_rows'] / aggregate['row_count'])}`。这是一组任务级难例，",
            "但其中仍混有标签歧义、缺失上下文和相邻类别，不应直接归因于共同的模型机制缺陷。",
            "",
            "## 定性编码",
            "",
            "48 条样本按六个预注册角色各取 8 条。证据 flags 可重叠：",
            "",
            "| Possible factor | Cases |",
            "| --- | ---: |",
        ]
    )
    for flag, count in sorted(
        qualitative["evidence_flag_counts"].items(), key=lambda item: (-item[1], item[0])
    ):
        lines.append(f"| `{flag}` | {count} |")
    lines.extend(
        [
            "",
            "| Primary possible source | Cases |",
            "| --- | ---: |",
        ]
    )
    for source, count in sorted(
        qualitative["primary_possible_source_counts"].items(),
        key=lambda item: (-item[1], item[0]),
    ):
        lines.append(f"| `{source}` | {count} |")
    lines.extend(
        [
            "",
            "高频现象是 lexical cue conflict、annotation ambiguity、mixed emotion 和 label overlap。",
            "例如同一句话可同时支持 caring/optimism、anger/annoyance 或 admiration/approval；另一些",
            "文本依赖被省略的论坛上下文，或包含否定、反讽和网络表达。定性样本被刻意富集为错误",
            "与模型转移案例，因此这些计数不能外推为 5,426 条 dev 的总体发生率。",
            "",
            "## 官方结果边界",
            "",
            "GoEmotions 论文没有发布可与本地 dev 对齐的 validation accuracy。论文 Table 4 的",
            f"完整 28 类 BERT Macro-P/R/F1 为 `{official['test_macro_precision']:.2f}`/"
            f"`{official['test_macro_recall']:.2f}`/`{official['test_macro_f1']:.2f}`，对应最终 test，",
            "不是 validation。官方仓库的代码可以计算 strict multi-label accuracy，但没有给出一个",
            "固定的官方 dev accuracy 数字。",
            "",
            f"本地 EXP-020 dev Macro-F1 为 `{official['local_exp020_dev_macro_f1_mean']:.3f} +/- "
            f"{official['local_exp020_dev_macro_f1_sample_std']:.3f}`，比官方 test 表中的 `0.46` 高 "
            f"`{official['local_dev_minus_official_test_macro_f1_reference']:.3f}`。由于 split、随机性和",
            "实现并未对齐，这只能说明本地结果处于相近尺度，不能写成超过官方或正式复现差值。",
            "",
            "## 结论与下一步边界",
            "",
            "1. LoRA 已大幅修复 frozen Qwen，但主要形成高 precision、低 cardinality 的保守分类器。",
            "2. BERT 的优势主要体现在多标签覆盖与类别召回；LoRA 的高 exact-match 受单标签占多数影响。",
            "3. neutral 共现禁令是一个已确认的结构性误差源，值得单独预注册 decoder/target ablation。",
            "4. 标签重叠、标注不确定性和缺失上下文同样重要，不能把所有错误归因于模型容量。",
            "",
            "任何新 decoder、阈值、LoRA 配置或上下文实验都必须使用新 EXP 编号和预注册规则。",
            "EXP-030 不打开 test gate，也不把定性判断写成机制解释。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    started = time.perf_counter()
    config_path = args.config.resolve()
    config = analysis.read_json(config_path)
    output_dir = analysis.project_path(config["output_dir"])
    targets = [
        output_dir / "qualitative_counts.csv",
        output_dir / "qualitative_summary.json",
        output_dir / "manual_review.json",
        output_dir / "REPORT.md",
        output_dir / "run.json",
    ]
    if any(path.exists() for path in targets):
        raise FileExistsError("A review output already exists")

    analysis_manifest = analysis.read_json(output_dir / "analysis_manifest.json")
    if analysis_manifest.get("status") != "AwaitingManualReview":
        raise ValueError("Analysis manifest is not awaiting manual review")
    if analysis.project_path(config["data"]["test_path"]).exists():
        raise ValueError("GoEmotions test file unexpectedly exists")

    labels_path = analysis.verify_file(config["data"]["labels"])
    dev_path = analysis.verify_file(config["data"]["dev"])
    labels = analysis.load_labels(labels_path, config["data"]["labels"]["count"])
    dev_rows = analysis.load_dev(dev_path, labels, config["data"]["dev"]["rows"])
    support = Counter(label_id for row in dev_rows for label_id in row["gold_ids"])

    manifest_path = output_dir / "sample_manifest.csv"
    annotations_path = output_dir / "manual_annotations.csv"
    manifest = load_csv(manifest_path)
    annotations = load_csv(annotations_path)
    validate_annotations(manifest, annotations, config, labels, support)
    qualitative_rows, qualitative_summary = count_annotations(annotations)
    analysis.write_csv(
        output_dir / "qualitative_counts.csv",
        ["dimension", "group", "value", "count", "denominator", "proportion"],
        qualitative_rows,
    )
    analysis.write_json(output_dir / "qualitative_summary.json", qualitative_summary)

    aggregate = analysis.read_json(output_dir / "aggregate_summary.json")
    official = analysis.read_json(output_dir / "official_reference.json")
    slice_rows = load_csv(output_dir / "slice_metrics.csv")
    per_label_rows = load_csv(output_dir / "per_label_metrics.csv")
    pair_rows = load_csv(output_dir / "missed_spurious_pairs.csv")
    transition_rows = load_csv(output_dir / "pairwise_transitions.csv")
    report_path = output_dir / "REPORT.md"
    report_path.write_text(
        render_report(
            aggregate,
            official,
            slice_rows,
            per_label_rows,
            pair_rows,
            transition_rows,
            qualitative_summary,
        ),
        encoding="utf-8",
    )

    qualitative_artifacts = {
        name: analysis.artifact_record(output_dir / name)
        for name in [
            "manual_annotations.csv",
            "qualitative_counts.csv",
            "qualitative_summary.json",
            "REPORT.md",
        ]
    }
    manual_review = {
        "artifacts": qualitative_artifacts,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": config["experiment_id"],
        "qualitative_summary": qualitative_summary,
        "reviewer_count": 1,
        "sampling_boundary": "stratified purposive sample; not a prevalence estimate",
        "status": "Completed",
        "wall_seconds": time.perf_counter() - started,
    }
    analysis.write_json(output_dir / "manual_review.json", manual_review)

    public_artifacts = {
        path.name: analysis.artifact_record(path)
        for path in sorted(output_dir.iterdir())
        if path.is_file() and path.name not in {"run.json", "verification.json"}
    }
    private_path = output_dir / "private" / "selected_text.private.jsonl"
    dirty_lines = git_value("status", "--short").splitlines()
    run = {
        "accessed_splits": ["dev"],
        "api_cost_usd": 0,
        "artifacts": public_artifacts,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": analysis.artifact_record(config_path),
        "data": analysis_manifest["data"],
        "experiment_id": config["experiment_id"],
        "git": {
            "branch": git_value("branch", "--show-current"),
            "commit": git_value("rev-parse", "HEAD"),
            "dirty": bool(dirty_lines),
            "dirty_path_count": len(dirty_lines),
        },
        "implementation": {
            "analyzer": analysis.artifact_record(analysis.Path(analysis.__file__).resolve()),
            "summarizer": analysis.artifact_record(Path(__file__).resolve()),
        },
        "official_reference_boundary": official["comparison_boundary"],
        "prediction_artifacts": analysis_manifest["prediction_artifacts"],
        "privacy": {
            "private_selected_text": analysis.artifact_record(private_path),
            "public_raw_text": False,
            "public_upstream_comment_ids": False,
        },
        "protocol": analysis_manifest["protocol"],
        "reproduction_commands": [
            "python3 experiments/goemotions/error-analysis/analyze_frozen_dev_errors.py",
            "python3 experiments/goemotions/error-analysis/summarize_review.py",
            "python3 experiments/goemotions/error-analysis/verify_error_analysis.py",
        ],
        "reviewed_rows": len(annotations),
        "rq_ids": ["RQ-G1", "RQ-G2"],
        "source_verifications": analysis_manifest["source_verifications"],
        "split": "dev",
        "stage": config["stage"],
        "status": "CompletedAwaitingVerification",
        "test_split_accessed": False,
        "tier": config["tier"],
    }
    analysis.write_json(output_dir / "run.json", run)
    print(
        json.dumps(
            {
                "annotation_count": len(annotations),
                "experiment_id": config["experiment_id"],
                "status": run["status"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
