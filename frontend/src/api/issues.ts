import { apiDelete, apiGet, apiPatch, apiPost } from './client'
import type { IssueItem } from '../types'

export function fetchIssues(projectId?: number | null): Promise<IssueItem[]> {
  const query = projectId != null ? `?project_id=${projectId}` : ''
  return apiGet<IssueItem[]>(`/api/issues${query}`)
}

export function fetchMyIssues(): Promise<IssueItem[]> {
  return apiGet<IssueItem[]>('/api/issues/mine')
}

export function createIssue(payload: {
  project_id: number
  issue_type?: string
  description: string
  owner?: string
  helper?: string
  priority?: string
  status?: string
  source_type?: string
  expected_resolve_time?: string
  related_task_id?: number | null
  related_subtask_id?: number | null
}): Promise<IssueItem> {
  return apiPost<IssueItem>('/api/issues', payload)
}

export function deleteIssue(id: number): Promise<unknown> {
  return apiDelete(`/api/issues/${id}`)
}

export function resolveIssue(id: number, resolution?: string, handlerReply?: string): Promise<IssueItem> {
  return apiPatch<IssueItem>(`/api/issues/${id}/resolve`, {
    resolution: resolution ?? '',
    handler_reply: handlerReply ?? '',
  })
}

export function closeIssue(id: number, reason?: string, handlerReply?: string): Promise<IssueItem> {
  return apiPatch<IssueItem>(`/api/issues/${id}/close`, {
    reason: reason ?? '',
    handler_reply: handlerReply ?? '',
  })
}

export function assignIssueHelper(id: number, helper: string): Promise<IssueItem> {
  return apiPatch<IssueItem>(`/api/issues/${id}/assign-helper`, { helper })
}

export function requestIssueCeo(id: number, needDecisionBy: string, note?: string): Promise<IssueItem> {
  return apiPatch<IssueItem>(`/api/issues/${id}/request-ceo`, {
    need_decision_by: needDecisionBy,
    note: note ?? '',
  })
}

export function updateIssueStatus(issueId: number, status: string): Promise<IssueItem> {
  return apiPatch<IssueItem>(`/api/issues/${issueId}/status`, { status })
}

// 统筹/教练提交意见（Issue 进入「待负责人确认」）
export function submitIssueOpinion(id: number, opinion: string): Promise<IssueItem> {
  return apiPatch<IssueItem>(`/api/issues/${id}/submit-opinion`, { opinion })
}

// 负责人确认意见（accepted=true → 已解决并回写；false → 退回）
export function ownerConfirmOpinion(id: number, accepted: boolean, note: string): Promise<IssueItem> {
  return apiPatch<IssueItem>(`/api/issues/${id}/owner-confirm`, { accepted, note })
}
