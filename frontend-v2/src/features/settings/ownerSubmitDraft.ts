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
const INFORMATIONAL_PERSON_WARNINGS = new Set(['will_join_project'])

function isInformationalPersonWarning(warning: { code?: unknown }): boolean {
  return INFORMATIONAL_PERSON_WARNINGS.has(String(warning.code ?? ''))
}

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
  if (id !== null && known && !known.has(id)) throw new RangeError(`${label} references unknown ${label.includes('member') || label.includes('helper') ? 'member' : 'snapshot record'} ID`)
  return id
}

function asSet(values?: ReadonlyArray<number>): Set<number> | undefined {
  if (!values) return undefined
  const result = new Set<number>()
  values.forEach((value, index) => {
    const id = positiveId(value, `known ID ${index}`)
    if (id !== null) result.add(id)
  })
  return result
}

function readFirst(record: DraftRecord, keys: string[]): unknown {
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(record, key)) return record[key]
  }
  return undefined
}

function readOptionalId(record: DraftRecord, keys: string[], label: string, known?: ReadonlySet<number>): number | null {
  return validateKnownId(readFirst(record, keys), label, known)
}

function readHelperIds(record: DraftRecord, label: string, known?: ReadonlySet<number>): number[] {
  const rawValues: unknown[] = []
  for (const key of ['helper_ids', 'helperIds']) {
    if (Object.prototype.hasOwnProperty.call(record, key)) {
      if (!Array.isArray(record[key])) throw new TypeError(`${label} must be an array`)
      rawValues.push(...record[key])
    }
  }
  const result: number[] = []
  for (const value of rawValues) {
    const id = validateKnownId(value, label, known)
    if (id !== null && !result.includes(id)) result.push(id)
  }
  return result
}

function normaliseOwnerHelpers(record: DraftRecord, ownerId: number | null, label: string, known?: ReadonlySet<number>): void {
  const hasSnake = Object.prototype.hasOwnProperty.call(record, 'helper_ids')
  const hasCamel = Object.prototype.hasOwnProperty.call(record, 'helperIds')
  if (!hasSnake && !hasCamel) return
  const helperIds = readHelperIds(record, label, known).filter((id) => id !== ownerId)
  if (hasSnake) record.helper_ids = [...helperIds]
  if (hasCamel) record.helperIds = [...helperIds]
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
    readOptionalId(taskRecord, ['owner_id', 'ownerId'], `task ${taskIndex} owner`, memberIds)
    readHelperIds(taskRecord, `task ${taskIndex} helper`, memberIds)
    const subtasks = Array.isArray(taskRecord.subtasks) ? taskRecord.subtasks : []
    subtasks.forEach((subtask: DraftRecord, subtaskIndex: number) => {
      const subtaskId = readId(subtask, ['id', 'subtask_id'], `subtask ${taskIndex}-${subtaskIndex}`, subtaskIds.size > 0 ? subtaskIds : undefined)
      if (subtaskId !== null) subtaskIds.add(subtaskId)
      readOptionalId(subtask, ['owner_id', 'ownerId', 'assignee_id', 'assigneeId'], `subtask ${taskIndex}-${subtaskIndex} member`, memberIds)
      readHelperIds(subtask, `subtask ${taskIndex}-${subtaskIndex} helper`, memberIds)
    })
  })
  return { taskIds, subtaskIds, memberIds }
}

function validateAiIds(task: DraftRecord, context: { taskIds: ReadonlySet<number>; subtaskIds: ReadonlySet<number>; memberIds?: ReadonlySet<number> }): void {
  readOptionalId(task, ['owner_id', 'ownerId'], 'task member', context.memberIds)
  readOptionalId(task, ['duplicate_of', 'duplicateOf'], 'task duplicate_of', context.taskIds)
  readHelperIds(task, 'task helper', context.memberIds)
  const taskWarnings = hasBlockingPersonWarning(task)
  if (taskWarnings && task.owner_id !== null && task.owner_id !== undefined) positiveId(task.owner_id, 'task owner_id')
  for (const subtask of Array.isArray(task.subtasks) ? task.subtasks : []) {
    readOptionalId(subtask, ['assignee_id', 'assigneeId', 'owner_id', 'ownerId'], 'subtask member', context.memberIds)
    readOptionalId(subtask, ['duplicate_of', 'duplicateOf'], 'subtask duplicate_of', context.subtaskIds)
    readHelperIds(subtask, 'subtask helper', context.memberIds)
  }
}

