#!/usr/bin/env python3
"""Finalize EXP-055 after the frozen qualitative sample has been coded."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[5]
ALLOWED_FLAGS = {
    "sarcasm_or_irony",
    "negation",
    "implicit_emotion",
    "mixed_emotion",
    "surface_noise",
    "possible_missing_context",
    "annotation_ambiguity",
    "lexical_cue_conflict",
    "emotion_ontology_overlap",
    "weak_emotion_neutral_boundary",
    "multilabel_underprediction",
    "low_support_surprise",
    "no_listed_factor",
}
ALLOWED_SOURCES = {
    "annotation_or_data_uncertainty",
    "overlapping_label_ontology",
    "missing_forum_context",
    "model_or_representation_limitation",
    "calibration_or_threshold_policy",
    "surface_form_noise",
    "low_support_label_uncertainty",
    "uncertain",
}
ALLOWED_PLAUSIBILITY = {"plausible", "debatable", "implausible"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--annotations", required=True, type=Path)
    return parser.parse_args()


def resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fmt(value: float) -> str:
    return f"{value:.6f}"


def mean_std(values: Sequence[float]) -> tuple[float, float]:
    return statistics.fmean(values), statistics.stdev(values)


def git_state() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip())
    return {"commit": commit, "dirty": dirty}


def main() -> None:
    started = time.time()
    args = parse_args()
    config_path = args.config.resolve()
    run_dir = args.run_dir.resolve()
    annotations_path = args.annotations.resolve()
    config = load_json(config_path)
    analysis = load_json(run_dir / "analysis.json")
    if config.get("experiment_id") != "EXP-055" or analysis.get("status") != "Prepared":
        raise ValueError("EXP-055 preparation is not ready for finalization")
    for forbidden in ("run.json", "summary.json", "REPORT.md", "qualitative_summary.json"):
        if (run_dir / forbidden).exists():
            raise FileExistsError(f"Refusing to overwrite append-only output: {run_dir / forbidden}")
    finalizer_record = config["implementation"]["finalizer"]
    if sha256_file(resolve(finalizer_record["path"])) != finalizer_record["sha256"]:
        raise ValueError("Finalizer implementation drift")
    if sha256_file(run_dir / "frozen-finalizer.py") != finalizer_record["sha256"]:
        raise ValueError("Frozen finalizer drift")
    if annotations_path.parent != run_dir:
        raise ValueError("Annotations must be stored in the EXP-055 run directory")

    sample_rows = read_csv(run_dir / "sample_manifest.csv")
    annotation_rows = read_csv(annotations_path)
    sample_ids = [row["case_id"] for row in sample_rows]
    annotation_ids = [row["case_id"] for row in annotation_rows]
    if len(sample_ids) != len(set(sample_ids)) or len(annotation_ids) != len(set(annotation_ids)):
        raise ValueError("Duplicate case IDs")
    if set(sample_ids) != set(annotation_ids) or len(sample_ids) > int(config["qualitative_max_rows"]):
        raise ValueError("Annotations do not exactly cover the frozen sample")

    flag_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    plausibility_counts: Counter[str] = Counter()
    role_counts: dict[str, Counter[str]] = defaultdict(Counter)
    sample_by_id = {row["case_id"]: row for row in sample_rows}
    normalized_rows: list[dict[str, Any]] = []
    for row in sorted(annotation_rows, key=lambda value: value["case_id"]):
        flags = [flag for flag in row["flags"].split(";") if flag]
        if not flags or len(flags) != len(set(flags)) or not set(flags).issubset(ALLOWED_FLAGS):
            raise ValueError(f"Invalid qualitative flags for {row['case_id']}")
        if "no_listed_factor" in flags and len(flags) != 1:
            raise ValueError("no_listed_factor must be the only flag")
        if row["primary_source"] not in ALLOWED_SOURCES:
            raise ValueError(f"Invalid primary source for {row['case_id']}")
        if row["gold_plausibility"] not in ALLOWED_PLAUSIBILITY:
            raise ValueError(f"Invalid gold plausibility for {row['case_id']}")
        if row["reviewer"] != "assistant_single_reviewer":
            raise ValueError("Unexpected reviewer identity")
        role = sample_by_id[row["case_id"]]["role"]
        flag_counts.update(flags)
        source_counts[row["primary_source"]] += 1
        plausibility_counts[row["gold_plausibility"]] += 1
        role_counts[role][row["primary_source"]] += 1
        normalized_rows.append({
            "case_id": row["case_id"],
            "role": role,
            "flags": flags,
            "primary_source": row["primary_source"],
            "gold_plausibility": row["gold_plausibility"],
        })

    qualitative = {
        "schema_version": "exp-055-qualitative-summary-v1",
        "experiment_id": "EXP-055",
        "reviewer_count": 1,
        "reviewer": "assistant_single_reviewer",
        "rows": len(annotation_rows),
        "flag_counts": dict(sorted(flag_counts.items())),
        "primary_source_counts": dict(sorted(source_counts.items())),
        "gold_plausibility_counts": dict(sorted(plausibility_counts.items())),
        "primary_source_by_role": {role: dict(sorted(counts.items())) for role, counts in sorted(role_counts.items())},
        "claim_boundary": "Selected-case hypotheses only; not revised ground truth, prevalence, causality, model reasoning, or inter-rater evidence.",
    }
    write_json(run_dir / "qualitative_summary.json", qualitative)

    exact_rows = read_csv(run_dir / "exact_transitions.csv")
    oracle_rows = read_csv(run_dir / "oracle_summary.csv")
    stability_rows = read_csv(run_dir / "family_stability.csv")
    per_label_rows = read_csv(run_dir / "per_label_metrics.csv")
    cardinality_rows = read_csv(run_dir / "cardinality_summary.csv")
    shared_exact = [row for row in exact_rows if row["condition"] == "shared_threshold"]
    shared_oracle = [row for row in oracle_rows if row["condition"] == "shared_threshold"]

    def family_metric(family: str, metric: str) -> tuple[float, float]:
        values = analysis["primary_shared_threshold_summary"][family][metric]
        return float(values["mean"]), float(values["sample_std"])

    m1_macro = family_metric("m1", "macro_f1")
    m3_macro = family_metric("m3", "macro_f1")
    m1_five = family_metric("m1", "five_label_macro_f1_without_surprise")
    m3_five = family_metric("m3", "five_label_macro_f1_without_surprise")
    m1_only = mean_std([float(row["m1_only_correct"]) for row in shared_exact])
    m3_only = mean_std([float(row["m3_only_correct"]) for row in shared_exact])
    both_wrong = mean_std([float(row["both_wrong"]) for row in shared_exact])
    oracle_six = mean_std([float(row["macro_f1_delta_vs_m1"]) for row in shared_oracle])
    oracle_five = mean_std([float(row["five_label_macro_f1_delta_vs_m1"]) for row in shared_oracle])
    oracle_rate = mean_std([float(row["m3_selection_rate"]) for row in shared_oracle])

    if m3_macro[0] > m1_macro[0] and m3_five[0] <= m1_five[0]:
        comparison_narrative = (
            "M3's mean six-label Macro-F1 is higher than M1's, but that ordering does "
            "not extend to the five-label sensitivity result."
        )
    elif m3_macro[0] > m1_macro[0] and m3_five[0] > m1_five[0]:
        comparison_narrative = (
            "M3's mean Macro-F1 is higher than M1's in both the six-label primary "
            "result and the five-label sensitivity result."
        )
    elif m3_macro[0] <= m1_macro[0] and m3_five[0] > m1_five[0]:
        comparison_narrative = (
            "M3 does not exceed M1 on mean six-label Macro-F1, although its mean "
            "five-label sensitivity result is higher."
        )
    else:
        comparison_narrative = (
            "M3 does not exceed M1 on mean Macro-F1 in either the six-label primary "
            "result or the five-label sensitivity result."
        )

    surprise_lines: list[str] = []
    for family in ("m1", "m3"):
        rows = [
            row for row in per_label_rows
            if row["family"] == family and row["condition"] == "shared_threshold" and row["label"] == "surprise"
        ]
        surprise_lines.append(
            f"- {family.upper()} surprise F1: "
            + " / ".join(f"seed {row['seed']}={float(row['f1']):.6f}" for row in rows)
            + "."
        )

    stable_lines: list[str] = []
    for family in ("m1", "m3"):
        rows = [row for row in stability_rows if row["family"] == family and row["condition"] == "shared_threshold"]
        values = {row["category"]: int(row["rows"]) for row in rows}
        stable_lines.append(
            f"- {family.upper()}: 3/3 exact correct {values['stable_exact_correct_3_of_3']}, "
            f"seed-unstable {values['seed_unstable_1_or_2_of_3']}, 0/3 exact correct {values['stable_exact_wrong_0_of_3']}."
        )

    cardinality_lines: list[str] = []
    for family in ("m1", "m3"):
        rows = [row for row in cardinality_rows if row["family"] == family and row["condition"] == "shared_threshold"]
        empty_mean = statistics.fmean(float(row["empty_predictions"]) for row in rows)
        false_empty_mean = statistics.fmean(float(row["false_empty_positive_rows"]) for row in rows)
        neutral_fp_mean = statistics.fmean(float(row["neutral_false_positive_rows"]) for row in rows)
        cardinality_lines.append(
            f"- {family.upper()}: mean empty predictions {empty_mean:.2f}/720, false-empty positive rows {false_empty_mean:.2f}, "
            f"neutral rows with at least one false positive {neutral_fp_mean:.2f}."
        )

    top_sources = ", ".join(f"{key}={value}" for key, value in source_counts.most_common())
    top_flags = ", ".join(f"{key}={value}" for key, value in flag_counts.most_common())
    gate = analysis["router_headroom_gate"]
    report = f"""# EXP-055 M1/M3 Frozen Validation Error Analysis

