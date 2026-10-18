import { apiGet, apiPost, apiPatch, apiDelete, apiPut } from './client'
import type { Project, ProjectCapabilities, ProjectMember, MemberChangeRequest, ProjectCloseRequest, ProjectCloseRequestCreatePayload, ProjectCloseRequestUpdatePayload, ProjectCloseReviewPayload } from '../types'
import type { ProjectLifecycleStatus } from '../domain/projectLifecycleStatus'
import type { WorkProgressOptionalColumnKey } from '../components/task-management/workProgressColumnSizing'

export type WorkProgressColumnConfiguration = { optional_columns: WorkProgressOptionalColumnKey[] }

export function getWorkProgressColumns(projectId: number): Promise<WorkProgressColumnConfiguration> {
  return apiGet<WorkProgressColumnConfiguration>(`/api/projects/${projectId}/work-progress-columns`)
}

export function updateWorkProgressColumns(projectId: number, optionalColumns: WorkProgressOptionalColumnKey[]): Promise<WorkProgressColumnConfiguration> {
  return apiPatch<WorkProgressColumnConfiguration>(`/api/projects/${projectId}/work-progress-columns`, { optional_columns: optionalColumns })
}

// 当前用户可见项目：GET /api/projects[?include_archived=true]
export function getProjects(includeArchived = false): Promise<Project[]> {
  const q = includeArchived ? '?include_archived=true' : ''
  return apiGet<Project[]>(`/api/projects${q}`)
}

// 项目详情：GET /api/projects/{id}
export function getProject(projectId: number): Promise<Project> {
  return apiGet<Project>(`/api/projects/${projectId}`)
}

// 项目成员：GET /api/projects/{id}/members
export function getProjectMembers(projectId: number): Promise<ProjectMember[]> {
  return apiGet<ProjectMember[]>(`/api/projects/${projectId}/members`)
}

// 当前用户在该项目的能力标志：GET /api/projects/{id}/capabilities
export function getProjectCapabilities(projectId: number): Promise<ProjectCapabilities> {
  return apiGet<ProjectCapabilities>(`/api/projects/${projectId}/capabilities`)
}

// ── 4B：项目主数据管理（super_admin）────────────────────────

export type ProjectCreatePayload = {
  name: string
  code?: string
  description?: string
  status?: string
  start_date?: string
  end_date?: string
  project_type?: string
  client_name?: string
  background?: string
  objectives?: string
  expected_outcomes?: string
  lifecycle_status?: string
  // 初始成员（可选）
  project_ceo_ids?: number[]
  owner_ids?: number[]
  coordinator_ids?: number[]
  member_ids?: number[]
}

export type ProjectPatchPayload = {
  name?: string
  code?: string
  description?: string
  status?: string
  start_date?: string
  end_date?: string
  project_type?: string
  client_name?: string
  background?: string
  objectives?: string
  expected_outcomes?: string
  lifecycle_status?: string
}

export function createProject(payload: ProjectCreatePayload, clientRequestId?: string): Promise<Project> {
  return apiPost<Project>('/api/projects', clientRequestId
    ? { ...payload, client_request_id: clientRequestId }
    : payload)
}

export function patchProject(projectId: number, payload: ProjectPatchPayload): Promise<Project> {
  return apiPatch<Project>(`/api/projects/${projectId}`, payload)
}

export function archiveProject(projectId: number): Promise<{ ok: boolean; status: string }> {
  return apiPost(`/api/projects/${projectId}/archive`)
}

export type ProjectDeleteResult = {
  ok: boolean
  project_id: number
  cleanup_pending: boolean
  cleanup_key: string | null
}

export function deleteProject(projectId: number, confirmName: string, confirmPhrase: string): Promise<ProjectDeleteResult> {
  return apiDelete(`/api/projects/${projectId}`, { confirm_name: confirmName, confirm_phrase: confirmPhrase })
}

