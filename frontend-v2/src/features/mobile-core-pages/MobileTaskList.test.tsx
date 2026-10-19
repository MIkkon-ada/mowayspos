/** @vitest-environment jsdom */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { SubTaskItem, TaskItem } from '../../types'
import { MobileTaskList } from './MobileTaskList'

describe('MobileTaskList plan date status', () => {
  it('shows a pending-date marker for an unfinished task without an exact due date', () => {
    const task = { id: 1, key_task: '重点工作', owner: '项目负责人', plan_time: '2026-10-01 至 2026-10-30' } as TaskItem
    const subtask = {
      id: 2,
      task_id: 1,
      title: '计划年份待确认',
      status: '进行中',
      plan_time: '7.3—7.10',
      due_kind: 'unknown',
      due_date: null,
    } as SubTaskItem

    render(<MobileTaskList tasks={[task]} subTasksByTaskId={{ 1: [subtask] }} loading={false} onOpenSubTask={() => {}} />)

    expect(screen.getByText('待确认日期')).toBeTruthy()
  })

  it('shows confirmed progress, the next step, and task risk in the mobile work list', () => {
    const task = { id: 1, key_task: '重点工作' } as TaskItem
    const subtask = {
      id: 2,
      task_id: 1,
      title: '关键任务',
      status: '进行中',
      assignee: '张三',
      plan_time: '2026-10-01 至 2026-10-30',
      has_risk: true,
      is_overdue: true,
      latest_confirmed_progress: { summary: '完成接口联调', next_step: '验证回写结果', source_label: '个人提交', confirmed_at: '2026-10-18T10:00:00', confirmed_by: '负责人' },
      latest_next_step: '验证回写结果',
    } as SubTaskItem

    render(<MobileTaskList tasks={[task]} subTasksByTaskId={{ 1: [subtask] }} loading={false} onOpenSubTask={() => {}} />)

    expect(screen.getByText('有风险')).toBeTruthy()
    expect(screen.getByText('已延期')).toBeTruthy()
    expect(screen.getByText('完成接口联调')).toBeTruthy()
    expect(screen.getByText('验证回写结果')).toBeTruthy()
    expect(screen.getAllByText('计划时间：2026-10-01 至 2026-10-30')).toHaveLength(2)
    expect(screen.getByText('负责人：项目负责人')).toBeTruthy()
  })
})
