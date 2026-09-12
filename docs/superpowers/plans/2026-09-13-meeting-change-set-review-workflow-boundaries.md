# Meeting Change-Set Review Workflow Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` in the current session task-by-task. Do not delegate to subagents for this repository.

**Goal:** Move regular meeting change-set read, proposal review, and execution orchestration into a service-owned transaction without changing HTTP contracts, authorization, audit, or entity-write semantics.

**Architecture:** Create `meeting_change_set_review_workflow.py` as the application layer around the existing `meeting_change_set.py` domain service. The new service owns meeting/change-set lookup, response payloads, workflow permissions, edit dispatch, audit records, and commits. `meetings.py` remains an HTTP adapter and keeps unrelated analysis, project-document review, and meeting lifecycle code.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Pydantic 2, pytest.

---

## File structure

- Create: `bowei_ai_dashboard/app/services/meeting_change_set_review_workflow.py`
- Modify: `bowei_ai_dashboard/app/routers/meetings.py:49-56, 519-580, 825, 1313, 1633-1769`
- Create: `bowei_ai_dashboard/tests/test_meeting_change_set_review_workflow_boundaries.py`
- Reuse: `bowei_ai_dashboard/tests/test_meeting_change_set_writeback.py`
- Reuse: `bowei_ai_dashboard/tests/test_project_meeting_review_writeback.py`
- Modify: `docs/superpowers/plans/2026-09-13-meeting-change-set-review-workflow-boundaries.md`

### Task 1: Fix the direct application-service boundary with tests

**Files:**

- Create: `bowei_ai_dashboard/tests/test_meeting_change_set_review_workflow_boundaries.py`

- [x] **Step 1: Write a failing direct service test for reads and ordinary edits.**

Use an in-memory SQLite `Session` (`StaticPool`) and seed one owner account, active project, member role, draft meeting, change set, and `update_subtask` proposal. Import the proposed workflow module, then check that it returns the existing payload contract and uses the ordinary editor for proposals without lineage:

```python
result = workflow.get_meeting_change_set(
    row_id=meeting.id, current_user="owner", db=db,
)
assert result["id"] == change_set.id
assert result["proposals"][0]["target"] == {
    "project_id": project.id,
    "subtask_id": proposal.target_id,
    "parent_workstream_id": proposal.parent_workstream_id,
}

patched = workflow.patch_meeting_change_proposal(
    row_id=meeting.id,
    proposal_id=proposal.id,
    payload=schemas.MeetingChangeProposalPatch(
        proposed={"notes": "Human reviewed notes"},
        evidence=["Meeting evidence."],
        reason="Human reviewed the exact note.",
    ),
    current_user="owner",
    db=db,
)
assert patched["proposed"] == {"notes": "Human reviewed notes"}
assert patched["validation"]["state"] == "ready"
```

The seed must set `meeting.transcript_text = "Meeting evidence."`, proposal `execution_status = "pending"`, and a valid frozen `snapshot_json` so ordinary revalidation can succeed.

- [x] **Step 2: Write direct service tests for path ownership, execution authorization, and execution audit.**

Add one proposal belonging to a second change set and a project member account. Assert a cross-meeting proposal produces `404`; a non-owner cannot execute (`403`); preserve the existing ordinary-proposal edit behavior (the stricter `A_MEETING_REVIEW_CHANGES` check applies only when `lineage_json` is present); owner execution creates exactly one audit record with the established action and result target:

```python
with pytest.raises(HTTPException) as missing:
    workflow.patch_meeting_change_proposal(
        row_id=meeting.id, proposal_id=other_proposal.id,
        payload=patch_payload, current_user="owner", db=db,
    )
assert missing.value.status_code == 404

with pytest.raises(HTTPException) as denied:
    workflow.execute_meeting_change_set(
        row_id=meeting.id,
        payload=schemas.MeetingChangeSetExecutePayload(proposal_ids=[proposal.id]),
        current_user="member", db=db,
    )
assert denied.value.status_code == 403

result = workflow.execute_meeting_change_set(
    row_id=meeting.id,
    payload=schemas.MeetingChangeSetExecutePayload(proposal_ids=[proposal.id]),
    current_user="owner", db=db,
)
log = db.query(models.OperationLog).filter_by(
    action="meeting_change_execute", target_id=proposal.id,
).one()
assert result["proposals"][0]["execution_status"] == "executed"
assert json.loads(log.after_json)["result_target_id"] == proposal.result_target_id
```

- [x] **Step 3: Run the new direct boundary tests and verify red.**