export function createProjectCloseRequest(projectId: number, payload: ProjectCloseRequestCreatePayload, clientRequestId?: string): Promise<ProjectCloseRequest> {
  return apiPost<ProjectCloseRequest>(`/api/projects/${projectId}/close-requests`, clientRequestId
    ? { ...payload, client_request_id: clientRequestId }
    : payload)
}
export function getProjectCloseRequests(projectId: number, status?: string): Promise<ProjectCloseRequest[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : ''
  return apiGet<ProjectCloseRequest[]>(`/api/projects/${projectId}/close-requests${query}`)
}
export function getProjectCloseRequest(projectId: number, requestId: number): Promise<ProjectCloseRequest> {
  return apiGet<ProjectCloseRequest>(`/api/projects/${projectId}/close-requests/${requestId}`)
}
export function updateProjectCloseRequest(projectId: number, requestId: number, payload: ProjectCloseRequestUpdatePayload): Promise<ProjectCloseRequest> {
  return apiPatch<ProjectCloseRequest>(`/api/projects/${projectId}/close-requests/${requestId}`, payload)
}
export function cancelProjectCloseRequest(projectId: number, requestId: number): Promise<ProjectCloseRequest> {
  return apiPost<ProjectCloseRequest>(`/api/projects/${projectId}/close-requests/${requestId}/cancel`, {})
}
export function approveProjectCloseRequest(projectId: number, requestId: number, payload: ProjectCloseReviewPayload): Promise<ProjectCloseRequest> {
  return apiPost<ProjectCloseRequest>(`/api/projects/${projectId}/close-requests/${requestId}/approve`, payload)
}
export function rejectProjectCloseRequest(projectId: number, requestId: number, payload: ProjectCloseReviewPayload): Promise<ProjectCloseRequest> {
  return apiPost<ProjectCloseRequest>(`/api/projects/${projectId}/close-requests/${requestId}/reject`, payload)
}

export function kickoffProject(projectId: number, kickoffDate?: string): Promise<Project> {
  const q = kickoffDate ? `?kickoff_date=${encodeURIComponent(kickoffDate)}` : ''
  return apiPost<Project>(`/api/projects/${projectId}/kickoff${q}`)
}

export type ProjectProfilePayload = {
  project_type?: string
  client_name?: string
  background?: string
  objectives?: string
  expected_outcomes?: string
  start_date?: string
  end_date?: string
  description?: string
  work_progress_draft?: ProjectWorkProgressTaskDraft[]
  replace_plan?: boolean
  ai_run_id?: number
}

export type ProjectWorkProgressSubTaskDraft = {
  id?: number
  subtask_id?: number
  title: string
  evaluation_standard?: string
  assignee?: string
  assignee_id?: number
  helper?: string
  helper_ids?: number[]
  plan_start?: string
  plan_end?: string
}

export type ProjectWorkProgressTaskDraft = {
  id?: number
  task_id?: number
  title: string
  description?: string
  goal?: string
  acceptance_criteria?: string
  process?: string
  owner?: string
  helper?: string
  plan_start?: string
  plan_end?: string
  subtasks?: ProjectWorkProgressSubTaskDraft[]
}

export function ownerSubmitProfile(
  projectId: number,
  payload: ProjectProfilePayload,
): Promise<Project & { submitted_for_review: boolean }> {
  return apiPost(`/api/projects/${projectId}/owner-submit`, payload)
}

export type OwnerPlanDraftResponse = {
  draft: ProjectProfilePayload | null
  existing_plan: ProjectWorkProgressTaskDraft[]
  saved_at: string | null
  return_reason: string
}

export function getOwnerPlanDraft(projectId: number): Promise<OwnerPlanDraftResponse> {
  return apiGet(`/api/projects/${projectId}/owner-plan-draft`)
}

export function saveOwnerPlanDraft(projectId: number, payload: ProjectProfilePayload): Promise<{ saved_at: string }> {
  return apiPut(`/api/projects/${projectId}/owner-plan-draft`, payload)
}

