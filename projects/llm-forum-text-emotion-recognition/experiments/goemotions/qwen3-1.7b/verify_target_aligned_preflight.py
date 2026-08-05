#!/usr/bin/env python3
"""Independently verify the PRE-EXP-033 target-aligned data audit."""

from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
CONTRACT_PATH = SCRIPT_DIR / "preflight" / "pre-exp-033-target-aligned-contract.json"
REPORT_PATH = SCRIPT_DIR / "preflight" / "pre-exp-033-target-aligned-audit.json"
VERIFICATION_PATH = (
    SCRIPT_DIR / "preflight" / "pre-exp-033-target-aligned-verification.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def expected_messages(
    prompt: dict[str, str], labels: tuple[str, ...], text: str, target: str
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": prompt["system_template"].format(
                allowed_labels=", ".join(labels)
            ),
        },
        {
            "role": "user",
            "content": prompt["user_template"].format(text=text),
        },
        {"role": "assistant", "content": target},
    ]


def rendered_tokens(tokenizer: Any, messages: list[dict[str, str]]) -> dict[str, Any]:
    full = list(
        tokenizer.apply_chat_template(
            messages, enable_thinking=True, return_dict=False
        )
    )
    full_false = list(
        tokenizer.apply_chat_template(
            messages, enable_thinking=False, return_dict=False
        )
    )
    train_prefix = list(
        tokenizer.apply_chat_template(
            messages[:-1],
            add_generation_prompt=True,
            enable_thinking=True,
            return_dict=False,
        )
    )
    inference_prefix = list(
        tokenizer.apply_chat_template(
            messages[:-1],
            add_generation_prompt=True,
            enable_thinking=False,
            return_dict=False,
        )
    )
    target_and_eos = list(
        tokenizer.encode(
            messages[-1]["content"] + "<|im_end|>\n",
            add_special_tokens=False,
        )
    )
    if full != full_false:
        raise ValueError("Full rendering changes with thinking flag")
    if full[: len(train_prefix)] != train_prefix:
        raise ValueError("Training prefix mismatch")
    if inference_prefix[: len(train_prefix)] != train_prefix:
        raise ValueError("Inference prefix mismatch")
    if full[: len(inference_prefix)] != inference_prefix:
        raise ValueError("Disabled-thinking context mismatch")
    if full[len(inference_prefix) :] != target_and_eos:
        raise ValueError("JSON target context mismatch")
    return {
        "control_count": len(inference_prefix) - len(train_prefix),
        "full": full,
    }


def truncate_independently(
    tokenizer: Any,
    prompt: dict[str, str],
    labels: tuple[str, ...],
    text: str,
    target: str,
    max_tokens: int,
) -> str:
    text_ids = list(tokenizer.encode(text, add_special_tokens=False))
    accepted = ""
    left, right = 0, len(text_ids)
    while left <= right:
        middle = (left + right) // 2
        candidate = tokenizer.decode(
            text_ids[:middle],
            skip_special_tokens=False,
            clean_up_tokenization_spaces=False,
        )
        length = len(
            rendered_tokens(
                tokenizer,
                expected_messages(prompt, labels, candidate, target),
            )["full"]
        )
        if candidate and length <= max_tokens:
            accepted = candidate
            left = middle + 1
        else:
            right = middle - 1
    if not accepted:
        raise ValueError("Independent truncation could not preserve input")
    return accepted


