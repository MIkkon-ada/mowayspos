import { useEffect, useRef, useState } from 'react'
import { extractOnly, fetchVoiceContext } from '../../api/updates'
import { fetchTasks } from '../../api/tasks'
import type { Project, SubTaskItem, TaskItem } from '../../types'
import type { KeyTaskIssue, TaskReport, UserSubtaskContext } from '../../api/updates'
import type { ProposedSubTask } from '../../api/subtaskDrafts'
import { type CardEdit, type Phase } from './voiceUpdateResultTypes'

type UseVoiceExtractionArgs = {
  currentProjectId: number | null
  selectedProjectId: number | null
  currentUser: { name?: string } | null
  text: string
  mode: 'voice' | 'upload' | 'text'
  selectedProvider: string
  projects: Project[]
  setText: (value: string) => void
}

export function useVoiceExtraction({
  selectedProjectId,
  currentUser,
  text,
  mode,
  selectedProvider,
  projects: _projects,
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
    if (!selectedProjectId) {
      submitLock.current = false
      setError('请先选择所属项目，再进行 AI 提取。')
      return
    }

    const projectId = selectedProjectId
    setPhase('extracting')
    setError(null)
    setResult(null)

    let userSubtasks: UserSubtaskContext[] = []
    // 无论是否选了项目，都拉用户可汇报的子任务上下文
    // 没选项目时后端返回所有项目的子任务（跨项目汇报）
    try {
      const contextSubs = await fetchVoiceContext(projectId)
      const mentioned = contextSubs.filter((s) => content.includes(s.title))
      const rest = contextSubs.filter((s) => !content.includes(s.title))
      userSubtasks = [...mentioned, ...rest].slice(0, 60)
      setVoiceSubtasksContext(userSubtasks)
    } catch {
      // context is optional
      setVoiceSubtasksContext([])
    }

    try {
      const res = await extractOnly({
        project_id: projectId,
        source_type: mode === 'voice' ? '语音更新' : '文字更新',
        transcript_text: content,
        submitter: currentUser?.name,
        llm_provider: selectedProvider,
        user_subtasks: userSubtasks,
      })
      const suggestion = res.suggestion ?? {}
      setResult(suggestion)
      setEditValues({ ...suggestion })
      setEditingField(null)
      const rawProposed = (suggestion.proposed_subtasks as ProposedSubTask[] | undefined) ?? []
      setProposedSubtasks(rawProposed.filter((s) => s.title?.trim()))
      const nextTaskReports = (suggestion.task_reports as TaskReport[] | undefined) ?? []
      setTaskReports(nextTaskReports)
      const initEdits: Record<number, CardEdit> = {}
      nextTaskReports.forEach((r, idx) => {
        if (r.type === 'progress' && r.matched_subtask_id) {
          const sub = userSubtasks.find((s) => s.id === r.matched_subtask_id)
          initEdits[idx] = {
            taskId: sub?.parent_task_id ?? null,
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
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'AI提取失败，请重试')
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
