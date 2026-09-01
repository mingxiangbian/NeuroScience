"""Independent EXP-085 functional, transfer-accounting and phase-safety audit.

No producer, model backend, source fetch or gold data is imported. Saved stops
can pass artifact auditing without passing the nine-job completion gate.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import struct
import sys
import tarfile
import sqlite3
from datetime import datetime, timezone

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "private/validation/exp-085/attempt-2"
SPEC = importlib.util.spec_from_file_location("exp085_independent_safety", ROOT / "scripts/verify_bounded_runtime.py")
B = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(B)
LOCAL = B.LOCAL
require, close, sha, finite = B.require, B.close, B.sha, B.finite
LABELS, COSTS = LOCAL.LABELS, B.COSTS
MODES = ("m1_only", "research", "demo")
BUDGETS = {"m1_only": 0, "research": 500, "demo": 20}
STRATEGY = "m1-receipt-transfer-v1"
SOURCE_JOB = "5ab3326150ee448ba326233264967d34"
SOURCE_SNAPSHOT = "cd656b035e76c9b4916c80b864a4f923de08c67af8863c426b3f774ec1c78a16"
SOURCE_LOGICAL = "8c0cc285ff71fd041eb832d5a8422d68dcaad84228a9c3b00d14f213dacd17a4"
PARENT_HASHES = {
    "plan": "24c1c85d7aadb8a77743203972df4652c1204f2f626ec8f2c6182116e731338f",
    "run": "e97540cec9a2cf87bdfe22f99c06a979c50d54603702b260a5a30551ad591d2a",
    "verification": "22e667dd23da182b40e5fbb876999ac7465682275258e10a8663640bf4041bd1",
}
ARCHIVE_SHA256 = "91ed8d8b0d8d8b631c7ad440cc824cd7dde813c0dc6f997bb1b8839dbef751af"
PREVIOUS_HASHES = {
    "plan": "9de78c110ef9a078025df831138e5acd63d08a596e7c972d5bd13d52f04aec25",
    "run": "b9965aaa8340212a3e49b3d1290febe962c402aeb3e31de97a10dc336f7d4686",
    "verification": "426c3ba406ca42b13942275b8d87384a8e8e9fa71fc9629739ec6b1a0f75bf2f",
}
PREVIOUS_ARCHIVE_SHA256 = "76664bc9b6d532e2fc0e81a7b169d25d512f32a72380cd5982e4360c9ce49733"
PROTOCOL = "experiments/stack-overflow-emotion-gold/protocols/exp-085-staged-website-bounded-acceptance-attempt-2.md"
MODEL_CONFIG = "experiments/stack-overflow-emotion-gold/oof-router/runs/exp-066-headless-runtime-parity/attempt-2/frozen-sources/config.json"
MODEL_CONFIG_SHA256 = "106db4b86614ac70c84f04a322b046bc1049686099c590997955120993bb9983"
BRIDGE_SHA256 = "45690716a8cd25688a1d7f64eba437acf75dc90cf7caf478c3a38a73335f1ddd"
COMPLETION_SHA256 = "b039b80a3ba1778d38352fc8ee7c075dc342e17dd127d9acfd1574d99c149408"
FEATURES = [f"m1_probability_{label}" for label in LABELS] + [
    "m1_mean_binary_entropy", "m1_max_binary_entropy", "m1_minimum_threshold_margin",
    "m1_predicted_cardinality", "m1_highest_probability", "m1_lowest_probability",
    "character_length", "m1_token_length",
]


def float32_bytes(values):
    values = LOCAL.probabilities(values)
    packed = struct.pack("<6f", *values)
    require(list(struct.unpack("<6f", packed)) == values, "lossy_float32_probability")
    return packed


def token_metadata(value):
    require(isinstance(value, dict) and set(value) == {"input_tokens", "used_tokens", "truncated"}, "m1_token_schema")
    full, used = value["input_tokens"], value["used_tokens"]
    require(type(full) is int and type(used) is int and 1 <= used <= 256
            and used == min(full, 256) and type(value["truncated"]) is bool
            and value["truncated"] == (full > used), "m1_token_contract")
    return value


def receipt_digest(rows):
    """Hash exactly the selected phase's canonical JSONL envelopes, in order."""
    return sha("".join(LOCAL.canonical(row) + "\n" for row in rows))


def check_parent_archive(path, expected_sha, plan, run, verification):
    require(B.regular_file(path) == expected_sha, "parent_archive_hash")
    require(run.get("status") == "Completed" and verification.get("status") == "Passed"
            and verification.get("diagnostic_completed") is True
            and verification.get("safety", {}).get("gate_passed") is True, "parent_not_verified")
    sources = plan.get("sources")
    require(isinstance(sources, dict) and len(sources) == 39 and "protocol.md" not in sources, "parent_source_count")
    expected = {**sources, "protocol.md": plan["protocol"]["sha256"]}
    actual, total = {}, 0
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            name = member.name
            require(not Path(name).is_absolute() and ".." not in Path(name).parts
                    and member.isfile() and name not in actual and name in expected
                    and 0 <= member.size <= 2 * 1024**2, "parent_archive_member")
            total += member.size
            require(total <= 32 * 1024**2, "parent_archive_size")
            stream = archive.extractfile(member)
            require(stream is not None, "parent_archive_payload")
            payload = stream.read(member.size + 1)
            require(len(payload) == member.size, "parent_archive_payload")
            actual[name] = sha(payload)
    require(actual == expected and B.regular_file(path) == expected_sha, "parent_archive_sources")
    # Deliberately do not compare old production files with their current paths.
    return {"members": len(actual), "sha256": expected_sha, "old_sources_checked_in_archive": True}


def check_previous_attempt(plan):
    documents = {}
    expected_bindings = {}
    for name, expected in PREVIOUS_HASHES.items():
        relative = f"private/validation/exp-085/attempt-1/{name}.json"
        require(plan.get("previous_attempt", {}).get(name) == {"path": relative, "sha256": expected}, "previous_attempt_binding")
        path = ROOT / relative
        require(B.regular_file(path) == expected, "previous_attempt_hash")
        documents[name] = LOCAL.strict_json(path.read_text())
        expected_bindings[name] = {"path": relative, "sha256": expected}
    run, verification, previous_plan = documents["run"], documents["verification"], documents["plan"]
    require(run.get("experiment_id") == "EXP-085" and run.get("attempt") == 1
            and run.get("status") == "Stopped" and run.get("failure_code") == "staged_internal_error", "previous_run_terminal")
    require(verification.get("experiment_id") == "EXP-085" and verification.get("attempt") == 1
            and verification.get("status") == "Failed" and verification.get("error_code") == "staged_lower_bound_range"
            and verification.get("exp085_complete") is False and verification.get("operational_state") == "stop-required", "previous_verification_terminal")
    archive_binding = {"path": "private/validation/exp-085/attempt-1/frozen-code.tar.gz",
                       "sha256": PREVIOUS_ARCHIVE_SHA256, "members": 33}
    require(plan.get("previous_attempt", {}).get("archive") == archive_binding
            and set(plan["previous_attempt"]) == {"plan", "run", "verification", "archive"}, "previous_archive_binding")
    archive_path = ROOT / archive_binding["path"]
    require(B.regular_file(archive_path) == PREVIOUS_ARCHIVE_SHA256, "previous_archive_hash")
    sources = previous_plan.get("sources")
    require(isinstance(sources, dict) and len(sources) == 32, "previous_source_count")
    protocol = previous_plan.get("protocol")
    require(isinstance(protocol, dict) and re.fullmatch(r"[a-f0-9]{64}", str(protocol.get("sha256"))), "previous_protocol_binding")
    expected_members = {**sources, "protocol.md": protocol["sha256"]}
    actual, total = {}, 0
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive:
            require(not Path(member.name).is_absolute() and ".." not in Path(member.name).parts
                    and member.isfile() and member.name in expected_members and member.name not in actual
                    and 0 <= member.size <= 2 * 1024**2, "previous_archive_member")
            stream = archive.extractfile(member)
            require(stream is not None, "previous_archive_payload")
            payload = stream.read(member.size + 1)
            total += len(payload)
            require(len(payload) == member.size and total <= 32 * 1024**2, "previous_archive_payload")
            actual[member.name] = sha(payload)
    require(actual == expected_members and B.regular_file(archive_path) == PREVIOUS_ARCHIVE_SHA256, "previous_archive_sources")
    return {"run_status": "Stopped", "run_failure_code": "staged_internal_error",
            "verification_status": "Failed", "verification_error_code": "staged_lower_bound_range",
            "exp085_complete": False, "archive_members": 33, "archive_sha256": PREVIOUS_ARCHIVE_SHA256,
            "reference_scope": "version_and_failure_lineage_only_not_model_input_or_success_reference"}


