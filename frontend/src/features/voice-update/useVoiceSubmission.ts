import { useRef, useState } from 'react'
import { createUpdate, createUpdateBatch } from '../../api/updates'
import { createDrafts } from '../../api/subtaskDrafts'
import type { Project } from '../../types'
import type { KeyTaskIssue, TaskReport, UserSubtaskContext } from '../../api/updates'
import type { ProposedSubTask } from '../../api/subtaskDrafts'
import { bindProgressReportsToTask, type CardEdit, type Phase, type VoiceReportScope } from './voiceUpdateResultTypes'
import { buildVoiceUpdateHumanResult } from '../../domain/voiceUpdateFlow'
import { DRAFT_KEY } from './useVoiceDraft'

type UseVoiceSubmissionArgs = {
  reportScope: VoiceReportScope
  selectedProjectId: number | null
  selectedSubtaskId: number | null
  selectedTaskContext: UserSubtaskContext | null
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
  reportScope,
  selectedProjectId,
  selectedSubtaskId,
  selectedTaskContext,
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
  const batchRequestId = useRef<string | null>(null)

  async function handleSubmitFinal() {
    if (submitLock.current) return
    submitLock.current = true
    const projectId = selectedProjectId
    if (reportScope === 'task' && !projectId) {
      submitLock.current = false
      setError('请先选择所属项目，再提交至 AI 确认中心。')
      return
    }
    if (reportScope === 'task' && (!selectedSubtaskId || !selectedTaskContext)) {
      submitLock.current = false
      setError('请先选择本次汇报对应的关键任务。')
      return
    }
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

    const defaultBoundTaskReports = reportScope === 'task' && selectedTaskContext
      ? bindProgressReportsToTask(taskReports, selectedTaskContext)
      : taskReports
    const patchedTaskReports = defaultBoundTaskReports.map((r, i) => {
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

    if (reportScope !== 'task' && patchedTaskReports.some((report) => (
      report.type !== 'progress' || !report.parent_task_id || !report.matched_subtask_id
    ))) {
      setError('请先确认所有任务卡的项目、重点工作和关键任务归属')
      submitLock.current = false
      return
    }

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
      const sourceType = mode === 'voice' ? '语音更新' : '文字更新'
      let submissionId: number | null = null
      if (reportScope === 'task') {
        const { submission } = await createUpdate({
          project_id: projectId,
          source_type: sourceType,
          transcript_text: content,
          submitter: submitterName,
          human_result: mergedHumanResult,
        })
        submissionId = submission?.id ?? null
      } else {
        batchRequestId.current ||= globalThis.crypto?.randomUUID?.()
          ?? `report-${Date.now()}-${Math.random().toString(36).slice(2)}`
        const batchResult = await createUpdateBatch({
          client_request_id: batchRequestId.current,
          source_type: sourceType,
          title: '工作汇报',
          transcript_text: content,
          human_result: mergedHumanResult,
        })
        submissionId = batchResult.submissions[0]?.id ?? null
        batchRequestId.current = null
      }

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
          source_submission_id: submissionId,
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
