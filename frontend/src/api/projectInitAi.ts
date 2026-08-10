import { ApiError, apiDelete, apiGet, apiPost } from './client'

export type PositiveId = number & { readonly __positiveId: unique symbol }

export type ProjectInitAnalysisRunStatus =
  | 'queued'
  | 'processing'
  | 'retrying'
  | 'completed'
  | 'partial_failed'
  | 'failed'

export type ProjectInitAnalysisStage =
  | 'reading'
  | 'parsing'
  | 'extracting'
  | 'matching'
  | 'merging'
  | 'retrying'
  | 'completed'
  | 'failed'
  | 'stale'

export type AgentWarning = {
  code: string
  message: string
  person_name: string
}

export type Evidence = {
  attachment_id: PositiveId | null
  file_name: string
  location: string
  excerpt: string
}

export type AgentSubTask = {
  title: string
  description: string
  assignee_name: string
  assignee_id: PositiveId | null
  helper_names: string[]
  helper_ids: PositiveId[]
  priority: string
  status: string
  plan_start: string
  plan_end: string
  evaluation_standard: string
  confidence: number
  evidence: Evidence[]
  source: string
  merge_status: 'new' | 'definite_duplicate' | 'possible_duplicate'
  duplicate_of: PositiveId | null
  duplicate_reason: string
  warnings: AgentWarning[]
}

export type AgentTask = {
  title: string
  description: string
  owner_name: string
  owner_id: PositiveId | null
  priority: string
  status: string
  plan_start: string
  plan_end: string
  evidence: Evidence[]
  source: string
  confidence: number
  merge_status: 'new' | 'definite_duplicate' | 'possible_duplicate'
  duplicate_of: PositiveId | null
  duplicate_reason: string
  warnings: AgentWarning[]
  subtasks: AgentSubTask[]
}

export type ProjectInitAiDraft = {
  tasks: AgentTask[]
  warnings?: AgentWarning[]
  provider?: string
  model_name?: string
}

export type ProjectWorkProgressSubTaskDraft = {
  title: string
  evaluation_standard: string
  assignee: string
  assignee_id: PositiveId | null
  helper: string
  helper_ids: PositiveId[]
  plan_start: string
  plan_end: string
}

export type ProjectWorkProgressTaskDraft = {
  title: string
  description: string
  owner: string
  helper: string
  plan_start: string
  plan_end: string
  subtasks: ProjectWorkProgressSubTaskDraft[]
}

/** The immutable current work-progress-table snapshot sent at run creation. */
export type ProjectInitCurrentDraft = ProjectWorkProgressTaskDraft[]

/** The run response contains either the current snapshot or the AI result. */
export type ProjectInitDraft = ProjectInitAiDraft | ProjectInitCurrentDraft

export type ProjectInitAttachment = {
  id: PositiveId
  project_id: PositiveId
  storage_key: string
  original_name: string
  mime_type: string
  size_bytes: number
  uploaded_by: string
  uploaded_by_person_id: PositiveId | null
  deleted_at: string | null
  deleted_by: string
  created_at: string
  updated_at: string
}

export type ProjectInitSnapshot = {
  project: Record<string, unknown>
  members: Array<Record<string, unknown>>
  people: Array<Record<string, unknown>>
  tasks: Array<Record<string, unknown>>
  attachments: Array<{
    id: PositiveId
    storage_key: string
    original_name: string
    mime_type: string
    size_bytes: number
  }>
  current_draft: ProjectInitCurrentDraft
}

export type ProjectInitAnalysisRun = {
  id: PositiveId
  project_id: PositiveId
  attachment_ids: PositiveId[]
  status: ProjectInitAnalysisRunStatus
  stage: ProjectInitAnalysisStage
  progress: number
  error_message: string
  draft: ProjectInitDraft
  result_metadata: Record<string, unknown>
  applied_at: string | null
  created_at: string | null
  started_at: string | null
  finished_at: string | null
}

