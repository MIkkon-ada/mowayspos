# Work Progress Monitoring View Implementation Plan

> **For agentic workers:** Execute inline in this session; subagents are prohibited by the repository instructions.

**Goal:** Make C02–C05 of the work-progress acceptance criteria accurate and usable in V2, including clear failure states, group summaries, confirmed progress, search, and quick filters.

**Architecture:** Keep the existing work-progress route and data APIs. Fix the batch subtask loader so a failed request remains an error and can be retried; derive overview/group summaries from the existing project-scoped tasks, subtasks, and issues; retain the existing plan table, export, and mobile task list.

**Tech Stack:** React 19, TypeScript, Vitest, Vite, existing FastAPI API and isolated SQLite acceptance data.

---

### Task 1: Preserve the failed subtask-load state

**Files:**
- Modify: `frontend-v2/src/pages/TaskManagementPage.tsx`
- Modify: `frontend-v2/src/components/task-management/PlanTableViewV2.tsx`
- Test: `frontend-v2/src/components/task-management/PlanTableViewV2.test.tsx`

- [ ] **Step 1: Add one UI regression test.** Render `PlanTableViewV2` with a batch-load error and retry callback. Assert the error message appears, no zero-count placeholder is presented as loaded data, and clicking retry invokes the callback once.
- [ ] **Step 2: Run the targeted test and confirm it fails.** From `frontend-v2`, run `npm run test:unit -- src/components/task-management/PlanTableViewV2.test.tsx`; expected: the new error/retry test fails because the component does not yet expose an error state.
- [ ] **Step 3: Implement the minimal error path.** Keep batch failures out of `taskSubMap`; store the failed state; prevent the loading effect from retrying continuously; show a clear retry action; clear the error and reload only after an explicit retry.
- [ ] **Step 4: Re-run the targeted test.** Expected: the new test and existing `PlanTableViewV2` tests pass.

### Task 2: Align project and workstream summaries with the visible rows

**Files:**
- Modify: `frontend-v2/src/components/task-management/PlanTableViewV2.tsx`
- Modify if required by a proven mismatch: `frontend-v2/src/components/task-management/planTableViewModel.ts`
- Test: `frontend-v2/src/components/task-management/PlanTableViewV2.test.tsx`

- [ ] **Step 1: Add assertions to the existing fixture test.** Use three workstreams with completed, overdue, risk-marked, open-issue, and closed-issue tasks. Assert task totals and per-workstream counts match the rendered rows; risk counts remain separate from issue counts.
- [ ] **Step 2: Run the targeted test and confirm any new expectation fails.** Use the same Vitest command above.
- [ ] **Step 3: Implement only the mismatched summary behavior.** Preserve project scoping and the existing SVG chevron; show explicit units for task counts and issue counts; keep collapsed groups out of view without removing them from metrics or export.
- [ ] **Step 4: Re-run the targeted test and confirm it passes.**

### Task 3: Verify high-signal content and responsive presentation

**Files:**
- Modify only if the live acceptance reveals a visible issue: `frontend-v2/src/components/task-management/workProgressWorkspace.css`, `PlanTableViewV2.tsx`, or `frontend-v2/src/features/mobile-core-pages/MobileTaskList.tsx`.
- Evidence: `outputs/acceptance-table-20261015/evidence/C02-C05/`.

- [ ] **Step 1: Start V2 and the backend against an isolated SQLite copy, never the primary database.** Confirm the effective DB path before startup and stop if it resolves to the primary path.
- [ ] **Step 2: Use one acceptance dataset** with at least three workstreams and all task/problem states in C02–C05. Reconcile the displayed KPI numbers with the underlying records, then click each KPI and quick filter and verify visible rows and active conditions.
- [ ] **Step 3: Capture desktop and mobile views.** Verify 1366×768, 1440×900, and 390×844. Confirm task, owner, plan, status, latest confirmed progress, next step, and retryable loading failures are understandable. Do not treat unconfirmed text as official progress.
- [ ] **Step 4: Run the targeted component test and V2 build once.** From `frontend-v2`, run `npm run test:unit -- src/components/task-management/PlanTableViewV2.test.tsx` and `npm run build`; expected: both exit with code 0.
- [ ] **Step 5: Record only the evidence actually observed** in the acceptance workbook; leave C02–C05 pending if live data, browser access, or screenshots are unavailable.

---

## Scope review

- The design preserves the work-progress table, hierarchy, permission boundaries, field preferences, exports, and mobile task list.
- This plan covers only C02–C05; C11–C12 and other project acceptance items remain separate work.
- The local V2 and API ports were confirmed to have no listeners at plan time. Live acceptance therefore requires safe isolated startup; historical code or test results are not substitutes.
