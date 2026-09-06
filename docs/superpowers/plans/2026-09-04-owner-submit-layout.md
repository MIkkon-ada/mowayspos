# 负责人提交方案页布局 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将负责人提交方案页实现为已确认的 B 方案布局，并移除多余字段、统计和重复展开 JSX。

**Architecture:** 保留 `OwnerSubmitModal` 现有数据状态与提交逻辑，只重写展示层：左侧是完整项目概览，右侧通过选中重点工作索引切换列表与详情，详情始终复用同一套编辑 JSX。用最小的展示模型和测试锁住文案与结构。

**Tech Stack:** React 19, TypeScript, Tailwind CSS, Vitest, Testing Library, Vite。

---

### Task 1: Add regression coverage for the agreed layout

**Files:**
- Create: `frontend/src/features/settings/OwnerSubmitModal.layout.test.tsx`
- Test target: `frontend/src/features/settings/OwnerSubmitModal.tsx`

- [ ] **Step 1: Write the failing test**

Render the modal with a project containing all overview fields and two workstreams, then assert the agreed labels/controls and the removed labels:

```tsx
it('renders the approved B layout without redundant workstream metadata', () => {
  render(<OwnerSubmitModal {...fixtureProps} />)

  expect(screen.getByText('项目概览')).toBeInTheDocument()
  expect(screen.getByText('P-TEST1')).toBeInTheDocument()
  expect(screen.getByText('负责人')).toBeInTheDocument()
  expect(screen.getByText('工作推进方案')).toBeInTheDocument()
  expect(screen.getByText('客户成功体系建设')).toBeInTheDocument()
  expect(screen.getByText('目标成果')).toBeInTheDocument()
  expect(screen.getByText('评价指标')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '返回项目详情' })).toHaveClass('bg-slate-50')
  expect(screen.queryByText('项目类型')).not.toBeInTheDocument()
  expect(screen.queryByText('客户名称')).not.toBeInTheDocument()
  expect(screen.queryByText('预期交付物')).not.toBeInTheDocument()
  expect(screen.queryByText('重点工作用于归类工作方向')).not.toBeInTheDocument()
  expect(screen.queryByText(/个关键任务/)).not.toBeInTheDocument()
  expect(screen.queryByText('继续新增重点工作')).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `npm run test:unit -- src/features/settings/OwnerSubmitModal.layout.test.tsx`

Expected: FAIL because the current component has the old overview title, collapsible details, redundant workstream metadata, old table label, and the bottom add button.

### Task 2: Replace the owner-submit presentation with the approved B structure

**Files:**
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx:836-1130`

- [ ] **Step 1: Implement the static overview and header constraints**

Use the approved labels and render all overview fields in the always-visible left card. Remove only the type/client/expected-outcomes fields from this page; keep project data available to other flows.

- [ ] **Step 2: Implement one workstream editor JSX path**

Introduce a selected workstream index for the B split view. Render the left workstream list from `draftTasks`, and render the selected task’s editable title, target result, time, and key-task table in one shared detail block. Keep add/remove/update handlers unchanged.

- [ ] **Step 3: Remove redundant controls and rename the evaluation column**

Remove task-count pills, the mobile task-count text, and the bottom “继续新增重点工作” button. Change only the table heading from `备注 / 标准` to `评价指标`; keep its input bound to `evaluation_standard`.

- [ ] **Step 4: Run the focused test**

Run: `npm run test:unit -- src/features/settings/OwnerSubmitModal.layout.test.tsx`

Expected: PASS.

### Task 3: Typecheck, build, and visually verify

**Files:**
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx` only, if verification finds a type/layout issue.

- [ ] **Step 1: Run all frontend unit tests**

Run: `npm run test:unit`

Expected: PASS.

- [ ] **Step 2: Run the production build**

Run: `npm run build`

Expected: TypeScript compilation and Vite build complete successfully.

- [ ] **Step 3: Inspect the running local page**

Open `http://localhost:52341/` and verify the left overview is always expanded, the active workstream list and detail are aligned, the header button has a normal background, and the fixed footer remains visible.
