from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.permissions import get_person_id, get_user_context_from_db
from app.routers.issues import _is_issue_related_to_user, assign_helper, get_issue, list_issues


def test_issue_model_has_stable_helper_person_id():
    assert "helper_person_id" in models.Issue.__table__.columns


def test_name_only_login_does_not_guess_between_duplicate_people(issue_identity_db):
    context = get_user_context_from_db("同名成员", issue_identity_db)

    assert context["person_id"] is None
    assert get_person_id("同名成员", issue_identity_db) is None


@pytest.fixture
def issue_identity_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    people = [
        models.Person(id=1, name="同名成员", system_role="normal_member", is_active=True),
        models.Person(id=2, name="同名成员", system_role="normal_member", is_active=True),
        models.Person(id=3, name="唯一成员", system_role="normal_member", is_active=True),
        models.Person(id=4, name="项目负责人", system_role="normal_member", is_active=True),
    ]
    db.add_all(people)
    db.add_all(
        [
            models.Account(username="member_one", password_hash="x", person_id=1, status="active"),
            models.Account(username="member_two", password_hash="x", person_id=2, status="active"),
            models.Account(username="unique_member", password_hash="x", person_id=3, status="active"),
            models.Account(username="project_owner", password_hash="x", person_id=4, status="active"),
            models.Project(id=1, name="问题身份项目", status="active", is_active=True),
            models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="同名成员", role="member"),
            models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="同名成员", role="member"),
            models.ProjectMember(project_id=1, person_id=3, person_name_snapshot="唯一成员", role="member"),
            models.ProjectMember(project_id=1, person_id=4, person_name_snapshot="项目负责人", role="owner"),
        ]
    )
    db.add_all(
        [
            models.Issue(id=1, project_id=1, description="属于成员一", owner="同名成员", owner_id=1, reporter="reporter_one"),
            models.Issue(id=2, project_id=1, description="属于成员二", owner="同名成员", owner_id=2, reporter="reporter_two"),
            models.Issue(id=3, project_id=1, description="归属不明确的旧问题", owner="同名成员", owner_id=None, reporter="old_reporter"),
            models.Issue(id=4, project_id=1, description="唯一历史负责人", owner="唯一成员", owner_id=None, reporter="old_reporter"),
            models.Issue(id=5, project_id=1, description="协助成员一", owner="项目负责人", owner_id=None, helper="同名成员", helper_person_id=1, reporter="reporter_other"),
            models.Issue(id=6, project_id=1, description="协助成员二", owner="项目负责人", owner_id=None, helper="同名成员", helper_person_id=2, reporter="reporter_other"),
            models.Issue(id=7, project_id=1, description="ID 已指向成员二但旧文本像成员一账号", owner="member_one", owner_id=2, reporter="reporter_other"),
        ]
    )
    db.commit()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_issue_list_scopes_same_name_owner_by_person_id(issue_identity_db):
    rows = list_issues(project_id=1, current_user="member_one", db=issue_identity_db)

    assert {row["id"] for row in rows} == {1, 5}


def test_bound_issue_owner_id_overrides_matching_account_text(issue_identity_db):
    rows = list_issues(project_id=1, current_user="member_one", db=issue_identity_db)

    assert 7 not in {row["id"] for row in rows}


def test_issue_detail_denies_same_name_different_person(issue_identity_db):
    with pytest.raises(HTTPException) as exc:
        get_issue(row_id=2, current_user="member_one", db=issue_identity_db)

    assert exc.value.status_code == 403


def test_issue_list_hides_ambiguous_legacy_owner_name(issue_identity_db):
    rows = list_issues(project_id=1, current_user="member_one", db=issue_identity_db)

    assert 3 not in {row["id"] for row in rows}


def test_issue_list_keeps_unique_legacy_owner_compatibility(issue_identity_db):
    rows = list_issues(project_id=1, current_user="unique_member", db=issue_identity_db)

    assert [row["id"] for row in rows] == [4]


def test_issue_helper_relation_uses_helper_person_id(issue_identity_db):
    issue = SimpleNamespace(
        reporter="reporter",
        owner="",
        owner_id=None,
        helper="旧显示名",
        helper_person_id=3,
    )

    assert _is_issue_related_to_user(issue, "unique_member", 3, "唯一成员", issue_identity_db)


def test_assign_helper_persists_selected_person_id_and_canonical_name(issue_identity_db):
    result = assign_helper(
        row_id=1,
        payload=schemas.AssignHelperRequest(helper="", helper_person_id=2),
        current_user="project_owner",
        db=issue_identity_db,
    )

    assert result["helper_person_id"] == 2
    assert result["helper"] == "同名成员"


def test_issue_list_scopes_same_name_helper_by_person_id(issue_identity_db):
    rows = list_issues(project_id=1, current_user="member_one", db=issue_identity_db)

    assert 5 in {row["id"] for row in rows}
    assert 6 not in {row["id"] for row in rows}


def test_issue_detail_denies_same_name_different_helper(issue_identity_db):
    with pytest.raises(HTTPException) as exc:
        get_issue(row_id=6, current_user="member_one", db=issue_identity_db)

    assert exc.value.status_code == 403


def test_name_fallback_does_not_override_another_helpers_person_id(issue_identity_db):
    issue_identity_db.get(models.Person, 2).is_active = False
    issue_identity_db.commit()
    issue = SimpleNamespace(
        reporter="reporter_other",
        owner="项目负责人",
        owner_id=None,
        helper="同名成员",
        helper_person_id=2,
    )

    assert not _is_issue_related_to_user(issue, "member_one", 1, "同名成员", issue_identity_db)


def test_issue_list_name_fallback_does_not_override_helper_person_id(issue_identity_db):
    issue_identity_db.get(models.Person, 2).is_active = False
    issue_identity_db.commit()

    rows = list_issues(project_id=1, current_user="member_one", db=issue_identity_db)

    assert 6 not in {row["id"] for row in rows}
