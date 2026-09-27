# 项目工作推进表智能宽表改造 Implementation Plan

> **For agentic workers:** This plan is executed inline in the current isolated worktree. The user has explicitly authorized implementation; do not delegate to subagents.

**Goal:** 将项目工作推进表改造成接近 Excel/企业微信智能表格的桌面端可操作宽表，保留完整字段，支持缩放、横向滚动、关键列冻结、拖拽调整列宽，并让网页与 Excel 继续共用同一份列定义。

**Architecture:** 继续以 `PLAN_TABLE_COLUMNS` 作为字段和导出顺序的唯一来源；新增一个纯函数/Hook 负责浏览器端列宽状态与拖拽边界，视图层只消费列布局并渲染表头、调整柄和单元格。网页个性化列宽只保存在浏览器本地，不改变 Excel 的标准导出宽度，避免用户的临时视图设置污染交付文件。

**Tech Stack:** React + TypeScript + CSS、Node.js `node:test` 合同测试、Vite 构建。

---

### Task 1: 固化智能宽表的布局契约

**Files:**
- Modify: `frontend-v2/tests/projectWorkProgressWbs.test.mjs`
- Modify: `frontend-v2/src/components/task-management/planTableViewModel.ts`

- [ ] **Step 1: 写列宽行为的失败测试**

在现有 WBS 测试中增加以下行为断言：默认列宽来自共享列配置；拖拽后的列宽被限制在最小/最大范围；非法本地存储值回退到默认宽度；布局顺序不影响导出顺序。

```js
test('column layout clamps resized widths and restores canonical widths', async () => {
  const {
    clampPlanTableColumnWidth,
    normalizeStoredPlanTableWidths,
    getDefaultPlanTableWidths,
  } = await loadViewModel()

  assert.equal(clampPlanTableColumnWidth('wbsCode', 20), 64)
  assert.equal(clampPlanTableColumnWidth('keyTask', 720), 520)
  assert.equal(clampPlanTableColumnWidth('keyTask', 340), 340)
  assert.deepEqual(normalizeStoredPlanTableWidths('{"wbsCode":88,"keyTask":360}').wbsCode, 88)
  assert.deepEqual(normalizeStoredPlanTableWidths('{"unknown":999}'), getDefaultPlanTableWidths())
})
```

- [ ] **Step 2: 运行测试确认它因缺少布局 API 而失败**

Run: `npm --prefix frontend-v2 exec -- node --test tests/projectWorkProgressWbs.test.mjs`

Expected: FAIL，失败原因是 `clampPlanTableColumnWidth` 或 `normalizeStoredPlanTableWidths` 尚未导出。

- [ ] **Step 3: 实现最小布局模型**

在 `planTableViewModel.ts` 中根据 `PLAN_TABLE_COLUMNS` 增加默认宽度映射、最小/最大宽度和三个纯函数：

```ts
export const PLAN_TABLE_COLUMN_MIN_WIDTH = 64
export const PLAN_TABLE_COLUMN_MAX_WIDTH = 520

export function getDefaultPlanTableWidths(): Record<PlanTableColumnKey, number> {
  return Object.fromEntries(PLAN_TABLE_COLUMNS.map((column) => [column.key, column.width])) as Record<PlanTableColumnKey, number>
}

export function clampPlanTableColumnWidth(key: PlanTableColumnKey, width: number): number {
  const fallback = getPlanTableColumn(key).width
  if (!Number.isFinite(width)) return fallback
  return Math.min(PLAN_TABLE_COLUMN_MAX_WIDTH, Math.max(PLAN_TABLE_COLUMN_MIN_WIDTH, Math.round(width)))
}

export function normalizeStoredPlanTableWidths(value: string | null): Record<PlanTableColumnKey, number> {
  const defaults = getDefaultPlanTableWidths()
  if (!value?.trim()) return defaults
  try {
    const parsed = JSON.parse(value) as Record<string, unknown>
    for (const column of PLAN_TABLE_COLUMNS) {
      const storedWidth = parsed[column.key]
      if (typeof storedWidth === 'number') defaults[column.key] = clampPlanTableColumnWidth(column.key, storedWidth)
    }
  } catch {
    return defaults
  }
  return defaults
}
```

`getPlanTableColumn` 只返回共享列配置，不改变导出使用的 `column.width`。

