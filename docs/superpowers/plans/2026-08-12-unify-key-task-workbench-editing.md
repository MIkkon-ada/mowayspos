# Unified Key-Task Workbench Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the monthly-plan workbench the only key-task detail view, retaining all six base-task editing fields in a right-side drawer.

**Architecture:** `TaskManagementPage` owns selected task data and the existing update API call. `KeyTaskExecutionDetailView` renders the authorized edit action and drawer. `PlanTableViewV2` remains only a table and delegates row clicks to the shared workbench entry.

**Tech Stack:** React, TypeScript, Tailwind CSS, existing `/api/subtasks/{id}` endpoint, Node test runner, Vite.

---

### Task 1: Characterize the intended replacement

**Files:**
- Modify: `frontend/tests/keyTaskExecutionDetailLayout.test.mjs`

- [ ] **Step 1: Add failing assertions**

```js
assert.match(detail, /onEditSubTask/)
assert.match(detail, /编辑关键任务/)
assert.match(detail, /KeyTaskEditDrawer/)
for (const label of ['任务名称', '责任人', '协同人', '计划时间', '整体状态', '完成标准']) assert.match(detail, new RegExp(label))
assert.match(page, /onEditSubTask=\{handleWorkbenchSubTaskSave\}/)
assert.doesNotMatch(planTable, /function SubTaskEditModal/)
assert.doesNotMatch(planTable, /editingSubTaskDetail/)
```

- [ ] **Step 2: Verify red**

Run `node --test tests/keyTaskExecutionDetailLayout.test.mjs` and confirm the new assertions fail because no drawer exists and legacy modal code remains.

### Task 2: Migrate base-field editing to the workbench drawer

**Files:**
- Modify: `frontend/src/components/task-management/KeyTaskExecutionDetailView.tsx`

- [ ] **Step 1: Add the callback contract**

```tsx
onEditSubTask?: (payload: Omit<SubTaskPayload, 'project_id'>) => Promise<void>
```

- [ ] **Step 2: Implement `KeyTaskEditDrawer`**

The drawer keeps local state for title, assignee, collaborator, plan time, status, and completion criteria. It selects assignees from project members, submits the exact `SubTaskPayload` fields, stays open with an error on failure, and closes only after save resolves.

- [ ] **Step 3: Render `编辑关键任务` in the title card only for `canManageSchedules`**

```tsx
{canManageSchedules && <button type="button" onClick={() => setEditingBaseTask(true)}>编辑关键任务</button>}
```

### Task 3: Synchronize the parent workbench state

**Files:**
- Modify: `frontend/src/pages/TaskManagementPage.tsx`

- [ ] **Step 1: Write `handleWorkbenchSubTaskSave`**

It calls `updateSubTask` with the selected task id and project id, then replaces the matching row in both `selectedSubTask` and `taskSubMap`.

- [ ] **Step 2: Pass the callback to `KeyTaskExecutionDetailView`**

```tsx
onEditSubTask={handleWorkbenchSubTaskSave}
```

### Task 4: Delete the superseded table modal

**Files:**
- Modify: `frontend/src/components/task-management/PlanTableViewV2.tsx`
- Modify: `frontend/src/pages/TaskManagementPage.tsx`

- [ ] **Step 1: Remove `SubTaskEditModal`, its fetch/type imports, modal state, member-name construction, and `onUpdateSubTask` prop.**

- [ ] **Step 2: Retain the shared navigation behavior**

```tsx
const openKeyTask = (row: PlanTableRow) => {
  if (!row.subtask) return
  setSelectedSubTaskId(row.subtask.id)
  onOpenSubTask?.(row.subtask)
}
```

- [ ] **Step 3: Stop passing `onUpdateSubTask` from `TaskManagementPage`.**

### Task 5: Verify and commit

**Files:**
- Test: `frontend/tests/keyTaskExecutionDetailLayout.test.mjs`

- [ ] **Step 1: Run focused tests**

Run `node --test tests/keyTaskExecutionDetailLayout.test.mjs`; expected result: all tests pass.

- [ ] **Step 2: Build the frontend**

Run `npm run build`; expected result: TypeScript and Vite complete successfully.

- [ ] **Step 3: Browser verification**

Open `/work/tasks?projectId=1`, click a key-task row, then click `编辑关键任务`; confirm the monthly workbench remains behind a right-side drawer containing all six fields.

- [ ] **Step 4: Commit**

Run `git add frontend/src/components/task-management/KeyTaskExecutionDetailView.tsx frontend/src/components/task-management/PlanTableViewV2.tsx frontend/src/pages/TaskManagementPage.tsx frontend/tests/keyTaskExecutionDetailLayout.test.mjs && git commit -m "feat: unify key task editing in monthly workbench"`.
