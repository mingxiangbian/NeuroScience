"""Full website/Store/dispatcher paths with synthetic numeric backends only."""
from functools import partial
import json
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from topicweb.app import create_app
from topicweb.staged_inference import StagedEngine, decode_transfer, digest, canonical
from topicweb.staged_safety import SafetyError
from topicweb.staged_worker import StagedDispatcher
from topicweb import inference_process as bridge
from test_staged_inference import BASE_FP, Bundle, Guard, RUNTIME


class InstantMonitor:
    """No system/process claims: unit-test the integration without real waiting."""
    def __init__(self, private_dir, *, observer=None, on_block=None):
        self.reason = self.thread = self.last_absence = None
        self.samples, self.seen = [], set()
        self.observer, self.on_block = observer, on_block

    def start(self):
        pass

    def finish(self):
        pass

    def check(self):
        if self.reason:
            raise SafetyError(self.reason)

    def block(self, reason):
        self.reason = self.reason or reason
        self.on_block(self.reason)

    def wait_ready(self, deadline, cancelled):
        self.check()
        assert not cancelled()
        start = len(self.samples)
        self.samples.extend({"index": index} for index in range(start, start + 10))
        return list(range(start, start + 10))

    def wait_absent(self, after_index, deadline):
        self.samples.append({"index": len(self.samples)})
        self.last_absence = {"sample_index": self.samples[-1]["index"], "absent_model_keys": []}
        return self.last_absence

    def set_phase(self, logical_job_id, phase_id):
        pass

    def emit(self, kind, payload):
        if self.observer:
            self.observer(kind, payload)

    def observe_resources(self, resources):
        assert resources["peak_rss_bytes"] == 1024


class SyntheticM1:
    def predict_probabilities(self, text):
        return np.asarray([.75, .25, .125, .375, .25, .125], dtype=np.float32), 12


class SyntheticM3:
    def predict_probabilities(self, text):
        return np.asarray([.25, .75, .125, .25, .125, .375], dtype=np.float32)


class SyntheticPhaseRunner:
    def __init__(self, job, *, lock_fd, cancelled, deadline, monitor, logical_job_id, transfer=None, on_progress=None):
        self.exit_recorded = False
        init = {"op": "init", "mode": job["mode"], "max_qwen_calls": job["request"]["max_qwen_calls"], "audit_rate": 0, "seed": 42}
        kwargs = {"runtime": RUNTIME, "bundle": Bundle(), "guard": Guard(),
                  "metadata": lambda backend, text, kind, used: {"input_tokens": used or 20, "used_tokens": used or 20, "truncated": False},
                  "m3_factory": SyntheticM3}
        if transfer is None:
            self.engine = bridge.JobInference(init, m1=SyntheticM1(), fingerprint=BASE_FP, **kwargs)
        else:
            transfer_hash = digest(canonical(transfer))
            cache, hashes, fingerprint = decode_transfer(transfer, transfer_hash, BASE_FP)
            self.engine = StagedEngine(init, m1=None, fingerprint=fingerprint, **kwargs)
            self.engine.m1_cache, self.engine.input_hashes = cache, hashes
            self.engine.base_fingerprint, self.engine.transfer_sha256 = BASE_FP, transfer_hash
            self.engine.current_ordinal, self.engine.emit_progress = None, on_progress

    def predict(self, item_id, record):
        return self.engine.predict({"op": "predict", "item_id": str(item_id), "text": record["model_input_text"],
                                    "model_input_hash": record["model_input_hash"]})["result"]

    def finish(self):
        self.close()

    def close(self):
        self.exit_recorded = True


@pytest.mark.parametrize("mode,count,budget", [("m1_only", 340, 0), ("research", 340, 500),
                                               ("research", 500, 500), ("demo", 500, 0), ("demo", 500, 1)])
def test_full_upload_api_to_staged_dispatcher(mode, count, budget, tmp_path):
    app = create_app(private_dir=tmp_path / "private", token="synthetic-integration-token-32-characters",
                     dispatcher_factory=partial(StagedDispatcher, monitor_factory=InstantMonitor),
                     runner_factory=SyntheticPhaseRunner)
    with TestClient(app, base_url="http://127.0.0.1:8787", client=("127.0.0.1", 9876)) as client:
        client.headers["Authorization"] = "Bearer synthetic-integration-token-32-characters"
        payload = {"name": "Synthetic full snapshot", "source": "upload", "mode": mode, "max_qwen_calls": budget,
                   "upload": {"format": "json", "content": json.dumps([
                       {"id": str(index), "text": "Synthetic repeated input " + str(index // 2)} for index in range(count)])}}
        response = client.post("/api/jobs", json=payload)
        assert response.status_code == 202
        identifier = response.json()["job"]["id"]
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            job = client.get(f"/api/jobs/{identifier}").json()["job"]
            if job["state"] in {"completed", "completed_with_fallback", "failed"}:
                break
            time.sleep(.02)
        assert job["state"] == ("completed_with_fallback" if mode == "demo" else "completed"), job
        assert job["total_items"] == job["completed_items"] == count
        value = client.get(f"/api/jobs/{identifier}/dashboard").json()
        cost = value["routing"]["cost"]
        assert cost["m1_attempts"] == cost["m1_cache_hit"] == count // 2
        expected_m3 = 0 if mode == "m1_only" else min(budget, count // 2)
        assert cost["m3_attempts"] == cost["m3_succeeded"] == expected_m3
        assert cost["m3_cache_hit"] == expected_m3
        assert value["routing"]["prelude_transfer_reuses"] == (0 if mode == "m1_only" else count)
        assert value["routing"]["cost_complete"] is True
        assert value["summary"]["successful_items"] == count
        assert value["derived"]["available"] is True
        csv = client.get(f"/api/jobs/{identifier}/export.csv")
        assert csv.status_code == 200 and len(csv.text.splitlines()) == count + 1
        assert client.delete(f"/api/jobs/{identifier}/raw").status_code == 200
        assert client.post(f"/api/jobs/{identifier}/replay").status_code == 409
        assert client.delete(f"/api/jobs/{identifier}").status_code == 204
        assert client.get(f"/api/jobs/{identifier}").status_code == 404
