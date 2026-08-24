# Key Task Workspace Reference Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the desktop key-task execution workspace match the supplied reference layout while retaining all existing data and interactions.

**Architecture:** Keep `KeyTaskExecutionWorkspace` as the data and action owner. Change only existing presentational components, adding one wrapper for the two secondary cards; each component keeps consuming its current DTO slice and preserves non-empty views.

**Tech Stack:** React 19, TypeScript, Tailwind CSS, Node built-in test runner, Vite.

---

## File structure

- Modify: `frontend/tests/keyTaskExecutionWorkspace.test.mjs` — source-structure regression tests for the reference layout.
- Modify: `frontend/src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx` — reference-ordered main/side layout and secondary-card wrapper.
- Modify: `frontend/src/components/key-task-workspace/KeyTaskHeader.tsx` — shallow blue task information header.
- Modify: `frontend/src/components/key-task-workspace/CurrentProgressCard.tsx` — bordered current-progress card and centered empty state.
- Modify: `frontend/src/components/key-task-workspace/ExecutionPlanTable.tsx` — reference table header and plan empty state.
- Modify: `frontend/src/components/key-task-workspace/AchievementList.tsx` — compact result card empty state.
- Modify: `frontend/src/components/key-task-workspace/IssueList.tsx` — compact risk card empty state.
- Modify: `frontend/src/components/key-task-workspace/ExecutionTimeline.tsx` — title-row filters and empty timeline state.
- Modify: `frontend/src/components/key-task-workspace/KeyTaskContextCard.tsx` — aligned relationship context card.

### Task 1: Lock the reference layout with a failing test

**Files:**

- Modify: `frontend/tests/keyTaskExecutionWorkspace.test.mjs`
- Test: `frontend/tests/keyTaskExecutionWorkspace.test.mjs`

- [ ] **Step 1: Write the failing test**

Append this test to the suite:

~~~js
test('workspace uses the reference main and side card hierarchy', () => {
  const workspace = read('src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx')
  const header = read('src/components/key-task-workspace/KeyTaskHeader.tsx')
  const plan = read('src/components/key-task-workspace/ExecutionPlanTable.tsx')
  const current = read('src/components/key-task-workspace/CurrentProgressCard.tsx')
  const achievements = read('src/components/key-task-workspace/AchievementList.tsx')
  const issues = read('src/components/key-task-workspace/IssueList.tsx')
  const timeline = read('src/components/key-task-workspace/ExecutionTimeline.tsx')
  const context = read('src/components/key-task-workspace/KeyTaskContextCard.tsx')

  assert.match(workspace, /md:grid-cols-2/)
  assert.match(workspace, /<AchievementList items={workspace\.achievements} \/><IssueList items={workspace\.issues} \/>/)
  assert.match(header, /bg-blue-50/)
  assert.match(plan, /添加计划/)
  assert.match(current, /暂无已确认的有效推进事实/)
  assert.match(achievements, /暂无关联成果/)
  assert.match(issues, /暂无关联问题或风险/)
  assert.match(timeline, /暂无已确认的推进记录/)
  assert.match(context, /所属关系/)
})
~~~

- [ ] **Step 2: Run the test to verify it fails**

Run:

~~~powershell
node --test frontend/tests/keyTaskExecutionWorkspace.test.mjs
~~~

Expected: FAIL in `workspace uses the reference main and side card hierarchy` because the workspace does not yet wrap achievements and issues in an `md:grid-cols-2` container, and the plan does not include `添加计划`.

- [ ] **Step 3: Commit the red test**

~~~powershell
git add frontend/tests/keyTaskExecutionWorkspace.test.mjs
git commit -m "test: define key task reference layout"
~~~

### Task 2: Implement the reference layout and empty states

**Files:**

- Modify: `frontend/src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx`
- Modify: `frontend/src/components/key-task-workspace/KeyTaskHeader.tsx`
- Modify: `frontend/src/components/key-task-workspace/CurrentProgressCard.tsx`
- Modify: `frontend/src/components/key-task-workspace/ExecutionPlanTable.tsx`
- Modify: `frontend/src/components/key-task-workspace/AchievementList.tsx`
- Modify: `frontend/src/components/key-task-workspace/IssueList.tsx`
- Modify: `frontend/src/components/key-task-workspace/ExecutionTimeline.tsx`
- Modify: `frontend/src/components/key-task-workspace/KeyTaskContextCard.tsx`
- Test: `frontend/tests/keyTaskExecutionWorkspace.test.mjs`

