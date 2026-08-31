#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
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
INPUT_KEYS = ("decision", "parent_exp069", "data", "privacy")
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
    if type(header["descr"]) is not str or type(header["fortran_order"]) is not bool:
        raise ValueError("NPY header type drift")
    if not isinstance(header["shape"], tuple) or any(type(value) is not int for value in header["shape"]):
        raise ValueError("NPY shape drift")
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


def expected_base_headers() -> dict[str, dict[str, Any]]:
    result = {
        "ordinal": {"dtype": "<i4", "fortran_order": False, "shape": [32]},
        "fold_id": {"dtype": "|i1", "fortran_order": False, "shape": [32]},
        "token_length": {"dtype": "<i2", "fortran_order": False, "shape": [32]},
        "standard_hf": {"dtype": "<f4", "fortran_order": False, "shape": [32, 2560]},
    }
    for point in POINTS:
        result[POINT_KEYS[point]] = {
            "dtype": "<f4",
            "fortran_order": False,
            "shape": [32, 2560],
        }
    return result


def expected_fold_headers(rows: int) -> dict[str, dict[str, Any]]:
    result = {
        "ordinal": {"dtype": "<i4", "fortran_order": False, "shape": [rows]},
        "fold_id": {"dtype": "|i1", "fortran_order": False, "shape": [rows]},
        "token_length": {"dtype": "<i2", "fortran_order": False, "shape": [rows]},
        "standard_hf": {"dtype": "<f4", "fortran_order": False, "shape": [rows, 2560]},
        "manual_logits": {"dtype": "<f4", "fortran_order": False, "shape": [rows, 6]},
        "standard_logits": {"dtype": "<f4", "fortran_order": False, "shape": [rows, 6]},
        "reference_logits": {"dtype": "<f4", "fortran_order": False, "shape": [rows, 6]},
    }
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


