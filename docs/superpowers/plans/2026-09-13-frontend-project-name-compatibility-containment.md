# Frontend Project Name Compatibility Containment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` in the current session task-by-task. Do not delegate to subagents for this repository.

**Goal:** Move frontend historical project-name fallback and task grouping into an explicit compatibility module without changing displayed names, Excel grouping, or API DTO contracts.

**Architecture:** Split strict project identity operations from historical-name display resolution. `projectIdentity.ts` accepts only ID aliases; `compatibility/projectNames.ts` owns all historical field lookup and group-key construction. Page and export callers use semantic functions, never raw historical fields for grouping.

**Tech Stack:** TypeScript, React, Vite, Vitest, ExcelJS.

---

## File structure

- Create: `frontend/src/domain/projectIdentity.ts`
- Create: `frontend/src/compatibility/projectNames.ts`
- Create: `frontend/src/compatibility/projectNames.test.ts`
- Modify: `frontend/src/domain/projectDisplay.ts`
- Modify: `frontend/src/pages/TaskManagementPage.tsx`
- Modify: `frontend/src/utils/exportTasksExcel.ts`
- Modify: current imports of `../domain/projectDisplay` and `../../domain/projectDisplay` found by `rg -l "projectDisplay" frontend/src`
- Create: `frontend/tests/project-name-compatibility-boundary.test.mjs`

### Task 1: Freeze compatibility behavior with failing tests

- [ ] **Step 1: Add focused Vitest coverage.**

Create `frontend/src/compatibility/projectNames.test.ts` with the following cases. Use `Project` objects containing only `id` and `name` via a local `as any` cast so the test has no unrelated DTO setup.

```ts
import { describe, expect, it } from 'vitest'
import { getProjectDisplayName, getProjectGroupKey } from './projectNames'

const projects = [{ id: 7, name: '当前项目' }] as any

describe('project name compatibility', () => {
  it('prefers a resolved project_id over a stale historical name', () => {
    expect(getProjectDisplayName(projects, { project_id: 7, special_project: '旧名称' })).toBe('当前项目')
    expect(getProjectGroupKey(projects, { project_id: 7, special_project: '旧名称' })).toBe('project:7')
  })

  it('uses a historical name only when no current project id resolves', () => {
    expect(getProjectDisplayName(projects, { related_special_project: '历史会议项目' })).toBe('历史会议项目')
    expect(getProjectGroupKey(projects, { special_project: '历史任务项目' })).toContain('历史任务项目')
  })

  it('uses the supplied fallback for records with no project data', () => {
    expect(getProjectDisplayName(projects, {}, '（未分类）')).toBe('（未分类）')
  })
})
```

- [ ] **Step 2: Add the source-boundary contract.**

Create `frontend/tests/project-name-compatibility-boundary.test.mjs`. Read the three source files with `fs.readFileSync`. Assert `frontend/src/compatibility/projectNames.ts` contains `special_project`; assert `frontend/src/domain/projectIdentity.ts`, `frontend/src/pages/TaskManagementPage.tsx`, and `frontend/src/utils/exportTasksExcel.ts` do not contain `legacy:`; assert the page/export source do not contain `task.special_project`.

- [ ] **Step 3: Run the new tests and confirm red.**

```powershell
Set-Location frontend
npx vitest run src/compatibility/projectNames.test.ts
node --test tests/project-name-compatibility-boundary.test.mjs
```

Expected: FAIL because neither new compatibility module nor strict identity module exists and the task callers still contain duplicated legacy grouping.

- [ ] **Step 4: Commit the failing contract.**

```powershell
git add frontend/src/compatibility/projectNames.test.ts frontend/tests/project-name-compatibility-boundary.test.mjs
git diff --cached --check
git commit -m "test: define frontend project name containment"
```

### Task 2: Split strict identity from historical-name compatibility

- [ ] **Step 1: Create `projectIdentity.ts`.**

Move `getProjectById`, `getProjectIdFromRecord`, and `isSameProjectById` from `projectDisplay.ts` without changing signatures. Keep `ProjectRecord`, `ProjectSummary`, numeric coercion and nested-parent lookup private to this module. Do not include `special_project`, `related_special_project`, or any display-name fallback.

- [ ] **Step 2: Create `compatibility/projectNames.ts`.**

Import `getProjectById` and `getProjectIdFromRecord` from `../domain/projectIdentity`. Move the trimmed-string helper and the ordered historical field list from `projectDisplay.ts` here. Define the stable group-key prefix privately:

```ts
const currentProjectKey = (projectId: number) => `project:${projectId}`
const historicalProjectKey = (name: string) => `compat-name:${name}`
```

`getProjectGroupKey` must first resolve an ID from the record and return `project:<id>` even if the projects list does not currently contain that ID; otherwise it returns `compat-name:<getProjectDisplayName(...)>`. This preserves grouping of current records across a stale project list without treating an old name as identity.

