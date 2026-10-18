// @vitest-environment jsdom
import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { CurrentUser } from '../../types'
import { DRAFT_KEY, getVoiceDraftStorageKey, readVoiceDraftLastContext, readVoiceDraftStorage, useVoiceDraft } from './useVoiceDraft'

afterEach(() => vi.unstubAllGlobals())

describe('voice draft storage identity', () => {
  it('isolates saved drafts by stable person or account identity', () => {
    expect(getVoiceDraftStorageKey({ person_id: 12, account_id: 3, username: 'alice' }, 7))
      .not.toBe(getVoiceDraftStorageKey({ person_id: 28, account_id: 4, username: 'alice' }, 7))
    expect(getVoiceDraftStorageKey({ account_id: 3, username: 'alice' }, 7))
      .not.toBe(getVoiceDraftStorageKey({ account_id: 4, username: 'alice' }, 7))
  })

  it('isolates a user’s report drafts by project and the all-work scope', () => {
    const user = { account_id: 3, username: 'alice' }
    expect(getVoiceDraftStorageKey(user, 7)).not.toBe(getVoiceDraftStorageKey(user, 8))
    expect(getVoiceDraftStorageKey(user, null)).not.toBe(getVoiceDraftStorageKey(user, 7))
  })

  it('does not fall back to a shared key when identity is unavailable', () => {
    expect(getVoiceDraftStorageKey(null, null)).toBeNull()
    expect(getVoiceDraftStorageKey({ username: '' }, 7)).toBeNull()
  })

  it('migrates a legacy user draft only into its matching project scope', () => {
    const values = new Map<string, string>()
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    })
    const user = { person_id: 12, account_id: 3, username: 'alice' }
    const oldKey = `${DRAFT_KEY}:person:12`
    values.set(oldKey, JSON.stringify({ text: '项目 7 的草稿', projectId: 7, scope: 'project' }))

    expect(readVoiceDraftStorage(user, 8)).toBeNull()
    expect(values.has(oldKey)).toBe(true)
    expect(readVoiceDraftStorage(user, 7)).toContain('项目 7 的草稿')
    expect(values.has(oldKey)).toBe(false)
    expect(values.get(getVoiceDraftStorageKey(user, 7)!)).toContain('项目 7 的草稿')
    expect(readVoiceDraftLastContext(user)).toEqual({ projectId: 7, scope: 'project' })
  })

  it('loads the selected project draft and clears text when switching to a project without one', async () => {
    const values = new Map<string, string>()
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    })
    const user: CurrentUser = {
      person_id: 12,
      account_id: 3,
      username: 'alice',
      name: 'Alice',
      system_role: 'normal_member',
      is_tech_admin: false,
      is_ceo: false,
      is_coordinator: false,
      can_view_all: false,
      can_confirm_all: false,
      visible_projects: [],
      project_roles: {},
    }
    values.set(getVoiceDraftStorageKey(user, 7)!, JSON.stringify({ text: '项目 7 汇报', provider: 'capability' }))
    const setText = vi.fn()
    const setSelectedProvider = vi.fn()
    const { rerender } = renderHook(({ projectId }: { projectId: number }) => useVoiceDraft({
      currentUser: user,
      projectId,
      scope: 'project',
      text: '',
      selectedProvider: 'capability',
      setText,
      setSelectedProvider,
    }), { initialProps: { projectId: 7 } })

    await waitFor(() => expect(setText).toHaveBeenCalledWith('项目 7 汇报'))
    setText.mockClear()
    rerender({ projectId: 8 })
    await waitFor(() => expect(setText).toHaveBeenCalledWith(''))
  })
})
