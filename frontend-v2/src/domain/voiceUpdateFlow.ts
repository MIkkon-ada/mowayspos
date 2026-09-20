type AnyRecord = Record<string, unknown>

export type VoiceContextSubtask = {
  id: number
  title: string
  status?: string
  parent_task_id?: number
  parent_project_id?: number | null
  parent_key_task?: string
  is_deleted?: boolean
}

export function filterSubtasksForVoiceContext<T extends VoiceContextSubtask>(
  subtasks: T[],
  selectedProjectId: number,
): T[] {
  return subtasks.filter((s) => (
    !s.is_deleted &&
    s.parent_project_id === selectedProjectId &&
    s.status !== '已完成' &&
    s.status !== '完成'
  ))
}

export function buildVoiceUpdateHumanResult({
  result,
  editValues,
  selectedProjectId,
  selectedProjectName,
  taskReports,
  keyTaskIssues,
}: {
  result: AnyRecord | null | undefined
  editValues: AnyRecord | null | undefined
  selectedProjectId: number | null
  selectedProjectName: string
  taskReports: unknown[]
  keyTaskIssues: unknown[]
}): AnyRecord {
  return {
    ...(result ?? {}),
    ...(editValues ?? {}),
    special_project: selectedProjectName,
    ...(selectedProjectId != null ? { project_id: selectedProjectId } : {}),
    task_reports: taskReports,
    key_task_issues: keyTaskIssues,
  }
}

export function formatIssueItem(item: unknown): string {
  if (typeof item === 'string') return item.trim()
  if (!item || typeof item !== 'object') return ''
  const record = item as AnyRecord
  const description = String(record.description || record.desc || '').trim()
  if (!description) return ''
  const issueType = String(record.issue_type || record.type || '').trim()
  return issueType ? `${issueType}：${description}` : description
}

export function formatIssueItems(items: unknown): string[] {
  if (!Array.isArray(items)) return []
  return items.map(formatIssueItem).filter(Boolean)
}

export function isValidSubtaskSuggestion(item: unknown): boolean {
  if (!item || typeof item !== 'object') return false
  const record = item as Record<string, unknown>
  return !!(record.parent_task_id && record.title)
}
