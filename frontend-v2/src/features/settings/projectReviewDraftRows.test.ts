import { describe, expect, it } from 'vitest'
import { buildDraftRows } from './projectReviewDraftRows'

describe('buildDraftRows', () => {
  it('uses the key task collaborators and completion criteria instead of parent task fields', () => {
    const rows = buildDraftRows(
      [{ id: 10, key_task: '重点工作', collaborators: '上层协助人', completion_standard: '上层标准' } as any],
      [{
        id: 20,
        task_id: 10,
        parent_task_id: 10,
        title: '关键任务',
        assignee: '负责人',
        collaborator_ids: [101, 102],
        completion_criteria: '行级标准',
        plan_time: '2026-06-01',
        notes: '需法务确认',
      } as any],
      { id: 1, name: '项目', objectives: '项目目标' } as any,
      [{ person_id: 101, person_name_snapshot: '甲' }, { person_id: 102, person_name_snapshot: '乙' }] as any,
    )

    expect(rows[0]).toMatchObject({ collaborator: '甲、乙', standard: '—', note: '行级标准；需法务确认' })
  })

  it('falls back to a legacy helper note and removes only that helper line from the displayed note', () => {
    const rows = buildDraftRows(
      [{ id: 10, key_task: '重点工作', completion_standard: '上层标准' } as any],
      [{
        id: 20,
        task_id: 10,
        parent_task_id: 10,
        title: '关键任务',
        assignee: '负责人',
        collaborators: [],
        completion_criteria: '',
        plan_time: '',
        notes: '协助人：甲、乙\n需法务确认',
      } as any],
      { id: 1, name: '项目' } as any,
      [] as any,
    )

    expect(rows[0]).toMatchObject({ collaborator: '甲、乙', standard: '—', note: '上层标准；需法务确认' })
  })

  it('uses collaborator IDs over a conflicting display-name array', () => {
    const rows = buildDraftRows(
      [{ id: 10, key_task: '重点工作' } as any],
      [{
        id: 20,
        task_id: 10,
        parent_task_id: 10,
        title: '关键任务',
        assignee: '负责人',
        collaborator_ids: [102],
        collaborators: ['错误人员'],
        completion_criteria: '行级标准',
        plan_time: '',
        notes: '',
      } as any],
      { id: 1, name: '项目' } as any,
      [{ person_id: 102, person_name_snapshot: '乙' }] as any,
    )

    expect(rows[0]?.collaborator).toBe('乙')
  })

  it('does not assign a parent collaborator to the placeholder row when no key task exists', () => {
    const rows = buildDraftRows(
      [{ id: 10, key_task: '重点工作', collaborators: '上层协助人', completion_standard: '标准' } as any],
      [],
      { id: 1, name: '项目' } as any,
      [] as any,
    )

    expect(rows[0]).toMatchObject({ collaborator: '—', isTaskOnly: true })
  })
})
