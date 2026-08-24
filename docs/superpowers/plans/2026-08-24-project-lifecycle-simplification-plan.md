# Project Lifecycle Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove dispatch and kickoff as mandatory lifecycle gates so every new project follows `create/configure → owner submit → coach approve → active`, while preserving permissions, execution records, close review, audit history, and legacy-state compatibility.

**Architecture:** Keep the canonical project lifecycle in the backend, but stop creating `dispatched` and `pending_kickoff` for new writes. Treat kickoff as an execution event that can create an audited kickoff meeting and write back approved proposals without changing the project lifecycle. Make the frontend derive todos and actions from the simplified lifecycle, while rendering legacy `dispatched` and `pending_kickoff` rows through compatibility mappings.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite/PostgreSQL-compatible models, React 19, TypeScript, Vitest, pytest.

---

## File Map

### Backend

- Create: `bowei_ai_dashboard/tests/test_project_lifecycle_simplification.py` — focused lifecycle, notification, approval, and compatibility tests.
- Modify: `bowei_ai_dashboard/app/domain/project_lifecycle.py` — canonical states and compatibility helpers.
- Modify: `bowei_ai_dashboard/app/routers/projects.py` — setup notification alias and direct approval to `active`.
- Modify: `bowei_ai_dashboard/app/routers/meetings.py` — allow kickoff and ordinary meetings for active projects.
- Modify: `bowei_ai_dashboard/app/services/kickoff_writeback.py` — make kickoff writeback an active-project event without a lifecycle transition.
- Modify: `bowei_ai_dashboard/tests/test_kickoff_agent_model.py` — replace pending-kickoff gate assertions with active-project event assertions.
- Modify: `bowei_ai_dashboard/tests/test_kickoff_writeback.py` — cover active-project kickoff confirmation and unchanged lifecycle.

### Frontend

- Modify: `frontend/src/domain/projectLifecycleStatus.ts` — add `pending_kickoff` compatibility normalization and remove it from new-state assumptions.
- Modify: `frontend/src/features/settings/projectsWorkbench.ts` — expose owner todo in `draft`, map legacy statuses, and keep coach review role-specific.
- Modify: `frontend/src/features/settings/ProjectsMgmtSection.tsx` — remove dispatch as a primary action and send owner notification after team setup.
- Modify: `frontend/src/pages/ProjectDetailPage.tsx` — remove the detail-page dispatch flow and keep role-appropriate next actions.
- Modify: `frontend/src/pages/MeetingPage.tsx` — treat kickoff as an optional active-project event instead of a pending-kickoff-only gate.
- Modify: `frontend/src/features/meeting/KickoffAgentWorkspace.tsx` — update copy and post-confirm behavior so confirmation records an event while project status stays `active`.
- Modify: `frontend/src/api/projects.ts` — retain the dispatch API only as a deprecated compatibility alias; do not use it from new UI code.
- Modify: `frontend/src/api/meetings.ts` — keep kickoff API types and refresh behavior aligned with the active-project event.
- Modify: `frontend/tests/projectDetailDispatch.test.mjs` — replace dispatch-button contracts with the no-dispatch UI contract.
- Modify: `frontend/src/features/settings/projectsWorkbench.test.ts` — cover new todo/status mappings.
- Modify: `frontend/src/pages/MeetingPage.test.ts` — cover active-project kickoff/ordinary-meeting rendering.
- Modify: `frontend/tests/kickoffAgentStructure.test.mjs` — update the kickoff workspace contract from pending-kickoff routing to active-project event routing.
- Modify: `frontend/tests/meetingCreationPageLayout.test.mjs` — preserve page-level meeting-workbench contracts after removing the pending-kickoff editor guard.

### Documentation

- Reference: `docs/superpowers/specs/2026-08-24-project-lifecycle-simplification-design.md` — approved behavior and acceptance criteria.

## Task 1: Add failing backend lifecycle tests

