#!/usr/bin/env python3
"""Build and audit the train-only target-aligned LoRA data contract."""

from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import sys
import tempfile
from typing import Any


AUDIT_ID = "PRE-EXP-033"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
REPO_ROOT = SCRIPT_DIR.parents[4]
CONTRACT_PATH = SCRIPT_DIR / "preflight" / "pre-exp-033-target-aligned-contract.json"
VERIFIER_PATH = SCRIPT_DIR / "verify_target_aligned_preflight.py"
TEST_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "test.tsv"
CONTROL_STRINGS = ("<|im_start|>", "<|im_end|>", "<think>", "</think>")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def project_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def artifact(path: Path) -> dict[str, Any]:
    return {
        "bytes": path.stat().st_size,
        "path": project_path(path),
        "sha256": sha256_file(path),
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def quantile_summary(values: list[int]) -> dict[str, float | int]:
    import numpy as np

    array = np.asarray(values, dtype=np.int64)
    return {
        "max": int(np.max(array)),
        "mean": float(np.mean(array)),
        "min": int(np.min(array)),
        "p50": float(np.quantile(array, 0.50)),
        "p95": float(np.quantile(array, 0.95)),
        "p99": float(np.quantile(array, 0.99)),
    }


def verify_frozen_inputs(contract: dict[str, Any]) -> None:
    if TEST_PATH.exists():
        raise ValueError(f"Test split must remain absent: {TEST_PATH}")
    for source in contract["sources"].values():
        path = resolve_path(source["path"])
        if sha256_file(path) != source["sha256"]:
            raise ValueError(f"Frozen source hash mismatch: {path}")
    template = contract["template_contract"]
    for path_key, hash_key in (
        ("chat_template_path", "chat_template_sha256"),
        ("tokenizer_config_path", "tokenizer_config_sha256"),
        ("tokenizer_path", "tokenizer_sha256"),
    ):
        path = resolve_path(template[path_key])
        if sha256_file(path) != template[hash_key]:
            raise ValueError(f"Tokenizer artifact hash mismatch: {path}")
    for source_key in ("datasets_source", "tokenizer_utils_source", "trainer_source"):
        source = contract["mlx_lm_contract"][source_key]
        if sha256_file(Path(source["path"])) != source["sha256"]:
            raise ValueError(f"MLX-LM source hash mismatch: {source['path']}")
    package_versions = {
        name: importlib.metadata.version(name)
        for name in ("mlx", "mlx-lm", "numpy", "transformers")
    }
    package_versions["python"] = platform.python_version()
    if package_versions != contract["mlx_lm_contract"]["packages"]:
        raise ValueError(f"Environment drift: {package_versions}")


def build_messages(
    prompt_spec: dict[str, str], labels: tuple[str, ...], text: str, target: str
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": prompt_spec["system_template"].format(
                allowed_labels=", ".join(labels)
            ),
        },
        {
            "role": "user",
            "content": prompt_spec["user_template"].format(text=text),
        },
        {"role": "assistant", "content": target},
    ]


