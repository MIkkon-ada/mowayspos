/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ExecutionPlan } from '../../api/keyTaskWorkspace'

const api = vi.hoisted(() => ({ createMonthlyPlan: vi.fn(), updateMonthlyPlan: vi.fn() }))
const planApi = vi.hoisted(() => ({ createTaskPlanProposalRun: vi.fn(), updateTaskPlanProposal: vi.fn(), applyTaskPlanProposalRun: vi.fn() }))
vi.mock('../../api/monthlyPlans', () => api)
vi.mock('../../api/keyTaskWorkspace', () => planApi)

import { ExecutionPlanCreateDrawer } from './ExecutionPlanCreateDrawer'

const members = [
  { id: 1, project_id: 7, person_id: 11, person_name_snapshot: '吴肖', role: 'owner', note: '', joined_at: null },
  { id: 2, project_id: 7, person_id: 12, person_name_snapshot: '郭曙彬', role: 'member', note: '', joined_at: null },
]

const editablePlan: ExecutionPlan = {
  id: 99,
  title: '完成页面流程与测试材料核对',
  status: '未开始',
  display_status: '已延期',
  assignee: '吴肖',
  assignee_id: 11,
  collaborator_ids: [12],
  collaborators: ['郭曙彬'],
  start_date: '2026-07-08',
  due_kind: 'exact',
  due_date: '2026-07-09',
  due_label: null,
  due_reference_date: null,
  expected_output: '核对结果已输出',
  actual_output: '',
  completion_criteria: '流程与测试材料均已核对',
  progress_note: '',
  latest_progress: null,
  risk_dependency: '',
  is_archived: false,
}

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

  it('uses AI to generate multiple reviewable drafts without creating a plan immediately', async () => {
    planApi.createTaskPlanProposalRun.mockResolvedValue({ id: 3, proposals: [] })
    render(<ExecutionPlanCreateDrawer keyTaskId={42} defaultAssigneeId={11} members={members} onClose={vi.fn()} onCreated={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: 'AI 拆解' }))
    fireEvent.change(screen.getByLabelText('待拆解文本'), { target: { value: '先整理客户清单，再安排访谈。' } })
    fireEvent.click(screen.getByRole('button', { name: '生成计划草稿' }))

    await waitFor(() => expect(planApi.createTaskPlanProposalRun).toHaveBeenCalledWith(42, '先整理客户清单，再安排访谈。', []))
    expect(api.createMonthlyPlan).not.toHaveBeenCalled()
  })

  it('sends multiple selected attachments to AI decomposition', async () => {
    planApi.createTaskPlanProposalRun.mockResolvedValue({ id: 3, attachments: [], proposals: [] })
    render(<ExecutionPlanCreateDrawer keyTaskId={42} defaultAssigneeId={11} members={members} onClose={vi.fn()} onCreated={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: 'AI 拆解' }))
    fireEvent.change(screen.getByLabelText('上传附件'), { target: { files: [new File(['A'], '安排.txt'), new File(['B'], '清单.txt')] } })
    fireEvent.click(screen.getByRole('button', { name: '生成计划草稿' }))

    await waitFor(() => expect(planApi.createTaskPlanProposalRun).toHaveBeenCalledWith(42, '', expect.arrayContaining([
      expect.objectContaining({ name: '安排.txt' }),
      expect.objectContaining({ name: '清单.txt' }),
    ])))
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

  it('updates the selected plan without creating a new plan', async () => {
    api.updateMonthlyPlan.mockResolvedValue({ id: editablePlan.id })
    const onClose = vi.fn()
    const onCreated = vi.fn()
    render(<ExecutionPlanCreateDrawer keyTaskId={42} defaultAssigneeId={11} members={members} plan={editablePlan} onClose={onClose} onCreated={onCreated} />)

    expect((screen.getByLabelText('计划事项') as HTMLInputElement).value).toBe(editablePlan.title)
    fireEvent.change(screen.getByLabelText('计划事项'), { target: { value: '完成修订后的材料核对' } })
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }))

    await waitFor(() => expect(api.updateMonthlyPlan).toHaveBeenCalledWith(editablePlan.id, expect.objectContaining({
      title: '完成修订后的材料核对',
      expected_output: editablePlan.expected_output,
      assignee_id: editablePlan.assignee_id,
    })))
    expect(api.createMonthlyPlan).not.toHaveBeenCalled()
    expect(onCreated).toHaveBeenCalledOnce()
    expect(onClose).toHaveBeenCalledOnce()
  })
})
