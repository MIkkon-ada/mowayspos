import { describe, expect, it } from 'vitest'
import type { SubTaskItem, TaskItem } from '../types'
import { getKeyTaskAssigneeNames, taskHasKeyTaskAssignee } from './keyTaskAssigneeFilter'

const task = (id: number): TaskItem => ({ id, key_task: `重点工作 ${id}` } as TaskItem)
const keyTask = (taskId: number, assignee: string): SubTaskItem => ({
  id: taskId * 10,
  task_id: taskId,
  title: '关键任务',
  assignee,
  plan_time: '',
  status: '未开始',
})

describe('key-task assignee filter', () => {
  it('lists only distinct non-empty key-task assignees for loaded workstreams', () => {
    expect(getKeyTaskAssigneeNames([task(1), task(2)], {
      1: [keyTask(1, '李明'), keyTask(1, '王芳')],
      2: [keyTask(2, '李明'), keyTask(2, ' ')],
      999: [keyTask(999, '不属于当前项目')],
    })).toEqual(['李明', '王芳'])
  })

  it('matches a workstream only when it has a key task for the selected assignee', () => {
    const taskSubMap = { 1: [keyTask(1, '李明')], 2: [keyTask(2, '王芳')] }

    expect(taskHasKeyTaskAssignee(task(1), taskSubMap, '李明')).toBe(true)
    expect(taskHasKeyTaskAssignee(task(2), taskSubMap, '李明')).toBe(false)
  })
})