def validate_router(router):
    require(isinstance(router, dict) and router.get("labels") == list(LABELS)
            and router.get("features") == FEATURES and router.get("classes") == [0, 1], "router_metadata")
    for name in ("scaler_mean", "scaler_scale", "coef"):
        require(isinstance(router.get(name), list) and len(router[name]) == 14
                and all(type(x) in (int, float) and math.isfinite(x) for x in router[name]), "router_parameter_shape")
    require(all(x > 0 for x in router["scaler_scale"])
            and type(router.get("intercept")) in (int, float) and math.isfinite(router["intercept"]), "router_parameters")
    require(all(type(router.get(name)) in (int, float) and math.isfinite(router[name]) and 0 <= router[name] <= 1
                for name in ("m1_threshold", "m3_threshold", "cutoff")), "router_thresholds")
    return router


def recompute_route(probabilities, character_length, tokens, router):
    """Scalar independent implementation of the frozen fourteen-feature rule."""
    p = LOCAL.probabilities(probabilities)
    require(type(character_length) is int and character_length > 0, "character_length")
    used = token_metadata(tokens)["used_tokens"]
    clipped = [min(max(value, 1e-15), 1 - 1e-15) for value in p]
    entropies = [-value * math.log(value) - (1 - value) * math.log1p(-value) for value in clipped]
    threshold = router["m1_threshold"]
    features = p + [sum(entropies) / 6, max(entropies), min(abs(value - threshold) for value in p),
                    sum(value >= threshold for value in p), max(p), min(p), character_length, used]
    logit = math.fsum((value - mean) / scale * weight for value, mean, scale, weight in
                     zip(features, router["scaler_mean"], router["scaler_scale"], router["coef"])) + router["intercept"]
    score = 1 / (1 + math.exp(-logit)) if logit >= 0 else math.exp(logit) / (1 + math.exp(logit))
    return {"features": features, "score": score, "eligible": score >= router["cutoff"],
            "m1_prediction": [int(value >= threshold) for value in p]}


def expected_receipts(records, rows, *, mode, budget, phase):
    require(mode in MODES and type(budget) is int and budget == BUDGETS[mode], "mode_budget")
    require(phase in {"m1", "m3"} and (phase != "m3" or mode != "m1_only"), "phase_mode")
    require(isinstance(rows, list) and len(rows) <= len(records)
            and [row.get("ordinal") for row in rows] == list(range(len(rows))), "receipt_prefix")
    seen_m1, seen_m3, cumulative = set(), set(), {name: 0 for name in COSTS}
    expected = []
    for row, record in zip(rows, records):
        exact, result = record["model_input_hash"], row["result"]
        require(row.get("input_sha256") == exact and type(result.get("hypothetical_route")) is bool, "receipt_input_route")
        requested = phase == "m3" and result["hypothetical_route"]
        counters = {name: 0 for name in COSTS}
        counters.update(m1_attempts=int(phase == "m1" and exact not in seen_m1),
                        m1_cache_hit=int(phase == "m3" or exact in seen_m1))
        seen_m1.add(exact)
        fallback = None
        if requested:
            if exact in seen_m3:
                counters["m3_cache_hit"] = 1
            elif cumulative["m3_attempts"] < budget:
                counters["m3_attempts"] = counters["m3_succeeded"] = 1
                seen_m3.add(exact)
            else:
                require(mode == "demo", "research_budget_fallback")
                fallback = "m3_budget_exhausted"
        cumulative = {name: cumulative[name] + counters[name] for name in COSTS}
        expected.append({"counters": counters, "cumulative_counters": dict(cumulative),
                         "requested": requested, "fallback": fallback,
                         "path": "m3" if requested and fallback is None else "m1"})
    return expected


def recompute_cost(records, rows, *, mode, budget, phase, complete=False):
    expectations = expected_receipts(records, rows, mode=mode, budget=budget, phase=phase)
    totals = {name: 0 for name in COSTS}
    fallbacks = Counter()
    for row, expected in zip(rows, expectations):
        result = row["result"]
        for field in ("counters", "cumulative_counters"):
            require(isinstance(result.get(field), dict) and all(type(result[field].get(name)) is int for name in COSTS), "counter_types")
            close(result[field], expected[field], "phase_cost_mismatch", tolerance=0)
        require(result.get("route_requested") is expected["requested"]
                and result.get("used_path") == expected["path"]
                and result.get("fallback_reason") == expected["fallback"]
                and result.get("fallback") is bool(expected["fallback"])
                and result["counters"].get("fallback_reason") == expected["fallback"], "cost_route_contract")
        require((result.get("m3_probabilities") is not None) == (expected["path"] == "m3"), "cost_component_availability")
        require(result.get("cache_hit") is bool(expected["counters"]["m1_cache_hit"]
                and (not expected["requested"] or expected["counters"]["m3_cache_hit"])), "raw_phase_cache_flag")
        if phase == "m3":
            require(result.get("prelude_transfer_reuse") is True
                    and result.get("m1_execution_origin") == "current_job_m1_receipt", "transfer_origin")
        totals = expected["cumulative_counters"]
        if expected["fallback"]:
            fallbacks[expected["fallback"]] += 1
    require(not complete or len(rows) == len(records), "partial_phase_called_complete")
    return {"acknowledged_receipts": len(rows), "raw_phase_counters": totals,
            "accounting": {"actual_m1_forward_attempts": totals["m1_attempts"],
                           "within_phase_duplicate_cache_hits": totals["m1_cache_hit"] if phase == "m1" else 0,
                           "prelude_transfer_reuse": len(rows) if phase == "m3" else 0,
                           "m3_attempts": totals["m3_attempts"], "m3_succeeded": totals["m3_succeeded"],
                           "m3_cache_hits": totals["m3_cache_hit"], "audit_extra_calls": totals["audit_extra_calls"]},
            "fallbacks": dict(fallbacks), "cost_complete": bool(complete),
            "unacknowledged_attempts": 0 if complete else None,
            "cost_scope": "completed_phase" if complete else "acknowledged_results_lower_bound"}


