import { useMemo, useState, type ReactNode } from 'react'
import type { MeetingItem } from '../../types'
import { STATUS_CONFIG, fmtTime, getStatus, type PublishStatus } from './meetingUtils'

type DetailTab = 'minutes' | 'todos' | 'tracking' | 'resources'
type DecisionSection = { title: string; bullets: string[] }
type ActionRow = { code: string; task: string; owner: string; tracker: string; dueDate: string; source: string }
type TrackingRow = { code: string; task: string; owner: string; status: string; progress: string }

function listFromJson(raw?: string): string[] {
  if (!raw) return []
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.map((item) => {
      if (typeof item === 'string') return item.trim()
      if (item && typeof item === 'object') {
        const row = item as Record<string, unknown>
        return String(row.title ?? row.content ?? row.name ?? row.task ?? '').trim()
      }
      return ''
    }).filter(Boolean)
  } catch {
    return []
  }
}

function recordsFromJson(raw?: string): Record<string, string>[] {
  if (!raw) return []
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.flatMap((item) => {
      if (typeof item === 'string' && item.trim()) return [{ task: item.trim() }]
      if (!item || typeof item !== 'object') return []
      return [Object.fromEntries(Object.entries(item as Record<string, unknown>).map(([key, value]) => [key, String(value ?? '').trim()]))]
    })
  } catch {
    return []
  }
}

function pick(row: Record<string, string>, ...keys: string[]) {
  return keys.map((key) => row[key]).find(Boolean) ?? '—'
}

function actionRowsFromJson(raw?: string): ActionRow[] {
  return recordsFromJson(raw).map((row, index) => ({
    code: pick(row, '编号', 'code', 'id') === '—' ? `本周-${String(index + 1).padStart(2, '0')}` : pick(row, '编号', 'code', 'id'),
    task: pick(row, '会议安排事项', '事项', 'task', 'title', 'content'),
    owner: pick(row, '负责人', 'owner'),
    tracker: pick(row, '追踪人', 'tracker'),
    dueDate: pick(row, '完成时限', '完成时间', 'due_date', 'dueDate'),
    source: pick(row, '来源/备注', '来源', '备注', 'source', 'note'),
  }))
}

function trackingRowsFromJson(raw?: string): TrackingRow[] {
  return recordsFromJson(raw).map((row, index) => ({
    code: pick(row, '编号', 'code', 'id') === '—' ? `上周-${String(index + 1).padStart(2, '0')}` : pick(row, '编号', 'code', 'id'),
    task: pick(row, '上周事项', '事项', 'task', 'title', 'content'),
    owner: pick(row, '负责人', 'owner'),
    status: pick(row, '状态', 'status'),
    progress: pick(row, '本周进展/说明', '本周进展', '说明', 'progress'),
  }))
}

function decisionSectionsFromJson(raw?: string, fallback?: string | null): DecisionSection[] {
  if (!raw) return fallback?.trim() ? [{ title: '会议小结', bullets: [fallback.trim()] }] : []
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.map((item, index) => {
      if (typeof item === 'string') return { title: item.trim(), bullets: [] }
      if (!item || typeof item !== 'object') return null
      const row = item as Record<string, unknown>
      const candidates = row.bullets ?? row.points ?? row.items ?? row.content
      const bullets = Array.isArray(candidates)
        ? candidates.map((entry) => String(entry).trim()).filter(Boolean)
        : candidates ? [String(candidates).trim()] : []
      const title = String(row.title ?? row.heading ?? row.topic ?? row.name ?? `决议 ${index + 1}`).trim()
      return title || bullets.length ? { title, bullets } : null
    }).filter((section): section is DecisionSection => Boolean(section))
  } catch {
    return fallback?.trim() ? [{ title: '会议小结', bullets: [fallback.trim()] }] : []
  }
}

function EmptyPanel({ children }: { children: string }) {
  return <div className="rounded-xl border border-dashed border-slate-200 bg-white px-5 py-16 text-center text-sm text-slate-400">{children}</div>
}

function MinutesTable({ children }: { children: ReactNode }) {
  return <div className="overflow-x-auto rounded-xl border border-slate-100"><table className="min-w-[820px] w-full text-sm">{children}</table></div>
}

