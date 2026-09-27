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
})
