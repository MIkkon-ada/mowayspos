import { useMemo } from 'react'
import type { ExecutionPlan, ExecutionEvent, KeyTaskWorkspace } from '../../api/keyTaskWorkspace'
import { DetailDrawer } from '../DetailDrawer'
import { formatDateTime, formatPlanTime, sourceLabel, statusTone } from './workspaceFormat'

type Props = { plan: ExecutionPlan | null; open: boolean; onClose: () => void; workspace: KeyTaskWorkspace; onSubmitUpdate?: () => void; onEdit?: (plan: ExecutionPlan) => void; onMarkCompleted?: (plan: ExecutionPlan) => void }

export function ExecutionPlanDetailDrawer({ plan, open, onClose, workspace, onSubmitUpdate, onEdit, onMarkCompleted }: Props) {
  const events = useMemo<ExecutionEvent[]>(() => plan ? workspace.timeline.filter((event) => event.execution_plan_id === plan.id) : [], [plan, workspace.timeline])
  if (!plan) return null

  return <DetailDrawer open={open} onClose={onClose} title="任务计划详情">
    <div className="space-y-4 text-sm text-slate-700">
      <section>
        <div className="flex flex-wrap items-start gap-2"><h3 className="min-w-0 flex-1 text-lg font-semibold leading-7 text-slate-900">{plan.title}</h3><span className={`shrink-0 rounded-md px-2 py-1 text-xs font-medium ${statusTone(plan.status)}`}>{plan.status || '未开始'}</span></div>
        <dl className="mt-4 grid overflow-hidden rounded-xl border border-slate-200 bg-white sm:grid-cols-3 sm:divide-x sm:divide-slate-200"><Field label="负责人" value={plan.assignee || '未指定'} compact /><Field label="协助人" value={plan.collaborators.length ? plan.collaborators.join('、') : '—'} compact /><Field label="计划时间" value={formatPlanTime(plan)} compact /></dl>
      </section>
      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white"><Field label="预期成果" value={plan.expected_output || '—'} multiline card /><div className="border-t border-slate-100" /><Field label="完成定义" value={plan.completion_criteria || '—'} multiline card /></section>
      <section className="rounded-xl border border-slate-200 bg-white"><Field label="当前进展" value={plan.latest_progress || plan.progress_note || '暂无正式更新'} multiline card /></section>
      <section className="rounded-xl border border-slate-200 bg-white p-4"><h4 className="font-semibold text-slate-900">推进记录</h4>{events.length === 0 ? <p className="mt-2 text-slate-500">暂无已确认记录</p> : <ol className="mt-3 space-y-3 border-l border-blue-200 pl-4">{events.map((event) => <li key={event.id}><p className="font-medium text-slate-800">{sourceLabel(event)} · {event.actor.name || '—'}</p><p className="mt-1 text-slate-600">{event.progress_summary || '计划状态已更新'}</p><time className="mt-1 block text-xs text-slate-400">{formatDateTime(event.occurred_at)}</time></li>)}</ol>}</section>
      {(workspace.permissions.can_submit_update || workspace.permissions.can_operate) && <footer className="sticky bottom-0 -mx-6 flex flex-wrap gap-2 border-t border-slate-200 bg-white px-6 py-4 shadow-[0_-8px_16px_-16px_rgba(15,23,42,0.45)]">{workspace.permissions.can_submit_update && <button type="button" onClick={onSubmitUpdate} className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700">提交更新</button>}{workspace.permissions.can_operate && <button type="button" onClick={() => onEdit?.(plan)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">编辑计划</button>}{workspace.permissions.can_operate && plan.status !== '已完成' && <button type="button" onClick={() => onMarkCompleted?.(plan)} className="rounded-lg border border-emerald-300 px-3 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-50">标记完成</button>}</footer>}
    </div>
  </DetailDrawer>
}

function Field({ label, value, multiline = false, compact = false, card = false }: { label: string; value: string; multiline?: boolean; compact?: boolean; card?: boolean }) {
  return <div className={card ? 'p-4' : compact ? 'p-4' : ''}><dt className="text-xs font-medium text-slate-500">{label}</dt><dd className={multiline ? 'mt-2 whitespace-pre-wrap leading-6 text-slate-700' : 'mt-1.5 text-slate-800'}>{value}</dd></div>
}
