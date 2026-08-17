# Hide Execution Detail Temporarily Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Temporarily make the work progress page stay in table view and prevent entry to the execution detail view while preserving the existing detail implementation for later restoration.

**Architecture:** Add a local feature switch in `TaskManagementPage.tsx`. When disabled, omit the execution-mode tab, keep `viewMode` at `plan`, and guard the subtask-focus path that currently switches to `execution`. Leave `KeyTaskExecutionDetailView` and its supporting APIs untouched.

**Tech Stack:** React, TypeScript, Vite, Node test runner with `node:test`-style assertions.

---

### Task 1: Update source-level regression tests

**Files:**
- Modify: `frontend/tests/workProgressExcelView.test.mjs:90-97`
- Modify: `frontend/tests/workProgressExcelView.test.mjs:348-354`

- [ ] **Step 1: Replace the old visibility expectation with a hidden-entry expectation**

Change the existing test so it continues to assert the plan default and execution implementation, but asserts that the rendered mode-tab block does not expose the `执行详情` label. The test should recognize a named switch in the page source, for example:

```js
test('work progress temporarily hides execution detail entry', () => {
  const source = read(PAGE_FILE)
  assert.match(source, /useState<'execution' \\| 'plan'>\\('plan'\\)/)
  assert.match(source, /const SHOW_EXECUTION_DETAIL = false/)
  assert.match(source, /SHOW_EXECUTION_DETAIL && \\(/)
  assert.match(source, /data-testid="work-progress-detail-panel"/)
})
```

- [ ] **Step 2: Change the header-tab test to assert the remaining table tab**

Replace the current ordered `表格视图 ... 执行详情` assertion with a test that asserts the title and `表格视图` remain present while `执行详情` is absent from the header source:

```js
test('work progress header keeps only the table mode tab while execution detail is hidden', () => {
  const page = read(PAGE_FILE)
  assert.match(page, /work-progress-title-group/)
  assert.match(page, /工作推进表[\\s\\S]*表格视图/)
  assert.doesNotMatch(page, /表格视图[\\s\\S]*执行详情/)
  assert.doesNotMatch(page, /min-w-\\[260px\\]/)
})
```

- [ ] **Step 3: Run the focused test and confirm it fails**

Run from `frontend`:

```powershell
node --test tests/workProgressExcelView.test.mjs
```

Expected: FAIL because the page does not yet contain the temporary switch/guard and still renders the execution tab.

### Task 2: Hide and guard execution detail entry

**Files:**
- Modify: `frontend/src/pages/TaskManagementPage.tsx:251,559,960-968`

- [ ] **Step 1: Add the temporary switch beside the view-mode state**

Add a clearly named constant immediately before the `viewMode` state:

```ts
const SHOW_EXECUTION_DETAIL = false
const [viewMode, setViewMode] = useState<'execution' | 'plan'>('plan')
```

Use the existing component scope; do not add environment configuration or remove the execution-detail component.

- [ ] **Step 2: Guard the subtask focus transition**

Keep the existing `focusSubTask` data-loading and selection logic, but conditionally skip only the execution-mode transition:

```ts
function focusSubTask(st: SubTaskItem, opts?: { keepTask?: boolean }) {
  if (SHOW_EXECUTION_DETAIL) setViewMode('execution')
  // existing logic remains unchanged
}
```

Do not call `openSubDetail` from this branch because it delegates back to `focusSubTask`. In hidden mode, the existing `selectedSubTask` loading continues and the current right-side detail panel remains the destination because `viewMode` stays `plan`.

- [ ] **Step 3: Conditionally render the execution mode button**

Wrap only the existing execution tab button in the switch, preserving the table tab and its current styling:

```tsx
{SHOW_EXECUTION_DETAIL && (
  <button
    type="button"
    onClick={() => setViewMode('execution')}
    className={`px-3 py-1.5 text-sm font-semibold rounded-md transition-colors ${viewMode === 'execution' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
  >
    执行详情
  </button>
)}
```

- [ ] **Step 4: Guard the execution-detail rendering branch**

Change the detail-page branch condition from `viewMode === 'execution' && selectedSubTask` to `SHOW_EXECUTION_DETAIL && viewMode === 'execution' && selectedSubTask`. Keep the existing `KeyTaskExecutionDetailView` props and `onBack` behavior unchanged.

- [ ] **Step 5: Run the focused test and confirm it passes**

Run:

```powershell
node --test tests/workProgressExcelView.test.mjs
```

Expected: PASS, including the existing tests that verify the execution detail component itself remains implemented.

### Task 3: Verify the frontend build and diff scope

**Files:**
- Verify: `frontend/src/pages/TaskManagementPage.tsx`
- Verify: `frontend/tests/workProgressExcelView.test.mjs`
- Verify: `docs/superpowers/specs/2026-08-13-hide-execution-detail-design.md`

- [ ] **Step 1: Run the frontend build**

Run from `frontend`:

```powershell
npm run build
```

Expected: TypeScript compilation and Vite build complete successfully.

- [ ] **Step 2: Check the patch for whitespace errors**

Run from the repository root:

```powershell
git diff --check -- frontend/src/pages/TaskManagementPage.tsx frontend/tests/workProgressExcelView.test.mjs
```

Expected: no output and exit code 0.

- [ ] **Step 3: Confirm only in-scope files changed**

Run:

```powershell
git status --short
git diff --stat -- frontend/src/pages/TaskManagementPage.tsx frontend/tests/workProgressExcelView.test.mjs
```

Expected: the implementation diff contains only the page and its focused test; pre-existing unrelated working-tree changes remain untouched.