- Status: `Completed; pending independent verification`
- Split: validation only (`720` rows; `702` duplicate components)
- New training or inference: `false`
- Test access: `false`
- Primary operating point: each seed's frozen shared threshold
- Companion: fixed threshold `0.50`

## Primary Family Results

| Family | Six-label Macro-F1 | Five-label Macro-F1 without surprise |
| --- | ---: | ---: |
| M1 RoBERTa | {fmt(m1_macro[0])} +/- {fmt(m1_macro[1])} | {fmt(m1_five[0])} +/- {fmt(m1_five[1])} |
| M3 Classification LoRA | {fmt(m3_macro[0])} +/- {fmt(m3_macro[1])} | {fmt(m3_five[0])} +/- {fmt(m3_five[1])} |

{comparison_narrative} Macro-F1 is non-additive, so this report does not assign an
additive share of the overall gap to any one label.

## Exact-Set Transitions

Across matched seeds, M1-only exact-correct rows average `{m1_only[0]:.2f} +/- {m1_only[1]:.2f}`;
M3-only exact-correct rows average `{m3_only[0]:.2f} +/- {m3_only[1]:.2f}`; rows where
both are exact-wrong average `{both_wrong[0]:.2f} +/- {both_wrong[1]:.2f}`.

{chr(10).join(stable_lines)}

