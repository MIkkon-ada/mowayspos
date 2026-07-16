import type {
  AchievementItem,
  IssueItem,
  MeetingItem,
  Project,
  ProjectCloseRequest,
  ProjectMember,
  TaskItem,
} from '../../types'
import type { SubTaskWithParent } from '../../api/subtasks'
import type { UpdateHistoryItem } from '../../api/updates'
import type { OperationLogItem } from '../../api/logs'

export const ARCHIVE_METRIC_LABELS = [
  '计划周期',
  '实际周期',
  '里程碑完成率',
  '关键任务完成率',
  '成果交付率',
  '问题关闭率',
] as const

export type ArchiveMetric = {
  label: (typeof ARCHIVE_METRIC_LABELS)[number]
  value: string
  detail: string
}

export type ArchiveProgressRow = {
  id: number
  name: string
  planTime: string
  total: number
  completed: number
  rate: string
  status: string
}

export type ArchiveTimelineEvent = {
  id: string
  title: string
  detail: string
  at: string | null
  tone: 'blue' | 'orange' | 'red' | 'green'
}

export type ArchiveObjectiveStatus = '未记录' | '部分完成' | '已完成'

export function getArchiveObjectiveStatus(
  objectiveResult?: string | null,
): ArchiveObjectiveStatus {
  const normalizedResult = objectiveResult?.trim()
  if (!normalizedResult) return '未记录'
  if (normalizedResult.includes('部分完成')) return '部分完成'
  return '已完成'
}

const DONE = new Set(['completed', 'complete', 'done', '已完成', '完成', '已确认', '已入库', '已验收'])
const ACTIVE = new Set(['in_progress', 'progress', '进行中', '执行中'])
const CLOSED = new Set(['closed', 'resolved', 'decided', '已关闭', '已解决', '已决策', '关闭', '解决'])
const DELIVERED = new Set(['completed', 'complete', 'done', 'confirmed', 'accepted', 'stored', '已完成', '已确认', '已入库', '已验收'])

function normalized(value: unknown): string {
  return String(value ?? '').trim().toLowerCase()
}

export function isCompleted(value: unknown): boolean {
  return DONE.has(normalized(value))
}

export function formatArchiveDate(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, 10) || '—'
  return new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).format(date)
}

export function formatArchiveDateTime(value?: string | null): string {
  if (!value) return '时间未记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(date)
}

function durationDays(start?: string | null, end?: string | null): number | null {
  if (!start || !end) return null
  const startMs = new Date(start).getTime()
  const endMs = new Date(end).getTime()
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs < startMs) return null
  return Math.max(1, Math.ceil((endMs - startMs) / 86_400_000) + 1)
}

function periodMetric(start?: string | null, end?: string | null): Pick<ArchiveMetric, 'value' | 'detail'> {
  const days = durationDays(start, end)
  if (days === null) return { value: '—', detail: '日期未完整记录' }
  return { value: `${days} 天`, detail: `${formatArchiveDate(start)} → ${formatArchiveDate(end)}` }
}

function rateMetric(done: number, total: number): Pick<ArchiveMetric, 'value' | 'detail'> {
  if (total === 0) return { value: '—', detail: '暂无数据' }
  return { value: `${Math.round((done / total) * 100)}%`, detail: `${done} / ${total}` }
}

export function latestApprovedCloseRequest(rows: ProjectCloseRequest[]): ProjectCloseRequest | null {
  return rows
    .filter((row) => row.status === 'approved')
    .sort((a, b) => Date.parse(b.reviewed_at ?? b.updated_at ?? b.created_at ?? '') - Date.parse(a.reviewed_at ?? a.updated_at ?? a.created_at ?? ''))[0] ?? null
}

export function findArchiveLog(logs: OperationLogItem[]): OperationLogItem | null {
  return logs
    .filter((log) => /archive|archived|归档/i.test(log.action))
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0] ?? null
}

export function buildArchiveMetrics(input: {
  project: Project
  closeRequest: ProjectCloseRequest | null
  tasks: TaskItem[]
  subtasks: SubTaskWithParent[]
  achievements: AchievementItem[]
  issues: IssueItem[]
}): ArchiveMetric[] {
  const { project, closeRequest, tasks, subtasks, achievements, issues } = input
  const plan = periodMetric(project.start_date, project.end_date)
  const actual = periodMetric(project.start_date, closeRequest?.reviewed_at)
  const taskRate = rateMetric(tasks.filter((row) => isCompleted(row.status)).length, tasks.length)
  const subtaskRate = rateMetric(subtasks.filter((row) => isCompleted(row.status)).length, subtasks.length)
  const achievementRate = rateMetric(achievements.filter((row) => DELIVERED.has(normalized(row.status))).length, achievements.length)
  const issueRate = rateMetric(issues.filter((row) => CLOSED.has(normalized(row.status))).length, issues.length)
  return [
    { label: '计划周期', ...plan },
    { label: '实际周期', ...actual },
    { label: '里程碑完成率', ...taskRate },
    { label: '关键任务完成率', ...subtaskRate },
    { label: '成果交付率', ...achievementRate },
    { label: '问题关闭率', ...issueRate },
  ]
}

