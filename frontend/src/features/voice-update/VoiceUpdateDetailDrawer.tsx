import { useEffect, useState } from 'react'
import type { UpdateDetail } from '../../api/updates'
import { resubmitSubmission } from '../../api/confirmations'
import { getProjectDisplayName } from '../../domain/projectDisplay'
import * as SS from '../../domain/submissionStatus'
import { fmtFull } from '../../utils/time'

type TimelineNode = {
  icon: string
  iconBg: string
  title: string
  time?: string
  sub?: string
  active?: boolean
  done?: boolean
}

type VoiceUpdateDetailDrawerProps = {
  detailItem: UpdateDetail | null
  detailLoading: boolean
  showTranscript: boolean
  onClose: () => void
  onToggleTranscript: () => void
  onRestartFromSubmission: (detailItem: UpdateDetail) => void
  currentUserName?: string
  onResubmitted: (id: number) => Promise<void>
}

export function VoiceUpdateDetailDrawer({
  detailItem,
  detailLoading,
  showTranscript,
  onClose,
  onToggleTranscript,
  onRestartFromSubmission,
  currentUserName,
  onResubmitted,
}: VoiceUpdateDetailDrawerProps) {
  const [supplementNote, setSupplementNote] = useState('')
  const [resubmitting, setResubmitting] = useState(false)
  const [resubmitError, setResubmitError] = useState<string | null>(null)
  const timelineNodes = buildTimelineNodes(detailItem)

  useEffect(() => {
    setSupplementNote('')
    setResubmitError(null)
  }, [detailItem?.id])

  async function handleResubmit() {
    if (!detailItem || !currentUserName || !supplementNote.trim()) return
    setResubmitting(true)
    setResubmitError(null)
    try {
      await resubmitSubmission(detailItem.id, supplementNote.trim(), currentUserName)
      setSupplementNote('')
      await onResubmitted(detailItem.id)
    } catch (error: unknown) {
      setResubmitError(error instanceof Error ? error.message : '重新提交失败，请重试')
    } finally {
      setResubmitting(false)
    }
  }

  if (!detailItem && !detailLoading) return null

  return (
    <div
      className="fixed inset-0 z-50"
      style={{ background: 'rgba(15,23,42,0.3)' }}
      onClick={onClose}
    >
      <div
        className="absolute right-0 top-0 h-full bg-white overflow-y-auto flex flex-col"
        style={{ width: 400, boxShadow: '-4px 0 24px rgba(15,23,42,0.12)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
          <div>
            <h3 className="text-sm font-bold text-slate-800">Submission Timeline</h3>
            {detailItem && (
              <p className="text-xs text-slate-400 mt-0.5">
                {detailItem.source_type} · {fmtFull(detailItem.created_at)}
              </p>
            )}
          </div>
          <button
            className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-slate-100 text-slate-400 cursor-pointer"
            onClick={onClose}
          >
            <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {detailLoading ? (
          <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">Loading...</div>
        ) : detailItem ? (
          <div className="flex-1 p-5 space-y-3 overflow-y-auto">
            <div className="relative">
              {timelineNodes.map((node, idx) => (
                <div key={idx} className="flex gap-3">
                  <div className="flex flex-col items-center flex-shrink-0" style={{ width: 36 }}>
                    <div
                      className="w-9 h-9 rounded-xl flex items-center justify-center text-base flex-shrink-0"
                      style={{
                        background: node.iconBg,
                        border: node.active ? '2px solid #F59E0B' : '2px solid #E9EFF6',
                        opacity: node.done || node.active ? 1 : 0.4,
                      }}
                    >
                      {node.icon}
                    </div>
                    {idx < timelineNodes.length - 1 && (
                      <div className="w-0.5 my-1" style={{ background: '#E9EFF6', minHeight: 20 }} />
                    )}
                  </div>
                  <div className="flex-1 pb-4">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-xs font-bold text-slate-800">{node.title}</span>
                      {node.active && (
                        <span className="text-xs px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-600 font-semibold">In progress</span>
                      )}
                    </div>
                    {node.time && <p className="text-xs text-slate-400 mb-0.5">{node.time}</p>}
                    {node.sub && <p className="text-xs text-slate-500 leading-relaxed">{node.sub}</p>}
                  </div>
                </div>
              ))}
            </div>

            {(detailItem.ai_result?.summary as string | undefined) && (
              <div className="p-3 rounded-xl" style={{ background: '#EFF6FF', border: '1px solid #BFDBFE' }}>
                <p className="text-xs font-semibold text-slate-500 mb-1">AI Summary</p>
                <p className="text-xs text-slate-700 leading-relaxed">{detailItem.ai_result?.summary as string}</p>
              </div>
            )}

            <div className="rounded-xl border overflow-hidden" style={{ borderColor: '#E9EFF6' }}>
              <button
                className="w-full flex items-center justify-between px-4 py-2.5 text-xs font-semibold text-slate-500 hover:bg-slate-50 cursor-pointer"
                onClick={onToggleTranscript}
              >
                <span>Transcript</span>
                <svg
                  style={{
                    width: 12,
                    height: 12,
                    transition: 'transform 0.2s',
                    transform: showTranscript ? 'rotate(180deg)' : 'rotate(0deg)',
                  }}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {showTranscript && (
                <div className="px-4 pb-3 text-xs text-slate-600 leading-relaxed" style={{ background: '#F8FAFC', borderTop: '1px solid #E9EFF6', maxHeight: 200, overflowY: 'auto' }}>
                  {detailItem.transcript_text || '-'}
                </div>
              )}
            </div>

            {SS.RETURNED_TO_SUBMITTER.has(SS.normalize(detailItem.confirm_status)) && (
              <div className="p-3 rounded-xl" style={{ background: '#FEF2F2', border: '1px solid #FECACA' }}>
                <p className="text-xs text-red-700 font-semibold mb-1">负责人已退回，请补充后重新提交</p>
                <p className="text-xs text-red-600 mb-2">退回原因：{detailItem.reject_reason || '未说明'}</p>
                <textarea
                  value={supplementNote}
                  onChange={(event) => setSupplementNote(event.target.value)}
                  placeholder="请说明本次补充或修正的内容（必填）…"
                  disabled={resubmitting}
                  className="w-full min-h-20 rounded-lg border border-red-200 bg-white p-2 text-xs resize-none"
                />
                {resubmitError && <p className="mt-2 text-xs text-red-600">{resubmitError}</p>}
                <div className="mt-2 flex gap-2">
                  <button className="text-xs text-slate-500 underline cursor-pointer" onClick={() => onRestartFromSubmission(detailItem)}>从原文重新编辑</button>
                  <button
                    className="ml-auto rounded-lg bg-orange-500 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
                    onClick={handleResubmit}
                    disabled={resubmitting || !supplementNote.trim() || !currentUserName}
                  >
                    {resubmitting ? '提交中…' : '补充并重新提交'}
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function buildTimelineNodes(detailItem: UpdateDetail | null): TimelineNode[] {
  if (!detailItem) return []
  const ai = detailItem.ai_result ?? {}
  const confPct = (() => {
    const c = detailItem.confidence ?? (ai.confidence as number | undefined) ?? 0
    return c < 1 ? Math.round((c as number) * 100) : Math.round(c as number)
  })()
  const fmt = (s?: string) => (fmtFull(s) !== '-' ? fmtFull(s) : undefined)

  const nodes: TimelineNode[] = [
    {
      icon: '1',
      iconBg: '#EFF6FF',
      title: 'Submitted',
      time: fmt(detailItem.created_at),
      sub: `via ${detailItem.source_type}`,
      done: true,
    },
    {
      icon: '2',
      iconBg: '#F5F3FF',
      title: 'AI extraction',
      time: fmt(detailItem.created_at),
      sub: confPct > 0
        ? `confidence ${confPct}% · project ${getProjectDisplayName([], ai)}`
        : `project ${getProjectDisplayName([], ai)}`,
      done: true,
    },
  ]

  const st = SS.normalize(detailItem.confirm_status)
  if (st === SS.S_NEW || SS.PENDING_OWNER_REVIEW.has(st)) {
    nodes.push({ icon: '3', iconBg: '#FFF7ED', title: 'Awaiting owner review', sub: 'Queued for confirmation', active: true })
  } else if (SS.CONFIRMED_AND_STORED.has(st)) {
    nodes.push({
      icon: '3',
      iconBg: '#F0FDF4',
      title: 'Confirmed and stored',
      time: fmt(detailItem.confirmed_at),
      sub: detailItem.confirmed_by ? `Confirmed by ${detailItem.confirmed_by}` : 'Saved to workflow board',
      done: true,
    })
  } else if (SS.RETURNED_TO_SUBMITTER.has(st)) {
    nodes.push({
      icon: '3',
      iconBg: '#FEF2F2',
      title: 'Returned for changes',
      time: fmt(detailItem.updated_at),
      sub: detailItem.reject_reason ? `Reason: ${detailItem.reject_reason}` : 'Needs re-edit',
      done: true,
    })
  } else if (SS.WAITING_COORDINATOR_FEEDBACK.has(st)) {
    nodes.push({
      icon: '3',
      iconBg: '#F5F3FF',
      title: 'Waiting coordinator feedback',
      time: fmt(detailItem.updated_at),
      sub: detailItem.coordinator_note || 'Submitted to coordinator',
      done: true,
    })
  } else if (SS.WAITING_CEO_DECISION.has(st)) {
    nodes.push({
      icon: '3',
      iconBg: '#EFF6FF',
      title: '待企业教练决策',
      time: fmt(detailItem.updated_at),
      sub: detailItem.ceo_note || '待企业教练处理',
      active: true,
    })
  }

  return nodes
}
