/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ createInitAnalysisRun: vi.fn(), getLatestInitAnalysisRun: vi.fn(), listInitAttachments: vi.fn(), retryInitAnalysisRun: vi.fn() }))
vi.mock('../../api/projectInitAi', async () => ({ ...(await vi.importActual<typeof import('../../api/projectInitAi')>('../../api/projectInitAi')), ...api }))
import { OwnerSubmitAiPanel } from './OwnerSubmitAiPanel'

function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((nextResolve) => { resolve = nextResolve }); return { promise, resolve } }
const failedRun = { id: 9, status: 'failed', stage: 'failed', progress: 100, error_message: '旧运行失败', draft: { tasks: [] }, result_metadata: {} } as any
const retryingRun = { ...failedRun, status: 'retrying', stage: 'retrying', progress: 10, error_message: '' } as any

function renderPanel() {
  return render(<OwnerSubmitAiPanel projectId={4} currentDraft={[] as any} existingAttachments={[{ id: 1, original_name: '推进表.xlsx' }] as any} onApplyDraft={vi.fn()} />)
}

describe('project-init analysis retry state', () => {
  beforeEach(() => { vi.clearAllMocks(); api.listInitAttachments.mockResolvedValue([{ id: 1, original_name: '推进表.xlsx' }]) })
  afterEach(cleanup)

  it('suppresses duplicate retry clicks and shows a neutral retry-pending state', async () => {
    const retry = deferred<typeof retryingRun>(); api.getLatestInitAnalysisRun.mockResolvedValue(failedRun); api.retryInitAnalysisRun.mockReturnValueOnce(retry.promise)
    renderPanel(); const retryButton = await screen.findByRole('button', { name: '重新分析' }); fireEvent.click(retryButton); fireEvent.click(retryButton)
    expect(api.retryInitAnalysisRun).toHaveBeenCalledTimes(1); expect(await screen.findByText('正在重新分析已上传文件…')).toBeTruthy(); expect(screen.queryByText('旧运行失败')).toBeNull()
    retry.resolve(retryingRun); expect(await screen.findByText('重试中')).toBeTruthy()
  })

  it('keeps recovery available when retrying a failed run also fails', async () => {
    api.getLatestInitAnalysisRun.mockResolvedValue(failedRun); api.retryInitAnalysisRun.mockRejectedValueOnce(new Error('重试服务不可用')); api.createInitAnalysisRun.mockResolvedValueOnce({ ...retryingRun, status: 'completed', stage: 'completed', progress: 100 })
    renderPanel(); fireEvent.click(await screen.findByRole('button', { name: '重新分析' })); expect((await screen.findAllByText('重试服务不可用')).length).toBeGreaterThan(0); fireEvent.click(screen.getByRole('button', { name: '重新分析' }))
    await waitFor(() => expect(api.createInitAnalysisRun).toHaveBeenCalledTimes(1))
  })

  it('removes a completed preview before it starts a fresh analysis', async () => {
    const previewRun = { ...retryingRun, status: 'completed', stage: 'completed', progress: 100, draft: { tasks: [{ title: '旧预览任务', description: '', subtasks: [], warnings: [], evidence: [], merge_status: 'new' }] } }
    const creation = deferred<typeof retryingRun>(); api.getLatestInitAnalysisRun.mockResolvedValue(previewRun); api.createInitAnalysisRun.mockReturnValueOnce(creation.promise)
    renderPanel(); const rerun = await screen.findByRole('button', { name: '重新分析' }); expect(screen.getByText('旧预览任务')).toBeTruthy(); fireEvent.click(rerun); fireEvent.click(rerun)
    await waitFor(() => expect(api.createInitAnalysisRun).toHaveBeenCalledTimes(1)); expect(screen.queryByText('旧预览任务')).toBeNull()
  })
})
