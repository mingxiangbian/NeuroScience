"""EXP-083 namespace adapter; reuse the unchanged EXP-082 observer algorithm."""
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
OBSERVER = ROOT / "scripts/diagnostic_m3_child.py"
OBSERVER_SHA256 = "6dc0da353b1f2d9da48151c5d6068279e5ed3bec2e6516e212bb098248548740"
STAGE_PATH = ROOT / "private/validation/exp-083/attempt-1/stages.jsonl"


def load_observer():
    if (any(path.is_symlink() for path in (OBSERVER, *OBSERVER.parents))
            or not stat.S_ISREG(OBSERVER.lstat().st_mode)
            or hashlib.sha256(OBSERVER.read_bytes()).hexdigest() != OBSERVER_SHA256):
        raise RuntimeError("inherited_observer_identity")
    spec = importlib.util.spec_from_file_location("exp083_inherited_observer", OBSERVER)
    observer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(observer)
    # Only this fresh module namespace changes. No file or tracing rule changes.
    observer.STAGE_PATH = STAGE_PATH
    return observer


def main():
    try:
        return load_observer().main()
    except Exception:
        os.write(2, b"EXP083 diagnostic adapter failed\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