export type ProjectInitApiErrorBody = {
  detail?: string | Array<{ msg?: unknown; message?: unknown; type?: unknown; loc?: unknown } | string> | { message?: unknown }
  [key: string]: unknown
}

export class ProjectInitApiError extends Error {
  readonly status: number
  readonly detail: string
  readonly body: unknown
  readonly code: string

  constructor(status: number, detail: string, body: unknown = null, code = 'API_ERROR') {
    super(detail)
    this.name = 'ProjectInitApiError'
    this.status = status
    this.detail = detail
    this.body = body
    this.code = code
  }
}

export const PROJECT_INIT_AI_TIMEOUT_MS = 90_000

type UploadProgress = (percent: number) => void
type UnknownRecord = Record<string, unknown>

const RUN_STATUSES = ['queued', 'processing', 'retrying', 'completed', 'partial_failed', 'failed'] as const
const RUN_STAGES = ['reading', 'parsing', 'extracting', 'matching', 'merging', 'retrying', 'completed', 'failed', 'stale'] as const
const MERGE_STATUSES = ['new', 'definite_duplicate', 'possible_duplicate'] as const

function isRecord(value: unknown): value is UnknownRecord {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function invalidResponse(message: string, body: unknown, status = 200): never {
  throw new ProjectInitApiError(status, `invalid project init AI response: ${message}`, body, 'RESPONSE_VALIDATION_ERROR')
}

function required(record: UnknownRecord, key: string, body: unknown): unknown {
  if (!Object.prototype.hasOwnProperty.call(record, key)) invalidResponse(`missing ${key}`, body)
  return record[key]
}

function stringValue(value: unknown, label: string, body: unknown, minLength = 0, maxLength = Number.POSITIVE_INFINITY): string {
  if (typeof value !== 'string') invalidResponse(`${label} must be a string`, body)
  if (value.length < minLength || value.length > maxLength) invalidResponse(`${label} length is out of range`, body)
  return value
}

function nullableString(value: unknown, label: string, body: unknown): string | null {
  if (value === null) return null
  return stringValue(value, label, body)
}

function numberValue(value: unknown, label: string, body: unknown, min = Number.NEGATIVE_INFINITY, max = Number.POSITIVE_INFINITY): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) invalidResponse(`${label} must be a number`, body)
  if (value < min || value > max) invalidResponse(`${label} is out of range`, body)
  return value
}

function positiveId(value: unknown, label: string, body: unknown = value): PositiveId {
  if (typeof value !== 'number' || !Number.isInteger(value) || value <= 0) {
    if (body === value) throw new RangeError(`${label} must be a positive integer`)
    invalidResponse(`${label} must be a positive integer`, body)
  }
  return value as PositiveId
}

function optionalPositiveId(value: unknown, label: string, body: unknown): PositiveId | null {
  return value === null ? null : positiveId(value, label, body)
}

function arrayValue(value: unknown, label: string, body: unknown, minLength = 0, maxLength = Number.POSITIVE_INFINITY): unknown[] {
  if (!Array.isArray(value)) invalidResponse(`${label} must be an array`, body)
  if (value.length < minLength || value.length > maxLength) invalidResponse(`${label} length is out of range`, body)
  return value
}

function recordValue(value: unknown, label: string, body: unknown): UnknownRecord {
  if (!isRecord(value)) invalidResponse(`${label} must be an object`, body)
  return value
}

function stringArray(value: unknown, label: string, body: unknown, maxLength = Number.POSITIVE_INFINITY): string[] {
  return arrayValue(value, label, body, 0, maxLength).map((item, index) => stringValue(item, `${label}[${index}]`, body))
}

function positiveIdArray(value: unknown, label: string, body: unknown, maxLength = Number.POSITIVE_INFINITY): PositiveId[] {
  return arrayValue(value, label, body, 0, maxLength).map((item, index) => positiveId(item, `${label}[${index}]`, body))
}

function warning(value: unknown, body: unknown): AgentWarning {
  const record = recordValue(value, 'warning', body)
  return {
    code: stringValue(required(record, 'code', body), 'warning.code', body, 1, 64),
    message: stringValue(required(record, 'message', body), 'warning.message', body, 1, 300),
    person_name: stringValue(required(record, 'person_name', body), 'warning.person_name', body, 0, 50),
  }
}

