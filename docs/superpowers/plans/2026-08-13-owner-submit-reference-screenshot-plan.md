# OwnerSubmitModal Screenshot-Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the owner-submit workbench with the approved screenshot without changing its business behavior.

**Architecture:** Update only `OwnerSubmitModal.tsx` markup and Tailwind classes, plus source-structure assertions in `ownerSubmitModalLayout.test.mjs`. Existing state, callbacks, Pickers, AI integration, audit and submit functions remain untouched.

**Tech Stack:** React, TypeScript, Tailwind CSS, Node `node:test`, Vite.

---

### Task 1: Add the screenshot-reference structural contract

**Files:**
- Modify: `frontend/tests/ownerSubmitModalLayout.test.mjs`

- [ ] Write assertions for display-first project summary classes, task status/task-count/date-range affordances, inline presentation icons, and preserved editable six-column table.
- [ ] Run `cd frontend; node --test tests/ownerSubmitModalLayout.test.mjs` and verify the new assertions fail on the prior markup.

### Task 2: Apply the visual reference without behavioral edits

**Files:**
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx`

- [ ] Change only JSX structure and class names around summary, task headers, collapsed summaries, table adornments, and action buttons.
- [ ] Do not edit `expandedTaskIndexes`, `addTaskDraft`, `removeTaskDraft`, AI merge functions, Pickers, audit or submit functions.
- [ ] Re-run `cd frontend; node --test tests/ownerSubmitModalLayout.test.mjs` and verify it passes.

### Task 3: Regression and visual acceptance

**Files:**
- Verify: `frontend/tests/ownerSubmitAiIntegration.test.mjs`
- Verify: `frontend/tests/ownerSubmitAiPanelBehavior.test.mjs`

- [ ] Run the two AI protection suites, all frontend Node tests, and `npm run build`.
- [ ] Use the real Modal local state to create one expanded and two collapsed tasks; inspect 1440px, 1600px, and 1920px; do not submit.
- [ ] Commit only verified source, test, and documentation changes and push the existing Draft PR branch.
