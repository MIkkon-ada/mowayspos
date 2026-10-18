/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getOwnerPlanDraft: vi.fn(), saveOwnerPlanDraft: vi.fn(), ownerSubmitProfile: vi.fn(), fetchPeople: vi.fn() }))
vi.mock('../../api/projects', async () => ({ ...(await vi.importActual<typeof import('../../api/projects')>('../../api/projects')), ...api }))
vi.mock('../../api/people', () => ({ fetchPeople: api.fetchPeople }))
vi.mock('./OwnerSubmitAiPanel', () => ({ OwnerSubmitAiPanel: () => null }))
import { OwnerSubmitWorkbench } from './OwnerSubmitModal'

const project = { id: 4, name: '客户项目', status: 'returned', objectives: '完成交付', user_roles: {} } as any
const plan = [{ id: 10, title: '交付准备', goal: '完整交付', acceptance_criteria: '客户验收', subtasks: [{ id: 20, title: '检查清单', assignee: 'PM', assignee_id: 1, plan_start: '2026-10-01', plan_end: '2026-10-12' }] }]
beforeEach(() => {
  vi.clearAllMocks()
  api.fetchPeople.mockResolvedValue([{ id: 1, name: 'PM', is_active: true }])
  api.getOwnerPlanDraft.mockResolvedValue({ draft: null, existing_plan: plan, saved_at: null, return_reason: '补充检查标准' })
  api.saveOwnerPlanDraft.mockResolvedValue({ saved_at: '2026-10-12T10:00:00Z' })
  api.ownerSubmitProfile.mockResolvedValue({ ...project, status: 'pending_review' })
})
afterEach(cleanup)

describe('owner planning continuity', () => {
  it('restores a returned plan and reviewer comment instead of an empty form', async () => {
    render(<OwnerSubmitWorkbench project={project} onClose={vi.fn()} />)
    expect(await screen.findByDisplayValue('检查清单')).toBeTruthy()
    expect(screen.getByText('补充检查标准')).toBeTruthy()
    expect(screen.getByDisplayValue('2026-10-01')).toBeTruthy()
  })
  it('saves incomplete fields without submitting the project', async () => {
    api.getOwnerPlanDraft.mockResolvedValue({ draft: { work_progress_draft: [{ title: '', subtasks: [{ title: '' }] }] }, existing_plan: [], saved_at: null, return_reason: '' })
    render(<OwnerSubmitWorkbench project={{ ...project, status: 'dispatched' }} onClose={vi.fn()} />)
    await waitFor(() => expect(screen.getByRole('button', { name: '保存草稿' }).hasAttribute('disabled')).toBe(false))
    fireEvent.click(screen.getByRole('button', { name: '保存草稿' }))
    await waitFor(() => expect(api.saveOwnerPlanDraft).toHaveBeenCalled())
    expect(api.saveOwnerPlanDraft.mock.calls[0][1].work_progress_draft[0].subtasks).toHaveLength(1)
    expect(api.ownerSubmitProfile).not.toHaveBeenCalled()
  })
  it('submits renamed tasks with their original IDs', async () => {
    render(<OwnerSubmitWorkbench project={project} onClose={vi.fn()} />)
    await screen.findByDisplayValue('检查清单')
    fireEvent.click(screen.getByRole('button', { name: '编辑重点工作名称' }))
    fireEvent.change(screen.getByPlaceholderText('请输入重点工作名称'), { target: { value: '交付检查' } })
    fireEvent.blur(screen.getByPlaceholderText('请输入重点工作名称'))
    fireEvent.click(screen.getByRole('button', { name: '重新提交计划审核' }))
    await waitFor(() => expect(api.ownerSubmitProfile).toHaveBeenCalled())
    const payload = api.ownerSubmitProfile.mock.calls[0][1]
    expect(payload.replace_plan).toBe(true)
    expect(payload.work_progress_draft[0].id).toBe(10)
    expect(payload.work_progress_draft[0].subtasks[0].id).toBe(20)
  })
  it('shows a blocking load error and retry instead of replacing the plan with blanks', async () => {
    api.getOwnerPlanDraft.mockRejectedValueOnce(new Error('网络失败'))
    render(<OwnerSubmitWorkbench project={project} onClose={vi.fn()} />)
    expect(await screen.findByRole('button', { name: '重新加载方案' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '重新提交计划审核' }).hasAttribute('disabled')).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: '重新加载方案' }))
    expect(await screen.findByDisplayValue('检查清单')).toBeTruthy()
  })
})
