# 工作推进表关键任务责任人筛选 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让工作推进表的负责人下拉及筛选完全以当前项目关键任务的责任人（`assignee`）为准。

**Architecture:** 把关键任务责任人的去重与重点工作匹配逻辑抽成一个纯前端领域模块，直接消费已有的 `taskSubMap` 批量读取结果，不增加接口。页面以该模块生成下拉选项和已筛选重点工作；项目上下文改变时清空已加载关键任务映射和失效的负责人筛选值。

**Tech Stack:** React、TypeScript、Vitest、Node.js test、Vite。

---

## 文件结构

- `frontend/src/domain/keyTaskAssigneeFilter.ts`：按关键任务责任人生成下拉名单并判断重点工作是否匹配的纯函数。
- `frontend/src/domain/keyTaskAssigneeFilter.test.ts`：纯函数的行为回归测试。
- `frontend/src/pages/TaskManagementPage.tsx`：使用纯函数渲染负责人下拉、筛选重点工作，并在项目切换时清理陈旧状态。
- `frontend/tests/workProgressExcelView.test.mjs`：断言页面不再使用项目负责人、并保留项目切换的清理逻辑。

### Task 1: 定义关键任务责任人筛选领域逻辑

**Files:**

- Create: `frontend/src/domain/keyTaskAssigneeFilter.ts`
- Create: `frontend/src/domain/keyTaskAssigneeFilter.test.ts`

- [ ] **Step 1: 写失败的纯函数测试**

```ts
import { describe, expect, it } from 'vitest'
import type { SubTaskItem, TaskItem } from '../types'
import { getKeyTaskAssigneeNames, taskHasKeyTaskAssignee } from './keyTaskAssigneeFilter'

const task = (id: number): TaskItem => ({ id, key_task: `重点工作 ${id}` } as TaskItem)
const keyTask = (taskId: number, assignee: string): SubTaskItem => ({
  id: taskId * 10, task_id: taskId, title: '关键任务', assignee,
  plan_time: '', status: '未开始',
})

describe('key-task assignee filter', () => {
  it('lists only distinct non-empty key-task assignees for loaded workstreams', () => {
    expect(getKeyTaskAssigneeNames([task(1), task(2)], {
      1: [keyTask(1, '李明'), keyTask(1, '王芳')],
      2: [keyTask(2, '李明'), keyTask(2, ' ')],
      999: [keyTask(999, '不属于当前项目')],
    })).toEqual(['李明', '王芳'])
  })

  it('matches a workstream only when it has a key task for the selected assignee', () => {
    const taskSubMap = { 1: [keyTask(1, '李明')], 2: [keyTask(2, '王芳')] }
    expect(taskHasKeyTaskAssignee(task(1), taskSubMap, '李明')).toBe(true)
    expect(taskHasKeyTaskAssignee(task(2), taskSubMap, '李明')).toBe(false)
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm run test:unit -- src/domain/keyTaskAssigneeFilter.test.ts`  
Expected: FAIL，模块 `keyTaskAssigneeFilter` 尚不存在。

- [ ] **Step 3: 以最小实现通过测试**

```ts
import type { SubTaskItem, TaskItem } from '../types'

export function getKeyTaskAssigneeNames(
  tasks: TaskItem[], taskSubMap: Record<number, SubTaskItem[]>,
): string[] {
  const names = tasks.flatMap((task) => taskSubMap[task.id] ?? [])
    .map((subtask) => subtask.assignee.trim()).filter(Boolean)
  return [...new Set(names)]
}

export function taskHasKeyTaskAssignee(
  task: TaskItem, taskSubMap: Record<number, SubTaskItem[]>, assignee: string,
): boolean {
  if (!assignee) return true
  return (taskSubMap[task.id] ?? []).some((subtask) => subtask.assignee.trim() === assignee)
}
```

该实现只读取传入 `tasks` 的键，因此不会把上一个项目残留映射中的责任人加入当前项目下拉。

- [ ] **Step 4: 运行测试确认通过**

