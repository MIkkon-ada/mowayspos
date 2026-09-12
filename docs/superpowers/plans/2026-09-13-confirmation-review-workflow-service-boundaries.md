# Confirmation Review Workflow Service Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not delegate to subagents for this repository.

**Goal:** Move confirmation-center human review commands into a service-owned transaction boundary without changing HTTP contracts, review states, permissions, audits, or notifications.

**Architecture:** `confirmation_review_workflow.py` owns common submission loading, compatibility-safe identity checks, manual-review state transitions, audit, notifications, and commits. `confirmations.py` remains the HTTP adapter and re-exports legacy helper aliases while its final `confirm` writeback and query endpoints remain untouched. The migration is deliberately split into submission-level commands, then task-card commands.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Pydantic 2, pytest.

---

## File structure

- Create: `bowei_ai_dashboard/app/services/confirmation_review_workflow.py`
- Modify: `bowei_ai_dashboard/app/routers/confirmations.py:346-529, 1039-1061, 1654-2520`
- Create: `bowei_ai_dashboard/tests/test_confirmation_review_workflow_boundaries.py`
- Reuse: `bowei_ai_dashboard/tests/test_confirmation_coordinator_flow.py`
- Reuse: `bowei_ai_dashboard/tests/test_confirmation_card_coordinator_flow.py`
- Reuse: `bowei_ai_dashboard/tests/test_confirmation_card_coach_flow.py`
- Reuse: `bowei_ai_dashboard/tests/test_submission_submitter_identity_flow.py`
- Reuse: `bowei_ai_dashboard/tests/test_confirmation_log_actions.py`

### Task 1: Extract shared review helpers without moving endpoints

**Files:**

- Create: `bowei_ai_dashboard/app/services/confirmation_review_workflow.py`
- Create: `bowei_ai_dashboard/tests/test_confirmation_review_workflow_boundaries.py`
- Modify: `bowei_ai_dashboard/app/routers/confirmations.py:346-529`

- [x] **Step 1: Write the failing helper-boundary test.**

```python
from app.routers import confirmations


def test_router_reexports_confirmation_review_helpers():
    from app.services import confirmation_review_workflow as workflow

    assert confirmations._load_submission is workflow.load_submission
    assert confirmations._is_submission_submitter is workflow.is_submission_submitter
    assert confirmations._submission_project_id is workflow.submission_project_id
```

- [x] **Step 2: Verify the new test is red.**

Run from `bowei_ai_dashboard`:

```powershell
python -m pytest tests/test_confirmation_review_workflow_boundaries.py -q
```

Expected: failure because `confirmation_review_workflow` does not exist.

- [x] **Step 3: Move exact shared helpers into the service.**

Move, without changing their observable behavior, the following Router helpers into the new service and export them with public names: `_load_submission`, `_is_submission_submitter`, `_submission_recipient_id`, `_submission_project_context`, `_submission_project_id`, `_submission_project_name`, `_resolve_pending_project_id`, `_require_submission_project_access`, `_require_submission_writable`, `_require_submission_owner_or_admin`, `_require_confirmation_center`, `_require_owner_style_actor`, and `_can_owner_style_action`.

Keep the identity fallback order in the service: matching `submitter_id` to `context["person_id"]`, then the exact account username, then a unique active person-name fallback only for legacy rows. Ambiguous legacy names must remain denied. Keep project business writability before every review state mutation:

```python
def require_submission_writable(
    row: models.UpdateSubmission,
    context: dict,
    db: Session,
) -> int | None:
    project_id = submission_project_id(db, row)
    if project_id is not None:
        require_project_business_writable(project_id, db)
    return project_id
```

`require_submission_project_access` must preserve the current missing-project `404`, explicit project-ID mismatch `403`, and `resolve_project_context` fallback behavior. The service may import domain/policy/permission services, but must not import `app.routers.confirmations`.

- [x] **Step 4: Re-export exact aliases and verify green.**

Replace the moved Router definitions with aliases, for example:

```python
from ..services.confirmation_review_workflow import (
    is_submission_submitter as _is_submission_submitter,
    load_submission as _load_submission,
    submission_project_id as _submission_project_id,
)
from ..services import confirmation_review_workflow as review_workflow
```

Run:

```powershell
python -m pytest tests/test_confirmation_review_workflow_boundaries.py tests/test_submission_submitter_identity_flow.py -q
```

Expected: pass.

- [x] **Step 5: Commit the helper boundary.**

```powershell
git add app/services/confirmation_review_workflow.py app/routers/confirmations.py tests/test_confirmation_review_workflow_boundaries.py
git diff --cached --check
git commit -m "refactor: extract confirmation review helpers"
```

### Task 2: Move submission-level owner and submitter commands

**Files:**

