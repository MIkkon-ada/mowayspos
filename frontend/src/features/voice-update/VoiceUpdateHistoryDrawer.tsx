import { useMemo, useState } from 'react'
import type { UpdateHistoryItem } from '../../api/updates'
import * as SS from '../../domain/submissionStatus'
import { fmtShort } from '../../utils/time'

type HistoryFilter = '全部' | '草稿' | '已提交' | '已退回'

type VoiceUpdateHistoryDrawerProps = {
  open: boolean
  selectedProjectId: number | null
  history: UpdateHistoryItem[]
  currentUserName?: string
  onClose: () => void
  onSelectUpdate: (id: number) => void
}

function historySummary(item: UpdateHistoryItem): string {
  try {
    const parsed = JSON.parse(item.ai_result_json || '{}') as { summary?: string }
    return parsed.summary || item.title || item.transcript_text || '未命名汇报'
  } catch {
    return item.title || item.transcript_text || '未命名汇报'
  }
}

function matchesHistoryFilter(item: UpdateHistoryItem, filter: HistoryFilter): boolean {
  if (filter === '全部') return true
  const status = SS.normalize(item.confirm_status)
  if (filter === '草稿') return item.confirm_status === '草稿'
  if (filter === '已退回') return SS.RETURNED_TO_SUBMITTER.has(status)
  return item.confirm_status !== '草稿' && !SS.RETURNED_TO_SUBMITTER.has(status)
}

export function VoiceUpdateHistoryDrawer({
  open,
  selectedProjectId,
  history,
  currentUserName,
  onClose,
  onSelectUpdate,
}: VoiceUpdateHistoryDrawerProps) {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<HistoryFilter>('全部')
  const rows = useMemo(() => {
    const keyword = search.trim().toLocaleLowerCase('zh-CN')
    return history
      .filter((item) => item.submitter === currentUserName)
      .filter((item) => matchesHistoryFilter(item, filter))
      .filter((item) => !keyword || `${historySummary(item)} ${item.source_type}`.toLocaleLowerCase('zh-CN').includes(keyword))
  }, [currentUserName, filter, history, search])

  if (!open) return null

  return (
    <div className="voice-update-drawer-backdrop" onClick={onClose}>
      <aside className="voice-update-drawer voice-update-history-drawer" onClick={(event) => event.stopPropagation()} aria-label="历史汇报">
        <header className="voice-update-drawer-header">
          <div><p>项目记录</p><h2>历史汇报</h2></div>
          <button type="button" onClick={onClose} aria-label="关闭历史汇报">×</button>
        </header>
        {!selectedProjectId ? (
          <div className="voice-update-drawer-state">请先选择所属项目</div>
        ) : (
          <div className="voice-update-history-body">
            <label className="voice-update-history-search">
              <span aria-hidden="true">⌕</span>
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索历史汇报内容" />
            </label>
            <div className="voice-update-history-filters" role="tablist" aria-label="历史汇报状态">
              {(['全部', '草稿', '已提交', '已退回'] as HistoryFilter[]).map((item) => (
                <button key={item} type="button" role="tab" aria-selected={filter === item} className={filter === item ? 'is-active' : ''} onClick={() => setFilter(item)}>{item}</button>
              ))}
            </div>
            <div className="voice-update-history-list">
              {rows.length === 0 ? <p className="voice-update-history-empty">暂无符合条件的汇报</p> : rows.map((item) => {
                const status = SS.normalize(item.confirm_status)
                const label = item.confirm_status === '草稿' ? '草稿' : SS.DISPLAY_LABEL[status] ?? item.confirm_status
                return (
                  <button
                    type="button"
                    className="voice-update-history-item"
                    key={item.id}
                    onClick={() => { onClose(); onSelectUpdate(item.id) }}
                  >
                    <span className="voice-update-history-summary">{historySummary(item)}</span>
                    <span>{fmtShort(item.created_at)} · {item.source_type}</span>
                    <em className={SS.STATUS_BADGE_CLASS[status] ?? 'bg-slate-100 text-slate-600'}>{label}</em>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </aside>
    </div>
  )
}
