# Meeting List Column Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep every meeting-list field readable by constraining long meeting types to their own column and preserving the complete meeting time.

**Architecture:** The change stays within the existing `MeetingPage` table. Its percentage-based columns become explicit minimum content widths within an overflow container, and the meeting-type badge gains an inner truncation boundary. A source-level Vitest regression test asserts the non-overlapping table contract.

**Tech Stack:** React 19, TypeScript, Tailwind CSS, Vitest, Vite.

---

### Task 1: Lock the meeting-list readability contract

**Files:**
- Create: `frontend/src/pages/MeetingPage.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import fs from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('meeting list column layout', () => {
  it('keeps meeting time in a fixed readable column and clips only the meeting type label', () => {
    const source = fs.readFileSync('src/pages/MeetingPage.tsx', 'utf8')
    expect(source).toContain('min-w-[1040px]')
    expect(source).toContain("width: '220px'")
    expect(source).toContain('max-w-full')
    expect(source).toContain('truncate')
    expect(source).toContain("width: '150px'")
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm.cmd run test:unit -- src/pages/MeetingPage.test.ts`

Expected: FAIL because `MeetingPage.tsx` still uses percentage widths and has no constrained meeting-type label.

- [ ] **Step 3: Commit the red test**

```powershell
git add frontend/src/pages/MeetingPage.test.ts
git commit -m "test: cover meeting list column readability"
```

### Task 2: Prevent type labels from covering adjacent columns

**Files:**
- Modify: `frontend/src/pages/MeetingPage.tsx:724-730`
- Modify: `frontend/src/pages/MeetingPage.tsx:758-762`
- Test: `frontend/src/pages/MeetingPage.test.ts`

- [ ] **Step 1: Replace percentage columns with a minimum-width table contract**

Replace the table and colgroup opening with:

```tsx
<div className="overflow-x-auto">
  <table className="min-w-[1040px] w-full table-fixed text-sm">
    <colgroup>
      <col style={{ width: '330px' }} />
      <col style={{ width: '220px' }} />
      <col style={{ width: '150px' }} />
      <col style={{ width: '110px' }} />
      <col style={{ width: '150px' }} />
      <col style={{ width: '120px' }} />
    </colgroup>
```

This leaves the existing `overflow-x-auto` wrapper in place, so narrow viewports scroll rather than compress data columns.

- [ ] **Step 2: Constrain the meeting type label inside its own cell**

Replace the meeting-type cell with:

```tsx
<td className="px-5 py-3.5 align-middle">
  <span
    className={`inline-flex max-w-full min-w-0 items-center rounded-md px-2 py-0.5 text-xs font-medium ${TYPE_STYLE[typeLabel(m.meeting_type)] ?? 'bg-slate-100 text-slate-600'}`}
    title={typeLabel(m.meeting_type)}
  >
    <span className="truncate">{typeLabel(m.meeting_type)}</span>
  </span>
</td>
```

The visible label truncates only within the 220px type column; its browser tooltip retains the complete value.

- [ ] **Step 3: Run the targeted test**

Run: `npm.cmd run test:unit -- src/pages/MeetingPage.test.ts`

Expected: PASS with one passing test.

- [ ] **Step 4: Run the complete frontend verification**

Run: `npm.cmd run test:unit; npm.cmd run build`

Expected: all unit tests pass and the TypeScript/Vite build completes.

- [ ] **Step 5: Commit the implementation**

```powershell
git add frontend/src/pages/MeetingPage.tsx frontend/src/pages/MeetingPage.test.ts
git commit -m "fix: keep meeting list columns readable"
```

### Task 3: Verify the visual regression in the local application

**Files:**
- Modify: none

- [ ] **Step 1: Start the existing local frontend and backend launchers**

Run the local frontend at `http://127.0.0.1:6004` and the safe backend at `http://127.0.0.1:8011`.

- [ ] **Step 2: Inspect the AI升级计划 meeting list at desktop width**

Expected: the complete `2026/7/27 08:00` timestamp is visible; the long type label remains in its own column and ends in an ellipsis when necessary.

- [ ] **Step 3: Inspect at a narrow width**

Expected: the table offers horizontal scrolling; no cell covers another column, and meeting time, status, and actions remain readable.

