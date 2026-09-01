# 项目审核关键任务字段映射 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让项目审核材料按关键任务行展示负责人、协助人、计划时间和完成标准，并去除备注中重复的旧协助人文本。

**Architecture:** 将审核表的纯行构造逻辑从页面组件提取至独立模块。项目读取接口只提供关键任务的 `collaborator_ids`，模块以 `ProjectMember.person_name_snapshot` 解析这些 ID；ID 始终是协助人的权威来源。关键任务 `completion_criteria` 和清理后的真实备注共同显示在行的“备注/标准”列。

**Tech Stack:** React 19、TypeScript、Vitest、Python pytest 源码结构回归检查。

---

### Task 1: 为行级字段映射建立失败的单元测试

**Files:**
- Create: `frontend/src/features/settings/projectReviewDraftRows.test.ts`
- Test: `frontend/src/features/settings/projectReviewDraftRows.test.ts`

- [ ] **Step 1: 写入失败测试，固定关键任务优先级与旧备注兼容规则**

```ts
import { describe, expect, it } from 'vitest'
import { buildDraftRows } from './projectReviewDraftRows'

describe('buildDraftRows', () => {
  it('uses the key task collaborators and completion criteria, not parent task fields', () => {
    const rows = buildDraftRows(
      [{ id: 10, key_task: '重点工作', collaborators: '上层协助人', completion_standard: '上层标准' } as any],
      [{ id: 20, task_id: 10, parent_task_id: 10, title: '关键任务', assignee: '负责人', collaborator_ids: [101, 102], completion_criteria: '行级标准', plan_time: '2026-06-01', notes: '需法务确认' } as any],
      { id: 1, name: '项目', objectives: '项目目标' } as any,
      [{ person_id: 101, person_name_snapshot: '甲' }, { person_id: 102, person_name_snapshot: '乙' }] as any,
    )
    expect(rows[0]).toMatchObject({ collaborator: '甲、乙', standard: '—', note: '行级标准；需法务确认' })
  })

  it('falls back to a legacy helper note and removes only that helper line from the displayed note', () => {
    const rows = buildDraftRows(
      [{ id: 10, key_task: '重点工作', completion_standard: '上层标准' } as any],
      [{ id: 20, task_id: 10, parent_task_id: 10, title: '关键任务', assignee: '负责人', collaborators: [], completion_criteria: '', plan_time: '', notes: '协助人：甲、乙\\n需法务确认' } as any],
      { id: 1, name: '项目' } as any, [] as any,
    )
    expect(rows[0]).toMatchObject({ collaborator: '甲、乙', standard: '—', note: '上层标准；需法务确认' })
  })

  it('does not assign a parent collaborator to the placeholder row when no key task exists', () => {
    const rows = buildDraftRows(
      [{ id: 10, key_task: '重点工作', collaborators: '上层协助人', completion_standard: '标准' } as any], [],
      { id: 1, name: '项目' } as any, [] as any,
    )
    expect(rows[0]).toMatchObject({ collaborator: '—', isTaskOnly: true })
  })
})
```

- [ ] **Step 2: 运行测试确认当前缺少实现**

Run: `npm run test:unit -- --run src/features/settings/projectReviewDraftRows.test.ts`

Expected: FAIL，提示无法解析 `./projectReviewDraftRows`。

### Task 2: 实现关键任务行构造模块并接入审核页

**Files:**
- Create: `frontend/src/features/settings/projectReviewDraftRows.ts`
- Modify: `frontend/src/features/settings/ProjectsMgmtSection.tsx:16-31,228-274`
- Test: `frontend/src/features/settings/projectReviewDraftRows.test.ts`

- [ ] **Step 1: 新建纯映射模块，使用结构化协助人并清理旧兼容行**

