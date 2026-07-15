export type ConfirmationAssetItem = Record<string, unknown>

export type ProjectedAchievement = {
  source: 'task_report' | 'submission'
  reportIndex?: number
  achievementIndex: number
  matchedSubtaskId?: number
  matchedSubtaskTitle?: string
  item: ConfirmationAssetItem
}

export type ProjectedIssue = {
  source: 'task_report' | 'submission'
  reportIndex?: number
  issueIndex?: number
  matchedSubtaskId?: number
  matchedSubtaskTitle?: string
  description: string
  item: ConfirmationAssetItem
}

export type ConfirmationAssetProjection = {
  reportAchievements: ProjectedAchievement[]
  submissionAchievements: ProjectedAchievement[]
  reportIssues: ProjectedIssue[]
  submissionIssues: ProjectedIssue[]
  allIssues: ProjectedIssue[]
}

const ISSUE_PREFIXES = [
  '需要负责人决策',
  '需要负责人确认',
  '风险提示：',
  '风险提示:',
  '需决策：',
  '需决策:',
  '待协调：',
  '待协调:',
  '问题：',
  '问题:',
  '风险：',
  '风险:',
  '决策：',
  '决策:',
]

function asRecord(value: unknown, fallbackField: 'name' | 'description'): ConfirmationAssetItem | null {
  if (typeof value === 'string') {
    const text = value.trim()
    return text ? { [fallbackField]: text } : null
  }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null
  return { ...(value as ConfirmationAssetItem) }
}

function normalizedAssetText(value: unknown): string {
  return String(value ?? '')
    .normalize('NFKC')
    .trim()
    .toLowerCase()
    .replace(/[\p{P}\p{Z}\s]+/gu, '')
}

export function normalizeAchievementKey(value: unknown): string {
  return normalizedAssetText(value)
}

export function normalizeIssueKey(value: unknown): string {
  let text = String(value ?? '').normalize('NFKC').trim()
  let removed = true
  while (removed && text) {
    removed = false
    for (const prefix of ISSUE_PREFIXES) {
      if (text.startsWith(prefix)) {
        text = text.slice(prefix.length).trim()
        removed = true
        break
      }
    }
  }
  return normalizedAssetText(text)
}

function bigrams(value: string): Set<string> {
  const result = new Set<string>()
  for (let index = 0; index < value.length - 1; index += 1) {
    result.add(value.slice(index, index + 2))
  }
  return result
}

export function issueKeysAreDuplicate(left: string, right: string): boolean {
  if (!left || !right) return false
  if (left === right) return true
  const shorter = left.length <= right.length ? left : right
  const longer = left.length <= right.length ? right : left
  if (shorter.length < 8) return false
  if (longer.includes(shorter)) return true

  const leftBigrams = bigrams(left)
  const rightBigrams = bigrams(right)
  if (leftBigrams.size === 0 || rightBigrams.size === 0) return false
  let overlap = 0
  for (const pair of leftBigrams) {
    if (rightBigrams.has(pair)) overlap += 1
  }
  const dice = (2 * overlap) / (leftBigrams.size + rightBigrams.size)
  return dice >= 0.85
}

function numericId(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return undefined
}

function reportTitle(report: ConfirmationAssetItem): string | undefined {
  const title = report.matched_subtask_title ?? report.subtask_title ?? report.title
  const text = String(title ?? '').trim()
  return text || undefined
}

function containsDuplicateIssue(key: string, existingKeys: string[]): boolean {
  return existingKeys.some((existing) => issueKeysAreDuplicate(key, existing))
}

