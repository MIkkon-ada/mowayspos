import type { PlanTableRow } from './planTableViewModel'

export const WORK_PROGRESS_VIEW_COLUMNS = [
  { key: 'keyTask', label: '关键任务', min: 230, max: 430, narrow: 270, flexible: true },
  { key: 'owner', label: '负责人', min: 88, max: 160, narrow: 100, flexible: false },
  { key: 'planTime', label: '计划时间', min: 120, max: 190, narrow: 130, flexible: false },
  { key: 'status', label: '状态 / 风险', min: 105, max: 150, narrow: 120, flexible: false },
  { key: 'latestProgress', label: '最新进展', min: 250, max: 520, narrow: 210, flexible: true },
  { key: 'nextStep', label: '下一步计划', min: 250, max: 520, narrow: 240, flexible: true },
] as const

export const WORK_PROGRESS_OPTIONAL_COLUMNS = [
  { key: 'expectedOutcome', label: '预期成果', min: 180, max: 380, narrow: 220, flexible: true },
  { key: 'goal', label: '目标', min: 180, max: 380, narrow: 220, flexible: true },
  { key: 'boweiRole', label: '博维角色', min: 160, max: 340, narrow: 200, flexible: true },
] as const
export const WORK_PROGRESS_ALL_COLUMNS = [...WORK_PROGRESS_VIEW_COLUMNS, ...WORK_PROGRESS_OPTIONAL_COLUMNS] as const
export type WorkProgressOptionalColumnKey = (typeof WORK_PROGRESS_OPTIONAL_COLUMNS)[number]['key']
export type WorkProgressColumnKey = (typeof WORK_PROGRESS_ALL_COLUMNS)[number]['key']
export type WorkProgressWidths = Record<WorkProgressColumnKey, number>
export type WorkProgressWidthOverrides = Partial<WorkProgressWidths>

const WIDE_TABLE_MIN_WIDTH = 1070

export function clampWorkProgressWidth(key: WorkProgressColumnKey, value: number): number {
  const column = WORK_PROGRESS_ALL_COLUMNS.find((item) => item.key === key)!
  return Math.min(column.max, Math.max(column.min, Math.round(value)))
}

export function readWorkProgressWidthOverrides(value: string | null): WorkProgressWidthOverrides {
  if (!value) return {}
  try {
    const parsed = JSON.parse(value) as Record<string, unknown>
    const overrides: WorkProgressWidthOverrides = {}
    for (const column of WORK_PROGRESS_ALL_COLUMNS) {
      const width = parsed[column.key]
      if (typeof width === 'number' && Number.isFinite(width)) overrides[column.key] = clampWorkProgressWidth(column.key, width)
    }
    return overrides
  } catch {
    return {}
  }
}

export function createWorkProgressTextMeasurer(): (text: string) => number {
  const context = typeof document !== 'undefined' ? document.createElement('canvas').getContext('2d') : null
  if (context) {
    context.font = '12px "Microsoft YaHei", "PingFang SC", sans-serif'
    return (text) => context.measureText(text).width
  }
  return (text) => [...text].reduce((width, char) => width + (char.charCodeAt(0) > 255 ? 12 : 7), 0)
}

function rowTexts(row: PlanTableRow, key: WorkProgressColumnKey): string[] {
  switch (key) {
    case 'keyTask': return [row.keyTask]
    case 'owner': return [row.responsible]
    case 'planTime': return [[row.planStart, row.planEnd].filter((value) => value !== '—').join(' — ')]
    case 'status': return [row.status, ...row.statusMarkers.map((marker) => marker.label)]
    case 'latestProgress': return row.latestProgress.split(/\r?\n|[；;]/)
    case 'nextStep': return row.nextStep.split(/\r?\n|[；;]/)
    case 'expectedOutcome': return [row.subtask?.expected_outcome ?? '']
    case 'goal': return [row.subtask?.goal ?? '']
    case 'boweiRole': return [row.subtask?.bowei_role ?? '']
  }
}

export function calculateWorkProgressWidths(
  rows: PlanTableRow[],
  availableWidth: number,
  overrides: WorkProgressWidthOverrides = {},
  measureText?: (text: string) => number,
  optionalKeys: readonly WorkProgressOptionalColumnKey[] = [],
): WorkProgressWidths {
  const widths = {} as WorkProgressWidths
  const columns = WORK_PROGRESS_ALL_COLUMNS.filter((column) =>
    WORK_PROGRESS_VIEW_COLUMNS.some((base) => base.key === column.key) || optionalKeys.some((key) => key === column.key))
  for (const column of WORK_PROGRESS_ALL_COLUMNS) widths[column.key] = overrides[column.key] ?? column.narrow
  if (availableWidth < WIDE_TABLE_MIN_WIDTH) {
    return widths
  }

  const measure = measureText ?? createWorkProgressTextMeasurer()
  const desired = {} as WorkProgressWidths
  for (const column of columns) {
    const contentWidth = Math.max(
      measure(column.label) + 28,
      ...rows.flatMap((row) => rowTexts(row, column.key).map((text) => measure(text) + (column.flexible ? 40 : 28))),
    )
    desired[column.key] = clampWorkProgressWidth(column.key, contentWidth)
    widths[column.key] = overrides[column.key] ?? (column.flexible ? column.min : desired[column.key])
  }

  let overflow = columns.reduce((sum, column) => sum + widths[column.key], 0) - Math.floor(availableWidth)
  while (overflow > 0) {
    const shrinkable = columns.filter((column) => !column.flexible && overrides[column.key] === undefined && widths[column.key] > column.min)
    if (!shrinkable.length) break
    const totalCapacity = shrinkable.reduce((sum, column) => sum + widths[column.key] - column.min, 0)
    const required = overflow
    let shrunk = 0
    shrinkable.forEach((column, index) => {
      const capacity = widths[column.key] - column.min
      const share = index === shrinkable.length - 1 ? required - shrunk : Math.floor(required * capacity / totalCapacity)
      const taken = Math.min(capacity, share)
      widths[column.key] -= taken
      shrunk += taken
    })
    if (!shrunk) break
    overflow -= shrunk
  }

  let remaining = Math.max(0, Math.floor(availableWidth) - columns.reduce((sum, column) => sum + widths[column.key], 0))
  while (remaining > 0) {
    const eligible = columns.filter((column) => column.flexible && overrides[column.key] === undefined && widths[column.key] < column.max)
    if (!eligible.length) break
    const weights = eligible.map((column) => 1 + Math.max(0, desired[column.key] - column.min) / 80)
    const totalWeight = weights.reduce((sum, weight) => sum + weight, 0)
    const available = remaining
    let distributed = 0
    eligible.forEach((column, index) => {
      const share = index === eligible.length - 1 ? available - distributed : Math.floor(available * weights[index] / totalWeight)
      const granted = Math.min(column.max - widths[column.key], share)
      widths[column.key] += granted
      distributed += granted
    })
    if (!distributed) break
    remaining -= distributed
  }
  return widths
}
