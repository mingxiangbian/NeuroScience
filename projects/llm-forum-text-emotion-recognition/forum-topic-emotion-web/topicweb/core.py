"""Pure data contracts and descriptive aggregates; no model or database access."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import unicodedata
from urllib.parse import urlsplit

LABELS = ("love", "joy", "surprise", "anger", "sadness", "fear")
MAX_ITEMS = 500
MAX_TEXT_BYTES = 64 * 1024
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
DERIVED_SCHEMA = "topicweb-derived-v1"


class ValidationError(ValueError):
    pass


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_timestamp(value):
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            stamp = datetime.fromtimestamp(value, timezone.utc)
        elif isinstance(value, str):
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                raise ValueError("timezone_required")
        else:
            raise ValueError("invalid_timestamp")
        return stamp.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except (ValueError, OverflowError, OSError) as exc:
        raise ValidationError("invalid_utc_timestamp") from exc


def make_record(*, source, site, object_type, source_object_id, model_input_text,
                source_payload_raw=None, source_url=None, created_at=None, updated_at=None,
                parent_object_id=None, thread_id=None, author_display_name=None,
                author_id_hash=None, content_license=None, provenance=None):
    if not isinstance(model_input_text, str) or not model_input_text.strip():
        raise ValidationError("empty_text")
    if len(model_input_text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ValidationError("text_too_large")
    identity = [str(part) for part in (source, site, object_type, source_object_id)]
    if any(not part or part == "None" for part in identity):
        raise ValidationError("missing_source_identity")
    if source_url:
        parsed = urlsplit(str(source_url))
        if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValidationError("invalid_source_url")
    normalized = " ".join(unicodedata.normalize("NFKC", model_input_text).casefold().split())
    return {
        "record_id": sha256(json.dumps(identity, ensure_ascii=False, separators=(",", ":"))),
        "source": str(source), "site": str(site), "object_type": str(object_type),
        "source_object_id": str(source_object_id), "source_url": source_url,
        "created_at": utc_timestamp(created_at), "updated_at": utc_timestamp(updated_at),
        "parent_object_id": None if parent_object_id is None else str(parent_object_id),
        "thread_id": None if thread_id is None else str(thread_id),
        "author_display_name": author_display_name, "author_id_hash": author_id_hash,
        "content_license": content_license, "provenance": provenance or {},
        "source_payload_raw": source_payload_raw, "model_input_text": model_input_text,
        "model_input_hash": sha256(model_input_text), "dedup_hash": sha256(normalized),
        "display_text": model_input_text[:280],
    }


def _bounded_int(value, minimum, maximum, name):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValidationError(name)
    return value


def validate_request(payload):
    if not isinstance(payload, dict):
        raise ValidationError("object_required")
    source = payload.get("source", "upload")
    mode = payload.get("mode", "m1_only")
    if source not in {"upload", "stackexchange", "discourse"}:
        raise ValidationError("invalid_source")
    if mode not in {"m1_only", "research", "demo"}:
        raise ValidationError("invalid_mode")
    name = payload.get("name", "未命名话题")
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise ValidationError("invalid_name")
    if payload.get("audit_rate", 0) != 0:
        raise ValidationError("audit_not_enabled")
    result = {"name": name.strip(), "source": source, "mode": mode,
              "max_qwen_calls": _bounded_int(payload.get("max_qwen_calls", 20), 0, 500, "invalid_qwen_budget"),
              "audit_rate": 0, "seed": 42}
    if mode != "demo":
        result["max_qwen_calls"] = MAX_ITEMS if mode == "research" else 0
    if source == "upload":
        upload = payload.get("upload")
        if not isinstance(upload, dict) or not isinstance(upload.get("content"), str):
            raise ValidationError("upload_content_required")
        if len(upload["content"].encode("utf-8")) > MAX_UPLOAD_BYTES:
            raise ValidationError("upload_too_large")
        if upload.get("format") not in {"csv", "json", "jsonl"}:
            raise ValidationError("invalid_upload_format")
        column = upload.get("text_column", "text")
        filename = upload.get("filename", "upload")
        if not isinstance(column, str) or not column or len(column) > 100:
            raise ValidationError("invalid_text_column")
        if not isinstance(filename, str) or len(filename) > 255:
            raise ValidationError("invalid_filename")
        result["upload"] = {"content": upload["content"], "format": upload["format"],
                            "text_column": column, "filename": filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]}
    elif source == "stackexchange":
        query = payload.get("query", {})
        if not isinstance(query, dict) or query.get("site", "stackoverflow") != "stackoverflow":
            raise ValidationError("site_not_allowed")
        start, end = utc_timestamp(query.get("from_utc")), utc_timestamp(query.get("to_utc"))
        if not start or not end:
            raise ValidationError("window_required")
        span = datetime.fromisoformat(end.replace("Z", "+00:00")) - datetime.fromisoformat(start.replace("Z", "+00:00"))
        if not 0 < span.total_seconds() <= 31 * 86400:
            raise ValidationError("invalid_window_max_31_days")
        tags, search = query.get("tags", ""), query.get("query", "")
        if not isinstance(tags, str) or len(tags) > 200 or not isinstance(search, str) or len(search) > 200:
            raise ValidationError("invalid_topic_query")
        if not tags.strip() and not search.strip():
            raise ValidationError("topic_required")
        result["query"] = {"site": "stackoverflow", "tags": tags.strip(), "query": search.strip(),
                           "from_utc": start, "to_utc": end,
                           "max_questions": _bounded_int(query.get("max_questions", 100), 1, 100, "invalid_question_limit"),
                           "max_items": _bounded_int(query.get("max_items", 500), 1, MAX_ITEMS, "invalid_item_limit")}
        for kind in ("questions", "answers", "comments"):
            selected = query.get("include_" + kind, True)
            if not isinstance(selected, bool):
                raise ValidationError("invalid_object_types")
            result["query"]["include_" + kind] = selected
        if not any(result["query"]["include_" + k] for k in ("questions", "answers", "comments")):
            raise ValidationError("object_type_required")
    else:
        query = payload.get("query")
        if (not isinstance(query, dict) or query.get("site") != "discuss.python.org"
                or type(query.get("category_id")) is not int or query["category_id"] != 7
                or not set(query) <= {"site", "category_id", "max_topics", "max_items"}):
            raise ValidationError("discourse_source_contract")
        result["query"] = {"site": "discuss.python.org", "category_id": 7,
                           "max_topics": _bounded_int(query.get("max_topics", 100), 1, 100, "invalid_topic_limit"),
                           "max_items": _bounded_int(query.get("max_items", 400), 1, MAX_ITEMS, "invalid_item_limit")}
    return result


def _vector(result, key):
    value = result.get(key)
    return value if isinstance(value, list) and len(value) == len(LABELS) else None


def aggregate(records, results, manifest=None, mode="m1_only"):
    """Occurrence-weighted descriptive results. Missing predictions are not neutral."""
    if len(records) != len(results):
        raise ValidationError("aggregate_alignment")
    counts = Counter({label: 0 for label in LABELS})
    paths, fallbacks, cost, types = Counter(), Counter(), Counter(), Counter()
    daily = defaultdict(lambda: {"n": 0, "neutral": 0, "labels": Counter()})
    eligible_types = Counter(r.get("object_type", "unknown") for r in records)
    successful = neutral = requested = 0
    paired = disagree = 0
    entropies, latencies = [], []
    for record, result in zip(records, results):
        if not isinstance(result, dict):
            continue
        prediction = _vector(result, "prediction")
        if prediction is None or any(p not in (0, 1, False, True) for p in prediction):
            raise ValidationError("invalid_prediction_vector")
        successful += 1
        types[record.get("object_type", "unknown")] += 1
        paths[result.get("used_path", "unknown")] += 1
        requested += bool(result.get("route_requested", result.get("route_eligible", False)))
        inactive = not any(prediction)
        neutral += inactive
        for label, active in zip(LABELS, prediction):
            counts[label] += bool(active)
        counters = result.get("counters", result.get("cost", {})) or {}
        for name in ("m1_attempts", "m3_attempts", "m3_succeeded", "m1_cache_hit", "m3_cache_hit", "audit_extra_calls"):
            value = counters.get(name, 0)
            if isinstance(value, (int, bool)):
                cost[name] += value
        fallback = result.get("fallback_reason") or counters.get("fallback_reason")
        if fallback:
            fallbacks[fallback] += 1
        m1, m3 = _vector(result, "m1_probabilities"), _vector(result, "m3_probabilities")
        if m1:
            entropies.append(sum(-(p * math.log(max(p, 1e-12)) + (1-p) * math.log(max(1-p, 1e-12))) for p in m1) / 6)
        # Decisions must be made with the frozen per-model thresholds, not an invented 0.5.
        m1_decision, m3_decision = _vector(result, "m1_prediction"), _vector(result, "m3_prediction")
        if m1_decision is not None and m3_decision is not None:
            paired += 1
            disagree += m1_decision != m3_decision
        latency = result.get("latency_ms")
        if isinstance(latency, (int, float)) and math.isfinite(latency):
            latencies.append(latency)
        if record.get("created_at"):
            day = record["created_at"][:10]
            daily[day]["n"] += 1
            daily[day]["neutral"] += inactive
            daily[day]["labels"].update({k: int(v) for k, v in zip(LABELS, prediction)})
    positives = sum(counts.values())
    return {
        "mode": mode, "labels": list(LABELS), "manifest": manifest or {},
        "summary": {"eligible_items": len(records), "successful_items": successful,
                    "missing_predictions": len(records) - successful,
                    "coverage": successful / len(records) if records else None,
                    "neutral_count": neutral, "neutral_rate": neutral / successful if successful else None,
                    "exact_input_groups": len({r.get("model_input_hash") for r in records}),
                    "normalized_text_groups": len({r.get("dedup_hash") for r in records}),
                    "undated_items": sum(not r.get("created_at") for r in records)},
        "emotions": [{"label": label, "count": counts[label],
                      "prevalence": counts[label] / successful if successful else None,
                      "positive_share": counts[label] / positives if positives else None} for label in LABELS],
        "daily": [{"date": day, "n": stats["n"], "neutral": stats["neutral"],
                   "prevalence": {label: stats["labels"][label] / stats["n"] for label in LABELS}} for day, stats in sorted(daily.items())],
        "object_types": [{"type": kind, "eligible": n, "successful": types[kind]} for kind, n in sorted(eligible_types.items())],
        "routing": {"route_requested": requested, "paths": dict(paths), "cost": dict(cost), "fallbacks": dict(fallbacks),
                    "paired_n": paired, "paired_disagreement": disagree / paired if paired else None,
                    "paired_scope": "Only items with both frozen model decisions; not a full-corpus estimate."},
        "uncertainty": {"m1_mean_binary_entropy_nats": sum(entropies) / len(entropies) if entropies else None, "n": len(entropies)},
        "timing": {"mean_item_ms": sum(latencies) / len(latencies) if latencies else None, "n": len(latencies)},
        "evidence_boundary": "Frozen-model predictions on this sampled snapshot, not gold labels, population sentiment, or external generalization evidence.",
    }


def _weighted_view(indices, predictions, group_ids, unique):
    groups = defaultdict(list)
    for index in indices:
        groups[group_ids[index] if unique else index].append(index)
    counts = [0] * len(LABELS)
    neutral = successful_units = successful_occurrences = mixed = partial = 0
    for members in groups.values():
        valid = [index for index in members if predictions[index] is not None]
        if not valid:
            continue
        successful_units += 1
        successful_occurrences += len(valid)
        partial += len(valid) < len(members)
        mixed += len({tuple(predictions[index]) for index in valid}) > 1
        weight = 1 / len(valid) if unique else 1
        for index in valid:
            values = predictions[index]
            neutral += weight * (not any(values))
            for label_index, value in enumerate(values):
                counts[label_index] += weight * value
    positives = sum(counts)
    return {
        "unit": "normalized_text_group" if unique else "occurrence",
        "summary": {"eligible_units": len(groups), "successful_units": successful_units,
                    "missing_units": len(groups) - successful_units,
                    "coverage": successful_units / len(groups) if groups else None,
                    "eligible_occurrences": len(indices), "successful_occurrences": successful_occurrences,
                    "neutral_count": neutral, "neutral_rate": neutral / successful_units if successful_units else None,
                    "cardinality": positives / successful_units if successful_units else None,
                    "mixed_prediction_groups": mixed, "partially_predicted_groups": partial},
        "emotions": [{"label": label, "count": counts[i],
                      "prevalence": counts[i] / successful_units if successful_units else None,
                      "positive_share": counts[i] / positives if positives else None} for i, label in enumerate(LABELS)],
    }


def _distribution(values):
    ordered = sorted(value for value in values if type(value) in (int, float) and math.isfinite(value))
    def quantile(fraction):
        position = (len(ordered) - 1) * fraction
        low = int(position)
        high = min(low + 1, len(ordered) - 1)
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)
    return {"n": len(ordered), "mean": sum(ordered) / len(ordered) if ordered else None,
            "median": quantile(.5) if ordered else None, "p95": quantile(.95) if ordered else None,
            "min": ordered[0] if ordered else None, "max": ordered[-1] if ordered else None}


def extended_views(records, results):
    """Read-only descriptive views; no model calls, selection, or stored metric mutation."""
    if len(records) != len(results):
        raise ValidationError("aggregate_alignment")
    predictions = []
    for result in results:
        values = _vector(result, "prediction") if isinstance(result, dict) else None
        if isinstance(result, dict) and (values is None or any(value not in (0, 1, False, True) for value in values)):
            raise ValidationError("invalid_prediction_vector")
        predictions.append(values)
    group_ids = [record.get("dedup_hash") or record.get("record_id") or f"missing-group-{i}"
                 for i, record in enumerate(records)]
    buckets = {"daily": defaultdict(list), "weekly": defaultdict(list)}
    for index, record in enumerate(records):
        if not record.get("created_at"):
            continue
        date = datetime.fromisoformat(utc_timestamp(record["created_at"]).replace("Z", "+00:00")).date()
        buckets["daily"][date.isoformat()].append(index)
        buckets["weekly"][(date - timedelta(days=date.weekday())).isoformat()].append(index)
    views = {}
    strata = {"object_type": defaultdict(list), "route_requested": {"true": [], "false": [], "unknown": []}}
    for index, record in enumerate(records):
        strata["object_type"][record.get("object_type") or "unknown"].append(index)
        result = results[index]
        requested = result.get("route_requested") if isinstance(result, dict) else None
        route_group = ("true" if requested else "false") if type(requested) is bool else "unknown"
        strata["route_requested"][route_group].append(index)
    for name, unique in (("object_weighted", False), ("normalized_unique_text", True)):
        view = _weighted_view(list(range(len(records))), predictions, group_ids, unique)
        view["strata"] = {kind: [{"group": group, **_weighted_view(indices, predictions, group_ids, unique)}
                                for group, indices in sorted(partitions.items())]
                          for kind, partitions in strata.items()}
        view["trends"] = {}
        for resolution, groups in buckets.items():
            view["trends"][resolution] = [
                {"date": date, **_weighted_view(indices, predictions, group_ids, unique)}
                for date, indices in sorted(groups.items())
            ]
        views[name] = view
    valid = [result for result, values in zip(results, predictions) if values is not None]
    cardinalities = [sum(values) for values in predictions if values is not None]
    entropies, margins = [], []
    for result in valid:
        probabilities = _vector(result, "m1_probabilities")
        if probabilities and all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in probabilities):
            entropies.append(sum(-(p * math.log(max(p, 1e-12)) + (1-p) * math.log(max(1-p, 1e-12))) for p in probabilities) / len(LABELS))
        margin = result.get("threshold_margin")
        if type(margin) in (int, float) and math.isfinite(margin):
            margins.append(margin)
    tokenlengths = {}
    for model in ("m1", "m3"):
        metadata = [result.get("tokenlengths", {}).get(model) for result in valid if isinstance(result.get("tokenlengths"), dict)]
        metadata = [value for value in metadata if isinstance(value, dict)]
        flags = [value["truncated"] for value in metadata if type(value.get("truncated")) is bool]
        tokenlengths[model] = {"input_tokens": _distribution([value.get("input_tokens") for value in metadata]),
                               "used_tokens": _distribution([value.get("used_tokens") for value in metadata]),
                               "truncation_n": len(flags), "truncated_count": sum(flags),
                               "truncated_rate": sum(flags) / len(flags) if flags else None}
    actual = [result["route_requested"] for result in valid if type(result.get("route_requested")) is bool]
    hypothetical = [result.get("hypothetical_route", result.get("route_eligible")) for result in valid]
    hypothetical = [value for value in hypothetical if type(value) is bool]
    fallback_count = sum(bool(result.get("fallback") or result.get("fallback_reason")) for result in valid)
    return {
        "schema_version": DERIVED_SCHEMA, "available": True,
        "weighting_contract": "Each normalized group has weight one; successful occurrences within that group share it equally. Different predictions are averaged, never OR-combined or selected.",
        "time_contract": "UTC days and Monday-start weeks; grouping is local to each time bucket. Undated objects are excluded; absent buckets are not zero-filled.",
        "strata_contract": "Object type and observed route_requested strata group locally. Unknown includes absent decisions. Routing strata are observational, not randomized comparisons; unique-group totals are not additive across strata.",
        "views": views,
        "diagnostics": {"basis": "acknowledged_object_occurrences", "eligible_items": len(records),
                        "successful_items": len(valid), "coverage": len(valid) / len(records) if records else None,
                        "undated_items": sum(not record.get("created_at") for record in records),
                        "cardinality": {**_distribution(cardinalities), "counts": [cardinalities.count(i) for i in range(7)]},
                        "m1_binary_entropy_nats": _distribution(entropies),
                        "m1_threshold_margin": _distribution(margins), "tokenlengths": tokenlengths,
                        "routing": {"actual_requested": sum(actual), "actual_known_n": len(actual),
                                    "actual_rate": sum(actual) / len(actual) if actual else None,
                                    "hypothetical_requested": sum(hypothetical), "hypothetical_known_n": len(hypothetical),
                                    "hypothetical_rate": sum(hypothetical) / len(hypothetical) if hypothetical else None,
                                    "m3_used": sum(result.get("used_path") == "m3" for result in valid),
                                    "fallback_count": fallback_count, "fallback_rate": fallback_count / len(valid) if valid else None},
                        "cost_note": "Costs and model-call accounting remain object/forward based and never use unique-text weights."},
    }
