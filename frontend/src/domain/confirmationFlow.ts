export type ConfirmationType =
  | 'progress_update'
  | 'subtask_completion'
  | 'suggest_new_subtask'
  | 'issue_report'
  | 'achievement_submit'
  | 'new_key_task'
  | 'meeting_summary'
  | 'mixed_update'
  | 'unknown'

export type ConfirmationClassification = {
  type: ConfirmationType
  label: string
}

export type ConfirmationContext = {
  sourceType: string
  submitter: string
  projectName: string
  keyTaskName: string
  subtaskNames: string[]
}

import { getProjectDisplayName } from './projectDisplay'

type AnyRecord = Record<string, unknown>

const TYPE_LABEL: Record<ConfirmationType, string> = {
  progress_update: '关键任务进展更新',
  subtask_completion: '关键任务完成提交',
  suggest_new_subtask: '建议新增关键任务',
  issue_report: '问题/风险/决策上报',
  achievement_submit: '成果提交',
  new_key_task: '新增重点工作',
  meeting_summary: '会议纪要沉淀',
  mixed_update: '混合更新',
  unknown: '待人工判断',
}

function asRecordArray(value: unknown): AnyRecord[] {
  return Array.isArray(value)
    ? value.filter((item): item is AnyRecord => typeof item === 'object' && item !== null)
    : []
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function taskReports(result: AnyRecord): AnyRecord[] {
  return asRecordArray(result.task_reports)
}

function issueItems(result: AnyRecord): AnyRecord[] {
  return [
    ...asRecordArray(result.key_task_issues),
    ...asRecordArray(result.issues).filter((item) => text(item.description)),
  ]
}

function achievementItems(result: AnyRecord): AnyRecord[] {
  return asRecordArray(result.achievements).filter((item) => text(item.name))
}

function progressReports(result: AnyRecord): AnyRecord[] {
  return taskReports(result).filter((report) => text(report.type) === 'progress' && report.matched_subtask_id)
}

function newTaskReports(result: AnyRecord): AnyRecord[] {
  return taskReports(result).filter((report) => text(report.type) === 'new_task' || text(report.title))
}

function suggestReports(result: AnyRecord): AnyRecord[] {
  return taskReports(result).filter((report) => text(report.result_type) === 'suggest_new_subtask')
}

function completedReports(result: AnyRecord): AnyRecord[] {
  return progressReports(result).filter((report) => text(report.status_update) === '已完成')
}

function isSubtaskStatusUpdate(result: AnyRecord): boolean {
  return text(result.result_type) === 'subtask_status_update'
}

function hasLegacyNewTask(result: AnyRecord): boolean {
  if (isSubtaskStatusUpdate(result)) return false
  const task = typeof result.task === 'object' && result.task !== null ? result.task as AnyRecord : {}
  return Boolean(text(task.key_task) || text(result.related_task))
}

export function classifyConfirmation(result: AnyRecord | null | undefined): ConfirmationClassification {
  const data = result ?? {}
  if (isSubtaskStatusUpdate(data)) {
    return text(data.to_status) === '已完成'
      ? { type: 'subtask_completion', label: TYPE_LABEL.subtask_completion }
      : { type: 'progress_update', label: TYPE_LABEL.progress_update }
  }
  const hasProgress = progressReports(data).length > 0
  const hasCompletion = completedReports(data).length > 0
  const hasSuggest = suggestReports(data).length > 0
  const hasIssues = issueItems(data).length > 0
  const hasAchievements = achievementItems(data).length > 0
  const hasNewTask = newTaskReports(data).length > 0 || hasLegacyNewTask(data)

  const categories = [
    hasCompletion || hasProgress,
    hasSuggest,
    hasIssues,
    hasAchievements,
    hasNewTask && !hasProgress && !hasSuggest,
  ].filter(Boolean).length

  if (categories > 1) return { type: 'mixed_update', label: TYPE_LABEL.mixed_update }
  if (hasCompletion) return { type: 'subtask_completion', label: TYPE_LABEL.subtask_completion }
  if (hasProgress) return { type: 'progress_update', label: TYPE_LABEL.progress_update }
  if (hasSuggest) return { type: 'suggest_new_subtask', label: TYPE_LABEL.suggest_new_subtask }
  if (hasIssues) return { type: 'issue_report', label: TYPE_LABEL.issue_report }
  if (hasAchievements) return { type: 'achievement_submit', label: TYPE_LABEL.achievement_submit }
  if (text(data.source_type).includes('会议')) return { type: 'meeting_summary', label: TYPE_LABEL.meeting_summary }
  if (hasNewTask) return { type: 'new_key_task', label: TYPE_LABEL.new_key_task }
  return { type: 'unknown', label: TYPE_LABEL.unknown }
}

export function buildConfirmationEffects(result: AnyRecord | null | undefined): string[] {
  const data = result ?? {}
  const effects: string[] = []
  if (isSubtaskStatusUpdate(data)) {
    const title = text(data.subtask_title) || '关键任务'
    const toStatus = text(data.to_status) || text(data.suggested_status) || '目标状态'
    return [`将「${title}」状态变更为「${toStatus}」`, '保留所属重点工作状态，由负责人判断是否关闭']
  }
  const matchedCount = progressReports(data).length
  const completedCount = completedReports(data).length
  const suggestCount = suggestReports(data).length
  const issueCount = issueItems(data).length
  const achievementCount = achievementItems(data).length
  const newTaskCount = newTaskReports(data).length

  if (completedCount > 0) {
    effects.push(`将 ${completedCount} 个已匹配关键任务标记为已完成`)
  } else if (matchedCount > 0) {
    effects.push(`更新 ${matchedCount} 个已匹配关键任务的进展记录`)
  }
  if (suggestCount > 0) effects.push(`建议新增 ${suggestCount} 个关键任务，需负责人选择归属重点工作后确认`)
  if (newTaskCount > 0) effects.push(`创建 ${newTaskCount} 个新关键任务草稿/任务项`)
  if (hasLegacyNewTask(data) && matchedCount === 0 && newTaskCount === 0) effects.push('写入工作推进表重点工作')
  if (achievementCount > 0) effects.push(`写入成果库 ${achievementCount} 条`)
  if (issueCount > 0) effects.push(`写入问题与决策 ${issueCount} 条`)
  if (matchedCount > 0) effects.push('保留所属重点工作状态，由负责人判断是否关闭')
  if (effects.length === 0) effects.push('需要负责人人工判断入库去向')
  return effects
}

export function getConfirmationContext(result: AnyRecord | null | undefined): ConfirmationContext {
  const data = result ?? {}
  const task = typeof data.task === 'object' && data.task !== null ? data.task as AnyRecord : {}
  const subtaskNames = isSubtaskStatusUpdate(data)
    ? [text(data.subtask_title)].filter(Boolean)
    : progressReports(data)
    .map((report) => text(report.matched_subtask_title))
    .filter(Boolean)

  return {
    sourceType: text(data.source_type),
    submitter: text(data.submitter),
    projectName: getProjectDisplayName([], data) || getProjectDisplayName([], task),
    keyTaskName: text(data.key_task) || text(data.related_task) || text(task.key_task),
    subtaskNames,
  }
}
