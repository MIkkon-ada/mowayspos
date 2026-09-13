from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, false, true

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
    plan_process = Column(Text, default="", server_default="")
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
    creator_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    meeting_type = Column(String(40), default="")
    title = Column(String(200), default="")
    meeting_date = Column(String(20), default="")
    location = Column(String(200), nullable=False, default="", server_default="")
    host = Column(String(50), default="")
    participants = Column(Text, default="")
    organizer = Column(String(100), nullable=False, default="", server_default="")
    copied_to = Column(Text, nullable=False, default="", server_default="")
    agenda_items_json = Column(Text, nullable=False, default="[]", server_default="[]")
    prior_action_items_json = Column(Text, nullable=False, default="[]", server_default="[]")
    source_mode = Column(
        String(32), nullable=False, default="ai_analysis", server_default="ai_analysis"
    )
    transcript_text = Column(Text, default="")
    summary = Column(Text, default="")
    task_list_json = Column(Text, default="")
    decision_items_json = Column(Text, default="")
    risk_items_json = Column(Text, default="")
    related_special_project = Column(String(80), default="")
    publish_status = Column(String(20), default="draft")
    document_source_id = Column(
        Integer, ForeignKey("meeting_document_sources.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    review_status = Column(String(24), nullable=False, default="legacy", server_default="legacy", index=True)
    review_version = Column(Integer, nullable=False, default=1, server_default="1")


class MeetingDocumentSource(Base, TimestampMixin):
    """Original Word file uploaded for a project meeting run."""

    __tablename__ = "meeting_document_sources"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    original_name = Column(String(255), nullable=False)
    storage_key = Column(String(255), nullable=False, unique=True)
    mime_type = Column(String(120), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    uploaded_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)


class ProjectMeetingRun(Base, TimestampMixin):
    """Immutable project snapshot and analysis output for one uploaded document."""

    __tablename__ = "project_meeting_runs"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    document_source_id = Column(Integer, ForeignKey("meeting_document_sources.id"), nullable=False, index=True)
    snapshot_json = Column(Text, nullable=False, default="{}", server_default="{}")
    document_text = Column(Text, nullable=False, default="", server_default="")
    result_json = Column(Text, nullable=False, default="{}", server_default="{}")
    status = Column(String(24), nullable=False, default="analyzing", server_default="analyzing", index=True)
    error_message = Column(Text, nullable=False, default="", server_default="")
    created_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    stage = Column(String(32), nullable=False, default="created", server_default="created", index=True)
    step_count = Column(Integer, nullable=False, default=0, server_default="0")
    prompt_version = Column(String(64), nullable=False, default="", server_default="")
    model_code = Column(String(96), nullable=False, default="", server_default="")
    invocation_log_ids_json = Column(Text, nullable=False, default="[]", server_default="[]")
    tool_trace_json = Column(Text, nullable=False, default="[]", server_default="[]")
    raw_responses_json = Column(Text, nullable=False, default="[]", server_default="[]")
    error_code = Column(String(64), nullable=False, default="", server_default="", index=True)


class MeetingReviewEvent(Base, TimestampMixin):
    """Audit trail for draft submission, owner review, return and writeback."""

    __tablename__ = "meeting_review_events"

    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)
    action = Column(String(24), nullable=False, index=True)
    actor_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    reason = Column(Text, nullable=False, default="", server_default="")
    selected_proposal_ids_json = Column(Text, nullable=False, default="[]", server_default="[]")


class MeetingTranscriptSource(Base, TimestampMixin):
    __tablename__ = "meeting_transcript_sources"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True, index=True)
    raw_text = Column(Text, nullable=False)
    source_hash = Column(String(64), nullable=False, index=True)
    source_type = Column(String(20), nullable=False, default="manual")
    created_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True)


class MeetingTranscriptRevision(Base, TimestampMixin):
    __tablename__ = "meeting_transcript_revisions"
    __table_args__ = (
        UniqueConstraint("source_id", "revision_no", name="uq_meeting_transcript_revision"),
    )

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(
        Integer, ForeignKey("meeting_transcript_sources.id"), nullable=False, index=True
    )
    revision_no = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    text_hash = Column(String(64), nullable=False)
    created_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True)


