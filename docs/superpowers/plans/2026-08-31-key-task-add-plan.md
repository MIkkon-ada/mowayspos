# Key Task Add Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the empty-state “添加计划” control create a new task plan directly beneath the current key task.

**Architecture:** Keep the existing monthly-plan persistence model as the single source of truth. The workspace loads project members while the creation drawer is open, passes the current key task as `subtask_id`, and refreshes its existing execution-workspace query after creation. A focused drawer owns form validation and calls `createMonthlyPlan`; the table only owns the permission-gated trigger.

**Tech Stack:** React 19, TypeScript, Tailwind CSS, Vitest/Testing Library, existing FastAPI monthly-plan endpoint.

---

### Task 1: Make the empty-state add control permission-aware

**Files:**

- Modify: `frontend/src/components/key-task-workspace/ExecutionPlanTable.tsx`
- Modify: `frontend/tests/keyTaskExecutionWorkspace.test.mjs`

- [ ] **Step 1: Write the failing structure test**

Append:

```js
test('empty execution plan state exposes an add-plan button only to plan managers', () => {
  const plan = read('src/components/key-task-workspace/ExecutionPlanTable.tsx')

  assert.match(plan, /onAdd/)
  assert.match(plan, /canManage/)
  assert.match(plan, /<button[^>]*onClick={onAdd}[^>]*>添加计划</button>/)
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test frontend/tests/keyTaskExecutionWorkspace.test.mjs`

Expected: FAIL because the table has no `onAdd` or `canManage` property and still uses a non-interactive span.

- [ ] **Step 3: Write the minimal table implementation**

Change the table props to:

```tsx
export function ExecutionPlanTable({
  plans,
  summary,
  canManage,
  onAdd,
  onOpen,
}: {
  plans: ExecutionPlan[]
  summary: KeyTaskWorkspace['plan_summary']
  canManage: boolean
  onAdd: () => void
  onOpen: (plan: ExecutionPlan) => void
}) {
  // Existing table rendering is unchanged.
}
```

Replace the empty-state span with:

```tsx
{canManage && <button type="button" onClick={onAdd} className="mt-4 border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-600 hover:border-blue-500 hover:text-blue-600">添加计划</button>}
```

- [ ] **Step 4: Re-run the structure test**

Run: `node --test frontend/tests/keyTaskExecutionWorkspace.test.mjs`

Expected: PASS. Replace the former assertion rejecting all add-plan buttons with this permission-aware assertion.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/components/key-task-workspace/ExecutionPlanTable.tsx frontend/tests/keyTaskExecutionWorkspace.test.mjs
git commit -m "feat: expose key task plan creation trigger"
```

### Task 2: Add a focused task-plan creation drawer

**Files:**

- Create: `frontend/src/components/key-task-workspace/ExecutionPlanCreateDrawer.tsx`
- Create: `frontend/src/components/key-task-workspace/ExecutionPlanCreateDrawer.test.tsx`
- Modify: `frontend/src/api/keyTaskWorkspace.ts`

- [ ] **Step 1: Write failing drawer tests**

Create `ExecutionPlanCreateDrawer.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { vi, describe, expect, it } from 'vitest'

const createMonthlyPlan = vi.fn()
vi.mock('../../api/monthlyPlans', () => ({ createMonthlyPlan }))

import { ExecutionPlanCreateDrawer } from './ExecutionPlanCreateDrawer'

const members = [
  { id: 1, project_id: 7, person_id: 11, person_name_snapshot: '吴肖', role: 'owner', note: '', joined_at: null },
  { id: 2, project_id: 7, person_id: 12, person_name_snapshot: '郭曙彬', role: 'member', note: '', joined_at: null },
]

