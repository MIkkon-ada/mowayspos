from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base contract for JSON returned by the project meeting agent."""

    model_config = ConfigDict(extra="forbid")


class EvidenceSpan(StrictModel):
    quote: str = Field(min_length=1)
    char_start: Annotated[int, Field(strict=True, ge=0)]
    char_end: Annotated[int, Field(strict=True, gt=0)]

    @model_validator(mode="after")
    def validate_offsets(self):
        if self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        return self


class MeetingInfo(StrictModel):
    title: str
    meeting_date: str
    meeting_type: str
    location: str
    host: str
    participants: list[str]
    organizer: str
    copied_to: list[str]


class MeetingFact(StrictModel):
    content: str = Field(min_length=1)
    evidence: list[EvidenceSpan]
    confidence: float = Field(ge=0, le=1)
    needs_confirmation: bool

    @model_validator(mode="after")
    def require_evidence_for_confirmed_fact(self):
        if not self.needs_confirmation and not self.evidence:
            raise ValueError("confirmed facts require evidence")
        return self


class TaskTarget(StrictModel):
    project_id: Annotated[int, Field(strict=True, gt=0)]
    workstream_id: Annotated[int, Field(strict=True, gt=0)]
    key_task_id: Annotated[int, Field(strict=True, gt=0)]
    execution_schedule_id: Annotated[int, Field(strict=True, gt=0)] | None = None


class TaskUpdate(StrictModel):
    action: Literal["update_execution_schedule", "create_execution_schedule"]
    target: TaskTarget
    before: dict[str, Any]
    proposed: dict[str, Any]
    evidence: list[EvidenceSpan]
    reason: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    needs_confirmation: bool

    @model_validator(mode="after")
    def validate_target_and_evidence(self):
        schedule_id = self.target.execution_schedule_id
        if self.action == "update_execution_schedule" and schedule_id is None:
            raise ValueError("update_execution_schedule requires execution_schedule_id")
        if self.action == "create_execution_schedule" and schedule_id is not None:
            raise ValueError("create_execution_schedule forbids execution_schedule_id")
        if not self.evidence:
            raise ValueError("all task updates require evidence")
        return self


INFO_FIELDS = (
    "title",
    "meeting_date",
    "meeting_type",
    "location",
    "host",
    "participants",
    "organizer",
    "copied_to",
)


class MeetingAgentFinal(StrictModel):
    meeting_info: MeetingInfo
    meeting_info_evidence: dict[str, list[EvidenceSpan]]
    summary: str
    summary_evidence: list[EvidenceSpan]
    agenda_items: list[MeetingFact]
    decisions: list[MeetingFact]
    completed_items: list[MeetingFact]
    next_steps: list[MeetingFact]
    risks: list[MeetingFact]
    open_questions: list[MeetingFact]
    task_updates: list[TaskUpdate]

    @model_validator(mode="after")
    def validate_evidence_requirements(self):
        unknown_fields = set(self.meeting_info_evidence) - set(INFO_FIELDS)
        if unknown_fields:
            raise ValueError("meeting_info_evidence contains unknown fields")

        for field_name in INFO_FIELDS:
            value = getattr(self.meeting_info, field_name)
            if value and not self.meeting_info_evidence.get(field_name):
                raise ValueError(f"meeting_info field '{field_name}' requires evidence")

        if self.summary and not self.summary_evidence:
            raise ValueError("nonempty summary requires summary_evidence")
        return self


class ToolCallEnvelope(StrictModel):
    type: Literal["tool_call"]
    tool: str = Field(min_length=1)
    arguments: dict[str, Any]


class FinalEnvelope(StrictModel):
    type: Literal["final"]
    result: MeetingAgentFinal
