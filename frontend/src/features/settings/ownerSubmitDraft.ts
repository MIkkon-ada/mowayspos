import type {
  AgentSubTask,
  AgentTask,
  PositiveId,
  ProjectInitAiDraft,
  ProjectInitCurrentDraft,
} from '../../api/projectInitAi'
import type { ProjectWorkProgressTaskDraft as SubmitTaskDraft } from '../../api/projects'

export type OwnerSubmitAiDecisionAction = 'new' | 'ignore' | 'supplement'

export type OwnerSubmitAiDecision = {
  key: string
  action: OwnerSubmitAiDecisionAction
  itemType: 'task' | 'subtask'
  taskIndex: number
  subtaskIndex?: number
  title: string
}

type DraftRecord = Record<string, any>

export type OwnerSubmitMergeContext = {
  knownTaskIds?: ReadonlyArray<number>
  knownSubtaskIds?: ReadonlyArray<number>
  knownMemberIds?: ReadonlyArray<number>
}

export type OwnerSubmitMergePreview = {
  draft: ProjectInitCurrentDraft
  changeCount: number
  addedTaskCount: number
  supplementedTaskCount: number
  warningCount: number
  warnings: string[]
}

const BLOCKING_PERSON_WARNINGS = new Set([
  'ambiguous_person',
  'inactive_person',
  'person_not_found',
  'helper_conflicts_with_owner',
])

function clone<T>(value: T): T {
  if (Array.isArray(value)) return value.map((item) => clone(item)) as T
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value as DraftRecord).map(([key, item]) => [key, clone(item)])) as T
  }
  return value
}

function isBlank(value: unknown): boolean {
  return value === undefined || value === null || (typeof value === 'string' && value.trim() === '')
}

function normaliseTitle(value: unknown): string {
  return typeof value === 'string' ? value.trim().replace(/\s+/g, ' ').toLowerCase() : ''
}

function positiveId(value: unknown, label: string): number | null {
  if (value === null || value === undefined || value === '') return null
  if (typeof value !== 'number' || !Number.isInteger(value) || value <= 0) {
    throw new TypeError(`${label} must be a positive integer`)
  }
  return value
}

function validateKnownId(value: unknown, label: string, known: ReadonlySet<number> | undefined): number | null {
  const id = positiveId(value, label)
  if (id !== null && known && !known.has(id)) throw new RangeError(`${label} references unknown ${label.includes('member') ? 'member' : 'snapshot record'} ID`)
  return id
}

function asSet(values?: ReadonlyArray<number>): Set<number> | undefined {
  if (!values) return undefined
  const result = new Set<number>()
  values.forEach((value, index) => {
    positiveId(value, `known ID ${index}`)
    result.add(value)
  })
  return result
}

function readId(record: DraftRecord, keys: string[], label: string, known?: ReadonlySet<number>): number | null {
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(record, key)) return validateKnownId(record[key], label, known)
  }
  return null
}

function warningCodes(item: DraftRecord): Set<string> {
  return new Set((Array.isArray(item.warnings) ? item.warnings : []).map((warning: DraftRecord) => String(warning?.code ?? '')))
}

function hasBlockingPersonWarning(item: DraftRecord): boolean {
  return [...warningCodes(item)].some((code) => BLOCKING_PERSON_WARNINGS.has(code))
}

function decisionMap(decisions: OwnerSubmitAiDecision[]): Map<string, OwnerSubmitAiDecisionAction> {
  const result = new Map<string, OwnerSubmitAiDecisionAction>()
  for (const decision of decisions) {
    if (!['new', 'ignore', 'supplement'].includes(decision.action)) throw new TypeError(`invalid decision ${decision.action}`)
    result.set(decision.key, decision.action)
  }
  return result
}

function evidenceKey(item: DraftRecord): string {
  return [item.attachment_id ?? '', item.file_name ?? '', item.location ?? '', item.excerpt ?? ''].join('|')
}

function mergeEvidence(existing: unknown, incoming: unknown, sourceLabel: string): DraftRecord[] {
  const result: DraftRecord[] = []
  const seen = new Set<string>()
  for (const value of [...(Array.isArray(existing) ? existing : []), ...(Array.isArray(incoming) ? incoming : [])]) {
    if (!value || typeof value !== 'object') continue
    const item = clone(value as DraftRecord)
    if (isBlank(item.source_label) && sourceLabel) item.source_label = sourceLabel
    const key = evidenceKey(item)
    if (seen.has(key)) continue
    seen.add(key)
    result.push(item)
  }
  return result
}

