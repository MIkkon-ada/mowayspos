/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Project, TaskItem, SubTaskItem } from '../../types'
import { PlanTableViewV2 } from './PlanTableViewV2'
import { buildPlanRows, summarizeWorkProgress } from './planTableViewModel'

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
  it('does not mark legacy child rows overdue when their parent task is completed', () => {
    const completedTask = { ...task, status: '已完成' }
    const legacySubtask = { ...subs[0], status: null, is_overdue: true } as unknown as SubTaskItem
    const rows = buildPlanRows({ project, tasks: [completedTask], taskSubMap: { 1: [legacySubtask] } })

    expect(rows[0].status).toBe('已完成')
    expect(rows[0].statusMarkers.map((marker) => marker.kind)).toEqual(['completed'])
    expect(summarizeWorkProgress(rows, []).delayed).toBe(0)
    expect(buildPlanRows({ project, tasks: [completedTask], taskSubMap: { 1: [legacySubtask] }, quickFilter: 'overdue' })).toEqual([])
  })
  it('renders all work and task records inside one continuous table without merged group cards', () => {
    render(<PlanTableViewV2 {...input} />)
    const table = screen.getByRole('table', { name: '工作推进明细' })
    expect(within(table).getAllByRole('row')).toHaveLength(4)
    expect(within(table).getAllByText('重点工作一')).toHaveLength(1)
    expect(within(table).getByRole('button', { name: '折叠重点工作 重点工作一' })).toBeTruthy()
    expect(within(table).queryByRole('columnheader', { name: '重点工作' })).toBeNull()
    expect(screen.getByRole('button', { name: '查看验收标准' })).toBeTruthy()
    expect(screen.queryByText('WBS编号')).toBeNull()
    expect(screen.queryByText('成果与验收')).toBeNull()
    fireEvent.click(within(table).getByRole('button', { name: '折叠重点工作 重点工作一' }))
    expect(within(table).getAllByRole('row')).toHaveLength(2)
    expect(within(table).getByRole('button', { name: '展开重点工作 重点工作一' })).toBeTruthy()
    fireEvent.click(within(table).getByRole('button', { name: '展开重点工作 重点工作一' }))
    expect(within(table).getAllByRole('row')).toHaveLength(4)
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
      latest_confirmed_submission: { summary: '完成调研；整理方案\n3、提交评审', confirmed_at: '2026-10-07T10:00:00', submitter: '张三', confirmed_by: '王主任', source_label: '个人提交' },
      latest_next_step: '1、联系客户；2. 确认排期',
    } as SubTaskItem
    render(<PlanTableViewV2 project={project} tasks={[task]} taskSubMap={{ 1: [detailedSub] }} />)
    const row = screen.getByText('准备方案').closest('tr')!
    expect(within(row.cells[4]).getAllByRole('listitem').map((item) => item.textContent)).toEqual(['完成调研', '整理方案', '提交评审'])
    expect(within(row.cells[5]).getAllByRole('listitem').map((item) => item.textContent)).toEqual(['联系客户', '确认排期'])
    expect(within(row.cells[4]).getByText('2026-10-07 · 确认人：王主任 · 个人提交')).toBeTruthy()
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
  it('shows the confirmer, not the submitter, for confirmed personal progress events', () => {
    const reviewedSub = {
      ...subs[0],
      latest_confirmed_progress: {
        summary: '确认后的正式进展', next_step: '', source_label: '个人提交',
        confirmed_at: '2026-10-08T10:00:00', actor: '汇报人甲', confirmed_by: '审核人乙',
      },
    } as SubTaskItem
    render(<PlanTableViewV2 project={project} tasks={[task]} taskSubMap={{ 1: [reviewedSub] }} />)
    const row = screen.getByText('准备方案').closest('tr')!
    expect(within(row.cells[4]).getByText('2026-10-08 · 确认人：审核人乙 · 个人提交')).toBeTruthy()
    expect(within(row.cells[4]).queryByText(/汇报人甲/)).toBeNull()
  })
  it('distinguishes no report from an unconfirmed report without showing its content as formal progress', () => {
    const pending = {
      ...subs[0],
      has_any_submission: true,
      unconfirmed_submission_count: 1,
      latest_unconfirmed_submission: {
        id: 9, confirm_status: '待负责人审核', submitter: '王五', created_at: '2026-10-18T09:30:00',
      },
    } as SubTaskItem
    const noReport = { ...subs[1], has_any_submission: false } as SubTaskItem
    render(<PlanTableViewV2 project={project} tasks={[task]} taskSubMap={{ 1: [noReport, pending] }} />)

    const pendingRow = screen.getByText('准备方案').closest('tr')!
    const noReportRow = screen.getByText('提交审核').closest('tr')!
    expect(within(pendingRow).getByText('待负责人审核 · 王五 · 2026-10-18')).toBeTruthy()
    expect(within(pendingRow).getByText('暂无已确认进展')).toBeTruthy()
    expect(within(pendingRow).queryByText('未确认汇报正文')).toBeNull()
    expect(within(noReportRow).getByText('尚未汇报')).toBeTruthy()
  })
  it('lets the user resize a column and restores the saved width', () => {
    const view = render(<PlanTableViewV2 {...input} />)
    const handle = screen.getByRole('button', { name: '调整关键任务列宽' })
    fireEvent.pointerDown(handle, { clientX: 100 })
    fireEvent.pointerMove(window, { clientX: 130 })
    fireEvent.pointerUp(window)
    expect(screen.getByRole('table').querySelector('col')?.style.width).toBe('300px')
    view.unmount()
    render(<PlanTableViewV2 {...input} />)
    expect(screen.getByRole('table').querySelector('col')?.style.width).toBe('300px')
    fireEvent.doubleClick(screen.getByRole('button', { name: '调整关键任务列宽' }))
    expect(screen.getByRole('table').querySelector('col')?.style.width).toBe('270px')
  })
  it('retains a workstream group when it has no child task yet', () => {
    render(<PlanTableViewV2 project={project} tasks={[task]} taskSubMap={{ 1: [] }} />)
    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('row')).toHaveLength(3)
    expect(within(table).getByText('暂无关键任务')).toBeTruthy()
    expect(within(table).queryAllByRole('listitem')).toHaveLength(0)
    expect(screen.getByText('尚未拆分关键任务')).toBeTruthy()
  })
  it('shows the three project-enabled fields from each key task, while keeping seven default columns', () => {
    const first = { ...subs[0], expected_outcome: '形成诊断报告', goal: '确认核心问题', bowei_role: '博维负责访谈与分析' }
    const view = render(<PlanTableViewV2 project={project} tasks={[task]} taskSubMap={{ 1: [first] }} />)
    expect(screen.getAllByRole('columnheader')).toHaveLength(6)
    view.rerender(<PlanTableViewV2 project={project} tasks={[task]} taskSubMap={{ 1: [first] }} optionalColumns={['expectedOutcome', 'goal', 'boweiRole']} />)
    expect(screen.getAllByRole('columnheader')).toHaveLength(9)
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
