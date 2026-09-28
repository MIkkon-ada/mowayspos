/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Project, TaskItem, SubTaskItem } from '../../types'
import { PlanTableViewV2 } from './PlanTableViewV2'
import { buildPlanRows } from './planTableViewModel'

afterEach(cleanup)
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
    expect(within(table).getByRole('button', { name: '查看验收标准' })).toBeTruthy()
    expect(screen.queryByText('WBS编号')).toBeNull()
    expect(screen.queryByText('成果与验收')).toBeNull()
  })
  it('opens the existing task detail from a task name', () => {
    const onOpen = vi.fn()
    render(<PlanTableViewV2 {...input} onOpenSubTask={onOpen} />)
    fireEvent.click(screen.getByRole('button', { name: '准备方案' }))
    expect(onOpen).toHaveBeenCalledWith(subs[0])
  })
  it('retains an unexpanded work record when it has no child task yet', () => {
    render(<PlanTableViewV2 project={project} tasks={[task]} taskSubMap={{ 1: [] }} />)
    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(2)
    expect(within(table).getByText('暂无关键任务')).toBeTruthy()
    expect(screen.queryByText('尚未拆分关键任务')).toBeNull()
  })
})
