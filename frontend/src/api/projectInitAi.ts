import { ApiError, apiDelete, apiGet, apiPost } from './client'

export type ProjectInitAnalysisRunStatus =
  | 'queued'
  | 'processing'
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
  attachment_id: number | null
  file_name: string
  location: string
  excerpt: string
}

export type AgentSubTask = {
  title: string
  description: string
  assignee_name: string
  assignee_id: number | null
  helper_names: string[]
  helper_ids: number[]
  priority: string
  status: string
  plan_start: string
  plan_end: string
  evaluation_standard: string
  confidence: number
  evidence: Evidence[]
  source: string
  merge_status: 'new' | 'possible_duplicate' | 'confirmed_duplicate'
  duplicate_of: number | null
  duplicate_reason: string
  warnings: AgentWarning[]
}

export type AgentTask = {
  title: string
  description: string
  owner_name: string
  owner_id: number | null
  priority: string
  status: string
  plan_start: string
  plan_end: string
  evidence: Evidence[]
  source: string
  confidence: number
  merge_status: 'new' | 'possible_duplicate' | 'confirmed_duplicate'
  duplicate_of: number | null
  duplicate_reason: string
  warnings: AgentWarning[]
  subtasks: AgentSubTask[]
}

export type ProjectInitDraft = {
  tasks: AgentTask[]
  provider?: string
  model_name?: string
  warnings?: AgentWarning[]
}

export type ProjectInitAttachment = {
  id: number
  project_id: number
  storage_key: string
  original_name: string
  mime_type: string
  size_bytes: number
  uploaded_by: string
  uploaded_by_person_id: number | null
  created_at: string
  updated_at: string
}

export type ProjectInitSnapshot = {
  attachments: Array<{
    id: number
    storage_key: string
    original_name: string
    mime_type?: string
    size_bytes?: number
  }>
  people?: unknown[]
  tasks?: unknown[]
  current_draft?: unknown[]
}

export type ProjectInitAnalysisRun = {
  id: number
  project_id: number
  attachment_ids: number[]
  status: ProjectInitAnalysisRunStatus
  stage: ProjectInitAnalysisStage
  progress: number
  error_message: string
  /** The queued/failed response may contain the submitted current-draft array. */
  draft: ProjectInitDraft | unknown[]
  result_metadata: Record<string, unknown>
  applied_at: string | null
  created_at: string | null
  started_at: string | null
  finished_at: string | null
  /** The server stores this immutable snapshot; older responses may omit it. */
  snapshot?: ProjectInitSnapshot
}

