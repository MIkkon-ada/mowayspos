import { useEffect, useRef, useState } from 'react'
import { extractOnly } from '../../api/updates'
import { fetchTasks } from '../../api/tasks'
import type { SubTaskItem, TaskItem } from '../../types'
import type { KeyTaskIssue, TaskReport, UserSubtaskContext } from '../../api/updates'
import type { ProposedSubTask } from '../../api/subtaskDrafts'
import { bindProgressReportsToTask, type CardEdit, type Phase, type VoiceReportScope } from './voiceUpdateResultTypes'

type UseVoiceExtractionArgs = {
  reportScope: VoiceReportScope
  selectedProjectId: number | null
  selectedTaskContext: UserSubtaskContext | null
  voiceCandidates: UserSubtaskContext[]
  selectedProjectIsActive: boolean
  currentUser: { name?: string } | null
  text: string
  mode: 'voice' | 'upload' | 'text'
  selectedProvider: string
  setText: (value: string) => void
}

export function useVoiceExtraction({
  reportScope,
  selectedProjectId,
  selectedTaskContext,
  voiceCandidates,
  selectedProjectIsActive,
  currentUser,
  text,
  mode,
  selectedProvider,
  setText,
}: UseVoiceExtractionArgs) {
  const [phase, setPhase] = useState<Phase>('input')
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editValues, setEditValues] = useState<Record<string, unknown> | null>(null)
  const [editingField, setEditingField] = useState<string | null>(null)
  const [proposedSubtasks, setProposedSubtasks] = useState<ProposedSubTask[]>([])
  const [taskReports, setTaskReports] = useState<TaskReport[]>([])
  const [keyTaskIssues, setKeyTaskIssues] = useState<KeyTaskIssue[]>([])
  const [projectTasksForSuggest, setProjectTasksForSuggest] = useState<TaskItem[]>([])
  const [voiceSubtasksContext, setVoiceSubtasksContext] = useState<UserSubtaskContext[]>([])
  const [cardEdits, setCardEdits] = useState<Record<number, CardEdit>>({})
  const submitLock = useRef(false)

  useEffect(() => {
    if (!selectedProjectId) {
      // 没选项目时，从用户子任务上下文中提取父任务 ID，加载对应任务
      // 用于 suggest_new_subtask 归属选择
      if (voiceSubtasksContext.length > 0) {
        const taskIds = [...new Set(voiceSubtasksContext.map((s) => s.parent_task_id).filter(Boolean))] as number[]
        Promise.all(taskIds.slice(0, 20).map((tid) => fetchTasks(null).catch(() => [] as TaskItem[])))
          .then(() => {
            // 从 voiceSubtasksContext 构建 task 列表
            const taskMap = new Map<number, TaskItem>()
            voiceSubtasksContext.forEach((s) => {
              if (s.parent_task_id && !taskMap.has(s.parent_task_id)) {
                taskMap.set(s.parent_task_id, {
                  id: s.parent_task_id,
                  key_task: s.parent_key_task,
                  project_id: s.parent_project_id ?? null,
                } as TaskItem)
              }
            })
            setProjectTasksForSuggest(Array.from(taskMap.values()))
          })
          .catch(() => setProjectTasksForSuggest([]))
      } else {
        setProjectTasksForSuggest([])
      }
      return
    }
    fetchTasks(selectedProjectId)
      .then((rows) => setProjectTasksForSuggest(Array.isArray(rows) ? rows : []))
      .catch(() => setProjectTasksForSuggest([]))
  }, [selectedProjectId, voiceSubtasksContext])

  function updateCardEdit(idx: number, patch: Partial<CardEdit>) {
    setCardEdits((prev) => {
      const cur = prev[idx] ?? { taskId: null, subtaskId: null, subtasks: [], editorOpen: false, modified: false }
      return { ...prev, [idx]: { ...cur, ...patch } }
    })
  }

  function resetExtractionState(options: { clearText?: boolean } = {}) {
    setPhase('input')
    if (options.clearText) setText('')
    setResult(null)
    setError(null)
    setEditValues(null)
    setEditingField(null)
    setProposedSubtasks([])
    setTaskReports([])
    setKeyTaskIssues([])
    setVoiceSubtasksContext([])
    setCardEdits({})
  }

  async function handleExtract() {
    if (submitLock.current) return
    submitLock.current = true
    const content = text.trim()
    if (!content) {
      submitLock.current = false
      setError('请先输入或录制内容')
      return
    }
    if (!selectedProjectIsActive) {
      submitLock.current = false
      setError('项目尚未进入执行阶段，暂不能进行 AI 提取。')
      return
    }

    if (voiceCandidates.length === 0) {
      submitLock.current = false
      setError('当前范围内暂无可汇报工作，请调整汇报范围。')
      return
    }

    const projectId = reportScope === 'all' ? undefined : selectedProjectId ?? undefined
    setPhase('extracting')
    setError(null)
    setResult(null)

    setVoiceSubtasksContext(voiceCandidates)

    try {
      const res = await extractOnly({
        ...(projectId ? { project_id: projectId } : {}),
        report_scope: reportScope,
        source_type: mode === 'voice' ? '语音更新' : '文字更新',
        transcript_text: content,
        submitter: currentUser?.name,
        llm_provider: selectedProvider,
        user_subtasks: voiceCandidates,
      })
      const suggestion = res.suggestion ?? {}
      setResult(suggestion)
      setEditValues({ ...suggestion })
      setEditingField(null)
      const rawProposed = (suggestion.proposed_subtasks as ProposedSubTask[] | undefined) ?? []
      setProposedSubtasks(rawProposed.filter((s) => s.title?.trim()))
      const extractedReports = (suggestion.task_reports as TaskReport[] | undefined) ?? []
      const nextTaskReports = reportScope === 'task' && selectedTaskContext
        ? bindProgressReportsToTask(extractedReports, selectedTaskContext)
        : extractedReports
      setTaskReports(nextTaskReports)
      const initEdits: Record<number, CardEdit> = {}
      nextTaskReports.forEach((r, idx) => {
        if (r.type === 'progress' && r.matched_subtask_id) {
          const matchedContext = voiceCandidates.find((item) => item.id === r.matched_subtask_id)
          initEdits[idx] = {
            taskId: matchedContext?.parent_task_id ?? r.parent_task_id ?? null,
            subtaskId: r.matched_subtask_id,
            subtasks: [],
            editorOpen: false,
            modified: false,
          }
        }
      })
      setCardEdits(initEdits)
      setKeyTaskIssues((suggestion.key_task_issues as KeyTaskIssue[] | undefined) ?? [])
      setPhase('extracted')
    } catch {
      setError('AI 提取失败，请重新尝试。')
      setPhase('input')
    } finally {
      submitLock.current = false
    }
  }

  return {
    phase,
    setPhase,
    result,
    error,
    setError,
    editValues,
    setEditValues,
    editingField,
    setEditingField,
    proposedSubtasks,
    setProposedSubtasks,
    taskReports,
    setTaskReports,
    keyTaskIssues,
    setKeyTaskIssues,
    cardEdits,
    setCardEdits,
    updateCardEdit,
    projectTasksForSuggest,
    voiceSubtasksContext,
    setVoiceSubtasksContext,
    resetExtractionState,
    handleExtract,
  }
}
