import type { LatestKeyTaskSubmission } from '../../api/keyTaskWorkspace'
import { formatDateTime } from './workspaceFormat'

export function CurrentProgressCard({ progress }: { progress: LatestKeyTaskSubmission | null }) {
  return <section className="rounded-xl border border-slate-200 border-l-4 border-l-blue-700 bg-white p-5 shadow-sm" aria-label="关键任务最新提交">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 className="text-base font-bold text-slate-900">最新提交</h2>
      {progress && <p className="text-xs text-slate-500">{progress.submitter || '未记录提交人'} · {formatDateTime(progress.confirmed_at)}</p>}
    </div>
    {!progress
      ? <div className="mt-3 rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-sm leading-6 text-slate-600"><p>还没有已确认的工作提交。</p><p className="mt-1">提交并确认后的最新内容会同步显示在工作推进表中。</p></div>
      : <div className="mt-3">
        <p className="whitespace-pre-wrap text-sm leading-6 text-slate-800">{progress.summary || '本次提交暂无摘要'}</p>
        {progress.next_step && <p className="mt-3 border-t border-slate-100 pt-3 text-sm leading-6 text-slate-700"><span className="font-semibold">下一步计划：</span>{progress.next_step}</p>}
      </div>}
  </section>
}
