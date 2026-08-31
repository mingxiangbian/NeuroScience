#!/usr/bin/env python3
"""Independent, public-only EXP-074 state recomputation and verification."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
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
import sys
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
ACCESS = {"verified_public_aggregates_read": True, "private_files_read": False, "array_values_read": False, "labels_read": False, "text_read": False, "model_loaded": False, "forward_executed": False, "validation_accessed": False, "test_accessed": False, "source_mutated": False}
HISTORY = {"exp071": "Failed", "exp071_incident002": "Complete", "exp075_post_diagnostic": True, "exp073": "Not executed (optional)", "context_c2": "Paused", "phase_b_minimum_complete": False}
CLAIM = "Same-train outer-heldout cross-training-seed representation replication and inference-time functional dependency are separate findings. Geometry preserves undefined CKA without imputation. No causal emotion mechanism, independent-data generalization, deployment efficiency, or original EXP-071 success is claimed."


def _helpers():
    path = MODULE_DIR / "verify_exp071_drift.py"
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != 121050 or stat.S_IMODE(info.st_mode) != 0o644 or hashlib.sha256(path.read_bytes()).hexdigest() != "0a6e0e03a2f14212bc2bf0d3a1ecc3d9cf4eec1ee8a3a9f7b44cd3ca83a0bbd2":
        raise ValueError("Pinned independent IO helper drift")
    spec = importlib.util.spec_from_file_location("exp074_independent_io", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SAFE = _helpers()
canonical_json_bytes, artifact = SAFE.canonical_json_bytes, SAFE.artifact


def digest(value):
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def number(value):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError("Expected a finite aggregate")
    return float(value)


def representation_state(results):
    if results.get("negative_control_failure") is not False:
        raise ValueError("Negative control blocks representation assignment")
    votes, passed = {}, []
    for seed in (43, 44):
        detail = {}
        for point in ("H27", "HF"):
            item = results["main_contrasts"]["m3-s%d:%s" % (seed, point)]
            effect = number(item["delta"]["five_label_macro_ap"])
            interval = item["bootstrap_delta_intervals"]["five_label_macro_ap"]
            if type(interval) is not list or len(interval) != 2:
                raise ValueError("Bootstrap interval shape mismatch")
            lower, upper = map(number, interval)
            if lower > upper:
                raise ValueError("Bootstrap interval reversed")
            detail[point] = {"delta": effect, "interval": interval, "passed": effect > 0.0 and lower > 0.0}
        vote = detail["H27"]["passed"] and detail["HF"]["passed"]
        votes[str(seed)] = {"passed": vote, "points": detail}
        passed.append(vote)
    count = passed.count(True)
    state = ("No replicated representation effect", "Representation effect seed-sensitive", "Representation effect replicated")[count]
    if type(results.get("representation_state")) is not int or results["representation_state"] != count or results.get("representation_state_label") != state or results.get("seed_votes") != votes:
        raise ValueError("Recomputed representation result disagrees with original")
    return {"state": state, "passed_seeds": count, "seed_votes": votes, "negative_control_failure": False}


def functional_state(results):
    conditions = results.get("conditions", {})
    if results.get("condition_order") != ABLATION_ORDER or set(conditions) != set(ABLATION_ORDER):
        raise ValueError("Incomplete functional ablation family")
    details = {}
    for seed in (43, 44):
        baseline = number(conditions[f"s{seed}:A0"]["metrics"]["five_label_macro_f1"])
        deltas = []
        for name in ("A2", "A3"):
            item = conditions[f"s{seed}:{name}"]
            current = number(item["metrics"]["five_label_macro_f1"])
            delta = number(item["delta_from_full"]["five_label_macro_f1"])
            if not 0 <= baseline <= 1 or not 0 <= current <= 1 or abs((current - baseline) - delta) > 1e-12:
                raise ValueError("Functional score difference inconsistent")
            deltas.append(delta)
        a2_drop, a3_drop = -deltas[0], -deltas[1]
        details[str(seed)] = {"attention_off_drop": a2_drop, "mlp_off_drop": a3_drop, "D": a2_drop - a3_drop}
    left, right = details["43"]["D"], details["44"]["D"]
    if left >= 0.01 and right >= 0.01:
        label = "Stable Attention-dominant dependency"
    elif left <= -0.01 and right <= -0.01:
        label = "Stable MLP-dominant dependency"
    else:
        label = "Both contribute / no stable dominance"
    return {"state": label, "metric": "five_label_macro_f1", "definition": "drop(A2)-drop(A3)=-delta(A2)+delta(A3)", "threshold": 0.01, "seeds": details}


def validate_geometry(results):
    if results.get("condition_order") != GEOMETRY_ORDER or set(results.get("conditions", {})) != set(GEOMETRY_ORDER):
        raise ValueError("Geometry points omitted or reordered")
    discovery_missing = []
    for condition in GEOMETRY_ORDER:
        item = results["conditions"][condition]["linear_cka"]
        if len(item["per_fold"]) != 5 or len(item["reason_by_fold"]) != 5:
            raise ValueError("Geometry folds omitted")
        defined = 0
        for value, reason in zip(item["per_fold"], item["reason_by_fold"]):
            if value is None:
                if reason != "zero_centered_variance":
                    raise ValueError("Undefined geometry reason missing")
            else:
                if reason is not None or not 0 <= number(value) <= 1:
                    raise ValueError("Invalid defined geometry value")
                defined += 1
        if item["n_defined"] != defined:
            raise ValueError("Geometry defined count mismatch")
        if defined < 5:
            if item["mean"] is not None or item["sample_sd"] is not None or item["reason"] != "undefined_fold_cka":
                raise ValueError("Undefined fold was imputed")
        elif not 0 <= number(item["mean"]) <= 1 or number(item["sample_sd"]) < 0 or item["reason"] is not None:
            raise ValueError("Invalid complete-fold aggregate")
        if condition.startswith("s42:"):
            discovery_missing.append(item["mean"] is None)
    correlation = results["seed42_spearman"]
    if correlation["point_order"] != list(POINTS) or correlation["n"] != 9:
        raise ValueError("Spearman point inventory mismatch")
    if any(discovery_missing) and (correlation["rho"] is not None or correlation["reason"] != "undefined_cka_input"):
        raise ValueError("Undefined correlation was imputed")


def make_summary(inputs, source):
    probe, geometry, ablation = inputs["probe"]["results"], inputs["geometry_run"]["results"], inputs["ablation_score"]["results"]
    validate_geometry(geometry)
    return {"schema_version": "exp-074-summary-v1", "experiment_id": "EXP-074", "sources": source,
            "representation_effect": representation_state(probe), "functional_dependency": functional_state(ablation),
            "probe": {"main_metrics": probe["main_metrics"], "main_contrasts": probe["main_contrasts"]},
            "geometry": geometry, "ablation": ablation, "history_and_scope": HISTORY, "claim_boundary": CLAIM}


def validate_config(config):
    if set(config) != {"experiment_id", "protocol", "implementation", "source", "outputs", "resources"} or config["experiment_id"] != "EXP-074" or config["resources"] != RESOURCES or config["outputs"] != OUTPUTS or set(config["source"]) != set(SOURCE_NAMES) or set(config["implementation"]) != set(IMPLEMENTATION_PATHS):
        raise ValueError("EXP-074 fixed config mismatch")
    for name, record in {"protocol": config["protocol"], **config["implementation"], **config["source"]}.items():
        if set(record) != {"path", "bytes", "mode", "sha256"} or type(record["bytes"]) is not int or not 0 < record["bytes"] <= RESOURCES["max_output_bytes"] or record["mode"] != "0644" or not re.fullmatch(r"[0-9a-f]{64}", str(record["sha256"])):
            raise ValueError("Invalid frozen artifact record")
        if name == "protocol" and record["path"] != PROTOCOL_PATH or name in IMPLEMENTATION_PATHS and record["path"] != IMPLEMENTATION_PATHS[name]:
            raise ValueError("Protocol or implementation path mismatch")
        if name in SOURCE_NAMES and (not record["path"].startswith(BASE + "runs/") or not record["path"].endswith(".json") or any(part in {"private", "test", ".."} for part in Path(record["path"]).parts)):
            raise ValueError("Source is not a public aggregate")


def frozen_files(config_path, config):
    for record in (config["protocol"], *config["implementation"].values(), *config["source"].values()):
        SAFE.require_record(record)
    if SAFE.require_record(config["implementation"]["verifier"]).resolve() != Path(__file__).resolve():
        raise ValueError("Verifier identity points elsewhere")
    return artifact(config_path)


def validate_probe_metadata(probe, verification, completion, source):
    if probe.get("experiment_id") != "EXP-070" or probe.get("status") != "CompletedAwaitingVerification":
        raise ValueError("Probe source identity/status mismatch")
    if verification.get("experiment_id") != "EXP-070" or verification.get("status") != "Passed" or verification.get("failed_count") != 0:
        raise ValueError("Probe recovery verification did not pass")
    if verification.get("source_probe") != source["probe"] or verification.get("source_snapshot_unchanged") is not True or verification.get("source_mutated") is not False:
        raise ValueError("Probe recovery source binding mismatch")
    if completion.get("experiment_id") != "EXP-070" or completion.get("status") != "Complete" or completion.get("verification") != source["probe_verification"] or completion.get("source_mutated") is not False:
        raise ValueError("Probe recovery completion binding mismatch")
    if any(completion.get(key) is not True for key in ("exp070_complete", "formal_probe_complete", "representation_state_assignment_valid")):
        raise ValueError("Probe completion does not permit synthesis")
    snapshot = verification.get("source_snapshot_sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", str(snapshot)) or completion.get("source_snapshot_sha256") != snapshot:
        raise ValueError("Probe recovery snapshot mismatch")


def load_inputs(config):
    source = config["source"]
    paths = {name: SAFE.require_record(source[name]) for name in SOURCE_NAMES}
    inputs = {name: SAFE.require_canonical_json(paths[name]) for name in SOURCE_NAMES}
    p, pv, pc, g, gv, a, av = [inputs[name] for name in SOURCE_NAMES]
    for payload, experiment, status in ((p, "EXP-070", "CompletedAwaitingVerification"), (pv, "EXP-070", "Passed"), (pc, "EXP-070", "Complete"), (g, "EXP-075", "Analyzed"), (gv, "EXP-075", "Passed"), (a, "EXP-072", "ScoredAwaitingVerification"), (av, "EXP-072", "Passed")):
        if payload.get("experiment_id") != experiment or payload.get("status") != status:
            raise ValueError("Source status/experiment mismatch")
    if any(terminal.get("source_unchanged") is not True for terminal in (gv, av)):
        raise ValueError("Upstream verification lacks unchanged-source seal")
    validate_probe_metadata(p, pv, pc, source)
    if pv.get("results_sha256") != digest(p["results"]):
        raise ValueError("Probe verification identity or result mismatch")
    if pc.get("representation_state_assignment_valid") is not True or any(item.get("negative_control_failure") is not False for item in (p["results"], pv, pc)):
        raise ValueError("Probe state not valid")
    for terminal in (pv, pc):
        if terminal.get("representation_state") != p["results"].get("representation_state") or terminal.get("representation_state_label") != p["results"].get("representation_state_label"):
            raise ValueError("Probe terminal state mismatch")
    if gv.get("complete") is not True or gv.get("exp075_complete") is not True or gv.get("exp071_complete") is not False or gv.get("failed_count") != 0 or gv.get("run") != source["geometry_run"] or gv.get("results_sha256") != digest(g["results"]) or g.get("method", {}).get("post_diagnostic") is not True:
        raise ValueError("Geometry verification mismatch")
    if av.get("complete") is not True or av.get("exp072_complete") is not True or av.get("score") != source["ablation_score"] or av.get("results_sha256") != digest(a["results"]) or a.get("results_sha256") != digest(a["results"]):
        raise ValueError("Ablation verification mismatch")
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


def peak_rss():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def budget(started, root=None):
    if time.monotonic() - started > RESOURCES["max_wall_seconds"] or peak_rss() > RESOURCES["max_peak_rss_bytes"] or root is not None and sum(path.stat().st_size for path in root.iterdir()) > RESOURCES["max_output_bytes"]:
        raise RuntimeError("Verification budget exceeded")


@contextmanager
def synthesis_lock():
    with SAFE._file_mutex(MODULE_DIR / "private/locks/exp074-synthesis.lock", "EXP-074 synthesis"):
        yield


def equal(left, right):
    if isinstance(right, dict):
        return isinstance(left, dict) and set(left) == set(right) and all(equal(left[key], right[key]) for key in right)
    if isinstance(right, list):
        return isinstance(left, list) and len(left) == len(right) and all(equal(a, b) for a, b in zip(left, right))
    if type(right) is float:
        return type(left) is float and math.isfinite(left) and math.isclose(left, right, rel_tol=0, abs_tol=1e-12)
    return type(left) is type(right) and left == right


def validate_payload(config_path, config, summary):
    root = SAFE.resolve_project(config["outputs"]["public_root"])
    actual = SAFE.require_canonical_json(root / "summary.json")
    if not equal(actual, summary):
        raise ValueError("Independent synthesis summary mismatch")
    run = SAFE.require_canonical_json(root / "run.json")
    expected = {"schema_version": "exp-074-run-v1", "experiment_id": "EXP-074", "run_id": "exp-074-phase-b-synthesis", "attempt_id": "attempt-1", "tier": "Major read-only synthesis", "rq_id": "RQ-S4", "stage": "synthesis", "status": "SynthesizedAwaitingVerification", "config": artifact(config_path), "protocol": config["protocol"], "source": config["source"], "source_snapshot_sha256": digest(config["source"]), "summary": artifact(root / "summary.json"), "summary_sha256": digest(actual), "stdout": artifact(root / "stdout.log"), "data": {"dataset": "DATA-SO-TASK-V1", "split": "train", "rows": 3360, "outer_folds": 5, "label_order": ["love", "joy", "surprise", "anger", "sadness", "fear"]}, "access": ACCESS, "claim_boundary": CLAIM}
    if set(run) != set(expected) | {"execution", "environment", "resources"} or any(run.get(key) != value for key, value in expected.items()):
        raise ValueError("Run envelope binding mismatch")
    execution = run["execution"]
    if set(execution) != {"started_at_utc", "ended_at_utc", "command", "cwd", "git_commit", "git_dirty"} or execution["command"] != [str(Path(sys.executable).resolve()), IMPLEMENTATION_PATHS["runner"], "--config", config_path.relative_to(PROJECT_ROOT).as_posix()] or execution["cwd"] != "." or not re.fullmatch(r"[0-9a-f]{40}", str(execution["git_commit"])) or type(execution["git_dirty"]) is not bool:
        raise ValueError("Execution record mismatch")
    start, end = [datetime.fromisoformat(execution[key]) for key in ("started_at_utc", "ended_at_utc")]
    if any(moment.utcoffset() is None or moment.utcoffset().total_seconds() != 0 for moment in (start, end)) or not 0 <= (end - start).total_seconds() <= RESOURCES["max_wall_seconds"]:
        raise ValueError("Execution time not bounded UTC")
    environment = {"python_executable": str(Path(sys.executable).resolve()), "python_version": platform.python_version(), "platform": platform.platform(), "machine": platform.machine(), "cpu_count": os.cpu_count()}
    if run["environment"] != environment:
        raise ValueError("Environment metadata drift")
    usage = run["resources"]
    if set(usage) != {"wall_seconds", "peak_rss_bytes", "api_cost_usd"} or not 0 <= number(usage["wall_seconds"]) <= RESOURCES["max_wall_seconds"] or type(usage["peak_rss_bytes"]) is not int or not 0 < usage["peak_rss_bytes"] <= RESOURCES["max_peak_rss_bytes"] or usage["api_cost_usd"] != 0:
        raise ValueError("Run resource ceiling violated")
    log = {"experiment_id": "EXP-074", "stage": "synthesis", "status": "SynthesizedAwaitingVerification", "sources": 7}
    if (root / "stdout.log").read_bytes() != canonical_json_bytes(log):
        raise ValueError("Stdout record drift")
    public_ok(run)
    public_ok(actual)
    return run


def no_compute_import():
    if {name.split(".", 1)[0] for name in sys.modules} & {"numpy", "torch", "mlx", "transformers", "mlx_lm"}:
        raise ValueError("Synthesis verifier must not import array or model libraries")
    for module in list(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename and Path(filename).resolve() == MODULE_DIR / "run_exp074_synthesis.py":
            raise ValueError("Synthesis verifier imported producer")


def verify(config_path):
    config_path = config_path.resolve()
    started = time.monotonic()
    config = SAFE.strict_json(config_path)
    validate_config(config)
    no_compute_import()
    with synthesis_lock():
        initial = frozen_files(config_path, config)
        root = SAFE.resolve_project(config["outputs"]["public_root"])
        if SAFE.require_safe_root(root, private=False) != {"run.json", "summary.json", "stdout.log"}:
            raise ValueError("Verifier requires exact unverified output prefix")
        SAFE.require_file_modes(root, ["run.json", "summary.json", "stdout.log"], private=False)
        sealed = [artifact(root / name) for name in ("run.json", "summary.json", "stdout.log")]
        inputs = load_inputs(config)
        summary = make_summary(inputs, config["source"])
        validate_payload(config_path, config, summary)
        if frozen_files(config_path, config) != initial or [artifact(root / name) for name in ("run.json", "summary.json", "stdout.log")] != sealed:
            raise ValueError("Source or output changed during verification")
        budget(started, root)
        payload = {"schema_version": "exp-074-verification-v1", "experiment_id": "EXP-074", "status": "Passed", "complete": True, "exp074_complete": True, "phase_b_minimum_complete": True, "exp071_complete": False, "config": initial, "run": artifact(root / "run.json"), "summary": artifact(root / "summary.json"), "summary_sha256": digest(SAFE.require_canonical_json(root / "summary.json")), "source_snapshot_sha256": digest(config["source"]), "source_unchanged": True, "representation_state": summary["representation_effect"]["state"], "functional_dependency_state": summary["functional_dependency"]["state"], "access": ACCESS, "resources": {"wall_seconds": time.monotonic() - started, "peak_rss_bytes": peak_rss(), "api_cost_usd": 0}, "claim_boundary": CLAIM}
        public_ok(payload)
        if sum(path.stat().st_size for path in root.iterdir()) + len(canonical_json_bytes(payload)) > RESOURCES["max_output_bytes"]:
            raise RuntimeError("Verification output budget exceeded")
        SAFE.create_json_once(root / "verification.json", payload)
        if SAFE.require_safe_root(root, private=False) != {"run.json", "summary.json", "stdout.log", "verification.json"}:
            raise ValueError("Final output inventory mismatch")
        return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args(argv)
    path = args.config.resolve()
    try:
        result = verify(path)
    except BaseException as error:
        try:
            config = SAFE.strict_json(path)
            validate_config(config)
            root = SAFE.resolve_project(config["outputs"]["public_root"])
            if SAFE.require_safe_root(root, private=False) == {"run.json", "summary.json", "stdout.log"}:
                SAFE.create_json_once(root / "verification.json", {"experiment_id": "EXP-074", "status": "Failed", "complete": False, "exp074_complete": False, "error_type": type(error).__name__, "automatic_retry": False})
        except Exception:
            pass
        print(json.dumps({"experiment_id": "EXP-074", "status": "Failed", "error_type": type(error).__name__}), file=sys.stderr)
        return 1
    print(json.dumps({"experiment_id": "EXP-074", "status": result["status"], "complete": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
