/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  fetchPeople: vi.fn(),
  ownerSubmitProfile: vi.fn(),
}))

vi.mock('../../api/people', () => ({ fetchPeople: api.fetchPeople }))
vi.mock('../../api/projects', async () => ({
  ...(await vi.importActual<typeof import('../../api/projects')>('../../api/projects')),
  ownerSubmitProfile: api.ownerSubmitProfile,
}))
vi.mock('./OwnerSubmitAiPanel', () => ({ OwnerSubmitAiPanel: () => null }))

import { OwnerSubmitWorkbench } from './OwnerSubmitModal'

const project = {
  id: 4,
  code: 'P-TEST1',
  name: 'test1',
  status: 'pending_review',
  start_date: '',
  end_date: '',
  description: '',
  project_type: '不应展示的类型',
  client_name: '不应展示的客户',
  background: '',
  objectives: '',
  expected_outcomes: '不应以预期交付物展示',
  user_roles: {
    owner: null,
    coordinator: null,
    coach: null,
    members: [],
  },
} as any

describe('owner submit approved B layout', () => {
  beforeEach(() => {
    api.fetchPeople.mockResolvedValue([])
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders the project overview and workstream detail without redundant metadata', async () => {
    render(<OwnerSubmitWorkbench project={project} onClose={vi.fn()} />)

    expect(await screen.findByText('项目概览')).toBeTruthy()
    expect(screen.getByText('P-TEST1')).toBeTruthy()
    expect(screen.getByText('工作推进方案')).toBeTruthy()
    expect(screen.getAllByText('未命名重点工作').length).toBe(2)
    expect(screen.getByText('目标')).toBeTruthy()
    expect(screen.getByText('验收标准 / 关键成果')).toBeTruthy()
    expect(screen.getByText('推进流程')).toBeTruthy()
    expect(screen.getByTestId('owner-submit-goal-result').getAttribute('data-layout')).toBe('stacked')
    expect(screen.getByRole('button', { name: '编辑重点工作名称' })).toBeTruthy()
    expect(screen.queryByPlaceholderText('请输入重点工作')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '编辑重点工作名称' }))
    expect(screen.getByPlaceholderText('请输入重点工作名称')).toBeTruthy()
    expect(screen.getByText('评价指标')).toBeTruthy()
    expect(screen.getByRole('table').className).toContain('lg:min-w-0')
    expect(screen.getByRole('button', { name: '返回项目详情' }).className).toContain('bg-slate-50')
    expect(screen.queryByText('项目类型')).toBeNull()
    expect(screen.queryByText('客户名称')).toBeNull()
    expect(screen.queryByText('预期交付物')).toBeNull()
    expect(screen.getByText('项目编号')).toBeTruthy()
    expect(screen.getByText('项目周期')).toBeTruthy()
    expect(screen.getByText('项目目标')).toBeTruthy()
    expect(screen.queryByText('项目编号 / 编码')).toBeNull()
    expect(screen.queryByText('项目周期 / 时间段')).toBeNull()
    expect(screen.queryByText('项目目标 / 完成准则')).toBeNull()
    expect(screen.getByTestId('owner-submit-goal-result').getAttribute('data-layout')).toBe('stacked')
    expect(screen.queryByText(/个关键任务/)).toBeNull()
    expect(screen.queryByText('继续新增重点工作')).toBeNull()
    expect(screen.getAllByText('负责人').some((element) => element.parentElement?.className.includes('owner-submit-project-role-row'))).toBe(true)
  })

  it('keeps one detail editor while switching among multiple workstreams', async () => {
    render(<OwnerSubmitWorkbench project={project} onClose={vi.fn()} />)
    await screen.findByText('项目概览')

    fireEvent.click(screen.getByRole('button', { name: '+ 新增重点工作' }))

    const workstreamButtons = screen.getAllByRole('button', { name: '未命名重点工作' })
    expect(workstreamButtons.length).toBe(2)
    fireEvent.click(workstreamButtons[1])

    expect(screen.getByText('02')).toBeTruthy()
    expect(screen.getAllByRole('heading', { name: '关键任务' }).length).toBe(1)
  })

  it('uses compact project rows, natural-height work content, and footer safe space', async () => {
    render(<OwnerSubmitWorkbench project={project} onClose={vi.fn()} />)
    await screen.findByText('项目概览')

    expect(screen.getByTestId('owner-submit-project-summary').getAttribute('data-layout')).toBe('compact')
    expect(screen.getByTestId('owner-submit-b-split').className).not.toContain('min-h-[560px]')
    expect(screen.getByTestId('owner-submit-workbench-main').className).toContain('pb-[88px]')
  })
})
