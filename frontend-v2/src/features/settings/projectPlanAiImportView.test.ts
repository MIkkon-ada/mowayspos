import { describe, expect, it } from 'vitest'
import type { BatchImportRow } from '../../api/projects'
import { groupImportRows } from './projectPlanAiImportView'

const row = (project_name: string, workstream: string, key_task: string): BatchImportRow => ({
  project_name,
  workstream,
  key_task,
})

describe('project plan import review groups', () => {
  it('keeps first-seen workstreams together and preserves task order', () => {
    const groups = groupImportRows([
      row('项目 A', '工作方向 1', '任务 1'),
      row('项目 A', '工作方向 2', '任务 3'),
      row('项目 A', '工作方向 1', '任务 2'),
    ])

    expect(groups.map((group) => group.key)).toEqual(['项目 A::工作方向 1', '项目 A::工作方向 2'])
    expect(groups[0].rows.map((item) => item.key_task)).toEqual(['任务 1', '任务 2'])
    expect(groups[1].workstream).toBe('工作方向 2')
  })

  it('returns no review groups for an empty import', () => {
    expect(groupImportRows([])).toEqual([])
  })
})
