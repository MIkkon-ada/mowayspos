import type { Project, SubTaskItem, TaskItem } from '../../types'

type Props = {
  project: Project | null
  tasks: TaskItem[]
  taskSubMap: Record<number, SubTaskItem[]>
  loading?: boolean
}

type ParsedPlanTime = {
  start: string
  end: string
}

type PlanRow = {
  task: TaskItem
  subtask: SubTaskItem | null
  taskRowSpan: number
  showTaskCells: boolean
}

const EMPTY_TEXT = '—'

export function parsePlanTimeRange(value?: string | null): ParsedPlanTime {
  const raw = String(value ?? '').trim()
  if (!raw) return { start: EMPTY_TEXT, end: EMPTY_TEXT }
  if (raw === '持续') return { start: '持续', end: EMPTY_TEXT }

  const fullDateRange = raw.match(/(\d{4}-\d{1,2}-\d{1,2})\s*(?:~|至|-)\s*(\d{4}-\d{1,2}-\d{1,2})/)
  if (fullDateRange) return { start: fullDateRange[1], end: fullDateRange[2] }

  const monthDayRange = raw.match(/(\d{1,2}月\d{1,2}日)\s*(?:~|至|-)\s*(\d{1,2}月\d{1,2}日)/)
  if (monthDayRange) return { start: monthDayRange[1], end: monthDayRange[2] }

  return { start: raw, end: EMPTY_TEXT }
}

function textOrFallback(value: string | undefined | null, fallback: string): string {
  const text = String(value ?? '').trim()
  return text || fallback
}

function buildPlanRows(tasks: TaskItem[], taskSubMap: Record<number, SubTaskItem[]>): PlanRow[] {
  const rows: PlanRow[] = []
  tasks.forEach((task) => {
    const subtasks = taskSubMap[task.id] ?? []
    if (subtasks.length === 0) {
      rows.push({ task, subtask: null, taskRowSpan: 1, showTaskCells: true })
      return
    }
    subtasks.forEach((subtask, index) => rows.push({
      task,
      subtask,
      taskRowSpan: subtasks.length,
      showTaskCells: index === 0,
    }))
  })
  return rows
}

export function PlanTableView({ project, tasks, taskSubMap, loading = false }: Props) {
  const rows = buildPlanRows(tasks, taskSubMap)
  const objective = project
    ? textOrFallback(project.objectives || project.description, '未填写项目目标')
    : '未填写项目目标'

  if (tasks.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-2xl border border-slate-200 bg-white">
        <div className="text-center">
          <div className="text-sm font-semibold text-slate-500">暂无工作推进表数据</div>
          <div className="mt-1 text-xs text-slate-400">可先在项目立项阶段填写工作推进表雏形，或在执行视图中新建重点工作。</div>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div>
          <div className="text-sm font-bold text-slate-800">计划表视图</div>
          <div className="mt-0.5 text-xs text-slate-400">同一套项目 / 重点工作 / 关键任务数据的类 Excel 展开视图</div>
        </div>
        {loading && <span className="text-xs font-semibold text-amber-600">关键任务加载中…</span>}
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-[980px] w-full text-xs" style={{ borderCollapse: 'collapse' }}>
          <thead className="bg-slate-50">
            <tr>
              {['目标', '重点工作', '评价标准', '序号', '关键任务', '责任人', '计划开始时间', '计划结束时间'].map((header) => (
                <th key={header} className="border-b border-r border-slate-200 px-3 py-2 text-left font-bold text-slate-600 last:border-r-0">
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => {
              const { task, subtask } = row
              const planSource = subtask ? subtask.plan_time || task.plan_time : task.plan_time
              const planTime = parsePlanTimeRange(planSource)
              const standard = textOrFallback(task.completion_standard || task.key_achievement, '未填写评价标准')
              const owner = textOrFallback(subtask ? subtask.assignee || task.owner : task.owner, EMPTY_TEXT)
              return (
                <tr key={`${task.id}-${subtask?.id ?? 'empty'}-${index}`} className="align-top hover:bg-slate-50/70">
                  {index === 0 && (
                    <td rowSpan={rows.length} className="w-[180px] whitespace-pre-wrap border-b border-r border-slate-200 bg-sky-50/40 px-3 py-2 leading-relaxed text-slate-700">
                      {objective}
                    </td>
                  )}
                  {row.showTaskCells && (
                    <>
                      <td rowSpan={row.taskRowSpan} className="w-[180px] whitespace-pre-wrap border-b border-r border-slate-200 px-3 py-2 font-semibold leading-relaxed text-slate-800">
                        {textOrFallback(task.key_task, EMPTY_TEXT)}
                      </td>
                      <td rowSpan={row.taskRowSpan} className="w-[180px] whitespace-pre-wrap border-b border-r border-slate-200 px-3 py-2 leading-relaxed text-slate-600">
                        {standard}
                      </td>
                    </>
                  )}
                  <td className="w-[56px] border-b border-r border-slate-200 px-3 py-2 text-center font-semibold text-slate-500">
                    {index + 1}
                  </td>
                  <td className="min-w-[220px] border-b border-r border-slate-200 px-3 py-2 text-left text-slate-700">
                    {subtask ? subtask.title || '暂无关键任务' : '暂无关键任务'}
                  </td>
                  <td className="w-[120px] border-b border-r border-slate-200 px-3 py-2 text-slate-600">
                    {owner}
                  </td>
                  <td className="w-[120px] border-b border-r border-slate-200 px-3 py-2 text-slate-500">
                    {planTime.start}
                  </td>
                  <td className="w-[120px] border-b border-slate-200 px-3 py-2 text-slate-500">
                    {planTime.end}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