function mergeEmptyFields(target: DraftRecord, source: DraftRecord, fields: string[]): void {
  for (const field of fields) {
    if (isBlank(target[field]) && !isBlank(source[field])) target[field] = clone(source[field])
  }
}

function validateCurrentIds(current: ProjectInitCurrentDraft, context: OwnerSubmitMergeContext): { taskIds: Set<number>; subtaskIds: Set<number>; memberIds?: ReadonlySet<number> } {
  const taskIds = asSet(context.knownTaskIds) ?? new Set<number>()
  const subtaskIds = asSet(context.knownSubtaskIds) ?? new Set<number>()
  const memberIds = asSet(context.knownMemberIds)
  current.forEach((task, taskIndex) => {
    const taskRecord = task as DraftRecord
    const taskId = readId(taskRecord, ['id', 'task_id'], `task ${taskIndex}`, taskIds.size > 0 ? taskIds : undefined)
    if (taskId !== null) taskIds.add(taskId)
    const subtasks = Array.isArray(taskRecord.subtasks) ? taskRecord.subtasks : []
    subtasks.forEach((subtask: DraftRecord, subtaskIndex: number) => {
      const subtaskId = readId(subtask, ['id', 'subtask_id'], `subtask ${taskIndex}-${subtaskIndex}`, subtaskIds.size > 0 ? subtaskIds : undefined)
      if (subtaskId !== null) subtaskIds.add(subtaskId)
      validateKnownId(subtask.assignee_id, `subtask ${taskIndex}-${subtaskIndex} member`, memberIds)
      for (const helperId of Array.isArray(subtask.helper_ids) ? subtask.helper_ids : []) validateKnownId(helperId, `subtask ${taskIndex}-${subtaskIndex} member`, memberIds)
    })
  })
  return { taskIds, subtaskIds, memberIds }
}

function validateAiIds(task: DraftRecord, context: { taskIds: ReadonlySet<number>; subtaskIds: ReadonlySet<number>; memberIds?: ReadonlySet<number> }): void {
  validateKnownId(task.owner_id, 'task member', context.memberIds)
  validateKnownId(task.duplicate_of, 'task duplicate_of', context.taskIds)
  const taskWarnings = hasBlockingPersonWarning(task)
  if (taskWarnings && task.owner_id !== null && task.owner_id !== undefined) positiveId(task.owner_id, 'task owner_id')
  for (const subtask of Array.isArray(task.subtasks) ? task.subtasks : []) {
    validateKnownId(subtask.assignee_id, 'subtask member', context.memberIds)
    validateKnownId(subtask.duplicate_of, 'subtask duplicate_of', context.subtaskIds)
    for (const helperId of Array.isArray(subtask.helper_ids) ? subtask.helper_ids : []) validateKnownId(helperId, 'subtask member', context.memberIds)
  }
}

function prepareTask(task: AgentTask, isNew: boolean): DraftRecord {
  const source = task as DraftRecord
  const result: DraftRecord = {
    title: source.title ?? '',
    description: source.description ?? '',
    owner: source.owner_name ?? '',
    helper: '',
    plan_start: source.plan_start ?? '',
    plan_end: source.plan_end ?? '',
    subtasks: [],
    evidence: mergeEvidence([], source.evidence, source.source ?? ''),
  }
  // A newly created task never trusts model-selected member IDs. Names remain
  // visible so the owner can choose a person in the existing picker.
  if (!isNew && !hasBlockingPersonWarning(source) && source.owner_id !== null && source.owner_id !== undefined) result.owner_id = source.owner_id
  return result
}

function prepareSubtask(subtask: AgentSubTask, isNew: boolean): DraftRecord {
  const source = subtask as DraftRecord
  const result: DraftRecord = {
    title: source.title ?? '',
    evaluation_standard: source.evaluation_standard ?? '',
    assignee: source.assignee_name ?? '',
    assignee_id: null,
    helper: Array.isArray(source.helper_names) ? source.helper_names.join('、') : '',
    helper_ids: [],
    plan_start: source.plan_start ?? '',
    plan_end: source.plan_end ?? '',
    evidence: mergeEvidence([], source.evidence, source.source ?? ''),
  }
  if (!isNew && !hasBlockingPersonWarning(source)) {
    if (source.assignee_id !== null && source.assignee_id !== undefined) result.assignee_id = source.assignee_id
    result.helper_ids = Array.isArray(source.helper_ids) ? [...source.helper_ids] : []
  }
  return result
}

