# Project Meeting Agent Lineage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fact-to-change lineage, field-level value provenance, snapshot-safe matching, delta analysis, and conflict-safe human writeback to the existing project meeting Agent.

**Architecture:** Keep one bounded Agent, frozen project snapshots, read-only tools, `ProjectMeetingRun`, `MeetingChangeSet`, `MeetingChangeProposal`, and owner approval. Extend the Agent result with an additive analysis layer while retaining the existing meeting display fields. `ProjectMeetingRun.result_json` is the immutable AI original result; the review proposal may be changed only through the audited owner-edit endpoint. Persist the full normalized package in existing JSON columns and a proposal-level `lineage_json`; use `result_json`, `snapshot_json`, and lineage together to reject stale UPDATEs and duplicate/stale CREATEs before formal project data changes.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic 2, SQLAlchemy, Alembic, pytest, React 19, TypeScript 5, Vite.

---

## Scope and file map

- Modify `bowei_ai_dashboard/app/services/project_meeting_agent_contracts.py`: add typed analysis-layer contracts and field provenance while retaining presentation fields.
- Modify `bowei_ai_dashboard/app/services/project_meeting_agent.py`: require the four-stage JSON contract and focused fact-aware lookup calls.
- Modify `bowei_ai_dashboard/app/services/project_meeting_agent_tools.py`: return typed candidate sets and echo a focused `fact_id`; remain snapshot-only.
- Modify `bowei_ai_dashboard/app/services/project_meeting_minutes.py`: normalize and validate facts, matches, deltas, proposed changes, field provenance, and legacy display fields.
- Modify `bowei_ai_dashboard/app/services/project_meeting_agent_processing.py`: persist normalized analysis and proposal lineage without changing the existing draft/review flow.
- Modify `bowei_ai_dashboard/app/models.py`: add `MeetingChangeProposal.lineage_json` only.
- Create `bowei_ai_dashboard/migrations/versions/d5e6f7a8b9c0_add_meeting_proposal_lineage.py`: add the nullable-safe, defaulted lineage column.
- Modify `bowei_ai_dashboard/app/routers/meetings.py`: expose trace data, support owner-edited field provenance, and reject/mark UPDATE and CREATE conflicts before writeback.
- Modify `frontend/src/api/meetings.ts` and `frontend/src/features/meeting/ProjectMeetingReviewWorkspace.tsx`: type and display the additive trace without replacing existing minutes fields.
- Modify `bowei_ai_dashboard/tests/test_project_meeting_agent_contracts.py`, `test_project_meeting_agent.py`, `test_project_meeting_agent_tools.py`, `test_project_meeting_minutes_service.py`, `test_project_meeting_agent_processing.py`, and `test_meeting_change_set_writeback.py`; create `bowei_ai_dashboard/tests/test_project_meeting_agent_lineage.py` and `frontend/tests/projectMeetingLineageTrace.test.mjs`.

Do not edit kickoff, work-report, realtime transcription, project management, or legacy meeting-result readers beyond the listed meeting Agent interfaces. Stage only files named by each task because the worktree already contains unrelated edits.

### Task 1: Define the additive analysis contract

**Files:**

- Modify: `bowei_ai_dashboard/app/services/project_meeting_agent_contracts.py`
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_agent_contracts.py`

- [ ] **Step 1: Write failing contract tests**

Add fixtures for an existing `MeetingAgentFinal` payload plus the following analysis payload. Assert it is accepted only when IDs and references are complete, and assert missing field provenance or an inference-only value is rejected:

```python
def analysis_payload() -> dict:
    return {
        "meeting_facts": [{
            "fact_id": "F001", "fact_type": "action_item",
            "content": "完成客户清单第一版", "fields": {
                "status": {"value": "completed", "raw_text": "已经完成", "evidence": [evidence("已经完成")], "provenance": {"source_type": "meeting_fact", "source_fact_id": "F001", "usage": "new"}},
            },
            "meeting_evidence": [evidence("完成客户清单第一版")], "confidence": 0.9,
            "needs_confirmation": False,
        }],
        "project_matches": [{
            "match_id": "M001", "fact_id": "F001", "target_type": "execution_schedule",
            "target_id": 30, "workstream_id": 10, "key_task_id": 20,
            "confidence": 0.95, "reasons": ["标题一致"],
            "project_evidence": [{"source_object": "execution_schedule:30", "field": "title", "value": "客户清单第一版"}],
        }],
        "project_deltas": [{
            "delta_id": "D001", "source_fact_id": "F001", "source_match_id": "M001",
            "delta_type": "PROGRESS_UPDATE", "reasoning": "会议确认完成，基线仍为进行中",
        }],
        "proposed_changes": [{
            "change_id": "C001", "source_fact_id": "F001", "source_match_id": "M001", "source_delta_id": "D001",
            "action": "update_execution_schedule",
            "target": {"project_id": 1, "workstream_id": 10, "key_task_id": 20, "execution_schedule_id": 30},
            "before": {}, "proposed": {"status": "completed"},
            "field_sources": {"status": {"source_type": "meeting_fact", "source_fact_id": "F001", "usage": "new"}},
            "requires_confirmation": True,
        }],
        "unmatched_items": [], "needs_confirmation": [],
    }