function prepareTask(task: AgentTask, _isNew: boolean, memberIds?: ReadonlySet<number>): DraftRecord {
  const source = task as DraftRecord
  const result: DraftRecord = {
    title: source.title ?? '',
    description: source.description ?? '',
    goal: source.goal ?? source.description ?? '',
    acceptance_criteria: source.acceptance_criteria ?? '',
    process: source.process ?? '',
    owner: source.owner_name ?? '',
    helper: '',
    plan_start: source.plan_start ?? '',
    plan_end: source.plan_end ?? '',
    subtasks: [],
    evidence: mergeEvidence([], source.evidence, source.source ?? ''),
  }
  if (!hasBlockingPersonWarning(source)) {
    const ownerId = readOptionalId(source, ['owner_id', 'ownerId'], 'task member', memberIds)
    if (ownerId !== null) result.owner_id = ownerId
    if (Object.prototype.hasOwnProperty.call(source, 'helper_ids') || Object.prototype.hasOwnProperty.call(source, 'helperIds')) {
      result.helper_ids = readHelperIds(source, 'task helper', memberIds).filter((id) => id !== ownerId)
    }
    normaliseOwnerHelpers(result, ownerId, 'task helper', memberIds)
  }
  return result
}

function prepareSubtask(subtask: AgentSubTask, _isNew: boolean, memberIds?: ReadonlySet<number>, allowPersonBinding = true): DraftRecord {
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
  if (allowPersonBinding && !hasBlockingPersonWarning(source)) {
    const assigneeId = readOptionalId(source, ['assignee_id', 'assigneeId', 'owner_id', 'ownerId'], 'subtask member', memberIds)
    if (assigneeId !== null) result.assignee_id = assigneeId
    result.helper_ids = readHelperIds(source, 'subtask helper', memberIds).filter((id) => id !== assigneeId)
    normaliseOwnerHelpers(result, assigneeId, 'subtask helper', memberIds)
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

function applyTaskSupplement(target: DraftRecord, source: DraftRecord, memberIds?: ReadonlySet<number>): void {
  mergeEmptyFields(target, source, ['description', 'goal', 'acceptance_criteria', 'process', 'owner', 'helper', 'plan_start', 'plan_end', 'status', 'priority'])
  const ownerId = readOptionalId(target, ['owner_id', 'ownerId'], 'task member', memberIds) ?? readOptionalId(source, ['owner_id', 'ownerId'], 'task member', memberIds)
  if (ownerId !== null && isBlank(readFirst(target, ['owner_id', 'ownerId']))) target.owner_id = ownerId
  const mergedHelpers = [...readHelperIds(target, 'task helper', memberIds), ...readHelperIds(source, 'task helper', memberIds)]
  if (mergedHelpers.length > 0 || Object.prototype.hasOwnProperty.call(target, 'helper_ids') || Object.prototype.hasOwnProperty.call(source, 'helper_ids')) {
    target.helper_ids = [...new Set(mergedHelpers)].filter((id) => id !== ownerId)
  }
  normaliseOwnerHelpers(target, ownerId, 'task helper')
  target.evidence = mergeEvidence(target.evidence, source.evidence, source.source ?? '')
}

function applySubtaskSupplement(target: DraftRecord, source: DraftRecord, memberIds?: ReadonlySet<number>): void {
  mergeEmptyFields(target, source, ['evaluation_standard', 'assignee', 'helper', 'plan_start', 'plan_end', 'status', 'priority'])
  const ownerId = readOptionalId(target, ['assignee_id', 'assigneeId', 'owner_id', 'ownerId'], 'subtask member', memberIds) ?? readOptionalId(source, ['assignee_id', 'assigneeId', 'owner_id', 'ownerId'], 'subtask member', memberIds)
  if (ownerId !== null && isBlank(readFirst(target, ['assignee_id', 'assigneeId', 'owner_id', 'ownerId']))) target.assignee_id = ownerId
  const currentHelpers = readHelperIds(target, 'subtask helper', memberIds)
  const incomingHelpers = readHelperIds(source, 'subtask helper', memberIds)
  if (currentHelpers.length > 0 || incomingHelpers.length > 0 || Object.prototype.hasOwnProperty.call(target, 'helper_ids')) {
    target.helper_ids = [...new Set([...currentHelpers, ...incomingHelpers])].filter((id) => id !== ownerId)
  }
  normaliseOwnerHelpers(target, ownerId, 'subtask helper')
  target.evidence = mergeEvidence(target.evidence, source.evidence, source.source ?? '')
}

function addSubtasks(target: DraftRecord, task: AgentTask, actionMap: Map<string, OwnerSubmitAiDecisionAction>, taskIndex: number, isNewTask: boolean, memberIds?: ReadonlySet<number>): void {
  const existing = Array.isArray(target.subtasks) ? target.subtasks : []
  const next = [...existing]
  const allowPersonBinding = !hasBlockingPersonWarning(task as DraftRecord)
  task.subtasks.forEach((subtask, subtaskIndex) => {
    const source = subtask as DraftRecord
    const key = `task-${taskIndex}-subtask-${subtaskIndex}`
    const action = actionMap.get(key)
    const duplicate = source.merge_status !== 'new'
    if (duplicate && !action) throw new Error(`${key}: duplicate subtask requires a decision`)
    if (action === 'ignore') return
    if (action === 'supplement') {
      const duplicateOf = readOptionalId(source, ['duplicate_of', 'duplicateOf'], `${key} duplicate_of`)
      const existingIndex = findSubtaskIndex(next, source, duplicateOf)
      if (existingIndex < 0) throw new Error(`${key}: supplement target subtask was not found`)
      applySubtaskSupplement(next[existingIndex], prepareSubtask(subtask, false, memberIds, allowPersonBinding), memberIds)
      return
    }
    if (duplicate && action !== 'new') throw new Error(`${key}: invalid subtask decision`)
    next.push(prepareSubtask(subtask, isNewTask, memberIds, allowPersonBinding))
  })
  target.subtasks = next
}

function normaliseDraftMembers(draft: DraftRecord[], memberIds?: ReadonlySet<number>): void {
  draft.forEach((task) => {
    const taskOwnerId = readOptionalId(task, ['owner_id', 'ownerId'], 'task member', memberIds)
    normaliseOwnerHelpers(task, taskOwnerId, 'task helper', memberIds)
    for (const subtask of Array.isArray(task.subtasks) ? task.subtasks as DraftRecord[] : []) {
      const ownerId = readOptionalId(subtask, ['owner_id', 'ownerId', 'assignee_id', 'assigneeId'], 'subtask member', memberIds)
      normaliseOwnerHelpers(subtask, ownerId, 'subtask helper', memberIds)
    }
  })
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
    const duplicateOf = readOptionalId(source, ['duplicate_of', 'duplicateOf'], `task ${taskIndex} duplicate_of`, ids.taskIds)
    const existingIndex = findTaskIndex(result, source, duplicateOf, action === 'supplement')
    if (action === 'supplement') {
      if (existingIndex < 0) throw new Error(`task ${taskIndex}: supplement target task was not found`)
      const target = result[existingIndex]
      applyTaskSupplement(target, prepareTask(task, false, ids.memberIds), ids.memberIds)
      addSubtasks(target, task, actionMap, taskIndex, false, ids.memberIds)
      return
    }
    if (!duplicate || action === 'new') {
      const prepared = prepareTask(task, true, ids.memberIds)
      addSubtasks(prepared, task, actionMap, taskIndex, true, ids.memberIds)
      result.push(prepared)
    }
  })
  normaliseDraftMembers(result, ids.memberIds)
  return result as ProjectInitCurrentDraft
}

