from __future__ import annotations

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.domain import submission_status as SS
from app.domain import issue_flow as IF
from app.domain import task_status as TS
from app.routers import projects as projects_router
from app.routers.projects import (
    approve_project_close_request,
    cancel_project_close_request,
    create_project_close_request,
    get_project_close_request,
    list_project_close_requests,
    reject_project_close_request,
    update_project_close_request,
)


def _db(status: str = "active"):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    people = [
        models.Person(id=1, name="Owner", system_role="normal_member", is_active=True),
        models.Person(id=2, name="Coach", system_role="normal_member", is_active=True),
        models.Person(id=3, name="Member", system_role="normal_member", is_active=True),
    ]
    db.add_all(people)
    db.add_all(
        [
            models.Account(username="owner", password_hash="x", person_id=1, status="active"),
            models.Account(username="coach", password_hash="x", person_id=2, status="active"),
            models.Account(username="member", password_hash="x", person_id=3, status="active"),
            models.Project(id=1, name="Project A", status=status, is_active=status == "active"),
            models.Project(id=2, name="Project B", status="active", is_active=True),
            models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner", role="owner"),
            models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="Coach", role="project_ceo"),
            models.ProjectMember(project_id=1, person_id=3, person_name_snapshot="Member", role="member"),
        ]
    )
    db.commit()
    return db


def _payload(summary: str = "Complete") -> schemas.ProjectCloseRequestCreatePayload:
    return schemas.ProjectCloseRequestCreatePayload(
        summary=summary,
        objective_result="Objectives achieved",
        unfinished_items=[],
        remaining_risks=[],
        handover_plan="Handover complete",
        retrospective="Retrospective complete",
    )