- [ ] **Step 1: Add the compact two-card wrapper**

In the main-content sequence in `KeyTaskExecutionWorkspace.tsx`, replace the adjacent secondary cards with:

~~~tsx
<div className="grid gap-4 md:grid-cols-2">
  <AchievementList items={workspace.achievements} />
  <IssueList items={workspace.issues} />
</div>
~~~

Keep the exact surrounding order `CurrentProgressCard`, `ExecutionPlanTable`, two-card wrapper, then `ExecutionTimeline`; keep the existing `xl:grid-cols-[minmax(0,1fr)_330px]` outer grid and sticky context card.

- [ ] **Step 2: Apply reference cards and empty states without changing data behavior**

Use a shared visual vocabulary in the existing JSX: `rounded-lg border border-slate-300 bg-white`, a colored `border-l-4`, `p-5`, and `shadow-sm`. In `ExecutionPlanTable`, render this only when `plans.length === 0`:

~~~tsx
<div className="grid min-h-48 place-items-center px-4 py-8 text-center text-sm text-slate-500">
  <div><p className="text-3xl text-slate-300">▣</p><p className="mt-3">尚未创建任务计划</p><button type="button" className="mt-4 border border-slate-300 px-3 py-1.5 text-xs text-slate-600">添加计划</button></div>
</div>
~~~

In `CurrentProgressCard`, render this when `progress` is null:

~~~tsx
<div className="mt-4 grid min-h-28 place-items-center border border-dashed border-slate-300 bg-slate-50 px-6 text-center text-sm text-slate-500">
  暂无已确认的有效推进事实。会议 AI 候选内容经人工确认并正式回填后，才会显示在这里。
</div>
~~~

For `AchievementList` and `IssueList`, use `border-l-4 border-emerald-600` and `border-l-4 border-red-500` respectively and retain their table render paths. For `ExecutionTimeline`, place the existing filters in the same flex row as the heading (`justify-between`) and render the empty event message inside a short left-border timeline line. Keep filter state, row click handlers, header actions, `aria-label` attributes, and `ExecutionPlanDetailDrawer` unchanged.

- [ ] **Step 3: Style the top and right context areas**

Set the `KeyTaskHeader` root to a shallow blue panel and maintain its metadata and action callbacks:

~~~tsx
<header className="border border-blue-200 bg-blue-50 px-5 py-6 shadow-sm sm:px-7">
~~~

Use square/slightly rounded action controls (`rounded-sm`) to match the reference. Keep every conditional action and the `details` menu exactly as currently gated by `permissions` and `eligibility`. Set `KeyTaskContextCard` to the standard card language with a blue left border, compact relationship spacing, and its existing labels: `项目`, `重点工作`, `关键任务`, `完成定义 / 预期结果`, `创建来源`, and `创建时间`.

- [ ] **Step 4: Run the focused test to verify it passes**

~~~powershell
node --test frontend/tests/keyTaskExecutionWorkspace.test.mjs
~~~

Expected: PASS, including the new reference-layout test and the prior workspace contract tests.

- [ ] **Step 5: Run the frontend build**

Run from `frontend`:

~~~powershell
npm run build
~~~

Expected: exit code 0 and Vite production build output.

- [ ] **Step 6: Make a visual verification capture**

Run the frontend and navigate to a key-task execution detail with no plans, achievements, issues, and timeline events. At desktop width, confirm: blue header, left/right layout, plan card above a two-card row, and timeline beneath. Then load a key task with populated data and confirm tables, filters, and row-to-drawer behavior are preserved.

- [ ] **Step 7: Commit the implementation**

~~~powershell
git add frontend/src/components/key-task-workspace frontend/tests/keyTaskExecutionWorkspace.test.mjs
git commit -m "feat: align key task workspace with reference layout"
~~~

## Plan self-review

- Spec coverage: Task 2 covers the header, main/side grid, ordered cards, desktop dual-card row, reference empty states, responsive fallback, and retained interaction boundaries. API and database work are intentionally absent.
- Placeholder scan: no unresolved markers, function names, or commands remain.
- Type consistency: all changes consume the existing `KeyTaskWorkspace` props and current component interfaces; no new DTO or function is introduced.
