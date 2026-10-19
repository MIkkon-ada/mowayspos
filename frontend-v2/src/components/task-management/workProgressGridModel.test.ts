import { describe, expect, it } from 'vitest'
import { buildCellChange, normalizeGridView, parseClipboard, mergeGridDraft } from './workProgressGridModel'
import type { SubTaskItem } from '../../types'

const row = { id: 20, task_id: 10, title: '原任务', assignee: '张三', status: '进行中', updated_at: '2026-10-19T09:00:00Z', edit_version: '2026-10-19T09:00:00.123456Z' } as SubTaskItem

describe('work progress grid data integrity', () => {
  it('rejects edits to source facts and validates names and dates', () => {
    expect(() => buildCellChange(row, 'latestProgress', '伪造', ['张三'])).toThrow(/只读/)
    expect(() => buildCellChange(row, 'owner', '项目外人员', ['张三'])).toThrow(/项目成员/)
    expect(() => buildCellChange(row, 'dueDate', '2026-02-30', ['张三'])).toThrow(/日期/)
    expect(buildCellChange(row, 'dueDate', '2026/10/30', ['张三'])).toEqual({ due_date: '2026-10-30' })
  })
  it('merges fields on one row without losing the original version token', () => {
    const first = mergeGridDraft({}, row, { title: '新任务' })
    const next = mergeGridDraft(first, { ...row, updated_at: 'newer' }, { notes: '备注' })
    expect(next[20]).toEqual({ id: 20, expected_updated_at: row.edit_version, changes: { title: '新任务', notes: '备注' } })
  })
  it('handles spreadsheet quoted multiline cells', () => {
    expect(parseClipboard('任务\t"两行\n备注"\r\n另一项\t正常\r\n')).toEqual([['任务', '两行\n备注'], ['另一项', '正常']])
  })
  it('restores only supported view columns and safe freeze settings', () => {
    const view = normalizeGridView({ columns: ['keyTask', 'evil', 'owner', 'owner'], frozen: 99, groupBy: 'evil' })
    expect(view.columns).toEqual(['keyTask', 'owner'])
    expect(view.frozen).toBe(2)
    expect(view.groupBy).toBe('workstream')
  })
})
