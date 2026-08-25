import type { CurrentProgress } from '../../api/keyTaskWorkspace'
import { formatDateTime, sourceLabel } from './workspaceFormat'

export function CurrentProgressCard({ progress }: { progress: CurrentProgress | null }) {
  return <section className="rounded-lg border border-slate-300 border-l-4 border-l-blue-700 bg-white p-5 shadow-sm" aria-label="当前进展">
    <h2 className="text-lg font-semibold text-slate-900">⌁　当前进展</h2>
    {!progress ? <div className="mt-4 grid min-h-28 place-items-center border border-dashed border-slate-300 bg-slate-50 px-6 text-center text-sm leading-6 text-slate-500"><div><p className="mb-2 text-2xl text-slate-300">▣</p>暂无已确认的有效推进事实。会议 AI 候选内容需经人工确认并正式回填后，才会显示在这里。</div></div> : <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_320px]">
      <div><p className="whitespace-pre-wrap text-sm leading-6 text-slate-700">{progress.progress_summary}</p><div className="mt-4 border-t border-slate-200 pt-4 text-sm"><span className="font-semibold text-slate-800">下一步：</span><span className="text-slate-600">{progress.next_step || '暂未记录'}</span></div></div>
      <dl className="space-y-2 rounded-lg border border-blue-100 bg-blue-50/40 p-4 text-sm text-slate-600"><div><dt className="inline text-slate-400">来源类型： </dt><dd className="inline font-medium text-blue-700">{sourceLabel({ source_type: progress.source_type, source_label: progress.source_label })}</dd></div><div><dt className="inline text-slate-400">来源对象： </dt><dd className="inline">#{progress.source_id}</dd></div><div><dt className="inline text-slate-400">提交/确认人： </dt><dd className="inline">{progress.actor.name || '—'}</dd></div><div><dt className="inline text-slate-400">生效时间： </dt><dd className="inline">{formatDateTime(progress.effective_at)}</dd></div></dl>
    </div>}
  </section>
}
