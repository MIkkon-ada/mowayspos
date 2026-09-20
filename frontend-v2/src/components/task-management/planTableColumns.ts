import type { PlanTableRow } from './planTableViewModel'

export type PlanTableColumnKey =
  | 'wbsCode'
  | 'workstream'
  | 'keyTask'
  | 'deliverable'
  | 'acceptance'
  | 'responsible'
  | 'planTime'
  | 'status'
  | 'risk'
  | 'latestProgress'
  | 'nextStep'

export type PlanTableColumn = {
  key: PlanTableColumnKey
  label: string
  priority: 'high' | 'medium' | 'low'
  width: number
  exportOrder: number
}

export const PLAN_TABLE_COLUMNS: readonly PlanTableColumn[] = [
  { key: 'wbsCode', label: 'WBS编号', priority: 'high', width: 72, exportOrder: 1 },
  { key: 'workstream', label: '重点工作', priority: 'high', width: 220, exportOrder: 2 },
  { key: 'keyTask', label: '关键任务', priority: 'high', width: 300, exportOrder: 3 },
  { key: 'deliverable', label: '交付成果', priority: 'medium', width: 230, exportOrder: 4 },
  { key: 'acceptance', label: '验收标准', priority: 'medium', width: 260, exportOrder: 5 },
  { key: 'responsible', label: '负责人', priority: 'high', width: 120, exportOrder: 6 },
  { key: 'planTime', label: '计划时间', priority: 'high', width: 150, exportOrder: 7 },
  { key: 'status', label: '状态', priority: 'high', width: 100, exportOrder: 8 },
  { key: 'risk', label: '风险/问题', priority: 'medium', width: 110, exportOrder: 9 },
  { key: 'latestProgress', label: '最新进展', priority: 'medium', width: 260, exportOrder: 10 },
  { key: 'nextStep', label: '下一步', priority: 'high', width: 220, exportOrder: 11 },
]

export function getPlanTableColumn(key: PlanTableColumnKey): PlanTableColumn {
  const column = PLAN_TABLE_COLUMNS.find((item) => item.key === key)
  if (!column) throw new Error(`Unknown project work progress column: ${key}`)
  return column
}

export function getPlanRowCellValue(row: PlanTableRow, key: PlanTableColumnKey): string {
  switch (key) {
    case 'wbsCode': return row.wbsCode
    case 'workstream': return row.workstream
    case 'keyTask': return row.keyTask
    case 'deliverable': return row.deliverable
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