def functional_comparison(records, rows, router, *, mode, budget, phase, source_results, prelude=None, known_m3=None):
    validate_router(router)
    require(len(source_results) == len(records), "source_result_alignment")
    known_m3 = {} if known_m3 is None else known_m3
    require(set(known_m3) <= {6}, "unproven_historical_m3_reference")
    expectations = expected_receipts(records, rows, mode=mode, budget=budget, phase=phase)
    max_m1 = max_m3 = None
    covered = []
    for row, record, old, expected in zip(rows, records, source_results, expectations):
        ordinal, result = row["ordinal"], row["result"]
        p1 = LOCAL.probabilities(result.get("m1_probabilities"))
        float32_bytes(p1)
        oldp = LOCAL.probabilities(old.get("m1_probabilities"))
        delta = max(abs(a - b) for a, b in zip(p1, oldp))
        require(delta <= 1e-6, "source_m1_probability_drift")
        max_m1 = delta if max_m1 is None else max(max_m1, delta)
        tokens = token_metadata(result.get("tokenlengths", {}).get("m1"))
        require(tokens == old.get("tokenlengths", {}).get("m1"), "source_token_drift")
        route = recompute_route(p1, len(record["model_input_text"]), tokens, router)
        require(result.get("hypothetical_route") is route["eligible"]
                and result.get("route_eligible") is route["eligible"]
                and old.get("hypothetical_route") is route["eligible"], "independent_router_decision")
        for name, value in (("route_score", route["score"]), ("m1_entropy", route["features"][6]),
                            ("threshold_margin", route["features"][8])):
            close(result.get(name), value, "independent_router_numeric", tolerance=1e-9)
        require(LOCAL.decisions(result.get("m1_prediction")) == route["m1_prediction"]
                == old.get("m1_prediction"), "m1_threshold_decision")
        if phase == "m3":
            require(prelude is not None and ordinal < len(prelude), "replay_without_current_prelude")
            first = prelude[ordinal]["result"]
            require(float32_bytes(p1) == float32_bytes(first["m1_probabilities"])
                    and tokens == first["tokenlengths"]["m1"], "replay_current_prelude_identity")
        p3 = LOCAL.probabilities(result.get("m3_probabilities"), optional=True)
        d3 = LOCAL.decisions(result.get("m3_prediction"), optional=True)
        require((p3 is not None) == (expected["path"] == "m3"), "selected_component_availability")
        if p3 is not None:
            float32_bytes(p3)
            require(d3 == [int(value >= router["m3_threshold"]) for value in p3], "m3_threshold_decision")
            if ordinal in known_m3:
                reference = known_m3[ordinal]
                difference = max(abs(a - b) for a, b in zip(p3, LOCAL.probabilities(reference["m3_probabilities"])))
                require(difference <= 1e-6 and d3 == reference["m3_prediction"]
                        and result["tokenlengths"].get("m3") == reference["tokenlengths"].get("m3"), "known_m3_reference_drift")
                max_m3 = difference if max_m3 is None else max(max_m3, difference)
                covered.append(ordinal)
        else:
            require(d3 is None and result.get("tokenlengths", {}).get("m3") is None, "absent_m3_metadata")
        selected = d3 if expected["path"] == "m3" else route["m1_prediction"]
        labels = [label for label, bit in zip(LABELS, selected) if bit]
        close(result, {"prediction": selected, "prediction6": selected, "active_labels": labels, "labels": labels,
                       "neutral": not labels, "used_path": expected["path"], "actual_model": expected["path"],
                       "route_requested": expected["requested"], "routed": expected["requested"],
                       "fallback": bool(expected["fallback"]), "degraded": bool(expected["fallback"]),
                       "fallback_reason": expected["fallback"],
                       "truncflags": {"m1": tokens["truncated"],
                                      "m3": result["tokenlengths"]["m3"]["truncated"] if p3 is not None else None}},
              "functional_decision_mismatch", tolerance=0)
    return {"verified_receipts": len(rows), "m1_source_max_abs_difference": max_m1,
            "historical_m3_reference_ordinals": sorted(set(covered)), "historical_m3_max_abs_difference": max_m3,
            "historical_m3_scope": "Only ordinal 6 has an EXP-082/084 reference; other M3 outputs require within-EXP-085 comparison."}


def compare_m3_repetitions(rows, baseline):
    """Check observed M3 repeats; never promote them to old independent parity."""
    compared = added = 0
    for row in rows:
        result = row["result"]
        if result.get("m3_probabilities") is None:
            continue
        key = row["input_sha256"]
        value = {name: result[name] for name in ("m3_probabilities", "m3_prediction")}
        value["m3_tokens"] = result["tokenlengths"]["m3"]
        if key in baseline:
            close(value["m3_probabilities"], baseline[key]["m3_probabilities"], "m3_repeat_probability_drift", tolerance=1e-6)
            require(value["m3_prediction"] == baseline[key]["m3_prediction"]
                    and value["m3_tokens"] == baseline[key]["m3_tokens"], "m3_repeat_metadata_drift")
            compared += 1
        else:
            baseline[key] = value
            added += 1
    return {"first_observed_inputs": added, "compared_occurrences": compared,
            "scope": "within_EXP085_observed_repetitions_not_historical_M3_parity"}


def check_transfer(envelope, prelude, *, logical_job_id, phase_id, m1_phase_id):
    require(isinstance(envelope, dict) and envelope.get("logical_job_id") == logical_job_id
            and envelope.get("phase_id") == phase_id and len(prelude) == 340, "transfer_job_binding")
    require(all(row.get("logical_job_id") == logical_job_id and row.get("phase_id") == m1_phase_id for row in prelude), "transfer_prelude_phase")
    require(envelope.get("m1_receipts_sha256") == receipt_digest(prelude), "transfer_current_receipt_digest")
    transfer = envelope.get("transfer")
    require(isinstance(transfer, dict) and set(transfer) == {"base_fingerprint", "entries"}
            and envelope.get("transfer_sha256") == sha(LOCAL.canonical(transfer)), "transfer_hash_schema")
    fingerprint = transfer["base_fingerprint"]
    require(isinstance(fingerprint, str) and re.fullmatch(r"[a-f0-9]{64}", fingerprint)
            and all(row["result"].get("fingerprint") == fingerprint for row in prelude), "transfer_base_fingerprint")
    entries = transfer["entries"]
    require(isinstance(entries, list) and len(entries) == 340, "transfer_count")
    groups = {}
    for ordinal, (entry, row) in enumerate(zip(entries, prelude)):
        require(isinstance(entry, dict) and set(entry) == {"ordinal", "input_sha256", "m1_probabilities", "tokenlengths"}
                and type(entry["ordinal"]) is int and entry["ordinal"] == row["ordinal"] == ordinal
                and entry["input_sha256"] == row["input_sha256"], "transfer_row_identity")
        packed = float32_bytes(entry["m1_probabilities"])
        require(packed == float32_bytes(row["result"]["m1_probabilities"])
                and entry["tokenlengths"] == {"m1": row["result"]["tokenlengths"]["m1"]}, "transfer_current_result_identity")
        token_metadata(entry["tokenlengths"]["m1"])
        value = (packed, entry["tokenlengths"])
        require(entry["input_sha256"] not in groups or groups[entry["input_sha256"]] == value, "transfer_duplicate_disagreement")
        groups[entry["input_sha256"]] = value
    derived = sha(LOCAL.canonical({"base_fingerprint": fingerprint, "strategy": STRATEGY,
                                  "transfer_sha256": envelope["transfer_sha256"]}))
    return {"transfer_items": len(entries), "cache_entries": len(groups), "fingerprint": derived,
            "base_fingerprint": fingerprint, "transfer_sha256": envelope["transfer_sha256"]}


def load_router(plan, project_root=None):
    """Read the small, hash-bound router coefficients; no backend construction."""
    import numpy as np

    project_root = ROOT.parent if project_root is None else project_root
    require(plan.get("model_config") == {"path": MODEL_CONFIG, "sha256": MODEL_CONFIG_SHA256}, "model_config_binding")
    path = B.source_path(MODEL_CONFIG, project_root)
    require(B.regular_file(path) == MODEL_CONFIG_SHA256, "model_config_hash")
    config = LOCAL.strict_json(path.read_text())
    assets = {name: config["runtime_assets"][name] for name in ("bundle_manifest", "bundle_parameters")}
    require(plan.get("router_assets") == assets, "router_assets_binding")
    paths = {}
    for name, binding in assets.items():
        paths[name] = B.source_path(binding["path"], project_root)
        require(B.regular_file(paths[name]) == binding["sha256"], "router_asset_hash")
    manifest = LOCAL.strict_json(paths["bundle_manifest"].read_text())
    with np.load(paths["bundle_parameters"], allow_pickle=False) as arrays:
        require(set(arrays.files) == {"scaler_mean", "scaler_var", "scaler_scale", "classes", "coef", "intercept"}, "router_array_keys")
        require(arrays["coef"].shape == (1, 14) and arrays["intercept"].shape == (1,), "router_array_shape")
        values = {name: arrays[name].tolist() for name in ("scaler_mean", "scaler_scale", "classes")}
        values.update(coef=arrays["coef"][0].tolist(), intercept=float(arrays["intercept"][0]))
    router = {**values, "labels": manifest["labels"], "features": manifest["features"],
              "m1_threshold": manifest["thresholds"]["m1"], "m3_threshold": manifest["thresholds"]["m3"],
              "cutoff": manifest["operating_point"]["cutoff"]}
    validate_router(router)
    require(router["m1_threshold"] == router["m3_threshold"] == .31
            and router["cutoff"] == .7796902005928844, "frozen_operating_point")
    require(B.regular_file(ROOT / "topicweb/inference_process.py") == BRIDGE_SHA256, "frozen_bridge_identity")
    completion = project_root / "experiments/stack-overflow-emotion-gold/oof-router/runs/exp-066-headless-runtime-parity/attempt-2/runtime-complete.json"
    require(B.regular_file(completion) == COMPLETION_SHA256, "frozen_completion_identity")
    runtime = config["implementation"]["runtime"]
    require(B.regular_file(B.source_path(runtime["path"], project_root)) == runtime["sha256"], "frozen_runtime_identity")
    router["base_fingerprint"] = sha(LOCAL.canonical({"input_contract": "phase-c-exact-utf8-v1", "bridge": BRIDGE_SHA256,
                                                     "parent_config": MODEL_CONFIG_SHA256, "parent_completion": COMPLETION_SHA256}))
    return router


