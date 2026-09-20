import { apiGet } from './client'
import type { DashboardOverview } from '../types'

// 项目工作台概览：GET /api/dashboard/overview?project_id=X&month=2026年6月
export function getOverview(projectId?: number | null, month?: string): Promise<DashboardOverview> {
  const params = new URLSearchParams()
  if (projectId !== null && projectId !== undefined) params.set('project_id', String(projectId))
  if (month) params.set('month', month)
  const query = params.toString() ? `?${params.toString()}` : ''
  return apiGet<DashboardOverview>(`/api/dashboard/overview${query}`)
}

// 导出周报：GET /api/dashboard/export-weekly-report → Blob(docx)
export async function exportWeeklyReport(projectId?: number | null, month?: string): Promise<void> {
  const params = new URLSearchParams()
  if (projectId !== null && projectId !== undefined) params.set('project_id', String(projectId))
  if (month) params.set('month', month)
  const query = params.toString() ? `?${params.toString()}` : ''
  const resp = await fetch(`/api/dashboard/export-weekly-report${query}`, { credentials: 'include' })
  if (!resp.ok) throw new Error('导出失败')
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const disposition = resp.headers.get('content-disposition') ?? ''
  const match = disposition.match(/filename\*?=(?:UTF-8'')?([^;]+)/)
  a.download = match ? decodeURIComponent(match[1].replace(/"/g, '')) : '周报.docx'
  a.click()
  URL.revokeObjectURL(url)
}
