import type { IssueItem } from '../../types'

type Props = { issues: IssueItem[]; loading: boolean; onOpen: (issue: IssueItem) => void }

function tone(issue: IssueItem) {
  const value = `${issue.priority || ''}${issue.status || ''}`
  if (value.includes('高') || value.includes('决策')) return 'border-red-200 bg-red-50/50'
  if (value.includes('中') || value.includes('协调') || value.includes('待处理')) return 'border-amber-200 bg-amber-50/50'
  return 'border-emerald-200 bg-emerald-50/40'
}

export function MobileIssueList({ issues, loading, onOpen }: Props) {
  if (loading) return <div className="px-4 py-10 text-center text-sm text-slate-400">加载中...</div>
  if (!issues.length) return <div className="px-4 py-10 text-center text-sm text-slate-400">当前没有风险事项</div>
  return <section className="space-y-3 px-4 pb-24" aria-label="风险事项">
    {issues.map((issue) => <button type="button" key={issue.id} onClick={() => onOpen(issue)} className={`w-full rounded-2xl border p-4 text-left shadow-sm ${tone(issue)}`}>
      <div className="flex items-start justify-between gap-3"><h2 className="min-w-0 text-sm font-bold leading-5 text-slate-800">{issue.description || '未命名问题'}</h2><span className="shrink-0 rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-semibold text-slate-600">{issue.status || '待处理'}</span></div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500"><span>负责人：{issue.owner || '—'}</span><span>截止：{issue.expected_resolve_time || '—'}</span><span className="col-span-2">最近更新：{issue.updated_at?.slice(0, 16).replace('T', ' ') || '—'}</span></div>
    </button>)}
  </section>
}
