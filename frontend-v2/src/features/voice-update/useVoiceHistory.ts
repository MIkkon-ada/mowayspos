import { useEffect, useState } from 'react'
import { fetchMyUpdates, getUpdate } from '../../api/updates'
import type { UpdateDetail, UpdateHistoryItem } from '../../api/updates'

type UseVoiceHistoryArgs = {
  activeProjectId: number | null
}

export function useVoiceHistory({ activeProjectId }: UseVoiceHistoryArgs) {
  const [history, setHistory] = useState<UpdateHistoryItem[]>([])
  const [detailItem, setDetailItem] = useState<UpdateDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [showTranscript, setShowTranscript] = useState(false)

  async function refreshHistory(_projectId: number | null = activeProjectId) {
    try {
      const rows = await fetchMyUpdates()
      setHistory(rows)
    } catch {
      setHistory([])
    }
  }

  useEffect(() => {
    void refreshHistory(activeProjectId)
  }, [activeProjectId])

  async function handleSelectUpdate(id: number) {
    setShowTranscript(false)
    setDetailItem(null)
    setDetailLoading(true)
    try {
      const detail = await getUpdate(id)
      setDetailItem(detail)
    } catch {
      // keep current drawer closed on failure
    } finally {
      setDetailLoading(false)
    }
  }

  return {
    history,
    detailItem,
    detailLoading,
    showTranscript,
    setShowTranscript,
    setDetailItem,
    setDetailLoading,
    refreshHistory,
    handleSelectUpdate,
  }
}
