from sqlalchemy import create_engine, inspect
import os
import subprocess
import sys
from pathlib import Path

from app import models
from app.database import Base


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_attachment_api_rejects_unauthorized_and_disallowed_files_and_soft_deletes(tmp_path):
    """The HTTP contract enforces project scope, type checks, and soft deletion."""
    script = r'''
from app.database import Base, engine, SessionLocal
from app import models
from app.auth import create_session

Base.metadata.create_all(bind=engine)
db = SessionLocal()
owner = models.Person(id=1, name="Owner", is_active=True)
member = models.Person(id=2, name="Member", is_active=True)
outsider = models.Person(id=3, name="Outsider", is_active=True)
db.add_all([owner, member, outsider, models.Project(id=1, name="Project A", status="active"), models.Project(id=2, name="Project B", status="active")])
db.add_all([
    models.Account(username="owner", password_hash="x", person_id=1, status="active"),
    models.Account(username="member", password_hash="x", person_id=2, status="active"),
    models.Account(username="outsider", password_hash="x", person_id=3, status="active"),
    models.ProjectMember(project_id=1, person_id=1, role="owner"),
    models.ProjectMember(project_id=2, person_id=1, role="owner"),
    models.ProjectMember(project_id=1, person_id=2, role="member"),
    models.Achievement(id=1, project_id=1, name="Result"),
    models.Achievement(id=2, project_id=2, name="Other result"),
])
db.commit(); db.close()

from app.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
def cookies(username): return {"bowei_session": create_session(username)}

blocked = client.post("/api/achievement-attachments", data={"project_id": "1", "achievement_id": "1"}, files={"file": ("movie.mp4", b"x", "video/mp4")}, cookies=cookies("member"))
assert blocked.status_code == 422, blocked.text
denied = client.get("/api/achievement-attachments", params={"achievement_id": 1}, cookies=cookies("outsider"))
assert denied.status_code == 403, denied.text
uploaded = client.post("/api/achievement-attachments", data={"project_id": "1", "achievement_id": "1"}, files={"file": ("report.pdf", b"pdf", "application/pdf")}, cookies=cookies("member"))
assert uploaded.status_code == 201, uploaded.text
attachment_id = uploaded.json()["id"]
assert uploaded.json()["mime_type"] == "application/pdf"
dangerous_mime = client.post("/api/achievement-attachments", data={"project_id": "1", "achievement_id": "1"}, files={"file": ("looks-safe.pdf", b"<script>", "text/html")}, cookies=cookies("member"))
assert dangerous_mime.status_code == 422, dangerous_mime.text
download = client.get(f"/api/achievement-attachments/{attachment_id}/download", cookies=cookies("member"))
assert download.status_code == 200 and download.content == b"pdf", download.text
assert download.headers["content-type"].startswith("application/pdf")
assert download.headers["x-content-type-options"] == "nosniff"
assert download.headers["content-disposition"].startswith("attachment;")
from app.routers import achievement_attachments
original_attachment_path = achievement_attachments._attachment_path
class UnlinkFailure:
    def unlink(self, **_kwargs): raise OSError("storage temporarily unavailable")
achievement_attachments._attachment_path = lambda _row: UnlinkFailure()
deleted = client.delete(f"/api/achievement-attachments/{attachment_id}", cookies=cookies("member"))
achievement_attachments._attachment_path = original_attachment_path
assert deleted.status_code == 200, deleted.text
db = SessionLocal(); row = db.get(models.AchievementAttachment, attachment_id)
assert row.deleted_at is not None and row.deleted_by == "member"
db.close()
orphaned_path = achievement_attachments._ROOT / row.storage_key
assert orphaned_path.is_file()
# A later attachment request retries cleanup of persistently soft-deleted rows.
assert client.get("/api/achievement-attachments", params={"achievement_id": 1}, cookies=cookies("member")).json() == []
assert not orphaned_path.exists()
assert client.get("/api/achievement-attachments", params={"achievement_id": 1}, cookies=cookies("member")).json() == []
mismatched = client.post("/api/achievement-attachments", data={"project_id": "2", "achievement_id": "1"}, files={"file": ("report.pdf", b"pdf", "application/pdf")}, cookies=cookies("owner"))
assert mismatched.status_code == 422, mismatched.text
too_large = client.post("/api/achievement-attachments", data={"project_id": "1", "achievement_id": "1"}, files={"file": ("large.pdf", b"x" * (20 * 1024 * 1024 + 1), "application/pdf")}, cookies=cookies("member"))
assert too_large.status_code in (413, 422), too_large.text
db = SessionLocal(); db.add(models.AchievementAttachment(project_id=1, achievement_id=1, storage_key="1/preexisting", original_name="old.pdf", mime_type="application/pdf", size_bytes=100 * 1024 * 1024, uploaded_by="member")); db.commit(); db.close()
total_full = client.post("/api/achievement-attachments", data={"project_id": "1", "achievement_id": "1"}, files={"file": ("another.pdf", b"x", "application/pdf")}, cookies=cookies("member"))
assert total_full.status_code == 422, total_full.text
project_b_upload = client.post("/api/achievement-attachments", data={"project_id": "2", "achievement_id": "2"}, files={"file": ("project-b.pdf", b"pdf", "application/pdf")}, cookies=cookies("owner"))
assert project_b_upload.status_code == 201, project_b_upload.text
project_b_attachment_id = project_b_upload.json()["id"]
assert client.get("/api/achievement-attachments", params={"achievement_id": 2}, cookies=cookies("member")).status_code == 403
assert client.get(f"/api/achievement-attachments/{project_b_attachment_id}/download", cookies=cookies("member")).status_code == 403
assert client.delete(f"/api/achievement-attachments/{project_b_attachment_id}", cookies=cookies("owner")).status_code == 200
'''
    database_path = (tmp_path / "attachments.db").resolve()
    env = os.environ.copy()
    env.update({"APP_ENV": "test", "DATABASE_URL": f"sqlite:///{database_path.as_posix()}", "FRONTEND_ORIGIN": ""})
    result = subprocess.run([sys.executable, "-c", script], cwd=BACKEND_ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_attachment_api_cleans_blob_when_database_write_fails(tmp_path):
    """A filesystem blob is never retained when metadata persistence fails."""
    script = r'''
from pathlib import Path
import os
from app.database import Base, engine, SessionLocal
from app import models
from app.auth import create_session

Base.metadata.create_all(bind=engine)
db = SessionLocal()
db.add_all([
    models.Person(id=1, name="Member", is_active=True),
    models.Project(id=1, name="Project A", status="active"),
    models.Account(username="member", password_hash="x", person_id=1, status="active"),
    models.ProjectMember(project_id=1, person_id=1, role="member"),
    models.Achievement(id=1, project_id=1, name="Result"),
])
db.commit(); db.close()

from app.main import app
import app.main as main
from app.routers import achievement_attachments
from fastapi.testclient import TestClient
storage = Path(os.environ["ATTACHMENT_TEST_ROOT"])
achievement_attachments._ROOT = storage
main.get_session_user = lambda _sid: "member"
app.dependency_overrides[achievement_attachments.get_current_user_name] = lambda: "member"
session_cookie = {"bowei_session": "test"}
original_commit = SessionLocal.class_.commit
def fail_commit(self): raise RuntimeError("database unavailable")
SessionLocal.class_.commit = fail_commit
try:
    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/achievement-attachments", data={"project_id": "1", "achievement_id": "1"},
        files={"file": ("report.pdf", b"pdf", "application/pdf")},
        cookies=session_cookie,
    )
    assert response.status_code == 500, response.text
finally:
    SessionLocal.class_.commit = original_commit
assert not [path for path in storage.rglob("*") if path.is_file()]
'''
    database_path = (tmp_path / "attachments-failure.db").resolve()
    env = os.environ.copy()
    env.update({"APP_ENV": "test", "DATABASE_URL": f"sqlite:///{database_path.as_posix()}", "FRONTEND_ORIGIN": "", "ATTACHMENT_TEST_ROOT": str((tmp_path / "attachment-storage").resolve())})
    result = subprocess.run([sys.executable, "-c", script], cwd=BACKEND_ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_achievement_attachment_model_has_storage_metadata_contract():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    table = models.AchievementAttachment.__table__
    assert table.name == "achievement_attachments"
    assert set(table.columns.keys()) == {
        "id",
        "project_id",
        "achievement_id",
        "achievement_submission_id",
        "storage_key",
        "original_name",
        "mime_type",
        "size_bytes",
        "uploaded_by",
        "uploaded_by_person_id",
        "deleted_at",
        "deleted_by",
        "created_at",
        "updated_at",
    }

    db_columns = {
        column["name"]: column
        for column in inspect(engine).get_columns("achievement_attachments")
    }
    assert not db_columns["project_id"]["nullable"]
    assert not db_columns["storage_key"]["nullable"]
    assert not db_columns["original_name"]["nullable"]
    assert not db_columns["mime_type"]["nullable"]
    assert not db_columns["size_bytes"]["nullable"]
    assert db_columns["storage_key"]["type"].length == 255
    assert db_columns["original_name"]["type"].length == 255
    assert db_columns["mime_type"]["type"].length == 120

    foreign_keys = {
        (tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]))
        for fk in inspect(engine).get_foreign_keys("achievement_attachments")
    }
    assert (("project_id",), "projects", ("id",)) in foreign_keys
    assert (("achievement_id",), "achievements", ("id",)) in foreign_keys
    assert (("achievement_submission_id",), "achievement_submissions", ("id",)) in foreign_keys
    assert (("uploaded_by_person_id",), "people", ("id",)) in foreign_keys

    indexed = {tuple(index["column_names"]) for index in inspect(engine).get_indexes("achievement_attachments")}
    assert ("project_id",) in indexed
    assert ("achievement_id",) in indexed
    assert ("achievement_submission_id",) in indexed
    assert ("uploaded_by_person_id",) in indexed

    assert table.c.storage_key.unique
    assert table.c.deleted_by.default.arg == ""


