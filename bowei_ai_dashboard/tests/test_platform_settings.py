from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]

_API_SCRIPT = r'''
from app import models
from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.main import app
from fastapi.testclient import TestClient

Base.metadata.create_all(bind=engine)
db = SessionLocal()
db.add_all([
    models.Person(id=1, name="admin", system_role="normal_member", is_active=True),
    models.Person(id=2, name="member", system_role="normal_member", is_active=True),
    models.Account(id=1, username="admin", password_hash=hash_password("testpass123"), person_id=1, status="active", is_tech_admin=True),
    models.Account(id=2, username="member", password_hash=hash_password("testpass123"), person_id=2, status="active", is_tech_admin=False),
])
db.commit()
db.close()

client = TestClient(app)
admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "testpass123"})
member_login = client.post("/api/auth/login", json={"username": "member", "password": "testpass123"})
assert admin_login.status_code == 200
assert member_login.status_code == 200
cookie_name = next(iter(admin_login.cookies.keys()))
admin_cookie = {cookie_name: admin_login.cookies[cookie_name]}
member_cookie = {cookie_name: member_login.cookies[cookie_name]}

configured = client.put("/api/platform-settings", cookies=admin_cookie, json={"logo_url": "/brand.png"})
assert configured.status_code == 200, configured.text
member_read = client.get("/api/platform-settings", cookies=member_cookie)
assert member_read.status_code == 200, member_read.text
assert member_read.json()["logo_url"] == "/brand.png"
assert client.put("/api/platform-settings", cookies=member_cookie, json={"logo_url": "/other.png"}).status_code == 403
print("ALL_PASSED")
'''


def test_retired_confidence_setting_is_removed_from_platform_payloads():
    from app.routers.platform_settings import _without_retired_settings

    source = {"platform_name": "测试平台", "confidence": 75}

    assert _without_retired_settings(source) == {"platform_name": "测试平台"}
    assert source["confidence"] == 75


def test_platform_settings_are_readable_by_members_but_writable_only_by_tech_admin(tmp_path: Path):
    database = tmp_path / "platform-settings-api.db"
    environment = os.environ.copy()
    environment.update({
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite:///{database.as_posix()}",
        "PROTECTED_DATABASE_PATHS": str((BACKEND_ROOT / "bowei_ai_dashboard.db").resolve()),
        "PYTHONPATH": str(BACKEND_ROOT),
    })

    result = subprocess.run(
        [sys.executable, "-c", _API_SCRIPT],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "ALL_PASSED" in result.stdout
