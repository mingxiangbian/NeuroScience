#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import struct
import subprocess
import sys
from typing import Any, BinaryIO
import zipfile


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
DEFAULT_CONFIG = MODULE_DIR / "configs" / "exp-070-layerwise-probe-preflight.json"
EXPERIMENT_ID = "EXP-070"
RUN_ID = "exp-070-layerwise-probe-preflight"
ATTEMPT_ID = "attempt-1"
POINTS = ("H-1", "H7", "H15", "H19", "H20", "H27", "H31", "H35", "HF")
POINT_KEYS = {
    "H-1": "h_minus_1",
    "H7": "h7",
    "H15": "h15",
    "H19": "h19",
    "H20": "h20",
    "H27": "h27",
    "H31": "h31",
    "H35": "h35",
    "HF": "hf",
}
SEEDS = (42, 43, 44)
FOLDS = (0, 1, 2, 3, 4)
FOLD_ROWS = (8, 6, 5, 7, 6)
PUBLIC_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
    "exp-070-layerwise-probe-preflight/attempt-1"
)
PRIVATE_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
    "exp-070-layerwise-probe-preflight/attempt-1"
)
FORMAL_PUBLIC_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
    "exp-070-layerwise-probes/formal-attempt-1"
)
FORMAL_PRIVATE_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
    "exp-070-layerwise-probes/formal-attempt-1"
)
FORBIDDEN_MODULES = {"mlx", "mlx_lm", "sklearn", "torch", "transformers"}
METHOD_KEYS = (
    "environments",
    "representation",
    "outer_cv",
    "probe",
    "threshold",
    "metrics",
    "seed_roles",
    "label_shuffle",
    "bootstrap",
    "resources",
    "authorization",
    "access",
    "outputs",
    "claim_boundary",
)
INPUT_KEYS = ("decision", "parent_exp069", "data", "privacy")
EXPECTED_METHOD_SHA256 = "2c397431887c44beb2d77c8f46cee0d2bb543f14c0f5080f76646f0524b2607f"
EXPECTED_INPUT_SHA256 = "46bfd6237fe2752336fb9e0c9c7df1cc5ff59bed935dbed89b14c507843e1950"


def _no_constant(value: str) -> Any:
    raise ValueError(f"Non-finite JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_no_constant,
    )


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def resolve_project(relative: str) -> Path:
    pure = PurePosixPath(relative)
    if type(relative) is not str or not relative or pure.is_absolute() or pure.as_posix() != relative:
        raise ValueError("Unsafe project path")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("Unsafe project path")
    path = PROJECT_ROOT.joinpath(*pure.parts)
    current = PROJECT_ROOT
    for part in pure.parts:
        current = current / part
        if os.path.lexists(current) and current.is_symlink():
            raise ValueError("Symlink path rejected")
    return path


def artifact(path: Path, *, logical_name: str | None = None) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError(f"Unsafe or missing artifact: {path}")
    result = {
        "bytes": path.stat().st_size,
        "mode": file_mode(path),
        "sha256": sha256(path),
    }
    if logical_name is None:
        result["path"] = path.relative_to(PROJECT_ROOT).as_posix()
    else:
        result["logical_name"] = logical_name
    return result


def require_record(record: dict[str, Any]) -> Path:
    if set(record) != {"path", "bytes", "mode", "sha256"}:
        raise ValueError("Artifact record schema drift")
    path = resolve_project(record["path"])
    if artifact(path) != record:
        raise ValueError(f"Artifact identity drift: {record['path']}")
    return path


