import { useEffect, useMemo, useRef, useState } from 'react'
import { fetchSubtaskDetail, type SubTaskDetail } from '../../api/subtasks'
import { fetchVoiceContext, type UserSubtaskContext } from '../../api/updates'
import { resolveVoiceTaskPreselection } from './voiceUpdateResultTypes'

export type VoiceTaskContext = UserSubtaskContext & {
  assignee?: string
  plan_time?: string
  completion_criteria?: string
  notes?: string
}

export type VoiceDraftState = {
  text?: string
  provider?: string
  mode?: 'text' | 'voice' | 'upload'
  projectId?: number | null
  subtaskId?: number | null
}

export function readVoiceDraftState(raw: string | null): VoiceDraftState {
  if (!raw) return {}
  try {
    const parsed = JSON.parse(raw) as VoiceDraftState
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

type UseVoiceTaskBindingArgs = {
  selectedProjectId: number | null
  enabled: boolean
  requestedSubtaskId: number | null
  restoredSubtaskId: number | null
}

export function useVoiceTaskBinding({
  selectedProjectId,
  enabled,
  requestedSubtaskId,
  restoredSubtaskId,
}: UseVoiceTaskBindingArgs) {
  const [taskOptions, setTaskOptions] = useState<VoiceTaskContext[]>([])
  const [selectedSubtaskId, setSelectedSubtaskId] = useState<number | null>(null)
  const [taskLoading, setTaskLoading] = useState(false)
  const [taskError, setTaskError] = useState<string | null>(null)
  const [taskDetail, setTaskDetail] = useState<SubTaskDetail | null>(null)
  const [taskDetailLoading, setTaskDetailLoading] = useState(false)
  const [taskDetailOpen, setTaskDetailOpen] = useState(false)
  const requestIdRef = useRef(0)

  useEffect(() => {
    const requestId = ++requestIdRef.current
    setSelectedSubtaskId(null)
    setTaskDetail(null)
    setTaskDetailOpen(false)
    setTaskError(null)

    if (!selectedProjectId || !enabled) {
      setTaskOptions([])
      setTaskLoading(false)
      setTaskError(null)
      return
    }

    setTaskOptions([])
    setTaskLoading(true)
    fetchVoiceContext(selectedProjectId)
      .then((rows) => {
        if (requestId !== requestIdRef.current) return
        const scopedRows = (Array.isArray(rows) ? rows : []) as VoiceTaskContext[]
        setTaskOptions(scopedRows)
        const desiredSubtaskId = requestedSubtaskId ?? restoredSubtaskId
        setSelectedSubtaskId(resolveVoiceTaskPreselection(desiredSubtaskId, scopedRows))
      })
      .catch(() => {
        if (requestId !== requestIdRef.current) return
        setTaskOptions([])
        setTaskError('关键任务加载失败，请稍后重试。')
      })
      .finally(() => {
        if (requestId === requestIdRef.current) setTaskLoading(false)
      })
  }, [enabled, requestedSubtaskId, restoredSubtaskId, selectedProjectId])

  const selectedTaskContext = useMemo(
    () => taskOptions.find((task) => task.id === selectedSubtaskId) ?? null,
    [selectedSubtaskId, taskOptions],
  )

  function selectTask(subtaskId: number | null) {
    setSelectedSubtaskId(subtaskId)
    setTaskDetail(null)
    setTaskDetailOpen(false)
  }

  async function openTaskDetail() {
    if (!selectedSubtaskId) return
    setTaskDetail(null)
    setTaskDetailOpen(true)
    setTaskDetailLoading(true)
    try {
      const detail = await fetchSubtaskDetail(selectedSubtaskId)
      setTaskDetail(detail)
    } catch {
      setTaskError('任务详情加载失败，请稍后重试。')
    } finally {
      setTaskDetailLoading(false)
    }
  }

  return {
    taskOptions,
    selectedSubtaskId,
    selectedTaskContext,
    taskLoading,
    taskError,
    taskDetail,
    taskDetailLoading,
    taskDetailOpen,
    selectTask,
    openTaskDetail,
    closeTaskDetail: () => setTaskDetailOpen(false),
  }
}
