# Desktop Responsive Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the authenticated desktop application remain usable while the browser content width changes continuously from 800px through ultrawide sizes.

**Architecture:** Keep the existing React and Tailwind structure, add CSS-only breakpoint behavior, and avoid JavaScript resize state. The global shell owns sidebar compaction and Flex shrink constraints; each core page owns its grid reflow, toolbar wrapping, and local overflow boundaries.

**Tech Stack:** React 19, TypeScript, Tailwind CSS 3, Node built-in test runner, Vite, in-app browser viewport testing

---

## File map

- Create `frontend/tests/desktopResponsiveLayout.test.mjs`: source-level regression checks for the shell and four affected pages.
- Modify `frontend/src/layouts/ProjectLayout.tsx`: make the application shell and content column shrinkable.
- Modify `frontend/src/components/Sidebar.tsx`: add full and compact desktop states without resize listeners.
- Modify `frontend/src/pages/DashboardPage.tsx`: wrap the header and reflow fixed multi-column grids.
- Modify `frontend/src/pages/MeetingPage.tsx`: wrap the header and stack the five-column detail layout at narrower widths.
- Modify `frontend/src/pages/IssuesPage.tsx`: reflow summary grids, wrap filters, and preserve local table scrolling.
- Modify `frontend/src/pages/TaskManagementPage.tsx`: wrap controls and turn the fixed detail pane into an overlay below 1024px.

### Task 1: Global shell and compact sidebar

**Files:**
- Create: `frontend/tests/desktopResponsiveLayout.test.mjs`
- Modify: `frontend/src/layouts/ProjectLayout.tsx:131-143`
- Modify: `frontend/src/components/Sidebar.tsx:137-267`

- [ ] **Step 1: Write the failing shell test**

Create `frontend/tests/desktopResponsiveLayout.test.mjs`:

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const src = (...parts) => fs.readFileSync(path.join(here, '..', 'src', ...parts), 'utf8')

test('project shell allows the main content column to shrink in both axes', () => {
  const source = src('layouts', 'ProjectLayout.tsx')
  assert.match(source, /flex-1 min-w-0 min-h-0 flex flex-col overflow-hidden/)
})