Run:

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_meeting_change_set_review_workflow_boundaries.py -q
```

Expected: collection fails because `app.services.meeting_change_set_review_workflow` is not importable.

- [x] **Step 4: Commit the failing boundary tests.**

```powershell
git add bowei_ai_dashboard/tests/test_meeting_change_set_review_workflow_boundaries.py
git diff --cached --check
git commit -m "test: define meeting change-set review workflow boundary"
```

### Task 2: Implement the service-owned read and review commands

**Files:**

- Create: `bowei_ai_dashboard/app/services/meeting_change_set_review_workflow.py`
- Modify: `bowei_ai_dashboard/tests/test_meeting_change_set_review_workflow_boundaries.py`

- [x] **Step 1: Add the new module's imports and stable payload functions.**

Use these exact service dependencies; do not import `app.routers.meetings`:

```python
import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..domain.workflow_permissions import (
    A_MEETING_APPLY_CHANGES,
    A_MEETING_REVIEW_CHANGES,
)
from ..permissions import (
    PROJECT_ROLE_OWNER_KEY,
    get_user_context_from_db,
    require_login,
    require_project_access,
)
from ..services import policy as P
from ..services.meeting_change_set import (
    edit_meeting_change_proposal,
    edit_project_meeting_lineage_proposal,
    execute_meeting_change_set as execute_change_set_domain,
)
from ..services.project_resolution import resolve_project_context
```

Implement `_json_value`, `meeting_change_proposal_payload`, and `meeting_change_set_payload` by moving the current router behavior verbatim: proposal target includes `project_id`, optional `workstream_id`, `subtask_id`, `execution_schedule_id`, and `parent_workstream_id`; conflict reasons are exposed only when `execution_status == "conflict"`; proposals are ordered by ascending ID.

- [x] **Step 2: Implement self-contained lookup and permission helpers.**

Implement `_require_workflow_action`, `_row_project_id`, `_can_view_meeting_draft`, `_meeting_for_read`, `_change_set_for_meeting`, and `_proposal_for_change_set` using the same messages as the Router. The access helper must not loosen draft visibility:

```python
def _meeting_for_read(row_id: int, current_user: str, db: Session) -> models.Meeting:
    context = get_user_context_from_db(current_user, db)
    row = db.get(models.Meeting, row_id)
    if not row:
        raise HTTPException(404, "meeting not found")
    project_id = _row_project_id(row, db)
    if row.publish_status != "published" and not _can_view_meeting_draft(
        row, current_user, context, db,
    ):
        raise HTTPException(403, "permission denied")
    if project_id is not None:
        require_project_access(current_user, project_id, db)
    elif not (context.get("is_tech_admin") or context.get("is_ceo")):
        raise HTTPException(403, "permission denied")
    return row
```

`_proposal_for_change_set` must query by both `id` and `change_set_id` and raise `HTTPException(404, "meeting change proposal not found")` when absent.

- [x] **Step 3: Implement read and patch as one-commit commands.**

Use the following command shapes. `patch_meeting_change_proposal` must use workflow-review permission only for proposals with lineage, preserve the current ordinary proposal behavior, commit once, refresh, and return the stable proposal payload:

```python
def get_meeting_change_set(*, row_id: int, current_user: str, db: Session) -> dict:
    current_user = require_login(current_user, db)
    meeting = _meeting_for_read(row_id, current_user, db)
    return meeting_change_set_payload(_change_set_for_meeting(meeting.id, db), db)

def patch_meeting_change_proposal(*, row_id: int, proposal_id: int,
                                  payload: schemas.MeetingChangeProposalPatch,
                                  current_user: str, db: Session) -> dict:
    current_user = require_login(current_user, db)
    meeting = _meeting_for_read(row_id, current_user, db)
    change_set = _change_set_for_meeting(meeting.id, db)
    proposal = _proposal_for_change_set(proposal_id, change_set.id, db)
    if _json_value(proposal.lineage_json, {}):
        context = get_user_context_from_db(current_user, db)
        _require_workflow_action(context, change_set.project_id, A_MEETING_REVIEW_CHANGES, db)
        edit_project_meeting_lineage_proposal(
            proposal=proposal, change_set=change_set, meeting=meeting,
            actor=current_user, proposed_updates=payload.proposed, db=db,
        )
    else:
        edit_meeting_change_proposal(
            proposal=proposal, change_set=change_set,
            transcript_text=meeting.transcript_text or "",
            proposed=payload.proposed, evidence=payload.evidence,
            reason=payload.reason, db=db,
        )
    db.commit()
    db.refresh(proposal)
    return meeting_change_proposal_payload(proposal, change_set.project_id)
