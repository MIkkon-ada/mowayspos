from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_project_init_attachment_signatures_are_checked(tmp_path):
    script = r'''
from pathlib import Path
import zipfile
from fastapi import HTTPException
from app.routers.project_init_ai import _validate_payload

def check(name, payload, expected):
    path = Path("PAYLOAD_DIR") / name
    path.write_bytes(payload)
    try:
        _validate_payload(path, name, path.suffix.lower())
    except HTTPException as exc:
        assert exc.status_code == 422
        assert expected == "reject"
    else:
        assert expected == "accept"

check("ok.pdf", b"%PDF-1.7\n", "accept")
check("bad.pdf", b"not a pdf", "reject")
check("ok.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "accept")
check("ok.xls", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "accept")
check("bad.xls", b"not ole", "reject")
check("bad.txt", b"contains\x00binary", "reject")
for name, member in (("ok.docx", "word/document.xml"), ("ok.xlsx", "xl/workbook.xml")):
    path = Path("PAYLOAD_DIR") / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member, "<root/>")
    _validate_payload(path, name, path.suffix.lower())
for name, member in (("bad.docx", "xl/workbook.xml"), ("bad.xlsx", "word/document.xml")):
    path = Path("PAYLOAD_DIR") / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member, "<root/>")
    try:
        _validate_payload(path, name, path.suffix.lower())
    except HTTPException as exc:
        assert exc.status_code == 422
    else:
        raise AssertionError(name)
'''.replace("PAYLOAD_DIR", str(tmp_path).replace("\\", "\\\\"))
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_project_init_attachment_api_enforces_scope_lifecycle_and_soft_delete(tmp_path):
    script = r'''
from pathlib import Path
import os
from app.database import Base, engine, SessionLocal
from app import models
from app.auth import create_session

Base.metadata.create_all(bind=engine)
db = SessionLocal()
owner = models.Person(id=1, name="Owner", is_active=True)
member = models.Person(id=2, name="Member", is_active=True)
outsider = models.Person(id=3, name="Outsider", is_active=True)
admin = models.Person(id=4, name="Admin", is_active=True)
db.add_all([
    owner, member, outsider, admin,
    models.Project(id=1, name="Editable", status="dispatched"),
    models.Project(id=2, name="Frozen", status="active"),
    models.Account(username="owner", password_hash="x", person_id=1, status="active"),
    models.Account(username="member", password_hash="x", person_id=2, status="active"),
    models.Account(username="outsider", password_hash="x", person_id=3, status="active"),
    models.Account(username="admin", password_hash="x", person_id=4, status="active", is_tech_admin=True),
    models.ProjectMember(project_id=1, person_id=1, role="owner"),
    models.ProjectMember(project_id=2, person_id=1, role="owner"),
    models.ProjectMember(project_id=1, person_id=2, role="member"),
])
db.commit(); db.close()

from app.main import app
from app.routers import project_init_ai
from fastapi.testclient import TestClient
project_init_ai._ROOT = Path(os.environ["ATTACHMENT_TEST_ROOT"])
client = TestClient(app)
def cookies(username):
    return {os.environ.get("SESSION_COOKIE_NAME", "bowei_session"): create_session(username)}

member = cookies("member")
owner = cookies("owner")
admin = cookies("admin")
assert client.post(
    "/api/projects/1/init-attachments",
    files={"file": ("report.pdf", b"not-pdf", "application/pdf")},
    cookies=member,
).status_code == 403
assert client.post(
    "/api/projects/1/init-attachments",
    files={"file": ("report.pdf", b"%PDF-1.7\ncontent", "application/pdf")},
    cookies=member,
).status_code == 403
uploaded = client.post(
    "/api/projects/1/init-attachments",
    files={"file": ("../plan.txt", b"line one\nline two", "text/plain")},
    cookies=owner,
)
assert uploaded.status_code == 201, uploaded.text
payload = uploaded.json()
assert payload["original_name"] == "plan.txt"
attachment_id = payload["id"]
listed = client.get("/api/projects/1/init-attachments", cookies=owner)
assert listed.status_code == 200 and [item["id"] for item in listed.json()] == [attachment_id]
member_listed = client.get("/api/projects/1/init-attachments", cookies=member)
assert member_listed.status_code == 200 and [item["id"] for item in member_listed.json()] == [attachment_id]
download = client.get(f"/api/projects/1/init-attachments/{attachment_id}/download", cookies=owner)
assert download.status_code == 200 and download.content == b"line one\nline two"
assert download.headers["x-content-type-options"] == "nosniff"
member_download = client.get(f"/api/projects/1/init-attachments/{attachment_id}/download", cookies=member)
assert member_download.status_code == 200 and member_download.content == b"line one\nline two"
db = SessionLocal(); row = db.get(models.ProjectInitAttachment, attachment_id); row.mime_type = "text/html"; db.commit(); db.close()
canonical_download = client.get(f"/api/projects/1/init-attachments/{attachment_id}/download", cookies=member)
assert canonical_download.status_code == 200 and canonical_download.headers["content-type"].startswith("text/plain")
admin_upload = client.post(
    "/api/projects/1/init-attachments",
    files={"file": ("admin.txt", b"admin", "text/plain")},
    cookies=admin,
)
assert admin_upload.status_code == 201, admin_upload.text
admin_attachment_id = admin_upload.json()["id"]
assert client.delete(f"/api/projects/1/init-attachments/{admin_attachment_id}", cookies=admin).status_code == 200
assert client.get("/api/projects/2/init-attachments", cookies=owner).status_code == 200
assert client.post(
    "/api/projects/2/init-attachments",
    files={"file": ("frozen.txt", b"frozen", "text/plain")},
    cookies=owner,
).status_code == 409
assert client.get("/api/projects/999999/init-attachments", cookies=owner).status_code == 404
assert client.get("/api/projects/1/init-attachments", cookies=cookies("outsider")).status_code == 403
assert client.delete(f"/api/projects/1/init-attachments/{attachment_id}", cookies=member).status_code == 403
original_attachment_path = project_init_ai._attachment_path
owner_blob = project_init_ai._ROOT / payload["storage_key"]
class FailingPath:
    def unlink(self, **_kwargs):
        raise OSError("storage temporarily unavailable")
project_init_ai._attachment_path = lambda _row: FailingPath()
deleted = client.delete(f"/api/projects/1/init-attachments/{attachment_id}", cookies=owner)
project_init_ai._attachment_path = original_attachment_path
assert deleted.status_code == 200, deleted.text
assert client.get("/api/projects/1/init-attachments", cookies=owner).json() == []
assert not owner_blob.exists()
db = SessionLocal(); row = db.get(models.ProjectInitAttachment, attachment_id)
assert row.deleted_at is not None and row.deleted_by == "owner"
db.close()
'''.replace("ATTACHMENT_TEST_ROOT", "ATTACHMENT_TEST_ROOT")
    database_path = (tmp_path / "project-init-attachments.db").resolve()
    storage_path = (tmp_path / "project-init-storage").resolve()
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
            "FRONTEND_ORIGIN": "",
            "ATTACHMENT_TEST_ROOT": str(storage_path),
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_project_init_attachment_model_is_soft_deletable():
    from app import models

    table = models.ProjectInitAttachment.__table__
    assert {"project_id", "storage_key", "original_name", "mime_type", "size_bytes", "deleted_at", "deleted_by"} <= set(table.c.keys())
    assert table.c.storage_key.unique is True


