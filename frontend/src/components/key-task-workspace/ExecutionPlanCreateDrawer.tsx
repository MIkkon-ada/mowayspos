import { useState, type FormEvent } from 'react'
import { applyTaskPlanProposalRun, createTaskPlanProposalRun, updateTaskPlanProposal, type TaskPlanProposalRun } from '../../api/keyTaskWorkspace'
import { createMonthlyPlan, type MonthlyPlanPayload } from '../../api/monthlyPlans'
import type { ProjectMember } from '../../types'
import { CollaboratorMultiSelect } from './CollaboratorMultiSelect'
import { TaskPlanProposalReview } from './TaskPlanProposalReview'

type Props = {
  keyTaskId: number
  defaultAssigneeId: number | null
  members: ProjectMember[]
  onClose: () => void
  onCreated: () => void
}

function blankPlan(assigneeId: number | null): MonthlyPlanPayload {
  return {
    plan_month: null,
    title: '',
    expected_output: '',
    assignee_id: assigneeId ?? 0,
    collaborator_ids: [],
    status: '未开始',
    start_date: null,
    due_kind: undefined,
    due_date: null,
    due_label: null,
    due_reference_date: null,
    completion_criteria: '',
    progress_note: '',
    risk_dependency: '',
    actual_output: '',
    delay_reason: '',
    sort_order: 0,
    is_archived: false,
  }
}

