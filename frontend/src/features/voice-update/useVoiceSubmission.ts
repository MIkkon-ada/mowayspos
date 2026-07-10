import { useRef, useState } from 'react'
import { createUpdate } from '../../api/updates'
import { createDrafts } from '../../api/subtaskDrafts'
import type { Project } from '../../types'
import type { KeyTaskIssue, TaskReport } from '../../api/updates'
import type { ProposedSubTask } from '../../api/subtaskDrafts'
import type { CardEdit, Phase } from './voiceUpdateResultTypes'
import { buildVoiceUpdateHumanResult } from '../../domain/voiceUpdateFlow'
import { DRAFT_KEY } from './useVoiceDraft'

type UseVoiceSubmissionArgs = {
  currentProjectId: number | null
  selectedProjectId: number | null
  currentUser: { name?: string } | null
  text: string
  mode: 'voice' | 'upload' | 'text'
  result: Record<string, unknown> | null
  editValues: Record<string, unknown> | null
  taskReports: TaskReport[]
  keyTaskIssues: KeyTaskIssue[]
  cardEdits: Record<number, CardEdit>
  proposedSubtasks: ProposedSubTask[]
  projectTasksForSuggest: { id: number; key_task: string }[]
  projects: Project[]
  setPhase: (phase: Phase) => void
  setError: (value: string | null) => void
  refreshHistory: (projectId?: number | null) => Promise<void>
}

export function useVoiceSubmission({
  selectedProjectId,
  currentUser,
  text,
  mode,
  result,
  editValues,
  taskReports,
  keyTaskIssues,
  cardEdits,
  proposedSubtasks,
  projectTasksForSuggest,
  projects,
  setPhase,
  setError,
  refreshHistory,
}: UseVoiceSubmissionArgs) {
  const [submittedAt, setSubmittedAt] = useState('')
  const submitLock = useRef(false)

  async function handleSubmitFinal() {
    if (submitLock.current) return
    submitLock.current = true
    const projectId = selectedProjectId  // 可为 null，后端从 AI 结果反查
    if (!currentUser) {
      submitLock.current = false
      setError('无法获取当前用户信息')
      return
    }

    const hasIncompleteOwnership = taskReports.some((r, i) => {
      const e = cardEdits[i]
      return r.type === 'progress' && e?.modified && e.taskId && !e.subtaskId
    })
    if (hasIncompleteOwnership) {
      setError('归属不完整：已修改的任务卡请完整选择重点工作和关键任务')
      submitLock.current = false
      return
    }

    const missingSuggest = taskReports.some((r, i) => {
      if ((r as Record<string, unknown>).type !== 'suggest_new_subtask') return false
      const hasParent = !!(r as Record<string, unknown>).parent_task_id
      return !hasParent && !(cardEdits[i]?.modified && cardEdits[i].taskId)
    })
    if (missingSuggest) {
      setError('请先为建议新增关键任务选择归属重点工作')
      submitLock.current = false
      return
    }

    const patchedTaskReports = taskReports.map((r, i) => {
      const e = cardEdits[i]
      if (!e?.modified) return r
      if (r.type === 'progress') {
        const selectedSub = e.subtaskId ? e.subtasks.find((s) => s.id === e.subtaskId) : null
        const selectedTask = e.taskId ? projectTasksForSuggest.find((t) => t.id === e.taskId) : null
        if (selectedSub) {
          return {
            ...r,
            matched_subtask_id: selectedSub.id,
            matched_subtask_title: selectedSub.title,
            parent_task_id: selectedTask?.id ?? null,
            parent_key_task: selectedTask?.key_task ?? '',
          }
        }
        return r
      }
      if ((r as Record<string, unknown>).type === 'suggest_new_subtask') {
        const selectedTask = e.taskId ? projectTasksForSuggest.find((t) => t.id === e.taskId) : null
        return {
          ...r,
          parent_task_id: selectedTask?.id ?? (r as Record<string, unknown>).parent_task_id ?? null,
          parent_key_task: selectedTask?.key_task ?? (r as Record<string, unknown>).parent_key_task ?? '',
        }
      }
      return r
    })

    const selectedProject = projectId ? projects.find((p) => p.id === projectId) : null
    const content = text.trim()
    const submitterName = currentUser.name ?? ''
    setPhase('submitting')
    setError(null)
    try {
      const mergedHumanResult = buildVoiceUpdateHumanResult({
        result,
        editValues,
        selectedProjectId: projectId,
        selectedProjectName: selectedProject?.name ?? '',
        taskReports: patchedTaskReports,
        keyTaskIssues,
      })
      const { submission } = await createUpdate({
        ...(projectId ? { project_id: projectId } : {}),
        source_type: mode === 'voice' ? '语音更新' : '文字更新',
        transcript_text: content,
        submitter: submitterName,
        human_result: mergedHumanResult,
      })

      const newTaskReports = taskReports.filter((r) => r.type === 'new_task') as Extract<TaskReport, { type: 'new_task' }>[]
      const draftItems = [
        ...newTaskReports.map((r) => ({
          title: r.title,
          assignee: r.assignee || submitterName,
          plan_time: r.plan_start && r.plan_end ? `${r.plan_start}~${r.plan_end}` : r.plan_start || '',
          parent_task_id: null as number | null,
        })),
        ...proposedSubtasks.map((s) => ({
          title: s.title,
          assignee: s.assignee || submitterName,
          plan_time: s.plan_time || '',
          parent_task_id: null as number | null,
        })),
      ].filter((d) => d.title.trim())

      if (draftItems.length > 0 && projectId) {
        createDrafts({
          project_id: projectId,
          source_submission_id: submission?.id ?? null,
          drafts: draftItems,
        }).catch(() => {})
      }

      setPhase('submitted')
      setSubmittedAt(
        new Date()
          .toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
          .replace(/\//g, '-'),
      )
      localStorage.removeItem(DRAFT_KEY)
      await refreshHistory(projectId ?? undefined)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '提交失败，请重试')
      setPhase('extracted')
    } finally {
      submitLock.current = false
    }
  }

  return {
    submittedAt,
    handleSubmitFinal,
  }
}
