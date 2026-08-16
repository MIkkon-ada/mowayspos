import type { ExecutionEvent, ExecutionPlan, KeyTaskWorkspace } from '../../api/keyTaskWorkspace'

export function formatDate(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}

export function formatDateTime(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export function formatPlanTime(item: Pick<ExecutionPlan, 'start_date' | 'due_kind' | 'due_date' | 'due_label'>) {
  const start = formatDate(item.start_date)
  if (item.due_kind === 'exact') return `${start} → ${formatDate(item.due_date)}`
  if (item.due_kind === 'fuzzy') return `${start} → ${item.due_label || '预计时间待补充'}`
  return `${start} → 暂未确定`
}

export function formatKeyTaskPlanTime(item: KeyTaskWorkspace['key_task']) {
  if (item.start_date || item.due_kind !== 'unknown') return formatPlanTime(item)
  return item.plan_time || '暂未确定'
}

export function sourceLabel(event: Pick<ExecutionEvent, 'source_type' | 'source_label'>) {
  return event.source_label || ({ work_submission: '工作提交', meeting_progress_review: '会议纪要', achievement: '成果', issue: '问题', execution_plan: '计划变更', key_task: '关键任务变更' }[event.source_type] || '执行事件')
}

export function statusTone(status?: string) {
  if (status === '已完成') return 'bg-emerald-50 text-emerald-700'
  if (status === '进行中') return 'bg-blue-50 text-blue-700'
  if (status === '已取消' || status === '暂缓') return 'bg-slate-100 text-slate-600'
  if (status === '延期') return 'bg-amber-50 text-amber-700'
  return 'bg-slate-100 text-slate-600'
}
