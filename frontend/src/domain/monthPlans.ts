import type { MonthlyPlan } from '../api/monthlyPlans'

const STATUS_RANK = { 已延期: 0, 进行中: 1, 暂缓: 2, 未开始: 3, 已完成: 4, 已取消: 5 } as const

export const currentMonthKey = (now = new Date()) =>
  `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`

export const monthPlanStatus = (plan: MonthlyPlan) => plan.display_status

export function sortMonthPlans(plans: MonthlyPlan[]) {
  return [...plans].sort((left, right) =>
    STATUS_RANK[monthPlanStatus(left)] - STATUS_RANK[monthPlanStatus(right)] ||
    Number(left.due_date == null) - Number(right.due_date == null) ||
    (left.due_date ?? '9999-12-31').localeCompare(right.due_date ?? '9999-12-31') ||
    left.sort_order - right.sort_order || left.id - right.id,
  )
}

function shiftMonth(month: string, delta: number) {
  const [year, value] = month.split('-').map(Number)
  const date = new Date(year, value - 1 + delta, 1)
  return currentMonthKey(date)
}

export function monthTabs(currentMonth: string, storedMonths: string[]) {
  return [...new Set([shiftMonth(currentMonth, -1), currentMonth, shiftMonth(currentMonth, 1), ...storedMonths])]
    .sort((left, right) => left.localeCompare(right))
}

export function formatMonthLabel(month: string) {
  const [year, value] = month.split('-')
  return `${year} 年 ${Number(value)} 月`
}
