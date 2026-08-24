# Unified Dropdown Chevron Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every selectable, expandable, and dropdown control render the same chevron geometry as the reference project selector.

**Architecture:** Preserve the existing global `<select>` SVG as the canonical geometry: a 14px, 24×24, grey-blue rounded polyline. Extract the same geometry into a shared React icon for explicit controls, and add an opt-in disclosure CSS class for controls currently showing browser markers. Retain ellipsis menus as ellipsis menus.

**Tech Stack:** React 19, TypeScript, Tailwind CSS, CSS custom properties, Node built-in test runner, Vite.

---

### Task 1: Lock the reference chevron geometry with tests

**Files:**
- Modify: `frontend/tests/meetingDetailWorkspace.test.mjs`
- Create: `frontend/tests/unifiedDropdownChevron.test.mjs`

- [ ] **Step 1: Write failing structural tests**

```js
assert.match(icon, /viewBox="0 0 24 24"/)
assert.match(icon, /strokeWidth="2\.5"/)
assert.match(icon, /<polyline points="6 9 12 15 18 9"/)
assert.doesNotMatch(archive, /⌄|⌃/)
```

- [ ] **Step 2: Verify the test fails**

Run: `node --test --test-name-pattern="unified dropdown" tests/unifiedDropdownChevron.test.mjs`

Expected: FAIL because no shared canonical icon or consistent disclosure classes exist.

- [ ] **Step 3: Implement only the test-supported changes in Tasks 2–4**

- [ ] **Step 4: Verify the new test passes**

Run: `node --test tests/unifiedDropdownChevron.test.mjs`

Expected: PASS with zero failures.

### Task 2: Establish one reusable Chevron component and select background

**Files:**
- Create: `frontend/src/components/icons/ChevronDownIcon.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/components/ProjectSelector.tsx`

- [ ] **Step 1: Add the shared icon with the reference geometry**

```tsx
export function ChevronDownIcon({ className = 'h-3.5 w-3.5' }: { className?: string }) {
  return <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9" /></svg>
}
```

- [ ] **Step 2: Name the existing encoded select image `--dropdown-chevron-image` and reuse it for all selects**

```css
:root { --dropdown-chevron-image: url("data:image/svg+xml,..."); }
select { background-image: var(--dropdown-chevron-image); }
```

- [ ] **Step 3: Restore the global background image after `ProjectSelector` uses inline background shorthand**

```ts
backgroundImage: 'var(--dropdown-chevron-image)',
backgroundRepeat: 'no-repeat',
backgroundPosition: 'right 8px center',
backgroundSize: '14px',
```

### Task 3: Replace variant explicit chevrons and text arrows

**Files:**
- Modify: `frontend/src/features/meeting/MeetingDetailWorkspace.tsx`
- Modify: `frontend/src/features/settings/AIModelDrawer.tsx`
- Modify: `frontend/src/pages/ConfirmPage.tsx`
- Modify: `frontend/src/features/project-archive/ArchiveOverview.tsx`
- Modify: `frontend/src/components/key-task-workspace/KeyTaskHeader.tsx`
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx`
- Modify: `frontend/src/features/settings/ProjectsMgmtSection.tsx`
- Modify: `frontend/src/features/voice-update/VoiceUpdateTaskBindingBar.tsx`
- Modify: `frontend/src/features/voice-update/voiceUpdateFlow.css`

- [ ] **Step 1: Replace each local SVG and `⌄`/`⌃` text symbol with `ChevronDownIcon`**

```tsx
<ChevronDownIcon className={`h-3.5 w-3.5 transition-transform ${open ? 'rotate-180' : ''}`} />
```

- [ ] **Step 2: Keep three-dot overflow triggers unchanged**

```tsx
<summary aria-label={`重点工作 ${taskIndex + 1} 更多操作`}>···</summary>
```

- [ ] **Step 3: Remove sideways `›` indicators from the two expandable settings summaries**

- [ ] **Step 4: Replace the CSS border-based scope selector arrow with `ChevronDownIcon`, while retaining its placement class**

### Task 4: Replace browser disclosure markers with the same chevron

**Files:**
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/features/voice-update/VoiceUpdateTaskReportsSection.tsx`
- Modify: `frontend/src/pages/MeetingPage.tsx`
- Modify: `frontend/src/features/meeting/ProjectMeetingReviewWorkspace.tsx`
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx`
- Modify: `frontend/src/features/settings/ProjectsMgmtSection.tsx`

- [ ] **Step 1: Add a scoped disclosure style that hides browser markers and appends the canonical image**

```css
.app-disclosure > summary { display: flex; align-items: center; gap: .375rem; list-style: none; }
.app-disclosure > summary::-webkit-details-marker { display: none; }
.app-disclosure > summary::after { content: ''; width: 14px; height: 14px; background: var(--dropdown-chevron-image) center / 14px no-repeat; transition: transform .15s; }
.app-disclosure[open] > summary::after { transform: rotate(180deg); }
```

- [ ] **Step 2: Add `app-disclosure` to every text-based `<details>` summary that currently relies on a browser marker**

```tsx
<details className="app-disclosure ..."><summary>查看原文依据</summary>...</details>
```

- [ ] **Step 3: Do not apply the class to summaries that already render an explicit icon or an ellipsis**

### Task 5: Verify source, tests, and compilation

**Files:**
- Modify: `frontend/tests/unifiedDropdownChevron.test.mjs`

- [ ] **Step 1: Run focused icon tests**

Run: `node --test tests/unifiedDropdownChevron.test.mjs tests/meetingDetailWorkspace.test.mjs`

Expected: the new source checks pass; report the known unrelated `NewMeetingModal` meeting-type assertion separately if it remains.

- [ ] **Step 2: Run formatting and production build checks**

Run: `git diff --check -- frontend/src frontend/tests/unifiedDropdownChevron.test.mjs && npm run build`

Expected: no whitespace errors and an exit code of 0 from Vite.
