#!/usr/bin/env python3
"""Recover EXP-049 after a report-only failure without reopening test labels."""

from __future__ import annotations

import json
from pathlib import Path

from test_gate_common import artifact, atomic_json, atomic_text, load_json, utc_now


SCRIPT_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = SCRIPT_DIR / "runs" / "exp-049-frozen-test"
AGGREGATE_PATH = PUBLIC_DIR / "aggregate-metrics.json"
LABEL_OPENING_PATH = PUBLIC_DIR / "label-opening.json"
REPORT_PATH = PUBLIC_DIR / "REPORT.md"
RUN_PATH = PUBLIC_DIR / "run.json"
INCIDENT_PATH = PUBLIC_DIR / "finalize-recovery.json"

CONDITION_ORDER = (
    "m0-majority",
    "m1-target-only",
    "encoder-seed-42",
    "encoder-seed-43",
    "encoder-seed-44",
    "qwen-reference",
    "qwen-lora-seed-42",
    "qwen-lora-seed-43",
    "qwen-lora-seed-44",
)


def render_report(aggregate: dict) -> str:
    rows = [
        "# EXP-049 Weibo EClass Frozen Test Report",
        "",
        "Status: Completed; pending independent verification.",
        "",
        "| Unit | Macro-F1 | Accuracy | Macro-P | Macro-R | Weighted-F1 | Parser valid | Seconds |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for unit in CONDITION_ORDER:
        result = aggregate["units"][unit]
        metric = result["metrics"]["slices"]["all"]
        parser = (result.get("parser") or {}).get("valid_rate")
        parser_text = f"{parser:.6f}" if parser is not None else "N/A"
        rows.append(
            f"| {unit} | {metric['macro_f1']:.6f} | {metric['accuracy']:.6f} | "
            f"{metric['macro_precision']:.6f} | {metric['macro_recall']:.6f} | "
            f"{metric['weighted_f1']:.6f} | {parser_text} | {result['resource']['seconds']:.3f} |"
        )
    rows.extend(["", "## Family Summary", ""])
    for family_id, summary in aggregate["families"].items():
        rows.append(
            f"- `{family_id}` Macro-F1: `{summary['macro_f1']['mean']:.6f} +/- "
            f"{summary['macro_f1']['sample_std']:.6f}`"
        )
    rows.extend(["", "## Frozen Contrasts", ""])
    for contrast_id, contrast in aggregate["contrasts"].items():
        rows.append(
            f"- `{contrast_id}`: delta `{contrast['observed_delta']:+.6f}`, "
            f"95% group bootstrap CI `[{contrast['ci95'][0]:+.6f}, {contrast['ci95'][1]:+.6f}]`, "
            f"decision `{contrast['decision']}`."
        )
    rows.extend(
        [
            "",
            "All nine configurations were frozen before test access and are reported without best-seed selection.",
            "Row-level predictions, source identifiers, text, gold labels, and Qwen reasoning remain private.",
            "No result may be used to tune or rerun this held-out split.",
            "",
        ]
    )
    return "\n".join(rows)


def main() -> None:
    if REPORT_PATH.exists() or INCIDENT_PATH.exists():
        raise FileExistsError("Recovery outputs are append-only")

    aggregate = load_json(AGGREGATE_PATH)
    opening = load_json(LABEL_OPENING_PATH)
    run = load_json(RUN_PATH)
    opened_at = aggregate.get("label_opened_at_utc")

    if (
        aggregate.get("status") != "Completed; pending independent verification"
        or aggregate.get("rows") != 1273
        or set(aggregate.get("units", {})) != set(CONDITION_ORDER)
        or opening.get("status") != "Opening"
        or opening.get("labels_opened_at_utc") != opened_at
        or opening.get("model_calls_after_open") != 0
        or run.get("test_labels_accessed") is not True
        or run.get("label_opening", {}).get("status") != "opening"
    ):
        raise RuntimeError("EXP-049 is not in the expected report-only recovery state")

    for condition in CONDITION_ORDER:
        stage = run.get("stages", {}).get(f"infer__{condition}", {})
        if stage.get("status") != "Completed" or stage.get("completed_at_utc", "") > opened_at:
            raise RuntimeError(f"Prediction stage was not complete before label opening: {condition}")

    aggregate_before = artifact(AGGREGATE_PATH)
    scored_before = aggregate["scored_predictions"]
    unit_results_before = artifact(PUBLIC_DIR / "unit-results.csv")
    recovered_at = utc_now()

    atomic_text(REPORT_PATH, render_report(aggregate))
    consumed = {
        **opening,
        "completed_at_utc": recovered_at,
        "status": "Consumed",
    }
    atomic_json(LABEL_OPENING_PATH, consumed)

    incident = {
        "aggregate_unchanged": aggregate_before,
        "detected_at_utc": recovered_at,
        "experiment_id": "EXP-049",
        "failure": {
            "exception": "AttributeError",
            "message": "Report renderer called .get() on a null parser field for a non-generative unit.",
            "scope": "REPORT.md rendering after metrics had been persisted",
        },
        "labels_already_opened": True,
        "model_calls_after_open": 0,
        "recovery_action": "Rendered REPORT.md from the persisted aggregate and completed the opening-to-consumed state transition.",
        "recovery_id": "EXP-049-FINALIZE-REPORT-RECOVERY-V1",
        "report": artifact(REPORT_PATH),
        "scored_predictions_unchanged": scored_before,
        "status": "Recovered; pending independent verification",
        "test_labels_reopened": False,
        "unit_results_unchanged": unit_results_before,
    }
    atomic_json(INCIDENT_PATH, incident)

    run.setdefault("commands", []).append(
        {
            "command": f"python {Path(__file__).name}",
            "recorded_at_utc": recovered_at,
        }
    )
    run["label_opening"] = {
        "artifact": artifact(LABEL_OPENING_PATH),
        "opened_at_utc": opened_at,
        "status": "consumed",
    }
    run["stages"]["finalize"] = {
        "aggregate": aggregate_before,
        "completed_at_utc": aggregate["completed_at_utc"],
        "recovery": artifact(INCIDENT_PATH),
        "report": artifact(REPORT_PATH),
        "status": "Completed",
    }
    run["status"] = "Completed; pending independent verification"
    run["test_inputs_accessed"] = True
    run["test_labels_accessed"] = True
    atomic_json(RUN_PATH, run)

    if artifact(AGGREGATE_PATH) != aggregate_before or aggregate["scored_predictions"] != scored_before:
        raise RuntimeError("Recovery changed a persisted metric or scored-prediction artifact")

    print(
        json.dumps(
            {
                "aggregate_unchanged": True,
                "model_calls_after_open": 0,
                "status": "Recovered; pending independent verification",
                "test_labels_reopened": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
