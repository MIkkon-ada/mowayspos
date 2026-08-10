import { useMemo, useState } from 'react'
import type { ExecutionSchedule } from '../../api/executionSchedules'

type Filter = '全部' | '待开始' | '进行中' | '已逾期' | '已完成'
type Props = { schedules: ExecutionSchedule[]; canManage?: boolean; onCreate?: () => void }

const filters: Filter[] = ['全部', '待开始', '进行中', '已逾期', '已完成']
const displayStatus = (row: ExecutionSchedule) => row.is_overdue ? '已逾期' : row.is_due_soon ? '即将到期' : row.status
const tone = (status: string) => ({
  '待开始': 'bg-slate-100 text-slate-700', '进行中': 'bg-blue-50 text-blue-700', '即将到期': 'bg-amber-50 text-amber-700', '已逾期': 'bg-red-50 text-red-700', '已完成': 'bg-emerald-50 text-emerald-700', '已取消': 'bg-slate-100 text-slate-500',
}[status] ?? 'bg-slate-100 text-slate-700')

export function ExecutionScheduleTimeline({ schedules, canManage = false, onCreate }: Props) {
  const [filter, setFilter] = useState<Filter>('全部')
  const rows = useMemo(() => schedules.filter((row) => filter === '全部' || displayStatus(row) === filter).sort((a, b) => a.start_date.localeCompare(b.start_date) || a.due_date.localeCompare(b.due_date)), [filter, schedules])
  return <section className="rounded-xl border border-slate-200 bg-white p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-base font-semibold text-slate-800">执行安排</h2><p className="mt-1 text-xs text-slate-400">按时间轴查看周计划和月计划</p></div>{canManage && <button type="button" onClick={onCreate} className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white">新建执行安排</button>}</div>
    <div className="mt-4 flex flex-wrap gap-2">{filters.map((item) => <button key={item} type="button" onClick={() => setFilter(item)} className={`rounded-full px-3 py-1 text-xs ${filter === item ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600'}`}>{item}</button>)}</div>
    <div className="mt-4 border-l-2 border-slate-200 pl-4">{rows.length ? rows.map((row) => { const status = displayStatus(row); return <article key={row.id} className="relative mb-3 rounded-lg border border-slate-200 p-3 before:absolute before:-left-[22px] before:top-5 before:size-2 before:rounded-full before:bg-blue-500"><div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-sm text-slate-800">{row.title}</strong><span aria-label={`状态：${status}`} className={`rounded-full px-2 py-0.5 text-xs font-semibold ${tone(status)}`}>{status}</span></div><p className="mt-1 text-xs text-slate-500"><span className="mr-2 rounded bg-blue-50 px-1.5 py-0.5 text-blue-700">{row.plan_type === 'week' ? '周计划' : '月计划'}</span>{row.start_date} 至 {row.due_date} · {row.assignee || '未指定负责人'}</p></article> }) : <p className="py-5 text-center text-sm text-slate-400">当前筛选条件下暂无执行安排</p>}</div>
  </section>
}
