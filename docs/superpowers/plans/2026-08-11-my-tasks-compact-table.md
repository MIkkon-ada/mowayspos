# My Tasks Compact Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove wasted height from the My Tasks table, preserve its existing data behavior, and make its overflow menu a viewport-aware floating interaction.

**Architecture:** `MyTasksPage` continues to own filters, pagination, and routes. `MyTasksTable` gains controlled local menu state and delegates above/below choice to a pure placement helper. CSS provides compact dimensions and positioning while preserving current columns and breakpoints.

**Tech Stack:** React 19, TypeScript, CSS, Node.js built-in test runner, Vite.

---

### Task 1: Add and test the menu placement helper

**Files:**
- Create: `frontend/src/features/my-tasks/menuPlacement.ts`
- Modify: `frontend/tests/myTasksPageStructure.test.mjs`

- [ ] **Step 1: Write the failing test**

Add `loadSourceModule(file)`, using the existing `ts.transpileModule` pattern, then add:

```js
test('overflow menu opens upward only when the viewport lacks lower space', async () => {
  const { getMyTaskMenuPlacement } = await loadSourceModule('src/features/my-tasks/menuPlacement.ts')
  assert.equal(getMyTaskMenuPlacement({ bottom: 400 }, 700, 120, 8), 'bottom')
  assert.equal(getMyTaskMenuPlacement({ bottom: 620 }, 700, 120, 8), 'top')
  assert.equal(getMyTaskMenuPlacement({ bottom: 580 }, 700, 112, 8), 'bottom')
})
```

- [ ] **Step 2: Run it and verify failure**

Run `node --test frontend/tests/myTasksPageStructure.test.mjs`. Expected: FAIL because `menuPlacement.ts` is missing.

- [ ] **Step 3: Implement the helper**

```ts
export type MenuTriggerBounds = Pick<DOMRect, 'bottom'>

export function getMyTaskMenuPlacement(trigger: MenuTriggerBounds, viewportHeight: number, menuHeight: number, gap: number): 'top' | 'bottom' {
  return viewportHeight - trigger.bottom < menuHeight + gap ? 'top' : 'bottom'
}
```

- [ ] **Step 4: Run the test and verify success**

Run `node --test frontend/tests/myTasksPageStructure.test.mjs`. Expected: PASS.

- [ ] **Step 5: Commit**

Run `git add frontend/src/features/my-tasks/menuPlacement.ts frontend/tests/myTasksPageStructure.test.mjs` then `git commit -m "test: cover task menu placement"`.

### Task 2: Replace native details with an accessible controlled menu

**Files:**
- Modify: `frontend/src/features/my-tasks/MyTasksTable.tsx`
- Modify: `frontend/tests/myTasksPageStructure.test.mjs`

- [ ] **Step 1: Write the failing structure test**

Add a test matching `useEffect, useRef, useState`, `getMyTaskMenuPlacement`, `openMenuId`, `aria-expanded={isMenuOpen}`, `my-task-actions-menu--top`, `event.key === 'Escape'`, and `!menuRoot.contains(event.target as Node)` in `MyTasksTable.tsx`.

- [ ] **Step 2: Run it and verify failure**

Run `node --test frontend/tests/myTasksPageStructure.test.mjs`. Expected: FAIL because the table still uses `details`.

- [ ] **Step 3: Implement local state and close behavior**

Import React hooks and `getMyTaskMenuPlacement`. Add `openMenuId`, `menuPlacement`, and `menuRootRef`. Replace each `details` with a `button` that toggles the row id and calculates placement from `event.currentTarget.getBoundingClientRect()` and `window.innerHeight`. Render the two existing actions only while open; add the `--top` modifier for upward placement. Add document `pointerdown` and Escape listeners that close the menu, and close before either navigation callback. Stop propagation on all row-action controls.

- [ ] **Step 4: Run the test and verify success**

Run `node --test frontend/tests/myTasksPageStructure.test.mjs`. Expected: PASS, including the existing three-action test.

- [ ] **Step 5: Commit**

Run `git add frontend/src/features/my-tasks/MyTasksTable.tsx frontend/tests/myTasksPageStructure.test.mjs` then `git commit -m "feat: control task overflow menu"`.

### Task 3: Apply compact, content-driven table styling

**Files:**
- Modify: `frontend/src/features/my-tasks/myTasks.css`
- Modify: `frontend/tests/myTasksPageStructure.test.mjs`

- [ ] **Step 1: Write the failing CSS contract test**

Assert that the CSS has header `height: 56px`, toolbar `min-height: 48px`, table card `height: auto` and `overflow: visible`, table cells `height: 76px`, and `.my-task-actions-menu--top` with `bottom: 38px`.

- [ ] **Step 2: Run it and verify failure**

Run `node --test frontend/tests/myTasksPageStructure.test.mjs`. Expected: FAIL because the current header is 64px and the card clips overflow.

- [ ] **Step 3: Implement the CSS contract**

Set `.my-tasks-header { height: 56px; }`, `.my-task-toolbar { min-height: 48px; padding: 7px 12px; }`, `.my-task-table-card { height: auto; overflow: visible; }`, `.my-task-table-scroll { overflow-x: auto; overflow-y: visible; }`, `.my-task-table td { height: 76px; }`, and `.my-task-actions-menu--top { top: auto; bottom: 38px; }`. Keep all seven columns, widths, horizontal scrolling, and responsive breakpoints.

- [ ] **Step 4: Run tests and verify success**

Run `node --test frontend/tests/myTasksPageStructure.test.mjs`. Expected: PASS.

- [ ] **Step 5: Commit**

Run `git add frontend/src/features/my-tasks/myTasks.css frontend/tests/myTasksPageStructure.test.mjs` then `git commit -m "style: compact my tasks table"`.

### Task 4: Verify the completed page

**Files:**
- Verify only: `frontend/src/features/my-tasks/MyTasksTable.tsx`
- Verify only: `frontend/src/features/my-tasks/myTasks.css`

- [ ] **Step 1: Run regression test**

Run `node --test frontend/tests/myTasksPageStructure.test.mjs`. Expected: all tests PASS.

- [ ] **Step 2: Build the frontend**

From `frontend`, run `npm run build`. Expected: TypeScript and Vite build both succeed.

- [ ] **Step 3: Check real interaction**

Open `/member/tasks` with one task: pagination must immediately follow the row; opening the menu must not alter list height; near the viewport bottom it must open upward; outside click and Escape must close it; all existing actions must still navigate. Under 900px, filters stack and the table remains horizontally scrollable.

- [ ] **Step 4: Commit only an adjustment found in verification**

If Step 3 requires a code adjustment, stage only the changed My Tasks files and use `git commit -m "fix: finalize compact task table behavior"`; otherwise do not create an extra commit.
