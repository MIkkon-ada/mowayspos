from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _run_alembic(database: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in (
        "ALLOW_DEV_SCHEMA_CREATE_ALL",
        "ALLOW_PROTECTED_DATABASE_MIGRATION",
        "ALLOW_TEST_MEMORY_DATABASE",
        "DATABASE_URL",
        "PROTECTED_DATABASE_PATHS",
    ):
        env.pop(key, None)
    env.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": f"sqlite:///{database.resolve().as_posix()}",
            "PROTECTED_DATABASE_PATHS": str(
                (BACKEND_ROOT / "bowei_ai_dashboard.db").resolve()
            ),
            "PYTHONPATH": str(BACKEND_ROOT),
        }
    )
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_meeting_change_set_migration_contract(tmp_path: Path):
    database = tmp_path / "meeting-change-set.db"
    result = _run_alembic(database, "upgrade", "head")
    assert result.returncode == 0, result.stdout + result.stderr

    inspector = sa.inspect(sa.create_engine(f"sqlite:///{database.as_posix()}"))
    assert "meeting_change_sets" in inspector.get_table_names()
    assert "meeting_change_proposals" in inspector.get_table_names()

    assert {
        column["name"]
        for column in inspector.get_columns("meeting_change_sets")
    } == {
        "id",
        "project_id",
        "meeting_id",
        "created_by_person_id",
        "transcript_hash",
        "snapshot_json",
        "result_json",
        "status",
        "created_at",
        "updated_at",
    }

    assert {
        column["name"]
        for column in inspector.get_columns("meeting_change_proposals")
    } == {
        "id",
        "change_set_id",
        "action",
        "target_type",
        "target_id",
        "parent_workstream_id",
        "before_json",
        "proposed_json",
        "evidence_json",
        "reason",
        "confidence",
        "validation_json",
        "execution_status",
        "executed_by_person_id",
        "executed_at",
        "result_target_id",
        "created_at",
        "updated_at",
    }

    change_set_indexes = {
        tuple(index["column_names"])
        for index in inspector.get_indexes("meeting_change_sets")
    }
    proposal_indexes = {
        tuple(index["column_names"])
        for index in inspector.get_indexes("meeting_change_proposals")
    }
    assert ("project_id", "status") in change_set_indexes
    assert ("meeting_id",) in change_set_indexes
    assert ("change_set_id", "execution_status") in proposal_indexes

    change_set_foreign_keys = {
        (tuple(foreign_key["constrained_columns"]), foreign_key["referred_table"])
        for foreign_key in inspector.get_foreign_keys("meeting_change_sets")
    }
    proposal_foreign_keys = {
        (tuple(foreign_key["constrained_columns"]), foreign_key["referred_table"])
        for foreign_key in inspector.get_foreign_keys("meeting_change_proposals")
    }
    assert (("project_id",), "projects") in change_set_foreign_keys
    assert (("meeting_id",), "meetings") in change_set_foreign_keys
    assert (("change_set_id",), "meeting_change_sets") in proposal_foreign_keys


def test_deleting_attached_meeting_preserves_change_set_and_clears_reference(
    tmp_path: Path,
):
    database = tmp_path / "meeting-delete.db"
    result = _run_alembic(database, "upgrade", "head")
    assert result.returncode == 0, result.stdout + result.stderr

    engine = sa.create_engine(f"sqlite:///{database.as_posix()}")

    @sa.event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    from app import models

    db = sessionmaker(bind=engine)()
    db.add(models.Project(id=1, name="Project A"))
    db.commit()
    db.add(models.Meeting(id=1, project_id=1, title="Attached meeting"))
    db.commit()
    db.add(
        models.MeetingChangeSet(
            id=1,
            project_id=1,
            meeting_id=1,
            transcript_hash="a" * 64,
            snapshot_json="{}",
            result_json="{}",
            status="attached",
        )
    )
    db.commit()

    db.delete(db.get(models.Meeting, 1))
    db.commit()
    db.expire_all()

    change_set = db.get(models.MeetingChangeSet, 1)
    assert change_set is not None
    assert change_set.meeting_id is None


