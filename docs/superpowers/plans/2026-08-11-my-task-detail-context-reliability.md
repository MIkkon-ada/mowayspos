# My Task Detail Context Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make a task opened from 我的任务 retain its project and workstream context, request detail within that scope, and show an actionable failure instead of falsely calling it unassociated.

**Architecture:** The list keeps projectId in the URL and passes known labels through React Router state. The client sends an optional project_id with the task-detail request. The backend resolves the task parent project itself, rejects a conflicting scope as 404, then uses existing access checks. The detail page only uses list context until canonical server data loads and shows the real API failure plus retry.

**Tech Stack:** React 18, TypeScript, React Router, Vite, FastAPI, SQLAlchemy, pytest, Node test runner.

---

## File Structure

- frontend/src/api/subtasks.ts — builds scoped task-detail API URL.
- frontend/src/pages/MyTasksPage.tsx — sends row context to task-detail route.
- frontend/src/pages/MyTaskDetailPage.tsx — loads scoped details and renders accurate pending/error labels.
- frontend/tests/myTasksPageStructure.test.mjs — covers route, request, and failure UI contracts.
- bowei_ai_dashboard/app/routers/subtasks.py — validates scope before authorization.
- bowei_ai_dashboard/tests/test_execution_submission_to_work_progress_flow.py — proves matching scope works and a mismatch is rejected.

### Task 1: Define and enforce backend detail scope

**Files:**
- Modify: bowei_ai_dashboard/app/routers/subtasks.py — get_subtask_detail
- Modify: bowei_ai_dashboard/tests/test_execution_submission_to_work_progress_flow.py — next to existing subtask detail test

- [ ] **Step 1: Write failing tests for matching and conflicting project scopes**

Add FastAPI HTTPException import and these tests:

~~~python
def test_flow3_subtask_detail_accepts_its_parent_project_scope():
    db = _make_session()
    team = _seed_execution_team(db)

    detail = get_subtask_detail(
        team["subtask"].id,
        project_id=team["project"].id,
        current_user="owner",
        db=db,
    )

    assert detail["id"] == team["subtask"].id
    assert detail["parent_task"]["special_project"] == team["project"].name


def test_flow3_subtask_detail_rejects_a_conflicting_project_scope():
    db = _make_session()
    team = _seed_execution_team(db)

    with pytest.raises(HTTPException) as exc_info:
        get_subtask_detail(
            team["subtask"].id,
            project_id=team["project"].id + 1,
            current_user="owner",
            db=db,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "subtask not found"
~~~

- [ ] **Step 2: Run the failing tests**

Run: pytest bowei_ai_dashboard/tests/test_execution_submission_to_work_progress_flow.py -k "subtask_detail_accepts_its_parent_project_scope or subtask_detail_rejects_a_conflicting_project_scope" -v

Expected: FAIL because get_subtask_detail does not accept project_id.

- [ ] **Step 3: Implement scope parsing and mismatch rejection**

Change the endpoint signature to receive a FastAPI query parameter:

~~~python
@router.get("/api/subtasks/{row_id}/detail")
def get_subtask_detail(
    row_id: int,
    project_id: int | None = Query(default=None),
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
~~~

Within the current parent-task block, derive ownership from the database and reject a conflict before access control:

~~~python
parent = db.get(models.Task, row.task_id)
if parent:
    resolved_project_id = _get_task_project_id(parent, db)
    if project_id is not None and resolved_project_id != project_id:
        raise HTTPException(status_code=404, detail="subtask not found")
    if resolved_project_id is not None:
        require_project_access(current_user, resolved_project_id, db)
    elif not context.is_tech_admin and not context.is_company_ceo:
        raise HTTPException(status_code=403, detail="project context required")
~~~

Keep the existing result parent_task construction unchanged.

- [ ] **Step 4: Run all detail endpoint regression tests**

Run: pytest bowei_ai_dashboard/tests/test_execution_submission_to_work_progress_flow.py -k "subtask_detail" -v

Expected: PASS, including existing source submission/result fields and both new scope tests.

- [ ] **Step 5: Commit backend contract**

~~~powershell
git add bowei_ai_dashboard/app/routers/subtasks.py bowei_ai_dashboard/tests/test_execution_submission_to_work_progress_flow.py
git commit -m "fix: scope task detail requests to project"
~~~

### Task 2: Send scope and retain context in frontend navigation

**Files:**
- Modify: frontend/src/api/subtasks.ts — fetchSubtaskDetail
- Modify: frontend/src/pages/MyTasksPage.tsx — openDetail
- Modify: frontend/tests/myTasksPageStructure.test.mjs — my-task navigation assertions

- [ ] **Step 1: Add failing source-contract tests**

~~~js
assert.match(subtasksSource, /fetchSubtaskDetail\(id: number, projectId\?: number \| null\)/)
assert.match(subtasksSource, /params\.set\('project_id', String\(projectId\)\)/)
assert.match(myTasksPageSource, /state:\s*\{[\s\S]*projectName: row\.projectName[\s\S]*workstreamName: row\.workstreamName/)
~~~

- [ ] **Step 2: Run frontend test and confirm failure**

Run: node --test frontend/tests/myTasksPageStructure.test.mjs

Expected: FAIL because the helper only takes id and navigation has no route state.

- [ ] **Step 3: Implement scoped API URL and route state**

Implement the helper without a trailing question mark:

~~~ts
export function fetchSubtaskDetail(id: number, projectId?: number | null): Promise<SubTaskDetail> {
  const params = new URLSearchParams()
  if (projectId != null) params.set('project_id', String(projectId))
  const query = params.size ? '?' + params.toString() : ''
  return apiGet<SubTaskDetail>('/api/subtasks/' + id + '/detail' + query)
}
~~~

Retain the current URL in openDetail, then pass fallback labels:

~~~ts
navigate(detailUrl, {
  state: {
    projectId: row.projectId,
    projectName: row.projectName,
    workstreamName: row.workstreamName,
  },
})
~~~

- [ ] **Step 4: Run frontend route/request regression**

Run: node --test frontend/tests/myTasksPageStructure.test.mjs

Expected: PASS.

- [ ] **Step 5: Commit client context work**

~~~powershell
git add frontend/src/api/subtasks.ts frontend/src/pages/MyTasksPage.tsx frontend/tests/myTasksPageStructure.test.mjs
git commit -m "fix: preserve my task detail context"
~~~

### Task 3: Render truthful failure state and reload action

**Files:**
- Modify: frontend/src/pages/MyTaskDetailPage.tsx
- Modify: frontend/tests/myTasksPageStructure.test.mjs

- [ ] **Step 1: Add failing assertions for context, diagnostic, and retry behavior**

~~~js
assert.match(myTaskDetailSource, /useLocation/)
assert.match(myTaskDetailSource, /fetchSubtaskDetail\(taskId, scopedProjectId\)/)
assert.match(myTaskDetailSource, /error instanceof ApiError/)
assert.match(myTaskDetailSource, /重新加载/)
assert.doesNotMatch(myTaskDetailSource, /'未关联项目'/)
assert.doesNotMatch(myTaskDetailSource, /'未关联重点工作'/)
~~~

- [ ] **Step 2: Run test and confirm current page is misleading**

Run: node --test frontend/tests/myTasksPageStructure.test.mjs

Expected: FAIL because the component renders generic error text and unassociated fallbacks.

- [ ] **Step 3: Implement typed route state, scoped loading, diagnostic mapping, and retry**

Import useLocation and ApiError. Add these definitions:

~~~ts
type MyTaskDetailRouteState = {
  projectId?: number | null
  projectName?: string
  workstreamName?: string
}

function getDetailErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403) return '你没有查看该任务详情的权限，请返回列表后刷新任务。'
    if (error.status === 404) return '该任务不存在、已删除，或不属于当前项目。'
    return error.message || '任务详情加载失败，请稍后重试。'
  }
  return '任务详情加载失败，请检查网络后重试。'
}
~~~

