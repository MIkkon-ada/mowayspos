# Meeting Change Set Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make one meeting-analysis Agent produce a reviewable, evidence-backed change set that can safely create or update workstreams and subtasks only after an authorized user selects and confirms the items.

**Architecture:** Add a meeting-specific, persistent Agent run and proposal audit model rather than reusing the kickoff models. `POST /api/meetings/analyze` will freeze a project-plan snapshot, persist the Agent result, and return both the ordinary meeting draft and proposals. Saving the meeting attaches that draft; a separate, transactional execution endpoint revalidates selected proposals against the live plan and records the resulting target IDs. The frontend replaces the second `generate-task-cards` LLM pass with one proposal-review modal after the meeting is saved.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic v2, PostgreSQL/SQLite test fixtures, React, TypeScript, Vite, Node test scripts.

---

## File Structure

- Create: `bowei_ai_dashboard/app/services/meeting_change_set.py` - freeze plan snapshots, normalize Agent output, validate proposals, and apply selected proposals.
- Create: `bowei_ai_dashboard/migrations/versions/<revision>_add_meeting_change_set_audit.py` - additive persistent run/proposal/audit schema.
- Create: `bowei_ai_dashboard/tests/test_meeting_change_set_service.py` - pure validation and snapshot regression tests.
- Create: `bowei_ai_dashboard/tests/test_meeting_change_set_writeback.py` - API-level persistence, permission, stale-state, and atomic execution tests.
- Create: `frontend/src/features/meeting/MeetingChangeSetReviewModal.tsx` - review, edit, select, and execute one saved meeting's proposals.
- Create: `frontend/tests/meetingChangeSetReviewStructure.test.mjs` - static frontend contract regression test.
- Modify: `bowei_ai_dashboard/app/models.py` - SQLAlchemy models for a draft change set and its durable proposal/audit rows.
- Modify: `bowei_ai_dashboard/app/schemas.py` - request/response schemas for attached analysis runs, proposal edits, and explicit execution selection.
- Modify: `bowei_ai_dashboard/app/routers/meetings.py` - unified analysis, attach-on-save, read/edit/execute endpoints, and audit logging.
- Modify: `bowei_ai_dashboard/app/services/llm.py` (or the existing meeting prompt module used by `meetings.py`) - typed JSON prompt contract for the meeting record plus `change_set`.
- Modify: `bowei_ai_dashboard/app/crud.py` - serialization only if `crud.to_dict()` does not already return relationships/JSON fields needed by the new endpoints.
- Modify: `frontend/src/api/meetings.ts` - TypeScript types and API calls for analysis runs/proposals; remove use of `generateTaskCards` from the active path.
- Modify: `frontend/src/features/meeting/NewMeetingModal.tsx` - retain the returned `analysis_id`, attach it while saving, and open the new review modal only after a meeting exists.
- Modify: `frontend/src/features/meeting/PushToTasksModal.tsx` - delete after all imports and tests have moved; do not leave the second LLM workflow reachable.

## API And Persistence Contract

Use these names consistently in all tasks:

```python
# models.py
class MeetingChangeSet(Base):
    __tablename__ = "meeting_change_sets"
    id: Mapped[int]
    project_id: Mapped[int]
    meeting_id: Mapped[int | None]       # null until the user saves the meeting
    created_by_person_id: Mapped[int | None]
    transcript_hash: Mapped[str]
    snapshot_json: Mapped[str]
    result_json: Mapped[str]
    status: Mapped[str]                  # draft | attached | executed

class MeetingChangeProposal(Base):
    __tablename__ = "meeting_change_proposals"
    id: Mapped[int]
    change_set_id: Mapped[int]
    action: Mapped[str]                  # create_workstream | update_workstream | create_subtask | update_subtask
    target_type: Mapped[str]             # workstream | subtask
    target_id: Mapped[int | None]
    parent_workstream_id: Mapped[int | None]
    before_json: Mapped[str]
    proposed_json: Mapped[str]
    evidence_json: Mapped[str]
    reason: Mapped[str]
    confidence: Mapped[float]
    validation_json: Mapped[str]
    execution_status: Mapped[str]        # pending | executed
    executed_by_person_id: Mapped[int | None]
    executed_at: Mapped[datetime | None]
    result_target_id: Mapped[int | None]
```

