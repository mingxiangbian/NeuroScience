#!/usr/bin/env python3
"""Run SQMA-003 attempt 2 with the shakedown-only format revision.

This wrapper reuses the frozen attempt-1 runner and changes only its prompt
bundle and OUTPUT_CONTRACTS.  An attempt-2 config must bind the new bundle and
use new public/private output namespaces.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any


sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ATTEMPT1_RUNNER = PROJECT_ROOT / "scripts" / "run_sqma003_agent_preflight.py"
PROMPT_V2 = PROJECT_ROOT / "prompts" / "agent-bundle-v2-classifier-free.json"
PROMPT_V2_RELATIVE = PROMPT_V2.relative_to(REPO_ROOT).as_posix()
ROLE_ORDER = ("evidence_appraisal", "pragmatics_critic", "judge", "single_agent")


class Attempt2Error(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Attempt2Error(message)


def regular_non_symlink(path: Path, label: str) -> None:
    require(os.path.lexists(path), f"missing {label}")
    observed = os.lstat(path)
    require(
        stat.S_ISREG(observed.st_mode) and not stat.S_ISLNK(observed.st_mode),
        f"invalid {label}",
    )


def read_json(path: Path, label: str) -> dict[str, Any]:
    regular_non_symlink(path, label)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Attempt2Error(f"invalid {label}") from exc
    require(isinstance(value, dict), f"{label} root must be an object")
    return value


def build_output_contracts(bundle: dict[str, Any]) -> dict[str, str]:
    examples = bundle.get("concrete_output_examples")
    require(isinstance(examples, dict) and set(examples) == set(ROLE_ORDER), "example inventory drift")
    encoded = {
        role: json.dumps(examples[role], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for role in ROLE_ORDER
    }
    require(all("|" not in value for value in encoded.values()), "example contains a pipe placeholder")
    evidence = examples["evidence_appraisal"].get("evidence_spans")
    single_evidence = examples["single_agent"].get("evidence_appraisal", {}).get("evidence_spans")
    require(
        isinstance(evidence, list)
        and isinstance(single_evidence, list)
        and all(isinstance(item, str) for item in evidence + single_evidence),
        "evidence_spans example must contain strings only",
    )
    refs = examples["judge"].get("evidence_refs")
    single_refs = examples["single_agent"].get("decision", {}).get("evidence_refs")
    require(
        isinstance(refs, list)
        and isinstance(single_refs, list)
        and all(type(item) is int for item in refs + single_refs),
        "evidence_refs example must contain integers only",
    )
    common = (
        "Use the example only for JSON shape and value types; its empty labels are not a default "
        "answer. Replace all semantic values using the current input. Do not copy vertical-bar "
        "alternatives. evidence_spans contains strings only. Every non-empty evidence_refs array "
        "contains zero-based JSON integers only. "
    )
    contracts = {
        role: (
            common
            + "Return exactly one JSON object with the same keys and JSON value types. "
            + "Concrete valid JSON example: "
            + encoded[role]
        )
        for role in ROLE_ORDER
    }
    for role in ("evidence_appraisal", "pragmatics_critic", "judge"):
        contracts[role] += (
            " When this contract is appended under Single Agent nested contracts, it is a field "
            "reference only; do not output it as a separate second JSON object."
        )
    return contracts


def load_attempt1_runner() -> Any:
    regular_non_symlink(ATTEMPT1_RUNNER, "attempt-1 runner")
    module_name = "sqma003_attempt1_runner_wrapped_by_attempt2"
    spec = importlib.util.spec_from_file_location(module_name, ATTEMPT1_RUNNER)
    require(spec is not None and spec.loader is not None, "attempt-1 runner import unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    require(Path(module.__file__).resolve() == ATTEMPT1_RUNNER.resolve(), "attempt-1 runner path drift")
    return module


def validate_attempt2_config(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    supplied = path.expanduser().resolve()
    require(REPO_ROOT.resolve() in supplied.parents, "attempt-2 config escapes repository")
    config = read_json(supplied, "attempt-2 config")
    require(config.get("experiment_id") == "SQMA-003", "experiment identity drift")
    implementation = config.get("implementation")
    require(isinstance(implementation, dict), "implementation contract missing")
    prompt_record = implementation.get("prompt_bundle")
    require(isinstance(prompt_record, dict), "prompt bundle record missing")
    require(prompt_record.get("path") == PROMPT_V2_RELATIVE, "attempt-2 must bind prompt bundle v2")
    regular_non_symlink(PROMPT_V2, "prompt bundle v2")
    require(prompt_record.get("bytes") == PROMPT_V2.stat().st_size, "prompt bundle byte drift")
    require(prompt_record.get("sha256") == __import__("hashlib").sha256(PROMPT_V2.read_bytes()).hexdigest(), "prompt bundle hash drift")
    outputs = config.get("outputs")
    require(isinstance(outputs, dict), "output contract missing")
    for key in ("public_attempt_dir", "private_attempt_dir"):
        value = outputs.get(key)
        require(isinstance(value, str) and "attempt-2" in value, f"{key} is not append-only attempt 2")
        require("attempt-1" not in value, f"{key} reuses attempt 1")
    bundle = read_json(PROMPT_V2, "prompt bundle v2")
    revision = bundle.get("revision_policy", {})
    require(
        revision.get("locked_records_decoded_by_diagnostic_process") is True
        and revision.get("locked_content_exposed_to_revision_author") is False
        and revision.get("locked_outputs_used_for_revision") is False
        and revision.get("semantic_or_label_rules_changed") is False,
        "format-only revision boundary drift",
    )
    return config, bundle


def run(config_path: str) -> dict[str, Any]:
    supplied = Path(config_path).expanduser().resolve()
    _, bundle = validate_attempt2_config(supplied)
    attempt1 = load_attempt1_runner()
    attempt1.CONFIG_PATH = supplied
    attempt1.OUTPUT_CONTRACTS = build_output_contracts(bundle)
    result = attempt1.run(str(supplied))
    require(isinstance(result, dict), "attempt-1 runner returned an invalid result")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    arguments = parser.parse_args()
    result = run(arguments.config)
    print(
        json.dumps(
            {
                "experiment_id": result.get("experiment_id"),
                "status": result.get("status"),
                "gate_passed": result.get("gate_passed"),
                "next_gate": result.get("next_gate"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, TypeError, ValueError, OSError, ImportError, Attempt2Error) as exc:
        print(f"SQMA-003 attempt-2 Failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
