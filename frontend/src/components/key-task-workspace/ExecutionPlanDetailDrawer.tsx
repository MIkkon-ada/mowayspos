import { useMemo } from 'react'
import type { ExecutionPlan, ExecutionEvent, KeyTaskWorkspace } from '../../api/keyTaskWorkspace'
import { DetailDrawer } from '../DetailDrawer'
import { formatDateTime, formatPlanTime, sourceLabel, statusTone } from './workspaceFormat'

type Props = { plan: ExecutionPlan | null; open: boolean; onClose: () => void; workspace: KeyTaskWorkspace; onSubmitUpdate?: () => void; onEdit?: (plan: ExecutionPlan) => void; onMarkCompleted?: (plan: ExecutionPlan) => void }

export function ExecutionPlanDetailDrawer({ plan, open, onClose, workspace, onSubmitUpdate, onEdit, onMarkCompleted }: Props) {
  const events = useMemo<ExecutionEvent[]>(() => plan ? workspace.timeline.filter((event) => event.execution_plan_id === plan.id) : [], [plan, workspace.timeline])
  if (!plan) return null
  return <DetailDrawer open={open} onClose={onClose} title="任务计划详情">
    <div className="space-y-5 text-sm text-slate-700"><div><div className="flex items-center gap-2"><h3 className="text-lg font-semibold text-slate-900">{plan.title}</h3><span className={`rounded px-2 py-1 text-xs ${statusTone(plan.status)}`}>{plan.status}</span></div><dl className="mt-4 grid gap-3 sm:grid-cols-2"><Field label="负责人" value={plan.assignee || '未指定'} /><Field label="协助人" value={plan.collaborators.length ? plan.collaborators.join('、') : '—'} /><Field label="计划时间" value={formatPlanTime(plan)} /><Field label="最近更新" value={formatDateTime(plan.updated_at)} /></dl></div>
      <Field label="当前进展" value={plan.latest_progress || plan.progress_note || '暂无正式更新'} multiline /><Field label="下一步" value={events[0]?.next_step || '暂未记录'} multiline /><Field label="预期结果" value={plan.expected_output || '—'} multiline /><Field label="完成定义" value={plan.completion_criteria || '—'} multiline /><Field label="实际产出" value={plan.actual_output || '暂未记录'} multiline />
      <div className="space-y-3"><div><h4 className="font-semibold text-slate-900">关联成果</h4><p className="mt-1 text-slate-500">当前关键任务范围内共有成果 {workspace.achievements.length} 项。</p></div><div><h4 className="font-semibold text-slate-900">关联问题</h4><p className="mt-1 text-slate-500">当前关键任务范围内共有问题 {workspace.issues.length} 项。第一阶段不预设成果/问题与单项计划的关系模型。</p></div></div>
      <div><h4 className="font-semibold text-slate-900">推进记录</h4>{events.length === 0 ? <p className="mt-2 text-slate-500">暂无与该任务计划关联的已确认事件。</p> : <ol className="mt-3 space-y-3 border-l border-blue-200 pl-4">{events.map((event) => <li key={event.id}><p className="font-medium text-slate-800">{sourceLabel(event)} · {event.actor.name || '—'}</p><p className="mt-1 text-slate-600">{event.progress_summary || '计划状态已更新'}</p><time className="mt-1 block text-xs text-slate-400">{formatDateTime(event.occurred_at)}</time></li>)}</ol>}</div>
      {(workspace.permissions.can_submit_update || workspace.permissions.can_operate) && <div className="flex flex-wrap gap-2 border-t border-slate-200 pt-4">{workspace.permissions.can_submit_update && <button type="button" onClick={onSubmitUpdate} className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white">提交更新</button>}{workspace.permissions.can_operate && <button type="button" onClick={() => onEdit?.(plan)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700">编辑计划</button>}{workspace.permissions.can_operate && plan.status !== '已完成' && <button type="button" onClick={() => onMarkCompleted?.(plan)} className="rounded-lg border border-emerald-300 px-3 py-2 text-sm font-medium text-emerald-700">标记完成</button>}</div>}
    </div>
  </DetailDrawer>
}

function Field({ label, value, multiline = false }: { label: string; value: string; multiline?: boolean }) { return <div><dt className="text-xs text-slate-400">{label}</dt><dd className={multiline ? 'mt-1 whitespace-pre-wrap leading-6' : 'mt-1'}>{value}</dd></div> }
