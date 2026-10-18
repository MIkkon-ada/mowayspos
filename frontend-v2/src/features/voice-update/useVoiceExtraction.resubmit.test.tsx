/** @vitest-environment jsdom */
import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useVoiceExtraction } from './useVoiceExtraction'
import type { TaskReport } from '../../api/updates'

const { extractOnly } = vi.hoisted(() => ({ extractOnly: vi.fn() }))

vi.mock('../../api/updates', () => ({ extractOnly }))
vi.mock('../../api/tasks', () => ({ fetchTasks: vi.fn().mockResolvedValue([]) }))

describe('useVoiceExtraction when retrying a returned report', () => {
  beforeEach(() => extractOnly.mockReset().mockResolvedValue(null))

  it('clears old structured cards before extraction so a failed retry cannot show them as new', async () => {
    const { result } = renderHook(() => useVoiceExtraction({
      reportScope: 'all',
      selectedProjectId: null,
      selectedTaskContext: null,
      selectedProjectIsActive: true,
      voiceCandidates: [],
      currentUser: { name: '成员甲' },
      text: '修订后的汇报内容',
      mode: 'text',
      selectedProvider: 'capability',
      setText: vi.fn(),
    }))
    const oldCard: TaskReport = {
      type: 'progress',
      matched_subtask_id: 1,
      matched_subtask_title: '旧任务',
      completed: '旧进展',
      achievements: [],
      subtask_issues: [],
      next_steps: [],
      status_update: '进行中',
    }

    act(() => result.current.setTaskReports([oldCard]))
    await act(async () => {
      try { await result.current.handleExtract() } catch { /* keep assertions focused on extracted state */ }
    })

    expect(result.current.phase).toBe('input')
    expect(result.current.taskReports).toEqual([])
    expect(result.current.result).toBeNull()
  })
})