function evidence(value: unknown, body: unknown): Evidence {
  const record = recordValue(value, 'evidence', body)
  return {
    attachment_id: optionalPositiveId(required(record, 'attachment_id', body), 'evidence.attachment_id', body),
    file_name: stringValue(required(record, 'file_name', body), 'evidence.file_name', body, 1, 255),
    location: stringValue(required(record, 'location', body), 'evidence.location', body, 1, 200),
    excerpt: stringValue(required(record, 'excerpt', body), 'evidence.excerpt', body, 1, 300),
  }
}

function mergeStatus(value: unknown, label: string, body: unknown): AgentTask['merge_status'] {
  if (typeof value !== 'string' || !(MERGE_STATUSES as readonly string[]).includes(value)) {
    invalidResponse(`${label} has an invalid value`, body)
  }
  return value as AgentTask['merge_status']
}

function subTask(value: unknown, body: unknown): AgentSubTask {
  const record = recordValue(value, 'subtask', body)
  return {
    title: stringValue(required(record, 'title', body), 'subtask.title', body, 1, 200),
    description: stringValue(required(record, 'description', body), 'subtask.description', body, 0, 2_000),
    assignee_name: stringValue(required(record, 'assignee_name', body), 'subtask.assignee_name', body, 0, 50),
    assignee_id: optionalPositiveId(required(record, 'assignee_id', body), 'subtask.assignee_id', body),
    helper_names: stringArray(required(record, 'helper_names', body), 'subtask.helper_names', body, 20),
    helper_ids: positiveIdArray(required(record, 'helper_ids', body), 'subtask.helper_ids', body, 20),
    priority: stringValue(required(record, 'priority', body), 'subtask.priority', body, 0, 30),
    status: stringValue(required(record, 'status', body), 'subtask.status', body, 0, 50),
    plan_start: stringValue(required(record, 'plan_start', body), 'subtask.plan_start', body, 0, 50),
    plan_end: stringValue(required(record, 'plan_end', body), 'subtask.plan_end', body, 0, 50),
    evaluation_standard: stringValue(required(record, 'evaluation_standard', body), 'subtask.evaluation_standard', body, 0, 1_000),
    confidence: numberValue(required(record, 'confidence', body), 'subtask.confidence', body, 0, 1),
    evidence: arrayValue(required(record, 'evidence', body), 'subtask.evidence', body, 0, 10).map((item) => evidence(item, body)),
    source: stringValue(required(record, 'source', body), 'subtask.source', body, 0, 255),
    merge_status: mergeStatus(required(record, 'merge_status', body), 'subtask.merge_status', body),
    duplicate_of: optionalPositiveId(required(record, 'duplicate_of', body), 'subtask.duplicate_of', body),
    duplicate_reason: stringValue(required(record, 'duplicate_reason', body), 'subtask.duplicate_reason', body, 0, 300),
    warnings: arrayValue(required(record, 'warnings', body), 'subtask.warnings', body, 0, 20).map((item) => warning(item, body)),
  }
}

