#!/usr/bin/env python3
"""Independent verifier for the registered EXP-071 drift consumer.

The static stages inspect identities, filesystem state, NPY/NPZ headers and
the synthetic suite without importing NumPy or reading scientific values.  The
formal stages independently reopen the sixteen representation matrices and the
two allowed row-contract members, reproduce every geometry value and public
summary, and replay the exact verification payload before completion.

This module intentionally does not import the producing program.
"""

from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import resource
import shutil
import stat
import struct
import subprocess
import sys
import time
from typing import Any, Iterator, Mapping, Sequence
import zipfile


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
HISTORICAL_STATIC_CONFIG = MODULE_DIR / "configs" / "exp-071-representation-drift-preflight.json"
DEFAULT_STATIC_CONFIG = (
    MODULE_DIR / "configs" / "exp-071-representation-drift-preflight-attempt-2.json"
)
DEFAULT_FORMAL_CONFIG = MODULE_DIR / "configs" / "exp-071-representation-drift-formal.json"
HEAVY_LOCK = MODULE_DIR / "private" / "locks" / "heavy-research-workload.lock"
VERIFIER_LOCK = MODULE_DIR / "private" / "locks" / "exp071-representation-drift-verifier.lock"

EXPERIMENT_ID = "EXP-071"
ROWS = 3360
FOLDS = (0, 1, 2, 3, 4)
HELDOUT_ROWS = 672
HIDDEN_SIZE = 2560
ALL_POINTS = ("H-1", "H7", "H15", "H19", "H20", "H27", "H31", "H35", "HF")
CONFIRMATION_POINTS = ("H19", "H27", "HF")
CONDITION_ORDER = tuple(
    [f"s42:{point}" for point in ALL_POINTS]
    + [f"s43:{point}" for point in CONFIRMATION_POINTS]
    + [f"s44:{point}" for point in CONFIRMATION_POINTS]
)
SANITY_CONDITIONS = frozenset(
    [f"s42:{point}" for point in ("H-1", "H7", "H15", "H19")]
    + ["s43:H19", "s44:H19"]
)
NPZ_MEMBER_ORDER = (
    "heldout_ordinals",
    "cosine_distance",
    "relative_l2_distance",
    "linear_cka",
    "max_abs_difference",
)
NPZ_MEMBERS = {
    "heldout_ordinals": {"shape": [5, 672], "dtype": "<i4"},
    "cosine_distance": {"shape": [15, 3360], "dtype": "<f8"},
    "relative_l2_distance": {"shape": [15, 3360], "dtype": "<f8"},
    "linear_cka": {"shape": [15, 5], "dtype": "<f8"},
    "max_abs_difference": {"shape": [15, 5], "dtype": "<f8"},
}
METHOD_SHA256 = "f428523680acd2dd130bb78ac3bcdebbceec2b64ced18730e936323e685cc210"
EXPECTED_SOURCE_SHA256 = "8f7bc1836021053d0ffd48a620170996ed72475f54c57034ca2591dd515dffcf"
EXPECTED_SOURCE_CANONICAL_BYTES = 13166
METHOD_PROTOCOL_RECORD = {
    "path": "experiments/stack-overflow-emotion-gold/protocols/exp-071-representation-drift.md",
    "bytes": 13708,
    "mode": "0644",
    "sha256": "7d03bde05da6b83e4db9e0c3396140fba6fd7418a8c678ce4a825e0d9208e099",
}
STATIC_CLAIM_BOUNDARY = (
    "A no-result static readiness check for the registered EXP-071 heldout "
    "representation-drift consumer. It authorizes no representation-value or "
    "probe-result access, geometry calculation, state assignment, model load, "
    "forward pass, validation, test, onset, significance, causal, independent-data, "
    "production or emotion-mechanism claim."
)
FORMAL_CLAIM_BOUNDARY = (
    "A formal same-sample outer-heldout Frozen-Qwen versus fold-specific M3 "
    "representation-drift analysis under the registered float64 cosine, "
    "Frozen-denominator relative L2, fold-local biased linear CKA and one seed-42 "
    "descriptive Spearman contract. It is limited to train-only fold-specific "
    "outer-heldout last-token geometry, assigns no EXP-071 state, and supports no "
    "exact onset, significance, causal mechanism, independent-data or test "
    "generalization, production-readiness, emotion-neuron or human-emotion-mechanism "
    "claim. It authorizes no model load, forward pass, label, component-code, "
    "sample-ID, private-probe-artifact, probability, prediction, train-text, "
    "validation or test access."
)
IMPLEMENTATION_PATHS = {
    "runner": (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/"
        "run_exp071_drift.py"
    ),
    "verifier": (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/"
        "verify_exp071_drift.py"
    ),
    "tests": (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/tests/"
        "test_exp071_drift.py"
    ),
}
ATTEMPT1_CONFIG_RECORD = {
    "path": (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/configs/"
        "exp-071-representation-drift-preflight.json"
    ),
    "bytes": 25672,
    "mode": "0644",
    "sha256": "9a030313ffe5d4e3bf40104327b749f319bf3707c93f12866d0ebe5369b084a7",
}
ATTEMPT1_FAILURE_RECORD = {
    "path": (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
        "exp-071-representation-drift/preflight-attempt-1/failure.json"
    ),
    "bytes": 395,
    "mode": "0644",
    "sha256": "e586400fd2ea57a98c5c4dc06f9d4c719b41d358947c9be9cc5a40211cd5ca33",
}
INCIDENT_001 = {
    "id": "EXP-071-PREFLIGHT-INCIDENT-001",
    "failed_config": ATTEMPT1_CONFIG_RECORD,
    "failure_artifact": ATTEMPT1_FAILURE_RECORD,
    "root_cause": "relative_config_path_not_resolved_before_stage_dispatch",
    "recovery_scope": "resolve_config_path_and_use_fresh_preflight_namespace_only",
}
ROW_CONTRACT_HEADERS = {
    "ordinal": {"shape": [3360], "dtype": "<i4", "fortran_order": False},
    "fold_id": {"shape": [3360], "dtype": "|i1", "fortran_order": False},
    "component_code": {"shape": [3360], "dtype": "<i4", "fortran_order": False},
}
ENVIRONMENT = {
    "python_executable": "/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python",
    "python_version": "3.10.20",
    "architecture": "arm64",
    "packages": {"numpy": "2.2.6"},
    "thread_environment": {
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    },
}
FORBIDDEN_MODEL_MODULES = {"mlx", "mlx_lm", "torch", "transformers"}
PUBLIC_FORBIDDEN_KEYS = {
    "ordinal",
    "ordinals",
    "heldout_ordinals",
    "rowwise",
    "rowwise_values",
    "sample_id",
    "sample_ids",
    "component_id",
    "component_ids",
    "component_code",
    "component_codes",
    "label",
    "labels",
    "probability",
    "probabilities",
    "prediction",
    "predictions",
    "representation",
    "representations",
    "text",
    "train_text",
}

STATIC_ACCESS = {
    "bound_source_file_bytes_hashed": True,
    "json_terminal_status_fields_read": True,
    "npy_headers_read": True,
    "npz_headers_read": True,
    "representation_values_read": False,
    "row_contract_values_read": False,
    "component_code_values_read": False,
    "probe_metric_values_read": False,
    "private_probe_artifacts_read": False,
    "labels_read": False,
    "sample_ids_read": False,
    "component_ids_read": False,
    "train_text_read": False,
    "model_loaded": False,
    "forward_executed": False,
    "validation_accessed": False,
    "test_accessed": False,
    "test_gate_accessed": False,
    "scientific_geometry_computed": False,
    "synthetic_fixtures_executed": True,
}
INITIALIZE_ACCESS = {**STATIC_ACCESS, "formal_roots_created": True}
ANALYZE_ACCESS = {
    "bound_source_file_bytes_hashed": True,
    "representation_values_read": True,
    "outer_heldout_representation_values_read": True,
    "outer_train_representation_values_read": False,
    "row_contract_ordinal_values_read": True,
    "row_contract_fold_id_values_read": True,
    "row_contract_component_code_values_read": False,
    "probe_metric_values_read": True,
    "private_probe_artifacts_read": False,
    "labels_read": False,
    "sample_ids_read": False,
    "component_ids_read": False,
    "train_text_read": False,
    "exp069_smoke_representation_values_read": False,
    "model_loaded": False,
    "forward_executed": False,
    "validation_accessed": False,
    "test_accessed": False,
    "test_gate_accessed": False,
    "source_mutated": False,
}

STATIC_CHECKS = (
    "config_identity",
    "method_identity",
    "implementation_identity",
    "implementation_import_boundary",
    "synthetic_suite",
    "environment_identity",
    "authorization_boundary",
    "access_boundary",
    "parent_terminal_bindings",
    "sixteen_matrix_identities",
    "sixteen_matrix_headers",
    "row_contract_identity_and_headers",
    "probe_identity_without_metric_access",
    "source_snapshot_identity",
    "static_public_inventory_modes_links",
    "static_private_inventory_modes_links",
    "static_runner_payload",
    "static_private_contract",
    "formal_roots_absent",
    "private_budget",
    "public_privacy",
    "source_unchanged",
    "no_scientific_value_read",
    "no_model_or_producer_import",
)

FORMAL_CHECKS = (
    "config_identity",
    "method_identity",
    "implementation_identity",
    "static_completion_exact_replay",
    "environment_identity",
    "authorization_boundary",
    "access_boundary",
    "parent_terminal_bindings",
    "sixteen_matrix_identities",
    "sixteen_readonly_matrix_mappings",
    "row_contract_allowed_members_only",
    "row_ordinal_partition",
    "public_probe_results_digest",
    "nine_allowed_probe_deltas_only",
    "formal_public_inventory_modes_links",
    "formal_private_inventory_modes_links",
    "run_claim_binding",
    "input_manifest_binding",
    "geometry_bundle_schema",
    "geometry_manifest_binding",
    "condition_and_fold_order",
    "seventy_five_comparisons",
    "finite_numeric_values",
    "independent_cosine_distance",
    "independent_relative_l2_distance",
    "independent_fold_local_linear_cka",
    "independent_maximum_absolute_difference",
    "independent_fold_statistics",
    "independent_pooled_statistics",
    "pre_lora_sanity_gate",
    "single_seed42_spearman",
    "drift_report_exact_results",
    "source_before_after_identity",
    "resource_ceilings",
    "private_budget",
    "access_attestations",
    "public_exact_schema_privacy",
    "no_model_forward_validation_test",
    "source_unchanged",
    "no_producer_import",
)


def _no_constant(value: str) -> Any:
    raise ValueError(f"Non-finite JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json_bytes(payload: bytes) -> Any:
    return json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_no_constant,
    )


def strict_json(path: Path) -> Any:
    return strict_json_bytes(path.read_bytes())


