import type { Alignment, Cell, Worksheet } from 'exceljs'
import type { Project, SubTaskItem, TaskItem } from '../types'
import {
  buildPlanRows,
} from '../components/task-management/planTableViewModel'
import {
  getPlanTableColumnGroups,
  getPlanRowCellValue,
  PLAN_TABLE_COLUMNS,
} from '../components/task-management/planTableColumns'

type ExportPlanTableInput = {
  project: Project
  tasks: TaskItem[]
  taskSubMap: Record<number, SubTaskItem[]>
  statusFilter?: string
  ownerFilter?: string
  searchText?: string
}

const BORDER_COLOR = 'FFD8DEE8'
const HEADER_FILL = 'FFF3F6FA'
const TITLE_FILL = 'FFFFFFFF'
const thin = { style: 'thin' as const, color: { argb: BORDER_COLOR } }
const border = { top: thin, left: thin, bottom: thin, right: thin }

function styleCell(
  cell: Cell,
  options?: { bold?: boolean; size?: number; horizontal?: Alignment['horizontal']; fill?: string },
) {
  cell.font = { name: '微软雅黑', size: options?.size ?? 10, bold: options?.bold, color: { argb: 'FF334155' } }
  cell.alignment = { vertical: 'middle', horizontal: options?.horizontal ?? 'left', wrapText: true }
  cell.border = border
  if (options?.fill) {
    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: options.fill } }
  }
}

function mergeVertical(sheet: Worksheet, column: string, startRow: number, rowSpan: number) {
  if (rowSpan > 1) sheet.mergeCells(`${column}${startRow}:${column}${startRow + rowSpan - 1}`)
}

function safeFilenamePart(value: string): string {
  return value.replace(/[\\/:*?"<>|]/g, '_').trim() || '未命名项目'
}

function excelColumnName(columnNumber: number): string {
  let current = columnNumber
  let name = ''
  while (current > 0) {
    const remainder = (current - 1) % 26
    name = String.fromCharCode(65 + remainder) + name
    current = Math.floor((current - 1) / 26)
  }
  return name
}

export async function exportPlanTableToExcel({
  project,
  tasks,
  taskSubMap,
  searchText = '',
  statusFilter = '',
  ownerFilter = '',
}: ExportPlanTableInput) {
  const ExcelJS = await import('exceljs')
  const workbook = new ExcelJS.Workbook()
  const sheet = workbook.addWorksheet('工作推进表')
  const rows = buildPlanRows({ project, tasks, taskSubMap, searchText, statusFilter, ownerFilter })

  sheet.columns = PLAN_TABLE_COLUMNS.map((column) => ({ width: Math.max(8, Math.round(column.width / 9)) }))
  sheet.views = [{ state: 'frozen', xSplit: 2, ySplit: 3 }]

  sheet.addRow(Array(PLAN_TABLE_COLUMNS.length).fill(''))
  sheet.mergeCells(`A1:${excelColumnName(PLAN_TABLE_COLUMNS.length)}1`)
  const titleCell = sheet.getCell('A1')
  titleCell.value = `${project.name}目标与重点工作计划表`
  styleCell(titleCell, { bold: true, size: 16, horizontal: 'center', fill: TITLE_FILL })
  sheet.getRow(1).height = 46

  const groupRow = sheet.addRow(Array(PLAN_TABLE_COLUMNS.length).fill(''))
  const groups = getPlanTableColumnGroups(PLAN_TABLE_COLUMNS)
  let groupStart = 1
  groups.forEach((group) => {
    const groupStartColumn = excelColumnName(groupStart)
    const groupEndColumn = excelColumnName(groupStart + group.columns.length - 1)
    groupRow.getCell(groupStart).value = group.label
    sheet.mergeCells(`${groupStartColumn}2:${groupEndColumn}2`)
    groupStart += group.columns.length
  })
  groupRow.height = 24
  groupRow.eachCell({ includeEmpty: true }, (cell) => {
    styleCell(cell, { bold: true, horizontal: 'center', fill: 'FFE7EBF0' })
  })

  const headerRow = sheet.addRow(PLAN_TABLE_COLUMNS.map((column) => column.label))
  headerRow.height = 36
  headerRow.eachCell({ includeEmpty: true }, (cell) => {
    styleCell(cell, { bold: true, horizontal: 'center', fill: HEADER_FILL })
  })

  rows.forEach((row) => {
    const values = PLAN_TABLE_COLUMNS.map((column) => getPlanRowCellValue(row, column.key))
    const dataRow = sheet.addRow(values)
    const estimatedLines = values.reduce((total, value) => {
      const lines = String(value ?? '').split(/\r?\n/)
      return total + lines.reduce((lineTotal, line) => lineTotal + Math.max(1, Math.ceil(line.length / 32)), 0)
    }, 0)
    dataRow.height = Math.min(120, Math.max(36, estimatedLines * 15))
    dataRow.eachCell({ includeEmpty: true }, (cell, columnNumber) => {
      styleCell(cell, { horizontal: ['status', 'responsible'].includes(PLAN_TABLE_COLUMNS[columnNumber - 1].key) ? 'center' : 'left' })
    })
  })

  if (rows.length === 0) {
    const emptyRow = sheet.addRow(['当前筛选条件下没有匹配的关键任务'])
    sheet.mergeCells(`A4:${excelColumnName(PLAN_TABLE_COLUMNS.length)}4`)
    styleCell(emptyRow.getCell(1), { horizontal: 'center' })
    emptyRow.height = 44
  } else {
    const dataStartRow = 4
    rows.forEach((row, index) => {
      if (!row.showTaskCells) return
      const startRow = dataStartRow + index
      for (const key of ['workstream']) {
        const columnIndex = PLAN_TABLE_COLUMNS.findIndex((column) => column.key === key)
        if (columnIndex >= 0) mergeVertical(sheet, excelColumnName(columnIndex + 1), startRow, row.taskRowSpan)
      }
    })
  }

  for (let rowNumber = 1; rowNumber <= sheet.rowCount; rowNumber += 1) {
    sheet.getRow(rowNumber).eachCell({ includeEmpty: true }, (cell) => {
      if (!cell.border?.top) styleCell(cell)
    })
  }

  const buffer = await workbook.xlsx.writeBuffer()
  const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `工作推进表_${safeFilenamePart(project.name)}_${new Date().toISOString().slice(0, 10)}.xlsx`
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}
