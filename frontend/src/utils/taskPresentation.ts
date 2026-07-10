import type { TaskItem } from '../types'

export type IssueTone = 'risk' | 'coordination' | 'decision' | 'delay' | 'none'

/**
 * 三层结构层级标签（语义映射）
 *
 * project  → 项目（Project）
 * task     → 重点工作（Workstream）— 物理表 tasks
 * subtask  → 关键任务（KeyTask）   — 物理表 subtasks
 */
export const TASK_LEVEL_LABELS = {
  project: '项目',
  task: '重点工作',
  subtask: '关键任务',
} as const

export type TaskLevelKey = keyof typeof TASK_LEVEL_LABELS

export type IssueTag = {
  label: string
  tone: IssueTone
}

const ISSUE_RULES: Array<{ tone: IssueTone; label: string; patterns: RegExp[] }> = [
  {
    tone: 'delay',
    label: '延期',
    patterns: [/延期/, /超期/, /逾期/, /滞后/, /拖延/, /未按期/, /未按时/, /卡期/],
  },
  {
    tone: 'decision',
    label: '需决策',
    patterns: [/决策/, /审批/, /拍板/, /定夺/, /选型/, /方案/, /预算/, /确认/, /定案/],
  },
  {
    tone: 'coordination',
    label: '需协调',
    patterns: [/协调/, /配合/, /支持/, /对接/, /权限/, /资源/, /申请/, /参与/, /跨部门/],
  },
  {
    tone: 'risk',
    label: '风险',
    patterns: [/风险/, /问题/, /异常/, /障碍/, /不足/, /缺少/, /不稳/, /卡点/, /隐患/],
  },
]

export function classifyIssue(text: string | null | undefined): IssueTag {
  const value = String(text || '').trim()
  if (!value) {
    return { label: '无', tone: 'none' }
  }

  for (const rule of ISSUE_RULES) {
    if (rule.patterns.some((pattern) => pattern.test(value))) {
      return { label: rule.label, tone: rule.tone }
    }
  }

  return { label: '无', tone: 'none' }
}

export function formatPeopleBlock(task: TaskItem) {
  const coordinator = task.coordinator?.trim() || '-'
  const owner = task.owner?.trim() || '-'
  const collaborators = formatCollaborators(task.collaborators)

  return [
    { label: '统筹', value: coordinator },
    { label: '负责人', value: owner },
    { label: '协同', value: collaborators },
  ]
}

export function formatCollaborators(value: string | null | undefined) {
  const raw = String(value || '').trim()
  if (!raw) {
    return '-'
  }
  return raw
    .split(/[，,、;；\n]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .join('、')
}

export function getTaskLevelLabel(level: TaskLevelKey) {
  return TASK_LEVEL_LABELS[level]
}

export function formatTaskLevelTrail() {
  return [TASK_LEVEL_LABELS.project, TASK_LEVEL_LABELS.task, TASK_LEVEL_LABELS.subtask].join(' / ')
}

export function formatDateTime(value?: string | null) {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatShortDate(value?: string | null) {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

export function formatStatusTone(status: string) {
  if (['已完成', '完成', '已交付', '已关闭', '已决策'].includes(status)) return 'green'
  if (['延期', '超期', '逾期', '滞后'].includes(status)) return 'red'
  if (['待处理', '未开始', '待确认', '待决策'].includes(status)) return 'amber'
  return 'blue'
}
