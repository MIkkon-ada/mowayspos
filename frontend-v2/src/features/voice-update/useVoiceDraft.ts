import { useEffect, useRef, useState } from 'react'

export const DRAFT_KEY = 'bw_voice_draft'

type UseVoiceDraftArgs = {
  text: string
  selectedProvider: string
  setText: (value: string) => void
  setSelectedProvider: (value: string) => void
}

export function useVoiceDraft({ text, selectedProvider, setText, setSelectedProvider }: UseVoiceDraftArgs) {
  const [draftSaved, setDraftSaved] = useState(false)
  const toastTimerRef = useRef<number | null>(null)

  useEffect(() => {
    try {
      const saved = localStorage.getItem(DRAFT_KEY)
      if (!saved) return
      const d = JSON.parse(saved) as { text?: string; provider?: string }
      if (d.text) setText(d.text)
      if (d.provider && d.provider !== 'rules') setSelectedProvider(d.provider)
    } catch {
      // ignore malformed draft
    }
  }, [setSelectedProvider, setText])

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current)
    }
  }, [])

  function saveDraft() {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify({ text, provider: selectedProvider }))
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