class MeetingAnalysisRun(Base, TimestampMixin):
    __tablename__ = "meeting_analysis_runs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True, index=True)
    source_id = Column(
        Integer, ForeignKey("meeting_transcript_sources.id"), nullable=False, index=True
    )
    transcript_revision_id = Column(
        Integer, ForeignKey("meeting_transcript_revisions.id"), nullable=True, index=True
    )
    member_snapshot_json = Column(Text, nullable=False, default="{}")
    plan_snapshot_json = Column(Text, nullable=False, default="{}")
    agent_input_json = Column(Text, nullable=False, default="{}")
    raw_response_json = Column(Text, nullable=False, default="{}")
    normalized_output_json = Column(Text, nullable=False, default="{}")
    validation_output_json = Column(Text, nullable=False, default="{}")
    provider = Column(String(64), nullable=False, default="")
    model_name = Column(String(120), nullable=False, default="")
    policy_version = Column(String(64), nullable=False, default="")
    prompt_version = Column(String(64), nullable=False, default="")
    prompt_hash = Column(String(64), nullable=False, default="")
    input_hash = Column(String(64), nullable=False, default="")
    reference_at = Column(DateTime, nullable=False)
    timezone = Column(String(64), nullable=False, default="Asia/Shanghai")
    status = Column(String(20), nullable=False, default="review", index=True)
    created_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)


class MeetingAnalysisCandidate(Base, TimestampMixin):
    __tablename__ = "meeting_analysis_candidates"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("meeting_analysis_runs.id"), nullable=False, index=True)
    candidate_type = Column(String(32), nullable=False, index=True)
    agent_proposal_json = Column(Text, nullable=False, default="{}")
    evidence_json = Column(Text, nullable=False, default="[]")
    validation_json = Column(Text, nullable=False, default="[]")
    final_value_json = Column(Text, nullable=False, default="{}")
    validation_status = Column(
        String(24), nullable=False, default="needs_confirmation", index=True
    )
    review_status = Column(String(24), nullable=False, default="pending", index=True)
    reviewer_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    review_comment = Column(Text, default="")


class MeetingSkillRun(Base, TimestampMixin):
    """Agent-owned orchestration record for a skill-backed meeting workflow."""

    __tablename__ = "meeting_skill_runs"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True, index=True)
    skill_name = Column(String(96), nullable=False, index=True)
    skill_version = Column(String(32), nullable=False)
    status = Column(
        String(32), nullable=False, default="created", server_default="created", index=True
    )
    current_input_snapshot_id = Column(Integer, nullable=True, index=True)
    output_json = Column(Text, nullable=False, default="{}", server_default="{}")
    output_answer_revisions_json = Column(
        Text, nullable=False, default="{}", server_default="{}"
    )
    created_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)


class MeetingSkillInputSnapshot(Base, TimestampMixin):
    __tablename__ = "meeting_skill_input_snapshots"
    __table_args__ = (UniqueConstraint("run_id", "version", name="uq_meeting_skill_snapshot_version"),)

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("meeting_skill_runs.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    transcript_text = Column(Text, nullable=False, default="", server_default="")
    reference_files_json = Column(
        Text, nullable=False, default="[]", server_default="[]"
    )
    input_hash = Column(String(64), nullable=False, index=True)
    is_current = Column(
        Boolean, nullable=False, default=True, server_default=true(), index=True
    )


class MeetingSkillClarification(Base, TimestampMixin):
    __tablename__ = "meeting_skill_clarifications"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("meeting_skill_runs.id"), nullable=False, index=True)
    input_snapshot_id = Column(Integer, ForeignKey("meeting_skill_input_snapshots.id"), nullable=False, index=True)
    code = Column(String(96), nullable=False, index=True)
    question = Column(Text, nullable=False)
    question_kind = Column(String(40), nullable=False, index=True)
    blocking = Column(
        Boolean, nullable=False, default=False, server_default=false(), index=True
    )
    required = Column(Boolean, nullable=False, default=False, server_default=false())
    action = Column(
        String(32), nullable=False, default="answer", server_default="answer"
    )
    answer_mode = Column(String(32), nullable=True)
    allow_other = Column(Boolean, nullable=False, default=False, server_default=false())
    allow_omit = Column(Boolean, nullable=False, default=False, server_default=false())
    options_json = Column(Text, nullable=False, default="[]", server_default="[]")
    evidence_json = Column(Text, nullable=False, default="[]", server_default="[]")
    resolved_at = Column(DateTime, nullable=True)