function task(value: unknown, body: unknown): AgentTask {
  const record = recordValue(value, 'task', body)
  return {
    title: stringValue(required(record, 'title', body), 'task.title', body, 1, 200),
    description: stringValue(required(record, 'description', body), 'task.description', body, 0, 2_000),
    owner_name: stringValue(required(record, 'owner_name', body), 'task.owner_name', body, 0, 50),
    owner_id: optionalPositiveId(required(record, 'owner_id', body), 'task.owner_id', body),
    priority: stringValue(required(record, 'priority', body), 'task.priority', body, 0, 30),
    status: stringValue(required(record, 'status', body), 'task.status', body, 0, 50),
    plan_start: stringValue(required(record, 'plan_start', body), 'task.plan_start', body, 0, 50),
    plan_end: stringValue(required(record, 'plan_end', body), 'task.plan_end', body, 0, 50),
    evidence: arrayValue(required(record, 'evidence', body), 'task.evidence', body, 0, 10).map((item) => evidence(item, body)),
    source: stringValue(required(record, 'source', body), 'task.source', body, 0, 255),
    confidence: numberValue(required(record, 'confidence', body), 'task.confidence', body, 0, 1),
    merge_status: mergeStatus(required(record, 'merge_status', body), 'task.merge_status', body),
    duplicate_of: optionalPositiveId(required(record, 'duplicate_of', body), 'task.duplicate_of', body),
    duplicate_reason: stringValue(required(record, 'duplicate_reason', body), 'task.duplicate_reason', body, 0, 300),
    warnings: arrayValue(required(record, 'warnings', body), 'task.warnings', body, 0, 20).map((item) => warning(item, body)),
    subtasks: arrayValue(required(record, 'subtasks', body), 'task.subtasks', body, 1, 100).map((item) => subTask(item, body)),
  }
}

function currentSubTask(value: unknown, body: unknown): ProjectWorkProgressSubTaskDraft {
  const record = recordValue(value, 'current_draft.subtask', body)
  return {
    title: stringValue(required(record, 'title', body), 'current_draft.subtask.title', body),
    evaluation_standard: stringValue(required(record, 'evaluation_standard', body), 'current_draft.subtask.evaluation_standard', body),
    assignee: stringValue(required(record, 'assignee', body), 'current_draft.subtask.assignee', body),
    assignee_id: optionalPositiveId(required(record, 'assignee_id', body), 'current_draft.subtask.assignee_id', body),
    helper: stringValue(required(record, 'helper', body), 'current_draft.subtask.helper', body),
    helper_ids: positiveIdArray(required(record, 'helper_ids', body), 'current_draft.subtask.helper_ids', body),
    plan_start: stringValue(required(record, 'plan_start', body), 'current_draft.subtask.plan_start', body),
    plan_end: stringValue(required(record, 'plan_end', body), 'current_draft.subtask.plan_end', body),
  }
}

function currentTask(value: unknown, body: unknown): ProjectWorkProgressTaskDraft {
  const record = recordValue(value, 'current_draft.task', body)
  return {
    title: stringValue(required(record, 'title', body), 'current_draft.task.title', body),
    description: stringValue(required(record, 'description', body), 'current_draft.task.description', body),
    owner: stringValue(required(record, 'owner', body), 'current_draft.task.owner', body),
    helper: stringValue(required(record, 'helper', body), 'current_draft.task.helper', body),
    plan_start: stringValue(required(record, 'plan_start', body), 'current_draft.task.plan_start', body),
    plan_end: stringValue(required(record, 'plan_end', body), 'current_draft.task.plan_end', body),
    subtasks: arrayValue(required(record, 'subtasks', body), 'current_draft.task.subtasks', body).map((item) => currentSubTask(item, body)),
  }
}

function decodeCurrentDraft(value: unknown, body: unknown): ProjectInitCurrentDraft {
  return arrayValue(value, 'current_draft', body).map((item) => currentTask(item, body))
}

function decodeDraft(value: unknown, body: unknown): ProjectInitDraft {
  if (Array.isArray(value)) return decodeCurrentDraft(value, body)
  const record = recordValue(value, 'draft', body)
  const decoded: ProjectInitAiDraft = {
    // Failed provider runs legitimately persist an empty task list. Non-empty
    // tasks still pass through the full task/subtask/evidence validators below.
    tasks: arrayValue(required(record, 'tasks', body), 'draft.tasks', body, 0, 100).map((item) => task(item, body)),
  }
  if (Object.prototype.hasOwnProperty.call(record, 'warnings')) {
    decoded.warnings = arrayValue(record.warnings, 'draft.warnings', body, 0, 20).map((item) => warning(item, body))
  }
  if (Object.prototype.hasOwnProperty.call(record, 'provider')) {
    decoded.provider = stringValue(record.provider, 'draft.provider', body)
  }
  if (Object.prototype.hasOwnProperty.call(record, 'model_name')) {
    decoded.model_name = stringValue(record.model_name, 'draft.model_name', body)
  }
  return decoded
}