test('sidebar switches from 64px compact mode to the full sidebar at xl', () => {
  const source = src('components', 'Sidebar.tsx')
  assert.match(source, /w-16 xl:w-44/)
  assert.match(source, /hidden xl:block/)
  assert.match(source, /title=\{entry\.label\}/)
  assert.doesNotMatch(source, /window\.addEventListener\(['"]resize/)
})
```

- [ ] **Step 2: Run the test and confirm the expected failure**

Run:

```powershell
node --test frontend/tests/desktopResponsiveLayout.test.mjs
```

Expected: both tests fail because `ProjectLayout` lacks `min-w-0 min-h-0` and `Sidebar` still uses only `w-44`.

- [ ] **Step 3: Implement the shrinkable shell**

Change the authenticated content column in `ProjectLayout.tsx` to:

```tsx
<div className="flex-1 min-w-0 min-h-0 flex flex-col overflow-hidden">
  <PageTransition />
</div>
```

- [ ] **Step 4: Implement the CSS-only compact sidebar**

In `Sidebar.tsx`:

```tsx
<aside className="w-16 xl:w-44 flex-shrink-0 flex flex-col overflow-hidden transition-[width] duration-200" ...>
```

Use `justify-center px-2 xl:justify-between xl:px-3` for the brand row, wrap `NotificationBell` in `hidden xl:block`, and remove the image's inline `maxWidth` in favor of:

```tsx
<img className="max-w-8 xl:max-w-[90px]" src={logoUrl} alt="logo" style={{ height: 32, objectFit: 'contain', flexShrink: 0 }} />
```

Give every navigation button `title={entry.label}`. Change its label and badge to compact-aware elements:

```tsx
<span className="hidden min-w-0 flex-1 xl:block">{entry.label}</span>
{entry.badge ? <span className="hidden xl:inline-block" style={badgeStyle}>{badgeText}</span> : null}
```

Change the footer to `flex-col px-2 xl:flex-row xl:px-3`, hide the user details with `hidden xl:block`, and retain the avatar, password, and logout buttons as icon-only controls with their existing titles.

- [ ] **Step 5: Verify the shell tests pass**

Run:

```powershell
node --test frontend/tests/desktopResponsiveLayout.test.mjs
```

Expected: 2 tests pass.

- [ ] **Step 6: Commit only the shell files**

```powershell
git add frontend/tests/desktopResponsiveLayout.test.mjs frontend/src/layouts/ProjectLayout.tsx frontend/src/components/Sidebar.tsx
git commit --only -m "fix: make application shell responsive" -- frontend/tests/desktopResponsiveLayout.test.mjs frontend/src/layouts/ProjectLayout.tsx frontend/src/components/Sidebar.tsx
```

### Task 2: Dashboard and meeting reflow

**Files:**
- Modify: `frontend/tests/desktopResponsiveLayout.test.mjs`
- Modify: `frontend/src/pages/DashboardPage.tsx:362-888`
- Modify: `frontend/src/pages/MeetingPage.tsx:150-350`

- [ ] **Step 1: Add failing page-grid tests**

Append:

```js
test('dashboard reflows fixed grids at lg and xl breakpoints', () => {
  const source = src('pages', 'DashboardPage.tsx')
  assert.match(source, /grid-cols-2 lg:grid-cols-3 xl:grid-cols-6/)
  assert.match(source, /grid-cols-2 lg:grid-cols-3 xl:grid-cols-5/)
  assert.match(source, /grid-cols-1 lg:grid-cols-2 xl:grid-cols-3/)
  assert.match(source, /min-h-16 flex-wrap/)
})

test('meeting page wraps its header and stacks the detail workspace below xl', () => {
  const source = src('pages', 'MeetingPage.tsx')
  assert.match(source, /min-h-16 flex-wrap/)
  assert.match(source, /grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-5/)
  assert.match(source, /col-span-2 lg:col-span-3 xl:col-span-2/)
  assert.match(source, /col-span-2 lg:col-span-3 xl:col-span-3/)
})
```

- [ ] **Step 2: Run and verify RED**

```powershell
node --test frontend/tests/desktopResponsiveLayout.test.mjs
```

Expected: the two new tests fail on the current fixed grid classes.

- [ ] **Step 3: Reflow the dashboard**

Change the top bar to `min-h-16 flex flex-wrap items-center gap-3 px-4 py-3 lg:px-6`. Add `min-w-0` to the title area, and allow both control groups to wrap.

Replace the decision grid expression with:

```tsx
className={`grid gap-4 ${canViewDecisions
  ? 'grid-cols-2 lg:grid-cols-3 xl:grid-cols-6'
  : 'grid-cols-2 lg:grid-cols-3 xl:grid-cols-5'}`}
```

Replace the fixed three-column area with `grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3`, and the fixed five-column area with `grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-5`.

- [ ] **Step 4: Reflow the meeting page**

Use the same wrapping top-bar pattern. Change the selected-meeting workspace to:

```tsx
<div className="mb-5 grid grid-cols-2 gap-5 lg:grid-cols-3 xl:grid-cols-5">
  <div className="col-span-2 overflow-y-auto ... lg:col-span-3 xl:col-span-2">
  ...
  <div className="col-span-2 flex flex-col gap-4 lg:col-span-3 xl:col-span-3">
```

Use `p-4 lg:p-6` on the main content so 800px windows retain usable width.

- [ ] **Step 5: Verify GREEN**

```powershell
node --test frontend/tests/desktopResponsiveLayout.test.mjs
npm --prefix frontend run build
```

Expected: all responsive tests pass and the TypeScript/Vite build succeeds.

- [ ] **Step 6: Commit only dashboard and meeting changes**

```powershell
git add frontend/tests/desktopResponsiveLayout.test.mjs frontend/src/pages/DashboardPage.tsx frontend/src/pages/MeetingPage.tsx
git commit --only -m "fix: reflow dashboard and meeting layouts" -- frontend/tests/desktopResponsiveLayout.test.mjs frontend/src/pages/DashboardPage.tsx frontend/src/pages/MeetingPage.tsx
```

### Task 3: Issues workspace and table containment

**Files:**
- Modify: `frontend/tests/desktopResponsiveLayout.test.mjs`
- Modify: `frontend/src/pages/IssuesPage.tsx:342-900`

- [ ] **Step 1: Add the failing issues test**

```js
test('issues page reflows summary cards and keeps wide tables locally scrollable', () => {
  const source = src('pages', 'IssuesPage.tsx')
  assert.match(source, /grid-cols-2 lg:grid-cols-3 xl:grid-cols-6/)
  assert.match(source, /flex flex-wrap items-center/)
  assert.match(source, /overflow-x-auto[^>]*>[\s\S]*?<table[^>]*min-w-\[920px\]/)
})
```

- [ ] **Step 2: Run and verify RED**

```powershell
node --test frontend/tests/desktopResponsiveLayout.test.mjs
```

Expected: the new issues test fails because the summary remains six columns and at least one 920px table is inside an `overflow-hidden` wrapper.

- [ ] **Step 3: Reflow issues controls and summary cards**

Change issue headers to the wrapping top-bar pattern. Change the six-column summary to `grid grid-cols-2 overflow-hidden ... lg:grid-cols-3 xl:grid-cols-6`. Add `flex-wrap` to filter rows and replace fixed horizontal padding with `px-4 lg:px-5` or `px-4 lg:px-6`.

- [ ] **Step 4: Fix local table scrolling**

For each business table that has or needs a minimum width, make the card wrapper `overflow-x-auto` and keep the table at a readable minimum width:

```tsx
<div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
  <table className="w-full min-w-[920px] text-left text-sm">
```

Do not add horizontal scrolling to the page root.

- [ ] **Step 5: Verify GREEN and build**

```powershell
node --test frontend/tests/desktopResponsiveLayout.test.mjs
npm --prefix frontend run build
```

Expected: tests and build pass.

- [ ] **Step 6: Commit only issues changes**

```powershell
git add frontend/tests/desktopResponsiveLayout.test.mjs frontend/src/pages/IssuesPage.tsx
git commit --only -m "fix: make issues workspace responsive" -- frontend/tests/desktopResponsiveLayout.test.mjs frontend/src/pages/IssuesPage.tsx
```

### Task 4: Task-management controls and narrow-window detail overlay

**Files:**
- Modify: `frontend/tests/desktopResponsiveLayout.test.mjs`
- Modify: `frontend/src/pages/TaskManagementPage.tsx:875-1360`

- [ ] **Step 1: Add the failing task-panel test**

```js
test('task detail pane overlays the workspace below 1024px and remains inline above it', () => {
  const source = src('pages', 'TaskManagementPage.tsx')
  assert.match(source, /fixed inset-y-0 right-0 z-40/)
  assert.match(source, /lg:static lg:z-auto lg:w-\[340px\] xl:w-\[380px\]/)
  assert.match(source, /w-\[min\(380px,calc\(100vw-64px\)\)\]/)
})
```

- [ ] **Step 2: Run and verify RED**

```powershell
node --test frontend/tests/desktopResponsiveLayout.test.mjs
```

Expected: the new test fails on the current fixed `w-[380px]` pane.

- [ ] **Step 3: Make the task toolbar responsive**

Change the top header to use `min-h-14 flex-wrap px-4 py-2 lg:px-6` while retaining `overflow-x-auto` only where the view selector genuinely needs it. Ensure the main split container keeps `min-w-0 min-h-0`.

- [ ] **Step 4: Convert the detail pane below 1024px**

Replace the fixed pane class with:

```tsx
className="fixed inset-y-0 right-0 z-40 flex w-[min(380px,calc(100vw-64px))] flex-shrink-0 flex-col overflow-hidden border-l bg-white shadow-2xl lg:static lg:z-auto lg:w-[340px] lg:shadow-none xl:w-[380px]"
```

Preserve the current close action and selected-detail state. Do not introduce resize listeners or a second detail component.

- [ ] **Step 5: Verify GREEN and build**

```powershell
node --test frontend/tests/desktopResponsiveLayout.test.mjs
npm --prefix frontend run build
```

Expected: tests and build pass.

- [ ] **Step 6: Commit only task-management changes**

```powershell
git add frontend/tests/desktopResponsiveLayout.test.mjs frontend/src/pages/TaskManagementPage.tsx
git commit --only -m "fix: adapt task detail pane to narrow windows" -- frontend/tests/desktopResponsiveLayout.test.mjs frontend/src/pages/TaskManagementPage.tsx
```

### Task 5: Regression and real viewport verification

**Files:**
- Verify: `frontend/src/**/*`
- Verify: `frontend/tests/**/*`

- [ ] **Step 1: Run the responsive regression test**

```powershell
node --test frontend/tests/desktopResponsiveLayout.test.mjs
```

Expected: all tests pass.

- [ ] **Step 2: Run the complete frontend test suite**

```powershell
node --test frontend/tests/*.test.mjs
```

Expected: all existing and new frontend tests pass with zero failures.

- [ ] **Step 3: Run the production build**

```powershell
npm --prefix frontend run build
```

Expected: `tsc -b && vite build` exits successfully.

- [ ] **Step 4: Start local services for browser verification**

Start the existing frontend and backend development commands in hidden windows. Do not change environment files or seed data.

- [ ] **Step 5: Verify the four viewport widths**

Using the in-app browser viewport capability, inspect 1440×900, 1100×800, 900×768, and 800×720. For every accessible core page, record:

```js
({
  viewport: innerWidth,
  rootClientWidth: document.documentElement.clientWidth,
  rootScrollWidth: document.documentElement.scrollWidth,
  sidebarWidth: document.querySelector('aside')?.getBoundingClientRect().width
})
```

Expected: root `scrollWidth <= clientWidth`; sidebar is 176px at 1440 and 64px at 1100, 900, and 800. Dashboard, meeting, issues, and task controls remain visible. Business tables may scroll only inside their local wrappers.

- [ ] **Step 6: Inspect browser logs**

Expected: no new console errors related to rendering, React keys, or layout code.

- [ ] **Step 7: Review the final diff**

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors; unrelated pre-existing user changes remain untouched.