**Files:**

- Create: `bowei_ai_dashboard/tests/test_project_lifecycle_simplification.py`
- Modify: `bowei_ai_dashboard/tests/test_kickoff_agent_model.py`
- Modify: `bowei_ai_dashboard/tests/test_kickoff_writeback.py`

- [ ] **Step 1: Create a minimal in-memory project fixture.**

The fixture must create a project, an active account for a project owner, an active account for a project coach, and `project_members` rows for `owner` and `project_ceo`. Add a separate company CEO account with `system_role="company_ceo"` and a super-admin account with `is_tech_admin=True` so tests can distinguish company-level and project-level permissions.

- [ ] **Step 2: Write the direct-approval failing test.**

Add a test with `Project(status="pending_review")` and a project-coach account that calls:

```python
result = projects.approve_project(1, current_user="coach", db=db)
assert result["status"] == "active"
assert db.get(models.Project, 1).status == "active"
assert db.get(models.Project, 1).is_active is True
```

The test must fail against the current implementation because it currently writes `pending_kickoff`.

- [ ] **Step 3: Write the notification-alias failing test.**

Call `projects.dispatch_project(1, current_user="company_ceo", db=db)` for a `draft` project with both required project roles. Assert that the response reports the owner recipient count, the project remains `draft`, and a project-dispatch notification is created. This defines dispatch as a notification event rather than a lifecycle transition.

- [ ] **Step 4: Write the legacy-state compatibility tests.**

Cover these exact cases:

```python
assert PL.is_execution_available("active") is True
assert PL.is_execution_available("pending_kickoff") is True
assert PL.is_owner_plan_editable("draft") is True
assert PL.is_owner_plan_editable("dispatched") is True
assert PL.is_owner_plan_editable("returned") is True
```

Add a test that an existing `pending_kickoff` project can create an ordinary meeting and write an execution schedule, proving old rows are not stranded.

- [ ] **Step 5: Update kickoff tests to express the new contract.**

Change `test_project_approval_enters_pending_kickoff_without_starting_project` into a test that asserts approval enters `active`. Change the structural-write test to assert that an `active` project permits execution writes, and add a separate compatibility test showing legacy `pending_kickoff` is also treated as execution-available.

- [ ] **Step 6: Run the focused tests and confirm they fail for the expected old behavior.**

Run:

```powershell
.\bowei_ai_dashboard\.venv\Scripts\python.exe -m pytest `
  bowei_ai_dashboard/tests/test_project_lifecycle_simplification.py `
  bowei_ai_dashboard/tests/test_kickoff_agent_model.py `
  bowei_ai_dashboard/tests/test_kickoff_writeback.py -q
```

Expected: failures identify the old `pending_kickoff` transition and pending-kickoff-only kickoff guards; no unrelated import or fixture failures.

- [ ] **Step 7: Commit the failing tests.**

```powershell
git add bowei_ai_dashboard/tests/test_project_lifecycle_simplification.py bowei_ai_dashboard/tests/test_kickoff_agent_model.py bowei_ai_dashboard/tests/test_kickoff_writeback.py
git commit -m "test: define simplified project lifecycle"
```

## Task 2: Implement backend lifecycle and compatibility helpers

**Files:**

- Modify: `bowei_ai_dashboard/app/domain/project_lifecycle.py`
- Modify: `bowei_ai_dashboard/app/routers/projects.py`
- Modify: `bowei_ai_dashboard/app/services/project_close.py`
- Test: `bowei_ai_dashboard/tests/test_project_lifecycle_simplification.py`

- [ ] **Step 1: Add explicit compatibility helpers to `project_lifecycle.py`.**

Add helpers with these exact semantics:

```python
def is_execution_available(value: object) -> bool:
    return normalize(value) in {S_ACTIVE, S_PENDING_KICKOFF}

def is_owner_plan_editable(value: object) -> bool:
    return normalize(value) in {S_DRAFT, S_DISPATCHED, S_RETURNED}