export function buildProgressRows(tasks: TaskItem[], subtasks: SubTaskWithParent[]): ArchiveProgressRow[] {
  return tasks.map((task) => {
    const children = subtasks.filter((subtask) => subtask.parent_task_id === task.id || subtask.task_id === task.id)
    const completed = children.filter((row) => isCompleted(row.status)).length
    return {
      id: task.id,
      name: task.key_task || `重点工作 #${task.id}`,
      planTime: task.plan_time || '—',
      total: children.length,
      completed,
      rate: children.length > 0 ? `${Math.round((completed / children.length) * 100)}%` : '—',
      status: task.status || '未记录',
    }
  })
}

export function buildProgressDistribution(subtasks: SubTaskWithParent[]) {
  const completed = subtasks.filter((row) => isCompleted(row.status)).length
  const inProgress = subtasks.filter((row) => ACTIVE.has(normalized(row.status))).length
  return { completed, inProgress, incomplete: Math.max(0, subtasks.length - completed - inProgress), total: subtasks.length }
}

export function parseMeetingDecisions(meeting: MeetingItem): string[] {
  if (!meeting.decision_items_json?.trim()) return []
  try {
    const parsed = JSON.parse(meeting.decision_items_json)
    const items = Array.isArray(parsed) ? parsed : [parsed]
    return items.map((item) => {
      if (typeof item === 'string') return item.trim()
      if (item && typeof item === 'object') {
        const record = item as Record<string, unknown>
        return String(record.decision ?? record.content ?? record.title ?? record.item ?? '').trim()
      }
      return ''
    }).filter(Boolean)
  } catch {
    return []
  }
}

function pushEvent(events: ArchiveTimelineEvent[], event: ArchiveTimelineEvent) {
  events.push(event)
}

export function getArchiveOperationTitle(action: string): string {
  const labels: Record<string, string> = {
    archive_project: '项目归档',
    project_close_request_create: '提交结束申请',
    project_close_request_update: '更新结束材料',
    project_close_request_cancel: '取消结束申请',
    project_close_request_approve: '批准项目结束',
    project_close_request_reject: '退回结束申请',
    create_project: '创建项目',
    dispatch_project: '项目下发',
    kickoff_project: '项目启动',
    update_project: '更新项目资料',
    project_kickoff: '项目启动',
    project_close_approved: '项目结束',
    project_close_rejected: '结束申请已退回',
    project_archived: '项目归档',
  }
  return labels[action] || action || '项目操作'
}

export function buildArchiveTimeline(input: {
  project: Project
  updates: UpdateHistoryItem[]
  meetings: MeetingItem[]
  closeRequests: ProjectCloseRequest[]
  logs: OperationLogItem[]
}): ArchiveTimelineEvent[] {
  const { project, updates, meetings, closeRequests, logs } = input
  const events: ArchiveTimelineEvent[] = []
  if (project.kickoff_date) pushEvent(events, { id: 'kickoff', title: '项目启动', detail: project.kickoff_by || '启动记录', at: project.kickoff_date, tone: 'blue' })
  updates.forEach((row) => pushEvent(events, { id: `update-${row.id}`, title: row.title || '提交工作汇报', detail: row.submitter || '项目成员', at: row.created_at, tone: 'blue' }))
  meetings.forEach((row) => pushEvent(events, { id: `meeting-${row.id}`, title: row.title || '项目会议', detail: row.host || row.meeting_type || '会议记录', at: row.meeting_date || row.created_at || null, tone: 'orange' }))
  closeRequests.forEach((row) => {
    pushEvent(events, { id: `close-created-${row.id}`, title: `提交结束申请 #${row.id}`, detail: row.requester_name || '申请人未记录', at: row.created_at, tone: 'blue' })
    if (row.status === 'approved') pushEvent(events, { id: `close-approved-${row.id}`, title: `结束申请已批准 #${row.id}`, detail: row.reviewer_name || '审核人未记录', at: row.reviewed_at, tone: 'green' })
    if (row.status === 'rejected') pushEvent(events, { id: `close-rejected-${row.id}`, title: `结束申请已退回 #${row.id}`, detail: row.reviewer_name || '审核人未记录', at: row.reviewed_at, tone: 'red' })
    if (row.status === 'cancelled') pushEvent(events, { id: `close-cancelled-${row.id}`, title: `结束申请已取消 #${row.id}`, detail: row.requester_name || '申请人未记录', at: row.cancelled_at, tone: 'orange' })
  })
  logs.forEach((log) => pushEvent(events, { id: `log-${log.id}`, title: getArchiveOperationTitle(log.action), detail: log.operator || '系统', at: log.created_at, tone: /archive|归档/i.test(log.action) ? 'green' : 'blue' }))
  if (project.status === 'archived' && !events.some((event) => /归档/.test(event.title))) {
    pushEvent(events, { id: 'archived-status', title: '项目已归档', detail: '归档时间未记录', at: null, tone: 'green' })
  }
  return events.sort((a, b) => {
    if (!a.at) return 1
    if (!b.at) return -1
    return Date.parse(b.at) - Date.parse(a.at)
  })
}

export function getMemberRoleSummary(members: ProjectMember[], project: Project) {
  const names = (role: string) => members.filter((member) => member.role === role).map((member) => member.person_name_snapshot).filter(Boolean)
  const owners = names('owner')
  const coordinators = names('coordinator')
  return {
    owner: owners.length ? owners.join('、') : project.owners?.join('、') || '未配置',
    projectCeo: names('project_ceo').join('、') || '未配置',
    coordinator: coordinators.length ? coordinators.join('、') : project.coordinator?.trim() || '未配置',
    count: members.length || project.collaborators?.length || 0,
  }
}
