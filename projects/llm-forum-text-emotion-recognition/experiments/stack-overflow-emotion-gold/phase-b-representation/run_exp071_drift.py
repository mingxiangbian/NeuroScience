#!/usr/bin/env python3
"""Frozen EXP-071 representation-drift producer.

The module deliberately keeps NumPy out of its import graph until ``analyze``.
``static`` hashes bound artifacts and parses array headers only. ``initialize``
creates an empty formal namespace. ``analyze`` consumes the exact heldout rows,
seals one private geometry bundle, and writes the public aggregate last.
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
import tempfile
import time
from typing import Any, BinaryIO, Callable, Iterable, Iterator, Mapping, Sequence
import zipfile


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
ATTEMPT1_STATIC_CONFIG = MODULE_DIR / "configs" / "exp-071-representation-drift-preflight.json"
DEFAULT_STATIC_CONFIG = (
    MODULE_DIR / "configs" / "exp-071-representation-drift-preflight-attempt-2.json"
)
DEFAULT_FORMAL_CONFIG = MODULE_DIR / "configs" / "exp-071-representation-drift-formal.json"
ANALYSIS_LOCK = MODULE_DIR / "private" / "locks" / "exp071-representation-drift.lock"
HEAVY_LOCK = MODULE_DIR / "private" / "locks" / "heavy-research-workload.lock"

EXPERIMENT_ID = "EXP-071"
ROWS = 3360
FOLDS = (0, 1, 2, 3, 4)
HELDOUT_PER_FOLD = 672
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
EXPECTED_AP5_PATHS = tuple(
    f"results.main_contrasts.m3-s42:{point}.delta.five_label_macro_ap"
    for point in ALL_POINTS
)
PRIVATE_MEMBER_ORDER = (
    "heldout_ordinals",
    "cosine_distance",
    "relative_l2_distance",
    "linear_cka",
    "max_abs_difference",
)
STATIC_NUMERIC_MODULES = ("numpy", "scipy", "sklearn")
FORBIDDEN_MODEL_MODULES = ("mlx", "mlx_lm", "torch", "transformers")
NUMERIC_TOLERANCE = 1e-12
SANITY_TOLERANCE = 1e-5
METHOD_SHA256 = "f428523680acd2dd130bb78ac3bcdebbceec2b64ced18730e936323e685cc210"
EXPECTED_SOURCE_SHA256 = "8f7bc1836021053d0ffd48a620170996ed72475f54c57034ca2591dd515dffcf"
METHOD_PROTOCOL_RECORD = {
    "path": "experiments/stack-overflow-emotion-gold/protocols/exp-071-representation-drift.md",
    "bytes": 13708,
    "mode": "0644",
    "sha256": "7d03bde05da6b83e4db9e0c3396140fba6fd7418a8c678ce4a825e0d9208e099",
}
EXPECTED_ENVIRONMENT = {
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
EXPECTED_RESOURCES = {
    "maximum_concurrent_workers": 1,
    "runner_wall_seconds": 7200,
    "verifier_wall_seconds": 7200,
    "peak_rss_bytes": 4294967296,
    "private_output_budget_bytes": 67108864,
    "minimum_free_disk_bytes": 1073741824,
    "threads_per_library": 1,
    "api_cost_usd": 0,
}
EXPECTED_IMPLEMENTATION_PATHS = {
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
CLAIM_BOUNDARY_SHA256 = {
    "static": "665b0147992f94e996d5bd4ce0a999fa7249307902447a13aaaecec8dd0a6f60",
    "formal": "3530f3ac1a2a2e30d013e104ec7718216ce1a6b884d0a2fc7457675a94a1c000",
}
PENDING_FORMAL_CLAIM_SHA256 = "bc883ac6c7eaa3d2c40df078e6742837a9ade900dc2706f0969b3037a3f92d1d"
INCIDENT_001 = {
    "id": "EXP-071-PREFLIGHT-INCIDENT-001",
    "failed_config": {
        "path": (
            "experiments/stack-overflow-emotion-gold/phase-b-representation/configs/"
            "exp-071-representation-drift-preflight.json"
        ),
        "bytes": 25672,
        "mode": "0644",
        "sha256": "9a030313ffe5d4e3bf40104327b749f319bf3707c93f12866d0ebe5369b084a7",
    },
    "failure_artifact": {
        "path": (
            "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
            "exp-071-representation-drift/preflight-attempt-1/failure.json"
        ),
        "bytes": 395,
        "mode": "0644",
        "sha256": "e586400fd2ea57a98c5c4dc06f9d4c719b41d358947c9be9cc5a40211cd5ca33",
    },
    "root_cause": "relative_config_path_not_resolved_before_stage_dispatch",
    "recovery_scope": "resolve_config_path_and_use_fresh_preflight_namespace_only",
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

INITIALIZE_ACCESS = {
    **STATIC_ACCESS,
    "formal_roots_created": True,
}

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


class SanityGateError(RuntimeError):
    """The frozen pre-LoRA coordinate identity no longer holds."""


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


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


_JSON_WHITESPACE = b" \t\r\n"
_JSON_HEX = frozenset(b"0123456789abcdefABCDEF")


def _json_ws(payload: bytes, index: int) -> int:
    while index < len(payload) and payload[index] in _JSON_WHITESPACE:
        index += 1
    return index


def _json_string_end(payload: bytes, index: int) -> int:
    if index >= len(payload) or payload[index] != 0x22:
        raise ValueError("Expected JSON string")
    index += 1
    while index < len(payload):
        byte = payload[index]
        if byte == 0x22:
            return index + 1
        if byte < 0x20:
            raise ValueError("Control byte in JSON string")
        if byte == 0x5C:
            index += 1
            if index >= len(payload) or payload[index] not in b'"\\/bfnrtu':
                raise ValueError("Invalid JSON escape")
            if payload[index] == ord("u"):
                if index + 4 >= len(payload) or any(
                    value not in _JSON_HEX for value in payload[index + 1 : index + 5]
                ):
                    raise ValueError("Invalid JSON unicode escape")
                index += 4
        index += 1
    raise ValueError("Unterminated JSON string")


def _json_number_end(payload: bytes, index: int) -> int:
    start = index
    if index < len(payload) and payload[index] == ord("-"):
        index += 1
    if index >= len(payload):
        raise ValueError("Truncated JSON number")
    if payload[index] == ord("0"):
        index += 1
        if index < len(payload) and ord("0") <= payload[index] <= ord("9"):
            raise ValueError("Leading zero in JSON number")
    elif ord("1") <= payload[index] <= ord("9"):
        index += 1
        while index < len(payload) and ord("0") <= payload[index] <= ord("9"):
            index += 1
    else:
        raise ValueError("Invalid JSON number")
    if index < len(payload) and payload[index] == ord("."):
        index += 1
        fraction = index
        while index < len(payload) and ord("0") <= payload[index] <= ord("9"):
            index += 1
        if index == fraction:
            raise ValueError("Missing JSON fraction")
    if index < len(payload) and payload[index] in b"eE":
        index += 1
        if index < len(payload) and payload[index] in b"+-":
            index += 1
        exponent = index
        while index < len(payload) and ord("0") <= payload[index] <= ord("9"):
            index += 1
        if index == exponent:
            raise ValueError("Missing JSON exponent")
    if index == start:
        raise ValueError("Invalid JSON number")
    return index


def _json_skip_value(payload: bytes, index: int) -> int:
    index = _json_ws(payload, index)
    if index >= len(payload):
        raise ValueError("Truncated JSON value")
    byte = payload[index]
    if byte == 0x22:
        return _json_string_end(payload, index)
    if byte == 0x7B:
        index = _json_ws(payload, index + 1)
        if index < len(payload) and payload[index] == 0x7D:
            return index + 1
        while True:
            index = _json_string_end(payload, index)
            index = _json_ws(payload, index)
            if index >= len(payload) or payload[index] != 0x3A:
                raise ValueError("Missing JSON object colon")
            index = _json_skip_value(payload, index + 1)
            index = _json_ws(payload, index)
            if index >= len(payload):
                raise ValueError("Truncated JSON object")
            if payload[index] == 0x7D:
                return index + 1
            if payload[index] != 0x2C:
                raise ValueError("Missing JSON object comma")
            index = _json_ws(payload, index + 1)
    if byte == 0x5B:
        index = _json_ws(payload, index + 1)
        if index < len(payload) and payload[index] == 0x5D:
            return index + 1
        while True:
            index = _json_skip_value(payload, index)
            index = _json_ws(payload, index)
            if index >= len(payload):
                raise ValueError("Truncated JSON array")
            if payload[index] == 0x5D:
                return index + 1
            if payload[index] != 0x2C:
                raise ValueError("Missing JSON array comma")
            index = _json_ws(payload, index + 1)
    for literal in (b"true", b"false", b"null"):
        if payload.startswith(literal, index):
            return index + len(literal)
    return _json_number_end(payload, index)


def _decode_json_string(payload: bytes, start: int, end: int) -> str:
    value = json.loads(payload[start:end].decode("utf-8"))
    if type(value) is not str:
        raise ValueError("JSON key is not a string")
    return value


def _decode_json_scalar(payload: bytes, start: int, end: int) -> Any:
    value = json.loads(payload[start:end].decode("utf-8"), parse_constant=_no_constant)
    if isinstance(value, (dict, list)):
        raise ValueError("Allowlisted JSON path is not scalar")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Allowlisted JSON scalar is non-finite")
    return value


def selective_json_scalars(
    payload: bytes,
    allowed_paths: Iterable[Sequence[str]],
    *,
    capture_paths: Iterable[Sequence[str]] = (),
) -> tuple[dict[tuple[str, ...], Any], dict[tuple[str, ...], bytes]]:
    """Materialize only exact allowlisted scalar paths from a JSON document.

    Unselected values are grammar-checked and skipped lexically. Captured values
    are returned as their raw JSON byte slices, which permits digest validation
    without constructing the object represented by those bytes.
    """

    allowed = {tuple(path) for path in allowed_paths}
    captures_requested = {tuple(path) for path in capture_paths}
    relevant = allowed | captures_requested
    found: dict[tuple[str, ...], Any] = {}
    captures: dict[tuple[str, ...], bytes] = {}

    def is_prefix(path: tuple[str, ...]) -> bool:
        return any(target[: len(path)] == path for target in relevant)

    def parse_value(index: int, path: tuple[str, ...]) -> int:
        start = _json_ws(payload, index)
        if not is_prefix(path):
            return _json_skip_value(payload, start)
        if path in allowed:
            end = _json_skip_value(payload, start)
            if payload[start] in (0x7B, 0x5B):
                raise ValueError("Allowlisted path is not scalar")
            if path in found:
                raise ValueError("Duplicate allowlisted JSON path")
            found[path] = _decode_json_scalar(payload, start, end)
            if path in captures_requested:
                captures[path] = payload[start:end]
            return end
        if start >= len(payload):
            raise ValueError("Truncated relevant JSON value")
        if payload[start] == 0x7B:
            index = _json_ws(payload, start + 1)
            seen: set[str] = set()
            if index < len(payload) and payload[index] == 0x7D:
                end = index + 1
            else:
                while True:
                    key_start = index
                    key_end = _json_string_end(payload, key_start)
                    key = _decode_json_string(payload, key_start, key_end)
                    if key in seen:
                        raise ValueError("Duplicate JSON object key")
                    seen.add(key)
                    index = _json_ws(payload, key_end)
                    if index >= len(payload) or payload[index] != 0x3A:
                        raise ValueError("Missing JSON object colon")
                    index = parse_value(index + 1, path + (key,))
                    index = _json_ws(payload, index)
                    if index >= len(payload):
                        raise ValueError("Truncated JSON object")
                    if payload[index] == 0x7D:
                        end = index + 1
                        break
                    if payload[index] != 0x2C:
                        raise ValueError("Missing JSON object comma")
                    index = _json_ws(payload, index + 1)
        elif payload[start] == 0x5B:
            # No registered EXP-071 scalar path addresses an array element.
            end = _json_skip_value(payload, start)
        else:
            end = _json_skip_value(payload, start)
        if path in captures_requested:
            captures[path] = payload[start:end]
        return end

    end = parse_value(0, ())
    if _json_ws(payload, end) != len(payload):
        raise ValueError("Trailing JSON content")
    if set(found) != allowed or set(captures) != captures_requested:
        missing = (allowed - set(found)) | (captures_requested - set(captures))
        raise ValueError(f"Missing selective JSON paths: {sorted(missing)}")
    return found, captures


def _selected_file_scalars(path: Path, paths: Iterable[Sequence[str]]) -> dict[tuple[str, ...], Any]:
    values, _ = selective_json_scalars(path.read_bytes(), paths)
    return values


def bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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
    path = PROJECT_ROOT.joinpath(*pure.parts)
    current = PROJECT_ROOT
    for part in pure.parts:
        current = current / part
        if os.path.lexists(current) and current.is_symlink():
            raise PermissionError("Symlink path rejected")
    if must_exist and not os.path.lexists(path):
        raise FileNotFoundError(path)
    return path


def artifact(path: Path, *, logical_name: str | None = None) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError(f"Unsafe or missing artifact: {path}")
    result: dict[str, Any] = {
        "bytes": path.stat().st_size,
        "mode": file_mode(path),
        "sha256": sha256(path),
    }
    if logical_name is None:
        result["path"] = path.relative_to(PROJECT_ROOT).as_posix()
    else:
        result["logical_name"] = logical_name
    return result


def logical_artifact(path: Path, logical_name: str) -> dict[str, Any]:
    return artifact(path, logical_name=logical_name)


def _identity_fields(record: Mapping[str, Any]) -> dict[str, Any]:
    required = {"path", "bytes", "mode", "sha256"}
    if not required.issubset(record):
        raise ValueError("Artifact record schema drift")
    value = {key: record[key] for key in ("path", "bytes", "mode", "sha256")}
    if (
        type(value["path"]) is not str
        or type(value["bytes"]) is not int
        or type(value["mode"]) is not str
        or type(value["sha256"]) is not str
        or value["bytes"] <= 0
        or value["mode"] == "TBD"
        or value["sha256"] == "TBD"
    ):
        raise ValueError("Unfrozen artifact record")
    return value


def require_record(record: Mapping[str, Any]) -> Path:
    expected = _identity_fields(record)
    path = resolve_project(str(expected["path"]))
    if artifact(path) != expected:
        raise ValueError(f"Artifact identity drift: {expected['path']}")
    return path


def create_json_once(path: Path, value: Any, *, private: bool = False) -> None:
    payload = canonical_json_bytes(value)
    mode = 0o600 if private else 0o644
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    inode = os.fstat(descriptor).st_ino
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        os.unlink(temporary)
        if path.is_symlink() or path.stat().st_nlink != 1 or file_mode(path) != f"{mode:04o}":
            raise PermissionError("Atomic JSON publication drift")
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if os.path.lexists(temporary):
            current = temporary.lstat()
            if stat.S_ISREG(current.st_mode) and current.st_ino == inode and current.st_nlink == 1:
                os.unlink(temporary)


def _create_root(path: Path, *, private: bool) -> None:
    if os.path.lexists(path):
        raise FileExistsError(f"Output root already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    if private:
        os.chmod(path.parent, 0o700)
    path.mkdir(mode=0o700 if private else 0o755)
    os.chmod(path, 0o700 if private else 0o755)


def inventory(root: Path) -> tuple[set[str], set[str]]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid inventory root")
    files: set[str] = set()
    directories: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise PermissionError("Nested symlink rejected")
        relative = path.relative_to(root).as_posix()
        if path.is_file():
            if path.stat().st_nlink != 1:
                raise PermissionError("Hard-link drift")
            files.add(relative)
        elif path.is_dir():
            directories.add(relative)
        else:
            raise PermissionError("Special filesystem entry rejected")
    return files, directories


def require_exact_inventory(
    root: Path,
    expected_files: Iterable[str],
    *,
    expected_directories: Iterable[str] = (),
    private: bool,
) -> None:
    if file_mode(root) != ("0700" if private else "0755"):
        raise PermissionError("Root mode drift")
    files, directories = inventory(root)
    if files != set(expected_files) or directories != set(expected_directories):
        raise ValueError("Output inventory drift")
    expected_mode = "0600" if private else "0644"
    for relative in files:
        if file_mode(root / relative) != expected_mode:
            raise PermissionError("Output file mode drift")
    expected_directory_mode = "0700" if private else "0755"
    for relative in directories:
        if file_mode(root / relative) != expected_directory_mode:
            raise PermissionError("Output directory mode drift")


def _read_npy_header_stream(handle: BinaryIO) -> dict[str, Any]:
    if handle.read(6) != b"\x93NUMPY":
        raise ValueError("Invalid NPY magic")
    version = tuple(handle.read(2))
    if version == (1, 0):
        length_bytes = handle.read(2)
        if len(length_bytes) != 2:
            raise ValueError("Truncated NPY header length")
        header_length = struct.unpack("<H", length_bytes)[0]
    elif version in {(2, 0), (3, 0)}:
        length_bytes = handle.read(4)
        if len(length_bytes) != 4:
            raise ValueError("Truncated NPY header length")
        header_length = struct.unpack("<I", length_bytes)[0]
    else:
        raise ValueError("Unsupported NPY version")
    header = handle.read(header_length)
    if len(header) != header_length:
        raise ValueError("Truncated NPY header")
    try:
        parsed = ast.literal_eval(header.decode("latin1").strip())
    except (SyntaxError, ValueError) as exc:
        raise ValueError("Invalid NPY header") from exc
    if not isinstance(parsed, dict) or set(parsed) != {"descr", "fortran_order", "shape"}:
        raise ValueError("NPY header schema drift")
    shape = parsed["shape"]
    if (
        not isinstance(shape, tuple)
        or any(type(item) is not int or item < 0 for item in shape)
        or type(parsed["descr"]) is not str
        or type(parsed["fortran_order"]) is not bool
    ):
        raise ValueError("NPY header value drift")
    return {
        "version": list(version),
        "descr": parsed["descr"],
        "fortran_order": parsed["fortran_order"],
        "shape": list(shape),
        "data_offset": handle.tell(),
    }


def read_npy_header(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("Unsafe NPY source")
    with path.open("rb") as handle:
        header = _read_npy_header_stream(handle)
    header["file_bytes"] = path.stat().st_size
    return header


def read_npz_headers(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError("Unsafe NPZ source")
    members: dict[str, Any] = {}
    order: list[str] = []
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        if len({item.filename for item in infos}) != len(infos):
            raise ValueError("Duplicate NPZ member")
        for info in infos:
            if (
                info.is_dir()
                or info.flag_bits & 1
                or info.compress_type != zipfile.ZIP_STORED
                or not info.filename.endswith(".npy")
                or "/" in info.filename
                or "\\" in info.filename
            ):
                raise ValueError("Unsafe or compressed NPZ member")
            name = info.filename[:-4]
            with archive.open(info, "r") as handle:
                header = _read_npy_header_stream(handle)
            header.update(
                {
                    "compressed_bytes": info.compress_size,
                    "uncompressed_bytes": info.file_size,
                }
            )
            order.append(name)
            members[name] = header
    return {"member_order": order, "members": members, "file_bytes": path.stat().st_size}


def method_sha256(config_or_method: Mapping[str, Any]) -> str:
    method = config_or_method.get("method", config_or_method)
    if not isinstance(method, Mapping):
        raise TypeError("Method must be an object")
    return bytes_sha256(canonical_json_bytes(method))


def _validate_method(method: Mapping[str, Any]) -> None:
    if set(method) != {
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
        raise ValueError("Method schema drift")
    if bytes_sha256(canonical_json_bytes(method)) != METHOD_SHA256:
        raise ValueError("Method digest drift")
    if method.get("condition_order") != list(CONDITION_ORDER):
        raise ValueError("Condition order drift")
    rows = method.get("rows", {})
    if rows != {
        "total": ROWS,
        "folds": 5,
        "heldout_per_fold": HELDOUT_PER_FOLD,
        "heldout_only": True,
        "fold_order": list(FOLDS),
        "within_fold_order": "ascending_ordinal",
    }:
        raise ValueError("Row method drift")
    representation = method.get("representation", {})
    if (
        representation.get("source_dtype") != "float32"
        or representation.get("calculation_dtype") != "float64"
        or representation.get("hidden_size") != HIDDEN_SIZE
        or representation.get("memory_map_mode") != "r"
        or representation.get("writeable") is not False
        or representation.get("slice_shape") != [HELDOUT_PER_FOLD, HIDDEN_SIZE]
        or representation.get("finite_required") is not True
    ):
        raise ValueError("Representation method drift")
    if method.get("private_bundle", {}).get("member_order") != list(PRIVATE_MEMBER_ORDER):
        raise ValueError("Private member order drift")
    expected_members = {
        "heldout_ordinals": {"shape": [5, 672], "dtype": "<i4"},
        "cosine_distance": {"shape": [15, 3360], "dtype": "<f8"},
        "relative_l2_distance": {"shape": [15, 3360], "dtype": "<f8"},
        "linear_cka": {"shape": [15, 5], "dtype": "<f8"},
        "max_abs_difference": {"shape": [15, 5], "dtype": "<f8"},
    }
    if method.get("private_bundle", {}).get("members") != expected_members:
        raise ValueError("Private bundle schema drift")
    lifecycle = method.get("lifecycle", {})
    if lifecycle.get("runner_stages") != ["static", "initialize", "analyze"]:
        raise ValueError("Runner lifecycle drift")
    if method.get("sanity", {}).get("maximum_absolute_tolerance") != SANITY_TOLERANCE:
        raise ValueError("Sanity tolerance drift")
    if (
        method.get("sanity", {}).get("arithmetic_dtype") != "float64"
        or method.get("sanity", {}).get("relationship_to_parent")
        != "new_float64_remeasurement_under_parent_atol"
    ):
        raise ValueError("Sanity arithmetic drift")
    if method.get("spearman", {}).get("x") != "1-five_fold_mean_linear_cka":
        raise ValueError("Spearman source drift")
    if method.get("verification_comparison") != {
        "ordinals_shapes_dtypes_orders": "exact",
        "strings_booleans_and_null": "exact",
        "float_arrays": {"rtol": 0.0, "atol": 1e-12},
        "recursive_numeric_json_summaries": {"rtol": 0.0, "atol": 1e-12},
        "defined_spearman_rho": {"rtol": 0.0, "atol": 1e-12},
        "constant_spearman_reason_and_null": "exact",
    }:
        raise ValueError("Verification comparison drift")


def _contains_tbd(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_tbd(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_tbd(item) for item in value)
    return value == "TBD"


def _validate_outputs(config: Mapping[str, Any], kind: str) -> None:
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
    if kind == "static":
        attempt_id = config.get("attempt_id")
        if attempt_id not in {"preflight-attempt-1", "preflight-attempt-2"}:
            raise ValueError("Static output attempt drift")
        expected = {
            **common,
            "preflight_public_root": (
                "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
                f"exp-071-representation-drift/{attempt_id}"
            ),
            "preflight_private_root": (
                "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
                f"exp-071-representation-drift/{attempt_id}"
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
    if config.get("outputs") != expected:
        raise ValueError("Output contract drift")


def _validate_authorization_schema(
    config: Mapping[str, Any], kind: str, *, allow_tbd: bool
) -> None:
    value = config.get("authorization")
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
    if not isinstance(value, Mapping) or set(value) != base_keys:
        raise PermissionError("Authorization schema drift")
    if value.get("model_loading_authorized") is not False or value.get("forward_authorized") is not False:
        raise PermissionError("Model or forward authorization drift")
    if kind == "static":
        if value.get("static_runner_authorized") is not True or value.get("static_verifier_authorized") is not True:
            raise PermissionError("Static authorization missing")
        for key in base_keys - {
            "static_runner_authorized",
            "static_verifier_authorized",
            "model_loading_authorized",
            "forward_authorized",
        }:
            if value.get(key) is not False:
                raise PermissionError("Static config over-authorizes formal work")
    elif not allow_tbd:
        for key in (
            "formal_initialize_authorized",
            "formal_analyze_authorized",
            "formal_verification_authorized",
            "formal_completion_authorized",
            "representation_value_access_authorized",
            "probe_metric_value_access_authorized",
        ):
            if value.get(key) is not True:
                raise PermissionError(f"Formal authorization missing: {key}")
        if value.get("static_runner_authorized") is not False or value.get("static_verifier_authorized") is not False:
            raise PermissionError("Formal config authorizes static execution")


def _validate_access_schema(config: Mapping[str, Any], kind: str, *, allow_tbd: bool) -> None:
    value = config.get("access")
    if not isinstance(value, Mapping):
        raise PermissionError("Access contract missing")
    if kind == "static":
        if set(value) != {"static_may_read", "static_must_not_read", "formal_root_creation"}:
            raise PermissionError("Static access schema drift")
        if value.get("formal_root_creation") is not False:
            raise PermissionError("Static formal-root creation enabled")
        if set(value.get("static_must_not_read", ())) != {
            "representation_values",
            "probe_metric_values",
            "labels",
            "component_codes",
            "component_ids",
            "sample_ids",
            "private_probe_artifacts",
            "probabilities",
            "predictions",
            "train_text",
            "validation",
            "test",
            "test_gate",
        }:
            raise PermissionError("Static forbidden access drift")
    else:
        if set(value) != {
            "formal_may_read_after_activation",
            "formal_must_not_read",
            "formal_model_load",
            "formal_forward",
            "formal_source_mutation",
            "currently_authorized",
        }:
            raise PermissionError("Formal access schema drift")
        if any(
            value.get(key) is not False
            for key in ("formal_model_load", "formal_forward", "formal_source_mutation")
        ):
            raise PermissionError("Forbidden formal access enabled")
        if not allow_tbd and value.get("currently_authorized") is not True:
            raise PermissionError("Formal access is not active")


def _validate_config_exact(config: Mapping[str, Any], kind: str, *, allow_tbd: bool) -> None:
    common_keys = {
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
    extra_keys = {"preflight"} if kind == "formal" else (
        {"incident"} if config.get("attempt_id") == "preflight-attempt-2" else set()
    )
    if set(config) != common_keys | extra_keys:
        raise ValueError("Config top-level schema drift")
    if kind == "static":
        expected_identity = {
            "preflight-attempt-1": (
                "exp-071-representation-drift-preflight-config-v1",
                "exp-071-representation-drift-preflight",
                "preflight-attempt-1",
                "no-result-preflight",
            ),
            "preflight-attempt-2": (
                "exp-071-representation-drift-preflight-config-v2",
                "exp-071-representation-drift-preflight",
                "preflight-attempt-2",
                "no-result-preflight",
            ),
        }.get(config.get("attempt_id"))
        if expected_identity is None:
            raise ValueError("Static attempt identity drift")
    else:
        expected_identity = (
            "exp-071-representation-drift-formal-config-v1",
            "exp-071-representation-drift-formal",
            "formal-attempt-1",
            "formal",
        )
    if (
        config.get("schema_version") != expected_identity[0]
        or config.get("experiment_id") != EXPERIMENT_ID
        or config.get("run_id") != expected_identity[1]
        or config.get("attempt_id") != expected_identity[2]
        or config.get("stage") != expected_identity[3]
        or config.get("rq_id") != "RQ-S4.2"
        or config.get("tier") != "Major representation experiment"
        or config.get("registered_at") != "2026-08-29"
        or type(config.get("claim_boundary")) is not str
        or not config["claim_boundary"]
    ):
        raise ValueError("Config identity drift")
    claim_sha256 = bytes_sha256(config["claim_boundary"].encode("utf-8"))
    allowed_claims = {CLAIM_BOUNDARY_SHA256[kind]}
    if kind == "formal" and allow_tbd:
        allowed_claims.add(PENDING_FORMAL_CLAIM_SHA256)
    if claim_sha256 not in allowed_claims:
        raise ValueError("Claim boundary drift")
    if kind == "static":
        if config.get("attempt_id") == "preflight-attempt-1":
            if "incident" in config:
                raise ValueError("Attempt-1 cannot contain recovery metadata")
        elif config.get("incident") != INCIDENT_001:
            raise ValueError("Incident-001 metadata drift")
    if not allow_tbd and _contains_tbd(config):
        raise ValueError("Config contains an unfrozen TBD")
    if config.get("method_protocol") != METHOD_PROTOCOL_RECORD:
        raise ValueError("Method protocol identity drift")
    implementation = config.get("implementation")
    if not isinstance(implementation, Mapping) or set(implementation) != {"runner", "verifier", "tests"}:
        raise ValueError("Implementation schema drift")
    validate_implementation_paths(implementation)
    for record in implementation.values():
        if not isinstance(record, Mapping) or set(record) != {"path", "bytes", "mode", "sha256", "status"}:
            raise ValueError("Implementation record schema drift")
        if not allow_tbd and (
            record.get("status") != "Frozen"
            or type(record.get("bytes")) is not int
            or record["bytes"] <= 0
            or record.get("mode") != "0644"
            or record.get("sha256") == "TBD"
        ):
            raise ValueError("Implementation is not frozen")
    if config.get("environment") != EXPECTED_ENVIRONMENT:
        raise EnvironmentError("Environment contract drift")
    if config.get("resources") != EXPECTED_RESOURCES:
        raise ValueError("Resource contract drift")
    _validate_outputs(config, kind)
    _validate_authorization_schema(config, kind, allow_tbd=allow_tbd)
    _validate_access_schema(config, kind, allow_tbd=allow_tbd)
    source = config.get("source", {})
    if set(source) != {
        "phase_b_decision",
        "exp069_terminal",
        "exp070_extraction_terminal",
        "exp070_probe_terminal",
        "public_fold_contract",
        "matrix_root",
        "matrices",
    }:
        raise ValueError("Source schema drift")
    if bytes_sha256(canonical_json_bytes(source)) != EXPECTED_SOURCE_SHA256:
        raise ValueError("Source contract digest drift")
    if source["matrix_root"] != (
        "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
        "exp-070-layerwise-probes/formal-extraction-attempt-1/extraction"
    ):
        raise ValueError("Matrix root drift")
    if source["exp070_probe_terminal"]["probe"].get("allowed_value_paths") != list(EXPECTED_AP5_PATHS):
        raise PermissionError("Probe metric value allowlist drift")
    validate_matrix_plan(source)
    if kind == "formal":
        preflight = config.get("preflight")
        if not isinstance(preflight, Mapping) or set(preflight) != {
            "config",
            "static_run",
            "static_verification",
            "no_result_completion",
            "required_statuses",
            "formal_execution_authorized_by_preflight",
        }:
            raise ValueError("Formal preflight schema drift")
        if not allow_tbd and config["authorization"].get("activation_condition") != (
            "Passed_static_completion_exact_identities_bound"
        ):
            raise PermissionError("Formal activation condition drift")
        if not allow_tbd:
            expected_paths = {
                "config": (
                    "experiments/stack-overflow-emotion-gold/phase-b-representation/configs/"
                    "exp-071-representation-drift-preflight-attempt-2.json"
                ),
                "static_run": (
                    "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
                    "exp-071-representation-drift/preflight-attempt-2/static.json"
                ),
                "static_verification": (
                    "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
                    "exp-071-representation-drift/preflight-attempt-2/static-verification.json"
                ),
                "no_result_completion": (
                    "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
                    "exp-071-representation-drift/preflight-attempt-2/no-result-complete.json"
                ),
            }
            if (
                preflight.get("formal_execution_authorized_by_preflight") is not True
                or preflight.get("required_statuses")
                != {
                    "static_run": "CompletedAwaitingVerification",
                    "static_verification": "Passed",
                    "no_result_completion": "Complete",
                }
                or any(preflight[key].get("path") != path for key, path in expected_paths.items())
            ):
                raise ValueError("Formal Incident-001 preflight binding drift")


def load_config(path: Path, *, expected_kind: str, allow_tbd: bool = False) -> dict[str, Any]:
    config = strict_json(path)
    if not isinstance(config, dict):
        raise TypeError("EXP-071 config must be an object")
    if config.get("experiment_id") != EXPERIMENT_ID:
        raise ValueError("Experiment identity drift")
    expected_schemas = (
        {
            "exp-071-representation-drift-preflight-config-v1",
            "exp-071-representation-drift-preflight-config-v2",
        }
        if expected_kind == "static"
        else {"exp-071-representation-drift-formal-config-v1"}
    )
    expected_stage = "no-result-preflight" if expected_kind == "static" else "formal"
    if config.get("schema_version") not in expected_schemas or config.get("stage") != expected_stage:
        raise ValueError("Config kind drift")
    _validate_method(config.get("method", {}))
    _validate_config_exact(config, expected_kind, allow_tbd=allow_tbd)
    return config


def _implementation_records(config: Mapping[str, Any]) -> None:
    implementation = config.get("implementation", {})
    if set(implementation) != {"runner", "verifier", "tests"}:
        raise ValueError("Implementation inventory drift")
    validate_implementation_paths(implementation)
    paths = {name: require_record(record) for name, record in implementation.items()}
    if paths["runner"].resolve() != Path(__file__).resolve():
        raise ValueError("Runner implementation identity points elsewhere")


def validate_implementation_paths(implementation: Mapping[str, Any]) -> None:
    if set(implementation) != set(EXPECTED_IMPLEMENTATION_PATHS):
        raise ValueError("Implementation inventory drift")
    for name, expected_path in EXPECTED_IMPLEMENTATION_PATHS.items():
        record = implementation.get(name)
        if not isinstance(record, Mapping) or record.get("path") != expected_path:
            raise ValueError(f"Implementation path drift: {name}")


def _walk_artifact_records(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, Mapping):
        if {"path", "bytes", "mode", "sha256"}.issubset(value):
            yield _identity_fields(value)
            return
        for child in value.values():
            yield from _walk_artifact_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_artifact_records(child)


def source_identity_snapshot(config: Mapping[str, Any]) -> dict[str, Any]:
    roots = {
        "method_protocol": config.get("method_protocol"),
        "implementation": config.get("implementation"),
        "source": config.get("source"),
    }
    records: dict[str, dict[str, Any]] = {}
    for record in _walk_artifact_records(roots):
        path = require_record(record)
        current = artifact(path)
        previous = records.setdefault(str(current["path"]), current)
        if previous != current:
            raise ValueError("Conflicting duplicate artifact record")
    ordered = [records[key] for key in sorted(records)]
    return {
        "artifact_count": len(ordered),
        "artifacts": ordered,
        "sha256": bytes_sha256(canonical_json_bytes(ordered)),
    }


def _validate_terminal_sources(config: Mapping[str, Any]) -> None:
    source = config["source"]
    exp069 = source["exp069_terminal"]
    verification = _selected_file_scalars(
        require_record(exp069["verification"]),
        (("status",), ("passed_count",), ("failed_count",)),
    )
    completion = _selected_file_scalars(
        require_record(exp069["completion"]), (("status",), ("exp069_complete",))
    )
    if (
        verification[("status",)] != exp069["verification"]["required_status"]
        or verification[("passed_count",)] != exp069["verification"]["required_passed_count"]
        or verification[("failed_count",)] != exp069["verification"]["required_failed_count"]
        or completion[("status",)] != exp069["completion"]["required_status"]
        or completion[("exp069_complete",)] is not True
        or exp069.get("smoke_representation_values_authorized") is not False
    ):
        raise ValueError("EXP-069 terminal binding drift")

    extraction = source["exp070_extraction_terminal"]
    extraction_verification = _selected_file_scalars(
        require_record(extraction["verification"]), (("status",),)
    )
    extraction_completion = _selected_file_scalars(
        require_record(extraction["completion"]),
        (("status",), ("formal_extraction_complete",)),
    )
    if (
        extraction_verification[("status",)] != extraction["verification"]["required_status"]
        or extraction_completion[("status",)] != extraction["completion"]["required_status"]
        or extraction_completion[("formal_extraction_complete",)] is not True
    ):
        raise ValueError("EXP-070 extraction terminal binding drift")

    probe = source["exp070_probe_terminal"]
    if probe.get("probe", {}).get("allowed_value_paths") != list(EXPECTED_AP5_PATHS):
        raise PermissionError("Probe metric value allowlist drift")
    probe_verification = _selected_file_scalars(
        require_record(probe["verification"]),
        (("status",), ("passed_count",), ("failed_count",), ("results_sha256",)),
    )
    probe_completion = _selected_file_scalars(
        require_record(probe["completion"]),
        (("status",), ("exp070_complete",), ("exp071_authorized",)),
    )
    if (
        probe_verification[("status",)] != probe["verification"]["required_status"]
        or probe_verification[("passed_count",)] != probe["verification"]["required_passed_count"]
        or probe_verification[("failed_count",)] != probe["verification"]["required_failed_count"]
        or probe_verification[("results_sha256",)] != probe["verified_results_sha256"]
        or probe_completion[("status",)] != probe["completion"]["required_status"]
        or probe_completion[("exp070_complete",)] is not True
        or probe_completion[("exp071_authorized",)] is not False
        or probe.get("private_probe_artifact_access") is not False
    ):
        raise ValueError("EXP-070 probe terminal binding drift")

    fold_contract = source["public_fold_contract"]
    fold_verification = _selected_file_scalars(
        require_record(fold_contract["verification"]), (("status",),)
    )
    if (
        fold_verification[("status",)] != fold_contract["verification"]["required_status"]
        or fold_contract.get("formal_parse_authorized") is not False
    ):
        raise ValueError("Public fold provenance drift")


def _validate_incident_evidence(config: Mapping[str, Any]) -> None:
    if config.get("attempt_id") != "preflight-attempt-2":
        return
    incident = config.get("incident")
    if incident != INCIDENT_001:
        raise ValueError("Incident-001 metadata drift")
    require_record(incident["failed_config"])
    failure_path = require_record(incident["failure_artifact"])
    fields = _selected_file_scalars(
        failure_path,
        (
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
        ),
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
    if fields != expected:
        raise ValueError("Incident-001 failure evidence drift")


def _matrix_headers(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    validate_matrix_plan(config["source"])
    matrices = config["source"]["matrices"]
    if len(matrices) != 16:
        raise ValueError("Matrix count drift")
    expected_workers = ["base"] + [
        f"m3-s{seed}-f{fold}" for seed in (42, 43, 44) for fold in FOLDS
    ]
    if [item.get("worker_id") for item in matrices] != expected_workers:
        raise ValueError("Matrix worker order drift")
    for record in matrices:
        path = require_record(record["artifact"])
        header = read_npy_header(path)
        if (
            header["shape"] != record["shape"]
            or header["descr"] not in {"<f4", "|f4", "=f4"}
            or header["fortran_order"] is not False
            or header["file_bytes"] != record["artifact"]["bytes"]
        ):
            raise ValueError("Matrix header drift")
        result.append(
            {
                "worker_id": record["worker_id"],
                "shape": header["shape"],
                "descr": "<f4",
                "fortran_order": False,
                "data_offset": header["data_offset"],
                "file_bytes": header["file_bytes"],
                "points": record["points"],
            }
        )
    return result


def _row_contract_headers(config: Mapping[str, Any]) -> dict[str, Any]:
    record = config["source"]["exp070_extraction_terminal"]["row_contract"]
    path = require_record(record)
    headers = read_npz_headers(path)
    if headers["member_order"] != ["ordinal", "fold_id", "component_code"]:
        raise ValueError("Row-contract member order drift")
    expected = {
        "ordinal": ([ROWS], {"<i4", "=i4", "|i4"}),
        "fold_id": ([ROWS], {"|i1", "<i1", "=i1"}),
        "component_code": ([ROWS], {"<i4", "=i4", "|i4"}),
    }
    for name, (shape, descriptions) in expected.items():
        header = headers["members"][name]
        if header["shape"] != shape or header["descr"] not in descriptions or header["fortran_order"]:
            raise ValueError("Row-contract header drift")
    return headers


def _environment_record(config: Mapping[str, Any], *, check_process: bool) -> dict[str, Any]:
    expected = config["environment"]
    observed = {
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "packages": {"numpy": importlib.metadata.version("numpy")},
        "thread_environment": {
            key: os.environ.get(key) for key in expected["thread_environment"]
        },
    }
    normalized_expected = dict(expected)
    normalized_expected["python_executable"] = str(Path(expected["python_executable"]).resolve())
    if check_process and observed != normalized_expected:
        raise RuntimeError("Frozen EXP-071 environment drift")
    return observed


def _require_static_import_boundary() -> None:
    for name in STATIC_NUMERIC_MODULES + FORBIDDEN_MODEL_MODULES:
        if name in sys.modules or any(key.startswith(name + ".") for key in sys.modules):
            raise RuntimeError("Static stage numeric/model import boundary violated")


def run_synthetic_tests(config: Mapping[str, Any]) -> dict[str, Any]:
    test_path = require_record(config["implementation"]["tests"])
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
    matches = re.findall(r"Ran\s+(\d+)\s+tests?", completed.stdout + "\n" + completed.stderr)
    if completed.returncode != 0 or not matches:
        raise RuntimeError("EXP-071 synthetic suite failed")
    return {
        "status": "Passed",
        "tests_run": int(matches[-1]),
        "test_artifact": artifact(test_path),
        "command_sha256": bytes_sha256(canonical_json_bytes(command)),
    }


def _public_root(config: Mapping[str, Any], *, static: bool) -> Path:
    key = "preflight_public_root" if static else "formal_public_root"
    return resolve_project(config["outputs"][key], must_exist=False)


def _private_root(config: Mapping[str, Any], *, static: bool) -> Path:
    key = "preflight_private_root" if static else "formal_private_root"
    return resolve_project(config["outputs"][key], must_exist=False)


def _private_size(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        if path.is_symlink():
            raise PermissionError("Private symlink rejected")
        if path.is_file():
            total += path.stat().st_size
        elif not path.is_dir():
            raise PermissionError("Private special entry rejected")
    return total


def _peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # Darwin reports bytes; Linux reports KiB.
    return value if sys.platform == "darwin" else value * 1024


def _require_private_ignore() -> None:
    path = MODULE_DIR / ".gitignore"
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise PermissionError("Privacy ignore file missing")
    rules = {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
    if "private/" not in rules:
        raise PermissionError("Private output is not ignored")


def public_privacy_ok(value: Any) -> bool:
    forbidden_keys = {
        "ordinal",
        "ordinals",
        "heldout_ordinals",
        "representation",
        "representations",
        "labels",
        "probabilities",
        "predictions",
        "sample_id",
        "sample_ids",
        "component_id",
        "component_ids",
        "component_code",
        "component_codes",
        "rowwise_values",
        "raw_text",
        "text",
        "private_path",
    }
    if isinstance(value, Mapping):
        if set(value) & forbidden_keys:
            return False
        return all(public_privacy_ok(child) for child in value.values())
    if isinstance(value, list):
        if len(value) >= HELDOUT_PER_FOLD:
            return False
        return all(public_privacy_ok(child) for child in value)
    return True


def validate_public_payload(value: Any) -> None:
    if not public_privacy_ok(value):
        raise PermissionError("Public row-level or private-path leakage")


def _static_authorization(config: Mapping[str, Any]) -> None:
    expected = {
        "static_runner_authorized": True,
        "static_verifier_authorized": True,
        "formal_initialize_authorized": False,
        "formal_analyze_authorized": False,
        "formal_verification_authorized": False,
        "formal_completion_authorized": False,
        "representation_value_access_authorized": False,
        "probe_metric_value_access_authorized": False,
        "model_loading_authorized": False,
        "forward_authorized": False,
    }
    if config.get("authorization") != expected:
        raise PermissionError("Static authorization drift")
    if config.get("access", {}).get("formal_root_creation") is not False:
        raise PermissionError("Static formal-root authorization drift")


def _formal_authorization(config: Mapping[str, Any]) -> None:
    authorization = config.get("authorization", {})
    for key in (
        "formal_initialize_authorized",
        "formal_analyze_authorized",
        "formal_verification_authorized",
        "formal_completion_authorized",
        "representation_value_access_authorized",
        "probe_metric_value_access_authorized",
    ):
        if authorization.get(key) is not True:
            raise PermissionError(f"Formal authorization missing: {key}")
    for key in (
        "static_runner_authorized",
        "static_verifier_authorized",
        "model_loading_authorized",
        "forward_authorized",
    ):
        if authorization.get(key) is not False:
            raise PermissionError(f"Formal authorization drift: {key}")
    if config.get("access", {}).get("currently_authorized") is not True:
        raise PermissionError("Formal access contract is not active")
    if config.get("preflight", {}).get("formal_execution_authorized_by_preflight") is not True:
        raise PermissionError("Preflight did not authorize formal execution")


def _preflight_completion(config: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    preflight = config["preflight"]
    if preflight.get("formal_execution_authorized_by_preflight") is not True:
        raise PermissionError("Preflight has not authorized formal execution")
    if preflight.get("required_statuses") != {
        "static_run": "CompletedAwaitingVerification",
        "static_verification": "Passed",
        "no_result_completion": "Complete",
    }:
        raise ValueError("Preflight required-status contract drift")
    paths = {
        key: require_record(preflight[key])
        for key in ("config", "static_run", "static_verification", "no_result_completion")
    }
    expected_preflight_paths = {
        "config": DEFAULT_STATIC_CONFIG.resolve(),
        "static_run": resolve_project(
            "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
            "exp-071-representation-drift/preflight-attempt-2/static.json"
        ),
        "static_verification": resolve_project(
            "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
            "exp-071-representation-drift/preflight-attempt-2/static-verification.json"
        ),
        "no_result_completion": resolve_project(
            "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
            "exp-071-representation-drift/preflight-attempt-2/no-result-complete.json"
        ),
    }
    if any(paths[key].resolve() != expected_preflight_paths[key] for key in paths):
        raise ValueError("Formal preflight must bind Incident-001 attempt-2")
    static_config = load_config(paths["config"], expected_kind="static")
    if (
        static_config.get("schema_version") != "exp-071-representation-drift-preflight-config-v2"
        or static_config.get("attempt_id") != "preflight-attempt-2"
    ):
        raise ValueError("Formal preflight recovery-attempt identity drift")
    _validate_incident_evidence(static_config)
    validate_static_formal_contracts(static_config, config)
    run = strict_json(paths["static_run"])
    verification = strict_json(paths["static_verification"])
    completion = strict_json(paths["no_result_completion"])
    run_record = artifact(paths["static_run"])
    verification_record = artifact(paths["static_verification"])
    completion_record = artifact(paths["no_result_completion"])
    validate_preflight_payloads(
        preflight,
        static_config,
        run,
        verification,
        completion,
        run_record,
        verification_record,
        completion_record,
    )
    public = _public_root(static_config, static=True)
    private = _private_root(static_config, static=True)
    require_exact_inventory(
        public,
        static_config["outputs"]["public_success_allowlist"],
        private=False,
    )
    require_exact_inventory(
        private,
        static_config["outputs"]["private_success_allowlist"],
        private=True,
    )
    return static_config, completion


def validate_preflight_payloads(
    preflight: Mapping[str, Any],
    static_config: Mapping[str, Any],
    run: Mapping[str, Any],
    verification: Mapping[str, Any],
    completion: Mapping[str, Any],
    run_record: Mapping[str, Any],
    verification_record: Mapping[str, Any],
    completion_record: Mapping[str, Any],
) -> None:
    if preflight.get("formal_execution_authorized_by_preflight") is not True:
        raise PermissionError("Preflight has not authorized formal execution")
    if preflight.get("required_statuses") != {
        "static_run": "CompletedAwaitingVerification",
        "static_verification": "Passed",
        "no_result_completion": "Complete",
    }:
        raise ValueError("Preflight required-status contract drift")
    if (
        preflight["static_run"] != run_record
        or preflight["static_verification"] != verification_record
        or preflight["no_result_completion"] != completion_record
        or run.get("status") != "CompletedAwaitingVerification"
        or run.get("method_sha256") != METHOD_SHA256
        or verification.get("status") != "Passed"
        or type(verification.get("passed_count")) is not int
        or verification["passed_count"] < 1
        or verification.get("failed_count") != 0
        or verification.get("run") != run_record
        or verification.get("method_sha256") != METHOD_SHA256
        or verification.get("source_snapshot_sha256") != run.get("source_snapshot_sha256")
        or verification.get("representation_values_read") is not False
        or verification.get("probe_metric_values_read") is not False
        or verification.get("formal_root_created") is not False
        or verification.get("formal_execution_authorized") is not False
        or completion.get("status") != "Complete"
        or completion.get("run") != run_record
        or completion.get("verification") != verification_record
        or completion.get("input_contract") != verification.get("input_contract")
        or completion.get("method_sha256") != METHOD_SHA256
        or completion.get("source_snapshot_sha256") != run.get("source_snapshot_sha256")
        or completion.get("representation_values_read") is not False
        or completion.get("probe_metric_values_read") is not False
        or completion.get("formal_execution_authorized") is not True
        or completion.get("exp071_complete") is not False
        or completion.get("exp072_authorized") is not False
        or completion.get("claim_boundary") != static_config["claim_boundary"]
    ):
        raise ValueError("Preflight completion drift")


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
            raise ValueError(f"Static/formal {key} drift")
    static_outputs = static_config.get("outputs", {})
    formal_outputs = formal_config.get("outputs", {})
    for key in (
        "formal_public_root",
        "formal_private_root",
        "public_directory_mode",
        "public_file_mode",
        "private_directory_mode",
        "private_file_mode",
    ):
        if static_outputs.get(key) != formal_outputs.get(key):
            raise ValueError(f"Static/formal output drift: {key}")
    if (
        static_outputs.get("formal_roots_must_be_absent") is not True
        or formal_outputs.get("formal_roots_must_be_fresh") is not True
    ):
        raise ValueError("Static/formal root-freshness drift")


def validate_matrix_plan(source: Mapping[str, Any]) -> None:
    matrices = source.get("matrices")
    if not isinstance(matrices, list) or len(matrices) != 16:
        raise ValueError("Matrix count drift")
    expected: list[dict[str, Any]] = [
        {
            "worker_id": "base",
            "kind": "frozen",
            "seed": None,
            "fold": None,
            "shape": [ROWS, len(ALL_POINTS), HIDDEN_SIZE],
            "points": list(ALL_POINTS),
        }
    ]
    for seed in (42, 43, 44):
        points = ALL_POINTS if seed == 42 else CONFIRMATION_POINTS
        for fold in FOLDS:
            expected.append(
                {
                    "worker_id": f"m3-s{seed}-f{fold}",
                    "kind": "m3",
                    "seed": seed,
                    "fold": fold,
                    "shape": [ROWS, len(points), HIDDEN_SIZE],
                    "points": list(points),
                }
            )
    for observed, plan in zip(matrices, expected, strict=True):
        if not isinstance(observed, Mapping):
            raise ValueError("Matrix record type drift")
        if {key: observed.get(key) for key in plan} != plan:
            raise ValueError(f"Matrix plan drift: {plan['worker_id']}")
        artifact_record = _identity_fields(observed.get("artifact", {}))
        expected_path = f"{source['matrix_root']}/{plan['worker_id']}/representations.npy"
        if artifact_record["path"] != expected_path or artifact_record["mode"] != "0600":
            raise ValueError(f"Matrix artifact path or mode drift: {plan['worker_id']}")


def static_stage(config_path: Path = DEFAULT_STATIC_CONFIG) -> dict[str, Any]:
    config_path = Path(config_path).resolve()
    started = time.monotonic()
    _require_static_import_boundary()
    config = load_config(config_path, expected_kind="static")
    _implementation_records(config)
    _static_authorization(config)
    _require_private_ignore()
    _environment_record(config, check_process=True)
    public = _public_root(config, static=True)
    private = _private_root(config, static=True)
    formal_public = _public_root(config, static=False)
    formal_private = _private_root(config, static=False)
    for path in (public, private, formal_public, formal_private):
        if os.path.lexists(path):
            raise FileExistsError(f"EXP-071 output root exists: {path}")

    before = source_identity_snapshot(config)
    _validate_incident_evidence(config)
    _validate_terminal_sources(config)
    matrix_headers = _matrix_headers(config)
    row_headers = _row_contract_headers(config)
    synthetic_tests = run_synthetic_tests(config)
    _validate_incident_evidence(config)
    after = source_identity_snapshot(config)
    if after != before:
        raise ValueError("Source snapshot changed during static gate")

    elapsed = time.monotonic() - started
    resources = {
        "elapsed_seconds": elapsed,
        "peak_rss_bytes": _peak_rss_bytes(),
        "source_artifact_count": before["artifact_count"],
        "api_cost_usd": 0,
    }
    if elapsed > float(config["resources"]["runner_wall_seconds"]):
        raise RuntimeError("Static wall-time ceiling exceeded")
    if resources["peak_rss_bytes"] > int(config["resources"]["peak_rss_bytes"]):
        raise RuntimeError("Static RSS ceiling exceeded")

    _create_root(private, private=True)
    _create_root(public, private=False)
    input_contract = {
        "schema_version": "exp-071-drift-static-input-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "status": "Sealed",
        "config": artifact(config_path),
        "method_sha256": method_sha256(config),
        "source_snapshot_sha256": before["sha256"],
        "source_artifact_count": before["artifact_count"],
        "matrix_headers": matrix_headers,
        "row_contract_headers": row_headers,
        "environment": _environment_record(config, check_process=False),
        "synthetic_tests": synthetic_tests,
        "formal_roots_absent": True,
        "access": STATIC_ACCESS,
    }
    input_path = private / "input-contract-manifest.json"
    create_json_once(input_path, input_contract, private=True)
    report = {
        "schema_version": "exp-071-drift-static-run-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "stage": "static",
        "status": "CompletedAwaitingVerification",
        "config": artifact(config_path),
        "input_manifest": logical_artifact(input_path, "input-contract-manifest.json"),
        "method_sha256": method_sha256(config),
        "source_snapshot_sha256": before["sha256"],
        "counts": {
            "source_artifacts": before["artifact_count"],
            "representation_matrices": 16,
            "conditions": 15,
            "folds": 5,
            "scientific_comparisons": 0,
        },
        "environment": _environment_record(config, check_process=False),
        "synthetic_tests": synthetic_tests,
        "resources": resources,
        "access": STATIC_ACCESS,
        "formal_execution_authorized": False,
        "exp071_complete": False,
        "exp072_authorized": False,
        "claim_boundary": config["claim_boundary"],
    }
    validate_public_payload(report)
    create_json_once(public / "static.json", report)
    require_exact_inventory(
        public,
        ["static.json"],
        private=False,
    )
    require_exact_inventory(
        private,
        ["input-contract-manifest.json"],
        private=True,
    )
    return report


def initialize_stage(config_path: Path = DEFAULT_FORMAL_CONFIG) -> dict[str, Any]:
    config_path = Path(config_path).resolve()
    config = load_config(config_path, expected_kind="formal")
    _implementation_records(config)
    _formal_authorization(config)
    static_config, completion = _preflight_completion(config)
    _require_private_ignore()
    _environment_record(config, check_process=True)
    # Existing lockfiles are persistent coordination inodes, not evidence that
    # a process currently owns them.
    with analysis_lock():
        pass
    public = _public_root(config, static=False)
    private = _private_root(config, static=False)
    for path in (public, private):
        if os.path.lexists(path):
            raise FileExistsError(f"Formal EXP-071 root exists: {path}")
    if shutil.disk_usage(PROJECT_ROOT).free < int(config["resources"]["minimum_free_disk_bytes"]):
        raise OSError("EXP-071 free-disk gate failed")
    before = source_identity_snapshot(config)
    if before["sha256"] != completion.get("source_snapshot_sha256"):
        raise ValueError("Formal source snapshot does not replay sealed static source")
    _validate_terminal_sources(config)
    matrix_headers = _matrix_headers(config)
    row_headers = _row_contract_headers(config)
    after = source_identity_snapshot(config)
    if before != after:
        raise ValueError("Source snapshot changed during initialization")

    _create_root(private, private=True)
    _create_root(public, private=False)
    input_manifest = {
        "schema_version": "exp-071-drift-input-manifest-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "status": "Initialized",
        "config": artifact(config_path),
        "preflight": config["preflight"],
        "method_sha256": method_sha256(config),
        "source_snapshot_sha256": before["sha256"],
        "source_artifact_count": before["artifact_count"],
        "matrix_headers": matrix_headers,
        "row_contract_headers": row_headers,
        "access": {**INITIALIZE_ACCESS, "source_mutated": False},
    }
    input_path = private / "input-manifest.json"
    create_json_once(input_path, input_manifest, private=True)
    claim = {
        "schema_version": "exp-071-drift-run-claim-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": config["run_id"],
        "attempt_id": config["attempt_id"],
        "stage": "initialize",
        "status": "Initialized",
        "config": artifact(config_path),
        "preflight_completion": config["preflight"]["no_result_completion"],
        "input_manifest": logical_artifact(input_path, "input-manifest.json"),
        "method_sha256": method_sha256(config),
        "counts": {"rows": 3360, "folds": 5, "conditions": 15, "comparisons": 75},
        "authorization": {
            "formal_analysis": True,
            "representation_value_access": True,
            "probe_metric_value_access": True,
            "model_loading": False,
            "forward": False,
            "validation": False,
            "test": False,
        },
        "access": {**INITIALIZE_ACCESS, "source_mutated": False},
        "claim_boundary": config["claim_boundary"],
    }
    validate_public_payload(claim)
    create_json_once(public / "run-claim.json", claim)
    require_exact_inventory(public, ["run-claim.json"], private=False)
    require_exact_inventory(private, ["input-manifest.json"], private=True)
    return claim


def distance_statistics(values: Any) -> dict[str, float]:
    import numpy as np

    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError("Invalid distance vector")
    percentiles = np.percentile(array, [50.0, 90.0, 95.0], method="linear")
    return {
        "mean": float(np.mean(array, dtype=np.float64)),
        "median": float(percentiles[0]),
        "p90": float(percentiles[1]),
        "p95": float(percentiles[2]),
    }


def compute_geometry_pair(x: Any, z: Any) -> tuple[Any, Any, float, float]:
    import numpy as np

    frozen = np.ascontiguousarray(x, dtype=np.float64)
    adapted = np.ascontiguousarray(z, dtype=np.float64)
    if frozen.ndim != 2 or adapted.shape != frozen.shape or frozen.shape[0] < 2:
        raise ValueError("Geometry pair shape drift")
    if not np.all(np.isfinite(frozen)) or not np.all(np.isfinite(adapted)):
        raise ValueError("Non-finite representation value")
    frozen_norm = np.linalg.norm(frozen, axis=1)
    adapted_norm = np.linalg.norm(adapted, axis=1)
    if (
        not np.all(np.isfinite(frozen_norm))
        or not np.all(np.isfinite(adapted_norm))
        or np.any(frozen_norm == 0.0)
        or np.any(adapted_norm == 0.0)
    ):
        raise ValueError("Zero or non-finite row norm")
    raw_cosine = np.einsum("ij,ij->i", frozen, adapted) / (frozen_norm * adapted_norm)
    if (
        not np.all(np.isfinite(raw_cosine))
        or np.any(raw_cosine < -1.0 - NUMERIC_TOLERANCE)
        or np.any(raw_cosine > 1.0 + NUMERIC_TOLERANCE)
    ):
        raise ValueError("Cosine numeric-range violation")
    cosine = 1.0 - np.clip(raw_cosine, -1.0, 1.0)
    relative = np.linalg.norm(adapted - frozen, axis=1) / frozen_norm
    if not np.all(np.isfinite(relative)):
        raise ValueError("Non-finite relative L2")

    centered_frozen = frozen - np.mean(frozen, axis=0, dtype=np.float64)
    centered_adapted = adapted - np.mean(adapted, axis=0, dtype=np.float64)
    gram_frozen = centered_frozen @ centered_frozen.T
    gram_adapted = centered_adapted @ centered_adapted.T
    norm_frozen = float(np.sum(gram_frozen * gram_frozen, dtype=np.float64))
    norm_adapted = float(np.sum(gram_adapted * gram_adapted, dtype=np.float64))
    denominator = float(np.sqrt(norm_frozen * norm_adapted))
    if not all(map(lambda value: value > 0.0 and value < float("inf"), (norm_frozen, norm_adapted, denominator))):
        raise ValueError("Zero or non-finite CKA denominator")
    raw_cka = float(np.sum(gram_frozen * gram_adapted, dtype=np.float64) / denominator)
    if (
        not np.isfinite(raw_cka)
        or raw_cka < -NUMERIC_TOLERANCE
        or raw_cka > 1.0 + NUMERIC_TOLERANCE
    ):
        raise ValueError("CKA numeric-range violation")
    cka = float(np.clip(raw_cka, 0.0, 1.0))
    maximum = float(np.max(np.abs(adapted - frozen)))
    if not np.isfinite(maximum):
        raise ValueError("Non-finite maximum difference")
    return (
        np.ascontiguousarray(cosine, dtype="<f8"),
        np.ascontiguousarray(relative, dtype="<f8"),
        cka,
        maximum,
    )


def average_ranks(values: Any) -> Any:
    import numpy as np

    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError("Invalid rank vector")
    order = np.argsort(array, kind="mergesort")
    ranks = np.empty(array.size, dtype=np.float64)
    start = 0
    while start < array.size:
        stop = start + 1
        while stop < array.size and array[order[stop]] == array[order[start]]:
            stop += 1
        ranks[order[start:stop]] = (start + stop - 1) / 2.0 + 1.0
        start = stop
    return ranks


def spearman_description(x: Any, y: Any) -> dict[str, Any]:
    import numpy as np

    x_rank = average_ranks(x)
    y_rank = average_ranks(y)
    if x_rank.shape != y_rank.shape:
        raise ValueError("Spearman vector shape drift")
    x_centered = x_rank - np.mean(x_rank, dtype=np.float64)
    y_centered = y_rank - np.mean(y_rank, dtype=np.float64)
    denominator = float(np.linalg.norm(x_centered) * np.linalg.norm(y_centered))
    if denominator == 0.0:
        return {"rho": None, "reason": "constant_vector"}
    rho = float(np.dot(x_centered, y_centered) / denominator)
    if not np.isfinite(rho) or rho < -1.0 - NUMERIC_TOLERANCE or rho > 1.0 + NUMERIC_TOLERANCE:
        raise ValueError("Spearman numeric-range violation")
    return {"rho": float(np.clip(rho, -1.0, 1.0)), "reason": None}


def heldout_partitions(ordinals: Any, fold_ids: Any, *, folds: Sequence[int] = FOLDS) -> list[Any]:
    import numpy as np

    ordinal_array = np.asarray(ordinals)
    fold_array = np.asarray(fold_ids)
    if ordinal_array.ndim != 1 or fold_array.shape != ordinal_array.shape:
        raise ValueError("Row-contract shape drift")
    if len(np.unique(ordinal_array)) != ordinal_array.size:
        raise ValueError("Duplicate row ordinal")
    result = []
    expected_count = ordinal_array.size // len(folds)
    for fold in folds:
        selected = np.sort(ordinal_array[fold_array == fold]).astype("<i4", copy=False)
        if selected.size != expected_count:
            raise ValueError("Fold size drift")
        result.append(np.ascontiguousarray(selected, dtype="<i4"))
    if sum(item.size for item in result) != ordinal_array.size:
        raise ValueError("Fold coverage drift")
    return result


PairLoader = Callable[[str, int, Any], tuple[Any, Any]]


def compute_geometry_bundle(
    partitions: Sequence[Any],
    pair_loader: PairLoader,
    *,
    condition_order: Sequence[str] = CONDITION_ORDER,
    sanity_conditions: frozenset[str] = SANITY_CONDITIONS,
    sanity_tolerance: float = SANITY_TOLERANCE,
) -> dict[str, Any]:
    import numpy as np

    if len(partitions) == 0:
        raise ValueError("No heldout partitions")
    fold_size = int(np.asarray(partitions[0]).size)
    if fold_size == 0 or any(np.asarray(item).shape != (fold_size,) for item in partitions):
        raise ValueError("Heldout partition shape drift")
    condition_count = len(condition_order)
    fold_count = len(partitions)
    heldout = np.stack([np.asarray(item, dtype="<i4") for item in partitions])
    cosine = np.empty((condition_count, fold_count * fold_size), dtype="<f8")
    relative = np.empty_like(cosine)
    cka = np.empty((condition_count, fold_count), dtype="<f8")
    maximum = np.empty_like(cka)
    for condition_index, condition in enumerate(condition_order):
        for fold_index, ordinals in enumerate(partitions):
            frozen, adapted = pair_loader(condition, fold_index, ordinals)
            current_cosine, current_relative, current_cka, current_maximum = compute_geometry_pair(
                frozen, adapted
            )
            if current_cosine.shape != (fold_size,) or current_relative.shape != (fold_size,):
                raise ValueError("Geometry vector length drift")
            start = fold_index * fold_size
            stop = start + fold_size
            cosine[condition_index, start:stop] = current_cosine
            relative[condition_index, start:stop] = current_relative
            cka[condition_index, fold_index] = current_cka
            maximum[condition_index, fold_index] = current_maximum
            if condition in sanity_conditions and current_maximum > sanity_tolerance:
                raise SanityGateError(f"Pre-LoRA parity failure: {condition}, fold {fold_index}")
    arrays = {
        "heldout_ordinals": np.ascontiguousarray(heldout, dtype="<i4"),
        "cosine_distance": np.ascontiguousarray(cosine, dtype="<f8"),
        "relative_l2_distance": np.ascontiguousarray(relative, dtype="<f8"),
        "linear_cka": np.ascontiguousarray(cka, dtype="<f8"),
        "max_abs_difference": np.ascontiguousarray(maximum, dtype="<f8"),
    }
    if not all(np.all(np.isfinite(value)) for value in arrays.values()):
        raise ValueError("Non-finite geometry bundle")
    return arrays


def build_results(
    arrays: Mapping[str, Any],
    ap5_deltas: Sequence[float],
    *,
    condition_order: Sequence[str] = CONDITION_ORDER,
    fold_order: Sequence[int] = FOLDS,
    sanity_conditions: frozenset[str] = SANITY_CONDITIONS,
) -> dict[str, Any]:
    import numpy as np

    cosine = np.asarray(arrays["cosine_distance"], dtype=np.float64)
    relative = np.asarray(arrays["relative_l2_distance"], dtype=np.float64)
    cka = np.asarray(arrays["linear_cka"], dtype=np.float64)
    maximum = np.asarray(arrays["max_abs_difference"], dtype=np.float64)
    fold_count = len(fold_order)
    condition_count = len(condition_order)
    if (
        cosine.shape[0] != condition_count
        or relative.shape != cosine.shape
        or cosine.shape[1] % fold_count
        or cka.shape != (condition_count, fold_count)
        or maximum.shape != cka.shape
    ):
        raise ValueError("Result bundle shape drift")
    fold_size = cosine.shape[1] // fold_count
    conditions: dict[str, Any] = {}
    sanity: dict[str, Any] = {}
    for index, condition in enumerate(condition_order):
        per_fold = []
        for fold_index, fold in enumerate(fold_order):
            start = fold_index * fold_size
            stop = start + fold_size
            per_fold.append(
                {
                    "fold": int(fold),
                    "cosine_distance": distance_statistics(cosine[index, start:stop]),
                    "relative_l2_distance": distance_statistics(relative[index, start:stop]),
                }
            )
        applies = condition in sanity_conditions
        maximum_value = float(np.max(maximum[index]))
        gate_passed: bool | None = maximum_value <= SANITY_TOLERANCE if applies else None
        conditions[condition] = {
            "per_fold_distance_statistics": per_fold,
            "pooled_distance_statistics": {
                "cosine_distance": distance_statistics(cosine[index]),
                "relative_l2_distance": distance_statistics(relative[index]),
            },
            "linear_cka": {
                "per_fold": [float(value) for value in cka[index]],
                "mean": float(np.mean(cka[index], dtype=np.float64)),
                "sample_sd": float(np.std(cka[index], ddof=1, dtype=np.float64)),
            },
            "max_abs_difference": {
                "per_fold": [float(value) for value in maximum[index]],
                "maximum": maximum_value,
                "sanity_gate_applies": applies,
                "sanity_gate_passed": gate_passed,
            },
        }
        if applies:
            sanity[condition] = {
                "per_fold": [float(value) for value in maximum[index]],
                "maximum": maximum_value,
                "passed": bool(gate_passed),
            }
    if len(ap5_deltas) != len(ALL_POINTS) or not np.all(np.isfinite(ap5_deltas)):
        raise ValueError("AP5 delta vector drift")
    seed42_cka_drift = 1.0 - np.mean(cka[: len(ALL_POINTS)], axis=1, dtype=np.float64)
    correlation = spearman_description(seed42_cka_drift, ap5_deltas)
    return {
        "condition_order": list(condition_order),
        "conditions": conditions,
        "pre_lora_sanity": {
            "tolerance": SANITY_TOLERANCE,
            "conditions": sanity,
            "passed": all(item["passed"] for item in sanity.values()),
        },
        "seed42_spearman": {
            "point_order": list(ALL_POINTS),
            "x": "1-five_fold_mean_linear_cka",
            "y": "verified_exp070_main_delta_five_label_macro_ap",
            "n": len(ALL_POINTS),
            **correlation,
        },
    }


def _array_digest(value: Any) -> str:
    import numpy as np

    return bytes_sha256(np.ascontiguousarray(value).tobytes(order="C"))


def _load_row_contract(config: Mapping[str, Any]) -> tuple[Any, Any]:
    import numpy as np

    record = config["source"]["exp070_extraction_terminal"]["row_contract"]
    path = require_record(record)
    with np.load(path, allow_pickle=False) as archive:
        if archive.files != ["ordinal", "fold_id", "component_code"]:
            raise ValueError("Row-contract member drift")
        # Deliberately never index archive["component_code"].
        ordinal = np.ascontiguousarray(archive["ordinal"], dtype="<i4")
        fold_id = np.ascontiguousarray(archive["fold_id"], dtype=np.int8)
    if ordinal.shape != (ROWS,) or fold_id.shape != (ROWS,):
        raise ValueError("Row-contract value shape drift")
    identity = config["source"]["exp070_extraction_terminal"]["row_identity"]
    if (
        _array_digest(ordinal) != identity["ordinal_sha256"]
        or _array_digest(fold_id) != identity["fold_id_order_sha256"]
        or not np.array_equal(ordinal, np.arange(ROWS, dtype=np.int32))
        or set(np.unique(fold_id).tolist()) != set(FOLDS)
    ):
        raise ValueError("Row-contract identity drift")
    return ordinal, fold_id


def _open_matrices(config: Mapping[str, Any]) -> dict[str, tuple[Any, tuple[str, ...]]]:
    import numpy as np

    opened: dict[str, tuple[Any, tuple[str, ...]]] = {}
    for record in config["source"]["matrices"]:
        path = require_record(record["artifact"])
        value = np.load(path, mmap_mode="r", allow_pickle=False)
        if (
            not isinstance(value, np.memmap)
            or value.flags.writeable
            or value.dtype != np.float32
            or list(value.shape) != record["shape"]
            or value.flags.f_contiguous
            or not value.flags.c_contiguous
        ):
            raise ValueError("Representation mapping contract drift")
        value.setflags(write=False)
        opened[record["worker_id"]] = (value, tuple(record["points"]))
    if len(opened) != 16:
        raise ValueError("Representation mapping count drift")
    return opened


def _formal_pair_loader(opened: Mapping[str, tuple[Any, tuple[str, ...]]]) -> PairLoader:
    import numpy as np

    base, base_points = opened["base"]

    def load(condition: str, fold_index: int, ordinals: Any) -> tuple[Any, Any]:
        seed_text, point = condition.split(":", 1)
        seed = int(seed_text[1:])
        worker = f"m3-s{seed}-f{fold_index}"
        adapted, adapted_points = opened[worker]
        base_index = base_points.index(point)
        adapted_index = adapted_points.index(point)
        selected = np.asarray(ordinals, dtype=np.int32)
        frozen_slice = np.ascontiguousarray(base[selected, base_index, :], dtype=np.float64)
        adapted_slice = np.ascontiguousarray(adapted[selected, adapted_index, :], dtype=np.float64)
        if frozen_slice.shape != (selected.size, HIDDEN_SIZE) or adapted_slice.shape != frozen_slice.shape:
            raise ValueError("Heldout slice shape drift")
        return frozen_slice, adapted_slice

    return load


def _load_ap5_deltas(config: Mapping[str, Any]) -> tuple[list[float], dict[str, Any]]:
    import numpy as np

    source = config["source"]["exp070_probe_terminal"]
    probe_path = require_record(source["probe"])
    allowed_strings = source["probe"]["allowed_value_paths"]
    if allowed_strings != list(EXPECTED_AP5_PATHS):
        raise PermissionError("Probe metric value allowlist drift")
    allowed_paths = [tuple(value.split(".")) for value in allowed_strings]
    selected, captures = selective_json_scalars(
        probe_path.read_bytes(),
        allowed_paths,
        capture_paths=(("results",),),
    )
    if bytes_sha256(captures[("results",)] + b"\n") != source["verified_results_sha256"]:
        raise ValueError("Verified probe results digest drift")
    values: list[float] = []
    for path in allowed_paths:
        value = selected[path]
        if type(value) not in {int, float} or not np.isfinite(value):
            raise ValueError("AP5 delta value drift")
        values.append(float(value))
    return values, {
        "probe": artifact(probe_path),
        "verified_results_sha256": source["verified_results_sha256"],
        "ap5_delta_sha256": _array_digest(np.asarray(values, dtype="<f8")),
    }


def _write_npz_part(path: Path, arrays: Mapping[str, Any]) -> None:
    import numpy as np

    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            np.savez(handle, **{name: arrays[name] for name in PRIVATE_MEMBER_ORDER})
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    os.chmod(path, 0o600)


def validate_geometry_bundle(path: Path, method: Mapping[str, Any]) -> dict[str, Any]:
    headers = read_npz_headers(path)
    if headers["member_order"] != list(PRIVATE_MEMBER_ORDER):
        raise ValueError("Geometry member order drift")
    expected = method["private_bundle"]["members"]
    for name in PRIVATE_MEMBER_ORDER:
        header = headers["members"][name]
        if (
            header["shape"] != expected[name]["shape"]
            or header["descr"] != expected[name]["dtype"]
            or header["fortran_order"] is not False
        ):
            raise ValueError("Geometry member schema drift")
    return headers


def _commit_part(part: Path, final: Path) -> None:
    if os.path.lexists(final):
        raise FileExistsError(f"Sealed artifact already exists: {final}")
    os.link(part, final)
    os.unlink(part)
    if final.stat().st_nlink != 1:
        raise PermissionError("Committed artifact hard-link drift")


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
def analysis_lock() -> Iterator[None]:
    # Lock order is global then experiment-local everywhere.
    with _file_mutex(HEAVY_LOCK, "heavy research"):
        with _file_mutex(ANALYSIS_LOCK, "EXP-071 analysis"):
            yield


def _initialized_state(
    config_path: Path, config: Mapping[str, Any]
) -> tuple[Path, Path, dict[str, Any], dict[str, Any]]:
    public = _public_root(config, static=False)
    private = _private_root(config, static=False)
    require_exact_inventory(public, ["run-claim.json"], private=False)
    require_exact_inventory(private, ["input-manifest.json"], private=True)
    claim = strict_json(public / "run-claim.json")
    manifest = strict_json(private / "input-manifest.json")
    if (
        claim.get("schema_version") != "exp-071-drift-run-claim-v1"
        or claim.get("status") != "Initialized"
        or claim.get("config") != artifact(config_path)
        or manifest.get("schema_version") != "exp-071-drift-input-manifest-v1"
        or manifest.get("status") != "Initialized"
        or manifest.get("config") != artifact(config_path)
        or claim.get("input_manifest") != logical_artifact(
            private / "input-manifest.json", "input-manifest.json"
        )
        or claim.get("method_sha256") != method_sha256(config)
        or manifest.get("method_sha256") != method_sha256(config)
    ):
        raise ValueError("Initialized state binding drift")
    return public, private, claim, manifest


def _manifest_with_stable_size(
    base: dict[str, Any], *, input_bytes: int, bundle_bytes: int
) -> tuple[dict[str, Any], int]:
    manifest = dict(base)
    total = 0
    for _ in range(8):
        resources = dict(manifest["resources"])
        resources["private_output_bytes"] = total
        manifest["resources"] = resources
        observed = input_bytes + bundle_bytes + len(canonical_json_bytes(manifest))
        if observed == total:
            return manifest, total
        total = observed
    resources = dict(manifest["resources"])
    resources["private_output_bytes"] = total
    manifest["resources"] = resources
    observed = input_bytes + bundle_bytes + len(canonical_json_bytes(manifest))
    if observed != total:
        raise RuntimeError("Manifest size did not stabilize")
    return manifest, total


def analyze_stage(config_path: Path = DEFAULT_FORMAL_CONFIG) -> dict[str, Any]:
    import numpy as np

    config_path = Path(config_path).resolve()
    started = time.monotonic()
    config = load_config(config_path, expected_kind="formal")
    _implementation_records(config)
    _formal_authorization(config)
    _preflight_completion(config)
    _require_private_ignore()
    _environment_record(config, check_process=True)
    public, private, _claim, input_manifest = _initialized_state(config_path, config)

    with analysis_lock():
        before = source_identity_snapshot(config)
        if before["sha256"] != input_manifest["source_snapshot_sha256"]:
            raise ValueError("Initialized source snapshot drift")
        ordinal, fold_id = _load_row_contract(config)
        partitions = heldout_partitions(ordinal, fold_id)
        if any(item.shape != (HELDOUT_PER_FOLD,) for item in partitions):
            raise ValueError("Formal fold-size drift")
        opened = _open_matrices(config)
        arrays = compute_geometry_bundle(partitions, _formal_pair_loader(opened))
        del opened
        ap5_deltas, probe_source = _load_ap5_deltas(config)
        results = build_results(arrays, ap5_deltas)
        if results["pre_lora_sanity"]["passed"] is not True:
            raise SanityGateError("Pre-LoRA sanity did not pass")
        after = source_identity_snapshot(config)
        if after != before:
            raise ValueError("Source snapshot changed during analysis")

        part_path = private / "geometry.npz.part"
        final_path = private / "geometry.npz"
        _write_npz_part(part_path, arrays)
        validate_geometry_bundle(part_path, config["method"])
        bundle_record = logical_artifact(part_path, "geometry.npz")
        elapsed = time.monotonic() - started
        peak = _peak_rss_bytes()
        if elapsed > float(config["resources"]["runner_wall_seconds"]):
            raise RuntimeError("Analyze wall-time ceiling exceeded")
        if peak > int(config["resources"]["peak_rss_bytes"]):
            raise RuntimeError("Analyze RSS ceiling exceeded")

        numeric_checks = {
            "all_finite": True,
            "cosine_min": float(np.min(arrays["cosine_distance"])),
            "cosine_max": float(np.max(arrays["cosine_distance"])),
            "relative_l2_min": float(np.min(arrays["relative_l2_distance"])),
            "relative_l2_max": float(np.max(arrays["relative_l2_distance"])),
            "linear_cka_min": float(np.min(arrays["linear_cka"])),
            "linear_cka_max": float(np.max(arrays["linear_cka"])),
            "maximum_absolute_difference": float(np.max(arrays["max_abs_difference"])),
            "pre_lora_tolerance": SANITY_TOLERANCE,
            "pre_lora_condition_count": len(SANITY_CONDITIONS),
            "pre_lora_maximum": float(
                max(
                    np.max(arrays["max_abs_difference"][CONDITION_ORDER.index(condition)])
                    for condition in SANITY_CONDITIONS
                )
            ),
            "pre_lora_passed": True,
        }
        access = dict(ANALYZE_ACCESS)
        resources = {
            "elapsed_seconds": elapsed,
            "peak_rss_bytes": peak,
            "private_output_bytes": 0,
            "api_cost_usd": 0,
        }
        manifest_base = {
            "schema_version": "exp-071-drift-geometry-manifest-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": config["run_id"],
            "attempt_id": config["attempt_id"],
            "status": "Sealed",
            "config": artifact(config_path),
            "input_manifest": logical_artifact(private / "input-manifest.json", "input-manifest.json"),
            "method_sha256": method_sha256(config),
            "condition_order": list(CONDITION_ORDER),
            "fold_order": list(FOLDS),
            "bundle": bundle_record,
            "members": config["method"]["private_bundle"],
            "source_before": before,
            "source_after": after,
            "numeric_checks": numeric_checks,
            "probe_source": probe_source,
            "resources": resources,
            "access": access,
        }
        manifest, private_bytes = _manifest_with_stable_size(
            manifest_base,
            input_bytes=(private / "input-manifest.json").stat().st_size,
            bundle_bytes=part_path.stat().st_size,
        )
        if private_bytes > int(config["resources"]["private_output_budget_bytes"]):
            raise RuntimeError("EXP-071 private-output budget exceeded")
        _commit_part(part_path, final_path)
        if logical_artifact(final_path, "geometry.npz") != manifest["bundle"]:
            raise ValueError("Committed geometry identity drift")
        manifest_path = private / "geometry-manifest.json"
        create_json_once(manifest_path, manifest, private=True)
        if _private_size(private) != private_bytes:
            raise ValueError("Private-output byte accounting drift")

        report_resources = dict(manifest["resources"])
        report = {
            "schema_version": "exp-071-drift-run-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": config["run_id"],
            "attempt_id": config["attempt_id"],
            "stage": "analyze",
            "status": "CompletedAwaitingVerification",
            "config": artifact(config_path),
            "input_manifest": logical_artifact(private / "input-manifest.json", "input-manifest.json"),
            "geometry_manifest": logical_artifact(manifest_path, "geometry-manifest.json"),
            "geometry_bundle": logical_artifact(final_path, "geometry.npz"),
            "method_sha256": method_sha256(config),
            "counts": {
                "rows": ROWS,
                "folds": len(FOLDS),
                "heldout_rows_per_fold": HELDOUT_PER_FOLD,
                "conditions": len(CONDITION_ORDER),
                "fold_condition_comparisons": len(CONDITION_ORDER) * len(FOLDS),
                "spearman_coefficients": 1,
            },
            "results": results,
            "source_snapshot_sha256": before["sha256"],
            "resources": report_resources,
            "access": access,
            "exp071_complete": False,
            "exp072_authorized": False,
            "claim_boundary": config["claim_boundary"],
        }
        validate_public_payload(report)
        create_json_once(public / "drift.json", report)
        require_exact_inventory(
            public,
            config["outputs"]["public_analyzed_allowlist"],
            private=False,
        )
        require_exact_inventory(
            private,
            config["outputs"]["private_success_allowlist"],
            private=True,
        )
        return report


def _safe_failure(config_path: Path, stage: str, error: BaseException) -> None:
    try:
        kind = "static" if stage == "static" else "formal"
        config = load_config(config_path, expected_kind=kind)
        public = _public_root(config, static=stage == "static")
        if os.path.lexists(public / "failure.json") or os.path.lexists(public / "drift.json"):
            return
        if os.path.lexists(public):
            observed_files, observed_directories = inventory(public)
            if observed_directories:
                return
            if stage == "static" and observed_files:
                return
            if stage != "static" and observed_files not in (set(), {"run-claim.json"}):
                return
        if not os.path.lexists(public):
            _create_root(public, private=False)
        if public.is_symlink() or not public.is_dir():
            return
        value = {
            "schema_version": "exp-071-drift-failure-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": config["run_id"],
            "attempt_id": config["attempt_id"],
            "stage": stage,
            "status": "Failed",
            "error_type": type(error).__name__,
            "error_sha256": bytes_sha256(str(error).encode("utf-8", errors="replace")),
            "source_mutation_authorized": False,
            "model_loading_authorized": False,
            "forward_authorized": False,
        }
        validate_public_payload(value)
        create_json_once(public / "failure.json", value)
    except Exception:
        return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("static", "initialize", "analyze"))
    parser.add_argument("--config", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    config_path = (arguments.config or (
        DEFAULT_STATIC_CONFIG if arguments.stage == "static" else DEFAULT_FORMAL_CONFIG
    )).resolve()
    try:
        if arguments.stage == "static":
            result = static_stage(config_path)
        elif arguments.stage == "initialize":
            result = initialize_stage(config_path)
        else:
            result = analyze_stage(config_path)
    except Exception as exc:
        _safe_failure(config_path, arguments.stage, exc)
        print(
            json.dumps(
                {"experiment_id": EXPERIMENT_ID, "stage": arguments.stage, "status": "Failed"},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps({"stage": arguments.stage, "status": result["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
