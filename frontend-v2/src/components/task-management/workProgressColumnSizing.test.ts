import { describe, expect, it } from 'vitest'
import type { PlanTableRow } from './planTableViewModel'
import { calculateWorkProgressWidths, WORK_PROGRESS_VIEW_COLUMNS } from './workProgressColumnSizing'

const measureText = (value: string) => [...value].length * 12
const row = (overrides: Partial<PlanTableRow> = {}) => ({
  workstream: '重点工作', keyTask: '关键任务', responsible: '张三', planStart: '2026-10-01', planEnd: '2026-10-31',
  status: '进行中', statusMarkers: [], latestProgress: '完成调研', nextStep: '联系客户',
  ...overrides,
}) as PlanTableRow

describe('work progress column sizing', () => {
  it('uses field content and the available width while bounding long text columns', () => {
    const rows = [row({ workstream: '较长的重点工作名称用于覆盖多个部门协同安排', responsible: '张三李四王五', latestProgress: '完成一项需要比较详细描述的前期调研工作；整理调研资料', nextStep: '联系客户' })]
    const widths = calculateWorkProgressWidths(rows, 1680, {}, measureText)
    expect(widths.workstream).toBeGreaterThan(180)
    expect(widths.owner).toBeGreaterThan(88)
    expect(widths.latestProgress).toBeGreaterThan(widths.nextStep)
    expect(widths.latestProgress).toBeLessThanOrEqual(520)
    expect(WORK_PROGRESS_VIEW_COLUMNS.reduce((sum, column) => sum + widths[column.key], 0)).toBe(1680)
  })

  it('holds a manually resized column and redistributes the remaining space', () => {
    const rows = [row()]
    const initial = calculateWorkProgressWidths(rows, 1680, {}, measureText)
    const resized = calculateWorkProgressWidths(rows, 1680, { owner: 145 }, measureText)
    expect(resized.owner).toBe(145)
    expect(resized.latestProgress + resized.nextStep + resized.keyTask).toBeLessThan(initial.latestProgress + initial.nextStep + initial.keyTask)
    expect(WORK_PROGRESS_VIEW_COLUMNS.reduce((sum, column) => sum + resized[column.key], 0)).toBe(1680)
  })

  it('uses minimum widths before introducing horizontal scrolling on a wide viewport', () => {
    const longText = '跨部门协同推进工作计划和执行安排'
    const widths = calculateWorkProgressWidths([row({ workstream: longText, responsible: longText, status: longText })], 1350, {}, measureText)
    expect(WORK_PROGRESS_VIEW_COLUMNS.reduce((sum, column) => sum + widths[column.key], 0)).toBe(1350)
    expect(widths.workstream).toBeGreaterThanOrEqual(180)
    expect(widths.owner).toBeGreaterThanOrEqual(88)
  })

  it('keeps the existing layout on narrower screens', () => {
    const widths = calculateWorkProgressWidths([row()], 1190, {}, measureText)
    expect(WORK_PROGRESS_VIEW_COLUMNS.map((column) => widths[column.key])).toEqual([220, 270, 100, 130, 120, 210, 240])
  })
})