function attachment(value: unknown, body: unknown): ProjectInitAttachment {
  const record = recordValue(value, 'attachment', body)
  return {
    id: positiveId(required(record, 'id', body), 'attachment.id', body),
    project_id: positiveId(required(record, 'project_id', body), 'attachment.project_id', body),
    storage_key: stringValue(required(record, 'storage_key', body), 'attachment.storage_key', body),
    original_name: stringValue(required(record, 'original_name', body), 'attachment.original_name', body),
    mime_type: stringValue(required(record, 'mime_type', body), 'attachment.mime_type', body),
    size_bytes: numberValue(required(record, 'size_bytes', body), 'attachment.size_bytes', body),
    uploaded_by: stringValue(required(record, 'uploaded_by', body), 'attachment.uploaded_by', body),
    uploaded_by_person_id: optionalPositiveId(required(record, 'uploaded_by_person_id', body), 'attachment.uploaded_by_person_id', body),
    deleted_at: nullableString(required(record, 'deleted_at', body), 'attachment.deleted_at', body),
    deleted_by: stringValue(required(record, 'deleted_by', body), 'attachment.deleted_by', body),
    created_at: stringValue(required(record, 'created_at', body), 'attachment.created_at', body),
    updated_at: stringValue(required(record, 'updated_at', body), 'attachment.updated_at', body),
  }
}

function decodeRun(value: unknown, status = 200): ProjectInitAnalysisRun {
  const record = recordValue(value, 'analysis run', value)
  const runStatus = required(record, 'status', value)
  const stage = required(record, 'stage', value)
  if (typeof runStatus !== 'string' || !(RUN_STATUSES as readonly string[]).includes(runStatus)) invalidResponse('status has an invalid value', value, status)
  if (typeof stage !== 'string' || !(RUN_STAGES as readonly string[]).includes(stage)) invalidResponse('stage has an invalid value', value, status)
  const progress = numberValue(required(record, 'progress', value), 'progress', value)
  if (!Number.isInteger(progress) || progress < 0 || progress > 100) invalidResponse('progress must be an integer from 0 to 100', value, status)
  return {
    id: positiveId(required(record, 'id', value), 'run.id', value),
    project_id: positiveId(required(record, 'project_id', value), 'run.project_id', value),
    attachment_ids: positiveIdArray(required(record, 'attachment_ids', value), 'run.attachment_ids', value),
    status: runStatus as ProjectInitAnalysisRunStatus,
    stage: stage as ProjectInitAnalysisStage,
    progress,
    error_message: stringValue(required(record, 'error_message', value), 'run.error_message', value),
    draft: decodeDraft(required(record, 'draft', value), value),
    result_metadata: recordValue(required(record, 'result_metadata', value), 'run.result_metadata', value),
    applied_at: nullableString(required(record, 'applied_at', value), 'run.applied_at', value),
    created_at: nullableString(required(record, 'created_at', value), 'run.created_at', value),
    started_at: nullableString(required(record, 'started_at', value), 'run.started_at', value),
    finished_at: nullableString(required(record, 'finished_at', value), 'run.finished_at', value),
  }
}

function decodeAttachmentList(value: unknown, status = 200): ProjectInitAttachment[] {
  return arrayValue(value, 'attachments', value).map((item) => attachment(item, value))
}

function decodeDeleteResult(value: unknown, status = 200): { ok: boolean } {
  const record = recordValue(value, 'delete response', value)
  if (typeof required(record, 'ok', value) !== 'boolean') invalidResponse('delete response.ok must be a boolean', value, status)
  return { ok: record.ok as boolean }
}