def check_ready(ready, transfer_info, *, mode):
    require(isinstance(ready, dict), "ready_schema")
    close(ready, {"type": "ready", "fingerprint": transfer_info["fingerprint"],
                  "base_fingerprint": transfer_info["base_fingerprint"],
                  "transfer_sha256": transfer_info["transfer_sha256"], "strategy": STRATEGY,
                  "transfer_items": 340, "cache_entries": 338, "m1_instance_absent": True,
                  "modelstatus": {"m1": "receipt_replay_not_loaded", "m3": "not_loaded", "mode": mode},
                  "cache_scope": "job_m1_receipt_transfer", "audit_rate": 0}, "staged_ready_identity", tolerance=0)
    require(type(ready["transfer_items"]) is int and type(ready["cache_entries"]) is int, "ready_count_types")


def check_final_results(records, final_rows, prelude, replay, *, mode, phase1_complete):
    require(len(final_rows) == len(records) and [row.get("ordinal") for row in final_rows] == list(range(len(records))), "final_row_alignment")
    observed = [row for row in final_rows if row.get("result") is not None]
    require([row["ordinal"] for row in observed] == list(range(len(observed))), "final_result_prefix")
    selected = prelude if mode == "m1_only" else replay
    require(len(observed) <= len(selected), "final_without_phase_receipt")
    base = prelude[-1]["result"]["cumulative_counters"] if prelude else {name: 0 for name in COSTS}
    if mode != "m1_only" and observed:
        require(phase1_complete and len(prelude) == 340, "final_replay_before_complete_prelude")
    for final, raw, record in zip(observed, selected, records):
        require(final["record"]["model_input_text"] == record["model_input_text"]
                and final["record"]["model_input_hash"] == record["model_input_hash"], "final_input_changed")
        actual, phase_result = final["result"], raw["result"]
        close(actual, {key: value for key, value in phase_result.items() if key not in {"counters", "cumulative_counters", "cache_hit"}},
              "stored_phase_result_identity", tolerance=0)
        if mode == "m1_only":
            require(actual.get("cache_hit") is phase_result.get("cache_hit"), "stored_m1_cache_flag")
            close(actual.get("counters"), phase_result["counters"], "stored_m1_cost", tolerance=0)
            close(actual.get("cumulative_counters"), phase_result["cumulative_counters"], "stored_m1_cumulative", tolerance=0)
            continue
        first = prelude[final["ordinal"]]["result"]
        require(actual.get("cache_hit") is bool(first["counters"]["m1_cache_hit"]
                and (not phase_result["route_requested"] or phase_result["counters"]["m3_cache_hit"])), "stored_physical_cache_flag")
        expected = {name: phase_result["counters"][name] for name in COSTS}
        cumulative = dict(phase_result["cumulative_counters"])
        for name in ("m1_attempts", "m1_cache_hit"):
            expected[name] = first["counters"][name]
            cumulative[name] = base[name]
        close(actual.get("counters"), expected, "stored_physical_row_cost", tolerance=0)
        close(actual.get("cumulative_counters"), cumulative, "stored_physical_job_cumulative", tolerance=0)
        close(actual.get("staged_raw_counters"), {name: phase_result["counters"][name] for name in COSTS}, "stored_raw_phase_cost", tolerance=0)
        require(actual.get("staged_counter_scope") == "physical_job_cumulative"
                and actual.get("staged_latency_scope") == "phase_response_only_m1_prepass_excluded", "stored_staged_scope")
        require(all(type(actual[field].get(name)) is int for field in ("counters", "cumulative_counters") for name in COSTS), "stored_counter_types")
    return {"final_acknowledged_items": len(observed), "missing_final_items": len(records) - len(observed)}


def receipt_safety(rows, events, service, run):
    """A model result receipt must name its real phase process, not another phase."""
    ready = [event for event in events if event["type"] == "ready"]
    exits = [event for event in events if event["type"] == "process_exit"]
    violations = 0
    previous = None
    for row in rows:
        result = row["result"]
        child_rss, parent_rss = B.result_rss(result.get("telemetry"))
        telemetry = result["telemetry"]
        timestamp = telemetry.get("monotonic")
        require(len(ready) == 1 and telemetry["child_pid"] == ready[0]["pid"]
                and telemetry["parent_pid"] == service["pid"] and finite(timestamp)
                and ready[0]["monotonic"] <= timestamp <= (exits[-1]["monotonic"] if exits else run["ended_monotonic"])
                and (previous is None or timestamp >= previous), "receipt_phase_process_identity")
        previous = timestamp
        resources = result.get("resources")
        require(isinstance(resources, dict) and all(type(resources.get(name)) is int and resources[name] >= 0
                for name in ("peak_rss_bytes", "mlx_peak_bytes")), "receipt_resource_schema")
        violations += bool(child_rss > 12 * 1024**3 or parent_rss > 1024**3
                           or resources["peak_rss_bytes"] > 12 * 1024**3 or resources["mlx_peak_bytes"] > 10_000_000_000)
    return violations


def runtime_progress(events, phase, rows, source_results, budget):
    """Use acknowledged progress as an additional lower bound, not a receipt."""
    totals = {name: 0 for name in COSTS}
    if rows:
        totals.update(rows[-1]["result"]["cumulative_counters"])
    markers = [row for row in events if row.get("type") == "staged_progress" and row.get("phase_id") == phase["id"]]
    selected = [i for i, result in enumerate(source_results) if result["hypothetical_route"]][:budget]
    open_stage, closed, violations, previous = None, Counter(), 0, -1
    attempted = succeeded = 0
    for marker in markers:
        ordinal, stage, kind = marker.get("ordinal"), marker.get("stage"), marker.get("kind")
        require(phase["phase"] == "m3" and type(ordinal) is int and ordinal in selected
                and stage in {"m3_load", "m3_forward"} and kind in {"begin", "end"}, "runtime_stage_contract")
        index = selected.index(ordinal)
        if stage == "m3_load":
            require(index == 0 and not closed["m3_load"] and previous <= ordinal, "m3_load_progress_order")
        if kind == "begin":
            require(open_stage is None and ordinal >= previous, "runtime_stage_overlap")
            if stage == "m3_forward":
                require(closed["m3_load"] == 1 and closed["m3_forward"] == index, "m3_forward_progress_order")
            open_stage = (stage, ordinal)
        else:
            require(open_stage == (stage, ordinal), "runtime_stage_end_without_begin")
            closed[stage] += 1
            open_stage = None
        previous = ordinal
        values = marker.get("cumulative_counters")
        require(isinstance(values, dict) and all(type(values.get(name)) is int and values[name] >= 0 for name in COSTS), "progress_counter_types")
        expected = {name: 0 for name in COSTS}
        expected.update(m1_cache_hit=ordinal + 1, m3_attempts=index + 1, m3_succeeded=index)
        close(values, expected, "progress_cost_identity", tolerance=0)
        attempted, succeeded = max(attempted, index + 1), max(succeeded, index)
        for name in COSTS:
            totals[name] = max(totals[name], values[name])
        resource = marker.get("resources")
        require(isinstance(resource, dict) and all(type(resource.get(name)) is int and resource[name] >= 0
                for name in ("peak_rss_bytes", "mlx_peak_bytes")), "progress_resource_schema")
        violations += bool(resource["peak_rss_bytes"] > 12 * 1024**3 or resource["mlx_peak_bytes"] > 10_000_000_000)
    failures = [row for row in events if row.get("type") == "failure_cost" and row.get("phase_id") == phase["id"]]
    for failure in failures:
        values = failure.get("cumulative_counters")
        require(isinstance(values, dict) and all(type(values.get(name)) is int and values[name] >= 0 for name in COSTS)
                and isinstance(failure.get("error_code"), str) and re.fullmatch(r"[a-z0-9_]{1,64}", failure["error_code"]), "failure_cost_schema")
        require(all(values[name] >= totals[name] for name in COSTS), "failure_cost_regression")
        require(values["m3_succeeded"] <= values["m3_attempts"] <= budget
                and values["m3_cache_hit"] == values["audit_extra_calls"] == 0, "failure_cost_budget")
        if phase["phase"] == "m1":
            require(values["m3_attempts"] == values["m3_succeeded"] == 0
                    and len(rows) <= values["m1_attempts"] + values["m1_cache_hit"] <= min(340, len(rows) + 1), "failure_m1_prefix_cost")
        else:
            require(values["m1_attempts"] == 0 and len(rows) <= values["m1_cache_hit"] <= min(340, len(rows) + 1), "failure_transfer_prefix_cost")
        totals = {name: values[name] for name in COSTS}
    if phase["status"] == "completed" and phase["phase"] == "m3":
        require(open_stage is None and closed["m3_load"] == 1
                and closed["m3_forward"] == len(selected), "complete_progress_coverage")
    return {"acknowledged_progress_events": len(markers), "acknowledged_failure_counter_events": len(failures),
            "raw_counter_lower_bound": {name: totals[name] for name in COSTS},
            "resource_violations": violations, "unfinished_stage": list(open_stage) if open_stage else None}


