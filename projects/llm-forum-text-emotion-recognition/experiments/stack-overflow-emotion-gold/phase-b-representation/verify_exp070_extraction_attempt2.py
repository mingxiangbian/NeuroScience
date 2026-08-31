#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import types
from typing import Any


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
DEFAULT_CONFIG = MODULE_DIR / "configs" / "exp-070-verification-attempt-2.json"

EXPERIMENT_ID = "EXP-070"
RUN_ID = "exp-070-layerwise-probe-formal-extraction"
SOURCE_ATTEMPT_ID = "formal-attempt-1"
ATTEMPT_ID = "formal-extraction-verification-attempt-2"
SOURCE_PUBLIC_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
    "exp-070-layerwise-probes/formal-extraction-attempt-1"
)
SOURCE_PRIVATE_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/private/"
    "exp-070-layerwise-probes/formal-extraction-attempt-1"
)
RECOVERY_PUBLIC_ROOT = (
    "experiments/stack-overflow-emotion-gold/phase-b-representation/runs/"
    "exp-070-layerwise-probes/formal-extraction-verification-attempt-2"
)
FORBIDDEN_MODEL_MODULES = {"mlx", "mlx_lm", "torch", "transformers"}
EXPECTED_NONSELF_CONFIG_SHA256 = "c5b7aae2898d70018f2f6e2ae9a0065ffb483030d3f12a0b4e15f540132a297e"


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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
            raise ValueError("Symlink path rejected")
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


def require_record(record: dict[str, Any]) -> Path:
    if set(record) != {"path", "bytes", "mode", "sha256"}:
        raise ValueError("Artifact record schema drift")
    path = resolve_project(record["path"])
    if artifact(path) != record:
        raise ValueError(f"Artifact identity drift: {record['path']}")
    return path


