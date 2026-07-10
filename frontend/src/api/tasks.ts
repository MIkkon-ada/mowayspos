import { apiDelete, apiGet, apiPost, apiPut } from './client'
import type { TaskItem, WorkstreamItem } from '../types'

/**
 * TaskPayload 业务语义：重点工作创建/更新参数
 *
 * API endpoint：/api/tasks
 * 对应物理表：tasks
 * 业务含义：Workstream / 重点工作（三层结构第二层）
 */
export type TaskPayload = {
  project_id: number
  /** 重点工作名称 */
  key_task: string
  key_achievement?: string
  completion_standard?: string
  coordinator?: string
  owner?: string
  collaborators?: string
  plan_time?: string
  status?: string
  problem_note?: string
}

/** alias：TaskPayload 即 WorkstreamPayload */
export type WorkstreamPayload = TaskPayload

export function createTask(payload: TaskPayload): Promise<TaskItem> {
  return apiPost<TaskItem>('/api/tasks', payload)
}

export function updateTask(id: number, payload: TaskPayload): Promise<TaskItem> {
  return apiPut<TaskItem>(`/api/tasks/${id}`, payload)
}

export function fetchTasks(projectId: number | null, deleted = false): Promise<TaskItem[]> {
  const qs = projectId != null ? `?project_id=${projectId}` : ''
  const deletedQs = `${qs}${qs ? '&' : '?'}deleted=${deleted ? 'true' : 'false'}`
  return apiGet<TaskItem[]>(`/api/tasks${deletedQs}`)
}

export function deleteTask(id: number, reason = ''): Promise<unknown> {
  const qs = reason ? `?reason=${encodeURIComponent(reason)}` : ''
  return apiDelete(`/api/tasks/${id}${qs}`)
}

export function restoreTask(id: number): Promise<TaskItem> {
  return apiPost<TaskItem>(`/api/tasks/${id}/restore`, {})
}

// ── 语义别名（Workstream = Task）──────────────────────────────
// API endpoint 不变（/api/tasks），仅函数名做语义映射
export const createWorkstream = createTask
export const updateWorkstream = updateTask
export const fetchWorkstreams = fetchTasks
export const deleteWorkstream = deleteTask
export const restoreWorkstream = restoreTask
export type { TaskItem as WorkstreamItem } from '../types'

export type TaskLog = { action: string; operator: string; note: string; created_at: string }
export type TaskUpdate = { id: number; submitter: string; transcript_text: string; created_at: string }

export function fetchTaskLogs(id: number): Promise<TaskLog[]> {
  return apiGet<TaskLog[]>(`/api/tasks/${id}/logs`)
}

export function fetchTaskUpdates(id: number): Promise<TaskUpdate[]> {
  return apiGet<TaskUpdate[]>(`/api/tasks/${id}/updates`)
}

/** AI 大纲提取的草稿项 — 对应重点工作草稿 */
export type TaskDraft = {
  key_task: string
  owner: string
  coordinator: string
  collaborators: string
  plan_time: string
  status: string
  key_achievement: string
  completion_standard: string
}

/** alias：TaskDraft 即 WorkstreamDraft */
export type WorkstreamDraft = TaskDraft

export type ExtractOutlineResult = {
  tasks: TaskDraft[]
  project_guess: string
  suggested_project: string
  confidence: number
}

export function extractTasksFromOutline(payload: {
  project_id?: number
  text: string
  llm_provider?: string
  project_names?: string[]
}): Promise<ExtractOutlineResult> {
  return apiPost<ExtractOutlineResult>('/api/tasks/extract', payload)
}

export function batchCreateTasks(payload: {
  project_id: number
  tasks: TaskDraft[]
}): Promise<TaskItem[]> {
  return apiPost<TaskItem[]>('/api/tasks/batch', payload)
}
