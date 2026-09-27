import { apiGet, apiPost, apiDelete } from './client'

export type SubTaskDraft = {
  id: number
  project_id: number | null
  parent_task_id: number | null
  parent_task_title?: string
  parent_task_project?: string
  title: string
  proposer: string
  assignee: string
  plan_time: string
  status: 'pending' | 'approved' | 'rejected'
  reject_reason?: string
  source_submission_id?: number | null
  created_at?: string
}

export type ProposedSubTask = {
  title: string
  assignee: string
  plan_time: string
}

export type SubTaskDraftsPayload = {
  project_id: number
  source_submission_id?: number | null
  drafts: { title: string; assignee: string; plan_time: string; parent_task_id?: number | null }[]
}

export function createDrafts(payload: SubTaskDraftsPayload): Promise<SubTaskDraft[]> {
  return apiPost<SubTaskDraft[]>('/api/subtask-drafts', payload)
}

export function listDrafts(projectId?: number | null, status = 'pending'): Promise<SubTaskDraft[]> {
  const qs = new URLSearchParams({ status: status })
  if (projectId != null) qs.set('project_id', String(projectId))
  return apiGet<SubTaskDraft[]>(`/api/subtask-drafts?${qs}`)
}

export function approveDraft(draftId: number, payload: { parent_task_id: number; assignee?: string; plan_time?: string }): Promise<{ ok: boolean; subtask_id: number }> {
  return apiPost(`/api/subtask-drafts/${draftId}/approve`, payload)
}

export function rejectDraft(draftId: number, reason?: string): Promise<{ ok: boolean }> {
  return apiPost(`/api/subtask-drafts/${draftId}/reject`, { reason: reason || '' })
}

export function deleteDraft(draftId: number): Promise<{ ok: boolean }> {
  return apiDelete(`/api/subtask-drafts/${draftId}`)
}