class MeetingSkillClarificationAnswerRevision(Base, TimestampMixin):
    __tablename__ = "meeting_skill_clarification_answer_revisions"
    __table_args__ = (
        UniqueConstraint("question_id", "answer_revision", name="uq_meeting_skill_answer_revision"),
        Index("ix_mskill_answer_rev_answered_by", "answered_by_person_id"),
    )

    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("meeting_skill_clarifications.id"), nullable=False, index=True)
    answer_revision = Column(Integer, nullable=False)
    answer_json = Column(Text, nullable=False, default="{}", server_default="{}")
    answered_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True)


class MeetingSkillResolvedFact(Base, TimestampMixin):
    __tablename__ = "meeting_skill_resolved_facts"
    __table_args__ = (UniqueConstraint("run_id", "field_name", name="uq_meeting_skill_resolved_fact"),)

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("meeting_skill_runs.id"), nullable=False, index=True)
    field_name = Column(String(96), nullable=False)
    value_json = Column(Text, nullable=False, default="{}", server_default="{}")
    display_value = Column(Text, nullable=False, default="", server_default="")
    source_type = Column(String(32), nullable=False)
    evidence_json = Column(Text, nullable=False, default="[]", server_default="[]")
    answer_revision_id = Column(Integer, ForeignKey("meeting_skill_clarification_answer_revisions.id"), nullable=True, index=True)


class MeetingProgressReview(Base, TimestampMixin):
    """Evidence-bound member progress result awaiting human confirmation."""

    __tablename__ = "meeting_progress_reviews"
    __table_args__ = (
        UniqueConstraint(
            "meeting_id",
            "analysis_version",
            "member_name",
            "baseline_subtask_id",
            name="uq_meeting_progress_review_version_member_subtask",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)
    baseline_run_id = Column(
        Integer, ForeignKey("kickoff_agent_runs.id"), nullable=False, index=True
    )
    baseline_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True, index=True)
    baseline_subtask_id = Column(
        Integer, ForeignKey("subtasks.id"), nullable=True, index=True
    )
    member_name = Column(String(100), nullable=False)
    baseline_snapshot_json = Column(Text, nullable=False, default="{}")
    report_text = Column(Text, nullable=False, default="")
    status = Column(String(24), nullable=False, default="not_mentioned", index=True)
    evidence_quote = Column(Text, nullable=False, default="")
    suggested_task_status = Column(String(40), default="")
    review_status = Column(String(24), nullable=False, default="pending", index=True)
    reviewer_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_comment = Column(Text, default="")
    validation_json = Column(Text, nullable=False, default="[]")
    analysis_version = Column(Integer, nullable=False, default=1, index=True)


class MeetingRevision(Base):
    """Immutable full snapshot of one saved meeting-minutes version."""

    __tablename__ = "meeting_revisions"
    __table_args__ = (
        UniqueConstraint("meeting_id", "version_no", name="uq_meeting_revisions_meeting_version"),
    )

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)
    version_no = Column(Integer, nullable=False)
    is_legacy_snapshot = Column(Boolean, nullable=False, default=False)
    saved_by = Column(String(100), nullable=False, default="")
    saved_at = Column(DateTime, nullable=False, default=now)
    related_special_project = Column(String(80), default="")
    meeting_type = Column(String(40), default="")
    title = Column(String(200), default="")
    meeting_date = Column(String(20), default="")
    location = Column(String(200), nullable=False, default="", server_default="")
    host = Column(String(50), default="")
    participants = Column(Text, default="")
    organizer = Column(String(100), nullable=False, default="", server_default="")
    copied_to = Column(Text, nullable=False, default="", server_default="")
    agenda_items_json = Column(Text, nullable=False, default="[]", server_default="[]")
    prior_action_items_json = Column(Text, nullable=False, default="[]", server_default="[]")
    source_mode = Column(
        String(32), nullable=False, default="ai_analysis", server_default="ai_analysis"
    )
    transcript_text = Column(Text, nullable=False, default="")
    summary = Column(Text, default="")
    task_list_json = Column(Text, default="")
    decision_items_json = Column(Text, default="")
    risk_items_json = Column(Text, default="")
    publish_status = Column(String(20), default="draft")
    transcript_source_id = Column(
        Integer, ForeignKey("meeting_transcript_sources.id"), nullable=True, index=True
    )
    transcript_revision_id = Column(
        Integer, ForeignKey("meeting_transcript_revisions.id"), nullable=True, index=True
    )
    analysis_run_id = Column(
        Integer, ForeignKey("meeting_analysis_runs.id"), nullable=True, index=True
    )
    parent_revision_id = Column(
        Integer, ForeignKey("meeting_revisions.id"), nullable=True, index=True
    )
    revision_kind = Column(String(32), default="draft_save")
    agent_output_json = Column(Text, default="{}")
    validation_output_json = Column(Text, default="{}")
    human_output_json = Column(Text, default="{}")
    human_diff_json = Column(Text, default="{}")