def inventory(root: Path) -> set[str]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid artifact root")
    entries = list(root.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise PermissionError("Nested symlink rejected")
    if any(not path.is_file() and not path.is_dir() for path in entries):
        raise PermissionError("Special filesystem entry rejected")
    return {path.relative_to(root).as_posix() for path in entries if path.is_file()}


def read_exact(handle: BinaryIO, size: int) -> bytes:
    value = handle.read(size)
    if len(value) != size:
        raise ValueError("Truncated NPY header")
    return value


def read_npy_header(handle: BinaryIO) -> dict[str, Any]:
    if read_exact(handle, 6) != b"\x93NUMPY":
        raise ValueError("Invalid NPY magic")
    major, minor = read_exact(handle, 2)
    if (major, minor) == (1, 0):
        header_size = struct.unpack("<H", read_exact(handle, 2))[0]
    elif major in (2, 3) and minor == 0:
        header_size = struct.unpack("<I", read_exact(handle, 4))[0]
    else:
        raise ValueError("Unsupported NPY version")
    if header_size <= 0 or header_size > 65536:
        raise ValueError("Unsafe NPY header size")
    header = ast.literal_eval(read_exact(handle, header_size).decode("latin1").strip())
    if set(header) != {"descr", "fortran_order", "shape"}:
        raise ValueError("NPY header schema drift")
    return {
        "dtype": header["descr"],
        "fortran_order": header["fortran_order"],
        "shape": list(header["shape"]),
        "version": [major, minor],
    }


def npz_headers(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        if len({info.filename for info in infos}) != len(infos):
            raise ValueError("Duplicate NPZ member")
        for info in infos:
            if info.is_dir() or info.flag_bits & 1 or not info.filename.endswith(".npy"):
                raise ValueError("Unsafe NPZ member")
            name = info.filename[:-4]
            if not name or "/" in name or "\\" in name:
                raise ValueError("Unsafe NPZ member name")
            with archive.open(info, "r") as handle:
                result[name] = read_npy_header(handle)
    return result


def expected_headers(rows: int, *, fold: bool) -> dict[str, dict[str, Any]]:
    result = {
        "ordinal": {"dtype": "<i4", "fortran_order": False, "shape": [rows]},
        "fold_id": {"dtype": "|i1", "fortran_order": False, "shape": [rows]},
        "token_length": {"dtype": "<i2", "fortran_order": False, "shape": [rows]},
        "standard_hf": {"dtype": "<f4", "fortran_order": False, "shape": [rows, 2560]},
    }
    if fold:
        for name in ("manual_logits", "standard_logits", "reference_logits"):
            result[name] = {"dtype": "<f4", "fortran_order": False, "shape": [rows, 6]}
    for point in POINTS:
        result[POINT_KEYS[point]] = {
            "dtype": "<f4",
            "fortran_order": False,
            "shape": [rows, 2560],
        }
    return result


def normalize_headers(headers: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        key: {name: value for name, value in header.items() if name != "version"}
        for key, header in headers.items()
    }


def environment_identity(executable: str, package_names: list[str]) -> dict[str, Any]:
    code = (
        "import importlib.metadata as m,json,platform,sys;"
        f"names={package_names!r};"
        "print(json.dumps({'python_executable':sys.executable,'python_version':platform.python_version(),"
        "'architecture':platform.machine(),'packages':{name:m.version(name) for name in names}},sort_keys=True))"
    )
    child_environment = dict(os.environ)
    child_environment.update(
        {
            "PYTHONNOUSERSITE": "1",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "OMP_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
        }
    )
    result = subprocess.run(
        [executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env=child_environment,
        timeout=30,
    )
    return json.loads(result.stdout, object_pairs_hook=_unique_object, parse_constant=_no_constant)


def method_digest(config: dict[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json_bytes({key: config[key] for key in METHOD_KEYS})
    ).hexdigest()


def input_digest(config: dict[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json_bytes({key: config[key] for key in INPUT_KEYS})
    ).hexdigest()


def validate_config(config: dict[str, Any]) -> None:
    if set(config) != {
        "schema_version",
        "experiment_id",
        "run_id",
        "attempt_id",
        "rq_id",
        "tier",
        "registered_at",
        "decision",
        "parent_exp069",
        "data",
        "privacy",
        "environments",
        "representation",
        "outer_cv",
        "probe",
        "threshold",
        "metrics",
        "seed_roles",
        "label_shuffle",
        "bootstrap",
        "resources",
        "authorization",
        "access",
        "outputs",
        "implementation",
        "claim_boundary",
    }:
        raise ValueError("EXP-070 config schema drift")
    if (
        config.get("schema_version") != "exp-070-layerwise-probe-preflight-config-v1"
        or config.get("experiment_id") != EXPERIMENT_ID
        or config.get("run_id") != RUN_ID
        or config.get("attempt_id") != ATTEMPT_ID
        or config.get("rq_id") != "RQ-S4.1"
        or config.get("tier") != "Major representation experiment"
        or method_digest(config) != EXPECTED_METHOD_SHA256
        or input_digest(config) != EXPECTED_INPUT_SHA256
    ):
        raise ValueError("EXP-070 frozen config drift")
    if set(config["parent_exp069"]) != {
        "original_config",
        "attempt4_config",
        "recovery_config",
        "attempt4_run",
        "attempt4_failed_verification",
        "smoke_manifest",
        "recovery_verification",
        "completion",
    }:
        raise ValueError("EXP-070 parent inventory drift")
    if set(config["data"]) != {
        "protocol_id",
        "rows",
        "components",
        "task_manifest",
        "train",
        "fold_manifest_public",
        "fold_manifest_private",
        "fold_verification",
    }:
        raise ValueError("EXP-070 data inventory drift")
    if set(config["implementation"]) != {"protocol", "runner", "verifier", "tests"}:
        raise ValueError("EXP-070 implementation inventory drift")
    if set(config["privacy"]) != {"gitignore", "required_rule"} or config["privacy"][
        "required_rule"
    ] != "private/":
        raise ValueError("EXP-070 privacy contract drift")
    if config["outputs"] != {
        "public_root": PUBLIC_ROOT,
        "private_root": PRIVATE_ROOT,
        "formal_public_root": FORMAL_PUBLIC_ROOT,
        "formal_private_root": FORMAL_PRIVATE_ROOT,
        "public_allowlist": ["static.json", "static-verification.json", "no-result-complete.json"],
        "private_allowlist": ["input-contract-manifest.json"],
    }:
        raise ValueError("EXP-070 output namespace drift")


def load_config(path: Path) -> dict[str, Any]:
    if path.resolve() != DEFAULT_CONFIG.resolve():
        raise PermissionError("EXP-070 requires the frozen default config")
    config = strict_json(path)
    validate_config(config)
    return config


def require_config_records(config: dict[str, Any]) -> None:
    require_record(config["decision"])
    for record in config["parent_exp069"].values():
        require_record(record)
    for key in (
        "task_manifest",
        "train",
        "fold_manifest_public",
        "fold_manifest_private",
        "fold_verification",
    ):
        require_record(config["data"][key])
    gitignore_path = require_record(config["privacy"]["gitignore"])
    gitignore_lines = gitignore_path.read_text(encoding="utf-8").splitlines()
    if config["privacy"]["required_rule"] not in gitignore_lines or any(
        line.startswith("!private") for line in gitignore_lines
    ):
        raise ValueError("EXP-070 private ignore rule drift")
    for record in config["implementation"].values():
        require_record(record)


def validate_parent(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    parent = config["parent_exp069"]
    original = strict_json(require_record(parent["original_config"]))
    attempt4 = strict_json(require_record(parent["attempt4_config"]))
    recovery_config = strict_json(require_record(parent["recovery_config"]))
    run = strict_json(require_record(parent["attempt4_run"]))
    failure = strict_json(require_record(parent["attempt4_failed_verification"]))
    verification = strict_json(require_record(parent["recovery_verification"]))
    completion = strict_json(require_record(parent["completion"]))
    smoke_manifest_path = require_record(parent["smoke_manifest"])
    smoke_manifest = strict_json(smoke_manifest_path)
    if (
        attempt4["parent_static"]["config"] != parent["original_config"]
        or recovery_config["source_snapshot"]["config"] != parent["attempt4_config"]
        or recovery_config["source_snapshot"]["run"] != parent["attempt4_run"]
        or recovery_config["source_snapshot"]["failed_verification"]
        != parent["attempt4_failed_verification"]
        or recovery_config["source_snapshot"]["smoke_manifest"] != parent["smoke_manifest"]
        or run.get("status") != "CompletedAwaitingVerification"
        or failure.get("status") != "Failed"
        or verification.get("status") != "Passed"
        or verification.get("passed_count") != 25
        or completion.get("status") != "Complete"
        or completion.get("exp069_complete") is not True
        or completion.get("model_rerun") is not False
        or completion.get("source_mutated") is not False
        or completion.get("run") != parent["attempt4_run"]
        or completion.get("source_failed_verification") != parent["attempt4_failed_verification"]
        or completion.get("recovery_verification") != parent["recovery_verification"]
        or smoke_manifest.get("max_errors") != run.get("max_errors")
        or smoke_manifest.get("coverage")
        != {"base_rows": 32, "seed_fold_rows": 96, "seeds": 3, "folds": 5}
        or original.get("data") != config["data"]
        or original["smoke"]["points"] != list(POINTS)
        or original["smoke"]["hidden_size"] != 2560
        or original["model"]["pooling"] != "last_non_padding_input_token"
        or smoke_manifest_path.parent != resolve_project(attempt4["outputs"]["private_root"])
    ):
        raise ValueError("EXP-069 parent binding drift")
    qwen_source = original["environment"]["qwen3_source"]
    qwen_path = Path(qwen_source["path"])
    if (
        set(qwen_source) != {"path", "bytes", "mode", "sha256"}
        or qwen_path
        != Path(
            "/Users/phoenix/miniconda3/envs/phase-a-runtime/lib/python3.11/"
            "site-packages/mlx_lm/models/qwen3.py"
        )
        or qwen_path.is_symlink()
        or not qwen_path.is_file()
        or qwen_path.stat().st_nlink != 1
        or qwen_path.stat().st_size != qwen_source["bytes"]
        or file_mode(qwen_path) != qwen_source["mode"]
        or sha256(qwen_path) != qwen_source["sha256"]
    ):
        raise ValueError("EXP-070 Qwen source identity drift")
    return attempt4, original


def expected_source_files() -> set[str]:
    return {
        "input-manifest.json",
        "base.npz",
        "base-worker.json",
        "smoke-manifest.json",
        *{
            f"seed-{seed}/fold-{fold}.{suffix}"
            for seed in SEEDS
            for fold in FOLDS
            for suffix in ("npz", "json")
        },
    }


def current_model_records(original: dict[str, Any]) -> dict[str, Any]:
    manifest_path = require_record(original["model"]["qwen_manifest"])
    manifest = strict_json(manifest_path)
    root = resolve_project(original["model"]["base_path"])
    expected_files = manifest["mlx_bf16"]["files"]
    expected_names = {item["path"] for item in expected_files}
    if (
        root.is_symlink()
        or not root.is_dir()
        or file_mode(root) != "0755"
        or inventory(root) != expected_names
        or any(path.is_dir() for path in root.rglob("*"))
        or manifest["repo_id"] != "Qwen/Qwen3-4B"
        or manifest["revision"] != "1cfa9a7208912126459214e8b04321603b3df60c"
        or manifest["mlx_bf16"]["file_count"] != 9
        or manifest["mlx_bf16"]["total_bytes"] != 8056445038
    ):
        raise ValueError("EXP-070 Qwen model-tree contract drift")
    records: dict[str, Any] = {}
    for expected in expected_files:
        path = root / expected["path"]
        observed = artifact(path)
        if (
            path.parent != root
            or observed["bytes"] != expected["bytes"]
            or observed["sha256"] != expected["sha256"]
            or observed["mode"] != "0644"
        ):
            raise ValueError("EXP-070 Qwen model file drift")
        records[expected["path"]] = observed
    return records


def verify_input_contract(
    config: dict[str, Any], manifest: dict[str, Any], original: dict[str, Any]
) -> None:
    smoke_root = require_record(config["parent_exp069"]["smoke_manifest"]).parent
    if file_mode(smoke_root) != "0700" or inventory(smoke_root) != expected_source_files():
        raise PermissionError("EXP-069 source root drift")
    smoke_dirs = {
        path.relative_to(smoke_root).as_posix()
        for path in smoke_root.rglob("*")
        if path.is_dir()
    }
    if smoke_dirs != {"seed-42", "seed-43", "seed-44"}:
        raise ValueError("EXP-069 source directory inventory drift")
    for relative in smoke_dirs:
        if (smoke_root / relative).is_symlink() or file_mode(smoke_root / relative) != "0700":
            raise PermissionError("EXP-069 source seed-directory mode drift")
    if any(file_mode(smoke_root / relative) != "0600" for relative in expected_source_files()):
        raise PermissionError("EXP-069 source private-file mode drift")
    snapshot = manifest.get("source_snapshot")
    if set(snapshot or {}) != {
        "files",
        "npz_headers",
        "checkpoint_files",
        "fold_lineage_files",
        "model_files",
    }:
        raise ValueError("EXP-070 input snapshot schema drift")
    if set(snapshot["files"]) != expected_source_files():
        raise ValueError("EXP-070 input file inventory drift")
    expected_npz = {
        "base.npz",
        *{f"seed-{seed}/fold-{fold}.npz" for seed in SEEDS for fold in FOLDS},
    }
    if set(snapshot["npz_headers"]) != expected_npz:
        raise ValueError("EXP-070 input NPZ inventory drift")
    input_manifest = strict_json(smoke_root / "input-manifest.json")
    sources = input_manifest.get("m3_sources")
    if not isinstance(sources, list) or len(sources) != 15:
        raise ValueError("EXP-069 M3 source inventory drift")
    source_by_pair = {(item.get("seed"), item.get("fold")): item for item in sources}
    if set(source_by_pair) != {(seed, fold) for seed in SEEDS for fold in FOLDS}:
        raise ValueError("EXP-069 M3 source coverage drift")
    expected_checkpoints: dict[str, Any] = {}
    for (seed, fold), source in source_by_pair.items():
        for source_name, record in {
            "adapter": source["adapter"],
            "head": source["head"],
            "heldout": source["heldout_logits"],
        }.items():
            require_record(record)
            expected_checkpoints[f"seed-{seed}/fold-{fold}/{source_name}"] = record
        for source_name in ("evidence", "checkpoint_provenance"):
            record = source.get(source_name)
            if record is None:
                if seed != 42 or source_name != "checkpoint_provenance":
                    raise ValueError("EXP-069 checkpoint provenance drift")
                continue
            require_record(record)
            expected_checkpoints[f"seed-{seed}/fold-{fold}/{source_name}"] = record
    if snapshot["checkpoint_files"] != expected_checkpoints:
        raise ValueError("EXP-070 checkpoint inventory drift")
    if snapshot["model_files"] != current_model_records(original):
        raise ValueError("EXP-070 Qwen model snapshot drift")
    for relative, record in snapshot["files"].items():
        if artifact(smoke_root / relative) != record:
            raise ValueError(f"EXP-070 input artifact drift: {relative}")
    for relative, expected in snapshot["npz_headers"].items():
        current = npz_headers(smoke_root / relative)
        if current != expected:
            raise ValueError(f"EXP-070 NPZ header identity drift: {relative}")
        if relative == "base.npz":
            schema = expected_headers(32, fold=False)
        else:
            fold = int(relative.split("/fold-")[1].split(".")[0])
            schema = expected_headers(FOLD_ROWS[fold], fold=True)
        if normalize_headers(current) != schema:
            raise ValueError(f"EXP-070 NPZ header schema drift: {relative}")
    observed_digest = hashlib.sha256(canonical_json_bytes(snapshot)).hexdigest()
    if observed_digest != manifest.get("source_snapshot_sha256"):
        raise ValueError("EXP-070 input snapshot digest drift")
    source_manifest = strict_json(smoke_root / "smoke-manifest.json")
    if (
        source_manifest.get("coverage")
        != {"base_rows": 32, "seed_fold_rows": 96, "seeds": 3, "folds": 5}
        or source_manifest.get("input_manifest")
        != artifact(smoke_root / "input-manifest.json", logical_name="input-manifest.json")
    ):
        raise ValueError("EXP-069 source coverage or input binding drift")
    base_worker = strict_json(smoke_root / "base-worker.json")
    if (
        base_worker != source_manifest.get("base_worker")
        or base_worker.get("rows") != 32
        or base_worker.get("output")
        != artifact(smoke_root / "base.npz", logical_name="base.npz")
    ):
        raise ValueError("EXP-069 source base-worker binding drift")
    workers = source_manifest.get("fold_workers")
    if not isinstance(workers, list) or len(workers) != 15:
        raise ValueError("EXP-069 source fold-worker inventory drift")
    total_rows = 0
    for index, worker in enumerate(workers):
        seed = SEEDS[index // 5]
        fold = FOLDS[index % 5]
        relative_json = f"seed-{seed}/fold-{fold}.json"
        relative_npz = f"seed-{seed}/fold-{fold}.npz"
        if (
            worker != strict_json(smoke_root / relative_json)
            or worker.get("seed") != seed
            or worker.get("fold") != fold
            or worker.get("rows") != FOLD_ROWS[fold]
            or worker.get("output")
            != artifact(smoke_root / relative_npz, logical_name=relative_npz)
            or worker.get("source_before") != worker.get("source_after")
        ):
            raise ValueError("EXP-069 source fold-worker binding drift")
        source = source_by_pair[(seed, fold)]
        expected_worker_sources = {
            "adapter": source["adapter"],
            "head": source["head"],
            "heldout": source["heldout_logits"],
        }
        if worker.get("source_before") != expected_worker_sources:
            raise ValueError("EXP-070 worker/source-manifest drift")
        for source_name, record in expected_worker_sources.items():
            key = f"seed-{seed}/fold-{fold}/{source_name}"
            if snapshot["checkpoint_files"].get(key) != record:
                raise ValueError("EXP-070 checkpoint snapshot binding drift")
            require_record(record)
        total_rows += int(worker["rows"])
    if total_rows != 96:
        raise ValueError("EXP-069 source fold-worker coverage drift")
    expected_lineage: dict[str, Any] = {}
    for lineage in original["m3_lineage"]:
        seed = int(lineage["seed"])
        for record_index, record in enumerate(lineage["aggregate_records"]):
            require_record(record)
            expected_lineage[f"seed-{seed}/aggregate-{record_index}"] = record
        for fold in FOLDS:
            source = source_by_pair[(seed, fold)]
            for kind, template_key in (("run", "run_template"), ("verification", "verification_template")):
                record = source[kind]
                if record["path"] != lineage[template_key].format(fold=fold):
                    raise ValueError("EXP-069 fold lineage path drift")
                path = require_record(record)
                value = strict_json(path)
                if (
                    kind == "run" and value.get("status") != "CompletedAwaitingVerification"
                ) or (
                    kind == "verification"
                    and (
                        value.get("status") != "Passed"
                        or value.get("passed_count") != lineage["fold_verification_checks"]
                    )
                ):
                    raise ValueError("EXP-069 fold lineage state drift")
                expected_lineage[f"seed-{seed}/fold-{fold}/{kind}"] = record
    if snapshot["fold_lineage_files"] != expected_lineage:
        raise ValueError("EXP-070 fold lineage snapshot drift")


def public_sensitive(value: Any) -> bool:
    if isinstance(value, dict):
        return any(public_sensitive(key) for key in value) or any(
            public_sensitive(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(public_sensitive(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return any(
            marker in lowered
            for marker in ("/users/", "phase-b-representation/private/", "sample-", "component-")
        )
    return False


def create_json_once(path: Path, value: Any) -> None:
    if os.path.lexists(path):
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    os.chmod(path.parent, 0o755)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    if os.path.lexists(temporary):
        raise FileExistsError(temporary)
    try:
        with temporary.open("xb") as handle:
            handle.write(canonical_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.link(temporary, path)
    finally:
        if os.path.lexists(temporary):
            temporary.unlink()


def verify(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    require_config_records(config)
    if {name.split(".")[0] for name in sys.modules} & FORBIDDEN_MODULES:
        raise RuntimeError("EXP-070 verifier imported a forbidden library")
    attempt4, original = validate_parent(config)
    public_root = resolve_project(config["outputs"]["public_root"])
    private_root = resolve_project(config["outputs"]["private_root"])
    if inventory(public_root) != {"static.json"} or file_mode(public_root) != "0755":
        raise ValueError("EXP-070 public preverification inventory drift")
    if inventory(private_root) != {"input-contract-manifest.json"} or file_mode(private_root) != "0700":
        raise ValueError("EXP-070 private preverification inventory drift")
    if any(path.is_dir() for path in public_root.rglob("*")) or any(
        path.is_dir() for path in private_root.rglob("*")
    ):
        raise ValueError("EXP-070 preverification directory inventory drift")
    if file_mode(public_root / "static.json") != "0644" or file_mode(private_root.parent) != "0700":
        raise PermissionError("EXP-070 preverification mode drift")
    private_manifest_path = private_root / "input-contract-manifest.json"
    if file_mode(private_manifest_path) != "0600":
        raise PermissionError("EXP-070 private manifest mode drift")
    report = strict_json(public_root / "static.json")
    manifest = strict_json(private_manifest_path)
    if set(report) != {
        "schema_version",
        "experiment_id",
        "run_id",
        "attempt_id",
        "stage",
        "status",
        "config",
        "parent_completion",
        "input_contract",
        "counts",
        "representation_points",
        "decision_metric",
        "source_snapshot_sha256",
        "environments",
        "resources",
        "authorization",
        "access",
        "claim_boundary",
    }:
        raise ValueError("EXP-070 public report schema drift")
    if set(report.get("environments", {})) != {"extractor", "probe"} or set(
        report.get("resources", {})
    ) != {
        "projected_extraction_hours",
        "raw_representation_bytes",
        "private_disk_budget_bytes",
        "minimum_free_disk_bytes",
        "observed_free_disk_bytes",
    }:
        raise ValueError("EXP-070 public nested schema drift")
    if set(manifest) != {
        "schema_version",
        "experiment_id",
        "run_id",
        "attempt_id",
        "status",
        "config",
        "parent_completion",
        "parent_smoke_manifest",
        "source_snapshot_sha256",
        "source_snapshot",
        "smoke_rows_usable_for_probe_fitting",
        "formal_representation_plan",
        "access",
    }:
        raise ValueError("EXP-070 private manifest schema drift")
    expected_access = {
        "public_parent_json_read": True,
        "private_manifest_metadata_read": True,
        "private_file_identity_read": True,
        "train_file_bytes_hashed": True,
        "checkpoint_file_bytes_hashed": True,
        "model_file_bytes_hashed": True,
        "npz_headers_read": True,
        "npz_array_values_read": False,
        "train_rows_parsed": False,
        "train_text_values_used": False,
        "train_label_values_used": False,
        "historical_logit_values_read": False,
        "validation_accessed": False,
        "test_accessed": False,
        "model_loaded": False,
        "forward_executed": False,
        "real_probe_fitted": False,
        "performance_metrics_computed": False,
    }
    if (
        report.get("schema_version") != "exp-070-no-result-preflight-v1"
        or report.get("experiment_id") != EXPERIMENT_ID
        or report.get("run_id") != RUN_ID
        or report.get("attempt_id") != ATTEMPT_ID
        or report.get("stage") != "no-result-preflight"
        or report.get("status") != "CompletedAwaitingVerification"
        or report.get("claim_boundary") != config["claim_boundary"]
        or report.get("config") != artifact(config_path)
        or report.get("parent_completion") != config["parent_exp069"]["completion"]
        or report.get("input_contract")
        != artifact(private_manifest_path, logical_name="input-contract-manifest.json")
        or report.get("authorization") != config["authorization"]
        or report.get("access") != manifest.get("access")
        or manifest.get("schema_version") != "exp-070-input-contract-manifest-v1"
        or manifest.get("experiment_id") != EXPERIMENT_ID
        or manifest.get("run_id") != RUN_ID
        or manifest.get("attempt_id") != ATTEMPT_ID
        or manifest.get("status") != "Registered"
        or manifest.get("config") != artifact(config_path)
        or manifest.get("parent_completion") != config["parent_exp069"]["completion"]
        or manifest.get("parent_smoke_manifest") != config["parent_exp069"]["smoke_manifest"]
        or manifest.get("smoke_rows_usable_for_probe_fitting") is not False
        or manifest.get("formal_representation_plan") != config["representation"]
        or manifest.get("access") != expected_access
        or report.get("counts")
        != {
            "source_private_files": 34,
            "source_npz_files": 16,
            "smoke_rows": 32,
            "formal_rows": 3360,
            "formal_model_workers": 16,
            "formal_representation_matrices": 16,
            "maximum_binary_probe_fits": 4320,
        }
        or report.get("representation_points") != list(POINTS)
        or report.get("decision_metric") != config["metrics"]["primary"]
        or report.get("resources", {}).get("projected_extraction_hours")
        != config["resources"]["projected_extraction_hours"]
        or report.get("resources", {}).get("raw_representation_bytes")
        != config["representation"]["raw_bytes"]
        or report.get("resources", {}).get("private_disk_budget_bytes")
        != config["resources"]["private_disk_budget_bytes"]
        or report.get("resources", {}).get("minimum_free_disk_bytes")
        != config["resources"]["minimum_free_disk_bytes"]
    ):
        raise ValueError("EXP-070 runner output binding drift")
    verify_input_contract(config, manifest, original)
    if report.get("source_snapshot_sha256") != manifest.get("source_snapshot_sha256"):
        raise ValueError("EXP-070 public/private snapshot binding drift")
    for role in ("extractor", "probe"):
        current = environment_identity(
            config["environments"][role]["python_executable"],
            list(config["environments"][role]["packages"]),
        )
        if current != config["environments"][role]:
            raise PermissionError(f"EXP-070 {role} environment drift")
        public_environment = {key: value for key, value in current.items() if key != "python_executable"}
        if report["environments"][role] != public_environment:
            raise ValueError(f"EXP-070 {role} public environment drift")
    if sys.executable != config["environments"]["probe"]["python_executable"]:
        raise PermissionError("EXP-070 verifier must run in the probe environment")
    free_bytes = shutil.disk_usage(PROJECT_ROOT).free
    if (
        free_bytes < config["resources"]["minimum_free_disk_bytes"]
        or int(report["resources"]["observed_free_disk_bytes"])
        < config["resources"]["minimum_free_disk_bytes"]
    ):
        raise OSError("EXP-070 verifier free-disk gate failed")
    for key in ("formal_public_root", "formal_private_root"):
        if os.path.lexists(resolve_project(config["outputs"][key])):
            raise FileExistsError("EXP-070 formal output exists")
    if public_sensitive(report):
        raise ValueError("EXP-070 public privacy drift")
    runner_path = require_record(config["implementation"]["runner"])
    verifier_path = require_record(config["implementation"]["verifier"])
    for path in (runner_path, verifier_path):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        if imports & FORBIDDEN_MODULES:
            raise RuntimeError("EXP-070 implementation imports a forbidden library")
    if {name.split(".")[0] for name in sys.modules} & FORBIDDEN_MODULES:
        raise RuntimeError("EXP-070 verifier imported a forbidden library")
    if attempt4["scope"]["exp070"] is not False:
        raise ValueError("EXP-069 parent scope drift")
    checks = [
        "config_identity",
        "method_contract_identity",
        "implementation_identity",
        "phase_b_decision_identity",
        "exp069_completion_binding",
        "exp069_failed_verification_preserved",
        "source_public_private_lineage",
        "source_private_inventory",
        "source_private_modes",
        "source_no_symlinks",
        "source_file_identities",
        "base_npz_header_schema",
        "fold_npz_header_schemas",
        "smoke_not_formal_input",
        "formal_output_absence",
        "extractor_environment",
        "probe_environment",
        "free_disk_gate",
        "access_boundary",
        "authorization_boundary",
        "no_model_import",
        "no_array_value_read",
        "no_probe_fit_or_metrics",
        "public_privacy",
    ]
    verification = {
        "schema_version": "exp-070-no-result-preflight-verification-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "stage": "no-result-preflight",
        "status": "Passed",
        "passed_count": len(checks),
        "failed_count": 0,
        "checks": checks,
        "config": artifact(config_path),
        "run": artifact(public_root / "static.json"),
        "input_contract": artifact(private_manifest_path, logical_name="input-contract-manifest.json"),
        "source_snapshot_sha256": manifest["source_snapshot_sha256"],
        "formal_execution_authorized": False,
        "model_libraries_imported": False,
        "runner_imported": False,
        "access": manifest["access"],
        "claim_boundary": config["claim_boundary"],
    }
    if public_sensitive(verification):
        raise ValueError("EXP-070 verification privacy drift")
    verification_path = public_root / "static-verification.json"
    create_json_once(verification_path, verification)
    if inventory(public_root) != {"static.json", "static-verification.json"} or any(
        file_mode(public_root / name) != "0644"
        for name in ("static.json", "static-verification.json")
    ):
        raise ValueError("EXP-070 precompletion public state drift")
    completion = {
        "schema_version": "exp-070-no-result-preflight-complete-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "Complete",
        "formal_execution_authorized": False,
        "exp070_formal_complete": False,
        "exp071_authorized": False,
        "run": artifact(public_root / "static.json"),
        "verification": artifact(verification_path),
        "input_contract": artifact(private_manifest_path, logical_name="input-contract-manifest.json"),
        "parent_exp069_completion": config["parent_exp069"]["completion"],
        "parent_attempt4_config": config["parent_exp069"]["attempt4_config"],
        "claim_boundary": config["claim_boundary"],
        "next_gate": "EXP-070 formal extraction and probe consumer remains unexecuted",
    }
    create_json_once(public_root / "no-result-complete.json", completion)
    if inventory(public_root) != set(config["outputs"]["public_allowlist"]):
        raise ValueError("EXP-070 terminal public inventory drift")
    if any(file_mode(public_root / name) != "0644" for name in config["outputs"]["public_allowlist"]):
        raise PermissionError("EXP-070 terminal public mode drift")
    return verification


def record_failure(config: dict[str, Any], error: BaseException) -> None:
    try:
        root = resolve_project(config["outputs"]["public_root"])
        target = root / "static-verification.json"
        if os.path.lexists(target):
            return
        value = {
            "schema_version": "exp-070-no-result-preflight-verification-failure-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "attempt_id": ATTEMPT_ID,
            "stage": "no-result-preflight",
            "status": "Failed",
            "error_type": type(error).__name__,
            "claim_boundary": config.get("claim_boundary"),
        }
        create_json_once(target, value)
    except Exception:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify EXP-070 no-result preflight")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    try:
        result = verify(args.config, config)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        record_failure(config, error)
        raise
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