export function ExecutionPlanCreateDrawer({ keyTaskId, defaultAssigneeId, members, onClose, onCreated }: Props) {
  const [form, setForm] = useState<MonthlyPlanPayload>(() => blankPlan(defaultAssigneeId))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [mode, setMode] = useState<'manual' | 'ai'>('manual')
  const [sourceText, setSourceText] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [proposalRun, setProposalRun] = useState<TaskPlanProposalRun | null>(null)

  function patch<K extends keyof MonthlyPlanPayload>(key: K, value: MonthlyPlanPayload[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function changeAssignee(assigneeId: number) {
    setForm((current) => ({
      ...current,
      assignee_id: assigneeId,
      collaborator_ids: current.collaborator_ids.filter((personId) => personId !== assigneeId),
    }))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!form.title.trim() || !form.expected_output.trim() || !form.assignee_id) {
      setError('请填写计划事项、预期成果和负责人')
      return
    }
    if (Boolean(form.start_date) !== Boolean(form.due_date)) {
      setError('开始日期和截止日期需同时填写')
      return
    }

    setSaving(true)
    setError('')
    try {
      await createMonthlyPlan(keyTaskId, {
        ...form,
        title: form.title.trim(),
        expected_output: form.expected_output.trim(),
      })
      onCreated()
      onClose()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '创建计划失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  async function generateDrafts() {
    if (!sourceText.trim() && !files.length) {
      setError('请输入需要拆解的文本或上传附件')
      return
    }
    setSaving(true)
    setError('')
    try {
      setProposalRun(await createTaskPlanProposalRun(keyTaskId, sourceText.trim(), files))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '生成计划草稿失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  async function updateDraft(proposalId: number, plan: TaskPlanProposalRun['proposals'][number]['plan']) {
    const updated = await updateTaskPlanProposal(proposalId, plan)
    setProposalRun((current) => current ? {
      ...current,
      proposals: current.proposals.map((proposal) => proposal.id === proposalId ? { ...proposal, ...updated } : proposal),
    } : current)
  }

  async function applyDrafts(proposalIds: number[]) {
    const updated = await applyTaskPlanProposalRun(keyTaskId, proposalRun!.id, proposalIds)
    setProposalRun(updated)
    onCreated()
    onClose()
  }

  const selectableMembers = members.filter((member, index, all) =>
    all.findIndex((candidate) => candidate.person_id === member.person_id) === index,
  )

  return <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/25" role="dialog" aria-modal="true" aria-label="新增任务计划" onClick={onClose}>
    <form onSubmit={(event) => void submit(event)} className="flex h-full w-full max-w-[500px] flex-col bg-white shadow-2xl" onClick={(event) => event.stopPropagation()}>
      <header className="flex items-start justify-between border-b border-slate-200 px-6 py-5">
        <div><h2 className="text-lg font-semibold text-slate-900">新增任务计划</h2><p className="mt-1 text-xs text-slate-400">为当前关键任务拆解一条可负责、可交付的计划。</p></div>
        <button type="button" onClick={onClose} className="rounded p-1 text-xl text-slate-400 hover:bg-slate-100" aria-label="关闭">×</button>
      </header>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-5">
        <div className="flex gap-2 rounded-lg bg-slate-100 p-1">
          <button type="button" onClick={() => { setMode('manual'); setError('') }} disabled={saving} className={`flex-1 rounded-md px-3 py-2 text-sm font-medium ${mode === 'manual' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-500'}`}>手工新增</button>
          <button type="button" onClick={() => { setMode('ai'); setError('') }} disabled={saving} className={`flex-1 rounded-md px-3 py-2 text-sm font-medium ${mode === 'ai' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-500'}`}>AI 拆解</button>
        </div>
        {mode === 'ai' ? proposalRun ? <TaskPlanProposalReview run={proposalRun} members={selectableMembers} busy={saving} onUpdate={updateDraft} onApply={applyDrafts} /> : <div className="space-y-4">
          <p className="rounded-lg bg-sky-50 p-3 text-xs leading-5 text-sky-800">AI 只会根据您输入的文本生成多条草稿和原文依据，不会自动创建计划。涉及客户、人员或敏感内容时，请仅输入业务必需信息。</p>
          <Field label="待拆解文本"><textarea aria-label="待拆解文本" rows={7} value={sourceText} disabled={saving} onChange={(event) => setSourceText(event.target.value)} placeholder="可选：补充会议纪要、工作安排或需求说明。" className={inputClass} /></Field>
          <label className="block text-xs font-medium text-slate-600">上传附件<input aria-label="上传附件" type="file" accept=".docx,.xlsx,.txt" multiple disabled={saving} className="mt-1 block w-full text-sm" onChange={(event) => {
            const incoming = Array.from(event.target.files ?? [])
            const invalid = incoming.find((file) => !/\.(docx|xlsx|txt)$/i.test(file.name) || file.size > 10 * 1024 * 1024)
            if (invalid) { setError(`附件 ${invalid.name} 仅支持 Word、Excel 或 UTF-8 TXT，且不能超过 10 MB`); event.currentTarget.value = ''; return }
            setFiles((current) => {
              const next = [...current, ...incoming.filter((file) => !current.some((item) => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified))]
              if (next.length > 10) { setError('一次最多上传 10 个附件'); return current }
              setError(''); return next
            })
            event.currentTarget.value = ''
          }} /></label>
          {files.length ? <ul className="space-y-1 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">{files.map((file) => <li key={`${file.name}-${file.lastModified}`} className="flex items-center justify-between gap-2"><span className="truncate">{file.name}（{Math.ceil(file.size / 1024)} KB）</span><button type="button" disabled={saving} onClick={() => setFiles((current) => current.filter((item) => item !== file))} className="text-rose-600">移除 {file.name}</button></li>)}</ul> : null}
          <button type="button" onClick={() => void generateDrafts()} className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50" disabled={saving}>{saving ? '生成中…' : '生成计划草稿'}</button>
        </div> : <>
        <Field label="计划事项 *"><input aria-label="计划事项" value={form.title} disabled={saving} onChange={(event) => patch('title', event.target.value)} placeholder="需要推进的具体事项" className={inputClass} /></Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="负责人 *"><select aria-label="负责人" value={form.assignee_id || ''} disabled={saving} onChange={(event) => changeAssignee(Number(event.target.value))} className={inputClass}><option value="">请选择负责人</option>{selectableMembers.map((member) => <option key={member.person_id} value={member.person_id}>{member.person_name_snapshot}</option>)}</select></Field>
          <CollaboratorMultiSelect members={selectableMembers} excludedPersonId={form.assignee_id || null} selectedIds={form.collaborator_ids} disabled={saving} onChange={(collaboratorIds) => patch('collaborator_ids', collaboratorIds)} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="开始日期"><input aria-label="开始日期" type="date" value={form.start_date ?? ''} disabled={saving} onChange={(event) => patch('start_date', event.target.value || null)} className={inputClass} /></Field>
          <Field label="截止日期"><input aria-label="截止日期" type="date" value={form.due_date ?? ''} disabled={saving} onChange={(event) => patch('due_date', event.target.value || null)} className={inputClass} /></Field>
        </div>
        <Field label="预期成果 *"><textarea aria-label="预期成果" rows={3} value={form.expected_output} disabled={saving} onChange={(event) => patch('expected_output', event.target.value)} className={inputClass} /></Field>
        <Field label="完成定义"><textarea aria-label="完成定义" rows={2} value={form.completion_criteria} disabled={saving} onChange={(event) => patch('completion_criteria', event.target.value)} className={inputClass} /></Field>
        </>}
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      </div>
      <footer className="flex justify-end gap-2 border-t border-slate-200 px-6 py-4">
        <button type="button" onClick={onClose} disabled={saving} className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 disabled:opacity-50">取消</button>
        {mode === 'manual' && <button disabled={saving} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{saving ? '创建中…' : '创建计划'}</button>}
      </footer>
    </form>
  </div>
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block text-xs font-medium text-slate-600"><span className="mb-1 block">{label}</span>{children}</label>
}

const inputClass = 'w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-blue-500 disabled:cursor-not-allowed disabled:bg-slate-50'
