import { useState } from 'react'
import type { TaskPlanProposal, TaskPlanProposalRun } from '../../api/keyTaskWorkspace'
import type { ProjectMember } from '../../types'
import { CollaboratorMultiSelect } from './CollaboratorMultiSelect'

type Props = {
  run: TaskPlanProposalRun
  members: ProjectMember[]
  busy: boolean
  onUpdate: (proposalId: number, plan: TaskPlanProposal['plan']) => Promise<void>
  onApply: (proposalIds: number[]) => Promise<void>
}

const inputClass = 'w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-blue-500 disabled:bg-slate-50'

export function TaskPlanProposalReview({ run, members, busy, onUpdate, onApply }: Props) {
  const [selected, setSelected] = useState<Set<number>>(() => new Set(run.proposals.filter((item) => item.status === 'ready').map((item) => item.id)))
  const [drafts, setDrafts] = useState<Record<number, TaskPlanProposal['plan']>>(() => Object.fromEntries(run.proposals.map((item) => [item.id, item.plan])))
  const [savingId, setSavingId] = useState<number | null>(null)
  const [error, setError] = useState('')

  const toggle = (proposal: TaskPlanProposal) => {
    if (proposal.status !== 'ready' || busy) return
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(proposal.id)) next.delete(proposal.id)
      else next.add(proposal.id)
      return next
    })
  }

  const save = async (proposal: TaskPlanProposal) => {
    setSavingId(proposal.id)
    setError('')
    try {
      await onUpdate(proposal.id, drafts[proposal.id])
      setSelected((current) => new Set([...current, proposal.id]))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '保存草稿失败')
    } finally {
      setSavingId(null)
    }
  }

  const confirm = async () => {
    setError('')
    try {
      await onApply([...selected])
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '创建任务计划失败')
    }
  }

  return <section className="space-y-4" aria-label="AI 计划草稿审核">
    <div className="rounded-lg bg-sky-50 p-3 text-xs leading-5 text-sky-800">AI 仅根据输入文本生成草稿，不会自动创建。请核对每条计划及其原文依据；补全后先保存该条草稿，再勾选确认创建。</div>
    {run.proposals.map((proposal) => {
      const plan = drafts[proposal.id]
      const ready = proposal.status === 'ready'
      const executed = proposal.status === 'executed'
      return <article key={proposal.id} className="rounded-xl border border-slate-200 p-4">
        <div className="flex items-start gap-3">
          <input type="checkbox" aria-label={`选择计划草稿 ${proposal.id}`} checked={selected.has(proposal.id)} disabled={!ready || busy || executed} onChange={() => toggle(proposal)} className="mt-1 size-4 accent-blue-600" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2"><span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${ready ? 'bg-emerald-100 text-emerald-700' : executed ? 'bg-slate-100 text-slate-600' : 'bg-amber-100 text-amber-700'}`}>{executed ? '已创建' : ready ? '可创建' : '待确认'}</span><span className="text-xs text-slate-500">草稿 #{proposal.id}</span></div>
            <div className="mt-3 space-y-3">
              <label className="block text-xs font-medium text-slate-600">计划事项 *<input value={plan.title} disabled={busy || executed} onChange={(event) => setDrafts((current) => ({ ...current, [proposal.id]: { ...plan, title: event.target.value } }))} className={inputClass + ' mt-1'} /></label>
              <label className="block text-xs font-medium text-slate-600">预期成果 *<textarea rows={2} value={plan.expected_output} disabled={busy || executed} onChange={(event) => setDrafts((current) => ({ ...current, [proposal.id]: { ...plan, expected_output: event.target.value } }))} className={inputClass + ' mt-1'} /></label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-xs font-medium text-slate-600">负责人 *<select value={plan.assignee_id ?? ''} disabled={busy || executed} onChange={(event) => setDrafts((current) => ({ ...current, [proposal.id]: { ...plan, assignee_id: Number(event.target.value) || null, collaborator_ids: plan.collaborator_ids.filter((id) => id !== Number(event.target.value)) } }))} className={inputClass + ' mt-1'}><option value="">请选择负责人</option>{members.filter((member, index, all) => all.findIndex((item) => item.person_id === member.person_id) === index).map((member) => <option key={member.person_id} value={member.person_id}>{member.person_name_snapshot}</option>)}</select></label>
                <CollaboratorMultiSelect members={members} excludedPersonId={plan.assignee_id} selectedIds={plan.collaborator_ids} disabled={busy || executed} onChange={(collaboratorIds) => setDrafts((current) => ({ ...current, [proposal.id]: { ...plan, collaborator_ids: collaboratorIds } }))} />
              </div>
              <div className="grid gap-3 sm:grid-cols-2"><label className="block text-xs font-medium text-slate-600">开始日期<input type="date" value={plan.start_date ?? ''} disabled={busy || executed} onChange={(event) => setDrafts((current) => ({ ...current, [proposal.id]: { ...plan, start_date: event.target.value || null } }))} className={inputClass + ' mt-1'} /></label><label className="block text-xs font-medium text-slate-600">截止日期<input type="date" value={plan.due_date ?? ''} disabled={busy || executed} onChange={(event) => setDrafts((current) => ({ ...current, [proposal.id]: { ...plan, due_date: event.target.value || null } }))} className={inputClass + ' mt-1'} /></label></div>
              <label className="block text-xs font-medium text-slate-600">完成定义<textarea rows={2} value={plan.completion_criteria} disabled={busy || executed} onChange={(event) => setDrafts((current) => ({ ...current, [proposal.id]: { ...plan, completion_criteria: event.target.value } }))} className={inputClass + ' mt-1'} /></label>
            </div>
            {proposal.validation.errors.length ? <p className="mt-3 text-xs text-amber-700">{proposal.validation.errors.join('；')}</p> : null}
            {Object.values(proposal.evidence).filter(Boolean).length ? <details className="mt-3 text-xs text-slate-500"><summary className="cursor-pointer text-sky-700">查看原文依据</summary><ul className="mt-2 space-y-1 rounded-lg bg-slate-50 p-3">{Object.entries(proposal.evidence).filter(([, quote]) => quote).map(([field, quote]) => <li key={field}>{field}：“{quote}”</li>)}</ul></details> : null}
            {!executed && <button type="button" onClick={() => void save(proposal)} disabled={busy || savingId === proposal.id} className="mt-3 rounded-lg border border-sky-200 px-3 py-2 text-xs font-semibold text-sky-700 disabled:opacity-50">{savingId === proposal.id ? '保存中…' : '保存此草稿'}</button>}
          </div>
        </div>
      </article>
    })}
    {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    <button type="button" onClick={() => void confirm()} disabled={busy || !selected.size} className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">确认创建已选计划（{selected.size}）</button>
  </section>
}