def check_dashboard(job, physical, transfer_reuses, *, complete, api_dashboard=None):
    items = job["items"]
    records, results = [row["record"] for row in items], [row.get("result") for row in items]
    progress = (job.get("progress") or {}).get("staged_execution")
    acknowledged = {name: sum(row["result"]["counters"][name] for row in items if row.get("result") is not None) for name in COSTS}
    require(isinstance(progress, dict) or not complete, "staged_progress_missing")
    if isinstance(progress, dict):
        reported_cost = progress.get("cumulative_counters")
        require(isinstance(reported_cost, dict) and all(type(reported_cost.get(name)) is int
                and acknowledged[name] <= reported_cost[name] <= physical[name] for name in COSTS), "staged_lower_bound_range")
        reported_reuse = progress.get("prelude_transfer_reuses")
        require(type(reported_reuse) is int and 0 <= reported_reuse <= transfer_reuses, "staged_reuse_lower_bound")
        close(progress, {"strategy": STRATEGY, "cost_complete": complete,
                         "cost_scope": "completed_job" if complete else "job_cumulative_lower_bound",
                         "unacknowledged_attempts": 0 if complete else None}, "staged_physical_progress", tolerance=0)
    else:
        reported_cost, reported_reuse = acknowledged, 0
    if complete:
        close(reported_cost, physical, "complete_progress_cost", tolerance=0)
        require(reported_reuse == transfer_reuses, "complete_transfer_reuse")
        require(progress.get("stage") == "completed" and progress.get("phase_completed_items") == 340
                and progress.get("phase_total_items") == 340, "complete_staged_progress")
    dashboard = job.get("dashboard")
    # Store retains the aggregate as originally computed; the API overlays current
    # physical accounting. The saved API response is the user-visible artifact.
    expected = B.recalculate_aggregate(records, results, job["mode"], reported_cost)
    if isinstance(dashboard, dict):
        aggregate_only = {key: value for key, value in expected.items() if key != "routing"}
        close(dashboard, aggregate_only, "stored_dashboard_aggregate")
        if "derived" in dashboard:
            B.DERIVED.check_derived(records, results, dashboard["derived"])
    require(isinstance(api_dashboard, dict) or not complete, "api_dashboard_missing")
    if isinstance(api_dashboard, dict):
        close(api_dashboard, expected, "api_dashboard_aggregate")
        scope = "staged_job_cumulative" if complete else "staged_known_lower_bound" if isinstance(progress, dict) else "acknowledged_items_lower_bound"
        close(api_dashboard["routing"], {"cost_scope": scope, "cost_complete": complete}, "api_dashboard_physical_cost_scope", tolerance=0)
        if isinstance(progress, dict):
            require(api_dashboard["routing"].get("prelude_transfer_reuses") == reported_reuse, "api_reuse_scope")
        B.DERIVED.check_derived(records, results, api_dashboard.get("derived"))
    return {"aggregate_verified": isinstance(dashboard, dict) or isinstance(api_dashboard, dict),
            "api_dashboard": "verified" if isinstance(api_dashboard, dict) else "not_observed_partial",
            "derived_verified": isinstance(api_dashboard, dict), "physical_cost_verified": True,
            "journal_counter_lower_bound": physical, "stored_counter_lower_bound": reported_cost,
            "not_published_counter_delta": {name: physical[name] - reported_cost[name] for name in COSTS},
            "cost_scope_note": "Cancellation may reject later progress writes; saved API/Store lower bounds are not relabelled as the latest journal lower bound.",
            "latency_scope": "phase_response_only; logical/phase wall time is reported separately"}