def test_analysis_contract_rejects_duplicate_fact_ids(valid_final):
    payload = valid_final | analysis_payload()
    payload["meeting_facts"].append(payload["meeting_facts"][0])
    with pytest.raises(ValidationError, match="duplicate fact_id"):
        MeetingAgentFinal.model_validate(payload)


def test_analysis_contract_accepts_f001_and_rejects_all_zero_ids(valid_final):
    assert MeetingAgentFinal.model_validate(valid_final | analysis_payload()).meeting_facts[0].fact_id == "F001"
    payload = valid_final | analysis_payload()
    payload["meeting_facts"][0]["fact_id"] = "F000"
    with pytest.raises(ValidationError, match="fact_id"):
        MeetingAgentFinal.model_validate(payload)


def test_analysis_contract_rejects_inference_as_writable_source(valid_final):
    payload = valid_final | analysis_payload()
    payload["proposed_changes"][0]["field_sources"]["status"] = {
        "source_type": "inference", "usage": "new",
    }
    with pytest.raises(ValidationError):
        MeetingAgentFinal.model_validate(payload)
```

- [ ] **Step 2: Run the new tests and confirm RED**

Run:

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent_contracts.py -q
```

Expected: failures because `MeetingAgentFinal` has no `meeting_facts`/`proposed_changes` fields and no provenance model.

- [ ] **Step 3: Implement minimal typed models**

Add these constants and strict models. Keep the existing `MeetingInfo`, `MeetingFact` display model, evidence spans, and envelope names unchanged.

```python
DELTA_TYPES = frozenset({
    "NO_CHANGE", "PROGRESS_UPDATE", "STATUS_CHANGE", "NEW_EXECUTION_SCHEDULE",
    "SCHEDULE_CHANGE", "ASSIGNEE_CHANGE", "NEW_RISK", "RISK_UPDATE",
    "NEW_OUTPUT", "COMPLETION", "SCOPE_CHANGE", "UNMATCHED", "AMBIGUOUS",
})


class FieldProvenance(StrictModel):
    source_type: Literal["meeting_fact", "project_baseline", "human_edit"]
    source_fact_id: str | None = None
    source_object: str | None = None
    source_field: str | None = None
    usage: Literal["new", "inherit", "override"]

    @model_validator(mode="after")
    def validate_source(self):
        if self.source_type == "meeting_fact" and (not self.source_fact_id or self.usage != "new"):
            raise ValueError("meeting_fact source requires source_fact_id and new usage")
        if self.source_type == "project_baseline" and (not self.source_object or not self.source_field or self.usage != "inherit"):
            raise ValueError("project_baseline source requires source_object, source_field, and inherit usage")
        if self.source_type == "human_edit" and self.usage != "override":
            raise ValueError("human_edit source requires override usage")
        return self


class SourcedValue(StrictModel):
    value: Any
    raw_text: str = Field(min_length=1)
    evidence: list[EvidenceSpan] = Field(min_length=1)
    provenance: FieldProvenance


class ExtractedMeetingFact(StrictModel):
    fact_id: str = Field(pattern=r"^F(?!0+$)[0-9]{3,}$")
    fact_type: Literal["action_item", "decision", "completion", "progress", "risk", "output", "scope"]
    content: str = Field(min_length=1)
    fields: dict[str, SourcedValue] = Field(default_factory=dict)
    meeting_evidence: list[EvidenceSpan] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    needs_confirmation: bool = False
```

Add `ProjectMatch`, `ProjectDelta`, and `ProposedChange` models with `M`, `D`, and `C` patterns `^M(?!0+$)[0-9]{3,}$`, `^D(?!0+$)[0-9]{3,}$`, and `^C(?!0+$)[0-9]{3,}$`. Add empty-default analysis fields to `MeetingAgentFinal`, then validate unique IDs, fact/match/delta references, and that each `proposed` key has exactly one `FieldProvenance`. `ProposedChange.requires_confirmation` must be literal `True`; never permit `inference` as a field source. `SourcedValue` is used only where a field carries a value, such as `MeetingFact.fields`; it carries `raw_text` and field-level Word evidence so a normalized value such as `completed` can be proved by the original phrase `已经完成`. Provenance alone never carries business data.

