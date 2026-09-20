import type { SubTaskItem, TaskItem } from '../../types'

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
          <div className="mt-2 flex gap-4 text-xs text-slate-500"><span>负责人：{task.owner || '—'}</span><span>计划时间：{task.plan_time || '—'}</span></div>
        </div>
        <div className="divide-y divide-slate-100">
          {subtasks.length ? subtasks.map((subtask) => <button type="button" key={subtask.id} onClick={() => onOpenSubTask(subtask)} className="w-full px-4 py-3 text-left active:bg-slate-50">
            <div className="flex items-start justify-between gap-3"><span className="min-w-0 text-sm font-medium leading-5 text-slate-700">{subtask.title}</span><span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${statusClass(subtask.status || '')}`}>{subtask.status || '未开始'}</span></div>
            <p className="mt-1 text-xs text-slate-400">负责人：{subtask.assignee || '—'} · 计划时间：{subtask.plan_time || '—'}</p>
          </button>) : <p className="px-4 py-3 text-xs text-slate-400">暂无关键任务</p>}
        </div>
      </article>
    })}
  </section>
}
