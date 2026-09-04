# 删除工作推进表执行视角 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除工作推进表的执行概览视图和入口，同时保留计划表、关键任务执行详情及现有操作能力。

**Architecture:** `TaskManagementPage` 只保留计划表作为主视图；关键任务详情由 `selectedSubTask` 直接驱动，不再借助 `viewMode='execution'`。执行概览组件及其专属预加载逻辑删除，现有操作区和回收站数据路径迁移到无视图模式依赖的页面状态中。

**Tech Stack:** React 19, TypeScript, Vite, Vitest/Node structure tests, Tailwind CSS, existing FastAPI APIs.

---

## 文件变更地图

- Modify: `frontend/src/pages/TaskManagementPage.tsx` — 移除执行概览模式状态/分支，保留计划表与关键任务详情，迁移操作入口和回收站渲染路径。
- Delete: `frontend/src/components/task-management/ExecutionProgressView.tsx` — 删除工作推进表的重点工作执行概览组件。
- Modify: `frontend/tests/workProgressExcelView.test.mjs` — 改为验证仅有计划表视图、详情仍可进入、操作入口仍存在。
- Modify: `frontend/tests/keyTaskExecutionWorkspace.test.mjs` — 去除对执行概览模式开关的断言，保留共享执行工作台和计划表入口断言。
- Modify: `frontend/tests/keyTaskExecutionDetailLayout.test.mjs` — 更新关键任务详情分支断言，不再要求 `viewMode === 'execution'`。
- Modify: `bowei_ai_dashboard/tests/test_work_progress_plan_table_frontend.py` — 调整页面结构断言，不再把 `viewMode` 作为计划表能力的必要条件。
- Modify: `docs/full-flow-manual-acceptance-checklist.md` — 删除执行视图验收项，改为计划表和关键任务执行详情验收项。

### Task 1: 先更新执行视角移除的回归测试

**Files:**
- Modify: `frontend/tests/workProgressExcelView.test.mjs:90-100,385-390`
- Modify: `frontend/tests/keyTaskExecutionWorkspace.test.mjs:1-25`
- Modify: `frontend/tests/keyTaskExecutionDetailLayout.test.mjs:1-18`
- Modify: `bowei_ai_dashboard/tests/test_work_progress_plan_table_frontend.py:8-12`

- [ ] **Step 1: Rewrite the work-progress mode test to describe the new contract.**

Replace assertions that require `useState<'execution' | 'plan'>`, `SHOW_EXECUTION_DETAIL`, `ExecutionProgressView`, or the execution-mode condition with assertions equivalent to:

```js
test('work progress keeps only the plan table while key-task detail remains available', () => {
  const source = read(PAGE_FILE)
  assert.doesNotMatch(source, /ExecutionProgressView/)
  assert.doesNotMatch(source, /执行详情/)
  assert.match(source, /<PlanTableViewV2[\s\S]*?onOpenSubTask=\{openSubDetail\}/)
  assert.match(source, /<KeyTaskExecutionDetailView/)
  assert.match(source, /selectedSubTask \? \(/)
  assert.match(source, /fetchSubtaskDetail\(st\.id\)/)
})
```

The header test must assert that `工作推进表` and the plan-table search/filters remain while the `执行详情` label and mode switch do not exist.

- [ ] **Step 2: Update execution-workspace structure tests.**

In `frontend/tests/keyTaskExecutionWorkspace.test.mjs` and `frontend/tests/keyTaskExecutionDetailLayout.test.mjs`, keep assertions for `KeyTaskExecutionWorkspace`, `keyTaskId={subTask.id}`, and `PlanTableViewV2`/`onOpenSubTask`. Replace the old page assertion:

```js
assert.match(page, /viewMode === 'execution' && selectedSubTask/)
```

with:

```js
assert.match(page, /selectedSubTask \? \(/)
assert.doesNotMatch(page, /viewMode === ['"]execution['"]|SHOW_EXECUTION_DETAIL/)
```

Remove the test that reads `ExecutionProgressView.tsx`; the component is intentionally deleted.

- [ ] **Step 3: Adjust the Python structural test.**

Keep `PlanTableViewV2`, `ensurePlanTableSubTasksLoaded`, `fetchSubTasksBatch(missingIds, false)`, and `taskSubMap` in the required symbols. Remove `viewMode` from that list so the test checks plan-table data loading rather than the retired mode abstraction.

- [ ] **Step 4: Run the focused tests and verify they fail for the expected missing implementation.**

Run from `frontend`:

