"""EXP-081 metadata-only synthesis; never opens a dataset or starts a job."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "private/validation/exp-081/attempt-2"


def decide(bounded, discourse):
    if bounded.get("status") not in {"Passed", "Failed"}:
        raise ValueError("exp079_audit_not_terminal")
    safe = bounded.get("status") == "Passed" and bounded.get("exp079_complete") is True and bounded.get("operational_state") == "safe-to-continue"
    if discourse is not None and not safe:
        raise ValueError("discourse_without_verified_safe_precondition")
    if discourse is not None and discourse.get("status") != "Passed":
        raise ValueError("exp080_audit_not_passed")
    portable = discourse is not None and discourse.get("exp080_complete") is True
    return {"bounded_operational_pass": safe, "discourse_formal_pass": portable,
            "bounded_verification_status": bounded["status"],
            "full_operational_completion": safe and portable,
            "overall": "Verified bounded operational research prototype; two-source service portability"
            if safe and portable else "Independent verification incomplete; operational goals not established"
            if bounded["status"] == "Failed" else "Operational goals not fully established",
            "discourse_state": "Verified Pass" if portable else "Audited non-pass" if discourse is not None else "Not executed"}


def read(path):
    if not path.is_file() or any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("source_missing_or_symlink")
    payload = path.read_bytes()
    return json.loads(payload), hashlib.sha256(payload).hexdigest()


def main():
    paths = {
        "exp076": ROOT / "private/validation/exp-076/attempt-3/verification.json",
        "exp077": ROOT / "private/validation/exp-077/attempt-1/verification.json",
        "exp079_attempt1": ROOT / "private/validation/exp-079/attempt-1/verification.json",
        "exp079_attempt2": ROOT / "private/validation/exp-079/attempt-2/verification.json",
        "exp079": ROOT / "private/validation/exp-079/attempt-3/verification.json",
    }
    discourse = ROOT / "private/validation/exp-080/attempt-1/verification.json"
    if discourse.exists():
        paths["exp080"] = discourse
    documents, bindings = {}, {}
    for name, path in paths.items():
        documents[name], hashed = read(path)
        bindings[name] = {"path": str(path.relative_to(ROOT)), "sha256": hashed}
    assert documents["exp076"].get("status") == "Passed" and documents["exp076"].get("exp076_verified") is True
    assert documents["exp077"].get("exp077_complete") is False
    assert documents["exp079_attempt1"].get("exp079_complete") is False
    assert documents["exp079_attempt2"].get("status") == "Failed"
    decision = decide(documents["exp079"], documents.get("exp080"))
    protocol = ROOT.parent / "experiments/stack-overflow-emotion-gold/protocols/exp-081-phase-c1-operational-closeout.md"
    result = {"experiment_id": "EXP-081", "tier": "Minor", "rq": "RQ-S3", "status": "Completed",
              "generated_at": datetime.now(timezone.utc).isoformat(), "command": sys.argv,
              "inputs": bindings, "decision": decision, "old_exp077_unchanged_nonpass": True,
              "training": False, "model_forward": False, "gold_accessed": False, "new_source_collection": False,
              "protocol_sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
              "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "claim_boundary": "Finite local operational evidence only; no external accuracy, human emotion, efficiency comparison or SLA claim."}
    for name, path in paths.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == bindings[name]["sha256"]
    if any(part.is_symlink() for part in (OUT, *OUT.parents)):
        raise ValueError("output_symlink")
    OUT.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(OUT / "run.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps(decision, ensure_ascii=False))


if __name__ == "__main__":
    if sys.argv[1:] in (["--help"], ["-h"]):
        print("EXP-081 metadata-only closeout after independent EXP-079/080 audits; create-only output.")
    elif sys.argv[1:]:
        raise SystemExit("unexpected_arguments")
    else:
        main()
