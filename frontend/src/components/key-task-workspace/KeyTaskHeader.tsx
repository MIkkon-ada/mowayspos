import type { ReactNode } from 'react'
import type { KeyTaskWorkspace } from '../../api/keyTaskWorkspace'
import { formatKeyTaskPlanTime, statusTone } from './workspaceFormat'

type MetaItemProps = {
  label: string
  value: string
  marker: ReactNode
  markerTone?: 'blue' | 'slate'
}

function MetaItem({ label, value, marker, markerTone = 'slate' }: MetaItemProps) {
  const markerClass = markerTone === 'blue'
    ? 'bg-blue-600 text-white'
    : 'bg-slate-100 text-slate-500'

  return <div className="flex min-h-8 min-w-0 items-center gap-2.5 text-sm leading-5 text-slate-700">
    <span className={`grid size-7 shrink-0 place-items-center rounded-full text-xs font-semibold ${markerClass}`} aria-hidden="true">{marker}</span>
    <span className="shrink-0 text-slate-500">{label}</span>
    <span className="truncate font-medium text-slate-800">{value}</span>
  </div>
}

export function KeyTaskHeader({ workspace, onSubmitUpdate, onConfirmCompletion, onReopen }: { workspace: KeyTaskWorkspace; onSubmitUpdate?: () => void; onConfirmCompletion: () => void; onReopen: () => void }) {
  const { key_task: task, project, workstream, completion_eligibility: eligibility, permissions } = workspace
  const isCompleted = task.status === '已完成'
  const collaborators = task.collaborators.length ? task.collaborators.map((person) => person.name).join('、') : '—'

  return <header className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
    <nav className="truncate text-sm text-slate-500" aria-label="关键任务路径">
      <span>{project?.name || '项目'}</span><span className="mx-2">/</span><span>{workstream?.name || '重点工作'}</span><span className="mx-2">/</span><span className="text-slate-700">关键任务</span>
    </nav>

    <div className="mt-4 flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">{task.title}</h1>
          <span className={`rounded-full px-3 py-1 text-sm font-semibold ${statusTone(task.status)}`}>{task.status || '未开始'}</span>
        </div>
      </div>

      <div className="flex shrink-0 flex-wrap gap-2">
        {permissions.can_submit_update && <button type="button" onClick={onSubmitUpdate} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white">提交更新</button>}
        {permissions.can_confirm_completion && !isCompleted && eligibility.state === 'eligible' && <button type="button" onClick={onConfirmCompletion} className="rounded-lg border border-emerald-300 px-4 py-2 text-sm font-semibold text-emerald-700">确认完成</button>}
        {permissions.can_operate && isCompleted && <button type="button" onClick={onReopen} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700">重新打开</button>}
      </div>
    </div>

    <div className="mt-5 grid items-center gap-3 border-t border-slate-100 pt-4 sm:grid-cols-2 xl:grid-cols-3" aria-label="关键任务元信息">
      <MetaItem label="负责人" value={task.owner.name || '未指定'} marker={(task.owner.name || '?').slice(0, 1)} markerTone="blue" />
      <MetaItem label="协同人" value={collaborators} marker="协" />
      <MetaItem label="计划时间" value={formatKeyTaskPlanTime(task)} marker="时" />
    </div>
  </header>
}
