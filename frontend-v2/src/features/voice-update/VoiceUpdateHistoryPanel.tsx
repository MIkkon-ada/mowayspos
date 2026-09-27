import type { UpdateHistoryItem } from '../../api/updates'
import * as SS from '../../domain/submissionStatus'
import { fmtShort } from '../../utils/time'

type VoiceUpdateHistoryPanelProps = {
  history: UpdateHistoryItem[]
  currentUserName?: string
  onSelectUpdate: (id: number) => void
}

export function VoiceUpdateHistoryPanel({ history, currentUserName, onSelectUpdate }: VoiceUpdateHistoryPanelProps) {
  const myHistory = history.filter((item) => item.submitter === currentUserName)

  return (
    <div className="bg-white rounded-2xl border flex-shrink-0" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
      <div className="flex items-center justify-between px-5 py-3 border-b" style={{ borderColor: '#E9EFF6' }}>
        <h3 className="text-sm font-bold text-slate-700">我的提交记录</h3>
        <span className="text-xs text-slate-400">{myHistory.length} 条 · 点击查看流转状态</span>
      </div>
      {myHistory.length === 0 ? (
        <div className="py-6 text-center text-xs text-slate-400">暂无提交记录</div>
      ) : (
        <div className="overflow-y-auto" style={{ maxHeight: 240 }}>
          {myHistory.slice(0, 8).map((item) => {
            const key = SS.normalize(item.confirm_status)
            const label = SS.DISPLAY_LABEL[key] ?? item.confirm_status ?? '-'
            const cls   = SS.STATUS_BADGE_CLASS[key] ?? 'bg-slate-100 text-slate-500'
            const dot   = SS.STATUS_DOT_COLOR[key]   ?? '#94A3B8'
            const summary = (() => {
              try {
                return JSON.parse(item.ai_result_json || '{}').summary || item.transcript_text
              } catch {
                return item.transcript_text
              }
            })()
            const time = fmtShort(item.created_at)
            return (
              <div
                key={item.id}
                className="flex items-center gap-3 px-5 py-2.5 border-b last:border-b-0 hover:bg-sky-50 transition-colors group cursor-pointer"
                style={{ borderColor: '#F8FAFC' }}
                onClick={() => onSelectUpdate(item.id)}
              >
                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: dot }} />
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-slate-700 truncate">{summary || '—'}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{item.source_type} · {time}</p>
                </div>
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold flex-shrink-0 ${cls}`}>
                  {label}
                </span>
                <svg className="opacity-0 group-hover:opacity-60 flex-shrink-0" style={{ width: 12, height: 12, color: '#64748B' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                </svg>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