```

- [x] **Step 4: Run direct tests and existing change-set regression tests.**

Run:

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_meeting_change_set_review_workflow_boundaries.py tests/test_meeting_change_set_writeback.py -q
```

Expected: pass, including ordinary revalidation, existing endpoint behavior, and no schema change.

- [x] **Step 5: Commit the application service.**

```powershell
git add bowei_ai_dashboard/app/services/meeting_change_set_review_workflow.py bowei_ai_dashboard/tests/test_meeting_change_set_review_workflow_boundaries.py
git diff --cached --check
git commit -m "refactor: extract meeting change-set review workflow"
```

### Task 3: Move execution audit and turn the Router into an adapter

**Files:**

- Modify: `bowei_ai_dashboard/app/services/meeting_change_set_review_workflow.py`
- Modify: `bowei_ai_dashboard/app/routers/meetings.py:49-56, 519-580, 825, 1313, 1653-1769`
- Modify: `bowei_ai_dashboard/tests/test_meeting_change_set_review_workflow_boundaries.py`

- [x] **Step 1: Add execution transaction, preservation, and Router-delegation tests.**

Add a frozen project test using `project.status = "pending_close"`; it must return `409`, preserve proposal `pending`, and add no `meeting_change_execute` log. Add a router source assertion that each of the three route bodies delegates to `change_set_review_workflow` and the route block does not contain `db.query(models.MeetingChangeSet)`:

```python
with pytest.raises(HTTPException) as frozen:
    workflow.execute_meeting_change_set(
        row_id=meeting.id,
        payload=schemas.MeetingChangeSetExecutePayload(proposal_ids=[proposal.id]),
        current_user="owner", db=db,
    )
assert frozen.value.status_code == 409
assert proposal.execution_status == "pending"
assert db.query(models.OperationLog).filter_by(action="meeting_change_execute").count() == 0

source = Path("app/routers/meetings.py").read_text(encoding="utf-8")
execute_block = source[source.index("def execute_reviewed_meeting_change_set"):source.index("@router.get(\"/{row_id}\")")]
assert "change_set_review_workflow.execute_meeting_change_set(" in execute_block
assert "db.query(models.MeetingChangeSet)" not in execute_block
```

- [x] **Step 2: Run the new test and verify red.**

Run:

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_meeting_change_set_review_workflow_boundaries.py -q
```

Expected: the service lacks its public execution command and the router is not yet delegating.

- [x] **Step 3: Implement the service-owned execute command and its audit payload.**

Use `A_MEETING_APPLY_CHANGES`, then delegate all state checks and entity writes to the existing domain service. The service alone adds audit records and commits:

```python
def execute_meeting_change_set(*, row_id: int,
                               payload: schemas.MeetingChangeSetExecutePayload,
                               current_user: str, db: Session) -> dict:
    current_user = require_login(current_user, db)
    meeting = _meeting_for_read(row_id, current_user, db)
    context = get_user_context_from_db(current_user, db)
    _require_workflow_action(context, meeting.project_id, A_MEETING_APPLY_CHANGES, db)
    proposals = execute_change_set_domain(
        meeting=meeting, proposal_ids=payload.proposal_ids,
        actor=current_user, db=db,
    )
    for proposal in proposals:
        proposed = _json_value(proposal.proposed_json, {})
        evidence = _json_value(proposal.evidence_json, [])
        crud.log(
            db, current_user, "meeting_change_execute", "meeting_change_proposal",
            proposal.id,
            {"proposal_id": proposal.id, "before": _json_value(proposal.before_json, {}),
             "proposed": proposed, "evidence": evidence},
            {"proposal_id": proposal.id, "proposed": proposed, "evidence": evidence,
             "result_target_id": proposal.result_target_id,
             "execution_status": proposal.execution_status},
            project_id=meeting.project_id,
        )
    db.commit()
    return meeting_change_set_payload(_change_set_for_meeting(meeting.id, db), db)
```

- [x] **Step 4: Redirect all existing payload and endpoint call sites.**

In `meetings.py`, import the module once:

```python
from ..services import meeting_change_set_review_workflow as change_set_review_workflow
```

Replace the current helper uses at the project meeting run payload and analysis response with `change_set_review_workflow.meeting_change_set_payload(...)`, then remove `_json_value`, `_meeting_change_proposal_payload`, and `_meeting_change_set_payload` only if there are no remaining references. Replace each endpoint body while preserving its decorator and parameters:

```python
return change_set_review_workflow.get_meeting_change_set(
    row_id=row_id, current_user=current_user, db=db,
)