def validate_config(config: dict[str, Any]) -> None:
    expected_keys = {
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
    }
    if set(config) != expected_keys:
        raise ValueError("EXP-070 config schema drift")
    if (
        config["schema_version"] != "exp-070-layerwise-probe-preflight-config-v1"
        or config["experiment_id"] != EXPERIMENT_ID
        or config["run_id"] != RUN_ID
        or config["attempt_id"] != ATTEMPT_ID
        or config["rq_id"] != "RQ-S4.1"
        or config["tier"] != "Major representation experiment"
    ):
        raise ValueError("EXP-070 config identity drift")
    input_digest = hashlib.sha256(
        canonical_json_bytes({key: config[key] for key in INPUT_KEYS})
    ).hexdigest()
    if input_digest != EXPECTED_INPUT_SHA256:
        raise ValueError("EXP-070 frozen input binding drift")
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
    if config["environments"] != {
        "extractor": {
            "python_executable": "/Users/phoenix/miniconda3/envs/phase-a-runtime/bin/python",
            "python_version": "3.11.15",
            "architecture": "arm64",
            "packages": {
                "numpy": "2.4.6",
                "mlx": "0.32.0",
                "mlx-lm": "0.31.3",
                "safetensors": "0.8.0",
                "tokenizers": "0.22.2",
                "transformers": "5.14.1",
            },
        },
        "probe": {
            "python_executable": "/Users/phoenix/miniconda3/envs/emotion-roberta/bin/python",
            "python_version": "3.10.20",
            "architecture": "arm64",
            "packages": {
                "numpy": "2.2.6",
                "scikit-learn": "1.7.2",
                "scipy": "1.15.3",
                "joblib": "1.5.3",
            },
        },
    }:
        raise ValueError("EXP-070 environment contract drift")
    if config["representation"] != {
        "rows": 3360,
        "hidden_size": 2560,
        "dtype": "float32",
        "layout": "C",
        "row_order": "DATA_SO_TASK_V1_train_source_order_0_to_3359",
        "private_row_identity_digests": [
            "ordinal_sha256",
            "sample_id_order_sha256",
            "component_id_order_sha256",
            "fold_id_order_sha256",
            "token_id_stream_sha256",
        ],
        "seed42_points": list(POINTS),
        "confirmation_points": ["H19", "H27", "HF"],
        "pre_lora_points": ["H-1", "H7", "H15", "H19"],
        "transient_pre_lora_points_for_confirmation_seeds": ["H-1", "H7", "H15"],
        "comparison_dtype": "float32",
        "pre_lora_rtol": 0.0,
        "pre_lora_atol": 0.00001,
        "base_matrices": 1,
        "m3_matrices": 15,
        "raw_bytes": 2890137600,
        "smoke_rows_usable_for_fitting": False,
    }:
        raise ValueError("EXP-070 representation contract drift")
    if config["outer_cv"] != {
        "folds": 5,
        "outer_train_rows": 2688,
        "outer_heldout_rows": 672,
        "inner_folds": "remaining_four_frozen_outer_fold_ids",
        "inner_train_rows": 2016,
        "inner_heldout_rows": 672,
        "new_split_generation": False,
        "same_m3_checkpoint_for_outer_train_and_heldout": True,
        "scientific_evidence_rows": "outer_heldout_only",
    }:
        raise ValueError("EXP-070 CV contract drift")
    if config["probe"] != {
        "scaler": {"with_mean": True, "with_std": True},
        "independent_binary_classifiers": 6,
        "input_cast": "float64",
        "penalty": "l2",
        "dual": False,
        "C": 1.0,
        "solver": "liblinear",
        "class_weight": None,
        "fit_intercept": True,
        "intercept_scaling": 1.0,
        "tol": 0.0001,
        "max_iter": 2000,
        "random_state": 42,
        "convergence_failure": "stop",
    }:
        raise ValueError("EXP-070 probe contract drift")
    if config["threshold"] != {
        "grid_start": 0.05,
        "grid_stop": 0.95,
        "grid_step": 0.01,
        "grid_count": 91,
        "shared_across_labels": True,
        "prediction_rule": "probability_gte_threshold",
        "comparison_tolerance": 1e-12,
        "zero_division": 0,
        "selection_order": [
            "highest_five_label_macro_f1",
            "lowest_six_label_hamming_loss_within_1e-12",
            "closest_to_0_5",
            "lower_threshold",
        ],
        "outer_heldout_selection_access": False,
    }:
        raise ValueError("EXP-070 threshold contract drift")
    if config["metrics"] != {
        "primary": "five_label_macro_average_precision",
        "primary_labels": ["love", "joy", "anger", "sadness", "fear"],
        "full_label_order": ["love", "joy", "surprise", "anger", "sadness", "fear"],
        "average_precision_implementation": "sklearn.metrics.average_precision_score",
        "secondary": [
            "six_label_macro_ap",
            "six_label_macro_f1",
            "five_label_macro_f1",
            "micro_ap",
            "micro_f1",
            "hamming_loss",
            "subset_accuracy",
            "per_label_ap",
            "per_label_f1",
        ],
    }:
        raise ValueError("EXP-070 metric contract drift")
    if config["seed_roles"] != {
        "discovery_seed": 42,
        "discovery_points": list(POINTS),
        "prospective_seeds": [43, 44],
        "confirmation_points": ["H19", "H27", "HF"],
        "voting_points": ["H27", "HF"],
        "seed_pass": "both_voting_points_delta_positive_and_bootstrap_lower_gt_zero",
        "states": {
            "2": "Representation effect replicated",
            "1": "Representation effect seed-sensitive",
            "0": "No replicated representation effect",
        },
    }:
        raise ValueError("EXP-070 seed-role drift")
    if config["label_shuffle"] != {
        "points": ["H27", "HF"],
        "seeds": [2026082711, 2026082712, 2026082713],
        "bit_generator": "PCG64",
        "seed_sequence": ["shuffle_seed", "outer_fold"],
        "permute": "complete_six_label_rows_within_outer_train",
        "outer_heldout_labels_used_for_permutation": False,
        "inner_threshold_selection": False,
        "metrics": ["five_label_macro_ap", "six_label_macro_ap", "per_label_ap"],
        "contrast": "3360_row_OOF_five_label_macro_AP_M3_shuffled_r_minus_Frozen_shuffled_r",
        "maximum_binary_fits_including_main": 4320,
        "negative_control_failure": "same_2_of_2_prospective_seed_pass_at_H27_and_HF",
        "failure_trigger": "any_of_three_shuffle_replicates",
        "failure_effect": "validity_failure_blocks_all_representation_states",
    }:
        raise ValueError("EXP-070 shuffle contract drift")
    if config["bootstrap"] != {
        "replicates": 2000,
        "bit_generator": "PCG64",
        "seed": 2026082701,
        "unit": "duplicate_component_within_outer_fold",
        "paired_plan_shared_across_all_conditions": True,
        "refit_probe": False,
        "reselect_threshold": False,
        "percentiles": [2.5, 97.5],
        "validity_labels": "all_six_positive_and_negative",
        "invalid_replicate": "stop_without_redraw",
    }:
        raise ValueError("EXP-070 bootstrap contract drift")
    if config["authorization"] != {
        "no_result_preflight": True,
        "formal_extraction": False,
        "model_loading": False,
        "forward": False,
        "real_probe_fitting": False,
        "threshold_selection": False,
        "bootstrap": False,
        "performance_metrics": False,
        "formal_completion": False,
        "exp071": False,
    }:
        raise PermissionError("EXP-070 authorization drift")
    if config["access"] != {
        "public_parent_json": True,
        "private_manifest_metadata": True,
        "private_file_identity": True,
        "npz_headers": True,
        "npz_array_values": False,
        "train_file_bytes_hash": True,
        "train_rows_parse": False,
        "train_text_values": False,
        "train_label_values": False,
        "historical_logit_values": False,
        "validation": False,
        "test": False,
        "gold": False,
    }:
        raise PermissionError("EXP-070 access drift")
    if config["resources"] != {
        "projected_extraction_hours": 38.044064278744436,
        "model_workers": 16,
        "maximum_concurrent_heavy_workers": 1,
        "worker_wall_hours": 4,
        "aggregate_model_wall_hours": 64,
        "worker_peak_mlx_gb": 10.0,
        "private_disk_budget_bytes": 5368709120,
        "minimum_free_disk_bytes": 10737418240,
        "maximum_concurrent_probe_workers": 1,
        "maximum_binary_probe_fits": 4320,
        "probe_wall_hours": 12,
        "probe_peak_rss_gb": 8.0,
        "api_cost_usd": 0,
    }:
        raise ValueError("EXP-070 resource contract drift")
    if config["outputs"] != {
        "public_root": PUBLIC_ROOT,
        "private_root": PRIVATE_ROOT,
        "formal_public_root": FORMAL_PUBLIC_ROOT,
        "formal_private_root": FORMAL_PRIVATE_ROOT,
        "public_allowlist": ["static.json", "static-verification.json", "no-result-complete.json"],
        "private_allowlist": ["input-contract-manifest.json"],
    }:
        raise ValueError("EXP-070 output contract drift")


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
    recovery_verification = strict_json(require_record(parent["recovery_verification"]))
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
        or recovery_verification.get("status") != "Passed"
        or recovery_verification.get("passed_count") != 25
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
    ):
        raise ValueError("EXP-069 parent binding drift")
    if original["data"] != config["data"]:
        raise ValueError("EXP-070 data contract differs from EXP-069")
    if original["smoke"]["points"] != list(POINTS) or original["smoke"]["hidden_size"] != 2560:
        raise ValueError("EXP-070 representation points drift")
    if original["model"]["pooling"] != "last_non_padding_input_token":
        raise ValueError("EXP-070 pooling drift")
    qwen_source = original["environment"]["qwen3_source"]
    if set(qwen_source) != {"path", "bytes", "mode", "sha256"}:
        raise ValueError("EXP-070 Qwen source record drift")
    qwen_path = Path(qwen_source["path"])
    if (
        qwen_path != Path(
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
    if smoke_manifest_path.parent != resolve_project(attempt4["outputs"]["private_root"]):
        raise ValueError("EXP-070 smoke root drift")
    return original, smoke_manifest


def validate_smoke_files(
    original: dict[str, Any], smoke_manifest: dict[str, Any], smoke_root: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    expected_inventory = {
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
    if file_mode(smoke_root) != "0700" or inventory(smoke_root) != expected_inventory:
        raise PermissionError("EXP-069 private smoke inventory or mode drift")
    observed_dirs = {
        path.relative_to(smoke_root).as_posix()
        for path in smoke_root.rglob("*")
        if path.is_dir()
    }
    if observed_dirs != {"seed-42", "seed-43", "seed-44"}:
        raise ValueError("EXP-069 private smoke directory inventory drift")
    for seed in SEEDS:
        seed_dir = smoke_root / f"seed-{seed}"
        if seed_dir.is_symlink() or file_mode(seed_dir) != "0700":
            raise PermissionError("EXP-069 seed directory drift")
    file_records: dict[str, Any] = {}
    for relative in sorted(expected_inventory):
        path = smoke_root / relative
        if file_mode(path) != "0600":
            raise PermissionError(f"EXP-069 private mode drift: {relative}")
        file_records[relative] = artifact(path)
    base_worker = strict_json(smoke_root / "base-worker.json")
    if base_worker != smoke_manifest["base_worker"]:
        raise ValueError("EXP-069 base worker manifest drift")
    base_path = smoke_root / base_worker["output"]["logical_name"]
    if artifact(base_path, logical_name="base.npz") != base_worker["output"]:
        raise ValueError("EXP-069 base NPZ identity drift")
    headers: dict[str, Any] = {"base.npz": npz_headers(base_path)}
    if normalize_headers(headers["base.npz"]) != expected_base_headers():
        raise ValueError("EXP-069 base NPZ header drift")
    if len(smoke_manifest["fold_workers"]) != 15:
        raise ValueError("EXP-069 fold-worker count drift")
    input_manifest = strict_json(smoke_root / "input-manifest.json")
    sources = input_manifest.get("m3_sources")
    if not isinstance(sources, list) or len(sources) != 15:
        raise ValueError("EXP-069 M3 source inventory drift")
    source_by_pair = {(item.get("seed"), item.get("fold")): item for item in sources}
    if set(source_by_pair) != {(seed, fold) for seed in SEEDS for fold in FOLDS}:
        raise ValueError("EXP-069 M3 source coverage drift")
    checkpoint_records: dict[str, Any] = {}
    lineage_records: dict[str, Any] = {}
    for index, worker in enumerate(smoke_manifest["fold_workers"]):
        seed = SEEDS[index // 5]
        fold = FOLDS[index % 5]
        relative_json = f"seed-{seed}/fold-{fold}.json"
        relative_npz = f"seed-{seed}/fold-{fold}.npz"
        if worker != strict_json(smoke_root / relative_json):
            raise ValueError("EXP-069 fold worker manifest drift")
        if worker.get("seed") != seed or worker.get("fold") != fold or worker.get("rows") != FOLD_ROWS[fold]:
            raise ValueError("EXP-069 fold worker identity drift")
        if artifact(smoke_root / relative_npz, logical_name=relative_npz) != worker["output"]:
            raise ValueError("EXP-069 fold NPZ identity drift")
        source = source_by_pair[(seed, fold)]
        expected_worker_sources = {
            "adapter": source["adapter"],
            "head": source["head"],
            "heldout": source["heldout_logits"],
        }
        if (
            worker.get("source_before") != worker.get("source_after")
            or worker.get("source_before") != expected_worker_sources
            or source.get("heldout_inventory")
            != {"members_read": ["sample_ids", "fold_ids", "logits"], "rows": 672}
        ):
            raise ValueError("EXP-069 checkpoint source binding drift")
        for source_name, record in expected_worker_sources.items():
            require_record(record)
            checkpoint_records[f"seed-{seed}/fold-{fold}/{source_name}"] = record
        for source_name in ("evidence", "checkpoint_provenance"):
            record = source.get(source_name)
            if record is None:
                if seed != 42 or source_name != "checkpoint_provenance":
                    raise ValueError("EXP-069 checkpoint provenance drift")
                continue
            require_record(record)
            checkpoint_records[f"seed-{seed}/fold-{fold}/{source_name}"] = record
        lineage = next(item for item in original["m3_lineage"] if item["seed"] == seed)
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
            lineage_records[f"seed-{seed}/fold-{fold}/{kind}"] = record
        headers[relative_npz] = npz_headers(smoke_root / relative_npz)
        if normalize_headers(headers[relative_npz]) != expected_fold_headers(FOLD_ROWS[fold]):
            raise ValueError("EXP-069 fold NPZ header drift")
    for lineage in original["m3_lineage"]:
        seed = int(lineage["seed"])
        for record_index, record in enumerate(lineage["aggregate_records"]):
            require_record(record)
            lineage_records[f"seed-{seed}/aggregate-{record_index}"] = record
    return file_records, headers, checkpoint_records, lineage_records


def validate_model_tree(original: dict[str, Any]) -> dict[str, Any]:
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
            for marker in (
                "/users/",
                "phase-b-representation/private/",
                "sample-",
                "component-",
                "input-contract-manifest.json/",
            )
        )
    return False


def create_json_once(path: Path, value: Any, *, private: bool = False) -> None:
    if os.path.lexists(path):
        raise FileExistsError(path)
    mode = 0o600 if private else 0o644
    directory_mode = 0o700 if private else 0o755
    path.parent.mkdir(parents=True, exist_ok=True, mode=directory_mode)
    os.chmod(path.parent, directory_mode)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    if os.path.lexists(temporary):
        raise FileExistsError(temporary)
    try:
        with temporary.open("xb") as handle:
            handle.write(canonical_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.link(temporary, path)
    finally:
        if os.path.lexists(temporary):
            temporary.unlink()


def run(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    require_config_records(config)
    public_root = resolve_project(config["outputs"]["public_root"])
    private_root = resolve_project(config["outputs"]["private_root"])
    formal_public = resolve_project(config["outputs"]["formal_public_root"])
    formal_private = resolve_project(config["outputs"]["formal_private_root"])
    for path in (public_root, private_root, formal_public, formal_private):
        if os.path.lexists(path):
            raise FileExistsError(f"EXP-070 output root exists: {path}")
    if {name.split(".")[0] for name in sys.modules} & FORBIDDEN_MODULES:
        raise RuntimeError("EXP-070 preflight imported a forbidden library")
    original, smoke_manifest = validate_parent(config)
    smoke_root = require_record(config["parent_exp069"]["smoke_manifest"]).parent
    file_records, headers, checkpoint_records, lineage_records = validate_smoke_files(
        original, smoke_manifest, smoke_root
    )
    model_records = validate_model_tree(original)
    extractor_environment = environment_identity(
        config["environments"]["extractor"]["python_executable"],
        list(config["environments"]["extractor"]["packages"]),
    )
    probe_environment = environment_identity(
        config["environments"]["probe"]["python_executable"],
        list(config["environments"]["probe"]["packages"]),
    )
    if extractor_environment != config["environments"]["extractor"]:
        raise PermissionError("EXP-070 extractor environment drift")
    if probe_environment != config["environments"]["probe"]:
        raise PermissionError("EXP-070 probe environment drift")
    if sys.executable != config["environments"]["probe"]["python_executable"]:
        raise PermissionError("EXP-070 preflight must run in the probe environment")
    free_bytes = shutil.disk_usage(PROJECT_ROOT).free
    if free_bytes < config["resources"]["minimum_free_disk_bytes"]:
        raise OSError("EXP-070 free-disk gate failed")
    if {name.split(".")[0] for name in sys.modules} & FORBIDDEN_MODULES:
        raise RuntimeError("EXP-070 preflight imported a forbidden library")

    source_snapshot = {
        "files": file_records,
        "npz_headers": headers,
        "checkpoint_files": checkpoint_records,
        "fold_lineage_files": lineage_records,
        "model_files": model_records,
    }
    snapshot_sha256 = hashlib.sha256(canonical_json_bytes(source_snapshot)).hexdigest()
    private_manifest = {
        "schema_version": "exp-070-input-contract-manifest-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "Registered",
        "config": artifact(config_path),
        "parent_completion": config["parent_exp069"]["completion"],
        "parent_smoke_manifest": config["parent_exp069"]["smoke_manifest"],
        "source_snapshot_sha256": snapshot_sha256,
        "source_snapshot": source_snapshot,
        "smoke_rows_usable_for_probe_fitting": False,
        "formal_representation_plan": config["representation"],
        "access": {
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
        },
    }
    private_root.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(private_root.parent, 0o700)
    private_root.mkdir(mode=0o700)
    os.chmod(private_root, 0o700)
    private_manifest_path = private_root / "input-contract-manifest.json"
    create_json_once(private_manifest_path, private_manifest, private=True)
    report = {
        "schema_version": "exp-070-no-result-preflight-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "attempt_id": ATTEMPT_ID,
        "stage": "no-result-preflight",
        "status": "CompletedAwaitingVerification",
        "config": artifact(config_path),
        "parent_completion": config["parent_exp069"]["completion"],
        "input_contract": artifact(private_manifest_path, logical_name="input-contract-manifest.json"),
        "counts": {
            "source_private_files": 34,
            "source_npz_files": 16,
            "smoke_rows": 32,
            "formal_rows": 3360,
            "formal_model_workers": 16,
            "formal_representation_matrices": 16,
            "maximum_binary_probe_fits": 4320,
        },
        "representation_points": list(POINTS),
        "decision_metric": config["metrics"]["primary"],
        "source_snapshot_sha256": snapshot_sha256,
        "environments": {
            "extractor": {
                key: value for key, value in extractor_environment.items() if key != "python_executable"
            },
            "probe": {
                key: value for key, value in probe_environment.items() if key != "python_executable"
            },
        },
        "resources": {
            "projected_extraction_hours": config["resources"]["projected_extraction_hours"],
            "raw_representation_bytes": config["representation"]["raw_bytes"],
            "private_disk_budget_bytes": config["resources"]["private_disk_budget_bytes"],
            "minimum_free_disk_bytes": config["resources"]["minimum_free_disk_bytes"],
            "observed_free_disk_bytes": free_bytes,
        },
        "authorization": config["authorization"],
        "access": private_manifest["access"],
        "claim_boundary": config["claim_boundary"],
    }
    if original["authorization"]["performance_metrics_authorized"] is not False:
        raise ValueError("EXP-069 parent metric boundary drift")
    if public_sensitive(report):
        raise ValueError("EXP-070 public privacy scan failed")
    create_json_once(public_root / "static.json", report)
    return report


def record_failure(config: dict[str, Any], error: BaseException) -> None:
    try:
        root = resolve_project(config["outputs"]["public_root"])
        target = root / "static.json"
        if os.path.lexists(target):
            return
        value = {
            "schema_version": "exp-070-no-result-preflight-failure-v1",
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
    parser = argparse.ArgumentParser(description="Run EXP-070 no-result preflight")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    try:
        result = run(args.config, config)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as error:
        record_failure(config, error)
        raise
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