- [ ] **Step 4: 运行聚焦测试确认通过**

Run: `npm --prefix frontend-v2 exec -- node --test tests/projectWorkProgressWbs.test.mjs`

Expected: 新增布局契约测试与既有 WBS 测试全部 PASS。

- [ ] **Step 5: 提交布局契约**

```bash
git add frontend-v2/tests/projectWorkProgressWbs.test.mjs frontend-v2/src/components/task-management/planTableViewModel.ts
git commit -m "test: define smart grid column layout contract"
```

### Task 2: 增加浏览器端列宽状态和拖拽调整

**Files:**
- Create: `frontend-v2/src/components/task-management/usePlanTableColumnLayout.ts`
- Modify: `frontend-v2/tests/projectWorkProgressWbs.test.mjs`

- [ ] **Step 1: 写 Hook 接口的失败结构测试**

增加源代码契约，要求 Hook 使用独立的本地存储键、共享列键和 pointer 事件，不把用户列宽写回导出配置。

```js
test('column layout hook persists personal widths without changing export columns', () => {
  const source = requireSources(COLUMN_LAYOUT_FILE)
  assert.match(source, /moways\.workProgress\.planColumnWidths/)
  assert.match(source, /PLAN_TABLE_COLUMNS/)
  assert.match(source, /pointermove/)
  assert.match(source, /pointerup/)
  assert.match(source, /clampPlanTableColumnWidth/)
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm --prefix frontend-v2 exec -- node --test tests/projectWorkProgressWbs.test.mjs`

Expected: FAIL，因为 Hook 文件不存在。

- [ ] **Step 3: 实现最小 Hook**

实现 `usePlanTableColumnLayout()`：初始化时读取本地宽度；提供 `columnWidths`、`getColumnWidth`、`startResize`、`resetColumnWidths`；拖拽过程中以 pointer 坐标差计算宽度，并在 pointerup 时移除监听。初始宽度始终来自 `PLAN_TABLE_COLUMNS`，因此导出不会读取用户视图宽度。

- [ ] **Step 4: 运行聚焦测试确认通过**

Run: `npm --prefix frontend-v2 exec -- node --test tests/projectWorkProgressWbs.test.mjs`

Expected: 布局 Hook 契约测试 PASS。

- [ ] **Step 5: 提交列宽交互**

```bash
git add frontend-v2/src/components/task-management/usePlanTableColumnLayout.ts frontend-v2/tests/projectWorkProgressWbs.test.mjs
git commit -m "feat: add resizable project work progress columns"
```

### Task 3: 把缩放、横向滚动、冻结列和列宽拖拽接入表格

**Files:**
- Modify: `frontend-v2/src/components/task-management/PlanTableViewV2.tsx`
- Modify: `frontend-v2/src/components/task-management/planTableExcelV2.css`
- Modify: `frontend-v2/tests/projectWorkProgressWbs.test.mjs`

- [ ] **Step 1: 写视图交互契约测试**

增加以下断言：视图接入 `usePlanTableZoom` 和 `usePlanTableColumnLayout`；渲染缩放工具栏；表头每列有可访问的调整柄；列宽通过 CSS 变量或 `col` style 传入；横向滚动容器仍然是独立工作区。

```js
test('smart grid exposes zoom and drag-resize controls', () => {
  const source = requireSources(VIEW_FILE, CSS_FILE)
  assert.match(source, /usePlanTableZoom/)
  assert.match(source, /usePlanTableColumnLayout/)
  assert.match(source, /调整列宽/)
  assert.match(source, /onPointerDown/)
  assert.match(source, /style=\{\{ width:/)
  assert.match(source, /plan-table-toolbar/)
  assert.match(source, /v2-table-scroll/)
  assert.match(CSS_FILE === VIEW_FILE ? '' : read(CSS_FILE), /resize-handle/)
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm --prefix frontend-v2 exec -- node --test tests/projectWorkProgressWbs.test.mjs`

Expected: FAIL，因为当前表格没有接入缩放 Hook、列宽 Hook 和调整柄。

- [ ] **Step 3: 接入工具栏和列布局**

在 `PlanTableViewV2` 中：

