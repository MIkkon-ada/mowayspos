import { useMemo, useState } from 'react'
import type { UpdateHistoryItem } from '../../api/updates'
import * as SS from '../../domain/submissionStatus'
import { fmtShort } from '../../utils/time'

export type HistoryFilter = '全部' | '审核中' | '已退回' | '已确认'

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

export type HistorySubmissionGroup = {
  key: string
  batchId: number | null
  items: UpdateHistoryItem[]
  aggregateStatus: string
}

export function aggregateHistoryStatus(items: UpdateHistoryItem[]): string {
  const statuses = items.map((item) => normalizeHistoryStatus(item.confirm_status).status)
  if (statuses.some((status) => SS.RETURNED_TO_SUBMITTER.has(status))) return SS.S_RETURNED
  if (statuses.length > 0 && statuses.every((status) => SS.CONFIRMED_AND_STORED.has(status))) return SS.S_CONFIRMED
  if (statuses.length > 0 && statuses.every((status) => status === SS.S_WITHDRAWN)) return SS.S_WITHDRAWN
  if (statuses.length > 0 && statuses.every((status) => status === SS.S_PERMANENTLY_REJECTED)) return SS.S_PERMANENTLY_REJECTED
  return statuses[0] ?? SS.S_NEW
}

export function groupHistorySubmissions(items: UpdateHistoryItem[]): HistorySubmissionGroup[] {
  const grouped = new Map<string, UpdateHistoryItem[]>()
  for (const item of items) {
    const key = item.batch_id ?? `legacy-${item.id}`
    const groupKey = String(key)
    grouped.set(groupKey, [...(grouped.get(groupKey) ?? []), item])
  }
  return Array.from(grouped.entries()).map(([key, groupItems]) => ({
    key,
    batchId: groupItems[0]?.batch_id ?? null,
    items: groupItems.sort((left, right) => (left.batch_order ?? 0) - (right.batch_order ?? 0)),
    aggregateStatus: aggregateHistoryStatus(groupItems),
  }))
}

export function matchesHistoryFilter(group: HistorySubmissionGroup, filter: HistoryFilter): boolean {
  if (filter === '全部') return true
  const status = SS.normalize(group.aggregateStatus)
  if (filter === '已退回') return SS.RETURNED_TO_SUBMITTER.has(status)
  if (filter === '已确认') return SS.CONFIRMED_AND_STORED.has(status)
  return status !== SS.S_WITHDRAWN
    && status !== SS.S_PERMANENTLY_REJECTED
    && !SS.RETURNED_TO_SUBMITTER.has(status)
    && !SS.CONFIRMED_AND_STORED.has(status)
}

export function VoiceUpdateHistoryDrawer({
  open,
  history,
  onClose,
  onSelectUpdate,
}: VoiceUpdateHistoryDrawerProps) {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<HistoryFilter>('全部')
  const groups = useMemo(() => {
    const keyword = search.trim().toLocaleLowerCase('zh-CN')
    return groupHistorySubmissions(history)
      .filter((group) => matchesHistoryFilter(group, filter))
      .filter((group) => !keyword || group.items.some((item) => (
        `${historySummary(item)} ${item.project_name ?? item.special_project ?? ''} ${item.source_type}`
          .toLocaleLowerCase('zh-CN')
          .includes(keyword)
      )))
  }, [filter, history, search])

  if (!open) return null

  return (
    <div className="voice-update-drawer-backdrop" onClick={onClose}>
      <aside className="voice-update-drawer voice-update-history-drawer" onClick={(event) => event.stopPropagation()} aria-label="历史提交">
        <header className="voice-update-drawer-header">
          <h2>历史提交</h2>
          <button type="button" onClick={onClose} aria-label="关闭历史提交">×</button>
        </header>
        <div className="voice-update-history-body">
            <label className="voice-update-history-search">
              <span aria-hidden="true">⌕</span>
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索历史提交内容" />
            </label>
            <div className="voice-update-history-filters" role="tablist" aria-label="历史提交状态">
              {(['全部', '审核中', '已退回', '已确认'] as HistoryFilter[]).map((item) => (
                <button key={item} type="button" role="tab" aria-selected={filter === item} className={filter === item ? 'is-active' : ''} onClick={() => setFilter(item)}>{item}</button>
              ))}
            </div>
            <div className="voice-update-history-list">
              {groups.length === 0 ? <p className="voice-update-history-empty">暂无符合条件的提交</p> : groups.map((group) => {
                const statusView = normalizeHistoryStatus(group.aggregateStatus)
                const isBatch = group.batchId !== null
                return (
                  <article className={`voice-update-history-group${isBatch ? ' is-batch' : ''}`} key={group.key}>
                    {isBatch && (
                      <header>
                        <strong>跨项目汇报 · {group.items.length} 个项目</strong>
                        <em className={statusView.badgeClass}>{statusView.label}</em>
                      </header>
                    )}
                    {group.items.map((item) => {
                      const childStatus = normalizeHistoryStatus(item.confirm_status)
                      return (
                        <button
                          type="button"
                          className="voice-update-history-item"
                          key={item.id}
                          onClick={() => { onClose(); onSelectUpdate(item.id) }}
                        >
                          <span className="voice-update-history-summary">{historySummary(item)}</span>
                          <span>{item.project_name ?? item.special_project ?? '—'} · {fmtShort(item.created_at)} · {item.source_type}</span>
                          <em className={childStatus.badgeClass}>{childStatus.label}</em>
                        </button>
                      )
                    })}
                  </article>
                )
              })}
            </div>
          </div>
      </aside>
    </div>
  )
}
