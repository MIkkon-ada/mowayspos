import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from './client'
import type { AchievementItem, AchievementSubmissionItem } from '../types'

export function fetchAchievements(projectId?: number | null): Promise<AchievementItem[]> {
  const qs = projectId != null ? `?project_id=${projectId}` : ''
  return apiGet<AchievementItem[]>(`/api/achievements${qs}`)
}

export function deleteAchievement(id: number): Promise<unknown> {
  return apiDelete(`/api/achievements/${id}`)
}

export type AchievementPayload = {
  project_id: number
  name: string
  achievement_type?: string
  related_task_id?: number | null
  related_subtask_id?: number | null
  owner?: string
  version?: string
  file_link?: string
  scenario?: string
  reuse_tag?: string
  status?: string
  source_type?: string
}

export function createAchievement(payload: AchievementPayload): Promise<AchievementItem> {
  return apiPost<AchievementItem>('/api/achievements', payload)
}

export function updateAchievement(id: number, payload: AchievementPayload): Promise<AchievementItem> {
  return apiPut<AchievementItem>(`/api/achievements/${id}`, payload)
}

// ── Achievement Submissions ───────────────────────────────────

export type AchievementSubmissionPayload = {
  project_id: number
  related_task_id: number
  name: string
  achievement_type?: string
  version?: string
  file_link?: string
  scenario?: string
  reuse_tag?: string
}

export function createAchievementSubmission(
  payload: AchievementSubmissionPayload,
): Promise<AchievementSubmissionItem> {
  return apiPost<AchievementSubmissionItem>('/api/achievement-submissions', payload)
}

export function fetchAchievementSubmissions(params?: {
  project_id?: number | null
  status?: string
}): Promise<AchievementSubmissionItem[]> {
  const qp = new URLSearchParams()
  if (params?.project_id != null) qp.set('project_id', String(params.project_id))
  if (params?.status) qp.set('status', params.status)
  const qs = qp.toString() ? `?${qp.toString()}` : ''
  return apiGet<AchievementSubmissionItem[]>(`/api/achievement-submissions${qs}`)
}

export function confirmAchievementSubmission(
  id: number,
): Promise<{ submission: AchievementSubmissionItem; achievement: AchievementItem }> {
  return apiPatch<{ submission: AchievementSubmissionItem; achievement: AchievementItem }>(
    `/api/achievement-submissions/${id}/confirm`,
    {},
  )
}

export function rejectAchievementSubmission(
  id: number,
  reject_reason: string,
): Promise<AchievementSubmissionItem> {
  return apiPatch<AchievementSubmissionItem>(`/api/achievement-submissions/${id}/reject`, {
    reject_reason,
  })
}

export function withdrawAchievementSubmission(id: number): Promise<AchievementSubmissionItem> {
  return apiPatch<AchievementSubmissionItem>(`/api/achievement-submissions/${id}/withdraw`, {})
}
