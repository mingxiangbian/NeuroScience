#!/usr/bin/env python3
"""One-shot EXP-074 synthesis of verified public aggregates only."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import re
import resource
import stat
import subprocess
import sys
import tempfile
import time

MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[2]
BASE = "experiments/stack-overflow-emotion-gold/phase-b-representation/"
PROTOCOL_PATH = "experiments/stack-overflow-emotion-gold/protocols/exp-074-phase-b-synthesis.md"
IMPLEMENTATION_PATHS = {"runner": BASE + "run_exp074_synthesis.py", "verifier": BASE + "verify_exp074_synthesis.py", "tests": BASE + "tests/test_exp074_synthesis.py"}
OUTPUTS = {"public_root": BASE + "runs/exp-074-phase-b-synthesis/attempt-1"}
RESOURCES = {"max_wall_seconds": 3600, "max_peak_rss_bytes": 1073741824, "max_output_bytes": 33554432}
SOURCE_NAMES = ("probe", "probe_verification", "probe_completion", "geometry_run", "geometry_verification", "ablation_score", "ablation_verification")
POINTS = ("H-1", "H7", "H15", "H19", "H20", "H27", "H31", "H35", "HF")
GEOMETRY_ORDER = [f"s42:{p}" for p in POINTS] + [f"s{s}:{p}" for s in (43, 44) for p in ("H19", "H27", "HF")]
ABLATION_ORDER = [f"s{s}:A{a}" for s in (42, 43, 44) for a in range(6 if s == 42 else 4)]
REPRESENTATION_STATES = {2: "Representation effect replicated", 1: "Representation effect seed-sensitive", 0: "No replicated representation effect"}
ACCESS = {"verified_public_aggregates_read": True, "private_files_read": False, "array_values_read": False, "labels_read": False, "text_read": False, "model_loaded": False, "forward_executed": False, "validation_accessed": False, "test_accessed": False, "source_mutated": False}
HISTORY = {"exp071": "Failed", "exp071_incident002": "Complete", "exp075_post_diagnostic": True, "exp073": "Not executed (optional)", "context_c2": "Paused", "phase_b_minimum_complete": False}
CLAIM = "Same-train outer-heldout cross-training-seed representation replication and inference-time functional dependency are separate findings. Geometry preserves undefined CKA without imputation. No causal emotion mechanism, independent-data generalization, deployment efficiency, or original EXP-071 success is claimed."


def _helpers():
    path = MODULE_DIR / "verify_exp071_drift.py"
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != 121050 or stat.S_IMODE(info.st_mode) != 0o644 or hashlib.sha256(path.read_bytes()).hexdigest() != "0a6e0e03a2f14212bc2bf0d3a1ecc3d9cf4eec1ee8a3a9f7b44cd3ca83a0bbd2":
        raise ValueError("Pinned IO helper drift")
    spec = importlib.util.spec_from_file_location("exp074_io", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SAFE = _helpers()
canonical_json_bytes, artifact = SAFE.canonical_json_bytes, SAFE.artifact


def digest(value):
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Missing or nonfinite aggregate")
    return float(value)


def representation_state(results):
    if results.get("negative_control_failure") is not False:
        raise ValueError("Negative control does not permit state assignment")
    votes = {}
    for seed in (43, 44):
        points = {}
        for point in ("H27", "HF"):
            contrast = results["main_contrasts"][f"m3-s{seed}:{point}"]
            delta = finite(contrast["delta"]["five_label_macro_ap"])
            interval = contrast["bootstrap_delta_intervals"]["five_label_macro_ap"]
            if not isinstance(interval, list) or len(interval) != 2 or finite(interval[0]) > finite(interval[1]):
                raise ValueError("Invalid bootstrap interval")
            points[point] = {"delta": delta, "interval": interval, "passed": delta > 0 and interval[0] > 0}
        votes[str(seed)] = {"passed": all(item["passed"] for item in points.values()), "points": points}
    count = sum(vote["passed"] for vote in votes.values())
    label = REPRESENTATION_STATES[count]
    if results.get("seed_votes") != votes or type(results.get("representation_state")) is not int or results["representation_state"] != count or results.get("representation_state_label") != label:
        raise ValueError("Original representation state inconsistent with registered vote")
    return {"state": label, "passed_seeds": count, "seed_votes": votes, "negative_control_failure": False}


def functional_state(results):
    if results.get("condition_order") != ABLATION_ORDER or set(results.get("conditions", {})) != set(ABLATION_ORDER):
        raise ValueError("Ablation condition inventory drift")
    details = {}
    for seed in (43, 44):
        full = finite(results["conditions"][f"s{seed}:A0"]["metrics"]["five_label_macro_f1"])
        deltas = {}
        for condition in ("A2", "A3"):
            item = results["conditions"][f"s{seed}:{condition}"]
            metric = finite(item["metrics"]["five_label_macro_f1"])
            delta = finite(item["delta_from_full"]["five_label_macro_f1"])
            if not 0 <= metric <= 1 or not 0 <= full <= 1 or not math.isclose(metric - full, delta, rel_tol=0, abs_tol=1e-12):
                raise ValueError("Ablation delta and metric inconsistent")
            deltas[condition] = delta
        details[str(seed)] = {"attention_off_drop": -deltas["A2"], "mlp_off_drop": -deltas["A3"], "D": -deltas["A2"] + deltas["A3"]}
    values = [details[str(seed)]["D"] for seed in (43, 44)]
    state = "Stable Attention-dominant dependency" if all(value >= 0.01 for value in values) else "Stable MLP-dominant dependency" if all(value <= -0.01 for value in values) else "Both contribute / no stable dominance"
    return {"state": state, "metric": "five_label_macro_f1", "definition": "drop(A2)-drop(A3)=-delta(A2)+delta(A3)", "threshold": 0.01, "seeds": details}


def validate_geometry(results):
    if results.get("condition_order") != GEOMETRY_ORDER or set(results.get("conditions", {})) != set(GEOMETRY_ORDER):
        raise ValueError("Geometry condition inventory drift")
    any_missing = False
    for condition in GEOMETRY_ORDER:
        cka = results["conditions"][condition]["linear_cka"]
        values, reasons = cka["per_fold"], cka["reason_by_fold"]
        if len(values) != 5 or len(reasons) != 5 or any((value is None) != (reason == "zero_centered_variance") or (value is not None and (reason is not None or not 0 <= finite(value) <= 1)) for value, reason in zip(values, reasons)):
            raise ValueError("Geometry nullable domain drift")
        n_defined = sum(value is not None for value in values)
        if cka["n_defined"] != n_defined or (n_defined != 5 and (cka["mean"] is not None or cka["sample_sd"] is not None or cka["reason"] != "undefined_fold_cka")):
            raise ValueError("Geometry missing-fold propagation drift")
        if n_defined == 5 and (not 0 <= finite(cka["mean"]) <= 1 or finite(cka["sample_sd"]) < 0 or cka["reason"] is not None):
            raise ValueError("Geometry defined aggregation drift")
        any_missing = any_missing or (condition.startswith("s42:") and cka["mean"] is None)
    correlation = results["seed42_spearman"]
    if correlation["point_order"] != list(POINTS) or correlation["n"] != 9 or (any_missing and (correlation["rho"] is not None or correlation["reason"] != "undefined_cka_input")):
        raise ValueError("Fixed-nine missingness propagation drift")


def make_summary(inputs, source):
    probe, geometry, ablation = inputs["probe"]["results"], inputs["geometry_run"]["results"], inputs["ablation_score"]["results"]
    representation, functional = representation_state(probe), functional_state(ablation)
    validate_geometry(geometry)
    return {"schema_version": "exp-074-summary-v1", "experiment_id": "EXP-074", "sources": source,
            "representation_effect": representation, "functional_dependency": functional,
            "probe": {"main_metrics": probe["main_metrics"], "main_contrasts": probe["main_contrasts"]},
            "geometry": geometry, "ablation": ablation, "history_and_scope": HISTORY, "claim_boundary": CLAIM}


def validate_config(config):
    if set(config) != {"experiment_id", "protocol", "implementation", "source", "outputs", "resources"} or config["experiment_id"] != "EXP-074" or config["outputs"] != OUTPUTS or config["resources"] != RESOURCES:
        raise ValueError("Frozen synthesis config drift")
    if set(config["implementation"]) != set(IMPLEMENTATION_PATHS) or set(config["source"]) != set(SOURCE_NAMES):
        raise ValueError("Config record inventory drift")
    for name, record in {"protocol": config["protocol"], **config["implementation"], **config["source"]}.items():
        if set(record) != {"path", "bytes", "mode", "sha256"} or type(record["bytes"]) is not int or not 0 < record["bytes"] <= RESOURCES["max_output_bytes"] or record["mode"] != "0644" or not re.fullmatch(r"[0-9a-f]{64}", str(record["sha256"])):
            raise ValueError("Artifact record schema drift")
        if name == "protocol" and record["path"] != PROTOCOL_PATH or name in IMPLEMENTATION_PATHS and record["path"] != IMPLEMENTATION_PATHS[name]:
            raise ValueError("Implementation or protocol path drift")
        if name in SOURCE_NAMES and (not record["path"].startswith(BASE + "runs/") or not record["path"].endswith(".json") or any(part in {"private", "test", ".."} for part in Path(record["path"]).parts)):
            raise ValueError("Source outside public aggregate boundary")


def frozen_files(config_path, config):
    for record in (config["protocol"], *config["implementation"].values(), *config["source"].values()):
        SAFE.require_record(record)
    if SAFE.require_record(config["implementation"]["runner"]).resolve() != Path(__file__).resolve():
        raise ValueError("Runner identity points elsewhere")
    return artifact(config_path)


def validate_probe_metadata(probe, verification, completion, source):
    """Replay the EXP-070 verification-attempt-2 public recovery chain."""
    if (probe.get("experiment_id") != "EXP-070" or probe.get("status") != "CompletedAwaitingVerification"
            or verification.get("experiment_id") != "EXP-070" or verification.get("status") != "Passed"
            or verification.get("failed_count") != 0 or verification.get("source_probe") != source["probe"]
            or verification.get("source_snapshot_unchanged") is not True or verification.get("source_mutated") is not False
            or completion.get("experiment_id") != "EXP-070" or completion.get("status") != "Complete"
            or completion.get("verification") != source["probe_verification"] or completion.get("source_mutated") is not False
            or completion.get("exp070_complete") is not True or completion.get("formal_probe_complete") is not True
            or completion.get("representation_state_assignment_valid") is not True
            or not re.fullmatch(r"[0-9a-f]{64}", str(verification.get("source_snapshot_sha256")))
            or completion.get("source_snapshot_sha256") != verification["source_snapshot_sha256"]):
        raise ValueError("Probe recovery verification/completion chain drift")


def load_inputs(config):
    source = config["source"]
    paths = {name: SAFE.require_record(source[name]) for name in SOURCE_NAMES}
    inputs = {name: SAFE.require_canonical_json(paths[name]) for name in SOURCE_NAMES}
    p, pv, pc, g, gv, a, av = (inputs[name] for name in SOURCE_NAMES)
    expected = ((p, "EXP-070", "CompletedAwaitingVerification"), (pv, "EXP-070", "Passed"), (pc, "EXP-070", "Complete"), (g, "EXP-075", "Analyzed"), (gv, "EXP-075", "Passed"), (a, "EXP-072", "ScoredAwaitingVerification"), (av, "EXP-072", "Passed"))
    if any(item.get("experiment_id") != experiment or item.get("status") != status for item, experiment, status in expected):
        raise ValueError("Source status or experiment binding drift")
    if any(item.get("source_unchanged") is not True for item in (gv, av)):
        raise ValueError("A source verification did not seal unchanged inputs")
    validate_probe_metadata(p, pv, pc, source)
    if pv.get("results_sha256") != digest(p["results"]) or any(item.get("negative_control_failure") is not False for item in (p["results"], pv, pc)) or pc.get("representation_state_assignment_valid") is not True:
        raise ValueError("Probe results or negative control not verified")
    for item in (pv, pc):
        if item.get("representation_state") != p["results"].get("representation_state") or item.get("representation_state_label") != p["results"].get("representation_state_label"):
            raise ValueError("Probe sealed state mismatch")
    if gv.get("complete") is not True or gv.get("exp075_complete") is not True or gv.get("exp071_complete") is not False or gv.get("failed_count") != 0 or gv.get("run") != source["geometry_run"] or gv.get("results_sha256") != digest(g["results"]) or g.get("method", {}).get("post_diagnostic") is not True:
        raise ValueError("Geometry verification chain or post-diagnostic boundary drift")
    if av.get("complete") is not True or av.get("exp072_complete") is not True or av.get("score") != source["ablation_score"] or av.get("results_sha256") != digest(a["results"]) or a.get("results_sha256") != digest(a["results"]):
        raise ValueError("Ablation verification chain drift")
    return inputs


def public_ok(value, path=()):
    if not SAFE.public_privacy_ok(value):
        raise ValueError("Sensitive public field")
    if isinstance(value, dict):
        for key, child in value.items():
            public_ok(child, path + (key,))
    elif isinstance(value, list):
        if len(value) >= 672:
            raise ValueError("Rowwise public vector")
        for index, child in enumerate(value):
            public_ok(child, path + (str(index),))
    elif isinstance(value, str) and ("/Users/" in value or "/private/" in value):
        if path not in {("execution", "command", "0"), ("environment", "python_executable")} or value != str(Path(sys.executable).resolve()):
            raise ValueError("Private path disclosure")


def write_once(path, payload):
    if path.parent.is_symlink() or not path.parent.is_dir() or os.path.lexists(path):
        raise FileExistsError("Output is not fresh")
    descriptor, name = tempfile.mkstemp(prefix=".exp074-", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o644)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def peak_rss():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def budget(started, root=None):
    if time.monotonic() - started > RESOURCES["max_wall_seconds"] or peak_rss() > RESOURCES["max_peak_rss_bytes"] or root is not None and sum(path.stat().st_size for path in root.iterdir()) > RESOURCES["max_output_bytes"]:
        raise RuntimeError("Synthesis resource ceiling exceeded")


@contextmanager
def synthesis_lock():
    with SAFE._file_mutex(MODULE_DIR / "private/locks/exp074-synthesis.lock", "EXP-074 synthesis"):
        yield


def execution(config_path, started, ended):
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True, capture_output=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=PROJECT_ROOT, text=True, capture_output=True, check=True).stdout)
    return {"started_at_utc": started, "ended_at_utc": ended, "command": [str(Path(sys.executable).resolve()), IMPLEMENTATION_PATHS["runner"], "--config", config_path.relative_to(PROJECT_ROOT).as_posix()], "cwd": ".", "git_commit": commit, "git_dirty": dirty}


def run(config_path):
    config_path = config_path.resolve()
    started, started_utc = time.monotonic(), datetime.now(timezone.utc).isoformat()
    config = SAFE.strict_json(config_path)
    validate_config(config)
    with synthesis_lock():
        config_record = frozen_files(config_path, config)
        root = SAFE.resolve_project(config["outputs"]["public_root"], must_exist=False)
        if os.path.lexists(root):
            raise FileExistsError("Synthesis attempt already exists")
        inputs = load_inputs(config)
        summary = make_summary(inputs, config["source"])
        public_ok(summary)
        budget(started)
        root.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        root.mkdir(mode=0o755)
        root.chmod(0o755)
        try:
            write_once(root / "summary.json", canonical_json_bytes(summary))
            log = {"experiment_id": "EXP-074", "stage": "synthesis", "status": "SynthesizedAwaitingVerification", "sources": 7}
            write_once(root / "stdout.log", canonical_json_bytes(log))
            if frozen_files(config_path, config) != config_record:
                raise ValueError("Config changed during synthesis")
            payload = {"schema_version": "exp-074-run-v1", "experiment_id": "EXP-074", "run_id": "exp-074-phase-b-synthesis", "attempt_id": "attempt-1", "tier": "Major read-only synthesis", "rq_id": "RQ-S4", "stage": "synthesis", "status": "SynthesizedAwaitingVerification",
                       "config": config_record, "protocol": config["protocol"], "source": config["source"], "source_snapshot_sha256": digest(config["source"]),
                       "summary": artifact(root / "summary.json"), "summary_sha256": digest(summary), "stdout": artifact(root / "stdout.log"),
                       "data": {"dataset": "DATA-SO-TASK-V1", "split": "train", "rows": 3360, "outer_folds": 5, "label_order": ["love", "joy", "surprise", "anger", "sadness", "fear"]},
                       "execution": execution(config_path, started_utc, datetime.now(timezone.utc).isoformat()), "environment": {"python_executable": str(Path(sys.executable).resolve()), "python_version": platform.python_version(), "platform": platform.platform(), "machine": platform.machine(), "cpu_count": os.cpu_count()},
                       "resources": {"wall_seconds": time.monotonic() - started, "peak_rss_bytes": peak_rss(), "api_cost_usd": 0}, "access": ACCESS, "claim_boundary": CLAIM}
            public_ok(payload)
            budget(started, root)
            if sum(path.stat().st_size for path in root.iterdir()) + len(canonical_json_bytes(payload)) > RESOURCES["max_output_bytes"]:
                raise RuntimeError("Output budget exceeded")
            write_once(root / "run.json", canonical_json_bytes(payload))
            if SAFE.require_safe_root(root, private=False) != {"run.json", "summary.json", "stdout.log"}:
                raise ValueError("Output inventory drift")
            SAFE.require_file_modes(root, ["run.json", "summary.json", "stdout.log"], private=False)
            return payload
        except BaseException as error:
            if not os.path.lexists(root / "failure.json"):
                write_once(root / "failure.json", canonical_json_bytes({"experiment_id": "EXP-074", "status": "Failed", "error_type": type(error).__name__, "automatic_retry": False}))
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = run(args.config.resolve())
    except BaseException as error:
        print(json.dumps({"experiment_id": "EXP-074", "status": "Failed", "error_type": type(error).__name__}), file=sys.stderr)
        return 1
    print(json.dumps({"experiment_id": "EXP-074", "status": result["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