_ANALYZE_AND_PERSIST_CHANGE_SET = r'''
import hashlib
import json

from app import models
from app.database import Base, SessionLocal, engine

Base.metadata.create_all(bind=engine)
db = SessionLocal()
db.add_all([
    models.Person(id=1, name="Owner", is_active=True),
    models.Person(id=2, name="CEO", system_role="company_ceo", is_active=True),
    models.Person(id=3, name="Admin", is_active=True),
    models.Account(id=1, username="owner", password_hash="x", person_id=1, status="active"),
    models.Account(id=2, username="ceo", password_hash="x", person_id=2, status="active"),
    models.Account(id=3, username="admin", password_hash="x", person_id=3, status="active", is_tech_admin=True),
    models.Project(id=1, name="Project A", status="active", is_active=True),
    models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner", role="owner"),
    models.Task(
        id=10,
        project_id=1,
        special_project="Project A",
        key_task="Workstream A",
        owner="Owner",
        status="in_progress",
    ),
    models.SubTask(
        id=20,
        task_id=10,
        title="Key task A",
        assignee="Owner",
        status="in_progress",
        notes="Before meeting",
    ),
])
db.commit()
before = {
    "task": (db.get(models.Task, 10).key_task, db.get(models.Task, 10).status),
    "subtask": (db.get(models.SubTask, 20).title, db.get(models.SubTask, 20).notes),
}
db.close()

from app.main import app
import app.main as main
from app.routers import meetings
from fastapi.testclient import TestClient

active_user = {"name": "owner"}
main.get_session_user = lambda _session_id: active_user["name"]
app.dependency_overrides[meetings.get_current_user_name] = lambda: active_user["name"]
meetings._pick_provider = lambda: "test"

transcript = "Owner agreed to update the task notes."
captured_prompts = []
def _valid_analysis(_text, prompt, _provider):
    captured_prompts.append(prompt)
    return {
        "title": "Weekly review",
        "summary": "Owner agreed to update the task notes.",
        "change_set": [{
            "action": "update_subtask",
            "target": {"project_id": 1, "subtask_id": 20},
            "proposed": {"notes": "Meeting confirmed scope"},
            "evidence": ["Owner agreed to update the task notes."],
            "reason": "The meeting explicitly directed the note update.",
            "confidence": 0.9,
        }],
    }
meetings._do_analyze = _valid_analysis

client = TestClient(app)
response = client.post(
    "/api/meetings/analyze",
    json={"text": transcript, "project_id": 1, "mode": "progress"},
    cookies={"bowei_session": "test-session"},
)
assert response.status_code == 200, response.text
payload = response.json()
assert isinstance(payload["analysis_id"], int)
assert payload["change_set"]["id"] == payload["analysis_id"]
assert payload["change_set"]["project_id"] == 1
assert payload["change_set"]["status"] == "draft"
assert payload["change_set"]["proposals"][0]["target"] == {
    "project_id": 1,
    "subtask_id": 20,
    "parent_workstream_id": 10,
}
assert payload["change_set"]["proposals"][0]["validation"]["state"] == "ready"
assert "change_set" in captured_prompts[0]
assert '"id":20' in captured_prompts[0]
assert "唯一事实来源" in captured_prompts[0]

db = SessionLocal()
change_set = db.get(models.MeetingChangeSet, payload["analysis_id"])
assert change_set is not None
assert change_set.meeting_id is None
assert change_set.transcript_hash == hashlib.sha256(transcript.encode("utf-8")).hexdigest()
snapshot = json.loads(change_set.snapshot_json)
assert snapshot["workstreams"][0]["id"] == 10
assert snapshot["workstreams"][0]["subtasks"][0]["id"] == 20
assert json.loads(change_set.result_json)["change_set"][0]["action"] == "update_subtask"
proposal = db.query(models.MeetingChangeProposal).filter_by(change_set_id=change_set.id).one()
assert proposal.action == "update_subtask"
assert proposal.target_id == 20
assert json.loads(proposal.evidence_json) == ["Owner agreed to update the task notes."]
assert json.loads(proposal.validation_json)["state"] == "ready"
after = {
    "task": (db.get(models.Task, 10).key_task, db.get(models.Task, 10).status),
    "subtask": (db.get(models.SubTask, 20).title, db.get(models.SubTask, 20).notes),
}
assert after == before

meetings._do_analyze = lambda *_args: {
    "change_set": [{
        "action": "update_subtask",
        "target": {"project_id": 1, "subtask_id": 20},
        "proposed": {"notes": "Blocked change"},
        "evidence": ["This quote does not exist."],
        "reason": "Still proposed by the model.",
        "confidence": 0.8,
    }],
}
blocked_response = client.post(
    "/api/meetings/analyze",
    json={"text": transcript, "project_id": 1, "mode": "progress"},
    cookies={"bowei_session": "test-session"},
)
assert blocked_response.status_code == 200, blocked_response.text
blocked_payload = blocked_response.json()
assert blocked_payload["change_set"]["proposals"][0]["validation"]["state"] == "blocked"
blocked_change_set = db.get(models.MeetingChangeSet, blocked_payload["analysis_id"])
assert blocked_change_set is not None
assert db.query(models.MeetingChangeProposal).filter_by(change_set_id=blocked_change_set.id).count() == 1
blocked_after = {
    "task": (db.get(models.Task, 10).key_task, db.get(models.Task, 10).status),
    "subtask": (db.get(models.SubTask, 20).title, db.get(models.SubTask, 20).notes),
}
assert blocked_after == before

audit_count_before_no_project = db.query(models.MeetingChangeSet).count()
meetings._do_analyze = lambda *_args: {"title": "No project analysis", "summary": "ordinary fields"}
for request_body in (
    {"text": "No project kickoff meeting", "mode": "kickoff"},
    {"text": "No project generic meeting"},
):
    no_project_response = client.post(
        "/api/meetings/analyze",
        json=request_body,
        cookies={"bowei_session": "test-session"},
    )
    assert no_project_response.status_code == 200, no_project_response.text
    no_project_payload = no_project_response.json()
    assert no_project_payload["title"] == "No project analysis"
    assert no_project_payload["analysis_id"] is None
    assert no_project_payload["change_set"] is None
assert db.query(models.MeetingChangeSet).count() == audit_count_before_no_project

llm_calls = []
def _unexpected_llm(*_args):
    llm_calls.append(True)
    raise AssertionError("missing projects must not reach the LLM")
meetings._do_analyze = _unexpected_llm
for username in ("admin", "ceo"):
    active_user["name"] = username
    missing_project_response = client.post(
        "/api/meetings/analyze",
        json={"text": transcript, "project_id": 999, "mode": "progress"},
        cookies={"bowei_session": "test-session"},
    )
    assert missing_project_response.status_code == 404, missing_project_response.text
    assert missing_project_response.json()["detail"] == "project not found"
assert llm_calls == []

active_user["name"] = "owner"
no_project_progress_response = client.post(
    "/api/meetings/analyze",
    json={"text": transcript, "mode": "progress"},
    cookies={"bowei_session": "test-session"},
)
assert no_project_progress_response.status_code == 422, no_project_progress_response.text
assert no_project_progress_response.json()["detail"] == "project_id is required for progress meeting analysis"
db.close()
app.dependency_overrides.clear()
print("ANALYZE_CHANGE_SET_PERSISTED")
'''


