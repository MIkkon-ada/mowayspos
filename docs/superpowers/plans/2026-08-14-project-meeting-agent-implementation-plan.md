# Project Meeting Agent Takeover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace rule-based project meeting-minute extraction with a provider-neutral Meeting Agent that queries frozen project context through read-only tools, returns a strict structured result, and produces owner-reviewed execution-schedule proposals.

**Architecture:** Keep FastAPI, SQLAlchemy, the existing `AIService`, project document storage, meeting review, and transactional writeback. Add Pydantic Agent contracts, a frozen-snapshot tool registry, and a bounded JSON-envelope orchestration loop; new Word uploads always use this Agent path and never fall back to `standard_minutes` field extraction. Preserve historical `standard_minutes` records and the existing kickoff/work-report flows.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, python-docx, pytest, React 19, TypeScript 5, Vite, Node test runner.

---

## Scope and file map

Create these focused backend units:

- `bowei_ai_dashboard/app/services/project_meeting_agent_contracts.py`: Pydantic envelopes, evidence, meeting facts, task updates, and final result.
- `bowei_ai_dashboard/app/services/project_meeting_agent_tools.py`: read-only tools over one frozen project snapshot.
- `bowei_ai_dashboard/app/services/project_meeting_agent.py`: prompt construction, bounded tool loop, format repair, trace capture, and final result.
- `bowei_ai_dashboard/app/services/project_meeting_agent_processing.py`: background run claim, Agent execution, success/failure persistence, and draft/change-set creation.
- `bowei_ai_dashboard/tests/test_project_meeting_agent_contracts.py`: schema and cross-field contract tests.
- `bowei_ai_dashboard/tests/test_project_meeting_agent_tools.py`: project boundary and tool-result tests.
- `bowei_ai_dashboard/tests/test_project_meeting_agent.py`: loop, repair, repeat detection, and step-limit tests.
- `bowei_ai_dashboard/tests/test_project_meeting_agent_processing.py`: background processing, audit persistence, and no-fallback tests.
- `bowei_ai_dashboard/tests/test_project_meeting_agent_api.py`: upload-to-review API integration tests.
- `bowei_ai_dashboard/migrations/versions/b2c3d4e5f6a7_add_project_meeting_agent_audit.py`: run audit columns.

Modify these existing units:

- `bowei_ai_dashboard/app/models.py`: extend `ProjectMeetingRun` audit fields.
- `bowei_ai_dashboard/app/services/project_meeting_minutes.py`: normalize Agent final output and validate field evidence/task updates.
- `bowei_ai_dashboard/app/routers/meetings.py`: remove standard-minutes prefill/fallback from new uploads and invoke the Agent.
- `frontend/src/api/meetings.ts`: expose Agent run state, facts, evidence, and errors; stop advertising standard parse results from text extraction.
- `frontend/src/features/meeting/NewMeetingModal.tsx`: upload/read Word without rule-prefilling fields and handle Agent run success/failure.
- `frontend/src/features/meeting/ProjectMeetingReviewWorkspace.tsx`: identify Agent analysis and display evidence/open questions.
- `frontend/src/pages/MeetingPage.tsx`: map Agent result into the review workspace.
- `frontend/tests/newMeetingMultiSource.test.mjs`: assert removal of the standard prefill branch.
- `frontend/tests/projectMeetingMinutesWorkflow.test.mjs`: assert Agent status/evidence/review behavior.
- `bowei_ai_dashboard/tests/test_project_meeting_minutes_service.py`: cover the new normalized contract while preserving writeback validation.

Do not edit `kickoff_agent.py`, `work_report_agent.py`, meeting Skill routing, realtime ASR, or historical meeting revisions except where a shared type must remain backward compatible.

The repository already contains unrelated and overlapping uncommitted work. Every implementation commit must stage only the files named by its task. Never reset or discard the existing worktree.

---

### Task 1: Define strict Meeting Agent contracts

**Files:**

- Create: `bowei_ai_dashboard/app/services/project_meeting_agent_contracts.py`
- Create: `bowei_ai_dashboard/tests/test_project_meeting_agent_contracts.py`

- [ ] **Step 1: Write failing contract tests**

Create tests that require strict envelopes, field-level evidence, project-scoped targets, and the two allowed task-update actions:

```python
from pydantic import ValidationError
import pytest

from app.services.project_meeting_agent_contracts import (
    FinalEnvelope,
    MeetingAgentFinal,
    ToolCallEnvelope,
)


def evidence(quote: str = "会议时间：2026-07-27") -> dict:
    return {"quote": quote, "char_start": 0, "char_end": len(quote)}


def final_payload() -> dict:
    info = {
        "title": "AI升级项目周会",
        "meeting_date": "2026-07-27",
        "meeting_type": "项目周会",
        "location": "线下会议室+腾讯会议",
        "host": "杨宇帆",
        "participants": ["刘万超", "吴肖"],
        "organizer": "吴肖",
        "copied_to": ["AI升级计划项目组成员"],
    }
    return {
        "meeting_info": info,
        "meeting_info_evidence": {name: [evidence()] for name in info},
        "summary": "确认本周进展和下周安排。",
        "summary_evidence": [evidence("确认本周进展和下周安排。")],
        "agenda_items": [],
        "decisions": [],
        "completed_items": [],
        "next_steps": [],
        "risks": [],
        "open_questions": [],
        "task_updates": [],
    }


def test_tool_call_envelope_forbids_extra_fields():
    with pytest.raises(ValidationError):
        ToolCallEnvelope.model_validate({
            "type": "tool_call",
            "tool": "get_project_profile",
            "arguments": {"project_id": 1},
            "unexpected": True,
        })


def test_final_envelope_validates_nested_result():
    envelope = FinalEnvelope.model_validate({"type": "final", "result": final_payload()})
    assert envelope.result.meeting_info.host == "杨宇帆"


def test_task_update_rejects_parent_task_creation():
    payload = final_payload()
    payload["task_updates"] = [{
        "action": "create_key_task",
        "target": {"project_id": 1, "workstream_id": 10, "key_task_id": 20},
        "before": {},
        "proposed": {"title": "新任务"},
        "evidence": [evidence("下周新增一个关键任务")],
        "reason": "会议提出新增",
        "confidence": 0.8,
        "needs_confirmation": False,
    }]
    with pytest.raises(ValidationError):
        MeetingAgentFinal.model_validate(payload)


def test_nonempty_meeting_info_requires_field_evidence():
    payload = final_payload()
    payload["meeting_info_evidence"] = {}
    with pytest.raises(ValidationError, match="meeting_info_evidence"):
        MeetingAgentFinal.model_validate(payload)


def test_confirmed_fact_requires_evidence():
    payload = final_payload()
    payload["decisions"] = [{
        "content": "确认方案",
        "evidence": [],
        "confidence": 0.9,
        "needs_confirmation": False,
    }]
    with pytest.raises(ValidationError, match="evidence"):
        MeetingAgentFinal.model_validate(payload)
```

- [ ] **Step 2: Run the tests and verify the module is missing**

