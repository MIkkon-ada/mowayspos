# Project Init Workbook Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让项目管理页导入真实工作推进表时，按表头、行和合并单元格确定性识别每项重点工作、目标成果、关键任务、负责人、协助人、时间和评价指标，并生成包含全部角色信息的完整推进表草稿。

**Architecture:** 保留现有上传、异步分析、AI 预览和 `owner-submit` 接口边界；在 Excel 解析阶段识别推进表表头并为每条数据行保留精确来源范围，在结构化导入阶段继承合并单元格的父级字段并把人员字段分配到正确层级。只有非推进表文件或无法确定表结构时才继续使用 AI 提取，所有人员 ID 仍由服务端确定性匹配。

**Tech Stack:** Python, FastAPI service layer, openpyxl/xlrd, pytest, existing React/TypeScript preview.

---

### Task 1: Make Excel worksheet parsing detect real work-plan headers

**Files:**
- Modify: `bowei_ai_dashboard/app/services/project_init_file_parser.py`
- Test: `bowei_ai_dashboard/tests/test_project_init_file_parser.py`

- [ ] **Step 1: Write failing tests** for a title row, sparse/merged header row, and a work-plan table that must emit one header-plus-row chunk per data row with the actual table column range.
- [ ] **Step 2: Run the parser tests** and verify the new cases fail because the current parser falls back to a whole-sheet range.
- [ ] **Step 3: Implement header detection** that recognizes multiple known work-plan headers even when unrelated title columns or blank cells exist, while preserving the existing dense generic-table behavior.
- [ ] **Step 4: Run parser tests** and verify old and new cases pass.

### Task 2: Preserve parent fields and all task roles through structured workbook mapping

**Files:**
- Modify: `bowei_ai_dashboard/app/services/project_init_ai_agent.py`
- Test: `bowei_ai_dashboard/tests/test_project_init_ai_agent.py`

- [ ] **Step 1: Write failing tests** for merged workstream values, target/result columns, task owner, task assignee, multiple helpers, date columns, status and evaluation criteria.
- [ ] **Step 2: Run the focused agent tests** and verify missing inherited values or incorrect role placement fails.
- [ ] **Step 3: Implement deterministic row-context inheritance** for workstream title, target/result, coordinator, dates and other explicitly merged parent fields; keep the key-task owner and helper columns on the subtask.
- [ ] **Step 4: Extend header aliases** for the real workbook vocabulary such as `目标`, `计划计划结束时间`, `完成情况`, and equivalent labels without changing API field names.
- [ ] **Step 5: Run focused agent tests** and verify no LLM call is made for a recognized work-plan workbook.

### Task 3: Verify complete owner-submit projection and review preview

**Files:**
- Inspect/modify only if required: `bowei_ai_dashboard/app/features/settings/OwnerSubmitAiPanel.tsx`, `frontend/src/features/settings/OwnerSubmitModal.tsx`, `bowei_ai_dashboard/app/routers/projects.py`
- Test: `bowei_ai_dashboard/tests/test_project_init_work_progress_draft.py`, existing frontend owner-submit tests

- [ ] **Step 1: Add an end-to-end service test** that parses a multi-row workbook and projects every mapped field into the existing `ProjectProfilePayload` shape without changing routes or endpoints.
- [ ] **Step 2: Run the test** and inspect the persisted `Task`, `SubTask`, project members and role values.
- [ ] **Step 3: Fix only a confirmed projection gap**, preserving the current owner-submit transaction, personnel validation and audit behavior.
- [ ] **Step 4: Run backend and frontend regression suites.**

### Task 4: Runtime verification

**Files:**
- No production changes unless a test exposes a regression.

- [ ] **Step 1: Run the focused parser/agent/project-init tests.**
- [ ] **Step 2: Run the complete frontend unit suite and production build.**
- [ ] **Step 3: Restart the local frontend and proxy-compatible backend, verify `/api/setup/status`, and open the owner-submit route without submitting or applying data.**
- [ ] **Step 4: Report any remaining limitation for files whose layout is not structurally identifiable instead of silently guessing.**
