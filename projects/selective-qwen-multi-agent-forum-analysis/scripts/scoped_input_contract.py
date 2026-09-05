#!/usr/bin/env python3
"""Pure contracts for SQMA-002 scoped-input materialization.

The module performs no filesystem I/O and imports only the Python standard
library.  Runners and verifiers pass decoded public/private rows or array
metadata into these functions; this module never opens a real private source.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence


class ContractError(ValueError):
    """Raised when a frozen SQMA-002 contract is violated."""


PROTOCOL_ID = "DATA-SO-TASK-V1"
SOURCE_TRAIN_SCHEMA_VERSION = "so-emotion-c0-v1"
SOURCE_FOLD_SCHEMA_VERSION = "exp-058-fold-row-v1"
SOURCE_FOLD_EXPERIMENT_ID = "EXP-058"
LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
MATERIALIZED_FOLDS = (0, 1, 2)
FOLD_ROWS = 672

PRIVATE_TRAIN_FIELDS = (
    "schema_version",
    "protocol_id",
    "sample_id",
    "component_id",
    "text",
    "labels",
    "neutral",
    "label_cardinality",
)
PUBLIC_FOLD_FIELDS = (
    "schema_version",
    "protocol_id",
    "experiment_id",
    "sample_id",
    "component_id",
    "fold_id",
)
PRIVATE_FOLD_FIELDS = PUBLIC_FOLD_FIELDS + (
    "labels",
    "neutral",
    "label_cardinality",
)

TRAIN_CAPABLE_FIELDS = (
    "schema_version",
    "protocol_id",
    "sample_id",
    "component_id",
    "fold_id",
    "source_ordinal",
    "text",
    "labels",
    "label_cardinality",
    "neutral",
)
GOLD_FREE_INFERENCE_FIELDS = (
    "schema_version",
    "protocol_id",
    "sample_id",
    "component_id",
    "fold_id",
    "source_ordinal",
    "text",
)


@dataclass(frozen=True)
class JsonlSchema:
    schema_id: str
    fields: tuple[str, ...]
    contains_text: bool
    contains_gold: bool


@dataclass(frozen=True)
class ArraySpec:
    dtype: str
    shape: tuple[int, ...]


@dataclass(frozen=True)
class ArraySchema:
    schema_id: str
    arrays: Mapping[str, ArraySpec]
    contains_text: bool
    contains_gold: bool


SOURCE_SCHEMAS = MappingProxyType(
    {
        "private-train": JsonlSchema(
            SOURCE_TRAIN_SCHEMA_VERSION, PRIVATE_TRAIN_FIELDS, True, True
        ),
        "public-fold-manifest": JsonlSchema(
            SOURCE_FOLD_SCHEMA_VERSION, PUBLIC_FOLD_FIELDS, False, False
        ),
        "private-fold-manifest": JsonlSchema(
            SOURCE_FOLD_SCHEMA_VERSION, PRIVATE_FOLD_FIELDS, False, True
        ),
    }
)

CONSUMER_GOLD_ARRAYS = MappingProxyType(
    {
        "sample_ids": ArraySpec("unicode", (FOLD_ROWS,)),
        "component_ids": ArraySpec("unicode", (FOLD_ROWS,)),
        "fold_ids": ArraySpec("int8", (FOLD_ROWS,)),
        "source_ordinals": ArraySpec("int32", (FOLD_ROWS,)),
        "gold": ArraySpec("uint8", (FOLD_ROWS, len(LABELS))),
    }
)

OUTPUT_SCHEMAS = MappingProxyType(
    {
        "train-capable": JsonlSchema(
            "sqma-train-capable-snapshot-v1", TRAIN_CAPABLE_FIELDS, True, True
        ),
        "gold-free-inference": JsonlSchema(
            "sqma-gold-free-inference-snapshot-v1",
            GOLD_FREE_INFERENCE_FIELDS,
            True,
            False,
        ),
        "consumer-gold": ArraySchema(
            "sqma-consumer-gold-snapshot-v1",
            CONSUMER_GOLD_ARRAYS,
            False,
            True,
        ),
    }
)

EXPECTED_FOLD_IDENTITY = MappingProxyType(
    {
        0: MappingProxyType(
            {
                "rows": 672,
                "components": 658,
                "sample_order_sha256": "bee1720141a9d6283aea78d8d1b5463b36df7794dafdb4bc6cf79666901b36eb",
                "sample_membership_sha256": "bee1720141a9d6283aea78d8d1b5463b36df7794dafdb4bc6cf79666901b36eb",
                "component_membership_sha256": "18dbb847e2b76786fb69f46dcb52a6c557348a3f3e0f85fcb5634f3059afa5dc",
                "row_membership_sha256": "c827258b5a04983e6a3275629753dd5d4f941d7f6e17573bebf05708b9dab7c1",
                "source_ordinal_sha256": "e19b67c8ae0a01a30c5a3f05c6f035d9311717eb765b2a5a2845dae010ff5002",
            }
        ),
        1: MappingProxyType(
            {
                "rows": 672,
                "components": 654,
                "sample_order_sha256": "22dfbeea7a324171b56b43805b899de8c374559008bdc67d3c318a86925066f8",
                "sample_membership_sha256": "22dfbeea7a324171b56b43805b899de8c374559008bdc67d3c318a86925066f8",
                "component_membership_sha256": "4cb12ca3c60938d74371887e2698c068e7ade8c8070107fd0a66b69accb0eabd",
                "row_membership_sha256": "5fbe916de4ee482179faf848baee11643d4970c0e1bd19b469245ce3665bb18f",
                "source_ordinal_sha256": "cf903e22275b611ceddcf39b03950529c4f10a3c37f18f0be1113b2208b0a6b9",
            }
        ),
        2: MappingProxyType(
            {
                "rows": 672,
                "components": 651,
                "sample_order_sha256": "9d239194b833f53a39f09d249190bcddd50655b95d677e1d8592a874c7adc8b0",
                "sample_membership_sha256": "9d239194b833f53a39f09d249190bcddd50655b95d677e1d8592a874c7adc8b0",
                "component_membership_sha256": "c8836c38a79160f16a9fda19aacee8d7edde8ede4667be7f72a9aa45814f5260",
                "row_membership_sha256": "1538cebe05c0b0bf8f5a3a7a186ab3e46a70bfb7da20b7229e949018575d5ec9",
                "source_ordinal_sha256": "3cbe675a7af8060209c78392aa5e1d50cfeea3c103aaa7101a8b55f796e6635a",
            }
        ),
    }
)


@dataclass(frozen=True, order=True)
class InputGrant:
    scope: str
    fold_id: int


PRODUCER_ALLOWLIST = MappingProxyType(
    {
        "dev-h0": frozenset(
            {
                InputGrant("train-capable", 1),
                InputGrant("train-capable", 2),
                InputGrant("gold-free-inference", 0),
            }
        ),
        "dev-h1": frozenset(
            {
                InputGrant("train-capable", 0),
                InputGrant("train-capable", 2),
                InputGrant("gold-free-inference", 1),
            }
        ),
        "dev-h2": frozenset(
            {
                InputGrant("train-capable", 0),
                InputGrant("train-capable", 1),
                InputGrant("gold-free-inference", 2),
            }
        ),
    }
)

PUBLIC_SENSITIVE_KEYS = frozenset(
    {
        "component_id",
        "component_ids",
        "gold",
        "label",
        "labels",
        "logits",
        "prediction",
        "predictions",
        "probabilities",
        "sample_id",
        "sample_ids",
        "source_ordinal",
        "source_ordinals",
        "text",
        "texts",
    }
)


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_json_line(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"


def _require_object(value: Any, expected_fields: Sequence[str], context: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(expected_fields):
        observed = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise ContractError(
            f"{context} schema drift: expected={sorted(expected_fields)}, observed={observed}"
        )
    return value


def _require_id(value: Any, prefix: str, context: str) -> str:
    if not isinstance(value, str) or not value.startswith(prefix) or len(value) <= len(prefix):
        raise ContractError(f"invalid {context}")
    return value


def _normalize_labels(value: Any, context: str) -> list[int]:
    if (
        not isinstance(value, list)
        or len(value) != len(LABELS)
        or any(type(item) not in (bool, int) or int(item) not in (0, 1) for item in value)
    ):
        raise ContractError(f"invalid {context} labels")
    return [int(item) for item in value]


def _validate_derived(value: Mapping[str, Any], labels: Sequence[int], context: str) -> None:
    cardinality = sum(labels)
    if type(value["label_cardinality"]) is not int or value["label_cardinality"] != cardinality:
        raise ContractError(f"{context} label_cardinality drift")
    if type(value["neutral"]) is not bool or value["neutral"] is not (cardinality == 0):
        raise ContractError(f"{context} neutral drift")


def validate_source_row(scope: str, value: Any) -> dict[str, Any]:
    try:
        schema = SOURCE_SCHEMAS[scope]
    except KeyError as exc:
        raise ContractError(f"unknown source scope: {scope}") from exc
    row = _require_object(value, schema.fields, scope)
    if row["protocol_id"] != PROTOCOL_ID:
        raise ContractError(f"{scope} protocol drift")
    _require_id(row["sample_id"], "sample-", f"{scope} sample_id")
    _require_id(row["component_id"], "component-", f"{scope} component_id")

    if scope == "private-train":
        if row["schema_version"] != SOURCE_TRAIN_SCHEMA_VERSION:
            raise ContractError("private-train schema identity drift")
        if not isinstance(row["text"], str) or not row["text"]:
            raise ContractError("private-train text must be non-empty")
        labels = _normalize_labels(row["labels"], scope)
        _validate_derived(row, labels, scope)
    else:
        if row["schema_version"] != SOURCE_FOLD_SCHEMA_VERSION:
            raise ContractError(f"{scope} schema identity drift")
        if row["experiment_id"] != SOURCE_FOLD_EXPERIMENT_ID:
            raise ContractError(f"{scope} experiment identity drift")
        if type(row["fold_id"]) is not int or row["fold_id"] not in range(5):
            raise ContractError(f"{scope} fold_id drift")
        if scope == "private-fold-manifest":
            labels = _normalize_labels(row["labels"], scope)
            _validate_derived(row, labels, scope)
    return row


def parse_source_json_line(scope: str, line: str, source_ordinal: int) -> dict[str, Any]:
    if type(source_ordinal) is not int or source_ordinal < 0:
        raise ContractError("source_ordinal must be a nonnegative integer")
    if not isinstance(line, str) or not line.strip():
        raise ContractError(f"empty {scope} JSONL line at ordinal {source_ordinal}")
    try:
        value = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid {scope} JSON at ordinal {source_ordinal}") from exc
    return validate_source_row(scope, value)


def materialize_selected_row(
    public_fold_row: Mapping[str, Any],
    private_train_row: Mapping[str, Any],
    private_fold_row: Mapping[str, Any],
    source_ordinal: int,
) -> dict[str, dict[str, Any]]:
    public = validate_source_row("public-fold-manifest", dict(public_fold_row))
    train = validate_source_row("private-train", dict(private_train_row))
    private = validate_source_row("private-fold-manifest", dict(private_fold_row))
    if type(source_ordinal) is not int or source_ordinal < 0:
        raise ContractError("source_ordinal must be a nonnegative integer")
    if public["fold_id"] not in MATERIALIZED_FOLDS:
        raise ContractError("SQMA-002 may materialize only folds 0-2")
    identities = {
        (public["sample_id"], public["component_id"]),
        (train["sample_id"], train["component_id"]),
        (private["sample_id"], private["component_id"]),
    }
    if len(identities) != 1 or private["fold_id"] != public["fold_id"]:
        raise ContractError("source-order join identity drift")
    normalized = _normalize_labels(train["labels"], "private-train")
    if normalized != _normalize_labels(private["labels"], "private-fold-manifest"):
        raise ContractError("source-order join label drift")
    if (
        train["neutral"] is not private["neutral"]
        or train["label_cardinality"] != private["label_cardinality"]
    ):
        raise ContractError("source-order join derived-field drift")

    common = {
        "protocol_id": PROTOCOL_ID,
        "sample_id": train["sample_id"],
        "component_id": train["component_id"],
        "fold_id": public["fold_id"],
        "source_ordinal": source_ordinal,
    }
    return {
        "train-capable": {
            "schema_version": OUTPUT_SCHEMAS["train-capable"].schema_id,
            **common,
            "text": train["text"],
            "labels": normalized,
            "label_cardinality": train["label_cardinality"],
            "neutral": train["neutral"],
        },
        "gold-free-inference": {
            "schema_version": OUTPUT_SCHEMAS["gold-free-inference"].schema_id,
            **common,
            "text": train["text"],
        },
        "consumer-gold": {
            "sample_id": train["sample_id"],
            "component_id": train["component_id"],
            "fold_id": public["fold_id"],
            "source_ordinal": source_ordinal,
            "gold": normalized,
        },
    }


def validate_output_json_row(scope: str, value: Any, expected_fold: int) -> dict[str, Any]:
    if scope not in ("train-capable", "gold-free-inference"):
        raise ContractError(f"scope is not a JSONL output: {scope}")
    if expected_fold not in MATERIALIZED_FOLDS:
        raise ContractError("output fold must be one of 0, 1, 2")
    schema = OUTPUT_SCHEMAS[scope]
    row = _require_object(value, schema.fields, scope)
    if row["schema_version"] != schema.schema_id or row["protocol_id"] != PROTOCOL_ID:
        raise ContractError(f"{scope} identity drift")
    _require_id(row["sample_id"], "sample-", f"{scope} sample_id")
    _require_id(row["component_id"], "component-", f"{scope} component_id")
    if row["fold_id"] != expected_fold:
        raise ContractError(f"{scope} fold drift")
    if type(row["source_ordinal"]) is not int or row["source_ordinal"] < 0:
        raise ContractError(f"{scope} source_ordinal drift")
    if not isinstance(row["text"], str) or not row["text"]:
        raise ContractError(f"{scope} text must be non-empty")
    if scope == "train-capable":
        labels = _normalize_labels(row["labels"], scope)
        _validate_derived(row, labels, scope)
    elif {"gold", "label", "labels", "neutral", "label_cardinality"} & set(row):
        raise ContractError("gold-free-inference contains a gold-derived field")
    return row


def membership_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    sample_ids = [str(row["sample_id"]) for row in rows]
    component_ids = [str(row["component_id"]) for row in rows]
    fold_ids = [int(row["fold_id"]) for row in rows]
    source_ordinals = [int(row["source_ordinal"]) for row in rows]
    row_membership = sorted(zip(sample_ids, component_ids, fold_ids, strict=True))
    return {
        "rows": len(rows),
        "components": len(set(component_ids)),
        "sample_order_sha256": canonical_digest(sample_ids),
        "sample_membership_sha256": canonical_digest(sorted(sample_ids)),
        "component_membership_sha256": canonical_digest(sorted(set(component_ids))),
        "row_membership_sha256": canonical_digest(row_membership),
        "source_ordinal_sha256": canonical_digest(source_ordinals),
    }


def validate_output_rows(
    scope: str,
    rows: Sequence[Mapping[str, Any]],
    fold_id: int,
    *,
    require_frozen_identity: bool = True,
) -> dict[str, Any]:
    validated = [validate_output_json_row(scope, dict(row), fold_id) for row in rows]
    ordinals = [row["source_ordinal"] for row in validated]
    if ordinals != sorted(ordinals) or len(ordinals) != len(set(ordinals)):
        raise ContractError(f"{scope} source order is not strictly increasing")
    sample_ids = [row["sample_id"] for row in validated]
    if len(sample_ids) != len(set(sample_ids)):
        raise ContractError(f"{scope} contains duplicate samples")
    summary = membership_summary(validated)
    if require_frozen_identity:
        try:
            expected = EXPECTED_FOLD_IDENTITY[fold_id]
        except KeyError as exc:
            raise ContractError("no frozen identity for output fold") from exc
        if any(summary[key] != expected[key] for key in expected):
            raise ContractError(f"{scope} fold {fold_id} membership drift")
    return summary


def validate_consumer_gold_arrays(
    observed: Mapping[str, Mapping[str, Any]], fold_id: int
) -> None:
    if fold_id not in MATERIALIZED_FOLDS:
        raise ContractError("consumer-gold fold must be one of 0, 1, 2")
    if set(observed) != set(CONSUMER_GOLD_ARRAYS):
        raise ContractError("consumer-gold array inventory drift")
    for name, expected in CONSUMER_GOLD_ARRAYS.items():
        value = observed[name]
        if not isinstance(value, Mapping) or set(value) != {"dtype", "shape"}:
            raise ContractError(f"consumer-gold metadata drift: {name}")
        if value["dtype"] != expected.dtype or tuple(value["shape"]) != expected.shape:
            raise ContractError(f"consumer-gold dtype/shape drift: {name}")


def validate_producer_request(
    fit_id: str, requested: Iterable[InputGrant | tuple[str, int]]
) -> frozenset[InputGrant]:
    try:
        expected = PRODUCER_ALLOWLIST[fit_id]
    except KeyError as exc:
        raise ContractError(f"fit is not authorized for Agent-Dev production: {fit_id}") from exc
    normalized: set[InputGrant] = set()
    for value in requested:
        grant = value if isinstance(value, InputGrant) else InputGrant(*value)
        if grant.scope not in {"train-capable", "gold-free-inference"}:
            raise ContractError(f"producer may not request scope: {grant.scope}")
        if grant.fold_id not in MATERIALIZED_FOLDS:
            raise ContractError(f"producer may not request fold: {grant.fold_id}")
        normalized.add(grant)
    if frozenset(normalized) != expected:
        raise ContractError(f"producer request does not exactly match allowlist for {fit_id}")
    return expected


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in PUBLIC_SENSITIVE_KEYS:
                violations.append(path)
            violations.extend(public_sensitive_paths(child, path))
    elif isinstance(value, (list, tuple, set, frozenset)):
        for index, child in enumerate(value):
            violations.extend(public_sensitive_paths(child, f"{prefix}[{index}]"))
    elif isinstance(value, str) and (
        value.startswith("sample-") or value.startswith("component-")
    ):
        violations.append(prefix)
    return violations


def assert_public_safe(value: Any) -> None:
    violations = public_sensitive_paths(value)
    if violations:
        raise ContractError(f"public value contains sensitive material: {violations}")


# Import-time invariants guard the frozen contract without opening a file.
if set(OUTPUT_SCHEMAS["gold-free-inference"].fields) & {
    "gold",
    "label",
    "labels",
    "neutral",
    "label_cardinality",
}:
    raise RuntimeError("gold-free inference schema contains a gold-derived field")
for _fit_id, _grants in PRODUCER_ALLOWLIST.items():
    validate_producer_request(_fit_id, _grants)