- [ ] **Step 4: Verify GREEN and preserve existing contracts**

Run:

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent_contracts.py tests/test_project_meeting_agent.py -q
```

Expected: all current and new contract tests pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add bowei_ai_dashboard/app/services/project_meeting_agent_contracts.py bowei_ai_dashboard/tests/test_project_meeting_agent_contracts.py
git commit -m "feat: add meeting agent analysis contracts"
```

### Task 2: Require fact-aware matching in the Agent prompt and snapshot tools

**Files:**

- Modify: `bowei_ai_dashboard/app/services/project_meeting_agent.py`
- Modify: `bowei_ai_dashboard/app/services/project_meeting_agent_tools.py`
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_agent.py`
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_agent_tools.py`

- [ ] **Step 1: Write failing tool and prompt tests**

```python
def test_search_plan_nodes_returns_candidates_grouped_by_fact_id(snapshot):
    result = ProjectMeetingAgentTools(snapshot).execute(
        "search_plan_nodes", {"project_id": 1, "queries": [
            {"fact_id": "F001", "query": "minutes"},
            {"fact_id": "F002", "query": "draft"},
        ]}
    )
    assert [item["fact_id"] for item in result["results"]] == ["F001", "F002"]
    assert result["results"][0]["candidates"][0] == {
        "target_type": "key_task", "target_id": 20, "title": "Meeting minutes workflow",
        "workstream_id": 10, "workstream_name": "Delivery", "assignee": "", "status": "in_progress",
        "execution_schedules": [{"id": 30, "title": "Draft agent", "status": "pending"}],
    }


def test_agent_prompt_requires_four_layers_and_fact_aware_lookup(document_text):
    prompt = _base_prompt(1, document_text, "regular")
    assert '"meeting_facts"' in prompt
    assert '"project_matches"' in prompt
    assert '"project_deltas"' in prompt
    assert '"proposed_changes"' in prompt
    assert '"queries":[{"fact_id":"F001","query":""}]' in prompt
    assert "Project baseline is not current meeting evidence" in prompt
```

- [ ] **Step 2: Run RED tests**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent.py tests/test_project_meeting_agent_tools.py -q
```

Expected: failures because lookup results do not expose a batch keyed by `fact_id`/`target_type` and the prompt has no four-layer contract.

- [ ] **Step 3: Implement focused snapshot retrieval and prompt rules**

Make `search_plan_nodes` require a non-empty `queries` list of `{fact_id, query}` objects. Each `fact_id` must match `^F(?!0+$)[0-9]{3,}$`. Return `{"results": [{"fact_id": "F001", "candidates": [...]}, ...]}` in input order, with at most ten candidates per fact. A key-task candidate must include the parent workstream, assignee, status, and only child schedule summaries; it must not return the entire snapshot. One call may carry every extracted fact from the Word, so the six Agent turns never discard analysis merely because the meeting has more than six facts.

Update `_base_prompt()` to require this exact process:

```text
1. Extract Word-only meeting_facts with F IDs and exact meeting_evidence.
2. Call search_plan_nodes once with a batch of {fact_id, query} entries before creating matches.
3. Use project evidence only for matching/baseline; never present it as a current-meeting fact.
4. Create deltas as inference only. An inference cannot supply a proposed field value.
5. Create a proposed change only with complete F/M/D lineage, explicit field_sources, and requires_confirmation=true.
```

Retain the six-step agent limit and the existing read-only tool boundary.

- [ ] **Step 4: Run GREEN tests**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent.py tests/test_project_meeting_agent_tools.py -q
```

Expected: pass.

- [ ] **Step 5: Commit Task 2**

```powershell
git add bowei_ai_dashboard/app/services/project_meeting_agent.py bowei_ai_dashboard/app/services/project_meeting_agent_tools.py bowei_ai_dashboard/tests/test_project_meeting_agent.py bowei_ai_dashboard/tests/test_project_meeting_agent_tools.py
git commit -m "feat: add fact-aware project meeting matching"
```

### Task 3: Normalize and validate the analysis layer against the frozen snapshot

**Files:**