def main() -> None:
    if VERIFICATION_PATH.exists():
        raise FileExistsError("Verification output already exists; it is append-only")
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    if report.get("status") != "Passed" or report.get("audit_id") != "PRE-EXP-033":
        raise ValueError("Audit report did not pass")
    if report["contract"]["sha256"] != sha256_file(CONTRACT_PATH):
        raise ValueError("Contract hash mismatch")
    for name, source in contract["sources"].items():
        if sha256_file(resolve_path(source["path"])) != source["sha256"]:
            raise ValueError(f"Frozen source changed: {name}")
    for source_key in ("datasets_source", "tokenizer_utils_source", "trainer_source"):
        source = contract["mlx_lm_contract"][source_key]
        if sha256_file(Path(source["path"])) != source["sha256"]:
            raise ValueError(f"MLX-LM source changed: {source_key}")

    exp_029 = json.loads(
        resolve_path(contract["sources"]["parent_exp_029_config"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    exp_032 = json.loads(
        resolve_path(
            contract["sources"]["parent_exp_032_verification"]["path"]
        ).read_text(encoding="utf-8")
    )
    inherited = contract["training_inheritance"]
    old_training = exp_029["training"]
    comparisons = {
        "batch_size": old_training["batch_size"],
        "effective_batch_size": old_training["effective_batch_size"],
        "epochs": old_training["epochs"],
        "grad_accumulation_steps": old_training["grad_accumulation_steps"],
        "iterations": old_training["iterations"],
        "learning_rate": old_training["learning_rate"],
        "lora_num_layers": old_training["lora"]["num_layers"],
        "lora_rank": old_training["lora"]["rank"],
        "lora_scale": old_training["lora"]["scale"],
        "mask_prompt": old_training["mask_prompt"],
        "max_sequence_length": old_training["max_sequence_length"],
        "optimizer": old_training["optimizer"],
        "optimizer_updates": old_training["optimizer_updates"],
    }
    for key, expected in comparisons.items():
        if inherited[key] != expected:
            raise ValueError(f"Training inheritance drift at {key}")
    if exp_032["training"]["selected_condition"] != "batch2-grad5":
        raise ValueError("EXP-032 did not select batch2-grad5")
    if exp_032["cache"]["recommended"] is not False:
        raise ValueError("EXP-032 cache decision changed")
    if inherited["inference_prompt_execution"] != "full-prompt":
        raise ValueError("Rejected prompt cache was reintroduced")

    labels = tuple(
        resolve_path(contract["sources"]["labels"]["path"])
        .read_text(encoding="utf-8")
        .splitlines()
    )
    neutral_id = labels.index("neutral")
    prompt = json.loads(
        resolve_path(contract["sources"]["prompt"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    train_path = resolve_path(contract["sources"]["train"]["path"])
    private_root = resolve_path(contract["outputs"]["private_data_root"])
    prepared_path = private_root / "train.jsonl"
    smoke_path = private_root / "smoke" / "train.jsonl"
    for key, path in (("prepared_train", prepared_path), ("smoke", smoke_path)):
        artifact = report[key]
        if artifact["sha256"] != sha256_file(path) or artifact["bytes"] != path.stat().st_size:
            raise ValueError(f"Private artifact mismatch: {key}")

    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(prepared_path)],
        cwd=REPO_ROOT,
        check=False,
    )
    if ignored.returncode != 0:
        raise ValueError("Prepared private data is not gitignored")

    from transformers import AutoTokenizer
    from label_json_constraint import LabelJsonGrammar
    from label_json_constraint_neutral_cooccurrence import NeutralCooccurrenceGrammar

    tokenizer = AutoTokenizer.from_pretrained(
        PROJECT_ROOT / "models" / "qwen3-1.7b" / "mlx-bf16",
        local_files_only=True,
    )
    old_grammar = LabelJsonGrammar(labels)
    open_grammar = NeutralCooccurrenceGrammar(labels)
    max_tokens = int(inherited["max_sequence_length"])
    expected_control = int(
        contract["template_contract"]["expected_empty_thinking_control_tokens"]
    )
    label_support = [0] * len(labels)
    cardinality = Counter()
    neutral_rows: list[int] = []
    target_digest = hashlib.sha256()
    prepared_by_row: dict[int, str] = {}
    labels_by_row: dict[int, tuple[int, ...]] = {}
    old_rejected = 0
    rows = 0

    with train_path.open("r", encoding="utf-8", newline="") as source, prepared_path.open(
        "r", encoding="utf-8"
    ) as prepared:
        source_reader = csv.reader(source, delimiter="\t")
        for row_number, pair in enumerate(zip(source_reader, prepared, strict=True), start=1):
            raw_row, serialized = pair
            if len(raw_row) != 3:
                raise ValueError(f"Invalid source row {row_number}")
            original_text, encoded_labels, _comment_id = raw_row
            label_ids = tuple(sorted(int(value) for value in encoded_labels.split(",")))
            for label_id in label_ids:
                label_support[label_id] += 1
            cardinality[len(label_ids)] += 1
            neutral_cooccurrence = neutral_id in label_ids and len(label_ids) > 1
            if neutral_cooccurrence:
                neutral_rows.append(row_number)
            target = json.dumps(
                {"labels": [labels[value] for value in label_ids]},
                separators=(",", ":"),
            )
            if not open_grammar.status(target).complete:
                raise ValueError(f"Open grammar rejects source target at row {row_number}")
            old_accepts = old_grammar.status(target).complete
            if not old_accepts:
                old_rejected += 1
            if old_accepts == neutral_cooccurrence:
                raise ValueError(f"Closed grammar classification mismatch at row {row_number}")

            record = json.loads(serialized)
            if set(record) != {"messages"} or len(record["messages"]) != 3:
                raise ValueError(f"Invalid prepared record at row {row_number}")
            prepared_text = record["messages"][1]["content"]
            prefix, suffix = "Comment:\n", "\n\nReturn JSON only."
            if not prepared_text.startswith(prefix) or not prepared_text.endswith(suffix):
                raise ValueError(f"Invalid user framing at row {row_number}")
            prepared_text = prepared_text[len(prefix) : -len(suffix)]
            expected_text = original_text
            original_messages = expected_messages(prompt, labels, original_text, target)
            if len(rendered_tokens(tokenizer, original_messages)["full"]) > max_tokens:
                expected_text = truncate_independently(
                    tokenizer,
                    prompt,
                    labels,
                    original_text,
                    target,
                    max_tokens,
                )
            expected = expected_messages(prompt, labels, expected_text, target)
            if record["messages"] != expected:
                raise ValueError(f"Prepared messages differ from source at row {row_number}")
            rendered = rendered_tokens(tokenizer, expected)
            if len(rendered["full"]) > max_tokens:
                raise ValueError(f"Prepared sequence exceeds limit at row {row_number}")
            if rendered["control_count"] != expected_control:
                raise ValueError(f"Thinking control boundary changed at row {row_number}")

            target_digest.update(
                f"{row_number}\t{','.join(map(str, label_ids))}\t{target}\n".encode(
                    "utf-8"
                )
            )
            prepared_by_row[row_number] = serialized
            labels_by_row[row_number] = label_ids
            rows += 1

    target_contract = contract["target_contract"]
    if rows != int(target_contract["expected_train_rows"]):
        raise ValueError("Independent row count mismatch")
    if label_support != [int(value) for value in target_contract["expected_gold_label_support"]]:
        raise ValueError("Independent label support mismatch")
    if len(neutral_rows) != int(target_contract["expected_neutral_cooccurrence_rows"]):
        raise ValueError("Independent neutral co-occurrence count mismatch")
    if old_rejected != len(neutral_rows):
        raise ValueError("Closed grammar did not reject exactly the corrected rows")
    reported_target = report["target_contract"]
    if target_digest.hexdigest() != reported_target["target_stream_sha256"]:
        raise ValueError("Target stream hash mismatch")
    if sha256_text(",".join(map(str, neutral_rows))) != reported_target[
        "neutral_cooccurrence_row_numbers_sha256"
    ]:
        raise ValueError("Neutral row-number hash mismatch")
    if reported_target["label_support"] != {
        label: label_support[index] for index, label in enumerate(labels)
    }:
        raise ValueError("Reported label support mismatch")
    if reported_target["cardinality_support"] != {
        str(key): value for key, value in sorted(cardinality.items())
    }:
        raise ValueError("Reported cardinality mismatch")

    smoke_lines = smoke_path.read_text(encoding="utf-8").splitlines(keepends=True)
    smoke_rows = [int(value) for value in report["smoke"]["row_numbers"]]
    if smoke_lines != [prepared_by_row[row] for row in smoke_rows]:
        raise ValueError("Smoke rows do not match prepared training rows")
    smoke_label_coverage: set[int] = set()
    smoke_neutral = 0
    for row_number in smoke_rows:
        label_ids = set(labels_by_row[row_number])
        smoke_label_coverage.update(label_ids)
        smoke_neutral += int(neutral_id in label_ids and len(label_ids) > 1)
    if smoke_label_coverage != set(range(len(labels))):
        raise ValueError("Independent smoke label coverage failed")
    if smoke_neutral != int(contract["smoke_contract"]["neutral_cooccurrence_rows"]):
        raise ValueError("Independent smoke neutral count failed")

    auditor_source = resolve_path(report["implementation"]["auditor"]["path"])
    if sha256_file(auditor_source) != report["implementation"]["auditor"]["sha256"]:
        raise ValueError("Auditor source changed after report generation")
    if sha256_file(Path(__file__)) != report["implementation"]["verifier"]["sha256"]:
        raise ValueError("Verifier source changed after report generation")
    auditor_text = auditor_source.read_text(encoding="utf-8")
    for forbidden in ("target_label_ids.remove", '"neutral-combined"'):
        if forbidden in auditor_text:
            raise ValueError(f"Old target policy leaked into auditor: {forbidden}")

    verification = {
        "accessed_splits": ["train"],
        "audit_id": "PRE-EXP-033",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "formal_training_authorized": False,
        "independent_checks": {
            "all_official_targets_preserved": True,
            "all_prepared_rows_reconstructed": rows,
            "closed_grammar_rejected_exactly_neutral_cooccurrences": old_rejected,
            "full_prompt_inherited_from_exp_032": True,
            "mlx_lm_target_context_equivalence_rows": rows,
            "neutral_cooccurrence_rows": len(neutral_rows),
            "private_data_gitignored": True,
            "smoke_covers_all_labels": True,
            "smoke_neutral_cooccurrence_rows": smoke_neutral,
            "training_hyperparameters_inherited_from_exp_029": True,
        },
        "model_forward_or_backward_executed": False,
        "next_required_step": contract["execution_gate"]["next_required_step"],
        "status": "Passed",
        "test_split_accessed": False,
        "validation_split_accessed": False,
    }
    write_json(VERIFICATION_PATH, verification)
    print(json.dumps(verification, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