Read location.state as MyTaskDetailRouteState or null. Prefer valid numeric URL projectId, otherwise numeric route-state projectId, and call fetchSubtaskDetail(taskId, scopedProjectId). Add reloadToken to the effect dependencies and make a reload callback increment it.

Set labels in this precedence order:

~~~ts
const projectName = fallback(
  detail?.parent_task?.special_project,
  routeState?.projectName || (loading ? '正在读取项目归属' : '项目归属暂不可用'),
)
const workstreamName = fallback(
  detail?.parent_task?.key_task,
  routeState?.workstreamName || (loading ? '正在读取重点工作' : '重点工作暂不可用'),
)
~~~

Server values remain authoritative after success. The error panel must show mapped error text, retain 返回列表, and add a visible 重新加载 button. Do not render 未关联项目 or 未关联重点工作 unless the API explicitly reports a successful unassociated record in the future.

- [ ] **Step 4: Run frontend regression and focused TypeScript validation**

Run: node --test frontend/tests/myTasksPageStructure.test.mjs

Expected: PASS.

Run: npx tsc --noEmit --jsx react-jsx --target ES2022 --module ESNext --moduleResolution bundler --skipLibCheck src/pages/MyTaskDetailPage.tsx src/pages/MyTasksPage.tsx src/api/subtasks.ts

Expected: PASS with no diagnostics from changed files.

- [ ] **Step 5: Commit accurate failure UI**

~~~powershell
git add frontend/src/pages/MyTaskDetailPage.tsx frontend/tests/myTasksPageStructure.test.mjs
git commit -m "fix: show actionable task detail failures"
~~~

### Task 4: Verify without editing unrelated meeting work

**Files:**
- Modify: none

- [ ] **Step 1: Run focused backend regression**

Run: pytest bowei_ai_dashboard/tests/test_execution_submission_to_work_progress_flow.py -k "subtask_detail" -v

Expected: PASS.

- [ ] **Step 2: Run focused frontend regression**

Run: node --test frontend/tests/myTasksPageStructure.test.mjs

Expected: PASS.

- [ ] **Step 3: Run targeted TypeScript validation**

Run: npx tsc --noEmit --jsx react-jsx --target ES2022 --module ESNext --moduleResolution bundler --skipLibCheck src/pages/MyTaskDetailPage.tsx src/pages/MyTasksPage.tsx src/api/subtasks.ts

Expected: PASS.

- [ ] **Step 4: Attempt full production build and isolate existing blocker**

Run: npm run build

Expected: detail repair causes no errors. If existing frontend/src/pages/MeetingPage.tsx diagnostics still fail, record them as unrelated and do not modify that file.

- [ ] **Step 5: Check final scope and whitespace**

Run: git status --short; git diff --check; git log --oneline -3

Expected: no whitespace errors; do not stage or alter dirty files outside this plan.

