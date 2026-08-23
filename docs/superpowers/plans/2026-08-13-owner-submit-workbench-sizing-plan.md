# OwnerSubmitModal Workbench Sizing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixed near-fullscreen OwnerSubmitModal shell with content-driven dimensions and a viewport-safe internal scroll boundary.

**Architecture:** The existing overlay remains responsible for safe spacing. The shell becomes a bounded flex column; Header and Footer retain `shrink-0`, while Main retains the sole `overflow-y-auto` scroll region. No application state or callbacks change.

**Tech Stack:** React, TypeScript, Tailwind CSS, Node `node:test`, Vite.

---

### Task 1: Add the shell sizing contract

**Files:**
- Modify: `frontend/tests/ownerSubmitModalLayout.test.mjs`

- [ ] Add a focused assertion that the shell has `w-full`, `max-w-[1400px]`, a viewport-safe max height, and no `h-[94vh]`.
- [ ] Assert that Main retains `min-h-0`, `flex-1`, `overflow-x-hidden`, and `overflow-y-auto`.
- [ ] Run `cd frontend; node --test tests/ownerSubmitModalLayout.test.mjs` and verify the new assertion fails against the old 94vh/1560px shell.

### Task 2: Apply the sizing-only shell change

**Files:**
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx`

- [ ] Replace only the shell sizing utility classes with `w-full max-w-[1400px] min-h-[640px] max-h-[calc(100vh-48px)]` and remove `h-[94vh]`.
- [ ] Preserve existing Header, Main, Footer, project, task, AI, picker, and submit markup and callbacks.
- [ ] Re-run `cd frontend; node --test tests/ownerSubmitModalLayout.test.mjs` and verify it passes.

### Task 3: Verify bounded growth

**Files:**
- Verify: `frontend/tests/ownerSubmitAiIntegration.test.mjs`
- Verify: `frontend/tests/ownerSubmitAiPanelBehavior.test.mjs`

- [ ] Verify one, three, and six-to-eight local draft tasks at 1440x900, 1600x900, and 1920x1080 without submitting data.
- [ ] Run focused tests, complete frontend Node tests, and `npm run build`.
- [ ] Commit and push the existing Draft PR branch only after verification succeeds.
