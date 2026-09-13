# 项目工作计划导入 UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将工作计划导入弹窗改成简洁的“提供内容 → 分组复核 → 确认导入”工作台。

**Architecture:** 保留现有 AI 预览和原子导入 API，只把 BatchImportRow 转换成按重点工作分组的前端视图模型。组件在 source/review 两个主要阶段之间切换，复核时默认展示核心字段，低频字段按需展开编辑。

**Tech Stack:** React 19, TypeScript, Tailwind utility classes, Vitest, Testing Library, existing project-plan import APIs.

---

### Task 1: Lock the compact grouping contract

**Files:**
- Create: `frontend/src/features/settings/projectPlanAiImportView.ts`
- Create: `frontend/src/features/settings/projectPlanAiImportView.test.ts`

- [x] **Step 1: Write the failing test**

Add tests for `groupImportRows`: it preserves first-seen workstream order, groups rows under the same project/workstream, exposes `key`, `projectName`, `workstream`, and `rows`, and returns an empty list for empty input.

- [x] **Step 2: Run the focused test and verify RED**

Run:

```powershell
npm run test:unit -- --run src/features/settings/projectPlanAiImportView.test.ts
```

Expected: FAIL because the grouping module does not exist.

- [x] **Step 3: Implement the minimal grouping helper**

Define `ProjectPlanImportGroup` and `groupImportRows(rows)` with a `Map` keyed by `${project_name}::${workstream}`. Preserve input row order inside each group and return `Array.from(groups.values())`.

- [x] **Step 4: Run the focused test and verify GREEN**

Run the same Vitest command. Expected: all grouping tests pass.

### Task 2: Lock the review interaction contract

**Files:**
- Create: `frontend/src/features/settings/ProjectPlanAiImportDialog.test.tsx`
- Modify: `frontend/tests/projectPlanImportUiContract.test.mjs`

- [x] **Step 1: Write failing component tests**

Render the dialog with a small preview fixture and mocked API calls. Assert that source mode shows upload/paste controls, review mode shows grouped workstreams rather than a wide table, the edit action reveals optional fields, and confirm stays disabled until review rows exist.

- [x] **Step 2: Run tests and verify RED**

Run:

```powershell
npm run test:unit -- --run src/features/settings/ProjectPlanAiImportDialog.test.tsx
node --test tests/projectPlanImportUiContract.test.mjs
```

Expected: the new component assertions fail against the current three-column wide-table implementation.

- [x] **Step 3: Update the static contract expectations**

Replace the old table-oriented assertions with checks for source mode labels, grouped review, optional editing, compact summary, and absence of `min-w-[980px]`.

### Task 3: Implement the compact source and review workbench

**Files:**
- Modify: `frontend/src/features/settings/ProjectPlanAiImportDialog.tsx`
- Modify: `frontend/src/features/settings/projectPlanAiImportView.ts`

- [x] **Step 1: Implement source mode**

Keep the existing file input and paste `File` conversion. Add `sourceMode: 'upload' | 'paste'`, a compact mode switch, one-line destination controls, and the existing analyze action. Keep errors and busy-state guards unchanged.

- [x] **Step 2: Implement compact review mode**

Use `groupImportRows(rows)` to render workstream cards. Show the three counts and fallback/source badges in a compact summary row. Render core task fields by default and reveal owner/status/time/notes inputs only for the selected row after clicking “编辑”. Keep `editRow` as the single update path so user edits remain in the same BatchImportRow array.

- [x] **Step 3: Implement the fixed action footer**

Keep the no-write notice visible, add a source reset action, and keep confirmation disabled unless `phase === 'review'` and all required row fields are nonempty. Do not change `applyAiProjectPlan` or parent refresh behavior.

- [x] **Step 4: Run component tests and build**

Run the focused Vitest and contract commands from Task 2, then:

```powershell
npm run build
```

Expected: all focused tests pass and TypeScript/Vite build exits 0.

### Task 4: Full regression and handoff

**Files:**
- Modify: `docs/superpowers/plans/2026-09-14-project-plan-import-ux.md`

- [x] **Step 1: Run the complete frontend verification**

```powershell
npm run test:all
npm run build
git diff --check
```

- [x] **Step 2: Inspect the final diff**

Confirm no backend/API/database changes, no credentials or deployment data in source, no wide review table, and the existing project management permission boundary remains unchanged.

- [ ] **Step 3: Commit the UX change**

```powershell
git add frontend/src/features/settings/ProjectPlanAiImportDialog.tsx frontend/src/features/settings/ProjectPlanAiImportDialog.test.tsx frontend/src/features/settings/projectPlanAiImportView.ts frontend/src/features/settings/projectPlanAiImportView.test.ts frontend/tests/projectPlanImportUiContract.test.mjs docs/superpowers/specs/2026-09-14-project-plan-import-ux-design.md docs/superpowers/plans/2026-09-14-project-plan-import-ux.md
git commit -m "feat: simplify work plan import review ui"
```