```powershell
node --test tests/workProgressExcelView.test.mjs tests/keyTaskExecutionWorkspace.test.mjs tests/keyTaskExecutionDetailLayout.test.mjs
```

Run from the repository root:

```powershell
python -m pytest bowei_ai_dashboard/tests/test_work_progress_plan_table_frontend.py -q
```

Expected: the new tests fail because the page still contains the execution mode and the deleted component has not yet been removed. No unrelated test failure should be introduced by the test-only change.

- [ ] **Step 5: Commit the test contract.**

```powershell
git add -- frontend/tests/workProgressExcelView.test.mjs frontend/tests/keyTaskExecutionWorkspace.test.mjs frontend/tests/keyTaskExecutionDetailLayout.test.mjs bowei_ai_dashboard/tests/test_work_progress_plan_table_frontend.py
git commit -m "test: define work progress plan-only view"
```

### Task 2: Remove the mode abstraction while preserving detail entry

**Files:**
- Modify: `frontend/src/pages/TaskManagementPage.tsx:18-19,132,254-255,504-524,571-582,958-1137,1345`

- [ ] **Step 1: Remove the retired overview import and mode state.**

Delete the `ExecutionProgressView` import, delete `SHOW_EXECUTION_DETAIL`, and remove:

```ts
const [viewMode, setViewMode] = useState<'execution' | 'plan'>('plan')
```

Keep `planTableLoading` and all plan-table data state.

- [ ] **Step 2: Remove execution-only data loading and detach subtask focus from the retired mode.**

Keep the existing plan preload effect, without a `viewMode\) guard:

```ts
useEffect(() => {
  ensurePlanTableSubTasksLoaded()
}, [tasks, planTableLoading, taskSubMap])
```

Delete the separate effect that checks `viewMode !== 'execution'` and calls `fetchSubTasksBatch`. Keep the project-member preload effect without the `viewMode !== 'plan'` guard:

```ts
useEffect(() => {
  if (!focusedProject) return
  ensureProjectMembersLoaded(focusedProject.id)
}, [focusedProject])
```

In `focusSubTask`, delete `if (SHOW_EXECUTION_DETAIL) setViewMode('execution')`; leave project-member loading, selection clearing, `subDetailLoading\), and `fetchSubtaskDetail` unchanged.

- [ ] **Step 3: Make the shared execution workbench depend only on selected subtask state.**

Change the top-level detail branch from:

```tsx
{SHOW_EXECUTION_DETAIL && viewMode === 'execution' && selectedSubTask ? (
```

to:

```tsx
{selectedSubTask ? (
```

Keep every `KeyTaskExecutionDetailView` prop and the `onBack={() => clearSelection()}` callback unchanged. Change the header visibility guard from `viewMode === 'execution' && selectedSubTask` to `selectedSubTask` so the full-screen detail layout remains the same.

- [ ] **Step 4: Remove the mode switch and execution overview render branch.**

Keep the `工作推进表` title, project/status/owner filters, and search input. Delete the segmented `表格视图 / 执行详情` buttons. Set the search placeholder permanently to `搜索重点工作、关键任务、责任人`.

Delete the `viewMode === 'execution'` action wrapper and the `ExecutionProgressView` branch. The main content should render the existing plan table on active records, with the existing mobile `MobileTaskList` and desktop `PlanTableViewV2` callbacks unchanged.

- [ ] **Step 5: Simplify the aside condition.**

Change:

```tsx
{viewMode !== 'execution' && (selectedSubTask || subDetailLoading) && <aside ...>
```

to:

```tsx
{(selectedSubTask || subDetailLoading) && <aside ...>
```

The top-level `selectedSubTask` branch prevents this aside from rendering at the same time as the full execution workbench. Do not alter its existing parent-task detail, edit, submit-progress, restore, or archive permission logic.

### Task 3: Preserve operations and recycle-bin behavior without execution mode

**Files:**
- Modify: `frontend/src/pages/TaskManagementPage.tsx:1029-1072,1090-1348`
- 
- [ ] **Step 1: Move the existing operation controls out of the retired mode condition.**

Render the current operation controls regardless of the removed view mode. Preserve these exact behaviors:

