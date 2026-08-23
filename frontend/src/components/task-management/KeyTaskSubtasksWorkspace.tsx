import { useEffect, useMemo, useState } from 'react'
import { createMonthlyPlan, deleteMonthlyPlan, fetchMonthlyPlans, updateMonthlyPlan, type MonthlyPlan, type MonthlyPlanPayload } from '../../api/monthlyPlans'
import { formatMonthLabel, monthPlanStatus, sortMonthPlans } from '../../domain/monthPlans'
import type { WorkReportEntryIntent } from '../../domain/workReportEntry'
import type { ProjectMember } from '../../types'
import { toast } from '../../utils/toast'
import { KeyTaskSubtaskDrawer } from './KeyTaskSubtaskDrawer'

type Props = {
  subtaskId: number
  defaultAssigneeId: number | null
  members: ProjectMember[]
  canManage?: boolean
  onChanged?: () => void
  onPlansLoaded?: (plans: MonthlyPlan[]) => void
  onEntry?: (intent: WorkReportEntryIntent) => void
}

const STATUS_STYLE = {
  已延期: 'bg-red-50 text-red-700',
  进行中: 'bg-emerald-50 text-emerald-700',
  暂缓: 'bg-orange-50 text-orange-700',
  未开始: 'bg-slate-100 text-slate-600',
  已完成: 'bg-emerald-50 text-emerald-700',
  已取消: 'bg-slate-100 text-slate-400',
} as const

export function KeyTaskSubtasksWorkspace({ subtaskId, defaultAssigneeId, members, canManage = false, onChanged, onPlansLoaded, onEntry }: Props) {
  const [selectedGroup, setSelectedGroup] = useState<'all' | string>('all')
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
      toast.error(error instanceof Error ? error.message : '子任务加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void refresh() }, [subtaskId])

  const monthGroups = useMemo(() => [...new Set(plans.map((plan) => plan.plan_month).filter((month): month is string => Boolean(month)))].sort(), [plans])
  const rows = useMemo(() => sortMonthPlans(selectedGroup === 'all' ? plans : plans.filter((plan) => plan.plan_month === selectedGroup)), [plans, selectedGroup])

  async function save(payload: MonthlyPlanPayload) {
    try {
      const saved = editing ? await updateMonthlyPlan(editing.id, payload) : await createMonthlyPlan(subtaskId, payload)
      const next = editing ? plans.map((plan) => plan.id === saved.id ? saved : plan) : [...plans, saved]
      setPlans(next)
      onPlansLoaded?.(next)
      toast.success(editing ? '子任务已更新' : '子任务已创建')
      onChanged?.()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '子任务保存失败')
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
      toast.success('子任务已删除')
      onChanged?.()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '子任务删除失败')
      throw error
    }
  }

  return <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2 className="text-lg font-semibold text-slate-900">子任务</h2>
      <div className="flex flex-wrap items-center gap-2">
        <select aria-label="子任务分组" value={selectedGroup} onChange={(event) => setSelectedGroup(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 outline-none focus:border-blue-500"><option value="all">全部子任务</option>{monthGroups.map((month) => <option key={month} value={month}>{formatMonthLabel(month)}</option>)}</select>
        {canManage && <button type="button" onClick={() => setEditing(null)} className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700">＋ 新增子任务</button>}
      </div>
    </div>

    <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200">
      <table className="min-w-[760px] w-full border-collapse text-left text-xs">
        <thead className="bg-slate-50 text-slate-500"><tr><th className="px-4 py-3 font-medium">状态</th><th className="px-4 py-3 font-medium">子任务事项</th><th className="px-4 py-3 font-medium">负责人</th><th className="px-4 py-3 font-medium">分组</th><th className="px-4 py-3 font-medium">时间安排</th><th className="px-4 py-3 font-medium">进度</th><th className="px-4 py-3 text-center font-medium">操作</th></tr></thead>
        <tbody className="divide-y divide-slate-100">{loading ? <tr><td colSpan={7} className="px-4 py-10 text-center text-slate-400">加载子任务中…</td></tr> : rows.length ? rows.map((plan) => <SubtaskRow key={plan.id} plan={plan} onOpen={() => setEditing(plan)} />) : <tr><td colSpan={7} className="px-4 py-10 text-center"><p className="font-medium text-slate-600">暂无子任务</p><p className="mt-1 text-slate-400">将关键任务拆成具体、可负责、可交付的事项</p></td></tr>}</tbody>
      </table>
    </div>
    <div className="mt-3 flex flex-wrap gap-4 text-[11px] text-slate-400"><span>● 未开始</span><span className="text-emerald-600">● 进行中</span><span className="text-orange-500">● 暂缓</span><span className="text-red-500">● 已延期</span><span className="text-emerald-700">● 已完成</span></div>

    {editing !== undefined && <KeyTaskSubtaskDrawer plan={editing} selectedGroup={selectedGroup} defaultAssigneeId={defaultAssigneeId} members={members} canManage={canManage} onSave={save} onDelete={editing ? remove : undefined} onEntry={onEntry} onClose={() => setEditing(undefined)} />}
  </section>
}

function SubtaskRow({ plan, onOpen }: { plan: MonthlyPlan; onOpen: () => void }) {
  const status = monthPlanStatus(plan)
  const progress = displayProgress(plan)
  const group = plan.plan_month ? formatMonthLabel(plan.plan_month).replaceAll(' ', '') : '未分月'
  const schedule = plan.start_date && plan.due_date ? `${shortDate(plan.start_date)} – ${shortDate(plan.due_date)}` : '未设置'
  return <tr className="text-slate-700 hover:bg-slate-50/70">
    <td className="px-4 py-3"><span className={`rounded-full px-2 py-1 font-semibold ${STATUS_STYLE[status]}`}>{status}</span></td>
    <td className="max-w-[280px] px-4 py-3"><button type="button" onClick={onOpen} className="text-left font-medium leading-5 text-slate-900 hover:text-blue-600">{plan.title}</button></td>
    <td className="whitespace-nowrap px-4 py-3">{plan.assignee || '未指定'}</td>
    <td className="whitespace-nowrap px-4 py-3">{group}</td>
    <td className="whitespace-nowrap px-4 py-3">{schedule}</td>
    <td className="px-4 py-3"><div className="w-20"><span>{progress}%</span><div className="mt-1 h-1 overflow-hidden rounded-full bg-slate-200"><i className="block h-full rounded-full bg-blue-600" style={{ width: `${progress}%` }} /></div></div></td>
    <td className="px-4 py-3 text-center"><button type="button" onClick={onOpen} className="font-medium text-blue-600 hover:text-blue-700">查看</button></td>
  </tr>
}

function displayProgress(plan: MonthlyPlan) {
  const explicit = plan.progress_note.match(/(?:^|\D)(\d{1,3})%/)
  if (explicit) return Math.min(100, Number(explicit[1]))
  return plan.status === '已完成' ? 100 : 0
}

function shortDate(value: string) {
  const [, month, day] = value.split('-')
  return `${Number(month)}.${Number(day)}`
}
