import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMeeting } from './meetings'

afterEach(() => vi.unstubAllGlobals())

describe('meeting create retry identity', () => {
  it('sends the stable request identity with the meeting payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      text: async () => JSON.stringify({ id: 18, title: '项目周会' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await createMeeting({
      project_id: 3,
      title: '项目周会',
      meeting_type: '进展会',
      meeting_date: '2026-10-08',
      location: '',
      host: '',
      participants: '',
      organizer: '',
      copied_to: '',
      agenda_items_json: '[]',
      prior_action_items_json: '[]',
      source_mode: 'ai_analysis',
      summary: '',
      task_list_json: '[]',
      decision_items_json: '[]',
      risk_items_json: '[]',
      transcript_text: '会议原文',
    }, 'meeting-request-0001')

    const [, request] = fetchMock.mock.calls[0]
    expect(JSON.parse(request.body as string)).toMatchObject({
      project_id: 3,
      title: '项目周会',
      transcript_text: '会议原文',
      client_request_id: 'meeting-request-0001',
    })
  })
})
