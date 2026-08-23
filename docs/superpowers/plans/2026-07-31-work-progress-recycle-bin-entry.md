# Work Progress Recycle-Bin Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the existing work-progress recycle-bin entry into the execution view's “操作” menu while preserving soft-delete, restore, permissions, and audit behavior.

**Architecture:** Keep the existing `showDeleted` state, task APIs, and backend permission checks. Add focused enter/leave helpers in `TaskManagementPage.tsx`, render a recycle-bin title and explicit return action while deleted records are shown, and fail back to the active work view on a `403`. No backend, database, route, or migration changes are required.

**Tech Stack:** React 19, TypeScript, Vite, Node test runner, existing FastAPI APIs

---

## File Map

- Create `frontend/tests/workProgressRecycleBinEntry.test.mjs`: focused structural regression tests for entry placement, permissions, enter/leave behavior, and `403` fallback.
- Modify `frontend/src/pages/TaskManagementPage.tsx`: remove the peer toggle, add menu entry, add enter/leave helpers, identify the recycle-bin state, and preserve existing restore calls.
- Do not modify `frontend/src/api/tasks.ts`, `frontend/src/api/subtasks.ts`, backend routers, models, migrations, or the local database.

Before starting, preserve unrelated worktree changes. Stage and commit only the files named in each task.

### Task 1: Move the recycle-bin entry into the operation menu

**Files:**
- Create: `frontend/tests/workProgressRecycleBinEntry.test.mjs`
- Modify: `frontend/src/pages/TaskManagementPage.tsx:576`
- Modify: `frontend/src/pages/TaskManagementPage.tsx:925-1043`

- [ ] **Step 1: Write the failing entry and navigation tests**

Create `frontend/tests/workProgressRecycleBinEntry.test.mjs`:

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const page = fs.readFileSync(path.join(root, 'src/pages/TaskManagementPage.tsx'), 'utf8')

