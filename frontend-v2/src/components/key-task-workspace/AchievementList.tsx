import type { KeyTaskWorkspace } from '../../api/keyTaskWorkspace'
import { downloadAchievementAttachment } from '../../api/achievements'
import { formatDateTime, statusTone } from './workspaceFormat'

function formatFileSize(size: number): string {
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export function AchievementList({ items }: { items: KeyTaskWorkspace['achievements'] }) {
  return <section className="rounded-xl border border-slate-200 border-l-4 border-l-emerald-600 bg-white p-5 shadow-sm" aria-label="成果">
    <div className="flex flex-wrap items-end justify-between gap-2">
      <h2 className="text-base font-bold text-slate-900">成果</h2>
      {items.length > 0 && <p className="text-xs text-slate-500">{items.length} 项成果</p>}
    </div>
    {items.length === 0
      ? <p className="mt-3 rounded-lg bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-600">这项关键任务还没有已关联的成果文件。</p>
      : <ul className="mt-3 divide-y divide-slate-100">
        {items.map((item) => <li key={item.id} className="py-3 first:pt-1 last:pb-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="min-w-0 flex-1 text-sm font-semibold text-slate-800">{item.name}</h3>
            <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${statusTone(item.status)}`}>{item.status || '—'}</span>
          </div>
          <p className="mt-1 text-xs text-slate-500">{[item.achievement_type, item.owner, item.version, formatDateTime(item.created_at)].filter(Boolean).join(' · ')}</p>
          {item.attachments.length > 0
            ? <ul className="mt-2 space-y-1.5">
              {item.attachments.map((attachment) => <li key={attachment.id}>
                <a href={downloadAchievementAttachment(attachment.id)} target="_blank" rel="noreferrer" className="inline-flex max-w-full items-center gap-2 text-sm font-medium text-blue-700 hover:text-blue-900 hover:underline">
                  <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h6"/></svg>
                  <span className="truncate">{attachment.original_name}</span>
                  <span className="shrink-0 text-xs font-normal text-slate-500">{formatFileSize(attachment.size_bytes)}</span>
                </a>
              </li>)}
            </ul>
            : <p className="mt-2 text-xs text-slate-500">暂未上传成果文件</p>}
        </li>)}
      </ul>}
  </section>
}