def inventory(root: Path) -> set[str]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid evidence root")
    entries = list(root.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise PermissionError("Nested symlink rejected")
    return {path.relative_to(root).as_posix() for path in entries if path.is_file()}


def snapshot_digest(public_root: Path, private_root: Path) -> str:
    records: dict[str, dict[str, Any]] = {}
    for prefix, root in (("public", public_root), ("private", private_root)):
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Source snapshot root drift")
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            if path.is_symlink() or path.stat().st_nlink != 1:
                raise PermissionError("Source snapshot link drift")
            records[f"{prefix}/{path.relative_to(root).as_posix()}"] = {
                "bytes": path.stat().st_size,
                "mode": file_mode(path),
                "sha256": sha256(path),
            }
    return bytes_sha256(canonical_json_bytes(records))


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


def validate_config(config: dict[str, Any]) -> None:
    if set(config) != {
        "schema_version", "experiment_id", "run_id", "source_attempt_id", "attempt_id",
        "verification_attempt", "registered_at", "scope", "source_snapshot",
        "incident_evidence", "future_snapshot", "authorization", "numeric_contract",
        "outputs", "implementation", "claim_boundary",
    }:
        raise ValueError("EXP-070 recovery config schema drift")
    if (
        config.get("schema_version")
        != "exp-070-extraction-verification-attempt-2-config-v1"
        or config.get("experiment_id") != EXPERIMENT_ID
        or config.get("run_id") != RUN_ID
        or config.get("source_attempt_id") != SOURCE_ATTEMPT_ID
        or config.get("attempt_id") != ATTEMPT_ID
        or config.get("verification_attempt") != 2
    ):
        raise ValueError("EXP-070 recovery identity drift")
    if config.get("scope") != {
        "verification_only": True,
        "model_rerun": False,
        "worker_rerun": False,
        "assemble_rerun": False,
        "source_mutation": False,
        "probe_consumer": False,
        "exp071": False,
    }:
        raise ValueError("EXP-070 recovery scope drift")
    if config.get("authorization") != {
        "terminal_verification_authorized_when_snapshot_complete": True,
        "model_loading": False,
        "forward": False,
        "training": False,
        "worker_rerun": False,
        "assemble_rerun": False,
        "train_text": False,
        "train_labels": False,
        "heldout_gold": False,
        "validation": False,
        "test": False,
        "probe_fitting": False,
        "threshold_selection": False,
        "label_shuffle": False,
        "bootstrap": False,
        "performance_metrics": False,
        "exp071": False,
    }:
        raise PermissionError("EXP-070 recovery authorization drift")
    if config.get("numeric_contract") != {
        "rtol": 0.0,
        "atol": 1e-5,
        "runner_metric": "runner_mlx_head_vs_historical_logit_max_abs",
        "float32_diagnostic": (
            "independent_numpy_float32_saved_hf_head_vs_historical_logit_max_abs"
        ),
        "float64_gate": (
            "independent_numpy_float64_saved_hf_head_vs_historical_logit_max_abs"
        ),
        "float64_formula": "x64_at_w64_transpose_plus_b64_compare_directly_to_reference64",
        "float64_result_cast_back": False,
        "cross_worker_token_digest_required": True,
        "base_legacy_m2_digest_equality_required": False,
        "no_fallback_dtype_operator_or_tolerance": True,
    }:
        raise ValueError("EXP-070 recovery numeric contract drift")
    if config.get("future_snapshot") != {
        "source_public_root": SOURCE_PUBLIC_ROOT,
        "source_private_root": SOURCE_PRIVATE_ROOT,
        "required_public_inventory_before_verification": [
            "extraction.json", "run-claim.json",
        ],
        "required_workers": 16,
        "required_matrices": 16,
        "required_status": "CompletedAwaitingVerification",
        "claim_before_replay": True,
        "source_unchanged_after_replay": True,
    }:
        raise ValueError("EXP-070 recovery future-snapshot contract drift")
    if config.get("outputs") != {
        "recovery_public_root": RECOVERY_PUBLIC_ROOT,
        "allowlist": [
            "source-snapshot-claim.json", "verification.json", "extraction-complete.json",
        ],
    }:
        raise ValueError("EXP-070 recovery output contract drift")
    if set(config.get("source_snapshot", {})) != {
        "formal_config", "formal_protocol", "source_runner", "source_verifier", "source_tests",
    }:
        raise ValueError("EXP-070 recovery source-record inventory drift")
    incident = config.get("incident_evidence", {})
    if set(incident) != {
        "base_worker", "base_matrix", "fold0_worker", "fold0_matrix", "fold0_head",
        "fold0_heldout", "exp052_runner", "exp069_runner", "m2_metadata",
        "observed_before_freeze",
    }:
        raise ValueError("EXP-070 recovery incident inventory drift")
    if set(config.get("implementation", {})) != {"protocol", "verifier", "tests"}:
        raise ValueError("EXP-070 recovery implementation inventory drift")


def load_config(path: Path) -> dict[str, Any]:
    if path.resolve() != DEFAULT_CONFIG.resolve():
        raise PermissionError("EXP-070 recovery requires the frozen default config")
    config = strict_json(path)
    nonself = {key: value for key, value in config.items() if key != "implementation"}
    if bytes_sha256(canonical_json_bytes(nonself)) != EXPECTED_NONSELF_CONFIG_SHA256:
        raise ValueError("EXP-070 recovery non-self config drift")
    validate_config(config)
    return config


def require_config_records(config: dict[str, Any]) -> None:
    for record in config["source_snapshot"].values():
        require_record(record)
    for key, record in config["incident_evidence"].items():
        if key != "observed_before_freeze":
            require_record(record)
    for record in config["implementation"].values():
        require_record(record)


def validate_incident(config: dict[str, Any]) -> None:
    evidence = config["incident_evidence"]
    observed = evidence["observed_before_freeze"]
    expected_observed = {
        "token_digest_values_observed_different": True,
        "base_token_digest_scheme": "exp069_070_zero_based_ordinal",
        "legacy_m2_token_digest_scheme": "exp052_one_based_row_position",
        "fold0_runner_mlx_max_abs": 0.0,
        "fold0_pre_lora_max_abs": 0.0,
        "fold0_numpy_float32_max_abs": 1.049041748046875e-5,
        "fold0_numpy_float32_count_gt_atol": 1,
        "fold0_numpy_float64_max_abs": 2.086469194750862e-6,
        "float64_result_observed_before_rule_freeze": True,
        "remaining_workers_float64_unobserved_at_freeze": 14,
    }
    if observed != expected_observed:
        raise ValueError("EXP-070 recovery observed incident drift")
    base = strict_json(require_record(evidence["base_worker"]))
    fold0 = strict_json(require_record(evidence["fold0_worker"]))
    m2 = strict_json(require_record(evidence["m2_metadata"]))
    base_token_digest = base.get("token_id_stream_sha256")
    legacy_token_digest = m2.get("token_id_stream_sha256")
    if (
        base.get("status") != "Completed"
        or base.get("worker_id") != "base"
        or not isinstance(base_token_digest, str)
        or len(base_token_digest) != 64
        or any(character not in "0123456789abcdef" for character in base_token_digest)
        or not isinstance(legacy_token_digest, str)
        or len(legacy_token_digest) != 64
        or any(character not in "0123456789abcdef" for character in legacy_token_digest)
        or base_token_digest == legacy_token_digest
        or base.get("max_errors", {}).get("m2_hf") != 0.0
        or fold0.get("status") != "Completed"
        or fold0.get("worker_id") != "m3-s42-f0"
        or fold0.get("heldout_rows_checked") != 672
        or fold0.get("max_errors", {}).get("heldout_logit") != 0.0
        or max(float(value) for value in fold0.get("max_errors", {}).get("pre_lora", {}).values())
        != 0.0
        or fold0.get("source_before", {}).get("head") != evidence["fold0_head"]
        or fold0.get("source_before", {}).get("heldout") != evidence["fold0_heldout"]
        or fold0.get("source_before") != fold0.get("source_after")
    ):
        raise ValueError("EXP-070 recovery incident artifact drift")
    access = fold0.get("access", {})
    if (
        access.get("train_label_values_used") is not False
        or access.get("heldout_gold_read") is not False
        or access.get("validation_accessed") is not False
        or access.get("test_accessed") is not False
        or access.get("probe_fitted") is not False
        or access.get("performance_metrics_computed") is not False
    ):
        raise PermissionError("EXP-070 recovery incident access drift")
    exp052_source = require_record(evidence["exp052_runner"]).read_text(encoding="utf-8")
    exp069_source = require_record(evidence["exp069_runner"]).read_text(encoding="utf-8")
    if (
        'token_digest.update((index + 1).to_bytes(8, "little", signed=False))'
        not in exp052_source
        or 'digest.update(int(ordinal).to_bytes(8, "little", signed=False))'
        not in exp069_source
    ):
        raise ValueError("EXP-070 recovery token-scheme evidence drift")


def validate_source_ready(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source_config_path = require_record(config["source_snapshot"]["formal_config"])
    source_config = strict_json(source_config_path)
    if source_config.get("implementation") != {
        "runner": config["source_snapshot"]["source_runner"],
        "verifier": config["source_snapshot"]["source_verifier"],
        "tests": config["source_snapshot"]["source_tests"],
    } or source_config.get("formal_protocol") != config["source_snapshot"]["formal_protocol"]:
        raise ValueError("EXP-070 recovery formal-source binding drift")
    public = resolve_project(config["future_snapshot"]["source_public_root"])
    private = resolve_project(config["future_snapshot"]["source_private_root"])
    if file_mode(public) != "0755" or file_mode(private) != "0700":
        raise PermissionError("EXP-070 recovery source-root mode drift")
    expected_public = set(config["future_snapshot"]["required_public_inventory_before_verification"])
    if inventory(public) != expected_public:
        raise ValueError("EXP-070 recovery source is not preverification terminal")
    run = strict_json(public / "extraction.json")
    claim = strict_json(public / "run-claim.json")
    if (
        run.get("status") != config["future_snapshot"]["required_status"]
        or run.get("counts") != {"rows": 3360, "workers": 16, "matrices": 16}
        or run.get("formal_probe_executed") is not False
        or run.get("performance_metrics_computed") is not False
        or run.get("validation_accessed") is not False
        or run.get("test_accessed") is not False
        or claim.get("formal_probe_authorized") is not False
        or claim.get("performance_metrics_authorized") is not False
        or claim.get("validation_access") is not False
        or claim.get("test_access") is not False
    ):
        raise ValueError("EXP-070 recovery source terminal state drift")
    manifest_record = run.get("extraction_manifest")
    if set(manifest_record or {}) != {"logical_name", "bytes", "mode", "sha256"}:
        raise ValueError("EXP-070 recovery source manifest record drift")
    manifest_path = private / manifest_record["logical_name"]
    if artifact(manifest_path, logical_name=manifest_record["logical_name"]) != manifest_record:
        raise ValueError("EXP-070 recovery source manifest identity drift")
    manifest = strict_json(manifest_path)
    if (
        manifest.get("status") != "Completed"
        or len(manifest.get("workers", [])) != 16
        or manifest.get("raw_representation_bytes") != 2_890_137_600
    ):
        raise ValueError("EXP-070 recovery source manifest terminal drift")
    return source_config, run, manifest


def transform_source_verifier(path: Path) -> tuple[Any, str]:
    source = path.read_text(encoding="utf-8")
    replacements = (
        (
            '    if base_worker["token_id_stream_sha256"] != original["m2_cache"]["token_id_stream_sha256"]:\n'
            '        raise ValueError("EXP-070 base token-stream digest drift")',
            '    legacy_m2_token_digest = original["m2_cache"]["token_id_stream_sha256"]\n'
            '    base_token_digest = base_worker["token_id_stream_sha256"]\n'
            '    if any(\n'
            '        not isinstance(value, str)\n'
            '        or len(value) != 64\n'
            '        or any(character not in "0123456789abcdef" for character in value)\n'
            '        for value in (legacy_m2_token_digest, base_token_digest)\n'
            '    ):\n'
            '        raise ValueError("EXP-070 token-stream digest schema drift")',
        ),
        (
            '    hidden = np.asarray(matrix[row_indices, hf_index, :], dtype=np.float32)\n'
            '    recomputed = (hidden @ head["weight"].T + head["bias"]).astype(np.float32)\n'
            '    return max_abs(recomputed, reference_logits[reference_order])',
            '    hidden = np.asarray(matrix[row_indices, hf_index, :], dtype=np.float32)\n'
            '    reference = np.asarray(reference_logits[reference_order], dtype=np.float32)\n'
            '    recomputed_float32 = (\n'
            '        hidden @ head["weight"].T + head["bias"]\n'
            '    ).astype(np.float32)\n'
            '    recomputed_float64 = (\n'
            '        hidden.astype(np.float64)\n'
            '        @ head["weight"].astype(np.float64).T\n'
            '        + head["bias"].astype(np.float64)\n'
            '    )\n'
            '    INDEPENDENT_AFFINE_DIAGNOSTICS.append(\n'
            '        {\n'
            '            "worker_id": spec["worker_id"],\n'
            '            "runner_mlx_max_abs": float(worker["max_errors"]["heldout_logit"]),\n'
            '            "numpy_float32_max_abs": max_abs(recomputed_float32, reference),\n'
            '            "numpy_float64_max_abs": max_abs(\n'
            '                recomputed_float64, reference.astype(np.float64)\n'
            '            ),\n'
            '        }\n'
            '    )\n'
            '    return max_abs(recomputed_float64, reference.astype(np.float64))',
        ),
    )
    for old, new in replacements:
        if source.count(old) != 1:
            raise ValueError("EXP-070 recovery source-transform anchor drift")
        source = source.replace(old, new)
    transformed_sha256 = bytes_sha256(source.encode("utf-8"))
    module = types.ModuleType("exp070_extraction_verification_attempt2_transformed")
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec"), module.__dict__)
    module.INDEPENDENT_AFFINE_DIAGNOSTICS = []
    return module, transformed_sha256


def run_transformed_replay(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], str]:
    source_path = require_record(config["source_snapshot"]["source_verifier"])
    source_config_path = require_record(config["source_snapshot"]["formal_config"])
    verifier, transformed_sha256 = transform_source_verifier(source_path)
    source_config = verifier.load_config(source_config_path)
    source_public = resolve_project(config["future_snapshot"]["source_public_root"])
    captured: dict[str, Any] = {}

    original_inventory = verifier.inventory

    def compatible_inventory(root: Path) -> set[str]:
        observed = original_inventory(root)
        if root.resolve() == source_public.resolve():
            return observed | set(captured)
        return observed

    verifier.inventory = compatible_inventory

    def capture_output(path: Path, value: Any) -> None:
        if path.parent.resolve() != source_public.resolve() or path.name not in {
            "extraction-verification.json", "extraction-complete.json",
        }:
            raise PermissionError("EXP-070 recovery transformed verifier attempted an unexpected write")
        if path.name in captured:
            raise FileExistsError(path.name)
        captured[path.name] = value

    verifier.create_json_once = capture_output
    original_artifact = verifier.artifact

    def captured_artifact(path: Path, *, logical_name: str | None = None) -> dict[str, Any]:
        if path.parent.resolve() == source_public.resolve() and path.name in captured:
            payload = verifier.canonical_json_bytes(captured[path.name])
            result: dict[str, Any] = {
                "bytes": len(payload),
                "mode": "0644",
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            if logical_name is None:
                result["path"] = path.relative_to(PROJECT_ROOT).as_posix()
            else:
                result["logical_name"] = logical_name
            return result
        return original_artifact(path, logical_name=logical_name)

    verifier.artifact = captured_artifact
    original_file_mode = verifier.file_mode

    def compatible_file_mode(path: Path) -> str:
        if path.parent.resolve() == source_public.resolve() and path.name in captured:
            return "0644"
        return original_file_mode(path)

    verifier.file_mode = compatible_file_mode
    replay = verifier.verify(source_config_path, source_config)
    if set(captured) != {"extraction-verification.json", "extraction-complete.json"}:
        raise ValueError("EXP-070 recovery transformed output-capture drift")
    diagnostics = list(verifier.INDEPENDENT_AFFINE_DIAGNOSTICS)
    return replay, captured, diagnostics, transformed_sha256


def completion_value(
    config_path: Path,
    config: dict[str, Any],
    claim_path: Path,
    verification_path: Path,
) -> dict[str, Any]:
    source_public = resolve_project(config["future_snapshot"]["source_public_root"])
    source_private = resolve_project(config["future_snapshot"]["source_private_root"])
    return {
        "schema_version": "exp-070-extraction-complete-v2",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "source_attempt_id": SOURCE_ATTEMPT_ID,
        "attempt_id": ATTEMPT_ID,
        "verification_attempt": 2,
        "status": "Complete",
        "completed_via": ATTEMPT_ID,
        "formal_extraction_complete": True,
        "probe_fitting_authorized": False,
        "performance_metrics_computed": False,
        "exp070_complete": False,
        "exp071_authorized": False,
        "model_rerun": False,
        "worker_rerun": False,
        "assemble_rerun": False,
        "source_mutated": False,
        "source_original_verifier_unexecuted": True,
        "source_run": artifact(source_public / "extraction.json"),
        "source_extraction_manifest": artifact(
            source_private / "extraction-manifest.json",
            logical_name="extraction-manifest.json",
        ),
        "source_snapshot_claim": artifact(claim_path),
        "recovery_config": artifact(config_path),
        "recovery_verification": artifact(verification_path),
        "claim_boundary": config["claim_boundary"],
        "next_gate": "A separate immutable EXP-070 probe consumer remains required and unexecuted",
    }


def require_transformed_completion(captured: dict[str, Any]) -> None:
    source_completion = captured.get("extraction-complete.json", {})
    if (
        source_completion.get("formal_extraction_complete") is not True
        or source_completion.get("probe_fitting_authorized") is not False
        or source_completion.get("performance_metrics_computed") is not False
        or source_completion.get("exp070_complete") is not False
        or source_completion.get("exp071_authorized") is not False
    ):
        raise ValueError("EXP-070 recovery transformed completion drift")


def build_recovery_verification(
    config_path: Path,
    config: dict[str, Any],
    claim_path: Path,
    snapshot_sha256: str,
    source_run: dict[str, Any],
    replay: dict[str, Any],
    diagnostics: list[dict[str, Any]],
    transformed_sha256: str,
) -> dict[str, Any]:
    source_public = resolve_project(config["future_snapshot"]["source_public_root"])
    source_private = resolve_project(config["future_snapshot"]["source_private_root"])
    if (
        replay.get("status") != "Passed"
        or replay.get("counts") != {"rows": 3360, "workers": 16, "matrices": 16}
        or "cross_worker_token_digest" not in replay.get("checks", [])
        or len(diagnostics) != 15
        or len({item.get("worker_id") for item in diagnostics}) != 15
    ):
        raise ValueError("EXP-070 recovery transformed replay state drift")
    expected_diagnostic_keys = {
        "worker_id", "runner_mlx_max_abs", "numpy_float32_max_abs", "numpy_float64_max_abs",
    }
    if any(set(item) != expected_diagnostic_keys for item in diagnostics):
        raise ValueError("EXP-070 recovery affine diagnostic schema drift")
    float32_values = [float(item["numpy_float32_max_abs"]) for item in diagnostics]
    float64_values = [float(item["numpy_float64_max_abs"]) for item in diagnostics]
    runner_mlx_values = [float(item["runner_mlx_max_abs"]) for item in diagnostics]
    if any(
        not (value >= 0.0 and value < float("inf"))
        for value in [*float32_values, *float64_values, *runner_mlx_values]
    ):
        raise ValueError("EXP-070 recovery affine diagnostic value drift")
    float32_max = max(float32_values, default=0.0)
    float64_max = max(float64_values, default=0.0)
    runner_mlx_max = max(runner_mlx_values, default=0.0)
    atol = float(config["numeric_contract"]["atol"])
    if (
        any(value > atol for value in float64_values)
        or any(value > atol for value in runner_mlx_values)
        or abs(float64_max - float(replay["max_errors"]["heldout_head_logit"])) > 1e-12
        or abs(runner_mlx_max - float(source_run["max_errors"]["heldout_logit"])) > 1e-12
    ):
        raise ValueError("EXP-070 recovery heldout affine parity gate failed")
    observed = config["incident_evidence"]["observed_before_freeze"]
    if (
        abs(float32_values[0] - float(observed["fold0_numpy_float32_max_abs"])) > 1e-12
        or abs(float64_values[0] - float(observed["fold0_numpy_float64_max_abs"])) > 1e-12
        or abs(runner_mlx_values[0] - float(observed["fold0_runner_mlx_max_abs"])) > 1e-12
        or diagnostics[0].get("worker_id") != "m3-s42-f0"
    ):
        raise ValueError("EXP-070 recovery fold-0 diagnostic replay drift")
    checks = list(replay["checks"]) + [
        "legacy_and_current_token_digest_scheme_separation",
        "float32_affine_diagnostic_preserved",
        "float64_affine_canonical_gate",
        "runner_mlx_parity_separate",
        "fold0_pre_freeze_observation_disclosed",
        "immutable_source_snapshot_claim",
    ]
    access = dict(replay["access"])
    if (
        access.get("train_label_values_read_by_verifier") is not False
        or access.get("heldout_gold_read") is not False
        or access.get("validation_accessed") is not False
        or access.get("test_accessed") is not False
        or access.get("probe_fitted") is not False
        or access.get("performance_metrics_computed") is not False
    ):
        raise PermissionError("EXP-070 recovery transformed access drift")
    return {
        "schema_version": "exp-070-extraction-verification-attempt-2-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "source_attempt_id": SOURCE_ATTEMPT_ID,
        "attempt_id": ATTEMPT_ID,
        "verification_attempt": 2,
        "stage": "formal-extraction",
        "status": "Passed",
        "passed_count": len(checks),
        "failed_count": 0,
        "checks": checks,
        "counts": replay["counts"],
        "max_errors": {
            "runner_mlx_head_vs_historical_logit_max_abs": runner_mlx_max,
            "independent_numpy_float32_saved_hf_head_vs_historical_logit_max_abs": float32_max,
            "independent_numpy_float64_saved_hf_head_vs_historical_logit_max_abs": float64_max,
            "m2_hf": float(replay["max_errors"]["m2_hf"]),
            "persisted_pre_lora": float(replay["max_errors"]["persisted_pre_lora"]),
            "recorded_transient_pre_lora": float(
                replay["max_errors"]["recorded_transient_pre_lora"]
            ),
        },
        "worker_parity_diagnostics": diagnostics,
        "token_digests": {
            "base_scheme": "exp069_070_zero_based_ordinal",
            "legacy_m2_scheme": "exp052_one_based_row_position",
            "values_equal": False,
            "cross_worker_current_scheme_passed": True,
            "cross_scheme_equality_required": False,
        },
        "numeric_contract": config["numeric_contract"],
        "source_snapshot_claim": artifact(claim_path),
        "source_snapshot_sha256": snapshot_sha256,
        "source_snapshot_unchanged": True,
        "source_run": artifact(source_public / "extraction.json"),
        "source_extraction_manifest": artifact(
            source_private / "extraction-manifest.json",
            logical_name="extraction-manifest.json",
        ),
        "original_source_verifier": config["source_snapshot"]["source_verifier"],
        "transformed_source_sha256": transformed_sha256,
        "config": artifact(config_path),
        "runner_imported": False,
        "model_libraries_imported": False,
        "model_rerun": False,
        "worker_rerun": False,
        "assemble_rerun": False,
        "source_mutated": False,
        "fold0_float64_result_observed_before_rule_freeze": True,
        "remaining_workers_float64_unobserved_at_freeze": 14,
        "access": access,
        "claim_boundary": config["claim_boundary"],
    }


def require_exact_passed_verification(path: Path, expected: dict[str, Any]) -> None:
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_nlink != 1
        or file_mode(path) != "0644"
        or strict_json(path) != expected
        or path.read_bytes() != canonical_json_bytes(expected)
    ):
        raise ValueError("EXP-070 recovery existing Passed verification drift")


def resume_passed_verification_completion(
    config_path: Path,
    config: dict[str, Any],
    recovery: Path,
) -> dict[str, Any]:
    observed = inventory(recovery)
    claim_path = recovery / "source-snapshot-claim.json"
    verification_path = recovery / "verification.json"
    completion_path = recovery / "extraction-complete.json"
    if observed not in (
        {"source-snapshot-claim.json", "verification.json"},
        set(config["outputs"]["allowlist"]),
    ):
        raise FileExistsError("EXP-070 recovery root is not a resumable Passed prefix")
    claim = strict_json(claim_path)
    source_public = resolve_project(config["future_snapshot"]["source_public_root"])
    source_private = resolve_project(config["future_snapshot"]["source_private_root"])
    snapshot_before = snapshot_digest(source_public, source_private)
    if (
        claim.get("status") != "Claimed"
        or claim.get("config") != artifact(config_path)
        or claim.get("source_snapshot_sha256") != snapshot_before
    ):
        raise ValueError("EXP-070 recovery snapshot-claim binding drift")
    imported_before = {name.split(".")[0] for name in sys.modules}
    if imported_before & FORBIDDEN_MODEL_MODULES:
        raise RuntimeError("EXP-070 recovery resume process already imported a model library")
    replay, captured, diagnostics, transformed_sha256 = run_transformed_replay(config)
    imported_after = {name.split(".")[0] for name in sys.modules}
    if imported_after & FORBIDDEN_MODEL_MODULES:
        raise RuntimeError("EXP-070 recovery resume imported a forbidden model library")
    snapshot_after = snapshot_digest(source_public, source_private)
    if snapshot_after != snapshot_before:
        raise ValueError("EXP-070 recovery source snapshot changed during resumed replay")
    require_transformed_completion(captured)
    source_run = strict_json(source_public / "extraction.json")
    expected_verification = build_recovery_verification(
        config_path,
        config,
        claim_path,
        snapshot_before,
        source_run,
        replay,
        diagnostics,
        transformed_sha256,
    )
    require_exact_passed_verification(verification_path, expected_verification)
    expected_completion = completion_value(
        config_path, config, claim_path, verification_path
    )
    if completion_path.exists():
        if strict_json(completion_path) != expected_completion or file_mode(completion_path) != "0644":
            raise ValueError("EXP-070 recovery existing completion drift")
    else:
        create_json_once(completion_path, expected_completion)
    if inventory(recovery) != set(config["outputs"]["allowlist"]):
        raise ValueError("EXP-070 recovery resumed terminal inventory drift")
    return expected_verification


def verify(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    require_config_records(config)
    validate_incident(config)
    _, source_run, source_manifest = validate_source_ready(config)
    source_public = resolve_project(config["future_snapshot"]["source_public_root"])
    source_private = resolve_project(config["future_snapshot"]["source_private_root"])
    recovery = resolve_project(config["outputs"]["recovery_public_root"], must_exist=False)
    if os.path.lexists(recovery):
        return resume_passed_verification_completion(config_path, config, recovery)
    snapshot_before = snapshot_digest(source_public, source_private)
    recovery.mkdir(parents=True, mode=0o755)
    os.chmod(recovery, 0o755)
    claim = {
        "schema_version": "exp-070-extraction-recovery-snapshot-claim-v1",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "source_attempt_id": SOURCE_ATTEMPT_ID,
        "attempt_id": ATTEMPT_ID,
        "status": "Claimed",
        "config": artifact(config_path),
        "source_run": artifact(source_public / "extraction.json"),
        "source_extraction_manifest": artifact(
            source_private / "extraction-manifest.json",
            logical_name="extraction-manifest.json",
        ),
        "source_snapshot_sha256": snapshot_before,
        "counts": {"workers": 16, "matrices": 16, "rows": 3360},
        "fold0_float64_result_observed_before_rule_freeze": True,
        "remaining_workers_float64_unobserved_at_freeze": 14,
        "source_verifier_unexecuted": True,
        "claim_boundary": config["claim_boundary"],
    }
    claim_path = recovery / "source-snapshot-claim.json"
    create_json_once(claim_path, claim)
    imported_before = {name.split(".")[0] for name in sys.modules}
    if imported_before & FORBIDDEN_MODEL_MODULES:
        raise RuntimeError("EXP-070 recovery process already imported a model library")
    replay, captured, diagnostics, transformed_sha256 = run_transformed_replay(config)
    imported_after = {name.split(".")[0] for name in sys.modules}
    if imported_after & FORBIDDEN_MODEL_MODULES:
        raise RuntimeError("EXP-070 recovery imported a forbidden model library")
    snapshot_after = snapshot_digest(source_public, source_private)
    if snapshot_after != snapshot_before:
        raise ValueError("EXP-070 recovery source snapshot changed during replay")
    require_transformed_completion(captured)
    verification = build_recovery_verification(
        config_path,
        config,
        claim_path,
        snapshot_before,
        source_run,
        replay,
        diagnostics,
        transformed_sha256,
    )
    verification_path = recovery / "verification.json"
    create_json_once(verification_path, verification)
    completion = completion_value(config_path, config, claim_path, verification_path)
    create_json_once(recovery / "extraction-complete.json", completion)
    if inventory(recovery) != set(config["outputs"]["allowlist"]):
        raise ValueError("EXP-070 recovery terminal output inventory drift")
    return verification


def record_failure(config: dict[str, Any], error: BaseException) -> None:
    try:
        recovery = resolve_project(config["outputs"]["recovery_public_root"], must_exist=False)
        claim = recovery / "source-snapshot-claim.json"
        if not claim.is_file() or (recovery / "verification.json").exists():
            return
        value = {
            "schema_version": "exp-070-extraction-verification-attempt-2-failure-v1",
            "experiment_id": EXPERIMENT_ID,
            "run_id": RUN_ID,
            "source_attempt_id": SOURCE_ATTEMPT_ID,
            "attempt_id": ATTEMPT_ID,
            "verification_attempt": 2,
            "stage": "formal-extraction",
            "status": "Failed",
            "error_type": type(error).__name__,
            "formal_extraction_complete": False,
            "probe_fitting_authorized": False,
            "performance_metrics_computed": False,
            "exp070_complete": False,
            "exp071_authorized": False,
            "source_snapshot_claim": artifact(claim),
            "claim_boundary": config.get("claim_boundary"),
        }
        create_json_once(recovery / "verification.json", value)
    except Exception:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
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
