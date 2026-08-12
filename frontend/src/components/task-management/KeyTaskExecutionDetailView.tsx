import { useState } from 'react'
import type { MonthlyPlan } from '../../api/monthlyPlans'
import { currentMonthKey, monthPlanStatus } from '../../domain/monthPlans'
import type { Project, ProjectMember, TaskItem } from '../../types'
import type { SubTaskDetail, SubTaskPayload } from '../../api/subtasks'
import { MonthlyPlanWorkspace } from './MonthlyPlanWorkspace'

type Props = {
  project: Project | null
  task: TaskItem | null
  subTask: SubTaskDetail
  projectMembers: ProjectMember[]
  onBack: () => void
  canManageSchedules?: boolean
  canChangeAssignee?: boolean
  onSchedulesChanged?: () => void
  onEditSubTask?: (payload: Omit<SubTaskPayload, 'project_id'>) => Promise<void>
}
type ReportItem = NonNullable<SubTaskDetail['work_reports']>[number]

const toLines = (value?: string[] | string) => Array.isArray(value) ? value.filter(Boolean) : value ? [value] : []
const collaboratorOf = (notes?: string) => notes?.match(/协同人[：:]?([^\n]+)/)?.[1]?.trim() || ''
const notesForCollaborator = (collaborator: string) => collaborator.trim() ? `协同人：${collaborator.trim()}` : ''
const dateText = (value?: string | null) => value ? value.replace('T', ' ').slice(0, 16) : '暂无汇报时间'

function ReportCell({ title, values }: { title: string; values: string[] }) {
  return <div className="min-w-0 border-b border-slate-100 px-4 py-3 even:border-l sm:border-b-0 sm:[&:nth-child(n+3)]:border-t"><h3 className="text-xs font-semibold text-slate-600">{title}</h3><div className="mt-1.5 text-xs leading-5 text-slate-700">{values.length ? values.map((value, index) => <p key={`${value}-${index}`}>{value}</p>) : <span className="text-slate-400">暂无</span>}</div></div>
}

