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
    from .core import AnnotationConflict, AnnotationError, AnnotationStore
except ImportError:
    from core import AnnotationConflict, AnnotationError, AnnotationStore


HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_REQUEST_BYTES = 16_384
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


class LocalAnnotationServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        *,
        store: AnnotationStore,
        static_dir: Path,
        csrf_token: str,
    ) -> None:
        self.store = store
        self.static_dir = static_dir
        self.csrf_token = csrf_token
        super().__init__(address, handler)


class AnnotationRequestHandler(BaseHTTPRequestHandler):
    server: LocalAnnotationServer
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
        supplied_token = self.headers.get("X-Annotation-Token", "")
        if not hmac.compare_digest(supplied_token, self.server.csrf_token):
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "invalid session token"})
            return

        path = urlsplit(self.path).path
        try:
            payload = self._read_json()
            if path == "/api/stage-a":
                response = self.server.store.submit_stage_a(
                    payload.get("case_id"), payload.get("decision")
                )
            elif path == "/api/stage-b":
                response = self.server.store.submit_stage_b(
                    payload.get("case_id"), payload.get("decision")
                )
            elif path == "/api/session/end":
                response = self.server.store.end_session()
            elif path == "/api/session/start":
                response = self.server.store.start_session()
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
        except AnnotationConflict as exc:
            self._send_json(exc.status_code, {"error": str(exc)})
            return
        except AnnotationError as exc:
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
            raise AnnotationError("Content-Length is required")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise AnnotationError("invalid Content-Length") from exc
        if length < 0 or length > MAX_REQUEST_BYTES:
            raise AnnotationError("request body is too large")
        data = self.rfile.read(length)
        payload = json.loads(data.decode("utf-8"))
        if not isinstance(payload, dict):
            raise AnnotationError("request body must be an object")
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
    annotator_dir = Path(__file__).resolve().parent
    project_root = annotator_dir.parents[3]
    private_root = project_root / "data/iac2/annotations/pilot-v1"
    return (
        private_root / "views",
        private_root / "records/human-pass-1",
        annotator_dir / "static",
    )


def build_demo_store(annotator_uid: str) -> tuple[AnnotationStore, tempfile.TemporaryDirectory[str]]:
    annotator_dir = Path(__file__).resolve().parent
    fixture = annotator_dir.parent / "fixtures/annotation-view-v1.synthetic.json"
    temporary = tempfile.TemporaryDirectory(prefix="forum-annotation-demo-")
    root = Path(temporary.name)
    views_dir = root / "views"
    views_dir.mkdir(mode=0o700)
    (views_dir / "0001.json").write_text(
        fixture.read_text(encoding="utf-8"), encoding="utf-8"
    )
    store = AnnotationStore(
        views_dir,
        root / "records",
        annotator_uid=annotator_uid,
        expected_total=1,
        session_limit=40,
        dataset_mode="synthetic",
    )
    return store, temporary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the private two-stage forum emotion annotator locally."
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--annotator-uid", default="ann_primary_human")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use the synthetic fixture and a temporary record directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if args.demo:
        store, temporary = build_demo_store(args.annotator_uid)
        static_dir = Path(__file__).resolve().parent / "static"
    else:
        views_dir, records_dir, static_dir = production_paths()
        store = AnnotationStore(
            views_dir,
            records_dir,
            annotator_uid=args.annotator_uid,
            expected_total=120,
            dataset_mode="private",
        )

    server = LocalAnnotationServer(
        (HOST, args.port),
        AnnotationRequestHandler,
        store=store,
        static_dir=static_dir,
        csrf_token=secrets.token_urlsafe(32),
    )
    url = f"http://{HOST}:{server.server_address[1]}"
    print(f"Forum emotion annotator: {url}")
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
