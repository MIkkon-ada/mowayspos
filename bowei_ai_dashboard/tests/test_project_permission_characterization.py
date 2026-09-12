from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.services import project_close_workflow
from app.database import Base
from app.domain.project_permissions import (
    A_ARCHIVE,
    A_BATCH_IMPORT,
    A_CANCEL_CLOSE_REQUEST,
    A_CREATE,
    A_DELETE,
    A_DISPATCH,
    A_EDIT_CLOSE_REQUEST,
    A_OWNER_SUBMIT,
    A_REQUEST_CLOSE,
    A_REVIEW_CLOSE_REQUEST,
    A_REVIEW_START,
    A_TECHNICAL_KICKOFF,
    A_VIEW,
)
from app.routers import projects
from app.routers.projects import (
    approve_project,
    approve_project_close_request,
    add_member,
    archive_project,
    batch_import_projects,
    create_member_change_request,
    create_project,
    create_project_close_request,
    cancel_project_close_request,
    delete_project,
    delete_project,
    dispatch_project,
    kickoff_project,
    kickoff_project,
    list_members,
    owner_submit_project_profile,
    return_project,
    update_project_close_request,
)


def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed(*, lifecycle: str = "active"):
    db = _make_session()
    people = [
        (1, "Admin", "admin", "normal_member", True),
        (2, "Company CEO", "company_ceo", "company_ceo", False),
        (3, "Project Coach", "coach", "normal_member", False),
        (4, "Owner", "owner", "normal_member", False),
        (5, "Coordinator", "coordinator", "normal_member", False),
        (6, "Member", "member", "normal_member", False),
        (7, "Outsider", "outsider", "normal_member", False),
    ]
    for person_id, name, username, system_role, is_tech_admin in people:
        db.add(models.Person(id=person_id, name=name, system_role=system_role, is_active=True))
        db.add(
            models.Account(
                username=username,
                password_hash="x",
                person_id=person_id,
                status="active",
                is_tech_admin=is_tech_admin,
            )
        )

    db.add(
        models.Project(
            id=1,
            name="Characterization Project",
            status=lifecycle,
            is_active=lifecycle == "active",
            objectives="Objective" if lifecycle == "draft" else "",
            start_date="2026-09-01" if lifecycle == "draft" else "",
        )
    )
    for person_id, role in [(3, "project_ceo"), (4, "owner"), (5, "coordinator"), (6, "member")]:
        db.add(models.ProjectMember(project_id=1, person_id=person_id, person_name_snapshot="", role=role))
    db.commit()
    return db


def _close_payload() -> schemas.ProjectCloseRequestCreatePayload:
    return schemas.ProjectCloseRequestCreatePayload(
        summary="Done",
        objective_result="Done",
        unfinished_items=[],
        remaining_risks=[],
        handover_plan="Done",
        retrospective="Done",
    )


def _assert_denial(call, *, status: int = 403, detail: str | None = None) -> None:
    with pytest.raises(HTTPException) as exc:
        call()
    assert exc.value.status_code == status
    if detail is not None:
        assert exc.value.detail == detail


def test_project_view_is_limited_to_project_members_or_global_admin():
    db = _seed()
    assert len(list_members(1, current_user="member", db=db)) == 4
    _assert_denial(
        lambda: list_members(1, current_user="outsider", db=db),
        detail="permission denied — 仅项目成员可查看",
    )


def test_create_and_dispatch_keep_company_management_boundary():
    create_db = _seed()
    created = create_project(schemas.ProjectCreatePayload(name="Created"), current_user="company_ceo", db=create_db)
    assert created["name"] == "Created"

    _assert_denial(
        lambda: create_project(schemas.ProjectCreatePayload(name="Rejected"), current_user="owner", db=_seed()),
        detail="仅公司管理或超级管理员可执行此操作",
    )

    dispatch_db = _seed(lifecycle="draft")
    assert dispatch_project(1, current_user="company_ceo", db=dispatch_db)["status"] == "dispatched"
    _assert_denial(
        lambda: dispatch_project(1, current_user="owner", db=_seed(lifecycle="draft")),
        detail="仅公司管理或超级管理员可执行此操作",
    )


