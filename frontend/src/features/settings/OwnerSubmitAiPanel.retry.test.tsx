/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  createInitAnalysisRun: vi.fn(),
  getLatestInitAnalysisRun: vi.fn(),
  listInitAttachments: vi.fn(),
  retryInitAnalysisRun: vi.fn(),
  uploadInitAttachments: vi.fn(),
}))
vi.mock('../../api/projectInitAi', async () => ({ ...(await vi.importActual<typeof import('../../api/projectInitAi')>('../../api/projectInitAi')), ...api }))
import { OwnerSubmitAiPanel } from './OwnerSubmitAiPanel'

const failedRun = { id: 9, status: 'failed', stage: 'failed', progress: 100, error_message: '旧运行失败', draft: { tasks: [] }, result_metadata: {} } as any

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
})
