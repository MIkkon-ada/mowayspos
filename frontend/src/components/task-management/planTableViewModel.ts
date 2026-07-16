import type { Project, SubTaskItem, TaskItem } from '../../types'

export const EMPTY_PLAN_CELL = '—'
export const DEFAULT_PLAN_TABLE_ZOOM = 100
export const MIN_PLAN_TABLE_ZOOM = 50
export const MAX_PLAN_TABLE_ZOOM = 160
export const PLAN_TABLE_ZOOM_STEP = 10

export const PLAN_TABLE_BUSINESS_HEADERS = [
  '目标',
  '重点工作',
  '评价标准',
  '序号',
  '关键任务',
  '责任人',
  '计划开始时间',
  '计划结束时间',
  '协同人',
  '完成情况',
  '备注',
  '项目经理',
  '重点工作计划开始时间',
  '重点工作计划结束时间',
] as const

export const PLAN_TABLE_COLUMN_WIDTHS = [
  210, 230, 260, 56, 330, 110, 130, 130, 140, 260, 220, 110, 140, 140,
] as const

export const PLAN_TABLE_ROW_NUMBER_WIDTH = 48
export const PLAN_TABLE_NATURAL_WIDTH = PLAN_TABLE_ROW_NUMBER_WIDTH
  + PLAN_TABLE_COLUMN_WIDTHS.reduce((total, width) => total + width, 0)

export type ParsedPlanTime = {
  start: string
  end: string
}

export type ParsedAssistingPerson = {
  assistingPerson: string
  remainingNotes: string
}

export type PlanTableRow = {
  task: TaskItem
  subtask: SubTaskItem | null
  sequence: number
  objective: string
  objectiveRowSpan: number
  showObjective: boolean
  taskRowSpan: number
  showTaskCells: boolean
  keyTask: string
  responsible: string
  planStart: string
  planEnd: string
  assistingPerson: string
  status: string
  statusTone: 'neutral' | 'blue' | 'green' | 'red' | 'amber'
  completionNote: string
  remarks: string
  projectManager: string
  taskPlanStart: string
  taskPlanEnd: string
}

export type BuildPlanRowsInput = {
  project: Project | null
  tasks: TaskItem[]
  taskSubMap: Record<number, SubTaskItem[]>
  searchText?: string
}

export function clampPlanTableZoom(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_PLAN_TABLE_ZOOM
  return Math.min(MAX_PLAN_TABLE_ZOOM, Math.max(MIN_PLAN_TABLE_ZOOM, Math.round(value)))
}

export function normalizeStoredPlanTableZoom(value: string | null): number {
  if (value === null || !value.trim()) return DEFAULT_PLAN_TABLE_ZOOM
  const parsed = Number(value)
  return Number.isFinite(parsed) ? clampPlanTableZoom(parsed) : DEFAULT_PLAN_TABLE_ZOOM
}

export function calculatePlanTableFitZoom(
  canvasWidth: number,
  naturalTableWidth = PLAN_TABLE_NATURAL_WIDTH,
): number {
  if (!Number.isFinite(canvasWidth) || canvasWidth <= 0 || naturalTableWidth <= 0) {
    return DEFAULT_PLAN_TABLE_ZOOM
  }
  return Math.min(100, clampPlanTableZoom(Math.floor(canvasWidth / naturalTableWidth * 100)))
}

export function parsePlanTimeRange(value?: string | null): ParsedPlanTime {
  const raw = String(value ?? '').trim()
  if (!raw) return { start: EMPTY_PLAN_CELL, end: EMPTY_PLAN_CELL }
  if (raw === '持续') return { start: '持续', end: EMPTY_PLAN_CELL }

  const fullDateRange = raw.match(/(\d{4}-\d{1,2}-\d{1,2})\s*(?:~|～|至|到|—|–)\s*(\d{4}-\d{1,2}-\d{1,2})/)
  if (fullDateRange) return { start: fullDateRange[1], end: fullDateRange[2] }

  const monthDayRange = raw.match(/(\d{1,2}月\d{1,2}日)\s*(?:~|～|至|到|—|–)\s*(\d{1,2}月\d{1,2}日)/)
  if (monthDayRange) return { start: monthDayRange[1], end: monthDayRange[2] }

  const yearMonthRange = raw.match(/(\d{4}(?:年|-)?\d{1,2}月?)\s*(?:~|～|至|到|—|–)\s*(\d{4}(?:年|-)?\d{1,2}月?)/)
  if (yearMonthRange) return { start: yearMonthRange[1], end: yearMonthRange[2] }

  return { start: raw, end: EMPTY_PLAN_CELL }
}