class _SelectiveJSON:
    """Lexically walk JSON while materializing only allowlisted scalar paths."""

    def __init__(
        self,
        payload: bytes,
        targets: Sequence[tuple[str, ...]],
        capture_paths: Sequence[tuple[str, ...]],
    ) -> None:
        try:
            self.text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Invalid UTF-8 JSON") from exc
        self.length = len(self.text)
        self.targets = frozenset(targets)
        self.capture_paths = frozenset(capture_paths)
        self.prefixes = frozenset(
            target[:size]
            for target in self.targets | self.capture_paths
            for size in range(len(target) + 1)
        )
        self.values: dict[tuple[str, ...], Any] = {}
        self.spans: dict[tuple[str, ...], tuple[int, int]] = {}

    def _space(self, position: int) -> int:
        while position < self.length and self.text[position] in " \t\r\n":
            position += 1
        return position

    def _string_end(self, position: int) -> int:
        if position >= self.length or self.text[position] != '"':
            raise ValueError("Expected JSON string")
        position += 1
        while position < self.length:
            character = self.text[position]
            if character == '"':
                return position + 1
            if character == "\\":
                position += 1
                if position >= self.length:
                    raise ValueError("Truncated JSON escape")
                if self.text[position] == "u":
                    token = self.text[position + 1 : position + 5]
                    if len(token) != 4 or any(item not in "0123456789abcdefABCDEF" for item in token):
                        raise ValueError("Invalid JSON unicode escape")
                    position += 4
            elif ord(character) < 0x20:
                raise ValueError("Invalid JSON control character")
            position += 1
        raise ValueError("Unterminated JSON string")

    def _key(self, position: int) -> tuple[str, int]:
        stop = self._string_end(position)
        value = json.loads(self.text[position:stop])
        if type(value) is not str:
            raise ValueError("Invalid JSON object key")
        return value, stop

    def _number_end(self, position: int) -> int:
        match = re.match(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", self.text[position:])
        if match is None:
            raise ValueError("Invalid JSON number")
        return position + len(match.group(0))

    def _skip(self, position: int) -> int:
        position = self._space(position)
        if position >= self.length:
            raise ValueError("Truncated JSON value")
        character = self.text[position]
        if character == '"':
            return self._string_end(position)
        if character == "{":
            position = self._space(position + 1)
            if position < self.length and self.text[position] == "}":
                return position + 1
            while True:
                _key, position = self._key(position)
                position = self._space(position)
                if position >= self.length or self.text[position] != ":":
                    raise ValueError("Invalid JSON object separator")
                position = self._skip(position + 1)
                position = self._space(position)
                if position < self.length and self.text[position] == "}":
                    return position + 1
                if position >= self.length or self.text[position] != ",":
                    raise ValueError("Invalid JSON object delimiter")
                position = self._space(position + 1)
        if character == "[":
            position = self._space(position + 1)
            if position < self.length and self.text[position] == "]":
                return position + 1
            while True:
                position = self._skip(position)
                position = self._space(position)
                if position < self.length and self.text[position] == "]":
                    return position + 1
                if position >= self.length or self.text[position] != ",":
                    raise ValueError("Invalid JSON array delimiter")
                position = self._space(position + 1)
        for literal in ("true", "false", "null"):
            if self.text.startswith(literal, position):
                return position + len(literal)
        return self._number_end(position)

    def _scalar(self, position: int) -> tuple[Any, int]:
        position = self._space(position)
        if self.text[position] == '"':
            stop = self._string_end(position)
            return json.loads(self.text[position:stop]), stop
        for literal, value in (("true", True), ("false", False), ("null", None)):
            if self.text.startswith(literal, position):
                return value, position + len(literal)
        stop = self._number_end(position)
        token = self.text[position:stop]
        value = float(token) if any(item in token for item in ".eE") else int(token)
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Non-finite selected JSON number")
        return value, stop

    def _visit(self, position: int, path: tuple[str, ...]) -> int:
        position = self._space(position)
        start = position
        if path in self.targets:
            value, position = self._scalar(position)
            self.values[path] = value
            self.spans[path] = (start, position)
            return position
        if path not in self.prefixes:
            return self._skip(position)
        if position >= self.length:
            raise ValueError("Truncated selected JSON value")
        character = self.text[position]
        if character == "{":
            position = self._space(position + 1)
            if position < self.length and self.text[position] == "}":
                self.spans[path] = (start, position + 1)
                return position + 1
            seen: set[str] = set()
            while True:
                key, position = self._key(position)
                if key in seen:
                    raise ValueError("Duplicate JSON key")
                seen.add(key)
                position = self._space(position)
                if position >= self.length or self.text[position] != ":":
                    raise ValueError("Invalid selected object separator")
                position = self._visit(position + 1, path + (key,))
                position = self._space(position)
                if position < self.length and self.text[position] == "}":
                    self.spans[path] = (start, position + 1)
                    return position + 1
                if position >= self.length or self.text[position] != ",":
                    raise ValueError("Invalid selected object delimiter")
                position = self._space(position + 1)
        if character == "[":
            position = self._space(position + 1)
            index = 0
            if position < self.length and self.text[position] == "]":
                self.spans[path] = (start, position + 1)
                return position + 1
            while True:
                position = self._visit(position, path + (str(index),))
                index += 1
                position = self._space(position)
                if position < self.length and self.text[position] == "]":
                    self.spans[path] = (start, position + 1)
                    return position + 1
                if position >= self.length or self.text[position] != ",":
                    raise ValueError("Invalid selected array delimiter")
                position = self._space(position + 1)
        raise ValueError("Selected JSON path is not a container")

    def parse(self) -> dict[tuple[str, ...], Any]:
        stop = self._space(self._visit(0, ()))
        if stop != self.length:
            raise ValueError("Trailing JSON content")
        if set(self.values) != set(self.targets):
            missing = sorted(set(self.targets) - set(self.values))
            raise KeyError(f"Missing selected JSON paths: {missing}")
        return self.values


def select_json_scalars(
    payload: bytes,
    targets: Sequence[tuple[str, ...]],
    *,
    capture_paths: Sequence[tuple[str, ...]] = (),
) -> tuple[dict[tuple[str, ...], Any], dict[tuple[str, ...], bytes]]:
    parser = _SelectiveJSON(payload, targets, capture_paths)
    values = parser.parse()
    encoded = parser.text.encode("utf-8")
    wanted_spans = parser.capture_paths or frozenset(
        path for path in parser.spans if path and path not in parser.targets
    )
    spans = {
        path: encoded[len(parser.text[:start].encode("utf-8")) : len(parser.text[:stop].encode("utf-8"))]
        for path, (start, stop) in parser.spans.items()
        if path in wanted_spans
    }
    return values, spans


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def require_canonical_json(path: Path) -> Any:
    value = strict_json(path)
    if path.read_bytes() != canonical_json_bytes(value):
        raise ValueError(f"Non-canonical JSON artifact: {path}")
    return value


def bytes_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def resolve_project(relative: str, *, must_exist: bool = True) -> Path:
    if type(relative) is not str:
        raise TypeError("Project path must be a string")
    pure = PurePosixPath(relative)
    if not relative or pure.is_absolute() or pure.as_posix() != relative:
        raise ValueError("Unsafe project path")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("Unsafe project path")
    current = PROJECT_ROOT
    for part in pure.parts:
        current = current / part
        if os.path.lexists(current) and current.is_symlink():
            raise ValueError(f"Symlink path rejected: {relative}")
    if must_exist and not os.path.lexists(current):
        raise FileNotFoundError(current)
    return current


def artifact(path: Path, *, logical_name: str | None = None) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError(f"Unsafe or missing artifact: {path}")
    value: dict[str, Any] = {
        "bytes": path.stat().st_size,
        "mode": file_mode(path),
        "sha256": sha256(path),
    }
    if logical_name is None:
        value["path"] = path.relative_to(PROJECT_ROOT).as_posix()
    else:
        value["logical_name"] = logical_name
    return value


def _artifact_fields(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in ("path", "bytes", "mode", "sha256")}


def require_record(record: Mapping[str, Any]) -> Path:
    if not {"path", "bytes", "mode", "sha256"}.issubset(record):
        raise ValueError("Artifact record schema drift")
    path = resolve_project(str(record["path"]))
    if artifact(path) != _artifact_fields(record):
        raise ValueError(f"Artifact identity drift: {record['path']}")
    return path


def iter_artifact_records(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, Mapping):
        if {"path", "bytes", "mode", "sha256"}.issubset(value):
            yield _artifact_fields(value)
            return
        for item in value.values():
            yield from iter_artifact_records(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_artifact_records(item)


def create_json_once(path: Path, value: Any) -> dict[str, Any]:
    if os.path.lexists(path):
        raise FileExistsError(path)
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise ValueError("Unsafe verifier output directory")
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    if os.path.lexists(temporary):
        raise FileExistsError(temporary)
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as handle:
                handle.write(canonical_json_bytes(value))
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(descriptor)
        os.chmod(temporary, 0o644)
        os.link(temporary, path)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)
    return artifact(path)


def require_safe_root(root: Path, *, private: bool) -> set[str]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"Unsafe artifact root: {root}")
    if file_mode(root) != ("0700" if private else "0755"):
        raise PermissionError(f"Root mode drift: {root}")
    entries = list(root.rglob("*"))
    if any(item.is_symlink() for item in entries):
        raise PermissionError(f"Nested symlink rejected: {root}")
    if any(not item.is_file() and not item.is_dir() for item in entries):
        raise PermissionError(f"Special entry rejected: {root}")
    if any(item.is_dir() for item in entries):
        raise ValueError(f"Nested directory rejected: {root}")
    return {item.relative_to(root).as_posix() for item in entries}


def require_file_modes(root: Path, names: Sequence[str], *, private: bool) -> None:
    expected = "0600" if private else "0644"
    for name in names:
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError(f"Unsafe artifact: {path}")
        if file_mode(path) != expected:
            raise PermissionError(f"Artifact mode drift: {path}")


def _read_exact(handle: Any, size: int) -> bytes:
    payload = handle.read(size)
    if len(payload) != size:
        raise ValueError("Truncated NPY header")
    return payload


def _read_npy_header_from(handle: Any) -> dict[str, Any]:
    if _read_exact(handle, 6) != b"\x93NUMPY":
        raise ValueError("Invalid NPY magic")
    version = tuple(_read_exact(handle, 2))
    if version == (1, 0):
        header_size = struct.unpack("<H", _read_exact(handle, 2))[0]
        prefix_bytes = 10
    elif version in {(2, 0), (3, 0)}:
        header_size = struct.unpack("<I", _read_exact(handle, 4))[0]
        prefix_bytes = 12
    else:
        raise ValueError("Unsupported NPY version")
    if not 0 < header_size <= 65536:
        raise ValueError("Unsafe NPY header size")
    header = ast.literal_eval(_read_exact(handle, header_size).decode("latin1").strip())
    if set(header) != {"descr", "fortran_order", "shape"}:
        raise ValueError("NPY header schema drift")
    if not isinstance(header["shape"], tuple) or type(header["fortran_order"]) is not bool:
        raise ValueError("NPY header type drift")
    return {
        "version": list(version),
        "descr": header["descr"],
        "fortran_order": header["fortran_order"],
        "shape": list(header["shape"]),
        "data_offset": prefix_bytes + header_size,
    }


