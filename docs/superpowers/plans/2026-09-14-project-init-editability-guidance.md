# 项目立项编辑权限与状态提示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在项目立项页面按真实生命周期控制编辑能力，并在不可编辑时提供清晰的中文原因提示。

**Architecture:** 复用 `projectLifecycleStatus` 的状态解析与标签，增加面向项目立项编辑的纯函数提示逻辑；`OwnerSubmitWorkbench` 根据该状态将右侧工作推进方案置为可编辑或只读。后端不放宽现有 `dispatched/returned` 写入限制。

**Tech Stack:** React、TypeScript、Vitest、FastAPI、Pytest。

---

### Task 1: 固化项目立项可编辑状态规则

**Files:**
- Modify: `frontend/src/domain/projectLifecycleStatus.ts`
- Test: `frontend/src/domain/projectLifecycleStatus.test.ts`

- [ ] **Step 1: Write the failing tests**

增加以下行为断言：`dispatched` 和 `returned` 返回可编辑；`pending_review` 返回审核中只读提示；`active` 返回执行中不可编辑提示；未知状态返回通用不可编辑提示。

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `npm run test:unit -- --run src/domain/projectLifecycleStatus.test.ts`

Expected: FAIL because the new project-init editability message helper does not exist。

- [ ] **Step 3: Implement the minimal status helpers**

在 `projectLifecycleStatus.ts` 中复用 `getProjectPrimaryStatus` 与 `getProjectStatusLabel`，导出：

```ts
export function canEditProjectInit(project?: ProjectLifecycleLike | null): boolean {
  const status = getProjectPrimaryStatus(project)
  return status === 'dispatched' || status === 'returned'
}

export function getProjectInitEditNotice(project?: ProjectLifecycleLike | null): string {
  const status = getProjectPrimaryStatus(project)
  if (status === 'pending_review') return '项目已提交审核，当前只能查看，需审核退回后才能继续完善。'
  if (!status) return '项目状态未知，暂不能编辑工作推进表。'
  return `项目当前为“${getProjectStatusLabel(project)}”状态，需进入已派发或已退回状态后才能编辑。`
}
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `npm run test:unit -- --run src/domain/projectLifecycleStatus.test.ts`

Expected: all lifecycle tests pass。

### Task 2: 将项目负责人工作台改为状态感知

**Files:**
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx`
- Test: `frontend/src/features/settings/OwnerSubmitModal.layout.test.tsx`

- [ ] **Step 1: Write the failing UI tests**

增加 `pending_review` 场景断言：显示“待审核”和只读说明；`AI 分析文件 / AI 草稿`、`+ 新增重点工作`、`提交立项审核` 均为 disabled；`dispatched` 场景继续显示可用的编辑入口。

- [ ] **Step 2: Run the focused UI test and verify it fails**

Run: `npm run test:unit -- --run src/features/settings/OwnerSubmitModal.layout.test.tsx`

Expected: FAIL because the current header写死“待负责人完善”，且编辑按钮没有按生命周期禁用。

- [ ] **Step 3: Implement status-aware rendering**

在 `OwnerSubmitWorkbench` 中读取 `canEditProjectInit(project)`、`getProjectStatusBadge(project)` 和 `getProjectInitEditNotice(project)`；将标题徽章改为真实状态；在工作推进方案上方显示只读说明；用 disabled fieldset 包裹右侧编辑区，并让底部提交按钮在只读态禁用。

- [ ] **Step 4: Run the focused UI test and verify it passes**

Run: `npm run test:unit -- --run src/features/settings/OwnerSubmitModal.layout.test.tsx`

Expected: all OwnerSubmitModal layout tests pass。

### Task 3: 回归验证与边界检查

**Files:**
- No new production files.
- Verify: `frontend/src/features/settings/OwnerSubmitAiPanel.tsx`
- Verify: `bowei_ai_dashboard/app/routers/project_init_ai.py`

- [ ] **Step 1: Run frontend full tests**

Run: `npm run test:all` from `frontend`。

Expected: all existing frontend unit and contract tests pass。

- [ ] **Step 2: Run backend project-init tests**

Run: `python -m pytest tests/test_project_init_analysis.py tests/test_project_init_attachments.py -q` from `bowei_ai_dashboard`。

Expected: all project-init lifecycle and attachment security tests pass。

- [ ] **Step 3: Build and check whitespace**

Run: `npm run build` from `frontend`, then `git diff --check` from the repository root。

Expected: TypeScript/Vite build succeeds and `git diff --check` emits no whitespace errors。