- Modify: `bowei_ai_dashboard/app/services/confirmation_review_workflow.py`
- Modify: `bowei_ai_dashboard/app/routers/confirmations.py:1039-1061, 2037-2174, 2336-2405`
- Modify: `bowei_ai_dashboard/tests/test_confirmation_review_workflow_boundaries.py`

- [x] **Step 1: Add failing direct-service transition tests.**

Create a SQLite fixture with an active project, owner, submitter, and one `pending_owner` submission. Test direct `save_submission_review`, `return_submission_to_submitter`, `resubmit_submission`, `withdraw_submission`, `reject_submission_finally`, `mark_submission_unrecognized`, and `assign_submission_owner` calls. Assert the same status values, rejection/note fields, and rejection/withdrawal error statuses currently asserted by the existing flow tests.

The identity test must explicitly prove that a same-name different account cannot resubmit or withdraw:

```python
with pytest.raises(HTTPException, match="只有原提交人"):
    workflow.resubmit_submission(
        submission_id=row.id, payload=schemas.ResubmitRequest(),
        current_user="same-name-other-account", db=db,
    )
```

- [x] **Step 2: Verify red.**

```powershell
python -m pytest tests/test_confirmation_review_workflow_boundaries.py -q
```

Expected: missing `save_submission_review` or another direct command function.

- [x] **Step 3: Implement the submission-level commands.**

Each function has keyword-only `submission_id`, typed payload when applicable, `current_user`, and `db`. Preserve the Router ordering: load row, obtain context using `current_user or payload.operator` where the existing endpoint does, require project writability, require confirmation access/owner-style actor or original-submitter identity, validate status/cards, mutate, audit, notify, commit once, and return the existing shape:

```python
return {"ok": True, "submission": crud.to_dict(row)}
```

Implement exact state transitions and audit names:

| Command | State / audit action |
| --- | --- |
| `save_submission_review` | `needs_revision` / `confirmation_update` |
| `return_submission_to_submitter` | `rejected` / `confirmation_reject` |
| `resubmit_submission` | `pending_owner` / `confirmation_resubmit` |
| `withdraw_submission` | `withdrawn` / `confirmation_withdraw` |
| `reject_submission_finally` | `permanently_rejected` / `confirmation_mark_not_imported` |
| `mark_submission_unrecognized` | `needs_revision` / `confirmation_mark_unrecognized` |
| `assign_submission_owner` | `pending_owner` / `confirmation_assign_owner` |

Do not move or edit `confirm`. Keep `merge_card_confirmation_payload`, pending-card guards, and existing notification payloads byte-for-byte equivalent in meaning. Reuse `send`, `project_strict_owner_ids`, and account/person-ID lookup helpers from `services.notify`; notification target selection remains in the service.

- [x] **Step 4: Delegate exactly seven Router endpoints and verify green.**

Each body becomes a single service call. For example:

```python
return review_workflow.withdraw_submission(
    submission_id=submission_id,
    current_user=current_user,
    db=db,
)
```

Run:

```powershell
python -m pytest tests/test_confirmation_review_workflow_boundaries.py tests/test_submission_submitter_identity_flow.py tests/test_confirmation_card_coach_flow.py tests/test_confirmation_card_coordinator_flow.py -q
```

Expected: pass.

- [x] **Step 5: Commit submission-level review commands.**

```powershell
git add app/services/confirmation_review_workflow.py app/routers/confirmations.py tests/test_confirmation_review_workflow_boundaries.py
git diff --cached --check
git commit -m "refactor: move confirmation submission reviews to service"
```

### Task 3: Move submission-level coordinator and coach decisions

**Files:**

- Modify: `bowei_ai_dashboard/app/services/confirmation_review_workflow.py`
- Modify: `bowei_ai_dashboard/app/routers/confirmations.py:2177-2333`
- Modify: `bowei_ai_dashboard/tests/test_confirmation_review_workflow_boundaries.py`

- [x] **Step 1: Add failing direct-service workflow tests.**

Test the direct sequence owner transfer → coordinator feedback → owner escalation → project-coach decision. Assert status progression `waiting_coordinator → coordinator_given → waiting_ceo → ceo_decided`, project-scoped denial for another project's coordinator/coach, and unchanged status when an invalid actor calls a command.

```python
with pytest.raises(HTTPException) as denied:
    workflow.coordinator_feedback(
        submission_id=row.id, payload=schemas.WorkflowNoteRequest(note="x"),
        current_user="other-project-coordinator", db=db,
    )
assert denied.value.status_code == 403
```

- [x] **Step 2: Verify red.**

```powershell
python -m pytest tests/test_confirmation_review_workflow_boundaries.py -q
```

Expected: missing `transfer_submission_to_coordinator` or the first direct workflow command.

- [x] **Step 3: Implement four decision commands.**

