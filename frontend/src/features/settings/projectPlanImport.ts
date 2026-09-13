import type { BatchImportRow } from '../../api/projects'

export type ProjectPlanImportRow = Omit<Required<BatchImportRow>, 'workstream'> & {
  work_area: string
}

export type ProjectPlanImportError = {
  row: number
  message: string
}

export type ProjectPlanImportResult = {
  rows: ProjectPlanImportRow[]
  errors: ProjectPlanImportError[]
  headerRow: number | null
}

type ImportField = keyof ProjectPlanImportRow

const HEADER_ALIASES: Record<string, ImportField> = {
  项目: 'project_name',
  项目名称: 'project_name',
  阶段: 'project_name',
  目标: 'project_objective',
  重点工作: 'work_area',
  关键任务: 'key_task',
  关键成果: 'key_achievement',
  评价标准: 'completion_standard',
  完成标准: 'completion_standard',
  统筹人: 'coordinator',
  负责人: 'owner',
  责任人: 'owner',
  协同: 'collaborators',
  协同人: 'collaborators',
  成员: 'collaborators',
  计划时间: 'plan_time',
  计划开始时间: 'plan_start',
  计划结束时间: 'plan_end',
  重点工作计划开始时间: 'workstream_plan_start',
  重点工作计划结束时间: 'workstream_plan_end',
  当前状态: 'status',
  状态: 'status',
  完成情况: 'status',
  问题与需协调事项: 'issue',
  问题: 'issue',
  备注: 'notes',
  序号: 'sequence',
}

const EMPTY_ROW: ProjectPlanImportRow = {
  project_name: '',
  project_objective: '',
  work_area: '',
  key_task: '',
  key_achievement: '',
  completion_standard: '',
  coordinator: '',
  owner: '',
  collaborators: '',
  plan_time: '',
  plan_start: '',
  plan_end: '',
  workstream_plan_start: '',
  workstream_plan_end: '',
  status: '',
  issue: '',
  notes: '',
  sequence: '',
}

function clean(value: string | undefined): string {
  return (value ?? '').replace(/\r/g, '').trim()
}

function titleProjectName(lines: string[], headerIndex: number): string {
  for (let index = headerIndex - 1; index >= 0; index -= 1) {
    const candidate = clean(lines[index].replace(/\t/g, ' '))
    if (!candidate) continue
    const name = candidate
      .replace(/目标与重点工作计划表$/, '')
      .replace(/重点工作计划表$/, '')
      .replace(/工作计划表$/, '')
      .trim()
    if (name && name !== candidate || /计划表$/.test(candidate)) return name
    return candidate
  }
  return ''
}

function combinePlanTime(start: string, end: string): string {
  if (start && end) return `${start}~${end}`
  return start || end
}

function findHeader(lines: string[]): { index: number; mapped: Array<ImportField | null> } | null {
  for (let index = 0; index < lines.length; index += 1) {
    const headers = lines[index].split('\t').map(clean)
    const mapped = headers.map((header) => HEADER_ALIASES[header] ?? null)
    if (mapped.includes('key_task') || mapped.includes('work_area')) return { index, mapped }
  }
  return null
}

export function parseProjectPlanImportText(text: string): ProjectPlanImportResult {
  const lines = text.split('\n').map((line) => line.trimEnd()).filter((line) => line.trim())
  const header = findHeader(lines)
  if (!header) {
    return {
      rows: [],
      errors: [{ row: 1, message: '未识别到包含“重点工作”或“关键任务”的表头' }],
      headerRow: null,
    }
  }

  const titleProject = titleProjectName(lines, header.index)
  const hasProjectColumn = header.mapped.includes('project_name')
  const hasWorkstreamColumn = header.mapped.includes('work_area')
  let currentProject = titleProject
  let currentWorkArea = ''
  const rows: ProjectPlanImportRow[] = []
  const errors: ProjectPlanImportError[] = []

  for (let index = header.index + 1; index < lines.length; index += 1) {
    const cells = lines[index].split('\t')
    const row = { ...EMPTY_ROW }
    header.mapped.forEach((field, cellIndex) => {
      if (!field) return
      row[field] = clean(cells[cellIndex])
    })

    const projectName = row.project_name || currentProject
    const workArea = row.work_area || currentWorkArea || (!hasWorkstreamColumn ? row.key_task : '')
    if (projectName) currentProject = projectName
    if (workArea) currentWorkArea = workArea
    row.project_name = projectName
    row.work_area = workArea
    row.plan_time = row.plan_time || combinePlanTime(row.plan_start, row.plan_end)
    if (!row.status) row.status = '未开始'

    const missing: string[] = []
    if (!row.project_name) missing.push(hasProjectColumn ? '项目' : '标题中的项目名')
    if (!row.work_area) missing.push('重点工作')
    if (!row.key_task) missing.push('关键任务')
    if (missing.length > 0) {
      errors.push({ row: index + 1, message: `缺少${missing.join('、')}` })
      continue
    }
    rows.push(row)
  }

  return { rows, errors, headerRow: header.index + 1 }
}

export function toBatchImportRows(rows: ProjectPlanImportRow[]): BatchImportRow[] {
  return rows.map(({ work_area, ...row }) => ({ ...row, workstream: work_area }))
}
