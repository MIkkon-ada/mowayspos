# 项目工作推进表 WBS 结构化改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将工作推进表重构为统一的 WBS 驱动视图，让网页主表和 Excel 导出共用同一套项目管理字段与行模型。

**Architecture:** 保留 `TaskItem` 作为重点工作、`SubTaskItem` 作为关键任务，在现有 `planTableViewModel` 中生成 WBS 展示编号和统一行数据。新增共享列配置，由网页表格和 Excel 导出共同消费；详情继续复用现有关键任务执行工作台，主表只承担摘要和导航。

**Tech Stack:** React 19、TypeScript、Vitest/Node test、ExcelJS、现有 Vite 前端。

---

## 文件结构与职责

- Create: `frontend-v2/src/components/task-management/planTableColumns.ts` — 统一列 key、标签、优先级、宽度和导出顺序。
- Modify: `frontend-v2/src/components/task-management/planTableViewModel.ts` — 生成 WBS 编号、交付成果、验收标准、风险、最新进展和统一单元格值。
- Modify: `frontend-v2/src/components/task-management/PlanTableViewV2.tsx` — 使用共享列配置渲染项目工作推进表，并恢复真实导出入口。
- Modify: `frontend-v2/src/components/task-management/planTableExcelV2.css` — 支持 WBS 列、摘要列、响应式隐藏和长文本布局。
- Modify: `frontend-v2/src/utils/exportPlanTableExcel.ts` — 使用共享列配置和统一行模型导出主表，并避免固定行高遮挡内容。
- Modify: `frontend-v2/src/pages/TaskManagementPage.tsx` — 页面标题和导出入口统一使用“项目工作推进表”。
- Create: `frontend-v2/tests/projectWorkProgressWbs.test.mjs` — 统一字段、WBS 行模型、导出引用和页面命名的契约测试。
- Modify: `frontend-v2/tests/workProgressExcelView.test.mjs` — 将旧的 14 列 Excel 契约迁移为网页/Excel 共用字段契约，并保留既有行模型回归测试。

### Task 1: Add failing tests for the shared WBS model

**Files:**
- Create: `frontend-v2/tests/projectWorkProgressWbs.test.mjs`
- Modify: `frontend-v2/tests/workProgressExcelView.test.mjs`
- Test: `frontend-v2/src/components/task-management/planTableColumns.ts`
- Test: `frontend-v2/src/components/task-management/planTableViewModel.ts`

- [ ] **Step 1: Write the failing test**

覆盖以下行为：

```js
test('shared columns describe the same project work progress fields for web and Excel', async () => {
  const { PLAN_TABLE_COLUMNS } = await loadModule('../src/components/task-management/planTableColumns.ts')
  assert.deepEqual(PLAN_TABLE_COLUMNS.map((column) => column.key), [
    'wbsCode', 'workstream', 'keyTask', 'deliverable', 'acceptance',
    'responsible', 'planTime', 'status', 'risk', 'latestProgress', 'nextStep',
  ])
})

test('plan rows expose stable WBS codes and project-control summaries', async () => {
  const { buildPlanRows } = await loadModule('../src/components/task-management/planTableViewModel.ts')
  const rows = buildPlanRows({ project, tasks, taskSubMap })
  assert.deepEqual(rows.map((row) => row.wbsCode), ['1.1', '1.2', '2'])
  assert.equal(rows[0].deliverable, '数据核验报告')
  assert.equal(rows[0].acceptance, '字段准确率达到100%')
  assert.equal(rows[0].latestProgress, '已完成第一轮核验')
  assert.equal(rows[0].nextStep, '提交复核')
  assert.equal(rows[0].risk, '有风险')
})
```

使用一个包含两个重点工作和三个关键任务的最小匿名数据集；不要读取开发数据库或参考 Excel 的真实内容。

- [ ] **Step 2: Run the test and verify it fails for the missing shared model**

Run: `node --test tests/projectWorkProgressWbs.test.mjs`

Expected: FAIL because `planTableColumns.ts` does not exist and the row model has no `wbsCode`/control summary fields.

- [ ] **Step 3: Commit the failing test**

```bash
git add frontend-v2/tests/projectWorkProgressWbs.test.mjs
git commit -m "test: define project work progress WBS contract"
```

### Task 2: Implement shared columns and WBS row projection

**Files:**
- Create: `frontend-v2/src/components/task-management/planTableColumns.ts`
- Modify: `frontend-v2/src/components/task-management/planTableViewModel.ts`
- Test: `frontend-v2/tests/projectWorkProgressWbs.test.mjs`

- [ ] **Step 1: Add the shared column metadata**

Define the eleven main-table columns with stable keys, labels, high/medium/low display priority, natural width, and export order. Keep React rendering out of the shared module.

- [ ] **Step 2: Add WBS and control-summary fields to `PlanTableRow`**

Add `wbsCode`, `workstream`, `deliverable`, `acceptance`, `risk`, and `latestProgress`. Generate codes from the visible task order and child order: `1.1`, `1.2`, then `2` for a workstream without child rows. Use existing fields only: `key_achievement`, `completion_standard`, `completion_criteria`, `has_risk`, `latest_confirmed_submission.summary`, `latest_next_step`, and parsed notes.

- [ ] **Step 3: Add a shared row-value accessor**

Implement `getPlanRowCellValue(row, key)` so Excel and non-rich table consumers read the same values. Empty values must remain `EMPTY_PLAN_CELL` or an explicit status label; never invent a percentage or completion fact.

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `node --test tests/projectWorkProgressWbs.test.mjs`

Expected: PASS for the shared column and row projection tests.

- [ ] **Step 5: Commit the model**

