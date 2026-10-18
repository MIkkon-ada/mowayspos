import { afterEach, describe, expect, it, vi } from 'vitest'
import { confirmSubmission, CONFIRMATION_COUNTS_INVALIDATED_EVENT, getPending } from './confirmations'

afterEach(() => vi.unstubAllGlobals())

describe('confirmation list request cancellation', () => {
  it('aborts the pending list request when its caller cancels', async () => {
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true })
    }))
    vi.stubGlobal('fetch', fetchMock)
    const controller = new AbortController()
    const pending = getPending(7, 'all', { signal: controller.signal })

    controller.abort()

    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(true)
  })
})

describe('confirmation count refresh signals', () => {
  it('announces a successful confirmation write so navigation badges refresh immediately', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }))))
    const dispatchEvent = vi.fn()
    vi.stubGlobal('window', { dispatchEvent })

    await confirmSubmission(12, '审核人')

    expect(dispatchEvent).toHaveBeenCalledWith(expect.objectContaining({
      type: CONFIRMATION_COUNTS_INVALIDATED_EVENT,
    }))
  })
})
