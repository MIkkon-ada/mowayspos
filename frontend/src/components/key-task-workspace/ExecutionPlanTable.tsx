import type { ExecutionPlan, KeyTaskWorkspace } from '../../api/keyTaskWorkspace'
import { formatPlanTime, statusTone } from './workspaceFormat'

export function ExecutionPlanTable({ plans, summary, canManage, onAdd, onOpen }: {
  plans: ExecutionPlan[]
  summary: KeyTaskWorkspace['plan_summary']
  canManage: boolean
  onAdd: () => void
  onOpen: (plan: ExecutionPlan) => void
}) {
  return <section className="rounded-xl border border-slate-200 border-l-4 border-l-blue-600 bg-white p-5 shadow-sm" aria-label="任务计划">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2 className="text-lg font-semibold text-slate-900">☷　任务计划</h2>
      <p className="text-sm text-slate-600">共 {summary.total} 项　 已完成 {summary.completed}　 进行中 {summary.in_progress}　 未开始 {summary.not_started}　 延期 {summary.delayed}</p>
    </div>
    <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200">
      {plans.length === 0 ? <div className="grid min-h-48 place-items-center px-4 py-8 text-center text-sm text-slate-500"><div><p className="text-3xl text-slate-300">▣</p><p className="mt-3">尚未创建任务计划</p>{canManage && <button type="button" onClick={onAdd} className="mt-4 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-600 hover:border-blue-500 hover:text-blue-600">添加计划</button>}</div></div> : <table className="min-w-[860px] w-full table-fixed text-left text-sm"><colgroup><col className="w-28" /><col /><col className="w-32" /><col className="w-32" /><col className="w-32" /><col className="w-12" /></colgroup><thead className="bg-slate-50 text-xs font-medium text-slate-500"><tr><th className="px-4 py-3">状态</th><th className="px-4 py-3">计划事项</th><th className="px-4 py-3">负责人</th><th className="px-4 py-3">协助人</th><th className="px-4 py-3">时间</th><th className="px-2 py-3"><span className="sr-only">详情</span></th></tr></thead><tbody>{plans.map((plan) => { const displayStatus = plan.display_status || plan.status || '未开始'; return <tr key={plan.id} className="border-t border-slate-100 text-slate-700 transition-colors hover:bg-blue-50/40"><td className="px-4 py-4"><span className={`inline-flex rounded-md px-2 py-1 text-xs font-medium ${statusTone(displayStatus)}`}>{displayStatus}</span></td><td className="px-4 py-4 font-medium text-slate-900"><span className="block truncate" title={plan.title}>{plan.title}</span></td><td className="px-4 py-4 whitespace-nowrap">{plan.assignee || '未指定'}</td><td className="px-4 py-4 whitespace-nowrap text-slate-500">{plan.collaborators.length ? plan.collaborators.join('、') : '—'}</td><td className="px-4 py-4 whitespace-nowrap text-slate-600">{formatPlanTime(plan)}</td><td className="px-2 py-4 text-right"><button type="button" aria-label={`查看任务计划：${plan.title}`} onClick={() => onOpen(plan)} className="rounded-md px-2 py-1 text-xl leading-none text-slate-400 hover:bg-blue-50 hover:text-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500">›</button></td></tr>})}</tbody></table>}
    </div>
  </section>
}
