import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiGet, ApiError } from './client'

afterEach(() => vi.unstubAllGlobals())

describe('ApiError code compatibility', () => {
  it('reads a stable top-level code and preserves the detail message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: '仅项目成员可查看', code: 'PROJECT_ACCESS_DENIED' }),
      { status: 403, headers: { 'Content-Type': 'application/json' } },
    )))

    await expect(apiGet('/api/projects/7')).rejects.toMatchObject({
      status: 403,
      code: 'PROJECT_ACCESS_DENIED',
      message: '仅项目成员可查看',
    })
  })

  it('falls back to API_ERROR when old responses have only detail', async () => {
    const error = new ApiError(403, 'permission denied', { detail: 'permission denied' })
    expect(error.code).toBe('API_ERROR')
  })

  it('aborts a GET when its caller cancels the request', async () => {
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true })
    }))
    vi.stubGlobal('fetch', fetchMock)
    const controller = new AbortController()
    const pending = apiGet('/api/my-tasks', { signal: controller.signal })

    controller.abort()

    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(true)
  })

  it('reports a timeout distinctly and aborts the underlying GET', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true })
    }))
    vi.stubGlobal('fetch', fetchMock)
    try {
      const pending = apiGet('/api/my-tasks', { timeoutMs: 5_000 })
      const timedOut = expect(pending).rejects.toMatchObject({
        status: 0,
        code: 'TIMEOUT_ERROR',
        message: '请求超时，请稍后重试',
      })
      await vi.advanceTimersByTimeAsync(5_000)
      await timedOut
      expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(true)
    } finally {
      vi.useRealTimers()
    }
  })

  it('applies the standard 30-second timeout to GET requests', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true })
    }))
    vi.stubGlobal('fetch', fetchMock)
    try {
      const pending = apiGet('/api/projects')
      const timedOut = expect(pending).rejects.toMatchObject({ code: 'TIMEOUT_ERROR' })
      await vi.advanceTimersByTimeAsync(29_999)
      expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(false)
      await vi.advanceTimersByTimeAsync(1)
      await timedOut
      expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(true)
    } finally {
      vi.useRealTimers()
    }
  })

  it('keeps the timeout active while reading the response body', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => Promise.resolve({
      ok: true,
      text: () => new Promise<string>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true })
      }),
    } as Response))
    vi.stubGlobal('fetch', fetchMock)
    try {
      const pending = apiGet('/api/my-tasks', { timeoutMs: 5_000 })
      const timedOut = expect(pending).rejects.toMatchObject({ code: 'TIMEOUT_ERROR' })
      await vi.advanceTimersByTimeAsync(5_000)
      await timedOut
    } finally {
      vi.useRealTimers()
    }
  })
})