- `导出表格` continues to call `handleExport()`.
- `从大纲导入` remains gated by `canManageProjectWork\), `currentProjectId`, `!projectArchived`, and `!showDeleted`.
- `回收站` remains gated by `canManageTrash` and clears selection, expanded rows, search, status, and owner filters before setting `showDeleted=true`.
- `在办` continues to clear selection and set `showDeleted=false`.

Do not change backend calls, permission helpers, or project-context resolution.

- [ ] **Step 2: Route the main body explicitly between active plan data and deleted-record data.**

When `showDeleted` is false, render the existing mobile/desktop plan table path. When `showDeleted` is true, render the existing grouped legacy list path that exposes `handleRestoreTask` and the current deleted-row restore controls. Keep `fetchTasks(effectiveTaskProjectId, showDeleted)` as the source of truth.

The plan-table subtask preload must not block or alter the recycle-bin state. Gate the preload with `!showDeleted`, and clear `taskSubMap` in the existing enter/leave recycle-bin handlers so deleted-record data is not mixed with active plan data.

- [ ] **Step 3: Preserve plan-table key-task navigation.**

Verify both callbacks remain wired:

```tsx
<MobileTaskList ... onOpenSubTask={openSubDetail} />
<PlanTableViewV2 ... onOpenSubTask={openSubDetail} />
```

The selected task must load through `fetchSubtaskDetail`, show `KeyTaskExecutionDetailView`, and return to the same plan/recycle-bin state after `clearSelection()`.

- [ ] **Step 4: Run the focused regression tests.**

Run:

```powershell
cd frontend
node --test tests/workProgressExcelView.test.mjs tests/keyTaskExecutionWorkspace.test.mjs tests/keyTaskExecutionDetailLayout.test.mjs
cd ..
python -m pytest bowei_ai_dashboard/tests/test_work_progress_plan_table_frontend.py -q
```

Expected: PASS, including assertions that the execution overview is absent, the plan table remains, and the shared execution workbench remains reachable.

- [ ] **Step 5: Commit the page refactor.**

```powershell
git add -- frontend/src/pages/TaskManagementPage.tsx frontend/src/components/task-management/PlanTableViewV2.tsx
git commit -m "refactor: remove work progress execution overview"
```

### Task 4: Delete the retired component and update acceptance wording

**Files:**
- Delete: `frontend/src/components/task-management/ExecutionProgressView.tsx`
- Modify: `docs/full-flow-manual-acceptance-checklist.md:50-59`

- [ ] **Step 1: Delete the component after all imports and tests are removed.**

Confirm before deletion:

```powershell
rg -n "ExecutionProgressView|执行详情|SHOW_EXECUTION_DETAIL|viewMode === ['"]execution['"]" frontend/src frontend/tests bowei_ai_dashboard/tests
```

No work-progress mode button or overview import may remain. References to “关键任务执行详情” in retained workbench files are allowed.

- [ ] **Step 2: Update the manual acceptance checklist.**

Replace the “工作推进表 — 执行视图” section with checks that:

1. 工作推进表默认只显示计划表。
2. 不显示“执行详情”视图切换按钮。
3. 桌面端和移动端点击关键任务进入关键任务执行详情。
4. 关键任务执行详情中的计划、成果、问题和推进记录可见。

Keep the existing plan-table acceptance section and later work-progress recheck items.

- [ ] **Step 3: Verify no stale source references remain.**

Run:

```powershell
rg -n "ExecutionProgressView|SHOW_EXECUTION_DETAIL|setViewMode|viewMode === ['"]execution['"]" frontend/src frontend/tests bowei_ai_dashboard/tests docs
```

Expected: no source/test references to the removed overview or mode state. Historical design documents may mention the old behavior and should not be edited unless they are current acceptance instructions.

### Task 5: Full verification and final diff audit

**Files:**
- Verify all files changed by Tasks 1-4.

- [ ] **Step 1: Run all frontend unit/structure tests.**

From `frontend`:

```powershell
npm run test:unit
```

Expected: PASS with no failures caused by the work-progress view removal.

- [ ] **Step 2: Run the production build.**

From `frontend`:

```powershell
npm run build
```

Expected: TypeScript and Vite build complete successfully.

- [ ] **Step 3: Run relevant backend tests to prove the backend contract is unchanged.**

From the repository root:

```powershell
python -m pytest bowei_ai_dashboard/tests/test_execution_submission_to_work_progress_flow.py bowei_ai_dashboard/tests/test_work_progress_plan_table_frontend.py -q
```

Expected: PASS; no backend files or database migrations are changed.

- [ ] **Step 4: Inspect the final diff and preserve unrelated worktree changes.**

Run:

```powershell
git status --short
git diff --stat
git diff --check
```

Confirm the diff contains only the approved work-progress changes plus the committed design/plan documents. Do not stage or modify the pre-existing `CoordinatePage`, `coordinateCompanyProjectRole.test.mjs`, or `bowei_ai_dashboard/data/` changes.