function collectWarnings(aiDraft: ProjectInitAiDraft, decisions: OwnerSubmitAiDecision[]): string[] {
  const actionMap = decisionMap(decisions)
  const warnings = [...(aiDraft.warnings ?? []).filter((item) => !isInformationalPersonWarning(item)).map((item) => `${item.code}: ${item.message}`)]
  aiDraft.tasks.forEach((task, taskIndex) => {
    const taskKey = `task-${taskIndex}`
    if (task.merge_status !== 'new' && !actionMap.has(taskKey)) warnings.push(`task-${taskIndex}: duplicate candidate requires a decision`)
    warnings.push(...task.warnings.filter((item) => !isInformationalPersonWarning(item)).map((item) => `${item.code}: ${item.message}`))
    task.subtasks.forEach((subtask, subtaskIndex) => {
      const key = `${taskKey}-subtask-${subtaskIndex}`
      if (subtask.merge_status !== 'new' && !actionMap.has(key)) warnings.push(`${key}: duplicate candidate requires a decision`)
      warnings.push(...subtask.warnings.filter((item) => !isInformationalPersonWarning(item)).map((item) => `${item.code}: ${item.message}`))
    })
  })
  return [...new Set(warnings)]
}

function countEvidenceAdditions(before: unknown, after: unknown): number {
  const beforeKeys = new Set((Array.isArray(before) ? before : []).filter(Boolean).map((item) => evidenceKey(item as DraftRecord)))
  return (Array.isArray(after) ? after : []).filter(Boolean).reduce((count, item) => count + (beforeKeys.has(evidenceKey(item as DraftRecord)) ? 0 : 1), 0)
}