def test_project_init_attachment_limits_and_database_failure_rollback(tmp_path):
    script = r'''
import os
from pathlib import Path
from fastapi.testclient import TestClient
from app.database import Base, engine, SessionLocal
from app import models
from app.auth import create_session

Base.metadata.create_all(bind=engine)
db = SessionLocal()
db.add_all([
    models.Person(id=1, name="Owner", is_active=True),
    models.Account(username="owner", password_hash="x", person_id=1, status="active"),
    models.Project(id=1, name="Project", status="dispatched"),
    models.ProjectMember(project_id=1, person_id=1, role="owner"),
])
db.commit(); db.close()

from app.main import app
from app.routers import project_init_ai
storage = Path(os.environ["ATTACHMENT_TEST_ROOT"])
project_init_ai._ROOT = storage
client = TestClient(app)
cookies = {os.environ.get("SESSION_COOKIE_NAME", "bowei_session"): create_session("owner")}

limit = project_init_ai._MAX_FILE_BYTES
exact = client.post(
    "/api/projects/1/init-attachments",
    files={"file": ("exact.txt", b"a" * limit, "text/plain")},
    cookies=cookies,
)
assert exact.status_code == 201, exact.text
too_large = client.post(
    "/api/projects/1/init-attachments",
    files={"file": ("too-large.txt", b"a" * (limit + 1), "text/plain")},
    cookies=cookies,
)
assert too_large.status_code == 413, too_large.text

original_log = project_init_ai.crud.log
project_init_ai.crud.log = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("db failure"))
try:
    failed = TestClient(app, raise_server_exceptions=False).post(
        "/api/projects/1/init-attachments",
        files={"file": ("rollback.txt", b"rollback", "text/plain")},
        cookies=cookies,
    )
finally:
    project_init_ai.crud.log = original_log
assert failed.status_code == 500
assert not list(storage.rglob("rollback.txt"))
db = SessionLocal()
assert db.query(models.ProjectInitAttachment).filter_by(original_name="rollback.txt").count() == 0
db.close()
'''
    database_path = (tmp_path / "limits.db").resolve()
    env = os.environ.copy()
    env.update({
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
        "FRONTEND_ORIGIN": "",
        "ATTACHMENT_TEST_ROOT": str((tmp_path / "attachment-storage").resolve()),
    })
    result = subprocess.run([sys.executable, "-c", script], cwd=BACKEND_ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_project_init_attachment_path_escape_is_rejected(tmp_path):
    script = r'''
import os
from pathlib import Path
from fastapi import HTTPException
from app import models
from app.routers import project_init_ai

root = Path(os.environ["ATTACHMENT_TEST_ROOT"]).resolve()
project_init_ai._ROOT = root
row = models.ProjectInitAttachment(storage_key="../outside", original_name="x.txt", mime_type="text/plain", size_bytes=1, uploaded_by="owner")
try:
    project_init_ai._attachment_path(row)
except HTTPException as exc:
    assert exc.status_code == 404
else:
    raise AssertionError("path escape was accepted")

outside = root.parent / "outside"
outside.write_text("secret", encoding="utf-8")
try:
    project_init_ai._attachment_path(row)
except HTTPException as exc:
    assert exc.status_code == 404
else:
    raise AssertionError("existing outside file was exposed")
'''
    env = os.environ.copy()
    env["ATTACHMENT_TEST_ROOT"] = str((tmp_path / "attachment-storage").resolve())
    result = subprocess.run([sys.executable, "-c", script], cwd=BACKEND_ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
