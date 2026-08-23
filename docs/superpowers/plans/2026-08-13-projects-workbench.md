# Projects Lifecycle Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with review checkpoints.

**Goal:** 将项目管理首页从搜索栏加表格升级为包含概览、角色化待办、生命周期卡片和可切换列表视图的项目工作台，同时保持现有项目流程、权限、API 和后端状态不变。

**Architecture:** 将新增的统计、待办、生命周期阶段和材料缺项计算放入可测试的纯函数模块；新增两个只负责展示的首页子组件；`ProjectsMgmtSection` 继续持有数据加载、权限上下文和所有流程 handler，并复用现有 `LifecycleCard`、列表表格和弹窗。待办区使用未经搜索过滤的 `roleFilteredProjects`，全部项目区继续使用现有搜索和分页结果。

**Tech Stack:** React 19, TypeScript, React Router, Tailwind utility classes, Vitest, Vite。

---

## 文件地图

- Create: `frontend/src/features/settings/projectsWorkbench.ts` — 首页统计、待办、材料缺项和生命周期阶段的纯函数与类型。
- Create: `frontend/src/features/settings/projectsWorkbench.test.ts` — 纯函数的 Vitest 单元测试。
- Create: `frontend/src/features/settings/ProjectOverviewStats.tsx` — 五项统计卡片的纯展示组件。
- Create: `frontend/src/features/settings/ProjectTodoSection.tsx` — “待我处理”区域和待办卡片的纯展示组件。
- Create: `frontend/tests/projectsWorkbenchStructure.test.mjs` — 首页结构与关键文案的源代码结构测试。
- Modify: `frontend/src/features/settings/ProjectsMgmtSection.tsx` — 接入派生数据、头部/概览/待办/全部项目布局，增加卡片列表切换，扩展现有 `LifecycleCard`。
- Do not modify: backend files, database migrations, API modules, Sidebar, Dashboard, OwnerSubmit 或结束/归档流程组件。

### Task 1: 为工作台纯函数建立失败测试

**Files:**
- Create: `frontend/src/features/settings/projectsWorkbench.test.ts`
- Reference: `frontend/src/features/settings/projectsWorkbench.ts` (do not create the production module until the test has failed)

- [ ] **Step 1: Write the failing tests**

Create tests with a minimal `Project` factory and cover the required boundaries:

```ts
import { describe, expect, it } from 'vitest'
import type { Project } from '../../types'
import {
  getProjectLifecycleStage,
  getProjectMaterialChecklist,
  getProjectOverviewStats,
  getProjectTodo,
} from './projectsWorkbench'

const project = (status: Project['status'], overrides: Partial<Project> = {}): Project => ({
  id: 1,
  name: '项目 A',
  code: '',
  description: '',
  status,
  is_active: status === 'active',
  user_roles: [],
  member_counts: {},
  coordinator: '',
  owners: [],
  collaborators: [],
  coaches: [],
  ...overrides,
})

describe('projects workbench pure helpers', () => {
  it('groups overview counts without dropping statuses that have no card', () => {
    const result = getProjectOverviewStats([
      project('draft'),
      project('dispatched'),
      project('returned'),
      project('pending_review'),
      project('active'),
      project('pending_close'),
      project('ended'),
      project('archived'),
    ])
    expect(result).toEqual({ all: 8, toComplete: 2, toApprove: 1, active: 1, archived: 1 })
  })

  it('maps real statuses to business stages without creating startup status', () => {
    expect(getProjectLifecycleStage('dispatched')).toMatchObject({ key: 'planning', label: '立项准备阶段', activeIndex: 0 })
    expect(getProjectLifecycleStage('active')).toMatchObject({ key: 'execution', label: '执行阶段', activeIndex: 2 })
    expect(getProjectLifecycleStage('pending_close')).toMatchObject({ key: 'closing', activeIndex: 3 })
    expect(getProjectLifecycleStage('archived')).toMatchObject({ key: 'archive', activeIndex: 4 })
    expect(getProjectLifecycleStage('startup' as string)).toMatchObject({ key: 'planning', activeIndex: 0 })
  })

  it('returns the four frontend-only material checks', () => {
    const result = getProjectMaterialChecklist(project('dispatched'), [], [])
    expect(result).toEqual([
      { key: 'objectives', label: '项目目标', complete: false },
      { key: 'period', label: '项目周期', complete: false },
      { key: 'tasks', label: '重点工作', complete: false },
      { key: 'subtasks', label: '关键任务', complete: false },
    ])
    expect(getProjectMaterialChecklist(project('dispatched', {
      objectives: '目标', start_date: '2026-08-01', end_date: '2026-08-31',
    }), [{ id: 1 } as any], [{ id: 2 } as any])).toEqual([
      { key: 'objectives', label: '项目目标', complete: true },
      { key: 'period', label: '项目周期', complete: true },
      { key: 'tasks', label: '重点工作', complete: true },
      { key: 'subtasks', label: '关键任务', complete: true },
    ])
  })

  it('shows only role-authorized todo items', () => {
    expect(getProjectTodo(project('draft'), {
      isSuperAdmin: false, isCompanyCeo: false, isRealProjectCeo: false, isRealOwner: true,
    }, [], [])).toBeNull()
    expect(getProjectTodo(project('draft'), {
      isSuperAdmin: false, isCompanyCeo: true, isRealProjectCeo: false, isRealOwner: false,
    }, [], [])).toMatchObject({ action: 'edit', actionLabel: '继续完善项目' })
    expect(getProjectTodo(project('dispatched'), {
      isSuperAdmin: false, isCompanyCeo: false, isRealProjectCeo: false, isRealOwner: true,
    }, [], [])).toMatchObject({ action: 'ownerSubmit', actionLabel: '继续完善项目' })
    expect(getProjectTodo(project('returned'), {
      isSuperAdmin: false, isCompanyCeo: false, isRealProjectCeo: false, isRealOwner: true,
    }, [], [])).toMatchObject({ action: 'ownerSubmit', actionLabel: '修改项目计划' })
    expect(getProjectTodo(project('pending_review'), {
      isSuperAdmin: false, isCompanyCeo: false, isRealProjectCeo: true, isRealOwner: false,
    }, [], [])).toMatchObject({ action: 'approvalMaterials', actionLabel: '审核项目' })
    expect(getProjectTodo(project('pending_review'), {
      isSuperAdmin: false, isCompanyCeo: false, isRealProjectCeo: false, isRealOwner: true,
    }, [], [])).toBeNull()
    for (const status of ['active', 'pending_close', 'ended', 'archived'] as const) {
      expect(getProjectTodo(project(status), {
        isSuperAdmin: true, isCompanyCeo: false, isRealProjectCeo: true, isRealOwner: true,
      }, [], [])).toBeNull()
    }
  })
})
```

