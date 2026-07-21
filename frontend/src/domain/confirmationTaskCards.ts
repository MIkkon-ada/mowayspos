type AnyRecord = Record<string, unknown>
import { getProjectDisplayName } from './projectDisplay'

export type ConfirmationTaskCard = {
  id: string
  title: string
  status: string
  confirmationStatus: string
  confirmationNote: string
  ceoNote: string
  ceoOperator: string
  ceoDecidedAt: string
  coordinatorRequestNote: string
  coordinatorRequestOperator: string
  coordinatorRequestedAt: string
  coordinatorNote: string
  coordinatorOperator: string
  coordinatorFeedbackAt: string
  structure: {
    projectName: string
    keyTaskName: string
    subtaskName: string
  }
  completedItems: string[]
  achievements: string[]
  pendingItems: string[]
  nextSteps: string[]
  /** 在后端 task_reports 中的原始索引（仅真实卡片有值） */
  backendCardIndex?: number
  /** 是否为后端真实存在的结构化任务卡 */
  isPersistedTaskCard: boolean
}

export type ReviewCardViewModel = {
  id: string | number
  statusText: string
  cardIndexText: string
  title: string
  projectName: string
  taskName: string
  summary: string
  completed: string[]
  pendingItems: string[]
  nextSteps: string[]
  achievements: string[]
}

type BuildConfirmationTaskCardsOptions = {
  projectName?: string
  fallbackKeyTaskName?: string
  fallbackSubtaskNames?: string[]
}

type NormalizeReviewCardOptions = {
  cardIndex?: number
  totalCards?: number
  fallbackProjectName?: string
  fallbackTaskName?: string
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function idValue(value: unknown, fallback: string | number): string | number {
  if (typeof value === 'string' && value.trim()) return value.trim()
  if (typeof value === 'number') return value
  return fallback
}

function asRecord(value: unknown): AnyRecord {
  return typeof value === 'object' && value !== null ? value as AnyRecord : {}
}

function parseJsonRecord(value: unknown): AnyRecord {
  if (typeof value === 'string' && value.trim()) {
    try {
      return asRecord(JSON.parse(value))
    } catch {
      return {}
    }
  }
  return asRecord(value)
}

function firstRecord(source: AnyRecord, keys: string[]): AnyRecord {
  for (const key of keys) {
    const value = parseJsonRecord(source[key])
    if (Object.keys(value).length > 0) return value
  }
  return {}
}

function recordArray(value: unknown): AnyRecord[] {
  return Array.isArray(value)
    ? value.filter((item): item is AnyRecord => typeof item === 'object' && item !== null)
    : []
}

function stringArray(value: unknown): string[] {
  if (typeof value === 'string') {
    return value
      .split(/\r?\n|[；;]\s*|[、]\s*/)
      .map((item) => item.replace(/^[-•·\d.、\s]+/, '').trim())
      .filter(Boolean)
  }
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    if (typeof item === 'string') return item.trim()
    if (typeof item === 'object' && item !== null) {
      const row = item as AnyRecord
      return text(row.name) || text(row.description) || text(row.title) || text(row.content)
    }
    return ''
  }).filter(Boolean)
}

function issueTextArray(value: unknown): string[] {
  return stringArray(value)
}

function achievementTextArray(value: unknown): string[] {
  return recordArray(value)
    .map((item) => text(item.name) || text(item.description) || text(item.title))
    .filter(Boolean)
}

function unique(items: string[]): string[] {
  return Array.from(new Set(items.map((item) => item.trim()).filter(Boolean)))
}

function firstText(source: AnyRecord, keys: string[]): string {
  for (const key of keys) {
    const value = text(source[key])
    if (value) return value
  }
  return ''
}

function firstStringArray(source: AnyRecord, keys: string[]): string[] {
  for (const key of keys) {
    const values = stringArray(source[key])
    if (values.length > 0) return unique(values)
  }
  return []
}

function firstAchievementArray(source: AnyRecord, keys: string[]): string[] {
  for (const key of keys) {
    const values = key === 'achievements' || key === 'deliverables'
      ? unique([...achievementTextArray(source[key]), ...stringArray(source[key])])
      : stringArray(source[key])
    if (values.length > 0) return values
  }
  return []
}

function summaryFallback(completed: string[], nextSteps: string[]): string {
  const parts = [
    completed.length > 0 ? `已完成：${completed.slice(0, 2).join('、')}` : '',
    nextSteps.length > 0 ? `下一步：${nextSteps.slice(0, 2).join('、')}` : '',
  ].filter(Boolean)
  return parts.join('；') || '请审核本次提交内容是否可写入工作推进表。'
}

function preferredReviewSource(source: AnyRecord): AnyRecord {
  const human = firstRecord(source, ['human_result_json', 'humanResult', 'editedResult'])
  if (Object.keys(human).length > 0) return human
  const ai = firstRecord(source, ['ai_result_json', 'aiResult', 'extractResult'])
  if (Object.keys(ai).length > 0) return ai
  return source
}

