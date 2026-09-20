# 项目工作推进表 Excel 工作表感改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute this plan inline in the current isolated worktree; do not delegate to subagents.

**Goal:** 把项目工作推进表从网页卡片式宽表改成接近 Excel/企业微信智能表格的工作表视图，同时保留现有 WBS 字段、详情入口、筛选和导出能力。

**Architecture:** 不改变 `PLAN_TABLE_COLUMNS`、行模型和导出逻辑，只重做 `PlanTableViewV2` 的工作表语义与 `planTableExcelV2.css` 的视觉层。表格仍使用合并单元格表达重点工作与交付成果，但单元格内部取消卡片容器，增加紧凑网格、冻结分割线、单元格选中反馈和明确的水平滚动轨道。

**Tech Stack:** React + TypeScript + CSS、Node.js `node:test`、Vite。

---

### Task 1: 固化 Excel 工作表视图契约

**Files:**
- Modify: `frontend-v2/tests/projectWorkProgressWbs.test.mjs`
- Modify: `frontend-v2/src/components/task-management/PlanTableViewV2.tsx`

- [ ] **Step 1: 写失败测试**

增加源代码契约，要求表格具备工作表工具栏、单元格选中状态、数据行号、清晰的冻结分割层以及非卡片式重点工作内容类名。

- [ ] **Step 2: 运行测试确认失败**

Run: `npm --prefix frontend-v2 exec -- node --test tests/projectWorkProgressWbs.test.mjs`

Expected: 新增契约失败，因为当前视图没有 active-cell、row-number 和 worksheet toolbar 标记。

- [ ] **Step 3: 实现视图标记**

在表格左侧增加窄行号列；为每个数据单元格增加可聚焦的 `tabIndex`/`aria-label` 和 active cell 状态；保留整行打开详情的能力，但单元格点击先呈现选中反馈。将“拖拽列宽”的提示收进紧凑工具栏。

- [ ] **Step 4: 运行聚焦测试**

Run: `npm --prefix frontend-v2 exec -- node --test tests/projectWorkProgressWbs.test.mjs`

Expected: 新增工作表结构契约通过。

- [ ] **Step 5: 提交**

```bash
git add frontend-v2/tests/projectWorkProgressWbs.test.mjs frontend-v2/src/components/task-management/PlanTableViewV2.tsx
git commit -m "feat: add worksheet interaction structure"
```

### Task 2: 重做表格视觉层

**Files:**
- Modify: `frontend-v2/src/components/task-management/planTableExcelV2.css`

- [ ] **Step 1: 写样式契约测试**

断言 CSS 包含紧凑行高、工作表网格、active cell、冻结分割线、底部水平滚动条和无卡片化重点工作样式，并禁止重点工作内容继续使用大圆角卡片背景。

- [ ] **Step 2: 运行测试确认失败**

Run: `npm --prefix frontend-v2 exec -- node --test tests/projectWorkProgressWbs.test.mjs`

Expected: 样式契约失败。

- [ ] **Step 3: 实现工作表样式**

将工作表主体改为白色、细网格、24-32px 的紧凑行高；表头使用浅灰实色；重点工作和交付成果保留合并关系但改为普通单元格排版；状态改为轻量单元格色标；冻结列增加明显的竖向边界；工具栏收紧成一条；滚动区域提供底部水平滚动空间。

- [ ] **Step 4: 运行测试和构建**

Run: `npm --prefix frontend-v2 exec -- node --test tests/projectWorkProgressWbs.test.mjs tests/workProgressExcelView.test.mjs`

Run: `npm --prefix frontend-v2 run build`

Expected: 全部通过，构建退出码为 0。

- [ ] **Step 5: 提交**

```bash
git add frontend-v2/src/components/task-management/planTableExcelV2.css frontend-v2/tests/projectWorkProgressWbs.test.mjs
git commit -m "feat: restyle work progress table as spreadsheet"
```

### Task 3: 浏览器复核

**Files:** 无新增文件。

- [ ] **Step 1: 查看 `/work/tasks`**

确认首屏表格占据主要空间，能同时看到 WBS、重点工作、关键任务和交付成果，且不出现竖条式文字。

- [ ] **Step 2: 复核交互**

点击单元格确认出现选中反馈；横向滚动确认 WBS/重点工作冻结；拖拽列宽确认表格仍保持网格；点击关键任务确认原详情入口没有丢失；导出 Excel 仍可用。

- [ ] **Step 3: 运行完整单元测试**

Run: `npm --prefix frontend-v2 run test:unit`

Expected: 全部测试通过。

