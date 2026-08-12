import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Project, ProjectMember, TaskItem } from '../../types'
import type { SubTaskDetail, SubTaskPayload } from '../../api/subtasks'
import { buildWorkReportEntryUrl, type WorkReportEntryIntent } from '../../domain/workReportEntry'
import { KeyTaskExecutionTimeline } from './KeyTaskExecutionTimeline'
import { KeyTaskSubtasksWorkspace } from './KeyTaskSubtasksWorkspace'

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

const collaboratorOf = (notes?: string) => notes?.match(/(?:协作人|协同人)[：:]?([^\n]+)/)?.[1]?.trim() || ''
const notesForCollaborator = (collaborator: string) => collaborator.trim() ? `协作人：${collaborator.trim()}` : ''

export function KeyTaskExecutionDetailView({
  project,
  task,
  subTask,
  projectMembers,
  onBack,
  canManageSchedules = false,
  canChangeAssignee = false,
  onSchedulesChanged,
  onEditSubTask,
}: Props) {
  const navigate = useNavigate()
  const [editingBaseTask, setEditingBaseTask] = useState(false)
  const collaborator = collaboratorOf(subTask.notes)
  const defaultAssigneeId = projectMembers.find((member) => member.person_name_snapshot === subTask.assignee)?.person_id ?? subTask.assignee_id ?? null

  function openWorkReport(entryIntent: WorkReportEntryIntent) {
    if (!project?.id) return
    navigate(buildWorkReportEntryUrl(project.id, subTask.id, entryIntent))
  }

  return <main className="flex-1 overflow-y-auto bg-slate-50">
    <div className="mx-auto max-w-[1380px] px-4 py-5 sm:px-6">
      <button type="button" onClick={onBack} className="text-xs font-medium text-slate-500 hover:text-blue-600">← 返回工作推进表</button>

      <header className="mt-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3"><h1 className="text-2xl font-semibold tracking-tight text-slate-900">{subTask.title}</h1><span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">{subTask.status || '未开始'}</span></div>
            <div className="mt-3 flex flex-wrap gap-x-8 gap-y-1 text-xs text-slate-500"><span>所属重点工作：{task?.key_task || '—'}</span><span>所属项目：{project?.name || '—'}</span></div>
          </div>
          {canManageSchedules && onEditSubTask && <button type="button" onClick={() => setEditingBaseTask(true)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 shadow-sm hover:border-blue-200 hover:text-blue-600">编辑关键任务</button>}
        </div>
      </header>

      <section className="mt-5 grid rounded-xl border border-slate-200 bg-white py-5 shadow-sm sm:grid-cols-2 xl:grid-cols-4" aria-label="关键任务概览">
        <SummaryItem icon="人" label="负责人" value={subTask.assignee || '未指定'} />
        <SummaryItem icon="协" label="协作人" value={collaborator || '无'} tone="green" />
        <SummaryItem icon="日" label="开始时间" value={startTimeOf(subTask.plan_time)} />
        <SummaryItem icon="态" label="状态" value={subTask.status || '未开始'} tone="green" accent />
      </section>

      <div className="mt-4 space-y-4">
        <KeyTaskSubtasksWorkspace
          subtaskId={subTask.id}
          defaultAssigneeId={defaultAssigneeId}
          members={projectMembers}
          canManage={canManageSchedules}
          onChanged={onSchedulesChanged}
          onEntry={openWorkReport}
        />
        <KeyTaskExecutionTimeline subTask={subTask} onEntry={openWorkReport} />
      </div>
    </div>

    {editingBaseTask && onEditSubTask && <KeyTaskEditDrawer subTask={subTask} members={projectMembers} canChangeAssignee={canChangeAssignee} onSave={onEditSubTask} onClose={() => setEditingBaseTask(false)} />}
  </main>
}

function SummaryItem({ icon, label, value, tone = 'blue', accent = false }: { icon: string; label: string; value: string; tone?: 'blue' | 'green'; accent?: boolean }) {
  return <div className="flex min-w-0 items-center gap-3 border-b border-slate-100 px-5 py-3 last:border-b-0 sm:[&:nth-child(odd)]:border-r xl:border-b-0 xl:border-r xl:last:border-r-0">
    <span className={`grid size-9 shrink-0 place-items-center rounded-full text-xs font-bold ${tone === 'green' ? 'bg-emerald-50 text-emerald-600' : 'bg-blue-50 text-blue-600'}`} aria-hidden="true">{icon}</span>
    <div className="min-w-0"><p className="text-xs text-slate-400">{label}</p><p className={`mt-1 truncate text-sm font-semibold ${accent ? 'text-blue-600' : 'text-slate-800'}`}>{value}</p></div>
  </div>
}

function startTimeOf(planTime?: string) {
  if (!planTime?.trim()) return '未填写'
  return planTime.match(/\d{4}[./-]\d{1,2}[./-]\d{1,2}/)?.[0] || planTime.split(/\s*(?:~|～|至|—|–)\s*/)[0] || planTime
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

  return <div className="fixed inset-0 z-50 bg-slate-900/25" onClick={onClose}>
    <aside className="ml-auto flex h-full w-full max-w-md flex-col bg-white shadow-2xl" aria-label="编辑关键任务" onClick={(event) => event.stopPropagation()}>
      <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4"><div><h2 className="text-base font-semibold text-slate-800">编辑关键任务</h2><p className="mt-1 text-xs text-slate-400">修改关键任务基础信息，不影响已有子任务。</p></div><button type="button" onClick={onClose} className="rounded p-1 text-xl leading-none text-slate-400 hover:bg-slate-100" aria-label="关闭">×</button></header>
      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
        <label className="block text-sm font-medium text-slate-700">任务名称<input value={title} onChange={(event) => setTitle(event.target.value)} disabled={saving} className={editInputClass} /></label>
        <label className="block text-sm font-medium text-slate-700">负责人<select value={assignee} onChange={(event) => setAssignee(event.target.value)} disabled={saving || !canChangeAssignee} className={editInputClass}>{memberNames.map((name) => <option key={name} value={name}>{name}</option>)}</select>{!canChangeAssignee && <span className="mt-1 block text-xs text-slate-400">当前权限不可调整负责人。</span>}</label>
        <label className="block text-sm font-medium text-slate-700">协作人<input value={collaborator} onChange={(event) => setCollaborator(event.target.value)} disabled={saving} placeholder="多人可用、分隔" className={editInputClass} /></label>
        <label className="block text-sm font-medium text-slate-700">开始时间<input value={planTime} onChange={(event) => setPlanTime(event.target.value)} disabled={saving} placeholder="例如 2026-08-01" className={editInputClass} /></label>
        <label className="block text-sm font-medium text-slate-700">状态<select value={status} onChange={(event) => setStatus(event.target.value)} disabled={saving} className={editInputClass}><option>未开始</option><option>进行中</option><option>延期</option><option>暂缓</option><option>已完成</option></select></label>
        <label className="block text-sm font-medium text-slate-700">完成标准<textarea value={criteria} onChange={(event) => setCriteria(event.target.value)} disabled={saving} rows={5} className={`${editInputClass} resize-y`} /></label>
        {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      </div>
      <footer className="flex justify-end gap-3 border-t border-slate-200 px-5 py-4"><button type="button" onClick={onClose} disabled={saving} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700">取消</button><button type="button" onClick={() => void submit()} disabled={saving} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">{saving ? '保存中…' : '保存更改'}</button></footer>
    </aside>
  </div>
}

const editInputClass = 'mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500'