export function normalizeReviewCardData(
  source: AnyRecord | ConfirmationTaskCard | null | undefined,
  options: NormalizeReviewCardOptions = {},
): ReviewCardViewModel {
  const raw = asRecord(source)
  const data = preferredReviewSource(raw)
  const structure = asRecord(raw.structure)
  const task = asRecord(data.task)
  const completed = firstStringArray(data, [
    'completed',
    'done',
    'weekly_completed',
    'this_week_completed',
    'completed_items',
    'completedItems',
    '本周完成',
    '完成内容',
  ]) || []
  const pendingItems = firstStringArray(data, [
    'issues',
    'problems',
    'risks',
    'pending',
    'pending_items',
    'pendingItems',
    'blockers',
    '需处理事项',
    '问题',
    '风险',
  ])
  const nextSteps = firstStringArray(data, [
    'next_steps',
    'next_plan',
    'nextSteps',
    'plan',
    'next',
    '下一步计划',
    '下周计划',
  ])
  const achievements = firstAchievementArray(data, [
    'achievements',
    'results',
    'outputs',
    'deliverables',
    '成果',
    '可入库成果',
  ])

  const projectName = getProjectDisplayName([], data) ||
    firstText(data, ['special_project', 'projectName', 'project_name']) ||
    text(structure.projectName) ||
    options.fallbackProjectName ||
    '-'
  const taskName = firstText(data, ['related_task', 'taskName', 'task_name', 'key_task']) ||
    text(structure.keyTaskName) ||
    text(task.key_task) ||
    options.fallbackTaskName ||
    '-'
  const title = firstText(data, ['title', 'task_title', 'subtask_title', 'related_subtask']) ||
    text(raw.title) ||
    text(structure.subtaskName) ||
    taskName
  const statusText = firstText(data, ['statusText', 'status_update', 'status_suggestion', 'status']) ||
    text(raw.status) ||
    text(raw.confirm_status) ||
    '待确认'
  const summary = firstText(data, ['summary', '重点', '本卡重点']) || summaryFallback(completed, nextSteps)
  const cardIndex = options.cardIndex ?? 0
  const totalCards = Math.max(options.totalCards ?? 1, 1)

  return {
    id: idValue(raw.id, idValue(data.id, cardIndex)),
    statusText,
    cardIndexText: `任务卡 ${cardIndex + 1}/${totalCards}`,
    title,
    projectName,
    taskName,
    summary,
    completed,
    pendingItems,
    nextSteps,
    achievements,
  }
}

export function buildConfirmationTaskCards(
  result: AnyRecord | null | undefined,
  options: BuildConfirmationTaskCardsOptions = {},
): ConfirmationTaskCard[] {
  const data = result ?? {}
  const task = asRecord(data.task)
  const projectName = options.projectName || getProjectDisplayName([], data) || getProjectDisplayName([], task) || '-'
  const fallbackKeyTaskName = options.fallbackKeyTaskName || text(data.related_task) || text(task.key_task) || '-'
  const fallbackSubtaskName = options.fallbackSubtaskNames?.filter(Boolean).join(' / ') || text(data.related_subtask) || '-'
  const reports = recordArray(data.task_reports)

  if (reports.length > 0) {
    return reports.map((report, index) => {
      const keyTaskName = text(report.parent_key_task) || fallbackKeyTaskName
      const subtaskName = text(report.matched_subtask_title) || text(report.title) || fallbackSubtaskName
      const completedItems = unique([text(report.completed), ...stringArray(report.completed_items)])
      const achievements = unique(achievementTextArray(report.achievements))
      const pendingItems = unique(issueTextArray(report.subtask_issues))
      const nextSteps = unique(stringArray(report.next_steps))

      return {
        id: String(report.matched_subtask_id || report.parent_task_id || report.title || index),
        title: subtaskName !== '-' ? subtaskName : keyTaskName,
        confirmationStatus: text(report.confirmation_status) || 'pending',
        confirmationNote: text(report.confirmation_note),
        ceoNote: text(report.ceo_note),
        ceoOperator: text(report.ceo_operator),
        ceoDecidedAt: text(report.ceo_decided_at),
        coordinatorRequestNote: text(report.coordinator_request_note),
        coordinatorRequestOperator: text(report.coordinator_request_operator),
        coordinatorRequestedAt: text(report.coordinator_requested_at),
        coordinatorNote: text(report.coordinator_note),
        coordinatorOperator: text(report.coordinator_operator),
        coordinatorFeedbackAt: text(report.coordinator_feedback_at),
        status: text(report.status_update) || '进行中',
        structure: {
          projectName,
          keyTaskName,
          subtaskName,
        },
        completedItems,
        achievements,
        pendingItems,
        nextSteps,
        backendCardIndex: index,
        isPersistedTaskCard: true,
      }
    })
  }

  return [{
    id: 'legacy',
    title: fallbackSubtaskName !== '-' ? fallbackSubtaskName : fallbackKeyTaskName,
    confirmationStatus: text(data.confirmation_status) || 'pending',
    confirmationNote: text(data.confirmation_note),
    ceoNote: text(data.ceo_note),
    ceoOperator: text(data.ceo_operator),
    ceoDecidedAt: text(data.ceo_decided_at),
    coordinatorRequestNote: text(data.coordinator_request_note),
    coordinatorRequestOperator: text(data.coordinator_request_operator),
    coordinatorRequestedAt: text(data.coordinator_requested_at),
    coordinatorNote: text(data.coordinator_note),
    coordinatorOperator: text(data.coordinator_operator),
    coordinatorFeedbackAt: text(data.coordinator_feedback_at),
    status: text(data.status_suggestion) || text(task.status) || '进行中',
    structure: {
      projectName,
      keyTaskName: fallbackKeyTaskName,
      subtaskName: fallbackSubtaskName,
    },
    completedItems: unique(stringArray(data.completed_items)),
    achievements: unique(achievementTextArray(data.achievements)),
    pendingItems: unique([...issueTextArray(data.issues), ...issueTextArray(data.key_task_issues), ...issueTextArray(data.pending_items)]),
    nextSteps: unique(stringArray(data.next_steps)),
    backendCardIndex: undefined,
    isPersistedTaskCard: false,
  }]
}
