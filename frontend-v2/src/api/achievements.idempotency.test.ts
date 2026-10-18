import { afterEach, describe, expect, it, vi } from 'vitest'
import { createAchievement, createAchievementSubmission } from './achievements'

afterEach(() => vi.unstubAllGlobals())

describe('manual achievement create retry identity', () => {
  it('sends the stable request identity with the create payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      text: async () => JSON.stringify({ id: 18, name: '成果清单' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await createAchievement({ project_id: 3, name: '成果清单' }, 'achievement-request-0001')

    const [, request] = fetchMock.mock.calls[0]
    expect(JSON.parse(request.body as string)).toMatchObject({
      project_id: 3,
      name: '成果清单',
      client_request_id: 'achievement-request-0001',
    })
  })
})

describe('achievement submission retry identity', () => {
  it('sends the stable request identity with the submission payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ id: 19, name: '成果提交' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await createAchievementSubmission({
      project_id: 3,
      related_task_id: 7,
      name: '成果提交',
      attachment_ids: [11],
    }, 'achievement-submission-request-0001')

    const [, request] = fetchMock.mock.calls[0]
    expect(JSON.parse(request.body as string)).toMatchObject({
      project_id: 3,
      related_task_id: 7,
      attachment_ids: [11],
      client_request_id: 'achievement-submission-request-0001',
    })
  })
})
