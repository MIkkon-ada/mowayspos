import { apiGet, apiPost } from './client'
import type { ConfirmationItem } from '../types'

// AI 确认中心待办：GET /api/confirmations/pending?project_id=X[&tab=...][&include_card_level=true]
// projectId 可选：企业教练决策中心传 null 表示查全部项目
export function getPending(
  projectId: number | null,
  tab?: string,
  options?: { includeCardLevel?: boolean },
): Promise<ConfirmationItem[]> {
  const params = new URLSearchParams()
  if (projectId !== null && projectId !== undefined) params.set('project_id', String(projectId))
  if (tab) params.set('tab', tab)
  if (options?.includeCardLevel) params.set('include_card_level', 'true')
  const query = params.toString() ? `?${params.toString()}` : ''
  return apiGet<ConfirmationItem[]>(`/api/confirmations/pending${query}`)
}

// 提交详情：GET /api/confirmations/{id}（含 ai_result / human_result）
export function getConfirmationDetail(id: number): Promise<Record<string, unknown>> {
  return apiGet<Record<string, unknown>>(`/api/confirmations/${id}`)
}

// ── 动作（前端只对当前角色显示对应按钮，权限由后端最终把关）──

export function confirmSubmission(
  id: number,
  operator: string,
  human_result?: Record<string, unknown>,
): Promise<{ ok?: boolean; submission?: ConfirmationItem }> {
  return apiPost<{ ok?: boolean; submission?: ConfirmationItem }>(`/api/confirmations/${id}/confirm`, { operator, human_result })
}

export function rejectSubmission(id: number, reason: string, operator: string): Promise<{ ok?: boolean; submission?: ConfirmationItem }> {
  return apiPost<{ ok?: boolean; submission?: ConfirmationItem }>(`/api/confirmations/${id}/reject`, { reason, operator })
}

export function resubmitSubmission(
  id: number,
  supplementNote: string,
  operator: string,
  humanResult?: Record<string, unknown>,
): Promise<{ ok?: boolean; submission?: ConfirmationItem }> {
  return apiPost<{ ok?: boolean; submission?: ConfirmationItem }>(`/api/confirmations/${id}/resubmit`, {
    supplement_note: supplementNote,
    operator,
    human_result: humanResult,
  })
}

export function transferCoordinator(id: number, note: string, operator: string): Promise<{ ok?: boolean; submission?: ConfirmationItem }> {
  return apiPost<{ ok?: boolean; submission?: ConfirmationItem }>(`/api/confirmations/${id}/transfer-coordinator`, { note, operator })
}

export function escalateCeo(id: number, note: string, operator: string): Promise<{ ok?: boolean; submission?: ConfirmationItem }> {
  return apiPost<{ ok?: boolean; submission?: ConfirmationItem }>(`/api/confirmations/${id}/escalate-ceo`, { note, operator })
}

export function coordinatorFeedback(id: number, note: string, operator: string) {
  return apiPost(`/api/confirmations/${id}/coordinator-feedback`, { note, operator })
}

export function coordinatorFeedbackTaskCard(
  id: number,
  cardIndex: number,
  note: string,
  operator: string,
) {
  return apiPost(
    `/api/confirmations/${id}/cards/${cardIndex}/coordinator-feedback`,
    { note, operator },
  )
}

export function ceoDecide(id: number, note: string, operator: string) {
  return apiPost(`/api/confirmations/${id}/ceo-decide`, { note, operator })
}

export function confirmTaskCard(id: number, cardIndex: number, operator: string) {
  return apiPost(`/api/confirmations/${id}/cards/${cardIndex}/confirm`, { operator })
}

export function rejectTaskCard(id: number, cardIndex: number, reason: string, operator: string) {
  return apiPost(`/api/confirmations/${id}/cards/${cardIndex}/reject`, { reason, operator })
}

export function transferTaskCardCoordinator(id: number, cardIndex: number, note: string, operator: string) {
  return apiPost(`/api/confirmations/${id}/cards/${cardIndex}/transfer-coordinator`, { note, operator })
}

export function escalateTaskCardCeo(id: number, cardIndex: number, note: string, operator: string) {
  return apiPost(`/api/confirmations/${id}/cards/${cardIndex}/escalate-ceo`, { note, operator })
}

export function ceoDecideTaskCard(id: number, cardIndex: number, note: string, operator: string) {
  return apiPost(`/api/confirmations/${id}/cards/${cardIndex}/ceo-decide`, { note, operator })
}

export function getConfirmationCounts(): Promise<Record<string, number>> {
  return apiGet<Record<string, number>>('/api/confirmations/counts')
}
