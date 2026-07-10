import { apiGet, apiPost, apiPatch, apiDelete } from './client'
import type { Project, ProjectCapabilities, ProjectMember, MemberChangeRequest } from '../types'

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

export function createProject(payload: ProjectCreatePayload): Promise<Project> {
  return apiPost<Project>('/api/projects', payload)
}

export function patchProject(projectId: number, payload: ProjectPatchPayload): Promise<Project> {
  return apiPatch<Project>(`/api/projects/${projectId}`, payload)
}

export function archiveProject(projectId: number): Promise<{ ok: boolean; status: string }> {
  return apiPost(`/api/projects/${projectId}/archive`)
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
}

export function ownerSubmitProfile(
  projectId: number,
  payload: ProjectProfilePayload,
): Promise<Project & { submitted_for_review: boolean }> {
  return apiPost(`/api/projects/${projectId}/owner-submit`, payload)
}

export function dispatchProject(projectId: number): Promise<{ ok: boolean; dispatched_to: number }> {
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
  key_task: string
  key_achievement?: string
  completion_standard?: string
  coordinator?: string
  owner?: string
  collaborators?: string
  plan_time?: string
  status?: string
  issue?: string
}

export type BatchImportResult = {
  ok: boolean
  projects_created: number
  projects_matched: number
  tasks_created: number
  issues_created: number
  skipped_rows: number
}

export function batchImportProjects(rows: BatchImportRow[]): Promise<BatchImportResult> {
  return apiPost<BatchImportResult>('/api/projects/batch-import', { rows })
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