class AIModel(Base, TimestampMixin):
    """One provider/model endpoint eligible for capability policies."""

    __tablename__ = "ai_models"
    __table_args__ = (UniqueConstraint("code", name="uq_ai_models_code"),)

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(96), nullable=False, index=True)
    display_name = Column(String(160), nullable=False)
    provider = Column(String(64), nullable=False, index=True)
    model_name = Column(String(160), nullable=False)
    model_type = Column(String(24), nullable=False, index=True)
    base_url = Column(Text, nullable=False, default="", server_default="")
    config_json = Column(Text, nullable=False, default="{}", server_default="{}")
    enabled = Column(Boolean, nullable=False, default=False, server_default=false(), index=True)
    source = Column(
        String(24), nullable=False, default="custom", server_default="custom", index=True
    )
    managed_by = Column(String(24), nullable=False, default="", server_default="")
    revision = Column(Integer, nullable=False, default=1, server_default="1")


class AIModelCredential(Base, TimestampMixin):
    """Encrypted credentials kept separately from public model metadata."""

    __tablename__ = "ai_model_credentials"
    __table_args__ = (UniqueConstraint("model_id", name="uq_ai_model_credentials_model"),)

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ai_models.id"), nullable=False, index=True)
    encrypted_api_key = Column(Text, nullable=False, default="", server_default="")
    encrypted_app_secret = Column(Text, nullable=False, default="", server_default="")
    key_version = Column(String(32), nullable=False, default="v1", server_default="v1")


class AICapabilityPolicy(Base, TimestampMixin):
    """Global model selection and fallback policy for one capability key."""

    __tablename__ = "ai_capability_policies"
    __table_args__ = (UniqueConstraint("capability_key", name="uq_ai_capability_policies_key"),)

    id = Column(Integer, primary_key=True, index=True)
    capability_key = Column(String(96), nullable=False, index=True)
    primary_model_id = Column(Integer, ForeignKey("ai_models.id"), nullable=True, index=True)
    fallback_model_ids_json = Column(
        Text, nullable=False, default="[]", server_default="[]"
    )
    timeout_seconds = Column(Integer, nullable=False, default=60, server_default="60")
    fallback_timeout_seconds = Column(Integer, nullable=False, default=25, server_default="25")
    max_attempts = Column(Integer, nullable=False, default=1, server_default="1")
    policy_version = Column(Integer, nullable=False, default=1, server_default="1")
    enabled = Column(Boolean, nullable=False, default=False, server_default=false(), index=True)


class AIInvocationLog(Base, TimestampMixin):
    """Sanitized audit metadata for a single model invocation attempt."""

    __tablename__ = "ai_invocation_logs"

    id = Column(Integer, primary_key=True, index=True)
    capability_key = Column(String(96), nullable=False, index=True)
    policy_version = Column(Integer, nullable=False)
    model_id = Column(Integer, ForeignKey("ai_models.id"), nullable=True, index=True)
    model_revision = Column(Integer, nullable=False, default=0, server_default="0")
    attempt_no = Column(Integer, nullable=False, default=1, server_default="1")
    status = Column(String(24), nullable=False, index=True)
    fallback_used = Column(Boolean, nullable=False, default=False, server_default=false())
    duration_ms = Column(Integer, nullable=False, default=0, server_default="0")
    error_code = Column(String(64), nullable=False, default="", server_default="", index=True)
    resource_type = Column(String(64), nullable=False, default="", server_default="", index=True)
    resource_id = Column(Integer, nullable=True, index=True)
    actor = Column(String(50), nullable=False, default="", server_default="", index=True)