```

Keep `S_DISPATCHED` and `S_PENDING_KICKOFF` in `ALL_STATUSES` for old rows and audit compatibility. Do not include either state in new-state transition helpers.

- [ ] **Step 2: Change `dispatch_project` into an idempotent notification alias.**

Keep the existing permission and required-role checks. Remove the `_set_project_lifecycle(project, "dispatched", ...)` call. Permit the alias for `draft` and legacy `dispatched`; for `active`, `pending_close`, `ended`, and `archived`, return the existing lifecycle conflict. Send the owner notification, write an audit event named `project_owner_notified`, commit, and return `{ "ok": True, "dispatched_to": len(recipient_ids) }`.

- [ ] **Step 3: Change `approve_project` to write `active` directly.**

Replace the `PL.S_PENDING_KICKOFF` write with `PL.S_ACTIVE`. Set `is_active=True` and `lifecycle_status="active"` through `_set_project_lifecycle`. Leave `kickoff_date` and `kickoff_by` empty until the kickoff event is confirmed. Keep the project-coach permission check, profile persistence, notification, and audit log. The audit after-state must report `active`.

- [ ] **Step 4: Make owner submission use the shared helper.**

Replace ad-hoc lifecycle comparisons in `owner_submit_project_profile` with `PL.is_owner_plan_editable(lifecycle)`. Continue rejecting `pending_review`, close-frozen states, ended, and archived projects. Preserve all existing work-progress validation and atomicity.

- [ ] **Step 5: Make business writes compatible with old pending-kickoff rows.**

Keep `require_project_business_writable` responsible only for archived/close-frozen protection. Update task/subtask execution guards that currently reject `pending_kickoff` so they call `PL.is_execution_available(project.status)` and permit both `active` and legacy `pending_kickoff`.

- [ ] **Step 6: Run the focused backend tests.**

Run the command from Task 1 Step 6. Expected: all lifecycle, kickoff, and compatibility tests pass.

- [ ] **Step 7: Commit the backend lifecycle changes.**

```powershell
git add bowei_ai_dashboard/app/domain/project_lifecycle.py bowei_ai_dashboard/app/routers/projects.py bowei_ai_dashboard/app/services/project_close.py bowei_ai_dashboard/tests/test_project_lifecycle_simplification.py bowei_ai_dashboard/tests/test_kickoff_agent_model.py bowei_ai_dashboard/tests/test_kickoff_writeback.py
git commit -m "feat: simplify project lifecycle transitions"
```

## Task 3: Convert kickoff from a lifecycle gate into an active-project event

**Files:**

- Modify: `bowei_ai_dashboard/app/routers/meetings.py`
- Modify: `bowei_ai_dashboard/app/services/kickoff_writeback.py`
- Modify: `bowei_ai_dashboard/tests/test_kickoff_writeback.py`
- Modify: `bowei_ai_dashboard/tests/test_kickoff_agent_model.py`

- [ ] **Step 1: Change kickoff-run creation to require execution availability.**

In `create_kickoff_run`, replace `project.status != "pending_kickoff"` with `not PL.is_execution_available(project.status)`. Keep owner authorization and snapshot generation. A new kickoff run must be allowed for `active` and legacy `pending_kickoff` projects.

- [ ] **Step 2: Remove ordinary-meeting blocking for pending kickoff.**

In `create_meeting`, delete the `pending_kickoff` rejection. Keep `require_project_business_writable`, archive protection, and project-role authorization. Ordinary meetings and kickoff events must coexist while the project is active.

- [ ] **Step 3: Make kickoff confirmation preserve `active`.**

In `confirm_kickoff_start`, require `PL.is_execution_available(project.status)`. Apply approved proposals, create the published kickoff meeting, set `kickoff_date` and `kickoff_by`, mark the run approved, and leave the project status as `active` with `is_active=True`. The function must not call a lifecycle transition to `active` because the project is already executing.

- [ ] **Step 4: Preserve atomic rollback behavior.**

Keep proposal validation and meeting creation in the same transaction. If proposal validation, writeback, or meeting creation raises, the project status, kickoff run, proposals, and execution records must remain unchanged after the router rolls back.

- [ ] **Step 5: Run kickoff and meeting tests.**

Run:

```powershell
.\bowei_ai_dashboard\.venv\Scripts\python.exe -m pytest `
  bowei_ai_dashboard/tests/test_kickoff_agent_model.py `
  bowei_ai_dashboard/tests/test_kickoff_writeback.py `
  bowei_ai_dashboard/tests/test_project_meeting_review_writeback.py -q
```

