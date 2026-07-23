import { apiGet, apiPost, apiPatch, apiDelete } from './client'
import type { SubTaskItem, KeyTaskItem } from '../types'

/**
 * SubTaskPayload 业务语义：关键任务创建/更新参数
 *
 * API endpoint：/api/tasks/{id}/subtasks 及 /api/subtasks/{id}
 * 对应物理表：subtasks
 * 业务含义：KeyTask / 关键任务（三层结构第三层）
 */
export type SubTaskPayload = {
  project_id: number
  title: string
  assignee: string
  plan_time: string
  status: string
  completion_criteria: string
  notes: string
}

/** alias：SubTaskPayload 即 KeyTaskPayload */
export type KeyTaskPayload = SubTaskPayload

export type SubTaskWithParent = SubTaskItem & {
  /** 上级重点工作(Workstream)名称 */
  parent_key_task: string
  parent_task_id: number
  parent_project_id: number | null
  // Historical display-only fallback; business ownership still comes from parent_project_id.
  parent_special_project: string
}

export function fetchSubTasks(taskId: number, deleted = false): Promise<SubTaskItem[]> {
  return apiGet<SubTaskItem[]>(`/api/tasks/${taskId}/subtasks?deleted=${deleted ? 'true' : 'false'}`)
}

/**
 * 批量获取多个 task 的 subtask，一次请求替代多次 fetchSubTasks。
 * 后端：GET /api/tasks/subtasks/batch?task_ids=1,2,3
 * 返回：{ "1": [...], "2": [...] }，task_id 字符串作为 key
 */
export function fetchSubTasksBatch(taskIds: number[], deleted = false): Promise<Record<string, SubTaskItem[]>> {
  if (taskIds.length === 0) return Promise.resolve({})
  const qs = `task_ids=${taskIds.join(',')}&deleted=${deleted ? 'true' : 'false'}`
  return apiGet<Record<string, SubTaskItem[]>>(`/api/tasks/subtasks/batch?${qs}`)
}

export function createSubTask(taskId: number, data: SubTaskPayload): Promise<SubTaskItem> {
  return apiPost<SubTaskItem>(`/api/tasks/${taskId}/subtasks`, data)
}

export function updateSubTask(id: number, data: SubTaskPayload): Promise<SubTaskItem> {
  return apiPatch<SubTaskItem>(`/api/subtasks/${id}`, data)
}

export type PendingConfirmationResult = {
  status: 'pending_confirmation'
  submission_id: number
}

export type SubTaskStatusResult = SubTaskItem | PendingConfirmationResult

export function isPendingConfirmation(r: SubTaskStatusResult): r is PendingConfirmationResult {
  return (r as PendingConfirmationResult).status === 'pending_confirmation'
}

export function patchSubTaskStatus(id: number, status: string): Promise<SubTaskStatusResult> {
  return apiPatch<SubTaskStatusResult>(`/api/subtasks/${id}/status`, { status })
}

export function deleteSubTask(id: number, reason = ''): Promise<unknown> {
  const qs = reason ? `?reason=${encodeURIComponent(reason)}` : ''
  return apiDelete(`/api/subtasks/${id}${qs}`)
}

export function restoreSubTask(id: number): Promise<SubTaskItem> {
  return apiPost<SubTaskItem>(`/api/subtasks/${id}/restore`, {})
}

export type SubTaskDetail = SubTaskItem & {
  parent_task?: { id: number; key_task: string; special_project: string } // legacy display fallback only
  source_submission?: {
    id: number
    submitter: string
    source_type: string
    title: string
    created_at: string | null
    summary: string
    completed_items: string[]
    transcript_text: string
  }
  related_achievements?: {
    id: number
    name: string
    achievement_type: string
    status: string
    owner: string
    version: string
    created_at: string | null
  }[]
  related_issues?: {
    id: number
    description: string
    issue_type: string
    status: string
    priority: string
    owner: string
    created_at: string | null
  }[]
}

export function fetchSubtaskDetail(id: number): Promise<SubTaskDetail> {
  return apiGet<SubTaskDetail>(`/api/subtasks/${id}/detail`)
}

export function fetchSubtasksByAssignee(assignee: string, projectId: number | null): Promise<SubTaskWithParent[]> {
  const qs = new URLSearchParams({ assignee })
  if (projectId != null) qs.set('project_id', String(projectId))
  return apiGet<SubTaskWithParent[]>(`/api/subtasks?${qs}`)
}

export function fetchSubtasksByProject(projectId: number): Promise<SubTaskWithParent[]> {
  return apiGet<SubTaskWithParent[]>(`/api/subtasks?project_id=${projectId}`)
}

// ── 语义别名（KeyTask = SubTask）───────────────────────────────
// API endpoint 不变，仅函数名做语义映射
export const fetchKeyTasks = fetchSubTasks
export const createKeyTask = createSubTask
export const updateKeyTask = updateSubTask
export const patchKeyTaskStatus = patchSubTaskStatus
export const deleteKeyTask = deleteSubTask
export const restoreKeyTask = restoreSubTask
export const fetchKeyTaskDetail = fetchSubtaskDetail
export const fetchKeyTasksByAssignee = fetchSubtasksByAssignee
export const fetchKeyTasksByProject = fetchSubtasksByProject
export type { SubTaskItem as KeyTaskItem } from '../types'
