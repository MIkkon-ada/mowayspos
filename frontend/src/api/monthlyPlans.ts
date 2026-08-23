import { apiDelete, apiGet, apiPatch, apiPost } from './client'

export type MonthPlanStatus = '未开始' | '进行中' | '暂缓' | '已完成' | '已取消'
export type MonthPlanDisplayStatus = MonthPlanStatus | '已延期'

export type MonthlyPlan = {
  id: number
  subtask_id: number
  plan_month: string | null
  title: string
  expected_output: string
  assignee: string
  assignee_id: number
  collaborator_ids: number[]
  collaborators: string[]
  status: MonthPlanStatus
  display_status: MonthPlanDisplayStatus
  is_overdue: boolean
  start_date: string | null
  due_kind?: 'exact' | 'fuzzy' | 'unknown'
  due_date: string | null
  due_label?: string | null
  due_reference_date?: string | null
  completion_criteria: string
  progress_note: string
  risk_dependency: string
  actual_output: string
  delay_reason: string
  sort_order: number
  is_archived?: boolean
  latest_progress?: string | null
}

export type MonthlyPlanPayload = Omit<MonthlyPlan,
  'id' | 'subtask_id' | 'assignee' | 'collaborators' | 'display_status' | 'is_overdue'
>

export const fetchMonthlyPlans = (subtaskId: number, month?: string) =>
  apiGet<MonthlyPlan[]>(`/api/subtasks/${subtaskId}/monthly-plans${month ? `?month=${encodeURIComponent(month)}` : ''}`)

export const createMonthlyPlan = (subtaskId: number, payload: MonthlyPlanPayload) =>
  apiPost<MonthlyPlan>(`/api/subtasks/${subtaskId}/monthly-plans`, payload)

export const updateMonthlyPlan = (planId: number, payload: Partial<MonthlyPlanPayload>) =>
  apiPatch<MonthlyPlan>(`/api/monthly-plans/${planId}`, payload)

export const deleteMonthlyPlan = (planId: number) =>
  apiDelete(`/api/monthly-plans/${planId}`)