function findTaskIndex(current: DraftRecord[], task: DraftRecord, duplicateOf: number | null, allowTitleFallback = false): number {
  if (duplicateOf !== null) {
    const index = current.findIndex((item) => readId(item, ['id', 'task_id'], 'task') === duplicateOf)
    if (index >= 0) return index
  }
  if (task.merge_status !== 'new' || allowTitleFallback) {
    const title = normaliseTitle(task.title)
    const index = current.findIndex((item) => normaliseTitle(item.title) === title && title !== '')
    if (index >= 0) return index
  }
  return -1
}

function findSubtaskIndex(current: DraftRecord[], subtask: DraftRecord, duplicateOf: number | null): number {
  if (duplicateOf !== null) {
    const index = current.findIndex((item) => readId(item, ['id', 'subtask_id'], 'subtask') === duplicateOf)
    if (index >= 0) return index
  }
  const title = normaliseTitle(subtask.title)
  return current.findIndex((item) => normaliseTitle(item.title) === title && title !== '')
}

function applyTaskSupplement(target: DraftRecord, source: DraftRecord): void {
  mergeEmptyFields(target, source, ['description', 'owner', 'helper', 'plan_start', 'plan_end', 'status', 'priority'])
  target.evidence = mergeEvidence(target.evidence, source.evidence, source.source ?? '')
}

function applySubtaskSupplement(target: DraftRecord, source: DraftRecord): void {
  mergeEmptyFields(target, source, ['evaluation_standard', 'assignee', 'helper', 'plan_start', 'plan_end', 'status', 'priority'])
  if (isBlank(target.assignee_id) && !isBlank(source.assignee_id)) target.assignee_id = source.assignee_id
  if ((!Array.isArray(target.helper_ids) || target.helper_ids.length === 0) && Array.isArray(source.helper_ids) && source.helper_ids.length > 0) target.helper_ids = [...source.helper_ids]
  target.evidence = mergeEvidence(target.evidence, source.evidence, source.source ?? '')
}

function addSubtasks(target: DraftRecord, task: AgentTask, actionMap: Map<string, OwnerSubmitAiDecisionAction>, taskIndex: number, isNewTask: boolean): void {
  const existing = Array.isArray(target.subtasks) ? target.subtasks : []
  const next = [...existing]
  task.subtasks.forEach((subtask, subtaskIndex) => {
    const source = subtask as DraftRecord
    const key = `task-${taskIndex}-subtask-${subtaskIndex}`
    const action = actionMap.get(key)
    if (action === 'ignore') return
    if (source.merge_status !== 'new' && !action && !isNewTask) return
    const prepared = prepareSubtask(subtask, isNewTask)
    if (action === 'supplement' && !isNewTask) {
      const existingIndex = findSubtaskIndex(next, source, source.duplicate_of ?? null)
      if (existingIndex >= 0) applySubtaskSupplement(next[existingIndex], prepared)
      return
    }
    if (action !== 'new' && source.merge_status !== 'new' && !isNewTask) return
    next.push(prepared)
  })
  target.subtasks = next
}

export function mergeAiDraft(
  currentDraft: ProjectInitCurrentDraft,
  aiDraft: ProjectInitAiDraft,
  decisions: OwnerSubmitAiDecision[],
  context: OwnerSubmitMergeContext = {},
): ProjectInitCurrentDraft {
  if (!Array.isArray(currentDraft) || !aiDraft || !Array.isArray(aiDraft.tasks)) throw new TypeError('invalid project init draft')
  const result = clone(currentDraft) as DraftRecord[]
  const ids = validateCurrentIds(currentDraft, context)
  const actionMap = decisionMap(decisions)
  aiDraft.tasks.forEach((task, taskIndex) => {
    const source = task as DraftRecord
    validateAiIds(source, ids)
    const taskKey = `task-${taskIndex}`
    const action = actionMap.get(taskKey)
    const duplicate = source.merge_status !== 'new'
    if (duplicate && !action) return
    if (action === 'ignore') return
    const duplicateOf = positiveId(source.duplicate_of, `task ${taskIndex} duplicate_of`)
    const existingIndex = findTaskIndex(result, source, duplicateOf, action === 'supplement')
    const isNewTask = action === 'new' || (!duplicate && action !== 'supplement') || (duplicate && existingIndex < 0 && action !== 'supplement')
    if (action === 'supplement' && existingIndex >= 0) {
      const target = result[existingIndex]
      applyTaskSupplement(target, prepareTask(task, false))
      addSubtasks(target, task, actionMap, taskIndex, false)
      return
    }
    if (action === 'supplement' && existingIndex < 0) return
    if (isNewTask) {
      const prepared = prepareTask(task, true)
      addSubtasks(prepared, task, actionMap, taskIndex, true)
      result.push(prepared)
    }
  })
  return result as ProjectInitCurrentDraft
}