def read_npy_header(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("Unsafe NPY artifact")
    with path.open("rb") as handle:
        value = _read_npy_header_from(handle)
    value["file_bytes"] = path.stat().st_size
    return value


def read_npz_headers(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("Unsafe NPZ artifact")
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        if len({item.filename for item in infos}) != len(infos):
            raise ValueError("Duplicate NPZ member")
        order: list[str] = []
        headers: dict[str, dict[str, Any]] = {}
        for info in infos:
            pure = PurePosixPath(info.filename)
            if (
                info.is_dir()
                or pure.is_absolute()
                or len(pure.parts) != 1
                or pure.suffix != ".npy"
                or any(part in {"", ".", ".."} for part in pure.parts)
            ):
                raise ValueError("Unsafe NPZ member")
            name = pure.stem
            with archive.open(info, "r") as handle:
                header = _read_npy_header_from(handle)
            if info.compress_type != zipfile.ZIP_STORED or info.flag_bits & 1:
                raise ValueError("Compressed or encrypted NPZ member")
            header["compressed_bytes"] = info.compress_size
            header["uncompressed_bytes"] = info.file_size
            order.append(name)
            headers[name] = header
    return {"member_order": order, "members": headers, "file_bytes": path.stat().st_size}


def _header_contract(header: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "shape": list(header["shape"]),
        "dtype": header["descr"],
        "fortran_order": header["fortran_order"],
    }


def _normalize_numbers(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_numbers(item) for item in value]
    if type(value) in (int, float):
        return float(value)
    return value


def method_sha256(config: Mapping[str, Any]) -> str:
    value = config.get("method")
    if not isinstance(value, Mapping):
        raise ValueError("Missing EXP-071 method")
    return bytes_sha256(canonical_json_bytes(value))


def _config_kind(config: Mapping[str, Any]) -> str:
    schema = config.get("schema_version")
    if schema in {
        "exp-071-representation-drift-preflight-config-v1",
        "exp-071-representation-drift-preflight-config-v2",
    }:
        return "static"
    if schema == "exp-071-representation-drift-formal-config-v1":
        return "formal"
    raise ValueError("Unrecognized EXP-071 config")


def _static_attempt(config: Mapping[str, Any]) -> int:
    schema = config.get("schema_version")
    if schema == "exp-071-representation-drift-preflight-config-v1":
        return 1
    if schema == "exp-071-representation-drift-preflight-config-v2":
        return 2
    raise ValueError("Not an EXP-071 static config")


def _contains_tbd(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_tbd(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_tbd(item) for item in value)
    return value == "TBD"


def _expected_top_keys(kind: str, *, static_attempt: int | None = None) -> set[str]:
    common = {
        "schema_version",
        "experiment_id",
        "run_id",
        "attempt_id",
        "rq_id",
        "tier",
        "registered_at",
        "stage",
        "method_protocol",
        "implementation",
        "source",
        "environment",
        "method",
        "resources",
        "authorization",
        "access",
        "outputs",
        "claim_boundary",
    }
    if kind == "formal":
        return common | {"preflight"}
    if static_attempt == 2:
        return common | {"incident"}
    return common


def validate_method(config: Mapping[str, Any]) -> None:
    method = config.get("method")
    if not isinstance(method, Mapping) or set(method) != {
        "rows",
        "condition_order",
        "representation",
        "cosine_distance",
        "relative_l2_distance",
        "linear_cka",
        "aggregation",
        "sanity",
        "spearman",
        "decision",
        "verification_comparison",
        "private_bundle",
        "lifecycle",
    }:
        raise ValueError("EXP-071 method schema drift")
    if method_sha256(config) != METHOD_SHA256:
        raise ValueError("EXP-071 method digest drift")
    if tuple(method["condition_order"]) != CONDITION_ORDER:
        raise ValueError("EXP-071 condition order drift")
    if method["rows"] != {
        "total": ROWS,
        "folds": 5,
        "heldout_per_fold": HELDOUT_ROWS,
        "heldout_only": True,
        "fold_order": list(FOLDS),
        "within_fold_order": "ascending_ordinal",
    }:
        raise ValueError("EXP-071 row contract drift")
    bundle = method["private_bundle"]
    if (
        bundle.get("format") != "uncompressed_npz"
        or tuple(bundle.get("member_order", ())) != NPZ_MEMBER_ORDER
        or bundle.get("members") != NPZ_MEMBERS
    ):
        raise ValueError("EXP-071 private bundle contract drift")
    if method["lifecycle"] != {
        "runner_stages": ["static", "initialize", "analyze"],
        "verifier_stages": ["static-verify", "static-complete", "formal-verify", "formal-complete"],
        "fold_seals": False,
        "partial_resume": False,
    }:
        raise ValueError("EXP-071 lifecycle drift")


def validate_resources(config: Mapping[str, Any]) -> None:
    if config.get("resources") != {
        "maximum_concurrent_workers": 1,
        "runner_wall_seconds": 7200,
        "verifier_wall_seconds": 7200,
        "peak_rss_bytes": 4294967296,
        "private_output_budget_bytes": 67108864,
        "minimum_free_disk_bytes": 1073741824,
        "threads_per_library": 1,
        "api_cost_usd": 0,
    }:
        raise ValueError("EXP-071 resource contract drift")


def validate_outputs(
    config: Mapping[str, Any], *, kind: str, static_attempt: int | None = None
) -> None:
    value = config.get("outputs")
    if not isinstance(value, Mapping):
        raise ValueError("Missing EXP-071 output contract")
    common = {
        "formal_public_root": (
            "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
            "exp-071-representation-drift/formal-attempt-1"
        ),
        "formal_private_root": (
            "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
            "exp-071-representation-drift/formal-attempt-1"
        ),
    }
    if any(value.get(key) != item for key, item in common.items()):
        raise ValueError("EXP-071 formal root drift")
    if kind == "static":
        attempt = 1 if static_attempt is None else static_attempt
        if attempt not in {1, 2}:
            raise ValueError("EXP-071 static output attempt drift")
        expected = {
            **common,
            "preflight_public_root": (
                "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
                f"exp-071-representation-drift/preflight-attempt-{attempt}"
            ),
            "preflight_private_root": (
                "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
                f"exp-071-representation-drift/preflight-attempt-{attempt}"
            ),
            "public_success_allowlist": [
                "static.json",
                "static-verification.json",
                "no-result-complete.json",
            ],
            "public_runner_failure_allowlist": ["failure.json"],
            "private_success_allowlist": ["input-contract-manifest.json"],
            "formal_roots_must_be_absent": True,
            "public_directory_mode": "0755",
            "public_file_mode": "0644",
            "private_directory_mode": "0700",
            "private_file_mode": "0600",
        }
    else:
        expected = {
            **common,
            "public_claim_allowlist": ["run-claim.json"],
            "public_analyzed_allowlist": ["run-claim.json", "drift.json"],
            "public_verified_allowlist": ["run-claim.json", "drift.json", "verification.json"],
            "public_success_allowlist": [
                "run-claim.json",
                "drift.json",
                "verification.json",
                "drift-complete.json",
            ],
            "public_runner_failure_allowlist": ["run-claim.json", "failure.json"],
            "private_initialized_allowlist": ["input-manifest.json"],
            "private_success_allowlist": [
                "input-manifest.json",
                "geometry.npz",
                "geometry-manifest.json",
            ],
            "formal_roots_must_be_fresh": True,
            "public_directory_mode": "0755",
            "public_file_mode": "0644",
            "private_directory_mode": "0700",
            "private_file_mode": "0600",
        }
    if dict(value) != expected:
        raise ValueError("EXP-071 output contract drift")


def validate_authorization(config: Mapping[str, Any], *, kind: str) -> None:
    value = config.get("authorization")
    if not isinstance(value, Mapping):
        raise PermissionError("Missing EXP-071 authorization")
    base_keys = {
        "static_runner_authorized",
        "static_verifier_authorized",
        "formal_initialize_authorized",
        "formal_analyze_authorized",
        "formal_verification_authorized",
        "formal_completion_authorized",
        "representation_value_access_authorized",
        "probe_metric_value_access_authorized",
        "model_loading_authorized",
        "forward_authorized",
    }
    if kind == "formal":
        base_keys.add("activation_condition")
    if set(value) != base_keys:
        raise PermissionError("EXP-071 authorization schema drift")
    if value.get("model_loading_authorized") is not False or value.get("forward_authorized") is not False:
        raise PermissionError("EXP-071 model or forward authorization drift")
    if kind == "static":
        if value.get("static_runner_authorized") is not True or value.get("static_verifier_authorized") is not True:
            raise PermissionError("EXP-071 static authorization missing")
        if any(value.get(key) is not False for key in base_keys - {
            "static_runner_authorized", "static_verifier_authorized", "model_loading_authorized", "forward_authorized"
        }):
            raise PermissionError("EXP-071 static config over-authorizes formal work")
    else:
        for key in (
            "formal_initialize_authorized",
            "formal_analyze_authorized",
            "formal_verification_authorized",
            "formal_completion_authorized",
            "representation_value_access_authorized",
            "probe_metric_value_access_authorized",
        ):
            if value.get(key) is not True:
                raise PermissionError(f"EXP-071 formal authorization missing: {key}")
        if value.get("static_runner_authorized") is not False or value.get("static_verifier_authorized") is not False:
            raise PermissionError("EXP-071 formal config authorizes static execution")
        if value.get("activation_condition") != "Passed_static_completion_exact_identities_bound":
            raise PermissionError("EXP-071 formal activation condition drift")


def validate_access(config: Mapping[str, Any], *, kind: str) -> None:
    value = config.get("access")
    if not isinstance(value, Mapping):
        raise PermissionError("Missing EXP-071 access contract")
    if kind == "static":
        if set(value) != {"static_may_read", "static_must_not_read", "formal_root_creation"}:
            raise PermissionError("EXP-071 static access schema drift")
        if value.get("formal_root_creation") is not False:
            raise PermissionError("EXP-071 static formal-root creation enabled")
        required_forbidden = {
            "representation_values", "probe_metric_values", "labels", "component_codes",
            "component_ids", "sample_ids", "private_probe_artifacts", "probabilities",
            "predictions", "train_text", "validation", "test", "test_gate",
        }
        if set(value.get("static_must_not_read", ())) != required_forbidden:
            raise PermissionError("EXP-071 static forbidden access drift")
    else:
        if set(value) != {
            "formal_may_read_after_activation",
            "formal_must_not_read",
            "formal_model_load",
            "formal_forward",
            "formal_source_mutation",
            "currently_authorized",
        }:
            raise PermissionError("EXP-071 formal access schema drift")
        if any(value.get(key) is not False for key in (
            "formal_model_load", "formal_forward", "formal_source_mutation"
        )):
            raise PermissionError("EXP-071 forbidden formal access enabled")
        if value.get("currently_authorized") is not True:
            raise PermissionError("EXP-071 formal access is not activated")


def validate_environment_config(config: Mapping[str, Any]) -> None:
    if config.get("environment") != ENVIRONMENT:
        raise EnvironmentError("EXP-071 environment config drift")


def observed_environment() -> dict[str, Any]:
    return {
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "packages": {"numpy": importlib.metadata.version("numpy")},
        "thread_environment": {
            key: os.environ.get(key) for key in ENVIRONMENT["thread_environment"]
        },
    }


def require_environment(config: Mapping[str, Any]) -> dict[str, Any]:
    validate_environment_config(config)
    observed = observed_environment()
    expected = dict(ENVIRONMENT)
    expected["python_executable"] = str(Path(ENVIRONMENT["python_executable"]).resolve())
    if observed != expected:
        raise EnvironmentError("EXP-071 verifier environment drift")
    if os.environ.get("PYTHONNOUSERSITE") != "1":
        raise EnvironmentError("PYTHONNOUSERSITE must equal 1")
    return observed


def validate_historical_attempt1_config(config_path: Path = HISTORICAL_STATIC_CONFIG) -> dict[str, Any]:
    resolved = config_path.resolve()
    if artifact(resolved) != ATTEMPT1_CONFIG_RECORD:
        raise ValueError("EXP-071 historical attempt-1 config identity drift")
    value = strict_json(resolved)
    if not isinstance(value, dict):
        raise ValueError("EXP-071 historical attempt-1 config must be an object")
    validate_config(value, kind="static")
    if _static_attempt(value) != 1:
        raise ValueError("EXP-071 historical attempt identity drift")
    return value


def validate_incident_001(config: Mapping[str, Any]) -> None:
    incident = config.get("incident")
    if incident != INCIDENT_001 or not isinstance(incident, Mapping) or set(incident) != {
        "id", "failed_config", "failure_artifact", "root_cause", "recovery_scope"
    }:
        raise ValueError("EXP-071 Incident 001 binding drift")
    require_record(incident["failed_config"])
    failure_path = require_record(incident["failure_artifact"])
    validate_historical_attempt1_config()
    selected, _ = select_json_scalars(
        failure_path.read_bytes(),
        [
            ("schema_version",),
            ("experiment_id",),
            ("run_id",),
            ("attempt_id",),
            ("stage",),
            ("status",),
            ("error_type",),
            ("model_loading_authorized",),
            ("forward_authorized",),
            ("source_mutation_authorized",),
        ],
    )
    expected = {
        ("schema_version",): "exp-071-drift-failure-v1",
        ("experiment_id",): EXPERIMENT_ID,
        ("run_id",): "exp-071-representation-drift-preflight",
        ("attempt_id",): "preflight-attempt-1",
        ("stage",): "static",
        ("status",): "Failed",
        ("error_type",): "ValueError",
        ("model_loading_authorized",): False,
        ("forward_authorized",): False,
        ("source_mutation_authorized",): False,
    }
    if selected != expected:
        raise ValueError("EXP-071 historical failure payload drift")


def validate_config(config: Mapping[str, Any], *, kind: str) -> None:
    attempt = _static_attempt(config) if kind == "static" else None
    if _config_kind(config) != kind or set(config) != _expected_top_keys(
        kind, static_attempt=attempt
    ):
        raise ValueError("EXP-071 config top-level schema drift")
    expected = (
        (
            f"exp-071-representation-drift-preflight-config-v{attempt}",
            "exp-071-representation-drift-preflight",
            f"preflight-attempt-{attempt}",
            "no-result-preflight",
        )
        if kind == "static"
        else (
            "exp-071-representation-drift-formal-config-v1",
            "exp-071-representation-drift-formal",
            "formal-attempt-1",
            "formal",
        )
    )
    if (
        config.get("schema_version") != expected[0]
        or config.get("experiment_id") != EXPERIMENT_ID
        or config.get("run_id") != expected[1]
        or config.get("attempt_id") != expected[2]
        or config.get("stage") != expected[3]
        or config.get("rq_id") != "RQ-S4.2"
        or config.get("tier") != "Major representation experiment"
        or config.get("registered_at") != "2026-08-29"
        or not isinstance(config.get("claim_boundary"), str)
        or not config["claim_boundary"]
    ):
        raise ValueError("EXP-071 config identity drift")
    if _contains_tbd(config):
        raise ValueError("EXP-071 config contains an unfrozen TBD")
    if config.get("method_protocol") != METHOD_PROTOCOL_RECORD:
        raise ValueError("EXP-071 method protocol identity drift")
    source_payload = canonical_json_bytes(config.get("source"))
    if (
        len(source_payload) != EXPECTED_SOURCE_CANONICAL_BYTES
        or bytes_sha256(source_payload) != EXPECTED_SOURCE_SHA256
    ):
        raise ValueError("EXP-071 registered source contract drift")
    if kind == "static" and config.get("claim_boundary") != STATIC_CLAIM_BOUNDARY:
        raise ValueError("EXP-071 static claim boundary drift")
    if kind == "formal" and config.get("claim_boundary") != FORMAL_CLAIM_BOUNDARY:
        raise ValueError("EXP-071 formal claim boundary drift")
    if kind == "static" and attempt == 2:
        validate_incident_001(config)
    validate_method(config)
    validate_resources(config)
    validate_outputs(config, kind=kind, static_attempt=attempt)
    validate_authorization(config, kind=kind)
    validate_access(config, kind=kind)
    validate_environment_config(config)
    validate_matrix_plan(config)


def load_config(path: Path, *, kind: str) -> dict[str, Any]:
    value = strict_json(path)
    if not isinstance(value, dict):
        raise ValueError("EXP-071 config must be an object")
    validate_config(value, kind=kind)
    return value


def validate_implementation_paths(value: Any) -> None:
    if not isinstance(value, Mapping) or set(value) != {"runner", "verifier", "tests"}:
        raise ValueError("EXP-071 implementation schema drift")
    for name, expected_path in IMPLEMENTATION_PATHS.items():
        record = value[name]
        if not isinstance(record, Mapping) or record.get("path") != expected_path:
            raise ValueError(f"EXP-071 {name} implementation path drift")


def require_implementation(config: Mapping[str, Any]) -> dict[str, Path]:
    value = config.get("implementation")
    validate_implementation_paths(value)
    result: dict[str, Path] = {}
    for name, record in value.items():
        if not isinstance(record, Mapping) or set(record) != {"path", "bytes", "mode", "sha256", "status"}:
            raise ValueError("EXP-071 implementation record schema drift")
        if record.get("status") != "Frozen" or record.get("bytes") == 0 or record.get("sha256") == "TBD":
            raise ValueError("EXP-071 implementation is not frozen")
        result[name] = require_record(record)
    if result["verifier"].resolve() != Path(__file__).resolve():
        raise ValueError("EXP-071 verifier identity points elsewhere")
    return result


def _imports(path: Path) -> tuple[set[str], set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    relative: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                relative.add(node.module or "")
            elif node.module:
                modules.add(node.module)
    return modules, relative


def require_import_boundaries(paths: Mapping[str, Path], *, static: bool) -> None:
    verifier_modules, verifier_relative = _imports(paths["verifier"])
    top = {name.split(".", 1)[0] for name in verifier_modules}
    if top & FORBIDDEN_MODEL_MODULES or verifier_relative:
        raise RuntimeError("EXP-071 verifier import boundary drift")
    if any("run_exp071" in name for name in verifier_modules):
        raise RuntimeError("EXP-071 verifier imports the producer")
    for name in ("runner", "tests"):
        modules, _relative = _imports(paths[name])
        if {item.split(".", 1)[0] for item in modules} & FORBIDDEN_MODEL_MODULES:
            raise RuntimeError(f"EXP-071 {name} imports a model library")
    runner_tree = ast.parse(paths["runner"].read_text(encoding="utf-8"), filename=str(paths["runner"]))
    runner_attributes = {
        node.attr for node in ast.walk(runner_tree) if isinstance(node, ast.Attribute)
    }
    if not {"flock", "LOCK_EX", "LOCK_NB", "LOCK_UN"}.issubset(runner_attributes):
        raise RuntimeError("EXP-071 runner lacks the persistent global flock protocol")
    for node in ast.walk(runner_tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        function = node.func
        if isinstance(function, ast.Attribute) and function.attr == "lexists":
            if isinstance(node.args[0], ast.Name) and node.args[0].id == "HEAVY_LOCK":
                raise RuntimeError("EXP-071 runner uses existence-based global lock gating")
    if static and "numpy" in sys.modules:
        raise RuntimeError("Static verifier imported NumPy")


def _artifact_records(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    roots: dict[str, Any] = {
        "method_protocol": config["method_protocol"],
        "implementation": config["implementation"],
        "source": config["source"],
    }
    records = list(iter_artifact_records(roots))
    by_path: dict[str, dict[str, Any]] = {}
    for record in records:
        path = str(record["path"])
        if path in by_path and by_path[path] != record:
            raise ValueError("Conflicting EXP-071 source record")
        by_path[path] = record
    return [by_path[path] for path in sorted(by_path)]


def source_identity_snapshot(config: Mapping[str, Any]) -> dict[str, Any]:
    records = _artifact_records(config)
    observed: list[dict[str, Any]] = []
    for record in records:
        path = require_record(record)
        observed.append(artifact(path))
    payload = canonical_json_bytes(observed)
    return {
        "artifact_count": len(observed),
        "artifacts": observed,
        "sha256": bytes_sha256(payload),
    }


def require_parent_statuses(config: Mapping[str, Any], *, read_probe_values: bool) -> None:
    source = config["source"]
    if set(source) != {
        "phase_b_decision",
        "exp069_terminal",
        "exp070_extraction_terminal",
        "exp070_probe_terminal",
        "public_fold_contract",
        "matrix_root",
        "matrices",
    }:
        raise ValueError("EXP-071 source schema drift")
    for record in _artifact_records(config):
        require_record(record)
    exp069 = source["exp069_terminal"]
    exp069_verification_path = require_record(exp069["verification"])
    exp069_completion_path = require_record(exp069["completion"])
    verification, _ = select_json_scalars(
        exp069_verification_path.read_bytes(),
        [("status",), ("passed_count",), ("failed_count",)],
    )
    completion, _ = select_json_scalars(
        exp069_completion_path.read_bytes(), [("status",), ("exp069_complete",)]
    )
    if (
        verification[("status",)] != exp069["verification"]["required_status"]
        or verification[("passed_count",)] != exp069["verification"]["required_passed_count"]
        or verification[("failed_count",)] != exp069["verification"]["required_failed_count"]
        or completion[("status",)] != exp069["completion"]["required_status"]
        or completion[("exp069_complete",)] is not exp069["completion"]["required_exp069_complete"]
        or exp069.get("smoke_representation_values_authorized") is not False
    ):
        raise ValueError("EXP-069 terminal binding drift")
    extraction = source["exp070_extraction_terminal"]
    extraction_verification_path = require_record(extraction["verification"])
    extraction_completion_path = require_record(extraction["completion"])
    extraction_verification, _ = select_json_scalars(
        extraction_verification_path.read_bytes(), [("status",)]
    )
    extraction_completion, _ = select_json_scalars(
        extraction_completion_path.read_bytes(), [("status",), ("formal_extraction_complete",)]
    )
    if (
        extraction_verification[("status",)] != extraction["verification"]["required_status"]
        or extraction_completion[("status",)] != extraction["completion"]["required_status"]
        or extraction_completion[("formal_extraction_complete",)]
        is not extraction["completion"]["required_formal_extraction_complete"]
    ):
        raise ValueError("EXP-070 extraction terminal binding drift")
    probe = source["exp070_probe_terminal"]
    probe_verification_path = require_record(probe["verification"])
    probe_completion_path = require_record(probe["completion"])
    probe_verification, _ = select_json_scalars(
        probe_verification_path.read_bytes(),
        [("status",), ("passed_count",), ("failed_count",), ("results_sha256",)],
    )
    probe_completion, _ = select_json_scalars(
        probe_completion_path.read_bytes(),
        [("status",), ("exp070_complete",), ("exp071_authorized",)],
    )
    if (
        probe_verification[("status",)] != probe["verification"]["required_status"]
        or probe_verification[("passed_count",)] != probe["verification"]["required_passed_count"]
        or probe_verification[("failed_count",)] != probe["verification"]["required_failed_count"]
        or probe_verification[("results_sha256",)] != probe["verification"]["required_results_sha256"]
        or probe_completion[("status",)] != probe["completion"]["required_status"]
        or probe_completion[("exp070_complete",)] is not probe["completion"]["required_exp070_complete"]
        or probe_completion[("exp071_authorized",)] is not probe["completion"]["recorded_exp071_authorized"]
        or probe.get("private_probe_artifact_access") is not False
    ):
        raise ValueError("EXP-070 probe terminal binding drift")
    fold = source["public_fold_contract"]
    fold_verification_path = require_record(fold["verification"])
    fold_verification, _ = select_json_scalars(
        fold_verification_path.read_bytes(), [("status",)]
    )
    if fold_verification[("status",)] != fold["verification"]["required_status"]:
        raise ValueError("EXP-058 fold verification binding drift")
    if fold.get("formal_parse_authorized") is not False:
        raise PermissionError("EXP-071 public fold manifest parsing enabled")
    if not read_probe_values:
        return
    _load_probe_deltas(config)


def validate_matrix_plan(config: Mapping[str, Any]) -> None:
    source = config.get("source")
    if not isinstance(source, Mapping) or source.get("matrix_root") != (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
        "exp-070-layerwise-probes/formal-extraction-attempt-1/extraction"
    ):
        raise ValueError("EXP-071 matrix root drift")
    matrices = source.get("matrices")
    if not isinstance(matrices, list) or len(matrices) != 16:
        raise ValueError("EXP-071 requires exactly sixteen matrices")
    expected: list[dict[str, Any]] = [
        {
            "worker_id": "base",
            "kind": "frozen",
            "seed": None,
            "fold": None,
            "shape": [ROWS, len(ALL_POINTS), HIDDEN_SIZE],
            "points": list(ALL_POINTS),
            "bytes": 309657728,
        }
    ]
    for seed in (42, 43, 44):
        points = ALL_POINTS if seed == 42 else CONFIRMATION_POINTS
        size = 309657728 if seed == 42 else 103219328
        for fold in FOLDS:
            expected.append(
                {
                    "worker_id": f"m3-s{seed}-f{fold}",
                    "kind": "m3",
                    "seed": seed,
                    "fold": fold,
                    "shape": [ROWS, len(points), HIDDEN_SIZE],
                    "points": list(points),
                    "bytes": size,
                }
            )
    for observed, planned in zip(matrices, expected, strict=True):
        if not isinstance(observed, Mapping) or set(observed) != {
            "worker_id", "kind", "seed", "fold", "shape", "points", "artifact"
        }:
            raise ValueError("EXP-071 matrix record schema drift")
        for key in ("worker_id", "kind", "seed", "fold", "shape", "points"):
            if observed.get(key) != planned[key]:
                raise ValueError(f"EXP-071 matrix plan drift: {planned['worker_id']} {key}")
        artifact_record = observed.get("artifact")
        expected_path = (
            f"{source['matrix_root']}/{planned['worker_id']}/representations.npy"
        )
        if (
            not isinstance(artifact_record, Mapping)
            or artifact_record.get("path") != expected_path
            or artifact_record.get("bytes") != planned["bytes"]
            or artifact_record.get("mode") != "0600"
            or not re.fullmatch(r"[0-9a-f]{64}", str(artifact_record.get("sha256", "")))
        ):
            raise ValueError(f"EXP-071 matrix artifact plan drift: {planned['worker_id']}")


def matrix_headers(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    validate_matrix_plan(config)
    matrices = config["source"]["matrices"]
    expected_workers = ["base"] + [
        f"m3-s{seed}-f{fold}" for seed in (42, 43, 44) for fold in FOLDS
    ]
    if [item.get("worker_id") for item in matrices] != expected_workers:
        raise ValueError("EXP-071 matrix order drift")
    observed: list[dict[str, Any]] = []
    for item in matrices:
        path = require_record(item["artifact"])
        header = read_npy_header(path)
        expected_shape = list(item["shape"])
        if _header_contract(header) != {
            "shape": expected_shape,
            "dtype": "<f4",
            "fortran_order": False,
        }:
            raise ValueError(f"EXP-071 matrix header drift: {item['worker_id']}")
        expected_size = header["data_offset"] + math.prod(expected_shape) * 4
        if path.stat().st_size != expected_size:
            raise ValueError(f"EXP-071 matrix payload size drift: {item['worker_id']}")
        observed.append(
            {
                "worker_id": item["worker_id"],
                "shape": expected_shape,
                "descr": "<f4",
                "fortran_order": False,
                "data_offset": header["data_offset"],
                "file_bytes": header["file_bytes"],
                "points": item["points"],
            }
        )
    return observed


def row_contract_headers(config: Mapping[str, Any]) -> dict[str, Any]:
    record = config["source"]["exp070_extraction_terminal"]["row_contract"]
    path = require_record(record)
    headers = read_npz_headers(path)
    order = headers["member_order"]
    members = headers["members"]
    if order != ["ordinal", "fold_id", "component_code"]:
        raise ValueError("EXP-071 row-contract member order drift")
    observed = {key: _header_contract(members[key]) for key in order}
    if observed != ROW_CONTRACT_HEADERS:
        raise ValueError("EXP-071 row-contract header drift")
    if record.get("allowed_value_members") != ["ordinal", "fold_id"]:
        raise PermissionError("EXP-071 row-contract value allowlist drift")
    if record.get("forbidden_value_members") != ["component_code"]:
        raise PermissionError("EXP-071 row-contract forbidden value drift")
    return headers


def _directory_bytes(root: Path) -> int:
    return sum(item.stat().st_size for item in root.rglob("*") if item.is_file())


def _root(config: Mapping[str, Any], *, private: bool, formal: bool) -> Path:
    prefix = "formal" if formal else "preflight"
    return resolve_project(
        config["outputs"][f"{prefix}_{'private' if private else 'public'}_root"],
        must_exist=False,
    )


def public_privacy_ok(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key) in PUBLIC_FORBIDDEN_KEYS or not public_privacy_ok(item):
                return False
    elif isinstance(value, list):
        return all(public_privacy_ok(item) for item in value)
    return True


def validate_public_payload(value: Any) -> None:
    if not isinstance(value, Mapping) or not public_privacy_ok(value):
        raise ValueError("EXP-071 public exact-schema privacy drift")


def _synthetic_test_summary(test_path: Path) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    command = [sys.executable, str(test_path)]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=600,
        check=False,
    )
    combined = completed.stdout + "\n" + completed.stderr
    matches = re.findall(r"Ran\s+(\d+)\s+tests?", combined)
    tests_run = int(matches[-1]) if matches else None
    if completed.returncode != 0 or tests_run is None or tests_run < 1:
        raise RuntimeError("EXP-071 synthetic suite failed")
    return {
        "status": "Passed",
        "tests_run": tests_run,
        "test_artifact": artifact(test_path),
        "command_sha256": bytes_sha256(canonical_json_bytes(command)),
    }


def run_synthetic_tests(config: Mapping[str, Any], test_path: Path) -> dict[str, Any]:
    summary = _synthetic_test_summary(test_path)
    if summary["test_artifact"] != _artifact_fields(config["implementation"]["tests"]):
        raise ValueError("EXP-071 synthetic test identity drift")
    return summary


def _validate_resource_payload(value: Any, config: Mapping[str, Any], *, require_disk: bool) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("EXP-071 resource payload missing")
    allowed = {
        "elapsed_seconds",
        "peak_rss_bytes",
        "private_output_bytes",
        "free_disk_bytes",
        "source_artifact_count",
        "api_cost_usd",
    }
    if not set(value).issubset(allowed) or not {"elapsed_seconds", "peak_rss_bytes", "api_cost_usd"}.issubset(value):
        raise ValueError("EXP-071 resource payload schema drift")
    if not 0.0 <= float(value["elapsed_seconds"]) <= config["resources"]["runner_wall_seconds"]:
        raise TimeoutError("EXP-071 runner wall-time ceiling exceeded")
    if not 0 < int(value["peak_rss_bytes"]) <= config["resources"]["peak_rss_bytes"]:
        raise MemoryError("EXP-071 runner peak-RSS ceiling exceeded")
    if value.get("api_cost_usd") != 0:
        raise ValueError("EXP-071 API cost drift")
    if "private_output_bytes" in value and not 0 <= int(value["private_output_bytes"]) <= config["resources"]["private_output_budget_bytes"]:
        raise OSError("EXP-071 private output budget exceeded")
    if "source_artifact_count" in value and int(value["source_artifact_count"]) < 1:
        raise ValueError("EXP-071 source artifact count drift")
    if require_disk and int(value.get("free_disk_bytes", -1)) < config["resources"]["minimum_free_disk_bytes"]:
        raise OSError("EXP-071 free-disk gate failed")


def _validate_static_runner_payload(
    config_path: Path,
    config: Mapping[str, Any],
    public: Path,
    private: Path,
    sources: Mapping[str, Any],
    headers: Sequence[Mapping[str, Any]],
    row_headers: Mapping[str, Any],
    environment: Mapping[str, Any],
    synthetic: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    run_path = public / "static.json"
    input_path = private / "input-contract-manifest.json"
    run = require_canonical_json(run_path)
    input_manifest = require_canonical_json(input_path)
    expected_run_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "stage", "status",
        "config", "input_manifest", "method_sha256", "source_snapshot_sha256", "counts",
        "synthetic_tests", "environment", "resources", "access",
        "formal_execution_authorized", "exp071_complete", "exp072_authorized", "claim_boundary",
    }
    if set(run) != expected_run_keys:
        raise ValueError("EXP-071 static runner payload schema drift")
    if (
        run.get("schema_version") != "exp-071-drift-static-run-v1"
        or run.get("experiment_id") != EXPERIMENT_ID
        or run.get("run_id") != config["run_id"]
        or run.get("attempt_id") != config["attempt_id"]
        or run.get("stage") != "static"
        or run.get("status") != "CompletedAwaitingVerification"
        or run.get("config") != artifact(config_path)
        or run.get("method_sha256") != METHOD_SHA256
        or run.get("source_snapshot_sha256") != sources["sha256"]
        or run.get("input_manifest") != artifact(input_path, logical_name="input-contract-manifest.json")
        or run.get("counts") != {
            "source_artifacts": sources["artifact_count"],
            "representation_matrices": 16,
            "conditions": 15,
            "folds": 5,
            "scientific_comparisons": 0,
        }
        or run.get("synthetic_tests") != synthetic
        or run.get("environment") != environment
        or run.get("formal_execution_authorized") is not False
        or run.get("exp071_complete") is not False
        or run.get("exp072_authorized") is not False
        or run.get("claim_boundary") != config["claim_boundary"]
    ):
        raise ValueError("EXP-071 static runner binding drift")
    _validate_resource_payload(run.get("resources"), config, require_disk=False)
    if run["resources"].get("source_artifact_count") != sources["artifact_count"]:
        raise ValueError("EXP-071 static resource source count drift")
    if run.get("access") != STATIC_ACCESS:
        raise PermissionError("EXP-071 static runner access drift")
    expected_input_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "status", "config",
        "method_sha256", "source_snapshot_sha256", "source_artifact_count", "matrix_headers",
        "row_contract_headers", "environment", "formal_roots_absent", "synthetic_tests", "access",
    }
    if set(input_manifest) != expected_input_keys:
        raise ValueError("EXP-071 static private contract schema drift")
    if (
        input_manifest.get("schema_version") != "exp-071-drift-static-input-v1"
        or input_manifest.get("experiment_id") != EXPERIMENT_ID
        or input_manifest.get("run_id") != config["run_id"]
        or input_manifest.get("attempt_id") != config["attempt_id"]
        or input_manifest.get("status") != "Sealed"
        or input_manifest.get("config") != artifact(config_path)
        or input_manifest.get("method_sha256") != METHOD_SHA256
        or input_manifest.get("source_snapshot_sha256") != sources["sha256"]
        or input_manifest.get("source_artifact_count") != sources["artifact_count"]
        or input_manifest.get("matrix_headers") != list(headers)
        or input_manifest.get("row_contract_headers") != row_headers
        or input_manifest.get("environment") != environment
        or input_manifest.get("formal_roots_absent") is not True
        or input_manifest.get("synthetic_tests") != synthetic
        or input_manifest.get("access") != STATIC_ACCESS
    ):
        raise ValueError("EXP-071 static private contract binding drift")
    validate_public_payload(run)
    return run, input_manifest, run_path, input_path


def _static_verification_payload(
    config_path: Path,
    config: Mapping[str, Any],
    run_path: Path,
    input_path: Path,
    source_snapshot: Mapping[str, Any],
    synthetic: Mapping[str, Any],
) -> dict[str, Any]:
    value = {
        "schema_version": "exp-071-drift-static-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "stage": "no-result-preflight",
        "status": "Passed",
        "passed_count": len(STATIC_CHECKS),
        "failed_count": 0,
        "checks": list(STATIC_CHECKS),
        "config": artifact(config_path),
        "run": artifact(run_path),
        "input_contract": artifact(input_path, logical_name="input-contract-manifest.json"),
        "method_sha256": METHOD_SHA256,
        "source_snapshot_sha256": source_snapshot["sha256"],
        "synthetic_tests": synthetic,
        "representation_values_read": False,
        "probe_metric_values_read": False,
        "formal_root_created": False,
        "formal_execution_authorized": False,
        "exp071_complete": False,
        "exp072_authorized": False,
        "claim_boundary": config["claim_boundary"],
    }
    validate_public_payload(value)
    return value


def _static_completion_payload(
    config: Mapping[str, Any],
    run_path: Path,
    input_path: Path,
    verification_path: Path,
    source_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    value = {
        "schema_version": "exp-071-drift-no-result-complete-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "status": "Complete",
        "run": artifact(run_path),
        "verification": artifact(verification_path),
        "input_contract": artifact(input_path, logical_name="input-contract-manifest.json"),
        "method_sha256": METHOD_SHA256,
        "source_snapshot_sha256": source_snapshot["sha256"],
        "representation_values_read": False,
        "probe_metric_values_read": False,
        "formal_execution_authorized": True,
        "exp071_complete": False,
        "exp072_authorized": False,
        "claim_boundary": config["claim_boundary"],
    }
    validate_public_payload(value)
    return value


def _validate_formal_roots_absent(config: Mapping[str, Any]) -> None:
    for private in (False, True):
        path = _root(config, private=private, formal=True)
        if os.path.lexists(path):
            raise FileExistsError("EXP-071 formal roots must remain absent during static stages")


def verify_static(config_path: Path, *, complete: bool) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = load_config(config_path, kind="static")
    if _static_attempt(config) != 2:
        validate_historical_attempt1_config(config_path)
        raise RuntimeError("EXP-071 preflight attempt 1 is historical and cannot execute")
    paths = require_implementation(config)
    require_import_boundaries(paths, static=True)
    environment = require_environment(config)
    public = _root(config, private=False, formal=False)
    private = _root(config, private=True, formal=False)
    public_files = require_safe_root(public, private=False)
    private_files = require_safe_root(private, private=True)
    allowed_public = (
        {"static.json"},
        {"static.json", "static-verification.json"},
        set(config["outputs"]["public_success_allowlist"]),
    )
    if public_files not in allowed_public or private_files != set(config["outputs"]["private_success_allowlist"]):
        raise ValueError("EXP-071 static exact-prefix inventory drift")
    if "failure.json" in public_files:
        raise RuntimeError("EXP-071 static runner failure blocks verification")
    require_file_modes(public, sorted(public_files), private=False)
    require_file_modes(private, sorted(private_files), private=True)
    _validate_formal_roots_absent(config)
    before = source_identity_snapshot(config)
    require_parent_statuses(config, read_probe_values=False)
    headers = matrix_headers(config)
    row_headers = row_contract_headers(config)
    synthetic = run_synthetic_tests(config, paths["tests"])
    after = source_identity_snapshot(config)
    if after != before:
        raise ValueError("EXP-071 source changed during static verification")
    _run, _input, run_path, input_path = _validate_static_runner_payload(
        config_path, config, public, private, before, headers, row_headers, environment, synthetic
    )
    if _directory_bytes(private) > config["resources"]["private_output_budget_bytes"]:
        raise OSError("EXP-071 static private budget exceeded")
    verification_path = public / "static-verification.json"
    completion_path = public / "no-result-complete.json"
    expected_verification = _static_verification_payload(
        config_path, config, run_path, input_path, before, synthetic
    )
    if os.path.lexists(verification_path):
        if require_canonical_json(verification_path) != expected_verification:
            raise ValueError("EXP-071 static verification prefix drift")
    elif complete:
        raise RuntimeError("Static completion requires an existing Passed verification")
    else:
        if public_files != {"static.json"}:
            raise ValueError("EXP-071 static preverification prefix drift")
        create_json_once(verification_path, expected_verification)
    if complete:
        expected_completion = _static_completion_payload(
            config, run_path, input_path, verification_path, before
        )
        if os.path.lexists(completion_path):
            if require_canonical_json(completion_path) != expected_completion:
                raise ValueError("EXP-071 static completion prefix drift")
        else:
            create_json_once(completion_path, expected_completion)
        if require_safe_root(public, private=False) != set(config["outputs"]["public_success_allowlist"]):
            raise ValueError("EXP-071 static terminal inventory drift")
    elif os.path.lexists(completion_path):
        raise RuntimeError("Static verify cannot create or consume completion")
    elif require_safe_root(public, private=False) != {"static.json", "static-verification.json"}:
        raise ValueError("EXP-071 static verified inventory drift")
    return expected_verification


def _array_digest(value: Any) -> str:
    import numpy as np

    return bytes_sha256(np.ascontiguousarray(value).tobytes(order="C"))


def distance_statistics(values: Any) -> dict[str, float]:
    import numpy as np

    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError("EXP-071 invalid distance vector")
    return {
        "mean": float(np.mean(array)),
        "median": float(np.percentile(array, 50.0, method="linear")),
        "p90": float(np.percentile(array, 90.0, method="linear")),
        "p95": float(np.percentile(array, 95.0, method="linear")),
    }


def compute_geometry_pair(frozen: Any, adapted: Any) -> tuple[Any, Any, float, float]:
    """Return rowwise cosine, rowwise relative L2, fold CKA and max abs diff."""
    import numpy as np

    x = np.ascontiguousarray(frozen, dtype=np.float64)
    z = np.ascontiguousarray(adapted, dtype=np.float64)
    if x.shape != z.shape or x.ndim != 2 or x.shape[1] < 1:
        raise ValueError("EXP-071 geometry slice shape mismatch")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(z)):
        raise ValueError("EXP-071 non-finite representation value")
    x_norm = np.linalg.norm(x, axis=1)
    z_norm = np.linalg.norm(z, axis=1)
    if np.any(x_norm == 0.0) or np.any(z_norm == 0.0):
        raise ZeroDivisionError("EXP-071 zero row norm")
    raw_cosine = np.einsum("ij,ij->i", x, z) / (x_norm * z_norm)
    tolerance = 1e-12
    if np.any(raw_cosine < -1.0 - tolerance) or np.any(raw_cosine > 1.0 + tolerance):
        raise ArithmeticError("EXP-071 cosine range violation")
    cosine_distance = 1.0 - np.clip(raw_cosine, -1.0, 1.0)
    difference = z - x
    relative_l2 = np.linalg.norm(difference, axis=1) / x_norm
    xc = x - np.mean(x, axis=0)
    zc = z - np.mean(z, axis=0)
    gram_x = xc @ xc.T
    gram_z = zc @ zc.T
    denominator = math.sqrt(
        float(np.sum(gram_x * gram_x)) * float(np.sum(gram_z * gram_z))
    )
    if denominator == 0.0 or not math.isfinite(denominator):
        raise ZeroDivisionError("EXP-071 zero or non-finite CKA denominator")
    raw_cka = float(np.sum(gram_x * gram_z)) / denominator
    if raw_cka < -tolerance or raw_cka > 1.0 + tolerance:
        raise ArithmeticError("EXP-071 CKA range violation")
    cka = float(np.clip(raw_cka, 0.0, 1.0))
    maximum = float(np.max(np.abs(difference)))
    if (
        not np.all(np.isfinite(cosine_distance))
        or not np.all(np.isfinite(relative_l2))
        or not math.isfinite(cka)
        or not math.isfinite(maximum)
    ):
        raise ArithmeticError("EXP-071 non-finite derived geometry")
    return cosine_distance, relative_l2, cka, maximum


def compute_pair(frozen: Any, adapted: Any) -> tuple[Any, Any, float, float]:
    """Compatibility alias used by the synthetic contract tests."""
    return compute_geometry_pair(frozen, adapted)


def average_ranks(values: Any) -> Any:
    import numpy as np

    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError("EXP-071 rank input drift")
    order = np.argsort(array, kind="mergesort")
    ranks = np.empty(array.size, dtype=np.float64)
    position = 0
    while position < array.size:
        stop = position + 1
        while stop < array.size and array[order[stop]] == array[order[position]]:
            stop += 1
        ranks[order[position:stop]] = (position + 1 + stop) / 2.0
        position = stop
    return ranks


def spearman_description(x: Any, y: Any) -> dict[str, Any]:
    import numpy as np

    left = np.asarray(x, dtype=np.float64)
    right = np.asarray(y, dtype=np.float64)
    if left.shape != right.shape or left.ndim != 1 or left.size == 0:
        raise ValueError("EXP-071 Spearman input shape drift")
    if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
        raise ValueError("EXP-071 non-finite Spearman input")
    if np.all(left == left[0]) or np.all(right == right[0]):
        return {"rho": None, "reason": "constant_vector"}
    left_rank = average_ranks(left)
    right_rank = average_ranks(right)
    left_centered = left_rank - np.mean(left_rank)
    right_centered = right_rank - np.mean(right_rank)
    denominator = float(np.linalg.norm(left_centered) * np.linalg.norm(right_centered))
    if denominator == 0.0:
        return {"rho": None, "reason": "constant_vector"}
    rho = float(np.dot(left_centered, right_centered) / denominator)
    if not math.isfinite(rho) or rho < -1.0 - 1e-12 or rho > 1.0 + 1e-12:
        raise ArithmeticError("EXP-071 invalid Spearman coefficient")
    return {"rho": float(np.clip(rho, -1.0, 1.0)), "reason": None}


def recursive_close(left: Any, right: Any, *, atol: float = 1e-12) -> bool:
    if isinstance(left, Mapping) or isinstance(right, Mapping):
        return (
            isinstance(left, Mapping)
            and isinstance(right, Mapping)
            and set(left) == set(right)
            and all(recursive_close(left[key], right[key], atol=atol) for key in left)
        )
    if isinstance(left, list) or isinstance(right, list):
        return (
            isinstance(left, list)
            and isinstance(right, list)
            and len(left) == len(right)
            and all(recursive_close(a, b, atol=atol) for a, b in zip(left, right, strict=True))
        )
    if type(left) in (int, float) and type(right) in (int, float) and not isinstance(left, bool) and not isinstance(right, bool):
        return math.isfinite(float(left)) and math.isfinite(float(right)) and math.isclose(
            float(left), float(right), rel_tol=0.0, abs_tol=atol
        )
    return type(left) is type(right) and left == right


def _load_row_contract_values(config: Mapping[str, Any]) -> tuple[Any, Any, list[Any]]:
    import numpy as np

    path = require_record(config["source"]["exp070_extraction_terminal"]["row_contract"])
    header_bundle = read_npz_headers(path)
    order = header_bundle["member_order"]
    headers = header_bundle["members"]
    if order != ["ordinal", "fold_id", "component_code"]:
        raise ValueError("EXP-071 row-contract member order drift")
    if {key: _header_contract(headers[key]) for key in order} != ROW_CONTRACT_HEADERS:
        raise ValueError("EXP-071 row-contract header drift")
    with np.load(path, allow_pickle=False) as archive:
        ordinal = np.asarray(archive["ordinal"], dtype=np.int32)
        fold_id = np.asarray(archive["fold_id"], dtype=np.int8)
    if ordinal.shape != (ROWS,) or fold_id.shape != (ROWS,):
        raise ValueError("EXP-071 row-contract value shape drift")
    if _array_digest(ordinal) != config["source"]["exp070_extraction_terminal"]["row_identity"]["ordinal_sha256"]:
        raise ValueError("EXP-071 ordinal identity drift")
    if _array_digest(fold_id) != config["source"]["exp070_extraction_terminal"]["row_identity"]["fold_id_order_sha256"]:
        raise ValueError("EXP-071 fold identity drift")
    if not np.array_equal(ordinal, np.arange(ROWS, dtype=np.int32)):
        raise ValueError("EXP-071 ordinal permutation drift")
    fold_rows: list[Any] = []
    for fold in FOLDS:
        indices = np.flatnonzero(fold_id == fold)
        if indices.shape != (HELDOUT_ROWS,):
            raise ValueError("EXP-071 heldout fold count drift")
        ordered = indices[np.argsort(ordinal[indices], kind="stable")]
        if not np.all(np.diff(ordinal[ordered]) > 0):
            raise ValueError("EXP-071 heldout ordinal order drift")
        fold_rows.append(ordered)
    return ordinal, fold_id, fold_rows


def _load_probe_deltas(config: Mapping[str, Any]) -> list[float]:
    probe = config["source"]["exp070_probe_terminal"]
    path = require_record(probe["probe"])
    expected_paths = [
        f"results.main_contrasts.m3-s42:{point}.delta.five_label_macro_ap"
        for point in ALL_POINTS
    ]
    if probe["probe"].get("allowed_value_paths") != expected_paths:
        raise PermissionError("EXP-071 probe value allowlist drift")
    target_paths = [tuple(path_string.split(".")) for path_string in expected_paths]
    selected, spans = select_json_scalars(
        path.read_bytes(), target_paths, capture_paths=[("results",)]
    )
    results_payload = spans.get(("results",))
    if results_payload is None or bytes_sha256(results_payload + b"\n") != probe["verified_results_sha256"]:
        raise ValueError("EXP-071 probe result digest mismatch")
    result: list[float] = []
    for target in target_paths:
        cursor = selected[target]
        if type(cursor) not in (int, float) or not math.isfinite(float(cursor)):
            raise ValueError("EXP-071 invalid public probe delta")
        result.append(float(cursor))
    return result


def _matrix_map(config: Mapping[str, Any]) -> dict[str, Any]:
    import numpy as np

    result: dict[str, Any] = {}
    for item in config["source"]["matrices"]:
        path = require_record(item["artifact"])
        value = np.load(path, mmap_mode="r", allow_pickle=False)
        if (
            not isinstance(value, np.memmap)
            or value.flags.writeable
            or value.dtype != np.dtype("<f4")
            or list(value.shape) != item["shape"]
            or value.flags.f_contiguous
            or not value.flags.c_contiguous
        ):
            raise ValueError(f"EXP-071 matrix mapping drift: {item['worker_id']}")
        value.flags.writeable = False
        result[item["worker_id"]] = value
    if set(result) != {"base"} | {
        f"m3-s{seed}-f{fold}" for seed in (42, 43, 44) for fold in FOLDS
    }:
        raise ValueError("EXP-071 matrix mapping inventory drift")
    return result


def _matrix_point_indices(config: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    return {
        item["worker_id"]: {point: index for index, point in enumerate(item["points"])}
        for item in config["source"]["matrices"]
    }


def recompute_geometry(config: Mapping[str, Any]) -> dict[str, Any]:
    import numpy as np

    ordinal, _fold_id, fold_rows = _load_row_contract_values(config)
    del _fold_id
    probe_deltas = _load_probe_deltas(config)
    matrices = _matrix_map(config)
    point_indices = _matrix_point_indices(config)
    heldout_ordinals = np.empty((5, HELDOUT_ROWS), dtype="<i4")
    cosine = np.empty((15, ROWS), dtype="<f8")
    relative = np.empty((15, ROWS), dtype="<f8")
    cka = np.empty((15, 5), dtype="<f8")
    maximum = np.empty((15, 5), dtype="<f8")
    conditions: dict[str, Any] = {}
    sanity: dict[str, Any] = {}
    for fold, rows in zip(FOLDS, fold_rows, strict=True):
        heldout_ordinals[fold] = ordinal[rows]
    for condition_index, condition in enumerate(CONDITION_ORDER):
        seed_text, point = condition.split(":", 1)
        seed = int(seed_text[1:])
        per_fold: list[dict[str, Any]] = []
        for fold, rows in zip(FOLDS, fold_rows, strict=True):
            worker = f"m3-s{seed}-f{fold}"
            base_point = point_indices["base"][point]
            adapted_point = point_indices[worker][point]
            x = np.ascontiguousarray(matrices["base"][rows, base_point, :], dtype=np.float64)
            z = np.ascontiguousarray(matrices[worker][rows, adapted_point, :], dtype=np.float64)
            values_cosine, values_relative, value_cka, value_maximum = compute_geometry_pair(x, z)
            start = fold * HELDOUT_ROWS
            stop = start + HELDOUT_ROWS
            cosine[condition_index, start:stop] = values_cosine
            relative[condition_index, start:stop] = values_relative
            cka[condition_index, fold] = value_cka
            maximum[condition_index, fold] = value_maximum
            per_fold.append(
                {
                    "fold": fold,
                    "cosine_distance": distance_statistics(values_cosine),
                    "relative_l2_distance": distance_statistics(values_relative),
                }
            )
        sanity_applies = condition in SANITY_CONDITIONS
        sanity_passed: bool | None = (
            bool(np.all(maximum[condition_index] <= 1e-5)) if sanity_applies else None
        )
        if sanity_applies and not sanity_passed:
            raise ArithmeticError(f"EXP-071 pre-LoRA sanity failure: {condition}")
        conditions[condition] = {
            "per_fold_distance_statistics": per_fold,
            "pooled_distance_statistics": {
                "cosine_distance": distance_statistics(cosine[condition_index]),
                "relative_l2_distance": distance_statistics(relative[condition_index]),
            },
            "linear_cka": {
                "per_fold": [float(item) for item in cka[condition_index]],
                "mean": float(np.mean(cka[condition_index])),
                "sample_sd": float(np.std(cka[condition_index], ddof=1)),
            },
            "max_abs_difference": {
                "per_fold": [float(item) for item in maximum[condition_index]],
                "maximum": float(np.max(maximum[condition_index])),
                "sanity_gate_applies": sanity_applies,
                "sanity_gate_passed": sanity_passed,
            },
        }
        if sanity_applies:
            sanity[condition] = {
                "per_fold": [float(item) for item in maximum[condition_index]],
                "maximum": float(np.max(maximum[condition_index])),
                "passed": bool(sanity_passed),
            }
    spearman_x = np.asarray(
        [1.0 - conditions[f"s42:{point}"]["linear_cka"]["mean"] for point in ALL_POINTS],
        dtype=np.float64,
    )
    spearman = spearman_description(spearman_x, np.asarray(probe_deltas, dtype=np.float64))
    results = {
        "condition_order": list(CONDITION_ORDER),
        "conditions": conditions,
        "pre_lora_sanity": {
            "tolerance": 1e-5,
            "conditions": sanity,
            "passed": all(item["passed"] for item in sanity.values()),
        },
        "seed42_spearman": {
            "point_order": list(ALL_POINTS),
            "x": "1-five_fold_mean_linear_cka",
            "y": "verified_exp070_main_delta_five_label_macro_ap",
            "n": len(ALL_POINTS),
            **spearman,
        },
    }
    arrays = {
        "heldout_ordinals": heldout_ordinals,
        "cosine_distance": cosine,
        "relative_l2_distance": relative,
        "linear_cka": cka,
        "max_abs_difference": maximum,
    }
    if any(not np.all(np.isfinite(value)) for key, value in arrays.items() if key != "heldout_ordinals"):
        raise ArithmeticError("EXP-071 non-finite recomputed bundle")
    return {
        "arrays": arrays,
        "results": results,
        "probe_deltas": probe_deltas,
        "probe_results_sha256": config["source"]["exp070_probe_terminal"]["verified_results_sha256"],
        "comparison_count": len(CONDITION_ORDER) * len(FOLDS),
    }


def _validate_geometry_npz(path: Path, recomputed: Mapping[str, Any]) -> dict[str, Any]:
    import numpy as np

    header_bundle = read_npz_headers(path)
    order = header_bundle["member_order"]
    headers = header_bundle["members"]
    if order != list(NPZ_MEMBER_ORDER):
        raise ValueError("EXP-071 geometry NPZ member order drift")
    for name in NPZ_MEMBER_ORDER:
        header = headers[name]
        expected = NPZ_MEMBERS[name]
        if (
            _header_contract(header)
            != {"shape": expected["shape"], "dtype": expected["dtype"], "fortran_order": False}
        ):
            raise ValueError(f"EXP-071 geometry member header drift: {name}")
    with np.load(path, allow_pickle=False) as archive:
        if list(archive.files) != list(NPZ_MEMBER_ORDER):
            raise ValueError("EXP-071 geometry array order drift")
        loaded = {name: np.asarray(archive[name]) for name in NPZ_MEMBER_ORDER}
    if not np.array_equal(loaded["heldout_ordinals"], recomputed["arrays"]["heldout_ordinals"]):
        raise ValueError("EXP-071 heldout ordinals mismatch")
    for name in NPZ_MEMBER_ORDER[1:]:
        if not np.allclose(
            loaded[name], recomputed["arrays"][name], rtol=0.0, atol=1e-12, equal_nan=False
        ):
            raise ValueError(f"EXP-071 geometry mismatch: {name}")
    return {
        "member_order": list(NPZ_MEMBER_ORDER),
        "members": {
            name: {
                "shape": NPZ_MEMBERS[name]["shape"],
                "dtype": NPZ_MEMBERS[name]["dtype"],
                "sha256": _array_digest(loaded[name]),
            }
            for name in NPZ_MEMBER_ORDER
        },
    }


def validate_static_formal_contracts(
    static_config: Mapping[str, Any], formal_config: Mapping[str, Any]
) -> None:
    for key in (
        "source",
        "method",
        "method_protocol",
        "implementation",
        "environment",
        "resources",
    ):
        if static_config.get(key) != formal_config.get(key):
            raise ValueError(f"EXP-071 static/formal {key} drift")
    static_outputs = static_config.get("outputs")
    formal_outputs = formal_config.get("outputs")
    if not isinstance(static_outputs, Mapping) or not isinstance(formal_outputs, Mapping):
        raise ValueError("EXP-071 static/formal output contract missing")
    for key in (
        "formal_public_root",
        "formal_private_root",
        "public_directory_mode",
        "public_file_mode",
        "private_directory_mode",
        "private_file_mode",
    ):
        if static_outputs.get(key) != formal_outputs.get(key):
            raise ValueError(f"EXP-071 static/formal output binding drift: {key}")


def require_preflight_artifact_identities(config: Mapping[str, Any]) -> None:
    preflight = config.get("preflight")
    if not isinstance(preflight, Mapping):
        raise ValueError("EXP-071 formal preflight binding missing")
    for key in ("config", "static_run", "static_verification", "no_result_completion"):
        record = preflight.get(key)
        if not isinstance(record, Mapping):
            raise ValueError(f"EXP-071 preflight artifact missing: {key}")
        require_record(record)


def require_static_completion(config: Mapping[str, Any]) -> Path:
    parent = config.get("preflight")
    if not isinstance(parent, Mapping) or set(parent) != {
        "config",
        "static_run",
        "static_verification",
        "no_result_completion",
        "required_statuses",
        "formal_execution_authorized_by_preflight",
    }:
        raise ValueError("EXP-071 formal preflight binding schema drift")
    if parent.get("formal_execution_authorized_by_preflight") is not True:
        raise PermissionError("EXP-071 formal preflight has not authorized execution")
    expected_attempt2_config_path = (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/configs/"
        "exp-071-representation-drift-preflight-attempt-2.json"
    )
    if not isinstance(parent.get("config"), Mapping) or parent["config"].get("path") != expected_attempt2_config_path:
        raise ValueError("EXP-071 formal preflight must bind recovery attempt 2")
    if parent.get("required_statuses") != {
        "static_run": "CompletedAwaitingVerification",
        "static_verification": "Passed",
        "no_result_completion": "Complete",
    }:
        raise ValueError("EXP-071 formal preflight status contract drift")
    for name in ("config", "static_run", "static_verification", "no_result_completion"):
        record = parent[name]
        if not isinstance(record, Mapping) or record.get("bytes") == 0 or record.get("sha256") == "TBD":
            raise ValueError("EXP-071 formal preflight record is not frozen")
        require_record(record)
    static_config_path = require_record(parent["config"])
    static_config = load_config(static_config_path, kind="static")
    if _static_attempt(static_config) != 2:
        raise ValueError("EXP-071 formal preflight replay is not attempt 2")
    validate_static_formal_contracts(static_config, config)
    paths = require_implementation(static_config)
    require_import_boundaries(paths, static=False)
    environment = require_environment(static_config)
    public = _root(static_config, private=False, formal=False)
    private = _root(static_config, private=True, formal=False)
    if require_safe_root(public, private=False) != set(static_config["outputs"]["public_success_allowlist"]):
        raise ValueError("EXP-071 static terminal public inventory drift")
    if require_safe_root(private, private=True) != set(static_config["outputs"]["private_success_allowlist"]):
        raise ValueError("EXP-071 static terminal private inventory drift")
    require_file_modes(public, static_config["outputs"]["public_success_allowlist"], private=False)
    require_file_modes(private, static_config["outputs"]["private_success_allowlist"], private=True)
    before = source_identity_snapshot(static_config)
    require_parent_statuses(static_config, read_probe_values=False)
    headers = matrix_headers(static_config)
    row_headers = row_contract_headers(static_config)
    recorded_run = require_canonical_json(public / "static.json")
    synthetic = recorded_run.get("synthetic_tests")
    expected_command = [sys.executable, str(paths["tests"])]
    if (
        not isinstance(synthetic, Mapping)
        or set(synthetic) != {"status", "tests_run", "test_artifact", "command_sha256"}
        or synthetic.get("status") != "Passed"
        or type(synthetic.get("tests_run")) is not int
        or synthetic["tests_run"] < 1
        or synthetic.get("test_artifact") != artifact(paths["tests"])
        or synthetic.get("command_sha256") != bytes_sha256(canonical_json_bytes(expected_command))
    ):
        raise ValueError("EXP-071 recorded synthetic-suite proof drift")
    after = source_identity_snapshot(static_config)
    if before != after:
        raise ValueError("EXP-071 source changed during static replay")
    _run, _input, run_path, input_path = _validate_static_runner_payload(
        static_config_path,
        static_config,
        public,
        private,
        before,
        headers,
        row_headers,
        environment,
        synthetic,
    )
    verification_path = require_record(parent["static_verification"])
    completion_path = require_record(parent["no_result_completion"])
    expected_verification = _static_verification_payload(
        static_config_path, static_config, run_path, input_path, before, synthetic
    )
    if require_canonical_json(verification_path) != expected_verification:
        raise ValueError("EXP-071 static verification replay mismatch")
    expected_completion = _static_completion_payload(
        static_config, run_path, input_path, verification_path, before
    )
    if require_canonical_json(completion_path) != expected_completion:
        raise ValueError("EXP-071 static completion replay mismatch")
    if (
        parent["static_run"] != artifact(run_path)
        or parent["static_verification"] != artifact(verification_path)
        or parent["no_result_completion"] != artifact(completion_path)
    ):
        raise ValueError("EXP-071 static artifact chain drift")
    return completion_path


def _validate_formal_roots(config: Mapping[str, Any]) -> tuple[Path, Path, set[str]]:
    public = _root(config, private=False, formal=True)
    private = _root(config, private=True, formal=True)
    public_files = require_safe_root(public, private=False)
    allowed_public = (
        set(config["outputs"]["public_analyzed_allowlist"]),
        set(config["outputs"]["public_verified_allowlist"]),
        set(config["outputs"]["public_success_allowlist"]),
    )
    if public_files not in allowed_public:
        raise ValueError("EXP-071 formal public exact-prefix drift")
    if "failure.json" in public_files:
        raise RuntimeError("EXP-071 runner failure blocks verification")
    require_file_modes(public, sorted(public_files), private=False)
    private_files = require_safe_root(private, private=True)
    if private_files != set(config["outputs"]["private_success_allowlist"]):
        raise ValueError("EXP-071 formal private inventory drift")
    require_file_modes(private, sorted(private_files), private=True)
    if _directory_bytes(private) > config["resources"]["private_output_budget_bytes"]:
        raise OSError("EXP-071 formal private output budget exceeded")
    return public, private, public_files


def _initialized_access() -> dict[str, Any]:
    return {**INITIALIZE_ACCESS, "source_mutated": False}


def _analyzed_access() -> dict[str, Any]:
    return dict(ANALYZE_ACCESS)


def _expected_counts() -> dict[str, int]:
    return {
        "rows": ROWS,
        "folds": len(FOLDS),
        "heldout_rows_per_fold": HELDOUT_ROWS,
        "conditions": len(CONDITION_ORDER),
        "fold_condition_comparisons": len(CONDITION_ORDER) * len(FOLDS),
        "spearman_coefficients": 1,
    }


def _claim_counts() -> dict[str, int]:
    return {"rows": ROWS, "folds": 5, "conditions": 15, "comparisons": 75}


def _validate_claim_and_input(
    config_path: Path,
    config: Mapping[str, Any],
    static_completion: Path,
    source_snapshot: Mapping[str, Any],
    headers: Sequence[Mapping[str, Any]],
    row_headers: Mapping[str, Any],
    public: Path,
    private: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    claim_path = public / "run-claim.json"
    input_path = private / "input-manifest.json"
    claim = require_canonical_json(claim_path)
    input_manifest = require_canonical_json(input_path)
    expected_input_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "status", "config",
        "preflight", "method_sha256", "source_snapshot_sha256", "source_artifact_count",
        "matrix_headers", "row_contract_headers", "access",
    }
    if set(input_manifest) != expected_input_keys:
        raise ValueError("EXP-071 formal input-manifest schema drift")
    if (
        input_manifest.get("schema_version") != "exp-071-drift-input-manifest-v1"
        or input_manifest.get("experiment_id") != EXPERIMENT_ID
        or input_manifest.get("run_id") != config["run_id"]
        or input_manifest.get("attempt_id") != config["attempt_id"]
        or input_manifest.get("status") != "Initialized"
        or input_manifest.get("config") != artifact(config_path)
        or input_manifest.get("preflight") != config["preflight"]
        or input_manifest.get("method_sha256") != METHOD_SHA256
        or input_manifest.get("source_snapshot_sha256") != source_snapshot["sha256"]
        or input_manifest.get("source_artifact_count") != source_snapshot["artifact_count"]
        or input_manifest.get("matrix_headers") != list(headers)
        or input_manifest.get("row_contract_headers") != row_headers
        or input_manifest.get("access") != _initialized_access()
    ):
        raise ValueError("EXP-071 formal input-manifest binding drift")
    expected_claim_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "stage", "status",
        "config", "preflight_completion", "input_manifest", "method_sha256", "counts",
        "authorization", "access", "claim_boundary",
    }
    if set(claim) != expected_claim_keys:
        raise ValueError("EXP-071 run-claim schema drift")
    expected_authorization = {
        "formal_analysis": True,
        "representation_value_access": True,
        "probe_metric_value_access": True,
        "model_loading": False,
        "forward": False,
        "validation": False,
        "test": False,
    }
    if (
        claim.get("schema_version") != "exp-071-drift-run-claim-v1"
        or claim.get("experiment_id") != EXPERIMENT_ID
        or claim.get("run_id") != config["run_id"]
        or claim.get("attempt_id") != config["attempt_id"]
        or claim.get("stage") != "initialize"
        or claim.get("status") != "Initialized"
        or claim.get("config") != artifact(config_path)
        or claim.get("preflight_completion") != config["preflight"]["no_result_completion"]
        or claim.get("input_manifest") != artifact(input_path, logical_name="input-manifest.json")
        or claim.get("method_sha256") != METHOD_SHA256
        or claim.get("counts") != _claim_counts()
        or claim.get("authorization") != expected_authorization
        or claim.get("access") != _initialized_access()
        or claim.get("claim_boundary") != config["claim_boundary"]
    ):
        raise ValueError("EXP-071 run-claim binding drift")
    validate_public_payload(claim)
    return claim, input_manifest


def _validate_manifest_and_report(
    config_path: Path,
    config: Mapping[str, Any],
    public: Path,
    private: Path,
    source_snapshot: Mapping[str, Any],
    recomputed: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    bundle_path = private / "geometry.npz"
    manifest_path = private / "geometry-manifest.json"
    report_path = public / "drift.json"
    bundle_schema = _validate_geometry_npz(bundle_path, recomputed)
    manifest = require_canonical_json(manifest_path)
    report = require_canonical_json(report_path)
    expected_manifest_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "status", "config",
        "input_manifest", "method_sha256", "condition_order", "fold_order", "bundle",
        "members", "source_before", "source_after", "numeric_checks", "probe_source",
        "resources", "access",
    }
    if set(manifest) != expected_manifest_keys:
        raise ValueError("EXP-071 geometry-manifest schema drift")
    import numpy as np

    arrays = recomputed["arrays"]
    expected_numeric_checks = {
        "all_finite": True,
        "cosine_min": float(np.min(arrays["cosine_distance"])),
        "cosine_max": float(np.max(arrays["cosine_distance"])),
        "relative_l2_min": float(np.min(arrays["relative_l2_distance"])),
        "relative_l2_max": float(np.max(arrays["relative_l2_distance"])),
        "linear_cka_min": float(np.min(arrays["linear_cka"])),
        "linear_cka_max": float(np.max(arrays["linear_cka"])),
        "maximum_absolute_difference": float(np.max(arrays["max_abs_difference"])),
        "pre_lora_tolerance": 1e-5,
        "pre_lora_condition_count": len(SANITY_CONDITIONS),
        "pre_lora_maximum": float(
            max(
                np.max(arrays["max_abs_difference"][CONDITION_ORDER.index(condition)])
                for condition in SANITY_CONDITIONS
            )
        ),
        "pre_lora_passed": True,
    }
    expected_probe_source = {
        "probe": _artifact_fields(config["source"]["exp070_probe_terminal"]["probe"]),
        "verified_results_sha256": config["source"]["exp070_probe_terminal"]["verified_results_sha256"],
        "ap5_delta_sha256": _array_digest(np.asarray(recomputed["probe_deltas"], dtype="<f8")),
    }
    if (
        manifest.get("schema_version") != "exp-071-drift-geometry-manifest-v1"
        or manifest.get("experiment_id") != EXPERIMENT_ID
        or manifest.get("run_id") != config["run_id"]
        or manifest.get("attempt_id") != config["attempt_id"]
        or manifest.get("status") != "Sealed"
        or manifest.get("config") != artifact(config_path)
        or manifest.get("input_manifest") != artifact(private / "input-manifest.json", logical_name="input-manifest.json")
        or manifest.get("method_sha256") != METHOD_SHA256
        or manifest.get("condition_order") != list(CONDITION_ORDER)
        or manifest.get("fold_order") != list(FOLDS)
        or manifest.get("bundle") != artifact(bundle_path, logical_name="geometry.npz")
        or manifest.get("members") != config["method"]["private_bundle"]
        or manifest.get("source_before") != source_snapshot
        or manifest.get("source_after") != source_snapshot
        or not recursive_close(manifest.get("numeric_checks"), expected_numeric_checks)
        or manifest.get("probe_source") != expected_probe_source
        or manifest.get("access") != _analyzed_access()
    ):
        raise ValueError("EXP-071 geometry-manifest binding drift")
    _validate_resource_payload(manifest.get("resources"), config, require_disk=False)
    if manifest["resources"].get("private_output_bytes") != _directory_bytes(private):
        raise ValueError("EXP-071 private-output byte accounting drift")
    expected_report_keys = {
        "schema_version", "experiment_id", "run_id", "attempt_id", "stage", "status",
        "config", "input_manifest", "geometry_manifest", "geometry_bundle", "method_sha256",
        "counts", "results", "source_snapshot_sha256", "resources", "access",
        "exp071_complete", "exp072_authorized", "claim_boundary",
    }
    if set(report) != expected_report_keys:
        raise ValueError("EXP-071 drift report schema drift")
    if (
        report.get("schema_version") != "exp-071-drift-run-v1"
        or report.get("experiment_id") != EXPERIMENT_ID
        or report.get("run_id") != config["run_id"]
        or report.get("attempt_id") != config["attempt_id"]
        or report.get("stage") != "analyze"
        or report.get("status") != "CompletedAwaitingVerification"
        or report.get("config") != artifact(config_path)
        or report.get("input_manifest") != artifact(private / "input-manifest.json", logical_name="input-manifest.json")
        or report.get("geometry_manifest") != artifact(manifest_path, logical_name="geometry-manifest.json")
        or report.get("geometry_bundle") != artifact(bundle_path, logical_name="geometry.npz")
        or report.get("method_sha256") != METHOD_SHA256
        or report.get("counts") != _expected_counts()
        or not recursive_close(report.get("results"), recomputed["results"])
        or report.get("source_snapshot_sha256") != source_snapshot["sha256"]
        or report.get("resources") != manifest.get("resources")
        or report.get("access") != _analyzed_access()
        or report.get("exp071_complete") is not False
        or report.get("exp072_authorized") is not False
        or report.get("claim_boundary") != config["claim_boundary"]
    ):
        raise ValueError("EXP-071 drift report binding drift")
    _validate_resource_payload(report.get("resources"), config, require_disk=False)
    validate_public_payload(report)
    return manifest, report, bundle_schema


def _formal_verification_payload(
    config_path: Path,
    config: Mapping[str, Any],
    public: Path,
    private: Path,
    static_completion: Path,
    source_snapshot: Mapping[str, Any],
    report: Mapping[str, Any],
    recomputed: Mapping[str, Any],
) -> dict[str, Any]:
    run_results_sha256 = bytes_sha256(canonical_json_bytes(report["results"]))
    recomputed_results_sha256 = bytes_sha256(canonical_json_bytes(recomputed["results"]))
    value = {
        "schema_version": "exp-071-drift-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "stage": "formal",
        "status": "Passed",
        "passed_count": len(FORMAL_CHECKS),
        "failed_count": 0,
        "checks": list(FORMAL_CHECKS),
        "config": artifact(config_path),
        "static_completion": artifact(static_completion),
        "run_claim": artifact(public / "run-claim.json"),
        "run": artifact(public / "drift.json"),
        "input_manifest": artifact(private / "input-manifest.json", logical_name="input-manifest.json"),
        "geometry_bundle": artifact(private / "geometry.npz", logical_name="geometry.npz"),
        "geometry_manifest": artifact(private / "geometry-manifest.json", logical_name="geometry-manifest.json"),
        "method_sha256": METHOD_SHA256,
        "source_snapshot_sha256": source_snapshot["sha256"],
        "probe_results_sha256": recomputed["probe_results_sha256"],
        "run_results_sha256": run_results_sha256,
        "recomputed_results_sha256": recomputed_results_sha256,
        "comparison_count": recomputed["comparison_count"],
        "comparison_tolerance": {"rtol": 0.0, "atol": 1e-12},
        "source_unchanged": True,
        "producer_imported": False,
        "model_libraries_imported": False,
        "access": {
            **_analyzed_access(),
            "geometry_bundle_values_read": True,
            "metrics_recomputed": True,
            "spearman_recomputed": True,
        },
        "exp071_complete": False,
        "exp072_authorized": False,
        "claim_boundary": config["claim_boundary"],
    }
    validate_public_payload(value)
    return value


def _formal_completion_payload(
    config: Mapping[str, Any],
    public: Path,
    private: Path,
    static_completion: Path,
    verification_path: Path,
    verification: Mapping[str, Any],
) -> dict[str, Any]:
    value = {
        "schema_version": "exp-071-drift-complete-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "status": "Complete",
        "static_completion": artifact(static_completion),
        "run": artifact(public / "drift.json"),
        "verification": artifact(verification_path),
        "input_manifest": artifact(private / "input-manifest.json", logical_name="input-manifest.json"),
        "geometry_bundle": artifact(private / "geometry.npz", logical_name="geometry.npz"),
        "geometry_manifest": artifact(private / "geometry-manifest.json", logical_name="geometry-manifest.json"),
        "method_sha256": METHOD_SHA256,
        "run_results_sha256": verification["run_results_sha256"],
        "recomputed_results_sha256": verification["recomputed_results_sha256"],
        "comparison_count": verification["comparison_count"],
        "source_unchanged": True,
        "model_loaded": False,
        "forward_executed": False,
        "source_mutated": False,
        "exp071_complete": True,
        "exp072_authorized": False,
        "claim_boundary": config["claim_boundary"],
        "next_gate": "EXP-071 Complete; EXP-072 unauthorized",
    }
    validate_public_payload(value)
    return value


def _peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


@contextmanager
def _file_mutex(path: Path, label: str) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    if path.is_symlink():
        raise PermissionError(f"Symlink {label} lock rejected")
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"Concurrent {label} workload detected") from exc
        os.fchmod(descriptor, 0o600)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


@contextmanager
def formal_verifier_lock() -> Iterator[None]:
    with _file_mutex(HEAVY_LOCK, "heavy research"):
        with _file_mutex(VERIFIER_LOCK, "EXP-071 verifier"):
            yield


def verify_formal(config_path: Path, *, complete: bool) -> dict[str, Any]:
    with formal_verifier_lock():
        return _verify_formal_locked(config_path, complete=complete)


def _verify_formal_locked(config_path: Path, *, complete: bool) -> dict[str, Any]:
    config_path = config_path.resolve()
    started = time.monotonic()
    config = load_config(config_path, kind="formal")
    paths = require_implementation(config)
    require_import_boundaries(paths, static=False)
    environment = require_environment(config)
    del environment
    static_completion = require_static_completion(config)
    if shutil.disk_usage(PROJECT_ROOT).free < config["resources"]["minimum_free_disk_bytes"]:
        raise OSError("EXP-071 verifier free-disk gate failed")
    public, private, public_files = _validate_formal_roots(config)
    verification_path = public / "verification.json"
    completion_path = public / "drift-complete.json"
    if "verification.json" in public_files:
        prefix = require_canonical_json(verification_path)
        if prefix.get("status") != "Passed" or prefix.get("failed_count") != 0:
            raise RuntimeError("Only an exact Passed formal verification prefix can resume")
    sealed_static_source, _ = select_json_scalars(
        static_completion.read_bytes(), [("source_snapshot_sha256",)]
    )
    before = source_identity_snapshot(config)
    if before["sha256"] != sealed_static_source[("source_snapshot_sha256",)]:
        raise ValueError("EXP-071 formal source snapshot is not bound to static completion")
    require_parent_statuses(config, read_probe_values=False)
    headers = matrix_headers(config)
    row_headers = row_contract_headers(config)
    _claim, _input = _validate_claim_and_input(
        config_path,
        config,
        static_completion,
        before,
        headers,
        row_headers,
        public,
        private,
    )
    recomputed = recompute_geometry(config)
    _manifest, report, _bundle = _validate_manifest_and_report(
        config_path, config, public, private, before, recomputed
    )
    after = source_identity_snapshot(config)
    if after != before:
        raise ValueError("EXP-071 source changed during formal verification")
    require_preflight_artifact_identities(config)
    elapsed = time.monotonic() - started
    if elapsed > config["resources"]["verifier_wall_seconds"]:
        raise TimeoutError("EXP-071 verifier wall-time ceiling exceeded")
    if _peak_rss_bytes() > config["resources"]["peak_rss_bytes"]:
        raise MemoryError("EXP-071 verifier peak-RSS ceiling exceeded")
    loaded_modules = {name.split(".", 1)[0] for name in sys.modules}
    if loaded_modules & FORBIDDEN_MODEL_MODULES:
        raise RuntimeError("EXP-071 verifier imported a model library")
    if any(name.endswith("run_exp071_drift") for name in sys.modules):
        raise RuntimeError("EXP-071 verifier imported the producer")
    expected_verification = _formal_verification_payload(
        config_path, config, public, private, static_completion, before, report, recomputed
    )
    if os.path.lexists(verification_path):
        if require_canonical_json(verification_path) != expected_verification:
            raise ValueError("EXP-071 Passed verification prefix drift")
    elif complete:
        raise RuntimeError("Formal completion requires an existing Passed verification")
    else:
        if public_files != set(config["outputs"]["public_analyzed_allowlist"]):
            raise ValueError("EXP-071 formal preverification inventory drift")
        create_json_once(verification_path, expected_verification)
    if complete:
        expected_completion = _formal_completion_payload(
            config,
            public,
            private,
            static_completion,
            verification_path,
            expected_verification,
        )
        if os.path.lexists(completion_path):
            if require_canonical_json(completion_path) != expected_completion:
                raise ValueError("EXP-071 completion prefix drift")
        else:
            create_json_once(completion_path, expected_completion)
        if require_safe_root(public, private=False) != set(config["outputs"]["public_success_allowlist"]):
            raise ValueError("EXP-071 formal terminal inventory drift")
        require_file_modes(public, config["outputs"]["public_success_allowlist"], private=False)
    elif os.path.lexists(completion_path):
        raise RuntimeError("Formal verify cannot create or consume completion")
    elif require_safe_root(public, private=False) != set(config["outputs"]["public_verified_allowlist"]):
        raise ValueError("EXP-071 formal verified inventory drift")
    return expected_verification


def _record_failure(kind: str, config_path: Path, error: BaseException) -> None:
    try:
        config_path = config_path.resolve()
        config = strict_json(config_path)
        if not isinstance(config, Mapping) or _config_kind(config) != kind:
            return
        public = _root(config, private=False, formal=kind == "formal")
        if not public.is_dir() or public.is_symlink() or file_mode(public) != "0755":
            return
        if kind == "static":
            prerequisite = public / "static.json"
            target = public / "static-verification.json"
            schema = "exp-071-drift-static-verification-failure-v1"
            stage = "no-result-preflight"
        else:
            prerequisite = public / "drift.json"
            target = public / "verification.json"
            schema = "exp-071-drift-verification-failure-v1"
            stage = "formal"
            if (public / "failure.json").exists():
                return
        if (
            not prerequisite.is_file()
            or prerequisite.is_symlink()
            or prerequisite.stat().st_nlink != 1
            or file_mode(prerequisite) != "0644"
            or os.path.lexists(target)
        ):
            return
        value = {
            "schema_version": schema,
            "experiment_id": EXPERIMENT_ID,
            "run_id": config.get("run_id"),
            "attempt_id": config.get("attempt_id"),
            "stage": stage,
            "status": "Failed",
            "technical_failure": True,
            "error_type": type(error).__name__,
            "exp071_complete": False,
            "exp072_authorized": False,
            "claim_boundary": config.get("claim_boundary"),
        }
        validate_public_payload(value)
        create_json_once(target, value)
    except Exception:
        return


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        required=True,
        choices=("static-verify", "static-complete", "formal-verify", "formal-complete"),
    )
    parser.add_argument("--config", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    kind, phase = args.stage.split("-", 1)
    config_path = args.config or (
        DEFAULT_STATIC_CONFIG if kind == "static" else DEFAULT_FORMAL_CONFIG
    )
    config_path = config_path.resolve()
    try:
        result = (
            verify_static(config_path, complete=phase == "complete")
            if kind == "static"
            else verify_formal(config_path, complete=phase == "complete")
        )
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as error:
        if phase == "verify":
            _record_failure(kind, config_path, error)
        print(f"{type(error).__name__}: verification failed", file=sys.stderr)
        return 1
    print(json.dumps({"stage": args.stage, "status": result["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
