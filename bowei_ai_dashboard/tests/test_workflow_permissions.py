from dataclasses import replace

import pytest

from app.domain.project_permissions import PermissionDecision, ProjectPermissionSubject
from app.domain.workflow_permissions import (
    A_CONFIRMATION_CEO_DECIDE,
    A_CONFIRMATION_COORDINATOR_FEEDBACK,
    A_CONFIRMATION_REVIEW,
    A_CONFIRMATION_RESUBMIT,
    A_CONFIRMATION_VIEW,
    A_MEETING_APPLY_CHANGES,
    A_MEETING_CREATE,
    A_MEETING_KICKOFF_DECIDE,
    A_MEETING_PROGRESS_REVIEW,
    A_MEETING_PUBLISH,
    A_MEETING_VIEW,
    WorkflowPermissionResource,
    decide_workflow_action,
)
from app.services import policy


ADMIN = ProjectPermissionSubject(is_tech_admin=True, person_id=1)
COMPANY_CEO = ProjectPermissionSubject(is_company_ceo=True, person_id=2)
OWNER = ProjectPermissionSubject(person_id=3, project_roles=frozenset({"owner"}))
COORDINATOR = ProjectPermissionSubject(person_id=4, project_roles=frozenset({"coordinator"}))
MEMBER = ProjectPermissionSubject(person_id=5, project_roles=frozenset({"member"}))
PROJECT_CEO = ProjectPermissionSubject(person_id=6, project_roles=frozenset({"project_ceo"}))
OUTSIDER = ProjectPermissionSubject(person_id=7)

PROJECT = WorkflowPermissionResource(project_id=10)


@pytest.mark.parametrize(
    ("action", "subject", "resource", "allowed"),
    [
        (A_CONFIRMATION_VIEW, ADMIN, PROJECT, True),
        (A_CONFIRMATION_VIEW, COMPANY_CEO, PROJECT, True),
        (A_CONFIRMATION_VIEW, OWNER, PROJECT, True),
        (A_CONFIRMATION_VIEW, COORDINATOR, PROJECT, True),
        (A_CONFIRMATION_VIEW, OUTSIDER, PROJECT, False),
        (A_CONFIRMATION_REVIEW, OWNER, PROJECT, True),
        (A_CONFIRMATION_REVIEW, COORDINATOR, PROJECT, False),
        (A_CONFIRMATION_COORDINATOR_FEEDBACK, COORDINATOR, PROJECT, True),
        (A_CONFIRMATION_COORDINATOR_FEEDBACK, OWNER, PROJECT, False),
        (A_CONFIRMATION_CEO_DECIDE, PROJECT_CEO, PROJECT, True),
        (A_CONFIRMATION_CEO_DECIDE, COMPANY_CEO, PROJECT, False),
        (A_MEETING_VIEW, COMPANY_CEO, PROJECT, True),
        (A_MEETING_VIEW, MEMBER, PROJECT, True),
        (A_MEETING_VIEW, OUTSIDER, PROJECT, False),
        (A_MEETING_CREATE, OWNER, PROJECT, True),
        (A_MEETING_CREATE, COORDINATOR, PROJECT, True),
        (A_MEETING_CREATE, MEMBER, PROJECT, True),
        (A_MEETING_CREATE, PROJECT_CEO, PROJECT, False),
        (A_MEETING_PUBLISH, OWNER, PROJECT, True),
        (A_MEETING_PUBLISH, COORDINATOR, PROJECT, False),
        (A_MEETING_PROGRESS_REVIEW, COORDINATOR, PROJECT, True),
        (A_MEETING_PROGRESS_REVIEW, MEMBER, PROJECT, False),
        (A_MEETING_KICKOFF_DECIDE, PROJECT_CEO, PROJECT, True),
        (A_MEETING_KICKOFF_DECIDE, COMPANY_CEO, PROJECT, False),
    ],
)
def test_workflow_action_matrix(action, subject, resource, allowed):
    decision = decide_workflow_action(subject, resource, action)
    assert isinstance(decision, PermissionDecision)
    assert decision.allowed is allowed


def test_confirmation_resubmit_requires_submitter_identity():
    own = replace(PROJECT, submitter_person_id=MEMBER.person_id)
    other = replace(PROJECT, submitter_person_id=OWNER.person_id)

    assert decide_workflow_action(MEMBER, own, A_CONFIRMATION_RESUBMIT).allowed
    assert not decide_workflow_action(MEMBER, other, A_CONFIRMATION_RESUBMIT).allowed
    assert not decide_workflow_action(ADMIN, own, A_CONFIRMATION_RESUBMIT).allowed


def test_meeting_edit_can_use_creator_identity_without_owner_role():
    resource = replace(PROJECT, creator_person_id=MEMBER.person_id)

    from app.domain.workflow_permissions import A_MEETING_EDIT

    assert decide_workflow_action(MEMBER, resource, A_MEETING_EDIT).allowed
    assert not decide_workflow_action(OUTSIDER, resource, A_MEETING_EDIT).allowed


def test_apply_changes_requires_project_owner_or_admin():
    assert decide_workflow_action(ADMIN, PROJECT, A_MEETING_APPLY_CHANGES).allowed
    assert decide_workflow_action(OWNER, PROJECT, A_MEETING_APPLY_CHANGES).allowed
    decision = decide_workflow_action(COORDINATOR, PROJECT, A_MEETING_APPLY_CHANGES)
    assert not decision.allowed
    assert decision.status_code == 403


def test_context_adapter_translates_project_roles_to_workflow_subject(monkeypatch):
    context = {
        "is_tech_admin": False,
        "is_ceo": False,
        "person_id": OWNER.person_id,
    }
    monkeypatch.setattr(policy, "user_roles_in_project", lambda *_args: {"owner"})

    decision = policy.decide_workflow_for_project(
        context,
        project_id=PROJECT.project_id,
        action=A_CONFIRMATION_REVIEW,
        db=object(),
    )

    assert decision.allowed


def test_context_adapter_preserves_company_ceo_as_global_reader(monkeypatch):
    context = {
        "is_tech_admin": False,
        "is_ceo": True,
        "person_id": COMPANY_CEO.person_id,
    }
    monkeypatch.setattr(policy, "user_roles_in_project", lambda *_args: set())

    decision = policy.decide_workflow_for_project(
        context,
        project_id=None,
        action=A_MEETING_VIEW,
        db=object(),
    )

    assert decision.allowed
