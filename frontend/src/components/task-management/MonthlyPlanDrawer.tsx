import { useEffect, useState } from 'react'
import type { MonthlyPlan, MonthlyPlanPayload, MonthPlanStatus } from '../../api/monthlyPlans'
import type { ProjectMember } from '../../types'

type Props = {
  plan: MonthlyPlan | null
  selectedMonth: string
  defaultAssigneeId: number | null
  members: ProjectMember[]
  canManage: boolean
  onSave: (payload: MonthlyPlanPayload) => Promise<void>
  onDelete?: () => Promise<void>
  onClose: () => void
}

const STATUS_OPTIONS: MonthPlanStatus[] = ['未开始', '进行中', '暂缓', '已完成', '已取消']

const emptyPlan = (month: string, assigneeId: number | null): MonthlyPlanPayload => ({
  plan_month: month,
  title: '',
  expected_output: '',
  assignee_id: assigneeId ?? 0,
  collaborator_ids: [],
  status: '未开始',
  start_date: null,
  due_date: null,
  completion_criteria: '',
  progress_note: '',
  risk_dependency: '',
  actual_output: '',
  delay_reason: '',
  sort_order: 0,
})

export function MonthlyPlanDrawer({ plan, selectedMonth, defaultAssigneeId, members, canManage, onSave, onDelete, onClose }: Props) {
  const [form, setForm] = useState<MonthlyPlanPayload>(() => plan ? toPayload(plan) : emptyPlan(selectedMonth, defaultAssigneeId))
  const [showMore, setShowMore] = useState(Boolean(plan))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setForm(plan ? toPayload(plan) : emptyPlan(selectedMonth, defaultAssigneeId))
    setShowMore(Boolean(plan))
    setError('')
  }, [plan, selectedMonth, defaultAssigneeId])

  const patch = <K extends keyof MonthlyPlanPayload>(key: K, value: MonthlyPlanPayload[K]) =>
    setForm((current) => ({ ...current, [key]: value }))

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!form.title.trim() || !form.expected_output.trim() || !form.assignee_id) {
      setError('请填写计划名称、预期产出和执行负责人')
      return
    }
    if (Boolean(form.start_date) !== Boolean(form.due_date)) {
      setError('开始日期和截止日期需同时填写')
      return
    }
    if (form.status === '已完成' && !form.actual_output.trim()) {
      setError('请填写实际产出')
      return
    }
    if (plan?.is_overdue && (form.plan_month !== plan.plan_month || form.due_date !== plan.due_date) && !form.delay_reason.trim()) {
      setError('调整已延期计划时必须填写延期原因')
      return
    }
    setSaving(true)
    setError('')
    try {
      await onSave({ ...form, title: form.title.trim(), expected_output: form.expected_output.trim() })
      onClose()
    } finally {
      setSaving(false)
    }
  }

  async function remove() {
    if (!onDelete || !plan) return
    setSaving(true)
    try {
      await onDelete()
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/30" role="dialog" aria-modal="true" aria-label={plan ? '编辑月计划' : '新增月计划'}>
    <form onSubmit={submit} className="flex h-full w-full max-w-xl flex-col bg-white shadow-2xl">
      <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
        <div><h2 className="text-base font-semibold text-slate-800">{plan ? '月计划详情' : '新增月计划'}</h2><p className="mt-1 text-xs text-slate-400">用于推进关键任务的当月执行分支</p></div>
        <button type="button" onClick={onClose} className="rounded p-2 text-slate-400 hover:bg-slate-100" aria-label="关闭">×</button>
      </header>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="计划月份 *"><input required type="month" value={form.plan_month ?? ''} disabled={!canManage} onChange={(e) => patch('plan_month', e.target.value)} className={inputClass} /></Field>
          <Field label="执行负责人 *"><select required value={form.assignee_id || ''} disabled={!canManage} onChange={(e) => patch('assignee_id', Number(e.target.value))} className={inputClass}><option value="">请选择负责人</option>{members.map((member) => <option key={member.person_id} value={member.person_id}>{member.person_name_snapshot}</option>)}</select></Field>
        </div>
        <Field label="计划名称 *"><input required value={form.title} disabled={!canManage} onChange={(e) => patch('title', e.target.value)} placeholder="本月要推进的具体事项" className={inputClass} /></Field>
        <Field label="预期产出 *"><textarea required rows={3} value={form.expected_output} disabled={!canManage} onChange={(e) => patch('expected_output', e.target.value)} placeholder="用可验证的交付结果描述" className={inputClass} /></Field>
        <Field label="状态 *"><select value={form.status} disabled={!canManage} onChange={(e) => patch('status', e.target.value as MonthPlanStatus)} className={inputClass}>{STATUS_OPTIONS.map((status) => <option key={status} value={status}>{status}</option>)}</select></Field>

        <button type="button" onClick={() => setShowMore((value) => !value)} className="text-xs font-medium text-blue-600">{showMore ? '收起补充信息' : '填写补充信息（可选）'}</button>
        {showMore && <div className="space-y-4 border-t border-slate-100 pt-4">
          <div className="grid gap-4 sm:grid-cols-2"><Field label="开始日期"><input type="date" value={form.start_date ?? ''} disabled={!canManage} onChange={(e) => patch('start_date', e.target.value || null)} className={inputClass} /></Field><Field label="截止日期"><input type="date" value={form.due_date ?? ''} disabled={!canManage} onChange={(e) => patch('due_date', e.target.value || null)} className={inputClass} /></Field></div>
          <Field label="协作人"><select multiple value={form.collaborator_ids.map(String)} disabled={!canManage} onChange={(e) => patch('collaborator_ids', [...e.currentTarget.selectedOptions].map((option) => Number(option.value)))} className={`${inputClass} min-h-24`}>{members.filter((member) => member.person_id !== form.assignee_id).map((member) => <option key={member.person_id} value={member.person_id}>{member.person_name_snapshot}</option>)}</select></Field>
          <Field label="完成标准"><textarea rows={2} value={form.completion_criteria} disabled={!canManage} onChange={(e) => patch('completion_criteria', e.target.value)} className={inputClass} /></Field>
          <Field label="进展说明"><textarea rows={3} value={form.progress_note} disabled={!canManage} onChange={(e) => patch('progress_note', e.target.value)} placeholder="当前动作、卡点及下一步" className={inputClass} /></Field>
          <Field label="风险与依赖"><textarea rows={2} value={form.risk_dependency} disabled={!canManage} onChange={(e) => patch('risk_dependency', e.target.value)} className={inputClass} /></Field>
          <Field label="实际产出"><textarea rows={2} value={form.actual_output} disabled={!canManage} onChange={(e) => patch('actual_output', e.target.value)} className={inputClass} /></Field>
          {plan?.is_overdue && <Field label="延期原因"><textarea rows={2} value={form.delay_reason} disabled={!canManage} onChange={(e) => patch('delay_reason', e.target.value)} className={inputClass} /></Field>}
        </div>}
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>
      <footer className="flex items-center justify-between border-t border-slate-200 px-5 py-4">
        <div>{canManage && plan && <button type="button" onClick={() => void remove()} disabled={saving} className="text-sm text-red-600 disabled:opacity-50">删除月计划</button>}</div>
        <div className="flex gap-2"><button type="button" onClick={onClose} className="rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100">关闭</button>{canManage && <button disabled={saving} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{saving ? '保存中…' : '保存'}</button>}</div>
      </footer>
    </form>
  </div>
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block text-xs font-medium text-slate-600"><span className="mb-1 block">{label}</span>{children}</label>
}

function toPayload(plan: MonthlyPlan): MonthlyPlanPayload {
  const { id: _id, subtask_id: _subtaskId, assignee: _assignee, collaborators: _collaborators, display_status: _displayStatus, is_overdue: _isOverdue, ...payload } = plan
  return payload
}

const inputClass = 'w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-blue-500 disabled:cursor-not-allowed disabled:bg-slate-50'
