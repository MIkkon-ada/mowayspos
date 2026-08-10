import { describe, expect, it } from 'vitest'
import type { AgentTask, ProjectInitAiDraft, ProjectInitCurrentDraft } from '../../api/projectInitAi'
import { buildAiMergePreview, mergeAiDraft } from './ownerSubmitDraft'

const evidence = {
  attachment_id: 11 as any,
  file_name: 'plan.pdf',
  location: 'page 2',
  excerpt: 'deliver the migration plan',
}

function aiTask(overrides: Partial<AgentTask> = {}): AgentTask {
  return {
    title: '新任务',
    description: 'AI 描述',
    owner_name: '张三',
    owner_id: 7 as any,
    priority: '高',
    status: '未开始',
    plan_start: '2026-08-01',
    plan_end: '2026-08-10',
    evidence: [evidence],
    source: '实施方案.pdf',
    confidence: 0.9,
    merge_status: 'new',
    duplicate_of: null,
    duplicate_reason: '',
    warnings: [],
    subtasks: [{
      title: '关键子任务',
      description: '子任务描述',
      assignee_name: '李四',
      assignee_id: 8 as any,
      helper_names: ['王五'],
      helper_ids: [9 as any],
      priority: '中',
      status: '未开始',
      plan_start: '',
      plan_end: '',
      evaluation_standard: '完成验收',
      confidence: 0.8,
      evidence: [evidence],
      source: '实施方案.pdf',
      merge_status: 'new',
      duplicate_of: null,
      duplicate_reason: '',
      warnings: [],
    }],
    ...overrides,
  }
}

function currentDraft(): ProjectInitCurrentDraft {
  return [{
    title: '已有任务',
    description: '手工描述',
    owner: '已有负责人',
    helper: '',
    plan_start: '',
    plan_end: '',
    subtasks: [{
      title: '已有子任务',
      evaluation_standard: '',
      assignee: '',
      assignee_id: null,
      helper: '',
      helper_ids: [],
      plan_start: '',
      plan_end: '',
    }],
  }]
}

