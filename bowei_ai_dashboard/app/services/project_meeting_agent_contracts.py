from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


DELTA_TYPES = frozenset(
    {
        "NO_CHANGE",
        "PROGRESS_UPDATE",
        "STATUS_CHANGE",
        "NEW_EXECUTION_SCHEDULE",
        "SCHEDULE_CHANGE",
        "ASSIGNEE_CHANGE",
        "NEW_RISK",
        "RISK_UPDATE",
        "NEW_OUTPUT",
        "COMPLETION",
        "SCOPE_CHANGE",
        "UNMATCHED",
        "AMBIGUOUS",
    }
)


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


class FieldProvenance(StrictModel):
    """Origin metadata for one structured field; it never carries business data."""

    source_type: Literal["meeting_fact", "project_baseline", "human_edit"]
    source_fact_id: str | None = None
    source_object: str | None = None
    source_field: str | None = None
    usage: Literal["new", "inherit", "override"]

    @model_validator(mode="after")
    def validate_source(self):
        if self.source_type == "meeting_fact":
            if not self.source_fact_id or self.usage != "new":
                raise ValueError("meeting_fact source requires source_fact_id and new usage")
        elif self.source_type == "project_baseline":
            if not self.source_object or not self.source_field or self.usage != "inherit":
                raise ValueError(
                    "project_baseline source requires source_object, source_field, and inherit usage"
                )
        elif self.usage != "override":
            raise ValueError("human_edit source requires override usage")
        return self


class SourcedValue(StrictModel):
    """A value emitted from a meeting fact with its original Word expression."""

    value: Any
    raw_text: str = Field(min_length=1)
    evidence: list[EvidenceSpan] = Field(min_length=1)
    provenance: FieldProvenance


class ExtractedMeetingFact(StrictModel):
    fact_id: str = Field(pattern=r"^F[0-9]{3,}$")
    fact_type: Literal[
        "action_item",
        "decision",
        "completion",
        "progress",
        "risk",
        "output",
        "scope",
    ]
    content: str = Field(min_length=1)
    fields: dict[str, SourcedValue] = Field(default_factory=dict)
    meeting_evidence: list[EvidenceSpan] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    needs_confirmation: bool = False

    @model_validator(mode="after")
    def validate_fact_id(self):
        _reject_all_zero_id(self.fact_id, "F", "fact_id")
        return self


class ProjectEvidence(StrictModel):
    source_object: str = Field(min_length=1)
    field: str = Field(min_length=1)
    value: Any


class ProjectMatch(StrictModel):
    match_id: str = Field(pattern=r"^M[0-9]{3,}$")
    fact_id: str = Field(pattern=r"^F[0-9]{3,}$")
    target_type: Literal["workstream", "key_task", "execution_schedule"]
    target_id: Annotated[int, Field(strict=True, gt=0)]
    workstream_id: Annotated[int, Field(strict=True, gt=0)]
    key_task_id: Annotated[int, Field(strict=True, gt=0)]
    confidence: float = Field(ge=0, le=1)
    reasons: list[str] = Field(min_length=1)
    project_evidence: list[ProjectEvidence] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_ids(self):
        _reject_all_zero_id(self.match_id, "M", "match_id")
        _reject_all_zero_id(self.fact_id, "F", "fact_id")
        return self


class ProjectDelta(StrictModel):
    delta_id: str = Field(pattern=r"^D[0-9]{3,}$")
    source_fact_id: str = Field(pattern=r"^F[0-9]{3,}$")
    source_match_id: str | None = Field(default=None, pattern=r"^M[0-9]{3,}$")
    delta_type: str
    reasoning: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_delta_type(self):
        if self.delta_type not in DELTA_TYPES:
            raise ValueError("delta_type is not supported")
        _reject_all_zero_id(self.delta_id, "D", "delta_id")
        _reject_all_zero_id(self.source_fact_id, "F", "source_fact_id")
        if self.source_match_id:
            _reject_all_zero_id(self.source_match_id, "M", "source_match_id")
        return self


