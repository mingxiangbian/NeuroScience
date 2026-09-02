import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("bounded_closeout_tested", Path(__file__).resolve().parents[1] / "scripts/closeout_bounded_operational.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def bounded(complete):
    return {"status": "Passed", "exp079_complete": complete,
            "operational_state": "safe-to-continue" if complete else "stop-required"}


@pytest.mark.parametrize("safe,discourse,expected", [
    (False, None, False), (True, None, False),
    (True, {"status": "Passed", "exp080_complete": False}, False),
    (True, {"status": "Passed", "exp080_complete": True}, True),
])
def test_completion_requires_both_actual_gates(safe, discourse, expected):
    assert module.decide(bounded(safe), discourse)["full_operational_completion"] is expected


def test_audit_pass_never_overrides_failed_run():
    value = module.decide(bounded(False), None)
    assert value["bounded_operational_pass"] is False
    assert value["discourse_state"] == "Not executed"


def test_unsafe_upstream_cannot_admit_discourse():
    with pytest.raises(ValueError, match="precondition"):
        module.decide(bounded(False), {"status": "Passed", "exp080_complete": True})


def test_failed_audits_are_not_publishable():
    value = module.decide({"status": "Failed", "exp079_complete": True, "operational_state": "safe-to-continue"}, None)
    assert value["bounded_operational_pass"] is False and value["full_operational_completion"] is False
    assert value["bounded_verification_status"] == "Failed"
    with pytest.raises(ValueError, match="exp079_audit"):
        module.decide({"status": "Running"}, None)
    with pytest.raises(ValueError, match="exp080_audit"):
        module.decide(bounded(True), {"status": "Failed"})