def token_contract(tokenizer: Any, messages: list[dict[str, str]]) -> dict[str, Any]:
    full_true = list(
        tokenizer.apply_chat_template(
            messages,
            enable_thinking=True,
            return_dict=False,
        )
    )
    full_false = list(
        tokenizer.apply_chat_template(
            messages,
            enable_thinking=False,
            return_dict=False,
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
    target = messages[-1]["content"]
    target_and_eos = list(
        tokenizer.encode(target + "<|im_end|>\n", add_special_tokens=False)
    )
    if full_true != full_false:
        raise ValueError("Full assistant rendering changes with enable_thinking")
    if full_true[: len(train_prefix)] != train_prefix:
        raise ValueError("MLX-LM training prefix is not a prefix of the full sequence")
    if inference_prefix[: len(train_prefix)] != train_prefix:
        raise ValueError("Inference and training prefixes diverge before thinking control")
    control_tokens = inference_prefix[len(train_prefix) :]
    if full_true[: len(inference_prefix)] != inference_prefix:
        raise ValueError("Full sequence does not contain the disabled-thinking prefix")
    if full_true[len(inference_prefix) :] != target_and_eos:
        raise ValueError("Target tokens differ between training and inference contexts")
    return {
        "control_tokens": control_tokens,
        "full_tokens": full_true,
        "json_and_eos_tokens": target_and_eos,
        "loss_offset": len(train_prefix),
    }


def truncate_text(
    tokenizer: Any,
    prompt_spec: dict[str, str],
    labels: tuple[str, ...],
    text: str,
    target: str,
    max_tokens: int,
) -> tuple[str, int]:
    text_tokens = list(tokenizer.encode(text, add_special_tokens=False))
    low, high = 0, len(text_tokens)
    best_text = ""
    best_length = 0
    while low <= high:
        midpoint = (low + high) // 2
        candidate = tokenizer.decode(
            text_tokens[:midpoint],
            skip_special_tokens=False,
            clean_up_tokenization_spaces=False,
        )
        length = len(
            token_contract(
                tokenizer,
                build_messages(prompt_spec, labels, candidate, target),
            )["full_tokens"]
        )
        if candidate and length <= max_tokens:
            best_text = candidate
            best_length = length
            low = midpoint + 1
        else:
            high = midpoint - 1
    if not best_text:
        raise ValueError("Unable to preserve a non-empty input within the sequence limit")
    return best_text, best_length


def deterministic_pick(
    rows: list[dict[str, Any]], selected: set[int], salt: str
) -> dict[str, Any]:
    candidates = [row for row in rows if row["row_number"] not in selected]
    if not candidates:
        raise ValueError(f"No candidate remains for {salt}")
    return min(
        candidates,
        key=lambda row: sha256_text(f"{salt}:{row['row_number']}"),
    )


def select_smoke_rows(
    rows: list[dict[str, Any]],
    label_support: list[int],
    row_count: int,
    cooccurrence_count: int,
    label_count: int,
) -> list[dict[str, Any]]:
    selected: set[int] = set()
    cooccurrence = [row for row in rows if row["neutral_cooccurrence"]]
    for index in range(cooccurrence_count):
        chosen = deterministic_pick(
            cooccurrence,
            selected,
            f"PRE-EXP-033-neutral-smoke-v1:{index}",
        )
        selected.add(chosen["row_number"])
    non_cooccurrence = [row for row in rows if not row["neutral_cooccurrence"]]
    for label_id in sorted(range(label_count), key=lambda value: label_support[value]):
        if any(
            row["row_number"] in selected and label_id in row["label_ids"]
            for row in rows
        ):
            continue
        candidates = [row for row in non_cooccurrence if label_id in row["label_ids"]]
        chosen = deterministic_pick(
            candidates,
            selected,
            f"PRE-EXP-033-label-smoke-v1:{label_id}",
        )
        selected.add(chosen["row_number"])
    while len(selected) < row_count:
        chosen = deterministic_pick(
            non_cooccurrence,
            selected,
            f"PRE-EXP-033-fill-smoke-v1:{len(selected)}",
        )
        selected.add(chosen["row_number"])
    if len(selected) != row_count:
        raise ValueError("Smoke selection exceeds the registered row count")
    smoke = sorted(
        (row for row in rows if row["row_number"] in selected),
        key=lambda row: row["row_number"],
    )
    covered = {label for row in smoke for label in row["label_ids"]}
    if covered != set(range(label_count)):
        raise ValueError("Smoke selection does not cover every label")
    if sum(row["neutral_cooccurrence"] for row in smoke) != cooccurrence_count:
        raise ValueError("Smoke neutral co-occurrence count is not exact")
    return smoke


def main() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if contract["audit_id"] != AUDIT_ID:
        raise ValueError("Unexpected audit contract")
    verify_frozen_inputs(contract)
    report_path = resolve_path(contract["outputs"]["audit_report"])
    verification_path = resolve_path(contract["outputs"]["verification_report"])
    private_root = resolve_path(contract["outputs"]["private_data_root"])
    if report_path.exists() or verification_path.exists() or private_root.exists():
        raise FileExistsError("Preflight outputs already exist; they are append-only")

    from transformers import AutoTokenizer
    from label_json_constraint import LabelJsonGrammar
    from label_json_constraint_neutral_cooccurrence import NeutralCooccurrenceGrammar

    labels_path = resolve_path(contract["sources"]["labels"]["path"])
    train_path = resolve_path(contract["sources"]["train"]["path"])
    prompt_path = resolve_path(contract["sources"]["prompt"]["path"])
    model_dir = PROJECT_ROOT / "models" / "qwen3-1.7b" / "mlx-bf16"
    labels = tuple(labels_path.read_text(encoding="utf-8").splitlines())
    if len(labels) != 28 or len(set(labels)) != len(labels):
        raise ValueError("Unexpected label ontology")
    neutral_id = labels.index("neutral")
    prompt_spec = json.loads(prompt_path.read_text(encoding="utf-8"))
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    old_grammar = LabelJsonGrammar(labels)
    open_grammar = NeutralCooccurrenceGrammar(labels)
    max_tokens = int(contract["training_inheritance"]["max_sequence_length"])
    expected_control_count = int(
        contract["template_contract"]["expected_empty_thinking_control_tokens"]
    )

    rows: list[dict[str, Any]] = []
    label_support = [0] * len(labels)
    cardinality = Counter()
    sequence_lengths: list[int] = []
    loss_lengths: list[int] = []
    json_eos_lengths: list[int] = []
    neutral_cooccurrence_rows: list[int] = []
    truncations: list[dict[str, int]] = []
    control_collision_rows: list[int] = []
    seen_comment_ids: set[str] = set()
    target_digest = hashlib.sha256()
    open_accepted = 0
    old_rejected = 0

    private_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="pre-exp-033-", dir=private_root.parent))
    try:
        output_path = temporary / "train.jsonl"
        with train_path.open("r", encoding="utf-8", newline="") as source, output_path.open(
            "w", encoding="utf-8"
        ) as output:
            for row_index, raw_row in enumerate(csv.reader(source, delimiter="\t")):
                row_number = row_index + 1
                if len(raw_row) != 3:
                    raise ValueError(f"train.tsv row {row_number} has {len(raw_row)} columns")
                text, encoded_labels, comment_id = raw_row
                if not text or not encoded_labels or not comment_id:
                    raise ValueError(f"train.tsv row {row_number} has an empty field")
                if comment_id in seen_comment_ids:
                    raise ValueError("Duplicate train comment ID")
                seen_comment_ids.add(comment_id)
                try:
                    label_ids = tuple(sorted(int(value) for value in encoded_labels.split(",")))
                except ValueError as error:
                    raise ValueError(f"Invalid label encoding at row {row_number}") from error
                if (
                    not label_ids
                    or len(label_ids) != len(set(label_ids))
                    or any(value < 0 or value >= len(labels) for value in label_ids)
                ):
                    raise ValueError(f"Invalid label set at row {row_number}")
                for label_id in label_ids:
                    label_support[label_id] += 1
                cardinality[len(label_ids)] += 1
                is_neutral_cooccurrence = neutral_id in label_ids and len(label_ids) > 1
                if is_neutral_cooccurrence:
                    neutral_cooccurrence_rows.append(row_number)
                target = json.dumps(
                    {"labels": [labels[value] for value in label_ids]},
                    separators=(",", ":"),
                )
                if open_grammar.status(target).complete:
                    open_accepted += 1
                else:
                    raise ValueError(f"Open grammar rejects row {row_number}")
                old_accepts = old_grammar.status(target).complete
                if not old_accepts:
                    old_rejected += 1
                if old_accepts == is_neutral_cooccurrence:
                    raise ValueError(f"Old grammar mismatch at row {row_number}")
                if any(value in text for value in CONTROL_STRINGS):
                    control_collision_rows.append(row_number)

                original_characters = len(text)
                messages = build_messages(prompt_spec, labels, text, target)
                tokens = token_contract(tokenizer, messages)
                original_length = len(tokens["full_tokens"])
                if original_length > max_tokens:
                    text, final_length = truncate_text(
                        tokenizer,
                        prompt_spec,
                        labels,
                        text,
                        target,
                        max_tokens,
                    )
                    messages = build_messages(prompt_spec, labels, text, target)
                    tokens = token_contract(tokenizer, messages)
                    if len(tokens["full_tokens"]) != final_length:
                        raise ValueError("Truncation length changed after reconstruction")
                    truncations.append(
                        {
                            "final_characters": len(text),
                            "final_tokens": final_length,
                            "original_characters": original_characters,
                            "original_tokens": original_length,
                            "row_number": row_number,
                        }
                    )
                if len(tokens["full_tokens"]) > max_tokens:
                    raise ValueError(f"Sequence exceeds limit at row {row_number}")
                if len(tokens["control_tokens"]) != expected_control_count:
                    raise ValueError(f"Thinking control token count changed at row {row_number}")
                if not tokens["json_and_eos_tokens"]:
                    raise ValueError(f"Empty target token range at row {row_number}")

                serialized = json.dumps(
                    {"messages": messages}, separators=(",", ":"), ensure_ascii=True
                )
                output.write(serialized + "\n")
                target_digest.update(
                    f"{row_number}\t{','.join(map(str, label_ids))}\t{target}\n".encode(
                        "utf-8"
                    )
                )
                rows.append(
                    {
                        "label_ids": label_ids,
                        "line": serialized,
                        "neutral_cooccurrence": is_neutral_cooccurrence,
                        "row_number": row_number,
                    }
                )
                sequence_lengths.append(len(tokens["full_tokens"]))
                loss_lengths.append(len(tokens["full_tokens"]) - tokens["loss_offset"])
                json_eos_lengths.append(len(tokens["json_and_eos_tokens"]))

        expected = contract["target_contract"]
        if len(rows) != int(expected["expected_train_rows"]):
            raise ValueError("Prepared row count differs from the contract")
        if label_support != [int(value) for value in expected["expected_gold_label_support"]]:
            raise ValueError("Target label support differs from official train labels")
        if len(neutral_cooccurrence_rows) != int(
            expected["expected_neutral_cooccurrence_rows"]
        ):
            raise ValueError("Neutral co-occurrence count differs from the contract")
        if open_accepted != len(rows) or old_rejected != len(neutral_cooccurrence_rows):
            raise ValueError("Grammar acceptance totals are inconsistent")
        if control_collision_rows:
            raise ValueError(
                f"Raw input contains chat-template control strings at rows {control_collision_rows}"
            )

        smoke_contract = contract["smoke_contract"]
        smoke = select_smoke_rows(
            rows,
            label_support,
            int(smoke_contract["rows"]),
            int(smoke_contract["neutral_cooccurrence_rows"]),
            len(labels),
        )
        smoke_dir = temporary / "smoke"
        smoke_dir.mkdir()
        (smoke_dir / "train.jsonl").write_text(
            "".join(row["line"] + "\n" for row in smoke),
            encoding="utf-8",
        )
        temporary.rename(private_root)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise

    report = {
        "accessed_splits": ["train"],
        "audit_id": AUDIT_ID,
        "candidate_experiment_id": contract["candidate_experiment_id"],
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract": artifact(CONTRACT_PATH),
        "execution_gate": {
            "formal_training_authorized": False,
            "model_forward_or_backward_executed": False,
            "next_required_step": contract["execution_gate"]["next_required_step"],
        },
        "grammar": {
            "old_closed_grammar_rejected_rows": old_rejected,
            "open_grammar_accepted_rows": open_accepted,
            "open_grammar_accepts_every_official_target": True,
        },
        "implementation": {
            "auditor": artifact(Path(__file__)),
            "verifier": artifact(VERIFIER_PATH),
        },
        "inheritance": {
            "acceleration": {
                "inference_prompt_execution": "full-prompt",
                "training_condition": "batch2-grad5",
            },
            "training": contract["training_inheritance"],
        },
        "prepared_train": {
            **artifact(private_root / "train.jsonl"),
            "rows": len(rows),
            "sequence_token_lengths": quantile_summary(sequence_lengths),
        },
        "privacy": {
            "private_data_gitignored": True,
            "public_comment_ids": False,
            "public_raw_text": False,
        },
        "smoke": {
            **artifact(private_root / "smoke" / "train.jsonl"),
            "covers_all_labels": True,
            "neutral_cooccurrence_rows": sum(
                row["neutral_cooccurrence"] for row in smoke
            ),
            "row_numbers": [row["row_number"] for row in smoke],
            "rows": len(smoke),
        },
        "status": "Passed",
        "target_contract": {
            "cardinality_support": {
                str(key): value for key, value in sorted(cardinality.items())
            },
            "canonical_label_order": expected["canonical_label_order"],
            "exact_official_gold_preservation": True,
            "label_support": {
                label: label_support[index] for index, label in enumerate(labels)
            },
            "neutral_cooccurrence_row_count": len(neutral_cooccurrence_rows),
            "neutral_cooccurrence_row_numbers_sha256": sha256_text(
                ",".join(map(str, neutral_cooccurrence_rows))
            ),
            "target_stream_sha256": target_digest.hexdigest(),
        },
        "template_contract": {
            "empty_thinking_control_token_count": expected_control_count,
            "full_assistant_rendering_true_false_identical_rows": len(rows),
            "inference_prefix_plus_target_matches_full_training_sequence_rows": len(rows),
            "json_and_eos_token_lengths": quantile_summary(json_eos_lengths),
            "loss_bearing_token_lengths": quantile_summary(loss_lengths),
            "loss_boundary_note": (
                "MLX-LM masks through the assistant prefix. Four empty-thinking control "
                "tokens remain loss-bearing; the JSON target follows the identical "
                "disabled-thinking inference prefix."
            ),
        },
        "test_split_accessed": False,
        "test_split_absent": not TEST_PATH.exists(),
        "truncation": {
            "affected_rows": len(truncations),
            "input_tail_only": True,
            "max_sequence_tokens": max_tokens,
            "records": truncations,
            "target_preserved": True,
        },
        "validation_split_accessed": False,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(report_path, report)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