Expected: kickoff confirmation creates the kickoff meeting without moving the project through `pending_kickoff`; legacy pending-kickoff rows remain usable.

- [ ] **Step 6: Commit the kickoff event changes.**

```powershell
git add bowei_ai_dashboard/app/routers/meetings.py bowei_ai_dashboard/app/services/kickoff_writeback.py bowei_ai_dashboard/tests/test_kickoff_agent_model.py bowei_ai_dashboard/tests/test_kickoff_writeback.py
git commit -m "feat: make kickoff an execution event"
```

## Task 4: Update frontend lifecycle and todo mappings

**Files:**

- Modify: `frontend/src/domain/projectLifecycleStatus.ts`
- Modify: `frontend/src/features/settings/projectsWorkbench.ts`
- Modify: `frontend/src/features/settings/projectsWorkbench.test.ts`

- [ ] **Step 1: Add frontend compatibility normalization.**

Keep `pending_kickoff` in the type union so old API rows type-check, but make `getProjectPrimaryStatus` and `getProjectStatusBadge` expose it as an execution-compatible status. New UI labels must not present it as a required startup gate.

- [ ] **Step 2: Update workbench status labels and stage mapping.**

Remove `dispatched` from the new lifecycle counts and map it to the owner-completion planning bucket. Count `draft`, legacy `dispatched`, and `returned` in the planning/to-complete bucket so a newly configured owner task is visible immediately. Map `pending_kickoff` to the execution stage for display and todo decisions. Keep `pending_close`, `ended`, and `archived` unchanged.

- [ ] **Step 3: Update `getProjectTodo`.**

Change the owner condition from only `status === 'dispatched'` to `status === 'draft' || status === 'dispatched'`, while preserving the company-manager `edit` todo and the `returned` owner todo. Keep `pending_review` review todo restricted to `isRealProjectCeo || isSuperAdmin`. Update the detail-panel action model so a project owner opening a `draft` project sees `完善立项信息`; the company CEO/super admin still sees `编辑项目` for team setup.

- [ ] **Step 4: Update unit tests before implementation completion.**

Add assertions that:

```ts
expect(getProjectTodo(project('draft'), ownerRoles)).toMatchObject({ action: 'ownerSubmit' })
expect(getProjectTodo(project('dispatched'), ownerRoles)).toMatchObject({ action: 'ownerSubmit' })
expect(getProjectLifecycleStage('pending_kickoff')).toMatchObject({ key: 'execution' })
```

Remove the expectation that a draft owner has no todo. Keep tests proving a company CEO sees setup editing and a project coach sees review only when the project is `pending_review`.

- [ ] **Step 5: Run frontend workbench tests.**

Run from `frontend`:

```powershell
npm run test:unit -- src/features/settings/projectsWorkbench.test.ts
```

Expected: PASS with the simplified owner and legacy-state mappings.

- [ ] **Step 6: Commit the frontend domain changes.**

```powershell
git add frontend/src/domain/projectLifecycleStatus.ts frontend/src/features/settings/projectsWorkbench.ts frontend/src/features/settings/projectsWorkbench.test.ts
git commit -m "feat: map todos to simplified project lifecycle"
```

