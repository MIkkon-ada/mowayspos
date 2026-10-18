/* @vitest-environment jsdom */
import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { useWindowFocusVersion } from './useWindowFocusVersion'

afterEach(cleanup)

describe('useWindowFocusVersion', () => {
  it('increments when the window regains focus and removes its listener on unmount', () => {
    const { result, unmount } = renderHook(() => useWindowFocusVersion())

    act(() => window.dispatchEvent(new Event('focus')))
    expect(result.current).toBe(1)

    unmount()
    act(() => window.dispatchEvent(new Event('focus')))
    expect(result.current).toBe(1)
  })
})
