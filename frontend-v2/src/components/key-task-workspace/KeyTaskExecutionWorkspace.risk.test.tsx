/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import type { KeyTaskWorkspace } from '../../api/keyTaskWorkspace'
import { KeyTaskExecutionWorkspace } from './KeyTaskExecutionWorkspace'

const api = vi.hoisted(() => ({
  fetchKeyTaskExecutionWorkspace: vi.fn(),
  setKeyTaskRisk: vi.fn(),
  confirmKeyTaskCompletion: vi.fn(),
  reopenKeyTask: vi.fn(),
  updateMonthlyPlan: vi.fn(),
  getProjectMembers: vi.fn(),
}))

vi.mock('../../api/keyTaskWorkspace', () => api)
vi.mock('../../api/monthlyPlans', () => ({ updateMonthlyPlan: api.updateMonthlyPlan }))
vi.mock('../../api/projects', () => ({ getProjectMembers: api.getProjectMembers }))
vi.mock('./CurrentProgressCard', () => ({ CurrentProgressCard: () => null }))
vi.mock('./ExecutionPlanCreateDrawer', () => ({ ExecutionPlanCreateDrawer: () => null }))
vi.mock('./ExecutionPlanDetailDrawer', () => ({ ExecutionPlanDetailDrawer: () => null }))
vi.mock('./ExecutionPlanSidebar', () => ({ ExecutionPlanSidebar: () => null }))
vi.mock('./ExecutionTimeline', () => ({ ExecutionTimeline: () => null }))
vi.mock('./IssueList', () => ({ IssueList: () => null }))
vi.mock('./AchievementList', () => ({ AchievementList: () => null }))
vi.mock('./KeyTaskRequirementCard', () => ({ KeyTaskRequirementCard: () => null }))

afterEach(cleanup)

const workspace = (riskNote = '') => ({
  key_task: {
    id: 9, title: '关键任务', status: '进行中', owner: { id: 2, name: '负责人' }, collaborators: [],
    start_date: null, due_kind: 'unknown', due_date: null, due_label: null, due_reference_date: null,
    plan_time: '', completion_definition: '', risk_note: riskNote, risk_marked_by: '', risk_marked_at: null,
    created_at: null, source_type: 'project_plan',
  },
  project: { id: 1, name: '项目一' }, workstream: { id: 3, name: '重点工作' }, current_progress: null,
  completion_eligibility: { state: 'in_progress', effective_plan_count: 0, completed_plan_count: 0, requires_owner_confirmation: false },
  plan_summary: { total: 0, completed: 0, in_progress: 0, not_started: 0, delayed: 0 },
  execution_plans: [], latest_submission: null, achievements: [], issues: [], timeline: [],
  permissions: { can_view: true, can_operate: true, can_manage_execution_plans: true, can_submit_update: true, can_confirm_completion: false, can_manage_risk: true },
}) as KeyTaskWorkspace

describe('KeyTaskExecutionWorkspace risk actions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.fetchKeyTaskExecutionWorkspace.mockResolvedValue(workspace())
    api.setKeyTaskRisk.mockResolvedValue({ ok: true })
  })

  function renderWorkspace(onRiskChanged?: () => void) {
    render(<MemoryRouter><KeyTaskExecutionWorkspace keyTaskId={9} projectId={1} onRiskChanged={onRiskChanged} /></MemoryRouter>)
  }

  it('opens and cancels the risk form without calling a browser prompt or writing data', async () => {
    renderWorkspace()
    fireEvent.click(await screen.findByRole('button', { name: '标记风险' }))
    expect(screen.getByRole('dialog', { name: '标记风险' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '标记风险' })).toBeNull())
    expect(api.setKeyTaskRisk).not.toHaveBeenCalled()
  })

  it('keeps the reason available after a failed save and closes only after success', async () => {
    const onRiskChanged = vi.fn()
    renderWorkspace(onRiskChanged)
    fireEvent.click(await screen.findByRole('button', { name: '标记风险' }))
    const input = screen.getByRole('textbox', { name: '风险原因' })
    fireEvent.change(input, { target: { value: '关键供应商延期' } })
    api.setKeyTaskRisk.mockRejectedValueOnce(new Error('网络连接失败'))
    fireEvent.click(screen.getByRole('button', { name: '保存风险' }))
    expect((await screen.findByRole('alert')).textContent).toContain('网络连接失败')
    expect((screen.getByRole('textbox', { name: '风险原因' }) as HTMLTextAreaElement).value).toBe('关键供应商延期')
    fireEvent.click(screen.getByRole('button', { name: '保存风险' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '标记风险' })).toBeNull())
    expect(api.setKeyTaskRisk).toHaveBeenNthCalledWith(2, 9, '关键供应商延期')
    expect(onRiskChanged).toHaveBeenCalledTimes(1)
  })

  it('requires a second explicit action to remove an existing risk mark', async () => {
    const onRiskChanged = vi.fn()
    api.fetchKeyTaskExecutionWorkspace.mockResolvedValue(workspace('关键供应商延期'))
    renderWorkspace(onRiskChanged)
    fireEvent.click(await screen.findByRole('button', { name: '解除风险' }))
    expect(screen.getByRole('dialog', { name: '解除风险' })).toBeTruthy()
    expect(api.setKeyTaskRisk).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '确认解除风险' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '解除风险' })).toBeNull())
    expect(api.setKeyTaskRisk).toHaveBeenCalledWith(9, '')
    expect(onRiskChanged).toHaveBeenCalledTimes(1)
  })
})
