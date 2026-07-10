export type MyTaskLike = {
  id: number
  status?: string
  parent_project_id?: number | null
}

export function normalizeTaskStatus(status?: string | null): string {
  const raw = String(status ?? '').trim()
  const key = raw.toLowerCase().replace(/\s+/g, '_')
  if (['推进中', '进行中', 'in_progress'].includes(raw) || key === 'in_progress') return '进行中'
  if (['已完成', '完成', '已关闭', 'completed', 'done'].includes(raw) || key === 'completed') return '已完成'
  if (['延期', '已延期', 'delayed'].includes(raw) || key === 'delayed') return '延期'
  if (['暂停', '暂缓', '已暂停', 'paused'].includes(raw) || key === 'paused') return '暂缓'
  return '未开始'
}

export function filterMyTasksByProject<T extends MyTaskLike>(items: T[], projectId: number | null): T[] {
  if (projectId === null) return items
  return items.filter((item) => item.parent_project_id === projectId)
}

export function getMemberTaskActions(status?: string | null): string[] {
  const normalized = normalizeTaskStatus(status)
  if (normalized === '未开始') return ['start', 'report_issue']
  if (normalized === '进行中') return ['submit_progress', 'complete', 'report_issue', 'pause']
  if (normalized === '暂缓' || normalized === '延期') return ['resume', 'submit_progress', 'report_issue']
  return ['view_parent']
}

export function groupMyTasks<T extends MyTaskLike>(items: T[]): Record<string, T[]> {
  return {
    '进行中': items.filter((item) => normalizeTaskStatus(item.status) === '进行中'),
    '未开始': items.filter((item) => normalizeTaskStatus(item.status) === '未开始'),
    '延期/暂缓': items.filter((item) => {
      const s = normalizeTaskStatus(item.status)
      return s === '延期' || s === '暂缓'
    }),
    '已完成': items.filter((item) => normalizeTaskStatus(item.status) === '已完成'),
  }
}