export function buildConfirmationAssetProjection(
  result: ConfirmationAssetItem | null | undefined,
): ConfirmationAssetProjection {
  const safeResult = result ?? {}
  const reports = Array.isArray(safeResult.task_reports) ? safeResult.task_reports : []
  const reportAchievements: ProjectedAchievement[] = []
  const submissionAchievements: ProjectedAchievement[] = []
  const reportIssues: ProjectedIssue[] = []
  const submissionIssues: ProjectedIssue[] = []

  const reportAchievementKeys = new Set<string>()
  const reportAchievementKeysBySubtask = new Map<string, Set<string>>()
  const reportIssueKeys: string[] = []
  const reportIssueKeysByScope = new Map<string, string[]>()

  reports.forEach((rawReport, reportIndex) => {
    const report = asRecord(rawReport, 'description')
    if (!report) return
    const matchedSubtaskId = numericId(report.matched_subtask_id ?? report.related_subtask_id)
    const matchedSubtaskTitle = reportTitle(report)
    const reportScope = matchedSubtaskId !== undefined ? `subtask:${matchedSubtaskId}` : `report:${reportIndex}`

    const achievements = Array.isArray(report.achievements) ? report.achievements : []
    const achievementScope = reportAchievementKeysBySubtask.get(reportScope) ?? new Set<string>()
    achievements.forEach((rawItem, achievementIndex) => {
      const item = asRecord(rawItem, 'name')
      if (!item) return
      const key = normalizeAchievementKey(item.name)
      if (!key || achievementScope.has(key)) return
      achievementScope.add(key)
      reportAchievementKeys.add(key)
      reportAchievements.push({
        source: 'task_report',
        reportIndex,
        achievementIndex,
        ...(matchedSubtaskId !== undefined ? { matchedSubtaskId } : {}),
        ...(matchedSubtaskTitle ? { matchedSubtaskTitle } : {}),
        item,
      })
    })
    reportAchievementKeysBySubtask.set(reportScope, achievementScope)

    const issues = Array.isArray(report.subtask_issues) ? report.subtask_issues : []
    const issueScope = reportIssueKeysByScope.get(reportScope) ?? []
    issues.forEach((rawItem, issueIndex) => {
      const item = asRecord(rawItem, 'description')
      if (!item) return
      const description = String(item.description ?? '').trim()
      const key = normalizeIssueKey(description)
      if (!key || containsDuplicateIssue(key, issueScope)) return
      issueScope.push(key)
      reportIssueKeys.push(key)
      reportIssues.push({
        source: 'task_report',
        reportIndex,
        issueIndex,
        ...(matchedSubtaskId !== undefined ? { matchedSubtaskId } : {}),
        ...(matchedSubtaskTitle ? { matchedSubtaskTitle } : {}),
        description,
        item,
      })
    })
    reportIssueKeysByScope.set(reportScope, issueScope)
  })

  const topAchievements = Array.isArray(safeResult.achievements) ? safeResult.achievements : []
  const topAchievementKeys = new Set<string>()
  topAchievements.forEach((rawItem, achievementIndex) => {
    const item = asRecord(rawItem, 'name')
    if (!item) return
    const key = normalizeAchievementKey(item.name)
    if (!key || reportAchievementKeys.has(key) || topAchievementKeys.has(key)) return
    topAchievementKeys.add(key)
    submissionAchievements.push({ source: 'submission', achievementIndex, item })
  })

  const submissionIssueKeys: string[] = []
  const topIssueSources: unknown[][] = [
    Array.isArray(safeResult.key_task_issues) ? safeResult.key_task_issues : [],
    Array.isArray(safeResult.issues) ? safeResult.issues : [],
    Array.isArray(safeResult.pending_items) ? safeResult.pending_items : [],
  ]
  topIssueSources.forEach((items) => {
    items.forEach((rawItem, issueIndex) => {
      const item = asRecord(rawItem, 'description')
      if (!item) return
      const description = String(item.description ?? '').trim()
      const key = normalizeIssueKey(description)
      if (!key || containsDuplicateIssue(key, reportIssueKeys) || containsDuplicateIssue(key, submissionIssueKeys)) return
      submissionIssueKeys.push(key)
      submissionIssues.push({ source: 'submission', issueIndex, description, item })
    })
  })

  return {
    reportAchievements,
    submissionAchievements,
    reportIssues,
    submissionIssues,
    allIssues: [...reportIssues, ...submissionIssues],
  }
}
