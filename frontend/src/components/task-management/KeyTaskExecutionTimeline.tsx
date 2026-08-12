import { useMemo, useState } from 'react'
import type { SubTaskDetail } from '../../api/subtasks'
import type { WorkReportEntryIntent } from '../../domain/workReportEntry'

type EventKind = 'report' | 'achievement' | 'issue' | 'meeting'
type Filter = 'all' | EventKind

type ExecutionEvent = {
  id: string
  kind: EventKind
  title: string
  summary: string
  actor: string
  createdAt: string | null
}

type Props = {
  subTask: SubTaskDetail
  onEntry: (intent: WorkReportEntryIntent) => void
}

const FILTERS: Array<{ value: Filter; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'report', label: '工作汇报' },
  { value: 'achievement', label: '成果' },
  { value: 'issue', label: '问题' },
  { value: 'meeting', label: '会议纪要' },
]

const KIND_STYLE: Record<EventKind, { badge: string; icon: string }> = {
  report: { badge: '工作汇报', icon: 'text-blue-600 bg-blue-50' },
  achievement: { badge: '成果', icon: 'text-emerald-600 bg-emerald-50' },
  issue: { badge: '问题', icon: 'text-red-600 bg-red-50' },
  meeting: { badge: '会议纪要', icon: 'text-violet-600 bg-violet-50' },
}

export function KeyTaskExecutionTimeline({ subTask, onEntry }: Props) {
  const [filter, setFilter] = useState<Filter>('all')
  const events = useMemo(() => projectExecutionEvents(subTask), [subTask])
  const visible = filter === 'all' ? events : events.filter((event) => event.kind === filter)

  return <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold text-slate-900">执行过程</h2><button type="button" onClick={() => onEntry('report')} className="rounded-lg border border-blue-200 bg-white px-4 py-2 text-xs font-semibold text-blue-600 hover:bg-blue-50">＋ 提交工作汇报</button></div>
    <div className="mt-3 flex gap-6 overflow-x-auto border-b border-slate-200" role="tablist" aria-label="执行过程类型">{FILTERS.map((item) => <button key={item.value} type="button" role="tab" aria-selected={filter === item.value} onClick={() => setFilter(item.value)} className={`shrink-0 border-b-2 px-1 py-2 text-xs font-medium ${filter === item.value ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>{item.label}</button>)}</div>
    <div className="mt-2">{visible.length ? visible.map((event) => <ExecutionRow key={event.id} event={event} />) : <div className="py-10 text-center"><p className="text-sm font-medium text-slate-600">暂无{FILTERS.find((item) => item.value === filter)?.label === '全部' ? '执行记录' : FILTERS.find((item) => item.value === filter)?.label}</p><p className="mt-1 text-xs text-slate-400">负责人提交后会在这里形成关键任务执行过程</p></div>}</div>
  </section>
}

function ExecutionRow({ event }: { event: ExecutionEvent }) {
  const tone = KIND_STYLE[event.kind]
  return <article className="grid grid-cols-[74px_34px_minmax(0,1fr)] items-center gap-3 border-b border-slate-100 px-1 py-4 last:border-b-0 sm:grid-cols-[90px_38px_minmax(0,1fr)_auto]">
    <time className="text-[11px] leading-5 text-slate-500">{dateParts(event.createdAt).map((part) => <span key={part} className="block">{part}</span>)}</time>
    <span className={`grid size-8 place-items-center rounded-full text-xs font-bold ${tone.icon}`} aria-hidden="true">{event.kind === 'report' ? '报' : event.kind === 'achievement' ? '果' : event.kind === 'issue' ? '问' : '会'}</span>
    <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold text-slate-800">{tone.badge}</h3>{event.actor && <span className="text-xs text-slate-400">来自{event.actor}</span>}</div><p className="mt-1 truncate text-xs text-slate-600">{event.title && event.title !== tone.badge ? `${event.title}：` : ''}{event.summary || '暂无摘要'}</p></div>
    <button type="button" className="hidden text-xs font-medium text-blue-600 sm:block">查看详情 ›</button>
  </article>
}

function projectExecutionEvents(subTask: SubTaskDetail): ExecutionEvent[] {
  const workReports = subTask.work_reports ?? []
  const achievements = subTask.related_achievements ?? []
  const issues = subTask.related_issues ?? []
  const meetings: ExecutionEvent[] = subTask.source_submission?.source_type?.includes('meeting') ? [{
    id: `meeting-${subTask.source_submission.id}`,
    kind: 'meeting',
    title: subTask.source_submission.title || '会议纪要',
    summary: subTask.source_submission.summary || subTask.source_submission.transcript_text || '',
    actor: subTask.source_submission.submitter || '',
    createdAt: subTask.source_submission.created_at,
  }] : []
  return [
    ...workReports.map((report): ExecutionEvent => ({
      id: `report-${report.id}`,
      kind: 'report',
      title: '工作汇报',
      summary: report.completed_items[0] || report.next_steps[0] || '已提交工作汇报',
      actor: report.submitter || '',
      createdAt: report.created_at,
    })),
    ...achievements.map((achievement): ExecutionEvent => ({
      id: `achievement-${achievement.id}`,
      kind: 'achievement',
      title: achievement.name || '成果',
      summary: [achievement.achievement_type, achievement.version].filter(Boolean).join(' · '),
      actor: achievement.owner || '',
      createdAt: achievement.created_at,
    })),
    ...issues.map((issue): ExecutionEvent => ({
      id: `issue-${issue.id}`,
      kind: 'issue',
      title: issue.issue_type || '问题',
      summary: issue.description,
      actor: issue.owner || '',
      createdAt: issue.created_at,
    })),
    ...meetings,
  ].sort((left, right) => (right.createdAt || '').localeCompare(left.createdAt || ''))
}

function dateParts(value: string | null) {
  if (!value) return ['日期未记录']
  const normalized = value.replace('T', ' ')
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return [normalized.slice(0, 10), normalized.slice(11, 16)]
  return [`${date.getMonth() + 1}月${String(date.getDate()).padStart(2, '0')}日`, normalized.slice(11, 16)]
}
