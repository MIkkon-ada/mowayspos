import { describe, expect, it } from 'vitest'
import { monthPlanStatus, monthTabs, sortMonthPlans } from './monthPlans'
import type { MonthlyPlan } from '../api/monthlyPlans'

const plan = (id: number, status: MonthlyPlan['status'], dueDate: string | null = null): MonthlyPlan => ({
  id,
  subtask_id: 1,
  plan_month: '2026-08',
  title: String(id),
  expected_output: '产出',
  assignee: '邹奇敏',
  assignee_id: 2,
  collaborator_ids: [],
  collaborators: [],
  status,
  display_status: status,
  is_overdue: false,
  start_date: dueDate,
  due_date: dueDate,
  completion_criteria: '',
  progress_note: '',
  risk_dependency: '',
  actual_output: '',
  delay_reason: '',
  sort_order: 0,
})

describe('month plans', () => {
  it('sorts overdue, in progress, paused, not started and completed in management order', () => {
    const overdue: MonthlyPlan = { ...plan(1, '进行中', '2026-08-10'), is_overdue: true, display_status: '已延期' }

    expect(sortMonthPlans([
      plan(5, '已完成'),
      plan(4, '未开始'),
      plan(3, '暂缓'),
      plan(2, '进行中'),
      overdue,
    ]).map((item) => item.id)).toEqual([1, 2, 3, 4, 5])
  })

  it('includes the current month and its immediate neighbours alongside stored months', () => {
    expect(monthTabs('2026-08', ['2026-06', '2026-10'])).toEqual([
      '2026-06', '2026-07', '2026-08', '2026-09', '2026-10',
    ])
  })

  it('uses the server overdue projection as the visible status', () => {
    expect(monthPlanStatus({ ...plan(1, '进行中'), is_overdue: true, display_status: '已延期' })).toBe('已延期')
  })
})