Run:

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent_contracts.py -q
```

Expected: collection fails with `ModuleNotFoundError: app.services.project_meeting_agent_contracts`.

- [ ] **Step 3: Implement the strict contracts**

Create `project_meeting_agent_contracts.py` with `extra="forbid"` on every model. Use these public types and field names consistently in all later tasks:

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceSpan(StrictModel):
    quote: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_range(self):
        if self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        return self


class MeetingInfo(StrictModel):
    title: str = ""
    meeting_date: str = ""
    meeting_type: str = ""
    location: str = ""
    host: str = ""
    participants: list[str] = Field(default_factory=list)
    organizer: str = ""
    copied_to: list[str] = Field(default_factory=list)


class MeetingFact(StrictModel):
    content: str = Field(min_length=1)
    evidence: list[EvidenceSpan] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    needs_confirmation: bool = False

    @model_validator(mode="after")
    def require_evidence_for_confirmed_fact(self):
        if not self.needs_confirmation and not self.evidence:
            raise ValueError("confirmed fact requires evidence")
        return self


class TaskTarget(StrictModel):
    project_id: int = Field(gt=0)
    workstream_id: int = Field(gt=0)
    key_task_id: int = Field(gt=0)
    execution_schedule_id: int | None = Field(default=None, gt=0)


class TaskUpdate(StrictModel):
    action: Literal["update_execution_schedule", "create_execution_schedule"]
    target: TaskTarget
    before: dict[str, Any] = Field(default_factory=dict)
    proposed: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceSpan] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    needs_confirmation: bool = False

    @model_validator(mode="after")
    def validate_target_shape(self):
        if self.action == "update_execution_schedule" and self.target.execution_schedule_id is None:
            raise ValueError("update_execution_schedule requires execution_schedule_id")
        if self.action == "create_execution_schedule" and self.target.execution_schedule_id is not None:
            raise ValueError("create_execution_schedule cannot include execution_schedule_id")
        if not self.needs_confirmation and not self.evidence:
            raise ValueError("executable task update requires evidence")
        return self


INFO_FIELDS = frozenset(MeetingInfo.model_fields)


class MeetingAgentFinal(StrictModel):
    meeting_info: MeetingInfo
    meeting_info_evidence: dict[str, list[EvidenceSpan]] = Field(default_factory=dict)
    summary: str = ""
    summary_evidence: list[EvidenceSpan] = Field(default_factory=list)
    agenda_items: list[MeetingFact] = Field(default_factory=list)
    decisions: list[MeetingFact] = Field(default_factory=list)
    completed_items: list[MeetingFact] = Field(default_factory=list)
    next_steps: list[MeetingFact] = Field(default_factory=list)
    risks: list[MeetingFact] = Field(default_factory=list)
    open_questions: list[MeetingFact] = Field(default_factory=list)
    task_updates: list[TaskUpdate] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_meeting_info_evidence(self):
        unknown = set(self.meeting_info_evidence) - INFO_FIELDS
        if unknown:
            raise ValueError(f"unknown meeting_info_evidence fields: {sorted(unknown)}")
        values = self.meeting_info.model_dump()
        missing = [
            name for name, value in values.items()
            if value not in ("", []) and not self.meeting_info_evidence.get(name)
        ]
        if missing:
            raise ValueError(f"meeting_info_evidence missing for: {missing}")
        if self.summary and not self.summary_evidence:
            raise ValueError("nonempty summary requires summary_evidence")
        return self


class ToolCallEnvelope(StrictModel):
    type: Literal["tool_call"]
    tool: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class FinalEnvelope(StrictModel):
    type: Literal["final"]
    result: MeetingAgentFinal
```

- [ ] **Step 4: Run contract tests**

Run the same pytest command. Expected: all tests pass.

- [ ] **Step 5: Commit only Task 1 files**

```powershell
git add bowei_ai_dashboard/app/services/project_meeting_agent_contracts.py bowei_ai_dashboard/tests/test_project_meeting_agent_contracts.py
git commit -m "feat: define project meeting agent contracts"
```

---

### Task 2: Add read-only Agent tools over the frozen project snapshot

**Files:**

- Create: `bowei_ai_dashboard/app/services/project_meeting_agent_tools.py`
- Create: `bowei_ai_dashboard/tests/test_project_meeting_agent_tools.py`
- Modify: `bowei_ai_dashboard/app/services/project_meeting_minutes.py:89`

- [ ] **Step 1: Write failing tool tests**

Build a frozen snapshot with two projects' IDs represented in test data and require all tools to stay inside `snapshot["project_id"]`:

```python
import pytest

from app.services.project_meeting_agent_tools import (
    AgentToolError,
    ProjectMeetingAgentTools,
)


SNAPSHOT = {
    "project_id": 1,
    "project": {"id": 1, "name": "AI升级计划", "objectives": "完成AI升级"},
    "members": [{"person_id": 7, "name": "吴肖", "role": "member"}],
    "workstreams": [{
        "id": 10,
        "key_task": "完善项目管理机制",
        "status": "进行中",
        "key_tasks": [{
            "id": 20,
            "title": "完善会议纪要流程",
            "status": "进行中",
            "execution_schedules": [{"id": 30, "title": "完成Agent方案", "status": "未开始"}],
        }],
    }],
    "recent_progress": [{"key_task_id": 20, "content": "已完成流程初稿"}],
    "previous_meetings": [],
    "history": {"is_first_meeting": True, "previous_meeting_ids": []},
}


def test_search_plan_nodes_returns_ids_and_parent_relationships():
    tools = ProjectMeetingAgentTools(SNAPSHOT)
    result = tools.execute("search_plan_nodes", {"project_id": 1, "query": "会议纪要"})
    assert result["matches"][0]["key_task_id"] == 20
    assert result["matches"][0]["execution_schedule_ids"] == [30]


def test_first_meeting_returns_empty_previous_meetings():
    tools = ProjectMeetingAgentTools(SNAPSHOT)
    assert tools.execute("get_previous_meetings", {"project_id": 1, "limit": 5}) == {
        "is_first_meeting": True,
        "meetings": [],
    }


def test_tool_rejects_cross_project_arguments():
    tools = ProjectMeetingAgentTools(SNAPSHOT)
    with pytest.raises(AgentToolError, match="project boundary"):
        tools.execute("list_project_members", {"project_id": 2})


def test_unknown_tool_is_rejected():
    tools = ProjectMeetingAgentTools(SNAPSHOT)
    with pytest.raises(AgentToolError, match="unknown tool"):
        tools.execute("write_execution_schedule", {"project_id": 1})
```

- [ ] **Step 2: Run the tests and verify failure**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent_tools.py -q
```

Expected: `ModuleNotFoundError` for `project_meeting_agent_tools`.

- [ ] **Step 3: Extend the frozen snapshot with recent progress and published meeting summaries**

Modify `build_project_meeting_snapshot()` so its return object includes `recent_progress` and `previous_meetings`. Query only the selected project and only confirmed/published records. Keep the existing `project`, `members`, `workstreams`, and `history` keys unchanged for compatibility.

Use this exact output shape:

```python
return {
    "project_id": project_id,
    "project": project_payload,
    "members": member_snapshot,
    "workstreams": workstreams,
    "recent_progress": recent_progress,
    "previous_meetings": previous_meetings,
    "history": {
        "is_first_meeting": not previous_meeting_ids,
        "previous_meeting_ids": previous_meeting_ids,
    },
}
```

Each recent-progress item must contain `key_task_id`, `execution_schedule_id`, `content`, `actual_output`, `status`, and `updated_at`. Each prior-meeting item must contain `meeting_id`, `meeting_date`, `title`, `summary`, `decisions`, and `actions`; cap the snapshot to the five newest published meetings.

- [ ] **Step 4: Implement the read-only registry**

Create `ProjectMeetingAgentTools` with a fixed dispatch table. Tool implementations read only `self.snapshot`, return JSON-compatible dictionaries, and never receive a database session:

```python
class AgentToolError(ValueError):
    pass


