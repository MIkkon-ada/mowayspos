# Confirmation Card Writeback Workflow Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not delegate to subagents for this repository.

**Goal:** Move the single-card final-confirmation writeback command into a service-owned transaction without changing its API, permissions, state machine, audit, or business-entity lineage.

**Architecture:** Add `confirmation_card_writeback_workflow.py` for `confirm_task_card` and its exclusive entity-write helpers. It reuses access controls from `confirmation_review_workflow.py` but never imports the confirmations Router. The Router remains an HTTP adapter; the broader submission-level `confirm` command is out of scope.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Pydantic 2, pytest.

---

## File structure

- Create: `bowei_ai_dashboard/app/services/confirmation_card_writeback_workflow.py`
- Modify: `bowei_ai_dashboard/app/routers/confirmations.py:4-14, 321-404, 1462-1513`
- Create: `bowei_ai_dashboard/tests/test_confirmation_card_writeback_workflow_boundaries.py`
- Reuse: `bowei_ai_dashboard/tests/test_ai_confirm_related_subtask_writeback.py`
- Reuse: `bowei_ai_dashboard/tests/test_confirmation_card_coach_flow.py`
- Reuse: `bowei_ai_dashboard/tests/test_confirmation_card_coordinator_flow.py`
- Reuse: `bowei_ai_dashboard/tests/test_company_ceo_owner_confirmation_permission.py`
- Reuse: `bowei_ai_dashboard/tests/test_confirmation_log_actions.py`

### Task 1: Define a direct card-writeback boundary

**Files:**

- Create: `bowei_ai_dashboard/tests/test_confirmation_card_writeback_workflow_boundaries.py`

- [ ] **Step 1: Write a failing direct-service transition test.**

Use `_make_session`, `_seed_card_coach_team`, and `_make_card_submission`. Create two cards, make card zero `subtask_progress`, and invoke the proposed service directly:

~~~
result = workflow.confirm_task_card(
    submission_id=row.id,
    card_index=0,
    payload=schemas.ConfirmRequest(operator="owner"),
    current_user="owner",
    db=db,
)
reports = json.loads(result["submission"]["human_result_json"])["task_reports"]
assert reports[0]["confirmation_status"] == "confirmed"
assert not reports[1].get("confirmation_status")
assert achievement.related_subtask_id == team["subtask"].id
assert issue.related_subtask_id == team["subtask"].id
~~~

- [ ] **Step 2: Run the new test and verify red.**

~~~
python -m pytest tests/test_confirmation_card_writeback_workflow_boundaries.py -q
~~~

Expected: `confirmation_card_writeback_workflow` is not importable.

- [ ] **Step 3: Commit the failing boundary test.**

~~~
git add tests/test_confirmation_card_writeback_workflow_boundaries.py
git diff --cached --check
git commit -m "test: define confirmation card writeback boundary"
~~~

### Task 2: Extract payload safety and entity-write helpers

**Files:**

- Create: `bowei_ai_dashboard/app/services/confirmation_card_writeback_workflow.py`
- Modify: `bowei_ai_dashboard/app/routers/confirmations.py:4-14, 321-404`
- Modify: `bowei_ai_dashboard/tests/test_confirmation_card_writeback_workflow_boundaries.py`

- [ ] **Step 1: Add failing tests for persisted workflow fields and `suggest_new_subtask`.**

For a persisted `ceo_decided` card, send edited `human_result` with a forged `confirmation_status`; assert persisted `ceo_note` survives until the normal final transition. For `suggest_new_subtask`, assert the created SubTask has `source_submission_id`, its Achievement has `related_subtask_id`, and the submission's `related_task_id` is the parent Task ID.

~~~
assert stored_report["ceo_note"] == "已批示，继续执行"
assert new_subtask.source_submission_id == row.id
assert achievement.related_subtask_id == new_subtask.id
assert db.get(models.UpdateSubmission, row.id).related_task_id == team["task"].id
~~~

- [ ] **Step 2: Verify red.**

~~~
python -m pytest tests/test_confirmation_card_writeback_workflow_boundaries.py -q
~~~

Expected: the direct service lacks writeback helpers.

- [ ] **Step 3: Create the service without Router coupling.**

Import only domain/model/service dependencies and `_sync_parent_task_status` from `app.routers.subtasks`. Reuse review access checks; do not import `app.routers.confirmations`.

~~~
from ..services.confirmation_review_workflow import (
    load_submission, require_confirmation_center, require_owner_style_actor,
    require_submission_writable, submission_project_context, submission_project_name,
)

_CARD_OWNER_ACTIONABLE = frozenset({"", "pending", "ceo_decided", "coordinator_given"})
~~~

Implement private `_task_reports`, `_get_task_card`, `_card_confirmation_status`, `_require_card_owner_actionable`, `_merge_card_confirmation_payload`, `_mark_task_card`, and `_all_task_cards_confirmed` using existing messages and field-preservation semantics. Move `_parse_subtask_issue`, `_storage_issue_type`, `_issue_status_for`, and the full `_write_single_task_report` behavior, retaining all branches: new subtask, normal progress/completion, missing/deleted subtask `422`, `crud.validate_subtask_link`, parent-status sync, write flags, Achievement fulfillment, and Issue lineage.

- [ ] **Step 4: Preserve generic-confirm compatibility aliases.**

Only re-export helpers used by both commands; leave the generic confirm's multi-mode write logic in the Router:

~~~
from ..services.confirmation_card_writeback_workflow import (
    all_task_cards_confirmed as _all_task_cards_confirmed,
    mark_task_card as _mark_task_card,
    merge_card_confirmation_payload as _merge_card_confirmation_payload,
    write_single_task_report as _write_single_task_report,
)
~~~