function errorDetail(body: unknown, fallback: string): string {
  if (!isRecord(body)) return fallback
  const detail = body.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => {
      if (typeof item === 'string') return item
      if (isRecord(item)) {
        const message = typeof item.msg === 'string' ? item.msg : typeof item.message === 'string' ? item.message : ''
        const location = Array.isArray(item.loc) ? ` (${item.loc.join('.')})` : ''
        return message ? `${message}${location}` : JSON.stringify(item)
      }
      return String(item)
    }).filter(Boolean)
    if (messages.length) return messages.join('; ')
  }
  if (isRecord(detail) && typeof detail.message === 'string' && detail.message.trim()) return detail.message
  return fallback
}

function toProjectInitError(error: unknown): ProjectInitApiError {
  if (error instanceof ProjectInitApiError) return error
  if (error instanceof ApiError) return new ProjectInitApiError(error.status, errorDetail(error.body, error.message), error.body, 'HTTP_ERROR')
  if (error instanceof Error) return new ProjectInitApiError(0, error.message || 'project init AI request failed', null, 'NETWORK_ERROR')
  return new ProjectInitApiError(0, 'project init AI request failed', error, 'NETWORK_ERROR')
}

async function projectJson<T>(request: () => Promise<unknown>, decode: (value: unknown, status?: number) => T): Promise<T> {
  try {
    return decode(await request())
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error
    throw toProjectInitError(error)
  }
}

async function apiPostWithSignal(path: string, body: unknown, signal: AbortSignal): Promise<unknown> {
  const response = await fetch(path, {
    method: 'POST',
    credentials: 'include',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  const text = await response.text()
  let parsed: unknown = null
  if (text) {
    try {
      parsed = JSON.parse(text)
    } catch {
      parsed = text
    }
  }
  if (!response.ok) {
    throw new ProjectInitApiError(response.status, errorDetail(parsed, `request failed: ${response.status}`), parsed, 'HTTP_ERROR')
  }
  return parsed
}

export function listInitAttachments(projectId: number): Promise<ProjectInitAttachment[]> {
  positiveId(projectId, 'projectId')
  return projectJson(() => apiGet<unknown>(projectPath(projectId, '/init-attachments')), decodeAttachmentList)
}

export function downloadInitAttachmentUrl(projectId: number, attachmentId: number): string {
  return projectPath(projectId, `/init-attachments/${positiveId(attachmentId, 'attachmentId')}/download`)
}

function projectPath(projectId: number, suffix: string): string {
  return `/api/projects/${positiveId(projectId, 'projectId')}${suffix}`
}

function uploadOneInitAttachment(
  projectId: number,
  file: File,
  loadedBefore: number,
  totalBytes: number,
  onProgress?: UploadProgress,
  signal?: AbortSignal,
): Promise<ProjectInitAttachment> {
  const form = new FormData()
  form.append('file', file)

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    let settled = false
    const cleanup = () => signal?.removeEventListener('abort', abort)
    const fail = (error: unknown) => {
      if (settled) return
      settled = true
      cleanup()
      if (error instanceof DOMException && error.name === 'AbortError') reject(error)
      else reject(toProjectInitError(error))
    }
    const abort = () => {
      try { xhr.abort() } finally { fail(new DOMException('upload aborted', 'AbortError')) }
    }

    xhr.open('POST', projectPath(projectId, '/init-attachments'))
    xhr.withCredentials = true
    xhr.timeout = PROJECT_INIT_AI_TIMEOUT_MS
    signal?.addEventListener('abort', abort, { once: true })
    if (signal?.aborted) {
      abort()
      return
    }
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(Math.round(((loadedBefore + event.loaded) / Math.max(totalBytes, 1)) * 100))
    }
    xhr.onerror = () => fail(new ProjectInitApiError(0, 'upload failed; please check the network', null, 'NETWORK_ERROR'))
    xhr.ontimeout = () => {
      if (settled) return
      settled = true
      cleanup()
      try { xhr.abort() } finally {
        reject(new ProjectInitApiError(0, 'upload timed out; please try again', null, 'TIMEOUT_ERROR'))
      }
    }
    xhr.onabort = () => fail(new DOMException('upload aborted', 'AbortError'))
    xhr.onload = () => {
      let body: unknown
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null
      } catch {
        fail(new ProjectInitApiError(xhr.status, 'invalid JSON response', xhr.responseText, 'JSON_PARSE_ERROR'))
        return
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const decoded = attachment(body, body)
          settled = true
          cleanup()
          resolve(decoded)
        } catch (error) {
          fail(error)
        }
        return
      }
      fail(new ProjectInitApiError(xhr.status, errorDetail(body, `upload failed: ${xhr.status}`), body, 'HTTP_ERROR'))
    }
    try {
      xhr.send(form)
    } catch (error) {
      fail(error)
    }
  })
}

