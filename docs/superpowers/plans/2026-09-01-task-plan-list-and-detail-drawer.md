# Task Plan List and Detail Drawer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make task plans compact to scan and keep full plan information in the right-side detail drawer.

**Architecture:** `ExecutionPlanTable` owns the compact five-column list and only emits `onOpen(plan)` from its row chevron. `ExecutionPlanDetailDrawer` keeps the existing drawer data source and rearranges it into summary, deliverable, progress, history, and fixed actions without changing API contracts.

**Tech Stack:** React 19, TypeScript, Tailwind CSS, Vitest, Testing Library.

---

### Task 1: Verify the compact list markup

**Files:**
- Create: `frontend/src/components/key-task-workspace/ExecutionPlanTable.test.tsx`
- Modify: `frontend/src/components/key-task-workspace/ExecutionPlanTable.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
it('renders compact owner, collaborator, date columns and a detail button', () => {
  render(<ExecutionPlanTable plans={[plan]} summary={summary} canManage={false} onAdd={() => {}} onOpen={onOpen} />)
  expect(screen.getByRole('columnheader', { name: '负责人' })).toBeTruthy()
  expect(screen.getByRole('columnheader', { name: '协助人' })).toBeTruthy()
  expect(screen.getByRole('button', { name: '查看任务计划：测试计划' })).toBeTruthy()
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test:unit -- ExecutionPlanTable.test.tsx`

Expected: FAIL because the compact column headers and detail button do not exist.

- [ ] **Step 3: Implement the compact list**

```tsx
<th>负责人</th><th>协助人</th><th>时间</th>
<button aria-label={`查看任务计划：${plan.title}`} onClick={() => onOpen(plan)}>›</button>
```

Remove the repeated per-row progress line and stop treating the entire row as the drawer trigger.

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm run test:unit -- ExecutionPlanTable.test.tsx`

Expected: PASS.

### Task 2: Arrange the detail drawer to match the approved sketch

**Files:**
- Modify: `frontend/src/components/key-task-workspace/ExecutionPlanDetailDrawer.tsx`
- Test: `frontend/src/components/key-task-workspace/ExecutionPlanTable.test.tsx`

- [ ] **Step 1: Add a source-level regression assertion**

```tsx
expect(readFileSync(drawerPath, 'utf8')).toContain('预期成果')
expect(readFileSync(drawerPath, 'utf8')).toContain('推进记录')
expect(readFileSync(drawerPath, 'utf8')).toContain('提交更新')
```

- [ ] **Step 2: Run the test to verify it fails if required drawer sections are absent**

Run: `npm run test:unit -- ExecutionPlanTable.test.tsx`

Expected: PASS against current drawer section names; this establishes the protected interaction contract before layout-only refactoring.

- [ ] **Step 3: Implement the layout-only drawer refinement**

```tsx
<dl className="grid grid-cols-3 divide-x rounded-xl border ...">...</dl>
<section className="rounded-xl border ...">...</section>
<footer className="sticky bottom-0 border-t ...">...</footer>
```

Keep the existing callbacks and permissions unchanged.

- [ ] **Step 4: Run the focused test and production build**

Run: `npm run test:unit -- ExecutionPlanTable.test.tsx && npm run build`

Expected: PASS and a successful TypeScript/Vite build.

### Task 3: Verify the running page and commit

**Files:**
- Modify: `frontend/src/components/key-task-workspace/ExecutionPlanTable.tsx`
- Modify: `frontend/src/components/key-task-workspace/ExecutionPlanDetailDrawer.tsx`
- Create: `frontend/src/components/key-task-workspace/ExecutionPlanTable.test.tsx`

- [ ] **Step 1: Confirm the list has no avatars or repeated empty progress rows**

Inspect the local task workspace and open a plan with the right-side detail button.

- [ ] **Step 2: Commit only the task-plan UI files and test**

```bash
git add frontend/src/components/key-task-workspace/ExecutionPlanTable.tsx frontend/src/components/key-task-workspace/ExecutionPlanDetailDrawer.tsx frontend/src/components/key-task-workspace/ExecutionPlanTable.test.tsx docs/superpowers/plans/2026-09-01-task-plan-list-and-detail-drawer.md
git commit -m "feat: refine task plan list and detail drawer"
```