function collectWarnings(aiDraft: ProjectInitAiDraft, decisions: OwnerSubmitAiDecision[]): string[] {
  const actionMap = decisionMap(decisions)
  const warnings = [...(aiDraft.warnings ?? []).map((item) => `${item.code}: ${item.message}`)]
  aiDraft.tasks.forEach((task, taskIndex) => {
    const taskKey = `task-${taskIndex}`
    if (task.merge_status !== 'new' && !actionMap.has(taskKey)) warnings.push(`task-${taskIndex}: duplicate candidate requires a decision`)
    warnings.push(...task.warnings.map((item) => `${item.code}: ${item.message}`))
    task.subtasks.forEach((subtask, subtaskIndex) => {
      const key = `${taskKey}-subtask-${subtaskIndex}`
      if (subtask.merge_status !== 'new' && !actionMap.has(key) && actionMap.has(taskKey)) warnings.push(`${key}: duplicate candidate requires a decision`)
      warnings.push(...subtask.warnings.map((item) => `${item.code}: ${item.message}`))
    })
  })
  return [...new Set(warnings)]
}

export function buildAiMergePreview(
  currentDraft: ProjectInitCurrentDraft,
  aiDraft: ProjectInitAiDraft,
  decisions: OwnerSubmitAiDecision[],
  context: OwnerSubmitMergeContext = {},
): OwnerSubmitMergePreview {
  const draft = mergeAiDraft(currentDraft, aiDraft, decisions, context)
  const warnings = collectWarnings(aiDraft, decisions)
  const currentJson = JSON.stringify(currentDraft)
  const nextJson = JSON.stringify(draft)
  const currentTasks = currentDraft.length
  const addedTaskCount = Math.max(0, draft.length - currentTasks)
  const supplementedTaskCount = Math.max(0, draft.length - addedTaskCount) - currentTasks + (currentJson === nextJson ? 0 : 1)
  return {
    draft,
    changeCount: currentJson === nextJson ? 0 : Math.max(1, addedTaskCount + supplementedTaskCount),
    addedTaskCount,
    supplementedTaskCount: Math.max(0, supplementedTaskCount),
    warningCount: warnings.length,
    warnings,
  }
}

export function toCurrentDraft(tasks: Array<{
  title: string
  description?: string
  owner?: string
  helper?: string
  plan_start?: string
  plan_end?: string
  subtasks?: Array<{
    title: string
    evaluation_standard?: string
    assignee?: string
    assignee_id?: number | null
    helper?: string
    helper_ids?: number[]
    plan_start?: string
    plan_end?: string
  }>
}>): ProjectInitCurrentDraft {
  return tasks.map((task) => ({
    title: task.title ?? '',
    description: task.description ?? '',
    owner: task.owner ?? '',
    helper: task.helper ?? '',
    plan_start: task.plan_start ?? '',
    plan_end: task.plan_end ?? '',
    subtasks: (task.subtasks ?? []).map((subtask) => ({
      title: subtask.title ?? '',
      evaluation_standard: subtask.evaluation_standard ?? '',
      assignee: subtask.assignee ?? '',
      assignee_id: (subtask.assignee_id ?? null) as PositiveId | null,
      helper: subtask.helper ?? '',
      helper_ids: (Array.isArray(subtask.helper_ids) ? [...subtask.helper_ids] : []) as PositiveId[],
      plan_start: subtask.plan_start ?? '',
      plan_end: subtask.plan_end ?? '',
    })),
  }))
}

export function toSubmitDraft(tasks: ProjectInitCurrentDraft): SubmitTaskDraft[] {
  return tasks.map((task) => {
    const record = task as DraftRecord
    return {
      title: String(record.title ?? '').trim(),
      description: String(record.description ?? '').trim(),
      owner: String(record.owner ?? '').trim(),
      helper: String(record.helper ?? '').trim(),
      plan_start: String(record.plan_start ?? ''),
      plan_end: String(record.plan_end ?? ''),
      subtasks: (Array.isArray(record.subtasks) ? record.subtasks : []).map((subtask: DraftRecord) => ({
        title: String(subtask.title ?? '').trim(),
        evaluation_standard: String(subtask.evaluation_standard ?? '').trim(),
        assignee: String(subtask.assignee ?? '').trim(),
        assignee_id: subtask.assignee_id || undefined,
        helper: String(subtask.helper ?? '').trim(),
        helper_ids: Array.isArray(subtask.helper_ids) ? [...subtask.helper_ids] : [],
        plan_start: String(subtask.plan_start ?? ''),
        plan_end: String(subtask.plan_end ?? ''),
      })).filter((subtask) => subtask.title),
    }
  }).filter((task) => task.title)
}
