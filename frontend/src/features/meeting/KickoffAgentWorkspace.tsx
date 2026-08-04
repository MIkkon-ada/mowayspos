import { useEffect, useMemo, useState } from 'react'
import {
  confirmKickoffStart,
  createKickoffRun,
  fetchKickoffRuns,
  reviewKickoffProposal,
  submitKickoffRun,
  type KickoffRun,
} from '../../api/meetings'

function parseJson(value: string): Record<string, unknown> {
  try { return JSON.parse(value) as Record<string, unknown> } catch { return {} }
}

function proposalLabel(type: string) {
  return ({ no_change: '无调整', create: '新增', update: '修改', delete: '删除' } as Record<string, string>)[type] ?? type
}

export function KickoffAgentWorkspace({ projectId, onClose }: { projectId: number; onClose: () => void }) {
  const [transcript, setTranscript] = useState('')
  const [run, setRun] = useState<KickoffRun | null>(null)
  const [summary, setSummary] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    fetchKickoffRuns(projectId)
      .then((runs) => {
        const latest = runs[0] ?? null
        setRun(latest)
        if (latest) setSummary(String(parseJson(latest.result_json).summary ?? ''))
      })
      .catch(() => setMessage('无法读取已有启动会审核包。'))
  }, [projectId])

  const result = useMemo(() => parseJson(run?.result_json ?? ''), [run])
  const isDraft = run?.status === 'draft'
  const isSubmitted = run?.status === 'submitted'
  const canConfirm = isSubmitted && !!run && run.proposals.every((item) => item.review_status !== 'pending' && item.review_status !== 'returned')

  async function create() {
    setSaving(true)
    try {
      const nextRun = await createKickoffRun(projectId, transcript)
      const runs = await fetchKickoffRuns(projectId)
      const created = runs.find((item) => item.id === nextRun.id) ?? runs[0] ?? null
      setRun(created)
      setSummary(created ? String(parseJson(created.result_json).summary ?? '') : '')
      setMessage('已创建审核包。请核对 Agent 结论后提交企业教练审核。')
    } catch { setMessage('创建审核包失败，请稍后重试。') } finally { setSaving(false) }
  }

  async function submit() {
    if (!run) return
    setSaving(true)
    try { setRun(await submitKickoffRun(run.id, summary)); setMessage('审核包已提交企业教练审核。') }
    catch { setMessage('提交失败，请确认当前账号具有项目负责人的权限。') }
    finally { setSaving(false) }
  }

  async function review(proposalId: number, status: 'approved' | 'returned') {
    if (!run) return
    setSaving(true)
    try {
      const updated = await reviewKickoffProposal(run.id, proposalId, status)
      setRun({ ...run, proposals: run.proposals.map((item) => item.id === updated.id ? updated : item) })
      setMessage(status === 'approved' ? '提案已审核通过。' : '提案已退回。')
    } catch { setMessage('审核失败，请确认当前账号具有企业教练权限。') } finally { setSaving(false) }
  }

  async function confirm() {
    if (!run) return
    setSaving(true)
    try { await confirmKickoffStart(run.id); setMessage('项目已启动。'); onClose() }
    catch { setMessage('启动确认失败，请完成所有提案审核后重试。') } finally { setSaving(false) }
  }

  return <section className="rounded-2xl border bg-white p-6" data-project-id={projectId}>
    <h2 className="text-base font-bold text-slate-800">启动会确认 Agent</h2>
    <p className="mt-2 text-sm text-slate-500">冻结会前工作推进表后，Agent 只生成可审核的结论和变更提案；未审核内容不会写入执行版。</p>

    {!run && <>
      <textarea className="mt-4 min-h-40 w-full rounded-xl border p-3 text-sm" value={transcript} onChange={(event) => setTranscript(event.target.value)} placeholder="粘贴或录入启动会原文" />
      <button className="mt-4 rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={!transcript.trim() || saving} onClick={create}>生成启动会审核包</button>
    </>}

    {run && <div className="mt-5 space-y-4">
      <div className="rounded-xl bg-slate-50 p-4">
        <div className="text-xs font-semibold text-slate-500">Agent 结论 · 审核包 #{run.id}</div>
        <textarea className="mt-2 min-h-24 w-full rounded-lg border p-3 text-sm" disabled={!isDraft} value={summary} onChange={(event) => setSummary(event.target.value)} />
        {isDraft && <button className="mt-3 rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={saving} onClick={submit}>提交企业教练审核</button>}
      </div>

      <div>
        <h3 className="text-sm font-bold text-slate-800">审核提案</h3>
        <div className="mt-2 space-y-2">
          {run.proposals.map((proposal) => <article key={proposal.id} className="rounded-xl border p-3 text-sm">
            <div className="font-semibold text-slate-800">{proposalLabel(proposal.proposal_type)} · {proposal.target_type || '启动结论'}</div>
            <div className="mt-1 text-slate-500">审核状态：{proposal.review_status}</div>
            {isSubmitted && proposal.review_status === 'pending' && <div className="mt-3 flex gap-2">
              <button className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white" disabled={saving} onClick={() => review(proposal.id, 'approved')}>通过</button>
              <button className="rounded-lg border px-3 py-1.5 text-xs font-semibold" disabled={saving} onClick={() => review(proposal.id, 'returned')}>退回</button>
            </div>}
          </article>)}
        </div>
      </div>

      {isSubmitted && <button className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={!canConfirm || saving} onClick={confirm}>确认启动项目</button>}
    </div>}

    <div className="mt-4 flex gap-3">
      <button className="rounded-xl border px-4 py-2 text-sm" onClick={onClose}>返回</button>
    </div>
    {message && <p className="mt-3 text-sm text-slate-600">{message}</p>}
    {result.start_conclusion === 'no_change' && <p className="mt-3 text-xs text-slate-500">本次会议结论为无调整，仍需完成审核后才能启动项目。</p>}
  </section>
}
