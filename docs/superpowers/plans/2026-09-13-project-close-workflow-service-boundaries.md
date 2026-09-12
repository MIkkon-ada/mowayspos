# Project Close Workflow Service Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not delegate to subagents for this repository.

**Goal:** Move project close-request reads and commands out of the projects router into a service-owned workflow without changing any public contract.

**Architecture:** `project_close_workflow.py` owns close-request lookup, locking, command authorization, material validation, audit, notifications, commit and DTO creation. `projects.py` remains the HTTP adapter and supplies its existing lifecycle compatibility writer plus the legacy query-view authorizer, so `status`, `lifecycle_status`, `is_active`, and legacy visibility stay synchronized without a service-to-router import.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Pydantic 2, pytest.

---

## File structure

- Create: `bowei_ai_dashboard/app/services/project_close_workflow.py`
- Modify: `bowei_ai_dashboard/app/routers/projects.py:1670-2153`
- Create: `bowei_ai_dashboard/tests/test_project_close_workflow_boundaries.py`
- Reuse: `tests/test_project_close_lifecycle_guards.py`, `tests/test_project_close_request_blockers.py`, `tests/test_project_permission_actions.py`, and `tests/test_full_role_lifecycle_audit.py`.

### Task 1: Extract immutable close-query helpers

**Files:**

- Create: `bowei_ai_dashboard/app/services/project_close_workflow.py`
- Create: `bowei_ai_dashboard/tests/test_project_close_workflow_boundaries.py`
- Modify: `bowei_ai_dashboard/app/routers/projects.py:1670-1825`

- [ ] **Step 1: Write the failing boundary test.**

```python
from app.routers import projects


def test_projects_router_reexports_close_workflow_helpers():
    from app.services import project_close_workflow as workflow

    assert projects._lock_project_for_close is workflow.lock_project_for_close
    assert projects._lock_close_request is workflow.lock_close_request
    assert projects._close_request_response is workflow.close_request_response
```

- [ ] **Step 2: Verify the test is red.**

Run from `bowei_ai_dashboard`:

```powershell
python -m pytest tests/test_project_close_workflow_boundaries.py -q
```

Expected: failure because `project_close_workflow` does not exist.

- [ ] **Step 3: Implement the helper boundary.**

Move the existing lock statements/loaders, project/request read lookup, close material state snapshot, ISO datetime formatter, response DTO, notification de-duplication, pending-pair assertion, and blocked-result exception into the new service. Preserve exception texts and DTO fields. Define both injected dependencies with their real keyword signatures:

```python
class LifecycleWriter(Protocol):
    def __call__(self, project: models.Project, lifecycle_status: str, *, db: Session, project_id: int) -> str:
        raise NotImplementedError

class ViewAuthorizer(Protocol):
    def __call__(self, current_user: str, project: models.Project, db: Session) -> dict:
        raise NotImplementedError
```

The row lock must retain `populate_existing=True`:

```python
def lock_project_for_close(project_id: int, db: Session) -> models.Project | None:
    statement = (
        select(models.Project)
        .where(models.Project.id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.execute(statement).scalar_one_or_none()
```

- [ ] **Step 4: Re-export helper aliases from the router and verify green.**

```python
from ..services.project_close_workflow import (
    close_request_response as _close_request_response,
    lock_close_request as _lock_close_request,
    lock_project_for_close as _lock_project_for_close,
)
```

Run:

```powershell
python -m pytest tests/test_project_close_workflow_boundaries.py tests/test_project_close_request_blockers.py -q
```

Expected: pass.

- [ ] **Step 5: Commit.**

```powershell
git add app/services/project_close_workflow.py app/routers/projects.py tests/test_project_close_workflow_boundaries.py
git diff --cached --check
git commit -m "refactor: extract project close workflow helpers"
```

### Task 2: Move creation, editing, and cancellation commands

**Files:**

- Modify: `bowei_ai_dashboard/app/services/project_close_workflow.py`
- Modify: `bowei_ai_dashboard/app/routers/projects.py:1829-2043`
- Modify: `bowei_ai_dashboard/tests/test_project_close_workflow_boundaries.py`

- [ ] **Step 1: Write failing direct service tests.**

```python
def test_create_close_request_uses_the_lifecycle_writer(db, active_project, valid_payload):
    from app.services import project_close_workflow as workflow

    writes = []
    def writer(project, status, *, db, project_id):
        writes.append((project_id, status))
        project.status = status
        project.is_active = status == "active"
        return status

    workflow.create_close_request(
        project_id=active_project.id, payload=valid_payload, current_user="owner",
        db=db, lifecycle_writer=writer,
    )

    assert writes == [(active_project.id, "pending_close")]
```

Add edit and cancellation assertions that preserve `pending`, then write `cancelled` and restore the project to `active`; a repeated cancel must raise `PROJECT_STATE_CONFLICT`.

