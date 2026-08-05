#!/usr/bin/env python3
"""Acquire and structurally validate the authorized GoEmotions test split."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import os
from pathlib import Path
import urllib.request

from test_gate_common import artifact, load_config, load_split, read_json, write_json


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
SOURCE_REVISION = "8dadc6c56e2c2e51a9dd7e0d4bf2840922b4b6c0"
SOURCE_URL = (
    "https://raw.githubusercontent.com/google-research/google-research/"
    f"{SOURCE_REVISION}/goemotions/data/test.tsv"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "goemotions" / "official" / "test.tsv"
DEFAULT_BINDING = SCRIPT_DIR / "preflight" / "exp-038-test-binding.json"
DEFAULT_CONFIG = SCRIPT_DIR / "configs" / "exp-038-preregistered.json"
REQUIRED_PREFLIGHTS = (
    SCRIPT_DIR / "preflight" / "exp-038-classical-bert.json",
    SCRIPT_DIR / "preflight" / "exp-038-qwen.json",
)
LABELS_PATH = PROJECT_ROOT / "data" / "goemotions" / "official" / "emotions.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--binding", type=Path, default=DEFAULT_BINDING)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--config-sha256", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _, preregistered_sha256 = load_config(
        args.config.resolve(),
        args.config_sha256,
        allow_unbound_test=True,
    )
    for preflight_path in REQUIRED_PREFLIGHTS:
        if not preflight_path.is_file():
            raise FileNotFoundError(preflight_path)
        preflight = read_json(preflight_path)
        if (
            preflight.get("status") != "Passed"
            or preflight.get("test_split_accessed") is not False
            or preflight.get("config_sha256") != preregistered_sha256
        ):
            raise ValueError(f"Required preflight did not pass: {preflight_path}")
    output = args.output.resolve()
    binding = args.binding.resolve()
    if output.exists() or binding.exists():
        raise FileExistsError("EXP-038 acquisition outputs already exist")
    output.parent.mkdir(parents=True, exist_ok=True)
    binding.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    if temporary.exists():
        raise FileExistsError(temporary)

    try:
        request = urllib.request.Request(
            SOURCE_URL,
            headers={"User-Agent": "NeuroScience-EXP-038-test-gate/1.0"},
        )
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open(
            "xb"
        ) as handle:
            if response.status != 200:
                raise RuntimeError(f"Unexpected HTTP status: {response.status}")
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())

        labels = tuple(LABELS_PATH.read_text(encoding="utf-8").splitlines())
        _, _, _, structural = load_split(temporary, 5427, labels)
        with temporary.open("r", encoding="utf-8", newline="") as handle:
            if any(len(row) != 3 for row in csv.reader(handle, delimiter="\t")):
                raise ValueError("Downloaded test split does not have exactly three columns")
        os.replace(temporary, output)
        write_json(
            binding,
            {
                "acquired_at_utc": datetime.now(timezone.utc).isoformat(),
                "artifact": artifact(output),
                "binding_contains_raw_text_or_ids": False,
                "preregistered_config_sha256": preregistered_sha256,
                "source_revision": SOURCE_REVISION,
                "source_url": SOURCE_URL,
                "structural_validation": {
                    "columns": 3,
                    "label_count": len(labels),
                    "rows": structural["rows"],
                    "unique_comment_ids": structural["unique_comment_ids"],
                },
            },
        )
        print(f"Bound official test: rows={structural['rows']} sha256={artifact(output)['sha256']}")
    finally:
        if temporary.exists():
            temporary.unlink()


if __name__ == "__main__":
    main()
