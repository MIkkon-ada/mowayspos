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
const PLACEHOLDER_TEXTS = new Set(['未填写项目目标', '未填写评价标准', '暂无关键任务', EMPTY_TEXT])
const TABLE_HEADERS = [
  { label: '目标', width: 'w-[200px]' },
  { label: '重点工作', width: 'w-[220px]' },
  { label: '评价标准', width: 'w-[260px]' },
  { label: '序号', width: 'w-[64px]' },
  { label: '关键任务', width: 'w-[360px]' },
  { label: '责任人', width: 'w-[120px]' },
  { label: '计划开始时间', width: 'w-[140px]' },
  { label: '计划结束时间', width: 'w-[140px]' },
]

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

function renderPlanTableText(value: string) {
  if (PLACEHOLDER_TEXTS.has(value)) {
    return <span className="plan-table-placeholder text-[10px] text-slate-300">{value}</span>
  }
  return value
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
  const tableTitle = project?.name?.trim()
    ? `${project.name.trim()}目标与重点工作计划表`
    : '目标与重点工作计划表'

  if (tasks.length === 0) {
    return (
      <div className="flex h-56 items-center justify-center border border-slate-300 bg-white">
        <div className="text-center">
          <div className="text-sm font-semibold text-slate-500">暂无工作推进表数据</div>
          <div className="mt-1 text-xs text-slate-400">可先在项目立项阶段填写工作推进表雏形，或在执行视图中新建重点工作。</div>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-2 flex items-end justify-between px-1">
        <div className="flex-1 text-center">
          <div className="text-base font-bold tracking-wide text-slate-900">{tableTitle}</div>
          <div className="mt-0.5 text-[11px] text-slate-400">同一套项目 / 重点工作 / 关键任务数据的类 Excel 展开视图</div>
        </div>
        {loading && <span className="text-xs font-semibold text-amber-600">关键任务加载中…</span>}
      </div>

      <div className="overflow-x-auto border border-slate-300 bg-white">
        <table className="plan-table-excel min-w-[1504px] w-full border-collapse text-[11px] leading-tight">
          <thead className="bg-slate-100">
            <tr>
              {TABLE_HEADERS.map((header) => (
                <th key={header.label} className={`plan-table-cell h-7 border border-slate-300 px-2 py-1 text-left font-semibold text-slate-700 ${header.width}`}>
                  {header.label}
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
                <tr key={`${task.id}-${subtask?.id ?? 'empty'}-${index}`} className="h-7 align-top hover:bg-slate-50/70">
                  {index === 0 && (
                    <td rowSpan={rows.length} className="plan-table-cell w-[200px] whitespace-pre-wrap border border-slate-300 bg-slate-50 px-2 py-1 leading-snug text-slate-700">
                      {renderPlanTableText(objective)}
                    </td>
                  )}
                  {row.showTaskCells && (
                    <>
                      <td rowSpan={row.taskRowSpan} className="plan-table-cell w-[220px] whitespace-pre-wrap border border-slate-300 px-2 py-1 font-semibold leading-snug text-slate-800">
                        {renderPlanTableText(textOrFallback(task.key_task, EMPTY_TEXT))}
                      </td>
                      <td rowSpan={row.taskRowSpan} className="plan-table-cell w-[260px] whitespace-pre-wrap border border-slate-300 px-2 py-1 leading-snug text-slate-600">
                        {renderPlanTableText(standard)}
                      </td>
                    </>
                  )}
                  <td className="plan-table-cell w-[64px] border border-slate-300 px-2 py-1 text-center font-semibold text-slate-500">
                    {index + 1}
                  </td>
                  <td className="plan-table-cell w-[360px] border border-slate-300 px-2 py-1 text-left text-slate-700">
                    {renderPlanTableText(subtask ? subtask.title || '暂无关键任务' : '暂无关键任务')}
                  </td>
                  <td className="plan-table-cell w-[120px] border border-slate-300 px-2 py-1 text-slate-600">
                    {renderPlanTableText(owner)}
                  </td>
                  <td className="plan-table-cell w-[140px] border border-slate-300 px-2 py-1 text-slate-500">
                    {renderPlanTableText(planTime.start)}
                  </td>
                  <td className="plan-table-cell w-[140px] border border-slate-300 px-2 py-1 text-slate-500">
                    {renderPlanTableText(planTime.end)}
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