- [ ] **Step 5: Verify direct behavior and existing lineage.**

~~~
python -m pytest tests/test_confirmation_card_writeback_workflow_boundaries.py tests/test_ai_confirm_related_subtask_writeback.py -q
~~~

Expected: pass, including no-new-migration and no-new-endpoint assertions.

- [ ] **Step 6: Commit helper extraction.**

~~~
git add app/services/confirmation_card_writeback_workflow.py app/routers/confirmations.py tests/test_confirmation_card_writeback_workflow_boundaries.py
git diff --cached --check
git commit -m "refactor: extract confirmation card writeback helpers"
~~~

### Task 3: Move the final transaction and delegate the route

**Files:**

- Modify: `bowei_ai_dashboard/app/services/confirmation_card_writeback_workflow.py`
- Modify: `bowei_ai_dashboard/app/routers/confirmations.py:1462-1513`
- Modify: `bowei_ai_dashboard/tests/test_confirmation_card_writeback_workflow_boundaries.py`

- [ ] **Step 1: Add failing access and state tests.**

Cover non-owner project coach `403`, frozen-project rejection before mutation, pending-ceo card `409`, and the transition where only confirming the second card sets `SS.S_CONFIRMED`, `confirmed_by`, and `confirmed_at`.

~~~
with pytest.raises(HTTPException) as denied:
    workflow.confirm_task_card(
        submission_id=row.id, card_index=0,
        payload=schemas.ConfirmRequest(operator="coach"),
        current_user="coach", db=db,
    )
assert denied.value.status_code == 403
~~~

- [ ] **Step 2: Verify red.**

~~~
python -m pytest tests/test_confirmation_card_writeback_workflow_boundaries.py -q
~~~

Expected: direct command lacks full access/state/transaction behavior.

- [ ] **Step 3: Implement one service-owned commit boundary.**

Implement the exact existing sequence:

~~~
row = load_submission(db, submission_id)
context = get_user_context_from_db(current_user or payload.operator, db)
require_submission_writable(row, context, db)
require_confirmation_center(context)
require_owner_style_actor(context, row, db)
W.require_submission_status(row, SS.OWNER_ACTIONABLE)
before = crud.to_dict(row)
persisted_data = W.submission_result(row)
_, persisted_report = _get_task_card(persisted_data, card_index)
_require_card_owner_actionable(persisted_report)
data = _merge_card_confirmation_payload(persisted_data, payload.human_result)
project_id = submission_project_context(db, row, json_payload=data)["project_id"]
task_id = _write_single_task_report(
    db, row, data, report, payload.operator, project_id,
    submission_project_name(db, row, json_payload=data), now,
)
_mark_task_card(row, data, card_index, "confirmed", payload.operator)
crud.log(db, payload.operator, "confirmation_card_approve", "confirmation", row.id,
         before, {"card_index": card_index, "task_id": task_id}, project_id=project_id)
db.commit()
return {"ok": True, "submission": crud.to_dict(row)}
~~~

Pass `submission_project_name(db, row, json_payload=data)` to the write helper. If every card is confirmed, set `SS.S_CONFIRMED`, `confirmed_by`, and `confirmed_at`; otherwise set `SS.S_PENDING_OWNER`. Do not notify, migrate schema, or commit inside helpers.

- [ ] **Step 4: Replace the Router body with one service call.**

Keep the current decorator/signature/dependencies and replace only the body:

~~~
return card_writeback_workflow.confirm_task_card(
    submission_id=submission_id, card_index=card_index, payload=payload,
    current_user=current_user, db=db,
)
~~~

- [ ] **Step 5: Run focused behavior and permission regressions.**

~~~
python -m pytest tests/test_confirmation_card_writeback_workflow_boundaries.py tests/test_ai_confirm_related_subtask_writeback.py tests/test_confirmation_card_coach_flow.py tests/test_confirmation_card_coordinator_flow.py tests/test_company_ceo_owner_confirmation_permission.py tests/test_confirmation_log_actions.py -q
~~~

Expected: pass, proving card isolation, pending-card bypass prevention, lineage, post-coach confirmation, owner authorization, and static audit action codes.

- [ ] **Step 6: Commit transaction migration.**

~~~
git add app/services/confirmation_card_writeback_workflow.py app/routers/confirmations.py tests/test_confirmation_card_writeback_workflow_boundaries.py
git diff --cached --check
git commit -m "refactor: move confirmation card writeback to service"
~~~

### Task 4: Delivery gate and evidence

**Files:**

- Modify: `docs/superpowers/plans/2026-09-13-confirmation-card-writeback-workflow-boundaries.md`

- [ ] **Step 1: Run focused confirmation writeback verification.**

~~~
Set-Location bowei_ai_dashboard
python -m pytest tests/test_confirmation_card_writeback_workflow_boundaries.py tests/test_ai_confirm_related_subtask_writeback.py tests/test_confirmation_card_coach_flow.py tests/test_confirmation_card_coordinator_flow.py tests/test_company_ceo_owner_confirmation_permission.py tests/test_confirmation_log_actions.py -q
~~~

Expected: exit code 0.

- [ ] **Step 2: Run complete delivery verification.**

~~~
python -m pytest tests -q
Set-Location ..\frontend
npm run test:all
npm run build
Set-Location ..
git diff --check
git status --short
~~~

Expected: all commands pass; the independently loaded `exceljs.min` size warning remains non-blocking.

- [ ] **Step 3: Record actual totals and commit.**

Record exact focused/backend/frontend/build totals in this plan, mark every completed step, then run:

~~~
git add docs/superpowers/plans/2026-09-13-confirmation-card-writeback-workflow-boundaries.md
git diff --cached --check
git commit -m "docs: record confirmation card writeback verification"
~~~