test('recycle bin is a permission-gated operation instead of a peer view toggle', () => {
  assert.doesNotMatch(page, />\s*在办\s*</)
  assert.match(page, /canManageTrash && \(\s*<option value="trash">回收站<\/option>/)
  assert.match(page, /if \(action === 'trash'\) enterRecycleBin\(\)/)
})

test('entering and leaving the recycle bin reset transient work-progress state', () => {
  assert.match(page, /function enterRecycleBin\(\)/)
  assert.match(page, /setViewMode\('execution'\)/)
  assert.match(page, /setSearch\(''\)/)
  assert.match(page, /setFilterStatus\(''\)/)
  assert.match(page, /setFilterOwner\(''\)/)
  assert.match(page, /setShowDeleted\(true\)/)
  assert.match(page, /function leaveRecycleBin\(\)/)
  assert.match(page, /setShowDeleted\(false\)/)
})

test('recycle-bin mode has a clear identity and return action', () => {
  assert.match(page, /data-testid="work-progress-title"/)
  assert.match(page, /showDeleted \? '回收站' : '工作推进表'/)
  assert.match(page, /data-testid="leave-recycle-bin"/)
  assert.match(page, />\s*返回工作推进表\s*</)
})

test('existing restore APIs remain wired to recycle-bin actions', () => {
  assert.match(page, /restoreTask\(task\.id\)/)
  assert.match(page, /restoreSubTask\(st\.id\)/)
})
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
node --test tests\workProgressRecycleBinEntry.test.mjs
```

Working directory: `frontend`

Expected: FAIL because the current source still renders the “在办 / 回收站” peer toggle and has no `enterRecycleBin`, `leaveRecycleBin`, recycle-bin title, or return action.

- [ ] **Step 3: Add focused enter and leave helpers**

Immediately after the existing `clearSelection` function in `frontend/src/pages/TaskManagementPage.tsx`, add:

```tsx
function enterRecycleBin() {
  clearSelection()
  setExpandedTasks(new Set())
  setSearch('')
  setFilterStatus('')
  setFilterOwner('')
  setViewMode('execution')
  setShowDeleted(true)
}

function leaveRecycleBin() {
  clearSelection()
  setExpandedTasks(new Set())
  setShowDeleted(false)
}
```

These helpers only manage transient UI state. They do not mutate task data.

- [ ] **Step 4: Give recycle-bin mode a clear page identity**

Replace the fixed header title with:

```tsx
<h1
  data-testid="work-progress-title"
  className="text-base font-bold text-slate-800"
>
  {showDeleted ? '回收站' : '工作推进表'}
</h1>
```

Render the existing “表格视图 / 执行详情” mode switch only when `showDeleted` is false:

```tsx
{!showDeleted && (
  <div className="inline-flex items-center rounded-lg border border-slate-200 bg-slate-50 p-0.5">
    <button
      type="button"
      onClick={() => {
        setViewMode('plan')
        clearSelection()
      }}
      className={`px-3 py-1.5 text-sm font-semibold rounded-md transition-colors ${
        viewMode === 'plan'
          ? 'bg-white text-slate-800 shadow-sm'
          : 'text-slate-500 hover:text-slate-700'
      }`}
    >
      表格视图
    </button>
    <button
      type="button"
      onClick={() => setViewMode('execution')}
      className={`px-3 py-1.5 text-sm font-semibold rounded-md transition-colors ${
        viewMode === 'execution'
          ? 'bg-white text-slate-800 shadow-sm'
          : 'text-slate-500 hover:text-slate-700'
      }`}
    >
      执行详情
    </button>
  </div>
)}
```

This prevents recycle-bin records from being projected through the plan-table view.

- [ ] **Step 5: Replace the peer toggle with operation-menu entry and return action**

Delete the current `在办 / 回收站` segmented-control block.

Inside `plan-execution-actions`, render an explicit return button while in recycle-bin mode:

```tsx
{showDeleted ? (
  <button
    type="button"
    data-testid="leave-recycle-bin"
    onClick={leaveRecycleBin}
    className="px-4 py-2 rounded-lg border border-slate-200 bg-white text-slate-700 text-sm font-semibold hover:bg-slate-50"
  >
    返回工作推进表
  </button>
) : (
  <select
    defaultValue=""
    onChange={(event) => {
      const action = event.target.value
      if (!action) return
      if (action === 'export') handleExport()
      if (action === 'import') setImportOpen(true)
      if (action === 'trash') enterRecycleBin()
      event.currentTarget.value = ''
    }}
    className="cursor-pointer min-w-[220px] px-4 py-2 rounded-lg border border-slate-200 bg-white text-slate-700 text-sm font-semibold focus:outline-none hover:bg-slate-50"
  >
    <option value="" disabled>操作</option>
    <option value="export">导出表格</option>
    {canManageProjectWork({
      isTechAdmin: currentUser?.is_tech_admin,
      projectRoles: currentProjectRoles,
    }) && currentProjectId && !projectArchived && (
      <option value="import">从大纲导入</option>
    )}
    {canManageTrash && (
      <option value="trash">回收站</option>
    )}
  </select>
)}
```

Keep the surrounding `viewMode === 'execution'` boundary unchanged. This preserves the current location of execution-specific operations and avoids expanding this task into plan-table toolbar redesign.

- [ ] **Step 6: Run the focused test and verify GREEN**

Run:

```powershell
node --test tests\workProgressRecycleBinEntry.test.mjs
```

Expected: 4 tests pass.

- [ ] **Step 7: Commit the entry relocation**

```powershell
git add frontend/src/pages/TaskManagementPage.tsx frontend/tests/workProgressRecycleBinEntry.test.mjs
git commit -m "refactor: move work progress recycle bin into actions"
```

Expected: the commit contains exactly the page and focused test file.

### Task 2: Fail safely when recycle-bin permission is rejected

**Files:**
- Modify: `frontend/tests/workProgressRecycleBinEntry.test.mjs`
- Modify: `frontend/src/pages/TaskManagementPage.tsx:350-390`

- [ ] **Step 1: Add the failing `403` fallback test**

Append to `frontend/tests/workProgressRecycleBinEntry.test.mjs`:

```javascript
test('a forbidden recycle-bin request returns to active work instead of showing an empty bin', () => {
  assert.match(
    page,
    /err instanceof ApiError && err\.status === 403[\s\S]*showDeleted[\s\S]*leaveRecycleBin\(\)/,
  )
  assert.match(page, /toast\.error\(TASK_PROJECT_PERMISSION_DENIED_MESSAGE\)/)
})
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
node --test tests\workProgressRecycleBinEntry.test.mjs
```

Expected: the new test fails because the current `403` branch only emits a toast and leaves `showDeleted` true.

- [ ] **Step 3: Implement the minimal `403` fallback**

In the `fetchTasks(...).catch(...)` branch inside the effect that loads tasks, change the permission handling to:

```tsx
if (err instanceof ApiError && err.status === 403) {
  if (showDeleted) leaveRecycleBin()
  toast.error(TASK_PROJECT_PERMISSION_DENIED_MESSAGE)
  return
}
```

Do not treat non-`403` errors as an empty recycle bin. Keep the existing project-context error handling unchanged.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run:

```powershell
node --test tests\workProgressRecycleBinEntry.test.mjs
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit the permission fallback**

```powershell
git add frontend/src/pages/TaskManagementPage.tsx frontend/tests/workProgressRecycleBinEntry.test.mjs
git commit -m "fix: leave recycle bin when access is denied"
```

Expected: the commit contains exactly the page and focused test file.

### Task 3: Full verification and local acceptance

**Files:**
- Verify only; no planned source changes.

- [ ] **Step 1: Run all frontend tests**

Run:

```powershell
$testFiles = Get-ChildItem tests -File -Filter '*.test.mjs' | Select-Object -ExpandProperty FullName
node --test $testFiles
```

Working directory: `frontend`

Expected: all tests pass with zero failures.

- [ ] **Step 2: Run the production frontend build**

Run:

```powershell
npm run build
```

Working directory: `frontend`

Expected: TypeScript and Vite build complete with exit code `0`. The existing large-chunk warning is non-blocking.

- [ ] **Step 3: Verify the local backend contract remains healthy**

With the existing local backend and frontend running:

```powershell
Invoke-RestMethod http://127.0.0.1:8008/api/health
Invoke-RestMethod http://127.0.0.1:6001/api/health
```

Expected: both report `status=ok`, `database=ok`, and `env=development`.

- [ ] **Step 4: Verify the UI in the browser**

Use an account with project-owner or technical-admin permission:

1. Open `http://127.0.0.1:6001/work/tasks`.
2. Select “执行详情”.
3. Confirm there is no “在办 / 回收站” peer toggle.
4. Open “操作” and confirm “回收站” is available.
5. Enter the recycle bin and confirm the title is “回收站”.
6. Confirm the table/execution mode switch is hidden in recycle-bin mode.
7. Confirm existing deleted records expose their current restore actions.
8. Select “返回工作推进表”.
9. Confirm the active work list reloads under the same project.

Use an ordinary member account and confirm “回收站” is absent from “操作”.

- [ ] **Step 5: Inspect the final diff**

Run:

```powershell
git diff --check
git status --short
git log -3 --oneline
```

Expected:

- no whitespace errors;
- only pre-existing unrelated working-tree files remain uncommitted;
- the two implementation commits are at the branch tip.
