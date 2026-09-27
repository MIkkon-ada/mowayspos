import { apiDelete, apiGet, apiPatch, apiPost } from './client'

export type ExecutionSchedule = {
  id: number
  subtask_id: number
  plan_type: 'week' | 'month'
  title: string
  start_date: string
  due_date: string
  assignee: string
  assignee_id?: number | null
  status: '待开始' | '进行中' | '已完成' | '已取消'
  is_overdue: boolean
  is_due_soon: boolean
}

export type ExecutionSchedulePayload = Pick<ExecutionSchedule, 'plan_type' | 'title' | 'start_date' | 'due_date' | 'assignee' | 'status'> & { assignee_id?: number | null }

export const fetchExecutionSchedules = (subtaskId: number) => apiGet<ExecutionSchedule[]>(`/api/subtasks/${subtaskId}/execution-schedules`)
export const createExecutionSchedule = (subtaskId: number, payload: ExecutionSchedulePayload) => apiPost<ExecutionSchedule>(`/api/subtasks/${subtaskId}/execution-schedules`, payload)
export const updateExecutionSchedule = (id: number, payload: ExecutionSchedulePayload) => apiPatch<ExecutionSchedule>(`/api/execution-schedules/${id}`, payload)
export const deleteExecutionSchedule = (id: number) => apiDelete(`/api/execution-schedules/${id}`)
