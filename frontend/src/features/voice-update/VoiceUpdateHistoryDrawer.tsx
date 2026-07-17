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

const HISTORY_SYMBOLIC_STATUS: Record<string, string> = {
  S_NEW: SS.S_NEW,
  S_PENDING_OWNER: SS.S_PENDING_OWNER,
  S_RETURNED: SS.S_RETURNED,
  S_WITHDRAWN: SS.S_WITHDRAWN,
  S_PERMANENTLY_REJECTED: SS.S_PERMANENTLY_REJECTED,
  S_WAITING_COORDINATOR: SS.S_WAITING_COORDINATOR,
  S_COORDINATOR_GIVEN: SS.S_COORDINATOR_GIVEN,
  S_WAITING_CEO: SS.S_WAITING_CEO,
  S_CEO_DECIDED: SS.S_CEO_DECIDED,
  S_CONFIRMED: SS.S_CONFIRMED,
  S_NEEDS_REVISION: SS.S_NEEDS_REVISION,
}

export function normalizeHistoryStatus(status: string | null | undefined): {
  status: string
  label: string
  badgeClass: string
} {
  const rawStatus = status?.trim() ?? ''
  if (rawStatus === '草稿') {
    return { status: rawStatus, label: rawStatus, badgeClass: 'bg-slate-100 text-slate-600' }
  }
  const symbolicStatus = HISTORY_SYMBOLIC_STATUS[rawStatus]
  const normalizedStatus = SS.normalize(symbolicStatus ?? rawStatus)
  const unknownSymbolicStatus = /^S_[A-Z_]+$/.test(rawStatus) && !symbolicStatus
  return {
    status: normalizedStatus,
    label: unknownSymbolicStatus ? '状态未识别' : SS.DISPLAY_LABEL[normalizedStatus] ?? (normalizedStatus || '状态未识别'),
    badgeClass: SS.STATUS_BADGE_CLASS[normalizedStatus] ?? 'bg-slate-100 text-slate-600',
  }
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
  const { status } = normalizeHistoryStatus(item.confirm_status)
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
          <h2>历史汇报</h2>
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
                const statusView = normalizeHistoryStatus(item.confirm_status)
                return (
                  <button
                    type="button"
                    className="voice-update-history-item"
                    key={item.id}
                    onClick={() => { onClose(); onSelectUpdate(item.id) }}
                  >
                    <span className="voice-update-history-summary">{historySummary(item)}</span>
                    <span>{fmtShort(item.created_at)} · {item.source_type}</span>
                    <em className={statusView.badgeClass}>{statusView.label}</em>
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
