#!/usr/bin/env python3
"""Independent verifier for SQMA-004 fold-3 Tune input materialization."""

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
IMPLEMENTATION_PATHS = {
    "protocol": "projects/selective-qwen-multi-agent-forum-analysis/protocols/sqma-004-agent-tune-input.md",
    "contract": "projects/selective-qwen-multi-agent-forum-analysis/scripts/scoped_input_contract.py",
    "runner": "projects/selective-qwen-multi-agent-forum-analysis/scripts/run_sqma004_agent_tune_input.py",
    "verifier": "projects/selective-qwen-multi-agent-forum-analysis/scripts/verify_sqma004_agent_tune_input.py",
    "tests": "projects/selective-qwen-multi-agent-forum-analysis/tests/test_sqma004_agent_tune_input.py",
}
PREREQUISITE_PATHS = {
    "classifier_free_amendment": "projects/selective-qwen-multi-agent-forum-analysis/configs/d0-classifier-free-amendment-v1.json",
    "sqma002_complete": "projects/selective-qwen-multi-agent-forum-analysis/runs/sqma-002-dev-scoped-input/attempt-1/complete.json",
    "sqma002_verification": "projects/selective-qwen-multi-agent-forum-analysis/runs/sqma-002-dev-scoped-input/attempt-1/verification.json",
    "sqma003_complete": "projects/selective-qwen-multi-agent-forum-analysis/runs/sqma-003-classifier-free-agent-preflight/attempt-1/complete.json",
    "public_fold_manifest": (
        "projects/llm-forum-text-emotion-recognition/experiments/"
        "stack-overflow-emotion-gold/oof-router/runs/"
        "exp-058-fold-manifest-preflight-attempt-2/fold-manifest.public.jsonl"
    ),
}
PRIVATE_ALLOWED = [
    "fold-3/gold-free-inference.jsonl",
    "fold-3/consumer-gold.npz",
    "private-manifest.json",
]
FOLD3_IDENTITY = {
    "rows": 672,
    "components": 657,
    "sample_order_sha256": "2537a0cef8c4ea878ea57083d4a76834b1ff963f3f0ca368f99f5744828a3b99",
    "sample_membership_sha256": "2537a0cef8c4ea878ea57083d4a76834b1ff963f3f0ca368f99f5744828a3b99",
    "component_membership_sha256": "115f387b4fb5674beffcbe9773b7bd81e8ccee3c814f5a7ef2d20c49e15401fb",
    "row_membership_sha256": "26b2b67d6a319c54d7b04b7627505acbb08f9017072177961706851e862f836c",
    "source_ordinal_sha256": "78d64405da2a37e9b4db69c69012e60658544dcc2005be6f0a9e9a262b2c6aba",
}
GOLD_FREE_FIELDS = {
    "schema_version", "protocol_id", "sample_id", "component_id", "fold_id",
    "source_ordinal", "text",
}
PRIVATE_MANIFEST_FIELDS = {
    "schema_version", "experiment_id", "status", "source_identity", "fold3", "artifacts",
    "access", "train_capable_created", "agent_tune_comparison_authorized", "next_gate",
    "source_records",
}
PUBLIC_RUN_FIELDS = {
    "schema_version", "experiment_id", "tier", "stage", "status", "config",
    "claim_boundary", "outputs", "access", "resources", "agent_tune_inputs_verified",
    "agent_tune_comparison_authorized", "next_gate",
}
PUBLIC_SENSITIVE_KEYS = {
    "analysis_text", "component_id", "component_ids", "gold", "label", "labels",
    "sample_id", "sample_ids", "source_ordinal", "source_ordinals", "text", "texts",
}
FORBIDDEN_IMPORTS = {"mlx", "mlx_lm", "torch", "transformers"}
EXPECTED_ACCESS = {
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


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


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


def checked_path(root: Path, relative: str, label: str) -> Path:
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute(), f"invalid {label} path")
    require(not any(character in relative for character in "*?[]{}"), f"wildcard {label} path")
    root = root.resolve()
    path = (root / relative).resolve()
    require(path == root or root in path.parents, f"{label} path escapes root")
    current = root
    for part in Path(relative).parts:
        require(part not in ("", ".", ".."), f"unnormalized {label} path")
        current /= part
        if os.path.lexists(current):
            require(not stat.S_ISLNK(os.lstat(current).st_mode), f"{label} path contains symlink")
    return path