- [ ] **Step 2: Run the focused test and verify the expected failure**

Run: `npm run test:unit -- src/features/settings/projectsWorkbench.test.ts`

Expected: Vitest fails because `./projectsWorkbench` does not exist yet. Do not implement production code before observing this module-resolution failure.

### Task 2: Implement the minimal pure helper module

**Files:**
- Create: `frontend/src/features/settings/projectsWorkbench.ts`
- Test: `frontend/src/features/settings/projectsWorkbench.test.ts`

- [ ] **Step 1: Add the shared types and functions**

Implement the exact public surface used by Task 1:

```ts
import type { Project, TaskItem } from '../../types'
import type { SubTaskWithParent } from '../../api/subtasks'
import { getProjectPrimaryStatus } from '../../domain/projectLifecycleStatus'

export type ProjectWorkbenchOverviewStats = {
  all: number
  toComplete: number
  toApprove: number
  active: number
  archived: number
}

export type ProjectTodoRoles = {
  isSuperAdmin: boolean
  isCompanyCeo: boolean
  isRealProjectCeo: boolean
  isRealOwner: boolean
}

export type ProjectTodoAction = 'edit' | 'ownerSubmit' | 'approvalMaterials'
export type ProjectMaterialKey = 'objectives' | 'period' | 'tasks' | 'subtasks'
export type ProjectMaterialCheck = { key: ProjectMaterialKey; label: string; complete: boolean }

export type ProjectTodo = {
  project: Project
  action: ProjectTodoAction
  actionLabel: string
  title: string
  description: string
  materialChecks: ProjectMaterialCheck[]
}

export type ProjectLifecycleStage = {
  key: 'planning' | 'startup' | 'execution' | 'closing' | 'archive'
  label: string
  activeIndex: number
  detail: string
}

export function getProjectOverviewStats(projects: readonly Project[]): ProjectWorkbenchOverviewStats
export function getProjectMaterialChecklist(project: Project, tasks: readonly TaskItem[], subtasks: readonly SubTaskWithParent[]): ProjectMaterialCheck[]
export function getProjectTodo(project: Project, roles: ProjectTodoRoles, tasks: readonly TaskItem[], subtasks: readonly SubTaskWithParent[]): ProjectTodo | null
export function getProjectLifecycleStage(status: string): ProjectLifecycleStage
```

Use `getProjectPrimaryStatus(project)` in every status decision. Map `draft/dispatched/pending_review/returned` to planning, `active` to execution, `pending_close` to closing, `ended` to closing with a completed detail, and `archived` to archive. Keep the five visual nodes in a constant and never return `startup` as a current real status.

