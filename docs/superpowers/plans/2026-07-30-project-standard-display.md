# Project Standard Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hide the work-progress table's project-standard button when the selected project has no project-level standard.

**Architecture:** The change is local to `PlanTableViewV2`. It derives one boolean from `project.objectives` and uses that boolean to guard the existing button; `ProjectStandardModal` and all task-level standard rendering remain unchanged.

**Tech Stack:** React, TypeScript, Node built-in test runner, Vite.

---

### Task 1: Guard the project-standard entry point

**Files:**
- Modify: `frontend/src/components/task-management/PlanTableViewV2.tsx`
- Test: `frontend/tests/workProgressExcelView.test.mjs`

- [ ] **Step 1: Write the failing structural test**

Add an assertion that requires `PlanTableViewV2` to derive a project-standard availability boolean from `project?.objectives?.trim()` and use it to conditionally render the existing project-standard button.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `node --test frontend/tests/workProgressExcelView.test.mjs`

Expected: the new assertion fails because the button is currently unconditional.

- [ ] **Step 3: Implement the minimal guard**

Add `const hasProjectStandard = Boolean(project?.objectives?.trim())` beside the component's existing derived state. Wrap the unchanged project-standard button in `{hasProjectStandard && (...)}`. Do not change the create-key-work button or modal implementation.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `node --test frontend/tests/workProgressExcelView.test.mjs`

Expected: PASS.

- [ ] **Step 5: Run full frontend verification**

Run:

```powershell
Push-Location frontend
$testFiles = Get-ChildItem tests -Filter '*.test.mjs' | ForEach-Object { $_.FullName }
node --test $testFiles
npm run build
Pop-Location
```

Expected: all tests pass and the Vite build exits with code 0.