class KickoffAgentRun(Base, TimestampMixin):
    __tablename__ = "kickoff_agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True, index=True)
    snapshot_json = Column(Text, nullable=False, default="{}")
    approved_snapshot_json = Column(Text, nullable=False, default="{}")
    result_json = Column(Text, nullable=False, default="{}")
    status = Column(String(20), nullable=False, default="draft", index=True)
    created_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)


class KickoffChangeProposal(Base, TimestampMixin):
    __tablename__ = "kickoff_change_proposals"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("kickoff_agent_runs.id"), nullable=False, index=True)
    proposal_type = Column(String(20), nullable=False)
    target_type = Column(String(20), nullable=False)
    target_id = Column(Integer, nullable=True, index=True)
    before_json = Column(Text, nullable=False, default="{}")
    proposed_json = Column(Text, nullable=False, default="{}")
    evidence_json = Column(Text, nullable=False, default="[]")
    validation_json = Column(Text, nullable=False, default="[]")
    review_status = Column(String(20), nullable=False, default="pending", index=True)
    reviewer_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    review_comment = Column(Text, default="")


class MeetingChangeSet(Base, TimestampMixin):
    __tablename__ = "meeting_change_sets"
    __table_args__ = (
        Index("ix_meeting_change_sets_project_id_status", "project_id", "status"),
        Index("ix_meeting_change_sets_meeting_id", "meeting_id"),
    )

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True)
    created_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True)
    transcript_hash = Column(String(64), nullable=False, default="")
    snapshot_json = Column(Text, nullable=False, default="{}")
    result_json = Column(Text, nullable=False, default="{}")
    status = Column(String(20), nullable=False, default="draft")


class MeetingChangeProposal(Base, TimestampMixin):
    __tablename__ = "meeting_change_proposals"
    __table_args__ = (
        Index(
            "ix_meeting_change_proposals_change_set_id_execution_status",
            "change_set_id",
            "execution_status",
        ),
    )

    id = Column(Integer, primary_key=True)
    change_set_id = Column(Integer, ForeignKey("meeting_change_sets.id"), nullable=False)
    action = Column(String(32), nullable=False)
    target_type = Column(String(20), nullable=False)
    target_id = Column(Integer, nullable=True)
    parent_workstream_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    parent_subtask_id = Column(Integer, ForeignKey("subtasks.id"), nullable=True, index=True)
    before_json = Column(Text, nullable=False, default="{}")
    proposed_json = Column(Text, nullable=False, default="{}")
    evidence_json = Column(Text, nullable=False, default="[]")
    reason = Column(Text, nullable=False, default="")
    confidence = Column(Float, nullable=False, default=0.0)
    validation_json = Column(Text, nullable=False, default="[]")
    lineage_json = Column(Text, nullable=False, default="{}", server_default="{}")
    execution_status = Column(String(20), nullable=False, default="pending")
    executed_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True)
    executed_at = Column(DateTime, nullable=True)
    result_target_id = Column(Integer, nullable=True)


class TaskPlanProposalRun(Base, TimestampMixin):
    """Persisted, review-only AI decomposition for one selected key task."""

    __tablename__ = "task_plan_proposal_runs"
    __table_args__ = (
        Index("ix_task_plan_proposal_runs_project_key_task_status", "project_id", "key_task_id", "status"),
    )

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    key_task_id = Column(Integer, ForeignKey("subtasks.id"), nullable=False, index=True)
    source_text = Column(Text, nullable=False, default="", server_default="")
    source_hash = Column(String(64), nullable=False, default="", server_default="", index=True)
    status = Column(
        String(32),
        nullable=False,
        default="ready_for_review",
        server_default="ready_for_review",
        index=True,
    )
    model_code = Column(String(96), nullable=False, default="", server_default="")
    invocation_log_id = Column(Integer, ForeignKey("ai_invocation_logs.id"), nullable=True, index=True)
    created_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)


