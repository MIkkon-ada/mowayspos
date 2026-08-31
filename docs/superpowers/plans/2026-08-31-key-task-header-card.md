# Key Task Header Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the key-task execution header as a white rounded information card while preserving all existing data, permissions, and actions.

**Architecture:** Keep the change local to `KeyTaskHeader.tsx`; it remains the sole owner of the header’s markup and continues to receive the same workspace DTO and callback props. Extend the existing source-structure test so the new card treatment is covered without changing task behavior.

**Tech Stack:** React 19, TypeScript, Tailwind CSS, Node.js built-in test runner, Vite.

---

### Task 1: Cover the card treatment with a failing test

**Files:**
- Modify: `frontend/tests/keyTaskExecutionWorkspace.test.mjs:24-34`
- Modify: `frontend/src/components/key-task-workspace/KeyTaskHeader.tsx:24-57`

- [x] **Step 1: Write the failing test**

Add the following test immediately after the existing metadata-rail test in `frontend/tests/keyTaskExecutionWorkspace.test.mjs`:

```js
test('key task header uses a white rounded reference card without changing its content rail', () => {
  const header = read('src/components/key-task-workspace/KeyTaskHeader.tsx')

  assert.match(header, /rounded-xl/)
  assert.match(header, /border-slate-200/)
  assert.match(header, /bg-white/)
  assert.doesNotMatch(header, /border-blue-200 bg-blue-50/)
})
```

- [x] **Step 2: Run the focused test to verify it fails**

Run: `node --test tests/keyTaskExecutionWorkspace.test.mjs`

Expected: the new test fails because the header currently uses `border-blue-200 bg-blue-50` and has no `rounded-xl` class.

- [x] **Step 3: Write the minimal implementation**

In `frontend/src/components/key-task-workspace/KeyTaskHeader.tsx`, replace the opening header class string with the following:

```tsx
return <header className="rounded-xl border border-slate-200 bg-white px-5 py-6 shadow-sm sm:px-7">
```

Do not alter the breadcrumb, title, risk state, metadata grid, button permission checks, callback wiring, or any text.

- [x] **Step 4: Run the focused test to verify it passes**

Run: `node --test tests/keyTaskExecutionWorkspace.test.mjs`

Expected: all tests in the file pass.

- [x] **Step 5: Run the production build**

Run: `npm run build`

Working directory: `frontend`

Expected: TypeScript and Vite complete successfully with exit code 0.

- [x] **Step 6: Commit the implementation**

```bash
git add frontend/src/components/key-task-workspace/KeyTaskHeader.tsx frontend/tests/keyTaskExecutionWorkspace.test.mjs
git commit -m "feat: restyle key task header card"
```
