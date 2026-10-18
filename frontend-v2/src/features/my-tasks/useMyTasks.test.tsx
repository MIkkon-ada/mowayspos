/* @vitest-environment jsdom */
import { act, cleanup, render, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchMyTasks } from '../../api/subtasks'
import { useMyTasks } from './useMyTasks'

vi.mock('../../api/subtasks', () => ({ fetchMyTasks: vi.fn() }))
const projectContext = vi.hoisted(() => ({
  currentUser: { account_id: 4, person_id: 9, username: 'member' },
}))
vi.mock('../../context/ProjectContext', () => ({
  useProject: () => projectContext,
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  projectContext.currentUser = { account_id: 4, person_id: 9, username: 'member' }
})

function MyTasksHarness() {
  useMyTasks()
  return null
}

describe('my task data refresh', () => {
  it('reloads after the page regains focus and removes the focus listener on unmount', async () => {
    vi.mocked(fetchMyTasks).mockResolvedValue({ projects: [], tasks: [], ambiguous_assignment_count: 0 })
    const view = render(<MyTasksHarness />)
    await waitFor(() => expect(fetchMyTasks).toHaveBeenCalledTimes(1))

    act(() => window.dispatchEvent(new Event('focus')))
    await waitFor(() => expect(fetchMyTasks).toHaveBeenCalledTimes(2))

    view.unmount()
    act(() => window.dispatchEvent(new Event('focus')))
    expect(fetchMyTasks).toHaveBeenCalledTimes(2)
  })

  it('aborts the previous identity request and ignores its late response', async () => {
    type Result = Awaited<ReturnType<typeof fetchMyTasks>>
    const requests: Array<{ resolve: (result: Result) => void; signal?: AbortSignal }> = []
    vi.mocked(fetchMyTasks).mockImplementation((signal) => new Promise((resolve) => {
      requests.push({ resolve, signal })
    }))

    const { result, rerender } = renderHook(() => useMyTasks())
    await waitFor(() => expect(requests).toHaveLength(1))

    projectContext.currentUser = { account_id: 5, person_id: 10, username: 'another-member' }
    rerender()
    await waitFor(() => expect(requests).toHaveLength(2))
    expect(requests[0].signal?.aborted).toBe(true)

    await act(async () => requests[1].resolve({
      projects: [{ id: 2, name: '新账号项目' }],
      tasks: [],
      ambiguous_assignment_count: 0,
    }))
    await waitFor(() => expect(result.current.activeProjects).toEqual([{ id: 2, name: '新账号项目' }]))

    await act(async () => requests[0].resolve({
      projects: [{ id: 1, name: '旧账号项目' }],
      tasks: [],
      ambiguous_assignment_count: 0,
    }))
    expect(result.current.activeProjects).toEqual([{ id: 2, name: '新账号项目' }])
  })
})
