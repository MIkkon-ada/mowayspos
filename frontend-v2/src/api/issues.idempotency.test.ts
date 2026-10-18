import { afterEach, describe, expect, it, vi } from 'vitest'
import { createIssue } from './issues'

afterEach(() => vi.unstubAllGlobals())

describe('issue create retry identity', () => {
  it('sends the stable request identity with the new issue payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      text: async () => JSON.stringify({ id: 18, description: '风险描述' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await createIssue({ project_id: 3, description: '风险描述' }, 'issue-request-0001')

    const [, request] = fetchMock.mock.calls[0]
    expect(JSON.parse(request.body as string)).toMatchObject({
      project_id: 3,
      description: '风险描述',
      client_request_id: 'issue-request-0001',
    })
  })
})
