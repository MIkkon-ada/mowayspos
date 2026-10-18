/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Project, TaskItem, SubTaskItem } from '../../types'
import { PlanTableViewV2 } from './PlanTableViewV2'
import { buildPlanRows } from './planTableViewModel'

afterEach(() => { cleanup(); window.localStorage.clear() })
const project = { id: 1, name: '项目', objectives: '项目总体目标' } as Project
const task = { id: 1, key_task: '重点工作一', status: '进行中', completion_standard: '上级标准', key_achievement: '交付成果一' } as TaskItem
const subs = [
  { id: 10, task_id: 1, title: '准备方案', assignee: '张三', status: '未开始', notes: '这只是备注', completion_criteria: '任务自己的标准' },
  { id: 11, task_id: 1, title: '提交审核', assignee: '李四', status: '已完成', is_overdue: true },
] as SubTaskItem[]
const input = { project, tasks: [task], taskSubMap: { 1: subs } }

describe('shared work progress table', () => {
  it('filters child task rows by owner and status', () => {
    expect(buildPlanRows({ ...input, ownerFilter: '张三', statusFilter: '未开始' }).map(r => r.subtask?.id)).toEqual([10])
    expect(buildPlanRows({ ...input, ownerFilter: '张三', statusFilter: '已完成' })).toEqual([])
    expect(buildPlanRows({ ...input, statusFilter: '延期' })).toEqual([])
  })
  it('renders all work and task records inside one continuous table without merged group cards', () => {
    render(<PlanTableViewV2 {...input} />)
    const table = screen.getByRole('table', { name: '工作推进明细' })
    expect(within(table).getAllByRole('row')).toHaveLength(3)
    const workstreamCell = within(table).getByText('重点工作一').closest('td')
    expect(within(table).getAllByText('重点工作一')).toHaveLength(1)
    expect(workstreamCell?.getAttribute('rowspan')).toBe('2')
    expect(within(table).getByRole('columnheader', { name: '重点工作' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '查看验收标准' })).toBeTruthy()
    expect(screen.queryByText('WBS编号')).toBeNull()
    expect(screen.queryByText('成果与验收')).toBeNull()
  })
  it('opens the existing task detail from a task name', () => {
    const onOpen = vi.fn()
    render(<PlanTableViewV2 {...input} onOpenSubTask={onOpen} />)
    fireEvent.click(screen.getByRole('button', { name: '准备方案' }))
    expect(onOpen).toHaveBeenCalledWith(subs[0])
  })
  it('shows each progress and next-step point on its own line', () => {
    const detailedSub = {
      ...subs[0],
      latest_confirmed_submission: { summary: '完成调研；整理方案\n3、提交评审', confirmed_at: '2026-10-07T10:00:00', submitter: '张三' },
      latest_next_step: '1、联系客户；2. 确认排期',
    } as SubTaskItem
    render(<PlanTableViewV2 project={project} tasks={[task]} taskSubMap={{ 1: [detailedSub] }} />)
    const row = screen.getByText('准备方案').closest('tr')!
    expect(within(row.cells[5]).getAllByRole('listitem').map((item) => item.textContent)).toEqual(['完成调研', '整理方案', '提交评审'])
    expect(within(row.cells[6]).getAllByRole('listitem').map((item) => item.textContent)).toEqual(['联系客户', '确认排期'])
    expect(within(row.cells[5]).getByText('2026-10-07 · 张三')).toBeTruthy()
  })
  it('shows approved meeting progress in the work progress table', () => {
    const reviewedSub = {
      ...subs[0],
      latest_confirmed_submission: { id: 1, summary: '旧个人提交', confirmed_at: '2026-10-07T10:00:00', submitter: '张三' },
      latest_confirmed_progress: {
        summary: '会议确认第一批已交付', next_step: '继续整理第二批',
        source_label: '会议纪要', confirmed_at: '2026-10-08T10:00:00', actor: '负责人',
      },
      latest_next_step: '继续整理第二批',
    } as SubTaskItem
    render(<PlanTableViewV2 project={project} tasks={[task]} taskSubMap={{ 1: [reviewedSub] }} />)
    const row = screen.getByText('准备方案').closest('tr')!
    expect(within(row).getByText('会议确认第一批已交付')).toBeTruthy()
    expect(within(row).queryByText('旧个人提交')).toBeNull()
    expect(within(row).getByText('2026-10-08 · 负责人 · 会议纪要')).toBeTruthy()
    expect(within(row).getByText('继续整理第二批')).toBeTruthy()
  })
  it('lets the user resize a column and restores the saved width', () => {
    const view = render(<PlanTableViewV2 {...input} />)
    const handle = screen.getByRole('button', { name: '调整重点工作列宽' })
    fireEvent.pointerDown(handle, { clientX: 100 })
    fireEvent.pointerMove(window, { clientX: 130 })
    fireEvent.pointerUp(window)
    expect(screen.getByRole('table').querySelector('col')?.style.width).toBe('250px')
    view.unmount()
    render(<PlanTableViewV2 {...input} />)
    expect(screen.getByRole('table').querySelector('col')?.style.width).toBe('250px')
    fireEvent.doubleClick(screen.getByRole('button', { name: '调整重点工作列宽' }))
    expect(screen.getByRole('table').querySelector('col')?.style.width).toBe('220px')
  })
  it('retains an unexpanded work record when it has no child task yet', () => {
    render(<PlanTableViewV2 project={project} tasks={[task]} taskSubMap={{ 1: [] }} />)
    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(2)
    expect(within(table).getByText('暂无关键任务')).toBeTruthy()
    expect(within(table).queryAllByRole('listitem')).toHaveLength(0)
    expect(screen.queryByText('尚未拆分关键任务')).toBeNull()
  })
  it('shows the three project-enabled fields from each key task, while keeping seven default columns', () => {
    const first = { ...subs[0], expected_outcome: '形成诊断报告', goal: '确认核心问题', bowei_role: '博维负责访谈与分析' }
    const view = render(<PlanTableViewV2 project={project} tasks={[task]} taskSubMap={{ 1: [first] }} />)
    expect(screen.getAllByRole('columnheader')).toHaveLength(7)
    view.rerender(<PlanTableViewV2 project={project} tasks={[task]} taskSubMap={{ 1: [first] }} optionalColumns={['expectedOutcome', 'goal', 'boweiRole']} />)
    expect(screen.getAllByRole('columnheader')).toHaveLength(10)
    const row = screen.getByText('准备方案').closest('tr')!
    expect(within(row).getByText('形成诊断报告')).toBeTruthy()
    expect(within(row).getByText('确认核心问题')).toBeTruthy()
    expect(within(row).getByText('博维负责访谈与分析')).toBeTruthy()
  })
  it('offers editing the selected key task fields from the expanded table', () => {
    const onEdit = vi.fn()
    render(<PlanTableViewV2 {...input} optionalColumns={['expectedOutcome']} onEditSubTask={onEdit} />)
    const row = screen.getByText('准备方案').closest('tr')!
    fireEvent.click(within(row).getByRole('button', { name: '编辑字段' }))
    expect(onEdit).toHaveBeenCalledWith(task, subs[0])
  })
})
