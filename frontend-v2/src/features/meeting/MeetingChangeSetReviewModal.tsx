import { useEffect, useMemo, useState } from 'react'
import {
  executeMeetingChangeSet,
  fetchMeetingChangeSet,
  updateMeetingChangeProposal,
  type MeetingChangeProposal,
  type MeetingChangeSet,
} from '../../api/meetings'

const ACTION_LABELS: Record<MeetingChangeProposal['action'], string> = {
  create_workstream: '新增重点工作',
  update_workstream: '修改重点工作',
  create_subtask: '新增关键任务',
  update_subtask: '修改关键任务',
}

const VALIDATION_LABELS = {
  ready: '可以执行',
  needs_review: '需要复核',
  blocked: '禁止执行',
} as const

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  return typeof value === 'string' ? value : JSON.stringify(value)
}

function proposalGroupKey(proposal: MeetingChangeProposal): string {
  if (proposal.parent_workstream_id) return `workstream-${proposal.parent_workstream_id}`
  if (proposal.target_type === 'workstream' && proposal.target_id) {
    return `workstream-${proposal.target_id}`
  }
  return 'new-workstreams'
}

export function MeetingChangeSetReviewModal({
  meetingId,
  onClose,
  onDone,
}: {
  meetingId: number
  onClose: () => void
  onDone: () => void
}) {
  const [changeSet, setChangeSet] = useState<MeetingChangeSet | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(true)
  const [executing, setExecuting] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [proposedDraft, setProposedDraft] = useState('')
  const [evidenceDraft, setEvidenceDraft] = useState('')
  const [reasonDraft, setReasonDraft] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchMeetingChangeSet(meetingId)
      .then((result) => {
        if (!cancelled) setChangeSet(result)
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [meetingId])

  const groups = useMemo(() => {
    const result = new Map<string, MeetingChangeProposal[]>()
    for (const proposal of changeSet?.proposals ?? []) {
      const key = proposalGroupKey(proposal)
      result.set(key, [...(result.get(key) ?? []), proposal])
    }
    return [...result.entries()]
  }, [changeSet])

  function toggleProposal(proposalId: number) {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(proposalId)) next.delete(proposalId)
      else next.add(proposalId)
      return next
    })
  }

  function beginEdit(proposal: MeetingChangeProposal) {
    setEditingId(proposal.id)
    setProposedDraft(JSON.stringify(proposal.proposed, null, 2))
    setEvidenceDraft(proposal.evidence.join('\n'))
    setReasonDraft(proposal.reason)
    setError('')
  }

  async function saveEdit(proposal: MeetingChangeProposal) {
    setError('')
    try {
      const parsed = JSON.parse(proposedDraft) as unknown
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('拟变更字段必须是 JSON 对象')
      }
      const updated = await updateMeetingChangeProposal(meetingId, proposal.id, {
        proposed: parsed as Record<string, unknown>,
        evidence: evidenceDraft
          .split('\n')
          .map((item) => item.trim())
          .filter(Boolean),
        reason: reasonDraft.trim(),
      })
      setChangeSet((current) => current
        ? {
            ...current,
            proposals: current.proposals.map((item) => item.id === updated.id ? updated : item),
          }
        : current)
      if (updated.validation.state === 'blocked') {
        setSelectedIds((current) => {
          const next = new Set(current)
          next.delete(updated.id)
          return next
        })
      }
      setEditingId(null)
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }

  async function confirmExecute() {
    if (selectedIds.size === 0) return
    const requestedCount = selectedIds.size
    setExecuting(true)
    setError('')
    setMessage('')
    try {
      const result = await executeMeetingChangeSet(meetingId, [...selectedIds])
      setChangeSet(result)
      setSelectedIds(new Set())
      setConfirming(false)
      setMessage(`已完成 ${requestedCount} 项变更，正在刷新会议数据…`)
      await new Promise((resolve) => window.setTimeout(resolve, 600))
      onDone()
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : String(cause))
      setConfirming(false)
    } finally {
      setExecuting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/50 p-6">
      <div className="flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <header className="flex items-start justify-between border-b border-slate-200 px-6 py-5">
          <div>
            <h2 className="text-lg font-bold text-slate-900">审核工作推进变更</h2>
            <p className="mt-1 text-sm text-slate-500">
              所有建议默认不勾选。只有你明确选择并确认的项目才会写入工作推进表。
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-3 py-1.5 text-sm text-slate-500 hover:bg-slate-100"
          >
            关闭
          </button>
        </header>

        <main className="flex-1 overflow-y-auto bg-slate-50 px-6 py-5">
          {loading && <div className="py-16 text-center text-sm text-slate-500">正在读取变更集…</div>}
          {!loading && !changeSet && (
            <div className="py-16 text-center text-sm text-slate-500">没有可审核的变更集。</div>
          )}
          {!loading && changeSet && changeSet.proposals.length === 0 && (
            <div className="rounded-xl border border-slate-200 bg-white py-16 text-center">
              <div className="font-semibold text-slate-700">本次会议没有提出工作推进变更</div>
              <div className="mt-2 text-sm text-slate-500">会议纪要已经保存，工作推进表没有发生变化。</div>
            </div>
          )}

          <div className="space-y-5">
            {groups.map(([groupKey, proposals]) => (
              <section key={groupKey} className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                <div className="border-b border-slate-200 bg-slate-100 px-4 py-2.5 text-sm font-semibold text-slate-700">
                  {groupKey === 'new-workstreams'
                    ? '拟新增重点工作'
                    : `重点工作 #${groupKey.replace('workstream-', '')}`}
                </div>
                <div className="divide-y divide-slate-100">
                  {proposals.map((proposal) => {
                    const blocked = proposal.validation.state === 'blocked'
                    const editable = proposal.execution_status === 'pending'
                    const fields = new Set([
                      ...Object.keys(proposal.before),
                      ...Object.keys(proposal.proposed),
                    ])
                    return (
                      <article key={proposal.id} className="p-4">
                        <div className="flex items-start gap-3">
                          <div className="w-6 pt-0.5">
                            {!blocked && editable && (
                              <input
                                type="checkbox"
                                checked={selectedIds.has(proposal.id)}
                                onChange={() => toggleProposal(proposal.id)}
                                className="h-4 w-4 rounded border-slate-300 text-sky-600"
                                aria-label={`选择变更 ${proposal.id}`}
                              />
                            )}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="rounded-full bg-sky-50 px-2.5 py-1 text-xs font-bold text-sky-700">
                                {ACTION_LABELS[proposal.action]}
                              </span>
                              <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                                blocked
                                  ? 'bg-red-50 text-red-700'
                                  : proposal.validation.state === 'needs_review'
                                    ? 'bg-amber-50 text-amber-700'
                                    : 'bg-emerald-50 text-emerald-700'
                              }`}>
                                {VALIDATION_LABELS[proposal.validation.state]}
                              </span>
                              {proposal.execution_status === 'executed' && (
                                <span className="text-xs font-semibold text-emerald-600">
                                  已执行 · 结果 #{proposal.result_target_id}
                                </span>
                              )}
                              <span className="text-xs text-slate-400">
                                置信度 {Math.round(proposal.confidence * 100)}%
                              </span>
                            </div>

                            <div className="mt-3 overflow-hidden rounded-lg border border-slate-200">
                              <div className="grid grid-cols-[150px_1fr_1fr] bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-500">
                                <span>字段</span><span>变更前</span><span>拟变更</span>
                              </div>
                              {[...fields].map((field) => (
                                <div key={field} className="grid grid-cols-[150px_1fr_1fr] border-t border-slate-100 px-3 py-2 text-sm">
                                  <span className="font-medium text-slate-600">{field}</span>
                                  <span className="break-all text-slate-500">{displayValue(proposal.before[field])}</span>
                                  <span className="break-all font-medium text-slate-800">{displayValue(proposal.proposed[field])}</span>
                                </div>
                              ))}
                            </div>

                            <div className="mt-3 grid gap-3 md:grid-cols-2">
                              <div className="rounded-lg bg-blue-50 p-3">
                                <div className="text-xs font-bold text-blue-700">会议原文证据</div>
                                <ul className="mt-1.5 space-y-1 text-sm text-blue-950">
                                  {proposal.evidence.map((item, index) => <li key={index}>“{item}”</li>)}
                                </ul>
                              </div>
                              <div className="rounded-lg bg-slate-50 p-3">
                                <div className="text-xs font-bold text-slate-600">建议理由</div>
                                <p className="mt-1.5 text-sm text-slate-700">{proposal.reason || '—'}</p>
                              </div>
                            </div>

                            {proposal.validation.errors.length > 0 && (
                              <ul className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                                {proposal.validation.errors.map((item, index) => <li key={index}>• {item}</li>)}
                              </ul>
                            )}

                            {editingId === proposal.id ? (
                              <div className="mt-3 space-y-3 rounded-lg border border-sky-200 bg-sky-50 p-3">
                                <label className="block text-xs font-semibold text-slate-600">
                                  拟变更字段（JSON）
                                  <textarea value={proposedDraft} onChange={(event) => setProposedDraft(event.target.value)} rows={5} className="mt-1 w-full rounded-lg border border-slate-300 bg-white p-2 font-mono text-xs" />
                                </label>
                                <label className="block text-xs font-semibold text-slate-600">
                                  原文证据（每行一条）
                                  <textarea value={evidenceDraft} onChange={(event) => setEvidenceDraft(event.target.value)} rows={3} className="mt-1 w-full rounded-lg border border-slate-300 bg-white p-2 text-sm" />
                                </label>
                                <label className="block text-xs font-semibold text-slate-600">
                                  理由
                                  <textarea value={reasonDraft} onChange={(event) => setReasonDraft(event.target.value)} rows={2} className="mt-1 w-full rounded-lg border border-slate-300 bg-white p-2 text-sm" />
                                </label>
                                <div className="flex justify-end gap-2">
                                  <button type="button" onClick={() => setEditingId(null)} className="rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-white">取消</button>
                                  <button type="button" onClick={() => saveEdit(proposal)} className="rounded-lg bg-sky-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-sky-700">保存并重新校验</button>
                                </div>
                              </div>
                            ) : editable && (
                              <button type="button" onClick={() => beginEdit(proposal)} className="mt-3 text-sm font-semibold text-sky-700 hover:text-sky-900">
                                编辑建议
                              </button>
                            )}
                          </div>
                        </div>
                      </article>
                    )
                  })}
                </div>
              </section>
            ))}
          </div>

          {error && <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
          {message && <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{message}</div>}
        </main>

        <footer className="flex items-center justify-between border-t border-slate-200 px-6 py-4">
          <span className="text-sm text-slate-500">已选择 {selectedIds.size} 项</span>
          <div className="flex gap-2">
            <button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">
              稍后处理
            </button>
            <button
              type="button"
              onClick={() => setConfirming(true)}
              disabled={selectedIds.size === 0 || executing}
              className="rounded-lg bg-sky-700 px-5 py-2 text-sm font-bold text-white hover:bg-sky-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              执行所选变更
            </button>
          </div>
        </footer>
      </div>

      {confirming && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/40">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-slate-900">确认执行 {selectedIds.size} 项变更？</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              系统会再次检查权限与工作推进表快照；任意一项已过期时，整批都不会写入。
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={() => setConfirming(false)} className="rounded-lg px-4 py-2 text-sm text-slate-600 hover:bg-slate-100">返回检查</button>
              <button type="button" onClick={confirmExecute} disabled={executing} className="rounded-lg bg-sky-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">
                {executing ? '执行中…' : '确认执行'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