function countSupplementalChanges(before: DraftRecord, after: DraftRecord): number {
  const fields = ['description', 'owner', 'helper', 'plan_start', 'plan_end', 'status', 'priority', 'evaluation_standard', 'assignee', 'assignee_id', 'helper_ids']
  let count = fields.reduce((total, field) => total + (isBlank(before[field]) && !isBlank(after[field]) ? 1 : 0), 0)
  count += countEvidenceAdditions(before.evidence, after.evidence)
  const beforeSubtasks = Array.isArray(before.subtasks) ? before.subtasks as DraftRecord[] : []
  const afterSubtasks = Array.isArray(after.subtasks) ? after.subtasks as DraftRecord[] : []
  for (const subtask of afterSubtasks) {
    const index = findSubtaskIndex(beforeSubtasks, subtask, readOptionalId(subtask, ['id', 'subtask_id'], 'subtask'))
    if (index < 0) {
      count += 1
      continue
    }
    count += countSupplementalChanges(beforeSubtasks[index], subtask)
  }
  return count
}

function countSupplementalChangesForPreview(currentDraft: ProjectInitCurrentDraft, mergedDraft: ProjectInitCurrentDraft, aiDraft: ProjectInitAiDraft, decisions: OwnerSubmitAiDecision[]): number {
  const actionMap = decisionMap(decisions)
  const current = currentDraft as DraftRecord[]
  const merged = mergedDraft as DraftRecord[]
  let count = 0
  aiDraft.tasks.forEach((task, taskIndex) => {
    if (actionMap.get(`task-${taskIndex}`) !== 'supplement') return
    const source = task as DraftRecord
    const duplicateOf = readOptionalId(source, ['duplicate_of', 'duplicateOf'], `task ${taskIndex} duplicate_of`)
    const beforeIndex = findTaskIndex(current, source, duplicateOf, true)
    const afterIndex = findTaskIndex(merged, source, duplicateOf, true)
    if (beforeIndex >= 0 && afterIndex >= 0) count += countSupplementalChanges(current[beforeIndex], merged[afterIndex])
  })
  return count
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
  const addedTaskCount = Math.max(0, draft.length - currentDraft.length)
  const supplementedTaskCount = countSupplementalChangesForPreview(currentDraft, draft, aiDraft, decisions)
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
  id?: number
  task_id?: number
  title: string
  description?: string
  goal?: string
  acceptance_criteria?: string
  process?: string
  owner?: string
  helper?: string
  plan_start?: string
  plan_end?: string
  subtasks?: Array<{
    id?: number
    subtask_id?: number
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
    ...(task.id !== undefined ? { id: task.id } : {}),
    ...(task.task_id !== undefined ? { task_id: task.task_id } : {}),
    title: task.title ?? '',
    description: task.description ?? '',
    goal: task.goal ?? task.description ?? '',
    acceptance_criteria: task.acceptance_criteria ?? '',
    process: task.process ?? '',
    owner: task.owner ?? '',
    helper: task.helper ?? '',
    plan_start: task.plan_start ?? '',
    plan_end: task.plan_end ?? '',
    subtasks: (task.subtasks ?? []).map((subtask) => ({
      ...(subtask.id !== undefined ? { id: subtask.id } : {}),
      ...(subtask.subtask_id !== undefined ? { subtask_id: subtask.subtask_id } : {}),
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
      goal: String(record.goal ?? record.description ?? '').trim(),
      acceptance_criteria: String(record.acceptance_criteria ?? '').trim(),
      process: String(record.process ?? '').trim(),
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