export type ProjectInitApiErrorBody = {
  detail?: string | { message?: string }
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

type UploadProgress = (percent: number) => void

function positiveId(value: number, label: string): number {
  if (!Number.isInteger(value) || value <= 0) {
    throw new RangeError(`${label} must be a positive integer`)
  }
  return value
}

function projectPath(projectId: number, suffix: string): string {
  return `/api/projects/${positiveId(projectId, 'projectId')}${suffix}`
}

function jsonValue<T>(value: unknown, status = 200): T {
  if (value === null || typeof value !== 'object') {
    throw new ProjectInitApiError(status, 'invalid JSON response', value, 'JSON_PARSE_ERROR')
  }
  return value as T
}

function errorDetail(body: unknown, fallback: string): string {
  if (body && typeof body === 'object') {
    const detail = (body as ProjectInitApiErrorBody).detail
    if (typeof detail === 'string' && detail) return detail
    if (detail && typeof detail === 'object' && typeof detail.message === 'string') return detail.message
  }
  return fallback
}

function toProjectInitError(error: unknown): ProjectInitApiError {
  if (error instanceof ProjectInitApiError) return error
  if (error instanceof ApiError) {
    return new ProjectInitApiError(error.status, errorDetail(error.body, error.message), error.body)
  }
  if (error instanceof Error) return new ProjectInitApiError(0, error.message, null, 'NETWORK_ERROR')
  return new ProjectInitApiError(0, 'project init AI request failed', error, 'NETWORK_ERROR')
}

async function projectJson<T>(request: () => Promise<unknown>): Promise<T> {
  try {
    return jsonValue<T>(await request())
  } catch (error) {
    throw toProjectInitError(error)
  }
}

export function listInitAttachments(projectId: number): Promise<ProjectInitAttachment[]> {
  positiveId(projectId, 'projectId')
  return projectJson<ProjectInitAttachment[]>(() =>
    apiGet<unknown>(projectPath(projectId, '/init-attachments')),
  )
}

export function downloadInitAttachmentUrl(projectId: number, attachmentId: number): string {
  return projectPath(projectId, `/init-attachments/${positiveId(attachmentId, 'attachmentId')}/download`)
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
      reject(error)
    }
    const abort = () => {
      xhr.abort()
      fail(new DOMException('upload aborted', 'AbortError'))
    }

    xhr.open('POST', projectPath(projectId, '/init-attachments'))
    xhr.withCredentials = true
    signal?.addEventListener('abort', abort, { once: true })
    if (signal?.aborted) {
      abort()
      return
    }
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress?.(Math.round(((loadedBefore + event.loaded) / Math.max(totalBytes, 1)) * 100))
      }
    }
    xhr.onerror = () => fail(new ProjectInitApiError(0, 'upload failed; please check the network', null, 'NETWORK_ERROR'))
    xhr.onabort = () => fail(new DOMException('upload aborted', 'AbortError'))
    xhr.onload = () => {
      let body: unknown = null
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null
      } catch {
        fail(new ProjectInitApiError(xhr.status, 'invalid JSON response', xhr.responseText, 'JSON_PARSE_ERROR'))
        return
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const attachment = jsonValue<ProjectInitAttachment>(body, xhr.status)
          settled = true
          cleanup()
          resolve(attachment)
        } catch (error) {
          fail(error)
        }
        return
      }
      fail(new ProjectInitApiError(xhr.status, errorDetail(body, `upload failed: ${xhr.status}`), body))
    }
    xhr.send(form)
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
  return projectJson<{ ok: boolean }>(() =>
    apiDelete<unknown>(projectPath(projectId, `/init-attachments/${attachmentId}`)),
  )
}

export function createInitAnalysisRun(
  projectId: number,
  attachmentIds: number[],
): Promise<ProjectInitAnalysisRun> {
  positiveId(projectId, 'projectId')
  const uniqueAttachmentIds = [...new Set(attachmentIds.map((id) => positiveId(id, 'attachmentId')))]
  return projectJson<ProjectInitAnalysisRun>(() =>
    apiPost<unknown>(projectPath(projectId, '/init-analysis-runs'), { attachment_ids: uniqueAttachmentIds }),
  )
}

export function getLatestInitAnalysisRun(projectId: number): Promise<ProjectInitAnalysisRun> {
  positiveId(projectId, 'projectId')
  return projectJson<ProjectInitAnalysisRun>(() =>
    apiGet<unknown>(projectPath(projectId, '/init-analysis-runs/latest')),
  )
}

export function getInitAnalysisRun(projectId: number, runId: number): Promise<ProjectInitAnalysisRun> {
  positiveId(projectId, 'projectId')
  positiveId(runId, 'runId')
  return projectJson<ProjectInitAnalysisRun>(() =>
    apiGet<unknown>(projectPath(projectId, `/init-analysis-runs/${positiveId(runId, 'runId')}`)),
  )
}

export function retryInitAnalysisRun(projectId: number, runId: number): Promise<ProjectInitAnalysisRun> {
  positiveId(projectId, 'projectId')
  positiveId(runId, 'runId')
  return projectJson<ProjectInitAnalysisRun>(() =>
    apiPost<unknown>(projectPath(projectId, `/init-analysis-runs/${positiveId(runId, 'runId')}/retry`), {}),
  )
}

export function applyInitAnalysisRun(projectId: number, runId: number): Promise<ProjectInitAnalysisRun> {
  positiveId(projectId, 'projectId')
  positiveId(runId, 'runId')
  return projectJson<ProjectInitAnalysisRun>(() =>
    apiPost<unknown>(projectPath(projectId, `/init-analysis-runs/${positiveId(runId, 'runId')}/apply`), {}),
  )
}