- Modify: `bowei_ai_dashboard/app/services/project_meeting_minutes.py`
- Create: `bowei_ai_dashboard/tests/test_project_meeting_agent_lineage.py`
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_minutes_service.py`

- [ ] **Step 1: Write failing normalization tests**

```python
def test_normalizer_keeps_snapshot_values_out_of_meeting_facts(snapshot, document_text, final):
    final = final.model_copy(update={"meeting_facts": [
        ExtractedMeetingFact(
            fact_id="F001", fact_type="progress", content="事项继续推进",
            fields={"assignee": SourcedValue(value="A", raw_text="事项继续推进", evidence=[span(document_text, "事项继续推进")], provenance=FieldProvenance(source_type="meeting_fact", source_fact_id="F001", usage="new"))},
            meeting_evidence=[span(document_text, "事项继续推进")], confidence=0.8,
        )
    ]})
    result = normalize_project_meeting_agent_result(final, document_text, snapshot)
    assert result["meeting_facts"][0]["validation"]["state"] == "blocked"
    assert "assignee" not in result["meeting_facts"][0]["fields"]


def test_normalizer_blocks_fact_field_when_its_own_word_evidence_does_not_support_it(snapshot, document_text, final):
    final = final_with_fact_field(
        field="assignee", value="张三", raw_text="已经完成",
        evidence=[span(document_text, "已经完成")],
    )
    result = normalize_project_meeting_agent_result(final, document_text, snapshot)
    assert result["meeting_facts"][0]["validation"]["state"] == "blocked"
    assert "assignee" not in result["meeting_facts"][0]["fields"]


def test_normalizer_allows_delta_inference_without_fake_delay_quote(snapshot, document_text, final):
    result = normalize_project_meeting_agent_result(final_with_overdue_progress_delta(), document_text, snapshot)
    assert result["project_deltas"][0]["delta_type"] == "SCHEDULE_CHANGE"
    assert result["project_deltas"][0]["validation"]["state"] == "ready"


def test_normalizer_blocks_change_when_target_is_outside_snapshot(snapshot, document_text, final):
    result = normalize_project_meeting_agent_result(final_with_target(schedule_id=999), document_text, snapshot)
    assert result["proposed_changes"][0]["validation"]["state"] == "blocked"
    assert "snapshot" in " ".join(result["proposed_changes"][0]["validation"]["errors"])
```

- [ ] **Step 2: Run RED tests**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent_lineage.py tests/test_project_meeting_minutes_service.py -q
```

Expected: failures because normalized results do not contain the four analysis collections.

- [ ] **Step 3: Implement validators**

Add pure helpers in `project_meeting_minutes.py`:

```python
def normalize_meeting_fact(fact: ExtractedMeetingFact, document_text: str) -> dict: ...
def normalize_project_match(match: ProjectMatch, facts: dict[str, dict], snapshot: dict) -> dict: ...
def normalize_project_delta(delta: ProjectDelta, facts: dict[str, dict], matches: dict[str, dict]) -> dict: ...
def normalize_proposed_change(change: ProposedChange, facts: dict[str, dict], matches: dict[str, dict], deltas: dict[str, dict], snapshot: dict) -> dict: ...
```

`normalize_meeting_fact` accepts only field values explicitly carried by the fact. It validates `SourcedValue.raw_text` and every field-level evidence span against the Word, then verifies that the value is a permitted deterministic normalization of the raw expression; it does not require normalized values such as `completed` to occur literally in the Word. A Fact-level quote cannot validate an unrelated hidden field. Do not call an LLM during validation. Implement an explicit status map such as `{"已完成": "completed", "完成": "completed", "已经完成": "completed", "进行中": "in_progress", "正在推进": "in_progress"}` and deterministic date parsing for `YYYY-MM-DD` and `YYYY年M月D日`; reject values outside those rules. `normalize_project_match` resolves the target from the frozen snapshot and verifies each `project_evidence` field/value against that target. `normalize_project_delta` accepts a valid fact plus match, or explicitly accepts `UNMATCHED`/`AMBIGUOUS` without a match; it stores reasoning without requiring a fabricated Word quote. `normalize_proposed_change` verifies F/M/D references, UPDATE target membership, CREATE parent membership, allowed execution-schedule fields, and complete field sources.

For `project_baseline` field provenance require an exact snapshot `source_object`/`source_field` value match and `usage="inherit"`; retain the proposed value separately and verify equality with the referenced baseline value. For AI-originated changes reject `human_edit`; that source is introduced only by the owner-edit endpoint in Task 5. Keep the existing `meeting_draft`, evidence, agenda, decisions, completed items, next-stage work, risks, and open questions output keys unchanged, then add the seven analysis keys beside them.