return change_set_review_workflow.patch_meeting_change_proposal(
    row_id=row_id, proposal_id=proposal_id, payload=payload,
    current_user=current_user, db=db,
)

return change_set_review_workflow.execute_meeting_change_set(
    row_id=row_id, payload=payload, current_user=current_user, db=db,
)
```

Remove now-unused imports from `meeting_change_set` only after `rg` confirms the Router no longer needs them. Do not modify `review_project_meeting` or `_execute_project_meeting_schedule_changes`.

- [x] **Step 5: Run focused behavior and project-meeting regressions.**

Run:

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_meeting_change_set_review_workflow_boundaries.py tests/test_meeting_change_set_writeback.py tests/test_project_meeting_review_writeback.py -q
```

Expected: pass, preserving four-action execution, stale batch atomicity, audit records, frozen project rejection, lineage review behavior, and the independent project-document review flow.

- [x] **Step 6: Commit the route delegation.**

```powershell
git add bowei_ai_dashboard/app/services/meeting_change_set_review_workflow.py bowei_ai_dashboard/app/routers/meetings.py bowei_ai_dashboard/tests/test_meeting_change_set_review_workflow_boundaries.py
git diff --cached --check
git commit -m "refactor: move meeting change-set commands to service"
```

### Task 4: Delivery gate and evidence

**Files:**

- Modify: `docs/superpowers/plans/2026-09-13-meeting-change-set-review-workflow-boundaries.md`

- [x] **Step 1: Run the complete meeting-focused gate.**

Run:

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_meeting_change_set_review_workflow_boundaries.py tests/test_meeting_change_set_writeback.py tests/test_project_meeting_review_writeback.py tests/test_meeting_draft_review.py tests/test_project_meeting_agent_processing.py -q
```

Expected: exit code 0, covering service boundaries, endpoint contracts, project-meeting lineage, draft contracts, and agent persistence.

- [x] **Step 2: Run the full delivery gate.**

Run:

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests -q
Set-Location ..\frontend
npm run test:all
npm run build
Set-Location ..
git diff --check
git status --short
```

Expected: backend, frontend test suites, and production build all succeed; the existing `exceljs.min` size warning remains non-blocking unless its wording changes to an error.

- [x] **Step 3: Record actual totals and commit the verification evidence.**

Replace the unchecked Task 4 items with checked entries and append the exact command outcomes and durations to this plan. Then run:

```powershell
git add docs/superpowers/plans/2026-09-13-meeting-change-set-review-workflow-boundaries.md
git diff --cached --check
git commit -m "docs: record meeting change-set workflow verification"
```

## Verification record

- 2026-09-13: the initial direct boundary test failed during collection as expected because `meeting_change_set_review_workflow` was not importable (`ImportError`).
- 2026-09-13: the initial execute-command test failed as expected because the new service had no `execute_meeting_change_set` attribute; the route-boundary test then failed as expected because the Router still queried `MeetingChangeSet` directly.
- 2026-09-13: `python -m pytest tests/test_meeting_change_set_review_workflow_boundaries.py tests/test_meeting_change_set_writeback.py -q` — `13 passed in 50.06s`.
- 2026-09-13: `python -m pytest tests/test_meeting_change_set_review_workflow_boundaries.py tests/test_meeting_change_set_writeback.py tests/test_project_meeting_review_writeback.py -q` — `33 passed in 51.38s` before the final direct preservation-test additions; rerun after those additions — `35 passed in 56.70s`.
- 2026-09-13: direct boundary tests after adding cross-meeting, non-owner execution, and frozen-project guards — `6 passed in 1.65s`. The frozen-project case was added during migration audit and passed because the reused domain service already enforced `pending_close`; it proves that the service boundary did not bypass that protection.
- 2026-09-13: complete meeting-focused gate — `50 passed in 52.22s` for boundary, writeback, project-review, draft-review, and agent-processing tests.
- 2026-09-13: complete backend gate — `1948 passed, 12 skipped in 397.67s (0:06:37)`.
- 2026-09-13: `npm run test:all` — Vitest `27` files / `89` tests passed; frontend contracts `502` passed / `0` failed.
- 2026-09-13: `npm run build` completed in `7.18s`; the known non-blocking `exceljs.min` chunk-size warning remains (940.19 kB minified, 271.33 kB gzip).