```text
POST /api/meetings/analyze
  -> ordinary meeting fields + analysis_id + change_set.proposals

POST /api/meetings
  payload additionally includes analysis_id
  -> creates Meeting, attaches the immutable MeetingChangeSet; does not change Task/SubTask

GET   /api/meetings/{meeting_id}/change-set
PATCH /api/meetings/{meeting_id}/change-set/proposals/{proposal_id}
POST  /api/meetings/{meeting_id}/change-set/execute  {"proposal_ids": [12, 13]}
```

`PATCH` accepts editable `proposed`, `evidence`, and `reason`, runs the same validation used for Agent output, and never changes the plan. `execute` accepts only explicit IDs: an empty array makes no changes; blocked proposals cannot be selected; all selected proposals are revalidated before the database writes begin. A stale/deleted target or a rejected authorization check returns HTTP 409/403 and commits none of the selected proposal writes.

### Task 1: Add the additive persistence models and migration

**Files:**
- Modify: `bowei_ai_dashboard/app/models.py` after `KickoffChangeProposal`
- Create: `bowei_ai_dashboard/migrations/versions/<revision>_add_meeting_change_set_audit.py`
- Test: `bowei_ai_dashboard/tests/test_meeting_change_set_writeback.py`

- [ ] **Step 1: Write the migration-contract test before adding models**

```python
def test_meeting_change_set_tables_are_available(db_session):
    inspector = sa.inspect(db_session.bind)
    assert {"meeting_change_sets", "meeting_change_proposals"} <= set(inspector.get_table_names())

    proposal_columns = {c["name"] for c in inspector.get_columns("meeting_change_proposals")}
    assert {
        "change_set_id", "action", "target_type", "before_json", "proposed_json",
        "evidence_json", "reason", "validation_json", "execution_status",
        "result_target_id", "executed_at",
    } <= proposal_columns
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd bowei_ai_dashboard && pytest tests/test_meeting_change_set_writeback.py::test_meeting_change_set_tables_are_available -q`

Expected: FAIL because the two tables do not exist.

- [ ] **Step 3: Add the SQLAlchemy models and an additive Alembic revision**

Add the two models shown in the API contract. Model all JSON fields as `Text` so SQLite fixtures and PostgreSQL use the same serialization path. Define foreign keys from `meeting_change_sets.project_id` to `projects.id`, `meeting_id` to `meetings.id`, and `meeting_change_proposals.change_set_id` to `meeting_change_sets.id`. Add indexes for `(project_id, status)`, `meeting_id`, and `(change_set_id, execution_status)`.

The migration must create only these tables and indexes. Its downgrade must drop only these indexes/tables in reverse order; it must not alter `tasks`, `subtasks`, `projects`, or the PostgreSQL volume.

```python
def upgrade() -> None:
    op.create_table("meeting_change_sets", ...)
    op.create_index("ix_meeting_change_sets_project_status", "meeting_change_sets", ["project_id", "status"])
    op.create_table("meeting_change_proposals", ...)
    op.create_index("ix_meeting_change_proposals_set_execution", "meeting_change_proposals", ["change_set_id", "execution_status"])
```

- [ ] **Step 4: Run the migration-contract test and migration head check**

Run: `cd bowei_ai_dashboard && pytest tests/test_meeting_change_set_writeback.py::test_meeting_change_set_tables_are_available -q && alembic upgrade head && alembic current`

Expected: PASS; `alembic current` reports the new revision as `(head)`.

