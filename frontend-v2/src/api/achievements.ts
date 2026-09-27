import { ApiError, apiDelete, apiGet, apiPatch, apiPost, apiPut } from './client'
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
  attachment_ids?: number[]
}

export type AchievementAttachment = {
  id: number
  project_id: number
  achievement_id?: number | null
  achievement_submission_id?: number | null
  original_name: string
  mime_type: string
  size_bytes: number
  uploaded_by: string
  created_at: string
}

export function fetchAchievementAttachments(achievementId: number): Promise<AchievementAttachment[]> {
  return apiGet<AchievementAttachment[]>(`/api/achievement-attachments?achievement_id=${achievementId}`)
}

export function downloadAchievementAttachment(id: number): string {
  return `/api/achievement-attachments/${id}/download`
}

export function deleteAchievementAttachment(id: number): Promise<unknown> {
  return apiDelete(`/api/achievement-attachments/${id}`)
}

export function uploadAchievementAttachment(
  file: File,
  target: { projectId: number; achievementId?: number; achievementSubmissionId?: number },
  onProgress?: (percent: number) => void,
  signal?: AbortSignal,
): Promise<AchievementAttachment> {
  const form = new FormData()
  form.append('project_id', String(target.projectId))
  form.append('file', file)
  if (target.achievementId != null) form.append('achievement_id', String(target.achievementId))
  if (target.achievementSubmissionId != null) form.append('achievement_submission_id', String(target.achievementSubmissionId))
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/achievement-attachments')
    xhr.withCredentials = true
    const abort = () => xhr.abort()
    signal?.addEventListener('abort', abort, { once: true })
    xhr.onloadend = () => signal?.removeEventListener('abort', abort)
    xhr.upload.onprogress = (event) => { if (event.lengthComputable) onProgress?.(Math.round(event.loaded / event.total * 100)) }
    xhr.onerror = () => reject(new Error('上传失败，请检查网络后重试'))
    xhr.onabort = () => reject(new DOMException('上传已取消', 'AbortError'))
    xhr.onload = () => {
      let body: unknown = null
      try { body = xhr.responseText ? JSON.parse(xhr.responseText) : null } catch { body = xhr.responseText }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as AchievementAttachment)
      else reject(new ApiError(xhr.status, (body as { detail?: string } | null)?.detail || '上传失败', body))
    }
    xhr.send(form)
  })
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