def _file_sessions(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'close-flow.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    seed = sessionmaker(bind=engine)()
    seed.add_all(
        [
            models.Person(id=1, name="Owner", system_role="normal_member", is_active=True),
            models.Person(id=2, name="Coach", system_role="normal_member", is_active=True),
            models.Account(username="owner", password_hash="x", person_id=1, status="active"),
            models.Account(username="coach", password_hash="x", person_id=2, status="active"),
            models.Project(id=1, name="Project A", status="active", is_active=True),
            models.ProjectMember(
                project_id=1,
                person_id=1,
                person_name_snapshot="Owner",
                role="owner",
            ),
            models.ProjectMember(
                project_id=1,
                person_id=2,
                person_name_snapshot="Coach",
                role="project_ceo",
            ),
        ]
    )
    seed.commit()
    seed.close()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return engine, factory(), factory()


def test_project_close_lock_statements_compile_to_postgresql_for_update():
    project_sql = str(
        projects_router._project_close_project_lock_statement(7).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    request_sql = str(
        projects_router._project_close_request_lock_statement(7, 11).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "FOR UPDATE" in project_sql
    assert "projects.id = 7" in project_sql
    assert "FOR UPDATE" in request_sql
    assert "project_close_requests.id = 11" in request_sql
    assert "project_close_requests.project_id = 7" in request_sql


def test_stale_session_cannot_overwrite_approved_close_request(tmp_path):
    engine, session_a, session_b = _file_sessions(tmp_path)
    request = create_project_close_request(1, _payload(), current_user="owner", db=session_a)
    request_id = request["id"]

    cached_project = session_b.get(models.Project, 1)
    cached_request = session_b.get(models.ProjectCloseRequest, request_id)
    assert cached_project.status == "pending_close"
    assert cached_request.status == "pending"
    session_b.commit()

    approve_project_close_request(
        1,
        request_id,
        schemas.ProjectCloseReviewPayload(review_comment="Approved"),
        current_user="coach",
        db=session_a,
    )
    log_count = session_a.query(models.OperationLog).count()
    notification_count = session_a.query(models.Notification).count()

    with pytest.raises(HTTPException) as exc:
        reject_project_close_request(
            1,
            request_id,
            schemas.ProjectCloseReviewPayload(review_comment="Stale reject"),
            current_user="coach",
            db=session_b,
        )
    assert exc.value.status_code == 409
    session_b.rollback()

    verify = sessionmaker(bind=engine)()
    assert verify.get(models.ProjectCloseRequest, request_id).status == "approved"
    assert verify.get(models.Project, 1).status == "ended"
    assert verify.query(models.OperationLog).count() == log_count
    assert verify.query(models.Notification).count() == notification_count
    assert verify.query(models.OperationLog).filter_by(action="project_close_request_reject").count() == 0
    assert verify.query(models.Notification).filter_by(type="project_close_rejected").count() == 0


def test_stale_active_project_cannot_create_duplicate_pending_request(tmp_path):
    _engine, session_a, session_b = _file_sessions(tmp_path)
    cached_project = session_b.get(models.Project, 1)
    assert cached_project.status == "active"
    session_b.commit()

    create_project_close_request(1, _payload("First"), current_user="owner", db=session_a)

    with pytest.raises(HTTPException) as exc:
        create_project_close_request(1, _payload("Duplicate"), current_user="owner", db=session_b)
    assert exc.value.status_code == 409
    session_b.rollback()
    assert session_a.query(models.ProjectCloseRequest).filter_by(status="pending").count() == 1


def test_complete_create_edit_cancel_reject_and_approve_history_flow():
    db = _db()

    first = create_project_close_request(1, _payload(), current_user="owner", db=db)
    assert first["status"] == "pending"
    assert first["project_status"] == "pending_close"
    assert db.get(models.Project, 1).is_active is False

    edited = update_project_close_request(
        1,
        first["id"],
        schemas.ProjectCloseRequestUpdatePayload(summary="Updated summary"),
        current_user="owner",
        db=db,
    )
    assert edited["summary"] == "Updated summary"
    assert edited["status"] == "pending"

    cancelled = cancel_project_close_request(1, first["id"], current_user="owner", db=db)
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancelled_at"] is not None
    assert db.get(models.Project, 1).status == "active"

    second = create_project_close_request(1, _payload("Second"), current_user="owner", db=db)
    rejected = reject_project_close_request(
        1,
        second["id"],
        schemas.ProjectCloseReviewPayload(review_comment="Need more evidence"),
        current_user="coach",
        db=db,
    )
    assert rejected["status"] == "rejected"
    assert rejected["reviewer_person_id"] == 2
    assert rejected["review_comment"] == "Need more evidence"
    assert db.get(models.Project, 1).status == "active"

    third = create_project_close_request(1, _payload("Third"), current_user="owner", db=db)
    approved = approve_project_close_request(
        1,
        third["id"],
        schemas.ProjectCloseReviewPayload(review_comment="Approved"),
        current_user="coach",
        db=db,
    )
    assert approved["status"] == "approved"
    assert approved["project_status"] == "ended"
    assert approved["reviewed_at"] is not None
    assert db.get(models.Project, 1).is_active is False

    history = list_project_close_requests(1, status=None, current_user="owner", db=db)
    assert [row["status"] for row in history] == ["approved", "rejected", "cancelled"]
    assert all("unfinished_items_json" not in row for row in history)


@pytest.mark.parametrize(
    "status,allowed",
    [
        ("draft", False),
        ("dispatched", False),
        ("pending_review", False),
        ("returned", False),
        ("active", True),
        ("pending_close", False),
        ("ended", False),
        ("archived", False),
    ],
)
def test_only_active_projects_accept_close_requests(status: str, allowed: bool):
    db = _db(status)
    if allowed:
        assert create_project_close_request(1, _payload(), current_user="owner", db=db)["status"] == "pending"
    else:
        with pytest.raises(HTTPException) as exc:
            create_project_close_request(1, _payload(), current_user="owner", db=db)
        assert exc.value.status_code == 409
        assert db.query(models.ProjectCloseRequest).count() == 0


def test_create_and_approve_recheck_strong_blockers_without_partial_state_changes():
    db = _db()
    db.add(
        models.UpdateSubmission(
            project_id=1,
            transcript_text="pending",
            confirm_status=SS.S_NEW,
        )
    )
    db.commit()

    with pytest.raises(HTTPException) as exc:
        create_project_close_request(1, _payload(), current_user="owner", db=db)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "PROJECT_CLOSE_BLOCKED"
    assert db.get(models.Project, 1).status == "active"
    assert db.query(models.ProjectCloseRequest).count() == 0

    db.query(models.UpdateSubmission).delete()
    db.commit()
    request = create_project_close_request(1, _payload(), current_user="owner", db=db)
    db.add(
        models.UpdateSubmission(
            project_id=1,
            transcript_text="late pending",
            confirm_status=SS.S_NEW,
        )
    )
    db.commit()

    with pytest.raises(HTTPException) as exc:
        approve_project_close_request(
            1,
            request["id"],
            schemas.ProjectCloseReviewPayload(),
            current_user="coach",
            db=db,
        )
    assert exc.value.status_code == 409
    stored = db.get(models.ProjectCloseRequest, request["id"])
    assert stored.status == "pending"
    assert stored.reviewer_person_id is None
    assert stored.reviewed_at is None
    assert db.get(models.Project, 1).status == "pending_close"


def test_warnings_do_not_block_create_or_approve():
    db = _db()
    task = models.Task(project_id=1, key_task="Workstream", status=TS.S_IN_PROGRESS)
    db.add(task)
    db.flush()
    db.add_all(
        [
            models.SubTask(
                task_id=task.id,
                title="Unfinished key task",
                assignee="Owner",
                status=TS.S_IN_PROGRESS,
            ),
            models.Issue(
                project_id=1,
                issue_type=IF.TYPE_ISSUE,
                description="Open ordinary issue",
                status=IF.STATUS_PENDING,
            ),
        ]
    )
    db.commit()

    request = create_project_close_request(1, _payload(), current_user="owner", db=db)
    assert {item["code"] for item in request["warnings"]} == {
        "unfinished_key_tasks",
        "open_non_decision_issues",
    }
    approved = approve_project_close_request(
        1,
        request["id"],
        schemas.ProjectCloseReviewPayload(review_comment="Warnings accepted"),
        current_user="coach",
        db=db,
    )
    assert approved["status"] == "approved"
    assert approved["project_status"] == "ended"


def test_cross_project_request_id_is_404_and_filters_are_validated():
    db = _db()
    request = create_project_close_request(1, _payload(), current_user="owner", db=db)

    with pytest.raises(HTTPException) as exc:
        get_project_close_request(2, request["id"], current_user="moways", db=db)
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        list_project_close_requests(1, status="invalid", current_user="owner", db=db)
    assert exc.value.status_code == 422