- [ ] **Step 4: Verify GREEN and legacy compatibility**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent_lineage.py tests/test_project_meeting_minutes_service.py -q
```

Expected: pass, including existing assertions for meeting draft and display facts.

- [ ] **Step 5: Commit Task 3**

```powershell
git add bowei_ai_dashboard/app/services/project_meeting_minutes.py bowei_ai_dashboard/tests/test_project_meeting_agent_lineage.py bowei_ai_dashboard/tests/test_project_meeting_minutes_service.py
git commit -m "feat: validate project meeting analysis lineage"
```

### Task 4: Persist proposal lineage without new analysis entities

**Files:**

- Modify: `bowei_ai_dashboard/app/models.py`
- Create: `bowei_ai_dashboard/migrations/versions/d5e6f7a8b9c0_add_meeting_proposal_lineage.py`
- Modify: `bowei_ai_dashboard/app/services/project_meeting_agent_processing.py`
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_agent_processing.py`

- [ ] **Step 1: Write failing persistence tests**

```python
def test_processing_persists_change_lineage_for_review(db, queued_run, normalized_result):
    process_project_meeting_agent_run(queued_run.id, session_factory=lambda: db)
    proposal = db.query(models.MeetingChangeProposal).one()
    lineage = json.loads(proposal.lineage_json)
    assert lineage["change_id"] == "C001"
    assert lineage["source_fact_id"] == "F001"
    assert lineage["source_match_id"] == "M001"
    assert lineage["source_delta_id"] == "D001"
    assert lineage["field_sources"]["status"]["source_type"] == "meeting_fact"


def test_existing_proposal_without_lineage_remains_readable(db, legacy_proposal):
    assert json.loads(legacy_proposal.lineage_json or "{}") == {}
```