Run: `npm run test:unit -- src/domain/keyTaskAssigneeFilter.test.ts`  
Expected: PASS，空责任人、重复责任人和不属于当前项目的映射项均不会进入下拉名单。

- [ ] **Step 5: 提交领域逻辑**

```bash
git add frontend/src/domain/keyTaskAssigneeFilter.ts frontend/src/domain/keyTaskAssigneeFilter.test.ts
git commit -m "feat: derive work-progress assignee filters from key tasks"
```

### Task 2: 将页面下拉与重点工作筛选改为关键任务责任人

**Files:**

- Modify: `frontend/src/pages/TaskManagementPage.tsx:1-20`
- Modify: `frontend/src/pages/TaskManagementPage.tsx:282`
- Modify: `frontend/src/pages/TaskManagementPage.tsx:421-456`
- Modify: `frontend/src/pages/TaskManagementPage.tsx:1000-1006`
- Test: `frontend/tests/workProgressExcelView.test.mjs`

- [ ] **Step 1: 写失败的页面结构回归测试**

```js
test('work-progress assignee filter uses key-task assignees instead of project owners', () => {
  const source = read(PAGE_FILE)
  assert.match(source, /getKeyTaskAssigneeNames\(tasks, taskSubMap\)/)
  assert.match(source, /taskHasKeyTaskAssignee\(t, taskSubMap, filterOwner\)/)
  assert.match(source, /assigneeNames\.map\(\(name\) => <option key=\{name\} value=\{name\}>\{name\}<\/option>\)/)
  assert.doesNotMatch(source, /resolvedTaskProjects\.flatMap\(\(p\) => p\.owners/)
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `node --test tests/workProgressExcelView.test.mjs`  
Expected: FAIL，页面当前仍以 `resolvedTaskProjects.flatMap((p) => p.owners ?? [])` 生成下拉名单。

- [ ] **Step 3: 接入页面状态和 JSX**

在 `TaskManagementPage.tsx` 顶部增加：

```ts
import { getKeyTaskAssigneeNames, taskHasKeyTaskAssignee } from '../domain/keyTaskAssigneeFilter'
```

替换项目 `owners` 聚合：

```ts
const assigneeNames = useMemo(
  () => getKeyTaskAssigneeNames(tasks, taskSubMap),
  [taskSubMap, tasks],
)
```

把 `planBaseTasks` 内的项目负责人判断替换为：

```ts
if (filterOwner && !taskHasKeyTaskAssignee(t, taskSubMap, filterOwner)) return false
```

将该 `useMemo` 的依赖补充 `taskSubMap`，保留 `resolvedTaskProjects`、`tasks`、`filterStatus`、`filterOwner`、`viewProjectId`，以便项目状态筛选继续按现有逻辑运行。最后将下拉选项替换为：

```tsx
{assigneeNames.map((name) => <option key={name} value={name}>{name}</option>)}
```

不得读取项目 `owners`、`collaborators`，也不得将协同人纳入负责人选项。

- [ ] **Step 4: 运行测试确认通过并执行类型构建**

Run: `node --test tests/workProgressExcelView.test.mjs; npm run test:unit -- src/domain/keyTaskAssigneeFilter.test.ts; npm run build`  
Expected: PASS，TypeScript 不再引用已删除的 `ownerNames`，构建成功。

- [ ] **Step 5: 提交页面筛选改动**

```bash
git add frontend/src/pages/TaskManagementPage.tsx frontend/tests/workProgressExcelView.test.mjs
git commit -m "fix: filter work progress by key-task assignee"
```

### Task 3: 在项目切换时清除陈旧的加载和筛选状态

**Files:**

- Modify: `frontend/src/pages/TaskManagementPage.tsx:332-339`
- Test: `frontend/tests/workProgressExcelView.test.mjs`

- [ ] **Step 1: 写失败的项目切换回归测试**

在 `frontend/tests/workProgressExcelView.test.mjs` 末尾增加：

```js
test('work-progress assignee filter resets stale key-task data when the project changes', () => {
  const source = read(PAGE_FILE)
  assert.match(source, /setTaskSubMap\(\{\}\)/)
  assert.match(source, /const keyTaskAssigneesLoaded = tasks\.every\(\(task\) => task\.id in taskSubMap\)/)
  assert.match(source, /if \(!keyTaskAssigneesLoaded \|\| !filterOwner \|\| assigneeNames\.includes\(filterOwner\)\) return/)
  assert.match(source, /setFilterOwner\(''\)/)
  assert.match(source, /getKeyTaskAssigneeNames\(tasks, taskSubMap\)/)
  assert.match(source, /taskHasKeyTaskAssignee\(t, taskSubMap, filterOwner\)/)
  assert.doesNotMatch(source, /resolvedTaskProjects\.flatMap\(\(p\) => p\.owners/)
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `node --test tests/workProgressExcelView.test.mjs`  
Expected: FAIL，页面尚未清空 `taskSubMap`，也没有等待关键任务加载完成的筛选值校验 effect。

- [ ] **Step 3: 实现项目切换清理和失效选择清理**

在现有以 `effectiveTaskProjectId` 为依赖的重置 effect 中加入：

```ts
setTaskSubMap({})
```

在 `assigneeNames` 定义之后加入：

```ts
const keyTaskAssigneesLoaded = tasks.every((task) => task.id in taskSubMap)

useEffect(() => {
  if (!keyTaskAssigneesLoaded || !filterOwner || assigneeNames.includes(filterOwner)) return
  setFilterOwner('')
}, [assigneeNames, filterOwner, keyTaskAssigneesLoaded])
```

项目变化先移除上个项目的关键任务映射；新项目批量加载结束后，若当前责任人不属于新项目关键任务负责人集合，筛选回到“全部负责人”。关键任务加载期间不应主动清除当前选择，避免空名单造成错误重置。

- [ ] **Step 4: 运行回归、构建和代码检查**

Run: `node --test tests/workProgressExcelView.test.mjs; npm run test:unit -- src/domain/keyTaskAssigneeFilter.test.ts; npm run build`  
Expected: PASS，结构回归、纯逻辑和 TypeScript 构建全部通过。

Run: `git diff --check`  
Expected: 无空白错误。

- [ ] **Step 5: 提交状态一致性修复**

```bash
git add frontend/src/pages/TaskManagementPage.tsx frontend/tests/workProgressExcelView.test.mjs
git commit -m "fix: reset stale work-progress assignee filter"
```

### Task 4: 最终验证

**Files:**

- Test: `frontend/src/domain/keyTaskAssigneeFilter.test.ts`
- Test: `frontend/tests/workProgressExcelView.test.mjs`

- [ ] **Step 1: 执行前端回归套件与构建**

Run: `npm run test:unit -- src/domain/keyTaskAssigneeFilter.test.ts; node --test tests/workProgressExcelView.test.mjs; npm run build`  
Expected: PASS，关键任务责任人名单、按责任人筛选、项目切换清理和现有推进表回归均通过。

- [ ] **Step 2: 手工验收**

在工作推进表中选择一个有多个关键任务责任人的项目，确认下拉仅列出这些 `assignee`；选择其中一人时，只保留包含该人员关键任务的重点工作。切换到不包含该人员的新项目后，确认下拉回到“全部负责人”；项目负责人和协同人不因其项目角色进入下拉。

- [ ] **Step 3: 最终工作区检查**

Run: `git diff --check; git status --short`  
Expected: 无空白错误；待提交文件仅限本计划列出的前端逻辑与测试文件，保留并不触碰其他既有改动。

## 自检结果

- **规格覆盖：** 关键任务责任人名单、负责人筛选、项目切换清理、空名单和回归验证均有明确任务。
- **类型一致性：** 纯函数统一使用 `TaskItem`、`SubTaskItem` 和 `Record<number, SubTaskItem[]>`；页面的责任人字段始终为关键任务 `assignee`。
- **范围控制：** 不修改后端、接口、项目成员字段或现有页面样式；不将协同人或项目负责人作为回退选项。