- [ ] **Step 5: Commit the schema slice**

```bash
git add bowei_ai_dashboard/app/models.py bowei_ai_dashboard/migrations/versions/<revision>_add_meeting_change_set_audit.py bowei_ai_dashboard/tests/test_meeting_change_set_writeback.py
git commit -m "feat: add meeting change set audit schema"
```

### Task 2: Build frozen snapshots and deterministic proposal validation

**Files:**
- Create: `bowei_ai_dashboard/app/services/meeting_change_set.py`
- Test: `bowei_ai_dashboard/tests/test_meeting_change_set_service.py`

- [ ] **Step 1: Write failing service tests for the four allowed actions and blocked cases**

```python
def test_validate_update_workstream_uses_frozen_before_value(db_session, seeded_project):
    snapshot = build_meeting_plan_snapshot(seeded_project.id, db_session)
    proposal = {
        "action": "update_workstream", "target": {"workstream_id": 1},
        "proposed": {"completion_standard": "approved target"},
        "evidence": ["Speaker 1: completion is measured by the approved target."],
        "reason": "The meeting explicitly revised the evaluation standard.", "confidence": 0.92,
    }
    normalized = validate_meeting_change_proposal(proposal, snapshot)
    assert normalized["before"]["completion_standard"] == "old target"
    assert normalized["validation"]["state"] == "ready"


def test_validate_blocks_ambiguous_or_unsupported_proposal(db_session, seeded_project):
    snapshot = build_meeting_plan_snapshot(seeded_project.id, db_session)
    blocked = validate_meeting_change_proposal({
        "action": "update_subtask", "target": {"subtask_id": 9999},
        "proposed": {"status": "进行中"}, "evidence": [], "reason": "", "confidence": 0.5,
    }, snapshot)
    assert blocked["validation"]["state"] == "blocked"
    assert "not present in snapshot" in " ".join(blocked["validation"]["errors"])
```

Also cover: a workstream creation without `key_task` is blocked; a subtask creation without `parent_workstream_id`/`title` is blocked; a proposal with evidence but no reason is blocked; unknown fields are removed and recorded as validation errors; a valid proposal that references a known target but an unknown assignee/owner is `needs_review`, not `ready`.

- [ ] **Step 2: Run the service tests to verify they fail**

Run: `cd bowei_ai_dashboard && pytest tests/test_meeting_change_set_service.py -q`

Expected: FAIL with `ModuleNotFoundError` or missing function errors.

- [ ] **Step 3: Implement the pure service boundary**

```python
ALLOWED_ACTIONS = {
    "create_workstream", "update_workstream", "create_subtask", "update_subtask",
}

def build_meeting_plan_snapshot(project_id: int, db: Session) -> dict[str, object]:
    # Query non-deleted Task rows and their non-deleted SubTask rows.
    # Return IDs plus only editable fields; never include inferred meeting facts.
    ...

def validate_meeting_change_proposal(raw: dict[str, object], snapshot: dict[str, object]) -> dict[str, object]:
    # Return the canonical action/target/before/proposed/evidence/reason/confidence/validation shape.
    # Fill before only from snapshot and set ready, needs_review, or blocked.
    ...
```

Use one explicit field allowlist per action:

```python
WORKSTREAM_FIELDS = {"key_task", "owner", "coordinator", "collaborators", "plan_time", "status", "key_achievement", "completion_standard"}
SUBTASK_FIELDS = {"title", "assignee", "plan_time", "completion_criteria", "status", "notes"}
```

Do not call the LLM or mutate the database in either function. Evidence must be a non-empty list of trimmed strings copied from the transcript; `before` must come from the frozen snapshot, never from the client or model.

- [ ] **Step 4: Run the service tests to verify they pass**