def analyze(plan, run, source, jobs, receipts, transfers, samples, events, runtime_events, service, router, known_m3, dashboards):
    close(plan, {"experiment_id": "EXP-085", "attempt": 2, "tier": "Major", "rq": "RQ-S3", "rounds": 3,
                 "modes": list(MODES), "planned_jobs": 9, "planned_events": 3060, "events_per_job": 340,
                 "max_seconds": 1800, "work_seconds": 1770, "cleanup_seconds": 15,
                 "source_job": SOURCE_JOB, "source_snapshot_sha256": SOURCE_SNAPSHOT,
                 "source_logical_sha256": SOURCE_LOGICAL}, "plan_contract", tolerance=0)
    metadata = B.validate_source_rows(source)
    require(plan.get("source_rows") == metadata and sha(LOCAL.canonical(source)) == SOURCE_LOGICAL, "source_plan_identity")
    records, old_results = [row["record"] for row in source], [row["result"] for row in source]
    close(run, {"experiment_id": "EXP-085", "attempt": 2, "tier": "Major", "planned_jobs": 9,
                "planned_events": 3060}, "run_contract", tolerance=0)
    require(run.get("status") in {"Completed", "Stopped", "Failed"} and finite(run.get("started_monotonic"))
            and finite(run.get("ended_monotonic")) and run["started_monotonic"] <= run["ended_monotonic"], "run_clock")
    close(run.get("elapsed_seconds"), run["ended_monotonic"] - run["started_monotonic"], "run_elapsed")
    require(all(run["started_monotonic"] <= row["started_monotonic"] <= row["monotonic"] <= run["ended_monotonic"] for row in samples)
            and all(run["started_monotonic"] <= row["monotonic"] <= run["ended_monotonic"] for row in events), "observation_clock")
    logical, phases = run.get("logical_jobs"), run.get("phases")
    require(isinstance(logical, list) and len(logical) <= 9 and isinstance(phases, list) and len(phases) <= 15, "run_sequence_shape")
    order = [(round_id, mode) for round_id in range(1, 4) for mode in MODES]
    require([(job.get("round"), job.get("mode")) for job in logical] == order[:len(logical)], "logical_order")
    require(len({job.get("id") for job in logical}) == len(logical) and set(jobs) == {job["id"] for job in logical}, "logical_job_set")
    phase_map = {phase.get("id"): phase for phase in phases}
    require(len(phase_map) == len(phases), "duplicate_phase")
    expected_phase_ids = [job["id"] + suffix for job in logical for suffix in ((":m1",) if job["mode"] == "m1_only" else (":m1", ":m3"))]
    require([phase["id"] for phase in phases] == expected_phase_ids[:len(phases)], "phase_sequence")
    for phase in phases:
        terminals = [row for row in runtime_events if row.get("type") == "phase_terminal" and row.get("phase_id") == phase["id"]]
        require(len(terminals) == 1, "phase_terminal_count")
        for field in ("id", "phase", "mode", "status", "total_items", "completed_items", "started_monotonic", "ended_monotonic",
                      "readiness_started_monotonic", "readiness_ended_monotonic", "readiness_indices", "normal_exit"):
            close(phase.get(field), terminals[0].get(field), "phase_terminal_binding", tolerance=0)
        require(phase["phase"] in {"m1", "m3"} and phase["status"] in {"completed", "failed", "cancelled"}
                and phase.get("total_items") == 340 and finite(phase.get("ended_monotonic"))
                and phase["started_monotonic"] <= phase["ended_monotonic"] <= run["ended_monotonic"], "phase_contract")
        for field in ("exit_observation", "cleanup", "cost_complete"):
            require(phase.get(field) == terminals[0].get(field), "phase_terminal_exit_binding")
    for event in events:
        require(event.get("phase_id") == event.get("job_id") and event.get("phase_id") in phase_map
                and event.get("logical_job_id") + ":" + phase_map[event["phase_id"]]["phase"] == event["phase_id"], "process_event_phase_binding")
    safety = B.verify_safety(samples, events, service, phases, elapsed_seconds=run["elapsed_seconds"], limit_seconds=1800)
    receipt_map = {key: [] for key in phase_map}
    last_phase = -1
    for row in receipts:
        phase_id = row.get("phase_id")
        require(phase_id in phase_map and row.get("logical_job_id") + ":" + phase_map[phase_id]["phase"] == phase_id, "receipt_phase_binding")
        index = [phase["id"] for phase in phases].index(phase_id)
        require(index >= last_phase, "receipt_phase_order")
        last_phase = index
        receipt_map[phase_id].append(row)
    transfer_map = {}
    for envelope in transfers:
        phase_id = envelope.get("phase_id")
        require(phase_id not in transfer_map and phase_id in expected_phase_ids and phase_id.endswith(":m3"), "transfer_phase_set")
        transfer_map[phase_id] = envelope
    summaries, m3_baseline, final_count, phase_count, receipt_violations = [], {}, 0, 0, 0
    total_accounting = {name: 0 for name in ("actual_m1_forward_attempts", "within_phase_duplicate_cache_hits", "prelude_transfer_reuse",
                                          "m3_attempts", "m3_succeeded", "m3_cache_hits", "audit_extra_calls")}
    progress_violations = 0
    for index, logical_job in enumerate(logical):
        identifier, mode = logical_job["id"], logical_job["mode"]
        job = jobs[identifier]
        require(logical_job.get("budget") == BUDGETS[mode] and job.get("mode") == mode
                and job.get("state") == logical_job.get("status")
                and job["state"] in {"completed", "completed_with_fallback", "failed", "cancelled"}, "logical_terminal")
        request = job.get("request", {})
        require(request.get("mode") == mode and request.get("max_qwen_calls") == BUDGETS[mode]
                and request.get("audit_rate") == 0 and job.get("total_items") == 340, "logical_request")
        items = job["items"]
        require(LOCAL.check_records([row["record"] for row in items]) == job.get("snapshot_hash") == logical_job.get("snapshot_hash"), "job_snapshot")
        require(all(row["record"]["model_input_text"] == record["model_input_text"]
                    and row["record"]["model_input_hash"] == record["model_input_hash"] for row, record in zip(items, records)), "job_original_text_identity")
        m1_id, m3_id = identifier + ":m1", identifier + ":m3"
        ids = [phase_id for phase_id in (m1_id, m3_id) if phase_id in phase_map]
        require(logical_job.get("phase_ids") == ids, "logical_phase_mapping")
        prelude, replay = receipt_map.get(m1_id, []), receipt_map.get(m3_id, [])
        phase_summaries = []
        physical = {name: 0 for name in COSTS}
        transfer_reuses = 0
        transfer_info = None
        if m3_id in transfer_map:
            require(m1_id in phase_map and phase_map[m1_id]["status"] == "completed", "transfer_before_completed_m1")
            m1_index = [phase["id"] for phase in phases].index(m1_id)
            require(safety["exits"][m1_index]["normal_exit"] and safety["exits"][m1_index]["absence_observed"], "transfer_before_m1_absence")
            transfer_info = check_transfer(transfer_map[m3_id], prelude, logical_job_id=identifier, phase_id=m3_id, m1_phase_id=m1_id)
            require(transfer_info["base_fingerprint"] == router["base_fingerprint"], "transfer_frozen_base_fingerprint")
        for phase_id in ids:
            phase = phase_map[phase_id]
            stage, rows = phase["phase"], receipt_map[phase_id]
            require(phase_id == identifier + ":" + stage and phase["mode"] == ("m1_only" if stage == "m1" else mode)
                    and phase.get("completed_items") == len(rows), "phase_result_count")
            complete = phase["status"] == "completed"
            if complete:
                require(len(rows) == 340 and phase.get("normal_exit") is True, "partial_phase_completion")
            own_events = [event for event in events if event["phase_id"] == phase_id]
            if stage == "m3":
                require(transfer_info is not None, "m3_without_transfer")
                ready_events = [event for event in own_events if event["type"] == "ready"]
                require(not rows or len(ready_events) == 1, "replay_without_ready")
                if ready_events:
                    check_ready(ready_events[0].get("ready"), transfer_info, mode=mode)
                require(all(row["result"].get("fingerprint") == transfer_info["fingerprint"] for row in rows), "replay_fingerprint")
            else:
                require(all(row["result"]["resources"]["mlx_peak_bytes"] == 0 for row in rows), "m1_mlx_activity")
                ready_events = [event for event in own_events if event["type"] == "ready"]
                if rows:
                    require(len(ready_events) == 1, "m1_without_ready")
                if ready_events:
                    close(ready_events[0].get("ready"), {"type": "ready", "fingerprint": router["base_fingerprint"],
                          "modelstatus": {"m1": "loaded", "m3": "not_loaded", "mode": "m1_only"},
                          "cache_scope": "job_exact_input_components", "audit_rate": 0}, "m1_ready_base_identity", tolerance=0)
                require(all(row["result"].get("fingerprint") == router["base_fingerprint"] for row in rows), "m1_base_fingerprint")
            costs = recompute_cost(records, rows, mode="m1_only" if stage == "m1" else mode,
                                   budget=0 if stage == "m1" else BUDGETS[mode], phase=stage, complete=complete)
            functional = functional_comparison(records, rows, router, mode="m1_only" if stage == "m1" else mode,
                                               budget=0 if stage == "m1" else BUDGETS[mode], phase=stage,
                                               source_results=old_results, prelude=prelude, known_m3=known_m3)
            repetitions = compare_m3_repetitions(rows, m3_baseline)
            receipt_violations += receipt_safety(rows, own_events, service, run)
            observed_progress = runtime_progress(runtime_events, phase, rows, old_results, BUDGETS[mode])
            for name in COSTS:
                if (stage == "m1") == (name in {"m1_attempts", "m1_cache_hit"}):
                    physical[name] = observed_progress["raw_counter_lower_bound"][name]
            if stage == "m3":
                transfer_reuses = observed_progress["raw_counter_lower_bound"]["m1_cache_hit"]
            progress_violations += observed_progress["resource_violations"]
            for name, value in costs["accounting"].items():
                total_accounting[name] += value
            phase_count += len(rows)
            phase_summaries.append({"id": phase_id, "phase": stage, "completed": complete, "cost": costs,
                                    "functional": functional, "repetitions": repetitions, "progress": observed_progress})
        final = check_final_results(records, items, prelude, replay, mode=mode,
                                    phase1_complete=m1_id in phase_map and phase_map[m1_id]["status"] == "completed")
        final_count += final["final_acknowledged_items"]
        require(job.get("completed_items") == logical_job.get("completed_items") == final["final_acknowledged_items"], "final_completed_count")
        completed = job["state"] in {"completed", "completed_with_fallback"}
        if completed:
            require(len(ids) == (1 if mode == "m1_only" else 2) and all(row["completed"] for row in phase_summaries)
                    and final["final_acknowledged_items"] == 340, "false_logical_completion")
            require(job["state"] == ("completed_with_fallback" if mode == "demo" else "completed"), "logical_fallback_state")
        if index + 1 < len(logical):
            require(completed, "logical_job_after_failure")
        cost_complete = len(ids) == (1 if mode == "m1_only" else 2) and all(row["completed"] for row in phase_summaries)
        dashboard_check = check_dashboard(job, physical, transfer_reuses, complete=cost_complete, api_dashboard=dashboards.get(identifier))
        summaries.append({"id": identifier, "round": logical_job["round"], "mode": mode, "completed": completed,
                          **final, "phases": phase_summaries, "physical_counter_lower_bound": physical,
                          "progress_transfer_reuses": transfer_reuses, "dashboard": dashboard_check})
    require(sum(len(rows) for rows in receipt_map.values()) == len(receipts), "unbound_receipts")
    safety.update(receipt_resource_gate=receipt_violations == 0, progress_resource_gate=progress_violations == 0)
    cleanup = run.get("cleanup")
    safety["http_cleanup_gate"] = cleanup is None or (finite(cleanup.get("started_monotonic")) and finite(cleanup.get("ended_monotonic"))
            and 0 <= cleanup["ended_monotonic"] - cleanup["started_monotonic"] <= 15 + 1e-6
            and cleanup.get("max_seconds") == 15 and cleanup.get("terminal_confirmed") is True)
    work_end = run["started_monotonic"] + 1770
    safety["work_budget_gate"] = all(row["result"]["telemetry"]["monotonic"] <= work_end for row in receipts)
    safety["gate_passed"] = safety["gate_passed"] and all(safety[key] for key in ("receipt_resource_gate", "progress_resource_gate", "work_budget_gate", "http_cleanup_gate"))
    all_complete = len(summaries) == 9 and all(row["completed"] for row in summaries)
    if all_complete:
        require(final_count == 3060 and phase_count == 5100 and len(phases) == 15 and len(transfers) == 6, "complete_event_totals")
        close(total_accounting, {"actual_m1_forward_attempts": 3042, "within_phase_duplicate_cache_hits": 18,
                                 "prelude_transfer_reuse": 2040, "m3_attempts": 135, "m3_succeeded": 135,
                                 "m3_cache_hits": 0, "audit_extra_calls": 0}, "complete_cost_totals", tolerance=0)
    if run["status"] == "Completed":
        require(all_complete and run.get("failure_code") is None, "false_run_completion")
    else:
        require(isinstance(run.get("failure_code"), str) and bool(run["failure_code"]), "stopped_without_reason")
    if run.get("failure_code") == "critical_memory_pressure":
        require(safety["system"]["critical_samples"] > 0, "critical_without_sample")
    if run.get("failure_code") == "swap_thrashing":
        require(safety["system"]["thrashing"], "thrashing_without_sample")
    complete = all_complete and run["status"] == "Completed" and safety["gate_passed"]
    return {"logical_jobs": summaries, "completed_jobs": sum(row["completed"] for row in summaries),
            "verified_final_items": final_count, "verified_phase_receipts": phase_count,
            "receipt_accounting_lower_bound": total_accounting, "cost_complete": all_complete,
            "observed_physical_counter_lower_bound": {name: sum(row["physical_counter_lower_bound"][name] for row in summaries) for name in COSTS},
            "observed_transfer_reuses_lower_bound": sum(row["progress_transfer_reuses"] for row in summaries),
            "unacknowledged_attempts": 0 if all_complete else None, "safety": safety,
            "exp085_complete": bool(complete), "operational_state": "safe-to-continue" if complete else "stop-required",
            "m3_historical_reference_ordinals": [6], "observed_unique_m3_inputs": len(m3_baseline),
            "claim_boundary": "Finite three-round website acceptance only; historical M3 parity covers ordinal 6, other M3 checks are frozen mathematics and within-run consistency. Not gold accuracy, causal repair, SLA or automatic EXP-080 execution."}