def test_company_ceo_cannot_review_start_as_project_coach():
    _assert_denial(
        lambda: approve_project(1, current_user="company_ceo", db=_seed(lifecycle="pending_review")),
        detail="仅企业教练或超级管理员可执行此操作",
    )


def test_owner_submit_requires_owner_or_super_admin():
    _assert_denial(
        lambda: owner_submit_project_profile(
            1,
            schemas.ProjectProfilePayload(objectives="Updated"),
            current_user="member",
            db=_seed(lifecycle="dispatched"),
        ),
        detail="permission denied",
    )


def test_member_change_request_keeps_owner_and_coach_requesters():
    payload = schemas.MemberChangeRequestPayload(target_person_id=7, to_role="member", reason="Need help")
    coach_db = _seed()
    assert create_member_change_request(1, payload, current_user="coach", db=coach_db)["status"] == "approved"
    _assert_denial(
        lambda: create_member_change_request(1, payload, current_user="company_ceo", db=_seed()),
        detail="仅项目负责人或企业教练可发起成员变更申请。",
    )


def test_close_request_requires_original_project_owner():
    _assert_denial(
        lambda: create_project_close_request(1, _close_payload(), current_user="member", db=_seed()),
        detail="仅项目负责人或超级管理员可执行此操作",
    )
    owner_db = _seed()
    assert create_project_close_request(1, _close_payload(), current_user="owner", db=owner_db)["status"] == "pending"


def test_company_ceo_cannot_review_close_request():
    db = _seed()
    request = create_project_close_request(1, _close_payload(), current_user="owner", db=db)
    _assert_denial(
        lambda: approve_project_close_request(
            1,
            request["id"],
            schemas.ProjectCloseReviewPayload(),
            current_user="company_ceo",
            db=db,
        ),
        detail="仅企业教练或超级管理员可执行此操作",
    )


def test_archive_delete_and_kickoff_are_technical_admin_only():
    _assert_denial(
        lambda: archive_project(1, current_user="company_ceo", db=_seed(lifecycle="ended")),
        detail="项目归档需提交公司管理审核。",
    )
    _assert_denial(
        lambda: delete_project(
            1,
            schemas.ProjectDeletePayload(confirm_name="Characterization Project", confirm_phrase="永久删除"),
            current_user="company_ceo",
            db=_seed(),
        ),
        detail="仅超级管理员可执行此操作",
    )
    _assert_denial(
        lambda: kickoff_project(1, current_user="company_ceo", db=_seed()),
        detail="仅超级管理员可执行此操作",
    )


def test_source_edit_is_restricted_after_dispatch():
    _assert_denial(
        lambda: add_member(
            1,
            schemas.ProjectMemberPayload(person_id=7, role="member"),
            current_user="company_ceo",
            db=_seed(lifecycle="active"),
        ),
        detail="项目已下发，当前仅支持查看。如需调整，请走变更申请流程。",
    )


def test_get_project_uses_access_service(monkeypatch):
    db = _seed()
    calls: list[str] = []

    def access_spy(current_user, project, action, db, **kwargs):
        calls.append(action)
        return SimpleNamespace(
            context=projects.get_user_context_from_db(current_user, db),
            subject=SimpleNamespace(project_roles=frozenset()),
            resource=SimpleNamespace(),
            role_source="project_members",
        )

    monkeypatch.setattr(projects, "authorize_project_action", access_spy, raising=False)

    projects.get_project(1, current_user="member", db=db)

    assert calls == [A_VIEW]