Run: `cd bowei_ai_dashboard && pytest tests/test_meeting_change_set_service.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the validator slice**

```bash
git add bowei_ai_dashboard/app/services/meeting_change_set.py bowei_ai_dashboard/tests/test_meeting_change_set_service.py
git commit -m "feat: validate meeting change proposals"
```

### Task 3: Make the single Agent response produce and persist a change-set draft

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/meetings.py:327-447`
- Modify: `bowei_ai_dashboard/app/services/llm.py` or the meeting prompt declarations used by `meetings.py`
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Modify: `bowei_ai_dashboard/app/services/meeting_change_set.py`
- Test: `bowei_ai_dashboard/tests/test_meeting_change_set_writeback.py`

- [ ] **Step 1: Write failing integration tests for unified analysis without plan writes**

```python
def test_meeting_analysis_returns_persisted_change_set_without_changing_plan(client, db_session, monkeypatch, owner_headers):
    before = snapshot_plan_rows(db_session, project_id=1)
    monkeypatch.setattr(meetings, "_do_analyze", lambda *_: {
        "title": "weekly review", "summary": "summary", "reports": [],
        "change_set": [{
            "action": "update_subtask", "target": {"subtask_id": 1},
            "proposed": {"status": "进行中"},
            "evidence": ["Speaker 1: task one is now in progress."],
            "reason": "The speaker explicitly reported the status.", "confidence": 0.9,
        }],
    })

    response = client.post("/api/meetings/analyze", json={"project_id": 1, "text": "Speaker 1: task one is now in progress.", "mode": "progress"}, headers=owner_headers)

    assert response.status_code == 200
    assert response.json()["analysis_id"] > 0
    assert response.json()["change_set"]["proposals"][0]["validation"]["state"] == "ready"
    assert snapshot_plan_rows(db_session, project_id=1) == before
```

Add a companion assertion that the frozen `snapshot_json`, original transcript hash, full raw result, and validated proposals are stored even when every proposal is blocked.

- [ ] **Step 2: Run the analysis test to verify it fails**

Run: `cd bowei_ai_dashboard && pytest tests/test_meeting_change_set_writeback.py::test_meeting_analysis_returns_persisted_change_set_without_changing_plan -q`

Expected: FAIL because `analysis_id` and persisted change sets do not exist.

- [ ] **Step 3: Extend the meeting prompt and `analyze_meeting` endpoint**

The meeting prompt must require valid JSON with the existing meeting keys and `change_set`. Include this behavioral contract directly in the prompt:

```text
For each change_set item, cite one or more exact transcript excerpts in evidence.
Use the provided snapshot only to identify IDs and compare fields; never infer a change from it.
Use only create_workstream, update_workstream, create_subtask, or update_subtask.
When a target is ambiguous, emit the item with an explanation rather than guessing an ID.
```

After `_do_analyze` returns, call `build_meeting_plan_snapshot`, normalize every raw item through `validate_meeting_change_proposal`, create a `MeetingChangeSet(status="draft")`, and add child `MeetingChangeProposal` rows. Return the existing analysis shape plus:

```python
return {
    **meeting_fields,
    "analysis_id": change_set.id,
    "change_set": serialize_change_set(change_set),
}
```

Create Pydantic response/request types in `schemas.py` for the canonical proposal shape. Do not add any client-supplied `before` or snapshot fields to a write schema.

- [ ] **Step 4: Run the focused integration and existing meeting draft tests**