class ProposedChange(StrictModel):
    change_id: str = Field(pattern=r"^C[0-9]{3,}$")
    source_fact_id: str = Field(pattern=r"^F[0-9]{3,}$")
    source_match_id: str = Field(pattern=r"^M[0-9]{3,}$")
    source_delta_id: str = Field(pattern=r"^D[0-9]{3,}$")
    action: Literal["update_execution_schedule", "create_execution_schedule"]
    target: TaskTarget
    before: dict[str, Any]
    proposed: dict[str, Any] = Field(min_length=1)
    field_sources: dict[str, FieldProvenance]
    requires_confirmation: Literal[True]

    @model_validator(mode="after")
    def validate_proposed_fields_and_target(self):
        _reject_all_zero_id(self.change_id, "C", "change_id")
        _reject_all_zero_id(self.source_fact_id, "F", "source_fact_id")
        _reject_all_zero_id(self.source_match_id, "M", "source_match_id")
        _reject_all_zero_id(self.source_delta_id, "D", "source_delta_id")
        if self.action == "update_execution_schedule" and self.target.execution_schedule_id is None:
            raise ValueError("update_execution_schedule requires execution_schedule_id")
        if self.action == "create_execution_schedule" and self.target.execution_schedule_id is not None:
            raise ValueError("create_execution_schedule forbids execution_schedule_id")
        if set(self.proposed) != set(self.field_sources):
            raise ValueError("field_sources must match proposed fields exactly")
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
    meeting_facts: list[ExtractedMeetingFact] = Field(default_factory=list)
    project_matches: list[ProjectMatch] = Field(default_factory=list)
    project_deltas: list[ProjectDelta] = Field(default_factory=list)
    proposed_changes: list[ProposedChange] = Field(default_factory=list)
    unmatched_items: list[ExtractedMeetingFact] = Field(default_factory=list)
    needs_confirmation: list[ExtractedMeetingFact] = Field(default_factory=list)

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
        self._validate_analysis_lineage()
        return self

    def _validate_analysis_lineage(self):
        all_facts = [
            *self.meeting_facts,
            *self.unmatched_items,
            *self.needs_confirmation,
        ]
        fact_ids = _unique_ids(all_facts, "fact_id")
        match_ids = _unique_ids(self.project_matches, "match_id")
        delta_ids = _unique_ids(self.project_deltas, "delta_id")
        _unique_ids(self.proposed_changes, "change_id")

        for fact in all_facts:
            for sourced_value in fact.fields.values():
                provenance = sourced_value.provenance
                if provenance.source_type == "human_edit":
                    raise ValueError("human_edit provenance is not permitted in model output")
                if provenance.source_type == "meeting_fact":
                    if provenance.source_fact_id not in fact_ids:
                        raise ValueError(
                            "field provenance source_fact_id must reference a known meeting fact"
                        )
                    if provenance.source_fact_id != fact.fact_id:
                        raise ValueError(
                            "field provenance source_fact_id must match enclosing fact_id"
                        )

        for match in self.project_matches:
            if match.fact_id not in fact_ids:
                raise ValueError(f"project match references unknown fact_id: {match.fact_id}")

        for delta in self.project_deltas:
            if delta.source_fact_id not in fact_ids:
                raise ValueError(f"project delta references unknown fact_id: {delta.source_fact_id}")
            if delta.source_match_id:
                match = match_ids.get(delta.source_match_id)
                if match is None:
                    raise ValueError(
                        f"project delta references unknown match_id: {delta.source_match_id}"
                    )
                if match.fact_id != delta.source_fact_id:
                    raise ValueError("project delta match_id must reference the same fact_id")

        for change in self.proposed_changes:
            if change.source_fact_id not in fact_ids:
                raise ValueError(f"proposed change references unknown fact_id: {change.source_fact_id}")
            match = match_ids.get(change.source_match_id)
            if match is None:
                raise ValueError(
                    f"proposed change references unknown match_id: {change.source_match_id}"
                )
            delta = delta_ids.get(change.source_delta_id)
            if delta is None:
                raise ValueError(
                    f"proposed change references unknown delta_id: {change.source_delta_id}"
                )
            if match.fact_id != change.source_fact_id or delta.source_fact_id != change.source_fact_id:
                raise ValueError("proposed change fact/match/delta references must share fact_id")
            if delta.source_match_id != change.source_match_id:
                raise ValueError("proposed change match_id must match its delta source_match_id")
            for provenance in change.field_sources.values():
                if provenance.source_type == "human_edit":
                    raise ValueError("human_edit provenance is not permitted in model output")


def _unique_ids(items: list[Any], attribute: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for item in items:
        identifier = getattr(item, attribute)
        if identifier in values:
            raise ValueError(f"duplicate {attribute}: {identifier}")
        values[identifier] = item
    return values


def _reject_all_zero_id(identifier: str, prefix: str, field_name: str) -> None:
    if identifier.removeprefix(prefix).strip("0") == "":
        raise ValueError(f"{field_name} must not be all zero")


class ToolCallEnvelope(StrictModel):
    type: Literal["tool_call"]
    tool: str = Field(min_length=1)
    arguments: dict[str, Any]


class FinalEnvelope(StrictModel):
    type: Literal["final"]
    result: MeetingAgentFinal
