from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint

from .database import Base
from .time_utils import utc_now


def now():
    return utc_now()


class TimestampMixin:
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class Task(Base, TimestampMixin):
    """业务语义：重点工作 / Workstream（三层结构第二层）

    物理表名：tasks（保持不变）
    业务含义：项目下的重点工作实体，对应文档"重点工作"层
    子层级：SubTask（KeyTask / 关键任务，三层结构第三层）

    special_project：项目名镜像字段（非重点工作名），由 project_id 自动回填
    key_task：重点工作名称（物理字段名含"task"，业务语义是 Workstream 名称）
    """
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    special_project = Column(String(80), index=True)
    key_task = Column(String(200), nullable=False)
    key_achievement = Column(String(200), default="")
    completion_standard = Column(Text, default="")
    coordinator = Column(String(50), default="")
    owner = Column(String(50), index=True)
    owner_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    collaborators = Column(String(200), default="")
    plan_time = Column(String(20), index=True)
    status = Column(String(20), default="未开始", index=True)
    problem_note = Column(Text, default="")
    achievement_links = Column(Text, default="")
    source_type = Column(String(40), default="人工录入")
    submitter = Column(String(50), default="")
    confirmed_by = Column(String(50), default="")
    confirmed_at = Column(DateTime, nullable=True)
    source_submission_id = Column(Integer, nullable=True, index=True)
    edit_count = Column(Integer, default=0)
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), default="")
    delete_reason = Column(Text, default="")
    delete_batch_id = Column(String(64), default="", index=True)


class UpdateSubmissionBatch(Base, TimestampMixin):
    __tablename__ = "update_submission_batches"

    id = Column(Integer, primary_key=True, index=True)
    client_request_id = Column(String(64), nullable=False, unique=True, index=True)
    submitter = Column(String(50), default="")
    submitter_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    source_type = Column(String(40), index=True)
    title = Column(String(200), default="")
    transcript_text = Column(Text, nullable=False)
    submission_count = Column(Integer, default=0)


class UpdateSubmission(Base, TimestampMixin):
    __tablename__ = "update_submissions"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("update_submission_batches.id"), nullable=True, index=True)
    batch_order = Column(Integer, default=0)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    source_type = Column(String(40), index=True)
    submitter = Column(String(50), default="")
    submitter_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    title = Column(String(200), default="")
    transcript_text = Column(Text, nullable=False)
    ai_result_json = Column(Text, default="")
    human_result_json = Column(Text, default="")
    confirm_status = Column(String(20), default="待确认", index=True)
    confidence = Column(Float, default=0)
    related_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    related_subtask_id = Column(Integer, ForeignKey("subtasks.id"), nullable=True, index=True)
    confirmed_by = Column(String(50), default="")
    confirmed_at = Column(DateTime, nullable=True)
    reject_reason = Column(Text, default="")
    coordinator_note = Column(Text, default="")
    ceo_note = Column(Text, default="")


class Meeting(Base, TimestampMixin):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    meeting_type = Column(String(40), default="")
    title = Column(String(200), default="")
    meeting_date = Column(String(20), default="")
    host = Column(String(50), default="")
    participants = Column(Text, default="")
    transcript_text = Column(Text, default="")
    summary = Column(Text, default="")
    task_list_json = Column(Text, default="")
    decision_items_json = Column(Text, default="")
    risk_items_json = Column(Text, default="")
    related_special_project = Column(String(80), default="")
    publish_status = Column(String(20), default="draft")


class Achievement(Base, TimestampMixin):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    name = Column(String(200), nullable=False)
    achievement_type = Column(String(40), index=True)
    special_project = Column(String(80), index=True)
    related_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    related_subtask_id = Column(Integer, ForeignKey("subtasks.id"), nullable=True, index=True)
    owner = Column(String(50), index=True)
    owner_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    version = Column(String(30), default="V0.1")
    file_link = Column(Text, default="")
    scenario = Column(Text, default="")
    reuse_tag = Column(String(80), default="")
    status = Column(String(20), default="草稿", index=True)
    source_type = Column(String(40), default="人工录入")
    confirmed_by = Column(String(50), default="")
    confirmed_at = Column(DateTime, nullable=True)
    source_submission_id = Column(Integer, nullable=True, index=True)
    source_achievement_submission_id = Column(Integer, nullable=True, index=True)
    edit_count = Column(Integer, default=0)


