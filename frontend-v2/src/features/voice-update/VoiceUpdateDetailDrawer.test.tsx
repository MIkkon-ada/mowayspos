/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { VoiceUpdateDetailDrawer } from './VoiceUpdateDetailDrawer'
import type { UpdateDetail } from '../../api/updates'

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
  afterEach(cleanup)

  it('opens the correction workbench instead of resubmitting the edited text directly', () => {
    const onReviseAndReextract = vi.fn()
    render(
      <VoiceUpdateDetailDrawer
        detailItem={detailItem}
        detailLoading={false}
        showTranscript
        onClose={vi.fn()}
        onToggleTranscript={vi.fn()}
        onReviseAndReextract={onReviseAndReextract}
      />,
    )

    const reportEditor = screen.getByRole('textbox', { name: '汇报内容' }) as HTMLTextAreaElement
    expect(reportEditor.value).toBe('原始进展内容')
    fireEvent.change(reportEditor, { target: { value: '修订后重新提取的内容' } })
    fireEvent.change(screen.getByPlaceholderText('补充说明（可选）'), {
      target: { value: '补充说明' },
    })
    fireEvent.click(screen.getByRole('button', { name: '修改并重新提取' }))

    expect(onReviseAndReextract).toHaveBeenCalledWith(41, '修订后重新提取的内容', '补充说明')
  })
})