Implement `transfer_submission_to_coordinator`, `coordinator_feedback`, `escalate_submission_to_coach`, and `coach_decide_submission`. Each must call `P.decide_workflow_for_project` with the existing action constant where the Router currently does, preserve the exact `W.require_submission_status` set, write the existing note column, emit the same audit action, notify the same project role IDs excluding the caller, commit once, and return the existing response dict.

The policy call pattern stays explicit:

```python
if not P.decide_workflow_for_project(
    context, row.project_id, A_CONFIRMATION_CEO_DECIDE, db
).allowed:
    raise HTTPException(403, "permission denied — 仅该项目企业教练或管理员可批示")
```

- [x] **Step 4: Delegate four Router endpoints and verify green.**

```powershell
python -m pytest tests/test_confirmation_review_workflow_boundaries.py tests/test_confirmation_coordinator_flow.py tests/test_confirmation_card_coach_flow.py tests/test_confirmation_log_actions.py -q
```

Expected: pass.

- [x] **Step 5: Commit coordinator and coach decisions.**

```powershell
git add app/services/confirmation_review_workflow.py app/routers/confirmations.py tests/test_confirmation_review_workflow_boundaries.py
git diff --cached --check
git commit -m "refactor: move confirmation escalation decisions to service"
```

### Task 4: Move task-card review and issue escalation commands

**Files:**

- Modify: `bowei_ai_dashboard/app/services/confirmation_review_workflow.py`
- Modify: `bowei_ai_dashboard/app/routers/confirmations.py:1708-2034, 2409-2476`
- Modify: `bowei_ai_dashboard/tests/test_confirmation_review_workflow_boundaries.py`

- [x] **Step 1: Add failing card-level service tests.**

Use one submission with multiple task reports. Cover direct card reject, transfer/coordinator feedback, coach escalation/decision, and `escalate_card_to_issue`. Assert that only the selected card changes, other cards retain their workflow history, an already pending card returns 409, and issue escalation returns its Issue ID while retaining the existing confirmation audit action.

- [x] **Step 2: Verify red.**

```powershell
python -m pytest tests/test_confirmation_review_workflow_boundaries.py -q
```

Expected: missing `reject_task_card_review` or another task-card service command.

- [x] **Step 3: Implement card-level command functions.**

Move the Router's `_get_task_card`, `_mark_task_card`, `_card_confirmation_status`, and pending-card guards into the service before the commands that consume them. Implement `reject_task_card_review`, `transfer_task_card_to_coordinator`, `coordinator_feedback_task_card`, `escalate_task_card_to_coach`, `coach_decide_task_card`, and `escalate_task_card_to_issue` by retaining their current Pydantic payloads, policy actions, mutation keys, notification title/body/link fields, audit action codes, and one-commit transaction boundary. Keep `confirm_task_card` in the Router because it writes Task/SubTask entities; it requires its own writeback-boundary design.

`escalate_task_card_to_issue` must validate `target in {"ceo", "coordinator"}` and nonempty `note` before mutation, then call the existing `ESC.escalate_card_to_issue` service; it must not reimplement Issue creation.

- [x] **Step 4: Delegate six task-card routes and verify green.**

```powershell
python -m pytest tests/test_confirmation_review_workflow_boundaries.py tests/test_confirmation_card_coordinator_flow.py tests/test_confirmation_card_coach_flow.py tests/test_confirmation_log_actions.py -q
```

Expected: pass.

- [ ] **Step 5: Commit task-card review migration.**

```powershell
git add app/services/confirmation_review_workflow.py app/routers/confirmations.py tests/test_confirmation_review_workflow_boundaries.py
git diff --cached --check
git commit -m "refactor: move confirmation card reviews to service"
```

### Task 5: Delivery gate and evidence

**Files:**

- Modify: `docs/superpowers/plans/2026-09-13-confirmation-review-workflow-service-boundaries.md`

- [ ] **Step 1: Run focused confirmation governance tests.**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_confirmation_review_workflow_boundaries.py tests/test_confirmation_coordinator_flow.py tests/test_confirmation_card_coordinator_flow.py tests/test_confirmation_card_coach_flow.py tests/test_submission_submitter_identity_flow.py tests/test_confirmation_log_actions.py -q
```

Expected: exit code 0.

- [ ] **Step 2: Run complete delivery verification.**

```powershell
python -m pytest tests -q
Set-Location ..\frontend
npm run test:all
npm run build
Set-Location ..
git diff --check
git status --short
```

Expected: all commands pass. The independently loaded `exceljs.min` chunk may retain its known size warning.

- [ ] **Step 3: Record actual totals and commit.**

Replace this instruction with the actual focused/backend/frontend/build totals, check every completed step, then run:

```powershell
git add docs/superpowers/plans/2026-09-13-confirmation-review-workflow-service-boundaries.md
git diff --cached --check
git commit -m "docs: record confirmation review workflow verification"
```
