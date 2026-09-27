import type { KeyTaskWorkspace } from '../../api/keyTaskWorkspace'
import { formatDateTime, statusTone } from './workspaceFormat'

export function IssueList({ items }: { items: KeyTaskWorkspace['issues'] }) {
  if (items.length === 0) return null
  return <section className="rounded-xl border border-slate-200 border-l-4 border-l-red-500 bg-white p-5 shadow-sm" aria-label="问题记录"><h2 className="text-base font-bold text-slate-900">问题记录</h2><div className="mt-3 space-y-2">{items.map((item) => <article key={item.id} className="rounded-lg border border-slate-100 bg-slate-50/70 p-3"><p className="text-sm leading-6 text-slate-800">{item.description}</p><div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500"><span className={`rounded px-2 py-0.5 font-medium ${statusTone(item.status)}`}>{item.status || '—'}</span>{item.issue_type && <span>{item.issue_type}</span>}{item.priority && <span>优先级：{item.priority}</span>}{item.owner && <span>负责人：{item.owner}</span>}<span>{formatDateTime(item.updated_at)}</span></div></article>)}</div></section>
}
