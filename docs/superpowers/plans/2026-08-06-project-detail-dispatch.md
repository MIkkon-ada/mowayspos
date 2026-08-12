# Project Detail Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the project detail page's dispatch button call the existing dispatch API and visibly report the result.

**Architecture:** Keep the existing `DetailPanel` presentation component and implement the missing action in `ProjectDetailPage`. Reuse `dispatchProject`, `getProject`, and the shared toast utility; guard concurrent clicks with local state.

**Tech Stack:** React 19, TypeScript, Node.js contract tests, Vite

---

### Task 1: Add the dispatch regression contract

**Files:**
- Create: `frontend/tests/projectDetailDispatch.test.mjs`
- Test: `frontend/tests/projectDetailDispatch.test.mjs`

- [ ] **Step 1: Write the failing test**

```js
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/pages/ProjectDetailPage.tsx', import.meta.url), 'utf8')

assert.match(source, /import \{[^}]*dispatchProject[^}]*\} from '\.\.\/api\/projects'/)
assert.match(source, /await dispatchProject\(project\.id\)/)
assert.match(source, /setProject\(await getProject\(project\.id\)\)/)
assert.match(source, /toast\.success/)
assert.match(source, /toast\.error/)
assert.doesNotMatch(source, /onDispatch=\{async \(\) => \{\s*\/\/[^\n]*dispatch logic\s*\}\}/)

console.log('project detail dispatch contract passed')
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node frontend/tests/projectDetailDispatch.test.mjs`

Expected: FAIL because `ProjectDetailPage.tsx` does not import or call `dispatchProject`.

### Task 2: Implement the project detail dispatch action

**Files:**
- Modify: `frontend/src/pages/ProjectDetailPage.tsx:1-170`
- Test: `frontend/tests/projectDetailDispatch.test.mjs`

- [ ] **Step 1: Import the existing API and toast utility**

```ts
import { dispatchProject, getProject, getProjectMembers } from '../api/projects'
import { toast } from '../utils/toast'
```

- [ ] **Step 2: Add the in-flight guard and action**

```ts
const [dispatching, setDispatching] = useState(false)

async function handleDispatch() {
  if (!project || dispatching) return
  setDispatching(true)
  try {
    const result = await dispatchProject(project.id)
    setProject(await getProject(project.id))
    toast.success(`已下发给 ${result.dispatched_to} 位负责人`)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : '下发失败')
  } finally {
    setDispatching(false)
  }
}
```

- [ ] **Step 3: Wire the detail button to the action**

```tsx
onDispatch={() => void handleDispatch()}
```

- [ ] **Step 4: Run focused verification**

Run: `node frontend/tests/projectDetailDispatch.test.mjs`

Expected: `project detail dispatch contract passed`

- [ ] **Step 5: Run frontend regression and build verification**

Run: `node frontend/tests/projectDetailLoading.test.mjs`

Expected: `project detail loading contract passed`

Run: `npm run build`

Working directory: `frontend`

Expected: TypeScript and Vite build complete with exit code 0.
