/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ createMonthlyPlan: vi.fn() }))
vi.mock('../../api/monthlyPlans', () => api)

import { ExecutionPlanCreateDrawer } from './ExecutionPlanCreateDrawer'

const members = [
  { id: 1, project_id: 7, person_id: 11, person_name_snapshot: '吴肖', role: 'owner', note: '', joined_at: null },
  { id: 2, project_id: 7, person_id: 12, person_name_snapshot: '郭曙彬', role: 'member', note: '', joined_at: null },
]

describe('ExecutionPlanCreateDrawer', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('defaults the assignee to the key task owner', () => {
    render(<ExecutionPlanCreateDrawer keyTaskId={42} defaultAssigneeId={11} members={members} onClose={vi.fn()} onCreated={vi.fn()} />)

    expect((screen.getByLabelText('负责人') as HTMLSelectElement).value).toBe('11')
  })

  it('uses a compact, de-duplicated collaborator selector', () => {
    render(<ExecutionPlanCreateDrawer keyTaskId={42} defaultAssigneeId={11} members={[...members, { ...members[1], id: 3 }]} onClose={vi.fn()} onCreated={vi.fn()} />)

    const trigger = screen.getByRole('button', { name: '协助人' })
    expect(trigger.getAttribute('aria-expanded')).toBe('false')
    expect(document.querySelector('select[multiple]')).toBeNull()
    fireEvent.click(trigger)
    expect(trigger.getAttribute('aria-expanded')).toBe('true')
    expect(screen.getAllByRole('checkbox', { name: '郭曙彬' })).toHaveLength(1)
  })

  it('creates a plan for the current key task and closes on success', async () => {
    api.createMonthlyPlan.mockResolvedValue({ id: 99 })
    const onClose = vi.fn()
    const onCreated = vi.fn()
    render(<ExecutionPlanCreateDrawer keyTaskId={42} defaultAssigneeId={11} members={members} onClose={onClose} onCreated={onCreated} />)

    fireEvent.change(screen.getByLabelText('计划事项'), { target: { value: '完成模块梳理' } })
    fireEvent.change(screen.getByLabelText('预期成果'), { target: { value: '模块清单' } })
    fireEvent.click(screen.getByRole('button', { name: '创建计划' }))

    await waitFor(() => expect(api.createMonthlyPlan).toHaveBeenCalledWith(42, expect.objectContaining({
      title: '完成模块梳理',
      expected_output: '模块清单',
      assignee_id: 11,
      status: '未开始',
    })))
    expect(onCreated).toHaveBeenCalledOnce()
    expect(onClose).toHaveBeenCalledOnce()
  })
})
