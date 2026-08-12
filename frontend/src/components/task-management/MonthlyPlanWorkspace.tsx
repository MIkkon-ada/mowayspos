import { useEffect, useMemo, useState } from 'react'
import { createMonthlyPlan, deleteMonthlyPlan, fetchMonthlyPlans, updateMonthlyPlan, type MonthlyPlan, type MonthlyPlanPayload } from '../../api/monthlyPlans'
import { currentMonthKey, formatMonthLabel, monthPlanStatus, monthTabs, sortMonthPlans } from '../../domain/monthPlans'
import type { ProjectMember } from '../../types'
import { toast } from '../../utils/toast'
import { MonthlyPlanDrawer } from './MonthlyPlanDrawer'

type Props = {
  subtaskId: number
  defaultAssigneeId: number | null
  members: ProjectMember[]
  canManage?: boolean
  onChanged?: () => void
  onPlansLoaded?: (plans: MonthlyPlan[]) => void
}

const STATUS_STYLE = {
  已延期: { rail: 'bg-red-500', badge: 'bg-red-50 text-red-700' },
  进行中: { rail: 'bg-blue-500', badge: 'bg-blue-50 text-blue-700' },
  暂缓: { rail: 'bg-amber-500', badge: 'bg-amber-50 text-amber-700' },
  未开始: { rail: 'bg-slate-400', badge: 'bg-slate-100 text-slate-700' },
  已完成: { rail: 'bg-emerald-500', badge: 'bg-emerald-50 text-emerald-700' },
  已取消: { rail: 'bg-slate-300', badge: 'bg-slate-100 text-slate-500' },
} as const

export function MonthlyPlanWorkspace({ subtaskId, defaultAssigneeId, members, canManage = false, onChanged, onPlansLoaded }: Props) {
  const currentMonth = currentMonthKey()
  const [selectedMonth, setSelectedMonth] = useState(currentMonth)
  const [plans, setPlans] = useState<MonthlyPlan[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<MonthlyPlan | null | undefined>(undefined)

  async function refresh() {
    setLoading(true)
    try {
      const loaded = await fetchMonthlyPlans(subtaskId)
      setPlans(loaded)
      onPlansLoaded?.(loaded)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '月计划加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void refresh() }, [subtaskId])

  const tabs = useMemo(() => monthTabs(currentMonth, plans.map((plan) => plan.plan_month)), [currentMonth, plans])
  const rows = useMemo(() => sortMonthPlans(plans.filter((plan) => plan.plan_month === selectedMonth)), [plans, selectedMonth])

  async function save(payload: MonthlyPlanPayload) {
    try {
      const saved = editing ? await updateMonthlyPlan(editing.id, payload) : await createMonthlyPlan(subtaskId, payload)
      const next = editing ? plans.map((plan) => plan.id === saved.id ? saved : plan) : [...plans, saved]
      setPlans(next)
      onPlansLoaded?.(next)
      setSelectedMonth(saved.plan_month)
      toast.success(editing ? '月计划已更新' : '月计划已创建')
      onChanged?.()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '月计划保存失败')
      throw error
    }
  }

  async function remove() {
    if (!editing) return
    try {
      await deleteMonthlyPlan(editing.id)
      const next = plans.filter((plan) => plan.id !== editing.id)
      setPlans(next)
      onPlansLoaded?.(next)
      toast.success('月计划已删除')
      onChanged?.()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '月计划删除失败')
      throw error
    }
  }

  return <section className="rounded-xl border border-slate-200 bg-white p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-base font-semibold text-slate-800">{formatMonthLabel(selectedMonth)}计划</h2><p className="mt-1 text-xs text-slate-400">默认打开当前月；同月可建立多个计划分支</p></div>{canManage && <button type="button" onClick={() => setEditing(null)} className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white">+ 新增月计划</button>}</div>
    <div className="mt-4 flex gap-1 overflow-x-auto border-b border-slate-100 pb-2" role="tablist" aria-label="计划月份">{tabs.map((month) => <button key={month} role="tab" aria-selected={selectedMonth === month} type="button" onClick={() => setSelectedMonth(month)} className={`shrink-0 rounded-lg px-3 py-2 text-xs ${selectedMonth === month ? 'bg-blue-50 font-semibold text-blue-700' : 'text-slate-500 hover:bg-slate-50'}`}>{formatMonthLabel(month)}{month === currentMonth ? '（本月）' : ''}</button>)}</div>
    <p className="mt-4 text-xs text-slate-400">排序：已延期 → 进行中 → 暂缓 → 未开始 → 已完成</p>
    <div className="mt-2 divide-y divide-slate-100">{loading ? <p className="py-8 text-center text-sm text-slate-400">加载月计划中…</p> : rows.length ? rows.map((plan) => <PlanRow key={plan.id} plan={plan} onOpen={() => setEditing(plan)} />) : <div className="py-10 text-center"><p className="text-sm font-medium text-slate-600">本月暂无计划分支</p><p className="mt-1 text-xs text-slate-400">将关键任务拆成这个月可推进、可交付的事项</p>{canManage && <button type="button" onClick={() => setEditing(null)} className="mt-3 text-xs font-semibold text-blue-600">新增月计划</button>}</div>}</div>
    {editing !== undefined && <MonthlyPlanDrawer plan={editing} selectedMonth={selectedMonth} defaultAssigneeId={defaultAssigneeId} members={members} canManage={canManage} onSave={save} onDelete={editing ? remove : undefined} onClose={() => setEditing(undefined)} />}
  </section>
}

function PlanRow({ plan, onOpen }: { plan: MonthlyPlan; onOpen: () => void }) {
  const status = monthPlanStatus(plan)
  const tone = STATUS_STYLE[status]
  const dateText = plan.start_date && plan.due_date ? `${plan.start_date} 至 ${plan.due_date}` : '未设置日期'
  const note = plan.progress_note || plan.risk_dependency || '暂无进展说明'
  return <button type="button" onClick={onOpen} className="grid w-full grid-cols-[5px_minmax(0,1fr)] gap-3 px-1 py-4 text-left hover:bg-slate-50"><span className={`rounded-full ${tone.rail}`} aria-hidden="true" /><span className="min-w-0"><span className="flex flex-wrap items-start justify-between gap-2"><strong className="text-sm font-medium text-slate-800">{plan.title}</strong><span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${tone.badge}`}>{status}</span></span><span className="mt-1 block text-xs leading-5 text-slate-600">预期产出：{plan.expected_output}</span><span className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-400"><span>负责人：{plan.assignee}</span><span>{dateText}</span><span>{note}</span></span></span></button>
}