class ProjectMeetingAgentTools:
    TOOL_NAMES = frozenset({
        "get_project_profile",
        "list_project_members",
        "search_plan_nodes",
        "get_plan_node_detail",
        "get_recent_progress",
        "get_previous_meetings",
    })

    def __init__(self, snapshot: dict):
        self.snapshot = snapshot
        self.project_id = int(snapshot["project_id"])

    def execute(self, name: str, arguments: dict) -> dict:
        if name not in self.TOOL_NAMES:
            raise AgentToolError(f"unknown tool: {name}")
        if arguments.get("project_id") != self.project_id:
            raise AgentToolError("tool call violates project boundary")
        return getattr(self, f"_{name}")(arguments)
```

`search_plan_nodes` performs retrieval only: case-insensitive substring/token overlap across workstream, key-task, and execution-schedule titles and returns at most ten candidates. It must not decide that a meeting fact is complete, delayed, assigned, or approved.

- [ ] **Step 5: Run tool and existing snapshot tests**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent_tools.py tests/test_project_meeting_minutes_service.py -q
```

Expected: all tests pass, including the existing first-meeting assertion.

- [ ] **Step 6: Commit only Task 2 files**

```powershell
git add bowei_ai_dashboard/app/services/project_meeting_agent_tools.py bowei_ai_dashboard/app/services/project_meeting_minutes.py bowei_ai_dashboard/tests/test_project_meeting_agent_tools.py bowei_ai_dashboard/tests/test_project_meeting_minutes_service.py
git commit -m "feat: add project meeting agent read tools"
```

---

### Task 3: Implement the bounded Agent orchestration loop

**Files:**

- Create: `bowei_ai_dashboard/app/services/project_meeting_agent.py`
- Create: `bowei_ai_dashboard/tests/test_project_meeting_agent.py`

- [ ] **Step 1: Write failing orchestration tests**

Use a sequence provider so tests do not call a real model:

```python
import json
import pytest

from app.services.project_meeting_agent import (
    AgentModelResponse,
    MeetingAgentError,
    run_project_meeting_agent,
)
from app.services.project_meeting_agent_tools import ProjectMeetingAgentTools


def response(payload: dict, call_id: int) -> AgentModelResponse:
    return AgentModelResponse(
        text=json.dumps(payload, ensure_ascii=False),
        model_code="fake-chat",
        invocation_log_id=call_id,
    )


def test_agent_executes_tool_then_returns_final(snapshot, valid_final):
    events = []
    replies = iter([
        response({"type": "tool_call", "tool": "search_plan_nodes", "arguments": {"project_id": 1, "query": "会议纪要"}}, 11),
        response({"type": "final", "result": valid_final}, 12),
    ])
    result = run_project_meeting_agent(
        project_id=1,
        document_text="会议时间：2026-07-27\n完善会议纪要流程",
        requested_meeting_type="项目周会",
        snapshot=snapshot,
        tools=ProjectMeetingAgentTools(snapshot),
        provider=lambda prompt: next(replies),
        on_event=events.append,
    )
    assert result.final.meeting_info.meeting_date == "2026-07-27"
    assert result.invocation_log_ids == [11, 12]
    assert result.trace[0]["tool"] == "search_plan_nodes"
    assert [event["kind"] for event in events] == ["model_response", "tool_result", "model_response", "final"]


def test_agent_repairs_one_invalid_json_response(snapshot, valid_final):
    replies = iter([
        AgentModelResponse("not-json", "fake-chat", 21),
        response({"type": "final", "result": valid_final}, 22),
    ])
    result = run_project_meeting_agent(
        project_id=1,
        document_text="会议时间：2026-07-27",
        requested_meeting_type="",
        snapshot=snapshot,
        tools=ProjectMeetingAgentTools(snapshot),
        provider=lambda prompt: next(replies),
    )
    assert result.invocation_log_ids == [21, 22]


def test_agent_blocks_repeated_identical_tool_call(snapshot):
    duplicate = {"type": "tool_call", "tool": "get_project_profile", "arguments": {"project_id": 1}}
    replies = iter([response(duplicate, 31), response(duplicate, 32)])
    with pytest.raises(MeetingAgentError) as exc:
        run_project_meeting_agent(1, "正文", snapshot, ProjectMeetingAgentTools(snapshot), lambda prompt: next(replies))
    assert exc.value.code == "repeated_tool_call"


def test_agent_stops_at_six_steps(snapshot):
    replies = iter([
        response({"type": "tool_call", "tool": "search_plan_nodes", "arguments": {"project_id": 1, "query": str(index)}}, index)
        for index in range(1, 7)
    ])
    with pytest.raises(MeetingAgentError) as exc:
        run_project_meeting_agent(1, "正文", snapshot, ProjectMeetingAgentTools(snapshot), lambda prompt: next(replies))
    assert exc.value.code == "step_limit_exceeded"
```

Provide local `snapshot` and `valid_final` pytest fixtures in the same test file. Ensure every nonempty meeting-info field in `valid_final` has exact evidence ranges against the test document.

- [ ] **Step 2: Run tests and verify failure**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent.py -q
```

Expected: the orchestration module is missing.

- [ ] **Step 3: Implement prompt construction and model response types**

Create these public dataclasses and constants:

```python
PROMPT_VERSION = "project-meeting-agent-v1"
MAX_AGENT_STEPS = 6


@dataclass(frozen=True)
class AgentModelResponse:
    text: str
    model_code: str
    invocation_log_id: int


@dataclass(frozen=True)
class MeetingAgentRunResult:
    final: MeetingAgentFinal
    trace: list[dict[str, Any]]
    raw_responses: list[str]
    invocation_log_ids: list[int]
    model_code: str
    step_count: int


class MeetingAgentError(RuntimeError):
    def __init__(self, code: str, message: str, *, trace=None, raw_responses=None, invocation_log_ids=None):
        super().__init__(message)
        self.code = code
        self.trace = list(trace or [])
        self.raw_responses = list(raw_responses or [])
        self.invocation_log_ids = list(invocation_log_ids or [])
```

The `run_project_meeting_agent` signature must accept `project_id`, `document_text`, `snapshot`, `tools`, `provider`, optional `requested_meeting_type=""`, and optional `on_event: Callable[[dict[str, Any]], None] | None = None`. The system prompt must state in Chinese that the Word text is the only meeting-fact source; a user-selected meeting type is context but cannot overwrite a contradictory document fact; project tools are context only; each nonempty basic-information field and each fact/update needs an exact evidence span; the model may return only one tool-call or final envelope; missing information stays empty or becomes `open_questions`; only two execution-schedule actions are allowed.

- [ ] **Step 4: Implement strict envelope parsing, one repair, and the six-step loop**

Use `json.loads(response.text)` and validate first as `ToolCallEnvelope`, then as `FinalEnvelope`, selected by `payload["type"]`. Do not search arbitrary surrounding prose for a JSON object. On the first malformed response, issue one repair prompt containing the validation error and the invalid response; a second malformed response raises `MeetingAgentError("invalid_model_output", ...)`.

For each legal tool call:

```python
signature = (envelope.tool, json.dumps(envelope.arguments, ensure_ascii=False, sort_keys=True))
if signature in seen_tool_calls:
    raise MeetingAgentError("repeated_tool_call", "model repeated an identical tool call", ...)
