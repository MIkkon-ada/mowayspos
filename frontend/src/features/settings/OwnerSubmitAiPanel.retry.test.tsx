/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  createInitAnalysisRun: vi.fn(),
  getInitAnalysisRun: vi.fn(),
  getLatestInitAnalysisRun: vi.fn(),
  listInitAttachments: vi.fn(),
  retryInitAnalysisRun: vi.fn(),
  uploadInitAttachments: vi.fn(),
}))
vi.mock('../../api/projectInitAi', async () => ({ ...(await vi.importActual<typeof import('../../api/projectInitAi')>('../../api/projectInitAi')), ...api }))
import { OwnerSubmitAiPanel } from './OwnerSubmitAiPanel'

const failedRun = { id: 9, status: 'failed', stage: 'failed', progress: 100, error_message: '旧运行失败', draft: { tasks: [] }, result_metadata: {} } as any
const completedStructuredRun = {
  id: 10,
  status: 'completed',
  stage: 'completed',
  progress: 100,
  error_message: '',
  draft: {
    project_profile: {
      name: '岗位 AI 应用优化',
      background: '岗位知识分散',
      objectives: '提升复用率',
      expected_outcomes: '形成案例库',
      start_date: '2026-07-01',
      end_date: '2026-09-30',
      description: '',
      confidence: 0.9,
      evidence: [{ attachment_id: 2, file_name: '工作推进表.xlsx', location: '概况!A1:B8', excerpt: '项目目标：提升复用率' }],
      warnings: [],
    },
    tasks: [{
      title: '重点工作', description: '', owner_name: '', owner_id: null, priority: '', status: '', plan_start: '', plan_end: '', evidence: [], source: '', confidence: 1, merge_status: 'new', duplicate_of: null, duplicate_reason: '', warnings: [],
      subtasks: [{
        title: '关键任务', description: '', assignee_name: '吴肖', assignee_id: 5, helper_names: ['郭熠彬'], helper_ids: [7], priority: '', status: '', plan_start: '2026-07-03', plan_end: '2026-07-10', evaluation_standard: '', confidence: 1, evidence: [], source: '', merge_status: 'new', duplicate_of: null, duplicate_reason: '',
        warnings: [{ code: 'will_join_project', message: '提交项目方案时将自动加入项目', person_name: '郭熠彬' }],
      }],
    }],
  },
  result_metadata: { model_name: 'structured-spreadsheet', attempted_models: [] },
} as any

function renderPanel() {
  return render(<OwnerSubmitAiPanel projectId={4} currentDraft={[] as any} existingAttachments={[{ id: 1, original_name: '推进表.xlsx' }] as any} onApplyDraft={vi.fn()} />)
}

describe('project-init analysis single-use upload flow', () => {
  beforeEach(() => { vi.clearAllMocks() })
  afterEach(cleanup)

  it('starts as a fresh upload session instead of restoring a failed historical run', async () => {
    api.getLatestInitAnalysisRun.mockResolvedValue(failedRun)
    api.listInitAttachments.mockResolvedValue([{ id: 1, original_name: '历史资料.xlsx' }])

    renderPanel()

    expect(await screen.findByText('选择资料文件')).toBeTruthy()
    expect(screen.queryByText('旧运行失败')).toBeNull()
    expect(api.getLatestInitAnalysisRun).not.toHaveBeenCalled()
    expect(api.listInitAttachments).not.toHaveBeenCalled()
  })

  it('clears a failed session and requires a newly selected file before another analysis', async () => {
    api.uploadInitAttachments.mockResolvedValueOnce([{ id: 2, original_name: '新资料.xlsx' }])
    api.createInitAnalysisRun.mockResolvedValueOnce(failedRun)

    renderPanel()
    const input = await screen.findByLabelText(/选择资料文件/)
    fireEvent.change(input, { target: { files: [new File(['source'], '新资料.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })] } })
    fireEvent.click(screen.getByRole('button', { name: '开始分析' }))
    fireEvent.click(await screen.findByRole('button', { name: '重新上传资料' }))

    expect(await screen.findByText('选择资料文件')).toBeTruthy()
    expect(screen.queryByText('旧运行失败')).toBeNull()
    expect(api.retryInitAnalysisRun).not.toHaveBeenCalled()
  })

  it('shows deterministic processing and a nonblocking project-join notice in the preview', async () => {
    api.uploadInitAttachments.mockResolvedValueOnce([{ id: 2, original_name: '工作推进表.xlsx' }])
    api.createInitAnalysisRun.mockResolvedValueOnce(completedStructuredRun)

    renderPanel()
    const input = await screen.findByLabelText(/选择资料文件/)
    fireEvent.change(input, { target: { files: [new File(['source'], '工作推进表.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })] } })
    fireEvent.click(screen.getByRole('button', { name: '开始分析' }))

    expect(await screen.findByText('实际处理器：structured-spreadsheet')).toBeTruthy()
    expect(screen.getByText('郭熠彬：提交时自动加入项目')).toBeTruthy()
    expect(screen.queryByText(/未自动绑定/)).toBeNull()
  })

  it('separates project-profile suggestions from work-progress suggestions', async () => {
    api.uploadInitAttachments.mockResolvedValueOnce([{ id: 2, original_name: '工作推进表.xlsx' }])
    api.createInitAnalysisRun.mockResolvedValueOnce(completedStructuredRun)

    renderPanel()
    fireEvent.change(await screen.findByLabelText(/选择资料文件/), { target: { files: [new File(['source'], '工作推进表.xlsx')] } })
    fireEvent.click(screen.getByRole('button', { name: '开始分析' }))
    fireEvent.click(await screen.findByRole('tab', { name: '项目基本信息' }))

    expect(await screen.findByText('项目基本信息识别结果')).toBeTruthy()
    expect(screen.getByText('岗位知识分散')).toBeTruthy()
    expect(screen.getByText('项目基本信息由立项人确认，本页不会直接覆盖。')).toBeTruthy()
    expect(screen.getByText('工作推进方案')).toBeTruthy()
  })

  it('leaves processing state when the run status request fails', async () => {
    api.uploadInitAttachments.mockResolvedValueOnce([{ id: 2, original_name: '工作推进表.xlsx' }])
    api.createInitAnalysisRun.mockResolvedValueOnce({
      id: 11,
      status: 'processing',
      stage: 'extracting',
      progress: 55,
      error_message: '',
      draft: { tasks: [] },
      result_metadata: {},
    } as any)
    api.getInitAnalysisRun.mockRejectedValueOnce(new Error('AI 分析服务暂时不可用，请稍后重试。'))

    renderPanel()
    fireEvent.change(await screen.findByLabelText(/选择资料文件/), { target: { files: [new File(['source'], '工作推进表.xlsx')] } })
    fireEvent.click(screen.getByRole('button', { name: '开始分析' }))

    expect(await screen.findByText('分析失败')).toBeTruthy()
    expect(screen.queryByText(/处理中.*55%/)).toBeNull()
  })
})