DEPENDENCIES = {
    "requirements.txt", "requirements-lock.txt", "start.py", "topicweb/__init__.py", "topicweb/app.py", "topicweb/core.py",
    "topicweb/adapters.py", "topicweb/store.py", "topicweb/worker.py", "topicweb/inference_process.py", "topicweb/telemetry.py",
    "static/index.html", "static/app.js", "static/app.css", "topicweb/staged_inference.py", "topicweb/staged_safety.py",
    "topicweb/staged_worker.py", "topicweb/staged_app.py", "tests/test_staged_inference.py", "tests/test_staged_safety.py",
    "tests/test_staged_worker.py", "tests/test_staged_app.py", "tests/test_staged_integration.py", "scripts/run_soak.py", "scripts/bounded_runtime_support.py",
    "scripts/verify_bounded_runtime.py", "scripts/verify_local.py", "scripts/verify_discourse_validation.py",
    "scripts/run_staged_runtime.py", "scripts/verify_staged_runtime.py", "tests/test_staged_runtime.py", "tests/test_verify_staged_runtime.py",
}
JOURNALS = {"sample": "samples.jsonl", "process_event": "process-events.jsonl", "phase_receipt": "phase-receipts.jsonl",
            "transfer": "transfers.jsonl", "runtime_event": "runtime-events.jsonl"}


def jsonl(path):
    raw = path.read_bytes()
    require(not raw or raw.endswith(b"\n"), "incomplete_jsonl_tail")
    return [LOCAL.strict_json(line) for line in raw.splitlines()]


def read_source(database):
    require(database.is_file() and not any(path.is_symlink() for path in (database, *database.parents)), "source_database_identity")
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1) as connection:
        metadata = connection.execute("SELECT state,snapshot_hash,total_items FROM jobs WHERE id=?", (SOURCE_JOB,)).fetchone()
        require(metadata == ("completed", SOURCE_SNAPSHOT, 340), "original_source_job")
        return [{"ordinal": i, "record": LOCAL.strict_json(record), "result": LOCAL.strict_json(result)} for i, record, result in
                connection.execute("SELECT ordinal,record,result FROM items WHERE job_id=? ORDER BY ordinal", (SOURCE_JOB,))]


