/** @vitest-environment jsdom */
import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useVoiceSubmission } from './useVoiceSubmission'

const { createUpdate, createUpdateBatch, createDrafts, resubmitSubmission } = vi.hoisted(() => ({
  createUpdate: vi.fn(),
  createUpdateBatch: vi.fn(),
  createDrafts: vi.fn(),
  resubmitSubmission: vi.fn(),
}))

vi.mock('../../api/updates', () => ({ createUpdate, createUpdateBatch }))
vi.mock('../../api/subtaskDrafts', () => ({ createDrafts }))
vi.mock('../../api/confirmations', () => ({ resubmitSubmission }))

describe('useVoiceSubmission returned report correction', () => {
  beforeEach(() => {
    localStorage.clear()
    createUpdate.mockReset()
    createUpdateBatch.mockReset()
    createDrafts.mockReset()
    resubmitSubmission.mockReset().mockResolvedValue({ ok: true })
  })

  it('resubmits the same report with the revised text and checked result without creating records or drafts', async () => {
    const progressCard = {
      type: 'progress' as const,
      matched_subtask_id: 8,
      matched_subtask_title: '交付准备',
      parent_task_id: 7,
      parent_key_task: '交付准备',
      completed: '更新后的进展',
      achievements: [],
      subtask_issues: [],
      next_steps: [],
      status_update: '进行中',
    }
    const onResubmitted = vi.fn().mockResolvedValue(undefined)
    localStorage.setItem('draft:41', JSON.stringify({ text: '修订后的汇报文字' }))
    const { result } = renderHook(() => useVoiceSubmission({
      reportScope: 'project',
      selectedProjectId: 2,
      selectedSubtaskId: null,
      selectedTaskContext: null,
      currentUser: { name: '成员甲' } as never,
      text: '修订后的汇报文字',
      mode: 'text',
      result: { summary: '核对后的摘要' },
      editValues: { summary: '核对后的摘要' },
      taskReports: [progressCard],
      keyTaskIssues: [],
      cardEdits: {},
      proposedSubtasks: [{ title: '建议事项', assignee: '成员甲', plan_time: '' }],
      projectTasksForSuggest: [],
      projects: [{ id: 2, name: '项目乙' }] as never,
      setPhase: vi.fn(),
      setError: vi.fn(),
      refreshHistory: vi.fn().mockResolvedValue(undefined),
      resubmission: { id: 41, supplementNote: '补充说明', draftStorageKey: 'draft:41' },
      onResubmitted,
    }))

    await act(async () => { await result.current.handleSubmitFinal() })

    expect(resubmitSubmission).toHaveBeenCalledWith(
      41,
      '补充说明',
      '成员甲',
      expect.objectContaining({ summary: '核对后的摘要', task_reports: [progressCard] }),
      '修订后的汇报文字',
    )
    expect(createUpdate).not.toHaveBeenCalled()
    expect(createUpdateBatch).not.toHaveBeenCalled()
    expect(createDrafts).not.toHaveBeenCalled()
    expect(onResubmitted).toHaveBeenCalledWith(41)
    expect(localStorage.getItem('draft:41')).toBeNull()
  })

  it('keeps the revision draft and extracted cards available when the server rejects resubmission', async () => {
    const setPhase = vi.fn()
    const setError = vi.fn()
    localStorage.setItem('draft:41', JSON.stringify({ text: '修订后的汇报文字' }))
    resubmitSubmission.mockImplementation(() => { throw new Error('汇报状态已变化') })
    const { result } = renderHook(() => useVoiceSubmission({
      reportScope: 'project',
      selectedProjectId: 2,
      selectedSubtaskId: null,
      selectedTaskContext: null,
      currentUser: { name: '成员甲' } as never,
      text: '修订后的汇报文字',
      mode: 'text',
      result: { summary: '核对后的摘要' },
      editValues: { summary: '核对后的摘要' },
      taskReports: [{
        type: 'progress', matched_subtask_id: 8, matched_subtask_title: '交付准备',
        parent_task_id: 7, parent_key_task: '交付准备', completed: '更新后的进展',
        achievements: [], subtask_issues: [], next_steps: [], status_update: '进行中',
      }],
      keyTaskIssues: [],
      cardEdits: {},
      proposedSubtasks: [],
      projectTasksForSuggest: [],
      projects: [{ id: 2, name: '项目乙' }] as never,
      setPhase,
      setError,
      refreshHistory: vi.fn().mockResolvedValue(undefined),
      resubmission: { id: 41, supplementNote: '补充说明', draftStorageKey: 'draft:41' },
      onResubmitted: vi.fn().mockResolvedValue(undefined),
    }))

    await act(async () => { await result.current.handleSubmitFinal() })

    expect(setError).toHaveBeenCalledWith('汇报状态已变化')
    expect(setPhase).toHaveBeenCalledWith('extracted')
    expect(localStorage.getItem('draft:41')).toBe(JSON.stringify({ text: '修订后的汇报文字' }))
    expect(createUpdate).not.toHaveBeenCalled()
    expect(createUpdateBatch).not.toHaveBeenCalled()
  })
})
