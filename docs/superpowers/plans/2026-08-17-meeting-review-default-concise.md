# Meeting Review Default Concise Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the meeting-review workspace show only decision-making information by default while retaining every source evidence record behind an explicit disclosure.

**Architecture:** Keep the existing `ProjectMeetingReviewWorkspace` data contract and owner-review callbacks unchanged. Change presentation only: collapse evidence in native `<details>`, remove default project-context/audit cards, omit duplicate title and nonessential metadata fields, and render empty confirmation/change sections only when they contain actionable content.

**Tech Stack:** React 19, TypeScript, Tailwind CSS, Vitest, Vite.

---

### Task 1: Lock the concise-review contract

**Files:**
- Create: `frontend/src/features/meeting/ProjectMeetingReviewWorkspace.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import fs from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('project meeting review workspace', () => {
  it('keeps evidence on demand and hides empty review sections', () => {
    const source = fs.readFileSync('src/features/meeting/ProjectMeetingReviewWorkspace.tsx', 'utf8')
    expect(source).toContain('<details')
    expect(source).toContain('查看原文依据')
    expect(source).toContain("['meeting_date', '会议日期']")
    expect(source).not.toContain("['title', '会议主题']")
    expect(source).toContain('{openQuestions.length ?')
    expect(source).toContain('{scheduleChanges.length ?')
    expect(source).not.toContain('aria-label="项目上下文"')
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm.cmd run test:unit -- src/features/meeting/ProjectMeetingReviewWorkspace.test.ts`

Expected: FAIL because the workspace currently renders source evidence and project-context cards by default.

### Task 2: Simplify the default owner-review view

**Files:**
- Modify: `frontend/src/features/meeting/ProjectMeetingReviewWorkspace.tsx:57-90`
- Modify: `frontend/src/features/meeting/ProjectMeetingReviewWorkspace.tsx:145-178`
- Test: `frontend/src/features/meeting/ProjectMeetingReviewWorkspace.test.ts`

- [ ] **Step 1: Make source evidence opt-in**

Render no component if an evidence set has no quotes. For available evidence, replace the always-open block with a native disclosure:

```tsx
return <details className="mt-2 text-xs text-slate-500">
  <summary className="cursor-pointer font-medium text-sky-700">查看原文依据{blocked ? '（待核验）' : ''}</summary>
  <ul className="mt-2 space-y-1 rounded-lg border border-dashed border-slate-200 bg-slate-50 p-3 text-slate-600">
    {quotes.map((quote, index) => <li key={`${quote}-${index}`}>“{quote}”</li>)}
  </ul>
</details>
```

- [ ] **Step 2: Keep only core meeting metadata on the default form**

Set `fieldLabels` to `meeting_type`, `meeting_date`, `location`, `host`, and `participants`. The meeting title stays in the page heading; organizer and copied-to remain stored in `editableDraft` and are not changed or deleted.

- [ ] **Step 3: Remove nonessential default panels**

Remove the `项目上下文` card and the header’s agent-audit line. Replace the draft helper text with `核对纪要内容；如需核验，可展开每项的原文依据。` and label the save action `保存修改`.

- [ ] **Step 4: Hide empty sections**

Render `待确认问题` only when `openQuestions.length > 0`; render `执行安排变更建议` only when `scheduleChanges.length > 0`. Do not modify the content, selection, lineage display, or review callbacks for nonempty sections.

- [ ] **Step 5: Run the targeted test**

Run: `npm.cmd run test:unit -- src/features/meeting/ProjectMeetingReviewWorkspace.test.ts`

Expected: PASS with one passing test.

- [ ] **Step 6: Run all frontend verification**

Run: `npm.cmd run test:unit; npm.cmd run build`

Expected: all unit tests pass and the production build succeeds.

### Task 3: Visually verify both states

**Files:**
- Modify: none

- [ ] **Step 1: Inspect a meeting with no schedule changes**

Expected: no project-context cards, no empty confirmation/change cards, no visible missing-evidence blocks, and the meeting title appears once.

- [ ] **Step 2: Inspect an evidence disclosure**

Expected: `查看原文依据` expands to the unchanged original Word quotes.