describe('ExecutionPlanCreateDrawer', () => {
  it('defaults the assignee to the key task owner', () => {
    render(<ExecutionPlanCreateDrawer keyTaskId={42} defaultAssigneeId={11} members={members} onClose={vi.fn()} onCreated={vi.fn()} />)
    expect((screen.getByLabelText('负责人') as HTMLSelectElement).value).toBe('11')
  })

  it('creates a plan for the current key task and closes on success', async () => {
    createMonthlyPlan.mockResolvedValue({ id: 99 })
    const onClose = vi.fn()
    const onCreated = vi.fn()
    render(<ExecutionPlanCreateDrawer keyTaskId={42} defaultAssigneeId={11} members={members} onClose={onClose} onCreated={onCreated} />)
    fireEvent.change(screen.getByLabelText('计划事项'), { target: { value: '完成模块梳理' } })
    fireEvent.change(screen.getByLabelText('预期成果'), { target: { value: '模块清单' } })
    fireEvent.click(screen.getByRole('button', { name: '创建计划' }))
    await waitFor(() => expect(createMonthlyPlan).toHaveBeenCalledWith(42, expect.objectContaining({
      title: '完成模块梳理',
      expected_output: '模块清单',
      assignee_id: 11,
      status: '未开始',
    })))
    expect(onCreated).toHaveBeenCalledOnce()
    expect(onClose).toHaveBeenCalledOnce()
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test:unit -- --run src/components/key-task-workspace/ExecutionPlanCreateDrawer.test.tsx`

Expected: FAIL with unresolved import `./ExecutionPlanCreateDrawer`.

- [ ] **Step 3: Implement the minimal creation drawer**

Create the component with this public contract and initial payload:

```tsx
type Props = {
  keyTaskId: number
  defaultAssigneeId: number | null
  members: ProjectMember[]
  onClose: () => void
  onCreated: () => void
}

const blankPlan = (assigneeId: number | null): MonthlyPlanPayload => ({
  plan_month: null,
  title: '',
  expected_output: '',
  assignee_id: assigneeId ?? 0,
  collaborator_ids: [],
  status: '未开始',
  start_date: null,
  due_kind: null,
  due_date: null,
  due_label: null,
  due_reference_date: null,
  completion_criteria: '',
  progress_note: '',
  risk_dependency: '',
  actual_output: '',
  delay_reason: '',
  sort_order: 0,
  is_archived: false,
})
```

Use `createMonthlyPlan(keyTaskId, payload)`. Title, expected result, and assignee are required. Exclude the assignee from collaborator choices. Render a right-side modal titled “新增任务计划”, labels `计划事项`, `负责人`, `协助人`, `开始日期`, `截止日期`, `预期成果`, and `完成定义`, submit button “创建计划”, and cancel button “取消”. On success call `onCreated()`, then `onClose()`; on a rejected request keep the drawer open and show an error using `role="alert"`.

Add the server DTO property in `keyTaskWorkspace.ts`:

```ts
can_manage_execution_plans: boolean
```

- [ ] **Step 4: Run drawer tests**

Run: `npm run test:unit -- --run src/components/key-task-workspace/ExecutionPlanCreateDrawer.test.tsx`

Expected: PASS for both default owner and API submission.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/components/key-task-workspace/ExecutionPlanCreateDrawer.tsx frontend/src/components/key-task-workspace/ExecutionPlanCreateDrawer.test.tsx frontend/src/api/keyTaskWorkspace.ts
git commit -m "feat: add key task plan creation drawer"
```

### Task 3: Connect drawer, permissions, and refresh to the workspace

**Files:**

- Modify: `frontend/src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx`
- Modify: `frontend/tests/keyTaskExecutionWorkspace.test.mjs`

- [ ] **Step 1: Write failing workspace wiring test**

Append:

```js
test('workspace wires task-plan creation to the current key task permissions and refresh', () => {
  const workspace = read('src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx')
  assert.match(workspace, /ExecutionPlanCreateDrawer/)
  assert.match(workspace, /getProjectMembers/)
  assert.match(workspace, /can_manage_execution_plans/)
  assert.match(workspace, /onAdd={() => setCreatingPlan(true)}/)
  assert.match(workspace, /onCreated={refresh}/)
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test frontend/tests/keyTaskExecutionWorkspace.test.mjs`

Expected: FAIL because the workspace has no creation state, member load, or drawer.

- [ ] **Step 3: Implement wiring**

Add imports and state:

```tsx
import { getProjectMembers } from '../../api/projects'
import type { ProjectMember } from '../../types'
import { ExecutionPlanCreateDrawer } from './ExecutionPlanCreateDrawer'

const [creatingPlan, setCreatingPlan] = useState(false)
const [projectMembers, setProjectMembers] = useState<ProjectMember[]>([])
```

Load members only while the drawer is open:

```tsx
useEffect(() => {
  if (!creatingPlan || !workspace?.project?.id) return
  let cancelled = false
  getProjectMembers(workspace.project.id)
    .then((members) => { if (!cancelled) setProjectMembers(members) })
    .catch(() => { if (!cancelled) setProjectMembers([]) })
  return () => { cancelled = true }
}, [creatingPlan, workspace?.project?.id])
```

Pass the table props and render the drawer next to the plan-detail drawer:

```tsx
<ExecutionPlanTable
  plans={workspace.execution_plans}
  summary={workspace.plan_summary}
  canManage={workspace.permissions.can_manage_execution_plans && workspace.key_task.status !== '已完成'}
  onAdd={() => setCreatingPlan(true)}
  onOpen={setSelectedPlan}
/>

{creatingPlan && <ExecutionPlanCreateDrawer
  keyTaskId={keyTaskId}
  defaultAssigneeId={workspace.key_task.owner.id ?? null}
  members={projectMembers}
  onClose={() => setCreatingPlan(false)}
  onCreated={refresh}
/>}
```

- [ ] **Step 4: Run the structure test**

Run: `node --test frontend/tests/keyTaskExecutionWorkspace.test.mjs`

Expected: PASS, including all existing workspace layout checks.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx frontend/tests/keyTaskExecutionWorkspace.test.mjs
git commit -m "feat: create plans from key task workspace"
```

### Task 4: Verify the frontend contract

**Files:**

- Verify: `frontend/src/components/key-task-workspace/ExecutionPlanCreateDrawer.test.tsx`
- Verify: `frontend/tests/keyTaskExecutionWorkspace.test.mjs`

- [ ] **Step 1: Run focused tests**

Run: `npm run test:unit -- --run src/components/key-task-workspace/ExecutionPlanCreateDrawer.test.tsx; node --test tests/keyTaskExecutionWorkspace.test.mjs`

Expected: all focused tests PASS.

- [ ] **Step 2: Run the complete unit suite**

Run: `npm run test:unit`

Expected: PASS with no failing test files.

- [ ] **Step 3: Build production frontend**

Run: `npm run build`

Expected: TypeScript compilation and the Vite production build complete successfully.

- [ ] **Step 4: Inspect the final change set**

Run: `git diff --check HEAD~3..HEAD; git status --short`

Expected: no whitespace errors; only the intended implementation commits and pre-existing user changes remain.
