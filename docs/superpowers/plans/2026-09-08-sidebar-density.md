# Sidebar Density Implementation Plan

> Status: Implemented on the delivery baseline; the original task checkboxes are retained as the execution record.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the expanded desktop sidebar visibly more compact while preserving its navigation content, visuals, and collapsed/mobile behavior.

**Architecture:** Keep all density choices local to the existing `Sidebar` markup. The navigation container, group separators, and button vertical padding will be reduced together; no new state, components, or CSS configuration is introduced. A source-level Vitest regression test protects these exact layout decisions.

**Tech Stack:** React, TypeScript, Tailwind utility classes, Vitest.

---

## File structure

- `frontend/src/components/Sidebar.tsx` — existing responsive sidebar; adjust only the expanded navigation's vertical density values.
- `frontend/src/components/Sidebar.test.ts` — existing Vitest source-style guard; add assertions for the selected compact dimensions.

### Task 1: Lock the approved compact density in a regression test

**Files:**
- Modify: `frontend/src/components/Sidebar.test.ts:5-12`
- Test: `frontend/src/components/Sidebar.test.ts`

- [ ] **Step 1: Add a failing source-style test**

  Add this test after the existing test:

  ```ts
  it('uses the approved compact vertical density for expanded navigation', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/components/Sidebar.tsx'), 'utf8')

    expect(source).toContain('className="flex-1 px-2 py-2 space-y-0.5 overflow-y-auto"')
    expect(source).toContain('className="pt-2"')
    expect(source).toContain("padding: '6px 10px'")
  })
  ```

- [ ] **Step 2: Run the focused test to verify it fails for the missing compact values**

  Run:

  ```powershell
  Set-Location frontend
  npm run test:unit -- src/components/Sidebar.test.ts
  ```

  Expected: the new test fails because `Sidebar.tsx` still contains `py-3`, `pt-3`, and `padding: '8px 10px'`.

- [ ] **Step 3: Apply the minimal density-only implementation**

  In `frontend/src/components/Sidebar.tsx`, make these three exact replacements:

  ```tsx
  <nav className="flex-1 px-2 py-2 space-y-0.5 overflow-y-auto">
  ```

  ```tsx
  return <div key={idx} className="pt-2" />
  ```

  ```ts
  padding: '6px 10px',
  ```

  Do not change width breakpoints, `xl` visibility classes, icon dimensions, text font size, colors, active state, bottom user area, item lists, or permissions.

- [ ] **Step 4: Run the focused test to verify it passes**

  Run:

  ```powershell
  Set-Location frontend
  npm run test:unit -- src/components/Sidebar.test.ts
  ```

  Expected: both `Sidebar navigation styles` tests pass.

- [ ] **Step 5: Commit the implementation and test**

  ```powershell
  git add frontend/src/components/Sidebar.tsx frontend/src/components/Sidebar.test.ts
  git commit -m "style: compact sidebar navigation spacing"
  ```

### Task 2: Verify no visual or build regression

**Files:**
- Verify: `frontend/src/components/Sidebar.tsx`
- Verify: `frontend/src/components/Sidebar.test.ts`

- [ ] **Step 1: Run the complete frontend test suite**

  Run:

  ```powershell
  Set-Location frontend
  npm run test:unit
  ```

  Expected: exit code 0 with no failing tests.

- [ ] **Step 2: Build the frontend**

  Run:

  ```powershell
  Set-Location frontend
  npm run build
  ```

  Expected: exit code 0 and a production bundle is generated without TypeScript errors.

- [ ] **Step 3: Check the final scoped diff**

  Run:

  ```powershell
  git diff HEAD -- frontend/src/components/Sidebar.tsx frontend/src/components/Sidebar.test.ts
  ```

  Expected: the diff contains only the three approved density changes and their regression test.
