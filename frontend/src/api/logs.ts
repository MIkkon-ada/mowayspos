import { apiGet } from './client'

export type OperationLogItem = {
  id: number
  operator: string
  action: string
  target_type: string
  target_id: number | null
  before_json: string
  after_json: string
  created_at: string
  project_id: number | null
}

export type GlobalLogsResult = {
  total: number
  items: OperationLogItem[]
}

export function fetchGlobalLogs(params: {
  operator?: string
  action?: string
  target_type?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}): Promise<GlobalLogsResult> {
  const qs = new URLSearchParams()
  if (params.operator)    qs.set('operator', params.operator)
  if (params.action)      qs.set('action', params.action)
  if (params.target_type) qs.set('target_type', params.target_type)
  if (params.date_from)   qs.set('date_from', params.date_from)
  if (params.date_to)     qs.set('date_to', params.date_to)
  if (params.page)        qs.set('page', String(params.page))
  if (params.page_size)   qs.set('page_size', String(params.page_size))
  return apiGet<GlobalLogsResult>(`/api/logs/global?${qs.toString()}`)
}