def test_meeting_analyze_persists_immutable_change_set_without_work_plan_mutation(tmp_path: Path):
    database = tmp_path / "meeting-analyze-change-set.db"
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": f"sqlite:///{database.resolve().as_posix()}",
            "FRONTEND_ORIGIN": "",
            "PYTHONPATH": str(BACKEND_ROOT),
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(_ANALYZE_AND_PERSIST_CHANGE_SET)],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ANALYZE_CHANGE_SET_PERSISTED" in result.stdout


_ATTACH_AND_READ_CHANGE_SET = r'''
import json

from app import models
from app.database import Base, SessionLocal, engine

Base.metadata.create_all(bind=engine)
db = SessionLocal()
db.add_all([
    models.Person(id=1, name="Owner", is_active=True),
    models.Person(id=2, name="Other owner", is_active=True),
    models.Person(id=3, name="Member", is_active=True),
    models.Account(id=1, username="owner", password_hash="x", person_id=1, status="active"),
    models.Account(id=2, username="other", password_hash="x", person_id=2, status="active"),
    models.Account(id=3, username="member", password_hash="x", person_id=3, status="active"),
    models.Project(id=1, name="Project A", status="active", is_active=True),
    models.Project(id=2, name="Project B", status="active", is_active=True),
    models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner", role="owner"),
    models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="Other owner", role="owner"),
    models.ProjectMember(project_id=1, person_id=3, person_name_snapshot="Member", role="member"),
    models.ProjectMember(project_id=2, person_id=1, person_name_snapshot="Owner", role="owner"),
])
db.commit()

def add_draft(project_id, creator_id):
    row = models.MeetingChangeSet(
        project_id=project_id,
        created_by_person_id=creator_id,
        transcript_hash="a" * 64,
        snapshot_json=json.dumps({"project_id": project_id, "workstreams": []}),
        result_json=json.dumps({"change_set": []}),
        status="draft",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.id

own_draft_id = add_draft(1, 1)
wrong_project_id = add_draft(2, 1)
other_users_id = add_draft(1, 2)
db.close()

from app.main import app
import app.main as main
from app.routers import meetings
from fastapi.testclient import TestClient

active_user = {"name": "owner"}
main.get_session_user = lambda _session_id: active_user["name"]
app.dependency_overrides[meetings.get_current_user_name] = lambda: active_user["name"]
client = TestClient(app)

def meeting_payload(analysis_id):
    return {
        "project_id": 1,
        "analysis_id": analysis_id,
        "title": "Weekly review",
        "meeting_type": "progress",
        "publish_status": "draft",
    }

response = client.post(
    "/api/meetings",
    json=meeting_payload(own_draft_id),
    cookies={"bowei_session": "test-session"},
)
assert response.status_code == 200, response.text
meeting_id = response.json()["id"]

detail = client.get(
    f"/api/meetings/{meeting_id}/change-set",
    cookies={"bowei_session": "test-session"},
)
assert detail.status_code == 200, detail.text
assert detail.json()["id"] == own_draft_id
assert detail.json()["status"] == "attached"

db = SessionLocal()
attached = db.get(models.MeetingChangeSet, own_draft_id)
assert attached.meeting_id == meeting_id
assert attached.status == "attached"
attach_log = db.query(models.OperationLog).filter_by(
    action="meeting_change_set_attach",
    target_type="meeting_change_set",
    target_id=own_draft_id,
).one()
assert json.loads(attach_log.after_json)["meeting_id"] == meeting_id
meeting_count = db.query(models.Meeting).count()
db.close()

for invalid_analysis_id in (wrong_project_id, other_users_id):
    invalid = client.post(
        "/api/meetings",
        json=meeting_payload(invalid_analysis_id),
        cookies={"bowei_session": "test-session"},
    )
    assert invalid.status_code == 409, invalid.text

db = SessionLocal()
assert db.query(models.Meeting).count() == meeting_count
assert db.get(models.MeetingChangeSet, wrong_project_id).meeting_id is None
assert db.get(models.MeetingChangeSet, other_users_id).meeting_id is None
db.close()

active_user["name"] = "member"
denied = client.get(
    f"/api/meetings/{meeting_id}/change-set",
    cookies={"bowei_session": "test-session"},
)
assert denied.status_code == 403, denied.text

app.dependency_overrides.clear()
print("ATTACH_AND_READ_CHANGE_SET")
'''


def test_saving_meeting_attaches_only_own_matching_draft_and_reuses_read_permissions(
    tmp_path: Path,
):
    database = tmp_path / "meeting-attach-change-set.db"
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": f"sqlite:///{database.resolve().as_posix()}",
            "FRONTEND_ORIGIN": "",
            "PYTHONPATH": str(BACKEND_ROOT),
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(_ATTACH_AND_READ_CHANGE_SET)],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ATTACH_AND_READ_CHANGE_SET" in result.stdout