For material checks, use only `objectives.trim()`, both dates, task length, and subtask length. For todos, use the exact role matrix in the design spec; return `null` for `active`, `pending_close`, `ended`, and `archived`.

- [ ] **Step 2: Run the focused tests and verify they pass**

Run: `npm run test:unit -- src/features/settings/projectsWorkbench.test.ts`

Expected: all helper tests pass.

- [ ] **Step 3: Commit the helper red-green cycle**

```bash
git add frontend/src/features/settings/projectsWorkbench.ts frontend/src/features/settings/projectsWorkbench.test.ts
git commit -m "feat: add projects workbench derived state"
```

### Task 3: Add failing homepage structure coverage

**Files:**
- Create: `frontend/tests/projectsWorkbenchStructure.test.mjs`
- Test: `frontend/src/features/settings/ProjectsMgmtSection.tsx`

- [ ] **Step 1: Write source-level acceptance assertions**

Read the target file with `fs.readFileSync` and assert that the source contains `项目管理`, `管理项目从立项、启动到执行与归档`, `待我处理`, `全部项目`, `卡片视图`, `列表视图`, `viewMode`, and the five overview labels. Assert that the source no longer contains the exact old action text `完善材料`.

- [ ] **Step 2: Run the new structure test and verify it fails for the old layout**

Run: `npm run test:unit -- frontend/tests/projectsWorkbenchStructure.test.mjs`

Expected: the test fails because the old target still has the standalone search/table layout, no card/list state, and contains `完善材料`.

### Task 4: Add the two focused display components

**Files:**
- Create: `frontend/src/features/settings/ProjectOverviewStats.tsx`
- Create: `frontend/src/features/settings/ProjectTodoSection.tsx`

- [ ] **Step 1: Implement `ProjectOverviewStats`**

Export a component accepting `stats: ProjectWorkbenchOverviewStats`. Render five compact white cards in a responsive row with the exact labels `全部项目`, `待完善`, `待审批`, `进行中`, `已归档`; use number emphasis only, with no click-to-filter behavior.

- [ ] **Step 2: Implement `ProjectTodoSection`**

Export a component accepting a list of view models with `ProjectTodo`, `ownerName`, and `coachName`, plus `onAction(todo)`. Render nothing for an empty list. Render a compact section title `待我处理` with count, explanatory subtitle, a vertical list limited by the parent to three items unless expanded, material checks only for dispatched/returned items, and the todo action button. The button must call `onAction(todo)` and stop propagation; the section must not navigate or call API handlers itself.

- [ ] **Step 3: Run TypeScript checking for the new components**

Run: `npm run build`

Expected: the build may still fail only because the components are not imported or used consistently yet; fix only component typing/import errors before moving to Task 5.

### Task 5: Wire the workbench layout into `ProjectsMgmtSection`

**Files:**
- Modify: `frontend/src/features/settings/ProjectsMgmtSection.tsx`

- [ ] **Step 1: Add imports and local display state**

Import the helper functions and the two display components. Add:

```ts
const [viewMode, setViewMode] = useState<'card' | 'list'>('card')
const [showAllTodos, setShowAllTodos] = useState(false)
```

- [ ] **Step 2: Derive overview and todo data from existing state**

Use `roleFilteredProjects` for overview and todo counts so search does not hide actionable work. Build each project’s roles from the existing `members`, `currentUser`, and `myPersonId` values; pass `projectTasksMap[project.id]` and `projectSubtasksMap[project.id]` to `getProjectTodo`. Add owner/Coach display names from the existing member snapshots using `summarizeProjectRoleLine`. Keep `filteredProjects`, `currentPageItems`, and pagination unchanged for the all-project section.

- [ ] **Step 3: Replace only the homepage render shell**

Change the render between the loading branch and the existing modal/menu blocks to:

1. a page header with title/subtitle and the existing `isFullAdmin` new/import buttons;
2. `<ProjectOverviewStats stats={overviewStats} />`;
3. `<ProjectTodoSection ... />` using `todoItems.slice(0, 3)` unless `showAllTodos` is true and a compact expand button when more than three exist;
4. an `全部项目（{roleFilteredProjects.length}）` section header containing the existing `searchQuery` input and `卡片视图`/`列表视图` buttons;
5. `viewMode === 'card'` rendering `currentPageItems.map(...)` through the existing `LifecycleCard`;
6. `viewMode === 'list'` retaining the current table markup and pagination.

The header search input must be removed. Keep batch import next to new project as a secondary outlined action. Keep every modal, `LifecycleMoreMenu`, close drawer, and handler invocation intact.