- [ ] **Step 2: Run RED tests**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent_processing.py -q
```

Expected: `AttributeError` because `lineage_json` does not exist.

- [ ] **Step 3: Add model and migration**

Add to `MeetingChangeProposal`:

```python
lineage_json = Column(Text, nullable=False, default="{}", server_default="{}")
```

Migration upgrade and downgrade must use batch operations:

```python
def upgrade() -> None:
    with op.batch_alter_table("meeting_change_proposals") as batch_op:
        batch_op.add_column(sa.Column("lineage_json", sa.Text(), nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("meeting_change_proposals") as batch_op:
        batch_op.drop_column("lineage_json")
```

Set the new migration `down_revision` to the current meeting-agent migration revision `c4e5f6a7b8c9`.

- [ ] **Step 4: Persist the normalized change package**

Change `_create_review_draft()` to build proposal rows from normalized `proposed_changes`, while retaining `execution_schedule_changes` as a compatibility projection. Store this exact shape in `lineage_json`:

```python
{
    "change_id": change["change_id"],
    "schema_version": 1,
    "action": change["action"],
    "target": change["target"],
    "requires_confirmation": change["requires_confirmation"],
    "source_fact_id": change["source_fact_id"],
    "source_match_id": change.get("source_match_id"),
    "source_delta_id": change["source_delta_id"],
    "field_sources": change["field_sources"],
    "meeting_evidence": change["meeting_evidence"],
    "project_evidence": change.get("project_evidence", []),
    "delta": change["delta"],
    "baseline_state": "existing_target" if change["action"] == "update_execution_schedule" else "not_applicable_new_object",
    "before_baseline": (
        {field: change["before"].get(field) for field in change["proposed"]}
        if change["action"] == "update_execution_schedule" else {}
    ),
    "parent_baseline": change.get("parent_baseline", {}),
    "owner_edit_history": [],
}
```

Keep `before_json`, `proposed_json`, `evidence_json`, `reason`, and `validation_json` populated so legacy review and download code continues to work.

- [ ] **Step 5: Run migration and persistence tests**

```powershell
Set-Location bowei_ai_dashboard
alembic upgrade head
python -m pytest tests/test_project_meeting_agent_processing.py tests/test_project_meeting_agent_models.py -q
```

Expected: migration succeeds and tests pass.

- [ ] **Step 6: Commit Task 4**

```powershell
git add bowei_ai_dashboard/app/models.py bowei_ai_dashboard/migrations/versions/d5e6f7a8b9c0_add_meeting_proposal_lineage.py bowei_ai_dashboard/app/services/project_meeting_agent_processing.py bowei_ai_dashboard/tests/test_project_meeting_agent_processing.py
git commit -m "feat: persist project meeting proposal lineage"
```

### Task 5: Add field-aware review validation and conflict-safe writeback

**Files:**

- Modify: `bowei_ai_dashboard/app/routers/meetings.py`
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Modify: `bowei_ai_dashboard/tests/test_meeting_change_set_writeback.py`
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_agent_lineage.py`

- [ ] **Step 1: Write failing writeback tests**

```python
def test_update_conflict_marks_proposal_and_refuses_overwrite(client, owner, proposal, schedule):
    schedule.status = "completed"  # changed after analysis
    db.session.commit()
    response = client.post(review_url(proposal), json={"action": "approve", "proposal_ids": [proposal.id]}, headers=owner)
    assert response.status_code == 409
    db.session.refresh(proposal)
    assert proposal.execution_status == "conflict"
    assert "target_changed_after_analysis" in json.loads(proposal.validation_json)["errors"]


def test_update_allows_unrelated_live_field_change(client, owner, proposal, schedule):
    schedule.risk_dependency = "new unrelated note"
    db.session.commit()
    response = client.post(review_url(proposal), json={"action": "approve", "proposal_ids": [proposal.id]}, headers=owner)
    assert response.status_code == 200
    db.session.refresh(schedule)
    assert schedule.status == "completed"


def test_create_conflict_refuses_duplicate_child(client, owner, create_proposal, key_task):
    create_equivalent_schedule(key_task, title="梳理顾问场景")
    response = client.post(review_url(create_proposal), json={"action": "approve", "proposal_ids": [create_proposal.id]}, headers=owner)
    assert response.status_code == 409
    db.session.refresh(create_proposal)
    assert create_proposal.execution_status == "conflict"


def test_owner_edit_marks_only_edited_fields_as_human_edit(client, owner, proposal):
    response = client.patch(edit_url(proposal), json={"proposed": {"due_date": "2026-08-03"}}, headers=owner)
    assert response.status_code == 200
    assert response.json()["lineage"]["field_sources"]["due_date"] == {
        "source_type": "human_edit", "usage": "override"
    }
    assert response.json()["lineage"]["owner_edit_history"][-1]["field"] == "due_date"
    assert response.json()["lineage"]["owner_edit_history"][-1]["before"] == "2026-07-31"
    assert response.json()["lineage"]["owner_edit_history"][-1]["after"] == "2026-08-03"


def test_owner_edit_adds_snapshot_before_value_for_newly_touched_field(client, owner, proposal):
    response = client.patch(edit_url(proposal), json={"proposed": {"due_date": "2026-08-03"}}, headers=owner)
    assert response.status_code == 200
    assert response.json()["lineage"]["before_baseline"]["due_date"] == "2026-07-31"


def test_owner_edit_rejects_new_touched_field_without_frozen_baseline(client, owner, proposal):
    remove_snapshot_schedule_field(proposal, "due_date")
    response = client.patch(edit_url(proposal), json={"proposed": {"due_date": "2026-08-03"}}, headers=owner)
    assert response.status_code == 409
    assert "frozen baseline" in response.json()["detail"]


def test_create_owner_edit_allows_new_field_without_target_baseline(client, owner, create_proposal):
    response = client.patch(edit_url(create_proposal), json={"proposed": {"due_date": "2026-08-03"}}, headers=owner)
    assert response.status_code == 200
    lineage = response.json()["lineage"]
    assert lineage["baseline_state"] == "not_applicable_new_object"
    assert "due_date" not in lineage["before_baseline"]
    assert lineage["field_sources"]["due_date"] == {"source_type": "human_edit", "usage": "override"}


def test_owner_edit_can_differ_from_immutable_ai_result_only_with_audited_history(client, owner, proposal):
    response = client.patch(edit_url(proposal), json={"proposed": {"due_date": "2026-08-03"}}, headers=owner)
    assert response.status_code == 200
    approved = client.post(review_url(proposal), json={"action": "approve", "proposal_ids": [proposal.id]}, headers=owner)
    assert approved.status_code == 200
```

- [ ] **Step 2: Run RED tests**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_meeting_change_set_writeback.py tests/test_project_meeting_agent_lineage.py -q
```

Expected: the existing writeback path silently accepts these cases or has no owner-edit endpoint.

- [ ] **Step 3: Implement lineage revalidation and conflict marking**

Add a `ProjectMeetingProposalConflict` exception carrying `{proposal_id: reason}`. Before applying any selected proposal, load immutable `ProjectMeetingRun.result_json`, `ProjectMeetingRun.snapshot_json`, and mutable review `proposal.lineage_json`. Validate the three sources according to their separate authority: `result_json` proves the original F/M/D/C objects and AI proposed change; `snapshot_json` proves target, parent, project boundary, and baseline; `lineage_json` proves a supported lineage schema, field provenance, and owner edit history. For every non-human-edited field, the review proposal and lineage must equal the immutable AI result. For every `human_edit` field, a server-created `owner_edit_history` entry must record `field`, `before`, `after`, `editor_person_id`, and `edited_at`; its `after` value must equal the current review proposal and its `before` value must equal the pre-edit proposal value. Lineage JSON is never treated as self-proving.

Owner edit has action-specific baseline rules. For UPDATE, when the owner PATCH endpoint adds a newly touched field, it must read that field's value from the frozen target schedule snapshot and append it to `lineage_json.before_baseline` before saving the review proposal. Set `baseline_state="existing_target"`; missing baseline for any touched field is blocked. At writeback, compute `touched_fields = set(proposal.proposed_json)` and compare only those `before_baseline[field]` values with live `ExecutionSchedule` values, while also validating execution-schedule, key-task, workstream, and project identity. Changes to unrelated fields must not create a conflict. For CREATE, set `baseline_state="not_applicable_new_object"`: the new execution schedule has no target-field baseline, so an owner may add an allowed field such as `due_date` with `human_edit/override` without adding a null or synthetic target baseline. CREATE writeback instead verifies snapshot parent key-task identity, current parent active/status state against `parent_baseline`, project boundary, and absence of a non-deleted equivalent execution schedule with the same normalized title and plan type/month. On either conflict set:

```python
proposal.execution_status = "conflict"
proposal.validation_json = json.dumps({"state": "blocked", "errors": [reason]}, ensure_ascii=False)
```

Do this for all selected proposals before applying any formal write. Commit the conflict state and return HTTP 409; do not update/create a formal schedule in that request.

Add `ProjectMeetingProposalEditPayload` with `proposed: dict[str, Any]`. Add an owner-only PATCH route under the project-meeting review path. It may replace only allowed execution-schedule fields. Each edited field gets `{"source_type":"human_edit","usage":"override"}` in the field provenance portion of `lineage_json`; untouched fields retain their prior provenance. Append a server-owned `owner_edit_history` record with `field`, `before`, `after`, `editor_person_id`, and UTC timestamp. For a newly touched UPDATE field, copy `before_baseline[field]` from the frozen target snapshot; if the snapshot cannot supply that field, return 409 and do not save the edit. For a CREATE field, keep `baseline_state="not_applicable_new_object"` and do not attempt to read a nonexistent target snapshot. It must not invent or modify meeting facts, matches, or deltas.

- [ ] **Step 4: Run GREEN tests**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_meeting_change_set_writeback.py tests/test_project_meeting_agent_lineage.py -q
```

Expected: pass; update and create conflicts persist as `conflict`, no formal data is overwritten/duplicated, and owner edits preserve upstream lineage.

- [ ] **Step 5: Commit Task 5**

```powershell
git add bowei_ai_dashboard/app/routers/meetings.py bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/tests/test_meeting_change_set_writeback.py bowei_ai_dashboard/tests/test_project_meeting_agent_lineage.py
git commit -m "feat: protect project meeting writeback conflicts"
```

### Task 6: Expose a lightweight review trace without replacing meeting minutes

**Files:**

- Modify: `bowei_ai_dashboard/app/routers/meetings.py`
- Modify: `frontend/src/api/meetings.ts`
- Modify: `frontend/src/features/meeting/ProjectMeetingReviewWorkspace.tsx`
- Create: `frontend/tests/projectMeetingLineageTrace.test.mjs`

- [ ] **Step 1: Write failing API/type/UI structure test**

```javascript
import assert from 'node:assert/strict'
import fs from 'node:fs'

const api = fs.readFileSync('src/api/meetings.ts', 'utf8')
const view = fs.readFileSync('src/features/meeting/ProjectMeetingReviewWorkspace.tsx', 'utf8')

assert.match(api, /type ProjectMeetingProposalLineage/)
assert.match(api, /field_sources/)
assert.match(view, /会议事实/)
assert.match(view, /项目匹配/)
assert.match(view, /项目基线/)
assert.match(view, /AI 判断/)
assert.match(view, /建议修改/)
```

- [ ] **Step 2: Run RED test**

```powershell
Set-Location frontend
node tests/projectMeetingLineageTrace.test.mjs
```

Expected: assertions fail because lineage fields and labels are absent.

- [ ] **Step 3: Implement additive API and view data**

In `_project_meeting_payload()`, expose each proposal's decoded `lineage` object and decoded validation without exposing raw model prompts/responses. Add TypeScript types:

```ts
export type ProjectMeetingFieldSource = {
  source_type: 'meeting_fact' | 'project_baseline' | 'human_edit'
  source_fact_id?: string
  source_object?: string
  source_field?: string
  usage: 'new' | 'inherit' | 'override'
}

export type ProjectMeetingProposalLineage = {
  schema_version: 1
  change_id: string
  action: 'update_execution_schedule' | 'create_execution_schedule'
  target: { project_id: number; workstream_id: number; key_task_id: number; execution_schedule_id?: number }
  requires_confirmation: true
  source_fact_id: string
  source_match_id?: string
  source_delta_id: string
  field_sources: Record<string, ProjectMeetingFieldSource>
  meeting_evidence: ProjectMeetingEvidenceSpan[]
  project_evidence: Array<{ source_object: string; field: string; value: unknown }>
  delta: { delta_type: string; reasoning: string }
  baseline_state: 'existing_target' | 'not_applicable_new_object'
  before_baseline: Record<string, unknown>
  parent_baseline: Record<string, unknown>
  owner_edit_history: Array<{ field: string; before: unknown; after: unknown; editor_person_id: number; edited_at: string }>
}
```

Render an accessible `<details>` block under each proposal with headings `会议事实`, `项目匹配`, `项目基线`, `AI 判断`, and `建议修改`. Keep the existing minutes draft cards and selection/approve/return controls intact. Display `conflict` as non-selectable with its validation reason.

- [ ] **Step 4: Run GREEN UI checks**

```powershell
Set-Location frontend
node tests/projectMeetingLineageTrace.test.mjs
npm run test:unit
npm run build
```

Expected: all pass.

- [ ] **Step 5: Commit Task 6**

```powershell
git add bowei_ai_dashboard/app/routers/meetings.py frontend/src/api/meetings.ts frontend/src/features/meeting/ProjectMeetingReviewWorkspace.tsx frontend/tests/projectMeetingLineageTrace.test.mjs
git commit -m "feat: show project meeting proposal lineage"
```

### Task 7: Run the acceptance matrix and a real-document validation

**Files:**

- Modify: `bowei_ai_dashboard/tests/test_project_meeting_agent_lineage.py`
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_agent_processing.py`

- [ ] **Step 1: Write acceptance cases before implementation refinements**

Add four deterministic normalized-result fixtures:

```python
def test_high_confidence_fact_match_creates_review_only_schedule_proposal(): ...
def test_similar_nonidentical_candidate_becomes_ambiguous_confirmation_item(): ...
def test_baseline_assignee_can_match_but_cannot_become_meeting_fact(): ...
def test_overdue_baseline_plus_continuing_meeting_fact_creates_inference_delta_only(): ...
```

Each test must assert its expected F/M/D/C relationship, exact Word evidence only for the fact, snapshot evidence only for the match, `requires_confirmation is True` for C, and zero writes to `ExecutionSchedule` before owner review.

- [ ] **Step 2: Run the acceptance tests and verify RED/GREEN state**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent_lineage.py -q
```

Expected before any needed refinement: a failing assertion that identifies the remaining behavior gap; after the smallest correction, all four cases pass.

- [ ] **Step 3: Run all backend and frontend regression suites**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_meeting_agent_contracts.py tests/test_project_meeting_agent.py tests/test_project_meeting_agent_tools.py tests/test_project_meeting_minutes_service.py tests/test_project_meeting_agent_processing.py tests/test_project_meeting_agent_models.py tests/test_project_meeting_agent_lineage.py tests/test_meeting_change_set_writeback.py -q
Set-Location ..\frontend
node tests/projectMeetingLineageTrace.test.mjs
npm run test:unit
npm run build
```

Expected: all commands exit 0.

- [ ] **Step 4: Execute the actual local document smoke test**

With the local backend using the configured provider, upload `C:\Users\25861\Desktop\AI升级项目周会-会议纪要-20260727.docx` under the existing AI升级计划 project. Record only the run ID, stage, output IDs, validation states, and proposal count. Verify that the stored result contains analysis-layer keys; no schedule changes occur before owner approval; and any unmatched/ambiguous content remains non-writable.

- [ ] **Step 5: Commit Task 7**

```powershell
git add bowei_ai_dashboard/tests/test_project_meeting_agent_lineage.py bowei_ai_dashboard/tests/test_project_meeting_agent_processing.py
git commit -m "test: cover project meeting lineage acceptance"
```

## Plan self-review

- **Spec coverage:** Tasks 1-3 cover schema, deterministic field-level Word evidence normalization, prompt, snapshot tools, meeting facts, matches, deltas, provenance, and boundary validation. Task 4 persists lineage without new entities. Task 5 treats owner review edits as an audited lineage stage, applies existing-target baselines only to UPDATE, applies parent-only baselines to CREATE, and enforces both conflict controls. Task 6 adds the requested lightweight review trace. Task 7 covers the four required cases, regressions, and a real Word run.
- **No placeholders:** every task gives files, named functions/types, assertions, commands, expected outcomes, and commit scope.
- **Type consistency:** `FieldProvenance`, `SourcedValue`, `ExtractedMeetingFact`, `ProjectMatch`, `ProjectDelta`, `ProposedChange`, and the versioned `lineage_json` keys are the sole names used throughout the plan. UPDATE uses an execution-schedule target and touched-field baseline comparison; CREATE uses a snapshot key-task parent plus duplicate detection.
