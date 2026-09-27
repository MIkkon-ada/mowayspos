import type { PlanTableRow } from './planTableViewModel'

export type PlanTableColumnKey =
  | 'workstream'
  | 'keyTask'
  | 'acceptance'
  | 'responsible'
  | 'planTime'
  | 'status'
  | 'risk'
  | 'latestProgress'
  | 'nextStep'

export type PlanTableColumnGroupKey = 'structure' | 'planning' | 'tracking'

export type PlanTableColumn = {
  key: PlanTableColumnKey
  label: string
  group: PlanTableColumnGroupKey
  priority: 'high' | 'medium' | 'low'
  width: number
  exportOrder: number
}

export const PLAN_TABLE_COLUMNS: readonly PlanTableColumn[] = [
  { key: 'workstream', label: '重点工作', group: 'structure', priority: 'high', width: 220, exportOrder: 1 },
  { key: 'keyTask', label: '关键任务', group: 'structure', priority: 'high', width: 300, exportOrder: 2 },
  { key: 'acceptance', label: '验收标准', group: 'planning', priority: 'medium', width: 260, exportOrder: 3 },
  { key: 'responsible', label: '负责人', group: 'planning', priority: 'high', width: 120, exportOrder: 4 },
  { key: 'planTime', label: '计划时间', group: 'planning', priority: 'high', width: 150, exportOrder: 5 },
  { key: 'status', label: '状态', group: 'tracking', priority: 'high', width: 100, exportOrder: 6 },
  { key: 'risk', label: '风险/问题', group: 'tracking', priority: 'medium', width: 110, exportOrder: 7 },
  { key: 'latestProgress', label: '最新进展', group: 'tracking', priority: 'medium', width: 260, exportOrder: 8 },
  { key: 'nextStep', label: '下一步', group: 'tracking', priority: 'high', width: 220, exportOrder: 9 },
]

export type PlanTableColumnGroup = {
  key: PlanTableColumnGroupKey
  label: string
  columns: readonly PlanTableColumn[]
}

const PLAN_TABLE_GROUP_LABELS: Record<PlanTableColumnGroupKey, string> = {
  structure: '工作结构',
  planning: '计划与验收',
  tracking: '推进跟进',
}

export function getPlanTableColumnGroups(
  columns: readonly PlanTableColumn[],
): PlanTableColumnGroup[] {
  return columns.reduce<PlanTableColumnGroup[]>((groups, column) => {
    const previous = groups[groups.length - 1]
    if (previous?.key === column.group) {
      previous.columns = [...previous.columns, column]
      return groups
    }
    groups.push({ key: column.group, label: PLAN_TABLE_GROUP_LABELS[column.group], columns: [column] })
    return groups
  }, [])
}

export function getPlanTableColumn(key: PlanTableColumnKey): PlanTableColumn {
  const column = PLAN_TABLE_COLUMNS.find((item) => item.key === key)
  if (!column) throw new Error(`Unknown project work progress column: ${key}`)
  return column
}

export function getPlanRowCellValue(row: PlanTableRow, key: PlanTableColumnKey): string {
  switch (key) {
    case 'workstream': return row.workstream
    case 'keyTask': return row.keyTask
    case 'acceptance': return row.acceptance
    case 'responsible': return row.responsible
    case 'planTime': {
      const values = [row.planStart, row.planEnd].filter((value) => value !== '—')
      if (values.length === 0) return '—'
      if (values.length === 1 || values[0] === values[1]) return values[0]
      return values.join(' ~ ')
    }
    case 'status': return row.status
    case 'risk': return row.risk
    case 'latestProgress': {
      const submission = row.latestConfirmedSubmission
      if (!submission) return row.latestProgress
      const meta = [submission.confirmed_at?.slice(0, 10), submission.submitter].filter(Boolean).join(' · ')
      return [meta, submission.summary].filter(Boolean).join('\n') || row.latestProgress
    }
    case 'nextStep': return row.nextStep
  }
}