export async function uploadInitAttachments(
  projectId: number,
  files: File[],
  onProgress?: UploadProgress,
  signal?: AbortSignal,
): Promise<ProjectInitAttachment[]> {
  positiveId(projectId, 'projectId')
  if (files.length === 0) return []
  const totalBytes = files.reduce((sum, file) => sum + file.size, 0)
  const results: ProjectInitAttachment[] = []
  let loadedBefore = 0
  for (const file of files) {
    const result = await uploadOneInitAttachment(projectId, file, loadedBefore, totalBytes, onProgress, signal)
    results.push(result)
    loadedBefore += file.size
    onProgress?.(Math.round((loadedBefore / Math.max(totalBytes, 1)) * 100))
  }
  return results
}

export function deleteInitAttachment(projectId: number, attachmentId: number): Promise<{ ok: boolean }> {
  positiveId(projectId, 'projectId')
  positiveId(attachmentId, 'attachmentId')
  return projectJson(() => apiDelete<unknown>(projectPath(projectId, `/init-attachments/${attachmentId}`)), decodeDeleteResult)
}

export function createInitAnalysisRun(
  projectId: number,
  attachmentIds: number[],
  currentDraft: ProjectInitCurrentDraft = [],
  signal?: AbortSignal,
): Promise<ProjectInitAnalysisRun> {
  positiveId(projectId, 'projectId')
  const uniqueAttachmentIds = [...new Set(attachmentIds.map((id) => positiveId(id, 'attachmentId')))]
  return projectJson(
    () => signal
      ? apiPostWithSignal(projectPath(projectId, '/init-analysis-runs'), {
        attachment_ids: uniqueAttachmentIds,
        current_draft: currentDraft,
      }, signal)
      : apiPost<unknown>(projectPath(projectId, '/init-analysis-runs'), {
      attachment_ids: uniqueAttachmentIds,
      current_draft: currentDraft,
    }),
    decodeRun,
  )
}

export function getLatestInitAnalysisRun(projectId: number): Promise<ProjectInitAnalysisRun> {
  positiveId(projectId, 'projectId')
  return projectJson(() => apiGet<unknown>(projectPath(projectId, '/init-analysis-runs/latest')), decodeRun)
}

export function getInitAnalysisRun(projectId: number, runId: number): Promise<ProjectInitAnalysisRun> {
  positiveId(projectId, 'projectId')
  positiveId(runId, 'runId')
  return projectJson(() => apiGet<unknown>(projectPath(projectId, `/init-analysis-runs/${positiveId(runId, 'runId')}`)), decodeRun)
}

export function retryInitAnalysisRun(projectId: number, runId: number, signal?: AbortSignal): Promise<ProjectInitAnalysisRun> {
  positiveId(projectId, 'projectId')
  positiveId(runId, 'runId')
  const path = projectPath(projectId, `/init-analysis-runs/${positiveId(runId, 'runId')}/retry`)
  return projectJson(() => signal ? apiPostWithSignal(path, {}, signal) : apiPost<unknown>(path, {}), decodeRun)
}

export function applyInitAnalysisRun(projectId: number, runId: number): Promise<ProjectInitAnalysisRun> {
  positiveId(projectId, 'projectId')
  positiveId(runId, 'runId')
  return projectJson(() => apiPost<unknown>(projectPath(projectId, `/init-analysis-runs/${positiveId(runId, 'runId')}/apply`), {}), decodeRun)
}
