import type { SubTaskItem, TaskItem } from '../types'

export function getKeyTaskAssigneeNames(
  tasks: TaskItem[],
  taskSubMap: Record<number, SubTaskItem[]>,
): string[] {
  const names = tasks
    .flatMap((task) => taskSubMap[task.id] ?? [])
    .map((subtask) => subtask.assignee.trim())
    .filter(Boolean)
  return [...new Set(names)]
}

export function taskHasKeyTaskAssignee(
  task: TaskItem,
  taskSubMap: Record<number, SubTaskItem[]>,
  assignee: string,
): boolean {
  if (!assignee) return true
  return (taskSubMap[task.id] ?? []).some((subtask) => subtask.assignee.trim() === assignee)
}
