from typing import Any

from pydantic import BaseModel, Field


class UserSubtaskContext(BaseModel):
    id: int
    title: str
    status: str = ""
    parent_key_task: str = ""


class ExtractRequest(BaseModel):
    project_id: int | None = None
    special_project: str | None = None
    source_type: str
    submitter: str | None = None
    title: str | None = None
    transcript_text: str
    human_result: dict[str, Any] | None = None
    edited_suggestion: dict[str, Any] | None = None
    llm_provider: str | None = None
    user_subtasks: list[UserSubtaskContext] | None = None


class ConfirmationSaveRequest(BaseModel):
    human_result: dict[str, Any]


class ConfirmRequest(BaseModel):
    operator: str = "管理员"
    human_result: dict[str, Any] | None = None


class RejectRequest(BaseModel):
    reason: str
    operator: str = "管理员"


class StatusRequest(BaseModel):
    status: str


class ResolveRequest(BaseModel):
    resolution: str = ""
    handler_reply: str = ""


class CloseRequest(BaseModel):
    reason: str = ""
    handler_reply: str = ""


class AssignHelperRequest(BaseModel):
    helper: str


class RequestCeoRequest(BaseModel):
    need_decision_by: str
    note: str = ""


class TaskPayload(BaseModel):
    """重点工作(Workstream)创建/更新参数 — 对应物理表 tasks"""
    project_id: int | None = None
    special_project: str = Field("", max_length=80)  # 项目名镜像字段
    key_task: str = Field(..., max_length=200)        # 重点工作名称
    key_achievement: str = Field("", max_length=200)
    completion_standard: str = ""
    coordinator: str = Field("", max_length=50)
    owner: str = Field("", max_length=50)
    collaborators: str = Field("", max_length=200)
    plan_time: str = Field("", max_length=20)
    status: str = Field("未开始", max_length=20)
    problem_note: str = ""
    achievement_links: str = ""
    source_type: str = Field("人工录入", max_length=40)

# alias：TaskPayload 即 WorkstreamPayload
WorkstreamPayload = TaskPayload


class AchievementSubmissionPayload(BaseModel):
    project_id: int
    related_task_id: int
    name: str = Field(..., max_length=200)
    achievement_type: str = Field("方案", max_length=40)
    version: str = Field("V0.1", max_length=30)
    file_link: str = ""
    scenario: str = ""
    reuse_tag: str = Field("", max_length=80)


class AchievementSubmissionRejectRequest(BaseModel):
    reject_reason: str = ""


class AchievementPayload(BaseModel):
    project_id: int | None = None
    name: str = Field(..., max_length=200)
    achievement_type: str = Field("方案", max_length=40)
    special_project: str = Field("", max_length=80)
    related_task_id: int | None = None
    owner: str = Field("", max_length=50)
    version: str = Field("V0.1", max_length=30)
    file_link: str = ""
    scenario: str = ""
    reuse_tag: str = Field("", max_length=80)
    status: str = Field("草稿", max_length=20)
    source_type: str = Field("人工录入", max_length=40)


class IssuePayload(BaseModel):
    project_id: int | None = None
    issue_type: str = Field("问题", max_length=40)
    description: str
    owner: str = Field("", max_length=50)
    helper: str = Field("", max_length=100)
    priority: str = Field("中", max_length=10)
    status: str = Field("待处理", max_length=20)
    need_decision_by: str = Field("", max_length=50)
    expected_resolve_time: str = Field("", max_length=20)
    resolution: str = ""
    related_task_id: int | None = None
    special_project: str = Field("", max_length=80)
    source_type: str = Field("人工录入", max_length=40)


class PersonPayload(BaseModel):
    name: str = Field(..., max_length=50)
    role: str = Field("", max_length=40)
    system_role: str = Field("normal_member", max_length=40)
    department: str = Field("", max_length=80)
    special_project_duty: str = ""
    permission: str = Field("查看", max_length=40)
    contact: str = Field("", max_length=100)
    is_active: bool = True
    is_admin: bool = False
    coordinated_projects: list[str] = []
    owned_projects: list[str] = []
    collaborated_projects: list[str] = []


class PersonBatchItem(BaseModel):
    name: str
    role: str = ""
    system_role: str = "normal_member"
    department: str = ""
    contact: str = ""


class PersonBatchPayload(BaseModel):
    people: list[PersonBatchItem]


class ProjectPayload(BaseModel):
    name: str
    coordinator: str = ""
    owners: list[str] = []
    collaborators: list[str] = []
    sort_order: int = 0
    is_active: bool = True


