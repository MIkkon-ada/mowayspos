# Owner Submit Workbench Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rework the负责人填写立项信息 modal into a compact, clearer workbench without changing its data payload or submission behavior.

**Architecture:** Keep `OwnerSubmitModal` as the single stateful component and preserve `ownerSubmitProfile`, `toPayloadDraft`, people loading, and validation. Refine the modal hierarchy with a compact header, narrower summary rail, grouped work-plan cards, contained people picker, and slim sticky footer; use local component classes/Tailwind utilities rather than a broad app-wide redesign.

**Tech Stack:** React 19, TypeScript, Tailwind utility classes, existing frontend API and toast helpers.

---

### Task 1: Establish the compact workbench shell

**Files:**
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx`

- [ ] **Step 1: Replace the modal shell classes**

Change the outer modal to use a responsive `max-w-[1440px]`, a shorter header, a two-column body with a narrower left rail, and a `sticky bottom-0` footer. Keep the existing click-to-close and `fillLoading` guards unchanged.

- [ ] **Step 2: Add visual hierarchy to the header and summary rail**

Keep the existing project name/status values, but use compact title metadata and reduce the summary card width. Keep the detailed-information `<details>` section and all bound state fields intact.

- [ ] **Step 3: Run TypeScript build**

Run `npm run build` from `frontend`. Expected: the existing project compiles without TypeScript errors.

### Task 2: Rework work-plan cards and people selection presentation

**Files:**
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx`

- [ ] **Step 1: Restyle重点工作 headers and fields**

Keep the existing `draftTasks.map`, update handlers, and add/remove callbacks. Use a denser card header with a numbered badge, title input, target/result input, and a compact overflow-safe remove action.

- [ ] **Step 2: Restyle the subtask table**

Keep every existing input/select binding and table column. Apply fixed/minimum column widths, clearer header contrast, compact row spacing, and a contained horizontal overflow wrapper so the table remains usable on narrow screens.

- [ ] **Step 3: Contain the helper list**

Keep the existing `people.filter(...).map(...)` checkbox list and `toggleSubTaskHelper` behavior. Wrap it in a bounded `max-h` scroll container with subtle surface styling so the list cannot expand the modal or cover unrelated content.

- [ ] **Step 4: Run TypeScript build**

Run `npm run build` from `frontend`. Expected: PASS with no new errors.

### Task 3: Refine footer and responsive states

**Files:**
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx`

- [ ] **Step 1: Make the footer compact and action-focused**

Preserve the cancel and submit handlers, disabled state, loading label, and existing button text. Reduce footer height, keep it visible while the body scrolls, and visually emphasize the submit action.

- [ ] **Step 2: Validate modal behaviors**

Use the running local app to verify: opening the modal, adding/removing重点工作, adding/removing关键任务, selecting a负责人, checking multiple协助人, scrolling on a narrow viewport, and submitting with the existing validation rules.

- [ ] **Step 3: Run final build and inspect git diff**

Run `npm run build` and `git diff --check`. Expected: both succeed; only the modal source and this plan/spec documentation are part of this change, and unrelated dirty files remain untouched.