## Task 5: Remove dispatch from project-management UI and wire owner notification

**Files:**

- Modify: `frontend/src/features/settings/ProjectsMgmtSection.tsx`
- Modify: `frontend/src/pages/ProjectDetailPage.tsx`
- Modify: `frontend/src/api/projects.ts`
- Modify: `frontend/tests/projectDetailDispatch.test.mjs`
- Modify: `bowei_ai_dashboard/tests/test_projects_management_lifecycle_workbench_frontend.py`

- [ ] **Step 1: Add a focused frontend contract test for the new action surface.**

Replace dispatch-specific assertions with these contracts:

```js
assert.doesNotMatch(sectionSource, /下发给负责人/)
assert.doesNotMatch(detailSource, /dispatchProject/)
assert.match(sectionSource, /ownerSubmit/)
assert.match(sectionSource, /project_owner_notified|负责人/)
```

Keep a backend-facing test for the deprecated API alias in the Python suite; the new frontend must not call it.

- [ ] **Step 2: Remove dispatch state and handlers from `ProjectsMgmtSection.tsx`.**

Delete `dispatchingId`, `handleDispatch`, `dispatchProject` imports, and `MainAction.type === 'dispatch'` branches. Change the draft owner action to navigate to the owner-submit workspace. Keep project setup editing for company CEO/super admin. Update the draft-card and list-row main-action code paths together so neither layout can render a dispatch action.

- [ ] **Step 3: Trigger notification after team configuration is saved.**

After `syncProjectMembers` returns successfully from `handleSaveProjectEdit`, call a new API function named `notifyProjectOwner(projectId)` that posts to the compatibility endpoint. Show `项目已保存，已通知负责人` on success. If notification fails after member save, show `项目已保存，但负责人通知失败，请稍后重试` and do not roll back the saved project/team data.

- [ ] **Step 4: Update the detail page action surface.**

Remove `dispatchProject`, `createProjectDetailDispatcher`, `dispatching`, `handleDispatch`, and `onDispatch` from `ProjectDetailPage.tsx` and `DetailPanel`. The draft detail page must show only setup editing for company CEO/super admin and owner plan completion for the project owner.

- [ ] **Step 5: Keep the API alias explicit.**

In `frontend/src/api/projects.ts`, rename the compatibility wrapper to `notifyProjectOwner(projectId)` while retaining the same POST path and response type. Do not expose a `dispatchProject` symbol to new callers.

- [ ] **Step 6: Run project-management frontend contracts.**

Run from `frontend`:

```powershell
node --test tests/projectDetailDispatch.test.mjs
npm run test:unit -- src/features/settings/projectsWorkbench.test.ts
```

Expected: no dispatch button or dispatch handler remains in the new UI, and owner todo/action routing works from `draft`.

- [ ] **Step 7: Commit the project-management UI changes.**

```powershell
git add frontend/src/features/settings/ProjectsMgmtSection.tsx frontend/src/pages/ProjectDetailPage.tsx frontend/src/api/projects.ts frontend/tests/projectDetailDispatch.test.mjs bowei_ai_dashboard/tests/test_projects_management_lifecycle_workbench_frontend.py
git commit -m "feat: remove dispatch gate from project management UI"
```

## Task 6: Update meeting UI to expose kickoff as an active-project event

**Files:**

- Modify: `frontend/src/pages/MeetingPage.tsx`
- Modify: `frontend/src/features/meeting/KickoffAgentWorkspace.tsx`
- Modify: `frontend/src/api/meetings.ts`
- Modify: `frontend/src/pages/MeetingPage.test.ts`
- Modify: `frontend/tests/kickoffAgentStructure.test.mjs`
- Modify: `frontend/tests/meetingCreationPageLayout.test.mjs`

- [ ] **Step 1: Add the active-project kickoff entry point.**

