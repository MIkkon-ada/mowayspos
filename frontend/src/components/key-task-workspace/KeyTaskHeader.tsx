import type { KeyTaskWorkspace } from '../../api/keyTaskWorkspace'
import { formatKeyTaskPlanTime, statusTone } from './workspaceFormat'

export function KeyTaskHeader({ workspace, onSubmitUpdate, onConfirmCompletion, onReopen, onChangeRisk }: { workspace: KeyTaskWorkspace; onSubmitUpdate?: () => void; onConfirmCompletion: () => void; onReopen: () => void; onChangeRisk: () => void }) {
  const { key_task: task, project, workstream, completion_eligibility: eligibility, permissions } = workspace
  const isCompleted = task.status === '已完成'

  return <header className="border-y border-blue-200 bg-blue-50 px-5 py-6 shadow-sm sm:px-7">
    <nav className="text-sm text-slate-500" aria-label="关键任务路径">
      <span>{project?.name || '项目'}</span><span className="mx-2">/</span><span>{workstream?.name || '重点工作'}</span><span className="mx-2">/</span><span className="text-slate-700">关键任务</span>
    </nav>
    <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{task.title}</h1>
          <span className={`rounded-sm px-3 py-1 text-sm font-semibold ${statusTone(task.status)}`}>{task.status || '未开始'}</span>
          {task.risk_note && <span title={task.risk_note} className="rounded-sm bg-orange-50 px-3 py-1 text-sm font-semibold text-orange-700">有风险</span>}
        </div>
        <div className="mt-4 grid gap-x-8 gap-y-3 text-sm text-slate-600 sm:grid-cols-3">
          <span className="flex items-center gap-2"><i className="grid size-7 place-items-center rounded-full bg-blue-600 text-xs font-bold text-white not-italic">{(task.owner.name || '?').slice(0, 1)}</i>负责人：{task.owner.name || '未指定'}</span>
          <span>协同人：{task.collaborators.length ? task.collaborators.map((person) => person.name).join('、') : '—'}</span>
          <span>计划时间：{formatKeyTaskPlanTime(task)}</span>
          {task.risk_note && <span className="text-orange-700 sm:col-span-3">风险原因：{task.risk_note}</span>}
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        {permissions.can_submit_update && <button type="button" onClick={onSubmitUpdate} className="rounded-sm bg-blue-700 px-4 py-2 text-sm font-semibold text-white shadow-sm">提交更新</button>}
        {permissions.can_manage_risk && <button type="button" onClick={onChangeRisk} className="rounded-sm border border-orange-300 bg-white px-4 py-2 text-sm font-semibold text-orange-700">{task.risk_note ? '解除风险' : '标记风险'}</button>}
        {permissions.can_confirm_completion && !isCompleted && eligibility.state === 'eligible' && <button type="button" onClick={onConfirmCompletion} className="rounded-sm border border-emerald-300 bg-white px-4 py-2 text-sm font-semibold text-emerald-700">确认完成</button>}
        {permissions.can_operate && isCompleted && <button type="button" onClick={onReopen} className="rounded-sm border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700">重新打开</button>}
        <details className="app-disclosure relative">
          <summary className="cursor-pointer list-none rounded-sm border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700">更多操作</summary>
          <div className="absolute right-0 z-10 mt-2 w-56 rounded-lg border border-slate-200 bg-white p-2 shadow-lg">
            <p className="px-2 py-1 text-xs text-slate-500">{eligibility.state === 'eligible' ? '所有有效任务计划已完成，等待负责人确认。' : eligibility.state === 'no_execution_plan' ? '尚无有效任务计划；不会自动完成。' : '任务计划尚未全部完成。'}</p>
          </div>
        </details>
      </div>
    </div>
  </header>
}
