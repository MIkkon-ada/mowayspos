/* @vitest-environment jsdom */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { NewMeetingModal } from './NewMeetingModal'

const apiMocks = vi.hoisted(() => ({
  analyzeMeeting: vi.fn(),
  createProjectMeetingDocumentRun: vi.fn(),
  fetchProjectMeetingDocumentRun: vi.fn(),
  pollProjectMeetingDocumentRun: vi.fn(),
  addMeetingSkillSnapshot: vi.fn(),
  answerMeetingSkillQuestions: vi.fn(),
  createMeeting: vi.fn(),
  extractMeetingDocumentText: vi.fn(),
  preflightMeetingSkill: vi.fn(),
  resumeMeetingSkillRun: vi.fn(),
  updateMeeting: vi.fn(),
  getProjectMembers: vi.fn(),
  fetchPeople: vi.fn(),
}))

vi.mock('../../api/meetings', () => ({
  analyzeMeeting: apiMocks.analyzeMeeting,
  createProjectMeetingDocumentRun: apiMocks.createProjectMeetingDocumentRun,
  fetchProjectMeetingDocumentRun: apiMocks.fetchProjectMeetingDocumentRun,
  pollProjectMeetingDocumentRun: apiMocks.pollProjectMeetingDocumentRun,
  addMeetingSkillSnapshot: apiMocks.addMeetingSkillSnapshot,
  answerMeetingSkillQuestions: apiMocks.answerMeetingSkillQuestions,
  createMeeting: apiMocks.createMeeting,
  extractMeetingDocumentText: apiMocks.extractMeetingDocumentText,
  preflightMeetingSkill: apiMocks.preflightMeetingSkill,
  resumeMeetingSkillRun: apiMocks.resumeMeetingSkillRun,
  updateMeeting: apiMocks.updateMeeting,
}))

vi.mock('../../api/projects', () => ({ getProjectMembers: apiMocks.getProjectMembers }))
vi.mock('../../api/people', () => ({ fetchPeople: apiMocks.fetchPeople }))

const projectId = 4
const accountKey = 'account:88'

beforeEach(() => {
  window.sessionStorage.clear()
  apiMocks.createProjectMeetingDocumentRun.mockResolvedValue({ id: 13 })
  apiMocks.extractMeetingDocumentText.mockResolvedValue({ filename: '会议纪要.txt', text: '本周完成客户清单核对。' })
  apiMocks.pollProjectMeetingDocumentRun.mockResolvedValue({
    status: 'failed', error_code: 'provider_error', error_message: '上游服务不可用',
  })
  apiMocks.getProjectMembers.mockResolvedValue([])
  apiMocks.fetchPeople.mockResolvedValue([])
})

afterEach(() => cleanup())

describe('meeting analysis failure form continuity', () => {
  it('retains entered meeting information after a failed analysis run', async () => {
    const { container } = render(<NewMeetingModal
      projectId={projectId}
      accountKey={accountKey}
      onClose={vi.fn()}
      onCreated={vi.fn()}
    />)

    fireEvent.change(screen.getByPlaceholderText('例如：项目推进周例会'), { target: { value: '项目进度检查会' } })
    fireEvent.change(container.querySelector('input[type="date"]')!, { target: { value: '2026-10-18' } })
    fireEvent.change(screen.getByPlaceholderText('线上会议或具体地点'), { target: { value: '线上会议' } })
    const file = new File(['会议纪要正文'], '会议纪要.txt', { type: 'text/plain' })
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByText('已就绪')).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'AI 生成草稿' }))

    await waitFor(() => expect(screen.getByText(/会议纪要 Agent 分析失败/)).toBeTruthy())
    expect((screen.getByPlaceholderText('例如：项目推进周例会') as HTMLInputElement).value).toBe('项目进度检查会')
    expect((container.querySelector('input[type="date"]') as HTMLInputElement).value).toBe('2026-10-18')
    expect((screen.getByPlaceholderText('线上会议或具体地点') as HTMLInputElement).value).toBe('线上会议')
  })
})