describe('mergeAiDraft', () => {
  it('fills blank fields while preserving every non-empty current value', () => {
    const current = currentDraft()
    const result = mergeAiDraft(current, { tasks: [aiTask({ title: '已有任务', merge_status: 'new' })] }, [
      { key: 'task-0', action: 'supplement', itemType: 'task', taskIndex: 0, title: '已有任务' },
    ], { knownMemberIds: [7, 8, 9] })

    expect(result).not.toBe(current)
    expect(result[0]).not.toBe(current[0])
    expect(result[0].description).toBe('手工描述')
    expect(result[0].owner).toBe('已有负责人')
    expect(result[0].plan_start).toBe('2026-08-01')
    expect(result[0].subtasks[0].title).toBe('已有子任务')
    expect(result[0].subtasks).toHaveLength(2)
    expect((result[0] as any).evidence).toHaveLength(1)
    expect(current[0].description).toBe('手工描述')
  })

  it('honors new, ignore, and supplement decisions for duplicates', () => {
    const duplicate = aiTask({ title: '已有任务', merge_status: 'definite_duplicate' })
    const ignored = mergeAiDraft(currentDraft(), { tasks: [duplicate] }, [], { knownMemberIds: [7, 8, 9] })
    expect(ignored).toHaveLength(1)

    const added = mergeAiDraft(currentDraft(), { tasks: [duplicate] }, [
      { key: 'task-0', action: 'new', itemType: 'task', taskIndex: 0, title: duplicate.title },
    ], { knownMemberIds: [7, 8, 9] })
    expect(added).toHaveLength(2)

    const supplemented = mergeAiDraft(currentDraft(), { tasks: [duplicate] }, [
      { key: 'task-0', action: 'supplement', itemType: 'task', taskIndex: 0, title: duplicate.title },
    ], { knownMemberIds: [7, 8, 9] })
    expect(supplemented).toHaveLength(1)
  })

  it('does not bind ambiguous or inactive people and rejects invalid or unknown IDs', () => {
    const warned = aiTask({ warnings: [{ code: 'ambiguous_person', message: '需要确认', person_name: '张三' }] })
    const result = mergeAiDraft([], { tasks: [warned] }, [], { knownMemberIds: [7, 8, 9] })
    expect((result[0].subtasks[0] as any).assignee_id).toBeNull()
    expect((result[0].subtasks[0] as any).assignee).toBe('李四')

    expect(() => mergeAiDraft([], { tasks: [aiTask({ owner_id: 0 as any })] }, [])).toThrow(/positive integer/)
    expect(() => mergeAiDraft([], { tasks: [aiTask({ owner_id: 99 as any })] }, [], { knownMemberIds: [7, 8, 9] })).toThrow(/unknown member/)
  })

  it('requires an explicit decision for duplicate candidates and reports preview changes', () => {
    const draft = { tasks: [aiTask({ merge_status: 'possible_duplicate' })] }
    expect(buildAiMergePreview(currentDraft(), draft, [])).toMatchObject({ changeCount: 0 })
    const preview = buildAiMergePreview(currentDraft(), draft, [
      { key: 'task-0', action: 'new', itemType: 'task', taskIndex: 0, title: '新任务' },
    ], { knownMemberIds: [7, 8, 9] })
    expect(preview.changeCount).toBeGreaterThan(0)
    expect(preview.warnings).toEqual(expect.any(Array))
  })

  it('deduplicates evidence by source coordinates while retaining source_label', () => {
    const first = { ...evidence, source_label: '原始文件' }
    const second = { ...evidence, source_label: '合并提示' }
    const result = mergeAiDraft([], { tasks: [aiTask({ evidence: [first, second] })] }, [], { knownMemberIds: [7, 8, 9] })
    expect((result[0] as any).evidence).toHaveLength(1)
    expect((result[0] as any).evidence[0].source_label).toBe('原始文件')
  })

  it('removes an owner from helper ids and deduplicates helper ids without mutating the current draft', () => {
    const current = [{
      ...currentDraft()[0],
      owner_id: 7,
      helper_ids: [7, 9, 9],
    }] as any
    const ai = aiTask({ title: '已有任务', merge_status: 'definite_duplicate' })
    const result = mergeAiDraft(current, { tasks: [ai] }, [
      { key: 'task-0', action: 'supplement', itemType: 'task', taskIndex: 0, title: ai.title },
    ], { knownMemberIds: [7, 8, 9] })

    expect((result[0] as any).helper_ids).toEqual([9])
    expect(current[0].helper_ids).toEqual([7, 9, 9])
  })

  it('supports camel-case member fields and rejects unknown helper ids explicitly', () => {
    const current = [{
      ...currentDraft()[0],
      ownerId: 7,
      helperIds: [7, 9, 9],
    }] as any
    const ai = aiTask({ title: '已有任务', merge_status: 'definite_duplicate', owner_id: 7 as any })
    const result = mergeAiDraft(current, { tasks: [ai] }, [
      { key: 'task-0', action: 'supplement', itemType: 'task', taskIndex: 0, title: ai.title },
    ], { knownMemberIds: [7, 8, 9] })
    expect((result[0] as any).helperIds).toEqual([9])

    const invalid = aiTask({ helperIds: [99] } as any)
    expect(() => mergeAiDraft([], { tasks: [invalid] }, [], { knownMemberIds: [7, 8, 9] })).toThrow(/unknown member/i)
  })

  it('requires and applies each duplicate subtask decision under a new task', () => {
    const duplicateSubtask = { ...aiTask().subtasks[0], merge_status: 'possible_duplicate' as const, duplicate_of: null }
    const ai = aiTask({ merge_status: 'new', subtasks: [duplicateSubtask] })
    expect(() => mergeAiDraft([], { tasks: [ai] }, [], { knownMemberIds: [7, 8, 9] })).toThrow(/subtask.*decision/i)

    const ignored = mergeAiDraft([], { tasks: [ai] }, [
      { key: 'task-0-subtask-0', action: 'ignore', itemType: 'subtask', taskIndex: 0, subtaskIndex: 0, title: duplicateSubtask.title },
    ], { knownMemberIds: [7, 8, 9] })
    expect(ignored[0].subtasks).toHaveLength(0)
  })

  it('throws when supplement cannot resolve its task or subtask target', () => {
    const duplicateTask = aiTask({ merge_status: 'definite_duplicate', duplicate_of: 42 as any })
    expect(() => mergeAiDraft([], { tasks: [duplicateTask] }, [
      { key: 'task-0', action: 'supplement', itemType: 'task', taskIndex: 0, title: duplicateTask.title },
    ], { knownTaskIds: [42], knownMemberIds: [7, 8, 9] })).toThrow(/supplement.*task/i)

    const duplicateSubtask = { ...aiTask().subtasks[0], merge_status: 'possible_duplicate' as const, duplicate_of: 42 as any }
    const newTask = aiTask({ merge_status: 'new', subtasks: [duplicateSubtask] })
    expect(() => mergeAiDraft([], { tasks: [newTask] }, [
      { key: 'task-0-subtask-0', action: 'supplement', itemType: 'subtask', taskIndex: 0, subtaskIndex: 0, title: duplicateSubtask.title },
    ], { knownSubtaskIds: [42], knownMemberIds: [7, 8, 9] })).toThrow(/supplement.*subtask/i)
  })

  it('does not count a newly added task as a supplemented task', () => {
    const preview = buildAiMergePreview([], { tasks: [aiTask()] }, [], { knownMemberIds: [7, 8, 9] })
    expect(preview.addedTaskCount).toBe(1)
    expect(preview.supplementedTaskCount).toBe(0)
  })

  it('counts only actual supplemented fields and evidence', () => {
    const ai = aiTask({ title: '已有任务', merge_status: 'definite_duplicate' })
    const preview = buildAiMergePreview(currentDraft(), { tasks: [ai] }, [
      { key: 'task-0', action: 'supplement', itemType: 'task', taskIndex: 0, title: ai.title },
    ], { knownMemberIds: [7, 8, 9] })
    expect(preview.supplementedTaskCount).toBeGreaterThan(0)
  })
})
