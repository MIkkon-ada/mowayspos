/* @vitest-environment jsdom */
import { useState } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { FormalProjectMeetingMinutes } from './FormalProjectMeetingMinutes'
import type { ProjectMeetingAgentFact } from '../../api/meetings'

const originalFact: ProjectMeetingAgentFact = {
  content: '原议程',
  evidence: [{ quote: '原议程', locator: '第 1 页·第 1 段' }],
  validation: { state: 'ready', errors: [] },
}

afterEach(cleanup)

function ReviewHarness() {
  const [draft, setDraft] = useState({
    meeting_date: '', location: '', host: '', participants: '', organizer: '', copied_to: '', summary: '',
    agendaItems: [originalFact], decisions: [], completedItems: [], nextStageWork: [], risks: [],
  })
  return <FormalProjectMeetingMinutes
    draft={draft}
    meetingInfoEvidence={{}}
    editable
    onFactsChange={(field, items) => setDraft((current) => ({ ...current, [field]: items }))}
  />
}

describe('meeting minutes review', () => {
  it('removes stale AI evidence when a reviewer changes a fact', () => {
    render(<ReviewHarness />)
    const sourceQuote = screen.getByText('“原议程”')
    expect(sourceQuote.closest('li')?.className).not.toContain('sr-only')
    expect(screen.getByText('第 1 页·第 1 段')).toBeTruthy()

    fireEvent.change(screen.getByLabelText('第1项内容'), { target: { value: '修订议程' } })

    expect(screen.queryByText('“原议程”')).toBeNull()
    expect(screen.getByText('人工修改；原有 AI 引用已移除')).toBeTruthy()
    expect((screen.getByLabelText('第1项内容') as HTMLTextAreaElement).value).toBe('修订议程')
  })

  it('shows grouped conclusions and the original action numbers', () => {
    render(<FormalProjectMeetingMinutes
      draft={{
        title: 'AI项目落地周会', meeting_date: '2026-08-24', meeting_type: '周会', location: '线上',
        host: '主持人', participants: '成员', organizer: '整理人', copied_to: '项目组', summary: '',
        agendaItems: [],
        completedItems: [{ content: '本周已完成计划核对', evidence: [], validation: { state: 'ready', errors: [] } }],
        risks: [{ content: '接口依赖待确认', evidence: [], validation: { state: 'ready', errors: [] } }],
        decisions: [{ content: '确认活动安排', topic: 'WorkBuddy活动', evidence: [], validation: { state: 'ready', errors: [] } }],
        nextStageWork: [{ content: '完成活动准备', code: '行动-01', evidence: [], validation: { state: 'ready', errors: [] } }],
        priorActionTracking: [{ content: '复盘上期进度', code: '追踪-01', evidence: [], validation: { state: 'ready', errors: [] } }],
      }}
      meetingInfoEvidence={{}}
      editable={false}
    />)
    expect(screen.getByText('（一）WorkBuddy活动')).toBeTruthy()
    expect(screen.getByText('行动-01')).toBeTruthy()
    expect(screen.getByText('追踪-01')).toBeTruthy()
    expect(screen.getByText('（二）上周待办追踪')).toBeTruthy()
    expect(screen.getByRole('heading', { level: 4, name: '本周已确认进展' })).toBeTruthy()
    expect(screen.getByRole('heading', { level: 4, name: '风险与待确认' })).toBeTruthy()
    expect(screen.queryByText('四、风险与待确认')).toBeNull()
  })
})
