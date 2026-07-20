"""HOTFIX-PROD-AUTH-COOKIE-NAME: session cookie name 不硬编码测试。

验证 get_current_user_name() 使用运行时配置的 Cookie 名，
而非硬编码 "bowei_session"。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------
# 每个子进程隔离环境，各自创建临时 SQLite 并运行 API 测试。
# --------------------------------------------------------------------------

_LOGIN_AND_VERIFY = r"""
import os, sys

expected_cookie = os.environ.get("SESSION_COOKIE_NAME", "bowei_session")

from app.database import Base, engine, SessionLocal
from app import models
from app.auth import hash_password

Base.metadata.create_all(bind=engine)

db = SessionLocal()
person = models.Person(id=1, name="testuser", system_role="company_ceo", is_active=True)
db.add(person)
account = models.Account(
    id=1,
    username="testuser",
    password_hash=hash_password("testpass123"),
    person_id=1,
    status="active",
    is_tech_admin=True,
)
db.add(account)
project = models.Project(id=1, name="TestProject", status="active")
db.add(project)
db.add(models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="testuser", role="project_ceo"))
db.commit()
db.close()

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

# 1 ── 登录响应 Cookie 名正确 ──────────────────────────────────
resp = client.post("/api/auth/login", json={"username": "testuser", "password": "testpass123"})
assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
assert resp.json()["ok"] is True
cookies = dict(resp.cookies)
assert expected_cookie in cookies, (
    f"Expected cookie '{expected_cookie}' not in {list(cookies.keys())}, "
    f"Set-Cookie header: {resp.headers.get('set-cookie', 'N/A')}"
)
token = cookies[expected_cookie]
print("STEP1_LOGIN_COOKIE_OK")

# 2 ── /api/auth/me 用该 Cookie 返回 200 ───────────────────────
resp2 = client.get("/api/auth/me", cookies={expected_cookie: token})
assert resp2.status_code == 200, f"/api/auth/me: {resp2.status_code} {resp2.text}"
data2 = resp2.json()
assert data2.get("username") == "testuser"
print("STEP2_AUTH_ME_OK")

# 3 ── 受保护接口 (依赖 get_current_user_name()) 返回 200 ──────
resp3 = client.get(
    "/api/confirmations/counts?scope=confirm_center",
    cookies={expected_cookie: token},
)
assert resp3.status_code == 200, f"Protected endpoint: {resp3.status_code} {resp3.text}"
print("STEP3_PROTECTED_OK")

# 4 ── 错误 Cookie 名返回 401 ──────────────────────────────────
# 重要：新 TestClient 避免旧 client 的 cookie jar 把正确 cookie 也带上
client4 = TestClient(app)
resp4 = client4.get("/api/auth/me", cookies={"not_the_right_name": token})
assert resp4.status_code == 401, f"Wrong cookie name: {resp4.status_code} {resp4.text}"
print("STEP4_WRONG_COOKIE_401")

print("ALL_PASSED")
"""


def _run(test_script: str, tmp_path: Path, extra_env: dict | None = None) -> subprocess.CompletedProcess[str]:
    database_path = (tmp_path / "session-cookie-test.db").resolve()
    env = os.environ.copy()
    env.setdefault("APP_ENV", "test")
    env["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    env["ALLOW_LEGACY_PASSWORD_LOGIN"] = "false"
    # 通过环境变量传入允许 origin，避免 CORS 安全拦截
    env.setdefault("FRONTEND_ORIGIN", "")
    if extra_env:
        env.update(extra_env)

    return subprocess.run(
        [sys.executable, "-c", test_script],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


# =========================================================================
# 测试用例
# =========================================================================


def test_custom_cookie_name_login_sets_correct_cookie(tmp_path: Path):
    """自定义 SESSION_COOKIE_NAME 时，登录响应设置正确的 Cookie。"""
    result = _run(_LOGIN_AND_VERIFY, tmp_path, {"SESSION_COOKIE_NAME": "moways_session"})
    assert result.returncode == 0, _error_report(result)
    assert "STEP1_LOGIN_COOKIE_OK" in result.stdout
    assert "ALL_PASSED" in result.stdout


def test_custom_cookie_name_auth_me_200(tmp_path: Path):
    """使用自定义 Cookie 名请求 /api/auth/me 返回 200。"""
    result = _run(_LOGIN_AND_VERIFY, tmp_path, {"SESSION_COOKIE_NAME": "moways_session"})
    assert result.returncode == 0, _error_report(result)
    assert "STEP2_AUTH_ME_OK" in result.stdout
    assert "ALL_PASSED" in result.stdout


def test_custom_cookie_name_protected_endpoint_not_401(tmp_path: Path):
    """使用自定义 Cookie 名调用受保护接口不再因 Cookie 名硬编码返回 401。"""
    result = _run(_LOGIN_AND_VERIFY, tmp_path, {"SESSION_COOKIE_NAME": "moways_session"})
    assert result.returncode == 0, _error_report(result)
    assert "STEP3_PROTECTED_OK" in result.stdout
    assert "ALL_PASSED" in result.stdout


def test_wrong_cookie_name_returns_401(tmp_path: Path):
    """错误 Cookie 名仍返回 401。"""
    result = _run(_LOGIN_AND_VERIFY, tmp_path, {"SESSION_COOKIE_NAME": "moways_session"})
    assert result.returncode == 0, _error_report(result)
    assert "STEP4_WRONG_COOKIE_401" in result.stdout
    assert "ALL_PASSED" in result.stdout


def test_default_cookie_name_unchanged(tmp_path: Path):
    """不设置 SESSION_COOKIE_NAME 时，默认 "bowei_session" 行为不变。"""
    result = _run(_LOGIN_AND_VERIFY, tmp_path)
    assert result.returncode == 0, _error_report(result)
    assert "ALL_PASSED" in result.stdout


def test_different_custom_name_production_scenario(tmp_path: Path):
    """生产场景：SESSION_COOKIE_NAME=moways_session，完整流程不报错。"""
    result = _run(_LOGIN_AND_VERIFY, tmp_path, {"SESSION_COOKIE_NAME": "moways_session"})
    assert result.returncode == 0, _error_report(result)
    for step in (
        "STEP1_LOGIN_COOKIE_OK",
        "STEP2_AUTH_ME_OK",
        "STEP3_PROTECTED_OK",
        "STEP4_WRONG_COOKIE_401",
    ):
        assert step in result.stdout, f"Missing: {step}\n{_error_report(result)}"
    assert "ALL_PASSED" in result.stdout


# =========================================================================
# helpers
# =========================================================================


def _error_report(result: subprocess.CompletedProcess[str]) -> str:
    return f"STDERR:\n{result.stderr}\n\nSTDOUT:\n{result.stdout}"