class AssignRequest(BaseModel):
    assignee: str
    operator: str = "管理员"


class ResubmitRequest(BaseModel):
    supplement_note: str = ""
    operator: str = ""
    human_result: dict[str, Any] | None = None


class WorkflowNoteRequest(BaseModel):
    note: str = ""
    operator: str = "管理员"


class ProjectMemberPayload(BaseModel):
    person_id: int
    role: str  # project_ceo / owner / coordinator / member
    note: str = ""


class ProjectMemberPatchPayload(BaseModel):
    role: str | None = None
    note: str | None = None


class MemberChangeRequestPayload(BaseModel):
    """发起成员变更申请（本轮仅 add member/coordinator）。"""
    target_person_id: int
    to_role: str  # member / coordinator
    reason: str = ""


class MemberChangeReviewPayload(BaseModel):
    """审核成员变更申请。"""
    review_comment: str = ""


class ProjectCreatePayload(BaseModel):
    name: str = Field(..., max_length=100)
    code: str = Field("", max_length=50)
    description: str = ""
    status: str = Field("draft", max_length=20)
    start_date: str = Field("", max_length=20)
    end_date: str = Field("", max_length=20)
    # 立项扩展字段
    project_type: str = ""          # 博维内部项目 / 博维-客户项目
    client_name: str = ""           # 客户/甲方名称
    background: str = ""            # 项目背景
    objectives: str = ""            # 项目目标
    expected_outcomes: str = ""     # 预期交付物
    lifecycle_status: str = "draft"
    # 初始成员（可选），写入 project_members 并同步旧字段
    project_ceo_ids: list[int] = []
    owner_ids: list[int] = []
    coordinator_ids: list[int] = []
    member_ids: list[int] = []


class BatchImportRow(BaseModel):
    project_name: str
    key_task: str = ""
    key_achievement: str = ""
    completion_standard: str = ""
    coordinator: str = ""
    owner: str = ""
    collaborators: str = ""
    plan_time: str = ""
    status: str = "未开始"
    issue: str = ""


class ProjectBatchImportPayload(BaseModel):
    rows: list[BatchImportRow]


class ProjectPatchPayload(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    status: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    project_type: str | None = None
    client_name: str | None = None
    background: str | None = None
    objectives: str | None = None
    expected_outcomes: str | None = None
    lifecycle_status: str | None = None


class ProjectProfilePayload(BaseModel):
    """负责人填报立项信息（不含名称/状态等管理字段）。"""
    project_type: str | None = None
    client_name: str | None = None
    background: str | None = None
    objectives: str | None = None
    expected_outcomes: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class MeetingPayload(BaseModel):
    project_id: int | None = None
    related_special_project: str = ""
    meeting_type: str = ""
    title: str = ""
    meeting_date: str = ""
    host: str = ""
    participants: str = ""
    transcript_text: str = ""
    summary: str = ""
    task_list_json: str = ""
    decision_items_json: str = ""
    risk_items_json: str = ""
    publish_status: str = "draft"


class MeetingStatusPatch(BaseModel):
    publish_status: str
    reject_reason: str = ""


class SubTaskPayload(BaseModel):
    """关键任务(KeyTask)创建/更新参数 — 对应物理表 subtasks"""
    title: str = Field(..., max_length=200)
    assignee: str = Field(..., max_length=50)
    plan_time: str = Field("", max_length=50)
    status: str = Field("未开始", max_length=20)
    completion_criteria: str = ""
    notes: str = ""

# alias：SubTaskPayload 即 KeyTaskPayload
KeyTaskPayload = SubTaskPayload


class TaskOutlineExtractRequest(BaseModel):
    project_id: int | None = None
    text: str
    llm_provider: str | None = None
    project_names: list[str] = []


class TaskDraft(BaseModel):
    key_task: str
    owner: str = ""
    coordinator: str = ""
    collaborators: str = ""
    plan_time: str = ""
    status: str = "未开始"
    key_achievement: str = ""
    completion_standard: str = ""


class TaskBatchCreateRequest(BaseModel):
    project_id: int
    tasks: list[TaskDraft]


class SubTaskDraftItem(BaseModel):
    title: str
    assignee: str = ""
    plan_time: str = ""
    parent_task_id: int | None = None


class SubTaskDraftsPayload(BaseModel):
    project_id: int
    source_submission_id: int | None = None
    drafts: list[SubTaskDraftItem]


class SubTaskDraftApprovePayload(BaseModel):
    parent_task_id: int
    assignee: str = ""
    plan_time: str = ""


class SubTaskDraftRejectPayload(BaseModel):
    reason: str = ""