observation = tools.execute(envelope.tool, envelope.arguments)
trace.append({"step": step, "tool": envelope.tool, "arguments": envelope.arguments, "observation": observation})
```

Append observations to the next prompt. Return `MeetingAgentRunResult` only after a validated `FinalEnvelope`.

Emit `on_event` callbacks after each model response, tool result, and final envelope. Events contain only `kind`, `step`, tool name/arguments where applicable, model code, and invocation log ID; do not copy the full document into events.

- [ ] **Step 5: Run Agent tests**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent.py tests/test_project_meeting_agent_contracts.py tests/test_project_meeting_agent_tools.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit only Task 3 files**

```powershell
git add bowei_ai_dashboard/app/services/project_meeting_agent.py bowei_ai_dashboard/tests/test_project_meeting_agent.py
git commit -m "feat: orchestrate project meeting agent"
```

---

### Task 4: Persist Agent audit state and an unambiguous execution-schedule parent

**Files:**

- Modify: `bowei_ai_dashboard/app/models.py:143`
- Create: `bowei_ai_dashboard/migrations/versions/b2c3d4e5f6a7_add_project_meeting_agent_audit.py`
- Create: `bowei_ai_dashboard/tests/test_project_meeting_agent_models.py`

- [ ] **Step 1: Write failing model tests**

```python
from app import models


def test_project_meeting_run_has_agent_audit_columns():
    columns = models.ProjectMeetingRun.__table__.columns
    expected = {
        "stage", "step_count", "prompt_version", "model_code",
        "invocation_log_ids_json", "tool_trace_json", "raw_responses_json",
        "validation_json", "error_code", "requested_meeting_type",
    }
    assert expected <= set(columns.keys())


def test_project_meeting_run_agent_defaults_survive_insert(db):
    run = models.ProjectMeetingRun(project_id=1, document_source_id=1)
    db.add(run)
    db.commit()
    db.refresh(run)
    assert run.stage == "created"
    assert run.step_count == 0
    assert run.invocation_log_ids_json == "[]"
    assert run.tool_trace_json == "[]"
    assert run.raw_responses_json == "[]"
    assert run.validation_json == "{}"
    assert run.error_code == ""
    assert run.requested_meeting_type == ""


def test_meeting_change_proposal_has_subtask_parent_column():
    columns = models.MeetingChangeProposal.__table__.columns
    assert "parent_subtask_id" in columns
    assert list(columns["parent_subtask_id"].foreign_keys)[0].target_fullname == "subtasks.id"
```

Set up the in-memory project and document source in the fixture before inserting the run.

- [ ] **Step 2: Run the model test and verify missing columns**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent_models.py -q
```

Expected: assertion fails because the audit columns do not exist.

- [ ] **Step 3: Add model fields**

Add to `ProjectMeetingRun`:

```python
stage = Column(String(32), nullable=False, default="created", server_default="created", index=True)
step_count = Column(Integer, nullable=False, default=0, server_default="0")
prompt_version = Column(String(64), nullable=False, default="", server_default="")
model_code = Column(String(96), nullable=False, default="", server_default="")
invocation_log_ids_json = Column(Text, nullable=False, default="[]", server_default="[]")
tool_trace_json = Column(Text, nullable=False, default="[]", server_default="[]")
raw_responses_json = Column(Text, nullable=False, default="[]", server_default="[]")
validation_json = Column(Text, nullable=False, default="{}", server_default="{}")
error_code = Column(String(64), nullable=False, default="", server_default="", index=True)
requested_meeting_type = Column(String(80), nullable=False, default="", server_default="")
```

Add to `MeetingChangeProposal` without changing the existing polymorphic `parent_workstream_id` behavior used by general meeting change sets:

```python
parent_subtask_id = Column(Integer, ForeignKey("subtasks.id"), nullable=True, index=True)
```

Project meeting execution-schedule proposals use `parent_subtask_id`; generic workstream/subtask proposals continue using `parent_workstream_id`.

- [ ] **Step 4: Add the Alembic migration**

Use revision `b2c3d4e5f6a7` and `down_revision = "a1b2c3d4e5f6"`. Add the ten `ProjectMeetingRun` columns and indexes for `stage` and `error_code`. Also add nullable `meeting_change_proposals.parent_subtask_id`, its foreign key to `subtasks.id`, and its index. Downgrade removes indexes/foreign key first, then columns in reverse order.

- [ ] **Step 5: Verify ORM and migration**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent_models.py -q
python -m alembic heads
python -m alembic upgrade head
```

Expected: tests pass, Alembic reports only `b2c3d4e5f6a7 (head)`, and upgrade succeeds against the configured development database. Before running the upgrade, make a database backup using the existing project database migration/backup procedure; do not delete or recreate the database.

For the current SQLite development database, run this backup immediately before `alembic upgrade head`:

```powershell
$backupStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$databaseSource = (Resolve-Path '.\bowei_ai_dashboard.db').Path
$backupDirectory = Join-Path (Get-Location) 'backups'
New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
$backupTarget = Join-Path $backupDirectory "bowei_ai_dashboard-pre-meeting-agent-$backupStamp.db"
Copy-Item -LiteralPath $databaseSource -Destination $backupTarget
Get-Item -LiteralPath $backupTarget | Select-Object FullName, Length
```

Expected: a nonzero backup file is printed under `bowei_ai_dashboard/backups/`.

- [ ] **Step 6: Commit only Task 4 files**

```powershell
git add bowei_ai_dashboard/app/models.py bowei_ai_dashboard/migrations/versions/b2c3d4e5f6a7_add_project_meeting_agent_audit.py bowei_ai_dashboard/tests/test_project_meeting_agent_models.py
git commit -m "feat: persist project meeting agent audit"
```

---

### Task 5: Normalize Agent output and enforce evidence/writeback safety

**Files:**

- Modify: `bowei_ai_dashboard/app/services/project_meeting_minutes.py:254`
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_minutes_service.py`

- [ ] **Step 1: Add failing normalization tests**

Add tests for `normalize_project_meeting_agent_result(final, document_text, snapshot)`:

