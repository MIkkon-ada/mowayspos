/** @vitest-environment jsdom */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { VoiceUpdateDetailDrawer } from './VoiceUpdateDetailDrawer'
import type { UpdateDetail } from '../../api/updates'

const { resubmitSubmission } = vi.hoisted(() => ({ resubmitSubmission: vi.fn() }))

vi.mock('../../api/confirmations', () => ({ resubmitSubmission }))

const detailItem: UpdateDetail = {
  id: 41,
  submitter: '成员甲',
  source_type: '文字汇报',
  title: '本周进展',
  transcript_text: '原始进展内容',
  confirm_status: '已打回提交人',
  confidence: 0.8,
  created_at: '2026-10-18T08:00:00',
  reject_reason: '请补充延期原因',
  ai_result: {},
  human_result: {},
}

describe('VoiceUpdateDetailDrawer returned report resubmission', () => {
  beforeEach(() => resubmitSubmission.mockReset().mockResolvedValue({ ok: true }))

  it('edits and resubmits the same report with the original text available', async () => {
    const onResubmitted = vi.fn().mockResolvedValue(undefined)
    render(
      <VoiceUpdateDetailDrawer
        detailItem={detailItem}
        detailLoading={false}
        showTranscript
        onClose={vi.fn()}
        onToggleTranscript={vi.fn()}
        currentUserName="member_a"
        onResubmitted={onResubmitted}
      />,
    )

    const reportEditor = screen.getByRole('textbox', { name: '汇报内容' }) as HTMLTextAreaElement
    expect(reportEditor.value).toBe('原始进展内容')
    fireEvent.change(reportEditor, { target: { value: '修订后的进展内容' } })
    fireEvent.change(screen.getByPlaceholderText('补充说明（可选）'), {
      target: { value: '补充延期原因' },
    })
    fireEvent.click(screen.getByRole('button', { name: '修改并重新提交' }))

    await waitFor(() => expect(resubmitSubmission).toHaveBeenCalledWith(
      41,
      '补充延期原因',
      'member_a',
      undefined,
      '修订后的进展内容',
    ))
    expect(onResubmitted).toHaveBeenCalledWith(41)
  })
})
