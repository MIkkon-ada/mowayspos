import { useEffect, useRef, useState } from 'react'
import type { CurrentUser } from '../../types'

export const DRAFT_KEY = 'bw_voice_draft'

type VoiceDraftOwner = Pick<CurrentUser, 'person_id' | 'account_id' | 'username'> | null
export type VoiceDraftContext = { projectId: number | null; scope: 'all' | 'project' | 'task' }

function getVoiceDraftOwnerKey(user: VoiceDraftOwner): string | null {
  if (user?.person_id) return `${DRAFT_KEY}:person:${user.person_id}`
  if (user?.account_id) return `${DRAFT_KEY}:account:${user.account_id}`
  if (user?.username?.trim()) return `${DRAFT_KEY}:user:${encodeURIComponent(user.username.trim().toLowerCase())}`
  return null
}

export function getVoiceDraftStorageKey(user: VoiceDraftOwner, projectId: number | null): string | null {
  const ownerKey = getVoiceDraftOwnerKey(user)
  return ownerKey ? `${ownerKey}:project:${projectId ?? 'all'}` : null
}

export function getVoiceDraftLastContextKey(user: VoiceDraftOwner): string | null {
  const ownerKey = getVoiceDraftOwnerKey(user)
  return ownerKey ? `${ownerKey}:last-context` : null
}

export function readVoiceDraftLastContext(user: VoiceDraftOwner): VoiceDraftContext | null {
  const contextKey = getVoiceDraftLastContextKey(user)
  if (!contextKey) return null
  try {
    const rawContext = localStorage.getItem(contextKey)
    if (rawContext) {
      const parsed = JSON.parse(rawContext) as VoiceDraftContext
      if ((parsed.scope === 'all' || parsed.scope === 'project' || parsed.scope === 'task')
        && ((parsed.scope === 'all' && parsed.projectId === null)
          || ((parsed.scope === 'project' || parsed.scope === 'task') && Number.isInteger(parsed.projectId)))) return parsed
    }

    const legacyKey = getVoiceDraftOwnerKey(user)
    const legacyRaw = legacyKey ? localStorage.getItem(legacyKey) : null
    if (!legacyRaw) return null
    const legacy = JSON.parse(legacyRaw) as { projectId?: number | null; scope?: VoiceDraftContext['scope'] }
    const context: VoiceDraftContext = {
      projectId: Number.isInteger(legacy.projectId) ? legacy.projectId ?? null : null,
      scope: legacy.scope === 'project' || legacy.scope === 'task' ? legacy.scope : 'all',
    }
    if (context.projectId === null) context.scope = 'all'
    localStorage.setItem(contextKey, JSON.stringify(context))
    return context
  } catch {
    return null
  }
}

export function saveVoiceDraftLastContext(user: VoiceDraftOwner, context: VoiceDraftContext): void {
  const contextKey = getVoiceDraftLastContextKey(user)
  if (!contextKey) return
  try {
    const validContext = context.scope !== 'all' && context.projectId === null
      ? { projectId: null, scope: 'all' as const }
      : context
    localStorage.setItem(contextKey, JSON.stringify(validContext))
  } catch {
    // Ignore unavailable browser storage.
  }
}

export function readVoiceDraftStorage(user: VoiceDraftOwner, projectId: number | null): string | null {
  const storageKey = getVoiceDraftStorageKey(user, projectId)
  if (!storageKey) return null
  const scopedDraft = localStorage.getItem(storageKey)
  if (scopedDraft !== null) return scopedDraft

  // Move an older account-wide draft only when its saved project matches this view.
  const legacyKey = getVoiceDraftOwnerKey(user)
  if (!legacyKey) return null
  const legacyDraft = localStorage.getItem(legacyKey)
  if (legacyDraft === null) return null
  try {
    const parsed = JSON.parse(legacyDraft) as { projectId?: number | null; scope?: VoiceDraftContext['scope'] }
    const legacyProjectId = Number.isInteger(parsed.projectId) ? parsed.projectId ?? null : null
    if (legacyProjectId !== projectId) return null
    localStorage.setItem(storageKey, legacyDraft)
    localStorage.setItem(getVoiceDraftLastContextKey(user)!, JSON.stringify({
      projectId,
      scope: parsed.scope === 'project' || parsed.scope === 'task' ? parsed.scope : 'all',
    }))
    localStorage.removeItem(legacyKey)
    return legacyDraft
  } catch {
    return null
  }
}

type UseVoiceDraftArgs = {
  currentUser: CurrentUser | null
  projectId: number | null
  scope: 'all' | 'project' | 'task'
  text: string
  selectedProvider: string
  setText: (value: string) => void
  setSelectedProvider: (value: string) => void
}

export function useVoiceDraft({ currentUser, projectId, scope, text, selectedProvider, setText, setSelectedProvider }: UseVoiceDraftArgs) {
  const [draftSaved, setDraftSaved] = useState(false)
  const toastTimerRef = useRef<number | null>(null)
  const storageKey = scope === 'all' || projectId !== null
    ? getVoiceDraftStorageKey(currentUser, projectId)
    : null

  useEffect(() => {
    setText('')
    setSelectedProvider('capability')
    if (!storageKey) return
    try {
      const saved = readVoiceDraftStorage(currentUser, projectId)
      if (!saved) return
      const d = JSON.parse(saved) as { text?: string; provider?: string }
      if (typeof d.text === 'string') setText(d.text)
      if (d.provider && d.provider !== 'rules') setSelectedProvider(d.provider)
    } catch {
      // ignore malformed draft
    }
  }, [currentUser, projectId, setSelectedProvider, setText, storageKey])

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current)
    }
  }, [])

  function saveDraft() {
    if (!storageKey) return
    try {
      localStorage.setItem(storageKey, JSON.stringify({ text, provider: selectedProvider }))
      setDraftSaved(true)
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current)
      toastTimerRef.current = window.setTimeout(() => setDraftSaved(false), 2000)
    } catch {
      // ignore storage failures
    }
  }

  return {
    draftSaved,
    saveDraft,
  }
}