export function dispatchProject(projectId: number): Promise<{ ok: boolean; notified_to: number; status: ProjectLifecycleStatus }> {
  return apiPost(`/api/projects/${projectId}/dispatch`, {})
}

export function returnProject(projectId: number, reason?: string): Promise<Project> {
  const q = reason ? `?reason=${encodeURIComponent(reason)}` : ''
  return apiPost<Project>(`/api/projects/${projectId}/return${q}`, {})
}

export function approveProject(
  projectId: number,
  payload?: ProjectProfilePayload,
  kickoffDate?: string,
): Promise<Project> {
  const q = kickoffDate ? `?kickoff_date=${encodeURIComponent(kickoffDate)}` : ''
  return apiPost<Project>(`/api/projects/${projectId}/approve${q}`, payload ?? {})
}

export type BatchImportRow = {
  project_name: string
  project_objective?: string
  workstream?: string
  key_task: string
  key_achievement?: string
  completion_standard?: string
  coordinator?: string
  owner?: string
  collaborators?: string
  plan_time?: string
  plan_start?: string
  plan_end?: string
  workstream_plan_start?: string
  workstream_plan_end?: string
  status?: string
  issue?: string
  notes?: string
  sequence?: string
}

export type BatchImportResult = {
  ok: boolean
  projects_created: number
  projects_matched: number
  tasks_created: number
  subtasks_created: number
  issues_created: number
  duplicates_skipped: number
  skipped_rows: number
}

export function batchImportProjects(rows: BatchImportRow[], clientRequestId?: string): Promise<BatchImportResult> {
  return apiPost<BatchImportResult>('/api/projects/batch-import', clientRequestId
    ? { rows, client_request_id: clientRequestId }
    : { rows })
}

// ── 4A：项目成员管理（super_admin）──────────────────────────

export type MemberAddPayload = {
  person_id: number
  role: string
  note?: string
}

export type MemberPatchPayload = {
  role?: string
  note?: string
}

export function addProjectMember(projectId: number, payload: MemberAddPayload): Promise<ProjectMember> {
  return apiPost<ProjectMember>(`/api/projects/${projectId}/members`, payload)
}

export function updateProjectMember(
  projectId: number,
  memberId: number,
  payload: MemberPatchPayload,
): Promise<ProjectMember> {
  return apiPatch<ProjectMember>(`/api/projects/${projectId}/members/${memberId}`, payload)
}

export function removeProjectMember(projectId: number, memberId: number): Promise<{ ok: boolean }> {
  return apiDelete(`/api/projects/${projectId}/members/${memberId}`)
}

// ── 成员变更申请（N8-P1-P1A/B）─────────────────────────────

export type MemberChangeRequestPayload = {
  target_person_id: number
  to_role: 'member' | 'coordinator'
  reason: string
}

export type MemberChangeReviewPayload = {
  review_comment?: string
}

export function createMemberChangeRequest(
  projectId: number,
  payload: MemberChangeRequestPayload,
): Promise<MemberChangeRequest> {
  return apiPost<MemberChangeRequest>(`/api/projects/${projectId}/member-change-requests`, payload)
}

export function getMemberChangeRequests(
  projectId: number,
  status?: 'pending' | 'approved' | 'rejected',
): Promise<MemberChangeRequest[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : ''
  return apiGet<MemberChangeRequest[]>(`/api/projects/${projectId}/member-change-requests${q}`)
}

export function approveMemberChangeRequest(
  projectId: number,
  requestId: number,
  payload?: MemberChangeReviewPayload,
): Promise<MemberChangeRequest> {
  return apiPost<MemberChangeRequest>(`/api/projects/${projectId}/member-change-requests/${requestId}/approve`, payload ?? {})
}

export function rejectMemberChangeRequest(
  projectId: number,
  requestId: number,
  payload?: MemberChangeReviewPayload,
): Promise<MemberChangeRequest> {
  return apiPost<MemberChangeRequest>(`/api/projects/${projectId}/member-change-requests/${requestId}/reject`, payload ?? {})
}