def regular(path: Path, label: str, mode: str | None = None) -> os.stat_result:
    require(os.path.lexists(path), f"missing {label}")
    observed = os.lstat(path)
    require(stat.S_ISREG(observed.st_mode) and not stat.S_ISLNK(observed.st_mode), f"invalid {label}")
    require(observed.st_nlink == 1 and observed.st_uid == os.getuid(), f"{label} owner/link drift")
    if mode is not None:
        require(f"{stat.S_IMODE(observed.st_mode):04o}" == mode, f"{label} mode drift")
    return observed


def read_json(path: Path, label: str) -> dict[str, Any]:
    regular(path, label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid {label}") from exc
    require(isinstance(value, dict), f"{label} root drift")
    return value


def verify_record(repo_root: Path, record: Any, expected_path: str, label: str) -> Path:
    require(isinstance(record, dict) and set(record) == {"path", "bytes", "sha256"}, f"{label} record drift")
    require(record["path"] == expected_path and type(record["bytes"]) is int and record["bytes"] > 0, f"{label} identity drift")
    require(isinstance(record["sha256"], str) and len(record["sha256"]) == 64 and set(record["sha256"]) <= set("0123456789abcdef"), f"{label} hash drift")
    path = checked_path(repo_root, expected_path, label)
    observed = regular(path, label)
    require(observed.st_size == record["bytes"] and sha256(path) == record["sha256"], f"{label} file drift")
    return path


def load_contract(repo_root: Path, record: Mapping[str, Any]) -> Any:
    path = verify_record(repo_root, record, IMPLEMENTATION_PATHS["contract"], "contract")
    name = "sqma004_contract_for_independent_verifier"
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "contract import unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def validate_config(config: Mapping[str, Any]) -> None:
    require(
        config.get("schema_version") == "sqma-004-agent-tune-input-v1"
        and config.get("experiment_id") == "SQMA-004"
        and config.get("stage") == "agent-tune-fold3-input-materialization",
        "config identity drift",
    )
    authorization = config.get("authorization", {})
    require(authorization.get("execution_authorized") is True, "SQMA-004 not authorized")
    for key in (
        "model_loading", "training", "agent_calls", "accuracy_scoring",
        "validation_access", "test_access", "network", "automatic_next_stage",
    ):
        require(authorization.get(key) is False, f"authorization drift: {key}")
    require(
        config.get("planned_access")
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
    require(config.get("fold3") == FOLD3_IDENTITY, "fold3 identity drift")
    require(
        config.get("snapshot_contract")
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
    require(config["outputs"]["private_allowed_files"] == PRIVATE_ALLOWED, "private allowlist drift")


def validate_sqma003_completion(value: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    require(value.get("schema_version") == expected.get("schema_version"), "SQMA-003 completion schema drift")
    require(value.get("experiment_id") == "SQMA-003", "SQMA-003 completion identity drift")
    require(value.get("status") == "Complete" and value.get("sqma003_complete") is True, "SQMA-003 is not complete")
    require(value.get("agent_preflight_verified") is True, "SQMA-003 preflight verification drift")
    require(value.get("preflight_gate") == "Passed", "SQMA-003 preflight gate drift")
    require(value.get("accuracy_scored") is False, "SQMA-003 accuracy boundary drift")
    require(value.get("gold_accessed") is False, "SQMA-003 gold boundary drift")
    require(value.get("model_training_executed") is False, "SQMA-003 training boundary drift")


def decode_private_fold(fold_id: int) -> bool:
    """The sole private JSON decode gate used by source replay."""

    return fold_id == 3


def materialize_expected_row(
    public: Mapping[str, Any], train: Mapping[str, Any], private: Mapping[str, Any],
    ordinal: int, contract: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    public_row = contract.validate_source_row("public-fold-manifest", dict(public))
    train_row = contract.validate_source_row("private-train", dict(train))
    private_row = contract.validate_source_row("private-fold-manifest", dict(private))
    require(public_row["fold_id"] == private_row["fold_id"] == 3, "non-fold3 private row")
    require(
        (public_row["sample_id"], public_row["component_id"])
        == (train_row["sample_id"], train_row["component_id"])
        == (private_row["sample_id"], private_row["component_id"]),
        "source-order join drift",
    )
    gold = [int(value) for value in train_row["labels"]]
    require(gold == [int(value) for value in private_row["labels"]], "source gold drift")
    require(train_row["neutral"] is private_row["neutral"] and train_row["label_cardinality"] == private_row["label_cardinality"], "derived field drift")
    inference = {
        "schema_version": "sqma-gold-free-inference-snapshot-v1",
        "protocol_id": contract.PROTOCOL_ID,
        "sample_id": train_row["sample_id"], "component_id": train_row["component_id"],
        "fold_id": 3, "source_ordinal": ordinal, "text": train_row["text"],
    }
    require(set(inference) == GOLD_FREE_FIELDS, "gold-free schema drift")
    return inference, {
        "sample_id": train_row["sample_id"], "component_id": train_row["component_id"],
        "fold_id": 3, "source_ordinal": ordinal, "gold": gold,
    }


def validate_gold_free_row(value: Any, contract: Any) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == GOLD_FREE_FIELDS, "gold-free row schema drift")
    require(value["schema_version"] == "sqma-gold-free-inference-snapshot-v1" and value["protocol_id"] == contract.PROTOCOL_ID, "gold-free identity drift")
    require(value["fold_id"] == 3 and type(value["source_ordinal"]) is int, "gold-free fold/order drift")
    require(isinstance(value["text"], str), "gold-free text drift")
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
    elif isinstance(value, str) and (value.startswith("sample-") or value.startswith("component-")):
        violations.append(prefix)
    return violations


def validate_private_inventory(root: Path) -> int:
    root_stat = os.lstat(root)
    require(stat.S_ISDIR(root_stat.st_mode) and not stat.S_ISLNK(root_stat.st_mode), "private root drift")
    require(root_stat.st_uid == os.getuid() and f"{stat.S_IMODE(root_stat.st_mode):04o}" == "0700", "private root privacy drift")
    files = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())
    require(files == PRIVATE_ALLOWED, "private inventory drift")
    total = 0
    for path in root.rglob("*"):
        observed = os.lstat(path)
        require(not stat.S_ISLNK(observed.st_mode) and observed.st_uid == os.getuid(), "private owner/symlink drift")
        if path.is_dir():
            require(f"{stat.S_IMODE(observed.st_mode):04o}" == "0700", "private directory mode drift")
        else:
            require(stat.S_ISREG(observed.st_mode) and observed.st_nlink == 1 and f"{stat.S_IMODE(observed.st_mode):04o}" == "0600", "private file mode/link drift")
            total += observed.st_size
    return total


def read_npz(path: Path, numpy: Any) -> dict[str, Any]:
    regular(path, "consumer gold", "0600")
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "duplicate NPZ member")
        require(set(names) == {"sample_ids.npy", "component_ids.npy", "fold_ids.npy", "source_ordinals.npy", "gold.npy"}, "NPZ member drift")
    with numpy.load(path, allow_pickle=False) as source:
        require(set(source.files) == {"sample_ids", "component_ids", "fold_ids", "source_ordinals", "gold"}, "NPZ array drift")
        arrays = {name: numpy.asarray(source[name]) for name in source.files}
    require(arrays["sample_ids"].shape == (672,) and arrays["sample_ids"].dtype.kind == "U", "sample array drift")
    require(arrays["component_ids"].shape == (672,) and arrays["component_ids"].dtype.kind == "U", "component array drift")
    require(arrays["fold_ids"].shape == (672,) and str(arrays["fold_ids"].dtype) == "int8" and bool(numpy.all(arrays["fold_ids"] == 3)), "fold array drift")
    require(arrays["source_ordinals"].shape == (672,) and str(arrays["source_ordinals"].dtype) == "int32", "ordinal array drift")
    require(arrays["gold"].shape == (672, 6) and str(arrays["gold"].dtype) == "uint8" and bool(numpy.all((arrays["gold"] == 0) | (arrays["gold"] == 1))), "gold array drift")
    return arrays


def replay_sources(
    public_path: Path, train_path: Path, private_fold_path: Path,
    inference_rows: list[dict[str, Any]], arrays: Mapping[str, Any], contract: Any,
) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    source_paths = {"public": public_path, "train": train_path, "private_fold": private_fold_path}
    before = {key: sha256(path) for key, path in source_paths.items()}
    streamers = {key: hashlib.sha256() for key in source_paths}
    streamed = {fold: 0 for fold in range(5)}
    decoded = {fold: 0 for fold in range(5)}
    expected_rows: list[dict[str, Any]] = []
    expected_gold: list[list[int]] = []
    sentinel = object()
    with public_path.open("rb") as public_source, train_path.open("rb") as train_source, private_fold_path.open("rb") as private_source:
        streams: tuple[BinaryIO, BinaryIO, BinaryIO] = (public_source, train_source, private_source)
        for ordinal, triple in enumerate(zip_longest(*streams, fillvalue=sentinel)):
            require(sentinel not in triple, "source line-count drift")
            public_bytes, train_bytes, private_bytes = triple
            require(isinstance(public_bytes, bytes) and isinstance(train_bytes, bytes) and isinstance(private_bytes, bytes), "source stream drift")
            streamers["public"].update(public_bytes); streamers["train"].update(train_bytes); streamers["private_fold"].update(private_bytes)
            try:
                public = contract.parse_source_json_line("public-fold-manifest", public_bytes.decode("utf-8"), ordinal)
            except (UnicodeDecodeError, contract.ContractError) as exc:
                raise VerificationError("public source row drift") from exc
            fold = public["fold_id"]
            streamed[fold] += 1
            if decode_private_fold(fold):
                try:
                    train = contract.parse_source_json_line("private-train", train_bytes.decode("utf-8"), ordinal)
                    private = contract.parse_source_json_line("private-fold-manifest", private_bytes.decode("utf-8"), ordinal)
                except (UnicodeDecodeError, contract.ContractError) as exc:
                    raise VerificationError("fold3 private row drift") from exc
                inference, gold = materialize_expected_row(public, train, private, ordinal, contract)
                expected_rows.append(inference); expected_gold.append(gold["gold"]); decoded[3] += 1
            else:
                require(fold in (0, 1, 2, 4), "unknown public fold")
                # Never decode the two private byte strings in this branch.
    require(streamed == {0: 672, 1: 672, 2: 672, 3: 672, 4: 672}, "streamed fold count drift")
    require(decoded == {0: 0, 1: 0, 2: 0, 3: 672, 4: 0}, "private decode boundary drift")
    require({key: digest.hexdigest() for key, digest in streamers.items()} == before, "stream hash drift")
    require({key: sha256(path) for key, path in source_paths.items()} == before, "source changed during verification")
    require(inference_rows == expected_rows, "gold-free output value/order drift")
    for index, expected in enumerate(expected_rows):
        require(str(arrays["sample_ids"][index]) == expected["sample_id"], "NPZ sample drift")
        require(str(arrays["component_ids"][index]) == expected["component_id"], "NPZ component drift")
        require(int(arrays["fold_ids"][index]) == 3, "NPZ fold drift")
        require(int(arrays["source_ordinals"][index]) == expected["source_ordinal"], "NPZ order drift")
        require(arrays["gold"][index].tolist() == expected_gold[index], "NPZ gold drift")
    membership = contract.membership_summary(expected_rows)
    require(membership == FOLD3_IDENTITY, "fold3 membership drift")
    return before, {"streamed": streamed, "decoded": decoded}, canonical_digest([row["text"] for row in expected_rows]), canonical_digest(expected_gold)


def verify_private_manifest(
    manifest: dict[str, Any], config: dict[str, Any], private_root: Path,
    inference_path: Path, npz_path: Path, arrays: Mapping[str, Any], membership: dict[str, Any],
    source_hashes: dict[str, str], access_counts: dict[str, Any], text_digest: str, gold_digest: str,
) -> None:
    require(set(manifest) == PRIVATE_MANIFEST_FIELDS, "private manifest schema drift")
    require(manifest["schema_version"] == "sqma-004-private-manifest-v1" and manifest["experiment_id"] == "SQMA-004" and manifest["status"] == "SealedAwaitingVerification", "private manifest identity drift")
    require(manifest["train_capable_created"] is False and manifest["agent_tune_comparison_authorized"] is False, "private authorization drift")
    require(manifest["next_gate"] == "independent_agent_tune_input_verification", "private next gate drift")
    require(manifest["access"] == EXPECTED_ACCESS, "private access drift")
    expected_artifacts = [
        {"logical_name": "fold-3/gold-free-inference.jsonl", "schema_id": "sqma-gold-free-inference-snapshot-v1", "bytes": inference_path.stat().st_size, "sha256": sha256(inference_path), "mode": "0600", "rows": 672, "components": 657},
        {"logical_name": "fold-3/consumer-gold.npz", "schema_id": "sqma-consumer-gold-snapshot-v1", "bytes": npz_path.stat().st_size, "sha256": sha256(npz_path), "mode": "0600", "rows": 672, "components": 657},
    ]
    require(manifest["artifacts"] == expected_artifacts and manifest["fold3"]["artifacts"] == expected_artifacts, "private artifact metadata drift")
    require(manifest["fold3"]["membership"] == membership, "private membership drift")
    require(manifest["fold3"]["text_value_sha256"] == text_digest and manifest["fold3"]["gold_value_sha256"] == gold_digest, "private value digest drift")
    metadata = {name: {"dtype": str(value.dtype), "shape": list(value.shape)} for name, value in arrays.items()}
    require(manifest["fold3"]["consumer_gold_arrays"] == metadata, "private NPZ metadata drift")
    require(manifest["source_identity"] == {key: {"sha256_before": value, "sha256_stream": value, "sha256_after": value} for key, value in source_hashes.items()}, "private source lineage drift")
    require(access_counts["decoded"] == {0: 0, 1: 0, 2: 0, 3: 672, 4: 0}, "decode audit drift")
    expected_source_records = {
        "private_train": {
            "bytes": config["sources"]["train"]["bytes"],
            "sha256": config["sources"]["train"]["sha256"],
            "mode": "0600",
            "rows": 3360,
        },
        "private_fold_manifest": {
            "bytes": config["sources"]["private_fold_manifest"]["bytes"],
            "sha256": config["sources"]["private_fold_manifest"]["sha256"],
            "mode": "0600",
            "rows": 3360,
        },
        "public_fold_manifest": {
            "bytes": config["prerequisites"]["public_fold_manifest"]["bytes"],
            "sha256": config["prerequisites"]["public_fold_manifest"]["sha256"],
            "rows": 3360,
        },
    }
    require(manifest["source_records"] == expected_source_records, "private source records drift")


def peak_rss_bytes() -> int:
    observed = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return observed * 1024 if sys.platform.startswith("linux") else observed


def write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "wb") as output:
        output.write(payload); output.flush(); os.fsync(output.fileno())


def verify(config_argument: str) -> dict[str, Any]:
    started = time.monotonic()
    repo_root = Path(__file__).resolve().parents[3]
    supplied = Path(config_argument).expanduser().resolve()
    expected_config = checked_path(repo_root, CONFIG_RELATIVE_PATH, "config")
    require(supplied == expected_config, "noncanonical config")
    config = read_json(supplied, "config")
    validate_config(config)
    for key, path in IMPLEMENTATION_PATHS.items():
        observed = verify_record(repo_root, config["implementation"][key], path, f"implementation.{key}")
        if key == "verifier":
            require(observed == Path(__file__).resolve(), "verifier path drift")
    contract = load_contract(repo_root, config["implementation"]["contract"])
    prerequisite_paths = {
        key: verify_record(repo_root, config["prerequisites"][key], path, f"prerequisite.{key}")
        for key, path in PREREQUISITE_PATHS.items()
    }
    sqma003 = read_json(prerequisite_paths["sqma003_complete"], "SQMA-003 completion")
    validate_sqma003_completion(sqma003, config["sqma003_completion_contract"])
    require("run_sqma004_agent_tune_input" not in sys.modules and not (FORBIDDEN_IMPORTS & set(sys.modules)), "runner/model import boundary drift")

    public_root = checked_path(repo_root, PUBLIC_OUTPUT_RELATIVE, "public root")
    private_root = checked_path(repo_root, PRIVATE_OUTPUT_RELATIVE, "private root")
    require(public_root.is_dir() and private_root.is_dir(), "output root missing")
    require(not os.path.lexists(public_root / "verification.json") and not os.path.lexists(public_root / "complete.json"), "verification output exists")
    private_bytes = validate_private_inventory(private_root)
    require(private_bytes <= config["resources"]["maximum_private_output_bytes"], "private byte cap")
    inference_path = private_root / "fold-3/gold-free-inference.jsonl"
    npz_path = private_root / "fold-3/consumer-gold.npz"
    manifest_path = private_root / "private-manifest.json"
    inference_rows = []
    with inference_path.open("r", encoding="utf-8") as source:
        for line in source:
            inference_rows.append(validate_gold_free_row(json.loads(line), contract))
    require(len(inference_rows) == 672, "gold-free row count drift")

    runtime = config["runtime"]
    require(Path(sys.executable).resolve() == Path(runtime["executable"]).resolve(), "verifier executable drift")
    require(platform.python_version() == runtime["python"] and platform.machine() == runtime["machine"], "runtime identity drift")
    numpy = importlib.import_module("numpy")
    require(numpy.__version__ == runtime["packages"]["numpy"], "NumPy version drift")
    arrays = read_npz(npz_path, numpy)

    sources = config["sources"]
    archive_root = Path(os.environ.get(sources["archive_root_env"], sources["audited_archive_root"])).expanduser().resolve()
    public_path = verify_record(repo_root, config["prerequisites"]["public_fold_manifest"], PREREQUISITE_PATHS["public_fold_manifest"], "public manifest")
    train_path = checked_path(archive_root, sources["train"]["relative_path"], "private train")
    private_fold_path = checked_path(archive_root, sources["private_fold_manifest"]["relative_path"], "private fold manifest")
    for path, spec, label in ((train_path, sources["train"], "private train"), (private_fold_path, sources["private_fold_manifest"], "private fold manifest")):
        observed = regular(path, label, "0600")
        require(observed.st_size == spec["bytes"] and sha256(path) == spec["sha256"], f"{label} identity drift")
    source_hashes, access_counts, text_digest, gold_digest = replay_sources(public_path, train_path, private_fold_path, inference_rows, arrays, contract)
    membership = contract.membership_summary(inference_rows)
    manifest = read_json(manifest_path, "private manifest")
    verify_private_manifest(manifest, config, private_root, inference_path, npz_path, arrays, membership, source_hashes, access_counts, text_digest, gold_digest)

    claim = read_json(public_root / "run-claim.json", "run claim")
    run = read_json(public_root / "run.json", "run")
    require(set(run) == PUBLIC_RUN_FIELDS and run["schema_version"] == "sqma-004-run-v1" and run["status"] == "CompletedAwaitingVerification", "public run drift")
    expected_claim = {
        "schema_version": "sqma-004-run-claim-v1",
        "experiment_id": "SQMA-004",
        "status": "ClaimedBeforePrivateAccess",
        "claimed_at_utc": claim.get("claimed_at_utc"),
        "config": {"path": CONFIG_RELATIVE_PATH, "bytes": supplied.stat().st_size, "sha256": sha256(supplied)},
        "claim_boundary": "Only fold-3 private rows may be decoded to create a gold-free Agent-Tune input and a scorer-only gold snapshot. Folds 0-2 and 4 remain opaque byte streams; no model, training, Agent, validation, or test access is authorized.",
        "planned_private_rows_decoded": {"fold0_2": 0, "fold3": 672, "fold4": 0},
        "train_capable_created": False,
        "agent_tune_comparison_authorized": False,
    }
    require(claim == expected_claim and isinstance(claim["claimed_at_utc"], str), "public claim drift")
    require(run["config"] == {"path": CONFIG_RELATIVE_PATH, "bytes": supplied.stat().st_size, "sha256": sha256(supplied)}, "run config drift")
    require(run["outputs"] == {"fold3_rows": 672, "fold3_components": 657, "fold0_2_output_rows": 0, "fold4_output_rows": 0, "train_capable_created": False, "private_manifest": {"logical_name": "private-manifest.json", "bytes": manifest_path.stat().st_size, "sha256": sha256(manifest_path), "mode": "0600"}}, "public output summary drift")
    require(run["access"] == manifest["access"] == EXPECTED_ACCESS, "public/private access drift")
    require(run["agent_tune_inputs_verified"] is False and run["agent_tune_comparison_authorized"] is False and run["next_gate"] == "independent_agent_tune_input_verification", "public state drift")
    require(not public_sensitive_paths(claim) and not public_sensitive_paths(run), "public privacy drift")
    require(str(private_root.resolve()) not in json.dumps(run, ensure_ascii=False), "private path leak")
    resources = run["resources"]
    require(resources["wall_seconds"] <= 300 and resources["peak_rss_bytes"] <= 1073741824 and resources["private_output_bytes"] == private_bytes, "runner resource drift")
    for key in ("model_or_mlx_allocations", "critical_memory_events", "oom_or_kill_events", "orphan_processes_after_exit"):
        require(resources[key] == 0, f"runner resource event: {key}")

    elapsed = time.monotonic() - started
    peak = peak_rss_bytes()
    require(elapsed <= 300 and peak <= 1073741824, "verifier resource cap")
    verification = {
        "schema_version": "sqma-004-verification-v1", "experiment_id": "SQMA-004", "status": "Passed", "verified_at_utc": utc_now(),
        "config": {"path": CONFIG_RELATIVE_PATH, "bytes": supplied.stat().st_size, "sha256": sha256(supplied)},
        "run": {"path": f"{PUBLIC_OUTPUT_RELATIVE}/run.json", "bytes": (public_root / "run.json").stat().st_size, "sha256": sha256(public_root / "run.json")},
        "private_manifest": {"logical_name": "private-manifest.json", "bytes": manifest_path.stat().st_size, "sha256": sha256(manifest_path), "mode": "0600"},
        "checks": ["identity_and_authorization", "independent_source_replay", "fold3_only_decode", "exact_private_inventory", "gold_free_schema_and_order", "consumer_npz_dtype_shape_and_values", "source_and_cross_scope_parity", "mode_owner_and_links", "public_privacy", "resource_and_access_boundary"],
        "fold3": {"rows": 672, "components": 657, "membership": membership},
        "fold0_2_private_rows_decoded": 0, "fold4_private_rows_decoded": 0,
        "resources": {"wall_seconds": elapsed, "peak_rss_bytes": peak, "private_output_bytes": private_bytes},
        "access": {"runner_imported": False, "model_framework_imported": False, "fold3_private_rows_decoded": 672, "fold0_2_private_rows_decoded": 0, "fold4_private_rows_decoded": 0, "model_loaded": False, "training_executed": False, "agent_calls": 0, "validation_accessed": False, "test_accessed": False, "files_written_private": False},
        "agent_tune_inputs_verified": True, "agent_tune_comparison_authorized": False,
        "next_gate": "register_full_672_row_agent_tune_matched_comparison",
        "claim_boundary": "Independent verification of fold-3-only classifier-free Tune inputs; folds 0-2 and 4 remained opaque private byte streams, and no model, Agent, accuracy, validation, or test operation occurred.",
    }
    require(not public_sensitive_paths(verification), "verification privacy drift")
    write_json_exclusive(public_root / "verification.json", verification)
    complete = {
        "schema_version": "sqma-004-complete-v1", "experiment_id": "SQMA-004", "status": "Complete", "completed_at_utc": utc_now(),
        "verification": {"path": f"{PUBLIC_OUTPUT_RELATIVE}/verification.json", "bytes": (public_root / "verification.json").stat().st_size, "sha256": sha256(public_root / "verification.json")},
        "sqma004_complete": True, "agent_tune_inputs_verified": True, "fold3_output_rows": 672,
        "fold0_2_private_rows_decoded": 0, "fold4_private_rows_decoded": 0,
        "train_capable_created": False, "model_loaded": False, "training_executed": False,
        "agent_calls": 0, "agent_tune_comparison_authorized": False,
        "next_gate": "register_full_672_row_agent_tune_matched_comparison",
    }
    require(not public_sensitive_paths(complete), "completion privacy drift")
    write_json_exclusive(public_root / "complete.json", complete)
    require(sorted(path.name for path in public_root.iterdir()) == sorted(config["outputs"]["public_allowed_files"]), "public inventory drift")
    require(sum(path.stat().st_size for path in public_root.iterdir()) <= config["resources"]["maximum_public_output_bytes"], "public byte cap")
    return verification


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    result = verify(args.config)
    print(json.dumps({"experiment_id": "SQMA-004", "status": result["status"], "next_gate": result["next_gate"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, ImportError, zipfile.BadZipFile, VerificationError) as exc:
        print(f"SQMA-004 verification Failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
