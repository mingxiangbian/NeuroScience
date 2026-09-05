#!/usr/bin/env python3
"""Prepare the fold-3-only SQMA-004 Agent-Tune input snapshots.

The registered config is intentionally non-executable.  A future explicitly
authorized successor may use this runner after binding every implementation
and prerequisite identity.  Private lines are decoded only for public fold 3;
folds 0-2 and 4 remain opaque byte streams.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.util
from itertools import zip_longest
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import stat
import sys
import time
from typing import Any, BinaryIO, Mapping
import zipfile


sys.dont_write_bytecode = True

CONFIG_RELATIVE_PATH = (
    "projects/selective-qwen-multi-agent-forum-analysis/configs/"
    "sqma-004-agent-tune-input.json"
)
PUBLIC_OUTPUT_RELATIVE = (
    "projects/selective-qwen-multi-agent-forum-analysis/runs/"
    "sqma-004-agent-tune-input/attempt-1"
)
PRIVATE_OUTPUT_RELATIVE = (
    "projects/selective-qwen-multi-agent-forum-analysis/private/"
    "sqma-004-agent-tune-input/attempt-1"
)
FOLD3_IDENTITY = {
    "rows": 672,
    "components": 657,
    "sample_order_sha256": "2537a0cef8c4ea878ea57083d4a76834b1ff963f3f0ca368f99f5744828a3b99",
    "sample_membership_sha256": "2537a0cef8c4ea878ea57083d4a76834b1ff963f3f0ca368f99f5744828a3b99",
    "component_membership_sha256": "115f387b4fb5674beffcbe9773b7bd81e8ccee3c814f5a7ef2d20c49e15401fb",
    "row_membership_sha256": "26b2b67d6a319c54d7b04b7627505acbb08f9017072177961706851e862f836c",
    "source_ordinal_sha256": "78d64405da2a37e9b4db69c69012e60658544dcc2005be6f0a9e9a262b2c6aba",
}
IMPLEMENTATION_PATHS = {
    "protocol": (
        "projects/selective-qwen-multi-agent-forum-analysis/protocols/"
        "sqma-004-agent-tune-input.md"
    ),
    "contract": (
        "projects/selective-qwen-multi-agent-forum-analysis/scripts/"
        "scoped_input_contract.py"
    ),
    "runner": (
        "projects/selective-qwen-multi-agent-forum-analysis/scripts/"
        "run_sqma004_agent_tune_input.py"
    ),
    "verifier": (
        "projects/selective-qwen-multi-agent-forum-analysis/scripts/"
        "verify_sqma004_agent_tune_input.py"
    ),
    "tests": (
        "projects/selective-qwen-multi-agent-forum-analysis/tests/"
        "test_sqma004_agent_tune_input.py"
    ),
}
PREREQUISITE_PATHS = {
    "classifier_free_amendment": (
        "projects/selective-qwen-multi-agent-forum-analysis/configs/"
        "d0-classifier-free-amendment-v1.json"
    ),
    "sqma002_complete": (
        "projects/selective-qwen-multi-agent-forum-analysis/runs/"
        "sqma-002-dev-scoped-input/attempt-1/complete.json"
    ),
    "sqma002_verification": (
        "projects/selective-qwen-multi-agent-forum-analysis/runs/"
        "sqma-002-dev-scoped-input/attempt-1/verification.json"
    ),
    "sqma003_complete": (
        "projects/selective-qwen-multi-agent-forum-analysis/runs/"
        "sqma-003-classifier-free-agent-preflight/attempt-1/complete.json"
    ),
    "public_fold_manifest": (
        "projects/llm-forum-text-emotion-recognition/experiments/"
        "stack-overflow-emotion-gold/oof-router/runs/"
        "exp-058-fold-manifest-preflight-attempt-2/fold-manifest.public.jsonl"
    ),
}
PRIVATE_FIELDS = {"relative_path", "bytes", "sha256", "mode", "rows"}
ARTIFACT_FIELDS = {"path", "bytes", "sha256"}
GOLD_FREE_FIELDS = {
    "schema_version",
    "protocol_id",
    "sample_id",
    "component_id",
    "fold_id",
    "source_ordinal",
    "text",
}
PRIVATE_ALLOWED = [
    "fold-3/gold-free-inference.jsonl",
    "fold-3/consumer-gold.npz",
    "private-manifest.json",
]
PUBLIC_SENSITIVE_KEYS = {
    "analysis_text",
    "component_id",
    "component_ids",
    "gold",
    "label",
    "labels",
    "sample_id",
    "sample_ids",
    "source_ordinal",
    "source_ordinals",
    "text",
    "texts",
}


class TuneInputError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise TuneInputError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_json(path: Path, label: str) -> dict[str, Any]:
    regular(path, label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TuneInputError(f"invalid {label}") from exc
    require(isinstance(value, dict), f"{label} root drift")
    return value


def checked_path(root: Path, relative: str, label: str) -> Path:
    require(isinstance(relative, str) and relative, f"invalid {label} path")
    require(not Path(relative).is_absolute(), f"absolute {label} path forbidden")
    require(not any(character in relative for character in "*?[]{}"), f"wildcard {label} path forbidden")
    lexical = root / relative
    resolved_root = root.resolve()
    resolved = lexical.resolve()
    require(resolved == resolved_root or resolved_root in resolved.parents, f"{label} path escapes root")
    current = root
    for part in Path(relative).parts:
        current = current / part
        if os.path.lexists(current):
            require(not stat.S_ISLNK(os.lstat(current).st_mode), f"{label} path contains symlink")
    return lexical


def regular(path: Path, label: str, mode: str | None = None) -> os.stat_result:
    require(os.path.lexists(path), f"missing {label}")
    observed = os.lstat(path)
    require(stat.S_ISREG(observed.st_mode) and not stat.S_ISLNK(observed.st_mode), f"invalid {label}")
    require(observed.st_nlink == 1, f"hard-linked {label}")
    require(observed.st_uid == os.getuid(), f"{label} owner drift")
    if mode is not None:
        require(f"{stat.S_IMODE(observed.st_mode):04o}" == mode, f"{label} mode drift")
    return observed


def verify_record(repo_root: Path, record: Any, expected_path: str, label: str) -> Path:
    require(isinstance(record, dict) and set(record) == ARTIFACT_FIELDS, f"{label} record drift")
    require(record["path"] == expected_path, f"{label} path drift")
    require(type(record["bytes"]) is int and record["bytes"] > 0, f"{label} bytes drift")
    require(
        isinstance(record["sha256"], str)
        and len(record["sha256"]) == 64
        and set(record["sha256"]) <= set("0123456789abcdef")
        and record["sha256"] != "TO_BE_REGISTERED",
        f"{label} hash is not registered",
    )
    path = checked_path(repo_root, record["path"], label)
    observed = regular(path, label)
    require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], f"{label} identity drift")
    return path


def load_contract(repo_root: Path, record: Mapping[str, Any]) -> Any:
    path = verify_record(repo_root, record, IMPLEMENTATION_PATHS["contract"], "contract")
    name = "sqma004_scoped_input_contract"
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "contract import spec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def validate_design(config: Mapping[str, Any], contract: Any) -> None:
    require(config.get("schema_version") == "sqma-004-agent-tune-input-v1", "config schema drift")
    require(config.get("experiment_id") == "SQMA-004", "experiment identity drift")
    require(config.get("stage") == "agent-tune-fold3-input-materialization", "stage drift")
    authorization = config.get("authorization")
    require(isinstance(authorization, dict), "authorization missing")
    require(authorization.get("automatic_next_stage") is False, "automatic progression forbidden")
    require(authorization.get("model_loading") is False, "model loading authorization drift")
    require(authorization.get("training") is False and authorization.get("agent_calls") is False, "model execution authorization drift")
    planned = config.get("planned_access")
    require(
        planned
        == {
            "public_fold_metadata_access": True,
            "monolithic_private_byte_streaming": True,
            "decode_private_rows_for_folds": [3],
            "decode_private_rows_for_folds_0_2": False,
            "decode_private_rows_for_fold4": False,
            "write_fold3_gold_free_and_consumer_gold": True,
            "write_train_capable": False,
            "validation_access": False,
            "test_access": False,
            "network": False,
        },
        "planned access drift",
    )
    sources = config.get("sources")
    require(isinstance(sources, dict), "sources missing")
    for key in ("train", "private_fold_manifest"):
        value = sources.get(key)
        require(isinstance(value, dict) and set(value) == PRIVATE_FIELDS, f"{key} source drift")
        require(value["mode"] == "0600" and value["rows"] == 3360, f"{key} source scope drift")
    fold = config.get("fold3")
    require(isinstance(fold, dict), "fold3 identity missing")
    for key, value in FOLD3_IDENTITY.items():
        require(fold.get(key) == value, f"fold3 {key} drift")
    snapshots = config.get("snapshot_contract")
    require(
        snapshots
        == {
            "output_fold": 3,
            "scopes": ["gold-free-inference", "consumer-gold"],
            "rows_per_scope": 672,
            "train_capable_created": False,
            "fold0_2_output_rows": 0,
            "fold4_output_rows": 0,
            "private_directory_mode": "0700",
            "private_file_mode": "0600",
            "extra_files_allowed": 0,
        },
        "snapshot contract drift",
    )
    outputs = config.get("outputs")
    require(outputs.get("public_attempt_dir") == PUBLIC_OUTPUT_RELATIVE, "public output path drift")
    require(outputs.get("private_attempt_dir") == PRIVATE_OUTPUT_RELATIVE, "private output path drift")
    require(outputs.get("private_allowed_files") == PRIVATE_ALLOWED, "private inventory drift")
    require(outputs.get("public_allowed_files") == ["run-claim.json", "run.json", "verification.json", "complete.json"], "public inventory drift")
    require(contract.OUTPUT_SCHEMAS["gold-free-inference"].contains_gold is False, "gold-free schema drift")


def validate_sqma003_completion(value: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    require(value.get("schema_version") == expected.get("schema_version"), "SQMA-003 completion schema drift")
    require(value.get("experiment_id") == "SQMA-003", "SQMA-003 completion identity drift")
    require(value.get("status") == "Complete" and value.get("sqma003_complete") is True, "SQMA-003 is not complete")
    require(value.get("agent_preflight_verified") is True, "SQMA-003 preflight verification drift")
    require(value.get("preflight_gate") == "Passed", "SQMA-003 preflight gate drift")
    require(value.get("accuracy_scored") is False, "SQMA-003 accuracy boundary drift")
    require(value.get("gold_accessed") is False, "SQMA-003 gold boundary drift")
    require(value.get("model_training_executed") is False, "SQMA-003 training boundary drift")


def source_record(path: Path, spec: Mapping[str, Any], label: str) -> dict[str, Any]:
    observed = regular(path, label, str(spec["mode"]))
    require(observed.st_size == spec["bytes"], f"{label} byte drift")
    digest = sha256(path)
    require(digest == spec["sha256"], f"{label} hash drift")
    return {"bytes": observed.st_size, "sha256": digest, "mode": spec["mode"], "rows": spec["rows"]}


def materialize_fold3_row(
    public: Mapping[str, Any], train: Mapping[str, Any], private: Mapping[str, Any], ordinal: int, contract: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    public_row = contract.validate_source_row("public-fold-manifest", dict(public))
    train_row = contract.validate_source_row("private-train", dict(train))
    private_row = contract.validate_source_row("private-fold-manifest", dict(private))
    require(public_row["fold_id"] == 3 and private_row["fold_id"] == 3, "non-fold3 row selected")
    identities = {
        (public_row["sample_id"], public_row["component_id"]),
        (train_row["sample_id"], train_row["component_id"]),
        (private_row["sample_id"], private_row["component_id"]),
    }
    require(len(identities) == 1, "fold3 source join identity drift")
    train_labels = [int(value) for value in train_row["labels"]]
    private_labels = [int(value) for value in private_row["labels"]]
    require(train_labels == private_labels, "fold3 source join label drift")
    require(
        train_row["neutral"] is private_row["neutral"]
        and train_row["label_cardinality"] == private_row["label_cardinality"],
        "fold3 derived-field drift",
    )
    inference = {
        "schema_version": "sqma-gold-free-inference-snapshot-v1",
        "protocol_id": contract.PROTOCOL_ID,
        "sample_id": train_row["sample_id"],
        "component_id": train_row["component_id"],
        "fold_id": 3,
        "source_ordinal": ordinal,
        "text": train_row["text"],
    }
    require(set(inference) == GOLD_FREE_FIELDS, "fold3 gold-free schema drift")
    gold = {
        "sample_id": train_row["sample_id"],
        "component_id": train_row["component_id"],
        "fold_id": 3,
        "source_ordinal": ordinal,
        "gold": train_labels,
    }
    return inference, gold


def write_exclusive(path: Path, payload: bytes, mode: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as output:
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())
    path.chmod(mode)


def write_json(path: Path, value: Mapping[str, Any], mode: int) -> None:
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    require(not os.path.lexists(path) and not os.path.lexists(temporary), "JSON output exists")
    write_exclusive(temporary, payload, mode)
    os.replace(temporary, path)
    path.chmod(mode)


def write_npz(path: Path, values: Mapping[str, list[Any]], numpy: Any) -> dict[str, Any]:
    arrays = {
        "sample_ids": numpy.asarray(values["sample_ids"], dtype=f"<U{max(map(len, values['sample_ids']))}"),
        "component_ids": numpy.asarray(values["component_ids"], dtype=f"<U{max(map(len, values['component_ids']))}"),
        "fold_ids": numpy.asarray(values["fold_ids"], dtype=numpy.int8),
        "source_ordinals": numpy.asarray(values["source_ordinals"], dtype=numpy.int32),
        "gold": numpy.asarray(values["gold"], dtype=numpy.uint8),
    }
    require(arrays["sample_ids"].shape == (672,) and arrays["sample_ids"].dtype.kind == "U", "sample array drift")
    require(arrays["component_ids"].shape == (672,) and arrays["component_ids"].dtype.kind == "U", "component array drift")
    require(arrays["fold_ids"].shape == (672,) and bool(numpy.all(arrays["fold_ids"] == 3)), "fold array drift")
    require(arrays["source_ordinals"].shape == (672,), "ordinal array drift")
    require(arrays["gold"].shape == (672, 6) and bool(numpy.all((arrays["gold"] == 0) | (arrays["gold"] == 1))), "gold array drift")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        numpy.savez(output, **arrays)
        output.flush()
        os.fsync(output.fileno())
    path.chmod(0o600)
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "duplicate NPZ member")
        require(set(names) == {f"{name}.npy" for name in arrays}, "NPZ member drift")
    with numpy.load(path, allow_pickle=False) as observed:
        require(set(observed.files) == set(arrays), "NPZ array inventory drift")
        for key, expected in arrays.items():
            require(observed[key].dtype == expected.dtype and observed[key].shape == expected.shape, f"NPZ {key} metadata drift")
            require(bool(numpy.array_equal(observed[key], expected)), f"NPZ {key} value drift")
    return {key: {"dtype": str(value.dtype), "shape": list(value.shape)} for key, value in arrays.items()}


def stream_fold3(
    public_path: Path,
    train_path: Path,
    private_fold_path: Path,
    staging: Path,
    contract: Any,
    numpy: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    before = {"public": sha256(public_path), "train": sha256(train_path), "private_fold": sha256(private_fold_path)}
    streamed = {key: hashlib.sha256() for key in before}
    rows: list[dict[str, Any]] = []
    gold_values: dict[str, list[Any]] = {
        "sample_ids": [], "component_ids": [], "fold_ids": [], "source_ordinals": [], "gold": []
    }
    streamed_counts = {fold: 0 for fold in range(5)}
    decoded_counts = {fold: 0 for fold in range(5)}
    public_components: dict[str, int] = {}
    public_samples: set[str] = set()
    fold_dir = staging / "fold-3"
    fold_dir.mkdir(mode=0o700)
    fold_dir.chmod(0o700)
    inference_path = fold_dir / "gold-free-inference.jsonl"
    descriptor = os.open(inference_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output, public_path.open("rb") as public_source, train_path.open("rb") as train_source, private_fold_path.open("rb") as private_source:
        sentinel = object()
        count = 0
        for ordinal, triple in enumerate(zip_longest(public_source, train_source, private_source, fillvalue=sentinel)):
            public_bytes, train_bytes, private_bytes = triple
            require(sentinel not in triple, "source line-count mismatch")
            require(isinstance(public_bytes, bytes) and isinstance(train_bytes, bytes) and isinstance(private_bytes, bytes), "source stream type drift")
            require(public_bytes.strip() and train_bytes.strip() and private_bytes.strip(), "empty source line")
            streamed["public"].update(public_bytes)
            streamed["train"].update(train_bytes)
            streamed["private_fold"].update(private_bytes)
            try:
                public = contract.parse_source_json_line("public-fold-manifest", public_bytes.decode("utf-8"), ordinal)
            except (UnicodeDecodeError, contract.ContractError) as exc:
                raise TuneInputError(f"public row failure at ordinal {ordinal}") from exc
            fold = public["fold_id"]
            streamed_counts[fold] += 1
            require(public["sample_id"] not in public_samples, "duplicate public sample")
            prior = public_components.setdefault(public["component_id"], fold)
            require(prior == fold, "component crosses public folds")
            public_samples.add(public["sample_id"])
            if fold == 3:
                try:
                    train = contract.parse_source_json_line("private-train", train_bytes.decode("utf-8"), ordinal)
                    private = contract.parse_source_json_line("private-fold-manifest", private_bytes.decode("utf-8"), ordinal)
                except (UnicodeDecodeError, contract.ContractError) as exc:
                    raise TuneInputError(f"fold3 private row failure at ordinal {ordinal}") from exc
                inference, gold = materialize_fold3_row(public, train, private, ordinal, contract)
                line = contract.canonical_json_line(inference).encode("utf-8")
                output.write(line)
                rows.append(inference)
                for singular, plural in (("sample_id", "sample_ids"), ("component_id", "component_ids"), ("fold_id", "fold_ids"), ("source_ordinal", "source_ordinals"), ("gold", "gold")):
                    gold_values[plural].append(gold[singular])
                decoded_counts[3] += 1
            else:
                require(fold in (0, 1, 2, 4), "unexpected fold")
                # Do not decode either private byte string in this branch.
            count += 1
        require(count == 3360, "source row count drift")
        output.flush()
        os.fsync(output.fileno())
    inference_path.chmod(0o600)
    require(streamed_counts == {0: 672, 1: 672, 2: 672, 3: 672, 4: 672}, "public fold count drift")
    require(decoded_counts == {0: 0, 1: 0, 2: 0, 3: 672, 4: 0}, "private decode boundary drift")
    stream_hashes = {key: value.hexdigest() for key, value in streamed.items()}
    require(stream_hashes == before, "stream source hash drift")
    after = {"public": sha256(public_path), "train": sha256(train_path), "private_fold": sha256(private_fold_path)}
    require(after == before, "source changed during materialization")
    membership = contract.membership_summary(rows)
    require(membership == FOLD3_IDENTITY, "fold3 membership drift")
    ordinals = [row["source_ordinal"] for row in rows]
    require(ordinals == sorted(ordinals) and len(ordinals) == len(set(ordinals)), "fold3 source order drift")
    npz_path = fold_dir / "consumer-gold.npz"
    arrays = write_npz(npz_path, gold_values, numpy)
    artifacts = []
    for path, schema in (
        (inference_path, "sqma-gold-free-inference-snapshot-v1"),
        (npz_path, "sqma-consumer-gold-snapshot-v1"),
    ):
        observed = regular(path, path.name, "0600")
        artifacts.append({
            "logical_name": path.relative_to(staging).as_posix(),
            "schema_id": schema,
            "bytes": observed.st_size,
            "sha256": sha256(path),
            "mode": "0600",
            "rows": 672,
            "components": 657,
        })
    access = {
        "monolithic_private_bytes_streamed": True,
        "private_rows_decoded": 672,
        "fold0_2_private_rows_decoded": 0,
        "fold3_private_rows_decoded": 672,
        "fold4_private_rows_decoded": 0,
        "fold0_2_private_rows_byte_streamed": 2016,
        "fold4_private_rows_byte_streamed": 672,
        "selected_train_text_read": True,
        "selected_train_gold_read": True,
        "model_loaded": False,
        "training_executed": False,
        "agent_calls": 0,
        "network_accessed": False,
        "validation_accessed": False,
        "test_accessed": False,
    }
    private_manifest = {
        "schema_version": "sqma-004-private-manifest-v1",
        "experiment_id": "SQMA-004",
        "status": "SealedAwaitingVerification",
        "source_identity": {
            key: {"sha256_before": before[key], "sha256_stream": stream_hashes[key], "sha256_after": after[key]}
            for key in before
        },
        "fold3": {
            "membership": membership,
            "artifacts": artifacts,
            "consumer_gold_arrays": arrays,
            "text_value_sha256": canonical_digest([row["text"] for row in rows]),
            "gold_value_sha256": canonical_digest(gold_values["gold"]),
        },
        "artifacts": artifacts,
        "access": access,
        "train_capable_created": False,
        "agent_tune_comparison_authorized": False,
        "next_gate": "independent_agent_tune_input_verification",
    }
    return private_manifest, access


def private_inventory(root: Path) -> int:
    files = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
    require(files == PRIVATE_ALLOWED, "private output inventory drift")
    total = 0
    for path in root.rglob("*"):
        observed = os.lstat(path)
        require(not stat.S_ISLNK(observed.st_mode) and observed.st_uid == os.getuid(), "private ownership/link drift")
        if path.is_dir():
            require(f"{stat.S_IMODE(observed.st_mode):04o}" == "0700", "private directory mode drift")
        else:
            require(stat.S_ISREG(observed.st_mode) and observed.st_nlink == 1, "private file link drift")
            require(f"{stat.S_IMODE(observed.st_mode):04o}" == "0600", "private file mode drift")
            total += observed.st_size
    return total


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
    elif isinstance(value, str) and (value.startswith("sample-") or value.startswith("component-")):
        violations.append(prefix)
    return violations


def peak_rss_bytes() -> int:
    observed = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return observed * 1024 if sys.platform.startswith("linux") else observed


def run(config_argument: str) -> dict[str, Any]:
    started = time.monotonic()
    repo_root = Path(__file__).resolve().parents[3]
    expected = checked_path(repo_root, CONFIG_RELATIVE_PATH, "config")
    supplied = Path(config_argument).expanduser().resolve()
    require(supplied == expected.resolve(), "noncanonical config path")
    config = read_json(supplied, "config")
    authorization = config.get("authorization", {})
    require(authorization.get("execution_authorized") is True, "SQMA-004 execution is not authorized")

    implementation = config["implementation"]
    for key, path in IMPLEMENTATION_PATHS.items():
        verify_record(repo_root, implementation[key], path, f"implementation.{key}")
    contract = load_contract(repo_root, implementation["contract"])
    validate_design(config, contract)
    for key, path in PREREQUISITE_PATHS.items():
        verify_record(repo_root, config["prerequisites"][key], path, f"prerequisite.{key}")
    sqma003 = read_json(checked_path(repo_root, config["prerequisites"]["sqma003_complete"]["path"], "SQMA-003 completion"), "SQMA-003 completion")
    validate_sqma003_completion(sqma003, config["sqma003_completion_contract"])

    public_target = checked_path(repo_root, config["outputs"]["public_attempt_dir"], "public output")
    private_target = checked_path(repo_root, config["outputs"]["private_attempt_dir"], "private output")
    staging = private_target.with_name(private_target.name + ".staging")
    require(not any(os.path.lexists(path) for path in (public_target, private_target, staging)), "output target exists")
    require(shutil.disk_usage(repo_root).free >= config["resources"]["minimum_free_disk_bytes"], "insufficient disk")
    public_target.mkdir(parents=True, mode=0o755)
    claim = {
        "schema_version": "sqma-004-run-claim-v1",
        "experiment_id": "SQMA-004",
        "status": "ClaimedBeforePrivateAccess",
        "claimed_at_utc": utc_now(),
        "config": {"path": CONFIG_RELATIVE_PATH, "bytes": supplied.stat().st_size, "sha256": sha256(supplied)},
        "claim_boundary": "Only fold-3 private rows may be decoded to create a gold-free Agent-Tune input and a scorer-only gold snapshot. Folds 0-2 and 4 remain opaque byte streams; no model, training, Agent, validation, or test access is authorized.",
        "planned_private_rows_decoded": {"fold0_2": 0, "fold3": 672, "fold4": 0},
        "train_capable_created": False,
        "agent_tune_comparison_authorized": False,
    }
    require(not public_sensitive_paths(claim), "public claim contains sensitive material")
    write_json(public_target / "run-claim.json", claim, 0o644)

    sources = config["sources"]
    archive = Path(os.environ.get(sources["archive_root_env"], sources["audited_archive_root"])).expanduser().resolve()
    require(archive.is_dir(), "archive root unavailable")
    public_path = verify_record(repo_root, config["prerequisites"]["public_fold_manifest"], PREREQUISITE_PATHS["public_fold_manifest"], "public fold manifest")
    train_path = checked_path(archive, sources["train"]["relative_path"], "private train")
    private_fold_path = checked_path(archive, sources["private_fold_manifest"]["relative_path"], "private fold manifest")
    train_record = source_record(train_path, sources["train"], "private train")
    fold_record = source_record(private_fold_path, sources["private_fold_manifest"], "private fold manifest")

    runtime = config["runtime"]
    require(Path(sys.executable).resolve() == Path(runtime["executable"]).resolve(), "runtime executable drift")
    require(platform.python_version() == runtime["python"] and platform.machine() == runtime["machine"], "runtime identity drift")
    numpy = importlib.import_module("numpy")
    require(numpy.__version__ == runtime["packages"]["numpy"], "NumPy version drift")

    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.parent.chmod(0o700)
    staging.mkdir(mode=0o700)
    private_manifest, access = stream_fold3(public_path, train_path, private_fold_path, staging, contract, numpy)
    private_manifest["source_records"] = {
        "private_train": train_record,
        "private_fold_manifest": fold_record,
        "public_fold_manifest": {"bytes": public_path.stat().st_size, "sha256": sha256(public_path), "rows": 3360},
    }
    write_json(staging / "private-manifest.json", private_manifest, 0o600)
    private_bytes = private_inventory(staging)
    require(private_bytes <= config["resources"]["maximum_private_output_bytes"], "private output budget exceeded")
    os.replace(staging, private_target)
    private_target.chmod(0o700)
    elapsed = time.monotonic() - started
    rss = peak_rss_bytes()
    require(elapsed <= config["resources"]["maximum_wall_seconds"], "wall cap exceeded")
    require(rss <= config["resources"]["maximum_peak_rss_bytes"], "RSS cap exceeded")
    manifest_path = private_target / "private-manifest.json"
    run_payload = {
        "schema_version": "sqma-004-run-v1",
        "experiment_id": "SQMA-004",
        "tier": config["tier"],
        "stage": config["stage"],
        "status": "CompletedAwaitingVerification",
        "config": {"path": CONFIG_RELATIVE_PATH, "bytes": supplied.stat().st_size, "sha256": sha256(supplied)},
        "claim_boundary": "Fold-3 Agent-Tune inputs were materialized without model execution. Private rows for folds 0-2 and 4 were byte-streamed but not decoded; no comparison or accuracy result was produced.",
        "outputs": {
            "fold3_rows": 672,
            "fold3_components": 657,
            "fold0_2_output_rows": 0,
            "fold4_output_rows": 0,
            "train_capable_created": False,
            "private_manifest": {"logical_name": "private-manifest.json", "bytes": manifest_path.stat().st_size, "sha256": sha256(manifest_path), "mode": "0600"},
        },
        "access": access,
        "resources": {"wall_seconds": elapsed, "peak_rss_bytes": rss, "private_output_bytes": private_bytes, "model_or_mlx_allocations": 0, "critical_memory_events": 0, "oom_or_kill_events": 0, "orphan_processes_after_exit": 0},
        "agent_tune_inputs_verified": False,
        "agent_tune_comparison_authorized": False,
        "next_gate": "independent_agent_tune_input_verification",
    }
    require(not public_sensitive_paths(run_payload), "public run contains sensitive material")
    encoded = (json.dumps(run_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    require((public_target / "run-claim.json").stat().st_size + len(encoded) <= config["resources"]["maximum_public_output_bytes"], "public output budget exceeded")
    write_exclusive(public_target / "run.json", encoded, 0o644)
    return run_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    result = run(args.config)
    print(json.dumps({"experiment_id": "SQMA-004", "status": result["status"], "next_gate": result["next_gate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, ImportError, TuneInputError) as exc:
        print(f"SQMA-004 materialization Failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
