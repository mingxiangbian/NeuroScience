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


PROTOCOL_ID = "DATA-FCTX-LABEL-V1"
RECORD_SCHEMA_VERSION = "annotation-record-v1"
DEFAULT_ANNOTATOR_UID = "ann_primary_human"
DEFAULT_SESSION_LIMIT = 40
QUALITY_STOP_UNUSABLE_COUNT = 6

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
CONFIDENCE_LEVELS = ("low", "medium", "high")
SARCASM_VALUES = ("present", "absent", "uncertain")
CONTEXT_SUFFICIENCY_VALUES = ("sufficient", "insufficient", "uncertain")
DECISION_STATUSES = ("unlabeled", "labeled", "unclear", "unusable")

SAMPLE_UID_RE = re.compile(r"^smp_[0-9a-f]{64}$")
ANNOTATOR_UID_RE = re.compile(r"^ann_[a-z0-9_]{3,48}$")
OTHER_EMOTION_RE = re.compile(r"^[A-Za-z][A-Za-z -]{0,63}$")


class AnnotationError(Exception):
    status_code = 400


class AnnotationConflict(AnnotationError):
    status_code = 409


class AnnotationStore:
    def __init__(
        self,
        views_dir: Path,
        records_dir: Path,
        *,
        annotator_uid: str = DEFAULT_ANNOTATOR_UID,
        expected_total: int | None = 120,
        session_limit: int = DEFAULT_SESSION_LIMIT,
        dataset_mode: str = "private",
    ) -> None:
        if not ANNOTATOR_UID_RE.fullmatch(annotator_uid):
            raise ValueError("annotator_uid does not match the frozen record schema")
        if session_limit < 1:
            raise ValueError("session_limit must be positive")
        if dataset_mode not in {"private", "synthetic"}:
            raise ValueError("dataset_mode must be private or synthetic")

        self.views_dir = views_dir.resolve()
        self.records_dir = records_dir.resolve()
        self.annotator_uid = annotator_uid
        self.expected_total = expected_total
        self.session_limit = session_limit
        self.dataset_mode = dataset_mode
        self._lock = threading.RLock()

        self._ensure_private_records_dir()
        self._cases = self._load_cases()
        self._case_by_id = {case["case_id"]: case for case in self._cases}
        self._validate_existing_records()

        self._session_uid = ""
        self._session_completed = 0
        self._session_ended = False
        self._session_started = False

    @staticmethod
    def utc_now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    @staticmethod
    def canonical_view_sha256(view: dict[str, Any]) -> str:
        payload = json.dumps(
            view,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _ensure_private_records_dir(self) -> None:
        self.records_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.records_dir.is_symlink():
            raise ValueError("records_dir must not be a symlink")
        os.chmod(self.records_dir, 0o700)

    def _load_cases(self) -> list[dict[str, Any]]:
        if not self.views_dir.is_dir() or self.views_dir.is_symlink():
            raise ValueError(f"view directory is unavailable: {self.views_dir}")

        paths = sorted(self.views_dir.glob("*.json"))
        if self.expected_total is not None and len(paths) != self.expected_total:
            raise ValueError(
                f"expected {self.expected_total} private views, found {len(paths)}"
            )
        if not paths:
            raise ValueError("no annotation views found")

        cases: list[dict[str, Any]] = []
        seen_samples: set[str] = set()
        for position, path in enumerate(paths, start=1):
            expected_name = f"{position:04d}.json"
            if path.name != expected_name:
                raise ValueError(
                    f"view order is not contiguous: expected {expected_name}, found {path.name}"
                )
            if path.is_symlink():
                raise ValueError(f"view must not be a symlink: {path.name}")
            try:
                view = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid view file {path.name}: {exc}") from exc
            self._validate_view(view, path.name)
            sample_uid = view["ids"]["sample_uid"]
            if sample_uid in seen_samples:
                raise ValueError(f"duplicate sample_uid in view set: {path.name}")
            seen_samples.add(sample_uid)
            cases.append(
                {
                    "case_id": path.stem,
                    "position": position,
                    "path": path,
                    "view": view,
                    "view_sha256": self.canonical_view_sha256(view),
                }
            )
        return cases

    @staticmethod
    def _validate_view(view: Any, filename: str) -> None:
        if not isinstance(view, dict):
            raise ValueError(f"view must be an object: {filename}")
        if view.get("schema_version") != "annotation-view-v1":
            raise ValueError(f"unexpected view schema: {filename}")
        if view.get("protocol_id") != PROTOCOL_ID:
            raise ValueError(f"unexpected protocol id: {filename}")

        ids = view.get("ids")
        context = view.get("context")
        target = view.get("target")
        contract = view.get("display_contract")
        if not isinstance(ids, dict) or not SAMPLE_UID_RE.fullmatch(
            str(ids.get("sample_uid", ""))
        ):
            raise ValueError(f"invalid sample_uid: {filename}")
        if not isinstance(context, dict) or not isinstance(target, dict):
            raise ValueError(f"missing context or target: {filename}")
        for key in ("discussion_title", "direct_parent_body"):
            if not isinstance(context.get(key), str) or not context[key].strip():
                raise ValueError(f"invalid context.{key}: {filename}")
        if not isinstance(context.get("target_quotes"), list):
            raise ValueError(f"invalid context.target_quotes: {filename}")
        for key in ("body", "full_with_quotes"):
            if not isinstance(target.get(key), str) or not target[key].strip():
                raise ValueError(f"invalid target.{key}: {filename}")
        if contract != {
            "stage_a": "target.body",
            "stage_b": "context+target",
            "stage_a_locked_before_stage_b": True,
            "future_replies_included": False,
            "ancestor_chain_included": False,
        }:
            raise ValueError(f"display contract mismatch: {filename}")

    def _record_path(self, case_id: str) -> Path:
        if case_id not in self._case_by_id:
            raise AnnotationError("unknown annotation case")
        return self.records_dir / f"{case_id}.json"

    def _load_record(self, case: dict[str, Any]) -> dict[str, Any] | None:
        path = self._record_path(case["case_id"])
        if not path.exists():
            return None
        if path.is_symlink():
            raise ValueError(f"record must not be a symlink: {path.name}")
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid annotation record {path.name}: {exc}") from exc
        self._validate_record(record, case)
        return record

    def _validate_existing_records(self) -> None:
        known_names = {f"{case['case_id']}.json" for case in self._cases}
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
            "sample_uid": case["view"]["ids"]["sample_uid"],
            "view_sha256": case["view_sha256"],
            "annotator": {
                "annotator_uid": self.annotator_uid,
                "role": "human",
                "annotation_mode": "blind",
            },
            "annotation_round": "calibration",
            "target_only": self._empty_decision(contextual=False),
            "contextual": self._empty_decision(contextual=True),
            "started_at": self.utc_now(),
            "completed_at": None,
        }

    @staticmethod
    def _empty_decision(*, contextual: bool) -> dict[str, Any]:
        decision: dict[str, Any] = {
            "status": "unlabeled",
            "primary_emotion": None,
            "other_emotion_text": None,
            "confidence": None,
            "note": None,
        }
        if contextual:
            decision.update(
                {
                    "sarcasm": None,
                    "mixed_emotion": None,
                    "context_sufficiency": None,
                }
            )
            decision = {
                "status": decision["status"],
                "primary_emotion": decision["primary_emotion"],
                "other_emotion_text": decision["other_emotion_text"],
                "confidence": decision["confidence"],
                "sarcasm": decision["sarcasm"],
                "mixed_emotion": decision["mixed_emotion"],
                "context_sufficiency": decision["context_sufficiency"],
                "note": decision["note"],
            }
        return decision

    def _validate_record(self, record: Any, case: dict[str, Any]) -> None:
        if not isinstance(record, dict):
            raise ValueError(f"record must be an object: {case['case_id']}")
        required_keys = {
            "schema_version",
            "protocol_id",
            "sample_uid",
            "view_sha256",
            "annotator",
            "annotation_round",
            "target_only",
            "contextual",
            "started_at",
            "completed_at",
        }
        if set(record) != required_keys:
            raise ValueError(f"record fields do not match V1: {case['case_id']}")
        if record["schema_version"] != RECORD_SCHEMA_VERSION:
            raise ValueError(f"record schema mismatch: {case['case_id']}")
        if record["protocol_id"] != PROTOCOL_ID:
            raise ValueError(f"record protocol mismatch: {case['case_id']}")
        if record["sample_uid"] != case["view"]["ids"]["sample_uid"]:
            raise ValueError(f"record sample mismatch: {case['case_id']}")
        if record["view_sha256"] != case["view_sha256"]:
            raise ValueError(f"record view hash mismatch: {case['case_id']}")
        if record.get("annotator") != {
            "annotator_uid": self.annotator_uid,
            "role": "human",
            "annotation_mode": "blind",
        }:
            raise ValueError(f"record annotator boundary mismatch: {case['case_id']}")
        if record.get("annotation_round") != "calibration":
            raise ValueError(f"record round mismatch: {case['case_id']}")
        if not isinstance(record.get("started_at"), str):
            raise ValueError(f"record started_at missing: {case['case_id']}")

        self._validate_stored_decision(record.get("target_only"), contextual=False)
        self._validate_stored_decision(record.get("contextual"), contextual=True)
        contextual_done = record["contextual"]["status"] != "unlabeled"
        if contextual_done != isinstance(record.get("completed_at"), str):
            raise ValueError(f"record completion state mismatch: {case['case_id']}")

    def _validate_stored_decision(self, decision: Any, *, contextual: bool) -> None:
        if not isinstance(decision, dict):
            raise ValueError("stored decision must be an object")
        expected = {
            "status",
            "primary_emotion",
            "other_emotion_text",
            "confidence",
            "note",
        }
        if contextual:
            expected.update({"sarcasm", "mixed_emotion", "context_sufficiency"})
        if set(decision) != expected:
            raise ValueError("stored decision fields do not match V1")
        if decision.get("status") == "unlabeled":
            if decision != self._empty_decision(contextual=contextual):
                raise ValueError("unlabeled decision contains non-null data")
            return
        self._normalize_submitted_decision(decision, contextual=contextual)

    @staticmethod
    def _single_line(value: Any, *, max_length: int, field: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise AnnotationError(f"{field} must be text")
        normalized = value.strip()
        if not normalized:
            return None
        if "\n" in normalized or "\r" in normalized:
            raise AnnotationError(f"{field} must be a single line")
        if len(normalized) > max_length:
            raise AnnotationError(f"{field} exceeds {max_length} characters")
        return normalized

    @staticmethod
    def _note(value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise AnnotationError("note must be text")
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 1000:
            raise AnnotationError("note exceeds 1000 characters")
        return normalized

    def _normalize_submitted_decision(
        self, payload: Any, *, contextual: bool
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise AnnotationError("decision payload must be an object")

        allowed = {
            "status",
            "primary_emotion",
            "other_emotion_text",
            "confidence",
            "note",
        }
        if contextual:
            allowed.update({"sarcasm", "mixed_emotion", "context_sufficiency"})
        if set(payload) - allowed:
            raise AnnotationError("decision payload contains unknown fields")

        status = payload.get("status")
        if status not in {"labeled", "unclear", "unusable"}:
            raise AnnotationError("status must be labeled, unclear or unusable")
        confidence = payload.get("confidence")
        if confidence not in CONFIDENCE_LEVELS:
            raise AnnotationError("confidence is required")

        primary = payload.get("primary_emotion")
        other_text = self._single_line(
            payload.get("other_emotion_text"),
            max_length=64,
            field="other_emotion_text",
        )
        if status == "labeled":
            if primary not in EMOTION_LABELS:
                raise AnnotationError("primary_emotion is required for labeled cases")
            if primary == "other_emotion":
                if other_text is None or not OTHER_EMOTION_RE.fullmatch(other_text):
                    raise AnnotationError(
                        "other_emotion_text must be a short atomic English name"
                    )
                other_text = other_text.lower()
            elif other_text is not None:
                raise AnnotationError(
                    "other_emotion_text is only allowed with other_emotion"
                )
        else:
            if primary is not None or other_text is not None:
                raise AnnotationError(
                    "unclear and unusable decisions cannot contain a primary emotion"
                )
            primary = None
            other_text = None

        note = self._note(payload.get("note"))
        if status == "unusable" and note is None:
            raise AnnotationError("unusable decisions require a note")

        decision: dict[str, Any] = {
            "status": status,
            "primary_emotion": primary,
            "other_emotion_text": other_text,
            "confidence": confidence,
            "note": note,
        }

        if contextual:
            sarcasm = payload.get("sarcasm")
            mixed_emotion = payload.get("mixed_emotion")
            context_sufficiency = payload.get("context_sufficiency")
            if status == "unusable":
                if (
                    sarcasm is not None
                    or mixed_emotion is not None
                    or context_sufficiency is not None
                ):
                    raise AnnotationError(
                        "unusable contextual decisions must leave diagnostics empty"
                    )
            else:
                if sarcasm not in SARCASM_VALUES:
                    raise AnnotationError("sarcasm decision is required")
                if not isinstance(mixed_emotion, bool):
                    raise AnnotationError("mixed_emotion must be true or false")
                if context_sufficiency not in CONTEXT_SUFFICIENCY_VALUES:
                    raise AnnotationError("context_sufficiency decision is required")
            decision = {
                "status": status,
                "primary_emotion": primary,
                "other_emotion_text": other_text,
                "confidence": confidence,
                "sarcasm": sarcasm,
                "mixed_emotion": mixed_emotion,
                "context_sufficiency": context_sufficiency,
                "note": note,
            }
        return decision

    def _atomic_write_record(self, case: dict[str, Any], record: dict[str, Any]) -> None:
        self._validate_record(record, case)
        destination = self._record_path(case["case_id"])
        if destination.is_symlink():
            raise ValueError(f"record must not be a symlink: {destination.name}")

        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{case['case_id']}.", suffix=".tmp", dir=self.records_dir
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
            "schema_version": "annotation-session-event-v1",
            "protocol_id": PROTOCOL_ID,
            "event": event,
            "session_uid": self._session_uid,
            "annotator_uid": self.annotator_uid,
            "timestamp": self.utc_now(),
            **fields,
        }
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        fd = os.open(path, flags, 0o600)
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
        stage_a_done = 0
        completed = 0
        unusable = 0
        for case in self._cases:
            record = self._load_record(case)
            if record is None:
                continue
            if record["target_only"]["status"] != "unlabeled":
                stage_a_done += 1
            if record["contextual"]["status"] != "unlabeled":
                completed += 1
                if record["contextual"]["status"] == "unusable":
                    unusable += 1
        return {
            "stage_a_done": stage_a_done,
            "completed": completed,
            "unusable": unusable,
        }

    def _next_incomplete(self) -> tuple[dict[str, Any], dict[str, Any] | None] | None:
        for case in self._cases:
            record = self._load_record(case)
            if record is None or record["contextual"]["status"] == "unlabeled":
                return case, record
        return None

    def _progress(self, case: dict[str, Any] | None = None) -> dict[str, Any]:
        counts = self._counts()
        return {
            **counts,
            "total": len(self._cases),
            "position": case["position"] if case else None,
            "session_completed": self._session_completed,
            "session_limit": self.session_limit,
        }

    def current(self) -> dict[str, Any]:
        with self._lock:
            self._ensure_session_started()
            counts = self._counts()
            if counts["unusable"] > QUALITY_STOP_UNUSABLE_COUNT:
                return {
                    "state": "quality_stop",
                    "reason": "More than six contextual cases are unusable; review the view exporter before continuing.",
                    "progress": self._progress(),
                }

            pending = self._next_incomplete()
            if pending is None:
                return {"state": "complete", "progress": self._progress()}
            if self._session_ended or self._session_completed >= self.session_limit:
                if not self._session_ended:
                    self.end_session(reason="continuous_limit_reached")
                return {
                    "state": "session_break",
                    "progress": self._progress(),
                }
            case, record = pending
            if record is None:
                record = self._new_record(case)
                self._atomic_write_record(case, record)

            common = {
                "state": "case",
                "case_id": case["case_id"],
                "progress": self._progress(case),
            }
            if record["target_only"]["status"] == "unlabeled":
                target_body = case["view"]["target"]["body"].replace(
                    "[[QUOTE]]", "[quoted text omitted]"
                )
                return {
                    **common,
                    "stage": "A",
                    "target_body": target_body,
                }

            context = case["view"]["context"]
            return {
                **common,
                "stage": "B",
                "stage_a_locked": True,
                "context": {
                    "discussion_title": context["discussion_title"],
                    "direct_parent_body": context["direct_parent_body"],
                    "target_quotes": context["target_quotes"],
                },
                "target_full_with_quotes": case["view"]["target"][
                    "full_with_quotes"
                ],
            }

    def _require_current_case(self, case_id: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        if self._session_ended or self._session_completed >= self.session_limit:
            raise AnnotationConflict("the current annotation session is closed")
        pending = self._next_incomplete()
        if pending is None:
            raise AnnotationConflict("all annotation cases are complete")
        case, record = pending
        if case_id != case["case_id"]:
            raise AnnotationConflict("the requested case is not the active case")
        if record is None:
            record = self._new_record(case)
            self._atomic_write_record(case, record)
        return case, record

    def submit_stage_a(self, case_id: Any, payload: Any) -> dict[str, Any]:
        with self._lock:
            case, record = self._require_current_case(case_id)
            if record["target_only"]["status"] != "unlabeled":
                raise AnnotationConflict("Stage A is already locked")
            record["target_only"] = self._normalize_submitted_decision(
                payload, contextual=False
            )
            self._atomic_write_record(case, record)
            self._append_session_event("stage_a_locked", case_id=case["case_id"])
            return self.current()

    def submit_stage_b(self, case_id: Any, payload: Any) -> dict[str, Any]:
        with self._lock:
            case, record = self._require_current_case(case_id)
            if record["target_only"]["status"] == "unlabeled":
                raise AnnotationConflict("Stage A must be locked before Stage B")
            if record["contextual"]["status"] != "unlabeled":
                raise AnnotationConflict("Stage B is already locked")
            record["contextual"] = self._normalize_submitted_decision(
                payload, contextual=True
            )
            record["completed_at"] = self.utc_now()
            self._atomic_write_record(case, record)
            self._session_completed += 1
            self._append_session_event("case_completed", case_id=case["case_id"])
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
            return {
                "state": "session_break",
                "progress": self._progress(),
            }

    def start_session(self) -> dict[str, Any]:
        with self._lock:
            if not self._session_ended:
                raise AnnotationConflict("the current session is still active")
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
