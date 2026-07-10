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
  priority?: string
  expected_resolve_time?: string
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