- [ ] **Step 3: Turn `projectDisplay.ts` into a compatibility re-export.**

Export the three identity functions from `./projectIdentity` and `getProjectDisplayName` from `../compatibility/projectNames`. Do not leave any field list or `special_project` string in this transitional facade. This retains existing consumer imports while subsequent call-site migrations happen independently.

- [ ] **Step 4: Run focused tests and confirm green.**

```powershell
Set-Location frontend
npx vitest run src/compatibility/projectNames.test.ts
node --test tests/project-name-compatibility-boundary.test.mjs
```

Expected: all new tests PASS.

- [ ] **Step 5: Commit the strict/compatibility split.**

```powershell
git add frontend/src/domain/projectIdentity.ts frontend/src/domain/projectDisplay.ts frontend/src/compatibility/projectNames.ts frontend/src/compatibility/projectNames.test.ts frontend/tests/project-name-compatibility-boundary.test.mjs
git diff --cached --check
git commit -m "refactor: isolate frontend project name compatibility"
```

### Task 3: Replace duplicate task grouping rules

- [ ] **Step 1: Change `TaskManagementPage.tsx`.**

Import `getProjectDisplayName`, `getProjectGroupKey`, and `getProjectNameFromGroupKey` from `../compatibility/projectNames`; import `getProjectById` and `getProjectIdFromRecord` from `../domain/projectIdentity`. Replace `taskProjectKey` with `return getProjectGroupKey(projects, task, '（未分类）')`. Replace `groupProjectName` parsing with `return getProjectNameFromGroupKey(projects, key, tasks, '（未分类）')`. Preserve function names and all rendered labels so React behavior does not change.

- [ ] **Step 2: Change `exportTasksExcel.ts`.**

Import `getProjectDisplayName` and `getProjectGroupKey` from `../compatibility/projectNames`. Replace `resolveTaskProjectLabel` with a wrapper that calls `getProjectDisplayName(projects, task, '（未分类）')`; replace `resolveTaskProjectKey` with `getProjectGroupKey(projects, task, '（未分类）')`. Leave the worksheet layout, merge behavior, title and file naming untouched.

- [ ] **Step 3: Expand the boundary test for both task consumers.**

Add assertions that the page and Excel source reference `getProjectGroupKey` and do not contain `special_project` or `legacy:`. Keep a separate assertion that the compatibility module owns `compat-name:`.

- [ ] **Step 4: Run focused regression checks.**

```powershell
Set-Location frontend
npx vitest run src/compatibility/projectNames.test.ts
node --test tests/project-name-compatibility-boundary.test.mjs
npm run test:all
```

Expected: compatibility and complete frontend suites PASS.

- [ ] **Step 5: Commit caller migration.**

```powershell
git add frontend/src/pages/TaskManagementPage.tsx frontend/src/utils/exportTasksExcel.ts frontend/tests/project-name-compatibility-boundary.test.mjs
git diff --cached --check
git commit -m "refactor: centralize task project grouping"
```

### Task 4: Migrate remaining display consumers and verify the delivery gate

- [ ] **Step 1: Migrate direct display imports.**

For every consumer returned by this command, replace only the `getProjectDisplayName` import with `frontend/src/compatibility/projectNames.ts`; keep identity imports on `projectIdentity.ts` where needed.

```powershell
rg -l "from ['\"](?:\.\./)+domain/projectDisplay['\"]" frontend/src -g "*.ts" -g "*.tsx"
```

At the current audit this includes confirmation flow/task cards, confirmation page, meeting page, issues page and voice-update detail drawer. Do not alter their rendering conditions or request payloads.

- [ ] **Step 2: Remove the transitional facade only when the search is empty.**

Run the same search. If no production consumer remains, delete `frontend/src/domain/projectDisplay.ts`; otherwise keep it as the documented no-field re-export and list the remaining consumer in the verification record. Never use a broad search-and-replace that changes API DTO fields.

- [ ] **Step 3: Run release-equivalent frontend verification.**

```powershell
Set-Location frontend
npm run test:all
npm run test:bundle
Set-Location ..
git diff --check
git status --short
```

Expected: Vitest, contract tests, production build and manifest bundle baseline PASS; status contains only the intended files before commit.

- [ ] **Step 4: Record exact results and commit.**

Append actual command totals and bundle values to this plan, then run:

```powershell
git add frontend/src/domain frontend/src/compatibility frontend/src/pages frontend/src/features frontend/tests docs/superpowers/plans/2026-09-13-frontend-project-name-compatibility-containment.md
git diff --cached --check
git commit -m "docs: verify frontend project name containment"
```

## Plan self-review

- The plan preserves public DTO fields and historical record display while making identity ID-first.
- Every proposed runtime behavior has a focused test and the final frontend gate verifies consumers/build output.
- PostgreSQL, remote CI and backend physical-field retirement are deliberately excluded because they require different evidence and migration design.
