import { useState, type FormEvent } from 'react'
import { createMonthlyPlan, type MonthlyPlanPayload } from '../../api/monthlyPlans'
import type { ProjectMember } from '../../types'

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
    due_kind: null,
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

  function changeCollaborators(event: React.ChangeEvent<HTMLSelectElement>) {
    patch('collaborator_ids', Array.from(event.target.selectedOptions, (option) => Number(option.value)))
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

  const collaboratorCandidates = members.filter((member) => member.person_id !== form.assignee_id)

  return <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/25" role="dialog" aria-modal="true" aria-label="新增任务计划" onClick={onClose}>
    <form onSubmit={(event) => void submit(event)} className="flex h-full w-full max-w-[500px] flex-col bg-white shadow-2xl" onClick={(event) => event.stopPropagation()}>
      <header className="flex items-start justify-between border-b border-slate-200 px-6 py-5">
        <div><h2 className="text-lg font-semibold text-slate-900">新增任务计划</h2><p className="mt-1 text-xs text-slate-400">为当前关键任务拆解一条可负责、可交付的计划。</p></div>
        <button type="button" onClick={onClose} className="rounded p-1 text-xl text-slate-400 hover:bg-slate-100" aria-label="关闭">×</button>
      </header>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-5">
        <Field label="计划事项 *"><input aria-label="计划事项" value={form.title} disabled={saving} onChange={(event) => patch('title', event.target.value)} placeholder="需要推进的具体事项" className={inputClass} /></Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="负责人 *"><select aria-label="负责人" value={form.assignee_id || ''} disabled={saving} onChange={(event) => changeAssignee(Number(event.target.value))} className={inputClass}><option value="">请选择负责人</option>{members.map((member) => <option key={member.person_id} value={member.person_id}>{member.person_name_snapshot}</option>)}</select></Field>
          <Field label="协助人"><select aria-label="协助人" multiple value={form.collaborator_ids.map(String)} disabled={saving} onChange={changeCollaborators} className={inputClass + ' min-h-24'}>{collaboratorCandidates.map((member) => <option key={member.person_id} value={member.person_id}>{member.person_name_snapshot}</option>)}</select></Field>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="开始日期"><input aria-label="开始日期" type="date" value={form.start_date ?? ''} disabled={saving} onChange={(event) => patch('start_date', event.target.value || null)} className={inputClass} /></Field>
          <Field label="截止日期"><input aria-label="截止日期" type="date" value={form.due_date ?? ''} disabled={saving} onChange={(event) => patch('due_date', event.target.value || null)} className={inputClass} /></Field>
        </div>
        <Field label="预期成果 *"><textarea aria-label="预期成果" rows={3} value={form.expected_output} disabled={saving} onChange={(event) => patch('expected_output', event.target.value)} className={inputClass} /></Field>
        <Field label="完成定义"><textarea aria-label="完成定义" rows={2} value={form.completion_criteria} disabled={saving} onChange={(event) => patch('completion_criteria', event.target.value)} className={inputClass} /></Field>
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      </div>
      <footer className="flex justify-end gap-2 border-t border-slate-200 px-6 py-4">
        <button type="button" onClick={onClose} disabled={saving} className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 disabled:opacity-50">取消</button>
        <button disabled={saving} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{saving ? '创建中…' : '创建计划'}</button>
      </footer>
    </form>
  </div>
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block text-xs font-medium text-slate-600"><span className="mb-1 block">{label}</span>{children}</label>
}

const inputClass = 'w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-blue-500 disabled:cursor-not-allowed disabled:bg-slate-50'

