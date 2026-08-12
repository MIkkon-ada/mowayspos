import { useEffect, useMemo, useState } from 'react'
import {
  analyzeProgressReview,
  confirmProgressReview,
  fetchProgressReviews,
  patchProgressReview,
  type MeetingProgressReviewItem,
  type MeetingProgressStatus,
} from '../../api/meetings'
import { ErrorBar, MeetingSection, SectionTitle } from './meetingShared'

const STATUS_LABEL: Record<MeetingProgressStatus, string> = {
  completed: '已完成',
  in_progress: '进行中',
  blocked: '阻塞',
  not_started: '未开始',
  not_mentioned: '未提及',
}

const STATUS_STYLE: Record<MeetingProgressStatus, string> = {
  completed: 'bg-emerald-50 text-emerald-700',
  in_progress: 'bg-sky-50 text-sky-700',
  blocked: 'bg-rose-50 text-rose-700',
  not_started: 'bg-amber-50 text-amber-700',
  not_mentioned: 'bg-slate-100 text-slate-500',
}

type Draft = { status: MeetingProgressStatus; suggested_task_status: string; review_comment: string }

function parseBaselineTitle(value: string) {
  try {
    const parsed = JSON.parse(value) as { subtask?: { title?: string }; task?: { title?: string } }
    return parsed.subtask?.title || parsed.task?.title || '未关联任务'
  } catch {
    return '未关联任务'
  }
}

function parseValidation(value: string): string[] {
  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed.map(String).filter(Boolean) : []
  } catch {
    return []
  }
}

export function MeetingProgressReviewSection({ meetingId, refreshToken = 0 }: { meetingId: number; refreshToken?: number }) {
  const [rows, setRows] = useState<MeetingProgressReviewItem[]>([])
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [drafts, setDrafts] = useState<Record<number, Draft>>({})

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      setRows(await fetchProgressReviews(meetingId))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [meetingId, refreshToken])

  const updateDraft = (row: MeetingProgressReviewItem, patch: Partial<Draft>) => {
    setDrafts((current) => ({
      ...current,
      [row.id]: {
        status: current[row.id]?.status ?? row.status,
        suggested_task_status: current[row.id]?.suggested_task_status ?? row.suggested_task_status,
        review_comment: current[row.id]?.review_comment ?? row.review_comment ?? '',
        ...patch,
      },
    }))
  }

  const draftFor = (row: MeetingProgressReviewItem): Draft => drafts[row.id] ?? {
    status: row.status,
    suggested_task_status: row.suggested_task_status,
    review_comment: row.review_comment ?? '',
  }

  const runAnalysis = async () => {
    setAnalyzing(true)
    setError('')
    try {
      await analyzeProgressReview(meetingId)
      await load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setAnalyzing(false)
    }
  }

  const saveDraft = async (row: MeetingProgressReviewItem, reviewStatus: 'pending' | 'ignored') => {
    const draft = draftFor(row)
    setError('')
    try {
      await patchProgressReview(meetingId, row.id, { ...draft, review_status: reviewStatus })
      await load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const confirm = async (row: MeetingProgressReviewItem) => {
    const draft = draftFor(row)
    setError('')
    try {
      await confirmProgressReview(meetingId, row.id, draft)
      await load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const pendingCount = useMemo(() => rows.filter((row) => row.review_status === 'pending').length, [rows])

  return (
    <div className="bg-white rounded-2xl border p-5 mb-5" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
      <div className="flex items-center justify-between mb-3">
        <SectionTitle>成员完成情况（启动会基线）</SectionTitle>
        <button type="button" className="text-xs text-sky-700 border border-sky-200 rounded-lg px-3 py-1.5 disabled:opacity-50" onClick={runAnalysis} disabled={analyzing}>
          {analyzing ? '分析中…' : rows.length ? '重新分析' : '分析完成情况'}
        </button>
      </div>
      {pendingCount > 0 && <div className="mb-3 text-xs text-amber-700">{pendingCount} 条结果等待负责人确认</div>}
      {error && <div className="mb-3"><ErrorBar msg={error} /></div>}
      {loading ? (
        <div className="text-xs text-slate-400">正在读取成员完成情况…</div>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-200 px-4 py-6 text-center text-xs text-slate-400">暂无成员进度分析结果，请确认会议原文使用“姓名：汇报内容”格式。</div>
      ) : (
        <div className="space-y-3">
          {rows.map((row) => {
            const draft = draftFor(row)
            const validation = parseValidation(row.validation_json)
            const locked = row.review_status !== 'pending'
            return (
              <MeetingSection key={row.id} title={`${row.member_name} · ${parseBaselineTitle(row.baseline_snapshot_json)}`}>
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${STATUS_STYLE[draft.status]}`}>{STATUS_LABEL[draft.status]}</span>
                  <span className="text-[11px] text-slate-400">审核：{row.review_status === 'accepted' ? '已确认' : row.review_status === 'ignored' ? '已忽略' : '待确认'}</span>
                </div>
                <div className="space-y-2 text-xs text-slate-600">
                  <p><span className="font-semibold text-slate-500">本次汇报：</span>{row.report_text || '未记录'}</p>
                  <p><span className="font-semibold text-slate-500">原文证据：</span>{row.evidence_quote || '暂无可核验证据'}</p>
                </div>
                {validation.length > 0 && <div className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">待核验：{validation.join('；')}</div>}
                {!locked && (
                  <div className="mt-3 grid gap-2 md:grid-cols-[150px_1fr]">
                    <select className="border border-slate-200 rounded-lg px-2 py-1.5 text-xs" value={draft.status} onChange={(event) => updateDraft(row, { status: event.target.value as MeetingProgressStatus })}>
                      {Object.entries(STATUS_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select>
                    <input className="border border-slate-200 rounded-lg px-2 py-1.5 text-xs" value={draft.review_comment} onChange={(event) => updateDraft(row, { review_comment: event.target.value })} placeholder="审核备注（可选）" />
                  </div>
                )}
                {!locked && (
                  <div className="mt-3 flex justify-end gap-2">
                    <button type="button" className="text-xs border border-slate-200 rounded-lg px-3 py-1.5 text-slate-500" onClick={() => saveDraft(row, 'ignored')}>忽略</button>
                    <button type="button" className="text-xs rounded-lg px-3 py-1.5 text-white bg-sky-600 disabled:opacity-50" onClick={() => confirm(row)}>确认并写回</button>
                  </div>
                )}
              </MeetingSection>
            )
          })}
        </div>
      )}
    </div>
  )
}
