from __future__ import annotations

import argparse
import json
from http.cookies import SimpleCookie
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class SmokeClient:
    def __init__(self, base_url: str, emit=print):
        self.base_url = base_url.rstrip("/")
        self.emit = emit

    def request(self, method: str, path: str, *, body: dict | None = None, session: str = "", expected_status: int = 200):
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if session:
            headers["Cookie"] = session
        request = Request(f"{self.base_url}{path}", data=payload, headers=headers, method=method)
        try:
            with urlopen(request, timeout=15) as response:
                status = response.status
                response_body = response.read()
                set_cookie = response.headers.get("Set-Cookie", "")
        except HTTPError as error:
            status = error.code
            response_body = error.read()
            set_cookie = ""
        try:
            data = json.loads(response_body or b"{}")
        except json.JSONDecodeError as error:
            raise RuntimeError(f"{method} {path} returned invalid JSON") from error
        if status != expected_status:
            raise RuntimeError(f"{method} {path} returned {status}, expected {expected_status}")
        self.emit(f"smoke ok: {method} {path} {status}")
        return data, set_cookie

    def login(self, username: str, password: str) -> str:
        _data, set_cookie = self.request("POST", "/api/auth/login", body={"username": username, "password": password})
        cookie = SimpleCookie()
        cookie.load(set_cookie)
        if "moways_ci_session" not in cookie:
            raise RuntimeError("login response omitted the CI session cookie")
        return f"moways_ci_session={cookie['moways_ci_session'].value}"


def run_smoke(base_url: str, *, emit=print) -> None:
    client = SmokeClient(base_url, emit=emit)
    status, _ = client.request("GET", "/api/setup/status")
    if status.get("initialized"):
        raise RuntimeError("CI Compose database must be uninitialized before smoke setup")

    admin_password = "CiSmokeAdminPass123!"
    member_password = "CiSmokeMemberPass123!"
    client.request("POST", "/api/setup/init", body={"username": "ci_smoke_admin", "password": admin_password})
    status, _ = client.request("GET", "/api/setup/status")
    if status != {"initialized": True}:
        raise RuntimeError("CI setup did not initialize the disposable database")
    admin_session = client.login("ci_smoke_admin", admin_password)
    client.request("GET", "/api/auth/me", session=admin_session)
    client.request(
        "POST",
        "/api/accounts",
        session=admin_session,
        body={"username": "ci_smoke_member", "password": member_password, "must_change_password": False},
    )
    project, _ = client.request("POST", "/api/projects", session=admin_session, body={"name": "CI Compose Business Smoke"})
    project_id = project.get("id")
    if not isinstance(project_id, int) or project_id <= 0:
        raise RuntimeError("project creation omitted a positive id")

    client.request("GET", f"/api/projects/{project_id}", session=admin_session)
    client.request("GET", f"/api/projects/{project_id}/capabilities", session=admin_session)
    for path in (
        f"/api/tasks?project_id={project_id}",
        f"/api/updates?project_id={project_id}",
        "/api/confirmations/pending",
        f"/api/meetings?project_id={project_id}",
        f"/api/issues?project_id={project_id}",
        f"/api/achievements?project_id={project_id}",
        "/api/projects?include_archived=true",
    ):
        client.request("GET", path, session=admin_session)

    member_session = client.login("ci_smoke_member", member_password)
    client.request("POST", "/api/projects", session=member_session, body={"name": "Denied CI Smoke Project"}, expected_status=403)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    run_smoke(args.base_url)


if __name__ == "__main__":
    main()
