from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Iterator
from urllib.parse import urlsplit


class _RecordingHandler(BaseHTTPRequestHandler):
    """Records every request and answers with the body the server was given."""

    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 - the name is the HTTP verb
        self._respond()

    def do_POST(self) -> None:  # noqa: N802
        self._respond()

    def do_PUT(self) -> None:  # noqa: N802
        self._respond()

    def do_PATCH(self) -> None:  # noqa: N802
        self._respond()

    def do_DELETE(self) -> None:  # noqa: N802
        self._respond()

    def _respond(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        parsed = urlsplit(self.path)
        request = {
            "method": self.command,
            "path": parsed.path,
            "query": parsed.query,
            "headers": {key.lower(): value for key, value in self.headers.items()},
            "body": raw.decode("utf-8"),
        }
        self.server.requests.append(request)  # type: ignore[attr-defined]
        responder: Callable[[dict[str, Any]], str] = self.server.responder  # type: ignore[attr-defined]
        body = responder(request).encode("utf-8")
        self.send_response(self.server.status)  # type: ignore[attr-defined]
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:
        """Keep the test output clean."""


@contextmanager
def serve(
    body: str | Callable[[dict[str, Any]], str], status: int = 200
) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """A recording HTTP server on a loopback ephemeral port.

    `body` is either the fixed payload every response carries or a function of
    the recorded request.
    """
    responder = body if callable(body) else (lambda _request: body)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _RecordingHandler)
    server.responder = responder  # type: ignore[attr-defined]
    server.status = status  # type: ignore[attr-defined]
    server.requests = []  # type: ignore[attr-defined]
    # A short poll interval keeps shutdown() prompt; the default is half a second
    # per server, which adds up across a suite.
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield f"http://{host}:{port}", server.requests  # type: ignore[attr-defined]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def envelope(data: Any) -> str:
    return json.dumps({"code": 0, "message": "ok", "data": data}, ensure_ascii=False)