## Surprise and Cardinality

{chr(10).join(surprise_lines)}

{chr(10).join(cardinality_lines)}

## Whole-Vector Oracle

The oracle selects one complete six-label vector per row using gold Hamming error and
ties to M1. It is not deployable. Relative to M1, shared-threshold oracle six-label
Macro-F1 delta is `{oracle_six[0]:.6f} +/- {oracle_six[1]:.6f}` and five-label delta is
`{oracle_five[0]:.6f} +/- {oracle_five[1]:.6f}`. M3 is selected on
`{oracle_rate[0]:.3%} +/- {oracle_rate[1]:.3%}` of rows.

Router-headroom gate: `{'Passed' if gate['passed'] else 'Failed'}`.

| Check | Passed |
| --- | --- |
""" + "\n".join(f"| {name} | `{str(passed).lower()}` |" for name, passed in gate["checks"].items()) + f"""

Passing only authorizes a separately registered train-OOF router feasibility test. It
does not show that pre-Qwen features can learn the oracle decision.

## Qualitative Review

- Frozen unique sample: `{len(annotation_rows)}` rows.
- Primary possible sources: {top_sources}.
- Evidence flags: {top_flags}.
- Gold plausibility: {', '.join(f'{key}={value}' for key, value in plausibility_counts.most_common())}.