```bash
git add frontend-v2/src/components/task-management/planTableColumns.ts frontend-v2/src/components/task-management/planTableViewModel.ts frontend-v2/tests/projectWorkProgressWbs.test.mjs
git commit -m "feat: add shared project work progress WBS model"
```

### Task 3: Rebuild the web project work progress table

**Files:**
- Modify: `frontend-v2/src/components/task-management/PlanTableViewV2.tsx`
- Modify: `frontend-v2/src/components/task-management/planTableExcelV2.css`
- Modify: `frontend-v2/src/pages/TaskManagementPage.tsx`
- Test: `frontend-v2/tests/projectWorkProgressWbs.test.mjs`

- [ ] **Step 1: Add the failing structure assertions**

Assert that the page uses the `项目工作推进表` label, that the table renders the shared column configuration, and that it exposes `WBS编号`, `交付成果`, `验收标准`, `风险/问题`, `最新进展`, and `下一步`.

- [ ] **Step 2: Render the configured table columns**

Use `PLAN_TABLE_COLUMNS` for header order and width metadata. Keep rich cell renderers for status markers, latest-progress summaries, task links, and the standard modal, while using the shared row accessor for plain values.

- [ ] **Step 3: Restore the export action in the table toolbar**

Consume the existing `exportDisabled` and `onExport` props in `PlanTableViewV2`. The action must remain disabled until all subtasks required for the current project are loaded.

- [ ] **Step 4: Make the layout responsive**

Keep WBS, 重点工作, 关键任务, 负责人, 状态 and 下一步 as high-priority columns. At narrower widths, collapse or hide lower-priority columns before allowing horizontal scrolling. Keep the table header and identifying columns sticky.

- [ ] **Step 5: Run focused tests and build**

Run: `node --test tests/projectWorkProgressWbs.test.mjs tests/workProgressExcelView.test.mjs`

Run: `npm run build`

Expected: all focused tests pass and TypeScript/Vite build succeeds.

- [ ] **Step 6: Commit the web view**

```bash
git add frontend-v2/src/components/task-management/PlanTableViewV2.tsx frontend-v2/src/components/task-management/planTableExcelV2.css frontend-v2/src/pages/TaskManagementPage.tsx frontend-v2/tests/projectWorkProgressWbs.test.mjs
git commit -m "feat: rebuild project work progress table view"
```

### Task 4: Make Excel export consume the same schema

**Files:**
- Modify: `frontend-v2/src/utils/exportPlanTableExcel.ts`
- Modify: `frontend-v2/src/components/task-management/planTableViewModel.ts`
- Test: `frontend-v2/tests/projectWorkProgressWbs.test.mjs`

- [ ] **Step 1: Add the failing export contract assertion**

Assert that the export source imports `PLAN_TABLE_COLUMNS`, maps headers from the shared configuration, and includes the same eleven keys as the web table. Update the old `workProgressExcelView.test.mjs` expectation so `PLAN_TABLE_BUSINESS_HEADERS` is no longer the source of truth and the shared column labels are asserted instead. Assert that no hard-coded fourteen-header list remains the export source of truth.

- [ ] **Step 2: Refactor export headers and row values**

Build the worksheet header from `PLAN_TABLE_COLUMNS.map(column => column.label)` and each data row from `getPlanRowCellValue(row, column.key)`. Use wrapped text with content-aware row heights or a safe minimum plus autofit behavior so long progress text is not silently hidden.

- [ ] **Step 3: Preserve useful spreadsheet behavior**

Keep the project title, frozen identifying columns, frozen header rows, borders, status semantics, and safe filename behavior. If historical progress is included, place it in a separate follow-up sheet rather than mixing multi-line history into the main table cell.

- [ ] **Step 4: Run export/model tests and build**

Run: `node --test tests/projectWorkProgressWbs.test.mjs tests/workProgressExcelView.test.mjs`

Run: `npm run build`

Expected: all focused tests pass and build succeeds.

- [ ] **Step 5: Commit the export**

```bash
git add frontend-v2/src/utils/exportPlanTableExcel.ts frontend-v2/src/components/task-management/planTableViewModel.ts frontend-v2/tests/projectWorkProgressWbs.test.mjs
git commit -m "feat: align project work progress Excel export"
```

### Task 5: Full verification and visual review

**Files:**
- Verify: `frontend-v2/tests/projectWorkProgressWbs.test.mjs`
- Verify: `frontend-v2/tests/workProgressExcelView.test.mjs`
- Verify: `frontend-v2/src/components/task-management/PlanTableViewV2.tsx`
- Verify: `frontend-v2/src/utils/exportPlanTableExcel.ts`

- [ ] **Step 1: Run all relevant tests**

Run: `node --test tests/projectWorkProgressWbs.test.mjs tests/workProgressExcelView.test.mjs`

Run: `npm run test:unit`

- [ ] **Step 2: Run the production build**

Run: `npm run build`

- [ ] **Step 3: Review the rendered layout**

Use the local preview with the anonymous example data and inspect desktop, narrow desktop, empty, long-text, risk, and no-subtask states. Confirm that the main table remains readable and that details remain reachable.

- [ ] **Step 4: Check scope and repository state**

Run: `git diff --check`

Run: `git status --short --branch`

Confirm that only intended source, test, plan, and documentation files changed; preserve the pre-existing untracked `frontend-v2/.workbuddy-ai/` directory.

- [ ] **Step 5: Commit final verification adjustments**

```bash
git add frontend-v2 docs/superpowers/plans/2026-09-20-project-work-progress-wbs.md
git commit -m "test: verify project work progress WBS redesign"
```
