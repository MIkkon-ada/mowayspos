/** @vitest-environment jsdom */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { SubTaskItem, TaskItem } from '../../types'
import { MobileTaskList } from './MobileTaskList'

describe('MobileTaskList plan date status', () => {
  it('shows a pending-date marker for an unfinished task without an exact due date', () => {
    const task = { id: 1, key_task: '重点工作' } as TaskItem
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
})
