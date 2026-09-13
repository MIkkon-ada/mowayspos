from dataclasses import replace

import pytest

from app.domain.project_permissions import (
    A_ARCHIVE,
    A_BATCH_IMPORT,
    A_CANCEL_CLOSE_REQUEST,
    A_CREATE,
    A_DELETE,
    A_DISPATCH,
    A_EDIT_CLOSE_REQUEST,
    A_EDIT_SOURCE,
    A_MANAGE_MEMBERS_DIRECT,
    A_OWNER_SUBMIT,
    A_REQUEST_CLOSE,
    A_REQUEST_MEMBER_CHANGE,
    A_REVIEW_CLOSE_REQUEST,
    A_REVIEW_MEMBER_CHANGE,
    A_REVIEW_START,
    A_TECHNICAL_KICKOFF,
    A_VIEW,
    ProjectPermissionResource,
    ProjectPermissionSubject,
    decide_project_action,
)


ADMIN = ProjectPermissionSubject(is_tech_admin=True)
COMPANY_CEO = ProjectPermissionSubject(is_company_ceo=True, person_id=2)
COACH = ProjectPermissionSubject(person_id=3, project_roles=frozenset({"project_ceo"}))
OWNER = ProjectPermissionSubject(person_id=4, project_roles=frozenset({"owner"}))
MEMBER = ProjectPermissionSubject(person_id=5, project_roles=frozenset({"member"}))
OUTSIDER = ProjectPermissionSubject(person_id=6)
ACTIVE = ProjectPermissionResource(project_id=1, lifecycle="active")


@pytest.mark.parametrize(
    ("action", "subject", "allowed"),
    [
        (A_VIEW, ADMIN, True),
        (A_VIEW, COMPANY_CEO, True),
        (A_VIEW, MEMBER, True),
        (A_VIEW, OUTSIDER, False),
        (A_CREATE, COMPANY_CEO, True),
        (A_CREATE, OWNER, False),
        (A_BATCH_IMPORT, ADMIN, True),
        (A_BATCH_IMPORT, COMPANY_CEO, False),
        (A_DISPATCH, COMPANY_CEO, True),
        (A_DISPATCH, OWNER, False),
        (A_MANAGE_MEMBERS_DIRECT, COMPANY_CEO, False),
        (A_OWNER_SUBMIT, OWNER, True),
        (A_OWNER_SUBMIT, MEMBER, False),
        (A_REVIEW_START, COACH, True),
        (A_REVIEW_START, COMPANY_CEO, False),
        (A_REQUEST_MEMBER_CHANGE, OWNER, True),
        (A_REQUEST_MEMBER_CHANGE, COACH, True),
        (A_REVIEW_MEMBER_CHANGE, COACH, True),
        (A_REVIEW_MEMBER_CHANGE, OWNER, False),
        (A_REQUEST_CLOSE, OWNER, True),
        (A_REVIEW_CLOSE_REQUEST, COACH, True),
        (A_ARCHIVE, ADMIN, True),
        (A_ARCHIVE, COMPANY_CEO, False),
        (A_DELETE, ADMIN, True),
        (A_TECHNICAL_KICKOFF, ADMIN, True),
    ],
)
def test_project_action_matrix(action, subject, allowed):
    assert decide_project_action(subject, ACTIVE, action).allowed is allowed


def test_company_ceo_can_edit_source_only_in_draft():
    assert decide_project_action(COMPANY_CEO, replace(ACTIVE, lifecycle="draft"), A_EDIT_SOURCE).allowed
    decision = decide_project_action(COMPANY_CEO, ACTIVE, A_EDIT_SOURCE)
    assert not decision.allowed
    assert decision.status_code == 403


def test_close_request_edit_requires_original_owner():
    owned = replace(ACTIVE, requester_person_id=OWNER.person_id)
    other = replace(ACTIVE, requester_person_id=999)
    assert decide_project_action(OWNER, owned, A_EDIT_CLOSE_REQUEST).allowed
    assert decide_project_action(OWNER, owned, A_CANCEL_CLOSE_REQUEST).allowed
    assert not decide_project_action(OWNER, other, A_EDIT_CLOSE_REQUEST).allowed
    assert decide_project_action(ADMIN, other, A_EDIT_CLOSE_REQUEST).allowed


def test_company_ceo_is_not_project_coach():
    assert not decide_project_action(COMPANY_CEO, ACTIVE, A_REVIEW_START).allowed
    assert not decide_project_action(COMPANY_CEO, ACTIVE, A_REVIEW_CLOSE_REQUEST).allowed
