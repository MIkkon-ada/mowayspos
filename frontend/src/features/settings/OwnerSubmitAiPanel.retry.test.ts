import { describe, expect, it, vi } from 'vitest'

const hookRuntime = vi.hoisted(() => {
  let state: unknown[] = []
  let refs: Array<{ current: unknown }> = []
  let hookIndex = 0

  return {
    seed(nextState: unknown[]) {
      state = nextState
      refs = []
    },
    render() {
      hookIndex = 0
    },
    stateAt(index: number) {
      return state[index]
    },
    useState: (<T,>(initial: T | (() => T)) => {
      const index = hookIndex++
      if (state[index] === undefined && index >= state.length) state[index] = typeof initial === 'function' ? (initial as () => T)() : initial
      return [state[index] as T, (next: T | ((current: T) => T)) => {
        state[index] = typeof next === 'function' ? (next as (current: T) => T)(state[index] as T) : next
      }]
    }) as typeof import('react').useState,
    useRef: (<T,>(initial: T) => {
      const index = hookIndex++
      if (!refs[index]) refs[index] = { current: initial }
      return refs[index] as { current: T }
    }) as typeof import('react').useRef,
    useMemo: (<T,>(factory: () => T) => {
      hookIndex += 1
      return factory()
    }) as typeof import('react').useMemo,
    useCallback: (<T extends (...args: never[]) => unknown>(callback: T) => {
      hookIndex += 1
      return callback
    }) as typeof import('react').useCallback,
    useEffect: (() => {
      hookIndex += 1
    }) as typeof import('react').useEffect,
  }
})

const api = vi.hoisted(() => ({
  createInitAnalysisRun: vi.fn(),
  retryInitAnalysisRun: vi.fn(),
}))

vi.mock('react', async () => {
  const actual = await vi.importActual<typeof import('react')>('react')
  return { ...actual, ...hookRuntime }
})

vi.mock('../../api/projectInitAi', async () => {
  const actual = await vi.importActual<typeof import('../../api/projectInitAi')>('../../api/projectInitAi')
  return { ...actual, createInitAnalysisRun: api.createInitAnalysisRun, retryInitAnalysisRun: api.retryInitAnalysisRun }
})

import { OwnerSubmitAiPanel } from './OwnerSubmitAiPanel'

type ElementLike = { props?: { children?: unknown; type?: string; onClick?: () => void; [key: string]: unknown } }

function textContent(node: unknown): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(textContent).join('')
  if (!node || typeof node !== 'object') return ''
  return textContent((node as ElementLike).props?.children)
}

function findButton(node: unknown, label: string): ElementLike {
  if (Array.isArray(node)) {
    for (const child of node) {
      try {
        return findButton(child, label)
      } catch {
        // Continue searching sibling nodes.
      }
    }
  }
  if (node && typeof node === 'object') {
    const element = node as ElementLike
    if (element.props?.type === 'button' && textContent(element.props.children) === label) return element
    return findButton(element.props?.children, label)
  }
  throw new Error(`button not found: ${label}`)
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((nextResolve) => { resolve = nextResolve })
  return { promise, resolve }
}

const failedRun = {
  id: 9,
  status: 'failed',
  stage: 'failed',
  progress: 100,
  error_message: '旧运行失败',
  draft: { tasks: [] },
  result_metadata: {},
} as any

const retryingRun = {
  ...failedRun,
  status: 'retrying',
  stage: 'retrying',
  progress: 10,
  error_message: '',
} as any

function renderPanel() {
  hookRuntime.render()
  return OwnerSubmitAiPanel({
    projectId: 4,
    currentDraft: [] as any,
    existingAttachments: [{ id: 1, original_name: '推进表.xlsx' }] as any,
    onApplyDraft: vi.fn(),
  })
}

describe('project-init analysis retry state', () => {
  it('suppresses duplicate retry clicks, clears the old preview, and displays neutral retry-pending state', async () => {
    const retry = deferred<typeof retryingRun>()
    api.retryInitAnalysisRun.mockReturnValueOnce(retry.promise)
    hookRuntime.seed(['failed', [], [{ id: 1, original_name: '推进表.xlsx' }], failedRun, failedRun.draft, '', false, { 'task-0': 'ignore' }, false, true])

    const initial = renderPanel()
    const retryButton = findButton(initial, '重新分析')
    retryButton.props?.onClick?.()
    retryButton.props?.onClick?.()

    expect(api.retryInitAnalysisRun).toHaveBeenCalledTimes(1)
    expect(hookRuntime.stateAt(3)).toBeUndefined()
    expect(hookRuntime.stateAt(4)).toBeUndefined()
    expect(hookRuntime.stateAt(7)).toEqual({})
    expect(hookRuntime.stateAt(9)).toBe(false)

    const pending = renderPanel()
    expect(textContent(pending)).toContain('正在重新分析已上传文件…')
    expect(textContent(pending)).not.toContain('旧运行失败')

    retry.resolve(retryingRun)
    await Promise.resolve()
    await Promise.resolve()

    const updated = renderPanel()
    expect(textContent(updated)).toContain('重试中')
  })

  it('keeps retry recovery available when retrying a failed run also fails', async () => {
    api.retryInitAnalysisRun.mockRejectedValueOnce(new Error('重试服务不可用'))
    api.createInitAnalysisRun.mockResolvedValueOnce(retryingRun)
    hookRuntime.seed(['failed', [], [{ id: 1, original_name: '推进表.xlsx' }], failedRun, failedRun.draft, '', false, {}, false, false])

    const initial = renderPanel()
    findButton(initial, '重新分析').props?.onClick?.()
    await Promise.resolve()
    await Promise.resolve()

    const failedAgain = renderPanel()
    expect(textContent(failedAgain)).toContain('重试服务不可用')
    findButton(failedAgain, '重新分析').props?.onClick?.()

    expect(api.createInitAnalysisRun).toHaveBeenCalledTimes(1)
  })
})
