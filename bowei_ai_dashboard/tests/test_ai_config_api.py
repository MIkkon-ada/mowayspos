from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEST_FERNET_KEY = "m6F5dBXMRy1ZOQ4Dv_rwuPhtchxZzTCBuRUg-hxeF6U="

_SCRIPT = r'''
from app import models
from app.auth import hash_password
from app.database import Base, SessionLocal, engine

Base.metadata.create_all(bind=engine)
db = SessionLocal()
person = models.Person(id=1, name="admin", system_role="normal_member", is_active=True)
admin = models.Account(id=1, username="admin", password_hash=hash_password("testpass123"), person_id=1, status="active", is_tech_admin=True)
member_person = models.Person(id=2, name="member", system_role="normal_member", is_active=True)
member = models.Account(id=2, username="member", password_hash=hash_password("testpass123"), person_id=2, status="active", is_tech_admin=False)
db.add_all([person, admin, member_person, member]); db.commit(); db.close()

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
admin_login = client.post("/api/auth/login", json={"username":"admin", "password":"testpass123"})
member_login = client.post("/api/auth/login", json={"username":"member", "password":"testpass123"})
assert admin_login.status_code == 200 and member_login.status_code == 200
cookie_name = next(iter(admin_login.cookies.keys()))
admin_cookie = {cookie_name: admin_login.cookies[cookie_name]}
member_cookie = {cookie_name: member_login.cookies[cookie_name]}

assert client.get("/api/ai-config/models", cookies=member_cookie).status_code == 403
created = client.post("/api/ai-config/models", cookies=admin_cookie, json={
    "code":"deepseek-chat-primary", "display_name":"DeepSeek", "provider":"deepseek",
    "model_name":"deepseek-chat", "model_type":"chat", "base_url":"https://api.deepseek.com",
    "config":{}, "enabled":True, "source":"custom",
})
assert created.status_code == 201, created.text
model_id = created.json()["id"]
saved = client.put(f"/api/ai-config/models/{model_id}/credentials", cookies=admin_cookie, json={"api_key":"never-return-this"})
assert saved.status_code == 200, saved.text
listed = client.get("/api/ai-config/models", cookies=admin_cookie)
assert listed.status_code == 200
assert listed.json()[0]["credential_configured"] is True
assert "never-return-this" not in listed.text
from app.ai.adapters import DefaultAIAdapters
from app.ai.contracts import AIUpstreamError

def fail_with_auth(*args, **kwargs):
    raise AIUpstreamError("AI_UPSTREAM_AUTH", retryable=False)

DefaultAIAdapters.complete_chat = fail_with_auth
auth_test = client.post(f"/api/ai-config/models/{model_id}/test", cookies=admin_cookie, json={})
assert auth_test.status_code == 200, auth_test.text
assert auth_test.json() == {
    "ok": False,
    "code": "AI_UPSTREAM_AUTH",
    "message": "API Key 无效或没有调用权限，请检查后重试",
}

def fail_with_bad_request(*args, **kwargs):
    raise AIUpstreamError("AI_UPSTREAM_BAD_REQUEST", retryable=False)

DefaultAIAdapters.complete_chat = fail_with_bad_request
bad_request_test = client.post(f"/api/ai-config/models/{model_id}/test", cookies=admin_cookie, json={})
assert bad_request_test.status_code == 200, bad_request_test.text
assert bad_request_test.json() == {
    "ok": False,
    "code": "AI_UPSTREAM_BAD_REQUEST",
    "message": "模型名称或请求参数无效，请核对模型标识",
}
assert "never-return-this" not in auth_test.text + bad_request_test.text
wrong_type = client.put("/api/ai-config/policies/speech.realtime", cookies=admin_cookie, json={
    "primary_model_id": model_id, "fallback_model_ids":[], "timeout_seconds":30, "max_attempts":1, "enabled":True,
})
assert wrong_type.status_code == 422, wrong_type.text
print("ALL_PASSED")
'''


def test_ai_config_api_is_admin_only_and_never_returns_credentials(tmp_path: Path):
    database = tmp_path / "ai-config-api.db"
    environment = os.environ.copy()
    environment.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": f"sqlite:///{database.as_posix()}",
            "PROTECTED_DATABASE_PATHS": str((BACKEND_ROOT / "bowei_ai_dashboard.db").resolve()),
            "AI_CONFIG_ENCRYPTION_KEY": TEST_FERNET_KEY,
            "PYTHONPATH": str(BACKEND_ROOT),
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ALL_PASSED" in result.stdout
