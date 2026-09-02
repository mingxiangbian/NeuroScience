"""Private SQLite job store; revoked jobs cannot accept late worker writes."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


ACTIVE = {"fetching", "snapshot_sealed", "inferencing", "aggregating"}
TERMINAL = {"completed", "completed_with_fallback", "failed", "cancelled"}


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


class QueueFull(ValueError):
    pass


class Store:
    def __init__(self, private_dir: Path, max_queue: int = 8):
        self.private_dir = Path(private_dir).absolute()
        if any(p.is_symlink() for p in (self.private_dir, *self.private_dir.parents)):
            raise ValueError("private_path_symlink")
        self.private_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.private_dir.chmod(0o700)
        os.umask(0o077)
        self.path = self.private_dir / "jobs.sqlite3"
        if self.path.is_symlink():
            raise ValueError("database_symlink")
        self.max_queue = max_queue
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, source TEXT NOT NULL,
                    mode TEXT NOT NULL, state TEXT NOT NULL, request TEXT NOT NULL,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL,
                    total_items INTEGER NOT NULL DEFAULT 0,
                    completed_items INTEGER NOT NULL DEFAULT 0,
                    error_code TEXT, progress TEXT NOT NULL DEFAULT '{}',
                    manifest TEXT, dashboard TEXT, snapshot_hash TEXT,
                    raw_expired INTEGER NOT NULL DEFAULT 0,
                    items_expired INTEGER NOT NULL DEFAULT 0,
                    replay_of TEXT
                );
                CREATE TABLE IF NOT EXISTS items (
                    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    ordinal INTEGER NOT NULL, record TEXT NOT NULL, result TEXT,
                    PRIMARY KEY(job_id,ordinal)
                );
            """)
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA secure_delete=ON")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise

    @staticmethod
    def _job(row, private=False):
        if row is None:
            return None
        out = dict(row)
        for key in ("request", "progress", "manifest", "dashboard"):
            out[key] = json.loads(out[key]) if out[key] is not None else None
        out["raw_expires_at"] = out["created_at"] + 7 * 86400
        out["items_expires_at"] = out["created_at"] + 30 * 86400
        out["aggregate_expires_at"] = out["created_at"] + 90 * 86400
        if not private:
            out.pop("request", None)
        return out

    def get(self, job_id, private=False):
        with self.connect() as db:
            return self._job(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone(), private)

    def list(self):
        with self.connect() as db:
            return [self._job(r) for r in db.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 100")]

    def create(self, request, records=None, manifest=None, replay_of=None):
        now = time.time()
        job_id = uuid.uuid4().hex
        # Upload content exists only in the sealed rows, not duplicated in request.
        saved_request = {k: v for k, v in request.items() if k not in {"upload", "records"}}
        with self.transaction() as db:
            queued = db.execute("SELECT count(*) FROM jobs WHERE state='queued'").fetchone()[0]
            if queued >= self.max_queue:
                raise QueueFull("queue_full")
            db.execute("INSERT INTO jobs (id,name,source,mode,state,request,created_at,updated_at,replay_of) VALUES (?,?,?,?,?,?,?,?,?)",
                       (job_id, request.get("name", "Untitled topic"), request["source"], request["mode"], "queued", dumps(saved_request), now, now, replay_of))
            if records is not None:
                self._insert_snapshot(db, job_id, records, manifest or {})
        return self.get(job_id)

    def _insert_snapshot(self, db, job_id, records, manifest):
        if len(records) > 500:
            raise ValueError("item_limit")
        encoded = [dumps(record) for record in records]
        fingerprint = hashlib.sha256(dumps(records).encode()).hexdigest()
        db.executemany("INSERT INTO items(job_id,ordinal,record) VALUES(?,?,?)", [(job_id, i, value) for i, value in enumerate(encoded)])
        db.execute("UPDATE jobs SET total_items=?,manifest=?,snapshot_hash=?,updated_at=? WHERE id=?", (len(records), dumps(manifest), fingerprint, time.time(), job_id))

    def claim(self):
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM jobs WHERE state IN ('fetching','snapshot_sealed','inferencing','aggregating','cancel_requested','deleting') LIMIT 1").fetchone():
                return None
            row = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY created_at LIMIT 1").fetchone()
            if row is None:
                return None
            state = "snapshot_sealed" if row["snapshot_hash"] else "fetching"
            db.execute("UPDATE jobs SET state=?,updated_at=? WHERE id=? AND state='queued'", (state, time.time(), row["id"]))
        return self.get(row["id"], private=True)

    def seal(self, job_id, records, manifest):
        with self.transaction() as db:
            row = db.execute("SELECT state,snapshot_hash FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None or row["state"] != "fetching":
                return False
            if row["snapshot_hash"]:
                raise ValueError("snapshot_already_sealed")
            self._insert_snapshot(db, job_id, records, manifest)
            db.execute("UPDATE jobs SET state='snapshot_sealed' WHERE id=?", (job_id,))
        return True

    def transition(self, job_id, expected, state, **fields):
        if not set(fields) <= {"error_code", "dashboard", "progress"}:
            raise ValueError("invalid_update")
        clauses = ["state=?", "updated_at=?"]
        values = [state, time.time()]
        for key, value in fields.items():
            clauses.append(f"{key}=?")
            values.append(dumps(value) if key != "error_code" else value)
        expected = [expected] if isinstance(expected, str) else list(expected)
        with self.transaction() as db:
            return db.execute(f"UPDATE jobs SET {','.join(clauses)} WHERE id=? AND state IN ({','.join('?' for _ in expected)})", values + [job_id] + expected).rowcount == 1

    def progress(self, job_id, progress):
        with self.connect() as db:
            db.execute("UPDATE jobs SET progress=?,updated_at=? WHERE id=? AND state IN ('fetching','snapshot_sealed','inferencing','aggregating')", (dumps(progress), time.time(), job_id))

    def cancelled(self, job_id):
        job = self.get(job_id)
        return job is None or job["state"] in {"cancel_requested", "cancelled", "deleting"}

    def cancel(self, job_id):
        self.transition(job_id, "queued", "cancelled")
        self.transition(job_id, ACTIVE, "cancel_requested")
        return self.get(job_id)

    def request_delete(self, job_id):
        with self.transaction() as db:
            row = db.execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                return "missing"
            if row["state"] in ACTIVE | {"cancel_requested", "deleting"}:
                db.execute("UPDATE jobs SET state='deleting',updated_at=? WHERE id=?", (time.time(), job_id))
                return "deleting"
            db.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        self.checkpoint()
        return "deleted"

    def finish_revocation(self, job_id):
        # Call only after the exact inference child has exited.
        with self.transaction() as db:
            db.execute("DELETE FROM jobs WHERE id=? AND state='deleting'", (job_id,))
            db.execute("UPDATE jobs SET state='cancelled',updated_at=? WHERE id=? AND state='cancel_requested'", (time.time(), job_id))
        self.checkpoint()

    def put_result(self, job_id, ordinal, result):
        with self.transaction() as db:
            row = db.execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None or row["state"] != "inferencing":
                return False
            changed = db.execute("UPDATE items SET result=? WHERE job_id=? AND ordinal=? AND result IS NULL", (dumps(result), job_id, ordinal)).rowcount
            if changed:
                db.execute("UPDATE jobs SET completed_items=completed_items+1,updated_at=? WHERE id=?", (time.time(), job_id))
            return bool(changed)

    def items(self, job_id, limit=500, offset=0, private=False):
        with self.connect() as db:
            rows = db.execute("SELECT ordinal,record,result FROM items WHERE job_id=? ORDER BY ordinal LIMIT ? OFFSET ?", (job_id, min(limit, 500), offset)).fetchall()
        output = []
        for row in rows:
            record = json.loads(row["record"])
            if not private:
                record = {key: value for key, value in record.items() if key not in {"source_payload_raw", "model_input_text", "model_input", "text", "author_id_hash"}}
                ids = [record.get(key) for key in ("thread_id", "source_object_id", "parent_object_id")]
                if (record.get("source") == "stackexchange" and record.get("site") == "stackoverflow"
                        and record.get("object_type") == "comment"
                        and all(isinstance(value, str) and value.isascii() and value.isdecimal() and value[0] != "0" for value in ids)):
                    record["recorded_source_url"] = record.get("source_url")
                    record["source_url"] = f"https://stackoverflow.com/questions/{ids[0]}#comment{ids[1]}_{ids[2]}"
            output.append({"ordinal": row["ordinal"], "record": record, "result": json.loads(row["result"]) if row["result"] else None})
        return output

    def replay(self, job_id):
        original = self.get(job_id, private=True)
        if original is None:
            raise KeyError(job_id)
        if not original["snapshot_hash"] or original["raw_expired"] or original["state"] not in TERMINAL:
            raise ValueError("snapshot_not_replayable")
        rows = self.items(job_id, private=True)
        return self.create(original["request"], [row["record"] for row in rows], original["manifest"], replay_of=job_id)

    def clear_raw(self, job_id):
        """Remove one terminal job's text without deleting metadata or predictions."""
        with self.transaction() as db:
            row = db.execute("SELECT state,request FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                return None
            if row["state"] not in TERMINAL:
                raise ValueError("job_not_terminal")
            raw_keys = {"source_payload_raw", "model_input_text", "model_input", "text", "display_text"}
            for item in db.execute("SELECT ordinal,record FROM items WHERE job_id=?", (job_id,)).fetchall():
                record = json.loads(item["record"])
                for key in raw_keys:
                    record.pop(key, None)
                db.execute("UPDATE items SET record=? WHERE job_id=? AND ordinal=?", (dumps(record), job_id, item["ordinal"]))
            request = json.loads(row["request"])
            for key in raw_keys | {"upload", "records", "content"}:
                request.pop(key, None)
            db.execute("UPDATE jobs SET request=?,raw_expired=1,updated_at=? WHERE id=?", (dumps(request), time.time(), job_id))
        self.checkpoint()
        return self.get(job_id)

    def recover_after_exclusive_lock(self):
        # The dispatcher lock is inherited by children. Holding it proves none survive.
        with self.transaction() as db:
            db.execute("DELETE FROM jobs WHERE state='deleting'")
            db.execute("UPDATE jobs SET state='failed',error_code='worker_interrupted',updated_at=? WHERE state IN ('fetching','snapshot_sealed','inferencing','aggregating','cancel_requested')", (time.time(),))
        self.checkpoint()

    def purge(self, now=None):
        from .core import aggregate

        now = time.time() if now is None else now
        counts = {"raw_redacted": 0, "items_removed": 0, "jobs_removed": 0}
        with self.transaction() as db:
            rows = db.execute("SELECT id,created_at,raw_expired,items_expired,dashboard,manifest,mode FROM jobs WHERE state IN ('completed','completed_with_fallback','failed','cancelled')").fetchall()
            for job in rows:
                age = now - job["created_at"]
                if age >= 90 * 86400:
                    db.execute("DELETE FROM jobs WHERE id=?", (job["id"],))
                    counts["jobs_removed"] += 1
                elif age >= 30 * 86400 and not job["items_expired"]:
                    if job["dashboard"] is None:
                        items = db.execute("SELECT record,result FROM items WHERE job_id=? ORDER BY ordinal", (job["id"],)).fetchall()
                        dashboard = aggregate(
                            [json.loads(item["record"]) for item in items],
                            [json.loads(item["result"]) if item["result"] else None for item in items],
                            json.loads(job["manifest"]) if job["manifest"] else {}, job["mode"],
                        )
                        db.execute("UPDATE jobs SET dashboard=? WHERE id=?", (dumps(dashboard), job["id"]))
                    db.execute("DELETE FROM items WHERE job_id=?", (job["id"],))
                    db.execute("UPDATE jobs SET request='{}',manifest=NULL,raw_expired=1,items_expired=1 WHERE id=?", (job["id"],))
                    counts["items_removed"] += 1
                elif age >= 7 * 86400 and not job["raw_expired"]:
                    for item in db.execute("SELECT ordinal,record FROM items WHERE job_id=?", (job["id"],)).fetchall():
                        record = json.loads(item["record"])
                        for key in ("source_payload_raw", "model_input_text", "model_input", "text", "display_text"):
                            record.pop(key, None)
                        db.execute("UPDATE items SET record=? WHERE job_id=? AND ordinal=?", (dumps(record), job["id"], item["ordinal"]))
                    db.execute("UPDATE jobs SET raw_expired=1 WHERE id=?", (job["id"],))
                    counts["raw_redacted"] += 1
        self.checkpoint()
        return counts

    def checkpoint(self):
        with self.connect() as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
