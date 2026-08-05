import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _safe_json_object(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _safe_json_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


class UserSubtaskContext(BaseModel):
    id: int
    title: str
    status: str = ""
    parent_key_task: str = ""
    project_id: int | None = None
    project_name: str = ""
    parent_task_id: int | None = None
    matched_subtask_id: int | None = None
    subtask_id: int | None = None
    subtask_title: str = ""
    parent_project_id: int | None = None
    assignee: str = ""
    user_relation: str = ""
    completion_criteria: str = ""
    plan_time: str = ""


class ExtractRequest(BaseModel):
    project_id: int | None = None
    report_scope: str | None = None
    special_project: str | None = None
    source_type: str
    submitter: str | None = None
    title: str | None = None
    transcript_text: str
    human_result: dict[str, Any] | None = None
    edited_suggestion: dict[str, Any] | None = None
    llm_provider: str | None = None
    user_subtasks: list[UserSubtaskContext] | None = None


class BatchUpdateRequest(BaseModel):
    client_request_id: str = Field(min_length=8, max_length=64)
    source_type: str = Field(min_length=1, max_length=40)
    title: str = Field(default="工作汇报", max_length=200)
    transcript_text: str = Field(min_length=1, max_length=5000)
    human_result: dict[str, Any]


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
    attachment_ids: list[int] = Field(default_factory=list)


class AchievementSubmissionRejectRequest(BaseModel):
    reject_reason: str = ""


class AchievementPayload(BaseModel):
    project_id: int | None = None
    name: str = Field(..., max_length=200)
    achievement_type: str = Field("方案", max_length=40)
    special_project: str = Field("", max_length=80)
    related_task_id: int | None = None
    related_subtask_id: int | None = None
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
    related_subtask_id: int | None = None
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


class ProjectCloseResidualItem(BaseModel):
    description: str
    reason: str
    owner: str
    handover_to: str
    follow_up_plan: str
    expected_resolution: str

    @field_validator("*", mode="before")
    @classmethod
    def trim_required_fields(cls, value: object) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("field must not be blank")
        return normalized


class ProjectCloseRequestCreatePayload(BaseModel):
    summary: str
    objective_result: str
    unfinished_items: list[ProjectCloseResidualItem]
    remaining_risks: list[ProjectCloseResidualItem]
    handover_plan: str
    retrospective: str

    @field_validator("summary", "objective_result", "handover_plan", "retrospective", mode="before")
    @classmethod
    def trim_required_text(cls, value: object) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("field must not be blank")
        return normalized


class ProjectCloseRequestUpdatePayload(BaseModel):
    summary: str | None = None
    objective_result: str | None = None
    unfinished_items: list[ProjectCloseResidualItem] | None = None
    remaining_risks: list[ProjectCloseResidualItem] | None = None
    handover_plan: str | None = None
    retrospective: str | None = None

    @field_validator("summary", "objective_result", "handover_plan", "retrospective", mode="before")
    @classmethod
    def trim_optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("field must not be blank")
        return normalized


class ProjectCloseReviewPayload(BaseModel):
    review_comment: str = ""

    @field_validator("review_comment", mode="before")
    @classmethod
    def trim_comment(cls, value: object) -> str:
        return str(value or "").strip()


class ProjectWorkProgressSubTaskDraft(BaseModel):
    title: str = Field("", max_length=200)
    evaluation_standard: str = ""
    assignee: str = Field("", max_length=50)
    helper: str = Field("", max_length=100)
    plan_start: str = Field("", max_length=20)
    plan_end: str = Field("", max_length=20)


class ProjectWorkProgressTaskDraft(BaseModel):
    title: str = Field("", max_length=200)
    description: str = ""
    owner: str = Field("", max_length=50)
    helper: str = Field("", max_length=200)
    plan_start: str = Field("", max_length=20)
    plan_end: str = Field("", max_length=20)
    subtasks: list[ProjectWorkProgressSubTaskDraft] = Field(default_factory=list)


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
    work_progress_draft: list[ProjectWorkProgressTaskDraft] = Field(default_factory=list)


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


class MeetingRevisionResponse(BaseModel):
    id: int
    meeting_id: int
    version_no: int
    is_legacy_snapshot: bool = False
    saved_by: str = ""
    saved_at: str | None = None
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
    transcript_source_id: int | None = None
    transcript_revision_id: int | None = None
    analysis_run_id: int | None = None
    parent_revision_id: int | None = None
    revision_kind: str = "draft_save"
    agent_output_json: str = "{}"
    validation_output_json: str = "{}"
    human_output_json: str = "{}"
    human_diff_json: str = "{}"


class EvidenceRef(BaseModel):
    source_id: int
    transcript_revision_id: int | None = None
    char_start: int
    char_end: int
    quote: str
    source_hash: str
    segment_id: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None


class CandidateReviewPayload(BaseModel):
    review_status: Literal["accepted", "needs_confirmation", "ignored"]
    final_value: dict[str, Any] = Field(default_factory=dict)
    review_comment: str = ""


class MeetingTranscriptRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    revision_no: int
    text: str
    text_hash: str
    created_by_person_id: int | None = None
    created_at: datetime
    updated_at: datetime


class MeetingAnalysisRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    meeting_id: int | None = None
    source_id: int
    transcript_revision_id: int | None = None
    member_snapshot_json: dict[str, Any]
    plan_snapshot_json: dict[str, Any]
    agent_input_json: dict[str, Any]
    raw_response_json: dict[str, Any]
    normalized_output_json: dict[str, Any]
    validation_output_json: dict[str, Any]
    provider: str
    model_name: str
    policy_version: str
    prompt_version: str
    prompt_hash: str
    input_hash: str
    reference_at: datetime
    timezone: str
    status: str
    created_by_person_id: int | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "member_snapshot_json",
        "plan_snapshot_json",
        "agent_input_json",
        "raw_response_json",
        "normalized_output_json",
        "validation_output_json",
        mode="before",
    )
    @classmethod
    def parse_json_object(cls, value: Any) -> Any:
        return _safe_json_object(value)


class MeetingAnalysisCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    candidate_type: str
    agent_proposal_json: dict[str, Any]
    evidence_json: list[EvidenceRef]
    validation_json: list[dict[str, Any]]
    final_value_json: dict[str, Any]
    validation_status: str
    review_status: str
    reviewer_person_id: int | None = None
    review_comment: str | None = ""
    created_at: datetime
    updated_at: datetime

    @field_validator("agent_proposal_json", "final_value_json", mode="before")
    @classmethod
    def parse_json_object(cls, value: Any) -> Any:
        return _safe_json_object(value)

    @field_validator("evidence_json", "validation_json", mode="before")
    @classmethod
    def parse_json_list(cls, value: Any) -> Any:
        return _safe_json_list(value)


class MeetingStatusPatch(BaseModel):
    publish_status: str
    reject_reason: str = ""


class KickoffRunCreatePayload(BaseModel):
    transcript_text: str = Field(..., min_length=1)


class KickoffRunSubmitPayload(BaseModel):
    summary: str = ""


class KickoffProposalReviewPayload(BaseModel):
    status: str
    review_comment: str = ""


class KickoffStartConfirmPayload(BaseModel):
    review_comment: str = ""


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
