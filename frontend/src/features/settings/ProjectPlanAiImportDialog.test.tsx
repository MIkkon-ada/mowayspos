/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ProjectPlanAiPreview } from '../../api/projectPlanAiImport'

const api = vi.hoisted(() => ({
  previewAiProjectPlan: vi.fn(),
  applyAiProjectPlan: vi.fn(),
}))

vi.mock('../../api/projectPlanAiImport', async () => {
  const actual = await vi.importActual<typeof import('../../api/projectPlanAiImport')>('../../api/projectPlanAiImport')
  return { ...actual, ...api }
})

import { ProjectPlanAiImportDialog } from './ProjectPlanAiImportDialog'

const preview: ProjectPlanAiPreview = {
  project_profile: { name: '项目 A', objectives: '完成目标' },
  tasks: [{
    title: '工作方向 1',
    goal: '形成成果',
    acceptance_criteria: '通过验收',
    subtasks: [{
      title: '任务 1',
      assignee_name: '张三',
      status: '未开始',
      plan_start: '2026-09-01',
      plan_end: '2026-09-30',
      evidence: [{ attachment_id: null, file_name: '计划.xlsx', location: '工作表1!A2:E3', excerpt: '任务 1 来源摘要' }],
    }],
  }],
  warnings: [],
  source_files: ['计划.xlsx'],
  provider: 'project.init.analysis',
  model_name: 'test-model',
  fallback_mode: 'ai',
}

describe('compact project plan import dialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.previewAiProjectPlan.mockResolvedValue(preview)
  })

  afterEach(cleanup)

  it('starts with simple upload and paste choices', () => {
    render(<ProjectPlanAiImportDialog open projects={[]} onClose={vi.fn()} onImported={vi.fn()} />)

    expect(screen.getByRole('button', { name: '上传文件' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '粘贴表格' })).toBeTruthy()
    expect(screen.getByText('提供工作计划')).toBeTruthy()
  })

  it('shows grouped review and reveals optional fields only after editing', async () => {
    render(<ProjectPlanAiImportDialog open projects={[]} onClose={vi.fn()} onImported={vi.fn()} />)
    const input = screen.getByLabelText('工作计划文件')
    fireEvent.change(input, { target: { files: [new File(['content'], '计划.xlsx')] } })
    fireEvent.click(screen.getByRole('button', { name: '开始分析' }))

    expect(await screen.findByRole('heading', { name: '工作推进方案' })).toBeTruthy()
    expect(screen.getByText('项目概览')).toBeTruthy()
    expect(screen.getByText('任务树')).toBeTruthy()
    expect(screen.getByDisplayValue('工作方向 1')).toBeTruthy()
    expect(screen.queryByDisplayValue('2026-09-01')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: '编辑任务 任务 1' }))
    await waitFor(() => expect(screen.getByDisplayValue('2026-09-01')).toBeTruthy())
    expect(screen.getByDisplayValue('张三')).toBeTruthy()
  })

  it('requires workstream adoption before import and opens source evidence', async () => {
    render(<ProjectPlanAiImportDialog open projects={[]} onClose={vi.fn()} onImported={vi.fn()} />)
    const input = screen.getByLabelText('工作计划文件')
    fireEvent.change(input, { target: { files: [new File(['content'], '计划.xlsx')] } })
    fireEvent.click(screen.getByRole('button', { name: '开始分析' }))

    const confirm = await screen.findByRole('button', { name: /确认导入/ })
    expect((confirm as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: '查看原文' }))
    expect(screen.getByText('原文对照')).toBeTruthy()
    expect(screen.getByText('任务 1 来源摘要')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '核对无误，采纳' }))
    await waitFor(() => expect((confirm as HTMLButtonElement).disabled).toBe(false))
  })

  it('explains when the preview used deterministic extraction', async () => {
    api.previewAiProjectPlan.mockResolvedValue({ ...preview, fallback_mode: 'deterministic' })
    render(<ProjectPlanAiImportDialog open projects={[]} onClose={vi.fn()} onImported={vi.fn()} />)
    const input = screen.getByLabelText('工作计划文件')
    fireEvent.change(input, { target: { files: [new File(['content'], '计划.xlsx')] } })
    fireEvent.click(screen.getByRole('button', { name: '开始分析' }))

    expect(await screen.findByText('AI 当前不可用，已自动切换为规则提取，请重点核对关键字段。')).toBeTruthy()
  })
})
