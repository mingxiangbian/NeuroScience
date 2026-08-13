#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hmac
import json
import secrets
import sys
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from .core import (
        AdjudicationConflict,
        AdjudicationError,
        BlindAdjudicationStore,
        CASE_SCHEMA_VERSION,
        DEFAULT_ADJUDICATOR_UID,
        PROTOCOL_ID,
        canonical_case_sha256,
    )
except ImportError:
    from core import (  # type: ignore[no-redef]
        AdjudicationConflict,
        AdjudicationError,
        BlindAdjudicationStore,
        CASE_SCHEMA_VERSION,
        DEFAULT_ADJUDICATOR_UID,
        PROTOCOL_ID,
        canonical_case_sha256,
    )


HOST = "127.0.0.1"
DEFAULT_PORT = 8766
MAX_REQUEST_BYTES = 24_576
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


class LocalAdjudicationServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        *,
        store: BlindAdjudicationStore,
        static_dir: Path,
        csrf_token: str,
    ) -> None:
        self.store = store
        self.static_dir = static_dir
        self.csrf_token = csrf_token
        super().__init__(address, handler)


class AdjudicationRequestHandler(BaseHTTPRequestHandler):
    server: LocalAdjudicationServer
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        if not self._valid_host():
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "invalid local host"})
            return
        path = urlsplit(self.path).path
        if path == "/api/current":
            payload = self.server.store.current()
            payload["csrf_token"] = self.server.csrf_token
            payload["dataset_mode"] = self.server.store.dataset_mode
            self._send_json(HTTPStatus.OK, payload)
            return
        if path == "/favicon.ico":
            self._send_empty(HTTPStatus.NO_CONTENT)
            return
        static_entry = STATIC_FILES.get(path)
        if static_entry is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        filename, content_type = static_entry
        data = (self.server.static_dir / filename).read_bytes()
        self._send_bytes(HTTPStatus.OK, data, content_type)

    def do_POST(self) -> None:
        if not self._valid_host() or not self._valid_origin():
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "invalid local origin"})
            return
        supplied_token = self.headers.get("X-Adjudication-Token", "")
        if not hmac.compare_digest(supplied_token, self.server.csrf_token):
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "invalid session token"})
            return

        path = urlsplit(self.path).path
        try:
            payload = self._read_json()
            if path == "/api/phase-1":
                response = self.server.store.submit_phase_1(
                    payload.get("case_id"), payload.get("judgment")
                )
            elif path == "/api/phase-2":
                response = self.server.store.submit_phase_2(
                    payload.get("case_id"), payload.get("judgment")
                )
            elif path == "/api/session/end":
                response = self.server.store.end_session()
            elif path == "/api/session/start":
                response = self.server.store.start_session()
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
        except AdjudicationConflict as exc:
            self._send_json(exc.status_code, {"error": str(exc)})
            return
        except AdjudicationError as exc:
            self._send_json(exc.status_code, {"error": str(exc)})
            return
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"invalid JSON: {exc}"})
            return

        response["csrf_token"] = self.server.csrf_token
        response["dataset_mode"] = self.server.store.dataset_mode
        self._send_json(HTTPStatus.OK, response)

    def do_HEAD(self) -> None:
        path = urlsplit(self.path).path
        if not self._valid_host() or path not in STATIC_FILES:
            self._send_empty(HTTPStatus.NOT_FOUND)
            return
        _, content_type = STATIC_FILES[path]
        self.send_response(HTTPStatus.OK)
        self._send_security_headers(content_type)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self._send_empty(HTTPStatus.METHOD_NOT_ALLOWED)

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise AdjudicationError("Content-Length is required")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise AdjudicationError("invalid Content-Length") from exc
        if length < 0 or length > MAX_REQUEST_BYTES:
            raise AdjudicationError("request body is too large")
        data = self.rfile.read(length)
        payload = json.loads(data.decode("utf-8"))
        if not isinstance(payload, dict):
            raise AdjudicationError("request body must be an object")
        return payload

    def _valid_host(self) -> bool:
        host = self.headers.get("Host", "")
        hostname = host.rsplit(":", 1)[0].strip("[]").lower()
        return hostname in {"127.0.0.1", "localhost"}

    def _valid_origin(self) -> bool:
        origin = self.headers.get("Origin", "")
        port = self.server.server_address[1]
        return origin in {
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        }

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        self._send_bytes(status, data, "application/json; charset=utf-8")

    def _send_empty(self, status: int) -> None:
        self.send_response(status)
        self._send_security_headers("text/plain; charset=utf-8")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_bytes(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self._send_security_headers(content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_security_headers(self, content_type: str) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'none'; connect-src 'self'; "
            "font-src 'none'; form-action 'self'; frame-ancestors 'none'; "
            "img-src 'self' data:; object-src 'none'; script-src 'self'; "
            "style-src 'self'",
        )

    def log_message(self, format_string: str, *args: Any) -> None:
        sys.stderr.write(
            f"[{self.log_date_time_string()}] {self.command} "
            f"{urlsplit(self.path).path} {args[1] if len(args) > 1 else ''}\n"
        )


def production_paths() -> tuple[Path, Path, Path]:
    adjudicator_dir = Path(__file__).resolve().parent
    project_root = adjudicator_dir.parents[3]
    private_root = (
        project_root
        / "data/iac2/annotations/pilot-v1/adjudication/diagnostic-v1"
    )
    return (
        private_root / "bundle.jsonl",
        private_root / "records",
        adjudicator_dir / "static",
    )


def build_demo_store(
    adjudicator_uid: str,
) -> tuple[BlindAdjudicationStore, tempfile.TemporaryDirectory[str]]:
    temporary = tempfile.TemporaryDirectory(prefix="forum-adjudication-demo-")
    root = Path(temporary.name)
    case: dict[str, Any] = {
        "schema_version": CASE_SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "blind_case_id": "001",
        "content": {
            "discussion_title": "Synthetic discussion for interface testing",
            "direct_parent_body": "The release removed a feature I use every day.",
            "target_quotes": ["The release removed a feature"],
            "target_full_with_quotes": (
                "The release removed a feature. I have explained this three times, "
                "and nobody seems to listen."
            ),
        },
        "candidates": [
            {
                "alias": "candidate_a",
                "decision": {
                    "status": "labeled",
                    "primary_emotion": "frustration",
                    "other_emotion_text": None,
                },
            },
            {
                "alias": "candidate_b",
                "decision": {
                    "status": "labeled",
                    "primary_emotion": "anger",
                    "other_emotion_text": None,
                },
            },
            {
                "alias": "candidate_c",
                "decision": {
                    "status": "unclear",
                    "primary_emotion": None,
                    "other_emotion_text": None,
                },
            },
        ],
    }
    case["case_sha256"] = canonical_case_sha256(case)
    bundle = root / "bundle.jsonl"
    bundle.write_text(json.dumps(case, ensure_ascii=False) + "\n", encoding="utf-8")
    os_mode = 0o600
    bundle.chmod(os_mode)
    store = BlindAdjudicationStore(
        bundle,
        root / "records",
        adjudicator_uid=adjudicator_uid,
        expected_total=1,
        session_limit=20,
        dataset_mode="synthetic",
    )
    return store, temporary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the private source-blind diagnostic adjudicator locally."
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--adjudicator-uid", default=DEFAULT_ADJUDICATOR_UID)
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use one synthetic case in a temporary private directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if args.demo:
        store, temporary = build_demo_store(args.adjudicator_uid)
        static_dir = Path(__file__).resolve().parent / "static"
    else:
        bundle_path, records_dir, static_dir = production_paths()
        store = BlindAdjudicationStore(
            bundle_path,
            records_dir,
            adjudicator_uid=args.adjudicator_uid,
            expected_total=40,
            session_limit=20,
            dataset_mode="private",
        )

    server = LocalAdjudicationServer(
        (HOST, args.port),
        AdjudicationRequestHandler,
        store=store,
        static_dir=static_dir,
        csrf_token=secrets.token_urlsafe(32),
    )
    url = f"http://{HOST}:{server.server_address[1]}"
    print(f"Forum emotion blind adjudicator: {url}")
    print(f"Dataset mode: {store.dataset_mode}; network binding: {HOST} only")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        store.close()
        server.server_close()
        if temporary is not None:
            temporary.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