```python
def test_normalizes_agent_meeting_info_without_rule_overrides(db, project_plan):
    project, schedule = project_plan
    text = "会议时间：2026-07-27\n主持人：杨宇帆"
    date_quote = "2026-07-27"
    host_quote = "杨宇帆"
    final = MeetingAgentFinal.model_validate({
        "meeting_info": {
            "title": "", "meeting_date": "2026-07-27", "meeting_type": "",
            "location": "", "host": "杨宇帆", "participants": [],
            "organizer": "", "copied_to": [],
        },
        "meeting_info_evidence": {
            "meeting_date": [{
                "quote": date_quote,
                "char_start": text.index(date_quote),
                "char_end": text.index(date_quote) + len(date_quote),
            }],
            "host": [{
                "quote": host_quote,
                "char_start": text.index(host_quote),
                "char_end": text.index(host_quote) + len(host_quote),
            }],
        },
        "summary": "",
        "agenda_items": [], "decisions": [], "completed_items": [],
        "next_steps": [], "risks": [], "open_questions": [], "task_updates": [],
    })
    normalized = normalize_project_meeting_agent_result(final, text, build_project_meeting_snapshot(project.id, db))
    assert normalized["meeting_draft"]["meeting_date"] == "2026-07-27"
    assert normalized["meeting_draft"]["host"] == "杨宇帆"
    assert normalized["meeting_info_evidence"]["host"][0]["validation"]["state"] == "ready"


def test_blocks_metadata_evidence_with_wrong_character_range(project_plan):
    text = "主持人：杨宇帆"
    final = valid_final_with_host_evidence(char_start=0, char_end=3)
    normalized = normalize_project_meeting_agent_result(final, text, snapshot)
    assert normalized["meeting_info_evidence"]["host"][0]["validation"]["state"] == "blocked"


def test_task_update_without_exact_word_evidence_cannot_execute(project_plan):
    final = final_with_schedule_update(evidence_quote="文档里不存在的句子")
    normalized = normalize_project_meeting_agent_result(final, document_text, snapshot)
    assert normalized["execution_schedule_changes"][0]["validation"]["state"] == "blocked"


def test_task_update_blocks_mismatched_workstream_and_key_task(project_plan):
    final = final_with_schedule_update(workstream_id=999, key_task_id=project_plan[1].subtask_id)
    normalized = normalize_project_meeting_agent_result(final, document_text, snapshot)
    assert "key_task_id does not belong to workstream_id" in normalized["execution_schedule_changes"][0]["validation"]["errors"]
```

Use the actual character positions calculated by `text.index(quote)` in fixtures so tests express the contract without fragile magic numbers.

- [ ] **Step 2: Run the targeted tests and verify the function is missing**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_minutes_service.py -q
```

Expected: import or attribute failure for `normalize_project_meeting_agent_result`.

- [ ] **Step 3: Implement evidence-span validation**

Add:

```python
def validate_evidence_span(span: EvidenceSpan, document_text: str) -> dict[str, Any]:
    errors: list[str] = []
    if span.char_end > len(document_text):
        errors.append("evidence range exceeds document_text")
    elif document_text[span.char_start:span.char_end] != span.quote:
        errors.append("evidence quote does not match document_text range")
    return {
        **span.model_dump(),
        "validation": {"state": "ready" if not errors else "blocked", "errors": errors},
    }
