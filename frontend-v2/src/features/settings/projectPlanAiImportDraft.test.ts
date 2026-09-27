import { describe, expect, it } from 'vitest'
import { draftToBatchImportRows } from './projectPlanAiImportDraft'

describe('AI work plan import draft conversion', () => {
  it('converts workstreams and subtasks while inheriting parent fields', () => {
    const rows = draftToBatchImportRows({
      project_profile: {
        name: '项目A',
        objectives: '完成目标',
        background: '',
        expected_outcomes: '',
        start_date: '',
        end_date: '',
        description: '',
        confidence: 0.9,
        evidence: [],
        warnings: [],
      },
      tasks: [{
        title: '重点工作A',
        description: '',
        goal: '形成成果',
        acceptance_criteria: '通过验收',
        process: '梳理→试运行',
        owner_name: '张三',
        owner_id: null,
        priority: '',
        status: '未开始',
        plan_start: '2026-09-01',
        plan_end: '2026-09-30',
        evidence: [{ attachment_id: null, file_name: '计划.xlsx', location: '复制推广!A3:E3', excerpt: '工作A' }],
        source: '',
        confidence: 0.9,
        merge_status: 'new',
        duplicate_of: null,
        duplicate_reason: '',
        warnings: [],
        subtasks: [{
          title: '关键任务A1',
          description: '',
          assignee_name: '',
          assignee_id: null,
          helper_names: [],
          helper_ids: [],
          priority: '',
          status: '',
          plan_start: '',
          plan_end: '',
          evaluation_standard: '',
          confidence: 0.9,
          evidence: [{ attachment_id: null, file_name: '计划.xlsx', location: '复制推广!A3:E3', excerpt: '任务A1' }],
          source: '',
          merge_status: 'new',
          duplicate_of: null,
          duplicate_reason: '',
          warnings: [],
        }],
      }],
      warnings: [],
      source_files: ['计划.xlsx'],
      provider: 'project.init.analysis',
      model_name: 'test-model',
      fallback_mode: 'ai',
    })

    expect(rows).toHaveLength(1)
    expect(rows[0]).toMatchObject({
      project_name: '项目A',
      workstream: '重点工作A',
      key_task: '关键任务A1',
      project_objective: '完成目标',
      owner: '张三',
      status: '未开始',
      plan_start: '2026-09-01',
      plan_end: '2026-09-30',
    })
    expect(rows[0].notes).toContain('计划.xlsx')
  })

  it('rejects an AI draft without a project or key task', () => {
    expect(() => draftToBatchImportRows({
      project_profile: { name: '', objectives: '', warnings: [], evidence: [] },
      tasks: [],
      warnings: [],
      source_files: [],
      provider: '',
      model_name: '',
      fallback_mode: 'ai',
    })).toThrow('项目')
  })
})