export function parseAssistingPerson(notes?: string | null): ParsedAssistingPerson {
  const normalized = String(notes ?? '').replace(/\r\n/g, '\n').trim()
  if (!normalized) return { assistingPerson: EMPTY_PLAN_CELL, remainingNotes: '' }
  const lines = normalized.split('\n')
  const firstLine = lines[0].trim()
  const matched = firstLine.match(/^(?:协助人|协同人)\s*[:：]\s*(.*)$/)
  if (!matched) {
    return { assistingPerson: EMPTY_PLAN_CELL, remainingNotes: normalized }
  }
  return {
    assistingPerson: matched[1].trim() || EMPTY_PLAN_CELL,
    remainingNotes: lines.slice(1).join('\n').trim(),
  }
}

function textOrFallback(value: unknown, fallback: string): string {
  const text = String(value ?? '').trim()
  return text || fallback
}

function normalizedStatus(value?: string | null): string {
  return String(value ?? '').trim().toLowerCase().replace(/\s+/g, '_')
}

export function getPlanStatusLabel(value?: string | null): string {
  const normalized = normalizedStatus(value)
  if (['completed', 'complete', 'done', '已完成', '完成'].includes(normalized)) return '已完成'
  if (['in_progress', 'progress', '推进中', '进行中'].includes(normalized)) return '进行中'
  if (['delayed', '延期', '已延期'].includes(normalized)) return '延期'
  if (['paused', '暂停', '暂缓', '已暂停'].includes(normalized)) return '暂缓'
  if (['not_started', 'notstarted', '未开始', '未启动'].includes(normalized)) return '未开始'
  return textOrFallback(value, '未开始')
}

export function getPlanStatusTone(status: string): PlanTableRow['statusTone'] {
  if (status === '已完成') return 'green'
  if (status === '进行中') return 'blue'
  if (status === '延期') return 'red'
  if (status === '暂缓') return 'amber'
  return 'neutral'
}

function includesSearch(values: unknown[], searchText: string): boolean {
  const query = searchText.trim().toLocaleLowerCase('zh-CN')
  if (!query) return true
  return values.some((value) => String(value ?? '').toLocaleLowerCase('zh-CN').includes(query))
}

function taskMatchesSearch(task: TaskItem, project: Project | null, searchText: string): boolean {
  return includesSearch([
    task.key_task,
    task.completion_standard,
    task.key_achievement,
    task.owner,
    task.collaborators,
    ...(project?.owners ?? []),
  ], searchText)
}

function subtaskMatchesSearch(subtask: SubTaskItem, searchText: string): boolean {
  return includesSearch([
    subtask.title,
    subtask.assignee,
    subtask.notes,
  ], searchText)
}

export function buildPlanRows({
  project,
  tasks,
  taskSubMap,
  searchText = '',
}: BuildPlanRowsInput): PlanTableRow[] {
  const objective = textOrFallback(project?.objectives || project?.description, '未填写项目目标')
  const projectManagers = project?.owners?.filter(Boolean).join('、') || ''
  const query = searchText.trim()
  const groupedRows: Array<Omit<PlanTableRow, 'sequence' | 'objectiveRowSpan' | 'showObjective'>> = []

  tasks.forEach((task) => {
    const allSubtasks = taskSubMap[task.id] ?? []
    const taskMatched = query ? taskMatchesSearch(task, project, query) : true
    const visibleSubtasks = query && !taskMatched
      ? allSubtasks.filter((subtask) => subtaskMatchesSearch(subtask, query))
      : allSubtasks

    if (query && !taskMatched && visibleSubtasks.length === 0) return

    const taskRows: Array<SubTaskItem | null> = visibleSubtasks.length > 0 ? visibleSubtasks : [null]
    const taskPlanTime = parsePlanTimeRange(task.plan_time)
    const taskRowSpan = taskRows.length

    taskRows.forEach((subtask, taskIndex) => {
      const parsedNotes = parseAssistingPerson(subtask?.notes)
      const planTime = parsePlanTimeRange(subtask?.plan_time || task.plan_time)
      const status = getPlanStatusLabel(subtask?.status || task.status)
      groupedRows.push({
        task,
        subtask,
        objective,
        taskRowSpan,
        showTaskCells: taskIndex === 0,
        keyTask: subtask ? textOrFallback(subtask.title, '暂无关键任务') : '暂无关键任务',
        responsible: subtask
          ? textOrFallback(subtask.assignee || task.owner, EMPTY_PLAN_CELL)
          : EMPTY_PLAN_CELL,
        planStart: planTime.start,
        planEnd: planTime.end,
        assistingPerson: subtask ? parsedNotes.assistingPerson : EMPTY_PLAN_CELL,
        status,
        statusTone: getPlanStatusTone(status),
        completionNote: subtask ? parsedNotes.remainingNotes : '',
        remarks: EMPTY_PLAN_CELL,
        projectManager: projectManagers || textOrFallback(task.owner, EMPTY_PLAN_CELL),
        taskPlanStart: taskPlanTime.start,
        taskPlanEnd: taskPlanTime.end,
      })
    })
  })

  const objectiveRowSpan = groupedRows.length
  return groupedRows.map((row, index) => ({
    ...row,
    sequence: index + 1,
    objectiveRowSpan,
    showObjective: index === 0,
  }))
}
