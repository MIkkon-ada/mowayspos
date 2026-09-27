import type { SubTaskWithParent } from '../../api/subtasks'
import type { Project } from '../../types'

export const MY_TASK_STATUSES = ['未开始', '进行中', '延期', '已完成', '暂缓'] as const
export type MyTaskStatus = (typeof MY_TASK_STATUSES)[number]
export type MyTaskStatusFilter = '全部' | MyTaskStatus
export type MyTaskStatusTone = 'neutral' | 'progress' | 'delayed' | 'completed' | 'paused'

export type MyTaskRow = {
  id: number
  subtask: SubTaskWithParent
  projectId: number | null
  projectName: string
  workstreamId: number
  workstreamName: string
  title: string
  completionCriteria: string
  planTime: string
  planStart: string
  planEnd: string
  planEndTimestamp: number | null
  status: MyTaskStatus
  statusTone: MyTaskStatusTone
  progressText: string
}
export type MyTaskFilters = {
  status: MyTaskStatusFilter
  projectId: number | null
  search: string
}

export type MyTaskStatusCounts = Record<MyTaskStatusFilter, number>

export type MyTaskProjectMerge = {
  rows: MyTaskRow[]
  successProjectIds: number[]
  failedProjectIds: number[]
}

const STATUS_ALIASES: Record<string, MyTaskStatus> = {
  not_started: '未开始', pending: '未开始', waiting: '未开始', '待开始': '未开始', '未启动': '未开始', '未开始': '未开始',
  in_progress: '进行中', doing: '进行中', active: '进行中', '执行中': '进行中', '进行中': '进行中',
  delayed: '延期', overdue: '延期', '已延期': '延期', '延期': '延期',
  completed: '已完成', done: '已完成', finished: '已完成', '完成': '已完成', '已完成': '已完成',
  paused: '暂缓', suspended: '暂缓', on_hold: '暂缓', '暂停': '暂缓', '已暂停': '暂缓', '暂缓': '暂缓',
}

const STATUS_TONES: Record<MyTaskStatus, MyTaskStatusTone> = {
  未开始: 'neutral',
  进行中: 'progress',
  延期: 'delayed',
  已完成: 'completed',
  暂缓: 'paused',
}

const STATUS_ORDER: Record<MyTaskStatus, number> = {
  延期: 0,
  进行中: 1,
  未开始: 2,
  暂缓: 3,
  已完成: 4,
}

export function normalizeMyTaskStatus(value?: string | null): MyTaskStatus {
  const normalized = String(value ?? '').trim().toLocaleLowerCase('zh-CN').replace(/[ -]+/g, '_')
  return STATUS_ALIASES[normalized] ?? '未开始'
}

export function getMyTaskStatusTone(status?: string | null): MyTaskStatusTone {
  return STATUS_TONES[normalizeMyTaskStatus(status)]
}