```ts
import type { Project, ProjectMember, TaskItem } from '../../types'
import type { SubTaskWithParent } from '../../api/subtasks'

export type ProjectReviewDraftRow = {
  objective: string; keyTask: string; standard: string; seq: string
  subTask: string; assignee: string; planRange: string; collaborator: string
  note: string; isTaskOnly: boolean
}

const DASH = '—'

function legacyHelperAndNote(notes?: string): { helper: string; note: string } {
  const lines = (notes ?? '').split(/\\r?\\n/)
  let helper = ''
  const kept = lines.filter((line) => {
    const match = line.trim().match(/^协助人[：:]\\s*(.+)$/)
    if (!match) return true
    helper ||= match[1].trim()
    return false
  })
  return { helper, note: kept.join('\\n').trim() }
}

function keyTaskCollaborator(subtask: SubTaskWithParent, projectMembers: ProjectMember[]): string {
  const memberNames = new Map(projectMembers.map((member) => [member.person_id, member.person_name_snapshot.trim()]))
  const ids = subtask.collaborator_ids ?? []
  const resolved = ids.map((id) => memberNames.get(id) ?? '').filter(Boolean)
  return resolved.length > 0 ? [...new Set(resolved)].join('、') : ids.length === 0 ? legacyHelperAndNote(subtask.notes).helper || DASH : DASH
}

export function buildDraftRows(tasks: TaskItem[], subtasks: SubTaskWithParent[], project: Project, projectMembers: ProjectMember[]): ProjectReviewDraftRow[] {
  const objectiveText = project.objectives?.trim()
  const objective = objectiveText ? (objectiveText.length > 10 ? `${objectiveText.slice(0, 10)}…` : objectiveText) : DASH
  return tasks.flatMap((task) => {
    const children = subtasks.filter((subtask) => subtask.parent_task_id === task.id || subtask.task_id === task.id)
    if (children.length === 0) {
      return [{ objective, keyTask: task.key_task || DASH, standard: task.completion_standard?.trim() || DASH, seq: DASH,
        subTask: '关键任务待补充', assignee: task.owner?.trim() || DASH, planRange: task.plan_time?.trim() || DASH,
        collaborator: DASH, note: DASH, isTaskOnly: true }]
    }
    return children.map((subtask, index) => {
      const legacy = legacyHelperAndNote(subtask.notes)
      const criteria = subtask.completion_criteria?.trim() || task.completion_standard?.trim() || ''
      const noteParts = [criteria, legacy.note].filter(Boolean)
      return { objective, keyTask: task.key_task || DASH, standard: task.key_achievement?.trim() || DASH,
        seq: String(index + 1), subTask: subtask.title?.trim() || DASH, assignee: subtask.assignee?.trim() || DASH,
        planRange: subtask.plan_time?.trim() || task.plan_time?.trim() || DASH, collaborator: keyTaskCollaborator(subtask, projectMembers),
        note: noteParts.join('；') || DASH, isTaskOnly: false }
    })
  })
}
```

- [ ] **Step 2: 用新模块替换页面内联的 `DraftRow` / `buildDraftRows`**

```ts
import { buildDraftRows, type ProjectReviewDraftRow } from './projectReviewDraftRows'

const draftRows = buildDraftRows(tasks, subtasks, project, projectMembers)
```

删除 `ProjectsMgmtSection.tsx` 中本地 `DraftRow` 类型和 `buildDraftRows` 函数，表格属性改为 `ProjectReviewDraftRow[]`，避免两个实现分叉。

- [ ] **Step 3: 运行新单元测试，确认映射行为通过**

Run: `npm run test:unit -- --run src/features/settings/projectReviewDraftRows.test.ts`

Expected: PASS，3 个测试全部通过。

### Task 3: 运行回归检查并验证真实审核材料

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py:90-111`（仅当现有源码结构断言需随模块提取调整时）
- Test: `frontend/src/features/settings/projectReviewDraftRows.test.ts`
- Test: `bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py`

- [ ] **Step 1: 确认现有前端结构检查仍覆盖审核页入口**

Run: `bowei_ai_dashboard/.venv/Scripts/python.exe -m pytest -q bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py`

Expected: PASS；它仍能在审核页源文件中找到 `buildDraftRows`、`DraftProgressTable` 和汇总展示。

- [ ] **Step 2: 运行 TypeScript 单元回归和生产构建**

Run: `npm run test:unit -- --run src/features/settings/projectReviewDraftRows.test.ts && npm run build`

Expected: 所有定向测试通过，`tsc -b && vite build` 成功。

- [ ] **Step 3: 在已登录浏览器中复查 AI测试项目的审核材料**

打开“AI测试项目”的审核材料并检查有协助人的关键任务行：

```text
协助人列：袁金玉、郭熠彬、吴肖
备注/标准列：—（若原备注只有协助人）或保留的真实备注
```

再检查没有协助人的行仍显示“—”，每行标准显示在“备注/标准”列，并确认项目状态和数据未被修改。

- [ ] **Step 4: 执行变更卫生检查并提交本任务文件**

Run: `git diff --check -- frontend/src/features/settings/ProjectsMgmtSection.tsx frontend/src/features/settings/projectReviewDraftRows.ts frontend/src/features/settings/projectReviewDraftRows.test.ts docs/superpowers/specs/2026-08-30-project-review-key-task-field-mapping-design.md docs/superpowers/plans/2026-08-30-project-review-key-task-field-mapping.md`

Expected: 无输出。

Commit:

```bash
git add frontend/src/features/settings/ProjectsMgmtSection.tsx frontend/src/features/settings/projectReviewDraftRows.ts frontend/src/features/settings/projectReviewDraftRows.test.ts bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py docs/superpowers/specs/2026-08-30-project-review-key-task-field-mapping-design.md docs/superpowers/plans/2026-08-30-project-review-key-task-field-mapping.md
git commit -m "fix: map review fields to key tasks"
```
