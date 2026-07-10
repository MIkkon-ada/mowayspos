import type { Dispatch, SetStateAction } from 'react'

import type { KeyTaskIssue, TaskReport, UserSubtaskContext } from '../../api/updates'
import type { ProposedSubTask } from '../../api/subtaskDrafts'
import type { SubTaskItem, TaskItem } from '../../types'

export type Phase = 'input' | 'extracting' | 'extracted' | 'submitting' | 'submitted'
export type CardEdit = { taskId: number | null; subtaskId: number | null; subtasks: SubTaskItem[]; editorOpen: boolean; modified: boolean }

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
  proposedSubtasks: ProposedSubTask[]
  setProposedSubtasks: Dispatch<SetStateAction<ProposedSubTask[]>>
  cardEdits: Record<number, CardEdit>
  updateCardEdit: (idx: number, patch: Partial<CardEdit>) => void
  projectTasksForSuggest: TaskItem[]
  voiceSubtasksContext: UserSubtaskContext[]
  currentUserName?: string
}

export type VoiceUpdateTaskReportsSectionProps = Pick<
  VoiceUpdateResultCardProps,
  'phase' | 'taskReports' | 'setTaskReports' | 'keyTaskIssues' | 'cardEdits' | 'updateCardEdit' | 'projectTasksForSuggest' | 'voiceSubtasksContext'
>

export type VoiceUpdateEditableFieldsSectionProps = Pick<
  VoiceUpdateResultCardProps,
  'phase' | 'editValues' | 'editingField' | 'setEditingField' | 'setEditValues' | 'proposedSubtasks' | 'setProposedSubtasks' | 'currentUserName' | 'taskReports'
>

export type VoiceUpdateSubmitPanelProps = {
  phase: Phase
  taskReports: TaskReport[]
  cardEdits: Record<number, CardEdit>
  currentUserName?: string
  selectedProjectName?: string | null
  isProjectSelected: boolean
  text: string
  submittedAt: string
  draftSaved: boolean
  onSaveDraft: () => void
  onExtract: () => void
  onResetExtractionState: (options?: { clearText?: boolean }) => void
  onSubmitFinal: () => void
  projectArchived?: boolean
}
