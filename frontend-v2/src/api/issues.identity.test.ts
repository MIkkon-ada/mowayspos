import { afterEach, describe, expect, it, vi } from 'vitest'
import { assignIssueHelper } from './issues'
import type { IssueItem } from '../types'

describe('assignIssueHelper identity payload', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('sends the selected helper person ID with the display name', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{"id":17,"project_id":1}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const assignWithPersonId = assignIssueHelper as unknown as (
      issueId: number,
      helper: string,
      helperPersonId: number,
    ) => Promise<IssueItem>
    await assignWithPersonId(17, '同名成员', 2)

    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string)
    expect(body).toEqual({ helper: '同名成员', helper_person_id: 2 })
  })
})