- [ ] **Step 2: Verify red.**

```powershell
python -m pytest tests/test_project_close_workflow_boundaries.py -q
```

Expected: missing command functions.

- [ ] **Step 3: Implement service commands.**

Add `create_close_request`, `update_close_request`, and `cancel_close_request` with keyword-only `project_id`, `request_id` where applicable, typed Pydantic payload, `current_user`, `db`, and a lifecycle writer on state-changing commands.

Creation must authorize `A_REQUEST_CLOSE` before its project lock; require active/no pending request; call `evaluate_project_close`; write the request; call `lifecycle_writer(project, PL.S_PENDING_CLOSE, db=db, project_id=project_id)`; log `project_close_request_create`; notify coaches; commit once. Edit and cancel must lock project then request, authorize with `requester_person_id`, require the pending pair, preserve merged Pydantic material validation, audit action names, notification targets, one commit, and response shape. Cancellation writes `cancelled_at` and uses `PL.S_ACTIVE`.

- [ ] **Step 4: Delegate the five router endpoints and verify green.**

Each Router body must become a single service call. Read endpoints pass `view_authorizer=_require_close_request_view`; command endpoints pass the lifecycle writer when they change lifecycle, for example:

```python
return close_workflow.create_close_request(
    project_id=project_id, payload=payload, current_user=current_user, db=db,
    lifecycle_writer=_set_project_lifecycle,
)
```

Run:

```powershell
python -m pytest tests/test_project_close_workflow_boundaries.py tests/test_project_close_lifecycle_guards.py tests/test_project_close_request_blockers.py tests/test_project_permission_actions.py -q
```

Expected: pass.

- [ ] **Step 5: Commit.**

```powershell
git add app/services/project_close_workflow.py app/routers/projects.py tests/test_project_close_workflow_boundaries.py
git diff --cached --check
git commit -m "refactor: move project close commands to workflow service"
```

### Task 3: Move approval and rejection commands

**Files:**

- Modify: `bowei_ai_dashboard/app/services/project_close_workflow.py`
- Modify: `bowei_ai_dashboard/app/routers/projects.py:2047-2153`
- Modify: `bowei_ai_dashboard/tests/test_project_close_workflow_boundaries.py`

- [ ] **Step 1: Write failing review-transition tests.**

```python
assert approved["status"] == "approved"
assert db.get(models.Project, project_id).status == "ended"
assert rejected["status"] == "rejected"
assert db.get(models.Project, project_id).status == "active"
```

Also assert an empty rejection comment raises 422 without changing request or project rows.

- [ ] **Step 2: Verify red.**

```powershell
python -m pytest tests/test_project_close_workflow_boundaries.py -q
```

Expected: review command functions absent.

- [ ] **Step 3: Implement and delegate review commands.**

Add `approve_close_request` and `reject_close_request` with keyword-only project/request IDs, the typed review payload, current user, DB session, and lifecycle writer.

Both commands authorize `A_REVIEW_CLOSE_REQUEST` before locking, then lock project/request and require the pending pair. Approval recomputes blockers, sets reviewer fields, logs `project_close_request_approve`, notifies all members, and moves to `PL.S_ENDED`. Rejection requires a nonempty comment, logs `project_close_request_reject`, notifies requester plus strict owners, and moves to `PL.S_ACTIVE`. Both commit exactly once and return the existing DTO. Router endpoints delegate with `_set_project_lifecycle`.

- [ ] **Step 4: Verify green and commit.**

```powershell
python -m pytest tests/test_project_close_workflow_boundaries.py tests/test_project_close_lifecycle_guards.py tests/test_project_close_request_blockers.py tests/test_project_permission_actions.py tests/test_full_role_lifecycle_audit.py -q
git add app/services/project_close_workflow.py app/routers/projects.py tests/test_project_close_workflow_boundaries.py
git diff --cached --check
git commit -m "refactor: move project close reviews to workflow service"
```

Expected: tests pass and staged diff is whitespace-clean.

### Task 4: Delivery gate and evidence

**Files:**

- Modify: `docs/superpowers/plans/2026-09-13-project-close-workflow-service-boundaries.md`

- [ ] **Step 1: Run focused governance tests.**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_close_workflow_boundaries.py tests/test_project_close_lifecycle_guards.py tests/test_project_close_request_blockers.py tests/test_project_permission_actions.py tests/test_full_role_lifecycle_audit.py -q
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

Expected: all commands pass. The independent dynamic `exceljs.min` chunk may retain its size warning.

- [ ] **Step 3: Record actual totals and commit.**

Check every completed step, replace this instruction with the actual focused/backend/frontend/build totals, then run:

```powershell
git add docs/superpowers/plans/2026-09-13-project-close-workflow-service-boundaries.md
git diff --cached --check
git commit -m "docs: record project close workflow verification"
```
