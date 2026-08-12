import { useEffect, useState } from 'react'
import type { MonthlyPlan, MonthlyPlanPayload, MonthPlanStatus } from '../../api/monthlyPlans'
import type { WorkReportEntryIntent } from '../../domain/workReportEntry'
import type { ProjectMember } from '../../types'

type Props = {
  plan: MonthlyPlan | null
  selectedGroup: 'all' | string
  defaultAssigneeId: number | null
  members: ProjectMember[]
  canManage: boolean
  onSave: (payload: MonthlyPlanPayload) => Promise<void>
  onDelete?: () => Promise<void>
  onEntry?: (intent: WorkReportEntryIntent) => void
  onClose: () => void
}

const STATUS_OPTIONS: MonthPlanStatus[] = ['未开始', '进行中', '暂缓', '已完成', '已取消']

const emptySubtask = (group: 'all' | string, assigneeId: number | null): MonthlyPlanPayload => ({
  plan_month: group === 'all' ? null : group,
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

export function KeyTaskSubtaskDrawer({
  plan,
  selectedGroup,
  defaultAssigneeId,
  members,
  canManage,
  onSave,
  onDelete,
  onEntry,
  onClose,
}: Props) {
  const [form, setForm] = useState<MonthlyPlanPayload>(() => plan ? toPayload(plan) : emptySubtask(selectedGroup, defaultAssigneeId))
  const [editing, setEditing] = useState(!plan)
  const [showMore, setShowMore] = useState(Boolean(plan))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const selectableMembers = members.filter((member, index, all) =>
    all.findIndex((candidate) => candidate.person_id === member.person_id) === index,
  )

  useEffect(() => {
    setForm(plan ? toPayload(plan) : emptySubtask(selectedGroup, defaultAssigneeId))
    setEditing(!plan)
    setShowMore(Boolean(plan))
    setError('')
  }, [plan, selectedGroup, defaultAssigneeId])

  const patch = <K extends keyof MonthlyPlanPayload>(key: K, value: MonthlyPlanPayload[K]) =>
    setForm((current) => ({ ...current, [key]: value }))

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!form.title.trim() || !form.expected_output.trim() || !form.assignee_id) {
      setError('请填写子任务事项、预期产出和负责人')
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
      setError('调整已延期子任务时必须填写延期原因')
      return
    }
    setSaving(true)
    setError('')
    try {
      await onSave({ ...form, title: form.title.trim(), expected_output: form.expected_output.trim() })
      onClose()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  async function remove() {
    if (!onDelete || !plan) return
    setSaving(true)
    setError('')
    try {
      await onDelete()
      onClose()
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : '删除失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  return <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/25" role="dialog" aria-modal="true" aria-label={plan ? '子任务详情' : '新增子任务'} onClick={onClose}>
    <form onSubmit={submit} className="flex h-full w-full max-w-[500px] flex-col bg-white shadow-2xl" onClick={(event) => event.stopPropagation()}>
      <header className="flex items-start justify-between border-b border-slate-200 px-6 py-5">
        <div><h2 className="text-lg font-semibold text-slate-900">{plan ? '子任务详情' : '新增子任务'}</h2><p className="mt-1 text-xs text-slate-400">拆解关键任务中的具体责任事项，月份分组可选</p></div>
        <button type="button" onClick={onClose} className="rounded p-1 text-xl text-slate-400 hover:bg-slate-100" aria-label="关闭">×</button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        {plan && !editing ? <SubtaskReadOnly plan={plan} /> : <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="分组方式"><select value={form.plan_month ?? ''} disabled={saving} onChange={(event) => patch('plan_month', event.target.value || null)} className={inputClass}><option value="">不按月份</option>{monthOptions(form.plan_month).map((month) => <option key={month} value={month}>{month.replace('-', '年')}月</option>)}</select></Field>
            <Field label="状态 *"><select value={form.status} disabled={saving} onChange={(event) => patch('status', event.target.value as MonthPlanStatus)} className={inputClass}>{STATUS_OPTIONS.map((status) => <option key={status}>{status}</option>)}</select></Field>
          </div>
          <Field label="子任务事项 *"><input value={form.title} disabled={saving} onChange={(event) => patch('title', event.target.value)} placeholder="需要推进的具体事项" className={inputClass} /></Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-xs font-medium text-slate-600"><span className="mb-1 block">负责人 *</span><select value={form.assignee_id || ''} disabled={saving} onChange={(event) => patch('assignee_id', Number(event.target.value))} className={inputClass}><option value="">请选择负责人</option>{selectableMembers.map((member) => <option key={member.person_id} value={member.person_id}>{member.person_name_snapshot}</option>)}</select></label>
            {editing && <label className="block text-xs font-medium text-slate-600"><span className="mb-1 block">协作人</span><select multiple value={form.collaborator_ids.map(String)} disabled={saving} onChange={(event) => patch('collaborator_ids', [...event.currentTarget.selectedOptions].map((option) => Number(option.value)))} className={`${inputClass} min-h-20`}>{selectableMembers.filter((member) => member.person_id !== form.assignee_id).map((member) => <option key={member.person_id} value={member.person_id}>{member.person_name_snapshot}</option>)}</select></label>}
          </div>
          <div className="grid gap-4 sm:grid-cols-2"><Field label="开始日期"><input type="date" value={form.start_date ?? ''} disabled={saving} onChange={(event) => patch('start_date', event.target.value || null)} className={inputClass} /></Field><Field label="截止日期"><input type="date" value={form.due_date ?? ''} disabled={saving} onChange={(event) => patch('due_date', event.target.value || null)} className={inputClass} /></Field></div>
          <Field label="预期产出 *"><textarea rows={3} value={form.expected_output} disabled={saving} onChange={(event) => patch('expected_output', event.target.value)} className={inputClass} /></Field>
          <button type="button" onClick={() => setShowMore((value) => !value)} className="text-xs font-medium text-blue-600">{showMore ? '收起更多信息' : '更多信息（可选）'}</button>
          {showMore && <div className="space-y-4 border-t border-slate-100 pt-4">
            <Field label="完成标准"><textarea rows={2} value={form.completion_criteria} disabled={saving} onChange={(event) => patch('completion_criteria', event.target.value)} className={inputClass} /></Field>
            <Field label="进展说明"><textarea rows={3} value={form.progress_note} disabled={saving} onChange={(event) => patch('progress_note', event.target.value)} className={inputClass} /></Field>
            <Field label="风险与依赖"><textarea rows={2} value={form.risk_dependency} disabled={saving} onChange={(event) => patch('risk_dependency', event.target.value)} className={inputClass} /></Field>
            <Field label="实际产出"><textarea rows={2} value={form.actual_output} disabled={saving} onChange={(event) => patch('actual_output', event.target.value)} className={inputClass} /></Field>
            {plan?.is_overdue && <Field label="延期原因"><textarea rows={2} value={form.delay_reason} disabled={saving} onChange={(event) => patch('delay_reason', event.target.value)} className={inputClass} /></Field>}
          </div>}
        </div>}
        {error && <p role="alert" className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      </div>

      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-6 py-4">
        <div>{plan && canManage && editing && <button type="button" onClick={() => void remove()} disabled={saving} className="text-sm text-red-600 disabled:opacity-50">删除子任务</button>}</div>
        <div className="flex flex-wrap justify-end gap-2">{plan && !editing ? <>
          {onEntry && <button type="button" onClick={() => onEntry('report')} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white">提交汇报</button>}
          {onEntry && <button type="button" onClick={() => onEntry('issue')} className="rounded-lg border border-orange-300 px-4 py-2 text-sm font-semibold text-orange-600">记录问题</button>}
          {onEntry && <button type="button" onClick={() => onEntry('achievement')} className="rounded-lg border border-emerald-300 px-4 py-2 text-sm font-semibold text-emerald-600">添加成果</button>}
          {canManage && <button type="button" onClick={() => setEditing(true)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700">编辑</button>}
        </> : <><button type="button" onClick={onClose} className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700">取消</button><button disabled={saving} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{saving ? '保存中…' : plan ? '保存修改' : '创建子任务'}</button></>}</div>
      </footer>
    </form>
  </div>
}

function SubtaskReadOnly({ plan }: { plan: MonthlyPlan }) {
  const group = plan.plan_month ? `${plan.plan_month.slice(0, 4)}年${Number(plan.plan_month.slice(5))}月` : '未分月'
  const schedule = plan.start_date && plan.due_date ? `${plan.start_date} — ${plan.due_date}` : '未设置'
  return <div>
    <div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">{plan.display_status}</span><h3 className="text-base font-semibold text-slate-900">{plan.title}</h3></div>
    <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 text-sm">
      <div><dt className="text-xs text-slate-400">负责人</dt><dd className="mt-1 font-medium text-slate-800">{plan.assignee || '未指定'}</dd></div>
      <div><dt className="text-xs text-slate-400">协作人</dt><dd className="mt-1 font-medium text-slate-800">{plan.collaborators.join('、') || '无'}</dd></div>
      <div><dt className="text-xs text-slate-400">分组</dt><dd className="mt-1 text-slate-700">{group}</dd></div>
      <div><dt className="text-xs text-slate-400">时间安排</dt><dd className="mt-1 text-slate-700">{schedule}</dd></div>
    </dl>
    <div className="mt-6 space-y-5 border-t border-slate-100 pt-5"><Detail label="预期产出" value={plan.expected_output} /><Detail label="完成标准" value={plan.completion_criteria || '未填写'} />{plan.progress_note && <Detail label="进展说明" value={plan.progress_note} />}</div>
  </div>
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div><h4 className="text-xs font-medium text-slate-400">{label}</h4><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{value}</p></div>
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block text-xs font-medium text-slate-600"><span className="mb-1 block">{label}</span>{children}</label>
}

function monthOptions(current: string | null) {
  const now = new Date()
  const values = Array.from({ length: 12 }, (_, index) => {
    const date = new Date(now.getFullYear(), now.getMonth() - 3 + index, 1)
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
  })
  return [...new Set(current ? [current, ...values] : values)].sort()
}

function toPayload(plan: MonthlyPlan): MonthlyPlanPayload {
  const { id: _id, subtask_id: _subtaskId, assignee: _assignee, collaborators: _collaborators, display_status: _displayStatus, is_overdue: _isOverdue, ...payload } = plan
  return payload
}

const inputClass = 'w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-blue-500 disabled:cursor-not-allowed disabled:bg-slate-50'