class AchievementSubmission(Base, TimestampMixin):
    __tablename__ = "achievement_submissions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    special_project = Column(String(80), index=True)
    related_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    related_subtask_id = Column(Integer, nullable=True)
    submitter = Column(String(50), default="", index=True)
    submitter_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    name = Column(String(200), nullable=False)
    achievement_type = Column(String(40), default="方案", index=True)
    version = Column(String(30), default="V0.1")
    file_link = Column(Text, default="")
    scenario = Column(Text, default="")
    reuse_tag = Column(String(80), default="")
    status = Column(String(20), default="待确认", index=True)
    reviewer = Column(String(50), default="")
    reviewed_at = Column(DateTime, nullable=True)
    reject_reason = Column(Text, default="")
    source_type = Column(String(40), default="人工补录")


class Issue(Base, TimestampMixin):
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    issue_type = Column(String(40), index=True)
    description = Column(Text, nullable=False)
    owner = Column(String(50), index=True)
    owner_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    helper = Column(String(100), default="")
    priority = Column(String(10), default="中", index=True)
    status = Column(String(20), default="待处理", index=True)
    need_decision_by = Column(String(50), default="")
    expected_resolve_time = Column(String(20), default="")
    resolution = Column(Text, default="")
    closed_at = Column(DateTime, nullable=True)
    related_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    related_subtask_id = Column(Integer, ForeignKey("subtasks.id"), nullable=True, index=True)
    special_project = Column(String(80), index=True)
    source_type = Column(String(40), default="人工录入")
    confirmed_by = Column(String(50), default="")
    source_submission_id = Column(Integer, nullable=True, index=True)
    edit_count = Column(Integer, default=0)
    reporter = Column(String(50), default="", index=True)
    handler_reply = Column(Text, default="")


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    code = Column(String(50), default="")
    description = Column(Text, default="")
    status = Column(String(20), default="draft", index=True)
    start_date = Column(String(20), default="")
    end_date = Column(String(20), default="")
    coordinator = Column(String(50), default="")
    owners = Column(String(200), default="")
    collaborators = Column(Text, default="")
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=False)


class ProjectCloseRequest(Base, TimestampMixin):
    __tablename__ = "project_close_requests"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    requester_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    summary = Column(Text, nullable=False)
    objective_result = Column(Text, nullable=False)
    unfinished_items_json = Column(Text, nullable=False, default="[]")
    remaining_risks_json = Column(Text, nullable=False, default="[]")
    handover_plan = Column(Text, nullable=False)
    retrospective = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    reviewer_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    review_comment = Column(Text, default="")
    reviewed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)


class Person(Base, TimestampMixin):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, index=True)
    role = Column(String(40), default="")          # 职务描述，仅展示用
    system_role = Column(String(40), default="normal_member", index=True)  # 全局权限角色英文键（company_ceo/super_admin/normal_member）
    department = Column(String(80), default="")
    special_project_duty = Column(Text, default="")
    permission = Column(String(40), default="查看")
    contact = Column(String(100), default="")
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, unique=True, index=True)
    password_hash = Column(String(128), nullable=False)
    person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    status = Column(String(20), default="active", index=True)
    is_tech_admin = Column(Boolean, default=False, index=True)
    last_login_at = Column(DateTime, nullable=True)
    last_password_changed_at = Column(DateTime, nullable=True)
    failed_login_count = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    must_change_password = Column(Boolean, default=False)
    wecom_userid = Column(String(64), nullable=True, index=True)


class PlatformSettings(Base, TimestampMixin):
    __tablename__ = "platform_settings"

    id = Column(Integer, primary_key=True, default=1)  # 单行，始终 id=1
    data_json = Column(Text, default="{}")


