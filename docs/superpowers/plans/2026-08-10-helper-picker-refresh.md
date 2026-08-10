# 协助人多选下拉刷新 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将协助人输入改为责任人同款搜索下拉视觉，同时保留多人选择和移除。

**Architecture:** 在 `OwnerSubmitModal.tsx` 中抽取可复用的多选人员选择器，按钮和弹出层沿用现有 `AssigneePicker` 的定位与 portal 方案。选择器通过 `helperIds` 受控，提交数据保持现有 `helperIds`/`helper` 映射。

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Node test runner, Vite。

---

### Task 1: Write the failing interaction test

**Files:**
- Modify: `frontend/tests/ownerSubmitModalLayout.test.mjs`

- [ ] **Step 1: Add assertions for the helper multi-select UI**

Assert the source contains a helper picker component, multi-select toggle behavior, and the helper placeholder.

- [ ] **Step 2: Run the focused test and verify it fails**

Run `node --test tests/ownerSubmitModalLayout.test.mjs` from `frontend/`. Expected: FAIL because the current source still renders helper checkboxes directly in the table cell.

### Task 2: Implement the controlled multi-select picker

**Files:**
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx`

- [ ] **Step 1: Extract `HelperPicker` next to `AssigneePicker`**

Give it `people`, `value`, `disabled`, and `onChange` props; filter candidates by name/department; render selected names as tags and a searchable portal menu.

- [ ] **Step 2: Replace the helper checkbox list**

Pass `subtask.helperIds` into `HelperPicker`, update through `toggleSubTaskHelper`, and preserve exclusion of the selected responsible person.

### Task 3: Verify and commit

**Files:**
- Test: `frontend/tests/ownerSubmitModalLayout.test.mjs`
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx`

- [ ] **Step 1: Run the focused test**

Run `node --test tests/ownerSubmitModalLayout.test.mjs`; expected PASS.

- [ ] **Step 2: Run the production build**

Run `npm run build`; expected TypeScript and Vite build success.

- [ ] **Step 3: Check the diff and commit only the scoped files**

Run `git diff --check`, then commit with `feat: refresh helper multi-select picker`.