Run: `cd bowei_ai_dashboard && pytest tests/test_meeting_change_set_writeback.py::test_meeting_analysis_returns_persisted_change_set_without_changing_plan tests/test_meeting_draft_review.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the unified analysis slice**

```bash
git add bowei_ai_dashboard/app/routers/meetings.py bowei_ai_dashboard/app/services/llm.py bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/app/services/meeting_change_set.py bowei_ai_dashboard/tests/test_meeting_change_set_writeback.py
git commit -m "feat: persist unified meeting analysis change sets"
```

### Task 4: Attach a draft to a saved meeting and expose it safely

**Files:**
- Modify: `bowei_ai_dashboard/app/schemas.py:374-389`
- Modify: `bowei_ai_dashboard/app/routers/meetings.py:269-324`
- Modify: `bowei_ai_dashboard/app/services/meeting_change_set.py`
- Test: `bowei_ai_dashboard/tests/test_meeting_change_set_writeback.py`

- [ ] **Step 1: Write failing tests for attach-on-save and controlled reads**

```python
def test_saving_meeting_attaches_own_draft_change_set(client, db_session, owner_headers):
    analysis_id = create_draft_change_set(db_session, project_id=1, username="owner")
    response = client.post("/api/meetings", json=meeting_payload(project_id=1, analysis_id=analysis_id), headers=owner_headers)
    assert response.status_code == 200

    detail = client.get(f"/api/meetings/{response.json()['id']}/change-set", headers=owner_headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "attached"


def test_cannot_attach_another_users_or_another_projects_change_set(client, db_session, member_headers):
    analysis_id = create_draft_change_set(db_session, project_id=2, username="owner")
    response = client.post("/api/meetings", json=meeting_payload(project_id=1, analysis_id=analysis_id), headers=member_headers)
    assert response.status_code == 409
```

- [ ] **Step 2: Run the attach tests to verify they fail**

Run: `cd bowei_ai_dashboard && pytest tests/test_meeting_change_set_writeback.py -k "attaches_own or another_users" -q`

Expected: FAIL because `analysis_id` is ignored and the read endpoint does not exist.

- [ ] **Step 3: Attach only the authenticated creator's matching draft**

Add `analysis_id: int | None = None` to `MeetingPayload`. In `create_meeting`, look up the draft before committing and reject it unless all conditions hold:

```python
change_set.project_id == payload.project_id
change_set.meeting_id is None
change_set.status == "draft"
change_set.created_by_person_id == current_account.person_id
```

Set `meeting_id`, change its status to `attached`, and log `meeting_change_set_attach` in the same database transaction as `meeting_create`. Add `GET /api/meetings/{meeting_id}/change-set`; it must use the existing meeting read permission check and return the persisted proposal records, not client copies.

- [ ] **Step 4: Run attach/read tests and the existing meeting API tests**

Run: `cd bowei_ai_dashboard && pytest tests/test_meeting_change_set_writeback.py -k "attaches_own or another_users" tests/test_meeting_draft_review.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the attach slice**

```bash
git add bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/app/routers/meetings.py bowei_ai_dashboard/app/services/meeting_change_set.py bowei_ai_dashboard/tests/test_meeting_change_set_writeback.py
git commit -m "feat: attach meeting change sets to saved meetings"
```

### Task 5: Add human edits and atomic authorized execution

**Files:**
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Modify: `bowei_ai_dashboard/app/routers/meetings.py`
- Modify: `bowei_ai_dashboard/app/services/meeting_change_set.py`
- Test: `bowei_ai_dashboard/tests/test_meeting_change_set_writeback.py`

- [ ] **Step 1: Write failing execution safety tests**

```python
def test_execution_requires_explicit_selection_and_preserves_unselected_rows(client, db_session, owner_headers):
    meeting, ready_id, other_id = attached_meeting_with_two_ready_proposals(db_session)
    response = client.post(f"/api/meetings/{meeting.id}/change-set/execute", json={"proposal_ids": [ready_id]}, headers=owner_headers)
    assert response.status_code == 200
    assert proposal(db_session, ready_id).execution_status == "executed"
    assert proposal(db_session, other_id).execution_status == "pending"


def test_execution_rejects_stale_selected_target_without_partial_write(client, db_session, owner_headers):
    meeting, update_id, create_id = attached_meeting_with_stale_update_and_create(db_session)
    mutate_target_after_snapshot(db_session, proposal_id=update_id)
    response = client.post(f"/api/meetings/{meeting.id}/change-set/execute", json={"proposal_ids": [update_id, create_id]}, headers=owner_headers)
    assert response.status_code == 409
    assert no_created_workstream_exists(db_session, proposal_id=create_id)
    assert proposal(db_session, update_id).execution_status == "pending"


def test_member_can_review_but_cannot_execute_structural_change(client, db_session, member_headers):
    meeting, proposal_id = attached_meeting_with_ready_proposal(db_session)
    response = client.post(f"/api/meetings/{meeting.id}/change-set/execute", json={"proposal_ids": [proposal_id]}, headers=member_headers)
    assert response.status_code == 403
```

Also test all four action types, rejected blocked IDs, PATCH changing `proposed` and evidence then revalidating, and an audit record with actor, timestamp, before/proposed/evidence/result target ID for each successfully selected row.

- [ ] **Step 2: Run the execution tests to verify they fail**

Run: `cd bowei_ai_dashboard && pytest tests/test_meeting_change_set_writeback.py -k "execution or member_can_review" -q`

Expected: FAIL because no execution endpoint exists.

- [ ] **Step 3: Implement one transactional execution service**

```python
def execute_meeting_change_set(
    *, meeting: models.Meeting, proposal_ids: list[int], actor: str, db: Session
) -> list[models.MeetingChangeProposal]:
    proposals = load_selected_pending_proposals(meeting.id, proposal_ids, db)
    require_structural_change_permission(actor, meeting.project_id, db)
    revalidate_all_selected_against_live_plan(proposals, db)  # raises before any write
    for proposal in proposals:
        target = apply_validated_proposal(proposal, meeting.project_id, db)
        proposal.result_target_id = target.id
        proposal.execution_status = "executed"
        proposal.executed_by_person_id = person_id_for_account(actor, db)
        proposal.executed_at = utcnow()
    return proposals
```

`apply_validated_proposal` must construct the same model fields used by `tasks.py:create_task` and `subtasks.py:create_subtask`, including owner/assignee IDs, normalized statuses, soft-delete checks, and `require_project_business_writable`. Do not issue HTTP requests to the application's own task routes. Reuse their underlying permission/normalization helpers where they are import-safe; otherwise move a small shared helper into `meeting_change_set.py` and cover it with tests.

The router endpoint must wrap the service in one transaction and emit one `crud.log` record per executed proposal (`meeting_change_execute`) whose `before` and `after` include proposal ID, evidence, and resulting target ID. Return serialized proposal results only after `db.commit()` succeeds.

- [ ] **Step 4: Run the execution safety suite**

Run: `cd bowei_ai_dashboard && pytest tests/test_meeting_change_set_writeback.py -k "execution or member_can_review" -q`

Expected: PASS; the stale test proves the create action was not committed.

- [ ] **Step 5: Commit the writeback slice**

```bash
git add bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/app/routers/meetings.py bowei_ai_dashboard/app/services/meeting_change_set.py bowei_ai_dashboard/tests/test_meeting_change_set_writeback.py
git commit -m "feat: execute reviewed meeting change sets"
```

### Task 6: Replace the frontend's second LLM task-card flow

**Files:**
- Create: `frontend/src/features/meeting/MeetingChangeSetReviewModal.tsx`
- Modify: `frontend/src/api/meetings.ts`
- Modify: `frontend/src/features/meeting/NewMeetingModal.tsx`
- Delete: `frontend/src/features/meeting/PushToTasksModal.tsx`
- Test: `frontend/tests/meetingChangeSetReviewStructure.test.mjs`

- [ ] **Step 1: Write the failing frontend contract test**

```javascript
assert.match(reviewSource, /checked=\{selectedIds\.has\(proposal\.id\)\}/)
assert.match(reviewSource, /const \[selectedIds, setSelectedIds\] = useState<Set<number>>\(new Set\(\)\)/)
assert.match(reviewSource, /proposal\.validation\.state === 'blocked'/)
assert.match(reviewSource, /evidence/)
assert.match(newMeetingSource, /analysis_id: analysisId/)
assert.doesNotMatch(newMeetingSource, /generateTaskCards|PushToTasksModal/)
```

- [ ] **Step 2: Run the frontend test to verify it fails**

Run: `node frontend/tests/meetingChangeSetReviewStructure.test.mjs`

Expected: FAIL because the review modal and `analysis_id` flow do not exist.

- [ ] **Step 3: Add typed API calls and the review modal**

Add these types and calls to `frontend/src/api/meetings.ts`:

```ts
export type MeetingChangeProposal = {
  id: number
  action: 'create_workstream' | 'update_workstream' | 'create_subtask' | 'update_subtask'
  target_type: 'workstream' | 'subtask'
  target_id: number | null
  parent_workstream_id: number | null
  before: Record<string, unknown>
  proposed: Record<string, unknown>
  evidence: string[]
  reason: string
  confidence: number
  validation: { state: 'ready' | 'needs_review' | 'blocked'; errors: string[] }
  execution_status: 'pending' | 'executed'
}

export function fetchMeetingChangeSet(meetingId: number) { return apiGet<MeetingChangeSet>(`/api/meetings/${meetingId}/change-set`) }
export function updateMeetingChangeProposal(meetingId: number, proposalId: number, payload: ProposalEditPayload) { return apiPatch<MeetingChangeProposal>(`/api/meetings/${meetingId}/change-set/proposals/${proposalId}`, payload) }
export function executeMeetingChangeSet(meetingId: number, proposalIds: number[]) { return apiPost<MeetingChangeSet>(`/api/meetings/${meetingId}/change-set/execute`, { proposal_ids: proposalIds }) }
```

`MeetingChangeSetReviewModal` must render ordinary diff rows grouped by workstream, showing action, target, each changed before/proposed field, evidence, reason, confidence, and server validation errors. Initialize `selectedIds` as an empty set. Render no checkbox for `blocked`; render unchecked checkboxes for `ready` and `needs_review`; keep the execute button disabled until at least one selected item remains. Open an explicit confirmation dialog before the execute call. On success, show each returned `execution_status` and call `onDone` so the meeting page refreshes.

In `NewMeetingModal`, store `analysis_id` when analysis returns. Include it only in the first `createMeeting` call; after that call returns a meeting ID, open `MeetingChangeSetReviewModal`. Do not show the modal for editing an existing meeting because no new analysis draft exists. Delete the old modal import, `showPushModal`, and the second LLM path.

- [ ] **Step 4: Run the frontend contract test and build**

Run: `node frontend/tests/meetingChangeSetReviewStructure.test.mjs && cd frontend && npm run build`

Expected: PASS; Vite completes without TypeScript errors.

- [ ] **Step 5: Commit the frontend workflow slice**

```bash
git add frontend/src/api/meetings.ts frontend/src/features/meeting/NewMeetingModal.tsx frontend/src/features/meeting/MeetingChangeSetReviewModal.tsx frontend/tests/meetingChangeSetReviewStructure.test.mjs
git rm frontend/src/features/meeting/PushToTasksModal.tsx
git commit -m "feat: review meeting changes before execution"
```

### Task 7: Verify the whole flow, prevent regression, and document release checks

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_meeting_draft_review.py`
- Modify: `README.md` or `docs/operations/production-release.md` if the project has an existing release checklist
- Test: `bowei_ai_dashboard/tests/test_meeting_change_set_service.py`
- Test: `bowei_ai_dashboard/tests/test_meeting_change_set_writeback.py`
- Test: `frontend/tests/meetingChangeSetReviewStructure.test.mjs`

- [ ] **Step 1: Add an end-to-end regression test for the exact safety boundary**

```python
def test_saved_meeting_requires_reviewed_selection_before_any_plan_write(client, db_session, owner_headers, monkeypatch):
    analysis = analyze_with_one_valid_create_subtask(client, monkeypatch, owner_headers)
    meeting = save_meeting_with_analysis(client, analysis["analysis_id"], owner_headers)
    assert count_subtasks(db_session) == 0

    detail = client.get(f"/api/meetings/{meeting['id']}/change-set", headers=owner_headers).json()
    proposal_id = detail["proposals"][0]["id"]
    client.post(f"/api/meetings/{meeting['id']}/change-set/execute", json={"proposal_ids": [proposal_id]}, headers=owner_headers)
    assert count_subtasks(db_session) == 1
```

- [ ] **Step 2: Run the regression test before final verification**

Run: `cd bowei_ai_dashboard && pytest tests/test_meeting_change_set_writeback.py::test_saved_meeting_requires_reviewed_selection_before_any_plan_write -q`

Expected: PASS; saving alone leaves the plan unchanged and executing the explicit ID creates exactly one subtask.

- [ ] **Step 3: Write the release note and operational safety checks**

Add a short release section that states:

```text
This release adds tables only. Deploy the backend migration with `alembic upgrade head`.
Do not run `docker compose down -v`, remove `/data/mowayspos/postgres`, or recreate the postgres service.
The persistent LLM file remains `/data/mowayspos/env/llm_configs.json` and WeCom values remain in `production.env`; neither is modified by this feature.
Verify after deployment: API health, Alembic head, one analysis that creates no Task/SubTask rows, then one explicitly selected proposal in a non-production project.
```

- [ ] **Step 4: Run all affected verification commands**

Run:

```bash
cd bowei_ai_dashboard
pytest tests/test_meeting_change_set_service.py tests/test_meeting_change_set_writeback.py tests/test_meeting_draft_review.py -q
alembic upgrade head
alembic current
cd ../frontend
node tests/meetingChangeSetReviewStructure.test.mjs
npm run build
```

Expected: every test passes, build succeeds, and Alembic prints the new revision as `(head)`.

- [ ] **Step 5: Commit the verification and release documentation**

```bash
git add bowei_ai_dashboard/tests/test_meeting_draft_review.py bowei_ai_dashboard/tests/test_meeting_change_set_service.py bowei_ai_dashboard/tests/test_meeting_change_set_writeback.py frontend/tests/meetingChangeSetReviewStructure.test.mjs README.md docs/operations/production-release.md
git commit -m "test: cover reviewed meeting change execution"
```

## Release Sequence After Implementation

1. Build and publish the tagged backend/frontend images in GitHub Actions; wait for success before touching CVM.
2. On CVM, capture the current image tag and database row-count snapshot before changing `MOWAYS_IMAGE_TAG`.
3. Pull only `backend` and `frontend`; do not pull/recreate `postgres`.
4. Run `alembic upgrade head` once, then start the two application services.
5. Check `/api/health`, `alembic current`, Web login/WeCom entry, and a read-only meeting analysis. Confirm the analysis does not change `tasks`/`subtasks` counts.
6. Keep the previous known-good tag for rollback. Rolling back application images does not restore a newer schema; the migration is additive and should remain compatible with the immediately previous application version.

## Self-Review

- Spec coverage: Tasks 1-2 cover additive persistence, immutable snapshots, action allowlists, and validation. Tasks 3-4 cover the single Agent result and save-without-plan-mutation behavior. Task 5 covers explicit selection, authorization, stale detection, atomic execution, and audit traceability. Task 6 removes the second LLM UI flow and provides the required review surface. Task 7 covers acceptance regression and deployment safety.
- Placeholder scan: no `TBD`, `TODO`, or unspecified validation steps appear; each implementation task names the required functions, fields, and test command.
- Type consistency: every API call uses `analysis_id`, `MeetingChangeSet`, `MeetingChangeProposal`, and `proposal_ids` as defined in the contract; the four action strings are identical throughout.