def test_global_and_lifecycle_endpoints_use_access_services(monkeypatch):
    global_calls: list[str] = []
    project_calls: list[str] = []

    def global_spy(current_user, action, db):
        global_calls.append(action)
        return SimpleNamespace(context=projects.get_user_context_from_db(current_user, db))

    def project_spy(current_user, project, action, db, **kwargs):
        project_calls.append(action)
        return SimpleNamespace(
            context=projects.get_user_context_from_db(current_user, db),
            subject=SimpleNamespace(is_tech_admin=current_user == "admin", project_roles=frozenset()),
        )

    monkeypatch.setattr(projects, "authorize_global_project_action", global_spy, raising=False)
    monkeypatch.setattr(projects, "authorize_project_action", project_spy, raising=False)

    create_project(schemas.ProjectCreatePayload(name="Created by spy"), current_user="company_ceo", db=_seed())
    batch_import_projects(schemas.ProjectBatchImportPayload(rows=[]), current_user="admin", db=_seed())
    dispatch_project(1, current_user="company_ceo", db=_seed(lifecycle="draft"))
    owner_submit_project_profile(
        1,
        schemas.ProjectProfilePayload(
            objectives="Updated",
            work_progress_draft=[
                schemas.ProjectWorkProgressTaskDraft(
                    title="Workstream",
                    owner="Owner",
                    subtasks=[schemas.ProjectWorkProgressSubTaskDraft(title="Task", assignee="Member")],
                )
            ],
        ),
        current_user="owner",
        db=_seed(lifecycle="dispatched"),
    )
    return_project(1, current_user="coach", db=_seed())
    approve_project(1, current_user="coach", db=_seed())
    kickoff_project(1, current_user="admin", db=_seed())

    assert global_calls == [A_CREATE, A_BATCH_IMPORT, A_TECHNICAL_KICKOFF]
    assert project_calls == [A_DISPATCH, A_OWNER_SUBMIT, A_REVIEW_START, A_REVIEW_START]


def test_terminal_endpoints_use_access_services(monkeypatch):
    global_calls: list[str] = []
    project_calls: list[tuple[str, dict]] = []

    def global_spy(current_user, action, db):
        global_calls.append(action)
        return SimpleNamespace(context=projects.get_user_context_from_db(current_user, db))

    def project_spy(current_user, project, action, db, **kwargs):
        project_calls.append((action, kwargs))
        roles = {"project_ceo"} if current_user == "coach" else {"owner"}
        return SimpleNamespace(
            context=projects.get_user_context_from_db(current_user, db),
            subject=SimpleNamespace(
                is_tech_admin=current_user == "admin",
                project_roles=frozenset(roles),
            ),
        )

    monkeypatch.setattr(projects, "authorize_global_project_action", global_spy, raising=False)
    monkeypatch.setattr(projects, "authorize_project_action", project_spy, raising=False)
    monkeypatch.setattr(project_close_workflow, "authorize_project_action", project_spy)

    close_db = _seed()
    request = create_project_close_request(1, _close_payload(), current_user="owner", db=close_db)
    update_project_close_request(
        1,
        request["id"],
        schemas.ProjectCloseRequestUpdatePayload(summary="Updated"),
        current_user="owner",
        db=close_db,
    )
    cancel_project_close_request(1, request["id"], current_user="owner", db=close_db)

    review_db = _seed()
    review_request = create_project_close_request(1, _close_payload(), current_user="owner", db=review_db)
    approve_project_close_request(
        1,
        review_request["id"],
        schemas.ProjectCloseReviewPayload(),
        current_user="coach",
        db=review_db,
    )

    archive_project(1, current_user="admin", db=_seed(lifecycle="ended"))
    delete_project(
        1,
        schemas.ProjectDeletePayload(confirm_name="Characterization Project", confirm_phrase="永久删除"),
        current_user="admin",
        db=_seed(),
    )

    assert [action for action, _ in project_calls] == [
        A_REQUEST_CLOSE,
        A_EDIT_CLOSE_REQUEST,
        A_CANCEL_CLOSE_REQUEST,
        A_REQUEST_CLOSE,
        A_REVIEW_CLOSE_REQUEST,
    ]
    assert global_calls == [A_ARCHIVE, A_DELETE]
    assert project_calls[1][1]["requester_person_id"] == 4