def check_bindings(plan, run, claim, service):
    close(claim, {"experiment_id": "EXP-085", "attempt": 2, "tier": "Major", "rq": "RQ-S3", "cwd": str(ROOT),
                  "training": False, "gold_accessed": False, "source_network_fetched": False}, "claim_contract", tolerance=0)
    require(all(run.get(key) == claim.get(key) for key in ("started_at", "started_monotonic", "plan_sha256")), "claim_run_binding")
    require(isinstance(claim.get("environment"), dict) and isinstance(claim.get("command"), list)
            and isinstance(claim.get("git_commit"), str) and isinstance(claim.get("git_status_porcelain"), list), "claim_environment")
    require(run.get("plan_sha256") == B.regular_file(RUN / "plan.json"), "plan_file_binding")
    require(set(plan.get("sources", {})) == DEPENDENCIES, "dependency_set")
    for name, expected in plan["sources"].items():
        require(B.regular_file(B.source_path(name, ROOT)) == expected, "implementation_identity")
    require(plan.get("protocol", {}).get("path") == PROTOCOL
            and B.regular_file(B.source_path(PROTOCOL, ROOT.parent)) == plan["protocol"].get("sha256"), "protocol_binding")
    close(plan, {"budgets": BUDGETS, "audit_rate": 0, "seed": 42, "port": 8789}, "frozen_execution_contract", tolerance=0)
    require(plan.get("runtime_environment") == claim.get("runtime_environment") == {"TOPICWEB_TELEMETRY": "1"}, "telemetry_environment_binding")
    close(service, {"experiment_id": "EXP-085", "attempt": 2, "root": str(ROOT), "bench_root": str(RUN / "bench"), "port": 8789}, "service_scope", tolerance=0)
    require(B.service_absent(service), "acceptance_supervisor_still_running")
    shutdown = run.get("shutdown")
    require(isinstance(shutdown, dict) and all(shutdown.get(name) is True for name in
            ("server_stopped", "dispatcher_stopped", "monitor_stopped", "dispatcher_lock_released", "current_process_absent", "fresh_absence_confirmed")), "shutdown_unconfirmed")
    require(run.get("total_budget_exceeded") is (run["elapsed_seconds"] > 1800), "total_budget_flag")
    for flag in ("training", "gold_accessed", "source_network_fetched"):
        require(run.get(flag) is False, "access_attestation")
    previous_attempt = check_previous_attempt(plan)
    previous = {}
    for name, expected in PARENT_HASHES.items():
        relative = f"private/validation/exp-084/attempt-1/{name}.json"
        require(plan.get("parent_bindings", {}).get(name) == {"path": relative, "sha256": expected}
                and B.regular_file(ROOT / relative) == expected, "parent_binding")
        previous[name] = LOCAL.strict_json((ROOT / relative).read_text())
    archive = plan.get("parent_archive")
    require(archive == {"path": "private/validation/exp-084/attempt-1/frozen-code.tar.gz", "sha256": ARCHIVE_SHA256, "members": 40}, "parent_archive_binding")
    archive_info = check_parent_archive(ROOT / archive["path"], ARCHIVE_SHA256, previous["plan"], previous["run"], previous["verification"])
    for name, expected in previous["verification"]["source_hashes"].items():
        require(name.startswith("private/validation/exp-084/attempt-1/") and B.regular_file(B.source_path(name, ROOT)) == expected, "parent_artifact_drift")
    references = previous["plan"]["reference_bindings"]
    require(plan.get("reference_bindings") == references, "historical_reference_binding")
    for binding in references.values():
        require(binding["path"].startswith("private/validation/exp-082/attempt-1/")
                and B.regular_file(B.source_path(binding["path"], ROOT)) == binding["sha256"], "historical_reference_hash")
    old = jsonl(ROOT / references["results"]["path"])
    replay = plan.get("parent_replay_results")
    name = "private/validation/exp-084/attempt-1/replay-results.jsonl"
    require(replay == {"path": name, "sha256": previous["verification"]["source_hashes"][name]}, "parent_replay_binding")
    latest = jsonl(ROOT / name)
    require(len(old) == len(latest) == 7 and [row.get("ordinal") for row in old] == [row.get("ordinal") for row in latest] == list(range(7)), "historical_prefix")
    close(old[6]["result"]["m3_probabilities"], latest[6]["result"]["m3_probabilities"], "historical_m3_pair", tolerance=1e-6)
    require(old[6]["input_sha256"] == latest[6]["input_sha256"] and old[6]["result"]["m3_prediction"] == latest[6]["result"]["m3_prediction"], "historical_m3_identity")
    env = claim["environment"]
    lock = env.get("requirements_lock", {})
    packages = dict(line.split("==", 1) for line in (ROOT / "requirements-lock.txt").read_text().splitlines() if line.strip() and not line.startswith("#"))
    require(lock.get("path") == "requirements-lock.txt" and lock.get("sha256") == plan["sources"]["requirements-lock.txt"]
            and lock.get("packages") == packages and env.get("website", {}).get("packages") == packages, "environment_lock")
    config = LOCAL.strict_json((ROOT.parent / MODEL_CONFIG).read_text())
    require(env.get("model_config") == plan["model_config"] and env.get("model_runtime") == config["environment"], "model_environment")
    return {6: latest[6]["result"]}, archive_info, previous_attempt


def main():
    target = RUN / "verification.json"
    require(not target.exists() and not any(path.is_symlink() for path in (target, *target.parents)), "verification_exists_or_symlink")
    report = {"experiment_id": "EXP-085", "attempt": 2, "tier": "Major", "status": "Failed", "exp085_complete": False,
              "operational_state": "stop-required", "models_loaded": False, "gold_accessed": False,
              "producer_numerical_helpers_imported": False, "verified_at": datetime.now(timezone.utc).isoformat(),
              "verifier_sha256": B.regular_file(Path(__file__))}
    try:
        plan, run, claim, service = (LOCAL.strict_json((RUN / name).read_text()) for name in ("plan.json", "run.json", "run-claim.json", "service.json"))
        before = dict(run.get("source_hashes", {}))
        fixed = {str((RUN / name).relative_to(ROOT)) for name in (*JOURNALS.values(), "stdout.log", "service.json", "plan.json", "run-claim.json")}
        database_name = str((RUN / "bench/jobs.sqlite3").relative_to(ROOT))
        require(run.get("bench_database") == database_name, "bench_database_binding")
        fixed.add(database_name)
        dashboards = {}
        for entry in run["logical_jobs"]:
            require(isinstance(entry.get("id"), str) and re.fullmatch(r"[a-f0-9]{32}", entry["id"]), "submission_identity_unconfirmed")
            for field, directory in (("results_path", "results"), ("dashboard_path", "dashboards")):
                if entry.get(field) is None:
                    require(field == "dashboard_path" and entry["status"] not in {"completed", "completed_with_fallback"}, "completed_artifact_missing")
                    continue
                expected = str((RUN / directory / (entry["id"] + ".json")).relative_to(ROOT))
                require(entry[field] == expected, "job_artifact_path")
                fixed.add(expected)
        require(set(before) == fixed, "artifact_set")
        for name, expected in before.items():
            path = B.source_path(name, ROOT)
            require(path.is_relative_to(RUN) and B.regular_file(path) == expected and path.stat().st_mode & 0o777 == 0o600, "artifact_identity_or_mode")
        run_hash = B.regular_file(RUN / "run.json")
        reference, archive_info, previous_attempt = check_bindings(plan, run, claim, service)
        router = load_router(plan)
        source = read_source(ROOT / "private/jobs.sqlite3")
        original_hash = sha(LOCAL.canonical(source))
        payload = "".join(LOCAL.canonical({"id": f"source-{row['ordinal']}", "text": row["record"]["model_input_text"]}) + "\n" for row in source)
        require(sha(payload) == plan.get("payload_sha256") and len(payload.encode()) == plan.get("payload_bytes"), "upload_payload_identity")
        database = ROOT / database_name
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            identifiers = {row[0] for row in connection.execute("SELECT id FROM jobs")}
        require(identifiers == {entry["id"] for entry in run["logical_jobs"]}, "unbound_bench_job")
        jobs = LOCAL.read_jobs(database, identifiers)
        for entry in run["logical_jobs"]:
            artifact = LOCAL.strict_json((ROOT / entry["results_path"]).read_text())
            job = jobs[entry["id"]]
            expected = {"id": entry["id"], "snapshot_hash": job["snapshot_hash"], "items": [
                {"ordinal": row["ordinal"], "input_sha256": row["record"]["model_input_hash"], "result": row["result"]} for row in job["items"]]}
            require(artifact == expected, "database_result_artifact")
            if entry.get("dashboard_path"):
                dashboards[entry["id"]] = LOCAL.strict_json((ROOT / entry["dashboard_path"]).read_text())
        journals = {kind: jsonl(RUN / name) for kind, name in JOURNALS.items()}
        require(run.get("journal_counts") == {kind: len(value) for kind, value in journals.items()}, "journal_count_binding")
        report.update(analyze(plan, run, source, jobs, journals["phase_receipt"], journals["transfer"], journals["sample"],
                              journals["process_event"], journals["runtime_event"], service, router, reference, dashboards))
        require(sha(LOCAL.canonical(read_source(ROOT / "private/jobs.sqlite3"))) == original_hash, "source_changed_during_audit")
        require(B.regular_file(RUN / "run.json") == run_hash and all(B.regular_file(ROOT / name) == expected for name, expected in before.items()), "artifacts_changed_during_audit")
        require(all(B.regular_file(ROOT / name) == expected for name, expected in plan["sources"].items()), "implementation_changed_during_audit")
        report.update(status="Passed", parent_archive=archive_info, previous_attempt=previous_attempt,
                      source_hashes={**before, str((RUN / "run.json").relative_to(ROOT)): run_hash}, source_logical_sha256=original_hash)
    except Exception as error:
        code = str(error) if isinstance(error, (B.VerificationError, LOCAL.VerificationError)) else type(error).__name__
        report.update(status="Failed", exp085_complete=False, operational_state="stop-required",
                      error_code=code if re.fullmatch(r"[A-Za-z0-9_]{1,100}", code) else "verification_failed")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")
        output.flush()
        os.fsync(output.fileno())
    print(json.dumps({name: report.get(name) for name in ("status", "exp085_complete", "operational_state", "error_code")}))
    return 0 if report["status"] == "Passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
