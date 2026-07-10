import type { Alignment, Worksheet } from 'exceljs'
import type { Project, TaskItem } from '../types'

const HEADER_BG  = 'FF1F3A6E'  // 深蓝
const STATUS_BG  = 'FFB0B8C4'  // 灰色（事项状态列）
const BORDER_CLR = 'FFD0D7E3'

const thin = { style: 'thin' as const, color: { argb: BORDER_CLR } }
const border = { top: thin, left: thin, bottom: thin, right: thin }

function cell(
  sheet: Worksheet,
  addr: string,
  opts?: { bold?: boolean; size?: number; hAlign?: Alignment['horizontal']; bgArgb?: string; fontArgb?: string }
) {
  const c = sheet.getCell(addr)
  c.font = { name: '微软雅黑', size: opts?.size ?? 10, bold: opts?.bold, color: { argb: opts?.fontArgb ?? 'FF1E293B' } }
  c.alignment = { vertical: 'middle', horizontal: opts?.hAlign ?? 'center', wrapText: true }
  if (opts?.bgArgb) c.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: opts.bgArgb } }
  c.border = border
  return c
}

function resolveTaskProjectLabel(task: TaskItem, projects: Project[]) {
  const matched = projects.find((p) => p.id === task.project_id)
  if (matched) return matched.name
  return task.special_project?.trim() || '（未分类）'
}

function resolveTaskProjectKey(task: TaskItem) {
  const projectId = task.project_id
  if (typeof projectId === 'number') return `project:${projectId}`
  return `legacy:${task.special_project?.trim() || '（未分类）'}`
}

export async function exportTasksToExcel(tasks: TaskItem[], title: string, projects: Project[]) {
  const ExcelJS = await import('exceljs')
  const workbook = new ExcelJS.Workbook()
  const sheet = workbook.addWorksheet('工作推进表')

  sheet.columns = [
    { width: 6  },  // A 序号
    { width: 18 },  // B 项目
    { width: 20 },  // C 评价标准
    { width: 28 },  // D 重点工作（key_task 字段，业务语义 Workstream）
    { width: 10 },  // E 责任人
    { width: 10 },  // F 协助人
    { width: 14 },  // G 计划开始时间
    { width: 14 },  // H 计划完成时间
    { width: 14 },  // I 实际完成时间
    { width: 12 },  // J 事项状态
  ]

  // ── 标题行 ──────────────────────────────────────────
  sheet.addRow(Array(10).fill(''))
  sheet.mergeCells('A1:J1')
  const titleCell = sheet.getCell('A1')
  titleCell.value = title
  titleCell.font = { bold: true, size: 16, name: '微软雅黑' }
  titleCell.alignment = { vertical: 'middle', horizontal: 'center' }
  sheet.getRow(1).height = 45

  // ── 表头行 ──────────────────────────────────────────
  // D 列："重点工作" 对应 TaskItem.key_task（物理字段名，业务语义 Workstream 名称）
  const HEADERS = ['序号', '项目', '评价标准', '重点工作', '责任人', '协助人', '计划开始时间', '计划完成时间', '实际完成时间', '事项状态']
  const COLS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
  sheet.addRow(HEADERS)
  const headerRow = sheet.getRow(2)
  headerRow.height = 36
  COLS.forEach((col, i) => {
    const c = sheet.getCell(`${col}2`)
    c.value = HEADERS[i]
    c.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: HEADER_BG } }
    c.font = { bold: true, color: { argb: 'FFFFFFFF' }, name: '微软雅黑', size: 10 }
    c.alignment = { vertical: 'middle', horizontal: 'center', wrapText: true }
    c.border = border
  })

  // ── 按专项分组 ──────────────────────────────────────
  const groups: [string, TaskItem[]][] = []
  const seen = new Map<string, TaskItem[]>()
  for (const t of tasks) {
    const key = resolveTaskProjectKey(t)
    if (!seen.has(key)) { seen.set(key, []); groups.push([key, seen.get(key)!]) }
    seen.get(key)!.push(t)
  }

  let idx = 1
  for (const [projName, groupTasks] of groups) {
    const startRow = sheet.rowCount + 1
    const projectLabel = groupTasks.length > 0 ? resolveTaskProjectLabel(groupTasks[0], projects) : projName

    for (const task of groupTasks) {
      const r = sheet.addRow([
        idx,
        projectLabel,
        task.completion_standard ?? '',
        task.key_task ?? '',
        task.owner ?? '',
        task.collaborators ?? '',
        '',
        task.plan_time ?? '',
        '',
        task.status ?? '',
      ])
      r.height = 36
      r.eachCell({ includeEmpty: true }, (c, colNum) => {
        c.font = { name: '微软雅黑', size: 10 }
        c.alignment = { vertical: 'middle', horizontal: colNum === 4 ? 'left' : 'center', wrapText: true }
        c.border = border
        if (colNum === 10) {
          c.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: STATUS_BG } }
        }
      })
    }

    const endRow = sheet.rowCount

    // 垂直合并除「重点工作」(D列) 以外的所有列
    if (groupTasks.length > 1) {
      for (const col of ['A', 'B', 'C', 'E', 'F', 'G', 'H', 'I', 'J']) {
        try { sheet.mergeCells(`${col}${startRow}:${col}${endRow}`) } catch { /* skip */ }
      }
    }

    idx++
  }

  // ── 输出文件 ─────────────────────────────────────────
  const buffer = await workbook.xlsx.writeBuffer()
  const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `工作推进表_${new Date().toISOString().slice(0, 10)}.xlsx`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
