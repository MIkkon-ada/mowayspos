from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


A_VIEW = "project.view"
A_CREATE = "project.create"
A_BATCH_IMPORT = "project.batch_import"
A_EDIT_SOURCE = "project.edit_source"
A_MANAGE_MEMBERS_DIRECT = "project.manage_members_direct"
A_REQUEST_MEMBER_CHANGE = "project.request_member_change"
A_REVIEW_MEMBER_CHANGE = "project.review_member_change"
A_DISPATCH = "project.dispatch"
A_OWNER_SUBMIT = "project.owner_submit"
A_REVIEW_START = "project.review_start"
A_REQUEST_CLOSE = "project.request_close"
A_EDIT_CLOSE_REQUEST = "project.edit_close_request"
A_CANCEL_CLOSE_REQUEST = "project.cancel_close_request"
A_REVIEW_CLOSE_REQUEST = "project.review_close_request"
A_ARCHIVE = "project.archive"
A_DELETE = "project.delete"
A_TECHNICAL_KICKOFF = "project.technical_kickoff"

ProjectAction = Literal[
    "project.view",
    "project.create",
    "project.batch_import",
    "project.edit_source",
    "project.manage_members_direct",
    "project.request_member_change",
    "project.review_member_change",
    "project.dispatch",
    "project.owner_submit",
    "project.review_start",
    "project.request_close",
    "project.edit_close_request",
    "project.cancel_close_request",
    "project.review_close_request",
    "project.archive",
    "project.delete",
    "project.technical_kickoff",
]

PROJECT_ROLES = frozenset({"owner", "coordinator", "member", "project_ceo"})
PROJECT_ACTIONS = frozenset(
    {
        A_VIEW,
        A_CREATE,
        A_BATCH_IMPORT,
        A_EDIT_SOURCE,
        A_MANAGE_MEMBERS_DIRECT,
        A_REQUEST_MEMBER_CHANGE,
        A_REVIEW_MEMBER_CHANGE,
        A_DISPATCH,
        A_OWNER_SUBMIT,
        A_REVIEW_START,
        A_REQUEST_CLOSE,
        A_EDIT_CLOSE_REQUEST,
        A_CANCEL_CLOSE_REQUEST,
        A_REVIEW_CLOSE_REQUEST,
        A_ARCHIVE,
        A_DELETE,
        A_TECHNICAL_KICKOFF,
    }
)


@dataclass(frozen=True)
class ProjectPermissionSubject:
    is_tech_admin: bool = False
    is_company_ceo: bool = False
    person_id: int | None = None
    project_roles: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ProjectPermissionResource:
    project_id: int | None = None
    lifecycle: str = ""
    requester_person_id: int | None = None


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    status_code: int = 200
    code: str = ""
    detail: str = ""


_ADMIN_ONLY = frozenset({A_BATCH_IMPORT, A_ARCHIVE, A_DELETE, A_TECHNICAL_KICKOFF})
_COMPANY_MANAGED = frozenset({A_CREATE, A_DISPATCH})
_COACH_REVIEW = frozenset({A_REVIEW_MEMBER_CHANGE, A_REVIEW_START, A_REVIEW_CLOSE_REQUEST})
_OWNER_ACTIONS = frozenset({A_OWNER_SUBMIT, A_REQUEST_CLOSE})


def _allow() -> PermissionDecision:
    return PermissionDecision(True)


def _deny(code: str, detail: str, status_code: int = 403) -> PermissionDecision:
    return PermissionDecision(False, status_code=status_code, code=code, detail=detail)


def _admin_only_detail(action: str) -> str:
    if action == A_ARCHIVE:
        return "项目归档需提交公司管理审核。"
    return "仅超级管理员可执行此操作"


def decide_project_action(
    subject: ProjectPermissionSubject,
    resource: ProjectPermissionResource,
    action: ProjectAction | str,
) -> PermissionDecision:
    """Return the project-domain role decision without loading application state."""
    if action not in PROJECT_ACTIONS:
        raise ValueError(f"unknown project action: {action}")

    roles = subject.project_roles & PROJECT_ROLES
    if subject.is_tech_admin:
        return _allow()
    if action == A_VIEW:
        return (
            _allow()
            if subject.is_company_ceo or roles
            else _deny("PROJECT_ACCESS_DENIED", "permission denied — 仅项目成员可查看")
        )
    if action in _ADMIN_ONLY:
        return _deny("PROJECT_ACTION_DENIED", _admin_only_detail(action))
    if action in _COMPANY_MANAGED:
        return (
            _allow()
            if subject.is_company_ceo
            else _deny("PROJECT_ACTION_DENIED", "仅公司管理或超级管理员可执行此操作")
        )
    if action in {A_EDIT_SOURCE, A_MANAGE_MEMBERS_DIRECT}:
        if subject.is_company_ceo and resource.lifecycle == "draft":
            return _allow()
        return _deny("PROJECT_ACTION_DENIED", "项目已下发，当前仅支持查看。如需调整，请走变更申请流程。")
    if action == A_REQUEST_MEMBER_CHANGE:
        return (
            _allow()
            if roles & {"owner", "project_ceo"}
            else _deny("PROJECT_ACTION_DENIED", "仅项目负责人或企业教练可发起成员变更申请。")
        )
    if action in _COACH_REVIEW:
        return (
            _allow()
            if "project_ceo" in roles
            else _deny("PROJECT_ACTION_DENIED", "仅企业教练或超级管理员可执行此操作")
        )
    if action in _OWNER_ACTIONS:
        return (
            _allow()
            if "owner" in roles
            else _deny("PROJECT_ACTION_DENIED", "仅项目负责人或超级管理员可执行此操作")
        )
    if action in {A_EDIT_CLOSE_REQUEST, A_CANCEL_CLOSE_REQUEST}:
        owned = (
            subject.person_id is not None
            and subject.person_id == resource.requester_person_id
            and "owner" in roles
        )
        return (
            _allow()
            if owned
            else _deny("PROJECT_RESOURCE_OWNER_REQUIRED", "仅原申请人或超级管理员可执行此操作")
        )
    raise AssertionError(f"unhandled project action: {action}")
