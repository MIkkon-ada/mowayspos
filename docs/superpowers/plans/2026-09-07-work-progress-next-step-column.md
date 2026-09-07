# 工作推进表下一步列 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在工作推进表末尾增加“下一步”列，展示每个关键任务最近一次已确认推进记录的下一步内容，并收窄“关键任务”列。

**Architecture:** 后端在批量关键任务列表的现有工作进展投影中，一次性查询每个关键任务最新的已确认执行事件并返回 `latest_next_step`。前端将该字段加入 `SubTaskItem`、计划行模型和表格末列，不改变现有详情页或提交流程。

**Tech Stack:** FastAPI, SQLAlchemy, React, TypeScript, CSS Modules-style component stylesheet.

---

### Task 1: 扩展批量关键任务投影

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/subtasks.py`
- Test reference: `bowei_ai_dashboard/tests/test_work_progress_latest_submission.py`

- [ ] 在 `_apply_work_progress_projection` 中批量查询 `KeyTaskExecutionEvent`，按 `key_task_id`、`effective_at`、`id` 倒序取每个关键任务最新的 `authority="confirmed"` 且 `affects_current_progress=True` 事件。
- [ ] 为每个返回项写入 `latest_next_step`，没有记录或内容为空时返回空字符串。

### Task 2: 贯通前端数据模型

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/components/task-management/planTableViewModel.ts`

- [ ] 在 `SubTaskItem` 增加可选的 `latest_next_step` 字段。
- [ ] 在 `PlanTableRow` 增加 `nextStep`，从关键任务的 `latest_next_step` 转换为空占位符 `—`。

### Task 3: 调整计划表布局

**Files:**
- Modify: `frontend/src/components/task-management/PlanTableViewV2.tsx`
- Modify: `frontend/src/components/task-management/planTableExcelV2.css`

- [ ] 使用比例列宽：重点工作 14%、关键任务 23%、负责人 6%、计划时间 9%、协同人 11%、最新已确认提交 18.5%、下一步 18.5%。
- [ ] 为表格设置 1120px 最小宽度，窄屏时允许横向滚动。
- [ ] 保持现有点击、合并单元格、sticky 列和空状态行为不变。

### Task 4: 验证

- [ ] 检查后端投影字段、前端列头和列宽差异。
- [ ] 按用户要求不运行测试命令。
