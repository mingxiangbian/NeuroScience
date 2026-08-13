from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROTOCOL_ID = "DATA-FCTX-ADJ-DIAG-V1"
CASE_SCHEMA_VERSION = "source-blind-adjudication-case-v1"
RECORD_SCHEMA_VERSION = "source-blind-adjudication-record-v1"
DEFAULT_ADJUDICATOR_UID = "ann_primary_human"
DEFAULT_SESSION_LIMIT = 20

EMOTION_LABELS = (
    "anger",
    "frustration",
    "disappointment",
    "sadness",
    "fear",
    "joy",
    "surprise",
    "confusion",
    "disgust",
    "cynicism",
    "neutral",
    "other_emotion",
)
DECISION_STATUSES = ("labeled", "unclear", "unusable")
CONFIDENCE_LEVELS = ("low", "medium", "high")
EMOTION_PRESENCE_VALUES = ("clear_emotion", "no_clear_emotion", "uncertain")
STANCE_VALUES = ("support", "oppose", "mixed", "none", "uncertain")
UNIT_VALIDITY_VALUES = (
    "valid_single_unit",
    "multi_segment_or_mixed_unit",
    "insufficient_context",
    "unusable",
)
CANDIDATE_ASSESSMENTS = (
    "supported",
    "acceptable_but_not_primary",
    "unsupported",
    "undecidable",
)
RESOLUTION_VALUES = ("final_decision", "no_stable_gold")
REASON_CODES = (
    "stance_vs_emotion",
    "neutral_vs_unclear",
    "anger_vs_frustration",
    "context_changes_interpretation",
    "multi_segment_or_mixed",
    "ontology_gap",
    "insufficient_context",
    "clear_protocol_violation",
    "other_documented_reason",
)
CANDIDATE_ALIASES = ("candidate_a", "candidate_b", "candidate_c")