```

Do not repair offsets by searching for another matching quote; incorrect model offsets must remain visible as blocked evidence.

- [ ] **Step 4: Implement final-result normalization**

`normalize_project_meeting_agent_result` must:

- convert participant and copied-to lists to `、`-joined meeting fields;
- preserve field-level and summary evidence with validation;
- normalize every fact collection with span validation;
- convert `task_updates` into the existing `execution_schedule_changes` shape;
- pass converted task updates through `validate_execution_schedule_proposal` so project IDs, task IDs, dates, writable fields, and exact quotes are checked again;
- verify `target.key_task_id` belongs to `target.workstream_id`; for an update, verify the execution schedule belongs to that same key task;
- mark a task update blocked if `needs_confirmation` is true or any evidence span is blocked;
- return `meeting_draft`, `meeting_info_evidence`, `summary_evidence`, `agenda_items`, `decisions`, `completed_items`, `next_stage_work`, `risks`, `open_questions`, and `execution_schedule_changes`.

Keep `normalize_project_meeting_result` for legacy callers until repository search proves it is unused outside historical/general analysis paths.

- [ ] **Step 5: Run normalization and change-set tests**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_minutes_service.py tests/test_meeting_change_set_service.py tests/test_meeting_change_set_writeback.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit only Task 5 files**

```powershell
git add bowei_ai_dashboard/app/services/project_meeting_minutes.py bowei_ai_dashboard/tests/test_project_meeting_minutes_service.py
git commit -m "feat: validate project meeting agent output"
```

---

### Task 6: Route new Word uploads exclusively through the Agent

**Files:**

- Modify: `bowei_ai_dashboard/app/routers/meetings.py:737-979`
- Create: `bowei_ai_dashboard/app/services/project_meeting_agent_processing.py`
- Create: `bowei_ai_dashboard/tests/test_project_meeting_agent_api.py`
- Create: `bowei_ai_dashboard/tests/test_project_meeting_agent_processing.py`

- [ ] **Step 1: Write failing API characterization tests**

Use FastAPI's test client with a test database. Monkeypatch the background processor to a no-op so the POST response can be asserted before processing:

```python
def test_extract_document_text_does_not_return_standard_minutes(client, auth, docx_bytes):
    response = client.post(
        "/api/meetings/extract-document-text?project_id=1",
        headers=auth,
        files={"file": ("minutes.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200
    assert set(response.json()) == {"filename", "text"}


def test_document_run_is_queued_without_waiting_for_model(client, auth, docx_bytes, monkeypatch):
    monkeypatch.setattr(meetings, "process_project_meeting_run", lambda run_id: None)
    response = upload_project_minutes(client, auth, docx_bytes)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["stage"] == "queued"
    assert body["meeting_id"] is None


def test_get_document_run_exposes_agent_progress(client, auth, queued_run):
    response = client.get(f"/api/meetings/document-runs/{queued_run.id}", headers=auth)
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert response.json()["stage"] == "queued"
```

Create processing tests that use a file-backed SQLite `session_factory`; background processing must never reuse the request session:

```python
def test_processor_uses_agent_result_for_all_basic_fields(db_factory, queued_run, monkeypatch):
    monkeypatch.setattr(processing, "run_project_meeting_agent", fake_successful_agent_run)
    processing.process_project_meeting_run(queued_run.id, session_factory=db_factory)
    with db_factory() as db:
        run = db.get(models.ProjectMeetingRun, queued_run.id)
        meeting = db.query(models.Meeting).filter_by(document_source_id=run.document_source_id).one()
        assert run.status == "completed"
        assert run.stage == "pending_review"
        assert meeting.meeting_date == "2026-07-27"
        assert meeting.host == "杨宇帆"
        assert meeting.source_mode == "ai_analysis"


def test_processor_persists_agent_failure_without_rule_fallback(db_factory, queued_run, monkeypatch):
    monkeypatch.setattr(processing, "run_project_meeting_agent", fake_agent_failure)
    processing.process_project_meeting_run(queued_run.id, session_factory=db_factory)
    with db_factory() as db:
        run = db.get(models.ProjectMeetingRun, queued_run.id)
        assert run.status == "failed"
        assert run.error_code == "invalid_model_output"
        assert db.query(models.Meeting).count() == 0


def test_first_meeting_does_not_require_previous_minutes(db_factory, first_meeting_run, monkeypatch):
    monkeypatch.setattr(processing, "run_project_meeting_agent", fake_successful_agent_run)
    processing.process_project_meeting_run(first_meeting_run.id, session_factory=db_factory)
    with db_factory() as db:
        run = db.get(models.ProjectMeetingRun, first_meeting_run.id)
        assert json.loads(run.snapshot_json)["history"]["is_first_meeting"] is True
        assert run.status == "completed"
```

- [ ] **Step 2: Run API tests and verify current standard fallback assertions fail**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent_api.py tests/test_project_meeting_agent_processing.py -q
```

Expected: failures show `standard_minutes` in extraction output and the processor module/Agent entrypoint is missing.

- [ ] **Step 3: Remove rule extraction from the new-upload path**

In `extract_document_text`, return only:

```python
return {"filename": filename, "text": text}
```

Remove `parse_standard_meeting_minutes` from this endpoint and `create_project_meeting_document_run`. Delete `_project_meeting_prompt`, `_fallback_project_meeting_result`, and the standard-fallback merge. Keep the parser module itself only for historical compatibility/tests until all other references are audited.

- [ ] **Step 4: Queue the run and return immediately**

Add `background_tasks: BackgroundTasks` to `create_project_meeting_document_run`. After storing the source, extracted text, frozen snapshot, and requested meeting type, create and queue the run:

```python
run = models.ProjectMeetingRun(
    project_id=project_id,
    document_source_id=source.id,
    snapshot_json=json.dumps(snapshot, ensure_ascii=False),
    document_text=document_text,
    requested_meeting_type=meeting_type.strip(),
    status="queued",
    stage="queued",
    created_by_person_id=account.person_id if account else None,
)
db.add(run)
db.commit()
db.refresh(run)
background_tasks.add_task(process_project_meeting_run, run.id)
return _project_meeting_payload(run, db)
```

Do not invoke a model inside the request transaction. The existing `GET /document-runs/{run_id}` is the polling endpoint.

- [ ] **Step 5: Implement the background processor and Agent provider**

Create `project_meeting_agent_processing.py`. `process_project_meeting_run(run_id, session_factory=SessionLocal)` opens a fresh session and atomically claims only a `queued` run by changing it to `processing`. A second worker that cannot claim the row returns without invoking the model.

Inside the claimed run, construct the provider closure:

```python
ai_service = AIService(db)

def provider(prompt: str) -> AgentModelResponse:
    response = ai_service.invoke_chat(
        Capability.MEETING_ANALYSIS,
        prompt,
        AIInvocationContext(
            resource_type="project_meeting_run",
            resource_id=run.id,
            actor=str(run.created_by_person_id or ""),
        ),
    )
    return AgentModelResponse(
        text=response.text,
        model_code=response.model_code,
        invocation_log_id=response.invocation_log_id,
)
```

Call `run_project_meeting_agent` with the frozen snapshot, `run.requested_meeting_type`, and `ProjectMeetingAgentTools(snapshot)`. Normalize with `normalize_project_meeting_agent_result`. Move `_project_meeting_change_set` from the router into this processing service so the service atomically creates the `Meeting`, proposals, and submitted review event without importing the HTTP router.

When persisting an execution-schedule proposal, store `target.workstream_id` in `parent_workstream_id` and `target.key_task_id` in the new `parent_subtask_id`. Extend `_meeting_change_set_payload` to expose both values. In `_execute_project_meeting_schedule_changes`, reconstruct `target.key_task_id` from `parent_subtask_id`, revalidate the parent relationship, and use `parent_subtask_id` when creating an `ExecutionSchedule`; never load a `SubTask` from `parent_workstream_id`.

Pass an `on_event` callback that commits safe stage progress for polling:

```python
def persist_agent_event(event: dict[str, Any]) -> None:
    kind = event.get("kind")
    tool = event.get("tool")
    if kind == "tool_result" and tool in {"search_plan_nodes", "get_plan_node_detail"}:
        stage = "matching_plan"
    elif kind == "tool_result":
        stage = "querying_project"
    elif kind == "final":
        stage = "validating"
    else:
        stage = "understanding"
    db.query(models.ProjectMeetingRun).filter_by(id=run.id, status="processing").update({
        models.ProjectMeetingRun.stage: stage,
        models.ProjectMeetingRun.step_count: int(event.get("step") or 0),
    })
    db.commit()
```

The callback stores stage metadata only. The complete bounded tool trace is written once from `MeetingAgentRunResult` on success or `MeetingAgentError` on failure.

- [ ] **Step 6: Persist success and failure without fabricating a draft**

On success:

- persist trace, raw responses, invocation IDs, model code, prompt version, step count, and validation output;
- create `Meeting`, `MeetingChangeSet`, proposals, and `submitted` review event;
- always set `source_mode="ai_analysis"`;
- set `run.status="completed"` and `run.stage="pending_review"`.

On `MeetingAgentError` or AI service failure:

```python
run.status = "failed"
run.stage = "failed"
run.error_code = safe_agent_error_code(exc)
run.error_message = safe_agent_error_message(exc)
run.tool_trace_json = json.dumps(getattr(exc, "trace", []), ensure_ascii=False)
run.raw_responses_json = json.dumps(getattr(exc, "raw_responses", []), ensure_ascii=False)
run.invocation_log_ids_json = json.dumps(getattr(exc, "invocation_log_ids", []))
db.commit()
return
```

Do not create a `Meeting` or `MeetingChangeSet` on failure. Do not put provider secrets, raw exception representations, or document contents into `error_message`.

If Word extraction fails after storage succeeds, the request path persists a failed run with `stage="document_read"`, `error_code="document_read_failed"`, empty `document_text`, and the safe parser message; it does not enqueue processing.

- [ ] **Step 7: Extend `_project_meeting_payload`**

Return `stage`, `step_count`, `prompt_version`, `model_code`, `invocation_log_ids`, `tool_trace`, `validation`, and `error_code`, parsing JSON columns with the existing `_json_value` helper.

- [ ] **Step 8: Run project-meeting processing, API, and existing review tests**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent_processing.py tests/test_project_meeting_agent_api.py tests/test_project_meeting_minutes_service.py tests/test_meeting_draft_review.py tests/test_meeting_revision_api.py -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit only Task 6 files**

```powershell
git add bowei_ai_dashboard/app/routers/meetings.py bowei_ai_dashboard/app/services/project_meeting_agent_processing.py bowei_ai_dashboard/tests/test_project_meeting_agent_api.py bowei_ai_dashboard/tests/test_project_meeting_agent_processing.py
git commit -m "feat: route project minutes through meeting agent"
```

---

### Task 7: Update frontend creation flow and API types

**Files:**

- Modify: `frontend/src/api/meetings.ts:252-333`
- Modify: `frontend/src/features/meeting/NewMeetingModal.tsx:190-280`
- Modify: `frontend/tests/newMeetingMultiSource.test.mjs`
- Modify: `frontend/tests/projectMeetingMinutesWorkflow.test.mjs`

- [ ] **Step 1: Change frontend tests first**

Replace the old assertions requiring `result.standard_minutes` and `source_mode: 'standard_minutes'` with:

```javascript
assert.doesNotMatch(modal, /result\.standard_minutes/)
assert.doesNotMatch(modal, /minutes\.current_action_items/)
assert.match(modal, /createProjectMeetingDocumentRun\(projectId, documentFile, form\.meeting_type\)/)
assert.match(modal, /fetchProjectMeetingDocumentRun\(current\.id\)/)
assert.match(modal, /AGENT_STAGE_LABELS/)
assert.match(modal, /run\.status === 'failed'/)
assert.match(modal, /run\.error_message/)
assert.match(modal, /source_mode: 'ai_analysis'/)
```

In `projectMeetingMinutesWorkflow.test.mjs`, assert API and type source contain `stage`, `step_count`, `error_code`, `tool_trace`, `meeting_info_evidence`, `summary_evidence`, and `open_questions`.

- [ ] **Step 2: Run Node tests and verify they fail against the old branch**

```powershell
node --test frontend/tests/newMeetingMultiSource.test.mjs frontend/tests/projectMeetingMinutesWorkflow.test.mjs
```

Expected: assertions fail because standard-minutes prefill remains and Agent audit fields are absent.

- [ ] **Step 3: Update API types**

Change text extraction to:

```typescript
export function extractMeetingDocumentText(
  projectId: number,
  file: File,
): Promise<{ filename: string; text: string }> {
  const fd = new FormData()
  fd.append('file', file, file.name)
  return apiUpload<{ filename: string; text: string }>(`/api/meetings/extract-document-text?project_id=${projectId}`, fd)
}
```

Add:

```typescript
export type AgentEvidence = {
  quote: string
  char_start: number
  char_end: number
  validation?: { state: 'ready' | 'blocked'; errors: string[] }
}

export type ProjectMeetingFact = {
  content: string
  evidence: AgentEvidence[]
  confidence: number
  needs_confirmation: boolean
  validation?: { state: 'ready' | 'blocked'; errors: string[] }
}
```

Extend `ProjectMeetingRun` with the audit fields from Task 6 and extend `result` with `meeting_info_evidence`, `summary_evidence`, `agenda_items`, `completed_items`, `next_stage_work`, `decisions`, and typed `open_questions`.

Extend `ProjectMeetingScheduleChange` with `parent_subtask_id: number | null`; keep `parent_workstream_id` as the enclosing workstream ID. Map `keyTaskId` in the review workspace from `parent_subtask_id`.

Keep the `StandardMeetingMinutes` type only if repository search shows historical editing still imports it; otherwise remove the unused export. Keep the `source_mode` union because historical records may still contain `standard_minutes`.

- [ ] **Step 4: Remove standard rule-prefill from document selection**

Reduce `handleDocumentSelected` to file/text transport:

```typescript
async function handleDocumentSelected(file: File) {
  setDocumentUploading(true)
  setError('')
  try {
    const result = await extractMeetingDocumentText(projectId, file)
    setDocumentFile(file)
    setDocumentName(result.filename)
    setDocumentText(result.text)
    setForm((previous) => ({
      ...previous,
      transcript_text: `【会议文档】\n${result.text}`,
      source_mode: 'ai_analysis',
    }))
  } catch (cause: unknown) {
    setError(`文档读取失败：${cause instanceof Error ? cause.message : String(cause)}`)
  } finally {
    setDocumentUploading(false)
  }
}
```

Do not assign title, date, location, people, agenda, summary, or action fields in this function.

- [ ] **Step 5: Handle Agent run outcome explicitly**

Add bounded polling so the UI can display persisted Agent stages while the background run proceeds:

```typescript
const AGENT_MAX_POLLS = 120
const AGENT_POLL_MS = 1000
const AGENT_STAGE_LABELS: Record<string, string> = {
  queued: '会议纪要 Agent 已排队',
  reading_document: '正在读取会议文档',
  understanding: '正在理解会议内容',
  querying_project: '正在查询项目上下文',
  matching_plan: '正在匹配工作计划',
  validating: '正在校验事实和变更建议',
  pending_review: '待审核草稿已生成',
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

async function waitForProjectMeetingAgent(initial: ProjectMeetingRun): Promise<ProjectMeetingRun> {
  let current = initial
  for (let index = 0; index < AGENT_MAX_POLLS; index += 1) {
    setStatusMsg(AGENT_STAGE_LABELS[current.stage] || '会议纪要 Agent 正在分析')
    if (current.status === 'completed' || current.status === 'failed') return current
    await delay(AGENT_POLL_MS)
    current = await fetchProjectMeetingDocumentRun(current.id)
  }
  throw new Error('会议纪要 Agent 分析超时，请稍后查看运行记录')
}
```

After `createProjectMeetingDocumentRun`, wait for the terminal run and handle it explicitly:

```typescript
const queuedRun = await createProjectMeetingDocumentRun(projectId, documentFile, form.meeting_type)
const run = await waitForProjectMeetingAgent(queuedRun)
if (run.status === 'failed') {
  setError(`会议纪要 Agent 分析失败：${run.error_message || run.error_code || '请稍后重试'}`)
  setStep('input')
  return
}
if (!run.meeting) {
  setError('会议纪要 Agent 未返回待审核会议记录')
  setStep('input')
  return
}
onCreated(run.meeting)
```

Change visible labels from “AI 生成草稿/文档分析结果” to “Agent 生成草稿/Agent 分析结果” only in this project meeting flow. Do not rename unrelated AI functions.

- [ ] **Step 6: Run frontend tests and TypeScript build**

```powershell
node --test frontend/tests/newMeetingMultiSource.test.mjs frontend/tests/projectMeetingMinutesWorkflow.test.mjs
Set-Location frontend
npm run build
```

Expected: Node tests pass and Vite production build succeeds.

- [ ] **Step 7: Commit only Task 7 files**

```powershell
git add frontend/src/api/meetings.ts frontend/src/features/meeting/NewMeetingModal.tsx frontend/tests/newMeetingMultiSource.test.mjs frontend/tests/projectMeetingMinutesWorkflow.test.mjs
git commit -m "feat: use meeting agent in creation flow"
```

---

### Task 8: Show Agent evidence and unresolved questions in owner review

**Files:**

- Modify: `frontend/src/features/meeting/ProjectMeetingReviewWorkspace.tsx`
- Modify: `frontend/src/pages/MeetingPage.tsx:206-279`
- Modify: `frontend/src/api/meetings.ts:411-452`
- Modify: `frontend/tests/projectMeetingMinutesWorkflow.test.mjs`

- [ ] **Step 1: Add failing review-UI assertions**

Assert the review workspace exposes Agent provenance and evidence:

```javascript
assert.match(workspace, /Agent 分析结果/)
assert.match(workspace, /原文证据/)
assert.match(workspace, /待确认事项/)
assert.match(workspace, /needs_confirmation/)
assert.match(workspace, /validationState === 'blocked'/)
assert.match(workspace, /onSaveDraft/)
assert.match(workspace, /保存负责人修改/)
assert.match(page, /openQuestions/)
assert.match(page, /meetingInfoEvidence/)
assert.match(page, /summaryEvidence/)
assert.match(page, /updateMeeting/)
```

- [ ] **Step 2: Run the UI test and verify failure**

```powershell
node --test frontend/tests/projectMeetingMinutesWorkflow.test.mjs
```

Expected: missing Agent evidence/open-question mappings.

- [ ] **Step 3: Extend review props**

Add to `ProjectMeetingReviewWorkspaceProps`:

```typescript
facts: ProjectMeetingFact[]
openQuestions: ProjectMeetingFact[]
meetingInfoEvidence: Record<string, AgentEvidence[]>
summaryEvidence: AgentEvidence[]
onSaveDraft: (draft: {
  title: string
  meeting_date: string
  meeting_type: string
  location: string
  host: string
  participants: string
  organizer: string
  copied_to: string
  summary: string
}) => void | Promise<void>
```

Render:

- an “Agent 分析结果” badge;
- a compact evidence block under each fact;
- a “待确认事项” section that never appears as approved fact;
- field-level evidence indicators for nonempty meeting-info fields;
- a summary evidence block under the Agent summary;
- blocked schedule changes with disabled checkbox, existing validation errors, and original evidence.

Extend `ProjectMeetingDraft` with `meeting_type`, `location`, `organizer`, and `copied_to`. Add owner-editable controls for all meeting-info fields and summary. Initialize local draft state from `meetingDraft`, synchronize it in `useEffect` when the selected meeting changes, and call `onSaveDraft` from a “保存负责人修改” button. Disable editing and saving for non-owners or while busy.

The saved human values replace the current editable projection but do not alter `meetingInfoEvidence`; show a “负责人已修改” origin label where the current value differs from the Agent value. The existing meeting revision service records the human diff, so do not rewrite Agent evidence as if it came from Word.

Do not expose raw prompts, full tool observations, model credentials, or provider exception text.

- [ ] **Step 4: Map run result in `MeetingPage.tsx`**

Read collections defensively:

```typescript
const facts = Array.isArray(projectMeetingReview.result.facts)
  ? projectMeetingReview.result.facts
  : []
const openQuestions = Array.isArray(projectMeetingReview.result.open_questions)
  ? projectMeetingReview.result.open_questions
  : []
const meetingInfoEvidence = projectMeetingReview.result.meeting_info_evidence ?? {}
const summaryEvidence = projectMeetingReview.result.summary_evidence ?? []
```

Pass these into `ProjectMeetingReviewWorkspace`. Import and use the existing `updateMeeting` API for `onSaveDraft`; construct its required payload from the current `MeetingItem`, replace only the editable fields, keep `source_mode="ai_analysis"`, and refresh `projectMeetingReview.meeting` with the returned row. Preserve existing owner permission checks and selected-proposal approval behavior.

- [ ] **Step 5: Run UI tests and build**

```powershell
node --test frontend/tests/projectMeetingMinutesWorkflow.test.mjs frontend/tests/meetingDetailWorkspace.test.mjs frontend/tests/meetingDraftReviewStructure.test.mjs
Set-Location frontend
npm run build
```

Expected: all tests and build pass.

- [ ] **Step 6: Commit only Task 8 files**

```powershell
git add frontend/src/api/meetings.ts frontend/src/features/meeting/ProjectMeetingReviewWorkspace.tsx frontend/src/pages/MeetingPage.tsx frontend/tests/projectMeetingMinutesWorkflow.test.mjs
git commit -m "feat: review meeting agent evidence"
```

---

### Task 9: End-to-end regression, real-document acceptance, and cleanup

**Files:**

- Modify: `bowei_ai_dashboard/tests/test_project_meeting_agent_api.py`
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_minutes_service.py`
- Modify: `frontend/tests/projectMeetingMinutesWorkflow.test.mjs`

- [ ] **Step 1: Add a portable first-meeting DOCX fixture**

Construct the fixture with `python-docx`; include:

- title `博维管理咨询 AI升级与项目管理周会 会议纪要`;
- date `2026-07-27`;
- location `线下会议室+腾讯会议（线上）`;
- type `AI升级与项目管理专题（第一次会议）`;
- host `杨宇帆`;
- participants `刘万超、邹奇敏、温会林、郭熠彬、许明良、吴肖、袁金玉、杨宇帆`;
- organizer `吴肖`;
- copied-to `AI升级计划项目组成员`;
- current completed/next-step rows;
- no prior-meeting table.

The fake Agent sequence must first call `search_plan_nodes`, then return field values and exact character offsets calculated from the extracted document text. Assert all basic fields, first-meeting behavior, one ready proposal, and one blocked unmatched proposal.

- [ ] **Step 2: Add a no-rule-fallback regression**

Use `monkeypatch` to make any accidental `parse_standard_meeting_minutes` call raise `AssertionError`. Upload the fixture and assert Agent success. Then make the Agent fail and assert no meeting is created.

- [ ] **Step 3: Audit parser references and confirm historical isolation**

Run:

```powershell
rg -n "parse_standard_meeting_minutes|standard_minutes" bowei_ai_dashboard frontend --glob '!*.db' --glob '!data/**'
```

Expected: no new-upload endpoint or frontend creation branch imports or calls the parser. Keep `standard_meeting_minutes.py`, its dedicated tests, stored historical rows, and `source_mode='standard_minutes'` compatibility unchanged; they are legacy compatibility code and are not an allowed Agent input or fallback.

- [ ] **Step 4: Run complete backend meeting suites**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent_contracts.py tests/test_project_meeting_agent_tools.py tests/test_project_meeting_agent.py tests/test_project_meeting_agent_models.py tests/test_project_meeting_agent_processing.py tests/test_project_meeting_agent_api.py tests/test_project_meeting_minutes_service.py tests/test_meeting_change_set_service.py tests/test_meeting_change_set_writeback.py tests/test_meeting_draft_review.py tests/test_meeting_revision_api.py tests/test_meeting_revision_service.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Run full backend and frontend verification**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest -q
Set-Location ..\frontend
npm run build
$testFiles = Get-ChildItem tests -Filter '*.test.mjs' | ForEach-Object FullName
node --test $testFiles
```

Expected: full pytest suite passes, TypeScript/Vite build succeeds, and all Node tests pass.

- [ ] **Step 6: Perform local browser acceptance with the supplied document**

Start the existing backend/frontend using the repository's configured commands. In the signed-in local app:

1. choose project `AI升级计划`;
2. upload `C:\Users\25861\Desktop\AI升级项目周会-会议纪要-20260727.docx`;
3. verify the UI shows Agent analysis, not standard-rule parsing;
4. verify all eight basic fields are populated;
5. verify project context and execution-schedule suggestions are visible;
6. verify blocked suggestions cannot be selected;
7. verify returning without a reason is rejected;
8. verify approving selected suggestions updates only those schedules;
9. verify the approved DOCX downloads successfully.

Use a disposable test project or database backup for the approval/writeback check. Do not execute writeback against production data.

- [ ] **Step 7: Commit regression and cleanup files**

```powershell
git add bowei_ai_dashboard/tests/test_project_meeting_agent_api.py bowei_ai_dashboard/tests/test_project_meeting_minutes_service.py frontend/tests/projectMeetingMinutesWorkflow.test.mjs
git diff --cached --name-only
git commit -m "test: verify project meeting agent takeover"
```

Confirm the staged file list contains no unrelated pre-existing work and does not contain either standard-parser file.

---

## Final completion checks

- [ ] New project Word uploads do not invoke or consume standard-minutes business extraction.
- [ ] Agent uses only the six approved read-only tools and cannot cross the selected project boundary.
- [ ] Agent stops after six steps, rejects repeated calls, and repairs malformed output at most once.
- [ ] Every nonempty meeting-info field, fact, and task update has field/item-level Word evidence.
- [ ] Invalid evidence or target IDs remain blocked and cannot be approved for writeback.
- [ ] First meetings work with empty history.
- [ ] Agent failure preserves source/run audit and creates no fabricated meeting draft.
- [ ] Project owner remains the only approver; return reason stays mandatory.
- [ ] Approved writeback remains atomic and only applies selected proposals.
- [ ] Kickoff, work-report, ASR, and historical `standard_minutes` behavior remain compatible.
- [ ] Full backend tests, frontend build, Node tests, and real-document browser acceptance pass.