These counts describe a purposefully selected sample reviewed once by the assistant.
They are hypotheses about failure cases, not dataset-wide prevalence, revised labels,
inter-rater evidence, causal explanations, or model reasoning.

## Boundary

EXP-055 used only frozen validation predictions and private validation text for the
pre-registered sample. It did not train, rerun inference, change thresholds, access
test, authorize EXP-054, or establish an internal emotion mechanism. Any router,
model change, TEST-READY decision, or generative comparison requires a new protocol.
"""
    (run_dir / "REPORT.md").write_text(report, encoding="utf-8")

    summary = {
        "schema_version": "exp-055-m1-m3-error-analysis-summary-v1",
        "experiment_id": "EXP-055",
        "status": "Completed; pending independent verification",
        "source_split": "validation",
        "rows": 720,
        "test_split_accessed": False,
        "primary_shared_threshold_summary": analysis["primary_shared_threshold_summary"],
        "exact_set_transitions": {
            "m1_only_correct_mean": m1_only[0],
            "m3_only_correct_mean": m3_only[0],
            "both_wrong_mean": both_wrong[0],
        },
        "router_headroom_gate": gate,
        "qualitative": {
            "rows": len(annotation_rows),
            "reviewer_count": 1,
            "flag_counts": dict(sorted(flag_counts.items())),
            "primary_source_counts": dict(sorted(source_counts.items())),
            "gold_plausibility_counts": dict(sorted(plausibility_counts.items())),
        },
        "claim_boundary": {
            "validation_only": True,
            "descriptive_only": True,
            "oracle_not_deployable": True,
            "qualitative_not_prevalence": True,
            "mechanism_claim": False,
        },
    }
    write_json(run_dir / "summary.json", summary)

    tracked_names = sorted(
        path.name for path in run_dir.iterdir()
        if path.is_file() and path.name not in {"run.json", "verification.json", "VERIFICATION-SUMMARY.md"}
    )
    run = {
        "schema_version": "exp-055-m1-m3-error-analysis-run-v1",
        "experiment_id": "EXP-055",
        "tier": "Major",
        "rq_ids": ["RQ-S1", "RQ-S3"],
        "stage": "descriptive-frozen-validation-error-analysis",
        "status": "Completed",
        "source_split": "validation",
        "rows": 720,
        "test_split_accessed": False,
        "training_performed": False,
        "inference_performed": False,
        "threshold_selection_performed": False,
        "router_headroom_gate": gate,
        "qualitative_rows": len(annotation_rows),
        "reviewer_count": 1,
        "git": git_state(),
        "config": artifact(config_path),
        "artifacts": {name: artifact(run_dir / name) for name in tracked_names},
        "finalization_wall_seconds": time.time() - started,
        "claim_boundary": {
            "validation_only": True,
            "descriptive_only": True,
            "oracle_not_deployable": True,
            "qualitative_not_prevalence": True,
            "mechanism_claim": False,
            "exp054_authorized": False,
            "test_ready": False,
        },
    }
    write_json(run_dir / "run.json", run)
    print(json.dumps({
        "status": "Completed",
        "qualitative_rows": len(annotation_rows),
        "router_gate_passed": gate["passed"],
        "test_accessed": False,
    }))


if __name__ == "__main__":
    main()
