/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
const api = vi.hoisted(() => ({ getProject: vi.fn(), getProjectMembers: vi.fn(), fetchTasks: vi.fn(), fetchSubTasksBatch: vi.fn(), approveProject: vi.fn(), returnProject: vi.fn(), reloadProjects: vi.fn() }))
vi.mock('../api/projects', () => ({ getProject: api.getProject, getProjectMembers: api.getProjectMembers, approveProject: api.approveProject, returnProject: api.returnProject }))
vi.mock('../api/tasks', () => ({ fetchTasks: api.fetchTasks }))
vi.mock('../api/subtasks', () => ({ fetchSubTasksBatch: api.fetchSubTasksBatch }))
vi.mock('../context/ProjectContext', () => ({ useProject: () => ({ currentUser: { person_id: 1, is_tech_admin: true }, reloadProjects: api.reloadProjects }) }))
vi.mock('react-router-dom', () => ({ useParams: () => ({ projectId: '2' }), useNavigate: () => vi.fn() }))
vi.mock('../features/settings/ProjectsMgmtSection', () => ({
  DetailPanel: ({ project, onOpenApprovalMaterials }: any) => <><p>{project.status}</p><button onClick={onOpenApprovalMaterials}>查看审核材料</button></>,
  ApprovalMaterialsWorkbenchModal: ({ onApprove, onReturn, planError, loading }: any) => <><p>{planError}</p><button disabled={loading || Boolean(planError)} onClick={onApprove}>审核通过</button><button onClick={() => onReturn('补充日期')}>退回修改</button></>,
}))
import ProjectDetailPage from './ProjectDetailPage'

beforeEach(() => {
  vi.clearAllMocks()
  api.getProject.mockResolvedValue({ id: 2, name: '待审项目', status: 'pending_review' })
  api.getProjectMembers.mockResolvedValue([])
  api.fetchTasks.mockResolvedValue([{ id: 10, key_task: '交付准备' }])
  api.fetchSubTasksBatch.mockResolvedValue({ '10': [{ id: 20, title: '检查清单' }] })
  api.approveProject.mockResolvedValue({ id: 2, name: '待审项目', status: 'active' })
  api.returnProject.mockResolvedValue({ id: 2, name: '待审项目', status: 'returned' })
  vi.spyOn(window, 'prompt').mockReturnValue('补充日期')
  vi.spyOn(console, 'error').mockImplementation(() => {})
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('project detail initiation actions', () => {
  it('actually approves and updates the project instead of only closing the modal', async () => {
    render(<ProjectDetailPage />)
    fireEvent.click(await screen.findByRole('button', { name: '查看审核材料' }))
    fireEvent.click(screen.getByRole('button', { name: '审核通过' }))
    await waitFor(() => expect(api.approveProject).toHaveBeenCalledWith(2, {}))
    expect(await screen.findByText('active')).toBeTruthy()
  })
  it('returns the project with a reason through the real API', async () => {
    render(<ProjectDetailPage />)
    fireEvent.click(await screen.findByRole('button', { name: '查看审核材料' }))
    fireEvent.click(screen.getByRole('button', { name: '退回修改' }))
    await waitFor(() => expect(api.returnProject).toHaveBeenCalledWith(2, '补充日期'))
    expect(await screen.findByText('returned')).toBeTruthy()
  })
  it('blocks approval when task loading failed while leaving the project visible', async () => {
    api.fetchTasks.mockRejectedValue(new Error('读取计划失败'))
    render(<ProjectDetailPage />)
    fireEvent.click(await screen.findByRole('button', { name: '查看审核材料' }))
    expect(screen.getByText('pending_review')).toBeTruthy()
    expect(screen.getByRole('button', { name: '审核通过' }).hasAttribute('disabled')).toBe(true)
  })
})