class TaskPlanProposalAttachment(Base, TimestampMixin):
    __tablename__ = "task_plan_proposal_attachments"

    id = Column(Integer, primary_key=True)
    run_id = Column(
        Integer,
        ForeignKey("task_plan_proposal_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_name = Column(String(255), nullable=False)
    storage_key = Column(String(255), nullable=False, unique=True)
    mime_type = Column(String(120), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    extracted_text = Column(Text, nullable=False, server_default="")
    uploaded_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)


class TaskPlanProposal(Base, TimestampMixin):
    __tablename__ = "task_plan_proposals"
    __table_args__ = (
        Index("ix_task_plan_proposals_run_status", "run_id", "status"),
    )

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("task_plan_proposal_runs.id"), nullable=False, index=True)
    plan_json = Column(Text, nullable=False, default="{}", server_default="{}")
    evidence_json = Column(Text, nullable=False, default="{}", server_default="{}")
    validation_json = Column(Text, nullable=False, default="{}", server_default="{}")
    status = Column(
        String(32),
        nullable=False,
        default="needs_confirmation",
        server_default="needs_confirmation",
        index=True,
    )
    reviewer_edit_json = Column(Text, nullable=False, default="{}", server_default="{}")
    created_plan_id = Column(Integer, ForeignKey("execution_schedules.id"), nullable=True, index=True)


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


class AchievementAttachment(Base, TimestampMixin):
    __tablename__ = "achievement_attachments"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=True, index=True)
    achievement_submission_id = Column(
        Integer, ForeignKey("achievement_submissions.id"), nullable=True, index=True
    )
    storage_key = Column(String(255), nullable=False, unique=True)
    original_name = Column(String(255), nullable=False)
    mime_type = Column(String(120), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    uploaded_by = Column(String(50))
    uploaded_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(50), default="")


