import { apiDelete, apiGet, apiPost } from './client'

export type CreateUpdatePayload = {
  project_id?: number | null  // 可选，AI 自动匹配
  source_type: string
  transcript_text: string
  submitter?: string
  title?: string
  llm_provider?: string
  human_result?: Record<string, unknown> // 用户编辑后的结果（二步流程第二步传入）
}

export type UserSubtaskContext = {
  id: number
  title: string
  status: string
  parent_task_id?: number
  parent_key_task: string
  parent_project_id?: number | null
  assignee?: string
  user_relation?: string // 'owner' | 'coordinator' | 'task_owner' | 'subtask_assignee'
}

export type TaskReportAchievement = {
  name: string
  achievement_type: string
  file_link?: string
}

export type TaskReportProgress = {
  type: 'progress'
  matched_subtask_id: number | null
  matched_subtask_title: string
  parent_task_id?: number | null
  parent_key_task?: string
  completed: string
  achievements: TaskReportAchievement[]
  subtask_issues: string[]
  next_steps: string[]
  status_update: string
}

export type TaskReportNewTask = {
  type: 'new_task'
  title: string
  assignee: string
  plan_start: string
  plan_end: string
  completed: null
  achievements: TaskReportAchievement[]
  subtask_issues: string[]
  next_steps: string[]
}

export type TaskReportSuggest = {
  type: 'suggest_new_subtask'
  result_type: 'suggest_new_subtask'
  title: string
  assignee?: string
  plan_start?: string
  plan_end?: string
  completed: null
  achievements: TaskReportAchievement[]
  subtask_issues: string[]
  next_steps: string[]
  parent_task_id: number | null
  parent_key_task: string
}

export type TaskReport = TaskReportProgress | TaskReportNewTask | TaskReportSuggest

export type KeyTaskIssue = {
  key_task_title: string
  issue_type: string
  description: string
  need_coordination: string[]
  priority: string
}

export type ExtractOnlyPayload = {
  project_id?: number
  source_type: string
  transcript_text: string
  submitter?: string
  llm_provider?: string
  user_subtasks?: UserSubtaskContext[]
}

export type CreateUpdateResult = {
  submission?: { id?: number; confirm_status?: string; [k: string]: unknown }
  suggestion?: Record<string, unknown>
}

// AI 提取，不写 DB：POST /api/updates/extract
export function extractOnly(payload: ExtractOnlyPayload): Promise<{ suggestion: Record<string, unknown> }> {
  return apiPost<{ suggestion: Record<string, unknown> }>('/api/updates/extract', payload)
}

// 成员提交进展（第二步确认后写DB）：POST /api/updates
export function createUpdate(payload: CreateUpdatePayload): Promise<CreateUpdateResult> {
  return apiPost<CreateUpdateResult>('/api/updates', payload)
}

export type UpdateHistoryItem = {
  id: number
  project_id?: number | null
  submitter: string
  source_type: string
  title?: string
  transcript_text: string
  confirm_status: string
  confidence: number | null
  special_project?: string
  created_at: string
  updated_at?: string
  ai_result_json?: string
  reject_reason?: string
  coordinator_note?: string
  ceo_note?: string
  [key: string]: unknown
}

export type UpdateDetail = UpdateHistoryItem & {
  confirmed_by?: string
  confirmed_at?: string
  reject_reason?: string
  coordinator_note?: string
  ceo_note?: string
  related_task_id?: number | null
  related_subtask_id?: number | null
  ai_result?: Record<string, unknown>
  human_result?: Record<string, unknown>
}

export function fetchUpdates(projectId: number): Promise<UpdateHistoryItem[]> {
  return apiGet<UpdateHistoryItem[]>(`/api/updates?project_id=${projectId}`)
}

export function fetchMyUpdates(): Promise<UpdateHistoryItem[]> {
  return apiGet<UpdateHistoryItem[]>('/api/updates?mine=true')
}

export function getUpdate(id: number): Promise<UpdateDetail> {
  return apiGet<UpdateDetail>(`/api/updates/${id}`)
}

export function deleteUpdate(id: number): Promise<unknown> {
  return apiDelete(`/api/updates/${id}`)
}

// 语音/文字更新提取前：获取当前用户有权提交进展的关键任务候选池（权限敏感）
// projectId 可选：不传时返回用户所有项目的子任务（跨项目汇报）
export function fetchVoiceContext(projectId?: number | null): Promise<UserSubtaskContext[]> {
  const qs = projectId != null ? `?project_id=${projectId}` : ''
  return apiGet<UserSubtaskContext[]>(`/api/updates/voice-context${qs}`)
}