Replace `pending_kickoff` as the only condition for rendering `KickoffAgentWorkspace` with an explicit kickoff action available for active projects. Keep ordinary “新建会议纪要” available at the same time. The kickoff action must be disabled only for archived, ended, or close-frozen projects.

- [ ] **Step 2: Keep the kickoff event auditable.**

Continue using `createKickoffRun`, `submitKickoffRun`, proposal review, and `confirmKickoffStart`. Update labels from “项目待启动会确认” to “启动会执行基线” or equivalent wording that does not imply the project is blocked before kickoff.

- [ ] **Step 3: Refresh the project after kickoff confirmation.**

After `confirmKickoffStart` succeeds, close the workspace, refetch the project/meeting list, and show the published kickoff meeting. Do not expect a status transition; the status must remain `active`.

- [ ] **Step 4: Update meeting tests.**

Add source-level assertions that ordinary meeting creation is not guarded by `pending_kickoff`, that the kickoff workspace can be opened for an active project, and that the button labels no longer claim the project must be started by kickoff confirmation. Update `frontend/tests/kickoffAgentStructure.test.mjs` to assert the kickoff API/review controls remain present without requiring a pending-kickoff status, and update `frontend/tests/meetingCreationPageLayout.test.mjs` so it checks the page-level editor contract without asserting the removed `!pending_kickoff` guard.

- [ ] **Step 5: Run meeting tests and build.**

Run from `frontend`:

```powershell
npm run test:unit -- src/pages/MeetingPage.test.ts
npm run build
```

Expected: PASS and a successful TypeScript/Vite production build.

- [ ] **Step 6: Commit the meeting UI changes.**

```powershell
git add frontend/src/pages/MeetingPage.tsx frontend/src/features/meeting/KickoffAgentWorkspace.tsx frontend/src/api/meetings.ts frontend/src/pages/MeetingPage.test.ts frontend/tests/kickoffAgentStructure.test.mjs frontend/tests/meetingCreationPageLayout.test.mjs
git commit -m "feat: make kickoff an optional active-project event"
```

## Task 7: Verify migration behavior and full workflow

**Files:**

- Modify: `bowei_ai_dashboard/tests/test_project_close_lifecycle_guards.py` only if existing frozen-state assertions need the new compatibility helper.
- Modify: `frontend/src/domain/projectLifecycleStatus.ts` only if full-flow type checks identify a missing legacy mapping.

- [ ] **Step 1: Run the full backend test suite.**

Run:

```powershell
.\bowei_ai_dashboard\.venv\Scripts\python.exe -m pytest bowei_ai_dashboard/tests -q
```

Expected: all tests pass, including close-flow, permission, kickoff, meeting, confirmation, and project-management suites.

- [ ] **Step 2: Run the full frontend unit suite and production build.**

Run from `frontend`:

```powershell
npm run test:unit
npm run build
```

Expected: all unit tests pass and the build completes without TypeScript errors.

- [ ] **Step 3: Perform a read-only legacy-state audit.**

Use a read-only database query to list projects with `status IN ('dispatched', 'pending_kickoff')`. Verify each legacy row has a compatible owner/coach role and that the frontend mapping renders it as owner-plan or execution work rather than a dead-end state. Do not mutate production or the shared local database during this audit.

- [ ] **Step 4: Verify the new end-to-end acceptance path.**

With a fresh test project, verify:

```text
create/configure team
→ owner notification
→ owner submits plan
→ project coach approves
→ status active
→ kickoff event optionally confirmed
→ ordinary meeting/report/task writes available
→ close request
→ coach close approval
→ super-admin archive
```

Confirm that the project never enters `dispatched` or `pending_kickoff` during this path and that audit records exist for setup, notification, submission, approval, kickoff event, close, and archive.

- [ ] **Step 5: Commit final verification updates.**

```powershell
git add bowei_ai_dashboard/tests/test_project_close_lifecycle_guards.py frontend/src/domain/projectLifecycleStatus.ts
git commit -m "test: verify simplified project lifecycle end to end"
```
