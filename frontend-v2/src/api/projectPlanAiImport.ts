import { apiPost, apiUpload } from './client'
import type { BatchImportResult, BatchImportRow } from './projects'

export type ProjectPlanAiEvidence = {
  attachment_id: number | null
  file_name: string
  location: string
  excerpt: string
}

export type ProjectPlanAiSubTask = {
  title: string
  description?: string
  assignee_name?: string
  assignee_id?: number | null
  helper_names?: string[]
  helper_ids?: number[]
  priority?: string
  status?: string
  plan_start?: string
  plan_end?: string
  evaluation_standard?: string
  evidence?: ProjectPlanAiEvidence[]
  confidence?: number
  source?: string
  merge_status?: 'new' | 'definite_duplicate' | 'possible_duplicate'
  duplicate_of?: number | null
  duplicate_reason?: string
  warnings?: Array<{ code: string; message: string; person_name?: string }>
}

export type ProjectPlanAiTask = {
  title: string
  description?: string
  goal?: string
  acceptance_criteria?: string
  process?: string
  owner_name?: string
  owner_id?: number | null
  priority?: string
  status?: string
  plan_start?: string
  plan_end?: string
  evidence?: ProjectPlanAiEvidence[]
  confidence?: number
  source?: string
  merge_status?: 'new' | 'definite_duplicate' | 'possible_duplicate'
  duplicate_of?: number | null
  duplicate_reason?: string
  warnings?: Array<{ code: string; message: string; person_name?: string }>
  subtasks: ProjectPlanAiSubTask[]
}

export type ProjectPlanAiPreview = {
  project_profile: {
    name?: string
    objectives?: string
    background?: string
    expected_outcomes?: string
    start_date?: string
    end_date?: string
    description?: string
    confidence?: number
    evidence?: ProjectPlanAiEvidence[]
    warnings?: Array<{ code: string; message: string; person_name?: string }>
  }
  tasks: ProjectPlanAiTask[]
  warnings: Array<{ code: string; message: string; person_name?: string }>
  source_files: string[]
  provider: string
  model_name: string
  fallback_mode: 'ai' | 'deterministic'
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function decodePreview(value: unknown): ProjectPlanAiPreview {
  if (!isRecord(value) || !isRecord(value.project_profile) || !Array.isArray(value.tasks)) {
    throw new Error('AI 导入返回的数据结构无效')
  }
  const fallbackMode = value.fallback_mode
  if (fallbackMode !== 'ai' && fallbackMode !== 'deterministic') {
    throw new Error('AI 导入返回的处理模式无效')
  }
  return {
    project_profile: value.project_profile as ProjectPlanAiPreview['project_profile'],
    tasks: value.tasks as ProjectPlanAiTask[],
    warnings: Array.isArray(value.warnings) ? value.warnings as ProjectPlanAiPreview['warnings'] : [],
    source_files: Array.isArray(value.source_files) ? value.source_files.map(text).filter(Boolean) : [],
    provider: text(value.provider),
    model_name: text(value.model_name),
    fallback_mode: fallbackMode,
  }
}

export function previewAiProjectPlan(
  file: File,
  options: { projectName?: string; targetProjectId?: number } = {},
): Promise<ProjectPlanAiPreview> {
  const form = new FormData()
  form.append('file', file, file.name || 'work-plan.tsv')
  if (options.projectName?.trim()) form.append('project_name', options.projectName.trim())
  if (options.targetProjectId) form.append('target_project_id', String(options.targetProjectId))
  return apiUpload<unknown>('/api/projects/ai-plan-import/preview', form).then(decodePreview)
}

export function applyAiProjectPlan(rows: BatchImportRow[]): Promise<BatchImportResult> {
  return apiPost<BatchImportResult>('/api/projects/ai-plan-import/apply', { rows })
}
