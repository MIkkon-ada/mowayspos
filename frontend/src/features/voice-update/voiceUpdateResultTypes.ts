import type { Dispatch, SetStateAction } from 'react'

import type { KeyTaskIssue, TaskReport, UserSubtaskContext } from '../../api/updates'
import type { ProposedSubTask } from '../../api/subtaskDrafts'
import type { SubTaskItem, TaskItem } from '../../types'

export type Phase = 'input' | 'extracting' | 'extracted' | 'submitting' | 'submitted'
export type VoiceReportScope = 'all' | 'project' | 'task'
export type CardEdit = { taskId: number | null; subtaskId: number | null; subtasks: SubTaskItem[]; editorOpen: boolean; modified: boolean }

export function getVoiceFlowStep(
  phase: Phase,
  hasContent: boolean,
): 1 | 2 | 3 | 4 | 5 {
  if (phase === 'extracting') return 3
  if (phase === 'extracted') return 4
  if (phase === 'submitting' || phase === 'submitted') return 5
  return hasContent ? 2 : 1
}

export function resolveVoiceTaskPreselection(
  requestedSubtaskId: number | null,
  taskOptions: UserSubtaskContext[],
): number | null {
  if (!requestedSubtaskId) return null
  return taskOptions.some((task) => task.id === requestedSubtaskId) ? requestedSubtaskId : null
}

export function buildSelectedVoiceContext(
  selectedTaskContext: UserSubtaskContext | null,
): UserSubtaskContext[] {
  return selectedTaskContext ? [selectedTaskContext] : []
}

export function bindProgressReportsToTask(
  reports: TaskReport[],
  selectedTaskContext: UserSubtaskContext,
): TaskReport[] {
  return reports.map((report) => report.type === 'progress'
    ? {
        ...report,
        matched_subtask_id: selectedTaskContext.id,
        matched_subtask_title: selectedTaskContext.title,
        parent_task_id: selectedTaskContext.parent_task_id ?? null,
        parent_key_task: selectedTaskContext.parent_key_task,
      }
    : report)
}

export function canExtractVoiceUpdate({
  scope,
  candidateCount,
  projectId,
  selectedTaskContext,
  text,
  projectActive,
  recording,
  transcribing,
  uploading,
  phase,
}: {
  scope?: VoiceReportScope
  candidateCount?: number
  projectId: number | null
  selectedTaskContext: UserSubtaskContext | null
  text: string
  projectActive: boolean
  recording: boolean
  transcribing: boolean
  uploading: boolean
  phase: Phase
}): boolean {
  return Boolean(
    ((scope === 'all' && Number(candidateCount) > 0)
      || (scope === 'project' && projectId && Number(candidateCount) > 0)
      || ((!scope || scope === 'task') && projectId && selectedTaskContext))
    && text.trim()
    && projectActive
    && !recording
    && !transcribing
    && !uploading
    && phase !== 'extracting'
    && phase !== 'submitting',
  )
}

export function hasUnconfirmedOwnership(reports: TaskReport[]): boolean {
  return reports.some((report) => report.type === 'progress'
    && Boolean(report.match_status)
    && (report.match_status !== 'matched' || !report.matched_subtask_id))
}

export function canSubmitVoiceUpdate(selectedSubtaskId: number | null, phase: Phase): boolean {
  return Boolean(selectedSubtaskId && phase === 'extracted')
}

export type VoiceUpdateResultCardProps = {
  result: Record<string, unknown> | null
  error: string | null
  phase: Phase
  editValues: Record<string, unknown> | null
  editingField: string | null
  setEditingField: Dispatch<SetStateAction<string | null>>
  setEditValues: Dispatch<SetStateAction<Record<string, unknown> | null>>
  taskReports: TaskReport[]
  setTaskReports: Dispatch<SetStateAction<TaskReport[]>>
  keyTaskIssues: KeyTaskIssue[]
  setKeyTaskIssues: Dispatch<SetStateAction<KeyTaskIssue[]>>
  selectedSubtaskId: number | null
  proposedSubtasks: ProposedSubTask[]
  setProposedSubtasks: Dispatch<SetStateAction<ProposedSubTask[]>>
  cardEdits: Record<number, CardEdit>
  updateCardEdit: (idx: number, patch: Partial<CardEdit>) => void
  projectTasksForSuggest: TaskItem[]
  voiceSubtasksContext: UserSubtaskContext[]
  currentUserName?: string
  onExtract: () => void
  hasSelectedTask: boolean
  hasText: boolean
}

export type VoiceUpdateTaskReportsSectionProps = Pick<
  VoiceUpdateResultCardProps,
  'phase' | 'taskReports' | 'setTaskReports' | 'keyTaskIssues' | 'setKeyTaskIssues' | 'selectedSubtaskId' | 'cardEdits' | 'updateCardEdit' | 'projectTasksForSuggest' | 'voiceSubtasksContext'
>

export type VoiceUpdateEditableFieldsSectionProps = Pick<
  VoiceUpdateResultCardProps,
  'phase' | 'editValues' | 'editingField' | 'setEditingField' | 'setEditValues' | 'proposedSubtasks' | 'setProposedSubtasks' | 'currentUserName' | 'taskReports'
>

export type VoiceUpdateSubmitPanelProps = {
  phase: Phase
  reportScope: VoiceReportScope
  taskReports: TaskReport[]
  cardEdits: Record<number, CardEdit>
  currentUserName?: string
  selectedProjectName?: string | null
  isProjectSelected: boolean
  selectedSubtaskId: number | null
  text: string
  submittedAt: string
  draftSaved: boolean
  onSaveDraft: () => void
  onResetExtractionState: (options?: { clearText?: boolean }) => void
  onClear: () => void
  onSubmitFinal: () => void
  onViewSubmissionHistory: () => void
  projectArchived?: boolean
  projectSubmitBlockedReason?: string | null
}