- [ ] **Step 4: Wire todo actions to existing handlers/routes**

Implement the parent callback with the existing behavior:

```ts
if (todo.action === 'edit') void openProjectEditor(todo.project)
if (todo.action === 'ownerSubmit') navigate(`/home/projects/${todo.project.id}/owner-submit`)
if (todo.action === 'approvalMaterials') setApprovalMaterialsProject(todo.project)
```

Do not add `setOwnerFillProject`; the repository’s existing OwnerSubmit route is the canonical current implementation.

- [ ] **Step 5: Run the structure test and focused helper tests**

Run: `npm run test:unit -- frontend/tests/projectsWorkbenchStructure.test.mjs src/features/settings/projectsWorkbench.test.ts`

Expected: both tests pass; the structure test confirms the new labels and absence of `完善材料`.

### Task 6: Extend and reuse `LifecycleCard`

**Files:**
- Modify: `frontend/src/features/settings/ProjectsMgmtSection.tsx`

- [ ] **Step 1: Render the existing card in card mode**

Pass each card project’s existing `status`, `teamLine`, `mainAction`, busy state, return visibility, selection state, more-menu callback, and current action handler into `LifecycleCard`. Add an `onOpenProject` prop for the uniform `进入项目` button. Ensure every business button and the open-project button call `stopPropagation()` before their handler.

- [ ] **Step 2: Add the lifecycle stage strip**

Use `getProjectLifecycleStage(status)` and a fixed five-node array:

```ts
['立项准备', '启动', '执行', '结束', '归档']
```

Render a compact line/dot strip with the active index from the helper. Show the stage label and the separate `getProjectStatusBadge(project)` badge. Do not infer or display a database `startup` status.

- [ ] **Step 3: Update action text and next-step copy**

Replace the table action text `完善材料` with `完善项目计划`; use `继续完善项目` only in the todo card. Keep existing labels and handlers for project editing, dispatch, approval, work progress, close review, end archive, and project archive.

- [ ] **Step 4: Run the complete frontend build**

Run: `npm run build`

Expected: TypeScript and Vite both exit with code 0.

### Task 7: Regression verification and handoff

**Files:**
- Modify only if a test is explicitly obsolete due to this homepage layout: `frontend/tests/projectsWorkbenchStructure.test.mjs` or a project-management-specific test.

- [ ] **Step 1: Run all frontend unit tests**

Run: `npm run test:unit`

Expected: all existing and new tests pass. If a failure concerns an old homepage DOM structure, update only that obsolete assertion; if it protects a handler, permission, route, API, or lifecycle rule, fix the implementation instead.

- [ ] **Step 2: Inspect the final diff and protected-scope changes**

Run:

```bash
git diff --check
git status --short
git diff -- frontend/src/features/settings/ProjectsMgmtSection.tsx frontend/src/features/settings/projectsWorkbench.ts frontend/src/features/settings/ProjectOverviewStats.tsx frontend/src/features/settings/ProjectTodoSection.tsx frontend/tests/projectsWorkbenchStructure.test.mjs
```

Confirm no backend, migration, API contract, Sidebar, Dashboard, or unrelated user files were changed by this task.

- [ ] **Step 3: Commit the implementation**

```bash
git add frontend/src/features/settings/ProjectsMgmtSection.tsx frontend/src/features/settings/projectsWorkbench.ts frontend/src/features/settings/projectsWorkbench.test.ts frontend/src/features/settings/ProjectOverviewStats.tsx frontend/src/features/settings/ProjectTodoSection.tsx frontend/tests/projectsWorkbenchStructure.test.mjs
git commit -m "feat: redesign projects management workbench"
```

- [ ] **Step 4: Report exact verification results**

Include the changed files, page structure, real-status-to-stage mapping, role-based todo rules, preserved workflows, backend/database/API change status, `npm run test:unit` output, `npm run build` output, and any unresolved issue. Do not claim completion without fresh command output.

## Self-review against the design spec

- Page header, lifecycle subtitle, new/import actions: Task 5.
- Five overview groups without filtering real statuses: Task 2 and Task 5.
- Role-authorized todo rules and material checks: Tasks 1, 2, 4, and 5.
- Default card view, retained list view, search and pagination: Task 5.
- Existing `LifecycleCard` reuse and five visual lifecycle nodes: Task 6.
- Correct action labels and preserved routes/modals/close/archive flows: Tasks 5 and 6.
- No backend/database/API/status changes: file map and Task 7 scope inspection.
- Focused tests, full tests, build, and diff verification: Tasks 1, 2, 3, 6, and 7.

No `TODO`, `TBD`, or unspecified implementation step is required by this plan.