export function MeetingDetailWorkspace({
  meeting,
  projectName,
  projectArchived,
  actionLoading,
  onBack,
  onEdit,
  onStatusChange,
}: {
  meeting: MeetingItem
  projectName: string
  projectArchived: boolean
  actionLoading: boolean
  onBack: () => void
  onEdit: () => void
  onStatusChange: (status: PublishStatus) => void
}) {
  const [activeTab, setActiveTab] = useState<DetailTab>('minutes')
  const [showAllDecisions, setShowAllDecisions] = useState(false)
  const status = getStatus(meeting)
  const statusConfig = STATUS_CONFIG[status]
  const agendaItems = useMemo(() => listFromJson(meeting.agenda_items_json), [meeting.agenda_items_json])
  const decisionSections = useMemo(() => decisionSectionsFromJson(meeting.decision_items_json, meeting.summary), [meeting.decision_items_json, meeting.summary])
  const currentActions = useMemo<ActionRow[]>(() => actionRowsFromJson(meeting.task_list_json), [meeting.task_list_json])
  const trackingRows = useMemo<TrackingRow[]>(() => trackingRowsFromJson(meeting.prior_action_items_json), [meeting.prior_action_items_json])
  const visibleDecisions = showAllDecisions ? decisionSections : decisionSections.slice(0, 2)
  const tabs: { id: DetailTab; label: string; count?: number }[] = [
    { id: 'minutes', label: '会议纪要' },
    { id: 'todos', label: '本周待办', count: currentActions.length || undefined },
    { id: 'tracking', label: '上周追踪' },
    { id: 'resources', label: '相关资料' },
  ]

  return (
    <section className="mx-auto w-full max-w-[1180px]">
      <div className="flex items-center gap-2 text-xs text-slate-400">
        <button type="button" onClick={onBack} className="hover:text-sky-600">会议列表</button>
        <span>/</span>
        <span className="text-slate-600">会议详情</span>
      </div>

      <header className="mt-4 rounded-xl border border-slate-200 bg-white px-6 py-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="truncate text-2xl font-semibold text-slate-800">{meeting.title || '未命名会议'}</h1>
              <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusConfig.cls}`}>{statusConfig.label}</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-500">
              <span>{fmtTime(meeting.meeting_date)}</span>
              <span>项目：{projectName || '—'}</span>
              <span>主持人：{meeting.host || '—'}</span>
              <span>参会人员：{meeting.participants || '—'}</span>
              <span>会议地点：{meeting.location || '—'}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={onEdit} disabled={projectArchived} className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:border-sky-300 hover:text-sky-600 disabled:cursor-not-allowed disabled:opacity-50">编辑</button>
            <button type="button" onClick={() => window.print()} className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:border-sky-300 hover:text-sky-600">导出</button>
            <details className="relative">
              <summary className="cursor-pointer list-none rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:border-sky-300 hover:text-sky-600">更多⌄</summary>
              <div className="absolute right-0 z-10 mt-2 w-28 rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
                {status !== 'published' && <button type="button" disabled={projectArchived || actionLoading} onClick={() => onStatusChange('published')} className="w-full rounded px-3 py-2 text-left text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50">发布</button>}
                {status !== 'returned' && <button type="button" disabled={projectArchived || actionLoading} onClick={() => onStatusChange('returned')} className="w-full rounded px-3 py-2 text-left text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50">退回</button>}
              </div>
            </details>
          </div>
        </div>
      </header>

      <div className="mt-4 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <nav className="flex overflow-x-auto border-b border-slate-100 px-5" aria-label="会议详情页签">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`shrink-0 border-b-2 px-5 py-3.5 text-sm transition ${activeTab === tab.id ? 'border-sky-500 font-semibold text-sky-600' : 'border-transparent font-normal text-slate-500 hover:text-slate-700'}`}
            >
              {tab.label}{tab.count ? ` ${tab.count}` : ''}
            </button>
          ))}
        </nav>

        <div className="p-7">
          {activeTab === 'minutes' && (
            <article className="mx-auto max-w-[980px] text-sm leading-7 text-slate-600">
              <section>
                <h2 className="text-lg font-semibold text-slate-800">一、会议议程</h2>
                {agendaItems.length ? <ol className="mt-4 space-y-2 pl-6">{agendaItems.map((item, index) => <li key={`${item}-${index}`} className="pl-1">{item}</li>)}</ol> : <p className="mt-4 text-slate-400">暂无会议议程</p>}
              </section>

              <section className="mt-7 border-t border-dashed border-slate-200 pt-7">
                <h2 className="text-lg font-semibold text-slate-800">二、会议小结与决议</h2>
                {visibleDecisions.length ? (
                  <div className="mt-4 divide-y divide-dashed divide-slate-200">
                    {visibleDecisions.map((section, index) => (
                      <div key={`${section.title}-${index}`} className="py-4 first:pt-0">
                        <h3 className="font-medium text-slate-800">（{['一', '二', '三', '四', '五', '六'][index] ?? index + 1}）{section.title}</h3>
                        {section.bullets.length ? <ul className="mt-2 space-y-1.5">{section.bullets.map((bullet, bulletIndex) => <li key={`${bullet}-${bulletIndex}`} className="flex gap-2"><span aria-hidden="true">·</span><span>{bullet}</span></li>)}</ul> : null}
                      </div>
                    ))}
                  </div>
                ) : <p className="mt-4 text-slate-400">暂无会议小结与决议</p>}
                {decisionSections.length > 2 && <button type="button" onClick={() => setShowAllDecisions((shown) => !shown)} className="mt-4 text-sm font-medium text-sky-600 hover:text-sky-700">{showAllDecisions ? '收起决议' : `查看全部 ${decisionSections.length} 个决议`} ›</button>}
              </section>

              <footer className="mt-8 border-t border-slate-200 pt-4 text-sm text-slate-500">整理人：{meeting.organizer || '—'} <span className="mx-6">抄送：{meeting.copied_to || '—'}</span></footer>
            </article>
          )}

          {activeTab === 'todos' && (currentActions.length ? (
            <section>
              <h2 className="mb-4 text-base font-semibold text-slate-800">本周新增待办事项</h2>
              <MinutesTable><thead><tr className="bg-slate-50 text-left text-xs font-medium text-slate-500">{['编号', '会议安排事项', '负责人', '追踪人', '完成时限', '来源/备注'].map((label) => <th key={label} className="whitespace-nowrap px-4 py-3">{label}</th>)}</tr></thead><tbody>{currentActions.map((item) => <tr key={item.code} className="border-t border-slate-100 text-slate-700"><td className="px-4 py-3">{item.code}</td><td className="min-w-[260px] px-4 py-3">{item.task}</td><td className="px-4 py-3">{item.owner}</td><td className="px-4 py-3">{item.tracker}</td><td className="px-4 py-3">{item.dueDate}</td><td className="px-4 py-3">{item.source}</td></tr>)}</tbody></MinutesTable>
            </section>
          ) : <EmptyPanel>暂无本周待办</EmptyPanel>)}

          {activeTab === 'tracking' && (
            <section>
              <h2 className="mb-4 text-base font-semibold text-slate-800">上周待办追踪</h2>
              <MinutesTable><thead><tr className="bg-slate-50 text-left text-xs font-medium text-slate-500">{['编号', '上周事项', '负责人', '状态', '本周进展/说明'].map((label) => <th key={label} className="whitespace-nowrap px-4 py-3">{label}</th>)}</tr></thead><tbody>{trackingRows.length ? trackingRows.map((item) => <tr key={item.code} className="border-t border-slate-100 text-slate-700"><td className="px-4 py-3">{item.code}</td><td className="min-w-[280px] px-4 py-3">{item.task}</td><td className="px-4 py-3">{item.owner}</td><td className="px-4 py-3">{item.status}</td><td className="px-4 py-3">{item.progress}</td></tr>) : <tr className="border-t border-slate-100"><td colSpan={5} className="px-4 py-12 text-center text-slate-400">暂无上周追踪数据</td></tr>}</tbody></MinutesTable>
            </section>
          )}
          {activeTab === 'resources' && <EmptyPanel>暂无相关资料</EmptyPanel>}
        </div>
      </div>
    </section>
  )
}