1. 增加 `workspaceRef`，将其绑定到 `.v2-table-scroll`。
2. 使用 `usePlanTableZoom(workspaceRef)`，把 `zoomPercent`、缩放、适合宽度、重置视图接入已有 `PlanTableToolbar`。
3. 使用 `usePlanTableColumnLayout()`，`col` 元素宽度读取 `getColumnWidth(column.key)`。
4. 在每个 `th` 内增加 `button` 或 `span` 调整柄，使用 `onPointerDown={(event) => startResize(column.key, event)}`，并提供 `aria-label={`${column.label}列宽调整`}`。
5. 对表格画布设置 `style={{ zoom: `${zoomPercent / 100}` }}`，让放大缩小同步影响表格实际可滚动宽度。
6. 增加“恢复列宽”按钮，调用 `resetColumnWidths`；它只恢复网页视图，不改变业务数据。

- [ ] **Step 4: 重写宽表 CSS 层级**

调整 `planTableExcelV2.css`：

- `.v2-table-scroll` 保持双向滚动和 `overscroll-behavior: contain`。
- `.v2-table-canvas` 使用 `width: max-content`，不再让 11 列被父容器等比例挤压。
- `.v2-grid` 使用 `table-layout: fixed`，宽度完全由 `col` 的当前宽度决定。
- WBS、重点工作两列使用 sticky，表头使用更高的 z-index 和不透明背景，滚动时不透字。
- 表头调整柄覆盖在右边界，hover/focus 时显示明显的蓝色竖线和双向光标。
- 单元格默认 `white-space: pre-wrap; overflow-wrap: anywhere`，不使用会截断重要信息的 ellipsis；只对人员、状态等短字段保持单行。
- 远窄屏继续保留横向滚动，不把列压成竖排文字。

- [ ] **Step 5: 运行测试确认视图契约通过**

Run: `npm --prefix frontend-v2 exec -- node --test tests/projectWorkProgressWbs.test.mjs`

Expected: WBS 视图相关测试全部 PASS。

- [ ] **Step 6: 提交表格交互**

```bash
git add frontend-v2/src/components/task-management/PlanTableViewV2.tsx frontend-v2/src/components/task-management/planTableExcelV2.css frontend-v2/tests/projectWorkProgressWbs.test.mjs
git commit -m "feat: make project work progress table spreadsheet-like"
```

### Task 4: 视觉验证和回归检查

**Files:**
- Modify: `frontend-v2/tests/workProgressExcelView.test.mjs` only if the shared-column contract needs an explicit regression assertion.

- [ ] **Step 1: 运行全部相关测试**

Run: `npm --prefix frontend-v2 exec -- node --test tests/projectWorkProgressWbs.test.mjs tests/workProgressExcelView.test.mjs`

Expected: 0 failures。

- [ ] **Step 2: 运行单元测试和构建**

Run: `npm --prefix frontend-v2 run test:unit`

Expected: 现有单元测试全部 PASS。

Run: `npm --prefix frontend-v2 run build`

Expected: Vite 构建退出码为 0。

- [ ] **Step 3: 在开发页面进行视觉检查**

打开 `/work/tasks`，确认 1280px 左右窗口下：表格不再出现竖条式文字；表头固定；左右滚动可用；调整列宽后文字不被截断；缩放按钮改变表格实际宽度；恢复视图可以回到标准列宽；点击关键任务仍进入原有详情页。

- [ ] **Step 4: 检查导出一致性**

使用页面“导出 Excel”，确认 Excel 的列名和顺序仍与 `PLAN_TABLE_COLUMNS` 一致，且网页调整列宽不会改变导出的标准列宽或丢失长文本。

- [ ] **Step 5: 提交验证记录**

```bash
git add docs/superpowers/plans/2026-09-20-project-work-progress-smart-grid.md frontend-v2/tests/workProgressExcelView.test.mjs
git commit -m "docs: record smart grid verification"
```

## Self-review

- 字段统一：由 `PLAN_TABLE_COLUMNS` 和 `getPlanRowCellValue` 同时驱动网页与 Excel，覆盖。
- 不截断：CSS 去除重要文本列的强制 ellipsis，覆盖。
- 缩放：已有 `usePlanTableZoom` 接入工具栏并作用于实际画布，覆盖。
- 拉拽：新增列宽 Hook、表头调整柄和宽度约束，覆盖。
- 窄屏：采用横向滚动而不是压缩列，覆盖。
- 风险控制：网页个性化宽度不写回导出配置，覆盖。