function toIsoDate(year: string, month: string, day: string): string {
  return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`
}

function normalizedPlanDates(value: string): string[] {
  const normalizedChinese = value.replace(
    /(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日/g,
    (_all, year: string, month: string, day: string) => toIsoDate(year, month, day),
  )
  return normalizedChinese.match(/\d{4}-\d{1,2}-\d{1,2}/g)?.map((date) => {
    const [year, month, day] = date.split('-')
    return toIsoDate(year, month, day)
  }) ?? []
}

export function parseMyTaskPlanTime(value?: string | null) {
  const raw = String(value ?? '').trim()
  if (!raw) return { start: '', end: '', display: '', endTimestamp: null as number | null }
  if (raw === '持续') return { start: '', end: '', display: '持续', endTimestamp: null as number | null }

  const dates = normalizedPlanDates(raw)
  if (dates.length >= 2) {
    const start = dates[0]
    const end = dates[1]
    return { start, end, display: `${start} ～ ${end}`, endTimestamp: Date.parse(`${end}T00:00:00`) }
  }
  if (dates.length === 1) {
    const date = dates[0]
    return { start: date, end: '', display: raw, endTimestamp: Date.parse(`${date}T00:00:00`) }
  }
  return { start: '', end: '', display: raw, endTimestamp: null as number | null }
}

export function getMyTaskProgressText(notes?: string | null): string {
  const lines = String(notes ?? '').replace(/\r\n/g, '\n').split('\n')
  if (/^\s*(?:协助人|协同人)\s*[:：]/.test(lines[0] ?? '')) lines.shift()
  const progress = lines.join('\n').trim()
  return progress || '暂无进展记录'
}

export function buildMyTaskRows(
  subtasks: SubTaskWithParent[],
  projects: Array<Pick<Project, 'id' | 'name'>>,
  assignee: string,
): MyTaskRow[] {
  const projectNames = new Map(projects.map((project) => [project.id, project.name]))
  const seen = new Set<number>()
  const expectedAssignee = assignee.trim()
  const rows: MyTaskRow[] = []

  for (const subtask of subtasks) {
    if (seen.has(subtask.id) || subtask.is_deleted || subtask.assignee?.trim() !== expectedAssignee) continue
    seen.add(subtask.id)
    const plan = parseMyTaskPlanTime(subtask.plan_time)
    const projectId = typeof subtask.parent_project_id === 'number' ? subtask.parent_project_id : null
    const status = normalizeMyTaskStatus(subtask.status)
    rows.push({
      id: subtask.id,
      subtask,
      projectId,
      projectName: (projectId !== null ? projectNames.get(projectId) : undefined) || subtask.parent_special_project || '未知项目',
      workstreamId: subtask.parent_task_id,
      workstreamName: subtask.parent_key_task || '未知重点工作',
      title: subtask.title || '未命名关键任务',
      completionCriteria: subtask.completion_criteria || '',
      planTime: plan.display,
      planStart: plan.start,
      planEnd: plan.end,
      planEndTimestamp: plan.endTimestamp,
      status,
      statusTone: STATUS_TONES[status],
      progressText: getMyTaskProgressText(subtask.notes),
    })
  }
  return rows
}

export function mergeMyTaskProjectResults(
  projects: Array<Pick<Project, 'id' | 'name'>>,
  results: PromiseSettledResult<SubTaskWithParent[]>[],
  assignee: string,
): MyTaskProjectMerge {
  const successfulTasks: SubTaskWithParent[] = []
  const successProjectIds: number[] = []
  const failedProjectIds: number[] = []
  results.forEach((result, index) => {
    const project = projects[index]
    if (!project) return
    if (result.status === 'fulfilled') {
      successProjectIds.push(project.id)
      successfulTasks.push(...result.value)
    } else {
      failedProjectIds.push(project.id)
    }
  })
  return {
    rows: buildMyTaskRows(successfulTasks, projects, assignee),
    successProjectIds,
    failedProjectIds,
  }
}

export function sortMyTaskRows(rows: MyTaskRow[]): MyTaskRow[] {
  return rows.map((row, index) => ({ row, index })).sort((a, b) => {
    const statusDelta = STATUS_ORDER[a.row.status] - STATUS_ORDER[b.row.status]
    if (statusDelta) return statusDelta
    const aHasEnd = a.row.planEndTimestamp !== null
    const bHasEnd = b.row.planEndTimestamp !== null
    if (aHasEnd !== bHasEnd) return aHasEnd ? -1 : 1
    if (aHasEnd && bHasEnd && a.row.planEndTimestamp !== b.row.planEndTimestamp) {
      return (a.row.planEndTimestamp ?? 0) - (b.row.planEndTimestamp ?? 0)
    }
    const projectDelta = a.row.projectName.localeCompare(b.row.projectName, 'zh-CN')
    if (projectDelta) return projectDelta
    const workstreamDelta = a.row.workstreamName.localeCompare(b.row.workstreamName, 'zh-CN')
    if (workstreamDelta) return workstreamDelta
    const idDelta = a.row.id - b.row.id
    return idDelta || a.index - b.index
  }).map(({ row }) => row)
}

function normalizedSearch(value: string): string {
  return value.trim().toLocaleLowerCase('zh-CN')
}

export function filterMyTaskRows(rows: MyTaskRow[], filters: MyTaskFilters): MyTaskRow[] {
  const query = normalizedSearch(filters.search)
  const filtered = rows.filter((row) => {
    if (filters.status !== '全部' && row.status !== filters.status) return false
    if (filters.projectId !== null && row.projectId !== filters.projectId) return false
    if (!query) return true
    return [row.title, row.completionCriteria, row.projectName, row.workstreamName, row.progressText]
      .some((value) => normalizedSearch(value).includes(query))
  })
  return sortMyTaskRows(filtered)
}

export function countMyTaskStatuses(rows: MyTaskRow[]): MyTaskStatusCounts {
  const counts: MyTaskStatusCounts = { 全部: rows.length, 未开始: 0, 进行中: 0, 延期: 0, 已完成: 0, 暂缓: 0 }
  rows.forEach((row) => { counts[row.status] += 1 })
  return counts
}

export function getMyTaskProjectOptions(rows: MyTaskRow[]): Array<{ id: number; name: string }> {
  const options = new Map<number, string>()
  rows.forEach((row) => { if (row.projectId !== null) options.set(row.projectId, row.projectName) })
  return [...options].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
}

export function paginateMyTaskRows<T>(rows: T[], requestedPage: number, pageSize: number) {
  const safePageSize = [10, 20, 50].includes(pageSize) ? pageSize : 10
  const totalPages = Math.max(1, Math.ceil(rows.length / safePageSize))
  const page = Math.min(Math.max(1, requestedPage), totalPages)
  const start = (page - 1) * safePageSize
  return { items: rows.slice(start, start + safePageSize), page, pageSize: safePageSize, total: rows.length, totalPages }
}