class OperationLog(Base, TimestampMixin):
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, nullable=True, index=True)
    operator = Column(String(50), default="")
    action = Column(String(80), default="")
    target_type = Column(String(40), default="")
    target_id = Column(Integer, nullable=True)
    note = Column(Text, default="")
    before_json = Column(Text, default="")
    after_json = Column(Text, default="")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    session_id = Column(String(64), primary_key=True, index=True)
    session_token_hash = Column(String(64), nullable=True, unique=True, index=True)
    username = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=now)
    expires_at = Column(DateTime, nullable=False, index=True)
    last_seen_at = Column(DateTime, nullable=False, default=now)
    revoked_at = Column(DateTime, nullable=True)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), default="", index=True)
    success = Column(Boolean, default=False, index=True)
    failure_reason = Column(String(80), default="")
    ip_address = Column(String(80), default="")
    user_agent = Column(Text, default="")
    created_at = Column(DateTime, default=now, index=True)


class SubTask(Base, TimestampMixin):
    """业务语义：关键任务 / KeyTask（三层结构第三层）

    物理表名：subtasks（保持不变）
    业务含义：重点工作(Workstream)下的关键任务实体，对应文档"关键任务"层
    父层级：Task（Workstream / 重点工作）
    """
    __tablename__ = "subtasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    assignee = Column(String(50), nullable=False, index=True)
    assignee_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    plan_time = Column(String(20), default="")
    status = Column(String(20), default="未开始", index=True)
    completion_criteria = Column(Text, default="")
    notes = Column(Text, default="")
    source_submission_id = Column(Integer, nullable=True, index=True)
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), default="")
    delete_reason = Column(Text, default="")
    delete_batch_id = Column(String(64), default="", index=True)
    deleted_by_parent_id = Column(Integer, nullable=True, index=True)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    recipient = Column(String(50), nullable=False, index=True, default="")  # 历史兼容，新记录优先用 recipient_id
    recipient_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)  # 首选
    type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, default="")
    link = Column(String(300), default="")
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=now, index=True)
    project_id = Column(Integer, nullable=True)


class SubTaskDraft(Base, TimestampMixin):
    __tablename__ = "subtask_drafts"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    parent_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    proposer = Column(String(50), nullable=False, index=True)
    assignee = Column(String(50), default="", index=True)
    assignee_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    plan_time = Column(String(20), default="")
    status = Column(String(20), default="pending", index=True)  # pending / approved / rejected
    reject_reason = Column(Text, default="")
    source_submission_id = Column(Integer, nullable=True, index=True)


class ProjectMember(Base, TimestampMixin):
    __tablename__ = "project_members"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("people.id"), nullable=False, index=True)
    person_name_snapshot = Column(String(50), default="", index=True)
    role = Column(String(30), nullable=False, index=True)
    joined_at = Column(DateTime, default=now)
    note = Column(Text, default="")

    __table_args__ = (
        UniqueConstraint("project_id", "person_id", "role", name="uq_project_member_role"),
    )


class MemberChangeRequest(Base, TimestampMixin):
    """成员变更申请（N8-P1-P1A：仅支持 add 普通成员 member/coordinator）。

    审核人：企业教练 project_ceo（项目角色）或 super_admin。
    company_ceo 不审核普通成员变更，仅查看。
    project_ceo 发起时自动通过（方案A）。
    """
    __tablename__ = "member_change_requests"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    requester_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    action = Column(String(20), nullable=False, default="add")  # 本轮仅 add
    target_person_id = Column(Integer, ForeignKey("people.id"), nullable=False, index=True)
    target_person_name = Column(String(50), default="")
    from_role = Column(String(30), default="")  # add 时为空
    to_role = Column(String(30), nullable=False)  # member / coordinator（本轮）
    reason = Column(Text, default="")
    status = Column(String(20), nullable=False, default="pending", index=True)  # pending/approved/rejected
    reviewer_person_id = Column(Integer, ForeignKey("people.id"), nullable=True)
    review_comment = Column(Text, default="")
    reviewed_at = Column(DateTime, nullable=True)