def test_confirming_submission_moves_bound_attachment_to_achievement(tmp_path):
    """Confirmation transfers active submitter-owned evidence to the new achievement."""
    script = r'''
from app.database import Base, engine, SessionLocal
from app import models
from app.auth import create_session

Base.metadata.create_all(bind=engine)
db = SessionLocal()
db.add_all([
    models.Person(id=1, name="Owner", is_active=True),
    models.Person(id=2, name="Member", is_active=True),
    models.Project(id=1, name="Project A", status="active"),
    models.Account(username="owner", password_hash="x", person_id=1, status="active"),
    models.Account(username="member", password_hash="x", person_id=2, status="active"),
    models.ProjectMember(project_id=1, person_id=1, role="owner"),
    models.ProjectMember(project_id=1, person_id=2, role="member"),
    models.Task(id=1, project_id=1, key_task="Task A"),
])
pending = models.AchievementAttachment(
    project_id=1, storage_key="1/pending", original_name="proof.pdf",
    mime_type="application/pdf", size_bytes=1, uploaded_by="member",
    uploaded_by_person_id=2,
)
deleted = models.AchievementAttachment(
    project_id=1, storage_key="1/deleted", original_name="old.pdf",
    mime_type="application/pdf", size_bytes=1, uploaded_by="member",
    uploaded_by_person_id=2,
)
db.add_all([pending, deleted]); db.commit()
pending_id, deleted_id = pending.id, deleted.id

from app.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
cookies = {"bowei_session": create_session("member")}
created = client.post("/api/achievement-submissions", json={
    "project_id": 1, "related_task_id": 1, "name": "Result",
    "attachment_ids": [pending_id],
}, cookies=cookies)
assert created.status_code == 200, created.text
submission_id = created.json()["id"]
db.refresh(pending)
assert pending.achievement_submission_id == submission_id
deleted.achievement_submission_id = submission_id
from app.time_utils import utc_now
deleted.deleted_at = utc_now()
db.commit(); db.close()

confirmed = client.patch(
    f"/api/achievement-submissions/{submission_id}/confirm",
    cookies={"bowei_session": create_session("owner")},
)
assert confirmed.status_code == 200, confirmed.text
achievement_id = confirmed.json()["achievement"]["id"]
db = SessionLocal()
pending = db.get(models.AchievementAttachment, pending_id)
deleted = db.get(models.AchievementAttachment, deleted_id)
assert pending.achievement_id == achievement_id
assert pending.achievement_submission_id is None
assert deleted.achievement_id is None
assert deleted.achievement_submission_id == submission_id
db.close()
'''
    database_path = (tmp_path / "attachment-transfer.db").resolve()
    env = os.environ.copy()
    env.update({"APP_ENV": "test", "DATABASE_URL": f"sqlite:///{database_path.as_posix()}", "FRONTEND_ORIGIN": ""})
    result = subprocess.run([sys.executable, "-c", script], cwd=BACKEND_ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_submission_rejects_attachments_outside_submitter_unbound_project_scope(tmp_path):
    """A submitter can bind only their own unbound attachments in the same project."""
    script = r'''
from app.database import Base, engine, SessionLocal
from app import models
from app.auth import create_session

Base.metadata.create_all(bind=engine)
db = SessionLocal()
db.add_all([
    models.Person(id=1, name="Member", is_active=True),
    models.Person(id=2, name="Other", is_active=True),
    models.Project(id=1, name="Project A", status="active"),
    models.Project(id=2, name="Project B", status="active"),
    models.Account(username="member", password_hash="x", person_id=1, status="active"),
    models.Account(username="other", password_hash="x", person_id=2, status="active"),
    models.ProjectMember(project_id=1, person_id=1, role="member"),
    models.ProjectMember(project_id=1, person_id=2, role="member"),
    models.Task(id=1, project_id=1, key_task="Task A"),
    models.AchievementSubmission(id=1, project_id=1, name="Existing", status="待确认"),
])
cross_project = models.AchievementAttachment(
    project_id=2, storage_key="2/cross", original_name="cross.pdf",
    mime_type="application/pdf", size_bytes=1, uploaded_by="member",
)
already_bound = models.AchievementAttachment(
    project_id=1, achievement_submission_id=1, storage_key="1/bound", original_name="bound.pdf",
    mime_type="application/pdf", size_bytes=1, uploaded_by="member",
)
other_uploader = models.AchievementAttachment(
    project_id=1, storage_key="1/other", original_name="other.pdf",
    mime_type="application/pdf", size_bytes=1, uploaded_by="other",
)
db.add_all([cross_project, already_bound, other_uploader]); db.commit()
attachment_ids = [cross_project.id, already_bound.id, other_uploader.id]
db.close()

from app.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
cookies = {"bowei_session": create_session("member")}
for attachment_id in attachment_ids:
    response = client.post("/api/achievement-submissions", json={
        "project_id": 1, "related_task_id": 1, "name": "Result",
        "attachment_ids": [attachment_id],
    }, cookies=cookies)
    assert response.status_code == 422, response.text
'''
    database_path = (tmp_path / "attachment-scope.db").resolve()
    env = os.environ.copy()
    env.update({"APP_ENV": "test", "DATABASE_URL": f"sqlite:///{database_path.as_posix()}", "FRONTEND_ORIGIN": ""})
    result = subprocess.run([sys.executable, "-c", script], cwd=BACKEND_ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_attachment_upload_allows_unbound_evidence_and_enforces_target_workflow_rules(tmp_path):
    """Work-report evidence may be unbound until confirmation; bound targets still enforce their rules."""
    script = r'''
import os
from pathlib import Path
from app.database import Base, engine, SessionLocal
from app import models
from app.auth import create_session
from app.routers.achievement_submissions import _STATUS_CONFIRMED, _STATUS_PENDING

Base.metadata.create_all(bind=engine)
db = SessionLocal()
db.add_all([
    models.Person(id=1, name="Owner", is_active=True),
    models.Person(id=2, name="Member", is_active=True),
    models.Person(id=3, name="Other", is_active=True),
    models.Project(id=1, name="Project A", status="active"),
    models.Account(username="owner", password_hash="x", person_id=1, status="active"),
    models.Account(username="member", password_hash="x", person_id=2, status="active"),
    models.Account(username="other", password_hash="x", person_id=3, status="active"),
    models.ProjectMember(project_id=1, person_id=1, role="owner"),
    models.ProjectMember(project_id=1, person_id=2, role="member"),
    models.ProjectMember(project_id=1, person_id=3, role="member"),
    models.Achievement(id=1, project_id=1, name="Achievement"),
    models.AchievementSubmission(id=1, project_id=1, submitter="member", name="Pending", status=_STATUS_PENDING),
    models.AchievementSubmission(id=2, project_id=1, submitter="member", name="Confirmed", status=_STATUS_CONFIRMED),
    models.AchievementSubmission(id=3, project_id=1, submitter="other", name="Other", status=_STATUS_PENDING),
])
db.commit(); db.close()

from app.main import app
from app.routers import achievement_attachments
from fastapi.testclient import TestClient
achievement_attachments._ROOT = Path(os.environ["ATTACHMENT_TEST_ROOT"])
client = TestClient(app)
def upload(data, user="member"):
    return client.post(
        "/api/achievement-attachments", data=data,
        files={"file": ("proof.pdf", b"pdf", "application/pdf")},
        cookies={"bowei_session": create_session(user)},
    )

assert upload({"project_id": "1"}).status_code == 201
assert upload({"project_id": "1", "achievement_id": "1", "achievement_submission_id": "1"}).status_code == 422
assert upload({"project_id": "1", "achievement_submission_id": "2"}).status_code == 422
assert upload({"project_id": "1", "achievement_submission_id": "3"}).status_code == 403
owner_upload = upload({"project_id": "1", "achievement_submission_id": "3"}, user="owner")
assert owner_upload.status_code == 201
db = SessionLocal(); db.get(models.Project, 1).status = "pending_close"; db.commit(); db.close()
assert upload({"project_id": "1", "achievement_submission_id": "1"}).status_code == 409
assert client.delete(
    f"/api/achievement-attachments/{owner_upload.json()['id']}",
    cookies={"bowei_session": create_session("owner")},
).status_code == 409
'''
    database_path = (tmp_path / "attachment-upload-scope.db").resolve()
    env = os.environ.copy()
    env.update({
        "APP_ENV": "test", "DATABASE_URL": f"sqlite:///{database_path.as_posix()}", "FRONTEND_ORIGIN": "",
        "ATTACHMENT_TEST_ROOT": str((tmp_path / "attachment-storage").resolve()),
    })
    result = subprocess.run([sys.executable, "-c", script], cwd=BACKEND_ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_attachment_cannot_be_bound_to_two_submissions(tmp_path):
    """A conditional bind allows only the first submission to claim an attachment."""
    script = r'''
from app.database import Base, engine, SessionLocal
from app import models
from app.auth import create_session

Base.metadata.create_all(bind=engine)
db = SessionLocal()
db.add_all([
    models.Person(id=1, name="Member", is_active=True),
    models.Project(id=1, name="Project A", status="active"),
    models.Account(username="member", password_hash="x", person_id=1, status="active"),
    models.ProjectMember(project_id=1, person_id=1, role="member"),
    models.Task(id=1, project_id=1, key_task="Task A"),
])
attachment = models.AchievementAttachment(
    project_id=1, storage_key="1/evidence", original_name="proof.pdf",
    mime_type="application/pdf", size_bytes=1, uploaded_by="member",
)
db.add(attachment); db.commit(); attachment_id = attachment.id; db.close()

from app.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
cookies = {"bowei_session": create_session("member")}
payload = {"project_id": 1, "related_task_id": 1, "name": "Result", "attachment_ids": [attachment_id]}
first = client.post("/api/achievement-submissions", json=payload, cookies=cookies)
assert first.status_code == 200, first.text
second = client.post("/api/achievement-submissions", json=payload, cookies=cookies)
assert second.status_code == 422, second.text
db = SessionLocal(); attachment = db.get(models.AchievementAttachment, attachment_id)
assert attachment.achievement_submission_id == first.json()["id"]
assert db.query(models.AchievementSubmission).count() == 1
db.close()
'''
    database_path = (tmp_path / "attachment-double-bind.db").resolve()
    env = os.environ.copy()
    env.update({"APP_ENV": "test", "DATABASE_URL": f"sqlite:///{database_path.as_posix()}", "FRONTEND_ORIGIN": ""})
    result = subprocess.run([sys.executable, "-c", script], cwd=BACKEND_ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_submission_confirmation_creates_one_achievement(tmp_path):
    """Once confirmation changes the submission state, a second request cannot write again."""
    script = r'''
from app.database import Base, engine, SessionLocal
from app import models
from app.auth import create_session
from app.routers.achievement_submissions import _STATUS_PENDING

Base.metadata.create_all(bind=engine)
db = SessionLocal()
db.add_all([
    models.Person(id=1, name="Owner", is_active=True),
    models.Project(id=1, name="Project A", status="active"),
    models.Account(username="owner", password_hash="x", person_id=1, status="active", is_tech_admin=True),
    models.ProjectMember(project_id=1, person_id=1, role="owner"),
    models.Task(id=1, project_id=1, key_task="Task A"),
    models.AchievementSubmission(
        id=1, project_id=1, related_task_id=1, submitter="owner",
        name="Result", status=_STATUS_PENDING,
    ),
])
db.commit(); db.close()

from app.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
cookies = {"bowei_session": create_session("owner")}
first = client.patch("/api/achievement-submissions/1/confirm", cookies=cookies)
assert first.status_code == 200, first.text
second = client.patch("/api/achievement-submissions/1/confirm", cookies=cookies)
assert second.status_code == 422, second.text
db = SessionLocal()
assert db.query(models.Achievement).filter_by(source_achievement_submission_id=1).count() == 1
db.close()
'''
    database_path = (tmp_path / "confirmation-race.db").resolve()
    env = os.environ.copy()
    env.update({"APP_ENV": "test", "DATABASE_URL": f"sqlite:///{database_path.as_posix()}", "FRONTEND_ORIGIN": ""})
    result = subprocess.run([sys.executable, "-c", script], cwd=BACKEND_ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