function AchievementList({ subTask }: { subTask: SubTaskDetail }) {
  const achievements = subTask.related_achievements ?? []
  return <section className="rounded-xl border border-slate-200 bg-white p-4"><h2 className="text-sm font-semibold text-slate-800">相关成果{achievements.length ? `（${achievements.length}）` : ''}</h2>{achievements.length ? <div className="mt-3 space-y-2">{achievements.map((item) => <div key={item.id} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2"><p className="truncate text-xs font-medium text-slate-700">{item.name}</p><p className="mt-1 text-[11px] text-slate-400">{item.achievement_type || '成果'} · {item.status || '进行中'}</p></div>)}</div> : <p className="mt-3 text-xs text-slate-400">暂无关联成果</p>}</section>
}

function KeyTaskEditDrawer({ subTask, members, canChangeAssignee, onSave, onClose }: {
  subTask: SubTaskDetail
  members: ProjectMember[]
  canChangeAssignee: boolean
  onSave: (payload: Omit<SubTaskPayload, 'project_id'>) => Promise<void>
  onClose: () => void
}) {
  const [title, setTitle] = useState(subTask.title || '')
  const [assignee, setAssignee] = useState(subTask.assignee || '')
  const [collaborator, setCollaborator] = useState(collaboratorOf(subTask.notes))
  const [planTime, setPlanTime] = useState(subTask.plan_time || '')
  const [status, setStatus] = useState(subTask.status || '未开始')
  const [criteria, setCriteria] = useState(subTask.completion_criteria || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const memberNames = Array.from(new Set([...members.map((member) => member.person_name_snapshot), assignee].filter(Boolean)))

  async function submit() {
    if (!title.trim()) {
      setError('请填写任务名称')
      return
    }
    setSaving(true)
    setError('')
    try {
      await onSave({
        title: title.trim(),
        assignee: assignee.trim(),
        plan_time: planTime.trim(),
        status,
        completion_criteria: criteria.trim(),
        notes: notesForCollaborator(collaborator),
      })
      onClose()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : '保存失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  return <div className="fixed inset-0 z-50 bg-slate-900/30" onClick={onClose}>
    <aside className="ml-auto flex h-full w-full max-w-md flex-col bg-white shadow-2xl" aria-label="编辑关键任务" onClick={(event) => event.stopPropagation()}>
      <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4"><div><h2 className="text-base font-semibold text-slate-800">编辑关键任务</h2><p className="mt-1 text-xs text-slate-400">修改基础信息，不影响已有月计划分支。</p></div><button type="button" onClick={onClose} className="rounded p-1 text-xl leading-none text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="关闭">×</button></header>
      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
        <label className="block text-sm font-medium text-slate-700">任务名称<input value={title} onChange={(event) => setTitle(event.target.value)} disabled={saving} className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500" /></label>
        <label className="block text-sm font-medium text-slate-700">责任人<select value={assignee} onChange={(event) => setAssignee(event.target.value)} disabled={saving || !canChangeAssignee} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500">{memberNames.map((name) => <option key={name} value={name}>{name}</option>)}</select>{!canChangeAssignee && <span className="mt-1 block text-xs text-slate-400">直接负责人不可调整责任人。</span>}</label>
        <label className="block text-sm font-medium text-slate-700">协同人<input value={collaborator} onChange={(event) => setCollaborator(event.target.value)} disabled={saving} placeholder="多人可用、分隔" className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500" /></label>
        <label className="block text-sm font-medium text-slate-700">计划时间<input value={planTime} onChange={(event) => setPlanTime(event.target.value)} disabled={saving} placeholder="例如 2026-08-01 ~ 2026-08-31" className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500" /></label>
        <label className="block text-sm font-medium text-slate-700">整体状态<select value={status} onChange={(event) => setStatus(event.target.value)} disabled={saving} className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500"><option value="未开始">未开始</option><option value="进行中">进行中</option><option value="延期">延期</option><option value="暂缓">暂缓</option><option value="已完成">已完成</option></select></label>
        <label className="block text-sm font-medium text-slate-700">完成标准<textarea value={criteria} onChange={(event) => setCriteria(event.target.value)} disabled={saving} rows={5} className="mt-1.5 w-full resize-y rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500" /></label>
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      </div>
      <footer className="flex justify-end gap-3 border-t border-slate-200 px-5 py-4"><button type="button" onClick={onClose} disabled={saving} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700">取消</button><button type="button" onClick={() => void submit()} disabled={saving} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">{saving ? '保存中…' : '保存更改'}</button></footer>
    </aside>
  </div>
}

export function KeyTaskExecutionDetailView({ project, task, subTask, projectMembers, onBack, canManageSchedules = false, canChangeAssignee = false, onSchedulesChanged, onEditSubTask }: Props) {
  const reports: ReportItem[] = subTask.work_reports ?? []
  const criteria = toLines(subTask.completion_criteria)
  const collaborator = collaboratorOf(subTask.notes)
  const latest = reports[0]
  const [monthlyPlans, setMonthlyPlans] = useState<MonthlyPlan[]>([])
  const [editingBaseTask, setEditingBaseTask] = useState(false)
  const defaultAssigneeId = projectMembers.find((member) => member.person_name_snapshot === subTask.assignee)?.person_id ?? subTask.assignee_id ?? null
  const currentMonthPlans = monthlyPlans.filter((plan) => plan.plan_month === currentMonthKey())
  const overdueCount = currentMonthPlans.filter((plan) => monthPlanStatus(plan) === '已延期').length
  const completedCount = currentMonthPlans.filter((plan) => plan.status === '已完成').length

  return <main className="flex-1 overflow-y-auto bg-slate-50"><div className="mx-auto max-w-[1360px] px-6 py-5">
    <button type="button" onClick={onBack} className="text-xs font-medium text-slate-500 hover:text-blue-600">← 返回工作推进表</button>
    <section className="mt-3 rounded-xl border border-slate-200 bg-white px-5 py-4"><div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h1 className="text-xl font-semibold tracking-tight text-slate-900">{subTask.title}</h1><span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">{subTask.status || '未开始'}</span></div><p className="mt-2 text-xs text-slate-500">所属重点工作：{task?.key_task || '—'}</p></div><div className="flex items-center gap-3"><span className="text-xs text-slate-400">所属项目：{project?.name || '—'}</span>{canManageSchedules && onEditSubTask && <button type="button" onClick={() => setEditingBaseTask(true)} className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700 hover:bg-blue-100">编辑关键任务</button>}</div></div><div className="mt-4 grid border-t border-slate-100 pt-3 sm:grid-cols-2 xl:grid-cols-4"><Info title="直接负责人" value={subTask.assignee || '未指定'} />{collaborator && <Info title="协同人" value={collaborator} />}<Info title="整体状态" value={subTask.status || '未开始'} accent /><Info title="计划周期" value={subTask.plan_time || '未填写'} /></div></section>
    <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]"><div className="min-w-0 space-y-4"><MonthlyPlanWorkspace subtaskId={subTask.id} defaultAssigneeId={defaultAssigneeId} members={projectMembers} canManage={canManageSchedules} onChanged={onSchedulesChanged} onPlansLoaded={setMonthlyPlans} /><section className="rounded-xl border border-slate-200 bg-white p-5"><div className="flex items-center justify-between gap-3"><h2 className="text-base font-semibold text-slate-800">过程记录</h2><span className="text-xs text-slate-400">汇报、成果与问题</span></div>{criteria.length > 0 && <div className="mt-4 rounded-lg bg-slate-50 px-4 py-3"><h3 className="text-xs font-semibold text-slate-600">任务评价标准</h3><div className="mt-2 space-y-1 text-sm leading-6 text-slate-700">{criteria.map((item, index) => <p key={`${item}-${index}`}>• {item}</p>)}</div></div>}<div className="mt-4 flex items-center justify-between gap-3"><h3 className="text-sm font-semibold text-slate-800">工作汇报记录</h3><span className="text-xs text-slate-400">共 {reports.length} 条</span></div>{reports.length ? <div className="mt-3 space-y-3">{reports.map((report) => <article key={report.id} className="overflow-hidden rounded-lg border border-slate-200 bg-white"><header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-slate-50 px-4 py-2.5"><span className="text-xs font-semibold text-slate-700">{report.submitter || '—'}</span><time className="text-xs text-slate-400">{dateText(report.created_at)}</time></header><div className="grid sm:grid-cols-2"><ReportCell title="已完成内容" values={toLines(report.completed_items)} /><ReportCell title="下一步计划" values={toLines(report.next_steps)} /><ReportCell title="问题" values={report.issues.map((item) => typeof item === 'string' ? item : item.description || '').filter(Boolean)} /><ReportCell title="成果" values={report.achievements.map((item) => item.name || item.achievement_type || '').filter(Boolean)} /></div></article>)}</div> : <div className="mt-3 rounded-lg border border-dashed border-slate-200 px-4 py-7 text-center"><p className="text-sm font-medium text-slate-600">暂无工作汇报</p><p className="mt-1 text-xs text-slate-400">提交第一条汇报后，这里会形成实际的任务推进记录。</p></div>}</section></div>
      <aside className="space-y-4"><section className="rounded-xl border border-slate-200 bg-white p-4"><h2 className="text-sm font-semibold text-slate-800">关键任务概览</h2><dl className="mt-4 space-y-3 text-xs"><div><dt className="text-slate-400">本月计划</dt><dd className="mt-1 font-semibold text-slate-700">{currentMonthPlans.length} 条</dd></div><div><dt className="text-slate-400">需关注</dt><dd className="mt-1 font-semibold text-red-600">{overdueCount} 条已延期</dd></div><div><dt className="text-slate-400">本月完成</dt><dd className="mt-1 font-semibold text-slate-700">{completedCount} / {currentMonthPlans.length}</dd></div><div><dt className="text-slate-400">最新汇报时间</dt><dd className="mt-1 text-slate-700">{dateText(latest?.created_at)}</dd></div>{criteria.length > 0 && <div><dt className="text-slate-400">完成标准</dt><dd className="mt-1 text-slate-700">已填写 {criteria.length} 条</dd></div>}</dl></section><section className="rounded-xl border border-slate-200 bg-white p-4"><h2 className="text-sm font-semibold text-slate-800">最新过程记录</h2>{latest ? <p className="mt-3 text-xs leading-5 text-slate-600">{toLines(latest.next_steps)[0] || toLines(latest.completed_items)[0] || '已提交最新汇报'}</p> : <p className="mt-3 text-xs text-slate-400">暂无过程记录</p>}</section>{(subTask.related_achievements?.length ?? 0) > 0 && <AchievementList subTask={subTask} />}</aside>
    </div>
  </div>{editingBaseTask && onEditSubTask && <KeyTaskEditDrawer subTask={subTask} members={projectMembers} canChangeAssignee={canChangeAssignee} onSave={onEditSubTask} onClose={() => setEditingBaseTask(false)} />}</main>
}

function Info({ title, value, accent = false }: { title: string; value: string; accent?: boolean }) {
  return <div className="min-w-0 border-b border-slate-100 px-4 py-3 last:border-b-0 sm:border-r sm:last:border-r-0 xl:border-b-0"><p className="text-xs text-slate-400">{title}</p><p className={`mt-1 truncate text-sm font-medium ${accent ? 'text-blue-600' : 'text-slate-800'}`}>{value}</p></div>
}
