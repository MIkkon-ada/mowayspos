from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from scripts.ci_compose_business_smoke import run_smoke


class _SmokeHandler(BaseHTTPRequestHandler):
    initialized = False
    requests: list[tuple[str, str, str]] = []

    def log_message(self, *_args):
        return

    def _json(self, status: int, payload: dict, *, cookie: str = ""):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")

    def _record(self):
        self.requests.append((self.command, self.path, self.headers.get("Cookie", "")))

    def do_GET(self):
        self._record()
        path = urlparse(self.path).path
        if path == "/api/setup/status":
            return self._json(200, {"initialized": self.initialized})
        if path == "/api/auth/me":
            return self._json(200, {"username": "ci_smoke_admin"})
        if self.headers.get("Cookie") != "moways_ci_session=admin-session":
            return self._json(401, {"detail": "not_authenticated"})
        if path in {
            "/api/projects",
            "/api/projects/101",
            "/api/projects/101/capabilities",
            "/api/tasks",
            "/api/updates",
            "/api/confirmations/pending",
            "/api/meetings",
            "/api/issues",
            "/api/achievements",
        }:
            return self._json(200, {} if path.endswith("capabilities") else [])
        return self._json(404, {"detail": path})

    def do_POST(self):
        self._record()
        path = urlparse(self.path).path
        payload = self._body()
        if path == "/api/setup/init":
            type(self).initialized = True
            return self._json(200, {"ok": True})
        if path == "/api/auth/login":
            session = "admin-session" if payload["username"] == "ci_smoke_admin" else "member-session"
            return self._json(200, {"ok": True}, cookie=f"moways_ci_session={session}; Secure; HttpOnly")
        if path == "/api/accounts" and self.headers.get("Cookie") == "moways_ci_session=admin-session":
            return self._json(200, {"id": 2})
        if path == "/api/projects":
            if self.headers.get("Cookie") == "moways_ci_session=member-session":
                return self._json(403, {"detail": "permission denied"})
            if self.headers.get("Cookie") == "moways_ci_session=admin-session":
                return self._json(200, {"id": 101})
        return self._json(401, {"detail": "not_authenticated"})


def test_compose_smoke_uses_proxy_authenticates_and_checks_member_denial():
    _SmokeHandler.initialized = False
    _SmokeHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SmokeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    events: list[str] = []
    try:
        run_smoke(f"http://127.0.0.1:{server.server_port}", emit=events.append)
    finally:
        server.shutdown()
        thread.join()

    paths = [(method, urlparse(path).path) for method, path, _cookie in _SmokeHandler.requests]
    assert ("POST", "/api/setup/init") in paths
    assert ("POST", "/api/auth/login") in paths
    assert ("GET", "/api/auth/me") in paths
    assert ("GET", "/api/projects/101") in paths
    assert ("GET", "/api/tasks") in paths
    assert ("GET", "/api/updates") in paths
    assert ("GET", "/api/confirmations/pending") in paths
    assert ("GET", "/api/meetings") in paths
    assert ("GET", "/api/issues") in paths
    assert ("GET", "/api/achievements") in paths
    assert any(method == "POST" and path == "/api/projects" and cookie == "moways_ci_session=member-session" for method, path, cookie in _SmokeHandler.requests)
    assert all("session" not in event and "password" not in event for event in events)
