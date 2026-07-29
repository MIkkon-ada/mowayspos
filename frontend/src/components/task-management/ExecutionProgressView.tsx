import type { Project, SubTaskItem, TaskItem } from '../../types'

type Props = {
  project: Project | null
  tasks: TaskItem[]
  subTasks: Record<number, SubTaskItem[]>
  onOpenSubTask: (item: SubTaskItem) => void
}

const isDone = (status?: string) => status === '已完成'
const progressOf = (rows: SubTaskItem[]) => rows.length ? Math.round(rows.filter((row) => isDone(row.status)).length / rows.length * 100) : 0
const splitLines = (value?: string) => (value || '').split(/\n|；|;/).map((item) => item.trim()).filter(Boolean)
const collaboratorOf = (notes?: string) => notes?.match(/协同人[：:]?([^\n]+)/)?.[1]?.trim() || '—'
const taskProgress = (status?: string) => isDone(status) ? 100 : status === '进行中' || status === '推进中' ? 50 : 0

export function ExecutionProgressView({ project, tasks, subTasks, onOpenSubTask }: Props) {
  const criteria = splitLines(project?.expected_outcomes)

  return (
    <div className="flex-1 overflow-y-auto bg-slate-50">
      <div className="mx-auto max-w-[1280px] space-y-4 px-6 py-5">
        <section className="grid grid-cols-1 overflow-hidden rounded-lg border border-slate-200 bg-white lg:grid-cols-2">
          <div className="px-5 py-4 lg:border-r lg:border-slate-100">
              <div className="flex items-center gap-2">
                <h2 className="truncate text-xl font-semibold tracking-tight text-slate-900">{project?.name || '工作推进表'}</h2>
                <span className="rounded bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">进行中</span>
              </div>
              <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
                <span>项目负责人：{project?.owners?.join('、') || '—'}</span>
                <span>企业教练：{project?.coaches?.join('、') || '—'}</span>
                <span>项目周期：{project?.start_date || '—'} 至 {project?.end_date || '—'}</span>
              </div>
          </div>
          <div className="px-5 py-4">
          <h3 className="text-sm font-semibold text-slate-800">项目评价标准</h3>
          <ol className="mt-2 space-y-1.5 text-sm text-slate-600">
            {criteria.length ? criteria.map((item, index) => <li key={item}><b className="mr-1 text-blue-600">{index + 1}.</b>{item}</li>) : <li className="text-slate-400">暂无评价标准</li>}
          </ol>
          </div>
        </section>

        <div className="flex items-baseline justify-between pt-1"><h3 className="text-base font-semibold text-slate-900">重点工作</h3><span className="text-xs text-slate-400">共 {tasks.length} 项</span></div>
        {tasks.map((task, index) => {
          const rows = subTasks[task.id] ?? []
          const value = progressOf(rows)
          return <section className="overflow-hidden rounded-lg border border-slate-200 bg-white" key={task.id}>
            <header className="flex items-center justify-between gap-5 border-b border-slate-100 px-5 py-3">
              <div className="flex min-w-0 items-center gap-3">
                <span className="inline-flex size-6 shrink-0 items-center justify-center rounded bg-blue-50 text-xs font-semibold text-blue-700">{String(index + 1).padStart(2, '0')}</span>
                <h4 className="truncate text-sm font-semibold text-slate-900">{task.key_task}</h4>
                <span className="shrink-0 text-xs text-slate-500">负责人：{task.owner || '—'}</span>
              </div>
              <div className="flex shrink-0 items-center gap-2.5 text-xs text-slate-500"><span>进度 <b className="text-blue-600">{value}%</b></span><div className="h-1.5 w-20 rounded-full bg-slate-200"><i className="block h-full rounded-full bg-blue-600" style={{ width: `${value}%` }} /></div></div>
            </header>
            <div className="border-b border-slate-100 bg-slate-50 px-5 py-2 text-xs leading-5 text-slate-600"><b className="mr-2 font-medium text-slate-700">评价标准</b>{task.completion_standard || '—'}</div>
            <div className="grid grid-cols-[minmax(240px,2fr)_100px_120px_130px_120px_120px] border-b border-slate-100 px-5 py-2 text-xs font-medium text-slate-400"><span>关键任务</span><span>负责人</span><span>协同人</span><span>计划时间</span><span>人员状态</span><span>进度</span></div>
            {rows.length ? rows.map((row) => <button type="button" onClick={() => onOpenSubTask(row)} className="grid w-full grid-cols-[minmax(240px,2fr)_100px_120px_130px_120px_120px] items-center border-b border-slate-100 px-5 py-3 text-left text-sm last:border-b-0 hover:bg-blue-50/60" key={row.id}>
              <span className="truncate font-medium text-slate-800">{row.title}</span><span className="truncate text-slate-600">{row.assignee || '—'}</span><span className="truncate text-slate-600">{collaboratorOf(row.notes)}</span><span className="text-slate-600">{row.plan_time || '—'}</span><span><i className="not-italic rounded bg-emerald-50 px-1.5 py-0.5 text-xs text-emerald-700">{isDone(row.status) ? '已完成' : '正常推进'}</i></span><span className="flex items-center gap-2"><i className="h-1.5 w-12 overflow-hidden rounded-full bg-slate-200"><i className="block h-full bg-blue-600" style={{ width: `${taskProgress(row.status)}%` }} /></i><b className="text-xs font-medium text-slate-600">{taskProgress(row.status)}%</b></span>
            </button>) : <div className="px-5 py-4 text-sm text-slate-400">暂无关键任务</div>}
          </section>
        })}
      </div>
    </div>
  )
}
