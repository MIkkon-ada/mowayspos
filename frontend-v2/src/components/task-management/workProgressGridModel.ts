import type { SubTaskItem } from '../../types'

export const GRID_COLUMNS = [
  { key: 'keyTask', label: '关键任务', field: 'title', width: 280 },
  { key: 'owner', label: '负责人', field: 'assignee', width: 120 },
  { key: 'startDate', label: '开始日期', field: 'start_date', width: 130 },
  { key: 'dueDate', label: '截止日期', field: 'due_date', width: 130 },
  { key: 'status', label: '状态', field: null, width: 115 },
  { key: 'risk', label: '风险 / 日期提示', field: null, width: 150 },
  { key: 'latestProgress', label: '最新进展 · 已确认', field: null, width: 320 },
  { key: 'nextStep', label: '下一步计划 · 来源记录', field: null, width: 280 },
  { key: 'expectedOutcome', label: '预期成果', field: 'expected_outcome', width: 240 },
  { key: 'goal', label: '目标', field: 'goal', width: 220 },
  { key: 'boweiRole', label: '博维角色', field: 'bowei_role', width: 180 },
  { key: 'acceptance', label: '验收标准', field: 'completion_criteria', width: 280 },
  { key: 'notes', label: '备注', field: 'notes', width: 220 },
] as const
export type GridColumnKey = typeof GRID_COLUMNS[number]['key']
export type GridChanges = Partial<Pick<SubTaskItem, 'title' | 'assignee' | 'start_date' | 'due_date' | 'completion_criteria' | 'expected_outcome' | 'goal' | 'bowei_role' | 'notes'>>
export type GridEdit = { id: number; expected_updated_at: string; changes: GridChanges }
export type GridDrafts = Record<number, GridEdit>
export type GridView = { columns: GridColumnKey[]; frozen: number; groupBy: 'workstream' | 'owner' | 'status' | 'none'; widths: Partial<Record<GridColumnKey, number>> }
export type GridFilters = { search: string; status: string; owner: string; quickFilter: 'all' | 'overdue' | 'risk' | 'issues' | 'date_unknown' }
export type SavedGridView = { id: string; name: string; layout: GridView; filters: GridFilters }
export const DEFAULT_GRID_VIEW: GridView = { columns: ['keyTask', 'owner', 'startDate', 'dueDate', 'status', 'risk', 'latestProgress', 'nextStep'], frozen: 1, groupBy: 'workstream', widths: {} }

export function normalizeGridView(input: unknown): GridView {
  const data = input && typeof input === 'object' ? input as Partial<GridView> : {}
  const known = new Set<string>(GRID_COLUMNS.map(column => column.key))
  const columns = Array.isArray(data.columns) ? [...new Set(data.columns.filter((key): key is GridColumnKey => typeof key === 'string' && known.has(key)))] : [...DEFAULT_GRID_VIEW.columns]
  if (!columns.includes('keyTask')) columns.unshift('keyTask')
  const widths: GridView['widths'] = {}
  if (data.widths && typeof data.widths === 'object') {
    for (const column of GRID_COLUMNS) {
      const width = data.widths[column.key]
      if (typeof width === 'number' && Number.isFinite(width)) widths[column.key] = Math.max(90, Math.min(700, width))
    }
  }
  return { columns, frozen: Math.min(columns.length, Math.max(0, Math.trunc(Number(data.frozen) || 0))), groupBy: ['workstream', 'owner', 'status', 'none'].includes(data.groupBy ?? '') ? data.groupBy! : 'workstream', widths }
}

export function buildCellChange(row: SubTaskItem, key: string, raw: string, memberNames: string[]): GridChanges {
  const column = GRID_COLUMNS.find(column => column.key === key)
  if (!column?.field) throw new Error('该字段为来源记录，只读；请在任务详情中处理')
  if (['已完成', '完成', 'completed'].includes(row.status)) throw new Error('已完成任务请先从详情重新打开')
  if (!row.edit_version) throw new Error('缺少记录版本，请刷新后重试')
  const value = raw.trim()
  if (key === 'keyTask' && (!value || value.length > 200)) throw new Error('任务名称须为 1 至 200 字')
  if (key === 'owner' && !memberNames.includes(value)) throw new Error('负责人必须从当前项目成员中选择')
  if (key === 'startDate' || key === 'dueDate') {
    if (!value) return { [column.field]: null }
    const match = value.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/)
    const iso = match ? `${match[1]}-${match[2].padStart(2, '0')}-${match[3].padStart(2, '0')}` : ''
    const date = new Date(`${iso}T00:00:00Z`)
    if (!iso || Number.isNaN(date.valueOf()) || date.toISOString().slice(0, 10) !== iso) throw new Error('请输入有效日期，例如 2026-10-30')
    return { [column.field]: iso }
  }
  if (value.length > 10000) throw new Error('单元格文字不能超过 10000 字')
  return { [column.field]: value }
}

export function mergeGridDraft(drafts: GridDrafts, row: SubTaskItem, changes: GridChanges): GridDrafts {
  const previous = drafts[row.id]
  const merged = { ...previous?.changes, ...changes }
  // Reverting a cell to its server value removes its pending change.
  for (const field of Object.keys(merged) as (keyof GridChanges)[]) {
    if ((merged[field] ?? '') === (row[field] ?? '')) delete merged[field]
  }
  const next = { ...drafts }
  if (Object.keys(merged).length) next[row.id] = { id: row.id, expected_updated_at: previous?.expected_updated_at ?? row.edit_version!, changes: merged }
  else delete next[row.id]
  return next
}

export function parseClipboard(text: string): string[][] {
  const rows: string[][] = []
  let cells: string[] = [], cell = '', quoted = false
  const value = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  for (let i = 0; i < value.length; i++) {
    const char = value[i]
    if (char === '"' && (quoted || !cell)) {
      if (quoted && value[i + 1] === '"') { cell += '"'; i++ }
      else quoted = !quoted
    } else if (!quoted && (char === '\t' || char === '\n')) {
      cells.push(cell); cell = ''
      if (char === '\n') { rows.push(cells); cells = [] }
    } else cell += char
  }
  if (cell || cells.length) rows.push([...cells, cell])
  return rows
}

export function readSavedGridViews(value: string | null): SavedGridView[] {
  try {
    const entries: unknown = JSON.parse(value || '[]')
    if (!Array.isArray(entries)) return []
    return entries.filter((entry) => entry && typeof entry.id === 'string' && typeof entry.name === 'string' && entry.filters && typeof entry.filters.search === 'string' && typeof entry.filters.status === 'string' && typeof entry.filters.owner === 'string')
      .slice(0, 20).map(entry => ({ id: entry.id, name: entry.name.slice(0, 40), layout: normalizeGridView(entry.layout), filters: { search: entry.filters.search, status: entry.filters.status, owner: entry.filters.owner, quickFilter: ['all', 'overdue', 'risk', 'issues', 'date_unknown'].includes(entry.filters.quickFilter) ? entry.filters.quickFilter : 'all' } }))
  } catch { return [] }
}
