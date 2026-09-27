import type { ExecutionPlan, KeyTaskWorkspace } from '../../api/keyTaskWorkspace'
import { formatPlanTime, statusTone } from './workspaceFormat'

type Props = {
  plans: ExecutionPlan[]
  summary: KeyTaskWorkspace['plan_summary']
  canManage: boolean
  onAdd: () => void
  onOpen: (plan: ExecutionPlan) => void
}

export function ExecutionPlanSidebar({ plans, summary, canManage, onAdd, onOpen }: Props) {
  return <aside className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm" aria-label="关键任务计划">
    <div className="flex items-start justify-between gap-2">
      <div>
        <h2 className="text-base font-bold text-slate-900">任务计划</h2>
        {summary.total > 0 && <p className="mt-1 text-xs text-slate-500">{summary.total} 项 · 已完成 {summary.completed} · 进行中 {summary.in_progress}</p>}
      </div>
      {plans.length > 0 && canManage && <button type="button" onClick={onAdd} className="shrink-0 rounded-md px-2 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-50">新增计划</button>}
    </div>
    {plans.length === 0 ? <p className="mt-3 rounded-lg bg-slate-50 px-3 py-3 text-sm leading-6 text-slate-500">暂无任务计划。后续安排添加后会显示在这里。</p> : <ol className="mt-3 space-y-2">
      {plans.map((plan) => {
        const status = plan.display_status || plan.status || '未开始'
        return <li key={plan.id}>
          <button type="button" onClick={() => onOpen(plan)} className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-left transition-colors hover:border-blue-300 hover:bg-blue-50/50 focus:outline-none focus:ring-2 focus:ring-blue-500">
            <span className="flex flex-wrap items-start justify-between gap-2">
              <span className="min-w-0 flex-1 text-sm font-semibold leading-5 text-slate-800">{plan.title}</span>
              <span className={`shrink-0 rounded px-2 py-0.5 text-[11px] font-medium ${statusTone(status)}`}>{status}</span>
            </span>
            <span className="mt-1.5 block text-xs leading-5 text-slate-500">{formatPlanTime(plan)}{plan.assignee ? ` · ${plan.assignee}` : ''}</span>
          </button>
        </li>
      })}
    </ol>}
  </aside>
}
