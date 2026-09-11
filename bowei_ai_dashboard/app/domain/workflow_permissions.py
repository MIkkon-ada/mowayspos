"""Pure permission decisions for confirmation-center and meeting workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .project_permissions import PermissionDecision, ProjectPermissionSubject


A_CONFIRMATION_VIEW = "confirmation.view"
A_CONFIRMATION_REVIEW = "confirmation.review"
A_CONFIRMATION_COORDINATOR_FEEDBACK = "confirmation.coordinator_feedback"
A_CONFIRMATION_ESCALATE = "confirmation.escalate"
A_CONFIRMATION_CEO_DECIDE = "confirmation.ceo_decide"
A_CONFIRMATION_RESUBMIT = "confirmation.resubmit"
A_CONFIRMATION_WITHDRAW = "confirmation.withdraw"

A_MEETING_VIEW = "meeting.view"
A_MEETING_CREATE = "meeting.create"
A_MEETING_EDIT = "meeting.edit"
A_MEETING_PUBLISH = "meeting.publish"
A_MEETING_REVIEW_CHANGES = "meeting.review_changes"
A_MEETING_APPLY_CHANGES = "meeting.apply_changes"
A_MEETING_PROGRESS_REVIEW = "meeting.progress_review"
A_MEETING_KICKOFF_SUBMIT = "meeting.kickoff_submit"
A_MEETING_KICKOFF_DECIDE = "meeting.kickoff_decide"

WorkflowAction = Literal[
    "confirmation.view",
    "confirmation.review",
    "confirmation.coordinator_feedback",
    "confirmation.escalate",
    "confirmation.ceo_decide",
    "confirmation.resubmit",
    "confirmation.withdraw",
    "meeting.view",
    "meeting.create",
    "meeting.edit",
    "meeting.publish",
    "meeting.review_changes",
    "meeting.apply_changes",
    "meeting.progress_review",
    "meeting.kickoff_submit",
    "meeting.kickoff_decide",
]

WORKFLOW_ACTIONS = frozenset(
    {
        A_CONFIRMATION_VIEW,
        A_CONFIRMATION_REVIEW,
        A_CONFIRMATION_COORDINATOR_FEEDBACK,
        A_CONFIRMATION_ESCALATE,
        A_CONFIRMATION_CEO_DECIDE,
        A_CONFIRMATION_RESUBMIT,
        A_CONFIRMATION_WITHDRAW,
        A_MEETING_VIEW,
        A_MEETING_CREATE,
        A_MEETING_EDIT,
        A_MEETING_PUBLISH,
        A_MEETING_REVIEW_CHANGES,
        A_MEETING_APPLY_CHANGES,
        A_MEETING_PROGRESS_REVIEW,
        A_MEETING_KICKOFF_SUBMIT,
        A_MEETING_KICKOFF_DECIDE,
    }
)


@dataclass(frozen=True)
class WorkflowPermissionResource:
    project_id: int | None = None
    submitter_person_id: int | None = None
    creator_person_id: int | None = None


def _allow() -> PermissionDecision:
    return PermissionDecision(True)


def _deny(code: str, detail: str) -> PermissionDecision:
    return PermissionDecision(False, status_code=403, code=code, detail=detail)


def _has_role(subject: ProjectPermissionSubject, *roles: str) -> bool:
    return bool(subject.project_roles.intersection(roles))


def decide_workflow_action(
    subject: ProjectPermissionSubject,
    resource: WorkflowPermissionResource,
    action: WorkflowAction | str,
) -> PermissionDecision:
    """Decide a workflow action without loading application state."""
    if action not in WORKFLOW_ACTIONS:
        raise ValueError(f"unknown workflow action: {action}")

    # Resubmission is deliberately actor-bound: the technical administrator's
    # existing withdrawal override must not silently become a resubmission
    # override.
    if action == A_CONFIRMATION_RESUBMIT:
        return (
            _allow()
            if subject.person_id is not None
            and subject.person_id == resource.submitter_person_id
            else _deny("WORKFLOW_ACTOR_REQUIRED", "仅原提交人可以重新提交")
        )

    if subject.is_tech_admin:
        return _allow()

    if action == A_CONFIRMATION_VIEW:
        if subject.is_company_ceo or _has_role(subject, "owner", "coordinator", "project_ceo"):
            return _allow()
        if subject.person_id is not None and subject.person_id == resource.submitter_person_id:
            return _allow()
        return _deny("WORKFLOW_ACCESS_DENIED", "permission denied")

    if action == A_CONFIRMATION_REVIEW:
        return (
            _allow()
            if _has_role(subject, "owner")
            else _deny("WORKFLOW_ACTION_DENIED", "仅项目负责人或超级管理员可执行此操作")
        )

    if action == A_CONFIRMATION_COORDINATOR_FEEDBACK:
        return (
            _allow()
            if _has_role(subject, "coordinator")
            else _deny("WORKFLOW_ACTION_DENIED", "仅项目统筹人或管理员可反馈")
        )

    if action == A_CONFIRMATION_ESCALATE:
        return (
            _allow()
            if _has_role(subject, "owner")
            else _deny("WORKFLOW_ACTION_DENIED", "仅项目负责人或超级管理员可上报企业教练")
        )

    if action == A_CONFIRMATION_CEO_DECIDE:
        return (
            _allow()
            if _has_role(subject, "project_ceo")
            else _deny("WORKFLOW_ACTION_DENIED", "仅该项目企业教练或管理员可批示")
        )

    if action == A_CONFIRMATION_WITHDRAW:
        return (
            _allow()
            if subject.person_id is not None and subject.person_id == resource.submitter_person_id
            else _deny("WORKFLOW_ACTOR_REQUIRED", "只有原提交人或管理员可以撤回")
        )

    if action == A_MEETING_VIEW:
        return (
            _allow()
            if subject.is_company_ceo or _has_role(subject, "owner", "coordinator", "member", "project_ceo")
            else _deny("WORKFLOW_ACCESS_DENIED", "permission denied")
        )

    if action == A_MEETING_CREATE:
        return (
            _allow()
            if _has_role(subject, "owner", "coordinator", "member")
            else _deny("WORKFLOW_ACTION_DENIED", "仅项目成员可以创建会议")
        )

    if action == A_MEETING_EDIT:
        return (
            _allow()
            if _has_role(subject, "owner")
            or (subject.person_id is not None and subject.person_id == resource.creator_person_id)
            else _deny("WORKFLOW_ACTION_DENIED", "仅会议创建人或项目负责人可以编辑")
        )

    if action in {A_MEETING_PUBLISH, A_MEETING_REVIEW_CHANGES, A_MEETING_APPLY_CHANGES}:
        return (
            _allow()
            if _has_role(subject, "owner")
            else _deny("WORKFLOW_ACTION_DENIED", "仅项目负责人或管理员可执行此操作")
        )

    if action == A_MEETING_PROGRESS_REVIEW:
        return (
            _allow()
            if _has_role(subject, "owner", "coordinator")
            else _deny("WORKFLOW_ACTION_DENIED", "仅项目负责人或项目统筹可审核会议进展")
        )

    if action == A_MEETING_KICKOFF_SUBMIT:
        return (
            _allow()
            if _has_role(subject, "owner")
            else _deny("WORKFLOW_ACTION_DENIED", "仅项目负责人可以提交启动会审核包")
        )

    if action == A_MEETING_KICKOFF_DECIDE:
        return (
            _allow()
            if _has_role(subject, "project_ceo")
            else _deny("WORKFLOW_ACTION_DENIED", "仅企业教练可以确认启动会")
        )

    raise AssertionError(f"unhandled workflow action: {action}")
