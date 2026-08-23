# Key Task Column Width Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the Key Task column in the work-progress overview from 430px to 360px while retaining automatic wrapping.

**Architecture:** The visible table layout is controlled by the `colgroup` in `PlanTableViewV2.tsx`; no model, API, or workspace-detail changes are needed. A source-level Node test will protect the fixed column contract.

**Tech Stack:** React, TypeScript, Vite, Node built-in test runner.

---

### Task 1: Lock and apply the Key Task column width

**Files:**
- Modify: `frontend/tests/workProgressExcelView.test.mjs`
- Modify: `frontend/src/components/task-management/PlanTableViewV2.tsx`

- [ ] **Step 1: Write the failing test**

```js
assert.match(source, /<col style=\{\{ width: 300 \}\} \/><col style=\{\{ width: 360 \}\} \/>/)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test tests/workProgressExcelView.test.mjs`

Expected: FAIL because the second `col` is currently 430px.

- [ ] **Step 3: Write minimal implementation**

```tsx
<colgroup><col style={{ width: 300 }} /><col style={{ width: 360 }} /><col style={{ width: 80 }} />
```

- [ ] **Step 4: Run verification**

Run: `node --test tests/workProgressExcelView.test.mjs && npm run build`

Expected: all selected tests and production build pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/task-management/PlanTableViewV2.tsx frontend/tests/workProgressExcelView.test.mjs
git commit -m "style: narrow key task table column"
```
