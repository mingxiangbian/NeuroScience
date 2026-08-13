#!/usr/bin/env python3
"""Export the frozen Stage A model inputs without revealing context fields."""

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


def load_stage_a_row(view_path: Path, annotation_order: int) -> dict[str, Any]:
    view = json.loads(view_path.read_text(encoding="utf-8"))

    if view.get("schema_version") != "annotation-view-v1":
        raise ValueError(f"{view_path.name}: unexpected view schema")
    if view.get("protocol_id") != "DATA-FCTX-LABEL-V1":
        raise ValueError(f"{view_path.name}: unexpected protocol")

    display_contract = view.get("display_contract")
    if not isinstance(display_contract, dict):
        raise ValueError(f"{view_path.name}: missing display contract")
    expected_contract = {
        "stage_a": "target.body",
        "stage_b": "context+target",
        "stage_a_locked_before_stage_b": True,
        "future_replies_included": False,
        "ancestor_chain_included": False,
    }
    if display_contract != expected_contract:
        raise ValueError(f"{view_path.name}: display contract changed")

    ids = view.get("ids")
    target = view.get("target")
    if not isinstance(ids, dict) or not isinstance(target, dict):
        raise ValueError(f"{view_path.name}: missing ids or target")

    sample_uid = ids.get("sample_uid")
    target_body = target.get("body")
    if not isinstance(sample_uid, str) or not SAMPLE_UID_RE.fullmatch(sample_uid):
        raise ValueError(f"{view_path.name}: invalid sample_uid")
    if not isinstance(target_body, str) or not target_body.strip():
        raise ValueError(f"{view_path.name}: empty target.body")

    return {
        "schema_version": "stage-a-model-input-v1",
        "protocol_id": "DATA-FCTX-LABEL-V1",
        "annotation_order": annotation_order,
        "sample_uid": sample_uid,
        "view_sha256": hashlib.sha256(canonical_json_bytes(view)).hexdigest(),
        "target_body": target_body,
    }


def export_stage_a_inputs(views_dir: Path, output_path: Path) -> dict[str, Any]:
    view_paths = sorted(views_dir.glob("*.json"))
    expected_names = [f"{index:04d}.json" for index in range(1, EXPECTED_VIEW_COUNT + 1)]
    if [path.name for path in view_paths] != expected_names:
        raise ValueError("views must be exactly 0001.json through 0120.json")

    rows = [
        load_stage_a_row(view_path, annotation_order)
        for annotation_order, view_path in enumerate(view_paths, start=1)
    ]
    sample_uids = [row["sample_uid"] for row in rows]
    if len(set(sample_uids)) != EXPECTED_VIEW_COUNT:
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
    result = export_stage_a_inputs(args.views_dir, args.output)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