class ProjectInitAttachment(Base, TimestampMixin):
    __tablename__ = "project_init_attachments"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    storage_key = Column(String(255), nullable=False, unique=True)
    original_name = Column(String(255), nullable=False)
    mime_type = Column(String(120), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    uploaded_by = Column(String(50), nullable=False, index=True)
    uploaded_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    deleted_by = Column(String(50), default="")


class ProjectInitAnalysisRun(Base, TimestampMixin):
    __tablename__ = "project_init_analysis_runs"
    __table_args__ = (
        Index("uq_project_init_analysis_runs_retry_of", "retry_of_run_id", unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    attachment_ids_json = Column(Text, nullable=False, default="[]")
    snapshot_json = Column(Text, nullable=False, default="{}")
    current_draft_json = Column(Text, nullable=False, default="[]")
    status = Column(String(24), nullable=False, default="queued", index=True)
    stage = Column(String(24), nullable=False, default="reading")
    progress = Column(Integer, nullable=False, default=0)
    result_json = Column(Text, nullable=False, default="{}")
    file_results_json = Column(Text, nullable=False, default="[]")
    error_summary = Column(Text, nullable=False, default="")
    provider = Column(String(30), nullable=False, default="")
    model_name = Column(String(100), nullable=False, default="")
    created_by = Column(String(50), nullable=False, index=True)
    created_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    applied_at = Column(DateTime, nullable=True)
    retry_of_run_id = Column(
        Integer,
        ForeignKey("project_init_analysis_runs.id", name="fk_project_init_analysis_retry_of"),
        nullable=True,
    )


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
    source_card_index = Column(Integer, nullable=True)
    opinion = Column(Text, default="")
    edit_count = Column(Integer, default=0)
    reporter = Column(String(50), default="", index=True)
    handler_reply = Column(Text, default="")


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    code = Column(String(50), default="")
    description = Column(Text, default="")
    objectives = Column(Text, default="")
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
    position_title = Column(String(100), default="", server_default="")  # 公司岗位名称，身份资料，不参与权限判断
    system_role = Column(String(40), default="normal_member", index=True)  # 全局权限角色英文键（company_ceo/super_admin/normal_member）
    department = Column(String(80), default="")
    wecom_userid = Column(String(64), default="", server_default="", index=True)
    wecom_department = Column(String(200), default="", server_default="")
    wecom_position_title = Column(String(100), default="", server_default="")
    department_source = Column(String(20), default="wecom", server_default="wecom")
    position_source = Column(String(20), default="wecom", server_default="wecom")
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
    collaborator_ids = Column(JSON, nullable=False, default=list, server_default="[]")
    plan_time = Column(String(20), default="")
    # Structured execution dates coexist with the legacy plan_time display text.
    start_date = Column(Date, nullable=True, index=True)
    due_kind = Column(String(10), nullable=False, default="unknown", server_default="unknown", index=True)
    due_date = Column(Date, nullable=True, index=True)
    due_label = Column(String(100), nullable=True)
    due_reference_date = Column(Date, nullable=True, index=True)
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
    risk_note = Column(Text, nullable=False, default="", server_default="")
    risk_marked_by = Column(String(50), nullable=False, default="", server_default="")
    risk_marked_at = Column(DateTime, nullable=True)


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


class ExecutionSchedule(Base, TimestampMixin):
    __tablename__ = "execution_schedules"
    __table_args__ = (
        Index(
            "ix_execution_schedules_month_plan_lookup",
            "subtask_id",
            "plan_type",
            "plan_month",
            "is_deleted",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    subtask_id = Column(Integer, ForeignKey("subtasks.id"), nullable=False, index=True)
    plan_type = Column(String(10), nullable=False, index=True)
    plan_month = Column(String(7), nullable=True)
    title = Column(String(200), nullable=False)
    start_date = Column(Date, nullable=True, index=True)
    due_date = Column(Date, nullable=True, index=True)
    due_kind = Column(String(10), nullable=False, default="unknown", server_default="unknown", index=True)
    due_label = Column(String(100), nullable=True)
    due_reference_date = Column(Date, nullable=True, index=True)
    assignee = Column(String(50), nullable=False, default="")
    assignee_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="待开始", index=True)
    expected_output = Column(Text, nullable=False, default="", server_default="")
    collaborator_ids = Column(JSON, nullable=False, default=list, server_default="[]")
    completion_criteria = Column(Text, nullable=False, default="", server_default="")
    progress_note = Column(Text, nullable=False, default="", server_default="")
    risk_dependency = Column(Text, nullable=False, default="", server_default="")
    actual_output = Column(Text, nullable=False, default="", server_default="")
    delay_reason = Column(Text, nullable=False, default="", server_default="")
    sort_order = Column(Integer, nullable=False, default=0, server_default="0")
    reminder_policy = Column(JSON, nullable=False, default=dict)
    created_by = Column(String(50), nullable=False, default="")
    updated_by = Column(String(50), nullable=False, default="")
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    is_archived = Column(Boolean, nullable=False, default=False, server_default=false(), index=True)


class KeyTaskExecutionEvent(Base):
    """Append-only projection for the confirmed Key Task execution timeline."""

    __tablename__ = "key_task_execution_events"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_key_task_execution_event_dedupe_key"),
        Index(
            "ix_key_task_execution_events_current_progress",
            "key_task_id",
            "authority",
            "affects_current_progress",
            "effective_at",
            "id",
        ),
        Index(
            "ix_key_task_execution_events_timeline",
            "key_task_id",
            "occurred_at",
            "id",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    key_task_id = Column(Integer, ForeignKey("subtasks.id"), nullable=False, index=True)
    execution_plan_id = Column(Integer, ForeignKey("execution_schedules.id"), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    source_type = Column(String(50), nullable=False, index=True)
    source_id = Column(Integer, nullable=False, index=True)
    dedupe_key = Column(String(200), nullable=False)
    actor_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    actor_name_snapshot = Column(String(100), nullable=False, default="", server_default="")
    occurred_at = Column(DateTime, nullable=False, index=True)
    confirmed_at = Column(DateTime, nullable=False, index=True)
    effective_at = Column(DateTime, nullable=False, index=True)
    affects_current_progress = Column(Boolean, nullable=False, default=False, server_default=false(), index=True)
    status_before = Column(String(40), nullable=True)
    status_after = Column(String(40), nullable=True)
    progress_summary = Column(Text, nullable=True)
    next_step = Column(Text, nullable=True)
    display_payload_json = Column(Text, nullable=True)
    authority = Column(String(30), nullable=False, default="confirmed", server_default="confirmed", index=True)
    created_at = Column(DateTime, nullable=False, default=now, index=True)


class ExecutionScheduleReminder(Base, TimestampMixin):
    __tablename__ = "execution_schedule_reminders"
    __table_args__ = (
        UniqueConstraint("schedule_id", "reminder_kind", "due_on", "recipient_id", name="uq_execution_schedule_reminder"),
    )

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("execution_schedules.id"), nullable=False, index=True)
    reminder_kind = Column(String(20), nullable=False)
    due_on = Column(Date, nullable=False)
    recipient_id = Column(Integer, ForeignKey("people.id"), nullable=False, index=True)
    notification_id = Column(Integer, ForeignKey("notifications.id"), nullable=True)
    wecom_error = Column(Text, nullable=False, default="")


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
