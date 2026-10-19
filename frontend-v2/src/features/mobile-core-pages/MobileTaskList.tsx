import type { SubTaskItem, TaskItem } from '../../types'
import { getPlanStatusMarkers, hasUnconfirmedPlanDate } from '../../components/task-management/planTableViewModel'

type Props = {
  tasks: TaskItem[]
  subTasksByTaskId: Record<number, SubTaskItem[]>
  loading: boolean
  onOpenSubTask: (item: SubTaskItem) => void
}

function statusClass(status: string) {
  if (status.includes('延期')) return 'bg-red-50 text-red-700'
  if (status.includes('完成')) return 'bg-emerald-50 text-emerald-700'
  if (status.includes('暂')) return 'bg-amber-50 text-amber-700'
  return 'bg-blue-50 text-blue-700'
}

export function MobileTaskList({ tasks, subTasksByTaskId, loading, onOpenSubTask }: Props) {
  if (loading) return <div className="px-4 py-10 text-center text-sm text-slate-400">加载中...</div>
  if (!tasks.length) return <div className="px-4 py-10 text-center text-sm text-slate-400">当前筛选条件下没有重点工作</div>
  return <section className="space-y-3 px-4 pb-24" aria-label="手机任务列表">
    {tasks.map((task) => {
      const subtasks = subTasksByTaskId[task.id] ?? []
      return <article key={task.id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 px-4 py-3">
          <div className="flex items-start justify-between gap-3"><h2 className="min-w-0 text-sm font-bold leading-5 text-slate-800">{task.key_task || '未命名重点工作'}</h2><span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${statusClass(task.status || '')}`}>{task.status || '进行中'}</span></div>
          <div className="mt-2 space-y-0.5 break-words text-xs text-slate-500"><p>负责人：{task.owner || '—'}</p><p>计划时间：{task.plan_time || '—'}</p></div>
        </div>
        <div className="divide-y divide-slate-100">
          {subtasks.length ? subtasks.map((subtask) => {
            const confirmedProgress = subtask.latest_confirmed_progress?.summary?.trim() || subtask.latest_confirmed_submission?.summary?.trim()
            const confirmedNextStep = subtask.latest_confirmed_progress?.next_step?.trim() || subtask.latest_next_step?.trim()
            const progressFallback = subtask.has_any_submission === false ? '尚未汇报' : '暂无已确认进展'
            const markers = getPlanStatusMarkers(subtask, task.status).filter((marker) => ['overdue', 'risk'].includes(marker.kind))
            return <button type="button" key={subtask.id} onClick={() => onOpenSubTask(subtask)} className="w-full px-4 py-3 text-left active:bg-slate-50">
            <div className="flex items-start justify-between gap-3"><span className="min-w-0 break-words text-sm font-medium leading-5 text-slate-700">{subtask.title}</span><span className="flex shrink-0 flex-wrap justify-end gap-1"><span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${statusClass(subtask.status || '')}`}>{subtask.status || '未开始'}</span>{hasUnconfirmedPlanDate(subtask, task.status) && <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700">待确认日期</span>}</span></div>
            <div className="mt-1 space-y-0.5 break-words text-xs text-slate-400"><p>负责人：{subtask.assignee || '—'}</p><p>计划时间：{subtask.plan_time || '—'}</p></div>
            {markers.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{markers.map((marker) => <span key={marker.kind} className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${marker.kind === 'overdue' ? 'bg-rose-50 text-rose-700' : 'bg-amber-50 text-amber-700'}`}>{marker.label}</span>)}</div>}
            <p className="mt-2 break-words whitespace-pre-line text-xs leading-5 text-slate-600"><span className="font-semibold text-slate-500">最新进展：</span>{confirmedProgress || progressFallback}</p>
            {subtask.latest_confirmed_progress?.confirmed_at && <p className="mt-0.5 text-[10px] text-slate-400">确认时间：{subtask.latest_confirmed_progress.confirmed_at.slice(0, 10)}</p>}
            <p className="mt-1 break-words whitespace-pre-line text-xs leading-5 text-slate-600"><span className="font-semibold text-slate-500">下一步：</span>{confirmedNextStep || '—'}</p>
          </button>}) : <p className="px-4 py-3 text-xs text-slate-400">暂无关键任务</p>}
        </div>
      </article>
    })}
  </section>
}
