#!/usr/bin/env python3
"""Static contract helpers for strict M1/M3 base production.

This module is deliberately standard-library-only.  It reads only the public
EXP-058 fold manifest; private snapshots, labels, model files, and model
runtimes are outside its scope.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence


LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
PUBLIC_MANIFEST_BASENAME = "fold-manifest.public.jsonl"
EXPECTED_PUBLIC_MANIFEST_SHA256 = (
    "82929b1d837ceb9825c5bc39a8fea18f6d0736fca42aad630f3788b1ff8139d8"
)
EXPECTED_PUBLIC_MEMBERSHIP_SHA256 = (
    "9b12df57f94c970176b9668f51bb04690ac4a7680803ab89876ddcb34680ad07"
)
PUBLIC_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "experiment_id",
        "protocol_id",
        "sample_id",
        "component_id",
        "fold_id",
    }
)
EXPECTED_MANIFEST_IDENTITY = {
    "schema_version": "exp-058-fold-row-v1",
    "experiment_id": "EXP-058",
    "protocol_id": "DATA-SO-TASK-V1",
}
EXPECTED_FOLD_COUNTS = {
    0: {"rows": 672, "components": 658},
    1: {"rows": 672, "components": 654},
    2: {"rows": 672, "components": 651},
    3: {"rows": 672, "components": 657},
    4: {"rows": 672, "components": 657},
}


class ContractError(ValueError):
    """Raised when the frozen strict-base contract is violated."""


@dataclass(frozen=True)
class FitSpec:
    fit_id: str
    phase: str
    train_folds: tuple[int, ...]
    heldout_folds: tuple[int, ...]


FULL_FIT_PLAN = (
    FitSpec("dev-h0", "dev", (1, 2), (0,)),
    FitSpec("dev-h1", "dev", (0, 2), (1,)),
    FitSpec("dev-h2", "dev", (0, 1), (2,)),
    FitSpec("tune-h3", "tune", (0, 1, 2), (3,)),
    FitSpec("final-h0", "final-development", (1, 2, 3), (0,)),
    FitSpec("final-h1", "final-development", (0, 2, 3), (1,)),
    FitSpec("final-h2", "final-development", (0, 1, 3), (2,)),
)
ACTIVE_DEV_FIT_IDS = ("dev-h0", "dev-h1", "dev-h2")
VIEW_FIT_IDS = {
    "dev": ACTIVE_DEV_FIT_IDS,
    "tune": ("tune-h3",),
    "final-development": ("final-h0", "final-h1", "final-h2", "tune-h3"),
}


@dataclass(frozen=True)
class SnapshotSchema:
    schema_id: str
    format: str
    fields: tuple[str, ...]
    contains_text: bool
    contains_gold: bool
    allowed_consumer: str


SCOPED_SNAPSHOT_SCHEMAS = {
    "train-capable": SnapshotSchema(
        "sqma-train-capable-snapshot-v1",
        "jsonl",
        (
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
        ),
        contains_text=True,
        contains_gold=True,
        allowed_consumer="fit_training_only",
    ),
    "gold-free-inference": SnapshotSchema(
        "sqma-gold-free-inference-snapshot-v1",
        "jsonl",
        (
            "schema_version",
            "protocol_id",
            "sample_id",
            "component_id",
            "fold_id",
            "source_ordinal",
            "text",
        ),
        contains_text=True,
        contains_gold=False,
        allowed_consumer="heldout_forward_only",
    ),
    "consumer-gold": SnapshotSchema(
        "sqma-consumer-gold-snapshot-v1",
        "npz",
        (
            "sample_ids",
            "component_ids",
            "fold_ids",
            "source_ordinals",
            "gold",
        ),
        contains_text=False,
        contains_gold=True,
        allowed_consumer="authorized_metric_consumer_only",
    ),
}

HELDOUT_LOGITS_SCHEMA = SnapshotSchema(
    "sqma-heldout-logits-v1",
    "npz",
    (
        "sample_ids",
        "component_ids",
        "fold_ids",
        "logits",
        "character_lengths",
        "token_lengths",
    ),
    contains_text=False,
    contains_gold=False,
    allowed_consumer="paired_base_assembler",
)

# Stable public export used by the future runner and verifier.  The values are
# immutable dataclasses; callers must validate observed fields rather than
# mutating this mapping.
SNAPSHOT_CONTRACT = MappingProxyType({
    **SCOPED_SNAPSHOT_SCHEMAS,
    "heldout-logits": HELDOUT_LOGITS_SCHEMA,
})

PUBLIC_SENSITIVE_KEYS = frozenset(
    {
        "component_id",
        "component_ids",
        "gold",
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


@dataclass(frozen=True)
class ManifestRow:
    source_ordinal: int
    sample_id: str
    component_id: str
    fold_id: int


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_fit_plan(plans: Sequence[FitSpec]) -> tuple[FitSpec, ...]:
    frozen = tuple(plans)
    expected_by_id = {fit.fit_id: fit for fit in FULL_FIT_PLAN}
    ids = [fit.fit_id for fit in frozen]
    if len(ids) != len(set(ids)):
        raise ContractError("fit plan contains a duplicate fit_id")
    if set(ids) != set(expected_by_id):
        missing = sorted(set(expected_by_id) - set(ids))
        extra = sorted(set(ids) - set(expected_by_id))
        raise ContractError(f"fit plan is incomplete or unexpected: missing={missing}, extra={extra}")
    if ids != list(expected_by_id):
        raise ContractError("fit plan order differs from the frozen execution order")

    for fit in frozen:
        if fit.phase not in {"dev", "tune", "final-development"}:
            raise ContractError(f"unknown phase for {fit.fit_id}: {fit.phase}")
        if not fit.train_folds or len(fit.heldout_folds) != 1:
            raise ContractError(f"{fit.fit_id} must have train folds and one held-out fold")
        if tuple(sorted(set(fit.train_folds))) != fit.train_folds:
            raise ContractError(f"{fit.fit_id} train_folds must be sorted and unique")
        if tuple(sorted(set(fit.heldout_folds))) != fit.heldout_folds:
            raise ContractError(f"{fit.fit_id} heldout_folds must be sorted and unique")
        all_folds = set(fit.train_folds) | set(fit.heldout_folds)
        if 4 in all_folds or not all_folds <= {0, 1, 2, 3}:
            raise ContractError(f"{fit.fit_id} injects forbidden fold 4 or an unknown fold")
        if set(fit.train_folds) & set(fit.heldout_folds):
            raise ContractError(f"{fit.fit_id} has train/held-out overlap")
        if fit != expected_by_id[fit.fit_id]:
            raise ContractError(f"{fit.fit_id} differs from its frozen train/held-out mapping")

    active = tuple(fit.fit_id for fit in frozen if fit.phase == "dev")
    if active != ACTIVE_DEV_FIT_IDS:
        raise ContractError("active Agent-Dev plan must contain exactly the three frozen Dev fits")
    return frozen


def active_dev_plan(plans: Sequence[FitSpec] = FULL_FIT_PLAN) -> tuple[FitSpec, ...]:
    return tuple(fit for fit in validate_fit_plan(plans) if fit.fit_id in ACTIVE_DEV_FIT_IDS)


def validate_snapshot_schema(scope: str, fields: Iterable[str]) -> SnapshotSchema:
    if scope == "heldout-logits":
        expected = HELDOUT_LOGITS_SCHEMA
    else:
        try:
            expected = SCOPED_SNAPSHOT_SCHEMAS[scope]
        except KeyError as exc:
            raise ContractError(f"unknown snapshot scope: {scope}") from exc
    observed = tuple(fields)
    if len(observed) != len(set(observed)) or set(observed) != set(expected.fields):
        raise ContractError(
            f"{scope} schema drift: expected={sorted(expected.fields)}, observed={sorted(observed)}"
        )
    if scope in {"gold-free-inference", "heldout-logits"}:
        forbidden = {"gold", "label", "labels", "targets"} & set(observed)
        if forbidden or expected.contains_gold:
            raise ContractError(f"{scope} must remain gold-free")
    return expected


def m1_schedule(
    training_rows: int,
    *,
    batch_size: int = 16,
    planned_epochs: int = 5,
    stop_epochs: int = 4,
    warmup_ratio: float = 0.1,
) -> dict[str, int]:
    if min(training_rows, batch_size, planned_epochs, stop_epochs) <= 0:
        raise ContractError("M1 schedule inputs must be positive")
    steps_per_epoch = math.ceil(training_rows / batch_size)
    horizon = steps_per_epoch * planned_epochs
    warmup_exact = horizon * warmup_ratio
    if not warmup_exact.is_integer():
        raise ContractError("M1 warmup steps must be integral")
    return {
        "training_rows": training_rows,
        "batch_size": batch_size,
        "steps_per_epoch": steps_per_epoch,
        "planned_scheduler_epochs": planned_epochs,
        "scheduler_horizon_steps": horizon,
        "warmup_steps": int(warmup_exact),
        "selected_stop_epoch": stop_epochs,
        "selected_stop_steps": steps_per_epoch * stop_epochs,
    }


def m3_schedule(training_rows: int, *, epochs: int = 2, batch_size: int = 1) -> dict[str, int]:
    if min(training_rows, epochs, batch_size) <= 0:
        raise ContractError("M3 schedule inputs must be positive")
    steps_per_epoch = math.ceil(training_rows / batch_size)
    return {
        "training_rows": training_rows,
        "batch_size": batch_size,
        "epochs": epochs,
        "steps_per_epoch": steps_per_epoch,
        "optimizer_steps": steps_per_epoch * epochs,
    }


def load_public_fold_manifest(path: Path) -> tuple[ManifestRow, ...]:
    path = Path(path)
    if path.name != PUBLIC_MANIFEST_BASENAME:
        raise ContractError(f"only {PUBLIC_MANIFEST_BASENAME} may be read")
    if not os.path.lexists(path):
        raise ContractError(f"public fold manifest is missing: {path}")
    observed = os.lstat(path)
    if stat.S_ISLNK(observed.st_mode) or not stat.S_ISREG(observed.st_mode):
        raise ContractError("public fold manifest must be a regular non-symlink file")

    rows: list[ManifestRow] = []
    sample_ids: set[str] = set()
    component_fold: dict[str, int] = {}
    with path.open("r", encoding="utf-8") as source:
        for ordinal, line in enumerate(source):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ContractError(f"invalid public manifest JSON at line {ordinal + 1}") from exc
            if not isinstance(value, dict) or set(value) != PUBLIC_MANIFEST_FIELDS:
                raise ContractError(f"public manifest schema drift at line {ordinal + 1}")
            if any(value[key] != expected for key, expected in EXPECTED_MANIFEST_IDENTITY.items()):
                raise ContractError(f"public manifest identity drift at line {ordinal + 1}")
            sample_id = value["sample_id"]
            component_id = value["component_id"]
            fold_id = value["fold_id"]
            if not isinstance(sample_id, str) or not isinstance(component_id, str):
                raise ContractError(f"invalid public IDs at line {ordinal + 1}")
            if type(fold_id) is not int or fold_id not in range(5):
                raise ContractError(f"invalid fold ID at line {ordinal + 1}")
            if sample_id in sample_ids:
                raise ContractError(f"duplicate sample ID at line {ordinal + 1}")
            prior_fold = component_fold.setdefault(component_id, fold_id)
            if prior_fold != fold_id:
                raise ContractError(f"component crosses folds at line {ordinal + 1}")
            sample_ids.add(sample_id)
            rows.append(ManifestRow(ordinal, sample_id, component_id, fold_id))
    if not rows:
        raise ContractError("public fold manifest is empty")
    return tuple(rows)


def load_public_manifest(path: Path) -> tuple[ManifestRow, ...]:
    """Stable runner/verifier API for the public EXP-058 fold manifest."""

    return load_public_fold_manifest(path)


def _membership_summary(rows: Sequence[ManifestRow]) -> dict[str, Any]:
    sample_ids = [row.sample_id for row in rows]
    components = sorted({row.component_id for row in rows})
    membership = sorted((row.sample_id, row.component_id, row.fold_id) for row in rows)
    return {
        "rows": len(rows),
        "components": len(components),
        "sample_order_sha256": canonical_digest(sample_ids),
        "sample_membership_sha256": canonical_digest(sorted(sample_ids)),
        "component_membership_sha256": canonical_digest(components),
        "row_membership_sha256": canonical_digest(membership),
    }


def aggregate_public_manifest(rows: Sequence[ManifestRow]) -> dict[str, Any]:
    values = tuple(rows)
    fold_summary = {
        str(fold): _membership_summary([row for row in values if row.fold_id == fold])
        for fold in range(5)
    }
    return {
        "schema_version": "sqma-public-fold-membership-v1",
        "rows": len(values),
        "components": len({row.component_id for row in values}),
        "membership_sha256": canonical_digest(
            [(row.sample_id, row.component_id, row.fold_id) for row in values]
        ),
        "folds": fold_summary,
    }


def validate_exp058_public_manifest(rows: Sequence[ManifestRow]) -> dict[str, Any]:
    summary = aggregate_public_manifest(rows)
    if summary["rows"] != 3360 or summary["components"] != 3277:
        raise ContractError("EXP-058 public manifest total count drift")
    if summary["membership_sha256"] != EXPECTED_PUBLIC_MEMBERSHIP_SHA256:
        raise ContractError("EXP-058 public manifest membership drift")
    for fold, expected in EXPECTED_FOLD_COUNTS.items():
        observed = summary["folds"][str(fold)]
        if observed["rows"] != expected["rows"] or observed["components"] != expected["components"]:
            raise ContractError(f"EXP-058 public manifest fold {fold} count drift")
    return summary


def summarize_fit(rows: Sequence[ManifestRow], fit: FitSpec) -> dict[str, Any]:
    validate_fit_plan(FULL_FIT_PLAN)
    expected = {item.fit_id: item for item in FULL_FIT_PLAN}.get(fit.fit_id)
    if fit != expected:
        raise ContractError(f"fit is not frozen: {fit.fit_id}")
    training = [row for row in rows if row.fold_id in fit.train_folds]
    heldout = [row for row in rows if row.fold_id in fit.heldout_folds]
    if not training or not heldout:
        raise ContractError(f"fit membership is empty: {fit.fit_id}")
    training_components = {row.component_id for row in training}
    heldout_components = {row.component_id for row in heldout}
    if training_components & heldout_components:
        raise ContractError(f"fit has component leakage: {fit.fit_id}")
    return {
        "fit_id": fit.fit_id,
        "phase": fit.phase,
        "train_folds": list(fit.train_folds),
        "heldout_folds": list(fit.heldout_folds),
        "training": _membership_summary(training),
        "heldout": _membership_summary(heldout),
        "m1_schedule": m1_schedule(len(training)),
        "m3_schedule": m3_schedule(len(training)),
    }


def validate_full_plan(plans: Sequence[FitSpec]) -> tuple[FitSpec, ...]:
    """Stable runner/verifier API for the complete seven-fit plan."""

    return validate_fit_plan(plans)


def summarize_active_dev(rows: Sequence[ManifestRow]) -> tuple[dict[str, Any], ...]:
    """Return summaries for exactly the three currently active Dev fits."""

    return tuple(summarize_fit(rows, fit) for fit in active_dev_plan())


def m3_steps(training_rows: int) -> int:
    """Return the frozen two-epoch, batch-one M3 optimizer-step count."""

    return m3_schedule(training_rows)["optimizer_steps"]


def strict_base_public_contract(
    manifest_path: Path, plans: Sequence[FitSpec] = FULL_FIT_PLAN
) -> dict[str, Any]:
    frozen_plan = validate_fit_plan(plans)
    rows = load_public_fold_manifest(manifest_path)
    manifest_summary = validate_exp058_public_manifest(rows)
    manifest_file_sha256 = sha256(Path(manifest_path))
    if manifest_file_sha256 != EXPECTED_PUBLIC_MANIFEST_SHA256:
        raise ContractError("EXP-058 public manifest file identity drift")
    value = {
        "schema_version": "sqma-strict-base-public-contract-v1",
        "manifest": {
            "bytes": Path(manifest_path).stat().st_size,
            "sha256": manifest_file_sha256,
            **manifest_summary,
        },
        "fit_count_per_family": len(frozen_plan),
        "families": ["m1", "m3"],
        "active_dev_fit_ids": list(ACTIVE_DEV_FIT_IDS),
        "views": {key: list(fit_ids) for key, fit_ids in VIEW_FIT_IDS.items()},
        "fits": [summarize_fit(rows, fit) for fit in frozen_plan],
        "snapshot_contracts": {
            scope: {
                "schema_id": schema.schema_id,
                "format": schema.format,
                "contains_text": schema.contains_text,
                "contains_gold": schema.contains_gold,
                "allowed_consumer": schema.allowed_consumer,
            }
            for scope, schema in SCOPED_SNAPSHOT_SCHEMAS.items()
        },
        "heldout_logits": {
            "schema_id": HELDOUT_LOGITS_SCHEMA.schema_id,
            "format": HELDOUT_LOGITS_SCHEMA.format,
            "contains_gold": HELDOUT_LOGITS_SCHEMA.contains_gold,
            "allowed_consumer": HELDOUT_LOGITS_SCHEMA.allowed_consumer,
        },
        "access": {
            "private_files_read": False,
            "model_imported": False,
            "fold4_in_fit_plan": False,
            "validation_accessed": False,
            "test_accessed": False,
        },
    }
    assert_public_safe(value)
    return value


def public_sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    violations: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            if key in PUBLIC_SENSITIVE_KEYS:
                violations.append(path)
            violations.extend(public_sensitive_paths(child, path))
    elif isinstance(value, (list, tuple)):
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
        raise ContractError(f"public value contains sensitive fields: {violations}")


# Import-time invariants cover constants without reading any file.
validate_fit_plan(FULL_FIT_PLAN)
for _scope, _schema in SCOPED_SNAPSHOT_SCHEMAS.items():
    validate_snapshot_schema(_scope, _schema.fields)
validate_snapshot_schema("heldout-logits", HELDOUT_LOGITS_SCHEMA.fields)
