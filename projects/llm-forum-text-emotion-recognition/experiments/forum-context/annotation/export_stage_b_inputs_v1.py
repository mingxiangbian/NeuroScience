#!/usr/bin/env python3
"""Export frozen Stage B model inputs without annotations or sampling metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


EXPECTED_VIEW_COUNT = 120
SAMPLE_UID_RE = re.compile(r"^smp_[0-9a-f]{64}$")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def load_stage_b_row(view_path: Path, annotation_order: int) -> dict[str, Any]:
    view = json.loads(view_path.read_text(encoding="utf-8"))

    if view.get("schema_version") != "annotation-view-v1":
        raise ValueError(f"{view_path.name}: unexpected view schema")
    if view.get("protocol_id") != "DATA-FCTX-LABEL-V1":
        raise ValueError(f"{view_path.name}: unexpected protocol")

    expected_contract = {
        "stage_a": "target.body",
        "stage_b": "context+target",
        "stage_a_locked_before_stage_b": True,
        "future_replies_included": False,
        "ancestor_chain_included": False,
    }
    if view.get("display_contract") != expected_contract:
        raise ValueError(f"{view_path.name}: display contract changed")

    ids = view.get("ids")
    context = view.get("context")
    target = view.get("target")
    if not isinstance(ids, dict):
        raise ValueError(f"{view_path.name}: missing ids")
    if not isinstance(context, dict) or set(context) != {
        "discussion_title",
        "direct_parent_body",
        "target_quotes",
    }:
        raise ValueError(f"{view_path.name}: invalid context fields")
    if not isinstance(target, dict) or set(target) != {"body", "full_with_quotes"}:
        raise ValueError(f"{view_path.name}: invalid target fields")

    sample_uid = ids.get("sample_uid")
    if not isinstance(sample_uid, str) or not SAMPLE_UID_RE.fullmatch(sample_uid):
        raise ValueError(f"{view_path.name}: invalid sample_uid")
    for key in ("discussion_title", "direct_parent_body"):
        if not isinstance(context[key], str) or not context[key].strip():
            raise ValueError(f"{view_path.name}: empty context.{key}")
    if not isinstance(context["target_quotes"], list):
        raise ValueError(f"{view_path.name}: target_quotes is not an array")
    for key in ("body", "full_with_quotes"):
        if not isinstance(target[key], str) or not target[key].strip():
            raise ValueError(f"{view_path.name}: empty target.{key}")

    return {
        "schema_version": "stage-b-model-input-v1",
        "protocol_id": "DATA-FCTX-LABEL-V1",
        "annotation_order": annotation_order,
        "sample_uid": sample_uid,
        "view_sha256": hashlib.sha256(canonical_json_bytes(view)).hexdigest(),
        "context": context,
        "target": target,
    }


def export_stage_b_inputs(views_dir: Path, output_path: Path) -> dict[str, Any]:
    view_paths = sorted(views_dir.glob("*.json"))
    expected_names = [f"{index:04d}.json" for index in range(1, EXPECTED_VIEW_COUNT + 1)]
    if [path.name for path in view_paths] != expected_names:
        raise ValueError("views must be exactly 0001.json through 0120.json")

    rows = [
        load_stage_b_row(view_path, annotation_order)
        for annotation_order, view_path in enumerate(view_paths, start=1)
    ]
    if len({row["sample_uid"] for row in rows}) != EXPECTED_VIEW_COUNT:
        raise ValueError("sample_uid values are not unique")

    output_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            for row in rows:
                handle.write(canonical_json_bytes(row).decode("utf-8"))
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, output_path)
        os.chmod(output_path, 0o600)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

    output_bytes = output_path.read_bytes()
    return {
        "status": "passed",
        "rows": len(rows),
        "quote_blocks": sum(len(row["context"]["target_quotes"]) for row in rows),
        "output_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "file_mode": oct(output_path.stat().st_mode & 0o777),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--views-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = export_stage_b_inputs(args.views_dir, args.output)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