ADJUDICATOR_UID_RE = re.compile(r"^ann_[a-z0-9_]{3,48}$")
BLIND_CASE_ID_RE = re.compile(r"^[0-9]{3}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OTHER_EMOTION_RE = re.compile(r"^[A-Za-z][A-Za-z -]{0,63}$")


class AdjudicationError(Exception):
    status_code = 400


class AdjudicationConflict(AdjudicationError):
    status_code = 409


def canonical_case_sha256(case: dict[str, Any]) -> str:
    payload = {key: value for key, value in case.items() if key != "case_sha256"}
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class BlindAdjudicationStore:
    def __init__(
        self,
        bundle_path: Path,
        records_dir: Path,
        *,
        adjudicator_uid: str = DEFAULT_ADJUDICATOR_UID,
        expected_total: int | None = 40,
        session_limit: int = DEFAULT_SESSION_LIMIT,
        dataset_mode: str = "private",
    ) -> None:
        if not ADJUDICATOR_UID_RE.fullmatch(adjudicator_uid):
            raise ValueError("adjudicator_uid does not match the record schema")
        if session_limit < 1:
            raise ValueError("session_limit must be positive")
        if dataset_mode not in {"private", "synthetic"}:
            raise ValueError("dataset_mode must be private or synthetic")

        self.bundle_path = bundle_path.resolve()
        self.records_dir = records_dir.resolve()
        self.adjudicator_uid = adjudicator_uid
        self.expected_total = expected_total
        self.session_limit = session_limit
        self.dataset_mode = dataset_mode
        self._lock = threading.RLock()

        self._ensure_private_records_dir()
        self._cases = self._load_cases()
        self._case_by_id = {case["blind_case_id"]: case for case in self._cases}
        self._validate_existing_records()

        self._session_uid = ""
        self._session_completed = 0
        self._session_ended = False
        self._session_started = False

    @staticmethod
    def utc_now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        )

    def _ensure_private_records_dir(self) -> None:
        self.records_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.records_dir.is_symlink():
            raise ValueError("records_dir must not be a symlink")
        os.chmod(self.records_dir, 0o700)

    def _load_cases(self) -> list[dict[str, Any]]:
        if not self.bundle_path.is_file() or self.bundle_path.is_symlink():
            raise ValueError(f"blind bundle is unavailable: {self.bundle_path}")

        cases: list[dict[str, Any]] = []
        for line_number, line in enumerate(
            self.bundle_path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line:
                raise ValueError(f"blank row in blind bundle at line {line_number}")
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid blind bundle JSON at line {line_number}: {exc}"
                ) from exc
            self._validate_case(case, line_number)
            expected_id = f"{line_number:03d}"
            if case["blind_case_id"] != expected_id:
                raise ValueError(
                    f"blind case order is not contiguous: expected {expected_id}"
                )
            cases.append(case)

        if self.expected_total is not None and len(cases) != self.expected_total:
            raise ValueError(
                f"expected {self.expected_total} blind cases, found {len(cases)}"
            )
        if not cases:
            raise ValueError("blind bundle contains no cases")
        return cases

    def _validate_case(self, case: Any, line_number: int) -> None:
        if not isinstance(case, dict):
            raise ValueError(f"blind case must be an object at line {line_number}")
        expected = {
            "schema_version",
            "protocol_id",
            "blind_case_id",
            "case_sha256",
            "content",
            "candidates",
        }
        if set(case) != expected:
            raise ValueError(f"blind case fields mismatch at line {line_number}")
        if case["schema_version"] != CASE_SCHEMA_VERSION:
            raise ValueError(f"blind case schema mismatch at line {line_number}")
        if case["protocol_id"] != PROTOCOL_ID:
            raise ValueError(f"blind case protocol mismatch at line {line_number}")
        if not BLIND_CASE_ID_RE.fullmatch(str(case["blind_case_id"])):
            raise ValueError(f"invalid blind case id at line {line_number}")
        if not SHA256_RE.fullmatch(str(case["case_sha256"])):
            raise ValueError(f"invalid blind case hash at line {line_number}")
        if canonical_case_sha256(case) != case["case_sha256"]:
            raise ValueError(f"blind case hash mismatch at line {line_number}")

        content = case["content"]
        if not isinstance(content, dict) or set(content) != {
            "discussion_title",
            "direct_parent_body",
            "target_quotes",
            "target_full_with_quotes",
        }:
            raise ValueError(f"blind case content mismatch at line {line_number}")
        for key in (
            "discussion_title",
            "direct_parent_body",
            "target_full_with_quotes",
        ):
            if not isinstance(content[key], str) or not content[key].strip():
                raise ValueError(f"invalid content.{key} at line {line_number}")
        if not isinstance(content["target_quotes"], list) or not all(
            isinstance(value, str) for value in content["target_quotes"]
        ):
            raise ValueError(f"invalid target quotes at line {line_number}")

        candidates = case["candidates"]
        if not isinstance(candidates, list) or len(candidates) != 3:
            raise ValueError(f"expected three candidates at line {line_number}")
        aliases = []
        for candidate in candidates:
            if not isinstance(candidate, dict) or set(candidate) != {
                "alias",
                "decision",
            }:
                raise ValueError(f"candidate fields mismatch at line {line_number}")
            aliases.append(candidate["alias"])
            self._validate_candidate_decision(candidate["decision"])
        if tuple(aliases) != CANDIDATE_ALIASES:
            raise ValueError(f"candidate aliases mismatch at line {line_number}")

    @staticmethod
    def _validate_candidate_decision(decision: Any) -> None:
        if not isinstance(decision, dict) or set(decision) != {
            "status",
            "primary_emotion",
            "other_emotion_text",
        }:
            raise ValueError("candidate decision fields mismatch")
        status = decision["status"]
        primary = decision["primary_emotion"]
        other = decision["other_emotion_text"]
        if status not in DECISION_STATUSES:
            raise ValueError("candidate decision status is invalid")
        if status == "labeled":
            if primary not in EMOTION_LABELS:
                raise ValueError("candidate primary emotion is invalid")
            if primary == "other_emotion":
                if not isinstance(other, str) or not other.strip() or len(other) > 64:
                    raise ValueError("candidate other emotion is invalid")
            elif other is not None:
                raise ValueError("candidate other emotion must be null")
        elif primary is not None or other is not None:
            raise ValueError("non-labeled candidate contains an emotion")

    def _record_path(self, blind_case_id: str) -> Path:
        if blind_case_id not in self._case_by_id:
            raise AdjudicationError("unknown blind case")
        return self.records_dir / f"{blind_case_id}.json"

    def _load_record(self, case: dict[str, Any]) -> dict[str, Any] | None:
        path = self._record_path(case["blind_case_id"])
        if not path.exists():
            return None
        if path.is_symlink():
            raise ValueError(f"record must not be a symlink: {path.name}")
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid adjudication record {path.name}: {exc}") from exc
        self._validate_record(record, case)
        return record

    def _validate_existing_records(self) -> None:
        known_names = {f"{case['blind_case_id']}.json" for case in self._cases}
        unexpected = [
            path.name
            for path in self.records_dir.glob("*.json")
            if path.name not in known_names
        ]
        if unexpected:
            raise ValueError(f"unexpected record files: {', '.join(sorted(unexpected))}")
        for case in self._cases:
            self._load_record(case)

    def _new_record(self, case: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": RECORD_SCHEMA_VERSION,
            "protocol_id": PROTOCOL_ID,
            "blind_case_id": case["blind_case_id"],
            "case_sha256": case["case_sha256"],
            "adjudicator": {
                "adjudicator_uid": self.adjudicator_uid,
                "role": "human",
                "annotation_mode": "source_blind_diagnostic",
            },
            "phase_1": None,
            "phase_2": None,
            "started_at": self.utc_now(),
            "completed_at": None,
        }

    def _validate_record(self, record: Any, case: dict[str, Any]) -> None:
        if not isinstance(record, dict):
            raise ValueError("adjudication record must be an object")
        expected = {
            "schema_version",
            "protocol_id",
            "blind_case_id",
            "case_sha256",
            "adjudicator",
            "phase_1",
            "phase_2",
            "started_at",
            "completed_at",
        }
        if set(record) != expected:
            raise ValueError("adjudication record fields mismatch")
        if record["schema_version"] != RECORD_SCHEMA_VERSION:
            raise ValueError("adjudication record schema mismatch")
        if record["protocol_id"] != PROTOCOL_ID:
            raise ValueError("adjudication record protocol mismatch")
        if record["blind_case_id"] != case["blind_case_id"]:
            raise ValueError("adjudication record case mismatch")
        if record["case_sha256"] != case["case_sha256"]:
            raise ValueError("adjudication record hash mismatch")
        if record["adjudicator"] != {
            "adjudicator_uid": self.adjudicator_uid,
            "role": "human",
            "annotation_mode": "source_blind_diagnostic",
        }:
            raise ValueError("adjudication record author boundary mismatch")
        if not isinstance(record["started_at"], str):
            raise ValueError("adjudication record started_at missing")

        phase_1 = record["phase_1"]
        phase_2 = record["phase_2"]
        if phase_1 is not None:
            self._normalize_phase_1(phase_1)
        if phase_2 is not None:
            if phase_1 is None:
                raise ValueError("Phase 2 exists without locked Phase 1")
            self._normalize_phase_2(phase_2)
        completed = isinstance(record["completed_at"], str)
        if completed != (phase_2 is not None):
            raise ValueError("adjudication record completion state mismatch")

    @staticmethod
    def _single_line(value: Any, *, max_length: int, field: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise AdjudicationError(f"{field} must be text")
        normalized = value.strip()
        if not normalized:
            return None
        if "\n" in normalized or "\r" in normalized:
            raise AdjudicationError(f"{field} must be a single line")
        if len(normalized) > max_length:
            raise AdjudicationError(f"{field} exceeds {max_length} characters")
        return normalized

    @staticmethod
    def _note(value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise AdjudicationError("note must be text")
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 1000:
            raise AdjudicationError("note exceeds 1000 characters")
        return normalized

    def _normalize_decision(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise AdjudicationError("decision must be an object")
        expected = {"status", "primary_emotion", "other_emotion_text"}
        if set(payload) != expected:
            raise AdjudicationError("decision fields do not match the protocol")
        status = payload["status"]
        primary = payload["primary_emotion"]
        other = self._single_line(
            payload["other_emotion_text"],
            max_length=64,
            field="other_emotion_text",
        )
        if status not in DECISION_STATUSES:
            raise AdjudicationError("decision status is invalid")
        if status == "labeled":
            if primary not in EMOTION_LABELS:
                raise AdjudicationError("primary_emotion is required")
            if primary == "other_emotion":
                if other is None or not OTHER_EMOTION_RE.fullmatch(other):
                    raise AdjudicationError(
                        "other_emotion_text must be a short atomic English name"
                    )
                other = other.lower()
            elif other is not None:
                raise AdjudicationError(
                    "other_emotion_text is only allowed with other_emotion"
                )
        else:
            if primary is not None or other is not None:
                raise AdjudicationError(
                    "unclear and unusable decisions cannot contain an emotion"
                )
            primary = None
            other = None
        return {
            "status": status,
            "primary_emotion": primary,
            "other_emotion_text": other,
        }

    def _normalize_phase_1(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise AdjudicationError("Phase 1 payload must be an object")
        expected = {
            "emotion_presence",
            "stance",
            "unit_validity",
            "independent_decision",
            "confidence",
            "note",
        }
        if set(payload) != expected:
            raise AdjudicationError("Phase 1 fields do not match the protocol")
        if payload["emotion_presence"] not in EMOTION_PRESENCE_VALUES:
            raise AdjudicationError("emotion_presence is required")
        if payload["stance"] not in STANCE_VALUES:
            raise AdjudicationError("stance is required")
        if payload["unit_validity"] not in UNIT_VALIDITY_VALUES:
            raise AdjudicationError("unit_validity is required")
        if payload["confidence"] not in CONFIDENCE_LEVELS:
            raise AdjudicationError("confidence is required")

        decision = self._normalize_decision(payload["independent_decision"])
        note = self._note(payload["note"])
        unit_unusable = payload["unit_validity"] == "unusable"
        decision_unusable = decision["status"] == "unusable"
        if unit_unusable != decision_unusable:
            raise AdjudicationError(
                "unit_validity and an unusable decision must be selected together"
            )
        if decision_unusable and note is None:
            raise AdjudicationError("an unusable decision requires a note")
        return {
            "emotion_presence": payload["emotion_presence"],
            "stance": payload["stance"],
            "unit_validity": payload["unit_validity"],
            "independent_decision": decision,
            "confidence": payload["confidence"],
            "note": note,
        }

    def _normalize_phase_2(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise AdjudicationError("Phase 2 payload must be an object")
        expected = {
            "candidate_assessments",
            "resolution",
            "final_decision",
            "primary_reason",
            "note",
        }
        if set(payload) != expected:
            raise AdjudicationError("Phase 2 fields do not match the protocol")
        assessments = payload["candidate_assessments"]
        if not isinstance(assessments, dict) or set(assessments) != set(
            CANDIDATE_ALIASES
        ):
            raise AdjudicationError("all three candidate assessments are required")
        if any(value not in CANDIDATE_ASSESSMENTS for value in assessments.values()):
            raise AdjudicationError("candidate assessment is invalid")
        resolution = payload["resolution"]
        if resolution not in RESOLUTION_VALUES:
            raise AdjudicationError("resolution is required")
        if payload["primary_reason"] not in REASON_CODES:
            raise AdjudicationError("primary_reason is required")
        note = self._note(payload["note"])

        if resolution == "final_decision":
            final_decision = self._normalize_decision(payload["final_decision"])
            if final_decision["status"] == "unusable" and note is None:
                raise AdjudicationError("an unusable final decision requires a note")
        else:
            if payload["final_decision"] is not None:
                raise AdjudicationError(
                    "no_stable_gold must not contain a final decision"
                )
            if note is None:
                raise AdjudicationError("no_stable_gold requires a note")
            final_decision = None
        if payload["primary_reason"] == "other_documented_reason" and note is None:
            raise AdjudicationError("other_documented_reason requires a note")
        return {
            "candidate_assessments": {
                alias: assessments[alias] for alias in CANDIDATE_ALIASES
            },
            "resolution": resolution,
            "final_decision": final_decision,
            "primary_reason": payload["primary_reason"],
            "note": note,
        }

    def _atomic_write_record(self, case: dict[str, Any], record: dict[str, Any]) -> None:
        self._validate_record(record, case)
        destination = self._record_path(case["blind_case_id"])
        if destination.is_symlink():
            raise ValueError(f"record must not be a symlink: {destination.name}")

        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{case['blind_case_id']}.", suffix=".tmp", dir=self.records_dir
        )
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(record, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, destination)
            os.chmod(destination, 0o600)
            directory_fd = os.open(self.records_dir, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

    def _append_session_event(self, event: str, **fields: Any) -> None:
        path = self.records_dir / "session-log.jsonl"
        payload = {
            "schema_version": "adjudication-session-event-v1",
            "protocol_id": PROTOCOL_ID,
            "event": event,
            "session_uid": self._session_uid,
            "adjudicator_uid": self.adjudicator_uid,
            "timestamp": self.utc_now(),
            **fields,
        }
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.fchmod(fd, 0o600)
            os.write(
                fd,
                (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode(
                    "utf-8"
                ),
            )
            os.fsync(fd)
        finally:
            os.close(fd)

    def _ensure_session_started(self) -> None:
        if self._session_started:
            return
        self._session_uid = "ses_" + uuid.uuid4().hex
        self._session_started = True
        self._append_session_event("session_started")

    def _counts(self) -> dict[str, int]:
        phase_1_done = 0
        completed = 0
        for case in self._cases:
            record = self._load_record(case)
            if record is None:
                continue
            if record["phase_1"] is not None:
                phase_1_done += 1
            if record["phase_2"] is not None:
                completed += 1
        return {"phase_1_done": phase_1_done, "completed": completed}

    def _next_incomplete(self) -> tuple[dict[str, Any], dict[str, Any] | None] | None:
        for case in self._cases:
            record = self._load_record(case)
            if record is None or record["phase_2"] is None:
                return case, record
        return None

    def _progress(self, case: dict[str, Any] | None = None) -> dict[str, Any]:
        counts = self._counts()
        return {
            **counts,
            "total": len(self._cases),
            "position": int(case["blind_case_id"]) if case else None,
            "session_completed": self._session_completed,
            "session_limit": self.session_limit,
        }

    def current(self) -> dict[str, Any]:
        with self._lock:
            self._ensure_session_started()
            pending = self._next_incomplete()
            if pending is None:
                return {"state": "complete", "progress": self._progress()}
            if self._session_ended or self._session_completed >= self.session_limit:
                if not self._session_ended:
                    self.end_session(reason="continuous_limit_reached")
                return {"state": "session_break", "progress": self._progress()}

            case, record = pending
            if record is None:
                record = self._new_record(case)
                self._atomic_write_record(case, record)
            common = {
                "state": "case",
                "case_id": case["blind_case_id"],
                "content": case["content"],
                "progress": self._progress(case),
            }
            if record["phase_1"] is None:
                return {**common, "stage": "phase_1"}
            return {
                **common,
                "stage": "phase_2",
                "phase_1_locked": True,
                "phase_1_summary": record["phase_1"],
                "candidates": case["candidates"],
            }

    def _require_current_case(self, case_id: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        if self._session_ended or self._session_completed >= self.session_limit:
            raise AdjudicationConflict("the current adjudication session is closed")
        pending = self._next_incomplete()
        if pending is None:
            raise AdjudicationConflict("all blind adjudication cases are complete")
        case, record = pending
        if case_id != case["blind_case_id"]:
            raise AdjudicationConflict("the requested case is not the active case")
        if record is None:
            record = self._new_record(case)
            self._atomic_write_record(case, record)
        return case, record

    def submit_phase_1(self, case_id: Any, payload: Any) -> dict[str, Any]:
        with self._lock:
            case, record = self._require_current_case(case_id)
            if record["phase_1"] is not None:
                raise AdjudicationConflict("Phase 1 is already locked")
            record["phase_1"] = self._normalize_phase_1(payload)
            self._atomic_write_record(case, record)
            self._append_session_event("phase_1_locked", case_id=case["blind_case_id"])
            return self.current()

    def submit_phase_2(self, case_id: Any, payload: Any) -> dict[str, Any]:
        with self._lock:
            case, record = self._require_current_case(case_id)
            if record["phase_1"] is None:
                raise AdjudicationConflict("Phase 1 must be locked before Phase 2")
            if record["phase_2"] is not None:
                raise AdjudicationConflict("Phase 2 is already locked")
            record["phase_2"] = self._normalize_phase_2(payload)
            record["completed_at"] = self.utc_now()
            self._atomic_write_record(case, record)
            self._session_completed += 1
            self._append_session_event("case_completed", case_id=case["blind_case_id"])
            return self.current()

    def end_session(self, *, reason: str = "user_ended") -> dict[str, Any]:
        with self._lock:
            self._ensure_session_started()
            if not self._session_ended:
                self._session_ended = True
                self._append_session_event(
                    "session_ended",
                    reason=reason,
                    completed_cases=self._session_completed,
                )
            return {"state": "session_break", "progress": self._progress()}

    def start_session(self) -> dict[str, Any]:
        with self._lock:
            if not self._session_ended:
                raise AdjudicationConflict("the current session is still active")
            self._session_uid = "ses_" + uuid.uuid4().hex
            self._session_completed = 0
            self._session_ended = False
            self._session_started = True
            self._append_session_event("session_started")
            return self.current()

    def close(self) -> None:
        with self._lock:
            if self._session_started and not self._session_ended:
                self.end_session(reason="server_stopped")
