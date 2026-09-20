import type { Alignment, Cell, Worksheet } from 'exceljs'
import type { Project, SubTaskItem, TaskItem } from '../types'
import {
  buildPlanRows,
  PLAN_TABLE_BUSINESS_HEADERS,
  PLAN_TABLE_COLUMN_WIDTHS,
} from '../components/task-management/planTableViewModel'

type ExportPlanTableInput = {
  project: Project
  tasks: TaskItem[]
  taskSubMap: Record<number, SubTaskItem[]>
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
  if (rowSpan <= 1) return
  sheet.mergeCells(`${column}${startRow}:${column}${startRow + rowSpan - 1}`)
}

function safeFilenamePart(value: string): string {
  return value.replace(/[\\/:*?"<>|]/g, '_').trim() || '未命名项目'
}

export async function exportPlanTableToExcel({
  project,
  tasks,
  taskSubMap,
  searchText = '',
}: ExportPlanTableInput) {
  const ExcelJS = await import('exceljs')
  const workbook = new ExcelJS.Workbook()
  const sheet = workbook.addWorksheet('工作推进表')
  const rows = buildPlanRows({ project, tasks, taskSubMap, searchText })

  sheet.columns = PLAN_TABLE_COLUMN_WIDTHS.map((width) => ({ width: Math.max(8, Math.round(width / 8)) }))
  sheet.views = [{ state: 'frozen', xSplit: 3, ySplit: 2 }]

  sheet.addRow(Array(PLAN_TABLE_BUSINESS_HEADERS.length).fill(''))
  sheet.mergeCells(`A1:N1`)
  const titleCell = sheet.getCell('A1')
  titleCell.value = `${project.name}目标与重点工作计划表`
  styleCell(titleCell, { bold: true, size: 16, horizontal: 'center', fill: TITLE_FILL })
  sheet.getRow(1).height = 46

  const headerRow = sheet.addRow([...PLAN_TABLE_BUSINESS_HEADERS])
  headerRow.height = 36
  headerRow.eachCell({ includeEmpty: true }, (cell) => {
    styleCell(cell, { bold: true, horizontal: 'center', fill: HEADER_FILL })
  })

  rows.forEach((row) => {
    const completion = row.completionNote ? `[${row.status}] ${row.completionNote}` : `[${row.status}]`
    const dataRow = sheet.addRow([
      row.objective,
      row.task.key_task,
      row.task.completion_standard || row.task.key_achievement || '未填写评价标准',
      row.sequence,
      row.keyTask,
      row.responsible,
      row.planStart,
      row.planEnd,
      row.assistingPerson,
      completion,
      row.remarks,
      row.projectManager,
      row.taskPlanStart,
      row.taskPlanEnd,
    ])
    dataRow.height = 36
    dataRow.eachCell({ includeEmpty: true }, (cell, columnNumber) => {
      styleCell(cell, { horizontal: columnNumber === 4 ? 'center' : 'left' })
    })
  })

  if (rows.length === 0) {
    const emptyRow = sheet.addRow(['当前筛选条件下没有匹配的关键任务'])
    sheet.mergeCells('A3:N3')
    styleCell(emptyRow.getCell(1), { horizontal: 'center' })
    emptyRow.height = 44
  } else {
    const dataStartRow = 3
    mergeVertical(sheet, 'A', dataStartRow, rows.length)
    rows.forEach((row, index) => {
      if (!row.showTaskCells) return
      const startRow = dataStartRow + index
      for (const column of ['B', 'C', 'L', 'M', 'N']) {
        mergeVertical(sheet, column, startRow, row.taskRowSpan)
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
